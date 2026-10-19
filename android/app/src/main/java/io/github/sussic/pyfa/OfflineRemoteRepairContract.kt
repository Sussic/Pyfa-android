package io.github.sussic.pyfa

import org.json.JSONArray
import org.json.JSONObject

enum class OfflineRemoteRepairAxis(val quantity: String, val unit: String) {
    DISTANCE("distance", "km"), TIME("time", "s"),
}

/** Original-source repair ordinates. */
enum class OfflineRemoteRepairOrdinate(val quantity: String, val unit: String) {
    RATE("repair_rate", "HP/s"),
    AMOUNT("repair_amount", "HP"),
}

/** Only distance rate + blank time retains the exact v1 wire. */
data class OfflineRemoteRepairRequest(
    val requestId: String,
    val context: OfflineContext,
    val fits: Map<String, Long>,
    val low: Double = 0.0,
    val high: Double = 100.0,
    val ancillaryReload: Boolean = true,
    val ignoreLockRange: Boolean = true,
    val ignoreDroneControlRange: Boolean = false,
    val budgetMs: Int = 10000,
    val time: Double? = null,
    val ordinate: OfflineRemoteRepairOrdinate = OfflineRemoteRepairOrdinate.RATE,
    val axis: OfflineRemoteRepairAxis = OfflineRemoteRepairAxis.DISTANCE,
    val distance: Double? = null,
) {
    val effectiveLow: Double get() = if (axis == OfflineRemoteRepairAxis.TIME) low.coerceIn(0.0, 2500.0) else low
    val effectiveHigh: Double get() = if (axis == OfflineRemoteRepairAxis.TIME) high.coerceIn(0.0, 2500.0) else high
    val version: Int get() = if (axis == OfflineRemoteRepairAxis.DISTANCE && ordinate == OfflineRemoteRepairOrdinate.RATE && time == null) 1 else 2

    fun json(): String {
        require(requestId.isNotBlank() && requestId.length <= 128)
        require(fits.size in 1..8 && fits.keys.all { it.isNotBlank() } && fits.values.all { it >= 1 })
        require(low.isFinite() && high.isFinite() && high >= low)
        if (axis == OfflineRemoteRepairAxis.DISTANCE) {
            require(low >= 0.0 && (low * 1000.0).isFinite() && (high * 1000.0).isFinite())
            require(distance == null)
            require(ordinate != OfflineRemoteRepairOrdinate.AMOUNT || time != null)
        } else {
            require(time == null)
            require(distance == null || distance.isFinite() && distance >= 0.0 && (distance * 1000.0).isFinite())
        }
        require(budgetMs in 1..10000)
        require(time == null || time.isFinite())
        val rows = JSONArray()
        fits.forEach { (id, revision) -> rows.put(JSONObject().put("fit_id", id).put("revision", revision)) }
        return OfflineFeatureCodec.json(JSONObject().put("version", version).put("request_id", requestId)
            .put("context", context.json()).put("fits", rows)
            .put("x", JSONObject().put("quantity", axis.quantity).put("unit", axis.unit).put("range", JSONArray().put(low).put(high)))
            .put("y", JSONObject().put("quantity", ordinate.quantity).put("unit", ordinate.unit))
            .put("time", time ?: JSONObject.NULL).also { if (version == 2) it.put("distance", distance ?: JSONObject.NULL) }
            .put("ancillary_reload", ancillaryReload)
            .put("ignore_lock_range", ignoreLockRange).put("ignore_drone_control_range", ignoreDroneControlRange)
            .put("budget_ms", budgetMs))
    }
}

/** Current source-column rates, before range application and without graph ancillary overrides. */
data class OfflineRemoteRepairSourceRates(val shield: Double, val armor: Double, val hull: Double)
data class OfflineRemoteRepairSeries(val fitId: String, val revision: Long,
    val sourceRates: OfflineRemoteRepairSourceRates, val x: List<Double>, val y: List<Double>)
data class OfflineRemoteRepairResult(val requestId: String, val ok: Boolean, val request: OfflineRemoteRepairRequest,
    val series: List<OfflineRemoteRepairSeries>, val error: OfflineFeatureError?, val effectiveTime: Double? = null) {
    internal val requiresEngineReopen: Boolean get() = !ok && error?.code in setOf("reopen_required", "engine_unavailable", "engine_error")
}

