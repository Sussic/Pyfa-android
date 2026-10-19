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

/** Run command_fits_seed, force-stop/relaunch without clearing, then command_fits_reopen. */
@RunWith(AndroidJUnit4::class)
class CommandFitPersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[CommandFitModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun send(op: BridgeOperation,vararg ids: String): BridgeResponse {
        val result=EngineRuntime.request(context,op,ids.toSet().associateWith { fit(it).revision }).get(120,TimeUnit.SECONDS)
        assertTrue(result.error?.message,result.isSuccess); return result
    }
    private fun snapshot(id: String): JSONObject {
        val value=fit(id)
        val identities=EngineRuntime.inspectionOptions(context,id).get(30,TimeUnit.SECONDS).targets
        return JSONObject().put("id",id).put("revision",value.revision).put("name",value.name).put("ship",value.ship)
            .put("modules",JSONArray(value.modules.map { JSONObject().put("index",it.index).put("name",it.name ?: JSONObject.NULL)
                .put("charge",it.charge ?: JSONObject.NULL).put("state",it.state?.name ?: JSONObject.NULL)
                .put("empty_slot",it.emptySlot?.name ?: JSONObject.NULL) }))
            .put("implants",JSONArray(value.implants.map { JSONObject().put("name",it.name).put("slot",it.slot).put("active",it.active) }))
            .put("links",JSONArray(value.commands.map { JSONObject().put("source",it.sourceId).put("active",it.active) }))
            .put("identities",JSONArray(identities.map { JSONObject(it.target.json()).put("name",it.name) }))
            .put("skills",JSONObject().apply { value.skills.toSortedMap().forEach { (name,level) -> put(name,level ?: JSONObject.NULL) } })
            .put("stats",JSONObject().apply { value.stats.toSortedMap().forEach { (key,stat) ->
                put(key,JSONObject().put("value",stat.value.raw).put("unit",stat.unit)) } })
    }
    private fun profiles(state: OfflineFeatureState) = JSONObject()
        .put("profiles",JSONArray(state.profiles.map { p -> JSONObject().put("id",p.id).put("name",p.name)
            .put("revision",p.revision).put("readonly",p.readonly).put("default_level",p.defaultLevel ?: JSONObject.NULL)
            .put("levels",JSONObject().apply { p.levels.toSortedMap().forEach { (skill,level) -> put(skill.toString(),level ?: JSONObject.NULL) } }) }))
        .put("bindings",JSONObject().apply { state.bindings.toSortedMap().forEach { (fit,binding) ->
            put(fit,JSONObject().put("profile",binding.profileId).put("revision",binding.revision)) } })
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }

    @Test fun loadedCommandSourceLinksOptionsProfilesAndResultsRestoreInAnActualNewProcess() {
        val phase=InstrumentationRegistry.getArguments().getString("offline_features_phase")
        assertTrue("Choose command_fits_seed or command_fits_reopen",phase in setOf("command_fits_seed","command_fits_reopen"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val prefs=context.getSharedPreferences("command_fits_qualification",Context.MODE_PRIVATE)
        if (phase=="command_fits_seed") {
            val reference=instrumentation.context.assets.open("command-expected.json").bufferedReader().use { JSONObject(it.readText()) }
            fun create(role: String): String = send(BridgeOperation.CreateFit(BridgeCodec.decodeFitSpec(
                reference.getJSONObject("inputs").getJSONObject(role)).copy(name="Command restart $role ${System.nanoTime()}"))).fits.single().id
            val source=create("source"); val first=create("target"); val second=create("target")
            val baseline=fit(first).stats
            send(BridgeOperation.AddCommandFit(source,first),source,first)
            send(BridgeOperation.AddCommandFit(source,second),source,second)
            assertNotEquals(baseline,fit(first).stats)
            val catalog=EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS)
            send(BridgeOperation.FitImplant(source,catalog.items.single { it.name=="Shield Command Mindlink" }.id),source)
            val burst=fit(source).modules.single { it.name=="Shield Command Burst II" }.index
            send(BridgeOperation.SetModuleCharge(source,burst,catalog.items.single { it.name=="Shield Harmonizing Charge" }.id),source)
            send(BridgeOperation.SetCommandFitActive(source,second,false),source,second)
            assertEquals(baseline,fit(second).stats); assertNotEquals(fit(first).stats,fit(second).stats)
            val ownBefore=fit(source).stats
            send(BridgeOperation.AddCommandFit(source,source),source)
            assertEquals("Self association adds no extra incoming command bonus",ownBefore,fit(source).stats)
            send(BridgeOperation.AddCommandFit(first,source),source,first)
            EngineRuntime.selectFit(context,first).get(30,TimeUnit.SECONDS)
            val state=EngineRuntime.offlineFeatureState(context,first).get(30,TimeUnit.SECONDS)
            val ids=listOf(source,first,second)
            val receipt=JSONObject().put("source",source).put("first",first).put("second",second)
                .put("session",state.context.sessionId).put("profiles",profiles(state))
                .put("snapshots",JSONArray(ids.map(::snapshot))).put("recent",JSONArray(EngineRuntime.recent.value))
            assertTrue(prefs.edit().putString("seed",receipt.toString()).commit())
        } else {
            val saved=JSONObject(checkNotNull(prefs.getString("seed",null)) { "Run command_fits_seed first on disposable app data." })
            val source=saved.getString("source"); val first=saved.getString("first"); val second=saved.getString("second")
            val state=EngineRuntime.offlineFeatureState(context,first).get(30,TimeUnit.SECONDS)
            assertNotEquals("New process required, not Activity recreation",saved.getString("session"),state.context.sessionId)
            assertEquals(saved.getJSONObject("profiles").toString(),profiles(state).toString())
            assertEquals(saved.getJSONArray("recent").toString(),JSONArray(EngineRuntime.recent.value).toString())
            val ids=listOf(source,first,second)
            assertEquals(saved.getJSONArray("snapshots").toString(),JSONArray(ids.map(::snapshot)).toString())
            assertEquals(0,state.history.undoCount); assertEquals(0,state.history.redoCount)
            for (id in ids) {
                val history=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
                assertEquals(0,history.undoCount); assertEquals(0,history.redoCount)
            }
            EngineRuntime.selectFit(context,second).get(30,TimeUnit.SECONDS)
            click("commands-open")
            compose.onNodeWithTag("command-$source-state").assertTextEquals("Command link disabled")
            click("command-$source-open")
            compose.waitUntil(120_000) { !model.busy && (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id==source }
            click("commands-return")
            compose.waitUntil(120_000) { !model.busy && (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id==second }
            compose.onNodeWithTag("commands-recipient").assertExists()
            compose.onNodeWithTag("command-$source-state").assertTextEquals("Command link disabled")
        }
    }
}
