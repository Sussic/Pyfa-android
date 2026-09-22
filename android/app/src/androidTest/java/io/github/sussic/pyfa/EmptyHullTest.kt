package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.os.Process
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.concurrent.TimeUnit
import kotlin.math.abs
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
@OptIn(ExperimentalTestApi::class)
class EmptyHullTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[FitLibraryModel::class.java]
    private fun fits() = EngineRuntime.library.value
    private fun fit(id: String) = fits().single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun click(tag: String) {
        sync()
        val node = compose.onNodeWithTag(tag)
        // Dialog action buttons are outside their scrolling content.
        if (tag !in setOf("empty-fit-confirm", "empty-fit-cancel", "fit-confirm", "fit-cancel")) node.performScrollTo()
        node.assertIsDisplayed().performClick(); sync()
    }
    private fun edit(tag: String, value: String) {
        val node = compose.onNodeWithTag(tag)
        if (tag != "fit-name") node.performScrollTo()
        node.performTextReplacement(value); sync()
    }
    private fun waitFor(predicate: () -> Boolean) { compose.waitUntil(30_000, predicate); sync() }
    private fun spec(hull: String, name: String = "Empty $hull") = FitSpec(name, hull, 5, false,
        DamagePattern(25.0, 25.0, 25.0, 25.0), Security(SystemSecurity.HISEC, 0.0), emptyList(), emptyList())
    private fun send(operation: BridgeOperation, vararg ids: String): BridgeResponse {
        val response = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
        assertTrue(response.error?.message, response.isSuccess)
        return response
    }
    private fun snapshot(fit: FitSnapshot): JSONObject {
        val stats = JSONObject()
        val types = JSONObject()
        for ((name, stat) in fit.stats) {
            stats.put(name, JSONObject().put("value", stat.value.raw).put("unit", stat.unit))
            types.put(name, when (stat.value) {
                is StatValue.Integer -> "integer"
                is StatValue.Decimal -> "decimal"
                is StatValue.BooleanValue -> "boolean"
                is StatValue.Text -> "text"
                StatValue.Unavailable -> "null"
            })
        }
        return JSONObject().put("id", fit.id).put("revision", fit.revision).put("name", fit.name).put("ship", fit.ship)
            .put("stats", stats).put("scalar_types", types)
            .put("modules", JSONArray(fit.modules.map { JSONObject().put("index", it.index).put("name", it.name)
                .put("state", it.state.name).put("charge", it.charge ?: JSONObject.NULL) }))
            .put("skills", JSONObject(fit.skills)).put("implants", JSONArray(fit.implants.map { JSONObject()
                .put("name", it.name).put("slot", it.slot).put("active", it.active) }))
            .put("projections", JSONArray(fit.projections.map { JSONObject().put("source_id", it.sourceId)
                .put("range_m", it.rangeM ?: JSONObject.NULL).put("active", it.active).put("amount", it.amount) }))
            .put("commands", JSONArray(fit.commands.map { JSONObject().put("source_id", it.sourceId).put("active", it.active) }))
    }
    private fun library() = JSONArray(fits().map(::snapshot))
    private fun compare(expected: Any, actual: Any, path: String) {
        when (expected) {
            is JSONObject -> {
                assertTrue(path, actual is JSONObject); actual as JSONObject
                assertEquals(path, expected.keys().asSequence().toSet(), actual.keys().asSequence().toSet())
                for (key in expected.keys()) compare(expected.get(key), actual.get(key), "$path.$key")
            }
            is JSONArray -> {
                assertTrue(path, actual is JSONArray); actual as JSONArray
                assertEquals(path, expected.length(), actual.length())
                for (i in 0 until expected.length()) compare(expected.get(i), actual.get(i), "$path[$i]")
            }
            is Number -> {
                assertTrue(path, actual is Number); actual as Number
                // Report JSON normalizes integral decimals. DTO types are checked separately below.
                val left = expected.toDouble(); val right = actual.toDouble()
                assertTrue(path, left.isFinite() && right.isFinite())
                assertEquals(path, left, right, maxOf(1e-9, 1e-10 * maxOf(abs(left), abs(right))))
            }
            else -> assertEquals(path, expected, actual)
        }
    }
    private fun checkHull(fit: FitSnapshot, oracle: JSONObject) {
        assertEquals(oracle.getString("name"), fit.ship)
        assertTrue(fit.modules.isEmpty() && fit.implants.isEmpty() && fit.projections.isEmpty() && fit.commands.isEmpty())
        val stats = oracle.getJSONObject("stats")
        assertEquals(39, fit.stats.size)
        assertEquals(stats.keys().asSequence().toSet(), fit.stats.keys)
        for (name in stats.keys()) {
            val expected = stats.getJSONObject(name)
            val actual = fit.stats.getValue(name)
            assertEquals(expected.getString("unit"), actual.unit)
            val scalar = expected.get("value")
            when (scalar) {
                JSONObject.NULL -> assertEquals(StatValue.Unavailable, actual.value)
                is Boolean -> assertTrue(name, actual.value is StatValue.BooleanValue)
                is Int, is Long -> assertTrue(name, actual.value is StatValue.Integer)
                is Double -> assertTrue(name, actual.value is StatValue.Decimal)
                is String -> assertTrue(name, actual.value is StatValue.Text)
                else -> error("Unknown reference scalar")
            }
            compare(scalar, actual.value.raw, "${fit.ship}.$name")
        }
        assertEquals("Unavailable", formatStat(fit.stats.getValue("gun_optimal")))
        assertEquals(0.0, fit.stats.getValue("total_dps").value.numberOrNull()!!, 0.0)
    }
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b0421-$name.png")).use { it.readBytes() }
    }
    private fun retain(report: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b0421-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(report.toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }

    @Test fun allEmptyHullsAndCreationSurviveRestartOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b0421_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        sync()
        val fixture = JSONObject(InstrumentationRegistry.getInstrumentation().context.assets.open("empty-hulls-expected.json")
            .bufferedReader().use { it.readText() })
        val hulls = fixture.getJSONArray("hulls").let { rows -> (0 until rows.length()).map { rows.getJSONObject(it) } }
        val byName = hulls.associateBy { it.getString("name") }
        val runtimeStart = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("opened_existing"))
        val before = library()
        val observed = JSONArray()
        val rejected = JSONArray()
        val saved = File(context.noBackupFilesDir, "b0421-test-expected.json")
        try {
            when (phase) {
                "prepare" -> {
                    assertEquals(437, hulls.size)
                    assertEquals(hulls.map { it.getInt("id") }.toSet(), EngineRuntime.catalog.value.hulls.map { it.id }.toSet())
                    val modified = EngineRuntime.modified.value
                    for (oracle in hulls) {
                        val created = send(BridgeOperation.CreateFit(spec(oracle.getString("name")))).fits.single()
                        checkHull(created, oracle)
                        observed.put(JSONObject().put("hull_id", oracle.getInt("id")).put("category", oracle.getString("category"))
                            .put("fit", snapshot(created)))
                        send(BridgeOperation.DeleteFit(created.id, false), created.id)
                    }
                    compare(before, library(), "existing_fits")
                    assertEquals(modified, EngineRuntime.modified.value)
                    sync()
                    click("library-create-empty")
                    click("empty-hull-next")
                    assertEquals(1, model.newHullPage.value)
                    compose.activityRule.scenario.recreate(); sync()
                    assertEquals(1, model.newHullPage.value)
                    click("empty-hull-previous")
                    edit("empty-hull-search", "zz-no-such-hull")
                    compose.onNodeWithTag("empty-hull-no-results").assertExists()
                    edit("empty-hull-search", "rifter")
                    click("empty-hull-${byName.getValue("Rifter").getInt("id")}")
                    edit("empty-fit-name", "")
                    compose.onNodeWithTag("empty-fit-confirm").assertIsNotEnabled()
                    edit("empty-fit-name", "探索 Δ empty Rifter")
                    compose.activityRule.scenario.recreate(); sync()
                    assertEquals("Rifter", model.newHull.value)
                    compose.onNodeWithTag("empty-fit-name").assertTextContains("探索 Δ empty Rifter")
                    compose.onNodeWithTag("empty-hull-search").assertTextContains("rifter")
                    // Dismiss the keyboard without cancelling the dialog.
                    click("empty-hull-${byName.getValue("Rifter").getInt("id")}")
                    compose.onNodeWithTag("empty-fit-name").performScrollTo()
                    screenshot("picker")
                    click("empty-fit-confirm")
                    waitFor { fits().any { it.name == "探索 Δ empty Rifter" } && model.action.value == null }
                    val ship = fits().single { it.name == "探索 Δ empty Rifter" }
                    checkHull(ship, byName.getValue("Rifter"))
                    waitFor { (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id == ship.id }
                    compose.onNodeWithText(context.getString(R.string.gun_optimal) + ": Unavailable").performScrollTo().assertIsDisplayed()
                    screenshot("ship")
                    click("duplicate-${ship.id}")
                    edit("fit-name", "B04 empty independent copy")
                    click("fit-confirm")
                    waitFor { fits().any { it.name == "B04 empty independent copy" } }
                    val copy = fits().single { it.name == "B04 empty independent copy" }
                    send(BridgeOperation.RenameFit(copy.id, "B04 renamed empty copy"), copy.id)
                    assertEquals("探索 Δ empty Rifter", fit(ship.id).name)
                    checkHull(fit(copy.id), byName.getValue("Rifter"))

                    // Enter the same creation flow from the actual hull browser.
                    click("mode-Hulls")
                    if (EngineRuntime.navigation.value.hideEmpty) click("hide-empty")
                    val structure = EngineRuntime.catalog.value.hulls.single { it.name == "Astrahus" }
                    click("group-${structure.groupId}")
                    click("hull-${structure.id}")
                    click("create-selected-hull")
                    assertEquals("Astrahus", model.newHull.value)
                    click("empty-fit-cancel")
                    assertEquals(before.length() + 2, fits().size)
                    click("create-selected-hull")
                    edit("empty-fit-name", "B04 empty Astrahus")
                    click("empty-fit-confirm")
                    waitFor { fits().any { it.name == "B04 empty Astrahus" } }
                    val citadel = fits().single { it.name == "B04 empty Astrahus" }
                    checkHull(citadel, byName.getValue("Astrahus"))
                    waitFor { (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id == citadel.id }
                    compose.onNodeWithTag("back-to-hull").performScrollTo().assertIsDisplayed()
                    screenshot("structure")

                    val committed = library()
                    val generation = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(30, TimeUnit.SECONDS))
                        .getJSONObject("persistence").getLong("generation")
                    for ((label, operation) in listOf(
                        "non_hull" to BridgeOperation.CreateFit(spec("Dual 150mm Railgun II")),
                        "unknown_hull" to BridgeOperation.CreateFit(spec("No such hull 123456")),
                        "empty_charge_index" to BridgeOperation.SetCharges(ship.id, listOf(0), "Iron Charge M"),
                        "empty_state_index" to BridgeOperation.SetModuleStates(ship.id, listOf(0), ModuleState.ACTIVE),
                    )) {
                        val response = EngineRuntime.request(context, operation,
                            if (operation is BridgeOperation.CreateFit) emptyMap() else mapOf(ship.id to fit(ship.id).revision))
                            .get(120, TimeUnit.SECONDS)
                        assertFalse(response.isSuccess)
                        assertEquals(BridgeErrorCode.INVALID_EDIT, response.error?.code)
                        compare(committed, library(), label)
                        rejected.put(JSONObject().put("label", label).put("code", response.error?.code?.name).put("fits", library()))
                    }
                    val stale = EngineRuntime.request(context, BridgeOperation.RenameFit(copy.id, "Stale"),
                        mapOf(copy.id to 1L)).get(120, TimeUnit.SECONDS)
                    assertEquals(BridgeErrorCode.REVISION_CONFLICT, stale.error?.code)
                    compare(committed, library(), "stale")
                    rejected.put(JSONObject().put("label", "stale_revision").put("code", stale.error?.code?.name).put("fits", library()))
                    assertEquals(generation, JSONObject(EngineRuntime.bridgeDiagnostics(context).get(30, TimeUnit.SECONDS))
                        .getJSONObject("persistence").getLong("generation"))
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    EngineRuntime.selectFit(context, copy.id).get(30, TimeUnit.SECONDS)
                    saved.writeText(JSONObject().put("fits", library()).put("prior", before).put("active_id", copy.id)
                        .put("new_ids", JSONArray(listOf(ship.id, copy.id, citadel.id))).toString(), Charsets.UTF_8)
                }
                "restored" -> {
                    val expected = JSONObject(saved.readText(Charsets.UTF_8))
                    compare(expected.getJSONArray("fits"), library(), "process_restart")
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    val ids = expected.getJSONArray("new_ids")
                    for (i in 0 until ids.length()) {
                        val item = fit(ids.getString(i))
                        checkHull(item, byName.getValue(item.ship))
                        click("open-${item.id}")
                        waitFor { (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id == item.id }
                        compose.onNodeWithText(context.getString(R.string.gun_optimal) + ": Unavailable").performScrollTo().assertIsDisplayed()
                    }
                    screenshot("restored")
                }
                else -> error("Unknown phase")
            }
            retain(JSONObject().put("task", "B04.2.1").put("phase", phase).put("pid", Process.myPid())
                .put("runtime_start", runtimeStart)
                .put("runtime_end", JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS)))
                .put("before", before).put("after", library()).put("hulls", observed).put("rejections", rejected)
                .put("saved", JSONObject(saved.readText(Charsets.UTF_8)))
                .put("checks", JSONArray(if (phase == "prepare") listOf("complete_hulls", "prior_fits_unchanged", "picker_pagination",
                    "picker_search_and_empty", "picker_recreation", "blank_name_rejected", "ship_creation", "independent_copy",
                    "hull_browser_structure_creation", "cancel_unchanged", "failed_edits_unchanged", "explicit_absence")
                    else listOf("fresh_process_restore", "identities_inputs_values_retained", "reopen_each_fit", "explicit_absence"))), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
