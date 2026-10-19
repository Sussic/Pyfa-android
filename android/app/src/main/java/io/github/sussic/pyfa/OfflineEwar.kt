package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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

class OfflineEwarModel(
    private val engineState: () -> EngineState = { EngineRuntime.state.value },
    private val featureContext: () -> OfflineContext? = { EngineRuntime.offlineFeatures.value?.context },
    private val library: () -> List<FitSnapshot> = { EngineRuntime.library.value },
    private val activeFitId: () -> String? = { EngineRuntime.navigation.value.activeId },
    private val read: (Context, OfflineEwarRequest, AtomicBoolean) -> CompletableFuture<OfflineEwarResult> = EngineRuntime::offlineEwar,
) : ViewModel() {
    var selected by mutableStateOf<Set<String>>(emptySet()); private set
    var query by mutableStateOf(""); private set
    var page by mutableStateOf(0); private set
    var low by mutableStateOf("0"); private set
    var high by mutableStateOf("100"); private set
    var resistance by mutableStateOf("0"); private set
    var ordinate by mutableStateOf(OfflineEwarOrdinate.NEUT); private set
    var ignoreLockRange by mutableStateOf(true); private set
    var ignoreDroneControlRange by mutableStateOf(false); private set
    var result by mutableStateOf<OfflineEwarResult?>(null); private set
    var busy by mutableStateOf(false); private set
    var cancelling by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    private var cancellation: AtomicBoolean? = null
    private var generation = 0L
    private var cleared = false
    private var initializedSelection = false
    private var lastContext: OfflineContext? = null
    private var lastRevisions: Map<String, Long> = emptyMap()
    private fun available(): Boolean = when (val engine = engineState()) {
        is EngineState.Ready -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        is EngineState.Empty -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        else -> false
    }
    val canPlot get() = !cleared && !busy && available() && featureContext() != null && selected.isNotEmpty() &&
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
        // Initialize once; an explicit empty selection also survives leaving/recreation.
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
    fun rangeLow(value: String) { if (value != low) { change(); low = value } }
    fun rangeHigh(value: String) { if (value != high) { change(); high = value } }
    fun selectedResistance(value: String) { if (value != resistance) { change(); resistance = value } }
    fun selectOrdinate(value: OfflineEwarOrdinate) { if (value != ordinate) { change(); ordinate = value } }
    fun lockRange(value: Boolean) { if (value != ignoreLockRange) { change(); ignoreLockRange = value } }
    fun droneControlRange(value: Boolean) { if (value != ignoreDroneControlRange) { change(); ignoreDroneControlRange = value } }
    private fun change() { cancel(); error = null }
    // Keep the launch gate until the actual serialized worker completes. Cooperative
    // cancellation cannot interrupt one EOS call, including after Back or recreation.
    fun cancel() { generation++; cancellation?.set(true); result = null; if (busy) cancelling = true }
    fun stop() { cancel(); error = "Sampling cancelled. The current engine call may still be finishing." }
    private fun isCurrent(request: OfflineEwarRequest): Boolean = available() && featureContext() == request.context &&
        request.fits.all { (id, revision) -> library().any { it.id == id && it.revision == revision } }

    fun plot(context: Context) {
        if (busy || cleared) return
        if (!available()) { error = "The fitting engine is unavailable. Restart the app before plotting."; return }
        val sourceContext = featureContext() ?: run { error = "Offline fitting inputs are not ready yet."; return }
        val fits = OfflineFeatureCodec.frozen(library().filter { it.id in selected }.associate { it.id to it.revision })
        val request = try {
            require(fits.keys == selected)
            OfflineEwarRequest(UUID.randomUUID().toString(), sourceContext, fits, low.trim().toDouble(), high.trim().toDouble(),
                ordinate, resistance.takeIf { it.isNotBlank() }?.trim()?.toDouble(), ignoreLockRange,
                ignoreDroneControlRange).also { it.json() }
        } catch (_: Exception) {
            error = "Select 1–8 fits and an ordered, finite, nonnegative distance range that remains finite in metres. Resistance must be blank or finite; values outside 0–100% are clamped without changing your draft."
            return
        }
        cancel(); val token = generation; val flag = AtomicBoolean(false)
        cancellation = flag; busy = true; cancelling = false; error = null
        val appContext = context.applicationContext
        val pending = try { read(appContext, request, flag) } catch (_: Exception) {
            if (cancellation === flag) { busy = false; cancelling = false; cancellation = null }
            error = "EWAR samples could not be started. Check whether the fitting engine needs a restart."
            return
        }
        pending.whenCompleteAsync({ value, failure ->
            // Only this worker may release its slot, even after cancellation or Back.
            if (cancellation !== flag) return@whenCompleteAsync
            busy = false; cancelling = false; cancellation = null
            if (token == generation) {
                if (failure != null || value == null || value.request != request || value.requestId != request.requestId) error = "EWAR samples could not be verified. Check whether the fitting engine needs a restart."
                else if (!value.ok) error = value.error?.message ?: "EWAR sampling failed."
                else if (!isCurrent(request)) error = "Fit inputs changed while plotting. Plot again."
                else result = value
            }
        }, ContextCompat.getMainExecutor(appContext))
    }
    override fun onCleared() { cleared = true; cancel() }
}

