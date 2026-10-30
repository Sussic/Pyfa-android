package io.github.sussic.pyfa

import org.json.JSONObject

enum class MutationValueRepresentation(val wire: String) { RAW("raw"), DISPLAY("display") }

data class MutationDisplayEdit(val attributeId: Int, val value: Double,
    val representation: MutationValueRepresentation)

/** Converted values originate in EOS; Android never reconstructs a unit formula. */
sealed interface MutationDisplayValue {
    data class Available(val value: Double, val minimum: Double, val maximum: Double,
        val sliderBase: Double, val unitLabel: String, val higherIsBetter: Boolean) : MutationDisplayValue
    data class Unavailable(val reason: String) : MutationDisplayValue
}

data class MutationDisplayAttribute(val raw: MutationAttribute, val display: MutationDisplayValue) {
    val initialRepresentation get() = if (display is MutationDisplayValue.Available)
        MutationValueRepresentation.DISPLAY else MutationValueRepresentation.RAW

    fun sourceValue(representation: MutationValueRepresentation): Double = when (representation) {
        MutationValueRepresentation.RAW -> raw.value
        MutationValueRepresentation.DISPLAY -> (display as? MutationDisplayValue.Available)?.value
            ?: throw IllegalArgumentException("Converted mutation entry is unavailable")
    }
}

data class MutationDisplayItem(val raw: MutationItem, val attributes: List<MutationDisplayAttribute>)
data class MutationDisplayDetails(val fitId: String, val revision: Long, val items: List<MutationDisplayItem>)

internal object MutationDisplayCodec {
    private fun count(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "Invalid converted mutation integer")
    }.toInt()

    private fun number(raw: Any): Double = when (raw) {
        is Int -> raw.toDouble(); is Long -> raw.toDouble(); is Double -> raw
        else -> OfflineFeatureCodec.reject("Converted mutation number required")
    }.also { OfflineFeatureCodec.expect(it.isFinite(), "Nonfinite converted mutation number") }

    private fun display(raw: Any): MutationDisplayValue = with(OfflineFeatureCodec) {
        val row = obj(raw)
        keys(row, "available", "value", "minimum", "maximum", "slider_base", "unit_label", "higher_is_better", "reason")
        if (bool(row.get("available"))) {
            val value = number(row.get("value"))
            val low = number(row.get("minimum")); val high = number(row.get("maximum"))
            val anchor = number(row.get("slider_base"))
            expect(low <= high && value in low..high && anchor in low..high,
                "Converted mutation value or anchor outside source range")
            expect(row.get("reason") === JSONObject.NULL, "Available converted value has an unavailable reason")
            MutationDisplayValue.Available(value, low, high, anchor, text(row.get("unit_label")),
                bool(row.get("higher_is_better")))
        } else {
            expect(listOf("value", "minimum", "maximum", "slider_base", "unit_label", "higher_is_better")
                .all { row.get(it) === JSONObject.NULL }, "Unavailable converted value contains usable metadata")
            val reason = text(row.get("reason"))
            expect(reason.isNotBlank(), "Unavailable converted value needs a reason")
            MutationDisplayValue.Unavailable(reason)
        }
    }

    fun decode(json: String): MutationDisplayDetails = with(OfflineFeatureCodec) {
        val root = parse(json)
        keys(root, "version", "fit_id", "revision", "items")
        expect(integer(root.get("version")) == 1L, "Unsupported converted mutation details version")
        val fitId = hexId(root.get("fit_id"))
        val revision = positive(root.get("revision"))
        // Read inherited raw scalars directly. Re-encoding an intermediate JSONObject
        // could normalize signed zero; no untouched raw value takes that round trip.
        val items = rows(root.get("items")).map { rawItem ->
            val row = obj(rawItem)
            keys(row, "kind", "position", "object_key", "name", "base_item_id", "mutaplasmid_id", "attributes")
            val kind = text(row.get("kind"))
            expect(kind in setOf("module", "drone"), "Invalid converted mutation kind")
            val base = count(row.get("base_item_id")); val mutaplasmid = count(row.get("mutaplasmid_id"))
            expect(base > 0 && mutaplasmid > 0, "Invalid converted mutation type identity")
            val attributes = rows(row.get("attributes")).map { entry ->
                val attribute = obj(entry)
                keys(attribute, "attribute_id", "value", "label", "unit_id", "minimum", "maximum", "high_is_good", "display")
                val id = count(attribute.get("attribute_id")); expect(id > 0, "Invalid converted rolled attribute")
                val value = number(attribute.get("value"))
                val low = number(attribute.get("minimum")); val high = number(attribute.get("maximum"))
                expect(low <= value && value <= high, "Raw rolled value outside source range")
                val label = text(attribute.get("label")); expect(label.isNotBlank(), "Empty mutation label")
                val unit = if (attribute.get("unit_id") === JSONObject.NULL) null else count(attribute.get("unit_id"))
                MutationDisplayAttribute(MutationAttribute(id, value, label, unit, low, high,
                    bool(attribute.get("high_is_good"))), display(attribute.get("display")))
            }
            expect(attributes.isNotEmpty() && attributes.zipWithNext().all { (a, b) -> a.raw.attributeId < b.raw.attributeId },
                "Incomplete, duplicate or unordered converted roll set")
            val name = text(row.get("name")); expect(name.isNotBlank(), "Empty mutation name")
            val raw = MutationItem(kind, count(row.get("position")), hexId(row.get("object_key")), name, base,
                mutaplasmid, frozen(attributes.map { it.raw }))
            MutationDisplayItem(raw, frozen(attributes))
        }
        expect(items.map { it.raw.kind to it.raw.position }.distinct().size == items.size, "Duplicate converted mutation position")
        expect(items.map { it.raw.objectKey }.distinct().size == items.size, "Duplicate converted mutation identity")
        MutationDisplayDetails(fitId, revision, frozen(items))
    }
}
