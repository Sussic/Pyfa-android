package io.github.sussic.pyfa

import java.math.BigDecimal
import java.math.BigInteger
import org.json.JSONArray
import org.json.JSONObject

/** Original fitEwarStats ordinates. Null is an original absent unit, not a percentage. */
enum class OfflineEwarOrdinate(val quantity: String, val unit: String?, val label: String) {
    NEUT("neutStr", null, "Cap neutralized per second"),
    WEB("webStr", "%", "Speed reduction"),
    ECM("ecmStrMax", null, "Combined ECM strength"),
    DAMP("dampStrLockRange", "%", "Lock range reduction"),
    TRACKING("tdStrOptimal", "%", "Turret optimal range reduction"),
    GUIDANCE("gdStrRange", "%", "Missile flight range reduction"),
    PAINTER("tpStr", "%", "Signature radius increase"),
}

data class OfflineEwarRequest(
    val requestId: String,
    val context: OfflineContext,
    val fits: Map<String, Long>,
    val low: Double = 0.0,
    val high: Double = 100.0,
    val ordinate: OfflineEwarOrdinate = OfflineEwarOrdinate.NEUT,
    val resistancePercent: Double? = 0.0,
    val ignoreLockRange: Boolean = true,
    val ignoreDroneControlRange: Boolean = false,
    val budgetMs: Int = 10000,
) {
    val effectiveResistanceFraction: Double? get() = resistancePercent?.let { (it / 100.0).coerceIn(0.0, 1.0) }
    fun json(): String {
        OfflineEwarCodec.identity(requestId)
        OfflineEwarCodec.context(context.json())
        require(fits.size in 1..8 && fits.values.all { it >= 1 })
        fits.keys.forEach(OfflineEwarCodec::identity)
        require(low.isFinite() && high.isFinite() && low >= 0.0 && high >= low)
        require((low * 1000.0).isFinite() && (high * 1000.0).isFinite())
        require(resistancePercent == null || resistancePercent.isFinite())
        require(budgetMs in 1..10000)
        val rows = JSONArray()
        fits.forEach { (id, revision) -> rows.put(JSONObject().put("fit_id", id).put("revision", revision)) }
        return OfflineFeatureCodec.json(JSONObject().put("version", 1).put("request_id", requestId)
            .put("context", context.json()).put("fits", rows)
            .put("x", JSONObject().put("quantity", "distance").put("unit", "km").put("range", JSONArray().put(low).put(high)))
            .put("y", JSONObject().put("quantity", ordinate.quantity).put("unit", ordinate.unit ?: JSONObject.NULL))
            .put("resistance_percent", resistancePercent ?: JSONObject.NULL)
            .put("ignore_lock_range", ignoreLockRange).put("ignore_drone_control_range", ignoreDroneControlRange)
            .put("budget_ms", budgetMs)).also { require(it.length <= 16384) }
    }
}

data class OfflineEwarSeries(val fitId: String, val revision: Long, val x: List<Double>, val y: List<Double>)
data class OfflineEwarResult(val requestId: String, val ok: Boolean, val request: OfflineEwarRequest,
    val series: List<OfflineEwarSeries>, val error: OfflineFeatureError?) {
    internal val requiresEngineReopen: Boolean get() = !ok && error?.code in setOf("reopen_required", "engine_unavailable", "engine_error")
}

internal object OfflineEwarCodec {
    const val MAX_WIRE_CHARS = 1036160 // 32768 + 624 * (8 * 201); before parsing/copies.
    const val MAX_NUMERIC_TOKEN = 310
    private val codec get() = OfflineFeatureCodec
    private val errorCodes = setOf("invalid_request", "invalid_engine_data", "stale_context", "stale_fit", "fit_not_found",
        "cancelled", "deadline_exceeded", "resource_exhausted", "clock_error", "engine_error", "reopen_required", "engine_unavailable")
    internal fun identity(raw: Any): String = codec.text(raw).also {
        codec.expect(it.codePointCount(0, it.length) in 1..128, "invalid EWAR identity")
    }
    internal fun context(row: JSONObject): OfflineContext {
        codec.keys(row, "session_id", "dataset_sha256", "generation")
        val dataset = codec.text(row.get("dataset_sha256"))
        codec.expect(dataset.matches(Regex("[0-9a-f]{64}")), "invalid EWAR dataset")
        val generation = codec.integer(row.get("generation"))
        codec.expect(generation >= 0, "invalid EWAR generation")
        return OfflineContext(identity(row.get("session_id")), dataset, generation)
    }
    private fun number(raw: Any): Double = (raw as? Number ?: codec.reject("EWAR number required")).toDouble()
        .also { codec.expect(it.isFinite(), "nonfinite EWAR value") }
    private fun pair(raw: Any): List<Double> {
        val array = raw as? JSONArray ?: codec.reject("EWAR range required")
        codec.expect(array.length() == 2, "EWAR range must have two endpoints")
        return listOf(number(array.get(0)), number(array.get(1)))
    }
    private fun nullableNumber(raw: Any, expected: Double?): Boolean =
        if (expected == null) raw === JSONObject.NULL else raw !== JSONObject.NULL && number(raw) == expected

