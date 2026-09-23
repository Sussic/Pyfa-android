package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

class RackEditorModel : ViewModel() {
    var options by mutableStateOf<RackOptions?>(null)
    var rack by mutableStateOf(ModuleSlot.HIGH)
    var source by mutableStateOf<Int?>(null)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    private var requested: Pair<String, Long>? = null
    private var generation = 0

    fun open(fitId: String?, position: Int?) {
        ++generation; requested = null; loading = false
        if (options?.fitId != fitId) { options = null; rack = ModuleSlot.HIGH }
        source = position; error = null; message = null
    }

    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested != null && requested != next) source = null
        if (requested?.first != null && requested?.first != fit.id) {
            options = null; error = null; message = null
        }
        requested = next
        val token = ++generation
        loading = true
        EngineRuntime.rackOptions(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) { options = null; error = "Rack details could not be loaded. Try again." }
                else {
                    options = value
                    val current = value.modules.find { it.index == source && it.id != null && it.slot.editable }
                    source = current?.index
                    if (current != null) rack = current.slot
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun move(context: Context, destination: Int) {
        val before = options ?: return
        val selected = source ?: return
        if (loading || editing || selected == destination) return
        editing = true; message = null; error = null
        EngineRuntime.request(context, BridgeOperation.SwapModules(before.fitId, selected, destination),
            mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (requested?.first == before.fitId) {
                if (failure != null) error = "The fitting engine could not confirm the edit. Restart the app."
                else if (!result.isSuccess) error = result.error?.message
                else { source = null; message = "Rack order saved." }
                EngineRuntime.library.value.find { it.id == before.fitId }?.let { load(context, it, retry = true) }
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun RackEditor(model: RackEditorModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    fun back() { if (model.source != null) model.source = null else onBack() }
    BackHandler { back() }
    Text("Arrange rack", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { back() }, modifier = Modifier.testTag("rack-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to arrange its modules."); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text(fit.name, style = MaterialTheme.typography.titleLarge)
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("rack-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("rack-saved")) }
    if (model.loading) Text("Loading rack…")
    if (model.editing) Text("Saving rack…")
    val options = model.options?.takeIf { it.fitId == fit.id } ?: run {
        if (!model.loading) Button(onClick = { model.load(context, fit, retry = true) }) { Text("Retry") }
        return
    }
    val enabled = !model.loading && !model.editing && options.revision == fit.revision &&
        (state as? EngineState.Ready)?.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
    for (row in ModuleSlot.entries.filter { it.editable }.chunked(3)) Row {
        for (slot in row) TextButton(onClick = { model.rack = slot; model.source = null }, enabled = enabled,
            modifier = Modifier.weight(1f).testTag("rack-slot-${slot.name}")) {
            Text(slot.label + if (slot == model.rack) " ✓" else "")
        }
    }
    val modules = options.modules.filter { it.slot == model.rack }
    val selected = modules.find { it.index == model.source }
    Text("Move a module to an empty slot, or swap it with another module in this rack. States and charges stay with their modules.")
    Text("Heat shows the desktop estimate of time until burnout for overheated modules.", style = MaterialTheme.typography.bodySmall)
    val action = remember { BringIntoViewRequester() }
    LaunchedEffect(model.source) { if (model.source != null) action.bringIntoView() }
    Column(Modifier.bringIntoViewRequester(action).testTag("rack-selection")) {
        Text(if (selected == null) "Choose a fitted module." else "Moving ${selected.name}. Choose a destination.")
        if (selected != null) TextButton(onClick = { model.source = null }, enabled = enabled,
            modifier = Modifier.testTag("rack-cancel")) { Text("Cancel move") }
    }
    if (modules.none { it.id != null }) Text("No fitted modules in this rack.", modifier = Modifier.testTag("rack-empty"))
    RackRows(modules, selected?.index, enabled, onSelect = { model.source = it }, onMove = { model.move(context, it) })
}

@Composable
private fun RackRows(modules: List<RackModule>, source: Int?, enabled: Boolean,
    onSelect: (Int) -> Unit, onMove: (Int) -> Unit) {
    for ((ordinal, module) in modules.withIndex()) key(module.index) {
        Card(Modifier.fillMaxWidth().testTag("rack-module-${module.index}")) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("${module.slot.label} ${ordinal + 1} · ${module.name ?: "Empty slot"}", style = MaterialTheme.typography.titleMedium)
                if (module.id != null) {
                    Text("${module.state.name.lowercase().replaceFirstChar { it.uppercase() }} · Charge: ${module.charge ?: "Empty"}")
                    module.heat?.let {
                        Text("Estimated burnout: ${formatStat(it.seconds)} · ${formatStat(it.cycles)}",
                            modifier = Modifier.testTag("rack-heat-${module.index}"))
                    }
                }
                if (source == null && module.id != null) TextButton(onClick = { onSelect(module.index) }, enabled = enabled,
                    modifier = Modifier.testTag("rack-select-${module.index}")) { Text("Move or swap") }
                else if (source != null) TextButton(onClick = { onMove(module.index) }, enabled = enabled && module.index != source,
                    modifier = Modifier.testTag("rack-move-${module.index}")) {
                    Text(if (module.index == source) "Selected module" else if (module.id == null) "Move here" else "Swap here")
                }
            }
        }
    }
}
