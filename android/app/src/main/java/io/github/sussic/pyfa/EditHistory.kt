package io.github.sussic.pyfa

import android.content.Context
import androidx.compose.foundation.layout.Row
import androidx.compose.material3.Button
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
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

data class EditHistory(val fitId: String, val revision: Long, val undoCount: Int, val redoCount: Int,
    val limit: Int, val undoLabel: String?, val redoLabel: String?)

class EditHistoryModel : ViewModel() {
    var options by mutableStateOf<EditHistory?>(null)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    private var requested: Pair<String, Long>? = null
    private var generation = 0

    fun load(context: Context, fit: FitSnapshot?, retry: Boolean = false) {
        val key = fit?.let { it.id to it.revision }
        if (!retry && requested == key) return
        if (requested?.first != key?.first) { error = null; message = null }
        requested = key; options = null
        val token = ++generation
        loading = fit != null
        if (fit == null) return
        EngineRuntime.editHistory(context, fit.id).whenCompleteAsync({ value, failure ->
            if (generation == token) {
                loading = false
                if (failure == null) { options = value; error = null }
                else error = "Edit history could not be loaded. Retry to check available actions."
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun apply(context: Context, redo: Boolean) {
        val before = options ?: return
        if (loading || editing || (if (redo) before.redoCount else before.undoCount) == 0) return
        val label = if (redo) before.redoLabel else before.undoLabel
        editing = true; error = null; message = null
        val operation = if (redo) BridgeOperation.Redo(before.fitId) else BridgeOperation.Undo(before.fitId)
        EngineRuntime.request(context, operation, mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            val fit = (EngineRuntime.state.value as? EngineState.Ready)?.fit
            if (fit?.id == before.fitId) {
                if (failure != null) error = "The history action could not be confirmed. Reopen the app to check the saved fit."
                else if (!result.isSuccess) error = result.error?.message ?: "The history action could not be saved."
                else {
                    message = "${if (redo) "Redid" else "Undid"}: $label. Select modules again if needed."
                    load(context, fit)
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun EditHistoryControls(model: EditHistoryModel) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    LaunchedEffect(fit?.id, fit?.revision) { model.load(context, fit) }
    if (fit == null) return
    val value = model.options
    Text("Recent edits · ${fit.name}", modifier = Modifier.testTag("history-fit"))
    Row {
        Button(onClick = { model.apply(context, false) }, enabled = !model.loading && !model.editing && (value?.undoCount ?: 0) > 0,
            modifier = Modifier.testTag("history-undo")) { Text("Undo") }
        TextButton(onClick = { model.apply(context, true) }, enabled = !model.loading && !model.editing && (value?.redoCount ?: 0) > 0,
            modifier = Modifier.testTag("history-redo")) { Text("Redo") }
    }
    if (model.loading) Text("Loading edit history…", modifier = Modifier.testTag("history-loading"))
    else if (model.editing) Text("Saving history action…", modifier = Modifier.testTag("history-saving"))
    else if (value != null) {
        Text(value.undoLabel?.let { "Undo: $it" } ?: "No undo action", modifier = Modifier.testTag("history-next-undo"))
        value.redoLabel?.let { Text("Redo: $it", modifier = Modifier.testTag("history-next-redo")) }
    }
    model.message?.let { Text(it, modifier = Modifier.testTag("history-message")) }
    model.error?.let {
        Text(it, modifier = Modifier.testTag("history-error"))
        TextButton(onClick = { model.load(context, fit, retry = true) }, enabled = !model.editing && !model.loading,
            modifier = Modifier.testTag("history-retry")) { Text("Reload history") }
    }
}
