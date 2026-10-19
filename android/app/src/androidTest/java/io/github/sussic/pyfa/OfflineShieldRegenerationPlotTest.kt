package io.github.sussic.pyfa

import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OfflineShieldRegenerationPlotTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun finiteScreenFractionsSurviveOverflowingSpansAndRetainOrdinaryCoordinates() {
        val max = Double.MAX_VALUE
        for ((value, expected) in listOf(-max to 0.0, -max / 2 to 0.25, 0.0 to 0.5, max / 2 to 0.75, max to 1.0)) {
            val fraction = offlinePlotFraction(value, -max, max)
            assertTrue(fraction.isFinite()); assertEquals(expected, fraction, 1e-15)
        }
        for (value in listOf(-50.0, -10.0, 0.0, 25.0, 100.0))
            assertEquals((value + 50.0) / 150.0, offlinePlotFraction(value, -50.0, 100.0), 0.0)
        assertEquals(0.5, offlinePlotFraction(max, max, max), 0.0)
        assertEquals(1.0, offlinePlotFraction(Double.MIN_VALUE, 0.0, Double.MIN_VALUE), 0.0)
        val adjacent = Math.nextUp(1e308)
        assertEquals(0.0, offlinePlotFraction(1e308, 1e308, adjacent), 0.0)
        assertEquals(1.0, offlinePlotFraction(adjacent, 1e308, adjacent), 0.0)
    }

    @Test fun signedHugeExtentsSingletonAndEmptyGraphKeepSharedTagsAndLegend() {
        compose.runOnUiThread { compose.activity.setContent { Column {
            OfflineSamplePlot(listOf(OfflinePlotSeries("Huge signed", listOf(-Double.MAX_VALUE, 0.0, Double.MAX_VALUE),
                listOf(Double.MAX_VALUE, 0.0, -Double.MAX_VALUE))), -Double.MAX_VALUE, Double.MAX_VALUE, "s", "HP/s", "shield-graph", "Empty")
            OfflineSamplePlot(listOf(OfflinePlotSeries("Singleton", listOf(42.0), listOf(-3.0))), 42.0, 42.0, "%", "HP/s", "shield-single", "Empty")
            OfflineSamplePlot(emptyList(), 0.0, 1.0, "HP", "HP", "shield-empty", "No shield samples.")
        } } }
        compose.onNodeWithTag("shield-graph-canvas").assertExists()
        compose.onNodeWithTag("shield-graph-axes").assertTextContains("HP/s", substring = true)
        compose.onNodeWithText("1. Huge signed").assertExists()
        compose.onNodeWithTag("shield-single-canvas").assertExists()
        compose.onNodeWithTag("shield-single-axes").assertTextEquals("X: 42.0–42.0 % · Y: -3.0–-3.0 HP/s")
        compose.onNodeWithTag("shield-empty-empty").assertTextEquals("No shield samples.")
        compose.onNodeWithTag("shield-empty-canvas").assertDoesNotExist()
    }
}
