package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.os.Process
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import io.github.sussic.pyfa.ModuleTestJson.array
import io.github.sussic.pyfa.ModuleTestJson.compare
import io.github.sussic.pyfa.ModuleTestJson.obj
import io.github.sussic.pyfa.ModuleTestJson.typed

@RunWith(AndroidJUnit4::class)
@OptIn(ExperimentalTestApi::class)
class EditHistoryTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[EditHistoryModel::class.java]
    private val picker get() = ViewModelProvider(compose.activity)[BulkChargeEditorModel::class.java]
    private fun fits() = EngineRuntime.library.value
    private fun fit(id: String) = fits().single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun waitFor(predicate: () -> Boolean) { compose.waitUntil(90_000, predicate); sync() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick(); sync() }
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList()) =
        EngineRuntime.request(context,operation,ids.associateWith { fit(it).revision }).get(180,TimeUnit.SECONDS).also {
            assertTrue(it.error?.message,it.isSuccess)
        }
    private fun library() = typed(array(fits().map(ModuleTestJson::fit)))
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(180,TimeUnit.SECONDS))
    private fun history(id: String) = EngineRuntime.editHistory(context,id).get(120,TimeUnit.SECONDS)
    private fun counts(id: String) = history(id).let { obj("undo_count" to it.undoCount,"redo_count" to it.redoCount,
        "can_undo" to (it.undoCount>0),"can_redo" to (it.redoCount>0)) }
    private fun ready(id: String) {
        waitFor { !model.loading && !model.editing && model.options?.fitId==id && model.options?.revision==fit(id).revision }
    }
    private fun select(id: String) { EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS);ready(id) }
    private fun reverse(id: String, redo: Boolean) {
        ready(id);val revision=fit(id).revision
        click(if(redo) "history-redo" else "history-undo")
        waitFor { fit(id).revision>revision && !model.loading && !model.editing && model.options?.revision==fit(id).revision }
        assertNull(model.error)
    }
    private fun screenshot(name: String, tag: String="history-undo") {
        compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed();sync()
        val automation=InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500,10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b091-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors=InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b091-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(value.toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
    private fun create(spec: JSONObject): String {
        val copied=JSONObject(spec.toString());copied.remove("ignore_restrictions")
        val modules=copied.getJSONArray("modules")
        copied.put("modules",array((0 until modules.length()).map(modules::getJSONObject).filter { !it.has("empty_slot") }))
        val id=send(BridgeOperation.CreateFit(BridgeCodec.decodeFitSpec(copied))).fits.single().id
        // Reproduce original pane's initial fill; no-op padding must not create history.
        send(BridgeOperation.SetFitRestrictions(id,false),listOf(id))
        assertEquals(0,history(id).undoCount)
        return id
    }
    private fun operation(id: String, row: JSONObject): BridgeOperation {
        val a=row.getJSONObject("arguments")
        fun indices()=a.getJSONArray("module_indices").let { (0 until it.length()).map(it::getInt) }
        return when(row.getString("operation")) {
            "set_module_charge" -> BridgeOperation.SetModuleCharge(id,a.getInt("position"),a.getInt("charge_id"))
            "set_bulk_charges" -> BridgeOperation.SetBulkCharges(id,a.getInt("main_position"),indices(),BulkScope.valueOf(a.getString("scope")),a.getInt("charge_id"))
            "set_charges" -> BridgeOperation.SetCharges(id,indices(),a.getString("charge"))
            "set_bulk_states" -> BridgeOperation.SetBulkStates(id,a.getInt("main_position"),indices(),BulkScope.valueOf(a.getString("scope")),StateClick.entries.single { it.wire==a.getString("click") })
            "set_module_states" -> BridgeOperation.SetModuleStates(id,indices(),ModuleState.valueOf(a.getString("state")))
            "add_module" -> BridgeOperation.AddModule(id,a.getInt("item_id"))
            "replace_module" -> BridgeOperation.ReplaceModule(id,a.getInt("position"),a.getInt("item_id"))
            "remove_module" -> BridgeOperation.RemoveModule(id,a.getInt("position"))
            "remove_bulk_modules" -> BridgeOperation.RemoveBulkModules(id,a.getInt("main_position"),indices(),BulkScope.valueOf(a.getString("scope")))
            "change_variation" -> BridgeOperation.ChangeVariation(id,VariationContext.MODULE,a.getInt("position"),a.getInt("item_id"))
            "change_bulk_variations" -> BridgeOperation.ChangeBulkVariations(id,a.getInt("main_position"),indices(),BulkScope.valueOf(a.getString("scope")),a.getInt("item_id"))
            "swap_modules" -> BridgeOperation.SwapModules(id,a.getInt("from_position"),a.getInt("to_position"))
            "fill_modules_item" -> BridgeOperation.FillModulesItem(id,a.getInt("item_id"))
            "fill_modules_clone" -> BridgeOperation.FillModulesClone(id,a.getInt("position"))
            "clone_selected_modules" -> BridgeOperation.CloneSelectedModules(id,indices())
            "clone_module_at" -> BridgeOperation.CloneModuleAt(id,a.getInt("source_position"),a.getInt("destination_position"))
            "set_fit_restrictions" -> BridgeOperation.SetFitRestrictions(id,a.getBoolean("ignore"))
            else -> error("Unknown history fixture operation")
        }
    }
    private fun observation(id: String, recipients: List<String>): JSONObject = obj(
        "stats" to ModuleTestJson.stats(fit(id)),
        "modules" to array(fit(id).modules.filter { it.emptySlot==null }.map { obj("index" to it.index,"name" to it.name,"state" to it.state!!.name,"charge" to it.charge) }),
        "ignore_restrictions" to EngineRuntime.fittingDetails(context,id).get(120,TimeUnit.SECONDS).ignoreRestrictions,
        "history" to counts(id),"recent" to array(EngineRuntime.recent.value),
        "recipients" to array(recipients.map { ModuleTestJson.stats(fit(it)) }))
    private fun compareState(expected: JSONObject, observed: JSONObject, recent: List<Int>) {
        val adjusted=JSONObject(expected.toString())
        val top=adjusted.getJSONArray("recent").let { (0 until it.length()).map(it::getInt) }
        adjusted.put("recent",array((top+recent.filter { it !in top }).take(20)))
        fun absentStats(left: JSONObject,right: JSONObject) {
            for(key in listOf("gun_optimal","gun_falloff")) if(right.getJSONObject(key).isNull("value")) {
                assertTrue(left.getJSONObject(key).getDouble("value") in listOf(0.0,1.0))
                left.getJSONObject(key).put("value",JSONObject.NULL)
            }
        }
        absentStats(adjusted.getJSONObject("stats"),observed.getJSONObject("stats"))
        val targets=adjusted.getJSONArray("recipients")
        for(i in 0 until targets.length()) absentStats(targets.getJSONObject(i),observed.getJSONArray("recipients").getJSONObject(i))
        compare(adjusted,observed,strict=false)
    }
    private fun guards(id: String): JSONArray {
        val good=history(id).let { obj("version" to 1,"fit_id" to id,"revision" to it.revision,"limit" to it.limit,
            "undo_count" to it.undoCount,"redo_count" to it.redoCount,"undo_label" to it.undoLabel,"redo_label" to it.redoLabel) }
        val names=listOf("version","extra","boolean_count","decimal_count","negative_count","overflow","limit","revision","missing_label","unexpected_label")
        for(name in names) {
            val bad=JSONObject(good.toString())
            when(name) {
                "version" -> bad.put("version",2)
                "extra" -> bad.put("extra",1)
                "boolean_count" -> bad.put("undo_count",true)
                "negative_count" -> bad.put("undo_count",-1)
                "overflow" -> {bad.put("undo_count",100);bad.put("redo_count",1)}
                "limit" -> bad.put("limit",101)
                "revision" -> bad.put("revision",0)
                "missing_label" -> {bad.put("undo_count",1);bad.put("undo_label",JSONObject.NULL)}
                "unexpected_label" -> {bad.put("undo_count",0);bad.put("undo_label","Unexpected")}
            }
            val raw=if(name=="decimal_count") bad.toString().replaceFirst(Regex("\"undo_count\":(\\d+)"),"\"undo_count\":$1.0") else bad.toString()
            try { BridgeCodec.decodeEditHistory(raw);fail("Accepted $name") } catch(_:BridgeProtocolException) { }
        }
        return array(names)
    }

    @Test fun moduleHistoryReversesUserActionsOffline() {
        val phase=InstrumentationRegistry.getArguments().getString("b091_phase") ?: error("Missing phase")
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(180,TimeUnit.SECONDS)
        val fixture=JSONObject(InstrumentationRegistry.getInstrumentation().context.assets.open("history-expected.json").bufferedReader().use { it.readText() })
        val before=library();val runtimeStart=diagnostics();val recentBefore=array(EngineRuntime.recent.value)
        assertEquals(if(phase=="prepare") 90 else 111,fits().size)
        val file=File(context.noBackupFilesDir,"b091-test-expected.json")
        val cases=JSONArray();val checks=JSONArray();var protocol=JSONArray();val observations=JSONObject()
        var ids=JSONArray()
        try {
            if(phase=="prepare") {
                val rows=fixture.getJSONArray("cases")
                val caseIds=mutableListOf<String>()
                for(index in 0 until rows.length()) {
                    val row=rows.getJSONObject(index);val id=create(row.getJSONObject("spec"));ids.put(id);caseIds.add(id)
                    val recipients=mutableListOf<String>()
                    row.optJSONArray("recipients")?.let { targets -> for(i in 0 until targets.length()) {
                        val target=create(targets.getJSONObject(i));ids.put(target);recipients.add(target)
                        send(BridgeOperation.AddProjection(id,target,0.0,true,1),listOf(id,target))
                    } }
                    select(id)
                    val recent=EngineRuntime.recent.value.toList();val states=JSONArray();val expected=row.getJSONArray("steps")
                    for(i in 0 until expected.length()) {
                        val step=expected.getJSONObject(i);val action=step.getString("action")
                        when(action) { "do" -> send(operation(id,row),listOf(id));"undo" -> reverse(id,false);"redo" -> reverse(id,true) }
                        val actual=observation(id,recipients);compareState(step.getJSONObject("result"),actual,recent)
                        states.put(obj("action" to action,"result" to typed(actual)))
                    }
                    cases.put(obj("name" to row.getString("name"),"fit_id" to id,"recipients" to array(recipients),"recent_before" to array(recent),"steps" to states))
                }
                checks.put("complete_original_matrix").put("touch_repeated_undo_redo").put("linked_recipients")
                val first=caseIds[0];select(first)
                send(BridgeOperation.SetNotes(first,"History preserves notes — 保持"),listOf(first));ready(first)
                click("modules-open");click("modules-bulk")
                waitFor { !picker.loading && picker.options?.fitId==first }
                click("bulk-select-0");click("bulk-select-1");assertEquals(setOf(0,1),picker.selected)
                reverse(first,false)
                waitFor { !picker.loading && picker.options?.revision==fit(first).revision }
                assertTrue(picker.selected.isEmpty());observations.put("selection_after_undo",array(picker.selected.toList()))
                observations.put("undone",typed(observation(first,emptyList())))
                assertEquals("History preserves notes — 保持",EngineRuntime.noteDetails(context,first).get(30,TimeUnit.SECONDS).text)
                screenshot("bulk-undone");reverse(first,true);screenshot("bulk-redone")
                click("bulk-back");click("modules-back")
                select(caseIds[1]);observations.put("other_history",counts(caseIds[1]));screenshot("fit-isolation")
                select(first);reverse(first,false)
                send(BridgeOperation.SetCharges(first,listOf(0),"Antimatter Charge M"),listOf(first));ready(first)
                assertEquals(0,history(first).redoCount);observations.put("branched",counts(first))
                compose.activityRule.scenario.recreate();ready(first)
                assertEquals(1,history(first).undoCount);screenshot("retained-history")
                compose.runOnUiThread { model.options=model.options!!.copy(revision=0);model.apply(context,false) }
                waitFor { !model.editing && model.error!=null }
                observations.put("stale",counts(first));screenshot("stale-action","history-error")
                click("history-retry");ready(first);reverse(first,false)
                val copy=send(BridgeOperation.DuplicateFit(first,"B09 history copy – Δ"),listOf(first)).fits.single { it.name=="B09 history copy – Δ" }.id
                ids.put(copy);assertEquals(0,history(copy).undoCount)
                checks.put("selection_safety").put("notes_preserved").put("fit_isolation").put("redo_branch_invalidated")
                    .put("history_recreation").put("stale_rejected").put("copy_has_no_history")
                protocol=guards(first);checks.put("typed_history_protocol")
                select(first);EngineRuntime.navigate(context) { it.copy(restore=true) }.get(30,TimeUnit.SECONDS)
                file.writeText(obj("fits" to library(),"prior" to before,"new_ids" to ids,"active_id" to first,
                    "recent" to array(EngineRuntime.recent.value),"notes" to EngineRuntime.noteDetails(context,first).get(30,TimeUnit.SECONDS).text,
                    "history_before_restart" to counts(first)).toString(),Charsets.UTF_8)
            } else {
                assertEquals("restored",phase)
                val expected=JSONObject(file.readText(Charsets.UTF_8));ids=expected.getJSONArray("new_ids")
                compare(expected.getJSONObject("fits"),library(),strict=false)
                val active=expected.getString("active_id")
                assertEquals(active,(EngineRuntime.state.value as EngineState.Ready).fit.id)
                assertEquals(expected.getString("notes"),EngineRuntime.noteDetails(context,active).get(30,TimeUnit.SECONDS).text)
                for(index in 0 until ids.length()) {
                    val id=ids.getString(index);select(id)
                    compare(obj("undo_count" to 0,"redo_count" to 0,"can_undo" to false,"can_redo" to false),counts(id))
                    compose.onNodeWithTag("history-undo").assertIsNotEnabled();compose.onNodeWithTag("history-redo").assertIsNotEnabled()
                }
                select(active);screenshot("restored-empty-history")
                checks.put("fresh_process_restore").put("reopen_each_fit").put("session_history_empty").put("notes_retained")
            }
            val histories=JSONObject()
            for(index in 0 until ids.length()) histories.put(ids.getString(index),counts(ids.getString(index)))
            retain(obj("task" to "B09.1","phase" to phase,"pid" to Process.myPid(),"runtime_start" to runtimeStart,
                "runtime_end" to diagnostics(),"before" to before,"after" to library(),"new_ids" to ids,"cases" to cases,
                "checks" to checks,"protocol_rejections" to protocol,"observations" to observations,"histories" to histories,
                "recent_before" to recentBefore,"recent_after" to array(EngineRuntime.recent.value),
                "saved" to JSONObject(file.readText(Charsets.UTF_8))),phase)
        } catch(failure:Throwable) {
            val automation=InstrumentationRegistry.getInstrumentation().uiAutomation
            ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand("screencap -p /sdcard/Download/pyfa-b091-failure.png")).use { it.readBytes() }
            throw failure
        }
    }
}
