package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class OfflineCapacitorContractTest {
    private fun request() = OfflineCapacitorRequest("curve", OfflineContext("session", "a".repeat(64), 1),
        mapOf("fit" to 2L), "time", "s", 0.0, 10.0, "cap_amount", "GJ", 100.0, true)
    private fun response(): JSONObject {
        val request = JSONObject(request().json())
        return JSONObject().put("version", 1).put("request_id", "curve").put("ok", true)
            .put("context", request.get("context")).put("x", request.get("x")).put("y", request.get("y"))
            .put("starting_cap_percent", 100.0).put("use_simulation", true).put("resolution", 256).put("total_points", 3)
            .put("series", JSONArray().put(JSONObject().put("fit_id", "fit").put("revision", 2)
                .put("capacity_gj", 100.0).put("recharge_time_s", 30.0).put("mode", "simulation")
                .put("simulation_applied", true).put("simulation_end_s", 10.0)
                .put("x", JSONArray().put(0.0).put(5.0).put(5.0))
                .put("y", JSONArray().put(100.0).put(95.0).put(60.0))))
    }
    @Test fun duplicateXPreservesVerticalSimulationSteps() {
        val result = OfflineCapacitorCodec.result(response().toString(), request())
        assertEquals(listOf(0.0, 5.0, 5.0), result.series.single().x)
        assertEquals(listOf(100.0, 95.0, 60.0), result.series.single().y)
    }
    @Test fun staleAndPartialResponsesAreRejected() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("request_id", "other") },
            { it.getJSONObject("context").put("generation", 2) },
            { it.getJSONArray("series").getJSONObject(0).put("revision", 3) },
            { it.put("total_points", 2) },
            { it.getJSONArray("series").getJSONObject(0).put("y", JSONArray().put(1)) },
            { it.getJSONArray("series").getJSONObject(0).put("x", JSONArray().put(0).put(5).put(4)) },
            { it.getJSONArray("series").getJSONObject(0).put("simulation_end_s", 4) },
            { it.getJSONArray("series").getJSONObject(0).put("mode", "range_exhausted") },
        )
        mutations.forEach { mutate ->
            val value = response(); mutate(value)
            try { OfflineCapacitorCodec.result(value.toString(), request()); fail("Accepted partial or stale curve") }
            catch (_: BridgeProtocolException) { }
        }
    }
    @Test fun exhaustedSimulationIsExplicitAndNeverFilledWithSyntheticPoints() {
        val expected = request().copy(low = 20.0, high = 30.0)
        val value = response().put("x", JSONObject(expected.json()).get("x")).put("total_points", 0)
        value.getJSONArray("series").getJSONObject(0).put("mode", "range_exhausted").put("x", JSONArray()).put("y", JSONArray())
        val result = OfflineCapacitorCodec.result(value.toString(), expected)
        assertTrue(result.series.single().x.isEmpty()); assertTrue(result.series.single().y.isEmpty())
    }
}
