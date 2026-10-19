package io.github.sussic.pyfa

import org.json.JSONObject

data class ProjectedDroneRow(val index: Int, val objectKey: String, val itemId: Int, val name: String,
    val amount: Int, val active: Int, val rangeM: Double?, val editable: Boolean, val unavailableReason: String?)
data class ProjectedDroneDetails(val fitId: String, val revision: Long, val isStructure: Boolean,
    val stacks: List<ProjectedDroneRow>)
data class ProjectedDroneVariation(val id: Int, val name: String, val enabled: Boolean)
data class ProjectedDroneOptions(val fitId: String, val revision: Long, val index: Int, val objectKey: String,
    val itemId: Int, val activationAllowed: Boolean, val activationUnavailableReason: String?,
    val variations: List<ProjectedDroneVariation>)
data class ProjectedDroneAddOptions(val fitId: String, val revision: Long, val itemId: Int,
    val isDrone: Boolean, val isProjectable: Boolean, val isStructure: Boolean,
    val enabled: Boolean, val unavailableReason: String?)

/** Only the agreed budget prefixes are surfaced from a wrapped Python read error. */
internal fun projectedDroneReadError(failure: Throwable, fallback: String): String =
    if (generateSequence(failure) { it.cause }.take(8).any { error -> error.message?.let {
        it.contains("Projected-drone evaluation budget:") || it.contains("Projected-drone capacitor evaluation budget:")
    } == true }) "This configuration exceeds the projected-drone evaluation budget. Reduce its quantity or complexity before retrying."
    else fallback

/** Counts are source inputs. Storage and evaluation limits are not game fitting limits. */
internal object ProjectedDroneCodec {
    private fun count(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "invalid projected drone integer")
    }.toInt()
    private fun id(raw: Any) = count(raw).also { OfflineFeatureCodec.expect(it > 0, "invalid projected item ID") }
    private fun label(raw: Any) = OfflineFeatureCodec.text(raw).also { OfflineFeatureCodec.expect(it.isNotBlank(), "empty projected label") }
    private fun reason(raw: Any): String? = if (raw === JSONObject.NULL) null else label(raw)
    private fun revision(raw: Any) = OfflineFeatureCodec.integer(raw).also { OfflineFeatureCodec.expect(it >= 1, "invalid projected revision") }
    private fun range(raw: Any): Double? {
        if (raw === JSONObject.NULL) return null
        val value = when (raw) { is Int -> raw.toDouble(); is Long -> raw.toDouble(); is Double -> raw
            else -> OfflineFeatureCodec.reject("projected range number required") }
        OfflineFeatureCodec.expect(value.isFinite() && value >= 0, "invalid projected range")
        if (raw is Long) OfflineFeatureCodec.expect(java.math.BigDecimal(raw).compareTo(java.math.BigDecimal(value)) == 0,
            "projected range integer loses precision")
        return value
    }
    private fun header(root: JSONObject): Pair<String, Long> = with(OfflineFeatureCodec) {
        expect(integer(root.get("version")) == 1L, "unsupported projected-drone version")
        identity(root.get("fit_id")) to revision(root.get("revision"))
    }
    fun details(json: String): ProjectedDroneDetails = with(OfflineFeatureCodec) {
        val root = parse(json); keys(root, "version", "fit_id", "revision", "is_structure", "stacks")
        val (fit, revision) = header(root); val structure = bool(root.get("is_structure"))
        val rawRows = rows(root.get("stacks")); expect(rawRows.size <= 1024, "too many projected drone stacks")
        val stacks = rawRows.mapIndexed { position, raw ->
            val row = obj(raw)
            keys(row, "index", "object_key", "item_id", "name", "amount", "active", "range_m", "editable", "unavailable_reason")
            val index = count(row.get("index")); expect(index == position, "projected stack position differs")
            val amount = id(row.get("amount")); val active = count(row.get("active"))
            expect(active <= amount, "projected active quantity exceeds total")
            val editable = bool(row.get("editable")); val why = reason(row.get("unavailable_reason"))
            expect(editable == (why == null) && (!structure || !editable), "projected availability differs")
            ProjectedDroneRow(index, ProjectedModuleCodec.objectKey(row.get("object_key")), id(row.get("item_id")),
                label(row.get("name")), amount, active, range(row.get("range_m")), editable, why)
        }
        expect(stacks.map { it.objectKey }.distinct().size == stacks.size, "duplicate projected identity")
        expect(stacks.map { it.itemId }.distinct().size == stacks.size, "duplicate projected drone type")
        ProjectedDroneDetails(fit, revision, structure, frozen(stacks))
    }
    fun options(json: String): ProjectedDroneOptions = with(OfflineFeatureCodec) {
        val root = parse(json)
        keys(root, "version", "fit_id", "revision", "index", "object_key", "item_id", "activation_allowed", "activation_unavailable_reason", "variations")
        val (fit, revision) = header(root)
        val allowed = bool(root.get("activation_allowed")); val why = reason(root.get("activation_unavailable_reason"))
        expect(allowed == (why == null), "projected activation availability differs")
        val rawChoices = rows(root.get("variations")); expect(rawChoices.size <= 8192, "too many projected drone variations")
        val choices = rawChoices.map { raw ->
            val row = obj(raw); keys(row, "id", "name", "enabled")
            ProjectedDroneVariation(id(row.get("id")), label(row.get("name")), bool(row.get("enabled")))
        }
        expect(choices.map { it.id }.distinct().size == choices.size, "duplicate projected variation")
        val index = count(root.get("index")); expect(index < 1024, "projected stack position exceeds storage boundary")
        ProjectedDroneOptions(fit, revision, index, ProjectedModuleCodec.objectKey(root.get("object_key")),
            id(root.get("item_id")), allowed, why, frozen(choices))
    }
    fun addOptions(json: String): ProjectedDroneAddOptions = with(OfflineFeatureCodec) {
        val root = parse(json)
        keys(root, "version", "fit_id", "revision", "item_id", "is_drone", "is_projectable", "is_structure", "enabled", "unavailable_reason")
        val (fit, revision) = header(root)
        val drone = bool(root.get("is_drone")); val projectable = bool(root.get("is_projectable"))
        val structure = bool(root.get("is_structure")); val enabled = bool(root.get("enabled")); val why = reason(root.get("unavailable_reason"))
        expect(enabled == (why == null) && (!enabled || drone && projectable && !structure), "projected add availability differs")
        ProjectedDroneAddOptions(fit, revision, id(root.get("item_id")), drone, projectable, structure, enabled, why)
    }
}
