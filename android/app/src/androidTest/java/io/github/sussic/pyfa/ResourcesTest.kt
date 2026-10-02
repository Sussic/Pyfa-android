package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.os.Process
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
class ResourcesTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[ResourcesModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().performClick(); sync() }
    private fun send(operation: BridgeOperation, id: String? = null): BridgeResponse {
        val result = EngineRuntime.request(context, operation, if (id == null) emptyMap() else mapOf(id to fit(id).revision))
            .get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess); return result
    }
    private fun query(id: String) = EngineRuntime.resourceDetails(context, id).get(120, TimeUnit.SECONDS)
    private fun raw(value: FitResources) = obj("fit_id" to value.fitId, "revision" to value.revision,
        "resources" to JSONObject().apply { value.resources.forEach { (name, row) -> put(name, obj(
            "used" to row.used.raw, "total" to row.total.raw,
            "used_type" to kind(row.used), "total_type" to kind(row.total), "unit" to row.unit,
            "overloaded" to row.overloaded, "used_display" to row.usedDisplay, "total_display" to row.totalDisplay,
            "used_detail" to row.usedDetail, "total_detail" to row.totalDetail)) } })
    private fun kind(value: StatValue) = when (value) {
        is StatValue.Integer -> "integer"; is StatValue.Decimal -> "decimal"; StatValue.Unavailable -> "unavailable"; else -> error("Non-numeric resource")
    }
    private fun wire(value: Any): String = when (value) {
        is JSONObject -> value.keys().asSequence().joinToString(",", "{", "}") { JSONObject.quote(it) + ":" + wire(value.get(it)) }
        is JSONArray -> (0 until value.length()).joinToString(",", "[", "]") { wire(value.get(it)) }
        is String -> JSONObject.quote(value)
        else -> value.toString()
    }
    private fun protocol(value: FitResources): JSONArray {
        val good = raw(value).put("version",1)
        assertEquals(value,BridgeCodec.decodeResources(wire(good)))
        val labels = listOf("version","extra","missing_pair","unit","scalar_kind","boolean_value","overload","missing_display","revision")
        for (label in labels) {
            val bad = JSONObject(wire(good)); val cpu = bad.getJSONObject("resources").getJSONObject("cpu")
            when (label) {
                "version" -> bad.put("version",2)
                "extra" -> bad.put("extra",true)
                "missing_pair" -> bad.getJSONObject("resources").remove("fighter_bay")
                "unit" -> cpu.put("unit","MW")
                "scalar_kind" -> cpu.put("total_type","integer")
                "boolean_value" -> cpu.put("used",false)
                "overload" -> cpu.put("overloaded",!cpu.getBoolean("overloaded"))
                "missing_display" -> cpu.put("used_display",JSONObject.NULL)
                "revision" -> bad.put("revision",0)
            }
            try { BridgeCodec.decodeResources(wire(bad)); fail("Accepted $label") } catch (_: BridgeProtocolException) { }
        }
        val unavailable = JSONObject(wire(good))
        unavailable.getJSONObject("resources").getJSONObject("cpu").apply {
            put("used",JSONObject.NULL); put("used_type","unavailable"); put("used_display",JSONObject.NULL)
            put("used_detail",JSONObject.NULL); put("overloaded",JSONObject.NULL)
        }
        assertEquals(StatValue.Unavailable,BridgeCodec.decodeResources(wire(unavailable)).resources.getValue("cpu").used)
        return JSONArray(labels)
    }
    private fun assertReference(expected: JSONObject, actual: FitResources) {
        assertEquals(RESOURCE_LABELS.keys, actual.resources.keys)
        for ((name, row) in actual.resources) {
            val left = expected.getJSONObject(name)
            compare(left.get("used"), row.used.raw!!, name)
            compare(left.get("total"), row.total.raw!!, name)
            assertEquals(left.getString("unit"), row.unit)
            assertEquals(left.getBoolean("overloaded"), row.overloaded)
            assertEquals(left.getString("desktop_used"), row.usedDisplay)
            assertEquals(left.getString("desktop_total"), row.totalDisplay)
            assertEquals(left.getString("desktop_used_detail"), row.usedDetail)
            assertEquals(left.getString("desktop_total_detail"), row.totalDetail)
        }
    }
    private fun ready(id: String) {
        compose.waitUntil(60_000) { !model.loading && model.error == null && model.details?.let {
            it.fitId == id && it.revision == fit(id).revision } == true }; sync()
    }
    private fun screenshot(name: String) {
        sync(); instrumentation.uiAutomation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-c011-$name.png")).use { it.readBytes() }
    }
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS); sync(); click("resources-open"); ready(id)
    }
    private fun screen(id: String, expected: JSONObject) {
        ready(id); assertReference(expected, model.details!!)
        for ((name, row) in model.details!!.resources) {
            compose.onNodeWithTag("resources-value-$name").performScrollTo()
                .assertTextEquals("${row.usedDisplay} / ${row.totalDisplay} ${row.unit}")
            if (row.overloaded == true) compose.onNodeWithTag("resources-overload-$name").assertTextEquals("Over capacity")
        }
    }
    @Test fun savedResourcesRefreshAndRestoreWithoutMutatingInputs() {
        val phase = InstrumentationRegistry.getArguments().getString("c011_phase") ?: error("Missing phase")
        assertTrue(phase in listOf("prepare", "restored"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val start = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        assertTrue(start.getJSONObject("persistence").getBoolean("enabled"))
        assertTrue(start.getJSONObject("persistence").getBoolean("opened_existing"))
        assertEquals(if (phase == "prepare") 147 else 158, EngineRuntime.library.value.size)
        val bytes = instrumentation.context.assets.open("resources-expected.json").use { it.readBytes() }
        val fixture = JSONObject(bytes.toString(Charsets.UTF_8))
        val cases = fixture.getJSONArray("cases")
        val file = File(context.noBackupFilesDir, "c011-test-expected.json")
        val observations = JSONArray(); val ids = JSONArray(); var guards = JSONArray()
        val inherited = ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit)))
        if (phase == "prepare") {
            val equipment = EngineRuntime.equipmentCatalog(context).get(120, TimeUnit.SECONDS)
            fun item(name: String) = equipment.items.single { it.name == name }.id
            for (index in 0 until cases.length()) {
                val case = cases.getJSONObject(index)
                if (case.getString("execution") != "durable") continue
                val spec = case.getJSONObject("spec")
                val drones = spec.getJSONArray("drones")
                val id = send(BridgeOperation.CreateFit(FitSpec("C01.1 ${spec.getString("name")}", spec.getString("ship"),
                    5, false, DamagePattern(25.0,25.0,25.0,25.0), Security(SystemSecurity.HISEC,0.0), emptyList(),
                    (0 until drones.length()).map { drones.getJSONObject(it).let { row ->
                        DroneSpec(row.getString("name"), row.getInt("amount"), row.getInt("active")) } }))).fits.single().id
                if (spec.getBoolean("ignore_restrictions")) send(BridgeOperation.SetFitRestrictions(id,true),id)
                val modules = spec.getJSONArray("modules")
                for (position in 0 until modules.length()) {
                    val module = modules.getJSONObject(position)
                    send(BridgeOperation.AddModule(id,item(module.getString("name"))),id)
                    val state = ModuleState.valueOf(module.getString("state"))
                    if (fit(id).modules[position].state != state)
                        send(BridgeOperation.SetModuleStates(id,listOf(position),state),id)
                    if (!module.isNull("charge")) send(BridgeOperation.SetModuleCharge(id,position,item(module.getString("charge"))),id)
                }
                val cargo = spec.getJSONArray("cargo")
                for (position in 0 until cargo.length()) cargo.getJSONObject(position).let {
                    send(BridgeOperation.AddCargo(id,item(it.getString("name")),it.getLong("amount")),id)
                }
                open(id); screen(id,case.getJSONObject("resources"))
                val before = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
                val recent = EngineRuntime.recent.value.toList(); val history = EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS)
                repeat(3) { System.gc(); assertReference(case.getJSONObject("resources"),query(id)) }
                compare(before, JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120,TimeUnit.SECONDS)), strict=false)
                assertEquals(recent,EngineRuntime.recent.value)
                assertEquals(history,EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS))
                if (index == 0) {
                    val original = query(id)
                    send(BridgeOperation.SetSkillLevel(id,"CPU Management",0),id); ready(id)
                    val changed = query(id); assertTrue(changed.resources.getValue("cpu").total.numberOrNull()!! < original.resources.getValue("cpu").total.numberOrNull()!!)
                    click("history-undo"); ready(id); assertEquals(original.resources,query(id).resources)
                    click("history-redo"); ready(id); assertEquals(changed.resources,query(id).resources)
                    click("history-undo"); ready(id); assertEquals(original.resources,query(id).resources)
                    val beforeCopy = EngineRuntime.library.value.map { it.id }.toSet()
                    val copy = send(BridgeOperation.DuplicateFit(id,"C01.1 copy"),id).fits.single { it.id !in beforeCopy }.id
                    assertEquals("C01.1 copy",fit(copy).name)
                    assertEquals(original.resources,query(copy).resources)
                    assertEquals(0,EngineRuntime.editHistory(context,copy).get(120,TimeUnit.SECONDS).undoCount)
                    EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS); ready(id)
                    guards = protocol(query(id))
                    click("resources-details-cpu")
                    compose.onNodeWithTag("resources-used-detail-cpu").performScrollTo().assertTextEquals("Used: 0.0 tf")
                    screenshot("prepare-empty-detail")
                    compose.activityRule.scenario.recreate(); ready(id); assertEquals(original.resources,query(id).resources)
                }
                if (index == 5 || index == 8 || index == 9) {
                    compose.onNodeWithTag("resources-value-${if (index == 5) "cpu" else if (index == 8) "drone_bandwidth" else "cargo_bay"}").performScrollTo()
                    screenshot("prepare-$index")
                }
                observations.put(obj("case" to index,"actual" to raw(query(id)))); ids.put(id)
                click("resources-back")
            }
            assertEquals(10,ids.length()); assertEquals(158,EngineRuntime.library.value.size)
            val priorIds = inherited.getJSONArray("data").let { rows -> (0 until rows.length()).map { rows.getJSONObject(it).getString("id") } }
            compare(inherited,ModuleTestJson.typed(JSONArray(priorIds.map { ModuleTestJson.fit(fit(it)) })),strict=false)
            val final = JSONArray((0 until ids.length()).map { raw(query(ids.getString(it))) })
            file.writeText(obj("pid" to Process.myPid(),"ids" to ids,"resources" to final,"inherited" to inherited).toString(),Charsets.UTF_8)
        } else {
            val saved = JSONObject(file.readText(Charsets.UTF_8)); assertNotEquals(saved.getInt("pid"),Process.myPid())
            val prior = saved.getJSONObject("inherited")
            val priorIds = prior.getJSONArray("data").let { rows -> (0 until rows.length()).map { rows.getJSONObject(it).getString("id") } }
            compare(prior,ModuleTestJson.typed(JSONArray(priorIds.map { ModuleTestJson.fit(fit(it)) })),strict=false)
            val oldIds = saved.getJSONArray("ids"); val old = saved.getJSONArray("resources")
            for (index in 0 until oldIds.length()) {
                val id = oldIds.getString(index); ids.put(id)
                open(id); val value = query(id)
                compare(old.getJSONObject(index).getJSONObject("resources"),raw(value).getJSONObject("resources"),strict=false)
                assertEquals(0,EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS).undoCount)
                observations.put(obj("actual" to raw(value))); click("resources-back")
            }
            open(oldIds.getString(0)); compose.onNodeWithTag("resources-value-cpu").performScrollTo(); screenshot("restored")
        }
        val descriptors = instrumentation.uiAutomation.executeShellCommandRw("dd of=/sdcard/Download/pyfa-c011-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(obj("task" to "C01.1","phase" to phase,
                "pid" to Process.myPid(),"runtime_start" to start,"ids" to ids,"observations" to observations,"protocol_rejections" to guards,
                "saved" to JSONObject(file.readText(Charsets.UTF_8)),"fixture_sha256" to MessageDigest.getInstance("SHA-256")
                    .digest(bytes).joinToString("") { "%02x".format(it) }).toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
}
