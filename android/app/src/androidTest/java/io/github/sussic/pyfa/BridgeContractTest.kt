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
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import kotlin.math.abs
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Runs separately from the legacy diagnostic and performance suites. */
@RunWith(AndroidJUnit4::class)
class BridgeContractTest {
    private lateinit var context: Context
    private lateinit var sessionId: String
    private val fits = linkedMapOf<String, FitSnapshot>()
    private val responses = JSONArray()
    private val scalarTypes = JSONObject()
    private val requestIds = mutableSetOf<String>()
    private var checkedSnapshots = 0

    @Test
    fun typedOperationsMatchDesktopAndPreserveCommittedRevisionsOffline() {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        context = instrumentation.targetContext
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        assertTrue("The contract suite requires its own fresh process", EngineRuntime.state.value is EngineState.Loading)

        val manifest = appJson("manifest")
        val fixtures = JSONObject()
        val goldens = linkedMapOf<String, JSONObject>()
        val cases = linkedMapOf<String, JSONObject>()
        for ((kind, asset) in listOf("ammunition" to "vexor", "projection" to "projection", "command" to "command")) {
            val bytes = instrumentation.context.assets.open("$asset-expected.json").use { it.readBytes() }
            val golden = JSONObject(bytes.toString(Charsets.UTF_8))
            val input = appJson(asset)
            compare(golden.get("inputs"), input, "$kind.inputs")
            val hash = sha256(bytes)
            val hashKey = if (kind == "ammunition") "desktop_fixture_sha256" else "${kind}_fixture_sha256"
            assertEquals(hash, manifest.getString(hashKey))
            assertEquals(golden.getString("source_commit"), manifest.getString("desktop_source_commit"))
            for (key in listOf("database_logical_sha256", "source_data_sha256", "dataset_metadata")) {
                compare(golden.get(key), manifest.get(key), "$kind.manifest.$key")
            }
            goldens[kind] = golden
            cases[kind] = input
            fixtures.put(kind, JSONObject().put("sha256", hash)
                .put("source_commit", golden.getString("source_commit"))
                .put("inputs", input).put("eos_settings", golden.getJSONObject("eos_settings")))
        }

        val sample = EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        assertEquals(1L, sample.revision)
        fits[sample.id] = sample
        val bootstrapQuery = EngineRuntime.request(context, BridgeOperation.Snapshot()).get(120, TimeUnit.SECONDS)
        sessionId = bootstrapQuery.sessionId
        accept(bootstrapQuery)
        assertEquals(listOf(sample), bootstrapQuery.fits)
        assertTrue(sessionId.isNotEmpty())

        val states = JSONObject()
        val ammunitionStates = JSONObject()
        // A01's independent oracle has 38 fields. A04 uses the identical Vexor
        // inputs and independently supplies its added scan-resolution field.
        val ammoInput = cases.getValue("ammunition")
        val projectionTarget = cases.getValue("projection").getJSONObject("target")
        val comparableAmmo = JSONObject(ammoInput.toString()).apply { remove("name"); remove("edit") }
        val comparableTarget = JSONObject(projectionTarget.toString()).apply { remove("name") }
        compare(comparableAmmo, comparableTarget, "scan_resolution_oracle_inputs")
        val scan = goldens.getValue("projection").getJSONObject("states")
            .getJSONObject("initial").getJSONObject("target").getJSONObject("scan_resolution")
        fun checkAmmo(stage: String) {
            val expected = JSONObject(goldens.getValue("ammunition").getJSONObject("states").getJSONObject(stage).toString())
                .put("scan_resolution", scan)
            checkStats(expected, fits.getValue(sample.id), "ammunition.$stage")
            ammunitionStates.put(stage, snapshotJson(fits.getValue(sample.id)))
        }
        checkAmmo("initial")
        val edit = ammoInput.getJSONObject("edit")
        mutate(BridgeOperation.SetCharges(sample.id, indices(edit), edit.getString("charge")), listOf(sample.id))
        checkAmmo("iron_ammunition")
        mutate(BridgeOperation.SetCharges(sample.id, indices(edit), "Antimatter Charge M"), listOf(sample.id))
        checkAmmo("restored")
        states.put("ammunition", ammunitionStates)

        for (kind in listOf("projection", "command")) {
            val input = cases.getValue(kind)
            val source = create(BridgeCodec.decodeFitSpec(input.getJSONObject("source")))
            val target = create(BridgeCodec.decodeFitSpec(input.getJSONObject("target")))
            val scenario = JSONObject()
            fun checkStage(stage: String) {
                val expected = goldens.getValue(kind).getJSONObject("states").getJSONObject(stage)
                checkStats(expected.getJSONObject("source"), fits.getValue(source), "$kind.$stage.source")
                checkStats(expected.getJSONObject("target"), fits.getValue(target), "$kind.$stage.target")
                scenario.put(stage, JSONObject().put("source", snapshotJson(fits.getValue(source)))
                    .put("target", snapshotJson(fits.getValue(target))))
            }
            checkStage("initial")
            var linked = false
            val steps = input.getJSONArray("steps")
            for (index in 0 until steps.length()) {
                val step = steps.getJSONObject(index)
                val action = step.getString("operation")
                val operation = operation(kind, step, source, target)
                val endpoints = action in setOf("add", "configure", "remove", "command_state")
                val expectedAffected = if (endpoints || linked) listOf(source, target) else listOf(source)
                mutate(operation, expectedAffected)
                if (action == "add") linked = true
                if (action == "remove") linked = false
                val current = fits.getValue(target)
                if (kind == "projection") {
                    assertEquals(if (linked) 1 else 0, current.projections.size)
                    if (linked) assertEquals(source, current.projections.single().sourceId)
                } else {
                    assertEquals(if (linked) 1 else 0, current.commands.size)
                    if (linked) assertEquals(source, current.commands.single().sourceId)
                }
                checkStage(step.getString("name"))
            }
            assertEquals(goldens.getValue(kind).getJSONObject("states").keys().asSequence().toSet(),
                scenario.keys().asSequence().toSet())
            states.put(kind, scenario)
        }
        assertEquals(63, checkedSnapshots)
        assertEquals(5, fits.size)

        // Errors must return no candidate snapshot and preserve every committed
        // fit, including the sample consumed by the UI.
        val beforeFailures = fits.toMap()
        reject(BridgeOperation.SetCharges(sample.id, listOf(0, 999999), "Iron Charge M"),
            revisions(sample.id), BridgeErrorCode.INVALID_EDIT)
        reject(BridgeOperation.SetCharges(sample.id, listOf(0, 1), "Shield Extension Charge"),
            revisions(sample.id), BridgeErrorCode.INVALID_EDIT)
        reject(BridgeOperation.SetCharges(sample.id, listOf(0, 1), "Iron Charge M"),
            mapOf(sample.id to 0L), BridgeErrorCode.REVISION_CONFLICT)
        reject(BridgeOperation.SetCharges(sample.id, listOf(0, 1), "Iron Charge M"),
            emptyMap(), BridgeErrorCode.INVALID_REQUEST)
        reject(BridgeOperation.Snapshot(listOf("unknown-fit")), emptyMap(), BridgeErrorCode.UNKNOWN_FIT)
        val brokenSpec = BridgeCodec.decodeFitSpec(projectionTarget).let { spec ->
            spec.copy(modules = spec.modules + ModuleSpec("B01 nonexistent module", ModuleState.ONLINE))
        }
        // Construction has already made the ship and earlier modules before
        // EOS encounters the invalid final item. Stable IDs must still resolve
        // to the committed fits after the failure recovery path.
        reject(BridgeOperation.CreateFit(brokenSpec), emptyMap(), BridgeErrorCode.INVALID_EDIT)
        assertEquals(beforeFailures, fits)

        // Two requests submitted without awaiting either carry the same CAS
        // revision. The single worker must commit precisely one grouped edit.
        val sharedRevision = revisions(sample.id)
        val callerOwnedIndices = mutableListOf(0, 1)
        val first = EngineRuntime.request(context,
            BridgeOperation.SetCharges(sample.id, callerOwnedIndices, "Iron Charge M"), sharedRevision)
        callerOwnedIndices.clear()
        val second = EngineRuntime.request(context,
            BridgeOperation.SetCharges(sample.id, listOf(0, 1), "Antimatter Charge M"), sharedRevision)
        val firstResponse = first.get(120, TimeUnit.SECONDS)
        val secondResponse = second.get(120, TimeUnit.SECONDS)
        accept(firstResponse)
        assertEquals(listOf(sample.id), firstResponse.fits.map { it.id })
        assertEquals(sharedRevision.getValue(sample.id) + 1, firstResponse.fits.single().revision)
        fits[sample.id] = firstResponse.fits.single()
        accept(secondResponse, BridgeErrorCode.REVISION_CONFLICT)
        assertEquals(listOf("Iron Charge M", "Iron Charge M"), fits.getValue(sample.id).modules.take(2).map { it.charge })
        queryUnchanged()
        mutate(BridgeOperation.SetCharges(sample.id, listOf(0, 1), "Antimatter Charge M"), listOf(sample.id))

        val codecRejections = checkCodec(firstResponse)
        val runtime = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
        assertEquals("pyfa-engine", runtime.getString("android_worker_thread"))
        assertFalse(runtime.getBoolean("android_main_thread"))
        assertEquals(sessionId, runtime.getString("session_id"))
        assertEquals(fits.size, runtime.getInt("retained_fit_count"))
        assertEquals("sqlite:///:memory:", runtime.getString("saveddata_connectionstring"))
        assertEquals(0, runtime.getJSONArray("desktop_import_attempts").length())
        compare(goldens.getValue("ammunition").get("eos_settings"), runtime.get("eos_settings"), "runtime.eos_settings")
        compare(manifest, runtime.get("manifest"), "runtime.manifest")
        compare(manifest.get("dataset_metadata"), runtime.get("dataset_metadata"), "runtime.dataset_metadata")

        val report = JSONObject().put("task", "B01").put("pid", Process.myPid())
            .put("airplane_mode", true).put("no_internet_permission", true)
            .put("session_id", sessionId).put("manifest", manifest).put("fixtures", fixtures)
            .put("states", states).put("responses", responses).put("runtime", runtime)
            .put("scalar_types", scalarTypes)
            .put("codec_rejections", codecRejections)
            .put("assertions", JSONObject().put("desktop_snapshots_checked", checkedSnapshots)
                .put("statistics_per_snapshot", 39).put("all_snapshots_matched_desktop", true)
                .put("raw_scalar_types_checked", true).put("units_checked", true)
                .put("bulk_rejection_unchanged", true).put("stale_revision_unchanged", true)
                .put("missing_revision_rejected_before_dispatch", true)
                .put("invalid_create_unchanged", true).put("queued_arguments_copied", true)
                .put("ui_preserved_after_errors", true)
                .put("queries_unchanged", true).put("unrelated_revisions_unchanged", true)
                .put("queued_same_revision_one_success_one_conflict", true)
                .put("retained_fit_count", fits.size))
        retain(report, "/sdcard/Download/pyfa-b01-contract.json")
    }

