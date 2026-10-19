package io.github.sussic.pyfa

import android.Manifest
import android.content.Context
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

/** Run system_security_seed, then force-stop/relaunch without clearing data and run system_security_reopen. */
@RunWith(AndroidJUnit4::class)
class SystemSecurityPersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun stats(id: String) = JSONObject().apply {
        fit(id).stats.toSortedMap().forEach { (key,stat) -> put(key,JSONObject().put("value",stat.value.raw).put("unit",stat.unit)) }
    }.toString()
    @Test fun systemChoiceCombatRigAndResultsSurviveActualProcessRestart() {
        val phase = InstrumentationRegistry.getArguments().getString("offline_features_phase")
        assertTrue("Choose system_security_seed or system_security_reopen",phase in setOf("system_security_seed","system_security_reopen"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val prefs = context.getSharedPreferences("system_security_qualification",Context.MODE_PRIVATE)
        if (phase == "system_security_seed") {
            val result = EngineRuntime.request(context,BridgeOperation.CreateFit(FitSpec("Security restart fixture","Fortizar",5,false,
                DamagePattern(25.0,25.0,25.0,25.0),Security(SystemSecurity.HISEC,0.0),
                listOf(ModuleSpec("Standup L-Set Target Acquisition Array I",ModuleState.ONLINE)),emptyList()))).get(120,TimeUnit.SECONDS)
            assertTrue(result.error?.message,result.isSuccess)
            val id = result.fits.single().id
            val baseline = stats(id)
            val edited = EngineRuntime.request(context,BridgeOperation.SetSystemSecurity(id,SystemSecurity.WSPACE),mapOf(id to fit(id).revision)).get(120,TimeUnit.SECONDS)
            assertTrue(edited.error?.message,edited.isSuccess)
            assertNotEquals("Combat-rig result must change with system security",baseline,stats(id))
            assertEquals(SystemSecurity.WSPACE,EngineRuntime.systemSecurityDetails(context,id).get(30,TimeUnit.SECONDS).system)
            val receipt = JSONObject().put("fit_id",id).put("stats",stats(id)).put("rig",fit(id).modules.single().name)
                .put("session",EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS).context.sessionId)
            assertTrue(prefs.edit().putString("seed",receipt.toString()).commit())
        } else {
            val saved = JSONObject(checkNotNull(prefs.getString("seed",null)) { "Run system_security_seed first on disposable app data." })
            val id = saved.getString("fit_id")
            assertNotEquals("A new process is required, not Activity recreation",saved.getString("session"),
                EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS).context.sessionId)
            assertEquals(saved.getString("stats"),stats(id)); assertEquals(saved.getString("rig"),fit(id).modules.single().name)
            assertEquals(SystemSecurity.WSPACE,EngineRuntime.systemSecurityDetails(context,id).get(30,TimeUnit.SECONDS).system)
            EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
            compose.onNodeWithTag("services-open").performScrollTo().performClick()
            val services = ViewModelProvider(compose.activity)[StructureServiceEditorModel::class.java]
            compose.waitUntil(120_000) { !services.loading && services.options?.fitId == id }
            compose.onNodeWithTag("services-system-security").performScrollTo().performClick()
            val model = ViewModelProvider(compose.activity)[SystemSecurityModel::class.java]
            compose.waitUntil(120_000) { !model.loading && model.currentDetails?.fitId == id }
            compose.onNodeWithTag("system-security-current").assertTextEquals("Current: W-Space")
            compose.onNodeWithTag("system-security-WSPACE").assertIsNotEnabled()
        }
    }
}
