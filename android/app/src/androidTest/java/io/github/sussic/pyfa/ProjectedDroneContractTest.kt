package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProjectedDroneContractTest {
    private val key="a".repeat(32)
    private fun rejects(block: () -> Unit) { try { block(); fail("Invalid projected-drone contract accepted") } catch (_: BridgeProtocolException) { } }
    private fun row(index: Int=0) = JSONObject().put("index",index).put("object_key",key).put("item_id",100)
        .put("name","Warrior SW-300").put("amount",5).put("active",2).put("range_m",JSONObject.NULL)
        .put("editable",true).put("unavailable_reason",JSONObject.NULL)
    private fun details(r: JSONObject=row()) = JSONObject().put("version",1).put("fit_id","fit").put("revision",7)
        .put("is_structure",false).put("stacks",JSONArray().put(r))
    private fun options() = JSONObject().put("version",1).put("fit_id","fit").put("revision",7).put("index",0)
        .put("object_key",key).put("item_id",100).put("activation_allowed",true).put("activation_unavailable_reason",JSONObject.NULL)
        .put("variations",JSONArray().put(JSONObject().put("id",101).put("name","Variation").put("enabled",true)))
    private fun add() = JSONObject().put("version",1).put("fit_id","fit").put("revision",7).put("item_id",100)
        .put("is_drone",true).put("is_projectable",true).put("is_structure",false).put("enabled",true)
        .put("unavailable_reason",JSONObject.NULL)

    @Test fun queriesPreservePartialCountsRawRangesAndStrictBoundedImmutableChoices() {
        val d=ProjectedDroneCodec.details(details().toString()); val r=d.stacks.single()
        assertEquals(5,r.amount); assertEquals(2,r.active); assertNull(r.rangeM)
        assertEquals(Int.MAX_VALUE,ProjectedDroneCodec.details(details(row().put("amount",Int.MAX_VALUE)).toString()).stacks.single().amount)
        for (raw in listOf(0.0,Double.MIN_VALUE,63.7)) assertEquals(raw,
            ProjectedDroneCodec.details(details(row().put("range_m",raw)).toString()).stacks.single().rangeM!!,0.0)
        val o=ProjectedDroneCodec.options(options().toString()); assertTrue(o.activationAllowed)
        assertFalse(ProjectedDroneCodec.options(options().put("activation_allowed",false)
            .put("activation_unavailable_reason","Recipient refuses assistance").toString()).activationAllowed)
        assertTrue(ProjectedDroneCodec.addOptions(add().toString()).enabled)
        assertFalse(ProjectedDroneCodec.addOptions(add().put("is_structure",true).put("enabled",false)
            .put("unavailable_reason","Individual projections are unavailable for structures").toString()).enabled)
        for (prefix in listOf("Projected-drone evaluation budget:","Projected-drone capacitor evaluation budget:")) {
            val failure=RuntimeException("wrapper",IllegalArgumentException(prefix+" internal detail"))
            assertEquals("This configuration exceeds the projected-drone evaluation budget. Reduce its quantity or complexity before retrying.",
                projectedDroneReadError(failure,"Safe fallback"))
            assertFalse(projectedReadRequiresReopen(failure))
        }
        assertEquals("Safe fallback",projectedDroneReadError(IllegalArgumentException("unrecognized detail"),"Safe fallback"))
        for (list in listOf(d.stacks,o.variations)) try { (list as MutableList<*>).clear(); fail("Mutable result") } catch (_: UnsupportedOperationException) { }
        for ((field,value) in listOf("amount" to 0,"amount" to -1,"amount" to 2147483648L,"amount" to true,
            "active" to -1,"active" to 6,"index" to 1,"object_key" to "bad","range_m" to -1,"editable" to false)) {
            rejects { ProjectedDroneCodec.details(details(row().put(field,value)).toString()) }
        }
        rejects { ProjectedDroneCodec.details(details().put("is_structure",true).toString()) }
        rejects { ProjectedDroneCodec.details(details(row().put("range_m",9007199254740993L)).toString()) }
        rejects { ProjectedDroneCodec.details(details(row().put("range_m",Long.MAX_VALUE)).toString()) }
        rejects { ProjectedDroneCodec.options(options().put("index",1024).toString()) }
        rejects { ProjectedDroneCodec.details(details().put("stacks",JSONArray().put(row()).put(row(1))).toString()) }
        rejects { ProjectedDroneCodec.details(details().put("stacks",JSONArray((0..1024).map { row(it).put("object_key",it.toString(16).padStart(32,'0')).put("item_id",it+1) })).toString()) }
        rejects { ProjectedDroneCodec.details(details().toString().replace("\"active\":2","\"active\":2.0")) }
        rejects { ProjectedDroneCodec.options(options().put("activation_allowed",false).toString()) }
        rejects { ProjectedDroneCodec.options(options().put("variations",JSONArray((1..8193).map { JSONObject().put("id",it).put("name","Choice").put("enabled",true) })).toString()) }
        rejects { ProjectedDroneCodec.options(options().put("extra",true).toString()) }
        rejects { ProjectedDroneCodec.addOptions(add().put("is_drone",false).toString()) }
        rejects { ProjectedDroneCodec.addOptions(add().put("enabled",false).toString()) }
    }

    @Test fun sixOperationsCarryExactIdentityRevisionAndSourceIntentWithoutComputedActiveCounts() {
        fun wire(op: BridgeOperation,revisions: Map<String,Long> = mapOf("fit" to 7L)) =
            JSONObject(BridgeCodec.encodeRequest(BridgeRequest("request","session",op,revisions)))
        val cases=listOf(
            Triple(BridgeOperation.AddProjectedDrone("fit",100),"add_projected_drone",setOf("fit_id","item_id")),
            Triple(BridgeOperation.SetProjectedDroneAmount("fit",0,key,0),"set_projected_drone_amount",setOf("fit_id","position","object_key","amount")),
            Triple(BridgeOperation.SetProjectedDroneActive("fit",0,key,false),"set_projected_drone_active",setOf("fit_id","position","object_key","active")),
            Triple(BridgeOperation.SetProjectedDroneRange("fit",0,key,null),"set_projected_drone_range",setOf("fit_id","position","object_key","range_m")),
            Triple(BridgeOperation.ChangeProjectedDroneVariation("fit",0,key,101),"change_projected_drone_variation",setOf("fit_id","position","object_key","item_id")),
            Triple(BridgeOperation.RemoveProjectedDrone("fit",0,key,1),"remove_projected_drone",setOf("fit_id","position","object_key","amount")))
        for ((op,name,keys) in cases) {
            val value=wire(op)
            assertEquals(name,value.getString("operation")); assertEquals(keys,value.getJSONObject("arguments").keys().asSequence().toSet())
            assertEquals(setOf("fit"),value.getJSONObject("expected_revisions").keys().asSequence().toSet())
            assertEquals(op,op.snapshotArguments()); rejects { wire(op,emptyMap()) }; rejects { wire(op,mapOf("fit" to 7L,"other" to 1L)) }
        }
        assertTrue(wire(cases[3].first).getJSONObject("arguments").isNull("range_m"))
        assertEquals(0.0,wire(BridgeOperation.SetProjectedDroneRange("fit",0,key,0.0)).getJSONObject("arguments").getDouble("range_m"),0.0)
        assertEquals(Int.MAX_VALUE,wire(BridgeOperation.SetProjectedDroneAmount("fit",0,key,Int.MAX_VALUE)).getJSONObject("arguments").getInt("amount"))
        rejects { wire(BridgeOperation.AddProjectedDrone("fit",0)) }
        rejects { wire(BridgeOperation.SetProjectedDroneAmount("fit",0,key,-1)) }
        rejects { wire(BridgeOperation.RemoveProjectedDrone("fit",0,key,0)) }
        rejects { wire(BridgeOperation.RemoveProjectedDrone("fit",-1,key,1)) }
        rejects { wire(BridgeOperation.RemoveProjectedDrone("fit",0,"wrong",1)) }
        rejects { wire(BridgeOperation.ChangeProjectedDroneVariation("fit",0,key,0)) }
        for (range in listOf(-1.0,Double.NaN,Double.POSITIVE_INFINITY)) rejects { wire(BridgeOperation.SetProjectedDroneRange("fit",0,key,range)) }
    }
}
