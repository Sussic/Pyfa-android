package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.UUID
import java.util.concurrent.CompletableFuture
import kotlinx.coroutines.Dispatchers
import org.json.JSONObject

/** Detached full-editor values are only converted to floats on explicit Save. */
data class OfflineTargetDraft(val operation: String, val sourceId: String?, val sourceRevision: Long?, val sessionId: String,
    val name: String, val fields: List<String>) {
    fun values(): JSONObject = JSONObject().also { row ->
        TARGET_FIELDS.forEachIndexed { index, key ->
            val input = fields[index].trim()
            val value = if (input.isEmpty()) { if (index < 4) 0.0 else null }
                else input.toDouble().also { require(it.isFinite() && it >= 0 && (index >= 4 || it <= 100)) }
            row.put(key, value?.let { if (index < 4) it / 100.0 else it } ?: JSONObject.NULL)
        }
    }
}
data class OfflineTargetDelete(val context: OfflineContext, val entry: OfflineTargetEntry)

class OfflineTargetProfilesModel(
    private val featureContext: () -> OfflineContext? = { EngineRuntime.offlineFeatures.value?.context },
    private val activeFit: () -> String? = { EngineRuntime.navigation.value.activeId },
    private val engineAvailable: () -> Boolean = { when (val engine = EngineRuntime.state.value) {
        is EngineState.Ready -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        is EngineState.Empty -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        else -> false
    } },
    private val request: (Context, OfflineTargetRequest) -> CompletableFuture<OfflineTargetResponse> = EngineRuntime::offlineTargetProfiles,
) : ViewModel() {
    var state by mutableStateOf<OfflineTargetState?>(null); private set
    var view by mutableStateOf(OfflineTargetView()); private set
    var draft by mutableStateOf<OfflineTargetDraft?>(null); private set
    var busy by mutableStateOf(false); private set
    var saving by mutableStateOf(false); private set
    var conflict by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var deleteConfirmation by mutableStateOf<OfflineTargetDelete?>(null); private set
    private var owner: Any? = null
    private var generation = 0L
    private var anchor: String? = null
    private var observedContext: OfflineContext? = null
    private var observedRevision: Long? = null
    private var refreshPending = false
    private var cleared = false
    val dirty get() = draft != null
    val detail get() = state?.detail?.takeIf { it.entry.id == view.selectedTargetId }
    val available get() = state != null && !cleared && !busy && engineAvailable() && state?.context == featureContext() && state?.fitId == activeFit()
    val canSave get() = available && dirty && !conflict

    fun synchronize(context: Context, current: OfflineContext?, fitId: String?, fitRevision: Long?) {
        if (current == observedContext && fitId == anchor && fitRevision == observedRevision && state != null) return
        val oldSession = observedContext?.sessionId
        observedContext = current; observedRevision = fitRevision; anchor = fitId
        if (oldSession != null && oldSession != current?.sessionId && dirty) conflict = true
        deleteConfirmation = null
        reload(context)
    }
    fun reload(context: Context) {
        generation++; refreshPending = true
        if (!busy) read(context)
    }
    private fun read(context: Context) {
        if (cleared || busy || !engineAvailable()) return
        val source = featureContext() ?: return
        refreshPending = false
        dispatch(context, OfflineTargetRequest(UUID.randomUUID().toString(), source, anchor, view), null)
    }
    fun search(context: Context, query: String) {
        if (saving || dirty || query == view.query) return
        view = view.copy(query = query, offset = 0); deleteConfirmation = null; reload(context)
    }
    fun page(context: Context, offset: Long) {
        if (saving || dirty || offset < 0) return
        view = view.copy(offset = offset); reload(context)
    }
    fun select(context: Context, id: String) {
        if (saving || dirty || state?.entries?.none { it.id == id } != false) return
        view = view.copy(selectedTargetId = id, boundOffset = 0); deleteConfirmation = null; message = null; reload(context)
    }
    fun boundPage(context: Context, offset: Long) {
        if (saving || offset < 0) return
        view = view.copy(boundOffset = offset); reload(context)
    }
    fun begin(operation: String) {
        if (!available || dirty) return
        val selected = detail
        if (operation !in setOf("create", "update_values", "rename", "duplicate") || operation != "create" && selected == null ||
            operation in setOf("update_values", "rename") && selected?.entry?.readonly == true) return
        val fields = TARGET_FIELDS.mapIndexed { index, key -> selected?.values?.fields?.get(key)?.let {
            if (index < 4) (it.toDouble() * 100.0).toString() else it.toString()
        } ?: if (index < 4) "0" else "" }
        draft = OfflineTargetDraft(operation, if (operation == "create") null else selected?.entry?.id,
            if (operation == "create") null else selected?.entry?.revision, checkNotNull(state).context.sessionId,
            if (operation == "create" || operation == "duplicate") "" else checkNotNull(selected).entry.name,
            if (operation == "create") List(8) { if (it < 4) "0" else "" } else fields)
        conflict = false; error = null; message = null; deleteConfirmation = null
    }
    fun editName(value: String) { if (!saving) draft = draft?.copy(name = value) }
    fun editField(index: Int, value: String) {
        if (saving || index !in 0..7) return
        draft = draft?.let { it.copy(fields = it.fields.toMutableList().also { values -> values[index] = value }.toList()) }
    }
    fun cancelDraft() { if (!saving) { draft = null; conflict = false; error = null } }
    fun save(context: Context) {
        val edit = draft ?: return
        if (!canSave) return
        val args = try {
            JSONObject().also {
                if (edit.sourceId != null) it.put("target_id", edit.sourceId).put("revision", edit.sourceRevision)
                if (edit.operation != "update_values") it.put("name", OfflineTargetCodec.name(edit.name))
                if (edit.operation in setOf("create", "update_values")) it.put("values", edit.values())
            }
        } catch (_: Exception) {
            error = "Enter a nonempty name of up to 200 Unicode characters without controls. Values must be finite and nonnegative; resistances must be 0–100%. Blank resistances mean zero; other blanks keep raw null."
            return
        }
        mutate(context, edit.operation, args, edit)
    }
    fun assign(context: Context) {
        val selected = detail?.entry ?: return; val current = state ?: return
        if (!available || dirty || current.fitId == null) return
        mutate(context, "assign", targetArgs(selected).put("fit_revision", current.fitRevision))
    }
    fun clear(context: Context) {
        val current = state ?: return
        if (!available || dirty || current.fitId == null) return
        mutate(context, "clear", JSONObject().put("fit_revision", current.fitRevision))
    }
    fun confirmDelete() {
        val current = state ?: return; val entry = detail?.entry ?: return
        if (available && !dirty && !entry.readonly) deleteConfirmation = OfflineTargetDelete(current.context, entry)
    }
    fun dismissDelete() { deleteConfirmation = null }
    fun delete(context: Context) {
        val confirmation = deleteConfirmation ?: return
        if (!available || dirty || state?.context != confirmation.context || detail?.entry != confirmation.entry) {
            deleteConfirmation = null; error = "Deletion impact changed. Reload and review it before deleting."; return
        }
        deleteConfirmation = null
        mutate(context, "delete", targetArgs(confirmation.entry).put("bound_fit_count", confirmation.entry.boundFitCount))
    }
    fun history(context: Context, redo: Boolean) {
        if (available && !dirty) mutate(context, if (redo) "redo" else "undo", JSONObject())
    }
    private fun targetArgs(entry: OfflineTargetEntry) = JSONObject().put("target_id", entry.id).put("revision", entry.revision)
    private fun mutate(context: Context, operation: String, arguments: JSONObject, edit: OfflineTargetDraft? = null) {
        val current = state ?: return
        if (!available) return
        dispatch(context, OfflineTargetRequest(UUID.randomUUID().toString(), current.context, anchor, view, operation, OfflineFeatureCodec.json(arguments)), edit)
    }
    private fun accept(value: OfflineTargetState) {
        state = value; view = value.view
        if (view.selectedTargetId == null && value.selection.targetId != null && !dirty) {
            view = view.copy(selectedTargetId = value.selection.targetId, boundOffset = 0); refreshPending = true
        }
        val edit = draft
        if (edit != null && (edit.sessionId != value.context.sessionId || edit.sourceId != null &&
            (value.detail?.entry?.id != edit.sourceId || value.detail.entry.revision != edit.sourceRevision))) conflict = true
    }
    private fun dispatch(context: Context, input: OfflineTargetRequest, edit: OfflineTargetDraft?) {
        if (busy || cleared) return
        try { input.json() } catch (_: Exception) { error = "The request is invalid. Check the name, search text and numeric values; your draft is kept."; return }
        val token = ++generation; val slot = Any(); owner = slot; busy = true; saving = input.operation != "read"; error = null
        val pending = try { request(context.applicationContext, input) } catch (_: Exception) {
            busy = false; saving = false; owner = null; error = "The request could not be started. Your draft is kept."; return
        }
        pending.whenCompleteAsync({ result, failure ->
            if (owner !== slot) return@whenCompleteAsync
            owner = null; busy = false; saving = false
            if (cleared) return@whenCompleteAsync
            // Confirmed success belongs to the exact submitted draft, even when its
            // own context publication scheduled a newer read before this callback.
            if (result?.ok == true && edit != null && draft === edit) { draft = null; conflict = false }
            val sameView = input.fitId == activeFit() && (token == generation ||
                input.operation != "read" && input.view == view)
            if (sameView) {
                if (failure != null || result == null) error = if (input.operation == "read") "Target profiles could not be loaded. Reload to try again."
                    else "The save could not be confirmed. Keep your draft and restart the app to check saved changes."
                else if (!result.ok) {
                    error = result.error?.message ?: "The request was not completed."
                    if (dirty && result.error?.code in setOf("stale_target", "missing_target", "stale_context")) conflict = true
                    // A removed selected profile must not make the library impossible to reload.
                    if (result.error?.code == "missing_target") view = view.copy(selectedTargetId = null, boundOffset = 0)
                } else if (result.state?.context != featureContext()) {
                    error = "Inputs changed while loading. Reload to use current saved values."; refreshPending = true
                } else {
                    if (edit != null && draft === edit) { draft = null; conflict = false }
                    accept(checkNotNull(result.state))
                    if (input.operation != "read") message = if (result.committed == true) "Saved. Shared changes apply to every bound fit." else "No saved values changed."
                }
            }
            if (refreshPending && engineAvailable()) read(context)
        }, ContextCompat.getMainExecutor(context))
    }
    override fun onCleared() { cleared = true; generation++ }
}

