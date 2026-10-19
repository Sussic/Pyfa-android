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

/** Deferred device gate: disposable durable data, offline_features_phase=boosters, airplane mode. */
@RunWith(AndroidJUnit4::class)
class BoosterEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[BoosterEditorModel::class.java]
    private val equipment get() = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun settled() { waitFor { !model.editing && !model.loading && model.currentDetails != null } }
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun item(name: String) = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS).items.single { it.name == name }
    private fun browse(value: EquipmentItem) {
        click("boosters-browse")
        compose.onNodeWithTag("equipment-search").performTextReplacement(value.name)
        click("equipment-search-submit"); waitFor { !equipment.busy }
        click("equipment-item-${value.id}")
        if (value.category == "Implant") waitFor { !model.addLoading && model.currentAdd(value.id) != null }
    }
    private fun history(id: String, redo: Boolean) {
        val before = fit(id).revision
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision == before }
        click(if (redo) "history-redo" else "history-undo")
        waitFor { fit(id).revision > before }; settled()
    }
    @Test fun offlineDefaultsVariationsExplicitReplacementStaleConfirmationAndBulkEdits() {
        assertEquals("boosters", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val prior = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Vexor", "Native booster editing").get(120, TimeUnit.SECONDS).isSuccess)
        val id = EngineRuntime.library.value.single { it.id !in prior }.id
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        val standard = item("Standard Blue Pill Booster")
        val improved = item("Improved Blue Pill Booster")
        val second = item("Standard Frentix Booster")
        click("boosters-open"); settled(); compose.onNodeWithTag("boosters-empty").assertExists()
        browse(standard)
        assertNull(model.currentAdd(standard.id)!!.occupant)
        click("equipment-fit-booster"); settled()
        var row = model.currentDetails!!.boosters.single()
        assertEquals(standard.id, row.itemId); assertTrue(row.active); assertTrue(row.sideEffects.all { !it.active })
        compose.onNodeWithTag("booster-0-duration").assertTextEquals("Duration: ${row.durationText}")
        val effect = row.sideEffects.first()
        click("booster-0-effect-${effect.effectId}"); settled()
        click("booster-0-toggle"); settled()
        assertFalse(model.currentDetails!!.boosters.single().active)
        click("booster-0-variations"); click("booster-0-variation-${improved.id}"); settled()
        row = model.currentDetails!!.boosters.single()
        assertEquals(improved.id, row.itemId); assertFalse(row.active)
        assertTrue(row.sideEffects.single { it.effectId == effect.effectId }.active)
        history(id, false); assertEquals(standard.id, model.currentDetails!!.boosters.single().itemId)
        history(id, true); assertEquals(improved.id, model.currentDetails!!.boosters.single().itemId)
        browse(standard)
        val beforeCancel = fit(id)
        val historyBeforeCancel = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS)
        click("equipment-fit-booster"); compose.onNodeWithTag("booster-replace-dialog").assertExists()
        assertEquals(improved.id, model.pendingReplacement!!.options.occupant!!.itemId)
        compose.onNodeWithTag("booster-replace-cancel").performClick()
        assertEquals(beforeCancel, fit(id))
        assertEquals(historyBeforeCancel, EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS))
        click("equipment-fit-booster")
        val retained = model; val pending = model.pendingReplacement
        compose.activityRule.scenario.recreate(); compose.waitForIdle()
        assertSame(retained, model); assertEquals(pending, model.pendingReplacement)
        val renamed = EngineRuntime.request(context, BridgeOperation.RenameFit(id, "Changed while replacement open"),
            mapOf(id to fit(id).revision)).get(120, TimeUnit.SECONDS)
        assertTrue(renamed.isSuccess)
        waitFor { !model.replacementCurrent }
        compose.onNodeWithTag("booster-replace-stale").assertExists()
        compose.onNodeWithTag("booster-replace-confirm").assertIsNotEnabled()
        val afterRename = fit(id)
        compose.runOnUiThread { model.confirmReplacement(context) {} }
        assertEquals(afterRename, fit(id)); assertNotNull(model.pendingReplacement)
        compose.onNodeWithTag("booster-replace-cancel").performClick()
        waitFor { !model.addLoading && model.currentAdd(standard.id) != null }
        val beforeReplace = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).history.undoCount
        click("equipment-fit-booster"); compose.onNodeWithTag("booster-replace-confirm").performClick(); settled()
        assertNull(model.pendingReplacement)
        row = model.currentDetails!!.boosters.single()
        assertEquals(standard.id, row.itemId); assertTrue(row.active); assertTrue(row.sideEffects.all { !it.active })
        assertEquals(beforeReplace + 1, EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).history.undoCount)
        history(id, false)
        row = model.currentDetails!!.boosters.single()
        assertEquals(improved.id, row.itemId); assertFalse(row.active)
        assertTrue(row.sideEffects.single { it.effectId == effect.effectId }.active)
        history(id, true)
        browse(standard)
        compose.onNodeWithTag("equipment-booster-already-fitted").assertExists()
        compose.onNodeWithTag("equipment-fit-booster").assertDoesNotExist()
        // The generic equipment fitting route must not remain trapped behind Boosters.
        click("equipment-view-fit"); compose.onNodeWithTag("modules-back").assertExists()
        compose.onNodeWithTag("boosters-back").assertDoesNotExist()
        click("modules-back"); click("boosters-open"); settled()
        browse(second); click("equipment-fit-booster"); settled()
        assertEquals(2, model.currentDetails!!.boosters.size)
        click("boosters-select-all"); click("boosters-toggle-selected"); settled()
        assertTrue(model.currentDetails!!.boosters.none { it.active })
        click("boosters-toggle-selected"); settled()
        assertTrue(model.currentDetails!!.boosters.all { it.active })
        val primary = model.currentDetails!!.boosters.single { it.itemId == standard.id }
        val otherBefore = model.currentDetails!!.boosters.single { it.itemId == second.id }
        click("booster-${primary.index}-effect-${effect.effectId}"); settled()
        assertEquals(otherBefore, model.currentDetails!!.boosters.single { it.itemId == second.id })
        val revision = fit(id).revision
        val positions = model.currentDetails!!.boosters.map { it.index }.toMutableList()
        val queued = EngineRuntime.request(context, BridgeOperation.ToggleBoosters(id, 0, positions), mapOf(id to revision))
        positions.clear(); assertTrue(queued.get(120, TimeUnit.SECONDS).isSuccess); settled()
        assertTrue(model.currentDetails!!.boosters.none { it.active })
        click("boosters-remove-selected"); settled(); assertTrue(model.currentDetails!!.boosters.isEmpty())
        val structureBefore = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Fortizar", "Booster structure restriction").get(120, TimeUnit.SECONDS).isSuccess)
        val structure = EngineRuntime.library.value.single { it.id !in structureBefore }
        EngineRuntime.selectFit(context, structure.id).get(30, TimeUnit.SECONDS)
        // A queued old-fit detail must never replace the current structure's state.
        compose.runOnUiThread { model.load(context, fit(id), true); model.load(context, structure, true) }
        settled(); assertEquals(structure.id, model.currentDetails!!.fitId)
        compose.onNodeWithTag("boosters-structure").assertExists(); compose.onNodeWithTag("boosters-browse").assertIsNotEnabled()
        assertTrue(EngineRuntime.boosterAddOptions(context, structure.id, standard.id).get(30, TimeUnit.SECONDS).isStructure)
        val nonbooster = EngineRuntime.boosterAddOptions(context, id, item("Small Armor Repairer I").id).get(30, TimeUnit.SECONDS)
        assertFalse(nonbooster.isBooster); assertNull(nonbooster.slot); assertNull(nonbooster.occupant)
        val module = item("Small Armor Repairer I")
        compose.runOnUiThread {
            model.loadAddOptions(context, structure, standard.id, true)
            model.loadAddOptions(context, structure, module.id, true)
        }
        waitFor { !model.addLoading }
        assertEquals(module.id, model.addOptions!!.itemId); assertFalse(model.addOptions!!.isBooster)
    }
}
