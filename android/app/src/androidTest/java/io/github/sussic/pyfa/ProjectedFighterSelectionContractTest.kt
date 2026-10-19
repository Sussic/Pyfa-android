package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.util.concurrent.CompletionException

/** Synthetic protocol identities; these are not catalogue eligibility fixtures. */
@RunWith(AndroidJUnit4::class)
class ProjectedFighterSelectionContractTest {
    private fun identity(index: Int, item: Int = if (index == 0) 23059 else 40558) = JSONObject()
        .put("index", index).put("object_key", index.toString(16).padStart(32,'0')).put("item_id", item)
    private fun source() = JSONObject().put("version", 1).put("fit_id", "fit").put("revision", 9)
        .put("main", identity(2)).put("matches", JSONArray().put(identity(0)).put(identity(2)))
    private fun row(index: Int, item: Int) = ProjectedFighterRow(index,index.toString(16).padStart(32,'0'),item,"Incoming $index",
        3,3,index!=2,if(index==2)0.0 else null,true,null)
    private fun details() = ProjectedFighterDetails("fit",9,false,listOf(row(0,23059),row(1,999),row(2,40558)))
    private fun reject(block: () -> Unit) {
        try { block(); fail("Accepted invalid similar-fighter response") } catch (_: BridgeProtocolException) { }
    }
    @Test fun orderedCrossTypeMatchesIncludeMainAndRemainImmutableWithoutAbilityInference() {
        val result = FighterSimilarSelectionCodec.decode(source().toString())
        assertEquals(listOf(0, 2), result.matches.map { it.index })
        assertEquals(listOf(23059, 40558), result.matches.map { it.itemId })
        val details = details()
        // Incoming details contain no abilities: Kotlin must not infer membership from the implemented-options query.
        assertEquals(listOf(details.squadrons[0],details.squadrons[2]), ProjectedFighterSelection.rows(result, details, details.squadrons[2]))
        try { (result.matches as MutableList<FighterSelectionIdentity>).clear(); fail("Mutable matches") }
        catch (_: UnsupportedOperationException) { }
        val maximum = source().put("main", identity(0)).put("matches", JSONArray((0..1023).map { identity(it) }))
        assertEquals(1024, FighterSimilarSelectionCodec.decode(maximum.toString()).matches.size)
        reject { FighterSimilarSelectionCodec.decode(maximum.put("matches", JSONArray((0..1024).map { identity(it) })).toString()) }
    }
    @Test fun strictShapeOrderUniquenessMainAndNumericTypesRejectMalformedSelection() {
        val mutations: List<(JSONObject) -> Unit> = listOf(
            { it.put("version", true) }, { it.put("revision", 0) }, { it.put("revision", 9.0) },
            { it.put("fit_id", "") }, { it.put("unknown", true) }, { it.put("matches", JSONArray()) },
            { it.put("matches", JSONArray().put(identity(2)).put(identity(0))) },
            { it.put("matches", JSONArray().put(identity(0)).put(identity(0))) },
            { it.getJSONArray("matches").getJSONObject(0).put("object_key", 2.toString(16).padStart(32,'0')) },
            { it.getJSONObject("main").put("item_id", 1) },
            { it.getJSONObject("main").put("index", true) },
            { it.getJSONArray("matches").getJSONObject(0).put("index", -1) },
            { it.getJSONArray("matches").getJSONObject(0).put("item_id", 0) },
            { it.getJSONArray("matches").getJSONObject(0).put("item_id", 23059.0) },
            { it.getJSONArray("matches").getJSONObject(0).put("extra", "ignored") })
        mutations.forEach { mutate -> val value = source(); mutate(value); reject { FighterSimilarSelectionCodec.decode(OfflineFeatureCodec.json(value)) } }
        reject { FighterSimilarSelectionCodec.decode(source().toString().replaceFirst("{", "{\"version\":1,")) }
    }
    @Test fun capturedFitRevisionMainAndEveryMatchedIdentityMustAgree() {
        val result = FighterSimilarSelectionCodec.decode(source().toString())
        val d = details(); val main = d.squadrons[2]
        reject { ProjectedFighterSelection.rows(result.copy(fitId = "other"), d, main) }
        reject { ProjectedFighterSelection.rows(result.copy(revision = 10), d, main) }
        reject { ProjectedFighterSelection.rows(result, d, main.copy()) }
        reject { ProjectedFighterSelection.rows(result.copy(main = result.matches[0]), d, main) }
        for (changed in listOf(result.matches[0].copy(objectKey = "replaced"), result.matches[0].copy(itemId = 99), result.matches[0].copy(index = 99))) {
            reject { ProjectedFighterSelection.rows(result.copy(matches = listOf(changed, result.main)), d, main) }
        }
        reject { ProjectedFighterSelection.rows(result, d.copy(isStructure=true), main) }
        reject { ProjectedFighterSelection.rows(result,d.copy(squadrons=d.squadrons.map { if(it.index==0) it.copy(editable=false,unavailableReason="Unavailable") else it }),main) }
        val selected=ProjectedFighterSelection.rows(result,d,main)
        try { (selected as MutableList<ProjectedFighterRow>).clear(); fail("Mutable selected rows") } catch (_: UnsupportedOperationException) { }
        val wrapped = CompletionException(IllegalArgumentException("Python ValueError: ${FighterSimilarSelectionCodec.LIMIT_MESSAGE}"))
        assertEquals("Select at most 1024 squadrons per edit.", FighterSimilarSelectionCodec.failureMessage(wrapped))
        assertFalse(FighterSimilarSelectionCodec.failureMessage(RuntimeException("private trace" )).contains("private trace"))
    }
}
