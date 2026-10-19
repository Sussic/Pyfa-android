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

/** Deferred device gate: projected_modules phase, disposable durable data and airplane mode. */
@RunWith(AndroidJUnit4::class)
class ProjectedModuleEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[ProjectedModuleModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000,test); compose.waitForIdle() }
    private fun settled(id: String) = waitFor { !model.editing && !model.loading && model.currentDetails?.let { it.fitId == id && it.revision == fit(id).revision } == true }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String,value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun prepare() {
        assertEquals("projected_modules",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
    }
    private fun send(operation: BridgeOperation,vararg ids: String): BridgeResponse {
        val result=EngineRuntime.request(context,operation,ids.toSet().associateWith { fit(it).revision }).get(120,TimeUnit.SECONDS)
        assertTrue(result.error?.message,result.isSuccess); return result
    }
    private fun create(ship: String="Rifter",modules: List<ModuleSpec> = emptyList(),environment: Boolean=false): String =
        send(BridgeOperation.CreateFit(FitSpec("Projected module $ship ${System.nanoTime()}",ship,5,false,
            DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),modules,emptyList(),
            environments=if (environment) listOf(EnvironmentSpec("Class 1 Red Giant Effects",ModuleState.ONLINE)) else emptyList()))).fits.single().id
    private fun changed(id: String, action: () -> Unit) {
        val revision=fit(id).revision; action(); waitFor { fit(id).revision > revision }; settled(id)
    }
    private fun item(name: String) = EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS).items.single { it.name == name }
    private fun project(id: String,name: String) {
        click("projected-modules-browse")
        val equipment=ViewModelProvider(compose.activity)[EquipmentModel::class.java]
        waitFor { equipment.catalog != null }
        val item=item(name)
        compose.runOnUiThread { equipment.selectedId=item.id }
        waitFor { !model.addLoading && model.currentAdd(item.id) != null }
        assertTrue(model.currentAdd(item.id)!!.enabled)
        changed(id) { click("equipment-project-module") }
        compose.onNodeWithTag("projected-modules-recipient").assertExists()
    }
    private fun options(index: Int): ProjectedModuleOptions {
        waitFor { !model.optionsLoading }
        click("projected-module-$index-options")
        waitFor { !model.optionsLoading && model.currentOptions?.index == index }
        return model.currentOptions!!
    }
    private fun history(id: String,redo: Boolean=false) {
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision == fit(id).revision }
        changed(id) { click(if (redo) "history-redo" else "history-undo") }
    }
    private fun range(id: String,index: Int,value: String) {
        click("projected-module-$index-edit-range"); text("projected-module-range-input",value)
        changed(id) { click("projected-module-range-save") }
    }
    private fun scan(id: String) = fit(id).stats.getValue("scan_resolution").value.numberOrNull()!!
    private fun armor(id: String) = EngineRuntime.tankDetails(context,id).get(30,TimeUnit.SECONDS)
        .modes.getValue("raw").reinforced.repairs.getValue("armorRepair").value.numberOrNull()!!

    @Test fun equipmentScriptRangeStateVariationDuplicateIdentityAndExactUndoReachActualEffects() {
        prepare(); val id=create()
        // Original projector commands fill empty local slots. Materialize that same
        // postcondition before the exact all-stat baseline, including gun ranges.
        send(BridgeOperation.AddProjectedModule(id,item("Remote Sensor Booster II").id),id)
        val setup=EngineRuntime.projectedModuleDetails(context,id,fit(id).revision).get(30,TimeUnit.SECONDS).modules.single()
        send(BridgeOperation.RemoveProjectedModule(id,setup.index,setup.objectKey),id)
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        val baseline=fit(id).stats; val baselineScan=scan(id); val recent=EngineRuntime.recent.value.toList()
        click("projected-modules-open"); settled(id)
        compose.onNodeWithTag("projected-modules-empty").assertExists()
        project(id,"Remote Sensor Booster II")
        var row=model.currentDetails!!.modules.single()
        val firstKey=row.objectKey
        assertEquals(ModuleState.ACTIVE,row.state); assertNull(row.rangeM); assertTrue(scan(id)>baselineScan)
        var menu=options(row.index)
        val script=item("Scan Resolution Script").id
        assertTrue(menu.charges.any { it.id==script })
        click("projected-module-${row.index}-charges")
        changed(id) { click("projected-module-${row.index}-charge-$script") }
        val scripted=scan(id)
        assertEquals(script,model.currentDetails!!.modules.single().chargeId)
        range(id,row.index,"0"); assertEquals(0.0,model.currentDetails!!.modules.single().rangeM!!,0.0)
        range(id,row.index,"1000"); assertTrue(scan(id)<scripted)
        range(id,row.index,""); assertNull(model.currentDetails!!.modules.single().rangeM)
        assertEquals(scripted,scan(id),0.0)
        menu=options(row.index)
        changed(id) { click("projected-module-${row.index}-state-inactive") }
        assertEquals(ModuleState.OFFLINE,model.currentDetails!!.modules.single().state); assertEquals(baselineScan,scan(id),0.0)
        options(row.index); changed(id) { click("projected-module-${row.index}-state-active") }
        assertEquals(scripted,scan(id),0.0)
        menu=options(row.index)
        if (menu.stateActions.single { it.id==ProjectedModuleStateAction.OVERHEAT }.enabled) {
            changed(id) { click("projected-module-${row.index}-state-overheat") }
            assertEquals(ModuleState.OVERHEATED,model.currentDetails!!.modules.single().state)
            history(id); assertEquals(scripted,scan(id),0.0)
        }
        project(id,"Remote Sensor Booster II")
        assertEquals(2,model.currentDetails!!.modules.size)
        assertEquals(2,model.currentDetails!!.modules.map { it.objectKey }.distinct().size)
        row=model.currentDetails!!.modules.first { it.objectKey==firstKey }
        range(id,row.index,"1.2345")
        val captured=model.currentDetails!!.modules.toList(); val beforeStats=fit(id).stats
        menu=options(row.index); val variant=item("Remote Sensor Booster I").id
        assertTrue(menu.variations.any { it.id==variant && it.enabled })
        click("projected-module-${row.index}-variations")
        compose.onNodeWithTag("projected-module-${row.index}-variation-warning").assertTextContains("Range resets",substring=true)
        changed(id) { click("projected-module-${row.index}-variation-$variant") }
        val replacement=model.currentDetails!!.modules.last()
        assertEquals(variant,replacement.itemId); assertNull(replacement.rangeM); assertNotEquals(firstKey,replacement.objectKey)
        history(id); assertEquals(captured,model.currentDetails!!.modules); assertEquals(beforeStats,fit(id).stats)
        history(id,true); assertEquals(variant,model.currentDetails!!.modules.last().itemId)
        history(id); assertEquals(captured,model.currentDetails!!.modules)
        // A stale anchor at position zero cannot act on a later replacement.
        val stale=model.anchor(model.currentDetails!!.modules.first())!!
        changed(id) { click("projected-module-${captured.first().index}-remove") }
        val after=fit(id)
        compose.runOnUiThread { model.remove(context,stale) }; assertEquals(after,fit(id))
        val remaining=model.currentDetails!!.modules.single()
        changed(id) { click("projected-module-${remaining.index}-remove") }
        assertEquals(baseline,fit(id).stats); assertEquals(recent,EngineRuntime.recent.value)
        history(id); assertEquals(remaining.objectKey,model.currentDetails!!.modules.single().objectKey)
        val feature=EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS)
        val export=EngineRuntime.offlineExportPreview(context,OfflineExportRequest(java.util.UUID.randomUUID().toString(),
            feature.context,id,fit(id).revision,OfflineExportOptions())).get(30,TimeUnit.SECONDS)
        assertTrue(export.ok); assertTrue(export.diagnostics.any { it.message.contains("projected",ignoreCase=true) })
        click("projected-module-${model.currentDetails!!.modules.single().index}-inspect-base")
        compose.onNodeWithTag("inspection-back").assertExists()
        waitFor { ViewModelProvider(compose.activity)[InspectionModel::class.java].details?.target?.context == "base" }
    }

    @Test fun scramblerSpoolLegacyPrefixRetainedDraftRecreationAndEquipmentReturnAreUsable() {
        prepare(); var id=create(modules=listOf(ModuleSpec("5MN Microwarpdrive II",ModuleState.ACTIVE)))
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        val baseline=fit(id)
        click("projected-modules-open"); settled(id); project(id,"Warp Scrambler II")
        assertEquals(ModuleState.ONLINE,fit(id).modules.single { it.name=="5MN Microwarpdrive II" }.state)
        assertTrue(fit(id).stats.getValue("max_velocity").value.numberOrNull()!! < baseline.stats.getValue("max_velocity").value.numberOrNull()!!)
        history(id); assertEquals(baseline.modules,fit(id).modules); assertEquals(baseline.stats,fit(id).stats)
        history(id,true); assertEquals(ModuleState.ONLINE,fit(id).modules.single { it.name=="5MN Microwarpdrive II" }.state)
        id=create(environment=true); EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS); settled(id)
        assertFalse(model.currentDetails!!.modules.single().editable)
        compose.onNodeWithTag("projected-module-0-edit-range").assertIsNotEnabled()
        project(id,"Heavy Mutadaptive Remote Armor Repairer II")
        var row=model.currentDetails!!.modules.single { it.editable }; assertEquals(1,row.index)
        var menu=options(row.index); val maximum=menu.spool!!.maximumCycles
        changed(id) { click("projected-module-${row.index}-spool-0") }; val zero=armor(id)
        menu=options(row.index); assertEquals(0,menu.spool!!.overrideCycles)
        changed(id) { click("projected-module-${row.index}-spool-$maximum") }; assertTrue(armor(id)>zero)
        options(row.index); changed(id) { click("projected-module-${row.index}-spool-reset") }
        menu=options(row.index); assertNull(menu.spool!!.overrideCycles)
        click("projected-module-${row.index}-edit-range"); text("projected-module-range-input","1.25")
        val retained=model; compose.activityRule.scenario.recreate(); settled(id)
        assertSame(retained,model); assertEquals("1.25",model.draft!!.text)
        send(BridgeOperation.RenameFit(id,"Renamed projected range ${System.nanoTime()}"),id); settled(id)
        compose.onNodeWithTag("projected-module-range-stale").assertExists()
        compose.onNodeWithTag("projected-module-range-save").assertIsNotEnabled(); assertEquals("1.25",model.draft!!.text)
        click("projected-module-range-review"); assertEquals("",model.draft!!.text)
        text("projected-module-range-input","0"); changed(id) { click("projected-module-range-save") }
        click("projected-module-${row.index}-edit-range"); text("projected-module-range-input","0.0")
        val noOp=fit(id); val noOpHistory=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
        click("projected-module-range-save"); assertNull(model.draft); assertEquals(noOp,fit(id))
        assertEquals(noOpHistory,EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS))
        click("projected-module-${row.index}-edit-range"); text("projected-module-range-input","2.5")
        row=model.currentDetails!!.modules.single { it.editable }
        send(BridgeOperation.RemoveProjectedModule(id,row.index,row.objectKey),id); settled(id)
        assertEquals("2.5",model.draft!!.text); assertFalse(model.canReview)
        compose.onNodeWithTag("projected-module-range-review").assertIsNotEnabled()
        history(id); assertEquals(row.objectKey,model.currentDetails!!.modules.single { it.editable }.objectKey)
        click("projected-module-range-review"); click("projected-module-range-discard")
        // Browsing a local module and choosing View fitting must not be trapped by the projected route.
        click("projected-modules-browse")
        val equipment=ViewModelProvider(compose.activity)[EquipmentModel::class.java]
        val repair=item("Small Armor Repairer I").id
        compose.runOnUiThread { equipment.selectedId=repair }
        waitFor { model.currentAdd(repair) != null }; assertFalse(model.currentAdd(repair)!!.enabled)
        click("equipment-view-fit"); compose.onNodeWithTag("modules-add").assertExists()
        click("modules-back"); click("projected-modules-open"); settled(id)
        val structure=create("Fortizar"); EngineRuntime.selectFit(context,structure).get(30,TimeUnit.SECONDS); settled(structure)
        compose.onNodeWithTag("projected-modules-structure").assertExists()
        compose.onNodeWithTag("projected-modules-browse").assertIsNotEnabled()
    }
}
