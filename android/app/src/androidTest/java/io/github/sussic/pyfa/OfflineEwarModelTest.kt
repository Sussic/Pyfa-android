package io.github.sussic.pyfa

import androidx.lifecycle.ViewModelStore
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import java.util.concurrent.atomic.AtomicBoolean
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Held synthetic reads test UI ownership and invalidation, never EOS numerical parity. */
@RunWith(AndroidJUnit4::class)
class OfflineEwarModelTest {
    private val instrumentation get() = InstrumentationRegistry.getInstrumentation()
    private val context get() = instrumentation.targetContext
    private fun main(block: () -> Unit) { instrumentation.runOnMainSync { block() }; instrumentation.waitForIdleSync() }
    private fun fit(id: String = "fit", revision: Long = 7L, name: String = "Source") = FitSnapshot(id, revision, name, "Vexor",
        emptyMap(), emptyList(), emptyMap(), emptyList(), emptyList(), emptyList())
    private inner class Harness {
        var rows = listOf(fit())
        var engine: EngineState = EngineState.Ready(rows.first())
        var sourceContext: OfflineContext? = OfflineContext("session", "a".repeat(64), 1)
        var active: String? = "fit"
        var throwOnStart = false
        val requests = mutableListOf<OfflineEwarRequest>()
        val flags = mutableListOf<AtomicBoolean>()
        val pending = mutableListOf<CompletableFuture<OfflineEwarResult>>()
        val model = OfflineEwarModel(engineState = { engine }, featureContext = { sourceContext }, library = { rows },
            activeFitId = { active }, read = { _, request, flag ->
                if (throwOnStart) throw IllegalStateException("Synthetic launch failure")
                requests.add(request); flags.add(flag)
                CompletableFuture<OfflineEwarResult>().also(pending::add)
            })
        fun sync() { model.synchronize(sourceContext, rows) }
        fun success(index: Int = pending.lastIndex): OfflineEwarResult {
            val request = requests[index]
            return OfflineEwarResult(request.requestId, true, request, request.fits.map { (id, revision) ->
                OfflineEwarSeries(id, revision,
                    (0..50).map { request.low + (request.high - request.low) / 50.0 * it }, List(51) { 6.0 })
            }, null)
        }
    }

    @Test fun cancelRepeatedPlotAndLeaveKeepOneWorkerUntilItsActualCompletion() {
        val h = Harness(); val m = h.model
        main {
            h.sync(); m.plot(context); m.plot(context)
            assertEquals(1, h.pending.size); assertTrue(m.busy); assertFalse(m.canPlot)
            m.stop(); m.plot(context); m.cancel(); h.sync(); m.plot(context)
            assertTrue(h.flags.single().get()); assertTrue(m.busy); assertTrue(m.cancelling)
            assertNull(m.currentResult); assertEquals(1, h.pending.size)
        }
        main { h.pending.single().complete(h.success()) }
        assertFalse(m.busy); assertFalse(m.cancelling); assertNull(m.currentResult)
        main { m.plot(context); m.plot(context) }
        assertEquals(2, h.pending.size); assertFalse(h.flags.last().get())
        main { h.pending.last().complete(h.success()) }
        assertTrue(m.currentResult!!.ok); assertTrue(m.canPlot)
    }

