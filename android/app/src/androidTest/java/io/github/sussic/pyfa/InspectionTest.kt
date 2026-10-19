package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.provider.Settings
import android.os.ParcelFileDescriptor
import android.os.Process
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import android.util.JsonReader
import android.util.JsonToken
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.TimeUnit
import java.io.File
import java.security.MessageDigest
import java.util.zip.GZIPInputStream
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import io.github.sussic.pyfa.ModuleTestJson.compare
import io.github.sussic.pyfa.ModuleTestJson.obj

/** Focused native transport proof; the complete inspector delivery matrix is separate. */
@RunWith(AndroidJUnit4::class)
class InspectionTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()

    private fun contextSqlReference(expected: JSONObject, actual: JSONObject, selectedMode: Int?) {
        val core = listOf("fit", "modules", "drones", "fighters")
        sqlReference(JSONObject().apply { core.forEach { put(it, expected.get(it)) } },
                     JSONObject().apply { core.forEach { put(it, actual.get(it)) } })
        assertEquals((core + listOf("cargo", "implants", "boosters", "booster_side_effects", "mode")).toSet(),
                     actual.keys().asSequence().toSet())
        val boosterIds = mutableMapOf<Long, Long>()
        for (table in listOf("cargo", "implants", "boosters")) {
            val before = expected.getJSONArray(table); val after = actual.getJSONArray(table)
            assertEquals(before.length(), after.length())
            val ids = mutableSetOf<Long>()
            for (index in 0 until before.length()) {
                val row = before.getJSONObject(index)
                val matches = (0 until after.length()).map { after.getJSONObject(it) }
                    .filter { it.getInt("itemID") == row.getInt("itemID") }
                assertEquals(1, matches.size); val member = matches.single()
                assertTrue(member.getLong("ID") > 0); assertTrue(ids.add(member.getLong("ID")))
                if (table == "boosters") boosterIds[row.getLong("ID")] = member.getLong("ID")
                val translated = JSONObject(wire(row)).put("ID", member.getLong("ID"))
                if (row.has("fitID")) {
                    assertEquals(expected.getJSONArray("fit").getJSONObject(0).getLong("ID"), row.getLong("fitID"))
                    translated.put("fitID", actual.getJSONArray("fit").getJSONObject(0).getLong("ID"))
                }
                compare(translated, member)
            }
        }
        val effects = JSONArray()
        val before = expected.getJSONArray("booster_side_effects")
        for (index in 0 until before.length()) {
            val row = JSONObject(wire(before.getJSONObject(index)))
            row.put("boosterID", checkNotNull(boosterIds[row.getLong("boosterID")]))
            effects.put(row)
        }
        compare(effects, actual.getJSONArray("booster_side_effects"))
        val wantedMode = expected.getJSONArray("mode")
        val storedMode = actual.getJSONArray("mode")
        assertEquals(1, wantedMode.length()); assertEquals(1, storedMode.length())
        val translatedMode = JSONObject(wire(wantedMode.getJSONObject(0)))
        // Original construction can leave the SQL override null while its
        // independently observed mode is the hull default. CreateFit receives
        // that explicit original selection. Prove the same selected item.
        if (translatedMode.isNull("modeID") && !storedMode.getJSONObject(0).isNull("modeID")) {
            assertEquals(checkNotNull(selectedMode), storedMode.getJSONObject(0).getInt("modeID"))
            translatedMode.put("modeID", selectedMode)
        }
        compare(JSONArray().put(translatedMode), storedMode)
    }

    private fun contextRawReference(expected: JSONArray, detail: ItemInspection, originalRoles: JSONObject,
                                    actualRoles: JSONObject, options: InspectionOptions) {
        val rows = JSONArray()
        for (index in 0 until expected.length()) {
            val row = JSONObject(wire(expected.getJSONObject(index)))
            assertEquals(originalRoles.getJSONArray("fit").getJSONObject(0).getLong("ID"), row.getLong("source_fit_id"))
            row.put("source_fit_id", actualRoles.getJSONArray("fit").getJSONObject(0).getLong("ID"))
            row.put("source_fit_key", options.fitId)
            val role = row.remove("source_role")
            if (role == JSONObject.NULL) row.put("source_target", JSONObject.NULL) else {
                role as JSONObject
                val matches = options.targets.filter { it.target.context == role.getString("context") && it.target.itemId == role.getInt("item_id") }
                assertEquals("Original source object has one fitted counterpart", 1, matches.size)
                row.put("source_target", JSONObject(matches.single().target.json()))
                if (!row.isNull("source_id")) {
                    val table = when (role.getString("context")) {
                        "module", "charge" -> "modules"; "drone" -> "drones"; "fighter" -> "fighters"
                        "cargo" -> "cargo"; "implant" -> "implants"; "booster" -> "boosters"
                        else -> error("Unexpected original saved source identity")
                    }
                    fun member(roles: JSONObject): JSONObject {
                        val members = roles.getJSONArray(table)
                        val candidates = (0 until members.length()).map { members.getJSONObject(it) }
                            .filter { it.getInt(if (role.getString("context") == "charge") "chargeID" else "itemID") == role.getInt("item_id") }
                        assertEquals(1, candidates.size); return candidates.single()
                    }
                    val key = if (table in listOf("drones", "fighters")) "groupID" else "ID"
                    assertEquals(member(originalRoles).getLong(key), row.getLong("source_id"))
                    row.put("source_id", member(actualRoles).getLong(key))
                }
            }
            rows.put(row)
        }
        compare(rows, JSONArray(detail.affectors.map(::json)))
    }

    private fun completeContextSlice(slice: Int) {
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val phase = "contexts$slice"
        val report = File(context.filesDir, "c032-$phase-observations.jsonl")
        val saved = File(context.filesDir, "c032-$phase-state.json")
        val requested = InstrumentationRegistry.getArguments().getString("c032_phase", phase)
        val restored = requested != phase
        if (!restored) {
            // The independent context export starts without a sample fit.
            // Seed an authentic empty store before EOS starts, so the automatic
            // Vexor sample cannot warm Item.ABYSSAL_TYPES ahead of its first read.
            val metadata = JSONObject(instrumentation.context.assets.open("inspector-context-metadata-expected.json")
                .bufferedReader().use { it.readText() })
            val database = File(context.noBackupFilesDir, "fits/graph.sqlite3")
            assertFalse("Only a freshly cleared synthetic context group may be seeded", database.exists())
            val empty = obj("format" to 2, "dataset_identity" to metadata.getString("databaseLogicalSha256"),
                "eos_settings" to metadata.getJSONObject("eos_settings"), "sample_id" to JSONObject.NULL,
                "fit_order" to JSONArray(), "records" to JSONObject(), "revisions" to JSONObject(), "modified" to JSONObject())
            if (!Python.isStarted()) Python.start(AndroidPlatform(context.applicationContext))
            val python = Python.getInstance()
            val store = python.getModule("android_bridge.store").callAttr("GraphStore", database.absolutePath)
            val attempt = store.callAttr("prepare", python.getModule("json").callAttr("loads", wire(empty)))
            store.callAttr("write", attempt)
            assertEquals("new", store.callAttr("confirm", attempt).toString())
            store.callAttr("accept", attempt)
        }
        val runtime = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", runtime.getJSONObject("manifest").getString("desktop_source_commit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", runtime.getJSONObject("manifest").getString("database_logical_sha256"))
        assertEquals("pyfa-engine", runtime.getString("android_worker_thread")); assertFalse(runtime.getBoolean("android_main_thread"))
        assertEquals(0, runtime.getJSONArray("desktop_import_attempts").length())
        assertTrue(runtime.getJSONObject("persistence").getBoolean("enabled"))
        if (restored) assertTrue(runtime.getJSONObject("persistence").getBoolean("opened_existing"))
        val itemGolden = JSONObject(instrumentation.context.assets.open("inspector-context-metadata-expected.json").bufferedReader().use { it.readText() })
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", itemGolden.getString("sourceCommit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", itemGolden.getString("databaseLogicalSha256"))
        val itemRows = itemGolden.getJSONArray("items")
        assertEquals(127, itemRows.length())
        val itemMetadata = (0 until itemRows.length()).map { itemRows.getJSONObject(it) }.associateBy { it.getInt("item_id") }
        assertEquals(127, itemMetadata.size)
        assertTrue(requested in listOf(phase, "$phase-restored1", "$phase-restored2"))
        val state = if (restored) JSONObject(saved.readText()) else obj("pids" to JSONArray(), "fits" to JSONObject())
        val pids = state.getJSONArray("pids")
        assertEquals(if (!restored) 0 else if (requested.endsWith("1")) 1 else 2, pids.length())
        assertFalse((0 until pids.length()).any { pids.getInt(it) == Process.myPid() }); pids.put(Process.myPid())
        var comparedCases = 0; var observations = 0; var originalStates = 0; var originalTargets = 0
        fun graph() = JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
        runtime.put("context_initial_graph", ModuleTestJson.typed(graph()))
        if (!restored) {
            assertTrue(runtime.getJSONObject("persistence").getBoolean("opened_existing"))
            assertTrue(EngineRuntime.library.value.isEmpty())
            assertEquals(0, graph().getJSONObject("records").length())
        }
        fun send(operation: BridgeOperation, id: String? = null): BridgeResponse {
            val revisions = if (id == null) emptyMap() else mapOf(id to EngineRuntime.library.value.single { it.id == id }.revision)
            val response = EngineRuntime.request(context, operation, revisions).get(120, TimeUnit.SECONDS)
            assertTrue(response.error?.message, response.isSuccess); return response
        }
        report.bufferedWriter(Charsets.UTF_8).use { output ->
            fun originalState(expected: JSONObject) {
                originalStates++; originalTargets += expected.getJSONArray("targets").length()
            }
            fun observe(caseIndex: Int, label: String, expected: JSONObject, id: String) {
                val before = graph()
                val roles = JSONObject(EngineRuntime.inspectionSqlRoles(context, id, true).get(120, TimeUnit.SECONDS))
                val modes = expected.getJSONArray("targets").let { targets ->
                    (0 until targets.length()).map { targets.getJSONObject(it) }.filter { it.getString("context") == "mode" }
                }
                assertTrue(modes.size <= 1)
                contextSqlReference(expected.getJSONObject("roles"), roles, modes.singleOrNull()?.getInt("item_id"))
                val options = EngineRuntime.inspectionOptions(context, id).get(120, TimeUnit.SECONDS)
                val remaining = options.targets.toMutableList(); val targets = JSONArray()
                val wanted = expected.getJSONArray("targets")
                for (index in 0 until wanted.length()) {
                    val row = wanted.getJSONObject(index); val family = row.getString("context"); val itemId = row.getInt("item_id")
                    val selection = if (family == "base") InspectionTarget("base", null, itemId) else {
                        val matches = remaining.filter { it.target.context == family && it.target.itemId == itemId }
                        assertEquals(1, matches.size); remaining.remove(matches.single()); matches.single().target
                    }
                    val detail = EngineRuntime.inspectionDetails(context, id, selection).get(120, TimeUnit.SECONDS)
                    assertEquals(selection, detail.target)
                    reference(obj("expected" to row.getJSONObject("attributes"), "equipment" to row.get("equipment")), detail)
                    treeReference(row.getJSONObject("affector_views"), detail)
                    propertyReference(row.getJSONArray("properties"), detail, expected.getJSONObject("roles"), roles)
                    contextRawReference(row.getJSONArray("affectors"), detail, expected.getJSONObject("roles"), roles, options)
                    contextItemMetadata(itemMetadata.getValue(itemId), detail)
                    targets.put(ModuleTestJson.typed(protocol(detail)))
                }
                assertTrue("Every fitted context target compared", remaining.isEmpty())
                compare(before, graph())
                output.write(wire(obj("case_index" to caseIndex, "observation" to label, "fit_id" to id,
                    "pid" to Process.myPid(), "sql_roles" to roles, "graph" to ModuleTestJson.typed(before), "targets" to targets)) + "\n")
                output.flush(); observations++
            }
            val header = JSONObject(); var globalIndex = 0
            JsonReader(GZIPInputStream(instrumentation.context.assets.open("inspector-contexts-expected.bin")).bufferedReader()).use { reader ->
                reader.beginObject()
                while (reader.hasNext()) {
                    val key = reader.nextName()
                    if (key != "cases") { assertFalse(header.has(key)); header.put(key, readExpected(reader)); continue }
                    reader.beginArray()
                    while (reader.hasNext()) {
                        val caseIndex = globalIndex++
                        val belongs = if (slice == 0) caseIndex < 8 else caseIndex in (8 + (slice - 1) * 25) until minOf(107, 8 + slice * 25)
                        if (!belongs) { reader.skipValue(); continue }
                        val case = readExpected(reader) as JSONObject; val family = case.getString("family")
                        val states = case.getJSONArray("states"); val initial = states.getJSONObject(1)
                        val spec = case.getJSONObject("spec"); val fitMap = state.getJSONObject("fits")
                        if (comparedCases == 0 && (slice > 0 || restored)) {
                            // The original sequential reference has already read
                            // base-item properties before these cases. Match its
                            // process-local Item cache without altering fit data.
                            val targets = states.getJSONObject(0).getJSONArray("targets")
                            val ship = (0 until targets.length()).map { targets.getJSONObject(it) }.single { it.getString("context") == "ship" }
                            val before = graph()
                            val base = EngineRuntime.inspectionDetails(context, null,
                                InspectionTarget("base", null, ship.getInt("item_id"))).get(120, TimeUnit.SECONDS)
                            assertEquals(ship.getInt("item_id"), JSONObject(wire(json(base.item))).getInt("id"))
                            compare(before, graph())
                        }
                        if (restored) {
                            val id = fitMap.getString(caseIndex.toString())
                            observe(caseIndex, requested, states.getJSONObject(states.length() - 1).getJSONObject("replayed"), id)
                            assertEquals(0, EngineRuntime.editHistory(context, id).get(120, TimeUnit.SECONDS).undoCount)
                            assertEquals(0, EngineRuntime.editHistory(context, id).get(120, TimeUnit.SECONDS).redoCount)
                            comparedCases++; continue
                        }
                        val input = JSONObject(wire(spec)); input.remove("cargo"); input.remove("ignore_restrictions")
                        input.put("implants", JSONArray()).put("boosters", JSONArray())
                        val id = send(BridgeOperation.CreateFit(BridgeCodec.decodeFitSpec(wire(input)))).fits.single().id
                        fitMap.put(caseIndex.toString(), id)
                        val fitted = states.getJSONObject(0).getJSONArray("targets")
                        for (index in 0 until fitted.length()) {
                            val target = fitted.getJSONObject(index)
                            when (target.getString("context")) {
                                "cargo" -> {
                                    val position = (0 until spec.getJSONArray("cargo").length()).first { spec.getJSONArray("cargo").getJSONObject(it).getString("name") == target.getJSONArray("properties").let { props ->
                                        (0 until props.length()).map { props.getJSONObject(it).getJSONObject("contract") }.first { it.getString("name") == "item" }.getJSONObject("value").getString("name") } }
                                    send(BridgeOperation.AddCargo(id, target.getInt("item_id"), spec.getJSONArray("cargo").getJSONObject(position).getLong("amount")), id)
                                }
                                "implant" -> send(BridgeOperation.AddImplant(id, spec.getJSONArray("implants").getJSONObject(0).getString("name")), id)
                                "booster" -> send(BridgeOperation.AddBooster(id, target.getInt("item_id")), id)
                            }
                        }
                        observe(caseIndex, "construction", states.getJSONObject(0), id); originalState(states.getJSONObject(0))
                        if (family == "booster") send(BridgeOperation.SetBoosterActive(id, 0, true), id)
                        observe(caseIndex, "initial", initial, id); originalState(initial)
                        var edited: JSONObject? = null; var removed: InspectionTarget? = null
                        for (index in 2 until states.length()) {
                            val expected = states.getJSONObject(index); val action = expected.getJSONObject("action"); val kind = action.getString("kind")
                            if (kind.startsWith("reverse")) {
                                if (kind == "reverse_remove" && family == "booster") {
                                    send(BridgeOperation.SetBoosterActive(id, 0, true), id)
                                } else {
                                    send(BridgeOperation.Undo(id), id)
                                }
                                observe(caseIndex, kind, if (kind == "reverse_remove" && family == "booster") expected else expected.getJSONObject("replayed"), id); originalState(expected)
                                if (!(kind == "reverse_remove" && family == "booster")) {
                                    send(BridgeOperation.Redo(id), id); observe(caseIndex, "$kind-redo", checkNotNull(edited).getJSONObject("replayed"), id)
                                    send(BridgeOperation.Undo(id), id); observe(caseIndex, "$kind-undo", expected.getJSONObject("replayed"), id)
                                }
                                continue
                            }
                            if (kind == "recreated") {
                                val first = initial.getJSONArray("targets")
                                val booster = (0 until first.length()).map { first.getJSONObject(it) }.single { it.getString("context") == "booster" }
                                send(BridgeOperation.AddBooster(id, booster.getInt("item_id")), id)
                                val recreated = EngineRuntime.inspectionOptions(context, id).get(120, TimeUnit.SECONDS).targets.single { it.target.context == "booster" }.target
                                assertNotEquals(checkNotNull(removed).objectKey, recreated.objectKey)
                                try { EngineRuntime.inspectionDetails(context, id, checkNotNull(removed)).get(120, TimeUnit.SECONDS); fail("Old identity rebound to a recreated booster") }
                                catch (error: java.util.concurrent.ExecutionException) { assertTrue(error.cause?.message.orEmpty().contains("ValueError")) }
                                observe(caseIndex, kind, expected, id); originalState(expected); continue
                            }
                            if (kind.startsWith("remove")) removed = EngineRuntime.inspectionOptions(context, id).get(120, TimeUnit.SECONDS).targets.single {
                                it.target.context == family && (family != "cargo" || it.target.index == action.getInt("index")) }.target
                            val operation: BridgeOperation = when (kind) {
                                "set_mode" -> BridgeOperation.ChangeMode(id, action.getInt("item_id"))
                                "set_cargo_amount" -> BridgeOperation.SetCargoQuantity(id, initial.getJSONArray("targets").getJSONObject(1).getInt("item_id"), action.getLong("amount"))
                                "set_implant_active" -> BridgeOperation.SetImplantActive(id, action.getInt("slot"), action.getBoolean("active"))
                                "set_booster_active" -> BridgeOperation.SetBoosterActive(id, action.getInt("index"), action.getBoolean("active"))
                                "set_booster_side_effect" -> BridgeOperation.SetBoosterSideEffect(id, action.getInt("index"), action.getInt("effect_id"), action.getBoolean("active"))
                                "remove_cargo" -> BridgeOperation.RemoveCargos(id, listOf(checkNotNull(removed).itemId))
                                "remove_implant" -> BridgeOperation.RemoveImplant(id, action.getInt("slot"))
                                "remove_booster" -> BridgeOperation.RemoveBooster(id, action.getInt("index"))
                                else -> error("Unhandled original context state $kind")
                            }
                            send(operation, id); edited = expected
                            observe(caseIndex, kind, expected, id); originalState(expected)
                            if (kind.startsWith("remove")) {
                                try { EngineRuntime.inspectionDetails(context, id, checkNotNull(removed)).get(120, TimeUnit.SECONDS); fail("Removed context target remained valid") }
                                catch (error: java.util.concurrent.ExecutionException) { assertTrue(error.cause?.message.orEmpty().contains("ValueError")) }
                                if (family == "booster") {
                                    send(BridgeOperation.Undo(id), id); observe(caseIndex, "remove-undo", states.getJSONObject(states.length() - 1).getJSONObject("replayed"), id)
                                    assertEquals(removed, EngineRuntime.inspectionOptions(context, id).get(120, TimeUnit.SECONDS).targets.single { it.target.context == family }.target)
                                    send(BridgeOperation.Redo(id), id); observe(caseIndex, "remove-redo", expected.getJSONObject("replayed"), id)
                                }
                            }
                        }
                        val oldIds = EngineRuntime.library.value.map { it.id }.toSet()
                        val copied = send(BridgeOperation.DuplicateFit(id, spec.getString("name")), id)
                        val copyId = copied.fits.map { it.id }.filter { it !in oldIds }.single()
                        val records = graph().getJSONObject("records")
                        val sourceRecord = records.getJSONObject(id); val copyRecord = records.getJSONObject(copyId)
                        val sourceKeys = sourceRecord.getJSONObject("inspection_ids"); val copyKeys = copyRecord.getJSONObject("inspection_ids")
                        assertEquals(sourceKeys.keys().asSequence().toSet(), copyKeys.keys().asSequence().toSet())
                        val originals = mutableSetOf<String>(); val copies = mutableSetOf<String>()
                        sourceKeys.keys().forEach { key ->
                            val left = sourceKeys.getJSONArray(key); val right = copyKeys.getJSONArray(key)
                            assertEquals(left.length(), right.length())
                            for (index in 0 until left.length()) { assertTrue(originals.add(left.getString(index))); assertTrue(copies.add(right.getString(index))) }
                        }
                        assertTrue(originals.intersect(copies).isEmpty())
                        val left = JSONObject(wire(sourceRecord)); val right = JSONObject(wire(copyRecord))
                        left.remove("inspection_ids"); right.remove("inspection_ids"); compare(left, right)
                        observe(caseIndex, "copy", states.getJSONObject(states.length() - 1).getJSONObject("replayed"), copyId)
                        send(BridgeOperation.DeleteFit(copyId, false), copyId)
                        comparedCases++
                    }
                    reader.endArray()
                }
                reader.endObject(); assertEquals(JsonToken.END_DOCUMENT, reader.peek())
            }
            assertEquals(107, globalIndex)
            assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", header.getString("sourceCommit"))
            assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", header.getString("databaseLogicalSha256"))
            compare(header.getJSONObject("eos_settings"), JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS)).getJSONObject("eos_settings"), strict = false)
        }
        assertEquals(if (slice == 0) 8 else if (slice == 4) 24 else 25, comparedCases)
        assertEquals(if (restored) 0 else listOf(48, 239, 175, 175, 168)[slice], originalStates)
        assertEquals(if (restored) 0 else listOf(200, 906, 650, 650, 624)[slice], originalTargets)
        state.put("phase", requested).put("cases", comparedCases).put("observations", observations).put("original_states", originalStates).put("original_targets", originalTargets)
            .put("payload_sha256", fileHash(report)).put("graph", ModuleTestJson.typed(graph()))
            .put("runtime_start", ModuleTestJson.typed(runtime))
            .put("all_fits", ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))))
        saved.writeText(wire(state), Charsets.UTF_8)
    }

    private fun contextItemMetadata(expected: JSONObject, detail: ItemInspection) {
        compare(expected.getJSONArray("effects"), JSONArray(detail.effects.map(::json)))
        val variations = json(detail.variations) as JSONObject
        compare(expected.getJSONArray("variation_columns"), variations.getJSONArray("columns"))
        val members = variations.getJSONArray("rows")
        compare(expected.getJSONArray("variation_ids"), JSONArray((0 until members.length()).map { members.getJSONObject(it).getInt("id") }))
        for (mode in listOf("normal", "raw")) {
            val rows = JSONArray()
            for (member in 0 until members.length()) {
                val row = members.getJSONObject(member)
                assertEquals(row.getInt("id") == detail.target.itemId, row.getBoolean("selected"))
                val cells = JSONArray().put(row.getString("name")); val values = row.getJSONArray("values")
                for (cell in 0 until values.length()) {
                    val value = values.getJSONObject(cell)
                    cells.put(if (value.getBoolean("available")) value.getString(if (mode == "raw") "raw" else "display") else "")
                    if (!value.getBoolean("available")) for (key in listOf("value", "raw", "display")) assertTrue(value.isNull(key))
                }
                val price = row.getJSONObject("price")
                if (!price.getBoolean("available")) for (key in listOf("value", "timestamp", "display")) assertTrue(price.isNull(key))
                cells.put(if (price.getBoolean("available")) price.getString("display") else ""); rows.put(cells)
            }
            compare(expected.getJSONObject("variation_presentation").getJSONObject(mode).getJSONArray("rows"), rows)
        }
    }

    @Test fun completeFittedModesCargoAndImplantsOffline() = completeContextSlice(0)
    @Test fun completeFittedBoosterShapesFirstQuarterOffline() = completeContextSlice(1)
    @Test fun completeFittedBoosterShapesSecondQuarterOffline() = completeContextSlice(2)
    @Test fun completeFittedBoosterShapesThirdQuarterOffline() = completeContextSlice(3)
    @Test fun completeFittedBoosterShapesFourthQuarterOffline() = completeContextSlice(4)

    private fun linkedHeader(kind: String): Pair<JSONObject, Set<String>> {
        val header = JSONObject(); val names = linkedSetOf<String>()
        JsonReader(instrumentation.context.assets.open("inspector-$kind-expected.json").bufferedReader()).use { reader ->
            reader.beginObject()
            while (reader.hasNext()) {
                val name = reader.nextName()
                if (name == "states") {
                    assertTrue(names.isEmpty()); reader.beginObject()
                    while (reader.hasNext()) { assertTrue(names.add(reader.nextName())); reader.skipValue() }
                    reader.endObject()
                } else { assertFalse(header.has(name)); header.put(name, readExpected(reader)) }
            }
            reader.endObject(); assertEquals(JsonToken.END_DOCUMENT, reader.peek())
        }
        return header to names
    }

    private fun linkedState(kind: String, state: String): JSONObject {
        var result: JSONObject? = null
        JsonReader(instrumentation.context.assets.open("inspector-$kind-expected.json").bufferedReader()).use { reader ->
            reader.beginObject()
            while (reader.hasNext()) {
                if (reader.nextName() != "states") { reader.skipValue(); continue }
                reader.beginObject()
                while (reader.hasNext()) {
                    if (reader.nextName() == state) { assertNull(result); result = readExpected(reader) as JSONObject }
                    else reader.skipValue()
                }
                reader.endObject()
            }
            reader.endObject(); assertEquals(JsonToken.END_DOCUMENT, reader.peek())
        }
        return checkNotNull(result) { "Missing original linked state: $state" }
    }

    private fun linkedFixtureHash(kind: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
        instrumentation.context.assets.open("inspector-$kind-expected.json").use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) { val count = input.read(buffer); if (count < 0) break; digest.update(buffer, 0, count) }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    @Test fun everyOriginalLinkedInspectionStateAndHistoryReversalOffline() {
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        fun graph() = JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
        fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
        fun send(operation: BridgeOperation, ids: List<String> = emptyList()): BridgeResponse {
            val result = EngineRuntime.request(context, operation, ids.associateWith { fit(it).revision }).get(120, TimeUnit.SECONDS)
            assertTrue(result.error?.message, result.isSuccess); return result
        }
        fun create(spec: JSONObject): String {
            val input = JSONObject(wire(spec))
            if (input.has("ignore_restrictions")) assertFalse(input.getBoolean("ignore_restrictions"))
            if (input.has("cargo")) assertEquals(0, input.getJSONArray("cargo").length())
            input.remove("ignore_restrictions"); input.remove("cargo")
            return send(BridgeOperation.CreateFit(BridgeCodec.decodeFitSpec(wire(input)))).fits.single().id
        }
        val inherited = graph()
        for ((kind, stateCount) in listOf("projection" to 11, "command" to 19)) {
            val (golden, states) = linkedHeader(kind)
            assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", golden.getString("source_commit"))
            assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", golden.getString("databaseLogicalSha256"))
            val runtime = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
            assertTrue(runtime.getJSONObject("persistence").getBoolean("enabled"))
            assertEquals(golden.getString("source_commit"), runtime.getJSONObject("manifest").getString("desktop_source_commit"))
            assertEquals(golden.getString("databaseLogicalSha256"), runtime.getJSONObject("manifest").getString("database_logical_sha256"))
            compare(golden.getJSONObject("eos_settings"), runtime.getJSONObject("eos_settings"), strict = false)
            assertEquals("decimal", runtime.getJSONObject("eos_settings_numeric_types").getString("root.globalDefaultSpoolupPercentage"))
            assertEquals("pyfa-engine", runtime.getString("android_worker_thread")); assertFalse(runtime.getBoolean("android_main_thread"))
            assertEquals(0, runtime.getJSONArray("desktop_import_attempts").length())
            assertEquals(stateCount, states.size)
            val inputs = golden.getJSONObject("inputs"); val steps = inputs.getJSONArray("steps")
            assertEquals(stateCount - 1, steps.length())
            assertEquals(states, setOf("initial") + (0 until steps.length()).map { steps.getJSONObject(it).getString("name") })
            val source = create(inputs.getJSONObject("source")); val target = create(inputs.getJSONObject("target"))
            val roles = mapOf("source" to source, "target" to target)
            var observationCount = 0; var followed = 0; var projectedFollowed = 0
            val reportFile = File(context.filesDir, "c032-linked-$kind.json")
            reportFile.bufferedWriter(Charsets.UTF_8).use { output ->
            val header = obj("task" to "C03.2", "scope" to "linked-inspection", "kind" to kind, "pid" to Process.myPid(),
                "runtime_start" to runtime, "source_id" to source, "target_id" to target, "fixture_sha256" to linkedFixtureHash(kind))
            output.write(wire(header).dropLast(1)); output.write(",\"observations\":[")
            fun sample(name: String, action: String) {
                Log.i("PyfaC032", "START linked $kind $name $action")
                val before = graph(); val state = linkedState(kind, name)
                if (observationCount > 0) output.write(",")
                output.write(wire(obj("state" to name, "action" to action)).dropLast(1)); output.write(",\"roles\":{")
                for ((roleIndex, roleEntry) in roles.entries.withIndex()) {
                    val (role, id) = roleEntry
                    val expected = state.getJSONObject(role)
                    val expectedStats = JSONObject().apply { expected.keys().forEach { key -> if (key != "inspection") put(key, expected.get(key)) } }
                    val actualStats = JSONObject().apply { fit(id).stats.forEach { (key, stat) -> put(key, obj("value" to stat.value.raw, "unit" to stat.unit)) } }
                    compare(expectedStats, actualStats)
                    val options = EngineRuntime.inspectionOptions(context, id).get(120, TimeUnit.SECONDS)
                    val wanted = expected.getJSONArray("inspection")
                    val counters = mutableMapOf<Pair<String, Int>, Int>()
                    val sourceTargets = mutableSetOf<String>()
                    if (roleIndex > 0) output.write(",")
                    output.write(JSONObject.quote(role) + ":")
                    output.write(wire(obj("fit_id" to id, "revision" to fit(id).revision, "stats" to actualStats)).dropLast(1))
                    output.write(",\"inspection\":[")
                    for (index in 0 until wanted.length()) {
                        val row = wanted.getJSONObject(index); val family = row.getString("context"); val item = row.getInt("item_id")
                        val key = family to item; val rank = counters.getOrDefault(key, 0); counters[key] = rank + 1
                        val selection = if (family == "base") InspectionTarget("base", null, item) else
                            options.targets.filter { it.target.context == family && it.target.itemId == item }.sortedBy { it.target.index }[rank].target
                        if (family != "base") assertNotNull(selection.objectKey)
                        val detail = EngineRuntime.inspectionDetails(context, id, selection, false).get(120, TimeUnit.SECONDS)
                        reference(obj("expected" to row.getJSONObject("attributes"), "equipment" to row.get("equipment")), detail)
                        treeReference(row.getJSONObject("trees"), detail)
                        // Resolve the fitted metadata behind each modifier through the real worker.
                        // Skill navigation belongs to C06; those sources have no fitted target.
                        for (value in detail.affectors) {
                            val affector = json(value) as JSONObject
                            if (affector.isNull("source_target")) continue
                            assertFalse("A fitted modifier must identify its saved owner", affector.isNull("source_fit_key"))
                            val owner = affector.getString("source_fit_key"); assertTrue(owner in roles.values)
                            val selected = affector.getJSONObject("source_target")
                            val next = InspectionTarget(selected.getString("context"), selected.getInt("index"), selected.getInt("item_id"), selected.getString("object_key"))
                            if (!sourceTargets.add(owner + ":" + next.json())) continue
                            val resolved = EngineRuntime.inspectionDetails(context, owner, next, false).get(120, TimeUnit.SECONDS)
                            assertEquals(owner, resolved.fitId); assertEquals(fit(owner).revision, resolved.revision)
                            assertEquals(next, resolved.target); followed++
                            if (owner != id) projectedFollowed++
                        }
                        if (index > 0) output.write(",")
                        output.write(wire(protocol(detail)))
                    }
                    val actualCounts = options.targets.filter { it.target.context in setOf("ship", "module", "charge", "drone", "fighter", "cargo") }
                        .groupingBy { it.target.context to it.target.itemId }.eachCount()
                    assertEquals(counters.filterKeys { it.first != "base" }, actualCounts)
                    output.write("]}")
                }
                compare(ModuleTestJson.typed(before), ModuleTestJson.typed(graph()), strict = false)
                output.write("}}"); output.flush(); observationCount++
                Log.i("PyfaC032", "PASS linked $kind $name $action")
            }
            sample("initial", "initial"); var previous = "initial"
            for (index in 0 until steps.length()) {
                val step = steps.getJSONObject(index); val name = step.getString("name")
                fun indices() = step.getJSONArray("module_indices").let { rows -> (0 until rows.length()).map(rows::getInt) }
                val operation: BridgeOperation = when (step.getString("operation")) {
                    "add" -> if (kind == "projection") BridgeOperation.AddProjection(source, target, if (step.isNull("range_m")) null else step.getDouble("range_m"), step.getBoolean("active"), step.getInt("amount")) else BridgeOperation.AddCommand(source, target)
                    "configure" -> BridgeOperation.ConfigureProjection(source, target, if (step.isNull("range_m")) null else step.getDouble("range_m"), step.getBoolean("active"), step.getInt("amount"))
                    "remove" -> if (kind == "projection") BridgeOperation.RemoveProjection(source, target) else BridgeOperation.RemoveCommand(source, target)
                    "charges" -> BridgeOperation.SetCharges(source, indices(), if (step.isNull("charge")) null else step.getString("charge"))
                    "command_state" -> BridgeOperation.SetCommandActive(source, target, step.getBoolean("active"))
                    "skill" -> BridgeOperation.SetSkillLevel(source, step.getString("skill"), step.getInt("level"))
                    "implant_add" -> BridgeOperation.AddImplant(source, step.getString("implant"))
                    "implant_state" -> BridgeOperation.SetImplantActive(source, step.getInt("slot"), step.getBoolean("active"))
                    "implant_remove" -> BridgeOperation.RemoveImplant(source, step.getInt("slot"))
                    "module_state" -> BridgeOperation.SetModuleStates(source, indices(), ModuleState.valueOf(step.getString("state")))
                    else -> error("Unrecognized original linked operation")
                }
                val linked = step.getString("operation") in setOf("add", "configure", "remove", "command_state")
                val owner = if (linked) target else source
                send(operation, if (linked) listOf(source, target) else listOf(source)); sample(name, "edit")
                send(BridgeOperation.Undo(owner), listOf(owner)); sample(previous, "undo")
                send(BridgeOperation.Redo(owner), listOf(owner)); sample(name, "redo")
                previous = name
            }
            assertEquals(1 + 3 * steps.length(), observationCount); assertTrue(followed > 0); assertTrue(projectedFollowed > 0)
            val finalGraph = graph()
            for (field in listOf("records", "revisions", "modified")) {
                val old = inherited.getJSONObject(field)
                for (id in old.keys()) compare(ModuleTestJson.typed(old.get(id)), ModuleTestJson.typed(finalGraph.getJSONObject(field).get(id)), strict = false)
            }
            output.write("],")
            output.write(wire(obj("followed_sources" to followed, "followed_projected_sources" to projectedFollowed,
                "graph" to ModuleTestJson.typed(finalGraph))).drop(1))
            }
            val descriptors = instrumentation.uiAutomation.executeShellCommandRw("dd of=/sdcard/Download/pyfa-c032-linked-$kind.json")
            ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
                ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { destination -> reportFile.inputStream().use { it.copyTo(destination) } }; completion.readBytes()
            }
        }
    }

    @Test fun repeatedModuleTargetsFollowReorderAndRejectRemovalOffline() {
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val bytes = instrumentation.context.assets.open("inspector-attributes-expected.json").use { it.readBytes() }
        val golden = JSONObject(bytes.toString(Charsets.UTF_8))
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", golden.getString("sourceCommit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", golden.getString("databaseLogicalSha256"))
        val case = golden.getJSONArray("cases").getJSONObject(0)
        val phase = InstrumentationRegistry.getArguments().getString("c032_identity_phase")
        assertTrue(phase == null || phase in listOf("prepare", "restored1", "restored2"))
        val stateFile = File(context.filesDir, "c032-inspection-identity.json")
        val start = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        if (phase != null) assertTrue(start.getJSONObject("persistence").getBoolean("enabled"))
        if (phase == "restored1" || phase == "restored2") {
            assertTrue(start.getJSONObject("persistence").getBoolean("opened_existing"))
            val saved = JSONObject(stateFile.readText(Charsets.UTF_8))
            assertEquals(if (phase == "restored1") "prepare" else "restored1", saved.getString("last_phase"))
            val previousPids = saved.getJSONArray("pids")
            assertEquals(if (phase == "restored1") 1 else 2, previousPids.length())
            assertFalse((0 until previousPids.length()).any { previousPids.getInt(it) == Process.myPid() })
            val id = saved.getString("id")
            compare(saved.getJSONObject("graph"), ModuleTestJson.typed(JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))), strict = false)
            compare(saved.getJSONObject("all_fits"), ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))), strict = false)
            val options = EngineRuntime.inspectionOptions(context, id).get(120, TimeUnit.SECONDS)
            val targets = saved.getJSONArray("targets")
            assertEquals(2, targets.length())
            val originals = case.getJSONArray("targets").let { rows ->
                (0 until rows.length()).map { rows.getJSONObject(it) }.filter { it.getString("context") == "module" }
            }
            val observations = JSONArray()
            for (index in 0 until targets.length()) {
                val target = options.targets.single { it.target.context == "module" && it.target.index == index }.target
                val expected = targets.getJSONObject(index)
                assertEquals(expected.getInt("item_id"), target.itemId)
                assertEquals(expected.getString("object_key"), target.objectKey)
                val actual = EngineRuntime.inspectionDetails(context, id, target, false).get(120, TimeUnit.SECONDS)
                reference(originals[index], actual)
                compare(expected.getJSONObject("protocol"), protocol(actual), strict = false)
                observations.put(protocol(actual))
            }
            assertTrue(EngineRuntime.library.value.all { fit -> EngineRuntime.editHistory(context, fit.id).get(120, TimeUnit.SECONDS).let { it.undoCount == 0 && it.redoCount == 0 } })
            compare(saved.getJSONObject("graph"), ModuleTestJson.typed(JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))), strict = false)
            previousPids.put(Process.myPid()); saved.put("last_phase", phase)
            stateFile.writeText(wire(saved), Charsets.UTF_8)
            identityReport(phase, start, saved, observations, bytes)
            return
        }
        val input = JSONObject(wire(case.getJSONObject("spec")))
        if (input.has("ignore_restrictions")) assertFalse(input.getBoolean("ignore_restrictions"))
        if (input.has("cargo")) assertEquals(0, input.getJSONArray("cargo").length())
        input.remove("ignore_restrictions"); input.remove("cargo")
        val created = EngineRuntime.request(context, BridgeOperation.CreateFit(BridgeCodec.decodeFitSpec(wire(input)))).get(120, TimeUnit.SECONDS)
        assertTrue(created.error?.message, created.isSuccess)
        val id = created.fits.single().id
        fun module(index: Int) = EngineRuntime.inspectionOptions(context, id).get(120, TimeUnit.SECONDS)
            .targets.single { it.target.context == "module" && it.target.index == index }.target
        fun edit(operation: BridgeOperation) {
            val revision = EngineRuntime.library.value.single { it.id == id }.revision
            val result = EngineRuntime.request(context, operation, mapOf(id to revision)).get(120, TimeUnit.SECONDS)
            assertTrue(result.error?.message, result.isSuccess)
        }
        fun rejected(target: InspectionTarget) {
            try {
                EngineRuntime.inspectionDetails(context, id, target, false).get(120, TimeUnit.SECONDS)
                fail("Stale target resolved to another repeated module")
            } catch (failure: java.util.concurrent.ExecutionException) {
                assertTrue(failure.cause?.message.orEmpty().contains("ValueError"))
            }
        }
        val first = module(0); val second = module(1)
        assertEquals(first.itemId, second.itemId); assertNotNull(first.objectKey)
        assertNotEquals(first.objectKey, second.objectKey)
        val original = case.getJSONArray("targets").let { rows ->
            (0 until rows.length()).map { rows.getJSONObject(it) }.first { it.getString("context") == "module" }
        }
        reference(original, EngineRuntime.inspectionDetails(context, id, first, false).get(120, TimeUnit.SECONDS))
        edit(BridgeOperation.SwapModules(id, 0, 1))
        assertEquals(first.objectKey, module(1).objectKey); assertEquals(second.objectKey, module(0).objectKey)
        rejected(first)
        reference(original, EngineRuntime.inspectionDetails(context, id, module(1), false).get(120, TimeUnit.SECONDS))
        edit(BridgeOperation.Undo(id))
        assertEquals(first.objectKey, module(0).objectKey); assertEquals(second.objectKey, module(1).objectKey)
        edit(BridgeOperation.Redo(id)); assertEquals(first.objectKey, module(1).objectKey)
        edit(BridgeOperation.RemoveModule(id, 1)); rejected(first)
        assertFalse(EngineRuntime.inspectionOptions(context, id).get(120, TimeUnit.SECONDS).targets.any { it.target.objectKey == first.objectKey })
        edit(BridgeOperation.Undo(id)); assertEquals(first.objectKey, module(1).objectKey)
        reference(original, EngineRuntime.inspectionDetails(context, id, module(1), false).get(120, TimeUnit.SECONDS))
        if (phase == "prepare") {
            // Return to the independent original ordering before persisting both objects.
            edit(BridgeOperation.Undo(id))
            assertEquals(first.objectKey, module(0).objectKey)
            assertEquals(second.objectKey, module(1).objectKey)
            val originals = case.getJSONArray("targets").let { rows ->
                (0 until rows.length()).map { rows.getJSONObject(it) }.filter { it.getString("context") == "module" }
            }
            val targets = JSONArray(); val observations = JSONArray()
            for (index in 0..1) {
                val target = module(index)
                val actual = EngineRuntime.inspectionDetails(context, id, target, false).get(120, TimeUnit.SECONDS)
                reference(originals[index], actual)
                targets.put(obj("index" to index, "item_id" to target.itemId, "object_key" to target.objectKey, "protocol" to protocol(actual)))
                observations.put(protocol(actual))
            }
            val saved = obj("id" to id, "targets" to targets, "pids" to JSONArray(listOf(Process.myPid())), "last_phase" to phase,
                "graph" to ModuleTestJson.typed(JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))),
                "all_fits" to ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))))
            stateFile.writeText(wire(saved), Charsets.UTF_8)
            identityReport(phase, start, saved, observations, bytes)
        }
    }

    private fun identityReport(phase: String, start: JSONObject, saved: JSONObject, observations: JSONArray, fixture: ByteArray) {
        val histories = JSONObject()
        for (fit in EngineRuntime.library.value) {
            val history = EngineRuntime.editHistory(context, fit.id).get(120, TimeUnit.SECONDS)
            histories.put(fit.id, obj("undo_count" to history.undoCount, "redo_count" to history.redoCount))
        }
        val report = obj("task" to "C03.2", "scope" to "repeated-module-identity", "phase" to phase,
            "pid" to Process.myPid(), "runtime_start" to start, "saved" to saved, "observations" to observations,
            "history" to histories,
            "fixture_sha256" to MessageDigest.getInstance("SHA-256").digest(fixture).joinToString("") { "%02x".format(it) })
        val descriptors = instrumentation.uiAutomation.executeShellCommandRw("dd of=/sdcard/Download/pyfa-c032-identity-$phase.json")
        ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
            ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(wire(report).toByteArray(Charsets.UTF_8)) }
            completion.readBytes()
        }
    }

    @Test fun originalGuardDomainsCrossNativeWorkerOffline() {
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val golden = JSONObject(instrumentation.context.assets.open("inspector-guard-domains-expected.json").bufferedReader().use { it.readText() })
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", golden.getString("sourceCommit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", golden.getString("databaseLogicalSha256"))
        val before = EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS)
        val inputs = golden.getJSONArray("inputs"); assertEquals(2793, inputs.length())
        val actual = JSONArray(EngineRuntime.inspectionGuardDomains(context, wire(inputs)).get(120, TimeUnit.SECONDS))
        compare(golden.getJSONArray("results"), actual)
        val forbidden = setOf("misc.py:__getData:40", "misc.py:__getData:62", "misc.py:__getData:64")
        assertEquals(forbidden, golden.getJSONArray("proofs").let { rows ->
            (0 until rows.length()).map { rows.getJSONObject(it).getString("return_id") }.toSet()
        })
        var outputs = 0; var exceptions = 0
        for (index in 0 until actual.length()) {
            val row = actual.getJSONObject(index)
            if (row.isNull("error")) {
                outputs++
                val returns = row.getJSONObject("output").getJSONArray("returns")
                for (path in 0 until returns.length()) assertFalse(returns.getString(path) in forbidden)
            } else {
                exceptions++
                assertTrue(row.isNull("output"))
                assertEquals("TypeError", row.getJSONObject("error").getString("type"))
            }
        }
        assertEquals(1572, outputs); assertEquals(1221, exceptions)
        for (invalid in listOf("{}", "[{\"group\":\"ECM\",\"values\":{},\"expected\":null}]")) {
            try {
                EngineRuntime.inspectionGuardDomains(context, invalid).get(120, TimeUnit.SECONDS)
                fail("Malformed guard input accepted")
            } catch (failure: java.util.concurrent.ExecutionException) {
                assertTrue(failure.cause?.message.orEmpty().contains("ValueError"))
            }
        }
        assertEquals(before, EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
    }

    @Test fun completeEquipmentProbesCrossNativeWorkerOffline() {
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        fun fixture(name: String) = JSONObject(instrumentation.context.assets.open("inspector-$name-expected.json").bufferedReader().use { it.readText() })
        val golden = fixture("equipment-probes")
        val attributes = fixture("attributes")
        val paths = fixture("equipment-paths")
        for (value in listOf(golden, attributes, paths)) {
            assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", value.getString("sourceCommit"))
            assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", value.getString("databaseLogicalSha256"))
            compare(golden.getJSONObject("eos_settings"), value.getJSONObject("eos_settings"))
        }
        val spec = JSONObject(wire(attributes.getJSONArray("cases").getJSONObject(0).getJSONObject("spec")))
        spec.put("name", "Inspector booster duration probes")
        for (family in listOf("modules", "drones", "fighters", "cargo", "environments")) spec.put(family, JSONArray())
        if (spec.has("ignore_restrictions")) assertFalse(spec.getBoolean("ignore_restrictions"))
        assertEquals(0, spec.getJSONArray("cargo").length())
        spec.remove("ignore_restrictions"); spec.remove("cargo")
        val created = EngineRuntime.request(context, BridgeOperation.CreateFit(BridgeCodec.decodeFitSpec(wire(spec)))).get(120, TimeUnit.SECONDS)
        assertTrue(created.error?.message, created.isSuccess)
        val id = created.fits.single().id
        val before = EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS)
        val inputs = JSONObject(wire(golden.getJSONObject("inputs")))
        inputs.remove("booster_duration_unit")
        val expected = JSONObject(wire(golden.getJSONObject("results")))
        for ((family, count) in listOf("legacy" to 35, "conditional" to 58, "boosters" to 311, "columns" to 97)) {
            assertEquals(count, inputs.getJSONArray(family).length())
            assertEquals(count, expected.getJSONArray(family).length())
        }
        for (index in 0 until inputs.getJSONArray("conditional").length()) {
            inputs.getJSONArray("conditional").getJSONObject(index).remove("expected_error")
            expected.getJSONArray("conditional").getJSONObject(index).getJSONObject("input").remove("expected_error")
        }
        val actual = JSONObject(EngineRuntime.inspectionEquipmentProbes(context, id, wire(inputs)).get(120, TimeUnit.SECONDS))
        assertEquals(setOf("definitions", "results"), actual.keys().asSequence().toSet())
        compare(expected, actual.getJSONObject("results"))
        val required = paths.getJSONObject("coverage").getJSONArray("required_return_ids")
        assertEquals(114, required.length())
        val definitions = JSONObject()
        for (index in 0 until required.length()) {
            val name = required.getString(index).substringBeforeLast(":")
            definitions.put(name, definitions.optInt(name) + 1)
        }
        compare(definitions, actual.getJSONObject("definitions"))
        val malformed = JSONObject(wire(inputs))
        malformed.getJSONArray("conditional").getJSONObject(0).put("expected_error", JSONObject.NULL)
        try {
            EngineRuntime.inspectionEquipmentProbes(context, id, wire(malformed)).get(120, TimeUnit.SECONDS)
            fail("Expectation field accepted by input-only diagnostic")
        } catch (failure: java.util.concurrent.ExecutionException) {
            assertTrue(failure.cause?.message.orEmpty().contains("ValueError"))
        }
        assertEquals(before, EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
    }

    @Test fun everyUnitDefinitionMatchesOriginalFormattingOffline() {
        val context = instrumentation.targetContext
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val golden = JSONObject(instrumentation.context.assets.open("inspector-units-expected.json").bufferedReader().use { it.readText() })
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", golden.getString("sourceCommit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", golden.getString("databaseLogicalSha256"))
        val before = EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS)
        val rows = golden.getJSONArray("units"); assertEquals(289, rows.length())
        val inputs = JSONArray((0 until rows.length()).map { index ->
            val row = rows.getJSONObject(index)
            JSONObject().put("unit_id", row.getJSONObject("unit").getInt("id")).put("value", row.get("value"))
        })
        val actual = JSONObject(EngineRuntime.inspectionUnitWitnesses(context, inputs.toString()).get(120, TimeUnit.SECONDS))
        assertEquals(setOf("units", "witnesses"), actual.keys().asSequence().toSet())
        val definitions = (0 until rows.length()).map { rows.getJSONObject(it).getJSONObject("unit") }
            .distinctBy { it.getInt("id") }.sortedBy { it.getInt("id") }
        assertEquals(60, definitions.size)
        compare(JSONArray(definitions), actual.getJSONArray("units"))
        val witnesses = actual.getJSONArray("witnesses"); assertEquals(rows.length(), witnesses.length())
        for (index in 0 until rows.length()) {
            val original = rows.getJSONObject(index); val witness = witnesses.getJSONObject(index)
            assertEquals(setOf("unit", "value", "formatted"), witness.keys().asSequence().toSet())
            compare(original.getJSONObject("unit"), witness.getJSONObject("unit"))
            compare(original.get("value"), witness.get("value"))
            assertEquals("Unit witness $index", original.getString("expected"), witness.getString("formatted"))
        }
        for (invalid in listOf("{}", "[{\"unit_id\":true,\"value\":1}]", "[{\"unit_id\":-1,\"value\":1}]",
            "[{\"unit_id\":1,\"value\":null}]", "[{\"unit_id\":1,\"value\":NaN}]",
            "[{\"unit_id\":1,\"value\":Infinity}]", "[{\"unit_id\":1,\"value\":1,\"expected\":\"fake\"}]")) {
            try {
                EngineRuntime.inspectionUnitWitnesses(context, invalid).get(120, TimeUnit.SECONDS)
                fail("Malformed unit input accepted: $invalid")
            } catch (failure: java.util.concurrent.ExecutionException) {
                assertTrue(failure.cause?.message.orEmpty().contains("ValueError"))
            }
        }
        assertEquals(before, EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
    }
    private val context get() = instrumentation.targetContext
    private fun wire(value: Any): String = when (value) {
        is JSONObject -> value.keys().asSequence().joinToString(",", "{", "}") { JSONObject.quote(it) + ":" + wire(value.get(it)) }
        is JSONArray -> (0 until value.length()).joinToString(",", "[", "]") { wire(value.get(it)) }
        is String -> JSONObject.quote(value)
        else -> value.toString()
    }
    private fun json(value: InspectionValue): Any = when (value) {
        InspectionValue.Absent -> JSONObject.NULL
        is InspectionValue.Scalar -> value.value.raw
        is InspectionValue.Sequence -> JSONArray(value.values.map(::json))
        is InspectionValue.Fields -> JSONObject().apply { value.values.forEach { (key, member) -> put(key, json(member)) } }
    }
    private fun reference(expected: JSONObject, actual: ItemInspection) {
        val precise = JSONArray(actual.attributes.map { row -> obj("name" to row.name, "id" to row.id,
            "current" to row.current.raw, "base" to row.base.raw,
            "unit" to row.unit?.let { obj("id" to it.id, "name" to it.name, "display" to it.display) }) })
        compare(expected.getJSONObject("expected").getJSONArray("precise"), precise)
        val members = actual.attributes.associateBy { it.name }
        for ((mode, order) in listOf("normal" to actual.normal, "raw" to actual.raw)) {
            val rows = JSONArray(order.map { entry ->
                val row = members.getValue(entry.name)
                obj("name" to entry.name, "groups" to JSONArray(entry.groups), "label" to entry.label,
                    "current" to if (mode == "raw") row.rawCurrent else row.displayCurrent,
                    "base" to if (mode == "raw") row.rawBase else row.displayBase)
            })
            compare(expected.getJSONObject("expected").getJSONArray(mode), rows)
        }
        compare(expected.get("equipment"), actual.equipment?.let(::json) ?: JSONObject.NULL)
    }
    private fun protocol(detail: ItemInspection): JSONObject = obj(
        "version" to 1, "fit_id" to detail.fitId, "revision" to detail.revision,
        "selection" to JSONObject(detail.target.json()), "item" to json(detail.item),
        "attributes" to obj("rows" to JSONArray(detail.attributes.map { row -> obj(
            "name" to row.name, "id" to row.id, "label" to row.label, "metadata" to row.metadata,
            "published" to row.published, "current" to row.current.raw, "base" to row.base.raw,
            "raw_current" to row.rawCurrent, "raw_base" to row.rawBase,
            "display_current" to row.displayCurrent, "display_base" to row.displayBase,
            "normal" to row.normal, "unit" to row.unit?.let { obj("id" to it.id, "name" to it.name, "display" to it.display) }) }),
            "normal" to JSONArray(detail.normal.map { obj("name" to it.name, "groups" to JSONArray(it.groups), "label" to it.label) }),
            "raw" to JSONArray(detail.raw.map { obj("name" to it.name, "groups" to JSONArray(it.groups), "label" to it.label) })),
        "effects" to JSONArray(detail.effects.map(::json)), "affectors" to JSONArray(detail.affectors.map(::json)),
        "properties" to JSONArray(detail.properties.map(::json)), "equipment" to detail.equipment?.let(::json),
        "variations" to json(detail.variations), "stack" to json(detail.stack), "affector_views" to json(detail.affectorViews))
    private fun guards(detail: ItemInspection) {
        val good = protocol(detail)
        assertEquals(detail, BridgeCodec.decodeInspection(wire(good)))
        fun rejected(change: (JSONObject) -> Unit) {
            val corrupt = JSONObject(wire(good)); change(corrupt)
            try { BridgeCodec.decodeInspection(wire(corrupt)); fail("Corrupt inspector payload accepted") }
            catch (_: BridgeProtocolException) {}
        }
        rejected { it.put("version", 2) }
        rejected { it.put("revision", 0) }
        rejected { it.put("extra", true) }
        rejected { it.getJSONObject("selection").put("item_id", detail.target.itemId + 1) }
        rejected { it.getJSONObject("attributes").getJSONArray("rows").getJSONObject(0).put("current", "0") }
        rejected { it.getJSONObject("attributes").getJSONArray("rows").getJSONObject(0).put("raw_current", "NaN") }
        rejected { it.getJSONObject("attributes").getJSONArray("raw").remove(0) }
        rejected { it.getJSONObject("affector_views").remove("attribute") }
        val properties = good.getJSONArray("properties")
        val unavailable = (0 until properties.length()).first { !properties.getJSONObject(it).getBoolean("available") }
        rejected { it.getJSONArray("properties").getJSONObject(unavailable).put("display", "0") }
        val displayed = (0 until properties.length()).first { !properties.getJSONObject(it).isNull("display") }
        rejected { it.getJSONArray("properties").getJSONObject(displayed).put("display", "incorrect value") }
        if (detail.effects.isNotEmpty()) {
            rejected { it.getJSONArray("effects").getJSONObject(0).put("types", JSONArray().put("unknown")) }
            rejected { it.getJSONArray("effects").put(it.getJSONArray("effects").getJSONObject(0)) }
            val implemented = (0 until good.getJSONArray("effects").length()).first {
                good.getJSONArray("effects").getJSONObject(it).getBoolean("implemented")
            }
            rejected { it.getJSONArray("effects").getJSONObject(implemented).put("runtime", "unknown") }
        }
        val affectors = good.getJSONArray("affectors")
        val fitted = (0 until affectors.length()).firstOrNull { !affectors.getJSONObject(it).isNull("source_target") }
        if (fitted != null) rejected {
            val row = it.getJSONArray("affectors").getJSONObject(fitted)
            row.getJSONObject("source_target").put("item_id", row.getInt("item_id") + 1)
        }
        val duplicate = wire(good).dropLast(1) + ",\"version\":1}"
        try { BridgeCodec.decodeInspection(duplicate); fail("Duplicate inspector field accepted") }
        catch (_: BridgeProtocolException) {}
    }
    private fun treeReference(expected: JSONObject, detail: ItemInspection) {
        fun flatten(nodes: JSONArray, prefix: List<String> = emptyList()): JSONArray {
            val result = JSONArray()
            for (index in 0 until nodes.length()) {
                val node = nodes.getJSONObject(index)
                val path = prefix + node.getString("label")
                result.put(obj("path" to JSONArray(path), "alternate" to node.get("alternate")))
                val children = flatten(node.getJSONArray("children"), path)
                for (child in 0 until children.length()) result.put(children.get(child))
            }
            return result
        }
        val views = json(detail.affectorViews) as JSONObject
        for (mode in listOf("source", "attribute")) compare(expected.getJSONArray(mode), flatten(views.getJSONArray(mode)))
    }
    private fun readExpected(reader: JsonReader): Any = when (reader.peek()) {
        JsonToken.BEGIN_OBJECT -> JSONObject().apply {
            reader.beginObject()
            while (reader.hasNext()) {
                val name = reader.nextName(); assertFalse("Duplicate expected field", has(name))
                put(name, readExpected(reader))
            }
            reader.endObject()
        }
        JsonToken.BEGIN_ARRAY -> JSONArray().apply {
            reader.beginArray(); while (reader.hasNext()) put(readExpected(reader)); reader.endArray()
        }
        JsonToken.STRING -> reader.nextString()
        JsonToken.BOOLEAN -> reader.nextBoolean()
        JsonToken.NULL -> { reader.nextNull(); JSONObject.NULL }
        JsonToken.NUMBER -> reader.nextString().let { it.toLongOrNull() ?: it.toDouble().also { number -> assertTrue(number.isFinite()) } }
        else -> error("Invalid independent expected JSON")
    }
    private fun sqlReference(expected: JSONObject, actual: JSONObject) {
        val translated = JSONObject(wire(expected))
        val expectedFit = expected.getJSONArray("fit").getJSONObject(0)
        assertEquals(1, actual.getJSONArray("fit").length())
        val fitId = actual.getJSONArray("fit").getJSONObject(0).getLong("ID")
        assertTrue(fitId > 0)
        translated.getJSONArray("fit").getJSONObject(0).put("ID", fitId)
        for (table in listOf("modules", "drones", "fighters")) {
            val before = expected.getJSONArray(table); val after = actual.getJSONArray(table)
            assertEquals(before.length(), after.length())
            val key = if (table == "modules") "ID" else "groupID"
            val ids = mutableSetOf<Long>()
            for (index in 0 until before.length()) {
                val original = before.getJSONObject(index); val row = after.getJSONObject(index)
                assertEquals(expectedFit.getLong("ID"), original.getLong("fitID"))
                assertTrue(row.getLong(key) > 0); assertTrue(ids.add(row.getLong(key)))
                translated.getJSONArray(table).getJSONObject(index).put(key, row.getLong(key)).put("fitID", fitId)
            }
        }
        compare(translated, actual)
    }
    private fun propertyReference(expected: JSONArray, detail: ItemInspection, before: JSONObject, after: JSONObject) {
        val fitted = detail.target.context != "base"
        val originalFit = before.getJSONArray("fit").getJSONObject(0)
        val actualFit = after.getJSONArray("fit").getJSONObject(0)
        fun translate(value: Any): Any = when (value) {
            is JSONObject -> JSONObject().apply {
                val owner = value.optString("object_type") == "Fit"
                if (owner) {
                    assertEquals(originalFit.getLong("ID"), value.getLong("id"))
                    assertEquals(originalFit.getString("name"), value.getString("name"))
                }
                value.keys().forEach { key -> put(key, if (owner && key == "id") actualFit.getLong("ID") else translate(value.get(key))) }
            }
            is JSONArray -> JSONArray((0 until value.length()).map { translate(value.get(it)) })
            else -> value
        }
        val rows = JSONArray()
        for (index in 0 until expected.length()) {
            val row = JSONObject(wire(expected.getJSONObject(index).getJSONObject("contract")))
            val name = row.getString("name")
            if (row.getBoolean("available")) {
                row.put("value", translate(row.get("value")))
                if (fitted && name in listOf("ID", "groupID", "fitID")) {
                    val oldId: Long; val newId: Long
                    if (name == "fitID") {
                        oldId = originalFit.getLong("ID"); newId = actualFit.getLong("ID")
                    } else {
                        val family = detail.target.context
                        val table = when (family) {
                            "module", "charge" -> "modules"; "drone" -> "drones"; "fighter" -> "fighters"
                            "cargo" -> "cargo"; "implant" -> "implants"; "booster" -> "boosters"
                            else -> error("Unexpected saved identity on $family")
                        }
                        val key = if (table in listOf("drones", "fighters")) "groupID" else "ID"
                        val position = checkNotNull(detail.target.index)
                        fun member(roles: JSONObject): JSONObject {
                            val rows = roles.getJSONArray(table)
                            if (family !in listOf("cargo", "implant", "booster")) return rows.getJSONObject(position)
                            val matches = (0 until rows.length()).map { rows.getJSONObject(it) }
                                .filter { it.getInt("itemID") == detail.target.itemId }
                            assertEquals("Unique original context membership", 1, matches.size)
                            return matches.single()
                        }
                        val original = member(before)
                        val actual = member(after)
                        assertEquals(detail.target.itemId, original.getInt(if (family == "charge") "chargeID" else "itemID"))
                        oldId = original.getLong(key); newId = actual.getLong(key)
                    }
                    assertEquals(oldId, row.getLong("value")); assertEquals(oldId.toString(), row.getString("display"))
                    row.put("value", newId).put("display", newId.toString())
                }
            }
            rows.put(row)
        }
        compare(rows, JSONArray(detail.properties.map(::json)))
    }
    @Test fun canonicalAttributesCrossNativeWorkerOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("c032_phase")
        assertTrue(phase in listOf("canonical", "canonical-restored1", "canonical-restored2"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val golden = JSONObject(instrumentation.context.assets.open("inspector-attributes-expected.json").bufferedReader().use { it.readText() })
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", golden.getString("sourceCommit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", golden.getString("databaseLogicalSha256"))
        val cases = golden.getJSONArray("cases")
        assertEquals(152, cases.length())
        if (phase != "canonical") {
            restoreCanonical(checkNotNull(phase), cases)
            return
        }
        val canonicalFile = File(context.filesDir, "c032-canonical-targets.jsonl")
        canonicalFile.writeText("", Charsets.UTF_8)
        val canonicalObservations = File(context.filesDir, "c032-canonical-observations.jsonl")
        canonicalObservations.writeText("", Charsets.UTF_8)
        val canonicalPids = JSONArray(listOf(Process.myPid()))
        val affectorGolden = JSONObject(instrumentation.context.assets.open("inspector-affectors-expected.json").bufferedReader().use { it.readText() })
        assertEquals(golden.getString("sourceCommit"), affectorGolden.getString("sourceCommit"))
        assertEquals(golden.getString("databaseLogicalSha256"), affectorGolden.getString("databaseLogicalSha256"))
        compare(golden.getJSONObject("eos_settings"), affectorGolden.getJSONObject("eos_settings"))
        val affectorCases = affectorGolden.getJSONArray("cases")
        assertEquals(cases.length(), affectorCases.length())
        val identities = JSONObject(instrumentation.context.assets.open("inspector-identities-expected.json").bufferedReader().use { it.readText() })
        assertEquals(golden.getString("sourceCommit"), identities.getString("sourceCommit"))
        assertEquals(golden.getString("databaseLogicalSha256"), identities.getString("databaseLogicalSha256"))
        compare(golden.getJSONObject("eos_settings"), identities.getJSONObject("eos_settings"))
        val identityCases = identities.getJSONArray("cases")
        assertEquals(cases.length(), identityCases.length())
        val paths = JSONObject(instrumentation.context.assets.open("inspector-equipment-paths-expected.json").bufferedReader().use { it.readText() })
        assertEquals(golden.getString("sourceCommit"), paths.getString("sourceCommit"))
        assertEquals(golden.getString("databaseLogicalSha256"), paths.getString("databaseLogicalSha256"))
        compare(golden.getJSONObject("eos_settings"), paths.getJSONObject("eos_settings"))
        val pathCases = paths.getJSONArray("cases"); assertEquals(cases.length(), pathCases.length())
        val requiredReturns = paths.getJSONObject("coverage").getJSONArray("required_return_ids")
        val definitions = JSONObject()
        for (index in 0 until requiredReturns.length()) {
            val name = requiredReturns.getString(index).substringBeforeLast(":")
            definitions.put(name, definitions.optInt(name) + 1)
        }
        assertEquals(114, requiredReturns.length())
        val observedReturns = mutableSetOf<String>()
        var comparedTargets = 0
        var comparedProperties = 0
        // Stream the complete 33 MB independent property fixture one fit at a
        // time; retaining it alongside all attributes is unnecessary test heap.
        JsonReader(instrumentation.context.assets.open("inspector-properties-expected.json").reader()).use { reader ->
            reader.beginObject()
            val propertyHeaders = JSONObject()
            var foundCases = false
            while (reader.hasNext()) {
                val name = reader.nextName()
                if (name == "cases") { foundCases = true; break }
                assertFalse(propertyHeaders.has(name)); propertyHeaders.put(name, readExpected(reader))
            }
            assertTrue(foundCases)
            assertEquals(golden.getString("sourceCommit"), propertyHeaders.getString("sourceCommit"))
            assertEquals(golden.getString("databaseLogicalSha256"), propertyHeaders.getString("databaseLogicalSha256"))
            compare(golden.getJSONObject("eos_settings"), propertyHeaders.getJSONObject("eos_settings"))
            reader.beginArray()
            for (caseIndex in 0 until cases.length()) {
                val case = cases.getJSONObject(caseIndex)
                val affectorCase = affectorCases.getJSONObject(caseIndex)
                assertTrue("Missing independent property case", reader.hasNext())
                val propertyCase = readExpected(reader) as JSONObject
                val identityCase = identityCases.getJSONObject(caseIndex)
                val pathCase = pathCases.getJSONObject(caseIndex)
                compare(case.getJSONObject("spec"), pathCase.getJSONObject("spec"))
                compare(case.getJSONObject("spec"), propertyCase.getJSONObject("spec"))
                compare(case.getJSONObject("spec"), identityCase.getJSONObject("spec"))
                compare(case.getJSONObject("spec"), affectorCase.getJSONObject("spec"))
                val input = JSONObject(wire(case.getJSONObject("spec")))
                if (input.has("ignore_restrictions")) assertFalse(input.getBoolean("ignore_restrictions"))
                if (input.has("cargo")) assertEquals(0, input.getJSONArray("cargo").length())
                input.remove("ignore_restrictions"); input.remove("cargo")
                val created = EngineRuntime.request(context, BridgeOperation.CreateFit(BridgeCodec.decodeFitSpec(wire(input)))).get(120, TimeUnit.SECONDS)
                assertTrue(created.error?.message, created.isSuccess)
                val id = created.fits.single().id
                val before = EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS)
                val originalRoles = identityCase.getJSONObject("expected")
                val actualRoles = JSONObject(EngineRuntime.inspectionSqlRoles(context, id).get(120, TimeUnit.SECONDS))
                sqlReference(originalRoles, actualRoles)
                val options = EngineRuntime.inspectionOptions(context, id).get(120, TimeUnit.SECONDS)
                assertEquals(id, options.fitId)
                val remaining = options.targets.toMutableList()
                val expected = case.getJSONArray("targets")
                val savedTargets = JSONArray()
                assertEquals(expected.length(), pathCase.getJSONArray("targets").length())
                val propertyTargets = propertyCase.getJSONArray("targets")
                assertEquals(expected.length(), propertyTargets.length())
                for (index in 0 until expected.length()) {
                    val row = expected.getJSONObject(index)
                    val family = row.getString("context")
                    val identity = row.getInt("item_id")
                    val selection = if (family == "base") InspectionTarget("base", null, identity) else {
                        val option = remaining.first { it.target.context == family && it.target.itemId == identity }
                        remaining.remove(option); option.target
                    }
                    val detail = EngineRuntime.inspectionDetails(context, id, selection).get(120, TimeUnit.SECONDS)
                    savedTargets.put(ModuleTestJson.typed(protocol(detail)))
                    assertEquals(selection, detail.target)
                    assertEquals(if (family == "base") null else id, detail.fitId)
                    assertEquals(if (family == "base") null else options.revision, detail.revision)
                    reference(row, detail)
                    val pathTarget = pathCase.getJSONArray("targets").getJSONObject(index)
                    assertEquals(family, pathTarget.getString("context")); assertEquals(identity, pathTarget.getInt("item_id"))
                    val actualPaths = JSONObject(EngineRuntime.inspectionEquipmentWitnesses(context, id, selection).get(120, TimeUnit.SECONDS))
                    assertEquals(setOf("definitions", "observations"), actualPaths.keys().asSequence().toSet())
                    compare(definitions, actualPaths.getJSONObject("definitions"))
                    val observations = actualPaths.getJSONArray("observations")
                    compare(pathTarget.getJSONArray("expected"), observations)
                    for (mode in 0 until observations.length()) {
                        val returns = observations.getJSONObject(mode).getJSONArray("returns")
                        for (position in 0 until returns.length()) observedReturns.add(returns.getString(position))
                    }
                    val affectorTarget = affectorCase.getJSONArray("targets").getJSONObject(index)
                    assertEquals(family, affectorTarget.getString("context")); assertEquals(identity, affectorTarget.getInt("item_id"))
                    treeReference(affectorTarget.getJSONObject("expected"), detail)
                    val propertyTarget = propertyTargets.getJSONObject(index)
                    assertEquals(family, propertyTarget.getString("context")); assertEquals(identity, propertyTarget.getInt("item_id"))
                    propertyReference(propertyTarget.getJSONArray("expected"), detail, originalRoles, actualRoles)
                    comparedProperties += propertyTarget.getJSONArray("expected").length()
                    if (caseIndex == 0 && family == "ship") guards(detail)
                    try { (detail.attributes as MutableList).clear(); fail("Mutable attribute list") } catch (_: UnsupportedOperationException) {}
                    comparedTargets++
                }
                assertTrue("Every fitted target compared", remaining.isEmpty())
                assertEquals("Read-only inspection preserves the saved graph", before,
                    EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
                canonicalFile.appendText(wire(obj("case_index" to caseIndex, "fit_id" to id,
                    "sql_roles" to actualRoles, "targets" to savedTargets)) + "\n", Charsets.UTF_8)
                canonicalObservations.appendText(wire(obj("case_index" to caseIndex, "fit_id" to id,
                    "phase" to "canonical", "pid" to Process.myPid(),
                    "sql_roles" to actualRoles, "targets" to savedTargets)) + "\n", Charsets.UTF_8)
            }
            assertFalse("Extra independent property case", reader.hasNext())
            reader.endArray()
            while (reader.hasNext()) {
                val name = reader.nextName(); assertFalse(propertyHeaders.has(name)); propertyHeaders.put(name, readExpected(reader))
            }
            reader.endObject()
            assertEquals(JsonToken.END_DOCUMENT, reader.peek())
            compare(obj("character_name" to "Headless synthetic skills"), propertyHeaders.getJSONObject("inputs"))
        }
        assertEquals("Every independent fitted and base target compared", 726, comparedTargets)
        assertEquals("Every independent property member compared", 57216, comparedProperties)
        val witnessed = paths.getJSONObject("coverage").getJSONArray("witnessed_return_ids")
        assertEquals((0 until witnessed.length()).map { witnessed.getString(it) }.toSet(), observedReturns)
        assertEquals("Real-case equipment return paths; probes remain separate", 52, observedReturns.size)
        val state = obj("last_phase" to "canonical", "pids" to canonicalPids,
            "cases" to cases.length(), "targets" to comparedTargets,
            "payload_sha256" to fileHash(canonicalFile),
            "graph" to ModuleTestJson.typed(JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))),
            "all_fits" to ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))))
        File(context.filesDir, "c032-canonical-state.json").writeText(wire(state), Charsets.UTF_8)
        val observedState = JSONObject(wire(state)).put("payload_sha256", fileHash(canonicalObservations))
        File(context.filesDir, "c032-canonical-observations-state.json").writeText(wire(observedState), Charsets.UTF_8)
    }

    private fun fileHash(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) { val count = input.read(buffer); if (count < 0) break; digest.update(buffer, 0, count) }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun restoreCanonical(phase: String, cases: JSONArray) {
        val start = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        assertTrue(start.getJSONObject("persistence").getBoolean("enabled"))
        assertTrue(start.getJSONObject("persistence").getBoolean("opened_existing"))
        val stateFile = File(context.filesDir, "c032-canonical-state.json")
        val state = JSONObject(stateFile.readText(Charsets.UTF_8))
        assertEquals(if (phase == "canonical-restored1") "canonical" else "canonical-restored1", state.getString("last_phase"))
        val pids = state.getJSONArray("pids")
        assertEquals(if (phase == "canonical-restored1") 1 else 2, pids.length())
        assertFalse((0 until pids.length()).any { pids.getInt(it) == Process.myPid() })
        assertEquals(152, state.getInt("cases")); assertEquals(726, state.getInt("targets"))
        val payload = File(context.filesDir, "c032-canonical-targets.jsonl")
        assertEquals(state.getString("payload_sha256"), fileHash(payload))
        fun unchanged() {
            compare(state.getJSONObject("graph"), ModuleTestJson.typed(JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))), strict = false)
            compare(state.getJSONObject("all_fits"), ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))), strict = false)
        }
        unchanged()
        var compared = 0
        val contexts = mutableSetOf<String>()
        val observations = File(context.filesDir, "c032-canonical-observations.jsonl")
        observations.writeText("", Charsets.UTF_8)
        payload.bufferedReader(Charsets.UTF_8).use { reader ->
            for (caseIndex in 0 until cases.length()) {
                val saved = JSONObject(checkNotNull(reader.readLine()) { "Missing saved canonical case" })
                assertEquals(caseIndex, saved.getInt("case_index"))
                val id = saved.getString("fit_id")
                val options = EngineRuntime.inspectionOptions(context, id).get(120, TimeUnit.SECONDS)
                val beforeRoles = saved.getJSONObject("sql_roles")
                val afterRoles = JSONObject(EngineRuntime.inspectionSqlRoles(context, id).get(120, TimeUnit.SECONDS))
                sqlReference(beforeRoles, afterRoles)
                val remaining = options.targets.toMutableList()
                val targets = saved.getJSONArray("targets")
                val original = cases.getJSONObject(caseIndex).getJSONArray("targets")
                assertEquals(original.length(), targets.length())
                val observedTargets = JSONArray()
                for (index in 0 until targets.length()) {
                    val expectedTyped = targets.getJSONObject(index)
                    val expected = expectedTyped.getJSONObject("data")
                    val identity = expected.getJSONObject("selection")
                    val family = identity.getString("context")
                    val target = if (family == "base") InspectionTarget("base", null, identity.getInt("item_id")) else {
                        val option = remaining.single { it.target.context == family && it.target.index == identity.getInt("index") }
                        remaining.remove(option)
                        assertEquals(identity.getInt("item_id"), option.target.itemId)
                        assertEquals(identity.getString("object_key"), option.target.objectKey)
                        option.target
                    }
                    val actual = EngineRuntime.inspectionDetails(context, id, target).get(120, TimeUnit.SECONDS)
                    reference(original.getJSONObject(index), actual)
                    val translated = replayProtocol(expected, actual, beforeRoles, afterRoles)
                    compare(ModuleTestJson.typed(translated), ModuleTestJson.typed(protocol(actual)), strict = false)
                    // Retain the captured numeric kinds independently of JSON reparsing.
                    compare(expectedTyped.getJSONObject("numeric_types"), ModuleTestJson.numericKinds(protocol(actual)))
                    observedTargets.put(ModuleTestJson.typed(protocol(actual)))
                    contexts.add(family); compared++
                }
                assertTrue("Every reopened fitted target compared", remaining.isEmpty())
                assertEquals(0, EngineRuntime.editHistory(context, id).get(120, TimeUnit.SECONDS).undoCount)
                assertEquals(0, EngineRuntime.editHistory(context, id).get(120, TimeUnit.SECONDS).redoCount)
                observations.appendText(wire(obj("case_index" to caseIndex, "fit_id" to id,
                    "phase" to phase, "pid" to Process.myPid(),
                    "sql_roles" to afterRoles, "targets" to observedTargets)) + "\n", Charsets.UTF_8)
            }
            assertNull("Extra saved canonical case", reader.readLine())
        }
        assertEquals(726, compared)
        assertEquals(setOf("base", "ship", "module", "charge", "drone", "fighter"), contexts)
        assertTrue(EngineRuntime.library.value.all { fit -> EngineRuntime.editHistory(context, fit.id).get(120, TimeUnit.SECONDS).let { it.undoCount == 0 && it.redoCount == 0 } })
        unchanged()
        assertEquals(state.getString("payload_sha256"), fileHash(payload))
        pids.put(Process.myPid()); state.put("last_phase", phase)
        stateFile.writeText(wire(state), Charsets.UTF_8)
        val observedState = JSONObject(wire(state)).put("payload_sha256", fileHash(observations))
            .put("graph", ModuleTestJson.typed(JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))))
            .put("all_fits", ModuleTestJson.typed(JSONArray(EngineRuntime.library.value.map(ModuleTestJson::fit))))
        File(context.filesDir, "c032-canonical-observations-state.json").writeText(wire(observedState), Charsets.UTF_8)
    }

    private fun replayProtocol(expected: JSONObject, actual: ItemInspection, before: JSONObject, after: JSONObject): JSONObject {
        // SQL row IDs can change during graph replay. Validate actual mapped-table
        // memberships first, then translate only these explicitly proven IDs.
        val oldFit = before.getJSONArray("fit").getJSONObject(0).getLong("ID")
        val newFit = after.getJSONArray("fit").getJSONObject(0).getLong("ID")
        val ids = mutableMapOf<String, Map<Long, Long>>()
        for ((kind, table) in listOf("Module" to "modules", "Drone" to "drones", "Fighter" to "fighters")) {
            val key = if (table == "modules") "ID" else "groupID"
            val left = before.getJSONArray(table); val right = after.getJSONArray(table)
            ids[kind] = (0 until left.length()).associate { left.getJSONObject(it).getLong(key) to right.getJSONObject(it).getLong(key) }
        }
        fun translate(value: Any): Any = when (value) {
            is JSONObject -> JSONObject().apply {
                value.keys().forEach { key ->
                    val member = value.get(key)
                    put(key, when {
                        key == "source_fit_id" -> { assertEquals(oldFit, value.getLong(key)); newFit }
                        key == "source_id" && member != JSONObject.NULL && value.optString("source_type") in ids ->
                            ids.getValue(value.getString("source_type")).getValue(value.getLong(key))
                        else -> translate(member)
                    })
                }
            }
            is JSONArray -> JSONArray((0 until value.length()).map { translate(value.get(it)) })
            else -> value
        }
        val result = translate(expected) as JSONObject
        val properties = expected.getJSONArray("properties")
        propertyReference(JSONArray((0 until properties.length()).map { obj("contract" to properties.getJSONObject(it)) }), actual, before, after)
        result.put("properties", JSONArray(actual.properties.map(::json)))
        return result
    }
    @Test fun completeBaseEffectsAndVariationsCrossNativeWorkerOffline() {
        assertEquals("canonical", InstrumentationRegistry.getArguments().getString("c032_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val golden = JSONObject(instrumentation.context.assets.open("inspector-metadata-expected.json").bufferedReader().use { it.readText() })
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", golden.getString("sourceCommit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", golden.getString("databaseLogicalSha256"))
        val before = EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS)
        val items = golden.getJSONArray("items")
        assertEquals(178, items.length())
        for (index in 0 until items.length()) {
            val expected = items.getJSONObject(index)
            val detail = EngineRuntime.inspectionDetails(context, null,
                InspectionTarget("base", null, expected.getInt("item_id"))).get(120, TimeUnit.SECONDS)
            assertNull(detail.fitId); assertNull(detail.revision)
            compare(expected.getJSONArray("effects"), JSONArray(detail.effects.map(::json)))
            val variations = json(detail.variations) as JSONObject
            compare(expected.getJSONArray("variation_columns"), variations.getJSONArray("columns"))
            val members = variations.getJSONArray("rows")
            compare(expected.getJSONArray("variation_ids"), JSONArray((0 until members.length()).map { members.getJSONObject(it).getInt("id") }))
            for (mode in listOf("normal", "raw")) {
                val rows = JSONArray()
                for (member in 0 until members.length()) {
                    val row = members.getJSONObject(member)
                    val cells = JSONArray().put(row.getString("name"))
                    val values = row.getJSONArray("values")
                    for (cell in 0 until values.length()) {
                        val value = values.getJSONObject(cell)
                        cells.put(if (value.getBoolean("available")) value.getString(if (mode == "raw") "raw" else "display") else "")
                    }
                    val price = row.getJSONObject("price")
                    cells.put(if (price.getBoolean("available")) price.getString("display") else "")
                    rows.put(cells)
                }
                compare(expected.getJSONObject("variation_presentation").getJSONObject(mode).getJSONArray("rows"), rows)
            }
        }
        assertEquals("Base inspection preserves the saved graph", before,
            EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
    }
    @Test fun originalComparisonSortSequencesUseNativeUiHelperOffline() {
        assertEquals("canonical", InstrumentationRegistry.getArguments().getString("c032_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val golden = JSONObject(instrumentation.context.assets.open("inspector-sorting-expected.json").bufferedReader().use { it.readText() })
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", golden.getString("sourceCommit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", golden.getString("databaseLogicalSha256"))
        val before = EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS)
        val items = golden.getJSONArray("items")
        assertEquals(178, items.length())
        var transitions = 0
        fun checkSequence(expected: JSONObject, members: List<InspectionValue.Fields>) {
            fun identity(row: InspectionValue.Fields) = ((row.values.getValue("id") as InspectionValue.Scalar).value.raw as Number).toInt()
            var order = (0 until expected.getJSONArray("initial_ids").length()).map { expected.getJSONArray("initial_ids").getInt(it) }
            compare(expected.getJSONArray("initial_ids"), JSONArray(members.map(::identity)))
            val sequence = expected.getJSONArray("sequence")
            for (index in 0 until sequence.length()) {
                val step = sequence.getJSONObject(index)
                val sorted = sortInspectionVariations(members, step.getString("key"), step.getBoolean("reverse"), order)
                order = sorted.map(::identity)
                compare(step.getJSONArray("ids"), JSONArray(order), "original_sort_step_$index")
                transitions++
            }
        }
        for (index in 0 until items.length()) {
            val expected = items.getJSONObject(index)
            val detail = EngineRuntime.inspectionDetails(context, null, InspectionTarget("base", null, expected.getInt("item_id"))).get(120, TimeUnit.SECONDS)
            val variation = json(detail.variations) as JSONObject
            compare(expected.getJSONArray("columns"), variation.getJSONArray("columns"))
            val members = (detail.variations.values.getValue("rows") as InspectionValue.Sequence).values.map { it as InspectionValue.Fields }
            checkSequence(expected, members)
        }
        val probes = golden.getJSONObject("probes")
        val inputs = probes.getJSONArray("inputs")
        val synthetic = (0 until inputs.length()).associate { index ->
            val row = inputs.getJSONObject(index)
            fun scalar(value: Any): InspectionValue = when (value) {
                JSONObject.NULL -> InspectionValue.Absent
                is String -> InspectionValue.Scalar(StatValue.Text(value))
                is Number -> InspectionValue.Scalar(if (value is Int || value is Long) StatValue.Integer(value.toLong()) else StatValue.Decimal(value.toDouble()))
                else -> error("Invalid synthetic sort input")
            }
            row.getInt("id") to InspectionValue.Fields(mapOf("id" to scalar(row.get("id")), "name" to scalar(row.get("name")),
                "meta" to scalar(row.get("meta")), "price" to InspectionValue.Fields(mapOf("value" to scalar(row.get("price")))),
                "values" to InspectionValue.Sequence(listOf(InspectionValue.Fields(mapOf("name" to scalar("probe"), "value" to scalar(row.get("value"))))))))
        }
        val initial = probes.getJSONArray("initial_ids")
        checkSequence(probes, (0 until initial.length()).map { synthetic.getValue(initial.getInt(it)) })
        assertEquals("Every family and synthetic cache/tie/Unicode sequence executed", 5520, transitions)
        assertEquals("Presentation sorting preserves saved fits", before,
            EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
    }
    @Test fun everyAssignedEffectCrossNativeWorkerOffline() {
        assertEquals("canonical", InstrumentationRegistry.getArguments().getString("c032_phase"))
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val golden = JSONObject(instrumentation.context.assets.open("inspector-effect-catalog-expected.json").bufferedReader().use { it.readText() })
        assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", golden.getString("sourceCommit"))
        assertEquals("5857af3ea30b3cfdf937120cf08c66f7cbe18dc8356db05b7adde72ee57bc607", golden.getString("databaseLogicalSha256"))
        val before = EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS)
        val expectedIds = golden.getJSONObject("inputs").getJSONArray("assigned_effect_ids")
        assertEquals(3016, expectedIds.length())
        val items = golden.getJSONArray("items")
        assertEquals(1274, items.length())
        val witnessed = mutableMapOf<Int, Set<Int>>()
        for (index in 0 until items.length()) {
            val expected = items.getJSONObject(index)
            val identity = expected.getInt("item_id")
            val detail = EngineRuntime.inspectionDetails(context, null, InspectionTarget("base", null, identity)).get(120, TimeUnit.SECONDS)
            assertNull(detail.fitId); assertNull(detail.revision)
            compare(expected.getJSONArray("effects"), JSONArray(detail.effects.map(::json)))
            val effects = detail.effects.map { (json(it) as JSONObject).getInt("id") }.toSet()
            assertNull("Duplicate item witness", witnessed.put(identity, effects))
        }
        compare(expectedIds, JSONArray(witnessed.values.flatten().toSortedSet().toList()))
        val assignments = golden.getJSONObject("inputs").getJSONArray("assignments")
        for (index in 0 until assignments.length()) {
            val row = assignments.getJSONObject(index)
            assertTrue("Assigned effect lost its independent item witness", witnessed.getValue(row.getInt("item_id")).contains(row.getInt("effect_id")))
        }
        assertEquals("Complete effect inspection preserves the saved graph", before,
            EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
    }
}
