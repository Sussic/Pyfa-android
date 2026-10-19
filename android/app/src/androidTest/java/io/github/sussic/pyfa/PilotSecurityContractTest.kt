package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Actual production codecs. Synthetic wire cases are not EOS numerical or device evidence. */
@RunWith(AndroidJUnit4::class)
class PilotSecurityContractTest {
    private val id = "f".repeat(32)
    private val profileId = "profile:" + "b".repeat(32)
    private val context = OfflineContext("a".repeat(32), "a".repeat(64), 1)
    private fun wire(value: JSONObject) = OfflineFeatureCodec.json(value)
    private fun reject(block: () -> Unit) {
        try { block(); fail("Invalid security authority accepted") } catch (_: BridgeProtocolException) { }
    }
    internal fun details(pilot: Any = JSONObject.NULL, security: Number = 2.75, hullId: Int = 44993, hullName: String = "Pacifier"): JSONObject = JSONObject()
        .put("version", 1).put("context", context.json()).put("fit_id", id).put("revision", 7)
        .put("hull_id", hullId).put("hull_name", hullName).put("eligible", true).put("unavailable_reason", JSONObject.NULL)
        .put("profile", JSONObject().put("profile_id", profileId).put("name", "Pilot").put("revision", 1)
            .put("binding_revision", 3).put("readonly", false).put("sec_status", security))
        .put("pilot", pilot).put("source", if (pilot === JSONObject.NULL) "CHARACTER" else "EXPLICIT")
        .put("effective", if (pilot === JSONObject.NULL) security else pilot).put("presets", JSONArray(PilotSecurityCodec.presets))
    private fun decode(value: JSONObject) = PilotSecurityCodec.decode(wire(value))
    private fun feature() = OfflineFeaturesContractTest().stateJson()
    private fun response(value: JSONObject = feature(), committed: Boolean = false) = JSONObject().put("version", 3)
        .put("request_id", "request").put("ok", true).put("committed", committed).put("reopen_required", false)
        .put("state", value).put("bridge", JSONObject().put("version", 1).put("request_id", "bootstrap")
            .put("session_id", context.sessionId).put("status", "ok").put("fits", JSONArray()).put("error", JSONObject.NULL))
        .put("error", JSONObject.NULL)