    private fun appJson(name: String): JSONObject = context.assets.open("engine/$name.json")
        .bufferedReader().use { JSONObject(it.readText()) }

    private fun create(spec: FitSpec): String {
        val response = EngineRuntime.request(context, BridgeOperation.CreateFit(spec)).get(120, TimeUnit.SECONDS)
        accept(response)
        val fit = response.fits.single()
        assertEquals(1L, fit.revision)
        assertFalse(fits.containsKey(fit.id))
        fits[fit.id] = fit
        queryUnchanged()
        return fit.id
    }

    private fun revisions(vararg ids: String): Map<String, Long> = ids.associateWith { fits.getValue(it).revision }

    private fun namedIds(operation: BridgeOperation): List<String> = when (operation) {
        is BridgeOperation.SetCharges -> listOf(operation.fitId)
        is BridgeOperation.SetModuleStates -> listOf(operation.fitId)
        is BridgeOperation.SetSkillLevel -> listOf(operation.fitId)
        is BridgeOperation.AddImplant -> listOf(operation.fitId)
        is BridgeOperation.SetImplantActive -> listOf(operation.fitId)
        is BridgeOperation.RemoveImplant -> listOf(operation.fitId)
        is BridgeOperation.AddProjection -> listOf(operation.sourceId, operation.targetId)
        is BridgeOperation.ConfigureProjection -> listOf(operation.sourceId, operation.targetId)
        is BridgeOperation.RemoveProjection -> listOf(operation.sourceId, operation.targetId)
        is BridgeOperation.AddCommand -> listOf(operation.sourceId, operation.targetId)
        is BridgeOperation.SetCommandActive -> listOf(operation.sourceId, operation.targetId)
        is BridgeOperation.RemoveCommand -> listOf(operation.sourceId, operation.targetId)
        else -> error("Not a mutation: $operation")
    }

