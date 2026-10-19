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

/** Deferred offline device gate, phase projected_module_bulk. Uses real EOS, no synthetic effect values. */
@RunWith(AndroidJUnit4::class)
class ProjectedModuleBulkUiTest {
    @get:Rule val compose=createAndroidComposeRule<MainActivity>()
    private val context get()=InstrumentationRegistry.getInstrumentation().targetContext
    private val model get()=ViewModelProvider(compose.activity)[ProjectedModuleModel::class.java]
    private fun fit(id: String)=EngineRuntime.library.value.single { it.id==id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000,test); compose.waitForIdle() }
    private fun settled(id: String)=waitFor { !model.editing && !model.loading && model.currentDetails?.let { it.fitId==id && it.revision==fit(id).revision }==true }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String,value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun send(op: BridgeOperation,vararg ids: String)=EngineRuntime.request(context,op,ids.toSet().associateWith { fit(it).revision })
        .get(120,TimeUnit.SECONDS).also { assertTrue(it.error?.message,it.isSuccess) }
    private fun details(id: String)=EngineRuntime.projectedModuleDetails(context,id,fit(id).revision).get(30,TimeUnit.SECONDS)
    private fun item(name: String)=EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS).items.single { it.name==name }.id
    private fun history(id: String)=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
    private fun changed(id: String,action: () -> Unit) { val before=fit(id).revision; action(); waitFor { fit(id).revision>before }; settled(id) }
    private fun undo(id: String,redo: Boolean=false) {
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision==fit(id).revision }
        changed(id) { click(if(redo)"history-redo" else "history-undo") }
    }
    private fun prepare() {
        assertEquals("projected_module_bulk",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
    }
    private fun create(environment: Boolean=false,ship: String="Rifter"): String = send(BridgeOperation.CreateFit(FitSpec(
        "Projected bulk $ship ${System.nanoTime()}",ship,5,false,DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),
        emptyList(),emptyList(),environments=if(environment)listOf(EnvironmentSpec("Class 1 Red Giant Effects",ModuleState.ONLINE)) else emptyList()))).fits.single().id
    private fun seed(environment: Boolean=false): String {
        val id=create(environment)
        repeat(3) { send(BridgeOperation.AddProjectedModule(id,item("Remote Sensor Booster II")),id) }
        val rows=details(id).modules.filter { it.editable }
        send(BridgeOperation.SetProjectedModuleCharge(id,rows[1].index,rows[1].objectKey,item("Scan Resolution Script")),id)
        send(BridgeOperation.SetProjectedModuleRange(id,rows[1].index,rows[1].objectKey,63.7),id)
        send(BridgeOperation.SetProjectedModuleRange(id,rows[2].index,rows[2].objectKey,0.0),id)
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        click("projected-modules-open"); settled(id); return id
    }

    @Test fun noncontiguousBulkActionsHaveRealEffectsOneHistoryEntryAndExactUndo() {
        prepare(); val id=seed(); val original=model.currentDetails!!.modules.toList(); val originalStats=fit(id).stats
        val recent=EngineRuntime.recent.value.toList(); val scan=fit(id).stats.getValue("scan_resolution").value.numberOrNull()!!
        click("projected-module-2-bulk-select"); click("projected-module-0-bulk-select")
        assertEquals(listOf(2,0),model.bulkSelection!!.rows.map { it.index })
        compose.onNodeWithTag("projected-modules-bulk-ranges").assertTextContains("Mixed",substring=true)
        var before=history(id).undoCount
        changed(id) { click("projected-modules-bulk-state-inactive") }
        assertEquals(before+1,history(id).undoCount)
        assertEquals(original[1],model.currentDetails!!.modules[1])
        assertTrue(model.currentDetails!!.modules.filter { it.index!=1 }.all { it.state==ModuleState.OFFLINE })
        assertTrue(fit(id).stats.getValue("scan_resolution").value.numberOrNull()!!<scan)
        compose.onNodeWithTag("projected-modules-bulk-stale").assertExists()
        compose.onNodeWithTag("projected-modules-bulk-remove").assertIsNotEnabled()
        undo(id); assertEquals(original,model.currentDetails!!.modules); assertEquals(originalStats,fit(id).stats)
        undo(id,true); assertTrue(model.currentDetails!!.modules.filter { it.index!=1 }.all { it.state==ModuleState.OFFLINE })
        undo(id); click("projected-modules-bulk-review")
        click("projected-modules-bulk-range-edit")
        compose.onNodeWithTag("projected-modules-bulk-range-save").assertIsNotEnabled()
        text("projected-modules-bulk-range-input","0")
        before=history(id).undoCount
        changed(id) { click("projected-modules-bulk-range-save") }
        assertEquals(before+1,history(id).undoCount); assertEquals(original[1],model.currentDetails!!.modules[1])
        assertTrue(model.currentDetails!!.modules.filter { it.index!=1 }.all { it.rangeM==0.0 })
        undo(id); assertEquals(original,model.currentDetails!!.modules)
        click("projected-modules-bulk-review"); before=history(id).undoCount
        changed(id) { click("projected-modules-bulk-remove") }
        assertNull(model.bulkSelection); assertEquals(before+1,history(id).undoCount)
        assertEquals(listOf(original[1].copy(index=0)),model.currentDetails!!.modules)
        undo(id); assertEquals(original,model.currentDetails!!.modules); assertEquals(originalStats,fit(id).stats)
        assertEquals(recent,EngineRuntime.recent.value)
        // The original single-row script/variation/spool route remains reachable.
        click("projected-module-1-options"); waitFor { model.currentOptions?.index==1 && !model.optionsLoading }
        assertEquals(item("Scan Resolution Script"),model.currentDetails!!.modules[1].chargeId)
        compose.onNodeWithTag("projected-module-1-charges").assertExists()
    }

    @Test fun retainedMixedDraftRecreationNavigationStaleDeletionAndDefaultRemainExplicit() {
        prepare(); val id=seed(environment=true)
        compose.onNodeWithTag("projected-module-0-bulk-select").assertIsNotEnabled()
        click("projected-module-3-bulk-select"); click("projected-module-1-bulk-select")
        val identities=model.bulkSelection!!.rows.map { it.objectKey }
        click("projected-modules-bulk-range-edit"); text("projected-modules-bulk-range-input","1.25")
        val retained=model; compose.activityRule.scenario.recreate(); settled(id)
        assertSame(retained,model); assertEquals("1.25",model.bulkDraft!!.text); assertEquals(identities,model.bulkSelection!!.rows.map { it.objectKey })
        click("projected-modules-back"); click("projected-modules-open"); settled(id)
        assertEquals("1.25",model.bulkDraft!!.text)
        send(BridgeOperation.RenameFit(id,"Bulk range renamed ${System.nanoTime()}"),id); settled(id)
        compose.onNodeWithTag("projected-modules-bulk-stale").assertExists()
        compose.onNodeWithTag("projected-modules-bulk-range-save").assertIsNotEnabled()
        assertEquals("1.25",model.bulkDraft!!.text)
        click("projected-modules-bulk-review")
        assertEquals(ProjectedModuleBulkRangeMode.MIXED,model.bulkDraft!!.mode)
        click("projected-modules-bulk-range-default")
        changed(id) { click("projected-modules-bulk-range-save") }
        assertTrue(model.currentDetails!!.modules.filter { it.objectKey in identities }.all { it.rangeM==null })
        assertFalse(model.currentDetails!!.modules.first().editable)
        click("projected-modules-bulk-review"); click("projected-modules-bulk-range-edit")
        val unchanged=fit(id); val unchangedHistory=history(id)
        click("projected-modules-bulk-range-default"); click("projected-modules-bulk-range-save")
        assertNull(model.bulkDraft); assertEquals(unchanged,fit(id)); assertEquals(unchangedHistory,history(id))
        click("projected-modules-bulk-range-edit"); text("projected-modules-bulk-range-input","2.5")
        val removed=model.bulkSelection!!.rows.first()
        send(BridgeOperation.RemoveProjectedModule(id,removed.index,removed.objectKey),id); settled(id)
        assertEquals("2.5",model.bulkDraft!!.text); assertEquals(2,model.bulkSelection!!.rows.size)
        compose.onNodeWithTag("projected-modules-bulk-review").assertIsNotEnabled()
        compose.onNodeWithTag("projected-modules-bulk-range-save").assertIsNotEnabled()
        click("projected-modules-bulk-clear"); assertNull(model.bulkDraft); assertNull(model.bulkSelection)
        val structure=create(ship="Fortizar"); EngineRuntime.selectFit(context,structure).get(30,TimeUnit.SECONDS); settled(structure)
        compose.onNodeWithTag("projected-modules-bulk-select-page").assertIsNotEnabled()
    }
}
