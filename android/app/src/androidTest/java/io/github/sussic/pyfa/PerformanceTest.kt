package io.github.sussic.pyfa

import android.content.pm.PackageManager
import android.os.Build
import android.os.ParcelFileDescriptor
import android.os.Process
import android.os.SystemClock
import android.provider.Settings
import androidx.test.core.app.ActivityScenario
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import kotlin.math.abs
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Separate fresh-process invocation; excluded from the five-test functional suite. */
@RunWith(AndroidJUnit4::class)
class PerformanceTest {
    @Test
    fun repeatedEditsMatchDesktopWithStableFitCountOffline() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,
            context.checkSelfPermission(android.Manifest.permission.INTERNET))
        assertTrue("Run this measurement in its own fresh process", EngineRuntime.state.value is EngineState.Loading)
        val startupFile = File(context.filesDir, "a10-startup.json")
        startupFile.delete()
        val memory = JSONObject().put("before_activity", EngineRuntime.memorySnapshot())
        ActivityScenario.launch(MainActivity::class.java).use {
            EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
            val deadline = SystemClock.elapsedRealtime() + 120000
            while (!startupFile.isFile && SystemClock.elapsedRealtime() < deadline) SystemClock.sleep(25)
            assertTrue("Ready UI must report a complete startup receipt", startupFile.isFile)
            val startup = JSONObject(startupFile.readText())
            assertEquals(Process.myPid(), startup.getInt("pid"))
            instrumentation.waitForIdleSync()
            memory.put("single_fit_ready", EngineRuntime.memorySnapshot())

            val names = mapOf("ammunition" to "vexor", "projection" to "projection", "command" to "command")
            val expected = names.mapValues { (_, name) ->
                instrumentation.context.assets.open("$name-expected.json").bufferedReader().use { JSONObject(it.readText()) }
            }
            val setup = JSONObject()
            val setupTimes = JSONObject()
            val operations = linkedMapOf(
                "ammunition" to listOf("iron_ammunition", "restored"),
                "projection_range" to listOf("falloff", "applied_zero"),
                "projection_link" to listOf("removed", "applied_zero"),
                "command_charge" to listOf("harmonizing", "extension_restored"),
                "command_link" to listOf("link_inactive", "link_active"),
            )
            val measurements = JSONObject()
            for ((kind, count) in listOf("ammunition" to 1, "projection" to 5, "command" to 9)) {
                val begin = SystemClock.elapsedRealtimeNanos()
                val result = JSONObject(EngineRuntime.prepareBenchmark(context, kind).get(120, TimeUnit.SECONDS))
                setupTimes.put(kind, (SystemClock.elapsedRealtimeNanos() - begin) / 1e6)
                assertEquals(count, result.getInt("retained_fit_count"))
                val golden = expected.getValue(kind)
                for (key in listOf("inputs", "dataset_metadata", "eos_settings", "database_logical_sha256", "source_data_sha256")) {
                    compare(golden.get(key), result.get(key), "setup.$kind.$key")
                }
                assertEquals(golden.getString("source_commit"), result.getString("desktop_source_commit"))
                val bytes = instrumentation.context.assets.open("${names.getValue(kind)}-expected.json").use { it.readBytes() }
                val digest = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
                assertEquals(digest, result.getString("desktop_fixture_sha256"))
                assertEquals(0, result.getJSONArray("desktop_import_attempts").length())
                checkSnapshot(golden, result)
                setup.put(kind, result)
                memory.put("after_${kind}_setup", EngineRuntime.memorySnapshot())
                for ((operation, stages) in operations.filterKeys { it.substringBefore("_") == kind }) {
                    val samples = JSONArray()
                    val warmups = JSONArray()
                    val actualStates = JSONObject()
                    for (i in 0 until 24) {
                        // Includes submission, worker queue, JNI, mutation, refreshed
                        // snapshots of every role, Python JSON and Kotlin JSON parse.
                        val begin = SystemClock.elapsedRealtimeNanos()
                        val result = JSONObject(EngineRuntime.stepBenchmark(operation).get(120, TimeUnit.SECONDS))
                        val elapsed = (SystemClock.elapsedRealtimeNanos() - begin) / 1e6
                        // Independent expected data and validation are outside timing.
                        assertTrue(elapsed.isFinite() && elapsed > 0)
                        assertEquals(count, result.getInt("retained_fit_count"))
                        assertEquals(stages[i % 2], result.getString("stage"))
                        checkSnapshot(expected.getValue(result.getString("kind")), result)
                        if (i < 4) warmups.put(elapsed) else samples.put(elapsed)
                        actualStates.put(result.getString("stage"), result)
                    }
                    measurements.put(operation, JSONObject().put("warmup_ms", warmups)
                        .put("samples_ms", samples).put("actual_states", actualStates)
                        .put("checked_snapshots", 24).put("retained_fit_count", count))
                    memory.put("after_$operation", EngineRuntime.memorySnapshot())
                }
            }
            val report = JSONObject().put("task", "A10").put("pid", Process.myPid())
                .put("instrumented_process", true).put("airplane_mode", true)
                .put("startup", startup).put("setup", setup).put("setup_ms", setupTimes)
                .put("operations", measurements).put("memory", memory)
                .put("all_snapshots_matched_desktop", true).put("retained_fit_count", 9)
            retain(report, "/sdcard/Download/pyfa-a10-performance.json")
        }
    }

    private fun checkSnapshot(golden: JSONObject, result: JSONObject) {
        val kind = result.getString("kind")
        val stage = result.getString("stage")
        val states = golden.getJSONObject("states")
        val actual = result.getJSONObject("stats")
        if (kind == "ammunition") {
            assertEquals(setOf("single"), actual.keys().asSequence().toSet())
            assertEquals(38, actual.getJSONObject("single").length())
            compare(states.get(stage), actual.get("single"), "$kind.$stage")
        } else {
            assertEquals(setOf("source", "first", "second", "unlinked"), actual.keys().asSequence().toSet())
            for (role in listOf("source", "first", "second", "unlinked")) {
                val state = if (role == "unlinked") "initial" else stage
                val goldenRole = if (role == "source") "source" else "target"
                assertEquals(39, actual.getJSONObject(role).length())
                compare(states.getJSONObject(state).get(goldenRole), actual.get(role), "$kind.$stage.$role")
            }
            val linked = stage !in setOf("removed", "link_inactive")
            assertLinks(result.getJSONObject("links"), linked, linked, "$kind.$stage")
            if (kind == "command") {
                val pending = JSONObject()
                for (role in listOf("source", "first", "second", "unlinked")) pending.put(role, 0)
                compare(pending, result.get("pending_command_bonuses"), "$kind.$stage.pending")
            }
        }
    }

    private fun assertLinks(actual: JSONObject, first: Boolean, second: Boolean, path: String) {
        val recipients = JSONObject()
        for ((name, linked) in mapOf("first" to first, "second" to second, "unlinked" to false)) {
            recipients.put(name, JSONObject().put("count", if (linked) 1 else 0)
                .put("forward", linked).put("reverse", linked))
        }
        val expected = JSONObject().put("source_count", (if (first) 1 else 0) + (if (second) 1 else 0))
            .put("recipients", recipients)
        compare(expected, actual, "$path.links")
    }

    private fun retain(actual: JSONObject, output: String) {
        // This report contains actual native values, not only a passed counter.
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        // UiAutomation uses Runtime.exec(String), which does not parse shell
        // quoting/redirection. Feed bytes directly to a shell-owned writer.
        // The native evidence suite targets API 36; this transport needs 31+.
        if (Build.VERSION.SDK_INT >= 31) {
            val descriptors = automation.executeShellCommandRw("dd of=$output")
            ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
                ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { input ->
                    input.write(actual.toString(2).toByteArray(Charsets.UTF_8))
                }
                completion.readBytes() // Wait for dd to finish, without stdout backpressure.
            }
        } else {
            throw IllegalStateException("The native evidence transport requires API 31 or later")
        }
        val retained = ParcelFileDescriptor.AutoCloseInputStream(
            automation.executeShellCommand("cat $output"),
        ).use { it.readBytes().toString(Charsets.UTF_8) }
        compare(actual, JSONObject(retained), "retained_native_evidence")
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
                for (i in 0 until expected.length()) compare(expected.get(i), actual.get(i), "$path[$i]")
            }
            is Number -> {
                assertTrue("$path must be numeric", actual is Number)
                if (expected is Int || expected is Long) {
                    assertTrue("$path must be an integer", actual is Int || actual is Long)
                    assertEquals(path, expected.toLong(), (actual as Number).toLong())
                } else {
                    val left = expected.toDouble()
                    val right = (actual as Number).toDouble()
                    assertTrue("$path must be finite", left.isFinite() && right.isFinite())
                    val tolerance = maxOf(1e-9, 1e-10 * maxOf(abs(left), abs(right)))
                    assertEquals(path, left, right, tolerance)
                }
            }
            else -> assertEquals(path, expected, actual)
        }
    }
}
