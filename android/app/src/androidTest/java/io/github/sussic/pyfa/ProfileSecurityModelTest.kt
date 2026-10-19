package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Actual shared profile model, held async boundaries; no substitute authority or numerical engine. */
@RunWith(AndroidJUnit4::class)
class ProfileSecurityModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private val id = "profile:" + "b".repeat(32)
    private data class Write(val context: OfflineContext, val op: String, val args: JSONObject, val anchor: String?, val future: CompletableFuture<OfflineFeatureResponse>)
    private inner class Harness {
        var current = OfflineContext("a".repeat(32), "c".repeat(64), 1)
        val all0 = OfflineProfile("builtin:all0", "All 0", true, null, emptyMap(), 0)
        val all5 = OfflineProfile("builtin:all5", "All 5", true, 5, emptyMap(), 0)
        var profile = OfflineProfile(id, "Pilot", false, 5, mapOf(1 to 0), 1,
            listOf(OfflineProfileImplant("d".repeat(32), 11, "Implant", 6, false)), SecurityNumber(2.75))
        var extra: OfflineProfile? = null
        val reads = mutableListOf<Pair<String?, CompletableFuture<OfflineFeatureState>>>()
        val writes = mutableListOf<Write>()
        var enqueueFailure = false
        val model = OfflineProfilesModel(featureContext = { current }, engineAvailable = { true }, read = { _, fit ->
            CompletableFuture<OfflineFeatureState>().also { reads += fit to it }
        }, mutate = { _, expected, operation, arguments, anchor ->
            if (enqueueFailure) throw IllegalArgumentException("Before enqueue")
            CompletableFuture<OfflineFeatureResponse>().also { writes += Write(expected, operation,
                OfflineFeatureCodec.parse(OfflineFeatureCodec.json(arguments)), anchor, it) }
        })
        fun state(anchor: String? = reads.lastOrNull()?.first) = OfflineFeatureState(current,
            listOfNotNull(all0, all5, profile, extra), emptyMap(), listOf(OfflineSkill(1, "Skill")), anchor,
            OfflineHistory(0, 0, 100, null, null))
        fun ready() {
            main { model.load(context, null) }
            main { reads.last().second.complete(state()) }
            main { model.selectProfile(id) }
            assertEquals(id, model.selectedProfile!!.id)
        }
        fun response(committed: Boolean = true) { writes.last().future.complete(OfflineFeatureResponse("request", true, committed, false, state(writes.last().anchor), null, null)) }
        fun reject(uncertain: Boolean = false, code: String = "response_size") {
            writes.last().future.complete(OfflineFeatureResponse("request", false, if (uncertain) null else false, uncertain, null, null, OfflineFeatureError(code, "Synthetic refusal")))
        }
    }
    @Test fun noFitSecuritySaveUsesScalarOnlyAndPreservesSkillsImplantsAndExplicitNullSaveAs() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.editSecurity("-6.25"); m.saveSecurity(context); m.saveSecurity(context) }
        val write = h.writes.single(); assertEquals("save_profile_security", write.op); assertNull(write.anchor)
        assertEquals(setOf("profile_id", "revision", "sec_status", "save_as"), write.args.keys().asSequence().toSet())
        assertTrue(write.args.isNull("save_as")); assertEquals("-6.25", OfflineFeatureCodec.json(write.args.get("sec_status")))
        val before = h.profile
        main { h.profile = before.copy(revision = 2, secStatus = SecurityNumber(-6.25)); h.current = h.current.copy(generation = 2); h.response() }
        assertFalse(m.securityDirty); assertEquals("-6.25", m.securityText); assertEquals(before.levels, m.selectedProfile!!.levels); assertEquals(before.implants, m.selectedProfile!!.implants)
    }
    @Test fun saveAsOfUnchangedDraftCreatesDetachedCompleteProfileWithoutAssigning() {
        val h = Harness(); h.ready(); val m = h.model; val source = h.profile
        main { m.name = "Copy"; m.saveSecurity(context, true) }
        assertEquals("Copy", h.writes.single().args.getString("save_as")); assertFalse(m.securityDirty)
        main {
            h.extra = source.copy(id = "profile:" + "e".repeat(32), name = "Copy", revision = 1,
                implants = source.implants.map { it.copy(implantId = "f".repeat(32)) })
            h.current = h.current.copy(generation = 2); h.response()
        }
        assertEquals(source, h.profile); assertEquals(h.extra, m.selectedProfile); assertEquals(source.levels, m.selectedProfile!!.levels)
        assertEquals(1, h.writes.size); assertEquals("save_profile_security", h.writes.single().op); assertTrue(m.state!!.bindings.isEmpty())
    }
    @Test fun skillDraftCannotBeSilentlyClearedBySecurityEditSaveAsOrSectionNavigation() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.selectSkill(1); m.editLevel(4); m.showSection(OfflineProfileSection.SECURITY); m.editSecurity("-6.25"); m.name = "Copy"; m.saveSecurity(context, true) }
        assertTrue(m.dirty); assertEquals(4, m.draftLevel); assertFalse(m.securityDirty); assertEquals("2.75", m.securityText); assertTrue(h.writes.isEmpty())
        main { m.revert(); m.editSecurity("-6.25") }; assertTrue(m.securityDirty); assertFalse(m.dirty)
    }
    @Test fun securityDraftBlocksOtherProfileMutationAndSurvivesNavigationUntilExplicitRevert() {
        val h = Harness(); h.ready(); val m = h.model
        main {
            m.selectSkill(1); m.editSecurity("-6.25"); m.selectProfile("builtin:all5"); m.editLevel(4); m.name = "Copy"; m.create(context)
            m.rename(context); m.requestDelete(); m.beginImplantAdd(); m.history(context, false); m.showSection(OfflineProfileSection.IMPLANTS)
        }
        assertEquals(id, m.profileId); assertFalse(m.dirty); assertTrue(m.securityDirty); assertNull(m.implantChoice); assertNull(m.deleteConfirmation); assertTrue(h.writes.isEmpty())
        main { m.close(); m.open(); m.load(context, null) }; main { h.reads.last().second.complete(h.state()) }
        assertEquals("-6.25", m.securityText); assertFalse(m.securityConflict)
        main { m.revertSecurity() }; assertFalse(m.securityDirty); assertEquals("2.75", m.securityText)
    }
    @Test fun builtinSecuritySaveAndSaveAsAreProtectedButCompleteDuplicateRemainsAvailable() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.selectProfile("builtin:all5"); m.editSecurity("-6.25"); m.name = "Copy all V"; m.saveSecurity(context); m.saveSecurity(context, true) }
        assertTrue(h.writes.isEmpty()); assertEquals("5.0", m.securityText); assertFalse(m.securityDirty)
        main { m.create(context) }; assertEquals("create_profile", h.writes.single().op); assertEquals("builtin:all5", h.writes.single().args.getString("source"))
    }
    @Test fun signedZeroSameValueSaveDoesNotLocallyRewriteRawAuthorityOrInventHistory() {
        val h = Harness(); h.profile = h.profile.copy(secStatus = SecurityNumber(0)); h.ready(); val m = h.model
        main { m.editSecurity("-0.0"); m.saveSecurity(context); h.response(false) }
        assertEquals("-0.0", OfflineFeatureCodec.json(h.writes.single().args.get("sec_status")))
        assertEquals(SecurityNumber(0), m.selectedProfile!!.secStatus); assertEquals("0", m.securityText); assertFalse(m.securityDirty); assertEquals(1L, m.state!!.context.generation)
    }
    @Test fun malformedAndFailedSecuritySavesKeepDraftAndNeverCommitOptimistically() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.editSecurity("5.01"); m.saveSecurity(context) }; assertTrue(h.writes.isEmpty()); assertEquals("5.01", m.securityText)
        main { m.editSecurity("-6.25"); h.enqueueFailure = true; m.saveSecurity(context) }; assertFalse(m.saving); assertFalse(m.reopenRequired)
        main { h.enqueueFailure = false; m.saveSecurity(context); h.reject() }
        assertTrue(m.securityDirty); assertEquals("-6.25", m.securityText); assertEquals(SecurityNumber(2.75), m.selectedProfile!!.secStatus); assertFalse(m.reopenRequired)
        main { m.saveSecurity(context) }; assertEquals(2, h.writes.size)
    }
    @Test fun staleRevisionKeepsSecurityTextAndRequiresRevertRatherThanRetargetingSave() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.editSecurity("-6.25"); h.profile = h.profile.copy(revision = 2, secStatus = SecurityNumber(4)); h.current = h.current.copy(generation = 2); m.load(context, null) }
        main { h.reads.last().second.complete(h.state()) }
        assertFalse(m.loading); assertEquals(2L, m.selectedProfile!!.revision)
        assertTrue(m.securityConflict); assertTrue(m.securityDirty); assertEquals("-6.25", m.securityText)
        main { m.name = "Valid stale copy"; m.saveSecurity(context, true) }
        assertTrue(m.securityConflict); assertTrue(m.securityDirty); assertEquals("-6.25", m.securityText); assertTrue(h.writes.isEmpty())
        main { m.revertSecurity() }; assertFalse(m.securityConflict); assertEquals("4", m.securityText)
    }
    @Test fun closedReadAndReopenedViewSerializeAndNeverAdoptOldFailure() {
        val h = Harness(); val m = h.model
        main { m.load(context, null); m.close(); m.open(); m.load(context, null) }
        assertEquals(1, h.reads.size)
        main { h.reads[0].second.completeExceptionally(IllegalStateException("Old")) }
        assertEquals(2, h.reads.size); assertTrue(m.loading); assertNull(m.error)
        main { h.reads[1].second.complete(h.state()) }; assertNotNull(m.state); assertFalse(m.loading)
    }
    @Test fun oldSaveAfterReopenCannotClearDraftOrSelectItsNewCopy() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.editSecurity("-6.25"); m.name = "Copy"; m.saveSecurity(context, true); m.close(); m.open(); m.load(context, null) }
        assertEquals(1, h.reads.size); assertTrue(m.saving)
        main { h.extra = h.profile.copy(id = "profile:" + "e".repeat(32), name = "Copy", secStatus = SecurityNumber(-6.25)); h.current = h.current.copy(generation = 2); h.response() }
        assertEquals(id, m.profileId); assertTrue(m.securityDirty); assertNull(m.message); assertEquals("-6.25", m.securityText)
        main { h.reads.last().second.complete(h.state()) }; assertEquals(id, m.profileId)
    }
    @Test fun uncertainSaveBlocksUntilReopenAndOldSessionFailureDoesNotPoisonNewSession() {
        val h = Harness(); h.ready(); val m = h.model
        main { m.editSecurity("-6.25"); m.saveSecurity(context); h.reject(true) }
        assertTrue(m.reopenRequired); assertTrue(m.securityDirty)
        main { m.saveSecurity(context); m.load(context, null) }; assertEquals(1, h.writes.size); assertEquals(1, h.reads.size)
        main { h.current = h.current.copy(sessionId = "e".repeat(32)); m.load(context, null) }
        main { h.reads.last().second.complete(h.state()) }; assertFalse(m.reopenRequired); assertTrue(m.securityConflict)
        main { m.revertSecurity(); m.editSecurity("-6.25"); m.saveSecurity(context); h.current = h.current.copy(sessionId = "f".repeat(32)); m.load(context, null) }
        main { h.writes.last().future.completeExceptionally(IllegalStateException("Old session")) }
        assertFalse(m.reopenRequired); assertTrue(m.securityDirty); assertTrue(m.loading)
    }
}
