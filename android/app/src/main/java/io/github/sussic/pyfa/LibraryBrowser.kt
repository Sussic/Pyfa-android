package io.github.sussic.pyfa

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

@Composable
internal fun OpenFits() {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val fits by EngineRuntime.library.collectAsState()
    val navigation by EngineRuntime.navigation.collectAsState()
    val error by EngineRuntime.navigationError.collectAsState()
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Open fits", style = MaterialTheme.typography.titleLarge)
        if (navigation.openIds.isEmpty()) Text("No open fits. Open a saved fit below.", modifier = Modifier.testTag("no-open-fits"))
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).testTag("open-fit-tabs"), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            for (id in navigation.openIds) {
                val fit = fits.find { it.id == id } ?: continue
                Card(Modifier.widthIn(max = 240.dp).testTag("tab-$id")) {
                    Column(Modifier.padding(8.dp)) {
                        TextButton(onClick = { focus.clearFocus(); EngineRuntime.selectFit(context, id) }, modifier = Modifier.testTag("switch-$id")) {
                            Text(fit.name + if (navigation.activeId == id) " · Active" else "")
                        }
                        TextButton(onClick = { focus.clearFocus(); EngineRuntime.navigate(context) { it.close(id) } }, modifier = Modifier.testTag("close-$id")) {
                            Text("Close")
                        }
                    }
                }
            }
        }
        if (navigation.openIds.isNotEmpty()) TextButton(onClick = {
            focus.clearFocus()
            EngineRuntime.navigate(context) { it.copy(openIds = emptyList(), activeId = null) }
        }, modifier = Modifier.testTag("close-all")) { Text("Close all fits") }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Checkbox(navigation.restore, onCheckedChange = { value -> EngineRuntime.navigate(context) { it.copy(restore = value) } },
                modifier = Modifier.testTag("restore-open-fits"))
            Text("Reopen previous fits on startup")
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("navigation-error")) }
    }
}

@Composable
internal fun LibraryBrowser(model: FitLibraryModel, fits: List<FitSnapshot>) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val catalog by EngineRuntime.catalog.collectAsState()
    val navigation by EngineRuntime.navigation.collectAsState()
    val mode by model.mode
    val groupId by model.groupId
    val hullName by model.hullName
    val races by model.races
    val searching = model.search.value.isNotBlank()
    fun back() {
        if (hullName != null) model.hullName.value = null else model.groupId.value = null
    }
    BackHandler(enabled = mode == "Hulls" && groupId != null && !searching && model.action.value == null) { back() }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        for (choice in listOf("All fits", "Hulls", "Recent")) {
            FilterChip(selected = mode == choice, onClick = { focus.clearFocus(); model.mode.value = choice; model.search.value = "" },
                label = { Text(choice) }, modifier = Modifier.testTag("mode-$choice"))
        }
    }
    if (searching) return // Search always spans the entire saved library.
    if (mode == "Recent") {
        Text("Recently modified · up to 50 fits. Opening a fit does not move it here.", style = MaterialTheme.typography.bodySmall)
        if (EngineRuntime.modified.collectAsState().value.values.any { it == 0L }) {
            Text("Fits saved by an earlier build have no recorded edit order and appear last.", style = MaterialTheme.typography.bodySmall)
        }
        return
    }
    if (mode != "Hulls") return
    val counts = fits.groupingBy { it.ship }.eachCount()
    val group = catalog.groups.find { it.id == groupId }
    if (group != null) TextButton(onClick = { back() }, modifier = Modifier.testTag("hull-back")) {
        Text(if (hullName == null) "Back to hull groups" else "Back to ${group.name}")
    }
    if (hullName != null) {
        Text(hullName!!, style = MaterialTheme.typography.titleMedium, modifier = Modifier.testTag("hull-title"))
        if (counts[hullName] == null) Text("No saved fits for this hull. New fits currently use the three example hulls.")
        return
    }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Checkbox(navigation.hideEmpty, onCheckedChange = { value -> EngineRuntime.navigate(context) { it.copy(hideEmpty = value) } },
            modifier = Modifier.testTag("hide-empty"))
        Text("Hide groups and hulls without fits")
    }
    if (group == null) {
        val shown = catalog.groups.filter { item -> !navigation.hideEmpty || catalog.hulls.any { it.groupId == item.id && (counts[it.name] ?: 0) > 0 } }
        if (shown.isEmpty()) Text("No groups contain saved fits.")
        for (item in shown) {
            val count = catalog.hulls.filter { it.groupId == item.id }.sumOf { counts[it.name] ?: 0 }
            TextButton(onClick = { model.groupId.value = item.id; model.races.value = emptySet() }, modifier = Modifier.testTag("group-${item.id}")) {
                Text("${item.name} · $count fits")
            }
        }
    } else {
        Text(group.name, style = MaterialTheme.typography.titleMedium)
        val hulls = catalog.hulls.filter { it.groupId == group.id }
        val available = hulls.mapNotNull { it.race }.distinct().sorted()
        Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).testTag("race-filters"), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(selected = races.isEmpty(), onClick = { model.races.value = emptySet() }, label = { Text("All races") }, modifier = Modifier.testTag("race-all"))
            for (race in available) FilterChip(selected = race in races, onClick = {
                model.races.value = if (race in races) races - race else races + race
            }, label = { Text(race.replaceFirstChar { it.uppercase() }) }, modifier = Modifier.testTag("race-$race"))
        }
        val shown = hulls.filter { (!navigation.hideEmpty || (counts[it.name] ?: 0) > 0) &&
            (races.isEmpty() || it.race == null || it.race in races) }.sortedBy { it.name }
        if (shown.isEmpty()) Text("No hulls match these filters.")
        for (hull in shown) TextButton(onClick = { model.hullName.value = hull.name }, modifier = Modifier.testTag("hull-${hull.id}")) {
            Text("${hull.name} · ${counts[hull.name] ?: 0} fits")
        }
    }
}
