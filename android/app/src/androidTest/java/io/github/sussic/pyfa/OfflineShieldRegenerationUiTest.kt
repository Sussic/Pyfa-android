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
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Deferred G04 native gate: disposable durable data, airplane mode and
 * offline_features_phase=shield_regeneration_graph. Compiling is not executing
 * this causal/read-only suite or the separate independent original comparator.
 */
@RunWith(AndroidJUnit4::class)
class OfflineShieldRegenerationUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineShieldRegenerationModel::class.java]
    private val defenses get() = ViewModelProvider(compose.activity)[DefenseModel::class.java]
    private val modules get() = ViewModelProvider(compose.activity)[ModuleEditorModel::class.java]
    private val states get() = ViewModelProvider(compose.activity)[BulkStateEditorModel::class.java]
    private val historyModel get() = ViewModelProvider(compose.activity)[EditHistoryModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun history(id: String) = EngineRuntime.editHistory(context, id).get(30, TimeUnit.SECONDS)
    private fun graph() = JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(30, TimeUnit.SECONDS))
    private fun plot(): OfflineShieldRegenerationResult {
        click("shield-graph-plot"); waitFor { !model.busy }
        assertTrue(model.error, model.currentResult?.ok == true)
        return model.currentResult!!
    }
    private fun prepare() {
        assertEquals("shield_regeneration_graph", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
    }
    private fun sourceSpec(name: String) = FitSpec(name, "Vexor", 5, true, DamagePattern(1.0, 2.0, 3.0, 4.0),
        Security(SystemSecurity.HISEC, 0.0), listOf(ModuleSpec("Large Shield Extender II", ModuleState.ONLINE),
            ModuleSpec("Multispectrum Shield Hardener II", ModuleState.ACTIVE)), emptyList())
    private fun create(spec: FitSpec): String {
        val result = EngineRuntime.request(context, BridgeOperation.CreateFit(spec), emptyMap()).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess); return result.fits.single().id
    }
    private fun mode(x: OfflineShieldRegenerationX, y: OfflineShieldRegenerationY, effective: Boolean) {
        if (model.effective != effective) click("shield-graph-effective")
        click("shield-graph-x-${when (x) { OfflineShieldRegenerationX.TIME -> "time"; OfflineShieldRegenerationX.AMOUNT -> "amount"; OfflineShieldRegenerationX.PERCENT -> "percent" }}")
        click("shield-graph-y-${if (y == OfflineShieldRegenerationY.AMOUNT) "amount" else "rate"}")
        assertEquals(x, model.x); assertEquals(y, model.y); assertEquals(effective, model.effective)
    }
    private fun sourceReadouts(series: OfflineShieldRegenerationSeries, effective: Boolean) {
        compose.onNodeWithTag("shield-graph-source-capacity-${series.fitId}").performScrollTo()
            .assertTextEquals("Source shield capacity: ${series.source.shieldCapacityHp} HP")
        compose.onNodeWithTag("shield-graph-source-recharge-${series.fitId}").performScrollTo()
            .assertTextEquals("Source shield recharge: ${series.source.shieldRechargeSeconds} s")
        for ((key, label) in DAMAGE_TYPES) {
            val node = compose.onNodeWithTag("shield-graph-source-$key-${series.fitId}")
            if (effective) node.performScrollTo().assertTextEquals("$label: ${series.source.damagePattern.getValue(key)}") else node.assertDoesNotExist()
        }
    }

    @Test fun allTwelveModesReadOnlyMultiFitAxesAndActualDamageEditReturnUseCurrentSources() {
        prepare()
        val prefix = "Shield modes ${System.nanoTime()}"
        val source = create(sourceSpec("$prefix source")); val empty = create(sourceSpec("$prefix empty").copy(modules = emptyList()))
        EngineRuntime.selectFit(context, source).get(30, TimeUnit.SECONDS)
        click("shield-regeneration-graph-open"); waitFor { source in model.selected }
        text("shield-graph-search", prefix); click("shield-graph-fit-$empty")
        assertEquals(setOf(source, empty), model.selected)
        val beforeFits = EngineRuntime.library.value; val beforeGraph = graph(); val beforeNavigation = EngineRuntime.navigation.value
        val beforeRecent = EngineRuntime.recent.value; val beforeHistory = history(source)
        val beforeState = EngineRuntime.offlineFeatureState(context, source).get(30, TimeUnit.SECONDS)
        val results = mutableMapOf<Triple<OfflineShieldRegenerationX, OfflineShieldRegenerationY, Boolean>, OfflineShieldRegenerationResult>()
        for (effective in listOf(false, true)) for (x in OfflineShieldRegenerationX.values()) for (y in OfflineShieldRegenerationY.values()) {
            mode(x, y, effective)
            assertNull(model.currentResult)
            if (x == OfflineShieldRegenerationX.TIME) {
                compose.onNodeWithTag("shield-graph-start").assertExists(); text("shield-graph-start", "")
            } else {
                compose.onNodeWithTag("shield-graph-start").assertDoesNotExist()
                compose.onNodeWithTag("shield-graph-input-explanation").assertTextContains("percentages", substring = true)
            }
            val result = plot(); results[Triple(x, y, effective)] = result
            assertNull(result.request.startingShieldPercent)
            assertEquals(x, result.request.x); assertEquals(y, result.request.y); assertEquals(effective, result.request.effective)
            result.series.forEach { series ->
                assertEquals(fit(series.fitId).revision, series.revision); assertEquals(201, series.x.size)
                assertTrue(series.x.all { it.isFinite() }); assertTrue(series.y.all { it.isFinite() }); sourceReadouts(series, effective)
            }
            val coordinates = result.series.flatMap { it.x }; val values = result.series.flatMap { it.y }
            compose.onNodeWithTag("shield-graph-axes").performScrollTo().assertTextEquals(
                "X: ${coordinates.minOrNull()}–${coordinates.maxOrNull()} ${x.unit(effective)} · Y: ${values.minOrNull()}–${values.maxOrNull()} ${y.unit(effective)}")
            compose.onNodeWithTag("shield-graph-canvas").performScrollTo().assertIsDisplayed()
        }
        assertEquals(12, results.size)
        val rawAmount = results.getValue(Triple(OfflineShieldRegenerationX.AMOUNT, OfflineShieldRegenerationY.AMOUNT, false))
        val sourceAmount = rawAmount.series.single { it.fitId == source }; val emptyAmount = rawAmount.series.single { it.fitId == empty }
        assertTrue(sourceAmount.x.last() > emptyAmount.x.last()); assertEquals(sourceAmount.source.shieldCapacityHp, sourceAmount.x.last(), 1e-9)
        assertEquals(beforeFits, EngineRuntime.library.value); assertEquals(beforeNavigation, EngineRuntime.navigation.value)
        assertEquals(beforeRecent, EngineRuntime.recent.value); assertEquals(beforeHistory, history(source))
        assertEquals(beforeState, EngineRuntime.offlineFeatureState(context, source).get(30, TimeUnit.SECONDS))
        ModuleTestJson.compare(beforeGraph, graph(), strict = false)

        mode(OfflineShieldRegenerationX.PERCENT, OfflineShieldRegenerationY.AMOUNT, true)
        val effectiveBefore = plot().series.single { it.fitId == source }
        text("shield-graph-low", "12.5"); text("shield-graph-high", "87.5")
        click("shield-graph-back"); click("defense-open")
        waitFor { !defenses.loading && defenses.details?.let { it.fitId == source && it.revision == fit(source).revision } == true }
        for (key in DAMAGE_TYPES.keys) text("defense-input-$key", if (key == "em") "1" else "0")
        val revision = fit(source).revision; click("defense-apply")
        waitFor { !defenses.drafts.getValue(source).saving && fit(source).revision > revision && defenses.details?.revision == fit(source).revision }
        assertNull(defenses.error); assertEquals(beforeHistory.undoCount + 1, history(source).undoCount)
        click("defense-back"); click("shield-regeneration-graph-open")
        assertEquals(setOf(source, empty), model.selected); assertEquals(prefix, model.query)
        assertEquals("12.5", model.low); assertEquals("87.5", model.high); assertTrue(model.effective); assertNull(model.currentResult)
        text("shield-graph-low", "0"); text("shield-graph-high", "100")
        val edited = plot().series.single { it.fitId == source }
        assertEquals(linkedMapOf("em" to 1.0, "thermal" to 0.0, "kinetic" to 0.0, "explosive" to 0.0), edited.source.damagePattern)
        assertEquals(effectiveBefore.source.shieldCapacityHp, edited.source.shieldCapacityHp, 0.0)
        assertNotEquals(effectiveBefore.y.last(), edited.y.last()); sourceReadouts(edited, true)
        waitFor { !historyModel.loading && historyModel.options?.revision == fit(source).revision }
        click("history-undo"); waitFor { !historyModel.editing && model.currentResult == null }
        val restored = plot().series.single { it.fitId == source }
        assertEquals(effectiveBefore.source, restored.source); assertEquals(effectiveBefore.x, restored.x); assertEquals(effectiveBefore.y, restored.y)
    }

    @Test fun sourceModuleStateUndoDraftRecreationRuntimeCaptureAndCancelRemainUsable() {
        prepare()
        val source = create(sourceSpec("Shield state ${System.nanoTime()}"))
        EngineRuntime.selectFit(context, source).get(30, TimeUnit.SECONDS)
        click("shield-regeneration-graph-open"); waitFor { model.selected == setOf(source) }
        mode(OfflineShieldRegenerationX.AMOUNT, OfflineShieldRegenerationY.AMOUNT, false)
        val before = plot().series.single(); val beforeHistory = history(source)
        click("shield-graph-back"); click("modules-open")
        waitFor { !modules.loading && modules.details?.let { it.fitId == source && it.revision == fit(source).revision } == true }
        val extender = fit(source).modules.single { it.name == "Large Shield Extender II" }.index
        click("modules-bulk-states"); waitFor { !states.loading && states.options?.revision == fit(source).revision }
        click("bulk-states-reference-$extender")
        assertEquals(setOf(extender), states.selected); assertEquals(BulkScope.SELECTED, states.scope)
        assertEquals(ModuleState.OFFLINE, states.options!!.modules.single { it.index == extender }.clickStates.getValue(StateClick.CYCLE))
        val revision = fit(source).revision; click("bulk-states-apply")
        waitFor { !states.editing && fit(source).revision > revision && states.options?.revision == fit(source).revision }
        assertNull(states.error); assertEquals(ModuleState.OFFLINE, fit(source).modules.single { it.index == extender }.state)
        click("bulk-states-back"); click("modules-back"); click("shield-regeneration-graph-open")
        assertNull(model.currentResult)
        val edited = plot().series.single(); assertTrue(edited.source.shieldCapacityHp < before.source.shieldCapacityHp)
        assertTrue(edited.x.last() < before.x.last()); assertEquals(beforeHistory.undoCount + 1, history(source).undoCount)
        waitFor { !historyModel.loading && historyModel.options?.revision == fit(source).revision }
        click("history-undo"); waitFor { !historyModel.editing && fit(source).modules.single { it.index == extender }.state == ModuleState.ONLINE }
        waitFor { model.currentResult == null }
        assertEquals(before.source, plot().series.single().source)

        text("shield-graph-high", "invalid retained draft"); click("shield-graph-plot")
        assertFalse(model.busy); compose.onNodeWithTag("shield-graph-error").assertExists()
        val retained = model; compose.activityRule.scenario.recreate(); waitFor { !model.busy }
        assertSame(retained, model); assertEquals("invalid retained draft", model.high); assertEquals(setOf(source), model.selected)
        mode(OfflineShieldRegenerationX.TIME, OfflineShieldRegenerationY.RATE, true)
        text("shield-graph-low", "2"); text("shield-graph-high", "2"); text("shield-graph-start", "")
        val singleton = plot(); assertTrue(singleton.series.all { it.x == listOf(2.0) && it.y.size == 1 }); assertNull(singleton.request.startingShieldPercent)
        mode(OfflineShieldRegenerationX.AMOUNT, OfflineShieldRegenerationY.AMOUNT, false)
        assertEquals("invalid retained draft", model.high)
        mode(OfflineShieldRegenerationX.TIME, OfflineShieldRegenerationY.RATE, true)
        assertEquals("2", model.low); assertEquals("2", model.high); assertEquals("", model.startingShield)
        val input = plot().request; val mutableFits = input.fits.toMutableMap()
        val pending = EngineRuntime.offlineShieldRegeneration(context, input.copy(fits = mutableFits), AtomicBoolean(false)); mutableFits.clear()
        val captured = pending.get(120, TimeUnit.SECONDS)
        assertTrue(captured.error?.message, captured.ok); assertEquals(input.fits, captured.request.fits)
        val cancelled = EngineRuntime.offlineShieldRegeneration(context, input, AtomicBoolean(true)).get(30, TimeUnit.SECONDS)
        assertFalse(cancelled.ok); assertEquals("cancelled", cancelled.error!!.code); assertTrue(cancelled.series.isEmpty())
        compose.runOnUiThread { model.plot(context); model.stop(); model.plot(context); assertTrue(model.busy); assertTrue(model.cancelling) }
        compose.activityRule.scenario.recreate(); waitFor { !model.busy }
        assertSame(retained, model); assertNull(model.currentResult); plot()
        text("shield-graph-low", "-1e308"); text("shield-graph-high", "-1e308")
        click("shield-graph-plot"); waitFor { !model.busy }; assertNull(model.currentResult); assertNotNull(model.error)
        text("shield-graph-low", "2"); text("shield-graph-high", "2"); plot()
        click("shield-graph-fit-$source"); compose.onNodeWithTag("shield-graph-no-selection").assertExists()
        click("shield-graph-back"); click("shield-regeneration-graph-open")
        assertTrue(model.selected.isEmpty()); compose.onNodeWithTag("shield-graph-plot").assertIsNotEnabled()
    }
}
