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
class OfflineRemoteRepairModelTest {
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
        val requests = mutableListOf<OfflineRemoteRepairRequest>()
        val flags = mutableListOf<AtomicBoolean>()
        val pending = mutableListOf<CompletableFuture<OfflineRemoteRepairResult>>()
        val model = OfflineRemoteRepairModel(engineState = { engine }, featureContext = { sourceContext }, library = { rows },
            activeFitId = { active }, read = { _, request, flag ->
                if (throwOnStart) throw IllegalStateException("Synthetic launch failure")
                requests.add(request); flags.add(flag)
                CompletableFuture<OfflineRemoteRepairResult>().also(pending::add)
            })
        fun sync() { model.synchronize(sourceContext, rows) }
        fun success(index: Int = pending.lastIndex): OfflineRemoteRepairResult {
            val request = requests[index]
            return OfflineRemoteRepairResult(request.requestId, true, request, request.fits.map { (id, revision) ->
                OfflineRemoteRepairSeries(id, revision, OfflineRemoteRepairSourceRates(1.0, 2.0, 3.0),
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
        val changes: List<(OfflineRemoteRepairModel) -> Unit> = listOf(
            { it.rangeLow("2") }, { it.rangeHigh("80") }, { it.ancillary(false) }, { it.lockRange(false) },
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
            assertEquals(m.ancillaryReload, expected.ancillaryReload); assertEquals(m.ignoreLockRange, expected.ignoreLockRange)
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
            h.sync(); h.model.select("other"); h.model.rangeHigh("75.25"); h.model.ancillary(false)
            h.model.plot(context)
            h.rows = listOf(fit(revision = 8), fit("other")); h.sync()
            assertTrue(h.model.busy); assertTrue(h.model.cancelling); assertTrue(h.flags.single().get())
            h.model.plot(context); assertEquals(1, h.pending.size)
            assertEquals(setOf("fit", "other"), h.model.selected); assertEquals("75.25", h.model.high)
            assertFalse(h.model.ancillaryReload)
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
        main { h.pending.last().complete(OfflineRemoteRepairResult(h.requests.last().requestId, false, h.requests.last(),
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
            h.sync(); h.model.rangeHigh("77"); h.model.ancillary(false)
            h.model.fitPage(1); assertEquals(1, h.model.page); h.model.select("fit-30")
            h.model.fitPage(2); assertEquals(2, h.model.page); h.model.select("fit-69")
            h.model.fitPage(99); assertEquals(2, h.model.page)
            h.model.cancel(); h.sync()
            assertEquals(setOf("fit-0", "fit-30", "fit-69"), h.model.selected)
            assertEquals("77", h.model.high); assertFalse(h.model.ancillaryReload); assertEquals(2, h.model.page)
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
    @Test fun selectedTimeDraftEditsCancelBackAndLateCompletionKeepActualWorkerOwnership() {
        val h = Harness(); val m = h.model
        main {
            h.sync(); m.selectedTime("3000"); m.plot(context)
            assertEquals(3000.0, h.requests.single().time!!, 0.0)
            m.selectedTime("-2"); m.selectedTime("0"); m.stop(); m.cancel(); h.sync(); m.plot(context)
            assertEquals("0", m.time); assertTrue(m.busy); assertTrue(m.cancelling)
            assertEquals(1, h.requests.size); assertTrue(h.flags.single().get())
        }
        main { h.pending.single().complete(h.success()) }
        assertNull(m.currentResult); assertFalse(m.busy)
        main { m.plot(context) }
        assertEquals(0.0, h.requests.last().time!!, 0.0); assertEquals(2, h.requests.last().version)
        main { h.pending.last().complete(h.success()); m.selectedTime(" "); m.plot(context) }
        assertNull(m.currentResult); assertNull(h.requests.last().time); assertEquals(1, h.requests.last().version)
        main { h.pending.last().complete(h.success()) }
    }

    @Test fun invalidSelectedTimesNeverCoerceToZeroOrLoseDraftAndSelection() {
        val h = Harness(); val m = h.model
        for (bad in listOf("bad", "NaN", "Infinity", "-Infinity", "1e309")) {
            main { h.sync(); m.selectedTime(bad); m.plot(context) }
            assertTrue(h.pending.isEmpty()); assertFalse(m.busy); assertNotNull(m.error)
            assertEquals(bad, m.time); assertEquals(setOf("fit"), m.selected)
        }
        main { m.selectedTime(" -0.0 "); m.plot(context) }
        assertEquals(java.lang.Double.doubleToRawLongBits(-0.0), java.lang.Double.doubleToRawLongBits(h.requests.single().time!!))
        main { h.pending.single().complete(h.success()) }
        assertNotNull(m.currentResult)
    }

    @Test fun amountBlankAndInvalidDraftsNeverLaunchAndExplicitZeroDoes() {
        val h = Harness(); val m = h.model
        main { h.sync(); m.selectOrdinate(OfflineRemoteRepairOrdinate.AMOUNT) }
        for (bad in listOf("", " ", "bad", "NaN", "Infinity", "-Infinity", "1e309")) {
            main { m.selectedTime(bad); m.plot(context) }
            assertTrue(h.requests.isEmpty()); assertFalse(m.busy); assertNotNull(m.error)
            if (bad.isBlank()) assertTrue(m.error!!.contains("requires a finite selected time"))
            assertEquals(bad, m.time); assertEquals(setOf("fit"), m.selected)
            assertEquals(OfflineRemoteRepairOrdinate.AMOUNT, m.ordinate)
        }
        main { m.selectedTime(" -0.0 "); m.plot(context) }
        assertEquals(OfflineRemoteRepairOrdinate.AMOUNT, h.requests.single().ordinate)
        assertEquals(2, h.requests.single().version)
        assertEquals(java.lang.Double.doubleToRawLongBits(-0.0), java.lang.Double.doubleToRawLongBits(h.requests.single().time!!))
        main { h.pending.single().complete(h.success()) }
        assertNotNull(m.currentResult)
        main { m.selectOrdinate(OfflineRemoteRepairOrdinate.RATE) }
        assertNull(m.currentResult); assertEquals(" -0.0 ", m.time)
        main { m.selectedTime(""); m.plot(context) }
        assertEquals(1, h.requests.last().version); assertNull(h.requests.last().time)
        main { h.pending.last().complete(h.success()) }
    }

    @Test fun ordinateSwitchAndSwitchBackInvalidateCallbacksWithoutReleasingWorkerOrDrafts() {
        val h = Harness(); val m = h.model
        main {
            h.sync(); m.selectedTime("3000"); m.plot(context)
            m.selectOrdinate(OfflineRemoteRepairOrdinate.AMOUNT); m.plot(context)
            assertTrue(m.busy); assertTrue(m.cancelling); assertFalse(m.canPlot)
            assertTrue(h.flags.single().get()); assertEquals(1, h.requests.size)
            m.selectOrdinate(OfflineRemoteRepairOrdinate.RATE); m.cancel(); h.sync(); m.plot(context)
            assertEquals("3000", m.time); assertEquals(setOf("fit"), m.selected)
            assertEquals(1, h.requests.size)
        }
        main { h.pending.single().complete(h.success()) }
        assertFalse(m.busy); assertNull(m.currentResult)
        main { m.selectOrdinate(OfflineRemoteRepairOrdinate.AMOUNT); m.plot(context) }
        assertEquals(OfflineRemoteRepairOrdinate.AMOUNT, h.requests.last().ordinate)
        main { m.selectOrdinate(OfflineRemoteRepairOrdinate.RATE); m.plot(context) }
        assertEquals(2, h.requests.size); assertTrue(m.busy)
        main { h.pending.last().completeExceptionally(IllegalStateException("Late amount failure")) }
        assertNull(m.currentResult); assertNull(m.error); assertFalse(m.busy)
        main { m.selectOrdinate(OfflineRemoteRepairOrdinate.AMOUNT); m.plot(context) }
        main { h.pending.last().complete(h.success()) }
        assertNotNull(m.currentResult)
        main { m.selectOrdinate(OfflineRemoteRepairOrdinate.AMOUNT) }
        assertNotNull(m.currentResult) // Reselecting the same ordinate is not an edit.
    }


    @Test fun axisSwitchRetainsIndependentDraftsAndOwnsBusyWorkerAcrossAllModes() {
        val h = Harness(); val m = h.model
        main {
            h.sync(); m.rangeLow("2"); m.rangeHigh("75"); m.selectedTime("9"); m.plot(context)
            m.selectAxis(OfflineRemoteRepairAxis.TIME); m.rangeLow("-2"); m.rangeHigh("3000"); m.selectedDistance("0")
            m.selectOrdinate(OfflineRemoteRepairOrdinate.AMOUNT); m.plot(context)
            assertTrue(m.busy); assertTrue(m.cancelling); assertTrue(h.flags.single().get()); assertEquals(1, h.requests.size)
            m.cancel(); h.sync(); m.selectAxis(OfflineRemoteRepairAxis.DISTANCE)
            assertEquals("2", m.low); assertEquals("75", m.high); assertEquals("9", m.time)
            m.selectAxis(OfflineRemoteRepairAxis.TIME)
            assertEquals("-2", m.low); assertEquals("3000", m.high); assertEquals("0", m.distance)
        }
        main { h.pending.single().complete(h.success()) }
        assertFalse(m.busy); assertNull(m.currentResult)
        for (ordinate in OfflineRemoteRepairOrdinate.values()) {
            main { m.selectOrdinate(ordinate); m.plot(context) }
            val request = h.requests.last()
            assertEquals(OfflineRemoteRepairAxis.TIME, request.axis); assertNull(request.time)
            assertEquals(0.0, request.distance!!, 0.0); assertEquals(-2.0, request.low, 0.0)
            assertEquals(3000.0, request.high, 0.0); assertEquals(2, request.version)
            main { m.selectedDistance(""); m.plot(context) }
            assertTrue(m.busy); assertTrue(h.flags.last().get())
            main { h.pending.last().complete(h.success()) }
            assertNull(m.currentResult)
            main { m.plot(context) }; assertNull(h.requests.last().distance)
            main { h.pending.last().complete(h.success()); m.selectedDistance("0") }
        }
    }

    @Test fun timeAxisIgnoresRetainedInvalidSecondaryTimeButRejectsInvalidDistanceAndRange() {
        val h = Harness(); val m = h.model
        main { h.sync(); m.selectedTime("invalid retained time"); m.selectAxis(OfflineRemoteRepairAxis.TIME); m.selectOrdinate(OfflineRemoteRepairOrdinate.AMOUNT) }
        for (bad in listOf("bad", "NaN", "Infinity", "-1", "1e308")) {
            main { m.selectedDistance(bad); m.plot(context) }
            assertTrue(h.requests.isEmpty()); assertEquals(bad, m.distance); assertNotNull(m.error)
        }
        main { m.selectedDistance(""); m.rangeLow("-10"); m.rangeHigh("-1"); m.plot(context) }
        assertNull(h.requests.single().time); assertNull(h.requests.single().distance)
        assertEquals(0.0, h.requests.single().effectiveHigh, 0.0)
        main { h.pending.single().complete(h.success()); m.selectAxis(OfflineRemoteRepairAxis.DISTANCE); m.plot(context) }
        assertEquals("invalid retained time", m.time); assertEquals(1, h.requests.size); assertNotNull(m.error)
    }

    @Test fun timePlotBoundsRetainTerminalBackwardsAndInitialOnlyOvershootOrder() {
        val request = OfflineRemoteRepairRequest("shape", OfflineContext("session", "a".repeat(64), 1), linkedMapOf("fit" to 1L),
            low = -1.0, high = 3.0, axis = OfflineRemoteRepairAxis.TIME)
        val xs = listOf(0.0, 6.0, 6.0, 3.0)
        val result = OfflineRemoteRepairResult("shape", true, request,
            listOf(OfflineRemoteRepairSeries("fit", 1L, OfflineRemoteRepairSourceRates(1.0, 2.0, 3.0), xs, listOf(0.0, 0.0, 256.0, 256.0))), null)
        assertEquals(0.0, result.plotLow, 0.0); assertEquals(6.0, result.plotHigh, 0.0)
        assertSame(xs, result.series.single().x)
        val single = result.copy(series = result.series.map { it.copy(x = listOf(3.0), y = listOf(17.0)) })
        assertEquals(0.0, single.plotLow, 0.0); assertEquals(3.0, single.plotHigh, 0.0)
    }
}
