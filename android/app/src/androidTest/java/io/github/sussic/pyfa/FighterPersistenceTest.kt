package io.github.sussic.pyfa

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.compose.ui.semantics.SemanticsProperties
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

/** Run fighters_seed, force-stop/relaunch without clearing disposable data, then fighters_reopen. */
@RunWith(AndroidJUnit4::class)
class FighterPersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun fingerprint(details: FighterDetails) = JSONArray(details.squadrons.map { row ->
        JSONObject().put("object_key", row.objectKey).put("item_id", row.itemId).put("amount", row.amount)
            .put("max_size", row.maxSize).put("active", row.active).put("slot", row.slot)
            .put("abilities", JSONArray(row.abilities.map { JSONObject().put("effect_id", it.effectId).put("active", it.active) }))
    }).toString()
    private fun stats(id: String) = JSONObject().apply {
        EngineRuntime.library.value.single { it.id == id }.stats.toSortedMap().forEach { (key, stat) ->
            put(key, JSONObject().put("value", stat.value.raw).put("unit", stat.unit))
        }
    }.toString()
    @Test fun nondefaultAbilitiesQuantityAndActiveStateSurviveRealProcessRestart() {
        val phase = InstrumentationRegistry.getArguments().getString("offline_features_phase")
        assertTrue("Choose fighters_seed or fighters_reopen", phase in setOf("fighters_seed", "fighters_reopen"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val prefs = context.getSharedPreferences("fighter_qualification", Context.MODE_PRIVATE)
        if (phase == "fighters_seed") {
            val before = EngineRuntime.library.value.map { it.id }.toSet()
            assertTrue(EngineRuntime.createEmptyFit(context, "Thanatos", "Fighter restart fixture").get(120, TimeUnit.SECONDS).isSuccess)
            val id = EngineRuntime.library.value.single { it.id !in before }.id
            fun send(operation: BridgeOperation) {
                val revision = EngineRuntime.library.value.single { it.id == id }.revision
                val response = EngineRuntime.request(context, operation, mapOf(id to revision)).get(120, TimeUnit.SECONDS)
                assertTrue(response.error?.message, response.isSuccess)
            }
            val item = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS).items.single { it.name == "Firbolg I" }
            repeat(2) { send(BridgeOperation.AddFighter(id, item.id)) }
            val details = EngineRuntime.fighterDetails(context, id).get(30, TimeUnit.SECONDS)
            send(BridgeOperation.ToggleFighterAbility(id, 0, emptyList(), details.squadrons.first().abilities.first().effectId))
            send(BridgeOperation.SetFighterAmount(id, 0, 2))
            send(BridgeOperation.ToggleFighters(id, 1, emptyList()))
            val variation = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS).items.single { it.name == "Firbolg II" }
            send(BridgeOperation.AddFighter(id, variation.id))
            send(BridgeOperation.RemoveFighters(id, listOf(2)))
            assertEquals(listOf(variation.id, item.id), EngineRuntime.recent.value.take(2))
            val beforeRejectedFit = EngineRuntime.library.value.map { it.id }.toSet()
            assertTrue(EngineRuntime.createEmptyFit(context, "Vexor", "Rejected fighter Recent restart").get(120, TimeUnit.SECONDS).isSuccess)
            val rejectedFit = EngineRuntime.library.value.single { it.id !in beforeRejectedFit }
            val rejectionHistory = EngineRuntime.offlineFeatureState(context, rejectedFit.id).get(30, TimeUnit.SECONDS).history
            val rejected = EngineRuntime.request(context, BridgeOperation.AddFighter(rejectedFit.id, item.id),
                mapOf(rejectedFit.id to rejectedFit.revision)).get(120, TimeUnit.SECONDS)
            assertFalse(rejected.isSuccess)
            assertEquals(rejectedFit, EngineRuntime.library.value.single { it.id == rejectedFit.id })
            assertEquals(rejectionHistory, EngineRuntime.offlineFeatureState(context, rejectedFit.id).get(30, TimeUnit.SECONDS).history)
            assertEquals(listOf(item.id, variation.id), EngineRuntime.recent.value.take(2))
            val saved = EngineRuntime.fighterDetails(context, id).get(30, TimeUnit.SECONDS)
            assertEquals(2, saved.squadrons.first().amount); assertFalse(saved.squadrons.last().active)
            val receipt = JSONObject().put("fit_id", id).put("squadrons", fingerprint(saved)).put("stats", stats(id))
                .put("recent", JSONArray(EngineRuntime.recent.value)).put("rejected_fit_id", rejectedFit.id)
                .put("rejected_revision", rejectedFit.revision).put("rejected_stats", stats(rejectedFit.id))
                .put("session", EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).context.sessionId)
            assertTrue(prefs.edit().putString("seed", receipt.toString()).commit())
        } else {
            val saved = JSONObject(checkNotNull(prefs.getString("seed", null)) { "Run fighters_seed first on this disposable app data." })
            val id = saved.getString("fit_id")
            val state = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS)
            assertNotEquals("This gate requires a new process, not Activity recreation", saved.getString("session"), state.context.sessionId)
            assertEquals(saved.getString("squadrons"), fingerprint(EngineRuntime.fighterDetails(context, id).get(30, TimeUnit.SECONDS)))
            assertEquals(saved.getString("stats"), stats(id))
            val recent = saved.getJSONArray("recent").let { values -> (0 until values.length()).map(values::getInt) }
            assertEquals(recent, EngineRuntime.recent.value)
            val rejectedId = saved.getString("rejected_fit_id")
            assertEquals(saved.getLong("rejected_revision"), EngineRuntime.library.value.single { it.id == rejectedId }.revision)
            assertEquals(saved.getString("rejected_stats"), stats(rejectedId))
            assertTrue(EngineRuntime.fighterDetails(context, rejectedId).get(30, TimeUnit.SECONDS).squadrons.isEmpty())
            EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
            compose.onNodeWithTag("fighters-open").performScrollTo().performClick()
            val model = ViewModelProvider(compose.activity)[FighterEditorModel::class.java]
            compose.waitUntil(120_000) { model.currentDetails?.fitId == id && !model.loading }
            compose.onNodeWithTag("fighter-0-amount").assertTextContains("2")
            assertEquals(saved.getString("squadrons"), fingerprint(model.currentDetails!!))
            compose.onNodeWithTag("fighters-browse").performScrollTo().performClick()
            val equipment = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
            compose.waitUntil(120_000) { !equipment.busy && equipment.catalog != null }
            compose.onNodeWithTag("equipment-recent").performScrollTo().performClick()
            compose.onNodeWithTag("equipment-location").assertTextEquals("Recent use · newest first")
            val rows = compose.onAllNodes(SemanticsMatcher("equipment rows") {
                it.config.getOrElse(SemanticsProperties.TestTag) { "" }.startsWith("equipment-item-")
            }).fetchSemanticsNodes().map { it.config[SemanticsProperties.TestTag].removePrefix("equipment-item-").toInt() }
            assertEquals(recent, rows)
            assertEquals(recent, EngineRuntime.recent.value)
        }
    }
}
