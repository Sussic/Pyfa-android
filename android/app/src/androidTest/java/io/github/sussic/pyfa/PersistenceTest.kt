package io.github.sussic.pyfa

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.ParcelFileDescriptor
import android.os.Process
import android.provider.Settings
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import kotlin.math.abs
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** CI invokes each phase in a new process, preserving the app's private data. */
@RunWith(AndroidJUnit4::class)
class PersistenceTest {
    private lateinit var context: Context
    private lateinit var sessionId: String
    private val fits = linkedMapOf<String, FitSnapshot>()
    private val roles = linkedMapOf<String, String>()
    private val goldens = linkedMapOf<String, JSONObject>()
    private val cases = linkedMapOf<String, JSONObject>()
    private val observations = JSONObject()
    private val oracleStates = JSONObject()
    private val scalarTypes = JSONObject()
    private val requests = JSONArray()
    private val responses = JSONArray()
    private val queryOrders = JSONArray()
    private var checkedSnapshots = 0
    private var successfulMutations = 0

    @Test
    fun persistentGraphSurvivesProcessRestartOffline() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        context = instrumentation.targetContext
        val phase = checkNotNull(InstrumentationRegistry.getArguments().getString("b02_phase"))
        assertTrue(phase in listOf("prepare", "reopen_edit", "verify"))
        assertTrue("Each phase requires a fresh process", EngineRuntime.state.value is EngineState.Loading)
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        val manifest = appJson("manifest")
        val fixtures = loadFixtures(manifest)
        val previous = when (phase) {
            "reopen_edit" -> readReceipt("prepare")
            "verify" -> readReceipt("reopen_edit")
            else -> null
        }

        val sample = EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val opened = EngineRuntime.request(context, BridgeOperation.Snapshot()).get(120, TimeUnit.SECONDS)
        assertTrue("Startup query failed: ${opened.error}", opened.isSuccess)
        sessionId = opened.sessionId
        opened.fits.forEach { fits[it.id] = it }
        val runtimeStart = diagnostics()
        // A10's normal launches already created the one-sample production
        // store. Its diagnostic probes must not have persisted extra fits.
        assertTrue(runtimeStart.getJSONObject("persistence").getBoolean("opened_existing"))
        assertEquals(sample.id, runtimeStart.getString("sample_id"))

        if (previous == null) {
            assertEquals(1, fits.size)
            assertEquals(1L, sample.revision)
            assertEquals(1L, runtimeStart.getJSONObject("persistence").getLong("generation"))
            roles["sample"] = sample.id
            prepare()
            observe("committed", "prepared")
        } else {
            val priorRoles = previous.getJSONObject("role_ids")
            for (role in ROLE_ORDER) roles[role] = priorRoles.getString(role)
            assertEquals(roles.values.toList(), fits.keys.toList())
            assertEquals(roles.getValue("sample"), sample.id)
            assertNotEquals(previous.getString("session_id"), sessionId)
            assertNotEquals(previous.getInt("pid"), Process.myPid())
            if (phase == "verify") {
                val first = readReceipt("prepare")
                assertNotEquals(first.getString("session_id"), sessionId)
                assertNotEquals(first.getInt("pid"), Process.myPid())
            }
            assertEquals(previous.getJSONObject("runtime_end").getJSONObject("persistence").getLong("generation"),
                runtimeStart.getJSONObject("persistence").getLong("generation"))
            compare(previous.getJSONObject("final_fits"), roleSnapshots(), "reopened_graph")
            for (role in ROLE_ORDER) {
                assertEquals(previous.getJSONObject("final_fits").getJSONObject(role).getLong("revision"), fit(role).revision)
            }
            observe("opened", if (phase == "reopen_edit") "prepared" else "edited")
            if (phase == "reopen_edit") editAfterReopen()
        }

