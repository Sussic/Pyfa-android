package io.github.sussic.pyfa

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
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

class FitLibraryModel : ViewModel() {
    val search = mutableStateOf("")
    val action = mutableStateOf<String?>(null)
    val targetId = mutableStateOf<String?>(null)
    val targetRevision = mutableStateOf(0L)
    val name = mutableStateOf("")
    val example = mutableStateOf("Vexor")
    val busy = mutableStateOf(false)
    val error = mutableStateOf<String?>(null)
}

/** B03.1: saved-fit lifecycle. The engine publishes only confirmed committed inputs. */
@Composable
internal fun FitLibrary(model: FitLibraryModel) {
    val context = LocalContext.current
    val fits by EngineRuntime.library.collectAsState()
    val state by EngineRuntime.state.collectAsState()
    var search by model.search
    var action by model.action
    var targetId by model.targetId
    var targetRevision by model.targetRevision
    var name by model.name
    var example by model.example
    var busy by model.busy
    var error by model.error
    val selected = (state as? EngineState.Ready)?.fit
    val unavailable = (state as? EngineState.Ready)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ||
        (state as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE
    val enabled = !busy && !unavailable
    fun openDialog(kind: String, fit: FitSnapshot? = null) {
        action = kind
        targetId = fit?.id
        targetRevision = fit?.revision ?: 0
        name = if (kind == "Duplicate") "${fit?.name?.take(190)} copy" else fit?.name ?: "New Vexor"
        error = null
    }
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Saved fits", style = MaterialTheme.typography.titleLarge)
        Text("Create from an example fit. Equipment editing is coming in a later milestone.",
            style = MaterialTheme.typography.bodySmall)
        Button(onClick = { openDialog("Create") }, enabled = enabled, modifier = Modifier.testTag("library-create")) {
            Text("New fit")
        }
        OutlinedTextField(value = search, onValueChange = { search = it }, label = { Text("Search fits or hulls") },
            singleLine = true, modifier = Modifier.fillMaxWidth().testTag("library-search"))
        error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("library-error")) }
        if (busy) Text("Saving…")
        val matches = fits.filter { it.name.contains(search, ignoreCase = true) || it.ship.contains(search, ignoreCase = true) }
            .sortedWith(compareBy<FitSnapshot> { it.name.lowercase() }.thenBy { it.id })
        if (fits.isEmpty()) Text("No saved fits. Create a fit to get started.", modifier = Modifier.testTag("library-empty"))
        else if (matches.isEmpty()) Text("No matching fits.")
        for (fit in matches) {
            Card(Modifier.fillMaxWidth().testTag("fit-${fit.id}")) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(fit.name, style = MaterialTheme.typography.titleMedium)
                    Text(fit.ship + if (selected?.id == fit.id) " · Open" else "")
                    Row {
                        TextButton(onClick = {
                            busy = true
                            EngineRuntime.selectFit(context, fit.id).whenCompleteAsync({ _, failure ->
                                busy = false
                                error = if (failure == null) null else "Could not open this fit. Restart the app."
                            }, ContextCompat.getMainExecutor(context))
                        }, enabled = enabled, modifier = Modifier.testTag("open-${fit.id}")) { Text("Open") }
                        TextButton(onClick = { openDialog("Rename", fit) }, enabled = enabled,
                            modifier = Modifier.testTag("rename-${fit.id}")) { Text("Rename") }
                        TextButton(onClick = { openDialog("Duplicate", fit) }, enabled = enabled,
                            modifier = Modifier.testTag("duplicate-${fit.id}")) { Text("Copy") }
                    }
                    TextButton(onClick = { openDialog("Delete", fit) }, enabled = enabled,
                        modifier = Modifier.testTag("delete-${fit.id}")) { Text("Delete") }
                }
            }
        }
    }
    action?.let { kind ->
        AlertDialog(
            onDismissRequest = { if (!busy) action = null },
            title = { Text("$kind fit") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    if (kind == "Delete") {
                        val target = fits.find { it.id == targetId }
                        val recipients = fits.filter { fit -> fit.projections.any { it.sourceId == targetId } ||
                            fit.commands.any { it.sourceId == targetId } }
                        Text("Delete “${target?.name ?: name}”? This removes its incoming links and links to ${recipients.size} other fit(s). Their statistics will be recalculated. This cannot be undone.")
                    } else {
                        if (kind == "Create") {
                            Text("Example: $example")
                            Row {
                                for (choice in listOf("Vexor", "Celestis", "Vulture")) {
                                    TextButton(onClick = { example = choice; name = "New $choice" }, enabled = !busy) { Text(choice) }
                                }
                            }
                        }
                        OutlinedTextField(value = name, onValueChange = { name = it }, singleLine = true,
                            label = { Text("Fit name") }, enabled = !busy, modifier = Modifier.testTag("fit-name"))
                        if (kind == "Duplicate") Text("Copies equipment, skills and incoming links. Linked source fits stay shared; outgoing recipients are not copied.")
                    }
                    error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                }
            },
            confirmButton = {
                val validName = name.isNotBlank() && name.codePointCount(0, name.length) <= 200 && name.none { it.code < 32 }
                TextButton(enabled = enabled && (kind == "Delete" || validName), modifier = Modifier.testTag("fit-confirm"), onClick = {
                    busy = true
                    error = null
                    val before = fits.map { it.id }.toSet()
                    val request = if (kind == "Create") EngineRuntime.createFromExample(context, example, name) else {
                        val id = checkNotNull(targetId)
                        val operation = when (kind) {
                            "Rename" -> BridgeOperation.RenameFit(id, name)
                            "Duplicate" -> BridgeOperation.DuplicateFit(id, name)
                            else -> BridgeOperation.DeleteFit(id, true)
                        }
                        EngineRuntime.request(context, operation, mapOf(id to targetRevision))
                    }
                    request.whenCompleteAsync({ response, failure ->
                        busy = false
                        if (failure != null) error = "Could not confirm this edit. Restart the app before trying again."
                        else if (!response.isSuccess) error = response.error?.message
                        else {
                            action = null
                            if (kind == "Create" || kind == "Duplicate") {
                                search = ""
                                response.fits.singleOrNull { it.id !in before }?.let { EngineRuntime.selectFit(context, it.id) }
                            }
                        }
                    }, ContextCompat.getMainExecutor(context))
                }) { Text(if (busy) "Saving…" else kind) }
            },
            dismissButton = { TextButton(onClick = { action = null; error = null }, enabled = !busy,
                modifier = Modifier.testTag("fit-cancel")) { Text("Cancel") } },
        )
    }
}
