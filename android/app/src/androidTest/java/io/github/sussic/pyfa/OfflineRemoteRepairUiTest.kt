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
 * Deferred G05.1 native gate: disposable durable data, airplane mode, and
 * offline_features_phase=remote_repair_graph. UI causal/read-only checks complement
 * the separately qualified reconstructed-original oracle; they do not replace it.
 */
@RunWith(AndroidJUnit4::class)
class OfflineRemoteRepairUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineRemoteRepairModel::class.java]
    private val modules get() = ViewModelProvider(compose.activity)[ModuleEditorModel::class.java]
    private val states get() = ViewModelProvider(compose.activity)[BulkStateEditorModel::class.java]
    private val historyModel get() = ViewModelProvider(compose.activity)[EditHistoryModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun history(id: String) = EngineRuntime.editHistory(context, id).get(30, TimeUnit.SECONDS)
    private fun plot(): OfflineRemoteRepairResult {
        click("remote-repair-graph-plot"); waitFor { !model.busy }
        assertTrue(model.error, model.currentResult?.ok == true)
        return model.currentResult!!
    }
    private fun prepare() {
        assertEquals("remote_repair_graph", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
    }
    private fun sourceSpec(): FitSpec {
        val cases = instrumentation.context.assets.open("output-expected.json").bufferedReader().use {
            JSONObject(it.readText()).getJSONArray("cases")
        }
        val raw = (0 until cases.length()).map { cases.getJSONObject(it).getJSONObject("spec") }
            .single { it.getString("name") == "All outgoing" }
        assertFalse(raw.getBoolean("ignore_restrictions")); assertEquals(0, raw.getJSONArray("cargo").length())
        raw.remove("ignore_restrictions"); raw.remove("cargo")
        return BridgeCodec.decodeFitSpec(raw)
    }
    private fun create(spec: FitSpec): String {
        val result = EngineRuntime.request(context, BridgeOperation.CreateFit(spec), emptyMap()).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess)
        return result.fits.single().id
    }
    private fun showSourceRates(series: OfflineRemoteRepairSeries) {
        for ((key, value) in listOf("shield" to series.sourceRates.shield, "armor" to series.sourceRates.armor, "hull" to series.sourceRates.hull)) {
            compose.onNodeWithTag("remote-repair-graph-source-$key-${series.fitId}").performScrollTo()
                .assertTextEquals("Current source $key: $value HP/s")
        }
    }

    @Test fun actualSourceStateEditReturnUndoRecreationAndReadOnlyComparisonUseCurrentRevisions() {
        prepare()
        val prefix = "Remote repair UI ${System.nanoTime()}"
        val source = create(sourceSpec().copy(name = "$prefix source"))
        val empty = create(sourceSpec().copy(name = "$prefix empty", modules = emptyList()))
        EngineRuntime.selectFit(context, source).get(30, TimeUnit.SECONDS)
        click("remote-repair-graph-open"); waitFor { source in model.selected }
        text("remote-repair-graph-search", prefix); click("remote-repair-graph-fit-$empty")
        assertEquals(setOf(source, empty), model.selected)
        assertTrue(model.ancillaryReload); assertTrue(model.ignoreLockRange); assertFalse(model.ignoreDroneControlRange)
        val beforeFits = EngineRuntime.library.value
        val beforeNavigation = EngineRuntime.navigation.value
        val beforeRecent = EngineRuntime.recent.value
        val beforeState = EngineRuntime.offlineFeatureState(context, source).get(30, TimeUnit.SECONDS)
        val beforeHistory = history(source)
        val baseline = plot()
        val originalSource = baseline.series.single { it.fitId == source }
        assertTrue(originalSource.sourceRates.shield > 0.0); assertTrue(originalSource.sourceRates.armor > 0.0)
        assertTrue(originalSource.sourceRates.hull > 0.0); assertTrue(originalSource.y.first() > 0.0)
        assertTrue(baseline.series.single { it.fitId == empty }.y.all { it == 0.0 })
        assertEquals(OfflineRemoteRepairSourceRates(0.0, 0.0, 0.0), baseline.series.single { it.fitId == empty }.sourceRates)
        baseline.series.forEach { row ->
            assertEquals(fit(row.fitId).revision, row.revision)
            assertTrue(row.x.size in 51..201); assertTrue(row.x.zipWithNext().all { (a, b) -> a <= b })
            assertTrue(row.y.all { it.isFinite() }); showSourceRates(row)
        }
        compose.onNodeWithTag("remote-repair-graph-canvas").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("remote-repair-graph-axes").assertTextContains("km", substring = true).assertTextContains("HP/s", substring = true)
        compose.onNodeWithTag("remote-repair-graph-source-explanation").assertTextContains("ancillary-reload override", substring = true)
        compose.onNodeWithTag("remote-repair-graph-rate-explanation").assertTextContains("Excludes capacitor transfer", substring = true)
        assertEquals(beforeFits, EngineRuntime.library.value); assertEquals(beforeNavigation, EngineRuntime.navigation.value)
        assertEquals(beforeRecent, EngineRuntime.recent.value); assertEquals(beforeHistory, history(source))
        assertEquals(beforeState, EngineRuntime.offlineFeatureState(context, source).get(30, TimeUnit.SECONDS))

        text("remote-repair-graph-high", "75.25")
        click("remote-repair-graph-ancillary"); click("remote-repair-graph-lock"); click("remote-repair-graph-drone-control")
        assertNull(model.currentResult)
        val changedOptions = plot()
        assertFalse(changedOptions.request.ancillaryReload); assertFalse(changedOptions.request.ignoreLockRange)
        assertTrue(changedOptions.request.ignoreDroneControlRange)
        assertEquals(beforeFits, EngineRuntime.library.value); assertEquals(beforeHistory, history(source))
        assertEquals(beforeNavigation, EngineRuntime.navigation.value)

        // Leave the graph, use the real source module-state editor, and return.
        click("remote-repair-graph-back"); click("modules-open")
        waitFor { !modules.loading && modules.details?.let { it.fitId == source && it.revision == fit(source).revision } == true }
        val armorIndex = fit(source).modules.single { it.name == "Medium Remote Armor Repairer II" }.index
        click("modules-bulk-states")
        waitFor { !states.loading && states.options?.revision == fit(source).revision }
        click("bulk-states-reference-$armorIndex")
        assertEquals(setOf(armorIndex), states.selected); assertEquals(BulkScope.SELECTED, states.scope)
        assertEquals(ModuleState.ONLINE, states.options!!.modules.single { it.index == armorIndex }.clickStates.getValue(StateClick.CYCLE))
        val revision = fit(source).revision
        click("bulk-states-apply")
        waitFor { !states.editing && fit(source).revision > revision && states.options?.revision == fit(source).revision }
        assertNull(states.error); assertEquals(ModuleState.ONLINE, fit(source).modules.single { it.index == armorIndex }.state)
        assertEquals(beforeHistory.undoCount + 1, history(source).undoCount)
        click("bulk-states-back"); click("modules-back"); click("remote-repair-graph-open")
        waitFor { model.currentResult == null }
        assertEquals(setOf(source, empty), model.selected); assertEquals("75.25", model.high); assertEquals(prefix, model.query)
        assertFalse(model.ancillaryReload); assertFalse(model.ignoreLockRange); assertTrue(model.ignoreDroneControlRange)
        val edited = plot().series.single { it.fitId == source }
        assertEquals(fit(source).revision, edited.revision)
        assertTrue(edited.sourceRates.armor < originalSource.sourceRates.armor)
        assertTrue(edited.y.first() < originalSource.y.first()); showSourceRates(edited)
        // Undo from the actual global UI must invalidate this completed graph.
        waitFor { !historyModel.loading && historyModel.options?.revision == fit(source).revision }
        click("history-undo")
        waitFor { !historyModel.editing && fit(source).modules.single { it.index == armorIndex }.state == ModuleState.ACTIVE }
        waitFor { model.currentResult == null }
        val restored = plot().series.single { it.fitId == source }
        assertEquals(originalSource.sourceRates, restored.sourceRates)
        assertEquals(originalSource.y.first(), restored.y.first(), 1e-9)

        text("remote-repair-graph-high", "invalid retained draft")
        click("remote-repair-graph-plot"); assertFalse(model.busy)
        compose.onNodeWithTag("remote-repair-graph-error").assertExists()
        val retained = model
        compose.activityRule.scenario.recreate(); waitFor { !model.busy }
        assertSame(retained, model); assertEquals("invalid retained draft", model.high)
        assertEquals(setOf(source, empty), model.selected); assertEquals(prefix, model.query)
        assertFalse(model.ancillaryReload); assertFalse(model.ignoreLockRange); assertTrue(model.ignoreDroneControlRange)
        text("remote-repair-graph-low", "2"); text("remote-repair-graph-high", "2")
        assertTrue(plot().series.all { it.x == listOf(2.0) && it.y.size == 1 })

        // Runtime capture prevents a mutable caller map changing queued work.
        val input = model.currentResult!!.request
        val mutableFits = input.fits.toMutableMap()
        val pending = EngineRuntime.offlineRemoteRepair(context, input.copy(fits = mutableFits), AtomicBoolean(false))
        mutableFits.clear()
        val captured = pending.get(120, TimeUnit.SECONDS)
        assertTrue(captured.error?.message, captured.ok); assertEquals(input.fits, captured.request.fits)
        assertEquals(input.fits.keys.toList(), captured.series.map { it.fitId })
        val cancelled = EngineRuntime.offlineRemoteRepair(context, input, AtomicBoolean(true)).get(30, TimeUnit.SECONDS)
        assertFalse(cancelled.ok); assertEquals("cancelled", cancelled.error!!.code); assertTrue(cancelled.series.isEmpty())
        compose.runOnUiThread { model.plot(context); model.stop(); model.plot(context); assertTrue(model.busy); assertTrue(model.cancelling) }
        waitFor { !model.busy }; assertNull(model.currentResult)
        plot()
        click("remote-repair-graph-fit-$source")
        plot(); compose.onNodeWithTag("remote-repair-graph-zero").assertExists()
        click("remote-repair-graph-fit-$empty")
        compose.onNodeWithTag("remote-repair-graph-no-selection").assertExists()
        click("remote-repair-graph-back"); click("remote-repair-graph-open")
        assertTrue(model.selected.isEmpty()); compose.onNodeWithTag("remote-repair-graph-plot").assertIsNotEnabled()
    }

    @Test fun ancillaryControlChangesAppliedCurveWithoutRelabelingSourceLayerRates() {
        prepare()
        val source = create(sourceSpec().copy(name = "Remote repair ancillary ${System.nanoTime()}", factorReload = false,
            modules = listOf(ModuleSpec("Small Ancillary Remote Armor Repairer", ModuleState.ACTIVE, "Nanite Repair Paste"),
                ModuleSpec("Small Ancillary Remote Shield Booster", ModuleState.ACTIVE, "Cap Booster 25"))))
        EngineRuntime.selectFit(context, source).get(30, TimeUnit.SECONDS)
        click("remote-repair-graph-open"); waitFor { model.selected == setOf(source) }
        val beforeFits = EngineRuntime.library.value; val beforeHistory = history(source)
        val included = plot().series.single()
        showSourceRates(included)
        val sourceTotal = included.sourceRates.shield + included.sourceRates.armor + included.sourceRates.hull
        assertTrue("Source settings must remain separate from graph ancillary override", sourceTotal > included.y.first())
        click("remote-repair-graph-ancillary")
        val excluded = plot().series.single()
        assertEquals(included.sourceRates, excluded.sourceRates)
        assertTrue(excluded.y.first() > included.y.first()); showSourceRates(excluded)
        assertEquals(beforeFits, EngineRuntime.library.value); assertEquals(beforeHistory, history(source))
        click("remote-repair-graph-ancillary")
        val restored = plot().series.single()
        assertEquals(included.sourceRates, restored.sourceRates); assertEquals(included.x, restored.x); assertEquals(included.y, restored.y)
    }
    /** Deferred integration gate: requires reviewed production selected-time admission. */
    @Test fun selectedTimeLabelsClampingSourceRatesAndDraftsSurviveBackAndRecreation() {
        prepare()
        val source = create(sourceSpec().copy(name = "Selected-time repair ${System.nanoTime()}"))
        EngineRuntime.selectFit(context, source).get(30, TimeUnit.SECONDS)
        click("remote-repair-graph-open"); waitFor { model.selected == setOf(source) }
        val beforeFits = EngineRuntime.library.value; val beforeHistory = history(source)
        val current = plot()
        assertNull(current.request.time)
        compose.onNodeWithTag("remote-repair-graph-time-explanation").performScrollTo().assertTextContains("Current rate", substring = true)
        text("remote-repair-graph-time", "-5")
        assertNull(model.currentResult)
        val selected = plot()
        assertEquals(-5.0, selected.request.time!!, 0.0); assertEquals(0.0, selected.effectiveTime!!, 0.0)
        assertEquals(current.series.single().sourceRates, selected.series.single().sourceRates)
        showSourceRates(selected.series.single())
        compose.onNodeWithTag("remote-repair-graph-applied-label").performScrollTo().assertTextContains("Selected-time", substring = true)
        compose.onNodeWithTag("remote-repair-graph-time-explanation").performScrollTo()
            .assertTextContains("Requested time: -5.0 s", substring = true)
            .assertTextContains("effective time: 0.0 s", substring = true).assertTextContains("clamped", substring = true)
        text("remote-repair-graph-time", "invalid retained time")
        click("remote-repair-graph-plot"); assertFalse(model.busy); assertNotNull(model.error)
        click("remote-repair-graph-back"); click("remote-repair-graph-open")
        assertEquals("invalid retained time", model.time); assertEquals(setOf(source), model.selected)
        val retained = model
        compose.activityRule.scenario.recreate(); waitFor { !model.busy }
        assertSame(retained, model); assertEquals("invalid retained time", model.time)
        text("remote-repair-graph-time", "0")
        val zero = plot(); assertEquals(2, zero.request.version); assertEquals(0.0, zero.effectiveTime!!, 0.0)
        text("remote-repair-graph-time", "")
        val restored = plot(); assertEquals(1, restored.request.version); assertNull(restored.request.time)
        assertEquals(current.series, restored.series)
        assertEquals(beforeFits, EngineRuntime.library.value); assertEquals(beforeHistory, history(source))
    }

    /** Deferred integration gate, not numerical parity or amount admission evidence. */
    @Test fun amountControlRequiresTimeLabelsHpAndRetainsModeDraftSelectionAcrossNavigation() {
        prepare()
        val source = create(sourceSpec().copy(name = "Amount repair ${System.nanoTime()}"))
        EngineRuntime.selectFit(context, source).get(30, TimeUnit.SECONDS)
        click("remote-repair-graph-open"); waitFor { model.selected == setOf(source) }
        val beforeFits = EngineRuntime.library.value; val beforeHistory = history(source)
        val current = plot()
        click("remote-repair-graph-ordinate-amount")
        compose.onNodeWithTag("remote-repair-graph-ordinate-amount").assertIsSelected()
        assertNull(model.currentResult); assertEquals("", model.time)
        click("remote-repair-graph-plot")
        assertFalse(model.busy); assertNull(model.currentResult)
        compose.onNodeWithTag("remote-repair-graph-error").performScrollTo()
            .assertTextContains("requires a finite selected time", substring = true)
        for ((draft, effective) in listOf("0" to 0.0, "-5" to 0.0, "3000" to 2500.0)) {
            text("remote-repair-graph-time", draft)
            val amount = plot()
            assertEquals(OfflineRemoteRepairOrdinate.AMOUNT, amount.request.ordinate)
            assertEquals(draft.toDouble(), amount.request.time!!, 0.0)
            assertEquals(effective, amount.effectiveTime!!, 0.0)
            assertEquals(current.series.single().sourceRates, amount.series.single().sourceRates)
            showSourceRates(amount.series.single())
            compose.onNodeWithTag("remote-repair-graph-applied-label").performScrollTo()
                .assertTextContains("Accumulated applied repair (HP)", substring = true)
            compose.onNodeWithTag("remote-repair-graph-axes").performScrollTo()
                .assertTextContains("HP", substring = true).assertTextContains("km", substring = true)
                .assert(hasText("HP/s", substring = true).not())
            compose.onNodeWithTag("remote-repair-graph-source-explanation").performScrollTo()
                .assertTextContains("Current source rates (HP/s), independent", substring = true)
            if (draft != "0") compose.onNodeWithTag("remote-repair-graph-time-explanation").performScrollTo()
                .assertTextContains("effective time: $effective s", substring = true).assertTextContains("clamped", substring = true)
        }
        text("remote-repair-graph-time", "invalid amount draft")
        click("remote-repair-graph-ordinate-rate")
        assertEquals("invalid amount draft", model.time)
        click("remote-repair-graph-ordinate-amount")
        click("remote-repair-graph-back"); click("remote-repair-graph-open")
        assertEquals("invalid amount draft", model.time); assertEquals(setOf(source), model.selected)
        assertEquals(OfflineRemoteRepairOrdinate.AMOUNT, model.ordinate)
        val retained = model
        compose.activityRule.scenario.recreate(); waitFor { !model.busy }
        assertSame(retained, model); assertEquals("invalid amount draft", model.time)
        compose.onNodeWithTag("remote-repair-graph-ordinate-amount").performScrollTo().assertIsSelected()
        text("remote-repair-graph-time", "0")
        // The serialized worker cannot relinquish ownership during a synchronous mode switch.
        compose.runOnUiThread {
            model.plot(context); model.selectOrdinate(OfflineRemoteRepairOrdinate.RATE); model.plot(context)
            assertTrue(model.busy); assertTrue(model.cancelling); assertNull(model.currentResult)
        }
        waitFor { !model.busy }; assertNull(model.currentResult)
        text("remote-repair-graph-time", "")
        val restored = plot()
        assertEquals(1, restored.request.version); assertEquals(current.series, restored.series)
        assertEquals(beforeFits, EngineRuntime.library.value); assertEquals(beforeHistory, history(source))
    }


    /** Deferred device gate: both time modes, independent drafts, rendering and actual worker ownership. */
    @Test fun timeAxisBothOrdinatesRetainIndependentDraftsAndRenderOriginalOrderAcrossRecreation() {
        prepare()
        val source = create(sourceSpec().copy(name = "Time-axis repair ${System.nanoTime()}"))
        EngineRuntime.selectFit(context, source).get(30, TimeUnit.SECONDS)
        click("remote-repair-graph-open"); waitFor { model.selected == setOf(source) }
        val beforeFits = EngineRuntime.library.value; val beforeHistory = history(source)
        text("remote-repair-graph-high", "75"); text("remote-repair-graph-time", "9")
        click("remote-repair-graph-axis-time")
        compose.onNodeWithTag("remote-repair-graph-axis-time").assertIsSelected()
        text("remote-repair-graph-low", "-1"); text("remote-repair-graph-high", "3")
        for (ordinate in listOf("rate", "amount")) {
            click("remote-repair-graph-ordinate-$ordinate")
            text("remote-repair-graph-distance", "")
            val bypassed = plot()
            assertNull(bypassed.request.distance); assertNull(bypassed.request.time)
            assertEquals(OfflineRemoteRepairAxis.TIME, bypassed.request.axis)
            assertEquals(0.0, bypassed.request.effectiveLow, 0.0)
            bypassed.series.forEach { row ->
                assertTrue(OfflineRemoteRepairCodec.timeCoordinates(row.x, row.y, 0.0, 3.0))
                assertTrue(row.x.maxOrNull()!! <= bypassed.plotHigh); showSourceRates(row)
            }
            compose.onNodeWithTag("remote-repair-graph-canvas").performScrollTo().assertIsDisplayed()
            compose.onNodeWithTag("remote-repair-graph-time-explanation").performScrollTo()
                .assertTextContains("Requested time range: -1.0–3.0 s", substring = true)
                .assertTextContains("effective: 0.0–3.0 s", substring = true)
            compose.onNodeWithTag("remote-repair-graph-axes").performScrollTo().assertTextContains(" s", substring = true)
            text("remote-repair-graph-distance", "0")
            val zero = plot(); assertEquals(0.0, zero.request.distance!!, 0.0)
            assertEquals(bypassed.series.single().sourceRates, zero.series.single().sourceRates)
        }
        text("remote-repair-graph-distance", "invalid retained distance")
        click("remote-repair-graph-axis-distance")
        assertEquals("75", model.high); assertEquals("9", model.time)
        click("remote-repair-graph-axis-time"); assertEquals("3", model.high)
        click("remote-repair-graph-back"); click("remote-repair-graph-open")
        val retained = model
        compose.activityRule.scenario.recreate(); waitFor { !model.busy }
        assertSame(retained, model); assertEquals(OfflineRemoteRepairAxis.TIME, model.axis)
        assertEquals("invalid retained distance", model.distance); assertEquals("-1", model.low)
        assertEquals(OfflineRemoteRepairOrdinate.AMOUNT, model.ordinate)
        text("remote-repair-graph-distance", "")
        compose.runOnUiThread {
            model.plot(context)
            for (axis in OfflineRemoteRepairAxis.values()) for (ordinate in OfflineRemoteRepairOrdinate.values()) {
                model.selectAxis(axis); model.selectOrdinate(ordinate); model.plot(context)
                assertTrue(model.busy); assertTrue(model.cancelling); assertNull(model.currentResult)
            }
            model.cancel()
        }
        waitFor { !model.busy }; assertNull(model.currentResult)
        val restored = plot(); assertEquals(OfflineRemoteRepairAxis.TIME, restored.request.axis)
        assertEquals(beforeFits, EngineRuntime.library.value); assertEquals(beforeHistory, history(source))
    }
}