@Composable
internal fun OfflineTargetProfilesView(model: OfflineTargetProfilesModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val features by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    var confirmLeave by rememberSaveable { mutableStateOf(false) }
    fun leave() { if (model.dirty) confirmLeave = true else onBack() }
    BackHandler { leave() }
    LaunchedEffect(features?.context, fit?.id, fit?.revision) { model.synchronize(context, features?.context, fit?.id, fit?.revision) }
    Text("Named target profiles", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { leave() }, modifier = Modifier.testTag("targets-back")) { Text("Back") }
    Text("195 read-only built-ins and your custom targets. Graph-only Ideal Target is not a fit profile.")
    if (model.busy) Text(if (model.saving) "Saving and recalculating…" else "Loading profiles…", Modifier.testTag("targets-busy"))
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("targets-error")) }
    model.message?.let { Text(it, Modifier.testTag("targets-message")) }
    TextButton(onClick = { model.reload(context) }, enabled = !model.busy, modifier = Modifier.testTag("targets-reload")) { Text("Reload saved profiles") }
    val state = model.state
    if (state != null) {
        val selectedName = state.selection.targetId?.let { id -> state.entries.find { it.id == id }?.name ?: state.detail?.entry?.takeIf { it.id == id }?.name ?: id }
        Text(when (state.selection.kind) {
            "no_fit" -> "No fit open. Manage the library without assigning a fit."
            "none" -> "${fit?.name ?: "Fit"}: No Profile"
            "anonymous" -> "${fit?.name ?: "Fit"}: Anonymous target"
            else -> "${fit?.name ?: "Fit"}: $selectedName"
        }, Modifier.testTag("targets-selection"))
        Row {
            TextButton(onClick = { model.history(context, false) }, enabled = model.available && !model.dirty && state.history.undoCount > 0,
                modifier = Modifier.testTag("targets-undo")) { Text("Undo") }
            TextButton(onClick = { model.history(context, true) }, enabled = model.available && !model.dirty && state.history.redoCount > 0,
                modifier = Modifier.testTag("targets-redo")) { Text("Redo") }
        }
        Text(state.history.undoLabel?.let { "Undo: $it" } ?: "No undo action")
    }
    OutlinedTextField(model.view.query, { model.search(context, it) }, enabled = !model.saving && !model.dirty,
        label = { Text("Search target profiles") }, singleLine = true, modifier = Modifier.fillMaxWidth().testTag("targets-search"))
    if (state != null) {
        Text("${state.total} matching profiles · offset ${state.view.offset}", Modifier.testTag("targets-page"))
        for (entry in state.entries) TextButton(onClick = { model.select(context, entry.id) }, enabled = !model.saving && !model.dirty,
            modifier = Modifier.testTag("target-select-${entry.id}")) {
            Text((if (model.view.selectedTargetId == entry.id) "✓ " else "") + entry.name + if (entry.readonly) " · built-in" else " · custom")
        }
        Row {
            TextButton(onClick = { model.page(context, (model.view.offset - 50).coerceAtLeast(0)) }, enabled = !model.busy && !model.dirty && model.view.offset > 0,
                modifier = Modifier.testTag("targets-previous")) { Text("Previous") }
            TextButton(onClick = { model.page(context, model.view.offset + 50) }, enabled = !model.busy && !model.dirty && model.view.offset < state.total - 50,
                modifier = Modifier.testTag("targets-next")) { Text("Next") }
        }
    }
    Button(onClick = { model.begin("create") }, enabled = model.available && !model.dirty, modifier = Modifier.testTag("target-create")) { Text("Create profile") }
    if (state?.fitId != null) TextButton(onClick = { model.clear(context) }, enabled = model.available && !model.dirty && state.selection.kind != "none",
        modifier = Modifier.testTag("target-clear")) { Text("Clear fit to No Profile") }
    model.detail?.let { detail ->
        val entry = detail.entry
        Text("${entry.name} · ${entry.kind} · ${entry.boundFitCount} bound fit(s)", style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("target-selected"))
        Text("Identity: ${entry.id}")
        if (entry.readonly) Text("Built-in values are read-only. Duplicate to make an independent custom profile.", Modifier.testTag("target-readonly"))
        for ((index, key) in TARGET_FIELDS.withIndex()) {
            val raw = detail.values.fields[key]; val effective = detail.effective.fields[key]
            fun label(value: Number?, rawValue: Boolean): String = value?.let { if (index < 4) "${it.toDouble() * 100}% (${it} fraction)" else it.toString() }
                ?: if (rawValue) "null (blank)" else "Unlimited"
            Text("${TARGET_LABELS[index]}: raw ${label(raw, true)} · effective ${label(effective, false)}", Modifier.testTag("target-value-$key"))
        }
        Text("Blank speed/physical radius has effective 0. Blank signature/HP is unlimited; explicit zero is zero. Spatial values are assumptions, not an application-versus-range calculation.")
        if (state?.fitId != null) Button(onClick = { model.assign(context) }, enabled = model.available && !model.dirty && state.selection.targetId != entry.id,
            modifier = Modifier.testTag("target-assign")) { Text("Use for ${fit?.name ?: "this fit"}") }
        Row {
            TextButton(onClick = { model.begin("duplicate") }, enabled = model.available && !model.dirty, modifier = Modifier.testTag("target-duplicate")) { Text("Duplicate") }
            if (!entry.readonly) {
                TextButton(onClick = { model.begin("update_values") }, enabled = model.available && !model.dirty, modifier = Modifier.testTag("target-edit")) { Text("Edit values") }
                TextButton(onClick = { model.begin("rename") }, enabled = model.available && !model.dirty, modifier = Modifier.testTag("target-rename")) { Text("Rename") }
            }
        }
        Text("Bound saved fits (${entry.boundFitCount}):", Modifier.testTag("target-bound-count"))
        detail.boundFits.forEach { Text(it.name, Modifier.testTag("target-bound-${it.id}")) }
        Row {
            TextButton(onClick = { model.boundPage(context, (detail.boundOffset - 50).coerceAtLeast(0)) }, enabled = !model.busy && detail.boundOffset > 0,
                modifier = Modifier.testTag("target-bound-previous")) { Text("Previous fits") }
            TextButton(onClick = { model.boundPage(context, detail.boundOffset + 50) }, enabled = !model.busy && detail.boundOffset < entry.boundFitCount - 50,
                modifier = Modifier.testTag("target-bound-next")) { Text("Next fits") }
        }
        if (!entry.readonly) TextButton(onClick = model::confirmDelete, enabled = model.available && !model.dirty,
            modifier = Modifier.testTag("target-delete")) { Text("Delete profile…") }
    }
    model.draft?.let { draft ->
        Text("Unsaved ${draft.operation.replace('_', ' ')} draft", style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("target-dirty"))
        if (draft.operation != "update_values") OutlinedTextField(draft.name, model::editName, enabled = !model.saving,
            label = { Text("Custom profile name") }, modifier = Modifier.fillMaxWidth().testTag("target-name"))
        if (draft.operation in setOf("create", "update_values")) {
            Text("Supported resistances are 0–100%. This deliberately rejects the desktop editor's unchecked values above 100%.")
            TARGET_FIELDS.forEachIndexed { index, key -> OutlinedTextField(draft.fields[index], { model.editField(index, it) }, enabled = !model.saving,
                label = { Text(TARGET_LABELS[index]) }, modifier = Modifier.fillMaxWidth().testTag("target-edit-$key")) }
        }
        if (model.conflict) Text("The source profile or session changed. Your draft is kept; cancel it before editing the new saved state.", color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("target-conflict"))
        Row {
            Button(onClick = { model.save(context) }, enabled = model.canSave, modifier = Modifier.testTag("target-save")) { Text("Save") }
            TextButton(onClick = model::cancelDraft, enabled = !model.saving, modifier = Modifier.testTag("target-cancel")) { Text("Cancel draft") }
        }
    }
    model.deleteConfirmation?.let { confirmation -> AlertDialog(onDismissRequest = model::dismissDelete,
        title = { Text("Delete ${confirmation.entry.name}?") },
        text = { Text("Exactly ${confirmation.entry.boundFitCount} bound saved fit(s) will switch to No Profile. All bindings clear together. You can undo during this session.") },
        confirmButton = { TextButton(onClick = { model.delete(context) }, modifier = Modifier.testTag("target-delete-confirm")) { Text("Delete and clear fits") } },
        dismissButton = { TextButton(onClick = model::dismissDelete) { Text("Cancel") } }) }
    if (confirmLeave) AlertDialog(onDismissRequest = { confirmLeave = false }, title = { Text("Keep unsaved target draft?") },
        text = { Text("Your draft will remain here while the app stays open.") },
        confirmButton = { TextButton(onClick = { confirmLeave = false; onBack() }, modifier = Modifier.testTag("target-leave-keep")) { Text("Keep draft and go back") } },
        dismissButton = { TextButton(onClick = { confirmLeave = false }) { Text("Stay") } })
}
