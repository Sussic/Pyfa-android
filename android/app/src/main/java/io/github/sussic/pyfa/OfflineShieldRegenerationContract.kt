package io.github.sussic.pyfa

import org.json.JSONArray
import org.json.JSONObject

enum class OfflineShieldRegenerationX(val quantity: String, val inputUnit: String) {
    TIME("time", "s"), AMOUNT("shield_amount", "%"), PERCENT("shield_amount", "%");
    fun unit(effective: Boolean): String = when (this) { TIME -> "s"; AMOUNT -> if (effective) "EHP" else "HP"; PERCENT -> "%" }
}
enum class OfflineShieldRegenerationY(val quantity: String) {
    AMOUNT("shield_amount"), RATE("shield_regen");
    fun unit(effective: Boolean): String = (if (effective) "EHP" else "HP") + if (this == RATE) "/s" else ""
}

/** The main shield input is always percent, independently of the plotted HP/EHP axis. */
data class OfflineShieldRegenerationRequest(
    val requestId: String,
    val context: OfflineContext,
    val fits: Map<String, Long>,
    val x: OfflineShieldRegenerationX = OfflineShieldRegenerationX.TIME,
    val y: OfflineShieldRegenerationY = OfflineShieldRegenerationY.AMOUNT,
    val effective: Boolean = false,
    val low: Double = 0.0,
    val high: Double = if (x == OfflineShieldRegenerationX.TIME) 300.0 else 100.0,
    val startingShieldPercent: Double? = if (x == OfflineShieldRegenerationX.TIME) 0.0 else null,
    val budgetMs: Int = 10000,
) {
    fun json(): String {
        require(requestId.isNotBlank() && requestId.length <= 128)
        require(fits.size in 1..8 && fits.keys.all { it.isNotBlank() && it.length <= 128 && it.none { c -> c.code < 32 } } && fits.values.all { it >= 1 })
        require(low.isFinite() && high.isFinite())
        require(startingShieldPercent == null || startingShieldPercent.isFinite())
        require(x == OfflineShieldRegenerationX.TIME || startingShieldPercent == null)
        require(budgetMs in 1..10000)
        OfflineFeatureCodec.context(context.json())
        val rows = JSONArray()
        fits.forEach { (id, revision) -> rows.put(JSONObject().put("fit_id", id).put("revision", revision)) }
        return OfflineFeatureCodec.json(JSONObject().put("version", 1).put("request_id", requestId)
            .put("context", context.json()).put("fits", rows)
            .put("x", JSONObject().put("quantity", x.quantity).put("unit", x.unit(effective)).put("input_unit", x.inputUnit)
                .put("range", JSONArray().put(low).put(high)))
            .put("y", JSONObject().put("quantity", y.quantity).put("unit", y.unit(effective)))
            .put("effective", effective).put("starting_shield_percent", startingShieldPercent ?: JSONObject.NULL).put("budget_ms", budgetMs))
    }
}

data class OfflineShieldRegenerationSource(val shieldCapacityHp: Double, val shieldRechargeSeconds: Double,
    val damagePattern: Map<String, Double>)
data class OfflineShieldRegenerationSeries(val fitId: String, val revision: Long,
    val source: OfflineShieldRegenerationSource, val x: List<Double>, val y: List<Double>)
data class OfflineShieldRegenerationResult(val requestId: String, val ok: Boolean, val request: OfflineShieldRegenerationRequest,
    val series: List<OfflineShieldRegenerationSeries>, val error: OfflineFeatureError?) {
    internal val requiresEngineReopen: Boolean get() = !ok && error?.code in setOf("reopen_required", "engine_unavailable", "engine_error")
}

internal object OfflineShieldRegenerationCodec {
    private val codec get() = OfflineFeatureCodec
    private val damageKeys = listOf("em", "thermal", "kinetic", "explosive")
    private val errorCodes = setOf("invalid_request", "invalid_engine_data", "stale_context", "stale_fit", "fit_not_found",
        "cancelled", "deadline_exceeded", "resource_exhausted", "clock_error", "engine_error", "reopen_required", "engine_unavailable")
    private fun number(raw: Any): Double = (raw as? Number ?: codec.reject("shield regeneration number required")).toDouble()
        .also { codec.expect(it.isFinite(), "nonfinite shield regeneration value") }
    private fun nullableNumber(raw: Any): Double? = if (raw === JSONObject.NULL) null else number(raw)

