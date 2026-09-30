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
import androidx.compose.material3.RadioButton
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
import kotlinx.coroutines.Dispatchers
import java.text.NumberFormat

/** Retained by CargoEditorModel so touch choices survive activity recreation. */
class CargoTransferModel {
    var details by mutableStateOf<CargoTransferDetails?>(null)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    var direction by mutableStateOf(CargoTransferDirection.TO_CARGO)
    var positions by mutableStateOf<Set<Int>>(emptySet())
    var cargoId by mutableStateOf<Int?>(null)
    private var requested: Pair<String, Long>? = null
    private var generation = 0

    fun open() {
        ++generation; requested = null; details = null; positions = emptySet(); cargoId = null
        direction = CargoTransferDirection.TO_CARGO; error = null; message = null; loading = false
    }

    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested != next) { positions = emptySet(); cargoId = null }
        if (requested?.first != fit.id) { details = null; error = null; message = null }
        requested = next
        val token = ++generation
        loading = true
        EngineRuntime.cargoTransferDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) { details = null; error = "Transfers could not be loaded. Try again." }
                else { details = value }
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun selectDirection(value: CargoTransferDirection) {
        direction = value; positions = emptySet(); cargoId = null; error = null; message = null
    }

    fun toggle(index: Int) {
        positions = if (index in positions) positions - index else
            if (direction == CargoTransferDirection.FROM_CARGO) setOf(index) else positions + index
    }

    fun submit(context: Context, copy: Boolean) {
        val current = details?.cargo ?: return
        if (loading || editing) return
        editing = true; error = null; message = null
        EngineRuntime.request(context, BridgeOperation.TransferCargo(current.fitId, direction,
            positions.sortedDescending(), cargoId, copy), mapOf(current.fitId to current.revision))
            .whenCompleteAsync({ result, failure ->
                editing = false
                val active = (EngineRuntime.state.value as? EngineState.Ready)?.fit
                if (active?.id == current.fitId && requested?.first == current.fitId) {
                    if (failure != null) error = "The engine could not confirm the transfer. Restart the app."
                    else if (!result.isSuccess) error = result.error?.message
                    else { message = "Transfer complete. Fit saved."; positions = emptySet(); cargoId = null }
                    load(context, active, retry = true)
                }
            }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun CargoTransferEditor(model: CargoTransferModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Cargo transfers", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("transfers-back")) { Text("Back to cargo") }
    if (fit == null) { Text("Open a fit to transfer items."); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("transfers-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("transfers-saved")) }
    if (model.loading) Text("Loading transfers…", modifier = Modifier.testTag("transfers-loading"))
    val details = model.details?.takeIf { it.cargo.fitId == fit.id && it.cargo.revision == fit.revision }
    if (details == null) {
        if (!model.loading) Button(onClick = { model.load(context, fit, retry = true) }) { Text("Retry transfers") }
        return
    }
    val enabled = !model.loading && !model.editing
    val toCargo = model.direction == CargoTransferDirection.TO_CARGO
    val number = NumberFormat.getNumberInstance().apply { maximumFractionDigits = 6 }
    Text("Cargo used: ${number.format(details.cargo.usedM3)} m³ / ${number.format(details.cargo.capacityM3)} m³",
        modifier = Modifier.testTag("transfers-volume"))
    if (details.cargo.overCapacity) Text("Over cargo capacity", color = MaterialTheme.colorScheme.error)
    Row {
        TextButton(onClick = { model.selectDirection(CargoTransferDirection.TO_CARGO) }, enabled = enabled,
            modifier = Modifier.testTag("transfers-to-cargo")) { Text("Fit → cargo") }
        TextButton(onClick = { model.selectDirection(CargoTransferDirection.FROM_CARGO) }, enabled = enabled,
            modifier = Modifier.testTag("transfers-from-cargo")) { Text("Cargo → fit") }
    }
    Text(if (toCargo) "Move or copy selected fitted modules and their loaded charges into cargo."
        else "Choose a cargo stack and one fitting position. Charges load a full magazine; copy keeps the source stack.")
    if (toCargo) Text("Choose an optional cargo module to swap when moving. An incompatible swap moves the fitted module into cargo.")
    else Text("An existing module or displaced ammunition returns to cargo. Module replacements retain supported state and charges.")
    Text("${model.positions.size} fitting positions selected", modifier = Modifier.testTag("transfers-selected-count"))
    val cargo = details.cargo.cargo.find { it.id == model.cargoId }
    Text(if (cargo == null) (if (toCargo) "No swap target" else "Choose a cargo stack")
        else "Cargo: ${cargo.name} × ${cargo.amount}", modifier = Modifier.testTag("transfers-cargo-selection"))
    val canSubmit = enabled && model.positions.isNotEmpty() && (toCargo || cargo != null)
    Row {
        Button(onClick = { model.submit(context, false) }, enabled = canSubmit,
            modifier = Modifier.testTag("transfers-move")) { Text(if (toCargo) "Move to cargo" else "Move to fit") }
        TextButton(onClick = { model.submit(context, true) }, enabled = canSubmit,
            modifier = Modifier.testTag("transfers-copy")) { Text(if (toCargo) "Copy to cargo" else "Copy to fit") }
    }
    Text(if (toCargo) "Fitted modules" else "Destination position", style = MaterialTheme.typography.titleMedium)
    if (toCargo) Row {
        TextButton(onClick = { model.positions = details.modules.filter { it.id != null }.map { it.index }.toSet() },
            enabled = enabled, modifier = Modifier.testTag("transfers-select-all")) { Text("Select all fitted") }
        TextButton(onClick = { model.positions = emptySet() }, enabled = enabled,
            modifier = Modifier.testTag("transfers-clear")) { Text("Clear") }
    }
    details.modules.filter { !toCargo || it.id != null }.forEach { module ->
        Card(Modifier.fillMaxWidth()) {
            Row(Modifier.padding(12.dp)) {
                Checkbox(module.index in model.positions, onCheckedChange = { model.toggle(module.index) },
                    enabled = enabled, modifier = Modifier.testTag("transfers-position-${module.index}"))
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("${module.index + 1} · ${module.slot.lowercase()} · ${module.name ?: "Empty slot"}")
                    if (module.id != null) Text(module.state.name.lowercase())
                    module.charge?.let { Text("$it × ${module.chargeAmount}") }
                    if (module.legal == false) Text("Fitting restriction", color = MaterialTheme.colorScheme.error)
                }
            }
        }
    }
    if (toCargo && details.modules.none { it.id != null }) Text("No fitted modules.")
    Text(if (toCargo) "Optional swap target" else "Cargo stack", style = MaterialTheme.typography.titleMedium)
    if (toCargo) TextButton(onClick = { model.cargoId = null }, enabled = enabled,
        modifier = Modifier.testTag("transfers-no-target")) { Text("No swap target") }
    details.cargo.cargo.forEach { stack ->
        Row {
            RadioButton(model.cargoId == stack.id, onClick = { model.cargoId = stack.id }, enabled = enabled,
                modifier = Modifier.testTag("transfers-stack-${stack.id}"))
            Text("${stack.name} × ${stack.amount}", Modifier.padding(top = 12.dp))
        }
    }
    if (details.cargo.cargo.isEmpty()) Text("Cargo is empty.")
}
