package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Wire witnesses only. These synthetic Y/EHP values do not establish fitting numerical parity. */
@RunWith(AndroidJUnit4::class)
class OfflineShieldRegenerationContractTest {
    private fun request(x: OfflineShieldRegenerationX = OfflineShieldRegenerationX.TIME,
        y: OfflineShieldRegenerationY = OfflineShieldRegenerationY.AMOUNT, effective: Boolean = false) =
        OfflineShieldRegenerationRequest("shield", OfflineContext("session", "a".repeat(64), 8), linkedMapOf("fit" to 2L), x, y, effective)
    private fun coordinates(r: OfflineShieldRegenerationRequest, capacity: Double): List<Double> {
        if (capacity == 0.0 && r.x == OfflineShieldRegenerationX.PERCENT && r.y == OfflineShieldRegenerationY.AMOUNT)
            return listOf(minOf(r.low, r.high), maxOf(r.low, r.high))
        fun raw(v: Double) = if (r.x == OfflineShieldRegenerationX.TIME) v else (v / 100.0 * capacity).coerceIn(minOf(0.0, capacity), maxOf(0.0, capacity))
        val low = minOf(raw(r.low), raw(r.high)); val high = maxOf(raw(r.low), raw(r.high)); val step = (high - low) / 200.0
        val xs = if (step == 0.0 || step.isNaN()) listOf(low) else (0..200).map { low + step * it }
        return when { r.x == OfflineShieldRegenerationX.PERCENT -> xs.map { it * 100.0 / capacity }
            r.x == OfflineShieldRegenerationX.AMOUNT && r.effective -> xs.map { -2.0 * it } // Deliberately structural, not effectivify.
            else -> xs }
    }
    private fun response(r: OfflineShieldRegenerationRequest = request(), capacity: Double = 2500.0,
        recharge: Double = 700.0): JSONObject {
        val wire = JSONObject(r.json()); val rows = JSONArray()
        r.fits.forEach { (id, revision) ->
            val xs = coordinates(r, capacity)
            val ys = if (capacity == 0.0 && r.x == OfflineShieldRegenerationX.PERCENT) List(xs.size) { 0.0 }
                else xs.indices.map { if (it % 2 == 0) -3.0 else 5.0 }
            rows.put(JSONObject().put("fit_id", id).put("revision", revision)
                .put("source", JSONObject().put("shield_capacity_hp", capacity).put("shield_recharge_seconds", recharge)
                    .put("damage_pattern", JSONObject().put("em", 1.0).put("thermal", 2.0).put("kinetic", 3.0).put("explosive", 4.0)))
                .put("x", JSONArray(xs)).put("y", JSONArray(ys)))
        }
        return JSONObject().put("version", 1).put("request_id", r.requestId).put("ok", true).put("error", JSONObject.NULL)
            .put("context", r.context.json()).put("x", wire.get("x")).put("y", wire.get("y"))
            .put("effective", r.effective).put("starting_shield_percent", r.startingShieldPercent ?: JSONObject.NULL)
            .put("total_points", (0 until rows.length()).sumOf { rows.getJSONObject(it).getJSONArray("x").length() }).put("series", rows)
    }
    private fun decode(root: JSONObject, r: OfflineShieldRegenerationRequest = request()) =
        OfflineShieldRegenerationCodec.result(OfflineFeatureCodec.json(root), r)
    private fun rejected(root: JSONObject, r: OfflineShieldRegenerationRequest = request()) {
        try { decode(root, r); fail("Accepted invalid shield graph protocol") } catch (_: BridgeProtocolException) { }
    }
    private fun row(root: JSONObject) = root.getJSONArray("series").getJSONObject(0)
    private fun samples(root: JSONObject, xs: List<Double>, ys: List<Double>) {
        row(root).put("x", JSONArray(xs)).put("y", JSONArray(ys)); root.put("total_points", xs.size)
    }

