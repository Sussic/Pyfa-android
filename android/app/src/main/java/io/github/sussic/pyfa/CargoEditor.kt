package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
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
    var details by mutableStateOf<CargoDetails?>(null)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    val amounts = mutableStateMapOf<Int, String>()
    val removals = mutableStateMapOf<Int, String>()
    private var requested: Pair<String, Long>? = null
    private var generation = 0

    fun open() {
        ++generation; requested = null; details = null; loading = false
        amounts.clear(); removals.clear(); error = null; message = null
    }

    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested?.first != fit.id) {
            details = null; amounts.clear(); removals.clear(); message = null; error = null
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
internal fun CargoEditor(model: CargoEditorModel, onBrowse: () -> Unit, onBack: () -> Unit) {
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
    if (details.isStructure) Text("Structures accept charges in cargo. Their listed cargo capacity may be zero.")
    TextButton(onClick = onBrowse, modifier = Modifier.testTag("cargo-browse")) { Text("Browse items to add") }
    if (details.cargo.isEmpty()) Text("No cargo stacks.", modifier = Modifier.testTag("cargo-empty"))
    for (stack in details.cargo) {
        Card(Modifier.fillMaxWidth().testTag("cargo-stack-${stack.id}")) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(stack.name, style = MaterialTheme.typography.titleMedium)
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