    fun result(raw: String, expected: OfflineEwarRequest): OfflineEwarResult {
        // The bridge already owns the raw String. This is a parser/copy bound, not a heap guarantee.
        codec.expect(raw.length <= MAX_WIRE_CHARS, "EWAR wire exceeds absolute bound")
        val root = codec.obj(EwarJson(raw).parse())
        codec.expect(codec.integer(root.get("version")) == 1L, "unsupported EWAR version")
        val ok = codec.bool(root.get("ok"))
        val requestId = root.get("request_id").let { if (it === JSONObject.NULL) null else identity(it) }
        codec.expect(requestId == expected.requestId || !ok && requestId == null, "EWAR response identity differs")
        if (!ok) {
            codec.keys(root, "version", "request_id", "ok", "error")
            codec.expect(raw.length <= 32768, "EWAR error wire exceeds bound")
            val error = codec.obj(root.get("error")); codec.keys(error, "code", "message")
            val code = codec.text(error.get("code")); codec.expect(code in errorCodes, "unknown EWAR error code")
            val message = codec.text(error.get("message"))
            codec.expect(message.isNotBlank() && message.codePointCount(0, message.length) <= 1024, "invalid EWAR error message")
            return OfflineEwarResult(expected.requestId, false, expected, emptyList(), OfflineFeatureError(code, message))
        }
        codec.keys(root, "version", "request_id", "ok", "context", "x", "y", "resistance_percent",
            "ignore_lock_range", "ignore_drone_control_range", "effective", "total_points", "series", "error")
        codec.expect(root.get("error") === JSONObject.NULL && context(codec.obj(root.get("context"))) == expected.context,
            "EWAR context or outcome differs")
        val x = codec.obj(root.get("x")); codec.keys(x, "quantity", "unit", "range")
        val y = codec.obj(root.get("y")); codec.keys(y, "quantity", "unit")
        val range = pair(x.get("range"))
        codec.expect(codec.text(x.get("quantity")) == "distance" && codec.text(x.get("unit")) == "km" &&
            range[0] == expected.low && range[1] == expected.high, "EWAR x differs")
        codec.expect(codec.text(y.get("quantity")) == expected.ordinate.quantity &&
            codec.nullableText(y.get("unit")) == expected.ordinate.unit, "EWAR y differs")
        codec.expect(nullableNumber(root.get("resistance_percent"), expected.resistancePercent), "EWAR requested resistance differs")
        val effective = codec.obj(root.get("effective")); codec.keys(effective, "distance_range_m", "resistance_fraction")
        val effectiveRange = pair(effective.get("distance_range_m"))
        codec.expect(effectiveRange[0] == expected.low * 1000.0 && effectiveRange[1] == expected.high * 1000.0 &&
            nullableNumber(effective.get("resistance_fraction"), expected.effectiveResistanceFraction), "EWAR effective values differ")
        codec.expect(codec.bool(root.get("ignore_lock_range")) == expected.ignoreLockRange &&
            codec.bool(root.get("ignore_drone_control_range")) == expected.ignoreDroneControlRange, "EWAR assumptions differ")
        val total = codec.integer(root.get("total_points"))
        codec.expect(total in 1..1608, "EWAR total exceeds bound")
        codec.expect(raw.length <= 32768L + 624L * total, "EWAR wire exceeds point allowance")
        val entries = root.get("series") as? JSONArray ?: codec.reject("EWAR series required")
        codec.expect(entries.length() == expected.fits.size && entries.length() in 1..8, "incomplete EWAR comparison")
        val wanted = expected.fits.entries.toList()
        var counted = 0L
        val series = (0 until entries.length()).map { index ->
            val row = codec.obj(entries.get(index)); codec.keys(row, "fit_id", "revision", "x", "y")
            val id = identity(row.get("fit_id")); val revision = codec.integer(row.get("revision"))
            codec.expect(id == wanted[index].key && revision >= 1 && revision == wanted[index].value, "EWAR fit order or revision differs")
            val rawX = row.get("x") as? JSONArray ?: codec.reject("EWAR x array required")
            val rawY = row.get("y") as? JSONArray ?: codec.reject("EWAR y array required")
            codec.expect(rawX.length() in 1..201 && rawX.length() == rawY.length(), "invalid EWAR array sizes")
            counted += rawX.length()
            codec.expect(counted <= total, "EWAR total exceeds bound")
            val xs = (0 until rawX.length()).map { number(rawX.get(it)) }
            val ys = (0 until rawY.length()).map { number(rawY.get(it)) }
            // Preserve exact integer comparisons for the adaptive branch predicates before
            // rendering as Double. Distinct finite large integers can otherwise collapse.
            val sourceYs = (0 until rawY.length()).map { rawY.get(it) as Number }
            codec.expect(adaptiveCoordinates(xs, sourceYs, expected.low, expected.high), "EWAR samples differ from original adaptive protocol")
            OfflineEwarSeries(id, revision, codec.frozen(xs), codec.frozen(ys))
        }
        codec.expect(counted == total, "incorrect EWAR sample total")
        return OfflineEwarResult(expected.requestId, true, expected, codec.frozen(series), null)
    }

