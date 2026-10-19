package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.UUID
import java.util.concurrent.CompletableFuture
import kotlinx.coroutines.Dispatchers
import org.json.JSONObject

/** These drafts contain names only; recipe and destination rows are never wire inputs. */
data class OfflineImplantSetDraft(val operation: String, val sourceId: String?, val sourceRevision: Long?,
    val sessionId: String, val name: String, val saveSource: OfflineImplantSaveSource? = null)
data class OfflineImplantSetDelete(val context: OfflineContext, val detail: OfflineImplantSetDetail)
data class OfflineImplantSetAddChoice(val context: OfflineContext, val detail: OfflineImplantSetDetail)
data class OfflineImplantSetReplacement(val choice: OfflineImplantSetAddChoice, val item: CharacterImplantItem,
    val occupant: OfflineImplantSetItem)
enum class OfflineImplantApplyDisposition { ADDED, REPLACED, DUPLICATE_SKIPPED }
data class OfflineImplantApplyStep(val item: OfflineImplantSetItem, val disposition: OfflineImplantApplyDisposition,
    val occupant: OfflineImplantCollectionRow?)
data class OfflineImplantApplicationReview(val context: OfflineContext, val anchorFitId: String?,
    val view: OfflineImplantSetView, val detail: OfflineImplantSetDetail, val destination: OfflineImplantSetDestination,
    val saveSource: OfflineImplantSaveSource?, val steps: List<OfflineImplantApplyStep>, val untouched: List<OfflineImplantCollectionRow>)

/** Presentation only. The authority repeats the ordered merge and validates all revisions. */
internal fun implantApplicationReview(state: OfflineImplantSetState): OfflineImplantApplicationReview? {
    val detail = state.detail ?: return null
    val destination = state.destination ?: return null
    data class PreviewMember(val itemId: Int, val slot: Int, val original: OfflineImplantCollectionRow?)
    val remaining = destination.implants.map { PreviewMember(it.itemId, it.slot, it) }.toMutableList()
    val encountered = mutableSetOf<String>()
    val steps = detail.items.map { item ->
        val duplicate = remaining.firstOrNull { it.itemId == item.itemId }
        if (destination is OfflineImplantSetDestination.Fit && duplicate != null) {
            duplicate.original?.let { encountered.add(it.rowId) }
            OfflineImplantApplyStep(item, OfflineImplantApplyDisposition.DUPLICATE_SKIPPED, duplicate.original)
        } else {
            val occupant = remaining.firstOrNull { it.slot == item.slot }
            if (occupant != null) { remaining.remove(occupant); occupant.original?.let { encountered.add(it.rowId) } }
            // Local merge accounting has no invented row identity or writable collection.
            remaining.add(PreviewMember(item.itemId, item.slot, null))
            OfflineImplantApplyStep(item, if (occupant == null) OfflineImplantApplyDisposition.ADDED else OfflineImplantApplyDisposition.REPLACED, occupant?.original)
        }
    }
    return OfflineImplantApplicationReview(state.context, state.anchorFitId, state.view, detail, destination,
        state.saveSource, steps.toList(), destination.implants.filter { it.rowId !in encountered })
}

