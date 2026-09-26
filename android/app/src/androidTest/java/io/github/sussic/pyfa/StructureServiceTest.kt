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
import io.github.sussic.pyfa.ModuleTestJson.stats
import io.github.sussic.pyfa.ModuleTestJson.typed

@RunWith(AndroidJUnit4::class)
@OptIn(ExperimentalTestApi::class)
class StructureServiceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[StructureServiceEditorModel::class.java]
    private fun fits() = EngineRuntime.library.value
    private fun fit(id: String) = fits().single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun waitFor(predicate: () -> Boolean) { compose.waitUntil(60_000, predicate); sync() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick(); sync() }
    private fun library() = typed(array(fits().map(ModuleTestJson::fit)))
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList(), ok: Boolean = true): BridgeResponse {
        val result = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision })
            .get(120, TimeUnit.SECONDS)
        assertEquals(result.error?.message, ok, result.isSuccess)
        return result
    }
    private fun create(ship: String): String = send(BridgeOperation.CreateFit(FitSpec(
        "B06.3 $ship – 探索", ship, 5, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
        Security(SystemSecurity.HISEC, 0.0), emptyList(), emptyList()))).fits.single().id
    private fun options(id: String) = EngineRuntime.structureServiceOptions(context, id).get(120, TimeUnit.SECONDS)
    private fun details(id: String) = EngineRuntime.fittingDetails(context, id).get(120, TimeUnit.SECONDS)
    private fun position(id: String, name: String) = details(id).modules.single { it.name == name }.index
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        sync(); click("services-open")
        waitFor { !model.loading && model.options?.fitId == id && model.options?.revision == fit(id).revision }
    }
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b063-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b063-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use {
                it.write(value.toString(2).toByteArray(Charsets.UTF_8))
            }
            completion.readBytes()
        }
    }
    private fun state(id: String): JSONObject {
        val layout = details(id)
        val slots = array(listOf(ModuleSlot.LOW, ModuleSlot.MED, ModuleSlot.HIGH,
            ModuleSlot.RIG, ModuleSlot.SERVICE).map { kind ->
            val row = layout.slots.single { it.slot == kind }
            obj("slot" to kind.name, "used" to row.used, "total" to row.total.raw)
        })
        val modules = array(layout.modules.map { row -> obj("index" to row.index, "id" to row.id,
            "name" to row.name, "slot" to row.slot.name, "state" to row.state.name,
            "charge" to row.charge, "legal" to row.legal) })
        val resources = obj("cpu_used" to layout.resources.getValue("cpu").used.raw,
            "cpu_total" to layout.resources.getValue("cpu").total.raw,
            "powergrid_used" to layout.resources.getValue("powergrid").used.raw,
            "powergrid_total" to layout.resources.getValue("powergrid").total.raw)
        return obj("modules" to modules, "slots" to slots, "resources" to resources,
            "stats" to stats(fit(id)))
    }
    private fun step(rows: JSONArray, id: String, operation: List<String>?, accepted: Boolean = true) {
        rows.put(obj("operation" to operation?.let(::array), "accepted" to accepted,
            "result" to state(id)))
    }
    private fun add(rows: JSONArray, id: String, item: Int, name: String, ok: Boolean = true) {
        send(BridgeOperation.AddModule(id, item), listOf(id), ok)
        step(rows, id, listOf("add", name), ok)
    }
    private fun remove(rows: JSONArray, id: String, name: String) {
        send(BridgeOperation.RemoveModule(id, position(id, name)), listOf(id))
        step(rows, id, listOf("remove", name))
    }

    @Test fun structureServicesMatchDesktopAndRestoreOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b063_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val before = library(); val runtimeStart = diagnostics()
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("enabled"))
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("opened_existing"))
        val saved = File(context.noBackupFilesDir, "b063-test-expected.json")
        val checks = JSONArray(); val rejected = JSONArray(); val protocol = JSONArray()
        val cases = JSONArray(); var ids = JSONArray()
        try {
            when (phase) {
                "prepare" -> {
                    val astrahus = create("Astrahus")
                    open(astrahus)
                    assertEquals(3, options(astrahus).capacity)
                    assertEquals(6, options(astrahus).choices.size)
                    compose.onNodeWithTag("services-count").assertTextContains("0/3", substring = true)
                    compose.onNodeWithTag("services-shield_hp").assertTextContains("3,600,000", substring = true)
                    screenshot("astrahus-empty")
                    val astrahusSteps = JSONArray(); step(astrahusSteps, astrahus, null)
                    click("service-choice-35878")
                    waitFor { !model.loading && !model.editing && model.options?.revision == fit(astrahus).revision &&
                        model.details?.modules?.any { it.name == "Standup Manufacturing Plant I" } == true }
                    compose.onNodeWithTag("services-count").assertTextContains("1/3", substring = true)
                    compose.onNodeWithTag("services-shield_hp").assertTextContains("14,400,000", substring = true)
                    screenshot("manufacturing-bonus")
                    step(astrahusSteps, astrahus, listOf("add", "Standup Manufacturing Plant I"))
                    add(astrahusSteps, astrahus, 35899, "Standup Reprocessing Facility I")
                    add(astrahusSteps, astrahus, 35891, "Standup Research Lab I")
                    waitFor { !model.loading && model.options?.revision == fit(astrahus).revision }
                    compose.onNodeWithTag("services-add-target").assertIsNotEnabled()
                        .assertTextContains("Service slots full", substring = true)
                    add(astrahusSteps, astrahus, 35886, "Standup Invention Lab I", false)
                    waitFor { !model.loading && model.options?.revision == fit(astrahus).revision }
                    val replaceAt = position(astrahus, "Standup Manufacturing Plant I")
                    click("services-replace-$replaceAt")
                    click("service-choice-35886")
                    waitFor { !model.loading && !model.editing && model.options?.revision == fit(astrahus).revision &&
                        model.details?.modules?.any { it.name == "Standup Invention Lab I" } == true }
                    screenshot("astrahus-replaced")
                    step(astrahusSteps, astrahus, listOf("replace", "Standup Manufacturing Plant I", "Standup Invention Lab I"))
                    val removeAt = position(astrahus, "Standup Reprocessing Facility I")
                    click("services-remove-$removeAt")
                    waitFor { !model.loading && !model.editing && model.options?.revision == fit(astrahus).revision &&
                        model.details?.modules?.none { it.name == "Standup Reprocessing Facility I" } == true }
                    step(astrahusSteps, astrahus, listOf("remove", "Standup Reprocessing Facility I"))
                    add(astrahusSteps, astrahus, 35899, "Standup Reprocessing Facility I")
                    add(astrahusSteps, astrahus, 35881, "Standup Capital Shipyard I", false)
                    add(astrahusSteps, astrahus, 2889, "200mm AutoCannon II", false)
                    cases.put(obj("ship" to "Astrahus", "steps" to astrahusSteps))
                    click("services-back")

                    val fortizar = create("Fortizar")
                    val fortizarSteps = JSONArray(); step(fortizarSteps, fortizar, null)
                    add(fortizarSteps, fortizar, 35892, "Standup Market Hub I")
                    add(fortizarSteps, fortizar, 35878, "Standup Manufacturing Plant I")
                    add(fortizarSteps, fortizar, 35899, "Standup Reprocessing Facility I")
                    remove(fortizarSteps, fortizar, "Standup Manufacturing Plant I")
                    cases.put(obj("ship" to "Fortizar", "steps" to fortizarSteps))

                    val athanor = create("Athanor")
                    val athanorSteps = JSONArray(); step(athanorSteps, athanor, null)
                    add(athanorSteps, athanor, 45009, "Standup Moon Drill I")
                    add(athanorSteps, athanor, 45537, "Standup Composite Reactor I")
                    add(athanorSteps, athanor, 35899, "Standup Reprocessing Facility I")
                    add(athanorSteps, athanor, 35891, "Standup Research Lab I", false)
                    cases.put(obj("ship" to "Athanor", "steps" to athanorSteps))

                    val ansiblex = create("Ansiblex Jump Bridge")
                    open(ansiblex)
                    assertEquals(1, options(ansiblex).capacity)
                    assertEquals(listOf(35913), options(ansiblex).choices.map { it.id })
                    screenshot("ansiblex-choice")
                    val ansiblexSteps = JSONArray(); step(ansiblexSteps, ansiblex, null)
                    click("service-choice-35913")
                    waitFor { !model.loading && !model.editing && model.options?.revision == fit(ansiblex).revision &&
                        model.details?.modules?.any { it.name == "Standup Conduit Generator I" } == true }
                    compose.onNodeWithTag("services-count").assertTextContains("1/1", substring = true)
                    screenshot("ansiblex-fitted")
                    step(ansiblexSteps, ansiblex, listOf("add", "Standup Conduit Generator I"))
                    add(ansiblexSteps, ansiblex, 35878, "Standup Manufacturing Plant I", false)
                    waitFor { !model.loading && model.options?.revision == fit(ansiblex).revision }
                    click("services-remove-${position(ansiblex, "Standup Conduit Generator I")}")
                    waitFor { !model.loading && !model.editing && model.options?.revision == fit(ansiblex).revision &&
                        model.details?.modules?.none { it.name == "Standup Conduit Generator I" } == true }
                    step(ansiblexSteps, ansiblex, listOf("remove", "Standup Conduit Generator I"))
                    cases.put(obj("ship" to "Ansiblex Jump Bridge", "steps" to ansiblexSteps))
                    click("services-back")

                    val metenox = create("Metenox Moon Drill")
                    val metenoxSteps = JSONArray(); step(metenoxSteps, metenox, null)
                    add(metenoxSteps, metenox, 82941, "Standup Metenox Moon Drill")
                    add(metenoxSteps, metenox, 35913, "Standup Conduit Generator I", false)
                    cases.put(obj("ship" to "Metenox Moon Drill", "steps" to metenoxSteps))

                    val copy = send(BridgeOperation.DuplicateFit(astrahus, "B06.3 structure copy – Δ"),
                        listOf(astrahus)).fits.single { it.name == "B06.3 structure copy – Δ" }.id
                    compare(stats(fit(astrahus)), stats(fit(copy)))
                    assertEquals(3, details(copy).slots.single { it.slot == ModuleSlot.SERVICE }.used)
                    checks.put("five_original_structure_sequences")
                    checks.put("service_bonus_copy")

                    val vexor = create("Vexor")
                    open(vexor)
                    assertFalse(options(vexor).isStructure)
                    compose.onNodeWithTag("services-not-structure").assertIsDisplayed()
                    screenshot("vexor-no-services")
                    click("services-back")
                    val committed = library()
                    val cross = send(BridgeOperation.AddModule(vexor, 35878), listOf(vexor), false)
                    rejected.put(obj("label" to "ship_standup", "code" to cross.error?.code?.name))
                    val stale = EngineRuntime.request(context, BridgeOperation.AddModule(astrahus, 35878),
                        mapOf(astrahus to 0L)).get(120, TimeUnit.SECONDS)
                    assertEquals(BridgeErrorCode.REVISION_CONFLICT, stale.error?.code)
                    rejected.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    // A failed valid market attempt can update recent-use history;
                    // the committed fit library must still be unchanged.
                    compare(committed, library())
                    checks.put("atomic_rejections")

                    val current = options(astrahus)
                    val raw = obj("version" to 1, "fit_id" to astrahus,
                        "revision" to current.revision, "is_structure" to current.isStructure,
                        "capacity" to current.capacity,
                        "choices" to array(current.choices.map { obj("id" to it.id, "name" to it.name) }))
                    BridgeCodec.decodeStructureServiceOptions(raw.toString())
                    for (label in listOf("duplicate_choice", "wrong_flag", "negative_capacity",
                        "wrong_version", "extra_field", "wrong_boolean")) {
                        val broken = JSONObject(raw.toString())
                        when (label) {
                            "duplicate_choice" -> broken.getJSONArray("choices").put(broken.getJSONArray("choices").getJSONObject(0))
                            "wrong_flag" -> broken.put("is_structure", false)
                            "negative_capacity" -> broken.put("capacity", -1)
                            "wrong_version" -> broken.put("version", 2)
                            "extra_field" -> broken.put("unexpected", true)
                            else -> broken.put("is_structure", "yes")
                        }
                        try { BridgeCodec.decodeStructureServiceOptions(broken.toString()); fail("Accepted $label") }
                        catch (_: BridgeProtocolException) { protocol.put(label) }
                    }
                    checks.put("typed_structure_service_protocol")
                    EngineRuntime.selectFit(context, copy).get(30, TimeUnit.SECONDS)
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    ids = array(listOf(astrahus, fortizar, athanor, ansiblex, metenox, copy, vexor))
                    saved.writeText(obj("fits" to library(), "new_ids" to ids, "copy_id" to copy,
                        "active_id" to copy, "prior" to before).toString(), Charsets.UTF_8)
                }
                "restored" -> {
                    val expected = JSONObject(saved.readText(Charsets.UTF_8))
                    compare(expected.getJSONObject("fits"), library(), strict = false)
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    ids = expected.getJSONArray("new_ids")
                    val copy = expected.getString("copy_id")
                    open(copy)
                    assertEquals(3, details(copy).slots.single { it.slot == ModuleSlot.SERVICE }.used)
                    compose.onNodeWithTag("services-shield_hp").assertTextContains("14,400,000", substring = true)
                    screenshot("restored-structure-copy")
                    click("services-back")
                    for (index in 0 until ids.length()) {
                        val id = ids.getString(index)
                        open(id); assertEquals(id, model.options?.fitId); click("services-back")
                    }
                    checks.put("fresh_process_restore"); checks.put("reopen_each_fit")
                }
                else -> error("Unknown phase")
            }
            retain(obj("task" to "B06.3", "phase" to phase, "pid" to Process.myPid(),
                "runtime_start" to runtimeStart, "runtime_end" to diagnostics(),
                "before" to before, "after" to library(), "cases" to cases,
                "new_ids" to ids, "checks" to checks, "rejections" to rejected,
                "protocol_rejections" to protocol,
                "saved" to JSONObject(saved.readText(Charsets.UTF_8))), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
