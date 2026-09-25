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
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

class VariationEditorModel : ViewModel() {
    var options by mutableStateOf<VariationOptions?>(null)
    var bulkOptions by mutableStateOf<BulkStateOptions?>(null)
    var bulkSelected by mutableStateOf<Set<Int>>(emptySet())
    var bulkScope by mutableStateOf(BulkScope.SELECTED)
    var context by mutableStateOf(VariationContext.MODULE)
    var position by mutableStateOf<Int?>(null)
    var selected by mutableStateOf<Int?>(null)
    var query by mutableStateOf("")
    var page by mutableStateOf(0)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    private var requested: Pair<String, Long>? = null
    private var ownRevision: Pair<String, Long>? = null
    private var generation = 0

    fun choose(target: VariationTarget?) {
        if (target != null) context = target.context
        if (target?.context == VariationContext.MODULE) bulkSelected = bulkSelected + target.index
        position = target?.index; selected = null; query = ""; page = 0
    }

    fun open(fitId: String?, module: Int?) {
        ++generation; requested = null; loading = false
        if (options?.fitId != fitId) options = null
        bulkOptions = null; bulkSelected = module?.let { setOf(it) } ?: emptySet()
        bulkScope = BulkScope.SELECTED; ownRevision = null
        context = VariationContext.MODULE; position = module; selected = null
        query = ""; page = 0; error = null; message = null
    }

    fun load(androidContext: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        val previous = options
        if (requested?.first != null && requested?.first != fit.id) {
            choose(null); options = null; error = null; message = null
        }
        if (retry && options == null) error = null
        requested = next
        val token = ++generation
        loading = true
        EngineRuntime.variationOptions(androidContext, fit.id).thenCombine(
            EngineRuntime.bulkStateOptions(androidContext, fit.id)) { variation, bulk -> variation to bulk
        }.whenCompleteAsync({ pair, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) { options = null; bulkOptions = null; error = "Variations could not be loaded. Try again." }
                else {
                    val (value, bulk) = pair
                    val old = previous?.targets?.find { it.context == context && it.index == position }
                    val current = value.targets.find { it.context == context && it.index == position }
                    if (old != null && old.itemId != current?.itemId) choose(null)
                    if (previous != null && (previous.fitId != value.fitId ||
                            previous.revision != value.revision && ownRevision != next)) {
                        bulkSelected = emptySet(); choose(null)
                    }
                    bulkSelected = bulkSelected.filterTo(mutableSetOf()) { index ->
                        value.targets.any { it.context == VariationContext.MODULE && it.index == index &&
                            previous?.targets?.any { oldRow -> oldRow.context == VariationContext.MODULE &&
                                oldRow.index == index && oldRow.itemId == it.itemId } == true }
                    }
                    options = value
                    bulkOptions = bulk
                    if (selected !in (current?.choices?.map { it.id } ?: emptyList())) selected = null
                    if (ownRevision == next) ownRevision = null
                }
            }
        }, ContextCompat.getMainExecutor(androidContext))
    }

    fun apply(androidContext: Context, target: VariationTarget, item: VariationChoice) {
        val before = options ?: return
        if (loading || editing) return
        editing = true; error = null; message = null
        EngineRuntime.request(androidContext,
            BridgeOperation.ChangeVariation(before.fitId, target.context, target.index, item.id),
            mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (requested?.first == before.fitId) {
                if (failure != null) error = "The fitting engine could not confirm the edit. Restart the app."
                else if (!result.isSuccess) error = result.error?.message
                else {
                    choose(null)
                    message = if (target.context == VariationContext.IMPLANT) "${item.name} applied to its slot. Fit saved."
                        else "Changed to ${item.name}. Fit saved."
                }
                EngineRuntime.library.value.find { it.id == before.fitId }?.let { load(androidContext, it, retry = true) }
            }
        }, ContextCompat.getMainExecutor(androidContext))
    }

    fun applyBulk(androidContext: Context, target: VariationTarget, item: VariationChoice?) {
        val before = options ?: return
        if (loading || editing || target.context != VariationContext.MODULE || target.index !in bulkSelected) return
        val operation = if (item == null) BridgeOperation.RemoveBulkModules(
            before.fitId, target.index, bulkSelected.sorted(), bulkScope)
        else BridgeOperation.ChangeBulkVariations(before.fitId, target.index, bulkSelected.sorted(), bulkScope, item.id)
        editing = true; error = null; message = null
        ownRevision = before.fitId to before.revision + 1
        EngineRuntime.request(androidContext, operation, mapOf(before.fitId to before.revision))
            .whenCompleteAsync({ result, failure ->
                editing = false
                if (failure != null || !result.isSuccess) ownRevision = null
                if (requested?.first == before.fitId) {
                    if (failure != null) error = "The fitting engine could not confirm the edit. Restart the app."
                    else if (!result.isSuccess) error = result.error?.message
                    else {
                        choose(null); bulkSelected = emptySet()
                        message = if (item == null) "Modules removed and fit saved."
                            else "Selected variations changed and fit saved."
                    }
                    EngineRuntime.library.value.find { it.id == before.fitId }?.let {
                        load(androidContext, it, retry = true)
                    }
                }
            }, ContextCompat.getMainExecutor(androidContext))
    }
}

