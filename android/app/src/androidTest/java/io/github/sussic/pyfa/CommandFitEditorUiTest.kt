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
import kotlin.math.abs
import kotlin.math.max
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred device phase command_fits; disposable durable data, existing unmodified A05 fixture. */
@RunWith(AndroidJUnit4::class)
class CommandFitEditorUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[CommandFitModel::class.java]
    private val reference by lazy { instrumentation.context.assets.open("command-expected.json").bufferedReader().use { JSONObject(it.readText()) } }
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000,test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun search(text: String) { compose.onNodeWithTag("commands-search").performScrollTo().performTextReplacement(text) }
    private fun prepare() {
        assertEquals("command_fits",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
    }
    private fun send(op: BridgeOperation,vararg ids: String): BridgeResponse {
        val result=EngineRuntime.request(context,op,ids.toSet().associateWith { fit(it).revision }).get(120,TimeUnit.SECONDS)
        assertTrue(result.error?.message,result.isSuccess); return result
    }
    private fun create(role: String): String {
        val spec=BridgeCodec.decodeFitSpec(reference.getJSONObject("inputs").getJSONObject(role)).copy(name="Native command $role ${System.nanoTime()}")
        return send(BridgeOperation.CreateFit(spec)).fits.single().id
    }
    private fun empty(): String = send(BridgeOperation.CreateFit(FitSpec("No burst ${System.nanoTime()}","Rifter",5,false,
        DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),emptyList(),emptyList()))).fits.single().id
    private fun changed(id: String, action: () -> Unit) {
        val revision=fit(id).revision; action(); waitFor { !model.busy && fit(id).revision>revision }
    }
    private fun history(id: String,redo: Boolean) {
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision==fit(id).revision }
        changed(id) { click(if (redo) "history-redo" else "history-undo") }
    }
    private fun assertReference(id: String,stage: String,role: String="target") {
        val expected=reference.getJSONObject("states").getJSONObject(stage).getJSONObject(role)
        assertEquals(39,expected.length())
        val tolerance=reference.getJSONObject("comparison_tolerance")
        for (key in expected.keys()) {
            val value=expected.getJSONObject(key); val actual=fit(id).stats.getValue(key)
            assertEquals("$stage.$role.$key unit",value.getString("unit"),actual.unit)
            when (val number=value.get("value")) {
                is Boolean -> assertEquals("$stage.$role.$key",number,actual.value.raw)
                is Number -> assertEquals("$stage.$role.$key",number.toDouble(),actual.value.numberOrNull()!!,
                    max(tolerance.getDouble("absolute"),abs(number.toDouble())*tolerance.getDouble("relative")))
                else -> fail("Unexpected reference scalar")
            }
        }
    }
    private fun feature(source: String,op: String,args: JSONObject): OfflineFeatureState {
        val state=EngineRuntime.offlineFeatureState(context,source).get(30,TimeUnit.SECONDS)
        val result=EngineRuntime.offlineFeatureRequest(context,state.context,op,args,source).get(120,TimeUnit.SECONDS)
        assertTrue(result.error?.message,result.ok); return result.state!!
    }
    @Test fun loadedBurstControlsMatchA05AndSourceEditsRefreshTwoRecipientsAcrossReturnAndRecreation() {
        prepare()
        val source=create("source"); val first=create("target"); val second=create("target")
        assertReference(source,"initial","source"); assertReference(first,"initial"); assertReference(second,"initial")
        EngineRuntime.selectFit(context,first).get(30,TimeUnit.SECONDS)
        click("commands-open"); compose.onNodeWithTag("commands-empty").assertExists(); search(fit(source).name)
        val recent=EngineRuntime.recent.value.toList()
        changed(first) { click("command-$source-add") }
        assertReference(first,"applied"); assertReference(source,"applied","source")
        compose.onNodeWithTag("command-$source-add").assertIsNotEnabled().assertTextContains("Already linked",substring=true)
        val noOpFit=fit(first); val noOpHistory=EngineRuntime.editHistory(context,first).get(30,TimeUnit.SECONDS)
        compose.runOnUiThread { model.add(context,model.anchor(fit(first),fit(source))) }
        assertEquals(noOpFit,fit(first)); assertEquals(noOpHistory,EngineRuntime.editHistory(context,first).get(30,TimeUnit.SECONDS))
        history(first,false); assertReference(first,"initial"); assertTrue(fit(first).commands.isEmpty())
        history(first,true); assertReference(first,"applied")
        changed(first) { click("command-$source-active") }; assertReference(first,"link_inactive")
        changed(first) { click("command-$source-active") }; assertReference(first,"applied")
        changed(first) { click("command-$source-remove") }; assertReference(first,"removed")
        history(first,false); assertReference(first,"applied")
        assertEquals(recent,EngineRuntime.recent.value)
        send(BridgeOperation.AddCommandFit(source,second),source,second)
        assertReference(second,"applied"); assertReference(first,"applied")
        click("command-$source-open"); waitFor { !model.busy && (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id==source }
        val retained=model; compose.activityRule.scenario.recreate(); compose.waitForIdle()
        assertSame(retained,model); assertEquals(first,model.returnRecipientId)
        click("modules-open")
        // Source-only copied profile changes affect both recipients without modifying their profiles.
        var state=EngineRuntime.offlineFeatureState(context,source).get(30,TimeUnit.SECONDS)
        val sourceProfile=state.bindings.getValue(source).profileId
        val name="Command skill proof ${System.nanoTime()}"
        state=feature(source,"create_profile",JSONObject().put("source",sourceProfile).put("name",name))
        val profile=state.profiles.single { it.name==name }.id
        state=feature(source,"assign_profile",JSONObject().put("fit_id",source).put("profile_id",profile))
        val skill=state.skills.single { it.name=="Shield Command Specialist" }.id
        feature(source,"set_profile_skill",JSONObject().put("profile_id",profile).put("revision",state.profiles.single { it.id==profile }.revision).put("skill_id",skill).put("level",4))
        assertReference(second,"specialist_4"); assertReference(first,"specialist_4"); assertReference(source,"specialist_4","source")
        state=EngineRuntime.offlineFeatureState(context,source).get(30,TimeUnit.SECONDS)
        feature(source,"set_profile_skill",JSONObject().put("profile_id",profile).put("revision",state.profiles.single { it.id==profile }.revision).put("skill_id",skill).put("level",5))
        assertReference(first,"applied"); assertReference(second,"applied")
        val catalog=EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS)
        send(BridgeOperation.FitImplant(source,catalog.items.single { it.name=="Shield Command Mindlink" }.id),source)
        assertReference(first,"mindlink_added"); assertReference(second,"mindlink_added"); assertReference(source,"mindlink_added","source")
        send(BridgeOperation.SetImplantActive(source,10,false),source)
        assertReference(second,"mindlink_inactive"); assertReference(first,"mindlink_inactive")
        send(BridgeOperation.SetImplantActive(source,10,true),source)
        val burst=fit(source).modules.single { it.name=="Shield Command Burst II" }.index
        send(BridgeOperation.SetModuleCharge(source,burst,catalog.items.single { it.name=="Shield Harmonizing Charge" }.id),source)
        assertReference(second,"harmonizing"); assertReference(first,"harmonizing"); assertReference(source,"harmonizing","source")
        click("commands-return"); waitFor { !model.busy && (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id==first }
        compose.onNodeWithTag("commands-recipient").assertExists()
        click("commands-back"); compose.onNodeWithTag("commands-open").assertExists()
        // Public reads in reverse recipient/source order must not contaminate later snapshots.
        val before=listOf(fit(source),fit(first),fit(second))
        for (id in listOf(second,source,first)) EngineRuntime.capacitorDetails(context,id).get(30,TimeUnit.SECONDS)
        send(BridgeOperation.Snapshot(listOf(first,source,second)))
        assertEquals(before,listOf(fit(source),fit(first),fit(second)))
    }
    @Test fun emptyAndSelfLinksHaveNoExtraEffectAndStaleDeletedOrPendingActionsCannotMisapply() {
        prepare()
        val source=empty(); val target=empty()
        EngineRuntime.selectFit(context,target).get(30,TimeUnit.SECONDS)
        click("commands-open"); search(fit(source).name)
        val baseline=fit(target).stats
        changed(target) { click("command-$source-add") }; assertEquals(baseline,fit(target).stats)
        search(fit(target).name); changed(target) { click("command-$target-add") }
        assertEquals(baseline,fit(target).stats)
        compose.onNodeWithTag("commands-effect-explanation").assertTextContains("self link adds no extra",substring=true)
        val stale=model.anchor(fit(target),fit(source))
        send(BridgeOperation.RenameFit(source,"Changed command source ${System.nanoTime()}"),source)
        val current=fit(target)
        compose.runOnUiThread { model.setActive(context,stale,false); model.remove(context,stale); model.add(context,stale) }
        assertEquals(current,fit(target))
        click("command-$source-open"); waitFor { !model.busy && (EngineRuntime.state.value as? EngineState.Ready)?.fit?.id==source }
        send(BridgeOperation.DeleteFit(target,true),target)
        compose.onNodeWithTag("commands-return-missing").assertExists(); compose.onNodeWithTag("commands-return").assertIsNotEnabled()
        click("commands-return-dismiss"); assertNull(model.returnRecipientId)
        val replacement=empty(); EngineRuntime.selectFit(context,replacement).get(30,TimeUnit.SECONDS)
        var calls=0
        lateinit var pending: CompletableFuture<BridgeResponse>
        val controlled=CommandFitModel { _,_,_ -> calls++; pending }
        val before=controlled.anchor(fit(replacement),fit(source))
        pending=CompletableFuture()
        compose.runOnUiThread { controlled.add(context,before); controlled.add(context,before) }
        assertEquals(1,calls); assertTrue(controlled.busy)
        EngineRuntime.selectFit(context,source).get(30,TimeUnit.SECONDS)
        pending.complete(BridgeResponse("request","session",BridgeStatus.ERROR,emptyList(),BridgeError(BridgeErrorCode.REVISION_CONFLICT,"Changed")))
        waitFor { !controlled.busy }; assertNull(controlled.error); assertNull(controlled.message)
        compose.runOnUiThread { controlled.add(context,before) }; assertEquals(1,calls)
        EngineRuntime.selectFit(context,replacement).get(30,TimeUnit.SECONDS)
        pending=CompletableFuture()
        compose.runOnUiThread { controlled.add(context,controlled.anchor(fit(replacement),fit(source))) }
        pending.complete(BridgeResponse("request","session",BridgeStatus.ERROR,emptyList(),BridgeError(BridgeErrorCode.INVALID_EDIT,"Command refused.")))
        waitFor { !controlled.busy }; assertEquals("Command refused.",controlled.error)
        send(BridgeOperation.DeleteFit(source,true),source)
        compose.runOnUiThread { controlled.add(context,before) }; assertEquals(2,calls)
        assertTrue(fit(replacement).commands.isEmpty())
    }
}
