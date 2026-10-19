package io.github.sussic.pyfa

import org.json.JSONArray
import org.json.JSONObject

/** EOS owns the values. Resolution is a count of intervals, not an invented fit formula. */
data class OfflineLockTimeRequest(val requestId: String, val context: OfflineContext, val fits: Map<String, Long>,
    val low: Double = 25.0, val high: Double = 500.0, val resolution: Int = 200, val budgetMs: Int = 10000) {
    fun json(): String {
        require(requestId.isNotBlank() && requestId.length <= 128)
        require(fits.size in 1..8 && fits.keys.all { it.isNotBlank() } && fits.values.all { it >= 1 })
        require(low.isFinite() && high.isFinite() && low >= 1 && high >= low && high <= 1e9)
        require(resolution in 1..1024 && budgetMs in 1..10000)
        val rows = JSONArray()
        fits.forEach { (id, revision) -> rows.put(JSONObject().put("fit_id", id).put("revision", revision)) }
        return OfflineFeatureCodec.json(JSONObject().put("version", 1).put("request_id", requestId)
            .put("context", context.json()).put("fits", rows)
            .put("x", JSONObject().put("quantity", "signature_radius").put("unit", "m").put("range", JSONArray().put(low).put(high)))
            .put("y", JSONObject().put("quantity", "lock_time").put("unit", "s"))
            .put("resolution", resolution).put("budget_ms", budgetMs))
    }
}
data class OfflineLockTimeSeries(val fitId: String, val revision: Long, val scanResolution: Double?,
    val x: List<Double>, val y: List<Double>)
data class OfflineLockTimeResult(val requestId: String, val ok: Boolean, val request: OfflineLockTimeRequest,
    val series: List<OfflineLockTimeSeries>, val error: OfflineFeatureError?) {
    internal val requiresEngineReopen: Boolean get() = !ok && error?.code in setOf("reopen_required", "engine_unavailable", "engine_error")
}

internal object OfflineLockTimeCodec {
    private val codec get() = OfflineFeatureCodec
    private fun number(raw: Any): Double = (raw as? Number ?: codec.reject("lock-time number required")).toDouble()
        .also { codec.expect(it.isFinite(), "nonfinite lock-time sample") }
    fun result(raw: String, expected: OfflineLockTimeRequest): OfflineLockTimeResult {
        val root = codec.parse(raw)
        codec.expect(codec.integer(root.get("version")) == 1L, "unsupported lock-time version")
        val ok = codec.bool(root.get("ok"))
        val requestId = codec.nullableText(root.get("request_id"))
        codec.expect(requestId == expected.requestId || !ok && requestId == null, "lock-time response identity differs")
        if (!ok) {
            codec.keys(root, "version", "request_id", "ok", "error")
            val error = codec.obj(root.get("error")); codec.keys(error, "code", "message")
            return OfflineLockTimeResult(expected.requestId, false, expected, emptyList(),
                OfflineFeatureError(codec.text(error.get("code")).also { codec.expect(it.isNotBlank(), "empty lock-time error code") },
                    codec.text(error.get("message")).also { codec.expect(it.isNotBlank(), "empty lock-time error message") }))
        }
        codec.keys(root, "version", "request_id", "ok", "context", "x", "y", "total_points", "series", "error")
        codec.expect(root.get("error") === JSONObject.NULL && codec.context(codec.obj(root.get("context"))) == expected.context,
            "lock-time context or outcome differs")
        val x = codec.obj(root.get("x")); codec.keys(x, "quantity", "unit", "range")
        val y = codec.obj(root.get("y")); codec.keys(y, "quantity", "unit")
        codec.expect(codec.text(x.get("quantity")) == "signature_radius" && codec.text(x.get("unit")) == "m" &&
            codec.rows(x.get("range")).map(::number) == listOf(expected.low, expected.high), "lock-time x differs")
        codec.expect(codec.text(y.get("quantity")) == "lock_time" && codec.text(y.get("unit")) == "s", "lock-time y differs")
        val series = codec.rows(root.get("series")).map { entry ->
            val row = codec.obj(entry); codec.keys(row, "fit_id", "revision", "scan_resolution", "x", "y")
            val id = codec.identity(row.get("fit_id")); val revision = codec.integer(row.get("revision"))
            codec.expect(expected.fits[id] == revision, "lock-time fit differs")
            val scanResolution = row.get("scan_resolution").let { if (it === JSONObject.NULL) null else number(it) }
            val xs = codec.rows(row.get("x")).map(::number); val ys = codec.rows(row.get("y")).map(::number)
            val count = if (expected.low == expected.high) 1 else expected.resolution + 1
            codec.expect(xs.size == count && xs.size == ys.size && xs.zipWithNext().all { (a, b) -> a <= b }, "invalid lock-time sample count or ordering")
            // The pinned SmoothPointGetter uses low + ((high-low)/intervals)*i.
            // Its final floating-point value can differ slightly from the requested high.
            // Eight ULPs (with a 1e-12 m floor) cover arithmetic/serialization rounding;
            // preserve the returned coordinates rather than clamping or resampling them.
            val step = (expected.high - expected.low) / expected.resolution
            codec.expect(xs.withIndex().all { (index, actual) ->
                val wanted = expected.low + step * index
                kotlin.math.abs(actual - wanted) <= maxOf(1e-12, 8 * Math.ulp(wanted))
            }, "lock-time samples differ from requested grid")
            codec.expect(ys.all { it >= 0 }, "negative lock time")
            OfflineLockTimeSeries(id, revision, scanResolution, codec.frozen(xs), codec.frozen(ys))
        }
        codec.expect(series.map { it.fitId } == expected.fits.keys.toList(), "incomplete or reordered lock-time comparison")
        codec.expect(codec.integer(root.get("total_points")) == series.sumOf { it.x.size }.toLong(), "incorrect lock-time sample total")
        return OfflineLockTimeResult(expected.requestId, true, expected, codec.frozen(series), null)
    }
}
