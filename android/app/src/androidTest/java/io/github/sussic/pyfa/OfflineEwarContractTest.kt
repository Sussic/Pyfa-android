package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import java.math.BigInteger
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Protocol witnesses, not an oracle for EWAR values. Android execution is a separate gate. */
@RunWith(AndroidJUnit4::class)
class OfflineEwarContractTest {
    private fun request() = OfflineEwarRequest("ewar", OfflineContext("session", "a".repeat(64), 8), linkedMapOf("fit" to 2L))
    private data class Samples(val x: List<Double>, val y: List<Number>)
    /** Literal source sampling shape, including its captured outer prevX/prevY. */
    private fun samples(expected: OfflineEwarRequest, value: (Double) -> Number = { 1.0 }): Samples {
        val xs = mutableListOf<Double>(); val ys = mutableListOf<Number>()
        val low = expected.low * 1000.0; val step = (expected.high * 1000.0 - low) / 50.0
        var prevX = low; var prevY = value(low)
        fun append(x: Double, y: Number) { xs.add(x / 1000.0); ys.add(y) }
        fun same(a: Number, b: Number): Boolean = when {
            a is BigInteger && b is BigInteger -> a == b
            else -> a.toDouble() == b.toDouble()
        }
        fun extra(x1: Double, y1: Number, x2: Double, y2: Number, depth: Int) {
            if (depth <= 0 || same(y1, y2)) return
            val x = (x1 + x2) / 2.0; val y = value(x)
            extra(prevX, prevY, x, y, depth - 1); append(x, y); extra(x, y, x2, y2, depth - 1)
        }
        append(prevX, prevY)
        if (step != 0.0) for (i in 1..50) {
            val x = low + step * i; val y = value(x)
            extra(prevX, prevY, x, y, 2); append(x, y); prevX = x; prevY = y
        }
        return Samples(xs, ys)
    }
    private fun response(expected: OfflineEwarRequest = request(), values: Samples = samples(expected)): JSONObject {
        val wire = JSONObject(expected.json()); val rows = JSONArray()
        expected.fits.forEach { (id, revision) -> rows.put(JSONObject().put("fit_id", id).put("revision", revision)
            .put("x", JSONArray(values.x)).put("y", JSONArray(values.y))) }
        return JSONObject().put("version", 1).put("request_id", expected.requestId).put("ok", true)
            .put("context", expected.context.json()).put("x", wire.get("x")).put("y", wire.get("y"))
            .put("resistance_percent", expected.resistancePercent ?: JSONObject.NULL)
            .put("ignore_lock_range", expected.ignoreLockRange).put("ignore_drone_control_range", expected.ignoreDroneControlRange)
            .put("effective", JSONObject().put("distance_range_m", JSONArray().put(expected.low * 1000.0).put(expected.high * 1000.0))
                .put("resistance_fraction", expected.effectiveResistanceFraction ?: JSONObject.NULL))
            .put("total_points", values.x.size * expected.fits.size).put("series", rows).put("error", JSONObject.NULL)
    }
    private fun decode(root: JSONObject, expected: OfflineEwarRequest = request()) = OfflineEwarCodec.result(OfflineFeatureCodec.json(root), expected)
    private fun rejectedRaw(raw: String, expected: OfflineEwarRequest = request()) {
        try { OfflineEwarCodec.result(raw, expected); fail("Accepted invalid EWAR wire") }
        catch (_: BridgeProtocolException) { }
        catch (_: org.json.JSONException) { }
    }
    private fun rejected(root: JSONObject, expected: OfflineEwarRequest = request()) = rejectedRaw(OfflineFeatureCodec.json(root), expected)
    private fun replace(root: JSONObject, values: Samples) {
        root.getJSONArray("series").getJSONObject(0).put("x", JSONArray(values.x)).put("y", JSONArray(values.y))
        root.put("total_points", values.x.size)
    }
    private fun invalidRequest(expected: OfflineEwarRequest) {
        try { expected.json(); fail("Accepted invalid EWAR request") } catch (_: IllegalArgumentException) { } catch (_: BridgeProtocolException) { }
    }