    @Test fun everyGraphInputInvalidatesPendingAndCompletedSamplesButKeepsDrafts() {
        val changes: List<(OfflineEwarModel) -> Unit> = listOf(
            { it.rangeLow("2") }, { it.rangeHigh("80") }, { it.selectedResistance("37.5") }, { it.selectOrdinate(OfflineEwarOrdinate.GUIDANCE) }, { it.lockRange(false) },
            { it.droneControlRange(true) }, { it.select("other") },
        )
        changes.forEach { change ->
            val h = Harness(); h.rows = h.rows + fit("other"); val m = h.model
            main { h.sync(); m.plot(context); change(m); m.plot(context) }
            assertEquals(1, h.pending.size); assertTrue(m.busy); assertTrue(h.flags.single().get())
            main { h.pending.single().complete(h.success()) }
            assertNull(m.currentResult)
            main { m.plot(context) }
            val expected = h.requests.last()
            assertEquals(m.low.toDouble(), expected.low, 0.0); assertEquals(m.high.toDouble(), expected.high, 0.0)
            assertEquals(m.resistance.toDouble(), expected.resistancePercent!!, 0.0); assertEquals(m.ordinate, expected.ordinate); assertEquals(m.ignoreLockRange, expected.ignoreLockRange)
            assertEquals(m.ignoreDroneControlRange, expected.ignoreDroneControlRange); assertEquals(m.selected, expected.fits.keys)
            main { h.pending.last().complete(h.success()) }
            assertNotNull(m.currentResult)
            main { m.rangeHigh("bad draft") }
            assertNull(m.currentResult); assertEquals("bad draft", m.high)
        }
    }

