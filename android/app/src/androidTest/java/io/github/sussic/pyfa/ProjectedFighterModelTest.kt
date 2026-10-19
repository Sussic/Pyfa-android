package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic immutable snapshots test UI ownership, not EOS numerical behavior. */
@RunWith(AndroidJUnit4::class)
class ProjectedFighterModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private val key = "a".repeat(32)
    private fun fit(id: String = "fit", revision: Long = 7) = FitSnapshot(id,revision,"Recipient","Rifter",
        emptyMap(),emptyList(),emptyMap(),emptyList(),emptyList(),emptyList())
    private fun row(index: Int = 0, objectKey: String = key) = ProjectedFighterRow(index,objectKey,100+index,"Projector",2,3,true,0.0,true,null)
    private fun details(revision: Long = 7, squadrons: List<ProjectedFighterRow> = listOf(row()), id: String = "fit") = ProjectedFighterDetails(id,revision,false,squadrons)
    private fun options(r: ProjectedFighterRow = row(), revision: Long = 7) = ProjectedFighterOptions("fit",revision,r.index,r.objectKey,r.itemId,
        listOf(FighterAbility(6435,"Web",true)),listOf(ProjectedFighterVariation(102,"Variation",true)))

    @Test fun retainedRangeRequiresExplicitReviewAndNeverTargetsDeletedReplacedOrOtherFitObjects() {
        var selected: EngineState = EngineState.Ready(fit())
        var response = details()
        var calls = 0
        val model = ProjectedFighterModel(engineState={selected}, read={_,_,_-> CompletableFuture.completedFuture(response)},
            dispatch={_,_,_-> calls++; CompletableFuture()})
        main { model.load(context,fit()) }
        val anchor = model.anchor(row())!!
        main { model.beginRange(anchor); model.changeDraft("0"); model.saveDraft(context) }
        assertEquals(0,calls); assertNull(model.draft); assertTrue(model.message!!.contains("unchanged"))
        main { model.beginRange(anchor); model.changeDraft("1.25") }
        val retained = model.draft
        for (unavailable in listOf(EngineState.Loading,EngineState.Empty(),EngineState.Failed("Unavailable"),
            EngineState.Ready(fit(),BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,"Restart")),EngineState.Ready(fit("other")))) {
            selected = unavailable
            main { model.saveDraft(context); model.remove(context,anchor) }
            assertSame(retained,model.draft); assertTrue(model.draftStale); assertFalse(model.available); assertEquals(0,calls)
        }
        selected = EngineState.Ready(fit(revision=8)); response = details(8,listOf(row().copy(rangeM=5000.0)))
        main { model.load(context,fit(revision=8)) }
        assertEquals("1.25",model.draft!!.text); assertTrue(model.draftStale); assertTrue(model.canReview)
        main { model.reviewDraft() }
        assertEquals("5.0",model.draft!!.text); assertFalse(model.draftStale); assertEquals(8L,model.draft!!.anchor.revision)
        main { model.changeDraft("NaN"); model.saveDraft(context) }
        assertEquals(0,calls); assertNotNull(model.error); assertEquals("NaN",model.draft!!.text)
        // Replacing the original object at the same position cannot rebase its draft.
        selected = EngineState.Ready(fit(revision=9)); response = details(9,listOf(row(objectKey="b".repeat(32))))
        main { model.load(context,fit(revision=9)); model.reviewDraft(); model.saveDraft(context) }
        assertTrue(model.draftStale); assertFalse(model.canReview); assertEquals(key,model.draft!!.anchor.row.objectKey)
        selected = EngineState.Ready(fit(revision=10)); response = details(10,emptyList())
        main { model.load(context,fit(revision=10)) }
        assertFalse(model.canReview); assertEquals("NaN",model.draft!!.text)
        main { model.discardDraft() }; assertNull(model.draft); assertEquals(0,calls)
    }

    @Test fun untouchedKilometreDisplayPreservesSubnormalAndInexactRawMetres() {
        for (raw in listOf(Double.MIN_VALUE,63.7)) {
            assertNotEquals(raw,(raw / 1000.0) * 1000.0)
            val r=row().copy(rangeM=raw)
            var calls=0
            val model=ProjectedFighterModel(engineState={EngineState.Ready(fit())},
                read={_,_,_-> CompletableFuture.completedFuture(details(squadrons=listOf(r)))},
                dispatch={_,_,_-> calls++; CompletableFuture()})
            main { model.load(context,fit()) }
            main { model.beginRange(model.anchor(r)!!); model.changeDraft(" ${model.draft!!.text} "); model.saveDraft(context) }
            assertEquals(0,calls); assertNull(model.draft); assertEquals(raw,model.currentDetails!!.squadrons.single().rangeM!!,0.0)
            assertTrue(model.message!!.contains("unchanged"))
        }
    }

    @Test fun lateReadAcrossUnavailableStateCanReloadAndExpectedReadFailureCanRetryWithoutMutation() {
        var selected: EngineState=EngineState.Ready(fit())
        val reads=mutableListOf<CompletableFuture<ProjectedFighterDetails>>()
        val choices=mutableListOf<CompletableFuture<ProjectedFighterOptions>>()
        val additions=mutableListOf<CompletableFuture<ProjectedFighterAddOptions>>()
        var writes=0
        val model=ProjectedFighterModel(engineState={selected},
            read={_,_,_-> CompletableFuture<ProjectedFighterDetails>().also(reads::add)},
            readOptions={_,_,_,_-> CompletableFuture<ProjectedFighterOptions>().also(choices::add)},
            readAdd={_,_,_,_-> CompletableFuture<ProjectedFighterAddOptions>().also(additions::add)},
            dispatch={_,_,_-> writes++; CompletableFuture()})
        main { model.load(context,fit()) }
        selected=EngineState.Loading
        main { reads.single().complete(details()) }
        assertNull(model.currentDetails); assertFalse(model.loading)
        selected=EngineState.Ready(fit())
        main { model.load(context,fit()) }
        assertEquals(2,reads.size)
        main { reads.last().completeExceptionally(IllegalArgumentException("Projected-drone evaluation budget: saved quantity")) }
        assertNotNull(model.error); assertNull(model.currentDetails); assertFalse(model.loading)
        assertTrue(model.error!!.startsWith("This configuration exceeds the incoming-projector evaluation budget."))
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
        main { additions.single().complete(ProjectedFighterAddOptions("fit",7,100,true,true,false,true,null)) }
        assertNull(model.currentAdd(100)); assertFalse(model.addLoading)
        selected=EngineState.Ready(fit())
        main { model.loadAdd(context,fit(),100) }
        assertEquals(2,additions.size)
        main { additions.last().complete(ProjectedFighterAddOptions("fit",7,100,true,true,false,true,null)) }
        assertTrue(model.currentAdd(100)!!.enabled); assertEquals(0,writes)
    }

    @Test fun staleListAndChoiceRepliesCannotCrossSelectionAndPendingEditCannotQueueTwice() {
        var selected: EngineState = EngineState.Ready(fit())
        val listReads = mutableListOf<CompletableFuture<ProjectedFighterDetails>>()
        val optionReads = mutableListOf<CompletableFuture<ProjectedFighterOptions>>()
        val addReads = mutableListOf<CompletableFuture<ProjectedFighterAddOptions>>()
        val pending = CompletableFuture<BridgeResponse>()
        var calls=0; var operation: BridgeOperation?=null
        val model = ProjectedFighterModel(engineState={selected},
            read={_,_,_-> CompletableFuture<ProjectedFighterDetails>().also(listReads::add)},
            readOptions={_,_,_,_-> CompletableFuture<ProjectedFighterOptions>().also(optionReads::add)},
            readAdd={_,_,_,_-> CompletableFuture<ProjectedFighterAddOptions>().also(addReads::add)},
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
        main { model.active(context,model.anchor(row())!!,current,false) }
        assertEquals(0,calls)
        main { model.variation(context,a,current,current.variations.single().copy(id=999)); model.ability(context,a,current,current.abilities.single().copy(effectId=999)) }
        assertEquals(0,calls)
        main { model.active(context,a,current,false); model.remove(context,a) }
        assertTrue(model.editing); assertEquals(1,calls)
        assertEquals(BridgeOperation.SetProjectedFighterActive("fit",1,second.objectKey,false),operation)
        selected=EngineState.Ready(fit("other"))
        main { pending.completeExceptionally(IllegalStateException("late rejected edit")) }
        assertFalse(model.editing); assertNull(model.error); assertNull(model.message)
        selected=EngineState.Ready(fit(revision=8))
        main { model.loadAdd(context,fit(revision=8),100); model.loadAdd(context,fit(revision=8),101) }
        main { addReads[0].complete(ProjectedFighterAddOptions("fit",8,100,true,true,false,true,null)) }
        assertTrue(model.addLoading); assertNull(model.currentAdd(100)); assertNull(model.currentAdd(101))
        main { addReads[1].complete(ProjectedFighterAddOptions("other",8,101,true,true,false,true,null)) }
        assertFalse(model.addLoading); assertNull(model.currentAdd(101)); assertNotNull(model.addError)
    }

    @Test fun zeroAlwaysRemovesMaximumUsesSourceValueAndAbilitiesRemainIndependentOfInactiveSquadron() {
        for (current in listOf(0,2)) {
            val r=row().copy(amount=current); val sent=mutableListOf<BridgeOperation>()
            val model=ProjectedFighterModel(engineState={EngineState.Ready(fit())},
                read={_,_,_-> CompletableFuture.completedFuture(details(squadrons=listOf(r)))},
                dispatch={_,op,_-> sent.add(op); CompletableFuture()})
            main { model.load(context,fit()) }
            main { model.beginAmount(model.anchor(r)!!); model.changeDraft("0"); model.saveDraft(context); model.saveDraft(context) }
            assertEquals(listOf(BridgeOperation.SetProjectedFighterAmount("fit",0,key,0)),sent)
        }
        val r=row().copy(active=false); val pending=CompletableFuture<BridgeResponse>(); val sent=mutableListOf<BridgeOperation>()
        val model=ProjectedFighterModel(engineState={EngineState.Ready(fit())},
            read={_,_,_-> CompletableFuture.completedFuture(details(squadrons=listOf(r)))},
            readOptions={_,_,_,_-> CompletableFuture.completedFuture(options(r))},
            dispatch={_,op,revisions-> assertEquals(mapOf("fit" to 7L),revisions); sent.add(op); pending})
        main { model.load(context,fit()) }; val a=model.anchor(r)!!
        for (bad in listOf("-1","1.5","4","2147483648","")) {
            main { model.beginAmount(a); model.changeDraft(bad); model.saveDraft(context) }
            assertTrue(sent.isEmpty()); assertNotNull(model.error)
            main { model.discardDraft() }
        }
        main { model.beginAmount(a); model.maximumAmount() }
        assertEquals("3",model.draft!!.text)
        main { model.saveDraft(context); model.remove(context,a) }
        assertEquals(listOf(BridgeOperation.SetProjectedFighterAmount("fit",0,key,3)),sent)
        main { pending.complete(BridgeResponse("request","session",BridgeStatus.ERROR,emptyList(),
            BridgeError(BridgeErrorCode.INVALID_EDIT,"Projected-drone evaluation budget: prospective configuration"))) }
        assertFalse(model.editing); assertEquals("3",model.draft!!.text); assertEquals(r,model.currentDetails!!.squadrons.single())
        main { model.discardDraft() }
        var operation: BridgeOperation?=null
        val other=ProjectedFighterModel(engineState={EngineState.Ready(fit())},
            read={_,_,_-> CompletableFuture.completedFuture(details(squadrons=listOf(r)))},
            readOptions={_,_,_,_-> CompletableFuture.completedFuture(options(r))}, dispatch={_,op,_-> operation=op; CompletableFuture()})
        main { other.load(context,fit()) }; main { other.select(context,r) }
        main { other.ability(context,other.anchor(r)!!,other.currentOptions!!,other.currentOptions!!.abilities.single()) }
        assertEquals(BridgeOperation.ToggleProjectedFighterAbility("fit",0,key,6435),operation)
        assertFalse(other.currentDetails!!.squadrons.single().active)
    }
}
