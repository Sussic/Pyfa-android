package io.github.sussic.pyfa

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.provider.Settings
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

/** Run spool_seed, force-stop/relaunch without clearing disposable data, then spool_reopen. */
@RunWith(AndroidJUnit4::class)
class ModuleSpoolPersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun fingerprint(details: ModuleSpoolDetails) = JSONArray(details.modules.map { row ->
        JSONObject().put("index", row.index).put("object_key", row.objectKey).put("item_id", row.itemId)
            .put("override", row.overrideCycles ?: JSONObject.NULL).put("current", row.currentCycles)
            .put("default", row.defaultCycles).put("minimum", row.minimumCycles).put("maximum", row.maximumCycles)
            .put("current_seconds", row.currentSeconds).put("default_seconds", row.defaultSeconds)
            .put("minimum_seconds", row.minimumSeconds).put("maximum_seconds", row.maximumSeconds)
            .put("choices", JSONArray(row.choices))
    }).toString()
    private fun details(id: String) = EngineRuntime.moduleSpoolDetails(context, id).get(30, TimeUnit.SECONDS)
    private fun stats(id: String) = JSONObject().apply {
        EngineRuntime.library.value.single { it.id == id }.stats.toSortedMap().forEach { (key, stat) ->
            put(key, JSONObject().put("value", stat.value.raw).put("unit", stat.unit))
        }
    }.toString()
    private fun weaponDps(id: String) = EngineRuntime.outputDetails(context, id).get(30, TimeUnit.SECONDS)
        .firepower.getValue("raw").getValue("weapon").spool.current.value.numberOrNull()!!
    @Test fun explicitZeroAndRawClampedOverrideSurviveOrdinaryEditAndRealProcessRestart() {
        val phase = InstrumentationRegistry.getArguments().getString("offline_features_phase")
        assertTrue("Choose spool_seed or spool_reopen", phase in setOf("spool_seed", "spool_reopen"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val prefs = context.getSharedPreferences("spool_qualification", Context.MODE_PRIVATE)
        if (phase == "spool_seed") {
            fun create(ship: String, module: ModuleSpec): String {
                val response = EngineRuntime.request(context, BridgeOperation.CreateFit(FitSpec("Spool persistence $ship", ship, 5, false,
                    DamagePattern(25.0, 25.0, 25.0, 25.0), Security(SystemSecurity.HISEC, 0.0), listOf(module), emptyList())))
                    .get(120, TimeUnit.SECONDS)
                assertTrue(response.error?.message, response.isSuccess); return response.fits.single().id
            }
            val weapon = create("Vedmak", ModuleSpec("Heavy Entropic Disintegrator II", ModuleState.ACTIVE, "Occult M", 0))
            val repair = create("Rodiva", ModuleSpec("Heavy Mutadaptive Remote Armor Repairer II", ModuleState.ACTIVE, spoolCycles = 999))
            val revision = EngineRuntime.library.value.single { it.id == weapon }.revision
            assertTrue(EngineRuntime.request(context, BridgeOperation.RenameFit(weapon, "Spool zero retained after edit"),
                mapOf(weapon to revision)).get(120, TimeUnit.SECONDS).isSuccess)
            assertEquals(0, details(weapon).modules.single().overrideCycles)
            assertEquals(999, details(repair).modules.single().overrideCycles)
            val rows = JSONArray(listOf(weapon, repair).map { id ->
                JSONObject().put("fit_id", id).put("details", fingerprint(details(id))).put("stats", stats(id)).put("weapon_dps", weaponDps(id))
            })
            val receipt = JSONObject().put("fits", rows)
                .put("session", EngineRuntime.offlineFeatureState(context, weapon).get(30, TimeUnit.SECONDS).context.sessionId)
            assertTrue(prefs.edit().putString("seed", receipt.toString()).commit())
        } else {
            val saved = JSONObject(checkNotNull(prefs.getString("seed", null)) { "Run spool_seed first on disposable app data." })
            val rows = saved.getJSONArray("fits")
            val firstId = rows.getJSONObject(0).getString("fit_id")
            val state = EngineRuntime.offlineFeatureState(context, firstId).get(30, TimeUnit.SECONDS)
            assertNotEquals("This gate requires a new process, not Activity recreation", saved.getString("session"), state.context.sessionId)
            for (index in 0 until rows.length()) {
                val row = rows.getJSONObject(index); val id = row.getString("fit_id")
                assertEquals(row.getString("details"), fingerprint(details(id)))
                assertEquals(row.getString("stats"), stats(id))
                assertEquals(row.getDouble("weapon_dps"), weaponDps(id), 0.0)
            }
            EngineRuntime.selectFit(context, firstId).get(30, TimeUnit.SECONDS)
            compose.onNodeWithTag("modules-open").performScrollTo().performClick()
            compose.onNodeWithTag("modules-spool").performScrollTo().performClick()
            val model = ViewModelProvider(compose.activity)[ModuleSpoolModel::class.java]
            compose.waitUntil(120_000) { !model.loading && model.currentDetails?.fitId == firstId }
            val module = model.currentDetails!!.modules.single()
            compose.onNodeWithTag("spool-mode-${module.index}").assertTextEquals("Explicit override: 0 cycles")
        }
    }
}
