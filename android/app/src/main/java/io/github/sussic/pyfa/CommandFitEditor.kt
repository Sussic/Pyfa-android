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

/** Existing immutable graph snapshots are the authority; no second read/query cache. */
data class CommandFitAnchor(
    val sourceId: String, val targetId: String, val sourceRevision: Long, val targetRevision: Long,
    val link: CommandSnapshot?,
) {
    val revisions get() = mapOf(sourceId to sourceRevision, targetId to targetRevision)
}

class CommandFitModel(
    private val engineState: () -> EngineState = { EngineRuntime.state.value },
    private val fits: () -> List<FitSnapshot> = { EngineRuntime.library.value },
    private val dispatch: (Context, BridgeOperation, Map<String, Long>) -> CompletableFuture<BridgeResponse> =
        { context, operation, revisions -> EngineRuntime.request(context, operation, revisions) },
) : ViewModel() {
    var busy by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var search by mutableStateOf(""); private set
    var returnRecipientId by mutableStateOf<String?>(null); private set
    var returnRecipientName by mutableStateOf<String?>(null); private set
    private var displayedFit: String? = null

    private fun selected() = (engineState() as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit
    private fun libraryFit(id: String) = fits().singleOrNull { it.id == id }
    val available get() = !busy && selected() != null
    fun search(value: String) { search = value.take(200) }
    fun show(fitId: String) {
        if (displayedFit != fitId) { displayedFit = fitId; error = null; message = null }
    }
    fun anchor(target: FitSnapshot, source: FitSnapshot) = CommandFitAnchor(
        source.id, target.id, source.revision, target.revision, target.commands.singleOrNull { it.sourceId == source.id })
    fun isCurrent(before: CommandFitAnchor): Boolean {
        val target = selected() ?: return false
        val source = libraryFit(before.sourceId) ?: return false
        val publishedTarget = libraryFit(before.targetId) ?: return false
        return target.id == before.targetId && target.revision == before.targetRevision &&
            publishedTarget.revision == before.targetRevision && source.revision == before.sourceRevision &&
            target.commands.singleOrNull { it.sourceId == before.sourceId } == before.link
    }
    fun canAdd(before: CommandFitAnchor) = available && before.link == null && isCurrent(before)
    fun canEdit(before: CommandFitAnchor) = available && before.link != null && isCurrent(before)
    fun add(context: Context, before: CommandFitAnchor) {
        if (!canAdd(before)) return
        submit(context, before, BridgeOperation.AddCommandFit(before.sourceId, before.targetId), "Command source linked. Undo is available.")
    }
    fun setActive(context: Context, before: CommandFitAnchor, active: Boolean) {
        if (!canEdit(before) || before.link!!.active == active) return
        submit(context, before, BridgeOperation.SetCommandFitActive(before.sourceId, before.targetId, active),
            "Command link ${if (active) "enabled" else "disabled"}. Undo is available.")
    }
    fun remove(context: Context, before: CommandFitAnchor) {
        if (!canEdit(before)) return
        submit(context, before, BridgeOperation.RemoveCommandFit(before.sourceId, before.targetId), "Command source removed. Undo is available.")
    }
    private fun submit(context: Context, before: CommandFitAnchor, operation: BridgeOperation, success: String) {
        busy = true; error = null; message = null
        val pending = try { dispatch(context, operation, before.revisions) } catch (_: Exception) {
            busy = false; error = "The command edit could not be confirmed. Check engine status before retrying."; return
        }
        pending.whenCompleteAsync({ result, failure ->
            busy = false
            // Other navigation may finish before this callback; never repaint another fit.
            if ((engineState() as? EngineState.Ready)?.fit?.id == before.targetId) {
                if (failure == null && result.isSuccess) message = success
                else error = if (failure != null) "The engine could not confirm the command edit. Restart before editing."
                    else result.error?.message ?: "The command edit was refused. Review current values."
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun openSource(context: Context, before: CommandFitAnchor, onOpened: () -> Unit) {
        if (!canEdit(before)) return
        val recipient = selected() ?: return
        navigate(context, before.sourceId) {
            returnRecipientId = recipient.id; returnRecipientName = recipient.name; onOpened()
        }
    }
    fun returnToRecipient(context: Context, onReturned: () -> Unit) {
        val id = returnRecipientId ?: return
        if (!available) return
        if (libraryFit(id) == null) { error = "The command recipient was deleted. Dismiss this return link and choose another fit."; return }
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
internal fun CommandFitReturn(model: CommandFitModel, onReturned: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val library by EngineRuntime.library.collectAsState(context = Dispatchers.Main)
    val id = model.returnRecipientId ?: return
    val available = !model.busy && state is EngineState.Ready && (state as? EngineState.Ready)?.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
    Text("Command recipient: ${library.find { it.id == id }?.name ?: model.returnRecipientName}")
    if (library.none { it.id == id }) Text("This recipient was deleted.", Modifier.testTag("commands-return-missing"))
    Button(onClick = { model.returnToRecipient(context, onReturned) }, enabled = available && library.any { it.id == id },
        modifier = Modifier.testTag("commands-return")) { Text("Return to command recipient") }
    TextButton(onClick = model::dismissReturn, enabled = !model.busy, modifier = Modifier.testTag("commands-return-dismiss")) { Text("Dismiss command return link") }
    model.error?.let { Text(it, Modifier.testTag("commands-navigation-error"), color = MaterialTheme.colorScheme.error) }
}

@Composable
internal fun CommandFitEditor(model: CommandFitModel, onBack: () -> Unit, onSource: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val library by EngineRuntime.library.collectAsState(context = Dispatchers.Main)
    val ready = state as? EngineState.Ready
    val target = ready?.fit
    BackHandler { onBack() }
    Text("Saved command fits", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("commands-back")) { Text("Back to fitting") }
    if (target == null) {
        when {
            state is EngineState.Loading -> Text("Loading the fitting library…", Modifier.testTag("commands-loading"))
            state is EngineState.Failed || (state as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ->
                Text("The fitting engine is unavailable. Restart before editing.", Modifier.testTag("commands-unavailable"))
            else -> Text("Open a fit to manage its incoming command sources.", Modifier.testTag("commands-no-fit"))
        }
        return
    }
    LaunchedEffect(target.id) { model.show(target.id) }
    Text("Recipient: ${target.name} · ${target.ship}", Modifier.testTag("commands-recipient"), style = MaterialTheme.typography.titleLarge)
    if (ready.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) {
        Text("The fitting engine is unavailable. Restart before editing.", Modifier.testTag("commands-unavailable")); return
    }
    Text("A command link does not guarantee a bonus. Fit, load and activate appropriate command bursts in the source; its hull, skills and applied implants affect the engine's result. A self link adds no extra incoming bonus.",
        Modifier.testTag("commands-effect-explanation"))
    if (model.busy) Text("Updating command links…", Modifier.testTag("commands-busy"))
    model.error?.let { Text(it, Modifier.testTag("commands-error"), color = MaterialTheme.colorScheme.error) }
    model.message?.let { Text(it, Modifier.testTag("commands-message")) }
    Text("Incoming command sources (${target.commands.size})", style = MaterialTheme.typography.titleMedium)
    if (target.commands.isEmpty()) Text("No saved command sources are linked to this fit.", Modifier.testTag("commands-empty"))
    var page by rememberSaveable(target.id) { mutableStateOf(0) }
    val lastPage = (target.commands.size - 1).coerceAtLeast(0) / 20
    val actualPage = page.coerceAtMost(lastPage)
    for (link in target.commands.drop(actualPage * 20).take(20)) {
        val source = library.find { it.id == link.sourceId }
        Text(source?.let { "${it.name} · ${it.ship}${if (it.id == target.id) " (self)" else ""}" } ?: "Source unavailable: ${link.sourceId}",
            style = MaterialTheme.typography.titleMedium, modifier = Modifier.testTag("command-${link.sourceId}-name"))
        Text(if (link.active) "Command link enabled" else "Command link disabled", Modifier.testTag("command-${link.sourceId}-state"))
        if (source != null) {
            val before = model.anchor(target, source)
            TextButton(onClick = { model.setActive(context, before, !link.active) }, enabled = model.canEdit(before),
                modifier = Modifier.testTag("command-${source.id}-active")) { Text(if (link.active) "Disable command source" else "Enable command source") }
            TextButton(onClick = { model.remove(context, before) }, enabled = model.canEdit(before),
                modifier = Modifier.testTag("command-${source.id}-remove")) { Text("Remove command source") }
            TextButton(onClick = { model.openSource(context, before, onSource) }, enabled = model.canEdit(before),
                modifier = Modifier.testTag("command-${source.id}-open")) { Text("Open command source fit") }
        } else Text("Reopen the fitting library before editing this link.")
    }
    if (lastPage > 0) {
        Text("Command-source page ${actualPage + 1} of ${lastPage + 1}")
        TextButton(onClick = { page = (actualPage - 1).coerceAtLeast(0) }, enabled = actualPage > 0) { Text("Previous command sources") }
        TextButton(onClick = { page = actualPage + 1 }, enabled = actualPage < lastPage) { Text("Next command sources") }
    }
    Text("Add a saved command source", style = MaterialTheme.typography.titleMedium)
    Text("All saved fits are available. An existing association is already linked; adding it again does not increase its strength.")
    OutlinedTextField(model.search, model::search, label = { Text("Search command source name or hull") }, singleLine = true,
        modifier = Modifier.fillMaxWidth().testTag("commands-search"))
    val matches = library.filter { it.name.contains(model.search.trim(), true) || it.ship.contains(model.search.trim(), true) }
    var pickerPage by rememberSaveable(target.id, model.search) { mutableStateOf(0) }
    val pickerLastPage = (matches.size - 1).coerceAtLeast(0) / 30
    val shownPage = pickerPage.coerceAtMost(pickerLastPage)
    Text("${matches.size} matching fits · page ${shownPage + 1} of ${pickerLastPage + 1}", Modifier.testTag("commands-match-count"))
    if (pickerLastPage > 0) {
        TextButton(onClick = { pickerPage = (shownPage - 1).coerceAtLeast(0) }, enabled = shownPage > 0,
            modifier = Modifier.testTag("commands-picker-previous")) { Text("Previous fits") }
        TextButton(onClick = { pickerPage = shownPage + 1 }, enabled = shownPage < pickerLastPage,
            modifier = Modifier.testTag("commands-picker-next")) { Text("Next fits") }
    }
    for (source in matches.drop(shownPage * 30).take(30)) {
        val before = model.anchor(target, source)
        Button(onClick = { model.add(context, before) }, enabled = model.canAdd(before),
            modifier = Modifier.fillMaxWidth().testTag("command-${source.id}-add")) {
            Text("${if (before.link == null) "Add" else "Already linked"}: ${source.name} · ${source.ship}${if (source.id == target.id) " (self)" else ""}")
        }
    }
}
