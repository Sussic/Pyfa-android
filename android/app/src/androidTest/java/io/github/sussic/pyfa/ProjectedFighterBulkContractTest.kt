package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProjectedFighterBulkContractTest {
    private fun key(n: Int) = n.toString(16).padStart(32,'0')
    private fun wire(op: BridgeOperation, revisions: Map<String,Long> = mapOf("fit" to 7L)) =
        JSONObject(BridgeCodec.encodeRequest(BridgeRequest("request","session",op,revisions)))
    private fun rejects(block: () -> Unit) { try { block(); fail("Malformed bulk request accepted") } catch (_: BridgeProtocolException) { } }

    @Test fun exactOrderedAtomicOperationsSnapshotCallerCollectionsAndRequireOneRevision() {
        val rows=mutableListOf(ProjectedFighterSelectionRow(9,key(9)),ProjectedFighterSelectionRow(2,key(2)))
        val original=listOf(
            BridgeOperation.SetProjectedFightersActive("fit",rows,true),
            BridgeOperation.SetProjectedFighterRanges("fit",rows,null),
            BridgeOperation.RemoveProjectedFighters("fit",rows),
            BridgeOperation.ToggleProjectedFighterAbilities("fit",rows.first(),rows,6435))
        val captured=original.map { it.snapshotArguments() }
        rows.clear()
        val names=listOf("set_projected_fighters_active","set_projected_fighter_ranges","remove_projected_fighters","toggle_projected_fighter_abilities")
        for ((index,op) in captured.withIndex()) {
            val json=wire(op); val args=json.getJSONObject("arguments")
            assertEquals(names[index],json.getString("operation"))
            assertEquals(setOf("fit_id","selection") + when(index) { 0 -> setOf("active"); 1 -> setOf("range_m"); 3 -> setOf("main","effect_id"); else -> emptySet() },args.keys().asSequence().toSet())
            val selection=args.getJSONArray("selection")
            assertEquals(2,selection.length()); assertEquals(9,selection.getJSONObject(0).getInt("position")); assertEquals(2,selection.getJSONObject(1).getInt("position"))
            for (i in 0..1) assertEquals(setOf("position","object_key"),selection.getJSONObject(i).keys().asSequence().toSet())
            assertEquals(key(9),selection.getJSONObject(0).getString("object_key"))
            assertEquals(7L,json.getJSONObject("expected_revisions").getLong("fit"))
            rejects { wire(op,emptyMap()) }; rejects { wire(op,mapOf("fit" to 7L,"other" to 1L)) }
        }
        val toggle=wire(captured[3]).getJSONObject("arguments")
        assertEquals(setOf("position","object_key"),toggle.getJSONObject("main").keys().asSequence().toSet())
        assertEquals(9,toggle.getJSONObject("main").getInt("position")); assertEquals(6435,toggle.getInt("effect_id"))
        assertTrue(wire(captured[0]).getJSONObject("arguments").getBoolean("active"))
        assertTrue(wire(captured[1]).getJSONObject("arguments").isNull("range_m"))
        val retained=(captured[2] as BridgeOperation.RemoveProjectedFighters).selection
        try { (retained as MutableList<*>).clear(); fail("Mutable queued selection") } catch (_: UnsupportedOperationException) { }
        for (value in listOf(0.0,Double.MIN_VALUE,63.7)) assertEquals(value,wire(BridgeOperation.SetProjectedFighterRanges("fit",retained,value)).getJSONObject("arguments").getDouble("range_m"),0.0)
    }

    @Test fun invalidEmptyDuplicateOversizedAndNonfiniteRequestsNeverEncode() {
        val a=ProjectedFighterSelectionRow(0,key(1))
        for (rows in listOf(emptyList(),listOf(a,a.copy(objectKey=key(2))),listOf(a,a.copy(position=1)),
            listOf(a.copy(position=-1)),listOf(a.copy(objectKey="wrong")),(0..1024).map { ProjectedFighterSelectionRow(it,key(it)) })) {
            rejects { wire(BridgeOperation.RemoveProjectedFighters("fit",rows)) }
        }
        val maximum=(0 until 1024).map { ProjectedFighterSelectionRow(it,key(it)) }
        assertEquals(1024,wire(BridgeOperation.RemoveProjectedFighters("fit",maximum)).getJSONObject("arguments").getJSONArray("selection").length())
        // Main may be absent, but combined membership must be unique and within the same bound.
        val absent=ProjectedFighterSelectionRow(99,key(99))
        assertEquals(99,wire(BridgeOperation.ToggleProjectedFighterAbilities("fit",absent,listOf(a),6435)).getJSONObject("arguments").getJSONObject("main").getInt("position"))
        for (bad in listOf(a.copy(objectKey=key(2)),a.copy(position=1),a.copy(position=-1),a.copy(objectKey="bad"))) {
            rejects { wire(BridgeOperation.ToggleProjectedFighterAbilities("fit",bad,listOf(a),6435)) }
        }
        rejects { wire(BridgeOperation.ToggleProjectedFighterAbilities("fit",ProjectedFighterSelectionRow(1024,key(1024)),maximum,6435)) }
        rejects { wire(BridgeOperation.ToggleProjectedFighterAbilities("fit",a,listOf(a),0)) }
        rejects { wire(BridgeOperation.ToggleProjectedFighterAbilities("fit",a,emptyList(),6435)) }
        for (range in listOf(-1.0,Double.NaN,Double.POSITIVE_INFINITY)) rejects { wire(BridgeOperation.SetProjectedFighterRanges("fit",listOf(a),range)) }
    }
}