// Include original endpoint drift in the visible plot without changing any coordinates.
internal val OfflineEwarResult.plotLow: Double get() = minOf(request.low, series.minOfOrNull { it.x.minOrNull() ?: request.low } ?: request.low)
internal val OfflineEwarResult.plotHigh: Double get() = maxOf(request.high, series.maxOfOrNull { it.x.maxOrNull() ?: request.high } ?: request.high)

@Composable
private fun EwarOption(label: String, checked: Boolean, tag: String, change: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().toggleable(checked, role = Role.Checkbox, onValueChange = change).testTag(tag)) {
        Checkbox(checked = checked, onCheckedChange = null)
        Text(label)
    }
}

@Composable
internal fun OfflineEwarView(model: OfflineEwarModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val feature by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val fits by EngineRuntime.library.collectAsState(context = Dispatchers.Main)
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    LaunchedEffect(feature?.context, fits.map { it.id to it.revision }, engine) { model.synchronize(feature?.context, fits) }
    DisposableEffect(model) { onDispose { model.cancel() } }
    BackHandler { model.cancel(); onBack() }
    Text("Electronic warfare comparison", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { model.cancel(); onBack() }, modifier = Modifier.testTag("ewar-graph-back")) { Text("Back") }
    Text("Distance (km) · up to 8 fits · original ordered samples · cooperative 10-second work budget.")
    Text("Choose one original EWAR ordinate. ECM is combined maximum racial strength, not jam probability. These curves are not a full target simulation.",
        Modifier.testTag("ewar-graph-explanation"))
    Text("Blank resistance stays unspecified and has the original zero-resistance effect. Finite values are divided by 100 then clamped to 0–1; the requested value is retained. A running engine call must finish before another plot can start.",
        Modifier.testTag("ewar-graph-resistance-explanation"))
    androidx.compose.foundation.layout.Column(Modifier.fillMaxWidth().selectableGroup()) {
        for (value in OfflineEwarOrdinate.values()) {
            Row(Modifier.fillMaxWidth().selectable(model.ordinate == value, role = Role.RadioButton,
                onClick = { model.selectOrdinate(value) }).testTag("ewar-graph-ordinate-${value.quantity}")) {
                RadioButton(selected = model.ordinate == value, onClick = null)
                Text(value.label + (value.unit?.let { " ($it)" } ?: ""))
            }
        }
    }
    OutlinedTextField(value = model.query, onValueChange = model::search, label = { Text("Search fits") },
        modifier = Modifier.fillMaxWidth().testTag("ewar-graph-search"))
    val matches = fits.filter { it.name.contains(model.query, ignoreCase = true) }
    val lastPage = (matches.size - 1).coerceAtLeast(0) / 30
    val page = model.page.coerceIn(0, lastPage)
    Text("${model.selected.size} selected · ${matches.size} matching fits · page ${page + 1} of ${lastPage + 1}",
        Modifier.testTag("ewar-graph-page"))
    if (fits.isEmpty()) Text("Create or import a fit to compare electronic warfare.", Modifier.testTag("ewar-graph-no-fits"))
    else if (matches.isEmpty()) Text("No fits match this search. Selected fits remain selected.", Modifier.testTag("ewar-graph-no-matches"))
    for (fit in matches.drop(page * 30).take(30)) {
        val checked = fit.id in model.selected
        val enabled = checked || model.selected.size < 8
        Row(Modifier.fillMaxWidth().toggleable(checked, enabled = enabled, role = Role.Checkbox, onValueChange = { model.select(fit.id) })
            .testTag("ewar-graph-fit-${fit.id}")) {
            Checkbox(checked = checked, onCheckedChange = null, enabled = enabled)
            Text(fit.name)
        }
    }
    if (lastPage > 0) Row {
        TextButton(onClick = { model.fitPage(page - 1) }, enabled = page > 0,
            modifier = Modifier.testTag("ewar-graph-previous")) { Text("Previous fits") }
        TextButton(onClick = { model.fitPage(page + 1) }, enabled = page < lastPage,
            modifier = Modifier.testTag("ewar-graph-next")) { Text("Next fits") }
    }
    if (model.selected.isEmpty() && fits.isNotEmpty()) Text("Select at least one fit to plot.", Modifier.testTag("ewar-graph-no-selection"))
    OutlinedTextField(value = model.low, onValueChange = model::rangeLow, label = { Text("Distance start (km)") },
        singleLine = true, modifier = Modifier.fillMaxWidth().testTag("ewar-graph-low"))
    OutlinedTextField(value = model.high, onValueChange = model::rangeHigh, label = { Text("Distance end (km)") },
        singleLine = true, modifier = Modifier.fillMaxWidth().testTag("ewar-graph-high"))
    OutlinedTextField(value = model.resistance, onValueChange = model::selectedResistance,
        label = { Text("Target EWAR resistance (%), blank for unspecified") }, singleLine = true,
        modifier = Modifier.fillMaxWidth().testTag("ewar-graph-resistance"))
    EwarOption("Ignore source lock range", model.ignoreLockRange, "ewar-graph-lock", model::lockRange)
    EwarOption("Ignore drone control range", model.ignoreDroneControlRange, "ewar-graph-drone-control", model::droneControlRange)
    Row {
        Button(onClick = { model.plot(context) }, enabled = model.canPlot, modifier = Modifier.testTag("ewar-graph-plot")) { Text("Plot") }
        if (model.busy) TextButton(onClick = { model.stop() }, enabled = !model.cancelling,
            modifier = Modifier.testTag("ewar-graph-cancel")) { Text("Cancel") }
    }
    if (model.busy) Text(if (model.cancelling) "Finishing cancelled sampling…" else "Sampling electronic warfare…", Modifier.testTag("ewar-graph-busy"))
    val unavailable = engine is EngineState.Failed || (engine as? EngineState.Ready)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ||
        (engine as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE
    if (unavailable) Text("The fitting engine is unavailable. Restart the app before plotting.", Modifier.testTag("ewar-graph-unavailable"))
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("ewar-graph-error")) }
    val result = model.currentResult
    if (result == null && !model.busy && model.error == null && model.selected.isNotEmpty())
        Text("Plot to calculate the selected fits with these assumptions.", Modifier.testTag("ewar-graph-not-plotted"))
    result?.let {
        Text(it.request.ordinate.label, Modifier.testTag("ewar-graph-applied-label"))
        Text(if (it.request.ordinate.unit == null) "The original graph specifies no Y-axis unit."
            else "Original Y-axis unit: ${it.request.ordinate.unit}. Signed results are preserved, not limited to 0–100%.",
            Modifier.testTag("ewar-graph-unit-explanation"))
        Text(it.request.resistancePercent?.let { requested ->
            "Requested resistance: $requested% · effective fraction: ${it.request.effectiveResistanceFraction} (clamped to 0–1)."
        } ?: "Requested resistance: unspecified · effective fraction: unspecified (original zero-resistance effect).",
            Modifier.testTag("ewar-graph-effective-resistance"))
        // An empty display suffix means an absent original unit, not an invented one.
        OfflineSamplePlot(it.series.map { series -> OfflinePlotSeries(fits.find { fit -> fit.id == series.fitId }?.name ?: series.fitId, series.x, series.y) },
            it.plotLow, it.plotHigh, "km", it.request.ordinate.unit ?: "", "ewar-graph", "No electronic warfare samples in this range.")
        if (it.series.all { series -> series.y.all { value -> value == 0.0 } })
            Text("Zero effect at every sample with these assumptions.", Modifier.testTag("ewar-graph-zero"))
        it.series.forEachIndexed { index, series ->
            val name = fits.find { fit -> fit.id == series.fitId }?.name ?: series.fitId
            Text("${index + 1}. $name · ${series.x.size} points", Modifier.testTag("ewar-graph-series-${series.fitId}"))
            Text("Sampled ${series.x.minOrNull()}–${series.x.maxOrNull()} km · ${it.request.ordinate.label}: ${series.y.minOrNull()}–${series.y.maxOrNull()}${it.request.ordinate.unit?.let { unit -> " $unit" } ?: ""}")
        }
    }
}
