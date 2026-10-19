package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

data class DefenseScalar(val value: StatValue, val unit: String, val display: String?, val detail: String?)
data class DefenseLayer(val hp: DefenseScalar, val ehp: DefenseScalar, val multiplier: DefenseScalar, val resistances: Map<String, DefenseScalar>)
data class IncomingContribution(val amount: Double, val percentage: Double, val display: String)
data class FitDefenses(val fitId: String, val revision: Long, val layers: Map<String, DefenseLayer>,
    val hp: DefenseScalar, val ehp: DefenseScalar, val pattern: Map<String, IncomingContribution>)
internal val DEFENSE_LAYERS = linkedMapOf("shield" to "Shield", "armor" to "Armor", "hull" to "Hull")
internal val DAMAGE_TYPES = linkedMapOf("em" to "EM", "thermal" to "Thermal", "kinetic" to "Kinetic", "explosive" to "Explosive")

class IncomingDraft(val fitId: String) {
    val text = mutableStateMapOf<String, String>()
    private var saved = emptyMap<String, Double>()
    var revision by mutableStateOf(0L); private set
    var conflict by mutableStateOf(false); private set
    var saving by mutableStateOf(false); internal set
    var error by mutableStateOf<String?>(null); internal set
    val dirty get() = DAMAGE_TYPES.keys.any { text[it]?.toDoubleOrNull() != saved[it] }
    fun load(value: FitDefenses, discard: Boolean = false) {
        if (revision == value.revision && !discard) return
        if (revision != 0L && dirty && !discard) { conflict = true; return }
        saved = value.pattern.mapValues { it.value.amount }
        text.clear(); saved.forEach { (key, amount) -> text[key] = amount.toString() }
        revision = value.revision; conflict = false; error = null
    }
    fun values(): List<Double>? {
        val values = DAMAGE_TYPES.keys.map { text[it]?.toDoubleOrNull() ?: return null }
        return values.takeIf { it.all { amount -> amount.isFinite() && amount >= 0 } && it.sum().let { sum -> sum.isFinite() && sum > 0 } }
    }
    fun accepted(values: List<Double>, nextRevision: Long) {
        saved = DAMAGE_TYPES.keys.zip(values).toMap(); revision = nextRevision; conflict = false
    }
}