    @Test fun revisionContextDeletionAndUnavailableCallbacksCannotPublishStaleResults() {
        for (change in listOf<(Harness) -> Unit>(
            { it.rows = listOf(fit(revision = 8)) },
            { it.sourceContext = it.sourceContext!!.copy(generation = 2) },
            { it.rows = emptyList() },
            { it.engine = EngineState.Failed("Unavailable") },
            { it.engine = EngineState.Ready(fit(), BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE, "Restart")) },
        )) {
            val h = Harness()
            main { h.sync(); h.model.plot(context); change(h) }
            // Completion rechecks authoritative inputs even before Compose synchronizes.
            main { h.pending.single().complete(h.success()) }
            assertFalse(h.model.busy); assertNull(h.model.currentResult); assertNotNull(h.model.error)
            main { h.sync() }
            assertNull(h.model.currentResult)
        }
        val h = Harness()
        main { h.sync(); h.model.plot(context) }
        main { h.pending.single().complete(h.success()) }
        assertNotNull(h.model.currentResult)
        main { h.rows = listOf(fit(revision = 8)) }
        assertNull(h.model.currentResult) // A stale completed result is hidden immediately.
        main { h.sync() }
        assertNull(h.model.result); assertEquals(setOf("fit"), h.model.selected)
    }

    @Test fun synchronizationRetainsCanceledGateSelectionsAndDraftsAcrossSourceEditAndDeletion() {
        val h = Harness(); h.rows = h.rows + fit("other")
        main {
            h.sync(); h.model.select("other"); h.model.rangeHigh("75.25"); h.model.selectedResistance("-25")
            h.model.plot(context)
            h.rows = listOf(fit(revision = 8), fit("other")); h.sync()
            assertTrue(h.model.busy); assertTrue(h.model.cancelling); assertTrue(h.flags.single().get())
            h.model.plot(context); assertEquals(1, h.pending.size)
            assertEquals(setOf("fit", "other"), h.model.selected); assertEquals("75.25", h.model.high)
            assertEquals("-25", h.model.resistance)
        }
        main { h.pending.single().complete(h.success()) }
        assertNull(h.model.currentResult)
        main { h.rows = listOf(fit("other")); h.sync() }
        assertEquals(setOf("other"), h.model.selected); assertTrue(h.model.error!!.contains("removed"))
        main { h.model.select("other"); h.sync() }
        assertTrue(h.model.selected.isEmpty()); assertFalse(h.model.canPlot)
        main { h.active = "other"; h.sync() }
        assertTrue(h.model.selected.isEmpty())
    }

    @Test fun failureAndSynchronousLaunchFailureReleaseOnlyTheirOwnCompletedGate() {
        val h = Harness()
        main { h.sync(); h.throwOnStart = true; h.model.plot(context) }
        assertFalse(h.model.busy); assertNotNull(h.model.error); assertTrue(h.pending.isEmpty())
        main { h.throwOnStart = false; h.model.plot(context) }
        main { h.pending.last().completeExceptionally(IllegalStateException("Synthetic worker failure")) }
        assertFalse(h.model.busy); assertNotNull(h.model.error); assertNull(h.model.currentResult)
        main { h.model.plot(context) }
        main { h.pending.last().complete(OfflineEwarResult(h.requests.last().requestId, false, h.requests.last(),
            emptyList(), OfflineFeatureError("deadline_exceeded", "Sampling budget exhausted."))) }
        assertEquals("Sampling budget exhausted.", h.model.error); assertFalse(h.model.busy)
        main { h.model.plot(context) }
        main { h.pending.last().complete(h.success()) }
        assertNull(h.model.error); assertTrue(h.model.currentResult!!.ok)
    }

    @Test fun clearingViewModelCancelsWithoutPublishingALateCallback() {
        val h = Harness(); val store = ViewModelStore()
        main { store.put("graph", h.model); h.sync(); h.model.plot(context); store.clear() }
        assertTrue(h.flags.single().get()); assertTrue(h.model.busy)
        main { h.pending.single().complete(h.success()) }
        assertFalse(h.model.busy); assertNull(h.model.currentResult)
    }

    @Test fun duplicateNamesRemainReachableByPageWhileSearchAndEmptySelectionAreRetained() {
        val h = Harness(); h.rows = (0..69).map { fit("fit-$it", name = "Duplicate") }; h.active = "fit-0"
        main {
            h.sync(); h.model.rangeHigh("77"); h.model.selectedResistance("-25")
            h.model.fitPage(1); assertEquals(1, h.model.page); h.model.select("fit-30")
            h.model.fitPage(2); assertEquals(2, h.model.page); h.model.select("fit-69")
            h.model.fitPage(99); assertEquals(2, h.model.page)
            h.model.cancel(); h.sync()
            assertEquals(setOf("fit-0", "fit-30", "fit-69"), h.model.selected)
            assertEquals("77", h.model.high); assertEquals("-25", h.model.resistance); assertEquals(2, h.model.page)
            h.model.search("missing"); assertEquals(0, h.model.page); assertEquals(3, h.model.selected.size)
            h.model.fitPage(1); assertEquals(0, h.model.page)
            h.model.search("Duplicate")
            for (i in 1..5) h.model.select("fit-$i")
            assertEquals(8, h.model.selected.size); h.model.select("fit-6"); assertEquals(8, h.model.selected.size)
            h.model.plot(context)
        }
        assertEquals(h.rows.filter { it.id in h.model.selected }.map { it.id }, h.requests.single().fits.keys.toList())
        main { h.pending.single().complete(h.success()) }
        assertNotNull(h.model.currentResult)
        main { h.model.selected.toList().forEach(h.model::select); h.sync() }
        assertTrue(h.model.selected.isEmpty()); assertFalse(h.model.canPlot)
    }

    @Test fun invalidDraftsNeverQueueWorkAndCanBeCorrectedWithoutLosingSelection() {
        val h = Harness()
        for (bad in listOf("bad", "NaN", "Infinity", "-1", "1e308")) {
            main { h.sync(); h.model.rangeHigh(bad); h.model.plot(context) }
            assertTrue(h.pending.isEmpty()); assertFalse(h.model.busy); assertNotNull(h.model.error)
            assertEquals(bad, h.model.high); assertEquals(setOf("fit"), h.model.selected)
        }
        main { h.model.rangeHigh("1e100"); h.model.plot(context) }
        assertEquals(1, h.pending.size)
        main { h.pending.single().complete(h.success()) }
        assertNotNull(h.model.currentResult)
    }
    @Test fun nullableResistanceAndAllModeSwitchesRetainDraftsAndActualBusyOwnership() {
        val h = Harness(); val m = h.model
        main {
            h.sync(); m.selectedResistance("250"); m.plot(context)
            for (mode in OfflineEwarOrdinate.values()) {
                m.selectOrdinate(mode); m.plot(context)
                assertTrue(m.busy); assertEquals(1, h.requests.size)
            }
            m.selectedResistance(" "); m.stop(); m.cancel(); h.sync(); m.plot(context)
            assertEquals(" ", m.resistance); assertTrue(m.cancelling); assertTrue(h.flags.single().get())
        }
        main { h.pending.single().complete(h.success()) }
        assertNull(m.currentResult); assertFalse(m.busy)
        main { m.plot(context) }
        assertNull(h.requests.last().resistancePercent); assertEquals(OfflineEwarOrdinate.PAINTER, h.requests.last().ordinate)
        main { h.pending.last().complete(h.success()) }
        assertNotNull(m.currentResult)
        main { m.selectOrdinate(OfflineEwarOrdinate.PAINTER) }
        assertNotNull(m.currentResult) // Same mode is not an edit.
        main { m.selectedResistance("-25"); m.plot(context) }
        assertEquals(-25.0, h.requests.last().resistancePercent!!, 0.0)
        assertEquals(0.0, h.requests.last().effectiveResistanceFraction!!, 0.0)
        main { h.pending.last().complete(h.success()) }
        assertEquals("-25", m.resistance)
    }

    @Test fun invalidResistanceNeverQueuesAndZeroIsNotTheUnspecifiedDraft() {
        val h = Harness(); val m = h.model
        for (bad in listOf("bad", "NaN", "Infinity", "-Infinity", "1e309")) {
            main { h.sync(); m.selectedResistance(bad); m.plot(context) }
            assertTrue(h.requests.isEmpty()); assertFalse(m.busy); assertNotNull(m.error)
            assertEquals(bad, m.resistance); assertEquals(setOf("fit"), m.selected)
        }
        for (draft in listOf("", " -0.0 ", "1e100", "-2", "101")) {
            main { m.selectedResistance(draft); m.plot(context) }
            val request = h.requests.last()
            if (draft.isEmpty()) assertNull(request.resistancePercent)
            else assertEquals(draft.trim().toDouble(), request.resistancePercent!!, 0.0)
            main { h.pending.last().complete(h.success()) }
            assertNotNull(m.currentResult); assertEquals(draft, m.resistance)
        }
    }

    @Test fun cancelledLateFailureAndOldCompletedFutureCannotPublishOrFreeTheNextWorker() {
        val h = Harness(); val m = h.model
        main { h.sync(); m.plot(context); m.selectedResistance("37.5") }
        main { h.pending.single().completeExceptionally(IllegalStateException("Late failure")) }
        assertNull(m.error); assertNull(m.currentResult); assertFalse(m.busy)
        main { m.plot(context) }
        assertTrue(m.busy); assertEquals(2, h.requests.size)
        main {
            assertFalse(h.pending.first().complete(h.success(0)))
            m.plot(context); assertTrue(m.busy); assertFalse(h.flags.last().get()); assertEquals(2, h.requests.size)
        }
        main { h.pending.last().complete(h.success()) }
        assertNotNull(m.currentResult); assertEquals(37.5, m.currentResult!!.request.resistancePercent!!, 0.0)
    }

    @Test fun unrelatedResponseIdentityIsNotPublishedAndClearedModelCannotLaunchAgain() {
        val h = Harness(); val m = h.model
        main { h.sync(); m.plot(context) }
        main { h.pending.single().complete(h.success().copy(requestId = "unrelated")) }
        assertFalse(m.busy); assertNull(m.currentResult); assertNotNull(m.error)
        val store = ViewModelStore()
        main { store.put("graph", m); m.plot(context); store.clear(); m.plot(context) }
        assertTrue(m.busy); assertTrue(h.flags.last().get()); assertEquals(2, h.requests.size)
        main { h.pending.last().complete(h.success()); m.plot(context) }
        assertNull(m.currentResult); assertFalse(m.canPlot); assertEquals(2, h.requests.size)
    }
}
