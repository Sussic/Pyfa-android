package io.github.sussic.pyfa

import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.ExecutionException
import java.util.concurrent.TimeUnit
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.OutputStream
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OfflineExportFilesTest {
    @Test fun malformedRetainedPreferencesFailExplicitlyAndCanBeReplaced() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val preferences = context.getSharedPreferences("eft-export-options", Context.MODE_PRIVATE)
        val old = preferences.getString("version-1-options", null)
        try {
            assertTrue(preferences.edit().putString("version-1-options", "{\"cargo\":true}").commit())
            try { OfflineExportFiles.loadOptions(context).get(30, TimeUnit.SECONDS); fail("Malformed preferences were accepted") }
            catch (failure: ExecutionException) { assertTrue(failure.cause is BridgeProtocolException) }
            val options = OfflineExportOptions(cargo = false, boosters = false)
            assertTrue(OfflineExportFiles.saveOptions(context, options).get(30, TimeUnit.SECONDS))
            assertEquals(options, OfflineExportFiles.loadOptions(context).get(30, TimeUnit.SECONDS))
        } finally {
            val edit = preferences.edit()
            if (old == null) edit.remove("version-1-options") else edit.putString("version-1-options", old)
            assertTrue(edit.commit())
        }
    }
    @Test fun stalePreviewNeverOpensOrTruncatesDestination() {
        var opened = false
        val outcome = OfflineExportFiles.writeSnapshot("[Vexor, Test]\n", { false }) { opened = true; ByteArrayOutputStream() }
        assertFalse(opened); assertFalse(outcome.written); assertTrue(outcome.message.contains("No EFT text was written"))
    }
    @Test fun staleAfterProviderOpenClosesWithoutWriting() {
        var current = true; var closed = false
        val bytes = object : ByteArrayOutputStream() { override fun close() { closed = true; super.close() } }
        val outcome = OfflineExportFiles.writeSnapshot("[Vexor, Test]\n", { current }) { current = false; bytes }
        assertFalse(outcome.written); assertEquals(0, bytes.size()); assertTrue(closed)
    }
    @Test fun utf8TextIsExactAndSuccessRequiresClose() {
        val text = "[Vexor, 探索]\r\n\r\nWarrior I x2\n"
        var closed = false
        val bytes = object : ByteArrayOutputStream() { override fun close() { closed = true; super.close() } }
        val outcome = OfflineExportFiles.writeSnapshot(text, { true }) { bytes }
        assertTrue(outcome.written); assertTrue(closed); assertArrayEquals(text.toByteArray(Charsets.UTF_8), bytes.toByteArray())
        val closeFails = object : ByteArrayOutputStream() { override fun close() { throw IOException("provider close failed") } }
        val failed = OfflineExportFiles.writeSnapshot(text, { true }) { closeFails }
        assertFalse(failed.written); assertTrue(failed.message.contains("partial file"))
    }
    @Test fun deniedNullAndPartialProvidersNeverReportSuccess() {
        assertFalse(OfflineExportFiles.writeSnapshot("text", { true }) { null }.written)
        val denied = OfflineExportFiles.writeSnapshot("text", { true }) { throw SecurityException("denied") }
        assertFalse(denied.written); assertTrue(denied.message.contains("denied"))
        var closed = false
        val partial = object : OutputStream() {
            override fun write(value: Int) { throw IOException("provider interrupted") }
            override fun close() { closed = true }
        }
        val outcome = OfflineExportFiles.writeSnapshot("text", { true }) { partial }
        assertFalse(outcome.written); assertTrue(closed); assertTrue(outcome.message.contains("partial file"))
    }
}
