package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.ActivityInfo
import android.content.pm.PackageManager
import android.content.res.Configuration
import android.graphics.Bitmap
import android.provider.Settings
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

@RunWith(AndroidJUnit4::class)
class AppShellTest {
    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun offlineLaunchShowsHonestStatusAndNavigatesBack() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        // The CI script disables networking before the app is installed/launched.
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        compose.onNodeWithText(context.getString(R.string.status_body)).assertIsDisplayed()
        screenshot("home")
        compose.onNodeWithText(context.getString(R.string.about_button)).performScrollTo().performClick()
        compose.onNodeWithText(context.getString(R.string.about_title)).assertIsDisplayed()
        compose.onNodeWithText(context.getString(R.string.version, BuildConfig.VERSION_NAME)).assertIsDisplayed()
        screenshot("about")
        compose.onNodeWithText(context.getString(R.string.back)).performScrollTo().performClick()
        compose.onNodeWithText(context.getString(R.string.status_title)).assertIsDisplayed()
    }

    @Test
    fun aboutSurvivesActivityRecreationAndLandscapeWithSystemBack() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        compose.onNodeWithText(context.getString(R.string.about_button)).performScrollTo().performClick()
        compose.activityRule.scenario.recreate()
        compose.onNodeWithText(context.getString(R.string.about_title)).assertIsDisplayed()
        try {
            compose.activityRule.scenario.onActivity {
                it.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE
            }
            compose.waitUntil(10_000) {
                compose.activity.resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
            }
            compose.onNodeWithText(context.getString(R.string.about_title)).assertIsDisplayed()
            compose.onNodeWithText(context.getString(R.string.back)).performScrollTo().assertIsDisplayed()
            screenshot("about-landscape")
            compose.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
            compose.onNodeWithText(context.getString(R.string.status_title)).performScrollTo().assertIsDisplayed()
        } finally {
            compose.activityRule.scenario.onActivity {
                it.requestedOrientation = ActivityInfo.SCREEN_ORIENTATION_PORTRAIT
            }
            compose.waitUntil(10_000) {
                compose.activity.resources.configuration.orientation == Configuration.ORIENTATION_PORTRAIT
            }
        }
    }

    private fun screenshot(name: String) {
        compose.waitForIdle()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val bitmap = instrumentation.uiAutomation.takeScreenshot()
        assertNotNull("Android screenshot must be captured", bitmap)
        val directory = File(instrumentation.targetContext.filesDir, "a06-screenshots")
        check(directory.isDirectory || directory.mkdirs())
        File(directory, "$name.png").outputStream().use {
            check(bitmap.compress(Bitmap.CompressFormat.PNG, 100, it))
        }
        bitmap.recycle()
    }
}
