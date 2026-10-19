package io.github.sussic.pyfa

import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.Composable
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Source regression for the shared surface; screenshot and accessibility review remain separate gates. */
@RunWith(AndroidJUnit4::class)
class OfflineSamplePlotTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private fun show(content: @Composable () -> Unit) {
        // Reuse the real manifest-declared Activity; no unregistered test host is required.
        compose.runOnUiThread { compose.activity.setContent(content = content) }
    }
    @Test fun capacitorVerticalStepsRetainExistingTagsUnitsAndLegend() {
        show { Column {
            OfflineSamplePlot(listOf(OfflinePlotSeries("fit", listOf(0.0, 5.0, 5.0), listOf(100.0, 95.0, 60.0))),
                0.0, 10.0, "s", "GJ", "cap-graph", "No capacitor samples in this range.")
        } }
        compose.onNodeWithTag("cap-graph-canvas").assertExists()
        compose.onNodeWithTag("cap-graph-axes").assertTextEquals("X: 0.0–10.0 s · Y: 60.0–100.0 GJ")
        compose.onNodeWithText("1. fit").assertExists()
        compose.onNodeWithTag("cap-graph-empty").assertDoesNotExist()
    }
    @Test fun singletonLockTimeAndEmptyCapacitorNeedNoSyntheticPoints() {
        show { Column {
            OfflineSamplePlot(listOf(OfflinePlotSeries("Lock fit", listOf(100.0), listOf(4.0))),
                100.0, 100.0, "m", "s", "lock-graph", "No lock-time samples in this range.")
            OfflineSamplePlot(listOf(OfflinePlotSeries("empty", emptyList(), emptyList())),
                0.0, 300.0, "s", "GJ", "cap-graph", "No capacitor samples in this range.")
        } }
        compose.onNodeWithTag("lock-graph-canvas").assertExists()
        compose.onNodeWithTag("lock-graph-axes").assertTextEquals("X: 100.0–100.0 m · Y: 4.0–4.0 s")
        compose.onNodeWithText("1. Lock fit").assertExists()
        compose.onNodeWithTag("cap-graph-empty").assertTextEquals("No capacitor samples in this range.")
        compose.onNodeWithTag("cap-graph-canvas").assertDoesNotExist()
    }
}