/** One actual owned future, including catalogue reads. Back/cancel never frees an in-flight worker. */
class OfflineImplantSetsModel(
    private val featureContext: () -> OfflineContext? = { EngineRuntime.offlineFeatures.value?.context },
    private val activeFit: () -> String? = { EngineRuntime.navigation.value.activeId },
    private val engineAvailable: () -> Boolean = { when (val engine = EngineRuntime.state.value) {
        is EngineState.Ready -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        is EngineState.Empty -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        else -> false
    } },
    private val request: (Context, OfflineImplantSetRequest) -> CompletableFuture<OfflineImplantSetResponse> = EngineRuntime::offlineImplantSets,
    private val loadCatalogue: (Context) -> CompletableFuture<CharacterImplantCatalog> = EngineRuntime::characterImplantCatalog,
) : ViewModel() {
    var state by mutableStateOf<OfflineImplantSetState?>(null); private set
    var view by mutableStateOf(OfflineImplantSetView()); private set
    var draft by mutableStateOf<OfflineImplantSetDraft?>(null); private set
    var busy by mutableStateOf(false); private set
    var saving by mutableStateOf(false); private set
    var reopenRequired by mutableStateOf(false); private set
    var conflict by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var skillDraftPending by mutableStateOf(false); private set
    var deleteConfirmation by mutableStateOf<OfflineImplantSetDelete?>(null); private set
    var applicationReview by mutableStateOf<OfflineImplantApplicationReview?>(null); private set
    var addChoice by mutableStateOf<OfflineImplantSetAddChoice?>(null); private set
    var replacement by mutableStateOf<OfflineImplantSetReplacement?>(null); private set
    var catalogue by mutableStateOf<CharacterImplantCatalog?>(null); private set
    var itemQuery by mutableStateOf(""); private set
    var itemPage by mutableStateOf(0); private set
    private var catalogueSession: String? = null
    private var anchor: String? = null
    private var observedContext: OfflineContext? = null
    private var observedRevision: Long? = null
    private var owner: Any? = null
    private var generation = 0L
    private var viewEpoch = 0L
    private var refreshPending = false
    private var reviewAfterRead = false
    private var visible = true
    private var cleared = false
    // A hidden success can settle the submitted draft on return, but cannot publish a hidden result.
    private var settledDraft: OfflineImplantSetDraft? = null
    val dirty get() = draft != null
    val detail get() = state?.detail?.takeIf { it.entry.id == view.selectedSetId }
    val available get() = visible && !cleared && !busy && !reopenRequired && engineAvailable() && state != null &&
        state?.context == featureContext() && state?.anchorFitId == activeFit() && state?.anchorFitId == anchor &&
        state?.view?.query == view.query && state?.view?.offset == view.offset &&
        state?.view?.selectedSetId == view.selectedSetId && state?.view?.targetProfileId == view.targetProfileId
    val canSave get() = available && dirty && !conflict
    val historyCurrent get() = state?.view?.historyTarget == view.historyTarget
    val addChoiceCurrent get() = addChoice?.let { available && !dirty && it.context == state?.context && it.detail == detail && !it.detail.entry.readonly } == true
    val replacementCurrent get() = replacement?.let { addChoiceCurrent && it.choice == addChoice && catalogue?.itemById?.get(it.item.itemId) == it.item } == true
    val reviewCurrent get() = applicationReview?.let { review -> available && !dirty &&
        review.context == state?.context && review.anchorFitId == anchor && review.view == view &&
        review.detail == detail && review.destination == state?.destination && review.saveSource == state?.saveSource &&
        !(review.destination is OfflineImplantSetDestination.Profile && skillDraftPending) } == true
    val matchingItems get() = catalogue?.items.orEmpty().filter { it.name.contains(itemQuery, ignoreCase = true) }

    fun preserveSkillDraft(pending: Boolean) {
        skillDraftPending = pending
        if (pending && applicationReview?.destination is OfflineImplantSetDestination.Profile) applicationReview = null
    }
    fun openForFit(): Boolean {
        if (dirty || saving) return false
        view = view.copy(targetProfileId = null, historyTarget = "library"); viewEpoch++; refreshPending = true
        return true
    }
    fun openForProfile(id: String): Boolean {
        if (dirty || saving || skillDraftPending) return false
        view = view.copy(targetProfileId = id, historyTarget = "library"); viewEpoch++; refreshPending = true
        return true
    }
    fun enter(context: Context) {
        if (cleared) return
        visible = true
        val completed = settledDraft
        if (completed != null) {
            if (draft === completed && completed.sessionId == featureContext()?.sessionId) { draft = null; conflict = false }
            settledDraft = null
        }
        refreshPending = true
        if (!busy) read(context)
    }
    fun leave() {
        visible = false; viewEpoch++; generation++; refreshPending = true; reviewAfterRead = false
        deleteConfirmation = null; applicationReview = null; replacement = null; addChoice = null
    }
    fun synchronize(context: Context, current: OfflineContext?, fitId: String?, fitRevision: Long?) {
        if (current == observedContext && fitId == anchor && fitRevision == observedRevision && state != null && !refreshPending) return
        val previousSession = observedContext?.sessionId
        if (previousSession != null && previousSession != current?.sessionId) {
            reopenRequired = false; catalogue = null; catalogueSession = null; settledDraft = null
            if (dirty) conflict = true
        }
        if (anchor != fitId && view.historyTarget != "library") view = view.copy(historyTarget = "library")
        observedContext = current; observedRevision = fitRevision; anchor = fitId
        deleteConfirmation = null; applicationReview = null; replacement = null
        reload(context)
    }
    fun reload(context: Context) {
        generation++; refreshPending = true
        if (!busy) read(context)
    }
    private fun read(context: Context) {
        if (!visible || cleared || busy || reopenRequired || !engineAvailable()) return
        val expected = featureContext() ?: return
        // The view may be re-entered before its effect synchronizes the active fit.
        if (anchor != activeFit()) return
        refreshPending = false
        dispatch(context, OfflineImplantSetRequest(UUID.randomUUID().toString(), expected, anchor, view), null)
    }
    private fun browse(context: Context, next: OfflineImplantSetView) {
        if (saving || dirty || next == view) return
        view = next; viewEpoch++; deleteConfirmation = null; applicationReview = null; addChoice = null; replacement = null
        reviewAfterRead = false; message = null; reload(context)
    }
    fun search(context: Context, text: String) { browse(context, view.copy(query = text, offset = 0)) }
    fun page(context: Context, offset: Long) { if (offset >= 0) browse(context, view.copy(offset = offset)) }
    fun select(context: Context, id: String) {
        if (state?.entries?.none { it.id == id } != false) return
        browse(context, view.copy(selectedSetId = id))
    }
    fun destination(context: Context, profileId: String?) {
        if (profileId != null && skillDraftPending) { error = "Save or revert the character skill draft before choosing a character destination."; return }
        browse(context, view.copy(targetProfileId = profileId))
    }
    fun chooseHistory(context: Context, target: String) {
        if (target != "library" && target != anchor) return
        browse(context, view.copy(historyTarget = target))
    }
    fun begin(operation: String) {
        if (!available || dirty || addChoice != null) return
        val selected = detail?.entry
        if (operation !in setOf("create", "rename", "duplicate", "save_current")) return
        if (operation in setOf("rename", "duplicate") && (selected == null || selected.readonly)) return
        val source = state?.saveSource
        if (operation == "save_current" && (source == null || source.implantCount == 0L)) return
        draft = OfflineImplantSetDraft(operation, if (operation in setOf("rename", "duplicate")) selected?.id else null,
            if (operation in setOf("rename", "duplicate")) selected?.revision else null, checkNotNull(state).context.sessionId,
            if (operation == "rename") checkNotNull(selected).name else "", if (operation == "save_current") source else null)
        conflict = false; error = null; message = null; applicationReview = null; deleteConfirmation = null
    }
    fun editName(text: String) { if (!saving) draft = draft?.copy(name = text) }
    fun cancelDraft() { if (!saving) { draft = null; conflict = false; error = null; settledDraft = null } }
    fun save(context: Context) {
        val edit = draft ?: return
        if (!canSave) return
        val args = try {
            JSONObject().put("name", OfflineImplantSetsCodec.name(edit.name)).also {
                if (edit.sourceId != null) it.put("set_id", edit.sourceId).put("revision", edit.sourceRevision)
                if (edit.saveSource != null) it.put("fit_revision", edit.saveSource.fitRevision)
            }
        } catch (_: Exception) { error = "Use a nonempty name of up to 200 Unicode characters without controls. Your draft is kept."; return }
        mutate(context, edit.operation, args, "library", edit)
    }
    fun confirmDelete() {
        val current = state ?: return; val selected = detail ?: return
        if (available && !dirty && !selected.entry.readonly) deleteConfirmation = OfflineImplantSetDelete(current.context, selected)
    }
    fun dismissDelete() { if (!saving) deleteConfirmation = null }
    fun delete(context: Context) {
        val pending = deleteConfirmation ?: return
        if (!available || dirty || pending.context != state?.context || pending.detail != detail) {
            deleteConfirmation = null; error = "The saved set changed. Reload and review it before deleting."; return
        }
        deleteConfirmation = null
        mutate(context, "delete", setArgs(pending.detail.entry), "library")
    }
    fun openPicker(context: Context) {
        val current = state ?: return; val selected = detail ?: return
        if (!available || dirty || selected.entry.readonly) return
        addChoice = OfflineImplantSetAddChoice(current.context, selected); itemQuery = ""; itemPage = 0
        if (catalogueSession == current.context.sessionId && catalogue?.datasetSha256 == current.context.datasetSha256 && catalogue?.error == null) return
        val slot = Any(); owner = slot; busy = true; val epoch = viewEpoch
        val pending = try { loadCatalogue(context.applicationContext) } catch (_: Exception) {
            owner = null; busy = false; error = "Implant metadata could not be loaded. Close and reopen the picker to retry."; return
        }
        pending.whenCompleteAsync({ value, failure ->
            if (owner !== slot) return@whenCompleteAsync
            owner = null; busy = false
            if (cleared) return@whenCompleteAsync
            if (visible && epoch == viewEpoch && current.context.sessionId == featureContext()?.sessionId &&
                current.context.datasetSha256 == featureContext()?.datasetSha256) {
                if (failure != null || value == null || value.error != null || value.datasetSha256 != current.context.datasetSha256)
                    error = "Implant metadata could not be verified. Close and reopen the picker to retry."
                else { catalogue = value; catalogueSession = current.context.sessionId }
            }
            if (refreshPending) read(context)
        }, ContextCompat.getMainExecutor(context))
    }
    fun closePicker() {
        if (saving) return
        addChoice = null; replacement = null
        // A catalogue callback is now obsolete, but keeps its real owner until completion.
        viewEpoch++
    }
    fun searchItems(text: String) { if (!saving) { itemQuery = text; itemPage = 0 } }
    fun pageItems(page: Int) { if (!saving) itemPage = page.coerceIn(0, ((matchingItems.size - 1).coerceAtLeast(0)) / 25) }
    fun chooseItem(context: Context, item: CharacterImplantItem) {
        val choice = addChoice ?: return
        if (!addChoiceCurrent || catalogue?.itemById?.get(item.itemId) != item) return
        val occupant = choice.detail.items.singleOrNull { it.slot == item.slot }
        if (occupant != null) replacement = OfflineImplantSetReplacement(choice, item, occupant)
        else addItem(context, choice, item, null)
    }
    fun dismissReplacement() { if (!saving) replacement = null }
    fun replaceItem(context: Context) {
        val pending = replacement ?: return
        if (!replacementCurrent) { error = "The recipe changed. Cancel and review the current slot."; return }
        addItem(context, pending.choice, pending.item, pending.occupant.itemId)
    }
    private fun addItem(context: Context, choice: OfflineImplantSetAddChoice, item: CharacterImplantItem, occupant: Int?) {
        if (!addChoiceCurrent || choice != addChoice) return
        mutate(context, "add_item", setArgs(choice.detail.entry).put("item_id", item.itemId)
            .put("replace_item_id", occupant ?: JSONObject.NULL), "library")
    }
    fun removeItem(context: Context, item: OfflineImplantSetItem) {
        val selected = detail ?: return
        if (!available || dirty || selected.entry.readonly || item !in selected.items) return
        mutate(context, "remove_item", setArgs(selected.entry).put("item_id", item.itemId), "library")
    }
    fun reviewApplication(context: Context) {
        if (!available || dirty || detail == null || addChoice != null) return
        val destination = state?.destination ?: return
        val target = when (destination) {
            is OfflineImplantSetDestination.Fit -> { if (destination.isStructure) return; destination.fitId }
            is OfflineImplantSetDestination.Profile -> { if (destination.readonly || skillDraftPending) return; "library" }
        }
        if (view.historyTarget != target) {
            // The button explicitly names the timeline. Refresh it before displaying the review.
            view = view.copy(historyTarget = target); viewEpoch++; reviewAfterRead = true; reload(context)
        } else applicationReview = implantApplicationReview(checkNotNull(state))
    }
    fun dismissApplication() { if (!saving) { applicationReview = null; reviewAfterRead = false } }
    fun apply(context: Context) {
        val review = applicationReview ?: return
        if (!reviewCurrent) { applicationReview = null; error = "The recipe or destination changed. Review the current saved values again."; return }
        val args = setArgs(review.detail.entry)
        when (val destination = review.destination) {
            is OfflineImplantSetDestination.Fit -> {
                if (destination.isStructure) return
                mutate(context, "apply_fit", args.put("fit_revision", destination.fitRevision), destination.fitId)
            }
            is OfflineImplantSetDestination.Profile -> {
                if (destination.readonly || skillDraftPending) return
                mutate(context, "apply_profile", args.put("profile_id", destination.profileId).put("profile_revision", destination.profileRevision), "library")
            }
        }
    }
    fun history(context: Context, redo: Boolean) {
        if (!available || dirty || !historyCurrent || addChoice != null) return
        val history = state?.history ?: return
        if (if (redo) history.redoCount == 0 else history.undoCount == 0) return
        mutate(context, if (redo) "redo" else "undo", JSONObject(), view.historyTarget)
    }
    private fun setArgs(entry: OfflineImplantSetEntry) = JSONObject().put("set_id", entry.id).put("revision", entry.revision)
    private fun mutate(context: Context, operation: String, arguments: JSONObject, historyTarget: String, edit: OfflineImplantSetDraft? = null) {
        val current = state ?: return
        if (!available) return
        view = view.copy(historyTarget = historyTarget)
        dispatch(context, OfflineImplantSetRequest(UUID.randomUUID().toString(), current.context, anchor, view, operation,
            OfflineFeatureCodec.json(arguments)), edit)
    }
    private fun accept(value: OfflineImplantSetState) {
        state = value; view = value.view; anchor = value.anchorFitId
        // Back then immediate return can precede the old worker's completion. Settle
        // that exact successful draft only with this subsequently accepted fresh view.
        settledDraft?.let { completed ->
            if (draft === completed && completed.sessionId == value.context.sessionId) { draft = null; conflict = false }
            settledDraft = null
        }
        val edit = draft
        val savedEntry = value.detail?.entry
        if (edit != null && (edit.sessionId != value.context.sessionId || edit.sourceId != null &&
                (savedEntry?.id != edit.sourceId || savedEntry?.revision != edit.sourceRevision) ||
                edit.saveSource != null && edit.saveSource != value.saveSource)) conflict = true
        if (addChoice?.let { it.context != value.context || it.detail != value.detail } == true) { addChoice = null; replacement = null }
        if (reviewAfterRead) {
            reviewAfterRead = false
            applicationReview = implantApplicationReview(value)?.takeIf {
                when (val target = it.destination) {
                    is OfflineImplantSetDestination.Fit -> !target.isStructure && view.historyTarget == target.fitId
                    is OfflineImplantSetDestination.Profile -> !target.readonly && !skillDraftPending && view.historyTarget == "library"
                }
            }
        }
    }
    private fun dispatch(context: Context, input: OfflineImplantSetRequest, edit: OfflineImplantSetDraft?) {
        if (busy || cleared || !visible) return
        // Everything passed to the worker is immutable, including the already encoded arguments.
        try { input.json() } catch (_: Exception) { error = "The request is invalid. Check the name or search text; your draft is kept."; return }
        val before = state; val token = ++generation; val epoch = viewEpoch; val slot = Any()
        owner = slot; busy = true; saving = input.operation != "read"; error = null; message = null
        val mutation = input.operation != "read"
        val pending = try { request(context.applicationContext, input) } catch (_: Exception) {
            owner = null; busy = false; saving = false
            // A transport may throw after enqueueing. Never infer that a mutation did not execute.
            if (mutation) { reopenRequired = true; error = "The change could not be confirmed. Restart the app before making more changes." }
            else error = "Implant sets could not be loaded. Reload to try again."
            return
        }
        pending.whenCompleteAsync({ result, failure ->
            if (owner !== slot) return@whenCompleteAsync
            owner = null; busy = false; saving = false
            if (cleared) return@whenCompleteAsync
            val valid = failure == null && result != null && try {
                OfflineImplantSetsCodec.validateResult(result, input, before); true
            } catch (_: Exception) { false }
            val uncertain = result?.reopenRequired == true || mutation && (!valid || result?.committed == null)
            // An old session cannot poison a successfully reopened one.
            if (uncertain && input.context.sessionId == featureContext()?.sessionId) reopenRequired = true
            val current = result?.state
            val replayDisappearance = result?.ok == true && current != null && input.operation in setOf("undo", "redo") &&
                input.anchorFitId != null && current.anchorFitId == null && activeFit() == null
            val expectedView = if (replayDisappearance && input.view.historyTarget != "library") input.view.copy(historyTarget = "library") else input.view
            val sameView = visible && epoch == viewEpoch && (input.anchorFitId == anchor || replayDisappearance) &&
                (input.anchorFitId == activeFit() || replayDisappearance) &&
                expectedView == view &&
                (mutation || token == generation)
            if (valid && result?.ok == true && edit != null && draft === edit && input.context.sessionId == featureContext()?.sessionId) {
                if (sameView) { draft = null; conflict = false } else settledDraft = edit
            }
            if (sameView) {
                if (!valid || uncertain) {
                    error = if (mutation) "The change could not be confirmed. Keep your draft and restart the app to check saved changes."
                        else "Implant sets could not be loaded safely. Reload to try again."
                } else if (result?.ok != true) {
                    error = result?.error?.message ?: "The request was not completed."
                    if (dirty && result?.error?.code in setOf("stale_context", "stale_set", "missing_set", "stale_profile", "conflict")) conflict = true
                } else if (current?.context != featureContext()) {
                    refreshPending = true
                    error = "Saved inputs changed while loading. Reloading the current values."
                } else {
                    if (mutation) { applicationReview = null; deleteConfirmation = null; replacement = null; addChoice = null }
                    accept(checkNotNull(current))
                    if (mutation) message = if (result?.committed != true) "No saved values changed." else when (input.operation) {
                        "apply_fit" -> "Applied to fit-specific implants. The active implant source is unchanged; no set binding was created."
                        "apply_profile" -> "Applied to the character. Shared assigned fits were refreshed; their source selections are unchanged."
                        "save_current" -> "Saved the applied source as an independent recipe, including inactive implants. The source is unchanged."
                        "delete" -> "Deleted the recipe only. Previously applied fit and character implants are unchanged."
                        else -> "Saved. Recipes and previously applied collections remain independent."
                    }
                }
            }
            if (refreshPending && !reopenRequired) read(context)
        }, ContextCompat.getMainExecutor(context))
    }
    override fun onCleared() { cleared = true; visible = false; generation++; viewEpoch++; super.onCleared() }
}

