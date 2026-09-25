package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
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
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

class ModuleEditorModel : ViewModel() {
    var details by mutableStateOf<FittingDetails?>(null)
    var vacancyOptions by mutableStateOf<CloneVacancyOptions?>(null)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var message by mutableStateOf<String?>(null)
    var error by mutableStateOf<String?>(null)
    var replacePosition by mutableStateOf<Int?>(null)
    var rack by mutableStateOf(ModuleSlot.HIGH)
    var showSkills by mutableStateOf(false)
    var confirmRestrictions by mutableStateOf(false)
    var selectedForClone by mutableStateOf<Set<Int>>(emptySet())
    var cloneSource by mutableStateOf<Int?>(null)
    private var requested: Pair<String, Long>? = null
    private var generation = 0

    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested?.first != fit.id) {
            details = null; vacancyOptions = null; replacePosition = null; confirmRestrictions = false; message = null; error = null
            selectedForClone = emptySet()
            cloneSource = null
        }
        requested = next
        val token = ++generation
        loading = true
        EngineRuntime.fittingDetails(context, fit.id)
            .thenCombine(EngineRuntime.cloneVacancyOptions(context, fit.id)) { value, vacant -> value to vacant }
            .whenCompleteAsync({ result, failure ->
            if (token == generation) {
                loading = false
                if (failure == null) {
                    val (value, vacant) = result
                    if (details?.revision != value.revision) {
                        selectedForClone = emptySet()
                        cloneSource = null
                    }
                    details = value
                    vacancyOptions = vacant
                }
                else { details = null; vacancyOptions = null; error = "Fitting details could not be loaded. Try again." }
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun submit(context: Context, operation: BridgeOperation) {
        val before = details ?: return
        if (loading || editing) return
        editing = true; error = null; message = null
        EngineRuntime.request(context, operation, mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (failure != null) error = "The fitting engine could not confirm the edit. Restart the app."
            else if (!result.isSuccess) error = result.error?.message
            else {
                message = "Fit saved."
                replacePosition = null
            }
            EngineRuntime.library.value.find { it.id == before.fitId }?.let { load(context, it, retry = true) }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun ModuleEditor(model: ModuleEditorModel, onBrowse: () -> Unit, onBack: () -> Unit, onCharges: (Int) -> Unit, onVariations: (Int) -> Unit, onArrange: () -> Unit, onBulk: () -> Unit, onBulkStates: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Fit modules", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("modules-back")) { Text("Back to library") }
    if (fit == null) { Text("Open a fit in the library to edit its modules."); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text(fit.name, style = MaterialTheme.typography.titleLarge)
    Text(fit.ship)
    TextButton(onClick = onBulk, modifier = Modifier.testTag("modules-bulk")) { Text("Change ammunition together") }
    TextButton(onClick = onBulkStates, modifier = Modifier.testTag("modules-bulk-states")) { Text("Change module states together") }
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("modules-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("modules-saved")) }
    if (model.loading) Text("Loading fitting details…")
    val details = model.details?.takeIf { it.fitId == fit.id } ?: run {
        if (!model.loading) Button(onClick = { model.load(context, fit, retry = true) }) { Text("Retry") }
        return
    }
    val enabled = !model.loading && !model.editing && details.revision == fit.revision &&
        model.vacancyOptions?.revision == fit.revision &&
        (state as? EngineState.Ready)?.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
    if (model.editing) Text("Saving fit…")
    Card(Modifier.fillMaxWidth().testTag("modules-resources")) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            for ((key, label) in listOf("cpu" to "CPU", "powergrid" to "Powergrid", "calibration" to "Calibration")) {
                val resource = details.resources.getValue(key)
                Text("$label: ${formatStat(Stat(resource.used, "")).trim()} / ${formatStat(Stat(resource.total, resource.unit))}" +
                    if (resource.overloaded) " · Overloaded" else "",
                    color = if (resource.overloaded) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.testTag("modules-resource-$key"))
            }
            for (hardpoint in details.hardpoints) Text(
                "${if (hardpoint.kind == "TURRET") "Turrets" else "Launchers"}: ${hardpoint.used} / ${formatStat(Stat(hardpoint.total, "")).trim()}")
            Text("Resource and skill warnings do not prevent saving.", style = MaterialTheme.typography.bodySmall)
        }
    }
    Text(if (details.ignoreRestrictions) "Fitting restrictions overridden" else "Fitting restrictions enforced",
        modifier = Modifier.testTag("modules-restrictions-state"))
    TextButton(onClick = { model.confirmRestrictions = true }, enabled = enabled,
        modifier = Modifier.testTag("modules-restrictions")) {
        Text(if (details.ignoreRestrictions) "Re-enable restrictions" else "Override restrictions")
    }
    if (model.confirmRestrictions) AlertDialog(
        onDismissRequest = { model.confirmRestrictions = false },
        title = { Text(if (details.ignoreRestrictions) "Re-enable fitting restrictions?" else "Override fitting restrictions?") },
        text = { Text(if (details.ignoreRestrictions)
            "Modules incompatible with this hull, rig size or group limits will be removed. Excess hardpoints remain fitted with a warning."
            else "Allow modules beyond hull, rig-size, group and hardpoint restrictions. Slot limits still apply.") },
        confirmButton = { Button(onClick = {
            model.confirmRestrictions = false
            model.submit(context, BridgeOperation.SetFitRestrictions(fit.id, !details.ignoreRestrictions))
        }, enabled = enabled, modifier = Modifier.testTag("modules-restrictions-confirm")) { Text("Apply") } },
        dismissButton = { TextButton(onClick = { model.confirmRestrictions = false }) { Text("Cancel") } },
    )
    if (details.skillWarnings.isNotEmpty()) {
        TextButton(onClick = { model.showSkills = !model.showSkills }, modifier = Modifier.testTag("modules-skills")) {
            Text("Missing skills for ${details.skillWarnings.size} items${if (model.showSkills) " · Hide" else " · Show"}")
        }
        if (model.showSkills) for (warning in details.skillWarnings) {
            Text(warning.name, style = MaterialTheme.typography.titleSmall)
            SkillRequirements(warning.requirements)
        }
    }
    Button(onClick = { model.replacePosition = null; onBrowse() }, enabled = enabled,
        modifier = Modifier.testTag("modules-add")) { Text("Add equipment") }
    val vacancies = model.vacancyOptions?.vacancies.orEmpty()
    model.cloneSource?.let { index ->
        val source = details.modules.getOrNull(index)
        if (source?.id != null) Text("Clone source: " + source.name + " · choose a vacant " +
            source.slot.label.lowercase() + " position below.")
    }
    val available = vacancies.groupBy { it.slot }.mapValues { (_, rows) -> rows.map { it.index }.toMutableList() }
    val cloneTargets = model.selectedForClone.sorted().mapNotNull { index ->
        val source = details.modules.getOrNull(index) ?: return@mapNotNull null
        val destination = available[source.slot]?.removeFirstOrNull() ?: return@mapNotNull null
        source to destination
    }
    Card(Modifier.fillMaxWidth().testTag("modules-clone-preview")) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Clone selected modules", style = MaterialTheme.typography.titleMedium)
            Text(model.selectedForClone.size.toString() + " selected · " + vacancies.size + " vacant slots")
            for ((source, destination) in cloneTargets)
                Text((source.index + 1).toString() + " · " + source.name + " → vacancy " + (destination + 1))
            if (model.selectedForClone.isNotEmpty() && cloneTargets.size != model.selectedForClone.size)
                Text("Not enough vacant slots in the selected racks.")
            Text("EOS checks each clone in order. The whole action is rejected if any clone is illegal.",
                style = MaterialTheme.typography.bodySmall)
            Button(onClick = { model.submit(context,
                BridgeOperation.CloneSelectedModules(fit.id, model.selectedForClone.sorted())) },
                enabled = enabled && model.selectedForClone.isNotEmpty() &&
                    cloneTargets.size == model.selectedForClone.size,
                modifier = Modifier.testTag("modules-clone-selected")) { Text("Clone selected once each") }
        }
    }
    TextButton(onClick = onArrange, enabled = enabled, modifier = Modifier.testTag("modules-arrange")) { Text("Arrange rack and view heat") }
    for (row in ModuleSlot.entries.chunked(3)) Row {
        for (slot in row) TextButton(onClick = { model.rack = slot }, modifier = Modifier.weight(1f).testTag("modules-rack-${slot.name}")) {
            Text(slot.label + if (slot == model.rack) " ✓" else "")
        }
    }
    if (!model.rack.editable) {
        Text("Subsystem editing is not available yet. Existing positions are retained.")
        return
    }
    val rack = details.slots.single { it.slot == model.rack }
    Text("${rack.slot.label} slots: ${rack.used} / ${formatStat(Stat(rack.total, "")).trim()}",
        modifier = Modifier.testTag("modules-rack-count"))
    val modules = details.modules.filter { it.slot == model.rack }
    if (modules.isEmpty()) Text("No fitted modules in this rack. Choose Add equipment or clone a fitted source.")
    for ((rackIndex, module) in modules.withIndex()) Card(Modifier.fillMaxWidth().testTag("module-${module.index}")) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("${module.slot.label} ${rackIndex + 1} · ${module.name ?: "Empty slot"}", style = MaterialTheme.typography.titleMedium)
            if (module.id != null) {
                Text(module.state.name.lowercase().replaceFirstChar { it.uppercase() })
                module.charge?.let { Text(it) }
                if (module.overridden) Text("Fitting restriction overridden", color = MaterialTheme.colorScheme.error)
                if (module.legal == false) Text("Exceeds a fitting restriction", color = MaterialTheme.colorScheme.error)
            }
            if (module.id != null) Row {
                Checkbox(checked = module.index in model.selectedForClone, onCheckedChange = { checked ->
                    model.selectedForClone = if (checked) model.selectedForClone + module.index
                        else model.selectedForClone - module.index
                }, enabled = enabled, modifier = Modifier.testTag("module-clone-select-" + module.index))
                Text("Select for cloning", modifier = Modifier.padding(top = 12.dp))
            }
            if (module.id != null) {
                val free = vacancies.count { it.slot == module.slot }
                TextButton(onClick = { model.cloneSource = module.index }, enabled = enabled && free > 0,
                    modifier = Modifier.testTag("module-clone-source-" + module.index)) {
                    Text(if (model.cloneSource == module.index) "Clone source ✓" else "Choose as clone source")
                }
                TextButton(onClick = { model.submit(context, BridgeOperation.FillModulesClone(fit.id, module.index)) },
                    enabled = enabled && free > 0, modifier = Modifier.testTag("module-fill-clone-" + module.index)) {
                    Text("Fill up to " + free + " vacant " + module.slot.label.lowercase() + " slots from this module")
                }
                Text("Copies retain state and charge. EOS may stop earlier; recent market use is unchanged.",
                    style = MaterialTheme.typography.bodySmall)
            }
            if (module.id == null && model.cloneSource?.let { details.modules.getOrNull(it)?.slot == module.slot } == true)
                TextButton(onClick = { model.submit(context,
                    BridgeOperation.CloneModuleAt(fit.id, checkNotNull(model.cloneSource), module.index)) },
                    enabled = enabled, modifier = Modifier.testTag("module-clone-here-" + module.index)) {
                    Text("Clone into this vacancy")
                }
            Row {
                TextButton(onClick = { model.replacePosition = module.index; onBrowse() }, enabled = enabled,
                    modifier = Modifier.testTag("module-replace-${module.index}")) { Text(if (module.id == null) "Fit here" else "Replace") }
                if (module.id != null) TextButton(onClick = {
                    model.submit(context, BridgeOperation.RemoveModule(fit.id, module.index))
                }, enabled = enabled, modifier = Modifier.testTag("module-remove-${module.index}")) { Text("Remove") }
            }
            if (module.id != null) TextButton(onClick = { onCharges(module.index) }, enabled = enabled,
                modifier = Modifier.testTag("module-charges-${module.index}")) { Text("Charges") }
            if (module.id != null) TextButton(onClick = { onVariations(module.index) }, enabled = enabled,
                modifier = Modifier.testTag("module-variations-${module.index}")) { Text("Variations") }
        }
    }
    for (vacancy in vacancies.filter { it.slot == model.rack && it.index >= details.modules.size })
        Card(Modifier.fillMaxWidth().testTag("module-virtual-" + vacancy.index)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(model.rack.label + " empty slot", style = MaterialTheme.typography.titleMedium)
                Text("This vacancy is materialized when a fitting edit is saved.")
                if (model.cloneSource?.let { details.modules.getOrNull(it)?.slot == vacancy.slot } == true)
                    TextButton(onClick = { model.submit(context, BridgeOperation.CloneModuleAt(
                        fit.id, checkNotNull(model.cloneSource), vacancy.index)) },
                        enabled = enabled, modifier = Modifier.testTag("module-clone-here-" + vacancy.index)) {
                        Text("Clone into this vacancy")
                    }
            }
        }
}

