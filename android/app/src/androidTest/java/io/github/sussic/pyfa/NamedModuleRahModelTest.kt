package io.github.sussic.pyfa

import androidx.lifecycle.ViewModelStore
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Held synthetic futures cover ownership; no EOS, native device or numerical proof is implied. */
@RunWith(AndroidJUnit4::class)
class NamedModuleRahModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private val id = "f".repeat(32)
    private val key = "e".repeat(32)
    private val named = "damage:" + "d".repeat(32)
    private inner class Harness {
        var current = OfflineContext("a".repeat(32), "b".repeat(64), 7)
        var fit: Pair<String,Long>? = id to 9L
        val detailInputs = mutableListOf<Triple<String,Long,Int>>()
        val detailPending = mutableListOf<CompletableFuture<ModuleRahDetails>>()
        val inputs = mutableListOf<OfflineDamageRequest>()
        val pending = mutableListOf<CompletableFuture<OfflineDamageResponse>>()
        val row = ModuleRahRow(2,key,4403,"Reactive Armor Hardener",RahMode.FIT,null)
        val entry = OfflineDamageEntry(named,"custom","Local custom",3,0,true,null)
        val zero = OfflineDamageEntry("damage:"+"c".repeat(32),"custom","Zero unassigned",1,0,false,"zero_total")
        val model = ModuleRahModel(featureContext={current},activeFit={fit},loadDetails={_,fitId,offset,limit ->
            detailInputs.add(Triple(fitId,offset,limit));CompletableFuture<ModuleRahDetails>().also(detailPending::add)
        },request={_,input -> inputs.add(input);CompletableFuture<OfflineDamageResponse>().also(pending::add)})
        fun details(index: Int = detailInputs.lastIndex, selected: ModuleRahRow = row) = ModuleRahDetails(detailInputs[index].first,
            checkNotNull(fit).second,current,detailInputs[index].second,detailInputs[index].third,1,listOf(selected),
            RahFitPattern("Fit pattern",true,null,RahComponents(1.0,0.0,0.0,0.0)))
        fun load() { model.open(); model.load(context,id,9) }
        fun completeDetails(index: Int = detailInputs.lastIndex, value: ModuleRahDetails = details(index)) { detailPending[index].complete(value) }
        fun choices(index: Int = inputs.lastIndex, selected: ModuleRahRow = row) = OfflineDamageState(current,id,checkNotNull(fit).second,
            OfflineDamageSelection("anonymous",null,null,null),inputs[index].view,2,listOf(entry,zero),null,OfflineHistory(0,0,100,null,null),module=selected)
        fun complete(index: Int = inputs.lastIndex, value: OfflineDamageState = choices(index), committed: Boolean = false) {
            pending[index].complete(OfflineDamageResponse(inputs[index].requestId,true,committed,false,value,null,null))
        }
        fun ready() { main { load() };main { completeDetails() } }
        fun choose() { main { model.chooseModule(context,model.currentDetails!!,row) };main { complete() } }
    }
    @Test fun closeReopenSameFitRevisionCannotAdoptOldLoadOrClearNewLoading() {
        val h=Harness();val m=h.model
        main { h.load();m.close();h.load() }
        main { h.completeDetails(0) }
        assertTrue(m.loading);assertNull(m.details);assertNull(m.error)
        main { h.completeDetails(1) }
        assertFalse(m.loading);assertEquals(id,m.currentDetails!!.fitId)
        assertEquals(Triple(id,0L,25),h.detailInputs.last())
    }
    @Test fun contextAndFitRevisionChangeRejectsOldFailureBeforeAnyFlagOrError() {
        val h=Harness();val m=h.model
        main { h.load();h.current=h.current.copy(generation=8);h.fit=id to 10L;m.load(context,id,10) }
        main { h.detailPending[0].completeExceptionally(IllegalStateException("old")) }
        assertTrue(m.loading);assertNull(m.error)
        main { h.completeDetails(1) };assertEquals(10L,m.currentDetails!!.revision)
    }
    @Test fun newQueryAndPageOwnTheirBoundedOptionsAndUnavailableZeroDoesNotBlockNamedChoice() {
        val h=Harness();h.ready();val m=h.model
        main { m.chooseModule(context,m.currentDetails!!,h.row);m.search(context,"First");m.search(context,"Newest") }
        assertEquals(3,h.inputs.size);assertTrue(m.loading)
        main { h.complete(0);h.pending[1].completeExceptionally(IllegalStateException("obsolete")) }
        assertTrue(m.loading);assertNull(m.error);assertNull(m.currentOptions)
        main { h.complete(2) }
        assertEquals("Newest",m.currentOptions!!.view.query);assertFalse(m.loading)
        assertEquals(20,h.inputs.last().view.limit);assertEquals("module_options",h.inputs.last().operation)
        val before=m.currentDetails!!
        main { m.setPattern(context,before,h.row,h.zero) };assertEquals(3,h.inputs.size)
        main { m.setPattern(context,before,h.row,h.entry) }
        val selection=OfflineFeatureCodec.parse(h.inputs.last().argumentsJson).getJSONObject("selection")
        assertEquals("named",selection.getString("mode"));assertEquals(named,selection.getString("pattern_id"))
        assertEquals(3L,OfflineFeatureCodec.integer(selection.get("revision")));assertFalse(selection.has("components"))
    }
    @Test fun acceptedSaveAfterCloseCannotReopenOrMutateNewEditorButAuthorityCanAdvance() {
        val h=Harness();h.ready();h.choose();val m=h.model
        main { m.setPattern(context,m.currentDetails!!,h.row,h.entry);m.close();h.current=h.current.copy(generation=8);h.fit=id to 10L;m.open();m.load(context,id,10) }
        val saved=h.row.copy(mode=RahMode.NAMED,namedId=named,patternRevision=3,patternName="Local custom",components=RahComponents(1.0,0.0,0.0,0.0))
        main { h.complete(1,h.choices(1,saved),true) }
        assertTrue(m.loading);assertFalse(m.editing);assertNull(m.details);assertNull(m.message);assertNull(m.selectedKey)
        main { h.completeDetails(value=h.details(selected=saved)) }
        assertEquals(named,m.currentDetails!!.modules.single().namedId);assertNull(m.message)
    }
    @Test fun disposeAndWrongRequestIdCannotPublishOrClearCurrentFlags() {
        val h=Harness();h.ready();val m=h.model
        main { m.chooseModule(context,m.currentDetails!!,h.row) }
        main { h.pending[0].complete(OfflineDamageResponse("another-request",true,false,false,h.choices(0),null,null)) }
        assertTrue(m.loading);assertNull(m.currentOptions)
        main { m.search(context,"new");val store=ViewModelStore();store.put("rah",m);store.clear() }
        main { h.complete(1) }
        assertFalse(m.loading);assertNull(m.details);assertNull(m.error);assertNull(m.currentOptions)
    }
    @Test fun uncertainMutationRequiresReopenAndCannotBeAutomaticallyReapplied() {
        val h=Harness();h.ready();h.choose();val m=h.model
        main { m.setPattern(context,m.currentDetails!!,h.row,h.entry) }
        main { h.pending.last().complete(OfflineDamageResponse(h.inputs.last().requestId,false,null,true,null,null,OfflineFeatureError("reopen_required","Restart required"))) }
        assertTrue(m.reopenRequired);assertFalse(m.available);assertFalse(m.editing)
        val count=h.inputs.size
        main { m.load(context,id,9,true);m.set(context,m.details!!,h.row,RahMode.DISABLED) }
        assertEquals(count,h.inputs.size)
    }
}
