package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.UUID
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OfflineImportRecoveryTest {
    private fun request(id: String = "fixed-retry-id") = JSONObject().put("version", 1).put("operation", "import_eft")
        .put("request_id", id).put("dataset", "a".repeat(64))
        .put("graph", JSONObject().put("generation", 1).put("token", "b".repeat(32)))
        .put("profile", JSONObject().put("id", "builtin:all5").put("revision", 0))
        .put("documents", JSONArray().put(JSONObject().put("label", "Unicode source").put("text", "[Vexor, 探索]\r\n\r\nWarrior I x2\r\n")))
    @Test fun exactSourceAndIdentitySurviveReopenAndCannotBeReplaced() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = File(context.cacheDir, "eft-recovery-${UUID.randomUUID()}.json")
        val original = request().toString()
        try {
            OfflineImportStore(file).save(original)
            assertEquals(original, OfflineImportStore(file).load())
            OfflineImportStore(file).save(original) // Idempotent retry of the same bytes.
            try { OfflineImportStore(file).save(request("different-id").toString()); fail("Replaced unresolved import") }
            catch (_: IllegalStateException) { }
            assertEquals(original, OfflineImportStore(file).load())
            OfflineImportStore(file).clear(); assertNull(OfflineImportStore(file).load())
            file.writeText("not a valid request")
            try { OfflineImportStore(file).save(original); fail("Overwrote damaged recovery data") }
            catch (_: Exception) { }
            assertEquals("not a valid request", file.readText())
        } finally { file.delete(); File(file.path + ".bak").delete(); File(file.path + ".new").delete() }
    }
    @Test fun contradictoryInnerOutcomeIsNeverTreatedAsSafeToClear() {
        val diagnostic = JSONObject().put("document", JSONObject.NULL).put("label", JSONObject.NULL).put("line", 0)
            .put("code", "unknown").put("message", "Restart and retry")
        val inner = JSONObject().put("version", 1).put("operation", "import_eft").put("ok", false)
            .put("import_committed", JSONObject.NULL).put("reopen_required", true).put("replayed", false)
            .put("fit_ids", JSONArray()).put("diagnostics", JSONArray().put(diagnostic))
        val response = JSONObject().put("version", 1).put("request_id", "fixed-retry-id").put("ok", false)
            .put("committed", false).put("reopen_required", false).put("import_result", inner)
            .put("state", JSONObject.NULL).put("bridge", JSONObject.NULL)
        try { OfflineImportCodec.result(response.toString(), "fixed-retry-id", "session", request()); fail("Accepted contradictory commit status") }
        catch (_: BridgeProtocolException) { }
        response.put("committed", JSONObject.NULL).put("reopen_required", true)
        val result = OfflineImportCodec.result(response.toString(), "fixed-retry-id", "session", request())
        assertNull(result.committed); assertTrue(result.reopenRequired)
    }
}