@Composable
internal fun VariationEditor(model: VariationEditorModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val action = remember { BringIntoViewRequester() }
    LaunchedEffect(model.selected) { if (model.selected != null) action.bringIntoView() }
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    fun back() { if (model.position != null) model.choose(null) else onBack() }
    BackHandler { back() }
    Text("Item variations", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { back() }, modifier = Modifier.testTag("variations-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to change its item variations.", modifier = Modifier.testTag("variations-no-fit")); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text(fit.name, style = MaterialTheme.typography.titleLarge)
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("variations-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("variations-saved")) }
    if (model.loading) Text("Loading variations…")
    if (model.editing) Text("Saving fit…")
    val options = model.options?.takeIf { it.fitId == fit.id } ?: run {
        if (!model.loading) Button(onClick = { model.load(context, fit, retry = true) }) { Text("Retry") }
        return
    }
    val enabled = !model.loading && !model.editing && options.revision == fit.revision &&
        (state as? EngineState.Ready)?.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
    val target = options.targets.find { it.context == model.context && it.index == model.position }
    if (target == null) {
        Row {
            for (kind in VariationContext.entries) TextButton(onClick = { model.context = kind; model.choose(null) },
                modifier = Modifier.weight(1f).testTag("variations-context-${kind.wire}")) {
                Text(kind.label + if (model.context == kind) " ✓" else "")
            }
        }
        Text("Choose an existing item to see its variations.")
        if (model.context == VariationContext.MODULE) {
            Text("${model.bulkSelected.size} selected for variation or removal",
                modifier = Modifier.testTag("bulk-edits-selection-count"))
            Row {
                TextButton(onClick = { model.bulkSelected = options.targets.filter {
                    it.context == VariationContext.MODULE }.map { it.index }.toSet() }, enabled = enabled,
                    modifier = Modifier.testTag("bulk-edits-select-all")) { Text("Select all") }
                TextButton(onClick = { model.bulkSelected = emptySet() }, enabled = enabled,
                    modifier = Modifier.testTag("bulk-edits-clear")) { Text("Clear") }
            }
        }
    } else {
        Card(Modifier.fillMaxWidth().testTag("variations-current")) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(target.name, style = MaterialTheme.typography.titleMedium)
                VariationCurrent(target, fit)
            }
        }
        Text(when (target.context) {
            VariationContext.MODULE -> "Keeps supported states and charges. Incompatible charges are unloaded."
            VariationContext.DRONE -> "Keeps total and active quantities. The replacement becomes the last stack."
            VariationContext.IMPLANT -> "Keeps activation and replaces any implant in the chosen variation’s slot. If that slot differs, this implant stays fitted."
        }, style = MaterialTheme.typography.bodySmall)
        target.choices.find { it.id == model.selected }?.let { chosen ->
            Button(onClick = { focus.clearFocus(); model.apply(context, target, chosen) },
                enabled = enabled && chosen.enabled && chosen.id != target.itemId,
                modifier = Modifier.fillMaxWidth().bringIntoViewRequester(action).testTag("variation-apply")) { Text("Change to ${chosen.name}") }
        }
        if (target.context == VariationContext.MODULE) {
            Text("${model.bulkSelected.size} selected · Reference: ${target.name}",
                modifier = Modifier.testTag("bulk-edits-reference"))
            for ((scope, label) in listOf(BulkScope.SELECTED to "Selection only",
                BulkScope.SIMILAR to "All similar modules")) TextButton(
                    onClick = { model.bulkScope = scope }, enabled = enabled,
                    modifier = Modifier.testTag("bulk-edits-scope-${scope.name}")) {
                Text(label + if (model.bulkScope == scope) " ✓" else "")
            }
            val moduleTargets = options.targets.filter { it.context == VariationContext.MODULE }
            val similar = model.bulkOptions?.takeIf { it.fitId == fit.id && it.revision == fit.revision }
                ?.modules?.getOrNull(target.index)?.similarCandidates ?: emptyList()
            val variationPositions = if (model.bulkScope == BulkScope.SIMILAR) similar else
                options.familyCandidates[target.index].orEmpty().filter { it in model.bulkSelected }
            val removalPositions = if (model.bulkScope == BulkScope.SIMILAR) similar else
                model.bulkSelected.sorted()
            val changeCount = variationPositions.count { index ->
                moduleTargets.find { it.index == index }?.itemId != model.selected
            }
            Card(Modifier.fillMaxWidth().testTag("bulk-edits-preview")) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Variation targets: ${variationPositions.size} · Removal targets: ${removalPositions.size}",
                        modifier = Modifier.testTag("bulk-edits-target-count"))
                    if (model.selected != null) Text("$changeCount selected variation changes requested")
                    if (model.bulkScope == BulkScope.SIMILAR)
                        Text("Related items outside your selection may be included; check every target.")
                    for (row in moduleTargets) {
                        val change = when {
                            row.index in variationPositions && row.itemId == model.selected -> "variation skipped: already chosen"
                            row.index in variationPositions -> "variation target"
                            row.index in model.bulkSelected -> "variation skipped: different family"
                            else -> "variation outside scope"
                        }
                        val removal = if (row.index in removalPositions) "removal target" else "removal outside scope"
                        Text("${row.index + 1} · ${row.name}: $change; $removal",
                            modifier = Modifier.testTag("bulk-edits-preview-${row.index}"))
                    }
                    Text("Fitting restrictions may reject individual replacements. Charges or states may change after EOS checks.",
                        style = MaterialTheme.typography.bodySmall)
                    target.choices.find { it.id == model.selected }?.let { chosen ->
                        Button(onClick = { model.applyBulk(context, target, chosen) },
                            enabled = enabled && target.index in model.bulkSelected && chosen.enabled &&
                                changeCount > 0,
                            modifier = Modifier.fillMaxWidth().testTag("bulk-edits-change")) {
                            Text("Change variation in ${variationPositions.size} targets")
                        }
                    }
                    Button(onClick = { model.applyBulk(context, target, null) },
                        enabled = enabled && target.index in model.bulkSelected && removalPositions.isNotEmpty(),
                        modifier = Modifier.fillMaxWidth().testTag("bulk-edits-remove")) {
                        Text("Remove ${removalPositions.size} modules")
                    }
                }
            }
        }
    }
    OutlinedTextField(value = model.query, onValueChange = { model.query = it; model.page = 0 }, singleLine = true,
        label = { Text(if (target == null) "Filter fitted items" else "Filter variations") },
        modifier = Modifier.fillMaxWidth().testTag("variations-search"))
    val targets = options.targets.filter { it.context == model.context && it.name.contains(model.query.trim(), ignoreCase = true) }
    val choices = target?.choices?.filter { it.name.contains(model.query.trim(), ignoreCase = true) } ?: emptyList()
    val count = if (target == null) targets.size else choices.size
    val pages = maxOf(1, (count + 19) / 20)
    val page = model.page.coerceIn(0, pages - 1)
    Text("$count items · Page ${page + 1} of $pages", modifier = Modifier.testTag("variations-count"))
    if (count == 0) Text(if (model.query.isNotBlank()) "No items match this filter." else if (target == null)
        "No ${model.context.label.lowercase()} in this fit." else "No supported variations for this item.",
        modifier = Modifier.testTag("variations-empty"))
    if (target == null) {
        VariationTargets(targets.drop(page * 20).take(20), fit, enabled, model.bulkSelected,
            onToggle = { index -> model.bulkSelected = if (index in model.bulkSelected)
                model.bulkSelected - index else model.bulkSelected + index }) { row ->
            focus.clearFocus(); model.choose(row)
        }
    } else {
        VariationChoices(choices.drop(page * 20).take(20), target.itemId, enabled) { row ->
            focus.clearFocus(); model.selected = row.id
        }
    }
    if (pages > 1) Row {
        TextButton(onClick = { focus.clearFocus(); model.page = page - 1 }, enabled = page > 0,
            modifier = Modifier.testTag("variations-previous")) { Text("Previous") }
        TextButton(onClick = { focus.clearFocus(); model.page = page + 1 }, enabled = page + 1 < pages,
            modifier = Modifier.testTag("variations-next")) { Text("Next") }
    }
}

