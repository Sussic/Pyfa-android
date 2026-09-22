package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.os.Process
import android.provider.Settings
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
@OptIn(ExperimentalTestApi::class)
class EquipmentBrowserTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun click(tag: String) {
        compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick()
        sync()
    }
    private fun search(query: String) {
        compose.onNodeWithTag("equipment-search").performScrollTo().performTextReplacement(query)
        click("equipment-search-submit")
        compose.waitUntil(30_000) { !model.busy && model.searched == query }
        sync()
        assertNull(model.error)
    }
    private fun itemIds() = compose.onAllNodes(SemanticsMatcher("equipment rows") {
        it.config.getOrElse(SemanticsProperties.TestTag) { "" }.startsWith("equipment-item-")
    }).fetchSemanticsNodes().map { it.config[SemanticsProperties.TestTag].removePrefix("equipment-item-").toInt() }
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b041-$name.png")).use { it.readBytes() }
    }

    @Test fun completeCatalogueAndBrowserMatchDesktopOffline() {
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        sync()
        val beforeFits = EngineRuntime.library.value
        val beforeModified = EngineRuntime.modified.value
        val beforeRuntime = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        assertTrue(beforeRuntime.getJSONObject("persistence").getBoolean("enabled"))
        val fixture = JSONObject(InstrumentationRegistry.getInstrumentation().context.assets.open("equipment-expected.json")
            .bufferedReader().use { it.readText() })
        val expected = EquipmentCatalog.decode(fixture.getJSONObject("catalog").toString())
        val actual = EngineRuntime.equipmentCatalog(context).get(180, TimeUnit.SECONDS)
        assertEquals(expected, actual)
        assertEquals(718, actual.groups.size)
        assertEquals(6822, actual.items.size)
        val raw = JSONObject(EngineRuntime.equipmentDiagnostics(context).get(30, TimeUnit.SECONDS))
        val searches = JSONObject()
        val queries = fixture.getJSONObject("searches")
        for (query in queries.keys()) {
            val ids = EngineRuntime.searchEquipment(context, query).get(30, TimeUnit.SECONDS)
            val expectedIds = queries.getJSONArray(query).let { rows -> (0 until rows.length()).map { rows.getInt(it) } }
            assertEquals(query, expectedIds, ids)
            searches.put(query, JSONArray(ids))
        }
        try {
            click("equipment-open")
            compose.waitUntil(30_000) { model.catalog != null && !model.busy }
            sync()
            actual.roots.forEach { compose.onNodeWithTag("equipment-group-$it").assertExists() }
            compose.onNodeWithTag("equipment-group-${actual.children(null).first().id}").performScrollTo().assertIsDisplayed()
            screenshot("root")
            val weapon = expected.items.single { it.name == "Dual 150mm Railgun II" }
            search(weapon.name)
            assertEquals(listOf(weapon.id), itemIds())
            click("equipment-item-${weapon.id}")
            compose.onNodeWithTag("equipment-selected").assertExists()
            assertEquals(weapon.id, model.selectedId)
            compose.activityRule.scenario.recreate()
            sync()
            assertEquals(weapon.id, model.selectedId)
            assertEquals(weapon.name, model.searched)
            screenshot("search")
            click("equipment-jump")
            assertNull(model.searched)
            assertEquals(weapon.marketGroupId, model.groupId)
            assertEquals(setOf(weapon.meta), model.metas)
            compose.onNodeWithTag("equipment-location").performScrollTo().assertIsDisplayed()
                .assertTextEquals(expected.path(checkNotNull(weapon.marketGroupId)).joinToString(" › ") { it.name })
            screenshot("group")
            click("equipment-back") // Dismiss item detail.
            click("equipment-back") // Parent group.
            assertEquals(expected.groupById[weapon.marketGroupId]?.parentId, model.groupId)
            click("equipment-root")
            for (group in expected.path(checkNotNull(weapon.marketGroupId))) click("equipment-group-${group.id}")
            assertEquals(weapon.marketGroupId, model.groupId)

            search("railgun")
            click("equipment-meta-Normal")
            compose.onNodeWithTag("equipment-empty").assertExists()
            assertTrue(itemIds().isEmpty())
            click("equipment-meta-Faction")
            val filtered = model.results.map { expected.itemById.getValue(it) }.filter { it.meta == "Faction" }
                .sortedWith(compareBy<EquipmentItem> { it.name.lowercase() }.thenBy { it.id }).map { it.id }.take(20)
            assertTrue(filtered.isNotEmpty())
            assertEquals(filtered, itemIds())
            screenshot("meta")
            for (meta in EquipmentCatalog.metas) if (meta !in model.metas) click("equipment-meta-$meta")
            search("Standup")
            val first = itemIds()
            assertEquals(20, first.size)
            click("equipment-next")
            val second = itemIds()
            assertEquals(20, second.size)
            assertTrue(first.intersect(second.toSet()).isEmpty())
            compose.activityRule.scenario.recreate()
            sync()
            assertEquals(second, itemIds())
            click("equipment-previous")
            assertEquals(first, itemIds())
            search("zz-no-such-equipment")
            compose.onNodeWithTag("equipment-empty").assertExists()
            screenshot("empty")
            click("equipment-root")
            click("equipment-back")
            compose.onNodeWithTag("equipment-open").assertExists()
            assertEquals(beforeFits, EngineRuntime.library.value)
            assertEquals(beforeModified, EngineRuntime.modified.value)
            val runtime = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(30, TimeUnit.SECONDS))
            assertEquals(beforeRuntime.getJSONObject("persistence").getLong("generation"), runtime.getJSONObject("persistence").getLong("generation"))
            val report = JSONObject().put("task", "B04.1").put("pid", Process.myPid()).put("runtime", runtime)
                .put("catalog", raw).put("searches", searches).put("first_page", JSONArray(first)).put("second_page", JSONArray(second))
                .put("checks", JSONArray(listOf("complete_desktop_catalogue", "all_desktop_searches", "tree_and_item_jump",
                    "meta_filters_and_empty", "pagination", "activity_recreation", "saved_fits_unchanged")))
            val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw("dd of=/sdcard/Download/pyfa-b041.json")
            ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
                ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(report.toString(2).toByteArray(Charsets.UTF_8)) }
                completion.readBytes()
            }
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
