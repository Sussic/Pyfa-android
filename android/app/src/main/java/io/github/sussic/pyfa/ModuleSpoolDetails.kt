package io.github.sussic.pyfa

import org.json.JSONObject

data class ModuleSpoolRow(val index: Int, val objectKey: String, val itemId: Int, val name: String,
    val overrideCycles: Int?, val currentCycles: Int, val defaultCycles: Int, val minimumCycles: Int,
    val maximumCycles: Int, val currentSeconds: Double, val defaultSeconds: Double,
    val minimumSeconds: Double, val maximumSeconds: Double, val choices: List<Int>)
data class ModuleSpoolDetails(val fitId: String, val revision: Long, val modules: List<ModuleSpoolRow>)

internal object ModuleSpoolCodec {
    private fun count(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "invalid spool integer")
    }.toInt()
    private fun seconds(raw: Any): Double {
        val value = when (raw) { is Int -> raw.toDouble(); is Long -> raw.toDouble(); is Double -> raw
            else -> OfflineFeatureCodec.reject("spool seconds number required") }
        OfflineFeatureCodec.expect(value.isFinite() && value >= 0, "invalid spool seconds")
        return value
    }
    fun decode(json: String): ModuleSpoolDetails = with(OfflineFeatureCodec) {
        val root = parse(json); keys(root, "version", "fit_id", "revision", "modules")
        expect(integer(root.get("version")) == 1L, "unsupported spool details version")
        val revision = integer(root.get("revision")); expect(revision >= 1, "invalid spool revision")
        val modules = rows(root.get("modules")).map { raw ->
            val row = obj(raw)
            keys(row, "index", "object_key", "item_id", "name", "override_cycles", "current_cycles", "default_cycles",
                "minimum_cycles", "maximum_cycles", "current_seconds", "default_seconds", "minimum_seconds", "maximum_seconds", "choices")
            val itemId = count(row.get("item_id")); expect(itemId > 0, "invalid spool item ID")
            val name = text(row.get("name")); expect(name.isNotBlank(), "empty spool module name")
            val current = count(row.get("current_cycles"))
            val minimum = count(row.get("minimum_cycles")); val maximum = count(row.get("maximum_cycles"))
            expect(minimum < maximum && maximum <= 100000, "unavailable or unbounded spool limits")
            val choices = rows(row.get("choices")).map(::count)
            expect(choices.zipWithNext().all { (a, b) -> a < b } && current in choices, "invalid spool choices")
            val override = if (row.get("override_cycles") === JSONObject.NULL) null else count(row.get("override_cycles"))
            expect(override != null || count(row.get("default_cycles")) in choices, "missing default spool choice")
            // Preserve raw override and effective values; EOS may clamp an override after a skill/variation change.
            ModuleSpoolRow(count(row.get("index")), identity(row.get("object_key")), itemId, name,
                override, current, count(row.get("default_cycles")), minimum, maximum, seconds(row.get("current_seconds")),
                seconds(row.get("default_seconds")), seconds(row.get("minimum_seconds")), seconds(row.get("maximum_seconds")), frozen(choices))
        }
        expect(modules.zipWithNext().all { (a, b) -> a.index < b.index }, "unordered spool modules")
        expect(modules.map { it.objectKey }.distinct().size == modules.size, "duplicate spool identity")
        ModuleSpoolDetails(identity(root.get("fit_id")), revision, frozen(modules))
    }
}
