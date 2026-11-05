package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.Process as AndroidProcess
import android.provider.Settings
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Deferred SLIDER1 selection, separate from frozen native14. Writer methods need
 * a fresh qualified module438 seed, offline_features_phase=mutation_slider, and
 * retained seed.json copied to no_backup/c10-slider-fixture. Bind its SHA256 and
 * final source manifest with mutation_slider_seed_sha256/source_sha256. Run the
 * reader only after externally proved force-stop and writer PID absence, without
 * reinstall/reseed. This class never prepares fixtures or proves external stop.
 * MainActivity starts before the body: external admission/source/seed gates must
 * prevent premature execution. Same-process readback is not fresh-process proof.
 */
@RunWith(AndroidJUnit4::class)
class MutationSliderPersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[MutationEditorModel::class.java]
    private val oraclePin = "0e9cddf9eb8df1c8c31620167dc4c86596d782a42d9e7859b7edce708d6205e7"
    private val sourcePin = "8b04f3b271e614b3e103853b44a7851a63d79d0e"
    private val databasePin = "e0dc4b3d281bd949f0a8089d587053ad66c0fcef90163cc6988e670d15d01065"
    private val logicalPin = "5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607"
    private val editedAttributeId = 50

    private data class Fixture(val id: String, val row: MutationItem,
        val display: MutationDisplayValue.Available, val initial: Map<Int, Double>,
        val target: Map<Int, Double>, val states: JSONArray, val seedSha256: String,
        val sourceSha256: String, val graphFile: File)

    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it.toInt() and 255) }
    private fun hash(file: File): String = file.inputStream().use { stream ->
        val digest = MessageDigest.getInstance("SHA-256"); val buffer = ByteArray(64 * 1024)
        while (true) { val count = stream.read(buffer); if (count < 0) break; digest.update(buffer, 0, count) }
        digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) }
    }
    private fun shaArgument(name: String) = checkNotNull(InstrumentationRegistry.getArguments().getString(name)) {
        "Bind the qualified $name before launch."
    }.also { assertTrue(it.matches(Regex("[0-9a-f]{64}"))) }
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(30, TimeUnit.SECONDS))
    private fun session(id: String) = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).context.sessionId
    private fun endpointCheckpoint() = File(context.noBackupFilesDir, "c10-slider-fixture/endpoint-checkpoint.json")
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(condition: () -> Boolean) { compose.waitUntil(120_000, condition); compose.waitForIdle() }
    private fun settled(id: String) = waitFor {
        !model.loading && !model.editing && model.current?.let { it.fitId == id && it.revision == fit(id).revision } == true
    }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick(); compose.waitForIdle() }
    private fun field(f: Fixture) = "mutation-value-${f.row.objectKey}-$editedAttributeId"
    private fun slider(f: Fixture) = "mutation-slider-${f.row.objectKey}-$editedAttributeId"
    private fun text(f: Fixture) = compose.onNodeWithTag(field(f)).performScrollTo().fetchSemanticsNode()
        .config[SemanticsProperties.EditableText].text
    private fun progress(f: Fixture) = compose.onNodeWithTag(slider(f)).performScrollTo().fetchSemanticsNode()
        .config[SemanticsProperties.ProgressBarRangeInfo].current
    private fun history(id: String) = EngineRuntime.editHistory(context, id).get(30, TimeUnit.SECONDS)
    private fun graph() = EngineRuntime.defensePersistenceSnapshot(context).get(30, TimeUnit.SECONDS)
    private fun rawRow(id: String) = EngineRuntime.mutationDetails(context, id).get(30, TimeUnit.SECONDS)
        .items.single { it.kind == "module" }
    private fun rolls(rows: JSONArray): Map<Int, Double> = (0 until rows.length()).associate { index ->
        rows.getJSONObject(index).let { it.getInt("attribute_id") to it.getDouble("value") }
    }
    private fun rowRolls(row: MutationItem) = row.attributes.associate { it.attributeId to it.value }
    private fun assertRaw(expected: Map<Int, Double>, actual: Map<Int, Double>) {
        assertEquals(expected.keys, actual.keys)
        expected.forEach { (id, value) -> assertEquals("Exact raw bits for attribute $id", value.toRawBits(), actual.getValue(id).toRawBits()) }
    }
    private fun storedRolls(json: String, f: Fixture) = rolls(JSONObject(json).getJSONObject("records")
        .getJSONObject(f.id).getJSONObject("spec").getJSONArray("modules").getJSONObject(f.row.position)
        .getJSONObject("mutation").getJSONArray("attributes"))

    private fun prepare(reopen: Boolean = false): Fixture {
        assertTrue(BuildConfig.DEBUG)
        val arguments = InstrumentationRegistry.getArguments()
        assertEquals(if (reopen) "mutation_slider_reopen" else "mutation_slider", arguments.getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val bytes = instrumentation.context.assets.open("module438-repeat.raw.json").use { it.readBytes() }
        assertEquals(oraclePin, hash(bytes))
        val oracle = JSONObject(bytes.toString(Charsets.UTF_8))
        assertEquals(sourcePin, oracle.getString("source_commit")); assertEquals(databasePin, oracle.getString("database_sha256"))
        assertEquals(logicalPin, oracle.getString("database_logical_sha256"))
        assertEquals(438, oracle.getInt("base_item_id")); assertEquals(47746, oracle.getInt("mutaplasmid_id"))
        assertEquals(47749, oracle.getInt("resulting_item_id"))
        val states = oracle.getJSONArray("states"); assertEquals(2, states.length())
        assertEquals(.25, states.getJSONObject(0).getDouble("fraction"), 0.0)
        assertEquals(.75, states.getJSONObject(1).getDouble("fraction"), 0.0)
        val initial = rolls(states.getJSONObject(0).getJSONArray("attributes"))
        val target = rolls(states.getJSONObject(1).getJSONArray("attributes"))
        assertEquals(setOf(6, 20, 30, 50), initial.keys); assertEquals(initial.keys, target.keys)

        val seedPin = shaArgument("mutation_slider_seed_sha256")
        val sourceBinding = shaArgument("mutation_slider_source_sha256")
        val seedBytes = File(context.noBackupFilesDir, "c10-slider-fixture/seed.json").readBytes()
        assertEquals(seedPin, hash(seedBytes))
        val seed = JSONObject(seedBytes.toString(Charsets.UTF_8))
        assertEquals(1, seed.getInt("schema_version")); assertEquals("C10.F14.02.UNITS1", seed.getString("task"))
        assertEquals("PREPARED_PENDING_NATIVE_ACCEPTANCE", seed.getString("status"))
        assertTrue(seed.getBoolean("synthetic_inputs_only")); assertFalse(seed.getBoolean("native_acceptance"))
        assertEquals(sourcePin, seed.getString("reference_source_commit")); assertEquals(databasePin, seed.getString("database_sha256"))
        assertEquals(logicalPin, seed.getString("database_logical_sha256"))
        assertEquals(oraclePin, seed.getJSONObject("oracle_asset").getString("sha256"))
        assertTrue(seed.getBoolean("vacancies_normalized_before_initial_capture"))
        val preparedGraph = seed.getJSONObject("graph")
        assertEquals(1, preparedGraph.getInt("fit_count")); assertEquals(1L, preparedGraph.getLong("generation"))
        val graphFile = File(context.noBackupFilesDir, "fits/graph.sqlite3")
        if (!reopen) assertEquals(preparedGraph.getString("sha256"), hash(graphFile))
        val manifest = JSONObject(context.assets.open("engine/manifest.json").bufferedReader().use { it.readText() })
        assertEquals(databasePin, manifest.getString("database_sha256"))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val persistence = diagnostics().getJSONObject("persistence")
        assertTrue(persistence.getBoolean("opened_existing"))
        assertEquals(graphFile.canonicalFile, File(persistence.getString("path")).canonicalFile)
        if (!reopen) assertEquals(1L, persistence.getLong("generation"))
        assertEquals(1, EngineRuntime.library.value.size)
        val observation = seed.getJSONObject("seed_observation")
        val id = observation.getString("fit_id"); assertEquals(id, EngineRuntime.library.value.single().id)
        assertEquals(preparedGraph.getString("fit_name"), fit(id).name); assertEquals("Rifter", fit(id).ship)
        if (!reopen) assertEquals(1L, fit(id).revision)
        assertEquals(0, history(id).undoCount); assertEquals(0, history(id).redoCount)
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        click("mutation-open"); settled(id); assertNull(model.error)
        val row = rawRow(id)
        assertEquals(observation.getString("object_key"), row.objectKey); assertEquals(0, row.position)
        assertEquals(438, row.baseItemId); assertEquals(47746, row.mutaplasmidId)
        if (!reopen) assertRaw(initial, rowRolls(row))
        assertRaw(initial, rolls(observation.getJSONArray("raw_vector")))
        val display = model.current!!.items.single().attributes.single { it.raw.attributeId == editedAttributeId }
            .display as MutationDisplayValue.Available
        // Pinned original Unit leaves CPU's tf scalar unchanged; direction is lower-is-better.
        assertEquals("tf", display.unitLabel); assertFalse(display.higherIsBetter)
        assertEquals(rowRolls(row).getValue(editedAttributeId).toRawBits(), display.value.toRawBits())
        assertTrue(display.minimum < display.sliderBase && display.sliderBase < display.maximum)
        return Fixture(id, row, display, initial, target, states, seedPin, sourceBinding, graphFile).also {
            if (!reopen) assertRaw(initial, storedRolls(graph(), it))
        }
    }

    private fun assertSaved(f: Fixture, expected: Map<Int, Double>) {
        assertRaw(expected, rowRolls(rawRow(f.id))); assertRaw(expected, storedRolls(graph(), f))
    }

    private fun assertOnlyRollChanged(f: Fixture, beforeGraph: String, target: Double) {
        val expected = JSONObject(beforeGraph).getJSONObject("records").getJSONObject(f.id).getJSONObject("spec")
        val rows = expected.getJSONArray("modules").getJSONObject(f.row.position).getJSONObject("mutation").getJSONArray("attributes")
        for (index in 0 until rows.length()) {
            val roll = rows.getJSONObject(index)
            if (roll.getInt("attribute_id") == editedAttributeId) roll.put("value", target)
        }
        assertEquals(expected.toString(), JSONObject(graph()).getJSONObject("records").getJSONObject(f.id).getJSONObject("spec").toString())
    }

    private fun send(f: Fixture, operation: BridgeOperation) {
        val revision = fit(f.id).revision
        val result = EngineRuntime.request(context, operation, mapOf(f.id to revision)).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess)
        waitFor { fit(f.id).revision > revision }; settled(f.id); assertNull(model.error)
    }

    private fun dragBetterEndpoint(f: Fixture) {
        compose.onNodeWithTag(slider(f)).performScrollTo().assertIsEnabled().performTouchInput {
            swipe(center, Offset(width.toFloat() - 1f, center.y), 400)
        }
        compose.waitForIdle()
        assertEquals(1f, progress(f), 0f)
        assertEquals(f.display.minimum.toRawBits(), text(f).toDouble().toRawBits())
    }

    private fun saveEndpointCheckpoint(f: Fixture, expected: Map<Int, Double>) {
        val rawVector = JSONArray()
        expected.toSortedMap().forEach { (id, value) ->
            rawVector.put(JSONObject().put("attribute_id", id).put("value", value).put("raw_bits", value.toRawBits()))
        }
        val checkpoint = JSONObject().put("schema_version", 1).put("task", "C10.F14.02.SLIDER1")
            .put("oracle_sha256", oraclePin).put("reference_source_commit", sourcePin).put("database_sha256", databasePin)
            .put("seed_sha256", f.seedSha256).put("source_manifest_sha256", f.sourceSha256)
            .put("app_apk_sha256", hash(File(context.applicationInfo.sourceDir)))
            .put("test_apk_sha256", hash(File(instrumentation.context.applicationInfo.sourceDir)))
            .put("fit_id", f.id).put("object_key", f.row.objectKey).put("position", f.row.position)
            .put("revision", fit(f.id).revision).put("generation", diagnostics().getJSONObject("persistence").getLong("generation"))
            .put("graph_sha256", hash(f.graphFile)).put("raw_vector", rawVector).put("session", session(f.id))
            .put("writer_pid", AndroidProcess.myPid()).put("writer_start_elapsed_ms", AndroidProcess.getStartElapsedRealtime())
            .put("external_force_stop_required", true).put("writer_death_proved_by_this_test", false)
        endpointCheckpoint().writeText(checkpoint.toString(), Charsets.UTF_8)
        assertEquals(checkpoint.toString(), endpointCheckpoint().readText(Charsets.UTF_8))
    }

    @Test fun touchEndpointSaveIsSparseAndOneUndoableAction() {
        val f = prepare(); val revision = fit(f.id).revision; val beforeGraph = graph()
        assertFalse("Use a fresh prepared writer seed; do not overwrite a prior checkpoint", endpointCheckpoint().exists())
        val beforeRecent = EngineRuntime.recent.value.toList()
        // Rendering and focus must never round the source Double through Float.
        compose.onNodeWithTag(field(f)).performScrollTo().performClick(); compose.waitForIdle()
        click("mutation-save-${f.row.objectKey}"); settled(f.id)
        assertEquals(revision, fit(f.id).revision); assertEquals(beforeGraph, graph()); assertEquals(0, history(f.id).undoCount)
        dragBetterEndpoint(f)
        click("mutation-raw-${f.row.objectKey}-$editedAttributeId")
        assertEquals(f.initial.getValue(editedAttributeId).toRawBits(), text(f).toDouble().toRawBits())
        compose.onNodeWithTag(slider(f)).assertDoesNotExist()
        click("mutation-display-${f.row.objectKey}-$editedAttributeId")
        assertEquals(f.display.value.toRawBits(), text(f).toDouble().toRawBits())
        dragBetterEndpoint(f)
        // Open-dialog draft and its scrolled control survive activity recreation,
        // correlated to this fit/revision/object. This is not process-death proof.
        compose.onNodeWithTag(slider(f)).performScrollTo().assertIsDisplayed()
        val retainedModel = model
        compose.activityRule.scenario.recreate(); settled(f.id)
        assertSame(retainedModel, model)
        compose.onNodeWithTag(slider(f)).assertIsDisplayed()
        assertEquals(f.id, model.current!!.fitId); assertEquals(revision, model.current!!.revision)
        assertEquals(f.row.objectKey, model.current!!.items.single().raw.objectKey)
        assertEquals(f.display.minimum.toRawBits(), text(f).toDouble().toRawBits())
        assertEquals(revision, fit(f.id).revision); assertEquals(beforeGraph, graph()); assertEquals(0, history(f.id).undoCount)
        compose.onNodeWithText("Discard this draft").performScrollTo().performClick(); compose.waitForIdle()
        assertEquals(f.display.value.toRawBits(), text(f).toDouble().toRawBits())
        dragBetterEndpoint(f); click("mutation-close")
        compose.onNodeWithTag(slider(f)).assertDoesNotExist()
        assertEquals(revision, fit(f.id).revision); assertEquals(beforeGraph, graph()); assertEquals(0, history(f.id).undoCount)
        assertSaved(f, f.initial)
        click("mutation-open"); settled(f.id)
        compose.waitForIdle()
        assertEquals(f.display.value.toRawBits(), text(f).toDouble().toRawBits())
        dragBetterEndpoint(f)
        assertEquals(revision, fit(f.id).revision); assertEquals(beforeGraph, graph()); assertEquals(0, history(f.id).undoCount)
        val expected = f.initial.toMutableMap().also { it[editedAttributeId] = f.display.minimum }
        click("mutation-save-${f.row.objectKey}"); waitFor { fit(f.id).revision > revision }; settled(f.id)
        assertNull(model.error); assertEquals(revision + 1, fit(f.id).revision)
        assertSaved(f, expected); assertOnlyRollChanged(f, beforeGraph, f.display.minimum)
        assertEquals(1, history(f.id).undoCount); assertEquals(0, history(f.id).redoCount)
        assertEquals(beforeRecent, EngineRuntime.recent.value)
        send(f, BridgeOperation.Undo(f.id)); assertSaved(f, f.initial)
        assertEquals(0, history(f.id).undoCount); assertEquals(1, history(f.id).redoCount)
        send(f, BridgeOperation.Redo(f.id)); assertSaved(f, expected)
        assertEquals(1, history(f.id).undoCount); assertEquals(0, history(f.id).redoCount)
        saveEndpointCheckpoint(f, expected)
    }

    @Test fun touchEndpointReopensAfterExternallyVerifiedFreshProcess() {
        // These values correlate an external controller's retained stop receipt.
        // They are prerequisites, not in-app evidence of PID absence or force-stop.
        val arguments = InstrumentationRegistry.getArguments()
        assertEquals("true", arguments.getString("mutation_slider_external_force_stop_verified"))
        shaArgument("mutation_slider_external_stop_receipt_sha256")
        val saved = JSONObject(endpointCheckpoint().readText(Charsets.UTF_8))
        val externalPid = checkNotNull(arguments.getString("mutation_slider_external_writer_pid")).toInt()
        val externalStart = checkNotNull(arguments.getString("mutation_slider_external_writer_start_elapsed_ms")).toLong()
        assertEquals(saved.getInt("writer_pid"), externalPid)
        assertEquals(saved.getLong("writer_start_elapsed_ms"), externalStart)
        assertEquals(1, saved.getInt("schema_version")); assertEquals("C10.F14.02.SLIDER1", saved.getString("task"))
        assertEquals(oraclePin, saved.getString("oracle_sha256")); assertEquals(sourcePin, saved.getString("reference_source_commit"))
        assertEquals(databasePin, saved.getString("database_sha256"))
        assertTrue(saved.getBoolean("external_force_stop_required")); assertFalse(saved.getBoolean("writer_death_proved_by_this_test"))
        val f = prepare(reopen = true)
        assertEquals(f.seedSha256, saved.getString("seed_sha256")); assertEquals(f.sourceSha256, saved.getString("source_manifest_sha256"))
        assertEquals(hash(File(context.applicationInfo.sourceDir)), saved.getString("app_apk_sha256"))
        assertEquals(hash(File(instrumentation.context.applicationInfo.sourceDir)), saved.getString("test_apk_sha256"))
        assertEquals(f.id, saved.getString("fit_id")); assertEquals(f.row.objectKey, saved.getString("object_key"))
        assertEquals(f.row.position, saved.getInt("position"))
        val start = AndroidProcess.getStartElapsedRealtime()
        assertTrue("Activity recreation cannot satisfy the reader phase", start > saved.getLong("writer_start_elapsed_ms"))
        assertTrue(AndroidProcess.myPid() != saved.getInt("writer_pid") || start != saved.getLong("writer_start_elapsed_ms"))
        assertNotEquals("Fresh bridge session is necessary; external stop proof remains separate", saved.getString("session"), session(f.id))
        assertEquals(saved.getLong("revision"), fit(f.id).revision)
        assertEquals(saved.getLong("generation"), diagnostics().getJSONObject("persistence").getLong("generation"))
        assertEquals(saved.getString("graph_sha256"), hash(f.graphFile))
        val expected = f.initial.toMutableMap().also { it[editedAttributeId] = f.display.minimum }
        val vector = saved.getJSONArray("raw_vector")
        assertRaw(expected, rolls(vector))
        for (index in 0 until vector.length()) {
            val row = vector.getJSONObject(index)
            assertEquals(row.getLong("raw_bits"), expected.getValue(row.getInt("attribute_id")).toRawBits())
        }
        assertSaved(f, expected)
        assertEquals(f.display.minimum.toRawBits(), text(f).toDouble().toRawBits()); assertEquals(1f, progress(f), 0f)
        assertEquals(saved.getString("graph_sha256"), hash(f.graphFile))
        // Undo stacks are session-local; do not claim stack survival across process death.
        assertEquals(0, history(f.id).undoCount); assertEquals(0, history(f.id).redoCount)
    }

    @Test fun accessibleBaseAndPreciseNumericDraftShareSparseSaveAndRefuseStaleRevision() {
        val f = prepare(); val beforeGraph = graph(); val revision = fit(f.id).revision
        compose.onNodeWithTag(slider(f)).performScrollTo().performSemanticsAction(SemanticsActions.SetProgress) { action ->
            assertTrue(action(0f))
        }
        compose.waitForIdle()
        assertEquals(0f, progress(f), 0f)
        assertEquals(f.display.sliderBase.toRawBits(), text(f).toDouble().toRawBits())
        assertEquals(beforeGraph, graph()); assertEquals(revision, fit(f.id).revision); assertEquals(0, history(f.id).undoCount)
        // Numeric precision remains authoritative; no slider grid rounds this pinned raw value.
        val target = f.target.getValue(editedAttributeId)
        compose.onNodeWithTag(field(f)).performScrollTo().performTextReplacement(target.toString()); compose.waitForIdle()
        assertEquals(target.toRawBits(), text(f).toDouble().toRawBits())
        // Original desktop gauge is piecewise about base, with better positive.
        val expectedProgress = if (target >= f.display.sliderBase)
            -((target - f.display.sliderBase) / (f.display.maximum - f.display.sliderBase)).toFloat()
        else ((f.display.sliderBase - target) / (f.display.sliderBase - f.display.minimum)).toFloat()
        assertEquals(expectedProgress, progress(f), 0.000001f)
        click("mutation-save-${f.row.objectKey}"); waitFor { fit(f.id).revision > revision }; settled(f.id)
        assertNull(model.error); assertEquals(revision + 1, fit(f.id).revision)
        val expected = f.initial.toMutableMap().also { it[editedAttributeId] = target }
        assertSaved(f, expected); assertOnlyRollChanged(f, beforeGraph, target)
        assertEquals(1, history(f.id).undoCount); assertEquals(0, history(f.id).redoCount)
        val cpu = fit(f.id).stats.getValue("cpu_used")
        val independentCpu = f.states.getJSONObject(1).getJSONObject("metrics").getJSONObject("cpu_used")
        assertEquals(independentCpu.getString("unit"), cpu.unit)
        assertEquals(independentCpu.getDouble("value"), cpu.value.numberOrNull()!!, 0.0)
        val powergrid = f.states.getJSONObject(0).getJSONObject("metrics").getJSONObject("powergrid_used")
        assertEquals(powergrid.getDouble("value"), fit(f.id).stats.getValue("powergrid_used").value.numberOrNull()!!, 0.0)
        val held = model.current!!; val heldRow = held.items.single()
        send(f, BridgeOperation.Undo(f.id)); assertSaved(f, f.initial)
        send(f, BridgeOperation.Redo(f.id)); assertSaved(f, expected)
        val savedGraph = graph(); val savedRevision = fit(f.id).revision
        // Use the independent oracle's initial CPU roll, not the held saved value:
        // bypassing stale refusal must reach dispatch rather than the no-edit return.
        val staleValue = f.initial.getValue(editedAttributeId)
        val staleTexts = heldRow.attributes.map {
            (if (it.raw.attributeId == editedAttributeId) staleValue else it.raw.value).toString()
        }
        assertTrue(heldRow.attributes.indices.all { index ->
            val value = staleTexts[index].toDouble()
            value.isFinite() && value in heldRow.attributes[index].raw.minimum..heldRow.attributes[index].raw.maximum
        })
        assertEquals("The valid stale candidate must contain exactly one changed roll", 1,
            heldRow.attributes.indices.count { index ->
                staleTexts[index].toDouble().toRawBits() != heldRow.attributes[index].raw.value.toRawBits()
            })
        val rawModes = heldRow.attributes.map { MutationValueRepresentation.RAW.wire }
        compose.runOnUiThread {
            val current = model.current; assertNotSame(held, current); assertTrue(model.available)
            model.save(context, held, heldRow, staleTexts, rawModes)
            assertFalse("A held stale draft must not dispatch a save", model.editing); assertSame(current, model.current)
        }
        compose.waitForIdle(); assertNull(model.error)
        assertEquals(savedRevision, fit(f.id).revision); assertEquals(savedGraph, graph()); assertSaved(f, expected)
        assertEquals(1, history(f.id).undoCount); assertEquals(0, history(f.id).redoCount)
    }
}
