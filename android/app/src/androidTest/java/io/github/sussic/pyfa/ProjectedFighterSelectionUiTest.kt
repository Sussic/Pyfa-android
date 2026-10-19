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

/** Deferred projected_fighter_selection phase. Read-only selection and an actual existing bulk action. */
@RunWith(AndroidJUnit4::class)
class ProjectedFighterSelectionUiTest {
    @get:Rule val compose=createAndroidComposeRule<MainActivity>()
    private val context get()=InstrumentationRegistry.getInstrumentation().targetContext
    private val model get()=ViewModelProvider(compose.activity)[ProjectedFighterModel::class.java]
    private fun fit(id: String)=EngineRuntime.library.value.single { it.id==id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000,test); compose.waitForIdle() }
    private fun settled(id: String)=waitFor { !model.loading && !model.editing && model.currentDetails?.revision==fit(id).revision && model.currentDetails?.fitId==id }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun send(op: BridgeOperation,vararg ids: String)=EngineRuntime.request(context,op,ids.toSet().associateWith { fit(it).revision })
        .get(120,TimeUnit.SECONDS).also { assertTrue(it.error?.message,it.isSuccess) }
    private fun details(id: String)=EngineRuntime.projectedFighterDetails(context,id,fit(id).revision).get(30,TimeUnit.SECONDS)
    private fun options(id: String,index: Int)=EngineRuntime.projectedFighterOptions(context,id,fit(id).revision,details(id).squadrons[index]).get(30,TimeUnit.SECONDS)
    private fun bits(id: String)=details(id).squadrons.map { options(id,it.index).abilities }
    private fun history(id: String)=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
    private fun changed(id: String,action: () -> Unit) { val revision=fit(id).revision;action();waitFor { fit(id).revision>revision };settled(id) }
    private fun similar(index: Int,expected: List<Int>) {
        click("projected-fighter-$index-select-similar")
        waitFor { !model.selectingSimilar && model.bulkSelection?.rows?.map { it.index }==expected }
        assertEquals(model.currentDetails!!.squadrons[index].objectKey,model.bulkMainKey)
    }
    private fun seed(): String {
        assertEquals("projected_fighter_selection",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val id=send(BridgeOperation.CreateFit(FitSpec("Incoming selection ${System.nanoTime()}","Rifter",5,false,
            DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),emptyList(),emptyList()))).fits.single().id
        val catalog=EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS)
        for (name in listOf("Dromi I","Siren I","Dromi II","Dromi I")) {
            send(BridgeOperation.AddProjectedFighter(id,catalog.items.single { it.name==name }.id),id)
        }
        val rows=details(id).squadrons
        for (index in listOf(2,3)) send(BridgeOperation.ToggleProjectedFighterAbility(id,rows[index].index,rows[index].objectKey,6435),id)
        send(BridgeOperation.SetProjectedFighterActive(id,3,rows[3].objectKey,false),id)
        send(BridgeOperation.SetProjectedFighterAmount(id,3,rows[3].objectKey,1),id)
        send(BridgeOperation.SetProjectedFighterRange(id,3,rows[3].objectKey,0.0),id)
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        click("projected-fighters-open");settled(id);return id
    }

    @Test fun sameTypeAndSimilarReplaceSelectionReadOnlyAndRetainMainAcrossRecreationAndDrafts() {
        val id=seed();val before=fit(id);val beforeRows=details(id).squadrons;val beforeBits=bits(id)
        val beforeHistory=history(id);val beforeRecent=EngineRuntime.recent.value.toList()
        val beforeContext=EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS).context
        click("projected-fighter-1-bulk-select")
        click("projected-fighter-3-select-type")
        assertEquals(listOf(0,3),model.bulkSelection!!.rows.map { it.index });assertEquals(beforeRows[3].objectKey,model.bulkMainKey)
        similar(3,listOf(0,2,3))
        assertEquals(2,model.bulkSelection!!.rows.map { it.itemId }.distinct().size)
        assertEquals(3,model.bulkSelection!!.rows.map { it.objectKey }.distinct().size)
        assertEquals(before,fit(id));assertEquals(beforeHistory,history(id));assertEquals(beforeRows,details(id).squadrons);assertEquals(beforeBits,bits(id))
        assertEquals(beforeRecent,EngineRuntime.recent.value)
        assertEquals(beforeContext,EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS).context)
        val selected=model.bulkSelection;val main=model.bulkMainKey;val retained=model
        compose.activityRule.scenario.recreate();settled(id)
        assertSame(retained,model);assertSame(selected,model.bulkSelection);assertEquals(main,model.bulkMainKey)
        click("projected-fighters-back");click("projected-fighters-open");settled(id)
        assertSame(selected,model.bulkSelection);assertEquals(main,model.bulkMainKey)
        click("projected-fighters-bulk-range-edit")
        compose.onNodeWithTag("projected-fighters-bulk-range-input").performScrollTo().performTextReplacement("1.25")
        compose.onNodeWithTag("projected-fighter-0-select-type").assertIsNotEnabled()
        compose.onNodeWithTag("projected-fighter-0-select-similar").assertIsNotEnabled()
        compose.activityRule.scenario.recreate();settled(id);assertEquals("1.25",model.bulkDraft!!.text)
        send(BridgeOperation.RenameFit(id,"Selection stale ${System.nanoTime()}"),id);settled(id)
        compose.onNodeWithTag("projected-fighter-0-select-similar").assertIsNotEnabled();assertSame(selected,model.bulkSelection)
        click("projected-fighters-bulk-review");assertEquals(main,model.bulkMainKey)
        click("projected-fighters-bulk-range-discard");click("projected-fighter-2-select-type")
        assertEquals(listOf(2),model.bulkSelection!!.rows.map { it.index });assertEquals(beforeRows[2].objectKey,model.bulkMainKey)
        assertEquals(beforeRows,details(id).squadrons);assertEquals(beforeBits,bits(id));assertEquals(beforeRecent,EngineRuntime.recent.value)
    }

    @Test fun crossTypeSelectionFeedsOneRealBulkAbilityEditAndExactUndoWithoutTouchingExcludedFamily() {
        val id=seed();val original=fit(id);val rows=details(id).squadrons;val abilities=bits(id);val recent=EngineRuntime.recent.value.toList()
        val originalSpeed=original.stats.getValue("max_velocity").value.numberOrNull()!!
        similar(3,listOf(0,2,3))
        click("projected-fighters-bulk-main-load");waitFor { model.bulkMainOptions?.index==3 && !model.optionsLoading }
        assertFalse(model.bulkMainOptions!!.abilities.single { it.effectId==6435 }.active)
        val count=history(id).undoCount
        changed(id) { click("projected-fighters-bulk-ability-6435") }
        assertEquals(count+1,history(id).undoCount)
        for (index in listOf(0,2,3)) assertTrue(options(id,index).abilities.single { it.effectId==6435 }.active)
        assertEquals(rows,details(id).squadrons);assertEquals(abilities[1],options(id,1).abilities)
        assertTrue(fit(id).stats.getValue("max_velocity").value.numberOrNull()!!<originalSpeed)
        send(BridgeOperation.Undo(id),id);settled(id)
        assertEquals(rows,details(id).squadrons);assertEquals(abilities,bits(id));assertEquals(original.stats,fit(id).stats)
        click("projected-fighters-bulk-review");similar(0,listOf(0,2,3))
        val undoCount=history(id).undoCount
        changed(id) { click("projected-fighters-bulk-active-false") }
        assertEquals(undoCount+1,history(id).undoCount)
        assertEquals(rows[1],details(id).squadrons[1]);assertEquals(abilities,bits(id));assertTrue(details(id).squadrons.filter { it.index!=1 }.none { it.active })
        send(BridgeOperation.Undo(id),id);settled(id)
        assertEquals(rows,details(id).squadrons);assertEquals(original.stats,fit(id).stats);assertEquals(recent,EngineRuntime.recent.value)
    }
}
