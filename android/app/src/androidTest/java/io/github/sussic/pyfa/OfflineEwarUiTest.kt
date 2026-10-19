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
import java.util.concurrent.atomic.AtomicBoolean
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Explicit deferred ewar_graph device gate on disposable durable data in airplane mode.
 * Compilation is not execution, numerical parity, visual/accessibility or ARM64 proof. */
@RunWith(AndroidJUnit4::class)
class OfflineEwarUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineEwarModel::class.java]
    private val modules get() = ViewModelProvider(compose.activity)[ModuleEditorModel::class.java]
    private val states get() = ViewModelProvider(compose.activity)[BulkStateEditorModel::class.java]
    private val historyModel get() = ViewModelProvider(compose.activity)[EditHistoryModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun history(id: String) = EngineRuntime.editHistory(context, id).get(30, TimeUnit.SECONDS)
    private fun plot(): OfflineEwarResult {
        click("ewar-graph-plot"); waitFor { !model.busy }
        assertTrue(model.error, model.currentResult?.ok == true); return model.currentResult!!
    }
    private fun prepare() {
        assertEquals("ewar_graph", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
    }
    private fun spec(name: String) = FitSpec(name, "Scorpion", 5, true, DamagePattern(1.0, 1.0, 1.0, 1.0),
        Security(SystemSecurity.HISEC, 0.0), listOf(
            ModuleSpec("Medium Energy Neutralizer II", ModuleState.ACTIVE), ModuleSpec("Stasis Webifier II", ModuleState.ACTIVE),
            ModuleSpec("Multispectral ECM II", ModuleState.ACTIVE), ModuleSpec("Remote Sensor Dampener II", ModuleState.ACTIVE),
            ModuleSpec("Tracking Disruptor II", ModuleState.ACTIVE), ModuleSpec("Guidance Disruptor II", ModuleState.ACTIVE),
            ModuleSpec("Target Painter II", ModuleState.ACTIVE)), emptyList())
    private fun create(value: FitSpec): String {
        val response = EngineRuntime.request(context, BridgeOperation.CreateFit(value), emptyMap()).get(120, TimeUnit.SECONDS)
        assertTrue(response.error?.message, response.isSuccess); return response.fits.single().id
    }

    @Test fun sevenModesRenderOriginalUnitsCompleteComparisonAndReadOnlySourceState() {
        prepare()
        val prefix = "EWAR UI ${System.nanoTime()}"
        val source = create(spec("$prefix source")); val empty = create(spec("$prefix empty").copy(modules = emptyList()))
        EngineRuntime.selectFit(context, source).get(30, TimeUnit.SECONDS)
        click("ewar-graph-open"); waitFor { source in model.selected }
        text("ewar-graph-search", prefix); click("ewar-graph-fit-$empty")
        assertEquals(setOf(source, empty), model.selected)
        assertTrue(model.ignoreLockRange); assertFalse(model.ignoreDroneControlRange); assertEquals("0", model.resistance)
        val beforeFits = EngineRuntime.library.value; val beforeNavigation = EngineRuntime.navigation.value
        val beforeRecent = EngineRuntime.recent.value; val beforeHistory = history(source)
        val beforeState = EngineRuntime.offlineFeatureState(context, source).get(30, TimeUnit.SECONDS)
        for (mode in OfflineEwarOrdinate.values()) {
            click("ewar-graph-ordinate-${mode.quantity}")
            compose.onNodeWithTag("ewar-graph-ordinate-${mode.quantity}").assertIsSelected()
            val result = plot(); assertEquals(mode, result.request.ordinate)
            assertEquals(EngineRuntime.library.value.filter { it.id in model.selected }.map { it.id }, result.series.map { it.fitId })
            assertTrue(result.series.single { it.fitId == source }.y.first() > 0.0)
            assertTrue(result.series.single { it.fitId == empty }.y.all { it == 0.0 })
            result.series.forEach { row ->
                assertEquals(fit(row.fitId).revision, row.revision); assertTrue(row.x.size in 51..201)
                assertEquals(row.x.size, row.y.size); assertTrue(row.y.all { it.isFinite() })
            }
            compose.onNodeWithTag("ewar-graph-canvas").performScrollTo().assertIsDisplayed()
            compose.onNodeWithTag("ewar-graph-applied-label").assertTextEquals(mode.label)
            compose.onNodeWithTag("ewar-graph-unit-explanation").assertTextContains(
                if (mode.unit == null) "no Y-axis unit" else "Original Y-axis unit: %", substring = true)
            compose.onNodeWithTag("ewar-graph-axes").performScrollTo().assertTextContains("km", substring = true)
            if (mode.unit == null) compose.onNodeWithTag("ewar-graph-axes").assert(hasText("%", substring = true).not())
        }
        assertEquals(beforeFits, EngineRuntime.library.value); assertEquals(beforeNavigation, EngineRuntime.navigation.value)
        assertEquals(beforeRecent, EngineRuntime.recent.value); assertEquals(beforeHistory, history(source))
        assertEquals(beforeState, EngineRuntime.offlineFeatureState(context, source).get(30, TimeUnit.SECONDS))
        compose.onNodeWithTag("ewar-graph-explanation").performScrollTo().assertTextContains("not jam probability", substring = true)
        click("ewar-graph-fit-$source"); plot(); compose.onNodeWithTag("ewar-graph-zero").assertExists()
        click("ewar-graph-fit-$empty"); compose.onNodeWithTag("ewar-graph-no-selection").assertExists()
        click("ewar-graph-back"); click("ewar-graph-open")
        assertTrue(model.selected.isEmpty()); compose.onNodeWithTag("ewar-graph-plot").assertIsNotEnabled()
    }

    @Test fun resistanceDraftsOptionsBackRecreationAndCancellationPreserveActualWorkerOwnership() {
        prepare()
        val source = create(spec("EWAR drafts ${System.nanoTime()}"))
        EngineRuntime.selectFit(context, source).get(30, TimeUnit.SECONDS)
        click("ewar-graph-open"); waitFor { model.selected == setOf(source) }
        click("ewar-graph-ordinate-webStr")
        val original = plot().series.single()
        for ((draft, fraction) in listOf("" to null, "-25" to 0.0, "100" to 1.0, "250" to 1.0)) {
            text("ewar-graph-resistance", draft); val result = plot()
            assertEquals(fraction, result.request.effectiveResistanceFraction)
            if (draft.isEmpty()) assertNull(result.request.resistancePercent)
            else assertEquals(draft.toDouble(), result.request.resistancePercent!!, 0.0)
            if (fraction == 1.0) assertTrue(result.series.single().y.all { it == 0.0 })
            else assertEquals(original.y, result.series.single().y)
            compose.onNodeWithTag("ewar-graph-effective-resistance").performScrollTo()
                .assertTextContains(if (draft.isEmpty()) "unspecified" else "clamped to 0–1", substring = true)
        }
        text("ewar-graph-high", "75.25"); text("ewar-graph-resistance", "invalid retained resistance")
        click("ewar-graph-lock"); click("ewar-graph-drone-control"); click("ewar-graph-plot")
        assertFalse(model.busy); assertNotNull(model.error)
        click("ewar-graph-back"); click("ewar-graph-open")
        val retained = model
        compose.activityRule.scenario.recreate(); waitFor { !model.busy }
        assertSame(retained, model); assertEquals("invalid retained resistance", model.resistance)
        assertEquals("75.25", model.high); assertEquals(OfflineEwarOrdinate.WEB, model.ordinate)
        assertFalse(model.ignoreLockRange); assertTrue(model.ignoreDroneControlRange); assertEquals(setOf(source), model.selected)
        text("ewar-graph-resistance", "0"); text("ewar-graph-low", "2"); text("ewar-graph-high", "2")
        assertEquals(listOf(2.0), plot().series.single().x)
        val input = model.currentResult!!.request; val mutableFits = input.fits.toMutableMap()
        val pending = EngineRuntime.offlineEwar(context, input.copy(fits = mutableFits), AtomicBoolean(false)); mutableFits.clear()
        val captured = pending.get(120, TimeUnit.SECONDS)
        assertTrue(captured.error?.message, captured.ok); assertEquals(input.fits, captured.request.fits)
        val cancelled = EngineRuntime.offlineEwar(context, input, AtomicBoolean(true)).get(30, TimeUnit.SECONDS)
        assertFalse(cancelled.ok); assertEquals("cancelled", cancelled.error!!.code); assertTrue(cancelled.series.isEmpty())
        compose.runOnUiThread {
            model.plot(context); model.selectOrdinate(OfflineEwarOrdinate.ECM); model.stop(); model.cancel(); model.plot(context)
            assertTrue(model.busy); assertTrue(model.cancelling); assertNull(model.currentResult)
        }
        waitFor { !model.busy }; assertNull(model.currentResult); plot()
    }

    @Test fun actualModuleStateEditReturnAndUndoInvalidateGraphWithoutLosingDrafts() {
        prepare()
        val source = create(spec("EWAR edits ${System.nanoTime()}"))
        EngineRuntime.selectFit(context, source).get(30, TimeUnit.SECONDS)
        click("ewar-graph-open"); waitFor { model.selected == setOf(source) }
        val baseline = plot().series.single(); assertTrue(baseline.y.first() > 0.0)
        text("ewar-graph-high", "75.25"); text("ewar-graph-resistance", "37.5")
        val beforeHistory = history(source)
        click("ewar-graph-back"); click("modules-open")
        waitFor { !modules.loading && modules.details?.let { it.fitId == source && it.revision == fit(source).revision } == true }
        val index = fit(source).modules.single { it.name == "Medium Energy Neutralizer II" }.index
        click("modules-bulk-states"); waitFor { !states.loading && states.options?.revision == fit(source).revision }
        click("bulk-states-reference-$index")
        assertEquals(setOf(index), states.selected); assertEquals(BulkScope.SELECTED, states.scope)
        assertEquals(ModuleState.ONLINE, states.options!!.modules.single { it.index == index }.clickStates.getValue(StateClick.CYCLE))
        val revision = fit(source).revision; click("bulk-states-apply")
        waitFor { !states.editing && fit(source).revision > revision && states.options?.revision == fit(source).revision }
        assertNull(states.error); assertEquals(ModuleState.ONLINE, fit(source).modules.single { it.index == index }.state)
        assertEquals(beforeHistory.undoCount + 1, history(source).undoCount)
        click("bulk-states-back"); click("modules-back"); click("ewar-graph-open")
        waitFor { model.currentResult == null }
        assertEquals("75.25", model.high); assertEquals("37.5", model.resistance); assertEquals(setOf(source), model.selected)
        assertTrue(plot().series.single().y.all { it == 0.0 })
        waitFor { !historyModel.loading && historyModel.options?.revision == fit(source).revision }
        click("history-undo")
        waitFor { !historyModel.editing && fit(source).modules.single { it.index == index }.state == ModuleState.ACTIVE }
        waitFor { model.currentResult == null }
        text("ewar-graph-high", "100"); text("ewar-graph-resistance", "0")
        val restored = plot().series.single()
        assertEquals(baseline.x, restored.x); assertEquals(baseline.y, restored.y); assertEquals(fit(source).revision, restored.revision)
    }
}
