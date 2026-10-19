package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class BoosterContractTest {
    private fun wire(operation: BridgeOperation) = JSONObject(BridgeCodec.encodeRequest(
        BridgeRequest("request", "session", operation, mapOf("fit" to 7L))))
    private fun row(index: Int = 0, slot: Int = 1) = JSONObject().put("index", index).put("object_key", "booster-$index")
        .put("item_id", 100 + index).put("name", "Standard booster $index").put("slot", slot).put("active", true)
        .put("duration_ms", 1800000).put("duration_text", "30 min")
        .put("side_effects", JSONArray().put(JSONObject().put("effect_id", 7).put("name", "-20% Shield").put("active", false))
            .put(JSONObject().put("effect_id", 3).put("name", "-10% Armor").put("active", true)))
        .put("variations", JSONArray().put(JSONObject().put("id", 102).put("name", "Improved booster").put("enabled", true)))
    private fun details() = JSONObject().put("version", 1).put("fit_id", "fit").put("revision", 7)
        .put("is_structure", false).put("boosters", JSONArray().put(row()))
    private fun options() = JSONObject().put("version", 1).put("fit_id", "fit").put("revision", 7).put("item_id", 102)
        .put("is_booster", true).put("is_structure", false).put("slot", 1).put("already_fitted", false)
        .put("occupant", JSONObject().put("index", 0).put("object_key", "booster-0").put("item_id", 100).put("name", "Standard booster"))
    private fun reject(block: () -> Unit) { try { block(); fail("Accepted invalid booster contract") } catch (_: BridgeProtocolException) { } }
    @Test fun atomicOperationsHaveExactFieldsAndKeepExistingSingleRowOperations() {
        val operations = listOf(
            Triple(BridgeOperation.FitBooster("fit", 102), "fit_booster", setOf("fit_id", "item_id")),
            Triple(BridgeOperation.ToggleBoosters("fit", 0, listOf(1)), "toggle_boosters", setOf("fit_id", "main_position", "positions")),
            Triple(BridgeOperation.RemoveBoosters("fit", listOf(1, 0)), "remove_boosters", setOf("fit_id", "positions")),
            Triple(BridgeOperation.ChangeBoosterVariation("fit", 0, 102), "change_booster_variation", setOf("fit_id", "position", "item_id")),
            Triple(BridgeOperation.AddBooster("fit", 100, false), "add_booster", setOf("fit_id", "item_id", "active")),
            Triple(BridgeOperation.SetBoosterSideEffect("fit", 0, 7, true), "set_booster_side_effect", setOf("fit_id", "position", "effect_id", "active")))
        operations.forEach { (operation, name, fields) ->
            val value = wire(operation)
            assertEquals(name, value.getString("operation")); assertEquals(fields, value.getJSONObject("arguments").keys().asSequence().toSet())
            assertEquals(7, value.getJSONObject("expected_revisions").getInt("fit"))
        }
    }
    @Test fun selectionCaptureAndInvalidArgumentsCannotBecomePartialEdits() {
        val positions = mutableListOf(0, 1)
        val captured = BridgeOperation.ToggleBoosters("fit", 0, positions).snapshotArguments() as BridgeOperation.ToggleBoosters
        positions.clear(); assertEquals(listOf(0, 1), captured.positions)
        try { (captured.positions as MutableList<Int>).clear(); fail("Mutable booster operation") } catch (_: UnsupportedOperationException) { }
        listOf(BridgeOperation.FitBooster("fit", 0), BridgeOperation.ToggleBoosters("fit", -1, emptyList()),
            BridgeOperation.ToggleBoosters("fit", 0, listOf(1, 1)), BridgeOperation.RemoveBoosters("fit", emptyList()),
            BridgeOperation.RemoveBoosters("fit", listOf(-1)), BridgeOperation.RemoveBoosters("fit", (0..1024).toList()),
            BridgeOperation.ChangeBoosterVariation("fit", -1, 102)).forEach { reject { wire(it) } }
        reject { BridgeCodec.encodeRequest(BridgeRequest("r", "s", BridgeOperation.FitBooster("fit", 102))) }
    }
    @Test fun sourceOrderDurationAvailabilityAndPositiveHigherSlotsArePreserved() {
        val value = details()
        value.getJSONArray("boosters").put(row(1, 11).put("duration_ms", JSONObject.NULL).put("duration_text", JSONObject.NULL))
        val result = BoosterDetailsCodec.details(value.toString())
        assertEquals(listOf(7, 3), result.boosters.first().sideEffects.map { it.effectId })
        assertEquals(1800000.0, result.boosters.first().durationMs!!, 0.0); assertEquals("30 min", result.boosters.first().durationText)
        assertEquals(11, result.boosters.last().slot); assertNull(result.boosters.last().durationMs); assertNull(result.boosters.last().durationText)
        try { (result.boosters as MutableList<BoosterRow>).clear(); fail("Mutable booster details") } catch (_: UnsupportedOperationException) { }
    }
    @Test fun optionsDistinguishNonboostersFreeSlotsOccupiedSlotsDuplicatesAndStructures() {
        val occupied = BoosterDetailsCodec.addOptions(options().toString())
        assertEquals(100, occupied.occupant!!.itemId); assertFalse(occupied.alreadyFitted)
        val free = BoosterDetailsCodec.addOptions(options().put("occupant", JSONObject.NULL).toString())
        assertTrue(free.isBooster); assertNull(free.occupant)
        val duplicate = BoosterDetailsCodec.addOptions(options().put("item_id", 100).put("already_fitted", true).toString())
        assertTrue(duplicate.alreadyFitted)
        val structure = BoosterDetailsCodec.addOptions(options().put("is_structure", true).toString())
        assertTrue(structure.isStructure); assertTrue(structure.isBooster)
        val other = BoosterDetailsCodec.addOptions(options().put("is_booster", false).put("slot", JSONObject.NULL).put("occupant", JSONObject.NULL).toString())
        assertFalse(other.isBooster); assertNull(other.slot); assertNull(other.occupant)
    }
    @Test fun malformedQueryIdentityCountsUnitsAndApplicabilityAreRejected() {
        val detailMutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", true) }, { it.put("revision", 0) }, { it.put("is_structure", 0) }, { it.put("extra", false) },
            { it.getJSONArray("boosters").getJSONObject(0).put("slot", 0) },
            { it.getJSONArray("boosters").getJSONObject(0).put("index", 1) },
            { it.getJSONArray("boosters").getJSONObject(0).put("active", 1) },
            { it.getJSONArray("boosters").getJSONObject(0).put("duration_ms", -1) },
            { it.getJSONArray("boosters").getJSONObject(0).put("duration_text", "30 s") },
            { it.getJSONArray("boosters").getJSONObject(0).put("duration_ms", JSONObject.NULL) },
            { it.getJSONArray("boosters").put(row(1, 1)) },
            { it.getJSONArray("boosters").getJSONObject(0).getJSONArray("side_effects").getJSONObject(1).put("effect_id", 7) })
        detailMutations.forEach { mutate -> val value = details(); mutate(value); reject { BoosterDetailsCodec.details(value.toString()) } }
        val optionMutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("is_booster", false) }, { it.put("slot", JSONObject.NULL) }, { it.put("already_fitted", true) },
            { it.put("slot", -1) }, { it.put("revision", 7.5) }, { it.getJSONObject("occupant").put("object_key", "") })
        optionMutations.forEach { mutate -> val value = options(); mutate(value); reject { BoosterDetailsCodec.addOptions(value.toString()) } }
        reject { BoosterDetailsCodec.details(details().toString().replaceFirst("{", "{\"version\":1,")) }
        reject { BoosterDetailsCodec.details(details().toString().replace("\"duration_ms\":1800000", "\"duration_ms\":1e309")) }
    }
}
