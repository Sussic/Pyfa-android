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

/** Explicit disposable offline implant_sets phase only. Written coverage is not executed device proof. */
@RunWith(AndroidJUnit4::class)
class OfflineImplantSetsUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineImplantSetsModel::class.java]
    private val profiles get() = ViewModelProvider(compose.activity)[OfflineProfilesModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun setup() {
        assertEquals("implant_sets", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
    }
    private fun name(label: String) = "$label ${UUID.randomUUID()}"
    private fun state(id: String?) = EngineRuntime.offlineFeatureState(context, id).get(120, TimeUnit.SECONDS)
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun feature(operation: String, args: JSONObject, id: String?): OfflineFeatureResponse =
        EngineRuntime.offlineFeatureRequest(context, state(id).context, operation, args, id).get(120, TimeUnit.SECONDS)
            .also { assertTrue(it.error?.message, it.ok) }
    private fun ordinary(id: String, operation: BridgeOperation) = EngineRuntime.request(context, operation, mapOf(id to fit(id).revision))
        .get(120, TimeUnit.SECONDS).also { assertTrue(it.error?.message, it.isSuccess) }
    private fun createFit(): String {
        val before = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Rifter", name("Set test fit")).get(120, TimeUnit.SECONDS).isSuccess)
        return EngineRuntime.library.value.single { it.id !in before }.id.also { EngineRuntime.selectFit(context, it).get(30, TimeUnit.SECONDS) }
    }
    private fun createProfile(id: String?): OfflineProfile {
        val before = state(id).profiles.map { it.id }.toSet()
        return feature("create_profile", JSONObject().put("name", name("Set test pilot")).put("source", "builtin:all0"), id)
            .state!!.profiles.single { it.id !in before }
    }
    private fun catalogue() = EngineRuntime.characterImplantCatalog(context).get(120, TimeUnit.SECONDS)
    private fun settled() { waitFor { !model.busy && model.available } }
    private fun profileSettled() { waitFor { !profiles.loading && !profiles.saving && profiles.state?.context == EngineRuntime.offlineFeatures.value?.context } }
    private fun findSet(query: String, id: String) {
        text("implant-sets-search", query); settled(); click("implant-set-select-$id"); settled()
    }
    private fun chooseItem(item: CharacterImplantItem) {
        click("implant-set-add"); waitFor { !model.busy && model.catalogue != null }
        text("implant-set-item-search", item.name); click("implant-set-pick-${item.itemId}")
    }

    @Test fun noFitPredefinedBrowseCustomCreateEditDuplicateDeleteAndLibraryReplay() {
        setup()
        // This explicitly selected phase is destructive only to its disposable test fixture.
        for (id in EngineRuntime.library.value.map { it.id }) ordinary(id, BridgeOperation.DeleteFit(id, true))
        waitFor { EngineRuntime.state.value is EngineState.Empty }
        click("implant-sets-open"); settled()
        compose.onNodeWithTag("implant-sets-no-fit").assertExists()
        findSet("Genolution", "builtin:implant-set:1")
        compose.onNodeWithTag("implant-set-family-grade").assertTextContains("Grade: none")
        assertEquals(listOf(2082, 2589, 33393, 33394), model.detail!!.items.map { it.itemId })
        compose.onNodeWithTag("implant-set-duplicate").assertDoesNotExist()
        compose.onNodeWithTag("implant-set-add").assertDoesNotExist()
        text("implant-sets-search", ""); settled()
        val label = name("No fit recipe")
        click("implant-set-create"); text("implant-set-name", label); click("implant-set-save")
        waitFor { !model.busy && model.detail?.entry?.name == label }; settled()
        val original = model.detail!!.entry.id
        assertTrue(model.detail!!.items.isEmpty()); assertEquals("library", model.view.historyTarget)
        val auroral = catalogue().items.single { it.name == "Genolution 'Auroral' AU-79" }
        chooseItem(auroral); waitFor { model.addChoice == null && !model.busy }; settled()
        assertEquals(79, model.detail!!.items.single().slot)
        click("implant-set-rename"); text("implant-set-name", "$label renamed"); click("implant-set-save")
        waitFor { !model.busy && model.detail?.entry?.name == "$label renamed" }; settled()
        assertEquals(original, model.detail!!.entry.id)
        click("implant-set-duplicate"); text("implant-set-name", "$label copy"); click("implant-set-save")
        waitFor { !model.busy && model.detail?.entry?.name == "$label copy" }; settled()
        val copied = model.detail!!.entry.id
        assertNotEquals(original, copied); assertEquals(listOf(auroral.itemId), model.detail!!.items.map { it.itemId })
        text("implant-sets-search", "$label copy"); settled()
        click("implant-set-delete"); compose.onNodeWithTag("implant-set-delete-confirm").performClick()
        waitFor { !model.busy && model.detail == null }; settled()
        assertEquals(0L, model.state!!.total); assertNull(model.view.selectedSetId)
        click("implant-sets-undo"); settled()
        assertTrue(model.state!!.entries.any { it.id == copied }); assertNull(model.detail)
        click("implant-set-select-$copied"); settled()
        val restored = model.detail!!.entry.revision
        click("implant-set-remove-${auroral.itemId}"); waitFor { !model.busy && model.detail?.items?.isEmpty() == true }; settled()
        assertTrue(model.detail!!.entry.revision > restored)
        findSet("$label renamed", original)
        assertEquals(listOf(auroral.itemId), model.detail!!.items.map { it.itemId })
        val noFitPilot = createProfile(null)
        settled(); click("implant-set-target-${noFitPilot.id}"); settled()
        click("implant-set-review-profile"); compose.onNodeWithTag("implant-set-apply-confirm").performClick(); settled()
        assertEquals(listOf(auroral.itemId), state(null).profiles.single { it.id == noFitPilot.id }.implants.map { it.itemId })
        assertNull(model.state!!.saveSource)
        assertTrue(EngineRuntime.library.value.isEmpty())
    }

    @Test fun saveAppliedCharacterSourceAndApplyDormantLocalCollectionWithoutSwitchingSource() {
        setup(); val id = createFit(); var pilot = createProfile(id)
        val implants = catalogue().items
        val nav1 = implants.single { it.name == "Eifyr and Co. 'Rogue' Navigation NN-601" }
        val nav5 = implants.single { it.name == "Eifyr and Co. 'Rogue' Navigation NN-605" }
        val auroral = implants.single { it.name == "Genolution 'Auroral' AU-79" }
        feature("assign_profile", JSONObject().put("fit_id", id).put("profile_id", pilot.id), id)
        pilot = feature("add_profile_implant", JSONObject().put("profile_id", pilot.id).put("revision", pilot.revision)
            .put("item_id", nav1.itemId).put("replace_implant_id", JSONObject.NULL), id).state!!.profiles.single { it.id == pilot.id }
        ordinary(id, BridgeOperation.FitImplant(id, nav5.itemId)); ordinary(id, BridgeOperation.SetImplantActive(id, nav5.slot, false))
        ordinary(id, BridgeOperation.FitImplant(id, auroral.itemId)); ordinary(id, BridgeOperation.SetImplantActive(id, auroral.slot, false))
        feature("set_implant_source", JSONObject().put("fit_id", id).put("fit_revision", fit(id).revision).put("source", "CHARACTER"), id)
        val beforeLocal = fit(id).implants
        val beforeCharacter = pilot.implants
        click("implants-open"); click("implants-open-sets"); settled()
        compose.onNodeWithTag("implant-set-save-source").assertTextContains("Character:")
        compose.onNodeWithTag("implant-set-dormant").assertExists()
        // Previewing another character must not alter the source copied by Save current.
        val other = createProfile(id)
        settled(); click("implant-set-target-${other.id}"); settled()
        val label = name("Saved applied implants")
        click("implant-set-save-current"); text("implant-set-name", label); click("implant-set-save")
        waitFor { !model.busy && model.detail?.entry?.name == label }; settled()
        val saved = model.detail!!
        assertEquals(listOf(nav1.itemId), saved.items.map { it.itemId })
        assertEquals(beforeLocal, fit(id).implants)
        assertEquals(beforeCharacter, state(id).profiles.single { it.id == pilot.id }.implants)
        click("implant-set-target-fit"); settled(); click("implant-set-review-fit")
        waitFor { model.applicationReview != null && !model.busy }
        assertEquals(OfflineImplantApplyDisposition.REPLACED, model.applicationReview!!.steps.single().disposition)
        assertEquals(auroral.itemId, model.applicationReview!!.untouched.single().itemId)
        compose.onNodeWithTag("implant-set-apply-confirm").performClick(); settled()
        assertEquals(ImplantLocation.CHARACTER, state(id).bindings.getValue(id).implantSource)
        assertEquals(listOf(79, 6), fit(id).implants.map { it.slot })
        assertFalse(fit(id).implants.first().active); assertTrue(fit(id).implants.last().active)
        assertEquals(saved, model.detail)
        val after = fit(id); val generation = model.state!!.context.generation
        click("implant-set-review-fit"); compose.onNodeWithTag("implant-set-apply-confirm").performClick(); settled()
        assertEquals(after, fit(id)); assertEquals(generation, model.state!!.context.generation)
        compose.onNodeWithTag("implant-sets-message").assertTextContains("No saved values changed")
        click("implant-sets-undo"); settled()
        assertEquals(beforeLocal, fit(id).implants)
        assertEquals(ImplantLocation.CHARACTER, state(id).bindings.getValue(id).implantSource)
    }

    @Test fun targetedCharacterApplicationPreservesOldSkillDraftAndRecreatesIncomingRows() {
        setup(); val id = createFit(); val pilot = createProfile(id)
        feature("assign_profile", JSONObject().put("fit_id", id).put("profile_id", pilot.id), id)
        click("profiles-open"); profileSettled(); click("profile-select-${pilot.id}")
        val skill = profiles.state!!.skills.first()
        text("profile-skill-search", skill.name); click("profile-skill-${skill.id}"); click("profile-level-0")
        assertTrue(profiles.dirty)
        compose.onNodeWithTag("profile-open-implant-sets").assertIsNotEnabled()
        click("profiles-back"); compose.onNodeWithText("Keep draft and go back").performClick()
        click("implant-sets-open"); settled()
        findSet("High-grade Snake", "builtin:implant-set:3")
        compose.onNodeWithTag("implant-set-skill-draft-block").assertExists()
        compose.onNodeWithTag("implant-set-target-${pilot.id}").assertIsNotEnabled()
        assertTrue(profiles.dirty); assertEquals(0, profiles.draftLevel)
        click("implant-sets-back"); click("profiles-open"); profileSettled()
        assertTrue(profiles.dirty); assertEquals(0, profiles.draftLevel)
        click("profile-skill-revert"); click("profile-open-implant-sets"); settled()
        assertEquals(pilot.id, model.view.targetProfileId)
        val selected = model.detail!!
        click("implant-set-review-profile"); compose.onNodeWithTag("implant-set-apply-confirm").performClick(); settled()
        val applied = state(id).profiles.single { it.id == pilot.id }
        assertEquals(selected.items.map { it.itemId }, applied.implants.map { it.itemId })
        assertTrue(applied.implants.all { it.active }); assertEquals(ImplantLocation.FIT, state(id).bindings.getValue(id).implantSource)
        click("implant-set-review-profile")
        assertTrue(model.applicationReview!!.steps.all { it.disposition == OfflineImplantApplyDisposition.REPLACED })
        compose.onNodeWithTag("implant-set-apply-confirm").performClick(); settled()
        val reapplied = state(id).profiles.single { it.id == pilot.id }
        assertTrue(reapplied.revision > applied.revision)
        assertTrue(reapplied.implants.map { it.implantId }.toSet().intersect(applied.implants.map { it.implantId }.toSet()).isEmpty())
        assertEquals(selected, model.detail); assertEquals("library", model.view.historyTarget)
        click("implant-sets-undo"); settled()
        assertEquals(applied.implants, state(id).profiles.single { it.id == pilot.id }.implants)
        assertFalse(profiles.dirty)
    }
}
