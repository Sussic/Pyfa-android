package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OfflineMobilityContractTest {
    private fun request(mode: OfflineMobilityMode = OfflineMobilityMode.SPEED) = OfflineMobilityRequest("mobility",
        OfflineContext("session", "a".repeat(64), 8), mapOf("fit" to 2L), mode = mode,
        targetMassMkg = if (mode.needsMass) 1300.0 else null, targetInertia = if (mode.needsInertia) 0.015 else null, resolution = 2)
    private fun response(expected: OfflineMobilityRequest = request()): JSONObject {
        val wire = JSONObject(expected.json())
        val step = (expected.high - expected.low) / expected.resolution
        val count = if (step == 0.0) 1 else expected.resolution + 1
        val xs = (0 until count).map { expected.low + step * it }
        val series = JSONArray()
        expected.fits.forEach { (id, revision) -> series.put(JSONObject().put("fit_id", id).put("revision", revision)
            .put("max_velocity_mps", 250.0).put("align_time_s", 8.0).put("x", JSONArray(xs))
            .put("y", JSONArray(xs.map { 1.0 }))) }
        return JSONObject().put("version", 1).put("request_id", expected.requestId).put("ok", true)
            .put("context", expected.context.json()).put("x", wire.get("x")).put("y", wire.get("y"))
            .put("target_mass_mkg", wire.get("target_mass_mkg")).put("target_inertia", wire.get("target_inertia"))
            .put("total_points", xs.size * expected.fits.size).put("series", series).put("error", JSONObject.NULL)
    }
    @Test fun allFiveSourceModesUnitsAndApplicableTargetInputsAreExact() {
        val units = listOf("m/s", "km", "Gkg⋅m/s", "m/s", "km")
        OfflineMobilityMode.entries.forEachIndexed { index, mode ->
            val expected = request(mode); val wire = JSONObject(expected.json())
            assertEquals(mode.quantity, wire.getJSONObject("y").getString("quantity"))
            assertEquals(units[index], wire.getJSONObject("y").getString("unit"))
            assertEquals(!mode.needsMass, wire.isNull("target_mass_mkg"))
            assertEquals(!mode.needsInertia, wire.isNull("target_inertia"))
            val result = OfflineMobilityCodec.result(response(expected).toString(), expected)
            assertTrue(result.ok); assertEquals(expected, result.request)
            assertEquals(listOf(0.0, 15.0, 30.0), result.series.single().x)
            try { (result.series as MutableList<OfflineMobilitySeries>).clear(); fail("Mutable comparison") }
            catch (_: UnsupportedOperationException) { }
        }
    }
    @Test fun signedSourceRoundoffAndUnavailableMetadataAreNotReplacedByZero() {
        val expected = request(OfflineMobilityMode.DISTANCE)
        val value = response(expected)
        value.getJSONArray("series").getJSONObject(0).put("max_velocity_mps", JSONObject.NULL).put("align_time_s", JSONObject.NULL)
            .put("y", JSONArray().put(-1e-15).put(0.0).put(1.0))
        val series = OfflineMobilityCodec.result(value.toString(), expected).series.single()
        assertNull(series.maxVelocityMps); assertNull(series.alignTimeSeconds)
        assertEquals(listOf(-1e-15, 0.0, 1.0), series.y)
    }
    @Test fun sourceGridPreservesFractionalEndpointsSingletonAndStepUnderflow() {
        for (expected in listOf(request().copy(low = 1.0, high = 4.3, resolution = 200),
            request().copy(low = 2.0, high = 2.0), request().copy(low = 0.0, high = Double.MIN_VALUE, resolution = 200))) {
            val result = OfflineMobilityCodec.result(response(expected).toString(), expected)
            if (expected.high == 4.3) assertEquals(4.300000000000001, result.series.single().x.last(), 0.0)
            else assertEquals(listOf(expected.low), result.series.single().x)
        }
        // A metre-sized absolute tolerance from another graph would incorrectly accept this.
        val tiny = request().copy(low = 0.0, high = 1e-20)
        val changed = response(tiny)
        changed.getJSONArray("series").getJSONObject(0).getJSONArray("x").put(1, 1e-13)
        try { OfflineMobilityCodec.result(changed.toString(), tiny); fail("Accepted an unrelated tiny-time grid") }
        catch (_: BridgeProtocolException) { }
    }
    @Test fun staleWrongUnitsChangedTargetsAndMalformedOrPartialCurvesAreRejected() {
        val expected = request(OfflineMobilityMode.BUMP_DISTANCE)
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", true) }, { it.put("request_id", "other") }, { it.put("request_id", JSONObject.NULL) },
            { it.getJSONObject("context").put("generation", 9) }, { it.put("extra", 1) },
            { it.getJSONObject("y").put("unit", "m") }, { it.getJSONObject("y").put("quantity", "distance") },
            { it.getJSONObject("x").put("unit", "min") }, { it.put("target_mass_mkg", 1301) }, { it.put("target_inertia", true) },
            { it.put("total_points", 2) }, { it.put("series", JSONArray()) }, { it.put("error", JSONObject()) },
            { it.getJSONArray("series").getJSONObject(0).put("revision", 3) },
            { it.getJSONArray("series").getJSONObject(0).put("align_time_s", -1) },
            { it.getJSONArray("series").getJSONObject(0).put("max_velocity_mps", false) },
            { it.getJSONArray("series").getJSONObject(0).put("y", JSONArray().put(1)) },
            { it.getJSONArray("series").getJSONObject(0).put("x", JSONArray().put(0).put(16).put(30)) },
        )
        mutations.forEach { mutate ->
            val value = response(expected); mutate(value)
            try { OfflineMobilityCodec.result(value.toString(), expected); fail("Accepted invalid mobility output") }
            catch (_: BridgeProtocolException) { }
        }
        val nonfinite = response(expected).toString().replace(Regex("\"align_time_s\":[^,}]+"), "\"align_time_s\":1e309")
        try { OfflineMobilityCodec.result(nonfinite, expected); fail("Accepted infinite metadata") }
        catch (_: BridgeProtocolException) { }
        val pair = expected.copy(fits = linkedMapOf("fit" to 2L, "second" to 1L))
        val reordered = response(pair)
        val rows = reordered.getJSONArray("series")
        reordered.put("series", JSONArray().put(rows.get(1)).put(rows.get(0)))
        try { OfflineMobilityCodec.result(reordered.toString(), pair); fail("Reordered source identities") }
        catch (_: BridgeProtocolException) { }
    }
    @Test fun cancelledOverflowAndReopenErrorsCannotExposePartialSamples() {
        for (code in listOf("cancelled", "deadline_exceeded", "numerical_overflow", "stale_context", "reopen_required", "engine_unavailable", "engine_error")) {
            val value = JSONObject().put("version", 1).put("request_id", JSONObject.NULL).put("ok", false)
                .put("error", JSONObject().put("code", code).put("message", "No complete samples."))
            val result = OfflineMobilityCodec.result(value.toString(), request())
            assertFalse(result.ok); assertTrue(result.series.isEmpty())
            assertEquals(code in setOf("reopen_required", "engine_unavailable", "engine_error"), result.requiresEngineReopen)
            value.put("series", JSONArray())
            try { OfflineMobilityCodec.result(value.toString(), request()); fail("Accepted partial failure") }
            catch (_: BridgeProtocolException) { }
        }
    }
    @Test fun finiteNonnegativeInputsHaveNoInventedDesktopCeilingAndHiddenInputsMustBeNull() {
        request().copy(high = 1e100).json()
        request(OfflineMobilityMode.BUMP_DISTANCE).copy(targetMassMkg = 0.0, targetInertia = 0.0).json()
        val invalid = listOf(request().copy(low = -1.0), request().copy(low = 31.0), request().copy(high = Double.POSITIVE_INFINITY),
            request().copy(targetMassMkg = 1300.0), request().copy(targetInertia = 0.015),
            request(OfflineMobilityMode.BUMP_SPEED).copy(targetMassMkg = null),
            request(OfflineMobilityMode.BUMP_DISTANCE).copy(targetInertia = Double.NaN),
            request(OfflineMobilityMode.BUMP_DISTANCE).copy(targetInertia = -1.0),
            request().copy(fits = emptyMap()), request().copy(fits = (1..9).associate { "$it" to 1L }),
            request().copy(resolution = 0), request().copy(resolution = 1025), request().copy(budgetMs = 0), request().copy(budgetMs = 10001))
        invalid.forEach { try { it.json(); fail("Accepted invalid mobility input") } catch (_: IllegalArgumentException) { } }
    }
}
