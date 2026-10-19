package io.github.sussic.pyfa

import android.Manifest
import android.content.pm.PackageManager
import android.provider.Settings
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.lifecycle.ViewModelProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import java.util.UUID
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.TimeUnit
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Deferred native gate: offline_features_phase=fighters_recent with disposable data and airplane mode. */
@RunWith(AndroidJUnit4::class)
class FighterRecentUseTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val model get() = ViewModelProvider(compose.activity)[FighterEditorModel::class.java]
    private val equipment get() = ViewModelProvider(compose.activity)[EquipmentModel::class.java]
    private fun fit(id: String) = EngineRuntime.library.value.single { it.id == id }
    private fun waitFor(test: () -> Boolean) { compose.waitUntil(120_000,test); compose.waitForIdle() }
    private fun settled(id: String) = waitFor { !model.loading && !model.editing && model.currentDetails?.fitId == id }
    private fun click(tag: String) { compose.onNodeWithTag(tag).performScrollTo().performClick() }
    private fun create(ship: String): String {
        val old=EngineRuntime.library.value.map { it.id }.toSet()
        assertTrue(EngineRuntime.createEmptyFit(context,ship,"Fighter Recent $ship").get(120,TimeUnit.SECONDS).isSuccess)
        return EngineRuntime.library.value.single { it.id !in old }.id
    }
    private fun browse(item: EquipmentItem) {
        click("fighters-browse")
        compose.onNodeWithTag("equipment-search").performTextReplacement(item.name)
        click("equipment-search-submit"); waitFor { !equipment.busy }
        click("equipment-item-${item.id}")
    }
    private fun assertRecentRows(expected: List<Int>) {
        assertEquals(expected,EngineRuntime.recent.value)
        click("equipment-recent")
        compose.onNodeWithTag("equipment-location").assertTextEquals("Recent use · newest first")
        val rows=compose.onAllNodes(SemanticsMatcher("equipment rows") {
            it.config.getOrElse(SemanticsProperties.TestTag) { "" }.startsWith("equipment-item-")
        }).fetchSemanticsNodes().map { it.config[SemanticsProperties.TestTag].removePrefix("equipment-item-").toInt() }
        assertEquals(expected,rows)
    }
    private fun closeRecent() { click("equipment-back"); click("equipment-back") }
    private fun history(id: String, redo: Boolean) {
        val revision=fit(id).revision
        waitFor { ViewModelProvider(compose.activity)[EditHistoryModel::class.java].options?.revision == revision }
        click(if (redo) "history-redo" else "history-undo")
        waitFor { fit(id).revision > revision }; settled(id)
    }
    private fun rejectedAttempt(id: String, item: EquipmentItem) {
        val before=fit(id)
        val state=EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS)
        val recent=EngineRuntime.recent.value.toList()
        val result=EngineRuntime.request(context,BridgeOperation.AddFighter(id,item.id),mapOf(id to before.revision)).get(120,TimeUnit.SECONDS)
        assertFalse(result.isSuccess); assertEquals(BridgeErrorCode.INVALID_EDIT,result.error!!.code)
        assertEquals(before,fit(id))
        val after=EngineRuntime.offlineFeatureState(context,id).get(30,TimeUnit.SECONDS)
        assertEquals(state.copy(context=after.context),after)
        assertEquals(state.context.sessionId,after.context.sessionId); assertEquals(state.context.datasetSha256,after.context.datasetSha256)
        if (recent.firstOrNull()!=item.id) assertTrue(after.context.generation>state.context.generation)
        assertEquals((listOf(item.id)+recent.filter { it!=item.id }).take(20),EngineRuntime.recent.value)
    }
    @Test fun addRemoveRejectedAttemptHistoryAndQuantityZeroFollowSourceRecentOrder() {
        assertEquals("fighters_recent",InstrumentationRegistry.getArguments().getString("offline_features_phase"))
        assertEquals(1,Settings.Global.getInt(context.contentResolver,Settings.Global.AIRPLANE_MODE_ON))
        assertEquals(PackageManager.PERMISSION_DENIED,context.checkSelfPermission(Manifest.permission.INTERNET))
        EngineRuntime.start(context).get(120,TimeUnit.SECONDS)
        val catalog=EngineRuntime.equipmentCatalog(context).get(30,TimeUnit.SECONDS)
        val first=catalog.items.single { it.name=="Firbolg I" }
        val second=catalog.items.single { it.name=="Firbolg II" }
        val id=create("Thanatos")
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS)
        click("fighters-open"); settled(id)
        for (item in listOf(first,second,first)) {
            val recent=EngineRuntime.recent.value.toList()
            browse(item); click("equipment-add-fighter"); settled(id)
            assertEquals((listOf(item.id)+recent.filter { it!=item.id }).take(20),EngineRuntime.recent.value)
        }
        assertEquals(listOf(first.id,second.id,first.id),model.currentDetails!!.squadrons.map { it.itemId })
        assertEquals(1,EngineRuntime.recent.value.count { it==first.id })
        click("fighters-browse"); assertRecentRows(EngineRuntime.recent.value.toList()); closeRecent()
        val ship=create("Vexor")
        EngineRuntime.selectFit(context,ship).get(30,TimeUnit.SECONDS); settled(ship)
        browse(second)
        val before=fit(ship); val beforeState=EngineRuntime.offlineFeatureState(context,ship).get(30,TimeUnit.SECONDS)
        val recentBefore=EngineRuntime.recent.value.toList()
        val epochBefore=EngineRuntime.featureEpoch.value
        assertEquals(first.id,recentBefore.first())
        click("equipment-add-fighter"); waitFor { !model.editing }
        compose.onNodeWithTag("equipment-fighter-error").assertExists()
        compose.onNodeWithTag("equipment-selected").assertExists() // Rejection does not navigate as a successful add.
        assertEquals(before,fit(ship))
        // Do not explicitly refresh feature state first: that would hide a stale runtime cache.
        val cachedAfter=checkNotNull(EngineRuntime.offlineFeatures.value)
        assertEquals(ship,cachedAfter.selectedFitId)
        assertEquals(beforeState.copy(context=cachedAfter.context),cachedAfter)
        assertTrue(cachedAfter.context.generation>beforeState.context.generation)
        assertTrue(EngineRuntime.featureEpoch.value>epochBefore)
        val preview=EngineRuntime.offlineExportPreview(context,OfflineExportRequest(UUID.randomUUID().toString(),cachedAfter.context,
            ship,before.revision,OfflineExportOptions())).get(120,TimeUnit.SECONDS)
        assertTrue(preview.error?.message,preview.ok)
        val graph=EngineRuntime.offlineLockTime(context,OfflineLockTimeRequest(UUID.randomUUID().toString(),cachedAfter.context,
            mapOf(ship to before.revision),resolution=1),AtomicBoolean(false)).get(120,TimeUnit.SECONDS)
        assertTrue(graph.error?.message,graph.ok)
        val afterState=EngineRuntime.offlineFeatureState(context,ship).get(30,TimeUnit.SECONDS)
        assertEquals(cachedAfter,afterState)
        assertEquals(beforeState.copy(context=afterState.context),afterState)
        assertEquals(beforeState.context.sessionId,afterState.context.sessionId)
        assertEquals(beforeState.context.datasetSha256,afterState.context.datasetSha256)
        assertTrue(afterState.context.generation>beforeState.context.generation)
        val afterRejected=(listOf(second.id)+recentBefore.filter { it!=second.id }).take(20)
        assertRecentRows(afterRejected)
        val retainedEquipment=equipment
        compose.activityRule.scenario.recreate(); compose.waitForIdle()
        assertSame(retainedEquipment,equipment); assertTrue(equipment.showRecent)
        assertRecentRows(afterRejected); closeRecent()
        EngineRuntime.selectFit(context,id).get(30,TimeUnit.SECONDS); settled(id)
        click("fighter-0-select"); click("fighter-1-select"); click("fighters-remove-selected"); settled(id)
        assertEquals(listOf(first.id),model.currentDetails!!.squadrons.map { it.itemId })
        val afterRemoval=(listOf(first.id,second.id)+afterRejected.filter { it!=first.id && it!=second.id }).take(20)
        assertEquals(afterRemoval,EngineRuntime.recent.value) // Descending removal promotes second, then first.
        history(id,false)
        assertEquals(listOf(first.id,second.id,first.id),model.currentDetails!!.squadrons.map { it.itemId })
        assertEquals(afterRemoval,EngineRuntime.recent.value) // Undo never rewinds the Recent list.
        rejectedAttempt(ship,second)
        assertEquals(second.id,EngineRuntime.recent.value.first())
        history(id,true); assertEquals(afterRemoval,EngineRuntime.recent.value) // Redo repeats the source promotion order.
        click("fighter-0-variations"); click("fighter-0-variation-${second.id}"); settled(id)
        assertEquals(afterRemoval,EngineRuntime.recent.value)
        click("fighter-0-variations"); click("fighter-0-variation-${first.id}"); settled(id)
        assertEquals(afterRemoval,EngineRuntime.recent.value)
        rejectedAttempt(ship,second)
        val unchanged=EngineRuntime.recent.value.toList()
        click("fighter-0-toggle"); settled(id); assertEquals(unchanged,EngineRuntime.recent.value)
        val ability=model.currentDetails!!.squadrons.single().abilities.first()
        click("fighter-0-ability-${ability.effectId}"); settled(id); assertEquals(unchanged,EngineRuntime.recent.value)
        compose.onNodeWithTag("fighter-0-amount").performTextReplacement("2")
        click("fighter-0-save"); settled(id); assertEquals(unchanged,EngineRuntime.recent.value)
        compose.onNodeWithTag("fighter-0-amount").performTextReplacement("0")
        click("fighter-0-save"); settled(id)
        assertTrue(model.currentDetails!!.squadrons.isEmpty()); assertEquals(unchanged,EngineRuntime.recent.value)
        // Invalid and stale requests never count as valid fitting attempts.
        val snapshot=fit(id)
        val contextBeforeInvalid=EngineRuntime.offlineFeatures.value!!.context
        val epochBeforeInvalid=EngineRuntime.featureEpoch.value
        val invalid=EngineRuntime.request(context,BridgeOperation.AddFighter(id,0),mapOf(id to snapshot.revision)).get(120,TimeUnit.SECONDS)
        assertFalse(invalid.isSuccess); assertEquals(snapshot,fit(id)); assertEquals(unchanged,EngineRuntime.recent.value)
        val stale=EngineRuntime.request(context,BridgeOperation.AddFighter(id,first.id),mapOf(id to snapshot.revision-1)).get(120,TimeUnit.SECONDS)
        assertFalse(stale.isSuccess); assertEquals(BridgeErrorCode.REVISION_CONFLICT,stale.error!!.code)
        assertEquals(snapshot,fit(id)); assertEquals(unchanged,EngineRuntime.recent.value)
        val nonfighter=catalog.items.single { it.name=="Small Armor Repairer I" }
        val wrongType=EngineRuntime.request(context,BridgeOperation.AddFighter(id,nonfighter.id),mapOf(id to snapshot.revision)).get(120,TimeUnit.SECONDS)
        assertFalse(wrongType.isSuccess); assertEquals(snapshot,fit(id)); assertEquals(unchanged,EngineRuntime.recent.value)
        assertEquals(contextBeforeInvalid,EngineRuntime.offlineFeatures.value!!.context)
        assertEquals(epochBeforeInvalid,EngineRuntime.featureEpoch.value)
        click("fighters-browse"); assertRecentRows(unchanged)
    }
}
