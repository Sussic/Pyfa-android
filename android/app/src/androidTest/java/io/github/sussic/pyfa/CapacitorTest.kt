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
class CapacitorTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[CapacitorModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().performClick(); sync() }
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList()): BridgeResponse {
        val result = EngineRuntime.request(context,operation,ids.associateWith { fit(it).revision }).get(120,TimeUnit.SECONDS)
        assertTrue(result.error?.message,result.isSuccess);return result
    }
    private fun query(id: String) = EngineRuntime.capacitorDetails(context,id).get(120,TimeUnit.SECONDS)
    private fun kind(value: StatValue) = when(value) {
        is StatValue.Integer -> "integer"; is StatValue.Decimal -> "decimal"; StatValue.Unavailable -> "unavailable"; else -> error("Non-numeric capacitor")
    }
    private fun raw(value: FitCapacitor) = obj("fit_id" to value.fitId,"revision" to value.revision,
        "capacitor" to JSONObject().apply { value.capacitor.forEach { (name,row) -> put(name,obj("value" to row.value.raw,
            "value_type" to kind(row.value),"unit" to row.unit,"display" to row.display,"detail" to row.detail)) } },
        "stability" to obj("kind" to value.stability.kind,"unit" to value.stability.unit,
            "values" to JSONArray(value.stability.values.map { it.raw }),"value_types" to JSONArray(value.stability.values.map(::kind)),"display" to value.stability.display))
    private fun wire(value: Any): String = when(value) {
        is JSONObject -> value.keys().asSequence().joinToString(",","{","}") { JSONObject.quote(it)+":"+wire(value.get(it)) }
        is JSONArray -> (0 until value.length()).joinToString(",","[","]") { wire(value.get(it)) }
        is String -> JSONObject.quote(value)
        else -> value.toString()
    }
    private fun assertReference(expected: JSONObject, value: FitCapacitor) {
        val actual=raw(value)
        compare(expected.getJSONObject("capacitor"),actual.getJSONObject("capacitor"),strict=false)
        compare(expected.getJSONObject("stability"),actual.getJSONObject("stability"),strict=false)
        for (name in CAPACITOR_LABELS.keys) assertEquals(expected.getJSONObject("capacitor").getJSONObject(name).getString("value_type"),kind(value.capacitor.getValue(name).value))
        assertEquals(expected.getJSONObject("stability").getJSONArray("value_types").getString(0),kind(value.stability.values.single()))
    }
    private fun protocol(value: FitCapacitor): JSONArray {
        val good=raw(value).put("version",1);assertEquals(value,BridgeCodec.decodeCapacitor(wire(good)))
        val names=listOf("version","extra","missing","unit","boolean","kind","display","revision","stability_unit","stability_kind","bounds","reversed_range","fractional_integer")
        for (name in names) {
            val bad=JSONObject(wire(good));val capacity=bad.getJSONObject("capacitor").getJSONObject("capacity");val state=bad.getJSONObject("stability")
            when(name) {
                "version" -> bad.put("version",2)
                "extra" -> bad.put("extra",true)
                "missing" -> bad.getJSONObject("capacitor").remove("use")
                "unit" -> capacity.put("unit","MW")
                "boolean" -> capacity.put("value",false)
                "kind" -> capacity.put("value_type","unknown")
                "display" -> capacity.put("display",JSONObject.NULL)
                "revision" -> bad.put("revision",0)
                "stability_unit" -> state.put("unit","GJ")
                "stability_kind" -> state.put("kind","seconds")
                "bounds" -> state.put("values",JSONArray())
                "reversed_range" -> state.put("kind","stable_range").put("unit","%").put("values",JSONArray(listOf(75.0,25.0))).put("value_types",JSONArray(listOf("decimal","decimal")))
                "fractional_integer" -> capacity.put("value",1.25).put("value_type","integer")
            }
            try { BridgeCodec.decodeCapacitor(wire(bad));fail("Accepted $name") } catch (_:BridgeProtocolException) { }
        }
        val range=JSONObject(wire(good));range.getJSONObject("stability").put("kind","stable_range").put("unit","%")
            .put("values",JSONArray(listOf(25.0,75.0))).put("value_types",JSONArray(listOf("decimal","decimal"))).put("display","25.0%-75.0%")
        assertEquals("stable_range",BridgeCodec.decodeCapacitor(wire(range)).stability.kind)
        val unavailable=JSONObject(wire(good));unavailable.getJSONObject("stability").put("kind","unavailable")
            .put("values",JSONArray(listOf(JSONObject.NULL))).put("value_types",JSONArray(listOf("unavailable"))).put("display",JSONObject.NULL)
        assertEquals(StatValue.Unavailable,BridgeCodec.decodeCapacitor(wire(unavailable)).stability.values.single())
        return JSONArray(names)
    }
    private fun ready(id: String) {
        compose.waitUntil(60_000) { !model.loading && model.error==null && model.details?.let { it.fitId==id && it.revision==fit(id).revision }==true };sync()
    }
    private fun open(id: String) { EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS);sync();click("capacitor-open");ready(id) }
    private fun screen(id: String,expected: JSONObject) {
        ready(id);assertReference(expected,model.details!!)
        val value=model.details!!
        compose.onNodeWithTag("capacitor-stability").performScrollTo().assertTextEquals(
            "${if(value.stability.kind=="depletion") "Lasts" else "Stable:"} ${value.stability.display}")
        for ((name,row) in value.capacitor) {
            val absent=if(name in listOf("effective_capacity","effective_excess")) "Not applicable" else "Unavailable"
            compose.onNodeWithTag("capacitor-value-$name").performScrollTo().assertTextEquals(row.display?.let { "$it ${row.unit}" } ?: absent)
        }
    }
    private fun screenshot(name: String) {
        sync();instrumentation.uiAutomation.waitForIdle(500,10_000)
        ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand("screencap -p /sdcard/Download/pyfa-c012-$name.png")).use { it.readBytes() }
    }
    private fun create(spec: JSONObject): String {
        val modules=spec.getJSONArray("modules")
        val id = send(BridgeOperation.CreateFit(FitSpec("C01.2 ${spec.getString("name")}",spec.getString("ship"),5,false,
            DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),
            (0 until modules.length()).map { modules.getJSONObject(it).let { row -> ModuleSpec(row.getString("name"),ModuleState.valueOf(row.getString("state")),if(row.isNull("charge")) null else row.getString("charge")) } },emptyList()))).fits.single().id
        assertEquals(modules.length(),fit(id).modules.size)
        for (index in 0 until modules.length()) {
            val expected=modules.getJSONObject(index);val actual=fit(id).modules[index]
            assertEquals(index,actual.index);assertEquals(expected.getString("name"),actual.name)
            assertEquals(expected.getString("state"),actual.state!!.name)
            assertEquals(if(expected.isNull("charge")) null else expected.getString("charge"),actual.charge)
        }
        return id
    }
    @Test fun capacitorDetailsRefreshAndRestoreOffline() {
        val phase=InstrumentationRegistry.getArguments().getString("c012_phase") ?: error("Missing phase")
        assertTrue(phase in listOf("prepare","restored"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val start=JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120,TimeUnit.SECONDS))
        assertTrue(start.getJSONObject("persistence").getBoolean("enabled"));assertTrue(start.getJSONObject("persistence").getBoolean("opened_existing"))
        assertEquals(if(phase=="prepare") 158 else 174,EngineRuntime.library.value.size)
        val bytes=instrumentation.context.assets.open("capacitor-expected.json").use { it.readBytes() }
        val cases=JSONObject(bytes.toString(Charsets.UTF_8)).getJSONArray("cases")
        assertEquals(12,cases.length())
        val file=File(context.noBackupFilesDir,"c012-test-expected.json")
        val observations=JSONArray();val ids=JSONArray();var guards=JSONArray()
        if(phase=="prepare") {
            val inherited=ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit)))
            for(index in 0 until cases.length()) {
                val row=cases.getJSONObject(index);val id=create(row.getJSONObject("spec"));ids.put(id)
                if(row.has("source")) {
                    val source=create(row.getJSONObject("source"));val edge=row.getJSONObject("projection")
                    send(BridgeOperation.AddProjection(source,id,edge.getDouble("range_m"),edge.getBoolean("active"),edge.getInt("amount")),listOf(source,id))
                }
                open(id);screen(id,row.getJSONObject("expected"))
                val before=JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120,TimeUnit.SECONDS))
                val recent=EngineRuntime.recent.value.toList();val history=EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS)
                repeat(3) { System.gc();assertReference(row.getJSONObject("expected"),query(id)) }
                compare(before,JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120,TimeUnit.SECONDS)),strict=false)
                assertEquals(recent,EngineRuntime.recent.value);assertEquals(history,EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS))
                if(index==5) {
                    val original=query(id);send(BridgeOperation.SetSkillLevel(id,"Capacitor Management",0),listOf(id));ready(id)
                    val changed=query(id);assertTrue(changed.capacitor.getValue("capacity").value.numberOrNull()!!<original.capacitor.getValue("capacity").value.numberOrNull()!!)
                    click("history-undo");ready(id);assertEquals(original.capacitor,query(id).capacitor);assertEquals(original.stability,query(id).stability)
                    click("history-redo");ready(id);assertEquals(changed.capacitor,query(id).capacitor)
                    click("history-undo");ready(id);assertEquals(original.capacitor,query(id).capacitor)
                    val old=EngineRuntime.library.value.map { it.id }.toSet()
                    val copy=send(BridgeOperation.DuplicateFit(id,"C01.2 copy"),listOf(id)).fits.single { it.id !in old }.id
                    assertEquals(original.capacitor,query(copy).capacitor);assertEquals(original.stability,query(copy).stability)
                    assertEquals(0,EngineRuntime.editHistory(context,copy).get(120,TimeUnit.SECONDS).undoCount)
                    EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS);ready(id)
                    guards=protocol(query(id));click("capacitor-details-effective_capacity")
                    compose.onNodeWithTag("capacitor-detail-effective_capacity").performScrollTo().assertTextEquals("${original.capacitor.getValue("effective_capacity").detail} GJ")
                    screenshot("prepare-battery-detail");compose.activityRule.scenario.recreate();ready(id);assertEquals(original.capacitor,query(id).capacitor)
                }
                if(index in listOf(0,4,10)) { compose.onNodeWithTag("capacitor-stability").performScrollTo();screenshot("prepare-$index") }
                observations.put(obj("case" to index,"actual" to raw(query(id))));click("capacitor-back")
            }
            val previous=inherited.getJSONArray("data");val priorIds=(0 until previous.length()).map { previous.getJSONObject(it).getString("id") }
            compare(inherited,ModuleTestJson.typed(JSONArray(priorIds.map { ModuleTestJson.fit(fit(it)) })),strict=false)
            assertEquals(174,EngineRuntime.library.value.size)
            file.writeText(obj("pid" to Process.myPid(),"ids" to ids,"inherited" to inherited,
                "all_fits" to ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))),
                "capacitors" to JSONArray((0 until ids.length()).map { raw(query(ids.getString(it))) })).toString(),Charsets.UTF_8)
        } else {
            val saved=JSONObject(file.readText(Charsets.UTF_8));assertNotEquals(saved.getInt("pid"),Process.myPid())
            compare(saved.getJSONObject("all_fits"),ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))),strict=false)
            val previous=saved.getJSONArray("ids");val prior=saved.getJSONArray("capacitors")
            for(index in 0 until previous.length()) {
                val id=previous.getString(index);ids.put(id);open(id);screen(id,cases.getJSONObject(index).getJSONObject("expected"))
                compare(prior.getJSONObject(index),raw(query(id)),strict=false)
                assertEquals(0,EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS).undoCount)
                observations.put(obj("actual" to raw(query(id))));click("capacitor-back")
            }
            open(previous.getString(5));compose.onNodeWithTag("capacitor-stability").performScrollTo();screenshot("restored")
        }
        val descriptors=instrumentation.uiAutomation.executeShellCommandRw("dd of=/sdcard/Download/pyfa-c012-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(obj("task" to "C01.2","phase" to phase,
                "pid" to Process.myPid(),"runtime_start" to start,"ids" to ids,"observations" to observations,"protocol_rejections" to guards,
                "saved" to JSONObject(file.readText(Charsets.UTF_8)),"fixture_sha256" to MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }).toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
}
