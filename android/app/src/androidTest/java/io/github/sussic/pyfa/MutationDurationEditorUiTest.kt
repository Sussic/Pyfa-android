package io.github.sussic.pyfa

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Process as AndroidProcess
import android.provider.Settings
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import kotlin.math.abs
import kotlin.math.max
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Deferred fixed-case source. No reference values or raw fixture are APK assets.
 *
 * Execution requires accepted independent original-reference AND finite three-case
 * EOS receipts, a final hardcoded oracle pin, matching immutable app/test source,
 * and qualified offline disposable debug app data. Provision the private oracle
 * and seed.json in no_backup/c10-duration-fixture, and the prepared graph in
 * no_backup/fits/graph.sqlite3 BEFORE launching the app.
 *
 * Run edit phase once, then externally prove force-stop/relaunch with no clear or
 * reseed before running reopen in a separate instrumentation/app process. Activity
 * recreation is insufficient. The phase receipt records identities; it cannot
 * attest the external stop or owned process-tree closure. No undo-stack survival
 * or writer-death recovery claim is made.
 *
 * createAndroidComposeRule launches MainActivity before the test body. The body
 * rejects UNFILLED before reading expectations or editing; external no-run gates
 * above must prevent premature app/EOS startup as well.
 */
@RunWith(AndroidJUnit4::class)
class MutationDurationEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[MutationEditorModel::class.java]
    private val oraclePin = "14baf8fe09bca5783d7d6955ba3a7b57c2c884fa2d8b3987eaaf6b3b3d9d1136"
    private val caseId = "module399-duration73"
    private val sourcePin = "8b04f3b271e614b3e103853b44a7851a63d79d0e"
    private val databasePin = "e0dc4b3d281bd949f0a8089d587053ad66c0fcef90163cc6988e670d15d01065"
    private val logicalPin = "5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607"
    private val attributeIds = listOf(6, 30, 50, 68, 73)
    private val inputError = "Enter a finite numeric value within its selected raw or converted range."
    private val preferences get() = context.getSharedPreferences("mutation_duration_qualification", Context.MODE_PRIVATE)

    private data class Fixture(val oracle: JSONObject, val seed: JSONObject,
        val initial: Map<Int, Double>, val target: Map<Int, Double>, val unit: JSONObject,
        val id: String, val objectKey: String, val position: Int, val graphFile: File,
        val seedSha256: String)

    private fun hash(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it.toInt() and 255) }
    private fun hash(file: File): String = file.inputStream().use { stream ->
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(64 * 1024)
        while (true) { val count = stream.read(buffer); if (count < 0) break; digest.update(buffer, 0, count) }
        digest.digest().joinToString("") { "%02x".format(it.toInt() and 255) }
    }
    private fun sha256(value: String) = assertTrue("Expected a qualified lowercase SHA256", value.matches(Regex("[0-9a-f]{64}")))
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(condition: () -> Boolean) { compose.waitUntil(120_000, condition); compose.waitForIdle() }
    private fun settled(id: String) = waitFor {
        !model.loading && !model.editing && model.current?.let { it.fitId == id && it.revision == fit(id).revision } == true
    }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick(); compose.waitForIdle() }
    private fun replace(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value); compose.waitForIdle() }
    private fun text(tag: String) = compose.onNodeWithTag(tag).performScrollTo().fetchSemanticsNode()
        .config[SemanticsProperties.EditableText].text
    private fun field(f: Fixture) = "mutation-value-${f.objectKey}-73"
    private fun rawChip(f: Fixture) = "mutation-raw-${f.objectKey}-73"
    private fun displayChip(f: Fixture) = "mutation-display-${f.objectKey}-73"
    private fun saveTag(f: Fixture) = "mutation-save-${f.objectKey}"
    private fun history(id: String) = EngineRuntime.editHistory(context, id).get(30, TimeUnit.SECONDS)
    private fun graph() = EngineRuntime.defensePersistenceSnapshot(context).get(30, TimeUnit.SECONDS)
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(30, TimeUnit.SECONDS))
    private fun session(id: String) = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).context.sessionId
    private fun rawRow(id: String) = EngineRuntime.mutationDetails(context, id).get(30, TimeUnit.SECONDS)
        .items.single { it.kind == "module" }
    private fun rows(array: JSONArray): Map<Int, Double> = (0 until array.length()).associate { index ->
        array.getJSONObject(index).let { it.getInt("attribute_id") to it.getDouble("value") }
    }.also { assertEquals(attributeIds, it.keys.toList()) }
    private fun actualRows(row: MutationItem) = row.attributes.associate { it.attributeId to it.value }
    private fun assertBits(expected: Double, actual: Double) = assertEquals(expected.toRawBits(), actual.toRawBits())
    private fun assertRaw(expected: Map<Int, Double>, actual: Map<Int, Double>) {
        assertEquals(expected.keys, actual.keys)
        expected.forEach { (id, value) -> assertEquals("Exact raw bits for attribute $id", value.toRawBits(), actual.getValue(id).toRawBits()) }
    }
    private fun storedRows(f: Fixture) = rows(JSONObject(graph()).getJSONObject("records").getJSONObject(f.id)
        .getJSONObject("spec").getJSONArray("modules").getJSONObject(f.position)
        .getJSONObject("mutation").getJSONArray("attributes"))

    private fun assertMetrics(f: Fixture, stateIndex: Int) {
        val expected = f.oracle.getJSONArray("states").getJSONObject(stateIndex).getJSONObject("metrics")
        assertEquals(38, expected.length())
        val actual = fit(f.id).stats
        // The UI snapshot also contains scan_resolution. Every independent38
        // entry is checked; that separately owned extra statistic is not a golden.
        expected.keys().forEach { key ->
            val wanted = expected.getJSONObject(key)
            val observed = checkNotNull(actual[key]) { "Missing independent metric $key" }
            assertEquals("Metric unit $key", wanted.getString("unit"), observed.unit)
            when (val value = wanted.get("value")) {
                JSONObject.NULL -> assertSame("Unavailable metric $key", StatValue.Unavailable, observed.value)
                is Boolean -> assertEquals("Boolean metric $key", StatValue.BooleanValue(value), observed.value)
                is String -> assertEquals("Text metric $key", StatValue.Text(value), observed.value)
                is Int, is Long -> {
                    assertTrue("Integer metric $key", observed.value is StatValue.Integer)
                    assertEquals((value as Number).toLong(), (observed.value as StatValue.Integer).value)
                }
                is Number -> {
                    assertTrue("Decimal metric $key", observed.value is StatValue.Decimal)
                    val wantedNumber = value.toDouble()
                    val actualNumber = (observed.value as StatValue.Decimal).value
                    assertTrue(wantedNumber.isFinite() && actualNumber.isFinite())
                    assertTrue("Independent metric $key", abs(wantedNumber - actualNumber) <=
                        max(1e-9, 1e-10 * max(abs(wantedNumber), abs(actualNumber))))
                }
                else -> fail("Unsupported independent metric type $key")
            }
        }
    }

    private fun display(f: Fixture): MutationDisplayValue.Available {
        val item = model.current!!.items.single { it.raw.kind == "module" }
        assertEquals(f.position, item.raw.position); assertEquals(f.objectKey, item.raw.objectKey)
        val duration = item.attributes.single { it.raw.attributeId == 73 }
        assertEquals(101, duration.raw.unitId)
        val result = duration.display as MutationDisplayValue.Available
        assertBits(f.unit.getDouble("display_minimum"), result.minimum)
        assertBits(f.unit.getDouble("display_maximum"), result.maximum)
        assertEquals(f.unit.getString("unit_label"), result.unitLabel)
        assertEquals(f.unit.getBoolean("higher_is_better"), result.higherIsBetter)
        return result
    }

    private fun assertState(f: Fixture, stateIndex: Int) {
        val expected = if (stateIndex == 0) f.initial else f.target
        val row = rawRow(f.id)
        assertEquals(f.position, row.position); assertEquals(f.objectKey, row.objectKey)
        assertEquals(399, row.baseItemId); assertEquals(47778, row.mutaplasmidId)
        assertEquals(ModuleState.ACTIVE, fit(f.id).modules.single { it.emptySlot == null }.state)
        val fitting = EngineRuntime.fittingDetails(context, f.id).get(30, TimeUnit.SECONDS)
        assertEquals(fit(f.id).revision, fitting.revision); assertFalse(fitting.ignoreRestrictions)
        val fittedModule = fitting.modules.single { it.id != null }
        assertEquals(f.position, fittedModule.index); assertEquals(47781, checkNotNull(fittedModule.id))
        assertEquals(ModuleState.ACTIVE, fittedModule.state); assertTrue(fittedModule.legal == true); assertFalse(fittedModule.overridden)
        assertRaw(expected, actualRows(row)); assertRaw(expected, storedRows(f))
        assertEquals(fit(f.id).revision, JSONObject(graph()).getJSONObject("revisions").getLong(f.id))
        val shown = display(f)
        assertBits(f.unit.getDouble(if (stateIndex == 0) "display_baseline" else "display_target"), shown.value)
        assertMetrics(f, stateIndex)
    }

    private fun load(phase: String): Fixture {
        assertTrue(BuildConfig.DEBUG)
        assertEquals(phase, InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        sha256(oraclePin) // UNFILLED must never become a caller-supplied expected hash.
        val root = File(context.noBackupFilesDir, "c10-duration-fixture").canonicalFile
        assertEquals(context.noBackupFilesDir.canonicalFile, root.parentFile)
        val oracleFile = File(root, "module399-duration.raw.json").canonicalFile
        val seedFile = File(root, "seed.json").canonicalFile
        assertEquals(root, oracleFile.parentFile); assertEquals(root, seedFile.parentFile)
        assertTrue("Provision the private independent fixture before launch", oracleFile.isFile && seedFile.isFile)
        val bytes = oracleFile.readBytes(); assertEquals(oraclePin, hash(bytes))
        val oracle = JSONObject(bytes.toString(Charsets.UTF_8))
        val seedBytes = seedFile.readBytes(); val seed = JSONObject(seedBytes.toString(Charsets.UTF_8))
        assertEquals(1, oracle.getInt("schema")); assertEquals(caseId, oracle.getString("case_id"))
        assertEquals("QUALIFIED_INDEPENDENT_REFERENCE_FIXTURE", oracle.getString("status"))
        assertEquals(sourcePin, oracle.getString("source_commit"))
        assertEquals(databasePin, oracle.getString("database_sha256")); assertEquals(logicalPin, oracle.getString("database_logical_sha256"))
        assertEquals(399, oracle.getInt("base_item_id")); assertEquals(47778, oracle.getInt("mutaplasmid_id"))
        assertEquals(47781, oracle.getInt("resulting_item_id"))
        val states = oracle.getJSONArray("states"); assertEquals(2, states.length())
        assertEquals("baseline", states.getJSONObject(0).getString("name"))
        assertEquals(.25, states.getJSONObject(0).getDouble("fraction"), 0.0)
        assertEquals("duration_only_target", states.getJSONObject(1).getString("name"))
        assertEquals("maximum", states.getJSONObject(1).getString("endpoint"))
        assertEquals(73, states.getJSONObject(1).getInt("changed_attribute_id"))
        val initial = rows(states.getJSONObject(0).getJSONArray("attributes"))
        val target = rows(states.getJSONObject(1).getJSONArray("attributes"))
        for (stateIndex in 0..1) {
            val identities = states.getJSONObject(stateIndex).getJSONArray("raw_identity")
            assertEquals(5, identities.length())
            for (index in attributeIds.indices) {
                val row = identities.getJSONObject(index); val id = attributeIds[index]
                assertEquals(id, row.getInt("attribute_id")); assertEquals("float", row.getString("type"))
                val encoded = java.lang.Double.valueOf(row.getString("encoding")).toDouble()
                assertBits(encoded, (if (stateIndex == 0) initial else target).getValue(id))
            }
        }
        initial.forEach { (id, value) -> if (id != 73) assertBits(value, target.getValue(id)) }
        assertTrue(initial.getValue(73).toRawBits() != target.getValue(73).toRawBits())
        val unit = oracle.getJSONObject("unit_observation")
        assertEquals(73, unit.getInt("attribute_id")); assertEquals(101, unit.getInt("unit_id"))
        assertEquals("Milliseconds", unit.getString("unit_name")); assertEquals("s", unit.getString("unit_label"))
        assertFalse(unit.getBoolean("higher_is_better")); assertTrue(unit.getBoolean("inverse_within_tolerance"))
        assertBits(initial.getValue(73), unit.getDouble("raw_baseline"))
        assertBits(target.getValue(73), unit.getDouble("raw_maximum"))
        assertTrue(initial.getValue(73) != unit.getDouble("display_baseline"))
        assertTrue(target.getValue(73) != unit.getDouble("display_target"))
        assertEquals(1, seed.getInt("schema_version")); assertEquals(caseId, seed.getString("case_id"))
        assertEquals("PREPARED_PENDING_NATIVE_ACCEPTANCE", seed.getString("status"))
        assertTrue(seed.getBoolean("synthetic_inputs_only")); assertFalse(seed.getBoolean("native_acceptance"))
        assertEquals(sourcePin, seed.getString("reference_source_commit"))
        assertEquals(databasePin, seed.getString("database_sha256")); assertEquals(logicalPin, seed.getString("database_logical_sha256"))
        val asset = seed.getJSONObject("oracle_asset")
        assertEquals("module399-duration.raw.json", asset.getString("name")); assertEquals(oraclePin, asset.getString("sha256"))
        assertEquals(bytes.size.toLong(), asset.getLong("size_bytes"))
        val prerequisites = seed.getJSONObject("prerequisites")
        val reference = prerequisites.getJSONObject("reference_fixture")
        assertEquals("ACCEPT_INDEPENDENT_REFERENCE_FIXTURE_WITH_ACTUAL_ZERO_CLOSURE", reference.getString("status"))
        assertEquals(sourcePin, reference.getString("source_commit")); assertEquals(oraclePin, reference.getString("oracle_sha256"))
        sha256(reference.getString("receipt_sha256"))
        val eos = prerequisites.getJSONObject("finite_three_case_eos")
        assertEquals("ACCEPT_FINITE_THREE_CASE_EOS_RECEIPT_SCHEMA", eos.getString("status"))
        assertEquals(oraclePin, eos.getString("oracle_sha256")); sha256(eos.getString("receipt_sha256"))
        sha256(eos.getString("request_sha256")); sha256(eos.getString("policy_sha256"))
        assertTrue(eos.getString("source_commit").matches(Regex("[0-9a-f]{40}")))
        sha256(seed.getString("source_manifest_sha256"))
        val preparedGraph = seed.getJSONObject("graph")
        assertEquals("graph.sqlite3", preparedGraph.getString("name")); sha256(preparedGraph.getString("sha256"))
        assertEquals(1, preparedGraph.getInt("schema")); assertEquals(1, preparedGraph.getInt("format"))
        assertEquals(1L, preparedGraph.getLong("generation")); assertEquals(1, preparedGraph.getInt("fit_count"))
        assertEquals(oracle.getJSONObject("initial_spec").getString("name"), preparedGraph.getString("fit_name"))
        val observation = seed.getJSONObject("seed_observation")
        val id = observation.getString("fit_id"); val key = observation.getString("object_key")
        assertTrue(id.matches(Regex("[0-9a-f]{32}"))); assertTrue(key.matches(Regex("[0-9a-f]{32}")))
        val position = observation.getInt("position"); assertTrue(position >= 0)
        assertRaw(initial, rows(observation.getJSONArray("raw_vector")))
        assertEquals(38, observation.getInt("independent_baseline_metrics_compared"))
        val graphFile = File(context.noBackupFilesDir, "fits/graph.sqlite3").canonicalFile
        assertEquals(context.noBackupFilesDir.canonicalFile, graphFile.parentFile!!.parentFile)
        assertTrue(graphFile.isFile)
        val result = Fixture(oracle, seed, initial, target, unit, id, key, position, graphFile, hash(seedBytes))
        val manifest = JSONObject(context.assets.open("engine/manifest.json").bufferedReader().use { it.readText() })
        assertEquals(databasePin, manifest.getString("database_sha256"))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val persistence = diagnostics().getJSONObject("persistence")
        assertTrue(persistence.getBoolean("enabled")); assertTrue(persistence.getBoolean("opened_existing"))
        assertEquals(1, persistence.getInt("schema"))
        assertEquals(graphFile, File(persistence.getString("path")).canonicalFile)
        assertEquals(1, EngineRuntime.library.value.size); assertEquals(id, EngineRuntime.library.value.single().id)
        assertEquals(preparedGraph.getString("fit_name"), fit(id).name); assertEquals("Rifter", fit(id).ship)
        assertEquals(oracle.getJSONObject("initial_spec").getJSONArray("modules").getJSONObject(0).getString("name"),
            fit(id).modules.single { it.emptySlot == null }.name)
        assertEquals(ModuleState.ACTIVE, fit(id).modules.single { it.emptySlot == null }.state)
        return result
    }

    private fun open(f: Fixture) {
        EngineRuntime.selectFit(context, f.id).get(30, TimeUnit.SECONDS)
        click("mutation-open"); settled(f.id); assertNull(model.error)
    }
    private fun send(f: Fixture, operation: BridgeOperation) {
        val revision = fit(f.id).revision
        val result = EngineRuntime.request(context, operation, mapOf(f.id to revision)).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess)
        waitFor { fit(f.id).revision > revision }; settled(f.id); assertNull(model.error)
    }

    @Test fun convertedDurationSparseSaveHistoryAndRefusals() {
        val f = load("mutation_duration_edit")
        assertFalse("Use fresh disposable app data, not a prior edit phase", preferences.contains("edit"))
        assertEquals(1L, fit(f.id).revision); assertEquals(0, history(f.id).undoCount); assertEquals(0, history(f.id).redoCount)
        assertEquals(1L, diagnostics().getJSONObject("persistence").getLong("generation"))
        assertEquals(f.seed.getJSONObject("graph").getString("sha256"), hash(f.graphFile))
        open(f); assertState(f, 0)
        val beforeRevision = fit(f.id).revision; val beforeGraph = graph(); val beforeStore = hash(f.graphFile)
        val beforeRecent = EngineRuntime.recent.value.toList()
        val baselineText = f.unit.getDouble("display_baseline").toString()
        val rawText = f.initial.getValue(73).toString()
        val targetText = f.unit.getDouble("display_target").toString()
        compose.onNodeWithTag(displayChip(f)).assertIsSelected(); assertEquals(baselineText, text(field(f)))
        compose.onNodeWithText("${f.unit.getDouble("display_minimum")} to ${f.unit.getDouble("display_maximum")}; s; lower is better")
            .performScrollTo().assertIsDisplayed()
        replace(field(f), targetText); click(rawChip(f)); assertEquals(rawText, text(field(f)))
        replace(field(f), f.target.getValue(73).toString()); click(displayChip(f)); assertEquals(baselineText, text(field(f)))
        val outsideDisplay = Math.nextUp(f.unit.getDouble("display_maximum"))
        assertTrue(outsideDisplay.isFinite() && outsideDisplay > f.unit.getDouble("display_maximum"))
        for (invalid in listOf("NaN", outsideDisplay.toString())) {
            replace(field(f), invalid); click(saveTag(f)); settled(f.id)
            compose.onNodeWithTag("mutation-error").assertTextEquals(inputError)
            assertEquals(beforeRevision, fit(f.id).revision); assertEquals(0, history(f.id).undoCount)
            assertEquals(beforeGraph, graph()); assertEquals(beforeStore, hash(f.graphFile)); assertRaw(f.initial, actualRows(rawRow(f.id)))
        }
        click(rawChip(f))
        val outsideRaw = Math.nextUp(f.unit.getDouble("raw_maximum"))
        assertTrue(outsideRaw.isFinite() && outsideRaw > f.unit.getDouble("raw_maximum"))
        replace(field(f), outsideRaw.toString()); click(saveTag(f)); settled(f.id)
        compose.onNodeWithTag("mutation-error").assertTextEquals(inputError)
        assertEquals(beforeRevision, fit(f.id).revision); assertEquals(beforeGraph, graph()); assertEquals(beforeStore, hash(f.graphFile))
        click(displayChip(f)); replace(field(f), targetText)
        compose.onNodeWithText("Discard this draft").performScrollTo().performClick(); compose.waitForIdle()
        assertEquals(baselineText, text(field(f))); assertEquals(beforeGraph, graph()); assertEquals(beforeStore, hash(f.graphFile))
        assertEquals(0, history(f.id).undoCount); assertRaw(f.initial, actualRows(rawRow(f.id)))

        replace(field(f), targetText); click(saveTag(f))
        waitFor { fit(f.id).revision > beforeRevision }; settled(f.id); assertNull(model.error)
        assertEquals(beforeRevision + 1, fit(f.id).revision)
        assertState(f, 1); assertEquals(1, history(f.id).undoCount); assertEquals(0, history(f.id).redoCount)
        assertEquals(beforeRecent, EngineRuntime.recent.value)
        val held = model.current!!; val heldRow = held.items.single { it.raw.kind == "module" }
        send(f, BridgeOperation.Undo(f.id)); assertState(f, 0)
        assertEquals(0, history(f.id).undoCount); assertEquals(1, history(f.id).redoCount)
        send(f, BridgeOperation.Redo(f.id)); assertState(f, 1)
        assertEquals(1, history(f.id).undoCount); assertEquals(0, history(f.id).redoCount)
        val revision = fit(f.id).revision; val durableGraph = graph(); val durableHash = hash(f.graphFile)
        val staleTexts = heldRow.attributes.map { attribute ->
            (if (attribute.raw.attributeId == 73) f.initial.getValue(73) else attribute.raw.value).toString()
        }
        val rawModes = heldRow.attributes.map { MutationValueRepresentation.RAW.wire }
        compose.runOnUiThread {
            val current = model.current; assertNotNull(current); assertTrue(model.available); assertNotSame(held, current)
            model.save(context, held, heldRow, staleTexts, rawModes)
            assertFalse("A held stale draft must not queue any save", model.editing); assertSame(current, model.current)
        }
        compose.waitForIdle(); assertNull(model.error)
        assertEquals(revision, fit(f.id).revision); assertEquals(1, history(f.id).undoCount); assertEquals(0, history(f.id).redoCount)
        assertEquals(durableGraph, graph()); assertEquals(durableHash, hash(f.graphFile)); assertState(f, 1)
        val persistence = diagnostics().getJSONObject("persistence")
        val receipt = JSONObject().put("case_id", caseId).put("oracle_sha256", oraclePin).put("seed_sha256", f.seedSha256)
            .put("fit_id", f.id).put("object_key", f.objectKey).put("position", f.position).put("revision", revision)
            .put("generation", persistence.getLong("generation")).put("graph_sha256", durableHash)
            .put("session", session(f.id)).put("pid", AndroidProcess.myPid())
            .put("process_start_elapsed_ms", AndroidProcess.getStartElapsedRealtime())
            .put("external_force_stop_required", true).put("writer_process_death_proved_by_this_test", false)
        assertTrue(preferences.edit().putString("edit", receipt.toString()).commit())
    }

    @Test fun durationTargetReopensAfterExternallyVerifiedFreshProcess() {
        val f = load("mutation_duration_reopen")
        val saved = JSONObject(checkNotNull(preferences.getString("edit", null)) { "Run the edit phase first without clearing or reseeding." })
        assertEquals(caseId, saved.getString("case_id")); assertEquals(oraclePin, saved.getString("oracle_sha256"))
        assertEquals(f.seedSha256, saved.getString("seed_sha256"))
        assertEquals(f.id, saved.getString("fit_id")); assertEquals(f.objectKey, saved.getString("object_key"))
        assertEquals(f.position, saved.getInt("position")); assertTrue(saved.getBoolean("external_force_stop_required"))
        assertFalse(saved.getBoolean("writer_process_death_proved_by_this_test"))
        assertNotEquals("A new session is necessary but not sufficient evidence of the external stop", saved.getString("session"), session(f.id))
        val started = AndroidProcess.getStartElapsedRealtime()
        assertTrue("Activity recreation cannot satisfy this phase", started > saved.getLong("process_start_elapsed_ms"))
        assertTrue(AndroidProcess.myPid() != saved.getInt("pid") || started != saved.getLong("process_start_elapsed_ms"))
        assertEquals(saved.getLong("revision"), fit(f.id).revision)
        assertEquals(saved.getLong("generation"), diagnostics().getJSONObject("persistence").getLong("generation"))
        assertEquals(saved.getString("graph_sha256"), hash(f.graphFile))
        open(f); assertState(f, 1)
        compose.onNodeWithTag(displayChip(f)).assertIsSelected()
        assertEquals(f.unit.getDouble("display_target").toString(), text(field(f)))
        assertEquals(saved.getLong("revision"), fit(f.id).revision)
        assertEquals(saved.getString("graph_sha256"), hash(f.graphFile))
        // Undo/redo is session-local. Do not compare it to the prior process's stack.
        assertEquals(0, history(f.id).undoCount); assertEquals(0, history(f.id).redoCount)
    }
}
