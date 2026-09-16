package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.ParcelFileDescriptor
import android.provider.Settings
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import kotlin.math.abs
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class EngineParityTest {
    @Test
    fun bundledEngineMatchesIndependentDesktopAmmunitionStatesOffline() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val fixtureBytes = instrumentation.context.assets.open("vexor-expected.json").use { it.readBytes() }
        val expected = JSONObject(fixtureBytes.toString(Charsets.UTF_8))
        val actual = JSONObject(EngineRuntime.verifyAmmunition(context).get(120, TimeUnit.SECONDS))
        for (key in listOf("states", "inputs", "dataset_metadata", "eos_settings", "resolved_item_ids",
            "database_logical_sha256", "source_data_sha256")) {
            compare(expected.get(key), actual.get(key), key)
        }
        assertEquals(expected.getString("source_commit"), actual.getString("desktop_source_commit"))
        val fixtureHash = MessageDigest.getInstance("SHA-256").digest(fixtureBytes)
            .joinToString("") { "%02x".format(it) }
        assertEquals(fixtureHash, actual.getString("desktop_fixture_sha256"))
        assertEquals(3, actual.getJSONObject("states").length())
        for (state in listOf("initial", "iron_ammunition", "restored")) {
            assertEquals(38, actual.getJSONObject("states").getJSONObject(state).length())
        }
        compare(JSONObject("""{"logbook":"1.7.0.post0","sqlalchemy":"1.4.50","greenlet":"3.0.1"}"""),
            actual.getJSONObject("dependencies"), "android_dependencies")
        assertTrue(actual.getString("native_greenlet_module").endsWith(".so"))
        assertTrue(actual.getBoolean("readonly_database"))
        assertEquals(0, actual.getJSONArray("desktop_import_attempts").length())
        val migrations = actual.getJSONArray("migration_versions")
        assertEquals(49, migrations.length())
        for (index in 0 until migrations.length()) assertEquals(index + 1, migrations.getInt(index))
        retain(actual, "/sdcard/Download/pyfa-a07-engine.json")
    }

    @Test
    fun projectedEffectsMatchDesktopAndRefreshAllRecipientsOffline() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val fixtureBytes = instrumentation.context.assets.open("projection-expected.json").use { it.readBytes() }
        val expected = JSONObject(fixtureBytes.toString(Charsets.UTF_8))
        val actual = JSONObject(EngineRuntime.verifyProjection(context).get(120, TimeUnit.SECONDS))
        for (key in listOf("states", "inputs", "dataset_metadata", "eos_settings", "resolved_item_ids",
            "database_logical_sha256", "source_data_sha256")) {
            compare(expected.get(key), actual.get(key), "projection.$key")
        }
        assertEquals(expected.getString("source_commit"), actual.getString("desktop_source_commit"))
        val fixtureHash = MessageDigest.getInstance("SHA-256").digest(fixtureBytes)
            .joinToString("") { "%02x".format(it) }
        assertEquals(fixtureHash, actual.getString("desktop_fixture_sha256"))
        assertEquals(0, actual.getJSONArray("desktop_import_attempts").length())
        val states = expected.getJSONObject("states")
        assertEquals(11, states.length())
        for (name in states.keys()) {
            for (role in listOf("source", "target")) {
                assertEquals(39, actual.getJSONObject("states").getJSONObject(name).getJSONObject(role).length())
            }
        }
        assertLinks(actual.getJSONObject("scenario_links"), false, false, "scenario_removed")

        // Both identical recipients use the same independent desktop oracle.
        // The runtime reads recipient two before one, without manual refreshes.
        val phases = linkedMapOf(
            "initial" to Pair("initial", "initial"),
            "applied" to Pair("applied_zero", "applied_zero"),
            "first_distant" to Pair("distant", "applied_zero"),
            "first_disabled" to Pair("initial", "applied_zero"),
            "first_reactivated" to Pair("applied_zero", "applied_zero"),
            "script_changed" to Pair("script_changed", "script_changed"),
            "first_removed" to Pair("initial", "script_changed"),
            "script_restored" to Pair("initial", "applied_zero"),
            "removed" to Pair("initial", "initial"),
        )
        val multi = actual.getJSONObject("multi_recipient")
        assertEquals(phases.keys, multi.keys().asSequence().toSet())
        for ((phase, names) in phases) {
            val result = multi.getJSONObject(phase)
            assertEquals(setOf("first", "second", "unlinked", "links"), result.keys().asSequence().toSet())
            compare(states.getJSONObject(names.first).getJSONObject("target"), result.get("first"), "$phase.first")
            compare(states.getJSONObject(names.second).getJSONObject("target"), result.get("second"), "$phase.second")
            compare(states.getJSONObject("initial").getJSONObject("target"), result.get("unlinked"), "$phase.unlinked")
            val secondLinked = phase != "initial" && phase != "removed"
            val firstLinked = secondLinked && phase != "first_removed" && phase != "script_restored"
            assertLinks(result.getJSONObject("links"), firstLinked, secondLinked, phase)
        }
        val cycles = actual.getJSONArray("repeated_cycles")
        assertEquals(5, cycles.length())
        for (i in 0 until cycles.length()) {
            val cycle = cycles.getJSONObject(i)
            compare(states.getJSONObject("applied_zero"), cycle.getJSONObject("applied").get("stats"), "cycle[$i].applied")
            compare(states.getJSONObject("initial"), cycle.getJSONObject("removed").get("stats"), "cycle[$i].removed")
            assertLinks(cycle.getJSONObject("applied").getJSONObject("links"), true, false, "cycle[$i].applied")
            assertLinks(cycle.getJSONObject("removed").getJSONObject("links"), false, false, "cycle[$i].removed")
        }
        // Re-enter on the same process-owned worker and compare every observation.
        val repeated = JSONObject(EngineRuntime.verifyProjection(context).get(120, TimeUnit.SECONDS))
        val repeatTime = repeated.remove("projection_sequence_ms")
        val firstTime = actual.remove("projection_sequence_ms")
        compare(actual, repeated, "same_worker_repeat")
        actual.put("projection_sequence_ms", firstTime)
        actual.put("repeat_sequence_ms", repeatTime)
        actual.put("same_worker_repeat_matched", true)

        // Projection verification must not contaminate the existing sample or its
        // provenance, regardless of native test ordering.
        val ammoExpected = instrumentation.context.assets.open("vexor-expected.json").bufferedReader().use {
            JSONObject(it.readText())
        }
        val ammunition = JSONObject(EngineRuntime.verifyAmmunition(context).get(120, TimeUnit.SECONDS))
        for (key in listOf("states", "inputs", "resolved_item_ids")) {
            compare(ammoExpected.get(key), ammunition.get(key), "ammunition_after_projection.$key")
        }
        assertTrue(ammunition.getBoolean("readonly_database"))
        actual.put("ammunition_after_projection_matched", true)
        retain(actual, "/sdcard/Download/pyfa-a08-projection.json")
    }

    @Test
    fun commandBurstsMatchDesktopAndClearRecipientBonusesOffline() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val fixtureBytes = instrumentation.context.assets.open("command-expected.json").use { it.readBytes() }
        val expected = JSONObject(fixtureBytes.toString(Charsets.UTF_8))
        val actual = JSONObject(EngineRuntime.verifyCommand(context).get(120, TimeUnit.SECONDS))
        for (key in listOf("states", "inputs", "dataset_metadata", "eos_settings", "resolved_item_ids",
            "database_logical_sha256", "source_data_sha256")) {
            compare(expected.get(key), actual.get(key), "command.$key")
        }
        assertEquals(expected.getString("source_commit"), actual.getString("desktop_source_commit"))
        val fixtureHash = MessageDigest.getInstance("SHA-256").digest(fixtureBytes)
            .joinToString("") { "%02x".format(it) }
        assertEquals(fixtureHash, actual.getString("desktop_fixture_sha256"))
        assertEquals(0, actual.getJSONArray("desktop_import_attempts").length())
        val states = expected.getJSONObject("states")
        val pendingExpected = JSONObject()
        assertEquals(19, states.length())
        for (name in states.keys()) {
            for (role in listOf("source", "target")) {
                assertEquals(39, actual.getJSONObject("states").getJSONObject(name).getJSONObject(role).length())
                pendingExpected.put("states.$name.$role", 0)
            }
        }
        assertLinks(actual.getJSONObject("scenario_links"), false, false, "command_scenario_removed")

        // Identical recipients share the independent A05 oracle. Source edits
        // must refresh both; link disable/removal must affect only the first.
        val phases = linkedMapOf(
            "initial" to Pair("initial", "initial"),
            "applied" to Pair("applied", "applied"),
            "specialist_4" to Pair("specialist_4", "specialist_4"),
            "specialist_restored" to Pair("specialist_restored", "specialist_restored"),
            "command_ships_4" to Pair("command_ships_4", "command_ships_4"),
            "command_ships_restored" to Pair("command_ships_restored", "command_ships_restored"),
            "mindlink_added" to Pair("mindlink_added", "mindlink_added"),
            "mindlink_inactive" to Pair("mindlink_inactive", "mindlink_inactive"),
            "mindlink_active" to Pair("mindlink_active", "mindlink_active"),
            "burst_online" to Pair("burst_online", "burst_online"),
            "burst_active" to Pair("burst_active", "burst_active"),
            "first_disabled" to Pair("initial", "burst_active"),
            "first_reactivated" to Pair("burst_active", "burst_active"),
            "harmonizing" to Pair("harmonizing", "harmonizing"),
            "first_removed" to Pair("initial", "harmonizing"),
            "extension_restored" to Pair("initial", "extension_restored"),
            "mindlink_removed" to Pair("initial", "mindlink_removed"),
            "removed" to Pair("initial", "initial"),
        )
        val multi = actual.getJSONObject("multi_recipient")
        assertEquals(phases.keys, multi.keys().asSequence().toSet())
        for ((phase, names) in phases) {
            val result = multi.getJSONObject(phase)
            assertEquals(setOf("first", "second", "unlinked", "links"), result.keys().asSequence().toSet())
            compare(states.getJSONObject(names.first).getJSONObject("target"), result.get("first"), "command.$phase.first")
            compare(states.getJSONObject(names.second).getJSONObject("target"), result.get("second"), "command.$phase.second")
            compare(states.getJSONObject("initial").getJSONObject("target"), result.get("unlinked"), "command.$phase.unlinked")
            val secondLinked = phase != "initial" && phase != "removed"
            val firstLinked = secondLinked && phase !in setOf("first_removed", "extension_restored", "mindlink_removed")
            assertLinks(result.getJSONObject("links"), firstLinked, secondLinked, "command.$phase")
            for (role in listOf("first", "second", "unlinked")) {
                pendingExpected.put("multi_recipient.$phase.$role", 0)
            }
        }
        val cycles = actual.getJSONArray("repeated_cycles")
        assertEquals(5, cycles.length())
        for (i in 0 until cycles.length()) {
            val cycle = cycles.getJSONObject(i)
            compare(states.getJSONObject("applied"), cycle.getJSONObject("applied").get("stats"), "command.cycle[$i].applied")
            compare(states.getJSONObject("initial"), cycle.getJSONObject("removed").get("stats"), "command.cycle[$i].removed")
            assertLinks(cycle.getJSONObject("applied").getJSONObject("links"), true, false, "command.cycle[$i].applied")
            assertLinks(cycle.getJSONObject("removed").getJSONObject("links"), false, false, "command.cycle[$i].removed")
            for (stage in listOf("applied", "removed")) {
                for (role in listOf("source", "target")) {
                    pendingExpected.put("repeated_cycles.$i.$stage.$role", 0)
                }
            }
        }
        // Assert the complete set of 112 observations, including source/target
        // and every restored recipient. Missing observations must fail too.
        assertEquals(112, pendingExpected.length())
        compare(pendingExpected, actual.getJSONObject("pending_command_bonuses"), "pending_command_bonuses")
        val repeated = JSONObject(EngineRuntime.verifyCommand(context).get(120, TimeUnit.SECONDS))
        val repeatTime = repeated.remove("command_sequence_ms")
        val firstTime = actual.remove("command_sequence_ms")
        compare(actual, repeated, "command_same_worker_repeat")
        actual.put("command_sequence_ms", firstTime)
        actual.put("repeat_sequence_ms", repeatTime)
        actual.put("same_worker_repeat_matched", true)

        // Check the existing scenarios after commands on this same worker.
        val ammoExpected = instrumentation.context.assets.open("vexor-expected.json").bufferedReader().use {
            JSONObject(it.readText())
        }
        val ammunition = JSONObject(EngineRuntime.verifyAmmunition(context).get(120, TimeUnit.SECONDS))
        val projectionExpected = instrumentation.context.assets.open("projection-expected.json").bufferedReader().use {
            JSONObject(it.readText())
        }
        val projection = JSONObject(EngineRuntime.verifyProjection(context).get(120, TimeUnit.SECONDS))
        for (key in listOf("states", "inputs", "resolved_item_ids")) {
            compare(ammoExpected.get(key), ammunition.get(key), "ammunition_after_command.$key")
            compare(projectionExpected.get(key), projection.get(key), "projection_after_command.$key")
        }
        assertTrue(ammunition.getBoolean("readonly_database"))
        actual.put("ammunition_after_command_matched", true)
        actual.put("projection_after_command_matched", true)
        retain(actual, "/sdcard/Download/pyfa-a09-command.json")
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
