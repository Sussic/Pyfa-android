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
class SubsystemTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[SubsystemEditorModel::class.java]
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
    private fun create(ship: String): String = send(BridgeOperation.CreateFit(FitSpec(
        "B06.2 $ship – 探索", ship, 5, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
        Security(SystemSecurity.HISEC, 0.0), emptyList(), emptyList()))).fits.single().id
    private fun options(id: String) = EngineRuntime.subsystemOptions(context, id).get(120, TimeUnit.SECONDS)
    private fun details(id: String) = EngineRuntime.fittingDetails(context, id).get(120, TimeUnit.SECONDS)
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        sync(); click("subsystems-open")
        waitFor { !model.loading && model.options?.fitId == id && model.options?.revision == fit(id).revision }
    }
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b062-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b062-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use {
                it.write(value.toString(2).toByteArray(Charsets.UTF_8))
            }
            completion.readBytes()
        }
    }
    private fun state(id: String): JSONObject {
        val layout = details(id)
        val subs = options(id)
        val slots = array(listOf(obj("slot" to "SUBSYSTEM", "used" to subs.groups.count { it.current != null },
            "total" to subs.capacity)) + listOf(ModuleSlot.HIGH, ModuleSlot.MED, ModuleSlot.LOW,
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
        val hardpoints = array(layout.hardpoints.map { obj("kind" to it.kind,
            "used" to it.used, "total" to it.total.raw) })
        return obj("modules" to modules, "slots" to slots, "hardpoints" to hardpoints,
            "resources" to resources, "stats" to stats(fit(id)))
    }
    private fun step(rows: JSONArray, id: String, operation: List<String>?, accepted: Boolean = true) {
        rows.put(obj("operation" to operation?.let(::array), "accepted" to accepted, "result" to state(id)))
    }

    @Test fun strategicCruiserSubsystemsMatchDesktopAndRestoreOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b062_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val before = library(); val runtimeStart = diagnostics()
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("enabled"))
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("opened_existing"))
        val saved = File(context.noBackupFilesDir, "b062-test-expected.json")
        val checks = JSONArray(); val rejected = JSONArray(); val protocol = JSONArray()
        val rows = JSONArray(); var ids = JSONArray()
        try {
            when (phase) {
                "prepare" -> {
                    val id = create("Tengu")
                    open(id)
                    val original = options(id)
                    assertEquals(4, original.capacity)
                    assertEquals(listOf(125, 126, 127, 128), original.groups.map { it.kind })
                    assertTrue(original.groups.all { it.choices.size == 3 && it.current == null })
                    compose.onNodeWithTag("subsystems-count").assertTextContains("0/4", substring = true)
                    screenshot("tengu-empty")
                    step(rows, id, null)

                    click("subsystem-choice-45601")
                    waitFor { !model.loading && !model.editing && model.options?.revision == fit(id).revision &&
                        model.options?.groups?.single { it.kind == 127 }?.current == 45601 }
                    screenshot("offensive-added")
                    step(rows, id, listOf("add", "Tengu Offensive - Accelerated Ejection Bay"))

                    send(BridgeOperation.AddModule(id, 2410), listOf(id))
                    val launcher = details(id).modules.single { it.name == "Heavy Missile Launcher II" }
                    send(BridgeOperation.SetModuleCharge(id, launcher.index, 209), listOf(id))
                    step(rows, id, listOf("add", "Heavy Missile Launcher II", "Scourge Heavy Missile"))
                    for ((item, kind, label) in listOf(
                        Triple(45590, 126, "Tengu Defensive - Supplemental Screening"),
                        Triple(45614, 128, "Tengu Propulsion - Chassis Optimization"),
                        Triple(45626, 125, "Tengu Core - Augmented Graviton Reactor"))) {
                        send(BridgeOperation.SetSubsystem(id, kind, item), listOf(id))
                        step(rows, id, listOf("add", label))
                    }
                    waitFor { !model.loading && model.options?.revision == fit(id).revision }
                    click("subsystem-choice-45603")
                    waitFor { !model.loading && !model.editing && model.options?.revision == fit(id).revision &&
                        model.options?.groups?.single { it.kind == 127 }?.current == 45603 }
                    screenshot("offensive-replaced")
                    step(rows, id, listOf("add", "Tengu Offensive - Support Processor"))
                    send(BridgeOperation.SetSubsystem(id, 127, 45601), listOf(id))
                    step(rows, id, listOf("replace", "Tengu Offensive - Accelerated Ejection Bay",
                        "Tengu Offensive - Support Processor"))
                    waitFor { !model.loading && model.options?.revision == fit(id).revision }
                    click("subsystem-remove-127")
                    waitFor { !model.loading && !model.editing && model.options?.revision == fit(id).revision &&
                        model.options?.groups?.single { it.kind == 127 }?.current == null }
                    compose.onNodeWithTag("subsystems-illegal").assertTextContains("Heavy Missile Launcher II", substring = true)
                    compose.onNodeWithTag("subsystems-illegal").performScrollTo().assertIsDisplayed()
                    screenshot("offensive-removed-invalid")
                    step(rows, id, listOf("remove", "Tengu Offensive - Accelerated Ejection Bay"))
                    checks.put("charged_launcher_retained_and_marked_illegal")

                    val invalidCopy = send(BridgeOperation.DuplicateFit(id, "B06.2 invalid copy – Δ"), listOf(id))
                        .fits.single { it.name == "B06.2 invalid copy – Δ" }.id
                    compare(stats(fit(id)), stats(fit(invalidCopy)))
                    assertEquals(false, details(invalidCopy).modules.single { it.name == "Heavy Missile Launcher II" }.legal)
                    checks.put("invalid_fit_copies_without_erasure")

                    send(BridgeOperation.SetSubsystem(id, 127, 45601), listOf(id))
                    step(rows, id, listOf("add", "Tengu Offensive - Accelerated Ejection Bay"))
                    send(BridgeOperation.SetSubsystem(id, 126, 45589), listOf(id))
                    step(rows, id, listOf("replace", "Tengu Defensive - Covert Reconfiguration",
                        "Tengu Defensive - Supplemental Screening"))
                    send(BridgeOperation.SetSubsystem(id, 126, null), listOf(id))
                    step(rows, id, listOf("remove", "Tengu Defensive - Covert Reconfiguration"))
                    send(BridgeOperation.SetSubsystem(id, 126, 45590), listOf(id))
                    step(rows, id, listOf("add", "Tengu Defensive - Supplemental Screening"))
                    val committed = library()
                    val cross = send(BridgeOperation.SetSubsystem(id, 125, 45623), listOf(id), false)
                    rejected.put(obj("label" to "cross_hull", "code" to cross.error?.code?.name))
                    step(rows, id, listOf("add", "Legion Core - Augmented Antimatter Reactor"), false)
                    val stale = EngineRuntime.request(context, BridgeOperation.SetSubsystem(id, 127, 45603),
                        mapOf(id to 0L)).get(120, TimeUnit.SECONDS)
                    assertEquals(BridgeErrorCode.REVISION_CONFLICT, stale.error?.code)
                    rejected.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    compare(committed, library())
                    checks.put("all_original_subsystem_states_and_choices")
                    checks.put("atomic_rejections")

                    val vexor = create("Vexor")
                    click("subsystems-back")
                    open(vexor)
                    assertTrue(options(vexor).groups.isEmpty())
                    compose.onNodeWithTag("subsystems-empty").assertIsDisplayed()
                    screenshot("vexor-empty")
                    click("subsystems-back")

                    try {
                        BridgeCodec.encodeRequest(BridgeRequest("b062-negative", runtimeStart.getString("session_id"),
                            BridgeOperation.SetSubsystem(id, 127, -1), mapOf(id to fit(id).revision)))
                        fail("Accepted negative subsystem ID")
                    } catch (_: BridgeProtocolException) { protocol.put("negative_request") }
                    try {
                        BridgeCodec.encodeRequest(BridgeRequest("b062-kind", runtimeStart.getString("session_id"),
                            BridgeOperation.SetSubsystem(id, 999, 45601), mapOf(id to fit(id).revision)))
                        fail("Accepted unknown subsystem kind")
                    } catch (_: BridgeProtocolException) { protocol.put("unknown_kind_request") }
                    val current = options(id)
                    val raw = obj("version" to 1, "fit_id" to id, "revision" to current.revision,
                        "capacity" to current.capacity, "groups" to array(current.groups.map { group ->
                            obj("kind" to group.kind, "name" to group.name, "current" to group.current,
                                "choices" to array(group.choices.map { obj("id" to it.id, "name" to it.name) }))
                        }))
                    BridgeCodec.decodeSubsystemOptions(raw.toString())
                    for (label in listOf("wrong_current", "duplicate_group", "wrong_capacity", "extra_field")) {
                        val broken = JSONObject(raw.toString())
                        when (label) {
                            "wrong_current" -> broken.getJSONArray("groups").getJSONObject(0).put("current", 999999)
                            "duplicate_group" -> broken.getJSONArray("groups").put(broken.getJSONArray("groups").getJSONObject(0))
                            "wrong_capacity" -> broken.put("capacity", 3)
                            else -> broken.put("unexpected", true)
                        }
                        try { BridgeCodec.decodeSubsystemOptions(broken.toString()); fail("Accepted $label") }
                        catch (_: BridgeProtocolException) { protocol.put(label) }
                    }
                    checks.put("typed_subsystem_protocol")
                    EngineRuntime.selectFit(context, invalidCopy).get(30, TimeUnit.SECONDS)
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    ids = array(listOf(id, invalidCopy, vexor))
                    saved.writeText(obj("fits" to library(), "new_ids" to ids, "invalid_id" to invalidCopy,
                        "active_id" to invalidCopy, "prior" to before).toString(), Charsets.UTF_8)
                }
                "restored" -> {
                    val expected = JSONObject(saved.readText(Charsets.UTF_8))
                    compare(expected.getJSONObject("fits"), library(), strict = false)
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    ids = expected.getJSONArray("new_ids")
                    val invalidId = expected.getString("invalid_id")
                    open(invalidId)
                    val retained = details(invalidId).modules.single { it.name == "Heavy Missile Launcher II" }
                    assertEquals(false, retained.legal)
                    assertEquals("Scourge Heavy Missile", retained.charge)
                    assertEquals(ModuleState.ACTIVE, retained.state)
                    compose.onNodeWithTag("subsystems-illegal").assertTextContains("Heavy Missile Launcher II", substring = true)
                    compose.onNodeWithTag("subsystems-illegal").performScrollTo().assertIsDisplayed()
                    screenshot("restored-invalid-copy")
                    click("subsystems-back")
                    for (i in 0 until ids.length()) {
                        val id = ids.getString(i)
                        open(id); assertEquals(id, model.options?.fitId); click("subsystems-back")
                    }
                    checks.put("fresh_process_restore"); checks.put("reopen_each_fit")
                }
                else -> error("Unknown phase")
            }
            retain(obj("task" to "B06.2", "phase" to phase, "pid" to Process.myPid(),
                "runtime_start" to runtimeStart, "runtime_end" to diagnostics(),
                "before" to before, "after" to library(), "steps" to rows,
                "new_ids" to ids, "checks" to checks, "rejections" to rejected,
                "protocol_rejections" to protocol,
                "saved" to JSONObject(saved.readText(Charsets.UTF_8))), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
