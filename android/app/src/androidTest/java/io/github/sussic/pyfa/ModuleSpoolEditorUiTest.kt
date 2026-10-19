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
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred native gate: disposable durable data, airplane mode, offline_features_phase=spool. */
@RunWith(AndroidJUnit4::class)
class ModuleSpoolEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[ModuleSpoolModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun settled(id: String) = waitFor { !model.editing && !model.loading && model.currentDetails?.fitId == id }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun send(operation: BridgeOperation, id: String? = null): BridgeResponse {
        val result = EngineRuntime.request(context, operation, id?.let { mapOf(it to fit(it).revision) } ?: emptyMap()).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess); return result
    }
    private fun create(ship: String, modules: List<ModuleSpec>): String = send(BridgeOperation.CreateFit(FitSpec("Native spool $ship", ship, 5,
        false, DamagePattern(25.0, 25.0, 25.0, 25.0), Security(SystemSecurity.HISEC, 0.0), modules, emptyList()))).fits.single().id
    private fun output(id: String) = EngineRuntime.outputDetails(context, id).get(30, TimeUnit.SECONDS)
        .firepower.getValue("raw").getValue("weapon").spool.current.value.numberOrNull()!!
    private fun history(id: String, redo: Boolean) {
        val revision = fit(id).revision
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision == revision }
        click(if (redo) "history-redo" else "history-undo")
        waitFor { fit(id).revision > revision }; settled(id)
    }
    @Test fun sourceChoicesZeroResetClampingHistoryRecreationStaleIdentityAndHeat() {
        assertEquals("spool", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        var id = create("Vedmak", listOf(ModuleSpec("Heavy Entropic Disintegrator II", ModuleState.ACTIVE, "Occult M")))
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        click("modules-open"); click("modules-spool"); settled(id)
        var row = model.currentDetails!!.modules.single()
        assertNull(row.overrideCycles); assertTrue(row.maximumCycles > 0)
        compose.onNodeWithTag("spool-mode-${row.index}").assertTextEquals("Using global default")
        val full = output(id)
        val beforeHistory = EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).history.undoCount
        click("spool-choices-${row.index}"); click("spool-choice-${row.index}-0"); settled(id)
        row = model.currentDetails!!.modules.single()
        assertEquals(0, row.overrideCycles); assertEquals(0, row.currentCycles); assertEquals(0.0, row.currentSeconds, 0.0)
        compose.onNodeWithTag("spool-mode-${row.index}").assertTextEquals("Explicit override: 0 cycles")
        assertTrue(output(id) < full)
        assertEquals(beforeHistory + 1, EngineRuntime.offlineFeatureState(context, id).get(30, TimeUnit.SECONDS).history.undoCount)
        history(id, false); assertNull(model.currentDetails!!.modules.single().overrideCycles)
        assertEquals(full, output(id), 0.0)
        history(id, true); assertEquals(0, model.currentDetails!!.modules.single().overrideCycles)
        compose.activityRule.scenario.recreate(); settled(id)
        compose.onNodeWithTag("spool-choice-${row.index}-0").assertIsNotEnabled()
        click("spool-reset-${row.index}"); settled(id)
        assertNull(model.currentDetails!!.modules.single().overrideCycles); assertEquals(full, output(id), 0.0)
        // Raw oversized overrides remain durable while EOS reports its effective clamp.
        id = create("Vedmak", listOf(ModuleSpec("Heavy Entropic Disintegrator II", ModuleState.ACTIVE, "Occult M", spoolCycles = 999)))
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS); settled(id)
        row = model.currentDetails!!.modules.single()
        click("spool-choices-${row.index}")
        assertEquals(999, row.overrideCycles); assertEquals(row.maximumCycles, row.currentCycles)
        compose.onNodeWithTag("spool-choice-${row.index}-${row.currentCycles}").assertIsEnabled()
            .assertTextEquals("${row.currentCycles} cycles · applied")
        click("spool-choice-${row.index}-${row.currentCycles}"); settled(id)
        assertEquals(row.currentCycles, model.currentDetails!!.modules.single().overrideCycles)
        history(id, false); assertEquals(999, model.currentDetails!!.modules.single().overrideCycles)
        val stale = model.currentDetails!!
        send(BridgeOperation.RenameFit(id, "Renamed spool fit"), id); settled(id)
        val renamed = fit(id)
        compose.runOnUiThread { model.set(context, stale, stale.modules.single(), 0) }
        assertEquals(renamed, fit(id)); assertFalse(model.editing)
        // Invalid source choice and a removed object cannot redirect to a new module at its position.
        val current = model.currentDetails!!
        compose.runOnUiThread { model.set(context, current, current.modules.single(), -1) }
        assertEquals(renamed, fit(id))
        val variant = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS).items.single { it.name == "Heavy Entropic Disintegrator I" }
        send(BridgeOperation.ChangeVariation(id, VariationContext.MODULE, row.index, variant.id), id); settled(id)
        assertEquals(999, model.currentDetails!!.modules.single().overrideCycles)
        val variationFit = fit(id)
        compose.runOnUiThread { model.set(context, current, current.modules.single(), 0) }
        assertEquals(variationFit, fit(id))
        click("spool-back"); compose.onNodeWithTag("modules-spool").assertExists()
        send(BridgeOperation.SetModuleStates(id, listOf(row.index), ModuleState.OVERHEATED), id)
        waitFor { ViewModelProvider(compose.activity)[ModuleEditorModel::class.java].details?.revision == fit(id).revision }
        click("modules-arrange")
        val rackModel = ViewModelProvider(compose.activity)[RackEditorModel::class.java]
        waitFor { !rackModel.loading && rackModel.options?.revision == fit(id).revision }
        val heat = rackModel.options!!.modules.single { it.id != null }.heat!!
        click("rack-heat-details-${row.index}")
        compose.onNodeWithTag("rack-heat-seconds-${row.index}").assertTextEquals("Full precision time to burnout: ${heat.seconds.value.raw} s")
        heat.probabilities.forEachIndexed { index, sample ->
            compose.onNodeWithTag("rack-heat-probability-${row.index}-$index").assertTextEquals(
                "Heat-damage probability at ${sample.seconds} s: ${sample.value} (0–1)")
        }
        click("rack-back"); click("modules-spool"); settled(id)
        val repair = create("Rodiva", listOf(ModuleSpec("Heavy Mutadaptive Remote Armor Repairer II", ModuleState.ACTIVE)))
        EngineRuntime.selectFit(context, repair).get(30, TimeUnit.SECONDS); settled(repair)
        var rr = model.currentDetails!!.modules.single()
        assertTrue(rr.maximumSeconds > 0)
        click("spool-choices-${rr.index}"); click("spool-choice-${rr.index}-0"); settled(repair)
        rr = model.currentDetails!!.modules.single(); assertEquals(0.0, rr.currentSeconds, 0.0)
        click("spool-reset-${rr.index}"); settled(repair)
        assertNull(model.currentDetails!!.modules.single().overrideCycles)
        val empty = create("Vexor", emptyList())
        EngineRuntime.selectFit(context, empty).get(30, TimeUnit.SECONDS); settled(empty)
        compose.onNodeWithTag("spool-empty").assertExists()
        // Last requested fit wins even when earlier reads are still on the serialized worker.
        compose.runOnUiThread { model.load(context, fit(id), true); model.load(context, fit(empty), true) }
        settled(empty); assertTrue(model.currentDetails!!.modules.isEmpty())
    }
}
