package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

class SystemSecurityModel : ViewModel() {
    var details by mutableStateOf<SystemSecurityDetails?>(null); private set
    var loading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    private fun fit() = (EngineRuntime.state.value as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit
    val currentDetails get() = details?.takeIf { d -> fit()?.let { it.id == d.fitId && it.revision == d.revision } == true }
    val available get() = !loading && !editing && currentDetails?.isStructure == true
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested?.first != fit.id) message = null
        requested = next; details = null; loading = true; error = null
        val token = ++generation
        EngineRuntime.systemSecurityDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "System security could not be verified. Retry, or restart if the engine is unavailable."
                else if (value.fitId == next.first && value.revision == next.second) details = value
                else error = "The fit changed while loading system security. Reload its current values."
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun canSet(before: SystemSecurityDetails, choice: SystemSecurityChoice) = available && before === currentDetails &&
        before.choices.any { it === choice } && before.system != choice.id
    fun set(context: Context, before: SystemSecurityDetails, choice: SystemSecurityChoice) {
        if (!canSet(before, choice)) return
        editing = true; error = null; message = null
        EngineRuntime.request(context, BridgeOperation.SetSystemSecurity(before.fitId, choice.id),
            mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (fit()?.id == before.fitId) {
                val editError = if (failure != null) "The engine could not confirm the security change. Restart the app before editing."
                    else if (!result.isSuccess) result.error?.message ?: "System security change was refused." else null
                if (editError == null) {
                    message = "${choice.label} saved. Undo is available."
                    fit()?.let { load(context, it, retry = true) }
                }
                error = editError
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun SystemSecurityEditor(model: SystemSecurityModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = state as? EngineState.Ready
    val fit = ready?.fit
    BackHandler { onBack() }
    Text("Structure system security", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("system-security-back")) { Text("Back to structure services") }
    if (fit == null) { Text("Open a structure fit to choose its system security.", Modifier.testTag("system-security-no-fit")); return }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    if (ready?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) {
        Text("The fitting engine is unavailable. Restart the app before editing.", Modifier.testTag("system-security-unavailable")); return
    }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    if (model.loading) Text("Loading system security…", Modifier.testTag("system-security-loading"))
    if (model.editing) Text("Saving system security…", Modifier.testTag("system-security-saving"))
    model.error?.let { Text(it, Modifier.testTag("system-security-error"), color = MaterialTheme.colorScheme.error) }
    model.message?.let { Text(it, Modifier.testTag("system-security-saved")) }
    TextButton(onClick = { model.load(context, fit, true) }, enabled = !model.loading && !model.editing,
        modifier = Modifier.testTag("system-security-refresh")) { Text("Reload current security") }
    val details = model.currentDetails ?: return
    if (!details.isStructure) {
        Text("System security controls are available only for structures.", Modifier.testTag("system-security-not-structure")); return
    }
    Text("System security changes applicable structure combat-rig bonuses. Values below are calculated by the fitting engine.")
    Text("Current: ${details.choices.single { it.id == details.system }.label}", Modifier.testTag("system-security-current"))
    details.choices.forEach { choice ->
        Button(onClick = { model.set(context, details, choice) }, enabled = model.canSet(details, choice),
            modifier = Modifier.fillMaxWidth().testTag("system-security-${choice.id.name}")) { Text(choice.label) }
    }
    for ((key, label) in listOf("scan_resolution" to "Scan resolution", "max_target_range" to "Maximum targeting range")) {
        fit.stats[key]?.let { Text("$label: ${formatStat(it)}", Modifier.testTag("system-security-$key")) }
    }
}
