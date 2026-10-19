package io.github.sussic.pyfa

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Run projected_fits_seed, force-stop/relaunch without clearing, then projected_fits_reopen. */
@RunWith(AndroidJUnit4::class)
class ProjectedFitPersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun send(op: BridgeOperation, vararg ids: String): BridgeResponse {
        val result = EngineRuntime.request(context,op,ids.toSet().associateWith { fit(it).revision }).get(120,TimeUnit.SECONDS)
        assertTrue(result.error?.message,result.isSuccess); return result
    }
    private fun snapshot(id: String): JSONObject {
        val fit = fit(id)
        return JSONObject().put("id",id).put("revision",fit.revision).put("name",fit.name).put("ship",fit.ship)
            .put("modules",JSONArray(fit.modules.map { JSONObject().put("index",it.index).put("name",it.name ?: JSONObject.NULL)
                .put("state",it.state?.name ?: JSONObject.NULL).put("charge",it.charge ?: JSONObject.NULL).put("empty_slot",it.emptySlot?.name ?: JSONObject.NULL) }))
            .put("links",JSONArray(fit.projections.map { JSONObject().put("source",it.sourceId).put("range",it.rangeM ?: JSONObject.NULL)
                .put("active",it.active).put("amount",it.amount) }))
            .put("stats",JSONObject().apply { fit.stats.toSortedMap().forEach { (key,stat) ->
                put(key,JSONObject().put("value",stat.value.raw).put("unit",stat.unit)) } })
    }
    @Test fun savedProjectionOptionsDependentModuleStateIdentitiesAndResultsSurviveNewProcess() {
        val phase = InstrumentationRegistry.getArguments().getString("offline_features_phase")
        assertTrue("Choose projected_fits_seed or projected_fits_reopen",phase in setOf("projected_fits_seed","projected_fits_reopen"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val prefs = context.getSharedPreferences("projected_fits_qualification",Context.MODE_PRIVATE)
        if (phase == "projected_fits_seed") {
            fun create(name: String, module: String) = send(BridgeOperation.CreateFit(FitSpec(name,"Rifter",5,false,
                DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),
                listOf(ModuleSpec(module,ModuleState.ACTIVE)),emptyList()))).fits.single().id
            val source=create("Projection restart source","Warp Scrambler II")
            val target=create("Projection restart recipient","5MN Microwarpdrive II")
            send(BridgeOperation.AddProjectedFit(source,target),source,target)
            assertEquals(ModuleState.ONLINE,fit(target).modules.single { it.name == "5MN Microwarpdrive II" }.state)
            send(BridgeOperation.SetProjectedFitAmount(source,target,2),source,target)
            send(BridgeOperation.SetProjectedFitRange(source,target,7500.0),source,target)
            send(BridgeOperation.AddProjectedFit(target,source),source,target)
            send(BridgeOperation.AddProjectedFit(source,source),source)
            send(BridgeOperation.SetProjectedFitActive(source,source,false),source)
            EngineRuntime.selectFit(context,target).get(30,TimeUnit.SECONDS)
            val state=EngineRuntime.offlineFeatureState(context,target).get(30,TimeUnit.SECONDS)
            val receipt=JSONObject().put("source",source).put("target",target).put("source_snapshot",snapshot(source)).put("target_snapshot",snapshot(target))
                .put("session",state.context.sessionId).put("recent",JSONArray(EngineRuntime.recent.value))
            assertTrue(prefs.edit().putString("seed",receipt.toString()).commit())
        } else {
            val saved=JSONObject(checkNotNull(prefs.getString("seed",null)) { "Run projected_fits_seed first on disposable data." })
            val source=saved.getString("source"); val target=saved.getString("target")
            val state=EngineRuntime.offlineFeatureState(context,target).get(30,TimeUnit.SECONDS)
            assertNotEquals("A new process is required, not only Activity recreation",saved.getString("session"),state.context.sessionId)
            assertEquals(saved.getJSONObject("source_snapshot").toString(),snapshot(source).toString())
            assertEquals(saved.getJSONObject("target_snapshot").toString(),snapshot(target).toString())
            assertEquals(saved.getJSONArray("recent").toString(),JSONArray(EngineRuntime.recent.value).toString())
            assertEquals(0,state.history.undoCount); assertEquals(0,state.history.redoCount)
            for (id in listOf(source,target)) {
                val history=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
                assertEquals(0,history.undoCount); assertEquals(0,history.redoCount)
            }
            EngineRuntime.selectFit(context,target).get(30,TimeUnit.SECONDS)
            compose.onNodeWithTag("projections-open").performScrollTo().performClick()
            compose.onNodeWithTag("projection-$source-values").assertTextEquals("Count: 2 · Active · Range: 7.5 km")
            compose.onNodeWithTag("projection-$source-open").performScrollTo().performClick()
            compose.waitUntil(120_000) { (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id == source }
            compose.onNodeWithTag("projections-return").performScrollTo().performClick()
            compose.waitUntil(120_000) { (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id == target }
            compose.onNodeWithTag("projections-recipient").assertExists()
        }
    }
}
