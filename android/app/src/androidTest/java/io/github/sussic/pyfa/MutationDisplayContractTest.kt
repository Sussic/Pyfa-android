package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred protocol checks; these synthetic values are not EOS parity witnesses. */
@RunWith(AndroidJUnit4::class)
class MutationDisplayContractTest {
    private val fitId = "1".repeat(32)
    private val objectKey = "2".repeat(32)
    private fun display() = JSONObject().put("available", true).put("value", 25)
        .put("minimum", 0).put("maximum", 50).put("slider_base", 20)
        .put("unit_label", "%").put("higher_is_better", false).put("reason", JSONObject.NULL)
    private fun attribute(id: Int = 10) = JSONObject().put("attribute_id", id).put("value", .75)
        .put("label", "Synthetic roll").put("unit_id", 108).put("minimum", .5).put("maximum", 1)
        .put("high_is_good", true).put("display", display())
    private fun item() = JSONObject().put("kind", "module").put("position", 0).put("object_key", objectKey)
        .put("name", "Synthetic mutated module").put("base_item_id", 100).put("mutaplasmid_id", 200)
        .put("attributes", JSONArray().put(attribute()))
    private fun details() = JSONObject().put("version", 1).put("fit_id", fitId).put("revision", 7)
        .put("items", JSONArray().put(item()))
    private fun firstAttribute(root: JSONObject) = root.getJSONArray("items").getJSONObject(0)
        .getJSONArray("attributes").getJSONObject(0)
    private fun firstDisplay(root: JSONObject) = firstAttribute(root).getJSONObject("display")
    private fun unavailable() = JSONObject().put("available", false).put("reason", "Unsupported numeric inverse")
        .also { row -> listOf("value", "minimum", "maximum", "slider_base", "unit_label", "higher_is_better")
            .forEach { row.put(it, JSONObject.NULL) } }
    private fun decode(root: JSONObject) = MutationDisplayCodec.decode(root.toString())
    private fun operation(edits: List<MutationDisplayEdit>) =
        BridgeOperation.SetMutationDisplayAttributes(fitId, "module", 0, objectKey, edits)
    private fun wire(operation: BridgeOperation) = JSONObject(BridgeCodec.encodeRequest(
        BridgeRequest("request", "session", operation, mapOf(fitId to 7L))))
    private fun reject(block: () -> Unit) {
        try { block(); fail("Accepted invalid mutation display contract") } catch (_: BridgeProtocolException) { }
    }

    @Test fun convertedMetadataRetainsRawValuesAndUsesReturnedDirection() {
        val result = decode(details())
        assertEquals(fitId, result.fitId); assertEquals(7L, result.revision)
        val attribute = result.items.single().attributes.single()
        assertEquals(.75, attribute.raw.value, 0.0); assertEquals(.5, attribute.raw.minimum, 0.0)
        assertEquals(1.0, attribute.raw.maximum, 0.0); assertTrue(attribute.raw.highIsGood)
        val display = attribute.display as MutationDisplayValue.Available
        assertEquals(25.0, display.value, 0.0); assertEquals(20.0, display.sliderBase, 0.0)
        assertEquals("%", display.unitLabel); assertFalse(display.higherIsBetter)
        assertEquals(MutationValueRepresentation.DISPLAY, attribute.initialRepresentation)
        try { (result.items as MutableList<MutationDisplayItem>).clear(); fail("Mutable converted details") }
        catch (_: UnsupportedOperationException) { }
        try { (result.items.single().attributes as MutableList<MutationDisplayAttribute>).clear(); fail("Mutable attributes") }
        catch (_: UnsupportedOperationException) { }
    }

    @Test fun unitlessAndUnavailableMetadataRetainExplicitRawEntry() {
        val unitless = details(); firstDisplay(unitless).put("unit_label", "")
        assertEquals("", (decode(unitless).items.single().attributes.single().display as MutationDisplayValue.Available).unitLabel)
        val unsupported = details(); firstAttribute(unsupported).put("display", unavailable())
        val attribute = decode(unsupported).items.single().attributes.single()
        assertEquals("Unsupported numeric inverse", (attribute.display as MutationDisplayValue.Unavailable).reason)
        assertEquals(MutationValueRepresentation.RAW, attribute.initialRepresentation)
        assertEquals(.75, attribute.sourceValue(MutationValueRepresentation.RAW), 0.0)
        try { attribute.sourceValue(MutationValueRepresentation.DISPLAY); fail("Invented unavailable value") }
        catch (_: IllegalArgumentException) { }
    }

    @Test fun rawSignedZeroSurvivesTheConvertedQueryCodec() {
        val root = details(); firstAttribute(root).put("minimum", -1).put("value", 0.75)
        val json = root.toString().replace("\"value\":0.75", "\"value\":-0.0")
        assertTrue(json.contains("\"value\":-0.0"))
        val raw = MutationDisplayCodec.decode(json).items.single().attributes.single().raw.value
        assertEquals((-0.0).toRawBits(), raw.toRawBits())
    }

