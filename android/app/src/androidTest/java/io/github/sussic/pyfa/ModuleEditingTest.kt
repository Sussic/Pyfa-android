package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.os.Process
import android.provider.Settings
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
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
class ModuleEditingTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val editor get() = ViewModelProvider(compose.activity)[ModuleEditorModel::class.java]
    private val equipment get() = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
    private fun fits() = EngineRuntime.library.value
    private fun fit(id: String) = fits().single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun waitFor(predicate: () -> Boolean) { compose.waitUntil(30_000, predicate); sync() }
    private fun click(tag: String) {
        sync()
        val node = compose.onNodeWithTag(tag)
        if (tag != "modules-restrictions-confirm") node.performScrollTo()
        node.assertIsDisplayed().performClick(); sync()
    }
    private fun edit(tag: String, value: String) {
        compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value); sync()
    }
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList(), ok: Boolean? = true): BridgeResponse {
        val response = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
        if (ok != null) assertEquals(response.error?.message, ok, response.isSuccess)
        if (!response.isSuccess) assertEquals(BridgeErrorCode.INVALID_EDIT, response.error?.code)
        return response
    }
    private fun create(ship: String, name: String, skills: Int = 5, modules: List<ModuleSpec> = emptyList()): String =
        send(BridgeOperation.CreateFit(FitSpec(name, ship, skills, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
            Security(SystemSecurity.HISEC, 0.0), modules, emptyList()))).fits.single().id
    private fun details(id: String) = EngineRuntime.fittingDetails(context, id).get(120, TimeUnit.SECONDS)
    private fun library() = typed(array(fits().map(ModuleTestJson::fit)))
    private fun allDetails() = typed(array(fits().map { fit -> ModuleTestJson.details(details(fit.id))
        .put("fit_id", fit.id).put("revision", fit.revision) }))
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS)).also {
        // Preserve the original diagnostic wire kinds before JSONObject's writer
        // normalizes whole-number decimals (for example 1.0) into integers.
        it.put("eos_settings_numeric_types", ModuleTestJson.numericKinds(it.getJSONObject("eos_settings")))
    }
    private fun report(id: String, recipients: List<String>): JSONObject = ModuleTestJson.details(details(id))
        .put("stats", ModuleTestJson.stats(fit(id))).put("recent", array(EngineRuntime.recent.value))
        .put("recipients", array(recipients.map { obj("name" to fit(it).name, "stats" to ModuleTestJson.stats(fit(it))) }))
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b0422-$name.png")).use { it.readBytes() }
    }
    private fun retain(report: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b0422-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(report.toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
    private fun useThroughBrowser(name: String, id: Int) {
        edit("equipment-search", name)
        click("equipment-search-submit")
        waitFor { !equipment.busy && equipment.searched == name }
        click("equipment-item-$id")
        waitFor { !editor.loading && editor.details != null }
        val before = fit(editor.details!!.fitId).revision
        click("equipment-fit")
        waitFor { !editor.editing && !editor.loading && editor.error == null && editor.details?.revision == before + 1 }
        click("equipment-view-fit")
    }

    private fun protocolGuards(id: String): JSONArray {
        val observed = JSONArray()
        fun reject(label: String, action: () -> Unit) {
            try { action(); fail("Accepted malformed $label") }
            catch (_: BridgeProtocolException) { observed.put(label) }
        }
        val detail = details(id)
        val raw = ModuleTestJson.details(detail).put("version", 1).put("fit_id", id).put("revision", detail.revision)
        fun malformed(label: String, change: (JSONObject) -> Unit) {
            val value = JSONObject(raw.toString()); change(value)
            reject(label) { BridgeCodec.decodeFitting(value.toString()) }
        }
        malformed("resource_boolean") { it.getJSONObject("resources").getJSONObject("cpu").put("used", true) }
        malformed("missing_resource_unit") { it.getJSONObject("resources").getJSONObject("cpu").remove("unit") }
        malformed("wrong_resource_unit") { it.getJSONObject("resources").getJSONObject("powergrid").put("unit", "tf") }
        malformed("vacancy_with_identity") { it.getJSONArray("modules").getJSONObject(0).put("id", 2048) }
        malformed("vacancy_with_legality") { it.getJSONArray("modules").getJSONObject(0).put("legal", true) }
        malformed("noncontiguous_position") { it.getJSONArray("modules").getJSONObject(0).put("index", 99) }
        malformed("missing_slot_totals") { it.getJSONArray("slots").remove(0) }
        val envelope = obj("version" to 1, "request_id" to "vacancy-check", "session_id" to "synthetic-session",
            "status" to "ok", "fits" to array(listOf(ModuleTestJson.fit(fit(id)))), "error" to null)
        reject("unknown_vacancy_slot") {
            val value = JSONObject(envelope.toString())
            value.getJSONArray("fits").getJSONObject(0).getJSONArray("modules").getJSONObject(0).put("empty_slot", "UNKNOWN")
            BridgeCodec.decodeResponse(value.toString())
        }
        reject("mixed_vacant_fitted_shape") {
            val value = JSONObject(envelope.toString())
            value.getJSONArray("fits").getJSONObject(0).getJSONArray("modules").getJSONObject(0).put("name", "Invented module")
            BridgeCodec.decodeResponse(value.toString())
        }
        for ((label, value) in listOf("recent_boolean_id" to "[true]", "recent_decimal_id" to "[1.0]",
                "recent_duplicate" to "[1,1]", "recent_over_limit" to (1..21).joinToString(prefix = "[", postfix = "]"))) {
            reject(label) { BridgeCodec.decodeRecent("{\"version\":1,\"item_ids\":$value}") }
        }
        return observed
    }

    @Test fun moduleEditsAndRecentUseSurviveRestartOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b0422_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val fixture = JSONObject(InstrumentationRegistry.getInstrumentation().context.assets.open("module-edits-expected.json")
            .bufferedReader().use { it.readText() })
        val catalogue = EngineRuntime.equipmentCatalog(context).get(120, TimeUnit.SECONDS)
        fun item(name: String) = catalogue.items.single { it.name == name }.id
        val before = library()
        val runtimeStart = diagnostics()
        val observed = JSONArray()
        val defaults = JSONArray()
        val history = JSONArray()
        val rejections = JSONArray()
        var codecRejections = JSONArray()
        val saved = File(context.noBackupFilesDir, "b0422-test-expected.json")
        try {
            when (phase) {
                "prepare" -> {
                    assertTrue(EngineRuntime.recent.value.isEmpty())
                    val originalIds = fits().map { it.id }.toSet()
                    val cases = fixture.getJSONArray("cases")
                    for (c in 0 until cases.length()) {
                        val case = cases.getJSONObject(c)
                        val initial = case.getJSONArray("initial_modules")
                        val modules = (0 until initial.length()).map { i -> initial.getJSONObject(i).let {
                            ModuleSpec(it.getString("name"), ModuleState.valueOf(it.getString("state")),
                                if (it.has("charge") && !it.isNull("charge")) it.getString("charge") else null) } }
                        val source = create(case.getString("ship"), case.getString("name"), case.getInt("skill_level"), modules)
                        send(BridgeOperation.SetFitRestrictions(source, false), listOf(source))
                        val recipients = mutableListOf<String>()
                        val targets = case.getJSONArray("recipients")
                        for (i in 0 until targets.length()) {
                            val target = targets.getJSONObject(i)
                            val id = create(target.getString("ship"), target.getString("name"))
                            send(BridgeOperation.SetFitRestrictions(id, false), listOf(id))
                            send(BridgeOperation.AddProjection(source, id, 0.0), listOf(source, id))
                            recipients += id
                        }
                        val steps = case.getJSONArray("steps")
                        val results = JSONArray()
                        for (s in 0 until steps.length()) {
                            val step = steps.getJSONObject(s)
                            val input = if (step.isNull("input")) null else step.getJSONArray("input")
                            if (input != null) {
                                val committed = library()
                                val operation = when (input.getString(0)) {
                                    "add" -> BridgeOperation.AddModule(source, item(input.getString(1)))
                                    "replace" -> BridgeOperation.ReplaceModule(source, input.getInt(1), item(input.getString(2)))
                                    "remove" -> BridgeOperation.RemoveModule(source, input.getInt(1))
                                    "restrictions" -> BridgeOperation.SetFitRestrictions(source, input.getBoolean(1))
                                    else -> error("Unknown reference operation")
                                }
                                send(operation, listOf(source), step.getBoolean("accepted"))
                                if (!step.getBoolean("accepted")) compare(committed, library(), "failed_fit_unchanged")
                            }
                            val actual = report(source, recipients)
                            compare(step.getJSONObject("result"), actual, "${case.getString("name")}.$s")
                            results.put(obj("input" to input, "accepted" to step.getBoolean("accepted"), "result" to typed(actual)))
                        }
                        observed.put(obj("name" to case.getString("name"), "steps" to results))
                        for (id in (listOf(source) + recipients).reversed()) send(BridgeOperation.DeleteFit(id, true), listOf(id))
                    }
                    compare(before, library(), "prior_fits_after_matrix")
                    val revisionBeforeDefaults = library()
                    val recentBeforeDefaults = EngineRuntime.recent.value
                    val actualDefaults = EngineRuntime.moduleDefaultsDiagnostics(context).get(120, TimeUnit.SECONDS)
                    assertEquals(4242, actualDefaults.size)
                    actualDefaults.forEach { defaults.put(obj("id" to it.id, "name" to it.name,
                        "slot" to it.slot.name, "state" to it.state.name, "limit" to it.limit.name)) }
                    compare(fixture.getJSONArray("default_states"), defaults, "all_module_default_states")
                    compare(revisionBeforeDefaults, library(), "defaults_read_only")
                    assertEquals(recentBeforeDefaults, EngineRuntime.recent.value)

                    val ship = create("Rifter", "B04 module editor Rifter", 0)
                    EngineRuntime.selectFit(context, ship).get(30, TimeUnit.SECONDS)
                    sync(); click("modules-open")
                    waitFor { !editor.loading && editor.details?.fitId == ship }
                    click("modules-add")
                    useThroughBrowser("200mm AutoCannon II", item("200mm AutoCannon II"))
                    val beforeGuards = library()
                    codecRejections = protocolGuards(ship)
                    compare(beforeGuards, library(), "protocol_guards_are_read_only")
                    click("module-replace-7")
                    edit("equipment-search", "150mm Light AutoCannon II")
                    click("equipment-search-submit")
                    waitFor { !equipment.busy }
                    click("equipment-item-${item("150mm Light AutoCannon II")}")
                    compose.activityRule.scenario.recreate(); sync()
                    assertEquals(7, editor.replacePosition)
                    assertEquals(item("150mm Light AutoCannon II"), equipment.selectedId)
                    waitFor { !editor.loading }
                    click("equipment-fit")
                    waitFor { !editor.editing && !editor.loading && fit(ship).modules[7].name == "150mm Light AutoCannon II" }
                    click("equipment-view-fit")
                    compose.onNodeWithTag("module-7").performScrollTo(); screenshot("rack")
                    click("module-remove-7")
                    waitFor { !editor.editing && !editor.loading && fit(ship).modules[7].emptySlot == ModuleSlot.HIGH }
                    click("module-replace-7")
                    useThroughBrowser("200mm AutoCannon II", item("200mm AutoCannon II"))
                    click("modules-add"); useThroughBrowser("Small Projectile Burst Aerator II", item("Small Projectile Burst Aerator II"))
                    click("modules-add"); useThroughBrowser("Large Shield Extender II", item("Large Shield Extender II"))
                    assertTrue(details(ship).resources.getValue("powergrid").overloaded)
                    compose.onNodeWithTag("modules-resources").performScrollTo(); screenshot("resources")
                    click("modules-skills")
                    assertTrue(editor.showSkills && details(ship).skillWarnings.isNotEmpty())
                    compose.onNodeWithTag("modules-skills").performScrollTo(); screenshot("skills")
                    click("modules-restrictions")
                    compose.activityRule.scenario.recreate(); sync()
                    assertTrue(editor.confirmRestrictions)
                    click("modules-restrictions-confirm")
                    waitFor { !editor.editing && !editor.loading && editor.details?.ignoreRestrictions == true }
                    click("modules-add"); useThroughBrowser("Capital Armor Repairer I", item("Capital Armor Repairer I"))
                    click("modules-rack-LOW")
                    compose.onNodeWithTag("module-0").performScrollTo(); screenshot("override")
                    click("modules-restrictions"); click("modules-restrictions-confirm")
                    waitFor { !editor.editing && !editor.loading && editor.details?.ignoreRestrictions == false }
                    assertFalse(fit(ship).modules.any { it.name == "Capital Armor Repairer I" })
                    assertTrue(fit(ship).modules.any { it.name == "Large Shield Extender II" })
                    val sourceBeforeCopy = ModuleTestJson.fit(fit(ship))
                    val copy = send(BridgeOperation.DuplicateFit(ship, "B04 independent module copy"), listOf(ship)).fits
                        .single { it.name == "B04 independent module copy" }.id
                    send(BridgeOperation.RemoveModule(copy, 7), listOf(copy))
                    compare(sourceBeforeCopy, ModuleTestJson.fit(fit(ship)), "copy_independent")
                    val structure = create("Astrahus", "B04 module editor Astrahus")
                    EngineRuntime.selectFit(context, structure).get(30, TimeUnit.SECONDS)
                    waitFor { !editor.loading && editor.details?.fitId == structure }
                    click("modules-add"); useThroughBrowser("Standup Manufacturing Plant I", item("Standup Manufacturing Plant I"))
                    click("modules-rack-SERVICE")
                    click("module-replace-14"); useThroughBrowser("Standup Research Lab I", item("Standup Research Lab I"))
                    compose.onNodeWithTag("module-14").performScrollTo(); screenshot("service")

                    val historyFit = create("Rifter", "Disposable recent-use attempts")
                    val referenceHistory = fixture.getJSONArray("recent_history")
                    for (i in 0 until referenceHistory.length()) {
                        val row = referenceHistory.getJSONObject(i)
                        val response = send(BridgeOperation.AddModule(historyFit, row.getInt("id")), listOf(historyFit), ok = null)
                        val recent = array(EngineRuntime.recent.value)
                        if (i >= 21) compare(row.getJSONArray("result"), recent, "bounded_history_$i")
                        assertTrue(EngineRuntime.recent.value.size <= 20)
                        history.put(obj("id" to row.getInt("id"), "recent" to recent, "accepted" to response.isSuccess))
                    }
                    send(BridgeOperation.DeleteFit(historyFit, false), listOf(historyFit))
                    assertEquals(20, EngineRuntime.recent.value.size)
                    val committed = library()
                    val recentCommitted = EngineRuntime.recent.value
                    val stale = EngineRuntime.request(context, BridgeOperation.AddModule(ship, item("Damage Control II")),
                        mapOf(ship to 1L)).get(120, TimeUnit.SECONDS)
                    assertEquals(BridgeErrorCode.REVISION_CONFLICT, stale.error?.code)
                    val invalid = send(BridgeOperation.AddModule(ship, Int.MAX_VALUE), listOf(ship), false)
                    compare(committed, library(), "stale_unknown_item_atomic")
                    assertEquals(recentCommitted, EngineRuntime.recent.value)
                    rejections.put(obj("label" to "stale_revision", "code" to stale.error?.code?.name))
                    rejections.put(obj("label" to "unknown_item", "code" to invalid.error?.code?.name))
                    click("modules-add"); click("equipment-recent")
                    val generation = diagnostics().getJSONObject("persistence").getLong("generation")
                    val tags = compose.onAllNodes(SemanticsMatcher("recent item") {
                        it.config.getOrNull(SemanticsProperties.TestTag)?.startsWith("equipment-item-") == true
                    }).fetchSemanticsNodes().map { it.config[SemanticsProperties.TestTag].removePrefix("equipment-item-").toInt() }
                    assertEquals(EngineRuntime.recent.value, tags)
                    compose.onNodeWithTag("equipment-item-${tags.first()}").performScrollTo(); screenshot("recent")
                    click("equipment-item-${tags.first()}")
                    waitFor { !editor.loading }
                    assertEquals(recentCommitted, EngineRuntime.recent.value)
                    assertEquals(generation, diagnostics().getJSONObject("persistence").getLong("generation"))
                    val afterPrior = typed(array(fits().filter { it.id in originalIds }.map(ModuleTestJson::fit)))
                    compare(before, afterPrior, "prior_fits_unchanged")
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    EngineRuntime.selectFit(context, copy).get(30, TimeUnit.SECONDS)
                    saved.writeText(obj("fits" to library(), "details" to allDetails(), "prior" to before,
                        "recent" to array(EngineRuntime.recent.value), "active_id" to copy,
                        "new_ids" to array(listOf(ship, copy, structure)), "recent_ui_ids" to array(tags)).toString(), Charsets.UTF_8)
                }
                "restored" -> {
                    val expected = JSONObject(saved.readText(Charsets.UTF_8))
                    compare(expected.getJSONObject("fits"), library(), "restored_library", strict = false)
                    compare(expected.getJSONObject("details"), allDetails(), "restored_details", strict = false)
                    compare(expected.getJSONArray("recent"), array(EngineRuntime.recent.value))
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    val ids = expected.getJSONArray("new_ids")
                    for (i in 0 until ids.length()) {
                        val id = ids.getString(i)
                        click("open-$id")
                        waitFor { (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id == id }
                        click("modules-open")
                        waitFor { !editor.loading && editor.details?.fitId == id }
                        assertTrue(editor.details!!.modules.any { it.id != null })
                        if (i == 1) {
                            assertEquals(ModuleSlot.HIGH, fit(id).modules[7].emptySlot)
                            click("modules-rack-HIGH")
                            compose.onNodeWithTag("module-7").performScrollTo(); screenshot("restored")
                        }
                        click("modules-back")
                    }
                }
                else -> error("Unknown phase")
            }
            retain(obj("task" to "B04.2.2", "phase" to phase, "pid" to Process.myPid(),
                "runtime_start" to runtimeStart, "runtime_end" to diagnostics(), "before" to before, "after" to library(),
                "details" to allDetails(), "recent" to array(EngineRuntime.recent.value), "cases" to observed,
                "default_states" to defaults, "history" to history, "rejections" to rejections,
                "codec_rejections" to codecRejections,
                "saved" to JSONObject(saved.readText(Charsets.UTF_8)), "checks" to array(if (phase == "prepare") listOf(
                    "complete_matrix", "all_default_states", "two_recipients", "prior_fits_unchanged", "ui_add_replace_remove",
                    "vacant_position_reused", "picker_recreation", "resource_warning", "skill_warning", "restriction_confirmation_recreation",
                    "override_reenable", "independent_copy", "structure_service_replacement", "twenty_recent_items",
                    "recent_order_visible", "views_do_not_record_use", "stale_unknown_atomic", "typed_protocol_guards") else listOf(
                    "fresh_process_restore", "identities_positions_states_values_retained", "recent_retained", "reopen_each_fit"))), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
