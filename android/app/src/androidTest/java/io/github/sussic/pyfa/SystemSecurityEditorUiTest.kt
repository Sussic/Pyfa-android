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

/** Deferred offline native gate: offline_features_phase=system_security on disposable app data. */
@RunWith(AndroidJUnit4::class)
class SystemSecurityEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[SystemSecurityModel::class.java]
    private val services get() = ViewModelProvider(compose.activity)[StructureServiceEditorModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000,test); compose.waitForIdle() }
    private fun settled(id: String) = waitFor { !model.loading && !model.editing && model.currentDetails?.fitId == id }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun send(operation: BridgeOperation, id: String? = null): BridgeResponse {
        val result = EngineRuntime.request(context,operation,id?.let { mapOf(it to fit(it).revision) } ?: emptyMap()).get(120,TimeUnit.SECONDS)
        assertTrue(result.error?.message,result.isSuccess); return result
    }
    private fun create(ship: String, modules: List<ModuleSpec>) = send(BridgeOperation.CreateFit(FitSpec("Native system security $ship",ship,5,false,
        DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),modules,emptyList()))).fits.single().id
    private fun history(id: String, redo: Boolean) {
        val revision=fit(id).revision
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision == revision }
        click(if (redo) "history-redo" else "history-undo")
        waitFor { fit(id).revision > revision }; settled(id)
    }
    private fun assertRigResult(id: String, system: SystemSecurity) {
        // Pinned Fortizar + Standup L-Set Target Acquisition Array I, all skills V.
        // EOS/source fixture values, not a native reconstruction of Effect6672.
        val scan = if (system == SystemSecurity.HISEC) 90.0 else 100.0
        val range = if (system == SystemSecurity.HISEC) 418000.00000000006 else 425600.00000000006
        val details = EngineRuntime.targetingDetails(context,id).get(30,TimeUnit.SECONDS)
        assertEquals(scan,checkNotNull(details.main.getValue("scan_resolution").value.numberOrNull()),1e-9)
        assertEquals(range,checkNotNull(details.main.getValue("range").value.numberOrNull()),1e-6)
        assertEquals("mm",details.main.getValue("scan_resolution").unit); assertEquals("m",details.main.getValue("range").unit)
        assertEquals(scan,checkNotNull(fit(id).stats.getValue("scan_resolution").value.numberOrNull()),1e-9)
        assertEquals(range,checkNotNull(fit(id).stats.getValue("max_target_range").value.numberOrNull()),1e-6)
    }
    @Test fun structureEntryExactModesRealBonusesHistoryRecreationStaleAndShipGates() {
        assertEquals("system_security",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val id=create("Fortizar",listOf(ModuleSpec("Standup L-Set Target Acquisition Array I",ModuleState.ONLINE)))
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        click("services-open"); waitFor { !services.loading && services.options?.fitId == id }
        click("services-system-security"); settled(id)
        assertEquals(listOf("High Security","Low Security","Null Security","W-Space"),model.currentDetails!!.choices.map { it.label })
        model.currentDetails!!.choices.forEach { compose.onNodeWithTag("system-security-${it.id.name}").assertTextEquals(it.label) }
        compose.onNodeWithTag("system-security-HISEC").assertIsNotEnabled()
        compose.onNodeWithTag("system-security-current").assertTextEquals("Current: High Security")
        assertRigResult(id,SystemSecurity.HISEC)
        val baseline=fit(id).stats
        val initial=model.currentDetails!!
        val low=initial.choices.single { it.id == SystemSecurity.LOWSEC }
        val initialHistory=EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS).history
        compose.runOnUiThread {
            assertFalse(model.canSet(initial.copy(),low)); assertFalse(model.canSet(initial,low.copy()))
            model.set(context,initial,initial.choices.single { it.id == initial.system })
        }
        assertEquals(initial.revision,fit(id).revision)
        assertEquals(initialHistory,EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS).history)
        click("system-security-LOWSEC"); settled(id)
        assertRigResult(id,SystemSecurity.LOWSEC)
        assertEquals(initialHistory.undoCount+1,EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS).history.undoCount)
        val retained=model
        compose.activityRule.scenario.recreate(); settled(id)
        assertSame(retained,model)
        compose.onNodeWithTag("system-security-current").assertTextEquals("Current: Low Security")
        compose.onNodeWithTag("system-security-LOWSEC").assertIsNotEnabled()
        val afterLow=fit(id)
        compose.runOnUiThread { model.set(context,initial,low) }
        assertEquals(afterLow,fit(id))
        history(id,false); assertEquals(baseline,fit(id).stats); assertRigResult(id,SystemSecurity.HISEC)
        history(id,true); assertRigResult(id,SystemSecurity.LOWSEC)
        click("system-security-NULLSEC"); settled(id); assertRigResult(id,SystemSecurity.NULLSEC)
        val nullStats=fit(id).stats
        click("system-security-WSPACE"); settled(id); assertRigResult(id,SystemSecurity.WSPACE)
        assertEquals(nullStats,fit(id).stats)
        // Ordinary no-op still publishes a revision; it must not introduce an undo entry.
        val beforeNoop=EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS).history
        send(BridgeOperation.SetSystemSecurity(id,SystemSecurity.WSPACE),id); settled(id)
        assertEquals(beforeNoop,EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS).history)
        val stale=model.currentDetails!!
        send(BridgeOperation.RenameFit(id,"Security changed outside this screen"),id); settled(id)
        val beforeRejected=fit(id)
        compose.runOnUiThread { model.set(context,stale,stale.choices.first()) }
        assertEquals(beforeRejected,fit(id))
        val rejected=EngineRuntime.request(context,BridgeOperation.SetSystemSecurity(id,SystemSecurity.HISEC),
            mapOf(id to stale.revision)).get(120,TimeUnit.SECONDS)
        assertFalse(rejected.isSuccess); assertEquals(BridgeErrorCode.REVISION_CONFLICT,rejected.error!!.code)
        assertEquals(beforeRejected,fit(id))
        val ship=create("Vexor",emptyList())
        EngineRuntime.selectFit(context,ship).get(30,TimeUnit.SECONDS)
        compose.runOnUiThread { model.load(context,fit(id),true); model.load(context,fit(ship),true) }
        settled(ship); assertFalse(model.currentDetails!!.isStructure)
        compose.onNodeWithTag("system-security-not-structure").assertExists()
        SystemSecurity.entries.forEach { compose.onNodeWithTag("system-security-${it.name}").assertDoesNotExist() }
        val shipBefore=fit(ship)
        val refused=EngineRuntime.request(context,BridgeOperation.SetSystemSecurity(ship,SystemSecurity.LOWSEC),
            mapOf(ship to shipBefore.revision)).get(120,TimeUnit.SECONDS)
        assertFalse(refused.isSuccess); assertEquals(shipBefore,fit(ship))
        click("system-security-back"); waitFor { !services.loading && services.options?.fitId == ship }
        compose.onNodeWithTag("services-not-structure").assertExists()
        compose.onNodeWithTag("services-system-security").assertDoesNotExist()
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        waitFor { !services.loading && services.options?.fitId == id }
        click("services-system-security"); settled(id)
        compose.onNodeWithTag("system-security-current").assertTextEquals("Current: W-Space")
        click("system-security-HISEC"); settled(id)
        assertEquals(baseline,fit(id).stats); assertRigResult(id,SystemSecurity.HISEC)
    }
}
