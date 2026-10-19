package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
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

/** Each screen incarnation and request has its own owner, even when all IDs match after reopening. */
class ModuleRahModel(
    private val featureContext: () -> OfflineContext? = { EngineRuntime.offlineFeatures.value?.context },
    private val activeFit: () -> Pair<String, Long>? = {
        (EngineRuntime.state.value as? EngineState.Ready)?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }
            ?.fit?.let { it.id to it.revision }
    },
    private val loadDetails: (Context, String, Long, Int) -> CompletableFuture<ModuleRahDetails> = { context, id, offset, limit ->
        EngineRuntime.moduleRahDetails(context, id, offset, limit)
    },
    private val request: (Context, OfflineDamageRequest) -> CompletableFuture<OfflineDamageResponse> = EngineRuntime::offlineDamagePatterns,
) : ViewModel() {
    var details by mutableStateOf<ModuleRahDetails?>(null); private set
    var options by mutableStateOf<OfflineDamageState?>(null); private set
    var loading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var reopenRequired by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var selectedKey by mutableStateOf<String?>(null); private set
    var searchText by mutableStateOf(""); private set
    var modulePage by mutableStateOf(0L); private set
    var patternPage by mutableStateOf(0L); private set
    private var requested: Triple<OfflineContext, String, Long>? = null
    private var generation = 0L
    private var screenOpen = false
    private var cleared = false
    val currentDetails get() = details?.takeIf { d -> screenOpen && featureContext() == d.context && activeFit() == (d.fitId to d.revision) }
    val available get() = screenOpen && !cleared && !reopenRequired && !loading && !editing && currentDetails != null
    val currentOptions get() = options?.takeIf { value -> value.context == featureContext() && (value.fitId to value.fitRevision) == activeFit() &&
        value.module?.objectKey == selectedKey && value.view.query == searchText && value.view.offset == patternPage * 20 }

    fun open() {
        if (cleared) return
        invalidate(); screenOpen = true; requested = null; details = null; options = null; selectedKey = null
        modulePage = 0; patternPage = 0; searchText = ""; error = null; message = null
    }
    fun close() { invalidate(); screenOpen = false; requested = null; details = null; options = null; selectedKey = null; error = null; message = null }
    private fun invalidate() { generation = Math.addExact(generation, 1); loading = false; editing = false }
    private fun owned(token: Long, source: OfflineContext, fit: Pair<String, Long>, key: String?, query: String, page: Long,
        accepted: OfflineDamageState? = null): Boolean {
        if (!screenOpen || cleared || token != generation || selectedKey != key || searchText != query || patternPage != page) return false
        val current = featureContext()
        val currentFit = activeFit()
        return if (accepted != null) accepted.context.sessionId == source.sessionId && accepted.context.datasetSha256 == source.datasetSha256 &&
            current == accepted.context && currentFit == (accepted.fitId to accepted.fitRevision)
        else current == source && currentFit == fit
    }
    fun synchronize(context: Context, fit: FitSnapshot?) {
        if (fit == null || featureContext() == null) {
            invalidate(); requested = null; details = null; options = null; selectedKey = null; return
        }
        load(context, fit)
    }
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) = load(context, fit.id, fit.revision, retry)
    fun load(context: Context, fitId: String, fitRevision: Long, retry: Boolean = false) {
        if (!screenOpen || cleared || reopenRequired) return
        val source = featureContext() ?: return
        val next = Triple(source, fitId, fitRevision)
        if (!retry && requested == next) return
        val switched = requested?.let { it.first.sessionId != source.sessionId || it.first.datasetSha256 != source.datasetSha256 || it.second != fitId } == true
        invalidate()
        if (switched) { selectedKey = null; modulePage = 0; patternPage = 0; searchText = ""; message = null }
        requested = next; details = null; options = null; loading = true; error = null
        val token = generation; val target = fitId to fitRevision; val key = selectedKey; val query = searchText; val page = patternPage
        val offset = modulePage * 25
        val pending = try { loadDetails(context.applicationContext, fitId, offset, 25) } catch (_: Exception) {
            if (owned(token, source, target, key, query, page)) { loading = false; error = "Reactive armor choices could not be loaded. Reload to try again." }; return
        }
        pending.whenCompleteAsync({ value, failure ->
            if (!owned(token, source, target, key, query, page)) return@whenCompleteAsync
            loading = false
            if (failure != null || value == null) error = "Reactive armor choices could not be verified. Reload, or restart if the engine is unavailable."
            else if (value.context != source || value.fitId != fitId || value.revision != fitRevision || value.moduleOffset != offset || value.moduleLimit != 25)
                error = "The fit changed while loading reactive armor choices. Reload its current values."
            else {
                details = value
                val selected = value.modules.find { it.objectKey == selectedKey }
                if (selected == null) selectedKey = null else loadOptions(context, value, selected)
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun chooseModule(context: Context, before: ModuleRahDetails, row: ModuleRahRow) {
        if (!available || before !== currentDetails || row !in before.modules) return
        invalidate(); options = null; patternPage = 0; searchText = ""
        selectedKey = if (selectedKey == row.objectKey) null else row.objectKey
        if (selectedKey != null) loadOptions(context, before, row)
    }
    fun search(context: Context, value: String) {
        if (!screenOpen || editing || reopenRequired || value == searchText) return
        val before = currentDetails ?: return; val row = before.modules.find { it.objectKey == selectedKey } ?: return
        invalidate(); searchText = value.take(200); patternPage = 0; options = null
        loadOptions(context, before, row)
    }
    fun showModulePage(context: Context, value: Long) {
        val before = currentDetails ?: return
        if (!available || value < 0 || value > (before.moduleTotal - 1).coerceAtLeast(0) / 25) return
        invalidate(); modulePage = value; selectedKey = null; options = null
        load(context, before.fitId, before.revision, true)
    }
    fun showPatternPage(context: Context, value: Long) {
        val before = currentDetails ?: return; val choices = currentOptions ?: return
        val row = before.modules.find { it.objectKey == selectedKey } ?: return
        if (!available || value < 0 || value > (choices.total - 1).coerceAtLeast(0) / 20) return
        invalidate(); patternPage = value; options = null; loadOptions(context, before, row)
    }
    private fun arguments(before: ModuleRahDetails, row: ModuleRahRow) = JSONObject().put("fit_revision", before.revision)
        .put("object_key", row.objectKey).put("position", row.index)
    private fun loadOptions(context: Context, before: ModuleRahDetails, row: ModuleRahRow) {
        dispatch(context, before, row, "module_options", arguments(before, row))
    }
    fun set(context: Context, before: ModuleRahDetails, row: ModuleRahRow, mode: RahMode, patternId: Int? = null) {
        if (!available || before !== currentDetails || row !in before.modules || mode == RahMode.NAMED) return
        if ((mode == RahMode.BUILTIN) != (patternId != null)) return
        if (mode == RahMode.BUILTIN && currentOptions?.entries?.none { it.id == "damage:builtin:$patternId" && it.assignable } != false) return
        if (mode == row.mode && patternId == row.patternId) return
        val selection = JSONObject().put("mode", mode.wire)
        if (patternId != null) selection.put("pattern_id", patternId)
        dispatch(context, before, row, "set_module", arguments(before, row).put("selection", selection))
    }
    fun setPattern(context: Context, before: ModuleRahDetails, row: ModuleRahRow, entry: OfflineDamageEntry) {
        if (!available || before !== currentDetails || row !in before.modules || selectedKey != row.objectKey ||
            currentOptions?.entries?.contains(entry) != true || !entry.assignable) return
        if (entry.kind == "builtin") { set(context, before, row, RahMode.BUILTIN, entry.id.substringAfterLast(':').toInt()); return }
        if (row.namedId == entry.id && row.patternRevision == entry.revision) return
        val selection = JSONObject().put("mode", "named").put("pattern_id", entry.id).put("revision", entry.revision)
        dispatch(context, before, row, "set_module", arguments(before, row).put("selection", selection))
    }
    private fun dispatch(context: Context, before: ModuleRahDetails, row: ModuleRahRow, operation: String, arguments: JSONObject) {
        if (!screenOpen || cleared || reopenRequired || before !== currentDetails) return
        invalidate(); val token = generation; val key = selectedKey; val query = searchText; val page = patternPage
        val input = OfflineDamageRequest(UUID.randomUUID().toString(), before.context, before.fitId,
            OfflineDamageView(query = query, offset = page * 20, limit = 20), operation, OfflineFeatureCodec.json(arguments))
        try { input.json() } catch (_: Exception) { error = "This selection is no longer valid. Reload current choices."; return }
        loading = damageReadLike(operation); editing = !loading; error = null; message = null
        val pending = try { request(context.applicationContext, input) } catch (_: Exception) {
            if (owned(token, before.context, before.fitId to before.revision, key, query, page)) {
                loading = false; editing = false; error = "The request could not be started. Reload to try again."
            }; return
        }
        pending.whenCompleteAsync({ result, failure ->
            // Check complete ownership before touching ANY editor flag, message, selection or error.
            if (result != null && result.requestId != input.requestId) return@whenCompleteAsync
            val accepted = result?.state?.takeIf { result.ok && !damageReadLike(operation) }
            if (!owned(token, before.context, before.fitId to before.revision, key, query, page, accepted)) return@whenCompleteAsync
            loading = false; editing = false
            if (result?.reopenRequired == true || failure != null && !damageReadLike(operation)) reopenRequired = true
            if (failure != null || result == null) error = if (damageReadLike(operation)) "Choices could not be loaded. Reload to try again."
                else "The save could not be confirmed. Restart the app before editing."
            else if (!result.ok) error = result.error?.message ?: "The reactive armor change was refused."
            else {
                val value = checkNotNull(result.state)
                if (value.context != featureContext() || (value.fitId to value.fitRevision) != activeFit() || value.module?.objectKey != row.objectKey || value.module?.index != row.index) {
                    error = "The selected module changed. Reload current choices."
                } else if (damageReadLike(operation)) options = value
                else {
                    message = if (result.committed == true) "Reactive armor selection saved. Fit incoming damage is unchanged." else "No saved values changed."
                    val current = checkNotNull(activeFit()); load(context, current.first, current.second, true)
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    override fun onCleared() { cleared = true; close() }
}

internal fun RahComponents.display() = "EM $em · Thermal $thermal · Kinetic $kinetic · Explosive $explosive (relative weights)"

@Composable
internal fun ModuleRahEditor(model: ModuleRahModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val features by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    fun leave() { model.close(); onBack() }
    DisposableEffect(model) { model.open(); onDispose { model.close() } }
    BackHandler { leave() }
    Text("Reactive armor patterns", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { leave() }, modifier = Modifier.testTag("rah-back")) { Text("Back to modules") }
    LaunchedEffect(features?.context, fit?.id, fit?.revision) { model.synchronize(context, fit) }
    if (fit == null) { Text("Open a fit to set its reactive armor pattern.", Modifier.testTag("rah-no-fit")); return }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    Text("Each local hardener can follow Fit Pattern, not adapt, or use an independent built-in or named pattern. Edit named values in the damage library.")
    if ((state as? EngineState.Ready)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE || model.reopenRequired)
        Text("The fitting engine is unavailable. Restart the app before editing.", Modifier.testTag("rah-unavailable"))
    if (model.loading) Text("Loading reactive armor choices…", Modifier.testTag("rah-loading"))
    if (model.editing) Text("Saving reactive armor pattern…", Modifier.testTag("rah-saving"))
    model.error?.let { Text(it, Modifier.testTag("rah-error"), color = MaterialTheme.colorScheme.error) }
    model.message?.let { Text(it, Modifier.testTag("rah-saved")) }
    if (!model.loading) TextButton(onClick = { model.load(context, fit, true) }, enabled = !model.editing && !model.reopenRequired,
        modifier = Modifier.testTag("rah-refresh")) { Text("Reload choices") }
    val details = model.currentDetails ?: return
    Text("Fit pattern: ${details.fitPattern.components?.display() ?: "preview unavailable (zero total)"}", Modifier.testTag("rah-fit-pattern"))
    if (details.moduleTotal == 0L) Text("No local reactive armor hardeners are fitted.", Modifier.testTag("rah-empty"))
    for (row in details.modules) key(row.objectKey) {
        Card(Modifier.fillMaxWidth().testTag("rah-module-${row.index}")) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("${row.index + 1} · ${row.name}", style = MaterialTheme.typography.titleMedium)
                Text(when (row.mode) {
                    RahMode.FIT -> "Using fit pattern"
                    RahMode.DISABLED -> "Do not adapt"
                    RahMode.BUILTIN -> "Built-in override: ${row.patternName}"
                    RahMode.NAMED -> "Named override: ${row.patternName}"
                }, Modifier.testTag("rah-mode-${row.index}"))
                if (row.mode == RahMode.DISABLED) Text("When active, the hardener keeps its base armor bonuses without adapting.")
                else Text((row.components ?: details.fitPattern.components)?.display() ?: "Fit pattern preview is unavailable.", Modifier.testTag("rah-components-${row.index}"))
                TextButton(onClick = { model.set(context, details, row, RahMode.FIT) }, enabled = model.available && row.mode != RahMode.FIT,
                    modifier = Modifier.testTag("rah-fit-${row.index}")) { Text("Use fit pattern") }
                TextButton(onClick = { model.set(context, details, row, RahMode.DISABLED) }, enabled = model.available && row.mode != RahMode.DISABLED,
                    modifier = Modifier.testTag("rah-disable-${row.index}")) { Text("Do not adapt") }
                TextButton(onClick = { model.chooseModule(context, details, row) }, enabled = model.available,
                    modifier = Modifier.testTag("rah-choose-${row.index}")) { Text(if (model.selectedKey == row.objectKey) "Hide patterns" else "Choose pattern") }
                if (model.selectedKey == row.objectKey) {
                    OutlinedTextField(value = model.searchText, onValueChange = { model.search(context, it) }, enabled = !model.editing && !model.reopenRequired, singleLine = true,
                        label = { Text("Search damage patterns") }, modifier = Modifier.fillMaxWidth().testTag("rah-search"))
                    val choices = model.currentOptions
                    if (choices != null) {
                        Text("${choices.total} matching patterns", Modifier.testTag("rah-match-count"))
                        if (choices.total == 0L) Text("No patterns match this search.", Modifier.testTag("rah-no-matches"))
                        for (entry in choices.entries) {
                            val selected = row.namedId == entry.id || row.patternId?.let { entry.id == "damage:builtin:$it" } == true
                            TextButton(onClick = { model.setPattern(context, details, row, entry) }, enabled = model.available && entry.assignable && !selected,
                                modifier = Modifier.fillMaxWidth().testTag("rah-pattern-${if (entry.kind == "builtin") entry.id.substringAfterLast(':') else entry.id}")) {
                                Text(entry.name + if (selected) " · selected" else if (!entry.assignable) " · unavailable (zero total)" else if (entry.kind == "selected_ammo") " · protected" else "")
                            }
                        }
                        if (choices.total > 20) Row {
                            TextButton(onClick = { model.showPatternPage(context, model.patternPage - 1) }, enabled = model.available && model.patternPage > 0,
                                modifier = Modifier.testTag("rah-pattern-previous")) { Text("Previous patterns") }
                            Text("Page ${model.patternPage + 1} of ${(choices.total - 1) / 20 + 1}")
                            TextButton(onClick = { model.showPatternPage(context, model.patternPage + 1) }, enabled = model.available && model.patternPage < (choices.total - 1) / 20,
                                modifier = Modifier.testTag("rah-pattern-next")) { Text("Next patterns") }
                        }
                    }
                }
            }
        }
    }
    if (details.moduleTotal > 25) Row {
        TextButton(onClick = { model.showModulePage(context, model.modulePage - 1) }, enabled = model.available && model.modulePage > 0,
            modifier = Modifier.testTag("rah-module-previous")) { Text("Previous modules") }
        Text("Page ${model.modulePage + 1} of ${(details.moduleTotal - 1) / 25 + 1}")
        TextButton(onClick = { model.showModulePage(context, model.modulePage + 1) }, enabled = model.available && model.modulePage < (details.moduleTotal - 1) / 25,
            modifier = Modifier.testTag("rah-module-next")) { Text("Next modules") }
    }
}
