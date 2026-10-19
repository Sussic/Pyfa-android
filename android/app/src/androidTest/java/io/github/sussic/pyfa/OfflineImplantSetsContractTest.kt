package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic actual-codec witnesses. Source-only until the bounded host/native gates execute. */
@RunWith(AndroidJUnit4::class)
class OfflineImplantSetsContractTest {
    private val set = "implant-set:" + "b".repeat(32)
    private val fresh = "implant-set:" + "e".repeat(32)
    private val pilot = "profile:" + "c".repeat(32)
    private val fitId = "f".repeat(32)
    private val ctx = OfflineContext("a".repeat(32), "d".repeat(64), 7)
    private val a = OfflineImplantSetItem(11, "Auroral", 79)
    private val b = OfflineImplantSetItem(12, "Navigation", 1)
    private val c = OfflineImplantSetItem(13, "Replacement", 79)
    private val catalogue = CharacterImplantCatalog(ctx.datasetSha256, listOf(a, b, c).map { CharacterImplantItem(it.itemId, it.name, it.slot) }, null)
    private fun obj(vararg fields: Pair<String, Any?>) = JSONObject().also { row -> fields.forEach { row.put(it.first, it.second ?: JSONObject.NULL) } }
    private fun json(value: Any) = OfflineFeatureCodec.json(value)
    private fun args(vararg fields: Pair<String, Any?>) = json(obj(*fields))
    private fun request(id: String? = set) = OfflineImplantSetRequest("set-test", ctx, null, OfflineImplantSetView(selectedSetId = id))
    private fun entry(id: String = set, name: String = "Recipe", revision: Long = if (id.startsWith("builtin:")) 0 else 3, count: Int = 2,
        family: String? = if (id.startsWith("builtin:")) "Genolution" else null, grade: String? = null) = obj(
        "set_id" to id, "kind" to if (id.startsWith("builtin:")) "builtin" else "custom", "name" to name,
        "family" to family, "grade" to grade, "revision" to revision, "item_count" to count)
    private fun recipe(id: String = set, name: String = if (id.startsWith("builtin:")) "Genolution" else "Recipe", revision: Long = if (id.startsWith("builtin:")) 0 else 3,
        items: List<OfflineImplantSetItem> = listOf(a, b)) = entry(id, name, revision, items.size).put("items", JSONArray(items.map {
            obj("item_id" to it.itemId, "name" to it.name, "slot" to it.slot) }))
    private fun row(item: OfflineImplantSetItem = a, id: String = "1".repeat(32), active: Boolean = false) = OfflineImplantCollectionRow(id, item.itemId, item.name, item.slot, active)
    private fun rowsJson(rows: List<OfflineImplantCollectionRow>) = JSONArray(rows.map {
        obj("row_id" to it.rowId, "item_id" to it.itemId, "name" to it.name, "slot" to it.slot, "active" to it.active) })
    private val unavailableStats = listOf(
        "cpu_output", "powergrid_output", "capacitor_capacity", "capacitor_recharge_time", "max_velocity", "max_target_range",
        "cpu_used", "powergrid_used", "drone_control_range", "drone_bandwidth_used", "weapon_dps", "drone_dps", "total_dps",
        "total_volley", "capacitor_used", "capacitor_recharge", "capacitor_stable", "capacitor_state", "gun_optimal", "gun_falloff",
        "shield_hp", "shield_ehp_uniform", "shield_em_resonance", "shield_thermal_resonance", "shield_kinetic_resonance", "shield_explosive_resonance",
        "armor_hp", "armor_ehp_uniform", "armor_em_resonance", "armor_thermal_resonance", "armor_kinetic_resonance", "armor_explosive_resonance",
        "hull_hp", "hull_ehp_uniform", "hull_em_resonance", "hull_thermal_resonance", "hull_kinetic_resonance", "hull_explosive_resonance", "scan_resolution"
    ).associateWith { Stat(StatValue.Unavailable, "") }
    private fun fit(rows: List<OfflineImplantCollectionRow> = listOf(row()), revision: Long = 2) =
        FitSnapshot(fitId, revision, "Legacy\u007FFit", "Rifter", unavailableStats, emptyList(), emptyMap(), rows.map { ImplantSnapshot(it.name, it.slot, it.active) }, emptyList(), emptyList())
    private fun fitTarget(rows: List<OfflineImplantCollectionRow> = listOf(row()), revision: Long = 2) = obj(
        "kind" to "fit", "fit_id" to fitId, "fit_revision" to revision, "name" to fit().name, "is_structure" to false, "implants" to rowsJson(rows))
    private fun profileTarget(rows: List<OfflineImplantCollectionRow> = listOf(row()), revision: Long = 4, count: Int = 1) = obj(
        "kind" to "profile", "profile_id" to pilot, "profile_revision" to revision, "name" to "Pilot", "readonly" to false,
        "assigned_fit_count" to count, "implants" to rowsJson(rows))
    private fun source(location: ImplantLocation = ImplantLocation.FIT, count: Int = 1, fitRevision: Long = 2) = obj(
        "fit_id" to fitId, "fit_revision" to fitRevision, "source" to location.name, "profile_id" to if (location == ImplantLocation.CHARACTER) pilot else null,
        "profile_revision" to if (location == ImplantLocation.CHARACTER) 4 else null, "profile_name" to if (location == ImplantLocation.CHARACTER) "Pilot" else null,
        "implant_count" to count)
    private fun history(target: String = "library", undo: Int = 0, redo: Int = 0) = obj("target" to target, "undo_count" to undo,
        "redo_count" to redo, "limit" to 100, "undo_label" to if (undo > 0) "Apply implant set to fit" else null,
        "redo_label" to if (redo > 0) "Apply implant set to fit" else null)
    private fun snapshotJson(fit: FitSnapshot) = obj("id" to fit.id, "revision" to fit.revision, "name" to fit.name, "ship" to fit.ship,
        "stats" to JSONObject().also { raw -> fit.stats.forEach { (key, value) -> raw.put(key, obj("value" to value.value.raw, "unit" to value.unit)) } },
        "modules" to JSONArray(), "skills" to JSONObject(fit.skills), "implants" to JSONArray(fit.implants.map {
            obj("name" to it.name, "slot" to it.slot, "active" to it.active) }), "projections" to JSONArray(), "commands" to JSONArray())
    private fun bridge(fits: List<FitSnapshot> = emptyList()) = obj("version" to 1, "request_id" to "bootstrap", "session_id" to ctx.sessionId,
        "status" to "ok", "fits" to JSONArray(fits.map(::snapshotJson)), "error" to null)
    private fun root(input: OfflineImplantSetRequest = request(), detail: JSONObject? = input.view.selectedSetId?.let { recipe(it) }): JSONObject {
        val metadata = detail?.let { JSONObject(json(it)).also { row -> row.remove("items") } }
        val state = obj("version" to 1, "context" to input.context.json(), "anchor_fit_id" to input.anchorFitId,
            "page" to obj("query" to input.view.query, "offset" to input.view.offset, "limit" to input.view.limit,
                "total" to if (metadata == null) 0 else 1, "entries" to JSONArray(if (metadata != null && input.view.offset == 0L) listOf(metadata) else emptyList<JSONObject>())),
            "detail" to detail, "destination" to if (input.anchorFitId == null) null else fitTarget(),
            "save_source" to if (input.anchorFitId == null) null else source(), "history" to history(input.view.historyTarget))
        return obj("version" to 1, "request_id" to input.requestId, "ok" to true, "committed" to false, "reopen_required" to false,
            "state" to state, "bridge" to if (input.operation == "read") null else bridge(if (input.anchorFitId == null) emptyList() else listOf(fit())), "error" to null)
    }
    private fun decode(root: JSONObject, input: OfflineImplantSetRequest = request()) = OfflineImplantSetsCodec.response(json(root), input)
    private fun reject(block: () -> Unit) { try { block(); fail("Accepted invalid implant-set wire") } catch (_: BridgeProtocolException) { } catch (_: org.json.JSONException) { } }
    private fun effective(root: JSONObject, generation: Long = ctx.generation + 1): JSONObject = root.put("committed", true).also {
        it.getJSONObject("state").put("context", ctx.copy(generation = generation).json()) }
    private fun features(location: ImplantLocation = ImplantLocation.FIT, hasFit: Boolean = true, rows: List<OfflineImplantCollectionRow> = listOf(row()),
        context: OfflineContext = ctx, fitRevision: Long = 2, profileRevision: Long = 4) = OfflineFeatureState(context,
        listOf(OfflineProfile("builtin:all0", "All 0", true, null, emptyMap(), 0), OfflineProfile("builtin:all5", "All 5", true, 5, emptyMap(), 0),
            OfflineProfile(pilot, "Pilot", false, 5, mapOf(1 to 4), profileRevision, rows.map { OfflineProfileImplant(it.rowId, it.itemId, it.name, it.slot, it.active) })),
        if (hasFit) mapOf(fitId to OfflineBinding(pilot, 1, fitRevision, location)) else emptyMap(), listOf(OfflineSkill(1, "Skill")),
        if (hasFit) fitId else null, OfflineHistory(0, 0, 100, null, null))

