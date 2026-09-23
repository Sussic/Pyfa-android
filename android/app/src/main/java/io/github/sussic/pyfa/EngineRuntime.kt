package io.github.sussic.pyfa

import android.content.Context
import android.os.Looper
import android.os.Debug
import android.os.Process
import android.os.SystemClock
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.CompletableFuture
import java.util.concurrent.Executors
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject
import org.json.JSONArray

sealed interface EngineState {
    data object Loading : EngineState
    data class Empty(val error: BridgeError? = null) : EngineState
    data class Ready(val fit: FitSnapshot, val error: BridgeError? = null) : EngineState
    data class Failed(val message: String) : EngineState
}

/** One process-owned worker: EOS and its SQLite session never cross threads. */
object EngineRuntime {
    private val executor = Executors.newSingleThreadExecutor { task -> Thread(task, "pyfa-engine") }
    private val mutableState = MutableStateFlow<EngineState>(EngineState.Loading)
    val state = mutableState.asStateFlow()
    private val mutableLibrary = MutableStateFlow<List<FitSnapshot>>(emptyList())
    val library = mutableLibrary.asStateFlow()
    private val mutableCatalog = MutableStateFlow(HullCatalog())
    val catalog = mutableCatalog.asStateFlow()
    private val mutableModified = MutableStateFlow<Map<String, Long>>(emptyMap())
    val modified = mutableModified.asStateFlow()
    private val mutableRecent = MutableStateFlow<List<Int>>(emptyList())
    val recent = mutableRecent.asStateFlow()
    private val mutableNavigation = MutableStateFlow(LibraryNavigation())
    val navigation = mutableNavigation.asStateFlow()
    private val mutableNavigationError = MutableStateFlow<String?>(null)
    val navigationError = mutableNavigationError.asStateFlow()
    private var navigationStore: NavigationStore? = null // Worker only.
    private var navigationWritable = true
    private var startup: CompletableFuture<FitSnapshot?>? = null
    private var sessionId: String? = null // Worker only.
    private var sampleId: String? = null // Worker only.
    private var unavailable = false // A transport fault may follow an unknown commit.
    private var startupMetrics: JSONObject? = null // Written/read only on the engine worker.
    private var startupDrawRecorded = false
    private var ephemeralDiagnostics = false // Selected before startup by the debug test runner.
    private var equipment: EquipmentCatalog? = null // Loaded on demand, worker only.
    private var equipmentRaw: String? = null

