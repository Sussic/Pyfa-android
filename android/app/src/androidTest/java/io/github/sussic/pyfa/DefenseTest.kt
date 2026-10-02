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
class DefenseTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[DefenseModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().performClick(); sync() }
    private fun send(operation: BridgeOperation, id: String? = null): BridgeResponse {
        val result = EngineRuntime.request(context, operation, id?.let { mapOf(it to fit(it).revision) } ?: emptyMap()).get(120,TimeUnit.SECONDS)
        assertTrue(result.error?.message,result.isSuccess);return result
    }
    private fun query(id: String) = EngineRuntime.defenseDetails(context,id).get(120,TimeUnit.SECONDS)
    private fun graph() = JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120,TimeUnit.SECONDS))
    private fun kind(value: StatValue) = when(value) {
        is StatValue.Integer -> "integer"; is StatValue.Decimal -> "decimal"; StatValue.Unavailable -> "unavailable"; else -> error("Non-numeric defense")
    }
    private fun scalar(value: DefenseScalar) = obj("value" to value.value.raw,"value_type" to kind(value.value),
        "unit" to value.unit,"display" to value.display,"detail" to value.detail)
    private fun raw(value: FitDefenses) = obj("fit_id" to value.fitId,"revision" to value.revision,"defenses" to obj(
        "layers" to JSONObject().apply { value.layers.forEach { (name,row) -> put(name,obj("hp" to scalar(row.hp),"ehp" to scalar(row.ehp),
            "multiplier" to scalar(row.multiplier),"resistances" to JSONObject().apply { row.resistances.forEach { (key,resist) -> put(key,scalar(resist)) } })) } },
        "total" to obj("hp" to scalar(value.hp),"ehp" to scalar(value.ehp)),
        "pattern" to JSONObject().apply { value.pattern.forEach { (name,row) -> put(name,obj("amount" to row.amount,"percentage" to row.percentage,"display" to row.display)) } }))
    private fun wire(value: Any): String = when(value) {
        is JSONObject -> value.keys().asSequence().joinToString(",","{","}") { JSONObject.quote(it)+":"+wire(value.get(it)) }
        is JSONArray -> (0 until value.length()).joinToString(",","[","]") { wire(value.get(it)) }
        is String -> JSONObject.quote(value)
        else -> value.toString()
    }
    private fun reference(expected: JSONObject,value: FitDefenses) {
        compare(expected,raw(value).getJSONObject("defenses"),strict=false)
        for ((name,row) in value.layers) {
            val wanted=expected.getJSONObject("layers").getJSONObject(name)
            for ((field,v) in listOf("hp" to row.hp,"ehp" to row.ehp,"multiplier" to row.multiplier))
                assertEquals(wanted.getJSONObject(field).getString("value_type"),kind(v.value))
            row.resistances.forEach { (field,v) -> assertEquals(wanted.getJSONObject("resistances").getJSONObject(field).getString("value_type"),kind(v.value)) }
        }
        assertEquals(expected.getJSONObject("total").getJSONObject("hp").getString("value_type"),kind(value.hp.value))
        assertEquals(expected.getJSONObject("total").getJSONObject("ehp").getString("value_type"),kind(value.ehp.value))
    }
    private fun ready(id: String) {
        compose.waitUntil(60_000) { !model.loading && model.error==null && model.details?.let { it.fitId==id && it.revision==fit(id).revision }==true };sync()
    }
    private fun open(id: String) { EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS);sync();click("defense-open");ready(id) }
    private fun text(tag: String,row: DefenseScalar) { compose.onNodeWithTag(tag).performScrollTo().assertTextEquals(row.display?.let { "$it ${row.unit}" } ?: "Unavailable") }
    private fun screen(id: String,expected: JSONObject) {
        ready(id);reference(expected,model.details!!)
        val value=model.details!!
        // The initial mode is effective; test both modes without changing EOS.
        compose.onNodeWithTag("defense-toggle").performScrollTo().assertTextEquals("Show raw HP")
        text("defense-value-total",value.ehp)
        value.pattern.forEach { (name,row) ->
            compose.onNodeWithTag("defense-input-$name").performScrollTo().assertTextContains(row.amount.toString())
            compose.onNodeWithTag("defense-percent-$name",useUnmergedTree=true).performScrollTo().assertTextEquals("Saved: ${row.display}%")
        }
        value.layers.forEach { (name,row) ->
            text("defense-value-$name-hp",row.ehp);text("defense-value-$name-multiplier",row.multiplier)
            row.resistances.forEach { (kind,resistance) -> text("defense-value-$name-$kind",resistance) }
        }
        click("defense-toggle");text("defense-value-total",value.hp)
        value.layers.forEach { (name,row) -> text("defense-value-$name-hp",row.hp) }
        click("defense-toggle");assertEquals(value,query(id))
    }
    private fun screenshot(name: String) {
        sync();instrumentation.uiAutomation.waitForIdle(500,10_000)
        ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand("screencap -p /sdcard/Download/pyfa-c013-$name.png")).use { it.readBytes() }
    }
    private fun pattern(value: JSONObject) = DamagePattern(value.getDouble("emAmount"),value.getDouble("thermalAmount"),value.getDouble("kineticAmount"),value.getDouble("explosiveAmount"))
    private fun create(value: JSONObject): String {
        val native=JSONObject(value.toString())
        assertFalse(native.getBoolean("ignore_restrictions"));assertEquals(0,native.getJSONArray("cargo").length())
        native.remove("ignore_restrictions");native.remove("cargo")
        val spec=BridgeCodec.decodeFitSpec(native.toString())
        val id=send(BridgeOperation.CreateFit(spec.copy(name="C01.3.1 ${spec.name}"))).fits.single().id
        assertEquals(spec.modules.size,fit(id).modules.size)
        spec.modules.forEachIndexed { index,module ->
            assertEquals(index,fit(id).modules[index].index);assertEquals(module.name,fit(id).modules[index].name)
            assertEquals(module.state,fit(id).modules[index].state);assertEquals(module.charge,fit(id).modules[index].charge)
        };return id
    }
    private fun protocol(value: FitDefenses): JSONArray {
        val good=raw(value).put("version",1);assertEquals(value,BridgeCodec.decodeDefenses(wire(good)))
        val names=listOf("version","extra","missing","unit","boolean","kind","display","revision","missing_layer","missing_resist",
            "multiplier_unit","negative_hp","resistance_over100","pattern_missing","pattern_negative","pattern_zero","pattern_percent","fractional_integer")
        for(name in names) {
            val bad=JSONObject(wire(good));val data=bad.getJSONObject("defenses")
            val layers=data.getJSONObject("layers");val hp=layers.getJSONObject("shield").getJSONObject("hp")
            val incoming=data.getJSONObject("pattern")
            when(name) {
                "version" -> bad.put("version",2);"extra" -> bad.put("extra",true);"missing" -> bad.remove("defenses")
                "unit" -> hp.put("unit","GJ");"boolean" -> hp.put("value",false);"kind" -> hp.put("value_type","text")
                "display" -> hp.put("display",JSONObject.NULL);"revision" -> bad.put("revision",0)
                "missing_layer" -> layers.remove("armor");"missing_resist" -> layers.getJSONObject("hull").getJSONObject("resistances").remove("em")
                "multiplier_unit" -> layers.getJSONObject("armor").getJSONObject("multiplier").put("unit","%")
                "negative_hp" -> hp.put("value",-1.0).put("value_type","decimal")
                "resistance_over100" -> layers.getJSONObject("shield").getJSONObject("resistances").getJSONObject("em").put("value",101.0).put("value_type","decimal")
                "pattern_missing" -> incoming.remove("em");"pattern_negative" -> incoming.getJSONObject("em").put("amount",-1.0)
                "pattern_zero" -> DAMAGE_TYPES.keys.forEach { incoming.getJSONObject(it).put("amount",0.0) }
                "pattern_percent" -> incoming.getJSONObject("em").put("percentage",101.0)
                "fractional_integer" -> hp.put("value",1.25).put("value_type","integer")
            }
            try { BridgeCodec.decodeDefenses(wire(bad));fail("Accepted $name") } catch (_: BridgeProtocolException) { }
        }
        val absent=JSONObject(wire(good));absent.getJSONObject("defenses").getJSONObject("total").getJSONObject("hp")
            .put("value",JSONObject.NULL).put("value_type","unavailable").put("display",JSONObject.NULL).put("detail",JSONObject.NULL)
        assertEquals(StatValue.Unavailable,BridgeCodec.decodeDefenses(wire(absent)).hp.value)
        for(values in listOf(DamagePattern(0.0,0.0,0.0,0.0),DamagePattern(-1.0,1.0,1.0,1.0),DamagePattern(Double.NaN,1.0,1.0,1.0),DamagePattern(Double.MAX_VALUE,Double.MAX_VALUE,0.0,0.0))) {
            try { BridgeCodec.encodeRequest(BridgeRequest("invalid","session",BridgeOperation.SetDamagePattern(value.fitId,values),mapOf(value.fitId to value.revision)));fail("Accepted invalid request") }
            catch (_: BridgeProtocolException) { }
        }
        return JSONArray(names)
    }

    @Test fun defensesIncomingDamageAndRestoreOffline() {
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        val phase=InstrumentationRegistry.getArguments().getString("c013_phase") ?: error("Missing phase")
        assertTrue(phase in listOf("prepare","restored"))
        val start=JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120,TimeUnit.SECONDS))
        assertTrue(start.getJSONObject("persistence").getBoolean("enabled"));assertTrue(start.getJSONObject("persistence").getBoolean("opened_existing"))
        assertEquals(if(phase=="prepare") 174 else 189,EngineRuntime.library.value.size)
        val bytes=instrumentation.context.assets.open("defenses-expected.json").use { it.readBytes() };val fixture=JSONObject(bytes.toString(Charsets.UTF_8))
        val cases=fixture.getJSONArray("cases");assertEquals(14,cases.length())
        val file=File(context.noBackupFilesDir,"c013-expected.json")
        val observations=JSONArray();val ids=JSONArray();var guards=JSONArray();val edits=JSONArray()
        if(phase=="prepare") {
            val inherited=ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit)));val inheritedGraph=graph()
            for(index in 0 until cases.length()) {
                val case=cases.getJSONObject(index);val id=create(case.getJSONObject("spec"));ids.put(id);open(id)
                val expected=case.getJSONObject("expected").getJSONObject("defenses");screen(id,expected)
                val before=raw(query(id));val durable=graph();val history=EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS);val recent=EngineRuntime.recent.value
                repeat(3) { System.gc();reference(expected,query(id)) }
                compare(durable,graph(),strict=false);assertEquals(history,EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS));assertEquals(recent,EngineRuntime.recent.value)
                observations.put(obj("case" to index,"actual" to before))
                if(index==0) {
                    guards=protocol(query(id))
                    for(layer in DEFENSE_LAYERS.keys) {
                        click("defense-details-$layer-em");text("defense-detail-$layer-em",DefenseScalar(StatValue.Decimal(0.0),"%",query(id).layers.getValue(layer).resistances.getValue("em").detail,null))
                        screenshot("prepare-$layer");click("defense-details-$layer-em")
                    }
                    compose.activityRule.scenario.recreate();ready(id);reference(expected,query(id))
                }
                if(index==5) { compose.onNodeWithTag("defense-value-total").performScrollTo();screenshot("prepare-mixed") }
                click("defense-back")
            }
            val owner=ids.getString(0);open(owner);val steps=fixture.getJSONObject("pattern_edits").getJSONArray("steps")
            compose.onNodeWithTag("defense-input-em").performScrollTo().performTextReplacement("50")
            send(BridgeOperation.SetSkillLevel(owner,"Hull Upgrades",0),owner);ready(owner)
            assertTrue(model.drafts.getValue(owner).conflict);assertEquals("50",model.drafts.getValue(owner).text["em"])
            compose.onNodeWithTag("defense-apply").performScrollTo().assertIsNotEnabled()
            click("defense-reset");click("history-undo");ready(owner)
            reference(fixture.getJSONObject("pattern_edits").getJSONObject("initial"),query(owner))
            for(field in DAMAGE_TYPES.keys) compose.onNodeWithTag("defense-input-$field").performScrollTo().performTextReplacement("0")
            compose.onNodeWithTag("defense-apply").performScrollTo().assertIsNotEnabled();click("defense-reset")
            for(index in 0 until steps.length()) {
                val step=steps.getJSONObject(index);val field=step.getString("field").removeSuffix("Amount")
                val unchanged=EngineRuntime.recent.value
                compose.onNodeWithTag("defense-input-$field").performScrollTo().performTextReplacement("50")
                click("defense-apply");compose.waitUntil(60_000) { !model.drafts.getValue(owner).saving };ready(owner)
                val changed=query(owner);reference(step.getJSONObject("expected"),changed)
                compare(step.getJSONObject("pattern"),graph().getJSONObject("records").getJSONObject(owner).getJSONObject("spec").getJSONObject("damage_pattern"),strict=false)
                assertEquals("Change incoming damage",EngineRuntime.editHistory(context,owner).get(120,TimeUnit.SECONDS).undoLabel)
                val after=raw(changed)
                click("history-undo");ready(owner);reference(fixture.getJSONObject("pattern_edits").getJSONObject("initial"),query(owner))
                click("history-redo");ready(owner);reference(step.getJSONObject("expected"),query(owner))
                edits.put(obj("field" to step.getString("field"),"after" to after,"redo" to raw(query(owner))))
                click("history-undo");ready(owner);reference(fixture.getJSONObject("pattern_edits").getJSONObject("initial"),query(owner));assertEquals(unchanged,EngineRuntime.recent.value)
            }
            val cursor=EngineRuntime.editHistory(context,owner).get(120,TimeUnit.SECONDS);val beforeNoOp=graph()
            send(BridgeOperation.SetDamagePattern(owner,DamagePattern(25.0,25.0,25.0,25.0)),owner);ready(owner)
            assertEquals(cursor.undoCount,EngineRuntime.editHistory(context,owner).get(120,TimeUnit.SECONDS).undoCount)
            assertEquals(cursor.redoCount,EngineRuntime.editHistory(context,owner).get(120,TimeUnit.SECONDS).redoCount)
            compare(ModuleTestJson.typed(beforeNoOp.getJSONObject("records")),ModuleTestJson.typed(graph().getJSONObject("records")),strict=false)
            val final=steps.getJSONObject(3);send(BridgeOperation.SetDamagePattern(owner,pattern(final.getJSONObject("pattern"))),owner);ready(owner)
            reference(final.getJSONObject("expected"),query(owner))
            compose.onNodeWithTag("defense-input-explosive").performScrollTo();screenshot("prepare-pattern")
            val old=EngineRuntime.library.value.map { it.id }.toSet()
            val copy=send(BridgeOperation.DuplicateFit(owner,"C01.3.1 copy"),owner).fits.single { it.id !in old }.id
            assertEquals(query(owner).layers,query(copy).layers);assertEquals(query(owner).pattern,query(copy).pattern)
            assertEquals(0,EngineRuntime.editHistory(context,copy).get(120,TimeUnit.SECONDS).undoCount)
            compose.activityRule.scenario.recreate();ready(owner);reference(final.getJSONObject("expected"),query(owner))
            val finalGraph=graph();val previous=inherited.getJSONArray("data");val priorIds=(0 until previous.length()).map { previous.getJSONObject(it).getString("id") }
            compare(inherited,ModuleTestJson.typed(JSONArray(priorIds.map { ModuleTestJson.fit(fit(it)) })),strict=false)
            for(id in priorIds) for(field in listOf("records","revisions","modified")) compare(ModuleTestJson.typed(inheritedGraph.getJSONObject(field).get(id)),ModuleTestJson.typed(finalGraph.getJSONObject(field).get(id)),strict=false)
            assertEquals(189,EngineRuntime.library.value.size)
            file.writeText(obj("pid" to Process.myPid(),"ids" to ids,"inherited" to inherited,"inherited_graph" to ModuleTestJson.typed(inheritedGraph),"graph" to ModuleTestJson.typed(finalGraph),
                "all_fits" to ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))),"edits" to edits,"copy_id" to copy,"copy_defense" to raw(query(copy)),
                "defenses" to JSONArray((0 until ids.length()).map { raw(query(ids.getString(it))) })).toString(),Charsets.UTF_8)
        } else {
            val saved=JSONObject(file.readText(Charsets.UTF_8));assertNotEquals(saved.getInt("pid"),Process.myPid());compare(saved.getJSONObject("graph"),ModuleTestJson.typed(graph()),strict=false)
            compare(saved.getJSONObject("all_fits"),ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))),strict=false)
            val previous=saved.getJSONArray("ids");val prior=saved.getJSONArray("defenses")
            for(index in 0 until previous.length()) {
                val id=previous.getString(index);ids.put(id);open(id)
                val expected=if(index==0) fixture.getJSONObject("pattern_edits").getJSONArray("steps").getJSONObject(3).getJSONObject("expected") else cases.getJSONObject(index).getJSONObject("expected").getJSONObject("defenses")
                screen(id,expected);compare(prior.getJSONObject(index),raw(query(id)),strict=false)
                assertEquals(0,EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS).undoCount)
                observations.put(obj("case" to index,"actual" to raw(query(id))));click("defense-back")
            }
            assertTrue(EngineRuntime.library.value.all { EngineRuntime.editHistory(context,it.id).get(120,TimeUnit.SECONDS).let { h -> h.undoCount==0 && h.redoCount==0 } })
            compare(saved.getJSONObject("copy_defense"),raw(query(saved.getString("copy_id"))),strict=false)
            open(previous.getString(0));compose.onNodeWithTag("defense-value-total").performScrollTo();screenshot("restored")
        }
        val descriptors=instrumentation.uiAutomation.executeShellCommandRw("dd of=/sdcard/Download/pyfa-c013-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(obj("task" to "C01.3.1","phase" to phase,"pid" to Process.myPid(),
                "runtime_start" to start,"ids" to ids,"observations" to observations,"protocol_rejections" to guards,"saved" to JSONObject(file.readText(Charsets.UTF_8)),
                "copy_observation" to raw(query(JSONObject(file.readText(Charsets.UTF_8)).getString("copy_id"))),
                "fixture_sha256" to MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }).toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
}
