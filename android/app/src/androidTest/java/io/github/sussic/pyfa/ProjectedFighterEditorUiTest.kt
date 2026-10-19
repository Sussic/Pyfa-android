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

/** Deferred device gate: projected_fighters phase, disposable durable data and airplane mode. */
@RunWith(AndroidJUnit4::class)
class ProjectedFighterEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[ProjectedFighterModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000,test); compose.waitForIdle() }
    private fun settled(id: String) = waitFor { !model.editing && !model.loading && model.currentDetails?.let { it.fitId == id && it.revision == fit(id).revision } == true }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String,value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun prepare() {
        assertEquals("projected_fighters",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
    }
    private fun send(operation: BridgeOperation,vararg ids: String): BridgeResponse {
        val result=EngineRuntime.request(context,operation,ids.toSet().associateWith { fit(it).revision }).get(120,TimeUnit.SECONDS)
        assertTrue(result.error?.message,result.isSuccess); return result
    }
    private fun create(ship: String="Rifter",modules: List<ModuleSpec> = emptyList(),environment: Boolean=false): String =
        send(BridgeOperation.CreateFit(FitSpec("Projected fighter $ship ${System.nanoTime()}",ship,5,false,
            DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),modules,emptyList(),
            environments=if (environment) listOf(EnvironmentSpec("Class 1 Red Giant Effects",ModuleState.ONLINE)) else emptyList()))).fits.single().id
    private fun changed(id: String, action: () -> Unit) {
        val revision=fit(id).revision; action(); waitFor { fit(id).revision > revision }; settled(id)
    }
    private fun item(name: String) = EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS).items.single { it.name == name }
    private fun project(id: String,name: String) {
        click("projected-fighters-browse")
        val equipment=ViewModelProvider(compose.activity)[EquipmentModel::class.java]
        waitFor { equipment.catalog != null }
        val item=item(name)
        compose.runOnUiThread { equipment.selectedId=item.id }
        waitFor { !model.addLoading && model.currentAdd(item.id) != null }
        assertTrue(model.currentAdd(item.id)!!.enabled)
        changed(id) { click("equipment-project-fighter") }
        compose.onNodeWithTag("projected-fighters-recipient").assertExists()
    }
    private fun options(index: Int): ProjectedFighterOptions {
        waitFor { !model.optionsLoading }
        click("projected-fighter-$index-options")
        waitFor { !model.optionsLoading && model.currentOptions?.index == index }
        return model.currentOptions!!
    }
    private fun history(id: String,redo: Boolean=false) {
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision == fit(id).revision }
        changed(id) { click(if (redo) "history-redo" else "history-undo") }
    }
    private fun range(id: String,index: Int,value: String) {
        click("projected-fighter-$index-edit-range"); text("projected-fighter-range-input",value)
        changed(id) { click("projected-fighter-draft-save") }
    }
    private fun speed(id: String) = fit(id).stats.getValue("max_velocity").value.numberOrNull()!!
    private fun quantity(id: String,index: Int,value: String) {
        click("projected-fighter-$index-edit-amount"); text("projected-fighter-amount-input",value)
        changed(id) { click("projected-fighter-draft-save") }
    }
    private fun filled(id: String) {
        send(BridgeOperation.AddModule(id,item("Small Armor Repairer I").id),id)
        val position=fit(id).modules.single { it.name=="Small Armor Repairer I" }.index
        send(BridgeOperation.RemoveModule(id,position),id)
    }

    @Test fun equipmentDuplicatesQuantityMaximumActivationAndAbilitiesHaveRealEffectsWithExactUndo() {
        prepare(); val id=create(); filled(id); EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        val baseline=fit(id).stats; val baseSpeed=speed(id); val recent=EngineRuntime.recent.value.toList()
        click("projected-fighters-open"); settled(id); project(id,"Dromi I")
        val first=model.currentDetails!!.squadrons.single(); assertTrue(first.active); assertEquals(first.maxSize,first.amount)
        assertTrue(first.maxSize>=2); assertTrue(speed(id)<baseSpeed); val firstSpeed=speed(id)
        assertTrue(options(0).abilities.single { it.effectId==6435 }.active)
        // The implemented propulsion ability is editable but has no incoming projected effect.
        assertFalse(options(0).abilities.single { it.effectId==6441 }.active)
        val beforeProp=fit(id).stats
        changed(id) { click("projected-fighter-0-ability-6441") }
        assertTrue(options(0).abilities.single { it.effectId==6441 }.active); assertEquals(beforeProp,fit(id).stats)
        history(id); assertFalse(options(0).abilities.single { it.effectId==6441 }.active); assertEquals(beforeProp,fit(id).stats)
        project(id,"Dromi I")
        assertEquals(2,model.currentDetails!!.squadrons.size)
        assertEquals(listOf(first.itemId,first.itemId),model.currentDetails!!.squadrons.map { it.itemId })
        assertEquals(2,model.currentDetails!!.squadrons.map { it.objectKey }.distinct().size)
        assertTrue(speed(id)<firstSpeed); val bothSpeed=speed(id); val second=model.currentDetails!!.squadrons[1]
        quantity(id,0,"1"); assertEquals(1,model.currentDetails!!.squadrons[0].amount); assertTrue(speed(id)>bothSpeed)
        assertEquals(second,model.currentDetails!!.squadrons[1])
        options(0); changed(id) { click("projected-fighter-0-ability-6435") }
        assertTrue(model.currentDetails!!.squadrons[0].active); assertFalse(options(0).abilities.single { it.effectId==6435 }.active)
        assertEquals(firstSpeed,speed(id),0.0)
        options(1); changed(id) { click("projected-fighter-1-toggle") }; assertEquals(baseSpeed,speed(id),0.0)
        options(0); changed(id) { click("projected-fighter-0-ability-6435") }; assertTrue(speed(id)<baseSpeed)
        options(0); changed(id) { click("projected-fighter-0-toggle") }; assertEquals(baseSpeed,speed(id),0.0)
        quantity(id,0,"2"); assertFalse(model.currentDetails!!.squadrons[0].active); assertEquals(baseSpeed,speed(id),0.0)
        click("projected-fighter-0-edit-amount"); click("projected-fighter-amount-maximum")
        changed(id) { click("projected-fighter-draft-save") }
        assertEquals(first.maxSize,model.currentDetails!!.squadrons[0].amount)
        options(0); changed(id) { click("projected-fighter-0-toggle") }; assertEquals(firstSpeed,speed(id),0.0)
        range(id,0,"1000000"); assertEquals(baseSpeed,speed(id),0.0)
        range(id,0,"0"); assertEquals(0.0,model.currentDetails!!.squadrons[0].rangeM!!,0.0)
        range(id,0,""); assertNull(model.currentDetails!!.squadrons[0].rangeM)
        val before=model.currentDetails!!.squadrons.toList(); val stats=fit(id).stats
        val anchor=model.anchor(before[0])!!
        changed(id) { click("projected-fighter-0-remove") }
        assertEquals(listOf(before[1].copy(index=0)),model.currentDetails!!.squadrons); assertEquals(baseline,fit(id).stats)
        val removed=fit(id); compose.runOnUiThread { model.remove(context,anchor) }; assertEquals(removed,fit(id))
        history(id); assertEquals(before,model.currentDetails!!.squadrons); assertEquals(stats,fit(id).stats)
        history(id,true); assertEquals(1,model.currentDetails!!.squadrons.size)
        history(id); quantity(id,0,"0"); assertEquals(listOf(before[1].copy(index=0)),model.currentDetails!!.squadrons)
        history(id); assertEquals(before,model.currentDetails!!.squadrons)
        assertEquals(recent,EngineRuntime.recent.value)
        val feature=EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS)
        val exported=EngineRuntime.offlineExportPreview(context,OfflineExportRequest(java.util.UUID.randomUUID().toString(),
            feature.context,id,fit(id).revision,OfflineExportOptions())).get(30,TimeUnit.SECONDS)
        assertTrue(exported.ok); assertTrue(exported.diagnostics.any { it.message.contains("fighter",true) && it.message.contains("projected",true) })
        click("projected-fighter-0-inspect-base")
        waitFor { ViewModelProvider(compose.activity)[InspectionModel::class.java].details?.target?.context=="base" }
        compose.onNodeWithTag("inspection-back").assertExists()
    }

    @Test fun variationAppendsWithoutMergingAndDraftRecreationDeletionAndEquipmentRoutesKeepIdentity() {
        prepare(); val id=create(); filled(id); EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        click("projected-fighters-open"); settled(id); project(id,"Dromi I"); quantity(id,0,"2"); range(id,0,"1.25")
        options(0); changed(id) { click("projected-fighter-0-ability-6435") }
        options(0); changed(id) { click("projected-fighter-0-toggle") }
        project(id,"Dromi II"); range(id,1,"0")
        val variant=item("Dromi II").id; val before=model.currentDetails!!.squadrons.toList(); val stats=fit(id).stats
        assertTrue(options(0).variations.any { it.id==variant && it.enabled })
        click("projected-fighter-0-variations")
        compose.onNodeWithTag("projected-fighter-0-variation-warning").assertTextContains("not merged",substring=true)
        changed(id) { click("projected-fighter-0-variation-$variant") }
        val changedRows=model.currentDetails!!.squadrons
        assertEquals(2,changedRows.size); assertEquals(before[1].copy(index=0),changedRows[0])
        assertEquals(variant,changedRows[1].itemId); assertEquals(2,changedRows[1].amount); assertFalse(changedRows[1].active); assertNull(changedRows[1].rangeM)
        assertNotEquals(before[0].objectKey,changedRows[1].objectKey)
        assertFalse(options(1).abilities.single { it.effectId==6435 }.active)
        history(id); assertEquals(before,model.currentDetails!!.squadrons); assertEquals(stats,fit(id).stats)
        assertFalse(options(0).abilities.single { it.effectId==6435 }.active)
        click("projected-fighter-0-edit-range"); text("projected-fighter-range-input","2.5")
        val retained=model; compose.activityRule.scenario.recreate(); settled(id)
        assertSame(retained,model); assertEquals("2.5",model.draft!!.text)
        click("projected-fighters-back"); click("projected-fighters-open"); settled(id); assertEquals("2.5",model.draft!!.text)
        send(BridgeOperation.RenameFit(id,"Renamed fighter recipient ${System.nanoTime()}"),id); settled(id)
        compose.onNodeWithTag("projected-fighter-draft-stale").assertExists()
        compose.onNodeWithTag("projected-fighter-draft-save").assertIsNotEnabled()
        click("projected-fighter-draft-review"); assertEquals("1.25",model.draft!!.text)
        val sameFit=fit(id); val sameHistory=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
        click("projected-fighter-draft-save"); assertEquals(sameFit,fit(id)); assertEquals(sameHistory,EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS))
        click("projected-fighter-0-edit-range"); text("projected-fighter-range-input","2.5")
        val row=model.currentDetails!!.squadrons[0]
        send(BridgeOperation.RemoveProjectedFighter(id,row.index,row.objectKey),id); settled(id)
        assertEquals("2.5",model.draft!!.text); assertFalse(model.canReview)
        compose.onNodeWithTag("projected-fighter-draft-review").assertIsNotEnabled()
        history(id); assertEquals(row.objectKey,model.currentDetails!!.squadrons.first().objectKey)
        click("projected-fighter-draft-review"); click("projected-fighter-draft-discard")
        click("projected-fighters-browse"); val equipment=ViewModelProvider(compose.activity)[EquipmentModel::class.java]
        val combat=item("Firbolg I").id
        compose.runOnUiThread { equipment.selectedId=combat }; waitFor { model.currentAdd(combat)!=null }
        assertTrue(model.currentAdd(combat)!!.isFighter); assertFalse(model.currentAdd(combat)!!.isProjectable)
        compose.onNodeWithTag("equipment-project-fighter").assertDoesNotExist()
        val repair=item("Small Armor Repairer I").id
        compose.runOnUiThread { equipment.selectedId=repair }; waitFor { model.currentAdd(repair)!=null }
        assertFalse(model.currentAdd(repair)!!.enabled)
        click("equipment-view-fit"); compose.onNodeWithTag("modules-add").assertExists()
        click("modules-back"); click("projected-fighters-open"); settled(id)
        val structure=create("Fortizar"); EngineRuntime.selectFit(context,structure).get(30,TimeUnit.SECONDS); settled(structure)
        compose.onNodeWithTag("projected-fighters-structure").assertExists()
        compose.onNodeWithTag("projected-fighters-browse").assertIsNotEnabled()
    }
}
