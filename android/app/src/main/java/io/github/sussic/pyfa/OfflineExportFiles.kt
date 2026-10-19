package io.github.sussic.pyfa

import android.content.Context
import android.content.Intent
import android.net.Uri
import java.io.FileNotFoundException
import java.io.OutputStream
import java.util.concurrent.CompletableFuture
import java.util.concurrent.Executors

internal data class OfflineExportWriteResult(val written: Boolean, val message: String)

/** Document-provider and preference I/O never runs on the UI or EOS worker. */
internal object OfflineExportFiles {
    private val executor = Executors.newSingleThreadExecutor { task -> Thread(task, "pyfa-export-files") }
    private const val PREFERENCES = "eft-export-options"
    private const val OPTIONS = "version-1-options"

    fun loadOptions(context: Context): CompletableFuture<OfflineExportOptions> {
        val app = context.applicationContext
        return CompletableFuture.supplyAsync({
            app.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).getString(OPTIONS, null)
                ?.let(OfflineExportCodec::options) ?: OfflineExportOptions()
        }, executor)
    }
    fun saveOptions(context: Context, options: OfflineExportOptions): CompletableFuture<Boolean> {
        val app = context.applicationContext
        val encoded = options.json().toString()
        return CompletableFuture.supplyAsync({
            app.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE).edit().putString(OPTIONS, encoded).commit()
        }, executor)
    }
    fun write(context: Context, uri: Uri, preview: OfflineExportPreview,
        current: () -> Boolean): CompletableFuture<OfflineExportWriteResult> {
        val resolver = context.applicationContext.contentResolver
        return CompletableFuture.supplyAsync({
            if (uri.scheme != "content") OfflineExportWriteResult(false, "The selected destination is not a document provider. No EFT text was written.")
            else writeSnapshot(checkNotNull(preview.text), current) { resolver.openOutputStream(uri, "wt") }
        }, executor)
    }

    /** Kept independently testable: rejected stale snapshots never even open/truncate a destination. */
    internal fun writeSnapshot(text: String, current: () -> Boolean, open: () -> OutputStream?): OfflineExportWriteResult {
        if (!current()) return OfflineExportWriteResult(false, "The fit or export options changed while choosing the destination. No EFT text was written; preview again. The provider may have created an empty file.")
        val output = try { open() ?: return OfflineExportWriteResult(false, "The document provider did not open a writable file. No EFT text was written.") }
        catch (_: FileNotFoundException) { return OfflineExportWriteResult(false, "The selected file could not be opened. No EFT text was written.") }
        catch (_: SecurityException) { return OfflineExportWriteResult(false, "Access to the selected file was denied. No EFT text was written.") }
        catch (_: Exception) { return OfflineExportWriteResult(false, "The selected destination could not be opened. No EFT text was written.") }
        return try {
            output.use { stream ->
                if (!current()) return OfflineExportWriteResult(false, "The fit changed while the provider opened the destination. No EFT text was written; the selected file may be empty.")
                stream.write(text.toByteArray(Charsets.UTF_8)); stream.flush()
            }
            OfflineExportWriteResult(true, "EFT text was written to the selected file.")
        } catch (_: Exception) {
            OfflineExportWriteResult(false, "The file write could not be confirmed. The destination may contain a partial file; choose another destination to retry.")
        }
    }

    fun shareChooser(preview: OfflineExportPreview): Intent {
        require(preview.ok && !preview.text.isNullOrBlank())
        val intent = Intent(Intent.ACTION_SEND).setType("text/plain")
            .putExtra(Intent.EXTRA_TEXT, preview.text).putExtra(Intent.EXTRA_SUBJECT, preview.filename)
        return Intent.createChooser(intent, "Share EFT fit")
    }
}
