package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic wire witnesses, not EOS parity or Android execution. */
@RunWith(AndroidJUnit4::class)
class OfflineDamagePatternsContractTest {
    private val pattern = "damage:" + "b".repeat(32)
    private val session = OfflineContext("a".repeat(32), "c".repeat(64), 7)
    private fun request(id: String? = pattern) = OfflineDamageRequest("damage-test", session, null, OfflineDamageView(selectedPatternId = id))
    private fun values(a: Number = 3L, b: Number = 7.0, c: Number = 11.0, d: Number = -0.0) =
        JSONObject().put("emAmount", a).put("thermalAmount", b).put("kineticAmount", c).put("explosiveAmount", d)
    private fun metadata(id: String = pattern, assignable: Boolean = true) = JSONObject().put("pattern_id", id)
        .put("kind", when { id == SELECTED_AMMO_PATTERN_ID -> "selected_ammo"; id.startsWith("damage:builtin:") -> "builtin"; else -> "custom" })
        .put("name", if (id == SELECTED_AMMO_PATTERN_ID) "Selected Ammo" else "[Synthetic] Pattern")
        .put("revision", if (id.startsWith("damage:builtin:")) 0 else 3).put("bound_fit_count", 0).put("bound_module_count", 0).put("affected_fit_count", 0)
        .put("assignable", assignable).put("unassignable_reason", if (assignable) JSONObject.NULL else "zero_total")
    private fun percentages(raw: JSONObject): JSONObject {
        val total = DAMAGE_PATTERN_FIELDS.sumOf { (raw.get(it) as Number).toDouble() }
        return JSONObject().also { result -> DAMAGE_PATTERN_FIELDS.forEach { key ->
            result.put(key, if (total > 0) (raw.get(key) as Number).toDouble() / total * 100.0 else 0.0)
        } }
    }
    private fun root(input: OfflineDamageRequest = request(), raw: JSONObject = values()): JSONObject {
        val assignable = DAMAGE_PATTERN_FIELDS.sumOf { (raw.get(it) as Number).toDouble() } > 0
        val detail = input.view.selectedPatternId?.let { id -> metadata(id, assignable).put("values", raw)
            .put("percentages", percentages(raw)).put("bound_fits", JSONObject().put("offset", input.view.boundOffset)
                .put("limit", 50).put("total", 0).put("entries", JSONArray()))
            .put("bound_modules", JSONObject().put("offset", input.view.moduleOffset).put("limit", 50).put("total", 0).put("entries", JSONArray())) }
        val state = JSONObject().put("version", 3).put("item", JSONObject.NULL).put("module", JSONObject.NULL).put("context", input.context.json()).put("fit_id", input.fitId ?: JSONObject.NULL)
            .put("fit_revision", if (input.fitId == null) JSONObject.NULL else 2)
            .put("selection", JSONObject().put("kind", if (input.fitId == null) "no_fit" else "anonymous")
                .put("pattern_id", JSONObject.NULL).put("pattern_revision", JSONObject.NULL).put("binding_revision", JSONObject.NULL))
            .put("page", JSONObject().put("query", input.view.query).put("offset", input.view.offset).put("limit", input.view.limit)
                .put("total", 1).put("entries", if (input.view.offset == 0L) JSONArray().put(metadata(input.view.selectedPatternId ?: pattern, assignable)) else JSONArray()))
            .put("detail", detail ?: JSONObject.NULL).put("history", JSONObject().put("undo_count", 0).put("redo_count", 0).put("limit", 100)
                .put("undo_label", JSONObject.NULL).put("redo_label", JSONObject.NULL))
        return JSONObject().put("version", 3).put("request_id", input.requestId).put("ok", true).put("committed", false)
            .put("reopen_required", false).put("state", state).put("bridge", JSONObject.NULL).put("error", JSONObject.NULL)
    }
    private fun decode(row: JSONObject, input: OfflineDamageRequest = request()) = OfflineDamageCodec.response(OfflineFeatureCodec.json(row), input)
    private fun rejects(block: () -> Unit) {
        try { block(); fail("Accepted invalid damage wire") }
        catch (_: BridgeProtocolException) { } catch (_: org.json.JSONException) { } catch (_: ArithmeticException) { }
    }
    private fun reject(row: JSONObject, input: OfflineDamageRequest = request()) = rejects { decode(row, input) }
    private fun invalid(input: OfflineDamageRequest) = rejects { input.json() }
    private fun args(vararg pairs: Pair<String, Any>) = OfflineFeatureCodec.json(JSONObject().also { row -> pairs.forEach { row.put(it.first, it.second) } })
    private fun bootstrap(input: OfflineDamageRequest) = JSONObject().put("version", 1).put("request_id", "bootstrap")
        .put("session_id", input.context.sessionId).put("status", "ok").put("fits", JSONArray()).put("error", JSONObject.NULL)