    @Test fun allTwelveModesKeepPercentInputsSeparateFromAxesAndRawSources() {
        var modes = 0
        for (effective in listOf(false, true)) for (x in OfflineShieldRegenerationX.values()) for (y in OfflineShieldRegenerationY.values()) {
            val r = request(x, y, effective); val wire = JSONObject(r.json()); val result = decode(response(r), r); modes++
            assertEquals(setOf("version", "request_id", "context", "fits", "x", "y", "effective", "starting_shield_percent", "budget_ms"), wire.keys().asSequence().toSet())
            assertEquals(x.unit(effective), wire.getJSONObject("x").getString("unit")); assertEquals(x.inputUnit, wire.getJSONObject("x").getString("input_unit"))
            assertEquals(y.unit(effective), wire.getJSONObject("y").getString("unit")); assertFalse(wire.has("resolution"))
            assertEquals(x != OfflineShieldRegenerationX.TIME, wire.isNull("starting_shield_percent"))
            assertEquals(201, result.series.single().x.size)
            assertEquals(2500.0, result.series.single().source.shieldCapacityHp, 0.0)
            assertEquals(700.0, result.series.single().source.shieldRechargeSeconds, 0.0)
            assertEquals(linkedMapOf("em" to 1.0, "thermal" to 2.0, "kinetic" to 3.0, "explosive" to 4.0), result.series.single().source.damagePattern)
        }
        assertEquals(12, modes)
    }

    @Test fun signedReversedClampedAndHugeFiniteInputsRetainSourceSequence() {
        val cases = listOf(request().copy(low = 300.0, high = -50.0, startingShieldPercent = null),
            request().copy(low = -30.0, high = -2.0, startingShieldPercent = -5.0), request().copy(low = 1e306, high = 1e308),
            request(OfflineShieldRegenerationX.AMOUNT).copy(low = 150.0, high = -50.0),
            request(OfflineShieldRegenerationX.PERCENT).copy(low = -200.0, high = -1.0),
            request(OfflineShieldRegenerationX.PERCENT).copy(low = 101.0, high = Double.MAX_VALUE),
            request(OfflineShieldRegenerationX.AMOUNT).copy(high = Double.MAX_VALUE))
        cases.forEach { r -> assertEquals(coordinates(r, 2500.0), decode(response(r), r).series.single().x) }
        val reversed = cases.first(); val root = response(reversed)
        root.getJSONObject("x").put("range", JSONArray().put(reversed.high).put(reversed.low))
        rejected(root, reversed) // Echo preserves the request's order even though output is sorted.
        val distinctCapacity = request(OfflineShieldRegenerationX.AMOUNT)
        val first = decode(response(distinctCapacity, 2500.0), distinctCapacity).series.single().x.last()
        val second = decode(response(distinctCapacity, 5000.0), distinctCapacity).series.single().x.last()
        assertEquals(2500.0, first, 0.0); assertEquals(5000.0, second, 0.0)
    }

    @Test fun singletonUnderflowRoundedDuplicatesAndOriginalEndpointDriftAreNotRewritten() {
        val cases = listOf(request().copy(low = 2.0, high = 2.0), request().copy(high = Double.MIN_VALUE),
            request().copy(low = 1e9, high = Math.nextUp(1e9)), request().copy(high = 0.0017))
        cases.forEach { r -> assertEquals(coordinates(r, 2500.0), decode(response(r), r).series.single().x) }
        assertEquals(1, coordinates(cases[1], 2500.0).size)
        val duplicates = coordinates(cases[2], 2500.0)
        assertEquals(201, duplicates.size); assertTrue(duplicates.distinct().size < duplicates.size)
        val truncated = response(cases[2]); samples(truncated, duplicates.dropLast(1), List(200) { 1.0 }); rejected(truncated, cases[2])
        val foreign = response(cases[3]); row(foreign).getJSONArray("x").put(80, 0.000681); rejected(foreign, cases[3])
        val tiny = request().copy(high = 1e-20); val corrupt = response(tiny)
        row(corrupt).getJSONArray("x").put(1, 1e-22); rejected(corrupt, tiny)
    }

