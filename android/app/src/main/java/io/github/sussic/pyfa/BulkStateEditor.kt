package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

private fun ModuleState.label(): String = name.lowercase().replaceFirstChar { it.uppercase() }

class BulkStateEditorModel : ViewModel() {
    var options by mutableStateOf<BulkStateOptions?>(null)
    var selected by mutableStateOf<Set<Int>>(emptySet())
    var main by mutableStateOf<Int?>(null)
    var scope by mutableStateOf(BulkScope.SELECTED)
    var click by mutableStateOf(StateClick.CYCLE)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    var actualChanges by mutableStateOf<List<String>>(emptyList())
    private var requested: Pair<String, Long>? = null
    private var ownRevision: Pair<String, Long>? = null
    private var beforeStates: Map<Int, ModuleState>? = null
    private var generation = 0

    fun clearSelection() { selected = emptySet(); main = null }
    fun open() {
        ++generation; options = null; requested = null; ownRevision = null
        beforeStates = null; loading = false; editing = false
        clearSelection(); scope = BulkScope.SELECTED; click = StateClick.CYCLE
        error = null; message = null; actualChanges = emptyList()
    }
    fun toggle(index: Int) {
        selected = if (index in selected) selected - index else selected + index
        if (main !in selected) main = selected.minOrNull()
        actualChanges = emptyList()
    }
    fun reference(index: Int) { selected = selected + index; main = index; actualChanges = emptyList() }
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        val previous = options
        if (previous != null && (previous.fitId != fit.id || previous.revision != fit.revision && ownRevision != next)) {
            clearSelection(); actualChanges = emptyList(); beforeStates = null
            message = if (previous.fitId == fit.id) "The fit changed. Select modules again." else null
        }
        requested = next
        val token = ++generation
        loading = true
        EngineRuntime.bulkStateOptions(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) { options = null; error = "Bulk states could not be loaded. Try again." }
                else {
                    if (selected.any { value.modules.getOrNull(it)?.editable != true ||
                            previous?.modules?.getOrNull(it)?.itemId != value.modules[it].itemId }) clearSelection()
                    options = value
                    beforeStates?.let { before ->
                        actualChanges = value.modules.mapNotNull { row ->
                            val was = before[row.index]
                            if (was != null && row.state != null && was != row.state)
                                "${row.index + 1} · ${was.label()} → ${row.state.label()}" else null
                        }
                        beforeStates = null
                    }
                    if (ownRevision == next) ownRevision = null
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun apply(context: Context) {
        val before = options ?: return
        val reference = main ?: return
        if (loading || editing || selected.isEmpty()) return
        editing = true; error = null; message = null; actualChanges = emptyList()
        beforeStates = before.modules.mapNotNull { row -> row.state?.let { row.index to it } }.toMap()
        ownRevision = before.fitId to before.revision + 1
        EngineRuntime.request(context, BridgeOperation.SetBulkStates(before.fitId, reference, selected.sorted(), scope, click),
            mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (failure != null || !result.isSuccess) { ownRevision = null; beforeStates = null }
            if (requested?.first == before.fitId) {
                if (failure != null) error = "The fitting engine could not confirm the edit. Restart the app."
                else if (!result.isSuccess) error = result.error?.message
                else message = "Module states saved. Actual states after fit-wide checks:"
                EngineRuntime.library.value.find { it.id == before.fitId }?.let { load(context, it, retry = true) }
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun BulkStateEditor(model: BulkStateEditorModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Bulk module states", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("bulk-states-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to change module states together."); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text(fit.name, style = MaterialTheme.typography.titleLarge)
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("bulk-states-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("bulk-states-saved")) }
    if (model.loading) Text("Loading state choices…")
    if (model.editing) Text("Saving fit…")
    val options = model.options?.takeIf { it.fitId == fit.id } ?: run {
        if (!model.loading) Button(onClick = { model.load(context, fit, retry = true) }) { Text("Retry") }
        return
    }
    val enabled = !model.loading && !model.editing && options.revision == fit.revision &&
        (state as? EngineState.Ready)?.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
    Text("${model.selected.size} selected", modifier = Modifier.testTag("bulk-states-selection-count"))
    Text("Select modules and a reference. Its state determines the request; each other module uses its own supported fallback.")
    Row {
        TextButton(onClick = {
            model.selected = options.modules.filter { it.editable }.map { it.index }.toSet()
            model.main = model.selected.minOrNull()
        }, enabled = enabled, modifier = Modifier.testTag("bulk-states-select-all")) { Text("Select all") }
        TextButton(onClick = { model.clearSelection() }, enabled = enabled,
            modifier = Modifier.testTag("bulk-states-clear")) { Text("Clear") }
    }
    if (options.modules.none { it.editable }) Text("No editable fitted modules.", modifier = Modifier.testTag("bulk-states-empty"))
    for (module in options.modules.filter { it.editable }) Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Row {
                Checkbox(checked = module.index in model.selected, onCheckedChange = { model.toggle(module.index) },
                    enabled = enabled, modifier = Modifier.testTag("bulk-states-select-${module.index}"))
                Text("${module.index + 1} · ${fit.modules[module.index].name}")
            }
            Text(module.state?.label() ?: "Unavailable")
            TextButton(onClick = { model.reference(module.index) }, enabled = enabled,
                modifier = Modifier.testTag("bulk-states-reference-${module.index}")) {
                Text(if (model.main == module.index) "Reference module ✓" else "Use as reference")
            }
        }
    }
    val main = model.main?.let { options.modules.getOrNull(it) } ?: return
    Text("Reference: ${fit.modules[main.index].name}", modifier = Modifier.testTag("bulk-states-reference"))
    for ((scope, label) in listOf(BulkScope.SELECTED to "Selection only", BulkScope.SIMILAR to "All similar modules"))
        TextButton(onClick = { model.scope = scope; model.actualChanges = emptyList() }, enabled = enabled,
            modifier = Modifier.testTag("bulk-states-scope-${scope.name}")) {
            Text(label + if (model.scope == scope) " ✓" else "")
        }
    for ((click, label) in listOf(StateClick.CYCLE to "Cycle state", StateClick.OVERHEAT to "Overheat where supported",
        StateClick.OFFLINE to "Take offline")) TextButton(onClick = { model.click = click; model.actualChanges = emptyList() },
        enabled = enabled, modifier = Modifier.testTag("bulk-states-click-${click.name}")) {
        Text(label + if (model.click == click) " ✓" else "")
    }
    val requested = main.clickStates[model.click] ?: return
    val candidates = if (model.scope == BulkScope.SIMILAR) main.similarCandidates else model.selected.sorted()
    val targets = candidates.associateWith { index ->
        if (index == main.index) requested else options.modules[index].supportedStates.getValue(requested)
    }
    val changed = targets.filter { (index, next) -> options.modules[index].state != next }
    Card(Modifier.fillMaxWidth().testTag("bulk-states-preview")) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Reference requests ${requested.label()}")
            Text("${changed.size} modules request a change", modifier = Modifier.testTag("bulk-states-change-count"))
            for (index in (model.selected + candidates).sorted()) {
                val row = options.modules[index]
                val outcome = when {
                    index !in candidates -> "Skipped · outside scope"
                    row.state == targets[index] -> "Already ${row.state?.label()}"
                    else -> "${row.state?.label()} → ${targets[index]?.label()}"
                }
                Text("${index + 1} · ${fit.modules[index].name}: $outcome",
                    modifier = Modifier.testTag("bulk-states-preview-$index"))
            }
            Text("Fit-wide restrictions may adjust other states after saving.", style = MaterialTheme.typography.bodySmall)
            Button(onClick = { model.apply(context) }, enabled = enabled && changed.isNotEmpty(),
                modifier = Modifier.testTag("bulk-states-apply")) { Text("Change ${changed.size} modules") }
        }
    }
    if (model.actualChanges.isNotEmpty()) Card(Modifier.fillMaxWidth().testTag("bulk-states-actual")) {
        Column(Modifier.padding(16.dp)) {
            for (change in model.actualChanges) Text(change)
        }
    }
}
