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
import java.util.UUID
import java.util.concurrent.TimeUnit
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Disposable-data offline gates. Compilation is not device, screenshot or ARM64 proof. */
@RunWith(AndroidJUnit4::class)
class OfflineDamagePatternsUiTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[OfflineDamagePatternsModel::class.java]
    private val defense get() = ViewModelProvider(compose.activity)[DefenseModel::class.java]
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000, test); compose.waitForIdle() }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun text(tag: String, value: String) { compose.onNodeWithTag(tag).performScrollTo().performTextReplacement(value) }
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun prepare() {
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
    }
    private fun call(fitId: String?, selected: String? = null, operation: String = "read", arguments: JSONObject = JSONObject(), offset: Long = 0): OfflineDamageResponse {
        val current = EngineRuntime.offlineFeatureState(context, fitId).get(120, TimeUnit.SECONDS).context
        return EngineRuntime.offlineDamagePatterns(context, OfflineDamageRequest(UUID.randomUUID().toString(), current, fitId,
            OfflineDamageView(offset = offset, selectedPatternId = selected), operation, OfflineFeatureCodec.json(arguments))).get(120, TimeUnit.SECONDS)
            .also { assertTrue(it.error?.message, it.ok) }
    }
    private fun create(name: String): String = EngineRuntime.createEmptyFit(context, "Vexor", name).get(120, TimeUnit.SECONDS)
        .also { assertTrue(it.error?.message, it.isSuccess) }.fits.single().id
    private fun settled() = waitFor { !model.busy && model.state?.context == EngineRuntime.offlineFeatures.value?.context }
    private fun defenseReady(id: String) = waitFor { !defense.loading && defense.details?.revision == fit(id).revision &&
        model.state?.fitId == id && model.state?.fitRevision == fit(id).revision && !model.busy }
    private fun storedPattern(id: String): JSONObject = OfflineFeatureCodec.parse(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
        .getJSONObject("records").getJSONObject(id).getJSONObject("spec").getJSONObject("damage_pattern")

    @Test fun sharedPatternsFractionalCopyDraftDeleteUndoAndFreshProcessReopen() {
        prepare()
        val phase = InstrumentationRegistry.getArguments().getString("offline_features_phase")
        val receipt = File(context.noBackupFilesDir, "damage-patterns-test.json")
        if (phase == "damage_patterns_restart") {
            val saved = JSONObject(receipt.readText()); val pattern = saved.getString("pattern")
            for (key in listOf("first", "second")) {
                val state = call(saved.getString(key), pattern).state!!
                assertEquals(pattern, state.selection.patternId); assertEquals(3.0, state.detail!!.values.fields["emAmount"])
                assertEquals(7.0, state.detail.values.fields["thermalAmount"])
                assertEquals(0, state.history.undoCount); assertEquals(0, state.history.redoCount)
            }
            return
        }
        assertEquals("damage_patterns_prepare", phase)
        val prefix = "Damage UI ${System.nanoTime()}"; val first = create("$prefix first"); val second = create("$prefix second")
        EngineRuntime.selectFit(context, first).get(30, TimeUnit.SECONDS)
        click("damage-patterns-open"); settled(); text("damage-patterns-search", "Conflagration"); settled()
        click("damage-pattern-select-damage:builtin:-17"); settled()
        compose.onNodeWithTag("damage-pattern-readonly").assertExists()
        assertEquals(7.7, model.detail!!.values.fields["emAmount"]); assertTrue(model.detail!!.values.fields["kineticAmount"] is Long)
        click("damage-pattern-duplicate"); text("damage-pattern-name", "$prefix shared"); click("damage-pattern-save"); settled()
        val pattern = model.detail!!.entry.id
        assertEquals(7.7, model.detail!!.values.fields["emAmount"]); assertTrue(model.detail!!.values.fields["kineticAmount"] is Long)
        click("damage-pattern-assign"); settled()
        call(second, pattern, "assign", JSONObject().put("pattern_id", pattern).put("revision", model.detail!!.entry.revision).put("fit_revision", fit(second).revision))
        settled(); assertEquals(2L, model.detail!!.entry.boundFitCount)
        val revisions = listOf(first, second).associateWith { fit(it).revision }
        click("damage-pattern-edit")
        listOf("3", "7", "11", "19").forEachIndexed { index, value -> text("damage-pattern-edit-${DAMAGE_PATTERN_FIELDS[index]}", value) }
        click("damage-pattern-save"); settled(); assertTrue(revisions.all { (id, revision) -> fit(id).revision > revision })
        click("damage-pattern-duplicate"); text("damage-pattern-name", "$prefix copy"); click("damage-pattern-save"); settled()
        assertNotEquals(pattern, model.detail!!.entry.id); assertEquals(3.0, model.detail!!.values.fields["emAmount"])
        click("damage-pattern-rename"); text("damage-pattern-name", "$prefix renamed copy"); click("damage-pattern-save"); settled()
        click("damage-pattern-delete"); compose.onNodeWithText("Exactly 0 incoming fit(s)", substring = true).assertExists()
        click("damage-pattern-delete-confirm"); settled(); waitFor { model.detail?.entry?.id == pattern && !model.busy }
        click("damage-pattern-edit"); text("damage-pattern-edit-emAmount", "invalid")
        click("damage-patterns-back"); click("damage-pattern-leave-keep"); click("damage-patterns-open"); settled()
        compose.activityRule.scenario.recreate(); settled(); assertEquals("invalid", model.draft!!.fields[0])
        click("damage-pattern-save"); compose.onNodeWithTag("damage-patterns-error").assertExists(); click("damage-pattern-cancel")
        click("damage-pattern-delete"); compose.onNodeWithText("Exactly 2 incoming fit(s) switch to Uniform and 0 local hardener(s) follow their respective Fit Pattern, across 2 distinct directly affected fit(s).", substring = true).assertExists()
        click("damage-pattern-delete-confirm"); settled()
        assertEquals("damage:builtin:-1", call(first).state!!.selection.patternId)
        assertEquals("damage:builtin:-1", call(second).state!!.selection.patternId)
        click("damage-patterns-undo"); settled()
        assertEquals(pattern, call(first, pattern).state!!.selection.patternId); assertEquals(pattern, call(second, pattern).state!!.selection.patternId)
        receipt.writeText(JSONObject().put("first", first).put("second", second).put("pattern", pattern).toString())
    }

    @Test fun defenseDetachIsVisibleWhenCleanAndPreservesInvalidDraftAndSavedRawKinds() {
        prepare(); assertEquals("damage_patterns_defense", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        val id = create("Damage defense ${System.nanoTime()}"); EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        call(id, operation = "reset_uniform", arguments = JSONObject().put("fit_revision", fit(id).revision))
        click("defense-open"); defenseReady(id)
        assertFalse(defense.drafts.getValue(id).dirty)
        compose.onNodeWithTag("defense-detach-anonymous").performScrollTo().assertIsEnabled()
        click("defense-detach-anonymous"); defenseReady(id)
        assertEquals("anonymous", model.state!!.selection.kind)
        DAMAGE_PATTERN_FIELDS.forEach { assertEquals(25L, storedPattern(id).get(it)) }
        click("defense-reset-uniform"); defenseReady(id)
        val raw = JSONObject().put("emAmount", -0.0).put("thermalAmount", 1.0).put("kineticAmount", 2.0).put("explosiveAmount", 3.0)
        val entry = call(id, operation = "create", arguments = JSONObject().put("name", "Signed zero ${System.nanoTime()}").put("values", raw)).state!!.detail!!.entry
        call(id, entry.id, "assign", JSONObject().put("pattern_id", entry.id).put("revision", entry.revision).put("fit_revision", fit(id).revision))
        defenseReady(id); text("defense-input-em", "not valid"); text("defense-input-thermal", "007.000")
        val beforeText = defense.drafts.getValue(id).text.toMap()
        compose.onNodeWithTag("defense-apply").performScrollTo().assertIsNotEnabled()
        compose.onNodeWithTag("defense-detach-anonymous").performScrollTo().assertIsEnabled()
        click("defense-detach-anonymous"); defenseReady(id)
        assertEquals("anonymous", model.state!!.selection.kind); assertEquals(beforeText, defense.drafts.getValue(id).text.toMap())
        assertTrue(defense.drafts.getValue(id).dirty); assertTrue(defense.drafts.getValue(id).conflict)
        assertEquals((-0.0).toBits(), (storedPattern(id).get("emAmount") as Double).toBits())
        assertEquals(1.0, storedPattern(id).get("thermalAmount"))
        val generation = model.state!!.context.generation
        click("defense-reset"); assertFalse(defense.drafts.getValue(id).dirty)
        assertEquals(generation, model.state!!.context.generation); assertEquals("anonymous", model.state!!.selection.kind)
        text("defense-input-em", "42"); click("defense-reset-uniform"); defenseReady(id)
        assertEquals("damage:builtin:-1", model.state!!.selection.patternId); assertEquals("42", defense.drafts.getValue(id).text["em"])
        click("defense-reset"); text("defense-input-em", "3"); click("defense-apply"); defenseReady(id)
        assertEquals("anonymous", model.state!!.selection.kind); assertEquals(3.0, storedPattern(id).get("emAmount"))
    }

    @Test fun libraryWithoutOpenFitReachesSourceOrderedBuiltinsAndPersistsUnassignedZero() {
        prepare(); assertEquals("damage_patterns_library", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        EngineRuntime.navigate(context) { it.copy(openIds = emptyList(), activeId = null) }.get(30, TimeUnit.SECONDS)
        click("damage-patterns-open"); settled(); assertEquals("no_fit", model.state!!.selection.kind)
        val ids = mutableListOf<String>(); var offset = 0L
        do {
            val page = call(null, offset = offset).state!!; ids.addAll(page.entries.filter { it.kind == "builtin" }.map { it.id }); offset += 50
        } while (offset < page.total)
        assertEquals((1..118).map { "damage:builtin:-$it" }, ids)
        click("damage-pattern-create"); text("damage-pattern-name", "Cancelled damage ${System.nanoTime()}"); click("damage-pattern-cancel")
        assertFalse(model.dirty)
        click("damage-pattern-create"); text("damage-pattern-name", "Zero library ${System.nanoTime()}")
        click("damage-pattern-save"); settled(); assertFalse(model.detail!!.entry.assignable)
        assertEquals("zero_total", model.detail!!.entry.unassignableReason)
        DAMAGE_PATTERN_FIELDS.forEach { assertEquals(0.0, model.detail!!.values.fields[it]) }
        compose.onNodeWithTag("damage-pattern-unassignable").performScrollTo().assertExists()
        compose.onNodeWithTag("damage-pattern-assign").assertDoesNotExist()
        click("damage-pattern-delete"); click("damage-pattern-delete-confirm"); settled()
        assertNull(model.detail); assertEquals("no_fit", model.state!!.selection.kind)
    }
    @Test fun selectedItemAppliesIncomingOnlyAndKeepsUnrelatedLibraryDraft() {
        prepare(); assertEquals("selected_item_damage", InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        val id = create("Selected item UI ${System.nanoTime()}"); EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS)
        val beforeModules = fit(id).modules; val beforeRecent = EngineRuntime.recent.value
        click("damage-patterns-open"); settled(); click("damage-pattern-create")
        text("damage-pattern-name", "Keep unrelated draft"); text("damage-pattern-edit-emAmount", "invalid")
        val draft = model.draft
        click("damage-patterns-back"); click("damage-pattern-leave-keep")
        click("equipment-open"); waitFor { ViewModelProvider(compose.activity)[EquipmentModel::class.java].catalog != null }
        text("equipment-search", "Scourge Light Missile"); click("equipment-search-submit")
        waitFor { !ViewModelProvider(compose.activity)[EquipmentModel::class.java].busy }
        click("equipment-item-210")
        waitFor { compose.onAllNodesWithTag("equipment-apply-damage").fetchSemanticsNodes().isNotEmpty() }
        compose.onNodeWithTag("equipment-damage-draft-kept").assertExists()
        val beforeEpoch = EngineRuntime.featureEpoch.value
        click("equipment-apply-damage")
        waitFor { EngineRuntime.featureEpoch.value > beforeEpoch }
        waitFor { compose.onAllNodesWithTag("equipment-damage-message").fetchSemanticsNodes().isNotEmpty() }
        val applied = call(id, SELECTED_AMMO_PATTERN_ID).state!!
        assertEquals(SELECTED_AMMO_PATTERN_ID, applied.selection.patternId)
        assertEquals("selected_ammo", applied.detail!!.entry.kind)
        assertEquals(83.0, applied.detail.values.fields["kineticAmount"])
        assertTrue(applied.detail.values.fields["emAmount"] is Long)
        assertEquals(beforeModules, fit(id).modules); assertEquals(beforeRecent, EngineRuntime.recent.value)
        assertSame(draft, model.draft); assertEquals("invalid", model.draft!!.fields[0])
        val generation = applied.context.generation
        click("equipment-apply-damage")
        waitFor { compose.onAllNodesWithText("No saved values changed.", substring = true).fetchSemanticsNodes().isNotEmpty() }
        assertEquals(generation, call(id).state!!.context.generation)
        click("equipment-back"); click("equipment-back"); click("equipment-back")
        click("damage-patterns-open"); settled(); assertSame(draft, model.draft)
        click("damage-pattern-cancel"); text("damage-patterns-search", "Selected Ammo"); settled()
        click("damage-pattern-select-$SELECTED_AMMO_PATTERN_ID"); settled()
        for (tag in listOf("damage-pattern-duplicate", "damage-pattern-edit", "damage-pattern-rename", "damage-pattern-delete"))
            compose.onNodeWithTag(tag).assertDoesNotExist()
        assertEquals(SELECTED_AMMO_PATTERN_ID, model.detail!!.entry.id)
    }
}