    @Test fun reversedRangesOutsideValuesAndOutsideAnchorsAreRejected() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("minimum", 60) }, { it.put("value", -1) }, { it.put("value", 51) },
            { it.put("slider_base", -1) }, { it.put("slider_base", 51) },
            { it.put("higher_is_better", 1) }, { it.put("unit_label", JSONObject.NULL) },
            { it.put("reason", "Cannot both be available and refused") })
        mutations.forEach { change -> val root = details(); change(firstDisplay(root)); reject { decode(root) } }
    }

    @Test fun unavailableMetadataRequiresEveryNullAndANonblankReason() {
        listOf("value", "minimum", "maximum", "slider_base", "unit_label", "higher_is_better").forEach { key ->
            val root = details(); firstAttribute(root).put("display", unavailable().put(key, 1))
            reject { decode(root) }
        }
        for (reason in listOf<Any>("", "  ", JSONObject.NULL, false)) {
            val root = details(); firstAttribute(root).put("display", unavailable().put("reason", reason))
            reject { decode(root) }
        }
    }

    @Test fun malformedEnvelopeIdentityRollOrderAndUnknownFieldsAreRejected() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", 2) }, { it.put("revision", 0) }, { it.put("revision", -1) },
            { it.put("revision", 7.5) }, { it.put("revision", true) }, { it.put("fit_id", "fit") },
            { it.put("extra", false) }, { firstDisplay(it).put("extra", false) },
            { firstAttribute(it).put("extra", false) },
            { it.getJSONArray("items").getJSONObject(0).put("object_key", "unknown") },
            { it.getJSONArray("items").getJSONObject(0).put("kind", "cargo") },
            { it.getJSONArray("items").getJSONObject(0).getJSONArray("attributes").put(attribute()) },
            { it.getJSONArray("items").getJSONObject(0).getJSONArray("attributes").put(attribute(9)) },
            { it.getJSONArray("items").put(item()) })
        mutations.forEach { change -> val root = details(); change(root); reject { decode(root) } }
        reject { MutationDisplayCodec.decode(details().toString().replaceFirst("{", "{\"version\":1,")) }
    }

    @Test fun nonfiniteOrNonnumericWireValuesCannotReachAnEditor() {
        val number = Regex("(\"slider_base\":)[^,}]+")
        for (token in listOf("1e309", "-1e309", "NaN", "Infinity", "\"20\"", "true")) {
            val json = number.replace(details().toString()) { it.groupValues[1] + token }
            reject { MutationDisplayCodec.decode(json) }
        }
    }

    @Test fun sparseEditsEncodeOnlyTheirRepresentationsAndCaptureCallerCollections() {
        val edits = mutableListOf(MutationDisplayEdit(10, .6, MutationValueRepresentation.RAW),
            MutationDisplayEdit(30, 15.0, MutationValueRepresentation.DISPLAY))
        val captured = operation(edits).snapshotArguments() as BridgeOperation.SetMutationDisplayAttributes
        edits.clear()
        val request = wire(captured)
        assertEquals("set_mutation_display_attributes", request.getString("operation"))
        assertEquals(7, request.getJSONObject("expected_revisions").getInt(fitId))
        val arguments = request.getJSONObject("arguments")
        assertEquals(setOf("fit_id", "kind", "position", "object_key", "edits"), arguments.keys().asSequence().toSet())
        val encoded = arguments.getJSONArray("edits")
        assertEquals(2, encoded.length()); assertEquals(10, encoded.getJSONObject(0).getInt("attribute_id"))
        assertEquals(30, encoded.getJSONObject(1).getInt("attribute_id"))
        assertEquals("raw", encoded.getJSONObject(0).getString("representation"))
        assertEquals("display", encoded.getJSONObject(1).getString("representation"))
        assertEquals(setOf("attribute_id", "value", "representation"), encoded.getJSONObject(0).keys().asSequence().toSet())
        try { (captured.edits as MutableList<MutationDisplayEdit>).clear(); fail("Mutable captured mutation edits") }
        catch (_: UnsupportedOperationException) { }
    }

    @Test fun emptyDuplicateUnorderedNonfiniteAndInvalidIdentityEditsAreRejected() {
        val raw = MutationDisplayEdit(10, .6, MutationValueRepresentation.RAW)
        listOf(emptyList(), listOf(raw, raw), listOf(raw, raw.copy(attributeId = 9)),
            listOf(raw.copy(attributeId = 0)), listOf(raw.copy(value = Double.NaN)),
            listOf(raw.copy(value = Double.POSITIVE_INFINITY))).forEach { reject { wire(operation(it)) } }
        reject { wire(operation(listOf(raw)).copy(kind = "cargo")) }
        reject { wire(operation(listOf(raw)).copy(position = -1)) }
        reject { wire(operation(listOf(raw)).copy(objectKey = "unknown")) }
        reject { BridgeCodec.encodeRequest(BridgeRequest("r", "s", operation(listOf(raw)))) }
    }

    @Test fun existingRawDetailsAndCompleteRawOperationRemainAvailable() {
        val root = details(); firstAttribute(root).remove("display")
        val decoded = MutationCodec.decode(root.toString())
        assertEquals(.75, decoded.items.single().attributes.single().value, 0.0)
        val request = wire(BridgeOperation.SetMutationAttributes(fitId, "module", 0, objectKey,
            listOf(MutationRollInput(10, .6))))
        assertEquals("set_mutation_attributes", request.getString("operation"))
        val arguments = request.getJSONObject("arguments")
        assertTrue(arguments.has("attributes")); assertFalse(arguments.has("edits"))
    }
}
