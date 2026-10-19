package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.UUID
import java.util.concurrent.CompletableFuture
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.Dispatchers

private data class ShieldRegenerationMode(val x: OfflineShieldRegenerationX, val y: OfflineShieldRegenerationY, val effective: Boolean)
private data class ShieldRegenerationDraft(val low: String = "0", val high: String, val start: String = "0")

class OfflineShieldRegenerationModel(
    private val engineState: () -> EngineState = { EngineRuntime.state.value },
    private val featureContext: () -> OfflineContext? = { EngineRuntime.offlineFeatures.value?.context },
    private val library: () -> List<FitSnapshot> = { EngineRuntime.library.value },
    private val activeFitId: () -> String? = { EngineRuntime.navigation.value.activeId },
    private val read: (Context, OfflineShieldRegenerationRequest, AtomicBoolean) -> CompletableFuture<OfflineShieldRegenerationResult> = EngineRuntime::offlineShieldRegeneration,
) : ViewModel() {
    private var mode by mutableStateOf(ShieldRegenerationMode(OfflineShieldRegenerationX.TIME, OfflineShieldRegenerationY.AMOUNT, false))
    private val drafts = mutableStateMapOf<ShieldRegenerationMode, ShieldRegenerationDraft>()
    private val draft get() = drafts[mode] ?: ShieldRegenerationDraft(high = if (x == OfflineShieldRegenerationX.TIME) "300" else "100")
    val x get() = mode.x
    val y get() = mode.y
    val effective get() = mode.effective
    val low get() = draft.low
    val high get() = draft.high
    val startingShield get() = draft.start
    var selected by mutableStateOf<Set<String>>(emptySet()); private set
    var query by mutableStateOf(""); private set
    var page by mutableStateOf(0); private set
    var result by mutableStateOf<OfflineShieldRegenerationResult?>(null); private set
    var busy by mutableStateOf(false); private set
    var cancelling by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    private data class Worker(val token: Long, val cancellation: AtomicBoolean)
    private var worker: Worker? = null
    private var generation = 0L
    private var initializedSelection = false
    private var lastContext: OfflineContext? = null
    private var lastRevisions: Map<String, Long> = emptyMap()
    private fun available(): Boolean = when (val engine = engineState()) {
        is EngineState.Ready -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        is EngineState.Empty -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        else -> false
    }
    val canPlot get() = !busy && available() && featureContext() != null && selected.isNotEmpty() &&
        library().map { it.id }.containsAll(selected)
    val currentResult get() = result?.takeIf { isCurrent(it.request) }

    fun synchronize(context: OfflineContext?, fits: List<FitSnapshot>) {
        val revisions = fits.associate { it.id to it.revision }
        if (context != lastContext || selected.any { lastRevisions[it] != revisions[it] } || !available()) {
            if (busy || result != null) { cancel(); error = "Fits or profiles changed. Plot again to use their current values." }
        }
        lastContext = context; lastRevisions = revisions
        if (!revisions.keys.containsAll(selected)) {
            cancel(); selected = selected.intersect(revisions.keys)
            error = "A selected fit was removed. Review the selection and plot again."
        }
        if (!initializedSelection && fits.isNotEmpty()) {
            selected = setOf(activeFitId()?.takeIf { it in revisions } ?: fits.first().id)
            initializedSelection = true
        }
    }
    fun select(id: String) {
        if (id !in selected && (selected.size >= 8 || library().none { it.id == id })) return
        change(); initializedSelection = true
        selected = if (id in selected) selected - id else selected + id
    }
    fun search(value: String) { if (value != query) { query = value; page = 0 } }
    fun fitPage(value: Int) {
        val count = library().count { it.name.contains(query, ignoreCase = true) }
        page = value.coerceIn(0, (count - 1).coerceAtLeast(0) / 30)
    }
    fun xAxis(value: OfflineShieldRegenerationX) { if (value != x) { change(); mode = mode.copy(x = value) } }
    fun yAxis(value: OfflineShieldRegenerationY) { if (value != y) { change(); mode = mode.copy(y = value) } }
    fun effective(value: Boolean) { if (value != effective) { change(); mode = mode.copy(effective = value) } }
    fun rangeLow(value: String) { if (value != low) { change(); drafts[mode] = draft.copy(low = value) } }
    fun rangeHigh(value: String) { if (value != high) { change(); drafts[mode] = draft.copy(high = value) } }
    fun startingShield(value: String) { if (value != startingShield) { change(); drafts[mode] = draft.copy(start = value) } }
    private fun change() { cancel(); error = null }
    // Cancellation changes publication eligibility, never releases an unfinished engine call.
    fun cancel() { generation++; worker?.cancellation?.set(true); result = null; if (busy) cancelling = true }
    fun stop() { cancel(); error = "Sampling cancelled. The current engine call may still be finishing." }
    private fun isCurrent(request: OfflineShieldRegenerationRequest): Boolean = available() && featureContext() == request.context &&
        request.fits.all { (id, revision) -> library().any { it.id == id && it.revision == revision } }
    private fun release(owner: Worker): Boolean {
        if (worker !== owner) return false
        worker = null; busy = false; cancelling = false
        return true
    }

    fun plot(context: Context) {
        if (busy) return
        if (!available()) { error = "The fitting engine is unavailable. Restart the app before plotting."; return }
        val sourceContext = featureContext() ?: run { error = "Offline fitting inputs are not ready yet."; return }
        val fits = OfflineFeatureCodec.frozen(library().filter { it.id in selected }.associate { it.id to it.revision })
        val request = try {
            require(fits.keys == selected)
            val start = if (x == OfflineShieldRegenerationX.TIME && startingShield.isNotBlank()) startingShield.toDouble() else null
            OfflineShieldRegenerationRequest(UUID.randomUUID().toString(), sourceContext, fits, x, y, effective,
                low.toDouble(), high.toDouble(), start).also { it.json() }
        } catch (_: Exception) {
            error = "Select 1–8 fits and enter finite range values. A time-mode starting percentage may be blank; other nonnumeric text is invalid."
            return
        }
        cancel()
        val owner = Worker(generation, AtomicBoolean(false))
        worker = owner; busy = true; cancelling = false; error = null
        val appContext = context.applicationContext
        val pending = try { read(appContext, request, owner.cancellation) } catch (_: Exception) {
            if (release(owner) && owner.token == generation)
                error = "Shield regeneration samples could not be started. Check whether the fitting engine needs a restart."
            return
        }
        pending.whenCompleteAsync({ value, failure ->
            if (release(owner) && owner.token == generation) {
                if (failure != null || value == null) error = "Shield regeneration samples could not be verified. Check whether the fitting engine needs a restart."
                else if (!value.ok) error = value.error?.message ?: "Shield regeneration sampling failed."
                else if (!isCurrent(request)) error = "Fit inputs changed while plotting. Plot again."
                else result = value
            }
        }, ContextCompat.getMainExecutor(appContext))
    }
    override fun onCleared() { cancel() }
}

