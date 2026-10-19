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
import org.json.JSONObject

data class ImplantReplacement(val options: ImplantAddOptions, val itemName: String, val fitName: String)

class ImplantEditorModel : ViewModel() {
    var details by mutableStateOf<ImplantDetails?>(null); private set
    var loading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var selected by mutableStateOf<Set<String>>(emptySet()); private set
    var page by mutableStateOf(0); private set
    var addOptions by mutableStateOf<ImplantAddOptions?>(null); private set
    var addLoading by mutableStateOf(false); private set
    var addError by mutableStateOf<String?>(null); private set
    var pendingReplacement by mutableStateOf<ImplantReplacement?>(null); private set
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    private var addRequested: Triple<String, Long, Int>? = null
    private var addGeneration = 0
    private fun fit(): FitSnapshot? = (EngineRuntime.state.value as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit
    val currentDetails get() = details?.takeIf { d -> fit()?.let { it.id == d.fitId && it.revision == d.revision } == true }
    val available get() = !loading && !editing && currentDetails?.editable == true
    fun currentAdd(itemId: Int): ImplantAddOptions? = addOptions?.takeIf { options ->
        options.itemId == itemId && fit()?.let { it.id == options.fitId && it.revision == options.revision } == true
    }
    val replacementCurrent get() = pendingReplacement?.options?.let { options ->
        !editing && options.editable && fit()?.let { it.id == options.fitId && it.revision == options.revision } == true
    } == true
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested?.first != fit.id) { selected = emptySet(); page = 0; message = null }
        requested = next; details = null; loading = true; error = null
        val token = ++generation
        EngineRuntime.implantDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Implant details could not be verified. Retry, or restart if the engine is unavailable."
                else if (value.fitId == next.first && value.revision == next.second) {
                    details = value
                    val keys = value.implants.map { it.objectKey }.toSet()
                    selected = selected.intersect(keys)
                    page = page.coerceAtMost((value.implants.size - 1).coerceAtLeast(0) / 25)
                } else error = "The fit changed while loading implants. Reload its current values."
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun loadAddOptions(context: Context, fit: FitSnapshot, itemId: Int, retry: Boolean = false) {
        val next = Triple(fit.id, fit.revision, itemId)
        if (!retry && addRequested == next) return
        addRequested = next; addOptions = null; addLoading = true; addError = null
        val token = ++addGeneration
        EngineRuntime.implantAddOptions(context, fit.id, itemId).whenCompleteAsync({ value, failure ->
            if (token == addGeneration) {
                addLoading = false
                if (failure != null) addError = "Implant slot could not be checked. Retry before adding or replacing."
                else if (value.fitId == next.first && value.revision == next.second && value.itemId == next.third) addOptions = value
                else addError = "The fit changed while checking this implant. Reload its slot."
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun add(context: Context, item: EquipmentItem, onSaved: () -> Unit) {
        val options = currentAdd(item.id) ?: return
        if (editing || addLoading || !options.canAdd) return
        if (options.occupant != null && !options.sourceOnly) {
            pendingReplacement = ImplantReplacement(options, item.name, fit()!!.name)
        } else submit(context, options.fitId, options.revision, BridgeOperation.FitImplant(options.fitId, item.id), onSaved)
    }
    fun cancelReplacement() { if (!editing) pendingReplacement = null }
    fun confirmReplacement(context: Context, onSaved: () -> Unit) {
        val pending = pendingReplacement ?: return
        if (!replacementCurrent) { addError = "The fit changed. Cancel this confirmation and check the slot again."; return }
        val options = pending.options
        if (!options.isImplant || !options.editable || options.alreadyFitted || options.occupant == null) return
        pendingReplacement = null
        // The exact revision shown in the confirmation guards the original occupant.
        submit(context, options.fitId, options.revision, BridgeOperation.FitImplant(options.fitId, options.itemId), onSaved)
    }
    fun setSource(context: Context, before: OfflineFeatureState, source: ImplantLocation) {
        val currentFit = fit() ?: return
        val d = currentDetails ?: return
        val binding = before.bindings[currentFit.id] ?: return
        if (editing || loading || d.isStructure || before !== EngineRuntime.offlineFeatures.value || binding.fitRevision != currentFit.revision) return
        editing = true; error = null; message = null
        val capturedSession = before.context.sessionId
        EngineRuntime.offlineFeatureRequest(context, before.context, "set_implant_source", JSONObject().put("fit_id", currentFit.id)
            .put("fit_revision", currentFit.revision).put("source", source.name), currentFit.id).whenCompleteAsync({ response, failure ->
            editing = false
            if (fit()?.id == currentFit.id && EngineRuntime.offlineFeatures.value?.context?.sessionId == capturedSession) {
                if (failure != null || response?.reopenRequired == true) error = "The source change could not be confirmed. Restart before making more changes."
                else if (!response.ok) error = response.error?.message ?: "The source change was rejected."
                else {
                    message = if (response.committed == true) "Implant source saved. Both collections are kept; Undo is available." else "Already selected. Both collections are unchanged."
                    fit()?.let { load(context, it, retry = true) }
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun select(key: String, checked: Boolean) {
        val d = currentDetails ?: return
        if (!available || d.implants.none { it.objectKey == key }) return
        if (checked && key !in selected && selected.size >= 1024) { error = "Select at most 1024 implants per edit."; return }
        selected = if (checked) selected + key else selected - key
    }
    fun selectAll() {
        if (!available) return
        val rows = currentDetails!!.implants
        if (rows.size > 1024) { error = "Select at most 1024 implants per edit."; return }
        selected = rows.map { it.objectKey }.toSet()
    }
    fun clearSelection() { if (available) selected = emptySet() }
    fun showPage(value: Int) {
        if (available) page = value.coerceIn(0, (currentDetails!!.implants.size - 1).coerceAtLeast(0) / 25)
    }
    private fun isCurrent(before: ImplantDetails, rows: List<ImplantRow>) = available && before === currentDetails &&
        rows.isNotEmpty() && rows.all { it in before.implants }
    fun toggle(context: Context, before: ImplantDetails, row: ImplantRow) {
        if (!isCurrent(before, listOf(row))) return
        submit(context, before.fitId, before.revision, BridgeOperation.ToggleImplants(before.fitId, row.index,
            before.implants.filter { it.objectKey in selected }.map { it.index }))
    }
    fun remove(context: Context, before: ImplantDetails, rows: List<ImplantRow>) {
        if (!isCurrent(before, rows)) return
        submit(context, before.fitId, before.revision, BridgeOperation.RemoveImplants(before.fitId, rows.map { it.index }))
    }
    fun openVariation(before: ImplantDetails, row: ImplantRow, onOpen: (Int) -> Unit) {
        if (isCurrent(before, listOf(row))) onOpen(row.index)
    }
    private fun submit(context: Context, fitId: String, revision: Long, operation: BridgeOperation, onSaved: () -> Unit = {}) {
        if (editing || fit()?.let { it.id == fitId && it.revision == revision } != true) return
        editing = true; error = null; addError = null; message = null
        EngineRuntime.request(context, operation, mapOf(fitId to revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (fit()?.id == fitId) {
                if (failure != null) error = "The engine could not confirm the implant edit. Restart before making more changes."
                else if (!result.isSuccess) error = result.error?.message ?: "The implant edit was rejected."
                else {
                    message = "Implant edit saved. Undo is available."
                    fit()?.let { load(context, it, retry = true) }; onSaved()
                }
                addError = error
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun ImplantReplacementDialog(model: ImplantEditorModel, onSaved: () -> Unit) {
    val pending = model.pendingReplacement ?: return
    val context = LocalContext.current
    // Observe engine publication so a background edit immediately disables stale confirmation.
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val current = engine is EngineState.Ready && model.replacementCurrent
    AlertDialog(onDismissRequest = model::cancelReplacement,
        title = { Text("Replace implant in slot ${pending.options.slot}?") },
        text = { Column {
            Text("${pending.fitName}: replace ${pending.options.occupant!!.name} with ${pending.itemName}.")
            Text("The new implant starts active. This is one undoable edit.")
            if (pending.options.location == ImplantLocation.CHARACTER) Text("This also switches to Fit-specific implants. The character collection is kept.")
            if (!current) Text("The fit or engine changed. Cancel and check the current slot before replacing.",
                color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("implant-replace-stale"))
        } },
        confirmButton = { TextButton(onClick = { model.confirmReplacement(context, onSaved) }, enabled = current,
            modifier = Modifier.testTag("implant-replace-confirm")) { Text("Replace implant") } },
        dismissButton = { TextButton(onClick = model::cancelReplacement, modifier = Modifier.testTag("implant-replace-cancel")) { Text("Cancel") } },
        modifier = Modifier.testTag("implant-replace-dialog"))
}

@Composable
internal fun ImplantEquipmentActions(model: ImplantEditorModel, item: EquipmentItem, onSaved: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = engine as? EngineState.Ready ?: return
    if (ready.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) {
        Text("Restart the app before adding or replacing an implant.", Modifier.testTag("equipment-implant-unavailable")); return
    }
    if (model.editing) Text("Saving implant edit…", Modifier.testTag("equipment-implant-saving"))
    LaunchedEffect(ready.fit.id, ready.fit.revision, item.id) { model.loadAddOptions(context, ready.fit, item.id) }
    if (model.addLoading) Text("Checking implant slot…", Modifier.testTag("equipment-implant-loading"))
    model.addError?.let {
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("equipment-implant-error"))
        TextButton(onClick = { model.loadAddOptions(context, ready.fit, item.id, true) }, enabled = !model.editing && !model.addLoading,
            modifier = Modifier.testTag("equipment-implant-retry")) { Text("Check implant slot again") }
    }
    val options = model.currentAdd(item.id) ?: return
    if (!options.isImplant) return
    Text("Implant slot ${options.slot}", Modifier.testTag("equipment-implant-slot"))
    if (options.isStructure) Text("Implants are unavailable for structures.", Modifier.testTag("equipment-implant-structure"))
    else if (options.alreadyFitted && !options.sourceOnly) Text("This implant is already fitted.", Modifier.testTag("equipment-implant-already-fitted"))
    else {
        if (options.location == ImplantLocation.CHARACTER) Text("This switches to Fit-specific implants and keeps the character collection.", Modifier.testTag("equipment-implant-character"))
        if (options.sourceOnly) Text("Already in the retained fit collection. Its activation and identity are kept.")
        else options.occupant?.let { Text("Fit-specific slot occupied by ${it.name}. Replacement requires confirmation.") }
        Button(onClick = { model.add(context, item, onSaved) }, enabled = !model.editing && !model.addLoading && options.canAdd,
            modifier = Modifier.testTag("equipment-fit-implant")) {
            Text(if (options.sourceOnly) "Use fit implants" else if (options.occupant == null) "Add implant" else "Review implant replacement")
        }
    }
}

@Composable
internal fun ImplantEditor(model: ImplantEditorModel, onBrowse: () -> Unit, onBack: () -> Unit, onInspect: () -> Unit, onVariations: (Int) -> Unit, onCharacter: (String) -> Unit = {}) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = engine as? EngineState.Ready
    val fit = ready?.fit
    BackHandler { onBack() }
    Text("Implants", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("implants-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to manage implants.", Modifier.testTag("implants-no-fit")); return }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    if (ready?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) {
        Text("Restart the app to recover the fitting engine.", Modifier.testTag("implants-unavailable")); return
    }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("implants-error")) }
    model.message?.let { Text(it, Modifier.testTag("implants-saved")) }
    if (model.loading) Text("Loading implants…", Modifier.testTag("implants-loading"))
    if (model.editing) Text("Saving implant edit…", Modifier.testTag("implants-saving"))
    val d = model.currentDetails
    if (d == null) {
        if (!model.loading) Button(onClick = { model.load(context, fit, true) }, enabled = !model.editing,
            modifier = Modifier.testTag("implants-retry")) { Text("Reload implants") }
        return
    }
    if (d.isStructure) Text("Implants are unavailable for structures.", Modifier.testTag("implants-structure"))
    val features by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val current = features?.takeIf { it.bindings[fit.id]?.fitRevision == fit.revision }
    val binding = current?.bindings?.get(fit.id)
    val profile = current?.profiles?.singleOrNull { it.id == binding?.profileId }
    if (binding == null || profile == null || binding.implantSource != d.location) {
        Text("Character source details are not current. Reload before changing implants.", Modifier.testTag("implants-source-unavailable")); return
    }
    Text("Fit-specific: ${d.implants.size} · Character: ${profile.name}: ${profile.implants.size}", Modifier.testTag("implants-counts"))
    Text("Switching keeps both collections", Modifier.testTag("implants-source-preserves"))
    Row {
        TextButton(onClick = { model.setSource(context, checkNotNull(current), ImplantLocation.FIT) }, enabled = !d.isStructure && !model.editing && !model.loading,
            modifier = Modifier.testTag("implants-source-fit")) { Text((if (d.location == ImplantLocation.FIT) "✓ " else "") + "Fit-specific") }
        TextButton(onClick = { model.setSource(context, checkNotNull(current), ImplantLocation.CHARACTER) }, enabled = !d.isStructure && !model.editing && !model.loading,
            modifier = Modifier.testTag("implants-source-character")) { Text((if (d.location == ImplantLocation.CHARACTER) "✓ " else "") + "Character: ${profile.name}") }
    }
    TextButton(onClick = { onCharacter(profile.id) }, enabled = !model.editing,
        modifier = Modifier.testTag("implants-edit-character")) { Text("Edit character implants") }
    TextButton(onClick = onBrowse, enabled = !d.isStructure && !model.editing,
        modifier = Modifier.testTag("implants-browse")) { Text("Browse implants to add") }
    TextButton(onClick = onInspect, modifier = Modifier.testTag("implants-inspect")) {
        Text(if (d.location == ImplantLocation.CHARACTER) "Retained fit-local item attributes (not character implants)" else "Fitted item attributes and affectors")
    }
    if (d.location == ImplantLocation.CHARACTER) {
        Text("Applied implants: ${profile.name}. Character rows are read-only here.", Modifier.testTag("implants-character"))
        var characterPage by remember(profile.id) { mutableStateOf(0) }
        val pages = ((profile.implants.size + 24) / 25).coerceAtLeast(1)
        val page = characterPage.coerceAtMost(pages - 1)
        if (profile.implants.isEmpty()) Text("No character implants. The fit-specific collection is retained.", Modifier.testTag("character-implants-empty"))
        if (pages > 1) Row {
            TextButton(onClick = { characterPage = page - 1 }, enabled = page > 0) { Text("Previous character implants") }
            Text("Page ${page + 1} of $pages")
            TextButton(onClick = { characterPage = page + 1 }, enabled = page + 1 < pages) { Text("Next character implants") }
        }
        profile.displayImplants.drop(page * 25).take(25).forEach { row -> key(profile.id, row.implantId) {
            Card(Modifier.fillMaxWidth().testTag("applied-character-implant-${row.implantId}")) {
                Column(Modifier.padding(12.dp)) {
                    Text("Slot ${row.slot}: ${row.name}")
                    Text("${profile.name} · ${if (row.active) "Active" else "Inactive"} · character revision ${profile.revision}")
                }
            }
        } }
        return
    }
    Text("Implants are shown by slot. Activation applies to this and selected rows. Replacement and removal are undoable.")
    val available = model.available
    val selected = d.displayRows.filter { it.objectKey in model.selected }
    Row {
        TextButton(onClick = model::selectAll, enabled = available, modifier = Modifier.testTag("implants-select-all")) { Text("Select all") }
        TextButton(onClick = model::clearSelection, enabled = available, modifier = Modifier.testTag("implants-clear-selection")) { Text("Clear selection") }
    }
    selected.firstOrNull()?.let { main ->
        Button(onClick = { model.toggle(context, d, main) }, enabled = available,
            modifier = Modifier.testTag("implants-toggle-selected")) { Text(if (main.active) "Deactivate selected" else "Activate selected") }
        TextButton(onClick = { model.remove(context, d, selected) }, enabled = available,
            modifier = Modifier.testTag("implants-remove-selected")) { Text("Remove selected implants") }
    }
    if (d.implants.isEmpty()) Text("No implants in this fit.", Modifier.testTag("implants-empty"))
    val pages = ((d.implants.size + 24) / 25).coerceAtLeast(1)
    if (pages > 1) {
        Text("Page ${model.page + 1} of $pages · ${selected.size} selected")
        Row {
            TextButton(onClick = { model.showPage(model.page - 1) }, enabled = available && model.page > 0) { Text("Previous implants") }
            TextButton(onClick = { model.showPage(model.page + 1) }, enabled = available && model.page + 1 < pages) { Text("Next implants") }
        }
    }
    d.displayRows.drop(model.page * 25).take(25).forEach { row -> key(row.objectKey) {
        Card(Modifier.fillMaxWidth().testTag("implant-${row.index}")) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(Modifier.fillMaxWidth().toggleable(row.objectKey in model.selected, enabled = available, role = Role.Checkbox,
                    onValueChange = { model.select(row.objectKey, it) }).testTag("implant-${row.index}-select")) {
                    Checkbox(checked = row.objectKey in model.selected, onCheckedChange = null)
                    Text("Slot ${row.slot}: ${row.name}", style = MaterialTheme.typography.titleMedium)
                }
                Text(if (row.active) "Active" else "Inactive", Modifier.testTag("implant-${row.index}-state"))
                TextButton(onClick = { model.toggle(context, d, row) }, enabled = available,
                    modifier = Modifier.testTag("implant-${row.index}-toggle")) { Text(if (row.active) "Deactivate this + selected" else "Activate this + selected") }
                TextButton(onClick = { model.remove(context, d, listOf(row)) }, enabled = available,
                    modifier = Modifier.testTag("implant-${row.index}-remove")) { Text("Remove this implant") }
                TextButton(onClick = { model.openVariation(d, row, onVariations) }, enabled = available,
                    modifier = Modifier.testTag("implant-${row.index}-variations")) { Text("Variations") }
            }
        }
    } }
}
