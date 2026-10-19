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

/** Run projected_modules_seed, force-stop/relaunch without clearing data, then projected_modules_reopen.
 * This checks exact persistence and cross-feature invariants, not an independent numerical oracle. */
@RunWith(AndroidJUnit4::class)
class ProjectedModulePersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun details(id: String) = EngineRuntime.projectedModuleDetails(context,id,fit(id).revision).get(30,TimeUnit.SECONDS)
    private fun send(op: BridgeOperation,vararg ids: String): BridgeResponse = EngineRuntime.request(context,op,
        ids.toSet().associateWith { fit(it).revision }).get(120,TimeUnit.SECONDS).also { assertTrue(it.error?.message,it.isSuccess) }
    private fun feature(op: String,args: JSONObject,id: String): OfflineFeatureState {
        val state=EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS)
        val response=EngineRuntime.offlineFeatureRequest(context,state.context,op,args,id).get(120,TimeUnit.SECONDS)
        assertTrue(response.error?.message,response.ok); return response.state!!
    }
    private fun rows(id: String): JSONArray = JSONArray(details(id).modules.map { row ->
        JSONObject().put("index",row.index).put("key",row.objectKey).put("item",row.itemId).put("name",row.name)
            .put("state",row.state.name).put("charge_id",row.chargeId ?: JSONObject.NULL)
            .put("charge_name",row.chargeName ?: JSONObject.NULL).put("range_m",row.rangeM ?: JSONObject.NULL)
            .put("editable",row.editable).put("reason",row.unavailableReason ?: JSONObject.NULL)
            .put("spool",if (!row.editable) JSONObject.NULL else EngineRuntime.projectedModuleOptions(context,id,
                fit(id).revision,row).get(30,TimeUnit.SECONDS).spool?.let { s -> JSONObject()
                .put("override",s.overrideCycles ?: JSONObject.NULL).put("current",s.currentCycles).put("default",s.defaultCycles)
                .put("minimum",s.minimumCycles).put("maximum",s.maximumCycles).put("seconds",s.currentSeconds)
                .put("default_seconds",s.defaultSeconds).put("minimum_seconds",s.minimumSeconds).put("maximum_seconds",s.maximumSeconds)
                .put("choices",JSONArray(s.choices)) } ?: JSONObject.NULL)
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

    @Test fun exactIdentitiesMenuSpoolLegacyPrefixAndSharedProfileSurviveFourLinkBoundariesAndNewProcess() {
        val phase=InstrumentationRegistry.getArguments().getString("offline_features_phase")
        assertTrue("Choose projected_modules_seed or projected_modules_reopen",phase in setOf("projected_modules_seed","projected_modules_reopen"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val prefs=context.getSharedPreferences("projected_modules_qualification",Context.MODE_PRIVATE)
        if (phase=="projected_modules_seed") {
            fun create(legacy: Boolean): String = send(BridgeOperation.CreateFit(FitSpec("Projected restart ${System.nanoTime()}",
                "Rifter",5,false,DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),emptyList(),emptyList(),
                environments=if (legacy) listOf(EnvironmentSpec("Class 1 Red Giant Effects",ModuleState.ONLINE)) else emptyList()))).fits.single().id
            val first=create(true); val second=create(false)
            val catalog=EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS)
            fun item(name: String) = catalog.items.single { it.name==name }.id
            send(BridgeOperation.AddProjectedModule(first,item("Remote Sensor Booster II")),first)
            var row=details(first).modules.last()
            send(BridgeOperation.SetProjectedModuleCharge(first,row.index,row.objectKey,item("Scan Resolution Script")),first)
            send(BridgeOperation.SetProjectedModuleRange(first,row.index,row.objectKey,1234.5),first)
            send(BridgeOperation.SetProjectedModuleState(first,row.index,row.objectKey,ProjectedModuleStateAction.OVERHEAT),first)
            val expectedOverrides=mutableListOf<Int>()
            for (maximum in listOf(false,true)) {
                send(BridgeOperation.AddProjectedModule(first,item("Heavy Mutadaptive Remote Armor Repairer II")),first)
                row=details(first).modules.last()
                val spool=EngineRuntime.projectedModuleOptions(context,first,fit(first).revision,row).get(30,TimeUnit.SECONDS).spool!!
                val cycles=if (maximum) spool.maximumCycles else 0
                assertTrue(cycles in spool.choices); expectedOverrides.add(cycles)
                send(BridgeOperation.SetProjectedModuleSpool(first,row.index,row.objectKey,cycles),first)
                send(BridgeOperation.SetProjectedModuleRange(first,row.index,row.objectKey,if (cycles==0) 0.0 else null),first)
            }
            val before=rows(first).toString()
            // Exercise all four low-level source ORM refresh paths on the projector-owning fit.
            val operations=listOf(BridgeOperation.AddProjection(first,second),BridgeOperation.RemoveProjection(first,second),
                BridgeOperation.AddCommand(first,second),BridgeOperation.RemoveCommand(first,second))
            for (operation in operations) {
                send(operation,first,second)
                assertEquals("Link refresh must preserve every projected input and object identity",before,rows(first).toString())
            }
            // The low-level refresh paths do not fill local slots. Materialize the GUI
            // command postcondition before this full-stat comparison.
            send(BridgeOperation.AddProjectedFit(first,second),first,second)
            send(BridgeOperation.RemoveProjectedFit(first,second),first,second)
            val unchangedSecond=fit(second).stats
            send(BridgeOperation.AddProjectedFit(first,second),first,second)
            assertEquals("Incoming individual projectors do not project onward through a saved-fit association",unchangedSecond,fit(second).stats)
            val name="Projected shared profile ${System.nanoTime()}"
            var state=feature("create_profile",JSONObject().put("name",name).put("source","builtin:all5"),first)
            val profile=state.profiles.single { it.name==name }.id
            for (id in listOf(first,second)) state=feature("assign_profile",JSONObject().put("fit_id",id).put("profile_id",profile),first)
            assertEquals(before,rows(first).toString())
            assertEquals(profile,state.bindings.getValue(first).profileId); assertEquals(profile,state.bindings.getValue(second).profileId)
            assertEquals(4,details(first).modules.size); assertFalse(details(first).modules.first().editable)
            val overrides=details(first).modules.filter { it.editable }.mapNotNull { r ->
                EngineRuntime.projectedModuleOptions(context,first,fit(first).revision,r).get(30,TimeUnit.SECONDS).spool?.overrideCycles }
            assertEquals(expectedOverrides,overrides)
            EngineRuntime.selectFit(context,first).get(30,TimeUnit.SECONDS)
            state=EngineRuntime.offlineFeatureState(context,first).get(30,TimeUnit.SECONDS)
            val receipt=JSONObject().put("first",first).put("second",second).put("session",state.context.sessionId)
                .put("profiles",profiles(state)).put("snapshots",JSONArray(listOf(first,second).map(::snapshot)))
                .put("recent",JSONArray(EngineRuntime.recent.value)).put("overrides",JSONArray(expectedOverrides))
            assertTrue(prefs.edit().putString("seed",receipt.toString()).commit())
        } else {
            val saved=JSONObject(checkNotNull(prefs.getString("seed",null)) { "Run projected_modules_seed first on disposable app data." })
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
            compose.onNodeWithTag("projected-modules-open").performScrollTo().performClick()
            val model=ViewModelProvider(compose.activity)[ProjectedModuleModel::class.java]
            compose.waitUntil(120_000) { !model.loading && model.currentDetails?.fitId==first }
            compose.onNodeWithTag("projected-module-0-edit-range").assertIsNotEnabled()
            for (offset in 0..1) {
                val index=offset+2; val raw=saved.getJSONArray("overrides").getInt(offset)
                compose.onNodeWithTag("projected-module-$index-options").performScrollTo().performClick()
                compose.waitUntil(30_000) { !model.optionsLoading && model.currentOptions?.index==index }
                assertEquals(raw,model.currentOptions!!.spool!!.overrideCycles)
                compose.onNodeWithTag("projected-module-$index-spool-mode").assertTextEquals("Explicit override: $raw cycles")
            }
        }
    }
}
