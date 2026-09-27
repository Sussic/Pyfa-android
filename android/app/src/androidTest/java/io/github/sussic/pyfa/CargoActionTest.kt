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
class CargoActionTest {
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
    private fun create(ship: String, name: String): String = send(BridgeOperation.CreateFit(FitSpec(
        "B07.2 $name – 探索", ship, 5, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
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
            "screencap -p /sdcard/Download/pyfa-b072-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b072-$phase.json")
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
            "stats" to stats(fit(id)), "recent" to array(EngineRuntime.recent.value))
    }

    private val itemIds = mapOf("Antimatter Charge S" to 222, "Core Scanner Probe I" to 30013,
        "200mm AutoCannon I" to 486, "200mm AutoCannon II" to 2889, "Multifrequency S" to 246,
        "Small Standard Container" to 3297)
    private fun item(name: String) = itemIds.getValue(name)
    private fun ready(id: String) {
        waitFor { !model.loading && !model.editing &&
            model.details?.fitId == id && model.details?.revision == fit(id).revision }
        compose.onNodeWithTag("cargo-back").assertExists()
    }
    private fun selection(names: JSONArray) {
        click("cargo-clear-selection")
        for (index in 0 until names.length()) click("cargo-select-${item(names.getString(index))}")
    }
    private fun options(id: String, itemId: Int, cargo: Boolean): CargoActionOptions {
        waitFor { !model.actionsLoading && model.actions?.let {
            it.fitId == id && it.revision == fit(id).revision && it.itemId == itemId && it.fromCargo == cargo
        } == true }
        return model.actions!!
    }
    private fun browse(id: String, name: String): CargoActionOptions {
        click("cargo-browse")
        val equipment = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
        waitFor { equipment.catalog != null && !equipment.busy }
        compose.onNodeWithTag("equipment-search").performTextClearance()
        compose.onNodeWithTag("equipment-search").performTextInput(name)
        click("equipment-search-submit")
        waitFor { !equipment.busy && equipment.searched == name }
        click("equipment-item-${item(name)}")
        return options(id, item(name), false)
    }
    private fun backFromSearch(id: String) {
        val equipment = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
        assertNotNull(equipment.selectedId); assertNotNull(equipment.searched); assertNull(equipment.groupId)
        click("equipment-back") // Selected item -> search results.
        assertNull(equipment.selectedId)
        click("equipment-back") // Search results -> market root.
        assertNull(equipment.searched)
        click("equipment-back") // Market root -> cargo.
        ready(id)
    }
    private fun act(id: String, operation: JSONObject, outcome: JSONObject): JSONObject? {
        ready(id)
        val kind = operation.getString("kind")
        val oldRevision = fit(id).revision
        var changesRevision = true
        var query: CargoActionOptions? = null
        when (kind) {
            "add" -> send(BridgeOperation.AddCargo(id, item(operation.getString("item")),
                operation.getLong("quantity")), listOf(id))
            "quantity", "remove" -> {
                selection(operation.getJSONArray("selected"))
                if (kind == "quantity") {
                    compose.onNodeWithTag("cargo-selected-quantity").performScrollTo().performTextReplacement(
                        operation.getLong("quantity").toString())
                    click("cargo-set-selected")
                } else click("cargo-remove-selected")
            }
            "preset", "fill_market" -> {
                val name = operation.getString("item")
                query = browse(id, name)
                val tag = if (kind == "preset") "equipment-cargo-preset" else "equipment-cargo-fill"
                if (!outcome.getBoolean("visible")) {
                    compose.onNodeWithTag(tag).assertDoesNotExist()
                    backFromSearch(id); changesRevision = false
                } else if (kind == "fill_market" && query.fillQuantity == 0L) {
                    compose.onNodeWithTag(tag).assertIsNotEnabled()
                    backFromSearch(id)
                    send(BridgeOperation.FillCargo(id, item(name), false), listOf(id))
                } else click(tag)
            }
            "fill_cargo" -> {
                val itemId = item(operation.getString("item"))
                selection(array(listOf(operation.getString("item"))))
                query = options(id, itemId, true)
                if (query.fillQuantity == 0L) {
                    compose.onNodeWithTag("cargo-fill-selected").assertIsNotEnabled()
                    send(BridgeOperation.FillCargo(id, itemId, true), listOf(id))
                } else click("cargo-fill-selected")
            }
            "variation" -> {
                selection(operation.getJSONArray("selected"))
                query = options(id, item(operation.getString("main")), true)
                click("cargo-variations")
                click("cargo-variation-${item(operation.getString("item"))}")
            }
            else -> error(kind)
        }
        if (changesRevision) waitFor { fit(id).revision > oldRevision }
        ready(id)
        assertNull(model.error)
        return query?.let { obj("item_id" to it.itemId, "from_cargo" to it.fromCargo,
            "preset_quantity" to it.presetQuantity, "fill_quantity" to it.fillQuantity,
            "variations" to array(it.variations.map { row -> obj("id" to row.id, "name" to row.name,
                "group" to row.group, "enabled" to row.enabled) })) }
    }
    private fun protocol(id: String): JSONArray {
        val result = JSONArray()
        val raw = obj("version" to 1, "fit_id" to id, "revision" to fit(id).revision,
            "item_id" to 222, "from_cargo" to false, "preset_quantity" to 1000L,
            "fill_quantity" to 0L, "variations" to JSONArray())
        BridgeCodec.decodeCargoActionOptions(raw.toString())
        for (name in listOf("wrong_version", "extra_field", "negative_fill", "invalid_preset",
            "wrong_context", "boolean_item", "zero_revision", "missing_fill")) {
            val broken = JSONObject(raw.toString())
            when (name) {
                "wrong_version" -> broken.put("version", 2)
                "extra_field" -> broken.put("extra", true)
                "negative_fill" -> broken.put("fill_quantity", -1)
                "invalid_preset" -> broken.put("preset_quantity", 1)
                "wrong_context" -> broken.put("from_cargo", true)
                "boolean_item" -> broken.put("item_id", true)
                "zero_revision" -> broken.put("revision", 0)
                else -> broken.remove("fill_quantity")
            }
            try { BridgeCodec.decodeCargoActionOptions(broken.toString()); fail("Accepted $name") }
            catch (_: BridgeProtocolException) { result.put(name) }
        }
        return result
    }

