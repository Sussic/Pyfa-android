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
class CloneFillTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val editor get() = ViewModelProvider(compose.activity)[ModuleEditorModel::class.java]
    private val equipment get() = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
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
            DamagePattern(25.0, 25.0, 25.0, 25.0),
            Security(SystemSecurity.HISEC, 0.0), modules, emptyList()))).fits.single().id
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        sync(); click("modules-open")
        waitFor { !editor.loading && editor.details?.fitId == id &&
            editor.details?.revision == fit(id).revision &&
            editor.vacancyOptions?.revision == fit(id).revision }
    }
    private fun awaitEdit(id: String, fittedCount: Int) {
        waitFor { !editor.editing && !editor.loading &&
            editor.details?.revision == fit(id).revision &&
            editor.vacancyOptions?.revision == fit(id).revision &&
            fit(id).modules.count { it.emptySlot == null } == fittedCount }
    }
    private fun close() { click("modules-back") }
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b053-" + name + ".png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b053-" + phase + ".json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use {
                it.write(value.toString(2).toByteArray(Charsets.UTF_8))
            }
            completion.readBytes()
        }
    }
    private fun modules(id: String): JSONObject {
        val details = EngineRuntime.fittingDetails(context, id).get(120, TimeUnit.SECONDS)
        val fitted = details.modules.filter { it.id != null }
        return obj("fit_id" to id, "revision" to fit(id).revision,
            "fitted" to array(fitted.map { row ->
                obj("index" to row.index, "id" to row.id, "name" to row.name,
                    "state" to row.state.name, "charge" to row.charge, "slot" to row.slot.name)
            }), "vacancies" to array(details.modules.filter { it.id == null && it.slot.editable }.map { it.index }),
            "stats" to ModuleTestJson.stats(fit(id)))
    }
    private fun decoderGuards(id: String): JSONArray {
        val itemId = 3106
        val value = EngineRuntime.fillItemOptions(context, id, itemId).get(120, TimeUnit.SECONDS)
        val raw = obj("version" to 1, "fit_id" to value.fitId, "revision" to value.revision,
            "item_id" to value.itemId, "slot" to value.slot.name, "vacancies" to value.vacancies,
            "ignore_restrictions" to value.ignoreRestrictions).toString()
        BridgeCodec.decodeFillItemOptions(raw)
        val rejected = JSONArray()
        for ((label, changed) in listOf(
            "decimal_item" to raw.replaceFirst("\"item_id\":" + itemId, "\"item_id\":" + itemId + ".0"),
            "unknown_slot" to raw.replaceFirst("\"slot\":\"HIGH\"", "\"slot\":\"SUBSYSTEM\""),
            "negative_vacancies" to raw.replaceFirst(Regex("\"vacancies\":\\d+"), "\"vacancies\":-1"),
            "extra_field" to raw.replaceFirst("{", "{\"extra\":1,")
        )) {
            assertNotEquals("Missing guard target: " + label, raw, changed)
            try { BridgeCodec.decodeFillItemOptions(changed); fail("Accepted " + label) }
            catch (_: BridgeProtocolException) { rejected.put(label) }
        }
        val vacancies = EngineRuntime.cloneVacancyOptions(context, id).get(120, TimeUnit.SECONDS)
        val rawVacancies = obj("version" to 1, "fit_id" to vacancies.fitId,
            "revision" to vacancies.revision, "vacancies" to array(vacancies.vacancies.map {
                obj("index" to it.index, "slot" to it.slot.name)
            })).toString()
        BridgeCodec.decodeCloneVacancyOptions(rawVacancies)
        val duplicate = JSONObject(rawVacancies)
        val first = duplicate.getJSONArray("vacancies").getJSONObject(0)
        duplicate.put("vacancies", JSONArray().put(first).put(first))
        for ((label, changed) in listOf(
            "boolean_vacancy_index" to rawVacancies.replaceFirst(Regex("\"index\":\\d+"), "\"index\":true"),
            "subsystem_vacancy" to rawVacancies.replaceFirst(Regex("\"slot\":\"[A-Z]+\""), "\"slot\":\"SUBSYSTEM\""),
            "duplicate_vacancy" to duplicate.toString()
        )) {
            assertNotEquals("Missing guard target: " + label, rawVacancies, changed)
            try { BridgeCodec.decodeCloneVacancyOptions(changed); fail("Accepted " + label) }
            catch (_: BridgeProtocolException) { rejected.put(label) }
        }
        return rejected
    }

    @Test fun cloneAndFillSurviveRestartOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b053_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val before = library()
        val recentBefore = array(EngineRuntime.recent.value)
        val runtimeStart = diagnostics()
        val saved = File(context.noBackupFilesDir, "b053-test-expected.json")
        val checks = JSONArray()
        val rejections = JSONArray()
        var codec = JSONArray()
        var ids = JSONArray()
        var selected = JSONObject()
        var filled = JSONObject()
        var market = JSONObject()
        var recipient = JSONObject()
        try {
            when (phase) {
                "prepare" -> {
                    val selectedId = create("Vexor", "B05 selected clone – 探索", listOf(
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.OVERHEATED, "Antimatter Charge M"),
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.ACTIVE, "Iron Charge M")))
                    open(selectedId)
                    click("module-clone-select-0"); click("module-clone-select-1")
                    assertEquals(setOf(0, 1), editor.selectedForClone)
                    compose.onNodeWithTag("modules-clone-preview").performScrollTo()
                        .assertTextContains("2 selected", substring = true)
                    screenshot("selection")
                    compose.activityRule.scenario.recreate(); sync()
                    assertEquals(setOf(0, 1), editor.selectedForClone)
                    click("modules-clone-selected")
                    awaitEdit(selectedId, 4)
                    selected = modules(selectedId)
                    val rows = selected.getJSONArray("fitted")
                    assertEquals(listOf(0, 1, 11, 12), (0 until rows.length()).map { rows.getJSONObject(it).getInt("index") })
                    assertEquals(listOf("OVERHEATED", "ACTIVE", "OVERHEATED", "ACTIVE"),
                        (0 until rows.length()).map { rows.getJSONObject(it).getString("state") })
                    assertEquals(listOf("Antimatter Charge M", "Iron Charge M", "Antimatter Charge M", "Iron Charge M"),
                        (0 until rows.length()).map { rows.getJSONObject(it).getString("charge") })
                    screenshot("selected-saved"); close()
                    checks.put("selection_recreation"); checks.put("selected_positions_states_charges")

                    val fillId = create("Vexor", "B05 fitted source fill", listOf(
                        ModuleSpec("Dual 150mm Railgun II", ModuleState.OVERHEATED, "Antimatter Charge M")))
                    open(fillId)
                    click("module-clone-source-0")
                    click("module-clone-here-10")
                    awaitEdit(fillId, 2)
                    assertEquals("Antimatter Charge M", fit(fillId).modules[10].charge)
                    screenshot("targeted")
                    click("module-fill-clone-0")
                    awaitEdit(fillId, 4)
                    filled = modules(fillId)
                    assertEquals(4, filled.getJSONArray("fitted").length())
                    for (i in 0 until 4) {
                        val row = filled.getJSONArray("fitted").getJSONObject(i)
                        assertEquals("OVERHEATED", row.getString("state"))
                        assertEquals("Antimatter Charge M", row.getString("charge"))
                    }
                    screenshot("fitted-fill"); close()
                    checks.put("targeted_vacancy"); checks.put("fitted_source_fill")

                    val marketId = create("Rifter", "B05 market fill")
                    open(marketId)
                    compose.onNodeWithTag("modules-clone-preview").performScrollTo().assertExists()
                    screenshot("empty")
                    click("modules-add")
                    waitFor { equipment.catalog != null && !equipment.busy }
                    compose.onNodeWithTag("equipment-search").performTextReplacement("Damage Control II")
                    click("equipment-search-submit")
                    waitFor { !equipment.busy && equipment.results.contains(2048) }
                    click("equipment-item-2048")
                    waitFor { runCatching {
                        compose.onNodeWithTag("equipment-fill-preview").assertTextContains("Up to 4", substring = true)
                        true
                    }.getOrDefault(false) }
                    screenshot("market-preview")
                    click("equipment-fill")
                    awaitEdit(marketId, 1)
                    assertEquals(2048, EngineRuntime.recent.value.first())
                    market = modules(marketId)
                    screenshot("market-saved")
                    click("equipment-view-fit"); close()
                    checks.put("market_touch_preview_stop_history")

                    val source = create("Celestis", "B05 projected fill", listOf(
                        ModuleSpec("Remote Sensor Dampener II", ModuleState.ACTIVE, "Scan Resolution Dampening Script")))
                    val target = create("Rifter", "B05 projected receiver")
                    send(BridgeOperation.AddProjection(source, target, 0.0), listOf(source, target))
                    val recipientBefore = ModuleTestJson.stats(fit(target))
                    val response = send(BridgeOperation.FillModulesClone(source, 0), listOf(source))
                    assertEquals(setOf(source, target), response.fits.map { it.id }.toSet())
                    val recipientAfter = ModuleTestJson.stats(fit(target))
                    assertNotEquals(recipientBefore.toString(), recipientAfter.toString())
                    recipient = obj("before" to recipientBefore, "after" to recipientAfter,
                        "source" to modules(source), "target" to modules(target))
                    checks.put("linked_recipient")

                    val committed = library()
                    for ((label, positions) in listOf("duplicate" to listOf(0, 0),
                            "vacancy" to listOf(2), "out_of_range" to listOf(999))) {
                        val result = send(BridgeOperation.CloneSelectedModules(selectedId, positions), listOf(selectedId), false)
                        rejections.put(obj("label" to label, "code" to result.error?.code?.name))
                    }
                    val stale = EngineRuntime.request(context,
                        BridgeOperation.CloneSelectedModules(selectedId, listOf(0)),
                        mapOf(selectedId to 0L)).get(120, TimeUnit.SECONDS)
                    assertEquals(BridgeErrorCode.REVISION_CONFLICT, stale.error?.code)
                    rejections.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    compare(committed, library())
                    codec = decoderGuards(fillId)
                    checks.put("atomic_rejections"); checks.put("typed_fill_preview")
                    EngineRuntime.selectFit(context, selectedId).get(30, TimeUnit.SECONDS)
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    ids = array(listOf(selectedId, fillId, marketId, source, target))
                    saved.writeText(obj("fits" to library(), "recent" to array(EngineRuntime.recent.value),
                        "prior" to before, "active_id" to selectedId, "new_ids" to ids).toString(), Charsets.UTF_8)
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
                        assertEquals(id, editor.details?.fitId)
                        if (i == 0) screenshot("restored")
                        close()
                    }
                    checks.put("fresh_process_restore"); checks.put("reopen_each_fit")
                }
                else -> error("Unknown phase")
            }
            retain(obj("task" to "B05.3", "phase" to phase, "pid" to Process.myPid(),
                "runtime_start" to runtimeStart, "runtime_end" to diagnostics(),
                "before" to before, "after" to library(), "recent_before" to recentBefore,
                "recent_after" to array(EngineRuntime.recent.value), "selected" to selected,
                "filled" to filled, "market" to market, "recipient" to recipient,
                "rejections" to rejections, "codec_rejections" to codec,
                "saved" to JSONObject(saved.readText(Charsets.UTF_8)), "checks" to checks), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
