package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.os.Process
import android.util.Log
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import io.github.sussic.pyfa.ModuleTestJson.obj
import io.github.sussic.pyfa.ModuleTestJson.compare

@RunWith(AndroidJUnit4::class)
class TargetingTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[TargetingModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().performClick(); sync() }
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList()): BridgeResponse {
        val result = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess); return result
    }
    private fun query(id: String) = EngineRuntime.targetingDetails(context,id).get(120,TimeUnit.SECONDS)
    private fun graph() = JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120,TimeUnit.SECONDS))
    private fun scalar(row: TargetingScalar) = obj("value" to row.value.raw,"value_type" to when(row.value) {
        is StatValue.Integer -> "integer"; is StatValue.Decimal -> "decimal"; StatValue.Unavailable -> "unavailable"; else -> error("Non-numeric targeting")
    },"unit" to row.unit,"display" to row.display,"detail" to row.detail)
    private fun raw(row: FitTargeting) = obj("fit_id" to row.fitId,"revision" to row.revision,"targeting" to JSONObject().apply {
        put("main",JSONObject().apply { row.main.forEach { (key,value) -> put(key,scalar(value)) } })
        put("sensor_type",row.sensorType)
        put("lock_times",JSONArray(row.lockTimes.map { obj("name" to it.name,"radius" to it.radius,"time" to scalar(it.time)) }))
        put("holds",JSONArray(row.holds.map { obj("attribute" to it.attribute,"name" to it.name,"present" to it.present,"capacity" to scalar(it.capacity)) }))
        row.details.forEach { (key,value) -> put(key,scalar(value)) }
    })
    private fun reference(expected: JSONObject,actual: FitTargeting) = compare(expected.getJSONObject("targeting"),raw(actual).getJSONObject("targeting"),strict=false)
    private fun wire(value: Any): String = when(value) {
        is JSONObject -> value.keys().asSequence().joinToString(",","{","}") { JSONObject.quote(it)+":"+wire(value.get(it)) }
        is JSONArray -> (0 until value.length()).joinToString(",","[","]") { wire(value.get(it)) }
        is String -> JSONObject.quote(value)
        else -> value.toString()
    }
    private fun create(value: JSONObject): String {
        val native=JSONObject(wire(value));assertFalse(native.getBoolean("ignore_restrictions"));assertEquals(0,native.getJSONArray("cargo").length())
        native.remove("ignore_restrictions");native.remove("cargo")
        val spec=BridgeCodec.decodeFitSpec(wire(native))
        val id=send(BridgeOperation.CreateFit(spec.copy(name="C03 ${spec.name}"))).fits.single().id
        assertEquals(spec.modules.size,fit(id).modules.size)
        spec.modules.forEachIndexed { index,m -> assertEquals(m.name,fit(id).modules[index].name);assertEquals(m.state,fit(id).modules[index].state);assertEquals(m.charge,fit(id).modules[index].charge) }
        return id
    }
    private fun ready(id: String) {
        compose.waitUntil(60_000) { !model.loading && model.error==null && model.details?.let { it.fitId==id && it.revision==fit(id).revision }==true };sync()
    }
    private fun open(id: String) {
        if(compose.onAllNodesWithTag("targeting-back").fetchSemanticsNodes().isNotEmpty())click("targeting-back")
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS);sync();click("targeting-open");ready(id)
        val row=query(id)
        for((key,value) in row.main)compose.onNodeWithTag("targeting-$key-value").performScrollTo().assertTextEquals(value.display ?: "Unavailable")
    }
    private fun expand(key: String) {
        if(compose.onAllNodesWithTag("targeting-$key-precision").fetchSemanticsNodes().isEmpty())click("targeting-$key-details")
    }
    private fun detail(key: String,row: TargetingScalar,absent: Boolean=false) {
        expand(key)
        val exact=if(row.value==StatValue.Unavailable) { if(absent)"Not present on this hull" else "Unavailable" } else row.value.raw.toString()
        compose.onNodeWithTag("targeting-$key-precision").performScrollTo().assertTextEquals("Full precision: $exact ${row.unit}")
        row.detail?.let { compose.onNodeWithTag("targeting-$key-desktop-detail").performScrollTo().assertTextEquals(it) }
    }
    private fun screenshot(name: String) {
        sync();instrumentation.uiAutomation.waitForIdle(500,10_000)
        ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand("screencap -p /sdcard/Download/pyfa-c031-$name.png")).use { it.readBytes() }
    }
    private fun reverse(id: String,redo: Boolean) {
        ready(id);val revision=fit(id).revision
        val history=ViewModelProvider(compose.activity)[EditHistoryModel::class.java]
        compose.waitUntil(60_000) { !history.loading && !history.editing && history.options?.revision==revision }
        val tag=if(redo)"history-redo" else "history-undo"
        compose.onNodeWithTag(tag).performScrollTo().assertIsEnabled();click(tag)
        compose.waitUntil(60_000) { fit(id).revision==revision+1 && !history.loading && !history.editing && history.options?.revision==fit(id).revision }
        assertNull(history.error);ready(id)
    }
    private fun guards(sample: FitTargeting): JSONArray {
        val good=raw(sample).put("version",1)
        val names=listOf("version","extra","missing","unit","boolean","kind","display","revision","missing_hold","changed_hold","hold_order","missing_lock","lock_radius","sensor_type","negative","fractional_integer","hold_presence","target_count_kind")
        for(name in names) {
            val bad=JSONObject(wire(good));val stats=bad.getJSONObject("targeting");val value=stats.getJSONObject("main").getJSONObject("range")
            when(name) {
                "version" -> bad.put("version",2);"extra" -> bad.put("extra",true);"missing" -> bad.remove("targeting")
                "unit" -> value.put("unit","km");"boolean" -> value.put("value",false);"kind" -> value.put("value_type","text")
                "display" -> value.put("display",JSONObject.NULL);"revision" -> bad.put("revision",0)
                "missing_hold" -> stats.getJSONArray("holds").remove(20)
                "changed_hold" -> stats.getJSONArray("holds").getJSONObject(0).put("name","wrong")
                "hold_order" -> stats.getJSONArray("holds").getJSONObject(0).put("attribute","specialAmmoHoldCapacity")
                "missing_lock" -> stats.getJSONArray("lock_times").remove(7)
                "lock_radius" -> stats.getJSONArray("lock_times").getJSONObject(0).put("radius",26)
                "sensor_type" -> stats.put("sensor_type","wrong")
                "negative" -> value.put("value",-1.0).put("value_type","decimal")
                "fractional_integer" -> value.put("value",1.25).put("value_type","integer")
                "hold_presence" -> stats.getJSONArray("holds").getJSONObject(0).let { it.put("present",!it.getBoolean("present")) }
                "target_count_kind" -> stats.getJSONObject("main").getJSONObject("targets").let { it.put("value",it.getDouble("value")).put("value_type","decimal") }
            }
            try { BridgeCodec.decodeTargeting(wire(bad));fail("Accepted $name") } catch(_: BridgeProtocolException) { }
        }
        val absent=JSONObject(wire(good));absent.getJSONObject("targeting").getJSONObject("probe_size")
            .put("value",JSONObject.NULL).put("value_type","unavailable").put("display",JSONObject.NULL).put("detail",JSONObject.NULL)
        assertEquals(StatValue.Unavailable,BridgeCodec.decodeTargeting(wire(absent)).details.getValue("probe_size").value)
        return JSONArray(names)
    }
    @Test fun targetingNavigationHoldsAndRestartOffline() {
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        val phase=InstrumentationRegistry.getArguments().getString("c031_phase") ?: error("Missing phase")
        assertTrue(phase in listOf("prepare0","prepare1","prepare2","restored"));val start=JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120,TimeUnit.SECONDS))
        assertTrue(start.getJSONObject("persistence").getBoolean("enabled"));assertTrue(start.getJSONObject("persistence").getBoolean("opened_existing"))
        assertEquals(when(phase) { "prepare0" -> 268; "prepare1" -> 301; "prepare2" -> 313; else -> 325 },EngineRuntime.library.value.size)
        val stageStart=obj("graph" to ModuleTestJson.typed(graph()),"all_fits" to ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))))
        assertTrue(EngineRuntime.library.value.all { EngineRuntime.editHistory(context,it.id).get(120,TimeUnit.SECONDS).let { h -> h.undoCount==0 && h.redoCount==0 } })
        val bytes=instrumentation.context.assets.open("targeting-expected.json").use { it.readBytes() };val fixture=JSONObject(bytes.toString(Charsets.UTF_8));val cases=fixture.getJSONArray("cases");assertEquals(53,cases.length())
        val file=File(context.noBackupFilesDir,"c031-expected.json");val ids=JSONArray();val observations=JSONArray();val edits=JSONArray();var rejections=JSONArray()
        if(phase!="restored") {
            val prior=if(phase=="prepare0")null else JSONObject(file.readText(Charsets.UTF_8))
            if(prior!=null) {
                assertNotEquals(prior.getInt("pid"),Process.myPid());compare(prior.getJSONObject("graph"),stageStart.getJSONObject("graph"),strict=false)
                compare(prior.getJSONObject("all_fits"),stageStart.getJSONObject("all_fits"),strict=false)
                val previous=prior.getJSONArray("ids");for(i in 0 until previous.length())ids.put(previous.getString(i))
                val previousEdits=prior.getJSONArray("edits");for(i in 0 until previousEdits.length())edits.put(previousEdits.getJSONObject(i))
            }
            val inherited=prior?.getJSONObject("inherited") ?: ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit)))
            val inheritedGraph=(prior?.getJSONObject("inherited_graph") ?: stageStart.getJSONObject("graph")).getJSONObject("data")
            val range=when(phase) { "prepare0" -> 0 until 33; "prepare1" -> 33 until 45; else -> 45 until 53 }
            for(index in range) {
                Log.i("PyfaC031", "START $phase case=$index");val caseStarted=System.nanoTime()
                val case=cases.getJSONObject(index);val id=create(case.getJSONObject("spec"));ids.put(id)
                if(case.has("initial"))reference(case.getJSONObject("initial"),query(id))
                val steps=case.getJSONArray("edits")
                for(i in 0 until steps.length()) {
                    val edit=steps.getJSONObject(i);val a=edit.getJSONObject("args")
                    val operation=when(edit.getString("operation")) {
                        "set_module_states" -> BridgeOperation.SetModuleStates(id,(0 until a.getJSONArray("module_indices").length()).map { a.getJSONArray("module_indices").getInt(it) },ModuleState.valueOf(a.getString("state")))
                        "set_skill_level" -> BridgeOperation.SetSkillLevel(id,a.getString("skill"),a.getInt("level"))
                        "add_cargo" -> BridgeOperation.AddCargo(id,a.getInt("item_id"),a.getLong("quantity"))
                        else -> error("Unknown fixture edit")
                    };send(operation,listOf(id))
                }
                if(case.has("source_spec")) { val source=create(case.getJSONObject("source_spec"));send(BridgeOperation.AddProjection(source,id),listOf(source,id)) }
                reference(case.getJSONObject("expected"),query(id))
                if(steps.length()>0 || case.has("source_spec")) {
                    val revision=fit(id).revision;val applied=raw(query(id))
                    send(BridgeOperation.Undo(id),listOf(id));assertEquals(revision+1,fit(id).revision);reference(case.getJSONObject("initial"),query(id));val undone=raw(query(id))
                    send(BridgeOperation.Redo(id),listOf(id));assertEquals(revision+2,fit(id).revision);reference(case.getJSONObject("expected"),query(id))
                    edits.put(obj("case" to index,"applied" to applied,"undone" to undone,"redone" to raw(query(id))))
                }
                val observed=raw(query(id));val stable=wire(ModuleTestJson.typed(graph()));val history=EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS)
                repeat(3) { Runtime.getRuntime().gc();compare(observed,raw(query(id)),strict=false);assertEquals(stable,wire(ModuleTestJson.typed(graph())));assertEquals(history,EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS)) }
                observations.put(obj("case" to index,"actual" to observed))
                Log.i("PyfaC031", "PASS $phase case=$index elapsed_ms=${(System.nanoTime()-caseStarted)/1_000_000}")
            }
            var uiHistory=prior?.getJSONObject("ui_history")
            if(phase=="prepare0") {
                val historyIndex=(0 until ids.length()).first { cases.getJSONObject(it).getJSONObject("spec").getString("name")=="Drone range" && cases.getJSONObject(it).getJSONArray("edits").length()>0 }
                val historyId=ids.getString(historyIndex);open(historyId);detail("drone_range",query(historyId).main.getValue("drone_range"))
                val historyBefore=raw(query(historyId));reverse(historyId,false)
                reference(cases.getJSONObject(historyIndex).getJSONObject("initial"),query(historyId))
                assertTrue(compose.onAllNodesWithTag("targeting-drone_range-precision").fetchSemanticsNodes().isNotEmpty());val historyUndone=raw(query(historyId))
                reverse(historyId,true);reference(cases.getJSONObject(historyIndex).getJSONObject("expected"),query(historyId))
                detail("drone_range",query(historyId).main.getValue("drone_range"));screenshot("prepare-history")
                uiHistory=obj("case" to historyIndex,"before" to historyBefore,"undone" to historyUndone,"redone" to raw(query(historyId)))
            }
            var copied: String?=null
            if(phase=="prepare2") {
            fun named(name: String)=(0 until cases.length()).first { cases.getJSONObject(it).getJSONObject("spec").getString("name")==name }
            val sensorCases=(0 until cases.length()).distinctBy { cases.getJSONObject(it).getJSONObject("expected").getJSONObject("targeting").getString("sensor_type") }
            assertEquals(setOf("Magnetometric","Ladar","Radar","Gravimetric","Multispectral"),sensorCases.map { cases.getJSONObject(it).getJSONObject("expected").getJSONObject("targeting").getString("sensor_type") }.toSet())
            for(index in sensorCases) {
                val id=ids.getString(index);open(id);expand("sensor")
                compose.onNodeWithTag("targeting-sensor-type").performScrollTo().assertTextEquals("Sensor type: ${cases.getJSONObject(index).getJSONObject("expected").getJSONObject("targeting").getString("sensor_type")}")
            }
            val owner=ids.getString(named("Targeting Vexor"));rejections=guards(query(owner));open(owner)
            val baseline=query(owner)
            detail("range",baseline.main.getValue("range"));detail("scan_resolution",baseline.main.getValue("scan_resolution"))
            for(row in baseline.lockTimes) {
                compose.onNodeWithTag("targeting-lock-${row.radius}").performScrollTo().assertTextEquals("${row.name} [${row.radius} m]: ${row.time.display}")
                compose.onNodeWithTag("targeting-lock-${row.radius}-precision").performScrollTo().assertTextEquals("Full precision: ${row.time.value.numberOrNull()} s")
            };screenshot("prepare-targeting")
            for((name,key) in listOf("Projected ECM" to "sensor","Drone range" to "drone_range","Armor mass" to "align","Microwarpdrive" to "signature","Projected Warp disruption" to "warp_speed","Cargo tooltip refresh" to "cargo")) {
                val id=ids.getString(named(name));open(id);val row=query(id);detail(key,row.main.getValue(key))
                val extra=when(key) { "sensor" -> listOf("jam_chance");"align" -> listOf("mass","agility");"signature" -> listOf("probe_size");"warp_speed" -> listOf("warp_distance","warp_core");"cargo" -> listOf("cargo_used","additional_cargo");else -> emptyList() }
                if(key=="sensor")compose.onNodeWithTag("targeting-sensor-type").performScrollTo().assertTextEquals("Sensor type: ${row.sensorType}")
                for(field in extra)detail(field,row.details.getValue(field));screenshot("prepare-$key")
            }
            val available=fixture.getJSONArray("available_holds")
            for(i in 0 until available.length()) {
                val attr=available.getString(i)
                val index=(0 until cases.length()).first { c -> val holds=cases.getJSONObject(c).getJSONObject("expected").getJSONObject("targeting").getJSONArray("holds");(0 until holds.length()).any { h -> holds.getJSONObject(h).getString("attribute")==attr && holds.getJSONObject(h).getJSONObject("capacity").optDouble("value",0.0)>0 } }
                val id=ids.getString(index);open(id);expand("cargo");val hold=query(id).holds.single { it.attribute==attr };detail(attr,hold.capacity,true);screenshot("prepare-hold-$attr")
            }
            open(owner);expand("cargo")
            for(hold in baseline.holds) {
                val text=if(!hold.present) "Not present on this hull" else hold.capacity.display?.let { "$it ${hold.capacity.unit}" } ?: "Unavailable"
                compose.onNodeWithTag("targeting-${hold.attribute}-value").performScrollTo().assertTextEquals(text)
            };detail("specialShipHoldCapacity",baseline.holds.single { it.attribute=="specialShipHoldCapacity" }.capacity,true);screenshot("prepare-absent")
            val old=EngineRuntime.library.value.map { it.id }.toSet();val copy=send(BridgeOperation.DuplicateFit(owner,"C03 copy"),listOf(owner)).fits.single { it.id !in old }.id
            compare(raw(query(owner)).getJSONObject("targeting"),raw(query(copy)).getJSONObject("targeting"),strict=false)
            send(BridgeOperation.SetSkillLevel(copy,"Drone Avionics",0),listOf(copy))
            reference(cases.getJSONObject(named("Skill Drone Avionics")).getJSONObject("expected"),query(copy))
            reference(cases.getJSONObject(named("Targeting Vexor")).getJSONObject("expected"),query(owner))
            send(BridgeOperation.Undo(copy),listOf(copy))
            reference(cases.getJSONObject(named("Targeting Vexor")).getJSONObject("expected"),query(copy))
            compose.activityRule.scenario.recreate();ready(owner);reference(cases.getJSONObject(named("Targeting Vexor")).getJSONObject("expected"),model.details!!)
            assertTrue(compose.onAllNodesWithTag("targeting-specialShipHoldCapacity-precision").fetchSemanticsNodes().isNotEmpty())
            copied=copy
            }
            val finalGraph=graph();val previous=inherited.getJSONArray("data");val priorIds=(0 until previous.length()).map { previous.getJSONObject(it).getString("id") }
            compare(inherited,ModuleTestJson.typed(JSONArray(priorIds.map { ModuleTestJson.fit(fit(it)) })),strict=false)
            for(id in priorIds)for(field in listOf("records","revisions","modified"))compare(ModuleTestJson.typed(inheritedGraph.getJSONObject(field).get(id)),ModuleTestJson.typed(finalGraph.getJSONObject(field).get(id)),strict=false)
            assertEquals(if(phase=="prepare2")325 else 268+ids.length(),EngineRuntime.library.value.size)
            // Observe every retained case after each additional process boundary.
            while(observations.length()>0)observations.remove(0)
            for(i in 0 until ids.length()) { reference(cases.getJSONObject(i).getJSONObject("expected"),query(ids.getString(i)));observations.put(obj("case" to i,"actual" to raw(query(ids.getString(i))))) }
            file.writeText(wire(obj("pid" to Process.myPid(),"ids" to ids,"inherited" to inherited,"inherited_graph" to ModuleTestJson.typed(inheritedGraph),"graph" to ModuleTestJson.typed(finalGraph),
                "all_fits" to ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))),"edits" to edits,"ui_history" to uiHistory,"copy_id" to copied,"copy_targeting" to copied?.let { raw(query(it)) },
                "outputs" to JSONArray((0 until ids.length()).map { raw(query(ids.getString(it))) }))),Charsets.UTF_8)
        } else {
            val saved=JSONObject(file.readText(Charsets.UTF_8));assertNotEquals(saved.getInt("pid"),Process.myPid())
            compare(saved.getJSONObject("graph"),ModuleTestJson.typed(graph()),strict=false);compare(saved.getJSONObject("all_fits"),ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))),strict=false)
            val previous=saved.getJSONArray("ids");val outputs=saved.getJSONArray("outputs")
            for(index in 0 until previous.length()) { val id=previous.getString(index);ids.put(id);compare(outputs.getJSONObject(index),raw(query(id)),strict=false);reference(cases.getJSONObject(index).getJSONObject("expected"),query(id));observations.put(obj("case" to index,"actual" to raw(query(id)))) }
            assertTrue(EngineRuntime.library.value.all { EngineRuntime.editHistory(context,it.id).get(120,TimeUnit.SECONDS).let { h -> h.undoCount==0 && h.redoCount==0 } })
            compare(saved.getJSONObject("copy_targeting"),raw(query(saved.getString("copy_id"))),strict=false)
            val owner=previous.getString(0);open(owner);detail("range",query(owner).main.getValue("range"));screenshot("restored")
        }
        val saved=JSONObject(file.readText(Charsets.UTF_8));val descriptors=instrumentation.uiAutomation.executeShellCommandRw("dd of=/sdcard/Download/pyfa-c031-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(wire(obj("task" to "C03.1","phase" to phase,"pid" to Process.myPid(),"runtime_start" to start,"stage_start" to stageStart,"ids" to ids,"observations" to observations,
                "protocol_rejections" to rejections,"saved" to saved,"copy_observation" to if(saved.isNull("copy_id"))null else raw(query(saved.getString("copy_id"))),
                "fixture_sha256" to MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) })).toByteArray(Charsets.UTF_8)) };completion.readBytes()
        }
    }
}
