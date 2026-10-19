package io.github.sussic.pyfa

import android.content.Context
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.core.content.ContextCompat
import java.util.UUID
import java.util.concurrent.CompletableFuture
import org.json.JSONObject

/** Equipment owns its preview, never the library's selection or detached editor draft. */
internal class OfflineSelectedItemDamageModel(
    private val featureContext: () -> OfflineContext? = { EngineRuntime.offlineFeatures.value?.context },
    private val activeFit: () -> String? = { EngineRuntime.navigation.value.activeId },
    private val fitRevision: () -> Long? = { (EngineRuntime.state.value as? EngineState.Ready)?.fit?.revision },
    private val selectedItem: () -> Int?,
    private val navigationEpoch: () -> Long,
    private val fitNavigationEpoch: () -> Long = { EngineRuntime.navigationEpoch.value },
    private val engineAvailable: () -> Boolean = { (EngineRuntime.state.value as? EngineState.Ready)?.let {
        it.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
    } == true },
    private val request: (Context, OfflineDamageRequest) -> CompletableFuture<OfflineDamageResponse> = EngineRuntime::offlineDamagePatterns,
) {
    private data class Anchor(val context: OfflineContext, val fitId: String, val fitRevision: Long, val itemId: Int, val navigation: Long, val fitNavigation: Long)
    private var anchor: Anchor? = null
    private var previewAnchor: Anchor? = null
    private var pendingRefresh = false
    private var closed = false
    private var session: String? = null
    var item by mutableStateOf<OfflineDamageItem?>(null); private set
    var busy by mutableStateOf(false); private set
    var saving by mutableStateOf(false); private set
    var reopenRequired by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    private fun liveAnchor(): Anchor? {
        val source = featureContext() ?: return null
        val fit = activeFit() ?: return null
        val revision = fitRevision() ?: return null
        val selected = selectedItem() ?: return null
        return Anchor(source, fit, revision, selected, navigationEpoch(), fitNavigationEpoch())
    }
    val currentItem get() = item.takeIf { !closed && previewAnchor != null && previewAnchor == liveAnchor() }
    val canApply get() = !closed && !busy && !reopenRequired && engineAvailable() && currentItem?.available == true

    fun synchronize(context: Context) {
        val source = featureContext()?.sessionId
        if (session != source) { session = source; reopenRequired = false }
        val current = liveAnchor()
        if (anchor == current) return
        anchor = current; previewAnchor = null; item = null; error = null; message = null
        pendingRefresh = current != null
        if (!busy) load(context)
    }
    fun reload(context: Context) {
        if (closed || busy || reopenRequired) return
        anchor = liveAnchor(); pendingRefresh = anchor != null; error = null
        load(context)
    }
    private fun load(context: Context) {
        val target = anchor ?: return
        if (closed || busy || reopenRequired || !engineAvailable() || target != liveAnchor() || !pendingRefresh) return
        pendingRefresh = false; previewAnchor = null; item = null
        dispatch(context, target, "item_options")
    }
    fun apply(context: Context) {
        if (!canApply) return
        val target = previewAnchor ?: return
        if (target != liveAnchor() || target != anchor) return
        dispatch(context, target, "apply_item")
    }
    private fun dispatch(context: Context, target: Anchor, operation: String) {
        if (busy || closed) return
        val input = OfflineDamageRequest(UUID.randomUUID().toString(), target.context, target.fitId,
            operation = operation, argumentsJson = OfflineFeatureCodec.json(JSONObject()
                .put("item_id", target.itemId).put("fit_revision", target.fitRevision)))
        try { input.json() } catch (_: Exception) { error = "The selected item request is invalid. Reload to try again."; return }
        busy = true; saving = !damageReadLike(operation); error = null; message = null
        val pending = try { request(context.applicationContext, input) } catch (_: Exception) {
            busy = false; saving = false; error = "The selected item request could not be started. Reload to try again."; return
        }
        pending.whenCompleteAsync({ result, failure ->
            busy = false; saving = false
            if (closed) return@whenCompleteAsync
            val current = liveAnchor()
            val sameSession = target.context.sessionId == featureContext()?.sessionId
            // A late mutation can be uncertain even after leaving this card. A previous
            // session cannot poison a successfully reopened engine.
            if (sameSession && (result?.reopenRequired == true || failure != null && !damageReadLike(operation))) reopenRequired = true
            val sameNavigation = current != null && current.navigation == target.navigation &&
                current.fitNavigation == target.fitNavigation && current.fitId == target.fitId && current.itemId == target.itemId && sameSession
            val reply = result?.state
            // Mutation publication can advance fit/context before this callback. Only
            // that exact published state, in the same navigation epoch, may be accepted.
            val ownsReply = sameNavigation && (current == target || operation == "apply_item" &&
                reply?.context == current?.context && reply?.fitRevision == current?.fitRevision)
            if (ownsReply) {
                if (failure != null || result == null) {
                    previewAnchor = null; item = null
                    error = if (damageReadLike(operation)) "Item damage options could not be loaded. Reload to try again."
                        else "The change could not be confirmed. Restart the app to check saved changes."
                } else if (!result.ok) {
                    error = result.error?.message ?: "The selected item request was not completed."
                    if (damageReadLike(operation) || result.error?.code in setOf("stale_context", "stale_fit", "missing_fit")) { previewAnchor = null; item = null }
                } else if (reply?.context == current?.context && reply?.fitId == current?.fitId &&
                    reply?.fitRevision == current?.fitRevision && reply?.item?.itemId == current?.itemId) {
                    anchor = current; previewAnchor = current; item = reply?.item; pendingRefresh = false
                    if (operation == "apply_item") message = if (result.committed == true)
                        "Selected Ammo applied. Updated contributions affect every fit using it; outgoing charges are unchanged."
                    else "This fit already uses Selected Ammo with these exact contributions. No saved values changed."
                } else {
                    previewAnchor = null; item = null; error = "Saved inputs changed. Reload item damage options."
                }
            }
            // A queued newer item/context read must not be lost behind an older request.
            if (pendingRefresh && !reopenRequired) load(context)
        }, ContextCompat.getMainExecutor(context))
    }
    fun close() { closed = true; anchor = null; previewAnchor = null; item = null; pendingRefresh = false }
}

