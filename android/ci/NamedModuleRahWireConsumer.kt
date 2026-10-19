package io.github.sussic.pyfa

import java.io.File
import org.json.JSONArray
import org.json.JSONObject

/**
 * Inert source until separately admitted compile/execution against the accepted producer bundle.
 * Consume exact retained Python strings from BOTH phases, never synthetic replacement responses.
 * Usage: NamedModuleRahWireConsumer frozen-SCHEDULE.json initial.wires.jsonl reopen.wires.jsonl
 */
object NamedModuleRahWireConsumer {
    private fun request(raw: String): OfflineDamageRequest = with(OfflineFeatureCodec) {
        val row = parse(raw); keys(row,"version","request_id","context","fit_id","view","operation","arguments")
        expect(integer(row.get("version")) == 3L,"Expected damage v3")
        val view = obj(row.get("view"));keys(view,"query","offset","limit","selected_pattern_id","bound_offset","module_offset")
        OfflineDamageRequest(text(row.get("request_id")),context(obj(row.get("context"))),nullableText(row.get("fit_id")),
            OfflineDamageView(text(view.get("query")),integer(view.get("offset")),integer(view.get("limit")).also { expect(it in 1..50,"page cap") }.toInt(),
                nullableText(view.get("selected_pattern_id")),integer(view.get("bound_offset")),integer(view.get("module_offset"))),
            text(row.get("operation")),json(row.get("arguments"))).also { it.json() }
    }
    private fun mustReject(block: () -> Unit) {
        try { block() } catch (_: BridgeProtocolException) { return } catch (_: org.json.JSONException) { return } catch (_: ArithmeticException) { return }
        error("Malformed captured-wire variant was accepted")
    }
    @JvmStatic fun main(args: Array<String>) {
        check(args.size == 3) { "Frozen schedule and both retained actual-wire phases are required" }
        val schedule = OfflineFeatureCodec.parse(File(args[0]).readText(Charsets.UTF_8))
        val phases = schedule.getJSONObject("phases")
        check(phases.keys().asSequence().toSet() == setOf("initial","reopen"))
        var damages=0;var details=0;var excludedBridges=0;var malformed=0
        val coverage=linkedSetOf<String>();val sessions=linkedMapOf<String,String>()
        for ((index,phase) in listOf("initial","reopen").withIndex()) {
            val expected=phases.getJSONObject(phase)
            fun labels(key: String)=OfflineFeatureCodec.rows(expected.get(key)).map(OfflineFeatureCodec::text)
            val expectedDamage=labels("damage_labels");val expectedDetails=labels("details_labels")
            check(expectedDamage.distinct().size==expectedDamage.size && expectedDetails.distinct().size==expectedDetails.size)
            val actualDamage=mutableListOf<String>();val actualDetails=mutableListOf<String>()
            val file=File(args[index+1]);check(file.length() in 1..16_777_216)
            var generation=0L
            fun observe(value: OfflineContext) {
                check(sessions.putIfAbsent(phase,value.sessionId)?.let { it==value.sessionId } != false)
                check(value.generation>=generation);generation=value.generation
            }
            file.useLines(Charsets.UTF_8) { lines -> lines.forEach { line ->
                check(line.isNotBlank());val event=OfflineFeatureCodec.parse(line)
                val label=event.getString("label");val raw=event.getString("response_json")
                when (event.getString("route")) {
                    "bridge" -> excludedBridges++
                    "damage" -> {
                        actualDamage+=label;val input=request(event.getString("request_json"));check(input.requestId==label)
                        val result=OfflineDamageCodec.response(raw,input);damages++
                        check(event.getBoolean("read_like")==damageReadLike(input.operation))
                        val unchanged=event.getString("authority_sha256_before")==event.getString("authority_sha256_after")
                        if (result.committed==false) check(unchanged)
                        if (!result.ok) coverage+="refusal" else {
                            val state=checkNotNull(result.state);observe(state.context)
                            coverage+=if(result.committed==true)"commit" else "noop"
                            if(damageReadLike(input.operation)) { check(result.bridge==null && result.committed==false);coverage+="read_no_publication" }
                            state.module?.let { coverage+="module_${it.mode.wire}";if(it.namedId==SELECTED_AMMO_PATTERN_ID)coverage+="selected_ammo" }
                            state.detail?.let { detail ->
                                if(!detail.entry.assignable)coverage+="unassigned_zero"
                                if(detail.entry.boundFitCount>0 && detail.entry.boundModuleCount>0)coverage+="dual_holders"
                                if(detail.boundOffset>0 || detail.moduleOffset>0)coverage+="independent_holder_offsets"
                            }
                            for (mutate in listOf<(JSONObject)->Unit>(
                                { it.put("version",2) }, { it.getJSONObject("state").put("version",2) },
                                { it.getJSONObject("state").remove("module") })) {
                                val wrong=OfflineFeatureCodec.parse(raw);mutate(wrong)
                                mustReject { OfflineDamageCodec.response(OfflineFeatureCodec.json(wrong),input) };malformed++
                            }
                            if(state.module!=null) {
                                val wrong=OfflineFeatureCodec.parse(raw)
                                wrong.getJSONObject("state").getJSONObject("module").put("object_key","0".repeat(32))
                                mustReject { OfflineDamageCodec.response(OfflineFeatureCodec.json(wrong),input) };malformed++
                            }
                        }
                    }
                    "module_rah_details" -> {
                        actualDetails+=label;val input=OfflineFeatureCodec.parse(event.getString("request_json"))
                        OfflineFeatureCodec.keys(input,"fit_id","offset","limit")
                        val value=ModuleRahCodec.decode(raw);details++;observe(value.context)
                        check(value.fitId==input.getString("fit_id") && value.moduleOffset==OfflineFeatureCodec.integer(input.get("offset")) &&
                            value.moduleLimit.toLong()==OfflineFeatureCodec.integer(input.get("limit")))
                        value.modules.forEach { coverage+="details_${it.mode.wire}" }
                        for(mutate in listOf<(JSONObject)->Unit>({it.put("version",1)}, {it.put("patterns",JSONArray())},
                            {it.getJSONObject("module_page").put("limit",26)})) {
                            val wrong=OfflineFeatureCodec.parse(raw);mutate(wrong)
                            mustReject { ModuleRahCodec.decode(OfflineFeatureCodec.json(wrong)) };malformed++
                        }
                    }
                    else -> error("Unexpected retained route ${event.getString("route")}")
                }
            } }
            check(actualDamage==expectedDamage) { "$phase damage label inventory/order differs" }
            check(actualDetails==expectedDetails) { "$phase details label inventory/order differs" }
            check(actualDamage.isNotEmpty() && actualDetails.isNotEmpty())
        }
        check(sessions.size==2 && sessions.values.distinct().size==2) { "Fresh reopen session was not observed" }
        val required=setOf("module_fit","module_disabled","module_builtin","module_named","selected_ammo","unassigned_zero",
            "dual_holders","independent_holder_offsets","details_fit","details_disabled","details_builtin","details_named","read_no_publication","noop","commit","refusal")
        check(coverage.containsAll(required)) { "Missing actual-wire coverage ${required-coverage}" }
        println(OfflineFeatureCodec.json(JSONObject().put("ok",true).put("damage_rows_consumed",damages).put("details_rows_consumed",details)
            .put("bridge_rows_not_validated",excludedBridges).put("malformed_actual_wire_variants_rejected",malformed).put("coverage",JSONArray(coverage.sorted()))
            .put("qualification","Actual damage-v3 and RAH-details-v2 codec consumption only; not EOS numerical, model, device or integrated proof.")))
    }
}
