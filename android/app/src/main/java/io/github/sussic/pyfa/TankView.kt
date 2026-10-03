package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

data class TankScalar(val value: StatValue, val unit: String, val display: String?, val detail: String?)
data class TankVariant(val repairs: Map<String, TankScalar>, val pre: TankScalar, val full: TankScalar,
    val indicated: Boolean, val tooltip: String)
data class TankMode(val passiveShield: TankScalar, val reinforced: TankVariant, val sustained: TankVariant)
data class FitTank(val fitId: String, val revision: Long, val modes: Map<String, TankMode>)
private fun TankScalar.precision(): String = if (value == StatValue.Unavailable) "Unavailable" else value.raw.toString()
internal val TANK_REPAIRS = linkedMapOf("shieldRepair" to "Active shield boost", "armorRepair" to "Armor repair", "hullRepair" to "Hull repair")

class TankModel : ViewModel() {
    var details by mutableStateOf<FitTank?>(null); private set
    var loading by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        requested = next; details = null; error = null; loading = true
        val token = ++generation
        EngineRuntime.tankDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Tank could not be loaded. Try again." else details = value
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
private fun TankValue(name: String, label: String, value: TankScalar, fitId: String, variant: TankVariant? = null) {
    var expanded by rememberSaveable(fitId, name) { mutableStateOf(false) }
    Card(Modifier.testTag("tank-row-$name")) {
        Column(Modifier.padding(16.dp)) {
            Text(label, style = MaterialTheme.typography.titleMedium)
            Text(value.display?.let { "$it ${value.unit}" } ?: "Unavailable", Modifier.testTag("tank-value-$name"))
            TextButton(onClick = { expanded = !expanded }, modifier = Modifier.testTag("tank-details-$name")) {
                Text(if (expanded) "Hide details" else "Details")
            }
            if (expanded) {
                Text(value.detail?.let { "$it ${value.unit}" } ?: "Unavailable", Modifier.testTag("tank-detail-$name"))
                Text("Full precision: ${value.precision()} ${value.unit}", Modifier.testTag("tank-raw-$name"))
                variant?.let {
                    Text(if (it.indicated) it.tooltip else "No spool increase", Modifier.testTag("tank-spool-indication-$name"))
                    Text("Current: ${value.precision()} ${value.unit}", Modifier.testTag("tank-spool-current-$name"))
                    Text("Pre-spool: ${it.pre.detail ?: "Unavailable"} ${it.pre.unit} · Full precision: ${it.pre.precision()}", Modifier.testTag("tank-spool-pre-$name"))
                    Text("Full spool: ${it.full.detail ?: "Unavailable"} ${it.full.unit} · Full precision: ${it.full.precision()}", Modifier.testTag("tank-spool-full-$name"))
                }
            }
        }
    }
}

@Composable
internal fun TankView(model: TankModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Repair and tank", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("tank-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to view its tank.", Modifier.testTag("tank-no-fit")); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    if (model.loading) Text("Loading tank…", Modifier.testTag("tank-loading"))
    model.error?.let {
        Text(it, Modifier.testTag("tank-error"), color = MaterialTheme.colorScheme.error)
        TextButton(onClick = { model.load(context, fit, true) }, modifier = Modifier.testTag("tank-retry")) { Text("Try again") }
    }
    val details = model.details?.takeIf { it.fitId == fit.id && it.revision == fit.revision } ?: return
    var effective by rememberSaveable(fit.id) { mutableStateOf(true) }
    TextButton(onClick = { effective = !effective }, modifier = Modifier.testTag("tank-toggle")) {
        Text(if (effective) "Show raw HP/s" else "Show effective EHP/s")
    }
    val mode = details.modes.getValue(if (effective) "effective" else "raw")
    TankValue("passive", "Passive shield recharge", mode.passiveShield, fit.id)
    for ((stability, variant) in listOf("reinforced" to mode.reinforced, "sustained" to mode.sustained)) {
        Text(stability.replaceFirstChar { it.uppercase() }, style = MaterialTheme.typography.titleLarge)
        for ((name, label) in TANK_REPAIRS) {
            TankValue("$stability-$name", label, variant.repairs.getValue(name), fit.id, if (name == "armorRepair") variant else null)
        }
    }
}
