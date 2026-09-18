package io.github.sussic.pyfa

import android.content.Context
import android.os.Looper
import android.os.Debug
import android.os.Process
import android.os.SystemClock
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.CompletableFuture
import java.util.concurrent.Executors
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject

sealed interface EngineState {
    data object Loading : EngineState
    data class Ready(val result: String) : EngineState
    data class Failed(val message: String) : EngineState
}

/** One process-owned worker: EOS and its SQLite session never cross threads. */
object EngineRuntime {
    private val executor = Executors.newSingleThreadExecutor { task -> Thread(task, "pyfa-engine") }
    private val mutableState = MutableStateFlow<EngineState>(EngineState.Loading)
    val state = mutableState.asStateFlow()
    private var startup: CompletableFuture<String>? = null
    private var startupMetrics: JSONObject? = null // Written/read only on the engine worker.
    private var startupDrawRecorded = false

    @Synchronized
    fun start(context: Context): CompletableFuture<String> {
        startup?.let { return it }
        val app = context.applicationContext
        val requested = SystemClock.elapsedRealtimeNanos()
        return submit {
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
            val result = Python.getInstance().getModule("mobile_runtime")
                .callAttr("boot", database.absolutePath, manifestText, case).toString()
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
            result
        }.also { startup = it }
    }

    /** Called after Compose reports the ready data drawn; no disk I/O on the UI thread. */
    @Synchronized
    fun recordStartupDraw(context: Context) {
        if (!BuildConfig.DEBUG || startupDrawRecorded || state.value !is EngineState.Ready) return
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

    fun setAmmunition(context: Context, name: String): CompletableFuture<String> {
        val ready = start(context)
        return submit {
            ready.join()
            Python.getInstance().getModule("mobile_runtime").callAttr("set_ammunition", name).toString()
        }
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

    private fun submit(action: () -> String): CompletableFuture<String> =
        CompletableFuture.supplyAsync({
            try {
                action().also { mutableState.value = EngineState.Ready(it) }
            } catch (error: Exception) {
                mutableState.value = EngineState.Failed(error.message ?: error.javaClass.simpleName)
                throw error
            }
        }, executor)

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
