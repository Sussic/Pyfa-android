package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.text.NumberFormat
import kotlinx.coroutines.Dispatchers

class CargoEditorModel : ViewModel() {
    val transfers = CargoTransferModel()
    var details by mutableStateOf<CargoDetails?>(null)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    var selected by mutableStateOf<List<Int>>(emptyList())
    var selectedAmount by mutableStateOf("1")
    var actions by mutableStateOf<CargoActionOptions?>(null)
    var actionsLoading by mutableStateOf(false)
    var showVariations by mutableStateOf(false)
    private var actionGeneration = 0
    val amounts = mutableStateMapOf<Int, String>()
    val removals = mutableStateMapOf<Int, String>()
    private var requested: Pair<String, Long>? = null
    private var generation = 0

    fun open() {
        ++generation; requested = null; details = null; loading = false
        amounts.clear(); removals.clear(); error = null; message = null
        selected = emptyList(); actions = null; ++actionGeneration; actionsLoading = false; showVariations = false
    }

    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested?.first != fit.id) {
            details = null; amounts.clear(); removals.clear(); message = null; error = null
            selected = emptyList(); actions = null; showVariations = false
        }
        requested = next
        val token = ++generation
        loading = true
        EngineRuntime.cargoDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) {
                    details = null; error = "Cargo could not be loaded. Try again."
                } else {
                    details = value; error = null
                    amounts.clear(); removals.clear()
                    value.cargo.forEach { amounts[it.id] = it.amount.toString(); removals[it.id] = "1" }
                    selected = selected.filter { id -> value.cargo.any { it.id == id } }
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun add(context: Context, item: EquipmentItem, onAdded: () -> Unit) {
        val fit = (EngineRuntime.state.value as? EngineState.Ready)?.fit ?: return
        if (editing) return
        submit(context, fit.id, fit.revision, BridgeOperation.AddCargo(fit.id, item.id, 1),
            "${item.name} added to cargo. Fit saved.", onAdded)
    }

    fun loadActions(context: Context, fit: FitSnapshot, itemId: Int, fromCargo: Boolean) {
        val token = ++actionGeneration
        actions = null; actionsLoading = true; showVariations = false
        EngineRuntime.cargoActionOptions(context, fit.id, itemId, fromCargo).whenCompleteAsync({ value, failure ->
            if (token == actionGeneration) {
                actionsLoading = false
                if (failure != null) error = "Cargo actions could not be loaded. Try again."
                else { actions = value; error = null }
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun toggle(stack: CargoStack) {
        selected = if (stack.id in selected) selected - stack.id else selected + stack.id
        showVariations = false
    }

    fun setSelected(context: Context) {
        val current = details ?: return
        val amount = selectedAmount.trim().toLongOrNull()
        if (amount == null || amount < 0) { error = "Enter a whole-number quantity, or zero to remove."; return }
        submit(context, current.fitId, current.revision,
            BridgeOperation.SetCargoQuantities(current.fitId, selected.toList(), amount), "Selected quantities saved.")
    }

    fun removeSelected(context: Context) {
        val current = details ?: return
        submit(context, current.fitId, current.revision,
            BridgeOperation.RemoveCargos(current.fitId, selected.toList()), "Selected cargo removed. Fit saved.")
    }

    fun preset(context: Context, current: CargoActionOptions, onSaved: () -> Unit) =
        submit(context, current.fitId, current.revision, BridgeOperation.AddCargoPreset(current.fitId, current.itemId),
            "Ammunition added to cargo. Fit saved.", onSaved)

    fun fill(context: Context, current: CargoActionOptions, onSaved: () -> Unit = {}) =
        submit(context, current.fitId, current.revision,
            BridgeOperation.FillCargo(current.fitId, current.itemId, current.fromCargo), "Cargo filled. Fit saved.", onSaved)

    fun variation(context: Context, current: CargoActionOptions, target: VariationChoice) {
        submit(context, current.fitId, current.revision,
            BridgeOperation.ChangeCargoVariations(current.fitId, current.itemId, selected.toList(), target.id),
            "Matching selected cargo changed to ${target.name}. Fit saved.")
    }

    fun set(context: Context, stack: CargoStack) {
        val current = details ?: return
        val amount = amounts[stack.id]?.trim()?.toLongOrNull()
        if (amount == null || amount <= 0) { error = "Enter a positive whole-number quantity."; return }
        if (amount == stack.amount) return
        submit(context, current.fitId, current.revision,
            BridgeOperation.SetCargoQuantity(current.fitId, stack.id, amount),
            "${stack.name} quantity saved.")
    }

    fun remove(context: Context, stack: CargoStack, all: Boolean) {
        val current = details ?: return
        val amount = if (all) stack.amount else removals[stack.id]?.trim()?.toLongOrNull()
        if (amount == null || amount <= 0) { error = "Enter a positive whole-number removal quantity."; return }
        submit(context, current.fitId, current.revision,
            BridgeOperation.RemoveCargo(current.fitId, stack.id, amount),
            "${stack.name} removed from cargo. Fit saved.")
    }

    private fun submit(context: Context, fitId: String, revision: Long, operation: BridgeOperation,
                       saved: String, onSaved: () -> Unit = {}) {
        if (editing || loading) return
        editing = true; error = null; message = null
        EngineRuntime.request(context, operation, mapOf(fitId to revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (failure != null) error = "The fitting engine could not confirm the cargo edit. Restart the app."
            else if (!result.isSuccess) error = result.error?.message
            else {
                message = saved; onSaved()
                EngineRuntime.library.value.find { it.id == fitId }?.let { load(context, it, retry = true) }
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

private fun volume(value: Double): String = NumberFormat.getNumberInstance().apply {
    maximumFractionDigits = 6
}.format(value) + " m³"

@Composable
internal fun CargoEditor(model: CargoEditorModel, onBrowse: () -> Unit, onBack: () -> Unit, onTransfers: () -> Unit) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Cargo", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("cargo-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to view its cargo."); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("cargo-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("cargo-saved")) }
    if (model.loading) Text("Loading cargo…", modifier = Modifier.testTag("cargo-loading"))
    val details = model.details?.takeIf { it.fitId == fit.id && it.revision == fit.revision }
    if (details == null) {
        if (!model.loading) Button(onClick = { model.load(context, fit, retry = true) },
            modifier = Modifier.testTag("cargo-retry")) { Text("Retry cargo") }
        return
    }
    Text("Cargo used: ${volume(details.usedM3)} / ${volume(details.capacityM3)}",
        modifier = Modifier.testTag("cargo-volume"))
    if (details.overCapacity) Text("Over cargo capacity", color = MaterialTheme.colorScheme.error,
        modifier = Modifier.testTag("cargo-over-capacity"))
    if (details.isStructure) Text("Structure cargo can also hold transferred fitted modules. Its listed capacity may be zero.")
    TextButton(onClick = onBrowse, modifier = Modifier.testTag("cargo-browse")) { Text("Browse items to add") }
    TextButton(onClick = onTransfers, modifier = Modifier.testTag("cargo-transfers")) { Text("Transfer fitted modules and charges") }
    val main = details.cargo.find { it.id == model.selected.firstOrNull() }
    LaunchedEffect(fit.id, fit.revision, main?.id) {
        if (main != null) model.loadActions(context, fit, main.id, true)
    }
    val available = !model.editing && !model.loading
    if (details.cargo.isNotEmpty()) {
        Row {
            TextButton(onClick = { model.selected = details.cargo.map { it.id } }, enabled = available,
                modifier = Modifier.testTag("cargo-select-all")) { Text("Select all") }
            TextButton(onClick = { model.selected = emptyList() }, enabled = available,
                modifier = Modifier.testTag("cargo-clear-selection")) { Text("Clear selection") }
        }
    }
    if (main != null) {
        Text("${model.selected.size} stacks selected", modifier = Modifier.testTag("cargo-selected-count"))
        OutlinedTextField(value = model.selectedAmount, onValueChange = { model.selectedAmount = it },
            label = { Text("Quantity for each selected stack (0 removes)") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            modifier = Modifier.fillMaxWidth().testTag("cargo-selected-quantity"))
        Button(onClick = { focus.clearFocus(); model.setSelected(context) }, enabled = available,
            modifier = Modifier.testTag("cargo-set-selected")) { Text("Save selected quantities") }
        TextButton(onClick = { focus.clearFocus(); model.removeSelected(context) }, enabled = available,
            modifier = Modifier.testTag("cargo-remove-selected")) { Text("Remove selected stacks") }
        val actions = model.actions?.takeIf { it.fitId == fit.id && it.revision == fit.revision &&
            it.itemId == main.id && it.fromCargo }
        if (actions != null) {
            Text("First selected: ${main.name}")
            Button(onClick = { focus.clearFocus(); model.fill(context, actions) },
                enabled = available && (actions.fillQuantity ?: 0) > 0,
                modifier = Modifier.testTag("cargo-fill-selected")) {
                Text("Fill cargo with ${main.name} (+${actions.fillQuantity})")
            }
            if (actions.fillQuantity == 0L) Text("No room for another item.")
            if (actions.variations.isNotEmpty()) {
                TextButton(onClick = { model.showVariations = !model.showVariations }, enabled = available,
                    modifier = Modifier.testTag("cargo-variations")) { Text("Change selected variations") }
                if (model.showVariations) {
                    Text("Changes selected stacks in the same variation family as ${main.name}; quantities merge.")
                    actions.variations.forEach { choice ->
                        TextButton(onClick = { focus.clearFocus(); model.variation(context, actions, choice) },
                            enabled = available && choice.enabled,
                            modifier = Modifier.testTag("cargo-variation-${choice.id}")) {
                            Text("${choice.group} · ${choice.name}")
                        }
                    }
                }
            }
        } else if (model.actionsLoading) Text("Loading cargo actions…")
        else TextButton(onClick = { model.loadActions(context, fit, main.id, true) },
            modifier = Modifier.testTag("cargo-actions-retry")) { Text("Retry cargo actions") }
    }
    if (details.cargo.isEmpty()) Text("No cargo stacks.", modifier = Modifier.testTag("cargo-empty"))
    for (stack in details.cargo) {
        Card(Modifier.fillMaxWidth().testTag("cargo-stack-${stack.id}")) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Row {
                    Checkbox(checked = stack.id in model.selected, onCheckedChange = { model.toggle(stack) },
                        enabled = available, modifier = Modifier.testTag("cargo-select-${stack.id}"))
                    Text(stack.name, style = MaterialTheme.typography.titleMedium)
                }
                Text("${stack.amount} items · ${volume(stack.unitVolumeM3)} each")
                OutlinedTextField(value = model.amounts[stack.id].orEmpty(),
                    onValueChange = { model.amounts[stack.id] = it },
                    label = { Text("Stack quantity") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth().testTag("cargo-quantity-${stack.id}"))
                Button(onClick = { focus.clearFocus(); model.set(context, stack) }, enabled = !model.editing && !model.loading,
                    modifier = Modifier.testTag("cargo-set-${stack.id}")) { Text("Save quantity") }
                OutlinedTextField(value = model.removals[stack.id].orEmpty(),
                    onValueChange = { model.removals[stack.id] = it },
                    label = { Text("Remove quantity") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth().testTag("cargo-remove-quantity-${stack.id}"))
                TextButton(onClick = { focus.clearFocus(); model.remove(context, stack, false) },
                    enabled = !model.editing && !model.loading,
                    modifier = Modifier.testTag("cargo-remove-part-${stack.id}")) { Text("Remove quantity") }
                TextButton(onClick = { focus.clearFocus(); model.remove(context, stack, true) },
                    enabled = !model.editing && !model.loading,
                    modifier = Modifier.testTag("cargo-remove-all-${stack.id}")) { Text("Remove stack") }
            }
        }
    }
}
