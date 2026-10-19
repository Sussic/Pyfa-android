package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** EFT remains import-v1, including receipt replay of a fit removed after import. */
@RunWith(AndroidJUnit4::class)
class CharacterImplantsImportContractTest {
    private fun JSONObject.wire(): String = OfflineFeatureCodec.json(this)
    private val session = "a".repeat(32)
    private val fit = "f".repeat(32)
    private fun request() = JSONObject().put("version", 1).put("operation", "import_eft").put("request_id", "import")
        .put("dataset", "a".repeat(64)).put("graph", JSONObject().put("generation", 1).put("token", "b".repeat(32)))
        .put("profile", JSONObject().put("id", "builtin:all5").put("revision", 0))
        .put("documents", JSONArray().put(JSONObject().put("label", "Fit").put("text", "[Rifter, Fit]")))
    private fun response(): JSONObject {
        val state = OfflineFeaturesContractTest().stateJson().also { it.getJSONObject("context").put("generation", 2) }
        return JSONObject().put("version", 1).put("request_id", "import").put("ok", true).put("committed", true).put("reopen_required", false)
            .put("import_result", JSONObject().put("version", 1).put("operation", "import_eft").put("ok", true).put("import_committed", true)
                .put("reopen_required", false).put("replayed", true).put("fit_ids", JSONArray().put(fit)).put("missing_fit_ids", JSONArray().put(fit))
                .put("current_graph", JSONObject().put("generation", 2).put("token", "c".repeat(32))).put("diagnostics", JSONArray())
                .put("receipt", JSONObject().put("fingerprint", "d".repeat(64)).put("fit_ids", JSONArray().put(fit)).put("names", JSONArray().put("Fit"))
                    .put("fit_revisions", JSONArray().put(1)).put("generation", 2)))
            .put("state", state).put("bridge", JSONObject().put("version", 1).put("request_id", "bootstrap").put("session_id", session)
                .put("status", "ok").put("fits", JSONArray()).put("error", JSONObject.NULL))
    }
    private fun reject(raw: JSONObject) {
        try { OfflineImportCodec.result(raw.wire(), "import", session, request()); fail("Mixed import/feature versions accepted") }
        catch (_: BridgeProtocolException) { }
    }
    @Test fun independentOuterV1ConsumesFeatureV3WithoutChangingReceiptReplay() {
        assertEquals(1, OfflineImportCodec.request(request().wire()).getInt("version"))
        val value = OfflineImportCodec.result(response().wire(), "import", session, request())
        assertTrue(value.ok); assertTrue(value.replayed); assertEquals(listOf(fit), value.missingFitIds)
        assertEquals(2L, value.state!!.context.generation); assertTrue(value.state!!.profiles.all { it.implants.isEmpty() })
    }
    @Test fun changingOuterVersionOrDowngradingEmbeddedFeatureStateIsRejected() {
        reject(response().put("version", 2))
        reject(response().also { it.getJSONObject("state").put("version", 1) })
        reject(response().also { it.getJSONObject("import_result").put("version", 2) })
        reject(response().also { it.getJSONObject("state").getJSONObject("context").put("session_id", "e".repeat(32)) })
    }
}
