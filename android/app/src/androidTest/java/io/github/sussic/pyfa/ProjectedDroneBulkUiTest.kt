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

/** Deferred device phase projected_drone_bulk. Real EOS effects; partial inputs also have separate model/source tests. */
@RunWith(AndroidJUnit4::class)
class ProjectedDroneBulkUiTest {
    @get:Rule val compose=createAndroidComposeRule<MainActivity>()
    private val context get()=InstrumentationRegistry.getInstrumentation().targetContext
    private val model get()=ViewModelProvider(compose.activity)[ProjectedDroneModel::class.java]
    private fun fit(id: String)=EngineRuntime.library.value.single { it.id==id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000,test); compose.waitForIdle() }
    private fun settled(id: String)=waitFor { !model.editing && !model.loading && model.currentDetails?.let { it.fitId==id && it.revision==fit(id).revision }==true }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String,value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun send(op: BridgeOperation,vararg ids: String)=EngineRuntime.request(context,op,ids.toSet().associateWith { fit(it).revision })
        .get(120,TimeUnit.SECONDS).also { assertTrue(it.error?.message,it.isSuccess) }
    private fun details(id: String)=EngineRuntime.projectedDroneDetails(context,id,fit(id).revision).get(30,TimeUnit.SECONDS)
    private fun item(name: String)=EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS).items.single { it.name==name }.id
    private fun history(id: String)=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
    private fun speed(id: String)=fit(id).stats.getValue("max_velocity").value.numberOrNull()!!
    private fun changed(id: String,action: () -> Unit) { val before=fit(id).revision; action(); waitFor { fit(id).revision>before }; settled(id) }
    private fun undo(id: String,redo: Boolean=false) {
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision==fit(id).revision }
        changed(id) { click(if(redo)"history-redo" else "history-undo") }
    }
    private fun prepare() {
        assertEquals("projected_drone_bulk",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
    }
    private fun create(ship: String="Rifter",modules: List<ModuleSpec> = emptyList()): String = send(BridgeOperation.CreateFit(FitSpec(
        "Projected drone bulk $ship ${System.nanoTime()}",ship,5,false,DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),
        modules,emptyList()))).fits.single().id
    private fun seed(blockAssistance: Boolean=false): String {
        val id=if(blockAssistance) create("Broadsword",listOf(ModuleSpec("Warp Disruption Field Generator I",ModuleState.ACTIVE))) else create()
        for (name in listOf("Warrior SW-300","Light Shield Maintenance Bot I","Light Armor Maintenance Bot I")) {
            send(BridgeOperation.AddProjectedDrone(id,item(name)),id)
            val row=details(id).stacks.single { it.name==name }
            send(BridgeOperation.SetProjectedDroneAmount(id,row.index,row.objectKey,3),id)
        }
        val rows=details(id).stacks
        send(BridgeOperation.SetProjectedDroneRange(id,rows[1].index,rows[1].objectKey,63.7),id)
        send(BridgeOperation.SetProjectedDroneRange(id,rows[2].index,rows[2].objectKey,0.0),id)
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        click("projected-drones-open"); settled(id); return id
    }

    @Test fun noncontiguousActivationRangesAndWholeStackRemovalHaveRealEffectsAndExactAtomicUndo() {
        prepare(); val id=seed(); val original=model.currentDetails!!.stacks.toList(); val originalStats=fit(id).stats
        val recent=EngineRuntime.recent.value.toList(); val webbed=speed(id)
        click("projected-drone-2-bulk-select"); click("projected-drone-0-bulk-select")
        assertEquals(listOf(2,0),model.bulkSelection!!.rows.map { it.index })
        compose.onNodeWithTag("projected-drones-bulk-ranges").assertTextContains("Mixed",substring=true)
        compose.onNodeWithTag("projected-drones-bulk-activation-policy").assertTextContains("partial",substring=true)
        var before=history(id).undoCount
        changed(id) { click("projected-drones-bulk-active-false") }
        assertEquals(before+1,history(id).undoCount); assertEquals(original[1],model.currentDetails!!.stacks[1])
        assertTrue(model.currentDetails!!.stacks.filter { it.index!=1 }.all { it.active==0 && it.amount==3 })
        assertTrue(speed(id)>webbed)
        compose.onNodeWithTag("projected-drones-bulk-stale").assertExists()
        compose.onNodeWithTag("projected-drones-bulk-remove").assertIsNotEnabled()
        undo(id); assertEquals(original,model.currentDetails!!.stacks); assertEquals(originalStats,fit(id).stats)
        undo(id,true); assertTrue(model.currentDetails!!.stacks.filter { it.index!=1 }.all { it.active==0 })
        click("projected-drones-bulk-review"); before=history(id).undoCount
        changed(id) { click("projected-drones-bulk-active-true") }
        assertEquals(before+1,history(id).undoCount); assertEquals(original,model.currentDetails!!.stacks); assertEquals(originalStats,fit(id).stats)
        click("projected-drones-bulk-review"); before=history(id).undoCount
        // Filled, unchanged active inputs: publication can advance revision without semantic history.
        changed(id) { click("projected-drones-bulk-active-true") }
        assertEquals(before,history(id).undoCount); assertEquals(original,model.currentDetails!!.stacks)
        click("projected-drones-bulk-review"); click("projected-drones-bulk-range-edit")
        compose.onNodeWithTag("projected-drones-bulk-range-save").assertIsNotEnabled()
        text("projected-drones-bulk-range-input","0"); before=history(id).undoCount
        changed(id) { click("projected-drones-bulk-range-save") }
        assertEquals(before+1,history(id).undoCount); assertEquals(original[1],model.currentDetails!!.stacks[1])
        assertTrue(model.currentDetails!!.stacks.filter { it.index!=1 }.all { it.rangeM==0.0 })
        undo(id); assertEquals(original,model.currentDetails!!.stacks)
        click("projected-drones-bulk-review"); before=history(id).undoCount
        changed(id) { click("projected-drones-bulk-remove") }
        assertNull(model.bulkSelection); assertEquals(before+1,history(id).undoCount)
        assertEquals(listOf(original[1].copy(index=0)),model.currentDetails!!.stacks)
        undo(id); assertEquals(original,model.currentDetails!!.stacks); assertEquals(originalStats,fit(id).stats)
        assertEquals(recent,EngineRuntime.recent.value)
        // Single-row Remove one and quantity are still distinct reachable commands.
        changed(id) { click("projected-drone-0-remove-one") }
        assertEquals(2,model.currentDetails!!.stacks[0].amount)
        undo(id); assertEquals(original,model.currentDetails!!.stacks)
        click("projected-drone-0-edit-amount"); text("projected-drone-amount-input","4")
        changed(id) { click("projected-drone-draft-save") }; assertEquals(4,model.currentDetails!!.stacks[0].amount)
        undo(id); assertEquals(original,model.currentDetails!!.stacks)
    }

    @Test fun recipientBlockedActivationAndRetainedDraftRecreationReviewDeletionStayTruthful() {
        prepare(); val id=seed(blockAssistance=true)
        val web=model.currentDetails!!.stacks[0]; val armor=model.currentDetails!!.stacks[2]
        val webOptions=EngineRuntime.projectedDroneOptions(context,id,fit(id).revision,web).get(30,TimeUnit.SECONDS)
        val armorOptions=EngineRuntime.projectedDroneOptions(context,id,fit(id).revision,armor).get(30,TimeUnit.SECONDS)
        assertTrue(webOptions.activationAllowed); assertFalse(armorOptions.activationAllowed)
        click("projected-drone-2-bulk-select"); click("projected-drone-0-bulk-select")
        changed(id) { click("projected-drones-bulk-active-false") }
        val inactive=model.currentDetails!!.stacks.toList(); val fast=speed(id)
        click("projected-drones-bulk-review"); val before=history(id).undoCount
        changed(id) { click("projected-drones-bulk-active-true") }
        assertEquals(before+1,history(id).undoCount)
        assertEquals(3,model.currentDetails!!.stacks[0].active); assertEquals(0,model.currentDetails!!.stacks[2].active)
        assertEquals(inactive[1],model.currentDetails!!.stacks[1]); assertTrue(speed(id)<fast)
        assertTrue(model.message!!.contains("may stay unchanged"))
        undo(id); assertEquals(inactive,model.currentDetails!!.stacks)
        click("projected-drones-bulk-review"); click("projected-drones-bulk-range-edit"); text("projected-drones-bulk-range-input","1.25")
        val identities=model.bulkSelection!!.rows.map { it.objectKey }; val retained=model
        compose.activityRule.scenario.recreate(); settled(id)
        assertSame(retained,model); assertEquals("1.25",model.bulkDraft!!.text); assertEquals(identities,model.bulkSelection!!.rows.map { it.objectKey })
        click("projected-drones-back"); click("projected-drones-open"); settled(id); assertEquals("1.25",model.bulkDraft!!.text)
        send(BridgeOperation.RenameFit(id,"Drone bulk renamed ${System.nanoTime()}"),id); settled(id)
        compose.onNodeWithTag("projected-drones-bulk-stale").assertExists()
        compose.onNodeWithTag("projected-drones-bulk-range-save").assertIsNotEnabled(); assertEquals("1.25",model.bulkDraft!!.text)
        click("projected-drones-bulk-review"); assertEquals(ProjectedDroneBulkRangeMode.MIXED,model.bulkDraft!!.mode)
        click("projected-drones-bulk-range-default"); changed(id) { click("projected-drones-bulk-range-save") }
        assertTrue(model.currentDetails!!.stacks.filter { it.objectKey in identities }.all { it.rangeM==null })
        click("projected-drones-bulk-review"); click("projected-drones-bulk-range-edit")
        val unchanged=fit(id); val unchangedHistory=history(id)
        click("projected-drones-bulk-range-default"); click("projected-drones-bulk-range-save")
        assertNull(model.bulkDraft); assertEquals(unchanged,fit(id)); assertEquals(unchangedHistory,history(id))
        click("projected-drones-bulk-range-edit"); text("projected-drones-bulk-range-input","2.5")
        val removed=model.bulkSelection!!.rows.first()
        send(BridgeOperation.RemoveProjectedDrone(id,removed.index,removed.objectKey,removed.amount),id); settled(id)
        assertEquals("2.5",model.bulkDraft!!.text); assertEquals(2,model.bulkSelection!!.rows.size)
        compose.onNodeWithTag("projected-drones-bulk-review").assertIsNotEnabled(); compose.onNodeWithTag("projected-drones-bulk-range-save").assertIsNotEnabled()
        click("projected-drones-bulk-clear"); assertNull(model.bulkDraft); assertNull(model.bulkSelection)
        val structure=create("Fortizar"); EngineRuntime.selectFit(context,structure).get(30,TimeUnit.SECONDS); settled(structure)
        compose.onNodeWithTag("projected-drones-bulk-select-page").assertIsNotEnabled()
    }
}
