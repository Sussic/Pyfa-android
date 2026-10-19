package io.github.sussic.pyfa

import android.Manifest
import android.content.ClipboardManager
import android.content.Context
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.provider.Settings
import android.util.JsonReader
import android.util.JsonToken
import android.view.inputmethod.InputMethodManager
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.state.ToggleableState
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.TimeUnit
import org.json.JSONObject
import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Real controls; complete family, linked and restart coverage remains separate. */
@RunWith(AndroidJUnit4::class)
class InspectionUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[InspectionModel::class.java]
    private var lastCopyAt = 0L
    private fun click(tag: String) {
        compose.onNodeWithTag(tag).performScrollTo().performClick(); compose.waitForIdle()
        if (tag.endsWith("-copy")) lastCopyAt = android.os.SystemClock.elapsedRealtime()
    }
    private fun search(text: String) {
        compose.onNodeWithTag("inspection-search").performScrollTo().performTextReplacement(text)
        compose.runOnIdle {
            (context.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager)
                .hideSoftInputFromWindow(compose.activity.window.decorView.windowToken, 0)
        }
        compose.waitForIdle(); instrumentation.uiAutomation.waitForIdle(500, 10_000)
    }
    private fun expand(tag: String) {
        click("$tag-expand")
        compose.waitUntil(10_000) { compose.onAllNodesWithTag("$tag-detail").fetchSemanticsNodes().size == 1 }
    }
    private fun originalJson(reader: JsonReader): Any = when (reader.peek()) {
        JsonToken.BEGIN_OBJECT -> JSONObject().apply {
            reader.beginObject()
            while (reader.hasNext()) { val name = reader.nextName(); assertFalse(has(name)); put(name, originalJson(reader)) }
            reader.endObject()
        }
        JsonToken.BEGIN_ARRAY -> JSONArray().apply {
            reader.beginArray(); while (reader.hasNext()) put(originalJson(reader)); reader.endArray()
        }
        JsonToken.STRING -> reader.nextString()
        JsonToken.BOOLEAN -> reader.nextBoolean()
        JsonToken.NULL -> { reader.nextNull(); JSONObject.NULL }
        JsonToken.NUMBER -> reader.nextString().let { it.toLongOrNull() ?: it.toDouble().also { n -> assertTrue(n.isFinite()) } }
        else -> error("Invalid original property JSON")
    }
    private fun firstPropertyCase(golden: JSONObject): JSONObject =
        JsonReader(instrumentation.context.assets.open("inspector-properties-expected.json").reader()).use { reader ->
            reader.beginObject()
            val headers = JSONObject()
            while (reader.hasNext()) {
                val name = reader.nextName()
                if (name == "cases") {
                    for (key in listOf("sourceCommit", "databaseLogicalSha256")) assertEquals(golden.getString(key), headers.getString(key))
                    reader.beginArray(); assertTrue(reader.hasNext())
                    return@use originalJson(reader) as JSONObject
                }
                assertFalse(headers.has(name)); headers.put(name, originalJson(reader))
            }
            error("Missing original property cases")
        }
    private fun ready() {
        compose.waitUntil(60_000) { model.details != null && !model.loading && model.error == null }
        compose.waitForIdle()
    }
    private fun screenshot(name: String) {
        // Android's temporary clipboard overlay can survive activity recreation.
        // Let that system preview expire before judging the underlying screen.
        val remainingPreview = 10_000 - (android.os.SystemClock.elapsedRealtime() - lastCopyAt)
        if (remainingPreview > 0) android.os.SystemClock.sleep(remainingPreview)
        compose.runOnIdle {
            (context.getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager)
                .hideSoftInputFromWindow(compose.activity.window.decorView.windowToken, 0)
        }
        compose.waitForIdle(); instrumentation.uiAutomation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-c032-ui-$name.png")).use { it.readBytes() }
    }
    private fun linkedUiFixture(kind: String): Pair<JSONObject, JSONObject> {
        val header = JSONObject()
        JsonReader(instrumentation.context.assets.open("inspector-$kind-expected.json").reader()).use { reader ->
            reader.beginObject()
            while (reader.hasNext()) {
                val key = reader.nextName()
                if (key == "states") reader.skipValue()
                else { assertFalse(header.has(key)); header.put(key, originalJson(reader)) }
            }
            reader.endObject(); assertEquals(JsonToken.END_DOCUMENT, reader.peek())
        }
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", header.getString("source_commit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", header.getString("databaseLogicalSha256"))
        val state = header.getJSONObject("inputs").getJSONArray("steps").getJSONObject(0).getString("name")
        var expected: JSONObject? = null
        JsonReader(instrumentation.context.assets.open("inspector-$kind-expected.json").reader()).use { reader ->
            reader.beginObject()
            while (reader.hasNext()) {
                if (reader.nextName() != "states") { reader.skipValue(); continue }
                reader.beginObject()
                while (reader.hasNext()) {
                    if (reader.nextName() == state) { assertNull(expected); expected = originalJson(reader) as JSONObject }
                    else reader.skipValue()
                }
                reader.endObject()
            }
            reader.endObject(); assertEquals(JsonToken.END_DOCUMENT, reader.peek())
        }
        return header to checkNotNull(expected)
    }
    private fun linkedAttributes(expected: JSONObject, actual: ItemInspection) {
        val rows = expected.getJSONArray("precise"); assertEquals(rows.length(), actual.attributes.size)
        fun value(wanted: Any, got: Any?) {
            if (wanted is Number) {
                assertTrue(got is Number)
                val first = wanted.toDouble(); val second = (got as Number).toDouble()
                assertTrue(first.isFinite() && second.isFinite())
                assertEquals(first, second, kotlin.math.max(1e-9, 1e-10 * kotlin.math.max(kotlin.math.abs(first), kotlin.math.abs(second))))
            } else assertEquals(if (wanted == JSONObject.NULL) null else wanted, got)
        }
        for (index in 0 until rows.length()) {
            val row = rows.getJSONObject(index); val got = actual.attributes[index]
            assertEquals(row.getString("name"), got.name); value(row.get("id"), got.id)
            value(row.get("current"), got.current.raw); value(row.get("base"), got.base.raw)
            if (row.isNull("unit")) assertNull(got.unit) else {
                val unit = row.getJSONObject("unit"); val gotUnit = checkNotNull(got.unit)
                assertEquals(unit.getInt("id"), gotUnit.id); assertEquals(unit.getString("name"), gotUnit.name)
                value(unit.get("display"), gotUnit.display)
            }
        }
        val members = actual.attributes.associateBy { it.name }
        for ((mode, order) in listOf("normal" to actual.normal, "raw" to actual.raw)) {
            val ordered = expected.getJSONArray(mode); assertEquals(ordered.length(), order.size)
            for (index in order.indices) {
                val row = ordered.getJSONObject(index); val got = order[index]; val attribute = members.getValue(got.name)
                assertEquals(row.getString("name"), got.name); assertEquals(row.getString("label"), got.label)
                assertEquals((0 until row.getJSONArray("groups").length()).map { row.getJSONArray("groups").getString(it) }, got.groups)
                value(row.get("current"), if (mode == "raw") attribute.rawCurrent else attribute.displayCurrent)
                value(row.get("base"), if (mode == "raw") attribute.rawBase else attribute.displayBase)
            }
        }
    }
    @Test fun projectedAndCommandSourceButtonsResolveOriginalFittedOwnersOffline() {
        assertEquals("ui", InstrumentationRegistry.getArguments().getString("c032_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        fun create(spec: JSONObject): String {
            val input = JSONObject(spec.toString())
            if (input.has("ignore_restrictions")) assertFalse(input.getBoolean("ignore_restrictions"))
            if (input.has("cargo")) assertEquals(0, input.getJSONArray("cargo").length())
            input.remove("ignore_restrictions"); input.remove("cargo")
            val response = EngineRuntime.request(context, BridgeOperation.CreateFit(BridgeCodec.decodeFitSpec(input))).get(120, TimeUnit.SECONDS)
            assertTrue(response.error?.message, response.isSuccess); return response.fits.single().id
        }
        fun rows(value: InspectionValue?): List<InspectionValue.Fields> =
            (value as InspectionValue.Sequence).values.map { it as InspectionValue.Fields }
        fun text(row: InspectionValue.Fields, key: String) = (row.values[key] as? InspectionValue.Scalar)?.value?.raw as? String
        for (kind in listOf("projection", "command")) {
            val (header, expected) = linkedUiFixture(kind); val input = header.getJSONObject("inputs")
            val source = create(input.getJSONObject("source")); val target = create(input.getJSONObject("target"))
            val step = input.getJSONArray("steps").getJSONObject(0); assertEquals("add", step.getString("operation"))
            val operation = if (kind == "projection") BridgeOperation.AddProjection(source, target,
                if (step.isNull("range_m")) null else step.getDouble("range_m"), step.getBoolean("active"), step.getInt("amount"))
                else BridgeOperation.AddCommand(source, target)
            val revisions = listOf(source, target).associateWith { id -> EngineRuntime.library.value.single { it.id == id }.revision }
            val linked = EngineRuntime.request(context, operation, revisions).get(120, TimeUnit.SECONDS)
            assertTrue(linked.error?.message, linked.isSuccess)
            val graph = EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS)
            for ((modeIndex, mode) in listOf("source", "attribute").withIndex()) {
                EngineRuntime.selectFit(context, target).get(30, TimeUnit.SECONDS)
                if (kind == "projection" && modeIndex == 0) {
                    compose.waitUntil(60_000) { compose.onAllNodesWithTag("inspection-open").fetchSemanticsNodes().isNotEmpty() }
                    click("inspection-open")
                }
                compose.waitUntil(60_000) { model.options?.fitId == target }
                click("inspection-choose"); click("inspection-target-ship-0")
                compose.waitUntil(60_000) { model.details?.let { it.fitId == target && it.target.context == "ship" } == true && !model.loading }
                ready(); click("inspection-tab-Affected-by")
                fun checkbox(tag: String, checked: Boolean) {
                    val control = compose.onNodeWithTag(tag).performScrollTo()
                    val state = control.fetchSemanticsNode().config.getOrNull(SemanticsProperties.ToggleableState)
                    assertNotNull(state)
                    if ((state == ToggleableState.On) != checked) { control.performClick(); compose.waitForIdle() }
                    if (checked) control.assertIsOn() else control.assertIsOff()
                }
                checkbox("inspection-affectors-expand", true)
                checkbox("inspection-affectors-by-attribute", mode == "attribute")
                val detail = checkNotNull(model.details)
                val key = "${detail.fitId}:${detail.target.context}:${detail.target.index}:${detail.target.itemId}"
                fun locate(nodes: List<InspectionValue.Fields>, tag: String): Pair<String, InspectionTarget>? {
                    for ((index, node) in nodes.withIndex()) {
                        val nodeTag = "$tag-$index"
                        for ((sourceIndex, row) in rows(node.values["sources"]).withIndex()) {
                            val selected = row.values["source_target"] as? InspectionValue.Fields ?: continue
                            if (text(row, "source_fit_key") != source || text(selected, "context") != "module") continue
                            fun number(name: String) = ((selected.values[name] as InspectionValue.Scalar).value.raw as Number).toInt()
                            return "$nodeTag-source-$sourceIndex" to InspectionTarget("module", number("index"), number("item_id"), text(selected, "object_key"))
                        }
                        locate(rows(node.values["children"]), nodeTag)?.let { return it }
                    }
                    return null
                }
                val (button, selected) = checkNotNull(locate(rows(detail.affectorViews.values[mode]), "inspection-affector-tree-$key-$mode"))
                assertNotNull(selected.objectKey)
                compose.onNodeWithTag(button).performScrollTo().assertTextEquals("Inspect modifier · ${input.getJSONObject("source").getString("name")}")
                screenshot("$kind-$mode-owner"); click(button)
                compose.waitUntil(60_000) { model.details?.let { it.fitId == source && it.target == selected } == true && !model.loading }
                ready(); assertEquals(source, (EngineRuntime.state.value as EngineState.Ready).fit.id)
                val sourceRows = expected.getJSONObject("source").getJSONArray("inspection")
                val original = (0 until sourceRows.length()).map { sourceRows.getJSONObject(it) }
                    .single { it.getString("context") == "module" && it.getInt("item_id") == selected.itemId }
                linkedAttributes(original.getJSONObject("attributes"), checkNotNull(model.details))
                click("inspection-tab-Attributes"); checkbox("inspection-raw", true)
                val rawRows = original.getJSONObject("attributes").getJSONArray("raw")
                val changed = (0 until rawRows.length()).map { rawRows.getJSONObject(it) }
                    .first { it.get("current") != it.get("base") }
                val attributeTag = "inspection-attribute-${changed.getString("name")}"; search(changed.getString("name"))
                if (compose.onAllNodesWithTag("$attributeTag-detail").fetchSemanticsNodes().isEmpty()) expand(attributeTag)
                compose.onNodeWithTag("$attributeTag-detail").performScrollTo()
                    .assertTextContains("Current: ${changed.getString("current")}", substring = true)
                    .assertTextContains("Base: ${changed.getString("base")}", substring = true)
                screenshot("$kind-$mode-fitted-source")
                assertEquals(graph, EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
            }
        }
    }
    @Test fun selectedObjectRefreshRemovalReversalAndVariationNavigationOffline() {
        assertEquals("ui", InstrumentationRegistry.getArguments().getString("c032_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        fun fixture(name: String) = JSONObject(instrumentation.context.assets.open("inspector-$name-expected.json").bufferedReader().use { it.readText() })
        val golden = fixture("attributes"); val metadata = fixture("metadata")
        for (value in listOf(golden, metadata)) {
            assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", value.getString("sourceCommit"))
            assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", value.getString("databaseLogicalSha256"))
        }
        val case = golden.getJSONArray("cases").getJSONObject(0)
        val spec = JSONObject(case.getJSONObject("spec").toString())
        if (spec.has("ignore_restrictions")) assertFalse(spec.getBoolean("ignore_restrictions"))
        if (spec.has("cargo")) assertEquals(0, spec.getJSONArray("cargo").length())
        spec.remove("ignore_restrictions"); spec.remove("cargo")
        val created = EngineRuntime.request(context, BridgeOperation.CreateFit(BridgeCodec.decodeFitSpec(spec))).get(120, TimeUnit.SECONDS)
        assertTrue(created.error?.message, created.isSuccess)
        val id = created.fits.single().id
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        compose.waitUntil(60_000) { compose.onAllNodesWithTag("inspection-open").fetchSemanticsNodes().isNotEmpty() }
        click("inspection-open"); ready()
        click("inspection-choose"); click("inspection-target-module-0"); ready()
        val selected = model.details!!.target
        val original = case.getJSONArray("targets").getJSONObject(1)
        assertEquals("module", original.getString("context"))
        assertEquals(original.getInt("item_id"), selected.itemId); assertNotNull(selected.objectKey)
        val other = EngineRuntime.inspectionOptions(context, id).get(120, TimeUnit.SECONDS).targets
            .single { it.target.context == "module" && it.target.index == 1 }.target
        assertEquals(selected.itemId, other.itemId); assertNotEquals(selected.objectKey, other.objectKey)
        click("inspection-raw"); search("damageMultiplier")
        val raw = original.getJSONObject("expected").getJSONArray("raw")
        val damage = (0 until raw.length()).map { raw.getJSONObject(it) }.single { it.getString("name") == "damageMultiplier" }
        fun values() {
            compose.onNodeWithTag("inspection-attribute-count").performScrollTo().assertTextEquals("1 attributes")
            if (compose.onAllNodesWithTag("inspection-attribute-damageMultiplier-detail").fetchSemanticsNodes().isEmpty())
                expand("inspection-attribute-damageMultiplier")
            compose.onNodeWithTag("inspection-attribute-damageMultiplier-detail").performScrollTo()
                .assertTextContains("Current: ${damage.getString("current")}", substring = true)
                .assertTextContains("Base: ${damage.getString("base")}", substring = true)
        }
        fun edit(operation: BridgeOperation): Long {
            val revision = EngineRuntime.library.value.single { it.id == id }.revision
            val result = EngineRuntime.request(context, operation, mapOf(id to revision)).get(120, TimeUnit.SECONDS)
            assertTrue(result.error?.message, result.isSuccess)
            return result.fits.single { it.id == id }.revision
        }
        fun expectSelected(index: Int, revision: Long) {
            compose.waitUntil(60_000) { model.details?.let { it.revision == revision && it.target.objectKey == selected.objectKey && it.target.index == index } == true }
            ready(); values()
        }
        fun absent(revision: Long) {
            compose.waitUntil(60_000) { model.options?.revision == revision && compose.onAllNodesWithTag("inspection-missing-target").fetchSemanticsNodes().size == 1 }
            compose.onNodeWithTag("inspection-missing-target").performScrollTo().assertTextEquals("Choose an item that is still in this fit.")
            compose.onNodeWithTag("inspection-name").assertDoesNotExist()
            assertFalse(model.options!!.targets.any { it.target.objectKey == selected.objectKey })
        }
        values(); screenshot("identity")
        expectSelected(1, edit(BridgeOperation.SwapModules(id, 0, 1))); screenshot("moved")
        expectSelected(0, edit(BridgeOperation.Undo(id)))
        expectSelected(1, edit(BridgeOperation.Redo(id)))
        absent(edit(BridgeOperation.RemoveModule(id, 1))); screenshot("removed")
        expectSelected(1, edit(BridgeOperation.Undo(id))); screenshot("restored")
        absent(edit(BridgeOperation.Redo(id)))
        expectSelected(1, edit(BridgeOperation.Undo(id)))
        val beforeNavigation = EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS)
        click("inspection-tab-Compare"); search("")
        val items = metadata.getJSONArray("items")
        val family = (0 until items.length()).map { items.getJSONObject(it) }.single { it.getInt("item_id") == selected.itemId }
        val variants = family.getJSONArray("variation_ids")
        val variationIndex = (0 until variants.length()).first { variants.getInt(it) != selected.itemId }
        val variation = variants.getInt(variationIndex)
        val originalCells = family.getJSONObject("variation_presentation").getJSONObject("raw").getJSONArray("rows").getJSONArray(variationIndex)
        click("inspection-variation-inspect-$variation")
        compose.waitUntil(60_000) { model.details?.target?.let { it.context == "base" && it.itemId == variation } == true }
        ready(); assertNull(model.details!!.fitId); assertNull(model.details!!.target.objectKey)
        compose.onNodeWithTag("inspection-name").assertTextEquals(originalCells.getString(0))
        val columns = family.getJSONArray("variation_columns")
        val damageColumn = (0 until columns.length()).single { columns.getJSONObject(it).getString("name") == "damageMultiplier" }
        search("damageMultiplier"); expand("inspection-attribute-damageMultiplier")
        compose.onNodeWithTag("inspection-attribute-damageMultiplier-detail").performScrollTo()
            .assertTextContains("Current: ${originalCells.getString(damageColumn + 1)}", substring = true)
            .assertTextContains("Base: ${originalCells.getString(damageColumn + 1)}", substring = true)
        screenshot("variation")
        assertEquals(beforeNavigation, EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
        click("inspection-back")
    }

    @Test fun descriptionsAndTraitsMatchOriginalHtmlWindowText() {
        assertEquals("ui", InstrumentationRegistry.getArguments().getString("c032_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val golden = JSONObject(instrumentation.context.assets.open("inspector-text-expected.json").bufferedReader().use { it.readText() })
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", golden.getString("sourceCommit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", golden.getString("databaseLogicalSha256"))
        var fields = 0
        fun check(expected: JSONObject) {
            for (name in listOf("description", "traits")) {
                val html = if (expected.isNull(name)) null else expected.getString(name)
                val original = if (expected.isNull(name + "_plain")) null else expected.getString(name + "_plain")
                    .replace("\r\n", "\n").trim().replace(Regex("\n{2,}"), "\n")
                assertEquals(name, original, inspectionPlainText(html, name == "traits"))
                fields++
            }
        }
        val before = EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS)
        val items = golden.getJSONArray("items"); assertEquals(178, items.length())
        for (index in 0 until items.length()) {
            val row = items.getJSONObject(index); val expected = row.getJSONObject("expected")
            val detail = EngineRuntime.inspectionDetails(context, null, InspectionTarget("base", null, row.getInt("item_id"))).get(120, TimeUnit.SECONDS)
            for (name in listOf("description", "traits")) {
                val actual = detail.item.values.getValue(name)
                if (expected.isNull(name)) assertEquals(InspectionValue.Absent, actual)
                else assertEquals(expected.getString(name), ((actual as InspectionValue.Scalar).value as StatValue.Text).value)
            }
            check(expected)
        }
        val probes = golden.getJSONArray("probes"); assertEquals(7, probes.length())
        for (index in 0 until probes.length()) check(probes.getJSONObject(index).getJSONObject("expected"))
        assertEquals(370, fields)
        assertEquals(before, EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
    }
    @Test fun originalShipValuesSearchCopyAndRecreationOffline() {
        assertEquals("ui", InstrumentationRegistry.getArguments().getString("c032_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val golden = JSONObject(instrumentation.context.assets.open("inspector-attributes-expected.json").bufferedReader().use { it.readText() })
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", golden.getString("sourceCommit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", golden.getString("databaseLogicalSha256"))
        val case = golden.getJSONArray("cases").getJSONObject(0)
        val spec = JSONObject(case.getJSONObject("spec").toString())
        if (spec.has("ignore_restrictions")) assertFalse(spec.getBoolean("ignore_restrictions"))
        if (spec.has("cargo")) assertEquals(0, spec.getJSONArray("cargo").length())
        spec.remove("ignore_restrictions"); spec.remove("cargo")
        val created = EngineRuntime.request(context, BridgeOperation.CreateFit(BridgeCodec.decodeFitSpec(spec))).get(120, TimeUnit.SECONDS)
        assertTrue(created.error?.message, created.isSuccess)
        val id = created.fits.single().id
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        compose.waitUntil(60_000) { compose.onAllNodesWithTag("inspection-open").fetchSemanticsNodes().isNotEmpty() }
        click("inspection-open"); ready()
        screenshot("ship")
        compose.onNodeWithTag("inspection-name").assertTextEquals(case.getJSONObject("spec").getString("ship"))
        click("inspection-raw")
        search("AGILITY")
        compose.onNodeWithTag("inspection-attribute-count").performScrollTo().assertTextEquals("1 attributes")
        val ship = case.getJSONArray("targets").getJSONObject(0)
        assertEquals("ship", ship.getString("context"))
        val raw = ship.getJSONObject("expected").getJSONArray("raw")
        val expected = (0 until raw.length()).map { raw.getJSONObject(it) }.single { it.getString("name") == "agility" }
        click("inspection-attribute-agility-expand")
        compose.onNodeWithTag("inspection-attribute-agility-detail").performScrollTo()
            .assertTextContains("Current: ${expected.getString("current")}", substring = true)
            .assertTextContains("Base: ${expected.getString("base")}", substring = true)
            .assertTextContains("Internal name: agility", substring = true)
        click("inspection-attribute-agility-copy")
        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
        val text = clipboard.primaryClip!!.getItemAt(0).text.toString()
        assertTrue(text.contains("Full precision current: ${expected.getString("current")}"))
        assertTrue(text.contains("Full precision base: ${expected.getString("base")}"))
        screenshot("raw-search-copy")
        val before = EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS)
        compose.activityRule.scenario.recreate(); ready()
        compose.onNodeWithTag("inspection-search").performScrollTo().assertTextContains("AGILITY")
        compose.onNodeWithTag("inspection-raw").performScrollTo().assertIsOn()
        compose.onNodeWithTag("inspection-attribute-agility-detail").performScrollTo()
            .assertTextContains("Current: ${expected.getString("current")}", substring = true)
        assertEquals(before, EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
        screenshot("recreated")
        val texts = JSONObject(instrumentation.context.assets.open("inspector-text-expected.json").bufferedReader().use { it.readText() })
            .getJSONArray("items")
        val originalText = (0 until texts.length()).map { texts.getJSONObject(it) }
            .single { it.getInt("item_id") == ship.getInt("item_id") }.getJSONObject("expected")
        for (tab in listOf("Description", "Traits")) {
            click("inspection-tab-$tab")
            val field = tab.lowercase() + "_plain"
            val expectedText = if (originalText.isNull(field)) "No ${tab.lowercase()} available."
                else originalText.getString(field).replace("\r\n", "\n").trim().replace(Regex("\n{2,}"), "\n")
            compose.onNodeWithTag("inspection-text").performScrollTo().assertTextEquals(expectedText)
            click("inspection-text-copy")
            assertEquals(expectedText, clipboard.primaryClip!!.getItemAt(0).text.toString())
        }
        val metadata = JSONObject(instrumentation.context.assets.open("inspector-metadata-expected.json").bufferedReader().use { it.readText() })
            .getJSONArray("items")
        val originalMetadata = (0 until metadata.length()).map { metadata.getJSONObject(it) }
            .single { it.getInt("item_id") == ship.getInt("item_id") }
        val affectorCase = JSONObject(instrumentation.context.assets.open("inspector-affectors-expected.json").bufferedReader().use { it.readText() })
            .getJSONArray("cases").getJSONObject(0)
        assertEquals(case.getJSONObject("spec").toString(), affectorCase.getJSONObject("spec").toString())
        val affectorTarget = affectorCase.getJSONArray("targets").getJSONObject(0)
        assertEquals("ship", affectorTarget.getString("context"))
        assertEquals(ship.getInt("item_id"), affectorTarget.getInt("item_id"))
        click("inspection-tab-Affected-by")
        click("inspection-affectors-expand")
        for (mode in listOf("source", "attribute")) {
            if (mode == "attribute") click("inspection-affectors-by-attribute")
            for (internal in listOf(false, true)) {
                if (internal) click("inspection-affectors-internal")
                val tree = affectorTarget.getJSONObject("expected").getJSONArray(mode)
                val expectedLabels = (0 until tree.length()).map { index ->
                    val row = tree.getJSONObject(index)
                    if (internal && !row.isNull("alternate")) row.getString("alternate")
                    else row.getJSONArray("path").getString(row.getJSONArray("path").length() - 1)
                }
                val target = model.details!!.target
                val prefix = "inspection-affector-tree-${model.details!!.fitId}:${target.context}:${target.index}:${target.itemId}-$mode-"
                val labels = mutableListOf<String>()
                fun visit(node: androidx.compose.ui.semantics.SemanticsNode) {
                    val tag = node.config.getOrNull(SemanticsProperties.TestTag).orEmpty()
                    if (tag.startsWith(prefix) && tag.endsWith("-label")) {
                        labels.add(node.config[SemanticsProperties.Text].single().text)
                    }
                    node.children.forEach(::visit)
                }
                visit(compose.onRoot(useUnmergedTree = true).fetchSemanticsNode())
                assertEquals("$mode internal=$internal", expectedLabels, labels)
                if (mode == "source" && !internal) {
                    compose.onNodeWithTag(prefix + "0-label", useUnmergedTree = true).performScrollTo()
                    compose.onNode(hasScrollAction() and hasAnyDescendant(hasTestTag(prefix + "0-label")), useUnmergedTree = true)
                        .performSemanticsAction(SemanticsActions.ScrollBy) { it(0f, 1200f) }
                    compose.waitForIdle()
                    screenshot("affectors")
                }
                if (internal) click("inspection-affectors-internal")
            }
        }
        click("inspection-affectors-unused")
        compose.onNodeWithTag("inspection-affectors-unused").assertIsOn()
        val propertyCase = firstPropertyCase(golden)
        assertEquals(case.getJSONObject("spec").toString(), propertyCase.getJSONObject("spec").toString())
        val propertyTargets = propertyCase.getJSONArray("targets")
        val shipProperties = propertyTargets.getJSONObject(0)
        assertEquals("ship", shipProperties.getString("context"))
        assertEquals(ship.getInt("item_id"), shipProperties.getInt("item_id"))
        val expectedProperties = shipProperties.getJSONArray("expected")
        click("inspection-tab-Properties")
        compose.onNodeWithTag("inspection-member-count").performScrollTo()
            .assertTextEquals("${expectedProperties.length()} properties · page 1 of 1")
        for (name in listOf("commandBonus", "modeItems", "boostItemAttr")) {
            val original = (0 until expectedProperties.length()).map { expectedProperties.getJSONObject(it).getJSONObject("contract") }
                .single { it.getString("name") == name }
            search(name); expand("inspection-properties-$name")
            val value = if (original.getBoolean("available")) original.getString("display") else "Unavailable"
            compose.onNodeWithTag("inspection-properties-$name-detail").performScrollTo()
                .assertTextContains("Value: $value", substring = true)
            if (!original.getBoolean("available")) compose.onNodeWithTag("inspection-properties-$name-detail")
                .assertTextContains(original.getString("reason"), substring = true)
            click("inspection-properties-$name-copy")
            assertTrue(clipboard.primaryClip!!.getItemAt(0).text.toString().contains("Value: $value"))
        }
        click("inspection-tab-Effects")
        val originalEffects = originalMetadata.getJSONArray("effects")
        compose.onNodeWithTag("inspection-member-count").performScrollTo()
            .assertTextEquals("${originalEffects.length()} effects · page 1 of 1")
        val effect = originalEffects.getJSONObject(0)
        search(effect.getString("name"))
        expand("inspection-effects-${effect.getString("name")}")
        compose.onNodeWithTag("inspection-effects-${effect.getString("name")}-detail").performScrollTo()
            .assertTextContains("id: ${effect.getInt("id")}", substring = true)
        click("inspection-tab-Compare")
        val variationCount = originalMetadata.getJSONArray("variation_ids").length()
        compose.onNodeWithTag("inspection-variation-count").performScrollTo()
            .assertTextEquals("$variationCount variations · base attributes")
        click("inspection-sort-name")
        compose.onNodeWithTag("inspection-sort-name").assertTextEquals("Sort name ↑")
        click("inspection-sort-name")
        compose.onNodeWithTag("inspection-sort-name").assertTextEquals("Sort name ↓")
        click("inspection-sort-default")
        compose.onNodeWithTag("inspection-sort-default").assertTextEquals("Sort meta/name ↑")
        click("inspection-choose")
        click("inspection-target-module-0"); ready()
        val moduleProperties = propertyTargets.getJSONObject(1)
        assertEquals("module", moduleProperties.getString("context"))
        assertEquals(moduleProperties.getInt("item_id"), model.details!!.target.itemId)
        click("inspection-tab-Properties")
        val members = moduleProperties.getJSONArray("expected").length()
        val pages = (members + 29) / 30
        compose.onNodeWithTag("inspection-member-count").performScrollTo()
            .assertTextEquals("$members properties · page 1 of $pages")
        compose.onNodeWithTag("inspection-previous").performScrollTo().assertIsNotEnabled()
        for (page in 2..pages) {
            click("inspection-next")
            compose.onNodeWithTag("inspection-member-count").performScrollTo()
                .assertTextEquals("$members properties · page $page of $pages")
        }
        compose.onNodeWithTag("inspection-next").performScrollTo().assertIsNotEnabled()
        for (page in pages - 1 downTo 1) {
            click("inspection-previous")
            compose.onNodeWithTag("inspection-member-count").performScrollTo()
                .assertTextEquals("$members properties · page $page of $pages")
        }
        click("inspection-tab-Equipment")
        val moduleTarget = case.getJSONArray("targets").getJSONObject(1)
        assertEquals(moduleProperties.getInt("item_id"), moduleTarget.getInt("item_id"))
        for (name in listOf("misc", "range", "capacitor")) {
            val value = moduleTarget.getJSONObject("equipment").getJSONObject(name)
            compose.onNodeWithTag("inspection-equipment-$name-detail").performScrollTo()
                .assertTextContains("display: ${value.getString("display")}", substring = true)
                .assertTextContains("detail: ${value.getString("detail")}", substring = true)
        }
        for (name in listOf("cpu", "power", "volume")) {
            val rows = moduleTarget.getJSONObject("expected").getJSONArray("raw")
            val value = (0 until rows.length()).map { rows.getJSONObject(it) }.single { it.getString("name") == name }
            compose.onNodeWithTag("inspection-equipment-$name-detail").performScrollTo()
                .assertTextContains("Current: ${value.getString("current")}", substring = true)
                .assertTextContains("Base: ${value.getString("base")}", substring = true)
        }
        screenshot("equipment")
        click("inspection-choose")
        click("inspection-target-charge-0"); ready()
        val charge = case.getJSONArray("targets").getJSONObject(2)
        assertEquals("charge", charge.getString("context"))
        assertEquals(charge.getInt("item_id"), model.details!!.target.itemId)
        click("inspection-tab-Attributes")
        search("kineticDamage")
        val chargeRaw = charge.getJSONObject("expected").getJSONArray("raw")
        val damage = (0 until chargeRaw.length()).map { chargeRaw.getJSONObject(it) }.single { it.getString("name") == "kineticDamage" }
        expand("inspection-attribute-kineticDamage")
        compose.onNodeWithTag("inspection-attribute-kineticDamage-detail").performScrollTo()
            .assertTextContains("Current: ${damage.getString("current")}", substring = true)
            .assertTextContains("Base: ${damage.getString("base")}", substring = true)
        screenshot("charge")
        assertEquals(before, EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
        click("inspection-back")
        compose.onNodeWithTag("inspection-open").performScrollTo().assertExists()
    }
}
