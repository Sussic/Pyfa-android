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
class TankTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[TankModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().performClick(); sync() }
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList()): BridgeResponse {
        val result = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess); return result
    }
    private fun query(id: String) = EngineRuntime.tankDetails(context, id).get(120, TimeUnit.SECONDS)
    private fun graph() = JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
    private fun kind(value: StatValue) = when (value) {
        is StatValue.Integer -> "integer"; is StatValue.Decimal -> "decimal"; StatValue.Unavailable -> "unavailable"; else -> error("Non-numeric tank")
    }
    private fun scalar(value: TankScalar) = obj("value" to value.value.raw, "value_type" to kind(value.value),
        "unit" to value.unit, "display" to value.display, "detail" to value.detail)
    private fun variant(value: TankVariant) = obj("repairs" to JSONObject().apply {
        value.repairs.forEach { (name, row) -> put(name, scalar(row)) }
    }, "armor_spool" to obj("pre" to scalar(value.pre), "full" to scalar(value.full), "indicated" to value.indicated, "tooltip" to value.tooltip))
    private fun raw(value: FitTank) = obj("fit_id" to value.fitId, "revision" to value.revision, "tank" to JSONObject().apply {
        value.modes.forEach { (name, row) -> put(name, obj("passive_shield" to scalar(row.passiveShield),
            "reinforced" to variant(row.reinforced), "sustained" to variant(row.sustained))) }
    })
    private fun wire(value: Any): String = when (value) {
        is JSONObject -> value.keys().asSequence().joinToString(",", "{", "}") { JSONObject.quote(it) + ":" + wire(value.get(it)) }
        is JSONArray -> (0 until value.length()).joinToString(",", "[", "]") { wire(value.get(it)) }
        is String -> JSONObject.quote(value)
        else -> value.toString()
    }
    private fun reference(expected: JSONObject, value: FitTank) {
        compare(expected.getJSONObject("tank"), raw(value).getJSONObject("tank"), strict=false)
        for ((name, row) in value.modes) {
            val wanted = expected.getJSONObject("tank").getJSONObject(name)
            assertEquals(wanted.getJSONObject("passive_shield").getString("value_type"), kind(row.passiveShield.value))
            for ((stability, v) in listOf("reinforced" to row.reinforced, "sustained" to row.sustained)) {
                val w = wanted.getJSONObject(stability)
                v.repairs.forEach { (field, s) -> assertEquals(w.getJSONObject("repairs").getJSONObject(field).getString("value_type"), kind(s.value)) }
                assertEquals(w.getJSONObject("armor_spool").getJSONObject("pre").getString("value_type"), kind(v.pre.value))
                assertEquals(w.getJSONObject("armor_spool").getJSONObject("full").getString("value_type"), kind(v.full.value))
            }
        }
    }
    private fun ready(id: String) {
        compose.waitUntil(60_000) { !model.loading && model.error == null && model.details?.let { it.fitId == id && it.revision == fit(id).revision } == true }; sync()
    }
    private fun open(id: String) { EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS); sync(); click("tank-open"); ready(id) }
    private fun text(tag: String, row: TankScalar) { compose.onNodeWithTag(tag).performScrollTo().assertTextEquals(row.display?.let { "$it ${row.unit}" } ?: "Unavailable") }
    private fun screen(id: String, expected: JSONObject) {
        ready(id); reference(expected, model.details!!)
        val original = query(id)
        compose.onNodeWithTag("tank-toggle").performScrollTo().assertTextEquals("Show raw HP/s")
        for (mode in listOf("effective", "raw")) {
            val row = original.modes.getValue(mode)
            text("tank-value-passive", row.passiveShield)
            for ((stability, variant) in listOf("reinforced" to row.reinforced, "sustained" to row.sustained))
                variant.repairs.forEach { (name, value) -> text("tank-value-$stability-$name", value) }
            click("tank-toggle")
        }
        assertEquals(original, query(id))
    }
    private fun precision(row: TankScalar) = if (row.value == StatValue.Unavailable) "Unavailable" else row.value.raw.toString()
    private fun spoolDetails(id: String, mode: String) {
        val row = query(id).modes.getValue(mode)
        for ((stability, variant) in listOf("reinforced" to row.reinforced, "sustained" to row.sustained)) {
            val tag = "$stability-armorRepair"; click("tank-details-$tag")
            compose.onNodeWithTag("tank-detail-$tag").performScrollTo().assertTextEquals("${variant.repairs.getValue("armorRepair").detail} ${variant.pre.unit}")
            compose.onNodeWithTag("tank-spool-indication-$tag").performScrollTo().assertTextEquals(if (variant.indicated) variant.tooltip else "No spool increase")
            compose.onNodeWithTag("tank-spool-current-$tag").performScrollTo().assertTextEquals("Current: ${precision(variant.repairs.getValue("armorRepair"))} ${variant.pre.unit}")
            compose.onNodeWithTag("tank-spool-pre-$tag").performScrollTo().assertTextEquals("Pre-spool: ${variant.pre.detail} ${variant.pre.unit} · Full precision: ${precision(variant.pre)}")
            compose.onNodeWithTag("tank-spool-full-$tag").performScrollTo().assertTextEquals("Full spool: ${variant.full.detail} ${variant.full.unit} · Full precision: ${precision(variant.full)}")
            screenshot("prepare-spool-$mode-$stability"); click("tank-details-$tag")
        }
    }
    private fun screenshot(name: String) {
        sync(); instrumentation.uiAutomation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand("screencap -p /sdcard/Download/pyfa-c0132-$name.png")).use { it.readBytes() }
    }
    private fun create(value: JSONObject): String {
        val native = JSONObject(value.toString())
        assertFalse(native.getBoolean("ignore_restrictions")); assertEquals(0, native.getJSONArray("cargo").length())
        native.remove("ignore_restrictions"); native.remove("cargo")
        val spec = BridgeCodec.decodeFitSpec(native.toString())
        val id = send(BridgeOperation.CreateFit(spec.copy(name="C01.3.2 ${spec.name}"))).fits.single().id
        assertEquals(spec.modules.size, fit(id).modules.size)
        spec.modules.forEachIndexed { index, m ->
            assertEquals(index, fit(id).modules[index].index); assertEquals(m.name, fit(id).modules[index].name)
            assertEquals(m.state, fit(id).modules[index].state); assertEquals(m.charge, fit(id).modules[index].charge)
        }; return id
    }
    private fun protocol(value: FitTank): JSONArray {
        val good = raw(value).put("version", 1); assertEquals(value, BridgeCodec.decodeTank(wire(good)))
        val names = listOf("version", "extra", "missing", "unit", "boolean", "kind", "display", "revision",
            "missing_mode", "missing_repair", "spool_flag", "spool_tooltip", "spool_missing", "fractional_integer")
        for (name in names) {
            val bad = JSONObject(wire(good)); val data = bad.getJSONObject("tank"); val row = data.getJSONObject("raw").getJSONObject("reinforced")
            val repair = row.getJSONObject("repairs").getJSONObject("armorRepair"); val spool = row.getJSONObject("armor_spool")
            when (name) {
                "version" -> bad.put("version", 2); "extra" -> bad.put("extra", true); "missing" -> bad.remove("tank")
                "unit" -> repair.put("unit", "GJ/s"); "boolean" -> repair.put("value", false); "kind" -> repair.put("value_type", "text")
                "display" -> repair.put("display", JSONObject.NULL); "revision" -> bad.put("revision", 0)
                "missing_mode" -> data.remove("effective"); "missing_repair" -> row.getJSONObject("repairs").remove("hullRepair")
                "spool_flag" -> spool.put("indicated", 1); "spool_tooltip" -> spool.put("indicated", true).put("tooltip", "")
                "spool_missing" -> spool.remove("full"); "fractional_integer" -> repair.put("value", 1.25).put("value_type", "integer")
            }
            try { BridgeCodec.decodeTank(wire(bad)); fail("Accepted $name") } catch (_: BridgeProtocolException) { }
        }
        val absent = JSONObject(wire(good)); absent.getJSONObject("tank").getJSONObject("raw").getJSONObject("passive_shield")
            .put("value", JSONObject.NULL).put("value_type", "unavailable").put("display", JSONObject.NULL).put("detail", JSONObject.NULL)
        assertEquals(StatValue.Unavailable, BridgeCodec.decodeTank(wire(absent)).modes.getValue("raw").passiveShield.value)
        return JSONArray(names)
    }

    @Test fun tankRepairSpoolRefreshAndRestoreOffline() {
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val phase = InstrumentationRegistry.getArguments().getString("c0132_phase") ?: error("Missing phase")
        assertTrue(phase in listOf("prepare", "restored"))
        val start = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        assertTrue(start.getJSONObject("persistence").getBoolean("enabled")); assertTrue(start.getJSONObject("persistence").getBoolean("opened_existing"))
        assertEquals(if (phase == "prepare") 189 else 230, EngineRuntime.library.value.size)
        val bytes = instrumentation.context.assets.open("tank-expected.json").use { it.readBytes() }
        val fixture = JSONObject(bytes.toString(Charsets.UTF_8)); val cases = fixture.getJSONArray("cases"); assertEquals(29, cases.length())
        val file = File(context.noBackupFilesDir, "c0132-expected.json")
        val observations = JSONArray(); val ids = JSONArray(); val sources = JSONObject(); var guards = JSONArray(); val edits = JSONArray()
        if (phase == "prepare") {
            val inherited = ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))); val inheritedGraph = graph()
            for (index in 0 until cases.length()) {
                println("TANK CASE $index ${cases.getJSONObject(index).getJSONObject("spec").getString("name")}")
                val case = cases.getJSONObject(index); val id = create(case.getJSONObject("spec")); ids.put(id)
                if (case.has("source")) {
                    val source = create(case.getJSONObject("source")); sources.put(id, source); val edge = case.getJSONObject("projection")
                    send(BridgeOperation.AddProjection(source, id, edge.getDouble("range_m"), edge.getBoolean("active"), edge.getInt("amount")), listOf(source, id))
                }
                open(id); screen(id, case.getJSONObject("expected"))
                val before = raw(query(id)); val durable = ModuleTestJson.typed(graph())
                val history = EngineRuntime.editHistory(context, id).get(120, TimeUnit.SECONDS); val recent = EngineRuntime.recent.value
                repeat(3) { System.gc(); reference(case.getJSONObject("expected"), query(id)) }
                compare(durable, ModuleTestJson.typed(graph()), strict=false)
                assertEquals(history, EngineRuntime.editHistory(context, id).get(120, TimeUnit.SECONDS)); assertEquals(recent, EngineRuntime.recent.value)
                observations.put(obj("case" to index, "actual" to before))
                if (index == 0) {
                    guards = protocol(query(id)); compose.activityRule.scenario.recreate(); ready(id); reference(case.getJSONObject("expected"), query(id))
                    click("tank-details-passive"); compose.onNodeWithTag("tank-detail-passive").performScrollTo().assertTextEquals("${query(id).modes.getValue("effective").passiveShield.detail} EHP/s")
                    screenshot("prepare-passive"); click("tank-details-passive")
                }
                if (index in listOf(1, 4, 7, 11, 15, 25, 28)) {
                    val tag = if (index == 7) "sustained-hullRepair" else if (index == 4 || index == 25) "reinforced-armorRepair" else "reinforced-shieldRepair"
                    compose.onNodeWithTag("tank-value-$tag").performScrollTo(); screenshot("prepare-$index")
                }
                if (index == 23) {
                    assertTrue(query(id).modes.getValue("raw").reinforced.indicated)
                    spoolDetails(id, "effective"); click("tank-toggle"); spoolDetails(id, "raw"); click("tank-toggle")
                }
                click("tank-back")
            }
            val armor = ids.getString(4); open(armor); val original = query(armor)
            send(BridgeOperation.SetModuleStates(armor, listOf(0), ModuleState.OFFLINE), listOf(armor)); ready(armor)
            assertEquals(0.0, query(armor).modes.getValue("raw").reinforced.repairs.getValue("armorRepair").value.numberOrNull()!!, 0.0)
            val changed = raw(query(armor)); click("history-undo"); ready(armor); assertEquals(original.modes, query(armor).modes)
            click("history-redo"); ready(armor); compare(changed.getJSONObject("tank"), raw(query(armor)).getJSONObject("tank"), strict=false)
            edits.put(obj("action" to "offline", "after" to changed, "redo" to raw(query(armor))))
            click("history-undo"); ready(armor)
            send(BridgeOperation.RemoveModule(armor, 0), listOf(armor)); ready(armor)
            assertEquals(0.0, query(armor).modes.getValue("raw").reinforced.repairs.getValue("armorRepair").value.numberOrNull()!!, 0.0)
            val removed = raw(query(armor)); click("history-undo"); ready(armor); assertEquals(original.modes, query(armor).modes)
            click("history-redo"); ready(armor); compare(removed.getJSONObject("tank"), raw(query(armor)).getJSONObject("tank"), strict=false)
            edits.put(obj("action" to "remove_module", "after" to removed, "redo" to raw(query(armor))))
            click("history-undo"); ready(armor); click("tank-back")
            val owner = ids.getString(23); val source = sources.getString(owner); open(owner); val before = query(owner)
            send(BridgeOperation.RemoveProjection(source, owner), listOf(source, owner)); ready(owner)
            val noProjection = query(owner); assertFalse(noProjection.modes.getValue("raw").reinforced.indicated)
            assertEquals(0.0, noProjection.modes.getValue("raw").reinforced.repairs.getValue("armorRepair").value.numberOrNull()!!, 0.0)
            click("history-undo"); ready(owner); assertEquals(before.modes, query(owner).modes)
            click("history-redo"); ready(owner); assertEquals(noProjection.modes, query(owner).modes)
            edits.put(obj("action" to "remove_projection", "after" to raw(noProjection), "redo" to raw(query(owner))))
            click("history-undo"); ready(owner); reference(cases.getJSONObject(23).getJSONObject("expected"), query(owner))
            val old = EngineRuntime.library.value.map { it.id }.toSet()
            val copy = send(BridgeOperation.DuplicateFit(owner, "C01.3.2 copy"), listOf(owner)).fits.single { it.id !in old }.id
            assertEquals(before.modes, query(copy).modes); assertEquals(0, EngineRuntime.editHistory(context, copy).get(120, TimeUnit.SECONDS).undoCount)
            compose.activityRule.scenario.recreate(); ready(owner); assertEquals(before.modes, query(owner).modes)
            val finalGraph = graph(); val previous = inherited.getJSONArray("data"); val priorIds = (0 until previous.length()).map { previous.getJSONObject(it).getString("id") }
            compare(inherited, ModuleTestJson.typed(JSONArray(priorIds.map { ModuleTestJson.fit(fit(it)) })), strict=false)
            for (id in priorIds) for (field in listOf("records", "revisions", "modified")) compare(ModuleTestJson.typed(inheritedGraph.getJSONObject(field).get(id)), ModuleTestJson.typed(finalGraph.getJSONObject(field).get(id)), strict=false)
            assertEquals(230, EngineRuntime.library.value.size)
            file.writeText(obj("pid" to Process.myPid(), "ids" to ids, "sources" to sources, "inherited" to inherited, "inherited_graph" to ModuleTestJson.typed(inheritedGraph),
                "graph" to ModuleTestJson.typed(finalGraph), "all_fits" to ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))),
                "edits" to edits, "copy_id" to copy, "copy_tank" to raw(query(copy)), "tanks" to JSONArray((0 until ids.length()).map { raw(query(ids.getString(it))) })).toString(), Charsets.UTF_8)
        } else {
            val saved = JSONObject(file.readText(Charsets.UTF_8)); assertNotEquals(saved.getInt("pid"), Process.myPid())
            compare(saved.getJSONObject("graph"), ModuleTestJson.typed(graph()), strict=false)
            compare(saved.getJSONObject("all_fits"), ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))), strict=false)
            val previous = saved.getJSONArray("ids"); val prior = saved.getJSONArray("tanks")
            for (index in 0 until previous.length()) {
                val id = previous.getString(index); ids.put(id); open(id); screen(id, cases.getJSONObject(index).getJSONObject("expected"))
                compare(prior.getJSONObject(index), raw(query(id)), strict=false); observations.put(obj("case" to index, "actual" to raw(query(id))))
                click("tank-back")
            }
            assertTrue(EngineRuntime.library.value.all { EngineRuntime.editHistory(context, it.id).get(120, TimeUnit.SECONDS).let { h -> h.undoCount == 0 && h.redoCount == 0 } })
            compare(saved.getJSONObject("copy_tank"), raw(query(saved.getString("copy_id"))), strict=false)
            open(previous.getString(23)); click("tank-details-reinforced-armorRepair"); compose.onNodeWithTag("tank-spool-full-reinforced-armorRepair").performScrollTo(); screenshot("restored")
        }
        val descriptors = instrumentation.uiAutomation.executeShellCommandRw("dd of=/sdcard/Download/pyfa-c0132-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(obj("task" to "C01.3.2", "phase" to phase, "pid" to Process.myPid(), "runtime_start" to start,
                "ids" to ids, "observations" to observations, "protocol_rejections" to guards, "saved" to JSONObject(file.readText(Charsets.UTF_8)),
                "copy_observation" to raw(query(JSONObject(file.readText(Charsets.UTF_8)).getString("copy_id"))),
                "fixture_sha256" to MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }).toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
}

