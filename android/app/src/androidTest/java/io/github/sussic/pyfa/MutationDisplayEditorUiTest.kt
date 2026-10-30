package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Deferred native source: run each method in a separate instrumentation process,
 * offline_features_phase=mutation_units, against a fresh disposable debug install
 * whose graph contains only the independently specified initial afterburner fit.
 *
 * Test APK asset module438-repeat.raw.json must be an exact copy of the retained
 * module-reference-determinism-01/module438-repeat.raw.json, now copied byte-for-
 * byte into this derivative's androidTest assets. Native seed generation and
 * qualification remain pending; the seed must materialize ordinary EOS vacancy
 * rows before BridgeSession adoption. This test never manufactures its seed.
 * Expected raw rolls come exclusively from that pinned desktop oracle.
 * The capacitor-need attribute (6, GJ) exercises identity display entry; this UI
 * gate does not replace independent nonidentity-unit/EOS or restart qualification.
 */
@RunWith(AndroidJUnit4::class)
class MutationDisplayEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[MutationEditorModel::class.java]
    private val oraclePin = "0e9cddf9eb8df1c8c31620167dc4c86596d782a42d9e7859b7edce708d6205e7"
    private val sourcePin = "8b04f3b271e614b3e103853b44a7851a63d79d0e"
    private val databasePin = "e0dc4b3d281bd949f0a8089d587053ad66c0fcef90163cc6988e670d15d01065"
    private val editedAttributeId = 6
    private val inputError = "Enter a finite numeric value within its selected raw or converted range."

    private data class Prepared(val id: String, val initial: Map<Int, Double>,
        val target: Map<Int, Double>, val row: MutationItem)

    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(condition: () -> Boolean) { compose.waitUntil(120_000, condition); compose.waitForIdle() }
    private fun settled(id: String) = waitFor {
        !model.loading && !model.editing && model.current?.let { it.fitId == id && it.revision == fit(id).revision } == true
    }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick(); compose.waitForIdle() }
    private fun replace(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value); compose.waitForIdle() }
    private fun inputText(tag: String) = compose.onNodeWithTag(tag).performScrollTo().fetchSemanticsNode()
        .config[SemanticsProperties.EditableText].text
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
    private fun graphRolls(json: String, id: String, position: Int) = rolls(JSONObject(json).getJSONObject("records")
        .getJSONObject(id).getJSONObject("spec").getJSONArray("modules").getJSONObject(position)
        .getJSONObject("mutation").getJSONArray("attributes"))
    private fun field(row: MutationItem, attributeId: Int = editedAttributeId) = "mutation-value-${row.objectKey}-$attributeId"
    private fun rawChip(row: MutationItem) = "mutation-raw-${row.objectKey}-$editedAttributeId"
    private fun displayChip(row: MutationItem) = "mutation-display-${row.objectKey}-$editedAttributeId"
    private fun send(id: String, operation: BridgeOperation) = EngineRuntime.request(context, operation,
        mapOf(id to fit(id).revision)).get(120, TimeUnit.SECONDS).also { assertTrue(it.error?.message, it.isSuccess) }

    private fun prepare(): Prepared {
        assertTrue(BuildConfig.DEBUG)
        assertEquals("mutation_units", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val bytes = instrumentation.context.assets.open("module438-repeat.raw.json").use { it.readBytes() }
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it.toInt() and 255) }
        assertEquals(oraclePin, digest)
        val oracle = JSONObject(bytes.toString(Charsets.UTF_8))
        assertEquals(sourcePin, oracle.getString("source_commit")); assertEquals(databasePin, oracle.getString("database_sha256"))
        assertEquals(438, oracle.getInt("base_item_id")); assertEquals(47746, oracle.getInt("mutaplasmid_id"))
        assertEquals(47749, oracle.getInt("resulting_item_id"))
        val states = oracle.getJSONArray("states"); assertEquals(2, states.length())
        assertEquals(.25, states.getJSONObject(0).getDouble("fraction"), 0.0)
        assertEquals(.75, states.getJSONObject(1).getDouble("fraction"), 0.0)
        val initial = rolls(states.getJSONObject(0).getJSONArray("attributes"))
        val target = rolls(states.getJSONObject(1).getJSONArray("attributes"))
        assertEquals(setOf(6, 20, 30, 50), initial.keys); assertEquals(initial.keys, target.keys)
        assertTrue(initial.getValue(editedAttributeId).toRawBits() != target.getValue(editedAttributeId).toRawBits())
        val manifest = JSONObject(context.assets.open("engine/manifest.json").bufferedReader().use { it.readText() })
        assertEquals(databasePin, manifest.getString("database_sha256"))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val diagnostics = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(30, TimeUnit.SECONDS))
        assertTrue(diagnostics.getJSONObject("persistence").getBoolean("opened_existing"))
        assertEquals("A fresh prepared one-fit synthetic seed is required", 1, EngineRuntime.library.value.size)
        val id = EngineRuntime.library.value.single().id
        assertEquals(oracle.getJSONObject("initial_spec").getString("name"), fit(id).name)
        assertEquals("Rifter", fit(id).ship)
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        click("mutation-open"); settled(id); assertNull(model.error)
        val row = rawRow(id)
        assertEquals(0, row.position); assertEquals(438, row.baseItemId); assertEquals(47746, row.mutaplasmidId)
        // Raw details use EOS fullName, which may include the mutaplasmid/base
        // names. The fit snapshot retains the independently specified item name.
        assertTrue(row.name.isNotBlank())
        assertEquals(oracle.getJSONObject("initial_spec").getJSONArray("modules").getJSONObject(0).getString("name"),
            fit(id).modules.single { it.emptySlot == null }.name)
        assertRaw(initial, rowRolls(row)); assertRaw(initial, graphRolls(graph(), id, row.position))
        assertEquals(0, history(id).undoCount)
        val attribute = model.current!!.items.single().attributes.single { it.raw.attributeId == editedAttributeId }
        val display = attribute.display as MutationDisplayValue.Available
        // Original Unit.SimplifyValue leaves the pinned GJ capacitor-need scalar unchanged.
        assertEquals("GJ", display.unitLabel)
        assertEquals(initial.getValue(editedAttributeId).toRawBits(), display.value.toRawBits())
        return Prepared(id, initial, target, row)
    }

    @Test fun entryModesResetFromSourceAndInvalidOrDiscardedDraftsDoNotSave() {
        val prepared = prepare(); val id = prepared.id; val row = prepared.row
        val beforeRevision = fit(id).revision; val beforeGraph = graph(); val beforeHistory = history(id).undoCount
        val initialText = prepared.initial.getValue(editedAttributeId).toString()
        compose.onNodeWithTag(displayChip(row)).assertIsSelected()
        replace(field(row), "999.125")
        click(rawChip(row)); compose.onNodeWithTag(rawChip(row)).assertIsSelected()
        assertEquals(initialText, inputText(field(row)))
        replace(field(row), "123.456")
        click(displayChip(row)); compose.onNodeWithTag(displayChip(row)).assertIsSelected()
        assertEquals(initialText, inputText(field(row)))
        val display = model.current!!.items.single().attributes.single { it.raw.attributeId == editedAttributeId }
            .display as MutationDisplayValue.Available
        assertTrue("The finite rejection input must exceed the source-provided converted range", 1_000_000.0 > display.maximum)
        for (invalid in listOf("NaN", "1000000")) {
            replace(field(row), invalid); click("mutation-save-${row.objectKey}"); settled(id)
            compose.onNodeWithTag("mutation-error").assertTextEquals(inputError)
            assertFalse(model.editing); assertEquals(beforeRevision, fit(id).revision)
            assertEquals(beforeHistory, history(id).undoCount); assertEquals(beforeGraph, graph())
            assertRaw(prepared.initial, rowRolls(rawRow(id)))
        }
        compose.onNodeWithText("Discard this draft").performScrollTo().performClick(); compose.waitForIdle()
        assertEquals(initialText, inputText(field(row)))
        assertEquals(beforeRevision, fit(id).revision); assertEquals(beforeGraph, graph())
        // Closing a valid but unsaved field must also leave the stored source intact.
        replace(field(row), prepared.target.getValue(editedAttributeId).toString())
        click("mutation-close"); compose.onNodeWithTag("mutation-save-${row.objectKey}").assertDoesNotExist()
        assertRaw(prepared.initial, rowRolls(rawRow(id)))
        assertEquals(beforeHistory, history(id).undoCount); assertEquals(beforeGraph, graph())
        click("mutation-open"); settled(id)
        assertEquals(initialText, inputText(field(row)))
    }

    @Test fun sparseUiSaveKeepsOmittedRawRollsAndOneHistoryEntryWhileHeldStaleDraftIsRefused() {
        val prepared = prepare(); val id = prepared.id; val row = prepared.row
        val beforeGraph = JSONObject(graph()); val beforeRevision = fit(id).revision
        val beforeHistory = history(id).undoCount; val beforeRecent = EngineRuntime.recent.value.toList()
        val target = prepared.target.getValue(editedAttributeId)
        click(rawChip(row)); replace(field(row), target.toString()); click("mutation-save-${row.objectKey}")
        waitFor { fit(id).revision > beforeRevision }; settled(id); assertNull(model.error)
        val expected = prepared.initial.toMutableMap().also { it[editedAttributeId] = target }
        val after = rawRow(id)
        assertRaw(expected, rowRolls(after)); assertRaw(expected, graphRolls(graph(), id, row.position))
        assertEquals(row.copy(attributes = row.attributes.map {
            if (it.attributeId == editedAttributeId) it.copy(value = target) else it
        }), after)
        assertEquals(beforeHistory + 1, history(id).undoCount); assertEquals(beforeRecent, EngineRuntime.recent.value)
        val expectedSpec = beforeGraph.getJSONObject("records").getJSONObject(id).getJSONObject("spec")
        val expectedRolls = expectedSpec.getJSONArray("modules").getJSONObject(row.position)
            .getJSONObject("mutation").getJSONArray("attributes")
        for (index in 0 until expectedRolls.length()) {
            val roll = expectedRolls.getJSONObject(index)
            if (roll.getInt("attribute_id") == editedAttributeId) roll.put("value", target)
        }
        assertEquals(expectedSpec.toString(), JSONObject(graph()).getJSONObject("records").getJSONObject(id)
            .getJSONObject("spec").toString())

        val held = model.current!!; val heldRow = held.items.single()
        val staleTexts = heldRow.attributes.map { attribute ->
            (if (attribute.raw.attributeId == editedAttributeId) prepared.initial.getValue(editedAttributeId)
             else attribute.raw.value).toString()
        }
        val representations = heldRow.attributes.map { MutationValueRepresentation.RAW.wire }
        send(id, BridgeOperation.RenameFit(id, "UNITS1 held draft ${System.nanoTime()}")); settled(id)
        val renamedRevision = fit(id).revision; val renamedGraph = graph(); val renamedHistory = history(id).undoCount
        compose.runOnUiThread {
            val current = model.current
            assertNotSame(held, current)
            model.save(context, held, heldRow, staleTexts, representations)
            // Check synchronously: a wrongly queued request would set editing before
            // its completion can return to this same UI thread, even if EOS rejects it.
            assertFalse(model.editing); assertSame(current, model.current)
        }
        compose.waitForIdle(); assertNull(model.error)
        assertEquals(renamedRevision, fit(id).revision); assertEquals(renamedHistory, history(id).undoCount)
        assertEquals(renamedGraph, graph()); assertRaw(expected, rowRolls(rawRow(id)))
    }
}
