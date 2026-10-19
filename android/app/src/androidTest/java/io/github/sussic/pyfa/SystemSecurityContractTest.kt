package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class SystemSecurityContractTest {
    private val labels = listOf("High Security", "Low Security", "Null Security", "W-Space")
    private fun source() = JSONObject().put("version",1).put("fit_id","fit").put("revision",3)
        .put("is_structure",true).put("system","HISEC").put("choices",JSONArray(SystemSecurity.entries.mapIndexed { index,id ->
            JSONObject().put("id",id.name).put("label",labels[index]) }))
    private fun reject(block: () -> Unit) { try { block(); fail("Accepted invalid system security contract") } catch (_: BridgeProtocolException) { } }
    @Test fun exactSourceChoicesAndCurrentSelectionAreImmutable() {
        for (system in SystemSecurity.entries) {
            val value = SystemSecurityCodec.decode(source().put("system",system.name).toString())
            assertEquals("fit",value.fitId); assertEquals(3L,value.revision); assertTrue(value.isStructure)
            assertEquals(system,value.system); assertEquals(SystemSecurity.entries.toList(),value.choices.map { it.id })
            assertEquals(labels,value.choices.map { it.label })
            try { (value.choices as MutableList<SystemSecurityChoice>).clear(); fail("Mutable choices") } catch (_: UnsupportedOperationException) { }
        }
        val ship = SystemSecurityCodec.decode(source().put("is_structure",false).put("choices",JSONArray()).toString())
        assertFalse(ship.isStructure); assertTrue(ship.choices.isEmpty()); assertEquals(SystemSecurity.HISEC,ship.system)
    }
    @Test fun unknownMalformedMisorderedOrInapplicableChoicesAreRejected() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version",true) }, { it.put("revision",0) }, { it.put("revision",3.0) },
            { it.put("fit_id","") }, { it.put("system","HIGH") }, { it.put("system",JSONObject.NULL) },
            { it.put("is_structure",1) }, { it.put("is_structure",false) }, { it.put("extra",true) },
            { it.put("choices",JSONArray()) },
            { it.getJSONArray("choices").getJSONObject(0).put("label","High") },
            { it.getJSONArray("choices").getJSONObject(1).put("id","HISEC") },
            { it.getJSONArray("choices").getJSONObject(0).put("id","LOWSEC") },
            { it.getJSONArray("choices").getJSONObject(0).put("extra",true) })
        mutations.forEach { mutate -> val value=source(); mutate(value); reject { SystemSecurityCodec.decode(OfflineFeatureCodec.json(value)) } }
        reject { SystemSecurityCodec.decode(source().toString().replaceFirst("{","{\"version\":1,")) }
    }
    @Test fun operationUsesExistingRevisionGuardAndOnlySystemSecurityArguments() {
        for (system in SystemSecurity.entries) {
            val operation = BridgeOperation.SetSystemSecurity("fit",system)
            val wire = JSONObject(BridgeCodec.encodeRequest(BridgeRequest("request","session",operation,mapOf("fit" to 3L))))
            assertEquals("set_system_security",wire.getString("operation"))
            assertEquals(setOf("fit_id","system"),wire.getJSONObject("arguments").keys().asSequence().toSet())
            assertEquals(system.name,wire.getJSONObject("arguments").getString("system"))
            assertEquals(3L,wire.getJSONObject("expected_revisions").getLong("fit"))
            assertEquals(operation,operation.snapshotArguments())
        }
    }
}
