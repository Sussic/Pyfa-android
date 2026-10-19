package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.ParcelFileDescriptor
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.concurrent.TimeUnit
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Authored touch coverage. Run each method in its own instrumentation process. */
@RunWith(AndroidJUnit4::class)
class DroneUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private val model get() = ViewModelProvider(compose.activity)[DroneEditorModel::class.java]
    private fun click(tag: String) {
        compose.waitUntil(60_000) {
            compose.onAllNodesWithTag(tag).fetchSemanticsNodes().singleOrNull()?.let {
                !it.config.contains(SemanticsProperties.Disabled)
            } == true
        }
        compose.onNodeWithTag(tag).performScrollTo().performClick(); compose.waitForIdle()
    }
    private fun ready(id: String, count: Int? = null) {
        compose.waitUntil(60_000) {
            val fit = EngineRuntime.library.value.find { it.id == id }
            !model.loading && !model.editing && model.error == null && model.details?.fitId == id &&
                model.details?.revision == fit?.revision && (count == null || model.details?.stacks?.size == count)
        }
        compose.waitForIdle()
    }
    private fun reverse(id: String, count: Int, redo: Boolean = false) {
        ready(id)
        val revision = EngineRuntime.library.value.single { it.id == id }.revision
        val history = ViewModelProvider(compose.activity)[EditHistoryModel::class.java]
        compose.waitUntil(60_000) {
            !history.loading && !history.editing && history.options?.fitId == id &&
                history.options?.revision == revision
        }
        click(if (redo) "history-redo" else "history-undo")
        // History uses its own worker request. The unchanged one-stack view can
        // satisfy ready() before undo publishes a new library revision.
        compose.waitUntil(60_000) {
            EngineRuntime.library.value.single { it.id == id }.revision == revision + 1 &&
                !history.loading && !history.editing && history.options?.fitId == id &&
                history.options?.revision == revision + 1
        }
        assertNull(history.error)
        ready(id, count)
    }
    private fun offline() {
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
    }
    private fun screenshot(name: String) {
        compose.waitForIdle(); instrumentation.uiAutomation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(instrumentation.uiAutomation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-c04-$name.png")).use { it.readBytes() }
    }
    @Test fun cargoBrowseReturnsToDronesAndEditsSurviveRecreation() {
        offline()
        val result = EngineRuntime.request(context, BridgeOperation.CreateFit(FitSpec("C04 touch synthetic", "Vexor", 5,
            false, DamagePattern(25.0, 25.0, 25.0, 25.0), Security(SystemSecurity.HISEC, 0.0), emptyList(), emptyList())))
            .get(120, TimeUnit.SECONDS)
        assertTrue(result.isSuccess)
        val id = result.fits.single().id
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        compose.waitForIdle(); click("cargo-open"); click("cargo-browse")
        val equipment = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
        compose.waitUntil(60_000) { equipment.catalog != null && !equipment.busy }
        compose.onNodeWithTag("equipment-search").performTextReplacement("Hobgoblin I")
        click("equipment-search-submit")
        compose.waitUntil(60_000) { !equipment.busy && equipment.searched == "Hobgoblin I" }
        click("equipment-item-2454"); click("equipment-add-drone"); ready(id, 1)
        compose.onNodeWithTag("drones-bay").assertExists()
        compose.onNodeWithTag("cargo-browse").assertDoesNotExist()
        val firstKey = model.details!!.stacks.single().objectKey
        click("drones-browse")
        compose.waitUntil(60_000) { equipment.catalog != null && !equipment.busy }
        click("equipment-add-drone-stack"); ready(id, 2)
        assertEquals(5, model.details!!.stacks.last().amount)
        reverse(id, 1)
        assertEquals(firstKey, model.details!!.stacks.single().objectKey)
        click("drone-0-variations")
        val variation = ViewModelProvider(compose.activity)[VariationEditorModel::class.java]
        compose.waitUntil(60_000) { !variation.loading && variation.options?.fitId == id }
        click("variation-item-2456"); click("variation-apply")
        compose.waitUntil(60_000) { !variation.loading && !variation.editing && variation.error == null &&
            variation.options?.revision == EngineRuntime.library.value.single { it.id == id }.revision }
        if (variation.position != null) click("variations-top-back")
        click("variations-top-back"); ready(id, 1)
        assertEquals(2456, model.details!!.stacks.single().itemId)
        assertEquals(1, model.details!!.stacks.single().amount)
        screenshot("ordinary-variation")
        reverse(id, 1)
        assertEquals(firstKey, model.details!!.stacks.single().objectKey)
        compose.onNodeWithTag("drone-0-amount").performScrollTo().performTextReplacement("5")
        click("drone-0-save"); ready(id, 1)
        click("drone-0-toggle"); ready(id, 1)
        val conservedBefore=model.details!!.stacks.single()
        compose.onNodeWithTag("drone-0-split-amount").performScrollTo().performTextReplacement("2")
        click("drone-0-split"); ready(id, 2)
        assertEquals(listOf(3,2),model.details!!.stacks.map { it.amount })
        assertEquals(5L,model.details!!.active)
        assertEquals(firstKey,model.details!!.stacks.first().objectKey)
        click("drone-0-select"); click("drone-1-select"); click("drones-merge-selected"); ready(id, 1)
        assertEquals(conservedBefore,model.details!!.stacks.single())
        screenshot("conserved-split-merge")
        reverse(id, 2)
        reverse(id, 1)
        assertEquals(conservedBefore,model.details!!.stacks.single())
        click("drones-clear-selection"); click("drone-0-toggle"); ready(id, 1)
        click("drone-0-clone"); ready(id, 2)
        assertEquals(firstKey, model.details!!.stacks.first().objectKey)
        assertNotEquals(firstKey, model.details!!.stacks.last().objectKey)
        compose.onNodeWithTag("drone-0-amount").performScrollTo().performTextReplacement("100")
        click("drone-0-save"); ready(id, 2)
        assertEquals(100, model.details!!.stacks[0].amount)
        compose.onNodeWithTag("drones-over-limit").assertExists()
        click("drone-0-select"); click("drone-1-select")
        val keys = model.selected
        val before = model.details
        compose.activityRule.scenario.recreate(); ready(id, 2)
        assertEquals(keys, model.selected); assertEquals(before, model.details)
        screenshot("selected-over-limit")
        click("drones-toggle-selected"); ready(id, 2)
        val activated = model.details!!.stacks
        assertTrue(activated.all { it.active == it.amount })
        click("drones-remove-selected"); ready(id, 0)
        compose.onNodeWithTag("drones-empty").assertExists()
        reverse(id, 2)
        assertEquals(activated, model.details!!.stacks)
        reverse(id, 0, redo = true)
        screenshot("empty-after-redo")
        File(context.noBackupFilesDir, "c04-ui-receipt.json").writeText(JSONObject()
            .put("fit_id", id).put("cargo_return", true).put("recreation_identity", true)
            .put("bulk_toggle_remove_history", true).toString(2))
    }

    @Test fun restoredMutationsShowDetailsAndRetainSeparateIdentities() {
        offline()
        val id = EngineRuntime.library.value.single { it.name == "C04 details skills 5 thermal 100" }.id
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        compose.waitForIdle(); click("drones-open"); ready(id, 16)
        val rolls = model.details!!.stacks.filter { it.mutation != null }
        assertEquals(3, rolls.size); assertEquals(3, rolls.map { it.objectKey }.distinct().size)
        assertEquals(rolls[0].mutation, rolls[2].mutation)
        assertNotEquals(rolls[0].mutation, rolls[1].mutation)
        compose.onNodeWithTag("drone-13-variations").assertDoesNotExist()
        click("drone-13-details")
        compose.onNodeWithTag("drone-13-hp_shield").performScrollTo().assertExists()
        val selected = model.details!!.stacks[13]
        click("drone-13-select"); compose.activityRule.scenario.recreate(); ready(id, 16)
        assertTrue(selected.objectKey in model.selected)
        assertEquals(selected, model.details!!.stacks[13])
        compose.onNodeWithTag("drone-13-hp_shield").performScrollTo().assertExists()
        screenshot("existing-roll-details")
    }
}
