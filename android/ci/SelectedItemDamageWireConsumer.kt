package io.github.sussic.pyfa

import java.io.File
import org.json.JSONArray
import org.json.JSONObject

/** Actual captured mobile_runtime wires enter shipping codecs. No EOS or Android workload is launched here.
 * Usage: SelectedItemDamageWireConsumer <frozen-SCHEDULE.json> <initial.wires.jsonl> <reopen.wires.jsonl>
 * Every damage row is consumed; other routes are counted explicitly as outside this consumer's qualification.
 * This source requires separately admitted compilation/execution against a frozen producer bundle.
 */
object SelectedItemDamageWireConsumer {
    private val damageKeys = arrayOf("label", "route", "request_json", "response_json", "before_state_json",
        "feature_before_json", "feature_after_json", "authority_sha256_before", "authority_sha256_after", "read_like")
    private fun request(raw: String): Pair<OfflineDamageRequest, Boolean> {
        val row = OfflineFeatureCodec.parse(raw)
        val view = row.getJSONObject("view")
        val input = OfflineDamageRequest(OfflineFeatureCodec.text(row.get("request_id")),
            OfflineFeatureCodec.context(row.getJSONObject("context")), OfflineFeatureCodec.nullableText(row.get("fit_id")),
            OfflineDamageView(OfflineFeatureCodec.text(view.get("query")), OfflineFeatureCodec.integer(view.get("offset")),
                OfflineFeatureCodec.integer(view.get("limit")).let { check(it in 1..50); it.toInt() },
                OfflineFeatureCodec.nullableText(view.get("selected_pattern_id")), OfflineFeatureCodec.integer(view.get("bound_offset"))),
            OfflineFeatureCodec.text(row.get("operation")), OfflineFeatureCodec.json(row.get("arguments")))
        val accepted = try {
            OfflineFeatureCodec.keys(row, "version", "request_id", "context", "fit_id", "view", "operation", "arguments")
            OfflineFeatureCodec.keys(view, "query", "offset", "limit", "selected_pattern_id", "bound_offset")
            OfflineFeatureCodec.expect(OfflineFeatureCodec.integer(row.get("version")) == 2L, "Expected damage v2")
            input.json(); true
        } catch (_: BridgeProtocolException) { false } catch (_: org.json.JSONException) { false } catch (_: ArithmeticException) { false }
        return input to accepted
    }
    private fun rejected(raw: String, input: OfflineDamageRequest, mutation: (JSONObject) -> Unit) {
        val row = OfflineFeatureCodec.parse(raw); mutation(row)
        try {
            OfflineDamageCodec.response(OfflineFeatureCodec.json(row), input)
        } catch (_: BridgeProtocolException) { return }
        catch (_: org.json.JSONException) { return }
        catch (_: ArithmeticException) { return }
        error("Malformed actual-wire variant accepted for ${input.requestId}")
    }
    @JvmStatic fun main(args: Array<String>) {
        check(args.size == 3) { "Expected frozen schedule and both actual retained phase wire files" }
        val schedule = OfflineFeatureCodec.parse(File(args[0]).readText(Charsets.UTF_8))
        val phases = schedule.getJSONObject("phases")
        check(phases.keys().asSequence().toSet() == setOf("initial", "reopen"))
        val expectedLabels = listOf("initial", "reopen").flatMap { phase ->
            OfflineFeatureCodec.rows(phases.getJSONObject(phase).get("damage_labels")).map(OfflineFeatureCodec::text)
        }
        check(expectedLabels.size == expectedLabels.distinct().size && expectedLabels.isNotEmpty())
        val labels = linkedSetOf<String>(); val coverage = linkedSetOf<String>()
        val operations = linkedMapOf<String, Int>()
        var consumed = 0; var outsideDamage = 0; var localRejections = 0; var malformedVariants = 0
        args.drop(1).forEach { path ->
            val file = File(path); check(file.length() in 1..16_777_216) { "Retained wire file exceeds unchanged evidence cap" }
            file.useLines(Charsets.UTF_8) { lines -> lines.forEach damageLine@ { line ->
                check(line.isNotBlank()) { "Blank retained event" }
                val event = OfflineFeatureCodec.parse(line)
                if (event.getString("route") != "damage") {
                    check(event.getString("route") in setOf("bridge", "implant_sets", "g04"))
                    outsideDamage++; return@damageLine
                }
                OfflineFeatureCodec.keys(event, *damageKeys)
                val label = OfflineFeatureCodec.text(event.get("label")); check(labels.add(label)) { "Duplicate damage label $label" }
                val requestRaw = OfflineFeatureCodec.text(event.get("request_json"))
                val responseRaw = OfflineFeatureCodec.text(event.get("response_json"))
                val (input, acceptedLocally) = request(requestRaw)
                check(input.requestId == label)
                check(OfflineFeatureCodec.bool(event.get("read_like")) == damageReadLike(input.operation))
                val response = OfflineDamageCodec.response(responseRaw, input)
                if (!acceptedLocally) { check(!response.ok && !response.reopenRequired); localRejections++ }
                consumed++; operations[input.operation] = operations.getOrDefault(input.operation, 0) + 1
                fun optional(key: String) = OfflineFeatureCodec.nullableText(event.get(key))
                val beforeFeature = optional("feature_before_json")?.let(OfflineFeatureCodec::state)
                val afterFeature = optional("feature_after_json")?.let(OfflineFeatureCodec::state)
                val beforeRaw = optional("before_state_json")
                val before = beforeRaw?.let { raw ->
                    val prior = OfflineFeatureCodec.parse(raw)
                    val priorContext = OfflineFeatureCodec.context(prior.getJSONObject("state").getJSONObject("context"))
                    val priorRequest = input.copy(requestId = prior.getString("request_id"), context = priorContext,
                        operation = "read", argumentsJson = "{}")
                    OfflineDamageCodec.response(raw, priorRequest).also { check(it.ok) }.state
                }
                fun hash(key: String) = OfflineFeatureCodec.text(event.get(key)).also { check(it.matches(Regex("[0-9a-f]{64}"))) }
                val unchanged = hash("authority_sha256_before") == hash("authority_sha256_after")
                if (response.reopenRequired) {
                    check(!response.ok && response.committed == null && afterFeature == null); coverage += "uncertain"
                    if (damageReadLike(input.operation)) { check(unchanged); coverage += "disabled_read" }
                } else {
                    check(beforeFeature != null && afterFeature != null && before != null)
                    if (response.committed == false) {
                        check(unchanged && beforeFeature == afterFeature) { "$label changed authority/features without commit" }
                    } else check(!unchanged)
                }
                if (!response.ok) {
                    coverage += "error"
                    if (label.startsWith("protected_")) check(!acceptedLocally) { "Protected action accepted natively" }
                    if (input.operation == "item_options" && !response.reopenRequired) coverage += "read_error"
                } else {
                    check(acceptedLocally)
                    val state = checkNotNull(response.state)
                    val after = checkNotNull(afterFeature)
                    check(state.context == after.context)
                    if (damageReadLike(input.operation)) {
                        check(response.committed == false && response.bridge == null && beforeFeature == afterFeature)
                        coverage += input.operation
                    } else {
                        OfflineFeatureCodec.validateLibrary(after, checkNotNull(response.bridge))
                        coverage += if (response.committed == true) "commit" else "noop"
                    }
                    state.item?.let { item ->
                        coverage += if (item.available) "available_item" else checkNotNull(item.unavailableReason)
                        if (item.values?.fields?.values?.any { it is Long } == true) coverage += "raw_integer"
                        if (item.values?.fields?.values?.any { it is Double } == true) coverage += "raw_float"
                        val changes: List<(JSONObject) -> Unit> = listOf(
                            { it.getJSONObject("state").getJSONObject("item").put("item_id", if (item.itemId == 1) 2 else 1) },
                            { it.getJSONObject("state").getJSONObject("item").put("extra", false) },
                            { it.getJSONObject("state").put("item", JSONObject.NULL) },
                            { it.getJSONObject("state").getJSONObject("item").put("name", "bad\nname") },
                            { it.put("version", 1) },
                        )
                        changes.forEach { rejected(responseRaw, input, it); malformedVariants++ }
                    }
                    if (state.detail?.entry?.id == SELECTED_AMMO_PATTERN_ID) {
                        coverage += "selected_ammo"
                        for ((key, wrong) in listOf("kind" to "custom", "kind" to "builtin", "name" to "Wrong", "revision" to 0)) {
                            rejected(responseRaw, input) { it.getJSONObject("state").getJSONObject("detail").put(key, wrong) }
                            malformedVariants++
                        }
                    }
                    if (input.operation == "apply_item") {
                        coverage += "apply_item"
                        check(state.detail?.values == state.item?.values && state.selection.patternId == SELECTED_AMMO_PATTERN_ID)
                        if (response.committed == true) {
                            val submitted = OfflineFeatureCodec.parse(input.argumentsJson).getLong("fit_revision")
                            rejected(responseRaw, input) { root ->
                                val changed = root.getJSONObject("state"); changed.put("fit_revision", submitted)
                                OfflineFeatureCodec.rows(changed.getJSONObject("detail").getJSONObject("bound_fits").get("entries")).forEach { value ->
                                    val fit = OfflineFeatureCodec.obj(value); if (fit.getString("fit_id") == input.fitId) fit.put("revision", submitted)
                                }
                                OfflineFeatureCodec.rows(root.getJSONObject("bridge").get("fits")).forEach { value ->
                                    val fit = OfflineFeatureCodec.obj(value); if (fit.getString("id") == input.fitId) fit.put("revision", submitted)
                                }
                            }; malformedVariants++
                        }
                    }
                }
            } }
        }
        val required = setOf("read", "item_options", "apply_item", "selected_ammo", "available_item", "no_damage_attributes",
            "invalid_values", "zero_total", "raw_integer", "raw_float", "commit", "noop", "error", "read_error", "uncertain", "disabled_read")
        check(labels.toList() == expectedLabels) { "Captured damage labels/order differ from frozen schedule" }
        check(coverage.containsAll(required)) { "Missing captured damage-wire coverage: ${required - coverage}" }
        check(listOf("rename", "duplicate", "update_values", "delete").all { "protected_$it" in labels })
        check(localRejections >= 4 && malformedVariants > 0 && consumed == labels.size)
        println(OfflineFeatureCodec.json(JSONObject().put("ok", true).put("damage_rows_consumed", consumed)
            .put("non_damage_rows_not_validated", outsideDamage).put("native_early_rejections", localRejections)
            .put("malformed_actual_wire_variants_rejected", malformedVariants).put("operations", JSONObject(operations))
            .put("coverage", JSONArray(coverage.sorted())).put("qualification", "Actual damage route codec consumption only; not EOS comparison, model scheduling, Android/device or integrated acceptance.")))
    }
}