    private fun mutate(operation: BridgeOperation, affected: List<String>) {
        val before = fits.toMap()
        val expected = namedIds(operation).associateWith { fits.getValue(it).revision }
        val response = EngineRuntime.request(context, operation, expected).get(120, TimeUnit.SECONDS)
        accept(response)
        assertEquals("Affected fits remain in registration order", fits.keys.filter { it in affected }, response.fits.map { it.id })
        for (fit in response.fits) {
            assertEquals(before.getValue(fit.id).revision + 1, fit.revision)
            fits[fit.id] = fit
        }
        for ((id, fit) in before) if (id !in affected) assertEquals(fit, fits.getValue(id))
        queryUnchanged()
    }

    private fun reject(operation: BridgeOperation, expected: Map<String, Long>, code: BridgeErrorCode) {
        val before = fits.toMap()
        val visibleFit = (EngineRuntime.state.value as EngineState.Ready).fit
        accept(EngineRuntime.request(context, operation, expected).get(120, TimeUnit.SECONDS), code)
        val visible = EngineRuntime.state.value as EngineState.Ready
        assertEquals(visibleFit, visible.fit)
        assertEquals(code, visible.error?.code)
        queryUnchanged()
        assertEquals(before, fits)
    }

    private fun queryUnchanged() {
        val response = EngineRuntime.request(context, BridgeOperation.Snapshot()).get(120, TimeUnit.SECONDS)
        assertTrue(response.isSuccess)
        assertEquals(sessionId, response.sessionId)
        assertEquals(fits.values.toList(), response.fits)
        // Ordered subsets must not silently become registration-order queries.
        val ids = fits.keys.toList().reversed().take(2)
        val subset = EngineRuntime.request(context, BridgeOperation.Snapshot(ids)).get(120, TimeUnit.SECONDS)
        assertTrue(subset.isSuccess)
        assertEquals(ids.map { fits.getValue(it) }, subset.fits)
    }

