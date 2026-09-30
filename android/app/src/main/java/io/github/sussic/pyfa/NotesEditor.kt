package io.github.sussic.pyfa

import android.content.Context
import android.os.Handler
import android.os.Looper
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.concurrent.CompletableFuture
import kotlinx.coroutines.Dispatchers

class NoteDraft(val fitId: String) {
    var text by mutableStateOf("")
    var stored by mutableStateOf("")
    var revision by mutableStateOf(0L)
    var editable by mutableStateOf(false)
    var loaded by mutableStateOf(false)
    var loading by mutableStateOf(false)
    var saving by mutableStateOf(false)
    var conflict by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var saved by mutableStateOf(false)
    val dirty get() = loaded && text != stored
    internal var generation = 0
    internal var timer: Runnable? = null
    internal var inFlight: CompletableFuture<Boolean>? = null
}

/** Drafts belong to fit IDs, not the currently selected fit or activity. */
class NotesModel : ViewModel() {
    val drafts = mutableStateMapOf<String, NoteDraft>()
    private val handler = Handler(Looper.getMainLooper())
    private var activeId: String? = null

    fun open(context: Context, fit: FitSnapshot?) {
        if (activeId != fit?.id) activeId?.let { drafts[it]?.let { prior -> save(context, prior) } }
        activeId = fit?.id
        if (fit == null) return
        val draft = drafts.getOrPut(fit.id) { NoteDraft(fit.id) }
        if (!draft.saving && (!draft.loaded || draft.revision != fit.revision)) load(context, draft)
    }

    fun load(context: Context, draft: NoteDraft) {
        val generation = ++draft.generation
        draft.loading = true
        EngineRuntime.noteDetails(context, draft.fitId).whenCompleteAsync({ value, failure ->
            if (generation == draft.generation) {
                draft.loading = false
                if (failure != null) draft.error = "Notes could not be loaded. Your draft is kept. Retry loading."
                else {
                    if (!draft.loaded || !draft.dirty || draft.text == value.text) {
                        draft.text = value.text; draft.error = null; draft.conflict = false
                    }
                    else if (draft.stored != value.text) {
                        draft.conflict = true
                        draft.error = "Saved notes changed. Save your draft to replace them, or use the saved text."
                    }
                    draft.stored = value.text; draft.revision = value.revision
                    draft.editable = value.editable; draft.loaded = true
                    if (draft.dirty && !draft.conflict && draft.error == null) schedule(context, draft)
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun edit(context: Context, draft: NoteDraft, text: String) {
        if (!draft.loaded || !draft.editable || draft.loading) return
        draft.text = text; draft.saved = false
        if (!draft.conflict) draft.error = null
        schedule(context, draft)
    }

    private fun cancel(draft: NoteDraft) {
        draft.timer?.let(handler::removeCallbacks); draft.timer = null
    }

    private fun schedule(context: Context, draft: NoteDraft) {
        cancel(draft)
        if (!draft.dirty || draft.conflict) return
        val app = context.applicationContext
        draft.timer = Runnable { draft.timer = null; save(app, draft) }.also { handler.postDelayed(it, 1000) }
    }

    fun useSaved(draft: NoteDraft) {
        cancel(draft); draft.text = draft.stored; draft.conflict = false; draft.error = null
    }

    fun save(context: Context, draft: NoteDraft, explicit: Boolean = false): CompletableFuture<Boolean> {
        cancel(draft)
        if (draft.saving) return checkNotNull(draft.inFlight).thenCompose { success ->
            if (success) save(context, draft, explicit) else CompletableFuture.completedFuture(false)
        }
        if (!draft.dirty) return CompletableFuture.completedFuture(true)
        if (draft.loading || !draft.editable || draft.conflict && !explicit)
            return CompletableFuture.completedFuture(false)
        val text = draft.text
        val completion = CompletableFuture<Boolean>()
        draft.inFlight = completion; draft.saving = true; draft.error = null
        EngineRuntime.request(context, BridgeOperation.SetNotes(draft.fitId, text),
            mapOf(draft.fitId to draft.revision)).whenCompleteAsync({ response, failure ->
                draft.saving = false; draft.inFlight = null
                if (failure != null) {
                    draft.error = "The save could not be confirmed. Copy your draft before restarting the app."
                    completion.complete(false)
                } else if (!response.isSuccess) {
                    draft.error = if (response.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE)
                        "The engine needs to restart. Copy your draft before restarting the app."
                    else "${response.error?.message ?: "Notes could not be saved."} Your draft is kept."
                    if (response.error?.code == BridgeErrorCode.REVISION_CONFLICT) load(context, draft)
                    completion.complete(false)
                } else {
                    draft.stored = text
                    draft.revision = response.fits.single { it.id == draft.fitId }.revision
                    draft.conflict = false; draft.saved = !draft.dirty
                    if (draft.dirty) schedule(context, draft)
                    completion.complete(true)
                }
            }, ContextCompat.getMainExecutor(context))
        return completion
    }

    fun flush(context: Context) { drafts.values.toList().forEach { save(context, it) } }
    override fun onCleared() { drafts.values.forEach(::cancel) }
}

@Composable
internal fun NotesEditor(model: NotesModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    val draft = fit?.let { model.drafts[it.id] }
    LaunchedEffect(fit?.id, fit?.revision) { model.open(context, fit) }
    fun leave() {
        focus.clearFocus()
        if (draft == null) onBack()
        else model.save(context, draft).thenAcceptAsync({ success ->
            if (success && (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id == draft.fitId) onBack()
        }, ContextCompat.getMainExecutor(context))
    }
    BackHandler { leave() }
    Text("Fit notes", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { leave() }, modifier = Modifier.testTag("notes-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to view its notes."); return }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    if (draft == null) { Text("Loading notes…"); return }
    if (draft.loading) Text("Loading notes…", modifier = Modifier.testTag("notes-loading"))
    draft.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("notes-error")) }
    if (!draft.loaded) {
        if (!draft.loading) Button(onClick = { model.load(context, draft) }, modifier = Modifier.testTag("notes-retry")) { Text("Retry loading") }
        return
    }
    if (!draft.editable) Text("Notes editing is unavailable for structures. Stored notes are preserved.",
        modifier = Modifier.testTag("notes-readonly"))
    else Text("Notes save after a short pause and when you go back.")
    OutlinedTextField(value = draft.text, onValueChange = { model.edit(context, draft, it) },
        label = { Text("Notes") }, readOnly = !draft.editable || draft.loading,
        minLines = 6, maxLines = 12, modifier = Modifier.fillMaxWidth().testTag("notes-text"))
    Text("${draft.text.codePointCount(0, draft.text.length)} characters", modifier = Modifier.testTag("notes-count"))
    when {
        draft.saving -> Text("Saving…", modifier = Modifier.testTag("notes-saving"))
        draft.dirty -> Text("Unsaved changes", modifier = Modifier.testTag("notes-unsaved"))
        draft.saved -> Text("Notes saved.", modifier = Modifier.testTag("notes-saved"))
    }
    if (draft.editable) Row {
        Button(onClick = { focus.clearFocus(); model.save(context, draft, explicit = true) },
            enabled = draft.dirty && !draft.saving && !draft.loading,
            modifier = Modifier.testTag("notes-save")) { Text(if (draft.conflict) "Save my draft" else "Save notes") }
        if (draft.conflict) TextButton(onClick = { model.useSaved(draft) },
            modifier = Modifier.testTag("notes-use-saved")) { Text("Use saved text") }
    }
}