    @Test fun characterAndExplicitZeroRemainDifferentAndRawNumbersRetainTheirKindAndSign() {
        assertNull(decode(details()).pilot)
        val zero = decode(details(0)); assertEquals(PilotSecuritySource.EXPLICIT, zero.source)
        assertTrue(zero.pilot!!.raw is Long || zero.pilot!!.raw is Int)
        for (number in listOf(-0.0, 0.0, -6.25, 2.75, -10.0, 5.0)) {
            val raw = decode(details(number)).pilot!!.raw
            assertTrue(raw is Double)
            assertEquals(java.lang.Double.doubleToRawLongBits(number), java.lang.Double.doubleToRawLongBits(raw.toDouble()))
        }
        assertEquals(0.0, decode(details(0, 2.75)).effective.raw.toDouble(), 0.0)
        assertTrue(SecurityNumber(0).numericallyEquals(SecurityNumber(-0.0)))
        assertNotEquals(SecurityNumber(0.0), SecurityNumber(-0.0))
    }
    @Test fun entryUsesStrictFiniteDecimalGrammarWithoutStrippingOrClamping() {
        for (text in listOf("  -6.25  ", "+2.75", ".5", "5.", "-1e1", "-0.0", "0e3")) assertNotNull(text, PilotSecurityCodec.entry(text))
        for (text in listOf("", " ", "1,2", "--2", "1 2", "0x1", "NaN", "Infinity", "1e309", "5.0001", "-10.01", "true", "1f"))
            assertNull(text, PilotSecurityCodec.entry(text))
        assertTrue(PilotSecurityCodec.entry("0")!!.raw is Double)
        assertEquals(java.lang.Double.doubleToRawLongBits(-0.0), java.lang.Double.doubleToRawLongBits(PilotSecurityCodec.entry("-0")!!.raw.toDouble()))
    }
    @Test fun sixExactHullPairsAndOnlyIntegerOrderedPresetsAreAccepted() {
        for ((hullId, name) in PilotSecurityCodec.hulls) assertTrue(decode(details(hullId = hullId, hullName = name)).eligible)
        reject { decode(details(hullName = "Rifter")) }
        reject { decode(details().put("hull_id", 44993.0)) }
        reject { decode(details().put("presets", JSONArray(PilotSecurityCodec.presets.reversed()))) }
        reject { decode(details().put("presets", JSONArray().put(-10.0))) }
        reject { decode(details().put("eligible", false).put("unavailable_reason", "unsupported_hull").put("presets", JSONArray())) }
        val unsupported = details(hullId = 587, hullName = "Rifter").put("eligible", false)
            .put("unavailable_reason", "unsupported_hull").put("presets", JSONArray())
        assertEquals(PilotSecuritySource.CHARACTER, decode(unsupported).source)
        reject { decode(unsupported.put("unavailable_reason", JSONObject.NULL)) }
    }
    @Test fun detailsRejectMixedFieldsVersionsSourcesEffectiveValuesAndMalformedNumbers() {
        val changes: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", 2) }, { it.put("version", 1.0) }, { it.put("extra", 0) }, { it.remove("pilot") },
            { it.put("pilot", "0") }, { it.put("pilot", false) }, { it.put("pilot", 5.01) },
            { it.put("source", "EXPLICIT") }, { it.put("effective", 0) }, { it.put("revision", 0) },
            { it.getJSONObject("context").put("session_id", "wrong") },
            { it.getJSONObject("profile").put("binding_revision", 0) }, { it.getJSONObject("profile").put("revision", 0) },
            { it.getJSONObject("profile").put("readonly", true) }, { it.getJSONObject("profile").put("sec_status", JSONObject.NULL) },
            { it.getJSONObject("profile").put("name", " Pilot") }, { it.getJSONObject("profile").put("extra", 0) },
        )
        changes.forEach { change -> reject { decode(details().also(change)) } }
        reject { PilotSecurityCodec.decode(wire(details()).replaceFirst("{", "{\"version\":1,")) }
        reject { PilotSecurityCodec.decode(wire(details()).replace("\"pilot\":null", "\"pilot\":NaN")) }
        reject { PilotSecurityCodec.number(0.0f) }
        reject { PilotSecurityCodec.number(Double.POSITIVE_INFINITY) }
    }
    @Test fun featureV3RequiresEverySecurityAndProtectsBuiltinExactDecimalEncodings() {
        val state = OfflineFeatureCodec.state(wire(feature()))
        assertEquals(SecurityNumber(0.0), state.profiles[0].secStatus)
        assertEquals(SecurityNumber(5.0), state.profiles[1].secStatus)
        reject { OfflineFeatureCodec.state(wire(feature().put("version", 2))) }
        for (bad in listOf<Any>(JSONObject.NULL, true, "0", 6, -11)) reject {
            OfflineFeatureCodec.state(wire(feature().also { it.getJSONArray("profiles").getJSONObject(2).put("sec_status", bad) }))
        }
        reject { OfflineFeatureCodec.state(wire(feature().also { it.getJSONArray("profiles").getJSONObject(2).remove("sec_status") })) }
        for (bad in listOf<Number>(0, -0.0, 1.0)) reject {
            OfflineFeatureCodec.state(wire(feature().also { it.getJSONArray("profiles").getJSONObject(0).put("sec_status", bad) }))
        }
        for (bad in listOf<Number>(5, 0.0)) reject {
            OfflineFeatureCodec.state(wire(feature().also { it.getJSONArray("profiles").getJSONObject(1).put("sec_status", bad) }))
        }
    }
    @Test fun rawProfileEncodingAndBuiltinDetailsAreNeverNormalizedOnRead() {
        for (number in listOf<Number>(0, -0.0, 0.0, -6.25, 5)) {
            val json = feature().also { it.getJSONArray("profiles").getJSONObject(2).put("sec_status", number) }
            val decoded = OfflineFeatureCodec.state(wire(json)).profiles.last().secStatus.raw
            assertEquals(number.toDouble(), decoded.toDouble(), 0.0)
            assertEquals(number is Double, decoded is Double)
            if (number is Double) assertEquals(java.lang.Double.doubleToRawLongBits(number), java.lang.Double.doubleToRawLongBits(decoded.toDouble()))
        }
        val raw = details(security = 0.0).also { it.getJSONObject("profile").put("profile_id", "builtin:all0").put("name", "All 0").put("revision", 0).put("readonly", true) }
        assertTrue(decode(raw).profile.readonly)
        reject { decode(raw.also { it.getJSONObject("profile").put("sec_status", -0.0) }) }
    }
    @Test fun pilotRequestsFreezeNullIntegerPresetAndDecimalCustomWithExactAnchorAndKeys() {
        for (number in listOf<Any>(JSONObject.NULL, 0, -10, 5, -0.0, 2.75)) {
            val args = JSONObject().put("fit_id", id).put("fit_revision", 7).put("pilot", number)
            val request = OfflineFeatureCodec.request("request", context, "set_pilot_security", args, id)
            args.put("pilot", 4)
            val row = OfflineFeatureCodec.parse(request); assertEquals(3L, OfflineFeatureCodec.integer(row.get("version")))
            assertEquals(OfflineFeatureCodec.json(number), OfflineFeatureCodec.json(row.getJSONObject("arguments").get("pilot")))
        }
        val args = JSONObject().put("fit_id", id).put("fit_revision", 7).put("pilot", JSONObject.NULL)
        reject { OfflineFeatureCodec.request("r", context, "set_pilot_security", args, null) }
        reject { OfflineFeatureCodec.request("r", context, "set_pilot_security", args, "e".repeat(32)) }
        reject { OfflineFeatureCodec.request("r", context, "set_pilot_security", args.put("binding_revision", 3), id) }
    }
    @Test fun profileSaveAsAllowsNoFitButNeverBuiltinNullSecurityOrExtraFields() {
        val args = JSONObject().put("profile_id", profileId).put("revision", 1).put("sec_status", -0.0).put("save_as", JSONObject.NULL)
        val save = OfflineFeatureCodec.parse(OfflineFeatureCodec.request("r", context, "save_profile_security", args, null))
        assertTrue(save.isNull("anchor_fit_id")); assertEquals("-0.0", OfflineFeatureCodec.json(save.getJSONObject("arguments").get("sec_status")))
        OfflineFeatureCodec.request("r", context, "save_profile_security", args.put("save_as", "Copy"), null)
        reject { OfflineFeatureCodec.request("r", context, "save_profile_security", args.put("save_as", " Copy"), null) }
        args.put("save_as", JSONObject.NULL)
        reject { OfflineFeatureCodec.request("r", context, "save_profile_security", args.put("profile_id", "builtin:all5"), null) }
        args.put("profile_id", profileId)
        reject { OfflineFeatureCodec.request("r", context, "save_profile_security", args.put("sec_status", JSONObject.NULL), null) }
    }
    @Test fun ownerCrossChecksContextRevisionBindingAndCompleteProfileSecurity() {
        val json = feature().also {
            it.getJSONArray("profiles").getJSONObject(2).put("sec_status", 2.75)
            it.getJSONObject("bindings").put(id, JSONObject().put("profile_id", profileId).put("revision", 3).put("fit_revision", 7).put("implant_source", "FIT"))
        }
        val state = OfflineFeatureCodec.state(wire(json))
        val fit = FitSnapshot(id, 7, "Fit", "Pacifier", emptyMap(), emptyList(), emptyMap(), emptyList(), emptyList(), emptyList())
        val owner = PilotSecurityOwner.capture(state, fit); owner.validate(decode(details()))
        for (value in listOf(owner.copy(fitRevision = 8), owner.copy(context = context.copy(generation = 2)),
            owner.copy(binding = owner.binding.copy(revision = 4)), owner.copy(profile = owner.profile.copy(secStatus = SecurityNumber(0.0))),
            owner.copy(profile = owner.profile.copy(name = "Renamed")), owner.copy(profile = owner.profile.copy(revision = 2)))) reject { value.validate(decode(details())) }
    }
    @Test fun noOpResponsesCannotChangeSecurityEncodingOrVersionAndUnknownCommitRequiresReopen() {
        val before = OfflineFeatureCodec.state(wire(feature()))
        assertFalse(OfflineFeatureCodec.response(wire(response()), "request", context, before).committed!!)
        reject { OfflineFeatureCodec.response(wire(response().put("version", 2)), "request", context, before) }
        val changed = feature().also { it.getJSONArray("profiles").getJSONObject(2).put("sec_status", -0.0) }
        reject { OfflineFeatureCodec.response(wire(response(changed)), "request", context, before) }
        val error = response().put("ok", false).put("committed", JSONObject.NULL).put("reopen_required", true)
            .put("state", JSONObject.NULL).put("bridge", JSONObject.NULL).put("error", JSONObject().put("code", "reopen_required").put("message", "Restart"))
        assertTrue(OfflineFeatureCodec.response(wire(error), "request", context).reopenRequired)
        reject { OfflineFeatureCodec.response(wire(error.put("reopen_required", false)), "request", context) }
    }
    @Test fun detailsKeepReadStateCeilingAndImmutablePresetCollection() {
        reject { PilotSecurityCodec.decode(" ".repeat(524_288) + wire(details())) }
        val presets = decode(details()).presets
        try { (presets as MutableList<Int>).clear(); fail("Mutable presets") } catch (_: UnsupportedOperationException) { }
    }
}
