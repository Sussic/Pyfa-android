package io.github.sussic.pyfa

import android.content.Context
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.UUID
import kotlinx.coroutines.Dispatchers
import org.json.JSONArray
import org.json.JSONObject

class OfflineImportModel : ViewModel() {
    var documents by mutableStateOf(listOf(OfflineEftDocument("Pasted fit", ""))); private set
    var profileId by mutableStateOf("builtin:all5"); private set
    var preview by mutableStateOf<OfflineImportPreview?>(null); private set
    var result by mutableStateOf<OfflineImportResult?>(null); private set
    var busy by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var libraryHistory by mutableStateOf<OfflineFeatureState?>(null); private set
    private var historyGeneration = 0
    fun refreshHistory(context: Context) {
        val token = ++historyGeneration
        EngineRuntime.offlineFeatureState(context, null).whenCompleteAsync({ value, failure ->
            if (token == historyGeneration && failure == null) libraryHistory = value
        }, ContextCompat.getMainExecutor(context))
    }
    fun history(context: Context, redo: Boolean) {
        if (busy || EngineRuntime.pendingImport.value != null) return
        val before = libraryHistory ?: return
        busy = true; error = null
        EngineRuntime.offlineFeatureRequest(context, before.context, if (redo) "redo" else "undo", JSONObject(), null).whenCompleteAsync({ value, failure ->
            busy = false
            if (failure != null) error = "History could not be confirmed. Restart to inspect the saved library."
            else if (!value.ok) error = value.error?.message
            else { libraryHistory = value.state; preview = null; previewContext = null; result = null }
        }, ContextCompat.getMainExecutor(context))
    }
    private var generation = 0
    private var previewContext: OfflineContext? = null
    fun changeProfile(id: String) { if (!busy) { profileId = id; invalidate() } }
    fun edit(index: Int, text: String) {
        if (busy || EngineRuntime.pendingImport.value != null) return
        if (documents.mapIndexed { i, row -> if (i == index) text else row.text }.sumOf { it.toByteArray(Charsets.UTF_8).size.toLong() } > 1024 * 1024) {
            error = "EFT documents must total at most 1 MiB of UTF-8 text."
            return
        }
        documents = documents.mapIndexed { i, row -> if (i == index) row.copy(text = text) else row }; invalidate()
    }
    fun add() { if (!busy && documents.size < 16) { documents = documents + OfflineEftDocument("Pasted fit ${documents.size + 1}", ""); invalidate() } }
    fun remove(index: Int) { if (!busy && documents.size > 1) { documents = documents.filterIndexed { i, _ -> i != index }; invalidate() } }
    private fun invalidate() { generation++; preview = null; result = null; error = null; previewContext = null }
    fun contextChanged(value: OfflineContext?) {
        if (preview != null && value != previewContext && !busy) {
            invalidate(); error = "Saved fits or profiles changed. Preview again before importing."
        }
    }
    fun files(context: Context, uris: List<Uri>) {
        if (busy || uris.isEmpty() || EngineRuntime.pendingImport.value != null) return
        invalidate(); val token = generation; busy = true
        EngineRuntime.readEftDocuments(context, uris).whenCompleteAsync({ value, failure ->
            busy = false
            if (token == generation) {
                if (failure != null) error = "Files could not be read as UTF-8 EFT text. Select at most 16 files totaling 1 MiB."
                else documents = value
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun prepare(context: Context) {
        if (busy || EngineRuntime.pendingImport.value != null) return
        val state = EngineRuntime.offlineFeatures.value ?: return
        val rows = JSONArray(); documents.forEach { rows.put(JSONObject().put("label", it.label).put("text", it.text)) }
        val request = JSONObject().put("version", 1).put("request_id", UUID.randomUUID().toString())
            .put("profile_id", profileId).put("documents", rows).toString()
        invalidate(); val token = generation; busy = true
        EngineRuntime.offlineImportPreview(context, request).whenCompleteAsync({ value, failure ->
            busy = false
            if (token == generation) {
                if (failure != null) error = "Preview could not be loaded. No import was requested."
                else if (EngineRuntime.offlineFeatures.value?.context != state.context) error = "Fits changed during preview. Preview again."
                else { preview = value; previewContext = state.context }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun execute(context: Context, retry: Boolean = false) {
        if (busy) return
        val raw = if (retry) EngineRuntime.pendingImport.value else preview?.takeIf { it.ok }?.exactRequest
        if (raw == null) return
        if (!retry && previewContext != EngineRuntime.offlineFeatures.value?.context) {
            contextChanged(EngineRuntime.offlineFeatures.value?.context); return
        }
        val token = ++generation; busy = true; error = null
        EngineRuntime.offlineImportExecute(context, raw).whenCompleteAsync({ value, failure ->
            busy = false
            if (token == generation) {
                if (failure != null) error = "The import was not confirmed. If a retry record is shown, restart and retry that exact request before starting another import."
                else {
                    result = value
                    if (value.ok || value.committed == false) { preview = null; previewContext = null }
                    if (value.reopenRequired) error = "Restart the app, then retry the saved request to determine what was committed."
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Suppress("DEPRECATION")
@Composable
internal fun OfflineImportView(model: OfflineImportModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val state by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val pending by EngineRuntime.pendingImport.collectAsState(context = Dispatchers.Main)
    val storageError by EngineRuntime.importStorageError.collectAsState(context = Dispatchers.Main)
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    var confirm by rememberSaveable { mutableStateOf(false) }
    val files = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { model.files(context, it) }
    val unavailable = (engine as? EngineState.Ready)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ||
        (engine as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE
    val enabled = !model.busy && !unavailable && storageError == null && pending == null
    BackHandler { onBack() }
    LaunchedEffect(state?.context) { model.contextChanged(state?.context); model.refreshHistory(context) }
    Text("Import EFT fits", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("eft-back")) { Text("Back") }
    model.libraryHistory?.history?.let { history ->
        Row {
            TextButton(onClick = { model.history(context, false) }, enabled = enabled && history.undoCount > 0,
                modifier = Modifier.testTag("eft-history-undo")) { Text("Undo library action") }
            TextButton(onClick = { model.history(context, true) }, enabled = enabled && history.redoCount > 0,
                modifier = Modifier.testTag("eft-history-redo")) { Text("Redo library action") }
        }
        Text(history.undoLabel?.let { "Undo: $it" } ?: "No library undo action", Modifier.testTag("eft-history"))
    }
    Text("Paste one fit per document or choose UTF-8 text files. All documents are checked before one atomic import.")
    storageError?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("eft-storage-error")) }
    if (pending != null) {
        Text("An import request is saved for recovery. Retrying uses its original text and identity, so already committed fits are not duplicated.", Modifier.testTag("eft-pending"))
        Button(onClick = { model.execute(context, retry = true) }, enabled = !model.busy && !unavailable && storageError == null,
            modifier = Modifier.testTag("eft-retry")) { Text("Retry saved import") }
        if (unavailable) Text("Restart the app before retrying.")
    }
    if (model.busy) Text("Working on EFT import…", Modifier.testTag("eft-busy"))
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("eft-error")) }
    for (profile in state?.profiles.orEmpty()) TextButton(onClick = { model.changeProfile(profile.id) }, enabled = enabled,
        modifier = Modifier.testTag("eft-profile-${profile.id}")) { Text((if (profile.id == model.profileId) "✓ " else "") + profile.name) }
    Text("Selected profile supplies all imported skills. Existing fits are kept.")
    for ((index, document) in model.documents.withIndex()) {
        OutlinedTextField(value = document.text, onValueChange = { model.edit(index, it) }, label = { Text(document.label) },
            enabled = enabled, minLines = 4, maxLines = 10, modifier = Modifier.fillMaxWidth().testTag("eft-text-$index"))
        Row {
            TextButton(onClick = { clipboard.getText()?.text?.let { model.edit(index, it) } }, enabled = enabled,
                modifier = Modifier.testTag("eft-paste-$index")) { Text("Paste") }
            if (model.documents.size > 1) TextButton(onClick = { model.remove(index) }, enabled = enabled) { Text("Remove document") }
        }
    }
    Row {
        TextButton(onClick = { model.add() }, enabled = enabled && model.documents.size < 16, modifier = Modifier.testTag("eft-add")) { Text("Add document") }
        TextButton(onClick = { files.launch(arrayOf("text/*", "application/octet-stream")) }, enabled = enabled,
            modifier = Modifier.testTag("eft-files")) { Text("Choose files") }
    }
    Button(onClick = { model.prepare(context) }, enabled = enabled, modifier = Modifier.testTag("eft-preview")) { Text("Preview import") }
    model.preview?.let { preview ->
        Text(if (preview.ok) "Ready for confirmation. No fit has been imported yet." else "Fix every reported problem before importing.", Modifier.testTag("eft-preview-status"))
        for (document in preview.documents) {
            Text("${document.label}: ${document.name ?: "No fit header"} · ${document.hull ?: "Unknown hull"}")
            document.lines.take(40).forEach { Text(it, style = MaterialTheme.typography.bodySmall) }
            if (document.lines.size > 40) Text("${document.lines.size - 40} more source lines checked; the complete source remains above.")
        }
        OfflineImportDiagnostics(preview.diagnostics)
        if (preview.ok) Button(onClick = { confirm = true }, enabled = enabled,
            modifier = Modifier.testTag("eft-confirm-open")) { Text("Import ${preview.documents.size} fit(s)…") }
    }
    model.result?.let { result ->
        if (result.ok) Text(if (result.replayed) "Saved import confirmed. No duplicate fits were created." else "Imported ${result.fitIds.size} fit(s).", Modifier.testTag("eft-result"))
        if (result.missingFitIds.isNotEmpty()) Text("${result.missingFitIds.size} fit(s) from that import were later removed or undone. Retrying does not recreate them.", Modifier.testTag("eft-missing"))
        for (id in result.fitIds.filter { it !in result.missingFitIds }) TextButton(onClick = { EngineRuntime.selectFit(context, id) }, enabled = !model.busy && !unavailable) {
            Text("Open ${EngineRuntime.library.value.find { it.id == id }?.name ?: id}")
        }
        OfflineImportDiagnostics(result.diagnostics)
    }
    if (confirm) AlertDialog(onDismissRequest = { confirm = false }, title = { Text("Import these fits?") },
        text = { Text("Create ${model.preview?.documents?.size ?: 0} saved fits using ${state?.profiles?.find { it.id == model.profileId }?.name}. All documents are committed together. You can undo the import during this session from its imported fit or library history.") },
        confirmButton = { TextButton(onClick = { confirm = false; model.execute(context) }, enabled = enabled,
            modifier = Modifier.testTag("eft-confirm")) { Text("Import all") } },
        dismissButton = { TextButton(onClick = { confirm = false }) { Text("Cancel") } })
}

@Composable
private fun OfflineImportDiagnostics(values: List<OfflineImportDiagnostic>) {
    values.forEach { Text("${it.label ?: "Import"}${if (it.line > 0) ":${it.line}" else ""} · ${it.code}: ${it.message}",
        color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("eft-diagnostic")) }
}