    @Test fun sevenModesKeepExactOriginalUnitsDefaultsAndStrictRequestKeys() {
        val expectedUnits = listOf(null, "%", null, "%", "%", "%", "%")
        val expectedQuantities = listOf("neutStr", "webStr", "ecmStrMax", "dampStrLockRange", "tdStrOptimal", "gdStrRange", "tpStr")
        assertEquals(expectedQuantities, OfflineEwarOrdinate.values().map { it.quantity })
        OfflineEwarOrdinate.values().forEachIndexed { index, mode ->
            val input = request().copy(ordinate = mode); val root = JSONObject(input.json())
            assertEquals(expectedUnits[index], mode.unit)
            assertEquals(setOf("version", "request_id", "context", "fits", "x", "y", "resistance_percent",
                "ignore_lock_range", "ignore_drone_control_range", "budget_ms"), root.keys().asSequence().toSet())
            assertEquals(mode.quantity, root.getJSONObject("y").getString("quantity"))
            if (mode.unit == null) assertSame(JSONObject.NULL, root.getJSONObject("y").get("unit"))
            else assertEquals("%", root.getJSONObject("y").getString("unit"))
            assertEquals("distance", root.getJSONObject("x").getString("quantity")); assertEquals("km", root.getJSONObject("x").getString("unit"))
            assertEquals(0.0, input.resistancePercent!!, 0.0); assertTrue(input.ignoreLockRange); assertFalse(input.ignoreDroneControlRange)
            assertTrue(decode(response(input), input).ok)
        }
    }

    @Test fun nullableAndSignedRequestedResistanceAreSeparateFromEffectiveClamping() {
        for (value in listOf(null, -100.0, -0.0, 0.0, 37.5, 100.0, 250.0, Double.MAX_VALUE)) {
            val input = request().copy(resistancePercent = value)
            val result = decode(response(input), input)
            assertEquals(value, result.request.resistancePercent)
            assertEquals(value?.let { (it / 100.0).coerceIn(0.0, 1.0) }, result.request.effectiveResistanceFraction)
            val wrong = response(input).put("resistance_percent", if (value == null) 0 else JSONObject.NULL)
            rejected(wrong, input)
            val wrongEffective = response(input)
            wrongEffective.getJSONObject("effective").put("resistance_fraction", if (value == null) 0 else JSONObject.NULL)
            rejected(wrongEffective, input)
        }
        val clamped = request().copy(resistancePercent = 250.0)
        rejected(response(clamped).put("resistance_percent", 100.0), clamped)
        val rawWrong = response(clamped); rawWrong.getJSONObject("effective").put("resistance_fraction", 2.5); rejected(rawWrong, clamped)
    }

    @Test fun nullUnitsNeverBecomePercentTextOrInventedEnergyUnits() {
        for (mode in listOf(OfflineEwarOrdinate.NEUT, OfflineEwarOrdinate.ECM)) for (unit in listOf("%", "GJ/s", "null", "")) {
            val input = request().copy(ordinate = mode); val root = response(input)
            root.getJSONObject("y").put("unit", unit); rejected(root, input)
        }
        val input = request().copy(ordinate = OfflineEwarOrdinate.WEB); val root = response(input)
        root.getJSONObject("y").put("unit", JSONObject.NULL); rejected(root, input)
    }

    @Test fun completeOrderedEightFitResultHasExactCountsAndImmutableArrays() {
        val input = request().copy(fits = (1..8).associate { "fit-$it" to it.toLong() }, high = 0.05)
        val values = samples(input) { it }; assertEquals(201, values.x.size)
        val result = decode(response(input, values), input)
        assertEquals(1608, result.series.sumOf { it.x.size }); assertEquals(input.fits.keys.toList(), result.series.map { it.fitId })
        try { (result.series as MutableList<OfflineEwarSeries>).clear(); fail("Mutable series") } catch (_: UnsupportedOperationException) { }
        try { (result.series.first().x as MutableList<Double>).clear(); fail("Mutable x") } catch (_: UnsupportedOperationException) { }
        try { (result.series.first().y as MutableList<Double>).clear(); fail("Mutable y") } catch (_: UnsupportedOperationException) { }
        rejected(response(input, values).put("total_points", 1607), input)
        val missing = response(input, values); missing.getJSONArray("series").remove(7); rejected(missing, input)
        val reordered = response(input, values); val rows = reordered.getJSONArray("series"); val first = rows.get(0); rows.put(0, rows.get(1)); rows.put(1, first); rejected(reordered, input)
        val duplicate = response(input, values); duplicate.getJSONArray("series").put(1, duplicate.getJSONArray("series").get(0)); rejected(duplicate, input)
    }

