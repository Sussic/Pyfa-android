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

class OfflineRemoteRepairModel(
    private val engineState: () -> EngineState = { EngineRuntime.state.value },
    private val featureContext: () -> OfflineContext? = { EngineRuntime.offlineFeatures.value?.context },
    private val library: () -> List<FitSnapshot> = { EngineRuntime.library.value },
    private val activeFitId: () -> String? = { EngineRuntime.navigation.value.activeId },
    private val read: (Context, OfflineRemoteRepairRequest, AtomicBoolean) -> CompletableFuture<OfflineRemoteRepairResult> = EngineRuntime::offlineRemoteRepair,
) : ViewModel() {
    var selected by mutableStateOf<Set<String>>(emptySet()); private set
    var query by mutableStateOf(""); private set
    var page by mutableStateOf(0); private set
    private var distanceLow by mutableStateOf("0")
    private var distanceHigh by mutableStateOf("100")
    private var timeLow by mutableStateOf("0")
    private var timeHigh by mutableStateOf("100")
    var axis by mutableStateOf(OfflineRemoteRepairAxis.DISTANCE); private set
    val low get() = if (axis == OfflineRemoteRepairAxis.TIME) timeLow else distanceLow
    val high get() = if (axis == OfflineRemoteRepairAxis.TIME) timeHigh else distanceHigh
    var distance by mutableStateOf(""); private set
    var time by mutableStateOf(""); private set
    var ordinate by mutableStateOf(OfflineRemoteRepairOrdinate.RATE); private set
    var ancillaryReload by mutableStateOf(true); private set
    var ignoreLockRange by mutableStateOf(true); private set
    var ignoreDroneControlRange by mutableStateOf(false); private set
    var result by mutableStateOf<OfflineRemoteRepairResult?>(null); private set
    var busy by mutableStateOf(false); private set
    var cancelling by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    private var cancellation: AtomicBoolean? = null
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
    fun rangeLow(value: String) { if (value != low) { change(); if (axis == OfflineRemoteRepairAxis.TIME) timeLow = value else distanceLow = value } }
    fun rangeHigh(value: String) { if (value != high) { change(); if (axis == OfflineRemoteRepairAxis.TIME) timeHigh = value else distanceHigh = value } }
    fun selectAxis(value: OfflineRemoteRepairAxis) { if (value != axis) { change(); axis = value } }
    fun selectedDistance(value: String) { if (value != distance) { change(); distance = value } }
    fun selectOrdinate(value: OfflineRemoteRepairOrdinate) { if (value != ordinate) { change(); ordinate = value } }
    fun selectedTime(value: String) { if (value != time) { change(); time = value } }
    fun ancillary(value: Boolean) { if (value != ancillaryReload) { change(); ancillaryReload = value } }
    fun lockRange(value: Boolean) { if (value != ignoreLockRange) { change(); ignoreLockRange = value } }
    fun droneControlRange(value: Boolean) { if (value != ignoreDroneControlRange) { change(); ignoreDroneControlRange = value } }
    private fun change() { cancel(); error = null }
    // Keep the launch gate until the actual serialized worker completes. Cooperative
    // cancellation cannot interrupt one EOS call, including after Back or recreation.
    fun cancel() { generation++; cancellation?.set(true); result = null; if (busy) cancelling = true }
    fun stop() { cancel(); error = "Sampling cancelled. The current engine call may still be finishing." }
    private fun isCurrent(request: OfflineRemoteRepairRequest): Boolean = available() && featureContext() == request.context &&
        request.fits.all { (id, revision) -> library().any { it.id == id && it.revision == revision } }

    fun plot(context: Context) {
        if (busy) return
        if (!available()) { error = "The fitting engine is unavailable. Restart the app before plotting."; return }
        val sourceContext = featureContext() ?: run { error = "Offline fitting inputs are not ready yet."; return }
        val fits = OfflineFeatureCodec.frozen(library().filter { it.id in selected }.associate { it.id to it.revision })
        if (axis == OfflineRemoteRepairAxis.DISTANCE && ordinate == OfflineRemoteRepairOrdinate.AMOUNT && time.isBlank()) {
            error = "Accumulated repair requires a finite selected time in seconds. Enter 0 for time zero."
            return
        }
        val request = try {
            require(fits.keys == selected)
            OfflineRemoteRepairRequest(UUID.randomUUID().toString(), sourceContext, fits, low.toDouble(), high.toDouble(),
                ancillaryReload, ignoreLockRange, ignoreDroneControlRange,
                time = if (axis == OfflineRemoteRepairAxis.DISTANCE) time.takeIf { it.isNotBlank() }?.trim()?.toDouble() else null,
                ordinate = ordinate, axis = axis,
                distance = if (axis == OfflineRemoteRepairAxis.TIME) distance.takeIf { it.isNotBlank() }?.trim()?.toDouble() else null).also { it.json() }
        } catch (_: Exception) {
            error = if (axis == OfflineRemoteRepairAxis.TIME) "Select 1–8 fits and ordered finite time endpoints. Each endpoint is clamped to 0–2500 seconds. Secondary distance must be blank or finite, nonnegative km that remains finite in metres."
                else "Select 1–8 fits and an ordered, finite, nonnegative distance range that remains finite in metres. Selected time must be a finite number of seconds; only repair rate allows blank time."
            return
        }
        cancel(); val token = generation; val flag = AtomicBoolean(false)
        cancellation = flag; busy = true; cancelling = false; error = null
        val appContext = context.applicationContext
        val pending = try { read(appContext, request, flag) } catch (_: Exception) {
            busy = false; cancelling = false; cancellation = null
            error = "Remote repair samples could not be started. Check whether the fitting engine needs a restart."
            return
        }
        pending.whenCompleteAsync({ value, failure ->
            busy = false; cancelling = false; cancellation = null
            if (token == generation) {
                if (failure != null || value == null) error = "Remote repair samples could not be verified. Check whether the fitting engine needs a restart."
                else if (!value.ok) error = value.error?.message ?: "Remote repair sampling failed."
                else if (!isCurrent(request)) error = "Fit inputs changed while plotting. Plot again."
                else result = value
            }
        }, ContextCompat.getMainExecutor(appContext))
    }
    override fun onCleared() { cancel() }
}