internal object OfflineRemoteRepairCodec {
    const val MAX_TIME_POINTS = 87210
    const val MAX_WIRE_CHARS = 5614208
    private val codec get() = OfflineFeatureCodec
    private val errorCodes = setOf("invalid_request", "invalid_engine_data", "stale_context", "stale_fit", "fit_not_found",
        "cancelled", "deadline_exceeded", "resource_exhausted", "clock_error", "engine_error", "reopen_required", "engine_unavailable")
    private fun number(raw: Any): Double = (raw as? Number ?: codec.reject("remote repair number required")).toDouble()
        .also { codec.expect(it.isFinite(), "nonfinite remote repair value") }

    private fun pair(raw: Any): List<Double> {
        val array = raw as? JSONArray ?: codec.reject("remote repair range required")
        codec.expect(array.length() == 2, "remote repair range must have two endpoints")
        return listOf(number(array.get(0)), number(array.get(1)))
    }

    fun result(raw: String, expected: OfflineRemoteRepairRequest): OfflineRemoteRepairResult {
        // EngineRuntime supplies the real raw bridge string here, before any JSONObject parse.
        // The bridge has already materialized this String; this bounds parsing and downstream copies.
        codec.expect(raw.length <= MAX_WIRE_CHARS, "remote repair wire exceeds absolute bound")
        val root = if (expected.axis == OfflineRemoteRepairAxis.TIME) codec.obj(RemoteRepairJson(raw).parse()) else codec.parse(raw)
        codec.expect(codec.integer(root.get("version")) == expected.version.toLong(), "unsupported remote repair version")
        val ok = codec.bool(root.get("ok"))
        val requestId = codec.nullableText(root.get("request_id"))
        codec.expect(requestId == expected.requestId || !ok && requestId == null, "remote repair response identity differs")
        if (!ok) {
            codec.keys(root, "version", "request_id", "ok", "error")
            val error = codec.obj(root.get("error")); codec.keys(error, "code", "message")
            val code = codec.text(error.get("code"))
            codec.expect(code in errorCodes, "unknown remote repair error code")
            val message = codec.text(error.get("message"))
            codec.expect(message.isNotBlank(), "empty remote repair error message")
            return OfflineRemoteRepairResult(expected.requestId, false, expected, emptyList(), OfflineFeatureError(code, message))
        }
        val successKeys = arrayOf("version", "request_id", "ok", "context", "x", "y", "time", "ancillary_reload",
            "ignore_lock_range", "ignore_drone_control_range", "total_points", "series", "error")
        codec.keys(root, *(if (expected.version == 2) successKeys + arrayOf("distance", "effective") else successKeys))
        codec.expect(root.get("error") === JSONObject.NULL && codec.context(codec.obj(root.get("context"))) == expected.context,
            "remote repair context or outcome differs")
        val x = codec.obj(root.get("x")); codec.keys(x, "quantity", "unit", "range")
        val y = codec.obj(root.get("y")); codec.keys(y, "quantity", "unit")
        val range = pair(x.get("range"))
        // Typed comparisons preserve Python's finite-double equality, including signed zero.
        codec.expect(codec.text(x.get("quantity")) == expected.axis.quantity && codec.text(x.get("unit")) == expected.axis.unit &&
            range.size == 2 && range[0] == expected.low && range[1] == expected.high, "remote repair x differs")
        codec.expect(codec.text(y.get("quantity")) == expected.ordinate.quantity && codec.text(y.get("unit")) == expected.ordinate.unit, "remote repair y differs")
        var effectiveTime: Double? = null
        if (expected.version == 1) codec.expect(root.get("time") === JSONObject.NULL, "remote repair time differs")
        else {
            fun nullableNumber(raw: Any, wanted: Double?) =
                if (wanted == null) raw === JSONObject.NULL else raw !== JSONObject.NULL && number(raw) == wanted
            codec.expect(nullableNumber(root.get("time"), expected.time) && nullableNumber(root.get("distance"), expected.distance),
                "remote repair requested time or distance differs")
            val effective = codec.obj(root.get("effective")); codec.keys(effective, "x_range", "time", "distance")
            val effectiveRange = pair(effective.get("x_range"))
            effectiveTime = expected.time?.coerceIn(0.0, 2500.0)
            codec.expect(effectiveRange.size == 2 && effectiveRange[0] == expected.effectiveLow && effectiveRange[1] == expected.effectiveHigh &&
                nullableNumber(effective.get("time"), effectiveTime) && nullableNumber(effective.get("distance"), expected.distance?.times(1000.0)),
                "remote repair effective values differ")
        }
        codec.expect(codec.bool(root.get("ancillary_reload")) == expected.ancillaryReload &&
            codec.bool(root.get("ignore_lock_range")) == expected.ignoreLockRange &&
            codec.bool(root.get("ignore_drone_control_range")) == expected.ignoreDroneControlRange, "remote repair assumptions differ")
        val total = codec.integer(root.get("total_points"))
        val ceiling = if (expected.axis == OfflineRemoteRepairAxis.TIME) MAX_TIME_POINTS else 1608
        codec.expect(total in 1..ceiling.toLong(), "remote repair total exceeds bound")
        if (expected.axis == OfflineRemoteRepairAxis.TIME)
            codec.expect(raw.length <= 32768L + 64L * total, "remote repair wire exceeds point allowance")
        val rawEntries = root.get("series") as? JSONArray ?: codec.reject("remote repair series required")
        codec.expect(rawEntries.length() == expected.fits.size && rawEntries.length() in 1..8, "incomplete remote repair comparison")
        val entries = codec.rows(rawEntries)
        var counted = 0L
        codec.expect(entries.size == expected.fits.size && entries.size in 1..8, "incomplete remote repair comparison")
        val series = entries.map { entry ->
            val row = codec.obj(entry); codec.keys(row, "fit_id", "revision", "source_rates", "x", "y")
            val id = codec.identity(row.get("fit_id")); val revision = codec.integer(row.get("revision"))
            codec.expect(expected.fits[id] == revision, "remote repair fit differs")
            val rates = codec.obj(row.get("source_rates")); codec.keys(rates, "shield", "armor", "hull")
            val source = OfflineRemoteRepairSourceRates(number(rates.get("shield")), number(rates.get("armor")), number(rates.get("hull")))
            val rawX = row.get("x") as? JSONArray ?: codec.reject("remote repair x array required")
            val rawY = row.get("y") as? JSONArray ?: codec.reject("remote repair y array required")
            val limit = if (expected.axis == OfflineRemoteRepairAxis.TIME) MAX_TIME_POINTS else 201
            codec.expect(rawX.length() in 1..limit && rawX.length() == rawY.length(), "invalid remote repair array sizes")
            counted += rawX.length()
            codec.expect(counted <= total && counted <= ceiling, "remote repair total exceeds bound")
            val xs = (0 until rawX.length()).map { number(rawX.get(it)) }
            val ys = (0 until rawY.length()).map { number(rawY.get(it)) }
            if (expected.axis == OfflineRemoteRepairAxis.TIME)
                codec.expect(timeCoordinates(xs, ys, expected.effectiveLow, expected.effectiveHigh), "invalid source-shaped time samples")
            else {
                codec.expect(xs.all { it >= 0.0 } && xs.zipWithNext().all { (a, b) -> a <= b }, "invalid remote repair samples")
                codec.expect(adaptiveCoordinates(xs, ys, expected.low, expected.high), "remote repair samples differ from original adaptive protocol")
            }
            OfflineRemoteRepairSeries(id, revision, source, codec.frozen(xs), codec.frozen(ys))
        }
        codec.expect(series.map { it.fitId } == expected.fits.keys.toList(), "reordered or duplicate remote repair fits")
        codec.expect(codec.integer(root.get("total_points")) == series.sumOf { it.x.size }.toLong(), "incorrect remote repair sample total")
        return OfflineRemoteRepairResult(expected.requestId, true, expected, codec.frozen(series), null, effectiveTime)
    }

