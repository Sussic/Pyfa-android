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
data class OfflineDamageDraft(val operation: String, val sourceId: String?, val sourceRevision: Long?, val sessionId: String,
    val name: String, val fields: List<String>) {
    fun values(): JSONObject = JSONObject().also { row ->
        require(fields.size == 4)
        DAMAGE_PATTERN_FIELDS.forEachIndexed { index, key ->
            val input = fields[index].trim()
            val value = if (input.isEmpty()) 0.0 else input.toDouble()
            require(value.isFinite() && value >= 0)
            row.put(key, value)
        }
        OfflineDamageCodec.values(row, editor = true)
    }
}
data class OfflineDamageDelete(val context: OfflineContext, val entry: OfflineDamageEntry)
private data class PendingDamageMutation(val screen: Long, val input: OfflineDamageRequest,
    val draft: OfflineDamageDraft?, val future: CompletableFuture<OfflineDamageResponse>)

class OfflineDamagePatternsModel(
    private val featureContext: () -> OfflineContext? = { EngineRuntime.offlineFeatures.value?.context },
    private val activeFit: () -> String? = { EngineRuntime.navigation.value.activeId },
    private val engineAvailable: () -> Boolean = { when (val engine = EngineRuntime.state.value) {
        is EngineState.Ready -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        is EngineState.Empty -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        else -> false
    } },
    private val request: (Context, OfflineDamageRequest) -> CompletableFuture<OfflineDamageResponse> = EngineRuntime::offlineDamagePatterns,
) : ViewModel() {
    var state by mutableStateOf<OfflineDamageState?>(null); private set
    var view by mutableStateOf(OfflineDamageView()); private set
    var draft by mutableStateOf<OfflineDamageDraft?>(null); private set
    var reopenRequired by mutableStateOf(false); private set
    var busy by mutableStateOf(false); private set
    var saving by mutableStateOf(false); private set
    var conflict by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var deleteConfirmation by mutableStateOf<OfflineDamageDelete?>(null); private set
    private var owner: Any? = null
    private var generation = 0L
    private var anchor: String? = null
    private var observedContext: OfflineContext? = null
    private var observedRevision: Long? = null
    private var refreshPending = false
    private var cleared = false
    private var screenOpen = true
    private var screen = 0L
    private var pendingMutation: PendingDamageMutation? = null
    val dirty get() = draft != null
    val detail get() = state?.detail?.takeIf { it.entry.id == view.selectedPatternId }
    val available get() = state != null && screenOpen && !cleared && !busy && !reopenRequired && engineAvailable() && state?.context == featureContext() && state?.fitId == activeFit()
    val canSave get() = available && dirty && !conflict

    fun open() { if (!cleared) { screen = Math.addExact(screen, 1); pendingMutation = null; invalidate(); screenOpen = true; state = null; error = null; message = null } }
    fun close() { screen = Math.addExact(screen, 1); pendingMutation = null; invalidate(); screenOpen = false; deleteConfirmation = null; error = null; message = null }
    private fun invalidate() { generation = Math.addExact(generation, 1); owner = null; busy = false; saving = false; refreshPending = false }
    fun synchronize(context: Context, current: OfflineContext?, fitId: String?, fitRevision: Long?) {
        if (current == observedContext && fitId == anchor && fitRevision == observedRevision && state != null) return
        if (!screenOpen || cleared) return
        invalidate()
        val oldSession = observedContext?.sessionId
        observedContext = current; observedRevision = fitRevision; anchor = fitId
        if (oldSession != null && oldSession != current?.sessionId) {
            if (dirty) conflict = true
            reopenRequired = false
        }
        deleteConfirmation = null
        reload(context)
    }
    fun reload(context: Context) {
        if (!screenOpen || cleared) return
        invalidate(); refreshPending = true
        read(context)
    }
    private fun read(context: Context) {
        if (!screenOpen || cleared || busy || reopenRequired || !engineAvailable()) return
        val source = featureContext() ?: return
        refreshPending = false
        dispatch(context, OfflineDamageRequest(UUID.randomUUID().toString(), source, anchor, view), null)
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
        view = view.copy(selectedPatternId = id, boundOffset = 0, moduleOffset = 0); deleteConfirmation = null; message = null; reload(context)
    }
    fun boundPage(context: Context, offset: Long) {
        if (saving || offset < 0) return
        view = view.copy(boundOffset = offset); reload(context)
    }
    fun modulePage(context: Context, offset: Long) {
        if (saving || offset < 0) return
        view = view.copy(moduleOffset = offset); reload(context)
    }
    fun begin(operation: String) {
        if (!available || dirty) return
        val selected = detail
        if (operation !in setOf("create", "update_values", "rename", "duplicate") || operation != "create" && selected == null ||
            operation in setOf("update_values", "rename") && selected?.entry?.readonly == true ||
            operation == "duplicate" && selected?.entry?.duplicable == false) return
        val fields = DAMAGE_PATTERN_FIELDS.map { key -> selected?.values?.fields?.get(key)?.toString() ?: "0" }
        draft = OfflineDamageDraft(operation, if (operation == "create") null else selected?.entry?.id,
            if (operation == "create") null else selected?.entry?.revision, checkNotNull(state).context.sessionId,
            if (operation == "create" || operation == "duplicate") "" else checkNotNull(selected).entry.name,
            if (operation == "create") List(4) { "0" } else fields)
        conflict = false; error = null; message = null; deleteConfirmation = null
    }
    fun editName(value: String) { if (!saving) draft = draft?.copy(name = value) }
    fun editField(index: Int, value: String) {
        if (saving || index !in 0..3) return
        draft = draft?.let { it.copy(fields = it.fields.toMutableList().also { values -> values[index] = value }.toList()) }
    }
    fun cancelDraft() { if (!saving) { draft = null; conflict = false; error = null } }
    fun save(context: Context) {
        val edit = draft ?: return
        if (!canSave) return
        val args = try {
            JSONObject().also {
                if (edit.sourceId != null) it.put("pattern_id", edit.sourceId).put("revision", edit.sourceRevision)
                if (edit.operation != "update_values") it.put("name", OfflineDamageCodec.name(edit.name))
                if (edit.operation in setOf("create", "update_values")) it.put("values", edit.values())
            }
        } catch (_: Exception) {
            error = "Use a nonreserved name of up to 200 Unicode characters without controls, and finite nonnegative contributions with a finite total. Blank fields mean zero. Zero-total patterns cannot be assigned."
            return
        }
        mutate(context, edit.operation, args, edit)
    }
    fun assign(context: Context) {
        val selected = detail?.entry ?: return; val current = state ?: return
        if (!available || dirty || current.fitId == null || !selected.assignable) return
        mutate(context, "assign", patternArgs(selected).put("fit_revision", current.fitRevision))
    }
    fun resetUniform(context: Context) {
        val current = state ?: return
        if (!available || current.fitId == null) return
        mutate(context, "reset_uniform", JSONObject().put("fit_revision", current.fitRevision))
    }
    /** Identity-only operation: neither a Defense draft nor any display number is an input. */
    fun detach(context: Context) {
        val current = state ?: return
        val selection = current.selection
        if (!available || current.fitId == null || selection.kind != "named") return
        mutate(context, "detach_to_anonymous", JSONObject().put("pattern_id", selection.patternId)
            .put("revision", selection.patternRevision).put("binding_revision", selection.bindingRevision)
            .put("fit_revision", current.fitRevision))
    }
    fun confirmDelete() {
        val current = state ?: return; val entry = detail?.entry ?: return
        if (available && !dirty && !entry.readonly) deleteConfirmation = OfflineDamageDelete(current.context, entry)
    }
    fun dismissDelete() { deleteConfirmation = null }
    fun delete(context: Context) {
        val confirmation = deleteConfirmation ?: return
        if (!available || dirty || state?.context != confirmation.context || detail?.entry != confirmation.entry) {
            deleteConfirmation = null; error = "Deletion impact changed. Reload and review it before deleting."; return
        }
        deleteConfirmation = null
        mutate(context, "delete", patternArgs(confirmation.entry).put("bound_fit_count", confirmation.entry.boundFitCount)
            .put("bound_module_count", confirmation.entry.boundModuleCount).put("affected_fit_count", confirmation.entry.affectedFitCount))
    }
    fun history(context: Context, redo: Boolean) {
        if (available && !dirty) mutate(context, if (redo) "redo" else "undo", JSONObject())
    }
    private fun patternArgs(entry: OfflineDamageEntry) = JSONObject().put("pattern_id", entry.id).put("revision", entry.revision)
    private fun mutate(context: Context, operation: String, arguments: JSONObject, edit: OfflineDamageDraft? = null) {
        val current = state ?: return
        if (!available) return
        dispatch(context, OfflineDamageRequest(UUID.randomUUID().toString(), current.context, anchor, view, operation, OfflineFeatureCodec.json(arguments)), edit)
    }
    private fun accept(value: OfflineDamageState) {
        state = value; view = value.view
        if (view.selectedPatternId == null && value.selection.patternId != null && !dirty) {
            view = view.copy(selectedPatternId = value.selection.patternId, boundOffset = 0, moduleOffset = 0); refreshPending = true
        }
        val edit = draft
        if (edit != null && (edit.sessionId != value.context.sessionId || edit.sourceId != null &&
            (value.detail?.entry?.id != edit.sourceId || value.detail.entry.revision != edit.sourceRevision))) conflict = true
    }
    private fun dispatch(context: Context, input: OfflineDamageRequest, edit: OfflineDamageDraft?) {
        if (busy || cleared || !screenOpen) return
        try { input.json() } catch (_: Exception) { error = "The request is invalid. Check the name, search text and numeric values; your draft is kept."; return }
        generation = Math.addExact(generation, 1)
        val token = generation; val slot = Any(); owner = slot; busy = true; saving = !damageReadLike(input.operation); error = null
        val pending = try { request(context.applicationContext, input) } catch (_: Exception) {
            if (owner === slot && token == generation && screenOpen && !cleared && input.fitId == activeFit() && input.view == view && featureContext() == input.context) {
                busy = false; saving = false; owner = null; error = "The request could not be started. Your draft is kept."
            }; return
        }
        if (!damageReadLike(input.operation)) pendingMutation = PendingDamageMutation(screen, input, edit, pending)
        pending.whenCompleteAsync({ result, failure ->
            val resultContext = result?.state?.context?.takeIf { result.ok && !damageReadLike(input.operation) }
            val validContext = featureContext() == (resultContext ?: input.context)
            // Screen, request, context, fit and view must match before ANY state update.
            if (result != null && result.requestId != input.requestId) return@whenCompleteAsync
            if (owner !== slot || token != generation || cleared || !screenOpen || input.fitId != activeFit() ||
                input.view != view || !validContext) return@whenCompleteAsync
            owner = null; busy = false; saving = false
            if (result?.reopenRequired == true || failure != null && !damageReadLike(input.operation)) reopenRequired = true
            run {
                if (failure != null || result == null) error = if (damageReadLike(input.operation)) "Damage patterns could not be loaded. Reload to try again."
                    else "The save could not be confirmed. Keep your draft and restart the app to check saved changes."
                else if (!result.ok) {
                    error = result.error?.message ?: "The request was not completed."
                    if (dirty && result.error?.code in setOf("stale_pattern", "missing_pattern", "stale_context")) conflict = true
                    // A removed selected pattern must not make the library impossible to reload.
                    if (result.error?.code == "missing_pattern") {
                        val reconciled = reconcileCompletedMutation(checkNotNull(featureContext()), activeFit())
                        if (!reconciled) view = view.copy(selectedPatternId = null, boundOffset = 0, moduleOffset = 0)
                        else { error = null; refreshPending = true }
                    }
                } else if (result.state?.context != featureContext()) {
                    error = "Inputs changed while loading. Reload to use current saved values."; refreshPending = true
                } else {
                    if (edit != null && draft === edit) { draft = null; conflict = false }
                    val value = checkNotNull(result.state)
                    val reconciled = damageReadLike(input.operation) && reconcileCompletedMutation(value.context, value.fitId)
                    if (reconciled && view != value.view) { state = value; refreshPending = true } else accept(value)
                    if (!damageReadLike(input.operation)) pendingMutation = null
                    if (!damageReadLike(input.operation)) message = if (result.committed != true) "No saved values changed." else when (input.operation) {
                        "detach_to_anonymous" -> "Detached to Anonymous using saved contributions. Unsaved edits were not applied."
                        "reset_uniform" -> "This fit now uses the built-in Uniform pattern."
                        "assign" -> "This fit now uses the selected named pattern."
                        "delete" -> "Pattern deleted. Incoming fits use Uniform; local hardeners follow their Fit Pattern."
                        else -> "Saved. Shared pattern changes apply to every incoming-fit and local-hardener holder."
                    }
                }
            }
            if (refreshPending && !reopenRequired && engineAvailable()) read(context)
        }, ContextCompat.getMainExecutor(context))
    }
    /**
     * Context publication can invalidate a save callback before it reaches the UI.
     * Only a NEW, fully owned authoritative read reconciles that completed result.
     * The obsolete callback itself never clears a flag, draft, selection or error.
     */
    private fun reconcileCompletedMutation(current: OfflineContext, fitId: String?): Boolean {
        val pending = pendingMutation ?: return false
        if (!pending.future.isDone) return false
        pendingMutation = null
        val result = try { pending.future.getNow(null) } catch (_: Exception) { null } ?: return false
        val resultState = result.state ?: return false
        if (pending.screen != screen || pending.input.fitId != activeFit() || pending.input.view != view ||
            result.requestId != pending.input.requestId || resultState.context.sessionId != pending.input.context.sessionId ||
            resultState.context.datasetSha256 != pending.input.context.datasetSha256 || !result.ok || resultState.context != current || resultState.fitId != fitId) return false
        if (pending.draft != null && draft === pending.draft) { draft = null; conflict = false }
        val selected = resultState.detail?.entry?.id
        if (selected != view.selectedPatternId) {
            view = view.copy(selectedPatternId = selected, boundOffset = 0, moduleOffset = 0); refreshPending = true
        }
        message = if (result.committed != true) "No saved values changed." else when (pending.input.operation) {
            "detach_to_anonymous" -> "Detached to Anonymous using saved contributions. Unsaved edits were not applied."
            "delete" -> "Pattern deleted. Incoming fits use Uniform; local hardeners follow their Fit Pattern."
            else -> "Saved. Shared pattern changes apply to every incoming-fit and local-hardener holder."
        }
        return true
    }
    override fun onCleared() { cleared = true; close() }
}

