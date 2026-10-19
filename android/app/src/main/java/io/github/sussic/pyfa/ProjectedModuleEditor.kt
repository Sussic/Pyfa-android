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

data class ProjectedModuleAnchor(val fitId: String, val revision: Long, val row: ProjectedModuleRow)
data class ProjectedModuleDraft(val anchor: ProjectedModuleAnchor, val fitName: String, val initial: String, val text: String)

/** One selected object's options and one explicitly reviewed range draft; no parallel edit queue. */
class ProjectedModuleModel(
    private val engineState: () -> EngineState = { EngineRuntime.state.value },
    private val read: (Context, String, Long) -> CompletableFuture<ProjectedModuleDetails> = EngineRuntime::projectedModuleDetails,
    private val readOptions: (Context, String, Long, ProjectedModuleRow) -> CompletableFuture<ProjectedModuleOptions> = EngineRuntime::projectedModuleOptions,
    private val readAdd: (Context, String, Long, Int) -> CompletableFuture<ProjectedModuleAddOptions> = EngineRuntime::projectedModuleAddOptions,
    private val previewCharges: (Context, ProjectedChargeCapture) -> CompletableFuture<ProjectedModuleChargePreview> = EngineRuntime::projectedModuleChargePreview,
    private val dispatch: (Context, BridgeOperation, Map<String, Long>) -> CompletableFuture<BridgeResponse> =
        { context, operation, revisions -> EngineRuntime.request(context, operation, revisions) },
) : ViewModel() {
    var details by mutableStateOf<ProjectedModuleDetails?>(null); private set
    var options by mutableStateOf<ProjectedModuleOptions?>(null); private set
    var loading by mutableStateOf(false); private set
    var optionsLoading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var optionsError by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var selectedKey by mutableStateOf<String?>(null); private set
    var page by mutableStateOf(0); private set
    var draft by mutableStateOf<ProjectedModuleDraft?>(null); private set
    var bulkSelection by mutableStateOf<ProjectedModuleBulkSelection?>(null); private set
    var bulkDraft by mutableStateOf<ProjectedModuleBulkRangeDraft?>(null); private set
    var addOptions by mutableStateOf<ProjectedModuleAddOptions?>(null); private set
    var addLoading by mutableStateOf(false); private set
    var addError by mutableStateOf<String?>(null); private set
    var chargeMainKey by mutableStateOf<String?>(null); private set
    var chargeScope by mutableStateOf(BulkScope.SELECTED); private set
    var chargeId by mutableStateOf<Int?>(null); private set
    var chargeChoices by mutableStateOf<List<ProjectedModuleCharge>>(emptyList()); private set
    var chargePreview by mutableStateOf<ProjectedModuleChargePreview?>(null); private set
    var chargeLoading by mutableStateOf(false); private set
    var chargeError by mutableStateOf<String?>(null); private set
    private var chargeCapture: ProjectedChargeCapture? = null
    private var chargeEpoch = 0L
    private fun invalidateCharges(clearChoices: Boolean = false) {
        ++chargeEpoch; chargePreview = null; chargeCapture = null; chargeError = null
        if (clearChoices) chargeChoices = emptyList()
    }
    /** Navigation invalidates pending replies, while retaining completed choices and UI inputs. */
    fun leaveChargeEditor() { ++chargeEpoch }
    val chargeMain get() = bulkSelection?.takeIf(::isBulkCurrent)?.rows?.singleOrNull { it.objectKey == chargeMainKey }
    val canConfigureCharges get() = actionsAvailable && !bulkStale && chargeMain != null
    val canPreviewCharges get() = canConfigureCharges && !chargeLoading
    fun canChooseChargeMain(row: ProjectedModuleRow) = canSelectBulk && bulkSelection?.rows?.any { it === row } == true
    fun chooseChargeMain(context: Context, row: ProjectedModuleRow) {
        if (!canChooseChargeMain(row)) return
        invalidateCharges(true); chargeMainKey = row.objectKey; chargeScope = BulkScope.SELECTED; chargeId = null
        refreshChargePreview(context)
    }
    fun chooseChargeScope(scope: BulkScope) {
        if (!canConfigureCharges || chargeScope == scope) return
        invalidateCharges(); chargeScope = scope
    }
    fun chooseBulkCharge(id: Int?) {
        if (!canConfigureCharges || id != null && chargeChoices.none { it.id == id } || chargeId == id) return
        invalidateCharges(); chargeId = id
    }
    private fun chargeCaptureCurrent(c: ProjectedChargeCapture) = actionsAvailable && currentDetails === c.details &&
        bulkSelection === c.selection && isBulkCurrent(c.selection) && chargeMain === c.main &&
        chargeScope == c.scope && chargeId == c.chargeId
    val currentChargePreview get() = chargePreview?.takeIf { chargeCapture?.let(::chargeCaptureCurrent) == true }
    val canApplyCharges get() = !chargeLoading && currentChargePreview?.let { it.available &&
        it.targets.any { target -> target.status == ProjectedChargeStatus.CHANGE } } == true
    fun refreshChargePreview(context: Context) {
        if (!canPreviewCharges) return
        val capture = ProjectedChargeCapture(currentDetails!!, bulkSelection!!, chargeMain!!, chargeScope, chargeId)
        invalidateCharges(); val token = chargeEpoch
        chargeLoading = true
        val pending = try { previewCharges(context, capture) } catch (_: Exception) {
            chargeLoading = false; chargeError = "Charge preview could not be verified. Refresh before applying."; return
        }
        pending.whenCompleteAsync({ result, failure ->
            // Hold the launch gate through actual completion even when the UI invalidates this request.
            chargeLoading = false
            if (token == chargeEpoch && chargeCaptureCurrent(capture)) {
                if (failure != null) chargeError = ProjectedModuleChargeCodec.failureMessage(failure)
                else try {
                    ProjectedModuleChargeCodec.correlate(result, capture)
                    chargeCapture = capture; chargePreview = result; chargeChoices = result.choices
                } catch (_: Exception) { chargeError = "Charge preview did not match the captured selection. Refresh current values." }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun applyCharges(context: Context, before: ProjectedModuleChargePreview) {
        if (!canApplyCharges || before !== currentChargePreview) return
        val capture = chargeCapture ?: return
        try { ProjectedModuleChargeCodec.correlate(before, capture) } catch (_: Exception) { return }
        val operation = BridgeOperation.SetProjectedModuleCharges(before.fitId, before.main.wire(),
            OfflineFeatureCodec.frozen(before.selection.map { it.wire() }), before.scope, before.chargeId,
            OfflineFeatureCodec.frozen(before.targets.map { it.identity.wire() }),
            OfflineFeatureCodec.frozen(before.targets.filter { it.status == ProjectedChargeStatus.CHANGE }.map { it.identity.wire() }))
        submit(context, before.fitId, before.revision, operation,
            "Previewed charge changes applied together. Review the refreshed selection before another edit.")
    }
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    private var optionGeneration = 0
    private var addRequested: Triple<String, Long, Int>? = null
    private var addGeneration = 0
    private fun fit() = (engineState() as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit
    val currentDetails get() = details?.takeIf { d -> fit()?.let { it.id == d.fitId && it.revision == d.revision } == true }
    val selectedRow get() = currentDetails?.modules?.singleOrNull { it.objectKey == selectedKey }
    val currentOptions get() = options?.takeIf { o -> currentDetails?.let { d -> selectedRow?.let { r ->
        o.fitId == d.fitId && o.revision == d.revision && o.index == r.index && o.objectKey == r.objectKey && o.itemId == r.itemId
    } } == true }
    val available get() = !editing && !loading && currentDetails?.isStructure == false
    val actionsAvailable get() = available && draft == null && bulkDraft == null
    val draftStale get() = draft?.let { !isCurrent(it.anchor) } == true
    fun anchor(row: ProjectedModuleRow): ProjectedModuleAnchor? = currentDetails?.takeIf { row in it.modules }
        ?.let { ProjectedModuleAnchor(it.fitId, it.revision, row) }
    fun isCurrent(a: ProjectedModuleAnchor): Boolean = currentDetails?.let {
        it.fitId == a.fitId && it.revision == a.revision && a.row in it.modules && !it.isStructure && a.row.editable
    } == true
    fun canEdit(a: ProjectedModuleAnchor) = actionsAvailable && isCurrent(a)
    val bulkStale get() = bulkSelection?.let { !isBulkCurrent(it) } == true
    fun isBulkCurrent(selection: ProjectedModuleBulkSelection) = currentDetails?.let { d ->
        !d.isStructure && d.fitId == selection.fitId && d.revision == selection.revision &&
            selection.rows.isNotEmpty() && selection.rows.all { it.editable && it in d.modules }
    } == true
    fun canBulk(selection: ProjectedModuleBulkSelection) = actionsAvailable && selection === bulkSelection && isBulkCurrent(selection)
    val canSelectBulk get() = actionsAvailable && !bulkStale
    fun toggleBulk(row: ProjectedModuleRow) {
        val a = anchor(row) ?: return
        if (!canSelectBulk || !isCurrent(a)) return
        invalidateCharges(true)
        val old = bulkSelection?.rows.orEmpty()
        val rows = if (old.any { it.objectKey == row.objectKey }) old.filterNot { it.objectKey == row.objectKey } else old + row
        bulkSelection = if (rows.isEmpty()) null else ProjectedModuleBulkSelection(a.fitId, a.revision, fit()!!.name, OfflineFeatureCodec.frozen(rows))
        error = null; message = null
    }
    fun selectBulkPage() {
        val d = currentDetails ?: return
        if (!canSelectBulk) return
        invalidateCharges(true)
        val old = bulkSelection?.rows.orEmpty()
        val rows = old + d.modules.drop(page * 25).take(25).filter { it.editable && old.none { r -> r.objectKey == it.objectKey } }
        if (rows.isNotEmpty()) bulkSelection = ProjectedModuleBulkSelection(d.fitId, d.revision, fit()!!.name, OfflineFeatureCodec.frozen(rows))
    }
    fun clearBulk() {
        if (editing) return
        invalidateCharges(true); chargeMainKey = null
        bulkSelection = null; bulkDraft = null; error = null
        message = "Selection and its range draft discarded. No edit was added."
    }
    val canReviewBulk get() = available && draft == null && bulkStale && bulkSelection?.let { old -> currentDetails?.let { d ->
        d.fitId == old.fitId && old.rows.all { row -> d.modules.any { it.objectKey == row.objectKey && it.itemId == row.itemId && it.editable } }
    } } == true
    fun reviewBulk() {
        val old = bulkSelection ?: return
        if (!canReviewBulk) return
        invalidateCharges(true)
        val d = currentDetails!!
        val rows = old.rows.map { row -> d.modules.single { it.objectKey == row.objectKey && it.itemId == row.itemId } }
        val reviewed = ProjectedModuleBulkSelection(d.fitId, d.revision, fit()!!.name, OfflineFeatureCodec.frozen(rows))
        bulkSelection = reviewed
        if (bulkDraft != null) bulkDraft = ProjectedModuleBulkRangeDraft.capture(reviewed)
        error = null; message = "Current selected objects loaded. Previous range draft discarded; review before applying."
    }
    fun beginBulkRange(selection: ProjectedModuleBulkSelection) {
        if (!canBulk(selection)) return
        invalidateCharges()
        bulkDraft = ProjectedModuleBulkRangeDraft.capture(selection); error = null; message = null
    }
    fun changeBulkRange(text: String) {
        if (editing || text.length > 100) return
        bulkDraft = bulkDraft?.copy(text = text, mode = ProjectedModuleBulkRangeMode.VALUE)
    }
    fun defaultBulkRange() {
        if (!editing) bulkDraft = bulkDraft?.copy(text = "", mode = ProjectedModuleBulkRangeMode.DEFAULT)
    }
    fun discardBulkRange() {
        if (!editing) { bulkDraft = null; error = null; message = "Selected range draft discarded. No edit was added." }
    }
    fun saveBulkRange(context: Context) {
        val d = bulkDraft ?: return
        val selection = d.selection
        if (!available || draft != null || selection !== bulkSelection || !isBulkCurrent(selection)) return
        if (d.mode == ProjectedModuleBulkRangeMode.MIXED) { error = "Choose a range or explicitly choose Default for the selected modules."; return }
        // Preserve the captured raw value even if kilometre formatting underflows or rounds.
        if (d.mode != ProjectedModuleBulkRangeMode.DEFAULT && !d.mixed && d.text.trim() == d.initial.trim()) {
            bulkDraft = null; error = null; message = "Selected ranges are unchanged. No edit was added to history."; return
        }
        val range = if (d.mode == ProjectedModuleBulkRangeMode.DEFAULT) null else try {
            require(d.text.isNotBlank()) { "Enter a range in km, or explicitly choose Default." }
            ProjectedFitInputs.rangeM(d.text)
        } catch (_: IllegalArgumentException) { error = "Enter a finite, nonnegative range in km, or explicitly choose Default."; return }
        if (selection.rows.all { ProjectedFitInputs.sameRange(it.rangeM, range) }) {
            bulkDraft = null; error = null; message = "Selected ranges are unchanged. No edit was added to history."; return
        }
        submit(context, selection.fitId, selection.revision, BridgeOperation.SetProjectedModuleRanges(selection.fitId, selection.wireRows(), range),
            "Selected ranges saved together. Review the refreshed selection before another bulk edit.", savedBulkDraft = d)
    }
    fun bulkState(context: Context, selection: ProjectedModuleBulkSelection, state: ProjectedModuleStateAction) {
        if (!canBulk(selection)) return
        submit(context, selection.fitId, selection.revision, BridgeOperation.SetProjectedModuleStates(selection.fitId, selection.wireRows(), state),
            "Selected states reviewed by the engine. An unchanged saved graph adds no history; review the refreshed selection before another bulk edit.")
    }
    fun removeBulk(context: Context, selection: ProjectedModuleBulkSelection) {
        if (!canBulk(selection)) return
        submit(context, selection.fitId, selection.revision, BridgeOperation.RemoveProjectedModules(selection.fitId, selection.wireRows()),
            "Selected projectors removed together. Undo restores their captured inputs.", removedSelection = selection)
    }
    fun load(context: Context, value: FitSnapshot, retry: Boolean = false) {
        val next = value.id to value.revision
        if (!retry && requested == next) return
        if (requested?.first != value.id) { selectedKey = null; page = 0; message = null }
        invalidateCharges(true)
        requested = next; details = null; loading = true; error = null
        options = null; optionsLoading = false; optionsError = null; ++optionGeneration
        val token = ++generation
        read(context, value.id, value.revision).whenCompleteAsync({ result, failure ->
            if (token == generation) {
                loading = false
                if (fit()?.let { it.id to it.revision } == next) {
                    if (failure != null) error = "Projected modules could not be verified. Reload, or restart if the engine is unavailable."
                    else if (result.fitId == next.first && result.revision == next.second) {
                        details = result
                        if (result.modules.none { it.objectKey == selectedKey }) selectedKey = null
                        page = page.coerceAtMost((result.modules.size - 1).coerceAtLeast(0) / 25)
                        selectedRow?.takeIf { it.editable && draft == null }?.let { select(context, it) }
                    } else error = "The fit changed while loading projected modules. Reload current values."
                } else requested = null
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun showPage(value: Int) { if (!editing) page = value.coerceIn(0, (currentDetails?.modules?.size?.minus(1) ?: 0).coerceAtLeast(0) / 25) }
    fun select(context: Context, row: ProjectedModuleRow) {
        val a = anchor(row) ?: return
        if (!canEdit(a) || optionsLoading && selectedKey == row.objectKey) return
        invalidateCharges()
        selectedKey = row.objectKey; options = null; optionsError = null; optionsLoading = true
        val token = ++optionGeneration
        readOptions(context, a.fitId, a.revision, row).whenCompleteAsync({ result, failure ->
            if (token == optionGeneration) {
                optionsLoading = false
                if (isCurrent(a) && selectedKey == row.objectKey) {
                    if (failure != null) optionsError = "This projected module's choices could not be verified. Retry before editing."
                    else if (result.fitId == a.fitId && result.revision == a.revision && result.index == row.index &&
                        result.objectKey == row.objectKey && result.itemId == row.itemId) options = result
                    else optionsError = "The projected module changed. Reload its current choices."
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun beginRange(a: ProjectedModuleAnchor) {
        if (!canEdit(a)) return
        invalidateCharges()
        val text = ProjectedFitInputs.rangeText(a.row.rangeM)
        draft = ProjectedModuleDraft(a, fit()!!.name, text, text); error = null; message = null
    }
    fun changeRange(value: String) { if (!editing && value.length <= 100) draft = draft?.copy(text = value) }
    fun discardRange() { if (!editing) { draft = null; error = null; message = "Range draft discarded. No edit was added." } }
    val canReview get() = available && draft?.let { d -> currentDetails?.let { current ->
        current.fitId == d.anchor.fitId && current.modules.any { it.objectKey == d.anchor.row.objectKey && it.editable }
    } } == true
    fun reviewRange() {
        val old = draft ?: return
        if (!canReview) return
        val row = currentDetails!!.modules.single { it.objectKey == old.anchor.row.objectKey }
        val text = ProjectedFitInputs.rangeText(row.rangeM)
        draft = ProjectedModuleDraft(anchor(row)!!, fit()!!.name, text, text)
        error = null; message = "Current range loaded. Previous draft discarded; review before saving."
    }
    fun saveRange(context: Context) {
        val d = draft ?: return
        if (!available || !isCurrent(d.anchor)) return
        // Formatting metres as kilometres is not always reversible (including underflow).
        // An untouched display must keep the captured raw input exactly.
        if (d.text.trim() == d.initial.trim()) {
            draft = null; error = null; message = "Range is unchanged. No edit was added to history."; return
        }
        val range = try { ProjectedFitInputs.rangeM(d.text) } catch (failure: IllegalArgumentException) { error = failure.message; return }
        if (ProjectedFitInputs.sameRange(range, d.anchor.row.rangeM)) {
            draft = null; error = null; message = "Range is unchanged. No edit was added to history."; return
        }
        val a = d.anchor
        submit(context, a.fitId, a.revision, BridgeOperation.SetProjectedModuleRange(a.fitId, a.row.index, a.row.objectKey, range),
            "Projected range saved. Undo is available.", savedDraft = d)
    }
    private fun optionsCurrent(a: ProjectedModuleAnchor, before: ProjectedModuleOptions) = canEdit(a) && before === currentOptions &&
        before.index == a.row.index && before.objectKey == a.row.objectKey && before.itemId == a.row.itemId
    fun state(context: Context, a: ProjectedModuleAnchor, before: ProjectedModuleOptions, action: ProjectedModuleAction) {
        if (!optionsCurrent(a, before) || action !in before.stateActions || !action.enabled) return
        submit(context, a.fitId, a.revision, BridgeOperation.SetProjectedModuleState(a.fitId, a.row.index, a.row.objectKey, action.id),
            "Projected state reviewed by the engine.")
    }
    fun charge(context: Context, a: ProjectedModuleAnchor, before: ProjectedModuleOptions, id: Int?) {
        if (!optionsCurrent(a, before) || id != null && before.charges.none { it.id == id } || id == a.row.chargeId) return
        submit(context, a.fitId, a.revision, BridgeOperation.SetProjectedModuleCharge(a.fitId, a.row.index, a.row.objectKey, id),
            "Projected charge saved. Undo is available.")
    }
    fun variation(context: Context, a: ProjectedModuleAnchor, before: ProjectedModuleOptions, choice: ProjectedModuleVariation) {
        if (!optionsCurrent(a, before) || choice !in before.variations || !choice.enabled || choice.id == a.row.itemId) return
        submit(context, a.fitId, a.revision, BridgeOperation.ChangeProjectedModuleVariation(a.fitId, a.row.index, a.row.objectKey, choice.id),
            "Variation saved at the end of the projected list; range reset to default. Undo restores the previous inputs.")
    }
    fun spool(context: Context, a: ProjectedModuleAnchor, before: ProjectedModuleOptions, cycles: Int?) {
        val spool = before.spool ?: return
        if (!optionsCurrent(a, before) || cycles != null && cycles !in spool.choices || cycles == spool.overrideCycles) return
        submit(context, a.fitId, a.revision, BridgeOperation.SetProjectedModuleSpool(a.fitId, a.row.index, a.row.objectKey, cycles),
            if (cycles == null) "Projected spool reset to the global default." else "Explicit projected spool cycles saved.")
    }
    fun remove(context: Context, a: ProjectedModuleAnchor) {
        if (!canEdit(a)) return
        submit(context, a.fitId, a.revision, BridgeOperation.RemoveProjectedModule(a.fitId, a.row.index, a.row.objectKey),
            "Projected module removed. Undo restores its captured inputs.")
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
                    if (failure != null) addError = "Projectability could not be checked. Retry before adding."
                    else if (result.fitId == next.first && result.revision == next.second && result.itemId == next.third) addOptions = result
                    else addError = "The fit changed while checking this item. Reload its projection options."
                } else addRequested = null
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun add(context: Context, itemId: Int, onSaved: () -> Unit) {
        val o = currentAdd(itemId) ?: return
        if (editing || addLoading || draft != null || bulkDraft != null || !o.enabled) return
        submit(context, o.fitId, o.revision, BridgeOperation.AddProjectedModule(o.fitId, itemId),
            "Individual projected module added. Undo is available.", onSaved = onSaved)
    }
    private fun submit(context: Context, fitId: String, revision: Long, operation: BridgeOperation, success: String,
        savedDraft: ProjectedModuleDraft? = null, savedBulkDraft: ProjectedModuleBulkRangeDraft? = null,
        removedSelection: ProjectedModuleBulkSelection? = null, onSaved: () -> Unit = {}) {
        invalidateCharges(true)
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
internal fun ProjectedModuleEquipmentActions(model: ProjectedModuleModel, item: EquipmentItem, onSaved: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = engine as? EngineState.Ready
    val fit = ready?.fit ?: return
    if (ready.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) return
    LaunchedEffect(fit.id, fit.revision, item.id) { model.loadAdd(context, fit, item.id) }
    if (model.addLoading) Text("Checking whether this item can be projected…", Modifier.testTag("equipment-project-loading"))
    model.addError?.let {
        Text(it, Modifier.testTag("equipment-project-error"), color = MaterialTheme.colorScheme.error)
        TextButton(onClick = { model.loadAdd(context, fit, item.id, true) }, enabled = !model.addLoading && !model.editing,
            modifier = Modifier.testTag("equipment-project-retry")) { Text("Check projection options again") }
    }
    val options = model.currentAdd(item.id) ?: return
    if (options.isModule && options.isProjectable) {
        options.unavailableReason?.let { Text(it, Modifier.testTag("equipment-project-unavailable")) }
        if (model.draft != null || model.bulkDraft != null) Text("Finish or discard the retained projected range draft before adding another projector.")
        Button(onClick = { model.add(context, item.id, onSaved) },
            enabled = options.enabled && !model.editing && !model.addLoading && model.draft == null && model.bulkDraft == null,
            modifier = Modifier.testTag("equipment-project-module")) { Text("Project module onto this fit") }
        Text("Adds an independent projector, not a fitted local module. Duplicate items remain separate projectors.")
    }
}

@Composable
internal fun ProjectedModuleEditor(model: ProjectedModuleModel, onBack: () -> Unit, onBrowse: () -> Unit, onInspectBase: (Int) -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val ready = state as? EngineState.Ready
    val fit = ready?.fit
    DisposableEffect(model, fit?.id, fit?.revision, ready?.error?.code) { onDispose { model.leaveChargeEditor() } }
    BackHandler { onBack() }
    Text("Individual projected modules", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("projected-modules-back")) { Text("Back to fitting") }
    // Retain and display even orphaned/cross-fit drafts; never replace their object implicitly.
    model.draft?.let { draft ->
        Text("Range draft: ${draft.fitName} · ${draft.anchor.row.name}", style = MaterialTheme.typography.titleMedium)
        if (model.draftStale) Text("The fit or projected object changed, or is unavailable. Your draft is retained. Discard it or explicitly review current values before saving.",
            Modifier.testTag("projected-module-range-stale"), color = MaterialTheme.colorScheme.error)
        OutlinedTextField(draft.text, model::changeRange, enabled = !model.editing, singleLine = true,
            label = { Text("Range in km (blank = default)") }, modifier = Modifier.fillMaxWidth().testTag("projected-module-range-input"))
        Text("Blank uses the engine default. Zero is an explicit zero-metre range.")
        Text("Captured range: ${draft.anchor.row.rangeM?.let { "$it m" } ?: "Default"}. Saving unchanged text preserves this exact value.")
        Button(onClick = { model.saveRange(context) }, enabled = model.available && !model.draftStale,
            modifier = Modifier.testTag("projected-module-range-save")) { Text("Save range") }
        if (model.draftStale) TextButton(onClick = model::reviewRange, enabled = model.canReview,
            modifier = Modifier.testTag("projected-module-range-review")) { Text("Discard draft and review current range") }
        TextButton(onClick = model::discardRange, enabled = !model.editing,
            modifier = Modifier.testTag("projected-module-range-discard")) { Text("Discard range draft") }
    }
    ProjectedModuleBulkControls(model)
    ProjectedModuleChargeControls(model)
    if (fit == null) {
        when {
            state is EngineState.Loading -> Text("Loading the fitting library…", Modifier.testTag("projected-modules-loading"))
            state is EngineState.Failed || (state as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ->
                Text("The fitting engine is unavailable. Restart before editing.", Modifier.testTag("projected-modules-unavailable"))
            else -> Text("Open a fit to manage its individual projectors.", Modifier.testTag("projected-modules-no-fit"))
        }
        return
    }
    Text("${fit.name} · ${fit.ship}", Modifier.testTag("projected-modules-recipient"), style = MaterialTheme.typography.titleLarge)
    if (ready.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) {
        Text("The fitting engine is unavailable. Restart before editing.", Modifier.testTag("projected-modules-unavailable")); return
    }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("These modules affect this recipient directly. They are not carried onward when this fit is projected onto another fit. EFT export omits individual projected objects.")
    model.error?.let { Text(it, Modifier.testTag("projected-modules-error"), color = MaterialTheme.colorScheme.error) }
    model.message?.let { Text(it, Modifier.testTag("projected-modules-message")) }
    if (model.loading) Text("Loading projected modules…", Modifier.testTag("projected-modules-loading"))
    if (model.editing) Text("Saving projected edit…", Modifier.testTag("projected-modules-saving"))
    if (!model.loading) TextButton(onClick = { model.load(context, fit, true) }, enabled = !model.editing,
        modifier = Modifier.testTag("projected-modules-reload")) { Text("Reload projected modules") }
    val d = model.currentDetails ?: return
    if (d.isStructure) Text("Individual projected module editing is unavailable for structures.", Modifier.testTag("projected-modules-structure"))
    TextButton(onClick = onBrowse, enabled = !model.editing && !d.isStructure,
        modifier = Modifier.testTag("projected-modules-browse")) { Text("Browse equipment to project") }
    if (d.modules.isEmpty()) Text("No individual modules are projected onto this fit.", Modifier.testTag("projected-modules-empty"))
    for (row in d.modules.drop(model.page * 25).take(25)) key(row.objectKey) {
        val a = model.anchor(row)!!
        Card(Modifier.fillMaxWidth().testTag("projected-module-${row.index}")) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("${row.index + 1} · ${row.name}", style = MaterialTheme.typography.titleMedium)
                Row {
                    Checkbox(checked = model.bulkSelection?.rows?.any { it.objectKey == row.objectKey } == true,
                        onCheckedChange = { model.toggleBulk(row) }, enabled = row.editable && model.canSelectBulk,
                        modifier = Modifier.testTag("projected-module-${row.index}-bulk-select").semantics {
                            contentDescription = "Select ${row.name}, projector ${row.index + 1}, for bulk edit"
                        })
                    Text("Select for bulk edit")
                }
                TextButton(onClick = { model.chooseChargeMain(context, row) }, enabled = model.canChooseChargeMain(row),
                    modifier = Modifier.testTag("projected-module-${row.index}-charge-main")) {
                    Text(if (model.chargeMainKey == row.objectKey) "Charge reference selected" else "Use selected module as charge reference")
                }
                Text("State: ${row.state.name}", Modifier.testTag("projected-module-${row.index}-state"))
                Text("Charge: ${row.chargeName ?: "Empty"}", Modifier.testTag("projected-module-${row.index}-charge"))
                Text("Range: ${row.rangeM?.let { "$it m (${ProjectedFitInputs.rangeText(it)} km)" } ?: "Default"}", Modifier.testTag("projected-module-${row.index}-range"))
                row.unavailableReason?.let { Text(it, Modifier.testTag("projected-module-${row.index}-unavailable")) }
                TextButton(onClick = { onInspectBase(row.itemId) }, modifier = Modifier.testTag("projected-module-${row.index}-inspect-base")) { Text("Inspect base item (unmodified attributes)") }
                TextButton(onClick = { model.beginRange(a) }, enabled = model.canEdit(a),
                    modifier = Modifier.testTag("projected-module-${row.index}-edit-range")) { Text("Edit range") }
                TextButton(onClick = { model.remove(context, a) }, enabled = model.canEdit(a),
                    modifier = Modifier.testTag("projected-module-${row.index}-remove")) { Text("Remove this projector") }
                TextButton(onClick = { model.select(context, row) }, enabled = model.canEdit(a) && !(model.optionsLoading && model.selectedKey == row.objectKey),
                    modifier = Modifier.testTag("projected-module-${row.index}-options")) { Text("Load state, charge, variation and spool choices") }
                if (model.selectedKey == row.objectKey) {
                    if (model.optionsLoading) Text("Loading this module's choices…", Modifier.testTag("projected-module-options-loading"))
                    model.optionsError?.let { Text(it, Modifier.testTag("projected-module-options-error"), color = MaterialTheme.colorScheme.error) }
                    model.currentOptions?.let { options -> ProjectedModuleControls(model, a, options) }
                }
            }
        }
    }
    if (d.modules.size > 25) {
        Text("Page ${model.page + 1} of ${(d.modules.size + 24) / 25}")
        Row {
            TextButton(onClick = { model.showPage(model.page - 1) }, enabled = !model.editing && model.page > 0,
                modifier = Modifier.testTag("projected-modules-previous")) { Text("Previous projectors") }
            TextButton(onClick = { model.showPage(model.page + 1) }, enabled = !model.editing && (model.page + 1) * 25 < d.modules.size,
                modifier = Modifier.testTag("projected-modules-next")) { Text("Next projectors") }
        }
    }
}

@Composable
private fun ProjectedModuleControls(model: ProjectedModuleModel, a: ProjectedModuleAnchor, options: ProjectedModuleOptions) {
    val context = LocalContext.current
    val available = model.canEdit(a)
    val index = a.row.index
    for (action in options.stateActions) TextButton(onClick = { model.state(context, a, options, action) },
        enabled = available && action.enabled, modifier = Modifier.testTag("projected-module-$index-state-${action.id.wire}")) { Text(action.label) }
    var charges by rememberSaveable(a.fitId, a.row.objectKey) { mutableStateOf(false) }
    var variations by rememberSaveable(a.fitId, a.row.objectKey) { mutableStateOf(false) }
    TextButton(onClick = { charges = !charges }, modifier = Modifier.testTag("projected-module-$index-charges")) { Text(if (charges) "Hide charges" else "Choose charge") }
    if (charges) {
        TextButton(onClick = { model.charge(context, a, options, null) }, enabled = available && a.row.chargeId != null,
            modifier = Modifier.testTag("projected-module-$index-charge-clear")) { Text("Clear loaded charge") }
        ProjectedModuleChoiceList("charge-$index", options.charges.map { it.id to it.name }, a.fitId + a.row.objectKey) { id, name ->
            TextButton(onClick = { model.charge(context, a, options, id) }, enabled = available && id != a.row.chargeId,
                modifier = Modifier.testTag("projected-module-$index-charge-$id")) { Text(name + if (id == a.row.chargeId) " · loaded" else "") }
        }
    }
    if (options.variations.isNotEmpty()) {
        TextButton(onClick = { variations = !variations }, modifier = Modifier.testTag("projected-module-$index-variations")) { Text(if (variations) "Hide variations" else "Choose variation") }
        if (variations) {
            Text("Changing variation removes this projector and appends its replacement. Range resets to default; an incompatible charge is cleared. Undo restores the captured original inputs.",
                Modifier.testTag("projected-module-$index-variation-warning"))
            ProjectedModuleChoiceList("variation-$index", options.variations.map { it.id to it.name }, a.fitId + a.row.objectKey) { id, name ->
                val choice = options.variations.single { it.id == id }
                TextButton(onClick = { model.variation(context, a, options, choice) }, enabled = available && choice.enabled && id != a.row.itemId,
                    modifier = Modifier.testTag("projected-module-$index-variation-$id")) { Text(name + if (id == a.row.itemId) " · current" else "") }
            }
        }
    }
    options.spool?.let { spool ->
        Text("Projected spool cycles", style = MaterialTheme.typography.titleMedium)
        Text(if (spool.overrideCycles == null) "Using global default" else "Explicit override: ${spool.overrideCycles} cycles",
            Modifier.testTag("projected-module-$index-spool-mode"))
        Text("Current: ${spool.currentCycles} cycles · ${spool.currentSeconds} s", Modifier.testTag("projected-module-$index-spool-current"))
        Text("Global default: ${spool.defaultCycles} cycles · ${spool.defaultSeconds} s")
        Text("Source range: ${spool.minimumCycles}–${spool.maximumCycles} cycles · ${spool.minimumSeconds}–${spool.maximumSeconds} s")
        if (spool.overrideCycles != null && spool.overrideCycles != spool.currentCycles)
            Text("EOS applies ${spool.currentCycles} cycles; the requested override remains ${spool.overrideCycles}.")
        for (group in spool.choices.chunked(3)) Row(Modifier.fillMaxWidth()) {
            for (cycles in group) TextButton(onClick = { model.spool(context, a, options, cycles) }, enabled = available && cycles != spool.overrideCycles,
                modifier = Modifier.weight(1f).testTag("projected-module-$index-spool-$cycles")) {
                Text("$cycles cycles" + when {
                    spool.overrideCycles != null && cycles == spool.currentCycles -> " · applied"
                    spool.overrideCycles == null && cycles == spool.defaultCycles -> " · default"
                    else -> ""
                })
            }
        }
        TextButton(onClick = { model.spool(context, a, options, null) }, enabled = available && spool.overrideCycles != null,
            modifier = Modifier.testTag("projected-module-$index-spool-reset")) { Text("Reset to global spool default") }
        Text("Explicit zero means no spool. Reset follows the global default.")
    }
}

@Composable
private fun ProjectedModuleChoiceList(tag: String, values: List<Pair<Int, String>>, key: String,
    content: @Composable (Int, String) -> Unit) {
    var query by rememberSaveable(key, tag) { mutableStateOf("") }
    var page by rememberSaveable(key, tag, query) { mutableStateOf(0) }
    OutlinedTextField(query, { query = it.take(200) }, label = { Text("Search choices") }, singleLine = true,
        modifier = Modifier.fillMaxWidth().testTag("projected-module-$tag-search"))
    val matches = values.filter { it.second.contains(query.trim(), true) }
    val last = (matches.size - 1).coerceAtLeast(0) / 25
    val current = page.coerceAtMost(last)
    Text("${matches.size} choices · page ${current + 1} of ${last + 1}")
    for ((id, name) in matches.drop(current * 25).take(25)) content(id, name)
    if (last > 0) Row {
        TextButton(onClick = { page = current - 1 }, enabled = current > 0, modifier = Modifier.testTag("projected-module-$tag-previous")) { Text("Previous choices") }
        TextButton(onClick = { page = current + 1 }, enabled = current < last, modifier = Modifier.testTag("projected-module-$tag-next")) { Text("Next choices") }
    }
}