    @Test fun zeroCapacityPercentIdentityRequiresExactlyTwoOriginalRequestedEndpoints() {
        for (effective in listOf(false, true)) for ((low, high) in listOf(-50.0 to 150.0, 42.0 to 42.0, 100.0 to 0.0)) {
            val r = request(OfflineShieldRegenerationX.PERCENT, effective = effective).copy(low = low, high = high)
            val root = response(r, 0.0, 0.0); val result = decode(root, r)
            assertEquals(listOf(minOf(low, high), maxOf(low, high)), result.series.single().x)
            assertEquals(listOf(0.0, 0.0), result.series.single().y)
            val one = response(r, 0.0, 0.0); samples(one, listOf(minOf(low, high)), listOf(0.0)); rejected(one, r)
            row(root).getJSONArray("y").put(1, 1.0); rejected(root, r)
            val nonzero = response(r, 0.0, 0.0); samples(nonzero, listOf(minOf(low, high), maxOf(low, high)), listOf(1.0, 1.0)); rejected(nonzero, r)
        }
        for (effective in listOf(false, true)) {
            val r = request(OfflineShieldRegenerationX.AMOUNT, effective = effective)
            assertEquals(1, decode(response(r, 0.0, 0.0), r).series.single().x.size)
        }
        val normal = request(OfflineShieldRegenerationX.PERCENT)
        val bogusFallback = response(normal); samples(bogusFallback, listOf(0.0, 100.0), listOf(0.0, 0.0)); rejected(bogusFallback, normal)
    }

    @Test fun signedSourceScalarsZeroRechargeAndDamageAmountsHaveNoInventedPositivityGate() {
        for (x in listOf(OfflineShieldRegenerationX.AMOUNT, OfflineShieldRegenerationX.PERCENT)) {
            val r = request(x); val root = response(r, -2500.0, 0.0)
            val pattern = row(root).getJSONObject("source").getJSONObject("damage_pattern")
            pattern.put("em", -3.0).put("thermal", 0.0).put("kinetic", 0.0).put("explosive", 0.0)
            val values = decode(root, r).series.single()
            assertEquals(-2500.0, values.source.shieldCapacityHp, 0.0); assertEquals(0.0, values.source.shieldRechargeSeconds, 0.0)
            assertEquals(-3.0, values.source.damagePattern.getValue("em"), 0.0)
            if (x == OfflineShieldRegenerationX.PERCENT) assertTrue(values.x.zipWithNext().all { (a, b) -> a >= b })
        }
    }

    @Test fun effectiveXValidationIsDeliberatelyStructuralAndRejectsWrongShapeOrNonmonotoneOrder() {
        val r = request(OfflineShieldRegenerationX.AMOUNT, effective = true)
        val root = response(r); val xs = coordinates(r, 2500.0)
        assertTrue(decode(root, r).series.single().x.zipWithNext().all { (a, b) -> a >= b })
        val reversed = response(r); samples(reversed, xs.reversed(), List(201) { -2.0 }); decode(reversed, r)
        val wrongCount = response(r); samples(wrongCount, xs.dropLast(1), List(200) { 0.0 }); rejected(wrongCount, r)
        val disorder = response(r); row(disorder).getJSONArray("x").put(10, 1.0); rejected(disorder, r)
        // Native must not claim effective-damage arithmetic validation. The independent
        // EOS comparator separately rejects plausible but numerically corrupted EHP.
        val plausible = response(r); samples(plausible, xs.map { it * 1.1 }, List(201) { 0.0 }); decode(plausible, r)
    }

