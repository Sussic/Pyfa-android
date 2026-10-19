package io.github.sussic.pyfa

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

/** Row order is user selection order; only the engine reverses removal positions. */
data class ProjectedModuleBulkSelection(val fitId: String, val revision: Long, val fitName: String,
    val rows: List<ProjectedModuleRow>) {
    fun wireRows(): List<ProjectedModuleSelectionRow> = OfflineFeatureCodec.frozen(rows.map { ProjectedModuleSelectionRow(it.index, it.objectKey) })
}

enum class ProjectedModuleBulkRangeMode { UNCHANGED, MIXED, VALUE, DEFAULT }
data class ProjectedModuleBulkRangeDraft(val selection: ProjectedModuleBulkSelection, val mixed: Boolean,
    val initial: String, val text: String, val mode: ProjectedModuleBulkRangeMode) {
    companion object {
        fun capture(selection: ProjectedModuleBulkSelection): ProjectedModuleBulkRangeDraft {
            require(selection.rows.isNotEmpty())
            val mixed = selection.rows.any { !ProjectedFitInputs.sameRange(it.rangeM, selection.rows.first().rangeM) }
            val text = if (mixed) "" else ProjectedFitInputs.rangeText(selection.rows.first().rangeM)
            return ProjectedModuleBulkRangeDraft(selection, mixed, text, text,
                if (mixed) ProjectedModuleBulkRangeMode.MIXED else ProjectedModuleBulkRangeMode.UNCHANGED)
        }
    }
}

@Composable
internal fun ProjectedModuleBulkControls(model: ProjectedModuleModel) {
    val context = LocalContext.current
    val selection = model.bulkSelection
    if (selection == null && model.currentDetails == null) return
    Card(Modifier.fillMaxWidth().testTag("projected-modules-bulk")) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Selected projected modules", style = MaterialTheme.typography.titleMedium)
            Text("${selection?.rows?.size ?: 0} selected", Modifier.testTag("projected-modules-bulk-count"))
            TextButton(onClick = model::selectBulkPage, enabled = model.canSelectBulk,
                modifier = Modifier.testTag("projected-modules-bulk-select-page")) { Text("Select editable modules on this page") }
            if (selection != null) {
                Text("Captured from ${selection.fitName} · revision ${selection.revision}")
                val states = selection.rows.map { it.state }.distinct()
                Text("Selected states: ${if (states.size == 1) states.single().name else "Mixed"}", Modifier.testTag("projected-modules-bulk-states"))
                val mixed = selection.rows.any { !ProjectedFitInputs.sameRange(it.rangeM, selection.rows.first().rangeM) }
                Text("Selected ranges: ${if (mixed) "Mixed (not Default)" else selection.rows.first().rangeM?.let { "$it m" } ?: "Default"}",
                    Modifier.testTag("projected-modules-bulk-ranges"))
                if (model.bulkStale) {
                    Text("The captured selection changed or is unavailable. Its identities and draft are retained. Review all current objects, or clear the selection; missing objects are never silently dropped.",
                        Modifier.testTag("projected-modules-bulk-stale"), color = MaterialTheme.colorScheme.error)
                    TextButton(onClick = model::reviewBulk, enabled = model.canReviewBulk,
                        modifier = Modifier.testTag("projected-modules-bulk-review")) { Text("Discard draft and review current selection") }
                }
                val draft = model.bulkDraft
                if (draft != null) {
                    OutlinedTextField(draft.text, model::changeBulkRange, enabled = !model.editing, singleLine = true,
                        label = { Text("Range for selected modules in km") }, modifier = Modifier.fillMaxWidth().testTag("projected-modules-bulk-range-input"))
                    Text(when (draft.mode) {
                        ProjectedModuleBulkRangeMode.MIXED -> "Mixed captured ranges: enter a value or explicitly choose Default."
                        ProjectedModuleBulkRangeMode.DEFAULT -> "Default selected: all selected ranges will use the engine default."
                        else -> "Zero is explicit zero metres. Unchanged uniform text preserves the exact captured range."
                    }, Modifier.testTag("projected-modules-bulk-range-mode"))
                    TextButton(onClick = model::defaultBulkRange, enabled = !model.editing,
                        modifier = Modifier.testTag("projected-modules-bulk-range-default")) { Text("Use Default for all selected") }
                    Button(onClick = { model.saveBulkRange(context) }, enabled = model.available && !model.bulkStale && draft.mode != ProjectedModuleBulkRangeMode.MIXED,
                        modifier = Modifier.testTag("projected-modules-bulk-range-save")) { Text("Apply selected ranges together") }
                    TextButton(onClick = model::discardBulkRange, enabled = !model.editing,
                        modifier = Modifier.testTag("projected-modules-bulk-range-discard")) { Text("Discard selected range draft") }
                } else {
                    Text("EOS chooses each module's supported state and reconciles other affected objects. Only an unchanged complete saved graph adds no history.")
                    for (state in ProjectedModuleStateAction.entries) TextButton(onClick = { model.bulkState(context, selection, state) },
                        enabled = model.canBulk(selection), modifier = Modifier.testTag("projected-modules-bulk-state-${state.wire}")) {
                        Text(when (state) { ProjectedModuleStateAction.INACTIVE -> "Make selected inactive"; ProjectedModuleStateAction.ACTIVE -> "Make selected active"; ProjectedModuleStateAction.OVERHEAT -> "Overheat selected" })
                    }
                    TextButton(onClick = { model.beginBulkRange(selection) }, enabled = model.canBulk(selection),
                        modifier = Modifier.testTag("projected-modules-bulk-range-edit")) { Text("Edit selected ranges") }
                    TextButton(onClick = { model.removeBulk(context, selection) }, enabled = model.canBulk(selection),
                        modifier = Modifier.testTag("projected-modules-bulk-remove")) { Text("Remove selected projectors together") }
                }
                TextButton(onClick = model::clearBulk, enabled = !model.editing,
                    modifier = Modifier.testTag("projected-modules-bulk-clear")) { Text("Clear selection and its draft") }
            }
        }
    }
}
