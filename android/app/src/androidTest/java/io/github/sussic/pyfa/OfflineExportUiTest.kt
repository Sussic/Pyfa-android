package io.github.sussic.pyfa

import android.Manifest
import android.content.ClipboardManager
import android.content.pm.PackageManager
import android.net.Uri
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

/** Use disposable durable app data and offline_features_phase=export. No external app is launched. */
@RunWith(AndroidJUnit4::class)
class OfflineExportUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineExportModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun preview() {
        click("eft-export-preview")
        waitFor { !model.loading }
        assertTrue(model.error, model.preview?.ok == true)
    }
    @Test fun reviewedExportIsReadOnlyRetainedAndInvalidatesBeforeAnyOutput() {
        assertEquals("export", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val originalOptions = OfflineExportFiles.loadOptions(context).get(30, TimeUnit.SECONDS)
        val oldNavigation = EngineRuntime.navigation.value
        try {
            assertTrue(OfflineExportFiles.saveOptions(context, OfflineExportOptions()).get(30, TimeUnit.SECONDS))
            val beforeIds = EngineRuntime.library.value.map { it.id }.toSet()
            assertTrue(EngineRuntime.createEmptyFit(context, "Vexor", "Export 探索").get(120, TimeUnit.SECONDS).isSuccess)
            val fitId = EngineRuntime.library.value.single { it.id !in beforeIds }.id
            EngineRuntime.selectFit(context, fitId).get(30, TimeUnit.SECONDS)
            click("eft-export-open"); waitFor { model.optionsLoaded && model.canPreview }
            compose.onNodeWithTag("eft-export-copy").assertIsNotEnabled()
            val fitsBefore = EngineRuntime.library.value
            val featureBefore = EngineRuntime.offlineFeatureState(context, fitId).get(30, TimeUnit.SECONDS)
            val navigationBefore = EngineRuntime.navigation.value
            preview()
            val firstText = checkNotNull(model.preview?.text)
            assertTrue(firstText.startsWith("[Vexor, Export 探索]"))
            compose.onAllNodesWithTag("eft-export-diagnostic").onFirst().assertExists()
            compose.onNodeWithTag("eft-export-save").assertIsEnabled()
            compose.onNodeWithTag("eft-export-share").assertIsEnabled()
            click("eft-export-copy")
            compose.runOnUiThread {
                assertEquals(firstText, context.getSystemService(ClipboardManager::class.java).primaryClip!!.getItemAt(0).text.toString())
            }
            assertEquals(fitsBefore, EngineRuntime.library.value)
            assertEquals(navigationBefore, EngineRuntime.navigation.value)
            assertEquals(featureBefore, EngineRuntime.offlineFeatureState(context, fitId).get(30, TimeUnit.SECONDS))

            val retained = model
            compose.activityRule.scenario.recreate()
            waitFor { model.optionsLoaded }
            assertSame(retained, model); assertEquals(firstText, model.preview?.text)
            compose.onNodeWithTag("eft-export-copy").assertIsEnabled()
            click("eft-export-option-cargo")
            assertNull(model.preview)
            compose.onNodeWithTag("eft-export-copy").assertIsNotEnabled()
            compose.onNodeWithTag("eft-export-save").assertIsNotEnabled()
            compose.onNodeWithTag("eft-export-share").assertIsNotEnabled()
            // Reading preferences on the same I/O worker also waits for the queued commit.
            assertFalse(OfflineExportFiles.loadOptions(context).get(30, TimeUnit.SECONDS).cargo)
            compose.activityRule.scenario.recreate(); waitFor { model.optionsLoaded }
            assertFalse(model.options.cargo)
            preview()

            // A real retained model owns the picker ticket; drive its callback without opening
            // a document provider or sending a fit to another application in this suite.
            compose.runOnUiThread { assertNotNull(model.beginDocument()); assertTrue(model.choosingFile); assertFalse(model.canOutput) }
            compose.activityRule.scenario.recreate()
            assertSame(retained, model); assertTrue(model.choosingFile)
            compose.runOnUiThread { model.documentReturned(context, null) }
            assertTrue(model.message!!.contains("Save cancelled")); assertTrue(model.canOutput)
            compose.runOnUiThread { assertNotNull(model.beginDocument()) }
            val fit = EngineRuntime.library.value.single { it.id == fitId }
            assertTrue(EngineRuntime.request(context, BridgeOperation.RenameFit(fitId, "Export changed"), mapOf(fitId to fit.revision))
                .get(120, TimeUnit.SECONDS).isSuccess)
            waitFor { model.preview == null }
            compose.runOnUiThread { model.documentReturned(context, Uri.parse("content://unused.test/stale")) }
            assertTrue(model.error!!.contains("changed while choosing")); assertFalse(model.savingFile)
            preview()
            compose.runOnUiThread { assertNotNull(model.beginDocument()); model.documentLaunchFailed() }
            assertTrue(model.error!!.contains("picker could not be opened")); assertTrue(model.canOutput)
            compose.runOnUiThread { assertNotNull(model.beginShare()); assertFalse(model.canOutput); model.shareLaunchFailed() }
            assertTrue(model.error!!.contains("Nothing was sent")); assertTrue(model.canOutput)
            compose.runOnUiThread { assertNotNull(model.beginShare()); model.shareReturned() }
            assertTrue(model.message!!.contains("cannot confirm"))

            compose.runOnUiThread {
                model.prepare(context); assertTrue(model.loading); assertFalse(model.canOutput)
                model.cancelPreview(); model.prepare(context)
                assertTrue(model.loading); assertTrue(model.cancelling); assertNull(model.preview)
            }
            waitFor { !model.loading }; assertNull(model.preview)
            compose.onNodeWithTag("eft-export-copy").assertIsNotEnabled()
            preview()
            EngineRuntime.navigate(context) { it.copy(openIds = emptyList(), activeId = null) }.get(30, TimeUnit.SECONDS)
            waitFor { !model.canPreview && model.preview == null }
            compose.onNodeWithTag("eft-export-no-fit").assertExists()
            compose.onNodeWithTag("eft-export-preview").assertIsNotEnabled()
            compose.onNodeWithTag("eft-export-copy").assertIsNotEnabled()
            // A recreated process has no reviewed ticket and must not resolve/open this URI.
            compose.runOnUiThread {
                val restarted = OfflineExportModel()
                assertFalse(restarted.canOutput); assertFalse(restarted.canPreview)
                restarted.documentReturned(context, Uri.parse("content://unused.test/lost-ticket"))
                assertTrue(restarted.error!!.contains("did not survive")); assertFalse(restarted.savingFile)
            }
        } finally {
            OfflineExportFiles.saveOptions(context, originalOptions).get(30, TimeUnit.SECONDS)
            EngineRuntime.navigate(context) { oldNavigation }.get(30, TimeUnit.SECONDS)
        }
    }
}