    fun result(raw: String, expected: OfflineShieldRegenerationRequest): OfflineShieldRegenerationResult {
        val root = codec.parse(raw)
        codec.expect(codec.integer(root.get("version")) == 1L, "unsupported shield regeneration version")
        val ok = codec.bool(root.get("ok")); val id = codec.nullableText(root.get("request_id"))
        codec.expect(id == expected.requestId || !ok && id == null, "shield regeneration response identity differs")
        if (!ok) {
            codec.keys(root, "version", "request_id", "ok", "error")
            val error = codec.obj(root.get("error")); codec.keys(error, "code", "message")
            val code = codec.text(error.get("code")); val message = codec.text(error.get("message"))
            codec.expect(code in errorCodes && message.isNotBlank(), "invalid shield regeneration error")
            return OfflineShieldRegenerationResult(expected.requestId, false, expected, emptyList(), OfflineFeatureError(code, message))
        }
        codec.keys(root, "version", "request_id", "ok", "context", "x", "y", "effective", "starting_shield_percent", "total_points", "series", "error")
        codec.expect(root.get("error") === JSONObject.NULL && codec.context(codec.obj(root.get("context"))) == expected.context,
            "shield regeneration context or outcome differs")
        val x = codec.obj(root.get("x")); codec.keys(x, "quantity", "unit", "input_unit", "range")
        val y = codec.obj(root.get("y")); codec.keys(y, "quantity", "unit")
        val range = codec.rows(x.get("range")).map(::number)
        codec.expect(codec.text(x.get("quantity")) == expected.x.quantity && codec.text(x.get("unit")) == expected.x.unit(expected.effective) &&
            codec.text(x.get("input_unit")) == expected.x.inputUnit && range.size == 2 && range[0] == expected.low && range[1] == expected.high,
            "shield regeneration x differs")
        codec.expect(codec.text(y.get("quantity")) == expected.y.quantity && codec.text(y.get("unit")) == expected.y.unit(expected.effective),
            "shield regeneration y differs")
        codec.expect(codec.bool(root.get("effective")) == expected.effective &&
            nullableNumber(root.get("starting_shield_percent")) == expected.startingShieldPercent, "shield regeneration assumptions differ")
        val entries = codec.rows(root.get("series"))
        codec.expect(entries.size == expected.fits.size && entries.size in 1..8, "incomplete shield regeneration comparison")
        val series = entries.map { entry ->
            val row = codec.obj(entry); codec.keys(row, "fit_id", "revision", "source", "x", "y")
            val fitId = codec.identity(row.get("fit_id")); val revision = codec.integer(row.get("revision"))
            codec.expect(expected.fits[fitId] == revision, "shield regeneration fit differs")
            val source = codec.obj(row.get("source")); codec.keys(source, "shield_capacity_hp", "shield_recharge_seconds", "damage_pattern")
            val pattern = codec.obj(source.get("damage_pattern")); codec.keys(pattern, *damageKeys.toTypedArray())
            val values = OfflineShieldRegenerationSource(number(source.get("shield_capacity_hp")), number(source.get("shield_recharge_seconds")),
                codec.frozen(damageKeys.associateWith { number(pattern.get(it)) }))
            val xs = codec.rows(row.get("x")).map(::number); val ys = codec.rows(row.get("y")).map(::number)
            codec.expect(xs.size == ys.size && xs.isNotEmpty() && xs.size <= 201, "invalid shield regeneration sample arrays")
            codec.expect(xs.zipWithNext().all { (a, b) -> a <= b } || xs.zipWithNext().all { (a, b) -> a >= b },
                "unordered shield regeneration coordinates")
            codec.expect(coordinates(xs, ys, expected, values.shieldCapacityHp), "shield regeneration sample sequence differs")
            OfflineShieldRegenerationSeries(fitId, revision, values, codec.frozen(xs), codec.frozen(ys))
        }
        codec.expect(series.map { it.fitId } == expected.fits.keys.toList(), "reordered or duplicate shield regeneration fits")
        codec.expect(codec.integer(root.get("total_points")) == series.sumOf { it.x.size }.toLong(), "incorrect shield regeneration sample total")
        return OfflineShieldRegenerationResult(expected.requestId, true, expected, codec.frozen(series), null)
    }

    /** Validate only source normalization/limiting/sampling, never shield or effective-HP formulas. */
    private fun coordinates(xs: List<Double>, ys: List<Double>, request: OfflineShieldRegenerationRequest, capacity: Double): Boolean {
        fun matches(actual: Double, wanted: Double): Boolean = wanted.isFinite() &&
            (actual == wanted || kotlin.math.abs(actual - wanted) <= 8.0 * Math.ulp(wanted))
        if (capacity == 0.0 && request.x == OfflineShieldRegenerationX.PERCENT && request.y == OfflineShieldRegenerationY.AMOUNT) {
            return xs.size == 2 && matches(xs[0], minOf(request.low, request.high)) && matches(xs[1], maxOf(request.low, request.high)) && ys.all { it == 0.0 }
        }
        fun normalize(value: Double): Double = if (request.x == OfflineShieldRegenerationX.TIME) value
            else (value / 100.0 * capacity).coerceIn(minOf(0.0, capacity), maxOf(0.0, capacity))
        val a = normalize(request.low); val b = normalize(request.high)
        val low = minOf(a, b); val high = maxOf(a, b); val step = (high - low) / 200.0
        val count = if (step == 0.0 || step.isNaN()) 1 else 201
        if (xs.size != count) return false
        // Effective X is structurally validated only. The independent original/candidate
        // comparator establishes EHP arithmetic, including endpoint and interior corruption.
        if (request.x == OfflineShieldRegenerationX.AMOUNT && request.effective) return true
        return xs.indices.all { i ->
            val raw = if (count == 1) low else low + step * i
            val wanted = if (request.x == OfflineShieldRegenerationX.PERCENT) raw * 100.0 / capacity else raw
            matches(xs[i], wanted)
        }
    }
}
