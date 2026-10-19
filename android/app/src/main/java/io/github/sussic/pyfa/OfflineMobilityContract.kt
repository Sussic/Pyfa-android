package io.github.sussic.pyfa

import org.json.JSONArray
import org.json.JSONObject

enum class OfflineMobilityMode(val quantity: String, val unit: String, val label: String) {
    SPEED("speed", "m/s", "Speed"), DISTANCE("distance", "km", "Distance"),
    MOMENTUM("momentum", "Gkg⋅m/s", "Momentum"), BUMP_SPEED("bumpSpeed", "m/s", "Bump speed"),
    BUMP_DISTANCE("bumpDistance", "km", "Bump distance");
    val needsMass get() = this == BUMP_SPEED || this == BUMP_DISTANCE
    val needsInertia get() = this == BUMP_DISTANCE
}

/** EOS owns the values. Resolution is a count of intervals, not an invented fit formula. */
data class OfflineMobilityRequest(val requestId: String, val context: OfflineContext, val fits: Map<String, Long>,
    val low: Double = 0.0, val high: Double = 30.0, val mode: OfflineMobilityMode = OfflineMobilityMode.SPEED,
    val targetMassMkg: Double? = null, val targetInertia: Double? = null,
    val resolution: Int = 200, val budgetMs: Int = 10000) {
    fun json(): String {
        require(requestId.isNotBlank() && requestId.length <= 128)
        require(fits.size in 1..8 && fits.keys.all { it.isNotBlank() } && fits.values.all { it >= 1 })
        require(low.isFinite() && high.isFinite() && low >= 0 && high >= low)
        require(if (mode.needsMass) targetMassMkg != null && targetMassMkg.isFinite() && targetMassMkg >= 0 else targetMassMkg == null)
        require(if (mode.needsInertia) targetInertia != null && targetInertia.isFinite() && targetInertia >= 0 else targetInertia == null)
        require(resolution in 1..1024 && budgetMs in 1..10000)
        val rows = JSONArray()
        fits.forEach { (id, revision) -> rows.put(JSONObject().put("fit_id", id).put("revision", revision)) }
        return OfflineFeatureCodec.json(JSONObject().put("version", 1).put("request_id", requestId)
            .put("context", context.json()).put("fits", rows)
            .put("x", JSONObject().put("quantity", "time").put("unit", "s").put("range", JSONArray().put(low).put(high)))
            .put("y", JSONObject().put("quantity", mode.quantity).put("unit", mode.unit))
            .put("target_mass_mkg", targetMassMkg ?: JSONObject.NULL).put("target_inertia", targetInertia ?: JSONObject.NULL)
            .put("resolution", resolution).put("budget_ms", budgetMs))
    }
}
data class OfflineMobilitySeries(val fitId: String, val revision: Long, val maxVelocityMps: Double?, val alignTimeSeconds: Double?,
    val x: List<Double>, val y: List<Double>)
data class OfflineMobilityResult(val requestId: String, val ok: Boolean, val request: OfflineMobilityRequest,
    val series: List<OfflineMobilitySeries>, val error: OfflineFeatureError?) {
    internal val requiresEngineReopen: Boolean get() = !ok && error?.code in setOf("reopen_required", "engine_unavailable", "engine_error")
}

