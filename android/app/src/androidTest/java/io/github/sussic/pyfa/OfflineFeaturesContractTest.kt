package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OfflineFeaturesContractTest {
    private fun JSONObject.wire(): String = OfflineFeatureCodec.json(this)
    internal fun stateJson(): JSONObject = JSONObject()
        .put("version", 4).put("context", OfflineContext("a".repeat(32), "a".repeat(64), 1).json())
        .put("profiles", JSONArray().put(profile("builtin:all0", "All 0", true, null, 0))
            .put(profile("builtin:all5", "All 5", true, 5, 0))
            .put(profile("profile:" + "b".repeat(32), "Pilot", false, 5, 1)
                .put("levels", JSONObject().put("1", JSONObject.NULL).put("2", 0))
                .put("effective_levels", JSONObject().put("1", 0).put("2", 0))))
        .put("bindings", JSONObject()).put("skills", JSONArray()
            .put(JSONObject().put("skill_id", 1).put("name", "One"))
            .put(JSONObject().put("skill_id", 2).put("name", "Two")))
        .put("alpha_catalogue", JSONObject().put("available", false).put("clones", JSONArray()).put("error", "Source Alpha data unavailable"))
        .put("selected_fit_id", JSONObject.NULL)
        .put("history", JSONObject().put("undo_count", 0).put("redo_count", 0).put("limit", 100)
            .put("undo_label", JSONObject.NULL).put("redo_label", JSONObject.NULL))
    private fun profile(id: String, name: String, readonly: Boolean, level: Int?, revision: Long) = JSONObject()
        .put("profile_id", id).put("name", name).put("readonly", readonly).put("default_level", level ?: JSONObject.NULL)
        .put("alpha_clone_id", JSONObject.NULL).put("effective_levels", JSONObject().put("1", level ?: 0).put("2", level ?: 0))
        .put("levels", JSONObject()).put("revision", revision).put("implants", JSONArray()).put("sec_status", if (id == "builtin:all5") 5.0 else 0.0)
    private fun rejected(raw: String) {
        try { OfflineFeatureCodec.state(raw); fail("Invalid feature state was accepted") }
        catch (_: BridgeProtocolException) { }
    }
    @Test fun nullAndZeroStayDistinctAndCollectionsCannotBeChanged() {
        val state = OfflineFeatureCodec.state(stateJson().wire())
        val custom = state.profiles.last()
        assertNull(custom.level(1)); assertEquals(0, custom.level(2)); assertEquals(5, custom.level(3))
        try { (custom.levels as MutableMap<Int, Int?>)[1] = 5; fail("Mutable levels") }
        catch (_: UnsupportedOperationException) { }
        try { (state.profiles as MutableList<OfflineProfile>).clear(); fail("Mutable profiles") }
        catch (_: UnsupportedOperationException) { }
    }
    @Test fun malformedTypedIdentityAndHistoryFieldsAreRejected() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", true) }, { it.put("version", 1) }, { it.put("unexpected", 1) },
            { it.getJSONObject("context").put("generation", 0) },
            { it.getJSONObject("context").put("dataset_sha256", "wrong") },
            { it.getJSONArray("profiles").getJSONObject(0).put("default_level", 0) },
            { it.getJSONArray("profiles").getJSONObject(1).put("readonly", false) },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONObject("levels").put("1", false) },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONObject("levels").put("999", 5) },
            { it.getJSONArray("skills").put(JSONObject().put("skill_id", 1).put("name", "Duplicate")) },
            { it.getJSONObject("history").put("undo_label", "Uncounted") },
            { it.getJSONObject("history").put("undo_count", 101) },
            { it.put("selected_fit_id", "missing") },
            { it.getJSONArray("profiles").getJSONObject(2).put("name", "\uD800") },
        )
        mutations.forEach { mutate -> val value = stateJson(); mutate(value); rejected(value.wire()) }
        rejected(stateJson().wire().replaceFirst("\"version\":4", "\"version\":4.0"))
        rejected(stateJson().wire().replaceFirst("\"version\":4", "\"version\":4,\"version\":4"))
    }
    @Test fun responsesMustCorrelateAndUnknownCommitMustRequireReopen() {
        val context = OfflineContext("a".repeat(32), "a".repeat(64), 1)
        fun error(committed: Any, reopen: Boolean, id: String = "request") = JSONObject()
            .put("version", 4).put("request_id", id).put("ok", false).put("committed", committed)
            .put("reopen_required", reopen).put("state", JSONObject.NULL).put("bridge", JSONObject.NULL).put("error", JSONObject().put("code", "failure").put("message", "Failed"))
        assertTrue(OfflineFeatureCodec.response(error(JSONObject.NULL, true).wire(), "request", context).reopenRequired)
        assertFalse(OfflineFeatureCodec.response(error(false, false).wire(), "request", context).reopenRequired)
        for (bad in listOf(error(JSONObject.NULL, false), error(false, true), error(false, false, "other"))) {
            try { OfflineFeatureCodec.response(bad.wire(), "request", context); fail("Ambiguous response accepted") }
            catch (_: BridgeProtocolException) { }
        }
    }
    @Test fun requestEncodingDetachesCallerJsonAndRetainsExplicitNull() {
        val arguments = JSONObject().put("profile_id", "profile:" + "b".repeat(32)).put("revision", 1).put("skill_id", 1).put("level", JSONObject.NULL)
        val encoded = OfflineFeatureCodec.request("request", OfflineContext("a".repeat(32), "a".repeat(64), 1), "set_profile_skill", arguments, null)
        arguments.put("level", 5)
        val request = JSONObject(encoded)
        assertTrue(request.getJSONObject("arguments").isNull("level"))
        assertTrue(request.isNull("anchor_fit_id"))
    }
    @Test fun cloneIdentityAndEffectiveLevelsAreStrictDetachedSourceValues() {
        // Synthetic wire identities, never a cap table or a numerical oracle.
        val root = stateJson().put("alpha_catalogue", JSONObject().put("available", true).put("error", JSONObject.NULL)
            .put("clones", JSONArray().put(JSONObject().put("alpha_clone_id", 41).put("name", "Synthetic choice"))))
        val profile = root.getJSONArray("profiles").getJSONObject(2).put("alpha_clone_id", 41)
        val state = OfflineFeatureCodec.state(root.wire()); val value = state.profiles.last()
        assertEquals(41, value.alphaCloneId); assertNull(value.level(1)); assertEquals(0, value.level(2))
        assertEquals(0, value.effectiveLevel(1)); assertEquals(0, value.effectiveLevel(2))
        profile.getJSONObject("effective_levels").put("1", 5)
        assertEquals(0, value.effectiveLevel(1))
        profile.getJSONObject("effective_levels").put("1", 0)
        try { (value.effectiveLevels as MutableMap<Int, Int>)[1] = 5; fail("Mutable effective levels") }
        catch (_: UnsupportedOperationException) { }
        try { (state.alphaCatalogue.clones as MutableList<OfflineAlphaClone>).clear(); fail("Mutable clone choices") }
        catch (_: UnsupportedOperationException) { }
        val changes: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", 3) },
            { it.getJSONArray("profiles").getJSONObject(2).put("alpha_clone_id", 42) },
            { it.getJSONArray("profiles").getJSONObject(2).put("alpha_clone_id", 41.0) },
            { it.getJSONArray("profiles").getJSONObject(2).put("alpha_clone_id", true) },
            { it.getJSONArray("profiles").getJSONObject(0).put("alpha_clone_id", 41) },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONObject("effective_levels").remove("1") },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONObject("effective_levels").put("1", JSONObject.NULL) },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONObject("effective_levels").put("1", 1.0) },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONObject("effective_levels").put("3", 0) },
            { it.getJSONObject("alpha_catalogue").put("available", false) },
            { it.getJSONObject("alpha_catalogue").put("error", "Contradictory") },
            { it.getJSONObject("alpha_catalogue").getJSONArray("clones").put(JSONObject().put("alpha_clone_id", 41).put("name", "Duplicate")) },
        )
        changes.forEach { change -> val bad = JSONObject(root.wire()); change(bad); rejected(bad.wire()) }
        val absent = stateJson(); absent.remove("alpha_catalogue"); rejected(absent.wire())
    }
    @Test fun cloneRequestKeepsOmegaNullAndRefusesProtectedOrMalformedValues() {
        val context = OfflineContext("a".repeat(32), "a".repeat(64), 1)
        fun args(value: Any) = JSONObject().put("profile_id", "profile:" + "b".repeat(32)).put("revision", 1).put("alpha_clone_id", value)
        val request = JSONObject(OfflineFeatureCodec.request("clone", context, "set_profile_clone", args(JSONObject.NULL), null))
        assertEquals(4, request.getInt("version")); assertTrue(request.getJSONObject("arguments").isNull("alpha_clone_id"))
        for (value in listOf(true, 0, -1, 1.0, "1", Long.MAX_VALUE)) {
            try { OfflineFeatureCodec.request("clone", context, "set_profile_clone", args(value), null); fail("Invalid clone accepted") }
            catch (_: BridgeProtocolException) { }
        }
        try { OfflineFeatureCodec.request("clone", context, "set_profile_clone", args(41).put("profile_id", "builtin:all5"), null); fail("Protected clone accepted") }
        catch (_: BridgeProtocolException) { }
    }
}
