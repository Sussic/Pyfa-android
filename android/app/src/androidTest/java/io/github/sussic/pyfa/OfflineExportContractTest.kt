package io.github.sussic.pyfa

import android.content.Intent
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OfflineExportContractTest {
    private fun request() = OfflineExportRequest("export-request", OfflineContext("session", "a".repeat(64), 4), "fit", 3,
        OfflineExportOptions(loadedCharges = false, cargo = true, implants = false, boosters = true, mutations = false))
    private fun response() = JSONObject().put("version", 1).put("request_id", "export-request").put("ok", true)
        .put("context", request().context.json()).put("fit_id", "fit").put("revision", 3)
        .put("text", "[Vexor, 探索]\n\nWarrior I x2\n").put("filename", "探索.txt")
        .put("diagnostics", JSONArray().put(JSONObject().put("code", "eft_loss").put("message", "Profiles and linked fits are not included.")))
        .put("error", JSONObject.NULL)
    @Test fun exactTextOptionsAndDiagnosticsRemainIntact() {
        val expected = request()
        assertEquals(expected.options, OfflineExportCodec.options(JSONObject(expected.json()).getJSONObject("options").toString()))
        val preview = OfflineExportCodec.preview(response().toString(), expected)
        assertTrue(preview.ok); assertEquals(response().getString("text"), preview.text); assertEquals("探索.txt", preview.filename)
        assertEquals("eft_loss", preview.diagnostics.single().code)
        try { (preview.diagnostics as MutableList<OfflineExportDiagnostic>).clear(); fail("Mutable warnings") }
        catch (_: UnsupportedOperationException) { }
    }
    @Test fun malformedStaleEmptyAndUnsafeOutputIsRejected() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", true) }, { it.put("extra", 1) }, { it.put("request_id", "other") },
            { it.getJSONObject("context").put("generation", 5) }, { it.put("fit_id", "other") },
            { it.put("revision", 4) }, { it.put("revision", true) },
            { it.put("text", "") }, { it.put("text", " \n\t") }, { it.put("text", "bad\u0000text") },
            { it.put("text", "\uD800") }, { it.put("text", "x".repeat(1024 * 1024 + 1)) },
            { it.put("filename", "../fit.txt") }, { it.put("filename", "dir\\fit.txt") },
            { it.put("filename", "fit.html") }, { it.put("filename", ".txt") },
            { it.put("error", JSONObject().put("code", "failure").put("message", "Cannot export")) },
        )
        mutations.forEach { mutate ->
            val value = response(); mutate(value)
            try { OfflineExportCodec.preview(value.toString(), request()); fail("Accepted invalid export") }
            catch (_: BridgeProtocolException) { }
        }
        try { OfflineExportCodec.preview(response().toString().replaceFirst("\"revision\":3", "\"revision\":3.0"), request()); fail("Accepted decimal revision") }
        catch (_: BridgeProtocolException) { }
    }
    @Test fun explicitFailureNeverExposesTextAndUnavailableSessionCanHaveNoRequestId() {
        val error = response().put("ok", false).put("request_id", JSONObject.NULL).put("context", JSONObject.NULL)
            .put("fit_id", JSONObject.NULL).put("revision", JSONObject.NULL).put("text", JSONObject.NULL).put("filename", JSONObject.NULL)
            .put("error", JSONObject().put("code", "engine_unavailable").put("message", "Restart before exporting."))
        val decoded = OfflineExportCodec.preview(error.toString(), request())
        assertFalse(decoded.ok); assertNull(decoded.text); assertNull(decoded.filename)
        assertEquals("engine_unavailable", decoded.error!!.code)
        assertTrue(decoded.requiresEngineReopen)
        assertTrue(decoded.copy(error = OfflineFeatureError("reopen_required", "Reopen storage.")).requiresEngineReopen)
        assertFalse(decoded.copy(error = OfflineFeatureError("unsupported_mutation", "Choose exclusions.")).requiresEngineReopen)
        assertFalse(OfflineExportCodec.preview(response().toString(), request()).requiresEngineReopen)
        error.put("text", "[Vexor, leaked]\n")
        try { OfflineExportCodec.preview(error.toString(), request()); fail("Failure exposed text") }
        catch (_: BridgeProtocolException) { }
    }
    @Suppress("DEPRECATION")
    @Test fun shareIsAChooserWithOnlyReviewedPlainText() {
        val preview = OfflineExportCodec.preview(response().toString(), request())
        val chooser = OfflineExportFiles.shareChooser(preview)
        assertEquals(Intent.ACTION_CHOOSER, chooser.action)
        val send = chooser.getParcelableExtra<Intent>(Intent.EXTRA_INTENT)!!
        assertEquals(Intent.ACTION_SEND, send.action); assertEquals("text/plain", send.type)
        assertEquals(preview.text, send.getStringExtra(Intent.EXTRA_TEXT))
        assertEquals(preview.filename, send.getStringExtra(Intent.EXTRA_SUBJECT))
        assertNull(send.component); assertNull(send.`package`); assertNull(send.data); assertNull(send.getParcelableExtra<android.net.Uri>(Intent.EXTRA_STREAM))
    }
}
