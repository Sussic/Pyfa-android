package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.os.Process
import android.os.SystemClock
import android.provider.Settings
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.text.AnnotatedString
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.concurrent.CompletableFuture
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
class NotesTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[NotesModel::class.java]
    private fun fits() = EngineRuntime.library.value
    private fun fit(id: String) = fits().single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun waitFor(predicate: () -> Boolean) { compose.waitUntil(60_000, predicate); sync() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().performClick(); sync() }
    private fun library() = typed(array(fits().map(ModuleTestJson::fit)))
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList()): BridgeResponse {
        val result = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess); return result
    }
    private fun details(id: String) = EngineRuntime.noteDetails(context, id).get(120, TimeUnit.SECONDS)
    private fun note(id: String): JSONObject = details(id).let {
        obj("text" to it.text, "characters" to it.characters, "editable" to it.editable)
    }
    private fun ready(id: String) {
        waitFor { model.drafts[id]?.let { it.loaded && !it.loading && !it.saving && it.revision == fit(id).revision } == true }
        compose.onNodeWithTag("notes-text").assertExists()
    }
    private fun open(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS); sync(); click("notes-open"); ready(id)
    }
    private fun type(text: String) { compose.onNodeWithTag("notes-text").performTextReplacement(text); sync() }
    private fun saved(id: String, text: String) {
        waitFor { model.drafts[id]?.let { !it.saving && !it.loading && !it.dirty && it.stored == text } == true }
        assertEquals(text, details(id).text)
    }
    private fun screenshot(name: String, tag: String = "notes-text") {
        compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed(); sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b08-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b08-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(value.toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
    private fun protocol(id: String): JSONArray {
        val good = note(id).apply { put("version", 1); put("fit_id", id); put("revision", fit(id).revision) }
        val labels = listOf("version", "extra", "null_text", "boolean_count", "negative_count", "wrong_count", "decimal_count", "editable", "revision", "surrogate")
        for (label in labels) {
            val bad = JSONObject(good.toString())
            when (label) {
                "version" -> bad.put("version", 2)
                "extra" -> bad.put("extra", 1)
                "null_text" -> bad.put("text", JSONObject.NULL)
                "boolean_count" -> bad.put("characters", true)
                "negative_count" -> bad.put("characters", -1)
                "wrong_count" -> bad.put("characters", good.getInt("characters") + 1)
                "editable" -> bad.put("editable", 1)
                "revision" -> bad.put("revision", 0)
                "surrogate" -> bad.put("text", "\uD800")
            }
            val raw = if (label == "decimal_count") bad.toString().replaceFirst(
                Regex("\"characters\":(\\d+)"), "\"characters\":$1.0") else bad.toString()
            try { BridgeCodec.decodeNoteDetails(raw); fail("Accepted $label") }
            catch (_: BridgeProtocolException) { }
        }
        return array(labels)
    }

    @Test fun notesSaveToCorrectFitsAndRestoreOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("b08_phase") ?: error("Missing phase")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val fixture = JSONObject(InstrumentationRegistry.getInstrumentation().context.assets
            .open("notes-expected.json").bufferedReader().use { it.readText() })
        val inputs = fixture.getJSONObject("inputs")
        val before = library(); val runtimeStart = diagnostics(); val recentBefore = array(EngineRuntime.recent.value)
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("enabled"))
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("opened_existing"))
        assertEquals(if (phase == "prepare") 85 else 90, fits().size)
        val file = File(context.noBackupFilesDir, "b08-test-expected.json")
        val observations = JSONObject(); val checks = JSONArray(); var guards = JSONArray()
        var ids = JSONArray(); val restored = JSONObject()
        try {
            if (phase == "prepare") {
                for (key in listOf("alpha", "beta", "structure")) {
                    val original = fixture.getJSONObject("initial").getJSONObject(key)
                    val spec = FitSpec("B08 $key – 探索", original.getString("ship"), 5, false,
                        DamagePattern(25.0,25.0,25.0,25.0), Security(SystemSecurity.HISEC,0.0), emptyList(),emptyList(),
                        notes = if (original.isNull("notes")) null else original.getString("notes"))
                    ids.put(send(BridgeOperation.CreateFit(spec)).fits.single().id)
                }
                val alpha=ids.getString(0); val beta=ids.getString(1); val structure=ids.getString(2)
                val baselineStats = obj(*(0 until ids.length()).map { ids.getString(it) to typed(ModuleTestJson.stats(fit(ids.getString(it)))) }.toTypedArray())
                open(alpha); observations.put("empty", note(alpha))
                type(inputs.getString("unicode")); saved(alpha,inputs.getString("unicode"))
                observations.put("unicode",note(alpha)); screenshot("unicode-notes")
                // Invoke the real text/back semantics in one UI transaction, before the debounce.
                val back = compose.onNodeWithTag("notes-back").fetchSemanticsNode().config[SemanticsActions.OnClick].action!!
                compose.onNodeWithTag("notes-text").performSemanticsAction(SemanticsActions.SetText) { input ->
                    val started=SystemClock.uptimeMillis()
                    input(AnnotatedString(inputs.getString("whitespace"))); back()
                    assertNull(model.drafts[alpha]!!.timer)
                    assertTrue(SystemClock.uptimeMillis()-started < 1000)
                }
                waitFor { compose.onAllNodesWithTag("notes-back").fetchSemanticsNodes().isEmpty() }
                assertEquals(inputs.getString("whitespace"),details(alpha).text)
                open(alpha); observations.put("quick_back",note(alpha)); screenshot("navigation-return")
                EngineRuntime.selectFit(context,beta).get(30,TimeUnit.SECONDS); ready(beta)
                lateinit var switched: CompletableFuture<Unit>
                compose.onNodeWithTag("notes-text").performSemanticsAction(SemanticsActions.SetText) { input ->
                    input(AnnotatedString(inputs.getString("beta"))); switched=EngineRuntime.selectFit(context,alpha)
                }
                switched.get(30,TimeUnit.SECONDS); ready(alpha); saved(beta,inputs.getString("beta"))
                observations.put("switch",note(beta)); assertEquals(inputs.getString("whitespace"),model.drafts[alpha]!!.text)
                type(""); saved(alpha,""); observations.put("clear",note(alpha))
                type(inputs.getString("long")); compose.activityRule.scenario.recreate(); ready(alpha)
                assertEquals(inputs.getString("long"),model.drafts[alpha]!!.text)
                saved(alpha,inputs.getString("long")); observations.put("recreated",note(alpha)); screenshot("retained-recreation")
                compose.runOnUiThread {
                    model.edit(context,model.drafts[alpha]!!,inputs.getString("unicode"))
                    model.drafts[alpha]!!.revision=0
                    model.save(context,model.drafts[alpha]!!,explicit=true)
                }
                waitFor { model.drafts[alpha]!!.error != null && !model.drafts[alpha]!!.loading }
                assertEquals(inputs.getString("unicode"),model.drafts[alpha]!!.text)
                assertEquals(inputs.getString("long"),details(alpha).text)
                observations.put("stale",obj("draft" to model.drafts[alpha]!!.text,"stored" to note(alpha)))
                screenshot("stale-draft","notes-error"); click("notes-save"); saved(alpha,inputs.getString("unicode"))
                observations.put("retry",note(alpha))
                lateinit var external: CompletableFuture<BridgeResponse>
                compose.onNodeWithTag("notes-text").performSemanticsAction(SemanticsActions.SetText) { input ->
                    input(AnnotatedString(inputs.getString("long")))
                    external=EngineRuntime.request(context,BridgeOperation.SetNotes(alpha,inputs.getString("whitespace")),mapOf(alpha to fit(alpha).revision))
                }
                assertTrue(external.get(30,TimeUnit.SECONDS).isSuccess)
                waitFor { model.drafts[alpha]!!.conflict && !model.drafts[alpha]!!.loading }
                observations.put("conflict",obj("draft" to model.drafts[alpha]!!.text,"stored" to note(alpha)))
                screenshot("conflict-draft","notes-error"); click("notes-use-saved")
                assertEquals(inputs.getString("whitespace"),model.drafts[alpha]!!.text)
                compose.onNodeWithTag("notes-text").performSemanticsAction(SemanticsActions.SetText) { input ->
                    input(AnnotatedString(inputs.getString("long")))
                    external=EngineRuntime.request(context,BridgeOperation.SetNotes(alpha,inputs.getString("unicode")),mapOf(alpha to fit(alpha).revision))
                }
                assertTrue(external.get(30,TimeUnit.SECONDS).isSuccess)
                waitFor { model.drafts[alpha]!!.conflict && !model.drafts[alpha]!!.loading }
                click("notes-save"); saved(alpha,inputs.getString("long"))
                observations.put("conflict_saved_draft",note(alpha))
                click("notes-back"); open(structure)
                observations.put("structure",note(structure)); compose.onNodeWithTag("notes-readonly").assertExists()
                compose.onAllNodesWithTag("notes-save").assertCountEquals(0); screenshot("structure-readonly")
                click("notes-back")
                for (id in listOf(alpha,structure)) {
                    val copy=send(BridgeOperation.DuplicateFit(id,"B08 copy ${if(id==alpha) "alpha" else "structure"} – Δ"),listOf(id))
                        .fits.single { it.name.startsWith("B08 copy") && it.id !in (0 until ids.length()).map(ids::getString) }.id
                    ids.put(copy); compare(note(id),note(copy))
                }
                for(index in 0..2) compare(baselineStats.getJSONObject(ids.getString(index)),typed(ModuleTestJson.stats(fit(ids.getString(index)))))
                checks.put("exact_text_and_character_counts").put("autosave_and_immediate_navigation_flush")
                    .put("correct_fit_switch_and_recreation").put("stale_draft_retry_and_conflict_resolution")
                    .put("structure_readonly_and_durable_copies").put("unchanged_calculations_and_recent_use")
                guards=protocol(alpha); checks.put("typed_notes_protocol")
                EngineRuntime.selectFit(context,ids.getString(3)).get(30,TimeUnit.SECONDS)
                EngineRuntime.navigate(context){it.copy(restore=true)}.get(30,TimeUnit.SECONDS)
                val states=JSONObject()
                for(index in 0 until ids.length()) states.put(ids.getString(index),note(ids.getString(index)))
                file.writeText(obj("fits" to library(),"new_ids" to ids,"prior" to before,"active_id" to ids.getString(3),
                    "notes" to states,"baseline_stats" to baselineStats,"recent" to recentBefore).toString(),Charsets.UTF_8)
            } else {
                assertEquals("restored",phase)
                val expected=JSONObject(file.readText(Charsets.UTF_8)); ids=expected.getJSONArray("new_ids")
                compare(expected.getJSONObject("fits"),library(),strict=false)
                assertEquals(expected.getString("active_id"),(EngineRuntime.state.value as EngineState.Ready).fit.id)
                for(index in 0 until ids.length()) {
                    val id=ids.getString(index); open(id); compare(expected.getJSONObject("notes").getJSONObject(id),note(id))
                    assertEquals(details(id).text,model.drafts[id]!!.text); restored.put(id,note(id))
                    if(index==3) screenshot("restored-copy")
                    click("notes-back")
                }
                checks.put("fresh_process_restore").put("reopen_each_fit")
            }
            compare(recentBefore,array(EngineRuntime.recent.value))
            retain(obj("task" to "B08","phase" to phase,"pid" to Process.myPid(),"runtime_start" to runtimeStart,
                "runtime_end" to diagnostics(),"before" to before,"after" to library(),"new_ids" to ids,
                "observations" to observations,"checks" to checks,"protocol_rejections" to guards,
                "recent_before" to recentBefore,"recent_after" to array(EngineRuntime.recent.value),
                "saved" to JSONObject(file.readText(Charsets.UTF_8)),"restored_notes" to restored),phase)
        } catch(failure:Throwable) {
            val automation=InstrumentationRegistry.getInstrumentation().uiAutomation
            ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand("screencap -p /sdcard/Download/pyfa-b08-failure.png")).use{it.readBytes()}
            throw failure
        }
    }
}
