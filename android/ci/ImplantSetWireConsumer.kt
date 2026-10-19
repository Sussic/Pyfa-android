package io.github.sussic.pyfa

import java.io.File
import java.security.MessageDigest
import org.json.JSONObject

/** Retained actual Python JSON strings enter the shipping Kotlin codecs and authority/model validators.
 * Usage: ImplantSetWireConsumer <events.jsonl> <frozen-original-catalogue-receipt.json>
 * First line: exactly {schema:"c073-implant-set-wire-v1",catalogue:<original raw JSON string>}.
 * Later lines: exact event fields below, with no catalogue field; all events share the header's raw catalogue.
 * Execution requires the parent's separately admitted, frozen host workload. This file launches nothing itself.
 */
object ImplantSetWireConsumer {
    private const val ORIGINAL_RECEIPT_SHA256 = "b11cd1dfe4b074c9a92e2bef8ccf6fcbfa9f577b9177e77b2d627cf17c834fda"
    @JvmStatic fun main(args: Array<String>) {
        check(args.size == 2) { "Expected retained JSONL and the independently frozen original receipt" }
        val originalBytes = File(args[1]).readBytes()
        val hash = MessageDigest.getInstance("SHA-256").digest(originalBytes).joinToString("") { "%02x".format(it) }
        check(hash == ORIGINAL_RECEIPT_SHA256) { "Original catalogue receipt does not match the reviewed freeze" }
        val original = OfflineFeatureCodec.parse(originalBytes.toString(Charsets.UTF_8))
        check(original.get("ok") == true && original.getString("stage") == "complete")
        val originalRows = OfflineFeatureCodec.rows(original.get("rows")).associate { raw ->
            val row = OfflineFeatureCodec.obj(raw)
            val id = "builtin:implant-set:${OfflineFeatureCodec.integer(row.get("set_id"))}"
            val family = OfflineFeatureCodec.text(row.get("family")); val grade = OfflineFeatureCodec.nullableText(row.get("grade"))
            val items = OfflineFeatureCodec.rows(row.get("resolved")).map { value ->
                val item = OfflineFeatureCodec.obj(value)
                check(item.get("genuine_implant") == true && item.get("active") == true)
                OfflineImplantSetItem(OfflineFeatureCodec.integer(item.get("item_id")).toInt(), OfflineFeatureCodec.text(item.get("name")),
                    OfflineFeatureCodec.integer(item.get("slot")).toInt())
            }
            check(OfflineFeatureCodec.rows(row.get("repeated_slots")).isEmpty())
            check(items.map { it.itemId } == OfflineFeatureCodec.rows(row.get("stored_order")).map { OfflineFeatureCodec.integer(it).toInt() })
            id to OfflineImplantSetDetail(OfflineImplantSetEntry(id, "builtin", if (grade == null) family else "$grade $family", family, grade, 0, items.size.toLong()), items)
        }
        check(originalRows.size == 56 && originalRows.values.sumOf { it.items.size } == 334)
        val labels = mutableSetOf<String>(); val operations = linkedMapOf<String, Int>(); val coverage = mutableSetOf<String>()
        val builtinDetails = mutableSetOf<String>()
        var effective = 0; var noops = 0; var reads = 0; var definite = 0; var uncertain = 0; var checkedRows = 0
        var nativeEarlyRejections = 0; var decodedRequests = 0
        File(args[0]).useLines(Charsets.UTF_8) { lines ->
            val records = lines.iterator()
            check(records.hasNext()) { "Missing retained catalogue header" }
            val header = OfflineFeatureCodec.parse(records.next())
            OfflineFeatureCodec.keys(header, "schema", "catalogue")
            check(OfflineFeatureCodec.text(header.get("schema")) == "c073-implant-set-wire-v1") { "Invalid retained wire schema" }
            val rawCatalogue = OfflineFeatureCodec.text(header.get("catalogue"))
            var retainedCatalogue: CharacterImplantCatalog? = null
            records.forEach { line ->
                check(line.isNotBlank()) { "Blank retained event" }
                val event = OfflineFeatureCodec.parse(line)
                OfflineFeatureCodec.keys(event, "label", "request", "response", "features_before", "features_after", "bridge_before", "before_set_state")
                val label = OfflineFeatureCodec.safeText(event.get("label"), 200); check(labels.add(label)) { "Duplicate event label" }
                fun raw(key: String) = OfflineFeatureCodec.text(event.get(key))
                val beforeFeatures = OfflineFeatureCodec.state(raw("features_before"))
                val beforeBridge = BridgeCodec.decodeResponse(raw("bridge_before"))
                OfflineFeatureCodec.validateLibrary(beforeFeatures, beforeBridge)
                val catalogue = retainedCatalogue ?: CharacterImplantCatalogCodec.decode(rawCatalogue, beforeFeatures.context.datasetSha256).also { retainedCatalogue = it }
                catalogue.validate(beforeFeatures)
                check(catalogue.items.any { it.slot == 79 }) { "Missing genuine slot-79 catalogue witness" }
                val before = if (event.get("before_set_state") === JSONObject.NULL) null else {
                    val previous = OfflineFeatureCodec.obj(event.get("before_set_state")); OfflineFeatureCodec.keys(previous, "request", "response")
                    val priorRequest = OfflineImplantSetsCodec.decodeRequest(OfflineFeatureCodec.text(previous.get("request")))
                    val response = OfflineImplantSetsCodec.response(OfflineFeatureCodec.text(previous.get("response")), priorRequest)
                    check(priorRequest.operation == "read" && response.ok)
                    checkNotNull(response.state).also { OfflineImplantSetsCodec.validateAuthority(it, beforeFeatures, beforeBridge.fits, catalogue) }
                }
                if (label == "wire-only-29-apply_profile") {
                    validateProtectedProfileEarlyRejection(raw("request"), raw("response"), checkNotNull(before), beforeFeatures)
                    check(event.get("features_after") === JSONObject.NULL)
                    nativeEarlyRejections++; definite++
                    operations["apply_profile"] = operations.getOrDefault("apply_profile", 0) + 1
                    return@forEach
                }
                val request = OfflineImplantSetsCodec.decodeRequest(raw("request"))
                decodedRequests++
                check(catalogue.datasetSha256 == request.context.datasetSha256) { "Retained event dataset differs from catalogue header" }
                val response = OfflineImplantSetsCodec.response(raw("response"), request)
                OfflineImplantSetsCodec.validateResult(response, request, before)
                operations[request.operation] = operations.getOrDefault(request.operation, 0) + 1
                if (!response.ok) {
                    check(event.get("features_after") === JSONObject.NULL)
                    if (response.reopenRequired) { uncertain++; check(response.committed == null) }
                    else { definite++; check(response.committed == false) }
                } else {
                    val state = checkNotNull(response.state)
                    val afterFeatures = OfflineFeatureCodec.state(raw("features_after"))
                    if (request.operation == "read") {
                        reads++; check(afterFeatures == beforeFeatures && response.bridge == null)
                        OfflineImplantSetsCodec.validateAuthority(state, beforeFeatures, beforeBridge.fits, catalogue)
                    } else {
                        OfflineImplantSetsCodec.validateTransition(response, request, before, beforeFeatures, beforeBridge.fits, afterFeatures, catalogue)
                        if (response.committed == true) effective++ else noops++
                    }
                    if (state.anchorFitId == null) coverage += "no_fit"
                    if (state.destination is OfflineImplantSetDestination.Fit) coverage += "fit_destination"
                    if (state.destination is OfflineImplantSetDestination.Profile) coverage += "profile_destination"
                    state.saveSource?.let { coverage += "source_${it.source.name}" }
                    if (state.detail == null && request.view.selectedSetId != null) coverage += "missing_detail"
                    if (state.destination == null && request.view.targetProfileId != null) coverage += "missing_profile_destination"
                    if (request.operation in setOf("undo", "redo") && request.anchorFitId != null && state.anchorFitId == null) coverage += "replay_fit_disappearance"
                    state.detail?.let { detail ->
                        if (detail.items.map { it.slot } != detail.items.map { it.slot }.sorted()) coverage += "stored_non_slot_order"
                        if (detail.entry.readonly) {
                            check(detail == originalRows[detail.entry.id]) { "$label: predefined recipe differs from independent original" }
                            builtinDetails += detail.entry.id
                        } else coverage += "custom_recipe"
                        checkedRows += detail.items.size
                    }
                    state.entries.filter { it.readonly }.forEach { check(it == originalRows[it.id]?.entry) { "$label: builtin page metadata differs from original" } }
                    if (request.operation == "apply_fit" && response.committed == false && before?.detail?.items?.isNotEmpty() == true) coverage += "duplicate_fit_noop"
                    if (request.operation == "apply_profile" && response.committed == true) {
                        val previous = checkNotNull(before)
                        val incoming = checkNotNull(previous.detail).items
                        check(incoming.isNotEmpty())
                        val old = previous.destination as? OfflineImplantSetDestination.Profile ?: error("Missing prior character destination")
                        val next = state.destination as? OfflineImplantSetDestination.Profile ?: error("Missing resulting character destination")
                        val slots = incoming.map { it.slot }.toSet()
                        val retained = old.implants.filterNot { it.slot in slots }
                        check(next.implants.size == retained.size + incoming.size && next.implants.take(retained.size) == retained) {
                            "Character application did not preserve unrelated rows exactly and in order" }
                        val oldIds = old.implants.map { it.rowId }.toSet()
                        next.implants.drop(retained.size).zip(incoming).forEach { (actual, item) ->
                            check(actual.itemId == item.itemId && actual.name == item.name && actual.slot == item.slot &&
                                actual.active && actual.rowId !in oldIds) { "Character incoming row was not recreated fresh, active and in recipe order" }
                        }
                        if (incoming.any { item -> old.implants.any { it.slot == item.slot && it.itemId != item.itemId && !it.active } })
                            coverage += "inactive_profile_slot_replacement"
                        if (incoming.all { item -> old.implants.any { it.slot == item.slot && it.itemId == item.itemId && it.active } })
                            coverage += "same_item_profile_recreation"
                    }
                }
            }
        }
        check(labels.size == 102 && decodedRequests == 101 && nativeEarlyRejections == 1) { "Finite event/decoder disposition count differs" }
        check(operations.keys.containsAll(setOf("read", "create", "rename", "duplicate", "delete", "add_item", "remove_item", "save_current", "apply_fit", "apply_profile", "undo", "redo"))) {
            "Retained wire workload missed required operations: $operations" }
        check(effective > 0 && noops > 0 && definite > 0 && uncertain > 0 && reads > 0) { "Retained wire workload missed a result disposition" }
        check(builtinDetails == originalRows.keys) { "Every predefined recipe must pass the actual native codec and independent receipt comparison" }
        check(coverage.containsAll(setOf("no_fit", "fit_destination", "profile_destination", "source_FIT", "source_CHARACTER", "missing_detail",
            "missing_profile_destination", "replay_fit_disappearance", "stored_non_slot_order", "custom_recipe", "duplicate_fit_noop", "inactive_profile_slot_replacement", "same_item_profile_recreation"))) {
            "Retained wire workload missed required cross-summary or replay witnesses: $coverage" }
        println(OfflineFeatureCodec.json(JSONObject().put("ok", true).put("events", labels.size).put("operations", JSONObject(operations))
            .put("effective", effective).put("noops", noops).put("reads", reads).put("definite_failures", definite).put("uncertain_failures", uncertain)
            .put("builtin_details_checked", builtinDetails.size).put("recipe_rows_checked", checkedRows).put("coverage", org.json.JSONArray(coverage.sorted()))
            .put("native_request_early_rejections", nativeEarlyRejections).put("decoded_requests", decodedRequests)
            .put("original_receipt_sha256", hash)))
    }

