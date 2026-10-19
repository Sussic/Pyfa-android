package io.github.sussic.pyfa

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.Dispatchers

private data class OfflineExportTarget(val context: OfflineContext, val fitId: String, val revision: Long)
private data class OfflineExportTicket(val preview: OfflineExportPreview, val valid: AtomicBoolean = AtomicBoolean(true))

/** Activity-owned drafts/options survive recreation; only options persist across process death. */
class OfflineExportModel : ViewModel() {
    var options by mutableStateOf(OfflineExportOptions()); private set
    var optionsLoaded by mutableStateOf(false); private set
    var preferenceError by mutableStateOf<String?>(null); private set
    var preview by mutableStateOf<OfflineExportPreview?>(null); private set
    var loading by mutableStateOf(false); private set
    var cancelling by mutableStateOf(false); private set
    var choosingFile by mutableStateOf(false); private set
    var savingFile by mutableStateOf(false); private set
    var sharing by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    private var optionsStarted = false
    private var writingPreferences = false
    private var desiredOptions: OfflineExportOptions? = null
    private var target: OfflineExportTarget? = null
    private var generation = 0
    private var pendingDocument: OfflineExportTicket? = null
    private var activeWrite: OfflineExportTicket? = null
    val busyOutput get() = choosingFile || savingFile || sharing
    val canPreview get() = optionsLoaded && target != null && !loading && !busyOutput && liveTarget() == target
    val canOutput get() = !loading && !busyOutput && optionsLoaded && preview?.let { it.ok && isCurrent(it) } == true

