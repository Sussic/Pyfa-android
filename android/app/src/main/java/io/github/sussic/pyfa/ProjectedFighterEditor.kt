package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.concurrent.CompletableFuture
import kotlinx.coroutines.Dispatchers

data class ProjectedFighterAnchor(val fitId: String, val revision: Long, val row: ProjectedFighterRow)
enum class ProjectedFighterDraftKind { RANGE, AMOUNT }
data class ProjectedFighterDraft(val kind: ProjectedFighterDraftKind, val anchor: ProjectedFighterAnchor, val fitName: String, val initial: String, val text: String)

/** Single-row options and retained whole-squadron selection share one edit gate. */
class ProjectedFighterModel(
    private val engineState: () -> EngineState = { EngineRuntime.state.value },
    private val read: (Context, String, Long) -> CompletableFuture<ProjectedFighterDetails> = EngineRuntime::projectedFighterDetails,
    private val readOptions: (Context, String, Long, ProjectedFighterRow) -> CompletableFuture<ProjectedFighterOptions> = EngineRuntime::projectedFighterOptions,
    private val readAdd: (Context, String, Long, Int) -> CompletableFuture<ProjectedFighterAddOptions> = EngineRuntime::projectedFighterAddOptions,
    private val similarQuery: (Context, String, Long, ProjectedFighterRow) -> CompletableFuture<FighterSimilarSelection> = EngineRuntime::projectedFighterSimilarSelection,
    private val dispatch: (Context, BridgeOperation, Map<String, Long>) -> CompletableFuture<BridgeResponse> =
        { context, operation, revisions -> EngineRuntime.request(context, operation, revisions) },
) : ViewModel() {
    var details by mutableStateOf<ProjectedFighterDetails?>(null); private set
    var options by mutableStateOf<ProjectedFighterOptions?>(null); private set
    var loading by mutableStateOf(false); private set
    var optionsLoading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var optionsError by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var selectedKey by mutableStateOf<String?>(null); private set
    var page by mutableStateOf(0); private set
    var draft by mutableStateOf<ProjectedFighterDraft?>(null); private set
    var addOptions by mutableStateOf<ProjectedFighterAddOptions?>(null); private set
    var addLoading by mutableStateOf(false); private set
    var addError by mutableStateOf<String?>(null); private set
    var bulkSelection by mutableStateOf<ProjectedFighterBulkSelection?>(null); private set
    var bulkDraft by mutableStateOf<ProjectedFighterBulkRangeDraft?>(null); private set
    var bulkMainKey by mutableStateOf<String?>(null); private set
    var selectingSimilar by mutableStateOf(false); private set
    private var selectionEpoch = 0L
    private fun selectionChanged() { ++selectionEpoch }
    /** Navigation invalidates pending reads, while current selections/drafts remain retained. */
    fun leaveEditor() { selectionChanged() }
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    private var optionGeneration = 0
    private var addRequested: Triple<String, Long, Int>? = null
    private var addGeneration = 0
    private fun fit() = (engineState() as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit
    val currentDetails get() = details?.takeIf { d -> fit()?.let { it.id == d.fitId && it.revision == d.revision } == true }
    val selectedRow get() = currentDetails?.squadrons?.singleOrNull { it.objectKey == selectedKey }
    val currentOptions get() = options?.takeIf { o -> currentDetails?.let { d -> selectedRow?.let { r ->
        o.fitId == d.fitId && o.revision == d.revision && o.index == r.index && o.objectKey == r.objectKey && o.itemId == r.itemId
    } } == true }
    val available get() = !editing && !loading && currentDetails?.isStructure == false
    val actionsAvailable get() = available && draft == null && bulkDraft == null
    val draftStale get() = draft?.let { !isCurrent(it.anchor) } == true
    fun anchor(row: ProjectedFighterRow): ProjectedFighterAnchor? = currentDetails?.takeIf { row in it.squadrons }
        ?.let { ProjectedFighterAnchor(it.fitId, it.revision, row) }
    fun isCurrent(a: ProjectedFighterAnchor): Boolean = currentDetails?.let {
        it.fitId == a.fitId && it.revision == a.revision && a.row in it.squadrons && !it.isStructure && a.row.editable
    } == true
    fun canEdit(a: ProjectedFighterAnchor) = actionsAvailable && isCurrent(a)
    val bulkStale get() = bulkSelection?.let { !isBulkCurrent(it) } == true
    fun isBulkCurrent(selection: ProjectedFighterBulkSelection) = currentDetails?.let { d ->
        !d.isStructure && d.fitId == selection.fitId && d.revision == selection.revision &&
            selection.rows.isNotEmpty() && selection.rows.all { it.editable && it in d.squadrons }
    } == true
    fun canBulk(selection: ProjectedFighterBulkSelection) = actionsAvailable && selection === bulkSelection && isBulkCurrent(selection)
    val canSelectBulk get() = actionsAvailable && !bulkStale
    fun canReplaceSelection(before: ProjectedFighterDetails, row: ProjectedFighterRow) = canSelectBulk &&
        currentDetails === before && row.editable && before.squadrons.any { it === row }
    fun canSelectSimilar(before: ProjectedFighterDetails, row: ProjectedFighterRow) = !selectingSimilar && canReplaceSelection(before, row)
    private fun replaceSelection(before: ProjectedFighterDetails, main: ProjectedFighterRow, rows: List<ProjectedFighterRow>) {
        selectionChanged()
        bulkSelection = ProjectedFighterBulkSelection(before.fitId, before.revision, fit()!!.name, OfflineFeatureCodec.frozen(rows))
        bulkMainKey = main.objectKey
        // Never relabel another row's options as the new main; load options only through the existing explicit control.
        selectedKey = main.objectKey; options = null; optionsError = null; optionsLoading = false; ++optionGeneration
        error = null
    }
    fun selectSameType(before: ProjectedFighterDetails, row: ProjectedFighterRow) {
        if (!canReplaceSelection(before, row)) return
        val rows = before.squadrons.filter { it.itemId == row.itemId }
        if (rows.size > 1024) { error = "${FighterSimilarSelectionCodec.LIMIT_MESSAGE}."; return }
        if (rows.isEmpty() || rows.any { !it.editable }) {
            error = "Matching squadrons could not be selected completely. Reload before retrying."; return
        }
        replaceSelection(before, row, rows)
        message = "${rows.size} same-type incoming squadrons selected. No fitting values changed."
    }
    fun selectSimilar(context: Context, before: ProjectedFighterDetails, row: ProjectedFighterRow) {
        if (!canSelectSimilar(before, row)) return
        val epoch = selectionEpoch
        selectingSimilar = true; error = null; message = null
        val pending = try { similarQuery(context, before.fitId, before.revision, row) } catch (failure: Exception) {
            selectingSimilar = false; error = FighterSimilarSelectionCodec.failureMessage(failure); return
        }
        pending.whenCompleteAsync({ result, failure ->
            // Hold the launch gate until completion, including invalidated requests: there is no growing query queue.
            selectingSimilar = false
            if (epoch == selectionEpoch && canReplaceSelection(before, row)) {
                if (failure != null) error = FighterSimilarSelectionCodec.failureMessage(failure)
                else try {
                    val rows = ProjectedFighterSelection.rows(result, before, row)
                    replaceSelection(before, row, rows)
                    message = "${rows.size} similar incoming squadrons selected. No fitting values changed."
                } catch (_: BridgeProtocolException) {
                    error = "The incoming fighter selection no longer matches this fit. Reload and try again."
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun toggleBulk(row: ProjectedFighterRow) {
        val a = anchor(row) ?: return
        if (!canSelectBulk || !isCurrent(a)) return
        selectionChanged()
        val old = bulkSelection?.rows.orEmpty()
        val rows = if (old.any { it.objectKey == row.objectKey }) old.filterNot { it.objectKey == row.objectKey } else old + row
        bulkSelection = if (rows.isEmpty()) null else ProjectedFighterBulkSelection(a.fitId, a.revision, fit()!!.name, OfflineFeatureCodec.frozen(rows))
        if (rows.none { it.objectKey == bulkMainKey }) bulkMainKey = null
        error = null; message = null
    }
    fun selectBulkPage() {
        val d = currentDetails ?: return
        if (!canSelectBulk) return
        selectionChanged()
        val old = bulkSelection?.rows.orEmpty()
        val rows = old + d.squadrons.drop(page * 25).take(25).filter { it.editable && old.none { r -> r.objectKey == it.objectKey } }
        if (rows.isNotEmpty()) bulkSelection = ProjectedFighterBulkSelection(d.fitId, d.revision, fit()!!.name, OfflineFeatureCodec.frozen(rows))
    }
    fun clearBulk() {
        if (editing) return
        selectionChanged()
        bulkSelection = null; bulkDraft = null; bulkMainKey = null; error = null
        message = "Selection and its range draft discarded. No edit was added."
    }
    val canReviewBulk get() = available && draft == null && bulkStale && bulkSelection?.let { old -> currentDetails?.let { d ->
        d.fitId == old.fitId && old.rows.all { row -> d.squadrons.any { it.objectKey == row.objectKey && it.itemId == row.itemId && it.editable } }
    } } == true
    fun reviewBulk() {
        val old = bulkSelection ?: return
        if (!canReviewBulk) return
        selectionChanged()
        val d = currentDetails!!
        val rows = old.rows.map { row -> d.squadrons.single { it.objectKey == row.objectKey && it.itemId == row.itemId } }
        val reviewed = ProjectedFighterBulkSelection(d.fitId, d.revision, fit()!!.name, OfflineFeatureCodec.frozen(rows))
        bulkSelection = reviewed
        if (bulkDraft != null) bulkDraft = ProjectedFighterBulkRangeDraft.capture(reviewed)
        error = null; message = "Current selected objects loaded. Previous range draft discarded; review before applying."
    }
    fun beginBulkRange(selection: ProjectedFighterBulkSelection) {
        if (!canBulk(selection)) return
        selectionChanged()
        bulkDraft = ProjectedFighterBulkRangeDraft.capture(selection); error = null; message = null
    }
    fun changeBulkRange(text: String) {
        if (editing || text.length > 100) return
        bulkDraft = bulkDraft?.copy(text = text, mode = ProjectedFighterBulkRangeMode.VALUE)
    }
    fun defaultBulkRange() {
        if (!editing) bulkDraft = bulkDraft?.copy(text = "", mode = ProjectedFighterBulkRangeMode.DEFAULT)
    }
    fun discardBulkRange() {
        if (!editing) { bulkDraft = null; error = null; message = "Selected range draft discarded. No edit was added." }
    }
    fun saveBulkRange(context: Context) {
        val d = bulkDraft ?: return
        val selection = d.selection
        if (!available || draft != null || selection !== bulkSelection || !isBulkCurrent(selection)) return
        if (d.mode == ProjectedFighterBulkRangeMode.MIXED) { error = "Choose a range or explicitly choose Default for the selected squadrons."; return }
        // Preserve the captured raw value even if kilometre formatting underflows or rounds.
        if (d.mode != ProjectedFighterBulkRangeMode.DEFAULT && !d.mixed && d.text.trim() == d.initial.trim()) {
            bulkDraft = null; error = null; message = "Selected ranges are unchanged. No edit was added to history."; return
        }
        val range = if (d.mode == ProjectedFighterBulkRangeMode.DEFAULT) null else try {
            require(d.text.isNotBlank()) { "Enter a range in km, or explicitly choose Default." }
            ProjectedFitInputs.rangeM(d.text)
        } catch (_: IllegalArgumentException) { error = "Enter a finite, nonnegative range in km, or explicitly choose Default."; return }
        if (selection.rows.all { ProjectedFitInputs.sameRange(it.rangeM, range) }) {
            bulkDraft = null; error = null; message = "Selected ranges are unchanged. No edit was added to history."; return
        }
        submit(context, selection.fitId, selection.revision, BridgeOperation.SetProjectedFighterRanges(selection.fitId, selection.wireRows(), range),
            "Selected ranges saved together. Review the refreshed selection before another bulk edit.", savedBulkDraft = d)
    }
    fun bulkActive(context: Context, selection: ProjectedFighterBulkSelection, active: Boolean) {
        if (!canBulk(selection)) return
        if (selection.rows.all { it.active == active }) {
            error = null; message = "Selected states are unchanged. No edit was added to history."; return
        }
        submit(context, selection.fitId, selection.revision, BridgeOperation.SetProjectedFightersActive(selection.fitId, selection.wireRows(), active),
            "Selected squadron states saved together. Applied effects depend on abilities, range and the recipient. Review the refreshed selection before another bulk edit.")
    }
    fun removeBulk(context: Context, selection: ProjectedFighterBulkSelection) {
        if (!canBulk(selection)) return
        submit(context, selection.fitId, selection.revision, BridgeOperation.RemoveProjectedFighters(selection.fitId, selection.wireRows()),
            "Selected complete squadrons removed together. Undo restores quantities, abilities, ranges and identities.", removedSelection = selection)
    }
    val capturedBulkMain get() = bulkSelection?.rows?.singleOrNull { it.objectKey == bulkMainKey }
    val bulkMain get() = capturedBulkMain?.takeIf { bulkSelection?.let(::isBulkCurrent) == true }
    val bulkMainOptions get() = currentOptions?.takeIf { it.objectKey == bulkMain?.objectKey }
    fun selectBulkMain(context: Context, row: ProjectedFighterRow) {
        val selection = bulkSelection ?: return
        if (!canBulk(selection) || row !in selection.rows) return
        selectionChanged()
        bulkMainKey = row.objectKey
        select(context, row)
    }
    fun bulkAbility(context: Context, selection: ProjectedFighterBulkSelection, main: ProjectedFighterAnchor,
        before: ProjectedFighterOptions, choice: FighterAbility) {
        if (!canBulk(selection) || main.row !in selection.rows || bulkMain != main.row ||
            before !== bulkMainOptions || !optionsCurrent(main, before) || choice !in before.abilities) return
        submit(context, selection.fitId, selection.revision, BridgeOperation.ToggleProjectedFighterAbilities(selection.fitId,
            ProjectedFighterSelectionRow(main.row.index, main.row.objectKey), selection.wireRows(), choice.effectId),
            "Matching selected abilities were ${if (choice.active) "disabled" else "enabled"} from the main squadron's state. Squadrons without that ability were unchanged.")
    }
    fun load(context: Context, value: FitSnapshot, retry: Boolean = false) {
        val next = value.id to value.revision
        if (!retry && requested == next) return
        selectionChanged()
        if (requested?.first != value.id) { selectedKey = null; page = 0; message = null }
        requested = next; details = null; loading = true; error = null
        options = null; optionsLoading = false; optionsError = null; ++optionGeneration
        val token = ++generation
        read(context, value.id, value.revision).whenCompleteAsync({ result, failure ->
            if (token == generation) {
                loading = false
                if (fit()?.let { it.id to it.revision } == next) {
                    if (failure != null) error = projectedFighterReadError(failure, "Projected fighters could not be verified. Reload, or restart if the engine is unavailable.")
                    else if (result.fitId == next.first && result.revision == next.second) {
                        details = result
                        if (result.squadrons.none { it.objectKey == selectedKey }) selectedKey = null
                        page = page.coerceAtMost((result.squadrons.size - 1).coerceAtLeast(0) / 25)
                        selectedRow?.takeIf { it.editable && draft == null }?.let { select(context, it) }
                    } else error = "The fit changed while loading projected fighters. Reload current values."
                } else requested = null
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun showPage(value: Int) { if (!editing) page = value.coerceIn(0, (currentDetails?.squadrons?.size?.minus(1) ?: 0).coerceAtLeast(0) / 25) }
    fun select(context: Context, row: ProjectedFighterRow) {
        val a = anchor(row) ?: return
        if (!canEdit(a) || optionsLoading && selectedKey == row.objectKey) return
        selectionChanged()
        selectedKey = row.objectKey; options = null; optionsError = null; optionsLoading = true
        val token = ++optionGeneration
        readOptions(context, a.fitId, a.revision, row).whenCompleteAsync({ result, failure ->
            if (token == optionGeneration) {
                optionsLoading = false
                if (isCurrent(a) && selectedKey == row.objectKey) {
                    if (failure != null) optionsError = projectedFighterReadError(failure, "This projected fighter's choices could not be verified. Retry before editing.")
                    else if (result.fitId == a.fitId && result.revision == a.revision && result.index == row.index &&
                        result.objectKey == row.objectKey && result.itemId == row.itemId) options = result
                    else optionsError = "The projected fighter changed. Reload its current choices."
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun beginRange(a: ProjectedFighterAnchor) {
        if (!canEdit(a)) return
        selectionChanged()
        val text = ProjectedFitInputs.rangeText(a.row.rangeM)
        draft = ProjectedFighterDraft(ProjectedFighterDraftKind.RANGE, a, fit()!!.name, text, text); error = null; message = null
    }
    fun changeDraft(value: String) { if (!editing && value.length <= 100) draft = draft?.copy(text = value) }
    fun discardDraft() { if (!editing) { draft = null; error = null; message = "Draft discarded. No edit was added." } }
    val canReview get() = available && draft?.let { d -> currentDetails?.let { current ->
        current.fitId == d.anchor.fitId && current.squadrons.any { it.objectKey == d.anchor.row.objectKey && it.editable }
    } } == true
    fun reviewDraft() {
        val old = draft ?: return
        if (!canReview) return
        val row = currentDetails!!.squadrons.single { it.objectKey == old.anchor.row.objectKey }
        val text = if (old.kind == ProjectedFighterDraftKind.RANGE) ProjectedFitInputs.rangeText(row.rangeM) else row.amount.toString()
        draft = ProjectedFighterDraft(old.kind, anchor(row)!!, fit()!!.name, text, text)
        error = null; message = "Current value loaded. Previous draft discarded; review before saving."
    }
    fun beginAmount(a: ProjectedFighterAnchor) {
        if (!canEdit(a)) return
        selectionChanged()
        val text = a.row.amount.toString()
        draft = ProjectedFighterDraft(ProjectedFighterDraftKind.AMOUNT, a, fit()!!.name, text, text)
        error = null; message = null
    }
    fun saveDraft(context: Context) {
        val d = draft ?: return
        if (!available || !isCurrent(d.anchor)) return
        // Kilometre formatting can underflow or round. Untouched text retains the raw metres.
        if (d.text.trim() == d.initial.trim() && !(d.kind == ProjectedFighterDraftKind.AMOUNT && d.text.trim().toIntOrNull() == 0)) {
            draft = null; error = null; message = "Value is unchanged. No edit was added to history."; return
        }
        val a = d.anchor
        val operation: BridgeOperation
        if (d.kind == ProjectedFighterDraftKind.RANGE) {
            val range = try { ProjectedFitInputs.rangeM(d.text) } catch (failure: IllegalArgumentException) { error = failure.message; return }
            if (ProjectedFitInputs.sameRange(range, a.row.rangeM)) {
                draft = null; error = null; message = "Range is unchanged. No edit was added to history."; return
            }
            operation = BridgeOperation.SetProjectedFighterRange(a.fitId, a.row.index, a.row.objectKey, range)
        } else {
            val text = d.text.trim()
            val amount = text.takeIf { it.isNotEmpty() && it.all { c -> c in '0'..'9' } }?.toIntOrNull()
            if (amount == null || amount !in 0..a.row.maxSize) { error = "Enter a whole quantity from 0 to ${a.row.maxSize}. Zero removes this squadron."; return }
            if (amount != 0 && amount == a.row.amount) {
                draft = null; error = null; message = "Quantity is unchanged. No edit was added to history."; return
            }
            operation = BridgeOperation.SetProjectedFighterAmount(a.fitId, a.row.index, a.row.objectKey, amount)
        }
        submit(context, a.fitId, a.revision, operation,
            "Projected fighter input saved. Undo restores the captured inputs.", savedDraft = d)
    }
    private fun optionsCurrent(a: ProjectedFighterAnchor, before: ProjectedFighterOptions) = canEdit(a) && before === currentOptions &&
        before.index == a.row.index && before.objectKey == a.row.objectKey && before.itemId == a.row.itemId
    fun active(context: Context, a: ProjectedFighterAnchor, before: ProjectedFighterOptions, value: Boolean) {
        if (!optionsCurrent(a, before) || value == a.row.active) return
        submit(context, a.fitId, a.revision, BridgeOperation.SetProjectedFighterActive(a.fitId, a.row.index, a.row.objectKey, value),
            "Squadron state saved. Effect application depends on enabled abilities, range and the recipient.")
    }
    fun variation(context: Context, a: ProjectedFighterAnchor, before: ProjectedFighterOptions, choice: ProjectedFighterVariation) {
        if (!optionsCurrent(a, before) || choice !in before.variations || !choice.enabled || choice.id == a.row.itemId) return
        submit(context, a.fitId, a.revision, BridgeOperation.ChangeProjectedFighterVariation(a.fitId, a.row.index, a.row.objectKey, choice.id),
            "Variation removed this squadron and appended its replacement at default range. Undo restores the exact captured inputs.")
    }
    fun ability(context: Context, a: ProjectedFighterAnchor, before: ProjectedFighterOptions, choice: FighterAbility) {
        if (!optionsCurrent(a, before) || choice !in before.abilities) return
        submit(context, a.fitId, a.revision, BridgeOperation.ToggleProjectedFighterAbility(a.fitId, a.row.index, a.row.objectKey, choice.effectId),
            "Ability state saved. Only source-supported effects apply to the recipient.")
    }
    fun maximumAmount() {
        val d = draft ?: return
        if (editing || d.kind != ProjectedFighterDraftKind.AMOUNT || !isCurrent(d.anchor) || d.anchor.row.maxSize <= 0) return
        draft = d.copy(text = d.anchor.row.maxSize.toString())
    }
    fun remove(context: Context, a: ProjectedFighterAnchor) {
        if (!canEdit(a)) return
        submit(context, a.fitId, a.revision, BridgeOperation.RemoveProjectedFighter(a.fitId, a.row.index, a.row.objectKey),
            "Projected squadron removed. Undo restores quantity, state, abilities and range.")
    }
    fun currentAdd(itemId: Int) = addOptions?.takeIf { o -> itemId == o.itemId && fit()?.let { it.id == o.fitId && it.revision == o.revision } == true }
    fun loadAdd(context: Context, value: FitSnapshot, itemId: Int, retry: Boolean = false) {
        val next = Triple(value.id, value.revision, itemId)
        if (!retry && addRequested == next) return
        addRequested = next; addOptions = null; addLoading = true; addError = null
        val token = ++addGeneration
        readAdd(context, value.id, value.revision, itemId).whenCompleteAsync({ result, failure ->
            if (token == addGeneration) {
                addLoading = false
                if (fit()?.let { it.id == next.first && it.revision == next.second } == true) {
                    if (failure != null) addError = projectedFighterReadError(failure, "Projectability could not be checked. Retry before adding.")
                    else if (result.fitId == next.first && result.revision == next.second && result.itemId == next.third) addOptions = result
                    else addError = "The fit changed while checking this item. Reload its projection options."
                } else addRequested = null
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun add(context: Context, itemId: Int, onSaved: () -> Unit) {
        val o = currentAdd(itemId) ?: return
        if (editing || addLoading || draft != null || bulkDraft != null || !o.enabled) return
        submit(context, o.fitId, o.revision, BridgeOperation.AddProjectedFighter(o.fitId, itemId),
            "A separate incoming fighter squadron was added. Undo is available.", onSaved = onSaved)
    }
    private fun submit(context: Context, fitId: String, revision: Long, operation: BridgeOperation, success: String,
        savedDraft: ProjectedFighterDraft? = null, savedBulkDraft: ProjectedFighterBulkRangeDraft? = null,
        removedSelection: ProjectedFighterBulkSelection? = null, onSaved: () -> Unit = {}) {
        selectionChanged()
        editing = true; error = null; addError = null; message = null
        options = null; ++optionGeneration; optionsLoading = false
        val pending = try { dispatch(context, operation, mapOf(fitId to revision)) } catch (_: Exception) {
            editing = false; error = "The projected edit could not be confirmed. Check engine status before retrying."; return
        }
        pending.whenCompleteAsync({ result, failure ->
            editing = false
            if (failure == null && result.isSuccess && savedDraft != null && draft === savedDraft) draft = null
            if (failure == null && result.isSuccess && savedBulkDraft != null && bulkDraft === savedBulkDraft) bulkDraft = null
            if (failure == null && result.isSuccess && removedSelection != null && bulkSelection === removedSelection) { bulkSelection = null; bulkMainKey = null }
            if ((engineState() as? EngineState.Ready)?.fit?.id == fitId) {
                val problem = if (failure != null) "The engine could not confirm the projected edit. Restart before editing."
                    else if (!result.isSuccess) result.error?.message ?: "Projected edit refused." else null
                if (problem == null) { message = success; onSaved() }
                fit()?.let { load(context, it, true) }
                error = problem; addError = problem
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun ProjectedFighterEquipmentActions(model: ProjectedFighterModel, item: EquipmentItem, onSaved: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = engine as? EngineState.Ready
    val fit = ready?.fit ?: return
    if (ready.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) return
    LaunchedEffect(fit.id, fit.revision, item.id) { model.loadAdd(context, fit, item.id) }
    if (model.addLoading) Text("Checking projected-fighter eligibility…", Modifier.testTag("equipment-project-fighter-loading"))
    model.addError?.let {
        Text(it, Modifier.testTag("equipment-project-fighter-error"), color = MaterialTheme.colorScheme.error)
        TextButton(onClick = { model.loadAdd(context, fit, item.id, true) }, enabled = !model.addLoading && !model.editing,
            modifier = Modifier.testTag("equipment-project-fighter-retry")) { Text("Check projected fighter options again") }
    }
    val options = model.currentAdd(item.id) ?: return
    if (options.isFighter && options.isProjectable) {
        options.unavailableReason?.let { Text(it, Modifier.testTag("equipment-project-fighter-unavailable")) }
        if (model.draft != null || model.bulkDraft != null) Text("Finish or discard the retained projected fighter draft before adding another fighter.")
        Button(onClick = { model.add(context, item.id, onSaved) },
            enabled = options.enabled && !model.editing && !model.addLoading && model.draft == null && model.bulkDraft == null,
            modifier = Modifier.testTag("equipment-project-fighter")) { Text("Project fighter squadron onto this fit") }
        Text("Adds a separate incoming squadron, including duplicate types. Local fighter bay, hull and launch-tube limits do not apply.")
    }
}

@Composable
internal fun ProjectedFighterEditor(model: ProjectedFighterModel, onBack: () -> Unit, onBrowse: () -> Unit, onInspectBase: (Int) -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = state as? EngineState.Ready
    val fit = ready?.fit
    DisposableEffect(model, fit?.id, fit?.revision, ready?.error?.code) {
        onDispose { model.leaveEditor() }
    }
    BackHandler { onBack() }
    Text("Individual projected fighters", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("projected-fighters-back")) { Text("Back to fitting") }
    model.draft?.let { draft ->
        val range = draft.kind == ProjectedFighterDraftKind.RANGE
        val kind = if (range) "range" else "amount"
        Text("${if (range) "Range" else "Quantity"} draft: ${draft.fitName} · ${draft.anchor.row.name}", style = MaterialTheme.typography.titleMedium)
        if (model.draftStale) Text("The fit or projected squadron changed, or is unavailable. Your draft is retained. Discard it or explicitly review current values before saving.",
            Modifier.testTag("projected-fighter-draft-stale"), color = MaterialTheme.colorScheme.error)
        OutlinedTextField(draft.text, model::changeDraft, enabled = !model.editing, singleLine = true,
            label = { Text(if (range) "Range in km (blank = default)" else "Total quantity (0 removes squadron)") },
            modifier = Modifier.fillMaxWidth().testTag("projected-fighter-$kind-input"))
        if (range) {
            Text("Blank uses the engine default. Zero is an explicit zero-metre range.")
            Text("Captured range: ${draft.anchor.row.rangeM?.let { "$it m" } ?: "Default"}. Saving unchanged text preserves this exact value.")
        } else {
            Text("Current quantity ${draft.anchor.row.amount}; EOS maximum ${draft.anchor.row.maxSize}. Zero removes the whole squadron.")
            TextButton(onClick = model::maximumAmount, enabled = !model.editing && !model.draftStale && draft.anchor.row.maxSize > 0,
                modifier = Modifier.testTag("projected-fighter-amount-maximum")) { Text("Use Maximum (${draft.anchor.row.maxSize})") }
            Text("Evaluation and storage budgets may refuse a configuration; these are not extra game fitting limits.")
        }
        Button(onClick = { model.saveDraft(context) }, enabled = model.available && !model.draftStale,
            modifier = Modifier.testTag("projected-fighter-draft-save")) { Text(if (range) "Save range" else "Save quantity") }
        if (model.draftStale) TextButton(onClick = model::reviewDraft, enabled = model.canReview,
            modifier = Modifier.testTag("projected-fighter-draft-review")) { Text("Discard draft and review current value") }
        TextButton(onClick = model::discardDraft, enabled = !model.editing,
            modifier = Modifier.testTag("projected-fighter-draft-discard")) { Text("Discard draft") }
    }
    ProjectedFighterBulkControls(model)
    if (fit == null) {
        when {
            state is EngineState.Loading -> Text("Loading the fitting library…", Modifier.testTag("projected-fighters-loading"))
            state is EngineState.Failed || (state as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ->
                Text("The fitting engine is unavailable. Restart before editing.", Modifier.testTag("projected-fighters-unavailable"))
            else -> Text("Open a fit to manage its individual projected fighters.", Modifier.testTag("projected-fighters-no-fit"))
        }
        return
    }
    Text("${fit.name} · ${fit.ship}", Modifier.testTag("projected-fighters-recipient"), style = MaterialTheme.typography.titleLarge)
    if (ready.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) {
        Text("The fitting engine is unavailable. Restart before editing.", Modifier.testTag("projected-fighters-unavailable")); return
    }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("Incoming fighters affect this recipient only, not onward saved-fit recipients. EFT export omits these squadrons and their ability states.")
    Text("Squadron activation and individual abilities are separate. Active abilities may have no effect because of range or recipient immunity.")
    model.error?.let { Text(it, Modifier.testTag("projected-fighters-error"), color = MaterialTheme.colorScheme.error) }
    model.message?.let { Text(it, Modifier.testTag("projected-fighters-message")) }
    if (model.loading) Text("Loading projected fighters…", Modifier.testTag("projected-fighters-loading"))
    if (model.selectingSimilar) Text("Finding similar incoming squadrons…", Modifier.testTag("projected-fighters-selecting-similar"))
    if (model.editing) Text("Saving projected fighter edit…", Modifier.testTag("projected-fighters-saving"))
    if (!model.loading) TextButton(onClick = { model.load(context, fit, true) }, enabled = !model.editing,
        modifier = Modifier.testTag("projected-fighters-reload")) { Text("Reload projected fighters") }
    val d = model.currentDetails ?: return
    if (d.isStructure) Text("Individual projected fighter editing is unavailable for structures.", Modifier.testTag("projected-fighters-structure"))
    TextButton(onClick = onBrowse, enabled = !model.editing && !d.isStructure,
        modifier = Modifier.testTag("projected-fighters-browse")) { Text("Browse equipment to project") }
    Text("Same type selects matching item IDs across all pages. Similar also includes matching source groups with the same complete ability-ID set; quantity, activation, ability states and range do not affect membership.",
        Modifier.testTag("projected-fighters-similar-help"))
    if (d.squadrons.isEmpty()) Text("No individual fighters are projected onto this fit.", Modifier.testTag("projected-fighters-empty"))
    for (row in d.squadrons.drop(model.page * 25).take(25)) key(row.objectKey) {
        val a = model.anchor(row)!!
        Card(Modifier.fillMaxWidth().testTag("projected-fighter-${row.index}")) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("${row.index + 1} · ${row.name}", style = MaterialTheme.typography.titleMedium)
                Row {
                    Checkbox(checked = model.bulkSelection?.rows?.any { it.objectKey == row.objectKey } == true,
                        onCheckedChange = { model.toggleBulk(row) }, enabled = row.editable && model.canSelectBulk,
                        modifier = Modifier.testTag("projected-fighter-${row.index}-bulk-select").semantics {
                            contentDescription = "Select ${row.name}, squadron ${row.index + 1}, for bulk edit"
                        })
                    Text("Select squadron for bulk edit")
                }
                if (model.bulkSelection?.rows?.any { it.objectKey == row.objectKey } == true) {
                    TextButton(onClick = { model.selectBulkMain(context, row) },
                        enabled = model.bulkSelection?.let { model.canBulk(it) } == true && !model.optionsLoading,
                        modifier = Modifier.testTag("projected-fighter-${row.index}-bulk-main")) { Text("Use this squadron as selected-ability main") }
                }

                TextButton(onClick = { model.selectSameType(d, row) }, enabled = model.canReplaceSelection(d, row),
                    modifier = Modifier.testTag("projected-fighter-${row.index}-select-type")) { Text("Select same type") }
                TextButton(onClick = { model.selectSimilar(context, d, row) }, enabled = model.canSelectSimilar(d, row),
                    modifier = Modifier.testTag("projected-fighter-${row.index}-select-similar")) { Text("Select similar squadrons") }
                Text("${row.amount} fighters / ${row.maxSize} maximum · ${if (row.active) "Active" else "Inactive"}", Modifier.testTag("projected-fighter-${row.index}-quantity"))
                Text("Range: ${row.rangeM?.let { "$it m (${ProjectedFitInputs.rangeText(it)} km)" } ?: "Default"}", Modifier.testTag("projected-fighter-${row.index}-range"))
                row.unavailableReason?.let { Text(it, Modifier.testTag("projected-fighter-${row.index}-unavailable")) }
                TextButton(onClick = { onInspectBase(row.itemId) }, modifier = Modifier.testTag("projected-fighter-${row.index}-inspect-base")) { Text("Inspect base item (unmodified attributes)") }
                TextButton(onClick = { model.beginAmount(a) }, enabled = model.canEdit(a),
                    modifier = Modifier.testTag("projected-fighter-${row.index}-edit-amount")) { Text("Edit total quantity") }
                TextButton(onClick = { model.beginRange(a) }, enabled = model.canEdit(a),
                    modifier = Modifier.testTag("projected-fighter-${row.index}-edit-range")) { Text("Edit range") }
                TextButton(onClick = { model.remove(context, a) }, enabled = model.canEdit(a),
                    modifier = Modifier.testTag("projected-fighter-${row.index}-remove")) { Text("Remove complete squadron") }
                TextButton(onClick = { model.select(context, row) }, enabled = model.canEdit(a) && !(model.optionsLoading && model.selectedKey == row.objectKey),
                    modifier = Modifier.testTag("projected-fighter-${row.index}-options")) { Text("Load activation, abilities and variation choices") }
                if (model.selectedKey == row.objectKey) {
                    if (model.optionsLoading) Text("Loading this squadron's choices…", Modifier.testTag("projected-fighter-options-loading"))
                    model.optionsError?.let { Text(it, Modifier.testTag("projected-fighter-options-error"), color = MaterialTheme.colorScheme.error) }
                    model.currentOptions?.let { options -> ProjectedFighterControls(model, a, options) }
                }
            }
        }
    }
    if (d.squadrons.size > 25) {
        Text("Page ${model.page + 1} of ${(d.squadrons.size + 24) / 25}")
        Row {
            TextButton(onClick = { model.showPage(model.page - 1) }, enabled = !model.editing && model.page > 0,
                modifier = Modifier.testTag("projected-fighters-previous")) { Text("Previous squadrons") }
            TextButton(onClick = { model.showPage(model.page + 1) }, enabled = !model.editing && (model.page + 1) * 25 < d.squadrons.size,
                modifier = Modifier.testTag("projected-fighters-next")) { Text("Next squadrons") }
        }
    }
}

@Composable
private fun ProjectedFighterControls(model: ProjectedFighterModel, a: ProjectedFighterAnchor, options: ProjectedFighterOptions) {
    val context = LocalContext.current
    val available = model.canEdit(a)
    val index = a.row.index
    TextButton(onClick = { model.active(context, a, options, !a.row.active) }, enabled = available,
        modifier = Modifier.testTag("projected-fighter-$index-toggle")) { Text(if (a.row.active) "Deactivate squadron" else "Activate squadron") }
    Text("Implemented ability states are retained separately, even when this squadron is inactive.")
    for (ability in options.abilities) TextButton(onClick = { model.ability(context, a, options, ability) }, enabled = available,
        modifier = Modifier.testTag("projected-fighter-$index-ability-${ability.effectId}")) {
        Text("${ability.name} · ${if (ability.active) "Enabled" else "Disabled"}")
    }
    var variations by rememberSaveable(a.fitId, a.row.objectKey) { mutableStateOf(false) }
    if (options.variations.isNotEmpty()) {
        TextButton(onClick = { variations = !variations }, modifier = Modifier.testTag("projected-fighter-$index-variations")) { Text(if (variations) "Hide variations" else "Choose variation") }
        if (variations) {
            Text("Variation removes this squadron and appends a separate replacement at default range. Matching abilities keep their states; other abilities use EOS defaults. Same-type squadrons are not merged. Undo restores the original range, order and identity.",
                Modifier.testTag("projected-fighter-$index-variation-warning"))
            var query by rememberSaveable(a.fitId, a.row.objectKey) { mutableStateOf("") }
            var page by rememberSaveable(a.fitId, a.row.objectKey, query) { mutableStateOf(0) }
            OutlinedTextField(query, { query = it.take(200) }, label = { Text("Search variations") }, singleLine = true,
                modifier = Modifier.fillMaxWidth().testTag("projected-fighter-$index-variation-search"))
            val matches = options.variations.filter { it.name.contains(query.trim(), true) }
            val last = (matches.size - 1).coerceAtLeast(0) / 25
            val current = page.coerceAtMost(last)
            Text("${matches.size} choices · page ${current + 1} of ${last + 1}")
            for (choice in matches.drop(current * 25).take(25)) TextButton(onClick = { model.variation(context, a, options, choice) },
                enabled = available && choice.enabled && choice.id != a.row.itemId,
                modifier = Modifier.testTag("projected-fighter-$index-variation-${choice.id}")) { Text(choice.name + if (choice.id == a.row.itemId) " · current" else "") }
            if (last > 0) Row {
                TextButton(onClick = { page = current - 1 }, enabled = current > 0,
                    modifier = Modifier.testTag("projected-fighter-$index-variation-previous")) { Text("Previous variations") }
                TextButton(onClick = { page = current + 1 }, enabled = current < last,
                    modifier = Modifier.testTag("projected-fighter-$index-variation-next")) { Text("Next variations") }
            }
        }
    }
}
