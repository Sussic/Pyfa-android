package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProjectedModuleContractTest {
    private val key = "a".repeat(32)
    private fun rejects(block: () -> Unit) { try { block(); fail("Invalid projector contract accepted") } catch (_: BridgeProtocolException) { } }
    private fun row(index: Int = 2, objectKey: String = key) = JSONObject().put("index",index).put("object_key",objectKey)
        .put("item_id",100).put("name","Remote Sensor Booster II").put("state","ACTIVE")
        .put("charge_id",JSONObject.NULL).put("charge_name",JSONObject.NULL).put("range_m",JSONObject.NULL)
        .put("editable",true).put("unavailable_reason",JSONObject.NULL)
    private fun details() = JSONObject().put("version",1).put("fit_id","fit").put("revision",7).put("is_structure",false)
        .put("modules",JSONArray().put(row()))
    private fun options() = JSONObject().put("version",1).put("fit_id","fit").put("revision",7)
        .put("index",2).put("object_key",key).put("item_id",100)
        .put("state_actions",JSONArray().put(JSONObject().put("id","inactive").put("label","Inactive").put("enabled",true)))
        .put("charges",JSONArray().put(JSONObject().put("id",200).put("name","Scan Resolution Script")))
        .put("variations",JSONArray().put(JSONObject().put("id",101).put("name","Remote Sensor Booster I").put("enabled",true)))
        .put("spool",JSONObject.NULL)
    private fun spool() = JSONObject().put("index",2).put("object_key",key).put("item_id",100).put("name","Remote repair")
        .put("override_cycles",999).put("current_cycles",30).put("default_cycles",30).put("minimum_cycles",0).put("maximum_cycles",30)
        .put("current_seconds",150.0).put("default_seconds",150.0).put("minimum_seconds",0.0).put("maximum_seconds",150.0)
        .put("choices",JSONArray(listOf(0,15,30)))
    private fun add() = JSONObject().put("version",1).put("fit_id","fit").put("revision",7).put("item_id",100)
        .put("is_module",true).put("is_projectable",true).put("is_structure",false).put("enabled",true)
        .put("unavailable_reason",JSONObject.NULL)

    @Test fun boundedImmutableQueriesKeepOriginalPositionsNullZeroAndUnavailableRows() {
        val d = ProjectedModuleCodec.details(details().put("modules",JSONArray()
            .put(row(0,"b".repeat(32)).put("editable",false).put("unavailable_reason","Legacy environment (read only)"))
            .put(row().put("range_m",0))).toString())
        assertEquals(listOf(0,2),d.modules.map { it.index }); assertNull(d.modules.first().rangeM)
        assertEquals(0.0,d.modules.last().rangeM!!,0.0); assertFalse(d.modules.first().editable)
        val o = ProjectedModuleCodec.options(options().put("spool",spool()).toString())
        assertEquals(999,o.spool!!.overrideCycles); assertEquals(30,o.spool!!.currentCycles)
        assertEquals(ProjectedModuleStateAction.INACTIVE,o.stateActions.single().id)
        assertEquals(200,o.charges.single().id); assertTrue(o.variations.single().enabled)
        assertTrue(ProjectedModuleCodec.addOptions(add().toString()).enabled)
        assertFalse(ProjectedModuleCodec.addOptions(add().put("is_structure",true).put("enabled",false)
            .put("unavailable_reason","Individual projections are unavailable for structures").toString()).enabled)
        for (list in listOf(d.modules,o.charges,o.variations,o.stateActions)) {
            try { (list as MutableList<*>).clear(); fail("Mutable query result") } catch (_: UnsupportedOperationException) { }
        }
        rejects { ProjectedModuleCodec.details(details().put("modules",JSONArray().put(row()).put(row())).toString()) }
        rejects { ProjectedModuleCodec.details(details().put("modules",JSONArray().put(row().put("object_key","bad"))).toString()) }
        rejects { ProjectedModuleCodec.details(details().put("modules",JSONArray().put(row().put("charge_id",200))).toString()) }
        rejects { ProjectedModuleCodec.details(details().put("is_structure",true).toString()) }
        rejects { ProjectedModuleCodec.details(details().put("modules",JSONArray().put(row().put("range_m",-1))).toString()) }
        rejects { ProjectedModuleCodec.details(details().put("modules",JSONArray().put(row().put("state","inactive"))).toString()) }
        rejects { ProjectedModuleCodec.details(details().put("modules",JSONArray((0..1024).map { row(it,it.toString(16).padStart(32,'0')) })).toString()) }
        rejects { ProjectedModuleCodec.options(options().put("extra",1).toString()) }
        rejects { ProjectedModuleCodec.options(options().put("state_actions",JSONArray().put(JSONObject().put("id","ONLINE").put("label","Online").put("enabled",true))).toString()) }
        rejects { ProjectedModuleCodec.options(options().put("spool",spool().put("object_key","b".repeat(32))).toString()) }
        rejects { ProjectedModuleCodec.options(options().put("spool",spool().put("minimum_cycles",30)).toString()) }
        rejects { ProjectedModuleCodec.options(options().put("charges",JSONArray((1..8193).map { JSONObject().put("id",it).put("name","Charge") })).toString()) }
        rejects { ProjectedModuleCodec.addOptions(add().put("is_module",false).toString()) }
        rejects { ProjectedModuleCodec.addOptions(add().put("enabled",false).toString()) }
        rejects { ProjectedModuleCodec.details(details().toString().replace("\"revision\":7","\"revision\":7.0")) }
    }

    @Test fun sevenOperationsAreExactSingleFitAtomicRequestsAndKeepResetVersusZero() {
        fun wire(op: BridgeOperation, revisions: Map<String,Long> = mapOf("fit" to 7L)) =
            JSONObject(BridgeCodec.encodeRequest(BridgeRequest("request","session",op,revisions)))
        val cases = listOf(
            Triple(BridgeOperation.AddProjectedModule("fit",100),"add_projected_module",setOf("fit_id","item_id")),
            Triple(BridgeOperation.SetProjectedModuleState("fit",2,key,ProjectedModuleStateAction.OVERHEAT),"set_projected_module_state",setOf("fit_id","position","object_key","state")),
            Triple(BridgeOperation.SetProjectedModuleCharge("fit",2,key,null),"set_projected_module_charge",setOf("fit_id","position","object_key","charge_id")),
            Triple(BridgeOperation.ChangeProjectedModuleVariation("fit",2,key,101),"change_projected_module_variation",setOf("fit_id","position","object_key","item_id")),
            Triple(BridgeOperation.SetProjectedModuleRange("fit",2,key,null),"set_projected_module_range",setOf("fit_id","position","object_key","range_m")),
            Triple(BridgeOperation.SetProjectedModuleSpool("fit",2,key,null),"set_projected_module_spool",setOf("fit_id","position","object_key","cycles")),
            Triple(BridgeOperation.RemoveProjectedModule("fit",2,key),"remove_projected_module",setOf("fit_id","position","object_key")),
        )
        for ((op,name,keys) in cases) {
            val result = wire(op)
            assertEquals(name,result.getString("operation")); assertEquals(keys,result.getJSONObject("arguments").keys().asSequence().toSet())
            assertEquals(setOf("fit"),result.getJSONObject("expected_revisions").keys().asSequence().toSet())
            assertEquals(op,op.snapshotArguments()); rejects { wire(op,emptyMap()) }; rejects { wire(op,mapOf("fit" to 7L,"other" to 1L)) }
        }
        assertEquals("overheat",wire(cases[1].first).getJSONObject("arguments").getString("state"))
        for ((index,field) in listOf(2 to "charge_id",4 to "range_m",5 to "cycles")) assertTrue(wire(cases[index].first).getJSONObject("arguments").isNull(field))
        assertEquals(0.0,wire(BridgeOperation.SetProjectedModuleRange("fit",2,key,0.0)).getJSONObject("arguments").getDouble("range_m"),0.0)
        assertEquals(0,wire(BridgeOperation.SetProjectedModuleSpool("fit",2,key,0)).getJSONObject("arguments").getInt("cycles"))
        rejects { wire(BridgeOperation.RemoveProjectedModule("fit",2,"wrong")) }
        rejects { wire(BridgeOperation.RemoveProjectedModule("fit",-1,key)) }
        rejects { wire(BridgeOperation.AddProjectedModule("fit",0)) }
        rejects { wire(BridgeOperation.SetProjectedModuleCharge("fit",2,key,0)) }
        rejects { wire(BridgeOperation.SetProjectedModuleSpool("fit",2,key,-1)) }
        for (range in listOf(-1.0,Double.NaN,Double.POSITIVE_INFINITY)) rejects { wire(BridgeOperation.SetProjectedModuleRange("fit",2,key,range)) }
    }

    @Test fun onlyRecognizedReadUnavailableMessagesRequestReopen() {
        assertTrue(projectedReadRequiresReopen(RuntimeException("RuntimeError: Restart the fitting engine")))
        assertTrue(projectedReadRequiresReopen(RuntimeException("wrapper",IllegalStateException("ProfileError: Reopen the profile fit graph"))))
        assertFalse(projectedReadRequiresReopen(IllegalArgumentException("Choose an editable projected module")))
        assertFalse(projectedReadRequiresReopen(IllegalArgumentException("Too many projected choices")))
    }
}