@Composable
internal fun OfflineImplantSetsView(model: OfflineImplantSetsModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val features by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    var confirmLeave by rememberSaveable { mutableStateOf(false) }
    fun leave() {
        when {
            model.saving -> { model.leave(); onBack() }
            model.replacement != null -> model.dismissReplacement()
            model.applicationReview != null -> model.dismissApplication()
            model.addChoice != null -> model.closePicker()
            model.dirty -> confirmLeave = true
            else -> { model.leave(); onBack() }
        }
    }
    BackHandler { leave() }
    DisposableEffect(model) { model.enter(context); onDispose { model.leave() } }
    LaunchedEffect(features?.context, fit?.id, fit?.revision) { model.synchronize(context, features?.context, fit?.id, fit?.revision) }
    Text("Named implant sets", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { leave() }, modifier = Modifier.testTag("implant-sets-back")) { Text("Back") }
    Text("Sets are independent ordered recipes, not live bindings. Applying a set never changes the fit's active implant source.")
    if (model.busy) Text(if (model.saving) "Saving and recalculating… You may go back; the operation is still owned until it finishes." else "Loading saved implant sets…", Modifier.testTag("implant-sets-busy"))
    if (model.reopenRequired) Text("Restart the app before making more changes. The last operation could not be confirmed.", color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("implant-sets-reopen"))
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("implant-sets-error")) }
    model.message?.let { Text(it, Modifier.testTag("implant-sets-message")) }
    TextButton(onClick = { model.reload(context) }, enabled = !model.busy && !model.reopenRequired,
        modifier = Modifier.testTag("implant-sets-reload")) { Text("Reload saved sets") }
    val state = model.state
    if (state?.anchorFitId == null) Text("No fit open. Browse predefined sets and manage custom recipes or custom character destinations.", Modifier.testTag("implant-sets-no-fit"))
    if (state != null) {
        Text("History: ${if (model.view.historyTarget == "library") "library / shared character" else "fit-specific"}", Modifier.testTag("implant-sets-history-target"))
        Row {
            TextButton(onClick = { model.chooseHistory(context, "library") }, enabled = !model.busy && !model.dirty,
                modifier = Modifier.testTag("implant-sets-history-library")) { Text("Library history") }
            state.anchorFitId?.let { id -> TextButton(onClick = { model.chooseHistory(context, id) }, enabled = !model.busy && !model.dirty,
                modifier = Modifier.testTag("implant-sets-history-fit")) { Text("Fit history") } }
        }
        Row {
            TextButton(onClick = { model.history(context, false) }, enabled = model.available && !model.dirty && model.historyCurrent && state.history.undoCount > 0,
                modifier = Modifier.testTag("implant-sets-undo")) { Text("Undo") }
            TextButton(onClick = { model.history(context, true) }, enabled = model.available && !model.dirty && model.historyCurrent && state.history.redoCount > 0,
                modifier = Modifier.testTag("implant-sets-redo")) { Text("Redo") }
        }
        if (model.historyCurrent) {
            Text(state.history.undoLabel?.let { "Undo: $it" } ?: "No undo action")
            Text(state.history.redoLabel?.let { "Redo: $it" } ?: "No redo action")
        }
    }
    if (model.addChoice != null) {
        ImplantSetItemPicker(model)
    } else {
        OutlinedTextField(model.view.query, { model.search(context, it) }, enabled = !model.saving && !model.dirty,
            label = { Text("Search implant sets") }, singleLine = true, modifier = Modifier.fillMaxWidth().testTag("implant-sets-search"))
        if (state != null) {
            Text("${state.total} matching sets · offset ${state.view.offset}", Modifier.testTag("implant-sets-page"))
            var section: String? = null
            state.entries.forEach { entry ->
                if (entry.kind != section) {
                    section = entry.kind
                    Text(if (entry.readonly) "Predefined sets · read-only" else "Custom saved sets", style = MaterialTheme.typography.titleMedium)
                }
                TextButton(onClick = { model.select(context, entry.id) }, enabled = !model.saving && !model.dirty,
                    modifier = Modifier.testTag("implant-set-select-${entry.id}")) {
                    Text((if (model.view.selectedSetId == entry.id) "✓ " else "") + entry.name + " · ${entry.itemCount} implants")
                }
            }
            Row {
                TextButton(onClick = { model.page(context, (model.view.offset - model.view.limit).coerceAtLeast(0)) },
                    enabled = !model.busy && !model.dirty && model.view.offset > 0, modifier = Modifier.testTag("implant-sets-previous")) { Text("Previous") }
                TextButton(onClick = { model.page(context, model.view.offset + model.view.limit) },
                    enabled = !model.busy && !model.dirty && model.view.offset < state.total - model.view.limit, modifier = Modifier.testTag("implant-sets-next")) { Text("Next") }
            }
        }
        Button(onClick = { model.begin("create") }, enabled = model.available && !model.dirty,
            modifier = Modifier.testTag("implant-set-create")) { Text("Create empty custom set") }
        Text("Create, rename, duplicate, delete, recipe edits and Save current use library history.")
        state?.saveSource?.let { source ->
            Text("Save current source: ${if (source.source == ImplantLocation.FIT) "Fit-specific implants" else "Character: ${source.profileName}"} · ${source.implantCount} implants, including inactive rows.",
                Modifier.testTag("implant-set-save-source"))
            Text("This is the open fit's applied source, not the application-preview destination below.")
            Button(onClick = { model.begin("save_current") }, enabled = model.available && !model.dirty && source.implantCount > 0,
                modifier = Modifier.testTag("implant-set-save-current")) { Text("Save current implants as set") }
            if (source.implantCount == 0L) Text("The applied source is empty. Create an empty custom set instead.", Modifier.testTag("implant-set-save-empty"))
        }
        model.detail?.let { detail ->
            val entry = detail.entry
            Text(entry.name, style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("implant-set-selected"))
            Text("${entry.kind} · revision ${entry.revision} · ${entry.itemCount} implants")
            if (entry.readonly) {
                Text("Family: ${entry.family} · Grade: ${entry.grade ?: "none"}", Modifier.testTag("implant-set-family-grade"))
                Text("Predefined recipes are browse/apply only. Apply one, then Save current to create an independent custom recipe.", Modifier.testTag("implant-set-readonly"))
            }
            Text("Recipe order (not slot-sorted):")
            if (detail.items.isEmpty()) Text("Empty recipe. Applying it does not remove existing implants.", Modifier.testTag("implant-set-empty"))
            detail.items.forEach { item ->
                Text("Slot ${item.slot}: ${item.name}", Modifier.testTag("implant-set-item-${item.itemId}"))
                if (!entry.readonly) TextButton(onClick = { model.removeItem(context, item) }, enabled = model.available && !model.dirty,
                    modifier = Modifier.testTag("implant-set-remove-${item.itemId}")) { Text("Remove from recipe") }
            }
            if (!entry.readonly) {
                Button(onClick = { model.openPicker(context) }, enabled = model.available && !model.dirty,
                    modifier = Modifier.testTag("implant-set-add")) { Text("Add / replace recipe implant") }
                Row {
                    TextButton(onClick = { model.begin("rename") }, enabled = model.available && !model.dirty,
                        modifier = Modifier.testTag("implant-set-rename")) { Text("Rename") }
                    TextButton(onClick = { model.begin("duplicate") }, enabled = model.available && !model.dirty,
                        modifier = Modifier.testTag("implant-set-duplicate")) { Text("Duplicate") }
                    TextButton(onClick = model::confirmDelete, enabled = model.available && !model.dirty,
                        modifier = Modifier.testTag("implant-set-delete")) { Text("Delete…") }
                }
            }
        }
        if (state != null) {
            Text("Application preview destination", style = MaterialTheme.typography.titleMedium)
            if (state.anchorFitId != null) TextButton(onClick = { model.destination(context, null) }, enabled = !model.saving && !model.dirty,
                modifier = Modifier.testTag("implant-set-target-fit")) { Text((if (model.view.targetProfileId == null) "✓ " else "") + "Fit-specific implants (source unchanged)") }
            if (model.skillDraftPending) Text("An unsaved character skill draft is kept. Save or revert it before choosing or applying to a character.", Modifier.testTag("implant-set-skill-draft-block"))
            features?.profiles?.forEach { profile ->
                TextButton(onClick = { model.destination(context, profile.id) }, enabled = !model.saving && !model.dirty && !model.skillDraftPending,
                    modifier = Modifier.testTag("implant-set-target-${profile.id}")) {
                    Text((if (model.view.targetProfileId == profile.id) "✓ " else "") + profile.name + if (profile.readonly) " · read-only" else " · character")
                }
            }
            when (val destination = state.destination) {
                null -> Text("No saved destination selected. A removed character is never replaced automatically.", Modifier.testTag("implant-set-destination-missing"))
                is OfflineImplantSetDestination.Fit -> {
                    Text("Fit-specific destination: ${destination.name} · ${destination.implants.size} implants", Modifier.testTag("implant-set-destination-fit"))
                    if (destination.isStructure) Text("Structures cannot receive implant sets.", Modifier.testTag("implant-set-structure-block"))
                    if (state.saveSource?.source == ImplantLocation.CHARACTER) Text("This fit-specific collection is dormant while Character is selected. Application will not switch the source.", Modifier.testTag("implant-set-dormant"))
                    Button(onClick = { model.reviewApplication(context) }, enabled = model.available && !model.dirty && model.detail != null && !destination.isStructure,
                        modifier = Modifier.testTag("implant-set-review-fit")) { Text("Review fit application (fit history)") }
                }
                is OfflineImplantSetDestination.Profile -> {
                    Text("Character destination: ${destination.name} · ${destination.assignedFitCount} directly assigned fit(s)", Modifier.testTag("implant-set-destination-profile"))
                    Text("The count includes fits with dormant character implants. Linked recipients may also recalculate. Choosing this preview does not assign the character or change any fit's source.")
                    if (destination.readonly) Text("Built-in characters are read-only. Choose an editable custom character.", Modifier.testTag("implant-set-profile-readonly"))
                    Button(onClick = { model.reviewApplication(context) }, enabled = model.available && !model.dirty && model.detail != null && !destination.readonly && !model.skillDraftPending,
                        modifier = Modifier.testTag("implant-set-review-profile")) { Text("Review character application (library history)") }
                }
            }
        }
    }
    model.draft?.let { draft ->
        Text("Unsaved ${draft.operation.replace('_', ' ')}", style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("implant-set-dirty"))
        draft.saveSource?.let { source -> Text("Captured applied source: ${if (source.source == ImplantLocation.FIT) "Fit-specific" else source.profileName} · ${source.implantCount} implants") }
        OutlinedTextField(draft.name, model::editName, enabled = !model.saving, label = { Text("Custom set name") },
            modifier = Modifier.fillMaxWidth().testTag("implant-set-name"))
        if (model.conflict) Text("The saved source or session changed. Your name draft is kept. Cancel it before editing current saved values.", color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("implant-set-conflict"))
        Row {
            Button(onClick = { model.save(context) }, enabled = model.canSave, modifier = Modifier.testTag("implant-set-save")) { Text("Save to library") }
            TextButton(onClick = model::cancelDraft, enabled = !model.saving, modifier = Modifier.testTag("implant-set-cancel-draft")) { Text("Cancel draft") }
        }
    }
    model.deleteConfirmation?.let { pending -> AlertDialog(onDismissRequest = model::dismissDelete,
        title = { Text("Delete ${pending.detail.entry.name}?") },
        text = { Text("Only this recipe is deleted. Previously applied fit and character implants stay unchanged. This uses library history and can be undone during this session.") },
        confirmButton = { TextButton(onClick = { model.delete(context) }, enabled = model.available && !model.dirty,
            modifier = Modifier.testTag("implant-set-delete-confirm")) { Text("Delete recipe") } },
        dismissButton = { TextButton(onClick = model::dismissDelete) { Text("Cancel") } }) }
    model.applicationReview?.let { review -> ImplantSetApplicationDialog(model, review) }
    if (confirmLeave) AlertDialog(onDismissRequest = { confirmLeave = false }, title = { Text("Keep unsaved set name?") },
        text = { Text("Your draft will stay here while the app remains open. No implant rows are applied by leaving.") },
        confirmButton = { TextButton(onClick = { confirmLeave = false; model.leave(); onBack() }, modifier = Modifier.testTag("implant-set-leave-keep")) { Text("Keep draft and go back") } },
        dismissButton = { TextButton(onClick = { confirmLeave = false }) { Text("Stay") } })
}