class DefenseModel : ViewModel() {
    var details by mutableStateOf<FitDefenses?>(null); private set
    var loading by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    val drafts = mutableStateMapOf<String, IncomingDraft>()
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        requested = next; details = null; error = null; loading = true
        val token = ++generation
        EngineRuntime.defenseDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Defenses could not be loaded. Try again."
                else { details = value; drafts.getOrPut(fit.id) { IncomingDraft(fit.id) }.load(value) }
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun apply(context: Context, fit: FitSnapshot, draft: IncomingDraft) {
        if (draft.saving || draft.conflict || draft.fitId != fit.id) return
        if (draft.revision != fit.revision) { draft.error = "The fit changed. Reload its saved contributions."; return }
        val values = draft.values() ?: run { draft.error = "Use nonnegative numbers with a positive finite total."; return }
        if (!draft.dirty) return
        draft.saving = true; draft.error = null
        EngineRuntime.request(context, BridgeOperation.SetDamagePattern(fit.id, DamagePattern(values[0], values[1], values[2], values[3])),
            mapOf(fit.id to draft.revision)).whenCompleteAsync({ response, failure ->
            draft.saving = false
            if (failure != null) draft.error = "The save could not be confirmed. Your draft is kept."
            else if (!response.isSuccess) draft.error = response.error?.message ?: "The save failed. Your draft is kept."
            else {
                draft.accepted(values, response.fits.single { it.id == fit.id }.revision)
                if (requested?.first == fit.id) load(context, response.fits.single { it.id == fit.id }, true)
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
private fun DefenseValue(name: String, label: String, value: DefenseScalar, fitId: String) {
    var expanded by rememberSaveable(fitId, name) { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().padding(8.dp).testTag("defense-row-$name")) {
        Text(label, style = MaterialTheme.typography.titleMedium)
        Text(value.display?.let { "$it ${value.unit}" } ?: "Unavailable", Modifier.testTag("defense-value-$name"))
        TextButton(onClick = { expanded = !expanded }, modifier = Modifier.testTag("defense-details-$name")) { Text(if (expanded) "Hide details" else "Details") }
        if (expanded) {
            Text(value.detail?.let { "$it ${value.unit}" } ?: "Unavailable", Modifier.testTag("defense-detail-$name"))
            Text("Full precision: ${if (value.value == StatValue.Unavailable) "Unavailable" else value.value.raw} ${value.unit}", Modifier.testTag("defense-raw-$name"))
        }
    }
}

@Composable
internal fun DefenseView(model: DefenseModel, patterns: OfflineDamagePatternsModel, onBack: () -> Unit, onNamedPatterns: () -> Unit) {
    val context = LocalContext.current
    DisposableEffect(patterns) { patterns.open(); onDispose { patterns.close() } }
    val focus = LocalFocusManager.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    val features by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    var leaveDestination by rememberSaveable { mutableStateOf<String?>(null) }
    val currentDraft = fit?.let { model.drafts[it.id] }
    fun leave(destination: String) {
        if (currentDraft?.saving == true || patterns.saving) return
        if (currentDraft?.dirty == true) leaveDestination = destination
        else { patterns.close(); if (destination == "patterns") onNamedPatterns() else onBack() }
    }
    BackHandler { leave("back") }
    if (leaveDestination != null) AlertDialog(onDismissRequest = { leaveDestination = null },
        title = { Text("Keep unsaved incoming damage?") },
        text = { Text("Your contribution draft will remain here while the app stays open. It has not been applied.") },
        confirmButton = { TextButton(onClick = {
            val destination = leaveDestination; leaveDestination = null
            patterns.close(); if (destination == "patterns") onNamedPatterns() else onBack()
        }, modifier = Modifier.testTag("defense-leave-keep")) { Text("Keep draft and continue") } },
        dismissButton = { TextButton(onClick = { leaveDestination = null }) { Text("Stay") } })
    Text("Defenses", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { leave("back") }, enabled = currentDraft?.saving != true && !patterns.saving, modifier = Modifier.testTag("defense-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to view its defenses."); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    LaunchedEffect(features?.context, fit.id, fit.revision) { patterns.synchronize(context, features?.context, fit.id, fit.revision) }
    TextButton(onClick = { leave("patterns") }, enabled = currentDraft?.saving != true && !patterns.saving,
        modifier = Modifier.testTag("defense-named-patterns")) { Text("Choose or manage named patterns") }
    val savedPattern = patterns.state?.takeIf { it.context == features?.context && it.fitId == fit.id && it.fitRevision == fit.revision }
    Text(when (savedPattern?.selection?.kind) {
        "named" -> "Incoming pattern: " + (savedPattern.selection.patternId?.let { id ->
            savedPattern.entries.find { it.id == id }?.name ?: savedPattern.detail?.entry?.takeIf { it.id == id }?.name ?: id
        })
        "anonymous" -> "Incoming pattern: Anonymous"
        else -> "Loading saved pattern identity…"
    }, Modifier.testTag("defense-pattern-identity"))
    patterns.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("defense-pattern-error")) }
    patterns.message?.let { Text(it, Modifier.testTag("defense-pattern-message")) }
    if (patterns.reopenRequired) Text("Restart the app to check saved changes before editing again.", color = MaterialTheme.colorScheme.error)
    if (savedPattern?.selection?.kind == "named") TextButton(onClick = { patterns.detach(context) },
        enabled = patterns.available && currentDraft?.saving != true,
        modifier = Modifier.testTag("defense-detach-anonymous")) { Text("Detach to Anonymous (keep saved contributions)") }
    TextButton(onClick = { patterns.resetUniform(context) }, enabled = patterns.available && currentDraft?.saving != true &&
        savedPattern != null && savedPattern.selection.patternId != "damage:builtin:-1",
        modifier = Modifier.testTag("defense-reset-uniform")) { Text("Reset to Uniform") }

    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    if (model.loading) Text("Loading defenses…", Modifier.testTag("defense-loading"))
    model.error?.let {
        Text(it, Modifier.testTag("defense-error"), color = MaterialTheme.colorScheme.error)
        TextButton(onClick = { model.load(context, fit, true) }, modifier = Modifier.testTag("defense-retry")) { Text("Try again") }
    }
    val details = model.details?.takeIf { it.fitId == fit.id && it.revision == fit.revision } ?: return
    var effective by rememberSaveable(fit.id) { mutableStateOf(true) }
    TextButton(onClick = { effective = !effective }, modifier = Modifier.testTag("defense-toggle")) { Text(if (effective) "Show raw HP" else "Show effective HP") }
    DefenseValue("total", if (effective) "Total effective HP" else "Total raw HP", if (effective) details.ehp else details.hp, fit.id)
    val draft = model.drafts.getValue(fit.id)
    Text("Incoming damage", style = MaterialTheme.typography.titleLarge)
    Text("Relative contributions; percentages are calculated by Pyfa.")
    for ((name, label) in DAMAGE_TYPES) {
        OutlinedTextField(value = draft.text[name] ?: "", onValueChange = { draft.text[name] = it }, enabled = !draft.saving && !patterns.saving,
            label = { Text("$label contribution") }, supportingText = { Text("Saved: ${details.pattern.getValue(name).display}%", Modifier.testTag("defense-percent-$name")) },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.fillMaxWidth().testTag("defense-input-$name"))
    }
    if (draft.dirty) Text("Unsaved incoming contribution draft. Named-pattern actions do not apply these fields.", Modifier.testTag("defense-dirty"))
    if (draft.conflict) Text("The fit changed. Your draft is kept; reload saved contributions before editing.", Modifier.testTag("defense-conflict"))
    if (draft.dirty && draft.values() == null) Text("Use nonnegative numbers with a positive finite total.", Modifier.testTag("defense-validation"))
    draft.error?.let { Text(it, Modifier.testTag("defense-edit-error"), color = MaterialTheme.colorScheme.error) }
    Button(onClick = { focus.clearFocus(); model.apply(context, fit, draft) }, enabled = patterns.available && draft.dirty && !draft.conflict && !draft.saving && draft.values() != null,
        modifier = Modifier.testTag("defense-apply")) { Text(if (draft.saving) "Saving…" else "Apply as Anonymous incoming damage") }
    TextButton(onClick = { draft.load(details, true) }, enabled = !draft.saving && !patterns.saving,
        modifier = Modifier.testTag("defense-reset")) { Text("Reload saved contributions") }
    for ((name, label) in DEFENSE_LAYERS) {
        val layer = details.layers.getValue(name)
        Card(Modifier.fillMaxWidth().testTag("defense-layer-$name")) {
            Column(Modifier.padding(12.dp)) {
                Text(label, style = MaterialTheme.typography.titleLarge)
                DefenseValue("$name-hp", if (effective) "Effective HP" else "Raw HP", if (effective) layer.ehp else layer.hp, fit.id)
                DefenseValue("$name-multiplier", "Resistance multiplier", layer.multiplier, fit.id)
                for ((kind, damage) in DAMAGE_TYPES) DefenseValue("$name-$kind", "$damage resistance", layer.resistances.getValue(kind), fit.id)
            }
        }
    }
}
