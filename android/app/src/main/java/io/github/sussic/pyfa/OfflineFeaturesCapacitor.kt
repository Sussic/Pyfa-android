package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.Dispatchers

class OfflineCapacitorModel : ViewModel() {
    var selected by mutableStateOf<Set<String>>(emptySet()); private set
    var query by mutableStateOf("")
    var xUnit by mutableStateOf("s"); private set
    var yUnit by mutableStateOf("GJ"); private set
    var low by mutableStateOf("0"); private set
    var high by mutableStateOf("300"); private set
    var starting by mutableStateOf("100"); private set
    var simulation by mutableStateOf(true); private set
    var result by mutableStateOf<OfflineCapacitorResult?>(null); private set
    var busy by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    private var cancellation: AtomicBoolean? = null
    private var generation = 0
    private var lastContext: OfflineContext? = null
    fun synchronize(context: OfflineContext?, fits: List<FitSnapshot>) {
        if (context != lastContext) {
            if (lastContext != null && (busy || result != null)) { cancel(); error = "Fits or profiles changed. Plot again to use their current values." }
            lastContext = context
        }
        val live = fits.map { it.id }.toSet()
        if (!live.containsAll(selected)) { cancel(); selected = selected.intersect(live) }
        if (selected.isEmpty()) selected = (EngineRuntime.navigation.value.activeId ?: fits.firstOrNull()?.id)?.let { setOf(it) }.orEmpty()
    }
    fun select(id: String) {
        if (id !in selected && selected.size >= 8) return
        change(); selected = if (id in selected) selected - id else selected + id
    }
    fun axis(unit: String) { change(); xUnit = unit; low = "0"; high = if (unit == "s") "300" else if (unit == "%") "100" else "1000" }
    fun output(unit: String) { change(); yUnit = unit }
    fun rangeLow(value: String) { change(); low = value }
    fun rangeHigh(value: String) { change(); high = value }
    fun start(value: String) { change(); starting = value }
    fun simulate(value: Boolean) { change(); simulation = value }
    private fun change() { cancel(); error = null }
    // Keep the launch gate held until the actual worker future completes. A cancelled
    // non-cooperative EOS simulation must not accumulate replacement requests.
    fun cancel() { generation++; cancellation?.set(true); result = null }
    fun stop() { cancel(); error = "Sampling cancelled. The cooperative engine call may still be finishing." }
    fun plot(context: Context) {
        if (busy) return
        val feature = EngineRuntime.offlineFeatures.value ?: return
        val fits = EngineRuntime.library.value.filter { it.id in selected }.associate { it.id to it.revision }
        val request = try {
            OfflineCapacitorRequest(UUID.randomUUID().toString(), feature.context, fits,
                if (xUnit == "s") "time" else "cap_amount", xUnit, low.toDouble(), high.toDouble(),
                if (yUnit == "GJ") "cap_amount" else "cap_regen", yUnit, starting.toDouble(), simulation).also { it.json() }
        } catch (_: Exception) {
            error = "Select 1–8 fits, an ordered nonnegative range (time ≤ 3600 s or percentage ≤ 100), and starting capacitor from 0–100%."
            return
        }
        cancel(); val token = generation; val flag = AtomicBoolean(false); cancellation = flag; busy = true; error = null
        EngineRuntime.offlineCapacitor(context, request, flag).whenCompleteAsync({ value, failure ->
            busy = false; cancellation = null
            if (token == generation) {
                val current = EngineRuntime.offlineFeatures.value?.context == request.context &&
                    request.fits.all { (id, revision) -> EngineRuntime.library.value.any { it.id == id && it.revision == revision } }
                if (!current) error = "Fit inputs changed while plotting. Plot again."
                else if (failure != null) error = "Capacitor samples could not be verified. Check whether the engine needs a restart."
                else if (!value.ok) error = value.error?.message
                else result = value
            }
        }, ContextCompat.getMainExecutor(context))
    }
    override fun onCleared() { cancellation?.set(true) }
}