    private fun accept(response: BridgeResponse, error: BridgeErrorCode? = null) {
        assertEquals(sessionId, response.sessionId)
        assertTrue("Every request is correlated uniquely", requestIds.add(checkNotNull(response.requestId)))
        if (error == null) {
            assertTrue("Unexpected bridge error: ${response.error}", response.isSuccess)
            assertNull(response.error)
        } else {
            assertFalse(response.isSuccess)
            assertEquals(error, response.error?.code)
            assertTrue(response.fits.isEmpty())
            assertFalse(checkNotNull(response.error).message.contains("Traceback"))
        }
        responses.put(responseJson(response))
    }

    private fun operation(kind: String, step: JSONObject, source: String, target: String): BridgeOperation =
        when (step.getString("operation")) {
            "add" -> if (kind == "projection") BridgeOperation.AddProjection(source, target,
                optionalDouble(step, "range_m"), step.getBoolean("active"), step.getInt("amount"))
                else BridgeOperation.AddCommand(source, target, true)
            "configure" -> BridgeOperation.ConfigureProjection(source, target,
                optionalDouble(step, "range_m"), step.getBoolean("active"), step.getInt("amount"))
            "remove" -> if (kind == "projection") BridgeOperation.RemoveProjection(source, target)
                else BridgeOperation.RemoveCommand(source, target)
            "charges" -> BridgeOperation.SetCharges(source, indices(step), step.getString("charge"))
            "skill" -> BridgeOperation.SetSkillLevel(source, step.getString("skill"), step.getInt("level"))
            "implant_add" -> BridgeOperation.AddImplant(source, step.getString("implant"), true)
            "implant_state" -> BridgeOperation.SetImplantActive(source, step.getInt("slot"), step.getBoolean("active"))
            "implant_remove" -> BridgeOperation.RemoveImplant(source, step.getInt("slot"))
            "module_state" -> BridgeOperation.SetModuleStates(source, indices(step), ModuleState.valueOf(step.getString("state")))
            "command_state" -> BridgeOperation.SetCommandActive(source, target, step.getBoolean("active"))
            else -> error("Unknown independent scenario operation: $step")
        }

