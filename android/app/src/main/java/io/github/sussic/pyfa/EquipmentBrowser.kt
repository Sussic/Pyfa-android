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
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.LaunchedEffect
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

class EquipmentModel : ViewModel() {
    var catalog by mutableStateOf<EquipmentCatalog?>(null)
    var busy by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)
    var query by mutableStateOf("")
    var searched by mutableStateOf<String?>(null)
    var results by mutableStateOf<List<Int>>(emptyList())
    var groupId by mutableStateOf<Int?>(null)
    var selectedId by mutableStateOf<Int?>(null)
    var metas by mutableStateOf(EquipmentCatalog.metas.toSet())
    var page by mutableStateOf(0)
    var showRecent by mutableStateOf(false)
    fun load(context: Context) {
        if (catalog != null || busy) return
        busy = true
        EngineRuntime.equipmentCatalog(context).whenCompleteAsync({ value, failure ->
            busy = false
            if (failure == null) { catalog = value; error = null }
            else error = "Equipment could not be loaded. Try again."
        }, ContextCompat.getMainExecutor(context))
    }
    fun search(context: Context) {
        if (busy) return
        if (query.isBlank()) { group(groupId); return }
        busy = true
        val submitted = query
        EngineRuntime.searchEquipment(context, submitted).whenCompleteAsync({ ids, failure ->
            busy = false
            if (failure == null) {
                results = ids; searched = submitted; selectedId = null; page = 0; error = null; showRecent = false
            } else error = "Search could not be completed. Try again."
        }, ContextCompat.getMainExecutor(context))
    }
    fun group(id: Int?) {
        groupId = id; searched = null; query = ""; selectedId = null; page = 0; error = null; showRecent = false
    }
}

