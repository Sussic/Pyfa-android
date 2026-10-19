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
class OfflineTargetProfilesModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private val target = "target:" + "b".repeat(32)
    private inner class Harness {
        var current = OfflineContext("a".repeat(32), "c".repeat(64), 7)
        var fit: String? = "f".repeat(32)
        var fitRevision: Long? = 2
        var ready = true
        var throwOnStart = false
        val inputs = mutableListOf<OfflineTargetRequest>()
        val pending = mutableListOf<CompletableFuture<OfflineTargetResponse>>()
        val entry = OfflineTargetEntry(target, "custom", "Synthetic target", 3, 0)
        val model = OfflineTargetProfilesModel(featureContext = { current }, activeFit = { fit }, engineAvailable = { ready }, request = { _, input ->
            if (throwOnStart) throw IllegalStateException("Synthetic launch error")
            inputs.add(input); CompletableFuture<OfflineTargetResponse>().also(pending::add)
        })
        fun sync() = model.synchronize(context, current, fit, fitRevision)
        fun state(index: Int = inputs.lastIndex, revision: Long = 3, id: String? = inputs[index].view.selectedTargetId): OfflineTargetState {
            val input = inputs[index]; val raw = OfflineTargetValues(TARGET_FIELDS.associateWith { if (it.endsWith("Amount")) 0.0 else null })
            val effective = OfflineTargetValues(raw.fields + mapOf("maxVelocity" to 0L, "radius" to 0L))
            val selected = id?.let { entry.copy(id = it, kind = if (it.startsWith("target:builtin:")) "builtin" else "custom", revision = if (it.startsWith("target:builtin:")) 0 else revision) }
            return OfflineTargetState(current, input.fitId, if (input.fitId == null) null else fitRevision,
                OfflineTargetSelection(if (input.fitId == null) "no_fit" else "none", null, null), input.view.copy(selectedTargetId = id), 1,
                listOf(selected ?: entry), selected?.let { OfflineTargetDetail(it, raw, effective, input.view.boundOffset, emptyList()) }, OfflineHistory(0, 0, 100, null, null))
        }
        fun complete(index: Int = inputs.lastIndex, value: OfflineTargetState = state(index), committed: Boolean = false) {
            pending[index].complete(OfflineTargetResponse(inputs[index].requestId, true, committed, false, value, null, null))
        }
        fun fail(code: String, index: Int = inputs.lastIndex) = pending[index].complete(OfflineTargetResponse(inputs[index].requestId,
            false, false, false, null, null, OfflineFeatureError(code, "Synthetic complete error")))
        fun loadSelected() {
            main { sync() }; main { complete() }; main { model.select(context, target) }; main { complete() }
        }
    }

    @Test fun newerSearchWaitsForActualWorkerAndOlderReadCannotReplaceIt() {
        val h = Harness(); val m = h.model
        main { h.sync(); m.search(context, "Newest"); m.search(context, "Final") }
        assertEquals(1, h.pending.size); assertTrue(m.busy)
        main { h.complete(0) }
        assertEquals(2, h.pending.size); assertEquals("Final", h.inputs.last().view.query); assertNull(m.state)
        main { h.complete() }
        assertEquals("Final", m.state!!.view.query); assertFalse(m.busy)
    }
    @Test fun repeatedSaveKeepsOneOwnerAndOwnPublicationCannotLeaveASavedDraftDirty() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("update_values"); m.editField(7, "125"); m.save(context); m.save(context); m.cancelDraft(); m.editField(7, "999") }
        assertEquals(3, h.pending.size); assertTrue(m.saving); assertEquals("125", m.draft!!.fields[7])
        main { h.current = h.current.copy(generation = 8); h.fitRevision = 3; h.sync() }
        assertEquals(3, h.pending.size); assertTrue(m.saving)
        main { h.complete(2, h.state(2, revision = 4), committed = true) }
        assertFalse(m.dirty); assertEquals(4, h.pending.size); assertTrue(m.busy)
        main { h.complete(3, h.state(3, revision = 4)) }
        assertFalse(m.busy); assertEquals(4L, m.detail!!.entry.revision)
    }
    @Test fun createSelectsItsNewIdentityAfterItsOwnPublicationSchedulesRefresh() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("create"); m.editName("New target"); m.save(context) }
        val created = "target:" + "e".repeat(32)
        main { h.current = h.current.copy(generation = 8); h.sync() }
        main { h.complete(2, h.state(2, revision = 1, id = created), committed = true) }
        assertFalse(m.dirty); assertEquals(created, m.view.selectedTargetId)
        assertEquals(created, h.inputs.last().view.selectedTargetId); assertEquals(4, h.inputs.size)
        main { h.complete(3, h.state(3, revision = 1, id = created)) }
        assertEquals(created, m.detail!!.entry.id)
    }
    @Test fun invalidDraftAndRejectedSaveRetainEveryInputUntilExplicitCancel() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("update_values"); m.editField(0, "101"); m.editField(7, "not a number"); m.save(context) }
        assertEquals(2, h.pending.size); assertEquals("not a number", m.draft!!.fields[7]); assertNotNull(m.error)
        main { m.editField(0, "100"); m.editField(7, "0"); m.save(context) }
        main { h.fail("stale_target") }
        assertTrue(m.dirty); assertTrue(m.conflict); assertFalse(m.canSave); assertEquals("0", m.draft!!.fields[7])
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
        main { m.begin("update_values"); m.editField(7, "42"); m.reload(context) }
        main { h.fail("missing_target") }
        assertTrue(m.dirty); assertTrue(m.conflict); assertNull(m.view.selectedTargetId); assertEquals("42", m.draft!!.fields[7])
        main { m.reload(context) }; main { h.complete() }
        assertNull(m.detail); assertTrue(m.dirty)
        main { m.cancelDraft(); m.select(context, target) }; main { h.complete() }
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
        assertEquals(3L, OfflineFeatureCodec.integer(args.get("revision")))
        assertEquals(target, args.getString("target_id"))
    }
    @Test fun builtinsAreReadOnlyAndDuplicateOnlySendsIdentityAndName() {
        val h = Harness(); main { h.sync() }; main { h.complete(value = h.state(id = "target:builtin:-149")) }
        val m = h.model
        main { m.begin("update_values"); m.begin("rename"); m.confirmDelete() }
        assertFalse(m.dirty); assertNull(m.deleteConfirmation)
        main { m.begin("duplicate"); m.editName("Independent"); m.save(context) }
        assertEquals("duplicate", h.inputs.last().operation)
        assertEquals(setOf("target_id", "revision", "name"), OfflineFeatureCodec.parse(h.inputs.last().argumentsJson).keys().asSequence().toSet())
    }
    @Test fun startFailureReleasesOwnershipAndUncertainCompletionKeepsDraft() {
        val h = Harness(); h.loadSelected(); val m = h.model
        main { m.begin("rename"); m.editName("Retained"); h.throwOnStart = true; m.save(context) }
        assertFalse(m.busy); assertTrue(m.dirty); assertNotNull(m.error)
        main { h.throwOnStart = false; m.save(context) }
        main { h.pending.last().completeExceptionally(IllegalStateException("unknown")) }
        assertFalse(m.busy); assertTrue(m.dirty); assertTrue(m.error!!.contains("restart"))
    }
    @Test fun clearedModelNeverPublishesLateReplyOrStartsPendingReload() {
        val h = Harness(); val store = ViewModelStore(); val m = h.model
        main { store.put("target", m); h.sync(); m.search(context, "pending"); store.clear() }
        main { h.complete(0) }
        assertNull(m.state); assertFalse(m.busy); assertEquals(1, h.pending.size)
    }
}
