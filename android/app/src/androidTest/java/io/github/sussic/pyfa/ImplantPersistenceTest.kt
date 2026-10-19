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

/** Run implants_seed, force-stop/relaunch without clearing disposable data, then implants_reopen. */
@RunWith(AndroidJUnit4::class)
class ImplantPersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun fingerprint(details: ImplantDetails) = JSONArray(details.implants.map { row ->
        JSONObject().put("index", row.index).put("object_key", row.objectKey).put("item_id", row.itemId)
            .put("slot", row.slot).put("active", row.active).put("name", row.name)
    }).toString()
    private fun stats(id: String) = JSONObject().apply {
        EngineRuntime.library.value.single { it.id == id }.stats.toSortedMap().forEach { (key, stat) ->
            put(key, JSONObject().put("value", stat.value.raw).put("unit", stat.unit))
        }
    }.toString()
    @Test fun slotOrderIdentitiesActivationAndUndoPersistThroughActualProcessRestart() {
        val phase = InstrumentationRegistry.getArguments().getString("offline_features_phase")
        assertTrue("Choose implants_seed or implants_reopen", phase in setOf("implants_seed", "implants_reopen"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val prefs = context.getSharedPreferences("implant_qualification", Context.MODE_PRIVATE)
        if (phase == "implants_seed") {
            val before = EngineRuntime.library.value.map { it.id }.toSet()
            assertTrue(EngineRuntime.createEmptyFit(context, "Vexor", "Implant restart fixture").get(120, TimeUnit.SECONDS).isSuccess)
            val id = EngineRuntime.library.value.single { it.id !in before }.id
            fun send(operation: BridgeOperation) {
                val revision = EngineRuntime.library.value.single { it.id == id }.revision
                val response = EngineRuntime.request(context, operation, mapOf(id to revision)).get(120, TimeUnit.SECONDS)
                assertTrue(response.error?.message, response.isSuccess)
            }
            val catalog = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS)
            val first = catalog.items.single { it.name == "Eifyr and Co. 'Rogue' Navigation NN-601" }
            val improved = catalog.items.single { it.name == "Eifyr and Co. 'Rogue' Navigation NN-605" }
            val mindlink = catalog.items.single { it.name == "Shield Command Mindlink" }
            send(BridgeOperation.AddImplant(id, mindlink.name)) // Existing name-based operation remains supported.
            send(BridgeOperation.FitImplant(id, first.id))
            send(BridgeOperation.SetImplantActive(id, 6, false)) // Existing slot-based operation remains supported.
            send(BridgeOperation.ChangeVariation(id, VariationContext.IMPLANT, 1, improved.id))
            val inactiveVariant = EngineRuntime.implantDetails(context, id).get(30, TimeUnit.SECONDS)
            assertEquals(listOf(10, 6), inactiveVariant.implants.map { it.slot })
            assertFalse(inactiveVariant.implants[1].active)
            send(BridgeOperation.FitImplant(id, first.id))
            assertTrue(EngineRuntime.implantDetails(context, id).get(30, TimeUnit.SECONDS).implants[1].active)
            send(BridgeOperation.Undo(id))
            val details = EngineRuntime.implantDetails(context, id).get(30, TimeUnit.SECONDS)
            assertEquals(fingerprint(inactiveVariant), fingerprint(details))
            val receipt = JSONObject().put("fit_id", id).put("implants", fingerprint(details)).put("stats", stats(id))
                .put("session", EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).context.sessionId)
            assertTrue(prefs.edit().putString("seed", receipt.toString()).commit())
        } else {
            val saved = JSONObject(checkNotNull(prefs.getString("seed", null)) { "Run implants_seed first on this disposable app data." })
            val id = saved.getString("fit_id")
            val state = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS)
            assertNotEquals("This gate requires a new process, not Activity recreation", saved.getString("session"), state.context.sessionId)
            assertEquals(saved.getString("implants"), fingerprint(EngineRuntime.implantDetails(context, id).get(30, TimeUnit.SECONDS)))
            assertEquals(saved.getString("stats"), stats(id))
            EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
            compose.onNodeWithTag("implants-open").performScrollTo().performClick()
            val model = ViewModelProvider(compose.activity)[ImplantEditorModel::class.java]
            compose.waitUntil(120_000) { model.currentDetails?.fitId == id && !model.loading }
            assertEquals(saved.getString("implants"), fingerprint(model.currentDetails!!))
            assertEquals(listOf(1, 0), model.currentDetails!!.displayRows.map { it.index })
            model.currentDetails!!.implants.forEach { row ->
                compose.onNodeWithTag("implant-${row.index}-state").assertTextEquals(if (row.active) "Active" else "Inactive")
            }
        }
    }
}