    private fun liveTarget(): OfflineExportTarget? {
        val engine = EngineRuntime.state.value as? EngineState.Ready ?: return null
        if (engine.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) return null
        val context = EngineRuntime.offlineFeatures.value?.context ?: return null
        return OfflineExportTarget(context, engine.fit.id, engine.fit.revision)
    }
    fun synchronize(context: Context) {
        if (!optionsStarted) {
            optionsStarted = true
            OfflineExportFiles.loadOptions(context).whenCompleteAsync({ value, failure ->
                if (failure == null) options = value
                else preferenceError = "Retained export options could not be read. Defaults are in use; choose options to save them again."
                optionsLoaded = true
            }, ContextCompat.getMainExecutor(context))
        }
        val current = liveTarget()
        if (current != target) {
            val hadPreview = preview != null || loading || choosingFile
            invalidate()
            target = current
            if ((EngineRuntime.state.value as? EngineState.Ready)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE)
                error = "The fitting engine is unavailable. Restart the app before preparing another export."
            else if (hadPreview) message = if (current == null) "Open a saved fit to prepare a new export." else "The selected fit or its inputs changed. Preview again before exporting."
        }
    }
    private fun invalidate() {
        generation++
        preview = null; error = null; message = null
        pendingDocument?.valid?.set(false); activeWrite?.valid?.set(false)
        if (loading) cancelling = true
    }
    fun setOptions(context: Context, value: OfflineExportOptions) {
        if (!optionsLoaded || busyOutput || value == options) return
        options = value; invalidate()
        desiredOptions = value
        retainOptions(context.applicationContext)
    }
    private fun retainOptions(context: Context) {
        if (writingPreferences) return
        val captured = desiredOptions ?: return
        writingPreferences = true
        OfflineExportFiles.saveOptions(context, captured).whenCompleteAsync({ saved, failure ->
            writingPreferences = false
            preferenceError = if (failure == null && saved == true) null else "Export options work for this session, but could not be retained for the next launch."
            if (desiredOptions != captured) retainOptions(context)
        }, ContextCompat.getMainExecutor(context))
    }
    fun prepare(context: Context) {
        if (!canPreview) return
        val before = checkNotNull(target)
        val request = OfflineExportRequest(UUID.randomUUID().toString(), before.context, before.fitId, before.revision, options)
        val token = ++generation
        preview = null; error = null; message = null; loading = true; cancelling = false
        EngineRuntime.offlineExportPreview(context, request).whenCompleteAsync({ value, failure ->
            loading = false; cancelling = false
            if (token == generation) {
                if (failure != null) error = "The export preview could not be verified. Try again; no export was copied, shared or saved."
                else if (!value.ok) {
                    preview = value
                    error = value.error?.message ?: "This fit cannot be exported as EFT."
                } else if (!isCurrent(request)) message = "The fit or export options changed while preparing the preview. Preview again."
                else preview = value
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun cancelPreview(silent: Boolean = false) {
        if (!loading) return
        generation++; cancelling = true; preview = null
        if (!silent) message = "Preview cancelled. Its read-only engine request may still be finishing."
    }
    internal fun isCurrent(value: OfflineExportPreview): Boolean = value.ok && isCurrent(value.request)
    private fun isCurrent(request: OfflineExportRequest): Boolean = optionsLoaded && request.options == options &&
        liveTarget() == OfflineExportTarget(request.context, request.fitId, request.revision)
    private fun reviewed(): OfflineExportPreview? {
        if (!canOutput) {
            error = "Prepare a current preview before exporting."
            return null
        }
        return preview
    }
    fun copy(context: Context) {
        val value = reviewed() ?: return
        try {
            checkNotNull(context.getSystemService(ClipboardManager::class.java))
                .setPrimaryClip(ClipData.newPlainText(value.filename, checkNotNull(value.text)))
            error = null; message = "Copied the reviewed EFT preview to the clipboard."
        } catch (_: Exception) { error = "The clipboard could not be updated. The export is still available in its preview." }
    }
    fun beginDocument(): String? {
        val value = reviewed() ?: return null
        pendingDocument = OfflineExportTicket(value); choosingFile = true; error = null; message = null
        return checkNotNull(value.filename)
    }
    fun documentLaunchFailed() {
        pendingDocument = null; choosingFile = false
        error = "A document picker could not be opened. No EFT text was written."
    }
    fun documentReturned(context: Context, uri: Uri?) {
        val ticket = pendingDocument
        pendingDocument = null; choosingFile = false
        if (uri == null) { message = "Save cancelled. No EFT text was written."; return }
        if (ticket == null) {
            error = "The reviewed preview did not survive the app restart. No EFT text was written; the provider may have created an empty file. Preview again."
            return
        }
        if (!ticket.valid.get() || !isCurrent(ticket.preview)) {
            error = "The fit or export options changed while choosing the destination. No EFT text was written; the provider may have created an empty file. Preview again."
            return
        }
        savingFile = true; activeWrite = ticket; error = null; message = null
        // The worker only reads immutable request/preview values and thread-safe runtime flows.
        val request = ticket.preview.request
        OfflineExportFiles.write(context, uri, ticket.preview) {
            val state = EngineRuntime.state.value as? EngineState.Ready
            ticket.valid.get() && state != null && state.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE &&
                state.fit.id == request.fitId && state.fit.revision == request.revision &&
                EngineRuntime.offlineFeatures.value?.context == request.context
        }.whenCompleteAsync({ result, failure ->
            savingFile = false; activeWrite = null
            if (failure != null) error = "The file write could not be confirmed. Check the selected destination before retrying."
            else if (!result.written) error = result.message
            else message = "${result.message} (${ticket.preview.filename})"
        }, ContextCompat.getMainExecutor(context))
    }
    fun beginShare(): Intent? {
        val value = reviewed() ?: return null
        return try {
            OfflineExportFiles.shareChooser(value).also {
                sharing = true; error = null; message = "Choose an app to continue sharing the reviewed EFT preview."
            }
        } catch (_: Exception) { error = "The share chooser could not be prepared."; null }
    }
    fun shareLaunchFailed() { sharing = false; error = "No app could open the share chooser. Nothing was sent by Pyfa." }
    fun shareReturned() {
        sharing = false
        // Android's chooser result does not prove that a recipient received anything.
        message = "Share chooser closed. Pyfa cannot confirm whether the other app sent the text."
    }
}

@Composable
internal fun OfflineExportView(model: OfflineExportModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val features by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    val document = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("text/plain")) { uri -> model.documentReturned(context, uri) }
    val sharing = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { model.shareReturned() }
    LaunchedEffect(fit?.id, fit?.revision, features?.context, engine) { model.synchronize(context) }
    fun leave() { model.cancelPreview(silent = true); onBack() }
    BackHandler { leave() }
    Text("Export EFT fit", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { leave() }, modifier = Modifier.testTag("eft-export-back")) { Text("Back") }
    if (fit == null) Text("Open a saved fit to export it.", Modifier.testTag("eft-export-no-fit"))
    else Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("eft-export-fit"))
    Text("Review the exact text and any limitations before copying, saving or choosing an app to share it.")
    if (!model.optionsLoaded) Text("Loading export options…", Modifier.testTag("eft-export-options-loading"))
    model.preferenceError?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("eft-export-preference-error")) }
    val enabled = model.optionsLoaded && !model.busyOutput
    fun change(value: OfflineExportOptions) { model.setOptions(context, value) }
    OfflineExportOption("Loaded charges", "charges", model.options.loadedCharges, enabled) { change(model.options.copy(loadedCharges = it)) }
    OfflineExportOption("Cargo", "cargo", model.options.cargo, enabled) { change(model.options.copy(cargo = it)) }
    OfflineExportOption("Implants", "implants", model.options.implants, enabled) { change(model.options.copy(implants = it)) }
    OfflineExportOption("Boosters", "boosters", model.options.boosters, enabled) { change(model.options.copy(boosters = it)) }
    OfflineExportOption("Mutation details when supported", "mutations", model.options.mutations, enabled) { change(model.options.copy(mutations = it)) }
    Text("Options are retained on this device. Unsupported mutated items cannot be silently converted into ordinary items.")
    Row {
        Button(onClick = { model.prepare(context) }, enabled = model.canPreview, modifier = Modifier.testTag("eft-export-preview")) { Text("Preview EFT") }
        if (model.loading) TextButton(onClick = { model.cancelPreview() }, enabled = !model.cancelling,
            modifier = Modifier.testTag("eft-export-cancel-preview")) { Text("Cancel") }
    }
    if (model.loading) Text(if (model.cancelling) "Finishing cancelled preview…" else "Preparing export preview…", Modifier.testTag("eft-export-loading"))
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("eft-export-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("eft-export-message")) }
    val preview = model.preview
    if (preview != null && (model.isCurrent(preview) || !preview.ok)) {
        preview.diagnostics.forEach { Text("${it.code}: ${it.message}", modifier = Modifier.testTag("eft-export-diagnostic")) }
        if (preview.ok) {
            Text(checkNotNull(preview.filename), Modifier.testTag("eft-export-filename"))
            SelectionContainer { Text(checkNotNull(preview.text), style = MaterialTheme.typography.bodySmall, modifier = Modifier.testTag("eft-export-text")) }
        }
    }
    Row {
        Button(onClick = { model.copy(context) }, enabled = model.canOutput, modifier = Modifier.testTag("eft-export-copy")) { Text("Copy") }
        TextButton(onClick = {
            model.beginDocument()?.let { filename ->
                try { document.launch(filename) } catch (_: Exception) { model.documentLaunchFailed() }
            }
        }, enabled = model.canOutput, modifier = Modifier.testTag("eft-export-save")) { Text("Save file") }
        TextButton(onClick = {
            model.beginShare()?.let { intent ->
                try { sharing.launch(intent) } catch (_: Exception) { model.shareLaunchFailed() }
            }
        }, enabled = model.canOutput, modifier = Modifier.testTag("eft-export-share")) { Text("Share…") }
    }
    if (model.choosingFile) Text("Choose a destination, or cancel in the document picker.")
    if (model.savingFile) Text("Writing the reviewed preview…", Modifier.testTag("eft-export-saving"))
}

@Composable
private fun OfflineExportOption(label: String, tag: String, checked: Boolean, enabled: Boolean, change: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().toggleable(value = checked, enabled = enabled, role = Role.Checkbox, onValueChange = change)
        .testTag("eft-export-option-$tag")) {
        Checkbox(checked = checked, onCheckedChange = null, enabled = enabled)
        Text(label)
    }
}
