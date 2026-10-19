package io.github.sussic.pyfa

import java.util.Collections
import org.json.JSONArray
import org.json.JSONObject

/** Immutable versioned values. Null skill levels mean unlearned, never trained level zero. */
data class OfflineContext(val sessionId: String, val datasetSha256: String, val generation: Long) {
    fun json(): JSONObject = JSONObject().put("session_id", sessionId)
        .put("dataset_sha256", datasetSha256).put("generation", generation)
}
data class OfflineProfile(val id: String, val name: String, val readonly: Boolean,
    val defaultLevel: Int?, val levels: Map<Int, Int?>, val revision: Long,
    val implants: List<OfflineProfileImplant> = emptyList(),
    val secStatus: SecurityNumber = SecurityNumber(if (id == "builtin:all5") 5.0 else 0.0)) {
    val displayImplants get() = implants.sortedBy { it.slot }
    fun level(skillId: Int): Int? = if (levels.containsKey(skillId)) levels[skillId] else defaultLevel
}
data class OfflineProfileImplant(val implantId: String, val itemId: Int, val name: String, val slot: Int, val active: Boolean)
data class OfflineSkill(val id: Int, val name: String)
data class OfflineBinding(val profileId: String, val revision: Long, val fitRevision: Long, val implantSource: ImplantLocation)
data class OfflineHistory(val undoCount: Int, val redoCount: Int, val limit: Int,
    val undoLabel: String?, val redoLabel: String?)
data class OfflineFeatureState(val context: OfflineContext, val profiles: List<OfflineProfile>,
    val bindings: Map<String, OfflineBinding>, val skills: List<OfflineSkill>, val selectedFitId: String?,
    val history: OfflineHistory)
data class OfflineFeatureError(val code: String, val message: String)
data class OfflineFeatureResponse(val requestId: String?, val ok: Boolean, val committed: Boolean?,
    val reopenRequired: Boolean, val state: OfflineFeatureState?, val bridge: BridgeResponse?,
    val error: OfflineFeatureError?)