@Composable
private fun ShieldGraphChoice(label: String, selected: Boolean, tag: String, change: () -> Unit) {
    Row(Modifier.fillMaxWidth().selectable(selected, role = Role.RadioButton, onClick = change).testTag(tag)) {
        RadioButton(selected = selected, onClick = null)
        Text(label)
    }
}

@Composable
internal fun OfflineShieldRegenerationView(model: OfflineShieldRegenerationModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val feature by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val fits by EngineRuntime.library.collectAsState(context = Dispatchers.Main)
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    LaunchedEffect(feature?.context, fits.map { it.id to it.revision }, engine) { model.synchronize(feature?.context, fits) }
    DisposableEffect(model) { onDispose { model.cancel() } }
    BackHandler { model.cancel(); onBack() }
    Text("Shield regeneration comparison", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { model.cancel(); onBack() }, modifier = Modifier.testTag("shield-graph-back")) { Text("Back") }
    Text("Up to 8 fits · original fixed sampling, 200 intervals · cooperative 10-second work budget. A running engine call must finish before another plot can start.")
    Text("Passive shield regeneration using current fit attributes. Effective values use each fit's current incoming damage contributions and shield resistances.",
        Modifier.testTag("shield-graph-explanation"))
    OutlinedTextField(value = model.query, onValueChange = model::search, label = { Text("Search fits") },
        modifier = Modifier.fillMaxWidth().testTag("shield-graph-search"))
    val matches = fits.filter { it.name.contains(model.query, ignoreCase = true) }
    val lastPage = (matches.size - 1).coerceAtLeast(0) / 30
    val page = model.page.coerceIn(0, lastPage)
    Text("${model.selected.size} selected · ${matches.size} matching fits · page ${page + 1} of ${lastPage + 1}", Modifier.testTag("shield-graph-page"))
    if (fits.isEmpty()) Text("Create or import a fit to compare shield regeneration.", Modifier.testTag("shield-graph-no-fits"))
    else if (matches.isEmpty()) Text("No fits match this search. Selected fits remain selected.", Modifier.testTag("shield-graph-no-matches"))
    for (fit in matches.drop(page * 30).take(30)) {
        val checked = fit.id in model.selected; val enabled = checked || model.selected.size < 8
        Row(Modifier.fillMaxWidth().toggleable(checked, enabled = enabled, role = Role.Checkbox, onValueChange = { model.select(fit.id) })
            .testTag("shield-graph-fit-${fit.id}")) {
            Checkbox(checked = checked, onCheckedChange = null, enabled = enabled)
            Text(fit.name)
        }
    }
    if (lastPage > 0) Row {
        TextButton(onClick = { model.fitPage(page - 1) }, enabled = page > 0, modifier = Modifier.testTag("shield-graph-previous")) { Text("Previous fits") }
        TextButton(onClick = { model.fitPage(page + 1) }, enabled = page < lastPage, modifier = Modifier.testTag("shield-graph-next")) { Text("Next fits") }
    }
    if (model.selected.isEmpty() && fits.isNotEmpty()) Text("Select at least one fit to plot.", Modifier.testTag("shield-graph-no-selection"))
    Row(Modifier.fillMaxWidth().toggleable(model.effective, role = Role.Checkbox, onValueChange = model::effective).testTag("shield-graph-effective")) {
        Checkbox(checked = model.effective, onCheckedChange = null); Text("Effective HP (EHP), using each fit's incoming damage")
    }
    Text("X axis", style = MaterialTheme.typography.titleMedium)
    ShieldGraphChoice("Time (s)", model.x == OfflineShieldRegenerationX.TIME, "shield-graph-x-time") { model.xAxis(OfflineShieldRegenerationX.TIME) }
    ShieldGraphChoice("Shield amount (${OfflineShieldRegenerationX.AMOUNT.unit(model.effective)})", model.x == OfflineShieldRegenerationX.AMOUNT,
        "shield-graph-x-amount") { model.xAxis(OfflineShieldRegenerationX.AMOUNT) }
    ShieldGraphChoice("Shield amount (%)", model.x == OfflineShieldRegenerationX.PERCENT, "shield-graph-x-percent") { model.xAxis(OfflineShieldRegenerationX.PERCENT) }
    Text("Y axis", style = MaterialTheme.typography.titleMedium)
    ShieldGraphChoice("Shield amount (${OfflineShieldRegenerationY.AMOUNT.unit(model.effective)})", model.y == OfflineShieldRegenerationY.AMOUNT,
        "shield-graph-y-amount") { model.yAxis(OfflineShieldRegenerationY.AMOUNT) }
    ShieldGraphChoice("Regeneration rate (${OfflineShieldRegenerationY.RATE.unit(model.effective)})", model.y == OfflineShieldRegenerationY.RATE,
        "shield-graph-y-rate") { model.yAxis(OfflineShieldRegenerationY.RATE) }
    val inputLabel = if (model.x == OfflineShieldRegenerationX.TIME) "Time" else "Shield"
    val inputUnit = model.x.inputUnit
    OutlinedTextField(value = model.low, onValueChange = model::rangeLow, label = { Text("$inputLabel range start ($inputUnit)") },
        singleLine = true, modifier = Modifier.fillMaxWidth().testTag("shield-graph-low"))
    OutlinedTextField(value = model.high, onValueChange = model::rangeHigh, label = { Text("$inputLabel range end ($inputUnit)") },
        singleLine = true, modifier = Modifier.fillMaxWidth().testTag("shield-graph-high"))
    if (model.x == OfflineShieldRegenerationX.TIME) {
        OutlinedTextField(value = model.startingShield, onValueChange = model::startingShield, label = { Text("Starting shield (%) · blank uses 0") },
            singleLine = true, modifier = Modifier.fillMaxWidth().testTag("shield-graph-start"))
    } else Text("Range inputs are percentages of each fit's shield capacity. The X axis is shown in ${model.x.unit(model.effective)}; its actual bounds can differ between fits.",
        Modifier.testTag("shield-graph-input-explanation"))
    Text("Endpoints may be reversed. Shield percentages are clamped by the original engine; signed time is accepted and may produce above-capacity shield or negative rates.")
    Row {
        Button(onClick = { model.plot(context) }, enabled = model.canPlot, modifier = Modifier.testTag("shield-graph-plot")) { Text("Plot") }
        if (model.busy) TextButton(onClick = { model.stop() }, enabled = !model.cancelling, modifier = Modifier.testTag("shield-graph-cancel")) { Text("Cancel") }
    }
    if (model.busy) Text(if (model.cancelling) "Finishing cancelled sampling…" else "Sampling shield regeneration…", Modifier.testTag("shield-graph-busy"))
    val unavailable = engine is EngineState.Failed || (engine as? EngineState.Ready)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ||
        (engine as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE
    if (unavailable) Text("The fitting engine is unavailable. Restart the app before plotting.", Modifier.testTag("shield-graph-unavailable"))
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("shield-graph-error")) }
    val result = model.currentResult
    if (result == null && !model.busy && model.error == null && model.selected.isNotEmpty())
        Text("Plot to calculate the selected fits with these inputs.", Modifier.testTag("shield-graph-not-plotted"))
    result?.let {
        val xs = it.series.flatMap { series -> series.x }
        val xUnit = it.request.x.unit(it.request.effective); val yUnit = it.request.y.unit(it.request.effective)
        OfflineSamplePlot(it.series.map { series -> OfflinePlotSeries(fits.find { fit -> fit.id == series.fitId }?.name ?: series.fitId, series.x, series.y) },
            xs.minOrNull() ?: 0.0, xs.maxOrNull() ?: 0.0, xUnit, yUnit, "shield-graph", "No shield regeneration samples in this range.")
        if (it.series.all { series -> series.y.all { value -> value == 0.0 } })
            Text("Zero at every sampled point with these inputs.", Modifier.testTag("shield-graph-zero"))
        Text("Source capacity is always raw HP. Source recharge is seconds to regenerate from 0% to 98.7%; these are source attributes, separate from the sampled curve.",
            Modifier.testTag("shield-graph-source-explanation"))
        it.series.forEachIndexed { index, series ->
            val name = fits.find { fit -> fit.id == series.fitId }?.name ?: series.fitId
            Text("${index + 1}. $name · ${series.x.size} points", Modifier.testTag("shield-graph-series-${series.fitId}"))
            Text("Source shield capacity: ${series.source.shieldCapacityHp} HP", Modifier.testTag("shield-graph-source-capacity-${series.fitId}"))
            Text("Source shield recharge: ${series.source.shieldRechargeSeconds} s", Modifier.testTag("shield-graph-source-recharge-${series.fitId}"))
            if (it.request.effective) {
                Text("Incoming damage contributions for this curve (relative amounts):")
                DAMAGE_TYPES.forEach { (key, label) -> Text("$label: ${series.source.damagePattern.getValue(key)}",
                    Modifier.testTag("shield-graph-source-$key-${series.fitId}")) }
            }
            Text("Sampled ${series.x.first()}–${series.x.last()} $xUnit · curve: ${series.y.minOrNull()}–${series.y.maxOrNull()} $yUnit")
        }
    }
}