    private fun optionalDouble(value: JSONObject, key: String): Double? = if (value.isNull(key)) null else value.getDouble(key)

    private fun indices(value: JSONObject): List<Int> = value.getJSONArray("module_indices").let { array ->
        List(array.length()) { array.getInt(it) }
    }

    private fun checkStats(expected: JSONObject, actual: FitSnapshot, path: String) {
        assertEquals(39, actual.stats.size)
        assertEquals(expected.keys().asSequence().toSet(), actual.stats.keys)
        val observedTypes = JSONObject()
        for (key in expected.keys()) {
            val reference = expected.getJSONObject(key)
            val stat = actual.stats.getValue(key)
            observedTypes.put(key, when (stat.value) {
                is StatValue.Integer -> "integer"
                is StatValue.Decimal -> "decimal"
                is StatValue.BooleanValue -> "boolean"
                is StatValue.Text -> "text"
            })
            assertEquals("$path.$key.unit", reference.getString("unit"), stat.unit)
            when (val value = reference.get("value")) {
                is Boolean -> {
                    assertTrue("$path.$key must preserve a boolean", stat.value is StatValue.BooleanValue)
                    assertEquals(value, stat.value.raw)
                }
                is Int, is Long -> {
                    assertTrue("$path.$key must preserve an integer", stat.value is StatValue.Integer)
                    assertEquals((value as Number).toLong(), (stat.value as StatValue.Integer).value)
                }
                is Number -> {
                    assertTrue("$path.$key must preserve a decimal", stat.value is StatValue.Decimal)
                    compare(value, stat.value.raw, "$path.$key.value")
                }
                is String -> {
                    assertTrue("$path.$key must preserve text", stat.value is StatValue.Text)
                    assertEquals(value, stat.value.raw)
                }
                else -> error("Unexpected independent scalar: $path.$key")
            }
        }
        scalarTypes.put(path, observedTypes)
        checkedSnapshots++
    }

