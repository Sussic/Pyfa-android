package io.github.sussic.pyfa

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

@Composable
internal fun ProjectedModuleChargeControls(model: ProjectedModuleModel) {
    if (model.bulkSelection == null && model.chargeMainKey == null) return
    val context = LocalContext.current
    Card(Modifier.fillMaxWidth().testTag("projected-module-bulk-charges")) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Selected charges and scripts", style = MaterialTheme.typography.titleMedium)
            Text("Select modules, then choose one selected module as the charge reference. Only its compatible charges are offered.")
            val main = model.chargeMain
            Text(main?.let { "Reference: ${it.index + 1} · ${it.name}" } ?: "Choose or review the selected reference module.",
                Modifier.testTag("projected-charge-main"))
            if (model.draft != null || model.bulkDraft != null) Text("Your range draft is retained. Finish or discard it before previewing charges.",
                Modifier.testTag("projected-charge-range-blocked"))
            for (scope in BulkScope.entries) TextButton(onClick = { model.chooseChargeScope(scope) }, enabled = model.canConfigureCharges,
                modifier = Modifier.testTag("projected-charge-scope-${scope.name}")) {
                Text((if(scope==BulkScope.SELECTED) "Selection only" else "All similar") + if(model.chargeScope==scope) " · selected" else "")
            }
            Text(if (model.chargeScope == BulkScope.SELECTED)
                "Selection only uses complete compatible-charge-set subset filtering. A candidate may still skip the chosen charge."
                else "All similar resolves the full incoming list, including off-page modules. A read-only environment match makes this scope unavailable.")
            Text("Chosen charge: ${model.chargeId?.let { id -> model.chargeChoices.singleOrNull { it.id==id }?.name ?: "ID $id (refresh choices)" } ?: "Clear charges"}",
                Modifier.testTag("projected-charge-choice"))
            TextButton(onClick = { model.chooseBulkCharge(null) }, enabled = model.canConfigureCharges,
                modifier = Modifier.testTag("projected-charge-clear")) { Text("Clear charges") }
            var query by rememberSaveable(model.chargeMainKey) { mutableStateOf("") }
            var choicePage by rememberSaveable(model.chargeMainKey,query) { mutableStateOf(0) }
            OutlinedTextField(query,{query=it.take(200)},singleLine=true,label={Text("Search charges and scripts")},
                modifier=Modifier.fillMaxWidth().testTag("projected-charge-search"))
            val matches=model.chargeChoices.filter { it.name.contains(query.trim(),true) }
            val last=(matches.size-1).coerceAtLeast(0)/25; val page=choicePage.coerceAtMost(last)
            Text("${matches.size} choices · page ${page+1} of ${last+1}")
            for (choice in matches.drop(page*25).take(25)) TextButton(onClick={model.chooseBulkCharge(choice.id)},
                enabled=model.canConfigureCharges,modifier=Modifier.testTag("projected-charge-choice-${choice.id}")) { Text(choice.name) }
            if(last>0) Row {
                TextButton(onClick={choicePage=page-1},enabled=page>0,modifier=Modifier.testTag("projected-charge-previous")) { Text("Previous charges") }
                TextButton(onClick={choicePage=page+1},enabled=page<last,modifier=Modifier.testTag("projected-charge-next")) { Text("Next charges") }
            }
            Button(onClick={model.refreshChargePreview(context)},enabled=model.canPreviewCharges,
                modifier=Modifier.testTag("projected-charge-refresh")) { Text("Refresh charge preview") }
            if(model.chargeLoading) Text("Checking the captured charge scope…",Modifier.testTag("projected-charge-loading"))
            model.chargeError?.let { Text(it,Modifier.testTag("projected-charge-error"),color=MaterialTheme.colorScheme.error) }
            val preview=model.currentChargePreview
            if(preview==null) Text("Refresh the preview after changing the scope, charge or selection. No charge edit has been submitted.",Modifier.testTag("projected-charge-needs-preview"))
            else {
                preview.unavailableReason?.let { Text(it,Modifier.testTag("projected-charge-unavailable"),color=MaterialTheme.colorScheme.error) }
                val changes=preview.targets.count { it.status==ProjectedChargeStatus.CHANGE }
                Text("${preview.selection.size} selected · ${preview.targets.size} resolved · $changes changes · ${preview.excluded.size} excluded",
                    Modifier.testTag("projected-charge-summary"))
                if(changes==0) Text("No charge changes in this preview. No edit will be added to history.",Modifier.testTag("projected-charge-unchanged"))
                var previewPage by rememberSaveable(preview.fitId,preview.revision,preview.main.objectKey,preview.scope,preview.chargeId) { mutableStateOf(0) }
                val display=preview.targets.map { "${it.identity.index+1} · ${it.name} · ${it.chargeName ?: "Empty"} → ${it.status.name.lowercase()}" } +
                    preview.excluded.map { "${it.identity.index+1} · excluded: ${it.reason}" }
                val final=(display.size-1).coerceAtLeast(0)/25; val current=previewPage.coerceAtMost(final)
                for((offset,line) in display.drop(current*25).take(25).withIndex()) Text(line,Modifier.testTag("projected-charge-preview-${current*25+offset}"))
                if(final>0) Row {
                    TextButton(onClick={previewPage=current-1},enabled=current>0,modifier=Modifier.testTag("projected-charge-preview-previous")) { Text("Previous preview rows") }
                    TextButton(onClick={previewPage=current+1},enabled=current<final,modifier=Modifier.testTag("projected-charge-preview-next")) { Text("Next preview rows") }
                }
                Button(onClick={model.applyCharges(context,preview)},enabled=model.canApplyCharges,
                    modifier=Modifier.testTag("projected-charge-apply")) { Text("Apply previewed charge changes together") }
            }
        }
    }
}
