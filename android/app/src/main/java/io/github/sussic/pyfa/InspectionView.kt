package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

class InspectionModel : ViewModel() {
    var options by mutableStateOf<InspectionOptions?>(null); private set
    var details by mutableStateOf<ItemInspection?>(null); private set
    var loading by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    private var optionRequest: Pair<String, Long>? = null
    private var detailRequest: List<Any?>? = null
    private var optionGeneration = 0
    private var generation = 0
    fun options(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && optionRequest == next) return
        optionRequest = next; options = null
        val token = ++optionGeneration
        EngineRuntime.inspectionOptions(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == optionGeneration) {
                if (failure == null) options = value else error = "Inspection targets could not be loaded. Try again."
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun load(context: Context, fit: FitSnapshot?, target: InspectionTarget, effective: Boolean, retry: Boolean = false) {
        val next = listOf(if (target.context == "base") null else fit?.id,
            if (target.context == "base") null else fit?.revision, target, effective)
        if (!retry && detailRequest == next) return
        detailRequest = next; details = null; error = null; loading = true
        val token = ++generation
        EngineRuntime.inspectionDetails(context, fit?.id, target, effective).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure == null) details = value else error = "This inspection item may have changed or been removed. Choose it again or retry."
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

internal fun InspectionValue.plain(absentLabel: String = "Unavailable"): String = when (this) {
    InspectionValue.Absent -> absentLabel
    is InspectionValue.Scalar -> when (val scalar = value) {
        is StatValue.BooleanValue -> if (scalar.value) "Yes" else "No"
        else -> scalar.raw.toString()
    }
    is InspectionValue.Sequence -> values.joinToString("\n") { it.plain(absentLabel) }.ifEmpty { "None" }
    is InspectionValue.Fields -> if (values.keys == setOf("number_kind")) {
        when (val kind = values.getValue("number_kind").plain()) {
            "positive_infinity" -> "∞"
            "negative_infinity" -> "−∞"
            else -> "number_kind: $kind"
        }
    } else values.entries.joinToString("\n") { (key, value) -> "$key: ${value.plain(absentLabel)}" }.ifEmpty { "None" }
}
private fun InspectionValue.Fields.field(name: String): InspectionValue = values.getValue(name)
private fun InspectionValue.Fields.text(name: String): String = field(name).plain()
private fun InspectionValue.Fields.number(name: String): Double? = (field(name) as? InspectionValue.Scalar)?.value?.numberOrNull()
private fun InspectionValue.Fields.flag(name: String): Boolean = ((field(name) as InspectionValue.Scalar).value as StatValue.BooleanValue).value
private fun InspectionValue.Fields.fields(name: String): InspectionValue.Fields = field(name) as InspectionValue.Fields
private fun InspectionValue.Fields.rows(name: String): List<InspectionValue.Fields> = (field(name) as InspectionValue.Sequence).values.map { it as InspectionValue.Fields }

@Composable
private fun InspectionCopy(text: String, tag: String) {
    val clipboard = LocalClipboardManager.current
    TextButton(onClick = { clipboard.setText(AnnotatedString(text)) }, modifier = Modifier.testTag(tag)) { Text("Copy") }
}

@Composable
private fun InspectionDetail(title: String, body: String, tag: String, expandedAll: Boolean = false) {
    var expanded by rememberSaveable(tag) { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth().testTag(tag)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            TextButton(onClick = { expanded = !expanded }, modifier = Modifier.testTag("$tag-expand")) { Text(title) }
            if (expanded || expandedAll) {
                SelectionContainer { Text(body, Modifier.testTag("$tag-detail")) }
                InspectionCopy("$title\n$body", "$tag-copy")
            }
        }
    }
}

@Composable
private fun InspectionAffectorTree(nodes: List<InspectionValue.Fields>, internal: Boolean, expandedAll: Boolean,
    tag: String, matches: (String) -> Boolean, sourceName: (InspectionValue.Fields) -> String,
    onFollow: (InspectionValue.Fields) -> Unit) {
    for ((index, node) in nodes.withIndex()) {
        if (!matches(node.plain())) continue
        val key = "$tag-$index"
        var expanded by rememberSaveable(key) { mutableStateOf(false) }
        val alternate = node.field("alternate")
        val label = if (internal && alternate != InspectionValue.Absent) alternate.plain() else node.text("label")
        val children = node.rows("children")
        Card(Modifier.fillMaxWidth().testTag(key)) {
            Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                if (children.isEmpty()) SelectionContainer { Text(label, Modifier.testTag("$key-label")) } else
                    TextButton(onClick = { expanded = !expanded }, modifier = Modifier.testTag("$key-expand")) { Text(label, Modifier.testTag("$key-label")) }
                if (children.isEmpty() || expanded || expandedAll) {
                    for ((sourceIndex, source) in node.rows("sources").withIndex()) TextButton(
                        onClick = { onFollow(source) }, modifier = Modifier.testTag("$key-source-$sourceIndex")) {
                        Text("Inspect modifier · ${sourceName(source)}")
                    }
                    InspectionCopy(label, "$key-copy")
                    if (children.isNotEmpty()) InspectionAffectorTree(children, internal, expandedAll, key, matches, sourceName, onFollow)
                }
            }
        }
    }
}