    private fun checkCodec(valid: BridgeResponse): JSONArray {
        val failures = JSONArray()
        fun rejected(name: String, text: String) {
            var failed = false
            try { BridgeCodec.decodeResponse(text) } catch (_: IllegalArgumentException) { failed = true }
            assertTrue("Malformed response accepted: $name", failed)
            failures.put(name)
        }
        fun changed(name: String, edit: (JSONObject) -> Unit) {
            rejected(name, responseJson(valid).also(edit).toString())
        }
        changed("unknown_response_field") { it.put("unexpected", true) }
        changed("missing_session") { it.remove("session_id") }
        changed("unknown_status") { it.put("status", "maybe") }
        changed("boolean_version") { it.put("version", true) }
        changed("unsupported_version") { it.put("version", 2) }
        changed("negative_revision") { it.getJSONArray("fits").getJSONObject(0).put("revision", -1) }
        changed("boolean_revision") { it.getJSONArray("fits").getJSONObject(0).put("revision", true) }
        changed("unknown_module_state") { it.getJSONArray("fits").getJSONObject(0)
            .getJSONArray("modules").getJSONObject(0).put("state", "HOT") }
        changed("missing_raw_unit") { it.getJSONArray("fits").getJSONObject(0)
            .getJSONObject("stats").getJSONObject("total_dps").remove("unit") }
        changed("unknown_error_code") { it.put("status", "error").put("fits", JSONArray())
            .put("error", JSONObject().put("code", "SOMETHING_NEW").put("message", "Invalid")) }
        val validText = responseJson(valid).toString()
        rejected("duplicate_keys", "{\"version\":1," + validText.substring(1))
        rejected("decimal_version", validText.replaceFirst("\"version\":1", "\"version\":1.0"))
        rejected("decimal_revision", validText.replaceFirst("\"revision\":${valid.fits.single().revision}",
            "\"revision\":${valid.fits.single().revision}.0"))
        rejected("nonfinite_number", validText.replaceFirst("\"revision\":${valid.fits.single().revision}", "\"revision\":1e400"))
        rejected("trailing_document", "$validText {}")

        // Golden combat fields happen to contain decimals/booleans. Exercise
        // all four allowed scalar variants explicitly at the codec boundary.
        val scalarFixture = responseJson(valid)
        val scalarStats = scalarFixture.getJSONArray("fits").getJSONObject(0).getJSONObject("stats")
        scalarStats.getJSONObject("cpu_output").put("value", 2L)
        scalarStats.getJSONObject("cpu_used").put("value", 2.5)
        scalarStats.getJSONObject("capacitor_stable").put("value", true)
        scalarStats.getJSONObject("shield_hp").put("value", "active")
        val decoded = BridgeCodec.decodeResponse(scalarFixture.toString()).fits.single().stats
        assertTrue(decoded.getValue("cpu_output").value is StatValue.Integer)
        assertTrue(decoded.getValue("cpu_used").value is StatValue.Decimal)
        assertTrue(decoded.getValue("capacitor_stable").value is StatValue.BooleanValue)
        assertTrue(decoded.getValue("shield_hp").value is StatValue.Text)
        return failures
    }

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

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256").digest(bytes)
        .joinToString("") { "%02x".format(it) }

    private fun retain(actual: JSONObject, output: String) {
        val automation = InstrumentationRegistry.getInstrumentation().uiAutomation
        if (Build.VERSION.SDK_INT >= 31) {
            val descriptors = automation.executeShellCommandRw("dd of=$output")
            ParcelFileDescriptor.AutoCloseInputStream(descriptors[0]).use { completion ->
                ParcelFileDescriptor.AutoCloseOutputStream(descriptors[1]).use { input ->
                    input.write(actual.toString(2).toByteArray(Charsets.UTF_8))
                }
                completion.readBytes()
            }
        } else error("The native evidence transport requires API 31 or later")
        val retained = ParcelFileDescriptor.AutoCloseInputStream(automation.executeShellCommand("cat $output"))
            .use { it.readBytes().toString(Charsets.UTF_8) }
        compare(actual, JSONObject(retained), "retained_native_evidence")
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
                if (expected is Int || expected is Long) {
                    assertTrue("$path must be an integer", actual is Int || actual is Long)
                    assertEquals(path, expected.toLong(), (actual as Number).toLong())
                } else {
                    val left = expected.toDouble()
                    val right = (actual as Number).toDouble()
                    assertTrue("$path must be finite", left.isFinite() && right.isFinite())
                    assertEquals(path, left, right, maxOf(1e-9, 1e-10 * maxOf(abs(left), abs(right))))
                }
            }
            else -> assertEquals(path, expected, actual)
        }
    }
}
