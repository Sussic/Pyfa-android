package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
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
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

class StructureServiceEditorModel : ViewModel() {
    var options by mutableStateOf<StructureServiceOptions?>(null)
    var details by mutableStateOf<FittingDetails?>(null)
    var targetPosition by mutableStateOf<Int?>(null)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    private var requested: Pair<String, Long>? = null
    private var generation = 0

    fun open() {
        ++generation; requested = null; loading = false; editing = false
        options = null; details = null; targetPosition = null; error = null; message = null
    }

    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested?.first != fit.id) {
            options = null; details = null; targetPosition = null; message = null
        }
        requested = next
        val token = ++generation
        loading = true
        EngineRuntime.structureServiceOptions(context, fit.id)
            .thenCombine(EngineRuntime.fittingDetails(context, fit.id)) { choices, layout -> choices to layout }
            .whenCompleteAsync({ value, failure ->
                if (token == generation) {
                    loading = false
                    if (failure != null || value.first.revision != value.second.revision) {
                        options = null; details = null
                        error = "Structure services could not be loaded. Try again."
                    } else {
                        options = value.first; details = value.second; error = null
                    }
                }
            }, ContextCompat.getMainExecutor(context))
    }

    fun chooseTarget(position: Int?) {
        if (loading || editing) return
        if (position != null && details?.modules?.none {
            it.index == position && it.slot == ModuleSlot.SERVICE && it.id != null
        } != false) return
        targetPosition = position
        error = null; message = null
    }

    fun fit(context: Context, choice: StructureServiceChoice) {
        val current = options ?: return
        val layout = details ?: return
        if (loading || editing || !current.isStructure || choice !in current.choices ||
            current.revision != layout.revision) return
        val target = targetPosition?.let { position ->
            layout.modules.firstOrNull { it.index == position && it.slot == ModuleSlot.SERVICE && it.id != null }
                ?: return
        }
        if (target?.id == choice.id || target == null &&
            layout.slots.single { it.slot == ModuleSlot.SERVICE }.used >= current.capacity) return
        val operation = if (target == null) BridgeOperation.AddModule(current.fitId, choice.id)
            else BridgeOperation.ReplaceModule(current.fitId, target.index, choice.id)
        submit(context, operation, current.fitId, current.revision, "${choice.name} fitted. Fit saved.")
    }

    fun remove(context: Context, position: Int) {
        val current = options ?: return
        val module = details?.modules?.firstOrNull {
            it.index == position && it.slot == ModuleSlot.SERVICE && it.id != null
        } ?: return
        if (loading || editing) return
        submit(context, BridgeOperation.RemoveModule(current.fitId, position), current.fitId,
            current.revision, "${module.name} removed. Fit saved.")
    }

    private fun submit(context: Context, operation: BridgeOperation, fitId: String,
                       revision: Long, saved: String) {
        editing = true; error = null; message = null
        EngineRuntime.request(context, operation, mapOf(fitId to revision))
            .whenCompleteAsync({ result, failure ->
                editing = false
                if (requested?.first == fitId) {
                    if (failure != null) error = "The fitting engine could not confirm the edit. Restart the app."
                    else if (!result.isSuccess) error = result.error?.message
                    else { message = saved; targetPosition = null }
                    EngineRuntime.library.value.find { it.id == fitId }?.let { load(context, it, retry = true) }
                }
            }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun StructureServiceEditor(model: StructureServiceEditorModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Structure services", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("services-back")) { Text("Back") }
    if (fit == null) {
        Text("Open a fit to view its services.", modifier = Modifier.testTag("services-no-fit"))
        return
    }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error,
        modifier = Modifier.testTag("services-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("services-saved")) }
    if (model.loading) Text("Loading structure services…", modifier = Modifier.testTag("services-loading"))
    val options = model.options?.takeIf { it.fitId == fit.id && it.revision == fit.revision }
    val details = model.details?.takeIf { it.fitId == fit.id && it.revision == fit.revision }
    if (options == null || details == null) return
    if (!options.isStructure) {
        Text("This hull is not a structure.", modifier = Modifier.testTag("services-not-structure"))
        return
    }
    val service = details.slots.single { it.slot == ModuleSlot.SERVICE }
    val hasVacancy = service.used < options.capacity
    Text("Service slots: ${service.used}/${options.capacity}", modifier = Modifier.testTag("services-count"))
    for ((name, label) in listOf("shield_hp" to "Shield HP", "armor_hp" to "Armor HP")) {
        fit.stats[name]?.let { Text("$label: ${formatStat(it)}", modifier = Modifier.testTag("services-$name")) }
    }
    Text("Choices are compatible with this structure. Slot, resource and group limits are checked when fitting.")
    TextButton(onClick = { model.chooseTarget(null) }, enabled = !model.loading && !model.editing && hasVacancy,
        modifier = Modifier.testTag("services-add-target")) {
        Text(if (!hasVacancy) "Service slots full; replace or remove a service"
            else if (model.targetPosition == null) "Add a service ✓" else "Add a service")
    }
    for (module in details.modules.filter { it.slot == ModuleSlot.SERVICE && it.id != null }) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(module.name ?: "Service", style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.testTag("services-current-${module.index}"))
                if (module.legal == false) Text("Exceeds a fitting restriction",
                    color = MaterialTheme.colorScheme.error)
                TextButton(onClick = { model.chooseTarget(module.index) },
                    enabled = !model.loading && !model.editing,
                    modifier = Modifier.testTag("services-replace-${module.index}")) {
                    Text(if (model.targetPosition == module.index) "Replacing this service ✓" else "Replace")
                }
                TextButton(onClick = { model.remove(context, module.index) },
                    enabled = !model.loading && !model.editing,
                    modifier = Modifier.testTag("services-remove-${module.index}")) { Text("Remove") }
            }
        }
    }
    Text(if (model.targetPosition != null) "Replace service"
        else if (hasVacancy) "Add service" else "Choose Replace or Remove above",
        style = MaterialTheme.typography.titleMedium, modifier = Modifier.testTag("services-action"))
    if (options.choices.isEmpty()) Text("No service modules are compatible with this structure.",
        modifier = Modifier.testTag("services-empty"))
    for (choice in options.choices) {
        val target = details.modules.firstOrNull { it.index == model.targetPosition }
        Button(onClick = { model.fit(context, choice) },
            enabled = !model.loading && !model.editing && target?.id != choice.id &&
                (target != null || hasVacancy),
            modifier = Modifier.testTag("service-choice-${choice.id}")) {
            Text(choice.name)
        }
    }
}
