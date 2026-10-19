package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.UUID
import java.util.concurrent.TimeUnit
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred disposable-data device gate. Merely compiling this is not Android execution. */
@RunWith(AndroidJUnit4::class)
class NamedModuleRahUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val rah get() = ViewModelProvider(compose.activity)[ModuleRahModel::class.java]
    private val library get() = ViewModelProvider(compose.activity)[OfflineDamagePatternsModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000,test);compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun call(fitId: String, operation: String, args: JSONObject, selected: String? = null): OfflineDamageResponse {
        val source=EngineRuntime.offlineFeatureState(context,fitId).get(120,TimeUnit.SECONDS).context
        return EngineRuntime.offlineDamagePatterns(context,OfflineDamageRequest(UUID.randomUUID().toString(),source,fitId,
            OfflineDamageView(selectedPatternId=selected),operation,OfflineFeatureCodec.json(args))).get(120,TimeUnit.SECONDS)
            .also { assertTrue(it.error?.message,it.ok) }
    }
    @Test fun namedAndUnavailableZeroChoicesDualHolderConfirmationAndUndo() {
        assertEquals("named_rah",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val created=EngineRuntime.request(context,BridgeOperation.CreateFit(FitSpec("Named RAH UI","Vexor",5,false,
            DamagePattern(1.0,0.0,0.0,0.0),Security(SystemSecurity.HISEC,0.0),
            listOf(ModuleSpec("Reactive Armor Hardener",ModuleState.ACTIVE)),emptyList()))).get(120,TimeUnit.SECONDS)
        assertTrue(created.error?.message,created.isSuccess);val fit=created.fits.single().id
        val prefix="Named RAH ${System.nanoTime()}"
        fun values(amount: Double)=JSONObject().put("emAmount",amount).put("thermalAmount",0.0).put("kineticAmount",0.0).put("explosiveAmount",0.0)
        val entry=call(fit,"create",JSONObject().put("name","$prefix positive").put("values",values(10.0))).state!!.detail!!.entry
        val zero=call(fit,"create",JSONObject().put("name","$prefix zero").put("values",values(0.0))).state!!.detail!!.entry
        EngineRuntime.selectFit(context,fit).get(30,TimeUnit.SECONDS)
        click("modules-open");click("modules-rah")
        waitFor { rah.available }
        val row=rah.currentDetails!!.modules.single();click("rah-choose-${row.index}")
        waitFor { rah.available && rah.currentOptions!=null }
        compose.onNodeWithTag("rah-search").performTextReplacement(prefix)
        waitFor { rah.available && rah.currentOptions?.view?.query==prefix }
        compose.onNodeWithTag("rah-pattern-${zero.id}").assertIsNotEnabled()
        click("rah-pattern-${entry.id}")
        waitFor { rah.available && rah.currentDetails?.modules?.singleOrNull()?.namedId==entry.id }
        val selected=call(fit,"read",JSONObject(),entry.id).state!!
        assertEquals("anonymous",selected.selection.kind)
        assertEquals(1L,selected.detail!!.entry.boundModuleCount);assertEquals(0L,selected.detail.entry.boundFitCount)
        call(fit,"assign",JSONObject().put("pattern_id",entry.id).put("revision",entry.revision).put("fit_revision",selected.fitRevision),entry.id)
        waitFor { rah.available }
        click("rah-back");click("modules-back");click("damage-patterns-open")
        waitFor { library.available }
        compose.onNodeWithTag("damage-patterns-search").performTextReplacement(prefix)
        waitFor { library.available && library.view.query==prefix }
        click("damage-pattern-select-${entry.id}");waitFor { library.available && library.detail?.entry?.id==entry.id }
        assertEquals(1L,library.detail!!.entry.boundFitCount);assertEquals(1L,library.detail!!.entry.boundModuleCount)
        assertEquals(1L,library.detail!!.entry.affectedFitCount)
        click("damage-pattern-delete")
        compose.onNodeWithText("Exactly 1 incoming fit(s) switch to Uniform and 1 local hardener(s) follow their respective Fit Pattern, across 1 distinct directly affected fit(s).",substring=true).assertExists()
        click("damage-pattern-delete-confirm");waitFor { library.available && library.detail?.entry?.id!=entry.id }
        assertEquals(RahMode.FIT,EngineRuntime.moduleRahDetails(context,fit).get(30,TimeUnit.SECONDS).modules.single().mode)
        assertEquals("damage:builtin:-1",call(fit,"read",JSONObject()).state!!.selection.patternId)
        click("damage-patterns-undo");waitFor { library.available }
        assertEquals(entry.id,EngineRuntime.moduleRahDetails(context,fit).get(30,TimeUnit.SECONDS).modules.single().namedId)
        assertEquals(entry.id,call(fit,"read",JSONObject()).state!!.selection.patternId)
    }
}
