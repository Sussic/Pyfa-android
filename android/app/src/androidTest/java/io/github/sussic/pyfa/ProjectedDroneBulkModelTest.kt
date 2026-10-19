package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Immutable synthetic details test native ownership; they are not a numerical oracle. */
@RunWith(AndroidJUnit4::class)
class ProjectedDroneBulkModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private fun fit(id: String="fit",revision: Long=7) = FitSnapshot(id,revision,"Recipient","Rifter",emptyMap(),emptyList(),emptyMap(),emptyList(),emptyList(),emptyList())
    private fun row(index: Int,range: Double?=null,editable: Boolean=true) = ProjectedDroneRow(index,(index+1).toString(16).padStart(32,'0'),100+index,"Projector $index",
        5,2,range,editable,if(editable)null else "Unsupported input")
    private fun details(rows: List<ProjectedDroneRow>,revision: Long=7,id: String="fit") = ProjectedDroneDetails(id,revision,false,rows)
    private fun refused() = BridgeResponse("request","session",BridgeStatus.ERROR,emptyList(),BridgeError(BridgeErrorCode.INVALID_EDIT,"Edit refused"))

    @Test fun orderedSelectionSurvivesPaginationAndRefreshUntilExplicitWholeSelectionReview() {
        var state: EngineState=EngineState.Ready(fit())
        var response=details((0..27).map { row(it,editable=it!=0) })
        var writes=0
        val model=ProjectedDroneModel(engineState={state},read={_,_,_-> CompletableFuture.completedFuture(response)},dispatch={_,_,_-> writes++; CompletableFuture()})
        main { model.load(context,fit()) }
        main { model.toggleBulk(response.stacks[0]); model.toggleBulk(response.stacks[3]); model.showPage(1); model.toggleBulk(response.stacks[27]); model.showPage(0); model.toggleBulk(response.stacks[1]) }
        val captured=model.bulkSelection!!
        assertEquals(listOf(3,27,1),captured.rows.map { it.index }); assertTrue(model.canBulk(captured))
        main { model.beginBulkRange(captured); model.changeBulkRange("1.25") }
        val retained=model.bulkDraft
        for (other in listOf(EngineState.Loading,EngineState.Empty(),EngineState.Failed("Unavailable"),
            EngineState.Ready(fit(),BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,"Restart")),EngineState.Ready(fit("other")))) {
            state=other
            main { model.saveBulkRange(context); model.removeBulk(context,captured); model.toggleBulk(response.stacks[2]) }
            assertSame(captured,model.bulkSelection); assertSame(retained,model.bulkDraft); assertTrue(model.bulkStale); assertFalse(model.canReviewBulk)
        }
        state=EngineState.Ready(fit(revision=8)); response=details(response.stacks.map { it.copy(rangeM=5000.0) },8)
        main { model.load(context,fit(revision=8)) }
        assertTrue(model.bulkStale); assertTrue(model.canReviewBulk); assertEquals("1.25",model.bulkDraft!!.text)
        main { model.reviewBulk() }
        assertEquals(listOf(3,27,1),model.bulkSelection!!.rows.map { it.index }); assertEquals(8L,model.bulkSelection!!.revision)
        assertFalse(model.bulkStale); assertEquals("5.0",model.bulkDraft!!.text)
        main { model.discardBulkRange(); model.bulkActive(context,captured,false) }; assertEquals(0,writes)
        // A replacement at the same position cannot inherit the selected object's identity.
        state=EngineState.Ready(fit(revision=9)); response=details(response.stacks.map { if(it.index==3) it.copy(objectKey="f".repeat(32)) else it },9)
        main { model.load(context,fit(revision=9)); model.reviewBulk(); model.selectBulkPage() }
        assertFalse(model.canReviewBulk); assertTrue(model.bulkStale); assertEquals(3,model.bulkSelection!!.rows.size); assertEquals(0,writes)
        main { model.clearBulk(); model.selectBulkPage() }
        assertEquals(24,model.bulkSelection!!.rows.size); assertTrue(model.bulkSelection!!.rows.all { it.editable }); assertEquals(0,writes)
    }

    @Test fun mixedNullZeroRequiresExplicitChoiceAndUniformRawMetresNeverRoundTripOnUntouchedSave() {
        for (raw in listOf(Double.MIN_VALUE,63.7,null)) {
            val rows=listOf(row(0,raw),row(2,raw)); var writes=0
            val model=ProjectedDroneModel(engineState={EngineState.Ready(fit())},read={_,_,_-> CompletableFuture.completedFuture(details(rows))},dispatch={_,_,_-> writes++; CompletableFuture()})
            main { model.load(context,fit()) }; main { rows.forEach(model::toggleBulk); model.beginBulkRange(model.bulkSelection!!); model.changeBulkRange(" ${model.bulkDraft!!.text} "); model.saveBulkRange(context) }
            assertEquals(0,writes); assertNull(model.bulkDraft); assertEquals(rows,model.bulkSelection!!.rows)
        }
        for (useDefault in listOf(false,true)) {
            val rows=listOf(row(0,null),row(2,0.0)); var operation: BridgeOperation?=null; var calls=0
            val model=ProjectedDroneModel(engineState={EngineState.Ready(fit())},read={_,_,_-> CompletableFuture.completedFuture(details(rows))},dispatch={_,op,revisions->
                assertEquals(mapOf("fit" to 7L),revisions); calls++; operation=op; CompletableFuture()})
            main { model.load(context,fit()) }; main { rows.reversed().forEach(model::toggleBulk); model.beginBulkRange(model.bulkSelection!!); model.saveBulkRange(context) }
            assertTrue(model.bulkDraft!!.mixed); assertEquals(0,calls); assertNotNull(model.error)
            main { model.changeBulkRange(""); model.saveBulkRange(context) }; assertEquals(0,calls)
            main { if(useDefault) model.defaultBulkRange() else model.changeBulkRange("0"); model.saveBulkRange(context) }
            assertEquals(1,calls)
            val op=operation as BridgeOperation.SetProjectedDroneRanges
            assertEquals(listOf(2,0),op.selection.map { it.position }); assertEquals(if(useDefault)null else 0.0,op.rangeM)
        }
    }

    @Test fun onePendingGateProtectsSingleAndBulkEditsAndFailureRetainsExactDraft() {
        val rows=listOf(row(0),row(2,0.0)); val response=details(rows)
        val pending=mutableListOf<CompletableFuture<BridgeResponse>>(); var calls=0
        val model=ProjectedDroneModel(engineState={EngineState.Ready(fit())},read={_,_,_-> CompletableFuture.completedFuture(response)},dispatch={_,_,_-> calls++; CompletableFuture<BridgeResponse>().also(pending::add)})
        main { model.load(context,fit()) }; val anchor=model.anchor(rows.first())!!
        main { rows.forEach(model::toggleBulk); model.beginRange(anchor); model.beginBulkRange(model.bulkSelection!!) }
        assertNotNull(model.draft); assertNull(model.bulkDraft)
        main { model.discardDraft(); model.beginBulkRange(model.bulkSelection!!); model.changeBulkRange("1.25"); model.beginRange(anchor) }
        assertNull(model.draft); val draft=model.bulkDraft; val selection=model.bulkSelection
        main { model.saveBulkRange(context); model.saveBulkRange(context); model.remove(context,anchor,1); model.removeBulk(context,selection!!); model.clearBulk(); model.defaultBulkRange() }
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
        val model=ProjectedDroneModel(engineState={state},read={_,_,_-> CompletableFuture.completedFuture(details(rows))},dispatch={_,op,_->
            assertTrue(op is BridgeOperation.SetProjectedDronesActive); calls++; pending})
        main { model.load(context,fit()) }; main { rows.forEach(model::toggleBulk); model.bulkActive(context,model.bulkSelection!!,false) }
        val selection=model.bulkSelection
        state=EngineState.Ready(fit("other"))
        main { pending.complete(BridgeResponse("request","session",BridgeStatus.OK,listOf(fit(revision=8)),null)) }
        assertNull(model.message); assertNull(model.error); assertSame(selection,model.bulkSelection); assertTrue(model.bulkStale); assertEquals(1,calls)
    }
    @Test fun partialAndBlockedActivationAreEngineDecisionsAndBudgetRefusalNeverChangesRows() {
        val rows=listOf(row(0).copy(amount=5,active=2),row(2).copy(amount=4,active=0))
        val pending=CompletableFuture<BridgeResponse>(); var sent: BridgeOperation?=null
        val model=ProjectedDroneModel(engineState={EngineState.Ready(fit())},read={_,_,_-> CompletableFuture.completedFuture(details(rows))},
            dispatch={_,op,_-> sent=op; pending})
        main { model.load(context,fit()) }
        main { rows.forEach(model::toggleBulk); model.bulkActive(context,model.bulkSelection!!,true) }
        val selection=model.bulkSelection
        assertTrue((sent as BridgeOperation.SetProjectedDronesActive).active)
        assertEquals(listOf(2,0),model.bulkSelection!!.rows.map { it.active })
        assertEquals(rows,model.currentDetails!!.stacks)
        main { pending.complete(BridgeResponse("request","session",BridgeStatus.ERROR,emptyList(),
            BridgeError(BridgeErrorCode.INVALID_EDIT,"Projected-drone evaluation budget: complete-request reservation exceeded"))) }
        assertSame(selection,model.bulkSelection); assertEquals(rows,model.currentDetails!!.stacks)
        assertTrue(model.error!!.contains("evaluation budget")); assertFalse(model.editing)
        // Partial and blocked are input observations, never a Kotlin calculation of the resulting counts.
        assertEquals(listOf(5,4),model.bulkSelection!!.rows.map { it.amount })
    }

}
