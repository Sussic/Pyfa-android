package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.UUID
import java.util.concurrent.TimeUnit
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred disposable-data offline gate. Compile is not execution, visual or ARM64 proof. */
@RunWith(AndroidJUnit4::class)
class OfflineTargetProfilesUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineTargetProfilesModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun prepare() {
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
    }
    private fun call(fitId: String?, selected: String? = null, operation: String = "read", arguments: JSONObject = JSONObject(), offset: Long = 0): OfflineTargetResponse {
        val current = EngineRuntime.offlineFeatureState(context, fitId).get(120, TimeUnit.SECONDS).context
        return EngineRuntime.offlineTargetProfiles(context, OfflineTargetRequest(UUID.randomUUID().toString(), current, fitId,
            OfflineTargetView(offset = offset, selectedTargetId = selected), operation, OfflineFeatureCodec.json(arguments))).get(120, TimeUnit.SECONDS)
            .also { assertTrue(it.error?.message, it.ok) }
    }
    private fun create(name: String): String = EngineRuntime.createEmptyFit(context, "Vexor", name).get(120, TimeUnit.SECONDS)
        .also { assertTrue(it.error?.message, it.isSuccess) }.fits.single().id
    private fun settled() = waitFor { !model.busy && model.state?.context == EngineRuntime.offlineFeatures.value?.context }

    @Test fun sharedTargetsDraftsDetachDeleteUndoAndFreshProcessReopen() {
        prepare()
        val phase = InstrumentationRegistry.getArguments().getString("offline_features_phase")
        val receipt = File(context.noBackupFilesDir, "target-profiles-test.json")
        if (phase == "target_profiles_restart") {
            val saved = JSONObject(receipt.readText()); val first = saved.getString("first"); val second = saved.getString("second"); val target = saved.getString("target")
            for (id in listOf(first, second)) {
                val state = call(id, target).state!!
                assertEquals(target, state.selection.targetId); assertEquals(125.0, state.detail!!.values.fields["hp"])
                assertEquals(0.0, state.detail.values.fields["signatureRadius"]); assertNull(state.detail.values.fields["maxVelocity"])
                assertEquals(0, state.history.undoCount); assertEquals(0, state.history.redoCount)
            }
            return
        }
        assertEquals("target_profiles_prepare", phase)
        val prefix = "Target UI ${System.nanoTime()}"
        val first = create("$prefix first"); val second = create("$prefix second")
        EngineRuntime.selectFit(context, first).get(30, TimeUnit.SECONDS)
        click("targets-open"); settled()
        text("targets-search", "Gamma T4/T5/T6"); settled()
        click("target-select-target:builtin:-149"); settled()
        compose.onNodeWithTag("target-readonly").assertExists()
        assertTrue(model.detail!!.values.fields["explosiveAmount"] is Long)
        click("target-duplicate"); text("target-name", "$prefix shared"); click("target-save"); settled()
        val target = model.detail!!.entry.id
        assertTrue(model.detail!!.values.fields["explosiveAmount"] is Long)
        click("target-edit"); text("target-edit-hp", "125"); text("target-edit-signatureRadius", "0")
        text("target-edit-maxVelocity", ""); text("target-edit-radius", ""); click("target-save"); settled()
        assertEquals(125.0, model.detail!!.values.fields["hp"]); assertEquals(0.0, model.detail!!.values.fields["signatureRadius"])
        click("target-assign"); settled()
        val entry = model.detail!!.entry
        call(second, target, "assign", JSONObject().put("target_id", target).put("revision", entry.revision).put("fit_revision", fit(second).revision))
        settled(); assertEquals(2L, model.detail!!.entry.boundFitCount)
        val revisions = listOf(first, second).associateWith { fit(it).revision }
        click("target-edit"); text("target-edit-emAmount", "100"); click("target-save"); settled()
        assertTrue(revisions.all { (id, revision) -> fit(id).revision > revision })
        click("target-duplicate"); text("target-name", "$prefix copy"); click("target-save"); settled()
        val copied = model.detail!!.entry.id; assertNotEquals(target, copied); assertEquals(125.0, model.detail!!.values.fields["hp"])
        click("target-rename"); text("target-name", "$prefix renamed copy"); click("target-save"); settled()
        click("target-delete"); compose.onNodeWithText("Exactly 0 bound saved fit(s) will switch to No Profile.", substring = true).assertExists()
        click("target-delete-confirm"); settled()
        // Bound target becomes the selected detail again after deleting the independent copy.
        waitFor { model.detail?.entry?.id == target && !model.busy }
        click("target-edit"); text("target-edit-emAmount", "101"); click("targets-back"); click("target-leave-keep")
        click("targets-open"); settled(); compose.activityRule.scenario.recreate(); settled()
        assertEquals("101", model.draft!!.fields[0]); click("target-save")
        compose.onNodeWithTag("targets-error").assertExists(); click("target-cancel")
        val anonymous = TargetProfile(0.0, 0.0, 0.0, 0.0, hp = 0.0, signatureRadius = 0.0)
        val detached = EngineRuntime.request(context, BridgeOperation.SetTargetProfile(first, anonymous), mapOf(first to fit(first).revision)).get(120, TimeUnit.SECONDS)
        assertTrue(detached.error?.message, detached.isSuccess); settled()
        assertEquals("anonymous", model.state!!.selection.kind); assertEquals(target, call(second).state!!.selection.targetId)
        val restored = EngineRuntime.request(context, BridgeOperation.Undo(first), mapOf(first to fit(first).revision)).get(120, TimeUnit.SECONDS)
        assertTrue(restored.error?.message, restored.isSuccess); settled(); assertEquals("named", model.state!!.selection.kind)
        click("target-delete"); compose.onNodeWithText("Exactly 2 bound saved fit(s) will switch to No Profile.", substring = true).assertExists()
        click("target-delete-confirm"); settled()
        assertEquals("none", call(first).state!!.selection.kind); assertEquals("none", call(second).state!!.selection.kind)
        click("targets-undo"); settled()
        assertEquals(target, call(first, target).state!!.selection.targetId); assertEquals(target, call(second, target).state!!.selection.targetId)
        receipt.writeText(JSONObject().put("first", first).put("second", second).put("target", target).toString())
    }

    @Test fun libraryWithoutOpenFitReachesEveryBuiltinAndCanCreateCancelDelete() {
        prepare(); assertEquals("target_profiles_library", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        EngineRuntime.navigate(context) { it.copy(openIds = emptyList(), activeId = null) }.get(30, TimeUnit.SECONDS)
        click("targets-open"); settled(); assertEquals("no_fit", model.state!!.selection.kind)
        val ids = mutableSetOf<String>(); var offset = 0L
        do {
            val page = call(null, offset = offset).state!!; ids.addAll(page.entries.filter { it.readonly }.map { it.id })
            offset += 50
        } while (offset < page.total)
        assertEquals((-195..-1).map { "target:builtin:$it" }.toSet(), ids)
        click("target-create"); text("target-name", "Cancelled target ${System.nanoTime()}"); text("target-edit-hp", "0")
        click("target-cancel"); assertFalse(model.dirty)
        click("target-create"); text("target-name", "Library target ${System.nanoTime()}"); text("target-edit-hp", "0")
        click("target-save"); settled(); assertEquals(0.0, model.detail!!.values.fields["hp"])
        click("target-delete"); click("target-delete-confirm"); settled(); assertNull(model.detail)
        assertEquals("no_fit", model.state!!.selection.kind)
    }
}
