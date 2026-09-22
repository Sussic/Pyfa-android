package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

class ChargeEditorModel : ViewModel() {
    var options by mutableStateOf<ChargeOptions?>(null)
    var position by mutableStateOf<Int?>(null)
    var selected by mutableStateOf<Int?>(null)
    var query by mutableStateOf("")
    var page by mutableStateOf(0)
    var loading by mutableStateOf(false)
    var editing by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var message by mutableStateOf<String?>(null)
    private var requested: Pair<String, Long>? = null
    private var generation = 0

    fun open(fitId: String?, target: Int?) {
        ++generation
        requested = null
        loading = false
        if (options?.fitId != fitId) options = null
        position = target; selected = null; query = ""; page = 0; error = null; message = null
    }

    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        val previous = options
        if (requested?.first != null && requested?.first != fit.id) {
            position = null; selected = null; query = ""; page = 0; message = null; error = null
        }
        if (retry && options == null) error = null
        requested = next
        val token = ++generation
        loading = true
        EngineRuntime.chargeOptions(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) { options = null; error = "Charges could not be loaded. Try again." }
                else {
                    val target = position
                    if (previous != null && target != null && previous.modules.getOrNull(target)?.itemId != value.modules.getOrNull(target)?.itemId) {
                        position = null; selected = null; page = 0
                    }
                    options = value
                    if (selected !in value.items.map { it.id }) selected = null
                }
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun apply(context: Context, target: Int, charge: Int?) {
        val before = options ?: return
        if (loading || editing) return
        editing = true; error = null; message = null
        EngineRuntime.request(context, BridgeOperation.SetModuleCharge(before.fitId, target, charge),
            mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (requested?.first == before.fitId) {
                if (failure != null) error = "The fitting engine could not confirm the edit. Restart the app."
                else if (!result.isSuccess) error = result.error?.message
                else message = if (charge == null) "Charge unloaded. Fit saved." else "Charge loaded. Fit saved."
                EngineRuntime.library.value.find { it.id == before.fitId }?.let { load(context, it, retry = true) }
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun ChargeEditor(model: ChargeEditorModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val selectedCard = remember { BringIntoViewRequester() }
    LaunchedEffect(model.selected) { if (model.selected != null) selectedCard.bringIntoView() }
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Charges", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("charges-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to see its compatible charges.", modifier = Modifier.testTag("charges-no-fit")); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text(fit.name, style = MaterialTheme.typography.titleLarge)
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("charges-error")) }
    model.message?.let { Text(it, modifier = Modifier.testTag("charges-saved")) }
    if (model.loading) Text("Loading compatible charges…")
    if (model.editing) Text("Saving fit…")
    val options = model.options?.takeIf { it.fitId == fit.id } ?: run {
        if (!model.loading) Button(onClick = { model.load(context, fit, retry = true) }) { Text("Retry") }
        return
    }
    val enabled = !model.loading && !model.editing && options.revision == fit.revision &&
        (state as? EngineState.Ready)?.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
    val target = model.position?.let { options.modules.getOrNull(it) }
    if (target != null) {
        val module = fit.modules.getOrNull(target.index)
        Text(module?.name ?: "Empty slot", modifier = Modifier.testTag("charges-target"))
        Text("Loaded: ${module?.charge ?: "Empty"}", modifier = Modifier.testTag("charges-current"))
        TextButton(onClick = { model.apply(context, target.index, null) }, enabled = enabled && target.chargeId != null,
            modifier = Modifier.testTag("charges-unload")) { Text("Unload charge") }
        TextButton(onClick = { model.position = null; model.selected = null; model.page = 0; model.query = "" },
            modifier = Modifier.testTag("charges-all")) { Text("Charges for active fit") }
    } else Text("Charges for active fit", modifier = Modifier.testTag("charges-active"))
    Text("Choose a charge, then load it into a compatible module. Other modules keep their current charges.",
        style = MaterialTheme.typography.bodySmall)
    val ids = target?.chargeIds?.toSet()
    val available = options.items.filter { ids == null || it.id in ids }
    val chosen = available.find { it.id == model.selected }
    chosen?.let { item ->
        Card(Modifier.fillMaxWidth().bringIntoViewRequester(selectedCard).testTag("charges-selected")) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(item.name, style = MaterialTheme.typography.titleMedium)
                for (module in options.modules.filter { item.id in it.chargeIds && (target == null || it.index == target.index) }) {
                    val name = fit.modules.getOrNull(module.index)?.name ?: "Module ${module.index + 1}"
                    Button(onClick = { focus.clearFocus(); model.apply(context, module.index, item.id) },
                        enabled = enabled && module.chargeId != item.id,
                        modifier = Modifier.fillMaxWidth().testTag("charge-load-${module.index}")) {
                        Text(if (module.chargeId == item.id) "Loaded in ${module.index + 1} · $name" else "Load into ${module.index + 1} · $name")
                    }
                }
            }
        }
    }
    OutlinedTextField(value = model.query, onValueChange = { model.query = it; model.page = 0 },
        label = { Text("Filter compatible charges") }, singleLine = true,
        modifier = Modifier.fillMaxWidth().testTag("charges-search"))
    val rows = available.filter { it.name.contains(model.query.trim(), ignoreCase = true) }
        .sortedWith(compareBy<ChargeItem> { it.name.lowercase() }.thenBy { it.id })
    val pages = maxOf(1, (rows.size + 19) / 20)
    val page = model.page.coerceIn(0, pages - 1)
    Text("${rows.size} charges · Page ${page + 1} of $pages", modifier = Modifier.testTag("charges-count"))
    if (rows.isEmpty()) Text(if (available.isEmpty()) "No compatible charges for this ${if (target == null) "fit" else "module"}."
        else "No charges match this filter.", modifier = Modifier.testTag("charges-empty"))
    for (item in rows.drop(page * 20).take(20)) TextButton(onClick = { focus.clearFocus(); model.selected = item.id },
        enabled = enabled, modifier = Modifier.fillMaxWidth().testTag("charge-item-${item.id}")) { Text(item.name) }
    if (pages > 1) Row {
        TextButton(onClick = { focus.clearFocus(); model.page = page - 1 }, enabled = page > 0,
            modifier = Modifier.testTag("charges-previous")) { Text("Previous") }
        TextButton(onClick = { focus.clearFocus(); model.page = page + 1 }, enabled = page + 1 < pages,
            modifier = Modifier.testTag("charges-next")) { Text("Next") }
    }
}