@Composable
private fun ImplantSetItemPicker(model: OfflineImplantSetsModel) {
    val context = LocalContext.current
    Text("Choose a genuine implant for the recipe", style = MaterialTheme.typography.titleLarge)
    Text("Slot conflicts remove the old member then append the incoming implant. Templates do not store activation.")
    TextButton(onClick = model::closePicker, enabled = !model.saving, modifier = Modifier.testTag("implant-set-picker-close")) { Text("Close picker") }
    OutlinedTextField(model.itemQuery, model::searchItems, enabled = !model.saving, label = { Text("Search genuine implants") },
        modifier = Modifier.fillMaxWidth().testTag("implant-set-item-search"))
    val matching = model.matchingItems
    Text("${matching.size} matching implants · page ${model.itemPage + 1}")
    matching.drop(model.itemPage * 25).take(25).forEach { item ->
        TextButton(onClick = { model.chooseItem(context, item) }, enabled = model.addChoiceCurrent,
            modifier = Modifier.testTag("implant-set-pick-${item.itemId}")) { Text("Slot ${item.slot}: ${item.name}") }
    }
    Row {
        TextButton(onClick = { model.pageItems(model.itemPage - 1) }, enabled = !model.saving && model.itemPage > 0,
            modifier = Modifier.testTag("implant-set-items-previous")) { Text("Previous") }
        TextButton(onClick = { model.pageItems(model.itemPage + 1) }, enabled = !model.saving && (model.itemPage + 1) * 25 < matching.size,
            modifier = Modifier.testTag("implant-set-items-next")) { Text("Next") }
    }
    model.replacement?.let { pending -> AlertDialog(onDismissRequest = model::dismissReplacement,
        title = { Text("Replace recipe slot ${pending.item.slot}?") },
        text = { Text("Remove ${pending.occupant.name} and append ${pending.item.name}. Re-adding the same implant also moves it to the end unless the order is already unchanged. This edits the recipe only, using library history.") },
        confirmButton = { TextButton(onClick = { model.replaceItem(context) }, enabled = model.replacementCurrent,
            modifier = Modifier.testTag("implant-set-replace-confirm")) { Text("Replace recipe member") } },
        dismissButton = { TextButton(onClick = model::dismissReplacement, enabled = !model.saving) { Text("Cancel") } }) }
}

