package io.github.sussic.pyfa

import org.json.JSONObject

/** Raw JSON authority, not a rounded display value. BridgeContract.Security remains numeric-only. */
data class SecurityNumber(val raw: Number) {
    init {
        OfflineFeatureCodec.expect(raw is Int || raw is Long || raw is Double, "security number required")
        OfflineFeatureCodec.expect(raw.toDouble().let { it.isFinite() && it in -10.0..5.0 }, "security must be finite and within -10 to 5")
    }
    fun numericallyEquals(other: SecurityNumber) = raw.toDouble() == other.raw.toDouble()
    override fun toString() = raw.toString()
}

enum class PilotSecuritySource { CHARACTER, EXPLICIT }
data class PilotSecurityProfile(val id: String, val name: String, val revision: Long,
    val bindingRevision: Long, val readonly: Boolean, val secStatus: SecurityNumber)
data class PilotSecurityDetails(val context: OfflineContext, val fitId: String, val revision: Long,
    val hullId: Int, val hullName: String, val eligible: Boolean, val unavailableReason: String?,
    val profile: PilotSecurityProfile, val pilot: SecurityNumber?, val source: PilotSecuritySource,
    val effective: SecurityNumber, val presets: List<Int>)

/** Immutable owner captured before queueing. It carries the full saved binding, not a display name. */
data class PilotSecurityOwner(val context: OfflineContext, val fitId: String, val fitRevision: Long,
    val hullName: String, val binding: OfflineBinding, val profile: OfflineProfile) {
    fun validate(value: PilotSecurityDetails) = with(OfflineFeatureCodec) {
        expect(value.context == context && value.fitId == fitId && value.revision == fitRevision && value.hullName == hullName,
            "pilot details owner differs")
        expect(value.profile == PilotSecurityProfile(profile.id, profile.name, profile.revision,
            binding.revision, profile.readonly, profile.secStatus), "pilot details profile differs")
    }
    companion object {
        fun capture(state: OfflineFeatureState, fit: FitSnapshot): PilotSecurityOwner = with(OfflineFeatureCodec) {
            val binding = state.bindings[fit.id] ?: reject("pilot binding missing")
            expect(binding.fitRevision == fit.revision, "pilot fit revision differs")
            val profile = state.profiles.singleOrNull { it.id == binding.profileId } ?: reject("pilot profile missing")
            PilotSecurityOwner(state.context, fit.id, fit.revision, fit.ship, binding, profile)
        }
    }
}

internal object PilotSecurityCodec {
    val hulls = mapOf(44993 to "Pacifier", 44995 to "Enforcer", 44996 to "Marshal",
        85062 to "Sidewinder", 85229 to "Cobra", 85236 to "Python")
    val presets: List<Int> = OfflineFeatureCodec.frozen(listOf(-10, -8, -6, -4, -2, 0, 1, 2, 3, 4, 5))
    private val decimal = Regex("[+-]?(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
    fun number(raw: Any): SecurityNumber = SecurityNumber(raw as? Number ?: OfflineFeatureCodec.reject("security number required"))
    fun nullable(raw: Any): SecurityNumber? = if (raw === JSONObject.NULL) null else number(raw)
    fun entry(text: String): SecurityNumber? {
        val trimmed = text.trim()
        if (!decimal.matches(trimmed)) return null
        val value = trimmed.toDoubleOrNull() ?: return null
        return if (value.isFinite() && value in -10.0..5.0) SecurityNumber(value) else null
    }
    fun builtin(id: String, value: SecurityNumber) = with(OfflineFeatureCodec) {
        val expected = if (id == "builtin:all0") 0.0 else 5.0
        expect(value.raw is Double && java.lang.Double.doubleToRawLongBits(value.raw.toDouble()) ==
            java.lang.Double.doubleToRawLongBits(expected), "modified built-in security")
    }
    fun profileName(raw: Any): String = OfflineFeatureCodec.text(raw).also { value ->
        OfflineFeatureCodec.expect(value.isNotBlank() && value == value.trim { it.isWhitespace() || it == '\u0085' } &&
            value.codePointCount(0, value.length) <= 200 && value.none { it.code < 32 }, "invalid profile name")
    }
    fun decode(raw: String): PilotSecurityDetails = with(OfflineFeatureCodec) {
        expect(raw.toByteArray(Charsets.UTF_8).size <= 524_288, "pilot details exceed byte limit")
        val root = parse(raw)
        keys(root, "version", "context", "fit_id", "revision", "hull_id", "hull_name", "eligible", "unavailable_reason",
            "profile", "pilot", "source", "effective", "presets")
        expect(integer(root.get("version")) == 1L, "unsupported pilot details version")
        val hullId = integer(root.get("hull_id")).also { expect(it in 1..Int.MAX_VALUE.toLong(), "invalid hull ID") }.toInt()
        val hullName = text(root.get("hull_name")).also { expect(it.isNotBlank(), "empty hull name") }
        val eligible = bool(root.get("eligible")); val reason = nullableText(root.get("unavailable_reason"))
        expect(eligible == (hulls[hullId] == hullName), "incorrect pilot-security eligibility")
        val choices = rows(root.get("presets")).map { integer(it).also { n -> expect(n in -10L..5L, "invalid preset") }.toInt() }
        expect(if (eligible) reason == null && choices == presets else reason == "unsupported_hull" && choices.isEmpty(), "invalid pilot choices")
        val row = obj(root.get("profile"))
        keys(row, "profile_id", "name", "revision", "binding_revision", "readonly", "sec_status")
        val id = profileId(row.get("profile_id")); val readonly = bool(row.get("readonly"))
        expect(readonly == id.startsWith("builtin:"), "invalid pilot profile protection")
        val revision = integer(row.get("revision")); expect(if (readonly) revision == 0L else revision > 0, "invalid profile revision")
        val profile = PilotSecurityProfile(id, profileName(row.get("name")), revision, positive(row.get("binding_revision")), readonly, number(row.get("sec_status")))
        if (readonly) {
            expect(profile.name == if (id == "builtin:all0") "All 0" else "All 5", "modified built-in name")
            builtin(id, profile.secStatus)
        }
        val pilot = nullable(root.get("pilot"))
        val source = PilotSecuritySource.entries.singleOrNull { it.name == text(root.get("source")) } ?: reject("invalid pilot source")
        expect((source == PilotSecuritySource.CHARACTER) == (pilot == null), "pilot source differs from raw input")
        val effective = number(root.get("effective"))
        expect(effective.numericallyEquals(pilot ?: profile.secStatus), "pilot effective value differs")
        PilotSecurityDetails(featureContext(obj(root.get("context"))), hexId(root.get("fit_id")), positive(root.get("revision")),
            hullId, hullName, eligible, reason, profile, pilot, source, effective, frozen(choices))
    }
}
