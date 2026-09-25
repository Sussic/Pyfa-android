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
class BulkVariationRemovalTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val picker get() = ViewModelProvider(compose.activity)[VariationEditorModel::class.java]
    private fun fits() = EngineRuntime.library.value
    private fun fit(id: String) = fits().single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun waitFor(predicate: () -> Boolean) { compose.waitUntil(60_000, predicate); sync() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick(); sync() }
    private fun library() = typed(array(fits().map(ModuleTestJson::fit)))
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList(), ok: Boolean = true): BridgeResponse {
        val response = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision })
            .get(120, TimeUnit.SECONDS)
        assertEquals(response.error?.message, ok, response.isSuccess)
        return response
    }
    private fun create(ship: String, name: String, modules: List<ModuleSpec> = emptyList()): String =
        send(BridgeOperation.CreateFit(FitSpec(name, ship, 5, false,
            DamagePattern(25.0, 25.0, 25.0, 25.0), Security(SystemSecurity.HISEC, 0.0),
            modules, emptyList()))).fits.single().id
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        sync(); click("variations-open")
        waitFor { !picker.loading && picker.options?.fitId == id &&
            picker.bulkOptions?.fitId == id && picker.options?.revision == fit(id).revision }
    }
    private fun close() { if (picker.position != null) click("variations-back"); click("variations-back") }
    private fun awaitEdit(id: String) { waitFor { !picker.loading && !picker.editing && picker.error == null &&
        picker.position == null && picker.options?.revision == fit(id).revision } }
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b054-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b054-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use {
                it.write(value.toString(2).toByteArray(Charsets.UTF_8))
            }
            completion.readBytes()
        }
    }
    private fun modules(id: String) = array(fit(id).modules.filter { it.emptySlot == null }.map { row ->
        obj("index" to row.index, "name" to row.name, "state" to row.state?.name, "charge" to row.charge)
    })

    @Test fun selectedAndSimilarEditsSurviveRestartOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b054_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val before = library(); val recentBefore = array(EngineRuntime.recent.value)
        val runtimeStart = diagnostics()
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("enabled"))
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("opened_existing"))
        val saved = File(context.noBackupFilesDir, "b054-test-expected.json")
        val checks = JSONArray(); val rejections = JSONArray(); val protocol = JSONArray()
        val results = JSONObject(); var ids = JSONArray()
        try {
            when (phase) {
                "prepare" -> {
                    val mixed = create("Vexor", "B05.4 mixed selected – 探索", listOf(
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.OVERHEATED, "Spike M"),
                        ModuleSpec("Dual 150mm Railgun I", ModuleState.ACTIVE, "Antimatter Charge M"),
                        ModuleSpec("200mm Railgun II", ModuleState.ACTIVE, "Iron Charge M"),
                        ModuleSpec("Sensor Booster I", ModuleState.ACTIVE, "Scan Resolution Script")))
                    open(mixed)
                    click("bulk-edits-select-all")
                    click("variation-target-module-0")
                    assertEquals(setOf(0, 1, 2, 3), picker.bulkSelected)
                    compose.onNodeWithTag("bulk-edits-preview").performScrollTo()
                    compose.onNodeWithTag("bulk-edits-preview-2")
                        .assertTextContains("variation skipped: different family", substring = true)
                    compose.onNodeWithTag("bulk-edits-preview-3")
                        .assertTextContains("variation skipped: different family", substring = true)
                    screenshot("selected-preview")
                    compose.activityRule.scenario.recreate(); sync()
                    assertEquals(setOf(0, 1, 2, 3), picker.bulkSelected)
                    assertEquals(0, picker.position)
                    click("variation-item-567")
                    click("bulk-edits-change")
                    awaitEdit(mixed)
                    assertEquals(listOf("Dual 150mm Railgun I", "Dual 150mm Railgun I",
                        "200mm Railgun II", "Sensor Booster I"),
                        fit(mixed).modules.take(4).map { it.name })
                    assertNull(fit(mixed).modules[0].charge)
                    results.put("mixed", modules(mixed)); screenshot("selected-saved"); close()
                    checks.put("selected_family_skip_recreation_charge")

                    val similar = create("Vexor", "B05.4 related similar", listOf(
                        ModuleSpec("Dual 150mm Railgun I", ModuleState.ACTIVE, "Antimatter Charge M"),
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.OVERHEATED, "Spike M"),
                        ModuleSpec("200mm Railgun II", ModuleState.ACTIVE, "Iron Charge M")))
                    open(similar); click("variation-target-module-0")
                    click("bulk-edits-expand")
                    click("bulk-edits-scope-SIMILAR")
                    compose.onNodeWithTag("bulk-edits-preview-2").performScrollTo()
                        .assertTextContains("variation target", substring = true)
                    screenshot("similar-preview")
                    click("variation-item-3106"); click("bulk-edits-change"); awaitEdit(similar)
                    assertEquals(listOf("Dual 150mm Railgun II", "Dual 150mm Railgun II",
                        "Dual 150mm Railgun II"), fit(similar).modules.take(3).map { it.name })
                    results.put("similar", modules(similar)); screenshot("similar-saved"); close()
                    checks.put("similar_cross_family_outside_selection")

                    val removal = create("Vexor", "B05.4 selected removal", listOf(
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.ACTIVE, "Antimatter Charge M"),
                        ModuleSpec("Sensor Booster I", ModuleState.ACTIVE, "Scan Resolution Script"),
                        ModuleSpec("Damage Control II", ModuleState.ONLINE)))
                    open(removal)
                    click("bulk-edits-select-0"); click("bulk-edits-select-2")
                    click("variation-target-module-0")
                    compose.onNodeWithTag("bulk-edits-target-count").performScrollTo()
                        .assertTextContains("Removal targets: 2", substring = true)
                    screenshot("removal-preview")
                    click("bulk-edits-remove"); awaitEdit(removal)
                    assertEquals(listOf("Sensor Booster I"), fit(removal).modules.filter { it.emptySlot == null }.map { it.name })
                    assertEquals(listOf(3106, 2048), EngineRuntime.recent.value.take(2))
                    results.put("removal", modules(removal)); screenshot("removal-saved"); close()
                    checks.put("selected_removal_reverse_history")

                    val empty = create("Rifter", "B05.4 empty")
                    open(empty)
                    compose.onNodeWithTag("variations-empty").performScrollTo().assertExists()
                    screenshot("empty")
                    EngineRuntime.selectFit(context, mixed).get(30, TimeUnit.SECONDS)
                    waitFor { !picker.loading && picker.options?.fitId == mixed }
                    assertTrue(picker.bulkSelected.isEmpty())
                    close(); checks.put("empty_and_fit_switch")

                    val committed = library()
                    for ((label, operation) in listOf(
                        "out_of_range" to BridgeOperation.RemoveBulkModules(mixed, 999, listOf(999), BulkScope.SELECTED),
                        "wrong_family" to BridgeOperation.ChangeBulkVariations(mixed, 0, listOf(0), BulkScope.SELECTED, 2048))) {
                        val failure = send(operation, listOf(mixed), false)
                        rejections.put(obj("label" to label, "code" to failure.error?.code?.name))
                    }
                    val stale = EngineRuntime.request(context,
                        BridgeOperation.RemoveBulkModules(mixed, 0, listOf(0), BulkScope.SELECTED),
                        mapOf(mixed to 0L)).get(120, TimeUnit.SECONDS)
                    assertEquals(BridgeErrorCode.REVISION_CONFLICT, stale.error?.code)
                    rejections.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    compare(committed, library())
                    checks.put("atomic_rejections")
                    for ((label, operation) in listOf(
                        "empty_selection" to BridgeOperation.RemoveBulkModules(mixed, 0, emptyList(), BulkScope.SELECTED),
                        "duplicate_selection" to BridgeOperation.RemoveBulkModules(mixed, 0, listOf(0, 0), BulkScope.SELECTED),
                        "negative_position" to BridgeOperation.RemoveBulkModules(mixed, -1, listOf(0), BulkScope.SELECTED),
                        "negative_item" to BridgeOperation.ChangeBulkVariations(mixed, 0, listOf(0), BulkScope.SELECTED, -1))) {
                        try {
                            BridgeCodec.encodeRequest(BridgeRequest("b054-$label", runtimeStart.getString("session_id"),
                                operation, mapOf(mixed to fit(mixed).revision)))
                            fail("Accepted $label")
                        } catch (_: BridgeProtocolException) { protocol.put(label) }
                    }
                    val choices = EngineRuntime.variationOptions(context, mixed).get(120, TimeUnit.SECONDS)
                    val raw = VariationTestJson.options(choices)
                        .put("version", 1).put("fit_id", mixed).put("revision", fit(mixed).revision)
                        .put("module_families", array(choices.familyCandidates.toSortedMap().map { (index, candidates) ->
                            obj("index" to index, "candidates" to array(candidates))
                        }))
                    BridgeCodec.decodeVariationOptions(raw.toString())
                    for (label in listOf("negative_family_candidate", "duplicate_family_candidate",
                            "missing_family_row", "asymmetric_family", "extra_family_field")) {
                        val changed = JSONObject(raw.toString())
                        val families = changed.getJSONArray("module_families")
                        val first = families.getJSONObject(0)
                        when (label) {
                            "negative_family_candidate" -> first.put("candidates", JSONArray().put(-1))
                            "duplicate_family_candidate" -> first.getJSONArray("candidates").put(0)
                            "missing_family_row" -> changed.put("module_families", JSONArray())
                            "asymmetric_family" -> first.put("candidates", JSONArray().put(0))
                            else -> first.put("unexpected", true)
                        }
                        try { BridgeCodec.decodeVariationOptions(changed.toString()); fail("Accepted $label") }
                        catch (_: BridgeProtocolException) { protocol.put(label) }
                    }
                    checks.put("typed_bulk_requests")
                    EngineRuntime.selectFit(context, mixed).get(30, TimeUnit.SECONDS)
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    ids = array(listOf(mixed, similar, removal, empty))
                    saved.writeText(obj("fits" to library(), "recent" to array(EngineRuntime.recent.value),
                        "prior" to before, "new_ids" to ids, "active_id" to mixed).toString(), Charsets.UTF_8)
                }
                "restored" -> {
                    val expected = JSONObject(saved.readText(Charsets.UTF_8))
                    compare(expected.getJSONObject("fits"), library(), strict = false)
                    compare(expected.getJSONArray("recent"), array(EngineRuntime.recent.value))
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    ids = expected.getJSONArray("new_ids")
                    for (i in 0 until ids.length()) {
                        val id = ids.getString(i)
                        open(id)
                        assertEquals(id, picker.options?.fitId)
                        if (i == 0) screenshot("restored")
                        close()
                    }
                    checks.put("fresh_process_restore"); checks.put("reopen_each_fit")
                }
                else -> error("Unknown phase")
            }
            retain(obj("task" to "B05.4", "phase" to phase, "pid" to Process.myPid(),
                "runtime_start" to runtimeStart, "runtime_end" to diagnostics(),
                "before" to before, "after" to library(), "recent_before" to recentBefore,
                "recent_after" to array(EngineRuntime.recent.value), "results" to results,
                "rejections" to rejections, "protocol_rejections" to protocol,
                "saved" to JSONObject(saved.readText(Charsets.UTF_8)),
                "new_ids" to ids, "checks" to checks), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
