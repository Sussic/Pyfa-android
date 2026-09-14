package io.github.sussic.pyfa

import android.content.Context
import android.os.Looper
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

    @Synchronized
    fun start(context: Context): CompletableFuture<String> {
        startup?.let { return it }
        val app = context.applicationContext
        return submit {
            check(Looper.myLooper() != Looper.getMainLooper())
            val manifestText = app.assets.open("engine/manifest.json").bufferedReader().use { it.readText() }
            val manifest = JSONObject(manifestText)
            val expectedHash = manifest.getString("database_sha256")
            val directory = File(app.filesDir, "game").apply { mkdirs() }
            val database = File(directory, "eve-$expectedHash.db")
            if (!database.isFile || sha256(database) != expectedHash) {
                val staging = File(directory, "eve-install.tmp")
                try {
                    app.assets.open("engine/eve.db").use { source ->
                        staging.outputStream().use { destination -> source.copyTo(destination) }
                    }
                    check(staging.length() == manifest.getLong("database_bytes")) { "Bundled database size mismatch" }
                    check(sha256(staging) == expectedHash) { "Bundled database checksum mismatch" }
                    check(staging.renameTo(database)) { "Could not install bundled game data" }
                } finally {
                    staging.delete()
                }
            }
            if (!Python.isStarted()) Python.start(AndroidPlatform(app))
            val case = app.assets.open("engine/vexor.json").bufferedReader().use { it.readText() }
            Python.getInstance().getModule("mobile_runtime")
                .callAttr("boot", database.absolutePath, manifestText, case).toString()
        }.also { startup = it }
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