@Composable
internal fun SelectedItemDamageActions(model: OfflineSelectedItemDamageModel, hasLibraryDraft: Boolean) {
    val context = LocalContext.current
    val item = model.currentItem
    if (model.busy) Text(if (model.saving) "Applying incoming damage and recalculating shared fits…" else "Checking incoming damage options…",
        Modifier.testTag("equipment-damage-busy"))
    model.error?.let { Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("equipment-damage-error")) }
    model.message?.let { Text(it, Modifier.testTag("equipment-damage-message")) }
    if (model.reopenRequired) Text("Restart the app before changing incoming damage.", color = MaterialTheme.colorScheme.error,
        modifier = Modifier.testTag("equipment-damage-reopen"))
    if (item?.eligible == true) {
        Text("Use this item's base damage as incoming damage only. No ammunition needs to be loaded; outgoing charges are unchanged.")
        item.values?.let { raw -> Text(DAMAGE_PATTERN_FIELDS.mapIndexed { index, key ->
            "${DAMAGE_PATTERN_LABELS[index]}: ${raw.fields.getValue(key)}"
        }.joinToString(" · "), Modifier.testTag("equipment-damage-values")) }
        if (item.available) {
            Text("Updates Selected Ammo for every fit using it, then uses it for this fit.")
            if (hasLibraryDraft) Text("Your unsaved damage-pattern draft is kept and is not applied.", Modifier.testTag("equipment-damage-draft-kept"))
            Button(onClick = { model.apply(context) }, enabled = model.canApply,
                modifier = Modifier.testTag("equipment-apply-damage")) { Text("Use as Selected Ammo · shared incoming pattern") }
        } else Text(when (item.unavailableReason) {
            "zero_total" -> "Unavailable: total damage is zero. The last valid incoming pattern is kept."
            else -> "Unavailable: base damage contains unsupported values. The last valid incoming pattern is kept."
        }, Modifier.testTag("equipment-damage-unavailable"))
    }
    if (!model.busy && !model.reopenRequired && model.error != null) TextButton(onClick = { model.reload(context) },
        modifier = Modifier.testTag("equipment-damage-retry")) { Text("Reload incoming damage options") }
}
