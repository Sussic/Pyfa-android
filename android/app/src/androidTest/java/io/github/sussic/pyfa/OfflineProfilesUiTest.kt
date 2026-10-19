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
