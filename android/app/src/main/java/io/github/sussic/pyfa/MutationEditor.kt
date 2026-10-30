package io.github.sussic.pyfa

import android.content.Context
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

class MutationEditorModel : ViewModel() {
    var details by mutableStateOf<MutationDisplayDetails?>(null); private set
    var loading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var uncertain by mutableStateOf(false); private set
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    private fun fit() = (EngineRuntime.state.value as? EngineState.Ready)
        ?.takeUnless { it.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE }?.fit
    val current get() = details?.takeIf { d -> fit()?.let { it.id == d.fitId && it.revision == d.revision } == true }
    val available get() = !loading && !editing && !uncertain && current != null

    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        if (uncertain || (!retry && requested == (fit.id to fit.revision))) return
        requested = fit.id to fit.revision; details = null; loading = true; error = null
        val token = ++generation
        EngineRuntime.mutationDisplayDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Exact rolls could not be verified. Restart if the engine is unavailable."
                else if (requested == (value.fitId to value.revision)) details = value
                else error = "The fit changed. Reload its current exact values."
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun save(context: Context, before: MutationDisplayDetails, row: MutationDisplayItem,
        texts: List<String>, representations: List<String>) {
        if (!available || before !== current || row !in before.items ||
            texts.size != row.attributes.size || representations.size != row.attributes.size) return
        val edits = mutableListOf<MutationDisplayEdit>()
        for (i in row.attributes.indices) {
            val attribute = row.attributes[i]
            val representation = MutationValueRepresentation.entries.singleOrNull { it.wire == representations[i] }
            if (representation == null) { error = "Choose raw or converted entry for every value."; return }
            val range = when (representation) {
                MutationValueRepresentation.RAW -> attribute.raw.minimum..attribute.raw.maximum
                MutationValueRepresentation.DISPLAY -> {
                    val display = attribute.display as? MutationDisplayValue.Available
                    if (display == null) { error = "Converted entry is unavailable for this attribute. Use raw entry."; return }
                    display.minimum..display.maximum
                }
            }
            val value = texts[i].toDoubleOrNull()
            if (value == null || !value.isFinite() || value !in range) {
                error = "Enter a finite numeric value within its selected raw or converted range."; return
            }
            // An untouched value never passes through a display conversion or a raw
            // formatting round trip at the backend. Changing entry mode alone is not an edit.
            if (value.toRawBits() != attribute.sourceValue(representation).toRawBits()) {
                edits.add(MutationDisplayEdit(attribute.raw.attributeId, value, representation))
            }
        }
        if (edits.isEmpty()) return
        editing = true; error = null
        EngineRuntime.request(context, BridgeOperation.SetMutationDisplayAttributes(before.fitId, row.raw.kind,
            row.raw.position, row.raw.objectKey, edits), mapOf(before.fitId to before.revision)).whenCompleteAsync({ result, failure ->
            editing = false
            if (failure != null) {
                uncertain = true; details = null
                error = "The save outcome could not be confirmed. Restart the app before editing; do not repeat the save."
            } else if (requested?.first == before.fitId) {
                val refused = if (!result.isSuccess) result.error?.message ?: "The exact-roll change was refused." else null
                fit()?.takeIf { it.id == before.fitId }?.let { load(context, it, retry = true) }
                error = refused
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
internal fun MutationEditorDialog(model: MutationEditorModel, onClose: () -> Unit) {
    val context = LocalContext.current
    val state by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (state as? EngineState.Ready)?.fit
    Dialog(onDismissRequest = onClose) {
        Surface { Column(Modifier.fillMaxWidth().fillMaxHeight(.9f).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Exact mutation rolls", style = MaterialTheme.typography.headlineSmall)
            TextButton(onClick = onClose, modifier = Modifier.testTag("mutation-close")) { Text("Close without saving drafts") }
            Text("Edit existing mutated modules and drone stacks using converted units or explicit raw values. Changing entry mode discards that field's draft and reloads its saved source value. Unchanged fields keep their exact raw rolls.")
            if (fit != null) LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
            else Text("Open a fit first.")
            if (model.loading) Text("Loading exact values.")
            if (model.editing) Text("Saving exact values.")
            model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("mutation-error")) }
            val details = model.current
            if (details != null) {
                if (details.items.isEmpty()) Text("No existing mutated modules or drone stacks in this fit.")
                for (row in details.items) key(details.fitId, details.revision, row.raw.objectKey) {
                    var representations by rememberSaveable(details.fitId, details.revision, row.raw.objectKey) {
                        mutableStateOf(row.attributes.map { it.initialRepresentation.wire }.toTypedArray())
                    }
                    var texts by rememberSaveable(details.fitId, details.revision, row.raw.objectKey) {
                        mutableStateOf(row.attributes.map { it.sourceValue(it.initialRepresentation).toString() }.toTypedArray())
                    }
                    Card(Modifier.fillMaxWidth().testTag("mutation-${row.raw.kind}-${row.raw.position}")) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(row.raw.name, style = MaterialTheme.typography.titleMedium)
                            Text("${row.raw.kind} ${row.raw.position + 1}; base ${row.raw.baseItemId}; mutaplasmid ${row.raw.mutaplasmidId}")
                            row.attributes.forEachIndexed { i, attribute ->
                                val representation = MutationValueRepresentation.entries.single { it.wire == representations[i] }
                                val display = attribute.display as? MutationDisplayValue.Available
                                fun selectRepresentation(next: MutationValueRepresentation) {
                                    if (next == representation) return
                                    // Reset from the returned metadata, never convert a local draft.
                                    representations = representations.copyOf().also { it[i] = next.wire }
                                    texts = texts.copyOf().also { it[i] = attribute.sourceValue(next).toString() }
                                }
                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    FilterChip(selected = representation == MutationValueRepresentation.DISPLAY,
                                        onClick = { selectRepresentation(MutationValueRepresentation.DISPLAY) },
                                        enabled = model.available && display != null, label = { Text("Converted") },
                                        modifier = Modifier.testTag("mutation-display-${row.raw.objectKey}-${attribute.raw.attributeId}"))
                                    FilterChip(selected = representation == MutationValueRepresentation.RAW,
                                        onClick = { selectRepresentation(MutationValueRepresentation.RAW) },
                                        enabled = model.available, label = { Text("Raw") },
                                        modifier = Modifier.testTag("mutation-raw-${row.raw.objectKey}-${attribute.raw.attributeId}"))
                                }
                                OutlinedTextField(value = texts[i], onValueChange = { value -> texts = texts.copyOf().also { it[i] = value } },
                                    enabled = model.available, singleLine = true,
                                    label = { Text(attribute.raw.label) },
                                    supportingText = {
                                        if (representation == MutationValueRepresentation.DISPLAY && display != null) {
                                            Text("${display.minimum} to ${display.maximum}; ${display.unitLabel.ifEmpty { "unitless" }}; ${if (display.higherIsBetter) "higher" else "lower"} is better")
                                        } else {
                                            Text("${attribute.raw.minimum} to ${attribute.raw.maximum}; raw unit ${attribute.raw.unitId ?: "none"}; ${if (attribute.raw.highIsGood) "higher" else "lower"} is better")
                                        }
                                    },
                                    modifier = Modifier.fillMaxWidth().testTag("mutation-value-${row.raw.objectKey}-${attribute.raw.attributeId}"))
                                (attribute.display as? MutationDisplayValue.Unavailable)?.let { unavailable ->
                                    Text("Converted entry unavailable: ${unavailable.reason} Raw entry remains available.",
                                        modifier = Modifier.testTag("mutation-display-unavailable-${row.raw.objectKey}-${attribute.raw.attributeId}"))
                                }
                            }
                            TextButton(onClick = {
                                texts = row.attributes.mapIndexed { i, attribute ->
                                    attribute.sourceValue(MutationValueRepresentation.entries.single { it.wire == representations[i] }).toString()
                                }.toTypedArray()
                            },
                                enabled = !model.editing) { Text("Discard this draft") }
                            Button(onClick = { model.save(context, details, row, texts.toList(), representations.toList()) }, enabled = model.available,
                                modifier = Modifier.testTag("mutation-save-${row.raw.objectKey}")) { Text("Save exact values") }
                        }
                    }
                }
            }
        } }
    }
}
