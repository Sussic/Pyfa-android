package io.github.sussic.pyfa

import androidx.lifecycle.ViewModelStore
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Held futures drive actual editor ownership. These methods do not execute EOS or prove device behavior. */
@RunWith(AndroidJUnit4::class)
class PilotSecurityModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private val id = "f".repeat(32)
    private val profileId = "profile:" + "b".repeat(32)
    private data class Read(val owner: PilotSecurityOwner, val future: CompletableFuture<PilotSecurityDetails>)
    private data class Write(val expected: OfflineContext, val operation: String, val args: JSONObject, val anchor: String?, val future: CompletableFuture<OfflineFeatureResponse>)
    private inner class Harness {
        var current = OfflineContext("a".repeat(32), "c".repeat(64), 1)
        var fit: FitSnapshot? = FitSnapshot(id, 7, "Fit", "Pacifier", emptyMap(), emptyList(), emptyMap(), emptyList(), emptyList(), emptyList())
        var profile = OfflineProfile(profileId, "Pilot", false, 5, emptyMap(), 1, secStatus = SecurityNumber(2.75))
        var raw: SecurityNumber? = null
        val reads = mutableListOf<Read>(); val writes = mutableListOf<Write>()
        var failEnqueue = false
        fun state() = OfflineFeatureState(current, listOf(profile), fit?.let { mapOf(it.id to OfflineBinding(profileId, 3, it.revision, ImplantLocation.FIT)) }.orEmpty(),
            listOf(OfflineSkill(1, "Skill")), fit?.id, OfflineHistory(0, 0, 100, null, null))
        val model = PilotSecurityModel(published = { state() }, activeFit = { fit }, read = { _, _ ->
            CompletableFuture<PilotSecurityDetails>().also { reads += Read(PilotSecurityOwner.capture(state(), checkNotNull(fit)), it) }
        }, mutate = { _, expected, operation, args, anchor ->
            if (failEnqueue) throw IllegalArgumentException("Before enqueue")
            CompletableFuture<OfflineFeatureResponse>().also {
                writes += Write(expected, operation, OfflineFeatureCodec.parse(OfflineFeatureCodec.json(args)), anchor, it)
            }
        })
        fun details(index: Int = reads.lastIndex): PilotSecurityDetails {
            val owner = reads[index].owner; val eligible = owner.hullName == "Pacifier"
            return PilotSecurityDetails(owner.context, owner.fitId, owner.fitRevision, if (eligible) 44993 else 587, owner.hullName, eligible,
                if (eligible) null else "unsupported_hull", PilotSecurityProfile(owner.profile.id, owner.profile.name, owner.profile.revision,
                    owner.binding.revision, owner.profile.readonly, owner.profile.secStatus), raw,
                if (raw == null) PilotSecuritySource.CHARACTER else PilotSecuritySource.EXPLICIT, raw ?: owner.profile.secStatus,
                if (eligible) PilotSecurityCodec.presets else emptyList())
        }
        fun load() { model.open(); model.load(context) }
        fun ready() { main { load() }; main { reads.last().future.complete(details()) } }
        fun success(index: Int = writes.lastIndex, committed: Boolean = true) {
            if (committed) { current = current.copy(generation = current.generation + 1); fit = fit!!.copy(revision = fit!!.revision + 1) }
            raw = PilotSecurityCodec.nullable(writes[index].args.get("pilot"))
            writes[index].future.complete(OfflineFeatureResponse("request", true, committed, false, state(), null, null))
        }
        fun refusal(code: String = "response_size", uncertain: Boolean = false, index: Int = writes.lastIndex) {
            writes[index].future.complete(OfflineFeatureResponse("request", false, if (uncertain) null else false, uncertain,
                null, null, OfflineFeatureError(code, "Synthetic refusal")))
        }
    }
    @Test fun explicitZeroFromCharacterIsOneGuardedWriteAndRereadsAfterPublication() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.choose(PilotSecurityChoice.PRESET, 0); m.save(context); m.save(context) }
        assertEquals(1, h.writes.size); val write = h.writes.single()
        assertEquals("set_pilot_security", write.operation); assertEquals(id, write.anchor)
        assertEquals(0L, OfflineFeatureCodec.integer(write.args.get("pilot"))); assertEquals(7L, OfflineFeatureCodec.integer(write.args.get("fit_revision")))
        main { h.success() }; assertNull(m.details); assertTrue(m.loading); assertFalse(m.dirty)
        main { h.reads.last().future.complete(h.details()) }
        assertEquals(PilotSecuritySource.EXPLICIT, m.currentDetails!!.source); assertEquals(PilotSecurityChoice.PRESET, m.choice)
    }
    @Test fun customTextUsesDecimalAndMalformedInputNeverDispatchesOrDiscardsDraft() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.edit("1,2"); m.save(context) }; assertTrue(h.writes.isEmpty()); assertEquals("1,2", m.text); assertFalse(m.inputValid)
        main { m.edit(" -0.0 "); m.save(context) }
        assertEquals("-0.0", OfflineFeatureCodec.json(h.writes.single().args.get("pilot")))
        assertEquals(" -0.0 ", m.text)
    }
    @Test fun characterSubmissionIsNullAndNoOpStillReloadsWithoutInventingHistory() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.choose(PilotSecurityChoice.CHARACTER); m.save(context) }
        assertTrue(h.writes.single().args.isNull("pilot"))
        main { h.success(committed = false) }; assertEquals(1L, h.current.generation); assertTrue(m.loading)
        main { h.reads.last().future.complete(h.details()) }; assertNull(m.currentDetails!!.pilot); assertFalse(m.dirty)
    }
    @Test fun unsupportedHullExposesTruthfulSourceButCannotSubmitEvenEqualNoOp() {
        val h = Harness(); h.fit = h.fit!!.copy(ship = "Rifter"); h.ready(); val m = h.model
        assertEquals(SecurityNumber(2.75), m.currentDetails!!.effective); assertFalse(m.available)
        main { m.choose(PilotSecurityChoice.CHARACTER); m.edit("0"); m.save(context) }
        assertTrue(h.writes.isEmpty()); assertFalse(m.dirty)
    }
    @Test fun closeAndReopenRetainPhysicalReadOwnerAndRejectOldFailureBeforeNewView() {
        val h = Harness(); val m = h.model
        main { h.load(); m.close(); h.load() }
        assertEquals(1, h.reads.size); assertTrue(m.loading)
        main { h.reads[0].future.completeExceptionally(IllegalStateException("Old read")) }
        assertEquals(2, h.reads.size); assertTrue(m.loading); assertNull(m.error); assertNull(m.details)
        main { h.reads[1].future.complete(h.details(1)) }; assertNotNull(m.currentDetails)
    }
    @Test fun queuedNewerReadNeverAdoptsOldFitContextOrLateSuccess() {
        val h = Harness(); val m = h.model
        main { h.load(); h.fit = h.fit!!.copy(id = "e".repeat(32)); h.current = h.current.copy(generation = 2); m.load(context) }
        assertEquals(1, h.reads.size)
        main { h.reads[0].future.complete(h.details(0)) }
        assertEquals(2, h.reads.size); assertNull(m.details); assertTrue(m.loading)
        main { h.reads[1].future.complete(h.details(1)) }
        assertEquals("e".repeat(32), m.currentDetails!!.fitId); assertNull(m.error)
    }
    @Test fun staleDraftCannotFollowBindingRevisionOrFitSwitchAndRevertReviewsNewOwner() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.edit("-6.25"); h.profile = h.profile.copy(revision = 2); h.current = h.current.copy(generation = 2); m.load(context) }
        main { h.reads.last().future.complete(h.details()) }
        assertTrue(m.conflict); assertTrue(m.dirty); assertEquals("-6.25", m.text)
        main { m.save(context) }; assertTrue(h.writes.isEmpty())
        main { m.revert() }; assertFalse(m.conflict); assertFalse(m.dirty); assertTrue(m.available)
    }
    @Test fun oldSaveFailureAfterReopenCannotPublishErrorOrClearRetainedDraft() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.edit("-6.25"); m.save(context); m.close(); h.load() }
        assertEquals(1, h.reads.size); assertTrue(m.saving)
        main { h.refusal() }
        assertEquals(2, h.reads.size); assertNull(m.error); assertTrue(m.dirty); assertEquals("-6.25", m.text)
        main { h.reads.last().future.complete(h.details()) }; assertTrue(m.available)
    }
    @Test fun oldSuccessfulSaveCannotClearReopenedDraftAndMustReviewItsNewRevision() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.edit("-6.25"); m.save(context); m.close(); h.load(); h.success() }
        assertTrue(m.dirty); assertNull(m.message); assertEquals("-6.25", m.text)
        main { h.reads.last().future.complete(h.details()) }
        assertTrue(m.conflict); assertEquals(SecurityNumber(-6.25), m.currentDetails!!.pilot)
    }
    @Test fun definiteRefusalAndPreEnqueueFailurePreserveDraftAndAllowExplicitRecovery() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.edit("-6.25"); h.failEnqueue = true; m.save(context) }
        assertTrue(m.dirty); assertFalse(m.saving); assertFalse(m.reopenRequired); assertTrue(h.writes.isEmpty())
        main { h.failEnqueue = false; m.save(context); h.refusal() }
        assertEquals("-6.25", m.text); assertTrue(m.available); assertFalse(m.reopenRequired)
        main { m.save(context) }; assertEquals(2, h.writes.size)
    }
    @Test fun uncertainSaveBlocksAllDispatchUntilAnotherSessionWithoutAutomaticReplay() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.edit("-6.25"); m.save(context); h.refusal("reopen_required", true) }
        assertTrue(m.reopenRequired); assertTrue(m.dirty); assertFalse(m.available)
        main { m.save(context); m.load(context, true) }; assertEquals(1, h.writes.size); assertEquals(1, h.reads.size)
        main { h.current = h.current.copy(sessionId = "d".repeat(32)); m.load(context, true) }
        main { h.reads.last().future.complete(h.details()) }
        assertFalse(m.reopenRequired); assertTrue(m.conflict); assertEquals("-6.25", m.text)
    }
    @Test fun clearedEditorCannotAdoptAReadOrMutationCompletion() {
        val h = Harness(); val m = h.model
        main { h.load(); val store = ViewModelStore(); store.put("pilot", m); store.clear() }
        main { h.reads[0].future.complete(h.details(0)) }; assertNull(m.details); assertNull(m.error); assertFalse(m.available)
    }
}
