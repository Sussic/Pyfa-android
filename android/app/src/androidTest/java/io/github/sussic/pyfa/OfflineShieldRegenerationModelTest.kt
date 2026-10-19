package io.github.sussic.pyfa

import androidx.lifecycle.ViewModelStore
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.concurrent.CompletableFuture
import java.util.concurrent.atomic.AtomicBoolean
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

/** Held synthetic reads exercise native ownership; numerical reference proof is independent. */
@RunWith(AndroidJUnit4::class)
class OfflineShieldRegenerationModelTest {
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
        var onStart: (() -> Unit)? = null
        val requests = mutableListOf<OfflineShieldRegenerationRequest>()
        val flags = mutableListOf<AtomicBoolean>()
        val pending = mutableListOf<CompletableFuture<OfflineShieldRegenerationResult>>()
        val model = OfflineShieldRegenerationModel(engineState = { engine }, featureContext = { sourceContext }, library = { rows },
            activeFitId = { active }, read = { _, request, flag ->
                onStart?.invoke()
                if (throwOnStart) throw IllegalStateException("Synthetic launch failure")
                requests.add(request); flags.add(flag)
                CompletableFuture<OfflineShieldRegenerationResult>().also(pending::add)
            })
        fun sync() { model.synchronize(sourceContext, rows) }
        fun success(index: Int = pending.lastIndex): OfflineShieldRegenerationResult {
            val request = requests[index]
            return OfflineShieldRegenerationResult(request.requestId, true, request, request.fits.map { (id, revision) ->
                OfflineShieldRegenerationSeries(id, revision, OfflineShieldRegenerationSource(2500.0, 700.0,
                    linkedMapOf("em" to 1.0, "thermal" to 2.0, "kinetic" to 3.0, "explosive" to 4.0)), listOf(0.0), listOf(1.0))
            }, null)
        }
    }

    @Test fun everyOneOfTwelveModesRetainsItsOwnRangeAndStartDrafts() {
        val h = Harness(); var index = 0
        main {
            h.sync()
            for (effective in listOf(false, true)) for (x in OfflineShieldRegenerationX.values()) for (y in OfflineShieldRegenerationY.values()) {
                h.model.effective(effective); h.model.xAxis(x); h.model.yAxis(y)
                assertEquals("0", h.model.low); assertEquals(if (x == OfflineShieldRegenerationX.TIME) "300" else "100", h.model.high)
                h.model.rangeLow("low-$index"); h.model.rangeHigh("high-$index"); h.model.startingShield("start-$index"); index++
            }
            index = 0
            for (effective in listOf(false, true)) for (x in OfflineShieldRegenerationX.values()) for (y in OfflineShieldRegenerationY.values()) {
                h.model.effective(effective); h.model.xAxis(x); h.model.yAxis(y)
                assertEquals("low-$index", h.model.low); assertEquals("high-$index", h.model.high); assertEquals("start-$index", h.model.startingShield); index++
            }
            h.model.cancel(); h.sync()
            assertEquals("high-11", h.model.high); assertEquals(setOf("fit"), h.model.selected)
        }
        assertEquals(12, index); assertTrue(h.pending.isEmpty())
    }

    @Test fun blankStartIsNullSignedReversedFiniteInputsAreAcceptedAndHiddenStartIsNeverSent() {
        val h = Harness()
        main { h.sync(); h.model.rangeLow("300"); h.model.rangeHigh("-50"); h.model.startingShield(" "); h.model.plot(context) }
        assertNull(h.requests.single().startingShieldPercent); assertEquals(300.0, h.requests.single().low, 0.0); assertEquals(-50.0, h.requests.single().high, 0.0)
        main { h.pending.single().complete(h.success()) }
        main { h.model.startingShield("invalid retained start"); h.model.xAxis(OfflineShieldRegenerationX.AMOUNT); h.model.plot(context) }
        assertNull(h.requests.last().startingShieldPercent)
        main { h.pending.last().complete(h.success()) }
        main { h.model.xAxis(OfflineShieldRegenerationX.TIME); h.model.plot(context) }
        assertEquals(2, h.requests.size); assertEquals("invalid retained start", h.model.startingShield); assertNotNull(h.model.error)
        main { h.model.startingShield("-100"); h.model.rangeHigh("1e308"); h.model.plot(context) }
        assertEquals(-100.0, h.requests.last().startingShieldPercent!!, 0.0); assertEquals(1e308, h.requests.last().high, 0.0)
        main { h.pending.last().complete(h.success()) }
    }

    @Test fun cancelBackAndRepeatedPlotRetainOneWorkerUntilActualCompletion() {
        val h = Harness(); val m = h.model
        main {
            h.sync(); m.plot(context); m.plot(context); m.stop(); m.plot(context); m.cancel(); h.sync(); m.plot(context)
            assertTrue(m.busy); assertTrue(m.cancelling); assertFalse(m.canPlot)
            assertTrue(h.flags.single().get()); assertNull(m.currentResult); assertEquals(1, h.pending.size)
        }
        main { h.pending.single().complete(h.success()) }
        assertFalse(m.busy); assertNull(m.currentResult)
        main { m.plot(context); m.plot(context) }
        assertEquals(2, h.pending.size); assertFalse(h.flags.last().get())
        main {
            assertFalse(h.pending.first().complete(h.success(0))) // An old completion cannot release the new owner.
            assertTrue(m.busy); assertFalse(m.canPlot)
            h.pending.last().complete(h.success())
        }
        assertTrue(m.currentResult!!.ok); assertFalse(m.busy)
    }

    @Test fun eachInputSelectionOrSourceChangeCancelsAndInvalidatesWithoutDroppingOwnership() {
        val changes: List<(Harness) -> Unit> = listOf(
            { it.model.rangeLow("2") }, { it.model.rangeHigh("80") }, { it.model.startingShield("25") },
            { it.model.xAxis(OfflineShieldRegenerationX.AMOUNT) }, { it.model.yAxis(OfflineShieldRegenerationY.RATE) },
            { it.model.effective(true) }, { it.model.select("other") },
            { it.rows = listOf(fit(revision = 8), fit("other")); it.sync() },
            { it.sourceContext = it.sourceContext!!.copy(generation = 2); it.sync() },
        )
        changes.forEach { change ->
            val h = Harness(); h.rows = h.rows + fit("other")
            main { h.sync(); h.model.plot(context); change(h); h.model.plot(context) }
            assertEquals(1, h.pending.size); assertTrue(h.model.busy); assertTrue(h.flags.single().get())
            main { h.pending.single().complete(h.success()) }
            assertNull(h.model.currentResult)
            main { h.model.plot(context) }
            assertEquals(2, h.requests.size)
            main { h.pending.last().complete(h.success()) }
            assertNotNull(h.model.currentResult)
            main { h.model.rangeHigh("invalid draft") }
            assertNull(h.model.currentResult); assertEquals("invalid draft", h.model.high)
        }
    }

    @Test fun callbacksRecheckRevisionContextDeletionAndUnavailableBeforePublishing() {
        for (change in listOf<(Harness) -> Unit>(
            { it.rows = listOf(fit(revision = 8)) }, { it.sourceContext = it.sourceContext!!.copy(generation = 2) },
            { it.rows = emptyList() }, { it.engine = EngineState.Failed("Unavailable") },
            { it.engine = EngineState.Ready(fit(), BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE, "Restart")) },
        )) {
            val h = Harness()
            main { h.sync(); h.model.plot(context); change(h); h.pending.single().complete(h.success()) }
            assertFalse(h.model.busy); assertNull(h.model.currentResult); assertNotNull(h.model.error)
            main { h.sync() }; assertNull(h.model.currentResult)
        }
        val h = Harness()
        main { h.sync(); h.model.plot(context); h.pending.single().complete(h.success()) }
        assertNotNull(h.model.currentResult)
        main { h.rows = listOf(fit(revision = 8)) }
        assertNull(h.model.currentResult) // Hidden before Compose synchronizes.
        main { h.sync() }; assertNull(h.model.result)
    }

    @Test fun launchErrorsWorkerErrorsAndReentrantCancellationReleaseOnlyTheirOwner() {
        val h = Harness()
        main { h.sync(); h.throwOnStart = true; h.model.plot(context) }
        assertFalse(h.model.busy); assertNotNull(h.model.error); assertTrue(h.pending.isEmpty())
        main { h.onStart = { h.model.stop() }; h.model.plot(context) }
        assertFalse(h.model.busy); assertTrue(h.model.error!!.startsWith("Sampling cancelled"))
        main { h.onStart = null; h.throwOnStart = false; h.model.plot(context); h.pending.last().completeExceptionally(IllegalStateException("Worker failure")) }
        assertFalse(h.model.busy); assertNull(h.model.currentResult); assertNotNull(h.model.error)
        for (code in listOf("deadline_exceeded", "invalid_engine_data", "cancelled", "reopen_required")) {
            main { h.model.plot(context); h.pending.last().complete(OfflineShieldRegenerationResult(h.requests.last().requestId, false,
                h.requests.last(), emptyList(), OfflineFeatureError(code, "Sampling failed: $code"))) }
            assertFalse(h.model.busy); assertEquals("Sampling failed: $code", h.model.error)
        }
        main { h.model.plot(context); h.pending.last().complete(h.success()) }
        assertNotNull(h.model.currentResult); assertNull(h.model.error)
    }

    @Test fun viewModelClearingRetainsCancelGateAndSuppressesLatePublication() {
        val h = Harness(); val store = ViewModelStore()
        main { store.put("shield", h.model); h.sync(); h.model.plot(context); store.clear() }
        assertTrue(h.flags.single().get()); assertTrue(h.model.busy)
        main { h.pending.single().complete(h.success()) }
        assertFalse(h.model.busy); assertNull(h.model.currentResult)
    }

    @Test fun paginatedDuplicateNamesSelectionLimitSearchAndExplicitEmptySelectionPersist() {
        val h = Harness(); h.rows = (0..69).map { fit("fit-$it", name = "Duplicate") }; h.active = "fit-0"
        main {
            h.sync(); h.model.rangeHigh("77"); h.model.fitPage(1); h.model.select("fit-30")
            h.model.fitPage(2); h.model.select("fit-69"); h.model.fitPage(99); assertEquals(2, h.model.page)
            h.model.cancel(); h.sync(); assertEquals(2, h.model.page); assertEquals("77", h.model.high)
            assertEquals(setOf("fit-0", "fit-30", "fit-69"), h.model.selected)
            h.model.search("missing"); assertEquals(0, h.model.page); h.model.fitPage(1); assertEquals(0, h.model.page)
            h.model.search("Duplicate"); for (i in 1..5) h.model.select("fit-$i")
            h.model.select("fit-6"); assertEquals(8, h.model.selected.size); h.model.plot(context)
        }
        assertEquals(h.rows.filter { it.id in h.model.selected }.map { it.id }, h.requests.single().fits.keys.toList())
        main { h.pending.single().complete(h.success()); h.model.selected.toList().forEach(h.model::select); h.sync() }
        assertTrue(h.model.selected.isEmpty()); assertFalse(h.model.canPlot)
        main { h.active = "fit-30"; h.sync() }; assertTrue(h.model.selected.isEmpty())
    }

    @Test fun deletionKeepsSurvivingSelectionsAndInvalidDraftsNeverQueueWork() {
        val h = Harness(); h.rows = h.rows + fit("other")
        main {
            h.sync(); h.model.select("other"); h.model.rangeHigh("invalid")
            h.rows = listOf(fit("other")); h.sync()
            assertEquals(setOf("other"), h.model.selected); assertEquals("invalid", h.model.high); assertTrue(h.model.error!!.contains("removed"))
        }
        for (bad in listOf("", "bad", "NaN", "Infinity", "-Infinity")) {
            main { h.model.rangeHigh(bad); h.model.plot(context) }
            assertTrue(h.pending.isEmpty()); assertFalse(h.model.busy); assertNotNull(h.model.error); assertEquals(bad, h.model.high)
        }
        main { h.model.rangeHigh("2"); h.model.rangeLow("5"); h.model.startingShield(""); h.model.plot(context); h.pending.single().complete(h.success()) }
        assertNotNull(h.model.currentResult)
    }
}