    /** Source-shaped XTimeMixin runs, not authentication of the hidden cache or numerical truth.
     * Initial event may overshoot; only its terminal horizontal return may descend.
     * No sorting, clipping, deduplication, or distance-grid assumptions are applied.
     * Strict JSON Number/graph Double storage can collapse distinct large integer tokens.
     * At integral magnitudes >= 2^53 only, an equal Double pair may still be an
     * original change. Admission there is deliberately conservative, not proof of
     * exact integer identity. Small-value redundant change pairs remain invalid. */
    internal fun timeCoordinates(xs: List<Double>, ys: List<Double>, low: Double, high: Double): Boolean {
        if (xs.isEmpty() || xs.size != ys.size || xs.any { !it.isFinite() || it < 0.0 } || ys.any { !it.isFinite() }) return false
        fun mayChange(a: Double, b: Double): Boolean = a != b ||
            kotlin.math.abs(a) >= 9007199254740992.0 && a == kotlin.math.floor(a)
        if (xs.size == 1) return xs[0] == high || low == high && xs[0] == low
        if (xs[0] != low) return false
        var i = 1
        var initial = low
        if (xs[i] > low) {
            if (ys[i] != ys[0]) return false
            initial = xs[i++]
        }
        if (i == xs.lastIndex && xs[i] == high && ys[i] == ys[i - 1]) return true
        if (i < xs.size && xs[i] == initial) {
            if (!mayChange(ys[i], ys[i - 1]) && ys[i] != 0.0) return false
            i++
        }
        if (i == xs.size) return initial >= high
        var previous = initial
        while (i < xs.size) {
            // Final extension, including original first-event overshoot/backwards segment.
            if (i == xs.lastIndex) return xs[i] == high && ys[i] == ys[i - 1] &&
                (previous <= high || previous == initial)
            val at = xs[i]
            if (at <= previous || at >= high || xs[i + 1] != at || ys[i] != ys[i - 1] || !mayChange(ys[i + 1], ys[i])) return false
            previous = at
            i += 2
        }
        // A completed non-initial change run below max always gets an extension.
        return false
    }

