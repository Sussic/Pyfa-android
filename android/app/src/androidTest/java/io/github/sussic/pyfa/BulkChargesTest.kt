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
class BulkChargesTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val picker get() = ViewModelProvider(compose.activity)[BulkChargeEditorModel::class.java]
    private fun fits() = EngineRuntime.library.value
    private fun fit(id: String) = fits().single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun waitFor(predicate: () -> Boolean) { compose.waitUntil(60_000, predicate); sync() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick(); sync() }
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList(), ok: Boolean = true): BridgeResponse {
        val response = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
        assertEquals(response.error?.message, ok, response.isSuccess)
        return response
    }
    private fun create(ship: String, name: String, modules: List<ModuleSpec> = emptyList()): String =
        send(BridgeOperation.CreateFit(FitSpec(name, ship, 5, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
            Security(SystemSecurity.HISEC, 0.0), modules, emptyList()))).fits.single().id
    private fun options(id: String) = EngineRuntime.bulkChargeOptions(context, id).get(120, TimeUnit.SECONDS)
    private fun allOptions() = typed(array(fits().map { BulkTestJson.options(options(it.id)).put("fit_id", it.id).put("revision", it.revision) }))
    private fun library() = typed(array(fits().map(ModuleTestJson::fit)))
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
    private fun report(id: String, recipients: List<String> = emptyList()): JSONObject {
        val value = options(id)
        val details = EngineRuntime.fittingDetails(context, id).get(120, TimeUnit.SECONDS)
        return obj("options" to BulkTestJson.options(value), "stats" to ModuleTestJson.stats(fit(id)),
            "modules" to array(details.modules.map { row -> obj("index" to row.index, "id" to row.id,
                "slot" to row.slot.name, "state" to row.state.name, "charge_id" to value.modules[row.index].chargeId) }),
            "recipients" to array(recipients.map { obj("name" to fit(it).name, "stats" to ModuleTestJson.stats(fit(it))) }),
            "recent" to array(EngineRuntime.recent.value))
    }
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b051-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b051-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(value.toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        sync(); click("modules-open"); click("modules-bulk")
        waitFor { !picker.loading && picker.options?.fitId == id }
    }
    private fun choose(name: String, identity: Int) {
        compose.onNodeWithTag("bulk-search").performScrollTo().performTextReplacement(name)
        click("bulk-charge-$identity")
    }
    private fun apply() {
        click("bulk-apply")
        waitFor { !picker.loading && !picker.editing && picker.options?.revision == (EngineRuntime.state.value as EngineState.Ready).fit.revision }
        assertNull(picker.error)
    }
    private fun close() { if (picker.choosing) click("bulk-back"); click("bulk-back"); click("modules-back") }
    private fun operation(id: String, input: JSONObject) = BridgeOperation.SetBulkCharges(id, input.getInt("main_position"),
        input.getJSONArray("module_indices").let { values -> (0 until values.length()).map(values::getInt) },
        BulkScope.valueOf(input.getString("scope")), if (input.isNull("charge_id")) null else input.getInt("charge_id"))
    private fun guards(id: String): JSONArray {
        val results = JSONArray()
        val raw = EngineRuntime.bulkChargeOptionsDiagnostics(context, id).get(120, TimeUnit.SECONDS)
        BridgeCodec.decodeBulkChargeOptions(raw)
        fun reject(name: String, pattern: String, replacement: String) {
            val changed = raw.replaceFirst(Regex(pattern), replacement)
            assertNotEquals("Missing guard target: $name", raw, changed)
            try { BridgeCodec.decodeBulkChargeOptions(changed); fail("Accepted $name") }
            catch (_: BridgeProtocolException) { results.put(name) }
        }
        reject("decimal_index", "\"index\":\\s*0", "\"index\":0.0")
        reject("decimal_revision", "\"revision\":\\s*${fit(id).revision}", "\"revision\":${fit(id).revision}.0")
        reject("boolean_id", "\"item_id\":\\s*\\d+", "\"item_id\":true")
        reject("decimal_charge", "\"charge_id\":\\s*\\d+", "\"charge_id\":1.0")
        reject("candidate_out_of_range", "\"similar_candidates\":\\s*\\[[^]]*]", "\"similar_candidates\":[0,999]")
        reject("duplicate_candidate", "\"selection_candidates\":\\s*\\[[^]]*]", "\"selection_candidates\":[0,0]")
        reject("decimal_candidate", "\"similar_candidates\":\\s*\\[[^]]*]", "\"similar_candidates\":[0.0]")
        reject("missing_reference", "\"similar_candidates\":\\s*\\[[^]]*]", "\"similar_candidates\":[]")
        reject("wrong_selection_subset", "\"selection_candidates\":\\s*\\[[^]]*]", "\"selection_candidates\":[0]")
        reject("extra_field", "\\{", "{\"extra\":1,")
        return results
    }

    @Test fun bulkSelectionChargesSurviveRestartOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b051_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val fixture = JSONObject(InstrumentationRegistry.getInstrumentation().context.assets.open("bulk-charges-expected.json")
            .bufferedReader().use { it.readText() })
        val before = library(); val recentBefore = array(EngineRuntime.recent.value); val runtimeStart = diagnostics()
        compare(ModuleTestJson.numericKinds(fixture.getJSONObject("eos_settings")), runtimeStart.getJSONObject("eos_settings_numeric_types"))
        val observed = JSONArray(); val rejections = JSONArray(); var codec = JSONArray()
        val saved = File(context.noBackupFilesDir, "b051-test-expected.json")
        try {
            when (phase) {
                "prepare" -> {
                    val originalIds = fits().map { it.id }.toSet()
                    val cases = fixture.getJSONArray("cases")
                    for (c in 0 until cases.length()) {
                        val case = cases.getJSONObject(c); val initial = case.getJSONArray("modules")
                        val source = create(case.getString("ship"), case.getString("name"), (0 until initial.length()).map { i ->
                            initial.getJSONObject(i).let { ModuleSpec(it.getString("name"), ModuleState.valueOf(it.getString("state")),
                                if (it.has("charge") && !it.isNull("charge")) it.getString("charge") else null) } })
                        send(BridgeOperation.SetFitRestrictions(source, false), listOf(source))
                        val recipients = mutableListOf<String>(); val targets = case.optJSONArray("recipients") ?: JSONArray()
                        for (i in 0 until targets.length()) {
                            val row = targets.getJSONObject(i); val id = create(row.getString("ship"), row.getString("name"))
                            send(BridgeOperation.SetFitRestrictions(id, false), listOf(id))
                            send(if (case.optString("link") == "command") BridgeOperation.AddCommand(source, id)
                                else BridgeOperation.AddProjection(source, id, 0.0), listOf(source, id)); recipients += id
                        }
                        val steps = case.getJSONArray("steps"); val results = JSONArray()
                        for (s in 0 until steps.length()) {
                            val step = steps.getJSONObject(s); val input = if (step.isNull("input")) null else step.getJSONObject("input")
                            if (input != null) send(operation(source, input), listOf(source))
                            val actual = report(source, recipients)
                            assertEquals("[]", step.getJSONObject("result").getJSONArray("recent").toString())
                            compare(step.getJSONObject("result").put("recent", recentBefore), actual, "${case.getString("name")}.$s")
                            results.put(obj("input" to input, "changed" to step.getBoolean("changed"), "result" to typed(actual)))
                        }
                        observed.put(obj("name" to case.getString("name"), "steps" to results))
                        if (c == 4) {
                            val original = typed(report(source, recipients))
                            open(source); click("bulk-select-all"); click("bulk-reference-0"); click("bulk-choose")
                            val script = options(source).items.single { it.name == "Scan Resolution Script" }
                            choose(script.name, script.id); compose.onNodeWithTag("bulk-preview-2").performScrollTo().assertTextContains("Skipped", substring = true)
                            apply(); compose.onNodeWithTag("bulk-preview").performScrollTo(); screenshot("scripts")
                            click("bulk-unload"); apply(); compare(original, typed(report(source, recipients))); close()
                        }
                        if (c == 8) { open(source); compose.onNodeWithTag("bulk-empty").assertExists(); screenshot("empty"); close() }
                        for (id in (listOf(source) + recipients).reversed()) send(BridgeOperation.DeleteFit(id, true), listOf(id))
                    }
                    compare(before, library(), "prior_fits_after_matrix")
                    val ship = create("Vexor", "B05 bulk charges – 探索", listOf(
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.ACTIVE, "Antimatter Charge M"),
                        ModuleSpec("Dual 150mm Railgun I", ModuleState.ACTIVE, "Iron Charge M"),
                        ModuleSpec("200mm Railgun II", ModuleState.OVERHEATED, "Iron Charge M"),
                        ModuleSpec("Sensor Booster II", ModuleState.ACTIVE, "Scan Resolution Script")))
                    send(BridgeOperation.SetFitRestrictions(ship, false), listOf(ship))
                    open(ship); click("bulk-select-all"); click("bulk-reference-0")
                    screenshot("selection")
                    compose.activityRule.scenario.recreate(); sync()
                    assertEquals(setOf(0,1,2,3), picker.selected); assertEquals(0, picker.main)
                    click("bulk-choose")
                    val spike = options(ship).items.single { it.name == "Spike M" }.id
                    val iron = options(ship).items.single { it.name == "Iron Charge M" }.id
                    choose("Spike M", spike)
                    compose.onNodeWithTag("bulk-preview-1").performScrollTo().assertTextContains("Skipped", substring = true)
                    compose.onNodeWithTag("bulk-preview-3").performScrollTo().assertTextContains("Skipped", substring = true)
                    compose.onNodeWithTag("bulk-preview").performScrollTo(); screenshot("mixed")
                    apply()
                    assertEquals(listOf("Spike M", "Iron Charge M", "Spike M", "Scan Resolution Script"), fit(ship).modules.take(4).map { it.charge })
                    click("bulk-back"); click("bulk-reference-1"); click("bulk-choose"); choose("Iron Charge M", iron)
                    compose.onNodeWithTag("bulk-change-count").assertTextEquals("0 modules will change")
                    compose.onNodeWithTag("bulk-apply").assertIsNotEnabled()
                    click("bulk-back"); click("bulk-reference-0"); click("bulk-choose")
                    click("bulk-scope-SIMILAR"); choose("Iron Charge M", iron)
                    compose.onNodeWithTag("bulk-preview").performScrollTo(); screenshot("similar")
                    apply(); assertEquals(listOf("Iron Charge M", "Iron Charge M", "Iron Charge M"), fit(ship).modules.take(3).map { it.charge })
                    click("bulk-scope-SELECTED"); choose("Spike M", spike); apply()
                    val initial = typed(report(ship)); codec = guards(ship)
                    val committed = library(); val priorOptions = allOptions()
                    for ((label, main, selected) in listOf(Triple("vacancy", 4, listOf(4)), Triple("missing_reference", 0, listOf(1)),
                            Triple("duplicate", 0, listOf(0,0)), Triple("negative", -1, listOf(0)), Triple("out_of_range", 999, listOf(0)))) {
                        val result = send(BridgeOperation.SetBulkCharges(ship, main, selected, BulkScope.SELECTED, null), listOf(ship), false)
                        rejections.put(obj("label" to label, "code" to result.error?.code?.name))
                    }
                    val stale = EngineRuntime.request(context, BridgeOperation.SetBulkCharges(ship, 0, listOf(0), BulkScope.SELECTED, null), mapOf(ship to 0L)).get(120, TimeUnit.SECONDS)
                    assertEquals(BridgeErrorCode.REVISION_CONFLICT, stale.error?.code)
                    rejections.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    compare(committed, library()); compare(priorOptions, allOptions())
                    val copy = send(BridgeOperation.DuplicateFit(ship, "B05 independent bulk copy"), listOf(ship)).fits.single { it.name == "B05 independent bulk copy" }.id
                    send(BridgeOperation.SetBulkCharges(copy, 0, listOf(0), BulkScope.SELECTED, null), listOf(copy))
                    compare(initial, typed(report(ship)))
                    // External mutations must not retain a stale module selection.
                    send(BridgeOperation.SetModuleCharge(ship, 0, iron), listOf(ship))
                    waitFor { !picker.loading && picker.options?.revision == fit(ship).revision && picker.selected.isEmpty() }
                    assertNull(picker.main); assertFalse(picker.choosing)
                    send(BridgeOperation.SetModuleCharge(ship, 0, spike), listOf(ship))
                    waitFor { !picker.loading && picker.options?.revision == fit(ship).revision }
                    click("bulk-select-0")
                    EngineRuntime.selectFit(context, copy).get(30, TimeUnit.SECONDS)
                    waitFor { !picker.loading && picker.options?.fitId == copy }
                    assertTrue(picker.selected.isEmpty()); assertNull(picker.main)
                    click("bulk-select-all"); click("bulk-clear"); assertTrue(picker.selected.isEmpty())
                    close()
                    compare(before, typed(array(fits().filter { it.id in originalIds }.map(ModuleTestJson::fit))))
                    compare(recentBefore, array(EngineRuntime.recent.value))
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    EngineRuntime.selectFit(context, ship).get(30, TimeUnit.SECONDS)
                    saved.writeText(obj("fits" to library(), "options" to allOptions(), "prior" to before, "recent" to recentBefore,
                        "active_id" to ship, "new_ids" to array(listOf(ship, copy))).toString(), Charsets.UTF_8)
                }
                "restored" -> {
                    val expected = JSONObject(saved.readText(Charsets.UTF_8))
                    compare(expected.getJSONObject("fits"), library(), "restored_fits", strict = false)
                    compare(expected.getJSONObject("options"), allOptions(), "restored_bulk_types", strict = false)
                    compare(expected.getJSONArray("recent"), array(EngineRuntime.recent.value))
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    val ids = expected.getJSONArray("new_ids")
                    for (i in 0 until ids.length()) {
                        open(ids.getString(i)); click("bulk-select-all")
                        compose.onNodeWithTag("bulk-reference-0").performScrollTo().assertIsDisplayed()
                        if (i == 0) screenshot("restored")
                        close()
                    }
                }
                else -> error("Unknown phase")
            }
            retain(obj("task" to "B05.1", "phase" to phase, "pid" to Process.myPid(), "runtime_start" to runtimeStart,
                "runtime_end" to diagnostics(), "before" to before, "after" to library(), "options" to allOptions(),
                "recent_before" to recentBefore, "recent_after" to array(EngineRuntime.recent.value), "cases" to observed,
                "rejections" to rejections, "codec_rejections" to codec, "saved" to JSONObject(saved.readText(Charsets.UTF_8)),
                "checks" to array(if (phase == "prepare") listOf("complete_matrix", "all_four_recipients", "prior_fits_unchanged",
                    "selection_recreation", "selected_ammo", "asymmetric_skip", "similar_variants", "script_controls",
                    "empty_fit", "clear_selection", "stale_selection_discarded", "fit_switch", "independent_copy",
                    "atomic_rejections", "recent_unchanged", "typed_protocol_guards") else listOf(
                    "fresh_process_restore", "identities_inputs_values_retained", "bulk_types_and_recent_retained", "reopen_each_fit"))), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
