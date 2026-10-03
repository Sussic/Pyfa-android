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
class OutputTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[OutputModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().performClick(); sync() }
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList()): BridgeResponse {
        val result = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess); return result
    }
    private fun query(id: String) = EngineRuntime.outputDetails(context, id).get(120, TimeUnit.SECONDS)
    private fun graph() = JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
    private fun kind(value: StatValue) = when(value) {
        is StatValue.Integer -> "integer"; is StatValue.Decimal -> "decimal"; StatValue.Unavailable -> "unavailable"; else -> error("Non-numeric output")
    }
    private fun scalar(value: OutputScalar) = obj("value" to value.value.raw, "value_type" to kind(value.value), "unit" to value.unit, "display" to value.display, "detail" to value.detail)
    private fun spool(value: OutputSpool) = obj("current" to scalar(value.current), "pre" to scalar(value.pre), "full" to scalar(value.full), "indicated" to value.indicated, "tooltip" to value.tooltip)
    private fun profile(value: TargetProfile?): Any = value?.let { obj("emAmount" to it.emAmount, "thermalAmount" to it.thermalAmount, "kineticAmount" to it.kineticAmount,
        "explosiveAmount" to it.explosiveAmount, "maxVelocity" to it.maxVelocity, "signatureRadius" to it.signatureRadius, "radius" to it.radius, "hp" to it.hp) } ?: JSONObject.NULL
    private fun raw(value: FitOutput) = obj("fit_id" to value.fitId, "revision" to value.revision, "target_profile" to profile(value.targetProfile),
        "output" to obj("effective" to value.effective, "default_spool_percentage" to value.defaultSpoolPercentage,
            "firepower" to JSONObject().apply { value.firepower.forEach { (mode, rows) -> put(mode, JSONObject().apply {
                rows.forEach { (name, row) -> put(name, spool(row.spool).put("damage", JSONObject().apply { row.damage.forEach { (kind, damage) -> put(kind, obj("amount" to scalar(damage.amount), "share" to scalar(damage.share))) } })) }
            }) } }, "mining" to JSONObject().apply { value.mining.forEach { (name, row) -> put(name, obj("yield_second" to scalar(row.yieldSecond), "drain_second" to scalar(row.drainSecond),
                "yield_hour" to scalar(row.yieldHour), "drain_hour" to scalar(row.drainHour), "efficiency" to scalar(row.efficiency))) } },
            "bombing" to obj("signature" to scalar(value.bombing.signature), "environment_multiplier" to scalar(value.bombing.multiplier),
                "levels" to JSONArray(value.bombing.levels.mapIndexed { level, rows -> obj("covert_ops_level" to level, "counts" to JSONObject().apply { rows.forEach { (kind, row) -> put(kind, scalar(row)) } }) })),
            "outgoing" to JSONObject().apply { value.outgoing.forEach { (name, row) -> put(name, spool(row)) } }))
    private fun reference(expected: JSONObject, value: FitOutput) { compare(expected.getJSONObject("output"), raw(value).getJSONObject("output"), strict=false) }
    private fun text(tag: String, value: OutputScalar, prefix: String = "") { compose.onNodeWithTag(tag).performScrollTo().assertTextEquals(prefix+(value.display?.let { "$it ${value.unit}" } ?: "Unavailable")) }
    private fun precision(value: OutputScalar) = value.value.numberOrNull()?.toString() ?: "Unavailable"
    private fun detail(name: String, row: OutputSpool, damage: Map<String, OutputDamage>? = null) {
        click("output-details-$name")
        compose.onNodeWithTag("output-current-$name").performScrollTo().assertTextEquals("Current: ${precision(row.current)} ${row.current.unit}")
        compose.onNodeWithTag("output-pre-$name").performScrollTo().assertTextEquals("Initial: ${row.pre.display} ${row.pre.unit} · Full precision: ${precision(row.pre)}")
        compose.onNodeWithTag("output-full-$name").performScrollTo().assertTextEquals("Full spool: ${row.full.display} ${row.full.unit} · Full precision: ${precision(row.full)}")
        compose.onNodeWithTag("output-spool-$name").performScrollTo().assertTextEquals(if(row.indicated) row.tooltip else "No spool increase")
        damage?.forEach { (kind, value) -> compose.onNodeWithTag("output-share-$name-$kind").performScrollTo().assertTextEquals("${OUTPUT_DAMAGE.getValue(kind)}: ${value.amount.display} ${value.amount.unit} · ${value.share.display} ${value.share.unit}") }
    }
    private fun screen(id: String, expected: JSONObject, index: Int) {
        open(id); reference(expected, model.details!!); val original=query(id)
        click("output-page-firepower")
        for(mode in listOf("effective", "raw")) {
            original.firepower.getValue(mode).forEach { (name,row) -> text("output-value-$name",row.spool.current) }
            click("output-toggle")
        }
        val page=when(index) { 18,21 -> "mining"; 28 -> "bombing"; 31,32 -> "outgoing"; else -> "firepower" }
        click("output-page-$page")
        when(page) {
            "mining" -> original.mining.forEach { (name,row) ->
                for((field,label,value) in listOf(Triple("yield-second","Yield",row.yieldSecond),Triple("drain-second","Drain",row.drainSecond),
                    Triple("yield-hour","Hourly yield",row.yieldHour),Triple("drain-hour","Hourly drain",row.drainHour),Triple("efficiency","Efficiency",row.efficiency))) text("output-mining-$name-$field",value,"$label: ")
            }
            "bombing" -> original.bombing.levels.forEachIndexed { level,rows -> rows.forEach { (kind,row) -> text("output-bomb-$level-$kind",row,"${OUTPUT_DAMAGE.getValue(kind)}: ") } }
            "outgoing" -> {
                original.outgoing.forEach { (name,row) -> text("output-value-outgoing-$name",row.current) }
                if(index==32)detail("outgoing-armor",original.outgoing.getValue("armor"))
            }
            else -> {
                val name=if(index==9) "drone" else "weapon";val row=original.firepower.getValue("effective").getValue(name)
                detail(name,row.spool,row.damage)
            }
        }
        screenshot("prepare-$index")
        if(page=="firepower")click("output-details-${if(index==9) "drone" else "weapon"}")
        if(index==32)click("output-details-outgoing-armor")
        if(index==28) { compose.onNodeWithTag("output-bomb-0-em").performScrollTo();screenshot("prepare-bombs-first") }
        click("output-page-firepower");assertEquals(original,query(id));click("output-back")
    }
    private fun protocol(value: FitOutput): JSONArray {
        val good=raw(value).put("version",1);assertEquals(value,BridgeCodec.decodeOutput(wire(good)))
        val names=listOf("version","extra","missing","unit","boolean","kind","display","revision","missing_mode","missing_damage","missing_spool","spool_flag","bomb_level","bomb_type","mining_unit","outgoing_unit","fractional_integer","profile_flag")
        for(name in names) {
            val bad=JSONObject(wire(good));val data=bad.getJSONObject("output");val row=data.getJSONObject("firepower").getJSONObject("raw").getJSONObject("weapon");val scalar=row.getJSONObject("current")
            when(name) {
                "version" -> bad.put("version",2);"extra" -> bad.put("extra",true);"missing" -> bad.remove("output")
                "unit" -> scalar.put("unit","MW");"boolean" -> scalar.put("value",false);"kind" -> scalar.put("value_type","text");"display" -> scalar.put("display",JSONObject.NULL)
                "revision" -> bad.put("revision",0);"missing_mode" -> data.getJSONObject("firepower").remove("effective");"missing_damage" -> row.getJSONObject("damage").remove("pure")
                "missing_spool" -> row.remove("full");"spool_flag" -> row.put("indicated",1)
                "bomb_level" -> data.getJSONObject("bombing").getJSONArray("levels").getJSONObject(0).put("covert_ops_level",5)
                "bomb_type" -> data.getJSONObject("bombing").getJSONArray("levels").getJSONObject(0).getJSONObject("counts").remove("em")
                "mining_unit" -> data.getJSONObject("mining").getJSONObject("module").getJSONObject("yield_hour").put("unit","m³/s")
                "outgoing_unit" -> data.getJSONObject("outgoing").getJSONObject("capacitor").getJSONObject("current").put("unit","HP/s")
                "fractional_integer" -> scalar.put("value",1.25).put("value_type","integer");"profile_flag" -> data.put("effective",true)
            }
            try { BridgeCodec.decodeOutput(wire(bad));fail("Accepted $name") } catch(_: BridgeProtocolException) { }
        }
        val absent=JSONObject(wire(good));absent.getJSONObject("output").getJSONObject("firepower").getJSONObject("raw").getJSONObject("weapon").getJSONObject("current")
            .put("value",JSONObject.NULL).put("value_type","unavailable").put("display",JSONObject.NULL).put("detail",JSONObject.NULL)
        assertEquals(StatValue.Unavailable,BridgeCodec.decodeOutput(wire(absent)).firepower.getValue("raw").getValue("weapon").spool.current.value)
        return JSONArray(names)
    }

    private fun profileRequestNumbers(cases: JSONArray) {
        for (index in listOf(14, 15, 16, 35, 36)) {
            val spec = JSONObject(wire(cases.getJSONObject(index).getJSONObject("spec")))
            spec.remove("ignore_restrictions"); spec.remove("cargo")
            val decoded = BridgeCodec.decodeFitSpec(wire(spec))
            val profile = decoded.targetProfile!!
            for (operation in listOf(BridgeOperation.CreateFit(decoded), BridgeOperation.SetTargetProfile("wire-fit", profile))) {
                val revisions = if (operation is BridgeOperation.CreateFit) emptyMap() else mapOf("wire-fit" to 1L)
                val request = BridgeRequest("wire-request", "wire-session", operation, revisions)
                val encoded = JSONObject(BridgeCodec.encodeRequest(request)).getJSONObject("arguments")
                val row = if (operation is BridgeOperation.CreateFit) encoded.getJSONObject("spec").getJSONObject("target_profile") else encoded.getJSONObject("profile")
                val expected = this.profile(profile) as JSONObject
                for (key in expected.keys()) {
                    assertEquals(expected.get(key), row.get(key))
                    if (expected.get(key) != JSONObject.NULL) assertTrue("$index $key lost decimal type", row.get(key) is Double)
                }
                if (operation is BridgeOperation.CreateFit) {
                    assertTrue(encoded.getJSONObject("spec").getInt("skill_level") == decoded.skillLevel)
                    assertTrue(encoded.getJSONObject("spec").getBoolean("factor_reload") == decoded.factorReload)
                }
            }
        }
        val nullProfile = BridgeRequest("wire-request", "wire-session", BridgeOperation.SetTargetProfile("wire-fit", null), mapOf("wire-fit" to 1L))
        assertEquals(JSONObject.NULL, JSONObject(BridgeCodec.encodeRequest(nullProfile)).getJSONObject("arguments").get("profile"))
    }

    @Test fun outputViewsProfileHistoryAndRestartOffline() {
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        val phase=InstrumentationRegistry.getArguments().getString("c02_phase") ?: error("Missing phase")
        assertTrue(phase in listOf("prepare","restored"));val start=JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120,TimeUnit.SECONDS))
        assertTrue(start.getJSONObject("persistence").getBoolean("enabled"));assertTrue(start.getJSONObject("persistence").getBoolean("opened_existing"))
        assertEquals(if(phase=="prepare")230 else 268,EngineRuntime.library.value.size)
        val bytes=instrumentation.context.assets.open("output-expected.json").use { it.readBytes() };val fixture=JSONObject(bytes.toString(Charsets.UTF_8));val cases=fixture.getJSONArray("cases");assertEquals(37,cases.length())
        profileRequestNumbers(cases)
        val file=File(context.noBackupFilesDir,"c02-expected.json");val observations=JSONArray();val ids=JSONArray();var guards=JSONArray();val edits=JSONArray()
        if(phase=="prepare") {
            val inherited=ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit)));val inheritedGraph=graph()
            for(index in 0 until cases.length()) {
                println("OUTPUT CASE $index ${cases.getJSONObject(index).getJSONObject("spec").getString("name")}")
                val case=cases.getJSONObject(index);val id=create(case.getJSONObject("spec"));ids.put(id);val before=raw(query(id));reference(case.getJSONObject("expected"),query(id))
                val durable=ModuleTestJson.typed(graph());val history=EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS);val recent=EngineRuntime.recent.value
                repeat(3) { System.gc();reference(case.getJSONObject("expected"),query(id)) }
                compare(durable,ModuleTestJson.typed(graph()),strict=false);assertEquals(history,EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS));assertEquals(recent,EngineRuntime.recent.value)
                observations.put(obj("case" to index,"actual" to before))
                if(index==0)guards=protocol(query(id))
                if(index in listOf(1,9,13,14,18,21,28,31,32,35))screen(id,case.getJSONObject("expected"),index)
            }
            val owner=ids.getString(35);open(owner);val original=query(owner);val baseRevision=fit(owner).revision
            click("output-profile-open");compose.onNodeWithTag("output-profile-hp").performScrollTo().performTextReplacement("1000000")
            click("output-profile-apply");compose.waitUntil(60_000) { !model.editing && fit(owner).revision>baseRevision };ready(owner)
            reference(cases.getJSONObject(36).getJSONObject("expected"),query(owner));val changed=raw(query(owner))
            reverse(owner,false);assertEquals(original.firepower,query(owner).firepower);reverse(owner,true);compare(changed.getJSONObject("output"),raw(query(owner)).getJSONObject("output"),strict=false)
            edits.put(obj("action" to "profile_hp","after" to changed,"redo" to raw(query(owner))));reverse(owner,false)
            val beforeClear=fit(owner).revision;click("output-profile-clear");compose.waitUntil(60_000) { !model.editing && fit(owner).revision>beforeClear };ready(owner)
            val cleared=raw(query(owner));assertNull(query(owner).targetProfile);assertFalse(query(owner).effective);assertEquals(original.firepower.getValue("raw"),query(owner).firepower.getValue("effective"));screenshot("prepare-profile-cleared")
            reverse(owner,false);assertEquals(original.firepower,query(owner).firepower)
            edits.put(obj("action" to "profile_clear","after" to cleared,"restored" to raw(query(owner))))
            val old=EngineRuntime.library.value.map { it.id }.toSet();val copy=send(BridgeOperation.DuplicateFit(owner,"C02 copy"),listOf(owner)).fits.single { it.id !in old }.id
            assertEquals(original.firepower,query(copy).firepower);assertEquals(original.targetProfile,query(copy).targetProfile)
            compose.activityRule.scenario.recreate();ready(owner);assertEquals(original.firepower,query(owner).firepower)
            val finalGraph=graph();val previous=inherited.getJSONArray("data");val priorIds=(0 until previous.length()).map { previous.getJSONObject(it).getString("id") }
            compare(inherited,ModuleTestJson.typed(JSONArray(priorIds.map { ModuleTestJson.fit(fit(it)) })),strict=false)
            for(id in priorIds)for(field in listOf("records","revisions","modified"))compare(ModuleTestJson.typed(inheritedGraph.getJSONObject(field).get(id)),ModuleTestJson.typed(finalGraph.getJSONObject(field).get(id)),strict=false)
            assertEquals(268,EngineRuntime.library.value.size)
            file.writeText(wire(obj("pid" to Process.myPid(),"ids" to ids,"inherited" to inherited,"inherited_graph" to ModuleTestJson.typed(inheritedGraph),"graph" to ModuleTestJson.typed(finalGraph),
                "all_fits" to ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))),"edits" to edits,"copy_id" to copy,"copy_output" to raw(query(copy)),"outputs" to JSONArray((0 until ids.length()).map { raw(query(ids.getString(it))) }))),Charsets.UTF_8)
        } else {
            val saved=JSONObject(file.readText(Charsets.UTF_8));assertNotEquals(saved.getInt("pid"),Process.myPid());compare(saved.getJSONObject("graph"),ModuleTestJson.typed(graph()),strict=false)
            compare(saved.getJSONObject("all_fits"),ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))),strict=false)
            val previous=saved.getJSONArray("ids");val prior=saved.getJSONArray("outputs")
            for(index in 0 until previous.length()) { val id=previous.getString(index);ids.put(id);compare(prior.getJSONObject(index),raw(query(id)),strict=false);reference(cases.getJSONObject(index).getJSONObject("expected"),query(id));observations.put(obj("case" to index,"actual" to raw(query(id)))) }
            assertTrue(EngineRuntime.library.value.all { EngineRuntime.editHistory(context,it.id).get(120,TimeUnit.SECONDS).let { h -> h.undoCount==0 && h.redoCount==0 } })
            compare(saved.getJSONObject("copy_output"),raw(query(saved.getString("copy_id"))),strict=false)
            val owner=previous.getString(35);open(owner);val row=query(owner).firepower.getValue("effective").getValue("weapon");detail("weapon",row.spool,row.damage);screenshot("restored")
        }
        val descriptors=instrumentation.uiAutomation.executeShellCommandRw("dd of=/sdcard/Download/pyfa-c02-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(wire(obj("task" to "C02","phase" to phase,"pid" to Process.myPid(),"runtime_start" to start,"ids" to ids,"observations" to observations,
                "protocol_rejections" to guards,"saved" to JSONObject(file.readText(Charsets.UTF_8)),"copy_observation" to raw(query(JSONObject(file.readText(Charsets.UTF_8)).getString("copy_id"))),
                "fixture_sha256" to MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) })).toByteArray(Charsets.UTF_8)) };completion.readBytes()
        }
    }

    private fun wire(value: Any): String = when (value) {
        is JSONObject -> value.keys().asSequence().joinToString(",", "{", "}") { JSONObject.quote(it) + ":" + wire(value.get(it)) }
        is JSONArray -> (0 until value.length()).joinToString(",", "[", "]") { wire(value.get(it)) }
        is String -> JSONObject.quote(value)
        else -> value.toString()
    }
    private fun ready(id: String) {
        compose.waitUntil(60_000) { !model.loading && model.error == null && model.details?.let { it.fitId == id && it.revision == fit(id).revision } == true }; sync()
    }
    private fun reverse(id: String, redo: Boolean) {
        ready(id); val revision = fit(id).revision
        val history = ViewModelProvider(compose.activity)[EditHistoryModel::class.java]
        compose.waitUntil(60_000) { !history.loading && !history.editing && history.options?.revision == revision }
        val tag = if (redo) "history-redo" else "history-undo"
        compose.onNodeWithTag(tag).performScrollTo().assertIsEnabled()
        click(tag)
        compose.waitUntil(60_000) { fit(id).revision > revision && !history.loading && !history.editing && history.options?.revision == fit(id).revision }
        assertNull(history.error); ready(id)
    }
    private fun open(id: String) { EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS); sync(); click("output-open"); ready(id) }
    private fun screenshot(name: String) {
        sync(); instrumentation.uiAutomation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand("screencap -p /sdcard/Download/pyfa-c02-$name.png")).use { it.readBytes() }
    }
    private fun create(value: JSONObject): String {
        val native = JSONObject(value.toString())
        assertFalse(native.getBoolean("ignore_restrictions")); assertEquals(0, native.getJSONArray("cargo").length())
        native.remove("ignore_restrictions"); native.remove("cargo")
        val spec = BridgeCodec.decodeFitSpec(native.toString())
        val id = send(BridgeOperation.CreateFit(spec.copy(name="C02 ${spec.name}"))).fits.single().id
        assertEquals(spec.modules.size, fit(id).modules.size)
        spec.modules.forEachIndexed { index, m ->
            assertEquals(index, fit(id).modules[index].index); assertEquals(m.name, fit(id).modules[index].name)
            assertEquals(m.state, fit(id).modules[index].state); assertEquals(m.charge, fit(id).modules[index].charge)
        }; return id
    }

}
