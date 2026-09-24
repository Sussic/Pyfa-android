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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

class BulkChargeEditorModel : ViewModel() {
    var options by mutableStateOf<BulkChargeOptions?>(null)
    var selected by mutableStateOf<Set<Int>>(emptySet())
    var main by mutableStateOf<Int?>(null)
    var scope by mutableStateOf(BulkScope.SELECTED)
    var choosing by mutableStateOf(false)
    var charge by mutableStateOf<Int?>(null)
    var choiceMade by mutableStateOf(false)
    var query by mutableStateOf("")
    var page by mutableStateOf(0)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    private var requested: Pair<String, Long>? = null
    private var ownRevision: Pair<String, Long>? = null
    private var generation = 0

    fun clearSelection() {
        selected = emptySet(); main = null; choosing = false; choiceMade = false; charge = null; query = ""; page = 0
    }
    fun open() {
        ++generation; options = null; requested = null; ownRevision = null; loading = false
        clearSelection(); scope = BulkScope.SELECTED; error = null; message = null
    }
    fun toggle(index: Int) {
        selected = if (index in selected) selected - index else selected + index
        if (main !in selected) main = selected.sorted().firstOrNull { options?.modules?.getOrNull(it)?.chargeIds?.isNotEmpty() == true }
        choiceMade = false
    }
    fun reference(index: Int) { selected = selected + index; main = index; choiceMade = false; charge = null; query = ""; page = 0 }
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        val previous = options
        if (previous != null && (previous.fitId != fit.id || previous.revision != fit.revision && ownRevision != next)) {
            clearSelection()
            message = if (previous.fitId == fit.id) "The fit changed. Select modules again." else null
        }
        requested = next
        val token = ++generation
        loading = true
        EngineRuntime.bulkChargeOptions(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) { options = null; error = "Bulk charges could not be loaded. Try again." }
                else {
                    if (selected.any { value.modules.getOrNull(it)?.itemId == null ||
                            previous?.modules?.getOrNull(it)?.itemId != value.modules[it].itemId }) clearSelection()
                    options = value
                    if (ownRevision == next) ownRevision = null
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun apply(context: Context) {
        val before = options ?: return
        val reference = main ?: return
        if (loading || editing || !choiceMade) return
        editing = true; error = null; message = null
        ownRevision = before.fitId to before.revision + 1
        EngineRuntime.request(context, BridgeOperation.SetBulkCharges(before.fitId, reference, selected.sorted(), scope, charge),
            mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (failure != null || !result.isSuccess) ownRevision = null
            if (requested?.first == before.fitId) {
                if (failure != null) error = "The fitting engine could not confirm the edit. Restart the app."
                else if (!result.isSuccess) error = result.error?.message
                else message = "Bulk charge change saved."
                EngineRuntime.library.value.find { it.id == before.fitId }?.let { load(context, it, retry = true) }
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun BulkChargeEditor(model: BulkChargeEditorModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    fun back() { if (model.choosing) model.choosing = false else onBack() }
    BackHandler { back() }
    Text("Bulk ammunition", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { back() }, modifier = Modifier.testTag("bulk-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to change charges together."); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text(fit.name, style = MaterialTheme.typography.titleLarge)
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("bulk-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("bulk-saved")) }
    if (model.loading) Text("Loading bulk choices…")
    if (model.editing) Text("Saving fit…")
    val options = model.options?.takeIf { it.fitId == fit.id } ?: run {
        if (!model.loading) Button(onClick = { model.load(context, fit, retry = true) }) { Text("Retry") }
        return
    }
    val enabled = !model.loading && !model.editing && options.revision == fit.revision &&
        (state as? EngineState.Ready)?.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
    val main = model.main?.let { options.modules.getOrNull(it) }
    Text("${model.selected.size} selected", modifier = Modifier.testTag("bulk-selection-count"))
    // Separate composition scopes keep the two lists stable through navigation.
    key(model.choosing) {
        if (!model.choosing) {
            Text("Select modules, then choose a reference module for its ammunition or scripts.")
            Row {
                TextButton(onClick = {
                    model.selected = options.modules.filter { it.itemId != null }.map { it.index }.toSet()
                    model.main = options.modules.firstOrNull { it.chargeIds.isNotEmpty() }?.index
                    model.choiceMade = false
                }, enabled = enabled, modifier = Modifier.testTag("bulk-select-all")) { Text("Select all") }
                TextButton(onClick = { model.clearSelection() }, enabled = enabled,
                    modifier = Modifier.testTag("bulk-clear")) { Text("Clear") }
            }
            Button(onClick = { model.choosing = true }, enabled = enabled && main != null && main.chargeIds.isNotEmpty(),
                modifier = Modifier.testTag("bulk-choose")) { Text("Choose charge and scope") }
            if (options.modules.none { it.itemId != null }) Text("No fitted modules.", modifier = Modifier.testTag("bulk-empty"))
            for (module in options.modules.filter { it.itemId != null }) Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp)) {
                    Row {
                        Checkbox(checked = module.index in model.selected, onCheckedChange = { model.toggle(module.index) },
                            enabled = enabled, modifier = Modifier.testTag("bulk-select-${module.index}"))
                        Text("${module.index + 1} · ${fit.modules[module.index].name}")
                    }
                    Text("${fit.modules[module.index].state?.name?.lowercase()?.replaceFirstChar { it.uppercase() } ?: "Unavailable"} · ${fit.modules[module.index].charge ?: "Empty"}")
                    if (module.chargeIds.isNotEmpty()) TextButton(onClick = { model.reference(module.index) }, enabled = enabled,
                        modifier = Modifier.testTag("bulk-reference-${module.index}")) {
                        Text(if (model.main == module.index) "Reference module ✓" else "Use as reference")
                    }
                }
            }
        } else if (main != null) {
            Text("Reference: ${fit.modules[main.index].name}", modifier = Modifier.testTag("bulk-reference"))
            for ((scope, label) in listOf(BulkScope.SELECTED to "Selection only", BulkScope.SIMILAR to "All similar modules"))
                TextButton(onClick = { model.scope = scope }, enabled = enabled, modifier = Modifier.testTag("bulk-scope-${scope.name}")) {
                    Text(label + if (model.scope == scope) " ✓" else "")
                }
            Text(if (model.scope == BulkScope.SIMILAR) "Includes related variants, even outside your selection. Incompatible charges are skipped."
                else "Uses the reference module’s charge group. Some selected modules may be skipped; check the preview.",
                style = MaterialTheme.typography.bodySmall)
            val candidates = if (model.scope == BulkScope.SIMILAR) main.similarCandidates else main.selectionCandidates.filter { it in model.selected }
            if (model.choiceMade) {
                val targets = candidates.filter { model.charge == null || model.charge in options.modules[it].chargeIds }
                val changed = targets.filter { options.modules[it].chargeId != model.charge }
                Card(Modifier.fillMaxWidth().testTag("bulk-preview")) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(model.charge?.let { id -> options.items.single { it.id == id }.name } ?: "Unload charges",
                            style = MaterialTheme.typography.titleMedium)
                        Text("${changed.size} modules will change", modifier = Modifier.testTag("bulk-change-count"))
                        for (index in (model.selected + candidates).sorted()) {
                            val action = when {
                                index in changed -> if (model.charge == null) "Will unload" else "Will load"
                                index in targets -> "Already set"
                                index !in candidates -> "Skipped · outside reference group"
                                else -> "Skipped · incompatible charge"
                            }
                            Text("${index + 1} · ${fit.modules[index].name}: $action", modifier = Modifier.testTag("bulk-preview-$index"))
                        }
                        Button(onClick = { focus.clearFocus(); model.apply(context) }, enabled = enabled && changed.isNotEmpty(),
                            modifier = Modifier.testTag("bulk-apply")) { Text(if (model.charge == null) "Unload from ${changed.size} modules" else "Load into ${changed.size} modules") }
                    }
                }
            }
            TextButton(onClick = { focus.clearFocus(); model.charge = null; model.choiceMade = true }, enabled = enabled,
                modifier = Modifier.testTag("bulk-unload")) { Text("Unload charges") }
            OutlinedTextField(value = model.query, onValueChange = { model.query = it; model.page = 0 },
                label = { Text("Find a charge") }, singleLine = true, modifier = Modifier.fillMaxWidth().testTag("bulk-search"))
            val rows = options.items.filter { it.id in main.chargeIds && it.name.contains(model.query.trim(), ignoreCase = true) }
                .sortedWith(compareBy<ChargeItem> { it.name.lowercase() }.thenBy { it.id })
            val pages = maxOf(1, (rows.size + 19) / 20); val page = model.page.coerceIn(0, pages - 1)
            Text("${rows.size} charges · Page ${page + 1} of $pages")
            if (rows.isEmpty()) Text("No charges match this filter.", modifier = Modifier.testTag("bulk-no-charges"))
            for (item in rows.drop(page * 20).take(20)) TextButton(onClick = { focus.clearFocus(); model.charge = item.id; model.choiceMade = true },
                enabled = enabled, modifier = Modifier.fillMaxWidth().testTag("bulk-charge-${item.id}")) { Text(item.name) }
            if (pages > 1) Row {
                TextButton(onClick = { focus.clearFocus(); model.page = page - 1 }, enabled = page > 0) { Text("Previous") }
                TextButton(onClick = { focus.clearFocus(); model.page = page + 1 }, enabled = page + 1 < pages) { Text("Next") }
            }
        }
    }
}
