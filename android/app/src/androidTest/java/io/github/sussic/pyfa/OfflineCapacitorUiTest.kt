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

@RunWith(AndroidJUnit4::class)
class OfflineCapacitorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineCapacitorModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    @Test fun realOfflineComparisonInvalidationAndCancellationKeepOneWorkerRequest() {
        check(InstrumentationRegistry.getArguments().containsKey("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        fun create(name: String): String {
            val before = EngineRuntime.library.value.map { it.id }.toSet()
            assertTrue(EngineRuntime.createEmptyFit(context, "Vexor", name).get(120, TimeUnit.SECONDS).isSuccess)
            return EngineRuntime.library.value.single { it.id !in before }.id
        }
        val first = create("Capacitor first"); val second = create("Capacitor second")
        EngineRuntime.selectFit(context, first).get(30, TimeUnit.SECONDS)
        click("cap-graph-open"); waitFor { first in model.selected }
        compose.runOnUiThread { model.select(second) }
        click("cap-graph-plot"); waitFor { !model.busy && model.result != null }
        assertEquals(setOf(first, second), model.result!!.series.map { it.fitId }.toSet())
        compose.onNodeWithTag("cap-graph-canvas").performScrollTo().assertIsDisplayed()
        compose.onNodeWithTag("cap-graph-start").performTextReplacement("50")
        assertNull(model.result)
        click("cap-graph-plot"); waitFor { !model.busy && model.result != null }
        model.result!!.series.forEach { series ->
            assertEquals(0.0, series.x.first(), 0.0)
            assertEquals(series.capacityGj / 2, series.y.first(), series.capacityGj * 1e-9)
        }
        val changed = EngineRuntime.library.value.single { it.id == first }
        assertTrue(EngineRuntime.request(context, BridgeOperation.RenameFit(first, "Capacitor renamed"), mapOf(first to changed.revision)).get(120, TimeUnit.SECONDS).isSuccess)
        waitFor { model.result == null }
        // Stop and attempt another launch in the same UI turn. Even if EOS is still
        // executing, the launch gate remains held until its future completes.
        compose.runOnUiThread {
            model.plot(context); assertTrue(model.busy)
            model.stop(); assertTrue(model.busy)
            model.plot(context); assertTrue(model.busy); assertNull(model.result)
        }
        waitFor { !model.busy }
        assertNull(model.result)
        click("cap-graph-plot"); waitFor { !model.busy && model.result != null }
    }
}
