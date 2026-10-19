package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic shape/type witnesses. Neither numerical parity nor Android execution is implied. */
@RunWith(AndroidJUnit4::class)
class OfflineTargetProfilesContractTest {
    private val target = "target:" + "b".repeat(32)
    private val session = OfflineContext("a".repeat(32), "c".repeat(64), 7)
    private fun request(id: String? = target) = OfflineTargetRequest("target-test", session, null, OfflineTargetView(selectedTargetId = id))
    private fun values() = JSONObject().put("emAmount", 0.0).put("thermalAmount", 1.0).put("kineticAmount", 0.25)
        .put("explosiveAmount", 0).put("maxVelocity", JSONObject.NULL).put("signatureRadius", JSONObject.NULL)
        .put("radius", -0.0).put("hp", 0.0)
    private fun metadata(id: String = target) = JSONObject().put("target_id", id).put("kind", if (id.startsWith("target:builtin:")) "builtin" else "custom")
        .put("name", "[Synthetic] Target").put("revision", if (id.startsWith("target:builtin:")) 0 else 3).put("bound_fit_count", 0)
    private fun root(input: OfflineTargetRequest = request()): JSONObject {
        val detail = input.view.selectedTargetId?.let { id -> metadata(id).put("values", values())
            .put("effective", values().put("maxVelocity", 0).put("radius", 0))
            .put("bound_fits", JSONObject().put("offset", input.view.boundOffset).put("limit", 50).put("total", 0).put("entries", JSONArray())) }
        val state = JSONObject().put("version", 1).put("context", input.context.json()).put("fit_id", input.fitId ?: JSONObject.NULL)
            .put("fit_revision", if (input.fitId == null) JSONObject.NULL else 2)
            .put("selection", JSONObject().put("kind", if (input.fitId == null) "no_fit" else "none").put("target_id", JSONObject.NULL).put("binding_revision", JSONObject.NULL))
            .put("page", JSONObject().put("query", input.view.query).put("offset", input.view.offset).put("limit", input.view.limit)
                .put("total", 1).put("entries", if (input.view.offset == 0L) JSONArray().put(metadata(input.view.selectedTargetId ?: target)) else JSONArray()))
            .put("detail", detail ?: JSONObject.NULL).put("history", JSONObject().put("undo_count", 0).put("redo_count", 0).put("limit", 100)
                .put("undo_label", JSONObject.NULL).put("redo_label", JSONObject.NULL))
        return JSONObject().put("version", 1).put("request_id", input.requestId).put("ok", true).put("committed", false)
            .put("reopen_required", false).put("state", state).put("bridge", JSONObject.NULL).put("error", JSONObject.NULL)
    }
    private fun decode(row: JSONObject, input: OfflineTargetRequest = request()) = OfflineTargetCodec.response(OfflineFeatureCodec.json(row), input)
    private fun reject(row: JSONObject, input: OfflineTargetRequest = request()) = rejectRaw(OfflineFeatureCodec.json(row), input)
    private fun rejectRaw(raw: String, input: OfflineTargetRequest = request()) {
        try { OfflineTargetCodec.response(raw, input); fail("Accepted malformed target response") }
        catch (_: BridgeProtocolException) { }
        catch (_: org.json.JSONException) { }
        catch (_: ArithmeticException) { }
    }
    private fun invalid(input: OfflineTargetRequest) {
        try { input.json(); fail("Accepted invalid request") } catch (_: BridgeProtocolException) { } catch (_: org.json.JSONException) { }
    }
    private fun args(vararg pairs: Pair<String, Any>) = OfflineFeatureCodec.json(JSONObject().also { row -> pairs.forEach { row.put(it.first, it.second) } })
    private fun bootstrap(input: OfflineTargetRequest) = JSONObject().put("version", 1).put("request_id", "bootstrap")
        .put("session_id", input.context.sessionId).put("status", "ok").put("fits", JSONArray()).put("error", JSONObject.NULL)