    @Test fun allFourAdaptiveShapesSignedOrGreaterThanHundredValuesRemainOriginal() {
        val input = request().copy(high = 0.05, ordinate = OfflineEwarOrdinate.PAINTER)
        val values: List<(Double) -> Number> = listOf({ -200.0 }, { if (it < 0.5) -1.0 else 2.0 },
            { if (it <= 0.5) -1.0 else 2.0 }, { it }, { 200.0 - it }, { kotlin.math.sin(it) })
        val counts = listOf(51, 53, 53, 201, 201, 201)
        values.forEachIndexed { index, value ->
            val samples = samples(input, value); assertEquals(counts[index], samples.x.size)
            val result = decode(response(input, samples), input).series.single()
            assertEquals(samples.x, result.x); assertEquals(samples.y.map { it.toDouble() }, result.y)
        }
    }

    @Test fun repeatedCoordinatesUnderflowSingletonAndTerminalRoundingAreNotSortedOrDeduplicated() {
        for (input in listOf(request().copy(low = 2.0, high = 2.0), request().copy(high = 0.0017),
            request().copy(low = 1e9, high = Math.nextUp(1e9)), request().copy(high = Double.MIN_VALUE))) {
            val source = samples(input); val row = decode(response(input, source), input).series.single()
            assertEquals(source.x, row.x); assertEquals(source.y.map { it.toDouble() }, row.y)
            if (source.x.size > 1) {
                val missing = response(input); replace(missing, Samples(source.x.dropLast(1), source.y.dropLast(1))); rejected(missing, input)
            }
        }
        val input = request().copy(low = 1e9, high = Math.nextUp(1e9))
        val source = samples(input) { it }; assertTrue(source.x.distinct().size < source.x.size)
        assertEquals(source.x, decode(response(input, source), input).series.single().x)
        // Unneeded midpoint overflow cannot invalidate a source-flat interval.
        val huge = request().copy(low = 9e304, high = 1e305)
        val flat = samples(huge)
        assertTrue((huge.low * 1000.0 + huge.high * 1000.0).isInfinite())
        assertEquals(flat.x, decode(response(huge, flat), huge).series.single().x)
        // But unequal bases require real finite source midpoint samples, never an invented grid.
        val forged = response(huge, Samples(flat.x, flat.x))
        rejected(forged, huge)
    }

    @Test fun adaptiveMutationsCannotRemoveInsertShuffleOrMoveEvenOneUlp() {
        val input = request().copy(high = 0.05); val source = samples(input) { it }
        val variants = listOf(
            Samples(source.x.drop(1), source.y.drop(1)),
            Samples(source.x.dropLast(1), source.y.dropLast(1)),
            Samples(source.x.toMutableList().also { it[1] = Math.nextUp(it[1]) }, source.y),
            Samples(source.x.reversed(), source.y.reversed()),
            Samples(source.x, List(source.y.size) { 1.0 }),
            Samples(source.x + source.x.last(), source.y + source.y.last()),
        )
        for (value in variants) { val root = response(input); replace(root, value); rejected(root, input) }
        val constant = samples(input); val refinedFlat = Samples(source.x, List(source.y.size) { 1.0 })
        assertEquals(51, constant.x.size); val root = response(input); replace(root, refinedFlat); rejected(root, input)
    }

    @Test fun finiteGenericIntegersOutsideLongAreAcceptedWithoutWeakeningStructuralIntegers() {
        val input = request().copy(low = 0.0, high = 0.0, resistancePercent = 1e100)
        val large = BigInteger.TEN.pow(100)
        val root = response(input, Samples(listOf(0.0), listOf(large))).put("resistance_percent", large)
        assertEquals(large.toDouble(), decode(root, input).series.single().y.single(), 0.0)
        for (key in listOf("version", "total_points")) rejected(response().put(key, large))
        val badRevision = response(); badRevision.getJSONArray("series").getJSONObject(0).put("revision", large); rejected(badRevision)
        val badGeneration = response(); badGeneration.getJSONObject("context").put("generation", large); rejected(badGeneration)
        for (token in listOf(1.0, true, "1")) rejected(response().put("total_points", token))
    }

