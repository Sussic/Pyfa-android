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
    private var startup: CompletableFuture<FitSnapshot?>? = null
    private var sessionId: String? = null // Worker only.
    private var sampleId: String? = null // Worker only.
    private var unavailable = false // A transport fault may follow an unknown commit.
    private var startupMetrics: JSONObject? = null // Written/read only on the engine worker.
    private var startupDrawRecorded = false
    private var ephemeralDiagnostics = false // Selected before startup by the debug test runner.

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
                val savedSampleId = module.callAttr("bridge_sample_id").toString()
                val result = bootstrap.fits.find { it.id == savedSampleId } ?: bootstrap.fits.firstOrNull()
                sessionId = bootstrap.sessionId
                sampleId = result?.id
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
                mutableState.value = result?.let { EngineState.Ready(it) } ?: EngineState.Empty()
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
                    val selected = merged.find { it.id == sampleId } ?: merged.firstOrNull()
                    sampleId = selected?.id
                    mutableState.value = selected?.let { EngineState.Ready(it) } ?: EngineState.Empty()
                } else {
                    if (response.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) unavailable = true
                    if (previous != null) mutableState.value = previous.copy(error = response.error)
                    else mutableState.value = EngineState.Empty(response.error)
                }
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
            sampleId = fit.id
            mutableState.value = EngineState.Ready(fit)
            Unit
        }, executor)
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
            JSONObject(Python.getInstance().getModule("mobile_runtime").callAttr("bridge_diagnostics").toString())
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
