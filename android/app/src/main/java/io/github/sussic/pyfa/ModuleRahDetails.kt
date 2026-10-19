package io.github.sussic.pyfa

import org.json.JSONObject

enum class RahMode(val wire: String) { FIT("fit"), DISABLED("disabled"), BUILTIN("builtin"), NAMED("named") }
sealed interface RahPattern {
    data object Disabled : RahPattern
    data class Builtin(val patternId: Int) : RahPattern
    /** Only graph-owned native state may decode this tag, never external FitSpec input. */
    data class Named(val patternId: String) : RahPattern
}
data class RahComponents(val em: Double, val thermal: Double, val kinetic: Double, val explosive: Double)
data class RahBuiltin(val id: Int, val name: String, val components: RahComponents)
data class RahFitPattern(val name: String, val available: Boolean, val unavailableReason: String?, val components: RahComponents?)
data class ModuleRahRow(val index: Int, val objectKey: String, val itemId: Int, val name: String,
    val mode: RahMode, val patternId: Int?, val namedId: String? = null, val patternRevision: Long? = null,
    val patternName: String? = null, val components: RahComponents? = null)
data class ModuleRahDetails(val fitId: String, val revision: Long, val context: OfflineContext,
    val moduleOffset: Long, val moduleLimit: Int, val moduleTotal: Long,
    val modules: List<ModuleRahRow>, val fitPattern: RahFitPattern)

// Retained for the legacy direct bridge's fixed unsupported-object failure.
internal const val UNSUPPORTED_RAH_MESSAGE = "Custom reactive armor patterns are not supported by this editor"
internal class UnsupportedRahPatternException : IllegalStateException(UNSUPPORTED_RAH_MESSAGE)
internal fun isUnsupportedRahFailure(failure: Throwable): Boolean {
    var current: Throwable? = failure
    repeat(8) {
        val value = current ?: return false
        if (value.message?.contains(UNSUPPORTED_RAH_MESSAGE) == true) return true
        current = value.cause
    }
    return false
}

