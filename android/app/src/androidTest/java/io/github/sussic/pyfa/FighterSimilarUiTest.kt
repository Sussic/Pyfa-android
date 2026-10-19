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
import java.util.concurrent.CompletableFuture
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred device gate: disposable durable data, offline_features_phase=fighters_similar. */
@RunWith(AndroidJUnit4::class)
class FighterSimilarUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[FighterEditorModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun settled(id: String) = waitFor { !model.loading && !model.editing && !model.selectingSimilar && model.currentDetails?.fitId == id }
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun send(id: String, operation: BridgeOperation) {
        val result = EngineRuntime.request(context, operation, mapOf(id to fit(id).revision)).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess)
    }
    @Test fun sourceSimilarSelectionCrossesTypesIgnoresStatesRetainsSelectionAndDrivesBulkUndo() {
        assertEquals("fighters_similar", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val oldIds = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Thanatos", "Native similar fighters").get(120, TimeUnit.SECONDS).isSuccess)
        val id = EngineRuntime.library.value.single { it.id !in oldIds }.id
        val catalog = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS)
        for (name in listOf("Firbolg I", "Dromi I", "Firbolg II", "Firbolg I")) {
            send(id, BridgeOperation.AddFighter(id, catalog.items.single { it.name == name }.id))
        }
        val initial = EngineRuntime.fighterDetails(context, id).get(30, TimeUnit.SECONDS)
        val effect = initial.squadrons[0].abilities.first().effectId
        send(id, BridgeOperation.ToggleFighters(id, 0, emptyList()))
        send(id, BridgeOperation.ToggleFighterAbility(id, 0, emptyList(), effect))
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        click("fighters-open"); settled(id)
        val rows = model.currentDetails!!.squadrons
        assertNotEquals(rows[0].active, rows[2].active)
        assertNotEquals(rows[0].abilities.single { it.effectId == effect }.active, rows[2].abilities.single { it.effectId == effect }.active)
        val expected = listOf(0, 2, 3).map { rows[it].objectKey }.toSet()
        val beforeFit = fit(id)
        val beforeState = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS)
        val beforeRecent = EngineRuntime.recent.value.toList()
        click("fighter-0-select-type")
        assertEquals(setOf(rows[0].objectKey, rows[3].objectKey), model.selected)
        click("fighter-0-select-similar"); settled(id)
        assertEquals(expected, model.selected)
        assertEquals(beforeFit, fit(id))
        assertEquals(beforeState, EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS))
        assertEquals(beforeRecent, EngineRuntime.recent.value)
        val retained = model
        compose.activityRule.scenario.recreate(); settled(id)
        assertSame(retained, model); assertEquals(expected, model.selected)
        // Selecting from the other, active main still picks the same source-compatible set.
        click("fighter-2-select-similar"); settled(id); assertEquals(expected, model.selected)
        val supportBefore = model.currentDetails!!.squadrons[1]
        val historyBefore = EngineRuntime.editHistory(context, id).get(30, TimeUnit.SECONDS).undoCount
        click("fighters-toggle-selected"); settled(id)
        assertTrue(model.currentDetails!!.squadrons.filter { it.objectKey in expected }.all { it.active })
        assertEquals(supportBefore, model.currentDetails!!.squadrons[1])
        assertEquals(historyBefore + 1, EngineRuntime.editHistory(context, id).get(30, TimeUnit.SECONDS).undoCount)
        assertEquals(beforeRecent, EngineRuntime.recent.value)
        send(id, BridgeOperation.Undo(id)); settled(id)
        assertEquals(rows, model.currentDetails!!.squadrons)
        send(id, BridgeOperation.Redo(id)); settled(id)
        assertTrue(model.currentDetails!!.squadrons.filter { it.objectKey in expected }.all { it.active })
        // The support fighter has a different complete ability set and stays alone.
        click("fighter-1-select-similar"); settled(id)
        assertEquals(setOf(supportBefore.objectKey), model.selected)
    }
    @Test fun delayedSelectionCannotOverwriteNewSelectionReloadRevisionOrFitAndFailuresPreserveIt() {
        assertEquals("fighters_similar", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val oldIds = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Thanatos", "Selection race carrier").get(120, TimeUnit.SECONDS).isSuccess)
        val id = EngineRuntime.library.value.single { it.id !in oldIds }.id
        val catalog = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS)
        for (name in listOf("Firbolg I", "Dromi I", "Firbolg II")) {
            send(id, BridgeOperation.AddFighter(id, catalog.items.single { it.name == name }.id))
        }
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        lateinit var pending: CompletableFuture<FighterSimilarSelection>
        var calls = 0
        val controlled = FighterEditorModel { _, _, _ -> calls += 1; pending }
        fun loaded(key: String) = waitFor { !controlled.loading && controlled.currentDetails?.fitId == key }
        fun begin(): Pair<FighterDetails, FighterSimilarSelection> {
            val d = controlled.currentDetails!!
            val result = EngineRuntime.fighterSimilarSelection(context, d.fitId, d.revision, 0).get(30, TimeUnit.SECONDS)
            pending = CompletableFuture()
            compose.runOnUiThread { controlled.selectSimilar(context, d, d.squadrons[0]) }
            assertTrue(controlled.selectingSimilar)
            return d to result
        }
        fun finish(value: FighterSimilarSelection) {
            pending.complete(value)
            waitFor { !controlled.selectingSimilar }
        }
        compose.runOnUiThread { controlled.load(context, fit(id)) }; loaded(id)
        val original = controlled.currentDetails!!
        compose.runOnUiThread {
            assertFalse(controlled.canSelectSimilar(original.copy(), original.squadrons[0]))
            assertFalse(controlled.canSelectSimilar(original, original.squadrons[0].copy()))
            controlled.selectSimilar(context, original.copy(), original.squadrons[0])
            controlled.selectType(original.squadrons[0].copy())
        }
        assertEquals(0, calls); assertTrue(controlled.selected.isEmpty())
        var capture = begin()
        compose.runOnUiThread {
            controlled.selectSimilar(context, capture.first, capture.first.squadrons[0])
            controlled.select(capture.first.squadrons[1].objectKey, true)
        }
        assertEquals(1, calls) // One active read, no queue growth from repeated clicks.
        finish(capture.second)
        assertEquals(setOf(original.squadrons[1].objectKey), controlled.selected)
        capture = begin()
        compose.runOnUiThread { controlled.selectType(capture.first.squadrons[0]) }
        finish(capture.second)
        assertEquals(setOf(original.squadrons[0].objectKey), controlled.selected)
        capture = begin()
        compose.runOnUiThread { controlled.load(context, fit(id), retry = true) }; loaded(id)
        assertNotSame(capture.first, controlled.currentDetails)
        finish(capture.second)
        assertEquals(setOf(original.squadrons[0].objectKey), controlled.selected)
        capture = begin()
        pending.completeExceptionally(IllegalArgumentException("ValueError: ${FighterSimilarSelectionCodec.LIMIT_MESSAGE}"))
        waitFor { !controlled.selectingSimilar }
        assertEquals("Select at most 1024 squadrons per edit.", controlled.error)
        assertEquals(setOf(original.squadrons[0].objectKey), controlled.selected)
        assertTrue(EngineRuntime.state.value is EngineState.Ready)
        capture = begin()
        finish(capture.second.copy(fitId = "wrong-fit"))
        assertNotNull(controlled.error)
        assertEquals(setOf(original.squadrons[0].objectKey), controlled.selected)
        capture = begin()
        send(id, BridgeOperation.RenameFit(id, "Changed during selection"))
        compose.runOnUiThread { controlled.load(context, fit(id)) }; loaded(id)
        finish(capture.second)
        assertEquals(setOf(original.squadrons[0].objectKey), controlled.selected)
        val beforeOther = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Thanatos", "Other selection carrier").get(120, TimeUnit.SECONDS).isSuccess)
        val other = EngineRuntime.library.value.single { it.id !in beforeOther }.id
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        compose.runOnUiThread { controlled.load(context, fit(id), retry = true) }; loaded(id)
        capture = begin()
        EngineRuntime.selectFit(context, other).get(30, TimeUnit.SECONDS)
        compose.runOnUiThread { controlled.load(context, fit(other)) }; loaded(other)
        finish(capture.second)
        assertEquals(other, controlled.currentDetails!!.fitId); assertTrue(controlled.selected.isEmpty())
        assertNull(controlled.error)
    }

}
