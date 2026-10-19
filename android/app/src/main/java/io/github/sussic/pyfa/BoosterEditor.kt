package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

data class BoosterReplacement(val options: BoosterAddOptions, val itemName: String, val fitName: String)

class BoosterEditorModel : ViewModel() {
    var details by mutableStateOf<BoosterDetails?>(null); private set
    var loading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var selected by mutableStateOf<Set<String>>(emptySet()); private set
    var expanded by mutableStateOf<Set<String>>(emptySet()); private set
    var page by mutableStateOf(0); private set
    var addOptions by mutableStateOf<BoosterAddOptions?>(null); private set
    var addLoading by mutableStateOf(false); private set
    var addError by mutableStateOf<String?>(null); private set
    var pendingReplacement by mutableStateOf<BoosterReplacement?>(null); private set
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    private var addRequested: Triple<String, Long, Int>? = null
    private var addGeneration = 0
    private fun fit(): FitSnapshot? = (EngineRuntime.state.value as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit
    val currentDetails get() = details?.takeIf { d -> fit()?.let { it.id == d.fitId && it.revision == d.revision } == true }
    val available get() = !loading && !editing && currentDetails?.isStructure == false
    fun currentAdd(itemId: Int): BoosterAddOptions? = addOptions?.takeIf { options ->
        options.itemId == itemId && fit()?.let { it.id == options.fitId && it.revision == options.revision } == true
    }
    val replacementCurrent get() = pendingReplacement?.options?.let { options ->
        !editing && fit()?.let { it.id == options.fitId && it.revision == options.revision } == true
    } == true
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested?.first != fit.id) { selected = emptySet(); expanded = emptySet(); page = 0; message = null }
        requested = next; details = null; loading = true; error = null
        val token = ++generation
        EngineRuntime.boosterDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Booster details could not be verified. Retry, or restart if the engine is unavailable."
                else if (value.fitId == next.first && value.revision == next.second) {
                    details = value
                    val keys = value.boosters.map { it.objectKey }.toSet()
                    selected = selected.intersect(keys); expanded = expanded.intersect(keys)
                    page = page.coerceAtMost((value.boosters.size - 1).coerceAtLeast(0) / 25)
                } else error = "The fit changed while loading boosters. Reload its current values."
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun loadAddOptions(context: Context, fit: FitSnapshot, itemId: Int, retry: Boolean = false) {
        val next = Triple(fit.id, fit.revision, itemId)
        if (!retry && addRequested == next) return
        addRequested = next; addOptions = null; addLoading = true; addError = null
        val token = ++addGeneration
        EngineRuntime.boosterAddOptions(context, fit.id, itemId).whenCompleteAsync({ value, failure ->
            if (token == addGeneration) {
                addLoading = false
                if (failure != null) addError = "Booster slot could not be checked. Retry before adding or replacing."
                else if (value.fitId == next.first && value.revision == next.second && value.itemId == next.third) addOptions = value
                else addError = "The fit changed while checking this booster. Reload its slot."
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun add(context: Context, item: EquipmentItem, onSaved: () -> Unit) {
        val options = currentAdd(item.id) ?: return
        if (editing || addLoading || !options.isBooster || options.isStructure || options.alreadyFitted) return
        if (options.occupant != null) {
            pendingReplacement = BoosterReplacement(options, item.name, fit()!!.name)
        } else submit(context, options.fitId, options.revision, BridgeOperation.FitBooster(options.fitId, item.id), onSaved)
    }
    fun cancelReplacement() { if (!editing) pendingReplacement = null }
    fun confirmReplacement(context: Context, onSaved: () -> Unit) {
        val pending = pendingReplacement ?: return
        if (!replacementCurrent) { addError = "The fit changed. Cancel this confirmation and check the slot again."; return }
        val options = pending.options
        if (!options.isBooster || options.isStructure || options.alreadyFitted || options.occupant == null) return
        pendingReplacement = null
        // The exact revision shown in the confirmation guards the original occupant.
        submit(context, options.fitId, options.revision, BridgeOperation.FitBooster(options.fitId, options.itemId), onSaved)
    }
    fun select(key: String, checked: Boolean) {
        val d = currentDetails ?: return
        if (!available || d.boosters.none { it.objectKey == key }) return
        if (checked && key !in selected && selected.size >= 1024) { error = "Select at most 1024 boosters per edit."; return }
        selected = if (checked) selected + key else selected - key
    }
    fun selectAll() {
        if (!available) return
        val rows = currentDetails!!.boosters
        if (rows.size > 1024) { error = "Select at most 1024 boosters per edit."; return }
        selected = rows.map { it.objectKey }.toSet()
    }
    fun clearSelection() { if (available) selected = emptySet() }
    fun expand(key: String) { expanded = if (key in expanded) expanded - key else expanded + key }
    fun showPage(value: Int) {
        if (available) page = value.coerceIn(0, (currentDetails!!.boosters.size - 1).coerceAtLeast(0) / 25)
    }
    fun toggle(context: Context, row: BoosterRow) {
        val d = currentDetails ?: return
        if (!available || row !in d.boosters) return
        submit(context, d.fitId, d.revision, BridgeOperation.ToggleBoosters(d.fitId, row.index,
            d.boosters.filter { it.objectKey in selected }.map { it.index }))
    }
    fun sideEffect(context: Context, row: BoosterRow, effect: BoosterSideEffect) {
        val d = currentDetails ?: return
        if (!available || row !in d.boosters || effect !in row.sideEffects) return
        submit(context, d.fitId, d.revision, BridgeOperation.SetBoosterSideEffect(d.fitId, row.index, effect.effectId, !effect.active))
    }
    fun remove(context: Context, rows: List<BoosterRow>) {
        val d = currentDetails ?: return
        if (!available || rows.isEmpty() || rows.any { it !in d.boosters }) return
        submit(context, d.fitId, d.revision, BridgeOperation.RemoveBoosters(d.fitId, rows.map { it.index }))
    }
    fun variation(context: Context, row: BoosterRow, choice: BoosterVariation) {
        val d = currentDetails ?: return
        if (!available || row !in d.boosters || choice !in row.variations || !choice.enabled) return
        submit(context, d.fitId, d.revision, BridgeOperation.ChangeBoosterVariation(d.fitId, row.index, choice.id))
    }
    private fun submit(context: Context, fitId: String, revision: Long, operation: BridgeOperation, onSaved: () -> Unit = {}) {
        if (editing || fit()?.let { it.id == fitId && it.revision == revision } != true) return
        editing = true; error = null; addError = null; message = null
        EngineRuntime.request(context, operation, mapOf(fitId to revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (fit()?.id == fitId) {
                if (failure != null) error = "The engine could not confirm the booster edit. Restart before making more changes."
                else if (!result.isSuccess) error = result.error?.message ?: "The booster edit was rejected."
                else {
                    message = "Booster edit saved. Undo is available."
                    fit()?.let { load(context, it, retry = true) }; onSaved()
                }
                addError = error
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun BoosterReplacementDialog(model: BoosterEditorModel, onSaved: () -> Unit) {
    val pending = model.pendingReplacement ?: return
    val context = LocalContext.current
    // Observe engine publication so a background edit immediately disables stale confirmation.
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val current = engine is EngineState.Ready && model.replacementCurrent
    AlertDialog(onDismissRequest = model::cancelReplacement,
        title = { Text("Replace booster in slot ${pending.options.slot}?") },
        text = { Column {
            Text("${pending.fitName}: replace ${pending.options.occupant!!.name} with ${pending.itemName}.")
            Text("The new booster uses its default active state and side effects. This is one undoable edit.")
            if (!current) Text("The fit or engine changed. Cancel and check the current slot before replacing.",
                color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("booster-replace-stale"))
        } },
        confirmButton = { TextButton(onClick = { model.confirmReplacement(context, onSaved) }, enabled = current,
            modifier = Modifier.testTag("booster-replace-confirm")) { Text("Replace booster") } },
        dismissButton = { TextButton(onClick = model::cancelReplacement, modifier = Modifier.testTag("booster-replace-cancel")) { Text("Cancel") } },
        modifier = Modifier.testTag("booster-replace-dialog"))
}

@Composable
internal fun BoosterEquipmentActions(model: BoosterEditorModel, item: EquipmentItem, onSaved: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = engine as? EngineState.Ready ?: return
    if (ready.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) {
        Text("Restart the app before adding or replacing a booster.", Modifier.testTag("equipment-booster-unavailable")); return
    }
    if (model.editing) Text("Saving booster edit…", Modifier.testTag("equipment-booster-saving"))
    LaunchedEffect(ready.fit.id, ready.fit.revision, item.id) { model.loadAddOptions(context, ready.fit, item.id) }
    if (model.addLoading) Text("Checking booster slot…", Modifier.testTag("equipment-booster-loading"))
    model.addError?.let {
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("equipment-booster-error"))
        TextButton(onClick = { model.loadAddOptions(context, ready.fit, item.id, true) }, enabled = !model.editing && !model.addLoading,
            modifier = Modifier.testTag("equipment-booster-retry")) { Text("Check booster slot again") }
    }
    val options = model.currentAdd(item.id) ?: return
    if (!options.isBooster) return
    Text("Booster slot ${options.slot}", Modifier.testTag("equipment-booster-slot"))
    if (options.isStructure) Text("Boosters are unavailable for structures.", Modifier.testTag("equipment-booster-structure"))
    else if (options.alreadyFitted) Text("This booster is already fitted.", Modifier.testTag("equipment-booster-already-fitted"))
    else {
        options.occupant?.let { Text("Slot occupied by ${it.name}. Replacement requires confirmation.") }
        Button(onClick = { model.add(context, item, onSaved) }, enabled = !model.editing && !model.addLoading,
            modifier = Modifier.testTag("equipment-fit-booster")) {
            Text(if (options.occupant == null) "Add booster" else "Review booster replacement")
        }
    }
}

@Composable
internal fun BoosterEditor(model: BoosterEditorModel, onBrowse: () -> Unit, onBack: () -> Unit, onInspect: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = engine as? EngineState.Ready
    val fit = ready?.fit
    BackHandler { onBack() }
    Text("Boosters", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("boosters-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to manage boosters."); return }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    if (ready?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) {
        Text("Restart the app to recover the fitting engine.", Modifier.testTag("boosters-unavailable")); return
    }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("boosters-error")) }
    model.message?.let { Text(it, Modifier.testTag("boosters-saved")) }
    if (model.loading) Text("Loading boosters…", Modifier.testTag("boosters-loading"))
    if (model.editing) Text("Saving booster edit…", Modifier.testTag("boosters-saving"))
    val d = model.currentDetails
    if (d == null) {
        if (!model.loading) Button(onClick = { model.load(context, fit, true) }, enabled = !model.editing,
            modifier = Modifier.testTag("boosters-retry")) { Text("Reload boosters") }
        return
    }
    if (d.isStructure) Text("Boosters are unavailable for structures.", Modifier.testTag("boosters-structure"))
    TextButton(onClick = onBrowse, enabled = !d.isStructure && !model.editing,
        modifier = Modifier.testTag("boosters-browse")) { Text("Browse boosters to add") }
    TextButton(onClick = onInspect, modifier = Modifier.testTag("boosters-inspect")) { Text("Fitted item attributes and affectors") }
    Text("Booster state applies to this and selected rows. Each side-effect switch changes only its own booster.")
    val available = model.available
    val selected = d.boosters.filter { it.objectKey in model.selected }
    Row {
        TextButton(onClick = model::selectAll, enabled = available, modifier = Modifier.testTag("boosters-select-all")) { Text("Select all") }
        TextButton(onClick = model::clearSelection, enabled = available, modifier = Modifier.testTag("boosters-clear-selection")) { Text("Clear selection") }
    }
    selected.firstOrNull()?.let { main ->
        Button(onClick = { model.toggle(context, main) }, enabled = available,
            modifier = Modifier.testTag("boosters-toggle-selected")) { Text(if (main.active) "Deactivate selected" else "Activate selected") }
        TextButton(onClick = { model.remove(context, selected) }, enabled = available,
            modifier = Modifier.testTag("boosters-remove-selected")) { Text("Remove selected boosters") }
    }
    if (d.boosters.isEmpty()) Text("No boosters in this fit.", Modifier.testTag("boosters-empty"))
    val pages = ((d.boosters.size + 24) / 25).coerceAtLeast(1)
    if (pages > 1) {
        Text("Page ${model.page + 1} of $pages · ${selected.size} selected")
        Row {
            TextButton(onClick = { model.showPage(model.page - 1) }, enabled = available && model.page > 0) { Text("Previous boosters") }
            TextButton(onClick = { model.showPage(model.page + 1) }, enabled = available && model.page + 1 < pages) { Text("Next boosters") }
        }
    }
    d.boosters.drop(model.page * 25).take(25).forEach { row -> key(row.objectKey) {
        Card(Modifier.fillMaxWidth().testTag("booster-${row.index}")) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(Modifier.fillMaxWidth().toggleable(row.objectKey in model.selected, enabled = available, role = Role.Checkbox,
                    onValueChange = { model.select(row.objectKey, it) }).testTag("booster-${row.index}-select")) {
                    Checkbox(checked = row.objectKey in model.selected, onCheckedChange = null)
                    Text("Slot ${row.slot}: ${row.name}", style = MaterialTheme.typography.titleMedium)
                }
                Text(if (row.active) "Active" else "Inactive", Modifier.testTag("booster-${row.index}-state"))
                Text("Duration: ${row.durationText ?: "Unavailable"}", Modifier.testTag("booster-${row.index}-duration"))
                TextButton(onClick = { model.toggle(context, row) }, enabled = available,
                    modifier = Modifier.testTag("booster-${row.index}-toggle")) { Text(if (row.active) "Deactivate this + selected" else "Activate this + selected") }
                TextButton(onClick = { model.remove(context, listOf(row)) }, enabled = available,
                    modifier = Modifier.testTag("booster-${row.index}-remove")) { Text("Remove this booster") }
                Text("Implemented side effects", style = MaterialTheme.typography.titleSmall)
                if (row.sideEffects.isEmpty()) Text("No implemented side effects available.")
                row.sideEffects.forEach { effect ->
                    Row(Modifier.fillMaxWidth().toggleable(effect.active, enabled = available, role = Role.Checkbox,
                        onValueChange = { model.sideEffect(context, row, effect) }).testTag("booster-${row.index}-effect-${effect.effectId}")) {
                        Checkbox(checked = effect.active, onCheckedChange = null)
                        Text(effect.name)
                    }
                }
                if (row.variations.isNotEmpty()) {
                    TextButton(onClick = { model.expand(row.objectKey) }, modifier = Modifier.testTag("booster-${row.index}-variations")) { Text("Variations") }
                    if (row.objectKey in model.expanded) {
                        Text("Changes this booster only, preserving its active state and matching side effects.")
                        row.variations.forEach { choice ->
                            TextButton(onClick = { model.variation(context, row, choice) }, enabled = available && choice.enabled && choice.id != row.itemId,
                                modifier = Modifier.testTag("booster-${row.index}-variation-${choice.id}")) { Text(choice.name) }
                        }
                    }
                }
            }
        }
    } }
}
