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
class CargoStackTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[CargoEditorModel::class.java]
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
        "B07.1 $ship – 探索", ship, 5, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
        Security(SystemSecurity.HISEC, 0.0), emptyList(), emptyList()))).fits.single().id
    private fun details(id: String) = EngineRuntime.cargoDetails(context, id).get(120, TimeUnit.SECONDS)
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        sync(); click("cargo-open")
        waitFor { !model.loading && model.details?.fitId == id && model.details?.revision == fit(id).revision }
    }
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b071-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b071-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use {
                it.write(value.toString(2).toByteArray(Charsets.UTF_8))
            }
            completion.readBytes()
        }
    }
    private fun state(id: String): JSONObject {
        val current = details(id)
        return obj("cargo" to array(current.cargo.map { obj("id" to it.id, "name" to it.name,
            "amount" to it.amount, "unit_volume_m3" to it.unitVolumeM3) }),
            "used_m3" to current.usedM3, "capacity_m3" to current.capacityM3,
            "stats" to stats(fit(id)))
    }
    private fun step(rows: JSONArray, id: String, operation: List<Any>?, accepted: Boolean = true) {
        rows.put(obj("operation" to operation?.let(::array), "accepted" to accepted,
            "result" to state(id)))
    }
    private fun action(rows: JSONArray, id: String, name: String, item: Int, amount: Long,
                       accepted: Boolean = true) {
        val operation = when (name) {
            "add" -> BridgeOperation.AddCargo(id, item, amount)
            "set" -> BridgeOperation.SetCargoQuantity(id, item, amount)
            "remove" -> BridgeOperation.RemoveCargo(id, item, amount)
            else -> error(name)
        }
        send(operation, listOf(id), accepted)
        val label = when (item) { 222 -> "Antimatter Charge S"; 2889 -> "200mm AutoCannon II"
            3297 -> "Small Standard Container"; else -> error("Unknown test item") }
        step(rows, id, listOf(name, label, amount), accepted)
    }

    @Test fun cargoStacksMatchDesktopAndRestoreOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b071_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val before = library(); val runtimeStart = diagnostics()
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("enabled"))
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("opened_existing"))
        val saved = File(context.noBackupFilesDir, "b071-test-expected.json")
        val checks = JSONArray(); val rejected = JSONArray(); val protocol = JSONArray()
        val cases = JSONArray(); var ids = JSONArray()
        val restoredCargo = JSONObject()
        try {
            when (phase) {
                "prepare" -> {
                    val vexor = create("Vexor")
                    open(vexor)
                    compose.onNodeWithTag("cargo-volume").assertTextContains("480", substring = true)
                    compose.onNodeWithTag("cargo-empty").assertExists()
                    screenshot("vexor-empty")
                    val vexorSteps = JSONArray(); step(vexorSteps, vexor, null)
                    click("cargo-browse")
                    val equipment = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
                    waitFor { equipment.catalog != null && !equipment.busy }
                    compose.onNodeWithTag("equipment-search").performTextInput("Antimatter Charge S")
                    click("equipment-search-submit")
                    waitFor { !equipment.busy && equipment.searched == "Antimatter Charge S" }
                    click("equipment-item-222")
                    click("equipment-add-cargo")
                    waitFor { !model.loading && !model.editing && model.details?.revision == fit(vexor).revision &&
                        model.details?.cargo?.singleOrNull()?.amount == 1L }
                    screenshot("vexor-first-stack")
                    step(vexorSteps, vexor, listOf("add", "Antimatter Charge S", 1))
                    action(vexorSteps, vexor, "add", 222, 9)
                    waitFor { !model.loading && model.details?.revision == fit(vexor).revision }
                    compose.onNodeWithTag("cargo-quantity-222").performTextClearance()
                    compose.onNodeWithTag("cargo-quantity-222").performTextInput("1500")
                    click("cargo-set-222")
                    waitFor { !model.loading && !model.editing && model.details?.revision == fit(vexor).revision &&
                        model.details?.cargo?.singleOrNull()?.amount == 1500L }
                    compose.onNodeWithTag("cargo-volume").performScrollTo().assertIsDisplayed()
                    screenshot("vexor-quantity")
                    step(vexorSteps, vexor, listOf("set", "Antimatter Charge S", 1500))
                    compose.onNodeWithTag("cargo-remove-quantity-222").performTextClearance()
                    compose.onNodeWithTag("cargo-remove-quantity-222").performTextInput("10")
                    click("cargo-remove-part-222")
                    waitFor { !model.loading && !model.editing && model.details?.revision == fit(vexor).revision &&
                        model.details?.cargo?.singleOrNull()?.amount == 1490L }
                    step(vexorSteps, vexor, listOf("remove", "Antimatter Charge S", 10))
                    action(vexorSteps, vexor, "add", 2889, 2)
                    action(vexorSteps, vexor, "add", 3297, 1)
                    waitFor { !model.loading && model.details?.revision == fit(vexor).revision }
                    compose.onNodeWithTag("cargo-remove-quantity-222").performTextClearance()
                    compose.onNodeWithTag("cargo-remove-quantity-222").performTextInput("10000")
                    click("cargo-remove-part-222")
                    waitFor { !model.loading && !model.editing && model.details?.revision == fit(vexor).revision &&
                        model.details?.cargo?.none { it.id == 222 } == true }
                    step(vexorSteps, vexor, listOf("remove", "Antimatter Charge S", 10000))
                    action(vexorSteps, vexor, "set", 2889, 1)
                    action(vexorSteps, vexor, "remove", 2889, 1)
                    action(vexorSteps, vexor, "remove", 2889, 1, false)
                    action(vexorSteps, vexor, "add", 3297, 4)
                    waitFor { !model.loading && model.details?.revision == fit(vexor).revision }
                    compose.onNodeWithTag("cargo-over-capacity").assertExists()
                    compose.onNodeWithTag("cargo-volume").assertTextContains("500", substring = true)
                    compose.onNodeWithTag("cargo-volume").performScrollTo().assertIsDisplayed()
                    screenshot("vexor-over-capacity")
                    action(vexorSteps, vexor, "set", 3297, 1)
                    cases.put(obj("ship" to "Vexor", "steps" to vexorSteps))
                    click("cargo-back")

                    val astrahus = create("Astrahus")
                    open(astrahus)
                    compose.onNodeWithTag("cargo-volume").assertTextContains("0 m³", substring = true)
                    val astrahusSteps = JSONArray(); step(astrahusSteps, astrahus, null)
                    action(astrahusSteps, astrahus, "add", 222, 1000)
                    waitFor { !model.loading && model.details?.revision == fit(astrahus).revision }
                    compose.onNodeWithTag("cargo-over-capacity").assertExists()
                    compose.onNodeWithTag("cargo-volume").performScrollTo().assertIsDisplayed()
                    screenshot("structure-charge")
                    action(astrahusSteps, astrahus, "add", 222, 1)
                    waitFor { !model.loading && model.details?.revision == fit(astrahus).revision }
                    click("cargo-remove-all-222")
                    waitFor { !model.loading && !model.editing && model.details?.revision == fit(astrahus).revision &&
                        model.details?.cargo?.isEmpty() == true }
                    step(astrahusSteps, astrahus, listOf("remove", "Antimatter Charge S", 1001))
                    cases.put(obj("ship" to "Astrahus", "steps" to astrahusSteps))
                    val copy = send(BridgeOperation.DuplicateFit(vexor, "B07.1 cargo copy – Δ"),
                        listOf(vexor)).fits.single { it.name == "B07.1 cargo copy – Δ" }.id
                    compare(state(vexor), state(copy))
                    checks.put("two_original_cargo_sequences")
                    checks.put("touch_add_set_partial_remove_and_over_capacity")
                    checks.put("durable_cargo_copy")
                    val committed = library()
                    val invalid = send(BridgeOperation.AddCargo(vexor, 222, 0), listOf(vexor), false)
                    rejected.put(obj("label" to "zero_quantity", "code" to invalid.error?.code?.name))
                    val structure = send(BridgeOperation.AddCargo(astrahus, 2889, 1), listOf(astrahus), false)
                    rejected.put(obj("label" to "structure_module", "code" to structure.error?.code?.name))
                    val stale = EngineRuntime.request(context, BridgeOperation.AddCargo(vexor, 222, 1),
                        mapOf(vexor to 0L)).get(120, TimeUnit.SECONDS)
                    assertFalse(stale.isSuccess)
                    rejected.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    compare(committed, library())
                    checks.put("atomic_rejections")
                    val current = details(vexor)
                    val raw = obj("version" to 1, "fit_id" to vexor, "revision" to current.revision,
                        "is_structure" to current.isStructure, "capacity_m3" to current.capacityM3,
                        "used_m3" to current.usedM3, "over_capacity" to current.overCapacity,
                        "cargo" to array(current.cargo.map { obj("id" to it.id, "name" to it.name,
                            "amount" to it.amount, "unit_volume_m3" to it.unitVolumeM3) }))
                    BridgeCodec.decodeCargoDetails(raw.toString())
                    for (label in listOf("duplicate_stack", "zero_amount", "negative_volume",
                        "wrong_over", "wrong_version", "extra_field")) {
                        val broken = JSONObject(raw.toString())
                        when (label) {
                            "duplicate_stack" -> broken.getJSONArray("cargo").put(broken.getJSONArray("cargo").getJSONObject(0))
                            "zero_amount" -> broken.getJSONArray("cargo").getJSONObject(0).put("amount", 0)
                            "negative_volume" -> broken.put("used_m3", -1)
                            "wrong_over" -> broken.put("over_capacity", true)
                            "wrong_version" -> broken.put("version", 2)
                            else -> broken.put("unexpected", true)
                        }
                        try { BridgeCodec.decodeCargoDetails(broken.toString()); fail("Accepted $label") }
                        catch (_: BridgeProtocolException) { protocol.put(label) }
                    }
                    checks.put("typed_cargo_protocol")
                    EngineRuntime.selectFit(context, copy).get(30, TimeUnit.SECONDS)
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    ids = array(listOf(vexor, astrahus, copy))
                    saved.writeText(obj("fits" to library(), "new_ids" to ids, "copy_id" to copy,
                        "active_id" to copy, "prior" to before,
                        "cargo_states" to obj(*listOf(vexor, astrahus, copy).map { it to typed(state(it)) }.toTypedArray())
                    ).toString(), Charsets.UTF_8)
                }
                "restored" -> {
                    val expected = JSONObject(saved.readText(Charsets.UTF_8))
                    compare(expected.getJSONObject("fits"), library(), strict = false)
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    ids = expected.getJSONArray("new_ids")
                    val copy = expected.getString("copy_id")
                    open(copy)
                    assertEquals(100.0, details(copy).usedM3, 1e-9)
                    compose.onNodeWithTag("cargo-volume").assertTextContains("100", substring = true)
                    screenshot("restored-cargo-copy")
                    click("cargo-back")
                    for (index in 0 until ids.length()) {
                        val id = ids.getString(index)
                        open(id); assertEquals(id, model.details?.fitId)
                        // JSONObject writes integral decimals without a decimal point.
                        // The typed wrapper retains numeric kinds across that serialization.
                        val restoredState = typed(state(id))
                        compare(expected.getJSONObject("cargo_states").getJSONObject(id), restoredState, strict = false)
                        restoredCargo.put(id, restoredState)
                        click("cargo-back")
                    }
                    checks.put("fresh_process_restore"); checks.put("reopen_each_fit")
                }
                else -> error("Unknown phase")
            }
            retain(obj("task" to "B07.1", "phase" to phase, "pid" to Process.myPid(),
                "runtime_start" to runtimeStart, "runtime_end" to diagnostics(),
                "before" to before, "after" to library(), "cases" to cases,
                "new_ids" to ids, "checks" to checks, "rejections" to rejected,
                "protocol_rejections" to protocol,
                "restored_cargo" to restoredCargo,
                "saved" to JSONObject(saved.readText(Charsets.UTF_8))), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
