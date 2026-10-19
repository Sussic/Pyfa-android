package io.github.sussic.pyfa

import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag

/** Displays already-sampled EOS thermodynamics; no heat calculation or rounding is performed here. */
@Composable
internal fun RackHeatDetails(heat: HeatEstimate, identity: String, index: Int) {
    var expanded by rememberSaveable(identity) { mutableStateOf(false) }
    Text("Estimated burnout: ${formatStat(heat.seconds)} · ${formatStat(heat.cycles)}",
        modifier = Modifier.testTag("rack-heat-$index"))
    TextButton(onClick = { expanded = !expanded }, modifier = Modifier.testTag("rack-heat-details-$index")) {
        Text(if (expanded) "Hide heat details" else "Heat details")
    }
    if (expanded) {
        fun raw(stat: Stat) = if (stat.value == StatValue.Unavailable) "Unavailable" else "${stat.value.raw} ${stat.unit}"
        Text("Full precision time to burnout: ${raw(heat.seconds)}", Modifier.testTag("rack-heat-seconds-$index"))
        Text("Full precision cycles to burnout: ${raw(heat.cycles)}", Modifier.testTag("rack-heat-cycles-$index"))
        Text("The estimate reflects this rack's current order, empty slots and overheated modules.")
        if (heat.probabilities.isEmpty()) Text("Heat-damage probabilities unavailable.", Modifier.testTag("rack-heat-no-probabilities-$index"))
        for ((sampleIndex, sample) in heat.probabilities.withIndex())
            Text("Heat-damage probability at ${sample.seconds} s: ${sample.value} (0–1)",
                Modifier.testTag("rack-heat-probability-$index-$sampleIndex"))
    }
}
