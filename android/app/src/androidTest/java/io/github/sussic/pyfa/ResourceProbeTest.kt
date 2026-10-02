package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.os.Process
import android.provider.Settings
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import io.github.sussic.pyfa.ModuleTestJson.compare

/** Real EOS inputs including states rejected by durable new-fit creation. */
@RunWith(AndroidJUnit4::class)
class ResourceProbeTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun allResourcePairsMatchOriginalDesktopOffline() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val bytes = instrumentation.context.assets.open("resources-expected.json").use { it.readBytes() }
        val fixture = JSONObject(bytes.toString(Charsets.UTF_8))
        val cases = fixture.getJSONArray("cases")
        assertEquals(14, cases.length())
        val inputs = JSONArray((0 until cases.length()).map { index ->
            val case = cases.getJSONObject(index)
            JSONObject().put("spec", case.getJSONObject("spec")).put("fighters", case.getJSONArray("fighters"))
        })
        val actual = JSONObject(EngineRuntime.verifyResources(context, inputs.toString()).get(120, TimeUnit.SECONDS))
        compare(inputs, actual.getJSONArray("inputs"), strict = false)
        assertEquals(fixture.getString("source_commit"), actual.getString("desktop_source_commit"))
        val baseline = JSONObject(instrumentation.context.assets.open("vexor-expected.json").bufferedReader().use { it.readText() })
        assertEquals(baseline.getString("database_logical_sha256"), actual.getString("database_logical_sha256"))
        assertEquals(0, actual.getJSONArray("desktop_import_attempts").length())
        compare(fixture.getJSONObject("eos_settings"),actual.getJSONObject("eos_settings"),strict=false)
        val rows = actual.getJSONArray("resources")
        assertEquals(cases.length(), rows.length())
        val overloads = mutableSetOf<String>()
        for (index in 0 until cases.length()) {
            val expected = cases.getJSONObject(index).getJSONObject("resources")
            val observed = rows.getJSONObject(index)
            assertEquals(RESOURCE_LABELS.keys, observed.keys().asSequence().toSet())
            val decoded = linkedMapOf<String, ResourceDetails>()
            for (name in RESOURCE_LABELS.keys) {
                val left = expected.getJSONObject(name); val right = observed.getJSONObject(name)
                for (key in listOf("used", "total")) {
                    compare(left.get(key), right.get(key), "$index.$name.$key")
                    val kind = if (left.get(key) is Int || left.get(key) is Long) "integer" else "decimal"
                    assertEquals(kind, right.getString("${key}_type"))
                }
                for (key in listOf("unit", "overloaded")) compare(left.get(key), right.get(key))
                for ((source, target) in listOf("desktop_used" to "used_display", "desktop_total" to "total_display",
                    "desktop_used_detail" to "used_detail", "desktop_total_detail" to "total_detail"))
                    assertEquals(left.getString(source), right.getString(target))
                if (right.getBoolean("overloaded")) overloads.add(name)
                fun scalar(key: String): StatValue = if (right.getString("${key}_type") == "integer")
                    StatValue.Integer(right.getLong(key)) else StatValue.Decimal(right.getDouble(key))
                decoded[name] = ResourceDetails(scalar("used"), scalar("total"), right.getString("unit"),
                    right.getBoolean("overloaded"), right.getString("used_display"), right.getString("total_display"),
                    right.getString("used_detail"), right.getString("total_detail"))
            }
            // Render the same production cards with actual native EOS results,
            // rather than an expected fixture or a separate test renderer.
            compose.activity.runOnUiThread {
                compose.activity.setContent { MaterialTheme {
                    Column(Modifier.verticalScroll(rememberScrollState())) {
                        decoded.forEach { (name, row) -> ResourceCard(name, RESOURCE_LABELS.getValue(name), row, "probe-$index") }
                    }
                } }
            }
            compose.waitForIdle()
            for ((name, row) in decoded) {
                compose.onNodeWithTag("resources-value-$name").performScrollTo()
                    .assertTextEquals("${row.usedDisplay} / ${row.totalDisplay} ${row.unit}")
                if (row.overloaded == true) compose.onNodeWithTag("resources-overload-$name").assertTextEquals("Over capacity")
                compose.onNodeWithTag("resources-details-$name").performScrollTo().performClick()
                compose.onNodeWithTag("resources-used-detail-$name").performScrollTo().assertTextEquals("Used: ${row.usedDetail} ${row.unit}")
                compose.onNodeWithTag("resources-total-detail-$name").performScrollTo().assertTextEquals("Capacity: ${row.totalDetail} ${row.unit}")
                if ((index == 3 && name == "cpu") || (index == 12 && name == "fighter_bay") || (index == 9 && name == "cargo_bay")) {
                    ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand(
                        "screencap -p /sdcard/Download/pyfa-c011-probe-$index-$name.png")).use { it.readBytes() }
                }
                compose.onNodeWithTag("resources-details-$name").performScrollTo().performClick()
            }
        }
        assertEquals(RESOURCE_LABELS.keys, overloads)
        actual.put("task", "C01.1").put("phase", "probe")
            .put("pid",Process.myPid())
            .put("fixture_sha256", MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) })
        val descriptors = instrumentation.uiAutomation.executeShellCommandRw("dd of=/sdcard/Download/pyfa-c011-probe.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(actual.toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
}
