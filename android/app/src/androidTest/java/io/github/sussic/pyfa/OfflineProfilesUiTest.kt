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
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Run with offline_features_phase=prepare, then a fresh app process with =restart. */
@RunWith(AndroidJUnit4::class)
class OfflineProfilesUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineProfilesModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun state(fitId: String?) = EngineRuntime.offlineFeatureState(context, fitId).get(120, TimeUnit.SECONDS)
    private fun dispatch(operation: String, args: JSONObject, fitId: String?) = EngineRuntime.offlineFeatureRequest(
        context, state(fitId).context, operation, args, fitId).get(120, TimeUnit.SECONDS).also { assertTrue(it.error?.message, it.ok) }
    private fun create(name: String): String {
        val before = EngineRuntime.library.value.map { it.id }.toSet()
        val response = EngineRuntime.createEmptyFit(context, "Vexor", name).get(120, TimeUnit.SECONDS)
        assertTrue(response.error?.message, response.isSuccess)
        return EngineRuntime.library.value.single { it.id !in before }.id
    }
    /** Select separately with alpha_profile_phase=prepare/restart; existing gates stay intact. */
    @Test fun alphaCloneTouchLearnedEffectiveRecreationSharedUndoAndFreshReopen() {
        val phase = InstrumentationRegistry.getArguments().getString("alpha_profile_phase") ?: error("Explicit ALPHA1 phase required")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val receipt = File(context.noBackupFilesDir, "offline-alpha-profile-test.json")
        if (phase == "restart") {
            val saved = JSONObject(receipt.readText()); val first = saved.getString("first")
            val value = state(first); val profile = value.profiles.single { it.id == saved.getString("profile") }
            assertEquals(saved.getInt("clone"), profile.alphaCloneId)
            assertEquals(0, profile.level(saved.getInt("skill"))); assertEquals(0, profile.effectiveLevel(saved.getInt("skill")))
            for (fit in listOf(first, saved.getString("second"))) assertEquals(profile.id, value.bindings.getValue(fit).profileId)
            assertEquals(saved.getLong("unrelated_revision"), value.bindings.getValue(saved.getString("unrelated")).fitRevision)
            assertEquals(0, value.history.undoCount)
            return
        }
        assertEquals("prepare", phase)
        val first = create("Alpha first"); val second = create("Alpha shared"); val unrelated = create("Alpha unrelated")
        val unrelatedRevision = state(unrelated).bindings.getValue(unrelated).fitRevision
        EngineRuntime.selectFit(context, first).get(30, TimeUnit.SECONDS)
        click("profiles-open"); waitFor { model.state?.selectedFitId == first && model.available }
        click("profile-select-builtin:all5")
        val sourceChoices = checkNotNull(model.state).alphaCatalogue
        assertTrue(sourceChoices.error, sourceChoices.available); assertTrue(sourceChoices.clones.isNotEmpty())
        compose.onNodeWithTag("profile-clone-${sourceChoices.clones.first().id}").assertIsNotEnabled()
        compose.onNodeWithTag("profile-name").performTextReplacement("Alpha custom")
        click("profile-copy"); waitFor { !model.saving && model.selectedProfile?.name == "Alpha custom" }
        val profile = checkNotNull(model.profileId)
        click("profile-assign"); waitFor { model.state?.bindings?.get(first)?.profileId == profile && model.available }
        dispatch("assign_profile", JSONObject().put("fit_id", second).put("profile_id", profile), first)
        waitFor { model.state?.bindings?.get(second)?.profileId == profile && model.available }
        for (choice in sourceChoices.clones) {
            click("profile-clone-${choice.id}"); waitFor { model.selectedProfile?.alphaCloneId == choice.id && model.available }
            compose.onNodeWithTag("profile-clone-${choice.id}").assertIsNotEnabled()
            assertEquals(unrelatedRevision, state(first).bindings.getValue(unrelated).fitRevision)
        }
        val clone = sourceChoices.clones.last().id
        val capped = checkNotNull(model.selectedProfile)
        val skill = model.state!!.skills.first { (capped.effectiveLevel(it.id) ?: error("Missing effective skill")) < 5 }
        compose.onNodeWithTag("profile-skill-search").performTextReplacement(skill.name)
        click("profile-skill-${skill.id}")
        compose.onNodeWithTag("profile-skill-effective").assertTextContains("Saved learned: 5")
        click("profile-level-unlearned"); click("profile-skill-save")
        waitFor { !model.dirty && model.available && model.selectedProfile?.level(skill.id) == null }
        compose.onNodeWithTag("profile-skill-effective").assertTextContains("effective: 0")
        click("profile-level-0"); compose.activityRule.scenario.recreate()
        waitFor { model.dirty && model.available }
        assertEquals(0, model.draftLevel); assertEquals(clone, model.selectedProfile!!.alphaCloneId)
        click("profile-skill-save"); waitFor { !model.dirty && model.available && model.selectedProfile?.level(skill.id) == 0 }
        click("profiles-undo"); waitFor { model.available && model.selectedProfile?.level(skill.id) == null }
        click("profiles-redo"); waitFor { model.available && model.selectedProfile?.level(skill.id) == 0 }
        click("profile-clone-omega"); waitFor { model.available && model.selectedProfile?.alphaCloneId == null }
        click("profiles-undo"); waitFor { model.available && model.selectedProfile?.alphaCloneId == clone }
        assertEquals(0, model.selectedProfile!!.level(skill.id))
        val final = state(first)
        assertTrue(final.bindings.getValue(first).fitRevision > 1); assertTrue(final.bindings.getValue(second).fitRevision > 1)
        assertEquals(unrelatedRevision, final.bindings.getValue(unrelated).fitRevision)
        receipt.writeText(JSONObject().put("first", first).put("second", second).put("profile", profile)
            .put("clone", clone).put("skill", skill.id).put("unrelated", unrelated).put("unrelated_revision", unrelatedRevision).toString())
    }
    @Test fun protectedCopyExplicitDraftSharedAssignmentHistoryAndRestart() {
        val phase = InstrumentationRegistry.getArguments().getString("offline_features_phase") ?: error("Explicit durable test phase required")
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val receipt = File(context.noBackupFilesDir, "offline-profiles-test.json")
        if (phase == "restart") {
            val saved = JSONObject(receipt.readText())
            val first = saved.getString("first"); val second = saved.getString("second"); val profile = saved.getString("profile")
            val skill = saved.getInt("skill")
            val value = state(first)
            assertEquals(profile, value.bindings.getValue(first).profileId)
            assertEquals(profile, value.bindings.getValue(second).profileId)
            assertEquals(0, value.profiles.single { it.id == profile }.level(skill))
            assertEquals(0, value.history.undoCount) // History is deliberately session-local.
            return
        }
        assertEquals("prepare", phase)
        val first = create("Offline profile first"); val second = create("Offline profile second")
        EngineRuntime.selectFit(context, first).get(30, TimeUnit.SECONDS)
        click("profiles-open"); waitFor { model.state?.selectedFitId == first && !model.loading }
        click("profile-select-builtin:all0")
        compose.onNodeWithTag("profile-readonly").assertExists()
        compose.onNodeWithTag("profile-name").performTextReplacement("Offline test pilot")
        click("profile-copy")
        waitFor { !model.saving && model.selectedProfile?.name == "Offline test pilot" }
        val profile = checkNotNull(model.profileId)
        click("profile-assign"); waitFor { !model.saving && model.state?.bindings?.get(first)?.profileId == profile }
        dispatch("assign_profile", JSONObject().put("fit_id", second).put("profile_id", profile), first)
        waitFor { model.state?.bindings?.get(second)?.profileId == profile && !model.loading }
        val skill = model.state!!.skills.first()
        compose.onNodeWithTag("profile-skill-search").performTextReplacement(skill.name)
        click("profile-skill-${skill.id}"); click("profile-level-0")
        compose.onNodeWithTag("profile-dirty").assertExists()
        assertNull(state(first).profiles.single { it.id == profile }.level(skill.id))
        compose.activityRule.scenario.recreate()
        waitFor { model.dirty && !model.loading }
        assertEquals(0, model.draftLevel)
        val revisions = EngineRuntime.library.value.filter { it.id in setOf(first, second) }.associate { it.id to it.revision }
        click("profile-skill-save")
        waitFor { !model.saving && !model.dirty && model.selectedProfile?.level(skill.id) == 0 }
        assertTrue(EngineRuntime.library.value.filter { it.id in revisions }.all { it.revision > revisions.getValue(it.id) })
        click("profiles-undo"); waitFor { !model.saving && !model.loading && model.selectedProfile?.level(skill.id) == null }
        click("profiles-redo"); waitFor { !model.saving && !model.loading && model.selectedProfile?.level(skill.id) == 0 }
        click("profile-level-5"); click("profile-skill-revert"); assertFalse(model.dirty); assertEquals(0, model.draftLevel)
        receipt.writeText(JSONObject().put("first", first).put("second", second).put("profile", profile).put("skill", skill.id).toString())
        // A detached draft must survive removal of its profile by another action.
        val profilesBefore = state(first).profiles.map { it.id }.toSet()
        val extra = dispatch("create_profile", JSONObject().put("name", "Orphan draft test").put("source", "builtin:all0"), first)
            .state!!.profiles.single { it.id !in profilesBefore }.id
        waitFor { model.state?.profiles?.any { it.id == extra } == true && !model.loading }
        click("profile-select-$extra"); click("profile-skill-${skill.id}"); click("profile-level-5")
        click("profiles-back"); compose.onNodeWithText("Keep draft and go back").performClick()
        dispatch("delete_profile", JSONObject().put("profile_id", extra).put("replacement", profile), first)
        click("profiles-open"); waitFor { !model.loading && model.conflict && model.selectedProfile == null }
        assertTrue(model.dirty); assertEquals(5, model.draftLevel)
        compose.onNodeWithTag("profile-orphaned-draft").assertExists()
        click("profile-discard-orphan"); assertFalse(model.dirty)
    }
}
