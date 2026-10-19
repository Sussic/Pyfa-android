package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Authored C04 contract checks. Execute with the native gate when its hold lifts. */
@RunWith(AndroidJUnit4::class)
class DroneContractTest {
    private fun payload(): JSONObject {
        val metrics = JSONArray()
        droneMetricUnits.forEach { (key, unit) -> metrics.put(JSONObject().put("key", key).put("label", key)
            .put("unit", unit).put("value", JSONObject.NULL).put("text", JSONObject.NULL)) }
        val row = JSONObject().put("index", 0).put("object_key", "a".repeat(32)).put("item_id", 2454)
            .put("name", "Hobgoblin I").put("group", "Combat Drone").put("amount", 5).put("active", 3)
            .put("mutation", JSONObject.NULL).put("metrics", metrics)
        return JSONObject().put("version", 1).put("fit_id", "fixture").put("revision", 1)
            .put("active", 3).put("active_limit", 5).put("bay_used", 25).put("bay_capacity", 125)
            .put("bandwidth_used", 15).put("bandwidth_capacity", 75).put("stacks", JSONArray().put(row))
    }
    private fun rejected(edit: (JSONObject) -> Unit) {
        val value = payload(); edit(value)
        try { BridgeCodec.decodeDroneDetails(value.toString()); fail("Malformed drone response accepted") }
        catch (_: BridgeProtocolException) { }
    }
    @Test fun exactDetailsContractRejectsLostFieldsUnitsIdentityAndCounts() {
        val decoded = BridgeCodec.decodeDroneDetails(payload().toString())
        assertEquals(47, decoded.stacks.single().metrics.size)
        assertNull(decoded.stacks.single().metrics.first().value)
        rejected { it.put("active", 4) }
        rejected { it.put("revision", 0) }
        rejected { it.put("extra", 1) }
        rejected { it.getJSONArray("stacks").getJSONObject(0).put("amount", true) }
        rejected { it.getJSONArray("stacks").getJSONObject(0).put("active", 6) }
        rejected { it.getJSONArray("stacks").getJSONObject(0).put("object_key", "old") }
        rejected { it.getJSONArray("stacks").getJSONObject(0).getJSONArray("metrics").remove(0) }
        rejected { it.getJSONArray("stacks").getJSONObject(0).getJSONArray("metrics").getJSONObject(0).put("unit", "wrong") }
        rejected { it.getJSONArray("stacks").getJSONObject(0).getJSONArray("metrics").getJSONObject(0).put("value", 0) }
    }
    @Test fun queuedSelectionsAreIndependentOfCallerMutation() {
        val positions = mutableListOf(0, 2)
        val remove = BridgeOperation.RemoveDrones("fit", positions, 1).snapshotArguments() as BridgeOperation.RemoveDrones
        val toggle = BridgeOperation.ToggleDrones("fit", 0, positions).snapshotArguments() as BridgeOperation.ToggleDrones
        positions.clear(); positions.add(9)
        assertEquals(listOf(0, 2), remove.positions)
        assertEquals(listOf(0, 2), toggle.positions)
    }
    @Test fun eightOperationsEncodePreciselyAndPermitMainOnlyToggle() {
        val operations = listOf(
            BridgeOperation.AddDrone("fit",2454,1) to "add_drone",
            BridgeOperation.AddDroneStack("fit",2454) to "add_drone_stack",
            BridgeOperation.SetDroneAmount("fit",0,0) to "set_drone_amount",
            BridgeOperation.RemoveDrones("fit",listOf(0,1),1) to "remove_drones",
            BridgeOperation.ToggleDrones("fit",0,emptyList()) to "toggle_drones",
            BridgeOperation.CloneDrone("fit",0) to "clone_drone",
            BridgeOperation.SplitDrone("fit",0,2) to "split_drone",
            BridgeOperation.MergeDrones("fit",1,0) to "merge_drones")
        operations.forEach { (operation, name) ->
            val wire = JSONObject(BridgeCodec.encodeRequest(BridgeRequest("request","session",operation,mapOf("fit" to 1L))))
            assertEquals(name, wire.getString("operation"))
            assertEquals("fit", wire.getJSONObject("arguments").getString("fit_id"))
        }
        val invalid = listOf(BridgeOperation.AddDrone("fit",2454,0),
            BridgeOperation.SplitDrone("fit",0,0), BridgeOperation.MergeDrones("fit",-1,0),
            BridgeOperation.RemoveDrones("fit",emptyList(),1), BridgeOperation.ToggleDrones("fit",0,listOf(0,0)))
        invalid.forEach { operation ->
            try { BridgeCodec.encodeRequest(BridgeRequest("request","session",operation,mapOf("fit" to 1L))); fail("Invalid drone edit accepted") }
            catch (_: BridgeProtocolException) { }
        }
    }
}
