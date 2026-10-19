package io.github.sussic.pyfa

import java.io.File
import org.json.JSONArray
import org.json.JSONObject

/** Separate actual-codec consumer for the terminal retained C07.2 candidate wire directory. */
object CharacterImplantWireConsumer {
    @JvmStatic fun main(args: Array<String>) {
        check(args.size == 1)
        val directory = File(args.single()).canonicalFile
        val wire = File(directory, "wire").canonicalFile
        fun root(name: String): String = File(directory, name).readText(Charsets.UTF_8)
        fun file(name: String): String {
            check(name.matches(Regex("[A-Za-z0-9_.-]+"))) { "Wire filename is not a bounded local basename" }
            val value = File(wire, name).canonicalFile
            check(value.parentFile == wire)
            return value.readText(Charsets.UTF_8)
        }
        val result = OfflineFeatureCodec.parse(root("result.json"))
        check(result.getBoolean("ok")) { "Candidate exporter is not terminal success" }
        val initial = OfflineFeatureCodec.state(root("initial-feature-state.json"))
        val initialBridge = BridgeCodec.decodeResponse(root("initial-bridge.json"))
        check(initial.bindings.isEmpty() && initialBridge.fits.isEmpty()) { "Missing zero-fit opening witness" }
        OfflineFeatureCodec.validateLibrary(initial, initialBridge)
        val metadata = CharacterImplantCatalogCodec.decode(root("catalogue.json"), initial.context.datasetSha256)
        check(metadata.error == null && metadata.items.any { it.slot == 79 })
        metadata.validate(initial)
        val events = OfflineFeatureCodec.rows(StrictJson(root("wire-index.json")).parse())
        check(result.getInt("wire_events") == events.size)
        val counts = linkedMapOf<String, Int>()
        var effective = 0; var noops = 0; var definite = 0; var uncertain = 0; var imports = 0; var previewCount = 0
        var membershipChecks = 1; var profileRowsChecked = 0; var localRowsChecked = 0
        val labels = mutableSetOf<String>()
        for (raw in events) {
            val event = OfflineFeatureCodec.obj(raw)
            val kind = OfflineFeatureCodec.text(event.get("kind"))
            val label = OfflineFeatureCodec.text(event.get("label")); check(labels.add(label))
            counts[kind] = counts.getOrDefault(kind, 0) + 1
            if (kind == "feature") OfflineFeatureCodec.keys(event, "label", "kind", "request", "response", "before_state", "before_bridge")
            else OfflineFeatureCodec.keys(event, "label", "kind", "request", "response")
            val request = if (event.get("request") === JSONObject.NULL) null else OfflineFeatureCodec.parse(file(event.getString("request")))
            val response = file(event.getString("response"))
            fun checkState(state: OfflineFeatureState, bridge: BridgeResponse) {
                OfflineFeatureCodec.validateLibrary(state, bridge)
                check(state.context.sessionId == initial.context.sessionId && state.context.datasetSha256 == initial.context.datasetSha256)
                metadata.validate(state)
                membershipChecks++; profileRowsChecked += state.profiles.sumOf { it.implants.size }; localRowsChecked += bridge.fits.sumOf { it.implants.size }
            }
            when (kind) {
                "catalogue" -> check(CharacterImplantCatalogCodec.decode(response, initial.context.datasetSha256) == metadata)
                "feature" -> {
                    val input = checkNotNull(request)
                    OfflineFeatureCodec.keys(input, "version", "request_id", "context", "operation", "arguments", "anchor_fit_id")
                    check(OfflineFeatureCodec.integer(input.get("version")) == 2L)
                    val before = OfflineFeatureCodec.state(file(event.getString("before_state")))
                    val beforeBridge = BridgeCodec.decodeResponse(file(event.getString("before_bridge")))
                    checkState(before, beforeBridge)
                    val expected = OfflineFeatureCodec.featureContext(OfflineFeatureCodec.obj(input.get("context")))
                    check(expected == before.context)
                    val anchor = OfflineFeatureCodec.nullableText(input.get("anchor_fit_id"))
                    val parsed = OfflineFeatureCodec.response(response, input.getString("request_id"), expected, before, anchor)
                    if (parsed.ok) {
                        checkState(checkNotNull(parsed.state), checkNotNull(parsed.bridge))
                        // Successful calls must also be valid outgoing native-v2 requests.
                        OfflineFeatureCodec.request(input.getString("request_id"), expected, input.getString("operation"), input.getJSONObject("arguments"), anchor)
                        if (parsed.committed == true) effective++ else { noops++; check(checkNotNull(parsed.bridge).fits == beforeBridge.fits) }
                    } else if (parsed.reopenRequired) { uncertain++; check(parsed.committed == null) }
                    else { definite++; check(parsed.committed == false) }
                }
                "feature-error" -> {
                    // Deliberately obsolete outgoing v1. The current native client rejects this reply correlation.
                    val input = checkNotNull(request); check(input.getInt("version") == 1)
                    val parsed = OfflineFeatureCodec.parse(response)
                    OfflineFeatureCodec.keys(parsed, "version", "request_id", "ok", "committed", "reopen_required", "state", "bridge", "error")
                    check(parsed.getInt("version") == 2 && parsed.get("ok") == false && parsed.get("committed") == false && parsed.get("reopen_required") == false)
                    check(parsed.isNull("request_id") && parsed.isNull("state") && parsed.isNull("bridge"))
                    val error = OfflineFeatureCodec.obj(parsed.get("error"))
                    OfflineFeatureCodec.keys(error, "code", "message")
                    OfflineFeatureCodec.safeText(error.get("code"), 128)
                    OfflineFeatureCodec.safeText(error.get("message"), 1024)
                    var rejected = false
                    try { OfflineFeatureCodec.response(response, input.getString("request_id"), OfflineFeatureCodec.featureContext(input.getJSONObject("context"))) }
                    catch (_: BridgeProtocolException) { rejected = true }
                    check(rejected) { "Unsupported-v1 request reply unexpectedly accepted as a correlated native request" }
                }
                "bridge" -> {
                    val decoded = BridgeCodec.decodeResponse(response)
                    check(decoded.isSuccess && decoded.sessionId == initial.context.sessionId && decoded.requestId == checkNotNull(request).getString("request_id"))
                    localRowsChecked += decoded.fits.sumOf { it.implants.size }
                }
                "import-preview" -> {
                    val input = checkNotNull(request)
                    check(OfflineImportCodec.preview(response, input.getString("request_id"), input).ok); previewCount++
                }
                "import" -> {
                    val input = checkNotNull(request)
                    OfflineImportCodec.request(OfflineFeatureCodec.json(input))
                    val decoded = OfflineImportCodec.result(response, input.getString("request_id"), initial.context.sessionId, input)
                    check(decoded.ok && !decoded.reopenRequired)
                    checkState(checkNotNull(decoded.state), checkNotNull(decoded.bridge)); imports++
                }
                "g07", "g07-stale" -> Unit // Owned by the independent graph comparison, not claimed as decoded here.
                else -> error("Unexpected wire kind $kind")
            }
        }
        check(effective > 0 && noops > 0 && definite > 0 && uncertain == 1 && imports == 1 && previewCount == 1)
        println(JSONObject().put("ok", true).put("events", events.size).put("kind_counts", JSONObject(counts as Map<*, *>))
            .put("effective_feature_successes", effective).put("exact_noops", noops).put("definite_errors", definite).put("uncertain_errors", uncertain)
            .put("import_v1_feature_v2_successes", imports).put("validated_library_memberships", membershipChecks)
            .put("profile_implant_rows_checked", profileRowsChecked).put("local_rows_observed", localRowsChecked)
            .put("catalogue_items", metadata.items.size).put("qualification", "Actual native codecs on retained candidate wire; host JVM only. G07 events are counted but decoded by the independent graph lane, not here."))
    }
}
