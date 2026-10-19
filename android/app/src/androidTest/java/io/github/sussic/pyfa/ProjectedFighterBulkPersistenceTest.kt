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

/** Run projected_fighter_bulk_seed, force-stop/relaunch without clearing data, then projected_fighter_bulk_reopen.
 * This checks exact public persistence and cross-feature invariants, not an independent numerical oracle.
 * The host source proof separately covers the complete eligible catalogue ability set. */
@RunWith(AndroidJUnit4::class)
class ProjectedFighterBulkPersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun details(id: String) = EngineRuntime.projectedFighterDetails(context,id,fit(id).revision).get(30,TimeUnit.SECONDS)
    private fun send(op: BridgeOperation,vararg ids: String): BridgeResponse = EngineRuntime.request(context,op,
        ids.toSet().associateWith { fit(it).revision }).get(120,TimeUnit.SECONDS).also { assertTrue(it.error?.message,it.isSuccess) }
    private fun feature(op: String,args: JSONObject,id: String): OfflineFeatureState {
        val state=EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS)
        val response=EngineRuntime.offlineFeatureRequest(context,state.context,op,args,id).get(120,TimeUnit.SECONDS)
        assertTrue(response.error?.message,response.ok); return response.state!!
    }
    private fun rows(id: String): JSONArray = JSONArray(details(id).squadrons.map { row ->
        JSONObject().put("index",row.index).put("key",row.objectKey).put("item",row.itemId).put("name",row.name)
            .put("amount",row.amount).put("maximum",row.maxSize).put("active",row.active).put("range_m",row.rangeM ?: JSONObject.NULL)
            .put("editable",row.editable).put("reason",row.unavailableReason ?: JSONObject.NULL)
            .put("abilities",JSONArray(EngineRuntime.projectedFighterOptions(context,id,fit(id).revision,row).get(30,TimeUnit.SECONDS).abilities.map {
                JSONObject().put("effect",it.effectId).put("name",it.name).put("active",it.active) }))
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

    @Test fun selectedAbilityStateRangeAndRemovalRestoreExactlyThroughFiveRefreshesAndNewProcess() {
        val phase=InstrumentationRegistry.getArguments().getString("offline_features_phase")
        assertTrue("Choose projected_fighter_bulk_seed or projected_fighter_bulk_reopen",phase in setOf("projected_fighter_bulk_seed","projected_fighter_bulk_reopen"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val prefs=context.getSharedPreferences("projected_fighter_bulk_qualification",Context.MODE_PRIVATE)
        if (phase=="projected_fighter_bulk_seed") {
            fun create(): String = send(BridgeOperation.CreateFit(FitSpec("Projected fighter restart ${System.nanoTime()}",
                "Rifter",5,false,DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),emptyList(),emptyList()))).fits.single().id
            val first=create(); val second=create()
            val catalog=EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS)
            fun item(name: String) = catalog.items.single { it.name==name }.id
            val originalRecent=EngineRuntime.recent.value.toList()
            for ((position,name) in listOf("Dromi I","Siren I","Dromi I").withIndex()) {
                send(BridgeOperation.AddProjectedFighter(first,item(name)),first)
                val row=details(first).squadrons.last()
                send(BridgeOperation.SetProjectedFighterAmount(first,row.index,row.objectKey,position+1),first)
                send(BridgeOperation.SetProjectedFighterRange(first,row.index,row.objectKey,if(position==0) 0.0 else 1234.5),first)
                if(position==0) send(BridgeOperation.ToggleProjectedFighterAbility(first,row.index,row.objectKey,6435),first)
                else if(position==2) send(BridgeOperation.SetProjectedFighterActive(first,row.index,row.objectKey,false),first)
            }
            assertEquals(3,details(first).squadrons.map { it.objectKey }.distinct().size)
            val initial=rows(first).toString(); val initialStats=fit(first).stats
            val firstRows=details(first).squadrons
            fun selected(vararg indices: Int)=indices.map { ProjectedFighterSelectionRow(firstRows[it].index,firstRows[it].objectKey) }
            var history=EngineRuntime.editHistory(context,first).get(30,TimeUnit.SECONDS).undoCount
            // Exercise the source's implicit main append and missing secondary ability in a real request.
            val ability=BridgeOperation.ToggleProjectedFighterAbilities(first,selected(0).single(),selected(2,1),6435)
            send(ability,first)
            assertEquals(history+1,EngineRuntime.editHistory(context,first).get(30,TimeUnit.SECONDS).undoCount)
            for (index in listOf(0,2)) assertTrue(EngineRuntime.projectedFighterOptions(context,first,fit(first).revision,
                details(first).squadrons[index]).get(30,TimeUnit.SECONDS).abilities.single { it.effectId==6435 }.active)
            assertEquals(JSONArray(initial).getJSONObject(1).toString(),rows(first).getJSONObject(1).toString())
            send(BridgeOperation.Undo(first),first); assertEquals(initial,rows(first).toString()); assertEquals(initialStats,fit(first).stats)
            send(BridgeOperation.Redo(first),first)
            val bothWebEnabled=rows(first).toString(); val bothStats=fit(first).stats
            send(BridgeOperation.SetProjectedFightersActive(first,selected(2,0),true),first)
            send(BridgeOperation.Undo(first),first); assertEquals(bothWebEnabled,rows(first).toString()); assertEquals(bothStats,fit(first).stats)
            send(BridgeOperation.Redo(first),first)
            send(BridgeOperation.SetProjectedFighterRanges(first,selected(2,0),63.7),first)
            val exact=rows(first).toString(); val exactStats=fit(first).stats
            assertEquals(63.7,details(first).squadrons[0].rangeM!!,0.0); assertEquals(63.7,details(first).squadrons[2].rangeM!!,0.0)
            history=EngineRuntime.editHistory(context,first).get(30,TimeUnit.SECONDS).undoCount
            send(BridgeOperation.RemoveProjectedFighters(first,selected(2,0)),first)
            assertEquals(history+1,EngineRuntime.editHistory(context,first).get(30,TimeUnit.SECONDS).undoCount)
            assertEquals(listOf(firstRows[1].copy(index=0)),details(first).squadrons)
            send(BridgeOperation.Undo(first),first); assertEquals(exact,rows(first).toString()); assertEquals(exactStats,fit(first).stats)
            send(BridgeOperation.Redo(first),first); send(BridgeOperation.Undo(first),first)
            assertEquals(exact,rows(first).toString()); assertEquals(originalRecent,EngineRuntime.recent.value)
            val before=rows(first).toString()
            // Four low-level paths plus the command-policy add below exercise all five source ORM refreshes.
            val operations=listOf(BridgeOperation.AddProjection(first,second),BridgeOperation.RemoveProjection(first,second),
                BridgeOperation.AddCommand(first,second),BridgeOperation.RemoveCommand(first,second))
            for (operation in operations) {
                send(operation,first,second)
                assertEquals("Link refresh must preserve every projected input and object identity",before,rows(first).toString())
            }
            send(BridgeOperation.AddCommandFit(first,second),first,second)
            assertEquals("Command-policy source refresh must preserve every projected fighter input and identity",before,rows(first).toString())
            send(BridgeOperation.RemoveCommandFit(first,second),first,second)
            // The low-level refresh paths do not fill local slots. Materialize the GUI
            // command postcondition before this full-stat comparison.
            send(BridgeOperation.AddProjectedFit(first,second),first,second)
            send(BridgeOperation.RemoveProjectedFit(first,second),first,second)
            val unchangedSecond=fit(second).stats
            send(BridgeOperation.AddProjectedFit(first,second),first,second)
            assertEquals("Incoming individual projectors do not project onward through a saved-fit association",unchangedSecond,fit(second).stats)
            val name="Projected fighter shared profile ${System.nanoTime()}"
            var state=feature("create_profile",JSONObject().put("name",name).put("source","builtin:all5"),first)
            val profile=state.profiles.single { it.name==name }.id
            for (id in listOf(first,second)) state=feature("assign_profile",JSONObject().put("fit_id",id).put("profile_id",profile),first)
            assertEquals(before,rows(first).toString())
            assertEquals(profile,state.bindings.getValue(first).profileId); assertEquals(profile,state.bindings.getValue(second).profileId)
            assertEquals(3,details(first).squadrons.size)
            assertEquals(listOf(1,2,3),details(first).squadrons.map { it.amount })
            assertTrue(details(first).squadrons.all { it.active })
            val navigation=state.skills.single { it.name=="Navigation" }.id
            val owner=state.profiles.single { it.id==profile }
            state=feature("set_profile_skill",JSONObject().put("profile_id",profile).put("revision",owner.revision)
                .put("skill_id",navigation).put("level",4),first)
            assertEquals(before,rows(first).toString())
            assertEquals(4,fit(first).skills["Navigation"]); assertEquals(4,fit(second).skills["Navigation"])
            val previousIds=EngineRuntime.library.value.map { it.id }.toSet()
            val copied=send(BridgeOperation.DuplicateFit(first,"Copied projected fighters ${System.nanoTime()}"),first).fits.single { it.id !in previousIds }.id
            val originals=details(first).squadrons; val copies=details(copied).squadrons
            assertEquals(originals.map { it.copy(objectKey="") },copies.map { it.copy(objectKey="") })
            assertTrue(originals.map { it.objectKey }.toSet().intersect(copies.map { it.objectKey }.toSet()).isEmpty())
            val ids=listOf(first,second,copied)
            EngineRuntime.selectFit(context,first).get(30,TimeUnit.SECONDS)
            state=EngineRuntime.offlineFeatureState(context,first).get(30,TimeUnit.SECONDS)
            val receipt=JSONObject().put("first",first).put("second",second).put("ids",JSONArray(ids)).put("session",state.context.sessionId)
                .put("profiles",profiles(state)).put("snapshots",JSONArray(ids.map(::snapshot)))
                .put("recent",JSONArray(EngineRuntime.recent.value))
            assertTrue(prefs.edit().putString("seed",receipt.toString()).commit())
        } else {
            val saved=JSONObject(checkNotNull(prefs.getString("seed",null)) { "Run projected_fighter_bulk_seed first on disposable app data." })
            val first=saved.getString("first"); val second=saved.getString("second")
            val ids=saved.getJSONArray("ids").let { values -> (0 until values.length()).map { values.getString(it) } }
            val state=EngineRuntime.offlineFeatureState(context,first).get(30,TimeUnit.SECONDS)
            assertNotEquals("A new process is required, not Activity recreation",saved.getString("session"),state.context.sessionId)
            assertEquals(saved.getJSONObject("profiles").toString(),profiles(state).toString())
            assertEquals(saved.getJSONArray("recent").toString(),JSONArray(EngineRuntime.recent.value).toString())
            assertEquals(saved.getJSONArray("snapshots").toString(),JSONArray(ids.map(::snapshot)).toString())
            assertEquals(0,state.history.undoCount); assertEquals(0,state.history.redoCount)
            for (id in ids) {
                val history=EngineRuntime.editHistory(context,id).get(30,TimeUnit.SECONDS)
                assertEquals(0,history.undoCount); assertEquals(0,history.redoCount)
            }
            EngineRuntime.selectFit(context,first).get(30,TimeUnit.SECONDS)
            compose.onNodeWithTag("projected-fighters-open").performScrollTo().performClick()
            val model=ViewModelProvider(compose.activity)[ProjectedFighterModel::class.java]
            compose.waitUntil(120_000) { !model.loading && model.currentDetails?.fitId==first }
            compose.onNodeWithTag("projected-fighter-0-quantity").assertTextContains("1 fighters",substring=true)
            compose.onNodeWithTag("projected-fighter-2-quantity").performScrollTo().assertTextContains("Active",substring=true)
            val firstOptions=EngineRuntime.projectedFighterOptions(context,first,fit(first).revision,details(first).squadrons.first()).get(30,TimeUnit.SECONDS)
            assertTrue(firstOptions.abilities.single { it.effectId==6435 }.active)
            val secondOptions=EngineRuntime.projectedFighterOptions(context,first,fit(first).revision,details(first).squadrons.last()).get(30,TimeUnit.SECONDS)
            assertTrue(secondOptions.abilities.single { it.effectId==6435 }.active)
            val library=EngineRuntime.offlineFeatureState(context,null).get(30,TimeUnit.SECONDS)
            assertEquals(0,library.history.undoCount); assertEquals(0,library.history.redoCount)
        }
    }
}