@Composable
internal fun OfflineCapacitorView(model: OfflineCapacitorModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val feature by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val fits by EngineRuntime.library.collectAsState(context = Dispatchers.Main)
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    LaunchedEffect(feature?.context, fits.map { it.id to it.revision }) { model.synchronize(feature?.context, fits) }
    DisposableEffect(model) { onDispose { model.cancel() } }
    BackHandler { model.cancel(); onBack() }
    Text("Capacitor comparison", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { model.cancel(); onBack() }, modifier = Modifier.testTag("cap-graph-back")) { Text("Back") }
    Text("EOS samples · up to 8 fits · 256 intervals · cooperative 10-second work budget. A simulation call cannot be forcibly interrupted.")
    OutlinedTextField(value = model.query, onValueChange = { model.query = it }, label = { Text("Search fits") }, modifier = Modifier.fillMaxWidth())
    val matches = fits.filter { it.name.contains(model.query, ignoreCase = true) }
    Text("${model.selected.size} selected · ${matches.size} matching fits (first 30 shown)")
    for (fit in matches.take(30)) Row {
        Checkbox(checked = fit.id in model.selected, onCheckedChange = { model.select(fit.id) },
            enabled = fit.id in model.selected || model.selected.size < 8, modifier = Modifier.testTag("cap-graph-fit-${fit.id}"))
        Text(fit.name)
    }
    Text("Horizontal axis")
    Row { for (unit in listOf("s", "%", "GJ")) TextButton(onClick = { model.axis(unit) }, modifier = Modifier.testTag("cap-graph-x-$unit")) { Text((if (unit == model.xUnit) "✓ " else "") + if (unit == "s") "Time (s)" else "Cap ($unit)") } }
    Text("Vertical axis")
    Row { for (unit in listOf("GJ", "GJ/s")) TextButton(onClick = { model.output(unit) }, modifier = Modifier.testTag("cap-graph-y-$unit")) { Text((if (unit == model.yUnit) "✓ " else "") + unit) } }
    OutlinedTextField(value = model.low, onValueChange = model::rangeLow, label = { Text("Range start (${model.xUnit})") }, singleLine = true, modifier = Modifier.fillMaxWidth().testTag("cap-graph-low"))
    OutlinedTextField(value = model.high, onValueChange = model::rangeHigh, label = { Text("Range end (${model.xUnit})") }, singleLine = true, modifier = Modifier.fillMaxWidth().testTag("cap-graph-high"))
    OutlinedTextField(value = model.starting, onValueChange = model::start, label = { Text("Starting capacitor (%)") }, singleLine = true, modifier = Modifier.fillMaxWidth().testTag("cap-graph-start"))
    Row {
        Checkbox(checked = model.simulation, onCheckedChange = model::simulate, modifier = Modifier.testTag("cap-graph-simulation"))
        Text("Use module simulation for time → capacitor amount")
    }
    val unavailable = (engine as? EngineState.Ready)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ||
        (engine as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE
    Row {
        Button(onClick = { model.plot(context) }, enabled = model.selected.isNotEmpty() && !model.busy && !unavailable,
            modifier = Modifier.testTag("cap-graph-plot")) { Text("Plot") }
        if (model.busy) TextButton(onClick = { model.stop() }, modifier = Modifier.testTag("cap-graph-cancel")) { Text("Cancel") }
    }
    if (model.busy) Text("Sampling capacitor…", Modifier.testTag("cap-graph-busy"))
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("cap-graph-error")) }
    model.result?.let { result ->
        OfflineCapacitorPlot(result)
        result.series.forEachIndexed { index, series ->
            Text("${index + 1}. ${fits.find { it.id == series.fitId }?.name ?: series.fitId} · ${series.mode.replace('_', ' ')} · ${series.x.size} points", Modifier.testTag("cap-graph-series-${series.fitId}"))
            Text("Capacity ${series.capacityGj} GJ · recharge ${series.rechargeSeconds} s")
            if (series.x.isEmpty()) Text("No samples in the requested range. Nothing is extrapolated.")
            else Text("Sampled ${series.x.first()}–${series.x.last()} ${result.request.xUnit}")
        }
    }
}

@Composable
private fun OfflineCapacitorPlot(result: OfflineCapacitorResult) {
    OfflineSamplePlot(result.series.map { OfflinePlotSeries(it.fitId, it.x, it.y) }, result.request.low, result.request.high,
        result.request.xUnit, result.request.yUnit, "cap-graph", "No capacitor samples in this range.")
}
