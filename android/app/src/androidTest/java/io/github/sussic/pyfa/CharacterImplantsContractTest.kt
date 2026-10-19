package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class CharacterImplantsContractTest {
    private fun JSONObject.wire(): String = OfflineFeatureCodec.json(this)
    private val session = "a".repeat(32)
    private val dataset = "a".repeat(64)
    private val custom = "profile:" + "b".repeat(32)
    private val fitId = "f".repeat(32)
    private val context = OfflineContext(session, dataset, 1)
    private fun state() = OfflineFeaturesContractTest().stateJson()
    private fun implant(id: String = "c".repeat(32), item: Int = 11, slot: Int = 79) = JSONObject()
        .put("implant_id", id).put("item_id", item).put("name", "Implant $item").put("slot", slot).put("active", false)
    private fun withImplants() = state().also { it.getJSONArray("profiles").getJSONObject(2)
        .put("implants", JSONArray().put(implant()).put(implant("d".repeat(32), 12, 1))) }
    private fun binding() = JSONObject().put("profile_id", custom).put("revision", 2).put("fit_revision", 7).put("implant_source", "CHARACTER")
    private fun reject(block: () -> Unit) { try { block(); fail("Invalid character contract accepted") } catch (_: BridgeProtocolException) { } }
    private fun response(committed: Boolean, value: JSONObject = state()) = JSONObject().put("version", 3).put("request_id", "request")
        .put("ok", true).put("committed", committed).put("reopen_required", false).put("error", JSONObject.NULL).put("state", value)
        .put("bridge", JSONObject().put("version", 1).put("request_id", "bootstrap").put("session_id", session).put("status", "ok")
            .put("fits", JSONArray()).put("error", JSONObject.NULL))
    private fun catalog() = JSONObject().put("version", 1).put("ok", true).put("dataset_sha256", dataset).put("error", JSONObject.NULL)
        .put("implants", JSONArray().put(JSONObject().put("item_id", 11).put("name", "Implant 11").put("slot", 79))
            .put(JSONObject().put("item_id", 12).put("name", "Implant 12").put("slot", 1))
            .put(JSONObject().put("item_id", 13).put("name", "Other slot 79").put("slot", 79)))

    @Test fun characterRowsKeepSavedOrderInactiveStateAndSlot79WithImmutableOwnership() {
        val value = OfflineFeatureCodec.state(withImplants().wire())
        val profile = value.profiles.last()
        assertEquals(listOf(79, 1), profile.implants.map { it.slot })
        assertEquals(listOf("d".repeat(32), "c".repeat(32)), profile.displayImplants.map { it.implantId })
        assertFalse(profile.implants.first().active)
        try { (profile.implants as MutableList<OfflineProfileImplant>).clear(); fail("Mutable profile implants") } catch (_: UnsupportedOperationException) { }
    }
    @Test fun duplicateSlotIdentityItemBuiltinRowsAndWrongScalarKindsFailClosed() {
        val changes: List<(JSONObject) -> Unit> = listOf(
            { it.getJSONArray("profiles").getJSONObject(2).getJSONArray("implants").getJSONObject(0).put("active", 1) },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONArray("implants").getJSONObject(0).put("slot", 79.0) },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONArray("implants").getJSONObject(0).put("slot", 0) },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONArray("implants").getJSONObject(1).put("slot", 79) },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONArray("implants").getJSONObject(1).put("implant_id", "c".repeat(32)) },
            { it.getJSONArray("profiles").getJSONObject(0).put("implants", JSONArray().put(implant("e".repeat(32)))) },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONArray("implants").getJSONObject(0).put("owner", custom) },
            { it.getJSONArray("profiles").getJSONObject(2).getJSONArray("implants").getJSONObject(0).put("name", "\uD800") },
        )
        changes.forEach { change -> val raw = withImplants(); change(raw); reject { OfflineFeatureCodec.state(OfflineFeatureCodec.json(raw)) } }
        val duplicateOwner = withImplants(); duplicateOwner.getJSONArray("profiles").put(JSONObject(duplicateOwner.getJSONArray("profiles").getJSONObject(2).wire()).put("profile_id", "profile:" + "e".repeat(32)))
        reject { OfflineFeatureCodec.state(duplicateOwner.wire()) }
    }
    @Test fun completeBindingsRequireExactFitRevisionsAndNoMissingOrExtraFits() {
        val raw = withImplants().put("bindings", JSONObject().put(fitId, binding())).put("selected_fit_id", fitId)
        val value = OfflineFeatureCodec.state(raw.wire())
        val fit = FitSnapshot(fitId, 7, "Fit", "Rifter", emptyMap(), emptyList(), emptyMap(), emptyList(), emptyList(), emptyList())
        OfflineFeatureCodec.validateFits(value, listOf(fit))
        reject { OfflineFeatureCodec.validateFits(value, listOf(fit.copy(revision = 8))) }
        reject { OfflineFeatureCodec.validateFits(value, emptyList()) }
        reject { OfflineFeatureCodec.validateFits(value, listOf(fit, fit)) }
        for (bad in listOf(binding().put("fit_revision", true), binding().put("implant_source", "LOCAL"), binding().put("revision", 0), binding().put("profile_id", "missing"))) {
            reject { OfflineFeatureCodec.state(raw.put("bindings", JSONObject().put(fitId, bad)).wire()) }
        }
    }
    @Test fun successfulNoopRequiresExactContextStateAndEffectiveChangeOneGeneration() {
        val before = OfflineFeatureCodec.state(state().wire())
        assertFalse(OfflineFeatureCodec.response(response(false).wire(), "request", context, before).committed!!)
        val changed = state().also { it.getJSONObject("context").put("generation", 2) }
        assertTrue(OfflineFeatureCodec.response(response(true, changed).wire(), "request", context, before).committed!!)
        reject { OfflineFeatureCodec.response(response(true).wire(), "request", context, before) }
        reject { OfflineFeatureCodec.response(response(false, changed).wire(), "request", context, before) }
        val jumped = state().also { it.getJSONObject("context").put("generation", 3) }
        reject { OfflineFeatureCodec.response(response(true, jumped).wire(), "request", context, before) }
        val renamed = state().also { it.getJSONArray("profiles").getJSONObject(2).put("name", "Wrong no-op") }
        reject { OfflineFeatureCodec.response(response(false, renamed).wire(), "request", context, before) }
    }
    @Test fun featureResponsesAlwaysRequireCompleteErrorEnvelopeAndSafeBoundedError() {
        fun error() = response(false).put("ok", false).put("state", JSONObject.NULL).put("bridge", JSONObject.NULL)
            .put("error", JSONObject().put("code", "failed").put("message", "No changes saved"))
        assertFalse(OfflineFeatureCodec.response(error().wire(), "request", context).ok)
        assertTrue(OfflineFeatureCodec.response(error().put("committed", JSONObject.NULL).put("reopen_required", true).wire(), "request", context).reopenRequired)
        val missing = error().also { it.remove("state") }; reject { OfflineFeatureCodec.response(missing.wire(), "request", context) }
        val hidden = error().put("state", state()); reject { OfflineFeatureCodec.response(hidden.wire(), "request", context) }
        for (message in listOf("x".repeat(1025), "bad\nline", "\uD800")) {
            val bad = error(); bad.getJSONObject("error").put("message", message)
            reject { OfflineFeatureCodec.response(bad.wire(), "request", context) }
        }
    }
    @Test fun featureStateWholeSizeGuardDoesNotTruncateOrCapCharacterCount() {
        val raw = state(); raw.getJSONArray("skills").getJSONObject(0).put("name", "x".repeat(524_288))
        reject { OfflineFeatureCodec.state(raw.wire()) }
        val many = state()
        repeat(125) { i -> many.getJSONArray("profiles").put(JSONObject(many.getJSONArray("profiles").getJSONObject(2).wire())
            .put("profile_id", "profile:" + (i + 50).toString(16).padStart(32, '0')).put("name", "Pilot $i")) }
        assertEquals(128, OfflineFeatureCodec.state(many.wire()).profiles.size)
    }
    @Test fun legacyCharacterNamesRemainReadableButNewNamesRejectDelAndC1() {
        for (control in listOf('\u007f', '\u0085', '\u009f')) {
            val name = "Legacy${control}pilot"
            val raw = state(); raw.getJSONArray("profiles").getJSONObject(2).put("name", name)
            assertEquals(name, OfflineFeatureCodec.state(raw.wire()).profiles.last().name)
            reject { OfflineFeatureCodec.request("request", context, "create_profile",
                JSONObject().put("name", name).put("source", "builtin:all5"), null) }
            reject { OfflineFeatureCodec.request("request", context, "rename_profile",
                JSONObject().put("profile_id", custom).put("revision", 2).put("name", name), null) }
        }
        for (name in listOf("Legacy\npilot", "Legacy\uD800pilot", "\u0085Legacy", "Legacy\u0085")) {
            val raw = state(); raw.getJSONArray("profiles").getJSONObject(2).put("name", name)
            reject { OfflineFeatureCodec.state(OfflineFeatureCodec.json(raw)) }
        }
    }
    @Test fun newRequestsUseExactVersionThreeTokensAndPreserveNullOccupant() {
        val args = JSONObject().put("profile_id", custom).put("revision", Long.MAX_VALUE).put("item_id", 11).put("replace_implant_id", JSONObject.NULL)
        val encoded = OfflineFeatureCodec.request("🚀".repeat(128), context, "add_profile_implant", args, null)
        args.put("item_id", 99)
        val value = JSONObject(encoded)
        assertEquals(3, value.getInt("version")); assertEquals(11, value.getJSONObject("arguments").getInt("item_id")); assertTrue(value.getJSONObject("arguments").isNull("replace_implant_id"))
        reject { OfflineFeatureCodec.request("🚀".repeat(129), context, "undo", JSONObject(), null) }
        reject { OfflineFeatureCodec.request("bad\n", context, "undo", JSONObject(), null) }
        reject { OfflineFeatureCodec.request("request", context.copy(sessionId = "session"), "undo", JSONObject(), null) }
        val source = JSONObject().put("fit_id", fitId).put("fit_revision", 7).put("source", "CHARACTER")
        assertEquals("CHARACTER", JSONObject(OfflineFeatureCodec.request("request", context, "set_implant_source", source, fitId)).getJSONObject("arguments").getString("source"))
        reject { OfflineFeatureCodec.request("request", context, "set_implant_source", source, null) }
        reject { OfflineFeatureCodec.request("request", context, "set_implant_source", source.put("fit_revision", 7.0), fitId) }
        reject { OfflineFeatureCodec.request("request", context, "remove_profile_implant", JSONObject().put("profile_id", custom).put("revision", 2).put("implant_id", "not-a-row"), null) }
    }
    @Test fun completeCatalogueAcceptsRepeatedSlotsAndValidatesEverySavedRow() {
        val value = CharacterImplantCatalogCodec.decode(catalog().wire(), dataset)
        assertEquals(listOf(79, 1, 79), value.items.map { it.slot })
        value.validate(OfflineFeatureCodec.state(withImplants().wire()))
        assertNull(value.itemById[99]) // Category-only booster IDs are not admitted by this genuine catalogue.
        val bad = withImplants(); bad.getJSONArray("profiles").getJSONObject(2).getJSONArray("implants").getJSONObject(0).put("name", "Wrong")
        reject { value.validate(OfflineFeatureCodec.state(bad.wire())) }
        reject { value.validate(OfflineFeatureCodec.state(withImplants().wire()).copy(context = context.copy(datasetSha256 = "b".repeat(64)))) }
        try { (value.items as MutableList<CharacterImplantItem>).clear(); fail("Mutable catalogue") } catch (_: UnsupportedOperationException) { }
    }
    @Test fun catalogueMalformedUnknownOversizeDatasetAndCompleteErrorCasesAreStrict() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", 1.0) }, { it.put("ok", 1) }, { it.put("dataset_sha256", "b".repeat(64)) }, { it.put("extra", false) },
            { it.getJSONArray("implants").getJSONObject(1).put("item_id", 11) },
            { it.getJSONArray("implants").getJSONObject(0).put("slot", true) },
            { it.getJSONArray("implants").getJSONObject(0).put("name", "bad\u007f") },
            { it.getJSONArray("implants").getJSONObject(0).put("slot", 0) },
        )
        mutations.forEach { change -> val raw = catalog(); change(raw); reject { CharacterImplantCatalogCodec.decode(OfflineFeatureCodec.json(raw), dataset) } }
        reject { CharacterImplantCatalogCodec.decode(" ".repeat(524_289) + catalog(), dataset) }
        reject { CharacterImplantCatalogCodec.decode(catalog().wire().replaceFirst("{", "{\"version\":1,"), dataset) }
        reject { CharacterImplantCatalogCodec.decode(catalog().wire() + "null", dataset) }
        val error = catalog().put("ok", false).put("dataset_sha256", JSONObject.NULL).put("implants", JSONArray())
            .put("error", JSONObject().put("code", "response_size").put("message", "Catalogue too large"))
        assertEquals("response_size", CharacterImplantCatalogCodec.decode(error.wire(), dataset).error?.code)
        reject { CharacterImplantCatalogCodec.decode(error.put("implants", catalog().getJSONArray("implants")).wire(), dataset) }
    }
    @Test fun equipmentCharacterDuplicateIsExplicitSourceOnlyButFitDuplicateStillBlocked() {
        val same = ImplantAddOptions(fitId, 7, 11, true, false, ImplantLocation.CHARACTER, 79, ImplantOccupant(0, "local", 11, "Implant 11"), true)
        assertTrue(same.editable); assertTrue(same.canAdd); assertTrue(same.sourceOnly)
        assertFalse(same.copy(location = ImplantLocation.FIT).canAdd)
        assertFalse(same.copy(isStructure = true).canAdd)
        assertFalse(same.copy(isImplant = false).canAdd)
        val replacement = same.copy(itemId = 12, alreadyFitted = false)
        assertTrue(replacement.canAdd); assertFalse(replacement.sourceOnly)
    }
}
