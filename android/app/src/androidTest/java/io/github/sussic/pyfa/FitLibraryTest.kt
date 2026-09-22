package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.ParcelFileDescriptor
import android.os.Process
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
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
class FitLibraryTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val observations = JSONArray()
    private val requests = JSONArray()
    private fun fits() = EngineRuntime.library.value
    private fun fit(id: String) = fits().single { it.id == id }
    private fun syncUi() {
        // A worker future can finish before its UI StateFlow collector runs.
        // Advance the Compose clock on the UI thread before observing the tree.
        compose.mainClock.advanceTimeByFrame()
        compose.waitForIdle()
    }
    private fun click(tag: String) { syncUi(); compose.onNodeWithTag(tag).performScrollTo().performClick(); syncUi() }
    private fun waitFor(predicate: () -> Boolean) { compose.waitUntil(30_000, predicate); syncUi() }
    private fun send(operation: BridgeOperation, vararg ids: String): BridgeResponse {
        val result = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
        syncUi()
        assertTrue(result.error?.message, result.isSuccess)
        requests.put(JSONObject().put("operation", operation.javaClass.simpleName)
            .put("fits", JSONArray(result.fits.map(::snapshotJson))))
        return result
    }
    private fun record(label: String) {
        val response = send(BridgeOperation.Snapshot())
        observations.put(JSONObject().put("label", label).put("fits", JSONArray(response.fits.map(::snapshotJson))))
    }
    private fun create(name: String): String {
        val before = fits().map { it.id }.toSet()
        click("library-create")
        compose.onNodeWithTag("fit-name").performTextReplacement(name)
        compose.onNodeWithTag("fit-confirm").performClick()
        waitFor { fits().any { it.id !in before && it.name == name } }
        return fits().single { it.id !in before }.id
    }
    private fun delete(id: String) {
        click("delete-$id")
        compose.onNodeWithTag("fit-confirm").performClick()
        waitFor { fits().none { it.id == id } }
    }
    private fun baseline(id: String, fixture: String = "projection", stage: String = "initial") {
        val golden = JSONObject(InstrumentationRegistry.getInstrumentation().context.assets
            .open("$fixture-expected.json").bufferedReader().use { it.readText() })
            .getJSONObject("states").getJSONObject(stage).getJSONObject("target")
        val actual = fit(id)
        assertEquals(39, actual.stats.size)
        for (key in golden.keys()) {
            val expected = golden.getJSONObject(key)
            val stat = actual.stats.getValue(key)
            assertEquals(expected.getString("unit"), stat.unit)
            when (expected.get("value")) {
                is Boolean -> assertTrue(stat.value is StatValue.BooleanValue)
                is Int, is Long -> assertTrue("$key integer", stat.value is StatValue.Integer)
                is Double -> assertTrue("$key decimal", stat.value is StatValue.Decimal)
                else -> assertTrue(stat.value is StatValue.Text)
            }
            compare(expected.get("value"), stat.value.raw, "baseline.$key")
        }
    }
    @Test fun libraryLifecycleAcrossProcessesOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b03_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        syncUi()
        compose.waitUntilExactlyOneExists(hasTestTag("library-create"), timeoutMillis = 30_000)
        val runtimeStart = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("enabled"))
        val saved = File(context.noBackupFilesDir, "b03-test-expected.json")
        record("start")
        when (phase) {
            "prepare" -> {
                val originalIds = fits().map { it.id }.toSet()
                assertEquals(9, originalIds.size) // B02's retained graph, no reinstall or clear-data.
                val created = create("探索 Δ fit")
                baseline(created)
                click("rename-$created")
                compose.onNodeWithTag("fit-name").performTextReplacement("探索 Δ renamed with a long fitting name")
                compose.activityRule.scenario.recreate()
                compose.onNodeWithTag("fit-name").assertTextContains("探索 Δ renamed with a long fitting name")
                compose.onNodeWithTag("fit-name").performClick()
                compose.waitUntil(10_000) { compose.activity.window.decorView.rootWindowInsets?.isVisible(android.view.WindowInsets.Type.ime()) == true }
                screenshot("dialog")
                compose.onNodeWithTag("fit-confirm").performClick()
                waitFor { fit(created).name.endsWith("fitting name") }
                val beforeCopy = fits().map { it.id }.toSet()
                click("duplicate-$created")
                compose.onNodeWithTag("fit-name").performTextReplacement("B03 independent copy")
                compose.onNodeWithTag("fit-confirm").performClick()
                waitFor { fits().size == beforeCopy.size + 1 }
                val copy = fits().single { it.id !in beforeCopy }.id
                baseline(copy)
                send(BridgeOperation.SetCharges(copy, listOf(0, 1), "Iron Charge M"), copy)
                assertEquals("Antimatter Charge M", fit(created).modules.first().charge)
                assertEquals("Iron Charge M", fit(copy).modules.first().charge)
                compose.onNodeWithTag("library-search").performScrollTo().performTextReplacement("no match 73519")
                compose.onNodeWithText("No matching fits.").performScrollTo().assertIsDisplayed()
                compose.onNodeWithTag("library-search").performTextReplacement("independent")
                click("open-$copy")
                waitFor { (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id == copy }
                screenshot("library")
                click("delete-$copy")
                compose.onNodeWithTag("fit-cancel").performClick()
                assertTrue(fits().any { it.id == copy })
                compose.onNodeWithTag("library-search").performScrollTo().performTextReplacement("")
                delete(created)
                send(BridgeOperation.SetCharges(copy, listOf(0, 1), "Antimatter Charge M"), copy)
                val second = create("B03 second recipient")
                for (kind in listOf("Celestis", "Vulture")) {
                    val source = EngineRuntime.createFromExample(context, kind, "B03 $kind source").get(120, TimeUnit.SECONDS).fits.single().id
                    for (target in listOf(copy, second)) {
                        if (kind == "Celestis") send(BridgeOperation.AddProjection(source, target, 0.0), source, target)
                        else send(BridgeOperation.AddCommand(source, target), source, target)
                    }
                    baseline(copy, if (kind == "Celestis") "projection" else "command",
                        if (kind == "Celestis") "applied_zero" else "applied")
                    baseline(second, if (kind == "Celestis") "projection" else "command",
                        if (kind == "Celestis") "applied_zero" else "applied")
                    record("$kind-linked")
                    delete(source)
                    baseline(copy); baseline(second)
                    assertTrue(fit(copy).projections.isEmpty() && fit(copy).commands.isEmpty())
                    record("$kind-deleted")
                }
                assertTrue(fits().map { it.id }.containsAll(originalIds))
                val expected = JSONArray(fits().map(::snapshotJson))
                saved.writeText(expected.toString(), Charsets.UTF_8)
            }
            "reopen_delete" -> {
                compare(JSONArray(saved.readText(Charsets.UTF_8)), JSONArray(fits().map(::snapshotJson)), "restart")
                assertEquals(11, fits().size)
                for (id in fits().map { it.id }.dropLast(1)) send(BridgeOperation.DeleteFit(id, true), id)
                delete(fits().single().id)
                assertTrue(EngineRuntime.state.value is EngineState.Empty)
                compose.onNodeWithTag("library-empty").performScrollTo().assertIsDisplayed()
                screenshot("empty")
            }
            "empty_reopen" -> {
                assertTrue(fits().isEmpty())
                assertTrue(runtimeStart.isNull("sample_id"))
                assertTrue(EngineRuntime.state.value is EngineState.Empty)
                compose.onNodeWithTag("library-empty").performScrollTo().assertIsDisplayed()
                val newFit = create("After empty restart")
                baseline(newFit)
                delete(newFit)
                assertTrue(fits().isEmpty())
                saved.delete()
            }
            else -> error("Unknown phase")
        }
        record("end")
        val runtimeEnd = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        val report = JSONObject().put("task", "B03.1").put("phase", phase).put("pid", Process.myPid())
            .put("runtime_start", runtimeStart).put("runtime_end", runtimeEnd)
            .put("observations", observations).put("requests", requests)
        retain(report, "/sdcard/Download/pyfa-b03-$phase.json")
    }
    private fun screenshot(name: String) {
        compose.waitForIdle()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        // WindowInsets reports the IME visible before its system animation ends.
        // Wait for accessibility idle so the retained image includes the keyboard.
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b03-$name.png")).use { it.readBytes() }
    }
    private fun readShellFile(path: String): String = ParcelFileDescriptor.AutoCloseInputStream(
        InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommand("cat $path")
    ).use { it.readBytes().toString(Charsets.UTF_8) }
    private fun snapshotJson(fit: FitSnapshot): JSONObject {
        val stats = JSONObject()
        for ((key, value) in fit.stats) stats.put(key, JSONObject().put("value", value.value.raw).put("unit", value.unit))
        val types = JSONObject()
        for ((key, value) in fit.stats) types.put(key, when (value.value) {
            is StatValue.Integer -> "integer"
            is StatValue.Decimal -> "decimal"
            is StatValue.BooleanValue -> "boolean"
            is StatValue.Text -> "string"
        })
        val skills = JSONObject()
        for ((name, level) in fit.skills) skills.put(name, level ?: JSONObject.NULL)
        return JSONObject().put("id", fit.id).put("revision", fit.revision).put("name", fit.name).put("ship", fit.ship)
            .put("stats", stats).put("scalar_types", types).put("skills", skills)
            .put("modules", JSONArray(fit.modules.map { JSONObject().put("index", it.index).put("name", it.name)
                .put("state", it.state.name).put("charge", it.charge ?: JSONObject.NULL) }))
            .put("implants", JSONArray(fit.implants.map { JSONObject().put("name", it.name).put("slot", it.slot).put("active", it.active) }))
            .put("projections", JSONArray(fit.projections.map { JSONObject().put("source_id", it.sourceId)
                .put("range_m", it.rangeM ?: JSONObject.NULL).put("active", it.active).put("amount", it.amount) }))
            .put("commands", JSONArray(fit.commands.map { JSONObject().put("source_id", it.sourceId).put("active", it.active) }))
    }

    private fun retain(actual: JSONObject, output: String) {
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        if (Build.VERSION.SDK_INT >= 31) {
            val descriptors = automation.executeShellCommandRw("dd of=$output")
            ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
                ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(actual.toString(2).toByteArray(Charsets.UTF_8)) }
                completion.readBytes()
            }
        } else error("The native evidence transport requires API 31 or later")
        compare(actual, JSONObject(readShellFile(output)), "retained_native_evidence")
    }

    private fun compare(expected: Any, actual: Any, path: String) {
        when (expected) {
            is JSONObject -> {
                assertTrue("$path must be an object", actual is JSONObject)
                actual as JSONObject
                assertEquals("$path keys", expected.keys().asSequence().toSet(), actual.keys().asSequence().toSet())
                for (key in expected.keys()) compare(expected.get(key), actual.get(key), "$path.$key")
            }
            is JSONArray -> {
                assertTrue("$path must be an array", actual is JSONArray)
                actual as JSONArray
                assertEquals("$path length", expected.length(), actual.length())
                for (index in 0 until expected.length()) compare(expected.get(index), actual.get(index), "$path[$index]")
            }
            is Number -> {
                assertTrue("$path must be numeric", actual is Number)
                actual as Number
                if ((expected is Int || expected is Long) && (actual is Int || actual is Long)) {
                    assertEquals(path, expected.toLong(), actual.toLong())
                } else {
                    // Receipt JSON normalizes integral decimals; independent
                    // oracle scalar types are checked before this comparison.
                    val left = expected.toDouble()
                    val right = actual.toDouble()
                    assertTrue("$path must be finite", left.isFinite() && right.isFinite())
                    assertEquals(path, left, right, maxOf(1e-9, 1e-10 * maxOf(abs(left), abs(right))))
                }
            }
            else -> assertEquals(path, expected, actual)
        }
    }

}
