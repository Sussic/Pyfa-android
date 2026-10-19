package io.github.sussic.pyfa

import org.json.JSONArray
import org.json.JSONObject

/** Request inputs are copied before queueing. EOS supplies every sample, including duplicate x values. */
data class OfflineCapacitorRequest(val requestId: String, val context: OfflineContext, val fits: Map<String, Long>,
    val xQuantity: String, val xUnit: String, val low: Double, val high: Double, val yQuantity: String, val yUnit: String,
    val startingPercent: Double, val useSimulation: Boolean, val resolution: Int = 256, val budgetMs: Int = 10000) {
    fun json(): String {
        require(fits.size in 1..8 && fits.values.all { it >= 1 })
        require((xQuantity to xUnit) in setOf("time" to "s", "cap_amount" to "GJ", "cap_amount" to "%"))
        require((yQuantity to yUnit) in setOf("cap_amount" to "GJ", "cap_regen" to "GJ/s"))
        require(low.isFinite() && high.isFinite() && low >= 0 && high >= low)
        require(xQuantity != "time" || high <= 3600)
        require(xUnit != "%" || high <= 100)
        require(startingPercent.isFinite() && startingPercent in 0.0..100.0 && resolution in 1..1024 && budgetMs in 1..10000)
        val rows = JSONArray(); fits.forEach { (id, revision) -> rows.put(JSONObject().put("fit_id", id).put("revision", revision)) }
        return OfflineFeatureCodec.json(JSONObject().put("version", 1).put("request_id", requestId).put("context", context.json())
            .put("fits", rows).put("x", JSONObject().put("quantity", xQuantity).put("unit", xUnit).put("range", JSONArray().put(low).put(high)))
            .put("y", JSONObject().put("quantity", yQuantity).put("unit", yUnit)).put("starting_cap_percent", startingPercent)
            .put("use_simulation", useSimulation).put("resolution", resolution).put("budget_ms", budgetMs))
    }
}
data class OfflineCapacitorSeries(val fitId: String, val revision: Long, val capacityGj: Double, val rechargeSeconds: Double,
    val mode: String, val simulationApplied: Boolean, val simulationEndSeconds: Double?, val x: List<Double>, val y: List<Double>)
data class OfflineCapacitorResult(val requestId: String, val ok: Boolean, val request: OfflineCapacitorRequest,
    val series: List<OfflineCapacitorSeries>, val error: OfflineFeatureError?)

internal object OfflineCapacitorCodec {
    private val codec get() = OfflineFeatureCodec
    private fun number(raw: Any): Double = (raw as? Number ?: codec.reject("number required")).toDouble().also { codec.expect(it.isFinite(), "nonfinite sample") }
    fun result(raw: String, expected: OfflineCapacitorRequest): OfflineCapacitorResult {
        val root = codec.parse(raw)
        codec.expect(codec.integer(root.get("version")) == 1L && codec.text(root.get("request_id")) == expected.requestId, "capacitor response identity differs")
        val ok = codec.bool(root.get("ok"))
        if (!ok) {
            codec.keys(root, "version", "request_id", "ok", "error")
            val error = codec.obj(root.get("error")); codec.keys(error, "code", "message")
            return OfflineCapacitorResult(expected.requestId, false, expected, emptyList(), OfflineFeatureError(codec.text(error.get("code")), codec.text(error.get("message"))))
        }
        codec.keys(root, "version", "request_id", "ok", "context", "x", "y", "starting_cap_percent", "use_simulation", "resolution", "total_points", "series")
        codec.expect(codec.context(codec.obj(root.get("context"))) == expected.context, "capacitor context differs")
        val x = codec.obj(root.get("x")); codec.keys(x, "quantity", "unit", "range")
        val y = codec.obj(root.get("y")); codec.keys(y, "quantity", "unit")
        val range = codec.rows(x.get("range")).map(::number)
        codec.expect(range == listOf(expected.low, expected.high) && codec.text(x.get("quantity")) == expected.xQuantity && codec.text(x.get("unit")) == expected.xUnit, "capacitor x differs")
        codec.expect(codec.text(y.get("quantity")) == expected.yQuantity && codec.text(y.get("unit")) == expected.yUnit, "capacitor y differs")
        codec.expect(number(root.get("starting_cap_percent")) == expected.startingPercent && codec.bool(root.get("use_simulation")) == expected.useSimulation && codec.integer(root.get("resolution")) == expected.resolution.toLong(), "capacitor inputs differ")
        val series = codec.rows(root.get("series")).map { entry ->
            val row = codec.obj(entry)
            codec.keys(row, "fit_id", "revision", "capacity_gj", "recharge_time_s", "mode", "simulation_applied", "simulation_end_s", "x", "y")
            val id = codec.identity(row.get("fit_id")); val revision = codec.integer(row.get("revision"))
            codec.expect(expected.fits[id] == revision, "capacitor fit differs")
            val capacity = number(row.get("capacity_gj")); val recharge = number(row.get("recharge_time_s"))
            codec.expect(capacity > 0 && recharge > 0, "invalid capacitor metadata")
            val mode = codec.text(row.get("mode")); codec.expect(mode in setOf("simulation", "range_exhausted", "recharge_only"), "unknown curve mode")
            val applied = codec.bool(row.get("simulation_applied"))
            val end = row.get("simulation_end_s").let { if (it === JSONObject.NULL) null else number(it) }
            codec.expect(applied == (mode != "recharge_only") && (end != null) == applied && (end == null || end in 0.0..3600.0), "inconsistent simulation mode")
            codec.expect(!applied || expected.useSimulation && expected.xQuantity == "time" && expected.yQuantity == "cap_amount", "unexpected simulation")
            val xs = codec.rows(row.get("x")).map(::number); val ys = codec.rows(row.get("y")).map(::number)
            codec.expect(xs.size == ys.size && xs.size <= 16384 && xs.zipWithNext().all { (a,b) -> a <= b }, "invalid sample ordering")
            codec.expect(xs.all { it >= 0 && it >= expected.low - 1e-9 && it <= expected.high + 1e-9 }, "sample outside requested range")
            codec.expect(if (mode == "range_exhausted") xs.isEmpty() else xs.isNotEmpty(), "unexpected empty curve")
            codec.expect(end == null || xs.all { it <= end + 1e-9 }, "extrapolated simulation")
            OfflineCapacitorSeries(id, revision, capacity, recharge, mode, applied, end, codec.frozen(xs), codec.frozen(ys))
        }
        codec.expect(series.map { it.fitId } == expected.fits.keys.toList(), "incomplete or reordered capacitor comparison")
        val total = series.sumOf { it.x.size }
        codec.expect(total <= 16384 && codec.integer(root.get("total_points")) == total.toLong(), "incorrect sample count")
        return OfflineCapacitorResult(expected.requestId, true, expected, codec.frozen(series), null)
    }
}
