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
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Run rah_seed, force-stop/relaunch without clearing disposable data, then rah_reopen. */
@RunWith(AndroidJUnit4::class)
class ModuleRahPersistenceTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private fun details(id: String) = EngineRuntime.moduleRahDetails(context,id).get(30,TimeUnit.SECONDS)
    private fun fingerprint(value: ModuleRahDetails) = JSONObject().put("fit_pattern",checkNotNull(value.fitPattern.components).display())
        .put("modules",JSONArray(value.modules.map { row -> JSONObject().put("index",row.index).put("object_key",row.objectKey)
            .put("item_id",row.itemId).put("mode",row.mode.wire).put("pattern_id",row.patternId ?: JSONObject.NULL) })).toString()
    private fun stats(id: String) = JSONObject().apply {
        EngineRuntime.library.value.single { it.id == id }.stats.toSortedMap().forEach { (key,stat) ->
            put(key,JSONObject().put("value",stat.value.raw).put("unit",stat.unit))
        }
    }.toString()
    private fun armor(id: String) = listOf("em","thermal","kinetic","explosive").map {
        EngineRuntime.library.value.single { fit -> fit.id == id }.stats.getValue("armor_${it}_resonance").value.numberOrNull()!!
    }
    @Test fun inheritedDisabledAndExplicitBuiltinModesSurviveOrdinaryEditsAndRealRestart() {
        val phase = InstrumentationRegistry.getArguments().getString("offline_features_phase")
        assertTrue("Choose rah_seed or rah_reopen",phase in setOf("rah_seed","rah_reopen"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val prefs = context.getSharedPreferences("rah_qualification",Context.MODE_PRIVATE)
        if (phase == "rah_seed") {
            val rows = JSONArray()
            for ((index,pattern) in listOf(null,RahPattern.Disabled,RahPattern.Builtin(-1)).withIndex()) {
                val response = EngineRuntime.request(context,BridgeOperation.CreateFit(FitSpec("RAH restart $index","Vexor",5,false,
                    DamagePattern(1.0,0.0,0.0,0.0),Security(SystemSecurity.HISEC,0.0),
                    listOf(ModuleSpec("Reactive Armor Hardener",ModuleState.ACTIVE,rahPattern=pattern)),emptyList()))).get(120,TimeUnit.SECONDS)
                assertTrue(response.error?.message,response.isSuccess)
                val id = response.fits.single().id
                assertTrue(EngineRuntime.request(context,BridgeOperation.RenameFit(id,"RAH ordinary edit $index"),
                    mapOf(id to response.fits.single().revision)).get(120,TimeUnit.SECONDS).isSuccess)
                val value = details(id)
                assertEquals(listOf(RahMode.FIT,RahMode.DISABLED,RahMode.BUILTIN)[index],value.modules.single().mode)
                rows.put(JSONObject().put("fit_id",id).put("details",fingerprint(value)).put("stats",stats(id)).put("armor",JSONArray(armor(id))))
            }
            val receipt = JSONObject().put("fits",rows)
                .put("session",EngineRuntime.offlineFeatureState(context,rows.getJSONObject(0).getString("fit_id")).get(30,TimeUnit.SECONDS).context.sessionId)
            assertTrue(prefs.edit().putString("seed",receipt.toString()).commit())
        } else {
            val saved = JSONObject(checkNotNull(prefs.getString("seed",null)) { "Run rah_seed first on disposable app data." })
            val rows = saved.getJSONArray("fits"); val firstId = rows.getJSONObject(0).getString("fit_id")
            val state = EngineRuntime.offlineFeatureState(context,firstId).get(30,TimeUnit.SECONDS)
            assertNotEquals("This gate requires a new process, not Activity recreation",saved.getString("session"),state.context.sessionId)
            for (index in 0 until rows.length()) {
                val row = rows.getJSONObject(index); val id = row.getString("fit_id")
                assertEquals(row.getString("details"),fingerprint(details(id)))
                assertEquals(row.getString("stats"),stats(id))
            }
            val builtinId = rows.getJSONObject(2).getString("fit_id")
            EngineRuntime.selectFit(context,builtinId).get(30,TimeUnit.SECONDS)
            compose.onNodeWithTag("modules-open").performScrollTo().performClick()
            compose.onNodeWithTag("modules-rah").performScrollTo().performClick()
            val model = ViewModelProvider(compose.activity)[ModuleRahModel::class.java]
            compose.waitUntil(120_000) { !model.loading && model.currentDetails?.fitId == builtinId }
            val module = model.currentDetails!!.modules.single()
            assertEquals(-1,module.patternId)
            compose.onNodeWithTag("rah-mode-${module.index}").assertTextEquals("Built-in override: Uniform")
            compose.onNodeWithTag("rah-fit-${module.index}").performScrollTo().performClick()
            compose.waitUntil(120_000) { !model.loading && !model.editing && model.currentDetails?.modules?.singleOrNull()?.mode == RahMode.FIT }
            assertEquals(armor(firstId),armor(builtinId))
        }
    }
}
