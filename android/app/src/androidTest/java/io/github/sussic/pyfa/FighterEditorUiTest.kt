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

/** Deferred device gate: disposable durable data, offline_features_phase=fighters, airplane mode. */
@RunWith(AndroidJUnit4::class)
class FighterEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[FighterEditorModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun settled() { waitFor { !model.loading && !model.editing && model.currentDetails != null } }
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun send(id: String, operation: BridgeOperation) {
        val result = EngineRuntime.request(context, operation, mapOf(id to fit(id).revision)).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess)
        settled()
    }
    @Test fun offlineAddBulkStatesAbilitiesQuantityConflictsHistoryAndVariants() {
        assertEquals("fighters", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val before = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Thanatos", "Native fighter editing").get(120, TimeUnit.SECONDS).isSuccess)
        val id = EngineRuntime.library.value.single { it.id !in before }.id
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        click("fighters-open"); settled()
        compose.onNodeWithTag("fighters-empty").assertExists()
        val item = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS).items.single { it.name == "Firbolg I" }
        val variation = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS).items.single { it.name == "Firbolg II" }
        click("fighters-browse")
        compose.onNodeWithTag("equipment-search").performTextReplacement("Firbolg I")
        click("equipment-search-submit")
        val equipment = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
        waitFor { !equipment.busy }
        click("equipment-item-${item.id}"); click("equipment-add-fighter"); settled()
        assertEquals(1, model.currentDetails!!.squadrons.size)
        assertEquals(6, model.currentDetails!!.squadrons.single().amount)
        assertTrue(model.currentDetails!!.squadrons.single().active)
        // Leaving the fighter browser for fitting must clear the higher-priority fighter route.
        val moduleItem = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS).items.single { it.name == "Small Armor Repairer I" }
        click("fighters-browse")
        compose.onNodeWithTag("equipment-search").performTextReplacement(moduleItem.name)
        click("equipment-search-submit"); waitFor { !equipment.busy }
        click("equipment-item-${moduleItem.id}"); click("equipment-view-fit")
        compose.onNodeWithTag("modules-back").assertExists()
        compose.onNodeWithTag("fighters-back").assertDoesNotExist()
        click("modules-back"); click("fighters-open"); settled()
        repeat(3) { send(id, BridgeOperation.AddFighter(id, item.id)) }
        val added = model.currentDetails!!
        assertEquals(4, added.squadrons.size); assertEquals(4, added.squadrons.map { it.objectKey }.distinct().size)
        assertEquals(3, added.squadrons.count { it.active }); assertFalse(added.squadrons.last().active)
        click("fighters-select-all"); click("fighters-toggle-selected"); settled()
        assertTrue(model.currentDetails!!.squadrons.none { it.active })
        click("fighters-toggle-selected"); settled()
        assertTrue(model.currentDetails!!.squadrons.all { it.active })
        compose.onNodeWithTag("fighters-over-limit").assertExists()
        val initial = model.currentDetails!!.squadrons.first()
        val ability = initial.abilities.first()
        click("fighter-0-ability-${ability.effectId}"); settled()
        assertTrue(model.currentDetails!!.squadrons.all { row -> row.abilities.single { it.effectId == ability.effectId }.active != ability.active })
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision == fit(id).revision }
        var historyRevision = fit(id).revision
        click("history-undo"); waitFor { fit(id).revision > historyRevision }; settled()
        assertTrue(model.currentDetails!!.squadrons.all { row -> row.abilities.single { it.effectId == ability.effectId }.active == ability.active })
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision == fit(id).revision }
        historyRevision = fit(id).revision
        click("history-redo"); waitFor { fit(id).revision > historyRevision }; settled()
        assertTrue(model.currentDetails!!.squadrons.all { row -> row.abilities.single { it.effectId == ability.effectId }.active != ability.active })
        click("fighters-clear-selection")
        compose.onNodeWithTag("fighter-0-amount").performTextReplacement("2")
        val key = model.currentDetails!!.squadrons.first().objectKey
        val retained = model
        compose.activityRule.scenario.recreate(); settled()
        assertSame(retained, model); assertEquals("2", model.drafts[id to key]!!.text)
        send(id, BridgeOperation.RenameFit(id, "Changed while drafting"))
        compose.onNodeWithTag("fighter-0-draft-conflict").assertExists()
        compose.onNodeWithTag("fighter-0-save").assertIsNotEnabled()
        click("fighter-0-keep-draft"); click("fighter-0-save"); settled()
        assertEquals(2, model.currentDetails!!.squadrons.first().amount)
        val unchanged = fit(id)
        compose.onNodeWithTag("fighter-0-amount").performTextReplacement("-1")
        click("fighter-0-save"); assertEquals(unchanged, fit(id))
        compose.onNodeWithTag("fighters-error").assertExists()
        click("fighter-0-maximum"); settled()
        assertEquals(6, model.currentDetails!!.squadrons.first().amount)
        compose.onNodeWithTag("fighter-1-amount").performTextReplacement("3")
        click("fighter-1-remove"); settled()
        compose.onNodeWithTag("fighters-orphan-draft").assertExists()
        compose.onNodeWithText("Discard missing squadron draft").performScrollTo().performClick()
        assertTrue(model.drafts.isEmpty())
        click("fighter-0-select-type"); assertEquals(3, model.selected.size)
        click("fighter-0-variations"); click("fighter-0-variation-${variation.id}"); settled()
        assertEquals(3, model.currentDetails!!.squadrons.size)
        assertTrue(model.currentDetails!!.squadrons.all { it.itemId == variation.id })
        assertTrue(model.selected.isEmpty()) // New objects; old positions cannot identify the selection.
        val latest = fit(id)
        val rejected = EngineRuntime.request(context, BridgeOperation.SetFighterAmount(id, 0, 1), mapOf(id to unchanged.revision))
            .get(120, TimeUnit.SECONDS)
        assertFalse(rejected.isSuccess); assertEquals(BridgeErrorCode.REVISION_CONFLICT, rejected.error!!.code)
        assertEquals(latest, fit(id))
        // Request captures a caller-owned selection before it enters the serialized engine queue.
        val positions = mutableListOf(0, 1, 2)
        val future = EngineRuntime.request(context, BridgeOperation.ToggleFighters(id, 0, positions), mapOf(id to latest.revision))
        positions.clear(); assertTrue(future.get(120, TimeUnit.SECONDS).isSuccess); settled()
        assertTrue(model.currentDetails!!.squadrons.none { it.active })
        compose.onNodeWithTag("fighter-0-amount").performTextReplacement("0")
        click("fighter-0-save"); settled(); assertEquals(2, model.currentDetails!!.squadrons.size)
        click("fighters-select-all"); click("fighters-remove-selected"); settled()
        compose.onNodeWithTag("fighters-empty").assertExists()
        val beforeZero = EngineRuntime.library.value.map { it.id }.toSet()
        val zeroSpec = FitSpec("Existing zero-count squadron", "Thanatos", 5, true,
            DamagePattern(1.0, 1.0, 1.0, 1.0), Security(SystemSecurity.NULLSEC, 0.0), emptyList(), emptyList(),
            fighters = listOf(FighterSpec("Firbolg I", 0, true)))
        assertTrue(EngineRuntime.request(context, BridgeOperation.CreateFit(zeroSpec)).get(120, TimeUnit.SECONDS).isSuccess)
        val zeroFit = EngineRuntime.library.value.single { it.id !in beforeZero }
        EngineRuntime.selectFit(context, zeroFit.id).get(30, TimeUnit.SECONDS); settled()
        assertEquals(0, model.currentDetails!!.squadrons.single().amount)
        click("fighter-0-save"); settled()
        assertTrue(model.currentDetails!!.squadrons.isEmpty()) // Save 0 must remove even when the old count is already 0.
        val existing = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Vexor", "Unsupported fighter hull").get(120, TimeUnit.SECONDS).isSuccess)
        val unsupported = EngineRuntime.library.value.single { it.id !in existing }
        EngineRuntime.selectFit(context, unsupported.id).get(30, TimeUnit.SECONDS)
        // Two queued reads cannot let the first fit's delayed callback replace the selected fit.
        compose.runOnUiThread {
            model.load(context, fit(id), retry = true)
            model.load(context, unsupported, retry = true)
        }
        settled(); assertEquals(unsupported.id, model.currentDetails!!.fitId)
        val beforeRejected = EngineRuntime.offlineFeatureState(context, unsupported.id).get(30, TimeUnit.SECONDS)
        val recentBeforeRejected = EngineRuntime.recent.value.toList()
        assertNotEquals(item.id, recentBeforeRejected.firstOrNull())
        compose.runOnUiThread { model.add(context, item) {} }
        waitFor { !model.editing }; assertNotNull(model.error)
        assertEquals(unsupported, fit(unsupported.id)) // Includes unchanged revision and calculated stats.
        val afterRejected = EngineRuntime.offlineFeatureState(context, unsupported.id).get(30, TimeUnit.SECONDS)
        assertEquals(beforeRejected.history, afterRejected.history)
        assertEquals(beforeRejected.copy(context = afterRejected.context), afterRejected)
        assertEquals(beforeRejected.context.sessionId, afterRejected.context.sessionId)
        assertEquals(beforeRejected.context.datasetSha256, afterRejected.context.datasetSha256)
        assertTrue(afterRejected.context.generation > beforeRejected.context.generation)
        assertEquals((listOf(item.id) + recentBeforeRejected.filter { it != item.id }).take(20), EngineRuntime.recent.value)
    }
}
