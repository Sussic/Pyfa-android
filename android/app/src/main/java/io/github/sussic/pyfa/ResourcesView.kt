package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

data class ResourceDetails(val used: StatValue, val total: StatValue, val unit: String,
    val overloaded: Boolean?, val usedDisplay: String?, val totalDisplay: String?,
    val usedDetail: String?, val totalDetail: String?)
data class FitResources(val fitId: String, val revision: Long, val resources: Map<String, ResourceDetails>)

class ResourcesModel : ViewModel() {
    var details by mutableStateOf<FitResources?>(null)
        private set
    var loading by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    private var requested: Pair<String, Long>? = null
    private var generation = 0

    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        requested = next
        details = null; error = null; loading = true
        val token = ++generation
        EngineRuntime.resourceDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Resources could not be loaded. Try again."
                else details = value
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

internal val RESOURCE_LABELS = linkedMapOf(
    "turret_hardpoints" to "Turret hardpoints", "launcher_hardpoints" to "Launcher hardpoints",
    "active_drones" to "Active drones", "fighter_tubes" to "Fighter tubes",
    "calibration" to "Calibration", "cpu" to "CPU", "powergrid" to "Powergrid",
    "drone_bay" to "Drone bay", "fighter_bay" to "Fighter bay",
    "drone_bandwidth" to "Drone bandwidth", "cargo_bay" to "Cargo bay",
)

@Composable
internal fun ResourcesView(model: ResourcesModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Resources", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("resources-back")) { Text("Back") }
    if (fit == null) {
        Text("Open a fit to view its resources.", modifier = Modifier.testTag("resources-no-fit"))
        return
    }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    Text("Used / capacity")
    if (model.loading) Text("Loading resources…", modifier = Modifier.testTag("resources-loading"))
    model.error?.let {
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("resources-error"))
        TextButton(onClick = { model.load(context, fit, retry = true) },
            modifier = Modifier.testTag("resources-retry")) { Text("Try again") }
    }
    val details = model.details?.takeIf { it.fitId == fit.id && it.revision == fit.revision } ?: return
    for ((name, label) in RESOURCE_LABELS) {
        val row = details.resources.getValue(name)
        ResourceCard(name, label, row, fit.id)
    }
}

@Composable
internal fun ResourceCard(name: String, label: String, row: ResourceDetails, fitId: String) {
        var expanded by rememberSaveable(fitId, name) { mutableStateOf(false) }
        Card(Modifier.fillMaxWidth().testTag("resources-row-$name")) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(label, style = MaterialTheme.typography.titleMedium)
                Text("${row.usedDisplay ?: "Unavailable"} / ${row.totalDisplay ?: "Unavailable"} ${row.unit}",
                    modifier = Modifier.testTag("resources-value-$name"))
                if (row.overloaded == true) Text("Over capacity", color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.testTag("resources-overload-$name"))
                TextButton(onClick = { expanded = !expanded }, modifier = Modifier.testTag("resources-details-$name")) {
                    Text(if (expanded) "Hide details" else "Details")
                }
                if (expanded) {
                    Text("Used: ${row.usedDetail ?: "Unavailable"} ${row.unit}", modifier = Modifier.testTag("resources-used-detail-$name"))
                    Text("Capacity: ${row.totalDetail ?: "Unavailable"} ${row.unit}", modifier = Modifier.testTag("resources-total-detail-$name"))
                    Text("Full precision used: ${if (row.used == StatValue.Unavailable) "Unavailable" else row.used.raw} ${row.unit}")
                    Text("Full precision capacity: ${if (row.total == StatValue.Unavailable) "Unavailable" else row.total.raw} ${row.unit}")
                }
            }
        }
}
