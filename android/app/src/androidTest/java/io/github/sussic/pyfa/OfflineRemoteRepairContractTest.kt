package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Protocol witnesses only. Independent original-EOS comparisons supply numerical parity. */
@RunWith(AndroidJUnit4::class)
class OfflineRemoteRepairContractTest {
    private fun request() = OfflineRemoteRepairRequest("remote-repair", OfflineContext("session", "a".repeat(64), 8),
        linkedMapOf("fit" to 2L))
    private data class Samples(val x: List<Double>, val y: List<Double>)

    /** Test transcription of the original finite depth-2 sampler, not repair calculations. */
    private fun samples(expected: OfflineRemoteRepairRequest, value: (Double) -> Double = { 1.0 }): Samples {
        val xs = mutableListOf<Double>(); val ys = mutableListOf<Double>()
        val low = expected.low * 1000.0; val high = expected.high * 1000.0
        val step = (high - low) / 50.0
        fun append(x: Double, y: Double) { xs.add(x / 1000.0); ys.add(y) }
        fun extra(x1: Double, y1: Double, x2: Double, y2: Double, depth: Int) {
            if (depth <= 0 || y1 == y2) return
            val x = (x1 + x2) / 2.0; val y = value(x)
            extra(x1, y1, x, y, depth - 1); append(x, y); extra(x, y, x2, y2, depth - 1)
        }
        var previousX = low; var previousY = value(low)
        append(previousX, previousY)
        if (step != 0.0) for (i in 1..50) {
            val x = low + step * i; val y = value(x)
            extra(previousX, previousY, x, y, 2); append(x, y)
            previousX = x; previousY = y
        }
        return Samples(xs, ys)
    }
    private fun response(expected: OfflineRemoteRepairRequest = request(), values: Samples = samples(expected)): JSONObject {
        val wire = JSONObject(expected.json())
        val series = JSONArray()
        expected.fits.forEach { (id, revision) -> series.put(JSONObject().put("fit_id", id).put("revision", revision)
            .put("source_rates", JSONObject().put("shield", 7.5).put("armor", 12.5).put("hull", 2.0))
            .put("x", JSONArray(values.x)).put("y", JSONArray(values.y))) }
        return JSONObject().put("version", expected.version).put("request_id", expected.requestId).put("ok", true)
            .put("context", expected.context.json()).put("x", wire.get("x")).put("y", wire.get("y"))
            .put("time", expected.time ?: JSONObject.NULL).also {
                if (expected.version == 2) it.put("distance", expected.distance ?: JSONObject.NULL).put("effective", JSONObject()
                    .put("x_range", JSONArray().put(expected.effectiveLow).put(expected.effectiveHigh))
                    .put("time", expected.time?.coerceIn(0.0, 2500.0) ?: JSONObject.NULL)
                    .put("distance", expected.distance?.times(1000.0) ?: JSONObject.NULL))
            }.put("ancillary_reload", expected.ancillaryReload)
            .put("ignore_lock_range", expected.ignoreLockRange).put("ignore_drone_control_range", expected.ignoreDroneControlRange)
            .put("total_points", values.x.size * expected.fits.size).put("series", series).put("error", JSONObject.NULL)
    }
    private fun decode(value: JSONObject, expected: OfflineRemoteRepairRequest = request()) =
        OfflineRemoteRepairCodec.result(OfflineFeatureCodec.json(value), expected)
    private fun rejected(value: JSONObject, expected: OfflineRemoteRepairRequest = request()) {
        try { decode(value, expected); fail("Accepted invalid remote repair protocol") }
        catch (_: BridgeProtocolException) { }
    }
    private fun replaceSamples(root: JSONObject, xs: List<Double>, ys: List<Double>) {
        root.getJSONArray("series").getJSONObject(0).put("x", JSONArray(xs)).put("y", JSONArray(ys))
        root.put("total_points", xs.size)
    }