// Separate composition scopes keep the two list shapes independent when saving
// or navigating changes a choice picker back into a fitted-item list.
@Composable
private fun VariationTargets(rows: List<VariationTarget>, fit: FitSnapshot, enabled: Boolean,
                             selected: Set<Int>, onToggle: (Int) -> Unit, onChoose: (VariationTarget) -> Unit) {
    for (row in rows) key(row.context, row.index, row.itemId) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp)) {
                Text("${row.index + 1} · ${row.name}", style = MaterialTheme.typography.titleSmall)
                if (row.context == VariationContext.MODULE) Row {
                    Checkbox(checked = row.index in selected, onCheckedChange = { onToggle(row.index) },
                        enabled = enabled, modifier = Modifier.testTag("bulk-edits-select-${row.index}"))
                    Text("Select for bulk edit")
                }
                VariationCurrent(row, fit)
                TextButton(onClick = { onChoose(row) }, enabled = enabled,
                    modifier = Modifier.testTag("variation-target-${row.context.wire}-${row.index}")) { Text("Variations") }
            }
        }
    }
}

@Composable
private fun VariationChoices(rows: List<VariationChoice>, currentId: Int, enabled: Boolean,
                             onChoose: (VariationChoice) -> Unit) {
    for (row in rows) key(row.id) {
        TextButton(onClick = { onChoose(row) }, enabled = enabled && row.enabled,
            modifier = Modifier.fillMaxWidth().testTag("variation-item-${row.id}")) {
            Text(row.name + (row.group?.let { " · $it" } ?: "") +
                if (row.id == currentId) " · Current" else if (!row.enabled) " · Unavailable on this hull" else "")
        }
    }
}

@Composable
private fun VariationCurrent(target: VariationTarget, fit: FitSnapshot) {
    Text(when (val current = target.current) {
        is VariationInput.Module -> "${current.state.name.lowercase().replaceFirstChar { it.uppercase() }} · Charge: ${fit.modules.getOrNull(target.index)?.charge ?: "Empty"}"
        is VariationInput.Drone -> "${current.amount} total · ${current.active} active"
        is VariationInput.Implant -> "Slot ${current.slot} · ${if (current.active) "Active" else "Inactive"} · In this fit"
    })
}
