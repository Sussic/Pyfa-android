package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.os.Process
import android.provider.Settings
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import java.util.concurrent.TimeUnit
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import io.github.sussic.pyfa.ModuleTestJson.obj
import io.github.sussic.pyfa.ModuleTestJson.array
import io.github.sussic.pyfa.ModuleTestJson.compare

/** Authored only: prepared synthetic saved inputs, independent desktop outputs. */
@RunWith(AndroidJUnit4::class)
class DroneAcceptanceTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun details(id: String) = EngineRuntime.droneDetails(context, id).get(120, TimeUnit.SECONDS)
    private fun graph() = JSONObject(EngineRuntime.defensePersistenceSnapshot(context).get(120, TimeUnit.SECONDS))
    private fun diagnostics() = JSONObject(EngineRuntime.bridgeDiagnostics(context).get(120, TimeUnit.SECONDS))
    private fun send(id: String, operation: BridgeOperation, revision: Long = fit(id).revision, ok: Boolean = true): BridgeResponse {
        val result = EngineRuntime.request(context, operation, mapOf(id to revision)).get(120, TimeUnit.SECONDS)
        assertEquals(result.error?.message, ok, result.isSuccess)
        return result
    }
    private fun state(d: DroneDetails): JSONObject = obj("fit_id" to d.fitId, "revision" to d.revision,
        "active" to d.active, "active_limit" to d.activeLimit, "bay_used" to d.bayUsed,
        "bay_capacity" to d.bayCapacity, "bandwidth_used" to d.bandwidthUsed, "bandwidth_capacity" to d.bandwidthCapacity,
        "stacks" to array(d.stacks.map { s -> obj("object_key" to s.objectKey, "item_id" to s.itemId,
            "name" to s.name, "amount" to s.amount, "active" to s.active,
            "mutation" to s.mutation?.let { m -> obj("base" to m.baseItemId, "mutaplasmid" to m.mutaplasmidId,
                "rolls" to array(m.rolls.map { obj("id" to it.attributeId, "value" to it.value) })) },
            "metrics" to array(s.metrics.map { obj("key" to it.key, "unit" to it.unit, "value" to it.value) })) }))
    private fun close(expected: Double, actual: Double) {
        assertTrue(actual.isFinite())
        assertEquals(expected, actual, kotlin.math.max(1e-9, 1e-10 * kotlin.math.max(kotlin.math.abs(expected), kotlin.math.abs(actual))))
    }
    private fun original(case: JSONObject, d: DroneDetails) {
        val resources = case.getJSONObject("resources")
        val current = state(d)
        resources.keys().forEach { key -> close(resources.getDouble(key), current.getDouble(key)) }
        val rows = case.getJSONArray("stacks")
        assertEquals(rows.length(), d.stacks.size)
        assertEquals(d.stacks.size, d.stacks.map { it.objectKey }.distinct().size)
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i); val stack = d.stacks[i]
            assertEquals(i, stack.index); assertEquals(row.getInt("item_id"), stack.itemId)
            assertEquals(row.getString("name"), stack.name); assertEquals(row.getString("group"), stack.group)
            assertEquals(row.getInt("amount"), stack.amount); assertEquals(row.getInt("active"), stack.active)
            val metrics = row.getJSONObject("metrics")
            assertEquals(metrics.keys().asSequence().toSet(), stack.metrics.map { it.key }.toSet())
            stack.metrics.forEach { metric ->
                if (metrics.isNull(metric.key)) { assertNull(metric.value); assertNull(metric.text) }
                else { close(metrics.getDouble(metric.key), checkNotNull(metric.value)); assertNotNull(metric.text) }
            }
            val input = case.getJSONObject("spec").getJSONArray("drones").getJSONObject(i)
            if (!input.has("mutation")) assertNull(stack.mutation)
            else {
                val expected = input.getJSONObject("mutation"); val mutation = checkNotNull(stack.mutation)
                assertEquals(expected.getInt("base_item_id"), mutation.baseItemId)
                assertEquals(expected.getInt("mutaplasmid_id"), mutation.mutaplasmidId)
                val rolls = expected.getJSONArray("attributes")
                assertEquals(rolls.length(), mutation.rolls.size)
                for (j in 0 until rolls.length()) {
                    assertEquals(rolls.getJSONObject(j).getInt("attribute_id"), mutation.rolls[j].attributeId)
                    assertEquals(rolls.getJSONObject(j).getDouble("value"), mutation.rolls[j].value, 0.0)
                }
            }
        }
    }

    @Test fun originalDetailsMutationHistoryAtomicityAndRestartOffline() {
        val phase = InstrumentationRegistry.getArguments().getString("c04_phase") ?: error("Missing C04 phase")
        assertTrue(EngineRuntime.state.value is EngineState.Loading)
        assertEquals(1, Settings.Global.getInt(context.contentResolver, Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED, context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120, TimeUnit.SECONDS)
        val runtime = diagnostics()
        assertTrue(runtime.getJSONObject("persistence").getBoolean("opened_existing"))
        val saved = File(context.noBackupFilesDir, "c04-restart-witness.json")
        when (phase) {
            "prepare" -> {
                assertFalse(saved.exists())
                val reference = JSONObject(instrumentation.context.assets.open("drone-details-expected.json").bufferedReader().use { it.readText() })
                assertEquals("8b04f3b271e614b3e103853b44a7851a63d79d0e", reference.getString("source_commit"))
                val cases = reference.getJSONArray("cases")
                assertEquals(4, cases.length()); assertEquals(4, EngineRuntime.library.value.size)
                for (i in 0 until cases.length()) {
                    val case = cases.getJSONObject(i)
                    val id = EngineRuntime.library.value.single { it.name == case.getJSONObject("spec").getString("name") }.id
                    val before = details(id); original(case, before)
                    assertNotEquals(before.stacks[13].mutation, before.stacks[14].mutation)
                    send(id, BridgeOperation.CloneDrone(id, 13))
                    val cloned = details(id)
                    assertEquals(16, cloned.stacks.size)
                    assertEquals(before.stacks[13].mutation, cloned.stacks.last().mutation)
                    assertNotEquals(before.stacks[13].objectKey, cloned.stacks.last().objectKey)
                    send(id, BridgeOperation.Undo(id)); assertEquals(before.stacks, details(id).stacks)
                    send(id, BridgeOperation.Redo(id)); assertEquals(cloned.stacks, details(id).stacks)
                    send(id, BridgeOperation.SetDroneAmount(id, 15, 2))
                    assertEquals(before.stacks[13], details(id).stacks[13])
                    assertEquals(2, details(id).stacks[15].amount)
                    assertEquals(0, details(id).stacks[15].active)
                    send(id, BridgeOperation.ToggleDrones(id, 15, emptyList()))
                    assertEquals(2, details(id).stacks[15].active)
                    val stable = details(id); val stableGraph = graph()
                    val store = File(context.noBackupFilesDir, "fits/graph.sqlite3")
                    val bytes = store.readBytes()
                    val history = EngineRuntime.editHistory(context, id).get(120, TimeUnit.SECONDS)
                    send(id, BridgeOperation.CloneDrone(id, 13), revision = before.revision, ok = false)
                    send(id, BridgeOperation.CloneDrone(id, 999), ok = false)
                    assertEquals(stable, details(id)); compare(stableGraph, graph())
                    assertArrayEquals(bytes, store.readBytes())
                    assertEquals(history, EngineRuntime.editHistory(context, id).get(120, TimeUnit.SECONDS))
                    val duplicated = send(id, BridgeOperation.DuplicateFit(id, "C04 copy $i"))
                    val copyId = duplicated.fits.single { it.id != id }.id
                    val copy = details(copyId)
                    assertEquals(stable.stacks.map { it.mutation }, copy.stacks.map { it.mutation })
                    assertTrue(stable.stacks.map { it.objectKey }.toSet().intersect(copy.stacks.map { it.objectKey }.toSet()).isEmpty())
                }
                val snapshots = JSONObject()
                EngineRuntime.library.value.forEach { snapshots.put(it.id, state(details(it.id))) }
                saved.writeText(obj("pid" to Process.myPid(), "runtime" to runtime, "graph" to graph(), "details" to snapshots).toString(2))
            }
            "restored" -> {
                val prior = JSONObject(saved.readText())
                assertNotEquals(prior.getInt("pid"), Process.myPid())
                assertNotEquals(prior.getJSONObject("runtime").getString("session_id"), runtime.getString("session_id"))
                compare(prior.getJSONObject("graph"), graph(), strict = false)
                val snapshots = prior.getJSONObject("details")
                assertEquals(snapshots.keys().asSequence().toSet(), EngineRuntime.library.value.map { it.id }.toSet())
                snapshots.keys().forEach { id -> compare(snapshots.getJSONObject(id), state(details(id)), strict = false) }
                File(context.noBackupFilesDir, "c04-restored-receipt.json").writeText(obj("pid" to Process.myPid(),
                    "prior_pid" to prior.getInt("pid"), "fits" to snapshots.length(), "runtime" to runtime,
                    "graph" to graph(), "details" to JSONObject().apply {
                        EngineRuntime.library.value.forEach { put(it.id, state(details(it.id))) }
                    }).toString(2))
            }
            else -> error("Unknown C04 phase")
        }
    }
}