internal object OfflineMobilityCodec {
    private val codec get() = OfflineFeatureCodec
    private fun number(raw: Any): Double = (raw as? Number ?: codec.reject("mobility number required")).toDouble()
        .also { codec.expect(it.isFinite(), "nonfinite mobility sample") }
    fun result(raw: String, expected: OfflineMobilityRequest): OfflineMobilityResult {
        val root = codec.parse(raw)
        codec.expect(codec.integer(root.get("version")) == 1L, "unsupported mobility version")
        val ok = codec.bool(root.get("ok"))
        val requestId = codec.nullableText(root.get("request_id"))
        codec.expect(requestId == expected.requestId || !ok && requestId == null, "mobility response identity differs")
        if (!ok) {
            codec.keys(root, "version", "request_id", "ok", "error")
            val error = codec.obj(root.get("error")); codec.keys(error, "code", "message")
            return OfflineMobilityResult(expected.requestId, false, expected, emptyList(),
                OfflineFeatureError(codec.text(error.get("code")).also { codec.expect(it.isNotBlank(), "empty mobility error code") },
                    codec.text(error.get("message")).also { codec.expect(it.isNotBlank(), "empty mobility error message") }))
        }
        codec.keys(root, "version", "request_id", "ok", "context", "x", "y", "total_points", "series", "error", "target_mass_mkg", "target_inertia")
        codec.expect(root.get("error") === JSONObject.NULL && codec.context(codec.obj(root.get("context"))) == expected.context,
            "mobility context or outcome differs")
        val x = codec.obj(root.get("x")); codec.keys(x, "quantity", "unit", "range")
        val y = codec.obj(root.get("y")); codec.keys(y, "quantity", "unit")
        codec.expect(codec.text(x.get("quantity")) == "time" && codec.text(x.get("unit")) == "s" &&
            codec.rows(x.get("range")).map(::number) == listOf(expected.low, expected.high), "mobility x differs")
        codec.expect(codec.text(y.get("quantity")) == expected.mode.quantity && codec.text(y.get("unit")) == expected.mode.unit, "mobility y differs")
        fun nullableNumber(raw: Any): Double? = if (raw === JSONObject.NULL) null else number(raw)
        codec.expect(nullableNumber(root.get("target_mass_mkg")) == expected.targetMassMkg &&
            nullableNumber(root.get("target_inertia")) == expected.targetInertia, "mobility target inputs differ")
        val series = codec.rows(root.get("series")).map { entry ->
            val row = codec.obj(entry); codec.keys(row, "fit_id", "revision", "max_velocity_mps", "align_time_s", "x", "y")
            val id = codec.identity(row.get("fit_id")); val revision = codec.integer(row.get("revision"))
            codec.expect(expected.fits[id] == revision, "mobility fit differs")
            val maxVelocity = nullableNumber(row.get("max_velocity_mps"))
            val alignTime = nullableNumber(row.get("align_time_s"))
            codec.expect((maxVelocity == null || maxVelocity >= 0) && (alignTime == null || alignTime >= 0), "invalid mobility metadata")
            val xs = codec.rows(row.get("x")).map(::number); val ys = codec.rows(row.get("y")).map(::number)
            val step = (expected.high - expected.low) / expected.resolution
            val count = if (step == 0.0) 1 else expected.resolution + 1
            codec.expect(xs.size == count && xs.size == ys.size && xs.zipWithNext().all { (a, b) -> a <= b }, "invalid mobility sample count or ordering")
            // The pinned SmoothPointGetter uses low + ((high-low)/intervals)*i.
            // Its final floating-point value can differ slightly from the requested high.
            // Eight ULPs cover double arithmetic/serialization; no absolute floor would
            // be safe for tiny time ranges. Preserve step-underflow singleton behavior.
            codec.expect(xs.withIndex().all { (index, actual) ->
                val wanted = expected.low + step * index
                wanted.isFinite() && actual >= 0 && kotlin.math.abs(actual - wanted) <= 8 * Math.ulp(wanted)
            }, "mobility samples differ from requested grid")
            // Distance uses the original subtraction expression: preserve signed roundoff.
            OfflineMobilitySeries(id, revision, maxVelocity, alignTime, codec.frozen(xs), codec.frozen(ys))
        }
        codec.expect(series.map { it.fitId } == expected.fits.keys.toList(), "incomplete or reordered mobility comparison")
        codec.expect(codec.integer(root.get("total_points")) == series.sumOf { it.x.size }.toLong(), "incorrect mobility sample total")
        return OfflineMobilityResult(expected.requestId, true, expected, codec.frozen(series), null)
    }
}