    @Test fun requestDefaultsFixedUnitsNullTimeAndSourceRatesAreDistinctAndFrozen() {
        val expected = request(); val wire = JSONObject(expected.json())
        assertEquals(setOf("version", "request_id", "context", "fits", "x", "y", "time", "ancillary_reload",
            "ignore_lock_range", "ignore_drone_control_range", "budget_ms"), wire.keys().asSequence().toSet())
        assertEquals("distance", wire.getJSONObject("x").getString("quantity")); assertEquals("km", wire.getJSONObject("x").getString("unit"))
        assertEquals("repair_rate", wire.getJSONObject("y").getString("quantity")); assertEquals("HP/s", wire.getJSONObject("y").getString("unit"))
        assertTrue(wire.isNull("time")); assertTrue(wire.getBoolean("ancillary_reload")); assertTrue(wire.getBoolean("ignore_lock_range"))
        assertFalse(wire.getBoolean("ignore_drone_control_range")); assertFalse(wire.has("resolution"))
        assertEquals(0.0, expected.low, 0.0); assertEquals(100.0, expected.high, 0.0)
        val result = decode(response()); val row = result.series.single()
        assertEquals(OfflineRemoteRepairSourceRates(7.5, 12.5, 2.0), row.sourceRates)
        assertTrue(row.y.all { it == 1.0 }) // Source readouts deliberately do not sum to this curve.
        try { (result.series as MutableList<OfflineRemoteRepairSeries>).clear(); fail("Mutable series") } catch (_: UnsupportedOperationException) { }
        try { (row.x as MutableList<Double>).clear(); fail("Mutable x") } catch (_: UnsupportedOperationException) { }
        try { (row.y as MutableList<Double>).clear(); fail("Mutable y") } catch (_: UnsupportedOperationException) { }
    }

    @Test fun allFourOriginalShapesAndDecreasingOrNonmonotoneRatesAreAccepted() {
        val expected = request().copy(high = 0.05) // One metre per base interval.
        val curves: List<(Double) -> Double> = listOf({ 1.0 }, { if (it < 0.5) 1.0 else 2.0 },
            { if (it <= 0.5) 1.0 else 2.0 }, { it }, { 100.0 - it }, { kotlin.math.sin(it) })
        val counts = listOf(51, 53, 53, 201, 201, 201)
        curves.forEachIndexed { index, value ->
            val input = samples(expected, value)
            assertEquals(counts[index], input.x.size)
            val row = decode(response(expected, input), expected).series.single()
            assertEquals(input.x, row.x); assertEquals(input.y, row.y)
        }
    }

    @Test fun singletonRepeatedRoundedBasesAndEndpointDriftArePreserved() {
        val cases = listOf(request().copy(low = 2.0, high = 2.0), request().copy(high = 0.0017),
            request().copy(low = 1e9, high = Math.nextUp(1e9)), request().copy(high = Double.MIN_VALUE))
        cases.forEach { expected ->
            val input = samples(expected)
            val row = decode(response(expected, input), expected).series.single()
            assertEquals(input.x, row.x); assertEquals(input.y, row.y)
        }
        val repeated = samples(cases[2])
        assertEquals(51, repeated.x.size); assertTrue(repeated.x.distinct().size < 51)
        val missing = response(cases[2], Samples(repeated.x.dropLast(1), repeated.y.dropLast(1)))
        rejected(missing, cases[2])
        val varyingRepeated = samples(cases[2]) { it }
        assertTrue(varyingRepeated.x.size > 51)
        decode(response(cases[2], varyingRepeated), cases[2])
    }

    @Test fun signedZeroEqualityDoesNotInventRefinement() {
        val expected = request().copy(low = -0.0, high = 0.05)
        val input = samples(expected) { if (it.toInt() % 2 == 0) -0.0 else 0.0 }
        assertEquals(51, input.x.size)
        val row = decode(response(expected, input), expected).series.single()
        assertEquals(java.lang.Double.doubleToRawLongBits(-0.0), java.lang.Double.doubleToRawLongBits(row.y[0]))
        assertEquals(java.lang.Double.doubleToRawLongBits(0.0), java.lang.Double.doubleToRawLongBits(row.y[1]))
        // The endpoint echo may use positive zero: Python equality accepts it.
        val echo = response(expected, input)
        echo.getJSONObject("x").getJSONArray("range").put(0, 0.0)
        decode(echo, expected)
    }

    @Test fun missingMidpointsForeignCoordinatesAndWrongYPredicatesFailCompletely() {
        val expected = request().copy(high = 0.05)
        val full = samples(expected) { it }
        val invalid = listOf(
            // Midpoint alone is impossible for finite unequal endpoints.
            Samples(full.x.filterIndexed { i, _ -> i != 1 && i != 3 }, full.y.filterIndexed { i, _ -> i != 1 && i != 3 }),
            // Three optional points cannot appear between equal endpoint y values.
            Samples(full.x, full.y.toMutableList().also { it[4] = it[0] }),
            // Left-quarter insertion requires low != mid, using exact finite-y equality.
            Samples(full.x, full.y.toMutableList().also { it[2] = it[0] }),
            Samples(full.x, full.y.toMutableList().also { it[2] = it[4] }),
            Samples(full.x.toMutableList().also { it[1] += 0.00001 }, full.y),
            Samples(full.x.dropLast(1), full.y.dropLast(1)),
        )
        invalid.forEach { rejected(response(expected, it), expected) }
        val base = samples(expected)
        // No refinement cannot conceal unequal base endpoint values.
        rejected(response(expected, Samples(base.x, base.y.toMutableList().also { it[1] = 2.0 })), expected)
        val tiny = request().copy(high = 1e-20)
        val tinyInput = samples(tiny)
        val changed = tinyInput.x.toMutableList().also { it[1] += 1e-30 }
        rejected(response(tiny, Samples(changed, tinyInput.y)), tiny)
    }

