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
class HullModeTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[ModeEditorModel::class.java]
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
        "B06.1 $ship – 探索", ship, 5, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
        Security(SystemSecurity.HISEC, 0.0), emptyList(), emptyList()))).fits.single().id
    private fun options(id: String) = EngineRuntime.modeOptions(context, id).get(120, TimeUnit.SECONDS)
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        sync(); click("modes-open")
        waitFor { !model.loading && model.options?.fitId == id && model.options?.revision == fit(id).revision }
    }
    private fun screenshot(name: String) {
        sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b061-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b061-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use {
                it.write(value.toString(2).toByteArray(Charsets.UTF_8))
            }
            completion.readBytes()
        }
    }
    private fun state(id: String, requested: Int?) = obj("requested" to requested,
        "current" to options(id).current, "stats" to stats(fit(id)))

    @Test fun hullModesMatchDesktopAndRestoreOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b061_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val before = library(); val runtimeStart = diagnostics()
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("enabled"))
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("opened_existing"))
        val saved = File(context.noBackupFilesDir, "b061-test-expected.json")
        val checks = JSONArray(); val rejected = JSONArray(); val protocol = JSONArray()
        val cases = JSONArray(); var ids = JSONArray()
        try {
            when (phase) {
                "prepare" -> {
                    val keys = mutableMapOf<String, String>()
                    for (ship in listOf("Confessor", "Jackdaw", "Anhinga", "Vexor")) {
                        val id = create(ship); keys[ship] = id
                        val available = options(id)
                        val steps = JSONArray().put(state(id, null))
                        if (ship == "Confessor") {
                            open(id)
                            compose.onNodeWithTag("modes-current").assertTextContains("Defense Mode", substring = true)
                            screenshot("confessor-initial")
                        }
                        for ((index, choice) in available.choices.withIndex()) {
                            if (ship == "Confessor" && index == 1) {
                                click("modes-choice-${choice.id}")
                                waitFor { !model.loading && !model.editing && model.error == null &&
                                    model.options?.revision == fit(id).revision && model.options?.current == choice.id }
                                screenshot("confessor-changed")
                            } else {
                                send(BridgeOperation.ChangeMode(id, choice.id), listOf(id))
                                if (ship == "Confessor") waitFor {
                                    !model.loading && model.options?.revision == fit(id).revision
                                }
                            }
                            assertEquals(choice.id, options(id).current)
                            steps.put(state(id, choice.id))
                        }
                        if (available.choices.isNotEmpty()) {
                            val first = available.choices.first()
                            send(BridgeOperation.ChangeMode(id, first.id), listOf(id))
                            steps.put(state(id, first.id))
                        }
                        if (ship == "Confessor") click("modes-back")
                        if (ship == "Vexor") {
                            open(id); compose.onNodeWithTag("modes-empty").assertIsDisplayed()
                            screenshot("vexor-empty"); click("modes-back")
                        }
                        cases.put(obj("ship" to ship, "id" to id,
                            "choices" to array(available.choices.map { obj("id" to it.id, "name" to it.name) }),
                            "steps" to steps))
                    }
                    checks.put("all_original_mode_states_and_choices")
                    val source = keys.getValue("Confessor")
                    val nonDefault = options(source).choices[2]
                    send(BridgeOperation.ChangeMode(source, nonDefault.id), listOf(source))
                    val copy = send(BridgeOperation.DuplicateFit(source, "B06.1 copied mode – Δ"), listOf(source))
                        .fits.single { it.name == "B06.1 copied mode – Δ" }.id
                    assertEquals(nonDefault.id, options(copy).current)
                    compare(stats(fit(source)), stats(fit(copy)))
                    checks.put("copy_keeps_selected_mode")

                    val committed = library()
                    val invalid = send(BridgeOperation.ChangeMode(source, options(keys.getValue("Jackdaw")).choices[0].id),
                        listOf(source), false)
                    rejected.put(obj("label" to "cross_hull", "code" to invalid.error?.code?.name))
                    val stale = EngineRuntime.request(context, BridgeOperation.ChangeMode(source, nonDefault.id),
                        mapOf(source to 0L)).get(120, TimeUnit.SECONDS)
                    assertEquals(BridgeErrorCode.REVISION_CONFLICT, stale.error?.code)
                    rejected.put(obj("label" to "stale", "code" to stale.error?.code?.name))
                    compare(committed, library())
                    checks.put("atomic_rejections")

                    try {
                        BridgeCodec.encodeRequest(BridgeRequest("b061-negative", runtimeStart.getString("session_id"),
                            BridgeOperation.ChangeMode(source, -1), mapOf(source to fit(source).revision)))
                        fail("Accepted negative mode ID")
                    } catch (_: BridgeProtocolException) { protocol.put("negative_request") }
                    val original = options(source)
                    val raw = obj("version" to 1, "fit_id" to source, "revision" to original.revision,
                        "current" to original.current,
                        "choices" to array(original.choices.map { obj("id" to it.id, "name" to it.name) }))
                    BridgeCodec.decodeModeOptions(raw.toString())
                    for (label in listOf("wrong_current", "duplicate_choice", "extra_field")) {
                        val broken = JSONObject(raw.toString())
                        when (label) {
                            "wrong_current" -> broken.put("current", 999999)
                            "duplicate_choice" -> broken.getJSONArray("choices").put(broken.getJSONArray("choices").getJSONObject(0))
                            else -> broken.put("unexpected", true)
                        }
                        try { BridgeCodec.decodeModeOptions(broken.toString()); fail("Accepted $label") }
                        catch (_: BridgeProtocolException) { protocol.put(label) }
                    }
                    checks.put("typed_mode_protocol")
                    EngineRuntime.selectFit(context, copy).get(30, TimeUnit.SECONDS)
                    EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                    ids = array(listOf(keys.getValue("Confessor"), keys.getValue("Jackdaw"),
                        keys.getValue("Anhinga"), keys.getValue("Vexor"), copy))
                    saved.writeText(obj("fits" to library(), "new_ids" to ids,
                        "copy_mode" to nonDefault.id, "active_id" to copy, "prior" to before).toString(), Charsets.UTF_8)
                }
                "restored" -> {
                    val expected = JSONObject(saved.readText(Charsets.UTF_8))
                    compare(expected.getJSONObject("fits"), library(), strict = false)
                    assertEquals(expected.getString("active_id"), (EngineRuntime.state.value as EngineState.Ready).fit.id)
                    ids = expected.getJSONArray("new_ids")
                    for (i in 0 until ids.length()) {
                        val id = ids.getString(i)
                        open(id)
                        assertEquals(id, model.options?.fitId)
                        if (i == 4) {
                            assertEquals(expected.getInt("copy_mode"), model.options?.current)
                            screenshot("restored-copy")
                        }
                        click("modes-back")
                    }
                    checks.put("fresh_process_restore"); checks.put("reopen_each_fit")
                }
                else -> error("Unknown phase")
            }
            retain(obj("task" to "B06.1", "phase" to phase, "pid" to Process.myPid(),
                "runtime_start" to runtimeStart, "runtime_end" to diagnostics(),
                "before" to before, "after" to library(), "cases" to cases,
                "new_ids" to ids, "checks" to checks, "rejections" to rejected,
                "protocol_rejections" to protocol,
                "saved" to JSONObject(saved.readText(Charsets.UTF_8))), phase)
        } catch (error: Throwable) { screenshot("failure"); throw error }
    }
}
