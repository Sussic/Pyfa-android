package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic protocol/state proof only. Original EOS is the separate numerical oracle. */
@RunWith(AndroidJUnit4::class)
class ProjectedModuleChargeModelTest {
    private val instrumentation get()=InstrumentationRegistry.getInstrumentation()
    private val context get()=instrumentation.targetContext
    private fun ui(block:()->Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private fun fit(id:String="fit",revision:Long=7)=FitSnapshot(id,revision,"Recipient","Rifter",emptyMap(),emptyList(),emptyMap(),emptyList(),emptyList(),emptyList())
    private fun row(n:Int)=ProjectedModuleRow(n,(n+1).toString(16).padStart(32,'0'),100+n,"Module $n",ModuleState.ACTIVE,
        if(n==2)900 else null,if(n==2)"Script" else null,if(n==0)Double.MIN_VALUE else 0.0,true,null)
    private fun identity(r:ProjectedModuleRow)=ProjectedChargeIdentity(r.index,r.objectKey,r.itemId)
    private fun response(c:ProjectedChargeCapture)=ProjectedModuleChargePreview(c.details.fitId,c.details.revision,identity(c.main),c.selection.rows.map(::identity),c.scope,c.chargeId,
        listOf(ProjectedModuleCharge(900,"Script"),ProjectedModuleCharge(901,"Other script")),true,null,
        (if(c.scope==BulkScope.SELECTED)c.selection.rows else c.details.modules).sortedBy { it.index }.map {
            ProjectedChargeTarget(identity(it),it.name,it.chargeId,it.chargeName,if(it.chargeId==c.chargeId)ProjectedChargeStatus.UNCHANGED else ProjectedChargeStatus.CHANGE)
        },emptyList())
    private fun refused()=BridgeResponse("request","session",BridgeStatus.ERROR,emptyList(),BridgeError(BridgeErrorCode.INVALID_EDIT,"Edit refused"))

    @Test fun explicitRefreshCapturesSelectionOrderAndDispatchesOnlyConfirmedOrderedChangesOnce() {
        val rows=(0..3).map(::row); val d=ProjectedModuleDetails("fit",7,false,rows)
        val reads=mutableListOf<ProjectedChargeCapture>(); val writes=mutableListOf<BridgeOperation>(); val pending=CompletableFuture<BridgeResponse>()
        val model=ProjectedModuleModel(engineState={EngineState.Ready(fit())},read={_,_,_->CompletableFuture.completedFuture(d)},
            previewCharges={_,c->reads+=c; CompletableFuture.completedFuture(response(c))},dispatch={_,op,revisions->assertEquals(mapOf("fit" to 7L),revisions); writes+=op; pending})
        ui { model.load(context,fit()) }; ui { model.toggleBulk(rows[2]); model.toggleBulk(rows[0]); model.chooseChargeMain(context,rows[0]) }
        assertEquals(1,reads.size); assertNull(model.chargeId); assertEquals(listOf(2,0),model.currentChargePreview!!.selection.map { it.index })
        assertEquals(listOf(0,2),model.currentChargePreview!!.targets.map { it.identity.index })
        val old=model.currentChargePreview!!
        ui { model.chooseBulkCharge(900); model.applyCharges(context,old) }; assertNull(model.currentChargePreview); assertTrue(writes.isEmpty()); assertEquals(1,reads.size)
        ui { model.refreshChargePreview(context) }; val preview=model.currentChargePreview!!
        ui { model.applyCharges(context,preview.copy()); model.applyCharges(context,preview); model.applyCharges(context,preview); model.remove(context,model.anchor(rows[0])!!); model.clearBulk() }
        assertEquals(1,writes.size); assertTrue(model.editing)
        val op=writes.single() as BridgeOperation.SetProjectedModuleCharges
        assertEquals(listOf(2,0),op.selection.map { it.position }); assertEquals(listOf(0,2),op.expectedTargets.map { it.position }); assertEquals(listOf(0),op.expectedChanges.map { it.position })
        assertEquals(rows[0].rangeM,model.bulkSelection!!.rows[1].rangeM)
        ui { pending.complete(refused()) }; assertFalse(model.editing); assertEquals("Edit refused",model.error); assertEquals(listOf(2,0),model.bulkSelection!!.rows.map { it.index })
        assertNull(model.currentChargePreview)
    }

    @Test fun oneHeldReadGateDropsEveryObsoleteScopeMainSelectionDraftNavigationAndEditReply() {
        val changes:List<(ProjectedModuleModel,List<ProjectedModuleRow>)->Unit> = listOf(
            {m,r->m.toggleBulk(r[1])}, {m,_->m.selectBulkPage()}, {m,_->m.clearBulk()}, {m,r->m.chooseChargeMain(context,r[2])},
            {m,_->m.chooseChargeScope(BulkScope.SIMILAR)}, {m,r->m.beginRange(m.anchor(r[0])!!)},
            {m,_->m.beginBulkRange(m.bulkSelection!!)}, {m,_->m.leaveChargeEditor()}, {m,_->m.load(context,fit(),true)},
            {m,_->m.bulkState(context,m.bulkSelection!!,ProjectedModuleStateAction.INACTIVE)})
        for(change in changes) {
            val rows=(0..3).map(::row); val d=ProjectedModuleDetails("fit",7,false,rows); var calls=0
            var captured:ProjectedChargeCapture?=null; val pending=CompletableFuture<ProjectedModuleChargePreview>()
            val model=ProjectedModuleModel(engineState={EngineState.Ready(fit())},read={_,_,_->CompletableFuture.completedFuture(d)},
                previewCharges={_,c->calls++; captured=c; pending},dispatch={_,_,_->CompletableFuture()})
            ui { model.load(context,fit()) }; ui { model.toggleBulk(rows[2]); model.toggleBulk(rows[0]); model.chooseChargeMain(context,rows[0]) }
            ui { change(model,rows); model.refreshChargePreview(context); model.refreshChargePreview(context) }
            assertTrue(model.chargeLoading); assertEquals(1,calls)
            val selection=model.bulkSelection; val draft=model.draft; val bulk=model.bulkDraft; val main=model.chargeMainKey
            ui { pending.complete(response(captured!!)) }
            assertFalse(model.chargeLoading); assertNull(model.currentChargePreview); assertSame(selection,model.bulkSelection)
            assertSame(draft,model.draft); assertSame(bulk,model.bulkDraft); assertEquals(main,model.chargeMainKey)
        }
    }

    @Test fun harmlessFailureMalformedReplyAndUnavailableStatesRetainInputsUntilExplicitReview() {
        var state:EngineState=EngineState.Ready(fit()); var d=ProjectedModuleDetails("fit",7,false,(0..3).map(::row))
        val reads=mutableListOf<Pair<ProjectedChargeCapture,CompletableFuture<ProjectedModuleChargePreview>>>()
        val model=ProjectedModuleModel(engineState={state},read={_,_,_->CompletableFuture.completedFuture(d)},
            previewCharges={_,c->CompletableFuture<ProjectedModuleChargePreview>().also { reads+=c to it }})
        ui { model.load(context,fit()) }; ui { model.toggleBulk(d.modules[0]); model.toggleBulk(d.modules[2]); model.chooseChargeMain(context,d.modules[0]) }
        val selection=model.bulkSelection
        ui { reads.last().second.completeExceptionally(IllegalArgumentException("private trace")) }
        assertSame(selection,model.bulkSelection); assertNotNull(model.chargeError); assertFalse(model.chargeError!!.contains("private trace"))
        ui { model.refreshChargePreview(context) }; ui { reads.last().second.complete(response(reads.last().first).copy(revision=8)) }
        assertNull(model.currentChargePreview); assertNotNull(model.chargeError)
        for(other in listOf(EngineState.Loading,EngineState.Failed("Unavailable"),EngineState.Ready(fit("other")),EngineState.Ready(fit(revision=8)),
            EngineState.Ready(fit(),BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,"Restart")))) {
            state=EngineState.Ready(fit()); ui { model.refreshChargePreview(context) }; state=other
            ui { reads.last().second.complete(response(reads.last().first)) }
            assertNull(model.currentChargePreview); assertSame(selection,model.bulkSelection); assertFalse(model.canApplyCharges)
        }
        state=EngineState.Ready(fit(revision=8)); d=d.copy(revision=8,modules=d.modules.map { it.copy() })
        ui { model.load(context,fit(revision=8)); model.refreshChargePreview(context) }; assertTrue(model.bulkStale)
        ui { model.reviewBulk(); model.refreshChargePreview(context) }; ui { reads.last().second.complete(response(reads.last().first)) }
        assertFalse(model.bulkStale); assertNotNull(model.currentChargePreview); assertEquals(8L,model.currentChargePreview!!.revision)
        // Deleted selected row cannot be silently dropped by whole-selection review.
        state=EngineState.Ready(fit(revision=9)); d=d.copy(revision=9,modules=d.modules.filterNot { it.index==2 })
        ui { model.load(context,fit(revision=9)); model.reviewBulk() }; assertTrue(model.bulkStale); assertFalse(model.canReviewBulk)
    }

