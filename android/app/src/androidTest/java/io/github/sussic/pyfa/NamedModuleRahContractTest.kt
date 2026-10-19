package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic strict-wire cases only. Real Python wire consumption is a separate acceptance gate. */
@RunWith(AndroidJUnit4::class)
class NamedModuleRahContractTest {
    private val fit = "f".repeat(32)
    private val key = "e".repeat(32)
    private val named = "damage:" + "d".repeat(32)
    private val context = OfflineContext("a".repeat(32), "b".repeat(64), 7)
    private fun components() = JSONObject().put("em", 1).put("thermal", 0.0).put("kinetic", -0.0).put("explosive", 0)
    private fun descriptor(id: String = named) = JSONObject().put("index", 2).put("object_key", key).put("item_id", 4403)
        .put("name", "Reactive Armor Hardener").put("mode", "named").put("builtin_id", JSONObject.NULL).put("named_id", id)
        .put("pattern_revision", 3).put("pattern_name", if (id == SELECTED_AMMO_PATTERN_ID) "Selected Ammo" else "Local custom").put("components", components())
    private fun args() = JSONObject().put("fit_revision", 9).put("object_key", key).put("position", 2)
    private fun request(operation: String = "module_options", selected: String? = null) = OfflineDamageRequest("named-rah-test", context, fit,
        OfflineDamageView(limit = 20, selectedPatternId = selected), operation, OfflineFeatureCodec.json(args()))
    private fun metadata(id: String = named, zero: Boolean = false) = JSONObject().put("pattern_id", id)
        .put("kind", if (id == SELECTED_AMMO_PATTERN_ID) "selected_ammo" else "custom")
        .put("name", if (id == SELECTED_AMMO_PATTERN_ID) "Selected Ammo" else if (zero) "Zero unassigned" else "Local custom")
        .put("revision", 3).put("bound_fit_count", 0).put("bound_module_count", if (zero) 0 else 1)
        .put("affected_fit_count", if (zero) 0 else 1).put("assignable", !zero).put("unassignable_reason", if (zero) "zero_total" else JSONObject.NULL)
    private fun page(offset: Long = 0, total: Int = 0, entries: JSONArray = JSONArray()) = JSONObject().put("offset", offset).put("limit", 50).put("total", total).put("entries", entries)
    private fun holder() = JSONObject().put("fit_id", fit).put("fit_name", "Fixture").put("fit_revision", 9)
        .put("object_key", key).put("position", 2).put("item_id", 4403).put("name", "Reactive Armor Hardener")
    private fun response(input: OfflineDamageRequest = request(), id: String = named): JSONObject {
        val entries = JSONArray().put(metadata(id)).put(metadata("damage:" + "c".repeat(32), true))
        val state = JSONObject().put("version", 3).put("context", context.json()).put("fit_id", fit).put("fit_revision", 9)
            .put("selection", JSONObject().put("kind", "anonymous").put("pattern_id", JSONObject.NULL).put("pattern_revision", JSONObject.NULL).put("binding_revision", JSONObject.NULL))
            .put("page", JSONObject().put("query", input.view.query).put("offset", 0).put("limit", 20).put("total", 2).put("entries", entries))
            .put("history", JSONObject().put("undo_count", 0).put("redo_count", 0).put("limit", 100).put("undo_label", JSONObject.NULL).put("redo_label", JSONObject.NULL))
            .put("item", JSONObject.NULL).put("module", descriptor(id)).put("detail", JSONObject.NULL)
        if (input.view.selectedPatternId != null) state.put("detail", metadata(id)
            .put("values", JSONObject().put("emAmount", 1).put("thermalAmount", 0.0).put("kineticAmount", -0.0).put("explosiveAmount", 0))
            .put("percentages", JSONObject().put("emAmount", 100.0).put("thermalAmount", 0.0).put("kineticAmount", -0.0).put("explosiveAmount", 0.0))
            .put("bound_fits", page(input.view.boundOffset)).put("bound_modules", page(input.view.moduleOffset, 1,
                if (input.view.moduleOffset == 0L) JSONArray().put(holder()) else JSONArray())))
        return JSONObject().put("version", 3).put("request_id", input.requestId).put("ok", true).put("committed", false)
            .put("reopen_required", false).put("state", state).put("bridge", JSONObject.NULL).put("error", JSONObject.NULL)
    }
    private fun rejects(block: () -> Unit) { try { block(); fail("Accepted invalid named RAH wire") } catch (_: BridgeProtocolException) { } }
    private fun decode(row: JSONObject, input: OfflineDamageRequest = request()) = OfflineDamageCodec.response(OfflineFeatureCodec.json(row), input)
    @Test fun moduleOptionsRetainsNamedIdentityAndAllowsUnrelatedZeroRow() {
        val value = decode(response()).state!!
        assertTrue(damageReadLike("module_options")); assertNull(value.item)
        assertEquals("anonymous", value.selection.kind)
        assertEquals(named, value.module!!.namedId); assertEquals(3L, value.module.patternRevision)
        assertTrue(value.entries[0].assignable); assertFalse(value.entries[1].assignable)
        assertEquals(1L, value.entries[0].boundModuleCount); assertEquals(1L, value.entries[0].affectedFitCount)
        assertNull(decode(response()).bridge)
        val ammo = decode(response(id = SELECTED_AMMO_PATTERN_ID)).state!!
        assertEquals(SELECTED_AMMO_PATTERN_ID, ammo.module!!.namedId); assertFalse(ammo.entries.first().duplicable)
    }
    @Test fun namedRequestsRequireExactFitLogicalKeyPositionAndCurrentPatternRevision() {
        for (selection in listOf(JSONObject().put("mode", "fit"), JSONObject().put("mode", "disabled"),
            JSONObject().put("mode", "builtin").put("pattern_id", -1), JSONObject().put("mode", "named").put("pattern_id", named).put("revision", 3),
            JSONObject().put("mode", "named").put("pattern_id", SELECTED_AMMO_PATTERN_ID).put("revision", 4))) {
            val input = request("set_module").copy(argumentsJson = OfflineFeatureCodec.json(args().put("selection", selection)))
            val wire = OfflineFeatureCodec.parse(input.json())
            assertEquals(3L, OfflineFeatureCodec.integer(wire.get("version")))
            assertEquals(setOf("fit_revision", "object_key", "position", "selection"), wire.getJSONObject("arguments").keys().asSequence().toSet())
            assertFalse(wire.getJSONObject("arguments").has("components"))
        }
        for (selection in listOf(JSONObject().put("mode", "named").put("pattern_id", named),
            JSONObject().put("mode", "named").put("pattern_id", named).put("revision", 0),
            JSONObject().put("mode", "named").put("pattern_id", "damage:builtin:-1").put("revision", 1),
            JSONObject().put("mode", "named").put("pattern_id", named).put("revision", 3).put("components", components()),
            JSONObject().put("mode", "fit").put("pattern_id", JSONObject.NULL)))
            rejects { request("set_module").copy(argumentsJson = OfflineFeatureCodec.json(args().put("selection", selection))).json() }
        rejects { request().copy(argumentsJson = OfflineFeatureCodec.json(args().put("object_key", "same item"))).json() }
        rejects { request().copy(argumentsJson = OfflineFeatureCodec.json(args().put("position", 2.0))).json() }
        rejects { request().copy(view = request().view.copy(moduleOffset = -1)).json() }
    }
    @Test fun independentHolderPagesAndDistinctUnionAreStrict() {
        val input = request(selected = named)
        val value = decode(response(input), input).state!!.detail!!
        assertEquals(0L, value.entry.boundFitCount); assertEquals(1, value.boundModules.size); assertTrue(value.boundFits.isEmpty())
        val beyond = input.copy(view = input.view.copy(moduleOffset = Long.MAX_VALUE, boundOffset = Long.MAX_VALUE))
        assertTrue(decode(response(beyond), beyond).state!!.detail!!.boundModules.isEmpty())
        for (mutation in listOf<(JSONObject) -> Unit>(
            { it.getJSONObject("state").getJSONObject("detail").getJSONObject("bound_modules").put("limit", 51) },
            { it.getJSONObject("state").getJSONObject("detail").getJSONObject("bound_modules").put("entries", JSONArray()) },
            { it.getJSONObject("state").getJSONObject("detail").put("affected_fit_count", 2) },
            { it.getJSONObject("state").getJSONObject("module").put("pattern_revision", 2) },
            { it.getJSONObject("state").getJSONObject("module").put("object_key", "0".repeat(32)) },
            { it.getJSONObject("state").getJSONObject("module").put("index", 3) })) {
            val row = response(input); mutation(row); rejects { decode(row, input) }
        }
        val overlap = response(input); val detail = overlap.getJSONObject("state").getJSONObject("detail")
        detail.put("bound_fit_count", 1).put("bound_fits", page(total = 1, entries = JSONArray().put(
            JSONObject().put("fit_id", fit).put("name", "Fixture").put("revision", 9))))
        // The selected fit must also report the incoming binding, not merely a holder row.
        rejects { decode(overlap, input) }
    }
    @Test fun deleteRequiresBothHolderCountsAndDistinctFitUnion() {
        val fields = JSONObject().put("pattern_id", named).put("revision", 3).put("bound_fit_count", 1).put("bound_module_count", 2).put("affected_fit_count", 1)
        val input = request().copy(operation = "delete", argumentsJson = OfflineFeatureCodec.json(fields))
        input.json()
        for (field in listOf("bound_fit_count", "bound_module_count", "affected_fit_count")) {
            val missing = JSONObject(fields.toString()); missing.remove(field)
            rejects { input.copy(argumentsJson = missing.toString()).json() }
        }
        rejects { input.copy(argumentsJson = JSONObject(fields.toString()).put("affected_fit_count", 4).toString()).json() }
        rejects { input.copy(argumentsJson = JSONObject(fields.toString()).put("pattern_id", SELECTED_AMMO_PATTERN_ID).toString()).json() }
    }
    @Test fun trustedTagsDoNotMakeExternalFitSpecsOrLegacyBridgeAcceptNamedInputs() {
        val tag = JSONObject().put("mode", "named").put("pattern_id", named)
        assertEquals(RahPattern.Named(named), ModuleRahCodec.pattern(tag, trustedNative = true))
        rejects { ModuleRahCodec.pattern(tag) }; rejects { ModuleRahCodec.encodePattern(RahPattern.Named(named)) }
        val spec = FitSpec("External", "Vexor", 5, false, DamagePattern(1.0,0.0,0.0,0.0), Security(SystemSecurity.HISEC,0.0),
            listOf(ModuleSpec("Reactive Armor Hardener",ModuleState.ACTIVE,rahPattern=RahPattern.Named(named))),emptyList())
        rejects { BridgeCodec.encodeFitSpec(spec) }
        rejects { BridgeCodec.encodeRequest(BridgeRequest("request", "session", BridgeOperation.SetModuleRah(fit,2,RahMode.NAMED),mapOf(fit to 9L))) }
        rejects { ModuleRahCodec.pattern(JSONObject(tag.toString()).put("revision",3), trustedNative = true) }
    }
    @Test fun defensiveZeroPreviewDoesNotWeakenPositiveComponentsOrAssignedNamedRows() {
        val root = JSONObject().put("version",2).put("context",context.json()).put("fit_id",fit).put("revision",9)
            .put("module_page",JSONObject().put("offset",0).put("limit",25).put("total",1).put("entries",JSONArray().put(descriptor())))
            .put("fit_pattern",JSONObject().put("name","Fit pattern").put("available",false).put("unavailable_reason","zero_total").put("components",JSONObject.NULL))
        assertFalse(ModuleRahCodec.decode(root.toString()).fitPattern.available)
        assertEquals(RahMode.NAMED,ModuleRahCodec.decode(root.toString()).modules.single().mode)
        val zero = JSONObject().put("em",0.0).put("thermal",0).put("kinetic",0).put("explosive",0)
        rejects { ModuleRahCodec.components(zero) }
        root.getJSONObject("module_page").getJSONArray("entries").getJSONObject(0).put("components",zero)
        rejects { ModuleRahCodec.decode(root.toString()) }
        val assignedZero = response(); assignedZero.getJSONObject("state").getJSONObject("page").getJSONArray("entries").getJSONObject(1).put("bound_module_count",1)
        rejects { decode(assignedZero) }
    }
    @Test fun publicationRejectsOlderGenerationAndDifferentSessionEvenAfterEditorCloses() {
        assertTrue(mayPublishDamageContext(context,context.copy(generation=8)))
        assertFalse(mayPublishDamageContext(context.copy(generation=9),context.copy(generation=8)))
        assertFalse(mayPublishDamageContext(context,context.copy(sessionId="c".repeat(32))))
        assertFalse(mayPublishDamageContext(context,context.copy(datasetSha256="c".repeat(64))))
    }
}
