package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ProjectedModuleChargeContractTest {
    private fun key(n:Int)=n.toString(16).padStart(32,'0')
    private fun identity(n:Int)=JSONObject().put("index",n).put("object_key",key(n)).put("item_id",100+n)
    private fun target(n:Int, status:String="change")=identity(n).put("name","Module $n").put("charge_id",if(status=="unchanged")900 else JSONObject.NULL)
        .put("charge_name",if(status=="unchanged")"Script" else JSONObject.NULL).put("status",status)
    private fun source()=JSONObject().put("version",1).put("fit_id","fit").put("revision",7).put("main",identity(2))
        .put("selection",JSONArray().put(identity(4)).put(identity(2))).put("scope","SELECTED").put("charge_id",900)
        .put("choices",JSONArray().put(JSONObject().put("id",900).put("name","Script"))).put("available",true).put("unavailable_reason",JSONObject.NULL)
        .put("targets",JSONArray().put(target(2)).put(target(4,"unchanged"))).put("excluded",JSONArray())
    private fun reject(block:()->Unit) { try { block(); fail("Invalid charge contract accepted") } catch (_:BridgeProtocolException) {} }
    private fun wire(op:BridgeOperation,revisions:Map<String,Long> = mapOf("fit" to 7L))=JSONObject(BridgeCodec.encodeRequest(BridgeRequest("request","session",op,revisions)))
    private fun row(n:Int,loaded:Boolean=false)=ProjectedModuleRow(n,key(n),100+n,"Module $n",ModuleState.ACTIVE,if(loaded)900 else null,if(loaded)"Script" else null,if(n==2)Double.MIN_VALUE else 0.0,true,null)

    @Test fun orderedPreviewIsImmutableAndOperationSnapshotsAllThreeCollections() {
        val preview=ProjectedModuleChargeCodec.decode(source().toString())
        assertEquals(listOf(4,2),preview.selection.map { it.index }); assertEquals(listOf(2,4),preview.targets.map { it.identity.index })
        val two=row(2); val four=row(4,true); val d=ProjectedModuleDetails("fit",7,false,listOf(two,four))
        ProjectedModuleChargeCodec.correlate(preview,ProjectedChargeCapture(d,ProjectedModuleBulkSelection("fit",7,"Fit",listOf(four,two)),two,BulkScope.SELECTED,900))
        val selected=preview.selection.map { it.wire() }.toMutableList(); val targets=preview.targets.map { it.identity.wire() }.toMutableList(); val changes=mutableListOf(preview.main.wire())
        val op=BridgeOperation.SetProjectedModuleCharges("fit",preview.main.wire(),selected,BulkScope.SELECTED,900,targets,changes).snapshotArguments()
        selected.clear(); targets.clear(); changes.clear()
        val args=wire(op).getJSONObject("arguments")
        assertEquals(setOf("fit_id","main","selection","scope","charge_id","expected_targets","expected_changes"),args.keys().asSequence().toSet())
        assertEquals("set_projected_module_charges",wire(op).getString("operation"))
        assertEquals(4,args.getJSONArray("selection").getJSONObject(0).getInt("position")); assertEquals(2,args.getJSONArray("expected_targets").getJSONObject(0).getInt("position"))
        assertEquals(1,args.getJSONArray("expected_changes").length())
        reject { wire(op,emptyMap()) }; reject { wire(op,mapOf("fit" to 7L,"other" to 1L)) }
        try { (preview.targets as MutableList<*>).clear(); fail("Mutable preview") } catch (_:UnsupportedOperationException) {}
        val clear=(op as BridgeOperation.SetProjectedModuleCharges).copy(chargeId=null,expectedChanges=emptyList())
        assertTrue(wire(clear).getJSONObject("arguments").isNull("charge_id"))
    }
    @Test fun malformedEnvelopesAndUnreviewedOperationListsAreRejected() {
        val mutate:List<(JSONObject)->Unit> = listOf(
            {it.put("version",true)}, {it.put("extra",1)}, {it.put("revision",7.0)}, {it.put("scope","ALL")}, {it.put("charge_id",false)},
            {it.put("available",false)}, {it.put("selection",JSONArray())}, {it.put("selection",JSONArray().put(identity(2)).put(identity(2)))},
            {it.getJSONObject("main").put("object_key","wrong")}, {it.getJSONArray("choices").put(it.getJSONArray("choices").get(0))},
            {it.put("targets",JSONArray().put(target(4)).put(target(2)))}, {it.getJSONArray("targets").getJSONObject(0).put("status","skip")},
            {it.getJSONArray("targets").getJSONObject(0).put("charge_name","Orphan")}, {it.getJSONArray("targets").getJSONObject(0).put("item_id",0)},
            {it.getJSONArray("excluded").put(identity(2).put("reason","duplicate"))})
        mutate.forEach { change -> val value=source(); change(value); reject { ProjectedModuleChargeCodec.decode(value.toString()) } }
        reject { ProjectedModuleChargeCodec.decode(source().toString().replaceFirst("{","{\"version\":1,")) }
        val a=ProjectedModuleSelectionRow(2,key(2)); val b=ProjectedModuleSelectionRow(4,key(4))
        val op=BridgeOperation.SetProjectedModuleCharges("fit",a,listOf(b,a),BulkScope.SELECTED,900,listOf(a,b),listOf(a))
        for (bad in listOf(op.copy(selection=emptyList()),op.copy(selection=listOf(b)),op.copy(chargeId=0),op.copy(expectedTargets=listOf(b,a)),
            op.copy(expectedTargets=listOf(b)),op.copy(expectedChanges=listOf(b,a)),op.copy(expectedChanges=listOf(a.copy(objectKey=key(9)))),
            op.copy(expectedTargets=(0..1024).map { ProjectedModuleSelectionRow(it,key(it)) }))) reject { wire(bad) }
        val many=source().put("choices",JSONArray((1..8192).map { JSONObject().put("id",it).put("name","Choice $it") }))
        assertEquals(8192,ProjectedModuleChargeCodec.decode(many.toString()).choices.size)
        reject { ProjectedModuleChargeCodec.decode(many.put("choices",JSONArray((1..8193).map { JSONObject().put("id",it).put("name","Choice $it") })).toString()) }
    }
    @Test fun exactCaptureRejectsStaleRowsAndReadOnlyScopeCannotBecomeApplicable() {
        assertTrue(ProjectedModuleChargeCodec.failureMessage(java.util.concurrent.CompletionException(
            IllegalArgumentException("ValueError: Choose a reference module with compatible charges"))).contains("no charge or script choices"))
        assertFalse(ProjectedModuleChargeCodec.failureMessage(IllegalStateException("private trace")).contains("private trace"))
        assertTrue(ProjectedModuleChargeCodec.failureMessage(RuntimeException("Projected-charge compatibility budget: private detail")).contains("compatibility work budget"))
        for (prefix in listOf("Projected-drone evaluation budget:","Projected-drone capacitor evaluation budget:"))
            assertTrue(ProjectedModuleChargeCodec.failureMessage(RuntimeException(prefix+" private detail")).contains("evaluation budget"))
        val p=ProjectedModuleChargeCodec.decode(source().toString()); val a=row(2); val b=row(4,true)
        val d=ProjectedModuleDetails("fit",7,false,listOf(a,b)); val s=ProjectedModuleBulkSelection("fit",7,"Fit",listOf(b,a)); val c=ProjectedChargeCapture(d,s,a,BulkScope.SELECTED,900)
        for (bad in listOf(p.copy(fitId="other"),p.copy(revision=8),p.copy(main=p.selection[0]),p.copy(selection=p.selection.reversed()),p.copy(scope=BulkScope.SIMILAR),
            p.copy(chargeId=null),p.copy(targets=p.targets.map { it.copy(chargeId=1,chargeName="Other") }),p.copy(excluded=listOf(ProjectedChargeExcluded(p.main,"Wrong"))))) reject { ProjectedModuleChargeCodec.correlate(bad,c) }
        reject { ProjectedModuleChargeCodec.correlate(p,c.copy(main=a.copy())) }
        val legacy=row(0).copy(editable=false,unavailableReason="Legacy environment")
        val c2=c.copy(details=d.copy(modules=listOf(legacy,a,b)),scope=BulkScope.SIMILAR)
        val target=ProjectedChargeTarget(ProjectedChargeIdentity(0,key(0),100),legacy.name,null,null,ProjectedChargeStatus.CHANGE)
        val unavailable=p.copy(scope=BulkScope.SIMILAR,available=false,unavailableReason="Read-only legacy environment",targets=listOf(target)+p.targets)
        ProjectedModuleChargeCodec.correlate(unavailable,c2)
        reject { ProjectedModuleChargeCodec.correlate(unavailable.copy(available=true,unavailableReason=null),c2) }
        val excluded=p.copy(targets=listOf(p.targets[0]),excluded=listOf(ProjectedChargeExcluded(p.selection[0],"Not a compatible-set subset")))
        ProjectedModuleChargeCodec.correlate(excluded,c)
        // Incompatibility is server policy, not reconstructed from Kotlin's offered main choices.
        ProjectedModuleChargeCodec.correlate(p.copy(targets=p.targets.map { if(it.identity.index==2) it.copy(status=ProjectedChargeStatus.INCOMPATIBLE) else it }),c)
    }
}
