package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CommandFitContractTest {
    private fun wire(op: BridgeOperation, revisions: Map<String,Long> = mapOf("source" to 3L,"target" to 7L)) =
        JSONObject(BridgeCodec.encodeRequest(BridgeRequest("request","session",op,revisions)))
    private fun rejects(block: () -> Unit) { try { block(); fail("Invalid command request accepted") } catch (_: BridgeProtocolException) { } }
    @Test fun exactSingleLinkOperationsRequireBothEndpointRevisionsAndPermitSelf() {
        val cases=listOf(
            Triple(BridgeOperation.AddCommandFit("source","target"),"add_command_fit",emptySet<String>()),
            Triple(BridgeOperation.SetCommandFitActive("source","target",false),"set_command_fit_active",setOf("active")),
            Triple(BridgeOperation.RemoveCommandFit("source","target"),"remove_command_fit",emptySet<String>()))
        for ((op,name,extra) in cases) {
            val result=wire(op)
            assertEquals(name,result.getString("operation"))
            assertEquals(setOf("source_id","target_id")+extra,result.getJSONObject("arguments").keys().asSequence().toSet())
            assertEquals("source",result.getJSONObject("arguments").getString("source_id"))
            assertEquals("target",result.getJSONObject("arguments").getString("target_id"))
            assertEquals(3L,result.getJSONObject("expected_revisions").getLong("source"))
            assertEquals(7L,result.getJSONObject("expected_revisions").getLong("target"))
            assertEquals(op,op.snapshotArguments())
            rejects { wire(op,mapOf("target" to 7L)) }
            rejects { wire(op,mapOf("source" to 3L,"target" to 7L,"other" to 1L)) }
        }
        assertEquals(false,wire(cases[1].first).getJSONObject("arguments").get("active"))
        val self=wire(BridgeOperation.AddCommandFit("target","target"),mapOf("target" to 7L))
        assertEquals(setOf("target"),self.getJSONObject("expected_revisions").keys().asSequence().toSet())
        rejects { wire(BridgeOperation.AddCommandFit("","target")) }
    }
    @Test fun staleMissingUnavailableDuplicateAndUnchangedStateGuardsNeverDispatch() {
        // Native state guards only; these synthetic snapshots are not numerical EOS evidence.
        val source=FitSnapshot("source",3,"Source","Vulture",emptyMap(),emptyList(),emptyMap(),emptyList(),emptyList(),emptyList())
        val target=source.copy(id="target",revision=7,name="Recipient",ship="Vexor",commands=listOf(CommandSnapshot("source",true)))
        var state: EngineState=EngineState.Ready(target)
        var fits=listOf(source,target)
        var calls=0
        val model=CommandFitModel(engineState={state},fits={fits},dispatch={ _,_,_ -> calls++; CompletableFuture<BridgeResponse>() })
        val anchor=model.anchor(target,source)
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        assertFalse(model.canAdd(anchor)); model.add(context,anchor); model.setActive(context,anchor,true); assertEquals(0,calls)
        for (stale in listOf(anchor.copy(sourceRevision=2),anchor.copy(targetRevision=6),anchor.copy(sourceId="missing"),
            anchor.copy(targetId="other"),anchor.copy(link=null),anchor.copy(link=CommandSnapshot("source",false)))) {
            assertFalse(model.isCurrent(stale)); model.add(context,stale); model.remove(context,stale); model.setActive(context,stale,false)
        }
        for (blocked in listOf(EngineState.Loading,EngineState.Empty(),EngineState.Failed("Unavailable"),
            EngineState.Ready(target,BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,"Restart")))) {
            state=blocked; assertFalse(model.available)
            model.add(context,anchor); model.remove(context,anchor); model.setActive(context,anchor,false)
            model.openSource(context,anchor) { fail("Blocked navigation accepted") }
        }
        state=EngineState.Ready(target); fits=listOf(target)
        assertFalse(model.isCurrent(anchor)); model.remove(context,anchor)
        fits=listOf(source); assertFalse(model.isCurrent(anchor)); model.remove(context,anchor)
        assertEquals(0,calls)
        fits=listOf(source,target.copy(revision=8)); assertFalse(model.isCurrent(anchor))
        fits=listOf(source,target); assertTrue(model.canEdit(anchor))
    }
}