    /**
     * SmoothPointGetter's 50 base intervals, depth 2, in metre arithmetic. Every
     * occurrence matters: adjacent bases and inserted points can round to the same
     * coordinate. Bounded dynamic matching avoids greedy ambiguity within 8 ULPs.
     * This validates the wire sampling protocol; EOS alone supplies the repair math.
     */
    private fun adaptiveCoordinates(xs: List<Double>, ys: List<Double>, low: Double, high: Double): Boolean {
        val lowM = low * 1000.0; val highM = high * 1000.0
        if (!lowM.isFinite() || !highM.isFinite()) return false
        val step = (highM - lowM) / 50.0
        fun matches(index: Int, metres: Double): Boolean {
            // An infinite expected midpoint must not pass using an infinite ULP tolerance.
            if (index !in xs.indices || !metres.isFinite()) return false
            val wanted = metres / 1000.0
            return wanted.isFinite() && kotlin.math.abs(xs[index] - wanted) <= 8.0 * Math.ulp(wanted)
        }
        if (step == 0.0) return xs.size == 1 && matches(0, lowM)
        if (xs.size !in 51..201 || !matches(0, lowM)) return false
        var positions = setOf(0)
        for (interval in 1..50) {
            val left = lowM + step * (interval - 1)
            val right = lowM + step * interval
            val mid = (left + right) / 2.0
            val quarterLeft = (left + mid) / 2.0
            val quarterRight = (mid + right) / 2.0
            val next = mutableSetOf<Int>()
            for (start in positions) {
                val lowY: Double = ys[start]
                // Shape []: equal base endpoint ys prohibit any midpoint evaluation.
                if (matches(start + 1, right) && lowY == ys[start + 1]) next.add(start + 1)
                for ((hasLeft, hasRight) in listOf(true to false, false to true, true to true)) {
                    val middle = start + if (hasLeft) 2 else 1
                    val end = middle + if (hasRight) 2 else 1
                    if (!matches(end, right) || !matches(middle, mid) ||
                        hasLeft && !matches(start + 1, quarterLeft) || hasRight && !matches(middle + 1, quarterRight)) continue
                    val midY: Double = ys[middle]; val highY: Double = ys[end]
                    if (lowY != highY && (lowY != midY) == hasLeft && (midY != highY) == hasRight) next.add(end)
                }
            }
            if (next.isEmpty()) return false
            positions = next
        }
        return xs.lastIndex in positions
    }
}

/** Isolated strict grammar copied from StrictJson; shared routes retain signed-64-only parsing.
 * Remote repair admits generic finite integer scalar tokens under its reviewed wire bound.
 * Duplicate keys, exact integer-vs-decimal types, nesting and all lexical checks stay strict. */
private class RemoteRepairJson(private val input: String) {
    private var position = 0

    fun parse(): Any {
        val value = value(0)
        whitespace()
        OfflineFeatureCodec.expect(position == input.length, "Trailing JSON input")
        return value
    }

    private fun value(depth: Int): Any {
        OfflineFeatureCodec.expect(depth <= 128, "JSON nesting is too deep")
        whitespace()
        OfflineFeatureCodec.expect(position < input.length, "Missing JSON value")
        return when (input[position]) {
            '{' -> objectValue(depth + 1)
            '[' -> arrayValue(depth + 1)
            '"' -> string()
            't' -> literal("true", true)
            'f' -> literal("false", false)
            'n' -> literal("null", JSONObject.NULL)
            '-', in '0'..'9' -> number()
            else -> OfflineFeatureCodec.reject("Invalid JSON value")
        }
    }