    @Test fun previousDamageResponseAndStateVersionsAreRejected() {
        reject(root().put("version", 2))
        val oldState = root(); oldState.getJSONObject("state").put("version", 2); reject(oldState)
        val missingModule = root(); missingModule.getJSONObject("state").remove("module"); reject(missingModule)
        invalid(request().copy(operation = "delete", argumentsJson = args("pattern_id" to pattern, "revision" to 3, "bound_fit_count" to 0)))
    }
    @Test fun rawKindsFractionsAndSignedZeroRemainDistinctFromDerivedPercentages() {
        val detail = decode(root()).state!!.detail!!
        assertTrue(detail.values.fields.getValue("emAmount") is Long)
        assertTrue(detail.values.fields.getValue("thermalAmount") is Double)
        assertEquals((-0.0).toBits(), detail.values.fields.getValue("explosiveAmount").toDouble().toBits())
        assertEquals(3.0 / 21.0 * 100.0, detail.percentages.fields.getValue("emAmount").toDouble(), 1e-12)
        val fraction = decode(root(raw = values(7.5, 2.5, 1L, 0L))).state!!.detail!!
        assertEquals(7.5, fraction.values.fields["emAmount"])
    }
    @Test fun all118CanonicalBuiltinIdsAreAcceptedAndForeignAliasesRejected() {
        for (ordinal in 1..118) {
            val input = request("damage:builtin:-$ordinal")
            assertTrue(decode(root(input), input).state!!.detail!!.entry.readonly); input.json()
        }
        for (id in listOf("damage:builtin:0", "damage:builtin:-119", "damage:builtin:-01", "damage:builtin:+1", "target:builtin:-1", "damage:bad")) invalid(request(id))
    }
    @Test fun completeSourceOrderedPagesAndCrossedCustomBoundaryRemainReachable() {
        val ids = (1..118).map { "damage:builtin:-$it" } + (0..57).map { "damage:" + it.toString(16).padStart(32, '0') }
        val observed = mutableListOf<String>()
        for (offset in listOf(0L, 50L, 100L, 150L)) {
            val input = request(null).copy(view = OfflineDamageView(offset = offset))
            val row = root(input); row.getJSONObject("state").getJSONObject("page").put("total", ids.size)
                .put("entries", JSONArray(ids.drop(offset.toInt()).take(50).map { metadata(it) }))
            observed += decode(row, input).state!!.entries.map { it.id }
        }
        assertEquals(ids, observed)
        val input = request(null).copy(view = OfflineDamageView(query = "untrimmed "))
        val row = root(input); row.getJSONObject("state").getJSONObject("page").put("total", 3)
            .put("entries", JSONArray(listOf(metadata("damage:builtin:-3"), metadata("damage:builtin:-17"), metadata(pattern))))
        assertEquals(listOf("damage:builtin:-3", "damage:builtin:-17", pattern), decode(row, input).state!!.entries.map { it.id })
        row.getJSONObject("state").getJSONObject("page").put("entries", JSONArray(listOf(metadata(pattern), metadata("damage:builtin:-17"), metadata("damage:builtin:-3"))))
        reject(row, input)
    }
    @Test fun divideFirstPercentagesAcceptLargeFiniteAndSubnormalContributions() {
        for (raw in listOf(values(1e308, 0.0, 0.0, 0.0), values(Double.MIN_VALUE, Double.MIN_VALUE, 0.0, 0.0),
            values(Long.MAX_VALUE, Long.MAX_VALUE, Long.MAX_VALUE, Long.MAX_VALUE))) {
            val detail = decode(root(raw = raw)).state!!.detail!!
            assertTrue(detail.percentages.fields.values.all { it.toDouble().isFinite() })
        }
        val row = root(); row.getJSONObject("state").getJSONObject("detail").getJSONObject("percentages").put("emAmount", 15.0); reject(row)
        val integer = root(); integer.getJSONObject("state").getJSONObject("detail").getJSONObject("percentages").put("explosiveAmount", 0); reject(integer)
    }
    @Test fun zeroUnassignedCustomHasExplicitReasonAndFourPositiveZeroPercentages() {
        val row = root(raw = values(0L, -0.0, 0.0, 0L)); val detail = decode(row).state!!.detail!!
        assertFalse(detail.entry.assignable); assertEquals("zero_total", detail.entry.unassignableReason)
        assertTrue(detail.percentages.fields.values.all { it is Double && it.toBits() == 0.0.toBits() })
        row.getJSONObject("state").getJSONObject("detail").getJSONObject("percentages").put("emAmount", -0.0); reject(row)
        val falseReason = root(); falseReason.getJSONObject("state").getJSONObject("detail").put("unassignable_reason", "zero_total"); reject(falseReason)
        val zeroBuiltin = request("damage:builtin:-1"); reject(root(zeroBuiltin, values(0L, 0L, 0L, 0L)), zeroBuiltin)
    }
    @Test fun rawLongBoundsBooleanNullNegativeAndOverflowValuesReject() {
        assertEquals(Long.MAX_VALUE, decode(root(raw = values(Long.MAX_VALUE))).state!!.detail!!.values.fields["emAmount"])
        val wire = OfflineFeatureCodec.json(root(raw = values(Long.MAX_VALUE)))
        rejects { OfflineDamageCodec.response(wire.replace(Long.MAX_VALUE.toString(), "9223372036854775808"), request()) }
        for (wrong in listOf(-1.0, JSONObject.NULL, true, "1")) {
            val row = root(); row.getJSONObject("state").getJSONObject("detail").getJSONObject("values").put("emAmount", wrong); reject(row)
        }
        rejects { OfflineDamageCodec.values(values(Double.MAX_VALUE, Double.MAX_VALUE)) }
        rejects { OfflineDamageCodec.response(OfflineFeatureCodec.json(root()).replace("7.0", "1e999"), request()) }
    }
    @Test fun editorOnlySaveUsesFloatTokensForBlankIntegralAndNegativeZeroInputs() {
        val draft = OfflineDamageDraft("create", null, null, session.sessionId, "Custom", listOf("", "1", "80206", "-0.0"))
        val input = request(null).copy(operation = "create", argumentsJson = args("name" to draft.name, "values" to draft.values()))
        val parsed = OfflineFeatureCodec.parse(input.json()).getJSONObject("arguments").getJSONObject("values")
        DAMAGE_PATTERN_FIELDS.forEach { assertTrue(parsed.get(it) is Double) }
        assertEquals(0.0, parsed.get("emAmount")); assertEquals(80206.0, parsed.get("kineticAmount"))
        assertEquals((-0.0).toBits(), (parsed.get("explosiveAmount") as Double).toBits())
        invalid(input.copy(argumentsJson = args("name" to "Custom", "values" to draft.values().put("emAmount", 0))))
        val zero = OfflineDamageDraft("create", null, null, session.sessionId, "Zero", List(4) { "" })
        request(null).copy(operation = "create", argumentsJson = args("name" to "Zero", "values" to zero.values())).json()
    }
    @Test fun duplicateAssignDetachAndResetAreIdentityOnlyNotDisplayValueSaves() {
        val source = "damage:builtin:-17"
        for (operation in listOf("duplicate", "assign", "detach_to_anonymous", "reset_uniform")) {
            val parameters = JSONObject()
            if (operation != "reset_uniform") parameters.put("pattern_id", source).put("revision", 0)
            if (operation == "duplicate") parameters.put("name", "Independent copy") else parameters.put("fit_revision", 9)
            if (operation == "detach_to_anonymous") parameters.put("binding_revision", 3)
            val input = request(source).copy(fitId = if (operation == "duplicate") null else "f".repeat(32), operation = operation,
                argumentsJson = OfflineFeatureCodec.json(parameters))
            assertFalse(OfflineFeatureCodec.parse(input.json()).getJSONObject("arguments").has("values"))
            invalid(input.copy(argumentsJson = OfflineFeatureCodec.json(parameters.put("values", values()))))
        }
        invalid(request().copy(operation = "detach_to_anonymous", argumentsJson = args("pattern_id" to pattern, "revision" to 3, "fit_revision" to 2)))
    }
    @Test fun unicodeCodePointBoundsPythonWhitespaceAndReservedExactNamesAgree() {
        val astral = "\uD83D\uDE80"
        assertEquals(astral.repeat(200), OfflineDamageCodec.name("\u0085\u00A0" + astral.repeat(200) + "\u3000"))
        for (name in listOf(astral.repeat(201), "A\u007FB", "A\u0085B", "\uD800", "\uDC00", " ", "Uniform", " Selected Ammo "))
            rejects { OfflineDamageCodec.name(name) }
        assertEquals("uniform", OfflineDamageCodec.name(" uniform ")); assertEquals("selected ammo", OfflineDamageCodec.name("selected ammo"))
        assertEquals("[NPC|Mission] Name", OfflineDamageCodec.name(" [NPC|Mission] Name "))
    }
    @Test fun unknownDuplicateFieldsWrongScalarKindsAndRequestBoundsReject() {
        invalid(request().copy(view = request().view.copy(query = "x".repeat(201))))
        invalid(request().copy(view = request().view.copy(limit = 51))); invalid(request().copy(requestId = "bad\nID"))
        invalid(request().copy(argumentsJson = "{\"unexpected\":0}")); invalid(request().copy(argumentsJson = "{\"x\":1,\"x\":2}"))
        invalid(request().copy(operation = "clear")); invalid(request().copy(fitId = "not-a-fit"))
        reject(root().put("unexpected", 0)); reject(root().put("version", 1.0))
        val raw = OfflineFeatureCodec.json(root()); rejects { OfflineDamageCodec.response(raw.replace("\"version\":3", "\"version\":3,\"version\":3"), request()) }
        val truncated = root(); truncated.getJSONObject("state").getJSONObject("page").put("total", 2); reject(truncated)
    }
    @Test fun outOfRangePagesAreEmptyWithoutClampingAndBoundNamesKeepExistingContract() {
        val input = request().copy(view = request().view.copy(offset = Long.MAX_VALUE, boundOffset = 200))
        val result = decode(root(input), input).state!!
        assertEquals(Long.MAX_VALUE, result.view.offset); assertTrue(result.entries.isEmpty()); assertNotNull(result.detail)
        for (name in listOf(" ", "\t", "Legacy\u0001\nFit")) {
            val row = root(); val state = row.getJSONObject("state"); val detail = state.getJSONObject("detail")
            state.getJSONObject("page").getJSONArray("entries").getJSONObject(0).put("bound_fit_count", 1).put("affected_fit_count", 1)
            detail.put("bound_fit_count", 1).put("affected_fit_count", 1).getJSONObject("bound_fits").put("total", 1).put("entries", JSONArray().put(
                JSONObject().put("fit_id", "f".repeat(32)).put("name", name).put("revision", 2)))
            assertEquals(name, decode(row).state!!.detail!!.boundFits.single().name)
        }
    }
    @Test fun namedSelectionIncludesPatternRevisionAndOffPageDetachDoesNotNeedDetail() {
        val input = request(null).copy(fitId = "f".repeat(32)); val row = root(input)
        val state = row.getJSONObject("state"); state.getJSONObject("selection").put("kind", "named")
            .put("pattern_id", "damage:builtin:-118").put("pattern_revision", 0).put("binding_revision", 9)
        assertEquals(0L, decode(row, input).state!!.selection.patternRevision)
        state.getJSONObject("selection").put("pattern_revision", 1); reject(row, input)
        state.getJSONObject("selection").put("kind", "none"); reject(row, input)
        val named = root(request().copy(fitId = "f".repeat(32))); val selection = named.getJSONObject("state").getJSONObject("selection")
        selection.put("kind", "named").put("pattern_id", pattern).put("pattern_revision", 4).put("binding_revision", 1)
        reject(named, request().copy(fitId = "f".repeat(32)))
    }
    @Test fun definiteAndUncertainErrorsHaveStrictCommitTriState() {
        for (uncertain in listOf(false, true)) {
            val row = root().put("ok", false).put("committed", if (uncertain) JSONObject.NULL else false)
                .put("reopen_required", uncertain).put("state", JSONObject.NULL)
                .put("error", JSONObject().put("code", "new_safe_code").put("message", "Complete safe error"))
            assertEquals(uncertain, decode(row).reopenRequired)
            row.put("committed", true); reject(row)
        }
        for (message in listOf("", "bad\ntext", "x".repeat(1025), "\uD800")) {
            val row = root().put("ok", false).put("state", JSONObject.NULL).put("error", JSONObject().put("code", "invalid").put("message", message)); reject(row)
        }
    }
    @Test fun readsNoopsAndMutationsRequireExactGenerationAndCompleteBootstrap() {
        val input = request().copy(operation = "rename", argumentsJson = args("pattern_id" to pattern, "revision" to 3, "name" to "Changed"))
        val row = root(input).put("bridge", bootstrap(input)); assertFalse(decode(row, input).committed!!)
        row.put("committed", true); row.getJSONObject("state").put("context", session.copy(generation = 8).json())
        assertTrue(decode(row, input).committed!!)
        row.getJSONObject("state").put("context", session.copy(generation = 9).json()); reject(row, input)
        reject(root().put("bridge", bootstrap(request())))
        reject(root().put("committed", true))
    }
    @Test fun deletedDetailAndCreatedDetailMustMatchOperationOwnership() {
        val input = request().copy(operation = "delete", argumentsJson = args("pattern_id" to pattern, "revision" to 3, "bound_fit_count" to 0, "bound_module_count" to 0, "affected_fit_count" to 0))
        val row = root(input).put("bridge", bootstrap(input)); reject(row, input)
        row.getJSONObject("state").put("detail", JSONObject.NULL); decode(row, input)
        invalid(input.copy(argumentsJson = args("pattern_id" to "damage:builtin:-1", "revision" to 0, "bound_fit_count" to 0, "bound_module_count" to 0, "affected_fit_count" to 0)))
        invalid(input.copy(argumentsJson = args("pattern_id" to pattern, "revision" to 3)))
    }
    @Test fun rawWireStateByteLimitCountsEscapedAstralDataRatherThanReserializedText() {
        val row = root(); val state = row.getJSONObject("state"); val detail = state.getJSONObject("detail")
        val fits = JSONArray(); repeat(50) { index -> fits.put(JSONObject().put("fit_id", index.toString(16).padStart(32, '0'))
            .put("name", "\uD83D\uDE80".repeat(1000)).put("revision", 1)) }
        state.getJSONObject("page").getJSONArray("entries").getJSONObject(0).put("bound_fit_count", 50).put("affected_fit_count", 50)
        detail.put("bound_fit_count", 50).put("affected_fit_count", 50).getJSONObject("bound_fits").put("total", 50).put("entries", fits)
        val compact = OfflineFeatureCodec.json(row); decode(row)
        val escaped = compact.replace("\uD83D\uDE80", "\\ud83d\\ude80")
        assertTrue(escaped.toByteArray(Charsets.UTF_8).size > 524_288)
        rejects { OfflineDamageCodec.response(escaped, request()) }
    }
    private fun itemRequest(operation: String = "item_options", id: Int = 210) = request(null).copy(fitId = "f".repeat(32),
        operation = operation, argumentsJson = args("item_id" to id, "fit_revision" to 2))
    private fun itemWire(input: OfflineDamageRequest = itemRequest(), eligible: Boolean = true, available: Boolean = true,
        reason: String? = null, raw: JSONObject? = values(0L, 0L, 83.0, 0L)) = root(input).also {
        it.getJSONObject("state").put("item", JSONObject().put("item_id", 210).put("name", "Scourge Light Missile")
            .put("eligible", eligible).put("available", available).put("unavailable_reason", reason ?: JSONObject.NULL)
            .put("values", raw ?: JSONObject.NULL))
    }
    @Test fun itemOptionsIsReadLikeWithExactItemAndFitRevisionPreconditions() {
        val input = itemRequest(); val row = itemWire(input)
        assertEquals(3, JSONObject(input.json()).getInt("version"))
        assertTrue(damageReadLike(input.operation)); assertFalse(damageReadLike("apply_item"))
        val parsed = decode(row, input)
        assertFalse(parsed.committed!!); assertNull(parsed.bridge); assertEquals(session, parsed.state!!.context)
        assertEquals(210, parsed.state.item!!.itemId)
        assertTrue(parsed.state.item.values!!.fields["kineticAmount"] is Double)
        assertTrue(parsed.state.item.values.fields["emAmount"] is Long)
        reject(itemWire(input).put("bridge", bootstrap(input)), input)
        reject(itemWire(input).put("committed", true), input)
        val stale = itemWire(input); stale.getJSONObject("state").put("fit_revision", 3); reject(stale, input)
        val foreign = itemWire(input); foreign.getJSONObject("state").getJSONObject("item").put("item_id", 185); reject(foreign, input)
        invalid(input.copy(fitId = null))
        for (id in listOf(0L, -1L, Int.MAX_VALUE.toLong() + 1, 1.0, true))
            invalid(input.copy(argumentsJson = args("item_id" to id, "fit_revision" to 2)))
        invalid(input.copy(argumentsJson = args("item_id" to 210, "fit_revision" to 2, "values" to values())))
        invalid(input.copy(argumentsJson = args("item_id" to 210, "fit_revision" to 0)))
    }
    @Test fun itemAvailabilityCrossFieldsAndNumericKindsAreStrict() {
        val input = itemRequest()
        val missing = itemWire(input, false, false, "no_damage_attributes", null)
        assertFalse(decode(missing, input).state!!.item!!.eligible)
        val invalid = itemWire(input, true, false, "invalid_values", null)
        assertNull(decode(invalid, input).state!!.item!!.values)
        val zero = itemWire(input, true, false, "zero_total", values(0L, 0L, 0L, 0L))
        assertEquals("zero_total", decode(zero, input).state!!.item!!.unavailableReason)
        val changes: List<(JSONObject) -> Unit> = listOf(
            { it.put("eligible", false) }, { it.put("available", false) }, { it.put("unavailable_reason", "zero_total") },
            { it.put("values", JSONObject.NULL) }, { it.put("item_id", 210.0) }, { it.put("extra", 0) },
            { it.put("name", "bad\nname") }, { it.put("name", "x".repeat(1025)) },
            { it.getJSONObject("values").put("kineticAmount", -1) },
        )
        changes.forEach { change -> val row = itemWire(input); change(row.getJSONObject("state").getJSONObject("item")); reject(row, input) }
        reject(itemWire(input, true, false, "zero_total", values()), input)
        reject(itemWire(input, true, true, null, values(0L, 0L, 0L, 0L)), input)
        val ordinary = root(); ordinary.getJSONObject("state").put("item", itemWire(input).getJSONObject("state").getJSONObject("item")); reject(ordinary)
        val absent = itemWire(input); absent.getJSONObject("state").put("item", JSONObject.NULL).put("module", JSONObject.NULL); reject(absent, input)
    }
    @Test fun protectedSpecialMetadataAndCrudAreDistinctFromBuiltinAndCustom() {
        val input = request(SELECTED_AMMO_PATTERN_ID)
        val special = decode(root(input), input).state!!.detail!!.entry
        assertEquals("selected_ammo", special.kind); assertTrue(special.readonly); assertFalse(special.duplicable)
        for (operation in listOf("rename", "duplicate", "update_values", "delete")) {
            val parameters = JSONObject().put("pattern_id", SELECTED_AMMO_PATTERN_ID).put("revision", 3)
            when (operation) {
                "rename", "duplicate" -> parameters.put("name", "Not protected")
                "update_values" -> parameters.put("values", values(1.0, 2.0, 3.0, 4.0))
                "delete" -> parameters.put("bound_fit_count", 0).put("bound_module_count", 0).put("affected_fit_count", 0)
            }
            invalid(input.copy(operation = operation, argumentsJson = OfflineFeatureCodec.json(parameters)))
        }
        for ((key, value) in listOf("kind" to "custom", "kind" to "builtin", "name" to "Wrong", "revision" to 0)) {
            val row = root(input); row.getJSONObject("state").getJSONObject("detail").put(key, value); reject(row, input)
        }
        val zero = root(input, values(0L, 0L, 0L, 0L)); reject(zero, input)
        val assign = input.copy(fitId = "f".repeat(32), operation = "assign", argumentsJson = args(
            "pattern_id" to SELECTED_AMMO_PATTERN_ID, "revision" to 3, "fit_revision" to 2))
        assign.json()
        assign.copy(operation = "detach_to_anonymous", argumentsJson = args("pattern_id" to SELECTED_AMMO_PATTERN_ID,
            "revision" to 3, "fit_revision" to 2, "binding_revision" to 4)).json()
        reject(root().put("version", 1))
        val oldState = root(); oldState.getJSONObject("state").put("version", 1); reject(oldState)
    }
    @Test fun specialSectionMustFollowBuiltinsAndPrecedeCustoms() {
        val input = request(null)
        val row = root(input); val page = row.getJSONObject("state").getJSONObject("page").put("total", 3)
        page.put("entries", JSONArray(listOf(metadata("damage:builtin:-118"), metadata(SELECTED_AMMO_PATTERN_ID), metadata())))
        assertEquals("selected_ammo", decode(row, input).state!!.entries[1].kind)
        page.put("entries", JSONArray(listOf(metadata("damage:builtin:-118"), metadata(), metadata(SELECTED_AMMO_PATTERN_ID))))
        reject(row, input)
        page.put("entries", JSONArray(listOf(metadata(SELECTED_AMMO_PATTERN_ID), metadata("damage:builtin:-118"), metadata())))
        reject(row, input)
    }