@Composable
private fun ImplantSetApplicationDialog(model: OfflineImplantSetsModel, review: OfflineImplantApplicationReview) {
    val context = LocalContext.current
    val character = review.destination is OfflineImplantSetDestination.Profile
    AlertDialog(onDismissRequest = model::dismissApplication, title = { Text("Apply ${review.detail.entry.name}?") },
        text = { Column(Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState())) {
            Text("Destination: ${review.destination.name} · ${if (character) "character implants" else "fit-specific implants"}")
            Text("History: ${if (character) "library / shared character" else "this fit"}. No source selector or set binding changes.")
            if (character) Text("${(review.destination as OfflineImplantSetDestination.Profile).assignedFitCount} directly assigned fit(s). Incoming character slots are recreated active, even for the same implant type.")
            if (!character && review.saveSource?.source == ImplantLocation.CHARACTER) Text("The destination stays dormant because the active source is Character.")
            Text("Untouched (${review.untouched.size}):")
            review.untouched.forEach { Text("Slot ${it.slot}: ${it.name} · ${if (it.active) "active" else "inactive"}") }
            review.steps.forEach { step -> Text(when (step.disposition) {
                OfflineImplantApplyDisposition.ADDED -> "Add slot ${step.item.slot}: ${step.item.name} · active"
                OfflineImplantApplyDisposition.REPLACED -> "Replace slot ${step.item.slot}: ${step.occupant?.name} with ${step.item.name} · fresh active row"
                OfflineImplantApplyDisposition.DUPLICATE_SKIPPED -> "Skip exact duplicate slot ${step.item.slot}: ${step.item.name} · existing ${if (step.occupant?.active == true) "active" else "inactive"} row preserved"
            }) }
            if (review.steps.isEmpty()) Text("Empty recipe: no implants will be removed or changed.")
            if (!model.reviewCurrent) Text("The saved inputs changed. Cancel and review again.", color = MaterialTheme.colorScheme.error)
        } },
        confirmButton = { TextButton(onClick = { model.apply(context) }, enabled = model.reviewCurrent,
            modifier = Modifier.testTag("implant-set-apply-confirm")) { Text(if (character) "Apply to this character" else "Apply to fit-specific implants") } },
        dismissButton = { TextButton(onClick = model::dismissApplication, enabled = !model.saving,
            modifier = Modifier.testTag("implant-set-apply-cancel")) { Text("Cancel") } })
}
