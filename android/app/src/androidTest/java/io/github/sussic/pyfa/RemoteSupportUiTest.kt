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
 * Deferred D02.2 device gate: offline_features_phase=remote_support, disposable data.
 * Three legal fixture inputs, one reciprocal pair and one additional recipient.
 * Display binding, causal changes and exact restoration complement the independent
 * original-EOS remote_support comparison; native self-comparison is not its oracle.
 */
@RunWith(AndroidJUnit4::class)
class RemoteSupportUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val saved get() = ViewModelProvider(compose.activity)[ProjectedFitModel::class.java]
    private val incoming get() = ViewModelProvider(compose.activity)[ProjectedModuleModel::class.java]
    private val modules get() = ViewModelProvider(compose.activity)[ModuleEditorModel::class.java]
    private val states get() = ViewModelProvider(compose.activity)[BulkStateEditorModel::class.java]
    private val historyModel get() = ViewModelProvider(compose.activity)[EditHistoryModel::class.java]
    private val tank get() = ViewModelProvider(compose.activity)[TankModel::class.java]
    private val capacitor get() = ViewModelProvider(compose.activity)[CapacitorModel::class.java]
    private val output get() = ViewModelProvider(compose.activity)[OutputModel::class.java]

    private data class Graph(val a: String, val b: String, val c: String) {
        val ids get() = listOf(a, b, c)
        val recipients get() = listOf(b, c)
    }
    private data class Values(val snapshot: FitSnapshot, val tank: FitTank,
        val capacitor: FitCapacitor, val output: FitOutput)

    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun snapshots(ids: List<String>) = ids.associateWith { fit(it) }
    private fun history(id: String) = EngineRuntime.editHistory(context, id).get(30, TimeUnit.SECONDS)
    private fun histories(ids: List<String>) = ids.associateWith { history(it) }
    private fun link(source: String, target: String) = fit(target).projections.single { it.sourceId == source }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun shown(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().assertTextEquals(value) }
    private fun select(id: String) {
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        selected(id)
    }
    private fun selected(id: String) = waitFor {
        !saved.busy && (EngineRuntime.state.value as? EngineState.Ready)?.fit == fit(id)
    }
    private fun send(operation: BridgeOperation, vararg ids: String): BridgeResponse =
        EngineRuntime.request(context, operation, ids.toSet().associateWith { fit(it).revision })
            .get(120, TimeUnit.SECONDS).also { assertTrue(it.error?.message, it.isSuccess) }
    private fun changed(id: String, action: () -> Unit) {
        val revision = fit(id).revision
        action()
        waitFor { !saved.busy && !states.editing && !incoming.editing && fit(id).revision > revision }
    }
    private fun oneEdit(id: String, action: () -> Unit) {
        val before = history(id)
        changed(id, action)
        assertEquals("Exactly one history entry", before.undoCount + 1, history(id).undoCount)
        assertEquals(0, history(id).redoCount)
    }
    private fun replay(id: String, redo: Boolean = false) {
        waitFor { !historyModel.loading && !historyModel.editing &&
            historyModel.options?.let { it.fitId == id && it.revision == fit(id).revision } == true }
        val before = history(id)
        changed(id) { click(if (redo) "history-redo" else "history-undo") }
        waitFor { !historyModel.loading && !historyModel.editing && historyModel.options?.revision == fit(id).revision }
        assertNull(historyModel.error)
        assertEquals(before.undoCount + if (redo) 1 else -1, history(id).undoCount)
        assertEquals(before.redoCount + if (redo) -1 else 1, history(id).redoCount)
    }
    private fun fixture(asset: String, name: String): JSONObject {
        val cases = instrumentation.context.assets.open(asset).bufferedReader().use {
            JSONObject(it.readText()).getJSONArray("cases")
        }
        return (0 until cases.length()).map { cases.getJSONObject(it) }
            .single { it.getJSONObject("spec").getString("name") == name }
    }
    private fun create(asset: String, name: String, label: String): String {
        val raw = fixture(asset, name).getJSONObject("spec")
        assertFalse(raw.getBoolean("ignore_restrictions"))
        assertEquals(0, raw.getJSONArray("cargo").length())
        raw.remove("ignore_restrictions"); raw.remove("cargo")
        val spec = BridgeCodec.decodeFitSpec(raw).copy(name = "Remote support $label ${System.nanoTime()}")
        assertEquals(5, spec.skillLevel); assertFalse(spec.factorReload)
        assertTrue(spec.drones.isEmpty()); assertTrue(spec.fighters.isEmpty()); assertTrue(spec.environments.isEmpty())
        val id = send(BridgeOperation.CreateFit(spec)).fits.single().id
        assertEquals(spec.modules.map { it.name }, fit(id).modules.map { it.name })
        assertEquals(spec.modules.map { it.state }, fit(id).modules.map { it.state })
        assertEquals(39, fit(id).stats.size)
        return id
    }
    private fun prepare(): Graph {
        assertEquals("remote_support", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val graph = Graph(create("output-expected.json", "All outgoing", "A"),
            create("output-expected.json", "All outgoing", "B"),
            create("tank-expected.json", "Cap limited repairs", "C"))
        select(graph.b); click("projections-open")
        for ((source, target) in listOf(graph.a to graph.b, graph.b to graph.a, graph.a to graph.c)) {
            select(target); text("projections-search", fit(source).name)
            oneEdit(target) { click("projection-$source-add") }
            assertEquals(listOf(ProjectionSnapshot(source, null, true, 1)), fit(target).projections)
        }
        click("projections-back")
        return graph
    }

    // Preserve all fields except monotonically advancing publication revisions.
    private fun values(id: String): Values {
        val t = EngineRuntime.tankDetails(context, id).get(120, TimeUnit.SECONDS)
        val c = EngineRuntime.capacitorDetails(context, id).get(120, TimeUnit.SECONDS)
        val o = EngineRuntime.outputDetails(context, id).get(120, TimeUnit.SECONDS)
        assertEquals(fit(id).revision, t.revision); assertEquals(fit(id).revision, c.revision)
        assertEquals(fit(id).revision, o.revision)
        return Values(fit(id).copy(revision = 0L), t.copy(revision = 0L), c.copy(revision = 0L), o.copy(revision = 0L))
    }
    private fun readAll(ids: List<String>) = ids.associateWith { values(it) }
    private fun armor(value: Values) = value.tank.modes.getValue("raw").reinforced.repairs.getValue("armorRepair").value.numberOrNull()!!
    private fun cap(value: Values, name: String) = value.capacitor.capacitor.getValue(name).value.numberOrNull()!!

    /** Starts/ends on Home. Each screen must load this fit's current revision. */
    private fun screens(id: String): Values {
        select(id)
        val before = fit(id); val beforeHistory = history(id)
        click("tank-open")
        waitFor { !tank.loading && tank.error == null && tank.details?.let { it.fitId == id && it.revision == fit(id).revision } == true }
        val t = tank.details!!
        for (mode in listOf("effective", "raw")) {
            val row = t.modes.getValue(mode)
            shown("tank-value-passive", "${row.passiveShield.display} ${row.passiveShield.unit}")
            for ((stability, variant) in listOf("reinforced" to row.reinforced, "sustained" to row.sustained)) {
                for ((name, scalar) in variant.repairs) {
                    assertNotNull(scalar.display)
                    shown("tank-value-$stability-$name", "${scalar.display} ${scalar.unit}")
                }
            }
            click("tank-toggle")
        }
        click("tank-back"); click("capacitor-open")
        waitFor { !capacitor.loading && capacitor.error == null && capacitor.details?.let { it.fitId == id && it.revision == fit(id).revision } == true }
        val c = capacitor.details!!
        for ((name, scalar) in c.capacitor) {
            val absent = if (name == "effective_capacity" || name == "effective_excess") "Not applicable" else "Unavailable"
            shown("capacitor-value-$name", scalar.display?.let { "$it ${scalar.unit}" } ?: absent)
        }
        shown("capacitor-stability", when (c.stability.kind) {
            "stable", "stable_range" -> "Stable: ${c.stability.display}"
            "depletion" -> "Lasts ${c.stability.display}"
            else -> "Stability unavailable"
        })
        click("capacitor-back"); click("output-open")
        waitFor { !output.loading && output.error == null && output.details?.let { it.fitId == id && it.revision == fit(id).revision } == true }
        val o = output.details!!
        click("output-page-outgoing")
        for ((name, row) in o.outgoing) {
            assertNotNull(row.current.display)
            shown("output-value-outgoing-$name", "${row.current.display} ${row.current.unit}")
        }
        click("output-back")
        assertEquals(before, fit(id)); assertEquals(beforeHistory, history(id))
        return Values(before.copy(revision = 0L), t.copy(revision = 0L), c.copy(revision = 0L), o.copy(revision = 0L))
    }

    @Test fun reciprocalSupportRefreshesRealScreensAndKeepsAtomicHistoryNullableDraftAndDeletion() {
        val graph = prepare()
        val baseline = graph.ids.associateWith { screens(it) }
        sourceEditAndReturn(graph, baseline)
        rangeStateAndNullableDraft(graph, baseline)
        incomingNeutralizer(graph, baseline)
        removeDirectionAndDeleteStaleSource(graph, baseline)
    }

    private fun sourceEditAndReturn(graph: Graph, baseline: Map<String, Values>) {
        val beforeHistory = histories(graph.ids)
        val revisions = snapshots(graph.ids)
        select(graph.b); click("projections-open")
        click("projection-${graph.a}-open"); selected(graph.a)
        assertEquals(graph.b, saved.returnRecipientId)
        click("modules-open")
        waitFor { !modules.loading && modules.details?.let { it.fitId == graph.a && it.revision == fit(graph.a).revision } == true }
        val armorIndex = fit(graph.a).modules.single { it.name == "Medium Remote Armor Repairer II" }.index
        click("modules-bulk-states")
        waitFor { !states.loading && states.options?.let { it.fitId == graph.a && it.revision == fit(graph.a).revision } == true }
        click("bulk-states-reference-$armorIndex")
        assertEquals(setOf(armorIndex), states.selected); assertEquals(BulkScope.SELECTED, states.scope)
        assertEquals(ModuleState.ONLINE, states.options!!.modules.single { it.index == armorIndex }.clickStates.getValue(StateClick.CYCLE))
        oneEdit(graph.a) { click("bulk-states-apply") }
        waitFor { !states.loading && states.options?.revision == fit(graph.a).revision }
        assertNull(states.error)
        assertEquals(ModuleState.ONLINE, fit(graph.a).modules.single { it.index == armorIndex }.state)
        waitFor { graph.recipients.all { fit(it).revision > revisions.getValue(it).revision } }
        for (id in graph.recipients) assertEquals(beforeHistory.getValue(id).undoCount, history(id).undoCount)
        click("projections-return"); selected(graph.b)
        compose.onNodeWithTag("projections-recipient").assertTextContains(fit(graph.b).name, substring = true)
        assertNull(saved.returnRecipientId)
        click("projections-back")
        val edited = listOf(graph.b, graph.c, graph.a).associateWith { screens(it) }
        for (id in graph.recipients) assertTrue("Source armor state refreshes $id", armor(edited.getValue(id)) < armor(baseline.getValue(id)))
        assertTrue(cap(edited.getValue(graph.a), "use") < cap(baseline.getValue(graph.a), "use"))
        assertTrue(edited.getValue(graph.a).output.outgoing.getValue("armor").current.value.numberOrNull()!! <
            baseline.getValue(graph.a).output.outgoing.getValue("armor").current.value.numberOrNull()!!)
        // Incoming support does not change B/C's own outgoing components.
        for (id in graph.recipients) assertEquals(baseline.getValue(id).output, edited.getValue(id).output)
        select(graph.a)
        replay(graph.a); assertEquals(baseline, readAll(graph.ids.reversed()))
        replay(graph.a, true); assertEquals(edited, readAll(graph.ids))
        replay(graph.a); assertEquals(baseline, readAll(graph.ids))
        assertEquals(beforeHistory.getValue(graph.a).undoCount, history(graph.a).undoCount)
        assertEquals(1, history(graph.a).redoCount)
    }

    private fun rangeStateAndNullableDraft(graph: Graph, baseline: Map<String, Values>) {
        // This input is the original ordinary armor fixture's optimal + falloff.
        val falloff = fixture("tank-expected.json", "Projected Armor falloff").getJSONObject("projection").getDouble("range_m")
        select(graph.b); click("projections-open")
        click("projection-${graph.a}-range"); text("projections-draft-input", (falloff / 1000).toString())
        oneEdit(graph.b) { click("projections-draft-save") }
        assertEquals(falloff, link(graph.a, graph.b).rangeM!!, 0.0)
        assertEquals(ProjectionSnapshot(graph.b, null, true, 1), link(graph.b, graph.a))
        assertEquals(ProjectionSnapshot(graph.a, null, true, 1), link(graph.a, graph.c))
        val ranged = readAll(graph.ids)
        assertTrue(armor(ranged.getValue(graph.b)) < armor(baseline.getValue(graph.b)))
        assertTrue(cap(ranged.getValue(graph.b), "recharge") < cap(baseline.getValue(graph.b), "recharge"))
        for (id in listOf(graph.a, graph.c)) assertEquals(baseline.getValue(id), ranged.getValue(id))
        replay(graph.b); assertEquals(baseline, readAll(graph.ids))
        replay(graph.b, true); assertEquals(ranged, readAll(graph.ids.reversed()))

        click("projection-${graph.a}-range"); text("projections-draft-input", "0")
        oneEdit(graph.b) { click("projections-draft-save") }
        assertEquals(0.0, link(graph.a, graph.b).rangeM!!, 0.0)
        click("projection-${graph.a}-range"); text("projections-draft-input", "")
        val retained = saved; val draft = saved.draft!!
        assertEquals(0.0, draft.anchor.link!!.rangeM!!, 0.0)
        assertEquals("0.0", draft.initial); assertEquals("", draft.text)
        val before = snapshots(graph.ids); val beforeHistory = histories(graph.ids)
        compose.activityRule.scenario.recreate(); selected(graph.b)
        assertSame(retained, saved); assertSame(draft, saved.draft)
        assertEquals(before, snapshots(graph.ids)); assertEquals(beforeHistory, histories(graph.ids))
        compose.onNodeWithTag("projections-draft-save").assertIsEnabled()
        oneEdit(graph.b) { click("projections-draft-save") }
        assertNull(link(graph.a, graph.b).rangeM); assertNull(saved.draft)
        assertEquals(baseline, readAll(graph.ids))

        // Changing B -> A leaves A -> B and A -> C enabled and numerically intact.
        select(graph.a)
        oneEdit(graph.a) { click("projection-${graph.b}-active") }
        assertFalse(link(graph.b, graph.a).active)
        assertTrue(link(graph.a, graph.b).active); assertTrue(link(graph.a, graph.c).active)
        val disabled = readAll(graph.ids)
        assertTrue(armor(disabled.getValue(graph.a)) < armor(baseline.getValue(graph.a)))
        assertTrue(cap(disabled.getValue(graph.a), "recharge") < cap(baseline.getValue(graph.a), "recharge"))
        assertEquals(baseline.getValue(graph.a).output, disabled.getValue(graph.a).output)
        for (id in graph.recipients) assertEquals(baseline.getValue(id), disabled.getValue(id))
        oneEdit(graph.a) { click("projection-${graph.b}-active") }
        assertEquals(baseline, readAll(graph.ids))
        click("projections-back")
    }

    private fun incomingSettled(id: String) = waitFor {
        !incoming.loading && !incoming.editing && incoming.currentDetails?.let { it.fitId == id && it.revision == fit(id).revision } == true
    }
    private fun incomingNeutralizer(graph: Graph, baseline: Map<String, Values>) {
        select(graph.a); click("projected-modules-open"); incomingSettled(graph.a)
        compose.onNodeWithTag("projected-modules-empty").assertExists()
        click("projected-modules-browse")
        val equipment = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
        waitFor { equipment.catalog != null }
        val item = equipment.catalog!!.items.single { it.name == "Medium Energy Neutralizer II" }
        compose.runOnUiThread { equipment.selectedId = item.id }
        waitFor { !incoming.addLoading && incoming.currentAdd(item.id) != null }
        assertTrue(incoming.currentAdd(item.id)!!.enabled)
        oneEdit(graph.a) { click("equipment-project-module") }; incomingSettled(graph.a)
        val row = incoming.currentDetails!!.modules.single()
        assertEquals(item.id, row.itemId); assertEquals(ModuleState.ACTIVE, row.state); assertNull(row.rangeM)
        shown("projected-module-${row.index}-state", "State: ACTIVE")
        val affected = readAll(graph.ids)
        assertTrue(cap(affected.getValue(graph.a), "use") > cap(baseline.getValue(graph.a), "use"))
        assertEquals(baseline.getValue(graph.a).output, affected.getValue(graph.a).output)
        for (id in graph.recipients) assertEquals(baseline.getValue(id), affected.getValue(id))
        oneEdit(graph.a) { click("projected-module-${row.index}-remove") }; incomingSettled(graph.a)
        compose.onNodeWithTag("projected-modules-empty").assertExists()
        assertEquals(baseline, readAll(graph.ids))
        click("projected-modules-back")
    }

    private fun removeDirectionAndDeleteStaleSource(graph: Graph, baseline: Map<String, Values>) {
        select(graph.a); click("projections-open")
        oneEdit(graph.a) { click("projection-${graph.b}-remove") }
        assertTrue(fit(graph.a).projections.isEmpty())
        for (id in graph.recipients) assertEquals(listOf(ProjectionSnapshot(graph.a, null, true, 1)), fit(id).projections)
        val removed = readAll(graph.ids)
        assertTrue(armor(removed.getValue(graph.a)) < armor(baseline.getValue(graph.a)))
        for (id in graph.recipients) assertEquals(baseline.getValue(id), removed.getValue(id))
        select(graph.c); click("projection-${graph.a}-range"); text("projections-draft-input", "0")
        val stale = saved.draft!!
        val previousHistory = histories(graph.recipients)
        // Source deletion is NON_HISTORY. It must prune both remaining edges.
        send(BridgeOperation.DeleteFit(graph.a, true), graph.a)
        waitFor { EngineRuntime.library.value.none { it.id == graph.a } && graph.recipients.all { fit(it).projections.isEmpty() } }
        assertTrue(saved.draftStale); assertFalse(saved.canReview); assertEquals("0", saved.draft!!.text)
        compose.onNodeWithTag("projections-draft-save").assertIsNotEnabled()
        compose.onNodeWithTag("projections-draft-review").assertIsNotEnabled()
        compose.onNodeWithTag("projection-${graph.a}-open").assertDoesNotExist()
        for (id in graph.recipients) assertTrue("Deletion adds no history", history(id).undoCount <= previousHistory.getValue(id).undoCount)
        val after = snapshots(graph.recipients); val afterHistory = histories(graph.recipients)
        compose.runOnUiThread { saved.save(context); saved.add(context, stale.anchor) }
        val rejected = EngineRuntime.request(context, BridgeOperation.AddProjectedFit(graph.a, graph.c), stale.anchor.revisions)
            .get(120, TimeUnit.SECONDS)
        assertFalse(rejected.isSuccess)
        assertEquals(BridgeErrorCode.UNKNOWN_FIT, rejected.error?.code)
        assertEquals(after, snapshots(graph.recipients)); assertEquals(afterHistory, histories(graph.recipients))
        click("projections-draft-discard"); click("projections-back")
        for (id in graph.recipients) {
            val current = screens(id)
            assertTrue("Deleted source no longer repairs $id", armor(current) < armor(baseline.getValue(id)))
            assertTrue("Deleted source no longer transfers capacitor to $id", cap(current, "recharge") < cap(baseline.getValue(id), "recharge"))
            assertEquals(baseline.getValue(id).output, current.output)
        }
        assertEquals(after, snapshots(graph.recipients)); assertEquals(afterHistory, histories(graph.recipients))
    }
}
