package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

class ModuleSpoolModel : ViewModel() {
    var details by mutableStateOf<ModuleSpoolDetails?>(null); private set
    var loading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var expanded by mutableStateOf<Set<String>>(emptySet()); private set
    var page by mutableStateOf(0); private set
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    private fun fit() = (EngineRuntime.state.value as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit
    val currentDetails get() = details?.takeIf { d -> fit()?.let { it.id == d.fitId && it.revision == d.revision } == true }
    val available get() = !loading && !editing && currentDetails != null
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested?.first != fit.id) { expanded = emptySet(); page = 0; message = null }
        requested = next; details = null; loading = true; error = null
        val token = ++generation
        EngineRuntime.moduleSpoolDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Spool choices could not be verified. Retry, or restart if the engine is unavailable."
                else if (value.fitId == next.first && value.revision == next.second) {
                    details = value
                    expanded = expanded.intersect(value.modules.map { it.objectKey }.toSet())
                    page = page.coerceAtMost((value.modules.size - 1).coerceAtLeast(0) / 25)
                } else error = "The fit changed while loading spool choices. Reload its current values."
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun expand(key: String) { expanded = if (key in expanded) expanded - key else expanded + key }
    fun showPage(value: Int) {
        if (available) page = value.coerceIn(0, (currentDetails!!.modules.size - 1).coerceAtLeast(0) / 25)
    }
    fun set(context: Context, before: ModuleSpoolDetails, row: ModuleSpoolRow, cycles: Int?) {
        if (!available || before !== currentDetails || row !in before.modules || cycles != null && cycles !in row.choices) return
        if (cycles == row.overrideCycles) return
        editing = true; error = null; message = null
        EngineRuntime.request(context, BridgeOperation.SetModuleSpool(before.fitId, row.index, cycles),
            mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (requested?.first == before.fitId) {
                val editError = if (failure != null) "The engine could not confirm the spool change. Restart the app before editing."
                    else if (!result.isSuccess) result.error?.message ?: "Spool change was refused." else null
                if (editError == null) message = if (cycles == null) "Module reset to the global spool default." else "Explicit spool cycles saved."
                // Reload only this fit. A completion cannot redirect navigation to a different selected fit.
                fit()?.takeIf { it.id == before.fitId }?.let { load(context, it, retry = true) }
                error = editError
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun ModuleSpoolEditor(model: ModuleSpoolModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Module spool cycles", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("spool-back")) { Text("Back to modules") }
    if (fit == null) { Text("Open a fit to set its module spool cycles.", Modifier.testTag("spool-no-fit")); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    Text("Choose a cycle count to save an override for one local module. Reset follows the global default. Explicit zero means no spool, even if the default changes.")
    if ((state as? EngineState.Ready)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE)
        Text("The fitting engine is unavailable. Restart the app before editing.", Modifier.testTag("spool-unavailable"))
    if (model.loading) Text("Loading spool choices…", Modifier.testTag("spool-loading"))
    if (model.editing) Text("Saving spool cycles…", Modifier.testTag("spool-saving"))
    model.error?.let { Text(it, Modifier.testTag("spool-error"), color = MaterialTheme.colorScheme.error) }
    model.message?.let { Text(it, Modifier.testTag("spool-saved")) }
    if (!model.loading) TextButton(onClick = { model.load(context, fit, true) }, enabled = !model.editing,
        modifier = Modifier.testTag("spool-refresh")) { Text("Reload choices") }
    val details = model.currentDetails ?: return
    if (details.modules.isEmpty()) Text("No local modules with spool-cycle controls are fitted.", Modifier.testTag("spool-empty"))
    for (row in details.modules.drop(model.page * 25).take(25)) key(row.objectKey) {
        Card(Modifier.fillMaxWidth().testTag("spool-module-${row.index}")) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("${row.index + 1} · ${row.name}", style = MaterialTheme.typography.titleMedium)
                Text(if (row.overrideCycles == null) "Using global default" else "Explicit override: ${row.overrideCycles} cycles",
                    Modifier.testTag("spool-mode-${row.index}"))
                Text("Current: ${row.currentCycles} cycles · ${row.currentSeconds} s", Modifier.testTag("spool-current-${row.index}"))
                Text("Global default: ${row.defaultCycles} cycles · ${row.defaultSeconds} s")
                if (row.overrideCycles != null && row.overrideCycles != row.currentCycles)
                    Text("EOS currently applies ${row.currentCycles} cycles; the requested override remains ${row.overrideCycles}.")
                TextButton(onClick = { model.expand(row.objectKey) }, modifier = Modifier.testTag("spool-choices-${row.index}")) {
                    Text(if (row.objectKey in model.expanded) "Hide cycle choices" else "Choose cycles")
                }
                if (row.objectKey in model.expanded) {
                    Text("Source range: ${row.minimumCycles}–${row.maximumCycles} cycles · ${row.minimumSeconds}–${row.maximumSeconds} s")
                    for (choices in row.choices.chunked(3)) Row(Modifier.fillMaxWidth()) {
                        for (cycles in choices) TextButton(onClick = { model.set(context, details, row, cycles) },
                            enabled = model.available && cycles != row.overrideCycles,
                            modifier = Modifier.weight(1f).testTag("spool-choice-${row.index}-$cycles")) {
                            Text("$cycles cycles" + when {
                                row.overrideCycles != null && cycles == row.currentCycles -> " · applied"
                                row.overrideCycles == null && cycles == row.defaultCycles -> " · default"
                                else -> ""
                            })
                        }
                    }
                }
                TextButton(onClick = { model.set(context, details, row, null) }, enabled = model.available && row.overrideCycles != null,
                    modifier = Modifier.testTag("spool-reset-${row.index}")) { Text("Reset to global default") }
            }
        }
    }
    if (details.modules.size > 25) Row {
        TextButton(onClick = { model.showPage(model.page - 1) }, enabled = model.available && model.page > 0,
            modifier = Modifier.testTag("spool-previous")) { Text("Previous modules") }
        Text("Page ${model.page + 1} of ${(details.modules.size + 24) / 25}")
        TextButton(onClick = { model.showPage(model.page + 1) }, enabled = model.available && (model.page + 1) * 25 < details.modules.size,
            modifier = Modifier.testTag("spool-next")) { Text("Next modules") }
    }
}
