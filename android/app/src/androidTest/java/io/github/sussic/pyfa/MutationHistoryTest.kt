package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.database.sqlite.SQLiteDatabase
import android.os.ParcelFileDescriptor
import android.os.Process
import android.provider.Settings
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import io.github.sussic.pyfa.ModuleTestJson.array
import io.github.sussic.pyfa.ModuleTestJson.compare
import io.github.sussic.pyfa.ModuleTestJson.obj
import io.github.sussic.pyfa.ModuleTestJson.typed

/** Every remaining original-command case reverses through the activity controls. */
@RunWith(AndroidJUnit4::class)
@OptIn(ExperimentalTestApi::class)
class MutationHistoryTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[EditHistoryModel::class.java]
    private val cargo get() = ViewModelProvider(compose.activity)[CargoEditorModel::class.java]
    private lateinit var fixture: JSONObject
    private lateinit var fixtureHash: String
    private lateinit var itemNames: Map<Int, String>
    private lateinit var itemSortKeys: Map<Int, Pair<String, String>>
    private fun fits() = EngineRuntime.library.value
    private fun fit(id: String) = fits().single { it.id == id }
    private fun sync() { compose.mainClock.advanceTimeByFrame(); compose.waitForIdle() }
    private fun waitFor(predicate: () -> Boolean) { compose.waitUntil(90_000, predicate); sync() }
    private fun click(tag: String) { sync(); compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed().performClick(); sync() }
    private fun send(operation: BridgeOperation, ids: List<String> = emptyList()) =
        EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(180, TimeUnit.SECONDS).also {
            assertTrue(it.error?.message, it.isSuccess)
        }
    private fun history(id: String) = EngineRuntime.editHistory(context, id).get(120, TimeUnit.SECONDS)
    private fun counts(id: String) = history(id).let { obj("undo_count" to it.undoCount, "redo_count" to it.redoCount,
        "can_undo" to (it.undoCount > 0), "can_redo" to (it.redoCount > 0)) }
    private fun ready(id: String) = waitFor { !model.loading && !model.editing && model.options?.fitId == id && model.options?.revision == fit(id).revision }
    private fun select(id: String) { EngineRuntime.selectFit(context, id).get(30, TimeUnit.SECONDS); ready(id) }
    private fun reverse(id: String, redo: Boolean) {
        ready(id); val revision = fit(id).revision
        click(if (redo) "history-redo" else "history-undo")
        waitFor { fit(id).revision > revision && !model.loading && !model.editing && model.options?.revision == fit(id).revision }
        assertNull(model.error)
    }
    private fun library() = typed(array(fits().map(ModuleTestJson::fit)))
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(180, TimeUnit.SECONDS))
    private fun screenshot(name: String, tag: String = "history-undo") {
        compose.onNodeWithTag(tag).performScrollTo().assertIsDisplayed(); sync()
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        automation.waitForIdle(500, 10_000)
        ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand(
            "screencap -p /sdcard/Download/pyfa-b092-$name.png")).use { it.readBytes() }
    }
    private fun retain(value: JSONObject, phase: String) {
        val descriptors = InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommandRw(
            "dd of=/sdcard/Download/pyfa-b092-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(value.toString(2).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }
    private fun fixtureCase(name: String): JSONObject = fixture.getJSONArray("cases").let { rows ->
        (0 until rows.length()).map(rows::getJSONObject).single { it.getString("name") == name }
    }
    // IDs come from independently exported arguments; assert the resulting names
    // below, rather than silently accepting a mismatched fixture item.
    private fun cargoId(name: String): Int = when (name) {
        "Antimatter Charge M" -> fixtureCase("cargo-add").getJSONObject("arguments").getInt("item_id")
        "Iron Charge M" -> fixtureCase("cargo-selected-zero").getJSONObject("arguments").getJSONArray("item_ids").getInt(1)
        "Damage Control II" -> fixtureCase("cargo-variation").getJSONObject("arguments").getInt("main_item_id")
        "200mm Railgun II" -> fixtureCase("transfer-from-False").getJSONObject("arguments").getInt("item_id")
        else -> error("Missing independent cargo fixture ID: $name")
    }
    private fun create(spec: JSONObject): String {
        val copied = JSONObject(spec.toString()); copied.remove("ignore_restrictions"); copied.remove("cargo")
        copied.put("implants", JSONArray())
        copied.put("modules", array(spec.getJSONArray("modules").let { rows ->
            (0 until rows.length()).map(rows::getJSONObject).filter { !it.has("empty_slot") }
        }))
        val id = send(BridgeOperation.CreateFit(BridgeCodec.decodeFitSpec(copied))).fits.single().id
        send(BridgeOperation.SetFitRestrictions(id, false), listOf(id))
        assertEquals(0, history(id).undoCount)
        spec.optJSONArray("cargo")?.let { rows -> for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            send(BridgeOperation.AddCargo(id, cargoId(row.getString("name")), row.getLong("amount")), listOf(id))
        } }
        val implants = spec.getJSONArray("implants")
        for (i in 0 until implants.length()) {
            val row = implants.getJSONObject(i)
            send(BridgeOperation.AddImplant(id, row.getString("name"), row.getBoolean("active")), listOf(id))
        }
        return id
    }
    private fun operation(id: String, source: String?, row: JSONObject): BridgeOperation {
        val a = row.getJSONObject("arguments")
        fun ids() = a.getJSONArray("item_ids").let { (0 until it.length()).map(it::getInt) }
        return when (row.getString("operation")) {
            "rename_fit" -> BridgeOperation.RenameFit(id, a.getString("name"))
            "change_mode" -> BridgeOperation.ChangeMode(id, a.getInt("item_id"))
            "set_subsystem" -> BridgeOperation.SetSubsystem(id, a.getInt("kind"), a.getInt("item_id"))
            "add_cargo" -> BridgeOperation.AddCargo(id, a.getInt("item_id"), a.getLong("quantity"))
            "set_cargo_quantity" -> BridgeOperation.SetCargoQuantity(id, a.getInt("item_id"), a.getLong("quantity"))
            "remove_cargo" -> BridgeOperation.RemoveCargo(id, a.getInt("item_id"), a.getLong("quantity"))
            "set_cargo_quantities" -> BridgeOperation.SetCargoQuantities(id, ids(), a.getLong("quantity"))
            "remove_cargos" -> BridgeOperation.RemoveCargos(id, ids())
            "add_cargo_preset" -> BridgeOperation.AddCargoPreset(id, a.getInt("item_id"))
            "fill_cargo" -> BridgeOperation.FillCargo(id, a.getInt("item_id"), a.getBoolean("from_cargo"))
            "change_cargo_variations" -> BridgeOperation.ChangeCargoVariations(id, a.getInt("main_item_id"), ids(), a.getInt("item_id"))
            "transfer_cargo" -> BridgeOperation.TransferCargo(id, CargoTransferDirection.valueOf(a.getString("direction")),
                a.getJSONArray("positions").let { (0 until it.length()).map(it::getInt) },
                if (a.isNull("item_id")) null else a.getInt("item_id"), a.getBoolean("copy"))
            "add_implant" -> BridgeOperation.AddImplant(id, a.getString("implant"), a.getBoolean("active"))
            "set_implant_active" -> BridgeOperation.SetImplantActive(id, a.getInt("slot"), a.getBoolean("active"))
            "remove_implant" -> BridgeOperation.RemoveImplant(id, a.getInt("slot"))
            "change_variation" -> BridgeOperation.ChangeVariation(id, VariationContext.valueOf(a.getString("context").uppercase()), a.getInt("position"), a.getInt("item_id"))
            "set_skill_level" -> BridgeOperation.SetSkillLevel(id, a.getString("skill"), a.getInt("level"))
            "add_projection" -> BridgeOperation.AddProjection(checkNotNull(source), id, a.getDouble("range_m"), a.getBoolean("active"), a.getInt("amount"))
            "configure_projection" -> BridgeOperation.ConfigureProjection(checkNotNull(source), id, a.getDouble("range_m"), a.getBoolean("active"), a.getInt("amount"))
            "remove_projection" -> BridgeOperation.RemoveProjection(checkNotNull(source), id)
            "add_command" -> BridgeOperation.AddCommand(checkNotNull(source), id, a.getBoolean("active"))
            "set_command_active" -> BridgeOperation.SetCommandActive(checkNotNull(source), id, a.getBoolean("active"))
            "remove_command" -> BridgeOperation.RemoveCommand(checkNotNull(source), id)
            else -> error("Unregistered remaining history operation")
        }
    }
    private fun observation(id: String, linked: String? = null): JSONObject {
        val current = fit(id)
        return obj("name" to current.name, "notes" to EngineRuntime.noteDetails(context, id).get(30, TimeUnit.SECONDS).text,
            "stats" to ModuleTestJson.stats(current), "mode" to EngineRuntime.modeOptions(context, id).get(120, TimeUnit.SECONDS).current,
            "modules" to array(current.modules.filter { it.emptySlot == null }.map { obj("index" to it.index, "name" to it.name, "state" to it.state!!.name, "charge" to it.charge) }),
            "drones" to array(EngineRuntime.variationAdditionDiagnostics(context, id).get(120, TimeUnit.SECONDS).let { raw ->
                val rows = JSONObject(raw).getJSONArray("drones"); (0 until rows.length()).map { index ->
                    val row = rows.getJSONObject(index)
                    obj("name" to itemNames.getValue(row.getInt("id")), "amount" to row.getInt("amount"), "active" to row.getInt("active"))
                }
            }),
            "implants" to array(current.implants.map { obj("name" to it.name, "slot" to it.slot, "active" to it.active) }),
            // Match the original cargo pane's category/group/name order using
            // actual bundled inventory metadata, not the expected fixture order.
            "cargo" to array(EngineRuntime.cargoDetails(context, id).get(120, TimeUnit.SECONDS).cargo
                .sortedWith(compareBy<CargoStack> { itemSortKeys.getValue(it.id).first }
                    .thenBy { itemSortKeys.getValue(it.id).second }.thenBy { it.name })
                .map { obj("name" to it.name, "amount" to it.amount) }),
            "skill_override" to (current.skills["Gunnery"] ?: 5), "recent" to array(EngineRuntime.recent.value),
            "projections" to array(current.projections.map { obj("source_name" to fit(it.sourceId).name, "range_m" to it.rangeM, "active" to it.active, "amount" to it.amount) }),
            "commands" to array(current.commands.map { obj("source_name" to fit(it.sourceId).name, "active" to it.active) }),
            "linked_stats" to linked?.let { ModuleTestJson.stats(fit(it)) })
    }
    private fun compareState(row: JSONObject, step: JSONObject, actual: JSONObject, recent: List<Int>) {
        val wanted = JSONObject(step.getJSONObject("result").toString())
        val op = row.getString("operation")
        val top = if (op in listOf("add_implant", "remove_implant")) emptyList()
            else if (op == "remove_cargo") if (step.getString("action") == "initial") emptyList() else listOf(row.getJSONObject("arguments").getInt("item_id"))
            else wanted.getJSONArray("recent").let { (0 until it.length()).map(it::getInt) }
        wanted.put("recent", array((top + recent.filter { it !in top }).take(20)))
        fun absent(left: JSONObject, right: JSONObject) {
            for (key in listOf("gun_optimal", "gun_falloff")) if (right.getJSONObject(key).isNull("value")) {
                assertTrue(left.getJSONObject(key).isNull("value") || left.getJSONObject(key).getDouble("value") in listOf(0.0, 1.0))
                left.getJSONObject(key).put("value", JSONObject.NULL)
            }
        }
        absent(wanted.getJSONObject("stats"), actual.getJSONObject("stats"))
        if (!wanted.isNull("linked_stats")) absent(wanted.getJSONObject("linked_stats"), actual.getJSONObject("linked_stats"))
        compare(wanted, actual, strict = false)
    }

    @Test fun remainingHistoryReversesAndPersistsOffline() {
        val arguments = InstrumentationRegistry.getArguments()
        val phase = arguments.getString("b092_phase") ?: error("Missing phase")
        val group = arguments.getString("b092_group")!!.toInt(); assertTrue(group in 0..3)
        assertTrue(phase in listOf("prepare", "restored"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(180, TimeUnit.SECONDS)
        val catalog = EngineRuntime.equipmentCatalog(context).get(180, TimeUnit.SECONDS)
        itemNames = catalog.items.associate { it.id to it.name }
        val manifest = JSONObject(context.assets.open("engine/manifest.json").bufferedReader().use { it.readText() })
        val database = File(context.filesDir, "game/eve-${manifest.getString("database_sha256")}.db")
        itemSortKeys = SQLiteDatabase.openDatabase(database.absolutePath, null, SQLiteDatabase.OPEN_READONLY).use { db ->
            db.rawQuery("SELECT t.typeID,c.name,g.name FROM invtypes t JOIN invgroups g ON t.groupID=g.groupID JOIN invcategories c ON g.categoryID=c.categoryID", null).use { cursor ->
                buildMap { while (cursor.moveToNext()) put(cursor.getInt(0), cursor.getString(1) to cursor.getString(2)) }
            }
        }
        val fixtureBytes = InstrumentationRegistry.getInstrumentation().context.assets.open("history-mutations-expected.json").use { it.readBytes() }
        fixtureHash = MessageDigest.getInstance("SHA-256").digest(fixtureBytes).joinToString("") { "%02x".format(it.toInt() and 255) }
        fixture = JSONObject(fixtureBytes.toString(Charsets.UTF_8))
        assertEquals(28, fixture.getJSONArray("cases").length())
        val file = File(context.noBackupFilesDir, "b092-test-expected.json")
        val before = library(); val start = diagnostics(); val recentBefore = array(EngineRuntime.recent.value)
        val cases = JSONArray(); val observations = JSONObject(); val checks = JSONArray()
        val restoredInputs = JSONObject(); val histories = JSONObject()
        val created = JSONArray(); val deleted = JSONArray()
        try {
            if (phase == "prepare") {
                if (group == 0) assertEquals(111, fits().size)
                else {
                    val prior = JSONObject(file.readText(Charsets.UTF_8)); assertEquals(group - 1, prior.getInt("group"))
                    compare(prior.getJSONObject("fits"), before, strict = false)
                }
                for (index in group * 7 until (group + 1) * 7) {
                    val row = fixture.getJSONArray("cases").getJSONObject(index)
                    android.util.Log.i("B09.2", "case=$index ${row.getString("name")}")
                    val id = create(row.getJSONObject("spec")); created.put(id)
                    val source = if (row.isNull("source_spec")) null else create(row.getJSONObject("source_spec")).also(created::put)
                    if (row.getBoolean("setup_link")) {
                        send(if (row.getString("operation").contains("projection")) BridgeOperation.AddProjection(checkNotNull(source), id, 0.0, true, 1)
                            else BridgeOperation.AddCommand(checkNotNull(source), id, true), listOf(checkNotNull(source), id))
                    }
                    select(id); val recent = EngineRuntime.recent.value.toList(); val baseline = history(id).undoCount
                    val sourceHistory = source?.let(::counts); val steps = JSONArray()
                    val expected = row.getJSONArray("steps")
                    for (i in 0 until expected.length()) {
                        val step = expected.getJSONObject(i); val action = step.getString("action"); val revision = fit(id).revision
                        when (action) { "do" -> send(operation(id, source, row), listOfNotNull(id, source)); "undo" -> reverse(id, false); "redo" -> reverse(id, true) }
                        if (action != "initial") assertTrue(fit(id).revision > revision)
                        val actual = observation(id, source); compareState(row, step, actual, recent)
                        val cursor = counts(id)
                        assertEquals(baseline + if (action in listOf("do", "redo")) 1 else 0, history(id).undoCount)
                        assertEquals(if (action == "undo") 1 else 0, history(id).redoCount)
                        if (source != null) compare(checkNotNull(sourceHistory), counts(source))
                        steps.put(obj("action" to action, "result" to typed(actual), "history" to cursor,
                            "revision_before" to revision, "revision_after" to fit(id).revision,
                            "source_history" to sourceHistory))
                    }
                    cases.put(obj("name" to row.getString("name"), "fit_id" to id, "source_id" to source,
                        "baseline_undo" to baseline, "recent_before" to array(recent), "steps" to steps))
                }
                checks.put("original_matrix").put("touch_repeated_reversals").put("single_action_grouping").put("recipient_ownership")
                if (group == 0) {
                    val id = cases.getJSONObject(6).getString("fit_id"); select(id); reverse(id, false)
                    click("cargo-open")
                    waitFor { !cargo.loading && cargo.details?.fitId == id && cargo.details?.revision == fit(id).revision }
                    val selected = listOf(cargoId("Antimatter Charge M"), cargoId("Iron Charge M"))
                    selected.forEach { click("cargo-select-$it") }; assertEquals(selected.toSet(), cargo.selected.toSet())
                    reverse(id, true)
                    waitFor { !cargo.loading && cargo.details?.revision == fit(id).revision }
                    assertTrue(cargo.selected.isEmpty()); assertTrue(cargo.details!!.cargo.isEmpty())
                    observations.put("cargo_selection_after_redo", array(cargo.selected)); screenshot("0-cargo-cleared", "cargo-empty")
                    reverse(id, false); waitFor { !cargo.loading && cargo.details?.revision == fit(id).revision }
                    assertTrue(cargo.selected.isEmpty()); assertEquals(2, cargo.details!!.cargo.size)
                    reverse(id, true); click("cargo-back"); checks.put("cargo_selection_safety")
                }
                if (group == 1) {
                    val row = fixture.getJSONObject("interleaved_recent")
                    val owner = create(row.getJSONObject("spec")); created.put(owner)
                    val other = create(row.getJSONObject("other_spec")); created.put(other)
                    val recent = EngineRuntime.recent.value.toList()
                    val item = row.getInt("item_id"); val otherItem = row.getInt("other_item_id")
                    send(BridgeOperation.AddCargo(other, item, 1), listOf(other))
                    send(BridgeOperation.RemoveCargo(other, item, 1), listOf(other))
                    select(owner)
                    val steps = JSONArray(); val expected = row.getJSONArray("steps")
                    val comparison = obj("operation" to "add_cargo")
                    for (index in 0 until expected.length()) {
                        val step = expected.getJSONObject(index); val action = step.getString("action")
                        when (action) {
                            "do" -> send(BridgeOperation.AddCargo(owner, item, 150), listOf(owner))
                            "undo" -> reverse(owner, false)
                            "other" -> send(BridgeOperation.AddCargo(other, otherItem, 1), listOf(other))
                            "redo" -> reverse(owner, true)
                        }
                        val ownerState = observation(owner); val otherState = observation(other)
                        compareState(comparison, obj("action" to action, "result" to step.getJSONObject("owner")), ownerState, recent)
                        compareState(comparison, obj("action" to action, "result" to step.getJSONObject("other")), otherState, recent)
                        compare(step.getJSONObject("owner_history"), counts(owner))
                        compare(step.getJSONObject("other_history"), counts(other))
                        steps.put(obj("action" to action, "owner" to typed(ownerState), "other" to typed(otherState),
                            "owner_history" to counts(owner), "other_history" to counts(other)))
                    }
                    observations.put("recent_case", obj("owner_id" to owner, "other_id" to other,
                        "recent_before" to array(recent), "steps" to steps))
                    click("cargo-open"); waitFor { !cargo.loading && cargo.details?.fitId == owner }
                    screenshot("1-recent-redone"); click("cargo-back")
                    checks.put("interleaved_recent_repromoted")
                }
                val active = cases.getJSONObject(0).getString("fit_id"); select(active)
                send(BridgeOperation.SetNotes(active, "B09.2 later notes — 保持"), listOf(active)); ready(active)
                reverse(active, false); assertEquals("B09.2 later notes — 保持", EngineRuntime.noteDetails(context, active).get(30, TimeUnit.SECONDS).text)
                screenshot("$group-undone"); reverse(active, true); screenshot("$group-redone")
                val priorCursor = counts(active); compose.activityRule.scenario.recreate(); ready(active)
                compare(priorCursor, counts(active)); screenshot("$group-recreated")
                checks.put("notes_preserved").put("history_recreation")
                if (group == 2) {
                    val picker = ViewModelProvider(compose.activity)[BulkChargeEditorModel::class.java]
                    click("modules-open"); click("modules-bulk")
                    waitFor { !picker.loading && picker.options?.fitId == active }
                    click("bulk-select-0"); assertEquals(setOf(0), picker.selected)
                    reverse(active, false); waitFor { !picker.loading && picker.options?.revision == fit(active).revision }
                    assertTrue(picker.selected.isEmpty()); observations.put("module_selection_after_undo", array(picker.selected.toList()))
                    screenshot("2-transfer-undone"); reverse(active, true); click("bulk-back"); click("modules-back")
                    checks.put("transfer_selection_safety")
                }
                if (group == 3) {
                    val original = cases.getJSONObject(0); val source = original.getString("source_id")
                    val copy = send(BridgeOperation.DuplicateFit(active, "B09.2 independent link copy — Δ"), listOf(active)).fits
                        .single { it.name == "B09.2 independent link copy — Δ" }.id
                    created.put(copy); assertEquals(0, history(copy).undoCount)
                    observations.put("copy_id", copy); observations.put("copy_history", counts(copy))
                    ready(active)
                    val beforeStale = library(); val cursor = counts(active)
                    val rejected = EngineRuntime.request(context, BridgeOperation.Undo(active), mapOf(active to 0L)).get(180, TimeUnit.SECONDS)
                    assertFalse(rejected.isSuccess); assertEquals("REVISION_CONFLICT", rejected.error?.code)
                    compare(beforeStale, library()); compare(cursor, counts(active))
                    observations.put("stale_error_code", rejected.error!!.code)
                    compose.runOnUiThread { model.options = model.options!!.copy(revision = 0); model.apply(context, false) }
                    waitFor { !model.editing && model.error != null }
                    compare(beforeStale, library()); compare(cursor, counts(active)); screenshot("3-stale", "history-error")
                    observations.put("stale_before", beforeStale); observations.put("stale_after", library())
                    observations.put("stale_history_before", cursor); observations.put("stale_history_after", counts(active))
                    click("history-retry"); ready(active)
                    send(BridgeOperation.DeleteFit(source, true), listOf(source)); deleted.put(source); ready(active)
                    assertEquals(0, history(active).undoCount); assertEquals(0, history(active).redoCount)
                    assertTrue(fit(active).projections.isEmpty()); assertTrue(fit(copy).projections.isEmpty())
                    assertFalse(fits().any { it.id == source })
                    observations.put("deleted_source", source); observations.put("recipient_after_delete", typed(observation(active)))
                    observations.put("copy_after_delete", typed(observation(copy)))
                    observations.put("recipient_history_after_delete", counts(active)); observations.put("copy_history_after_delete", counts(copy))
                    screenshot("3-deleted-source")
                    checks.put("copy_history_empty").put("stale_rejected").put("deleted_source_not_revived")
                }
                select(active); EngineRuntime.navigate(context) { it.copy(restore = true) }.get(30, TimeUnit.SECONDS)
                val allIds = fits().map { it.id }; val persisted = JSONObject()
                val tracked = if (group == 0) mutableSetOf<String>() else JSONObject(file.readText(Charsets.UTF_8)).getJSONObject("persisted_states").keys().asSequence().toMutableSet()
                for (i in 0 until created.length()) tracked.add(created.getString(i))
                for (i in 0 until deleted.length()) tracked.remove(deleted.getString(i))
                for (id in tracked) persisted.put(id, typed(observation(id)))
                file.writeText(obj("group" to group, "fits" to library(), "prior" to before, "created_ids" to created,
                    "deleted_ids" to deleted, "all_ids" to array(allIds), "active_id" to active,
                    "recent" to array(EngineRuntime.recent.value), "persisted_states" to persisted).toString(), Charsets.UTF_8)
            } else {
                val expected = JSONObject(file.readText(Charsets.UTF_8)); assertEquals(group, expected.getInt("group"))
                compare(expected.getJSONObject("fits"), library(), strict = false)
                compare(expected.getJSONArray("recent"), array(EngineRuntime.recent.value))
                val persisted = expected.getJSONObject("persisted_states")
                for (id in persisted.keys()) {
                    val state = observation(id)
                    compare(persisted.getJSONObject(id), typed(state), strict = false)
                    restoredInputs.put(id, typed(state))
                }
                for (id in fits().map { it.id }) {
                    select(id); assertEquals(0, history(id).undoCount); assertEquals(0, history(id).redoCount)
                    compose.onNodeWithTag("history-undo").assertIsNotEnabled(); compose.onNodeWithTag("history-redo").assertIsNotEnabled()
                }
                select(expected.getString("active_id")); screenshot("$group-restored")
                checks.put("fresh_process_restore").put("all_session_history_empty").put("all_new_inputs_retained").put("reopen_every_fit")
            }
            val saved = JSONObject(file.readText(Charsets.UTF_8))
            for (id in fits().map { it.id }) histories.put(id, counts(id))
            retain(obj("task" to "B09.2", "group" to group, "phase" to phase, "pid" to Process.myPid(),
                "fixture_sha256" to fixtureHash,
                "runtime_start" to start, "runtime_end" to diagnostics(), "before" to before, "after" to library(),
                "recent_before" to recentBefore, "recent_after" to array(EngineRuntime.recent.value),
                "cases" to cases, "checks" to checks, "observations" to observations, "saved" to saved,
                "histories" to histories, "restored_inputs" to restoredInputs), "$group-$phase")
        } catch (failure: Throwable) {
            ParcelFileDescriptor.AutoCloseInputStream(InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommand(
                "screencap -p /sdcard/Download/pyfa-b092-$group-failure.png")).use { it.readBytes() }
            throw failure
        }
    }
}
