package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.TimeUnit
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Deferred device phase multisource_ewar, on disposable offline data.
 * Reuses A04's legal fit inputs, not its single-source expected outputs for this graph.
 * Full-output restoration and effect directions complement the separate original-EOS
 * multi-source oracle; these assertions do not invent a numerical golden value.
 */
@RunWith(AndroidJUnit4::class)
class MultiSourceEwarUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val saved get() = ViewModelProvider(compose.activity)[ProjectedFitModel::class.java]
    private val incoming get() = ViewModelProvider(compose.activity)[ProjectedModuleModel::class.java]
    private val modules get() = ViewModelProvider(compose.activity)[ModuleEditorModel::class.java]
    private val charges get() = ViewModelProvider(compose.activity)[ChargeEditorModel::class.java]
    private val historyModel get() = ViewModelProvider(compose.activity)[EditHistoryModel::class.java]
    private val inputs by lazy {
        instrumentation.context.assets.open("projection-expected.json").bufferedReader().use {
            JSONObject(it.readText()).getJSONObject("inputs")
        }
    }

    private data class Graph(val sourceA: String, val sourceB: String, val first: String, val second: String) {
        val ids get() = listOf(sourceA, sourceB, first, second)
        val recipients get() = listOf(first, second)
    }

    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun snapshots(ids: List<String>) = ids.associateWith { fit(it) }
    // Revisions must advance on edits/history; every other published field must restore exactly.
    private fun outputs(ids: List<String>) = ids.associateWith { fit(it).copy(revision = 0L) }
    private fun stat(id: String, key: String) = fit(id).stats.getValue(key).value.numberOrNull()!!
    private fun history(id: String) = EngineRuntime.editHistory(context, id).get(30, TimeUnit.SECONDS)
    private fun histories(ids: List<String>) = ids.associateWith { history(it) }
    private fun details(id: String) = EngineRuntime.projectedModuleDetails(context, id, fit(id).revision).get(30, TimeUnit.SECONDS)
    private fun item(name: String) = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS).items.single { it.name == name }.id
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun send(operation: BridgeOperation, vararg ids: String) = EngineRuntime.request(context, operation,
        ids.toSet().associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS).also {
        assertTrue(it.error?.message, it.isSuccess)
    }
    private fun selected(id: String) = waitFor {
        !saved.busy && (EngineRuntime.state.value as? EngineState.Ready)?.fit == fit(id)
    }
    private fun select(id: String) { EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS); selected(id) }
    private fun incomingSettled(id: String) = waitFor {
        !incoming.editing && !incoming.loading && incoming.currentDetails?.let { it.fitId == id && it.revision == fit(id).revision } == true
    }
    private fun chargesSettled(id: String) = waitFor {
        !charges.editing && !charges.loading && charges.options?.let { it.fitId == id && it.revision == fit(id).revision } == true
    }
    private fun changed(id: String, action: () -> Unit) {
        val revision = fit(id).revision
        action()
        waitFor { !saved.busy && !incoming.editing && !charges.editing && fit(id).revision > revision }
    }
    private fun replay(id: String, redo: Boolean = false) {
        waitFor { !historyModel.loading && !historyModel.editing && historyModel.options?.let { it.fitId == id && it.revision == fit(id).revision } == true }
        changed(id) { click(if (redo) "history-redo" else "history-undo") }
        waitFor { !historyModel.loading && !historyModel.editing && historyModel.options?.revision == fit(id).revision }
        assertNull(historyModel.error)
    }
    private fun preview() = waitFor { !incoming.chargeLoading && incoming.currentChargePreview != null }
    private fun assertRecipientScreen(id: String) {
        compose.onNodeWithTag("projections-recipient").assertTextContains(fit(id).name, substring = true)
        compose.onNodeWithTag("projections-scan_resolution").assertTextContains(formatStat(fit(id).stats.getValue("scan_resolution")), substring = true)
    }

    private fun prepare(): Graph {
        assertEquals("multisource_ewar", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        fun create(role: String, label: String): String {
            val spec = BridgeCodec.decodeFitSpec(inputs.getJSONObject(role)).copy(name = "Multi-source $label ${System.nanoTime()}")
            return send(BridgeOperation.CreateFit(spec)).fits.single().id
        }
        val graph = Graph(create("source", "A"), create("source", "B"), create("target", "first"), create("target", "second"))
        graph.ids.forEach { assertEquals("Complete published statistics for $it", 39, fit(it).stats.size) }
        select(graph.first)
        click("projections-open")
        for (id in graph.recipients) {
            select(id)
            val baseline = stat(id, "max_target_range")
            for (source in listOf(graph.sourceA, graph.sourceB)) {
                val before = stat(id, "max_target_range")
                text("projections-search", fit(source).name)
                changed(id) { click("projection-$source-add") }
                assertEquals(ProjectionSnapshot(source, null, true, 1), fit(id).projections.single { it.sourceId == source })
                assertTrue("Each active range-dampening source contributes", stat(id, "max_target_range") < before)
            }
            assertTrue(stat(id, "max_target_range") < baseline)
            assertEquals(listOf(graph.sourceA, graph.sourceB), fit(id).projections.map { it.sourceId })
        }
        assertEquals(fit(graph.first).stats, fit(graph.second).stats)
        select(graph.first)
        return graph
    }

    @Test fun twoSourcesRefreshBothRecipientsAndRetainSelectedScriptAndRangeStateThroughDeletion() {
        val graph = prepare()
        sourceEditAndReturn(graph)
        selectedIncomingScriptsAndDeletion(graph)
    }

    private fun sourceEditAndReturn(graph: Graph) {
        val before = outputs(graph.ids)
        val beforeHistory = history(graph.sourceA).undoCount
        val recipientRevisions = graph.recipients.associateWith { fit(it).revision }
        click("projection-${graph.sourceA}-range")
        text("projections-draft-input", "1.25")
        val retainedSaved = saved
        val retainedDraft = saved.draft
        compose.activityRule.scenario.recreate(); selected(graph.first)
        assertSame(retainedSaved, saved); assertSame(retainedDraft, saved.draft)
        assertEquals("1.25", saved.draft!!.text)
        click("projection-${graph.sourceA}-open"); selected(graph.sourceA)
        assertEquals(graph.first, saved.returnRecipientId)
        click("modules-open")
        waitFor { !modules.loading && modules.details?.let { it.fitId == graph.sourceA && it.revision == fit(graph.sourceA).revision } == true }
        val dampener = fit(graph.sourceA).modules.single { it.name == "Remote Sensor Dampener II" }.index
        val rack = modules.details!!.modules.single { it.index == dampener }.slot
        click("modules-rack-${rack.name}"); click("module-charges-$dampener"); chargesSettled(graph.sourceA)
        val script = item("Scan Resolution Dampening Script")
        text("charges-search", "Scan Resolution Dampening Script"); click("charge-item-$script")
        changed(graph.sourceA) { click("charge-load-$dampener") }; chargesSettled(graph.sourceA)
        waitFor { graph.recipients.all { fit(it).revision > recipientRevisions.getValue(it) } }
        assertEquals("Scan Resolution Dampening Script", fit(graph.sourceA).modules.single { it.index == dampener }.charge)
        assertEquals(beforeHistory + 1, history(graph.sourceA).undoCount)
        assertEquals(before.getValue(graph.sourceB), outputs(listOf(graph.sourceB)).getValue(graph.sourceB))
        for (id in graph.recipients) {
            val original = before.getValue(id)
            assertTrue("Source script refresh reaches $id before navigating back", stat(id, "scan_resolution") < original.stats.getValue("scan_resolution").value.numberOrNull()!!)
            assertTrue(stat(id, "max_target_range") > original.stats.getValue("max_target_range").value.numberOrNull()!!)
            assertEquals(original.copy(stats = fit(id).stats), fit(id).copy(revision = 0L))
        }
        val edited = outputs(graph.ids)
        replay(graph.sourceA); chargesSettled(graph.sourceA)
        assertEquals(before, outputs(graph.ids)); assertEquals(beforeHistory, history(graph.sourceA).undoCount)
        assertEquals(1, history(graph.sourceA).redoCount)
        replay(graph.sourceA, true); chargesSettled(graph.sourceA)
        assertEquals(edited, outputs(graph.ids)); assertEquals(beforeHistory + 1, history(graph.sourceA).undoCount)
        assertEquals(0, history(graph.sourceA).redoCount)
        click("projections-return"); selected(graph.first)
        assertRecipientScreen(graph.first)
        compose.onNodeWithTag("projections-draft-stale").assertExists()
        compose.onNodeWithTag("projections-draft-save").assertIsNotEnabled()
        assertEquals("1.25", saved.draft!!.text)
        click("projections-draft-review"); assertFalse(saved.draftStale); assertEquals("", saved.draft!!.text)
        click("projections-draft-discard")
        val published = snapshots(graph.ids)
        val beforeReadHistory = histories(graph.ids)
        select(graph.second); assertRecipientScreen(graph.second)
        assertEquals(fit(graph.first).stats, fit(graph.second).stats)
        select(graph.first)
        // Reading in reverse order must not publish an edit or change the complete outputs.
        send(BridgeOperation.Snapshot(graph.ids.reversed()))
        assertEquals(published, snapshots(graph.ids)); assertEquals(beforeReadHistory, histories(graph.ids))
        click("projections-back")
    }

    private fun selectedIncomingScriptsAndDeletion(graph: Graph) {
        repeat(3) { send(BridgeOperation.AddProjectedModule(graph.first, item("Remote Sensor Booster II")), graph.first) }
        val ranged = details(graph.first).modules[2]
        send(BridgeOperation.SetProjectedModuleRange(graph.first, ranged.index, ranged.objectKey, 63.7), graph.first)
        click("projected-modules-open"); incomingSettled(graph.first)
        val originalRows = incoming.currentDetails!!.modules.toList()
        val before = outputs(graph.ids)
        val beforeHistory = history(graph.first).undoCount
        val recent = EngineRuntime.recent.value.toList()
        click("projected-module-2-bulk-select"); click("projected-module-0-bulk-select")
        click("projected-module-0-charge-main"); preview()
        val script = item("Scan Resolution Script")
        text("projected-charge-search", "Scan Resolution Script"); click("projected-charge-choice-$script")
        click("projected-charge-refresh"); preview()
        assertEquals(BulkScope.SELECTED, incoming.currentChargePreview!!.scope)
        assertEquals(listOf(2, 0), incoming.currentChargePreview!!.selection.map { it.index })
        assertEquals(listOf(0, 2), incoming.currentChargePreview!!.targets.filter { it.status == ProjectedChargeStatus.CHANGE }.map { it.identity.index })
        assertEquals(before, outputs(graph.ids)); assertEquals(beforeHistory, history(graph.first).undoCount)
        changed(graph.first) { click("projected-charge-apply") }; incomingSettled(graph.first)
        val editedRows = incoming.currentDetails!!.modules.toList()
        assertEquals(listOf(script, null, script), editedRows.map { it.chargeId })
        assertEquals(originalRows[1], editedRows[1])
        assertEquals(originalRows.map { it.objectKey }, editedRows.map { it.objectKey })
        assertEquals(originalRows.map { it.rangeM }, editedRows.map { it.rangeM })
        assertEquals(originalRows.map { it.state }, editedRows.map { it.state })
        assertTrue(stat(graph.first, "scan_resolution") > before.getValue(graph.first).stats.getValue("scan_resolution").value.numberOrNull()!!)
        assertEquals(beforeHistory + 1, history(graph.first).undoCount)
        for (id in listOf(graph.sourceA, graph.sourceB, graph.second)) assertEquals(before.getValue(id), fit(id).copy(revision = 0L))
        assertEquals(before.getValue(graph.first).copy(stats = fit(graph.first).stats), fit(graph.first).copy(revision = 0L))
        val edited = outputs(graph.ids)
        replay(graph.first); incomingSettled(graph.first)
        assertEquals(before, outputs(graph.ids)); assertEquals(originalRows, incoming.currentDetails!!.modules)
        assertEquals(beforeHistory, history(graph.first).undoCount); assertEquals(1, history(graph.first).redoCount)
        replay(graph.first, true); incomingSettled(graph.first)
        assertEquals(edited, outputs(graph.ids)); assertEquals(editedRows, incoming.currentDetails!!.modules)
        assertEquals(beforeHistory + 1, history(graph.first).undoCount); assertEquals(0, history(graph.first).redoCount)
        assertEquals(recent, EngineRuntime.recent.value)

        click("projected-modules-bulk-review")
        click("projected-modules-bulk-range-edit"); text("projected-modules-bulk-range-input", "1.25")
        val retainedIncoming = incoming
        val selection = incoming.bulkSelection
        val rangeDraft = incoming.bulkDraft
        val main = incoming.chargeMainKey
        compose.onNodeWithTag("projected-charge-refresh").assertIsNotEnabled()
        click("projected-modules-back"); click("projections-open")
        click("projection-${graph.sourceA}-range"); text("projections-draft-input", "7.5")
        val retainedSaved = saved
        val sourceDraft = saved.draft!!
        val published = snapshots(graph.ids)
        val priorHistory = histories(graph.ids)
        compose.activityRule.scenario.recreate(); selected(graph.first)
        assertSame(retainedSaved, saved); assertSame(sourceDraft, saved.draft)
        assertSame(retainedIncoming, incoming); assertSame(selection, incoming.bulkSelection); assertSame(rangeDraft, incoming.bulkDraft)
        assertEquals(listOf(2, 0), incoming.bulkSelection!!.rows.map { it.index })
        assertEquals(main, incoming.chargeMainKey); assertEquals(script, incoming.chargeId)
        assertEquals(BulkScope.SELECTED, incoming.chargeScope); assertEquals("1.25", incoming.bulkDraft!!.text)
        assertEquals("7.5", saved.draft!!.text)
        assertEquals(published, snapshots(graph.ids)); assertEquals(priorHistory, histories(graph.ids))
        assertEquals(editedRows, details(graph.first).modules); assertEquals(recent, EngineRuntime.recent.value)

        // Deletion is NON_HISTORY. Never attempt to undo it or resurrect the old endpoint.
        send(BridgeOperation.DeleteFit(graph.sourceA, true), graph.sourceA)
        waitFor { EngineRuntime.library.value.none { it.id == graph.sourceA } && graph.recipients.all { id -> fit(id).projections.none { it.sourceId == graph.sourceA } } }
        for (id in graph.recipients) {
            assertEquals(listOf(ProjectionSnapshot(graph.sourceB, null, true, 1)), fit(id).projections)
            assertTrue("Deleting the scan-damp source refreshes $id", stat(id, "scan_resolution") > published.getValue(id).stats.getValue("scan_resolution").value.numberOrNull()!!)
            assertTrue("Deletion must not add an undo action", history(id).undoCount <= priorHistory.getValue(id).undoCount)
        }
        assertEquals(published.getValue(graph.sourceB), fit(graph.sourceB))
        assertTrue(saved.draftStale); assertFalse(saved.canReview); assertEquals("7.5", saved.draft!!.text)
        compose.onNodeWithTag("projections-draft-save").assertIsNotEnabled()
        compose.onNodeWithTag("projections-draft-review").assertIsNotEnabled()
        compose.onNodeWithTag("projection-${graph.sourceA}-open").assertDoesNotExist()
        val remaining = listOf(graph.sourceB, graph.first, graph.second)
        val deleted = snapshots(remaining)
        val deletedHistory = histories(remaining)
        compose.runOnUiThread { saved.save(context); saved.add(context, sourceDraft.anchor) }
        assertEquals(deleted, snapshots(remaining)); assertEquals(deletedHistory, histories(remaining))
        click("projections-draft-discard"); click("projections-back"); click("projected-modules-open"); incomingSettled(graph.first)
        assertSame(selection, incoming.bulkSelection); assertEquals("1.25", incoming.bulkDraft!!.text)
        assertTrue(incoming.bulkStale); assertTrue(incoming.canReviewBulk); assertNull(incoming.currentChargePreview)
        assertEquals(editedRows, incoming.currentDetails!!.modules)
        compose.onNodeWithTag("projected-modules-bulk-range-save").assertIsNotEnabled()
        compose.onNodeWithTag("projected-charge-refresh").assertIsNotEnabled()
        click("projected-modules-bulk-review")
        assertFalse(incoming.bulkStale); assertEquals("", incoming.bulkDraft!!.text)
        assertEquals(ProjectedModuleBulkRangeMode.MIXED, incoming.bulkDraft!!.mode)
        assertEquals(selection!!.rows.map { it.objectKey }, incoming.bulkSelection!!.rows.map { it.objectKey })
        click("projected-modules-bulk-range-discard"); click("projected-charge-refresh"); preview()
        compose.onNodeWithTag("projected-charge-unchanged").assertExists()
        compose.onNodeWithTag("projected-charge-apply").assertIsNotEnabled()
        assertEquals(deleted, snapshots(remaining)); assertEquals(deletedHistory, histories(remaining))
        assertEquals(recent, EngineRuntime.recent.value)
    }
}
