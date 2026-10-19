package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic immutable snapshots test UI ownership, not EOS numerical behavior. */
@RunWith(AndroidJUnit4::class)
class ProjectedModuleModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private val key = "a".repeat(32)
    private fun fit(id: String = "fit", revision: Long = 7) = FitSnapshot(id,revision,"Recipient","Rifter",
        emptyMap(),emptyList(),emptyMap(),emptyList(),emptyList(),emptyList())
    private fun row(index: Int = 0, objectKey: String = key) = ProjectedModuleRow(index,objectKey,100,"Projector",ModuleState.ACTIVE,null,null,0.0,true,null)
    private fun details(revision: Long = 7, modules: List<ProjectedModuleRow> = listOf(row()), id: String = "fit") = ProjectedModuleDetails(id,revision,false,modules)
    private fun options(r: ProjectedModuleRow = row(), revision: Long = 7) = ProjectedModuleOptions("fit",revision,r.index,r.objectKey,r.itemId,
        listOf(ProjectedModuleAction(ProjectedModuleStateAction.INACTIVE,"Inactive",true)),
        listOf(ProjectedModuleCharge(200,"Script")),listOf(ProjectedModuleVariation(101,"Variation",true)),null)

    @Test fun retainedRangeRequiresExplicitReviewAndNeverTargetsDeletedReplacedOrOtherFitObjects() {
        var selected: EngineState = EngineState.Ready(fit())
        var response = details()
        var calls = 0
        val model = ProjectedModuleModel(engineState={selected}, read={_,_,_-> CompletableFuture.completedFuture(response)},
            dispatch={_,_,_-> calls++; CompletableFuture()})
        main { model.load(context,fit()) }
        val anchor = model.anchor(row())!!
        main { model.beginRange(anchor); model.changeRange("0"); model.saveRange(context) }
        assertEquals(0,calls); assertNull(model.draft); assertTrue(model.message!!.contains("unchanged"))
        main { model.beginRange(anchor); model.changeRange("1.25") }
        val retained = model.draft
        for (unavailable in listOf(EngineState.Loading,EngineState.Empty(),EngineState.Failed("Unavailable"),
            EngineState.Ready(fit(),BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,"Restart")),EngineState.Ready(fit("other")))) {
            selected = unavailable
            main { model.saveRange(context); model.remove(context,anchor) }
            assertSame(retained,model.draft); assertTrue(model.draftStale); assertFalse(model.available); assertEquals(0,calls)
        }
        selected = EngineState.Ready(fit(revision=8)); response = details(8,listOf(row().copy(rangeM=5000.0)))
        main { model.load(context,fit(revision=8)) }
        assertEquals("1.25",model.draft!!.text); assertTrue(model.draftStale); assertTrue(model.canReview)
        main { model.reviewRange() }
        assertEquals("5.0",model.draft!!.text); assertFalse(model.draftStale); assertEquals(8L,model.draft!!.anchor.revision)
        main { model.changeRange("NaN"); model.saveRange(context) }
        assertEquals(0,calls); assertNotNull(model.error); assertEquals("NaN",model.draft!!.text)
        // Replacing the original object at the same position cannot rebase its draft.
        selected = EngineState.Ready(fit(revision=9)); response = details(9,listOf(row(objectKey="b".repeat(32))))
        main { model.load(context,fit(revision=9)); model.reviewRange(); model.saveRange(context) }
        assertTrue(model.draftStale); assertFalse(model.canReview); assertEquals(key,model.draft!!.anchor.row.objectKey)
        selected = EngineState.Ready(fit(revision=10)); response = details(10,emptyList())
        main { model.load(context,fit(revision=10)) }
        assertFalse(model.canReview); assertEquals("NaN",model.draft!!.text)
        main { model.discardRange() }; assertNull(model.draft); assertEquals(0,calls)
    }

    @Test fun untouchedKilometreDisplayPreservesSubnormalAndInexactRawMetres() {
        for (raw in listOf(Double.MIN_VALUE,63.7)) {
            assertNotEquals(raw,(raw / 1000.0) * 1000.0)
            val r=row().copy(rangeM=raw)
            var calls=0
            val model=ProjectedModuleModel(engineState={EngineState.Ready(fit())},
                read={_,_,_-> CompletableFuture.completedFuture(details(modules=listOf(r)))},
                dispatch={_,_,_-> calls++; CompletableFuture()})
            main { model.load(context,fit()) }
            main { model.beginRange(model.anchor(r)!!); model.changeRange(" ${model.draft!!.text} "); model.saveRange(context) }
            assertEquals(0,calls); assertNull(model.draft); assertEquals(raw,model.currentDetails!!.modules.single().rangeM!!,0.0)
            assertTrue(model.message!!.contains("unchanged"))
        }
    }

    @Test fun lateReadAcrossUnavailableStateCanReloadAndExpectedReadFailureCanRetryWithoutMutation() {
        var selected: EngineState=EngineState.Ready(fit())
        val reads=mutableListOf<CompletableFuture<ProjectedModuleDetails>>()
        val choices=mutableListOf<CompletableFuture<ProjectedModuleOptions>>()
        val additions=mutableListOf<CompletableFuture<ProjectedModuleAddOptions>>()
        var writes=0
        val model=ProjectedModuleModel(engineState={selected},
            read={_,_,_-> CompletableFuture<ProjectedModuleDetails>().also(reads::add)},
            readOptions={_,_,_,_-> CompletableFuture<ProjectedModuleOptions>().also(choices::add)},
            readAdd={_,_,_,_-> CompletableFuture<ProjectedModuleAddOptions>().also(additions::add)},
            dispatch={_,_,_-> writes++; CompletableFuture()})
        main { model.load(context,fit()) }
        selected=EngineState.Loading
        main { reads.single().complete(details()) }
        assertNull(model.currentDetails); assertFalse(model.loading)
        selected=EngineState.Ready(fit())
        main { model.load(context,fit()) }
        assertEquals(2,reads.size)
        main { reads.last().completeExceptionally(IllegalArgumentException("Too many projected modules")) }
        assertNotNull(model.error); assertNull(model.currentDetails); assertFalse(model.loading)
        main { model.load(context,fit(),true) }
        main { reads.last().complete(details()) }
        assertNull(model.error); assertNotNull(model.currentDetails)
        main { model.select(context,row()) }
        main { choices.last().completeExceptionally(IllegalArgumentException("Choose an editable projected module")) }
        assertNotNull(model.optionsError); assertNull(model.currentOptions); assertFalse(model.optionsLoading)
        main { model.select(context,row()) }
        main { choices.last().complete(options()) }
        assertNull(model.optionsError); assertNotNull(model.currentOptions); assertEquals(0,writes)
        main { model.loadAdd(context,fit(),100) }
        selected=EngineState.Ready(fit("other"))
        main { additions.single().complete(ProjectedModuleAddOptions("fit",7,100,true,true,false,true,null)) }
        assertNull(model.currentAdd(100)); assertFalse(model.addLoading)
        selected=EngineState.Ready(fit())
        main { model.loadAdd(context,fit(),100) }
        assertEquals(2,additions.size)
        main { additions.last().complete(ProjectedModuleAddOptions("fit",7,100,true,true,false,true,null)) }
        assertTrue(model.currentAdd(100)!!.enabled); assertEquals(0,writes)
    }

    @Test fun staleListAndChoiceRepliesCannotCrossSelectionAndPendingEditCannotQueueTwice() {
        var selected: EngineState = EngineState.Ready(fit())
        val listReads = mutableListOf<CompletableFuture<ProjectedModuleDetails>>()
        val optionReads = mutableListOf<CompletableFuture<ProjectedModuleOptions>>()
        val addReads = mutableListOf<CompletableFuture<ProjectedModuleAddOptions>>()
        val pending = CompletableFuture<BridgeResponse>()
        var calls=0; var operation: BridgeOperation?=null
        val model = ProjectedModuleModel(engineState={selected},
            read={_,_,_-> CompletableFuture<ProjectedModuleDetails>().also(listReads::add)},
            readOptions={_,_,_,_-> CompletableFuture<ProjectedModuleOptions>().also(optionReads::add)},
            readAdd={_,_,_,_-> CompletableFuture<ProjectedModuleAddOptions>().also(addReads::add)},
            dispatch={_,op,revisions-> assertEquals(mapOf("fit" to 8L),revisions); calls++; operation=op; pending})
        main { model.load(context,fit()) }
        selected=EngineState.Ready(fit(revision=8))
        main { model.load(context,fit(revision=8)); listReads[0].complete(details()) }
        assertTrue(model.loading); assertNull(model.currentDetails)
        val second=row(1,"b".repeat(32))
        main { listReads[1].complete(details(8,listOf(row(),second))) }
        assertEquals(8L,model.currentDetails!!.revision)
        main { model.select(context,row()); model.select(context,second) }
        main { optionReads[0].complete(options(revision=8)) }
        assertNull(model.currentOptions); assertTrue(model.optionsLoading)
        main { optionReads[1].complete(options(second,8)) }
        val current = model.currentOptions!!; val a=model.anchor(second)!!
        // A valid option object from another current row still must not address this row.
        main { model.state(context,model.anchor(row())!!,current,current.stateActions.single()) }
        assertEquals(0,calls)
        main { model.variation(context,a,current,current.variations.single().copy(id=999)) }
        assertEquals(0,calls)
        main { model.state(context,a,current,current.stateActions.single()); model.remove(context,a) }
        assertTrue(model.editing); assertEquals(1,calls)
        assertEquals(BridgeOperation.SetProjectedModuleState("fit",1,second.objectKey,ProjectedModuleStateAction.INACTIVE),operation)
        selected=EngineState.Ready(fit("other"))
        main { pending.completeExceptionally(IllegalStateException("late rejected edit")) }
        assertFalse(model.editing); assertNull(model.error); assertNull(model.message)
        selected=EngineState.Ready(fit(revision=8))
        main { model.loadAdd(context,fit(revision=8),100); model.loadAdd(context,fit(revision=8),101) }
        main { addReads[0].complete(ProjectedModuleAddOptions("fit",8,100,true,true,false,true,null)) }
        assertTrue(model.addLoading); assertNull(model.currentAdd(100)); assertNull(model.currentAdd(101))
        main { addReads[1].complete(ProjectedModuleAddOptions("other",8,101,true,true,false,true,null)) }
        assertFalse(model.addLoading); assertNull(model.currentAdd(101)); assertNotNull(model.addError)
    }
}
