package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProjectedFitContractTest {
    private fun wire(op: BridgeOperation, revisions: Map<String, Long> = mapOf("source" to 3L, "target" to 7L)) =
        JSONObject(BridgeCodec.encodeRequest(BridgeRequest("request", "session", op, revisions)))
    private fun rejects(block: () -> Unit) { try { block(); fail("Invalid projection request accepted") } catch (_: BridgeProtocolException) { } }
    @Test fun fiveAtomicOperationsHaveExactArgumentsAndBothEndpointRevisionsIncludingSelf() {
        val cases = listOf(
            Triple(BridgeOperation.AddProjectedFit("source", "target"), "add_projected_fit", emptySet<String>()),
            Triple(BridgeOperation.SetProjectedFitAmount("source", "target", 0), "set_projected_fit_amount", setOf("amount")),
            Triple(BridgeOperation.SetProjectedFitRange("source", "target", null), "set_projected_fit_range", setOf("range_m")),
            Triple(BridgeOperation.SetProjectedFitActive("source", "target", false), "set_projected_fit_active", setOf("active")),
            Triple(BridgeOperation.RemoveProjectedFit("source", "target"), "remove_projected_fit", emptySet<String>()),
        )
        for ((op, name, extra) in cases) {
            val value = wire(op)
            assertEquals(name, value.getString("operation"))
            assertEquals(setOf("source_id", "target_id") + extra, value.getJSONObject("arguments").keys().asSequence().toSet())
            assertEquals("source", value.getJSONObject("arguments").getString("source_id"))
            assertEquals("target", value.getJSONObject("arguments").getString("target_id"))
            assertEquals(3L, value.getJSONObject("expected_revisions").getLong("source"))
            assertEquals(7L, value.getJSONObject("expected_revisions").getLong("target"))
            assertEquals(op, op.snapshotArguments())
            rejects { wire(op, mapOf("target" to 7L)) }
        }
        assertTrue(wire(BridgeOperation.SetProjectedFitRange("source", "target", null)).getJSONObject("arguments").isNull("range_m"))
        assertEquals(0.0, wire(BridgeOperation.SetProjectedFitRange("source", "target", 0.0)).getJSONObject("arguments").getDouble("range_m"), 0.0)
        assertFalse(wire(BridgeOperation.SetProjectedFitActive("source", "target", false)).getJSONObject("arguments").getBoolean("active"))
        val self = wire(BridgeOperation.AddProjectedFit("target", "target"), mapOf("target" to 7L))
        assertEquals(setOf("target"), self.getJSONObject("expected_revisions").keys().asSequence().toSet())
        // Bridge accepts the source command's wider integer input; Python owns clamping.
        assertEquals(Int.MAX_VALUE, wire(BridgeOperation.SetProjectedFitAmount("source", "target", Int.MAX_VALUE)).getJSONObject("arguments").getInt("amount"))
        rejects { wire(BridgeOperation.SetProjectedFitAmount("source", "target", -1)) }
        for (range in listOf(-0.1, Double.NaN, Double.POSITIVE_INFINITY)) rejects {
            wire(BridgeOperation.SetProjectedFitRange("source", "target", range))
        }
    }
    @Test fun draftInputKeepsDefaultAndExplicitZeroDistinctAndRejectsOverflowWithoutClamping() {
        assertNull(ProjectedFitInputs.rangeM("  "))
        assertEquals(0.0, ProjectedFitInputs.rangeM("0")!!, 0.0)
        assertTrue(ProjectedFitInputs.sameRange(-0.0,0.0)); assertFalse(ProjectedFitInputs.sameRange(null,0.0))
        assertEquals(12500.0, ProjectedFitInputs.rangeM("12.5")!!, 0.0)
        assertEquals("", ProjectedFitInputs.rangeText(null)); assertEquals("0.0", ProjectedFitInputs.rangeText(0.0))
        assertEquals(0, ProjectedFitInputs.count("0")); assertEquals(20, ProjectedFitInputs.count("20"))
        for (text in listOf("-1", "1.5", "21", "2147483648", "", "NaN")) {
            try { ProjectedFitInputs.count(text); fail("Invalid count accepted: $text") } catch (_: IllegalArgumentException) { }
        }
        for (text in listOf("-1", "NaN", "Infinity", "1e308", "no")) {
            try { ProjectedFitInputs.rangeM(text); fail("Invalid range accepted: $text") } catch (_: IllegalArgumentException) { }
        }
    }
    @Test fun unavailableLoadingAndMissingFitCannotSubmitOrDiscardRetainedDraftImplicitly() {
        // Synthetic snapshots exercise the native guard only, never fitting calculations.
        val link=ProjectionSnapshot("source",null,true,3)
        val source=FitSnapshot("source",3,"Source","Rifter",emptyMap(),emptyList(),emptyMap(),emptyList(),emptyList(),emptyList())
        val target=source.copy(id="target",revision=7,name="Recipient",projections=listOf(link))
        var state: EngineState=EngineState.Ready(target)
        var calls=0
        val model=ProjectedFitModel(engineState={state},fits={listOf(source,(state as? EngineState.Ready)?.fit ?: target)},dispatch={ _,_,_ ->
            calls += 1; java.util.concurrent.CompletableFuture<BridgeResponse>() })
        val anchor=model.anchor(target,source)
        model.begin(anchor,ProjectedFitField.RANGE); model.change("12.5")
        val draft=model.draft
        val context=androidx.test.platform.app.InstrumentationRegistry.getInstrumentation().targetContext
        for (blocked in listOf(EngineState.Loading,EngineState.Empty(),EngineState.Failed("Unavailable"),
            EngineState.Ready(target,BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,"Restart")))) {
            state=blocked
            assertFalse(model.available); assertFalse(model.isCurrent(anchor))
            model.save(context); model.add(context,anchor); model.active(context,anchor); model.remove(context,anchor)
            model.openSource(context,anchor) { fail("Unavailable navigation accepted") }
            assertEquals(0,calls); assertSame(draft,model.draft)
        }
        state=EngineState.Ready(target)
        assertTrue(model.available); assertFalse(model.draftStale); assertEquals("12.5",model.draft!!.text)
        model.discard(); model.begin(anchor,ProjectedFitField.COUNT); model.change("03"); model.save(context)
        assertNull(model.draft); assertEquals(0,calls); assertTrue(model.message!!.contains("unchanged"))
        model.begin(anchor,ProjectedFitField.RANGE); model.change("   "); model.save(context)
        assertNull(model.draft); assertEquals(0,calls); assertTrue(model.message!!.contains("unchanged"))
        val atLimit=target.copy(revision=8,projections=listOf(link.copy(amount=20)))
        state=EngineState.Ready(atLimit)
        val capped=model.anchor(atLimit,source)
        assertFalse(model.canAdd(capped)); model.add(context,capped); assertEquals(0,calls)
    }

}
