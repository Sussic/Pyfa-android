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
class CargoTransferTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[CargoEditorModel::class.java].transfers
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
    private fun details(id: String) = EngineRuntime.cargoTransferDetails(context, id).get(120, TimeUnit.SECONDS)
    private fun ready(id: String) {
        waitFor { !model.loading && !model.editing && model.details?.cargo?.fitId == id &&
            model.details?.cargo?.revision == fit(id).revision }
        compose.onNodeWithTag("transfers-back").assertExists()
    }
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        sync(); click("cargo-open"); click("cargo-transfers"); ready(id)
    }
    private fun close() { click("transfers-back"); click("cargo-back") }
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b073-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b073-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use {
                it.write(value.toString(2).toByteArray(Charsets.UTF_8))
            }
            completion.readBytes()
        }
    }
    private fun state(id: String): JSONObject {
        val current = details(id)
        return obj("modules" to array(current.modules.map { obj("index" to it.index, "id" to it.id,
            "name" to it.name, "slot" to it.slot, "state" to it.state.name,
            "charge_id" to it.chargeId, "charge" to it.charge, "charge_amount" to it.chargeAmount, "legal" to it.legal) }),
            "cargo" to array(current.cargo.cargo.map { obj("id" to it.id, "name" to it.name,
                "amount" to it.amount, "unit_volume_m3" to it.unitVolumeM3) }),
            "used_m3" to current.cargo.usedM3, "capacity_m3" to current.cargo.capacityM3,
            "stats" to stats(fit(id)), "recent" to array(EngineRuntime.recent.value))
    }
    private fun create(case: JSONObject): String {
        val initial = case.getJSONArray("steps").getJSONObject(0).getJSONObject("result")
        val modules = initial.getJSONArray("modules")
        val input = (0 until modules.length()).map { modules.getJSONObject(it) }.filter { !it.isNull("id") }
        val id = send(BridgeOperation.CreateFit(FitSpec("B07.3 ${case.getString("name")} – 探索",
            case.getString("ship"), 5, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
            Security(SystemSecurity.HISEC, 0.0), input.map { ModuleSpec(it.getString("name"),
                ModuleState.valueOf(it.getString("state")), if (it.isNull("charge")) null else it.getString("charge")) },
            emptyList()))).fits.single().id
        // Materialize original vacancies without adding/removing any initial item.
        send(BridgeOperation.SetFitRestrictions(id, false), listOf(id))
        val equipment = EngineRuntime.equipmentCatalog(context).get(120, TimeUnit.SECONDS)
        val cargo = case.getJSONArray("cargo")
        for (index in 0 until cargo.length()) {
            val row = cargo.getJSONObject(index)
            val item = equipment.items.single { it.name == row.getString("name") }
            if (details(id).cargo.isStructure && item.category != "Charge") {
                // The desktop fixture contains transferred structure modules.
                // Seed them through the same supported fit-to-cargo workflow.
                send(BridgeOperation.AddModule(id, item.id), listOf(id))
                val position = details(id).modules.single { it.id == item.id }.index
                send(BridgeOperation.TransferCargo(id, CargoTransferDirection.TO_CARGO,
                    listOf(position), null, false), listOf(id))
                if (row.getLong("amount") != 1L)
                    send(BridgeOperation.SetCargoQuantity(id, item.id, row.getLong("amount")), listOf(id))
            } else send(BridgeOperation.AddCargo(id, item.id, row.getLong("amount")), listOf(id))
        }
        return id
    }
    private fun positions(operation: JSONObject): List<Int> = if (operation.has("positions"))
        operation.getJSONArray("positions").let { values -> (0 until values.length()).map { values.getInt(it) } }
        else listOf(operation.getInt("position"))
    private fun act(id: String, step: JSONObject, recreation: Boolean): Boolean {
        ready(id)
        val operation = step.getJSONObject("operation")
        val toCargo = operation.getString("kind") == "to_cargo"
        val indices = positions(operation)
        val item = if (operation.isNull("cargo_item_id")) null else operation.getInt("cargo_item_id")
        val copy = operation.getBoolean("copy")
        val target = details(id).modules[indices.first()]
        val noop = (toCargo && target.id == null) || (item != null && item in listOf(target.id, target.chargeId))
        val accepted = step.getBoolean("changed") || noop
        val before = library(); val recent = array(EngineRuntime.recent.value)
        if (toCargo && target.id == null) {
            // Empty source is an original command no-op; the UI lists fitted modules only.
            send(BridgeOperation.TransferCargo(id, CargoTransferDirection.TO_CARGO, indices, item, copy), listOf(id))
            ready(id)
        } else {
            click(if (toCargo) "transfers-to-cargo" else "transfers-from-cargo")
            for (index in indices) click("transfers-position-$index")
            if (item != null) click("transfers-stack-$item")
            assertEquals(indices.toSet(), model.positions); assertEquals(item, model.cargoId)
            if (recreation) {
                compose.activityRule.scenario.recreate(); ready(id)
                assertEquals(indices.toSet(), model.positions); assertEquals(item, model.cargoId)
                compose.onNodeWithTag("transfers-position-${indices.first()}").performScrollTo()
                screenshot("selected-modules")
            }
            click(if (copy) "transfers-copy" else "transfers-move")
            ready(id)
            if (accepted) {
                assertNull(model.error); assertNotNull(model.message)
            } else {
                assertNotNull(model.error); compare(before, library())
            }
        }
        compare(recent, array(EngineRuntime.recent.value))
        return accepted
    }
    private fun protocol(id: String): JSONArray {
        val value = details(id)
        val raw = state(id).apply {
            remove("stats"); remove("recent")
            put("version", 1); put("fit_id", id); put("revision", fit(id).revision)
            put("is_structure", value.cargo.isStructure); put("over_capacity", value.cargo.overCapacity)
        }
        val result = JSONArray()
        for (label in listOf("wrong_version", "extra_field", "boolean_amount", "negative_amount",
            "unknown_slot", "duplicate_position", "missing_charge_amount", "missing_module_name", "zero_revision")) {
            val broken = JSONObject(raw.toString())
            val module = broken.getJSONArray("modules").getJSONObject(0)
            when (label) {
                "wrong_version" -> broken.put("version", 2)
                "extra_field" -> broken.put("extra", 1)
                "boolean_amount" -> module.put("charge_amount", true)
                "negative_amount" -> module.put("charge_amount", -1)
                "unknown_slot" -> module.put("slot", "unknown")
                "duplicate_position" -> broken.getJSONArray("modules").getJSONObject(1).put("index", 0)
                "missing_charge_amount" -> module.remove("charge_amount")
                "missing_module_name" -> module.remove("name")
                else -> broken.put("revision", 0)
            }
            try { BridgeCodec.decodeCargoTransferDetails(broken.toString()); fail("Accepted $label") }
            catch (_: BridgeProtocolException) { result.put(label) }
        }
        val decimal = raw.toString().replaceFirst(Regex("\"charge_amount\":(\\d+)"), "\"charge_amount\":$1.0")
        try { BridgeCodec.decodeCargoTransferDetails(decimal); fail("Accepted decimal charge count") }
        catch (_: BridgeProtocolException) { result.put("decimal_amount") }
        val mutable = mutableListOf(0)
        val captured = BridgeOperation.TransferCargo(id, CargoTransferDirection.TO_CARGO, mutable, null, true).snapshotArguments()
            as BridgeOperation.TransferCargo
        mutable.add(1); assertEquals(listOf(0), captured.positions)
        return result
    }

    @Test fun cargoTransfersMatchDesktopAndRestoreOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b073_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val fixture = JSONObject(InstrumentationRegistry.getInstrumentation().context.assets
            .open("cargo-transfers-expected.json").bufferedReader().use { it.readText() }).getJSONArray("cases")
        assertEquals(14, fixture.length())
        val before = library(); val runtimeStart = diagnostics()
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("enabled"))
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("opened_existing"))
        assertEquals(if (phase == "prepare") 57 else 85, fits().size)
        val recentBefore = array(EngineRuntime.recent.value)
        val saved = File(context.noBackupFilesDir, "b073-test-expected.json")
        val checks = JSONArray(); val rejected = JSONArray(); var guards = JSONArray()
        val cases = JSONArray(); var ids = JSONArray(); val restoredCargo = JSONObject()
        try {
            when (phase) {
                "prepare" -> {
                    val states = JSONObject()
                    var copy = ""
                    for (caseIndex in 0 until fixture.length()) {
                        val case = fixture.getJSONObject(caseIndex)
                        val id = create(case); ids.put(id); open(id)
                        val steps = JSONArray().put(obj("operation" to null, "accepted" to null, "result" to state(id)))
                        val original = case.getJSONArray("steps")
                        for (index in 1 until original.length()) {
                            val step = original.getJSONObject(index)
                            val accepted = act(id, step, case.getString("name") == "selected-loaded-modules" && index == 1)
                            steps.put(obj("operation" to step.getJSONObject("operation"), "accepted" to accepted, "result" to state(id)))
                            val picture = when (case.getString("name") to index) {
                                "magazine-adjustments" to 1 -> "magazine-swap"
                                "laser-crystal-counts" to 1 -> "single-crystal"
                                "structure-module-cargo" to 2 -> "structure-swap"
                                "illegal-hull-target-and-empty-noops" to (original.length()-1) -> "atomic-rejection"
                                else -> null
                            }
                            if (picture != null) {
                                compose.onNodeWithTag(if (picture == "atomic-rejection") "transfers-error" else "transfers-position-0")
                                    .performScrollTo().assertIsDisplayed()
                                screenshot(picture)
                            }
                        }
                        cases.put(obj("name" to case.getString("name"), "ship" to case.getString("ship"), "steps" to steps))
                        states.put(id, typed(state(id)))
                        val copyName = "B07.3 copy ${case.getString("name")} – Δ"
                        copy = send(BridgeOperation.DuplicateFit(id, copyName), listOf(id)).fits.single { it.name == copyName }.id
                        compare(state(id), state(copy)); states.put(copy, typed(state(copy))); ids.put(copy)
                        close()
                    }
                    checks.put("fourteen_original_transfer_sequences")
                    checks.put("touch_move_copy_swap_selected_and_recreation")
                    checks.put("atomic_desktop_failure_correction")
                    checks.put("durable_transfer_copies")
                    val id = ids.getString(2)
                    val committed = library(); val committedRecent = array(EngineRuntime.recent.value)
                    for ((label, operation) in listOf(
                        "duplicate_positions" to BridgeOperation.TransferCargo(id, CargoTransferDirection.TO_CARGO, listOf(0,0), null, true),
                        "missing_stack" to BridgeOperation.TransferCargo(id, CargoTransferDirection.FROM_CARGO, listOf(0), 222, false),
                        "invalid_destination" to BridgeOperation.TransferCargo(id, CargoTransferDirection.TO_CARGO, listOf(999), null, false))) {
                        val response = send(operation, listOf(id), false)
                        rejected.put(obj("label" to label, "code" to response.error?.code?.name))
                    }
                    val stale = EngineRuntime.request(context, BridgeOperation.TransferCargo(id,
                        CargoTransferDirection.TO_CARGO, listOf(0), null, false), mapOf(id to 0L)).get(120, TimeUnit.SECONDS)
                    assertFalse(stale.isSuccess)
                    rejected.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    compare(committed, library()); compare(committedRecent, array(EngineRuntime.recent.value))
                    checks.put("atomic_rejections"); guards = protocol(id); checks.put("typed_transfer_protocol")
                    checks.put("captured_selection")
                    EngineRuntime.selectFit(context, copy).get(30, TimeUnit.SECONDS)
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    for (index in 0 until ids.length()) {
                        val savedId = ids.getString(index); states.put(savedId, typed(state(savedId)))
                    }
                    saved.writeText(obj("fits" to library(), "new_ids" to ids, "active_id" to copy,
                        "prior" to before, "cargo_states" to states, "recent" to array(EngineRuntime.recent.value)).toString(), Charsets.UTF_8)
                }
                "restored" -> {
                    val expected = JSONObject(saved.readText(Charsets.UTF_8))
                    compare(expected.getJSONObject("fits"), library(), strict = false)
                    compare(expected.getJSONArray("recent"), array(EngineRuntime.recent.value))
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    ids = expected.getJSONArray("new_ids")
                    for (index in 0 until ids.length()) {
                        val id = ids.getString(index); open(id)
                        val actual = typed(state(id))
                        compare(expected.getJSONObject("cargo_states").getJSONObject(id), actual, strict = false)
                        restoredCargo.put(id, actual)
                        if (index == 3) {
                            click("transfers-from-cargo")
                            val stack = details(id).cargo.cargo.first()
                            click("transfers-stack-${stack.id}")
                            screenshot("restored-transfer-copy")
                        }
                        close()
                    }
                    checks.put("fresh_process_restore"); checks.put("reopen_each_fit")
                }
                else -> error(phase)
            }
            retain(obj("task" to "B07.3", "phase" to phase, "pid" to Process.myPid(),
                "runtime_start" to runtimeStart, "runtime_end" to diagnostics(), "before" to before,
                "after" to library(), "cases" to cases, "new_ids" to ids, "checks" to checks,
                "rejections" to rejected, "protocol_rejections" to guards, "recent_before" to recentBefore,
                "recent_after" to array(EngineRuntime.recent.value), "saved" to JSONObject(saved.readText()),
                "restored_cargo" to restoredCargo), phase)
        } catch (failure: Throwable) { screenshot("failure"); throw failure }
    }
}