    @Test fun rawKindsNullsAndSignedZeroRemainDistinctFromEffectiveZero() {
        val value = decode(root()).state!!.detail!!
        assertTrue(value.values.fields.getValue("explosiveAmount") is Long)
        assertTrue(value.values.fields.getValue("emAmount") is Double)
        assertNull(value.values.fields["maxVelocity"])
        assertEquals((-0.0).toBits(), (value.values.fields.getValue("radius") as Double).toBits())
        assertEquals(0L, value.effective.fields.getValue("radius"))
        assertEquals(0L, value.effective.fields.getValue("maxVelocity"))
        assertNull(value.effective.fields["signatureRadius"])
        assertEquals(0.0, value.effective.fields.getValue("hp"))
    }
    @Test fun all195BuiltinIdsAreReachableButIdealZeroIsNot() {
        for (id in -195..-1) {
            val input = request("target:builtin:$id")
            assertTrue(decode(root(input), input).state!!.detail!!.entry.readonly)
            input.json()
        }
        for (id in listOf("target:builtin:0", "target:builtin:-196", "target:builtin:-01", "target:builtin:+1", "target:bad")) invalid(request(id))
    }
    @Test fun zeroSignatureAndHpAreNotUnlimitedAndNegativeZeroIsRetained() {
        val row = root(); val detail = row.getJSONObject("state").getJSONObject("detail")
        for (key in listOf("signatureRadius", "hp")) { detail.getJSONObject("values").put(key, -0.0); detail.getJSONObject("effective").put(key, -0.0) }
        val result = decode(row).state!!.detail!!
        assertEquals((-0.0).toBits(), (result.effective.fields.getValue("signatureRadius") as Double).toBits())
        assertEquals((-0.0).toBits(), (result.effective.fields.getValue("hp") as Double).toBits())
        detail.getJSONObject("effective").put("hp", JSONObject.NULL); reject(row)
    }
    @Test fun namedLibraryRawIntegersUseSignedLongRangeWithoutNarrowingEditorFloats() {
        // Named-library records reject integers outside the existing wire decoder's
        // range. Actual built-in integers and every finite editor float remain supported.
        val row = root(); val detail = row.getJSONObject("state").getJSONObject("detail")
        detail.getJSONObject("values").put("hp", Long.MAX_VALUE)
        detail.getJSONObject("effective").put("hp", Long.MAX_VALUE)
        assertEquals(Long.MAX_VALUE, decode(row).state!!.detail!!.values.fields["hp"])
        rejectRaw(OfflineFeatureCodec.json(row).replace(Long.MAX_VALUE.toString(), "9223372036854775808"))
        detail.getJSONObject("values").put("hp", 1e30)
        detail.getJSONObject("effective").put("hp", 1e30)
        assertEquals(1e30, decode(row).state!!.detail!!.values.fields["hp"])
    }
    @Test fun effectiveProjectionRejectsChangedKindsAndZeroSigns() {
        for ((key, wrong) in listOf("radius" to 0.0, "maxVelocity" to JSONObject.NULL, "explosiveAmount" to 0.0, "emAmount" to -0.0, "hp" to 0)) {
            val row = root(); row.getJSONObject("state").getJSONObject("detail").getJSONObject("effective").put(key, wrong); reject(row)
        }
    }
    @Test fun fullEditorEmitsDecimalTokensForIntegralInputsAndBlankResistances() {
        val draft = OfflineTargetDraft("create", null, null, session.sessionId, "Target", listOf("", "100", "0", "0", "", "0", "-0.0", "0"))
        val input = request(null).copy(operation = "create", argumentsJson = args("name" to draft.name, "values" to draft.values()))
        val parsed = OfflineFeatureCodec.parse(input.json()).getJSONObject("arguments").getJSONObject("values")
        for (key in TARGET_FIELDS.filter { it != "maxVelocity" }) assertTrue("$key lost decimal kind", parsed.get(key) is Double)
        assertSame(JSONObject.NULL, parsed.get("maxVelocity"))
        assertEquals((-0.0).toBits(), (parsed.get("radius") as Double).toBits())
        invalid(input.copy(argumentsJson = args("name" to "Target", "values" to draft.values().put("hp", 0))))
    }
    @Test fun duplicateAndAssignUseIdentityOnlyAndNeverReserializeSourceValues() {
        val source = "target:builtin:-149"
        for (operation in listOf("duplicate", "assign")) {
            val parameters = JSONObject().put("target_id", source).put("revision", 0)
            if (operation == "duplicate") parameters.put("name", "Independent copy") else parameters.put("fit_revision", 9)
            val input = request(source).copy(fitId = if (operation == "assign") "f".repeat(32) else null,
                operation = operation, argumentsJson = OfflineFeatureCodec.json(parameters))
            assertFalse(OfflineFeatureCodec.parse(input.json()).getJSONObject("arguments").has("values"))
        }
    }
    @Test fun unicodeCodePointLimitControlValidationAndPythonTrimAgree() {
        val astral = "\uD83D\uDE80"
        assertEquals(astral.repeat(200), OfflineTargetCodec.name("\u0085\u00A0" + astral.repeat(200) + "\u3000"))
        for (name in listOf(astral.repeat(201), "A\u007FB", "A\u0085B", "\uD800", "\uDC00", "  ")) {
            try { OfflineTargetCodec.name(name); fail("Accepted invalid name") } catch (_: BridgeProtocolException) { }
        }
        assertEquals("All 5", OfflineTargetCodec.name("All 5"))
        assertEquals("[NPC] Mixed Case", OfflineTargetCodec.name(" [NPC] Mixed Case "))
    }
    @Test fun namesQueriesAndRequestsHaveStrictBoundsAndFields() {
        invalid(request().copy(view = request().view.copy(query = "x".repeat(201))))
        invalid(request().copy(view = request().view.copy(limit = 51)))
        invalid(request().copy(requestId = "bad\nID"))
        invalid(request().copy(argumentsJson = "{\"unexpected\":0}"))
        invalid(request().copy(argumentsJson = "{\"x\":1,\"x\":2}"))
        invalid(request().copy(operation = "unknown"))
        invalid(request().copy(fitId = "not-a-fit"))
    }
    @Test fun negativeAndNonfiniteOrOutsideResistanceEditorValuesReject() {
        for ((key, wrong) in listOf("hp" to -1.0, "signatureRadius" to -1.0, "emAmount" to 1.01)) {
            invalid(request().copy(operation = "create", argumentsJson = args("name" to "Custom", "values" to values().put("explosiveAmount", 0.0).put(key, wrong))))
        }
        rejectRaw(OfflineFeatureCodec.json(root()).replace("0.25", "1e999"))
    }
    @Test fun unknownDuplicateFieldsWrongScalarKindsAndTruncatedPageReject() {
        reject(root().put("unexpected", 0))
        val raw = OfflineFeatureCodec.json(root()); rejectRaw(raw.replace("\"version\":1", "\"version\":1,\"version\":1"))
        val version = root().put("version", 1.0); reject(version)
        val count = root(); count.getJSONObject("state").getJSONObject("page").put("total", 2); reject(count)
        val boolean = root(); boolean.getJSONObject("state").getJSONObject("detail").getJSONObject("values").put("hp", false); reject(boolean)
    }
    @Test fun outOfRangePagesAreEmptyWithoutClampingOrLostDetail() {
        val input = request().copy(view = request().view.copy(offset = Long.MAX_VALUE, boundOffset = 200))
        val result = decode(root(input), input).state!!
        assertEquals(Long.MAX_VALUE, result.view.offset); assertTrue(result.entries.isEmpty()); assertNotNull(result.detail)
        val clamped = root(input); clamped.getJSONObject("state").getJSONObject("page").put("offset", 0); reject(clamped, input)
    }
    @Test fun legacyBoundFitNamesKeepTheUnchangedNonemptyBridgeContract() {
        for (name in listOf(" ", "\t", "Legacy\u0001\nFit")) {
            val row = root(); val state = row.getJSONObject("state"); val detail = state.getJSONObject("detail")
            state.getJSONObject("page").getJSONArray("entries").getJSONObject(0).put("bound_fit_count", 1)
            detail.put("bound_fit_count", 1).getJSONObject("bound_fits").put("total", 1).put("entries", JSONArray().put(
                JSONObject().put("fit_id", "f".repeat(32)).put("name", name).put("revision", 2)))
            assertEquals(name, decode(row).state!!.detail!!.boundFits.single().name)
        }
    }
    @Test fun selectionFitAndBindingConsistencyRejectsImpossibleStates() {
        val row = root(); row.getJSONObject("state").getJSONObject("selection").put("kind", "named").put("target_id", target).put("binding_revision", 1)
        reject(row)
        val input = request().copy(fitId = "f".repeat(32)); assertTrue(decode(root(input), input).ok)
        for (kind in listOf("none", "anonymous")) { val changed = root(input); changed.getJSONObject("state").getJSONObject("selection").put("kind", kind).put("target_id", target); reject(changed, input) }
    }
    @Test fun staleContextWrongRequestAndReadMutationReject() {
        reject(root().put("request_id", "other"))
        for (generation in listOf(6L, 8L)) { val row = root(); row.getJSONObject("state").getJSONObject("context").put("generation", generation); reject(row) }
        reject(root().put("committed", true)); reject(root().put("reopen_required", true))
    }
    @Test fun actualMutationAdvancesOnceAndNoopDoesNot() {
        val input = request().copy(operation = "rename", argumentsJson = args("target_id" to target, "revision" to 3, "name" to "Other"))
        val row = root(input).put("bridge", bootstrap(input))
        assertFalse(decode(row, input).committed!!)
        row.put("committed", true); row.getJSONObject("state").getJSONObject("context").put("generation", 8)
        assertTrue(decode(row, input).committed!!)
        row.getJSONObject("state").getJSONObject("context").put("generation", 9); reject(row, input)
    }
    @Test fun completeErrorsKeepOpenCodesAndUncertainOutcomeRequiresReopen() {
        val row = root().put("ok", false).put("state", JSONObject.NULL).put("error", JSONObject().put("code", "new_backend_code").put("message", "Complete explanation"))
        assertEquals("new_backend_code", decode(row).error!!.code)
        row.put("committed", JSONObject.NULL); reject(row)
        row.put("reopen_required", true); assertTrue(decode(row).reopenRequired)
        row.put("committed", false); reject(row) // Certain failure must not claim an uncertain/reopen outcome.
        row.put("committed", JSONObject.NULL)
        row.put("bridge", bootstrap(request())); reject(row)
    }
    @Test fun deletionRequiresExplicitCountAndProtectedBuiltinsCannotMutate() {
        val input = request().copy(operation = "delete", argumentsJson = args("target_id" to target, "revision" to 3, "bound_fit_count" to 0))
        input.json()
        invalid(input.copy(argumentsJson = args("target_id" to target, "revision" to 3)))
        invalid(input.copy(argumentsJson = args("target_id" to "target:builtin:-149", "revision" to 0, "bound_fit_count" to 0)))
    }
}