@Composable
private fun SkillRequirements(rows: List<SkillRequirement>) {
    Column(Modifier.padding(start = 12.dp)) {
        for (row in rows) {
            Text("${row.name}: needs ${row.required}, current ${row.actual}", style = MaterialTheme.typography.bodySmall)
            if (row.requirements.isNotEmpty()) SkillRequirements(row.requirements)
        }
    }
}

@Composable
internal fun EquipmentFittingActions(model: ModuleEditorModel, item: EquipmentItem, onViewFit: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    if (fit == null) { Text("Open a fit in the library to add equipment."); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("Fitting to ${fit.name}")
    val details = model.details?.takeIf { it.fitId == fit.id && it.revision == fit.revision }
    var fillOptions by remember(fit.id, fit.revision, item.id) { mutableStateOf<FillItemOptions?>(null) }
    var fillUnavailable by remember(fit.id, fit.revision, item.id) { mutableStateOf(false) }
    LaunchedEffect(fit.id, fit.revision, item.id) {
        if (item.category in setOf("Module", "Structure Module")) {
            EngineRuntime.fillItemOptions(context, fit.id, item.id).whenCompleteAsync({ value, failure ->
                if (failure == null) fillOptions = value else fillUnavailable = true
            }, ContextCompat.getMainExecutor(context))
        }
    }
    val position = model.replacePosition
    val target = position?.let { details?.modules?.getOrNull(it) }
    if (target != null) Text("Replace ${target.name ?: "empty ${target.slot.label.lowercase()} slot"}")
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("equipment-fit-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("equipment-fit-saved")) }
    if (item.category in setOf("Module", "Structure Module")) Button(onClick = {
        model.submit(context, if (position == null) BridgeOperation.AddModule(fit.id, item.id)
            else BridgeOperation.ReplaceModule(fit.id, position, item.id))
    }, enabled = details != null && !model.loading && !model.editing &&
        (state as? EngineState.Ready)?.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE,
        modifier = Modifier.testTag("equipment-fit")) { Text(if (position == null) "Add to fit" else "Replace in fit") }
    if (position == null && item.category in setOf("Module", "Structure Module")) {
        Text(fillOptions?.let { "Up to " + it.vacancies + " vacant " + it.slot.label.lowercase() +
            " slots; EOS may stop earlier." } ?: if (fillUnavailable) "Slot preview unavailable for this item."
            else "Checking vacant slots…", modifier = Modifier.testTag("equipment-fill-preview"))
        Text("A failed market attempt still enters recent use.",
            style = MaterialTheme.typography.bodySmall)
        Button(onClick = { model.submit(context, BridgeOperation.FillModulesItem(fit.id, item.id)) },
            enabled = details != null && !model.loading && !model.editing &&
                (state as? EngineState.Ready)?.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE,
            modifier = Modifier.testTag("equipment-fill")) { Text("Fill free slots with this item") }
    }
    TextButton(onClick = onViewFit, modifier = Modifier.testTag("equipment-view-fit")) { Text("View fitting") }
}
