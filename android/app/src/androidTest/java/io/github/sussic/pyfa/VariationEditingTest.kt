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
class VariationEditingTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val picker get() = ViewModelProvider(compose.activity)[VariationEditorModel::class.java]
    private fun fits() = EngineRuntime.library.value
    private fun fit(id: String) = fits().single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun waitFor(predicate: () -> Boolean) { compose.waitUntil(60_000, predicate); sync() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick(); sync() }
    private fun edit(text: String) { compose.onNodeWithTag("variations-search").performScrollTo().performTextReplacement(text); sync() }
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList(), ok: Boolean = true): BridgeResponse {
        val response = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
        assertEquals(response.error?.message, ok, response.isSuccess)
        return response
    }
    private fun create(ship: String, name: String, modules: List<ModuleSpec> = emptyList(), drones: List<DroneSpec> = emptyList()): String =
        send(BridgeOperation.CreateFit(FitSpec(name, ship, 5, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
            Security(SystemSecurity.HISEC, 0.0), modules, drones))).fits.single().id
    private fun options(id: String) = EngineRuntime.variationOptions(context, id).get(120, TimeUnit.SECONDS)
    private fun allOptions() = array(fits().map { VariationTestJson.options(options(it.id)).put("fit_id", it.id).put("revision", it.revision) })
    private fun library() = typed(array(fits().map(ModuleTestJson::fit)))
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
    private fun report(id: String, recipients: List<String> = emptyList()): JSONObject {
        val additions = JSONObject(EngineRuntime.variationAdditionDiagnostics(context, id).get(120, TimeUnit.SECONDS))
        return obj("options" to VariationTestJson.options(options(id)), "stats" to ModuleTestJson.stats(fit(id)),
            "modules" to JSONArray(EngineRuntime.chargeModuleDiagnostics(context, id).get(120, TimeUnit.SECONDS)),
            "drones" to additions.getJSONArray("drones"), "implants" to additions.getJSONArray("implants"),
            "implant_location" to additions.getString("implant_location"),
            "recipients" to array(recipients.map { obj("name" to fit(it).name, "stats" to ModuleTestJson.stats(fit(it))) }),
            "recent" to array(EngineRuntime.recent.value))
    }
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b04232-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b04232-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(value.toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        sync(); click("variations-open")
        waitFor { !picker.loading && picker.options?.fitId == id }
    }
    private fun target(kind: VariationContext, position: Int) {
        click("variations-context-${kind.wire}"); click("variation-target-${kind.wire}-$position")
    }
    private fun choose(name: String, id: Int) { edit(name); click("variation-item-$id"); click("variation-apply")
        waitFor { !picker.loading && !picker.editing && picker.error == null && picker.position == null }
    }
    private fun guards(id: String): JSONArray {
        val results = JSONArray()
        val base = VariationTestJson.options(options(id)).put("version", 1).put("fit_id", id).put("revision", fit(id).revision)
        fun reject(name: String, mutate: (JSONObject) -> Unit) {
            val changed = JSONObject(base.toString()); mutate(changed)
            try { BridgeCodec.decodeVariationOptions(changed.toString()); fail("Accepted $name") }
            catch (_: BridgeProtocolException) { results.put(name) }
        }
        val raw = base.toString()
        for ((label, from, to) in listOf(Triple("decimal_index", "\"index\":0", "\"index\":0.0"),
                Triple("decimal_revision", "\"revision\":${fit(id).revision}", "\"revision\":${fit(id).revision}.0"))) {
            val malformed = raw.replaceFirst(from, to); assertNotEquals(raw, malformed)
            try { BridgeCodec.decodeVariationOptions(malformed); fail("Accepted $label") }
            catch (_: BridgeProtocolException) { results.put(label) }
        }
        fun first(value: JSONObject) = value.getJSONArray("targets").getJSONObject(0)
        reject("boolean_id") { first(it).put("item_id", true) }
        reject("unknown_context") { first(it).put("context", "cargo") }
        reject("missing_targets") { it.remove("targets") }
        reject("extra_field") { it.put("extra", 1) }
        reject("duplicate_target") { it.getJSONArray("targets").put(first(it)) }
        reject("duplicate_choice") { first(it).getJSONArray("choices").put(first(it).getJSONArray("choices").getJSONObject(0)) }
        reject("nonboolean_enablement") { first(it).getJSONArray("choices").getJSONObject(0).put("enabled", 1) }
        reject("invalid_state") { first(it).getJSONObject("current").put("state", "FICTIONAL") }
        reject("wrong_current_fields") { first(it).getJSONObject("current").put("amount", 5) }
        reject("drone_active_exceeds_total") { value ->
            val rows = value.getJSONArray("targets")
            (0 until rows.length()).map { rows.getJSONObject(it) }.first { it.getString("context") == "drone" }
                .getJSONObject("current").put("active", Int.MAX_VALUE)
        }
        reject("unsupported_implant_location") { value ->
            val rows = value.getJSONArray("targets")
            (0 until rows.length()).map { rows.getJSONObject(it) }.first { it.getString("context") == "implant" }
                .getJSONObject("current").put("location", "CHARACTER")
        }
        return results
    }

    @Test fun fittedAndAdditionVariationsSurviveRestartOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b04232_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val fixture = JSONObject(InstrumentationRegistry.getInstrumentation().context.assets.open("variation-edits-expected.json")
            .bufferedReader().use { it.readText() })
        val catalogue = EngineRuntime.equipmentCatalog(context).get(120, TimeUnit.SECONDS)
        fun item(name: String) = catalogue.items.single { it.name == name }.id
        val before = library(); val recentBefore = array(EngineRuntime.recent.value); val runtimeStart = diagnostics()
        compare(ModuleTestJson.numericKinds(fixture.getJSONObject("eos_settings")), runtimeStart.getJSONObject("eos_settings_numeric_types"))
        val observed = JSONArray(); val families = JSONArray(); val rejections = JSONArray(); var codec = JSONArray()
        val saved = File(context.noBackupFilesDir, "b04232-test-expected.json")
        try {
            when (phase) {
                "prepare" -> {
                    val originalIds = fits().map { it.id }.toSet()
                    val cases = fixture.getJSONArray("cases")
                    for (c in 0 until cases.length()) {
                        val case = cases.getJSONObject(c); val initial = case.getJSONArray("modules")
                        val drones = case.optJSONArray("drones") ?: JSONArray()
                        val source = create(case.getString("ship"), case.getString("name"), (0 until initial.length()).map { i ->
                            initial.getJSONObject(i).let { ModuleSpec(it.getString("name"), ModuleState.valueOf(it.getString("state")),
                                if (it.has("charge") && !it.isNull("charge")) it.getString("charge") else null) } },
                            (0 until drones.length()).map { i -> drones.getJSONObject(i).let { DroneSpec(it.getString("name"), it.getInt("amount"), it.getInt("active")) } })
                        val implants = case.optJSONArray("implants") ?: JSONArray()
                        for (i in 0 until implants.length()) implants.getJSONObject(i).let {
                            send(BridgeOperation.AddImplant(source, it.getString("name"), it.getBoolean("active")), listOf(source)) }
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
                            if (input != null) {
                                val kind = VariationContext.entries.single { it.wire == input.getString("context") }
                                val position = input.getInt("position"); val identity = input.getInt("item_id")
                                val same = options(source).targets.single { it.context == kind && it.index == position }.itemId == identity
                                val committed = library(); val priorOptions = allOptions()
                                val result = send(BridgeOperation.ChangeVariation(source, kind, position, identity), listOf(source), step.getBoolean("changed") || same)
                                if (!result.isSuccess) { compare(committed, library()); compare(priorOptions, allOptions()) }
                            }
                            val actual = report(source, recipients)
                            assertEquals("[]", step.getJSONObject("result").getJSONArray("recent").toString())
                            compare(step.getJSONObject("result").put("recent", recentBefore), actual, "${case.getString("name")}.$s")
                            results.put(obj("input" to input, "changed" to step.getBoolean("changed"), "result" to typed(actual)))
                        }
                        observed.put(obj("name" to case.getString("name"), "steps" to results))
                        for (id in (listOf(source) + recipients).reversed()) send(BridgeOperation.DeleteFit(id, true), listOf(id))
                    }
                    compare(before, library(), "prior_fits_after_matrix")
                    val probe = create("Rifter", "Complete native family probe")
                    EngineRuntime.variationFamiliesDiagnostics(context, probe).get(360, TimeUnit.SECONDS).forEach {
                        families.put(obj("id" to it.id, "context" to it.context.wire, "choices" to array(it.choices.map(VariationTestJson::choice)))) }
                    compare(fixture.getJSONArray("families"), families, "complete_5226_families"); assertEquals(5226, families.length())
                    send(BridgeOperation.DeleteFit(probe, true), listOf(probe)); compare(before, library())

                    val ship = create("Vexor", "B04 variations – 探索", listOf(
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.ACTIVE, "Spike M"),
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.OVERHEATED, "Antimatter Charge M"),
                        ModuleSpec("Prototype Cloaking Device I", ModuleState.ONLINE)), listOf(
                        DroneSpec("Hobgoblin I", 5, 3), DroneSpec("Hobgoblin II", 4, 0)))
                    send(BridgeOperation.AddImplant(ship, "Eifyr and Co. 'Rogue' Navigation NN-601", false), listOf(ship))
                    open(ship); target(VariationContext.MODULE, 0)
                    compose.onNodeWithTag("variations-current").performScrollTo(); screenshot("module")
                    edit("Dual 150mm Railgun I"); click("variation-item-${item("Dual 150mm Railgun I")}")
                    compose.activityRule.scenario.recreate(); sync()
                    assertEquals(0, picker.position); assertEquals(item("Dual 150mm Railgun I"), picker.selected)
                    assertEquals("Dual 150mm Railgun I", picker.query)
                    click("variation-apply"); waitFor { !picker.loading && !picker.editing && picker.position == null }
                    assertEquals("Dual 150mm Railgun I", fit(ship).modules[0].name); assertNull(fit(ship).modules[0].charge)
                    assertEquals("Antimatter Charge M", fit(ship).modules[1].charge); assertEquals(ModuleState.OVERHEATED, fit(ship).modules[1].state)
                    compose.onNodeWithTag("variations-saved").performScrollTo(); screenshot("unloaded")
                    target(VariationContext.DRONE, 0); assertTrue(picker.options!!.targets.first { it.context == VariationContext.DRONE }.choices.size > 20)
                    click("variations-next"); assertEquals(1, picker.page); screenshot("drone-picker")
                    edit("zz-no-such-variation"); compose.onNodeWithTag("variations-empty").assertExists()
                    choose("Hobgoblin II", item("Hobgoblin II"))
                    val stacks = options(ship).targets.filter { it.context == VariationContext.DRONE }
                    assertEquals(listOf(VariationInput.Drone(4, 0), VariationInput.Drone(5, 3)), stacks.map { it.current })
                    assertEquals(listOf(item("Hobgoblin II"), item("Hobgoblin II")), stacks.map { it.itemId })
                    compose.onNodeWithTag("variation-target-drone-1").performScrollTo(); screenshot("drone")
                    target(VariationContext.IMPLANT, 0)
                    choose("Eifyr and Co. 'Rogue' Navigation NN-605", item("Eifyr and Co. 'Rogue' Navigation NN-605"))
                    assertEquals(VariationInput.Implant(6, false, "FIT"), options(ship).targets.single { it.context == VariationContext.IMPLANT }.current)
                    send(BridgeOperation.AddImplant(ship, "Genolution Core Augmentation CA-1", false), listOf(ship))
                    send(BridgeOperation.AddImplant(ship, "Genolution Core Augmentation CA-2", true), listOf(ship))
                    waitFor { !picker.loading && picker.options?.revision == fit(ship).revision }
                    target(VariationContext.IMPLANT, 1)
                    choose("Genolution Core Augmentation CA-3", item("Genolution Core Augmentation CA-3"))
                    assertEquals(4, options(ship).targets.count { it.context == VariationContext.IMPLANT })
                    compose.onNodeWithTag("variation-target-implant-0").performScrollTo(); screenshot("implant")
                    target(VariationContext.MODULE, 2)
                    edit("Covert Ops Cloaking Device II")
                    compose.onNodeWithTag("variation-item-${item("Covert Ops Cloaking Device II")}").assertIsNotEnabled()
                    screenshot("disabled"); click("variations-back")
                    codec = guards(ship)
                    val committed = library(); val priorOptions = allOptions()
                    for ((label, position, identity) in listOf(Triple("wrong_family", 0, item("Hobgoblin II")),
                            Triple("disabled_hull", 2, item("Covert Ops Cloaking Device II")), Triple("unknown", 0, Int.MAX_VALUE))) {
                        val result = send(BridgeOperation.ChangeVariation(ship, VariationContext.MODULE, position, identity), listOf(ship), false)
                        rejections.put(obj("label" to label, "code" to result.error?.code?.name))
                    }
                    val stale = EngineRuntime.request(context, BridgeOperation.ChangeVariation(ship, VariationContext.MODULE, 0,
                        item("Dual 150mm Railgun II")), mapOf(ship to 0L)).get(120, TimeUnit.SECONDS)
                    assertEquals(BridgeErrorCode.REVISION_CONFLICT, stale.error?.code)
                    rejections.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    compare(committed, library()); compare(priorOptions, allOptions())
                    val sourceReport = typed(report(ship))
                    val copy = send(BridgeOperation.DuplicateFit(ship, "B04 independent variation copy"), listOf(ship)).fits.single { it.name == "B04 independent variation copy" }.id
                    for ((kind, position, name) in listOf(Triple(VariationContext.MODULE, 0, "Dual 150mm Railgun II"),
                            Triple(VariationContext.DRONE, 1, "Hobgoblin I"), Triple(VariationContext.IMPLANT, 0, "Eifyr and Co. 'Rogue' Navigation NN-601")))
                        send(BridgeOperation.ChangeVariation(copy, kind, position, item(name)), listOf(copy))
                    compare(sourceReport, typed(report(ship)))
                    val empty = fits().first { it.id in originalIds && it.modules.none { mod -> mod.name != null } }
                    EngineRuntime.selectFit(context, empty.id).get(30, TimeUnit.SECONDS)
                    waitFor { !picker.loading && picker.options?.fitId == empty.id }
                    assertTrue(picker.options!!.targets.isEmpty()); compose.onNodeWithTag("variations-empty").performScrollTo(); screenshot("empty")
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
                    compare(expected.getJSONArray("options"), allOptions()); compare(expected.getJSONArray("recent"), array(EngineRuntime.recent.value))
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    val ids = expected.getJSONArray("new_ids")
                    for (i in 0 until ids.length()) {
                        open(ids.getString(i)); target(VariationContext.DRONE, 1)
                        compose.onNodeWithTag("variations-current").assertExists()
                        if (i == 0) { compose.onNodeWithTag("variations-current").performScrollTo(); screenshot("restored") }
                        click("variations-back"); click("variations-back")
                    }
                }
                else -> error("Unknown phase")
            }
            retain(obj("task" to "B04.2.3.2", "phase" to phase, "pid" to Process.myPid(), "runtime_start" to runtimeStart,
                "runtime_end" to diagnostics(), "before" to before, "after" to library(), "options" to allOptions(),
                "recent_before" to recentBefore, "recent_after" to array(EngineRuntime.recent.value), "cases" to observed,
                "families" to families, "rejections" to rejections, "codec_rejections" to codec,
                "saved" to JSONObject(saved.readText(Charsets.UTF_8)), "checks" to array(if (phase == "prepare") listOf(
                    "complete_matrix", "all_5226_families", "all_six_recipients", "prior_fits_unchanged", "picker_recreation",
                    "charge_reconciliation", "neighbour_retained", "drone_pagination_search", "distinct_stacks_quantities_order",
                    "implant_activation_location", "disabled_choices", "empty_fit_refresh", "independent_copy", "atomic_rejections",
                    "recent_unchanged", "typed_protocol_guards") else listOf(
                    "fresh_process_restore", "identities_inputs_values_retained", "options_and_recent_retained", "reopen_each_fit"))), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
