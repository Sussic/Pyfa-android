package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import java.util.concurrent.TimeUnit
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred device gate: offline_features_phase=projected_fits on disposable durable data. */
@RunWith(AndroidJUnit4::class)
class ProjectedFitEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[ProjectedFitModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun replace(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun prepare() {
        assertEquals("projected_fits", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
    }
    private fun send(operation: BridgeOperation, vararg ids: String): BridgeResponse {
        val result = EngineRuntime.request(context, operation, ids.toSet().associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess); return result
    }
    private fun create(label: String, module: String? = null): String = send(BridgeOperation.CreateFit(FitSpec(
        "$label ${System.nanoTime()}", "Rifter", 5, false, DamagePattern(25.0,25.0,25.0,25.0), Security(SystemSecurity.HISEC,0.0),
        module?.let { listOf(ModuleSpec(it, ModuleState.ACTIVE)) } ?: emptyList(), emptyList()))).fits.single().id
    private fun changed(id: String, action: () -> Unit) {
        val revision = fit(id).revision; action(); waitFor { !model.busy && fit(id).revision > revision }
    }
    private fun history(id: String, redo: Boolean) {
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision == fit(id).revision }
        changed(id) { click(if (redo) "history-redo" else "history-undo") }
    }
    private fun link(source: String, target: String) = fit(target).projections.single { it.sourceId == source }
    private fun saveText(target: String, text: String) { replace("projections-draft-input", text); changed(target) { click("projections-draft-save") } }

    @Test fun sourcePickerAtomicControlsRealStateConsequencesHistorySelfAndSourceReturn() {
        prepare()
        val source = create("Native projected scrambler", "Warp Scrambler II")
        val target = create("Native projected recipient", "5MN Microwarpdrive II")
        EngineRuntime.selectFit(context, target).get(30, TimeUnit.SECONDS)
        val baseline = fit(target)
        assertEquals(ModuleState.ACTIVE, baseline.modules.single { it.name == "5MN Microwarpdrive II" }.state)
        val recent = EngineRuntime.recent.value.toList()
        click("projections-open")
        compose.onNodeWithTag("projections-empty").assertExists()
        replace("projections-search", fit(source).name)
        changed(target) { click("projection-$source-add") }
        assertEquals(ProjectionSnapshot(source, null, true, 1), link(source, target))
        // Original checkStates consequence: scrambler disables the active MWD input.
        assertEquals(ModuleState.ONLINE, fit(target).modules.single { it.name == "5MN Microwarpdrive II" }.state)
        assertTrue(fit(target).stats.getValue("max_velocity").value.numberOrNull()!! < baseline.stats.getValue("max_velocity").value.numberOrNull()!!)
        history(target, false)
        assertTrue(fit(target).projections.isEmpty()); assertEquals(baseline.modules, fit(target).modules); assertEquals(baseline.stats, fit(target).stats)
        history(target, true)
        assertEquals(ModuleState.ONLINE, fit(target).modules.single { it.name == "5MN Microwarpdrive II" }.state)
        click("projection-$source-range"); saveText(target, "12.5"); assertEquals(12500.0, link(source,target).rangeM!!, 0.0)
        click("projection-$source-range"); saveText(target, "0"); assertEquals(0.0, link(source,target).rangeM!!, 0.0)
        click("projection-$source-range"); replace("projections-draft-input","0")
        val beforeSameRange=fit(target); val beforeSameHistory=EngineRuntime.editHistory(context,target).get(30,TimeUnit.SECONDS)
        click("projections-draft-save"); assertNull(model.draft)
        assertEquals(beforeSameRange,fit(target)); assertEquals(beforeSameHistory,EngineRuntime.editHistory(context,target).get(30,TimeUnit.SECONDS))
        compose.onNodeWithTag("projections-message").assertTextContains("unchanged",substring=true)
        click("projection-$source-range"); saveText(target, ""); assertNull(link(source,target).rangeM)
        click("projection-$source-count"); saveText(target, "3"); assertEquals(3, link(source,target).amount)
        changed(target) { click("projection-$source-add") }; assertEquals(4, link(source,target).amount)
        changed(target) { click("projection-$source-active") }
        assertEquals(ProjectionSnapshot(source, null, false, 4), link(source,target))
        click("projection-$source-count"); replace("projections-draft-input", "21")
        val beforeInvalid = fit(target); click("projections-draft-save")
        compose.onNodeWithTag("projections-error").assertTextContains("0 to 20", substring = true)
        assertEquals(beforeInvalid, fit(target)); click("projections-draft-discard")
        replace("projections-search", fit(target).name)
        changed(target) { click("projection-$target-add") }; assertEquals(1, link(target,target).amount)
        changed(target) { click("projection-$target-remove") }; assertTrue(fit(target).projections.none { it.sourceId == target })
        // A draft survives recreation and a source-edit excursion, then requires explicit review.
        click("projection-$source-range"); replace("projections-draft-input", "1.25")
        val retained = model; compose.activityRule.scenario.recreate(); compose.waitForIdle()
        assertSame(retained, model); assertEquals("1.25", model.draft!!.text)
        click("projection-$source-open"); waitFor { !model.busy && (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id == source }
        click("modules-open")
        compose.activityRule.scenario.recreate(); compose.waitForIdle()
        assertEquals(target,model.returnRecipientId); assertEquals("1.25",model.draft!!.text)
        send(BridgeOperation.RenameFit(source, "Edited projected source ${System.nanoTime()}"), source)
        click("projections-return"); waitFor { !model.busy && (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id == target }
        compose.onNodeWithTag("projections-recipient").assertExists()
        compose.onNodeWithTag("projections-draft-stale").assertExists()
        compose.onNodeWithTag("projections-draft-save").assertIsNotEnabled()
        assertEquals("1.25", model.draft!!.text)
        click("projections-draft-review"); assertFalse(model.draftStale); assertEquals("", model.draft!!.text)
        click("projections-draft-discard")
        click("projection-$source-count"); saveText(target, "20")
        replace("projections-search",fit(source).name)
        val atLimit=EngineRuntime.editHistory(context,target).get(30,TimeUnit.SECONDS).undoCount
        compose.onNodeWithTag("projection-$source-add").assertIsNotEnabled()
        assertEquals(20,link(source,target).amount)
        assertEquals(atLimit,EngineRuntime.editHistory(context,target).get(30,TimeUnit.SECONDS).undoCount)
        click("projection-$source-count"); saveText(target, "0")
        assertTrue(fit(target).projections.isEmpty())
        assertEquals(recent, EngineRuntime.recent.value)
        click("projections-back"); compose.onNodeWithTag("projections-open").assertExists()
    }

    @Test fun legacyCountsStaleEndpointsDeletionAndPendingFailuresPreserveDraftAndHistory() {
        prepare()
        val source = create("Legacy projection source")
        val target = create("Legacy projection recipient")
        send(BridgeOperation.AddProjection(source, target, rangeM = 2500.0, active = false, amount = 35), source, target)
        EngineRuntime.selectFit(context, target).get(30, TimeUnit.SECONDS)
        click("projections-open")
        compose.onNodeWithTag("projection-$source-values").assertTextContains("Count: 35", substring = true)
        click("projection-$source-range"); saveText(target, "5"); assertEquals(35, link(source,target).amount)
        changed(target) { click("projection-$source-active") }; assertEquals(35, link(source,target).amount)
        replace("projections-search",fit(source).name)
        compose.onNodeWithTag("projection-$source-add").assertTextContains("Normalize count to 20",substring=true)
        changed(target) { click("projection-$source-add") }; assertEquals(20,link(source,target).amount)
        history(target,false); assertEquals(35,link(source,target).amount)
        click("projection-$source-count"); assertEquals("35", model.draft!!.text)
        val before = model.draft!!
        send(BridgeOperation.RenameFit(source, "Stale source ${System.nanoTime()}"), source)
        waitFor { model.draftStale }
        val unchanged = fit(target)
        val history = EngineRuntime.editHistory(context,target).get(30,TimeUnit.SECONDS)
        compose.runOnUiThread { model.change("2"); model.save(context); model.add(context,before.anchor) }
        assertEquals(unchanged,fit(target)); assertEquals(history,EngineRuntime.editHistory(context,target).get(30,TimeUnit.SECONDS))
        send(BridgeOperation.DeleteFit(source,true), source)
        waitFor { fit(target).projections.isEmpty() }
        assertTrue(model.draftStale); assertFalse(model.canReview); assertEquals("2",model.draft!!.text)
        click("projections-draft-discard")
        val other = create("Pending projection source")
        EngineRuntime.selectFit(context,target).get(30,TimeUnit.SECONDS)
        var calls = 0
        lateinit var pending: CompletableFuture<BridgeResponse>
        val controlled = ProjectedFitModel { _, _, _ -> calls += 1; pending }
        val anchor = controlled.anchor(fit(target),fit(other))
        pending = CompletableFuture()
        compose.runOnUiThread { controlled.add(context,anchor); controlled.add(context,anchor) }
        assertEquals(1,calls); assertTrue(controlled.busy)
        // No worker result may repaint the wrong selected fit with a late failure.
        EngineRuntime.selectFit(context,other).get(30,TimeUnit.SECONDS)
        pending.complete(BridgeResponse("request","session",BridgeStatus.ERROR,emptyList(),BridgeError(BridgeErrorCode.REVISION_CONFLICT,"Review current values.")))
        waitFor { !controlled.busy }; assertNull(controlled.error)
        compose.runOnUiThread { controlled.add(context,anchor) }; assertEquals(1,calls)
        EngineRuntime.selectFit(context,target).get(30,TimeUnit.SECONDS)
        val current = controlled.anchor(fit(target),fit(other))
        pending = CompletableFuture()
        compose.runOnUiThread { controlled.add(context,current) }
        pending.complete(BridgeResponse("request","session",BridgeStatus.ERROR,emptyList(),BridgeError(BridgeErrorCode.INVALID_EDIT,"Projection refused.")))
        waitFor { !controlled.busy }; assertEquals("Projection refused.",controlled.error)
        assertTrue(fit(target).projections.isEmpty())
    }
}
