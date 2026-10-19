package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ImplantContractTest {
    private fun wire(operation: BridgeOperation) = JSONObject(BridgeCodec.encodeRequest(
        BridgeRequest("request","session",operation,mapOf("fit" to 7L))))
    private fun row(index: Int = 0, slot: Int = 12) = JSONObject().put("index",index).put("object_key","implant-$index")
        .put("item_id",100+index).put("name","Implant $index").put("slot",slot).put("active",true)
    private fun details() = JSONObject().put("version",1).put("fit_id","fit").put("revision",7)
        .put("is_structure",false).put("location","FIT").put("implants",JSONArray().put(row()).put(row(1,1)))
    private fun options() = JSONObject().put("version",1).put("fit_id","fit").put("revision",7).put("item_id",102)
        .put("is_implant",true).put("is_structure",false).put("location","FIT").put("slot",12).put("already_fitted",false)
        .put("occupant",JSONObject().put("index",0).put("object_key","implant-0").put("item_id",100).put("name","Implant 0"))
    private fun reject(block: () -> Unit) { try { block(); fail("Accepted invalid implant contract") } catch (_: BridgeProtocolException) { } }
    @Test fun newAtomicAndExistingSingleSlotOperationsKeepExactWireFields() {
        val cases = listOf(
            Triple(BridgeOperation.FitImplant("fit",102),"fit_implant",setOf("fit_id","item_id")),
            Triple(BridgeOperation.ToggleImplants("fit",0,listOf(1)),"toggle_implants",setOf("fit_id","main_position","positions")),
            Triple(BridgeOperation.RemoveImplants("fit",listOf(1,0)),"remove_implants",setOf("fit_id","positions")),
            Triple(BridgeOperation.AddImplant("fit","Implant 0",false),"add_implant",setOf("fit_id","implant","active")),
            Triple(BridgeOperation.SetImplantActive("fit",12,false),"set_implant_active",setOf("fit_id","slot","active")),
            Triple(BridgeOperation.RemoveImplant("fit",12),"remove_implant",setOf("fit_id","slot")))
        cases.forEach { (operation,name,fields) ->
            val value = wire(operation); assertEquals(name,value.getString("operation"))
            assertEquals(fields,value.getJSONObject("arguments").keys().asSequence().toSet())
            assertEquals(7,value.getJSONObject("expected_revisions").getInt("fit"))
        }
    }
    @Test fun boundedSelectionIsCapturedAndInvalidInputsFailBeforeEnqueue() {
        val positions = mutableListOf(1,0)
        val captured = BridgeOperation.ToggleImplants("fit",0,positions).snapshotArguments() as BridgeOperation.ToggleImplants
        positions.clear(); assertEquals(listOf(1,0),captured.positions)
        try { (captured.positions as MutableList<Int>).clear(); fail("Mutable positions") } catch (_: UnsupportedOperationException) { }
        listOf(BridgeOperation.FitImplant("fit",0),BridgeOperation.ToggleImplants("fit",-1,emptyList()),
            BridgeOperation.RemoveImplants("fit",emptyList()),BridgeOperation.RemoveImplants("fit",listOf(1,1)),
            BridgeOperation.RemoveImplants("fit",listOf(-1)),BridgeOperation.ToggleImplants("fit",0,(0..1024).toList()))
            .forEach { reject { wire(it) } }
    }
    @Test fun detailsSortOnlyForDisplayAndRetainSlotIdentityAndSourceAvailability() {
        val value = ImplantDetailsCodec.details(details().toString())
        assertEquals(listOf(0,1),value.implants.map { it.index })
        assertEquals(listOf(1,0),value.displayRows.map { it.index })
        assertEquals(listOf(1,12),value.displayRows.map { it.slot })
        assertEquals(listOf("implant-1","implant-0"),value.displayRows.map { it.objectKey })
        assertTrue(value.editable)
        assertFalse(ImplantDetailsCodec.details(details().put("is_structure",true).toString()).editable)
        assertFalse(ImplantDetailsCodec.details(details().put("location","CHARACTER").toString()).editable)
        try { (value.implants as MutableList<ImplantRow>).clear(); fail("Mutable saved order") } catch (_: UnsupportedOperationException) { }
        assertTrue(ImplantDetailsCodec.details(details().put("implants",JSONArray()).toString()).implants.isEmpty())
    }
    @Test fun addOptionsRepresentFreeOccupiedDuplicateNonimplantStructureAndCharacter() {
        val occupied = ImplantDetailsCodec.addOptions(options().toString())
        assertEquals(100,occupied.occupant!!.itemId); assertTrue(occupied.editable); assertFalse(occupied.alreadyFitted)
        val free = ImplantDetailsCodec.addOptions(options().put("occupant",JSONObject.NULL).toString())
        assertTrue(free.isImplant); assertEquals(12,free.slot); assertNull(free.occupant)
        assertTrue(ImplantDetailsCodec.addOptions(options().put("item_id",100).put("already_fitted",true).toString()).alreadyFitted)
        assertFalse(ImplantDetailsCodec.addOptions(options().put("is_structure",true).toString()).editable)
        assertTrue(ImplantDetailsCodec.addOptions(options().put("location","CHARACTER").toString()).editable)
        val other = ImplantDetailsCodec.addOptions(options().put("is_implant",false).put("slot",JSONObject.NULL).put("occupant",JSONObject.NULL).toString())
        assertFalse(other.isImplant); assertNull(other.slot); assertNull(other.occupant)
    }
    @Test fun malformedShapesTypesIdentityAndSlotApplicabilityAreRejected() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version",true) },{ it.put("revision",0) },{ it.put("location","UNKNOWN") },{ it.put("extra",true) },
            { it.getJSONArray("implants").getJSONObject(0).put("active",1) },
            { it.getJSONArray("implants").getJSONObject(0).put("slot",0) },
            { it.getJSONArray("implants").getJSONObject(0).put("slot",1.0) },
            { it.getJSONArray("implants").getJSONObject(0).put("index",2) },
            { it.getJSONArray("implants").getJSONObject(1).put("slot",12) },
            { it.getJSONArray("implants").getJSONObject(1).put("item_id",100) },
            { it.getJSONArray("implants").getJSONObject(1).put("object_key","implant-0") })
        mutations.forEach { mutate -> val value = details(); mutate(value); reject { ImplantDetailsCodec.details(OfflineFeatureCodec.json(value)) } }
        val optionMutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("is_implant",false) },{ it.put("slot",JSONObject.NULL) },{ it.put("already_fitted",true) },
            { it.put("location",JSONObject.NULL) },{ it.getJSONObject("occupant").put("object_key","") })
        optionMutations.forEach { mutate -> val value = options(); mutate(value); reject { ImplantDetailsCodec.addOptions(value.toString()) } }
        reject { ImplantDetailsCodec.details(details().toString().replaceFirst("{","{\"version\":1,")) }
    }
}
