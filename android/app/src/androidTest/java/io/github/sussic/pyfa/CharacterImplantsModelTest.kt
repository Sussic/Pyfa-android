package io.github.sussic.pyfa

import androidx.lifecycle.ViewModelStore
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Held callbacks exercise the actual profile model reachable from Skills / Implants. No EOS substitute. */
@RunWith(AndroidJUnit4::class)
class CharacterImplantsModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private val profileId = "profile:" + "b".repeat(32)
    private val firstFit = "f".repeat(32)
    private val secondFit = "e".repeat(32)
    private val nav = CharacterImplantItem(11, "Navigation", 6)
    private val improved = CharacterImplantItem(12, "Improved navigation", 6)
    private val auroral = CharacterImplantItem(79, "Auroral", 79)
    private fun row(item: CharacterImplantItem = nav, id: String = "c".repeat(32), active: Boolean = false) =
        OfflineProfileImplant(id, item.itemId, item.name, item.slot, active)
    private data class Read(val fit: String?, val context: OfflineContext, val future: CompletableFuture<OfflineFeatureState>)
    private data class Write(val context: OfflineContext, val operation: String, val args: JSONObject, val fit: String?, val future: CompletableFuture<OfflineFeatureResponse>)
    private inner class Harness {
        var current = OfflineContext("a".repeat(32), "d".repeat(64), 1)
        var ready = true
        var throwBeforeEnqueue = false
        val reads = mutableListOf<Read>()
        val writes = mutableListOf<Write>()
        val all0 = OfflineProfile("builtin:all0", "All 0", true, null, emptyMap(), 0)
        val all5 = OfflineProfile("builtin:all5", "All 5", true, 5, emptyMap(), 0)
        var profile = OfflineProfile(profileId, "Pilot", false, 5, emptyMap(), 3)
        var bindings = emptyMap<String, OfflineBinding>()
        val model = OfflineProfilesModel(featureContext = { current }, engineAvailable = { ready }, read = { _, fit ->
            CompletableFuture<OfflineFeatureState>().also { reads += Read(fit, current, it) }
        }, mutate = { _, before, operation, args, fit ->
            if (throwBeforeEnqueue) throw IllegalArgumentException("Synthetic enqueue validation failure")
            CompletableFuture<OfflineFeatureResponse>().also { writes += Write(before, operation, JSONObject(OfflineFeatureCodec.json(args)), fit, it) }
        })
        fun state(fit: String? = reads.lastOrNull()?.fit, ctx: OfflineContext = current) = OfflineFeatureState(ctx,
            listOf(all0, all5, profile), bindings, listOf(OfflineSkill(1, "Skill")), fit, OfflineHistory(0, 0, 100, null, null))
        fun load(fit: String? = null) {
            main { model.load(context, fit) }; main { reads.last().future.complete(state(fit)) }; main { model.selectProfile(profileId) }
        }
        fun complete(value: OfflineFeatureState = state(writes.last().fit), index: Int = writes.lastIndex) {
            writes[index].future.complete(OfflineFeatureResponse("request", true, true, false, value, null, null))
        }
        fun fail(uncertain: Boolean = false, code: String = "conflict") {
            writes.last().future.complete(OfflineFeatureResponse("request", false, if (uncertain) null else false, uncertain,
                null, null, OfflineFeatureError(code, "Synthetic rejection")))
        }
    }
    @Test fun noFitAddUsesExplicitProfileAndOneOwnerForRapidRepeatedTaps() {
        val h = Harness(); h.load(); val m = h.model
        main { m.showSection(OfflineProfileSection.IMPLANTS); m.beginImplantAdd(); m.chooseImplant(context, auroral); m.chooseImplant(context, auroral); m.closeImplantPicker() }
        assertEquals(1, h.writes.size); assertTrue(m.saving); assertNotNull(m.implantChoice)
        val request = h.writes.single()
        assertNull(request.fit); assertEquals("add_profile_implant", request.operation)
        assertEquals(profileId, request.args.getString("profile_id")); assertEquals(3, request.args.getInt("revision"))
        assertEquals(79, request.args.getInt("item_id")); assertTrue(request.args.isNull("replace_implant_id"))
        main { h.current = h.current.copy(generation = 2); h.profile = h.profile.copy(revision = 4, implants = listOf(row(auroral, active = true))); h.complete() }
        assertFalse(m.saving); assertNull(m.implantChoice); assertEquals(79, m.selectedProfile!!.implants.single().slot)
    }
    @Test fun sameAndDifferentItemReplacementRequireCapturedOccupantAndCancelDoesNothing() {
        val h = Harness(); h.profile = h.profile.copy(implants = listOf(row())); h.load(); val m = h.model
        main { m.beginImplantAdd(); m.chooseImplant(context, nav) }
        assertEquals(0, h.writes.size); assertTrue(m.implantReplacementCurrent)
        assertEquals("c".repeat(32), m.implantReplacement!!.occupant.implantId)
        main { m.cancelImplantReplacement(); m.chooseImplant(context, improved); m.confirmImplantReplacement(context); m.confirmImplantReplacement(context) }
        assertEquals(1, h.writes.size); assertEquals(12, h.writes.single().args.getInt("item_id"))
        assertEquals("c".repeat(32), h.writes.single().args.getString("replace_implant_id"))
    }
    @Test fun staleReplacementKeepsSnapshotButCannotSubmitAfterAnyContextChange() {
        val h = Harness(); h.profile = h.profile.copy(implants = listOf(row())); h.load(); val m = h.model
        main { m.beginImplantAdd(); m.chooseImplant(context, improved); h.current = h.current.copy(generation = 2); m.confirmImplantReplacement(context) }
        assertFalse(m.implantReplacementCurrent); assertTrue(h.writes.isEmpty()); assertNotNull(m.implantReplacement)
        main { m.cancelImplantReplacement(); m.closeImplantPicker() }; assertNull(m.implantChoice)
    }
    @Test fun sourceProfileRemainsExplicitAcrossFitNavigationAndPickerCannotFollowNewProfile() {
        val h = Harness(); h.bindings = mapOf(firstFit to OfflineBinding(profileId, 1, 1, ImplantLocation.FIT), secondFit to OfflineBinding("builtin:all5", 1, 1, ImplantLocation.CHARACTER))
        h.load(firstFit); val m = h.model
        main { m.beginImplantAdd(); m.load(context, secondFit) }; main { h.reads.last().future.complete(h.state(secondFit)) }
        assertEquals(profileId, m.profileId)
        main { m.chooseImplant(context, nav) }
        assertEquals(profileId, h.writes.single().args.getString("profile_id")); assertEquals(secondFit, h.writes.single().fit)
    }
    @Test fun dirtySkillDraftSurvivesSectionAndNavigationWhileAllImplantCopyAssignActionsBlock() {
        val h = Harness(); h.profile = h.profile.copy(implants = listOf(row())); h.load(); val m = h.model
        main { m.selectSkill(1); m.editLevel(0); m.showSection(OfflineProfileSection.IMPLANTS); m.beginImplantAdd(); m.name = "Copy"; m.create(context); m.assign(context); m.removeImplant(context, m.selectedProfile!!, m.selectedProfile!!.implants.first()); m.requestDelete(); m.openImplants("builtin:all5") }
        assertTrue(m.dirty); assertEquals(0, m.draftLevel); assertEquals(profileId, m.profileId); assertTrue(h.writes.isEmpty()); assertNull(m.implantChoice); assertNull(m.deleteConfirmation)
        main { m.load(context, null) }; main { h.reads.last().future.complete(h.state()) }
        assertTrue(m.dirty); assertFalse(m.conflict); assertEquals(OfflineProfileSection.IMPLANTS, m.section)
        main { m.revert(); m.beginImplantAdd() }; assertFalse(m.dirty); assertNotNull(m.implantChoice)
    }
    @Test fun skillSaveRetainsActualOwnershipAcrossOwnPublicationRefresh() {
        val h = Harness(); h.load(); val m = h.model
        main { m.selectSkill(1); m.editLevel(0); m.save(context); m.save(context); m.revert() }
        assertEquals(1, h.writes.size); assertTrue(m.dirty); assertTrue(m.saving)
        main { h.current = h.current.copy(generation = 2); h.profile = h.profile.copy(revision = 4, levels = mapOf(1 to 0)); m.load(context, null) }
        assertEquals(1, h.reads.size); assertTrue(m.saving)
        main { h.complete() }
        assertFalse(m.dirty); assertTrue(m.loading); assertEquals(2, h.reads.size)
        main { h.reads.last().future.complete(h.state()) }
        assertFalse(m.loading); assertEquals(0, m.draftLevel)
    }
    @Test fun builtinsBlockMutationButCompleteDuplicateUsesExplicitSource() {
        val h = Harness(); h.load(); val m = h.model
        main { m.selectProfile("builtin:all0"); m.beginImplantAdd(); m.requestDelete(); m.name = "Copy All 0"; m.rename(context) }
        assertNull(m.implantChoice); assertNull(m.deleteConfirmation); assertTrue(h.writes.isEmpty())
        main { m.create(context) }
        assertEquals("create_profile", h.writes.single().operation); assertEquals("builtin:all0", h.writes.single().args.getString("source"))
    }
    @Test fun newerLoadWaitsForActualReadAndOldAnchorCannotReplaceIt() {
        val h = Harness(); val m = h.model
        main { m.load(context, firstFit); m.load(context, secondFit); m.load(context, null) }
        assertEquals(1, h.reads.size); assertTrue(m.loading)
        main { h.reads.first().future.complete(h.state(firstFit)) }
        assertNull(m.state); assertEquals(2, h.reads.size); assertNull(h.reads.last().fit)
        main { h.reads.last().future.complete(h.state(null)) }
        assertNotNull(m.state); assertFalse(m.loading)
    }
    @Test fun externalRevisionConflictKeepsSkillInputAndExplicitRevertRecovers() {
        val h = Harness(); h.load(); val m = h.model
        main { m.selectSkill(1); m.editLevel(null); h.profile = h.profile.copy(revision = 4, levels = mapOf(1 to 2)); h.current = h.current.copy(generation = 2); m.load(context, null) }
        main { h.reads.last().future.complete(h.state()) }
        assertTrue(m.conflict); assertTrue(m.dirty); assertNull(m.draftLevel)
        main { m.save(context) }; assertTrue(h.writes.isEmpty())
        main { m.revert() }; assertFalse(m.conflict); assertFalse(m.dirty); assertEquals(2, m.draftLevel)
    }
    @Test fun sameRevisionNewSessionCannotEraseOrSilentlySaveTheOldSkillDraft() {
        val h = Harness(); h.load(); val m = h.model
        main { m.selectSkill(1); m.editLevel(0); m.save(context) }
        val old = h.state()
        main { h.current = h.current.copy(sessionId = "e".repeat(32)); m.load(context, null); h.complete(old) }
        assertTrue(m.dirty); assertTrue(m.conflict); assertTrue(m.loading)
        main { h.reads.last().future.complete(h.state()) }
        assertTrue(m.dirty); assertTrue(m.conflict); assertEquals(0, m.draftLevel)
    }
    @Test fun definiteFailureKeepsPickerButUncertainOutcomeBlocksAllFurtherRequests() {
        val h = Harness(); h.load(); val m = h.model
        main { m.beginImplantAdd(); m.chooseImplant(context, nav); h.fail() }
        assertFalse(m.saving); assertFalse(m.reopenRequired); assertNotNull(m.implantChoice)
        main { m.chooseImplant(context, nav); h.fail(uncertain = true); m.chooseImplant(context, nav); m.load(context, null) }
        assertTrue(m.reopenRequired); assertFalse(m.available); assertEquals(2, h.writes.size); assertEquals(1, h.reads.size)
    }
    @Test fun transportFailurePreservesDraftAndDoesNotAutomaticallyRetry() {
        val h = Harness(); h.load(); val m = h.model
        main { m.selectSkill(1); m.editLevel(0); m.save(context); h.writes.last().future.completeExceptionally(IllegalStateException("Lost acknowledgement")); m.save(context) }
        assertTrue(m.dirty); assertTrue(m.reopenRequired); assertEquals(1, h.writes.size)
    }
    @Test fun deleteConfirmationBindsOwnerReplacementImpactAndContext() {
        val h = Harness(); h.bindings = mapOf(firstFit to OfflineBinding(profileId, 1, 7, ImplantLocation.CHARACTER)); h.load(firstFit); val m = h.model
        main { m.requestDelete() }
        assertTrue(m.deleteCurrent); assertEquals(1, m.deleteConfirmation!!.assignedCount)
        main { m.replacementId = "builtin:all0"; m.delete(context) }; assertTrue(h.writes.isEmpty()); assertFalse(m.deleteCurrent)
        main { m.dismissDelete(); m.requestDelete(); m.delete(context) }
        assertEquals("delete_profile", h.writes.single().operation); assertEquals("builtin:all0", h.writes.single().args.getString("replacement"))
    }
    @Test fun sortedPagedRemovalUsesStableRowIdentityNotDisplayIndex() {
        val h = Harness(); val rows = (1..28).map { i -> OfflineProfileImplant(i.toString(16).padStart(32, '0'), 100 + i, "Implant $i", 100 - i, i % 2 == 0) }
        h.profile = h.profile.copy(implants = rows); h.load(); val m = h.model
        main { m.showImplantPage(1) }; assertEquals(1, m.implantPage)
        val before = m.selectedProfile!!; val selected = before.displayImplants[25]
        main { m.removeImplant(context, before.copy(), selected); m.removeImplant(context, before, selected.copy()) }
        assertTrue(h.writes.isEmpty())
        main { m.removeImplant(context, before, selected) }
        assertEquals(selected.implantId, h.writes.single().args.getString("implant_id")); assertEquals("remove_profile_implant", h.writes.single().operation)
    }
    @Test fun cancelledPickerAndClearedViewModelIgnoreLateActionsAndCallbacks() {
        val h = Harness(); h.load(); val m = h.model
        main { m.beginImplantAdd(); m.closeImplantPicker(); m.chooseImplant(context, nav) }; assertTrue(h.writes.isEmpty())
        main { m.load(context, null); ViewModelStore().also { it.put("profile", m); it.clear() } }
        val previous = m.state
        main { h.profile = h.profile.copy(name = "Late"); h.reads.last().future.complete(h.state()) }
        assertSame(previous, m.state)
    }
    @Test fun synchronousValidationFailureReleasesOwnerWithoutPretendingACommit() {
        val h = Harness(); h.load(); val m = h.model; h.throwBeforeEnqueue = true
        main { m.beginImplantAdd(); m.chooseImplant(context, nav) }
        assertFalse(m.saving); assertFalse(m.reopenRequired); assertTrue(h.writes.isEmpty()); assertNotNull(m.error)
    }
}
