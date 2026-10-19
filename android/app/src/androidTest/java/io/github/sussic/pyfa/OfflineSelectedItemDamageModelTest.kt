package io.github.sussic.pyfa

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Held replies test ownership only. They are not engine or device execution evidence. */
@RunWith(AndroidJUnit4::class)
class OfflineSelectedItemDamageModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private inner class Harness {
        var current = OfflineContext("a".repeat(32), "c".repeat(64), 7)
        var fit: String? = "f".repeat(32)
        var revision: Long? = 2
        var item: Int? = 210
        var epoch = 0L
        var fitEpoch = 0L
        var ready = true
        var throwOnStart = false
        val inputs = mutableListOf<OfflineDamageRequest>()
        val pending = mutableListOf<CompletableFuture<OfflineDamageResponse>>()
        val model = OfflineSelectedItemDamageModel(featureContext = { current }, activeFit = { fit }, fitRevision = { revision },
            selectedItem = { item }, navigationEpoch = { epoch }, fitNavigationEpoch = { fitEpoch }, engineAvailable = { ready }, request = { _, input ->
                if (throwOnStart) throw IllegalStateException("Definite start failure")
                inputs.add(input); CompletableFuture<OfflineDamageResponse>().also(pending::add)
            })
        fun sync() = model.synchronize(context)
        fun select(id: Int?) { item = id; epoch++; sync() }
        fun state(index: Int = inputs.lastIndex, source: OfflineContext = inputs[index].context,
            fitRevision: Long = 2, available: Boolean = true): OfflineDamageState {
            val input = inputs[index]
            val raw = OfflineDamageValues(mapOf("emAmount" to 0L, "thermalAmount" to 0L, "kineticAmount" to 83.0, "explosiveAmount" to 0L))
            val selected = OfflineDamageItem(OfflineFeatureCodec.parse(input.argumentsJson).getInt("item_id"), "Synthetic item", true,
                available, if (available) null else "zero_total", if (available) raw else OfflineDamageValues(DAMAGE_PATTERN_FIELDS.associateWith { 0L }))
            return OfflineDamageState(source, input.fitId, fitRevision, OfflineDamageSelection("anonymous", null, null, null),
                input.view, 0, emptyList(), null, OfflineHistory(0, 0, 100, null, null), selected)
        }
        fun complete(index: Int = inputs.lastIndex, value: OfflineDamageState = state(index), committed: Boolean = false) {
            pending[index].complete(OfflineDamageResponse(inputs[index].requestId, true, committed, false, value, null, null))
        }
        fun load() { main { sync() }; main { complete() } }
    }
    @Test fun readIsNotSavingAndExactIdentityOnlyApplyCannotRepeat() {
        val h = Harness(); main { h.sync() }
        assertTrue(h.model.busy); assertFalse(h.model.saving); assertFalse(h.model.canApply)
        main { h.complete() }; assertTrue(h.model.canApply)
        main { h.model.apply(context); h.model.apply(context); h.model.reload(context) }
        assertEquals(2, h.inputs.size); assertTrue(h.model.saving)
        val input = h.inputs.last(); assertEquals("apply_item", input.operation)
        val args = OfflineFeatureCodec.parse(input.argumentsJson)
        assertEquals(setOf("item_id", "fit_revision"), args.keys().asSequence().toSet())
        assertEquals(210, args.getInt("item_id")); assertEquals(2, args.getInt("fit_revision"))
    }
    @Test fun newerItemQueuesOneReadAndOldReplyCannotReplaceCard() {
        val h = Harness(); main { h.sync(); h.select(185); h.select(12565) }
        assertEquals(1, h.inputs.size)
        main { h.complete(0) }; assertNull(h.model.currentItem); assertEquals(2, h.inputs.size)
        assertEquals(12565, OfflineFeatureCodec.parse(h.inputs.last().argumentsJson).getInt("item_id"))
        main { h.complete() }; assertEquals(12565, h.model.currentItem!!.itemId)
    }
    @Test fun backAndSameItemReentryUsesNavigationEpochNotJustId() {
        val h = Harness(); main { h.sync(); h.select(null); h.select(210) }
        main { h.complete(0) }; assertNull(h.model.currentItem); assertEquals(2, h.inputs.size)
        main { h.complete() }; assertEquals(210, h.model.currentItem!!.itemId)
    }
    @Test fun liveSelectionGuardWorksBeforeCompositionSynchronizes() {
        val h = Harness(); h.load()
        main { h.item = 185; h.epoch++; h.model.apply(context) }
        assertEquals(1, h.inputs.size); assertNull(h.model.currentItem); assertFalse(h.model.canApply)
    }
    @Test fun ownPublicationBeforeCallbackAcceptsOnlyExactPublishedContext() {
        val h = Harness(); h.load(); main { h.model.apply(context) }
        main { h.current = h.current.copy(generation = 8); h.revision = 3; h.sync() }
        assertEquals(2, h.inputs.size)
        main { h.complete(1, h.state(1, h.current, 3), true) }
        assertEquals(2, h.inputs.size); assertTrue(h.model.canApply)
        assertTrue(h.model.message!!.contains("every fit"))
    }
    @Test fun completedApplyAfterBackCannotRepopulateOrNavigate() {
        val h = Harness(); h.load(); main { h.model.apply(context); h.select(null) }
        main { h.current = h.current.copy(generation = 8); h.revision = 3; h.complete(1, h.state(1, h.current, 3), true) }
        assertNull(h.model.currentItem); assertNull(h.model.message); assertEquals(2, h.inputs.size)
    }
    @Test fun fitSwitchAndReopenNeverAcceptOlderResult() {
        val h = Harness(); main { h.sync(); h.fit = "e".repeat(32); h.sync() }
        main { h.complete(0) }; assertNull(h.model.currentItem); assertEquals(2, h.inputs.size)
        main { h.current = h.current.copy(sessionId = "d".repeat(32), generation = 1); h.sync() }
        main { h.pending[1].completeExceptionally(IllegalStateException("Old read failed")) }
        assertFalse(h.model.reopenRequired); assertEquals(3, h.inputs.size)
        main { h.complete(2) }; assertTrue(h.model.canApply)
    }
    @Test fun malformedItemOptionsIsRecoverableButMalformedApplyRequiresReopen() {
        val h = Harness(); main { h.sync() }
        main { h.pending[0].completeExceptionally(BridgeProtocolException("Malformed preview")) }
        assertFalse(h.model.reopenRequired); assertFalse(h.model.busy); assertNotNull(h.model.error)
        main { h.model.reload(context) }; main { h.complete() }; assertTrue(h.model.canApply)
        main { h.model.apply(context) }; main { h.pending.last().completeExceptionally(BridgeProtocolException("Malformed mutation")) }
        assertTrue(h.model.reopenRequired); assertFalse(h.model.canApply)
        val count = h.inputs.size; main { h.model.apply(context); h.model.reload(context) }; assertEquals(count, h.inputs.size)
    }
    @Test fun genuineReopenRequiredDisablesReadAndOnlyNewSessionRecovers() {
        val h = Harness(); main { h.sync() }
        main { h.pending[0].complete(OfflineDamageResponse(h.inputs[0].requestId, false, null, true, null, null,
            OfflineFeatureError("reopen_required", "Restart required"))) }
        assertTrue(h.model.reopenRequired)
        main { h.select(185); h.model.reload(context) }; assertEquals(1, h.inputs.size)
        main { h.current = h.current.copy(sessionId = "d".repeat(32), generation = 1); h.sync() }
        assertFalse(h.model.reopenRequired); assertEquals(2, h.inputs.size)
    }
    @Test fun unavailableOrStalePreviewCannotSubmit() {
        val h = Harness(); main { h.sync() }; main { h.complete(value = h.state(available = false)) }
        main { h.model.apply(context) }; assertEquals(1, h.inputs.size); assertFalse(h.model.canApply)
        main { h.model.reload(context) }; main { h.complete() }
        main { h.current = h.current.copy(generation = 8); h.model.apply(context) }
        assertEquals(2, h.inputs.size); assertFalse(h.model.canApply)
    }
    @Test fun synchronousStartFailureAndClosedCardReleaseWithoutRetryingMutation() {
        val h = Harness(); main { h.throwOnStart = true; h.sync() }
        assertFalse(h.model.busy); assertFalse(h.model.reopenRequired)
        main { h.throwOnStart = false; h.model.reload(context) }; main { h.complete() }
        main { h.model.apply(context); h.model.close() }; main { h.complete(1) }
        assertNull(h.model.currentItem); assertNull(h.model.message); assertFalse(h.model.canApply)
    }
    @Test fun separateItemActionNeverReplacesOrSavesAnUnrelatedLibraryDraft() {
        val h = Harness()
        val libraryReplies = mutableListOf<CompletableFuture<OfflineDamageResponse>>()
        val libraryInputs = mutableListOf<OfflineDamageRequest>()
        val library = OfflineDamagePatternsModel(featureContext = { h.current }, activeFit = { h.fit }, engineAvailable = { true },
            request = { _, input -> libraryInputs.add(input); CompletableFuture<OfflineDamageResponse>().also(libraryReplies::add) })
        main { library.synchronize(context, h.current, h.fit, h.revision) }
        main { libraryReplies[0].complete(OfflineDamageResponse(libraryInputs[0].requestId, true, false, false,
            OfflineDamageState(h.current, h.fit, h.revision, OfflineDamageSelection("anonymous", null, null, null),
                OfflineDamageView(), 0, emptyList(), null, OfflineHistory(0, 0, 100, null, null)), null, null)) }
        main { library.begin("create"); library.editName("Keep this draft"); library.editField(0, "invalid") }
        val draft = library.draft; h.load(); main { h.model.apply(context) }
        main { h.current = h.current.copy(generation = 8); h.revision = 3; h.sync() }
        main { h.complete(1, h.state(1, h.current, 3), true) }
        assertSame(draft, library.draft); assertTrue(library.dirty); assertEquals(1, libraryInputs.size)
        assertFalse(h.inputs.last().argumentsJson.contains("values"))
    }
    @Test fun fitAtoBtoAInvalidatesHeldReplyEvenWithIdenticalFinalContextAndRevision() {
        val h = Harness(); main { h.sync() }
        val original = h.fit
        main { h.fit = "e".repeat(32); h.fitEpoch++; h.sync(); h.fit = original; h.fitEpoch++; h.sync() }
        main { h.complete(0) }
        assertNull(h.model.currentItem); assertEquals(2, h.inputs.size)
        main { h.complete(1) }; assertTrue(h.model.canApply)
        main { h.model.apply(context); h.fit = "e".repeat(32); h.fitEpoch++; h.fit = original; h.fitEpoch++ }
        main { h.complete(2) }
        assertNull(h.model.currentItem); assertNull(h.model.message)
    }
    @Test fun heldApplyFromPreviousSessionCannotPoisonOrAttachToReopenedCard() {
        for (uncertain in listOf(false, true)) {
            val h = Harness(); h.load(); main { h.model.apply(context) }
            main { h.current = h.current.copy(sessionId = "d".repeat(32), generation = 1); h.sync() }
            main {
                if (uncertain) h.pending[1].completeExceptionally(BridgeProtocolException("Previous session mutation uncertain"))
                else h.complete(1, h.state(1, h.inputs[1].context.copy(generation = 8), fitRevision = 3), true)
            }
            assertFalse(h.model.reopenRequired); assertNull(h.model.currentItem); assertNull(h.model.message)
            assertEquals(3, h.inputs.size); assertEquals(h.current, h.inputs[2].context)
            main { h.complete(2) }; assertTrue(h.model.canApply)
        }
    }
}
