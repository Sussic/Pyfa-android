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

class ModeEditorModel : ViewModel() {
    var options by mutableStateOf<ModeOptions?>(null)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    private var requested: Pair<String, Long>? = null
    private var generation = 0

    fun open() {
        ++generation; requested = null; loading = false
        options = null; error = null; message = null
    }

    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        if (requested?.first != fit.id) { options = null; message = null }
        requested = next
        val token = ++generation
        loading = true
        EngineRuntime.modeOptions(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) { options = null; error = "Hull modes could not be loaded. Try again." }
                else { options = value; error = null }
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun change(context: Context, choice: HullModeChoice) {
        val before = options ?: return
        if (loading || editing || before.current == choice.id || choice !in before.choices) return
        editing = true; error = null; message = null
        EngineRuntime.request(context, BridgeOperation.ChangeMode(before.fitId, choice.id),
            mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (requested?.first == before.fitId) {
                if (failure != null) error = "The fitting engine could not confirm the edit. Restart the app."
                else if (!result.isSuccess) error = result.error?.message
                else message = "${choice.name} applied. Fit saved."
                EngineRuntime.library.value.find { it.id == before.fitId }?.let { load(context, it, retry = true) }
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun ModeEditor(model: ModeEditorModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Hull modes", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("modes-back")) { Text("Back") }
    if (fit == null) {
        Text("Open a fit to view its hull modes.", modifier = Modifier.testTag("modes-no-fit"))
        return
    }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("modes-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("modes-saved")) }
    if (model.loading) Text("Loading modes…", modifier = Modifier.testTag("modes-loading"))
    val options = model.options?.takeIf { it.fitId == fit.id && it.revision == fit.revision }
    if (options == null) return
    if (options.choices.isEmpty()) {
        Text("This hull has no selectable modes.", modifier = Modifier.testTag("modes-empty"))
        return
    }
    Text("Current: ${options.choices.single { it.id == options.current }.name}",
        modifier = Modifier.testTag("modes-current"))
    Text("Choose a mode to recalculate this fit and its linked effects.")
    for (choice in options.choices) {
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(choice.name, style = MaterialTheme.typography.titleMedium)
                Button(onClick = { model.change(context, choice) },
                    enabled = !model.loading && !model.editing && choice.id != options.current,
                    modifier = Modifier.testTag("modes-choice-${choice.id}")) {
                    Text(if (choice.id == options.current) "Current mode" else "Use this mode")
                }
            }
        }
    }
}
