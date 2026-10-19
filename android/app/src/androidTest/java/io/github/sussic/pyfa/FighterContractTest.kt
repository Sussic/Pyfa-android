package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class FighterContractTest {
    private fun wire(operation: BridgeOperation) = JSONObject(BridgeCodec.encodeRequest(
        BridgeRequest("request", "session", operation, mapOf("fit" to 7L))))
    private fun spec(fighters: List<FighterSpec>) = FitSpec("Carrier", "Thanatos", 5, true,
        DamagePattern(1.0, 1.0, 1.0, 1.0), Security(SystemSecurity.NULLSEC, 0.0), emptyList(), emptyList(), fighters = fighters)
    private fun row(index: Int = 0, active: Boolean = true) = JSONObject().put("index", index).put("object_key", "fighter-$index")
        .put("item_id", 23059).put("name", "Firbolg I").put("group", "Light Fighter").put("slot", "F_LIGHT")
        .put("amount", 6).put("max_size", 6).put("active", active)
        .put("abilities", JSONArray().put(JSONObject().put("effect_id", 1).put("name", "Attack").put("active", true)))
        .put("variations", JSONArray().put(JSONObject().put("id", 40558).put("name", "Firbolg II").put("enabled", true)))
    private fun details() = JSONObject().put("version", 1).put("fit_id", "fit").put("revision", 7)
        .put("bay_used", 3000.0).put("bay_capacity", JSONObject.NULL).put("tubes_used", 1).put("tubes_total", 4)
        .put("categories", JSONArray(FighterDetailsCodec.slots.map { slot -> JSONObject().put("slot", slot).put("name", slot)
            .put("used", if (slot == "F_LIGHT") 1 else 0).put("total", if (slot == "F_LIGHT") 3 else 0) }))
        .put("squadrons", JSONArray().put(row()).put(row(1, false)))
    private fun reject(block: () -> Unit) {
        try { block(); fail("Accepted invalid fighter contract") } catch (_: BridgeProtocolException) { }
    }
    @Test fun sixOperationsUseExistingRevisionEnvelopeAndExactFields() {
        val operations = listOf(
            Triple(BridgeOperation.AddFighter("fit", 23059), "add_fighter", setOf("fit_id", "item_id")),
            Triple(BridgeOperation.SetFighterAmount("fit", 0, 0), "set_fighter_amount", setOf("fit_id", "position", "amount")),
            Triple(BridgeOperation.RemoveFighters("fit", listOf(1, 0)), "remove_fighters", setOf("fit_id", "positions")),
            Triple(BridgeOperation.ToggleFighters("fit", 0, emptyList()), "toggle_fighters", setOf("fit_id", "main_position", "positions")),
            Triple(BridgeOperation.ToggleFighterAbility("fit", 0, listOf(1), 7), "toggle_fighter_ability", setOf("fit_id", "main_position", "positions", "effect_id")),
            Triple(BridgeOperation.ChangeFighterVariations("fit", 0, listOf(1), 40558), "change_fighter_variations", setOf("fit_id", "main_position", "positions", "item_id")))
        operations.forEach { (operation, name, fields) ->
            val value = wire(operation)
            assertEquals(name, value.getString("operation"))
            assertEquals(fields, value.getJSONObject("arguments").keys().asSequence().toSet())
            assertEquals(7L, value.getJSONObject("expected_revisions").getLong("fit"))
        }
        assertEquals(0, wire(operations[1].first).getJSONObject("arguments").getInt("amount"))
    }
    @Test fun invalidIndicesDuplicateSelectionsAndNegativeSentinelAreRejected() {
        listOf(BridgeOperation.AddFighter("fit", 0), BridgeOperation.SetFighterAmount("fit", 0, -1),
            BridgeOperation.SetFighterAmount("fit", -1, 1), BridgeOperation.RemoveFighters("fit", emptyList()),
            BridgeOperation.RemoveFighters("fit", listOf(0, 0)), BridgeOperation.ToggleFighters("fit", 0, listOf(-1)),
            BridgeOperation.ToggleFighterAbility("fit", 0, listOf(1, 1), 3), BridgeOperation.ToggleFighterAbility("fit", 0, emptyList(), 0),
            BridgeOperation.ChangeFighterVariations("fit", 0, emptyList(), 0)).forEach { operation -> reject { wire(operation) } }
        reject { BridgeCodec.encodeRequest(BridgeRequest("r", "s", BridgeOperation.AddFighter("fit", 1))) }
    }
    @Test fun legacyAbsenceAndExplicitCompleteAbilityStatesStayDistinctAndCallerListsAreCaptured() {
        val legacy = FighterSpec("Firbolg I", 6, true)
        val encoded = BridgeCodec.encodeFitSpec(spec(listOf(legacy)))
        assertFalse(encoded.getJSONArray("fighters").getJSONObject(0).has("abilities"))
        assertNull(BridgeCodec.decodeFitSpec(encoded).fighters.single().abilities)
        val abilities = mutableListOf(FighterAbilityState(7, false), FighterAbilityState(8, true))
        val fighters = mutableListOf(legacy.copy(abilities = abilities))
        val captured = BridgeOperation.CreateFit(spec(fighters)).snapshotArguments() as BridgeOperation.CreateFit
        abilities.clear(); fighters.clear()
        assertEquals(listOf(FighterAbilityState(7, false), FighterAbilityState(8, true)), captured.spec.fighters.single().abilities)
        val restored = BridgeCodec.decodeFitSpec(BridgeCodec.encodeFitSpec(captured.spec))
        assertEquals(captured.spec.fighters, restored.fighters)
        val duplicate = captured.spec.copy(fighters = listOf(legacy.copy(abilities = listOf(FighterAbilityState(7, true), FighterAbilityState(7, false)))))
        reject { BridgeCodec.encodeFitSpec(duplicate) }
        val unordered = legacy.copy(abilities = listOf(FighterAbilityState(8, true), FighterAbilityState(7, false)))
        val oversized = legacy.copy(abilities = (1..129).map { FighterAbilityState(it, false) })
        reject { BridgeCodec.encodeFitSpec(spec(listOf(unordered))) }
        reject { BridgeCodec.encodeFitSpec(spec(listOf(oversized))) }
        assertEquals(0, BridgeCodec.decodeFitSpec(BridgeCodec.encodeFitSpec(spec(listOf(legacy.copy(amount = 0))))).fighters.single().amount)
        val positions = mutableListOf(1)
        val toggle = BridgeOperation.ToggleFighterAbility("fit", 0, positions, 7).snapshotArguments() as BridgeOperation.ToggleFighterAbility
        positions.clear(); assertEquals(listOf(1), toggle.positions)
        try { (toggle.positions as MutableList<Int>).clear(); fail("Mutable operation capture") } catch (_: UnsupportedOperationException) { }
    }
    @Test fun unknownCapacityIndependentSameTypeSquadronsAndExplicitOveragesArePreserved() {
        val value = details()
        value.getJSONArray("squadrons").getJSONObject(0).put("amount", 8)
        val result = FighterDetailsCodec.decode(value.toString())
        assertNull(result.bayCapacity); assertEquals(2, result.squadrons.size)
        assertEquals(result.squadrons[0].itemId, result.squadrons[1].itemId)
        assertNotEquals(result.squadrons[0].objectKey, result.squadrons[1].objectKey)
        assertEquals(8, result.squadrons[0].amount); assertEquals(6, result.squadrons[0].maxSize)
        assertEquals(1, result.tubesUsed); assertFalse(result.squadrons[1].active)
        try { (result.squadrons as MutableList<FighterSquadron>).clear(); fail("Mutable details") } catch (_: UnsupportedOperationException) { }
    }
    @Test fun malformedDetailsCannotPublishPartialOrInventedCounts() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", true) }, { it.put("revision", 0) }, { it.put("bay_capacity", false) },
            { it.put("tubes_used", 2) }, { it.put("extra", 1) }, { it.put("categories", JSONArray()) },
            { it.getJSONArray("categories").getJSONObject(0).put("used", 0) },
            { it.getJSONArray("squadrons").getJSONObject(0).put("index", 1) },
            { it.getJSONArray("squadrons").getJSONObject(1).put("object_key", "fighter-0") },
            { it.getJSONArray("squadrons").getJSONObject(0).put("amount", -1) },
            { it.getJSONArray("squadrons").getJSONObject(0).put("slot", "DRONE") },
            { it.getJSONArray("squadrons").getJSONObject(0).getJSONArray("abilities").put(JSONObject().put("effect_id", 1).put("name", "Duplicate").put("active", false)) },
            { it.getJSONArray("squadrons").getJSONObject(0).getJSONArray("abilities").getJSONObject(0).put("active", 1) })
        mutations.forEach { mutation -> val value = details(); mutation(value); reject { FighterDetailsCodec.decode(value.toString()) } }
        reject { FighterDetailsCodec.decode(details().toString().replace("\"bay_used\":3000", "\"bay_used\":1e309")) }
        reject { FighterDetailsCodec.decode(details().toString().replaceFirst("{", "{\"version\":1,")) }
    }
}
