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

/** Deferred device gate: disposable durable data, airplane mode, offline_features_phase=rah. */
@RunWith(AndroidJUnit4::class)
class ModuleRahEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[ModuleRahModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun settled(id: String) = waitFor { !model.editing && !model.loading && model.currentDetails?.fitId == id }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun send(operation: BridgeOperation, id: String? = null): BridgeResponse {
        val result = EngineRuntime.request(context, operation, id?.let { mapOf(it to fit(it).revision) } ?: emptyMap()).get(120, TimeUnit.SECONDS)
        assertTrue(result.error?.message, result.isSuccess); return result
    }
    private fun create(name: String, modules: List<ModuleSpec>): String = send(BridgeOperation.CreateFit(FitSpec(name,"Vexor",5,false,
        DamagePattern(25.0,25.0,25.0,25.0), Security(SystemSecurity.HISEC,0.0),modules,emptyList()))).fits.single().id
    private fun armor(id: String) = listOf("em","thermal","kinetic","explosive").map {
        checkNotNull(fit(id).stats.getValue("armor_${it}_resonance").value.numberOrNull())
    }
    private fun history(id: String, redo: Boolean) {
        val revision = fit(id).revision
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision == revision }
        click(if (redo) "history-redo" else "history-undo")
        waitFor { fit(id).revision > revision }; settled(id)
    }
    @Test fun inheritedVersusExplicitPatternsDisableResetSearchHistoryRecreationAndStaleRows() {
        assertEquals("rah", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val id = create("Native reactive armor",listOf(ModuleSpec("Reactive Armor Hardener",ModuleState.ACTIVE)))
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        click("modules-open"); click("modules-rah"); settled(id)
        var row = model.currentDetails!!.modules.single()
        assertEquals(RahMode.FIT,row.mode)
        compose.onNodeWithTag("rah-mode-${row.index}").assertTextEquals("Using fit pattern")
        val inheritedUniform = armor(id)
        click("rah-choose-${row.index}"); settled(id)
        assertTrue(model.currentOptions!!.total > 20)
        assertEquals(20, model.currentOptions!!.entries.size)
        compose.onNodeWithTag("rah-pattern--21").assertDoesNotExist()
        click("rah-pattern-next"); settled(id); assertEquals(1L,model.patternPage)
        click("rah-pattern-previous"); settled(id); assertEquals(0L,model.patternPage)
        compose.onNodeWithTag("rah-search").performTextReplacement("Uniform"); settled(id)
        val uniform = model.currentOptions!!.entries.single()
        assertEquals("damage:builtin:-1",uniform.id)
        val before = EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS).history.undoCount
        click("rah-pattern--1"); settled(id)
        row = model.currentDetails!!.modules.single()
        assertEquals(RahMode.BUILTIN,row.mode); assertEquals(-1,row.patternId)
        assertEquals(inheritedUniform,armor(id))
        assertEquals(before+1,EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS).history.undoCount)
        compose.activityRule.scenario.recreate(); settled(id)
        // Recreation is a new screen incarnation, not ownership of the old query/request.
        assertNull(model.selectedKey)
        click("rah-choose-${row.index}"); settled(id)
        compose.onNodeWithTag("rah-search").performTextReplacement("Uniform"); settled(id)
        compose.onNodeWithTag("rah-pattern--1").assertIsNotEnabled()
        // An explicit Uniform remains independent when the fit's incoming damage changes.
        send(BridgeOperation.SetDamagePattern(id,DamagePattern(1.0,0.0,0.0,0.0)),id); settled(id)
        assertEquals(inheritedUniform,armor(id))
        assertEquals(RahComponents(1.0,0.0,0.0,0.0),model.currentDetails!!.fitPattern.components)
        click("rah-fit-${row.index}"); settled(id)
        assertEquals(RahMode.FIT,model.currentDetails!!.modules.single().mode)
        val inheritedEm = armor(id); assertNotEquals(inheritedUniform,inheritedEm)
        history(id,false); assertEquals(RahMode.BUILTIN,model.currentDetails!!.modules.single().mode)
        assertEquals(inheritedUniform,armor(id))
        history(id,true); assertEquals(RahMode.FIT,model.currentDetails!!.modules.single().mode)
        assertEquals(inheritedEm,armor(id))
        click("rah-disable-${row.index}"); settled(id)
        assertEquals(RahMode.DISABLED,model.currentDetails!!.modules.single().mode)
        val disabled = armor(id)
        send(BridgeOperation.SetDamagePattern(id,DamagePattern(0.0,0.0,0.0,1.0)),id); settled(id)
        assertEquals(disabled,armor(id))
        compose.onNodeWithTag("rah-components-${row.index}").assertDoesNotExist()
        // The search draft can be cleared or replaced without changing any saved input/history.
        val noEdit = fit(id)
        compose.onNodeWithTag("rah-search").performTextReplacement("no matching source pattern"); settled(id)
        compose.onNodeWithTag("rah-no-matches").assertExists(); assertEquals(noEdit,fit(id))
        compose.onNodeWithTag("rah-search").performTextReplacement("[Generic]EM"); settled(id)
        val em = model.currentOptions!!.entries.single()
        val emId = em.id.substringAfterLast(':').toInt()
        click("rah-pattern-$emId"); settled(id)
        assertEquals(inheritedEm,armor(id))
        val stale = model.currentDetails!!
        send(BridgeOperation.RenameFit(id,"Renamed reactive armor"),id); settled(id)
        val renamed = fit(id)
        compose.runOnUiThread { model.set(context,stale,stale.modules.single(),RahMode.DISABLED) }
        assertEquals(renamed,fit(id)); assertFalse(model.editing)
        val current = model.currentDetails!!
        compose.runOnUiThread { model.set(context,current,current.modules.single(),RahMode.BUILTIN,-999999) }
        assertEquals(renamed,fit(id))
        send(BridgeOperation.SetModuleStates(id,listOf(row.index),ModuleState.OFFLINE),id); settled(id)
        assertEquals(emId,model.currentDetails!!.modules.single().patternId)
        send(BridgeOperation.SetModuleStates(id,listOf(row.index),ModuleState.ACTIVE),id); settled(id)
        assertEquals(inheritedEm,armor(id))
        val beforeRemove = model.currentDetails!!
        send(BridgeOperation.RemoveModule(id,row.index),id); settled(id)
        compose.onNodeWithTag("rah-empty").assertExists()
        val removed = fit(id)
        compose.runOnUiThread { model.set(context,beforeRemove,beforeRemove.modules.single(),RahMode.FIT) }
        assertEquals(removed,fit(id))
        history(id,false); assertEquals(emId,model.currentDetails!!.modules.single().patternId)
        assertEquals(inheritedEm,armor(id))
        click("rah-back"); compose.onNodeWithTag("modules-rah").assertExists()
        click("modules-rah"); settled(id)
        val empty = create("Empty reactive armor view",emptyList())
        EngineRuntime.selectFit(context,empty).get(30,TimeUnit.SECONDS); settled(empty)
        compose.onNodeWithTag("rah-empty").assertExists()
        compose.runOnUiThread { model.load(context,fit(id),true); model.load(context,fit(empty),true) }
        settled(empty); assertTrue(model.currentDetails!!.modules.isEmpty())
    }
}
