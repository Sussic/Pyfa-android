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

/** Run on disposable durable app data with offline_features_phase=mobility and airplane mode. */
@RunWith(AndroidJUnit4::class)
class OfflineMobilityUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineMobilityModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun plot() {
        click("mobility-graph-plot"); waitFor { !model.busy }
        assertTrue(model.error, model.currentResult?.ok == true)
    }
    @Test fun allModesKeepUnitsTargetDraftsReadOnlyStateAndBoundedCancellation() {
        assertEquals("mobility", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val ids = (1..2).map { index ->
            val before = EngineRuntime.library.value.map { it.id }.toSet()
            assertTrue(EngineRuntime.createEmptyFit(context, "Vexor", "Mobility graph $index").get(120, TimeUnit.SECONDS).isSuccess)
            EngineRuntime.library.value.single { it.id !in before }.id
        }
        EngineRuntime.selectFit(context, ids.first()).get(30, TimeUnit.SECONDS)
        click("mobility-graph-open"); waitFor { ids.first() in model.selected }
        click("mobility-graph-fit-${ids.last()}")
        val beforeFits = EngineRuntime.library.value
        val beforeState = EngineRuntime.offlineFeatureState(context, ids.first()).get(30, TimeUnit.SECONDS)
        val beforeNavigation = EngineRuntime.navigation.value
        for (mode in OfflineMobilityMode.entries) {
            click("mobility-graph-mode-${mode.quantity}")
            if (mode.needsMass) compose.onNodeWithTag("mobility-graph-target-mass").assertExists()
            else compose.onNodeWithTag("mobility-graph-target-mass").assertDoesNotExist()
            if (mode.needsInertia) compose.onNodeWithTag("mobility-graph-target-inertia").assertExists()
            else compose.onNodeWithTag("mobility-graph-target-inertia").assertDoesNotExist()
            plot()
            val result = checkNotNull(model.currentResult)
            assertEquals(mode, result.request.mode)
            assertEquals(if (mode.needsMass) 1300.0 else null, result.request.targetMassMkg)
            assertEquals(if (mode.needsInertia) 0.015 else null, result.request.targetInertia)
            assertEquals(ids.toSet(), result.series.map { it.fitId }.toSet())
            result.series.forEach { series ->
                assertEquals(201, series.x.size); assertEquals(0.0, series.x.first(), 0.0); assertEquals(30.0, series.x.last(), 1e-12)
                assertTrue(series.y.all { it.isFinite() }); assertTrue(series.maxVelocityMps!! > 0); assertTrue(series.alignTimeSeconds!! > 0)
                compose.onNodeWithTag("mobility-graph-speed-${series.fitId}").assertExists()
                compose.onNodeWithTag("mobility-graph-align-${series.fitId}").assertExists()
            }
            compose.onNodeWithTag("mobility-graph-canvas").performScrollTo().assertIsDisplayed()
            compose.onNodeWithTag("mobility-graph-axes").assertTextContains(mode.unit, substring = true)
        }
        assertEquals(beforeFits, EngineRuntime.library.value)
        assertEquals(beforeState, EngineRuntime.offlineFeatureState(context, ids.first()).get(30, TimeUnit.SECONDS))
        assertEquals(beforeNavigation, EngineRuntime.navigation.value)
        compose.onNodeWithTag("mobility-graph-bump-explanation").assertExists()
        compose.onNodeWithTag("mobility-graph-drift-explanation").assertExists()
        compose.onNodeWithTag("mobility-graph-target-mass").performTextReplacement("1500")
        compose.onNodeWithTag("mobility-graph-target-inertia").performTextReplacement("0.02")
        assertNull(model.currentResult)
        click("mobility-graph-mode-speed"); plot()
        assertNull(model.currentResult!!.request.targetMassMkg); assertNull(model.currentResult!!.request.targetInertia)
        click("mobility-graph-mode-bumpDistance")
        assertEquals("1500", model.targetMass); assertEquals("0.02", model.targetInertia)
        val retained = model
        compose.activityRule.scenario.recreate(); waitFor { !model.busy }
        assertSame(retained, model); assertEquals(OfflineMobilityMode.BUMP_DISTANCE, model.mode)
        assertEquals("1500", model.targetMass); assertEquals("0.02", model.targetInertia)
        plot()
        // An invalid hidden draft must not prevent an unrelated speed graph.
        compose.onNodeWithTag("mobility-graph-target-mass").performTextReplacement("bad")
        click("mobility-graph-plot"); assertFalse(model.busy); compose.onNodeWithTag("mobility-graph-error").assertExists()
        click("mobility-graph-mode-speed"); plot()
        click("mobility-graph-mode-bumpDistance"); assertEquals("bad", model.targetMass)
        compose.onNodeWithTag("mobility-graph-target-mass").performTextReplacement("0")
        compose.onNodeWithTag("mobility-graph-target-inertia").performTextReplacement("0")
        plot(); assertTrue(model.currentResult!!.series.all { series -> series.y.all { it == 0.0 } })
        compose.onNodeWithTag("mobility-graph-low").performTextReplacement("2")
        compose.onNodeWithTag("mobility-graph-high").performTextReplacement("2")
        plot(); assertTrue(model.currentResult!!.series.all { it.x == listOf(2.0) && it.y.size == 1 })
        val fit = EngineRuntime.library.value.single { it.id == ids.first() }
        assertTrue(EngineRuntime.request(context, BridgeOperation.RenameFit(fit.id, "Mobility changed"), mapOf(fit.id to fit.revision))
            .get(120, TimeUnit.SECONDS).isSuccess)
        waitFor { model.currentResult == null }
        compose.runOnUiThread {
            model.plot(context); assertTrue(model.busy)
            model.stop(); model.plot(context)
            assertTrue(model.busy); assertTrue(model.cancelling); assertNull(model.currentResult)
        }
        waitFor { !model.busy }; assertNull(model.currentResult)
        plot()
        val input = model.currentResult!!.request
        val callerFits = input.fits.toMutableMap()
        val pending = EngineRuntime.offlineMobility(context, input.copy(fits = callerFits), AtomicBoolean(false))
        callerFits.clear()
        assertTrue(pending.get(120, TimeUnit.SECONDS).ok)
        val cancelled = EngineRuntime.offlineMobility(context, input, AtomicBoolean(true)).get(30, TimeUnit.SECONDS)
        assertFalse(cancelled.ok); assertEquals("cancelled", cancelled.error!!.code); assertTrue(cancelled.series.isEmpty())
    }
}
