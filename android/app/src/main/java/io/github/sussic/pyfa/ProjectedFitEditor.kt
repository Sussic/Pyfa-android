package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.concurrent.CompletableFuture
import kotlinx.coroutines.Dispatchers

/** The durable association is identified by its endpoints and their revisions. */
data class ProjectedFitAnchor(
    val sourceId: String, val targetId: String, val sourceRevision: Long, val targetRevision: Long,
    val link: ProjectionSnapshot?,
) {
    val revisions get() = mapOf(sourceId to sourceRevision, targetId to targetRevision)
}
enum class ProjectedFitField { COUNT, RANGE }
data class ProjectedFitDraft(val anchor: ProjectedFitAnchor, val field: ProjectedFitField, val initial: String, val text: String)

internal object ProjectedFitInputs {
    fun count(text: String): Int {
        val clean = text.trim()
        require(clean.matches(Regex("[0-9]+"))) { "Enter a whole source count from 0 to 20. Zero removes the link." }
        return clean.toIntOrNull()?.takeIf { it in 0..20 }
            ?: throw IllegalArgumentException("Enter a whole source count from 0 to 20. Zero removes the link.")
    }
    fun rangeM(text: String): Double? {
        val clean = text.trim()
        if (clean.isEmpty()) return null
        val km = clean.toDoubleOrNull()
        require(km != null && km.isFinite() && km >= 0 && (km * 1000).isFinite()) {
            "Enter a finite, nonnegative range in km, or leave it blank for the default."
        }
        return km * 1000
    }
    fun sameRange(first: Double?, second: Double?) = if (first == null || second == null) first == null && second == null else first == second
    fun rangeText(rangeM: Double?) = rangeM?.let { (it / 1000).toString() } ?: ""
}

