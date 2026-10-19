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
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Compiled-only until the explicit offline character_implants phase runs on disposable app data. */
@RunWith(AndroidJUnit4::class)
class CharacterImplantsUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val profiles get() = ViewModelProvider(compose.activity)[OfflineProfilesModel::class.java]
    private val implants get() = ViewModelProvider(compose.activity)[ImplantEditorModel::class.java]
    private val equipment get() = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun setup() {
        assertEquals("character_implants", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
    }
    private fun state(fit: String? = null) = EngineRuntime.offlineFeatureState(context, fit).get(120, TimeUnit.SECONDS)
    private fun feature(op: String, args: JSONObject, fit: String? = null): OfflineFeatureResponse =
        EngineRuntime.offlineFeatureRequest(context, state(fit).context, op, args, fit).get(120, TimeUnit.SECONDS).also { assertTrue(it.error?.message, it.ok) }
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun ordinary(id: String, op: BridgeOperation) = EngineRuntime.request(context, op, mapOf(id to fit(id).revision))
        .get(120, TimeUnit.SECONDS).also { assertTrue(it.error?.message, it.isSuccess) }
    private fun item(name: String) = EngineRuntime.equipmentCatalog(context).get(30, TimeUnit.SECONDS).items.single { it.name == name }
    private fun choose(item: EquipmentItem) {
        click("profile-implant-add")
        waitFor { !equipment.busy && equipment.catalog != null }
        compose.onNodeWithTag("profile-implant-search").performTextReplacement(item.name)
        click("profile-implant-search-submit"); waitFor { !equipment.busy }
        waitFor { compose.onAllNodesWithTag("profile-implant-choice-${item.id}").fetchSemanticsNodes().isNotEmpty() }
        click("profile-implant-choice-${item.id}")
    }
    private fun profileSettled() { waitFor { !profiles.loading && !profiles.saving && profiles.state?.context == EngineRuntime.offlineFeatures.value?.context } }
    private fun implantSettled() { waitFor { !implants.loading && !implants.editing && implants.currentDetails != null } }

    @Test fun noFitBuiltinProtectionSlot79ReplaceCancelDirtySectionsCompleteCopyAndRemoval() {
        setup()
        // This phase explicitly requires disposable data. No real-phone/user-data execution is implied.
        for (id in EngineRuntime.library.value.map { it.id }) ordinary(id, BridgeOperation.DeleteFit(id, true))
        waitFor { EngineRuntime.state.value is EngineState.Empty }
        click("profiles-open"); profileSettled()
        click("profile-select-builtin:all0"); click("profile-section-implants")
        compose.onNodeWithTag("profile-implant-add").assertIsNotEnabled()
        compose.onNodeWithTag("profile-copy-scope").assertExists()
        compose.onNodeWithTag("profile-name").performTextReplacement("Native no-fit implants")
        click("profile-copy"); waitFor { profiles.selectedProfile?.name == "Native no-fit implants" && !profiles.saving }; profileSettled()
        val profile = profiles.profileId!!
        val auroral = item("Genolution 'Auroral' AU-79")
        val nav1 = item("Eifyr and Co. 'Rogue' Navigation NN-601")
        val nav5 = item("Eifyr and Co. 'Rogue' Navigation NN-605")
        val recent = EngineRuntime.recent.value.toList()
        choose(auroral); waitFor { profiles.selectedProfile?.implants?.any { it.itemId == auroral.id } == true && profiles.implantChoice == null }; profileSettled()
        assertEquals(79, profiles.selectedProfile!!.implants.single().slot)
        choose(nav1); waitFor { profiles.selectedProfile?.implants?.size == 2 && profiles.implantChoice == null }; profileSettled()
        val original = profiles.selectedProfile!!
        choose(nav1)
        compose.onNodeWithTag("profile-implant-replace-confirm").assertIsEnabled()
        compose.onNodeWithTag("profile-implant-replace-cancel").performClick()
        assertEquals(original, profiles.selectedProfile); assertEquals(recent, EngineRuntime.recent.value)
        click("profile-implant-picker-close")
        choose(nav5); compose.onNodeWithTag("profile-implant-replace-confirm").performClick()
        waitFor { profiles.selectedProfile?.implants?.any { it.itemId == nav5.id } == true && profiles.implantChoice == null }; profileSettled()
        val replaced = profiles.selectedProfile!!
        assertEquals(listOf(79, 6), replaced.implants.map { it.slot })
        assertNotEquals(original.implants.last().implantId, replaced.implants.last().implantId)
        assertTrue(replaced.implants.last().active); assertEquals(recent, EngineRuntime.recent.value)
        click("profile-section-skills")
        val skill = profiles.state!!.skills.first()
        compose.onNodeWithTag("profile-skill-search").performTextReplacement(skill.name)
        click("profile-skill-${skill.id}"); click("profile-level-0"); click("profile-section-implants")
        compose.onNodeWithTag("profile-dirty").assertExists(); compose.onNodeWithTag("profile-implant-add").assertIsNotEnabled()
        compose.activityRule.scenario.recreate(); profileSettled()
        assertTrue(profiles.dirty); assertEquals(OfflineProfileSection.IMPLANTS, profiles.section)
        click("profile-skill-revert"); assertFalse(profiles.dirty)
        val auroralRow = profiles.selectedProfile!!.implants.single { it.itemId == auroral.id }
        click("profile-implant-remove-${auroralRow.implantId}")
        waitFor { profiles.selectedProfile?.implants?.size == 1 && !profiles.saving }; profileSettled()
        val source = profiles.selectedProfile!!
        compose.onNodeWithTag("profile-name").performTextReplacement("Complete implant duplicate")
        click("profile-copy"); waitFor { profiles.selectedProfile?.name == "Complete implant duplicate" && !profiles.saving }; profileSettled()
        val duplicate = profiles.selectedProfile!!
        assertNotEquals(source.id, duplicate.id); assertNotEquals(source.implants.single().implantId, duplicate.implants.single().implantId)
        assertEquals(source.implants.single().itemId, duplicate.implants.single().itemId)
        assertEquals(source.implants.single().active, duplicate.implants.single().active)
        assertEquals(source, state().profiles.single { it.id == profile })
        click("profile-delete"); compose.onNodeWithTag("profile-delete-cancel").performClick(); assertEquals(duplicate, profiles.selectedProfile)
        click("profile-delete"); compose.onNodeWithTag("profile-delete-confirm").performClick()
        waitFor { profiles.state?.profiles?.none { it.id == duplicate.id } == true && !profiles.saving }; profileSettled()
        assertTrue(EngineRuntime.library.value.isEmpty())
        click("profiles-back")
    }

    @Test fun reversibleSourcesRetainLocalIdentityAndEquipmentDuplicateSwitchesInOneAction() {
        setup()
        val prior = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Rifter", "Native character source").get(120, TimeUnit.SECONDS).isSuccess)
        val id = EngineRuntime.library.value.single { it.id !in prior }.id
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        val oldProfiles = state(id).profiles.map { it.id }.toSet()
        val pilot = feature("create_profile", JSONObject().put("name", "Native source pilot").put("source", "builtin:all5"), id).state!!.profiles.single { it.id !in oldProfiles }
        feature("assign_profile", JSONObject().put("fit_id", id).put("profile_id", pilot.id), id)
        val nav1 = item("Eifyr and Co. 'Rogue' Navigation NN-601"); val nav5 = item("Eifyr and Co. 'Rogue' Navigation NN-605")
        feature("add_profile_implant", JSONObject().put("profile_id", pilot.id).put("revision", pilot.revision).put("item_id", nav1.id).put("replace_implant_id", JSONObject.NULL), id)
        ordinary(id, BridgeOperation.FitImplant(id, nav5.id)); ordinary(id, BridgeOperation.SetImplantActive(id, 6, false))
        click("implants-open"); implantSettled()
        val local = implants.currentDetails!!.implants.single(); compose.runOnUiThread { implants.select(local.objectKey, true) }
        click("implants-source-character"); implantSettled()
        compose.onNodeWithTag("implants-character").assertExists(); compose.onNodeWithTag("implant-0-toggle").assertDoesNotExist()
        assertEquals(listOf(local), implants.currentDetails!!.implants)
        click("implants-source-fit"); implantSettled(); assertTrue(local.objectKey in implants.selected)
        assertFalse(implants.currentDetails!!.implants.single().active)
        click("implants-source-character"); implantSettled()
        click("implants-browse")
        compose.onNodeWithTag("equipment-search").performTextReplacement(nav5.name)
        click("equipment-search-submit"); waitFor { !equipment.busy }; click("equipment-item-${nav5.id}")
        waitFor { !implants.addLoading && implants.currentAdd(nav5.id) != null }
        compose.onNodeWithText("Use fit implants").assertExists()
        val before = state(id).history.undoCount
        click("equipment-fit-implant"); implantSettled()
        assertEquals(ImplantLocation.FIT, implants.currentDetails!!.location); assertEquals(listOf(local), implants.currentDetails!!.implants)
        assertEquals(before + 1, state(id).history.undoCount)
        feature("undo", JSONObject(), id); implantSettled()
        assertEquals(ImplantLocation.CHARACTER, implants.currentDetails!!.location)
        click("implants-browse")
        compose.onNodeWithTag("equipment-search").performTextReplacement(nav1.name)
        click("equipment-search-submit"); waitFor { !equipment.busy }; click("equipment-item-${nav1.id}")
        waitFor { !implants.addLoading && implants.currentAdd(nav1.id) != null }
        click("equipment-fit-implant")
        assertEquals(nav5.id, implants.pendingReplacement!!.options.occupant!!.itemId)
        compose.onNodeWithText("This also switches to Fit-specific implants. The character collection is kept.").assertExists()
        ordinary(id, BridgeOperation.RenameFit(id, "Changed source dialog"))
        waitFor { !implants.replacementCurrent }
        compose.onNodeWithTag("implant-replace-confirm").assertIsNotEnabled()
        compose.onNodeWithTag("implant-replace-cancel").performClick()
        assertEquals(ImplantLocation.CHARACTER, state(id).bindings.getValue(id).implantSource)
        click("equipment-view-fit"); click("modules-back"); click("implants-open"); implantSettled()
        click("implants-edit-character"); profileSettled()
        assertEquals(pilot.id, profiles.profileId); assertEquals(OfflineProfileSection.IMPLANTS, profiles.section)
    }
}
