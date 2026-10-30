package io.github.sussic.pyfa

import org.json.JSONObject

data class MutationRollInput(val attributeId: Int, val value: Double)
data class MutationAttribute(val attributeId: Int, val value: Double, val label: String,
    val unitId: Int?, val minimum: Double, val maximum: Double, val highIsGood: Boolean)
data class MutationItem(val kind: String, val position: Int, val objectKey: String,
    val name: String, val baseItemId: Int, val mutaplasmidId: Int, val attributes: List<MutationAttribute>)
data class MutationDetails(val fitId: String, val revision: Long, val items: List<MutationItem>)

internal object MutationCodec {
    private fun count(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "Invalid mutation integer")
    }.toInt()
    private fun number(raw: Any): Double = when (raw) {
        is Int -> raw.toDouble(); is Long -> raw.toDouble(); is Double -> raw
        else -> OfflineFeatureCodec.reject("Mutation number required")
    }.also { OfflineFeatureCodec.expect(it.isFinite(), "Nonfinite mutation value") }

    fun decode(json: String): MutationDetails = with(OfflineFeatureCodec) {
        val root = parse(json); keys(root, "version", "fit_id", "revision", "items")
        expect(integer(root.get("version")) == 1L, "Unsupported mutation details version")
        val revision = integer(root.get("revision")); expect(revision >= 1, "Invalid mutation revision")
        val items = rows(root.get("items")).map { raw ->
            val row = obj(raw)
            keys(row, "kind", "position", "object_key", "name", "base_item_id", "mutaplasmid_id", "attributes")
            val kind = text(row.get("kind")); expect(kind in setOf("module", "drone"), "Invalid mutation kind")
            val base = count(row.get("base_item_id")); val mutaplasmid = count(row.get("mutaplasmid_id"))
            expect(base > 0 && mutaplasmid > 0, "Invalid mutation type identity")
            val attributes = rows(row.get("attributes")).map { entry ->
                val a = obj(entry)
                keys(a, "attribute_id", "value", "label", "unit_id", "minimum", "maximum", "high_is_good")
                val id = count(a.get("attribute_id")); expect(id > 0, "Invalid rolled attribute")
                val value = number(a.get("value")); val low = number(a.get("minimum")); val high = number(a.get("maximum"))
                expect(low <= value && value <= high, "Rolled value outside source range")
                val label = text(a.get("label")); expect(label.isNotBlank(), "Empty mutation label")
                val direction = a.get("high_is_good")
                expect(direction is Boolean, "Invalid mutation direction")
                MutationAttribute(id, value, label, if (a.get("unit_id") === JSONObject.NULL) null else count(a.get("unit_id")),
                    low, high, direction as Boolean)
            }
            expect(attributes.isNotEmpty() && attributes.zipWithNext().all { (a, b) -> a.attributeId < b.attributeId },
                "Incomplete, duplicate or unordered roll set")
            val name = text(row.get("name")); expect(name.isNotBlank(), "Empty mutation name")
            MutationItem(kind, count(row.get("position")), identity(row.get("object_key")), name, base, mutaplasmid, frozen(attributes))
        }
        expect(items.map { it.kind to it.position }.distinct().size == items.size, "Duplicate mutation position")
        expect(items.map { it.objectKey }.distinct().size == items.size, "Duplicate mutation identity")
        MutationDetails(identity(root.get("fit_id")), revision, frozen(items))
    }
}
