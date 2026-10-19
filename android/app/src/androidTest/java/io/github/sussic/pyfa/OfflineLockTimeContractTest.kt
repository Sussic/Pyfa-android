package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OfflineLockTimeContractTest {
    private fun request() = OfflineLockTimeRequest("lock-curve", OfflineContext("session", "a".repeat(64), 7),
        mapOf("fit" to 3L), 25.0, 500.0, resolution = 2)
    private fun response(expected: OfflineLockTimeRequest = request()): JSONObject {
        val wire = JSONObject(expected.json())
        val xs = if (expected.low == expected.high) listOf(expected.low) else listOf(expected.low, (expected.low + expected.high) / 2, expected.high)
        return JSONObject().put("version", 1).put("request_id", expected.requestId).put("ok", true)
            .put("context", expected.context.json()).put("x", wire.get("x")).put("y", wire.get("y"))
            .put("total_points", xs.size).put("error", JSONObject.NULL)
            .put("series", JSONArray().put(JSONObject().put("fit_id", "fit").put("revision", 3)
                .put("scan_resolution", 345.0).put("x", JSONArray(xs)).put("y", JSONArray(xs.map { 10.0 }))))
    }
    @Test fun exactSamplesAndNullableOrNegativeScanResolutionArePreserved() {
        for (scan in listOf<Any>(JSONObject.NULL, -1.0, 0.0, 345.0)) {
            val value = response(); value.getJSONArray("series").getJSONObject(0).put("scan_resolution", scan)
            val result = OfflineLockTimeCodec.result(value.toString(), request())
            assertTrue(result.ok); assertEquals(listOf(25.0, 262.5, 500.0), result.series.single().x)
            assertEquals(if (scan === JSONObject.NULL) null else scan, result.series.single().scanResolution)
            try { (result.series.single().x as MutableList<Double>).clear(); fail("Mutable samples") }
            catch (_: UnsupportedOperationException) { }
        }
    }
    @Test fun singletonAndNarrowFloatingPointGridsAreNotResampled() {
        val singleton = request().copy(low = 100.0, high = 100.0)
        assertEquals(listOf(100.0), OfflineLockTimeCodec.result(response(singleton).toString(), singleton).series.single().x)
        val narrow = request().copy(low = 25.0, high = Math.nextUp(25.0))
        val value = response(narrow)
        value.getJSONArray("series").getJSONObject(0).put("x", JSONArray().put(narrow.low).put(narrow.low).put(narrow.high))
        assertEquals(listOf(narrow.low, narrow.low, narrow.high), OfflineLockTimeCodec.result(value.toString(), narrow).series.single().x)
    }
    @Test fun pinnedFractionalEndpointRoundingIsPreserved() {
        for ((low, high, last) in listOf(Triple(1.0, 4.3, 4.300000000000001), Triple(1.0, 55.5, 55.50000000000001),
            Triple(100.0, 1000.1, 1000.0999999999999))) {
            val expected = request().copy(low = low, high = high, resolution = 200)
            val xs = (0..200).map { low + ((high - low) / 200) * it }
            assertEquals(last, xs.last(), 0.0)
            val value = response(expected).put("total_points", xs.size)
            value.getJSONArray("series").getJSONObject(0).put("x", JSONArray(xs)).put("y", JSONArray(xs.map { 10.0 }))
            val result = OfflineLockTimeCodec.result(value.toString(), expected)
            assertEquals(last, result.series.single().x.last(), 0.0)
            assertEquals(xs, result.series.single().x)
        }
    }
    @Test fun staleMalformedPartialWrongUnitsAndNonfiniteSamplesFailClosed() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("request_id", "other") }, { it.put("request_id", JSONObject.NULL) }, { it.put("version", true) },
            { it.getJSONObject("context").put("generation", 8) }, { it.put("extra", 1) },
            { it.getJSONObject("x").put("unit", "km") }, { it.getJSONObject("y").put("quantity", "cap_amount") },
            { it.put("total_points", 2) }, { it.put("series", JSONArray()) }, { it.put("error", JSONObject()) },
            { it.getJSONArray("series").getJSONObject(0).put("revision", 4) },
            { it.getJSONArray("series").getJSONObject(0).put("scan_resolution", true) },
            { it.getJSONArray("series").getJSONObject(0).put("x", JSONArray().put(25).put(24).put(500)) },
            { it.getJSONArray("series").getJSONObject(0).put("x", JSONArray().put(26).put(262.5).put(500)) },
            { it.getJSONArray("series").getJSONObject(0).put("y", JSONArray().put(10).put(-1).put(10)) },
            { it.getJSONArray("series").getJSONObject(0).put("y", JSONArray().put(10)) },
        )
        mutations.forEach { mutate ->
            val value = response(); mutate(value)
            try { OfflineLockTimeCodec.result(value.toString(), request()); fail("Accepted invalid lock-time response") }
            catch (_: BridgeProtocolException) { }
        }
        for (raw in listOf(response().toString().replace(Regex("\"scan_resolution\":[^,}]+"), "\"scan_resolution\":1e309"), response().toString().replace("\"revision\":3", "\"revision\":3.0"))) {
            try { OfflineLockTimeCodec.result(raw, request()); fail("Accepted nonfinite or noninteger metadata") }
            catch (_: BridgeProtocolException) { }
        }
    }
    @Test fun errorsExposeNoPartialCurveAndOnlyFatalErrorsRequestReopen() {
        for (code in listOf("cancelled", "deadline", "stale_context", "reopen_required", "engine_unavailable", "engine_error")) {
            val value = JSONObject().put("version", 1).put("request_id", JSONObject.NULL).put("ok", false)
                .put("error", JSONObject().put("code", code).put("message", "No complete samples."))
            val result = OfflineLockTimeCodec.result(value.toString(), request())
            assertFalse(result.ok); assertTrue(result.series.isEmpty())
            assertEquals(code in setOf("reopen_required", "engine_unavailable", "engine_error"), result.requiresEngineReopen)
            value.put("series", JSONArray())
            try { OfflineLockTimeCodec.result(value.toString(), request()); fail("Accepted partial error envelope") }
            catch (_: BridgeProtocolException) { }
        }
    }
    @Test fun boundedRequestsRejectInvalidRangesCountsAndBudgets() {
        val invalid = listOf(request().copy(fits = emptyMap()), request().copy(fits = (1..9).associate { "$it" to 1L }),
            request().copy(low = 0.0), request().copy(low = 501.0), request().copy(high = 1e9 + 1),
            request().copy(low = Double.NaN), request().copy(high = Double.POSITIVE_INFINITY),
            request().copy(resolution = 0), request().copy(resolution = 1025), request().copy(budgetMs = 0), request().copy(budgetMs = 10001))
        invalid.forEach { try { it.json(); fail("Accepted unbounded request") } catch (_: IllegalArgumentException) { } }
        assertEquals(200, OfflineLockTimeRequest("defaults", request().context, request().fits).resolution)
    }
}
