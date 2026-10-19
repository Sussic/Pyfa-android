package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ModuleSpoolContractTest {
    private fun wire(operation: BridgeOperation) = JSONObject(BridgeCodec.encodeRequest(
        BridgeRequest("request", "session", operation, mapOf("fit" to 7L))))
    private fun row(index: Int = 2) = JSONObject().put("index", index).put("object_key", "module-$index")
        .put("item_id", 100).put("name", "Spooling module").put("override_cycles", JSONObject.NULL)
        .put("current_cycles", 10).put("default_cycles", 10).put("minimum_cycles", 0).put("maximum_cycles", 10)
        .put("current_seconds", 21.23456789).put("default_seconds", 21.23456789).put("minimum_seconds", 0).put("maximum_seconds", 21.23456789)
        .put("choices", JSONArray(listOf(0, 5, 10)))
    private fun details() = JSONObject().put("version", 1).put("fit_id", "fit").put("revision", 7)
        .put("modules", JSONArray().put(row()))
    private fun spec(modules: List<ModuleSpec>) = FitSpec("Spool", "Vedmak", 5, false,
        DamagePattern(25.0, 25.0, 25.0, 25.0), Security(SystemSecurity.HISEC, 0.0), modules, emptyList())
    private fun reject(block: () -> Unit) { try { block(); fail("Accepted invalid spool contract") } catch (_: BridgeProtocolException) { } }
    @Test fun operationDistinguishesResetFromExplicitZeroAndRejectsNegativeArguments() {
        for (cycles in listOf(null, 0, Int.MAX_VALUE)) {
            val value = wire(BridgeOperation.SetModuleSpool("fit", 2, cycles))
            assertEquals("set_module_spool", value.getString("operation"))
            val args = value.getJSONObject("arguments")
            assertEquals(setOf("fit_id", "position", "cycles"), args.keys().asSequence().toSet())
            assertEquals("fit", args.getString("fit_id")); assertEquals(2, args.getInt("position"))
            if (cycles == null) assertTrue(args.isNull("cycles")) else assertEquals(cycles, args.getInt("cycles"))
            assertEquals(7, value.getJSONObject("expected_revisions").getInt("fit"))
        }
        reject { wire(BridgeOperation.SetModuleSpool("fit", -1, 0)) }
        reject { wire(BridgeOperation.SetModuleSpool("fit", 0, -1)) }
    }
    @Test fun legacyModuleSpecsOmitDefaultsAndCallerCaptureRetainsExplicitZero() {
        val legacy = ModuleSpec("Heavy Entropic Disintegrator I", ModuleState.ACTIVE)
        assertFalse(BridgeCodec.encodeFitSpec(spec(listOf(legacy))).getJSONArray("modules").getJSONObject(0).has("spool_cycles"))
        val modules = mutableListOf(legacy.copy(spoolCycles = 0), legacy.copy(spoolCycles = Int.MAX_VALUE))
        val captured = (BridgeOperation.CreateFit(spec(modules)).snapshotArguments() as BridgeOperation.CreateFit).spec
        modules.clear()
        val encoded = BridgeCodec.encodeFitSpec(captured)
        assertEquals(0, encoded.getJSONArray("modules").getJSONObject(0).getInt("spool_cycles"))
        assertEquals(captured, BridgeCodec.decodeFitSpec(encoded))
        try { (captured.modules as MutableList<ModuleSpec>).clear(); fail("Mutable module snapshot") } catch (_: UnsupportedOperationException) { }
        reject { BridgeCodec.encodeFitSpec(spec(listOf(legacy.copy(spoolCycles = -1)))) }
        for (bad in listOf(JSONObject.NULL, true, 0.0, -1, 2147483648L)) {
            val malformed = BridgeCodec.encodeFitSpec(spec(listOf(legacy)))
            malformed.getJSONArray("modules").getJSONObject(0).put("spool_cycles", bad)
            reject { BridgeCodec.decodeFitSpec(malformed) }
        }
    }
    @Test fun queryPreservesSourceChoicesSparsePositionsRawOverrideAndExactSeconds() {
        val value = details(); value.getJSONArray("modules").put(row(7).put("override_cycles", Int.MAX_VALUE))
        val decoded = ModuleSpoolCodec.decode(value.toString())
        assertEquals(listOf(2, 7), decoded.modules.map { it.index })
        assertNull(decoded.modules[0].overrideCycles)
        assertEquals(Int.MAX_VALUE, decoded.modules[1].overrideCycles)
        assertEquals(10, decoded.modules[1].currentCycles)
        assertEquals(21.23456789, decoded.modules[0].currentSeconds, 0.0)
        assertEquals(listOf(0, 5, 10), decoded.modules[0].choices)
        try { (decoded.modules as MutableList<ModuleSpoolRow>).clear(); fail("Mutable spool rows") } catch (_: UnsupportedOperationException) { }
        try { (decoded.modules[0].choices as MutableList<Int>).clear(); fail("Mutable source choices") } catch (_: UnsupportedOperationException) { }
        val zero = details(); zero.getJSONArray("modules").getJSONObject(0).put("override_cycles", 0)
        assertEquals(0, ModuleSpoolCodec.decode(zero.toString()).modules.single().overrideCycles)
        assertTrue(ModuleSpoolCodec.decode(details().put("modules", JSONArray()).toString()).modules.isEmpty())
    }
    @Test fun queryRejectsMalformedIdentityBoundsOrderChoicesAndUnavailableNumbers() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", true) }, { it.put("revision", 0) }, { it.put("extra", false) },
            { it.getJSONArray("modules").getJSONObject(0).put("override_cycles", -1) },
            { it.getJSONArray("modules").getJSONObject(0).put("current_cycles", 1.5) },
            { it.getJSONArray("modules").getJSONObject(0).put("maximum_cycles", 2147483648L) },
            { it.getJSONArray("modules").getJSONObject(0).put("minimum_cycles", 11) },
            { it.getJSONArray("modules").getJSONObject(0).put("minimum_cycles", 10) },
            { it.getJSONArray("modules").getJSONObject(0).put("maximum_cycles", 100001) },
            { it.getJSONArray("modules").getJSONObject(0).put("default_cycles", 9) },
            { it.getJSONArray("modules").getJSONObject(0).put("current_seconds", JSONObject.NULL) },
            { it.getJSONArray("modules").getJSONObject(0).put("default_seconds", -1) },
            { it.getJSONArray("modules").getJSONObject(0).put("item_id", 0) },
            { it.getJSONArray("modules").getJSONObject(0).put("object_key", "") },
            { it.getJSONArray("modules").getJSONObject(0).put("choices", JSONArray(listOf(0, 10, 5))) },
            { it.getJSONArray("modules").getJSONObject(0).put("choices", JSONArray(listOf(0, 5, 5, 10))) },
            { it.getJSONArray("modules").getJSONObject(0).put("choices", JSONArray(listOf(0, 5))) },
            { it.getJSONArray("modules").put(row()) },
            { it.getJSONArray("modules").put(row(7).put("object_key", "module-2")) })
        mutations.forEach { mutate -> val value = details(); mutate(value); reject { ModuleSpoolCodec.decode(value.toString()) } }
        reject { ModuleSpoolCodec.decode(details().toString().replaceFirst("{", "{\"version\":1,")) }
        reject { ModuleSpoolCodec.decode(details().toString().replace("21.23456789", "1e309")) }
    }
}
