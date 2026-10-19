package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.concurrent.CompletableFuture
import kotlinx.coroutines.Dispatchers
import org.json.JSONObject

enum class PilotSecurityChoice { CHARACTER, PRESET, CUSTOM }

/** One physical operation remains owned across Close/Back. A new screen can queue, never steal it. */
class PilotSecurityModel(
    private val published: () -> OfflineFeatureState? = { EngineRuntime.offlineFeatures.value },
    private val activeFit: () -> FitSnapshot? = { (EngineRuntime.state.value as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit },
    private val read: (Context, String) -> CompletableFuture<PilotSecurityDetails> = EngineRuntime::pilotSecurityDetails,
    private val mutate: (Context, OfflineContext, String, JSONObject, String?) -> CompletableFuture<OfflineFeatureResponse> =
        { context, expected, operation, arguments, anchor -> EngineRuntime.offlineFeatureRequest(context, expected, operation, arguments, anchor) },
) : ViewModel() {
    var details by mutableStateOf<PilotSecurityDetails?>(null); private set
    var loading by mutableStateOf(false); private set
    var saving by mutableStateOf(false); private set
    var reopenRequired by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var choice by mutableStateOf(PilotSecurityChoice.CHARACTER); private set
    var preset by mutableStateOf(0); private set
    var text by mutableStateOf(""); private set
    var dirty by mutableStateOf(false); private set
    var conflict by mutableStateOf(false); private set
    private var draftOwner: PilotSecurityOwner? = null
    private var screen: Any? = null
    private var work: Any? = null
    private var requested: PilotSecurityOwner? = null
    private var refreshPending = false
    private var cleared = false
    private var blockedSession: String? = null
    private fun capture(): PilotSecurityOwner? {
        val state = published() ?: return null; val fit = activeFit() ?: return null
        return try { PilotSecurityOwner.capture(state, fit) } catch (_: Exception) { null }
    }
    val currentDetails get() = details?.takeIf { value -> screen != null && capture()?.let { owner ->
        try { owner.validate(value); true } catch (_: Exception) { false }
    } == true }
    val available get() = !cleared && screen != null && work == null && !reopenRequired &&
        !conflict && currentDetails?.eligible == true && draftOwner == capture()
    val input: SecurityNumber? get() = when (choice) {
        PilotSecurityChoice.CHARACTER -> null
        PilotSecurityChoice.PRESET -> SecurityNumber(preset)
        PilotSecurityChoice.CUSTOM -> PilotSecurityCodec.entry(text)
    }
    val inputValid get() = choice != PilotSecurityChoice.CUSTOM || PilotSecurityCodec.entry(text) != null
    fun open() { if (!cleared && screen == null) { screen = Any(); requested = null; message = null; error = null } }
    fun close() {
        screen = null; requested = null; refreshPending = false; details = null; message = null; error = null
        // work, saving and draft authority deliberately survive dismissal.
    }
    fun load(context: Context, retry: Boolean = false) {
        if (cleared || screen == null) return
        val next = capture()
        if (blockedSession != null && published()?.context?.sessionId?.let { it != blockedSession } == true) { reopenRequired = false; blockedSession = null }
        if (next == null) { details = null; if (dirty) conflict = true; return }
        if (!retry && requested == next) return
        requested = next; refreshPending = true
        if (dirty && draftOwner != next) conflict = true
        if (work == null) readLatest(context)
    }
    private fun readLatest(context: Context) {
        if (screen == null || cleared || work != null || reopenRequired || !refreshPending) return
        val expected = capture() ?: return; val view = screen; val token = Any(); work = token
        refreshPending = false; loading = true; error = null
        val pending = try { read(context.applicationContext, expected.fitId) } catch (_: Exception) {
            work = null; loading = false; error = "Pilot security could not be loaded. Reload the saved values."; return
        }
        pending.whenCompleteAsync({ value, failure ->
            if (work !== token || cleared) return@whenCompleteAsync
            work = null; loading = false
            if (screen === view && capture() == expected) {
                if (failure != null || value == null) error = "Pilot security could not be verified. Reload, or restart if the engine is unavailable."
                else try {
                    expected.validate(value); details = value
                    if (!dirty) resetDraft(expected, value) else conflict = draftOwner != expected
                } catch (_: Exception) { error = "The fit or character changed. Reload and review the saved values." }
            } else if (screen != null) refreshPending = true
            if (refreshPending) readLatest(context)
        }, ContextCompat.getMainExecutor(context))
    }
    private fun resetDraft(owner: PilotSecurityOwner, value: PilotSecurityDetails) {
        draftOwner = owner; dirty = false; conflict = false
        val raw = value.pilot
        choice = when {
            raw == null -> PilotSecurityChoice.CHARACTER
            raw.raw is Int && raw.raw in value.presets -> PilotSecurityChoice.PRESET
            raw.raw is Long && raw.raw.toInt() in value.presets -> PilotSecurityChoice.PRESET
            else -> PilotSecurityChoice.CUSTOM
        }
        preset = if (choice == PilotSecurityChoice.PRESET) checkNotNull(raw).raw.toInt() else 0
        text = if (choice == PilotSecurityChoice.CUSTOM) raw.toString() else ""
    }
    fun choose(value: PilotSecurityChoice, presetValue: Int = preset) {
        if (!available || value == PilotSecurityChoice.PRESET && presetValue !in PilotSecurityCodec.presets) return
        choice = value; preset = presetValue; dirty = true; message = null
    }
    fun edit(value: String) { if (available) { choice = PilotSecurityChoice.CUSTOM; text = value; dirty = true; message = null } }
    fun revert() {
        if (work != null) return
        val value = currentDetails; val current = capture()
        if (value != null && current != null) resetDraft(current, value)
        else { dirty = false; conflict = false; draftOwner = null; text = "" }
        error = null
    }
    fun save(context: Context) {
        val before = currentDetails ?: return; val expected = draftOwner ?: return
        if (!available || !dirty || !inputValid) return
        val args = JSONObject().put("fit_id", expected.fitId).put("fit_revision", expected.fitRevision)
            .put("pilot", input?.raw ?: JSONObject.NULL)
        val view = screen; val token = Any(); work = token; saving = true; error = null; message = null
        val pending = try { mutate(context.applicationContext, expected.context, "set_pilot_security", args, expected.fitId) }
        catch (_: Exception) { work = null; saving = false; error = "The request could not be started. Your draft is unchanged."; return }
        pending.whenCompleteAsync({ result, failure ->
            if (work !== token || cleared) return@whenCompleteAsync
            work = null; saving = false
            val sameSession = published()?.context?.let { it.sessionId == expected.context.sessionId && it.datasetSha256 == expected.context.datasetSha256 } == true
            val uncertain = failure != null || result == null || result.reopenRequired || result.committed == null
            if (uncertain && sameSession) { reopenRequired = true; blockedSession = expected.context.sessionId }
            if (screen === view && sameSession && draftOwner == expected) {
                if (uncertain) error = "The save could not be confirmed. Your draft is kept. Restart before editing."
                else if (!result!!.ok) {
                    error = result.error?.message ?: "The change was refused. Your draft is kept."
                    if (result.error?.code in setOf("stale_context", "conflict", "profile_mismatch")) conflict = true
                } else if (result.state?.context == published()?.context && result.state?.selectedFitId == expected.fitId && activeFit()?.id == before.fitId) {
                    dirty = false; conflict = false; draftOwner = null; details = null
                    message = if (result.committed == true) "Pilot security saved. Undo is available." else "Already selected. Saved raw input is unchanged."
                    refreshPending = true
                } else { conflict = true; refreshPending = true }
            } else if (screen != null) refreshPending = true
            if (refreshPending && !reopenRequired) readLatest(context)
        }, ContextCompat.getMainExecutor(context))
    }
    override fun onCleared() { cleared = true; screen = null; super.onCleared() }
}

@Composable
internal fun PilotSecurityEditor(model: PilotSecurityModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val published by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    DisposableEffect(model) { model.open(); onDispose { model.close() } }
    LaunchedEffect(fit?.id, fit?.revision, published?.context) { model.load(context) }
    fun leave() { model.close(); onBack() }
    BackHandler { leave() }
    Text("Pilot security", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { leave() }, modifier = Modifier.testTag("pilot-security-back")) { Text("Back") }
    if (fit == null) { Text("Open a saved fit to view pilot security.", Modifier.testTag("pilot-security-no-fit")); return }
    Text("${fit.name} · ${fit.ship}")
    if (model.loading) Text("Loading pilot security…", Modifier.testTag("pilot-security-loading"))
    if (model.saving) Text("Saving and recalculating…", Modifier.testTag("pilot-security-saving"))
    model.error?.let { Text(it, Modifier.testTag("pilot-security-error"), color = MaterialTheme.colorScheme.error) }
    model.message?.let { Text(it, Modifier.testTag("pilot-security-message")) }
    TextButton(onClick = { model.load(context, true) }, enabled = !model.saving && !model.loading && !model.reopenRequired,
        modifier = Modifier.testTag("pilot-security-reload")) { Text("Reload saved values") }
    if (model.dirty) Text("Unsaved draft is kept while the app remains open. Revert before changing its owner.", Modifier.testTag("pilot-security-dirty"))
    if (model.conflict) Text("This draft belongs to an older fit or character state. Review the saved values and revert before editing.", Modifier.testTag("pilot-security-conflict"))
    val details = model.currentDetails
    if (details != null) {
        Text("Character: ${details.profile.name} · ${details.profile.secStatus}", Modifier.testTag("pilot-security-profile"))
        Text("Saved source: ${if (details.source == PilotSecuritySource.CHARACTER) "Character" else "Explicit ${details.pilot}"} · Effective: ${details.effective}", Modifier.testTag("pilot-security-current"))
        if (!details.eligible) Text("Pilot security editing is available only for Pacifier, Enforcer, Marshal, Sidewinder, Cobra and Python.", Modifier.testTag("pilot-security-unsupported"))
        else {
            TextButton(onClick = { model.choose(PilotSecurityChoice.CHARACTER) }, enabled = model.available,
                modifier = Modifier.testTag("pilot-security-character")) { Text("Character${if (model.choice == PilotSecurityChoice.CHARACTER) " ✓" else ""}") }
            for (chunk in details.presets.chunked(4)) Row {
                for (number in chunk) TextButton(onClick = { model.choose(PilotSecurityChoice.PRESET, number) }, enabled = model.available,
                    modifier = Modifier.testTag("pilot-security-preset-$number")) { Text("$number${if (model.choice == PilotSecurityChoice.PRESET && model.preset == number) " ✓" else ""}") }
            }
            TextButton(onClick = { model.choose(PilotSecurityChoice.CUSTOM) }, enabled = model.available,
                modifier = Modifier.testTag("pilot-security-custom")) { Text("Custom${if (model.choice == PilotSecurityChoice.CUSTOM) " ✓" else ""}") }
            OutlinedTextField(model.text, model::edit, label = { Text("Custom security (-10 to 5)") }, enabled = model.available,
                singleLine = true, isError = model.choice == PilotSecurityChoice.CUSTOM && !model.inputValid,
                modifier = Modifier.fillMaxWidth().testTag("pilot-security-input"))
            Button(onClick = { model.save(context) }, enabled = model.available && model.dirty && model.inputValid,
                modifier = Modifier.testTag("pilot-security-save")) { Text("Save pilot security") }
        }
    }
    TextButton(onClick = model::revert, enabled = !model.saving && !model.loading && model.dirty,
        modifier = Modifier.testTag("pilot-security-revert")) { Text("Revert draft") }
}
