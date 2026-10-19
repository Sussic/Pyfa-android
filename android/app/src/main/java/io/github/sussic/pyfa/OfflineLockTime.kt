package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.selection.toggleable
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
import androidx.compose.ui.semantics.Role
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.Dispatchers

class OfflineLockTimeModel : ViewModel() {
    var selected by mutableStateOf<Set<String>>(emptySet()); private set
    var query by mutableStateOf("")
    var low by mutableStateOf("25"); private set
    var high by mutableStateOf("500"); private set
    var result by mutableStateOf<OfflineLockTimeResult?>(null); private set
    var busy by mutableStateOf(false); private set
    var cancelling by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    private var cancellation: AtomicBoolean? = null
    private var generation = 0
    private var lastContext: OfflineContext? = null
    private var lastRevisions: Map<String, Long> = emptyMap()
    private fun available(): Boolean = when (val engine = EngineRuntime.state.value) {
        is EngineState.Ready -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        is EngineState.Empty -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        else -> false
    }
    val canPlot get() = !busy && available() && EngineRuntime.offlineFeatures.value != null && selected.isNotEmpty()
    val currentResult get() = result?.takeIf { isCurrent(it.request) }
    fun synchronize(context: OfflineContext?, fits: List<FitSnapshot>) {
        val revisions = fits.associate { it.id to it.revision }
        if (context != lastContext || selected.any { lastRevisions[it] != revisions[it] } || !available()) {
            if (busy || result != null) { cancel(); error = "Fits or profiles changed. Plot again to use their current values." }
            lastContext = context
        }
        lastRevisions = revisions
        val live = revisions.keys
        if (!live.containsAll(selected)) { cancel(); selected = selected.intersect(live) }
        if (selected.isEmpty()) selected = (EngineRuntime.navigation.value.activeId ?: fits.firstOrNull()?.id)?.let { setOf(it) }.orEmpty()
    }
    fun select(id: String) {
        if (id !in selected && (selected.size >= 8 || EngineRuntime.library.value.none { it.id == id })) return
        change(); selected = if (id in selected) selected - id else selected + id
    }
    fun rangeLow(value: String) { if (value != low) { change(); low = value } }
    fun rangeHigh(value: String) { if (value != high) { change(); high = value } }
    private fun change() { cancel(); error = null }
    // Cancellation never releases the launch gate before the real worker completes.
    // Repeated taps cannot enqueue unbounded requests behind a noncooperative EOS call.
    fun cancel() { generation++; cancellation?.set(true); result = null; if (busy) cancelling = true }
    fun stop() { cancel(); error = "Sampling cancelled. The cooperative engine call may still be finishing." }
    private fun isCurrent(request: OfflineLockTimeRequest): Boolean = available() &&
        EngineRuntime.offlineFeatures.value?.context == request.context &&
        request.fits.all { (id, revision) -> EngineRuntime.library.value.any { it.id == id && it.revision == revision } }
    fun plot(context: Context) {
        if (busy) return
        if (!available()) { error = "The fitting engine is unavailable. Restart the app before plotting."; return }
        val feature = EngineRuntime.offlineFeatures.value ?: return
        val fits = EngineRuntime.library.value.filter { it.id in selected }.associate { it.id to it.revision }
        val request = try {
            OfflineLockTimeRequest(UUID.randomUUID().toString(), feature.context, fits, low.toDouble(), high.toDouble()).also { it.json() }
        } catch (_: Exception) {
            error = "Select 1–8 fits and an ordered signature-radius range from 1 to 1,000,000,000 m."
            return
        }
        cancel(); val token = generation; val flag = AtomicBoolean(false)
        cancellation = flag; busy = true; cancelling = false; error = null
        EngineRuntime.offlineLockTime(context, request, flag).whenCompleteAsync({ value, failure ->
            busy = false; cancelling = false; cancellation = null
            if (token == generation) {
                if (failure != null) error = "Lock-time samples could not be verified. Check whether the fitting engine needs a restart."
                else if (!value.ok) error = value.error?.message
                else if (!isCurrent(request)) error = "Fit inputs changed while plotting. Plot again."
                else result = value
            }
        }, ContextCompat.getMainExecutor(context))
    }
    override fun onCleared() { cancellation?.set(true) }
}

