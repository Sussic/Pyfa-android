package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Immutable synthetic details test native ownership; they are not a numerical oracle. */
@RunWith(AndroidJUnit4::class)
class ProjectedFighterBulkModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private fun fit(id: String="fit",revision: Long=7) = FitSnapshot(id,revision,"Recipient","Rifter",emptyMap(),emptyList(),emptyMap(),emptyList(),emptyList(),emptyList())
    private fun row(index: Int,range: Double?=null,editable: Boolean=true) = ProjectedFighterRow(index,(index+1).toString(16).padStart(32,'0'),100+index,"Projector $index",
        2,3,true,range,editable,if(editable)null else "Unsupported input")
    private fun details(rows: List<ProjectedFighterRow>,revision: Long=7,id: String="fit") = ProjectedFighterDetails(id,revision,false,rows)
    private fun refused() = BridgeResponse("request","session",BridgeStatus.ERROR,emptyList(),BridgeError(BridgeErrorCode.INVALID_EDIT,"Edit refused"))

    @Test fun orderedSelectionSurvivesPaginationAndRefreshUntilExplicitWholeSelectionReview() {
        var state: EngineState=EngineState.Ready(fit())
        var response=details((0..27).map { row(it,editable=it!=0) })
        var writes=0
        val model=ProjectedFighterModel(engineState={state},read={_,_,_-> CompletableFuture.completedFuture(response)},
            readOptions={_,id,revision,row-> CompletableFuture.completedFuture(ProjectedFighterOptions(id,revision,row.index,row.objectKey,row.itemId,emptyList(),emptyList()))},
            dispatch={_,_,_-> writes++; CompletableFuture()})
        main { model.load(context,fit()) }
        main { model.toggleBulk(response.squadrons[0]); model.toggleBulk(response.squadrons[3]); model.showPage(1); model.toggleBulk(response.squadrons[27]); model.showPage(0); model.toggleBulk(response.squadrons[1]) }
        val captured=model.bulkSelection!!
        assertEquals(listOf(3,27,1),captured.rows.map { it.index }); assertTrue(model.canBulk(captured))
        main { model.selectBulkMain(context,response.squadrons[3]); model.beginBulkRange(captured); model.changeBulkRange("1.25") }
        val mainKey=model.bulkMainKey; assertEquals(response.squadrons[3].objectKey,mainKey)
        val retained=model.bulkDraft
        for (other in listOf(EngineState.Loading,EngineState.Empty(),EngineState.Failed("Unavailable"),
            EngineState.Ready(fit(),BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,"Restart")),EngineState.Ready(fit("other")))) {
            state=other
            main {
                if (other is EngineState.Ready && other.fit.id=="other") model.load(context,other.fit)
                model.saveBulkRange(context); model.removeBulk(context,captured); model.toggleBulk(response.squadrons[2])
            }
            assertEquals(mainKey,model.bulkMainKey); assertEquals(captured.rows.first(),model.capturedBulkMain)
            assertSame(captured,model.bulkSelection); assertSame(retained,model.bulkDraft); assertTrue(model.bulkStale); assertFalse(model.canReviewBulk)
        }
        state=EngineState.Ready(fit(revision=8)); response=details(response.squadrons.map { it.copy(rangeM=5000.0) },8)
        main { model.load(context,fit(revision=8)) }
        assertTrue(model.bulkStale); assertTrue(model.canReviewBulk); assertEquals("1.25",model.bulkDraft!!.text)
        main { model.reviewBulk() }
        assertEquals(listOf(3,27,1),model.bulkSelection!!.rows.map { it.index }); assertEquals(8L,model.bulkSelection!!.revision)
        assertFalse(model.bulkStale); assertEquals("5.0",model.bulkDraft!!.text)
        assertEquals(mainKey,model.bulkMainKey); assertEquals(3,model.bulkMain!!.index); assertNull(model.bulkMainOptions)
        main { model.discardBulkRange(); model.bulkActive(context,captured,false) }; assertEquals(0,writes)
        // A replacement at the same position cannot inherit the selected object's identity.
        state=EngineState.Ready(fit(revision=9)); response=details(response.squadrons.map { if(it.index==3) it.copy(objectKey="f".repeat(32)) else it },9)
        main { model.load(context,fit(revision=9)); model.reviewBulk(); model.selectBulkPage() }
        assertFalse(model.canReviewBulk); assertTrue(model.bulkStale); assertEquals(3,model.bulkSelection!!.rows.size); assertEquals(0,writes)
        main { model.clearBulk(); model.selectBulkPage() }
        assertEquals(24,model.bulkSelection!!.rows.size); assertTrue(model.bulkSelection!!.rows.all { it.editable }); assertEquals(0,writes)
    }

    @Test fun mixedNullZeroRequiresExplicitChoiceAndUniformRawMetresNeverRoundTripOnUntouchedSave() {
        for (raw in listOf(Double.MIN_VALUE,63.7,null)) {
            val rows=listOf(row(0,raw),row(2,raw)); var writes=0
            val model=ProjectedFighterModel(engineState={EngineState.Ready(fit())},read={_,_,_-> CompletableFuture.completedFuture(details(rows))},dispatch={_,_,_-> writes++; CompletableFuture()})
            main { model.load(context,fit()) }; main { rows.forEach(model::toggleBulk); model.beginBulkRange(model.bulkSelection!!); model.changeBulkRange(" ${model.bulkDraft!!.text} "); model.saveBulkRange(context) }
            assertEquals(0,writes); assertNull(model.bulkDraft); assertEquals(rows,model.bulkSelection!!.rows)
        }
        for (useDefault in listOf(false,true)) {
            val rows=listOf(row(0,null),row(2,0.0)); var operation: BridgeOperation?=null; var calls=0
            val model=ProjectedFighterModel(engineState={EngineState.Ready(fit())},read={_,_,_-> CompletableFuture.completedFuture(details(rows))},dispatch={_,op,revisions->
                assertEquals(mapOf("fit" to 7L),revisions); calls++; operation=op; CompletableFuture()})
            main { model.load(context,fit()) }; main { rows.reversed().forEach(model::toggleBulk); model.beginBulkRange(model.bulkSelection!!); model.saveBulkRange(context) }
            assertTrue(model.bulkDraft!!.mixed); assertEquals(0,calls); assertNotNull(model.error)
            main { model.changeBulkRange(""); model.saveBulkRange(context) }; assertEquals(0,calls)
            main { if(useDefault) model.defaultBulkRange() else model.changeBulkRange("0"); model.saveBulkRange(context) }
            assertEquals(1,calls)
            val op=operation as BridgeOperation.SetProjectedFighterRanges
            assertEquals(listOf(2,0),op.selection.map { it.position }); assertEquals(if(useDefault)null else 0.0,op.rangeM)
        }
    }

    @Test fun onePendingGateProtectsSingleAndBulkEditsAndFailureRetainsExactDraft() {
        val rows=listOf(row(0),row(2,0.0)); val response=details(rows)
        val pending=mutableListOf<CompletableFuture<BridgeResponse>>(); var calls=0
        val model=ProjectedFighterModel(engineState={EngineState.Ready(fit())},read={_,_,_-> CompletableFuture.completedFuture(response)},dispatch={_,_,_-> calls++; CompletableFuture<BridgeResponse>().also(pending::add)})
        main { model.load(context,fit()) }; val anchor=model.anchor(rows.first())!!
        main { rows.forEach(model::toggleBulk); model.beginRange(anchor); model.beginBulkRange(model.bulkSelection!!) }
        assertNotNull(model.draft); assertNull(model.bulkDraft)
        main { model.discardDraft(); model.beginBulkRange(model.bulkSelection!!); model.changeBulkRange("1.25"); model.beginRange(anchor) }
        assertNull(model.draft); val draft=model.bulkDraft; val selection=model.bulkSelection
        main { model.saveBulkRange(context); model.saveBulkRange(context); model.remove(context,anchor); model.removeBulk(context,selection!!); model.clearBulk(); model.defaultBulkRange() }
        assertTrue(model.editing); assertEquals(1,calls); assertSame(selection,model.bulkSelection); assertSame(draft,model.bulkDraft)
        main { pending.single().complete(refused()) }
        assertFalse(model.editing); assertSame(draft,model.bulkDraft); assertEquals("Edit refused",model.error)
        main { model.discardBulkRange(); model.removeBulk(context,selection!!) }
        assertEquals(2,calls)
        main { pending.last().complete(BridgeResponse("request","session",BridgeStatus.OK,listOf(fit()),null)) }
        assertNull(model.bulkSelection); assertNull(model.bulkDraft)
        main { model.selectBulkPage(); model.clearBulk() }; assertNull(model.bulkSelection); assertEquals(2,calls)
    }

    @Test fun lateSuccessCannotRepaintAnotherFitAndSelectionDoesNotFollowReplacementRows() {
        var state: EngineState=EngineState.Ready(fit()); val rows=listOf(row(0),row(2))
        val pending=CompletableFuture<BridgeResponse>(); var calls=0
        val model=ProjectedFighterModel(engineState={state},read={_,_,_-> CompletableFuture.completedFuture(details(rows))},dispatch={_,op,_->
            assertTrue(op is BridgeOperation.SetProjectedFightersActive); calls++; pending})
        main { model.load(context,fit()) }; main { rows.forEach(model::toggleBulk); model.bulkActive(context,model.bulkSelection!!,false) }
        val selection=model.bulkSelection
        state=EngineState.Ready(fit("other"))
        main { pending.complete(BridgeResponse("request","session",BridgeStatus.OK,listOf(fit(revision=8)),null)) }
        assertNull(model.message); assertNull(model.error); assertSame(selection,model.bulkSelection); assertTrue(model.bulkStale); assertEquals(1,calls)
    }
    @Test fun booleanStateNoopAndJointBudgetFailurePreserveExactSelection() {
        val rows=listOf(row(0),row(2).copy(active=false))
        val pending=CompletableFuture<BridgeResponse>(); var sent: BridgeOperation?=null; var calls=0
        val model=ProjectedFighterModel(engineState={EngineState.Ready(fit())},read={_,_,_-> CompletableFuture.completedFuture(details(rows))},
            dispatch={_,op,_-> calls++; sent=op; pending})
        main { model.load(context,fit()) }
        main { model.toggleBulk(rows[0]); model.bulkActive(context,model.bulkSelection!!,true) }
        assertEquals(0,calls); assertTrue(model.message!!.contains("unchanged"))
        main { model.toggleBulk(rows[1]); model.bulkActive(context,model.bulkSelection!!,true) }
        val selection=model.bulkSelection
        assertTrue((sent as BridgeOperation.SetProjectedFightersActive).active)
        assertEquals(rows,model.currentDetails!!.squadrons)
        main { pending.complete(BridgeResponse("request","session",BridgeStatus.ERROR,emptyList(),
            BridgeError(BridgeErrorCode.INVALID_EDIT,"Projected-drone evaluation budget: complete-request reservation exceeded"))) }
        assertSame(selection,model.bulkSelection); assertEquals(rows,model.currentDetails!!.squadrons)
        assertTrue(model.error!!.contains("evaluation budget")); assertFalse(model.editing)
    }

    @Test fun mainOptionsOwnOneDirectionWithIdentityGuardsAndNoSecondaryFiltering() {
        val rows=listOf(row(0),row(1).copy(itemId=rowsItem,active=false),row(2).copy(itemId=rowsItem))
        val optionReads=mutableListOf<CompletableFuture<ProjectedFighterOptions>>()
        val calls=mutableListOf<BridgeOperation>(); val pending=CompletableFuture<BridgeResponse>()
        var state: EngineState=EngineState.Ready(fit())
        val model=ProjectedFighterModel(engineState={state},read={_,_,_-> CompletableFuture.completedFuture(details(rows))},
            readOptions={_,_,_,_-> CompletableFuture<ProjectedFighterOptions>().also(optionReads::add)},
            dispatch={_,op,revisions-> assertEquals(mapOf("fit" to 7L),revisions); calls+=op; pending})
        fun options(row: ProjectedFighterRow,on: Boolean)=ProjectedFighterOptions("fit",7,row.index,row.objectKey,row.itemId,
            listOf(FighterAbility(6435,"Web",on),FighterAbility(6441,"MWD",false)),emptyList())
        main { model.load(context,fit()) }
        main { model.toggleBulk(rows[2]); model.toggleBulk(rows[1]); model.selectBulkMain(context,rows[0]) }
        assertEquals(0,optionReads.size) // Nonselected main is not a UI action.
        main { model.selectBulkMain(context,rows[2]); model.selectBulkMain(context,rows[1]) }
        main { optionReads[0].complete(options(rows[2],true)) }; assertNull(model.currentOptions)
        main { optionReads[1].complete(options(rows[1],false)) }
        val selection=model.bulkSelection!!; val mainAnchor=model.anchor(rows[1])!!; val before=model.currentOptions!!
        assertEquals(rows[1],model.bulkMain)
        main {
            model.bulkAbility(context,selection,model.anchor(rows[0])!!,before,before.abilities.first())
            model.bulkAbility(context,selection,mainAnchor,before.copy(),before.abilities.first())
            model.bulkAbility(context,selection,mainAnchor,before,before.abilities.first().copy(active=true))
        }
        assertTrue(calls.isEmpty())
        main { model.bulkAbility(context,selection,mainAnchor,before,before.abilities.first())
            model.bulkAbility(context,selection,mainAnchor,before,before.abilities.first()); model.toggleBulk(rows[0]) }
        assertEquals(1,calls.size)
        val op=calls.single() as BridgeOperation.ToggleProjectedFighterAbilities
        assertEquals(ProjectedFighterSelectionRow(1,rows[1].objectKey),op.main)
        assertEquals(listOf(2,1),op.selection.map { it.position }); assertEquals(6435,op.effectId)
        // The backend, not a per-secondary options fanout, applies matching IDs or skips missing IDs.
        assertEquals(2,optionReads.size); assertEquals(rows,model.currentDetails!!.squadrons)
        state=EngineState.Ready(fit("other"))
        main { pending.complete(BridgeResponse("request","session",BridgeStatus.OK,listOf(fit(revision=8)),null)) }
        assertNull(model.message); assertSame(selection,model.bulkSelection); assertTrue(model.bulkStale)
    }
    @Test fun lateMainOptionsCannotReviveDeselectedMainOrReuseAnOldSelectionAfterReview() {
        val rows=listOf(row(0),row(2))
        var state: EngineState=EngineState.Ready(fit()); var response=details(rows)
        val pending=mutableListOf<CompletableFuture<ProjectedFighterOptions>>(); var writes=0
        val model=ProjectedFighterModel(engineState={state},read={_,_,_-> CompletableFuture.completedFuture(response)},
            readOptions={_,_,_,_-> CompletableFuture<ProjectedFighterOptions>().also(pending::add)},
            dispatch={_,_,_-> writes++; CompletableFuture()})
        fun options(revision: Long)=ProjectedFighterOptions("fit",revision,0,rows[0].objectKey,rows[0].itemId,
            listOf(FighterAbility(6435,"Web",true)),emptyList())
        main { model.load(context,fit()) }
        main { rows.forEach(model::toggleBulk); model.selectBulkMain(context,rows[0]) }
        val old=model.bulkSelection!!; val anchor=model.anchor(rows[0])!!
        main { model.toggleBulk(rows[0]); pending[0].complete(options(7)) }
        assertNull(model.bulkMain); assertNull(model.bulkMainKey); assertNull(model.bulkMainOptions)
        main { model.bulkAbility(context,old,anchor,options(7),options(7).abilities.first()); model.toggleBulk(rows[0]) }
        assertEquals(0,writes); assertNull(model.bulkMain)
        main { model.selectBulkMain(context,rows[0]) }
        val second=model.bulkSelection!!
        state=EngineState.Ready(fit(revision=8)); response=details(rows,8)
        main { model.load(context,fit(revision=8)) }
        assertEquals(3,pending.size) // Current row read replaces the still-pending old revision read.
        main { pending[1].complete(options(7)) }
        assertNull(model.bulkMainOptions); assertTrue(model.bulkStale)
        main { model.reviewBulk(); pending[2].complete(options(8)) }
        val current=model.bulkMainOptions!!
        assertEquals(rows[0].objectKey,model.bulkMainKey); assertEquals(listOf(2,0),model.bulkSelection!!.rows.map { it.index })
        main { model.bulkAbility(context,second,anchor,current,current.abilities.first()) }
        assertEquals(0,writes)
        main { model.bulkAbility(context,model.bulkSelection!!,model.anchor(rows[0])!!,current,current.abilities.first()) }
        assertEquals(1,writes)
    }
    private val rowsItem=200
}