    fun equipmentCatalog(context: Context): CompletableFuture<EquipmentCatalog> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            equipment ?: Python.getInstance().getModule("mobile_runtime").callAttr("equipment_catalog").toString().let { raw ->
                EquipmentCatalog.decode(raw).also { equipment = it; equipmentRaw = raw }
            }
        }, executor)
    }

    fun equipmentDiagnostics(context: Context): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = equipmentCatalog(context)
        return CompletableFuture.supplyAsync({ ready.join(); checkNotNull(equipmentRaw) }, executor)
    }

    fun searchEquipment(context: Context, query: String): CompletableFuture<List<Int>> {
        val ready = equipmentCatalog(context)
        return CompletableFuture.supplyAsync({
            val catalog = ready.join()
            val rows = JSONArray(Python.getInstance().getModule("mobile_runtime")
                .callAttr("equipment_search", query).toString())
            val ids = (0 until rows.length()).map { rows.getInt(it) }
            check(ids.distinct().size == ids.size && ids.all { catalog.itemById[it]?.searchable == true })
            ids
        }, executor)
    }

    fun fittingDetails(context: Context, fitId: String): CompletableFuture<FittingDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeFitting(Python.getInstance().getModule("mobile_runtime")
                .callAttr("fitting_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun moduleDefaultsDiagnostics(context: Context): CompletableFuture<List<ModuleDefault>> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable)
            BridgeCodec.decodeModuleDefaults(Python.getInstance().getModule("mobile_runtime")
                .callAttr("module_defaults_diagnostics").toString())
        }, executor)
    }

    fun variationOptions(context: Context, fitId: String): CompletableFuture<VariationOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeVariationOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("variation_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun variationFamiliesDiagnostics(context: Context, fitId: String): CompletableFuture<List<VariationFamily>> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            BridgeCodec.decodeVariationFamilies(Python.getInstance().getModule("mobile_runtime")
                .callAttr("variation_families_diagnostics", fitId).toString())
        }, executor)
    }

    fun variationAdditionDiagnostics(context: Context, fitId: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("variation_addition_diagnostics", fitId).toString()
        }, executor)
    }

    fun chargeOptions(context: Context, fitId: String): CompletableFuture<ChargeOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeChargeOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("charge_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun chargeCompatibilityDiagnostics(context: Context): CompletableFuture<List<ChargeCompatibility>> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            BridgeCodec.decodeChargeCompatibility(Python.getInstance().getModule("mobile_runtime")
                .callAttr("charge_compatibility_diagnostics").toString())
        }, executor)
    }

    fun chargeModuleDiagnostics(context: Context, fitId: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("charge_module_diagnostics", fitId).toString()
        }, executor)
    }

    @Synchronized
    fun useEphemeralStorageForDiagnostics() {
        check(BuildConfig.DEBUG && startup == null) { "Diagnostics must select storage before engine startup" }
        ephemeralDiagnostics = true
    }

    @Synchronized
    fun start(context: Context): CompletableFuture<FitSnapshot?> {
        startup?.let { return it }
        val app = context.applicationContext
        val requested = SystemClock.elapsedRealtimeNanos()
        return CompletableFuture.supplyAsync({
            try {
                check(Looper.myLooper() != Looper.getMainLooper())
                val workerStarted = SystemClock.elapsedRealtimeNanos()
                val manifestText = app.assets.open("engine/manifest.json").bufferedReader().use { it.readText() }
                val manifest = JSONObject(manifestText)
                val expectedHash = manifest.getString("database_sha256")
                val directory = File(app.filesDir, "game").apply { mkdirs() }
                val database = File(directory, "eve-$expectedHash.db")
                var installed = false
                if (!database.isFile || sha256(database) != expectedHash) {
                    val staging = File(directory, "eve-install.tmp")
                    try {
                        app.assets.open("engine/eve.db").use { source ->
                            staging.outputStream().use { destination -> source.copyTo(destination) }
                        }
                        check(staging.length() == manifest.getLong("database_bytes")) { "Bundled database size mismatch" }
                        check(sha256(staging) == expectedHash) { "Bundled database checksum mismatch" }
                        check(staging.renameTo(database)) { "Could not install bundled game data" }
                        installed = true
                    } finally {
                        staging.delete()
                    }
                }
                val databaseReady = SystemClock.elapsedRealtimeNanos()
                if (!Python.isStarted()) Python.start(AndroidPlatform(app))
                val pythonReady = SystemClock.elapsedRealtimeNanos()
                val case = app.assets.open("engine/vexor.json").bufferedReader().use { it.readText() }
                val module = Python.getInstance().getModule("mobile_runtime")
                val store = if (ephemeralDiagnostics) null else {
                    val fits = File(app.noBackupFilesDir, "fits")
                    check(fits.isDirectory || fits.mkdirs()) { "Could not open saved fit storage" }
                    File(fits, "graph.sqlite3").absolutePath
                }
                module.callAttr("boot", database.absolutePath, manifestText, case, store)
                val bootstrap = BridgeCodec.decodeResponse(module.callAttr("bridge_bootstrap").toString())
                check(bootstrap.requestId == "bootstrap" && bootstrap.isSuccess) {
                    "Invalid engine bootstrap response"
                }
                val savedSampleId = module.callAttr("bridge_sample_id")?.toString()
                val result = bootstrap.fits.find { it.id == savedSampleId } ?: bootstrap.fits.firstOrNull()
                sessionId = bootstrap.sessionId
                sampleId = result?.id
                mutableCatalog.value = HullCatalog.decode(module.callAttr("library_catalog").toString())
                readOrganization()
                readRecent()
                if (!ephemeralDiagnostics) {
                    navigationStore = NavigationStore(File(app.noBackupFilesDir, "library-navigation.json"))
                }
                var navigation = LibraryNavigation(result?.let { listOf(it.id) } ?: emptyList(), result?.id)
                try {
                    navigationStore?.load()?.let { saved ->
                        navigation = (if (saved.restore) saved else saved.copy(openIds = emptyList(), activeId = null))
                            .retain(bootstrap.fits.map { it.id }.toSet())
                    }
                    navigationStore?.save(navigation)
                } catch (_: Exception) {
                    // Preserve damaged preferences and the independently valid fit store.
                    navigationWritable = false
                    mutableNavigationError.value = "Saved navigation could not be read or confirmed. Navigation will last for this session only."
                    navigation = LibraryNavigation()
                }
                mutableNavigation.value = navigation
                sampleId = navigation.activeId
                val ready = SystemClock.elapsedRealtimeNanos()
                startupMetrics = JSONObject()
                    .put("pid", Process.myPid())
                    .put("process_start_elapsed_ms", Process.getStartElapsedRealtime())
                    .put("engine_ready_elapsed_ms", ready / 1e6)
                    .put("engine_start_to_ready_ms", (ready - requested) / 1e6)
                    .put("queue_ms", (workerStarted - requested) / 1e6)
                    .put("database_ms", (databaseReady - workerStarted) / 1e6)
                    .put("python_start_ms", (pythonReady - databaseReady) / 1e6)
                    .put("python_boot_snapshot_ms", (ready - pythonReady) / 1e6)
                    .put("database_installed", installed)
                    .put("database_sha256", expectedHash)
                mutableLibrary.value = bootstrap.fits
                publishSelection()
                result
            } catch (error: Exception) {
                if (BuildConfig.DEBUG) Log.e("PyfaEngine", "Engine startup failed", error)
                mutableState.value = EngineState.Failed(error.message ?: "The fitting engine could not start.")
                throw error
            }
        }, executor).also { startup = it }
    }

    /** Called after Compose reports the ready data drawn; no disk I/O on the UI thread. */
    @Synchronized
    fun recordStartupDraw(context: Context) {
        if (!BuildConfig.DEBUG || startupDrawRecorded || state.value !is EngineState.Ready && state.value !is EngineState.Empty) return
        startupDrawRecorded = true
        val drawn = SystemClock.elapsedRealtimeNanos() / 1e6
        val app = context.applicationContext
        executor.execute {
            val report = checkNotNull(startupMetrics)
                .put("ready_draw_elapsed_ms", drawn)
                .put("process_to_ready_draw_ms", drawn - Process.getStartElapsedRealtime())
                .put("ready_to_draw_ms", drawn - checkNotNull(startupMetrics).getDouble("engine_ready_elapsed_ms"))
                .put("memory", memorySnapshot())
            val staging = File(app.filesDir, "a10-startup.tmp")
            staging.writeText(report.toString(2))
            check(staging.renameTo(File(app.filesDir, "a10-startup.json")))
        }
    }

    /** App process snapshots, not peaks; Android may omit protected graphics allocations. */
    fun memorySnapshot(): JSONObject {
        val info = Debug.MemoryInfo()
        Debug.getMemoryInfo(info)
        return JSONObject().put("total_pss_kb", info.totalPss)
            .put("total_private_dirty_kb", info.totalPrivateDirty)
            .put("native_heap_allocated_bytes", Debug.getNativeHeapAllocatedSize())
            .put("java_heap_used_bytes", Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory())
    }

    fun prepareBenchmark(context: Context, kind: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        val app = context.applicationContext
        return CompletableFuture.supplyAsync({
            ready.join()
            val case = when (kind) {
                "ammunition" -> "{}"
                "projection", "command" -> app.assets.open("engine/$kind.json").bufferedReader().use { it.readText() }
                else -> error("Unknown benchmark kind: $kind")
            }
            Python.getInstance().getModule("mobile_runtime").callAttr("prepare_benchmark", kind, case).toString()
        }, executor)
    }

    fun stepBenchmark(operation: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        return CompletableFuture.supplyAsync({
            checkNotNull(startup).join()
            Python.getInstance().getModule("mobile_runtime").callAttr("step_benchmark", operation).toString()
        }, executor)
    }

    /** All encoding, Python calls, decoding and publication use the same EOS worker. */
    fun request(
        context: Context,
        operation: BridgeOperation,
        expectedRevisions: Map<String, Long> = emptyMap(),
    ): CompletableFuture<BridgeResponse> {
        val ready = start(context)
        // Capture caller-owned collections before enqueueing.
        val capturedOperation = operation.snapshotArguments()
        val revisions = expectedRevisions.toMap()
        return CompletableFuture.supplyAsync({
            ready.join()
            check(Looper.myLooper() != Looper.getMainLooper())
            try {
                val request = BridgeRequest(UUID.randomUUID().toString(), checkNotNull(sessionId), capturedOperation, revisions)
                if (unavailable) {
                    return@supplyAsync BridgeResponse(request.requestId, request.sessionId, BridgeStatus.ERROR,
                        emptyList(), BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,
                            "Restart the app to recover the fitting engine."))
                }
                val encoded = try {
                    BridgeCodec.encodeRequest(request)
                } catch (_: BridgeProtocolException) {
                    val error = BridgeError(BridgeErrorCode.INVALID_REQUEST, "The edit request is invalid.")
                    val previous = mutableState.value as? EngineState.Ready
                    if (previous != null) mutableState.value = previous.copy(error = error)
                    else if (mutableState.value is EngineState.Empty) mutableState.value = EngineState.Empty(error)
                    return@supplyAsync BridgeResponse(request.requestId, request.sessionId,
                        BridgeStatus.ERROR, emptyList(), error)
                }
                val response = BridgeCodec.decodeResponse(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("bridge_dispatch", encoded).toString())
                check(response.requestId == request.requestId && response.sessionId == request.sessionId) {
                    "Engine response does not match its request"
                }
                val previous = mutableState.value as? EngineState.Ready
                if (response.isSuccess) {
                    val complete = capturedOperation is BridgeOperation.RenameFit ||
                        capturedOperation is BridgeOperation.DuplicateFit || capturedOperation is BridgeOperation.DeleteFit ||
                        capturedOperation is BridgeOperation.Snapshot && capturedOperation.fitIds.isEmpty()
                    val merged = if (complete) response.fits else {
                        val changed = response.fits.associateBy { it.id }
                        mutableLibrary.value.map { changed[it.id] ?: it } +
                            response.fits.filter { fit -> mutableLibrary.value.none { it.id == fit.id } }
                    }
                    mutableLibrary.value = merged
                    readOrganization()
                    val retained = mutableNavigation.value.retain(merged.map { it.id }.toSet())
                    if (retained != mutableNavigation.value) {
                        // Deletion already committed; never keep a deleted view active if preference I/O fails.
                        saveNavigation(retained)
                        mutableNavigation.value = retained
                    }
                    publishSelection()
                } else {
                    if (response.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) unavailable = true
                    if (previous != null) mutableState.value = previous.copy(error = response.error)
                    else mutableState.value = EngineState.Empty(response.error)
                }
                // Desktop recent use includes rejected fitting attempts. A stale
                // or malformed request leaves this independently confirmed list unchanged.
                if (!unavailable) readRecent()
                response
            } catch (error: Exception) {
                // A failed call may have committed before its reply was lost. Do
                // not accept later snapshots after losing that known boundary.
                unavailable = true
                val previous = mutableState.value as? EngineState.Ready
                if (previous != null) mutableState.value = previous.copy(error = BridgeError(
                    BridgeErrorCode.ENGINE_UNAVAILABLE, "The fitting engine returned an invalid response. Restart the app.",
                ))
                if (previous == null) mutableState.value = EngineState.Empty(BridgeError(
                    BridgeErrorCode.ENGINE_UNAVAILABLE, "Restart the app to recover the fitting engine."))
                throw error
            }
        }, executor)
    }

    fun selectFit(context: Context, id: String): CompletableFuture<Unit> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            val fit = mutableLibrary.value.single { it.id == id }
            val next = mutableNavigation.value.open(fit.id)
            if (saveNavigation(next)) {
                mutableNavigation.value = next
                publishSelection()
            }
            Unit
        }, executor)
    }

    private fun readOrganization() {
        val value = JSONObject(Python.getInstance().getModule("mobile_runtime").callAttr("library_organization").toString())
        check(value.getInt("version") == 1)
        val rows = value.getJSONObject("modified")
        mutableModified.value = rows.keys().asSequence().associateWith { id -> rows.getLong(id).also { check(it >= 0) } }
    }

    private fun readRecent() {
        mutableRecent.value = BridgeCodec.decodeRecent(Python.getInstance().getModule("mobile_runtime")
            .callAttr("recent_items").toString())
    }

    private fun publishSelection() {
        sampleId = mutableNavigation.value.activeId
        val error = if (unavailable) BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,
            "Restart the app to recover the fitting engine.") else null
        mutableState.value = mutableLibrary.value.find { it.id == sampleId }?.let { EngineState.Ready(it, error) } ?: EngineState.Empty(error)
    }

    private fun saveNavigation(next: LibraryNavigation): Boolean {
        if (!navigationWritable) return true // Explicitly reported session-only fallback.
        return try {
            navigationStore?.save(next)
            mutableNavigationError.value = null
            true
        } catch (_: Exception) {
            mutableNavigationError.value = "Could not confirm saved navigation preferences. The current view is unchanged; try again."
            false
        }
    }

    fun navigate(context: Context, change: (LibraryNavigation) -> LibraryNavigation): CompletableFuture<Unit> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            val next = change(mutableNavigation.value).retain(mutableLibrary.value.map { it.id }.toSet())
            if (saveNavigation(next)) {
                mutableNavigation.value = next
                publishSelection()
            }
            Unit
        }, executor)
    }

    fun createEmptyFit(context: Context, hull: String, name: String): CompletableFuture<BridgeResponse> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(catalog.value.hulls.any { it.name == hull }) { "Choose a bundled hull" }
            FitSpec(name, hull, 5, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
                Security(SystemSecurity.HISEC, 0.0), emptyList(), emptyList())
        }, executor).thenCompose { request(context, BridgeOperation.CreateFit(it)) }
    }

    fun createFromExample(context: Context, example: String, name: String): CompletableFuture<BridgeResponse> {
        val ready = start(context)
        val app = context.applicationContext
        return CompletableFuture.supplyAsync({
            ready.join()
            check(example in listOf("Vexor", "Celestis", "Vulture"))
            val asset = when (example) { "Vexor" -> "vexor"; "Celestis" -> "projection"; else -> "command" }
            val case = JSONObject(app.assets.open("engine/$asset.json").bufferedReader().use { it.readText() })
            val spec = if (example == "Vexor") case.apply { remove("edit") } else case.getJSONObject("source")
            BridgeCodec.decodeFitSpec(spec).copy(name = name)
        }, executor).thenCompose { request(context, BridgeOperation.CreateFit(it)) }
    }

    fun setAmmunition(context: Context, name: String): CompletableFuture<BridgeResponse> {
        val current = (state.value as? EngineState.Ready)?.fit
            ?: return CompletableFuture<BridgeResponse>().also {
                it.completeExceptionally(IllegalStateException("Wait for the fit to load"))
            }
        return request(context, BridgeOperation.SetCharges(current.id, listOf(0, 1), name),
            mapOf(current.id to current.revision))
    }

    fun bridgeDiagnostics(context: Context): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(Looper.myLooper() != Looper.getMainLooper())
            val report = JSONObject(Python.getInstance().getModule("mobile_runtime").callAttr("bridge_diagnostics").toString())
            // Capture the original Python JSON types before this first native
            // serialization normalizes whole-number decimals into integers.
            val settings = report.getJSONObject("eos_settings")
            val numericTypes = JSONObject()
            settings.keys().forEach { name ->
                when (settings.get(name)) {
                    is Int, is Long -> numericTypes.put("root.$name", "integer")
                    is Double -> numericTypes.put("root.$name", "decimal")
                }
            }
            report.put("eos_settings_numeric_types", numericTypes)
                .put("android_worker_thread", Thread.currentThread().name)
                .put("android_main_thread", Looper.myLooper() == Looper.getMainLooper()).toString()
        }, executor)
    }

    fun verifyAmmunition(context: Context): CompletableFuture<String> {
        val ready = start(context)
        // The report is returned to native tests; the UI retains its sample snapshot.
        return CompletableFuture.supplyAsync({
            ready.join()
            Python.getInstance().getModule("mobile_runtime").callAttr("verify_ammunition").toString()
        }, executor)
    }

    fun verifyProjection(context: Context): CompletableFuture<String> {
        val ready = start(context)
        val app = context.applicationContext
        return CompletableFuture.supplyAsync({
            ready.join()
            check(Looper.myLooper() != Looper.getMainLooper())
            val case = app.assets.open("engine/projection.json").bufferedReader().use { it.readText() }
            Python.getInstance().getModule("mobile_runtime").callAttr("verify_projection", case).toString()
        }, executor)
    }

    fun verifyCommand(context: Context): CompletableFuture<String> {
        val ready = start(context)
        val app = context.applicationContext
        return CompletableFuture.supplyAsync({
            ready.join()
            check(Looper.myLooper() != Looper.getMainLooper())
            val case = app.assets.open("engine/command.json").bufferedReader().use { it.readText() }
            Python.getInstance().getModule("mobile_runtime").callAttr("verify_command", case).toString()
        }, executor)
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