    private fun appliedItemWire(input: OfflineDamageRequest = itemRequest("apply_item"), committed: Boolean = true): JSONObject {
        // Explicitly synthetic bootstrap: only protocol shape/cross-field ownership is tested.
        val row = itemWire(input); val state = row.getJSONObject("state")
        val nextRevision = if (committed) 3 else 2
        row.put("committed", committed)
        state.put("context", session.copy(generation = if (committed) 8 else 7).json()).put("fit_revision", nextRevision)
        state.getJSONObject("selection").put("kind", "named").put("pattern_id", SELECTED_AMMO_PATTERN_ID)
            .put("pattern_revision", 3).put("binding_revision", 4)
        val entry = metadata(SELECTED_AMMO_PATTERN_ID).put("bound_fit_count", 1).put("affected_fit_count", 1)
        state.getJSONObject("page").put("entries", JSONArray().put(entry))
        val raw = values(0L, 0L, 83.0, 0L)
        val detail = metadata(SELECTED_AMMO_PATTERN_ID).put("bound_fit_count", 1).put("affected_fit_count", 1).put("values", raw)
            .put("percentages", percentages(raw)).put("bound_fits", JSONObject().put("offset", 0).put("limit", 50).put("total", 1)
                .put("entries", JSONArray().put(JSONObject().put("fit_id", input.fitId).put("name", "Synthetic fit").put("revision", nextRevision))))
        detail.put("bound_modules", JSONObject().put("offset", input.view.moduleOffset).put("limit", 50).put("total", 0).put("entries", JSONArray()))
        state.put("detail", detail)
        val statNames = listOf("cpu_output", "powergrid_output", "capacitor_capacity", "capacitor_recharge_time", "max_velocity", "max_target_range",
            "cpu_used", "powergrid_used", "drone_control_range", "drone_bandwidth_used", "weapon_dps", "drone_dps", "total_dps",
            "total_volley", "capacitor_used", "capacitor_recharge", "capacitor_stable", "capacitor_state", "gun_optimal", "gun_falloff",
            "shield_hp", "shield_ehp_uniform", "shield_em_resonance", "shield_thermal_resonance", "shield_kinetic_resonance", "shield_explosive_resonance",
            "armor_hp", "armor_ehp_uniform", "armor_em_resonance", "armor_thermal_resonance", "armor_kinetic_resonance", "armor_explosive_resonance",
            "hull_hp", "hull_ehp_uniform", "hull_em_resonance", "hull_thermal_resonance", "hull_kinetic_resonance", "hull_explosive_resonance", "scan_resolution")
        val stats = JSONObject(); statNames.forEach { stats.put(it, JSONObject().put("value", JSONObject.NULL).put("unit", "")) }
        val fit = JSONObject().put("id", input.fitId).put("revision", nextRevision).put("name", "Synthetic fit").put("ship", "Vexor")
            .put("stats", stats).put("modules", JSONArray()).put("skills", JSONObject()).put("implants", JSONArray()).put("projections", JSONArray()).put("commands", JSONArray())
        return row.put("bridge", bootstrap(input).put("fits", JSONArray().put(fit)))
    }
    @Test fun applySelectsProtectedDetailAndExactRawValuesWithStrictCommitRevision() {
        val input = itemRequest("apply_item")
        val applied = decode(appliedItemWire(input), input)
        assertTrue(applied.committed!!); assertEquals(SELECTED_AMMO_PATTERN_ID, applied.state!!.detail!!.entry.id)
        assertEquals(applied.state.item!!.values, applied.state.detail.values)
        assertFalse(decode(appliedItemWire(input, false), input).committed!!)
        for ((committed, wrongRevision) in listOf(true to 2, false to 3)) {
            val row = appliedItemWire(input, committed); val state = row.getJSONObject("state")
            state.put("fit_revision", wrongRevision)
            state.getJSONObject("detail").getJSONObject("bound_fits").getJSONArray("entries").getJSONObject(0).put("revision", wrongRevision)
            row.getJSONObject("bridge").getJSONArray("fits").getJSONObject(0).put("revision", wrongRevision)
            reject(row, input)
        }
        val wrongKind = appliedItemWire(input)
        wrongKind.getJSONObject("state").getJSONObject("item").getJSONObject("values").put("kineticAmount", 83L)
        reject(wrongKind, input) // Same magnitude is not the same raw numeric kind.
        val absentDetail = appliedItemWire(input); absentDetail.getJSONObject("state").put("detail", JSONObject.NULL); reject(absentDetail, input)
        val noBinding = appliedItemWire(input); noBinding.getJSONObject("state").getJSONObject("selection").put("kind", "anonymous")
            .put("pattern_id", JSONObject.NULL).put("pattern_revision", JSONObject.NULL).put("binding_revision", JSONObject.NULL)
        reject(noBinding, input)
    }
}
