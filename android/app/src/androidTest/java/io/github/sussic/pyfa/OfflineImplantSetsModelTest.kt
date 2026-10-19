package io.github.sussic.pyfa

import androidx.lifecycle.ViewModelStore
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Held synthetic transports exercise the actual model. They are not EOS or device evidence until run. */
@RunWith(AndroidJUnit4::class)
class OfflineImplantSetsModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private val setId = "implant-set:" + "b".repeat(32)
    private val profileId = "profile:" + "c".repeat(32)
    private val createdId = "implant-set:" + "e".repeat(32)
    private val recipe = listOf(OfflineImplantSetItem(1001, "Synthetic duplicate", 1),
        OfflineImplantSetItem(1005, "Synthetic replacement", 2), OfflineImplantSetItem(1002, "Synthetic slot 79", 79))
    private val rows = listOf(OfflineImplantCollectionRow("1".repeat(32), 1001, "Synthetic duplicate", 1, false),
        OfflineImplantCollectionRow("2".repeat(32), 1003, "Synthetic old slot", 2, false),
        OfflineImplantCollectionRow("3".repeat(32), 1004, "Synthetic untouched", 7, false))
    private inner class Harness {
        var current = OfflineContext("a".repeat(32), "d".repeat(64), 7)
        var fit: String? = "f".repeat(32)
        var fitRevision: Long? = 2
        var source = ImplantLocation.FIT
        var ready = true
        var throwOnStart = false
        var entry = OfflineImplantSetEntry(setId, "custom", "Synthetic set", null, null, 3, recipe.size.toLong())
        var items = recipe
        val inputs = mutableListOf<OfflineImplantSetRequest>()
        val futures = mutableListOf<CompletableFuture<OfflineImplantSetResponse>>()
        val catalogues = mutableListOf<CompletableFuture<CharacterImplantCatalog>>()
        val model = OfflineImplantSetsModel(featureContext = { current }, activeFit = { fit }, engineAvailable = { ready },
            request = { _, input ->
                if (throwOnStart) throw IllegalStateException("Synthetic transport failure")
                inputs.add(input); CompletableFuture<OfflineImplantSetResponse>().also(futures::add)
            }, loadCatalogue = { CompletableFuture<CharacterImplantCatalog>().also(catalogues::add) })
        fun sync() = model.synchronize(context, current, fit, fitRevision)
        fun state(index: Int = inputs.lastIndex, selected: OfflineImplantSetEntry? = entry.takeIf { inputs[index].view.selectedSetId == entry.id },
            members: List<OfflineImplantSetItem> = items, epoch: OfflineContext = inputs[index].context,
            anchor: String? = inputs[index].anchorFitId, destinationRows: List<OfflineImplantCollectionRow> = rows,
            history: OfflineHistory = OfflineHistory(0, 0, 100, null, null)): OfflineImplantSetState {
            val input = inputs[index]
            val target = input.view.targetProfileId
            val destination = if (target != null) OfflineImplantSetDestination.Profile(target, if (target.startsWith("builtin:")) 0L else 4L,
                "Preview pilot", target.startsWith("builtin:"), 2, if (target.startsWith("builtin:")) emptyList() else destinationRows)
                else anchor?.let { OfflineImplantSetDestination.Fit(it, fitRevision ?: 2L, "Synthetic fit", false, destinationRows) }
            val save = anchor?.let { OfflineImplantSaveSource(it, fitRevision ?: 2L, source,
                if (source == ImplantLocation.CHARACTER) profileId else null,
                if (source == ImplantLocation.CHARACTER) 4L else null,
                if (source == ImplantLocation.CHARACTER) "Applied pilot" else null, 3) }
            return OfflineImplantSetState(epoch, anchor, input.view.copy(selectedSetId = if (input.operation == "delete") null else selected?.id ?: input.view.selectedSetId,
                historyTarget = if (anchor == null && input.view.historyTarget != "library") "library" else input.view.historyTarget),
                1, listOf(selected ?: entry), selected?.let { OfflineImplantSetDetail(it, members) }, destination, save, history)
        }
        fun complete(index: Int = inputs.lastIndex, value: OfflineImplantSetState = state(index), committed: Boolean = false) {
            val input = inputs[index]
            val bridge = if (input.operation == "read") null else BridgeResponse("bootstrap", value.context.sessionId, BridgeStatus.OK,
                value.anchorFitId?.let { id -> listOf(FitSnapshot(id, value.saveSource!!.fitRevision, "Synthetic fit", "Vexor", emptyMap(),
                    emptyList(), emptyMap(), rows.map { ImplantSnapshot(it.name, it.slot, it.active) }, emptyList(), emptyList())) } ?: emptyList(), null)
            futures[index].complete(OfflineImplantSetResponse(input.requestId, true, committed, false, value, bridge, null))
        }
        fun fail(code: String, index: Int = inputs.lastIndex) {
            futures[index].complete(OfflineImplantSetResponse(inputs[index].requestId, false, false, false, null, null,
                OfflineFeatureError(code, "Synthetic definite rejection")))
        }
        fun loadSelected() {
            main { sync() }; main { complete() }; main { model.select(context, entry.id) }; main { complete() }
        }
        fun catalogue() = CharacterImplantCatalog(current.datasetSha256,
            (recipe.map { CharacterImplantItem(it.itemId, it.name, it.slot) } + CharacterImplantItem(1006, "Synthetic new slot two", 2)).sortedBy { it.itemId }, null)
        fun openPicker() { main { model.openPicker(context) }; main { catalogues.last().complete(catalogue()) } }
        fun advance() { current = current.copy(generation = current.generation + 1) }
    }

    @Test fun lastSearchQueuesBehindOwnedReadAndCannotPublishOlderPage() {
        val h = Harness(); val m = h.model
        main { h.sync(); m.search(context, "First"); m.search(context, "Newest") }
        assertEquals(1, h.inputs.size); assertTrue(m.busy)
        main { h.complete(0) }
        assertNull(m.state); assertEquals(2, h.inputs.size); assertEquals("Newest", h.inputs.last().view.query)
        main { h.complete() }
        assertEquals("Newest", m.state!!.view.query); assertFalse(m.busy)
    }
    @Test fun noFitCreateUsesLibraryHistoryAndTrimsSupplementaryUnicodeName() {
        val h = Harness(); h.fit = null; h.fitRevision = null; h.loadSelected(); val m = h.model
        val label = "\uD801\uDC00".repeat(200)
        main { m.begin("create"); m.editName("\u0085$label\u00A0"); m.save(context) }
        val input = h.inputs.last(); val args = OfflineFeatureCodec.parse(input.argumentsJson)
        assertEquals("create", input.operation); assertNull(input.anchorFitId); assertEquals("library", input.view.historyTarget)
        assertEquals(label, args.getString("name")); assertEquals(setOf("name"), args.keys().asSequence().toSet())
    }
    @Test fun namesWithControlsOrMoreThanTwoHundredCodePointsKeepDraftWithoutDispatch() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("create"); m.editName("Bad\u0000name"); m.save(context) }
        assertEquals(2, h.inputs.size); assertTrue(m.dirty); assertNotNull(m.error)
        main { m.editName("\uD801\uDC00".repeat(201)); m.save(context) }
        assertEquals(2, h.inputs.size); assertEquals(402, m.draft!!.name.length)
    }
    @Test fun doubleSaveAndCancelCannotMutateCapturedDraftOrReleaseWorker() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Saved name"); m.save(context); m.save(context); m.cancelDraft(); m.editName("Late name") }
        val frozen = h.inputs.last().json()
        assertEquals(3, h.inputs.size); assertTrue(m.saving); assertEquals("Saved name", m.draft!!.name)
        main { h.advance(); h.sync() }
        assertEquals(3, h.inputs.size); assertEquals(frozen, h.inputs.last().json())
        val renamed = h.entry.copy(name = "Saved name", revision = 4)
        main { h.complete(2, h.state(2, selected = renamed, epoch = h.current), true) }
        assertFalse(m.dirty); assertEquals(4, h.inputs.size)
        main { h.complete(3, h.state(3, selected = renamed)) }
        assertEquals("Saved name", m.detail!!.entry.name); assertFalse(m.busy)
    }
    @Test fun createSelectsFreshIdentityDespiteItsOwnContextPublication() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("create"); m.editName("Empty custom"); m.save(context); h.advance(); h.sync() }
        val created = h.entry.copy(id = createdId, name = "Empty custom", revision = 1, itemCount = 0)
        main { h.complete(2, h.state(2, selected = created, members = emptyList(), epoch = h.current), true) }
        assertEquals(createdId, m.view.selectedSetId); assertFalse(m.dirty)
        assertEquals(createdId, h.inputs.last().view.selectedSetId)
    }
    @Test fun definiteFailureRetainsNameAndStaleRevisionMarksConflict() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Retained"); m.save(context) }; main { h.fail("stale_set") }
        assertEquals("Retained", m.draft!!.name); assertTrue(m.conflict); assertFalse(m.canSave); assertFalse(m.reopenRequired)
        main { m.cancelDraft() }; assertFalse(m.dirty)
    }
    @Test fun disappearedSelectionDoesNotRetargetAndPreservesOrphanDraft() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Keep orphan"); h.advance(); h.sync() }
        main { h.complete(value = h.state(selected = null).copy(entries = emptyList(), total = 0)) }
        assertNull(m.detail); assertEquals(setId, m.view.selectedSetId); assertTrue(m.conflict); assertEquals("Keep orphan", m.draft!!.name)
    }
    @Test fun backRetainsWorkerAndSuppressesHiddenResultUntilReturnRead() {
        val h = Harness(); val m = h.model
        main { h.sync(); m.leave(); m.reload(context) }
        assertTrue(m.busy); assertEquals(1, h.inputs.size)
        main { h.complete(0) }
        assertNull(m.state); assertFalse(m.busy); assertEquals(1, h.inputs.size)
        main { m.enter(context) }; assertEquals(2, h.inputs.size)
        main { h.complete() }; assertNotNull(m.state)
    }
    @Test fun successfulHiddenSaveSettlesExactDraftOnReturnWithoutPublishingOldState() {
        val h = Harness(); h.loadSelected(); val m = h.model; val before = m.state
        main { m.begin("rename"); m.editName("Hidden save"); m.save(context); m.leave(); h.advance() }
        val renamed = h.entry.copy(name = "Hidden save", revision = 4)
        main { h.complete(value = h.state(selected = renamed, epoch = h.current), committed = true) }
        assertSame(before, m.state); assertTrue(m.dirty); assertFalse(m.busy)
        main { m.enter(context) }; assertFalse(m.dirty); assertEquals(4, h.inputs.size)
    }
    @Test fun activeFitChangeRejectsOldReadAndQueuesCorrectAnchor() {
        val h = Harness(); val m = h.model
        main { h.sync(); h.fit = "9".repeat(32); h.sync() }
        main { h.complete(0) }; assertNull(m.state); assertEquals(h.fit, h.inputs.last().anchorFitId)
        main { h.complete() }; assertEquals(h.fit, m.state!!.anchorFitId)
    }
    @Test fun returnBeforeSaveFinishesKeepsOwnershipThenSettlesDraftOnFreshRead() {
        val h = Harness(); h.loadSelected(); val m = h.model; val before = m.state
        main { m.begin("rename"); m.editName("Saved during back"); m.save(context); m.leave(); m.enter(context) }
        assertEquals(3, h.inputs.size); assertTrue(m.saving)
        main { h.advance() }
        val renamed = h.entry.copy(name = "Saved during back", revision = 4)
        main { h.complete(2, h.state(2, selected = renamed, epoch = h.current), true) }
        assertSame(before, m.state); assertEquals(4, h.inputs.size); assertTrue(m.dirty)
        main { h.complete(3, h.state(3, selected = renamed)) }
        assertFalse(m.dirty); assertFalse(m.conflict); assertEquals(renamed, m.detail!!.entry)
    }
    @Test fun oldSessionUncertainCallbackCannotPoisonAlreadyReopenedSession() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Old draft"); m.save(context); h.current = h.current.copy(sessionId = "8".repeat(32), generation = 1); h.sync() }
        main { h.futures[2].completeExceptionally(IllegalStateException("old unknown")) }
        assertFalse(m.reopenRequired); assertTrue(m.conflict); assertEquals(4, h.inputs.size)
        main { h.complete(3) }; assertEquals(h.current, m.state!!.context)
    }
    @Test fun uncertainAndMismatchedMutationRepliesDisableUntilNewSessionWithoutRetry() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Uncertain"); m.save(context) }
        main { h.futures.last().complete(OfflineImplantSetResponse("wrong-id", false, false, false, null, null, OfflineFeatureError("invalid_request", "Wrong request"))) }
        assertTrue(m.reopenRequired); assertTrue(m.dirty)
        main { m.save(context); m.reload(context); m.cancelDraft(); m.begin("create") }; assertEquals(3, h.inputs.size)
        main { h.current = h.current.copy(sessionId = "8".repeat(32), generation = 1); h.sync() }
        assertFalse(m.reopenRequired); assertEquals(4, h.inputs.size)
    }
    @Test fun synchronousMutationTransportThrowIsUncertainRatherThanSafeToRepeat() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Retained"); h.throwOnStart = true; m.save(context) }
        assertFalse(m.busy); assertTrue(m.reopenRequired); assertTrue(m.dirty)
        main { h.throwOnStart = false; m.save(context) }; assertEquals(2, h.inputs.size)
    }
    @Test fun clearNeverPublishesLateResultOrStartsQueuedRefresh() {
        val h = Harness(); val store = ViewModelStore()
        main { store.put("implant-sets", h.model); h.sync(); h.model.search(context, "later"); store.clear() }
        main { h.complete(0) }
        assertNull(h.model.state); assertFalse(h.model.busy); assertEquals(1, h.inputs.size)
    }
    @Test fun builtinSetIsBrowseApplyOnlyNotDuplicateRenameDeleteOrEdit() {
        val h = Harness(); h.entry = h.entry.copy(id = "builtin:implant-set:1", kind = "builtin", name = "Genolution", family = "Genolution", grade = null, revision = 0)
        h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.begin("duplicate"); m.confirmDelete(); m.openPicker(context); m.removeItem(context, recipe.first()) }
        assertFalse(m.dirty); assertNull(m.deleteConfirmation); assertNull(m.addChoice); assertEquals(2, h.inputs.size)
        main { m.reviewApplication(context) }; assertEquals("read", h.inputs.last().operation); assertEquals(h.fit, h.inputs.last().view.historyTarget)
        main { h.complete() }; assertNotNull(m.applicationReview)
    }
    @Test fun catalogueCancelKeepsOwnershipAndDiscardsLateMetadata() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.openPicker(context); m.closePicker(); m.reload(context) }
        assertTrue(m.busy); assertEquals(2, h.inputs.size); assertEquals(1, h.catalogues.size)
        main { h.catalogues[0].complete(h.catalogue()) }
        assertNull(m.catalogue); assertNull(m.addChoice); assertEquals(3, h.inputs.size)
    }
    @Test fun sameSlotReplacementUsesExpectedOccupantAndOnlyIdentityArguments() {
        val h = Harness(); h.loadSelected(); h.openPicker(); val m = h.model
        val item = h.catalogue().itemById.getValue(1006)
        main { m.chooseItem(context, item) }; assertEquals(1005, m.replacement!!.occupant.itemId)
        main { m.replaceItem(context); m.replaceItem(context) }
        assertEquals(3, h.inputs.size)
        val args = OfflineFeatureCodec.parse(h.inputs.last().argumentsJson)
        assertEquals(setOf("set_id", "revision", "item_id", "replace_item_id"), args.keys().asSequence().toSet())
        assertEquals(1005, args.getInt("replace_item_id")); assertEquals(1006, args.getInt("item_id")); assertEquals("library", h.inputs.last().view.historyTarget)
    }
    @Test fun staleReplacementAndDeletionConfirmationsCannotSubmit() {
        val h = Harness(); h.loadSelected(); h.openPicker(); val m = h.model
        main { m.chooseItem(context, h.catalogue().itemById.getValue(1006)); h.advance(); m.replaceItem(context) }
        assertEquals(2, h.inputs.size); assertNotNull(m.error)
        main { m.closePicker(); h.sync() }; main { h.complete() }
        main { m.confirmDelete(); h.advance(); m.delete(context) }
        assertEquals(3, h.inputs.size); assertNull(m.deleteConfirmation)
    }
    @Test fun applicationReviewPreservesInactiveDuplicateUntouchedAndActualSlotSeventyNine() {
        val h = Harness(); h.loadSelected()
        val review = implantApplicationReview(h.model.state!!)!!
        assertEquals(listOf(OfflineImplantApplyDisposition.DUPLICATE_SKIPPED, OfflineImplantApplyDisposition.REPLACED, OfflineImplantApplyDisposition.ADDED), review.steps.map { it.disposition })
        assertEquals(false, review.steps.first().occupant!!.active); assertEquals(79, review.steps.last().item.slot)
        assertEquals(listOf(rows.last()), review.untouched)
        assertEquals(rows, h.model.state!!.destination!!.implants)
    }
    @Test fun characterReviewRecreatesExactDuplicateAndSkillDraftBlocksApplication() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.destination(context, profileId) }; main { h.complete() }
        main { m.reviewApplication(context) }
        assertEquals(OfflineImplantApplyDisposition.REPLACED, m.applicationReview!!.steps.first().disposition)
        main { m.preserveSkillDraft(true); m.apply(context); m.destination(context, "builtin:all5") }
        assertNull(m.applicationReview); assertEquals(profileId, m.view.targetProfileId); assertEquals(3, h.inputs.size)
        main { m.preserveSkillDraft(false); m.reviewApplication(context); m.apply(context) }
        assertEquals("apply_profile", h.inputs.last().operation); assertEquals("library", h.inputs.last().view.historyTarget)
        val args = OfflineFeatureCodec.parse(h.inputs.last().argumentsJson)
        assertEquals(setOf("set_id", "revision", "profile_id", "profile_revision"), args.keys().asSequence().toSet())
        assertEquals(profileId, args.getString("profile_id"))
    }
    @Test fun fitApplicationDeliberatelyChangesHistoryAndPreservesCharacterSourceInRequest() {
        val h = Harness(); h.source = ImplantLocation.CHARACTER; h.loadSelected(); val m = h.model
        main { m.reviewApplication(context) }
        assertTrue(m.busy); assertEquals(h.fit, m.view.historyTarget); assertNull(m.applicationReview)
        main { h.complete() }; main { m.apply(context); m.apply(context) }
        val input = h.inputs.last(); val args = OfflineFeatureCodec.parse(input.argumentsJson)
        assertEquals("apply_fit", input.operation); assertNull(input.view.targetProfileId); assertEquals(h.fit, input.view.historyTarget)
        assertEquals(setOf("set_id", "revision", "fit_revision"), args.keys().asSequence().toSet()); assertEquals(4, h.inputs.size)
    }
    @Test fun saveCurrentUsesAppliedSourceNotThePreviewCharacterAndCapturesRevision() {
        val h = Harness(); h.source = ImplantLocation.CHARACTER; h.loadSelected(); val m = h.model
        val preview = "profile:" + "9".repeat(32)
        main { m.destination(context, preview) }; main { h.complete() }
        main { m.begin("save_current"); m.editName("From applied"); m.save(context) }
        assertEquals(profileId, m.draft!!.saveSource!!.profileId); assertEquals(preview, h.inputs.last().view.targetProfileId)
        val args = OfflineFeatureCodec.parse(h.inputs.last().argumentsJson)
        assertEquals(setOf("name", "fit_revision"), args.keys().asSequence().toSet()); assertEquals(2L, args.getLong("fit_revision"))
    }
    @Test fun saveCurrentSourceChangeKeepsDraftButBlocksSubmission() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("save_current"); m.editName("Old source"); h.source = ImplantLocation.CHARACTER; h.fitRevision = 3; h.advance(); h.sync() }
        main { h.complete() }; main { m.save(context) }
        assertEquals(ImplantLocation.FIT, m.draft!!.saveSource!!.source); assertTrue(m.conflict); assertEquals(3, h.inputs.size)
    }
    @Test fun missingPreviewCharacterNeverFallsBackToFitAndSaveSourceRemainsSeparate() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.destination(context, profileId) }
        main { h.complete(value = h.state().copy(destination = null)) }
        assertEquals(profileId, m.view.targetProfileId); assertNull(m.state!!.destination); assertEquals(h.fit, m.state!!.saveSource!!.fitId)
        main { m.reviewApplication(context) }; assertNull(m.applicationReview); assertEquals(3, h.inputs.size)
    }
    @Test fun noFitCharacterApplicationNeedsOnlyExplicitProfileAndLibraryTimeline() {
        val h = Harness(); h.fit = null; h.fitRevision = null; h.loadSelected(); val m = h.model
        main { m.destination(context, profileId) }; main { h.complete() }
        main { m.reviewApplication(context); m.apply(context) }
        assertEquals("apply_profile", h.inputs.last().operation); assertNull(h.inputs.last().anchorFitId)
        assertEquals(profileId, h.inputs.last().view.targetProfileId); assertEquals("library", h.inputs.last().view.historyTarget)
        assertNull(m.state!!.saveSource)
    }
    @Test fun missingMutationBridgeIsUncertainEvenWhenTypedSuccessClaimsCommit() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Claimed save"); m.save(context) }
        val input = h.inputs.last()
        val value = h.state(selected = h.entry.copy(name = "Claimed save", revision = 4), epoch = input.context.copy(generation = 8))
        main { h.futures.last().complete(OfflineImplantSetResponse(input.requestId, true, true, false, value, null, null)) }
        assertTrue(m.reopenRequired); assertTrue(m.dirty); assertEquals("Synthetic set", m.detail!!.entry.name)
    }
    @Test fun readOnlyProfileAndStructureDestinationsCannotApply() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.destination(context, "builtin:all5") }; main { h.complete() }; main { m.reviewApplication(context) }
        assertNull(m.applicationReview)
        main { m.destination(context, null) }
        val value = h.state(); main { h.complete(value = value.copy(destination = (value.destination as OfflineImplantSetDestination.Fit).copy(isStructure = true))) }
        main { m.reviewApplication(context) }; assertNull(m.applicationReview); assertEquals(4, h.inputs.size)
    }
    @Test fun replayDisappearanceDropsFitAndPreservesLibraryRedo() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.chooseHistory(context, h.fit!!) }
        main { h.complete(value = h.state(history = OfflineHistory(1, 0, 100, "Import fits", null))) }
        main { m.history(context, false); h.fit = null; h.fitRevision = null; h.advance(); h.sync() }
        val after = h.state(anchor = null, epoch = h.current, history = OfflineHistory(0, 1, 100, null, "Import fits"))
        main { h.complete(3, after, true) }
        assertNull(m.state!!.anchorFitId); assertNull(m.state!!.saveSource); assertNull(m.state!!.destination)
        assertEquals("library", m.view.historyTarget); assertEquals(1, m.state!!.history.redoCount)
        assertEquals("library", h.inputs.last().view.historyTarget)
    }
}
