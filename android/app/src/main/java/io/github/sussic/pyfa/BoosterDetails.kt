package io.github.sussic.pyfa

import org.json.JSONObject

data class BoosterSideEffect(val effectId: Int, val name: String, val active: Boolean)
data class BoosterVariation(val id: Int, val name: String, val enabled: Boolean)
data class BoosterRow(val index: Int, val objectKey: String, val itemId: Int, val name: String,
    val slot: Int, val active: Boolean, val durationMs: Double?, val durationText: String?,
    val sideEffects: List<BoosterSideEffect>, val variations: List<BoosterVariation>)
data class BoosterDetails(val fitId: String, val revision: Long, val isStructure: Boolean, val boosters: List<BoosterRow>)
data class BoosterOccupant(val index: Int, val objectKey: String, val itemId: Int, val name: String)
data class BoosterAddOptions(val fitId: String, val revision: Long, val itemId: Int, val isBooster: Boolean,
    val isStructure: Boolean, val slot: Int?, val occupant: BoosterOccupant?, val alreadyFitted: Boolean)

internal object BoosterDetailsCodec {
    private fun count(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "invalid booster integer")
    }.toInt()
    private fun id(raw: Any): Int = count(raw).also { OfflineFeatureCodec.expect(it > 0, "invalid booster ID or slot") }
    private fun name(raw: Any): String = OfflineFeatureCodec.text(raw).also {
        OfflineFeatureCodec.expect(it.isNotBlank(), "empty booster label")
    }
    private fun revision(raw: Any) = OfflineFeatureCodec.integer(raw).also { OfflineFeatureCodec.expect(it >= 1, "invalid booster revision") }
    private fun duration(raw: Any): Double? {
        if (raw === JSONObject.NULL) return null
        val value = when (raw) { is Int -> raw.toDouble(); is Long -> raw.toDouble(); is Double -> raw
            else -> OfflineFeatureCodec.reject("booster duration number required") }
        OfflineFeatureCodec.expect(value.isFinite() && value >= 0, "invalid booster duration")
        return value
    }
    fun details(json: String): BoosterDetails = with(OfflineFeatureCodec) {
        val root = parse(json); keys(root, "version", "fit_id", "revision", "is_structure", "boosters")
        expect(integer(root.get("version")) == 1L, "unsupported booster details version")
        val boosters = rows(root.get("boosters")).mapIndexed { index, raw ->
            val row = obj(raw)
            keys(row, "index", "object_key", "item_id", "name", "slot", "active", "duration_ms", "duration_text", "side_effects", "variations")
            expect(count(row.get("index")) == index, "unordered boosters")
            val duration = duration(row.get("duration_ms"))
            val display = nullableText(row.get("duration_text"))
            expect((duration == null) == (display == null), "booster duration availability differs")
            expect(display == null || display.endsWith(" min") && display.length > 4, "invalid booster duration unit")
            val effects = rows(row.get("side_effects")).map { value ->
                val effect = obj(value); keys(effect, "effect_id", "name", "active")
                BoosterSideEffect(id(effect.get("effect_id")), name(effect.get("name")), bool(effect.get("active")))
            }
            expect(effects.map { it.effectId }.distinct().size == effects.size, "duplicate booster side effect")
            val variations = rows(row.get("variations")).map { value ->
                val choice = obj(value); keys(choice, "id", "name", "enabled")
                BoosterVariation(id(choice.get("id")), name(choice.get("name")), bool(choice.get("enabled")))
            }
            expect(variations.map { it.id }.distinct().size == variations.size, "duplicate booster variation")
            BoosterRow(index, identity(row.get("object_key")), id(row.get("item_id")), name(row.get("name")), id(row.get("slot")),
                bool(row.get("active")), duration, display, frozen(effects), frozen(variations))
        }
        expect(boosters.map { it.objectKey }.distinct().size == boosters.size, "duplicate booster identity")
        expect(boosters.map { it.slot }.distinct().size == boosters.size, "duplicate booster slot")
        expect(boosters.map { it.itemId }.distinct().size == boosters.size, "duplicate fitted booster")
        BoosterDetails(identity(root.get("fit_id")), revision(root.get("revision")), bool(root.get("is_structure")), frozen(boosters))
    }
    fun addOptions(json: String): BoosterAddOptions = with(OfflineFeatureCodec) {
        val root = parse(json)
        keys(root, "version", "fit_id", "revision", "item_id", "is_booster", "is_structure", "slot", "occupant", "already_fitted")
        expect(integer(root.get("version")) == 1L, "unsupported booster add version")
        val itemId = id(root.get("item_id"))
        val isBooster = bool(root.get("is_booster"))
        val slot = if (root.isNull("slot")) null else id(root.get("slot"))
        val occupant = if (root.isNull("occupant")) null else obj(root.get("occupant")).let { row ->
            keys(row, "index", "object_key", "item_id", "name")
            BoosterOccupant(count(row.get("index")), identity(row.get("object_key")), id(row.get("item_id")), name(row.get("name")))
        }
        val already = bool(root.get("already_fitted"))
        expect(isBooster == (slot != null), "booster slot applicability differs")
        expect(isBooster || occupant == null && !already, "nonbooster has fitting state")
        expect(already == (occupant?.itemId == itemId), "already-fitted booster identity differs")
        BoosterAddOptions(identity(root.get("fit_id")), revision(root.get("revision")), itemId, isBooster,
            bool(root.get("is_structure")), slot, occupant, already)
    }
}
