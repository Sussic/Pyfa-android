package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import java.util.concurrent.CompletionException
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ModuleRahContractTest {
    private fun wire(operation: BridgeOperation) = JSONObject(BridgeCodec.encodeRequest(
        BridgeRequest("request", "session", operation, mapOf("fit" to 7L))))
    private fun components(em: Double = 126.0, thermal: Double = 427.0, kinetic: Double = 218.0, explosive: Double = 230.0) =
        JSONObject().put("em", em).put("thermal", thermal).put("kinetic", kinetic).put("explosive", explosive)
    private val context = OfflineContext("a".repeat(32), "c".repeat(64), 7)
    private fun row(index: Int = 2, mode: String = "fit", patternId: Int? = null) = JSONObject().put("index", index)
        .put("object_key", index.toString(16).padStart(32, '0')).put("item_id", 4403).put("name", "Reactive Armor Hardener")
        .put("mode", mode).put("builtin_id", patternId ?: JSONObject.NULL).put("named_id", JSONObject.NULL)
        .put("pattern_revision", if (patternId == null) JSONObject.NULL else 0)
        .put("pattern_name", if (patternId == null) JSONObject.NULL else "[NPC][Abyssal]All")
        .put("components", if (patternId == null) JSONObject.NULL else components())
    private fun details() = JSONObject().put("version", 2).put("context", context.json()).put("fit_id", "f".repeat(32)).put("revision", 7)
        .put("module_page", JSONObject().put("offset", 0).put("limit", 25).put("total", 3)
            .put("entries", JSONArray().put(row()).put(row(5, "disabled")).put(row(7, "builtin", -61))))
        .put("fit_pattern", JSONObject().put("name", "Fit pattern").put("available", true).put("unavailable_reason", JSONObject.NULL)
            .put("components", components(1.0,0.0,0.0,0.0)))
    private fun spec(modules: List<ModuleSpec>) = FitSpec("RAH", "Vexor", 5, false,
        DamagePattern(25.0,25.0,25.0,25.0), Security(SystemSecurity.HISEC, 0.0), modules, emptyList())
    private fun reject(block: () -> Unit) { try { block(); fail("Accepted invalid RAH contract") } catch (_: BridgeProtocolException) { } }
    @Test fun operationUsesExactModeAndOnlyBuiltinHasPatternId() {
        for ((mode, id) in listOf(RahMode.FIT to null, RahMode.DISABLED to null, RahMode.BUILTIN to -1)) {
            val value = wire(BridgeOperation.SetModuleRah("fit", 2, mode, id))
            assertEquals("set_module_rah", value.getString("operation"))
            val args = value.getJSONObject("arguments")
            assertEquals(setOf("fit_id", "position", "mode") + if (id == null) emptySet() else setOf("pattern_id"), args.keys().asSequence().toSet())
            assertEquals(mode.wire, args.getString("mode")); assertEquals(2, args.getInt("position"))
            if (id == null) assertFalse(args.has("pattern_id")) else assertEquals(id, args.getInt("pattern_id"))
            assertEquals(7, value.getJSONObject("expected_revisions").getInt("fit"))
        }
        listOf(BridgeOperation.SetModuleRah("fit", -1, RahMode.FIT), BridgeOperation.SetModuleRah("fit", 0, RahMode.FIT, -1),
            BridgeOperation.SetModuleRah("fit", 0, RahMode.DISABLED, -1), BridgeOperation.SetModuleRah("fit", 0, RahMode.BUILTIN),
            BridgeOperation.SetModuleRah("fit", 0, RahMode.BUILTIN, 0)).forEach { reject { wire(it) } }
    }
    @Test fun taggedDurableInputsPreserveLegacyOmissionExplicitUniformAndCallerSnapshot() {
        val inherited = ModuleSpec("Reactive Armor Hardener", ModuleState.ACTIVE)
        val rows = mutableListOf(inherited, inherited.copy(rahPattern = RahPattern.Disabled), inherited.copy(rahPattern = RahPattern.Builtin(-1)))
        val captured = (BridgeOperation.CreateFit(spec(rows)).snapshotArguments() as BridgeOperation.CreateFit).spec
        rows.clear()
        val value = BridgeCodec.encodeFitSpec(captured); val modules = value.getJSONArray("modules")
        assertFalse(modules.getJSONObject(0).has("rah_pattern"))
        assertEquals(setOf("mode"), modules.getJSONObject(1).getJSONObject("rah_pattern").keys().asSequence().toSet())
        assertEquals(-1, modules.getJSONObject(2).getJSONObject("rah_pattern").getInt("pattern_id"))
        assertEquals(captured, BridgeCodec.decodeFitSpec(value))
        try { (captured.modules as MutableList<ModuleSpec>).clear(); fail("Mutable module snapshot") } catch (_: UnsupportedOperationException) { }
        val bad = listOf(JSONObject.NULL, JSONObject(), JSONObject().put("mode","fit"),
            JSONObject().put("mode","disabled").put("pattern_id",JSONObject.NULL),
            JSONObject().put("mode","builtin"), JSONObject().put("mode","builtin").put("pattern_id",-1.0),
            JSONObject().put("mode","builtin").put("pattern_id",0), JSONObject().put("mode","custom"))
        bad.forEach { input ->
            val malformed = BridgeCodec.encodeFitSpec(spec(listOf(inherited)))
            malformed.getJSONArray("modules").getJSONObject(0).put("rah_pattern",input)
            reject { BridgeCodec.decodeFitSpec(malformed) }
        }
        reject { BridgeCodec.encodeFitSpec(spec(listOf(inherited.copy(rahPattern = RahPattern.Builtin(1))))) }
    }
    @Test fun queryRetainsRelativeWeightsSourceOrderModesAndSparseIdentities() {
        val decoded = ModuleRahCodec.decode(details().toString())
        assertEquals(context, decoded.context)
        assertEquals(listOf(2, 5, 7), decoded.modules.map { it.index })
        assertEquals(listOf(RahMode.FIT, RahMode.DISABLED, RahMode.BUILTIN), decoded.modules.map { it.mode })
        assertEquals(RahComponents(126.0,427.0,218.0,230.0), decoded.modules[2].components)
        assertEquals(RahComponents(1.0,0.0,0.0,0.0), decoded.fitPattern.components)
        assertNull(decoded.modules[0].patternId); assertEquals(-61, decoded.modules[2].patternId)
        val empty = details(); empty.getJSONObject("module_page").put("total", 0).put("entries", JSONArray())
        assertTrue(ModuleRahCodec.decode(empty.toString()).modules.isEmpty())
        try { (decoded.modules as MutableList<ModuleRahRow>).clear(); fail("Mutable module rows") } catch (_: UnsupportedOperationException) { }
    }
    @Test fun malformedQueryModesNumbersAndReferencesFailClosed() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version",true) }, { it.put("version",1) }, { it.put("revision",0) }, { it.put("extra",false) },
            { it.getJSONObject("fit_pattern").put("name",JSONObject.NULL) },
            { it.getJSONObject("fit_pattern").put("components",components(0.0,0.0,0.0,0.0)) },
            { it.getJSONObject("module_page").put("limit",26) }, { it.getJSONObject("module_page").put("total",4) },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(0).put("mode","custom") },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(0).put("object_key","legacy-label") },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(2).put("builtin_id",-61.0) },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(2).getJSONObject("components").put("em",true) },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(2).getJSONObject("components").put("em",-1) },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(0).put("builtin_id",-1) },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(1).put("builtin_id",-1) },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(2).put("builtin_id",JSONObject.NULL) },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(2).put("builtin_id",-999) },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(2).put("index",2) },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(2).put("object_key",2.toString(16).padStart(32,'0')) },
            { it.getJSONObject("module_page").getJSONArray("entries").getJSONObject(0).put("item_id",0) })
        mutations.forEach { mutate -> val value = details(); mutate(value); reject { ModuleRahCodec.decode(OfflineFeatureCodec.json(value)) } }
        reject { ModuleRahCodec.decode(details().toString().replaceFirst("{", "{\"version\":2,")) }
        reject { ModuleRahCodec.decode(details().toString().replace("126", "1e309")) }
        // Legacy details v1 cannot masquerade as the bounded native v2 protocol.
        reject { ModuleRahCodec.decode(JSONObject().put("version",1).put("fit_id","fit").put("revision",7)
            .put("patterns",JSONArray()).put("modules",JSONArray()).put("fit_pattern",JSONObject()).toString()) }
    }
    @Test fun onlyKnownCustomQueryFailureGetsTheFixedUnsupportedMessage() {
        assertTrue(isUnsupportedRahFailure(CompletionException(IllegalArgumentException("ValueError: $UNSUPPORTED_RAH_MESSAGE"))))
        assertTrue(isUnsupportedRahFailure(UnsupportedRahPatternException()))
        assertEquals(UNSUPPORTED_RAH_MESSAGE, UnsupportedRahPatternException().message)
        assertFalse(isUnsupportedRahFailure(IllegalStateException("Transport disconnected")))
        assertFalse(isUnsupportedRahFailure(IllegalArgumentException("Unknown built-in reactive armor pattern")))
        assertFalse(isUnsupportedRahFailure(IllegalArgumentException("Custom reactive armor")))
    }
}