        queryUnchanged()
        val runtimeEnd = diagnostics()
        verifyDrones(runtimeEnd)
        val storage = runtimeEnd.getJSONObject("persistence")
        assertEquals(runtimeStart.getJSONObject("persistence").getLong("generation") + successfulMutations,
            storage.getLong("generation"))
        assertEquals(9, fits.size)
        assertEquals(if (phase == "reopen_edit") 27 else 9, checkedSnapshots)
        val report = JSONObject().put("task", "B02").put("phase", phase).put("pid", Process.myPid())
            .put("session_id", sessionId).put("airplane_mode", true).put("no_internet_permission", true)
            .put("role_ids", JSONObject(roles as Map<*, *>)).put("manifest", manifest).put("fixtures", fixtures)
            .put("runtime_start", runtimeStart).put("runtime_end", runtimeEnd)
            .put("observations", observations).put("oracle_states", oracleStates).put("scalar_types", scalarTypes)
            .put("requests", requests).put("responses", responses).put("query_orders", queryOrders).put("final_fits", roleSnapshots())
            .put("assertions", JSONObject().put("desktop_snapshots_checked", checkedSnapshots)
                .put("statistics_per_snapshot", 39).put("all_snapshots_matched_desktop", true)
                .put("raw_scalar_types_checked", true).put("units_checked", true)
                .put("successful_mutations", successfulMutations).put("retained_fit_count", fits.size)
                .put("queries_unchanged", true).put("drones_match_inputs", true)
                .put("reopened_identity_and_revisions", previous != null)
                .put("reopened_full_graph", previous != null)
                .put("failed_edit_unchanged", phase == "reopen_edit")
                .put("both_recipients_refreshed", phase == "reopen_edit"))
        retain(report, receiptPath(phase))
    }

    private fun prepare() {
        edit(BridgeOperation.SetCharges(id("sample"), listOf(0, 1), "Iron Charge M"), listOf("sample"))
        for (kind in listOf("projection", "command")) {
            for (role in listOf("source", "first", "second", "unlinked")) {
                val base = cases.getValue(kind).getJSONObject(if (role == "source") "source" else "target")
                val spec = BridgeCodec.decodeFitSpec(base).copy(name = "B02 $kind $role – Δ")
                val response = request(BridgeOperation.CreateFit(spec))
                val created = response.fits.single()
                assertEquals(1L, created.revision)
                assertFalse(fits.containsKey(created.id))
                fits[created.id] = created
                roles["${kind}_$role"] = created.id
                successfulMutations++
            }
        }
        edit(BridgeOperation.AddProjection(id("projection_source"), id("projection_first"), 100000.0, true, 1),
            listOf("projection_source", "projection_first"))
        edit(BridgeOperation.AddProjection(id("projection_source"), id("projection_second"), 0.0, false, 1),
            listOf("projection_source", "projection_first", "projection_second"))
        edit(BridgeOperation.SetSkillLevel(id("command_source"), "Shield Command Specialist", 4), listOf("command_source"))
        edit(BridgeOperation.AddCommand(id("command_source"), id("command_first"), true),
            listOf("command_source", "command_first"))
        edit(BridgeOperation.AddCommand(id("command_source"), id("command_second"), false),
            listOf("command_source", "command_first", "command_second"))
        assertEquals(ROLE_ORDER, roles.keys.toList())
    }

    private fun editAfterReopen() {
        val projection = listOf("projection_source", "projection_first", "projection_second")
        val command = listOf("command_source", "command_first", "command_second")
        edit(BridgeOperation.ConfigureProjection(id("projection_source"), id("projection_first"), 0.0, true, 1), projection)
        edit(BridgeOperation.ConfigureProjection(id("projection_source"), id("projection_second"), 0.0, true, 1), projection)
        edit(BridgeOperation.SetCharges(id("projection_source"), listOf(1), "Scan Resolution Dampening Script"), projection)
        edit(BridgeOperation.SetCommandActive(id("command_source"), id("command_second"), true), command)
        edit(BridgeOperation.SetSkillLevel(id("command_source"), "Shield Command Specialist", 5), command)
        edit(BridgeOperation.AddImplant(id("command_source"), "Shield Command Mindlink", true), command)
        edit(BridgeOperation.SetCharges(id("command_source"), listOf(1), "Shield Harmonizing Charge"), command)
        observe("recipients_refreshed", "both")
        edit(BridgeOperation.RemoveProjection(id("projection_source"), id("projection_first")), projection)
        edit(BridgeOperation.RemoveCommand(id("command_source"), id("command_first")), command)
        edit(BridgeOperation.SetCharges(id("sample"), listOf(0, 1), "Antimatter Charge M"), listOf("sample"))

        val before = fits.toMap()
        val generation = diagnostics().getJSONObject("persistence").getLong("generation")
        val invalidOperation = BridgeOperation.SetCharges(id("sample"), listOf(0, 999999), "Iron Charge M")
        val invalidRevisions = mapOf(id("sample") to fit("sample").revision)
        val response = EngineRuntime.request(context, invalidOperation, invalidRevisions).get(120, TimeUnit.SECONDS)
        assertEquals(sessionId, response.sessionId)
        assertFalse(response.isSuccess)
        assertEquals(BridgeErrorCode.INVALID_EDIT, response.error?.code)
        assertTrue(response.fits.isEmpty())
        record(invalidOperation, invalidRevisions, response)
        queryUnchanged()
        assertEquals(before, fits)
        assertEquals(generation, diagnostics().getJSONObject("persistence").getLong("generation"))
        observe("committed", "edited")
    }

    private fun observe(name: String, state: String) {
        queryUnchanged()
        assertStructure(state)
        val selectors = JSONObject()
        val actual = JSONObject()
        for (role in ROLE_ORDER) {
            val kind = if (role == "sample") "ammunition" else role.substringBefore('_')
            val source = role.endsWith("_source")
            val stage = when {
                role == "sample" -> if (state == "edited") "restored" else "iron_ammunition"
                role.endsWith("_unlinked") -> "initial"
                kind == "projection" && state == "prepared" -> if (source || role.endsWith("_first")) "falloff" else "initial"
                kind == "projection" -> if (state == "edited" && role.endsWith("_first")) "initial" else "script_changed"
                state == "prepared" -> if (source || role.endsWith("_first")) "specialist_4" else "initial"
                else -> if (state == "edited" && role.endsWith("_first")) "initial" else "harmonizing"
            }
            val goldenRole = if (kind == "ammunition") "single" else if (source) "source" else "target"
            val reference = goldens.getValue(kind).getJSONObject("states").getJSONObject(stage)
            val expected = if (kind == "ammunition") copyObject(reference).put("scan_resolution",
                goldens.getValue("projection").getJSONObject("states").getJSONObject("initial")
                    .getJSONObject("target").getJSONObject("scan_resolution")) else reference.getJSONObject(goldenRole)
            checkStats(expected, fit(role), "$name.$role")
            selectors.put(role, JSONObject().put("fixture", kind).put("state", stage).put("role", goldenRole))
            actual.put(role, snapshotJson(fit(role)))
        }
        observations.put(name, actual)
        oracleStates.put(name, selectors)
    }

    private fun assertStructure(state: String) {
        val edited = state != "prepared"
        for (role in ROLE_ORDER) {
            val fit = fit(role)
            if (role != "sample") assertEquals("B02 ${role.replace('_', ' ')} – Δ", fit.name)
            if (role != "command_source") assertTrue(fit.implants.isEmpty())
            if (!role.startsWith("projection_") || role.endsWith("_source") || role.endsWith("_unlinked")) {
                assertTrue(fit.projections.isEmpty())
            }
            if (!role.startsWith("command_") || role.endsWith("_source") || role.endsWith("_unlinked")) {
                assertTrue(fit.commands.isEmpty())
            }
        }
        val source = fit("command_source")
        if (edited) {
            assertFalse(source.skills.containsKey("Shield Command Specialist"))
            assertEquals(listOf(ImplantSnapshot("Shield Command Mindlink", 10, true)), source.implants)
        } else {
            assertEquals(4, source.skills.getValue("Shield Command Specialist"))
            assertTrue(source.implants.isEmpty())
        }
        assertEquals(if (edited) "Shield Harmonizing Charge" else "Shield Extension Charge", source.modules[1].charge)
        assertEquals(if (edited) "Scan Resolution Dampening Script" else "Targeting Range Dampening Script",
            fit("projection_source").modules[1].charge)
        assertEquals(List(2) { if (state == "edited") "Antimatter Charge M" else "Iron Charge M" },
            fit("sample").modules.take(2).map { it.charge })
        for (recipient in listOf("first", "second")) {
            val removed = state == "edited" && recipient == "first"
            val active = state != "prepared" || recipient == "first"
            val range = if (state == "prepared" && recipient == "first") 100000.0 else 0.0
            assertEquals(if (removed) emptyList() else listOf(ProjectionSnapshot(id("projection_source"), range, active, 1)),
                fit("projection_$recipient").projections)
            assertEquals(if (removed) emptyList() else listOf(CommandSnapshot(id("command_source"), active)),
                fit("command_$recipient").commands)
        }
    }

    private fun edit(operation: BridgeOperation, affectedRoles: List<String>) {
        val before = fits.toMap()
        val named = when (operation) {
            is BridgeOperation.SetCharges -> listOf(operation.fitId)
            is BridgeOperation.SetSkillLevel -> listOf(operation.fitId)
            is BridgeOperation.AddImplant -> listOf(operation.fitId)
            is BridgeOperation.AddProjection -> listOf(operation.sourceId, operation.targetId)
            is BridgeOperation.ConfigureProjection -> listOf(operation.sourceId, operation.targetId)
            is BridgeOperation.RemoveProjection -> listOf(operation.sourceId, operation.targetId)
            is BridgeOperation.AddCommand -> listOf(operation.sourceId, operation.targetId)
            is BridgeOperation.SetCommandActive -> listOf(operation.sourceId, operation.targetId)
            is BridgeOperation.RemoveCommand -> listOf(operation.sourceId, operation.targetId)
            else -> error("Unexpected persistence scenario operation")
        }
        val response = request(operation, named.associateWith { fits.getValue(it).revision })
        val affected = affectedRoles.map(::id)
        assertEquals(fits.keys.filter { it in affected }, response.fits.map { it.id })
        for (fit in response.fits) {
            assertEquals(before.getValue(fit.id).revision + 1, fit.revision)
            fits[fit.id] = fit
        }
        for ((id, fit) in before) if (id !in affected) assertEquals(fit, fits.getValue(id))
        successfulMutations++
    }

    private fun request(operation: BridgeOperation, revisions: Map<String, Long> = emptyMap()): BridgeResponse {
        val response = EngineRuntime.request(context, operation, revisions).get(120, TimeUnit.SECONDS)
        assertEquals(sessionId, response.sessionId)
        assertTrue("Unexpected operation failure: ${response.error}", response.isSuccess)
        assertNotNull(response.requestId)
        record(operation, revisions, response)
        return response
    }

    private fun record(operation: BridgeOperation, revisions: Map<String, Long>, response: BridgeResponse) {
        requests.put(JSONObject(BridgeCodec.encodeRequest(BridgeRequest(checkNotNull(response.requestId), sessionId, operation, revisions))))
        responses.put(responseJson(response))
    }

    private fun queryUnchanged() {
        val response = EngineRuntime.request(context, BridgeOperation.Snapshot()).get(120, TimeUnit.SECONDS)
        assertTrue(response.isSuccess)
        assertEquals(sessionId, response.sessionId)
        assertEquals(fits.values.toList(), response.fits)
        val reverseRecipients = listOf("projection_second", "projection_first", "command_second", "command_first").map(::id)
        val selected = EngineRuntime.request(context, BridgeOperation.Snapshot(reverseRecipients)).get(120, TimeUnit.SECONDS)
        assertTrue(selected.isSuccess)
        assertEquals(sessionId, selected.sessionId)
        assertEquals(reverseRecipients.map { fits.getValue(it) }, selected.fits)
        queryOrders.put(JSONArray(selected.fits.map { it.id }))
    }

    private fun diagnostics(): JSONObject {
        val result = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        assertEquals("pyfa-engine", result.getString("android_worker_thread"))
        assertFalse(result.getBoolean("android_main_thread"))
        assertEquals(sessionId, result.getString("session_id"))
        assertEquals(fits.size, result.getInt("retained_fit_count"))
        assertEquals(0, result.getJSONArray("desktop_import_attempts").length())
        val persistence = result.getJSONObject("persistence")
        assertTrue(persistence.getBoolean("enabled"))
        assertEquals(1, persistence.getInt("schema"))
        assertTrue(persistence.getLong("generation") >= 1)
        val database = File(persistence.getString("path"))
        assertEquals(File(context.noBackupFilesDir, "fits/graph.sqlite3").canonicalPath, database.canonicalPath)
        assertTrue(database.isFile)
        database.inputStream().use {
            val header = ByteArray(16)
            assertEquals(16, it.read(header))
            assertEquals("SQLite format 3\u0000", header.toString(Charsets.US_ASCII))
        }
        compare(appJson("manifest"), result.get("manifest"), "runtime.manifest")
        compare(appJson("manifest").get("dataset_metadata"), result.get("dataset_metadata"), "runtime.dataset_metadata")
        compare(goldens.getValue("ammunition").get("eos_settings"), result.get("eos_settings"), "runtime.eos_settings")
        return result
    }

    private fun verifyDrones(runtime: JSONObject) {
        val actual = runtime.getJSONObject("drones")
        assertEquals(fits.keys, actual.keys().asSequence().toSet())
        for (role in ROLE_ORDER) {
            val spec = when {
                role == "sample" -> cases.getValue("ammunition")
                else -> cases.getValue(role.substringBefore('_')).getJSONObject(if (role.endsWith("_source")) "source" else "target")
            }
            compare(spec.get("drones"), actual.get(id(role)), "drones.$role")
        }
    }

    private fun loadFixtures(manifest: JSONObject): JSONObject {
        val fixtures = JSONObject()
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        for ((kind, asset) in listOf("ammunition" to "vexor", "projection" to "projection", "command" to "command")) {
            val bytes = instrumentation.context.assets.open("$asset-expected.json").use { it.readBytes() }
            val golden = JSONObject(bytes.toString(Charsets.UTF_8))
            val input = appJson(asset)
            compare(golden.get("inputs"), input, "$kind.inputs")
            val hash = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            assertEquals(hash, manifest.getString(if (kind == "ammunition") "desktop_fixture_sha256" else "${kind}_fixture_sha256"))
            assertEquals(golden.getString("source_commit"), manifest.getString("desktop_source_commit"))
            for (key in listOf("database_logical_sha256", "source_data_sha256", "dataset_metadata")) {
                compare(golden.get(key), manifest.get(key), "$kind.manifest.$key")
            }
            goldens[kind] = golden
            cases[kind] = input
            fixtures.put(kind, JSONObject().put("sha256", hash).put("source_commit", golden.getString("source_commit"))
                .put("inputs", input).put("eos_settings", golden.get("eos_settings")))
        }
        val ammunition = copyObject(cases.getValue("ammunition")).apply { remove("name"); remove("edit") }
        val target = copyObject(cases.getValue("projection").getJSONObject("target")).apply { remove("name") }
        compare(ammunition, target, "scan_resolution_oracle_inputs")
        return fixtures
    }

    private fun checkStats(expected: JSONObject, actual: FitSnapshot, path: String) {
        assertEquals(39, actual.stats.size)
        assertEquals(expected.keys().asSequence().toSet(), actual.stats.keys)
        val types = JSONObject()
        for (key in expected.keys()) {
            val reference = expected.getJSONObject(key)
            val stat = actual.stats.getValue(key)
            val type = when (stat.value) {
                is StatValue.Integer -> "integer"
                is StatValue.Decimal -> "decimal"
                is StatValue.BooleanValue -> "boolean"
                is StatValue.Text -> "text"
            }
            val value = reference.get("value")
            val expectedType = when (value) {
                is Int, is Long -> "integer"
                is Number -> "decimal"
                is Boolean -> "boolean"
                is String -> "text"
                else -> error("Unexpected independent scalar")
            }
            assertEquals("$path.$key.type", expectedType, type)
            assertEquals("$path.$key.unit", reference.getString("unit"), stat.unit)
            compare(value, stat.value.raw, "$path.$key.value")
            types.put(key, type)
        }
        scalarTypes.put(path, types)
        checkedSnapshots++
    }

    private fun id(role: String): String = roles.getValue(role)
    private fun fit(role: String): FitSnapshot = fits.getValue(id(role))
    private fun roleSnapshots(): JSONObject = JSONObject().also { value ->
        for (role in ROLE_ORDER) value.put(role, snapshotJson(fit(role)))
    }
    private fun appJson(name: String): JSONObject = context.assets.open("engine/$name.json").bufferedReader().use { JSONObject(it.readText()) }
    private fun copyObject(value: JSONObject): JSONObject = JSONObject().also { copy ->
        // Preserve original scalar types; JSON string roundtrips turn 1750.0 into 1750.
        for (key in value.keys()) copy.put(key, value.get(key))
    }
    private fun receiptPath(phase: String) = "/sdcard/Download/pyfa-b02-$phase.json"
    private fun readReceipt(phase: String): JSONObject = JSONObject(readShellFile(receiptPath(phase)))
    private fun readShellFile(path: String): String = ParcelFileDescriptor.AutoCloseInputStream(
        InstrumentationRegistry.getInstrumentation().uiAutomation.executeShellCommand("cat $path"),
    ).use { it.readBytes().toString(Charsets.UTF_8) }

    private fun responseJson(response: BridgeResponse): JSONObject = JSONObject().put("version", 1)
        .put("request_id", response.requestId ?: JSONObject.NULL).put("session_id", response.sessionId)
        .put("status", if (response.isSuccess) "ok" else "error")
        .put("fits", JSONArray(response.fits.map(::snapshotJson)))
        .put("error", response.error?.let { JSONObject().put("code", it.code.name).put("message", it.message) } ?: JSONObject.NULL)

    private fun snapshotJson(fit: FitSnapshot): JSONObject {
        val stats = JSONObject()
        for ((key, value) in fit.stats) stats.put(key, JSONObject().put("value", value.value.raw).put("unit", value.unit))
        val skills = JSONObject()
        for ((name, level) in fit.skills) skills.put(name, level ?: JSONObject.NULL)
        return JSONObject().put("id", fit.id).put("revision", fit.revision).put("name", fit.name).put("ship", fit.ship)
            .put("stats", stats).put("skills", skills)
            .put("modules", JSONArray(fit.modules.map { JSONObject().put("index", it.index).put("name", it.name)
                .put("state", it.state.name).put("charge", it.charge ?: JSONObject.NULL) }))
            .put("implants", JSONArray(fit.implants.map { JSONObject().put("name", it.name).put("slot", it.slot).put("active", it.active) }))
            .put("projections", JSONArray(fit.projections.map { JSONObject().put("source_id", it.sourceId)
                .put("range_m", it.rangeM ?: JSONObject.NULL).put("active", it.active).put("amount", it.amount) }))
            .put("commands", JSONArray(fit.commands.map { JSONObject().put("source_id", it.sourceId).put("active", it.active) }))
    }

    private fun retain(actual: JSONObject, output: String) {
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        if (Build.VERSION.SDK_INT >= 31) {
            val descriptors = automation.executeShellCommandRw("dd of=$output")
            ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
                ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { it.write(actual.toString(2).toByteArray(Charsets.UTF_8)) }
                completion.readBytes()
            }
        } else error("The native evidence transport requires API 31 or later")
        compare(actual, JSONObject(readShellFile(output)), "retained_native_evidence")
    }

    private fun compare(expected: Any, actual: Any, path: String) {
        when (expected) {
            is JSONObject -> {
                assertTrue("$path must be an object", actual is JSONObject)
                actual as JSONObject
                assertEquals("$path keys", expected.keys().asSequence().toSet(), actual.keys().asSequence().toSet())
                for (key in expected.keys()) compare(expected.get(key), actual.get(key), "$path.$key")
            }
            is JSONArray -> {
                assertTrue("$path must be an array", actual is JSONArray)
                actual as JSONArray
                assertEquals("$path length", expected.length(), actual.length())
                for (index in 0 until expected.length()) compare(expected.get(index), actual.get(index), "$path[$index]")
            }
            is Number -> {
                assertTrue("$path must be numeric", actual is Number)
                actual as Number
                if ((expected is Int || expected is Long) && (actual is Int || actual is Long)) {
                    assertEquals(path, expected.toLong(), actual.toLong())
                } else {
                    // Receipt JSON normalizes integral decimals; independent
                    // oracle scalar types are checked before this comparison.
                    val left = expected.toDouble()
                    val right = actual.toDouble()
                    assertTrue("$path must be finite", left.isFinite() && right.isFinite())
                    assertEquals(path, left, right, maxOf(1e-9, 1e-10 * maxOf(abs(left), abs(right))))
                }
            }
            else -> assertEquals(path, expected, actual)
        }
    }

    companion object {
        private val ROLE_ORDER = listOf("sample", "projection_source", "projection_first", "projection_second", "projection_unlinked",
            "command_source", "command_first", "command_second", "command_unlinked")
    }
}
