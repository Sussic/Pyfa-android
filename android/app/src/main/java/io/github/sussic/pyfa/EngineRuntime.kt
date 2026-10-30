package io.github.sussic.pyfa

import android.content.Context
import android.os.Looper
import android.os.Debug
import android.os.Process
import android.os.SystemClock
import android.util.Log
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.CompletableFuture
import java.util.concurrent.Executors
import java.util.UUID
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.json.JSONObject
import org.json.JSONArray

sealed interface EngineState {
    data object Loading : EngineState
    data class Empty(val error: BridgeError? = null) : EngineState
    data class Ready(val fit: FitSnapshot, val error: BridgeError? = null) : EngineState
    data class Failed(val message: String) : EngineState
}

/** One process-owned worker: EOS and its SQLite session never cross threads. */
object EngineRuntime {
    private val executor = Executors.newSingleThreadExecutor { task -> Thread(task, "pyfa-engine") }
    private val mutableState = MutableStateFlow<EngineState>(EngineState.Loading)
    val state = mutableState.asStateFlow()
    private val mutableLibrary = MutableStateFlow<List<FitSnapshot>>(emptyList())
    val library = mutableLibrary.asStateFlow()
    private val mutableCatalog = MutableStateFlow(HullCatalog())
    val catalog = mutableCatalog.asStateFlow()
    private val mutableModified = MutableStateFlow<Map<String, Long>>(emptyMap())
    val modified = mutableModified.asStateFlow()
    private val mutableRecent = MutableStateFlow<List<Int>>(emptyList())
    val recent = mutableRecent.asStateFlow()
    private val mutableNavigation = MutableStateFlow(LibraryNavigation())
    val navigation = mutableNavigation.asStateFlow()
    // In-memory ownership token: even an A → B → A navigation invalidates held item replies.
    private val mutableNavigationEpoch = MutableStateFlow(0L)
    internal val navigationEpoch = mutableNavigationEpoch.asStateFlow()
    private fun publishNavigation(next: LibraryNavigation) {
        if (mutableNavigation.value != next) mutableNavigationEpoch.value += 1
        mutableNavigation.value = next
    }
    private val mutableNavigationError = MutableStateFlow<String?>(null)
    val navigationError = mutableNavigationError.asStateFlow()
    private var navigationStore: NavigationStore? = null // Worker only.
    private var navigationWritable = true
    private var startup: CompletableFuture<FitSnapshot?>? = null
    private var sessionId: String? = null // Worker only.
    private var sampleId: String? = null // Worker only.
    private var unavailable = false // A transport fault may follow an unknown commit.
    private var startupMetrics: JSONObject? = null // Written/read only on the engine worker.
    private var startupDrawRecorded = false
    private var ephemeralDiagnostics = false // Selected before startup by the debug test runner.
    private var equipment: EquipmentCatalog? = null // Loaded on demand, worker only.
    private var equipmentRaw: String? = null
    private var characterImplants: Pair<Pair<String, String>, CharacterImplantCatalog>? = null // Worker only.
    private var implantSetViews = emptyList<OfflineImplantSetState>() // Verified, same-generation worker cache only.
    private var implantSetKnownSession: String? = null
    private val implantSetKnownIds = mutableSetOf<String>()


