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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.concurrent.CompletableFuture
import kotlinx.coroutines.Dispatchers

data class ProjectedDroneAnchor(val fitId: String, val revision: Long, val row: ProjectedDroneRow)
enum class ProjectedDroneDraftKind { RANGE, AMOUNT }
data class ProjectedDroneDraft(val kind: ProjectedDroneDraftKind, val anchor: ProjectedDroneAnchor, val fitName: String, val initial: String, val text: String)

/** One selected stack's options and one explicitly reviewed quantity or range draft; no parallel edit queue. */
class ProjectedDroneModel(
    private val engineState: () -> EngineState = { EngineRuntime.state.value },
    private val read: (Context, String, Long) -> CompletableFuture<ProjectedDroneDetails> = EngineRuntime::projectedDroneDetails,
    private val readOptions: (Context, String, Long, ProjectedDroneRow) -> CompletableFuture<ProjectedDroneOptions> = EngineRuntime::projectedDroneOptions,
    private val readAdd: (Context, String, Long, Int) -> CompletableFuture<ProjectedDroneAddOptions> = EngineRuntime::projectedDroneAddOptions,
    private val dispatch: (Context, BridgeOperation, Map<String, Long>) -> CompletableFuture<BridgeResponse> =
        { context, operation, revisions -> EngineRuntime.request(context, operation, revisions) },
) : ViewModel() {
    var details by mutableStateOf<ProjectedDroneDetails?>(null); private set
    var options by mutableStateOf<ProjectedDroneOptions?>(null); private set
    var loading by mutableStateOf(false); private set
    var optionsLoading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var optionsError by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var selectedKey by mutableStateOf<String?>(null); private set
    var page by mutableStateOf(0); private set
    var draft by mutableStateOf<ProjectedDroneDraft?>(null); private set
    var bulkSelection by mutableStateOf<ProjectedDroneBulkSelection?>(null); private set
    var bulkDraft by mutableStateOf<ProjectedDroneBulkRangeDraft?>(null); private set
    var addOptions by mutableStateOf<ProjectedDroneAddOptions?>(null); private set
    var addLoading by mutableStateOf(false); private set
    var addError by mutableStateOf<String?>(null); private set
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    private var optionGeneration = 0
    private var addRequested: Triple<String, Long, Int>? = null
    private var addGeneration = 0
    private fun fit() = (engineState() as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit
    val currentDetails get() = details?.takeIf { d -> fit()?.let { it.id == d.fitId && it.revision == d.revision } == true }
    val selectedRow get() = currentDetails?.stacks?.singleOrNull { it.objectKey == selectedKey }
    val currentOptions get() = options?.takeIf { o -> currentDetails?.let { d -> selectedRow?.let { r ->
        o.fitId == d.fitId && o.revision == d.revision && o.index == r.index && o.objectKey == r.objectKey && o.itemId == r.itemId
    } } == true }
    val available get() = !editing && !loading && currentDetails?.isStructure == false
    val actionsAvailable get() = available && draft == null && bulkDraft == null
    val draftStale get() = draft?.let { !isCurrent(it.anchor) } == true
    fun anchor(row: ProjectedDroneRow): ProjectedDroneAnchor? = currentDetails?.takeIf { row in it.stacks }
        ?.let { ProjectedDroneAnchor(it.fitId, it.revision, row) }
    fun isCurrent(a: ProjectedDroneAnchor): Boolean = currentDetails?.let {
        it.fitId == a.fitId && it.revision == a.revision && a.row in it.stacks && !it.isStructure && a.row.editable
    } == true
    fun canEdit(a: ProjectedDroneAnchor) = actionsAvailable && isCurrent(a)
    val bulkStale get() = bulkSelection?.let { !isBulkCurrent(it) } == true
    fun isBulkCurrent(selection: ProjectedDroneBulkSelection) = currentDetails?.let { d ->
        !d.isStructure && d.fitId == selection.fitId && d.revision == selection.revision &&
            selection.rows.isNotEmpty() && selection.rows.all { it.editable && it in d.stacks }
    } == true
    fun canBulk(selection: ProjectedDroneBulkSelection) = actionsAvailable && selection === bulkSelection && isBulkCurrent(selection)
    val canSelectBulk get() = actionsAvailable && !bulkStale
    fun toggleBulk(row: ProjectedDroneRow) {
        val a = anchor(row) ?: return
        if (!canSelectBulk || !isCurrent(a)) return
        val old = bulkSelection?.rows.orEmpty()
        val rows = if (old.any { it.objectKey == row.objectKey }) old.filterNot { it.objectKey == row.objectKey } else old + row
        bulkSelection = if (rows.isEmpty()) null else ProjectedDroneBulkSelection(a.fitId, a.revision, fit()!!.name, OfflineFeatureCodec.frozen(rows))
        error = null; message = null
    }
    fun selectBulkPage() {
        val d = currentDetails ?: return
        if (!canSelectBulk) return
        val old = bulkSelection?.rows.orEmpty()
        val rows = old + d.stacks.drop(page * 25).take(25).filter { it.editable && old.none { r -> r.objectKey == it.objectKey } }
        if (rows.isNotEmpty()) bulkSelection = ProjectedDroneBulkSelection(d.fitId, d.revision, fit()!!.name, OfflineFeatureCodec.frozen(rows))
    }
    fun clearBulk() {
        if (editing) return
        bulkSelection = null; bulkDraft = null; error = null
        message = "Selection and its range draft discarded. No edit was added."
    }
    val canReviewBulk get() = available && draft == null && bulkStale && bulkSelection?.let { old -> currentDetails?.let { d ->
        d.fitId == old.fitId && old.rows.all { row -> d.stacks.any { it.objectKey == row.objectKey && it.itemId == row.itemId && it.editable } }
    } } == true
    fun reviewBulk() {
        val old = bulkSelection ?: return
        if (!canReviewBulk) return
        val d = currentDetails!!
        val rows = old.rows.map { row -> d.stacks.single { it.objectKey == row.objectKey && it.itemId == row.itemId } }
        val reviewed = ProjectedDroneBulkSelection(d.fitId, d.revision, fit()!!.name, OfflineFeatureCodec.frozen(rows))
        bulkSelection = reviewed
        if (bulkDraft != null) bulkDraft = ProjectedDroneBulkRangeDraft.capture(reviewed)
        error = null; message = "Current selected objects loaded. Previous range draft discarded; review before applying."
    }
    fun beginBulkRange(selection: ProjectedDroneBulkSelection) {
        if (!canBulk(selection)) return
        bulkDraft = ProjectedDroneBulkRangeDraft.capture(selection); error = null; message = null
    }
    fun changeBulkRange(text: String) {
        if (editing || text.length > 100) return
        bulkDraft = bulkDraft?.copy(text = text, mode = ProjectedDroneBulkRangeMode.VALUE)
    }
    fun defaultBulkRange() {
        if (!editing) bulkDraft = bulkDraft?.copy(text = "", mode = ProjectedDroneBulkRangeMode.DEFAULT)
    }
    fun discardBulkRange() {
        if (!editing) { bulkDraft = null; error = null; message = "Selected range draft discarded. No edit was added." }
    }
    fun saveBulkRange(context: Context) {
        val d = bulkDraft ?: return
        val selection = d.selection
        if (!available || draft != null || selection !== bulkSelection || !isBulkCurrent(selection)) return
        if (d.mode == ProjectedDroneBulkRangeMode.MIXED) { error = "Choose a range or explicitly choose Default for the selected stacks."; return }
        // Preserve the captured raw value even if kilometre formatting underflows or rounds.
        if (d.mode != ProjectedDroneBulkRangeMode.DEFAULT && !d.mixed && d.text.trim() == d.initial.trim()) {
            bulkDraft = null; error = null; message = "Selected ranges are unchanged. No edit was added to history."; return
        }
        val range = if (d.mode == ProjectedDroneBulkRangeMode.DEFAULT) null else try {
            require(d.text.isNotBlank()) { "Enter a range in km, or explicitly choose Default." }
            ProjectedFitInputs.rangeM(d.text)
        } catch (_: IllegalArgumentException) { error = "Enter a finite, nonnegative range in km, or explicitly choose Default."; return }
        if (selection.rows.all { ProjectedFitInputs.sameRange(it.rangeM, range) }) {
            bulkDraft = null; error = null; message = "Selected ranges are unchanged. No edit was added to history."; return
        }
        submit(context, selection.fitId, selection.revision, BridgeOperation.SetProjectedDroneRanges(selection.fitId, selection.wireRows(), range),
            "Selected ranges saved together. Review the refreshed selection before another bulk edit.", savedBulkDraft = d)
    }
    fun bulkActive(context: Context, selection: ProjectedDroneBulkSelection, active: Boolean) {
        if (!canBulk(selection)) return
        submit(context, selection.fitId, selection.revision, BridgeOperation.SetProjectedDronesActive(selection.fitId, selection.wireRows(), active),
            "Selected activation reviewed by the engine. Partial or recipient-blocked stacks may stay unchanged. An unchanged saved graph adds no history; review the refreshed counts.")
    }
    fun removeBulk(context: Context, selection: ProjectedDroneBulkSelection) {
        if (!canBulk(selection)) return
        submit(context, selection.fitId, selection.revision, BridgeOperation.RemoveProjectedDrones(selection.fitId, selection.wireRows()),
            "Selected complete stacks removed together. Undo restores counts, ranges and identities.", removedSelection = selection)
    }
    fun load(context: Context, value: FitSnapshot, retry: Boolean = false) {
        val next = value.id to value.revision
        if (!retry && requested == next) return
        if (requested?.first != value.id) { selectedKey = null; page = 0; message = null }
        requested = next; details = null; loading = true; error = null
        options = null; optionsLoading = false; optionsError = null; ++optionGeneration
        val token = ++generation
        read(context, value.id, value.revision).whenCompleteAsync({ result, failure ->
            if (token == generation) {
                loading = false
                if (fit()?.let { it.id to it.revision } == next) {
                    if (failure != null) error = projectedDroneReadError(failure, "Projected drones could not be verified. Reload, or restart if the engine is unavailable.")
                    else if (result.fitId == next.first && result.revision == next.second) {
                        details = result
                        if (result.stacks.none { it.objectKey == selectedKey }) selectedKey = null
                        page = page.coerceAtMost((result.stacks.size - 1).coerceAtLeast(0) / 25)
                        selectedRow?.takeIf { it.editable && draft == null }?.let { select(context, it) }
                    } else error = "The fit changed while loading projected drones. Reload current values."
                } else requested = null
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun showPage(value: Int) { if (!editing) page = value.coerceIn(0, (currentDetails?.stacks?.size?.minus(1) ?: 0).coerceAtLeast(0) / 25) }
    fun select(context: Context, row: ProjectedDroneRow) {
        val a = anchor(row) ?: return
        if (!canEdit(a) || optionsLoading && selectedKey == row.objectKey) return
        selectedKey = row.objectKey; options = null; optionsError = null; optionsLoading = true
        val token = ++optionGeneration
        readOptions(context, a.fitId, a.revision, row).whenCompleteAsync({ result, failure ->
            if (token == optionGeneration) {
                optionsLoading = false
                if (isCurrent(a) && selectedKey == row.objectKey) {
                    if (failure != null) optionsError = projectedDroneReadError(failure, "This projected drone's choices could not be verified. Retry before editing.")
                    else if (result.fitId == a.fitId && result.revision == a.revision && result.index == row.index &&
                        result.objectKey == row.objectKey && result.itemId == row.itemId) options = result
                    else optionsError = "The projected drone changed. Reload its current choices."
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun beginRange(a: ProjectedDroneAnchor) {
        if (!canEdit(a)) return
        val text = ProjectedFitInputs.rangeText(a.row.rangeM)
        draft = ProjectedDroneDraft(ProjectedDroneDraftKind.RANGE, a, fit()!!.name, text, text); error = null; message = null
    }
    fun changeDraft(value: String) { if (!editing && value.length <= 100) draft = draft?.copy(text = value) }
    fun discardDraft() { if (!editing) { draft = null; error = null; message = "Draft discarded. No edit was added." } }
    val canReview get() = available && draft?.let { d -> currentDetails?.let { current ->
        current.fitId == d.anchor.fitId && current.stacks.any { it.objectKey == d.anchor.row.objectKey && it.editable }
    } } == true
    fun reviewDraft() {
        val old = draft ?: return
        if (!canReview) return
        val row = currentDetails!!.stacks.single { it.objectKey == old.anchor.row.objectKey }
        val text = if (old.kind == ProjectedDroneDraftKind.RANGE) ProjectedFitInputs.rangeText(row.rangeM) else row.amount.toString()
        draft = ProjectedDroneDraft(old.kind, anchor(row)!!, fit()!!.name, text, text)
        error = null; message = "Current value loaded. Previous draft discarded; review before saving."
    }
    fun beginAmount(a: ProjectedDroneAnchor) {
        if (!canEdit(a)) return
        val text = a.row.amount.toString()
        draft = ProjectedDroneDraft(ProjectedDroneDraftKind.AMOUNT, a, fit()!!.name, text, text)
        error = null; message = null
    }
    fun saveDraft(context: Context) {
        val d = draft ?: return
        if (!available || !isCurrent(d.anchor)) return
        // Kilometre formatting can underflow or round. Untouched text retains the raw metres.
        if (d.text.trim() == d.initial.trim()) {
            draft = null; error = null; message = "Value is unchanged. No edit was added to history."; return
        }
        val a = d.anchor
        val operation: BridgeOperation
        if (d.kind == ProjectedDroneDraftKind.RANGE) {
            val range = try { ProjectedFitInputs.rangeM(d.text) } catch (failure: IllegalArgumentException) { error = failure.message; return }
            if (ProjectedFitInputs.sameRange(range, a.row.rangeM)) {
                draft = null; error = null; message = "Range is unchanged. No edit was added to history."; return
            }
            operation = BridgeOperation.SetProjectedDroneRange(a.fitId, a.row.index, a.row.objectKey, range)
        } else {
            val text = d.text.trim()
            val amount = text.takeIf { it.isNotEmpty() && it.all { c -> c in '0'..'9' } }?.toIntOrNull()
            if (amount == null) { error = "Enter a whole quantity from 0 to 2147483647. Evaluation may require a smaller configuration."; return }
            if (amount == a.row.amount) {
                draft = null; error = null; message = "Quantity is unchanged. No edit was added to history."; return
            }
            operation = BridgeOperation.SetProjectedDroneAmount(a.fitId, a.row.index, a.row.objectKey, amount)
        }
        submit(context, a.fitId, a.revision, operation,
            "Projected drone input saved. Undo restores the captured inputs.", savedDraft = d)
    }
    private fun optionsCurrent(a: ProjectedDroneAnchor, before: ProjectedDroneOptions) = canEdit(a) && before === currentOptions &&
        before.index == a.row.index && before.objectKey == a.row.objectKey && before.itemId == a.row.itemId
    fun active(context: Context, a: ProjectedDroneAnchor, before: ProjectedDroneOptions, value: Boolean) {
        if (!optionsCurrent(a, before) || value == (a.row.active > 0) || value && !before.activationAllowed) return
        submit(context, a.fitId, a.revision, BridgeOperation.SetProjectedDroneActive(a.fitId, a.row.index, a.row.objectKey, value),
            if (value) "Stack activated. Undo restores the previous active quantity." else "Stack deactivated. Undo restores the previous active quantity.")
    }
    fun variation(context: Context, a: ProjectedDroneAnchor, before: ProjectedDroneOptions, choice: ProjectedDroneVariation) {
        if (!optionsCurrent(a, before) || choice !in before.variations || !choice.enabled || choice.id == a.row.itemId) return
        submit(context, a.fitId, a.revision, BridgeOperation.ChangeProjectedDroneVariation(a.fitId, a.row.index, a.row.objectKey, choice.id),
            "Variation saved. An existing destination keeps its range; a new destination uses default range. Undo restores the captured inputs.")
    }
    fun remove(context: Context, a: ProjectedDroneAnchor, amount: Int) {
        if (!canEdit(a) || amount !in 1..a.row.amount) return
        submit(context, a.fitId, a.revision, BridgeOperation.RemoveProjectedDrone(a.fitId, a.row.index, a.row.objectKey, amount),
            "Projected drones removed. Undo restores quantity, active count and range.")
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
                    if (failure != null) addError = projectedDroneReadError(failure, "Projectability could not be checked. Retry before adding.")
                    else if (result.fitId == next.first && result.revision == next.second && result.itemId == next.third) addOptions = result
                    else addError = "The fit changed while checking this item. Reload its projection options."
                } else addRequested = null
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun add(context: Context, itemId: Int, onSaved: () -> Unit) {
        val o = currentAdd(itemId) ?: return
        if (editing || addLoading || draft != null || bulkDraft != null || !o.enabled) return
        submit(context, o.fitId, o.revision, BridgeOperation.AddProjectedDrone(o.fitId, itemId),
            "One projected drone added or merged into its existing stack. Undo is available.", onSaved = onSaved)
    }
    private fun submit(context: Context, fitId: String, revision: Long, operation: BridgeOperation, success: String,
        savedDraft: ProjectedDroneDraft? = null, savedBulkDraft: ProjectedDroneBulkRangeDraft? = null,
        removedSelection: ProjectedDroneBulkSelection? = null, onSaved: () -> Unit = {}) {
        editing = true; error = null; addError = null; message = null
        options = null; ++optionGeneration; optionsLoading = false
        val pending = try { dispatch(context, operation, mapOf(fitId to revision)) } catch (_: Exception) {
            editing = false; error = "The projected edit could not be confirmed. Check engine status before retrying."; return
        }
        pending.whenCompleteAsync({ result, failure ->
            editing = false
            if (failure == null && result.isSuccess && savedDraft != null && draft === savedDraft) draft = null
            if (failure == null && result.isSuccess && savedBulkDraft != null && bulkDraft === savedBulkDraft) bulkDraft = null
            if (failure == null && result.isSuccess && removedSelection != null && bulkSelection === removedSelection) bulkSelection = null
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
internal fun ProjectedDroneEquipmentActions(model: ProjectedDroneModel, item: EquipmentItem, onSaved: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = engine as? EngineState.Ready
    val fit = ready?.fit ?: return
    if (ready.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) return
    LaunchedEffect(fit.id, fit.revision, item.id) { model.loadAdd(context, fit, item.id) }
    if (model.addLoading) Text("Checking projected-drone eligibility…", Modifier.testTag("equipment-project-drone-loading"))
    model.addError?.let {
        Text(it, Modifier.testTag("equipment-project-drone-error"), color = MaterialTheme.colorScheme.error)
        TextButton(onClick = { model.loadAdd(context, fit, item.id, true) }, enabled = !model.addLoading && !model.editing,
            modifier = Modifier.testTag("equipment-project-drone-retry")) { Text("Check projected drone options again") }
    }
    val options = model.currentAdd(item.id) ?: return
    if (options.isDrone && options.isProjectable) {
        options.unavailableReason?.let { Text(it, Modifier.testTag("equipment-project-drone-unavailable")) }
        if (model.draft != null || model.bulkDraft != null) Text("Finish or discard the retained projected drone draft before adding another drone.")
        Button(onClick = { model.add(context, item.id, onSaved) },
            enabled = options.enabled && !model.editing && !model.addLoading && model.draft == null && model.bulkDraft == null,
            modifier = Modifier.testTag("equipment-project-drone")) { Text("Project one drone onto this fit") }
        Text("Adds an independent incoming drone. Same-type drones merge into one stack; local drone bay and bandwidth limits do not apply.")
    }
}

@Composable
internal fun ProjectedDroneEditor(model: ProjectedDroneModel, onBack: () -> Unit, onBrowse: () -> Unit, onInspectBase: (Int) -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = state as? EngineState.Ready
    val fit = ready?.fit
    BackHandler { onBack() }
    Text("Individual projected drones", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("projected-drones-back")) { Text("Back to fitting") }
    model.draft?.let { draft ->
        val range = draft.kind == ProjectedDroneDraftKind.RANGE
        val kind = if (range) "range" else "amount"
        Text("${if (range) "Range" else "Quantity"} draft: ${draft.fitName} · ${draft.anchor.row.name}", style = MaterialTheme.typography.titleMedium)
        if (model.draftStale) Text("The fit or projected stack changed, or is unavailable. Your draft is retained. Discard it or explicitly review current values before saving.",
            Modifier.testTag("projected-drone-draft-stale"), color = MaterialTheme.colorScheme.error)
        OutlinedTextField(draft.text, model::changeDraft, enabled = !model.editing, singleLine = true,
            label = { Text(if (range) "Range in km (blank = default)" else "Total quantity (0 removes stack)") },
            modifier = Modifier.fillMaxWidth().testTag("projected-drone-$kind-input"))
        if (range) {
            Text("Blank uses the engine default. Zero is an explicit zero-metre range.")
            Text("Captured range: ${draft.anchor.row.rangeM?.let { "$it m" } ?: "Default"}. Saving unchanged text preserves this exact value.")
        } else {
            Text("If partly active, changing total changes the active quantity by the same difference, bounded by zero and the new total. Inactive stacks stay inactive.")
            Text("Evaluation and storage budgets can refuse a large configuration; these are not game quantity caps.")
        }
        Button(onClick = { model.saveDraft(context) }, enabled = model.available && !model.draftStale,
            modifier = Modifier.testTag("projected-drone-draft-save")) { Text(if (range) "Save range" else "Save quantity") }
        if (model.draftStale) TextButton(onClick = model::reviewDraft, enabled = model.canReview,
            modifier = Modifier.testTag("projected-drone-draft-review")) { Text("Discard draft and review current value") }
        TextButton(onClick = model::discardDraft, enabled = !model.editing,
            modifier = Modifier.testTag("projected-drone-draft-discard")) { Text("Discard draft") }
    }
    ProjectedDroneBulkControls(model)
    if (fit == null) {
        when {
            state is EngineState.Loading -> Text("Loading the fitting library…", Modifier.testTag("projected-drones-loading"))
            state is EngineState.Failed || (state as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ->
                Text("The fitting engine is unavailable. Restart before editing.", Modifier.testTag("projected-drones-unavailable"))
            else -> Text("Open a fit to manage its individual projected drones.", Modifier.testTag("projected-drones-no-fit"))
        }
        return
    }
    Text("${fit.name} · ${fit.ship}", Modifier.testTag("projected-drones-recipient"), style = MaterialTheme.typography.titleLarge)
    if (ready.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) {
        Text("The fitting engine is unavailable. Restart before editing.", Modifier.testTag("projected-drones-unavailable")); return
    }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("Incoming drones affect this recipient only, not onward saved-fit recipients. EFT export omits individual projected objects.")
    Text("Total and active quantities are shown separately. Deactivate then activate to enable every drone; an already-active partial stack stays partial.")
    model.error?.let { Text(it, Modifier.testTag("projected-drones-error"), color = MaterialTheme.colorScheme.error) }
    model.message?.let { Text(it, Modifier.testTag("projected-drones-message")) }
    if (model.loading) Text("Loading projected drones…", Modifier.testTag("projected-drones-loading"))
    if (model.editing) Text("Saving projected drone edit…", Modifier.testTag("projected-drones-saving"))
    if (!model.loading) TextButton(onClick = { model.load(context, fit, true) }, enabled = !model.editing,
        modifier = Modifier.testTag("projected-drones-reload")) { Text("Reload projected drones") }
    val d = model.currentDetails ?: return
    if (d.isStructure) Text("Individual projected drone editing is unavailable for structures.", Modifier.testTag("projected-drones-structure"))
    TextButton(onClick = onBrowse, enabled = !model.editing && !d.isStructure,
        modifier = Modifier.testTag("projected-drones-browse")) { Text("Browse equipment to project") }
    if (d.stacks.isEmpty()) Text("No individual drones are projected onto this fit.", Modifier.testTag("projected-drones-empty"))
    for (row in d.stacks.drop(model.page * 25).take(25)) key(row.objectKey) {
        val a = model.anchor(row)!!
        Card(Modifier.fillMaxWidth().testTag("projected-drone-${row.index}")) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("${row.index + 1} · ${row.name}", style = MaterialTheme.typography.titleMedium)
                Row {
                    Checkbox(checked = model.bulkSelection?.rows?.any { it.objectKey == row.objectKey } == true,
                        onCheckedChange = { model.toggleBulk(row) }, enabled = row.editable && model.canSelectBulk,
                        modifier = Modifier.testTag("projected-drone-${row.index}-bulk-select").semantics {
                            contentDescription = "Select ${row.name}, stack ${row.index + 1}, for bulk edit"
                        })
                    Text("Select stack for bulk edit")
                }
                Text("${row.active} active / ${row.amount} total", Modifier.testTag("projected-drone-${row.index}-quantity"))
                Text("Range: ${row.rangeM?.let { "$it m (${ProjectedFitInputs.rangeText(it)} km)" } ?: "Default"}", Modifier.testTag("projected-drone-${row.index}-range"))
                row.unavailableReason?.let { Text(it, Modifier.testTag("projected-drone-${row.index}-unavailable")) }
                TextButton(onClick = { onInspectBase(row.itemId) }, modifier = Modifier.testTag("projected-drone-${row.index}-inspect-base")) { Text("Inspect base item (unmodified attributes)") }
                TextButton(onClick = { model.beginAmount(a) }, enabled = model.canEdit(a),
                    modifier = Modifier.testTag("projected-drone-${row.index}-edit-amount")) { Text("Edit total quantity") }
                TextButton(onClick = { model.beginRange(a) }, enabled = model.canEdit(a),
                    modifier = Modifier.testTag("projected-drone-${row.index}-edit-range")) { Text("Edit range") }
                TextButton(onClick = { model.remove(context, a, 1) }, enabled = model.canEdit(a),
                    modifier = Modifier.testTag("projected-drone-${row.index}-remove-one")) { Text("Remove one drone") }
                Text("Remove one preserves the current active count up to the remaining total; changing total has different partial-active behavior.")
                TextButton(onClick = { model.remove(context, a, row.amount) }, enabled = model.canEdit(a),
                    modifier = Modifier.testTag("projected-drone-${row.index}-remove-stack")) { Text("Remove entire stack") }
                TextButton(onClick = { model.select(context, row) }, enabled = model.canEdit(a) && !(model.optionsLoading && model.selectedKey == row.objectKey),
                    modifier = Modifier.testTag("projected-drone-${row.index}-options")) { Text("Load activation and variation choices") }
                if (model.selectedKey == row.objectKey) {
                    if (model.optionsLoading) Text("Loading this stack's choices…", Modifier.testTag("projected-drone-options-loading"))
                    model.optionsError?.let { Text(it, Modifier.testTag("projected-drone-options-error"), color = MaterialTheme.colorScheme.error) }
                    model.currentOptions?.let { options -> ProjectedDroneControls(model, a, options) }
                }
            }
        }
    }
    if (d.stacks.size > 25) {
        Text("Page ${model.page + 1} of ${(d.stacks.size + 24) / 25}")
        Row {
            TextButton(onClick = { model.showPage(model.page - 1) }, enabled = !model.editing && model.page > 0,
                modifier = Modifier.testTag("projected-drones-previous")) { Text("Previous stacks") }
            TextButton(onClick = { model.showPage(model.page + 1) }, enabled = !model.editing && (model.page + 1) * 25 < d.stacks.size,
                modifier = Modifier.testTag("projected-drones-next")) { Text("Next stacks") }
        }
    }
}

@Composable
private fun ProjectedDroneControls(model: ProjectedDroneModel, a: ProjectedDroneAnchor, options: ProjectedDroneOptions) {
    val context = LocalContext.current
    val available = model.canEdit(a)
    val index = a.row.index
    options.activationUnavailableReason?.let { Text(it, Modifier.testTag("projected-drone-$index-activation-unavailable")) }
    TextButton(onClick = { model.active(context, a, options, a.row.active == 0) },
        enabled = available && (a.row.active > 0 || options.activationAllowed),
        modifier = Modifier.testTag("projected-drone-$index-toggle")) { Text(if (a.row.active > 0) "Deactivate stack" else "Activate entire stack") }
    var variations by rememberSaveable(a.fitId, a.row.objectKey) { mutableStateOf(false) }
    if (options.variations.isNotEmpty()) {
        TextButton(onClick = { variations = !variations }, modifier = Modifier.testTag("projected-drone-$index-variations")) { Text(if (variations) "Hide variations" else "Choose variation") }
        if (variations) {
            Text("Variation removes this stack and appends a new type at default range. If that type already exists, it keeps its range and gains the entire quantity; its active count grows only if already active. Undo restores the original stacks.",
                Modifier.testTag("projected-drone-$index-variation-warning"))
            var query by rememberSaveable(a.fitId, a.row.objectKey) { mutableStateOf("") }
            var page by rememberSaveable(a.fitId, a.row.objectKey, query) { mutableStateOf(0) }
            OutlinedTextField(query, { query = it.take(200) }, label = { Text("Search variations") }, singleLine = true,
                modifier = Modifier.fillMaxWidth().testTag("projected-drone-$index-variation-search"))
            val matches = options.variations.filter { it.name.contains(query.trim(), true) }
            val last = (matches.size - 1).coerceAtLeast(0) / 25
            val current = page.coerceAtMost(last)
            Text("${matches.size} choices · page ${current + 1} of ${last + 1}")
            for (choice in matches.drop(current * 25).take(25)) TextButton(onClick = { model.variation(context, a, options, choice) },
                enabled = available && choice.enabled && choice.id != a.row.itemId,
                modifier = Modifier.testTag("projected-drone-$index-variation-${choice.id}")) { Text(choice.name + if (choice.id == a.row.itemId) " · current" else "") }
            if (last > 0) Row {
                TextButton(onClick = { page = current - 1 }, enabled = current > 0,
                    modifier = Modifier.testTag("projected-drone-$index-variation-previous")) { Text("Previous variations") }
                TextButton(onClick = { page = current + 1 }, enabled = current < last,
                    modifier = Modifier.testTag("projected-drone-$index-variation-next")) { Text("Next variations") }
            }
        }
    }
}