    /** This one deliberately invalid Python fixture cannot enter the native response codec, which revalidates requests.
     * Assert actual native rejection and inspect its unchanged raw server failure with the same strict JSON primitives.
     * No other event is exempted from the complete native request/response/authority/transition path above.
     */
    private fun validateProtectedProfileEarlyRejection(rawRequest: String, rawResponse: String,
        before: OfflineImplantSetState, features: OfflineFeatureState) = with(OfflineFeatureCodec) {
        val label = "wire-only-29-apply_profile"
        val request = parse(rawRequest)
        keys(request, "version", "request_id", "context", "anchor_fit_id", "view", "operation", "arguments")
        check(integer(request.get("version")) == 1L && text(request.get("request_id")) == label)
        check(text(request.get("operation")) == "apply_profile" && request.get("anchor_fit_id") === JSONObject.NULL)
        check(featureContext(obj(request.get("context"))) == features.context && before.context == features.context)
        check(before.anchorFitId == null && before.saveSource == null)
        val detail = checkNotNull(before.detail)
        check(!detail.entry.readonly)
        val destination = before.destination as? OfflineImplantSetDestination.Profile ?: error("Expected built-in profile preview")
        check(destination.profileId == "builtin:all5" && destination.readonly && destination.profileRevision == 0L && destination.implants.isEmpty())
        val view = obj(request.get("view"))
        keys(view, "query", "offset", "limit", "selected_set_id", "target_profile_id", "history_target")
        check(text(view.get("query")) == "" && integer(view.get("offset")) == 0L && integer(view.get("limit")) == 1L)
        check(text(view.get("selected_set_id")) == detail.entry.id && text(view.get("target_profile_id")) == "builtin:all5" &&
            text(view.get("history_target")) == "library")
        check(before.view == OfflineImplantSetView("", 0, 1, detail.entry.id, "builtin:all5", "library"))
        val arguments = obj(request.get("arguments"))
        keys(arguments, "set_id", "revision", "profile_id", "profile_revision")
        check(text(arguments.get("set_id")) == detail.entry.id && integer(arguments.get("revision")) == detail.entry.revision)
        check(text(arguments.get("profile_id")) == "builtin:all5" && integer(arguments.get("profile_revision")) == 1L)
        var rejected = false
        try {
            OfflineImplantSetsCodec.decodeRequest(rawRequest)
        } catch (failure: BridgeProtocolException) {
            check(failure.message == "Offline features: Implant sets: built-in character is read-only")
            rejected = true
        }
        check(rejected) { "Native request codec accepted protected-profile mutation" }
        val response = parse(rawResponse)
        keys(response, "version", "request_id", "ok", "committed", "reopen_required", "state", "bridge", "error")
        check(integer(response.get("version")) == 1L && text(response.get("request_id")) == label)
        check(!bool(response.get("ok")) && !bool(response.get("committed")) && !bool(response.get("reopen_required")))
        check(response.get("state") === JSONObject.NULL && response.get("bridge") === JSONObject.NULL)
        val failure = obj(response.get("error")); keys(failure, "code", "message")
        check(text(failure.get("code")) == "protected" && safeText(failure.get("message"), 1024) == "Built-in profiles are read-only")
    }
}