@Composable
internal fun EquipmentBrowser(model: EquipmentModel, moduleModel: ModuleEditorModel, onBack: () -> Unit, onViewFit: () -> Unit, onCharges: () -> Unit) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val recent by EngineRuntime.recent.collectAsState(context = Dispatchers.Main)
    val selectedCard = remember { BringIntoViewRequester() }
    LaunchedEffect(model.selectedId) { if (model.selectedId != null) selectedCard.bringIntoView() }
    LaunchedEffect(Unit) { model.load(context) }
    fun back() {
        focus.clearFocus()
        when {
            model.selectedId != null -> model.selectedId = null
            model.showRecent -> model.group(null)
            model.searched != null -> model.group(model.groupId)
            model.groupId != null -> model.group(model.catalog?.groupById?.get(model.groupId)?.parentId)
            else -> onBack()
        }
    }
    BackHandler { back() }
    Text("Equipment", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { back() }, modifier = Modifier.testTag("equipment-back")) { Text("Back") }
    Text("Browse bundled items, variants and charges offline.")
    model.error?.let {
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("equipment-error"))
        if (model.catalog == null) Button(onClick = { model.load(context) }, enabled = !model.busy) { Text("Retry") }
    }
    if (model.busy) Text("Loading equipment…", modifier = Modifier.testTag("equipment-loading"))
    val catalog = model.catalog ?: return
    OutlinedTextField(value = model.query, onValueChange = { model.query = it },
        label = { Text("Search equipment") }, singleLine = true,
        modifier = Modifier.fillMaxWidth().testTag("equipment-search"))
    Text("Use words, * or ? wildcards, common abbreviations, or re: for a regular expression.", style = MaterialTheme.typography.bodySmall)
    Row {
        Button(onClick = { focus.clearFocus(); model.search(context) }, enabled = !model.busy,
            modifier = Modifier.testTag("equipment-search-submit")) { Text("Search") }
        TextButton(onClick = { focus.clearFocus(); model.group(null) }, enabled = !model.busy,
            modifier = Modifier.testTag("equipment-root")) { Text("All groups") }
    }
    TextButton(onClick = {
        focus.clearFocus(); model.group(null); model.showRecent = true; model.metas = EquipmentCatalog.metas.toSet()
    }, enabled = !model.busy, modifier = Modifier.testTag("equipment-recent")) { Text("Recent use (${recent.size})") }
    TextButton(onClick = { focus.clearFocus(); onCharges() }, modifier = Modifier.testTag("equipment-charges")) {
        Text("Charges for active fit")
    }
    for (pair in EquipmentCatalog.metas.chunked(2)) Row {
        for (meta in pair) Row(Modifier.weight(1f)) {
            Checkbox(checked = meta in model.metas, onCheckedChange = {
                model.metas = if (it) model.metas + meta else model.metas - meta
                model.page = 0
            }, modifier = Modifier.testTag("equipment-meta-$meta"))
            Text(meta, modifier = Modifier.padding(top = 12.dp))
        }
    }
    val selected = catalog.itemById[model.selectedId]
    selected?.let { item ->
        Card(Modifier.fillMaxWidth().bringIntoViewRequester(selectedCard).testTag("equipment-selected")) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(item.name, style = MaterialTheme.typography.titleMedium)
                Text("${item.category} · ${item.meta}")
                EquipmentFittingActions(moduleModel, item, onViewFit)
                catalog.itemById[item.parentId]?.takeIf { it.id != item.id }?.let { Text("Variation of ${it.name}") }
                val group = catalog.groupById[item.marketGroupId]
                if (group == null) Text("This item has no visible market group.") else TextButton(onClick = {
                    focus.clearFocus(); model.group(group.id); model.metas = setOf(item.meta)
                    model.selectedId = item.id
                }, enabled = !model.busy, modifier = Modifier.testTag("equipment-jump")) { Text("Show market group") }
            }
        }
    }
    if (model.showRecent) Text("Recent use · newest first", modifier = Modifier.testTag("equipment-location"))
    else if (model.searched != null) Text("Results for “${model.searched}” · up to 100 matches", modifier = Modifier.testTag("equipment-location"))
    else {
        val path = model.groupId?.let { catalog.path(it).joinToString(" › ") { group -> group.name } } ?: "All equipment groups"
        Text(path, modifier = Modifier.testTag("equipment-location"))
        for (group in catalog.children(model.groupId)) {
            TextButton(onClick = { focus.clearFocus(); model.group(group.id) }, enabled = !model.busy,
                modifier = Modifier.fillMaxWidth().testTag("equipment-group-${group.id}")) { Text(group.name) }
        }
    }
    val ids = if (model.showRecent) recent else if (model.searched != null) model.results else catalog.groupById[model.groupId]?.itemIds.orEmpty()
    val filtered = ids.mapNotNull { catalog.itemById[it] }.filter { it.meta in model.metas }
    val rows = if (model.showRecent) filtered else filtered.sortedWith(compareBy<EquipmentItem> { it.name.lowercase() }.thenBy { it.id })
    val size = 20
    val pages = maxOf(1, (rows.size + size - 1) / size)
    val page = model.page.coerceIn(0, pages - 1)
    Text("${rows.size} items · Page ${page + 1} of $pages", modifier = Modifier.testTag("equipment-count"))
    if (rows.isEmpty() && (model.showRecent || model.searched != null || model.groupId != null && catalog.children(model.groupId).isEmpty())) {
        Text(if (model.showRecent) "No recently used items match these filters. Add, replace or remove equipment to build this list."
            else "No matching items. Change the search or meta filters.", modifier = Modifier.testTag("equipment-empty"))
    }
    for (item in rows.drop(page * size).take(size)) {
        TextButton(onClick = { focus.clearFocus(); model.selectedId = item.id }, enabled = !model.busy,
            modifier = Modifier.fillMaxWidth().testTag("equipment-item-${item.id}")) { Text("${item.name} · ${item.meta}") }
    }
    if (pages > 1) Row {
        TextButton(onClick = { model.page = page - 1 }, enabled = page > 0,
            modifier = Modifier.testTag("equipment-previous")) { Text("Previous") }
        TextButton(onClick = { model.page = page + 1 }, enabled = page + 1 < pages,
            modifier = Modifier.testTag("equipment-next")) { Text("Next") }
    }
}
