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
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import io.github.sussic.pyfa.ModuleTestJson.array
import io.github.sussic.pyfa.ModuleTestJson.compare
import io.github.sussic.pyfa.ModuleTestJson.obj
import io.github.sussic.pyfa.ModuleTestJson.typed

@RunWith(AndroidJUnit4::class)
@OptIn(ExperimentalTestApi::class)
class ChargeEditingTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val picker get() = ViewModelProvider(compose.activity)[ChargeEditorModel::class.java]
    private val editor get() = ViewModelProvider(compose.activity)[ModuleEditorModel::class.java]
    private fun fits() = EngineRuntime.library.value
    private fun fit(id: String) = fits().single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun waitFor(predicate: () -> Boolean) { compose.waitUntil(60_000, predicate); sync() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick(); sync() }
    private fun edit(tag: String, text: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(text); sync() }
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList(), ok: Boolean = true): BridgeResponse {
        val response = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
        assertEquals(response.error?.message, ok, response.isSuccess)
        return response
    }
    private fun create(ship: String, name: String, modules: List<ModuleSpec> = emptyList()): String =
        send(BridgeOperation.CreateFit(FitSpec(name, ship, 5, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
            Security(SystemSecurity.HISEC, 0.0), modules, emptyList()))).fits.single().id
    private fun options(id: String) = EngineRuntime.chargeOptions(context, id).get(120, TimeUnit.SECONDS)
    private fun optionJson(value: ChargeOptions) = obj(
        "modules" to array(value.modules.map { obj("index" to it.index, "item_id" to it.itemId,
            "charge_id" to it.chargeId, "charge_ids" to array(it.chargeIds)) }),
        "items" to array(value.items.map { obj("id" to it.id, "name" to it.name) }))
    private fun allOptions() = array(fits().map { optionJson(options(it.id)).put("fit_id", it.id).put("revision", it.revision) })
    private fun library() = typed(array(fits().map(ModuleTestJson::fit)))
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
    private fun report(id: String, recipients: List<String>) = obj(
        "options" to optionJson(options(id)), "stats" to ModuleTestJson.stats(fit(id)),
        "modules" to JSONArray(EngineRuntime.chargeModuleDiagnostics(context, id).get(120, TimeUnit.SECONDS)),
        "recipients" to array(recipients.map { obj("name" to fit(it).name, "stats" to ModuleTestJson.stats(fit(it))) }),
        "recent" to array(EngineRuntime.recent.value))
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b04231-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b04231-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(value.toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
    private fun choose(name: String, id: Int, target: Int) {
        edit("charges-search", name)
        click("charge-item-$id")
        click("charge-load-$target")
        waitFor { !picker.loading && !picker.editing && picker.error == null && picker.options?.modules?.getOrNull(target)?.chargeId == id }
    }
    private fun enter(id: String, position: Int) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        sync(); click("modules-open")
        waitFor { !editor.loading && editor.details?.fitId == id }
        val slot = editor.details!!.modules[position].slot
        click("modules-rack-${slot.name}"); click("module-charges-$position")
        waitFor { !picker.loading && picker.options?.fitId == id }
    }
    private fun leave() { click("charges-back"); click("modules-back") }
    private fun guards(id: String): JSONArray {
        val results = JSONArray()
        val base = optionJson(options(id)).put("version", 1).put("fit_id", id).put("revision", fit(id).revision)
        fun reject(name: String, mutate: (JSONObject) -> Unit) {
            val changed = JSONObject(base.toString()); mutate(changed)
            try { BridgeCodec.decodeChargeOptions(changed.toString()); fail("Accepted $name") }
            catch (_: BridgeProtocolException) { results.put(name) }
        }
        val raw = base.toString()
        val firstId = base.getJSONArray("items").getJSONObject(0).getInt("id")
        for ((label, malformed) in listOf("decimal_id" to raw.replaceFirst("\"id\":$firstId", "\"id\":$firstId.0"),
                "decimal_revision" to raw.replaceFirst("\"revision\":${fit(id).revision}", "\"revision\":${fit(id).revision}.0"))) {
            assertNotEquals(raw, malformed)
            try { BridgeCodec.decodeChargeOptions(malformed); fail("Accepted $label") }
            catch (_: BridgeProtocolException) { results.put(label) }
        }
        reject("boolean_id") { it.getJSONArray("items").getJSONObject(0).put("id", true) }
        reject("negative_revision") { it.put("revision", -1) }
        reject("missing_items") { it.remove("items") }
        reject("extra_field") { it.put("extra", 1) }
        reject("noncontiguous_position") { it.getJSONArray("modules").getJSONObject(0).put("index", 9) }
        reject("duplicate_charge") { it.getJSONArray("items").put(it.getJSONArray("items").getJSONObject(0)) }
        reject("incorrect_union") { it.getJSONArray("items").remove(0) }
        reject("vacancy_with_charge") { it.getJSONArray("modules").getJSONObject(0).put("item_id", JSONObject.NULL) }
        val firstCompatible = base.getJSONArray("modules").getJSONObject(0).getJSONArray("charge_ids").getInt(0)
        val decimalCompatibility = raw.replaceFirst("\"charge_ids\":[$firstCompatible", "\"charge_ids\":[$firstCompatible.0")
        assertNotEquals(raw, decimalCompatibility)
        try { BridgeCodec.decodeChargeOptions(decimalCompatibility); fail("Accepted decimal_compatibility") }
        catch (_: BridgeProtocolException) { results.put("decimal_compatibility") }
        return results
    }

    @Test fun chargesAndDiscoverySurviveRestartOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b04231_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val fixture = JSONObject(InstrumentationRegistry.getInstrumentation().context.assets.open("charge-edits-expected.json")
            .bufferedReader().use { it.readText() })
        val catalogue = EngineRuntime.equipmentCatalog(context).get(120, TimeUnit.SECONDS)
        fun item(name: String) = catalogue.items.single { it.name == name }.id
        val before = library()
        val recentBefore = array(EngineRuntime.recent.value)
        val runtimeStart = diagnostics()
        compare(ModuleTestJson.numericKinds(fixture.getJSONObject("eos_settings")), runtimeStart.getJSONObject("eos_settings_numeric_types"))
        val observed = JSONArray()
        val compatibility = JSONArray()
        val rejections = JSONArray()
        var codec = JSONArray()
        val saved = File(context.noBackupFilesDir, "b04231-test-expected.json")
        try {
            when (phase) {
                "prepare" -> {
                    val originalIds = fits().map { it.id }.toSet()
                    val cases = fixture.getJSONArray("cases")
                    for (c in 0 until cases.length()) {
                        val case = cases.getJSONObject(c)
                        val initial = case.getJSONArray("modules")
                        val source = create(case.getString("ship"), case.getString("name"), (0 until initial.length()).map { i ->
                            initial.getJSONObject(i).let { ModuleSpec(it.getString("name"), ModuleState.valueOf(it.getString("state")),
                                if (it.has("charge") && !it.isNull("charge")) it.getString("charge") else null) } })
                        send(BridgeOperation.SetFitRestrictions(source, false), listOf(source))
                        val recipients = mutableListOf<String>()
                        val targets = case.optJSONArray("recipients") ?: JSONArray()
                        for (i in 0 until targets.length()) {
                            val target = targets.getJSONObject(i)
                            val id = create(target.getString("ship"), target.getString("name"))
                            send(BridgeOperation.SetFitRestrictions(id, false), listOf(id))
                            send(if (case.optString("link") == "command") BridgeOperation.AddCommand(source, id)
                                else BridgeOperation.AddProjection(source, id, 0.0), listOf(source, id))
                            recipients += id
                        }
                        val steps = case.getJSONArray("steps")
                        val results = JSONArray()
                        for (s in 0 until steps.length()) {
                            val step = steps.getJSONObject(s)
                            val input = if (step.isNull("input")) null else step.getJSONObject("input")
                            if (input != null) {
                                val position = input.getInt("position")
                                val charge = if (input.isNull("charge_id")) null else input.getInt("charge_id")
                                val same = options(source).modules[position].chargeId == charge
                                val committed = library()
                                val result = send(BridgeOperation.SetModuleCharge(source, position, charge), listOf(source), step.getBoolean("changed") || same)
                                if (!result.isSuccess) compare(committed, library(), "invalid_charge_atomic")
                            }
                            val actual = report(source, recipients)
                            // Desktop charge commands leave history unchanged; the prior native
                            // phase intentionally populated it. Verify that same transition here.
                            assertEquals("[]", step.getJSONObject("result").getJSONArray("recent").toString())
                            val reference = step.getJSONObject("result").put("recent", recentBefore)
                            compare(reference, actual, "${case.getString("name")}.$s")
                            results.put(obj("input" to input, "changed" to step.getBoolean("changed"), "result" to typed(actual)))
                        }
                        observed.put(obj("name" to case.getString("name"), "steps" to results))
                        for (id in (listOf(source) + recipients).reversed()) send(BridgeOperation.DeleteFit(id, true), listOf(id))
                    }
                    compare(before, library(), "prior_fits_after_matrix")
                    val all = EngineRuntime.chargeCompatibilityDiagnostics(context).get(300, TimeUnit.SECONDS)
                    all.forEach { compatibility.put(obj("id" to it.id, "charge_ids" to array(it.chargeIds))) }
                    compare(fixture.getJSONArray("compatibility"), compatibility, "all_4242_charge_sets")
                    assertEquals(4242, all.size)
                    compare(before, library(), "compatibility_read_only")

                    val ship = create("Vexor", "B04 charge picker – 探索", listOf(
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.ACTIVE, "Antimatter Charge M"),
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.OVERHEATED, "Iron Charge M"),
                        ModuleSpec("Tracking Computer II", ModuleState.ACTIVE)))
                    enter(ship, 0)
                    assertTrue(options(ship).modules[0].chargeIds.size > 20)
                    click("charges-next"); assertEquals(1, picker.page)
                    screenshot("picker")
                    edit("charges-search", "zz-no-such-charge")
                    compose.onNodeWithTag("charges-empty").assertExists()
                    edit("charges-search", "Spike M"); click("charge-item-${item("Spike M")}")
                    compose.activityRule.scenario.recreate(); sync()
                    assertEquals(0, picker.position); assertEquals(item("Spike M"), picker.selected)
                    assertEquals("Spike M", picker.query)
                    click("charge-load-0")
                    waitFor { !picker.loading && !picker.editing && fit(ship).modules[0].charge == "Spike M" }
                    assertEquals("Iron Charge M", fit(ship).modules[1].charge)
                    assertEquals(ModuleState.OVERHEATED, fit(ship).modules[1].state)
                    compose.onNodeWithTag("charges-current").performScrollTo(); screenshot("loaded")
                    codec = guards(ship)
                    val committed = library()
                    val bad = send(BridgeOperation.SetModuleCharge(ship, 0, item("Antimatter Charge S")), listOf(ship), false)
                    rejections.put(obj("label" to "incompatible", "code" to bad.error?.code?.name))
                    val unknown = send(BridgeOperation.SetModuleCharge(ship, 0, Int.MAX_VALUE), listOf(ship), false)
                    rejections.put(obj("label" to "unknown", "code" to unknown.error?.code?.name))
                    val stale = EngineRuntime.request(context, BridgeOperation.SetModuleCharge(ship, 0, null), mapOf(ship to 0L)).get(120, TimeUnit.SECONDS)
                    rejections.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    assertEquals(BridgeErrorCode.REVISION_CONFLICT, stale.error?.code)
                    compare(committed, library(), "rejections_atomic")
                    click("charges-unload")
                    waitFor { !picker.loading && !picker.editing && fit(ship).modules[0].charge == null }
                    choose("Javelin M", item("Javelin M"), 0)
                    leave(); enter(ship, 2)
                    choose("Tracking Speed Script", item("Tracking Speed Script"), 2)
                    compose.onNodeWithTag("charges-current").performScrollTo(); screenshot("script")
                    leave()
                    val laser = create("Punisher", "B04 laser crystal", listOf(ModuleSpec("Gatling Pulse Laser II", ModuleState.OVERHEATED)))
                    enter(laser, 0); choose("Scorch S", item("Scorch S"), 0)
                    compose.onNodeWithTag("charges-current").performScrollTo(); screenshot("crystal"); leave()
                    val miner = create("Hulk", "B04 mining crystal", listOf(ModuleSpec("Modulated Strip Miner II", ModuleState.ACTIVE)))
                    enter(miner, 0); choose("Simple Asteroid Mining Crystal Type B II", item("Simple Asteroid Mining Crystal Type B II"), 0)
                    compose.onNodeWithTag("charges-current").performScrollTo(); screenshot("mining"); leave()
                    val copy = send(BridgeOperation.DuplicateFit(ship, "B04 independent charge copy"), listOf(ship)).fits.single { it.name == "B04 independent charge copy" }.id
                    send(BridgeOperation.SetModuleCharge(copy, 0, null), listOf(copy))
                    assertEquals("Javelin M", fit(ship).modules[0].charge)
                    EngineRuntime.selectFit(context, ship).get(30, TimeUnit.SECONDS)
                    click("equipment-open"); click("equipment-charges")
                    waitFor { !picker.loading && picker.options?.fitId == ship }
                    assertNull(picker.position)
                    edit("charges-search", "Script")
                    compose.onNodeWithTag("charges-active").performScrollTo(); screenshot("active")
                    // Existing no-charge ship proves active-fit changes cannot leave stale choices.
                    val empty = fits().first { it.id in originalIds && it.modules.none { mod -> mod.name != null } }
                    EngineRuntime.selectFit(context, empty.id).get(30, TimeUnit.SECONDS)
                    waitFor { !picker.loading && picker.options?.fitId == empty.id }
                    assertTrue(picker.options!!.items.isEmpty())
                    compose.onNodeWithTag("charges-empty").performScrollTo(); screenshot("empty")
                    compare(before, typed(array(fits().filter { it.id in originalIds }.map(ModuleTestJson::fit))), "prior_fits_unchanged")
                    compare(recentBefore, array(EngineRuntime.recent.value), "charge_history_unchanged")
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    EngineRuntime.selectFit(context, ship).get(30, TimeUnit.SECONDS)
                    saved.writeText(obj("fits" to library(), "options" to allOptions(), "prior" to before,
                        "recent" to recentBefore, "active_id" to ship, "new_ids" to array(listOf(ship, laser, miner, copy))).toString(), Charsets.UTF_8)
                }
                "restored" -> {
                    val expected = JSONObject(saved.readText(Charsets.UTF_8))
                    compare(expected.getJSONObject("fits"), library(), "restored_fits", strict = false)
                    compare(expected.getJSONArray("options"), allOptions(), "restored_options")
                    compare(expected.getJSONArray("recent"), array(EngineRuntime.recent.value))
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    val ids = expected.getJSONArray("new_ids")
                    for (i in 0 until ids.length()) {
                        val id = ids.getString(i)
                        enter(id, 0)
                        assertEquals(fit(id).modules[0].charge != null, picker.options!!.modules[0].chargeId != null)
                        if (i == 0) { compose.onNodeWithTag("charges-current").performScrollTo(); screenshot("restored") }
                        leave()
                    }
                }
                else -> error("Unknown phase")
            }
            retain(obj("task" to "B04.2.3.1", "phase" to phase, "pid" to Process.myPid(),
                "runtime_start" to runtimeStart, "runtime_end" to diagnostics(), "before" to before, "after" to library(),
                "options" to allOptions(), "recent_before" to recentBefore, "recent_after" to array(EngineRuntime.recent.value),
                "cases" to observed, "compatibility" to compatibility, "rejections" to rejections, "codec_rejections" to codec,
                "saved" to JSONObject(saved.readText(Charsets.UTF_8)), "checks" to array(if (phase == "prepare") listOf(
                    "complete_matrix", "all_4242_charge_sets", "projection_and_command_recipients", "prior_fits_unchanged",
                    "picker_pagination_search", "picker_recreation", "load_replace_unload", "neighbour_state_charge_retained",
                    "script", "laser_crystal", "mining_crystal", "active_fit_discovery", "empty_fit_refresh", "independent_copy",
                    "rejections_atomic", "recent_unchanged", "typed_protocol_guards") else listOf(
                    "fresh_process_restore", "identities_states_charges_values_retained", "options_and_recent_retained", "reopen_each_fit"))), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
