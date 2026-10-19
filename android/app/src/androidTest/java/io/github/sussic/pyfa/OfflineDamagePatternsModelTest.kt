package io.github.sussic.pyfa

import androidx.lifecycle.ViewModelStore
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Held synthetic worker replies prove draft/callback ownership only, not EOS behavior. */
@RunWith(AndroidJUnit4::class)
class OfflineDamagePatternsModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private val pattern = "damage:" + "b".repeat(32)
    private inner class Harness {
        var current = OfflineContext("a".repeat(32), "c".repeat(64), 7)
        var fit: String? = "f".repeat(32)
        var fitRevision: Long? = 2
        var ready = true
        var throwOnStart = false
        val inputs = mutableListOf<OfflineDamageRequest>()
        val pending = mutableListOf<CompletableFuture<OfflineDamageResponse>>()
        val entry = OfflineDamageEntry(pattern, "custom", "Synthetic pattern", 3, 0, true, null)
        val model = OfflineDamagePatternsModel(featureContext = { current }, activeFit = { fit }, engineAvailable = { ready }, request = { _, input ->
            if (throwOnStart) throw IllegalStateException("Synthetic launch error")
            inputs.add(input); CompletableFuture<OfflineDamageResponse>().also(pending::add)
        })
        fun sync() = model.synchronize(context, current, fit, fitRevision)
        fun state(index: Int = inputs.lastIndex, revision: Long = 3, id: String? = inputs[index].view.selectedPatternId): OfflineDamageState {
            val input = inputs[index]; val raw = OfflineDamageValues(DAMAGE_PATTERN_FIELDS.associateWith { 25.0 })
            val percentages = OfflineDamageValues(DAMAGE_PATTERN_FIELDS.associateWith { 25.0 })
            val selected = id?.let { entry.copy(id = it, kind = when { it == SELECTED_AMMO_PATTERN_ID -> "selected_ammo"; it.startsWith("damage:builtin:") -> "builtin"; else -> "custom" }, revision = if (it.startsWith("damage:builtin:")) 0 else revision) }
            return OfflineDamageState(current, input.fitId, if (input.fitId == null) null else fitRevision,
                OfflineDamageSelection(if (input.fitId == null) "no_fit" else "anonymous", null, null, null), input.view.copy(selectedPatternId = id), 1,
                listOf(selected ?: entry), selected?.let { OfflineDamageDetail(it, raw, percentages, input.view.boundOffset, emptyList()) }, OfflineHistory(0, 0, 100, null, null))
        }
        fun complete(index: Int = inputs.lastIndex, value: OfflineDamageState = state(index), committed: Boolean = false) {
            pending[index].complete(OfflineDamageResponse(inputs[index].requestId, true, committed, false, value, null, null))
        }
        fun fail(code: String, index: Int = inputs.lastIndex) = pending[index].complete(OfflineDamageResponse(inputs[index].requestId,
            false, false, false, null, null, OfflineFeatureError(code, "Synthetic complete error")))
        fun loadSelected() {
            main { sync() }; main { complete() }; main { model.select(context, pattern) }; main { complete() }
        }
    }

    @Test fun newerSearchInvalidatesBeforeOlderReadCanClearLoadingOrReplaceIt() {
        val h = Harness(); val m = h.model
        main { h.sync(); m.search(context, "Newest"); m.search(context, "Final") }
        assertEquals(3, h.pending.size); assertTrue(m.busy)
        main { h.complete(0) }; main { h.complete(1) }
        assertEquals("Final", h.inputs.last().view.query); assertNull(m.state); assertTrue(m.busy)
        main { h.complete(2) }
        assertEquals("Final", m.state!!.view.query); assertFalse(m.busy)
    }
    @Test fun ownPublicationInvalidatesOldSaveButNewOwnedReadReconcilesExactDraft() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("update_values"); m.editField(3, "125"); m.save(context); m.save(context); m.cancelDraft(); m.editField(3, "999") }
        assertEquals(3, h.pending.size); assertTrue(m.saving); assertEquals("125", m.draft!!.fields[3])
        main { h.current = h.current.copy(generation = 8); h.fitRevision = 3; h.sync() }
        assertEquals(4, h.pending.size); assertTrue(m.busy); assertFalse(m.saving)
        main { h.complete(2, h.state(2, revision = 4), committed = true) }
        // The obsolete save callback cannot even clear busy or its submitted draft.
        assertTrue(m.dirty); assertTrue(m.busy); assertNull(m.message)
        main { h.complete(3, h.state(3, revision = 4)) }
        assertFalse(m.dirty); assertFalse(m.conflict); assertFalse(m.busy); assertEquals(4L, m.detail!!.entry.revision)
        assertNotNull(m.message)
    }
    @Test fun createSelectionIsReconciledOnlyByNewReadAfterOwnPublication() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("create"); m.editName("New pattern"); m.save(context) }
        val created = "damage:" + "e".repeat(32)
        main { h.current = h.current.copy(generation = 8); h.sync() }
        main { h.complete(2, h.state(2, revision = 1, id = created), committed = true) }
        assertTrue(m.dirty); assertEquals(pattern, m.view.selectedPatternId); assertEquals(4, h.inputs.size)
        main { h.complete(3) }
        assertFalse(m.dirty); assertEquals(created, m.view.selectedPatternId)
        assertEquals(created, h.inputs.last().view.selectedPatternId); assertEquals(5, h.inputs.size)
        main { h.complete(4, h.state(4, revision = 1, id = created)) }
        assertEquals(created, m.detail!!.entry.id)
    }
    @Test fun ownDeletePublicationRecoversMissingSelectedDetailWithoutFalseRefusal() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.confirmDelete(); m.delete(context) }
        val deletion = h.inputs.lastIndex
        main { h.current = h.current.copy(generation = 8); h.sync() }
        val refresh = h.inputs.lastIndex
        main { h.complete(deletion, h.state(deletion, id = null), committed = true) }
        assertTrue(m.busy); assertNull(m.message)
        main { h.fail("missing_pattern", refresh) }
        assertNull(m.error); assertNull(m.view.selectedPatternId); assertTrue(m.message!!.contains("local hardeners"))
        assertEquals(refresh + 2, h.inputs.size)
        main { h.complete() }; assertFalse(m.busy); assertNull(m.detail)
    }
    @Test fun closeAndSameContextReopenRejectsOldReadAndSavedDraftReconciliation() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Retain draft"); m.save(context); m.close(); m.open(); h.sync() }
        val currentRead = h.inputs.lastIndex
        main { h.complete(2, h.state(2), committed = true) }
        assertTrue(m.busy); assertTrue(m.dirty); assertNull(m.message)
        main { h.complete(currentRead) }
        assertTrue(m.dirty); assertNull(m.message); assertEquals("Retain draft",m.draft!!.name)
    }
    @Test fun identityMismatchedCompletionCannotReconcileDraftThroughLaterRead() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Retained"); m.save(context); h.current = h.current.copy(generation = 8); h.sync() }
        main { h.pending[2].complete(OfflineDamageResponse("another-request",true,true,false,h.state(2),null,null)) }
        main { h.complete(3) }
        assertTrue(m.dirty); assertEquals("Retained",m.draft!!.name); assertNull(m.message)
    }
    @Test fun invalidDraftAndRejectedSaveRetainEveryInputUntilExplicitCancel() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("update_values"); m.editField(0, "-1"); m.editField(3, "not a number"); m.save(context) }
        assertEquals(2, h.pending.size); assertEquals("not a number", m.draft!!.fields[3]); assertNotNull(m.error)
        main { m.editField(0, "100"); m.editField(3, "0"); m.save(context) }
        main { h.fail("stale_pattern") }
        assertTrue(m.dirty); assertTrue(m.conflict); assertFalse(m.canSave); assertEquals("0", m.draft!!.fields[3])
        main { m.cancelDraft() }; assertFalse(m.dirty); assertFalse(m.conflict)
    }
    @Test fun externalRevisionRefreshKeepsDraftAndMarksConflictWithoutChangingItsSource() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Kept new name"); h.current = h.current.copy(generation = 8); h.sync() }
        main { h.complete(value = h.state(revision = 4)) }
        assertEquals("Kept new name", m.draft!!.name); assertEquals(3L, m.draft!!.sourceRevision); assertTrue(m.conflict)
    }
    @Test fun sourceRemovalLeavesOrphanDraftRecoverableInsteadOfReloadingMissingIdForever() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("update_values"); m.editField(3, "42"); m.reload(context) }
        main { h.fail("missing_pattern") }
        assertTrue(m.dirty); assertTrue(m.conflict); assertNull(m.view.selectedPatternId); assertEquals("42", m.draft!!.fields[3])
        main { m.reload(context) }; main { h.complete() }
        assertNull(m.detail); assertTrue(m.dirty)
        main { m.cancelDraft(); m.select(context, pattern) }; main { h.complete() }
        assertNotNull(m.detail); assertFalse(m.conflict)
    }
    @Test fun navigationAndSessionChangeIgnoreOldCallbackButRetainDraft() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Keep me"); m.reload(context); h.fit = null; h.fitRevision = null; h.sync() }
        main { h.complete(2) }
        assertEquals(4, h.pending.size); assertEquals("Keep me", m.draft!!.name)
        main { h.current = h.current.copy(sessionId = "d".repeat(32), generation = 1); h.sync() }
        main { h.complete(3) }; main { h.complete(4) }
        assertNull(m.state!!.fitId); assertEquals(h.current, m.state!!.context); assertTrue(m.conflict); assertTrue(m.dirty)
    }
    @Test fun deleteConfirmationCapturesExactCountContextAndProfileRevision() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.confirmDelete() }; assertEquals(0L, m.deleteConfirmation!!.entry.boundFitCount)
        main { h.current = h.current.copy(generation = 8); m.delete(context) }
        assertEquals(2, h.pending.size); assertNull(m.deleteConfirmation); assertNotNull(m.error)
        main { h.sync() }; main { h.complete() }
        main { m.confirmDelete(); m.delete(context); m.delete(context) }
        assertEquals(4, h.pending.size)
        val args = OfflineFeatureCodec.parse(h.inputs.last().argumentsJson)
        assertEquals(0L, OfflineFeatureCodec.integer(args.get("bound_fit_count")))
        assertEquals(0L, OfflineFeatureCodec.integer(args.get("bound_module_count")))
        assertEquals(0L, OfflineFeatureCodec.integer(args.get("affected_fit_count")))
        assertEquals(3L, OfflineFeatureCodec.integer(args.get("revision")))
        assertEquals(pattern, args.getString("pattern_id"))
    }
    @Test fun builtinsAreReadOnlyAndDuplicateOnlySendsIdentityAndName() {
        val h = Harness(); main { h.sync() }; main { h.complete(value = h.state(id = "damage:builtin:-17")) }
        val m = h.model
        main { m.begin("update_values"); m.begin("rename"); m.confirmDelete() }
        assertFalse(m.dirty); assertNull(m.deleteConfirmation)
        main { m.begin("duplicate"); m.editName("Independent"); m.save(context) }
        assertEquals("duplicate", h.inputs.last().operation)
        assertEquals(setOf("pattern_id", "revision", "name"), OfflineFeatureCodec.parse(h.inputs.last().argumentsJson).keys().asSequence().toSet())
    }
    @Test fun startFailureReleasesOwnershipAndUncertainCompletionKeepsDraft() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Retained"); h.throwOnStart = true; m.save(context) }
        assertFalse(m.busy); assertTrue(m.dirty); assertNotNull(m.error)
        main { h.throwOnStart = false; m.save(context) }
        main { h.pending.last().completeExceptionally(IllegalStateException("unknown")) }
        assertFalse(m.busy); assertTrue(m.dirty); assertTrue(m.error!!.contains("restart")); assertTrue(m.reopenRequired); assertFalse(m.available)
        main { m.save(context); m.reload(context) }; assertEquals(3, h.pending.size)
    }
    @Test fun clearedModelNeverPublishesLateReplyOrStartsPendingReload() {
        val h = Harness(); val store = ViewModelStore(); val m = h.model
        main { store.put("pattern", m); h.sync(); m.search(context, "pending"); store.clear() }
        main { h.complete(0) }
        assertNull(m.state); assertFalse(m.busy); assertEquals(2, h.pending.size)
    }
    private fun defenses(id: String, revision: Long): FitDefenses {
        val scalar = DefenseScalar(StatValue.Unavailable, "HP", null, null)
        return FitDefenses(id, revision, emptyMap(), scalar, scalar,
            DAMAGE_TYPES.keys.associateWith { IncomingContribution(25.0, 25.0, "25") })
    }
    private fun Harness.namedState(): OfflineDamageState = state().let { value -> value.copy(
        selection = OfflineDamageSelection("named", pattern, 3, 9),
        entries = value.entries.map { it.copy(boundFitCount = 1) },
        detail = value.detail?.copy(entry = value.detail.entry.copy(boundFitCount = 1))) }

    @Test fun unchangedDefenseDraftCanDetachUsingOnlySavedIdentityPreconditions() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.reload(context) }; main { h.complete(value = h.namedState()) }
        val defense = IncomingDraft(h.fit!!); defense.load(defenses(h.fit!!, 2)); assertFalse(defense.dirty)
        main { m.detach(context); m.detach(context) }
        assertEquals(4, h.inputs.size)
        val input = h.inputs.last(); val args = OfflineFeatureCodec.parse(input.argumentsJson)
        assertEquals("detach_to_anonymous", input.operation)
        assertEquals(setOf("pattern_id", "revision", "binding_revision", "fit_revision"), args.keys().asSequence().toSet())
        assertEquals(pattern, args.getString("pattern_id")); assertEquals(3L, OfflineFeatureCodec.integer(args.get("revision")))
        assertEquals(9L, OfflineFeatureCodec.integer(args.get("binding_revision")))
        assertEquals(2L, OfflineFeatureCodec.integer(args.get("fit_revision")))
        assertFalse(defense.dirty)
    }
    @Test fun invalidDefenseTextSurvivesDetachPublicationBeforeCallbackAndStaysUnapplied() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.reload(context) }; main { h.complete(value = h.namedState()) }
        val defense = IncomingDraft(h.fit!!); defense.load(defenses(h.fit!!, 2))
        defense.text["em"] = "not valid"; defense.text["thermal"] = "007.000"
        val text = defense.text.toMap(); assertTrue(defense.dirty); assertNull(defense.values())
        main { m.detach(context) }
        assertFalse(h.inputs.last().argumentsJson.contains("values"))
        main { h.current = h.current.copy(generation = 8); h.fitRevision = 3; h.sync(); defense.load(defenses(h.fit!!, 3)) }
        main { h.complete(3, h.state(3), committed = true) }
        main { h.complete(4) }
        assertEquals(text, defense.text.toMap()); assertTrue(defense.dirty); assertTrue(defense.conflict)
        assertEquals("anonymous", m.state!!.selection.kind)
        assertTrue(m.message!!.contains("Unsaved edits were not applied"))
    }
    @Test fun rejectedDetachKeepsBindingAndDirtyDefenseText() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.reload(context) }; main { h.complete(value = h.namedState()) }
        val defense = IncomingDraft(h.fit!!); defense.load(defenses(h.fit!!, 2)); defense.text["em"] = "42"
        main { m.detach(context) }; main { h.fail("stale_binding") }
        assertEquals("named", m.state!!.selection.kind); assertEquals("42", defense.text["em"]); assertTrue(defense.dirty)
    }
    @Test fun reloadSavedContributionsDoesNotSendMutationWhileUniformResetDoes() {
        val h = Harness(); h.loadSelected(); val m = h.model
        val defense = IncomingDraft(h.fit!!); val saved = defenses(h.fit!!, 2); defense.load(saved)
        defense.text["em"] = "42"; val requests = h.inputs.size
        main { defense.load(saved, discard = true) }
        assertEquals(requests, h.inputs.size); assertFalse(defense.dirty)
        main { m.resetUniform(context) }
        assertEquals("reset_uniform", h.inputs.last().operation)
        assertEquals(setOf("fit_revision"), OfflineFeatureCodec.parse(h.inputs.last().argumentsJson).keys().asSequence().toSet())
    }
    @Test fun zeroLibraryRecordCanEditButCannotAssignAndNoFitLibraryStillSaves() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.reload(context) }; main { h.complete(value = h.state().let { value -> value.copy(
            entries = value.entries.map { it.copy(assignable = false, unassignableReason = "zero_total") },
            detail = value.detail!!.copy(entry = value.detail.entry.copy(assignable = false, unassignableReason = "zero_total"),
                values = OfflineDamageValues(DAMAGE_PATTERN_FIELDS.associateWith { 0.0 }))) }) }
        val count = h.inputs.size; main { m.assign(context) }; assertEquals(count, h.inputs.size)
        main { h.fit = null; h.fitRevision = null; h.sync() }; main { h.complete() }
        main { m.begin("create"); m.editName("Unassigned zero"); m.save(context) }
        assertNull(h.inputs.last().fitId); assertEquals("create", h.inputs.last().operation)
        val values = OfflineFeatureCodec.parse(h.inputs.last().argumentsJson).getJSONObject("values")
        DAMAGE_PATTERN_FIELDS.forEach { assertEquals(0.0, values.get(it)) }
    }
    @Test fun uncertainReplyDisablesFurtherOperationsUntilDifferentSessionReopens() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.resetUniform(context) }
        main { h.pending.last().complete(OfflineDamageResponse(h.inputs.last().requestId, false, null, true, null, null,
            OfflineFeatureError("reopen_required", "Restart required"))) }
        assertTrue(m.reopenRequired); val count = h.inputs.size
        main { m.resetUniform(context); m.reload(context) }; assertEquals(count, h.inputs.size)
        main { h.current = h.current.copy(sessionId = "d".repeat(32), generation = 1); h.sync() }
        assertFalse(m.reopenRequired); assertEquals(count + 1, h.inputs.size)
    }
    @Test fun selectedAmmoRejectsEveryLibraryEditIncludingDuplicateButCanAssign() {
        val h = Harness(); main { h.sync() }; main { h.complete(value = h.state(id = SELECTED_AMMO_PATTERN_ID)) }
        main { h.model.begin("rename"); h.model.begin("update_values"); h.model.begin("duplicate"); h.model.confirmDelete() }
        assertFalse(h.model.dirty); assertNull(h.model.deleteConfirmation)
        main { h.model.assign(context) }; assertEquals("assign", h.inputs.last().operation)
    }
}