    @Test fun cargoActionsMatchDesktopAndRestoreOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b072_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val before = library(); val runtimeStart = diagnostics()
        val recentBefore = array(EngineRuntime.recent.value)
        val saved = File(context.noBackupFilesDir, "b072-test-expected.json")
        val checks = JSONArray(); val rejected = JSONArray(); var guards = JSONArray()
        val cases = JSONArray(); var ids = JSONArray(); val restoredCargo = JSONObject()
        try {
            when (phase) {
                "prepare" -> {
                    val fixture = JSONObject(InstrumentationRegistry.getInstrumentation().context.assets
                        .open("cargo-actions-expected.json").bufferedReader().use { it.readText() }).getJSONArray("cases")
                    val states = JSONObject()
                    var copy = ""
                    for (caseIndex in 0 until fixture.length()) {
                        val case = fixture.getJSONObject(caseIndex)
                        val id = create(case.getString("ship"), case.getString("name"))
                        ids.put(id); open(id)
                        val steps = JSONArray().put(obj("operation" to null, "options" to null, "result" to state(id)))
                        val original = case.getJSONArray("steps")
                        for (index in 1 until original.length()) {
                            val step = original.getJSONObject(index)
                            val operation = step.getJSONObject("operation")
                            val observedOptions = act(id, operation, step.getJSONObject("outcome"))
                            steps.put(obj("operation" to operation, "options" to observedOptions, "result" to state(id)))
                            val picture = when (caseIndex to index) {
                                0 to 4 -> "selected-quantity"
                                1 to 2 -> "crystal-preset"
                                2 to 2 -> "filled-cargo"
                                3 to 4 -> "variation-merge"
                                4 to 1 -> "structure-preset"
                                else -> null
                            }
                            if (picture != null) {
                                val tag = when (picture) {
                                    "crystal-preset" -> "cargo-stack-246"
                                    "variation-merge" -> "cargo-stack-2889"
                                    else -> "cargo-volume"
                                }
                                compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed()
                                screenshot(picture)
                            }
                        }
                        cases.put(obj("name" to case.getString("name"), "ship" to case.getString("ship"), "steps" to steps))
                        states.put(id, typed(state(id)))
                        val copyName = "B07.2 copy ${case.getString("name")} – Δ"
                        copy = send(BridgeOperation.DuplicateFit(id, copyName), listOf(id)).fits.single { it.name == copyName }.id
                        compare(state(id), state(copy)); states.put(copy, typed(state(copy))); ids.put(copy)
                        click("cargo-back")
                    }
                    checks.put("five_original_cargo_action_sequences")
                    checks.put("touch_selected_quantity_remove_presets_fill_and_variations")
                    checks.put("durable_cargo_copies")
                    val id = ids.getString(6) // Variation case retains ammunition and a module.
                    val committed = library(); val committedRecent = array(EngineRuntime.recent.value)
                    for ((label, operation) in listOf(
                        "duplicate_selection" to BridgeOperation.RemoveCargos(id, listOf(222, 222)),
                        "missing_stack" to BridgeOperation.SetCargoQuantities(id, listOf(222, 2889), 2),
                        "wrong_variation" to BridgeOperation.ChangeCargoVariations(id, 486, listOf(486, 222), 222))) {
                        val response = send(operation, listOf(id), false)
                        rejected.put(obj("label" to label, "code" to response.error?.code?.name))
                    }
                    val stale = EngineRuntime.request(context, BridgeOperation.RemoveCargos(id, listOf(222)),
                        mapOf(id to 0L)).get(120, TimeUnit.SECONDS)
                    assertFalse(stale.isSuccess)
                    rejected.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    compare(committed, library()); compare(committedRecent, array(EngineRuntime.recent.value))
                    checks.put("atomic_rejections"); guards = protocol(id); checks.put("typed_cargo_actions_protocol")
                    EngineRuntime.selectFit(context, copy).get(30, TimeUnit.SECONDS)
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    for (index in 0 until ids.length()) {
                        val savedId = ids.getString(index)
                        states.put(savedId, typed(state(savedId)))
                    }
                    saved.writeText(obj("fits" to library(), "new_ids" to ids, "active_id" to copy,
                        "prior" to before, "cargo_states" to states,
                        "recent" to array(EngineRuntime.recent.value)).toString(), Charsets.UTF_8)
                }
                "restored" -> {
                    val expected = JSONObject(saved.readText(Charsets.UTF_8))
                    compare(expected.getJSONObject("fits"), library(), strict = false)
                    compare(expected.getJSONArray("recent"), array(EngineRuntime.recent.value))
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    ids = expected.getJSONArray("new_ids")
                    for (index in 0 until ids.length()) {
                        val id = ids.getString(index)
                        open(id)
                        val actual = typed(state(id))
                        val prior = expected.getJSONObject("cargo_states").getJSONObject(id)
                        compare(prior, actual, strict = false); restoredCargo.put(id, actual)
                        if (index == 7) {
                            compose.onNodeWithTag("cargo-stack-486").performScrollTo().assertIsDisplayed()
                            screenshot("restored-variation-copy")
                        }
                        click("cargo-back")
                    }
                    checks.put("fresh_process_restore"); checks.put("reopen_each_fit")
                }
                else -> error(phase)
            }
            retain(obj("task" to "B07.2", "phase" to phase, "pid" to Process.myPid(),
                "runtime_start" to runtimeStart, "runtime_end" to diagnostics(),
                "before" to before, "after" to library(), "cases" to cases, "new_ids" to ids,
                "checks" to checks, "rejections" to rejected, "protocol_rejections" to guards,
                "recent_before" to recentBefore, "recent_after" to array(EngineRuntime.recent.value),
                "restored_cargo" to restoredCargo, "saved" to JSONObject(saved.readText(Charsets.UTF_8))), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
