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

/** Run projected_drones_seed, force-stop/relaunch without clearing data, then projected_drones_reopen.
 * This checks exact persistence and cross-feature invariants, not an independent numerical oracle. */
@RunWith(AndroidJUnit4::class)
class ProjectedDronePersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun details(id: String) = EngineRuntime.projectedDroneDetails(context,id,fit(id).revision).get(30,TimeUnit.SECONDS)
    private fun send(op: BridgeOperation,vararg ids: String): BridgeResponse = EngineRuntime.request(context,op,
        ids.toSet().associateWith { fit(it).revision }).get(120,TimeUnit.SECONDS).also { assertTrue(it.error?.message,it.isSuccess) }
    private fun feature(op: String,args: JSONObject,id: String): OfflineFeatureState {
        val state=EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS)
        val response=EngineRuntime.offlineFeatureRequest(context,state.context,op,args,id).get(120,TimeUnit.SECONDS)
        assertTrue(response.error?.message,response.ok); return response.state!!
    }
    private fun rows(id: String): JSONArray = JSONArray(details(id).stacks.map { row ->
        JSONObject().put("index",row.index).put("key",row.objectKey).put("item",row.itemId).put("name",row.name)
            .put("amount",row.amount).put("active",row.active).put("range_m",row.rangeM ?: JSONObject.NULL)
            .put("editable",row.editable).put("reason",row.unavailableReason ?: JSONObject.NULL)
    })
    private fun snapshot(id: String): JSONObject {
        val f=fit(id)
        return JSONObject().put("id",id).put("revision",f.revision).put("name",f.name).put("rows",rows(id))
            .put("projections",JSONArray(f.projections.map { JSONObject().put("source",it.sourceId).put("active",it.active)
                .put("range",it.rangeM ?: JSONObject.NULL).put("amount",it.amount) }))
            .put("commands",JSONArray(f.commands.map { JSONObject().put("source",it.sourceId).put("active",it.active) }))
            .put("skills",JSONObject().apply { f.skills.toSortedMap().forEach { (name,level) -> put(name,level ?: JSONObject.NULL) } })
            .put("stats",JSONObject().apply { f.stats.toSortedMap().forEach { (name,value) ->
                put(name,JSONObject().put("value",value.value.raw).put("unit",value.unit)) } })
    }
    private fun profiles(state: OfflineFeatureState) = JSONObject()
        .put("profiles",JSONArray(state.profiles.map { p -> JSONObject().put("id",p.id).put("name",p.name)
            .put("revision",p.revision).put("readonly",p.readonly).put("default",p.defaultLevel ?: JSONObject.NULL)
            .put("levels",JSONObject().apply { p.levels.toSortedMap().forEach { (skill,level) -> put(skill.toString(),level ?: JSONObject.NULL) } }) }))
        .put("bindings",JSONObject().apply { state.bindings.toSortedMap().forEach { (id,binding) ->
            put(id,JSONObject().put("profile",binding.profileId).put("revision",binding.revision)) } })

    @Test fun exactStacksRangesSharedProfilesAndFiveRefreshPathsSurviveNewProcess() {
        val phase=InstrumentationRegistry.getArguments().getString("offline_features_phase")
        assertTrue("Choose projected_drones_seed or projected_drones_reopen",phase in setOf("projected_drones_seed","projected_drones_reopen"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val prefs=context.getSharedPreferences("projected_drones_qualification",Context.MODE_PRIVATE)
        if (phase=="projected_drones_seed") {
            fun create(): String = send(BridgeOperation.CreateFit(FitSpec("Projected drone restart ${System.nanoTime()}",
                "Rifter",5,false,DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),emptyList(),emptyList()))).fits.single().id
            val first=create(); val second=create()
            val catalog=EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS)
            fun item(name: String) = catalog.items.single { it.name==name }.id
            val originalRecent=EngineRuntime.recent.value.toList()
            for ((name,amount) in listOf("Warrior SW-300" to 3,"Light Armor Maintenance Bot I" to 2)) {
                send(BridgeOperation.AddProjectedDrone(first,item(name)),first)
                val row=details(first).stacks.last()
                send(BridgeOperation.SetProjectedDroneAmount(first,row.index,row.objectKey,amount),first)
                send(BridgeOperation.SetProjectedDroneRange(first,row.index,row.objectKey,if (row.index==0) 0.0 else 1234.5),first)
                if (row.index==1) send(BridgeOperation.SetProjectedDroneActive(first,row.index,row.objectKey,false),first)
            }
            assertEquals(originalRecent,EngineRuntime.recent.value)
            val before=rows(first).toString()
            // Four low-level paths plus the command-policy add below exercise all five source ORM refreshes.
            val operations=listOf(BridgeOperation.AddProjection(first,second),BridgeOperation.RemoveProjection(first,second),
                BridgeOperation.AddCommand(first,second),BridgeOperation.RemoveCommand(first,second))
            for (operation in operations) {
                send(operation,first,second)
                assertEquals("Link refresh must preserve every projected input and object identity",before,rows(first).toString())
            }
            send(BridgeOperation.AddCommandFit(first,second),first,second)
            assertEquals("Command-policy source refresh must preserve every projected drone input and identity",before,rows(first).toString())
            send(BridgeOperation.RemoveCommandFit(first,second),first,second)
            // The low-level refresh paths do not fill local slots. Materialize the GUI
            // command postcondition before this full-stat comparison.
            send(BridgeOperation.AddProjectedFit(first,second),first,second)
            send(BridgeOperation.RemoveProjectedFit(first,second),first,second)
            val unchangedSecond=fit(second).stats
            send(BridgeOperation.AddProjectedFit(first,second),first,second)
            assertEquals("Incoming individual projectors do not project onward through a saved-fit association",unchangedSecond,fit(second).stats)
            val name="Projected drone shared profile ${System.nanoTime()}"
            var state=feature("create_profile",JSONObject().put("name",name).put("source","builtin:all5"),first)
            val profile=state.profiles.single { it.name==name }.id
            for (id in listOf(first,second)) state=feature("assign_profile",JSONObject().put("fit_id",id).put("profile_id",profile),first)
            assertEquals(before,rows(first).toString())
            assertEquals(profile,state.bindings.getValue(first).profileId); assertEquals(profile,state.bindings.getValue(second).profileId)
            assertEquals(2,details(first).stacks.size)
            assertEquals(listOf(3,2),details(first).stacks.map { it.amount })
            assertEquals(listOf(3,0),details(first).stacks.map { it.active })
            val navigation=state.skills.single { it.name=="Navigation" }.id
            val owner=state.profiles.single { it.id==profile }
            state=feature("set_profile_skill",JSONObject().put("profile_id",profile).put("revision",owner.revision)
                .put("skill_id",navigation).put("level",4),first)
            assertEquals(before,rows(first).toString())
            assertEquals(4,fit(first).skills["Navigation"]); assertEquals(4,fit(second).skills["Navigation"])
            EngineRuntime.selectFit(context,first).get(30,TimeUnit.SECONDS)
            state=EngineRuntime.offlineFeatureState(context,first).get(30,TimeUnit.SECONDS)
            val receipt=JSONObject().put("first",first).put("second",second).put("session",state.context.sessionId)
                .put("profiles",profiles(state)).put("snapshots",JSONArray(listOf(first,second).map(::snapshot)))
                .put("recent",JSONArray(EngineRuntime.recent.value))
            assertTrue(prefs.edit().putString("seed",receipt.toString()).commit())
        } else {
            val saved=JSONObject(checkNotNull(prefs.getString("seed",null)) { "Run projected_drones_seed first on disposable app data." })
            val first=saved.getString("first"); val second=saved.getString("second")
            val state=EngineRuntime.offlineFeatureState(context,first).get(30,TimeUnit.SECONDS)
            assertNotEquals("A new process is required, not Activity recreation",saved.getString("session"),state.context.sessionId)
            assertEquals(saved.getJSONObject("profiles").toString(),profiles(state).toString())
            assertEquals(saved.getJSONArray("recent").toString(),JSONArray(EngineRuntime.recent.value).toString())
            assertEquals(saved.getJSONArray("snapshots").toString(),JSONArray(listOf(first,second).map(::snapshot)).toString())
            assertEquals(0,state.history.undoCount); assertEquals(0,state.history.redoCount)
            for (id in listOf(first,second)) {
                val history=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
                assertEquals(0,history.undoCount); assertEquals(0,history.redoCount)
            }
            EngineRuntime.selectFit(context,first).get(30,TimeUnit.SECONDS)
            compose.onNodeWithTag("projected-drones-open").performScrollTo().performClick()
            val model=ViewModelProvider(compose.activity)[ProjectedDroneModel::class.java]
            compose.waitUntil(120_000) { !model.loading && model.currentDetails?.fitId==first }
            compose.onNodeWithTag("projected-drone-0-quantity").assertTextEquals("3 active / 3 total")
            compose.onNodeWithTag("projected-drone-1-quantity").performScrollTo().assertTextEquals("0 active / 2 total")
            val options=EngineRuntime.projectedDroneOptions(context,first,fit(first).revision,details(first).stacks.last()).get(30,TimeUnit.SECONDS)
            assertTrue(options.activationAllowed)
            val library=EngineRuntime.offlineFeatureState(context,null).get(30,TimeUnit.SECONDS)
            assertEquals(0,library.history.undoCount); assertEquals(0,library.history.redoCount)
        }
    }
}