    @Test fun noFitLibraryReadPreservesOrderedSlot79RecipeAndImmutableRows() {
        val state = decode(root()).state!!
        assertNull(state.anchorFitId); assertNull(state.destination); assertNull(state.saveSource)
        assertEquals(listOf(79, 1), state.detail!!.items.map { it.slot })
        OfflineImplantSetsCodec.validateAuthority(state, features(hasFit = false), emptyList(), catalogue)
        try { (state.detail.items as MutableList<OfflineImplantSetItem>).clear(); fail("Mutable recipe") } catch (_: UnsupportedOperationException) { }
    }
    @Test fun namesUseCodePointsPythonStripAndDoNotReserveProfileOrDamageNames() {
        val astral = "\uD83D\uDE80"
        assertEquals(astral.repeat(200), OfflineImplantSetsCodec.name("\u001C\u0085\u00A0" + astral.repeat(200) + "\u3000"))
        for (allowed in listOf("All 0", "All 5", "Uniform", "Selected Ammo", "Genolution")) assertEquals(allowed, OfflineImplantSetsCodec.name(allowed))
        for (bad in listOf("", " ", "A\u007FB", "A\u0085B", "\uD800", "\uDC00", astral.repeat(201))) reject { OfflineImplantSetsCodec.name(bad) }
    }
    @Test fun strictRequestUsesOnlyIdentityAndExactExplicitViewKeys() {
        val input = request().copy(anchorFitId = fitId, view = request().view.copy(historyTarget = fitId), operation = "apply_fit",
            argumentsJson = args("set_id" to set, "revision" to 3, "fit_revision" to 2))
        assertEquals(input, OfflineImplantSetsCodec.decodeRequest(input.json()))
        for (extra in listOf("source", "implants", "active", "row_id", "slot")) {
            val raw = OfflineFeatureCodec.parse(input.json()); raw.getJSONObject("arguments").put(extra, "forged")
            reject { OfflineImplantSetsCodec.decodeRequest(json(raw)) }
        }
        reject { input.copy(view = input.view.copy(historyTarget = "library")).json() }
        reject { input.copy(view = input.view.copy(targetProfileId = pilot)).json() }
    }
    @Test fun allCustomOperationsRequireTheirExplicitLibraryHistoryAndSelectedIdentity() {
        val operations = mapOf("rename" to args("set_id" to set, "revision" to 3, "name" to "Renamed"),
            "duplicate" to args("set_id" to set, "revision" to 3, "name" to "Copy"), "delete" to args("set_id" to set, "revision" to 3),
            "add_item" to args("set_id" to set, "revision" to 3, "item_id" to 13, "replace_item_id" to 11),
            "remove_item" to args("set_id" to set, "revision" to 3, "item_id" to 11))
        for ((operation, arguments) in operations) {
            val input = request().copy(anchorFitId = fitId, operation = operation, argumentsJson = arguments)
            input.json(); reject { input.copy(view = input.view.copy(selectedSetId = fresh)).json() }
            reject { input.copy(view = input.view.copy(historyTarget = fitId)).json() }
        }
    }
    @Test fun predefinedIdsAreCanonicalRevisionZeroAndCustomOnlyDuplicationIsProtected() {
        for (bad in listOf("builtin:implant-set:0", "builtin:implant-set:01", "builtin:implant-set:+1", "builtin:implant-set:2147483648", "implant-set:ABC", "damage:builtin:-1"))
            reject { request(bad).json() }
        val builtin = "builtin:implant-set:1"; val input = request(builtin)
        assertTrue(decode(root(input), input).state!!.detail!!.entry.readonly)
        val duplicate = input.copy(operation = "duplicate", argumentsJson = args("set_id" to builtin, "revision" to 0, "name" to "Copy"))
        reject { duplicate.json() }
        val bad = root(input); bad.getJSONObject("state").getJSONObject("detail").put("revision", 1); reject { decode(bad, input) }
        reject { request().copy(operation = "delete", argumentsJson = args("set_id" to set, "revision" to 0)).json() }
    }
    @Test fun requestRawKindsMissingExtraDuplicateTrailingNonfiniteAndUnicodeReject() {
        val wire = request().json()
        for (bad in listOf(wire + "{}", wire.replace("\"version\":1", "\"version\":1,\"version\":1"),
            wire.replace("\"version\":1", "\"version\":1.0"), wire.replace("\"offset\":0", "\"offset\":0e0"),
            wire.replace("\"offset\":0", "\"offset\":true"), wire.replace("\"offset\":0", "\"offset\":\"0\""),
            wire.replace("\"offset\":0", "\"offset\":NaN"), wire.replace("\"offset\":0", "\"offset\":9223372036854775808"),
            wire.replace("\"query\":\"\"", "\"query\":\"\\ud800\""))) reject { OfflineImplantSetsCodec.decodeRequest(bad) }
        val missing = OfflineFeatureCodec.parse(wire); missing.getJSONObject("view").remove("target_profile_id")
        reject { OfflineImplantSetsCodec.decodeRequest(json(missing)) }
        val extra = OfflineFeatureCodec.parse(wire).put("source", "FIT"); reject { OfflineImplantSetsCodec.decodeRequest(json(extra)) }
    }
    @Test fun untrimmedWireNamesRejectWhileUiNormalizationAndExactCaseRemainExplicit() {
        for (name in listOf(" Name", "Name\u3000", "\u00A0Name")) reject { request(null).copy(operation = "create", argumentsJson = args("name" to name)).json() }
        request(null).copy(operation = "create", argumentsJson = args("name" to "Name")).json()
        request(null).copy(operation = "create", argumentsJson = args("name" to "name")).json()
    }
    @Test fun outOfRangeOffsetLongMaxRemainsExactAndEmptyWithoutAdditionOverflow() {
        val input = request().copy(view = request().view.copy(offset = Long.MAX_VALUE))
        val state = decode(root(input), input).state!!
        assertEquals(Long.MAX_VALUE, state.view.offset); assertTrue(state.entries.isEmpty()); assertNotNull(state.detail)
        val forged = root(input); forged.getJSONObject("state").getJSONObject("page").put("offset", 0)
        reject { decode(forged, input) }
    }
    @Test fun exactPageSizeAndMetadataConsistencyRejectSilentTruncationAndDuplicateIdentity() {
        val short = root(); short.getJSONObject("state").getJSONObject("page").put("total", 2); reject { decode(short) }
        val duplicate = root(); val page = duplicate.getJSONObject("state").getJSONObject("page"); page.put("total", 2)
            .getJSONArray("entries").put(entry()); reject { decode(duplicate) }
        val mismatch = root(); mismatch.getJSONObject("state").getJSONObject("detail").put("name", "Other"); reject { decode(mismatch) }
    }
    @Test fun familyGradeAndCustomUnicodeScalarOrderingAreValidatedWithoutSlotSorting() {
        val input = request(null); val root = root(input); val page = root.getJSONObject("state").getJSONObject("page")
        val entries = listOf(entry("builtin:implant-set:34", "Low-grade Snake", 0, family = "Snake", grade = "Low-grade"),
            entry("builtin:implant-set:10", "Mid-grade Snake", 0, family = "Snake", grade = "Mid-grade"),
            entry("builtin:implant-set:3", "High-grade Snake", 0, family = "Snake", grade = "High-grade"),
            entry(set, "\uE000"), entry(fresh, "\uD83D\uDE80"))
        page.put("total", entries.size).put("entries", JSONArray(entries)); assertEquals(5, decode(root, input).state!!.entries.size)
        page.put("entries", JSONArray(entries.reversed())); reject { decode(root, input) }
    }
    @Test fun repeatedSlotsRepeatedItemsAndForgedCatalogueLabelsFailCompletely() {
        val duplicateSlot = root(detail = recipe(items = listOf(a, c))); reject { decode(duplicateSlot) }
        val duplicateId = root(detail = recipe(items = listOf(a, a.copy(slot = 1)))); reject { decode(duplicateId) }
        val forged = root(detail = recipe(items = listOf(a.copy(name = "Not the catalogue"), b)))
        reject { OfflineImplantSetsCodec.validateAuthority(decode(forged).state!!, features(hasFit = false), emptyList(), catalogue) }
    }
    @Test fun rawStateByteLimitCountsOriginalWhitespaceRatherThanCompactEncoding() {
        val wire = json(root()); val stateAt = wire.indexOf("\"state\":") + "\"state\":".length
        val padded = wire.substring(0, stateAt + 1) + " ".repeat(524_288) + wire.substring(stateAt + 1)
        assertTrue(OfflineImplantSetsCodec.stateByteCount(padded) > 524_288)
        reject { OfflineImplantSetsCodec.response(padded, request()) }
        assertTrue(decode(root()).ok)
    }
    @Test fun rawStateByteLimitCountsEscapedSupplementaryUnicodeWithoutReencoding() {
        val input = request().copy(anchorFitId = fitId); val root = root(input)
        root.getJSONObject("state").getJSONObject("destination").put("name", "\uD83D\uDE80".repeat(50_000))
        val literal = json(root); assertTrue(OfflineImplantSetsCodec.response(literal, input).ok)
        val escaped = literal.replace("\uD83D\uDE80", "\\ud83d\\ude80")
        reject { OfflineImplantSetsCodec.response(escaped, input) }
    }
    @Test fun requestByteAndCharacterBoundsRejectLongRawWhitespaceBeforeParsing() {
        val wire = request().json(); reject { OfflineImplantSetsCodec.decodeRequest(" ".repeat(16_384) + wire) }
        reject { request().copy(argumentsJson = " ".repeat(16_384) + "{}").json() }
        reject { request().copy(requestId = "x".repeat(129)).json() }
        reject { request().copy(requestId = "non-ascii-\u00E9").json() }
    }
    @Test fun fitPreviewChecksLocalOrderedNamesSlotsActivationAndCountEvenUnderCharacterSource() {
        val input = request().copy(anchorFitId = fitId); val wire = root(input)
        wire.getJSONObject("state").put("save_source", source(ImplantLocation.CHARACTER))
        val state = decode(wire, input).state!!
        OfflineImplantSetsCodec.validateAuthority(state, features(ImplantLocation.CHARACTER), listOf(fit()), catalogue)
        for (wrong in listOf(fit().copy(implants = emptyList()), fit().copy(implants = listOf(ImplantSnapshot(a.name, a.slot, true))),
            fit().copy(implants = listOf(ImplantSnapshot(b.name, b.slot, false)))))
            reject { OfflineImplantSetsCodec.validateAuthority(state, features(ImplantLocation.CHARACTER), listOf(wrong), catalogue) }
    }
    @Test fun fitSaveCountChecksBridgeLocalCollectionWhileProfilePreviewHidesFitDestination() {
        val input = request().copy(anchorFitId = fitId, view = request().view.copy(targetProfileId = pilot))
        val wire = root(input); wire.getJSONObject("state").put("destination", profileTarget())
        val state = decode(wire, input).state!!
        OfflineImplantSetsCodec.validateAuthority(state, features(), listOf(fit()), catalogue)
        val bad = state.copy(saveSource = state.saveSource!!.copy(implantCount = 2))
        reject { OfflineImplantSetsCodec.validateAuthority(bad, features(), listOf(fit()), catalogue) }
        reject { OfflineImplantSetsCodec.validateAuthority(state, features(), listOf(fit().copy(implants = emptyList())), catalogue) }
    }
    @Test fun profilePreviewChecksRowsIdentityOrderActivityRevisionAndDirectAssignmentCount() {
        val input = request().copy(anchorFitId = fitId, view = request().view.copy(targetProfileId = pilot)); val wire = root(input)
        wire.getJSONObject("state").put("destination", profileTarget()); val state = decode(wire, input).state!!
        OfflineImplantSetsCodec.validateAuthority(state, features(), listOf(fit()), catalogue)
        val target = state.destination as OfflineImplantSetDestination.Profile
        for (wrong in listOf(target.copy(profileRevision = 5), target.copy(assignedFitCount = 2), target.copy(implants = listOf(row(id = "2".repeat(32)))),
            target.copy(implants = listOf(row(active = true))), target.copy(name = "Other")))
            reject { OfflineImplantSetsCodec.validateAuthority(state.copy(destination = wrong), features(), listOf(fit()), catalogue) }
    }
    @Test fun legacyLabelsPreserveControlsButUnpairedSurrogatesAreNeverValidWireText() {
        val input = request().copy(anchorFitId = fitId)
        for (label in listOf("Legacy\u0001\nFit", "Legacy\u007FFit", "Legacy\u0085Fit", " ")) {
            val wire = root(input); wire.getJSONObject("state").getJSONObject("destination").put("name", label)
            assertEquals(label, (decode(wire, input).state!!.destination as OfflineImplantSetDestination.Fit).name)
        }
        for (label in listOf("\uD800", "\uDC00", "")) {
            val wire = root(input); wire.getJSONObject("state").getJSONObject("destination").put("name", label)
            reject { decode(wire, input) }
        }
    }
    @Test fun characterSaveSourceMustBeActualAssignedProfileNotThePreviewTarget() {
        val other = "profile:" + "9".repeat(32); val input = request().copy(anchorFitId = fitId, view = request().view.copy(targetProfileId = other))
        val wire = root(input); wire.getJSONObject("state").put("destination", JSONObject.NULL).put("save_source", source(ImplantLocation.CHARACTER))
        val state = decode(wire, input).state!!; OfflineImplantSetsCodec.validateAuthority(state, features(ImplantLocation.CHARACTER), listOf(fit()), catalogue)
        reject { OfflineImplantSetsCodec.validateAuthority(state.copy(saveSource = state.saveSource!!.copy(profileId = other)), features(ImplantLocation.CHARACTER), listOf(fit()), catalogue) }
    }
    @Test fun missingSelectionAndMissingProfileStayNullWithoutRetargeting() {
        val input = request().copy(view = request().view.copy(targetProfileId = pilot)); val root = root(input, null)
        val state = decode(root, input).state!!; assertNull(state.detail); assertNull(state.destination)
        val base = features(hasFit = false).copy(profiles = features(hasFit = false).profiles.take(2))
        OfflineImplantSetsCodec.validateAuthority(state, base, emptyList(), catalogue)
        root.getJSONObject("state").put("detail", recipe(fresh)); reject { decode(root, input) }
    }
    @Test fun replayAnchorDisappearanceFallsBackOnlyToLibraryAndRetainsRedo() {
        val input = request().copy(anchorFitId = fitId, view = request().view.copy(historyTarget = fitId), operation = "undo")
        val root = effective(root(input)); val state = root.getJSONObject("state")
        state.put("anchor_fit_id", JSONObject.NULL).put("destination", JSONObject.NULL).put("save_source", JSONObject.NULL).put("history", history("library", redo = 1))
        root.put("bridge", bridge())
        val result = decode(root, input); assertNull(result.state!!.anchorFitId); assertEquals("library", result.state.view.historyTarget); assertEquals(1, result.state.history.redoCount)
        state.put("history", history(fitId, redo = 1)); reject { decode(root, input) }
    }
    @Test fun definiteAndUncertainFailuresRequireExactTriStateAndReopenCode() {
        for (uncertain in listOf(false, true)) {
            val wire = root().put("ok", false).put("state", JSONObject.NULL).put("committed", if (uncertain) JSONObject.NULL else false)
                .put("reopen_required", uncertain).put("error", obj("code" to if (uncertain) "reopen_required" else "stale_context", "message" to "Complete safe error"))
            assertEquals(uncertain, decode(wire).reopenRequired)
            wire.getJSONObject("error").put("code", if (uncertain) "invalid_request" else "reopen_required"); reject { decode(wire) }
        }
        for (message in listOf("", "bad\ntext", "x".repeat(1025), "\uD800")) {
            val wire = root().put("ok", false).put("state", JSONObject.NULL).put("error", obj("code" to "invalid_request", "message" to message)); reject { decode(wire) }
        }
    }
    @Test fun readNeverMutatesAndEffectiveGenerationCannotJumpOverflowOrChangeSession() {
        reject { decode(root().put("committed", true)) }
        reject { decode(root().put("bridge", bridge())) }
        val input = request(null).copy(operation = "create", argumentsJson = args("name" to "New"))
        val good = effective(root(input, recipe(fresh, "New", 1, emptyList())))
        assertTrue(decode(good, input).committed!!)
        reject { decode(effective(root(input, recipe(fresh, "New", 1, emptyList())), 9), input) }
        val exhausted = input.copy(context = ctx.copy(generation = Long.MAX_VALUE))
        val bad = root(exhausted, recipe(fresh, "New", 1, emptyList())).put("committed", true)
        reject { decode(bad, exhausted) }
    }
    @Test fun createRequiresFreshRevisionOneEmptyMembershipAndKnownIdentityExclusion() {
        val input = request().copy(operation = "create", argumentsJson = args("name" to "New"))
        val before = decode(root()).state!!
        val good = decode(effective(root(input, recipe(fresh, "New", 1, emptyList()))), input)
        OfflineImplantSetsCodec.validateResult(good, input, before)
        reject { decode(effective(root(input, recipe(set, "New", 1, emptyList()))), input) }
        reject { decode(effective(root(input, recipe(fresh, "New", 2, emptyList()))), input) }
        reject { decode(effective(root(input, recipe(fresh, "New", 1, listOf(a)))), input) }
    }
    @Test fun customDuplicateIsDetachedOrderedMembershipNotActivationOrLiveBinding() {
        val input = request().copy(operation = "duplicate", argumentsJson = args("set_id" to set, "revision" to 3, "name" to "Copy"))
        val before = decode(root()).state!!
        val good = decode(effective(root(input, recipe(fresh, "Copy", 1))), input); OfflineImplantSetsCodec.validateResult(good, input, before)
        val wrong = decode(effective(root(input, recipe(fresh, "Copy", 1, listOf(b, a)))), input)
        reject { OfflineImplantSetsCodec.validateResult(wrong, input, before) }
    }
    @Test fun unchangedRenameIsNoopAndOrderedAddReappendIsValidated() {
        val before = decode(root()).state!!
        val rename = request().copy(operation = "rename", argumentsJson = args("set_id" to set, "revision" to 3, "name" to "Recipe"))
        OfflineImplantSetsCodec.validateResult(decode(root(rename), rename), rename, before)
        reject { OfflineImplantSetsCodec.validateResult(decode(effective(root(rename, recipe(revision = 4))), rename), rename, before) }
        val add = request().copy(operation = "add_item", argumentsJson = args("set_id" to set, "revision" to 3, "item_id" to 11, "replace_item_id" to 11))
        val result = decode(effective(root(add, recipe(revision = 4, items = listOf(b, a)))), add)
        OfflineImplantSetsCodec.validateResult(result, add, before)
        val wrong = decode(effective(root(add, recipe(revision = 4))), add)
        reject { OfflineImplantSetsCodec.validateResult(wrong, add, before) }
    }
    @Test fun sourceSaveIncludesInactiveLocalRowsEvenWithOtherCharacterPreview() {
        val input = request().copy(anchorFitId = fitId, view = request().view.copy(targetProfileId = pilot), operation = "save_current",
            argumentsJson = args("name" to "Saved inactive", "fit_revision" to 2))
        val beforeWire = root(input.copy(operation = "read", argumentsJson = "{}")); beforeWire.getJSONObject("state").put("destination", profileTarget())
        val before = decode(beforeWire, input.copy(operation = "read", argumentsJson = "{}")).state!!
        val wire = effective(root(input, recipe(fresh, "Saved inactive", 1, listOf(a)))); wire.getJSONObject("state").put("destination", profileTarget())
        val result = decode(wire, input)
        OfflineImplantSetsCodec.validateTransition(result, input, before, features(), listOf(fit()), features(context = ctx.copy(generation = 8)), catalogue)
        val wrong = result.copy(state = result.state!!.copy(detail = result.state.detail!!.copy(items = listOf(b))))
        reject { OfflineImplantSetsCodec.validateTransition(wrong, input, before, features(), listOf(fit()), features(context = ctx.copy(generation = 8)), catalogue) }
    }
    @Test fun localApplySkipsInactiveExactDuplicateAndAppendsFreshActiveRowsWithoutSwitchingSource() {
        val input = request().copy(anchorFitId = fitId, view = request().view.copy(historyTarget = fitId), operation = "apply_fit",
            argumentsJson = args("set_id" to set, "revision" to 3, "fit_revision" to 2))
        val beforeInput = input.copy(operation = "read", argumentsJson = "{}")
        val oldWire = root(beforeInput); oldWire.getJSONObject("state").put("save_source", source(ImplantLocation.CHARACTER))
        val before = decode(oldWire, beforeInput).state!!; val nextRows = listOf(row(), row(b, "2".repeat(32), true))
        val wire = effective(root(input)); wire.getJSONObject("state").put("destination", fitTarget(nextRows, 3)).put("save_source", source(ImplantLocation.CHARACTER, fitRevision = 3))
        wire.put("bridge", bridge(listOf(fit(nextRows, 3)))); val result = decode(wire, input)
        val next = features(ImplantLocation.CHARACTER, context = ctx.copy(generation = 8), fitRevision = 3)
        OfflineImplantSetsCodec.validateTransition(result, input, before, features(ImplantLocation.CHARACTER), listOf(fit()), next, catalogue)
        val wrongRows = listOf(row(active = true), row(b, "2".repeat(32), true))
        val wrong = result.copy(state = result.state!!.copy(destination = (result.state.destination as OfflineImplantSetDestination.Fit).copy(implants = wrongRows)),
            bridge = result.bridge!!.copy(fits = listOf(fit(wrongRows, 3))))
        reject { OfflineImplantSetsCodec.validateTransition(wrong, input, before, features(ImplantLocation.CHARACTER), listOf(fit()), next, catalogue) }
    }
    @Test fun duplicateOnlyFitApplicationPreservesCompleteInactiveRowsAndGeneration() {
        val input = request().copy(anchorFitId = fitId, view = request().view.copy(historyTarget = fitId), operation = "apply_fit",
            argumentsJson = args("set_id" to set, "revision" to 3, "fit_revision" to 2))
        val read = input.copy(operation = "read", argumentsJson = "{}")
        val before = decode(root(read, recipe(items = listOf(a))), read).state!!
        val result = decode(root(input, recipe(items = listOf(a))), input)
        OfflineImplantSetsCodec.validateTransition(result, input, before, features(), listOf(fit()), features(), catalogue)
        reject { OfflineImplantSetsCodec.validateTransition(result.copy(bridge = result.bridge!!.copy(fits = listOf(fit().copy(name = "Changed")))),
            input, before, features(), listOf(fit()), features(), catalogue) }
    }
    @Test fun noFitProfileApplicationRecreatesIdenticalInactiveTypeAndPreservesSkills() {
        val input = request().copy(view = request().view.copy(targetProfileId = pilot), operation = "apply_profile",
            argumentsJson = args("set_id" to set, "revision" to 3, "profile_id" to pilot, "profile_revision" to 4))
        val read = input.copy(operation = "read", argumentsJson = "{}")
        val beforeWire = root(read, recipe(items = listOf(a))); beforeWire.getJSONObject("state").put("destination", profileTarget(count = 0))
        val before = decode(beforeWire, read).state!!; val nextRows = listOf(row(id = "2".repeat(32), active = true))
        val wire = effective(root(input, recipe(items = listOf(a)))); wire.getJSONObject("state").put("destination", profileTarget(nextRows, 5, 0))
        val result = decode(wire, input); val old = features(hasFit = false); val next = features(hasFit = false, rows = nextRows, context = ctx.copy(generation = 8), profileRevision = 5)
        OfflineImplantSetsCodec.validateTransition(result, input, before, old, emptyList(), next, catalogue)
        val wrong = next.copy(profiles = next.profiles.map { if (it.id == pilot) it.copy(levels = emptyMap()) else it })
        reject { OfflineImplantSetsCodec.validateTransition(result, input, before, old, emptyList(), wrong, catalogue) }
    }
}
