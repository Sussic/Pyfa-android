package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.TimeUnit
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred offline Android phase projected_module_charges; real EOS effects, no invented golden values. */
@RunWith(AndroidJUnit4::class)
class ProjectedModuleChargeUiTest {
    @get:Rule val compose=createAndroidComposeRule<MainActivity>()
    private val context get()=InstrumentationRegistry.getInstrumentation().targetContext
    private val model get()=ViewModelProvider(compose.activity)[ProjectedModuleModel::class.java]
    private fun fit(id:String)=EngineRuntime.library.value.single { it.id==id }
    private fun waitFor(test:()->Boolean) { compose.waitUntil(120_000,test); compose.waitForIdle() }
    private fun settled(id:String)=waitFor { !model.editing && !model.loading && model.currentDetails?.let { it.fitId==id && it.revision==fit(id).revision }==true }
    private fun click(tag:String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag:String,value:String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun send(op:BridgeOperation,vararg ids:String)=EngineRuntime.request(context,op,ids.toSet().associateWith { fit(it).revision })
        .get(120,TimeUnit.SECONDS).also { assertTrue(it.error?.message,it.isSuccess) }
    private fun item(name:String)=EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS).items.single { it.name==name }.id
    private fun details(id:String)=EngineRuntime.projectedModuleDetails(context,id,fit(id).revision).get(30,TimeUnit.SECONDS)
    private fun history(id:String)=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
    private fun scan(id:String)=fit(id).stats.getValue("scan_resolution").value.numberOrNull()!!
    private fun preview()=waitFor { !model.chargeLoading && model.currentChargePreview!=null }
    private fun refresh() { click("projected-charge-refresh"); preview() }
    private fun apply(id:String) { val before=fit(id).revision; click("projected-charge-apply"); waitFor { fit(id).revision>before }; settled(id) }
    private fun undo(id:String,redo:Boolean=false) {
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision==fit(id).revision }
        val before=fit(id).revision; click(if(redo)"history-redo" else "history-undo"); waitFor { fit(id).revision>before }; settled(id)
    }
    private fun prepare():String {
        assertEquals("projected_module_charges",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val id=send(BridgeOperation.CreateFit(FitSpec("Projected charges ${System.nanoTime()}","Rifter",5,false,
            DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),emptyList(),emptyList()))).fits.single().id
        repeat(3) { send(BridgeOperation.AddProjectedModule(id,item("Remote Sensor Booster II")),id) }
        send(BridgeOperation.AddProjectedModule(id,item("Warp Scrambler II")),id)
        val rows=details(id).modules
        send(BridgeOperation.SetProjectedModuleRange(id,rows[2].index,rows[2].objectKey,63.7),id)
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS); click("projected-modules-open"); settled(id)
        return id
    }

    @Test fun selectedAndSimilarScriptsPreviewExactSkipsHaveRealEffectsAndOneUndo() {
        val id=prepare(); val original=model.currentDetails!!.modules.toList(); val stats=fit(id).stats; val originalScan=scan(id)
        val recent=EngineRuntime.recent.value.toList(); val beforeHistory=history(id).undoCount; val revision=fit(id).revision
        click("projected-module-2-bulk-select"); click("projected-module-3-bulk-select"); click("projected-module-0-bulk-select")
        click("projected-module-0-charge-main"); preview()
        assertEquals(listOf(2,3,0),model.currentChargePreview!!.selection.map { it.index })
        assertEquals(listOf(0,2,3),model.currentChargePreview!!.targets.map { it.identity.index })
        compose.onNodeWithTag("projected-charge-apply").assertIsNotEnabled()
        compose.onNodeWithTag("projected-charge-unchanged").assertExists()
        val script=item("Scan Resolution Script")
        text("projected-charge-search","Scan Resolution Script"); click("projected-charge-choice-$script")
        compose.onNodeWithTag("projected-charge-needs-preview").assertExists(); refresh()
        val p=model.currentChargePreview!!
        assertEquals(listOf(0,2),p.targets.filter { it.status==ProjectedChargeStatus.CHANGE }.map { it.identity.index })
        assertEquals(ProjectedChargeStatus.INCOMPATIBLE,p.targets.single { it.identity.index==3 }.status)
        assertEquals(revision,fit(id).revision); assertEquals(beforeHistory,history(id).undoCount); assertEquals(original,model.currentDetails!!.modules)
        apply(id); assertEquals(beforeHistory+1,history(id).undoCount); assertTrue(scan(id)>originalScan)
        assertEquals(original[1],model.currentDetails!!.modules[1]); assertEquals(original[3],model.currentDetails!!.modules[3])
        assertEquals(listOf(script,null,script,null),model.currentDetails!!.modules.map { it.chargeId })
        assertEquals(original.map { it.rangeM },model.currentDetails!!.modules.map { it.rangeM }); assertEquals(recent,EngineRuntime.recent.value)
        undo(id); assertEquals(original,model.currentDetails!!.modules); assertEquals(stats,fit(id).stats)
        undo(id,true); assertEquals(listOf(script,null,script,null),model.currentDetails!!.modules.map { it.chargeId })
        undo(id); click("projected-modules-bulk-review")
        click("projected-charge-scope-SIMILAR"); refresh()
        assertEquals(listOf(0,1,2),model.currentChargePreview!!.targets.map { it.identity.index })
        assertEquals(listOf(3),model.currentChargePreview!!.excluded.map { it.identity.index })
        val before=history(id).undoCount; apply(id); assertEquals(before+1,history(id).undoCount)
        assertEquals(listOf(script,script,script,null),model.currentDetails!!.modules.map { it.chargeId })
        click("projected-modules-bulk-review"); click("projected-charge-clear"); refresh(); apply(id)
        assertEquals(original,model.currentDetails!!.modules); assertEquals(stats,fit(id).stats); assertEquals(recent,EngineRuntime.recent.value)
        // Existing single-row charge controls still reach the same persisted projectors.
        click("projected-module-1-options"); waitFor { model.currentOptions?.index==1 && !model.optionsLoading }
        click("projected-module-1-charges"); compose.onNodeWithTag("projected-module-1-charge-$script").assertExists()
    }

    @Test fun recreationNavigationRetainsInputsAndRangeDraftStaleDeletionRequireReview() {
        val id=prepare(); click("projected-module-2-bulk-select"); click("projected-module-0-bulk-select"); click("projected-module-0-charge-main"); preview()
        val script=item("Targeting Range Script")
        text("projected-charge-search","Targeting Range Script"); click("projected-charge-choice-$script"); click("projected-charge-scope-SIMILAR"); refresh()
        val selected=model.bulkSelection; val main=model.chargeMainKey; val retained=model; val undoCount=history(id).undoCount
        compose.activityRule.scenario.recreate(); settled(id)
        assertSame(retained,model); assertSame(selected,model.bulkSelection); assertEquals(main,model.chargeMainKey)
        assertEquals(script,model.chargeId); assertEquals(BulkScope.SIMILAR,model.chargeScope); assertEquals(undoCount,history(id).undoCount)
        click("projected-modules-back"); click("projected-modules-open"); settled(id)
        assertEquals(script,model.chargeId); assertEquals(main,model.chargeMainKey)
        click("projected-modules-bulk-range-edit"); text("projected-modules-bulk-range-input","1.25")
        compose.onNodeWithTag("projected-charge-refresh").assertIsNotEnabled(); compose.onNodeWithTag("projected-charge-range-blocked").assertExists()
        compose.onNodeWithTag("projected-module-0-charge-main").assertIsNotEnabled()
        compose.activityRule.scenario.recreate(); settled(id); assertEquals("1.25",model.bulkDraft!!.text)
        send(BridgeOperation.RenameFit(id,"Charge draft renamed ${System.nanoTime()}"),id); settled(id)
        assertTrue(model.bulkStale); assertEquals("1.25",model.bulkDraft!!.text); assertNull(model.currentChargePreview)
        click("projected-modules-bulk-review"); assertFalse(model.bulkStale); assertEquals(script,model.chargeId)
        click("projected-modules-bulk-range-discard"); refresh(); assertTrue(model.canApplyCharges)
        val remove=model.currentDetails!!.modules[2]
        send(BridgeOperation.RemoveProjectedModule(id,remove.index,remove.objectKey),id); settled(id)
        assertTrue(model.bulkStale); assertFalse(model.canReviewBulk); compose.onNodeWithTag("projected-charge-refresh").assertIsNotEnabled()
        assertEquals(2,model.bulkSelection!!.rows.size); assertEquals(main,model.chargeMainKey)
        click("projected-modules-bulk-clear"); assertNull(model.chargeMainKey); assertNull(model.currentChargePreview)
    }
}
