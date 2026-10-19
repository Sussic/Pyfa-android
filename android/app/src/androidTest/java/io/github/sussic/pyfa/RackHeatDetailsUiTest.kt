package io.github.sussic.pyfa

import androidx.activity.compose.setContent
import androidx.compose.runtime.Composable
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Presentation assertions only; EOS numerical parity remains an independent reference gate. */
@RunWith(AndroidJUnit4::class)
class RackHeatDetailsUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private fun show(content: @Composable () -> Unit) {
        compose.runOnUiThread { compose.activity.setContent(content = content) }
    }
    @Test fun precisionAndSourceHeatDamageProbabilitiesAreExposedWithoutRounding() {
        val heat = HeatEstimate(Stat(StatValue.Integer(123456789L), "cycles"), Stat(StatValue.Decimal(9.876543219), "s"),
            listOf(HeatProbability(1.0, 0.0123456789123), HeatProbability(10.0, 0.9876543210987)))
        show { MaterialTheme { Column { RackHeatDetails(heat, "fit:module", 2) } } }
        compose.onNodeWithTag("rack-heat-seconds-2").assertDoesNotExist()
        compose.onNodeWithTag("rack-heat-details-2").performClick()
        compose.onNodeWithTag("rack-heat-seconds-2").assertTextEquals("Full precision time to burnout: 9.876543219 s")
        compose.onNodeWithTag("rack-heat-cycles-2").assertTextEquals("Full precision cycles to burnout: 123456789 cycles")
        compose.onNodeWithTag("rack-heat-probability-2-0").assertTextEquals("Heat-damage probability at 1.0 s: 0.0123456789123 (0–1)")
        compose.onNodeWithTag("rack-heat-probability-2-1").assertTextEquals("Heat-damage probability at 10.0 s: 0.9876543210987 (0–1)")
        compose.onNodeWithTag("rack-heat-details-2").performClick()
        compose.onNodeWithTag("rack-heat-seconds-2").assertDoesNotExist()
    }
    @Test fun unavailableHeatNeverDisplaysFabricatedZeroOrProbability() {
        val heat = HeatEstimate(Stat(StatValue.Unavailable, "cycles"), Stat(StatValue.Unavailable, "s"), emptyList())
        show { MaterialTheme { Column { RackHeatDetails(heat, "fit:unavailable", 1) } } }
        compose.onNodeWithTag("rack-heat-details-1").performClick()
        compose.onNodeWithTag("rack-heat-seconds-1").assertTextEquals("Full precision time to burnout: Unavailable")
        compose.onNodeWithTag("rack-heat-cycles-1").assertTextEquals("Full precision cycles to burnout: Unavailable")
        compose.onNodeWithTag("rack-heat-no-probabilities-1").assertTextEquals("Heat-damage probabilities unavailable.")
        compose.onNodeWithTag("rack-heat-probability-1-0").assertDoesNotExist()
    }
}
