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

/** Run boosters_seed, force-stop/relaunch without clearing disposable data, then boosters_reopen. */
@RunWith(AndroidJUnit4::class)
class BoosterPersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun fingerprint(details: BoosterDetails) = JSONArray(details.boosters.map { row ->
        JSONObject().put("object_key", row.objectKey).put("item_id", row.itemId).put("slot", row.slot).put("active", row.active)
            .put("duration_ms", row.durationMs ?: JSONObject.NULL).put("duration_text", row.durationText ?: JSONObject.NULL)
            .put("side_effects", JSONArray(row.sideEffects.map { JSONObject().put("effect_id", it.effectId).put("active", it.active).put("name", it.name) }))
    }).toString()
    private fun stats(id: String) = JSONObject().apply {
        EngineRuntime.library.value.single { it.id == id }.stats.toSortedMap().forEach { (key, stat) ->
            put(key, JSONObject().put("value", stat.value.raw).put("unit", stat.unit))
        }
    }.toString()
    @Test fun activeAndIndependentSideEffectStatesSurviveRealProcessRestart() {
        val phase = InstrumentationRegistry.getArguments().getString("offline_features_phase")
        assertTrue("Choose boosters_seed or boosters_reopen", phase in setOf("boosters_seed", "boosters_reopen"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val prefs = context.getSharedPreferences("booster_qualification", Context.MODE_PRIVATE)
        if (phase == "boosters_seed") {
            val before = EngineRuntime.library.value.map { it.id }.toSet()
            assertTrue(EngineRuntime.createEmptyFit(context, "Vexor", "Booster restart fixture").get(120, TimeUnit.SECONDS).isSuccess)
            val id = EngineRuntime.library.value.single { it.id !in before }.id
            fun send(operation: BridgeOperation) {
                val revision = EngineRuntime.library.value.single { it.id == id }.revision
                val response = EngineRuntime.request(context, operation, mapOf(id to revision)).get(120, TimeUnit.SECONDS)
                assertTrue(response.error?.message, response.isSuccess)
            }
            val catalog = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS)
            val first = catalog.items.single { it.name == "Standard Blue Pill Booster" }
            val improved = catalog.items.single { it.name == "Improved Blue Pill Booster" }
            val second = catalog.items.single { it.name == "Standard Frentix Booster" }
            send(BridgeOperation.FitBooster(id, first.id))
            var details = EngineRuntime.boosterDetails(context, id).get(30, TimeUnit.SECONDS)
            val effect = details.boosters.single().sideEffects.first()
            send(BridgeOperation.SetBoosterSideEffect(id, 0, effect.effectId, true))
            send(BridgeOperation.SetBoosterActive(id, 0, false))
            send(BridgeOperation.ChangeBoosterVariation(id, 0, improved.id))
            send(BridgeOperation.FitBooster(id, second.id))
            details = EngineRuntime.boosterDetails(context, id).get(30, TimeUnit.SECONDS)
            val changed = details.boosters.single { it.itemId == improved.id }
            assertFalse(changed.active); assertTrue(changed.sideEffects.single { it.effectId == effect.effectId }.active)
            val receipt = JSONObject().put("fit_id", id).put("boosters", fingerprint(details)).put("stats", stats(id))
                .put("session", EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).context.sessionId)
            assertTrue(prefs.edit().putString("seed", receipt.toString()).commit())
        } else {
            val saved = JSONObject(checkNotNull(prefs.getString("seed", null)) { "Run boosters_seed first on this disposable app data." })
            val id = saved.getString("fit_id")
            val state = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS)
            assertNotEquals("This gate requires a new process, not Activity recreation", saved.getString("session"), state.context.sessionId)
            assertEquals(saved.getString("boosters"), fingerprint(EngineRuntime.boosterDetails(context, id).get(30, TimeUnit.SECONDS)))
            assertEquals(saved.getString("stats"), stats(id))
            EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
            compose.onNodeWithTag("boosters-open").performScrollTo().performClick()
            val model = ViewModelProvider(compose.activity)[BoosterEditorModel::class.java]
            compose.waitUntil(120_000) { model.currentDetails?.fitId == id && !model.loading }
            assertEquals(saved.getString("boosters"), fingerprint(model.currentDetails!!))
            model.currentDetails!!.boosters.forEach { row ->
                compose.onNodeWithTag("booster-${row.index}-duration").assertTextEquals("Duration: ${row.durationText}")
            }
        }
    }
}
