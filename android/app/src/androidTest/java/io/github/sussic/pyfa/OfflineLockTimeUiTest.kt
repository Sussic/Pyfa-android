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

/** Run on disposable durable app data with offline_features_phase=lock_time and airplane mode. */
@RunWith(AndroidJUnit4::class)
class OfflineLockTimeUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineLockTimeModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun plot() {
        click("lock-graph-plot"); waitFor { !model.busy }
        assertTrue(model.error, model.currentResult?.ok == true)
    }
    @Test fun realOfflineComparisonBoundsCancellationSingletonAndReadOnlyHistory() {
        assertEquals("lock_time", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val ids = (1..9).map { index ->
            val before = EngineRuntime.library.value.map { it.id }.toSet()
            assertTrue(EngineRuntime.createEmptyFit(context, "Vexor", "Lock graph $index").get(120, TimeUnit.SECONDS).isSuccess)
            EngineRuntime.library.value.single { it.id !in before }.id
        }
        EngineRuntime.selectFit(context, ids.first()).get(30, TimeUnit.SECONDS)
        click("lock-graph-open"); waitFor { ids.first() in model.selected }
        compose.onNodeWithTag("lock-graph-search").performTextReplacement("Lock graph ")
        ids.drop(1).take(7).forEach { click("lock-graph-fit-$it") }
        assertEquals(8, model.selected.size)
        compose.onNodeWithTag("lock-graph-fit-${ids.last()}").assertIsNotEnabled()
        compose.runOnUiThread { model.select(ids.last()) }
        assertFalse(ids.last() in model.selected)
        val beforeFits = EngineRuntime.library.value
        val beforeState = EngineRuntime.offlineFeatureState(context, ids.first()).get(30, TimeUnit.SECONDS)
        val beforeNavigation = EngineRuntime.navigation.value
        plot()
        val result = checkNotNull(model.currentResult)
        assertEquals(ids.take(8).toSet(), result.series.map { it.fitId }.toSet())
        result.series.forEach { series ->
            assertEquals(201, series.x.size); assertEquals(25.0, series.x.first(), 0.0); assertEquals(500.0, series.x.last(), 0.0)
            assertNotNull(series.scanResolution); assertTrue(series.scanResolution!! > 0)
            assertTrue(series.y.all { it.isFinite() && it > 0 }); assertTrue(series.y.first() > series.y.last())
            compose.onNodeWithTag("lock-graph-scan-${series.fitId}").assertExists()
        }
        compose.onNodeWithTag("lock-graph-canvas").performScrollTo().assertIsDisplayed()
        assertEquals(beforeFits, EngineRuntime.library.value)
        assertEquals(beforeState, EngineRuntime.offlineFeatureState(context, ids.first()).get(30, TimeUnit.SECONDS))
        assertEquals(beforeNavigation, EngineRuntime.navigation.value)

        // Runtime captures the caller's collection before putting work on the serialized queue.
        val callerFits = linkedMapOf(ids.first() to beforeFits.single { it.id == ids.first() }.revision)
        val captured = OfflineLockTimeRequest("capture-map", beforeState.context, callerFits, resolution = 1)
        val pending = EngineRuntime.offlineLockTime(context, captured, AtomicBoolean(false))
        callerFits.clear()
        val capturedResult = pending.get(120, TimeUnit.SECONDS)
        assertTrue(capturedResult.ok); assertEquals(listOf(ids.first()), capturedResult.request.fits.keys.toList())
        val cancelled = EngineRuntime.offlineLockTime(context, capturedResult.request, AtomicBoolean(true)).get(30, TimeUnit.SECONDS)
        assertFalse(cancelled.ok); assertEquals("cancelled", cancelled.error!!.code); assertTrue(cancelled.series.isEmpty())

        compose.onNodeWithTag("lock-graph-low").performTextReplacement("0")
        assertNull(model.currentResult); click("lock-graph-plot")
        assertFalse(model.busy); compose.onNodeWithTag("lock-graph-error").assertExists()
        compose.onNodeWithTag("lock-graph-low").performTextReplacement("100")
        compose.onNodeWithTag("lock-graph-high").performTextReplacement("100")
        plot(); assertTrue(model.currentResult!!.series.all { it.x == listOf(100.0) && it.y.size == 1 })
        val retained = model
        compose.activityRule.scenario.recreate(); waitFor { !model.busy }
        assertSame(retained, model); assertEquals("100", model.low); assertEquals("100", model.high)
        assertEquals(ids.take(8).toSet(), model.selected)
        plot()
        val first = EngineRuntime.library.value.single { it.id == ids.first() }
        assertTrue(EngineRuntime.request(context, BridgeOperation.RenameFit(first.id, "Lock graph changed"), mapOf(first.id to first.revision))
            .get(120, TimeUnit.SECONDS).isSuccess)
        waitFor { model.currentResult == null }
        compose.runOnUiThread {
            model.plot(context); assertTrue(model.busy)
            model.stop(); model.plot(context)
            assertTrue(model.busy); assertTrue(model.cancelling); assertNull(model.currentResult)
        }
        waitFor { !model.busy }; assertNull(model.currentResult)
        plot()
        click("lock-graph-back"); click("cap-graph-open")
        val capacitor = ViewModelProvider(compose.activity)[OfflineCapacitorModel::class.java]
        waitFor { capacitor.selected.isNotEmpty() }
        click("cap-graph-plot"); waitFor { !capacitor.busy }
        assertTrue(capacitor.error, capacitor.result?.ok == true)
        compose.onNodeWithTag("cap-graph-canvas").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("cap-graph-axes").assertExists()
    }
}
