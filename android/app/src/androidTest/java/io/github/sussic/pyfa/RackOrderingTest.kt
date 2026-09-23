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
class RackOrderingTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val picker get() = ViewModelProvider(compose.activity)[RackEditorModel::class.java]
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
    private fun options(id: String) = EngineRuntime.rackOptions(context, id).get(120, TimeUnit.SECONDS)
    private fun allOptions() = typed(array(fits().map { RackTestJson.options(options(it.id)).put("fit_id", it.id).put("revision", it.revision) }))
    private fun library() = typed(array(fits().map(ModuleTestJson::fit)))
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
    private fun report(id: String, recipients: List<String> = emptyList()) = obj(
        "rack" to RackTestJson.options(options(id)), "stats" to ModuleTestJson.stats(fit(id)),
        "recipients" to array(recipients.map { obj("name" to fit(it).name, "stats" to ModuleTestJson.stats(fit(it))) }),
        "recent" to array(EngineRuntime.recent.value))
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b04233-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b04233-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(value.toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        sync(); click("modules-open"); click("modules-arrange")
        waitFor { !picker.loading && picker.options?.fitId == id }
    }
    private fun move(from: Int, to: Int) {
        click("rack-select-$from"); click("rack-move-$to")
        waitFor { !picker.loading && !picker.editing && picker.source == null && picker.error == null }
    }
    private fun guards(id: String): JSONArray {
        val results = JSONArray()
        val raw = EngineRuntime.rackOptionsDiagnostics(context, id).get(120, TimeUnit.SECONDS)
        BridgeCodec.decodeRackOptions(raw)
        fun reject(name: String, pattern: String, replacement: String) {
            val changed = raw.replaceFirst(Regex(pattern), replacement)
            assertNotEquals("Missing guard target: $name", raw, changed)
            try { BridgeCodec.decodeRackOptions(changed); fail("Accepted $name") }
            catch (_: BridgeProtocolException) { results.put(name) }
        }
        reject("decimal_index", "\"index\":\\s*0", "\"index\":0.0")
        reject("decimal_revision", "\"revision\":\\s*${fit(id).revision}", "\"revision\":${fit(id).revision}.0")
        reject("boolean_id", "\"id\":\\s*\\d+", "\"id\":true")
        reject("unknown_slot", "\"slot\":\\s*\"HIGH\"", "\"slot\":\"FICTIONAL\"")
        reject("wrong_heat_unit", "\"unit\":\\s*\"cycles\"", "\"unit\":\"s\"")
        reject("decimal_cycles", "\"cycles\":\\s*\\{\\s*\"unit\":\\s*\"cycles\",\\s*\"value\":\\s*\\d+", "\"cycles\":{\"unit\":\"cycles\",\"value\":1.0")
        reject("integer_seconds", "\"seconds\":\\s*\\{\\s*\"unit\":\\s*\"s\",\\s*\"value\":\\s*[0-9.Ee+-]+", "\"seconds\":{\"unit\":\"s\",\"value\":1")
        reject("integer_sample_time", "\"seconds\":\\s*1\\.0", "\"seconds\":1")
        reject("probability_out_of_range", "\"unit\":\\s*\"probability\",\\s*\"value\":\\s*[0-9.Ee+-]+", "\"unit\":\"probability\",\"value\":1.1")
        reject("extra_field", "\\{", "{\"extra\":1,")
        return results
    }

    @Test fun rackPositionsAndDesktopHeatSurviveRestartOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b04233_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val fixture = JSONObject(InstrumentationRegistry.getInstrumentation().context.assets.open("rack-ordering-expected.json")
            .bufferedReader().use { it.readText() })
        val before = library(); val recentBefore = array(EngineRuntime.recent.value); val runtimeStart = diagnostics()
        compare(ModuleTestJson.numericKinds(fixture.getJSONObject("eos_settings")), runtimeStart.getJSONObject("eos_settings_numeric_types"))
        val observed = JSONArray(); val rejections = JSONArray(); var codec = JSONArray()
        val saved = File(context.noBackupFilesDir, "b04233-test-expected.json")
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
                            if (input != null) send(BridgeOperation.SwapModules(source, input.getInt("from_position"), input.getInt("to_position")), listOf(source))
                            val actual = report(source, recipients)
                            assertEquals("[]", step.getJSONObject("result").getJSONArray("recent").toString())
                            compare(step.getJSONObject("result").put("recent", recentBefore), actual, "${case.getString("name")}.$s")
                            results.put(obj("input" to input, "changed" to step.getBoolean("changed"), "result" to typed(actual)))
                        }
                        observed.put(obj("name" to case.getString("name"), "steps" to results))
                        if (c == 2 || c == 5) {
                            val rack = if (c == 2) ModuleSlot.MED else ModuleSlot.SERVICE
                            val original = typed(report(source, recipients))
                            open(source); click("rack-slot-${rack.name}")
                            val occupied = options(source).modules.filter { it.slot == rack && it.id != null }
                            move(occupied[0].index, occupied[1].index)
                            compose.onNodeWithTag("rack-module-${occupied[0].index}").performScrollTo()
                            screenshot(if (c == 2) "medium" else "service")
                            move(occupied[0].index, occupied[1].index)
                            compare(original, typed(report(source, recipients)))
                            click("rack-back"); click("modules-back")
                        }
                        for (id in (listOf(source) + recipients).reversed()) send(BridgeOperation.DeleteFit(id, true), listOf(id))
                    }
                    compare(before, library(), "prior_fits_after_matrix")
                    val ship = create("Vexor", "B04 rack order – 探索", listOf(
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.OVERHEATED, "Spike M"),
                        ModuleSpec("200mm Railgun II", ModuleState.ACTIVE, "Antimatter Charge M"),
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.OVERHEATED, "Antimatter Charge M")))
                    send(BridgeOperation.SetFitRestrictions(ship, false), listOf(ship))
                    open(ship)
                    val initial = typed(report(ship))
                    compose.onNodeWithTag("rack-heat-0").performScrollTo(); screenshot("initial")
                    click("rack-select-0"); compose.onNodeWithTag("rack-move-0").assertIsNotEnabled()
                    compose.activityRule.scenario.recreate(); sync(); assertEquals(0, picker.source)
                    click("rack-move-1"); waitFor { !picker.loading && !picker.editing && picker.source == null && picker.error == null }
                    assertEquals("Spike M", fit(ship).modules[1].charge)
                    assertEquals(ModuleState.OVERHEATED, fit(ship).modules[1].state)
                    assertEquals("200mm Railgun II", fit(ship).modules[0].name)
                    compose.onNodeWithTag("rack-heat-1").performScrollTo(); screenshot("swapped")
                    val vacancy = options(ship).modules.first { it.slot == ModuleSlot.HIGH && it.id == null }.index
                    move(1, vacancy); assertNull(fit(ship).modules[1].name)
                    assertEquals("Spike M", fit(ship).modules[vacancy].charge)
                    compose.onNodeWithTag("rack-heat-$vacancy").performScrollTo(); screenshot("vacant")
                    move(vacancy, 1); move(1, 0); compare(initial, typed(report(ship)))
                    click("rack-select-0"); click("rack-back"); assertNull(picker.source)
                    click("rack-slot-MED"); compose.onNodeWithTag("rack-empty").assertExists(); screenshot("empty")
                    click("rack-slot-HIGH")
                    codec = guards(ship)
                    val committed = library(); val priorOptions = allOptions()
                    val cross = options(ship).modules.first { it.slot == ModuleSlot.MED }.index
                    for ((label, from, to) in listOf(Triple("empty_source", vacancy, 0), Triple("cross_rack", 0, cross),
                            Triple("negative", -1, 0), Triple("out_of_range", 0, Int.MAX_VALUE))) {
                        val result = send(BridgeOperation.SwapModules(ship, from, to), listOf(ship), false)
                        rejections.put(obj("label" to label, "code" to result.error?.code?.name))
                    }
                    val stale = EngineRuntime.request(context, BridgeOperation.SwapModules(ship, 0, 1), mapOf(ship to 0L)).get(120, TimeUnit.SECONDS)
                    assertEquals(BridgeErrorCode.REVISION_CONFLICT, stale.error?.code)
                    rejections.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    compare(committed, library()); compare(priorOptions, allOptions())
                    val copy = send(BridgeOperation.DuplicateFit(ship, "B04 independent rack copy"), listOf(ship)).fits.single { it.name == "B04 independent rack copy" }.id
                    send(BridgeOperation.SwapModules(copy, 0, vacancy), listOf(copy)); compare(initial, typed(report(ship)))
                    // An external edit while a source is selected must discard the stale selection.
                    click("rack-select-0")
                    send(BridgeOperation.SwapModules(ship, 0, 1), listOf(ship))
                    waitFor { !picker.loading && picker.options?.revision == fit(ship).revision && picker.source == null }
                    move(1, 0)
                    EngineRuntime.selectFit(context, copy).get(30, TimeUnit.SECONDS)
                    waitFor { !picker.loading && picker.options?.fitId == copy }
                    assertNull(picker.source)
                    click("rack-back"); click("modules-back")
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
                    compare(expected.getJSONObject("options"), allOptions(), "restored_heat_types", strict = false)
                    compare(expected.getJSONArray("recent"), array(EngineRuntime.recent.value))
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    val ids = expected.getJSONArray("new_ids")
                    for (i in 0 until ids.length()) {
                        open(ids.getString(i)); val position = options(ids.getString(i)).modules.first { it.heat != null }.index
                        compose.onNodeWithTag("rack-heat-$position").performScrollTo().assertIsDisplayed()
                        if (i == 0) screenshot("restored")
                        click("rack-back"); click("modules-back")
                    }
                }
                else -> error("Unknown phase")
            }
            retain(obj("task" to "B04.2.3.3", "phase" to phase, "pid" to Process.myPid(), "runtime_start" to runtimeStart,
                "runtime_end" to diagnostics(), "before" to before, "after" to library(), "options" to allOptions(),
                "recent_before" to recentBefore, "recent_after" to array(EngineRuntime.recent.value), "cases" to observed,
                "rejections" to rejections, "codec_rejections" to codec, "saved" to JSONObject(saved.readText(Charsets.UTF_8)),
                "checks" to array(if (phase == "prepare") listOf("complete_matrix", "all_four_recipients", "prior_fits_unchanged",
                    "selection_recreation", "occupied_swap", "vacant_move", "states_charges_retained", "positional_heat",
                    "medium_and_service_controls", "cancel_selection", "empty_rack", "stale_selection_discarded", "fit_switch", "independent_copy",
                    "atomic_rejections", "recent_unchanged", "typed_protocol_guards") else listOf(
                    "fresh_process_restore", "identities_inputs_values_retained", "heat_types_and_recent_retained", "reopen_each_fit"))), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
