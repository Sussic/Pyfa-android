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

class SubsystemEditorModel : ViewModel() {
    var options by mutableStateOf<SubsystemOptions?>(null)
    var details by mutableStateOf<FittingDetails?>(null)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    private var requested: Pair<String, Long>? = null
    private var generation = 0

    fun open() {
        ++generation; requested = null; loading = false
        options = null; details = null; error = null; message = null
    }

    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested?.first != fit.id) { options = null; details = null; message = null }
        requested = next
        val token = ++generation
        loading = true
        EngineRuntime.subsystemOptions(context, fit.id)
            .thenCombine(EngineRuntime.fittingDetails(context, fit.id)) { choices, layout -> choices to layout }
            .whenCompleteAsync({ value, failure ->
                if (token == generation) {
                    loading = false
                    if (failure != null || value.first.revision != value.second.revision) {
                        options = null; details = null
                        error = "Subsystems could not be loaded. Try again."
                    } else { options = value.first; details = value.second; error = null }
                }
            }, ContextCompat.getMainExecutor(context))
    }

    fun change(context: Context, group: SubsystemGroup, choice: SubsystemChoice?) {
        val before = options ?: return
        if (loading || editing || before.groups.find { it.kind == group.kind } != group ||
            group.current == choice?.id || choice != null && choice !in group.choices) return
        editing = true; error = null; message = null
        EngineRuntime.request(context, BridgeOperation.SetSubsystem(before.fitId, group.kind, choice?.id),
            mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (requested?.first == before.fitId) {
                if (failure != null) error = "The fitting engine could not confirm the edit. Restart the app."
                else if (!result.isSuccess) error = result.error?.message
                else message = "${choice?.name ?: group.name + " subsystem removed"}. Fit saved."
                EngineRuntime.library.value.find { it.id == before.fitId }?.let { load(context, it, retry = true) }
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun SubsystemEditor(model: SubsystemEditorModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Strategic cruiser subsystems", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("subsystems-back")) { Text("Back") }
    if (fit == null) {
        Text("Open a fit to view its subsystems.", modifier = Modifier.testTag("subsystems-no-fit"))
        return
    }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error,
        modifier = Modifier.testTag("subsystems-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("subsystems-saved")) }
    if (model.loading) Text("Loading subsystems…", modifier = Modifier.testTag("subsystems-loading"))
    val options = model.options?.takeIf { it.fitId == fit.id && it.revision == fit.revision }
    val details = model.details?.takeIf { it.fitId == fit.id && it.revision == fit.revision }
    if (options == null || details == null) return
    if (options.groups.isEmpty()) {
        Text("This hull has no subsystem slots.", modifier = Modifier.testTag("subsystems-empty"))
        return
    }
    Text("Subsystems can change module slots, hardpoints and bonuses. Existing modules that no longer fit remain visible with a warning.")
    Text("Installed subsystems: ${options.groups.count { it.current != null }}/${options.capacity}",
        modifier = Modifier.testTag("subsystems-count"))
    Text(details.slots.filter { it.slot in setOf(ModuleSlot.HIGH, ModuleSlot.MED, ModuleSlot.LOW) }
        .joinToString(" · ") { slot ->
            val total = slot.total.numberOrNull()?.let { if (it % 1.0 == 0.0) it.toInt().toString() else it.toString() }
                ?: "Unavailable"
            "${slot.slot.label} ${slot.used}/$total"
        }, modifier = Modifier.testTag("subsystems-layout"))
    val invalid = details.modules.filter { it.legal == false }
    if (invalid.isNotEmpty()) {
        Text("No longer fits: " + invalid.joinToString { module ->
            module.name.orEmpty() + (module.charge?.let { " ($it)" } ?: "")
        }, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("subsystems-illegal"))
    }
    for (group in options.groups) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(group.name, style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.testTag("subsystem-group-${group.kind}"))
                Text("Current: " + (group.choices.find { it.id == group.current }?.name ?: "Empty"),
                    modifier = Modifier.testTag("subsystem-current-${group.kind}"))
                for (choice in group.choices) {
                    Button(onClick = { model.change(context, group, choice) },
                        enabled = !model.loading && !model.editing && choice.id != group.current,
                        modifier = Modifier.testTag("subsystem-choice-${choice.id}")) {
                        Text(if (choice.id == group.current) "Current" else "Use ${choice.name}")
                    }
                }
                if (group.current != null) TextButton(onClick = { model.change(context, group, null) },
                    enabled = !model.loading && !model.editing,
                    modifier = Modifier.testTag("subsystem-remove-${group.kind}")) {
                    Text("Remove ${group.name} subsystem")
                }
            }
        }
    }
}
