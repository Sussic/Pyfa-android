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

/** Deferred device gate: projected_drones phase, disposable durable data and airplane mode. */
@RunWith(AndroidJUnit4::class)
class ProjectedDroneEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[ProjectedDroneModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000,test); compose.waitForIdle() }
    private fun settled(id: String) = waitFor { !model.editing && !model.loading && model.currentDetails?.let { it.fitId == id && it.revision == fit(id).revision } == true }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String,value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun prepare() {
        assertEquals("projected_drones",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
    }
    private fun send(operation: BridgeOperation,vararg ids: String): BridgeResponse {
        val result=EngineRuntime.request(context,operation,ids.toSet().associateWith { fit(it).revision }).get(120,TimeUnit.SECONDS)
        assertTrue(result.error?.message,result.isSuccess); return result
    }
    private fun create(ship: String="Rifter",modules: List<ModuleSpec> = emptyList(),environment: Boolean=false): String =
        send(BridgeOperation.CreateFit(FitSpec("Projected drone $ship ${System.nanoTime()}",ship,5,false,
            DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),modules,emptyList(),
            environments=if (environment) listOf(EnvironmentSpec("Class 1 Red Giant Effects",ModuleState.ONLINE)) else emptyList()))).fits.single().id
    private fun changed(id: String, action: () -> Unit) {
        val revision=fit(id).revision; action(); waitFor { fit(id).revision > revision }; settled(id)
    }
    private fun item(name: String) = EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS).items.single { it.name == name }
    private fun project(id: String,name: String) {
        click("projected-drones-browse")
        val equipment=ViewModelProvider(compose.activity)[EquipmentModel::class.java]
        waitFor { equipment.catalog != null }
        val item=item(name)
        compose.runOnUiThread { equipment.selectedId=item.id }
        waitFor { !model.addLoading && model.currentAdd(item.id) != null }
        assertTrue(model.currentAdd(item.id)!!.enabled)
        changed(id) { click("equipment-project-drone") }
        compose.onNodeWithTag("projected-drones-recipient").assertExists()
    }
    private fun options(index: Int): ProjectedDroneOptions {
        waitFor { !model.optionsLoading }
        click("projected-drone-$index-options")
        waitFor { !model.optionsLoading && model.currentOptions?.index == index }
        return model.currentOptions!!
    }
    private fun history(id: String,redo: Boolean=false) {
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision == fit(id).revision }
        changed(id) { click(if (redo) "history-redo" else "history-undo") }
    }
    private fun range(id: String,index: Int,value: String) {
        click("projected-drone-$index-edit-range"); text("projected-drone-range-input",value)
        changed(id) { click("projected-drone-draft-save") }
    }
    private fun speed(id: String) = fit(id).stats.getValue("max_velocity").value.numberOrNull()!!
    private fun quantity(id: String,index: Int,value: String) {
        click("projected-drone-$index-edit-amount"); text("projected-drone-amount-input",value)
        changed(id) { click("projected-drone-draft-save") }
    }
    private fun filled(id: String) {
        send(BridgeOperation.AddModule(id,item("Small Armor Repairer I").id),id)
        val position=fit(id).modules.single { it.name=="Small Armor Repairer I" }.index
        send(BridgeOperation.RemoveModule(id,position),id)
    }

    @Test fun equipmentWebQuantityActiveRangeRemovalAndUndoReachRealRecipientEffectsWithoutRecentPromotion() {
        prepare(); val id=create(); filled(id)
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        val baseline=fit(id).stats; val baseSpeed=speed(id); val recent=EngineRuntime.recent.value.toList()
        click("projected-drones-open"); settled(id); project(id,"Warrior SW-300")
        var row=model.currentDetails!!.stacks.single(); val firstKey=row.objectKey
        assertEquals(1,row.amount); assertEquals(1,row.active); assertTrue(speed(id)<baseSpeed)
        val oneSpeed=speed(id)
        project(id,"Warrior SW-300")
        row=model.currentDetails!!.stacks.single()
        assertEquals(firstKey,row.objectKey); assertEquals(2,row.amount); assertEquals(2,row.active)
        assertTrue(speed(id)<oneSpeed); assertEquals(recent,EngineRuntime.recent.value)
        quantity(id,0,"6"); assertEquals(6,model.currentDetails!!.stacks.single().active)
        options(0); changed(id) { click("projected-drone-0-toggle") }
        assertEquals(0,model.currentDetails!!.stacks.single().active); assertEquals(baseSpeed,speed(id),0.0)
        quantity(id,0,"3"); assertEquals(0,model.currentDetails!!.stacks.single().active)
        options(0); changed(id) { click("projected-drone-0-toggle") }
        assertEquals(3,model.currentDetails!!.stacks.single().active); assertTrue(speed(id)<baseSpeed)
        range(id,0,"1000000"); assertEquals(baseSpeed,speed(id),0.0)
        range(id,0,"0"); assertEquals(0.0,model.currentDetails!!.stacks.single().rangeM!!,0.0)
        range(id,0,""); assertNull(model.currentDetails!!.stacks.single().rangeM)
        val before=model.currentDetails!!.stacks.toList(); val stats=fit(id).stats
        changed(id) { click("projected-drone-0-remove-one") }
        assertEquals(2,model.currentDetails!!.stacks.single().amount)
        history(id); assertEquals(before,model.currentDetails!!.stacks); assertEquals(stats,fit(id).stats)
        history(id,true); assertEquals(2,model.currentDetails!!.stacks.single().amount)
        val anchor=model.anchor(model.currentDetails!!.stacks.single())!!
        changed(id) { click("projected-drone-0-remove-stack") }
        assertTrue(model.currentDetails!!.stacks.isEmpty()); assertEquals(baseline,fit(id).stats)
        val removed=fit(id)
        compose.runOnUiThread { model.remove(context,anchor,1) }; assertEquals(removed,fit(id))
        history(id); assertEquals(firstKey,model.currentDetails!!.stacks.single().objectKey)
        quantity(id,0,"0"); assertTrue(model.currentDetails!!.stacks.isEmpty()); assertEquals(baseline,fit(id).stats)
        history(id); assertEquals(2,model.currentDetails!!.stacks.single().amount)
        assertEquals(recent,EngineRuntime.recent.value)
        val feature=EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS)
        val exported=EngineRuntime.offlineExportPreview(context,OfflineExportRequest(java.util.UUID.randomUUID().toString(),
            feature.context,id,fit(id).revision,OfflineExportOptions())).get(30,TimeUnit.SECONDS)
        assertTrue(exported.ok); assertTrue(exported.diagnostics.any { it.message.contains("projected",ignoreCase=true) })
        click("projected-drone-0-inspect-base")
        waitFor { ViewModelProvider(compose.activity)[InspectionModel::class.java].details?.target?.context=="base" }
        compose.onNodeWithTag("inspection-back").assertExists()
    }

    @Test fun variationMergeRetainedDraftRecreationDeletionAndEquipmentRoutesStayBoundToTheirStack() {
        prepare(); val id=create(); filled(id); EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        click("projected-drones-open"); settled(id)
        project(id,"Light Armor Maintenance Bot I"); quantity(id,0,"2"); range(id,0,"1.25")
        var row=model.currentDetails!!.stacks.single(); val originalKey=row.objectKey
        var menu=options(0); val variant=item("Light Armor Maintenance Bot II").id
        assertTrue(menu.variations.any { it.id==variant && it.enabled })
        val before=model.currentDetails!!.stacks.toList(); val stats=fit(id).stats
        click("projected-drone-0-variations")
        compose.onNodeWithTag("projected-drone-0-variation-warning").assertTextContains("default range",substring=true)
        changed(id) { click("projected-drone-0-variation-$variant") }
        assertEquals(variant,model.currentDetails!!.stacks.single().itemId); assertNull(model.currentDetails!!.stacks.single().rangeM)
        assertNotEquals(originalKey,model.currentDetails!!.stacks.single().objectKey)
        history(id); assertEquals(before,model.currentDetails!!.stacks); assertEquals(stats,fit(id).stats)
        // Variation into an existing inactive destination preserves its identity, range and inactivity.
        project(id,"Light Armor Maintenance Bot II"); range(id,1,"0")
        options(1); changed(id) { click("projected-drone-1-toggle") }
        val destination=model.currentDetails!!.stacks.last(); val both=model.currentDetails!!.stacks.toList()
        options(0); click("projected-drone-0-variations")
        changed(id) { click("projected-drone-0-variation-$variant") }
        row=model.currentDetails!!.stacks.single()
        assertEquals(destination.objectKey,row.objectKey); assertEquals(3,row.amount); assertEquals(0,row.active)
        assertEquals(0.0,row.rangeM!!,0.0)
        history(id); assertEquals(both,model.currentDetails!!.stacks)
        click("projected-drone-0-edit-amount"); text("projected-drone-amount-input","4")
        val retained=model; compose.activityRule.scenario.recreate(); settled(id)
        assertSame(retained,model); assertEquals("4",model.draft!!.text)
        send(BridgeOperation.RenameFit(id,"Renamed drone recipient ${System.nanoTime()}"),id); settled(id)
        compose.onNodeWithTag("projected-drone-draft-stale").assertExists()
        compose.onNodeWithTag("projected-drone-draft-save").assertIsNotEnabled()
        click("projected-drone-draft-review"); assertEquals("2",model.draft!!.text)
        val sameFit=fit(id); val sameHistory=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
        text("projected-drone-amount-input","0002"); click("projected-drone-draft-save")
        assertEquals(sameFit,fit(id)); assertEquals(sameHistory,EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS))
        click("projected-drone-0-edit-range"); text("projected-drone-range-input","2.5")
        row=model.currentDetails!!.stacks.first()
        send(BridgeOperation.RemoveProjectedDrone(id,row.index,row.objectKey,row.amount),id); settled(id)
        assertEquals("2.5",model.draft!!.text); assertFalse(model.canReview)
        compose.onNodeWithTag("projected-drone-draft-review").assertIsNotEnabled()
        history(id); assertEquals(row.objectKey,model.currentDetails!!.stacks.first().objectKey)
        click("projected-drone-draft-review"); click("projected-drone-draft-discard")
        click("projected-drones-browse")
        val equipment=ViewModelProvider(compose.activity)[EquipmentModel::class.java]
        val combatDrone=item("Hobgoblin I").id
        compose.runOnUiThread { equipment.selectedId=combatDrone }
        waitFor { model.currentAdd(combatDrone)!=null }
        assertTrue(model.currentAdd(combatDrone)!!.isDrone); assertFalse(model.currentAdd(combatDrone)!!.isProjectable)
        compose.onNodeWithTag("equipment-project-drone").assertDoesNotExist()
        val repair=item("Small Armor Repairer I").id
        compose.runOnUiThread { equipment.selectedId=repair }
        waitFor { model.currentAdd(repair)!=null }; assertFalse(model.currentAdd(repair)!!.enabled)
        click("equipment-view-fit"); compose.onNodeWithTag("modules-add").assertExists()
        click("modules-back"); click("projected-drones-open"); settled(id)
        val structure=create("Fortizar"); EngineRuntime.selectFit(context,structure).get(30,TimeUnit.SECONDS); settled(structure)
        compose.onNodeWithTag("projected-drones-structure").assertExists()
        compose.onNodeWithTag("projected-drones-browse").assertIsNotEnabled()
    }
}
