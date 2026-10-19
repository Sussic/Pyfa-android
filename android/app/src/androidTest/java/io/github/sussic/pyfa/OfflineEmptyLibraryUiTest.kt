package io.github.sussic.pyfa

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

/** Run only on newly cleared disposable app data with offline_features_phase=empty. */
@RunWith(AndroidJUnit4::class)
class OfflineEmptyLibraryUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    @Test fun profilesAndTheirLibraryUndoRemainUsableWithoutAnyFit() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        assertEquals("empty", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        // Guard against accidentally running a destructive fixture on an existing library.
        val diagnostics = org.json.JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        assertFalse(diagnostics.getJSONObject("persistence").getBoolean("opened_existing"))
        val initial = EngineRuntime.library.value.single()
        assertTrue(EngineRuntime.request(context, BridgeOperation.DeleteFit(initial.id, true), mapOf(initial.id to initial.revision)).get(120, TimeUnit.SECONDS).isSuccess)
        waitFor { EngineRuntime.library.value.isEmpty() && EngineRuntime.state.value is EngineState.Empty }
        click("profiles-open")
        val model = ViewModelProvider(compose.activity)[OfflineProfilesModel::class.java]
        waitFor { !model.loading && model.state != null }
        val count = model.state!!.profiles.size
        compose.onNodeWithTag("profile-name").performTextReplacement("Empty library pilot")
        click("profile-copy"); waitFor { !model.saving && model.state!!.profiles.size == count + 1 }
        assertTrue(EngineRuntime.library.value.isEmpty())
        click("profiles-undo"); waitFor { !model.saving && model.state!!.profiles.size == count }
        click("profiles-redo"); waitFor { !model.saving && model.state!!.profiles.size == count + 1 }
        click("profiles-back"); click("eft-open")
        compose.onNodeWithTag("eft-text-0").assertExists()
    }
}
