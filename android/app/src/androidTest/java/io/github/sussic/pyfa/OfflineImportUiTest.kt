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
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Dedicated durable app data; prepare then force-stop/restart with offline_features_phase=restart. */
@RunWith(AndroidJUnit4::class)
class OfflineImportUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineImportModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun fitIds() = EngineRuntime.library.value.map { it.id }.toSet()
    @Test fun atomicPreviewConfirmationUndoAndDurableSameIdRecovery() {
        val phase = InstrumentationRegistry.getArguments().getString("offline_features_phase") ?: error("Explicit durable phase required")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val receipt = File(context.noBackupFilesDir, "offline-import-test.json")
        click("eft-open")
        waitFor { model.libraryHistory != null }
        if (phase == "restart") {
            val saved = JSONObject(receipt.readText()); val expected = saved.getJSONArray("fit_ids").let { a -> (0 until a.length()).map(a::getString) }
            val original = checkNotNull(EngineRuntime.pendingImport.value)
            val before = fitIds()
            compose.onNodeWithTag("eft-pending").assertExists()
            click("eft-retry"); waitFor { !model.busy && model.result?.ok == true }
            assertTrue(model.result!!.replayed); assertEquals(expected, model.result!!.fitIds)
            assertEquals(before, fitIds()); assertNull(EngineRuntime.pendingImport.value)
            // Later removal must not be reversed by retrying the original receipt.
            val victim = expected.first(); val fit = EngineRuntime.library.value.single { it.id == victim }
            assertTrue(EngineRuntime.request(context, BridgeOperation.DeleteFit(victim, true), mapOf(victim to fit.revision)).get(120, TimeUnit.SECONDS).isSuccess)
            val afterDeletion = fitIds()
            val replay = EngineRuntime.offlineImportExecute(context, original).get(120, TimeUnit.SECONDS)
            assertTrue(replay.ok && replay.replayed); assertEquals(listOf(victim), replay.missingFitIds)
            assertEquals(afterDeletion, fitIds())
            return
        }
        assertEquals("prepare", phase)
        val before = fitIds()
        compose.onNodeWithTag("eft-text-0").performTextReplacement("[Vexor, EFT first]\r\n")
        click("eft-add")
        compose.onNodeWithTag("eft-text-1").performTextReplacement("[Unknown invented hull, Invalid]\n")
        click("eft-preview"); waitFor { !model.busy && model.preview != null }
        assertFalse(model.preview!!.ok); assertTrue(model.preview!!.diagnostics.isNotEmpty()); assertEquals(before, fitIds())
        compose.onNodeWithTag("eft-text-1").performTextReplacement("[Vexor, EFT second]\n")
        click("eft-preview"); waitFor { !model.busy && model.preview?.ok == true }
        assertEquals(before, fitIds())
        val exact = model.preview!!.exactRequest!!
        click("eft-confirm-open"); compose.onNodeWithTag("eft-confirm").performClick()
        waitFor { !model.busy && model.result?.ok == true }
        val ids = model.result!!.fitIds
        assertEquals(2, ids.size); assertEquals(before + ids.toSet(), fitIds()); assertNull(EngineRuntime.pendingImport.value)
        waitFor { model.libraryHistory?.history?.undoLabel == "Import EFT fits" }
        click("eft-history-undo"); waitFor { !model.busy && fitIds() == before }
        click("eft-history-redo"); waitFor { !model.busy && fitIds() == before + ids.toSet() }
        // Recreate an acknowledgement-loss boundary with the real durable recovery store.
        // The next fresh process must read and retry these exact already-committed bytes.
        OfflineImportStore(File(context.noBackupFilesDir, "fits/pending-eft-import.json")).save(exact)
        receipt.writeText(JSONObject().put("fit_ids", JSONArray(ids)).toString())
    }
}
