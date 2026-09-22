package io.github.sussic.pyfa

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers

@Composable
internal fun EmptyHullDialog(model: FitLibraryModel) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val catalog by EngineRuntime.catalog.collectAsState(context = Dispatchers.Main)
    val hull = model.newHull.value
    val name = model.name.value
    val busy = model.busy.value
    val query = model.newHullSearch.value.trim()
    val choices = catalog.hulls.filter { it.name.contains(query, ignoreCase = true) }.sortedBy { it.name.lowercase() }
    val pages = maxOf(1, (choices.size + 4) / 5)
    val page = model.newHullPage.value.coerceIn(0, pages - 1)
    val validName = name.isNotBlank() && name.codePointCount(0, name.length) <= 200 && name.none { it.code < 32 }
    AlertDialog(
        onDismissRequest = { if (!busy) model.action.value = null },
        title = { Text("New fit") },
        text = {
            Column(Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Empty fit · all skills V · no equipment or drones")
                Text("Hull: $hull", modifier = Modifier.testTag("empty-hull-selected"))
                OutlinedTextField(value = name, onValueChange = { model.name.value = it },
                    label = { Text("Fit name") }, singleLine = true, enabled = !busy,
                    modifier = Modifier.fillMaxWidth().testTag("empty-fit-name"))
                OutlinedTextField(value = model.newHullSearch.value, onValueChange = {
                    model.newHullSearch.value = it; model.newHullPage.value = 0
                }, label = { Text("Find ship or structure") }, singleLine = true, enabled = !busy,
                    modifier = Modifier.fillMaxWidth().testTag("empty-hull-search"))
                Text("${choices.size} hulls · Page ${page + 1} of $pages", modifier = Modifier.testTag("empty-hull-count"))
                if (choices.isEmpty()) Text("No matching hulls.", modifier = Modifier.testTag("empty-hull-no-results"))
                for (choice in choices.drop(page * 5).take(5)) TextButton(onClick = {
                    focus.clearFocus()
                    if (name == "New $hull" || name.isBlank()) model.name.value = "New ${choice.name}"
                    model.newHull.value = choice.name
                }, enabled = !busy, modifier = Modifier.fillMaxWidth().testTag("empty-hull-${choice.id}")) {
                    Text(choice.name + if (choice.name == hull) " · Selected" else "")
                }
                if (pages > 1) Row {
                    TextButton(onClick = { focus.clearFocus(); model.newHullPage.value = page - 1 },
                        enabled = !busy && page > 0, modifier = Modifier.testTag("empty-hull-previous")) { Text("Previous") }
                    TextButton(onClick = { focus.clearFocus(); model.newHullPage.value = page + 1 },
                        enabled = !busy && page + 1 < pages, modifier = Modifier.testTag("empty-hull-next")) { Text("Next") }
                }
                model.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("empty-hull-error")) }
            }
        },
        confirmButton = {
            TextButton(enabled = !busy && validName && catalog.hulls.any { it.name == hull },
                modifier = Modifier.testTag("empty-fit-confirm"), onClick = {
                    focus.clearFocus(); model.busy.value = true; model.error.value = null
                    EngineRuntime.createEmptyFit(context, hull, name).whenCompleteAsync({ response, failure ->
                        model.busy.value = false
                        model.error.value = failure?.let { "Could not create this fit. Try again." } ?: response?.error?.message
                        if (response?.isSuccess == true) {
                            model.action.value = null; model.search.value = ""; model.mode.value = "All fits"
                            response.fits.singleOrNull()?.let { EngineRuntime.selectFit(context, it.id) }
                        }
                    }, ContextCompat.getMainExecutor(context))
                }) { Text(if (busy) "Saving…" else "Create") }
        },
        dismissButton = {
            TextButton(enabled = !busy, onClick = { model.action.value = null; model.error.value = null },
                modifier = Modifier.testTag("empty-fit-cancel")) { Text("Cancel") }
        },
    )
}