    private fun objectValue(depth: Int): JSONObject {
        position++
        val result = JSONObject()
        val keys = mutableSetOf<String>()
        whitespace()
        if (take('}')) return result
        while (true) {
            whitespace()
            OfflineFeatureCodec.expect(position < input.length && input[position] == '"', "JSON object keys must be quoted")
            val key = string()
            OfflineFeatureCodec.expect(keys.add(key), "Duplicate JSON key")
            whitespace()
            OfflineFeatureCodec.expect(take(':'), "Missing JSON colon")
            result.put(key, value(depth))
            whitespace()
            if (take('}')) return result
            OfflineFeatureCodec.expect(take(','), "Missing JSON object separator")
        }
    }

    private fun arrayValue(depth: Int): JSONArray {
        position++
        val result = JSONArray()
        whitespace()
        if (take(']')) return result
        while (true) {
            result.put(value(depth))
            whitespace()
            if (take(']')) return result
            OfflineFeatureCodec.expect(take(','), "Missing JSON array separator")
        }
    }

    private fun string(): String {
        position++
        val result = StringBuilder()
        while (position < input.length) {
            val char = input[position++]
            when {
                char == '"' -> return result.toString()
                char == '\\' -> {
                    OfflineFeatureCodec.expect(position < input.length, "Incomplete JSON escape")
                    when (val escaped = input[position++]) {
                        '"', '\\', '/' -> result.append(escaped)
                        'b' -> result.append('\b')
                        'f' -> result.append('\u000C')
                        'n' -> result.append('\n')
                        'r' -> result.append('\r')
                        't' -> result.append('\t')
                        'u' -> {
                            OfflineFeatureCodec.expect(position + 4 <= input.length, "Incomplete Unicode escape")
                            val digits = input.substring(position, position + 4)
                            OfflineFeatureCodec.expect(digits.all { it in '0'..'9' || it in 'a'..'f' || it in 'A'..'F' }, "Invalid Unicode escape")
                            result.append(digits.toInt(16).toChar())
                            position += 4
                        }
                        else -> OfflineFeatureCodec.reject("Invalid JSON escape")
                    }
                }
                char.code < 0x20 -> OfflineFeatureCodec.reject("Unescaped JSON control character")
                else -> result.append(char)
            }
        }
        OfflineFeatureCodec.reject("Unterminated JSON string")
    }

    private fun number(): Number {
        val begin = position
        take('-')
        OfflineFeatureCodec.expect(position < input.length, "Incomplete JSON number")
        if (take('0')) {
            OfflineFeatureCodec.expect(position == input.length || input[position] !in '0'..'9', "Leading zero in JSON number")
        } else {
            OfflineFeatureCodec.expect(position < input.length && input[position] in '1'..'9', "Invalid JSON number")
            digits()
        }
        var decimal = false
        if (take('.')) {
            decimal = true
            requiredDigits()
        }
        if (take('e') || take('E')) {
            decimal = true
            if (!take('+')) take('-')
            requiredDigits()
        }
        // Finite binary64-compatible integer headers need at most 309 digits plus sign.
        // Bound temporary numeric token storage before substring or BigInteger allocation.
        OfflineFeatureCodec.expect(position - begin <= 310, "Remote repair numeric token too long")
        val token = input.substring(begin, position)
        return if (decimal) {
            val number = token.toDoubleOrNull() ?: OfflineFeatureCodec.reject("Invalid decimal")
            OfflineFeatureCodec.expect(number.isFinite(), "Nonfinite JSON number")
            number
        } else token.toLongOrNull() ?: java.math.BigInteger(token).also {
            OfflineFeatureCodec.expect(it.toDouble().isFinite(), "Nonfinite remote repair integer")
        }
    }

    private fun requiredDigits() {
        OfflineFeatureCodec.expect(position < input.length && input[position] in '0'..'9', "Missing number digits")
        digits()
    }
    private fun digits() { while (position < input.length && input[position] in '0'..'9') position++ }
    private fun literal(token: String, value: Any): Any {
        OfflineFeatureCodec.expect(input.startsWith(token, position), "Invalid JSON literal")
        position += token.length
        return value
    }
    private fun take(char: Char): Boolean {
        if (position >= input.length || input[position] != char) return false
        position++
        return true
    }
    private fun whitespace() { while (position < input.length && input[position] in " \t\r\n") position++ }
}