class ProjectedFitModel(
    private val engineState: () -> EngineState = { EngineRuntime.state.value },
    private val fits: () -> List<FitSnapshot> = { EngineRuntime.library.value },
    private val dispatch: (Context, BridgeOperation, Map<String, Long>) -> CompletableFuture<BridgeResponse> =
        { context, operation, revisions -> EngineRuntime.request(context, operation, revisions) },
) : ViewModel() {
    var draft by mutableStateOf<ProjectedFitDraft?>(null); private set
    var busy by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var search by mutableStateOf(""); private set
    var returnRecipientId by mutableStateOf<String?>(null); private set
    var returnRecipientName by mutableStateOf<String?>(null); private set

    private fun selected() = (engineState() as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit
    private fun libraryFit(id: String) = fits().singleOrNull { it.id == id }
    val available get() = !busy && selected() != null
    val actionsAvailable get() = available && draft == null
    fun search(value: String) { search = value.take(200) }
    fun anchor(target: FitSnapshot, source: FitSnapshot) = ProjectedFitAnchor(
        source.id, target.id, source.revision, target.revision, target.projections.singleOrNull { it.sourceId == source.id })
    fun isCurrent(before: ProjectedFitAnchor): Boolean {
        val target = selected() ?: return false
        val source = libraryFit(before.sourceId) ?: return false
        val publishedTarget = libraryFit(before.targetId) ?: return false
        return publishedTarget.revision == before.targetRevision && target.id == before.targetId && target.revision == before.targetRevision &&
            source.revision == before.sourceRevision &&
            target.projections.singleOrNull { it.sourceId == before.sourceId } == before.link
    }
    val draftStale get() = draft?.let { !isCurrent(it.anchor) } == true
    fun canEdit(before: ProjectedFitAnchor) = actionsAvailable && before.link != null && isCurrent(before)
    fun begin(before: ProjectedFitAnchor, field: ProjectedFitField) {
        if (!canEdit(before)) return
        val link = checkNotNull(before.link)
        val text = if (field == ProjectedFitField.COUNT) link.amount.toString() else ProjectedFitInputs.rangeText(link.rangeM)
        draft = ProjectedFitDraft(before, field, text, text); error = null; message = null
    }
    fun change(value: String) { if (!busy && value.length <= 100) draft = draft?.copy(text = value) }
    fun discard() { if (!busy) { draft = null; error = null; message = "Draft discarded. No projection values were changed." } }
    /** Explicit review discards the old draft, never silently rebases its input. */
    fun review() {
        val old = draft ?: return
        val target = selected() ?: return
        val source = libraryFit(old.anchor.sourceId) ?: return
        if (busy || target.id != old.anchor.targetId) return
        val next = anchor(target, source)
        val link = next.link ?: return
        val text = if (old.field == ProjectedFitField.COUNT) link.amount.toString() else ProjectedFitInputs.rangeText(link.rangeM)
        draft = ProjectedFitDraft(next, old.field, text, text)
        error = null; message = "Current link loaded. Previous draft discarded; review the values before saving."
    }
    val canReview get() = available && draft?.let { d -> selected()?.id == d.anchor.targetId &&
        selected()?.projections?.any { it.sourceId == d.anchor.sourceId } == true && libraryFit(d.anchor.sourceId) != null } == true
    fun canAdd(before: ProjectedFitAnchor) = actionsAvailable && isCurrent(before) && before.link?.amount != 20
    fun add(context: Context, before: ProjectedFitAnchor) {
        if (!canAdd(before)) return
        val action = when {
            before.link == null -> "Projected source added."
            before.link.amount > 20 -> "Source count normalized to 20."
            else -> "Projected source count increased."
        }
        submit(context, before, BridgeOperation.AddProjectedFit(before.sourceId, before.targetId), "$action Undo is available.")
    }
    fun active(context: Context, before: ProjectedFitAnchor) {
        if (!canEdit(before)) return
        submit(context, before, BridgeOperation.SetProjectedFitActive(before.sourceId, before.targetId, !before.link!!.active),
            "Projected source state saved. Undo is available.")
    }
    fun remove(context: Context, before: ProjectedFitAnchor) {
        if (!canEdit(before)) return
        submit(context, before, BridgeOperation.RemoveProjectedFit(before.sourceId, before.targetId), "Projected source removed. Undo is available.")
    }
    fun save(context: Context) {
        val before = draft ?: return
        if (!available || !isCurrent(before.anchor) || before.text == before.initial) return
        val a = before.anchor
        val operation = try {
            when (before.field) {
                ProjectedFitField.COUNT -> BridgeOperation.SetProjectedFitAmount(a.sourceId, a.targetId, ProjectedFitInputs.count(before.text))
                ProjectedFitField.RANGE -> BridgeOperation.SetProjectedFitRange(a.sourceId, a.targetId, ProjectedFitInputs.rangeM(before.text))
            }
        } catch (failure: IllegalArgumentException) { error = failure.message; return }
        val link = checkNotNull(a.link)
        val unchanged = when (operation) {
            is BridgeOperation.SetProjectedFitAmount -> operation.amount == link.amount
            is BridgeOperation.SetProjectedFitRange -> ProjectedFitInputs.sameRange(operation.rangeM, link.rangeM)
            else -> false
        }
        if (unchanged) {
            draft = null; error = null; message = "Projection values are unchanged. No edit was added to history."
            return
        }
        submit(context, a, operation, "Projection change saved. Undo is available.", before)
    }
    private fun submit(context: Context, before: ProjectedFitAnchor, operation: BridgeOperation, success: String,
        savedDraft: ProjectedFitDraft? = null) {
        busy = true; error = null; message = null
        val pending = try { dispatch(context, operation, before.revisions) } catch (_: Exception) {
            busy = false; error = "The projection edit could not be confirmed. Check engine status before retrying."; return
        }
        pending.whenCompleteAsync({ result, failure ->
            busy = false
            if (failure == null && result.isSuccess) {
                if (savedDraft != null && draft === savedDraft) draft = null
                if (selected()?.id == before.targetId) message = success
            } else if ((engineState() as? EngineState.Ready)?.fit?.id == before.targetId) {
                error = if (failure != null) "The engine could not confirm the projection edit. Restart before editing."
                    else result.error?.message ?: "The projection edit was refused. Review current values."
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun openSource(context: Context, before: ProjectedFitAnchor, onOpened: () -> Unit) {
        if (!available || !isCurrent(before) || before.link == null) return
        val recipient = selected() ?: return
        navigate(context, before.sourceId) {
            returnRecipientId = recipient.id; returnRecipientName = recipient.name; onOpened()
        }
    }
    fun returnToRecipient(context: Context, onReturned: () -> Unit) {
        val id = returnRecipientId ?: return
        if (!available) return
        if (libraryFit(id) == null) { error = "The projection recipient was deleted. Dismiss this return link and choose another fit."; return }
        navigate(context, id) { returnRecipientId = null; returnRecipientName = null; onReturned() }
    }
    fun dismissReturn() { if (!busy) { returnRecipientId = null; returnRecipientName = null } }
    private fun navigate(context: Context, id: String, onSelected: () -> Unit) {
        busy = true; error = null; message = null
        EngineRuntime.selectFit(context, id).whenCompleteAsync({ _, failure ->
            busy = false
            if (failure == null && selected()?.id == id) onSelected()
            else error = "The fit could not be opened. Check that it still exists and the engine is available."
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun ProjectedFitReturn(model: ProjectedFitModel, onReturned: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val library by EngineRuntime.library.collectAsState(context = Dispatchers.Main)
    val id = model.returnRecipientId ?: return
    val available = !model.busy && state is EngineState.Ready && (state as? EngineState.Ready)?.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
    Text("Projection recipient: ${library.find { it.id == id }?.name ?: model.returnRecipientName}")
    if (library.none { it.id == id }) Text("This recipient was deleted.", Modifier.testTag("projections-return-missing"))
    Button(onClick = { model.returnToRecipient(context, onReturned) }, enabled = available && library.any { it.id == id },
        modifier = Modifier.testTag("projections-return")) { Text("Return to projection recipient") }
    TextButton(onClick = model::dismissReturn, enabled = !model.busy, modifier = Modifier.testTag("projections-return-dismiss")) { Text("Dismiss return link") }
    model.error?.let { Text(it, Modifier.testTag("projections-navigation-error"), color = MaterialTheme.colorScheme.error) }
}

@Composable
internal fun ProjectedFitEditor(model: ProjectedFitModel, onBack: () -> Unit, onSource: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val library by EngineRuntime.library.collectAsState(context = Dispatchers.Main)
    val ready = state as? EngineState.Ready
    val target = ready?.fit
    BackHandler { onBack() }
    Text("Saved-fit projections", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("projections-back")) { Text("Back to fitting") }
    if (target == null) {
        when {
            state is EngineState.Loading -> Text("Loading the fitting library…", Modifier.testTag("projections-loading"))
            state is EngineState.Failed || (state as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ->
                Text("The fitting engine is unavailable. Restart before editing. Your draft has been retained.", Modifier.testTag("projections-unavailable"))
            else -> Text("Open a fit to manage its incoming projected sources.", Modifier.testTag("projections-no-fit"))
        }
        return
    }
    Text("Recipient: ${target.name} · ${target.ship}", Modifier.testTag("projections-recipient"), style = MaterialTheme.typography.titleLarge)
    if (ready.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) {
        Text("The fitting engine is unavailable. Restart before editing. Your draft has been retained.", Modifier.testTag("projections-unavailable")); return
    }
    if (model.busy) Text("Updating projections…", Modifier.testTag("projections-busy"))
    model.error?.let { Text(it, Modifier.testTag("projections-error"), color = MaterialTheme.colorScheme.error) }
    model.message?.let { Text(it, Modifier.testTag("projections-message")) }
    val draft = model.draft
    if (draft != null) {
        Text("Edit ${if (draft.field == ProjectedFitField.COUNT) "source count" else "range (km)"}", style = MaterialTheme.typography.titleMedium)
        Text("Source: ${library.find { it.id == draft.anchor.sourceId }?.name ?: "Deleted source"}")
        if (model.draftStale) Text("The source, recipient or link changed. Your draft is retained. Discard it or reload current values before saving.",
            Modifier.testTag("projections-draft-stale"), color = MaterialTheme.colorScheme.error)
        OutlinedTextField(value = draft.text, onValueChange = model::change, singleLine = true, enabled = !model.busy,
            label = { Text(if (draft.field == ProjectedFitField.COUNT) "Count (0 removes, maximum 20)" else "Range in km (blank = default)") },
            modifier = Modifier.fillMaxWidth().testTag("projections-draft-input"))
        if (draft.field == ProjectedFitField.RANGE) Text("Blank uses the engine default. Zero is an explicit zero-metre range.")
        Button(onClick = { model.save(context) }, enabled = model.available && !model.draftStale && draft.text != draft.initial,
            modifier = Modifier.testTag("projections-draft-save")) { Text("Save ${if (draft.field == ProjectedFitField.COUNT) "count" else "range"}") }
        if (model.draftStale) TextButton(onClick = model::review, enabled = model.canReview,
            modifier = Modifier.testTag("projections-draft-review")) { Text("Discard draft and review current values") }
        TextButton(onClick = model::discard, enabled = !model.busy, modifier = Modifier.testTag("projections-draft-discard")) { Text("Discard draft") }
    }
    for ((key, label) in listOf("scan_resolution" to "Recipient scan resolution", "max_velocity" to "Recipient maximum velocity")) {
        target.stats[key]?.let { Text("$label: ${formatStat(it)}", Modifier.testTag("projections-$key")) }
    }
    Text("Incoming sources (${target.projections.size})", style = MaterialTheme.typography.titleMedium)
    if (target.projections.isEmpty()) Text("No saved-fit sources are projected onto this fit.", Modifier.testTag("projections-empty"))
    var page by rememberSaveable(target.id) { mutableStateOf(0) }
    val lastPage = (target.projections.size - 1).coerceAtLeast(0) / 20
    val actualPage = page.coerceAtMost(lastPage)
    for (link in target.projections.drop(actualPage * 20).take(20)) {
        val source = library.find { it.id == link.sourceId }
        Text(source?.let { "${it.name} · ${it.ship}${if (it.id == target.id) " (self)" else ""}" } ?: "Source unavailable: ${link.sourceId}",
            style = MaterialTheme.typography.titleMedium, modifier = Modifier.testTag("projection-${link.sourceId}-name"))
        Text("Count: ${link.amount} · ${if (link.active) "Active" else "Inactive"} · Range: ${link.rangeM?.let { "${ProjectedFitInputs.rangeText(it)} km" } ?: "Default"}",
            Modifier.testTag("projection-${link.sourceId}-values"))
        if (link.amount > 20) Text("Stored count exceeds the current editor limit. State and range edits preserve it. Edit the count or use the explicit Normalize count to 20 action below to change it.")
        if (source != null) {
            val before = model.anchor(target, source)
            TextButton(onClick = { model.begin(before, ProjectedFitField.COUNT) }, enabled = model.canEdit(before),
                modifier = Modifier.testTag("projection-${source.id}-count")) { Text("Edit count") }
            TextButton(onClick = { model.begin(before, ProjectedFitField.RANGE) }, enabled = model.canEdit(before),
                modifier = Modifier.testTag("projection-${source.id}-range")) { Text("Edit range") }
            TextButton(onClick = { model.active(context, before) }, enabled = model.canEdit(before),
                modifier = Modifier.testTag("projection-${source.id}-active")) { Text(if (link.active) "Deactivate source" else "Activate source") }
            TextButton(onClick = { model.remove(context, before) }, enabled = model.canEdit(before),
                modifier = Modifier.testTag("projection-${source.id}-remove")) { Text("Remove source") }
            TextButton(onClick = { model.openSource(context, before, onSource) }, enabled = model.available && model.isCurrent(before),
                modifier = Modifier.testTag("projection-${source.id}-open")) { Text("Open source fit") }
        } else Text("Reload or reopen the fitting library before editing this link.")
    }
    if (lastPage > 0) {
        Text("Source page ${actualPage + 1} of ${lastPage + 1}")
        TextButton(onClick = { page = (actualPage - 1).coerceAtLeast(0) }, enabled = actualPage > 0) { Text("Previous sources") }
        TextButton(onClick = { page = actualPage + 1 }, enabled = actualPage < lastPage) { Text("Next sources") }
    }
    Text("Add a saved-fit source", style = MaterialTheme.typography.titleMedium)
    Text("Adding an existing source increases its count, up to 20. Older counts above 20 have a separate Normalize count to 20 action. You can project this fit onto itself. Finish or discard an open draft before another edit.")
    OutlinedTextField(model.search, model::search, label = { Text("Search source name or hull") }, singleLine = true,
        modifier = Modifier.fillMaxWidth().testTag("projections-search"))
    val matches = library.filter { it.name.contains(model.search.trim(), true) || it.ship.contains(model.search.trim(), true) }
    var pickerPage by rememberSaveable(target.id, model.search) { mutableStateOf(0) }
    val pickerLastPage = (matches.size - 1).coerceAtLeast(0) / 30
    val shownPage = pickerPage.coerceAtMost(pickerLastPage)
    Text("${matches.size} matching fits · page ${shownPage + 1} of ${pickerLastPage + 1}", Modifier.testTag("projections-match-count"))
    if (pickerLastPage > 0) {
        TextButton(onClick = { pickerPage = (shownPage - 1).coerceAtLeast(0) }, enabled = shownPage > 0,
            modifier = Modifier.testTag("projections-picker-previous")) { Text("Previous fits") }
        TextButton(onClick = { pickerPage = shownPage + 1 }, enabled = shownPage < pickerLastPage,
            modifier = Modifier.testTag("projections-picker-next")) { Text("Next fits") }
    }
    for (source in matches.drop(shownPage * 30).take(30)) {
        val before = model.anchor(target, source)
        Button(onClick = { model.add(context, before) }, enabled = model.canAdd(before),
            modifier = Modifier.fillMaxWidth().testTag("projection-${source.id}-add")) {
            val action = when {
                before.link == null -> "Add"
                before.link.amount > 20 -> "Normalize count to 20"
                before.link.amount == 20 -> "At maximum count 20"
                else -> "Add another"
            }
            Text("$action: ${source.name} · ${source.ship}${if (source.id == target.id) " (self)" else ""}")
        }
    }
}
