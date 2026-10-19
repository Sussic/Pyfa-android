package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

internal val droneMetricUnits = mapOf(
    "hp_shield" to "HP",
    "hp_armor" to "HP",
    "hp_hull" to "HP",
    "ehp_shield" to "EHP",
    "ehp_armor" to "EHP",
    "ehp_hull" to "EHP",
    "shield_regen" to "HP/s",
    "effective_shield_regen" to "EHP/s",
    "dps_em" to "HP/s",
    "dps_thermal" to "HP/s",
    "dps_kinetic" to "HP/s",
    "dps_explosive" to "HP/s",
    "dps_total" to "HP/s",
    "volley_em" to "HP",
    "volley_thermal" to "HP",
    "volley_kinetic" to "HP",
    "volley_explosive" to "HP",
    "volley_total" to "HP",
    "mining_yield" to "m3/s",
    "mining_drain" to "m3/s",
    "remote_shield" to "HP/s",
    "remote_armor" to "HP/s",
    "remote_hull" to "HP/s",
    "remote_capacitor" to "GJ/s",
    "range" to "m",
    "falloff" to "m",
    "volume" to "m3",
    "droneBandwidthUsed" to "Mbit/s",
    "trackingSpeed" to "rad/s",
    "maxVelocity" to "m/s",
    "signatureRadius" to "m",
    "duration" to "ms",
    "ECMDuration" to "ms",
    "energyNeutralizerDuration" to "ms",
    "accessDifficultyBonus" to "%",
    "scanGravimetricStrengthBonus" to "points",
    "scanLadarStrengthBonus" to "points",
    "scanMagnetometricStrengthBonus" to "points",
    "scanRadarStrengthBonus" to "points",
    "speedFactor" to "%",
    "signatureRadiusBonus" to "%",
    "trackingSpeedBonus" to "%",
    "maxRangeBonus" to "%",
    "falloffBonus" to "%",
    "scanResolutionBonus" to "%",
    "maxTargetRangeBonus" to "%",
    "energyNeutralizerAmount" to "GJ",
)

data class DroneMetric(val key: String, val label: String, val unit: String, val value: Double?, val text: String?)
data class DroneRoll(val attributeId: Int, val value: Double)
data class DroneMutation(val baseItemId: Int, val baseName: String, val mutaplasmidId: Int,
    val mutaplasmidName: String, val rolls: List<DroneRoll>)
data class DroneStack(val index: Int, val objectKey: String, val itemId: Int, val name: String,
    val group: String, val amount: Int, val active: Int, val mutation: DroneMutation?, val metrics: List<DroneMetric>)
data class DroneDetails(val fitId: String, val revision: Long, val active: Long, val activeLimit: Double,
    val bayUsed: Double, val bayCapacity: Double?, val bandwidthUsed: Double, val bandwidthCapacity: Double?,
    val stacks: List<DroneStack>)

