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

/** Deferred native gate: disposable durable data, offline_features_phase=implants, airplane mode. */
@RunWith(AndroidJUnit4::class)
class ImplantEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[ImplantEditorModel::class.java]
    private val equipment get() = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
    private val variations get() = ViewModelProvider(compose.activity)[VariationEditorModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun settled() { waitFor { !model.editing && !model.loading && model.currentDetails != null } }
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun item(name: String) = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS).items.single { it.name == name }
    private fun browse(value: EquipmentItem) {
        click("implants-browse")
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
    @Test fun offlineSlotOrderVariationRecentExplicitReplacementStaleGuardsAndGroupEdits() {
        assertEquals("implants", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val prior = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Vexor", "Native fit implants").get(120, TimeUnit.SECONDS).isSuccess)
        val id = EngineRuntime.library.value.single { it.id !in prior }.id
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        val first = item("Eifyr and Co. 'Rogue' Navigation NN-601")
        val improved = item("Eifyr and Co. 'Rogue' Navigation NN-605")
        val mindlink = item("Shield Command Mindlink")
        click("implants-open"); settled()
        browse(mindlink); click("equipment-fit-implant"); settled()
        assertEquals(mindlink.id, EngineRuntime.recent.value.first())
        browse(first); click("equipment-fit-implant"); settled()
        assertEquals(first.id, EngineRuntime.recent.value.first())
        var details = model.currentDetails!!
        assertEquals(listOf(10, 6), details.implants.map { it.slot })
        assertEquals(listOf(1, 0), details.displayRows.map { it.index })
        compose.onNodeWithTag("implant-1").assertExists(); compose.onNodeWithTag("implant-0").assertExists()
        click("implant-1-toggle"); settled()
        assertFalse(model.currentDetails!!.implants[1].active)
        assertTrue(model.currentDetails!!.implants[0].active)
        val beforeVariationRecent = EngineRuntime.recent.value.toList()
        click("implant-1-variations")
        waitFor { !variations.loading && variations.options?.revision == fit(id).revision }
        compose.onNodeWithText("Keeps activation. A different-slot variation keeps the original implant and can replace the destination slot occupant.").assertExists()
        val oldTarget = variations.options!!.targets.single { it.context == VariationContext.IMPLANT && it.itemId == first.id }
        val choice = oldTarget.choices.single { it.id == improved.id }
        compose.runOnUiThread {
            assertTrue(variations.canApply(oldTarget, choice))
            assertFalse(variations.canApply(oldTarget.copy(), choice))
            assertFalse(variations.canApply(oldTarget, choice.copy()))
        }
        compose.onNodeWithTag("variations-search").performTextReplacement(improved.name)
        click("variation-item-${improved.id}"); click("variation-apply")
        waitFor { !variations.editing && !variations.loading && fit(id).implants.any { it.name == improved.name } }
        compose.runOnUiThread { assertFalse(variations.canApply(oldTarget, choice)) }
        assertEquals(beforeVariationRecent, EngineRuntime.recent.value)
        click("variations-back"); settled()
        assertFalse(model.currentDetails!!.implants.single { it.itemId == improved.id }.active)
        browse(first)
        val beforeCancel = fit(id)
        val beforeCancelHistory = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).history
        val beforeCancelRecent = EngineRuntime.recent.value.toList()
        click("equipment-fit-implant")
        compose.onNodeWithTag("implant-replace-dialog").assertExists()
        assertEquals(improved.id, model.pendingReplacement!!.options.occupant!!.itemId)
        compose.onNodeWithTag("implant-replace-cancel").performClick()
        assertEquals(beforeCancel, fit(id)); assertEquals(beforeCancelRecent, EngineRuntime.recent.value)
        assertEquals(beforeCancelHistory, EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).history)
        click("equipment-fit-implant")
        val retained = model; val pending = model.pendingReplacement
        compose.activityRule.scenario.recreate(); compose.waitForIdle()
        assertSame(retained, model); assertEquals(pending, model.pendingReplacement)
        assertTrue(EngineRuntime.request(context, BridgeOperation.RenameFit(id, "Changed with implant confirmation open"),
            mapOf(id to fit(id).revision)).get(120, TimeUnit.SECONDS).isSuccess)
        waitFor { !model.replacementCurrent }
        compose.onNodeWithTag("implant-replace-stale").assertExists()
        compose.onNodeWithTag("implant-replace-confirm").assertIsNotEnabled()
        val afterRename = fit(id)
        compose.runOnUiThread { model.confirmReplacement(context) {} }
        assertEquals(afterRename, fit(id)); assertNotNull(model.pendingReplacement)
        compose.onNodeWithTag("implant-replace-cancel").performClick()
        waitFor { !model.addLoading && model.currentAdd(first.id) != null }
        val beforeReplace = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).history.undoCount
        click("equipment-fit-implant"); compose.onNodeWithTag("implant-replace-confirm").performClick(); settled()
        assertNull(model.pendingReplacement)
        assertTrue(model.currentDetails!!.implants.single { it.itemId == first.id }.active)
        assertEquals(beforeReplace + 1, EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).history.undoCount)
        history(id, false)
        assertFalse(model.currentDetails!!.implants.single { it.itemId == improved.id }.active)
        history(id, true)
        browse(first)
        compose.onNodeWithTag("equipment-implant-already-fitted").assertExists()
        compose.onNodeWithTag("equipment-fit-implant").assertDoesNotExist()
        val duplicateBefore = fit(id); val duplicateRecent = EngineRuntime.recent.value.toList()
        val duplicateHistory = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).history
        assertFalse(EngineRuntime.request(context, BridgeOperation.FitImplant(id, first.id),
            mapOf(id to duplicateBefore.revision)).get(120, TimeUnit.SECONDS).isSuccess)
        assertEquals(duplicateBefore, fit(id)); assertEquals(duplicateRecent, EngineRuntime.recent.value)
        assertEquals(duplicateHistory, EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).history)
        // Returning from equipment must not remain trapped in the implant route.
        click("equipment-view-fit"); compose.onNodeWithTag("modules-back").assertExists()
        compose.onNodeWithTag("implants-back").assertDoesNotExist()
        click("modules-back"); click("implants-open"); settled()
        details = model.currentDetails!!
        val oldRow = details.implants.first()
        compose.runOnUiThread { model.toggle(context, details.copy(), oldRow) }
        assertFalse(model.editing) // Equal-but-not-current details cannot submit a captured row.
        click("implants-select-all"); click("implants-toggle-selected"); settled()
        assertTrue(model.currentDetails!!.implants.none { it.active })
        val afterToggle = fit(id)
        compose.runOnUiThread { model.remove(context, details, listOf(oldRow)) }
        assertEquals(afterToggle, fit(id))
        val positions = model.currentDetails!!.implants.map { it.index }.toMutableList()
        val queued = EngineRuntime.request(context, BridgeOperation.ToggleImplants(id, 0, positions), mapOf(id to fit(id).revision))
        positions.clear(); assertTrue(queued.get(120, TimeUnit.SECONDS).isSuccess); settled()
        assertTrue(model.currentDetails!!.implants.all { it.active })
        click("implants-remove-selected"); settled(); assertTrue(model.currentDetails!!.implants.isEmpty())
        // Original different-slot behavior retains the source and replaces the destination occupant.
        val source = item("Genolution Core Augmentation CA-1")
        val destination = item("Cybernetic 'Source' Subprocessor")
        val occupant = item("Genolution Core Augmentation CA-2")
        fun send(operation: BridgeOperation) {
            val response = EngineRuntime.request(context, operation, mapOf(id to fit(id).revision)).get(120, TimeUnit.SECONDS)
            assertTrue(response.error?.message, response.isSuccess)
        }
        send(BridgeOperation.FitImplant(id, source.id)); settled()
        send(BridgeOperation.FitImplant(id, occupant.id)); settled()
        click("implant-0-toggle"); settled()
        val originalKey = model.currentDetails!!.implants[0].objectKey
        val beforeDifferentSlotRecent = EngineRuntime.recent.value.toList()
        click("implant-0-variations")
        waitFor { !variations.loading && variations.options?.revision == fit(id).revision }
        val currentOptions = variations.options!!
        val currentTarget = currentOptions.targets.single { it.context == VariationContext.IMPLANT && it.itemId == source.id }
        val destinationChoice = currentTarget.choices.single { it.id == destination.id }
        // Even malformed availability from a future source must not allow character-source editing.
        val characterTarget = currentTarget.copy(current = (currentTarget.current as VariationInput.Implant).copy(location = "CHARACTER"))
        compose.runOnUiThread {
            variations.options = currentOptions.copy(targets = listOf(characterTarget))
            assertFalse(variations.canApply(characterTarget, destinationChoice))
            variations.options = currentOptions
        }
        compose.onNodeWithTag("variations-search").performTextReplacement(destination.name)
        click("variation-item-${destination.id}"); click("variation-apply")
        waitFor { !variations.editing && !variations.loading && fit(id).implants.any { it.name == destination.name } }
        click("variations-back"); settled()
        assertEquals(listOf(source.id, destination.id), model.currentDetails!!.implants.map { it.itemId })
        assertEquals(originalKey, model.currentDetails!!.implants[0].objectKey)
        assertTrue(model.currentDetails!!.implants.none { it.active })
        assertEquals(beforeDifferentSlotRecent, EngineRuntime.recent.value)
        history(id, false)
        assertEquals(listOf(source.id, occupant.id), model.currentDetails!!.implants.map { it.itemId })
        val structureBefore = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Fortizar", "Implant structure restriction").get(120, TimeUnit.SECONDS).isSuccess)
        val structure = EngineRuntime.library.value.single { it.id !in structureBefore }
        EngineRuntime.selectFit(context, structure.id).get(30, TimeUnit.SECONDS)
        compose.runOnUiThread { model.load(context, fit(id), true); model.load(context, structure, true) }
        settled(); assertEquals(structure.id, model.currentDetails!!.fitId)
        compose.onNodeWithTag("implants-structure").assertExists()
        compose.onNodeWithTag("implants-browse").assertIsNotEnabled()
        val booster = item("Standard Blue Pill Booster")
        compose.runOnUiThread {
            model.loadAddOptions(context, structure, first.id, true)
            model.loadAddOptions(context, structure, booster.id, true)
        }
        waitFor { !model.addLoading }
        assertEquals(booster.id, model.addOptions!!.itemId)
        assertFalse(model.addOptions!!.isImplant); assertNull(model.addOptions!!.slot); assertNull(model.addOptions!!.occupant)
        assertTrue(EngineRuntime.implantAddOptions(context, structure.id, first.id).get(30, TimeUnit.SECONDS).isStructure)
    }
}