    fun offlineExportPreview(context: Context, request: OfflineExportRequest): CompletableFuture<OfflineExportPreview> {
        // Request fields are immutable; encode before queueing so the reviewed inputs are fixed.
        val encoded = request.json()
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the fitting engine before exporting." }
            val result = OfflineExportCodec.preview(Python.getInstance().getModule("mobile_runtime")
                .callAttr("offline_export_preview", encoded).toString(), request)
            if (result.ok) {
                check(mutableOfflineFeatures.value?.context == request.context &&
                    mutableLibrary.value.any { it.id == request.fitId && it.revision == request.revision }) {
                    "The fit changed while preparing its export. Preview again."
                }
            }
            // A refused read can report that the durable backend already closed itself.
            if (result.requiresEngineReopen) markEngineUnavailable()
            // Otherwise this read must not publish a fit, alter navigation, or touch edit history.
            result
        }, executor)
    }

    fun offlineMobility(context: Context, request: OfflineMobilityRequest,
        cancellation: java.util.concurrent.atomic.AtomicBoolean): CompletableFuture<OfflineMobilityResult> {
        val captured = request.copy(fits = OfflineFeatureCodec.frozen(request.fits))
        val encoded = captured.json()
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable) { "Restart the fitting engine before plotting." }
            if (cancellation.get()) return@supplyAsync OfflineMobilityResult(captured.requestId, false, captured, emptyList(),
                OfflineFeatureError("cancelled", "Mobility sampling was cancelled before it started."))
            try {
                val result = OfflineMobilityCodec.result(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_mobility_samples", encoded, cancellation).toString(), captured)
                if (result.requiresEngineReopen) markEngineUnavailable()
                result
            } catch (failure: Exception) {
                // Unknown transport/protocol failures cannot certify that EOS is reusable.
                markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun offlineRemoteRepair(context: Context, request: OfflineRemoteRepairRequest,
        cancellation: java.util.concurrent.atomic.AtomicBoolean): CompletableFuture<OfflineRemoteRepairResult> {
        val captured = request.copy(fits = OfflineFeatureCodec.frozen(request.fits))
        val encoded = captured.json()
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable) { "Restart the fitting engine before plotting." }
            if (cancellation.get()) return@supplyAsync OfflineRemoteRepairResult(captured.requestId, false, captured, emptyList(),
                OfflineFeatureError("cancelled", "Remote repair sampling was cancelled before it started."))
            try {
                val result = OfflineRemoteRepairCodec.result(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_remote_repair_samples", encoded, cancellation).toString(), captured)
                if (result.requiresEngineReopen) markEngineUnavailable()
                result
            } catch (failure: Exception) {
                // Unknown transport/protocol failures cannot certify that EOS is reusable.
                markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun offlineEwar(context: Context, request: OfflineEwarRequest,
        cancellation: java.util.concurrent.atomic.AtomicBoolean): CompletableFuture<OfflineEwarResult> {
        val captured = request.copy(fits = OfflineFeatureCodec.frozen(request.fits))
        val encoded = captured.json()
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable) { "Restart the fitting engine before plotting." }
            if (cancellation.get()) return@supplyAsync OfflineEwarResult(captured.requestId, false, captured, emptyList(),
                OfflineFeatureError("cancelled", "EWAR sampling was cancelled before it started."))
            try {
                val result = OfflineEwarCodec.result(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_ewar_samples", encoded, cancellation).toString(), captured)
                if (result.requiresEngineReopen) markEngineUnavailable()
                result
            } catch (failure: Exception) {
                // Unknown transport/protocol failures cannot certify that EOS is reusable.
                markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun offlineShieldRegeneration(context: Context, request: OfflineShieldRegenerationRequest,
        cancellation: java.util.concurrent.atomic.AtomicBoolean): CompletableFuture<OfflineShieldRegenerationResult> {
        val captured = request.copy(fits = OfflineFeatureCodec.frozen(request.fits))
        val encoded = captured.json()
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable) { "Restart the fitting engine before plotting." }
            if (cancellation.get()) return@supplyAsync OfflineShieldRegenerationResult(captured.requestId, false, captured, emptyList(),
                OfflineFeatureError("cancelled", "Shield regeneration sampling was cancelled before it started."))
            try {
                val result = OfflineShieldRegenerationCodec.result(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_shield_regeneration_samples", encoded, cancellation).toString(), captured)
                if (result.requiresEngineReopen) markEngineUnavailable()
                result
            } catch (failure: Exception) {
                // Unknown transport/protocol failures cannot certify that EOS is reusable.
                markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun offlineLockTime(context: Context, request: OfflineLockTimeRequest,
        cancellation: java.util.concurrent.atomic.AtomicBoolean): CompletableFuture<OfflineLockTimeResult> {
        val captured = request.copy(fits = OfflineFeatureCodec.frozen(request.fits))
        val encoded = captured.json()
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable) { "Restart the fitting engine before plotting." }
            if (cancellation.get()) return@supplyAsync OfflineLockTimeResult(captured.requestId, false, captured, emptyList(),
                OfflineFeatureError("cancelled", "Lock-time sampling was cancelled before it started."))
            try {
                val result = OfflineLockTimeCodec.result(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_locktime_samples", encoded, cancellation).toString(), captured)
                if (result.requiresEngineReopen) markEngineUnavailable()
                result
            } catch (failure: Exception) {
                // Unknown transport/protocol failures cannot certify that EOS is reusable.
                markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun offlineCapacitor(context: Context, request: OfflineCapacitorRequest,
        cancellation: java.util.concurrent.atomic.AtomicBoolean): CompletableFuture<OfflineCapacitorResult> {
        val captured = request.copy(fits = OfflineFeatureCodec.frozen(request.fits))
        val encoded = captured.json()
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            if (cancellation.get()) return@supplyAsync OfflineCapacitorResult(captured.requestId, false, captured, emptyList(),
                OfflineFeatureError("cancelled", "Capacitor sampling was cancelled before it started."))
            try {
                val result = OfflineCapacitorCodec.result(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_capacitor_samples", encoded, cancellation).toString(), captured)
                if (result.error?.code == "engine_error") markEngineUnavailable()
                result
            } catch (failure: Exception) {
                // Invalid wrapper output may mean its EOS cache cleanup failed.
                markEngineUnavailable()
                throw failure
            }
        }, executor)
    }
    private var importStore: OfflineImportStore? = null
    private val mutablePendingImport = MutableStateFlow<String?>(null)
    val pendingImport = mutablePendingImport.asStateFlow()
    private val mutableImportStorageError = MutableStateFlow<String?>(null)
    val importStorageError = mutableImportStorageError.asStateFlow()

    fun offlineImportPreview(context: Context, requestJson: String): CompletableFuture<OfflineImportPreview> {
        val ready = start(context)
        val expected = OfflineFeatureCodec.parse(requestJson)
        val id = expected.getString("request_id")
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            OfflineImportCodec.preview(Python.getInstance().getModule("mobile_runtime")
                .callAttr("offline_import_preview", requestJson).toString(), id, expected)
        }, executor)
    }

    fun offlineImportExecute(context: Context, exactRequest: String): CompletableFuture<OfflineImportResult> {
        val request = OfflineImportCodec.request(exactRequest)
        val id = request.getString("request_id")
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable) { "Restart before retrying the saved import." }
            check(mutableImportStorageError.value == null) { "Pending import storage needs recovery." }
            val store = checkNotNull(importStore)
            // A different request may never overwrite an unresolved earlier import.
            try { store.save(exactRequest) }
            catch (failure: Exception) {
                mutableImportStorageError.value = "Could not safely save the import retry record. No import was started; existing retry data has been preserved."
                throw failure
            }
            mutablePendingImport.value = exactRequest
            try {
                val response = OfflineImportCodec.result(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_import_execute", exactRequest).toString(), id, checkNotNull(sessionId), request)
                if (response.ok) {
                    readCharacterImplantCatalog(checkNotNull(response.state).context).validate(checkNotNull(response.state))
                    mutableLibrary.value = checkNotNull(response.bridge).fits
                    readOrganization(); readRecent()
                    val retained = mutableNavigation.value.retain(mutableLibrary.value.map { it.id }.toSet())
                    if (retained != mutableNavigation.value) { saveNavigation(retained); publishNavigation(retained) }
                    mutableOfflineFeatures.value = checkNotNull(response.state)
                    mutableFeatureEpoch.value += 1
                    publishSelection()
                }
                if (response.reopenRequired || response.committed == null) markEngineUnavailable()
                else {
                    try { store.clear(); mutablePendingImport.value = null }
                    catch (_: Exception) { mutableImportStorageError.value = "The import result is known, but its retry record could not be cleared. Restart before another import." }
                }
                response
            } catch (failure: Exception) {
                // Keep the exact source/ID across process death and unknown commit outcomes.
                markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun readEftDocuments(context: Context, uris: List<android.net.Uri>): CompletableFuture<List<OfflineEftDocument>> {
        val captured = uris.toList()
        val app = context.applicationContext
        return CompletableFuture.supplyAsync({ OfflineImportFiles.read(app, captured) }, executor)
    }
    private val mutableOfflineFeatures = MutableStateFlow<OfflineFeatureState?>(null)
    val offlineFeatures = mutableOfflineFeatures.asStateFlow()
    private val mutableFeatureEpoch = MutableStateFlow(0L)
    val featureEpoch = mutableFeatureEpoch.asStateFlow()

    /** Stage without publishing: compound set results must pass all cross-summary checks first. */
    private fun stageOfflineFeatures(fitId: String?, fits: List<FitSnapshot>): OfflineFeatureState {
        check(!ephemeralDiagnostics && !unavailable) { "Offline features need the saved fitting engine." }
        return OfflineFeatureCodec.state(Python.getInstance().getModule("mobile_runtime")
            .callAttr("offline_feature_state", fitId).toString()).also { value ->
            check(value.context.sessionId == sessionId && value.selectedFitId == fitId)
            OfflineFeatureCodec.validateFits(value, fits)
            readCharacterImplantCatalog(value.context).validate(value)
        }
    }
    private fun readOfflineFeatures(fitId: String?): OfflineFeatureState =
        stageOfflineFeatures(fitId, mutableLibrary.value).also { mutableOfflineFeatures.value = it }

    fun offlineFeatureState(context: Context, fitId: String?): CompletableFuture<OfflineFeatureState> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            try { readOfflineFeatures(fitId) }
            catch (failure: Exception) { markEngineUnavailable(); throw failure }
        }, executor)
    }

    /** Capture the JSON now. Every mutation, commit acknowledgement and publication stays on EOS's worker. */
    fun offlineFeatureRequest(context: Context, expected: OfflineContext, operation: String,
        arguments: JSONObject, anchorFitId: String?, requestId: String = UUID.randomUUID().toString()): CompletableFuture<OfflineFeatureResponse> {
        val encoded = OfflineFeatureCodec.request(requestId, expected, operation, arguments, anchorFitId)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(Looper.myLooper() != Looper.getMainLooper())
            // A queued request may be stale; the server returns a definite rejection.
            try {
                val before = mutableOfflineFeatures.value?.let {
                    if (it.context == expected && it.selectedFitId != anchorFitId) readOfflineFeatures(anchorFitId) else it
                }
                val response = OfflineFeatureCodec.response(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_feature_dispatch", encoded).toString(), requestId, expected, before?.takeIf { it.context == expected }, anchorFitId)
                if (response.ok) {
                    val state = checkNotNull(response.state)
                    if (response.committed == false) check(checkNotNull(response.bridge).fits == mutableLibrary.value) { "No-op changed fit library" }
                    readCharacterImplantCatalog(checkNotNull(response.state).context).validate(checkNotNull(response.state))
                    mutableLibrary.value = checkNotNull(response.bridge).fits
                    readOrganization(); readRecent()
                    val retained = mutableNavigation.value.retain(mutableLibrary.value.map { it.id }.toSet())
                    if (retained != mutableNavigation.value) { saveNavigation(retained); publishNavigation(retained) }
                    mutableOfflineFeatures.value = state
                    if (response.committed == true) mutableFeatureEpoch.value += 1
                    publishSelection()
                } else if (response.reopenRequired || response.committed == null) {
                    markEngineUnavailable()
                }
                response
            } catch (failure: Exception) {
                // Transport or invalid reply may follow a successful durable commit.
                markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    /** Target records and bridge refresh share the existing serialized EOS worker. */
    fun offlineTargetProfiles(context: Context, request: OfflineTargetRequest): CompletableFuture<OfflineTargetResponse> {
        val encoded = request.json()
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!ephemeralDiagnostics && !unavailable) { "Restart the app to recover the saved fitting engine." }
            check(Looper.myLooper() != Looper.getMainLooper())
            try {
                val response = OfflineTargetCodec.response(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_target_profiles", encoded).toString(), request)
                if (response.ok && request.operation != "read") {
                    val target = checkNotNull(response.state)
                    mutableLibrary.value = checkNotNull(response.bridge).fits
                    readOrganization(); readRecent()
                    val retained = mutableNavigation.value.retain(mutableLibrary.value.map { it.id }.toSet())
                    if (retained != mutableNavigation.value) { saveNavigation(retained); publishNavigation(retained) }
                    val refreshed = readOfflineFeatures(mutableNavigation.value.activeId)
                    check(refreshed.context == target.context) { "Target and character context publication differ" }
                    if (response.committed == true) mutableFeatureEpoch.value += 1
                    publishSelection()
                } else if (response.reopenRequired || response.committed == null) markEngineUnavailable()
                response
            } catch (failure: Exception) {
                // A malformed/absent mutation reply can follow a durable commit. Reads never commit.
                if (request.operation != "read") markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    /** Damage patterns and bridge refresh share the existing serialized EOS worker. */
    fun offlineDamagePatterns(context: Context, request: OfflineDamageRequest): CompletableFuture<OfflineDamageResponse> {
        val encoded = request.json()
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!ephemeralDiagnostics && !unavailable) { "Restart the app to recover the saved fitting engine." }
            check(Looper.myLooper() != Looper.getMainLooper())
            try {
                val response = OfflineDamageCodec.response(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_damage_patterns", encoded).toString(), request)
                if (response.ok && !damageReadLike(request.operation)) {
                    val damage = checkNotNull(response.state)
                    // Engine publication is independent of editor ownership. A late completion
                    // must never replace a newer generation or another runtime session.
                    if (!mayPublishDamageContext(mutableOfflineFeatures.value?.context, damage.context)) return@supplyAsync response
                    mutableLibrary.value = checkNotNull(response.bridge).fits
                    readOrganization(); readRecent()
                    val retained = mutableNavigation.value.retain(mutableLibrary.value.map { it.id }.toSet())
                    if (retained != mutableNavigation.value) { saveNavigation(retained); publishNavigation(retained) }
                    val refreshed = readOfflineFeatures(mutableNavigation.value.activeId)
                    check(refreshed.context == damage.context) { "Damage-pattern and character context publication differ" }
                    if (response.committed == true) mutableFeatureEpoch.value += 1
                    publishSelection()
                } else if (response.reopenRequired || response.committed == null) markEngineUnavailable()
                response
            } catch (failure: Exception) {
                // A malformed/absent mutation reply can follow a durable commit. Reads never commit.
                if (!damageReadLike(request.operation)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    /** One immutable call owns the EOS worker through dispatch, verification, refresh and publication. */
    fun offlineImplantSets(context: Context, request: OfflineImplantSetRequest): CompletableFuture<OfflineImplantSetResponse> {
        val captured = request.copy(view = request.view.copy())
        val encoded = captured.json() // Any definite local validation failure occurs before enqueue.
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!ephemeralDiagnostics && !unavailable) { "Restart the app to recover the saved fitting engine." }
            check(Looper.myLooper() != Looper.getMainLooper())
            val beforeFeatures = checkNotNull(mutableOfflineFeatures.value)
            val beforeFits = mutableLibrary.value
            val beforeView = implantSetViews.lastOrNull { it.context == captured.context && it.anchorFitId == captured.anchorFitId &&
                it.view.targetProfileId == captured.view.targetProfileId && it.detail?.entry?.id == captured.view.selectedSetId }
            try {
                val response = OfflineImplantSetsCodec.response(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_implant_sets", encoded).toString(), captured)
                if (response.ok) {
                    val state = checkNotNull(response.state)
                    val metadata = readCharacterImplantCatalog(state.context)
                    OfflineImplantSetsCodec.validateResult(response, captured, beforeView)
                    if (captured.operation in setOf("create", "duplicate", "save_current") && implantSetKnownSession == captured.context.sessionId) {
                        check(state.detail?.entry?.id !in implantSetKnownIds) { "New set reused a known identity" }
                    }
                    if (captured.operation == "read") {
                        // Reads never republish a fit or an obsolete feature context.
                        check(beforeFeatures.context == captured.context && mutableOfflineFeatures.value?.context == captured.context)
                        OfflineImplantSetsCodec.validateAuthority(state, beforeFeatures, beforeFits, metadata)
                    } else {
                        val fits = checkNotNull(response.bridge).fits
                        val retained = mutableNavigation.value.retain(fits.map { it.id }.toSet())
                        // Do not call readOfflineFeatures here: that helper publishes before compound validation.
                        val refreshed = stageOfflineFeatures(retained.activeId, fits)
                        OfflineImplantSetsCodec.validateTransition(response, captured, beforeView, beforeFeatures, beforeFits, refreshed, metadata)
                        val modified = stageOrganization()
                        val recent = stageRecent()
                        check(recent == mutableRecent.value) { "Implant-set operation changed Recent-use" }
                        if (response.committed == false || captured.operation in setOf("create", "rename", "duplicate", "delete", "add_item", "remove_item", "save_current"))
                            check(modified == mutableModified.value) { "Template/no-op changed fit modification order" }
                        // Every protocol and cross-summary check is now complete. Navigation persistence
                        // remains the existing best-effort preference, never a second recipe mutation.
                        if (retained != mutableNavigation.value) saveNavigation(retained)
                        mutableLibrary.value = fits
                        mutableModified.value = modified
                        mutableRecent.value = recent
                        publishNavigation(retained)
                        mutableOfflineFeatures.value = refreshed
                        if (response.committed == true) mutableFeatureEpoch.value += 1
                        publishSelection()
                    }
                    if (implantSetKnownSession != state.context.sessionId) {
                        implantSetKnownSession = state.context.sessionId; implantSetKnownIds.clear()
                    }
                    implantSetKnownIds.addAll(state.entries.map { it.id }); state.detail?.let { implantSetKnownIds.add(it.entry.id) }
                    implantSetViews = (implantSetViews.filter { it.context == state.context &&
                        !(it.anchorFitId == state.anchorFitId && it.view == state.view) } + state).takeLast(16)
                } else if (response.reopenRequired || response.committed == null) markEngineUnavailable()
                response
            } catch (failure: Exception) {
                // Never repeat a possibly committed mutation after absent/malformed/late publication output.
                if (captured.operation != "read") markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    private fun markEngineUnavailable() {
        unavailable = true
        publishSelection()
    }

    private fun readCharacterImplantCatalog(expected: OfflineContext): CharacterImplantCatalog {
        check(!unavailable && expected.sessionId == sessionId) { "Implant metadata session changed." }
        val key = expected.sessionId to expected.datasetSha256
        characterImplants?.takeIf { it.first == key }?.let { return it.second }
        val value = CharacterImplantCatalogCodec.decode(Python.getInstance().getModule("mobile_runtime")
            .callAttr("implant_catalog").toString(), expected.datasetSha256)
        check(value.error == null) { value.error?.message ?: "Implant metadata could not be verified." }
        characterImplants = key to value
        return value
    }
    fun characterImplantCatalog(context: Context): CompletableFuture<CharacterImplantCatalog> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            readCharacterImplantCatalog(checkNotNull(mutableOfflineFeatures.value).context)
        }, executor)
    }

    fun equipmentCatalog(context: Context): CompletableFuture<EquipmentCatalog> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            equipment ?: Python.getInstance().getModule("mobile_runtime").callAttr("equipment_catalog").toString().let { raw ->
                EquipmentCatalog.decode(raw).also { equipment = it; equipmentRaw = raw }
            }
        }, executor)
    }

    fun equipmentDiagnostics(context: Context): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = equipmentCatalog(context)
        return CompletableFuture.supplyAsync({ ready.join(); checkNotNull(equipmentRaw) }, executor)
    }

    fun searchEquipment(context: Context, query: String): CompletableFuture<List<Int>> {
        val ready = equipmentCatalog(context)
        return CompletableFuture.supplyAsync({
            val catalog = ready.join()
            val rows = JSONArray(Python.getInstance().getModule("mobile_runtime")
                .callAttr("equipment_search", query).toString())
            val ids = (0 until rows.length()).map { rows.getInt(it) }
            check(ids.distinct().size == ids.size && ids.all { catalog.itemById[it]?.searchable == true })
            ids
        }, executor)
    }

    fun fittingDetails(context: Context, fitId: String): CompletableFuture<FittingDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeFitting(Python.getInstance().getModule("mobile_runtime")
                .callAttr("fitting_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun defensePersistenceSnapshot(context: Context): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("defense_persistence_snapshot").toString()
        }, executor)
    }

    fun inspectionSqlRoles(context: Context, fitId: String, complete: Boolean = false): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("inspection_sql_roles", fitId, complete).toString()
        }, executor)
    }

    fun inspectionUnitWitnesses(context: Context, samples: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("inspection_unit_witnesses", samples).toString()
        }, executor)
    }

    fun inspectionEquipmentWitnesses(context: Context, fitId: String, target: InspectionTarget): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("inspection_equipment_witnesses", fitId, target.json()).toString()
        }, executor)
    }

    fun inspectionEquipmentProbes(context: Context, fitId: String, inputs: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("inspection_equipment_probes", fitId, inputs).toString()
        }, executor)
    }

    fun inspectionGuardDomains(context: Context, inputs: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("inspection_guard_domains", inputs).toString()
        }, executor)
    }

    fun targetingDetails(context: Context, fitId: String): CompletableFuture<FitTargeting> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeTargeting(Python.getInstance().getModule("mobile_runtime").callAttr("targeting_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun inspectionOptions(context: Context, fitId: String): CompletableFuture<InspectionOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeInspectionOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("inspection_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun inspectionDetails(context: Context, fitId: String?, target: InspectionTarget, effective: Boolean = false): CompletableFuture<ItemInspection> {
        require(target.context == "base" || target.objectKey != null) { "Choose a current saved inspection target." }
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            val runtime = Python.getInstance().getModule("mobile_runtime")
            val raw = if (target.context == "base") runtime.callAttr("inspection_base_details", target.itemId)
                else runtime.callAttr("inspection_details", checkNotNull(fitId), target.json(), effective)
            BridgeCodec.decodeInspection(raw.toString()).also { result ->
                check(result.target == target)
                if (target.context == "base") check(result.fitId == null && result.revision == null)
                else check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun outputDetails(context: Context, fitId: String): CompletableFuture<FitOutput> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeOutput(Python.getInstance().getModule("mobile_runtime").callAttr("output_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun tankDetails(context: Context, fitId: String): CompletableFuture<FitTank> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeTank(Python.getInstance().getModule("mobile_runtime")
                .callAttr("tank_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun defenseDetails(context: Context, fitId: String): CompletableFuture<FitDefenses> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeDefenses(Python.getInstance().getModule("mobile_runtime")
                .callAttr("defense_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun capacitorDetails(context: Context, fitId: String): CompletableFuture<FitCapacitor> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeCapacitor(Python.getInstance().getModule("mobile_runtime")
                .callAttr("capacitor_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun resourceDetails(context: Context, fitId: String): CompletableFuture<FitResources> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeResources(Python.getInstance().getModule("mobile_runtime")
                .callAttr("resource_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun systemSecurityDetails(context: Context, fitId: String): CompletableFuture<SystemSecurityDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId }) { "This fit is no longer in the library." }
            try {
                SystemSecurityCodec.decode(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("system_security_details", fitId).toString()).also { result ->
                    check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
                }
            } catch (failure: Exception) { markEngineUnavailable(); throw failure }
        }, executor)
    }

    /** Capture before queueing; a later navigation or binding publication never retargets this read. */
    fun pilotSecurityDetails(context: Context, fitId: String): CompletableFuture<PilotSecurityDetails> {
        val expected = PilotSecurityOwner.capture(checkNotNull(mutableOfflineFeatures.value),
            mutableLibrary.value.single { it.id == fitId })
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!ephemeralDiagnostics && !unavailable) { "Restart the app to recover the saved fitting engine." }
            fun current() = PilotSecurityOwner.capture(checkNotNull(mutableOfflineFeatures.value),
                mutableLibrary.value.single { it.id == fitId })
            // Staleness before calling Python is a read refusal, not uncertain durable mutation.
            check(current() == expected) { "The fit or character changed before reading pilot security." }
            try {
                PilotSecurityCodec.decode(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("offline_pilot_security_details", fitId).toString()).also { value ->
                    expected.validate(value)
                    check(mutableCatalog.value.hulls.any { it.id == value.hullId && it.name == value.hullName }) { "Pilot hull differs from the bundled catalogue." }
                    check(current() == expected) { "The fit or character changed while reading pilot security." }
                    current().validate(value)
                }
            } catch (failure: Exception) { markEngineUnavailable(); throw failure }
        }, executor)
    }

    fun moduleRahDetails(context: Context, fitId: String, offset: Long = 0, limit: Int = 25): CompletableFuture<ModuleRahDetails> {
        require(offset >= 0 && limit in 1..25)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId }) { "This fit is no longer in the library." }
            val expectedContext = checkNotNull(mutableOfflineFeatures.value).context
            val expectedRevision = mutableLibrary.value.single { it.id == fitId }.revision
            try {
                ModuleRahCodec.decode(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("module_rah_details", fitId, offset, limit).toString()).also { result ->
                    check(result.fitId == fitId && result.revision == expectedRevision && result.context == expectedContext &&
                        mutableOfflineFeatures.value?.context == expectedContext && mutableLibrary.value.single { it.id == fitId }.revision == expectedRevision &&
                        result.moduleOffset == offset && result.moduleLimit == limit)
                }
            } catch (failure: Exception) {
                if (isUnsupportedRahFailure(failure)) throw UnsupportedRahPatternException()
                markEngineUnavailable(); throw failure
            }
        }, executor)
    }

    fun mutationDetails(context: Context, fitId: String): CompletableFuture<MutationDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId }) { "This fit is no longer in the library." }
            try {
                MutationCodec.decode(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("mutation_details", fitId).toString()).also { result ->
                    check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
                }
            } catch (failure: Exception) { markEngineUnavailable(); throw failure }
        }, executor)
    }

    fun mutationDisplayDetails(context: Context, fitId: String): CompletableFuture<MutationDisplayDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId }) { "This fit is no longer in the library." }
            try {
                MutationDisplayCodec.decode(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("mutation_display_details", fitId).toString()).also { result ->
                    check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
                }
            } catch (failure: Exception) { markEngineUnavailable(); throw failure }
        }, executor)
    }

    fun moduleSpoolDetails(context: Context, fitId: String): CompletableFuture<ModuleSpoolDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId }) { "This fit is no longer in the library." }
            try {
                ModuleSpoolCodec.decode(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("module_spool_details", fitId).toString()).also { result ->
                    check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
                }
            } catch (failure: Exception) { markEngineUnavailable(); throw failure }
        }, executor)
    }

    fun implantDetails(context: Context, fitId: String): CompletableFuture<ImplantDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId }) { "This fit is no longer in the library." }
            try {
                ImplantDetailsCodec.details(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("implant_details", fitId).toString()).also { result ->
                    check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
                }
            } catch (failure: Exception) { markEngineUnavailable(); throw failure }
        }, executor)
    }

    fun implantAddOptions(context: Context, fitId: String, itemId: Int): CompletableFuture<ImplantAddOptions> {
        require(itemId > 0)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId }) { "This fit is no longer in the library." }
            try {
                ImplantDetailsCodec.addOptions(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("implant_add_options", fitId, itemId).toString()).also { result ->
                    check(result.fitId == fitId && result.itemId == itemId &&
                        mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
                }
            } catch (failure: Exception) { markEngineUnavailable(); throw failure }
        }, executor)
    }

    fun boosterDetails(context: Context, fitId: String): CompletableFuture<BoosterDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId }) { "This fit is no longer in the library." }
            try {
                BoosterDetailsCodec.details(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("booster_details", fitId).toString()).also { result ->
                    check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
                }
            } catch (failure: Exception) { markEngineUnavailable(); throw failure }
        }, executor)
    }

    fun boosterAddOptions(context: Context, fitId: String, itemId: Int): CompletableFuture<BoosterAddOptions> {
        require(itemId > 0)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId }) { "This fit is no longer in the library." }
            try {
                BoosterDetailsCodec.addOptions(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("booster_add_options", fitId, itemId).toString()).also { result ->
                    check(result.fitId == fitId && result.itemId == itemId &&
                        mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
                }
            } catch (failure: Exception) { markEngineUnavailable(); throw failure }
        }, executor)
    }

    fun projectedModuleDetails(context: Context, fitId: String, revision: Long): CompletableFuture<ProjectedModuleDetails> {
        require(revision >= 1)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) { "The fit changed before projected modules could be read." }
            try {
                ProjectedModuleCodec.details(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("projected_module_details", fitId).toString()).also {
                    OfflineFeatureCodec.expect(it.fitId == fitId && it.revision == revision, "projected detail identity differs")
                }
            } catch (failure: Exception) {
                if (failure is BridgeProtocolException || projectedReadRequiresReopen(failure)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun projectedModuleChargePreview(context: Context, capture: ProjectedChargeCapture): CompletableFuture<ProjectedModuleChargePreview> {
        val fitId = capture.details.fitId
        val revision = capture.details.revision
        require(revision >= 1)
        // Encode caller-owned collections before queueing on the one EOS worker.
        val request = ProjectedModuleChargeCodec.request(ProjectedModuleSelectionRow(capture.main.index, capture.main.objectKey),
            capture.selection.wireRows(), capture.scope, capture.chargeId).toString()
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the fitting engine" }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) { "The fit changed before charge preview." }
            try {
                ProjectedModuleChargeCodec.decode(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("projected_module_charge_preview", fitId, request).toString()).also {
                    OfflineFeatureCodec.expect(it.fitId == fitId && it.revision == revision, "charge preview fit differs")
                }
            } catch (failure: Exception) {
                // A failed preview is read-only. Preserve the engine unless it actually requires reopening.
                if (projectedReadRequiresReopen(failure)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun projectedModuleOptions(context: Context, fitId: String, revision: Long, row: ProjectedModuleRow): CompletableFuture<ProjectedModuleOptions> {
        require(revision >= 1 && row.index >= 0)
        // All captured row fields are immutable; selection changes cannot alter this queued read.
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) { "The fit changed before projected choices could be read." }
            try {
                ProjectedModuleCodec.options(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("projected_module_options", fitId, row.index).toString()).also {
                    OfflineFeatureCodec.expect(it.fitId == fitId && it.revision == revision && it.index == row.index &&
                        it.objectKey == row.objectKey && it.itemId == row.itemId, "projected choice identity differs")
                }
            } catch (failure: Exception) {
                if (failure is BridgeProtocolException || projectedReadRequiresReopen(failure)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun projectedModuleAddOptions(context: Context, fitId: String, revision: Long, itemId: Int): CompletableFuture<ProjectedModuleAddOptions> {
        require(revision >= 1 && itemId > 0)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) { "The fit changed before projectability could be checked." }
            try {
                ProjectedModuleCodec.addOptions(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("projected_module_add_options", fitId, itemId).toString()).also {
                    OfflineFeatureCodec.expect(it.fitId == fitId && it.revision == revision && it.itemId == itemId, "projected add identity differs")
                }
            } catch (failure: Exception) {
                if (failure is BridgeProtocolException || projectedReadRequiresReopen(failure)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun projectedFighterDetails(context: Context, fitId: String, revision: Long): CompletableFuture<ProjectedFighterDetails> {
        require(revision >= 1)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) { "The fit changed before projected fighters could be read." }
            try {
                ProjectedFighterCodec.details(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("projected_fighter_details", fitId).toString()).also {
                    OfflineFeatureCodec.expect(it.fitId == fitId && it.revision == revision, "projected detail identity differs")
                }
            } catch (failure: Exception) {
                if (failure is BridgeProtocolException || projectedReadRequiresReopen(failure)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun projectedFighterOptions(context: Context, fitId: String, revision: Long, row: ProjectedFighterRow): CompletableFuture<ProjectedFighterOptions> {
        require(revision >= 1 && row.index >= 0)
        // All captured row fields are immutable; selection changes cannot alter this queued read.
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) { "The fit changed before projected choices could be read." }
            try {
                ProjectedFighterCodec.options(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("projected_fighter_options", fitId, row.index).toString()).also {
                    OfflineFeatureCodec.expect(it.fitId == fitId && it.revision == revision && it.index == row.index &&
                        it.objectKey == row.objectKey && it.itemId == row.itemId, "projected choice identity differs")
                }
            } catch (failure: Exception) {
                if (failure is BridgeProtocolException || projectedReadRequiresReopen(failure)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun projectedFighterAddOptions(context: Context, fitId: String, revision: Long, itemId: Int): CompletableFuture<ProjectedFighterAddOptions> {
        require(revision >= 1 && itemId > 0)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) { "The fit changed before projectability could be checked." }
            try {
                ProjectedFighterCodec.addOptions(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("projected_fighter_add_options", fitId, itemId).toString()).also {
                    OfflineFeatureCodec.expect(it.fitId == fitId && it.revision == revision && it.itemId == itemId, "projected add identity differs")
                }
            } catch (failure: Exception) {
                if (failure is BridgeProtocolException || projectedReadRequiresReopen(failure)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun projectedDroneDetails(context: Context, fitId: String, revision: Long): CompletableFuture<ProjectedDroneDetails> {
        require(revision >= 1)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) { "The fit changed before projected drones could be read." }
            try {
                ProjectedDroneCodec.details(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("projected_drone_details", fitId).toString()).also {
                    OfflineFeatureCodec.expect(it.fitId == fitId && it.revision == revision, "projected detail identity differs")
                }
            } catch (failure: Exception) {
                if (failure is BridgeProtocolException || projectedReadRequiresReopen(failure)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun projectedDroneOptions(context: Context, fitId: String, revision: Long, row: ProjectedDroneRow): CompletableFuture<ProjectedDroneOptions> {
        require(revision >= 1 && row.index >= 0)
        // All captured row fields are immutable; selection changes cannot alter this queued read.
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) { "The fit changed before projected choices could be read." }
            try {
                ProjectedDroneCodec.options(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("projected_drone_options", fitId, row.index).toString()).also {
                    OfflineFeatureCodec.expect(it.fitId == fitId && it.revision == revision && it.index == row.index &&
                        it.objectKey == row.objectKey && it.itemId == row.itemId, "projected choice identity differs")
                }
            } catch (failure: Exception) {
                if (failure is BridgeProtocolException || projectedReadRequiresReopen(failure)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun projectedDroneAddOptions(context: Context, fitId: String, revision: Long, itemId: Int): CompletableFuture<ProjectedDroneAddOptions> {
        require(revision >= 1 && itemId > 0)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) { "The fit changed before projectability could be checked." }
            try {
                ProjectedDroneCodec.addOptions(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("projected_drone_add_options", fitId, itemId).toString()).also {
                    OfflineFeatureCodec.expect(it.fitId == fitId && it.revision == revision && it.itemId == itemId, "projected add identity differs")
                }
            } catch (failure: Exception) {
                if (failure is BridgeProtocolException || projectedReadRequiresReopen(failure)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun projectedFighterSimilarSelection(context: Context, fitId: String, revision: Long, main: ProjectedFighterRow): CompletableFuture<FighterSimilarSelection> {
        require(main.index >= 0 && main.editable && revision >= 1)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) {
                "The fit changed before similar incoming fighters could be read."
            }
            try {
                // Metadata-only query: no preparation/recalculation or edit. Malformed reads preserve selection and allow retry.
                FighterSimilarSelectionCodec.decode(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("projected_fighter_similar_selection", fitId, main.index).toString()).also { result ->
                    OfflineFeatureCodec.expect(result.fitId == fitId && result.revision == revision &&
                        result.main == FighterSelectionIdentity(main.index, main.objectKey, main.itemId), "stale incoming reference fighter")
                }
            } catch (failure: Exception) {
                if (projectedReadRequiresReopen(failure)) markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun fighterSimilarSelection(context: Context, fitId: String, revision: Long, position: Int): CompletableFuture<FighterSimilarSelection> {
        require(position >= 0 && revision >= 1)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId && it.revision == revision }) {
                "The fit changed before similar fighters could be read."
            }
            // A rejected read cannot make an uncertain edit. Preserve selection and allow retry.
            FighterSimilarSelectionCodec.decode(Python.getInstance().getModule("mobile_runtime")
                .callAttr("fighter_similar_selection", fitId, position).toString()).also { result ->
                check(result.fitId == fitId && result.revision == revision && result.main.index == position)
            }
        }, executor)
    }

    fun fighterDetails(context: Context, fitId: String): CompletableFuture<FighterDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            check(mutableLibrary.value.any { it.id == fitId }) { "This fit is no longer in the library." }
            try {
                FighterDetailsCodec.decode(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("fighter_details", fitId).toString()).also { result ->
                    check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
                }
            } catch (failure: Exception) {
                markEngineUnavailable()
                throw failure
            }
        }, executor)
    }

    fun droneDetails(context: Context, fitId: String): CompletableFuture<DroneDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeDroneDetails(Python.getInstance().getModule("mobile_runtime")
                .callAttr("drone_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun cargoDetails(context: Context, fitId: String): CompletableFuture<CargoDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeCargoDetails(Python.getInstance().getModule("mobile_runtime")
                .callAttr("cargo_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun editHistory(context: Context, fitId: String): CompletableFuture<EditHistory> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeEditHistory(Python.getInstance().getModule("mobile_runtime")
                .callAttr("history_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun noteDetails(context: Context, fitId: String): CompletableFuture<NoteDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeNoteDetails(Python.getInstance().getModule("mobile_runtime")
                .callAttr("note_details", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun cargoTransferDetails(context: Context, fitId: String): CompletableFuture<CargoTransferDetails> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeCargoTransferDetails(Python.getInstance().getModule("mobile_runtime")
                .callAttr("cargo_transfer_details", fitId).toString()).also { result ->
                check(result.cargo.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.cargo.revision)
            }
        }, executor)
    }

    fun cargoActionOptions(context: Context, fitId: String, itemId: Int,
                           fromCargo: Boolean): CompletableFuture<CargoActionOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeCargoActionOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("cargo_action_options", fitId, itemId, fromCargo).toString()).also { result ->
                check(result.fitId == fitId && result.itemId == itemId && result.fromCargo == fromCargo &&
                    mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun moduleDefaultsDiagnostics(context: Context): CompletableFuture<List<ModuleDefault>> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable)
            BridgeCodec.decodeModuleDefaults(Python.getInstance().getModule("mobile_runtime")
                .callAttr("module_defaults_diagnostics").toString())
        }, executor)
    }

    fun rackOptions(context: Context, fitId: String): CompletableFuture<RackOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeRackOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("rack_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun rackOptionsDiagnostics(context: Context, fitId: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("rack_options", fitId).toString()
        }, executor)
    }

    fun bulkChargeOptionsDiagnostics(context: Context, fitId: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("bulk_charge_options", fitId).toString()
        }, executor)
    }

    fun bulkStateOptionsDiagnostics(context: Context, fitId: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("bulk_state_options", fitId).toString()
        }, executor)
    }

    fun variationOptions(context: Context, fitId: String): CompletableFuture<VariationOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeVariationOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("variation_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun modeOptions(context: Context, fitId: String): CompletableFuture<ModeOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeModeOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("mode_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun subsystemOptions(context: Context, fitId: String): CompletableFuture<SubsystemOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeSubsystemOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("subsystem_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun structureServiceOptions(context: Context, fitId: String): CompletableFuture<StructureServiceOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeStructureServiceOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("structure_service_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun variationFamiliesDiagnostics(context: Context, fitId: String): CompletableFuture<List<VariationFamily>> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            BridgeCodec.decodeVariationFamilies(Python.getInstance().getModule("mobile_runtime")
                .callAttr("variation_families_diagnostics", fitId).toString())
        }, executor)
    }

    fun variationAdditionDiagnostics(context: Context, fitId: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("variation_addition_diagnostics", fitId).toString()
        }, executor)
    }

    fun chargeOptions(context: Context, fitId: String): CompletableFuture<ChargeOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeChargeOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("charge_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun bulkChargeOptions(context: Context, fitId: String): CompletableFuture<BulkChargeOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeBulkChargeOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("bulk_charge_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun bulkStateOptions(context: Context, fitId: String): CompletableFuture<BulkStateOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeBulkStateOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("bulk_state_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun fillItemOptions(context: Context, fitId: String, itemId: Int): CompletableFuture<FillItemOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeFillItemOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("fill_item_options", fitId, itemId).toString()).also { result ->
                check(result.fitId == fitId && result.itemId == itemId &&
                    mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun cloneVacancyOptions(context: Context, fitId: String): CompletableFuture<CloneVacancyOptions> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            BridgeCodec.decodeCloneVacancyOptions(Python.getInstance().getModule("mobile_runtime")
                .callAttr("clone_vacancy_options", fitId).toString()).also { result ->
                check(result.fitId == fitId && mutableLibrary.value.single { it.id == fitId }.revision == result.revision)
            }
        }, executor)
    }

    fun chargeCompatibilityDiagnostics(context: Context): CompletableFuture<List<ChargeCompatibility>> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            BridgeCodec.decodeChargeCompatibility(Python.getInstance().getModule("mobile_runtime")
                .callAttr("charge_compatibility_diagnostics").toString())
        }, executor)
    }

    fun chargeModuleDiagnostics(context: Context, fitId: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join(); check(!unavailable)
            Python.getInstance().getModule("mobile_runtime").callAttr("charge_module_diagnostics", fitId).toString()
        }, executor)
    }

    @Synchronized
    fun useEphemeralStorageForDiagnostics() {
        check(BuildConfig.DEBUG && startup == null) { "Diagnostics must select storage before engine startup" }
        ephemeralDiagnostics = true
    }

    @Synchronized
    fun start(context: Context): CompletableFuture<FitSnapshot?> {
        startup?.let { return it }
        val app = context.applicationContext
        val requested = SystemClock.elapsedRealtimeNanos()
        return CompletableFuture.supplyAsync({
            try {
                check(Looper.myLooper() != Looper.getMainLooper())
                val workerStarted = SystemClock.elapsedRealtimeNanos()
                val manifestText = app.assets.open("engine/manifest.json").bufferedReader().use { it.readText() }
                val manifest = JSONObject(manifestText)
                val expectedHash = manifest.getString("database_sha256")
                val directory = File(app.filesDir, "game").apply { mkdirs() }
                val database = File(directory, "eve-$expectedHash.db")
                var installed = false
                if (!database.isFile || sha256(database) != expectedHash) {
                    val staging = File(directory, "eve-install.tmp")
                    try {
                        app.assets.open("engine/eve.db").use { source ->
                            staging.outputStream().use { destination -> source.copyTo(destination) }
                        }
                        check(staging.length() == manifest.getLong("database_bytes")) { "Bundled database size mismatch" }
                        check(sha256(staging) == expectedHash) { "Bundled database checksum mismatch" }
                        check(staging.renameTo(database)) { "Could not install bundled game data" }
                        installed = true
                    } finally {
                        staging.delete()
                    }
                }
                val databaseReady = SystemClock.elapsedRealtimeNanos()
                if (!Python.isStarted()) Python.start(AndroidPlatform(app))
                val pythonReady = SystemClock.elapsedRealtimeNanos()
                val case = app.assets.open("engine/vexor.json").bufferedReader().use { it.readText() }
                val module = Python.getInstance().getModule("mobile_runtime")
                val store = if (ephemeralDiagnostics) null else {
                    val fits = File(app.noBackupFilesDir, "fits")
                    check(fits.isDirectory || fits.mkdirs()) { "Could not open saved fit storage" }
                    File(fits, "graph.sqlite3").absolutePath
                }
                module.callAttr("boot", database.absolutePath, manifestText, case, store)
                val bootstrap = BridgeCodec.decodeResponse(module.callAttr("bridge_bootstrap").toString())
                check(bootstrap.requestId == "bootstrap" && bootstrap.isSuccess) {
                    "Invalid engine bootstrap response"
                }
                val savedSampleId = module.callAttr("bridge_sample_id")?.toString()
                val result = bootstrap.fits.find { it.id == savedSampleId } ?: bootstrap.fits.firstOrNull()
                sessionId = bootstrap.sessionId
                sampleId = result?.id
                mutableCatalog.value = HullCatalog.decode(module.callAttr("library_catalog").toString())
                readOrganization()
                readRecent()
                if (!ephemeralDiagnostics) {
                    navigationStore = NavigationStore(File(app.noBackupFilesDir, "library-navigation.json"))
                }
                var navigation = LibraryNavigation(result?.let { listOf(it.id) } ?: emptyList(), result?.id)
                try {
                    navigationStore?.load()?.let { saved ->
                        navigation = (if (saved.restore) saved else saved.copy(openIds = emptyList(), activeId = null))
                            .retain(bootstrap.fits.map { it.id }.toSet())
                    }
                    navigationStore?.save(navigation)
                } catch (_: Exception) {
                    // Preserve damaged preferences and the independently valid fit store.
                    navigationWritable = false
                    mutableNavigationError.value = "Saved navigation could not be read or confirmed. Navigation will last for this session only."
                    navigation = LibraryNavigation()
                }
                publishNavigation(navigation)
                sampleId = navigation.activeId
                val ready = SystemClock.elapsedRealtimeNanos()
                startupMetrics = JSONObject()
                    .put("pid", Process.myPid())
                    .put("process_start_elapsed_ms", Process.getStartElapsedRealtime())
                    .put("engine_ready_elapsed_ms", ready / 1e6)
                    .put("engine_start_to_ready_ms", (ready - requested) / 1e6)
                    .put("queue_ms", (workerStarted - requested) / 1e6)
                    .put("database_ms", (databaseReady - workerStarted) / 1e6)
                    .put("python_start_ms", (pythonReady - databaseReady) / 1e6)
                    .put("python_boot_snapshot_ms", (ready - pythonReady) / 1e6)
                    .put("database_installed", installed)
                    .put("database_sha256", expectedHash)
                mutableLibrary.value = bootstrap.fits
                if (!ephemeralDiagnostics) {
                    readOfflineFeatures(sampleId)
                    importStore = OfflineImportStore(File(app.noBackupFilesDir, "fits/pending-eft-import.json"))
                    try { mutablePendingImport.value = importStore?.load() }
                    catch (_: Exception) { mutableImportStorageError.value = "An earlier import retry record could not be read. It has been preserved; importing is blocked until recovered." }
                }
                publishSelection()
                result
            } catch (error: Exception) {
                if (BuildConfig.DEBUG) Log.e("PyfaEngine", "Engine startup failed", error)
                mutableState.value = EngineState.Failed(error.message ?: "The fitting engine could not start.")
                throw error
            }
        }, executor).also { startup = it }
    }

    /** Called after Compose reports the ready data drawn; no disk I/O on the UI thread. */
    @Synchronized
    fun recordStartupDraw(context: Context) {
        if (!BuildConfig.DEBUG || startupDrawRecorded || state.value !is EngineState.Ready && state.value !is EngineState.Empty) return
        startupDrawRecorded = true
        val drawn = SystemClock.elapsedRealtimeNanos() / 1e6
        val app = context.applicationContext
        executor.execute {
            val report = checkNotNull(startupMetrics)
                .put("ready_draw_elapsed_ms", drawn)
                .put("process_to_ready_draw_ms", drawn - Process.getStartElapsedRealtime())
                .put("ready_to_draw_ms", drawn - checkNotNull(startupMetrics).getDouble("engine_ready_elapsed_ms"))
                .put("memory", memorySnapshot())
            val staging = File(app.filesDir, "a10-startup.tmp")
            staging.writeText(report.toString(2))
            check(staging.renameTo(File(app.filesDir, "a10-startup.json")))
        }
    }

    /** App process snapshots, not peaks; Android may omit protected graphics allocations. */
    fun memorySnapshot(): JSONObject {
        val info = Debug.MemoryInfo()
        Debug.getMemoryInfo(info)
        return JSONObject().put("total_pss_kb", info.totalPss)
            .put("total_private_dirty_kb", info.totalPrivateDirty)
            .put("native_heap_allocated_bytes", Debug.getNativeHeapAllocatedSize())
            .put("java_heap_used_bytes", Runtime.getRuntime().totalMemory() - Runtime.getRuntime().freeMemory())
    }

    fun prepareBenchmark(context: Context, kind: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        val app = context.applicationContext
        return CompletableFuture.supplyAsync({
            ready.join()
            val case = when (kind) {
                "ammunition" -> "{}"
                "projection", "command" -> app.assets.open("engine/$kind.json").bufferedReader().use { it.readText() }
                else -> error("Unknown benchmark kind: $kind")
            }
            Python.getInstance().getModule("mobile_runtime").callAttr("prepare_benchmark", kind, case).toString()
        }, executor)
    }

    fun stepBenchmark(operation: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        return CompletableFuture.supplyAsync({
            checkNotNull(startup).join()
            Python.getInstance().getModule("mobile_runtime").callAttr("step_benchmark", operation).toString()
        }, executor)
    }

    /** All encoding, Python calls, decoding and publication use the same EOS worker. */
    fun request(
        context: Context,
        operation: BridgeOperation,
        expectedRevisions: Map<String, Long> = emptyMap(),
    ): CompletableFuture<BridgeResponse> {
        val ready = start(context)
        // Capture caller-owned collections before enqueueing.
        val capturedOperation = operation.snapshotArguments()
        val revisions = expectedRevisions.toMap()
        return CompletableFuture.supplyAsync({
            ready.join()
            check(Looper.myLooper() != Looper.getMainLooper())
            try {
                val request = BridgeRequest(UUID.randomUUID().toString(), checkNotNull(sessionId), capturedOperation, revisions)
                if (unavailable) {
                    return@supplyAsync BridgeResponse(request.requestId, request.sessionId, BridgeStatus.ERROR,
                        emptyList(), BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,
                            "Restart the app to recover the fitting engine."))
                }
                val encoded = try {
                    BridgeCodec.encodeRequest(request)
                } catch (_: BridgeProtocolException) {
                    val error = BridgeError(BridgeErrorCode.INVALID_REQUEST, "The edit request is invalid.")
                    val previous = mutableState.value as? EngineState.Ready
                    if (previous != null) mutableState.value = previous.copy(error = error)
                    else if (mutableState.value is EngineState.Empty) mutableState.value = EngineState.Empty(error)
                    return@supplyAsync BridgeResponse(request.requestId, request.sessionId,
                        BridgeStatus.ERROR, emptyList(), error)
                }
                val response = BridgeCodec.decodeResponse(Python.getInstance().getModule("mobile_runtime")
                    .callAttr("bridge_dispatch", encoded).toString())
                check(response.requestId == request.requestId && response.sessionId == request.sessionId) {
                    "Engine response does not match its request"
                }
                val previous = mutableState.value as? EngineState.Ready
                if (response.isSuccess) {
                    val complete = !ephemeralDiagnostics && (capturedOperation is BridgeOperation.Undo || capturedOperation is BridgeOperation.Redo) ||
                        capturedOperation is BridgeOperation.RenameFit ||
                        capturedOperation is BridgeOperation.DuplicateFit || capturedOperation is BridgeOperation.DeleteFit ||
                        capturedOperation is BridgeOperation.Snapshot && capturedOperation.fitIds.isEmpty()
                    val merged = if (complete) response.fits else {
                        val changed = response.fits.associateBy { it.id }
                        mutableLibrary.value.map { changed[it.id] ?: it } +
                            response.fits.filter { fit -> mutableLibrary.value.none { it.id == fit.id } }
                    }
                    mutableLibrary.value = merged
                    readOrganization()
                    val retained = mutableNavigation.value.retain(merged.map { it.id }.toSet())
                    if (retained != mutableNavigation.value) {
                        // Deletion already committed; never keep a deleted view active if preference I/O fails.
                        saveNavigation(retained)
                        publishNavigation(retained)
                    }
                    if (!ephemeralDiagnostics) {
                        readOfflineFeatures(mutableNavigation.value.activeId)
                        // Another fit's ordinary edit can invalidate a shared history action
                        // without changing the currently visible fit revision.
                        if (capturedOperation !is BridgeOperation.Snapshot) mutableFeatureEpoch.value += 1
                    }
                    publishSelection()
                } else {
                    if (response.error?.code == BridgeErrorCode.ENGINE_UNAVAILABLE) unavailable = true
                    if (!unavailable && !ephemeralDiagnostics) {
                        // A confirmed rejected fitting attempt can commit Recent metadata
                        // without changing fit revisions/history. Publish its durable context
                        // before exposing the rejection so graph/export/profile callers agree.
                        val beforeContext = mutableOfflineFeatures.value?.context
                        val refreshed = readOfflineFeatures(mutableNavigation.value.activeId)
                        if (refreshed.context != beforeContext) mutableFeatureEpoch.value += 1
                    }
                    if (previous != null) mutableState.value = previous.copy(error = response.error)
                    else mutableState.value = EngineState.Empty(response.error)
                }
                // Desktop recent use includes rejected fitting attempts. A stale
                // or malformed request leaves this independently confirmed list unchanged.
                if (!unavailable) readRecent()
                response
            } catch (error: Exception) {
                // A failed call may have committed before its reply was lost. Do
                // not accept later snapshots after losing that known boundary.
                unavailable = true
                val previous = mutableState.value as? EngineState.Ready
                if (previous != null) mutableState.value = previous.copy(error = BridgeError(
                    BridgeErrorCode.ENGINE_UNAVAILABLE, "The fitting engine returned an invalid response. Restart the app.",
                ))
                if (previous == null) mutableState.value = EngineState.Empty(BridgeError(
                    BridgeErrorCode.ENGINE_UNAVAILABLE, "Restart the app to recover the fitting engine."))
                throw error
            }
        }, executor)
    }

    fun selectFit(context: Context, id: String): CompletableFuture<Unit> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(!unavailable) { "Restart the app to recover the fitting engine." }
            val fit = mutableLibrary.value.single { it.id == id }
            val next = mutableNavigation.value.open(fit.id)
            if (saveNavigation(next)) {
                publishNavigation(next)
                if (!ephemeralDiagnostics) readOfflineFeatures(next.activeId)
                publishSelection()
            }
            Unit
        }, executor)
    }

    private fun stageOrganization(): Map<String, Long> {
        val value = JSONObject(Python.getInstance().getModule("mobile_runtime").callAttr("library_organization").toString())
        check(value.getInt("version") == 1)
        val rows = value.getJSONObject("modified")
        return rows.keys().asSequence().associateWith { id -> rows.getLong(id).also { check(it >= 0) } }
    }
    private fun readOrganization() { mutableModified.value = stageOrganization() }
    private fun stageRecent(): List<Int> = BridgeCodec.decodeRecent(Python.getInstance().getModule("mobile_runtime")
        .callAttr("recent_items").toString())
    private fun readRecent() { mutableRecent.value = stageRecent() }

    private fun publishSelection() {
        sampleId = mutableNavigation.value.activeId
        val error = if (unavailable) BridgeError(BridgeErrorCode.ENGINE_UNAVAILABLE,
            "Restart the app to recover the fitting engine.") else null
        mutableState.value = mutableLibrary.value.find { it.id == sampleId }?.let { EngineState.Ready(it, error) } ?: EngineState.Empty(error)
    }

    private fun saveNavigation(next: LibraryNavigation): Boolean {
        if (!navigationWritable) return true // Explicitly reported session-only fallback.
        return try {
            navigationStore?.save(next)
            mutableNavigationError.value = null
            true
        } catch (_: Exception) {
            mutableNavigationError.value = "Could not confirm saved navigation preferences. The current view is unchanged; try again."
            false
        }
    }

    fun navigate(context: Context, change: (LibraryNavigation) -> LibraryNavigation): CompletableFuture<Unit> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            val next = change(mutableNavigation.value).retain(mutableLibrary.value.map { it.id }.toSet())
            if (saveNavigation(next)) {
                publishNavigation(next)
                if (!ephemeralDiagnostics) readOfflineFeatures(next.activeId)
                publishSelection()
            }
            Unit
        }, executor)
    }

    fun createEmptyFit(context: Context, hull: String, name: String): CompletableFuture<BridgeResponse> {
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(catalog.value.hulls.any { it.name == hull }) { "Choose a bundled hull" }
            FitSpec(name, hull, 5, false, DamagePattern(25.0, 25.0, 25.0, 25.0),
                Security(SystemSecurity.HISEC, 0.0), emptyList(), emptyList())
        }, executor).thenCompose { request(context, BridgeOperation.CreateFit(it)) }
    }

    fun createFromExample(context: Context, example: String, name: String): CompletableFuture<BridgeResponse> {
        val ready = start(context)
        val app = context.applicationContext
        return CompletableFuture.supplyAsync({
            ready.join()
            check(example in listOf("Vexor", "Celestis", "Vulture"))
            val asset = when (example) { "Vexor" -> "vexor"; "Celestis" -> "projection"; else -> "command" }
            val case = JSONObject(app.assets.open("engine/$asset.json").bufferedReader().use { it.readText() })
            val spec = if (example == "Vexor") case.apply { remove("edit") } else case.getJSONObject("source")
            BridgeCodec.decodeFitSpec(spec).copy(name = name)
        }, executor).thenCompose { request(context, BridgeOperation.CreateFit(it)) }
    }

    fun setAmmunition(context: Context, name: String): CompletableFuture<BridgeResponse> {
        val current = (state.value as? EngineState.Ready)?.fit
            ?: return CompletableFuture<BridgeResponse>().also {
                it.completeExceptionally(IllegalStateException("Wait for the fit to load"))
            }
        return request(context, BridgeOperation.SetCharges(current.id, listOf(0, 1), name),
            mapOf(current.id to current.revision))
    }

    fun bridgeDiagnostics(context: Context): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(Looper.myLooper() != Looper.getMainLooper())
            val report = JSONObject(Python.getInstance().getModule("mobile_runtime").callAttr("bridge_diagnostics").toString())
            // Capture the original Python JSON types before this first native
            // serialization normalizes whole-number decimals into integers.
            val settings = report.getJSONObject("eos_settings")
            val numericTypes = JSONObject()
            settings.keys().forEach { name ->
                when (settings.get(name)) {
                    is Int, is Long -> numericTypes.put("root.$name", "integer")
                    is Double -> numericTypes.put("root.$name", "decimal")
                }
            }
            report.put("eos_settings_numeric_types", numericTypes)
                .put("android_worker_thread", Thread.currentThread().name)
                .put("android_main_thread", Looper.myLooper() == Looper.getMainLooper()).toString()
        }, executor)
    }

    fun verifyAmmunition(context: Context): CompletableFuture<String> {
        val ready = start(context)
        // The report is returned to native tests; the UI retains its sample snapshot.
        return CompletableFuture.supplyAsync({
            ready.join()
            Python.getInstance().getModule("mobile_runtime").callAttr("verify_ammunition").toString()
        }, executor)
    }

    fun verifyResources(context: Context, casesJson: String): CompletableFuture<String> {
        check(BuildConfig.DEBUG)
        val ready = start(context)
        return CompletableFuture.supplyAsync({
            ready.join()
            check(Looper.myLooper() != Looper.getMainLooper())
            Python.getInstance().getModule("mobile_runtime").callAttr("verify_resources", casesJson).toString()
        }, executor)
    }

    fun verifyProjection(context: Context): CompletableFuture<String> {
        val ready = start(context)
        val app = context.applicationContext
        return CompletableFuture.supplyAsync({
            ready.join()
            check(Looper.myLooper() != Looper.getMainLooper())
            val case = app.assets.open("engine/projection.json").bufferedReader().use { it.readText() }
            Python.getInstance().getModule("mobile_runtime").callAttr("verify_projection", case).toString()
        }, executor)
    }

    fun verifyCommand(context: Context): CompletableFuture<String> {
        val ready = start(context)
        val app = context.applicationContext
        return CompletableFuture.supplyAsync({
            ready.join()
            check(Looper.myLooper() != Looper.getMainLooper())
            val case = app.assets.open("engine/command.json").bufferedReader().use { it.readText() }
            Python.getInstance().getModule("mobile_runtime").callAttr("verify_command", case).toString()
        }, executor)
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
