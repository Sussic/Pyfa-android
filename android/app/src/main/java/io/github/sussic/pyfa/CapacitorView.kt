package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

data class CapacitorScalar(val value: StatValue, val unit: String, val display: String?, val detail: String?)
data class CapacitorStability(val kind: String, val unit: String, val values: List<StatValue>, val display: String?)
data class FitCapacitor(val fitId: String, val revision: Long, val capacitor: Map<String, CapacitorScalar>, val stability: CapacitorStability)

internal val CAPACITOR_LABELS = linkedMapOf("capacity" to "Capacity", "effective_capacity" to "Effective capacity",
    "recharge" to "Recharge", "use" to "Use", "delta" to "Delta", "effective_excess" to "Effective excess gain",
    "neutralizer_resistance" to "Neutralizer resistance")

class CapacitorModel : ViewModel() {
    var details by mutableStateOf<FitCapacitor?>(null); private set
    var loading by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        requested = next; details = null; error = null; loading = true
        val token = ++generation
        EngineRuntime.capacitorDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Capacitor could not be loaded. Try again." else details = value
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun CapacitorView(model: CapacitorModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Capacitor", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("capacitor-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to view its capacitor.", Modifier.testTag("capacitor-no-fit")); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    if (model.loading) Text("Loading capacitor…", Modifier.testTag("capacitor-loading"))
    model.error?.let {
        Text(it, Modifier.testTag("capacitor-error"), color = MaterialTheme.colorScheme.error)
        TextButton(onClick = { model.load(context, fit, true) }, modifier = Modifier.testTag("capacitor-retry")) { Text("Try again") }
    }
    val details = model.details?.takeIf { it.fitId == fit.id && it.revision == fit.revision } ?: return
    val state = details.stability
    Text(when (state.kind) {
        "stable", "stable_range" -> "Stable: ${state.display}"
        "depletion" -> "Lasts ${state.display}"
        else -> "Stability unavailable"
    }, Modifier.testTag("capacitor-stability"))
    Text("Full precision: ${state.values.joinToString(" – ") { if (it == StatValue.Unavailable) "Unavailable" else it.raw.toString() }} ${state.unit}",
        Modifier.testTag("capacitor-state-raw"))
    for ((name, label) in CAPACITOR_LABELS) {
        val row = details.capacitor.getValue(name)
        var expanded by rememberSaveable(fit.id, name) { mutableStateOf(false) }
        Card(Modifier.testTag("capacitor-row-$name")) {
            Column(Modifier.padding(16.dp)) {
                Text(label, style = MaterialTheme.typography.titleMedium)
                val absent = if (name == "effective_capacity" || name == "effective_excess") "Not applicable" else "Unavailable"
                Text(row.display?.let { "$it ${row.unit}" } ?: absent, Modifier.testTag("capacitor-value-$name"))
                TextButton(onClick = { expanded = !expanded }, modifier = Modifier.testTag("capacitor-details-$name")) {
                    Text(if (expanded) "Hide details" else "Details")
                }
                if (expanded) {
                    Text(row.detail?.let { "$it ${row.unit}" } ?: absent, Modifier.testTag("capacitor-detail-$name"))
                    Text("Full precision: ${if (row.value == StatValue.Unavailable) absent else row.value.raw} ${row.unit}",
                        Modifier.testTag("capacitor-raw-$name"))
                }
            }
        }
    }
}