    @Test fun finiteBaseCurveAllowsUnusedOverflowButInfinityNeverMatchesAnOptionalCoordinate() {
        val expected = request().copy(low = 1e305, high = 1.1e305)
        val base = samples(expected)
        assertEquals(51, base.x.size); assertTrue(base.x.all { it.isFinite() })
        assertFalse((expected.low * 1000.0 + expected.high * 1000.0).isFinite())
        decode(response(expected, base), expected)
        // Every inserted coordinate is finite and ordered, but its expected source
        // midpoint overflowed. An infinite ULP tolerance must not accept this forgery.
        val xs = listOf(base.x[0], base.x[0], base.x[0], base.x[0]) + base.x.drop(1)
        val ys = listOf(0.0, 0.0, 1.0, 1.0) + List(50) { 2.0 }
        rejected(response(expected, Samples(xs, ys)), expected)
        val overflow = OfflineFeatureCodec.json(response()).replace("\"shield\":7.5", "\"shield\":1e309")
        try { OfflineRemoteRepairCodec.result(overflow, request()); fail("Accepted nonfinite source rate") }
        catch (_: BridgeProtocolException) { }
        val nonfiniteX = OfflineFeatureCodec.json(response()).replace("\"x\":[0.0", "\"x\":[1e309")
        try { OfflineRemoteRepairCodec.result(nonfiniteX, request()); fail("Accepted nonfinite coordinate") }
        catch (_: BridgeProtocolException) { }
    }