    @Test fun adaptiveBranchesCompareLargeIntegerTokensBeforeTheirDoubleRenderingCollapse() {
        val input = request().copy(high = 0.05); val base = BigInteger.ONE.shiftLeft(80)
        val source = samples(input) { base + BigInteger.valueOf((it * 4.0).toLong()) }
        assertEquals(201, source.x.size); assertEquals(1, source.y.map { it.toDouble() }.distinct().size)
        val result = decode(response(input, source), input)
        assertEquals(source.x, result.series.single().x); assertEquals(201, result.series.single().y.size)
        val wrong = response(input, source); replace(wrong, Samples(source.x, List(201) { base })); rejected(wrong, input)
        // Python distinguishes this int from the rounded float, despite identical plotted Doubles.
        val exactAbove = BigInteger("9007199254740993")
        val rounded = 9007199254740992.0
        val mixed = Samples((listOf(0.0, 0.25, 0.5) + (1..50).map { it.toDouble() }).map { it / 1000.0 },
            listOf(exactAbove, exactAbove) + List(51) { rounded })
        assertEquals(53, decode(response(input, mixed), input).series.single().x.size)
        val exactEqual = BigInteger("9007199254740992")
        val flatMixed = Samples((0..50).map { it / 1000.0 }, (0..50).map { if (it % 2 == 0) exactEqual else rounded })
        assertEquals(51, decode(response(input, flatMixed), input).series.single().x.size)
        val redundant = response(input, Samples(mixed.x, listOf(exactEqual, exactEqual) + List(51) { rounded }))
        rejected(redundant, input)
    }

    @Test fun numericTokenAndRawBoundsRejectBeforeConversionAndParsing() {
        val input = request().copy(low = 0.0, high = 0.0)
        val raw = OfflineFeatureCodec.json(response(input)).replace("\"y\":[1.0]", "\"y\":[TOKEN]")
        assertTrue(raw.contains("TOKEN"))
        val limit = "-1" + "0".repeat(308); assertEquals(310, limit.length)
        assertEquals(-1e308, OfflineEwarCodec.result(raw.replace("TOKEN", limit), input).series.single().y.single(), 0.0)
        for (token in listOf("0." + "0".repeat(309), "1" + "0".repeat(309), "1e309", "NaN", "true", "\"1\"", "null"))
            rejectedRaw(raw.replace("TOKEN", token), input)
        rejectedRaw(" ".repeat(OfflineEwarCodec.MAX_WIRE_CHARS + 1), input)
        val valid = OfflineFeatureCodec.json(response(input))
        rejectedRaw(valid + " ".repeat(32768 + 624 - valid.length + 1), input)
    }

    @Test fun duplicateKeysTrailingDataMalformedNumbersAndInvalidUnicodeAreRejected() {
        val raw = OfflineFeatureCodec.json(response())
        rejectedRaw(raw.replace("\"version\":1", "\"version\":1,\"version\":1"))
        rejectedRaw(raw + "{}")
        for (token in listOf("01", "+1", "1.", ".1", "1e", "--1")) rejectedRaw(raw.replace("\"version\":1", "\"version\":$token"))
        rejectedRaw(raw.replace("\"fit_id\":\"fit\"", "\"fit_id\":\"\\ud800\""))
        rejectedRaw(raw.replace("\"request_id\":\"ewar\"", "\"request_id\":\"\\udc00\""))
        rejected(response().put("unknown", true))
    }

