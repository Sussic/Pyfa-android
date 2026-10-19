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
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred disposable-data device gate. Source/compilation alone never counts as UI execution. */
@RunWith(AndroidJUnit4::class)
class PilotSecurityUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val pilot get() = ViewModelProvider(compose.activity)[PilotSecurityModel::class.java]
    private val profiles get() = ViewModelProvider(compose.activity)[OfflineProfilesModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun admitted() {
        assertEquals("pilot_security", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
    }
    private fun createPilotProfile() {
        click("profiles-open"); waitFor { profiles.available }
        click("profile-select-builtin:all5")
        compose.onNodeWithTag("profile-name").performTextReplacement("Security UI ${System.nanoTime()}")
        click("profile-copy"); waitFor { profiles.available && profiles.selectedProfile?.readonly == false }
    }
    @Test fun savedFitCharacterPresetCustomValidationAndBackRetainOwnedDraft() {
        admitted()
        val before = EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context, "Pacifier", "Pilot security UI").get(120, TimeUnit.SECONDS).isSuccess)
        val id = EngineRuntime.library.value.single { it.id !in before }.id
        EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        click("pilot-security-open"); waitFor { pilot.available }
        click("pilot-security-character"); click("pilot-security-save")
        waitFor { pilot.available && pilot.currentDetails?.source == PilotSecuritySource.CHARACTER }
        assertNull(EngineRuntime.pilotSecurityDetails(context, id).get(30, TimeUnit.SECONDS).pilot)
        click("pilot-security-preset-0"); click("pilot-security-save")
        waitFor { pilot.available && pilot.currentDetails?.source == PilotSecuritySource.EXPLICIT }
        assertFalse(pilot.currentDetails!!.pilot!!.raw is Double)
        compose.onNodeWithTag("pilot-security-input").performScrollTo().performTextReplacement("-6.25")
        click("pilot-security-save"); waitFor { pilot.available && pilot.currentDetails?.pilot == SecurityNumber(-6.25) }
        compose.onNodeWithTag("pilot-security-input").performScrollTo().performTextReplacement("1,2")
        compose.onNodeWithTag("pilot-security-save").assertIsNotEnabled()
        click("pilot-security-back"); click("pilot-security-open"); waitFor { pilot.available }
        assertEquals("1,2", pilot.text); assertTrue(pilot.dirty)
        click("pilot-security-revert"); assertEquals("-6.25", pilot.text); assertFalse(pilot.dirty)
    }
    @Test fun profileSecurityBuiltinProtectionAndExistingSkillDraftStayDistinct() {
        admitted(); click("profiles-open"); waitFor { profiles.available }
        click("profile-select-builtin:all5"); click("profile-section-security")
        compose.onNodeWithTag("profile-security-input").assertIsNotEnabled()
        compose.onNodeWithTag("profile-security-save-as").assertIsNotEnabled()
        compose.onNodeWithTag("profile-name").performScrollTo().performTextReplacement("Security draft UI ${System.nanoTime()}")
        click("profile-copy"); waitFor { profiles.available && profiles.selectedProfile?.readonly == false }
        click("profile-section-skills")
        val skill = profiles.state!!.skills.first()
        compose.onNodeWithTag("profile-skill-search").performScrollTo().performTextReplacement(skill.name)
        click("profile-skill-${skill.id}"); click("profile-level-0"); click("profile-section-security")
        assertTrue(profiles.dirty); compose.onNodeWithTag("profile-security-input").assertIsNotEnabled()
        compose.onNodeWithTag("profile-security-skill-draft").assertExists()
        click("profile-section-skills"); click("profile-skill-revert"); click("profile-section-security")
        compose.onNodeWithTag("profile-security-input").assertIsEnabled()
    }
    @Test fun profileSaveAsCopiesDraftWithoutReassigningAndBackKeepsUnsubmittedText() {
        admitted(); createPilotProfile(); val sourceId = profiles.profileId!!
        val source = profiles.selectedProfile!!; val bindings = profiles.state!!.bindings
        click("profile-section-security")
        compose.onNodeWithTag("profile-security-input").performScrollTo().performTextReplacement("-6.25")
        compose.onNodeWithTag("profile-name").performScrollTo().performTextReplacement("Security saved copy ${System.nanoTime()}")
        click("profile-security-save-as")
        waitFor { profiles.available && profiles.profileId != sourceId && !profiles.securityDirty }
        assertEquals(source, profiles.state!!.profiles.single { it.id == sourceId })
        assertEquals(bindings, profiles.state!!.bindings); assertEquals(SecurityNumber(-6.25), profiles.selectedProfile!!.secStatus)
        assertEquals(source.levels, profiles.selectedProfile!!.levels)
        compose.onNodeWithTag("profile-security-input").performScrollTo().performTextReplacement("2.75")
        click("profiles-back"); compose.onNodeWithText("Keep draft and go back").performClick()
        click("profiles-open"); waitFor { profiles.available }
        assertEquals("2.75", profiles.securityText); assertTrue(profiles.securityDirty)
        click("profile-security-revert"); assertEquals("-6.25", profiles.securityText)
    }
}
