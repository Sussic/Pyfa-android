package io.github.sussic.pyfa

import org.json.JSONObject

/** EOS owns squadron limits and ability defaults. These values are presentation only. */
data class FighterAbilityState(val effectId: Int, val active: Boolean)
data class FighterAbility(val effectId: Int, val name: String, val active: Boolean)
data class FighterVariation(val id: Int, val name: String, val enabled: Boolean)
data class FighterCategory(val slot: String, val name: String, val used: Int, val total: Double?)
data class FighterSquadron(val index: Int, val objectKey: String, val itemId: Int, val name: String,
    val group: String, val slot: String, val amount: Int, val maxSize: Int, val active: Boolean,
    val abilities: List<FighterAbility>, val variations: List<FighterVariation>)
data class FighterDetails(val fitId: String, val revision: Long, val bayUsed: Double, val bayCapacity: Double?,
    val tubesUsed: Int, val tubesTotal: Double?, val categories: List<FighterCategory>, val squadrons: List<FighterSquadron>)

internal object FighterDetailsCodec {
    val slots = setOf("F_LIGHT", "F_SUPPORT", "F_HEAVY", "FS_LIGHT", "FS_SUPPORT", "FS_HEAVY")
    private fun count(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "invalid fighter count")
    }.toInt()
    private fun id(raw: Any): Int = count(raw).also { OfflineFeatureCodec.expect(it > 0, "invalid fighter ID") }
    private fun name(raw: Any): String = OfflineFeatureCodec.text(raw).also {
        OfflineFeatureCodec.expect(it.isNotBlank(), "empty fighter label")
    }
    private fun number(raw: Any): Double {
        val value = when (raw) { is Int -> raw.toDouble(); is Long -> raw.toDouble(); is Double -> raw
            else -> OfflineFeatureCodec.reject("fighter number required") }
        OfflineFeatureCodec.expect(value.isFinite() && value >= 0, "invalid fighter capacity")
        return value
    }
    private fun nullableNumber(raw: Any): Double? = if (raw === JSONObject.NULL) null else number(raw)
    fun decode(json: String): FighterDetails = with(OfflineFeatureCodec) {
        val root = parse(json)
        keys(root, "version", "fit_id", "revision", "bay_used", "bay_capacity", "tubes_used", "tubes_total", "categories", "squadrons")
        expect(integer(root.get("version")) == 1L, "unsupported fighter details version")
        val revision = integer(root.get("revision")); expect(revision >= 1, "invalid fighter revision")
        val categories = rows(root.get("categories")).map { raw ->
            val row = obj(raw); keys(row, "slot", "name", "used", "total")
            FighterCategory(text(row.get("slot")), name(row.get("name")), count(row.get("used")), nullableNumber(row.get("total")))
        }
        expect(categories.size == slots.size && categories.map { it.slot }.toSet() == slots, "missing or duplicate fighter categories")
        val squadrons = rows(root.get("squadrons")).mapIndexed { index, raw ->
            val row = obj(raw)
            keys(row, "index", "object_key", "item_id", "name", "group", "slot", "amount", "max_size", "active", "abilities", "variations")
            expect(count(row.get("index")) == index, "unordered fighter squadrons")
            val slot = text(row.get("slot")); expect(slot in slots, "invalid fighter slot")
            val abilities = rows(row.get("abilities")).map { value ->
                val ability = obj(value); keys(ability, "effect_id", "name", "active")
                FighterAbility(id(ability.get("effect_id")), name(ability.get("name")), bool(ability.get("active")))
            }
            expect(abilities.map { it.effectId }.distinct().size == abilities.size, "duplicate fighter ability")
            val variations = rows(row.get("variations")).map { value ->
                val variation = obj(value); keys(variation, "id", "name", "enabled")
                FighterVariation(id(variation.get("id")), name(variation.get("name")), bool(variation.get("enabled")))
            }
            expect(variations.map { it.id }.distinct().size == variations.size, "duplicate fighter variation")
            FighterSquadron(index, identity(row.get("object_key")), id(row.get("item_id")), name(row.get("name")),
                name(row.get("group")), slot, count(row.get("amount")), count(row.get("max_size")), bool(row.get("active")),
                frozen(abilities), frozen(variations))
        }
        expect(squadrons.map { it.objectKey }.distinct().size == squadrons.size, "duplicate fighter identity")
        val tubesUsed = count(root.get("tubes_used"))
        expect(tubesUsed == squadrons.count { it.active }, "fighter tube count differs")
        categories.forEach { category ->
            expect(category.used == squadrons.count { it.slot == category.slot && it.active }, "fighter category count differs")
        }
        FighterDetails(identity(root.get("fit_id")), revision, number(root.get("bay_used")), nullableNumber(root.get("bay_capacity")),
            tubesUsed, nullableNumber(root.get("tubes_total")), frozen(categories), frozen(squadrons))
    }
}
