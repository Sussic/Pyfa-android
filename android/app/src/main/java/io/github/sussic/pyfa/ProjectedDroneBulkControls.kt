package io.github.sussic.pyfa

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

/** Preserve captured selection order; the engine removes complete stacks by stable item identity. */
data class ProjectedDroneBulkSelection(val fitId: String, val revision: Long, val fitName: String,
    val rows: List<ProjectedDroneRow>) {
    fun wireRows(): List<ProjectedDroneSelectionRow> = OfflineFeatureCodec.frozen(rows.map { ProjectedDroneSelectionRow(it.index, it.objectKey) })
}

enum class ProjectedDroneBulkRangeMode { UNCHANGED, MIXED, VALUE, DEFAULT }
data class ProjectedDroneBulkRangeDraft(val selection: ProjectedDroneBulkSelection, val mixed: Boolean,
    val initial: String, val text: String, val mode: ProjectedDroneBulkRangeMode) {
    companion object {
        fun capture(selection: ProjectedDroneBulkSelection): ProjectedDroneBulkRangeDraft {
            require(selection.rows.isNotEmpty())
            val mixed = selection.rows.any { !ProjectedFitInputs.sameRange(it.rangeM, selection.rows.first().rangeM) }
            val text = if (mixed) "" else ProjectedFitInputs.rangeText(selection.rows.first().rangeM)
            return ProjectedDroneBulkRangeDraft(selection, mixed, text, text,
                if (mixed) ProjectedDroneBulkRangeMode.MIXED else ProjectedDroneBulkRangeMode.UNCHANGED)
        }
    }
}

@Composable
internal fun ProjectedDroneBulkControls(model: ProjectedDroneModel) {
    val context = LocalContext.current
    val selection = model.bulkSelection
    if (selection == null && model.currentDetails == null) return
    Card(Modifier.fillMaxWidth().testTag("projected-drones-bulk")) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Selected incoming drone stacks", style = MaterialTheme.typography.titleMedium)
            Text("${selection?.rows?.size ?: 0} selected", Modifier.testTag("projected-drones-bulk-count"))
            TextButton(onClick = model::selectBulkPage, enabled = model.canSelectBulk,
                modifier = Modifier.testTag("projected-drones-bulk-select-page")) { Text("Select editable stacks on this page") }
            if (selection != null) {
                Text("Captured from ${selection.fitName} · revision ${selection.revision}")
                val active = selection.rows.sumOf { it.active.toLong() }
                val total = selection.rows.sumOf { it.amount.toLong() }
                val partial = selection.rows.count { it.active in 1 until it.amount }
                Text("$active active / $total total across selected stacks · $partial partially active", Modifier.testTag("projected-drones-bulk-counts"))
                val mixed = selection.rows.any { !ProjectedFitInputs.sameRange(it.rangeM, selection.rows.first().rangeM) }
                Text("Selected ranges: ${if (mixed) "Mixed (not Default)" else selection.rows.first().rangeM?.let { "$it m" } ?: "Default"}",
                    Modifier.testTag("projected-drones-bulk-ranges"))
                if (model.bulkStale) {
                    Text("The captured selection changed or is unavailable. Its identities and draft are retained. Review all current objects, or clear the selection; missing objects are never silently dropped.",
                        Modifier.testTag("projected-drones-bulk-stale"), color = MaterialTheme.colorScheme.error)
                    TextButton(onClick = model::reviewBulk, enabled = model.canReviewBulk,
                        modifier = Modifier.testTag("projected-drones-bulk-review")) { Text("Discard draft and review current selection") }
                }
                val draft = model.bulkDraft
                if (draft != null) {
                    OutlinedTextField(draft.text, model::changeBulkRange, enabled = !model.editing, singleLine = true,
                        label = { Text("Range for selected stacks in km") }, modifier = Modifier.fillMaxWidth().testTag("projected-drones-bulk-range-input"))
                    Text(when (draft.mode) {
                        ProjectedDroneBulkRangeMode.MIXED -> "Mixed captured ranges: enter a value or explicitly choose Default."
                        ProjectedDroneBulkRangeMode.DEFAULT -> "Default selected: all selected ranges will use the engine default."
                        else -> "Zero is explicit zero metres. Unchanged uniform text preserves the exact captured range."
                    }, Modifier.testTag("projected-drones-bulk-range-mode"))
                    TextButton(onClick = model::defaultBulkRange, enabled = !model.editing,
                        modifier = Modifier.testTag("projected-drones-bulk-range-default")) { Text("Use Default for all selected") }
                    Button(onClick = { model.saveBulkRange(context) }, enabled = model.available && !model.bulkStale && draft.mode != ProjectedDroneBulkRangeMode.MIXED,
                        modifier = Modifier.testTag("projected-drones-bulk-range-save")) { Text("Apply selected ranges together") }
                    TextButton(onClick = model::discardBulkRange, enabled = !model.editing,
                        modifier = Modifier.testTag("projected-drones-bulk-range-discard")) { Text("Discard selected range draft") }
                } else {
                    Text("Activate leaves already-active partial stacks partial and recipient-blocked inactive stacks unchanged. Deactivate sets active counts to zero. Review each refreshed stack; only an unchanged complete saved graph adds no history.",
                        Modifier.testTag("projected-drones-bulk-activation-policy"))
                    for (active in listOf(true, false)) TextButton(onClick = { model.bulkActive(context, selection, active) },
                        enabled = model.canBulk(selection), modifier = Modifier.testTag("projected-drones-bulk-active-$active")) {
                        Text(if (active) "Activate selected stacks" else "Deactivate selected stacks")
                    }
                    TextButton(onClick = { model.beginBulkRange(selection) }, enabled = model.canBulk(selection),
                        modifier = Modifier.testTag("projected-drones-bulk-range-edit")) { Text("Edit selected ranges") }
                    TextButton(onClick = { model.removeBulk(context, selection) }, enabled = model.canBulk(selection),
                        modifier = Modifier.testTag("projected-drones-bulk-remove")) { Text("Remove complete selected stacks together") }
                }
                TextButton(onClick = model::clearBulk, enabled = !model.editing,
                    modifier = Modifier.testTag("projected-drones-bulk-clear")) { Text("Clear selection and its draft") }
            }
        }
    }
}