    /** Python equality of finite int/float tokens, not Double-rounded integer equality. */
    private fun equal(a: Number, b: Number): Boolean {
        if (a is Double && b is Double) return a == b
        fun exact(value: Number): BigDecimal = when (value) {
            is BigInteger -> BigDecimal(value)
            is Double -> BigDecimal(value) // Exact binary64 value, not its shortest decimal spelling.
            else -> BigDecimal.valueOf(value.toLong())
        }
        return exact(a).compareTo(exact(b)) == 0
    }

    /** Source SmoothPointGetter, 50 base intervals and depth 2 in metres. No sort,
     * deduplication or strict-monotonic assumption. Dynamic matching retains repeated
     * rounded coordinates; only the four original value-dependent shapes are accepted.
     * This verifies sampling shape, not the hidden EOS arithmetic. */
    internal fun adaptiveCoordinates(xs: List<Double>, ys: List<Number>, low: Double, high: Double): Boolean {
        if (xs.isEmpty() || xs.size != ys.size || xs.any { !it.isFinite() } || ys.any { !it.toDouble().isFinite() }) return false
        val lowM = low * 1000.0; val highM = high * 1000.0
        if (!lowM.isFinite() || !highM.isFinite() || lowM < 0.0 || highM < lowM) return false
        val step = (highM - lowM) / 50.0
        fun matches(index: Int, metres: Double): Boolean =
            index in xs.indices && metres.isFinite() && xs[index] == metres / 1000.0
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
                if (matches(start + 1, right) && equal(ys[start], ys[start + 1])) next.add(start + 1)
                for ((hasLeft, hasRight) in listOf(true to false, false to true, true to true)) {
                    val middle = start + if (hasLeft) 2 else 1
                    val end = middle + if (hasRight) 2 else 1
                    if (!matches(end, right) || !matches(middle, mid) ||
                        hasLeft && !matches(start + 1, quarterLeft) || hasRight && !matches(middle + 1, quarterRight)) continue
                    if (!equal(ys[start], ys[end]) && (!equal(ys[start], ys[middle])) == hasLeft &&
                        (!equal(ys[middle], ys[end])) == hasRight) next.add(end)
                }
            }
            if (next.isEmpty()) return false
            positions = next
        }
        return xs.lastIndex in positions
    }
}

/** EWAR-only strict grammar: generic finite numbers are not structural integers. */
private class EwarJson(private val input: String) {
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
        OfflineFeatureCodec.expect(position - begin <= OfflineEwarCodec.MAX_NUMERIC_TOKEN, "EWAR numeric token too long")
        val token = input.substring(begin, position)
        return if (decimal) {
            val number = token.toDoubleOrNull() ?: OfflineFeatureCodec.reject("Invalid decimal")
            OfflineFeatureCodec.expect(number.isFinite(), "Nonfinite JSON number")
            number
        } else token.toLongOrNull() ?: java.math.BigInteger(token).also {
            OfflineFeatureCodec.expect(it.toDouble().isFinite(), "Nonfinite EWAR integer")
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
