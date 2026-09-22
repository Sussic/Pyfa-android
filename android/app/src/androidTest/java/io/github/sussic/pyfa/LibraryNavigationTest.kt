package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.os.Process
import android.provider.Settings
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LibraryNavigationTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val checks = mutableListOf<String>()
    private fun fits() = EngineRuntime.library.value
    private fun nav() = EngineRuntime.navigation.value
    private fun waitFor(predicate: () -> Boolean) {
        try { compose.waitUntil(30_000, predicate) } catch (error: Throwable) {
            println("Navigation at failure: ${nav()}; error: ${EngineRuntime.navigationError.value}")
            screenshot("failure") // Retain the app before the activity rule tears it down.
            throw error
        }
    }
    private fun click(tag: String) {
        // performScrollTo scrolls only the nearest ancestor. Bring a nested
        // horizontal strip into the vertical viewport before scrolling its child.
        if (tag.startsWith("switch-") || tag.startsWith("close-") && tag != "close-all") {
            compose.onNodeWithTag("open-fit-tabs").performScrollTo()
        } else if (tag.startsWith("race-")) {
            compose.onNodeWithTag("race-filters").performScrollTo()
        }
        compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick()
        compose.waitForIdle()
    }
    private fun open(id: String) {
        click("mode-All fits")
        click("open-$id")
        waitFor { nav().activeId == id }
    }
    private fun create(name: String, hull: String = "Vexor"): String {
        val before = fits().map { it.id }.toSet()
        click("library-create")
        if (hull != "Vexor") compose.onNodeWithText(hull, useUnmergedTree = true).performClick()
        compose.onNodeWithTag("fit-name").performTextReplacement(name)
        compose.onNodeWithTag("fit-confirm").performClick()
        waitFor { fits().any { it.id !in before } && nav().activeId !in before && nav().activeId != null }
        return fits().single { it.id !in before }.id
    }
    private fun snapshot(): JSONObject {
        val rows = fits().map { fit ->
            val stats = JSONObject()
            val types = JSONObject()
            for ((key, value) in fit.stats) {
                stats.put(key, JSONObject().put("value", value.value.raw).put("unit", value.unit))
                types.put(key, value.value.javaClass.simpleName)
            }
            JSONObject().put("id", fit.id).put("revision", fit.revision).put("name", fit.name).put("ship", fit.ship)
                .put("stats", stats).put("types", types)
        }
        return JSONObject().put("fits", JSONArray(rows)).put("modified", JSONObject(EngineRuntime.modified.value))
            .put("open_ids", JSONArray(nav().openIds)).put("active_id", nav().activeId ?: JSONObject.NULL)
            .put("restore", nav().restore).put("hide_empty", nav().hideEmpty)
    }
    private fun screenshot(name: String) {
        compose.waitForIdle()
        InstrumentationRegistry.getInstrumentation().uiAutomation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(InstrumentationRegistry.getInstrumentation().uiAutomation
            .executeShellCommand("screencap -p /sdcard/Download/pyfa-b032-$name.png")).use { it.readBytes() }
    }
    private fun recentIds(): List<String> = compose.onAllNodes(SemanticsMatcher("fit cards") {
        it.config.getOrElse(SemanticsProperties.TestTag) { "" }.startsWith("fit-") &&
            it.config.getOrElse(SemanticsProperties.TestTag) { "" }.removePrefix("fit-") in fits().map { fit -> fit.id }
    }).fetchSemanticsNodes().map { it.config[SemanticsProperties.TestTag].removePrefix("fit-") }

    @Test fun organizationAndOpenViewsAcrossProcessesOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b032_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val runtime = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        assertTrue(runtime.getJSONObject("persistence").getBoolean("enabled"))
        val expectedCatalog = HullCatalog.decode(InstrumentationRegistry.getInstrumentation().context.assets
            .open("catalog-expected.json").bufferedReader().use { it.readText() })
        assertEquals(expectedCatalog, EngineRuntime.catalog.value)
        assertEquals(55, expectedCatalog.groups.size)
        assertEquals(437, expectedCatalog.hulls.size)
        checks += "independent_desktop_catalog"
        val initial = snapshot()
        val saved = File(context.noBackupFilesDir, "b032-expected.json")
        when (phase) {
            "prepare" -> {
                assertTrue(fits().isEmpty()) // B03.1's empty store survives, without clearing app data.
                assertTrue(nav().openIds.isEmpty())
                assertFalse(nav().restore)
                val a = create("Navigation same name")
                val b = create("Navigation same name")
                val c = create("Navigation command", "Vulture")
                assertEquals(listOf(a, b, c), nav().openIds)
                open(a)
                open(a)
                assertEquals(listOf(a, b, c), nav().openIds)
                val beforeNavigation = EngineRuntime.modified.value
                click("mode-Recent")
                assertEquals(listOf(c, b, a), recentIds())
                click("open-$a")
                waitFor { nav().activeId == a }
                assertEquals(beforeNavigation, EngineRuntime.modified.value)
                assertEquals(listOf(c, b, a), recentIds())
                checks += "opening_does_not_modify_recents"
                click("rename-$a")
                compose.onNodeWithTag("fit-name").performTextReplacement("探索 Δ navigation with a long fitting name")
                compose.onNodeWithTag("fit-confirm").performClick()
                waitFor { fits().single { it.id == a }.name.startsWith("探索") }
                compose.waitForIdle()
                assertEquals(listOf(a, c, b), recentIds())
                screenshot("recent")
                checks += "rename_updates_recents"

                click("mode-Hulls")
                compose.onNodeWithTag("group--1").performScrollTo().assertIsDisplayed()
                click("hide-empty")
                waitFor { nav().hideEmpty }
                compose.onNodeWithTag("group--1").assertDoesNotExist()
                click("group-26") // Cruiser; actual desktop catalogue ID.
                click("race-caldari")
                compose.onNodeWithTag("hull-626").assertDoesNotExist()
                compose.onNodeWithText("No hulls match these filters.").performScrollTo().assertIsDisplayed()
                click("race-gallente") // Multi-select, Gallente is now also visible.
                click("hull-626")
                compose.onNodeWithTag("fit-$a").performScrollTo().assertIsDisplayed()
                compose.onNodeWithTag("fit-$b").performScrollTo().assertIsDisplayed()
                compose.onNodeWithTag("fit-$c").assertDoesNotExist()
                compose.activityRule.scenario.recreate()
                compose.onNodeWithTag("hull-title").performScrollTo().assertTextEquals("Vexor")
                screenshot("hull")
                compose.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
                compose.onNodeWithTag("hull-626").performScrollTo().assertIsDisplayed()
                click("hull-back")
                click("hide-empty")
                waitFor { !nav().hideEmpty }
                click("group--1")
                click("hull-back")
                checks += "groups_races_empty_visibility_and_back"

                open(c)
                click("back-to-hull")
                compose.onNodeWithTag("hull-title").performScrollTo().assertTextEquals("Vulture")
                compose.onNodeWithTag("fit-$c").performScrollTo().assertIsDisplayed()
                compose.onNodeWithTag("fit-$a").assertDoesNotExist()
                checks += "back_to_correct_hull"
                // Search crosses hull/race filters and resolves by identity, including duplicate names.
                compose.onNodeWithTag("library-search").performScrollTo().performTextReplacement("same name")
                click("open-$b")
                waitFor { nav().activeId == b }
                assertEquals(b, (EngineRuntime.state.value as EngineState.Ready).fit.id)
                checks += "search_opens_intended_id"
                click("mode-All fits")
                click("close-$c") // Closing an inactive view does not change the selected fit.
                waitFor { c !in nav().openIds }
                assertEquals(b, nav().activeId)
                click("close-$b")
                waitFor { nav().activeId == a }
                assertEquals(listOf(a), nav().openIds)
                open(c)
                open(b)
                click("delete-$b")
                compose.onNodeWithTag("fit-confirm").performClick()
                waitFor { fits().none { it.id == b } && b !in nav().openIds }
                assertEquals(listOf(a, c), nav().openIds)
                assertEquals(c, nav().activeId)
                checks += "close_active_inactive_and_delete_open"
                click("restore-open-fits")
                waitFor { nav().restore }
                click("mode-Hulls")
                click("hull-back")
                click("hide-empty")
                waitFor { nav().hideEmpty }
                click("mode-All fits")
                click("switch-$a")
                waitFor { nav().activeId == a }
                compose.activityRule.scenario.recreate()
                assertEquals(listOf(a, c), nav().openIds)
                assertEquals(a, nav().activeId)
                compose.onNodeWithTag("open-fit-tabs").performScrollTo()
                compose.onNodeWithTag("switch-$a").performScrollTo().assertIsDisplayed()
                screenshot("open")
                saved.writeText(JSONObject().put("a", a).put("c", c).put("expected", snapshot()).toString())
                checks += "activity_recreation_and_restore_enabled"
                // Invalid view preferences must be rejected without overwriting them.
                val bad = File(context.cacheDir, "invalid-navigation.json")
                bad.writeText("{broken")
                try { NavigationStore(bad).load(); fail("Corrupt preferences were accepted") } catch (_: org.json.JSONException) { }
                assertEquals("{broken", bad.readText())
                checks += "corrupt_preferences_preserved"
            }
            "restored" -> {
                val data = JSONObject(saved.readText())
                val a = data.getString("a"); val c = data.getString("c")
                assertEquals(listOf(a, c), nav().openIds)
                assertEquals(a, nav().activeId)
                assertTrue(nav().restore && nav().hideEmpty)
                checks += "previous_set_and_active_restored"
                val modified = EngineRuntime.modified.value
                click("switch-$c")
                waitFor { nav().activeId == c }
                assertEquals(modified, EngineRuntime.modified.value)
                click("close-all")
                waitFor { nav().openIds.isEmpty() }
                assertTrue(EngineRuntime.state.value is EngineState.Empty)
                assertEquals(2, fits().size)
                compose.onNodeWithTag("no-open-fits").performScrollTo().assertIsDisplayed()
                screenshot("closed")
                open(c)
                click("restore-open-fits")
                waitFor { !nav().restore }
                checks += "close_all_preserves_saved_fits_and_disable_restore"
            }
            "disabled" -> {
                assertFalse(nav().restore)
                assertTrue(nav().hideEmpty && nav().openIds.isEmpty())
                assertTrue(EngineRuntime.state.value is EngineState.Empty)
                assertEquals(2, fits().size)
                click("restore-open-fits")
                waitFor { nav().restore }
                open(JSONObject(saved.readText()).getString("a"))
                click("close-all")
                waitFor { nav().openIds.isEmpty() }
                compose.activityRule.scenario.recreate()
                assertTrue(nav().openIds.isEmpty() && EngineRuntime.state.value is EngineState.Empty)
                checks += "disabled_restart_keeps_library_and_enabled_close_all"
            }
            "closed" -> {
                assertTrue(nav().restore && nav().hideEmpty && nav().openIds.isEmpty())
                assertTrue(EngineRuntime.state.value is EngineState.Empty)
                assertEquals(2, fits().size)
                open(JSONObject(saved.readText()).getString("a"))
                assertEquals(1, nav().openIds.size)
                checks += "empty_open_set_stays_empty_after_restart"
            }
            else -> error("Unknown phase")
        }
        assertNull(EngineRuntime.navigationError.value)
        val report = JSONObject().put("task", "B03.2").put("phase", phase).put("pid", Process.myPid())
            .put("runtime", runtime).put("initial", initial).put("final", snapshot())
            .put("checks", JSONArray(checks)).put("catalog_groups", 55).put("catalog_hulls", 437)
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        val descriptors = automation.executeShellCommandRw("dd of=/sdcard/Download/pyfa-b032-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(report.toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
}
