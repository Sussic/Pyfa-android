package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic immutable details isolate selection ownership and async races; they are not an EOS oracle. */
@RunWith(AndroidJUnit4::class)
class ProjectedFighterSelectionModelTest {
    private val instrumentation get()=InstrumentationRegistry.getInstrumentation()
    private val context get()=instrumentation.targetContext
    private fun ui(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private fun fit(id: String="fit",revision: Long=7)=FitSnapshot(id,revision,"Recipient","Rifter",emptyMap(),emptyList(),emptyMap(),emptyList(),emptyList(),emptyList())
    private fun row(index: Int)=ProjectedFighterRow(index,index.toString(16).padStart(32,'0'),if(index in listOf(0,3,27))100 else 200+index,
        "Incoming $index",index%4,3,index%2==0,if(index%2==0)null else 0.0,true,null)
    private fun result(d: ProjectedFighterDetails,main: Int=3,indices: List<Int> = listOf(0,3,5,27)): FighterSimilarSelection {
        fun id(row: ProjectedFighterRow)=FighterSelectionIdentity(row.index,row.objectKey,row.itemId)
        return FighterSimilarSelection(d.fitId,d.revision,id(d.squadrons[main]),indices.map { id(d.squadrons[it]) })
    }
    private inner class Harness {
        var state: EngineState=EngineState.Ready(fit())
        var details=ProjectedFighterDetails("fit",7,false,(0..29).map(::row))
        val reads=mutableListOf<CompletableFuture<FighterSimilarSelection>>()
        var writes=0
        val model=ProjectedFighterModel(engineState={state},read={_,_,_-> CompletableFuture.completedFuture(details)},
            readOptions={_,id,revision,row-> CompletableFuture.completedFuture(ProjectedFighterOptions(id,revision,row.index,row.objectKey,row.itemId,
                listOf(FighterAbility(6435,"Web",true)),emptyList()))},
            similarQuery={_,id,revision,main-> assertEquals(details.fitId,id); assertEquals(details.revision,revision); assertSame(details.squadrons[main.index],main)
                CompletableFuture<FighterSimilarSelection>().also(reads::add)},
            dispatch={_,_,_-> writes++; CompletableFuture()})
        fun load() { ui { model.load(context,(state as EngineState.Ready).fit) } }
        fun start() { ui { model.selectSimilar(context,details,details.squadrons[3]) } }
    }

    @Test fun sameTypeUsesAllPagesReplacesSelectionAndEstablishesMainWithoutQueryOrWrite() {
        val h=Harness();h.load();val m=h.model;val d=h.details
        ui { m.toggleBulk(d.squadrons[5]); m.showPage(1); m.selectSameType(d,d.squadrons[3]) }
        assertEquals(listOf(0,3,27),m.bulkSelection!!.rows.map { it.index }); assertEquals(d.squadrons[3].objectKey,m.bulkMainKey)
        assertSame(d.squadrons[27],m.bulkSelection!!.rows.last()); assertEquals(1,m.page)
        assertTrue(h.reads.isEmpty());assertEquals(0,h.writes)
        val captured=m.bulkSelection
        ui { m.selectSameType(d.copy(),d.squadrons[3]); m.selectSameType(d,d.squadrons[3].copy()) }
        assertSame(captured,m.bulkSelection)
        ui { m.beginBulkRange(captured!!); m.changeBulkRange("1.25"); m.selectSameType(d,d.squadrons[5]); m.selectSimilar(context,d,d.squadrons[3]) }
        assertSame(captured,m.bulkSelection);assertEquals("1.25",m.bulkDraft!!.text);assertTrue(h.reads.isEmpty())
    }

    @Test fun validSimilarSelectionKeepsServerOrderAndMissingAbilitiesAreNotLocallyInferred() {
        val h=Harness();h.load();h.start()
        ui { h.model.selectSimilar(context,h.details,h.details.squadrons[0]) };assertEquals(1,h.reads.size)
        ui { h.reads.single().complete(result(h.details)) }
        assertFalse(h.model.selectingSimilar)
        assertEquals(listOf(0,3,5,27),h.model.bulkSelection!!.rows.map { it.index });assertEquals(h.details.squadrons[3].objectKey,h.model.bulkMainKey)
        assertNull(h.model.bulkMainOptions);assertEquals(0,h.writes)
        ui { h.model.selectBulkMain(context,h.details.squadrons[3]) }
        assertEquals(3,h.model.bulkMainOptions!!.index);assertEquals(1,h.reads.size)
        val selected=h.model.bulkSelection!!
        ui { h.model.bulkAbility(context,selected,h.model.anchor(h.details.squadrons[3])!!,h.model.bulkMainOptions!!,h.model.bulkMainOptions!!.abilities.first()) }
        assertEquals(1,h.writes) // Downstream operation remains the existing atomic command.
    }

    @Test fun manualChangesDraftsReloadNavigationAndEditsInvalidateLateResultsWithoutOpeningAnotherQuerySlot() {
        val changes: List<(Harness)->Unit> = listOf(
            { h-> h.model.toggleBulk(h.details.squadrons[5]) },
            { h-> h.model.selectBulkPage() },
            { h-> h.model.clearBulk() },
            { h-> h.model.selectSameType(h.details,h.details.squadrons[0]) },
            { h-> h.model.selectBulkMain(context,h.details.squadrons[0]) },
            { h-> h.model.select(context,h.details.squadrons[5]) },
            { h-> h.model.beginRange(h.model.anchor(h.details.squadrons[0])!!) },
            { h-> h.model.beginAmount(h.model.anchor(h.details.squadrons[0])!!) },
            { h-> h.model.beginBulkRange(h.model.bulkSelection!!) },
            { h-> h.model.leaveEditor() },
            { h-> h.model.load(context,fit(),true) },
            { h-> h.model.bulkActive(context,h.model.bulkSelection!!,false) })
        for (change in changes) {
            val h=Harness();h.load();ui { h.model.toggleBulk(h.details.squadrons[0]) };h.start()
            ui { change(h) };val selection=h.model.bulkSelection;val draft=h.model.draft;val bulkDraft=h.model.bulkDraft;val main=h.model.bulkMainKey
            ui { h.model.selectSimilar(context,h.details,h.details.squadrons[3]) };assertEquals(1,h.reads.size);assertTrue(h.model.selectingSimilar)
            ui { h.reads.single().complete(result(h.details)) }
            assertFalse(h.model.selectingSimilar);assertSame(selection,h.model.bulkSelection);assertSame(draft,h.model.draft)
            assertSame(bulkDraft,h.model.bulkDraft);assertEquals(main,h.model.bulkMainKey)
        }
    }

    @Test fun failuresMalformedResponsesCrossFitAndRevisionChangesPreserveCapturedStateAndAllowRetry() {
        val h=Harness();h.load();ui { h.model.selectSameType(h.details,h.details.squadrons[0]) }
        val retained=h.model.bulkSelection;val main=h.model.bulkMainKey
        h.start();ui { h.reads.last().completeExceptionally(IllegalArgumentException("Python ValueError: Select at most 1024 squadrons per edit")) }
        assertSame(retained,h.model.bulkSelection);assertEquals(main,h.model.bulkMainKey);assertTrue(h.model.error!!.contains("1024"));assertFalse(h.model.selectingSimilar)
        h.start();ui { h.reads.last().complete(result(h.details).copy(main=FighterSelectionIdentity(3,"replaced",100))) }
        assertSame(retained,h.model.bulkSelection);assertNotNull(h.model.error);assertEquals(0,h.writes)
        for (state in listOf(EngineState.Ready(fit("other")),EngineState.Ready(fit(revision=8)),EngineState.Loading,EngineState.Failed("Offline"),
            EngineState.Ready(fit(),BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,"Restart")))) {
            h.state=EngineState.Ready(fit());h.start();h.state=state
            ui { h.reads.last().complete(result(h.details)) }
            assertSame(retained,h.model.bulkSelection);assertEquals(main,h.model.bulkMainKey);assertFalse(h.model.selectingSimilar)
        }
        h.state=EngineState.Ready(fit());h.start();ui { h.reads.last().complete(result(h.details)) }
        assertEquals(listOf(0,3,5,27),h.model.bulkSelection!!.rows.map { it.index });assertEquals(0,h.writes)
    }
}