// Bound chart storage by the decoder's whole-request point ceiling; retain each original
// vertex once in the drawing path. This is not a claim about native heap-byte usage.
internal val OfflineRemoteRepairResult.plotLow: Double get() =
    if (request.axis == OfflineRemoteRepairAxis.TIME) minOf(request.effectiveLow, series.minOfOrNull { it.x.minOrNull() ?: request.effectiveLow } ?: request.effectiveLow) else request.low
internal val OfflineRemoteRepairResult.plotHigh: Double get() =
    if (request.axis == OfflineRemoteRepairAxis.TIME) maxOf(request.effectiveHigh, series.maxOfOrNull { it.x.maxOrNull() ?: request.effectiveHigh } ?: request.effectiveHigh) else request.high

@Composable
private fun RemoteRepairOption(label: String, checked: Boolean, tag: String, change: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().toggleable(checked, role = Role.Checkbox, onValueChange = change).testTag(tag)) {
        Checkbox(checked = checked, onCheckedChange = null)
        Text(label)
    }
}

@Composable
internal fun OfflineRemoteRepairView(model: OfflineRemoteRepairModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val feature by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val fits by EngineRuntime.library.collectAsState(context = Dispatchers.Main)
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    LaunchedEffect(feature?.context, fits.map { it.id to it.revision }, engine) { model.synchronize(feature?.context, fits) }
    DisposableEffect(model) { onDispose { model.cancel() } }
    BackHandler { model.cancel(); onBack() }
    Text("Remote repair comparison", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { model.cancel(); onBack() }, modifier = Modifier.testTag("remote-repair-graph-back")) { Text("Back") }
    Text("${model.axis.quantity} (${model.axis.unit}) → applied repair (${model.ordinate.unit}). Up to 8 fits · original ordered samples · cooperative 10-second work budget.")
    Text("Outgoing shield + armor + hull repair after distance gates. Excludes capacitor transfer; no recipient resistance, tank, or diminishing-return calculation.",
        Modifier.testTag("remote-repair-graph-rate-explanation"))
    Text("Distance graphs: blank time uses current repair rate; accumulated HP requires an explicit time. Time graphs: endpoints are clamped independently to 0–2500 seconds; blank distance bypasses range gates, while 0 km is an actual distance. Original duplicate and overshoot points are preserved. A running engine call must finish before another plot can start.")
    Row(Modifier.fillMaxWidth().selectableGroup()) {
        for (value in OfflineRemoteRepairAxis.values()) {
            Row(Modifier.weight(1f).selectable(model.axis == value, role = Role.RadioButton,
                onClick = { model.selectAxis(value) }).testTag("remote-repair-graph-axis-${value.quantity}")) {
                RadioButton(selected = model.axis == value, onClick = null)
                Text("${value.quantity.replaceFirstChar { it.uppercase() }} (${value.unit})")
            }
        }
    }
    Row(Modifier.fillMaxWidth().selectableGroup()) {
        for ((value, label, tag) in listOf(
            Triple(OfflineRemoteRepairOrdinate.RATE, "Repair rate (HP/s)", "rate"),
            Triple(OfflineRemoteRepairOrdinate.AMOUNT, "Accumulated repair (HP)", "amount"),
        )) {
            Row(Modifier.weight(1f).selectable(model.ordinate == value, role = Role.RadioButton,
                onClick = { model.selectOrdinate(value) }).testTag("remote-repair-graph-ordinate-$tag")) {
                RadioButton(selected = model.ordinate == value, onClick = null)
                Text(label)
            }
        }
    }
    OutlinedTextField(value = model.query, onValueChange = model::search, label = { Text("Search fits") },
        modifier = Modifier.fillMaxWidth().testTag("remote-repair-graph-search"))
    val matches = fits.filter { it.name.contains(model.query, ignoreCase = true) }
    val lastPage = (matches.size - 1).coerceAtLeast(0) / 30
    val page = model.page.coerceIn(0, lastPage)
    Text("${model.selected.size} selected · ${matches.size} matching fits · page ${page + 1} of ${lastPage + 1}",
        Modifier.testTag("remote-repair-graph-page"))
    if (fits.isEmpty()) Text("Create or import a fit to compare remote repair.", Modifier.testTag("remote-repair-graph-no-fits"))
    else if (matches.isEmpty()) Text("No fits match this search. Selected fits remain selected.", Modifier.testTag("remote-repair-graph-no-matches"))
    for (fit in matches.drop(page * 30).take(30)) {
        val checked = fit.id in model.selected
        val enabled = checked || model.selected.size < 8
        Row(Modifier.fillMaxWidth().toggleable(checked, enabled = enabled, role = Role.Checkbox, onValueChange = { model.select(fit.id) })
            .testTag("remote-repair-graph-fit-${fit.id}")) {
            Checkbox(checked = checked, onCheckedChange = null, enabled = enabled)
            Text(fit.name)
        }
    }
    if (lastPage > 0) Row {
        TextButton(onClick = { model.fitPage(page - 1) }, enabled = page > 0,
            modifier = Modifier.testTag("remote-repair-graph-previous")) { Text("Previous fits") }
        TextButton(onClick = { model.fitPage(page + 1) }, enabled = page < lastPage,
            modifier = Modifier.testTag("remote-repair-graph-next")) { Text("Next fits") }
    }
    if (model.selected.isEmpty() && fits.isNotEmpty()) Text("Select at least one fit to plot.", Modifier.testTag("remote-repair-graph-no-selection"))
    OutlinedTextField(value = model.low, onValueChange = model::rangeLow, label = { Text("${model.axis.quantity.replaceFirstChar { it.uppercase() }} start (${model.axis.unit})") },
        singleLine = true, modifier = Modifier.fillMaxWidth().testTag("remote-repair-graph-low"))
    OutlinedTextField(value = model.high, onValueChange = model::rangeHigh, label = { Text("${model.axis.quantity.replaceFirstChar { it.uppercase() }} end (${model.axis.unit})") },
        singleLine = true, modifier = Modifier.fillMaxWidth().testTag("remote-repair-graph-high"))
    if (model.axis == OfflineRemoteRepairAxis.TIME) OutlinedTextField(value = model.distance, onValueChange = model::selectedDistance,
        label = { Text("Secondary distance (km), blank to bypass range gates") }, singleLine = true,
        modifier = Modifier.fillMaxWidth().testTag("remote-repair-graph-distance"))
    else OutlinedTextField(value = model.time, onValueChange = model::selectedTime, label = { Text(if (model.ordinate == OfflineRemoteRepairOrdinate.AMOUNT) "Selected time (s), required for accumulated HP"
            else "Selected time (s), blank for current rate") },
        singleLine = true, modifier = Modifier.fillMaxWidth().testTag("remote-repair-graph-time"))
    RemoteRepairOption("Include ancillary reload time", model.ancillaryReload, "remote-repair-graph-ancillary", model::ancillary)
    RemoteRepairOption("Ignore source lock range", model.ignoreLockRange, "remote-repair-graph-lock", model::lockRange)
    RemoteRepairOption("Ignore drone control range", model.ignoreDroneControlRange, "remote-repair-graph-drone-control", model::droneControlRange)
    Row {
        Button(onClick = { model.plot(context) }, enabled = model.canPlot, modifier = Modifier.testTag("remote-repair-graph-plot")) { Text("Plot") }
        if (model.busy) TextButton(onClick = { model.stop() }, enabled = !model.cancelling,
            modifier = Modifier.testTag("remote-repair-graph-cancel")) { Text("Cancel") }
    }
    if (model.busy) Text(if (model.cancelling) "Finishing cancelled sampling…" else "Sampling remote repair…", Modifier.testTag("remote-repair-graph-busy"))
    val unavailable = engine is EngineState.Failed || (engine as? EngineState.Ready)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ||
        (engine as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE
    if (unavailable) Text("The fitting engine is unavailable. Restart the app before plotting.", Modifier.testTag("remote-repair-graph-unavailable"))
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("remote-repair-graph-error")) }
    val result = model.currentResult
    if (result == null && !model.busy && model.error == null && model.selected.isNotEmpty())
        Text("Plot to calculate the selected fits with these assumptions.", Modifier.testTag("remote-repair-graph-not-plotted"))
    result?.let {
        Text(if (it.request.axis == OfflineRemoteRepairAxis.TIME) "${if (it.request.ordinate == OfflineRemoteRepairOrdinate.AMOUNT) "Accumulated applied repair (HP)" else "Applied repair rate (HP/s)"} over time"
            else if (it.request.ordinate == OfflineRemoteRepairOrdinate.AMOUNT) "Accumulated applied repair (HP) at each sampled distance"
            else if (it.request.time == null) "Current applied repair rate at each sampled distance"
            else "Selected-time applied repair rate at each sampled distance", Modifier.testTag("remote-repair-graph-applied-label"))
        Text(if (it.request.axis == OfflineRemoteRepairAxis.TIME) "Requested time range: ${it.request.low}–${it.request.high} s · effective: ${it.request.effectiveLow}–${it.request.effectiveHigh} s (clamped to 0–2500 s). Distance: ${it.request.distance?.let { d -> "$d km" } ?: "range gates bypassed"}"
            else if (it.request.time == null) "Current rate · no selected elapsed time"
            else if (it.request.time == it.effectiveTime) "Selected time: ${it.effectiveTime} s"
            else "Requested time: ${it.request.time} s · effective time: ${it.effectiveTime} s (clamped to 0–2500 s)",
            Modifier.testTag("remote-repair-graph-time-explanation"))
        OfflineSamplePlot(it.series.map { series -> OfflinePlotSeries(fits.find { fit -> fit.id == series.fitId }?.name ?: series.fitId, series.x, series.y) },
            it.plotLow, it.plotHigh, it.request.axis.unit, it.request.ordinate.unit, "remote-repair-graph", "No remote repair samples in this range.")
        if (it.series.all { series -> series.y.all { rate -> rate == 0.0 } })
            Text("Zero applied repair at every sample with these assumptions.", Modifier.testTag("remote-repair-graph-zero"))
        Text("Current source rates (HP/s), independent of the curve ordinate, before range application, using each fit's reload settings. These readouts do not use the graph's ancillary-reload override and may differ from the applied curve.",
            Modifier.testTag("remote-repair-graph-source-explanation"))
        it.series.forEachIndexed { index, series ->
            val name = fits.find { fit -> fit.id == series.fitId }?.name ?: series.fitId
            Text("${index + 1}. $name · ${series.x.size} points", Modifier.testTag("remote-repair-graph-series-${series.fitId}"))
            Text("Current source shield: ${series.sourceRates.shield} HP/s", Modifier.testTag("remote-repair-graph-source-shield-${series.fitId}"))
            Text("Current source armor: ${series.sourceRates.armor} HP/s", Modifier.testTag("remote-repair-graph-source-armor-${series.fitId}"))
            Text("Current source hull: ${series.sourceRates.hull} HP/s", Modifier.testTag("remote-repair-graph-source-hull-${series.fitId}"))
            Text("Sampled ${series.x.minOrNull()}–${series.x.maxOrNull()} ${it.request.axis.unit} · applied repair: ${series.y.minOrNull()}–${series.y.maxOrNull()} ${it.request.ordinate.unit}")
        }
    }
}
