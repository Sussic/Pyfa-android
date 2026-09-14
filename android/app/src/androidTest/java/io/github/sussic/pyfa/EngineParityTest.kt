package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.provider.Settings
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
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
        // This report contains actual native values, not only a passed counter.
        val receipt = File(context.filesDir, "a07-engine.json")
        receipt.writeText(actual.toString(2))
        val automation = instrumentation.uiAutomation
        val output = "/sdcard/Download/pyfa-a07-engine.json"
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "sh -c 'run-as ${context.packageName} cat files/a07-engine.json > $output'",
        )).use { it.readBytes() }
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