@Composable
internal fun OfflineDamagePatternsView(model: OfflineDamagePatternsModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val features by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    var confirmLeave by rememberSaveable { mutableStateOf(false) }
    fun leave() { if (model.dirty) confirmLeave = true else { model.close(); onBack() } }
    DisposableEffect(model) { model.open(); onDispose { model.close() } }
    BackHandler { leave() }
    LaunchedEffect(features?.context, fit?.id, fit?.revision) { model.synchronize(context, features?.context, fit?.id, fit?.revision) }
    Text("Named damage patterns", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { leave() }, modifier = Modifier.testTag("damage-patterns-back")) { Text("Back") }
    Text("118 read-only built-ins in original source order, then protected Selected Ammo when created, then your custom patterns. Contributions are not percentages.")
    if (model.reopenRequired) Text("Restart the app before making more changes. The last operation could not be confirmed.", color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("damage-patterns-reopen"))
    if (model.busy) Text(if (model.saving) "Saving and recalculating…" else "Loading patterns…", Modifier.testTag("damage-patterns-busy"))
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("damage-patterns-error")) }
    model.message?.let { Text(it, Modifier.testTag("damage-patterns-message")) }
    TextButton(onClick = { model.reload(context) }, enabled = !model.busy && !model.reopenRequired, modifier = Modifier.testTag("damage-patterns-reload")) { Text("Reload saved patterns") }
    val state = model.state
    if (state != null) {
        val selectedName = state.selection.patternId?.let { id -> state.entries.find { it.id == id }?.name ?: state.detail?.entry?.takeIf { it.id == id }?.name ?: id }
        Text(when (state.selection.kind) {
            "no_fit" -> "No fit open. Manage the library without assigning a fit."
            "anonymous" -> "${fit?.name ?: "Fit"}: Anonymous incoming damage"
            else -> "${fit?.name ?: "Fit"}: $selectedName"
        }, Modifier.testTag("damage-patterns-selection"))
        Row {
            TextButton(onClick = { model.history(context, false) }, enabled = model.available && !model.dirty && state.history.undoCount > 0,
                modifier = Modifier.testTag("damage-patterns-undo")) { Text("Undo") }
            TextButton(onClick = { model.history(context, true) }, enabled = model.available && !model.dirty && state.history.redoCount > 0,
                modifier = Modifier.testTag("damage-patterns-redo")) { Text("Redo") }
        }
        Text(state.history.undoLabel?.let { "Undo: $it" } ?: "No undo action")
    }
    OutlinedTextField(model.view.query, { model.search(context, it) }, enabled = !model.saving && !model.dirty,
        label = { Text("Search damage patterns") }, singleLine = true, modifier = Modifier.fillMaxWidth().testTag("damage-patterns-search"))
    if (state != null) {
        Text("${state.total} matching patterns · offset ${state.view.offset}", Modifier.testTag("damage-patterns-page"))
        var section: String? = null
        for (entry in state.entries) {
            if (section != entry.kind) {
                section = entry.kind
                Text(when (entry.kind) { "builtin" -> "Built-in patterns · original order"; "selected_ammo" -> "Selected-item pattern"; else -> "Custom patterns" }, style = MaterialTheme.typography.titleMedium)
            }
            TextButton(onClick = { model.select(context, entry.id) }, enabled = !model.saving && !model.dirty,
                modifier = Modifier.testTag("damage-pattern-select-${entry.id}")) {
                Text((if (model.view.selectedPatternId == entry.id) "✓ " else "") + entry.name +
                    (when (entry.kind) { "builtin" -> " · built-in"; "selected_ammo" -> " · protected"; else -> " · custom" }) + if (!entry.assignable) " · not assignable (zero total)" else "")
            }
        }
        Row {
            TextButton(onClick = { model.page(context, (model.view.offset - 50).coerceAtLeast(0)) }, enabled = !model.busy && !model.dirty && model.view.offset > 0,
                modifier = Modifier.testTag("damage-patterns-previous")) { Text("Previous") }
            TextButton(onClick = { model.page(context, model.view.offset + 50) }, enabled = !model.busy && !model.dirty && model.view.offset < state.total - 50,
                modifier = Modifier.testTag("damage-patterns-next")) { Text("Next") }
        }
    }
    Button(onClick = { model.begin("create") }, enabled = model.available && !model.dirty, modifier = Modifier.testTag("damage-pattern-create")) { Text("Create pattern") }
    if (state?.fitId != null) TextButton(onClick = { model.resetUniform(context) }, enabled = model.available && !model.dirty && state.selection.patternId != "damage:builtin:-1",
        modifier = Modifier.testTag("damage-pattern-reset-uniform")) { Text("Reset fit to Uniform") }
    model.detail?.let { detail ->
        val entry = detail.entry
        Text("${entry.name} · ${entry.kind} · ${entry.boundFitCount} incoming fit(s), ${entry.boundModuleCount} local hardener(s), ${entry.affectedFitCount} directly affected fit(s)", style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("damage-pattern-selected"))
        Text("Identity: ${entry.id}")
        if (entry.kind == "builtin") Text("Built-in values are read-only. Duplicate to make an independent custom pattern.", Modifier.testTag("damage-pattern-readonly"))
        for ((index, key) in DAMAGE_PATTERN_FIELDS.withIndex()) {
            Text("${DAMAGE_PATTERN_LABELS[index]}: raw ${detail.values.fields.getValue(key)} · ${detail.percentages.fields.getValue(key)}%",
                Modifier.testTag("damage-pattern-value-$key"))
        }
        if (!entry.assignable) Text("Not assignable: total is zero. Enter a positive contribution before using this pattern for a fit.",
            Modifier.testTag("damage-pattern-unassignable"))
        if (state?.fitId != null) Button(onClick = { model.assign(context) }, enabled = model.available && !model.dirty && entry.assignable && state.selection.patternId != entry.id,
            modifier = Modifier.testTag("damage-pattern-assign")) { Text("Use for ${fit?.name ?: "this fit"}") }
        if (entry.kind == "selected_ammo") Text("Updated only from a selected equipment item. Changes affect every incoming fit and local hardener using Selected Ammo.")
        Row {
            if (entry.duplicable) TextButton(onClick = { model.begin("duplicate") }, enabled = model.available && !model.dirty, modifier = Modifier.testTag("damage-pattern-duplicate")) { Text("Duplicate") }
            if (!entry.readonly) {
                TextButton(onClick = { model.begin("update_values") }, enabled = model.available && !model.dirty, modifier = Modifier.testTag("damage-pattern-edit")) { Text("Edit values") }
                TextButton(onClick = { model.begin("rename") }, enabled = model.available && !model.dirty, modifier = Modifier.testTag("damage-pattern-rename")) { Text("Rename") }
            }
        }
        Text("Bound saved fits (${entry.boundFitCount}):", Modifier.testTag("damage-pattern-bound-count"))
        detail.boundFits.forEach { Text(it.name, Modifier.testTag("damage-pattern-bound-${it.id}")) }
        Row {
            TextButton(onClick = { model.boundPage(context, (detail.boundOffset - 50).coerceAtLeast(0)) }, enabled = !model.busy && detail.boundOffset > 0,
                modifier = Modifier.testTag("damage-pattern-bound-previous")) { Text("Previous fits") }
            TextButton(onClick = { model.boundPage(context, detail.boundOffset + 50) }, enabled = !model.busy && detail.boundOffset < entry.boundFitCount - 50,
                modifier = Modifier.testTag("damage-pattern-bound-next")) { Text("Next fits") }
        }
        Text("Local hardeners (${entry.boundModuleCount}):", Modifier.testTag("damage-pattern-module-count"))
        detail.boundModules.forEach { Text("${it.fitName} · ${it.position + 1} · ${it.name}", Modifier.testTag("damage-pattern-module-${it.fitId}-${it.objectKey}")) }
        Row {
            TextButton(onClick = { model.modulePage(context, (detail.moduleOffset - 50).coerceAtLeast(0)) }, enabled = !model.busy && detail.moduleOffset > 0,
                modifier = Modifier.testTag("damage-pattern-module-previous")) { Text("Previous hardeners") }
            TextButton(onClick = { model.modulePage(context, detail.moduleOffset + 50) }, enabled = !model.busy && detail.moduleOffset < entry.boundModuleCount - 50,
                modifier = Modifier.testTag("damage-pattern-module-next")) { Text("Next hardeners") }
        }
        if (!entry.readonly) TextButton(onClick = model::confirmDelete, enabled = model.available && !model.dirty,
            modifier = Modifier.testTag("damage-pattern-delete")) { Text("Delete pattern…") }
    }
    model.draft?.let { draft ->
        Text("Unsaved ${draft.operation.replace('_', ' ')} draft", style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("damage-pattern-dirty"))
        if (draft.operation != "update_values") OutlinedTextField(draft.name, model::editName, enabled = !model.saving,
            label = { Text("Custom pattern name") }, modifier = Modifier.fillMaxWidth().testTag("damage-pattern-name"))
        if (draft.operation in setOf("create", "update_values")) {
            Text("Enter raw contributions, not percentages. Blank means zero. Unassigned zero-total patterns may be saved; bound patterns require a positive total.")
            DAMAGE_PATTERN_FIELDS.forEachIndexed { index, key -> OutlinedTextField(draft.fields[index], { model.editField(index, it) }, enabled = !model.saving,
                label = { Text(DAMAGE_PATTERN_LABELS[index]) }, modifier = Modifier.fillMaxWidth().testTag("damage-pattern-edit-$key")) }
        }
        if (model.conflict) Text("The source pattern or session changed. Your draft is kept; cancel it before editing the new saved state.", color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("damage-pattern-conflict"))
        Row {
            Button(onClick = { model.save(context) }, enabled = model.canSave, modifier = Modifier.testTag("damage-pattern-save")) { Text("Save") }
            TextButton(onClick = model::cancelDraft, enabled = !model.saving, modifier = Modifier.testTag("damage-pattern-cancel")) { Text("Cancel draft") }
        }
    }
    model.deleteConfirmation?.let { confirmation -> AlertDialog(onDismissRequest = model::dismissDelete,
        title = { Text("Delete ${confirmation.entry.name}?") },
        text = { Text("Exactly ${confirmation.entry.boundFitCount} incoming fit(s) switch to Uniform and ${confirmation.entry.boundModuleCount} local hardener(s) follow their respective Fit Pattern, across ${confirmation.entry.affectedFitCount} distinct directly affected fit(s). A fit in both sets receives both changes. Linked dependents may recalculate. All changes are atomic and can be undone during this session.") },
        confirmButton = { TextButton(onClick = { model.delete(context) }, modifier = Modifier.testTag("damage-pattern-delete-confirm")) { Text("Delete and apply fallbacks") } },
        dismissButton = { TextButton(onClick = model::dismissDelete) { Text("Cancel") } }) }
    if (confirmLeave) AlertDialog(onDismissRequest = { confirmLeave = false }, title = { Text("Keep unsaved damage-pattern draft?") },
        text = { Text("Your draft will remain here while the app stays open.") },
        confirmButton = { TextButton(onClick = { confirmLeave = false; model.close(); onBack() }, modifier = Modifier.testTag("damage-pattern-leave-keep")) { Text("Keep draft and go back") } },
        dismissButton = { TextButton(onClick = { confirmLeave = false }) { Text("Stay") } })
}