internal object OfflineFeatureCodec {
    internal fun reject(message: String): Nothing = throw BridgeProtocolException("Offline features: $message")
    internal fun expect(condition: Boolean, message: String) { if (!condition) reject(message) }
    internal fun obj(raw: Any): JSONObject = raw as? JSONObject ?: reject("object required")
    internal fun rows(raw: Any): List<Any> = (raw as? JSONArray ?: reject("array required")).let { a ->
        (0 until a.length()).map(a::get)
    }
    internal fun keys(row: JSONObject, vararg names: String) = expect(row.keys().asSequence().toSet() == names.toSet(), "unsupported fields")
    internal fun text(raw: Any): String = (raw as? String ?: reject("text required")).also { value ->
        var i = 0
        while (i < value.length) {
            val c = value[i++]
            if (Character.isHighSurrogate(c)) expect(i < value.length && Character.isLowSurrogate(value[i++]), "invalid Unicode")
            else expect(!Character.isLowSurrogate(c), "invalid Unicode")
        }
    }
    internal fun nullableText(raw: Any): String? = if (raw === JSONObject.NULL) null else text(raw)
    internal fun bool(raw: Any): Boolean = raw as? Boolean ?: reject("boolean required")
    internal fun integer(raw: Any): Long = when (raw) { is Int -> raw.toLong(); is Long -> raw; else -> reject("integer required") }
    internal fun identity(raw: Any): String = text(raw).also { expect(it.isNotBlank() && it.length <= 200 && it.none { c -> c.code < 32 }, "invalid identity") }
    internal fun level(raw: Any): Int? = if (raw === JSONObject.NULL) null else integer(raw).also { expect(it in 0..5, "invalid skill level") }.toInt()
    internal fun <T> frozen(values: Collection<T>): List<T> = Collections.unmodifiableList(ArrayList(values))
    internal fun <K,V> frozen(values: Map<K,V>): Map<K,V> = Collections.unmodifiableMap(LinkedHashMap(values))
    internal fun parse(raw: String): JSONObject = obj(StrictJson(raw).parse())
    // JSONObject.toString normalizes integral doubles; retain the original scalar types for BridgeCodec.
    internal fun json(raw: Any): String = when (raw) {
        is JSONObject -> raw.keys().asSequence().joinToString(",", "{", "}") { JSONObject.quote(it) + ":" + json(raw.get(it)) }
        is JSONArray -> rows(raw).joinToString(",", "[", "]") { json(it) }
        is String -> JSONObject.quote(raw)
        JSONObject.NULL -> "null"
        is Number, is Boolean -> raw.toString()
        else -> reject("unsupported JSON value")
    }
    internal fun context(row: JSONObject): OfflineContext {
        keys(row, "session_id", "dataset_sha256", "generation")
        val dataset = text(row.get("dataset_sha256")); expect(dataset.matches(Regex("[0-9a-f]{64}")), "invalid dataset")
        val generation = integer(row.get("generation")); expect(generation >= 1, "invalid generation")
        return OfflineContext(identity(row.get("session_id")), dataset, generation)
    }
    internal fun hexId(raw: Any): String = text(raw).also { expect(it.matches(Regex("[0-9a-f]{32}")), "invalid fit or row identity") }
    internal fun profileId(raw: Any): String = text(raw).also {
        expect(it in setOf("builtin:all0", "builtin:all5") || it.matches(Regex("profile:[0-9a-f]{32}")), "invalid profile identity")
    }
    internal fun safeText(raw: Any, limit: Int): String = text(raw).also {
        expect(it.isNotEmpty() && it.codePointCount(0, it.length) <= limit && it.none { c -> Character.isISOControl(c) }, "invalid safe text")
    }
    internal fun featureContext(row: JSONObject): OfflineContext = context(row).also { hexId(it.sessionId) }
    internal fun source(raw: Any): ImplantLocation = ImplantLocation.entries.singleOrNull { it.name == text(raw) } ?: reject("invalid implant source")
    internal fun positive(raw: Any): Long = integer(raw).also { expect(it >= 1, "positive revision required") }
    private fun itemId(raw: Any): Int = integer(raw).also { expect(it in 1..Int.MAX_VALUE.toLong(), "invalid item or slot") }.toInt()
    fun state(raw: String): OfflineFeatureState = state(parse(raw))
    internal fun state(root: JSONObject): OfflineFeatureState {
        keys(root, "version", "context", "profiles", "bindings", "skills", "selected_fit_id", "history")
        expect(integer(root.get("version")) == 3L, "unsupported version")
        expect(json(root).toByteArray(Charsets.UTF_8).size <= 524_288, "feature state exceeds 524288 bytes")
        val skills = rows(root.get("skills")).map { obj(it).let { row ->
            keys(row, "skill_id", "name")
            val id = integer(row.get("skill_id")); expect(id in 1..Int.MAX_VALUE.toLong(), "invalid skill")
            OfflineSkill(id.toInt(), text(row.get("name")).also { expect(it.isNotBlank(), "empty skill") })
        } }
        val skillIds = skills.map { it.id }.toSet(); expect(skillIds.size == skills.size && skills.isNotEmpty(), "duplicate or absent skills")
        val implantIds = mutableSetOf<String>()
        val profiles = rows(root.get("profiles")).map { obj(it).let { row ->
            keys(row, "profile_id", "name", "readonly", "default_level", "levels", "revision", "implants", "sec_status")
            val id = identity(row.get("profile_id")); val readonly = bool(row.get("readonly"))
            expect(if (readonly) id in setOf("builtin:all0", "builtin:all5") else id.matches(Regex("profile:[0-9a-f]{32}")), "invalid profile identity")
            val revision = integer(row.get("revision")); expect(if (readonly) revision == 0L else revision >= 1, "invalid profile revision")
            val levels = obj(row.get("levels")).let { values -> values.keys().asSequence().associate { key ->
                val skillId = key.toIntOrNull() ?: reject("invalid skill identity")
                expect(key == skillId.toString() && skillId in skillIds, "unknown skill")
                skillId to level(values.get(key))
            } }
            val implants = rows(row.get("implants")).map { raw -> obj(raw).let { implant ->
                keys(implant, "implant_id", "item_id", "name", "slot", "active")
                val rowId = hexId(implant.get("implant_id")); expect(implantIds.add(rowId), "duplicate profile implant identity")
                OfflineProfileImplant(rowId, itemId(implant.get("item_id")), text(implant.get("name")).also { expect(it.isNotEmpty() && it.none { c -> Character.isISOControl(c) }, "invalid implant name") },
                    itemId(implant.get("slot")), bool(implant.get("active")))
            } }
            expect(implants.map { it.slot }.toSet().size == implants.size && implants.map { it.itemId }.toSet().size == implants.size, "duplicate profile implant slot or item")
            // Existing C06 names may contain DEL/C1. Preserve them on read; new name requests remain strict safeText.
            val value = OfflineProfile(id, text(row.get("name")).also {
                expect(it.isNotBlank() && it == it.trim { c -> c.isWhitespace() || c == '\u0085' }
                    && it.codePointCount(0, it.length) <= 200 && it.none { c -> c.code < 32 }, "invalid profile name")
            }, readonly,
                level(row.get("default_level")), frozen(levels), revision, frozen(implants), PilotSecurityCodec.number(row.get("sec_status")))
            if (readonly) PilotSecurityCodec.builtin(id, value.secStatus)
            if (readonly) expect(implants.isEmpty(), "built-in implants must be empty")
            if (readonly) expect(value.levels.isEmpty() && value.name == if (id == "builtin:all0") "All 0" else "All 5", "modified built-in")
            if (readonly) expect(value.defaultLevel == if (id == "builtin:all0") null else 5, "modified built-in skills")
            value
        } }
        val profileIds = profiles.map { it.id }.toSet()
        expect(profiles.size == profileIds.size && profileIds.containsAll(setOf("builtin:all0", "builtin:all5")), "duplicate or absent profiles")
        val bindings = obj(root.get("bindings")).let { values -> values.keys().asSequence().associateWith { key ->
            hexId(key); val row = obj(values.get(key)); keys(row, "profile_id", "revision", "fit_revision", "implant_source")
            val id = identity(row.get("profile_id")); expect(id in profileIds, "missing assigned profile")
            OfflineBinding(id, positive(row.get("revision")), positive(row.get("fit_revision")), source(row.get("implant_source")))
        } }
        val selected = nullableText(root.get("selected_fit_id")); expect(selected == null || selected in bindings, "unknown selected fit")
        val history = obj(root.get("history")); keys(history, "undo_count", "redo_count", "limit", "undo_label", "redo_label")
        val limit = integer(history.get("limit")); val undo = integer(history.get("undo_count")); val redo = integer(history.get("redo_count"))
        expect(limit == 100L && undo in 0..limit && redo in 0..limit && undo + redo <= limit, "invalid history counts")
        fun label(name: String, count: Long): String? = nullableText(history.get(name)).also { expect(if (count == 0L) it == null else !it.isNullOrBlank(), "invalid history label") }
        return OfflineFeatureState(featureContext(obj(root.get("context"))), frozen(profiles), frozen(bindings), frozen(skills), selected,
            OfflineHistory(undo.toInt(), redo.toInt(), limit.toInt(), label("undo_label", undo), label("redo_label", redo)))
    }
    /** Validate the complete publication before any StateFlow can expose it. */
    internal fun validateLibrary(state: OfflineFeatureState, bridge: BridgeResponse) {
        expect(bridge.isSuccess && bridge.requestId == "bootstrap" && bridge.sessionId == state.context.sessionId, "invalid committed bridge")
        validateFits(state, bridge.fits)
    }
    internal fun validateFits(state: OfflineFeatureState, fits: List<FitSnapshot>) {
        expect(fits.map { it.id }.toSet() == state.bindings.keys && fits.map { it.id }.distinct().size == fits.size, "incomplete committed library")
        fits.forEach { fit ->
            val binding = state.bindings.getValue(fit.id)
            expect(binding.fitRevision == fit.revision, "binding fit revision differs")
            expect(state.profiles.any { it.id == binding.profileId }, "binding profile missing")
        }
    }
    fun response(raw: String, requestId: String, expected: OfflineContext, before: OfflineFeatureState? = null,
        anchorFitId: String? = before?.selectedFitId): OfflineFeatureResponse {
        val row = parse(raw)
        keys(row, "version", "request_id", "ok", "committed", "reopen_required", "state", "bridge", "error")
        expect(integer(row.get("version")) == 3L, "unsupported response version")
        val id = nullableText(row.get("request_id")); expect(id == requestId, "response identity differs")
        val ok = bool(row.get("ok")); val reopen = bool(row.get("reopen_required"))
        val committed = row.get("committed").let { if (it === JSONObject.NULL) null else bool(it) }
        if (ok) {
            expect(committed != null && !reopen && row.get("error") === JSONObject.NULL, "ambiguous success")
            val state = state(obj(row.get("state")))
            expect(state.context.sessionId == expected.sessionId && state.context.datasetSha256 == expected.datasetSha256, "response context differs")
            expect(if (committed == true) expected.generation < Long.MAX_VALUE && state.context.generation == expected.generation + 1
                else state.context.generation == expected.generation, "response generation differs")
            expect(state.selectedFitId == anchorFitId, "response anchor differs")
            if (committed == false && before != null) expect(state == before.copy(selectedFitId = anchorFitId), "no-op changed feature state")
            val bridge = BridgeCodec.decodeResponse(json(row.get("bridge")))
            validateLibrary(state, bridge)
            return OfflineFeatureResponse(id, true, committed, false, state, bridge, null)
        }
        expect(committed != true && (committed == null) == reopen, "ambiguous error status")
        expect(row.get("state") === JSONObject.NULL && row.get("bridge") === JSONObject.NULL, "failure published state")
        val error = obj(row.get("error")); keys(error, "code", "message")
        return OfflineFeatureResponse(id, false, committed, reopen, null, null,
            OfflineFeatureError(safeText(error.get("code"), 128), safeText(error.get("message"), 1024)))
    }
    fun request(requestId: String, context: OfflineContext, operation: String, arguments: JSONObject, anchorFitId: String?): String {
        safeText(requestId, 128); featureContext(context.json()); anchorFitId?.let(::hexId)
        fun profile(key: String = "profile_id") = profileId(arguments.get(key))
        fun revision(key: String = "revision") = positive(arguments.get(key))
        when (operation) {
            "create_profile" -> { keys(arguments, "name", "source"); safeText(arguments.get("name"), 200); profile("source") }
            "rename_profile" -> { keys(arguments, "profile_id", "revision", "name"); profile(); revision(); safeText(arguments.get("name"), 200) }
            "assign_profile" -> { keys(arguments, "fit_id", "profile_id"); hexId(arguments.get("fit_id")); profile() }
            "set_profile_skill" -> { keys(arguments, "profile_id", "revision", "skill_id", "level"); profile(); revision(); itemId(arguments.get("skill_id")); level(arguments.get("level")) }
            "delete_profile" -> { keys(arguments, "profile_id", "replacement"); profile(); if (arguments.get("replacement") !== JSONObject.NULL) profile("replacement") }
            "add_profile_implant" -> {
                keys(arguments, "profile_id", "revision", "item_id", "replace_implant_id"); profile(); revision(); itemId(arguments.get("item_id"))
                if (arguments.get("replace_implant_id") !== JSONObject.NULL) hexId(arguments.get("replace_implant_id"))
            }
            "remove_profile_implant" -> { keys(arguments, "profile_id", "revision", "implant_id"); profile(); revision(); hexId(arguments.get("implant_id")) }
            "set_implant_source" -> {
                keys(arguments, "fit_id", "fit_revision", "source"); val fit = hexId(arguments.get("fit_id")); revision("fit_revision"); source(arguments.get("source"))
                expect(anchorFitId != null && fit == anchorFitId, "source target must equal anchor")
            }
            "set_pilot_security" -> {
                keys(arguments, "fit_id", "fit_revision", "pilot")
                val fit = hexId(arguments.get("fit_id")); revision("fit_revision"); PilotSecurityCodec.nullable(arguments.get("pilot"))
                expect(anchorFitId != null && fit == anchorFitId, "pilot target must equal anchor")
            }
            "save_profile_security" -> {
                keys(arguments, "profile_id", "revision", "sec_status", "save_as")
                expect(!profile().startsWith("builtin:"), "built-in security is protected"); revision()
                PilotSecurityCodec.number(arguments.get("sec_status"))
                if (arguments.get("save_as") !== JSONObject.NULL) {
                    val name = safeText(arguments.get("save_as"), 200)
                    expect(name == name.trim { it.isWhitespace() || it == '\u0085' }, "invalid profile name")
                }
            }
            "undo", "redo" -> keys(arguments)
            else -> reject("unsupported feature operation")
        }
        return json(JSONObject().put("version", 3).put("request_id", requestId).put("context", context.json())
            .put("operation", operation).put("arguments", arguments).put("anchor_fit_id", anchorFitId ?: JSONObject.NULL)).also {
                expect(it.toByteArray(Charsets.UTF_8).size <= 16_384, "feature request exceeds 16384 bytes")
            }
    }
}