internal object ModuleRahCodec {
    private fun count(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "invalid RAH index or item ID")
    }.toInt()
    fun builtinId(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in -118L..-1L, "unknown built-in damage pattern ID")
    }.toInt()
    fun namedId(raw: Any): String = OfflineFeatureCodec.text(raw).also {
        OfflineFeatureCodec.expect(it == SELECTED_AMMO_PATTERN_ID || it.matches(Regex("damage:[0-9a-f]{32}")), "invalid named RAH identity")
    }
    private fun identity(raw: Any): String = OfflineFeatureCodec.text(raw).also {
        OfflineFeatureCodec.expect(it.matches(Regex("[0-9a-f]{32}")), "invalid local RAH identity")
    }
    private fun name(raw: Any): String = OfflineFeatureCodec.text(raw).also {
        OfflineFeatureCodec.expect(it.isNotBlank(), "empty RAH label")
    }
    private fun mode(raw: Any): RahMode = RahMode.entries.singleOrNull { it.wire == OfflineFeatureCodec.text(raw) }
        ?: OfflineFeatureCodec.reject("unsupported RAH mode")
    fun components(raw: Any): RahComponents = with(OfflineFeatureCodec) {
        val row = obj(raw); keys(row, "em", "thermal", "kinetic", "explosive")
        val amounts = listOf("em", "thermal", "kinetic", "explosive").map { field ->
            val value = when (val number = row.get(field)) {
                is Int -> number.toDouble(); is Long -> number.toDouble(); is Double -> number
                else -> reject("damage component number required")
            }
            expect(value.isFinite() && value >= 0, "invalid damage component"); value
        }
        expect(amounts.sum().let { it.isFinite() && it > 0 }, "empty or overflowing damage pattern")
        RahComponents(amounts[0], amounts[1], amounts[2], amounts[3])
    }
    fun pattern(raw: Any, trustedNative: Boolean = false): RahPattern = with(OfflineFeatureCodec) {
        val row = obj(raw)
        expect(row.has("mode"), "RAH mode required")
        when (mode(row.get("mode"))) {
            RahMode.DISABLED -> { keys(row, "mode"); RahPattern.Disabled }
            RahMode.BUILTIN -> { keys(row, "mode", "pattern_id"); RahPattern.Builtin(builtinId(row.get("pattern_id"))) }
            RahMode.NAMED -> { keys(row, "mode", "pattern_id"); expect(trustedNative, "named RAH requires native graph authority"); RahPattern.Named(namedId(row.get("pattern_id"))) }
            RahMode.FIT -> reject("omit default RAH input instead of storing it")
        }
    }
    fun encodePattern(value: RahPattern, trustedNative: Boolean = false): JSONObject = when (value) {
        RahPattern.Disabled -> JSONObject().put("mode", RahMode.DISABLED.wire)
        is RahPattern.Builtin -> JSONObject().put("mode", RahMode.BUILTIN.wire).put("pattern_id", builtinId(value.patternId))
        is RahPattern.Named -> {
            OfflineFeatureCodec.expect(trustedNative, "named RAH requires native graph authority")
            JSONObject().put("mode", RahMode.NAMED.wire).put("pattern_id", namedId(value.patternId))
        }
    }
    fun selection(raw: Any) = with(OfflineFeatureCodec) {
        val row = obj(raw)
        when (mode(row.get("mode"))) {
            RahMode.FIT, RahMode.DISABLED -> keys(row, "mode")
            RahMode.BUILTIN -> { keys(row, "mode", "pattern_id"); builtinId(row.get("pattern_id")) }
            RahMode.NAMED -> {
                keys(row, "mode", "pattern_id", "revision"); namedId(row.get("pattern_id"))
                expect(integer(row.get("revision")) > 0, "invalid named RAH revision")
            }
        }
    }
    fun descriptor(raw: Any): ModuleRahRow = with(OfflineFeatureCodec) {
        val row = obj(raw)
        keys(row, "index", "object_key", "item_id", "name", "mode", "builtin_id", "named_id", "pattern_revision", "pattern_name", "components")
        val mode = mode(row.get("mode"))
        val builtin = if (row.isNull("builtin_id")) null else builtinId(row.get("builtin_id"))
        val named = if (row.isNull("named_id")) null else namedId(row.get("named_id"))
        val revision = if (row.isNull("pattern_revision")) null else integer(row.get("pattern_revision"))
        val label = if (row.isNull("pattern_name")) null else name(row.get("pattern_name"))
        val components = if (row.isNull("components")) null else components(row.get("components"))
        expect(when (mode) {
            RahMode.FIT, RahMode.DISABLED -> builtin == null && named == null && revision == null && label == null && components == null
            RahMode.BUILTIN -> builtin != null && named == null && revision == 0L && label != null && components != null
            RahMode.NAMED -> builtin == null && named != null && revision != null && revision > 0 && label != null && components != null
        }, "inconsistent RAH pattern applicability")
        if (named == SELECTED_AMMO_PATTERN_ID) expect(label == "Selected Ammo", "protected RAH name differs")
        val itemId = count(row.get("item_id")); expect(itemId > 0, "invalid RAH module ID")
        ModuleRahRow(count(row.get("index")), ModuleRahCodec.identity(row.get("object_key")), itemId, name(row.get("name")), mode, builtin, named, revision, label, components)
    }
    fun decode(json: String): ModuleRahDetails = with(OfflineFeatureCodec) {
        expect(json.toByteArray(Charsets.UTF_8).size <= 524_288, "RAH details exceed byte limit")
        val root = parse(json); keys(root, "version", "context", "fit_id", "revision", "module_page", "fit_pattern")
        expect(integer(root.get("version")) == 2L, "unsupported RAH details version")
        val context = context(obj(root.get("context")))
        ModuleRahCodec.identity(context.sessionId)
        val revision = integer(root.get("revision")); expect(revision >= 1, "invalid RAH revision")
        val page = obj(root.get("module_page")); keys(page, "offset", "limit", "total", "entries")
        val offset = integer(page.get("offset")); val limit = integer(page.get("limit")); val total = integer(page.get("total"))
        expect(offset >= 0 && total >= 0 && limit in 1..25, "invalid RAH module page")
        val modules = rows(page.get("entries")).map(::descriptor)
        expect(modules.size.toLong() == minOf(limit, (total - offset).coerceAtLeast(0)), "incomplete RAH module page")
        expect(modules.zipWithNext().all { (a, b) -> a.index < b.index }, "unordered RAH modules")
        expect(modules.map { it.objectKey }.distinct().size == modules.size, "duplicate RAH module identity")
        val fitPattern = obj(root.get("fit_pattern")); keys(fitPattern, "name", "available", "unavailable_reason", "components")
        expect(text(fitPattern.get("name")) == "Fit pattern", "unsupported fit pattern label")
        val available = bool(fitPattern.get("available")); val reason = nullableText(fitPattern.get("unavailable_reason"))
        val preview = if (fitPattern.isNull("components")) null else components(fitPattern.get("components"))
        expect(if (available) reason == null && preview != null else reason == "zero_total" && preview == null, "invalid fit pattern preview")
        ModuleRahDetails(ModuleRahCodec.identity(root.get("fit_id")), revision, context, offset, limit.toInt(), total, frozen(modules),
            RahFitPattern("Fit pattern", available, reason, preview))
    }
}