    @Test fun zeroChangeAndReadOnlyScopeCannotApplyAndRawRangeDraftIsNeverDiscarded() {
        val rows=(0..3).map(::row); val d=ProjectedModuleDetails("fit",7,false,rows); var writes=0
        val model=ProjectedModuleModel(engineState={EngineState.Ready(fit())},read={_,_,_->CompletableFuture.completedFuture(d)},
            previewCharges={_,c->CompletableFuture.completedFuture(response(c).let { if(c.scope==BulkScope.SIMILAR) it.copy(available=false,unavailableReason="Read-only environment") else it })},
            dispatch={_,_,_->writes++; CompletableFuture()})
        ui { model.load(context,fit()) }; ui { model.toggleBulk(rows[0]); model.chooseChargeMain(context,rows[0]) }
        assertNotNull(model.currentChargePreview); assertFalse(model.canApplyCharges)
        ui { model.applyCharges(context,model.currentChargePreview!!); model.chooseChargeScope(BulkScope.SIMILAR); model.refreshChargePreview(context) }
        assertFalse(model.currentChargePreview!!.available); assertFalse(model.canApplyCharges)
        ui { model.chooseChargeScope(BulkScope.SELECTED); model.beginRange(model.anchor(rows[0])!!); model.changeRange("1.25") }
        val draft=model.draft
        ui { model.chooseChargeMain(context,rows[0]); model.refreshChargePreview(context); model.chooseBulkCharge(900) }
        assertSame(draft,model.draft); assertNull(model.currentChargePreview); assertEquals(0,writes)
        ui { model.discardRange(); model.beginBulkRange(model.bulkSelection!!) }
        assertEquals(Double.MIN_VALUE,model.bulkDraft!!.selection.rows.single().rangeM)
        val bulk=model.bulkDraft
        ui { model.chooseChargeScope(BulkScope.SIMILAR); model.chooseChargeMain(context,rows[0]) }
        assertSame(bulk,model.bulkDraft); assertEquals(BulkScope.SELECTED,model.chargeScope); assertEquals(0,writes)
    }
}