    @Test fun strictSchemaIdentityEchoTypesOrderAndTotalsRejectCorruption() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("extra", 0) }, { it.put("version", true) }, { it.put("ok", 1) }, { it.put("request_id", "other") },
            { it.put("request_id", JSONObject.NULL) }, { it.getJSONObject("context").put("generation", 9) },
            { it.getJSONObject("x").put("unit", "HP") }, { it.getJSONObject("x").put("input_unit", "%") },
            { it.getJSONObject("x").put("quantity", "shield_amount") }, { it.getJSONObject("y").put("unit", "%") },
            { it.getJSONObject("y").put("quantity", "other") }, { it.put("effective", true) }, { it.put("effective", 1) },
            { it.put("starting_shield_percent", JSONObject.NULL) }, { it.put("starting_shield_percent", "0") },
            { it.put("total_points", 200) }, { it.put("series", JSONArray()) }, { it.put("error", JSONObject()) },
            { row(it).put("fit_id", "other") }, { row(it).put("revision", 3) }, { row(it).put("y", JSONArray().put(0)) },
            { row(it).getJSONObject("source").put("shield_capacity_hp", true) },
            { row(it).getJSONObject("source").put("shield_recharge_seconds", JSONObject.NULL) },
            { row(it).getJSONObject("source").getJSONObject("damage_pattern").put("other", 0) },
            { row(it).getJSONObject("source").getJSONObject("damage_pattern").put("em", "1") },
        )
        mutations.forEach { mutate -> response().also(mutate).let { rejected(it) } }
        val r = request().copy(fits = linkedMapOf("fit" to 2L, "second" to 1L)); val pair = response(r)
        val rows = pair.getJSONArray("series"); assertEquals(r.fits.keys.toList(), decode(pair, r).series.map { it.fitId })
        pair.put("series", JSONArray().put(rows.get(1)).put(rows.get(0))); rejected(pair, r)
        pair.put("series", JSONArray().put(rows.get(0)).put(rows.get(0))); rejected(pair, r)
        for (wire in listOf(OfflineFeatureCodec.json(response()).replace("\"shield_capacity_hp\":2500.0", "\"shield_capacity_hp\":1e309"),
            OfflineFeatureCodec.json(response()).replace("\"thermal\":2.0", "\"thermal\":1e309"),
            OfflineFeatureCodec.json(response()).replace("\"x\":[0.0", "\"x\":[1e309"),
            OfflineFeatureCodec.json(response()).replace("\"version\":1", "\"version\":1,\"version\":1"))) {
            try { OfflineShieldRegenerationCodec.result(wire, request()); fail("Accepted corrupt JSON") } catch (_: BridgeProtocolException) { }
        }
    }

    @Test fun failuresAreAtomicTypedAndMarkEngineReopenOnlyWhenRequired() {
        for (code in listOf("invalid_request", "invalid_engine_data", "stale_context", "stale_fit", "fit_not_found", "cancelled",
            "deadline_exceeded", "resource_exhausted", "clock_error", "engine_error", "reopen_required", "engine_unavailable")) {
            val root = JSONObject().put("version", 1).put("request_id", JSONObject.NULL).put("ok", false)
                .put("error", JSONObject().put("code", code).put("message", "No complete samples."))
            val result = decode(root); assertFalse(result.ok); assertTrue(result.series.isEmpty())
            assertEquals(code in setOf("reopen_required", "engine_error", "engine_unavailable"), result.requiresEngineReopen)
            root.put("series", JSONArray()); rejected(root)
        }
        rejected(JSONObject().put("version", 1).put("request_id", "shield").put("ok", false)
            .put("error", JSONObject().put("code", "unknown").put("message", "Unknown")))
    }

    @Test fun finiteRequestBoundsNullStartAndImmutableDecodedArraysStayStrict() {
        request().copy(low = Double.MAX_VALUE, high = -Double.MAX_VALUE, startingShieldPercent = null).json()
        request().copy(startingShieldPercent = -100.0).json()
        request().copy(fits = (1..8).associate { "$it" to 1L }).json()
        val invalid = listOf(request().copy(low = Double.NaN), request().copy(high = Double.POSITIVE_INFINITY),
            request().copy(startingShieldPercent = Double.NaN), request(OfflineShieldRegenerationX.AMOUNT).copy(startingShieldPercent = 0.0),
            request().copy(fits = emptyMap()), request().copy(fits = (1..9).associate { "$it" to 1L }),
            request().copy(fits = mapOf("fit" to 0L)), request().copy(fits = mapOf("" to 1L)), request().copy(fits = mapOf("f".repeat(129) to 1L)), request().copy(requestId = ""),
            request().copy(requestId = "r".repeat(129)), request().copy(budgetMs = 0), request().copy(budgetMs = 10001))
        invalid.forEach { try { it.json(); fail("Accepted invalid request") } catch (_: IllegalArgumentException) { } }
        val result = decode(response()); val series = result.series.single()
        try { (result.series as MutableList<OfflineShieldRegenerationSeries>).clear(); fail("Mutable series") } catch (_: UnsupportedOperationException) { }
        try { (series.x as MutableList<Double>).clear(); fail("Mutable x") } catch (_: UnsupportedOperationException) { }
        try { (series.y as MutableList<Double>).clear(); fail("Mutable y") } catch (_: UnsupportedOperationException) { }
        try { (series.source.damagePattern as MutableMap<String, Double>).clear(); fail("Mutable source") } catch (_: UnsupportedOperationException) { }
    }
}