    @Test fun exactContextIdentityRevisionAxesOptionsAndEffectiveMetresMustMatch() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("request_id", "other") }, { it.getJSONObject("context").put("generation", 9) },
            { it.getJSONObject("context").put("session_id", "other") }, { it.getJSONObject("context").put("dataset_sha256", "b".repeat(64)) },
            { it.getJSONObject("x").put("unit", "m") }, { it.getJSONObject("x").put("quantity", "time") },
            { it.getJSONObject("x").put("range", JSONArray().put(0).put(99)) }, { it.getJSONObject("y").put("quantity", "webStr") },
            { it.getJSONObject("effective").put("distance_range_m", JSONArray().put(0).put(100)) },
            { it.put("ignore_lock_range", false) }, { it.put("ignore_drone_control_range", true) },
            { it.getJSONArray("series").getJSONObject(0).put("revision", 3) },
        )
        for (mutate in mutations) { val root = response(); mutate(root); rejected(root) }
        val zeroGeneration = request().copy(context = request().context.copy(generation = 0)); assertTrue(decode(response(zeroGeneration), zeroGeneration).ok)
        val max = request().copy(context = request().context.copy(generation = Long.MAX_VALUE), fits = mapOf("fit" to Long.MAX_VALUE))
        assertTrue(decode(response(max), max).ok)
    }

    @Test fun requestRejectsInvalidRangeResistanceIdentityCountAndBudgetWithoutCoercion() {
        for (input in listOf(request().copy(low = -1.0), request().copy(low = 2.0, high = 1.0), request().copy(high = 1e308),
            request().copy(high = Double.NaN), request().copy(resistancePercent = Double.POSITIVE_INFINITY),
            request().copy(fits = emptyMap()), request().copy(fits = (1..9).associate { "$it" to 1L }),
            request().copy(fits = mapOf("fit" to 0L)), request().copy(fits = mapOf("x".repeat(129) to 1L)),
            request().copy(requestId = ""), request().copy(requestId = "\ud800"), request().copy(budgetMs = 0), request().copy(budgetMs = 10001),
            request().copy(context = request().context.copy(generation = -1)), request().copy(context = request().context.copy(datasetSha256 = "A".repeat(64))))) invalidRequest(input)
        val unicode = request().copy(requestId = "\ud83d\ude00".repeat(128), fits = mapOf("\n " to 1L))
        assertTrue(decode(response(unicode), unicode).ok)
        invalidRequest(unicode.copy(requestId = unicode.requestId + "x"))
    }

    @Test fun completeRecognizedErrorsRemainEmptyAndReopenOnlyWhenRequired() {
        val codes = listOf("invalid_request", "invalid_engine_data", "stale_context", "stale_fit", "fit_not_found", "cancelled",
            "deadline_exceeded", "resource_exhausted", "clock_error", "engine_error", "reopen_required", "engine_unavailable")
        for (code in codes) for (id in listOf("ewar", null)) {
            val root = JSONObject().put("version", 1).put("request_id", id ?: JSONObject.NULL).put("ok", false)
                .put("error", JSONObject().put("code", code).put("message", "Refused safely."))
            val result = decode(root); assertFalse(result.ok); assertTrue(result.series.isEmpty())
            assertEquals(code in setOf("engine_error", "reopen_required", "engine_unavailable"), result.requiresEngineReopen)
            rejected(JSONObject(OfflineFeatureCodec.json(root)).put("series", JSONArray()))
        }
        val root = JSONObject().put("version", 1).put("request_id", "ewar").put("ok", false)
            .put("error", JSONObject().put("code", "unknown").put("message", "Bad")); rejected(root)
        root.getJSONObject("error").put("code", "cancelled").put("message", "x".repeat(1024)); assertFalse(decode(root).ok)
        root.getJSONObject("error").put("message", "x".repeat(1025)); rejected(root)
        root.getJSONObject("error").put("message", "\ud83d\ude00".repeat(1024)); assertFalse(decode(root).ok)
        root.getJSONObject("error").put("message", "\ud83d\ude00".repeat(1025)); rejected(root)
    }

    @Test fun signedZeroSamplesStaySignedAndCompleteErrorsNeverBecomeFabricatedZeros() {
        val input = request().copy(low = -0.0, high = -0.0, resistancePercent = -0.0)
        val result = decode(response(input, Samples(listOf(-0.0), listOf(-0.0))), input)
        assertEquals(java.lang.Double.doubleToRawLongBits(-0.0), java.lang.Double.doubleToRawLongBits(result.series.single().y.single()))
        val malformed = response(input); malformed.getJSONArray("series").getJSONObject(0).put("y", JSONArray()); rejected(malformed, input)
        val partial = response(input); partial.getJSONArray("series").getJSONObject(0).put("x", JSONArray()); rejected(partial, input)
        val tooLarge = response(input); replace(tooLarge, Samples(List(202) { 0.0 }, List(202) { 0.0 })); rejected(tooLarge, input)
    }
}