@Composable
internal fun OfflineLockTimeView(model: OfflineLockTimeModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val feature by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val fits by EngineRuntime.library.collectAsState(context = Dispatchers.Main)
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    LaunchedEffect(feature?.context, fits.map { it.id to it.revision }, engine) { model.synchronize(feature?.context, fits) }
    DisposableEffect(model) { onDispose { model.cancel() } }
    BackHandler { model.cancel(); onBack() }
    Text("Lock-time comparison", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { model.cancel(); onBack() }, modifier = Modifier.testTag("lock-graph-back")) { Text("Back") }
    Text("Target signature radius (m) → lock time (s). EOS samples · up to 8 fits · 200 intervals · cooperative 10-second work budget.")
    OutlinedTextField(value = model.query, onValueChange = { model.query = it }, label = { Text("Search fits") },
        modifier = Modifier.fillMaxWidth().testTag("lock-graph-search"))
    val matches = fits.filter { it.name.contains(model.query, ignoreCase = true) }
    Text("${model.selected.size} selected · ${matches.size} matching fits (first 30 shown)")
    for (fit in matches.take(30)) {
        val checked = fit.id in model.selected
        val enabled = checked || model.selected.size < 8
        Row(Modifier.fillMaxWidth().toggleable(checked, enabled = enabled, role = Role.Checkbox, onValueChange = { model.select(fit.id) })
            .testTag("lock-graph-fit-${fit.id}")) {
            Checkbox(checked = checked, onCheckedChange = null, enabled = enabled)
            Text(fit.name)
        }
    }
    OutlinedTextField(value = model.low, onValueChange = model::rangeLow, label = { Text("Signature radius start (m)") },
        singleLine = true, modifier = Modifier.fillMaxWidth().testTag("lock-graph-low"))
    OutlinedTextField(value = model.high, onValueChange = model::rangeHigh, label = { Text("Signature radius end (m)") },
        singleLine = true, modifier = Modifier.fillMaxWidth().testTag("lock-graph-high"))
    Row {
        Button(onClick = { model.plot(context) }, enabled = model.canPlot, modifier = Modifier.testTag("lock-graph-plot")) { Text("Plot") }
        if (model.busy) TextButton(onClick = { model.stop() }, enabled = !model.cancelling,
            modifier = Modifier.testTag("lock-graph-cancel")) { Text("Cancel") }
    }
    if (model.busy) Text(if (model.cancelling) "Finishing cancelled sampling…" else "Sampling lock time…", Modifier.testTag("lock-graph-busy"))
    val unavailable = (engine as? EngineState.Ready)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE ||
        (engine as? EngineState.Empty)?.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE
    if (unavailable) Text("The fitting engine is unavailable. Restart the app before plotting.", Modifier.testTag("lock-graph-unavailable"))
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("lock-graph-error")) }
    model.currentResult?.let { result ->
        OfflineSamplePlot(result.series.map { series -> OfflinePlotSeries(fits.find { it.id == series.fitId }?.name ?: series.fitId, series.x, series.y) },
            result.request.low, result.request.high, "m", "s", "lock-graph", "No lock-time samples in this range.")
        result.series.forEachIndexed { index, series ->
            val name = fits.find { it.id == series.fitId }?.name ?: series.fitId
            Text("${index + 1}. $name · ${series.x.size} points", Modifier.testTag("lock-graph-series-${series.fitId}"))
            Text(if (series.scanResolution != null && series.scanResolution > 0) "Scan resolution: ${series.scanResolution} mm"
                else "Scan resolution: ${series.scanResolution?.toString() ?: "unavailable"} · EOS scan-speed fallback",
                Modifier.testTag("lock-graph-scan-${series.fitId}"))
            Text("Sampled ${series.x.first()}–${series.x.last()} m · lock time ${series.y.minOrNull()}–${series.y.maxOrNull()} s")
        }
    }
}
