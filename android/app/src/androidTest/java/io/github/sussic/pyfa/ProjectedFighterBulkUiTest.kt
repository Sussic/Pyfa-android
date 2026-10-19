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

/** Deferred projected_fighter_bulk device phase. Real EOS interactions; independent numeric parity remains host proof. */
@RunWith(AndroidJUnit4::class)
class ProjectedFighterBulkUiTest {
    @get:Rule val compose=createAndroidComposeRule<MainActivity>()
    private val context get()=InstrumentationRegistry.getInstrumentation().targetContext
    private val model get()=ViewModelProvider(compose.activity)[ProjectedFighterModel::class.java]
    private fun fit(id: String)=EngineRuntime.library.value.single { it.id==id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000,test); compose.waitForIdle() }
    private fun settled(id: String)=waitFor { !model.editing && !model.loading && model.currentDetails?.let { it.fitId==id && it.revision==fit(id).revision }==true }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String,value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun send(op: BridgeOperation,vararg ids: String)=EngineRuntime.request(context,op,ids.toSet().associateWith { fit(it).revision })
        .get(120,TimeUnit.SECONDS).also { assertTrue(it.error?.message,it.isSuccess) }
    private fun details(id: String)=EngineRuntime.projectedFighterDetails(context,id,fit(id).revision).get(30,TimeUnit.SECONDS)
    private fun options(id: String,index: Int)=EngineRuntime.projectedFighterOptions(context,id,fit(id).revision,details(id).squadrons[index]).get(30,TimeUnit.SECONDS)
    private fun bits(id: String)=details(id).squadrons.map { row -> options(id,row.index).abilities }
    private fun item(name: String)=EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS).items.single { it.name==name }.id
    private fun history(id: String)=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
    private fun speed(id: String)=fit(id).stats.getValue("max_velocity").value.numberOrNull()!!
    private fun changed(id: String,action: () -> Unit) { val before=fit(id).revision; action(); waitFor { fit(id).revision>before }; settled(id) }
    private fun undo(id: String,redo: Boolean=false) {
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision==fit(id).revision }
        changed(id) { click(if(redo)"history-redo" else "history-undo") }
    }
    private fun mainRow(index: Int) { click("projected-fighter-$index-bulk-main"); waitFor { !model.optionsLoading && model.currentOptions?.index==index } }
    private fun prepare() {
        assertEquals("projected_fighter_bulk",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
    }
    private fun create(ship: String="Rifter"): String = send(BridgeOperation.CreateFit(FitSpec(
        "Projected fighter bulk $ship ${System.nanoTime()}",ship,5,false,DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),
        emptyList(),emptyList()))).fits.single().id
    private fun seed(): String {
        val id=create()
        for (name in listOf("Dromi I","Dromi II","Dromi I","Siren I")) send(BridgeOperation.AddProjectedFighter(id,item(name)),id)
        val rows=details(id).squadrons
        send(BridgeOperation.SetProjectedFighterRange(id,rows[1].index,rows[1].objectKey,63.7),id)
        send(BridgeOperation.SetProjectedFighterRange(id,rows[2].index,rows[2].objectKey,0.0),id)
        send(BridgeOperation.ToggleProjectedFighterAbility(id,rows[2].index,rows[2].objectKey,6435),id)
        assertFalse(options(id,3).abilities.any { it.effectId==6435 })
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        click("projected-fighters-open"); settled(id); return id
    }

    @Test fun noncontiguousStateRangeAndRemovalAreAtomicAndMainAbilitySetsOneDirectionSkippingMissing() {
        prepare(); val id=seed(); val original=model.currentDetails!!.squadrons.toList(); val originalBits=bits(id)
        val originalStats=fit(id).stats; val recent=EngineRuntime.recent.value.toList(); val webbed=speed(id)
        assertEquals(original[0].itemId,original[2].itemId); assertNotEquals(original[0].objectKey,original[2].objectKey)
        click("projected-fighter-2-bulk-select"); click("projected-fighter-0-bulk-select")
        assertEquals(listOf(2,0),model.bulkSelection!!.rows.map { it.index })
        compose.onNodeWithTag("projected-fighters-bulk-ranges").assertTextContains("Mixed",substring=true)
        var before=history(id).undoCount
        changed(id) { click("projected-fighters-bulk-active-false") }
        assertEquals(before+1,history(id).undoCount); assertTrue(speed(id)>webbed)
        assertEquals(original[1],model.currentDetails!!.squadrons[1]); assertEquals(original[3],model.currentDetails!!.squadrons[3])
        assertEquals(originalBits,bits(id)); assertTrue(model.currentDetails!!.squadrons.filter { it.index in setOf(0,2) }.none { it.active })
        compose.onNodeWithTag("projected-fighters-bulk-remove").assertIsNotEnabled()
        undo(id); assertEquals(original,model.currentDetails!!.squadrons); assertEquals(originalStats,fit(id).stats)
        undo(id,true); click("projected-fighters-bulk-review")
        changed(id) { click("projected-fighters-bulk-active-true") }; assertEquals(original,model.currentDetails!!.squadrons)
        click("projected-fighters-bulk-review"); val unchanged=fit(id); val unchangedHistory=history(id)
        click("projected-fighters-bulk-active-true"); assertEquals(unchanged,fit(id)); assertEquals(unchangedHistory,history(id))
        click("projected-fighter-3-bulk-select"); mainRow(2)
        compose.onNodeWithTag("projected-fighters-bulk-main").assertTextContains("3 · Dromi I",substring=true)
        compose.onNodeWithTag("projected-fighters-bulk-ability-policy").assertTextContains("without the ability",substring=true)
        before=history(id).undoCount
        changed(id) { click("projected-fighters-bulk-ability-6435") }
        assertEquals(before+1,history(id).undoCount)
        assertTrue(options(id,0).abilities.single { it.effectId==6435 }.active)
        assertTrue(options(id,2).abilities.single { it.effectId==6435 }.active) // Set from main once, not individual inversion.
        assertEquals(originalBits[3],options(id,3).abilities); assertEquals(originalBits[1],options(id,1).abilities)
        assertEquals(original,model.currentDetails!!.squadrons); assertTrue(speed(id)<webbed)
        undo(id); assertEquals(originalBits,bits(id)); assertEquals(originalStats,fit(id).stats)
        click("projected-fighters-bulk-review"); mainRow(0)
        changed(id) { click("projected-fighters-bulk-ability-6435") }
        assertFalse(options(id,0).abilities.single { it.effectId==6435 }.active)
        assertFalse(options(id,2).abilities.single { it.effectId==6435 }.active)
        assertEquals(originalBits[3],options(id,3).abilities); assertTrue(speed(id)>webbed)
        undo(id); click("projected-fighters-bulk-review"); click("projected-fighters-bulk-range-edit")
        compose.onNodeWithTag("projected-fighters-bulk-range-save").assertIsNotEnabled()
        text("projected-fighters-bulk-range-input","0"); before=history(id).undoCount
        changed(id) { click("projected-fighters-bulk-range-save") }
        assertEquals(before+1,history(id).undoCount); assertEquals(original[1],model.currentDetails!!.squadrons[1])
        assertTrue(model.currentDetails!!.squadrons.filter { it.index!=1 }.all { it.rangeM==0.0 })
        undo(id); assertEquals(original,model.currentDetails!!.squadrons)
        click("projected-fighters-bulk-review"); before=history(id).undoCount
        changed(id) { click("projected-fighters-bulk-remove") }
        assertNull(model.bulkSelection); assertEquals(before+1,history(id).undoCount)
        assertEquals(listOf(original[1].copy(index=0)),model.currentDetails!!.squadrons)
        undo(id); assertEquals(original,model.currentDetails!!.squadrons); assertEquals(originalBits,bits(id)); assertEquals(originalStats,fit(id).stats)
        assertEquals(recent,EngineRuntime.recent.value)
        // The original single-squadron quantity/Maximum route remains reachable.
        click("projected-fighter-0-edit-amount"); text("projected-fighter-amount-input","1")
        changed(id) { click("projected-fighter-draft-save") }; assertEquals(1,model.currentDetails!!.squadrons[0].amount)
        undo(id); assertEquals(original,model.currentDetails!!.squadrons)
    }

    @Test fun inactiveMainPropulsionAndDraftRecreationStaleReviewAndMissingIdentityStaySafe() {
        prepare(); val id=seed()
        click("projected-fighter-0-bulk-select"); click("projected-fighter-2-bulk-select")
        changed(id) { click("projected-fighters-bulk-active-false") }; click("projected-fighters-bulk-review"); mainRow(0)
        val beforeStats=fit(id).stats; val beforeRows=model.currentDetails!!.squadrons.toList(); val beforeBits=bits(id)
        changed(id) { click("projected-fighters-bulk-ability-6441") }
        assertEquals(beforeStats,fit(id).stats); assertEquals(beforeRows,model.currentDetails!!.squadrons)
        assertTrue(options(id,0).abilities.single { it.effectId==6441 }.active)
        assertTrue(options(id,2).abilities.single { it.effectId==6441 }.active)
        undo(id); assertEquals(beforeBits,bits(id)); click("projected-fighters-bulk-review")
        click("projected-fighters-bulk-range-edit"); text("projected-fighters-bulk-range-input","1.25")
        val keys=model.bulkSelection!!.rows.map { it.objectKey }; val mainKey=model.bulkMainKey; val retained=model
        compose.activityRule.scenario.recreate(); settled(id)
        assertSame(retained,model); assertEquals(mainKey,model.bulkMainKey); assertEquals("1.25",model.bulkDraft!!.text); assertEquals(keys,model.bulkSelection!!.rows.map { it.objectKey })
        click("projected-fighters-back"); click("projected-fighters-open"); settled(id)
        send(BridgeOperation.RenameFit(id,"Fighter bulk renamed ${System.nanoTime()}"),id); settled(id)
        compose.onNodeWithTag("projected-fighters-bulk-stale").assertExists()
        compose.onNodeWithTag("projected-fighters-bulk-range-save").assertIsNotEnabled(); assertEquals("1.25",model.bulkDraft!!.text)
        click("projected-fighters-bulk-review"); assertEquals(ProjectedFighterBulkRangeMode.MIXED,model.bulkDraft!!.mode); assertEquals(mainKey,model.bulkMainKey)
        click("projected-fighters-bulk-range-default"); changed(id) { click("projected-fighters-bulk-range-save") }
        assertTrue(model.currentDetails!!.squadrons.filter { it.objectKey in keys }.all { it.rangeM==null })
        click("projected-fighters-bulk-review"); click("projected-fighters-bulk-range-edit")
        val unchanged=fit(id); val noHistory=history(id)
        click("projected-fighters-bulk-range-default"); click("projected-fighters-bulk-range-save")
        assertNull(model.bulkDraft); assertEquals(unchanged,fit(id)); assertEquals(noHistory,history(id))
        click("projected-fighters-bulk-range-edit"); text("projected-fighters-bulk-range-input","2.5")
        val removed=model.bulkSelection!!.rows.first()
        send(BridgeOperation.RemoveProjectedFighter(id,removed.index,removed.objectKey),id); settled(id)
        assertEquals("2.5",model.bulkDraft!!.text); assertEquals(2,model.bulkSelection!!.rows.size)
        compose.onNodeWithTag("projected-fighters-bulk-review").assertIsNotEnabled(); compose.onNodeWithTag("projected-fighters-bulk-range-save").assertIsNotEnabled()
        click("projected-fighters-bulk-clear"); assertNull(model.bulkDraft); assertNull(model.bulkSelection)
        val structure=create("Fortizar"); EngineRuntime.selectFit(context,structure).get(30,TimeUnit.SECONDS); settled(structure)
        compose.onNodeWithTag("projected-fighters-bulk-select-page").assertIsNotEnabled()
    }
}