    @Test fun strictIdentityOrderSchemaAssumptionEchoAndTotalsRejectCorruption() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", true) }, { it.put("ok", 1) }, { it.put("request_id", "other") }, { it.put("request_id", JSONObject.NULL) },
            { it.getJSONObject("context").put("generation", 9) }, { it.put("extra", 1) },
            { it.getJSONObject("x").put("quantity", "time") }, { it.getJSONObject("x").put("unit", "m") },
            { it.getJSONObject("x").put("range", JSONArray().put(0).put(99)) },
            { it.getJSONObject("y").put("quantity", "repair_total") }, { it.getJSONObject("y").put("unit", "HP") },
            { it.put("time", 0) }, { it.put("ancillary_reload", false) }, { it.put("ignore_lock_range", false) },
            { it.put("ignore_drone_control_range", true) }, { it.put("ancillary_reload", 1) },
            { it.put("total_points", 50) }, { it.put("series", JSONArray()) }, { it.put("error", JSONObject()) },
            { it.getJSONArray("series").getJSONObject(0).put("revision", 3) },
            { it.getJSONArray("series").getJSONObject(0).getJSONObject("source_rates").put("capacitor", 0) },
            { it.getJSONArray("series").getJSONObject(0).getJSONObject("source_rates").put("hull", JSONObject.NULL) },
            { it.getJSONArray("series").getJSONObject(0).getJSONObject("source_rates").put("armor", false) },
            { it.getJSONArray("series").getJSONObject(0).put("y", JSONArray().put(1)) },
            { it.getJSONArray("series").getJSONObject(0).getJSONArray("x").put(2, -1) },
            { it.getJSONArray("series").getJSONObject(0).getJSONArray("x").put(2, 1) },
        )
        mutations.forEach { mutate -> response().also(mutate).let { rejected(it) } }
        val pair = request().copy(fits = linkedMapOf("fit" to 2L, "second" to 1L))
        val ordered = response(pair)
        assertEquals(pair.fits.keys.toList(), decode(ordered, pair).series.map { it.fitId })
        val rows = ordered.getJSONArray("series")
        ordered.put("series", JSONArray().put(rows.get(1)).put(rows.get(0)))
        rejected(ordered, pair)
        ordered.put("series", JSONArray().put(rows.get(0)).put(rows.get(0)))
        rejected(ordered, pair)
    }

    @Test fun failuresHaveNoPartialSeriesAndUnknownCodesAreProtocolFailures() {
        for (code in listOf("invalid_request", "invalid_engine_data", "stale_context", "stale_fit", "fit_not_found", "cancelled",
            "deadline_exceeded", "resource_exhausted", "clock_error", "engine_error", "reopen_required", "engine_unavailable")) {
            val wire = JSONObject().put("version", 1).put("request_id", JSONObject.NULL).put("ok", false)
                .put("error", JSONObject().put("code", code).put("message", "No complete samples."))
            val result = decode(wire)
            assertFalse(result.ok); assertTrue(result.series.isEmpty())
            assertEquals(code in setOf("reopen_required", "engine_unavailable", "engine_error"), result.requiresEngineReopen)
            wire.put("series", JSONArray()); rejected(wire)
        }
        rejected(JSONObject().put("version", 1).put("request_id", "remote-repair").put("ok", false)
            .put("error", JSONObject().put("code", "unknown_future_error").put("message", "Unknown")))
    }

    @Test fun finiteMetreNormalizationAndBoundedRequestValidationHaveNoInventedDistanceCeiling() {
        request().copy(high = 1e100).json()
        request().copy(low = -0.0, high = 0.0).json()
        request().copy(fits = (1..8).associate { "$it" to 1L }).json()
        val invalid = listOf(request().copy(low = -1.0), request().copy(low = 101.0), request().copy(high = Double.NaN),
            request().copy(high = Double.POSITIVE_INFINITY), request().copy(high = Double.MAX_VALUE),
            request().copy(fits = emptyMap()), request().copy(fits = (1..9).associate { "$it" to 1L }),
            request().copy(fits = mapOf("fit" to 0L)), request().copy(fits = mapOf("" to 1L)),
            request().copy(requestId = ""), request().copy(requestId = "r".repeat(129)),
            request().copy(budgetMs = 0), request().copy(budgetMs = 10001))
        invalid.forEach { try { it.json(); fail("Accepted invalid remote repair input") } catch (_: IllegalArgumentException) { } }
    }
    @Test fun selectedTimeUsesV2AndPreservesRequestedTimeAndCurrentSourceRates() {
        for (time in listOf(-100.0, -0.0, 0.0, 0.5, 2500.0, 3000.0, Double.MAX_VALUE)) {
            val expected = request().copy(time = time)
            val wire = JSONObject(expected.json())
            assertEquals(2, wire.getInt("version")); assertTrue(wire.isNull("distance"))
            assertEquals(time, wire.getDouble("time"), 0.0)
            assertEquals(setOf("version", "request_id", "context", "fits", "x", "y", "time", "distance",
                "ancillary_reload", "ignore_lock_range", "ignore_drone_control_range", "budget_ms"), wire.keys().asSequence().toSet())
            val result = decode(response(expected), expected)
            assertEquals(time.coerceIn(0.0, 2500.0), result.effectiveTime!!, 0.0)
            assertEquals(OfflineRemoteRepairSourceRates(7.5, 12.5, 2.0), result.series.single().sourceRates)
            assertTrue(result.series.single().y.all { it == 1.0 })
        }
        val zero = request().copy(time = -0.0)
        assertEquals(java.lang.Double.doubleToRawLongBits(-0.0),
            java.lang.Double.doubleToRawLongBits(JSONObject(zero.json()).getDouble("time")))
        val echo = response(zero).put("time", 0.0)
        echo.getJSONObject("effective").put("time", 0.0)
        decode(echo, zero) // Source numeric equality, not signed-zero bit equality.
        assertEquals(1, JSONObject(request().json()).getInt("version"))
        for (bad in listOf(Double.NaN, Double.NEGATIVE_INFINITY, Double.POSITIVE_INFINITY)) {
            try { request().copy(time = bad).json(); fail("Nonfinite selected time") }
            catch (_: IllegalArgumentException) { }
        }
    }

    @Test fun selectedTimeStrictEchoKeysTypesAndVersionCannotAcceptAStaleCurrentResult() {
        val expected = request().copy(time = 3000.0)
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", 1) }, { it.put("version", true) }, { it.put("version", 2.0) },
            { it.remove("time") }, { it.put("time", true) }, { it.put("time", "3000") },
            { it.put("time", JSONObject.NULL) }, { it.put("time", 2500) },
            { it.remove("distance") }, { it.put("distance", 0) }, { it.put("extra", 0) },
            { it.remove("effective") }, { it.put("effective", JSONObject.NULL) },
            { it.getJSONObject("effective").remove("time") },
            { it.getJSONObject("effective").put("time", 3000) },
            { it.getJSONObject("effective").put("time", true) },
            { it.getJSONObject("effective").put("time", "2500") },
            { it.getJSONObject("effective").put("time", JSONObject.NULL) },
            { it.getJSONObject("effective").put("distance", 0) },
            { it.getJSONObject("effective").put("extra", 0) },
            { it.getJSONObject("effective").put("x_range", JSONArray().put(0).put(99)) },
            { it.getJSONObject("effective").put("x_range", JSONArray().put(0).put(100).put(100)) },
            { it.getJSONObject("effective").put("x_range", JSONArray().put(false).put(100)) },
            { it.getJSONObject("x").put("unit", "s") }, { it.getJSONObject("y").put("unit", "HP") },
        )
        mutations.forEach { mutate -> response(expected).also(mutate).let { rejected(it, expected) } }
        rejected(response(), expected); rejected(response(expected))
        for ((field, number) in listOf("time" to "3000.0", "time" to "2500.0")) {
            val raw = OfflineFeatureCodec.json(response(expected)).replace("\"$field\":$number", "\"$field\":1e309")
            try { OfflineRemoteRepairCodec.result(raw, expected); fail("Nonfinite time echo") }
            catch (_: BridgeProtocolException) { }
        }
    }

    @Test fun selectedTimeRetainsAll201SamplesFitOrderAndWholeRequestFailures() {
        val expected = request().copy(time = 123.5, high = 0.05, fits = linkedMapOf("second" to 4L, "fit" to 2L))
        val full = samples(expected) { it }
        assertEquals(201, full.x.size)
        val result = decode(response(expected, full), expected)
        assertEquals(listOf("second", "fit"), result.series.map { it.fitId })
        assertTrue(result.series.all { it.x == full.x && it.y == full.y })
        val reordered = response(expected, full); val rows = reordered.getJSONArray("series")
        reordered.put("series", JSONArray().put(rows.get(1)).put(rows.get(0))); rejected(reordered, expected)
        val partial = response(expected, full).put("series", JSONArray().put(rows.get(0))).put("total_points", 201)
        rejected(partial, expected)
        val oversize = response(expected, full)
        val oversizedRow = oversize.getJSONArray("series").getJSONObject(0)
        oversizedRow.getJSONArray("x").put(full.x.last())
        oversizedRow.getJSONArray("y").put(full.y.last())
        oversize.put("total_points", 403) // Equal lengths and correct sum still cannot exceed 201 per fit.
        rejected(oversize, expected)
        for (code in listOf("invalid_request", "invalid_engine_data", "stale_context", "stale_fit", "fit_not_found",
            "cancelled", "deadline_exceeded", "resource_exhausted", "clock_error", "engine_error", "reopen_required", "engine_unavailable")) {
            val error = JSONObject().put("version", 2).put("request_id", expected.requestId).put("ok", false)
                .put("error", JSONObject().put("code", code).put("message", "No complete samples."))
            val failure = decode(error, expected)
            assertFalse(failure.ok); assertTrue(failure.series.isEmpty())
            assertEquals(code in setOf("reopen_required", "engine_unavailable", "engine_error"), failure.requiresEngineReopen)
            error.put("request_id", JSONObject.NULL); assertFalse(decode(error, expected).ok)
            error.put("request_id", "foreign"); rejected(error, expected)
            error.put("request_id", expected.requestId).put("series", JSONArray()); rejected(error, expected)
            error.remove("series"); error.put("version", 1); rejected(error, expected)
        }
    }

    @Test fun amountRequiresFiniteExplicitTimeAndPreservesUnitsClampsAndSourceRates() {
        for (time in listOf(-Double.MAX_VALUE, -0.0, 0.0, 0.5, 2500.0, Double.MAX_VALUE)) {
            val expected = request().copy(time = time, ordinate = OfflineRemoteRepairOrdinate.AMOUNT)
            val wire = JSONObject(expected.json())
            assertEquals(2, wire.getInt("version")); assertTrue(wire.isNull("distance"))
            assertEquals("repair_amount", wire.getJSONObject("y").getString("quantity"))
            assertEquals("HP", wire.getJSONObject("y").getString("unit"))
            assertEquals(time, wire.getDouble("time"), 0.0)
            val result = decode(response(expected), expected)
            assertEquals(time.coerceIn(0.0, 2500.0), result.effectiveTime!!, 0.0)
            assertEquals(OfflineRemoteRepairSourceRates(7.5, 12.5, 2.0), result.series.single().sourceRates)
            // Zero is an actual event lookup, not a codec-fabricated all-zero curve.
            assertTrue(result.series.single().y.all { it == 1.0 })
        }
        for (bad in listOf(null, Double.NaN, Double.POSITIVE_INFINITY, Double.NEGATIVE_INFINITY)) {
            try { request().copy(time = bad, ordinate = OfflineRemoteRepairOrdinate.AMOUNT).json(); fail("Invalid amount time") }
            catch (_: IllegalArgumentException) { }
        }
        assertEquals(1, request().version)
        assertEquals(2, request().copy(time = 0.0).version)
    }

    @Test fun amountRejectsRateEchoWrongUnitsNullBooleanTimeAndRelaxedDistanceShapes() {
        val expected = request().copy(time = 3000.0, ordinate = OfflineRemoteRepairOrdinate.AMOUNT)
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.getJSONObject("y").put("quantity", "repair_rate") },
            { it.getJSONObject("y").put("unit", "HP/s") },
            { it.getJSONObject("y").put("extra", 0) }, { it.put("version", 1) },
            { it.remove("time") }, { it.put("time", JSONObject.NULL) }, { it.put("time", true) },
            { it.put("time", "3000") }, { it.put("time", 2500) }, { it.put("distance", 0) },
            { it.getJSONObject("effective").put("time", 3000) },
            { it.getJSONObject("effective").put("time", JSONObject.NULL) },
            { it.getJSONObject("effective").put("time", false) },
            { it.getJSONObject("effective").put("distance", 0) },
            { it.getJSONObject("x").put("quantity", "time") },
            { it.getJSONObject("x").put("unit", "s") },
            { it.getJSONArray("series").getJSONObject(0).getJSONArray("x").put(1, 0.5) },
        )
        mutations.forEach { mutate -> rejected(response(expected).also(mutate), expected) }
        rejected(response(expected.copy(ordinate = OfflineRemoteRepairOrdinate.RATE)), expected)
        rejected(response(expected), expected.copy(ordinate = OfflineRemoteRepairOrdinate.RATE))
        val negative = expected.copy(time = -5.0)
        rejected(response(negative).also { it.getJSONObject("effective").put("time", -5) }, negative)
        val raw = OfflineFeatureCodec.json(response(expected)).replace("\"time\":3000.0", "\"time\":1e309")
        try { OfflineRemoteRepairCodec.result(raw, expected); fail("Nonfinite amount time echo") }
        catch (_: BridgeProtocolException) { }
    }

    @Test fun amountKeepsAdaptiveCoordinatesOrderAndCompleteFailureEnvelopes() {
        val expected = request().copy(time = 0.0, ordinate = OfflineRemoteRepairOrdinate.AMOUNT,
            high = 0.05, fits = linkedMapOf("second" to 4L, "fit" to 2L))
        val full = samples(expected) { it }
        val result = decode(response(expected, full), expected)
        assertEquals(201, full.x.size)
        assertEquals(expected.fits.keys.toList(), result.series.map { it.fitId })
        assertTrue(result.series.all { it.x == full.x && it.y == full.y })
        val single = expected.copy(low = 2.0, high = 2.0)
        assertTrue(decode(response(single), single).series.all { it.x == listOf(2.0) })
        val partial = response(expected, full)
        partial.put("series", JSONArray().put(partial.getJSONArray("series").get(0))).put("total_points", 201)
        rejected(partial, expected)
        for (code in listOf("cancelled", "resource_exhausted", "deadline_exceeded", "stale_fit", "invalid_request")) {
            val error = JSONObject().put("version", 2).put("request_id", expected.requestId).put("ok", false)
                .put("error", JSONObject().put("code", code).put("message", "No complete samples."))
            assertTrue(decode(error, expected).series.isEmpty())
            error.put("series", JSONArray()); rejected(error, expected)
        }
    }


    @Test fun bothTimeOrdinatesPreserveClampedRequestsNullZeroAndSourceRates() {
        for (ordinate in OfflineRemoteRepairOrdinate.values()) for (distance in listOf(null, 0.0, 65.625)) {
            val expected = request().copy(axis = OfflineRemoteRepairAxis.TIME, ordinate = ordinate,
                low = -1.0, high = 2501.0, distance = distance)
            val wire = JSONObject(expected.json())
            assertEquals(2, expected.version); assertTrue(wire.isNull("time"))
            assertEquals("time", wire.getJSONObject("x").getString("quantity"))
            assertEquals("s", wire.getJSONObject("x").getString("unit"))
            assertEquals(distance == null, wire.isNull("distance"))
            val samples = Samples(listOf(0.0, 2500.0), listOf(0.0, 0.0))
            val result = decode(response(expected, samples), expected)
            assertEquals(samples.x, result.series.single().x); assertNull(result.effectiveTime)
            assertEquals(OfflineRemoteRepairSourceRates(7.5, 12.5, 2.0), result.series.single().sourceRates)
            assertEquals(0.0, expected.effectiveLow, 0.0); assertEquals(2500.0, expected.effectiveHigh, 0.0)
        }
    }

    @Test fun timeOriginalOvershootsDuplicatesAndOnePointWindowsAreNotDistanceGrids() {
        for (ordinate in OfflineRemoteRepairOrdinate.values()) {
            val cases = listOf(
                Triple(0.0 to 0.0, listOf(0.0, 6.0, 6.0, 0.0), listOf(0.0, 0.0, 256.0, 256.0)),
                Triple(0.0 to 3.0, listOf(0.0, 6.0, 6.0, 3.0), listOf(0.0, 0.0, 256.0, 256.0)),
                Triple(0.0 to 3.0, listOf(0.0, 6.0, 6.0), listOf(0.0, 0.0, 256.0)),
                Triple(2.0 to 2.0, listOf(2.0, 2.0), listOf(0.0, 0.0)),
                Triple(2.0 to 3.0, listOf(3.0), listOf(17.0)),
                Triple(0.0 to 0.0, listOf(0.0), listOf(0.0)),
                Triple(0.0 to 3.0, listOf(0.0, 0.0, 1.0, 1.0, 3.0), listOf(0.0, 5.0, 5.0, 2.0, 2.0)),
            )
            for ((range, x, y) in cases) {
                val expected = request().copy(axis = OfflineRemoteRepairAxis.TIME, ordinate = ordinate, low = range.first, high = range.second)
                val result = decode(response(expected, Samples(x, y)), expected)
                assertEquals(x, result.series.single().x); assertEquals(y, result.series.single().y)
                assertEquals(maxOf(expected.effectiveHigh, x.maxOrNull()!!), result.plotHigh, 0.0)
            }
        }
    }

    @Test fun timeStrictEchoTypesModeOrderAndMalformedStepRunsFailClosed() {
        val expected = request().copy(axis = OfflineRemoteRepairAxis.TIME, high = 3.0, distance = 1.25)
        val valid = Samples(listOf(0.0, 0.0, 3.0), listOf(0.0, 4.0, 4.0))
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", 1) }, { it.put("time", 0) }, { it.put("distance", JSONObject.NULL) },
            { it.put("distance", true) }, { it.put("distance", "1.25") },
            { it.getJSONObject("effective").put("distance", 1.25) },
            { it.getJSONObject("effective").put("time", 0) },
            { it.getJSONObject("effective").put("x_range", JSONArray(listOf(0, 4))) },
            { it.getJSONObject("x").put("unit", "km") }, { it.getJSONObject("y").put("unit", "HP") },
            { it.put("total_points", 3.0) }, { it.put("total_points", true) },
            { it.getJSONArray("series").getJSONObject(0).put("revision", 3) },
            { it.getJSONArray("series").getJSONObject(0).getJSONArray("x").put(1, true) },
        )
        mutations.forEach { rejected(response(expected, valid).also(it), expected) }
        for (bad in listOf(
            Samples(listOf(0.0, 2.0, 1.0, 3.0), listOf(0.0, 0.0, 0.0, 0.0)),
            Samples(listOf(0.0, 1.0, 3.0), listOf(0.0, 4.0, 4.0)),
            Samples(listOf(0.0, 0.0, 1.0, 2.0, 3.0), listOf(0.0, 4.0, 4.0, 6.0, 6.0)),
            Samples(listOf(0.0, 0.0, 4.0, 4.0, 3.0), listOf(0.0, 1.0, 1.0, 2.0, 2.0)),
            Samples(listOf(0.0, 6.0, 6.0, 2.0), listOf(0.0, 0.0, 2.0, 2.0)),
        )) rejected(response(expected, bad), expected)
        val two = expected.copy(fits = linkedMapOf("a" to 1L, "b" to 2L))
        val reordered = response(two, valid); val rows = reordered.getJSONArray("series")
        reordered.put("series", JSONArray().put(rows.get(1)).put(rows.get(0))); rejected(reordered, two)
    }

    @Test fun timeCeilingsCoverWholeRequestAndRawTextBeforeParsing() {
        val expected = request().copy(axis = OfflineRemoteRepairAxis.TIME, high = 2500.0)
        val xs = mutableListOf(0.0); val ys = mutableListOf(0.0)
        for (i in 1..1000) { xs.add(i.toDouble()); xs.add(i.toDouble()); ys.add((i - 1).toDouble()); ys.add(i.toDouble()) }
        xs.add(2500.0); ys.add(1000.0)
        assertEquals(2002, decode(response(expected, Samples(xs, ys)), expected).series.single().x.size)
        rejected(response(expected, Samples(xs, ys)).put("total_points", 87211), expected)
        val excessive = response(expected, Samples(List(87211) { 0.0 }, List(87211) { 0.0 })).put("total_points", 87210)
        rejected(excessive, expected)
        val multiple = expected.copy(fits = linkedMapOf("a" to 1L, "b" to 2L))
        rejected(response(multiple, Samples(List(43606) { 0.0 }, List(43606) { 0.0 })), multiple)
        try { OfflineRemoteRepairCodec.result("x".repeat(OfflineRemoteRepairCodec.MAX_WIRE_CHARS + 1), expected); fail("Oversize raw text accepted") }
        catch (failure: BridgeProtocolException) { assertTrue(failure.message!!.contains("wire exceeds absolute bound")) }
        val small = response(expected, Samples(listOf(0.0, 2500.0), listOf(0.0, 0.0)))
        try { OfflineRemoteRepairCodec.result(OfflineFeatureCodec.json(small) + " ".repeat(33000), expected); fail("Per-point wire allowance ignored") }
        catch (_: BridgeProtocolException) { }
    }

    @Test fun timeRequestRejectsWrongSecondaryInputsAndKeepsNegativeOrderedEndpoints() {
        val expected = request().copy(axis = OfflineRemoteRepairAxis.TIME)
        for (bad in listOf(expected.copy(time = 0.0), expected.copy(distance = -1.0), expected.copy(distance = Double.NaN),
            expected.copy(distance = 1e308), expected.copy(low = 2.0, high = 1.0), expected.copy(high = Double.POSITIVE_INFINITY))) {
            try { bad.json(); fail("Invalid time request accepted") } catch (_: IllegalArgumentException) { }
        }
        for ((low, high) in listOf(-5.0 to -1.0, 2501.0 to 3000.0, -0.0 to 0.0)) {
            val input = expected.copy(low = low, high = high)
            input.json(); assertEquals(low.coerceIn(0.0, 2500.0), input.effectiveLow, 0.0)
            assertEquals(high.coerceIn(0.0, 2500.0), input.effectiveHigh, 0.0)
        }
    }


    @Test fun genericLargeIntegerChangesSurviveJsonAndGraphDoublePrecisionLoss() {
        val expected = request().copy(axis = OfflineRemoteRepairAxis.TIME, high = 2.0)
        for (values in listOf("[0,9007199254740992,9007199254740992,9007199254740993,9007199254740993]",
            "[0,100000000000000000000,100000000000000000000,100000000000000000001,100000000000000000001]",
            java.math.BigInteger.TEN.pow(60).let { n -> "[0,$n,$n,${n + java.math.BigInteger.ONE},${n + java.math.BigInteger.ONE}]" })) {
            val row = response(expected, Samples(listOf(0.0, 0.0, 1.0, 1.0, 2.0), listOf(0.0, 1.0, 1.0, 2.0, 2.0)))
            // Build generic integer tokens before the graph converts Number values to Double.
            val serialized = OfflineFeatureCodec.json(row)
            val raw = serialized.replace("\"y\":" + OfflineFeatureCodec.json(row.getJSONArray("series").getJSONObject(0).getJSONArray("y")), "\"y\":$values")
            assertNotEquals(serialized, raw)
            val result = OfflineRemoteRepairCodec.result(raw, expected)
            assertEquals(listOf(0.0, 0.0, 1.0, 1.0, 2.0), result.series.single().x)
        }
        assertFalse(OfflineRemoteRepairCodec.timeCoordinates(listOf(0.0, 0.0, 1.0, 1.0, 2.0),
            listOf(0.0, 4.0, 4.0, 4.0, 4.0), 0.0, 2.0))
    }

    @Test fun boundedGenericIntegerParserKeepsStrictGrammarAndIdentityIntegerTypes() {
        val expected = request().copy(axis = OfflineRemoteRepairAxis.TIME, high = 2.0)
        val valid = response(expected, Samples(listOf(0.0, 2.0), listOf(0.0, 0.0)))
        val raw = OfflineFeatureCodec.json(valid)
        val invalid = listOf(
            raw.replace("\"ok\":true", "\"ok\":true,\"ok\":true"),
            raw + " false",
            raw.replace("\"y\":[0.0,0.0]", "\"y\":" + "[".repeat(129) + "0" + "]".repeat(129)),
            raw.replace("\"total_points\":2", "\"total_points\":2.0"),
            raw.replace("\"revision\":2", "\"revision\":100000000000000000000"),
            raw.replace("\"y\":[0.0,0.0]", "\"y\":[1e309,1e309]"),
            raw.replace("\"y\":[0.0,0.0]", "\"y\":[" + "9".repeat(311) + ",0]"),
            raw.replace("\"y\":[0.0,0.0]", "\"y\":[01,0]"),
        )
        invalid.forEach { changed ->
            assertNotEquals(raw, changed)
            try { OfflineRemoteRepairCodec.result(changed, expected); fail("Malformed generic integer protocol accepted") }
            catch (_: BridgeProtocolException) { }
        }
    }
}