@Composable
internal fun InspectionView(model: InspectionModel, entryItemId: Int?, onBack: () -> Unit, onInspectBase: (Int) -> Unit) {
    BackHandler(onBack = onBack)
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val library by EngineRuntime.library.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    var selectedContext by rememberSaveable(entryItemId, fit?.id) { mutableStateOf(if (entryItemId != null) "base" else "ship") }
    var selectedIndex by rememberSaveable(entryItemId, fit?.id) { mutableStateOf(0) }
    var selectedItem by rememberSaveable(entryItemId, fit?.id) { mutableStateOf(entryItemId) }
    var tab by rememberSaveable(entryItemId, fit?.id) { mutableStateOf("Attributes") }
    var raw by rememberSaveable(entryItemId, fit?.id) { mutableStateOf(false) }
    var effective by rememberSaveable(entryItemId, fit?.id) { mutableStateOf(false) }
    var search by rememberSaveable(entryItemId, fit?.id, tab) { mutableStateOf("") }
    var page by rememberSaveable(entryItemId, fit?.id, tab, search, raw) { mutableStateOf(0) }
    var choose by rememberSaveable { mutableStateOf(false) }
    var selectedObject by rememberSaveable { mutableStateOf<String?>(null) }
    var followFit by rememberSaveable { mutableStateOf<String?>(null) }
    var followContext by rememberSaveable { mutableStateOf("ship") }
    var followIndex by rememberSaveable { mutableStateOf(0) }
    var followItem by rememberSaveable { mutableStateOf(0) }
    var followObject by rememberSaveable { mutableStateOf<String?>(null) }
    var navigationError by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(fit?.id, followFit) {
        if (followFit != null && fit?.id == followFit) {
            selectedContext = followContext; selectedIndex = followIndex; selectedItem = followItem
            selectedObject = followObject
            followFit = null; search = ""; page = 0; tab = "Attributes"
        }
    }
    fun inspectBase(identity: Int) {
        followFit = null; selectedContext = "base"; selectedIndex = 0; selectedItem = identity
        selectedObject = null
        search = ""; page = 0; tab = "Attributes"; onInspectBase(identity)
    }
    Text("Item inspector", style = MaterialTheme.typography.headlineMedium)
    TextButton(onClick = onBack, modifier = Modifier.testTag("inspection-back")) { Text("Back") }
    navigationError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    if (fit != null) LaunchedEffect(fit.id, fit.revision) { model.options(context, fit) }
    val options = model.options?.takeIf { it.fitId == fit?.id && it.revision == fit?.revision }
    val target = if (selectedContext == "base") selectedItem?.let { InspectionTarget("base", null, it) }
        else options?.targets?.firstOrNull { it.target.context == selectedContext &&
            (if (selectedObject != null) it.target.objectKey == selectedObject else it.target.index == selectedIndex) &&
            (selectedItem == null || it.target.itemId == selectedItem) }?.target
    LaunchedEffect(target) {
        if (target != null && target.context != "base" && selectedObject == null) selectedObject = target.objectKey
    }
    TextButton(onClick = { choose = !choose }, modifier = Modifier.testTag("inspection-choose")) { Text("Choose fitted item") }
    if (choose && options != null) for (option in options.targets) {
        TextButton(onClick = {
            selectedContext = option.target.context; selectedIndex = option.target.index!!; selectedItem = option.target.itemId
            selectedObject = option.target.objectKey
            choose = false; page = 0; search = ""
        }, modifier = Modifier.testTag("inspection-target-${option.target.context}-${option.target.index}")) {
            Text("${option.target.context} ${option.target.index!! + 1} · ${option.name}")
        }
    }
    if (target == null) {
        Text(if (fit == null) "Select a fit or inspect an item from the equipment browser." else "Choose an item that is still in this fit.", Modifier.testTag("inspection-missing-target"))
        model.error?.let { Text(it) }
        if (fit != null) TextButton(onClick = { model.options(context, fit, true) }) { Text("Reload targets") }
        return
    }
    LaunchedEffect(fit?.id, fit?.revision, target, effective) { model.load(context, fit, target, effective) }
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    TextButton(onClick = { model.load(context, fit, target, effective, true) }, modifier = Modifier.testTag("inspection-refresh")) { Text("Refresh") }
    val detail = model.details?.takeIf { it.target == target && (target.context == "base" || it.fitId == fit?.id && it.revision == fit?.revision) }
    if (detail == null) { Text(if (model.loading) "Loading inspection…" else "Inspection unavailable."); return }
    Text(detail.item.text("name"), style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("inspection-name"))
    Text("${detail.item.text("category")} · ${detail.item.text("group")} · ID ${target.itemId}")
    if (target.context != "base") TextButton(onClick = { inspectBase(target.itemId) }, modifier = Modifier.testTag("inspection-base")) { Text("Inspect base item") }
    val tabs = listOf("Attributes", "Description", "Traits", "Affected by", "Compare", "Effects", "Properties", "Equipment")
    for (chunk in tabs.chunked(2)) Row {
        for (name in chunk) TextButton(onClick = { tab = name; search = ""; page = 0 }, modifier = Modifier.testTag("inspection-tab-${name.replace(' ', '-')}")) {
            Text(if (tab == name) "• $name" else name)
        }
    }
    if (tab !in listOf("Description", "Traits")) OutlinedTextField(search, onValueChange = { search = it; page = 0 },
        label = { Text("Search names, IDs and details") }, modifier = Modifier.fillMaxWidth().testTag("inspection-search"), singleLine = true)
    fun matches(vararg values: String) = search.isBlank() || values.any { it.contains(search.trim(), ignoreCase = true) }
    val targetKey = "${detail.fitId}:${target.context}:${target.index}:${target.itemId}"
    val stateKey = "${detail.fitId}:${target.context}:${target.objectKey ?: target.itemId}"
    when (tab) {
        "Attributes" -> {
            Row { Checkbox(raw, { raw = it; page = 0 }, Modifier.testTag("inspection-raw")); Text("Raw attributes") }
            val byName = detail.attributes.associateBy { it.name }
            val ordered = (if (raw) detail.raw else detail.normal).filter { entry ->
                val row = byName.getValue(entry.name)
                matches(entry.label, row.name, row.id?.toString().orEmpty(), row.rawCurrent, row.rawBase, entry.groups.joinToString(" "))
            }
            var collapsed by rememberSaveable(stateKey, raw) { mutableStateOf(listOf<String>()) }
            val groups = ordered.map { it.groups.joinToString(" › ").ifEmpty { "Other attributes" } }.distinct()
            TextButton(onClick = { collapsed = if (collapsed.isEmpty()) groups else emptyList() }, modifier = Modifier.testTag("inspection-groups-toggle")) {
                Text(if (collapsed.isEmpty()) "Collapse groups" else "Expand groups")
            }
            Text("${ordered.size} attributes", Modifier.testTag("inspection-attribute-count"))
            for (group in groups) {
                TextButton(onClick = { collapsed = if (group in collapsed) collapsed - group else collapsed + group }) { Text(group) }
                if (group !in collapsed) for (entry in ordered.filter { it.groups.joinToString(" › ").ifEmpty { "Other attributes" } == group }) {
                    val row = byName.getValue(entry.name)
                    val current = if (raw) row.rawCurrent else row.displayCurrent!!
                    val base = if (raw) row.rawBase else row.displayBase!!
                    val body = "Current: $current\nBase: $base\nFull precision current: ${row.rawCurrent}\nFull precision base: ${row.rawBase}\n" +
                        "Internal name: ${row.name}\nID: ${row.id ?: "No metadata"}\nInternal unit: ${row.unit?.name ?: "No unit"}\n" +
                        "Unit ID: ${row.unit?.id ?: "No unit"}\nPublished: ${row.published}"
                    InspectionDetail("${entry.label} · $current", body, "inspection-attribute-${row.name}")
                }
            }
        }
        "Description", "Traits" -> {
            val html = detail.item.field(if (tab == "Description") "description" else "traits")
            val body = inspectionPlainText(if (html == InspectionValue.Absent) null else html.plain(), tab == "Traits")
                ?: "No ${tab.lowercase()} available."
            SelectionContainer { Text(body, Modifier.testTag("inspection-text")) }
            InspectionCopy(body, "inspection-text-copy")
        }
        "Affected by" -> {
            var internalNames by rememberSaveable(stateKey) { mutableStateOf(false) }
            var attributeView by rememberSaveable(stateKey) { mutableStateOf(false) }
            var unused by rememberSaveable(stateKey) { mutableStateOf(false) }
            var expanded by rememberSaveable(stateKey) { mutableStateOf(false) }
            Row { Checkbox(attributeView, { attributeView = it }, Modifier.testTag("inspection-affectors-by-attribute")); Text("Group by attribute") }
            Row { Checkbox(internalNames, { internalNames = it }, Modifier.testTag("inspection-affectors-internal")); Text("Internal attribute names") }
            Row { Checkbox(unused, { unused = it }, Modifier.testTag("inspection-affectors-unused")); Text("Include unused or unchanged modifiers") }
            Row { Checkbox(expanded, { expanded = it }, Modifier.testTag("inspection-affectors-expand")); Text("Expand all") }
            fun follow(row: InspectionValue.Fields) {
                val identity = row.number("item_id")?.toInt() ?: return
                val fitted = row.field("source_target") as? InspectionValue.Fields
                val sourceFit = (row.field("source_fit_key") as? InspectionValue.Scalar)?.value?.raw as? String
                if (fitted == null || sourceFit == null) inspectBase(identity) else {
                    followFit = sourceFit; followContext = fitted.text("context")
                    followIndex = fitted.number("index")!!.toInt(); followItem = identity; navigationError = null
                    followObject = (fitted.values["object_key"] as? InspectionValue.Scalar)?.value?.raw as? String
                    EngineRuntime.selectFit(context, sourceFit).whenCompleteAsync({ _, failure ->
                        if (failure != null) { followFit = null; navigationError = "The modifier fit is no longer available. Inspect its base item instead." }
                    }, ContextCompat.getMainExecutor(context))
                }
            }
            fun sourceName(row: InspectionValue.Fields): String {
                val key = (row.field("source_fit_key") as? InspectionValue.Scalar)?.value?.raw as? String
                return library.singleOrNull { it.id == key }?.name ?: row.text("source_fit_name")
            }
            if (!unused) {
                val mode = if (attributeView) "attribute" else "source"
                Text("${detail.affectors.count { it.flag("used") && it.flag("changed") && it.field("item_id") != InspectionValue.Absent }} modifiers", Modifier.testTag("inspection-affector-count"))
                InspectionAffectorTree(detail.affectorViews.rows(mode), internalNames, expanded || search.isNotEmpty(),
                    "inspection-affector-tree-$targetKey-$mode", ::matches, ::sourceName, ::follow)
            } else {
            val labels = detail.attributes.associate { it.name to it.label }
            val sourceOrder = listOf("Fit", "Ship", "Citadel", "Mode", "Module", "Drone", "Fighter", "Implant", "Booster", "Skill")
            val rows = detail.affectors.filter { (unused || it.flag("used") && it.flag("changed")) && matches(it.plain()) }.sortedWith(
                compareBy<InspectionValue.Fields> { if (it.text("source_fit_key") == detail.fitId) 1 else 0 }
                    .thenBy { sourceOrder.indexOf(it.text("source_type")) }.thenBy { it.text("item_name") }.thenBy { it.text("attribute") })
            val grouped = rows.groupBy { if (attributeView) {
                val name = it.text("attribute"); if (internalNames) name else labels[name] ?: name
            } else "${it.text("source_type")} · ${it.text("item_name")} · ${it.text("source_fit_name")}" }
            Text("${rows.size} modifiers", Modifier.testTag("inspection-affector-count"))
            for ((group, entries) in grouped) {
                Text(group, style = MaterialTheme.typography.titleSmall)
                for ((index, row) in entries.withIndex()) {
                    val attribute = row.text("attribute")
                    InspectionDetail(if (internalNames) attribute else labels[attribute] ?: attribute, row.plain(), "inspection-affector-$group-$index", expanded)
                    row.number("item_id")?.let { identity ->
                        TextButton(onClick = { follow(row) }, modifier = Modifier.testTag("inspection-affector-item-${identity.toInt()}")) { Text("Inspect modifier item") }
                    }
                }
            }
            }
        }
        "Compare" -> {
            var sort by rememberSaveable(stateKey) { mutableStateOf("default") }
            var reverse by rememberSaveable(stateKey) { mutableStateOf(false) }
            var order by rememberSaveable(stateKey) { mutableStateOf(listOf<Int>()) }
            var highlighted by rememberSaveable(stateKey) { mutableStateOf(listOf<Int>()) }
            Row { Checkbox(raw, { raw = it; page = 0 }); Text("Raw values") }
            val columns = detail.variations.rows("columns")
            val members = detail.variations.rows("rows")
            for (key in listOf("default", "name", "price") + columns.map { it.text("name") }) TextButton(onClick = {
                val nextReverse = key != "default" && sort == key && !reverse
                order = sortInspectionVariations(members, key, nextReverse, order).map { it.number("id")!!.toInt() }
                reverse = nextReverse; sort = key
            }, modifier = Modifier.testTag("inspection-sort-$key")) { Text("Sort ${columns.firstOrNull { it.text("name") == key }?.text("label") ?: if (key == "default") "meta/name" else key}${if (sort == key) if (reverse) " ↓" else " ↑" else ""}") }
            val sorted = sortInspectionVariations(members, sort, reverse, order).filter { matches(it.plain()) }
            Text("${sorted.size} variations · base attributes", Modifier.testTag("inspection-variation-count"))
            for (row in sorted) {
                val identity = row.number("id")!!.toInt()
                val price = row.fields("price")
                val values = row.rows("values").joinToString("\n") { cell ->
                    val label = columns.first { it.text("name") == cell.text("name") }.text("label")
                    "$label: ${if (!cell.flag("available")) "Absent" else cell.text(if (raw) "raw" else "display")}" +
                        if (row.flag("selected") && target.context != "base") detail.attributes.firstOrNull { it.name == cell.text("name") }?.let {
                            "\nFitted current: ${if (raw) it.rawCurrent else it.displayCurrent ?: it.rawCurrent} · base: ${if (raw) it.rawBase else it.displayBase ?: it.rawBase}"
                        }.orEmpty() else ""
                }
                val body = values + "\nPrice: ${if (price.flag("available")) price.text("display") + " ISK" else "Unavailable"}\n" +
                    "Price timestamp: ${price.text("timestamp")}\nItem ID: $identity"
                InspectionDetail((if (identity in highlighted) "★ " else "") + row.text("name"), body, "inspection-variation-$identity")
                Row {
                    TextButton(onClick = { highlighted = if (identity in highlighted) highlighted - identity else highlighted + identity }) { Text("Highlight") }
                    TextButton(onClick = { inspectBase(identity) }, modifier = Modifier.testTag("inspection-variation-inspect-$identity")) { Text("Inspect") }
                }
            }
        }
        "Effects", "Properties" -> {
            val rows = (if (tab == "Effects") detail.effects else detail.properties).filter { matches(it.plain()) }
            val size = 30; val pages = maxOf(1, (rows.size + size - 1) / size); val current = page.coerceIn(0, pages - 1)
            Text("${rows.size} ${tab.lowercase()} · page ${current + 1} of $pages", Modifier.testTag("inspection-member-count"))
            for (row in rows.drop(current * size).take(size)) {
                val body = if (tab == "Properties") {
                    "Value: ${if (row.flag("available")) if (row.field("display") != InspectionValue.Absent) row.text("display") else row.field("value").plain("None") else "Unavailable"}" +
                        if (row.flag("available")) "\nProperty: ${row.text("name")}" else "\n${row.text("reason")}\nProperty: ${row.text("name")}"
                } else row.plain()
                InspectionDetail(row.text(if (tab == "Effects") "name" else "label"), body,
                    "inspection-${tab.lowercase()}-${row.text("name")}")
            }
            if (pages > 1) Row {
                TextButton(onClick = { page = current - 1 }, enabled = current > 0, modifier = Modifier.testTag("inspection-previous")) { Text("Previous") }
                TextButton(onClick = { page = current + 1 }, enabled = current + 1 < pages, modifier = Modifier.testTag("inspection-next")) { Text("Next") }
            }
        }
        "Equipment" -> {
            Row { Checkbox(effective, { effective = it }, Modifier.testTag("inspection-effective")); Text("Effective local repair details") }
            InspectionDetail("Volume and stack", detail.stack.plain(), "inspection-stack", true)
            detail.equipment?.let { row ->
                for (name in listOf("misc", "range", "capacitor")) {
                    val value = row.field(name)
                    InspectionDetail(name.replaceFirstChar { it.uppercase() }, if (value == InspectionValue.Absent) "Not applicable to this item." else value.plain(), "inspection-equipment-$name", true)
                }
            } ?: Text("No fitted equipment column applies. Inspect attributes and properties for full item details.")
            for (name in listOf("cpu", "power", "volume")) detail.attributes.firstOrNull { it.name == name }?.let { row ->
                InspectionDetail(row.label, "Current: ${row.rawCurrent}\nBase: ${row.rawBase}\nUnit: ${row.unit?.name ?: "No unit"}", "inspection-equipment-$name", true)
            }
        }
    }
}