class DroneEditorModel : ViewModel() {
    var details by mutableStateOf<DroneDetails?>(null); private set
    var loading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var selected by mutableStateOf<Set<String>>(emptySet())
    var expanded by mutableStateOf<Set<String>>(emptySet())
    val amounts = mutableStateMapOf<String, String>()
    val splitAmounts = mutableStateMapOf<String, String>()
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    fun open() {
        ++generation; requested = null; details = null; loading = false
        selected = emptySet(); expanded = emptySet(); amounts.clear(); splitAmounts.clear(); error = null; message = null
    }
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && next == requested) return
        if (requested?.first != fit.id) { selected = emptySet(); expanded = emptySet(); message = null }
        requested = next; details = null; loading = true
        val token = ++generation
        EngineRuntime.droneDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Drone details could not be loaded. Try again."
                else {
                    details = value; error = null; amounts.clear(); splitAmounts.clear()
                    val keys = value.stacks.map { it.objectKey }.toSet()
                    selected = selected.intersect(keys); expanded = expanded.intersect(keys)
                    value.stacks.forEach { amounts[it.objectKey] = it.amount.toString(); splitAmounts[it.objectKey] = (it.amount / 2).coerceAtLeast(1).toString() }
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun add(context: Context, item: EquipmentItem, stack: Boolean, onSaved: () -> Unit) {
        val fit = (EngineRuntime.state.value as? EngineState.Ready)?.fit ?: return
        submit(context, fit.id, fit.revision,
            if (stack) BridgeOperation.AddDroneStack(fit.id, item.id) else BridgeOperation.AddDrone(fit.id, item.id, 1), onSaved)
    }
    fun setAmount(context: Context, stack: DroneStack) {
        val d = details ?: return
        val amount = amounts[stack.objectKey]?.trim()?.toIntOrNull()
        if (amount == null || amount < 0) { error = "Enter a whole-number quantity, or zero to remove."; return }
        if (amount == stack.amount) return
        submit(context, d.fitId, d.revision, BridgeOperation.SetDroneAmount(d.fitId, stack.index, amount))
    }
    fun toggle(context: Context, main: DroneStack) {
        val d = details ?: return
        submit(context, d.fitId, d.revision, BridgeOperation.ToggleDrones(d.fitId, main.index,
            d.stacks.filter { it.objectKey in selected }.map { it.index }))
    }
    fun remove(context: Context, stacks: List<DroneStack>, all: Boolean) {
        val d = details ?: return
        submit(context, d.fitId, d.revision,
            BridgeOperation.RemoveDrones(d.fitId, stacks.map { it.index }, if (all) Int.MAX_VALUE else 1))
    }
    fun clone(context: Context, stack: DroneStack) {
        val d = details ?: return
        submit(context, d.fitId, d.revision, BridgeOperation.CloneDrone(d.fitId, stack.index))
    }
    fun split(context: Context, stack: DroneStack) {
        val d = details ?: return
        val amount = splitAmounts[stack.objectKey]?.trim()?.toIntOrNull()
        if (amount == null || amount < 1 || amount >= stack.amount) { error = "Split a whole-number quantity smaller than the stack."; return }
        submit(context, d.fitId, d.revision, BridgeOperation.SplitDrone(d.fitId, stack.index, amount))
    }
    fun merge(context: Context, source: DroneStack, destination: DroneStack) {
        val d = details ?: return
        submit(context, d.fitId, d.revision, BridgeOperation.MergeDrones(d.fitId, source.index, destination.index))
    }
    private fun submit(context: Context, fitId: String, revision: Long, operation: BridgeOperation,
        onSaved: () -> Unit = {}) {
        if (editing || loading) return
        editing = true; error = null; message = null
        val token = generation
        EngineRuntime.request(context, operation, mapOf(fitId to revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (token == generation) {
                if (failure != null) error = "The engine could not confirm the drone edit. Restart the app."
                else if (!result.isSuccess) error = result.error?.message
                else {
                    message = "Drone changes saved."; onSaved()
                    EngineRuntime.library.value.find { it.id == fitId }?.let { load(context, it, retry = true) }
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun DroneEditor(model: DroneEditorModel, onBrowse: () -> Unit, onBack: () -> Unit,
    onVariations: (Int) -> Unit, onInspect: () -> Unit) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Drones", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("drones-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to manage its drones."); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("drones-error")) }
    model.message?.let { Text(it, Modifier.testTag("drones-saved")) }
    if (model.loading) Text("Loading drones.", Modifier.testTag("drones-loading"))
    val d = model.details?.takeIf { it.fitId == fit.id && it.revision == fit.revision }
    if (d == null) {
        if (!model.loading) Button(onClick = { model.load(context, fit, true) }, Modifier.testTag("drones-retry")) { Text("Retry") }
        return
    }
    Text("Active: ${d.active} / ${d.activeLimit}", Modifier.testTag("drones-active"))
    Text("Bay: ${d.bayUsed} / ${d.bayCapacity ?: "Unavailable"} m³", Modifier.testTag("drones-bay"))
    Text("Bandwidth: ${d.bandwidthUsed} / ${d.bandwidthCapacity ?: "Unavailable"} Mbit/s", Modifier.testTag("drones-bandwidth"))
    if (d.active > d.activeLimit || d.bayCapacity?.let { d.bayUsed > it } == true ||
        d.bandwidthCapacity?.let { d.bandwidthUsed > it } == true)
        Text("Drone resources exceeded", color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("drones-over-limit"))
    TextButton(onClick = onBrowse, modifier = Modifier.testTag("drones-browse")) { Text("Browse drones to add") }
    TextButton(onClick = onInspect, modifier = Modifier.testTag("drones-inspect")) { Text("All fitted item attributes and affectors") }
    val available = !model.editing && !model.loading
    val selected = d.stacks.filter { it.objectKey in model.selected }
    Row {
        TextButton(onClick = { model.selected = d.stacks.map { it.objectKey }.toSet() }, enabled = available,
            modifier = Modifier.testTag("drones-select-all")) { Text("Select all") }
        TextButton(onClick = { model.selected = emptySet() }, enabled = available,
            modifier = Modifier.testTag("drones-clear-selection")) { Text("Clear selection") }
    }
    selected.firstOrNull()?.let { main ->
        Button(onClick = { focus.clearFocus(); model.toggle(context, main) }, enabled = available,
            modifier = Modifier.testTag("drones-toggle-selected")) {
            Text(if (main.active > 0) "Deactivate selected" else "Activate selected")
        }
        TextButton(onClick = { focus.clearFocus(); model.remove(context, selected, true) }, enabled = available,
            modifier = Modifier.testTag("drones-remove-selected")) { Text("Remove selected stacks") }
    }
    if (selected.size == 2) {
        val destination = selected[0]; val source = selected[1]
        val compatible = source.itemId == destination.itemId && source.mutation == destination.mutation
        TextButton(onClick = { focus.clearFocus(); model.merge(context, source, destination) },
            enabled = available && compatible, modifier = Modifier.testTag("drones-merge-selected")) { Text("Merge selected into upper stack") }
        if (!compatible) Text("Only identical drone types and mutation rolls can merge.")
    }
    if (d.stacks.isEmpty()) Text("No drones in this fit.", Modifier.testTag("drones-empty"))
    for (stack in d.stacks) key(stack.objectKey) {
        Card(Modifier.fillMaxWidth().testTag("drone-${stack.index}")) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row {
                    Checkbox(checked = stack.objectKey in model.selected, onCheckedChange = { checked ->
                        model.selected = if (checked) model.selected + stack.objectKey else model.selected - stack.objectKey
                    }, enabled = available, modifier = Modifier.testTag("drone-${stack.index}-select"))
                    Text(stack.name, style = MaterialTheme.typography.titleMedium)
                }
                Text("${stack.group} · Stored ${stack.amount} · Active ${stack.active}")
                stack.mutation?.let { Text("${it.baseName} · ${it.mutaplasmidName}") }
                OutlinedTextField(value = model.amounts[stack.objectKey] ?: stack.amount.toString(),
                    onValueChange = { model.amounts[stack.objectKey] = it }, enabled = available,
                    label = { Text("Stored quantity") }, singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth().testTag("drone-${stack.index}-amount"))
                Row {
                    TextButton(onClick = { focus.clearFocus(); model.setAmount(context, stack) }, enabled = available,
                        modifier = Modifier.testTag("drone-${stack.index}-save")) { Text("Save quantity") }
                    TextButton(onClick = { model.toggle(context, stack) }, enabled = available,
                        modifier = Modifier.testTag("drone-${stack.index}-toggle")) { Text(if (stack.active > 0) "Deactivate" else "Activate") }
                }
                Row {
                    TextButton(onClick = { model.remove(context, listOf(stack), false) }, enabled = available,
                        modifier = Modifier.testTag("drone-${stack.index}-remove-one")) { Text("Remove one") }
                    TextButton(onClick = { model.clone(context, stack) }, enabled = available,
                        modifier = Modifier.testTag("drone-${stack.index}-clone")) { Text("Clone stack") }
                }
                if (stack.amount > 1) {
                    OutlinedTextField(value = model.splitAmounts[stack.objectKey] ?: "1",
                        onValueChange = { model.splitAmounts[stack.objectKey] = it }, enabled = available,
                        label = { Text("Quantity to split") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.fillMaxWidth().testTag("drone-${stack.index}-split-amount"))
                    TextButton(onClick = { focus.clearFocus(); model.split(context, stack) }, enabled = available,
                        modifier = Modifier.testTag("drone-${stack.index}-split")) { Text("Split stack") }
                }
                if (stack.mutation == null) TextButton(onClick = { onVariations(stack.index) }, enabled = available,
                    modifier = Modifier.testTag("drone-${stack.index}-variations")) { Text("Variations") }
                TextButton(onClick = {
                    model.expanded = if (stack.objectKey in model.expanded) model.expanded - stack.objectKey else model.expanded + stack.objectKey
                }, modifier = Modifier.testTag("drone-${stack.index}-details")) { Text("Details") }
                if (stack.objectKey in model.expanded) {
                    Text("Health and shield regeneration are per drone. EHP uses the fit's incoming damage pattern.")
                    stack.metrics.forEach { metric ->
                        Text("${metric.label}: ${metric.text?.let { "$it ${metric.unit}" } ?: "Not applicable / unavailable"}",
                            Modifier.testTag("drone-${stack.index}-${metric.key}"))
                    }
                }
            }
        }
    }
}
