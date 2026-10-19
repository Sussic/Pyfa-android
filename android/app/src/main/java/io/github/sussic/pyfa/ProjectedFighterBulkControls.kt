package io.github.sussic.pyfa

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

/** Preserve captured selection order; the engine removes complete squadrons in descending captured position order. */
data class ProjectedFighterBulkSelection(val fitId: String, val revision: Long, val fitName: String,
    val rows: List<ProjectedFighterRow>) {
    fun wireRows(): List<ProjectedFighterSelectionRow> = OfflineFeatureCodec.frozen(rows.map { ProjectedFighterSelectionRow(it.index, it.objectKey) })
}

enum class ProjectedFighterBulkRangeMode { UNCHANGED, MIXED, VALUE, DEFAULT }
data class ProjectedFighterBulkRangeDraft(val selection: ProjectedFighterBulkSelection, val mixed: Boolean,
    val initial: String, val text: String, val mode: ProjectedFighterBulkRangeMode) {
    companion object {
        fun capture(selection: ProjectedFighterBulkSelection): ProjectedFighterBulkRangeDraft {
            require(selection.rows.isNotEmpty())
            val mixed = selection.rows.any { !ProjectedFitInputs.sameRange(it.rangeM, selection.rows.first().rangeM) }
            val text = if (mixed) "" else ProjectedFitInputs.rangeText(selection.rows.first().rangeM)
            return ProjectedFighterBulkRangeDraft(selection, mixed, text, text,
                if (mixed) ProjectedFighterBulkRangeMode.MIXED else ProjectedFighterBulkRangeMode.UNCHANGED)
        }
    }
}

@Composable
internal fun ProjectedFighterBulkControls(model: ProjectedFighterModel) {
    val context = LocalContext.current
    val selection = model.bulkSelection
    if (selection == null && model.currentDetails == null) return
    Card(Modifier.fillMaxWidth().testTag("projected-fighters-bulk")) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Selected incoming fighter squadrons", style = MaterialTheme.typography.titleMedium)
            Text("${selection?.rows?.size ?: 0} selected", Modifier.testTag("projected-fighters-bulk-count"))
            TextButton(onClick = model::selectBulkPage, enabled = model.canSelectBulk,
                modifier = Modifier.testTag("projected-fighters-bulk-select-page")) { Text("Select editable squadrons on this page") }
            if (selection != null) {
                Text("Captured from ${selection.fitName} · revision ${selection.revision}")
                val active = selection.rows.count { it.active }
                Text("$active active / ${selection.rows.size} selected squadrons", Modifier.testTag("projected-fighters-bulk-counts"))
                val mixed = selection.rows.any { !ProjectedFitInputs.sameRange(it.rangeM, selection.rows.first().rangeM) }
                Text("Selected ranges: ${if (mixed) "Mixed (not Default)" else selection.rows.first().rangeM?.let { "$it m" } ?: "Default"}",
                    Modifier.testTag("projected-fighters-bulk-ranges"))
                if (model.bulkStale) {
                    Text("The captured selection changed or is unavailable. Its identities and draft are retained. Review all current objects, or clear the selection; missing objects are never silently dropped.",
                        Modifier.testTag("projected-fighters-bulk-stale"), color = MaterialTheme.colorScheme.error)
                    TextButton(onClick = model::reviewBulk, enabled = model.canReviewBulk,
                        modifier = Modifier.testTag("projected-fighters-bulk-review")) { Text("Discard draft and review current selection") }
                }
                val draft = model.bulkDraft
                if (draft != null) {
                    OutlinedTextField(draft.text, model::changeBulkRange, enabled = !model.editing, singleLine = true,
                        label = { Text("Range for selected squadrons in km") }, modifier = Modifier.fillMaxWidth().testTag("projected-fighters-bulk-range-input"))
                    Text(when (draft.mode) {
                        ProjectedFighterBulkRangeMode.MIXED -> "Mixed captured ranges: enter a value or explicitly choose Default."
                        ProjectedFighterBulkRangeMode.DEFAULT -> "Default selected: all selected ranges will use the engine default."
                        else -> "Zero is explicit zero metres. Unchanged uniform text preserves the exact captured range."
                    }, Modifier.testTag("projected-fighters-bulk-range-mode"))
                    TextButton(onClick = model::defaultBulkRange, enabled = !model.editing,
                        modifier = Modifier.testTag("projected-fighters-bulk-range-default")) { Text("Use Default for all selected") }
                    Button(onClick = { model.saveBulkRange(context) }, enabled = model.available && !model.bulkStale && draft.mode != ProjectedFighterBulkRangeMode.MIXED,
                        modifier = Modifier.testTag("projected-fighters-bulk-range-save")) { Text("Apply selected ranges together") }
                    TextButton(onClick = model::discardBulkRange, enabled = !model.editing,
                        modifier = Modifier.testTag("projected-fighters-bulk-range-discard")) { Text("Discard selected range draft") }
                } else {
                    Text("Activation changes squadron states only. Abilities are separate; range and recipient immunity can prevent their effects.",
                        Modifier.testTag("projected-fighters-bulk-activation-policy"))
                    for (active in listOf(true, false)) TextButton(onClick = { model.bulkActive(context, selection, active) },
                        enabled = model.canBulk(selection), modifier = Modifier.testTag("projected-fighters-bulk-active-$active")) {
                        Text(if (active) "Activate selected squadrons" else "Deactivate selected squadrons")
                    }
                    val main = model.capturedBulkMain
                    if (main == null) Text("Choose a selected squadron below as the main for ability toggles.", Modifier.testTag("projected-fighters-bulk-main"))
                    else {
                        Text("Ability main: ${main.index + 1} · ${main.name}", Modifier.testTag("projected-fighters-bulk-main"))
                        Text("The main ability determines one shared direction. Matching abilities are set to that state; selected squadrons without the ability stay unchanged. Inactive squadrons retain ability edits.",
                            Modifier.testTag("projected-fighters-bulk-ability-policy"))
                        if (model.optionsLoading) Text("Loading main squadron abilities…")
                        model.optionsError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                        TextButton(onClick = { model.selectBulkMain(context, main) }, enabled = model.canBulk(selection) && !model.optionsLoading,
                            modifier = Modifier.testTag("projected-fighters-bulk-main-load")) { Text("Load main squadron abilities") }
                        model.bulkMainOptions?.let { options ->
                            val anchor = model.anchor(main)!!
                            for (ability in options.abilities) TextButton(
                                onClick = { model.bulkAbility(context, selection, anchor, options, ability) }, enabled = model.canBulk(selection),
                                modifier = Modifier.testTag("projected-fighters-bulk-ability-${ability.effectId}")) {
                                Text("${if (ability.active) "Disable" else "Enable"} ${ability.name} on selected squadrons with this ability")
                            }
                        }
                    }
                    TextButton(onClick = { model.beginBulkRange(selection) }, enabled = model.canBulk(selection),
                        modifier = Modifier.testTag("projected-fighters-bulk-range-edit")) { Text("Edit selected ranges") }
                    TextButton(onClick = { model.removeBulk(context, selection) }, enabled = model.canBulk(selection),
                        modifier = Modifier.testTag("projected-fighters-bulk-remove")) { Text("Remove complete selected squadrons together") }
                }
                TextButton(onClick = model::clearBulk, enabled = !model.editing,
                    modifier = Modifier.testTag("projected-fighters-bulk-clear")) { Text("Clear selection and its draft") }
            }
        }
    }
}
