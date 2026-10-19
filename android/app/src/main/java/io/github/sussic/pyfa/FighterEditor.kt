package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers
import java.util.concurrent.CompletableFuture

data class FighterQuantityDraft(val revision: Long, val text: String)

class FighterEditorModel(private val similarQuery: (Context, FighterDetails, FighterSquadron) -> CompletableFuture<FighterSimilarSelection> =
    { context, details, row -> EngineRuntime.fighterSimilarSelection(context, details.fitId, details.revision, row.index) }) : ViewModel() {
    var details by mutableStateOf<FighterDetails?>(null); private set
    var loading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var selectingSimilar by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var selected by mutableStateOf<Set<String>>(emptySet()); private set
    var expanded by mutableStateOf<Set<String>>(emptySet()); private set
    var page by mutableStateOf(0); private set
    val drafts = mutableStateMapOf<Pair<String, String>, FighterQuantityDraft>()
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    private var selectionEpoch = 0L
    private fun selectionChanged() { selectionEpoch += 1 }
    private fun fit(): FitSnapshot? = (EngineRuntime.state.value as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit
    val currentDetails get() = details?.takeIf { d -> fit()?.let { it.id == d.fitId && it.revision == d.revision } == true }
    val available get() = !loading && !editing && currentDetails != null
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && next == requested) return
        if (requested?.first != fit.id) { selected = emptySet(); expanded = emptySet(); page = 0; message = null }
        selectionChanged()
        requested = next; details = null; loading = true; error = null
        val token = ++generation
        EngineRuntime.fighterDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Fighter details could not be verified. Retry, or restart if the engine is unavailable."
                else if (value.fitId == next.first && value.revision == next.second) {
                    details = value
                    val keys = value.squadrons.map { it.objectKey }.toSet()
                    selected = selected.intersect(keys); expanded = expanded.intersect(keys)
                    page = page.coerceAtMost((value.squadrons.size - 1).coerceAtLeast(0) / 25)
                } else error = "The fit changed while loading fighters. Reload its current values."
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun select(key: String, checked: Boolean) {
        if (!available || currentDetails?.squadrons?.none { it.objectKey == key } != false) return
        if (checked && key !in selected && selected.size >= 1024) { error = "Select at most 1024 squadrons per edit."; return }
        selectionChanged()
        selected = if (checked) selected + key else selected - key
    }
    fun selectAll() {
        if (!available) return
        val rows = currentDetails!!.squadrons
        if (rows.size > 1024) { error = "Select at most 1024 squadrons per edit."; return }
        selectionChanged()
        selected = rows.map { it.objectKey }.toSet()
    }
    fun showPage(value: Int) {
        if (available) page = value.coerceIn(0, (currentDetails!!.squadrons.size - 1).coerceAtLeast(0) / 25)
    }
    fun clearSelection() { if (available) { selectionChanged(); selected = emptySet() } }
    fun selectType(row: FighterSquadron) {
        if (!available || currentDetails!!.squadrons.none { it === row }) return
        val rows = currentDetails!!.squadrons.filter { it.itemId == row.itemId }
        if (rows.size > 1024) { error = "Select at most 1024 squadrons per edit."; return }
        selectionChanged()
        selected = rows.map { it.objectKey }.toSet()
    }
    fun canSelectSimilar(before: FighterDetails, row: FighterSquadron) = available && !selectingSimilar &&
        currentDetails === before && before.squadrons.any { it === row }
    fun selectSimilar(context: Context, before: FighterDetails, row: FighterSquadron) {
        if (!canSelectSimilar(before, row)) return
        val epoch = selectionEpoch
        selectingSimilar = true; error = null; message = null
        val pending = try { similarQuery(context, before, row) } catch (failure: Exception) {
            selectingSimilar = false; error = FighterSimilarSelectionCodec.failureMessage(failure); return
        }
        pending.whenCompleteAsync({ result, failure ->
            // Hold the launch gate until completion, even if selection or navigation changes.
            selectingSimilar = false
            if (epoch == selectionEpoch && available && currentDetails === before) {
                if (failure != null) error = FighterSimilarSelectionCodec.failureMessage(failure)
                else try {
                    val keys = FighterSimilarSelectionCodec.selectedKeys(result, before, row)
                    selectionChanged(); selected = keys
                    message = "${keys.size} similar squadrons selected. No fitting values changed."
                } catch (_: BridgeProtocolException) {
                    error = "The fighter selection no longer matches this fit. Reload fighters and try again."
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun expand(key: String) { expanded = if (key in expanded) expanded - key else expanded + key }
    fun draft(row: FighterSquadron): FighterQuantityDraft? = details?.let { drafts[it.fitId to row.objectKey] }
    fun quantity(row: FighterSquadron, text: String) {
        val d = currentDetails ?: return
        if (!available) return
        val key = d.fitId to row.objectKey
        if (text == row.amount.toString()) drafts.remove(key)
        else drafts[key] = FighterQuantityDraft(drafts[key]?.revision ?: d.revision, text)
    }
    fun discard(fitId: String, key: String) { drafts.remove(fitId to key) }
    fun rebase(row: FighterSquadron) {
        val d = currentDetails ?: return
        val key = d.fitId to row.objectKey
        drafts[key]?.let { drafts[key] = it.copy(revision = d.revision) }
    }
    fun add(context: Context, item: EquipmentItem, onSaved: () -> Unit) {
        val fit = fit() ?: return
        if (item.category != "Fighter") return
        submit(context, fit.id, fit.revision, BridgeOperation.AddFighter(fit.id, item.id), onSaved = onSaved)
    }
    fun saveAmount(context: Context, row: FighterSquadron, maximum: Boolean = false) {
        val d = currentDetails ?: return
        if (row !in d.squadrons) return
        val draft = draft(row)
        if (!maximum && draft != null && draft.revision != d.revision) {
            error = "This quantity draft is stale. Review the current squadron, then keep or discard the draft."; return
        }
        val amount = if (maximum) row.maxSize else (draft?.text ?: row.amount.toString()).trim().toIntOrNull()
        if (amount == null || amount !in 0..row.maxSize) {
            error = "Enter a whole-number quantity from 0 to ${row.maxSize}. Zero removes this squadron."; return
        }
        // GUI quantity zero means remove, including an already-zero durable squadron.
        if (amount != 0 && amount == row.amount) { discard(d.fitId, row.objectKey); return }
        submit(context, d.fitId, d.revision, BridgeOperation.SetFighterAmount(d.fitId, row.index, amount),
            savedDraft = d.fitId to row.objectKey)
    }
    private fun positions(d: FighterDetails) = d.squadrons.filter { it.objectKey in selected }.map { it.index }
    fun toggle(context: Context, row: FighterSquadron) {
        val d = currentDetails ?: return
        if (row !in d.squadrons) return
        submit(context, d.fitId, d.revision, BridgeOperation.ToggleFighters(d.fitId, row.index, positions(d)))
    }
    fun ability(context: Context, row: FighterSquadron, effectId: Int) {
        val d = currentDetails ?: return
        if (row !in d.squadrons) return
        if (row.abilities.none { it.effectId == effectId }) return
        submit(context, d.fitId, d.revision, BridgeOperation.ToggleFighterAbility(d.fitId, row.index, positions(d), effectId))
    }
    fun remove(context: Context, rows: List<FighterSquadron>) {
        val d = currentDetails ?: return
        if (rows.isEmpty() || rows.any { it !in d.squadrons }) return
        submit(context, d.fitId, d.revision, BridgeOperation.RemoveFighters(d.fitId, rows.map { it.index }))
    }
    fun variation(context: Context, row: FighterSquadron, choice: FighterVariation) {
        val d = currentDetails ?: return
        if (row !in d.squadrons) return
        if (!choice.enabled || choice !in row.variations) return
        submit(context, d.fitId, d.revision, BridgeOperation.ChangeFighterVariations(d.fitId, row.index, positions(d), choice.id))
    }
    private fun submit(context: Context, fitId: String, revision: Long, operation: BridgeOperation,
        savedDraft: Pair<String, String>? = null, onSaved: () -> Unit = {}) {
        if (editing || loading || fit()?.let { it.id == fitId && it.revision == revision } != true) return
        selectionChanged()
        editing = true; error = null; message = null
        EngineRuntime.request(context, operation, mapOf(fitId to revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (failure == null && result.isSuccess && savedDraft != null) drafts.remove(savedDraft)
            if (fit()?.id == fitId) {
                if (failure != null) error = "The engine could not confirm the fighter edit. Restart before making more changes."
                else if (!result.isSuccess) error = result.error?.message ?: "The fighter edit was rejected."
                else {
                    message = "Fighter edit saved. Undo is available."
                    // Replacement can append/reorder rows. Reload identities; never retain positions as selection.
                    fit()?.let { load(context, it, retry = true) }; onSaved()
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun FighterEditor(model: FighterEditorModel, onBrowse: () -> Unit, onBack: () -> Unit, onInspect: () -> Unit) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = engine as? EngineState.Ready
    val fit = ready?.fit
    BackHandler { onBack() }
    Text("Fighters", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("fighters-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to manage fighter squadrons."); return }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    if (ready?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) {
        Text("Restart the app to recover the fitting engine.", Modifier.testTag("fighters-unavailable")); return
    }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("fighters-error")) }
    model.message?.let { Text(it, Modifier.testTag("fighters-saved")) }
    if (model.loading) Text("Loading fighter squadrons…", Modifier.testTag("fighters-loading"))
    if (model.editing) Text("Saving fighter edit…", Modifier.testTag("fighters-saving"))
    if (model.selectingSimilar) Text("Finding similar squadrons…", Modifier.testTag("fighters-selecting-similar"))
    val d = model.currentDetails
    if (d == null) {
        if (!model.loading) Button(onClick = { model.load(context, fit, true) }, enabled = !model.editing,
            modifier = Modifier.testTag("fighters-retry")) { Text("Reload fighters") }
        return
    }
    Text("Active squadrons: ${d.tubesUsed} / ${d.tubesTotal ?: "Unavailable"} tubes", Modifier.testTag("fighters-tubes"))
    Text("Fighter bay: ${d.bayUsed} / ${d.bayCapacity ?: "Unavailable"} m³", Modifier.testTag("fighters-bay"))
    d.categories.forEach { category ->
        Text("${category.name}: ${category.used} / ${category.total ?: "Unavailable"} active squadrons", Modifier.testTag("fighters-category-${category.slot}"))
    }
    if (d.tubesTotal?.let { d.tubesUsed > it } == true || d.bayCapacity?.let { d.bayUsed > it } == true ||
        d.categories.any { category -> category.total?.let { category.used > it } == true }) {
        Text("Fighter resources exceeded. Explicit activation is preserved; review the limits above.",
            color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("fighters-over-limit"))
    }
    TextButton(onClick = onBrowse, enabled = !model.editing, modifier = Modifier.testTag("fighters-browse")) { Text("Browse fighters to add") }
    TextButton(onClick = onInspect, modifier = Modifier.testTag("fighters-inspect")) { Text("Fitted item attributes and affectors") }
    Text("Adding uses EOS ability defaults and available tubes. Squadrons stay separate even when their types match.")
    val available = model.available
    val selected = d.squadrons.filter { it.objectKey in model.selected }
    Row {
        TextButton(onClick = model::selectAll, enabled = available, modifier = Modifier.testTag("fighters-select-all")) { Text("Select all") }
        TextButton(onClick = model::clearSelection, enabled = available, modifier = Modifier.testTag("fighters-clear-selection")) { Text("Clear selection") }
    }
    selected.firstOrNull()?.let { main ->
        Button(onClick = { focus.clearFocus(); model.toggle(context, main) }, enabled = available,
            modifier = Modifier.testTag("fighters-toggle-selected")) { Text(if (main.active) "Deactivate selected" else "Activate selected") }
        TextButton(onClick = { model.remove(context, selected) }, enabled = available,
            modifier = Modifier.testTag("fighters-remove-selected")) { Text("Remove selected squadrons") }
    }
    Text("Similar selection includes matching fighter types and source-compatible groups with the same complete ability set. Activity and ability on/off states do not affect membership.",
        Modifier.testTag("fighters-similar-help"))
    Text("A row's activation or ability control also applies to selected squadrons. Abilities affect only squadrons with that same effect.",
        Modifier.testTag("fighters-selection-help"))
    // Removed/replaced rows keep drafts visible until the user explicitly discards them.
    model.drafts.filter { (key, _) -> key.first == d.fitId && d.squadrons.none { it.objectKey == key.second } }.forEach { (key, draft) ->
        Text("A removed or replaced squadron has an unsaved quantity: ${draft.text}", Modifier.testTag("fighters-orphan-draft"))
        TextButton(onClick = { model.discard(key.first, key.second) }, enabled = available) { Text("Discard missing squadron draft") }
    }
    if (d.squadrons.isEmpty()) Text("No fighter squadrons in this fit.", Modifier.testTag("fighters-empty"))
    val pages = ((d.squadrons.size + 24) / 25).coerceAtLeast(1)
    if (pages > 1) {
        Text("Page ${model.page + 1} of $pages · ${selected.size} selected")
        Row {
            TextButton(onClick = { model.showPage(model.page - 1) }, enabled = available && model.page > 0,
                modifier = Modifier.testTag("fighters-previous")) { Text("Previous squadrons") }
            TextButton(onClick = { model.showPage(model.page + 1) }, enabled = available && model.page + 1 < pages,
                modifier = Modifier.testTag("fighters-next")) { Text("Next squadrons") }
        }
    }
    d.squadrons.drop(model.page * 25).take(25).forEach { row -> key(row.objectKey) {
        Card(Modifier.fillMaxWidth().testTag("fighter-${row.index}")) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(Modifier.fillMaxWidth().toggleable(row.objectKey in model.selected, enabled = available, role = Role.Checkbox,
                    onValueChange = { model.select(row.objectKey, it) }).testTag("fighter-${row.index}-select")) {
                    Checkbox(checked = row.objectKey in model.selected, onCheckedChange = null)
                    Text(row.name, style = MaterialTheme.typography.titleMedium)
                }
                Text("${row.group} · ${row.amount} / ${row.maxSize} fighters · ${if (row.active) "Active" else "Stored inactive"}")
                val draft = model.draft(row)
                val staleDraft = draft != null && draft.revision != d.revision
                OutlinedTextField(value = draft?.text ?: row.amount.toString(), onValueChange = { model.quantity(row, it) },
                    enabled = available, label = { Text("Squadron quantity (0 removes)") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth().testTag("fighter-${row.index}-amount"))
                if (staleDraft) {
                    Text("Fit changed. Review this retained quantity draft before saving.", color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.testTag("fighter-${row.index}-draft-conflict"))
                    TextButton(onClick = { model.rebase(row) }, enabled = available,
                        modifier = Modifier.testTag("fighter-${row.index}-keep-draft")) { Text("Keep draft for current squadron") }
                }
                Row {
                    TextButton(onClick = { focus.clearFocus(); model.saveAmount(context, row) }, enabled = available && !staleDraft,
                        modifier = Modifier.testTag("fighter-${row.index}-save")) { Text("Save quantity") }
                    TextButton(onClick = { model.saveAmount(context, row, maximum = true) }, enabled = available,
                        modifier = Modifier.testTag("fighter-${row.index}-maximum")) { Text("Maximum") }
                }
                if (draft != null) TextButton(onClick = { model.discard(d.fitId, row.objectKey) }, enabled = available,
                    modifier = Modifier.testTag("fighter-${row.index}-revert")) { Text("Discard quantity draft") }
                TextButton(onClick = { model.toggle(context, row) }, enabled = available,
                    modifier = Modifier.testTag("fighter-${row.index}-toggle")) { Text(if (row.active) "Deactivate this + selected" else "Activate this + selected") }
                TextButton(onClick = { model.selectType(row) }, enabled = available,
                    modifier = Modifier.testTag("fighter-${row.index}-select-type")) { Text("Select same type") }
                TextButton(onClick = { model.selectSimilar(context, d, row) }, enabled = model.canSelectSimilar(d, row),
                    modifier = Modifier.testTag("fighter-${row.index}-select-similar")) { Text("Select similar squadrons") }
                TextButton(onClick = { model.remove(context, listOf(row)) }, enabled = available,
                    modifier = Modifier.testTag("fighter-${row.index}-remove")) { Text("Remove this squadron") }
                Text("Implemented abilities", style = MaterialTheme.typography.titleSmall)
                if (row.abilities.isEmpty()) Text("No implemented abilities available.")
                row.abilities.forEach { ability ->
                    Row(Modifier.fillMaxWidth().toggleable(ability.active, enabled = available, role = Role.Checkbox,
                        onValueChange = { model.ability(context, row, ability.effectId) })
                        .testTag("fighter-${row.index}-ability-${ability.effectId}")) {
                        Checkbox(checked = ability.active, onCheckedChange = null)
                        Text(ability.name)
                    }
                }
                if (row.variations.isNotEmpty()) {
                    TextButton(onClick = { model.expand(row.objectKey) }, modifier = Modifier.testTag("fighter-${row.index}-variations")) { Text("Variations") }
                    if (row.objectKey in model.expanded) {
                        Text("Replace this and selected same-family squadrons. Replacement may reorder them.")
                        row.variations.forEach { choice ->
                            TextButton(onClick = { model.variation(context, row, choice) }, enabled = available && choice.enabled && choice.id != row.itemId,
                                modifier = Modifier.testTag("fighter-${row.index}-variation-${choice.id}")) { Text(choice.name) }
                        }
                    }
                }
            }
        }
    } }
}
