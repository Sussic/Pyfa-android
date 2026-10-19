package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProjectedFighterContractTest {
    private val key="a".repeat(32)
    private fun rejects(block: () -> Unit) { try { block(); fail("Invalid projected-fighter contract accepted") } catch (_: BridgeProtocolException) { } }
    private fun row(index: Int=0) = JSONObject().put("index",index).put("object_key",key).put("item_id",100)
        .put("name","Dromi I").put("amount",5).put("max_size",3).put("active",true).put("range_m",JSONObject.NULL)
        .put("editable",true).put("unavailable_reason",JSONObject.NULL)
    private fun details(r: JSONObject=row()) = JSONObject().put("version",1).put("fit_id","fit").put("revision",7)
        .put("is_structure",false).put("squadrons",JSONArray().put(r))
    private fun options() = JSONObject().put("version",1).put("fit_id","fit").put("revision",7).put("index",0)
        .put("object_key",key).put("item_id",100).put("abilities",JSONArray().put(JSONObject().put("effect_id",6435).put("name","Stasis Webifier").put("active",true)))
        .put("variations",JSONArray().put(JSONObject().put("id",101).put("name","Variation").put("enabled",true)))
    private fun add() = JSONObject().put("version",1).put("fit_id","fit").put("revision",7).put("item_id",100)
        .put("is_fighter",true).put("is_projectable",true).put("is_structure",false).put("enabled",true)
        .put("unavailable_reason",JSONObject.NULL)

    @Test fun queriesAllowDuplicateSquadronsAndTruthfulCountsWithStrictImmutableAbilityChoices() {
        val d=ProjectedFighterCodec.details(details().toString()); val r=d.squadrons.single()
        assertEquals(5,r.amount); assertEquals(3,r.maxSize); assertTrue(r.active); assertNull(r.rangeM)
        assertEquals(Int.MAX_VALUE,ProjectedFighterCodec.details(details(row().put("amount",Int.MAX_VALUE)).toString()).squadrons.single().amount)
        for (raw in listOf(0.0,Double.MIN_VALUE,63.7)) assertEquals(raw,
            ProjectedFighterCodec.details(details(row().put("range_m",raw)).toString()).squadrons.single().rangeM!!,0.0)
        val o=ProjectedFighterCodec.options(options().toString()); assertTrue(o.abilities.single().active)
        assertEquals(6435,o.abilities.single().effectId)
        val duplicates=details().put("squadrons",JSONArray().put(row()).put(row(1).put("object_key","b".repeat(32))))
        assertEquals(listOf(100,100),ProjectedFighterCodec.details(duplicates.toString()).squadrons.map { it.itemId })
        assertEquals(0,ProjectedFighterCodec.details(details(row().put("amount",0)).toString()).squadrons.single().amount)
        assertTrue(ProjectedFighterCodec.addOptions(add().toString()).enabled)
        assertFalse(ProjectedFighterCodec.addOptions(add().put("is_structure",true).put("enabled",false)
            .put("unavailable_reason","Individual projections are unavailable for structures").toString()).enabled)
        for (prefix in listOf("Projected-drone evaluation budget:","Projected-drone capacitor evaluation budget:")) {
            val failure=RuntimeException("wrapper",IllegalArgumentException(prefix+" internal detail"))
            assertEquals("This configuration exceeds the incoming-projector evaluation budget. Reduce its quantity or complexity before retrying.",
                projectedFighterReadError(failure,"Safe fallback"))
            assertFalse(projectedReadRequiresReopen(failure))
        }
        assertEquals("Safe fallback",projectedFighterReadError(IllegalArgumentException("unrecognized detail"),"Safe fallback"))
        for (list in listOf(d.squadrons,o.abilities,o.variations)) try { (list as MutableList<*>).clear(); fail("Mutable result") } catch (_: UnsupportedOperationException) { }
        for ((field,value) in listOf("max_size" to -1,"amount" to -1,"amount" to 2147483648L,"amount" to true,
            "active" to 1,"active" to "true","index" to 1,"object_key" to "bad","range_m" to -1,"editable" to false)) {
            rejects { ProjectedFighterCodec.details(details(row().put(field,value)).toString()) }
        }
        rejects { ProjectedFighterCodec.details(details().put("is_structure",true).toString()) }
        rejects { ProjectedFighterCodec.details(details(row().put("range_m",9007199254740993L)).toString()) }
        rejects { ProjectedFighterCodec.details(details(row().put("range_m",Long.MAX_VALUE)).toString()) }
        rejects { ProjectedFighterCodec.options(options().put("index",1024).toString()) }
        rejects { ProjectedFighterCodec.details(details().put("squadrons",JSONArray().put(row()).put(row(1))).toString()) }
        rejects { ProjectedFighterCodec.details(details().put("squadrons",JSONArray((0..1024).map { row(it).put("object_key",it.toString(16).padStart(32,'0')).put("item_id",it+1) })).toString()) }
        rejects { ProjectedFighterCodec.details(details().toString().replace("\"active\":true","\"active\":1")) }
        rejects { ProjectedFighterCodec.options(options().put("abilities",JSONArray().put(JSONObject().put("effect_id",6435).put("name","Web").put("active",1))).toString()) }
        rejects { ProjectedFighterCodec.options(options().put("abilities",JSONArray((1..129).map { JSONObject().put("effect_id",it).put("name","Ability").put("active",false) })).toString()) }
        rejects { ProjectedFighterCodec.options(options().put("abilities",JSONArray(listOf(1,1).map { JSONObject().put("effect_id",it).put("name","Ability").put("active",false) })).toString()) }
        rejects { ProjectedFighterCodec.options(options().put("variations",JSONArray((1..8193).map { JSONObject().put("id",it).put("name","Choice").put("enabled",true) })).toString()) }
        rejects { ProjectedFighterCodec.options(options().put("extra",true).toString()) }
        rejects { ProjectedFighterCodec.addOptions(add().put("is_fighter",false).toString()) }
        rejects { ProjectedFighterCodec.addOptions(add().put("enabled",false).toString()) }
    }

    @Test fun sevenOperationsCarryExactIdentityRevisionAndIndependentAbilityStateIntent() {
        fun wire(op: BridgeOperation,revisions: Map<String,Long> = mapOf("fit" to 7L)) =
            JSONObject(BridgeCodec.encodeRequest(BridgeRequest("request","session",op,revisions)))
        val cases=listOf(
            Triple(BridgeOperation.AddProjectedFighter("fit",100),"add_projected_fighter",setOf("fit_id","item_id")),
            Triple(BridgeOperation.SetProjectedFighterAmount("fit",0,key,0),"set_projected_fighter_amount",setOf("fit_id","position","object_key","amount")),
            Triple(BridgeOperation.SetProjectedFighterActive("fit",0,key,false),"set_projected_fighter_active",setOf("fit_id","position","object_key","active")),
            Triple(BridgeOperation.SetProjectedFighterRange("fit",0,key,null),"set_projected_fighter_range",setOf("fit_id","position","object_key","range_m")),
            Triple(BridgeOperation.ChangeProjectedFighterVariation("fit",0,key,101),"change_projected_fighter_variation",setOf("fit_id","position","object_key","item_id")),
            Triple(BridgeOperation.RemoveProjectedFighter("fit",0,key),"remove_projected_fighter",setOf("fit_id","position","object_key")),
            Triple(BridgeOperation.ToggleProjectedFighterAbility("fit",0,key,6435),"toggle_projected_fighter_ability",setOf("fit_id","position","object_key","effect_id")))
        for ((op,name,keys) in cases) {
            val value=wire(op)
            assertEquals(name,value.getString("operation")); assertEquals(keys,value.getJSONObject("arguments").keys().asSequence().toSet())
            assertEquals(setOf("fit"),value.getJSONObject("expected_revisions").keys().asSequence().toSet())
            assertEquals(op,op.snapshotArguments()); rejects { wire(op,emptyMap()) }; rejects { wire(op,mapOf("fit" to 7L,"other" to 1L)) }
        }
        assertTrue(wire(cases[3].first).getJSONObject("arguments").isNull("range_m"))
        assertEquals(0.0,wire(BridgeOperation.SetProjectedFighterRange("fit",0,key,0.0)).getJSONObject("arguments").getDouble("range_m"),0.0)
        assertEquals(Int.MAX_VALUE,wire(BridgeOperation.SetProjectedFighterAmount("fit",0,key,Int.MAX_VALUE)).getJSONObject("arguments").getInt("amount"))
        rejects { wire(BridgeOperation.AddProjectedFighter("fit",0)) }
        rejects { wire(BridgeOperation.SetProjectedFighterAmount("fit",0,key,-1)) }
        rejects { wire(BridgeOperation.ToggleProjectedFighterAbility("fit",0,key,0)) }
        rejects { wire(BridgeOperation.RemoveProjectedFighter("fit",-1,key)) }
        rejects { wire(BridgeOperation.RemoveProjectedFighter("fit",0,"wrong")) }
        rejects { wire(BridgeOperation.ChangeProjectedFighterVariation("fit",0,key,0)) }
        for (range in listOf(-1.0,Double.NaN,Double.POSITIVE_INFINITY)) rejects { wire(BridgeOperation.SetProjectedFighterRange("fit",0,key,range)) }
    }
}
