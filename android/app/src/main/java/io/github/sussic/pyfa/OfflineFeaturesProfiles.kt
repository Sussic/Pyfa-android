package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers
import org.json.JSONObject

enum class OfflineProfileSection { SKILLS, IMPLANTS, SECURITY }
data class ProfileSecurityDraft(val profileId: String, val revision: Long, val sessionId: String, val original: SecurityNumber)
data class ProfileImplantChoice(val context: OfflineContext, val profile: OfflineProfile, val assignedCount: Int)
data class ProfileImplantReplacement(val choice: ProfileImplantChoice, val item: CharacterImplantItem, val occupant: OfflineProfileImplant)
data class OfflineProfileDelete(val context: OfflineContext, val profile: OfflineProfile, val replacement: OfflineProfile, val assignedCount: Int)

/** One owned request at a time. Navigation queues a refresh, never frees an in-flight owner. */
class OfflineProfilesModel(
    private val featureContext: () -> OfflineContext? = { EngineRuntime.offlineFeatures.value?.context },
    private val engineAvailable: () -> Boolean = { when (val engine = EngineRuntime.state.value) {
        is EngineState.Ready -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        is EngineState.Empty -> engine.error?.code != BridgeErrorCode.ENGINE_UNAVAILABLE
        else -> false
    } },
    private val read: (Context, String?) -> java.util.concurrent.CompletableFuture<OfflineFeatureState> = EngineRuntime::offlineFeatureState,
    private val mutate: (Context, OfflineContext, String, JSONObject, String?) -> java.util.concurrent.CompletableFuture<OfflineFeatureResponse> =
        { context, expected, operation, arguments, anchor -> EngineRuntime.offlineFeatureRequest(context, expected, operation, arguments, anchor) },
) : ViewModel() {
    var state by mutableStateOf<OfflineFeatureState?>(null); private set
    var loading by mutableStateOf(false); private set
    var saving by mutableStateOf(false); private set
    var reopenRequired by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var message by mutableStateOf<String?>(null); private set
    var profileId by mutableStateOf<String?>(null); private set
    var skillId by mutableStateOf<Int?>(null); private set
    var draftLevel by mutableStateOf<Int?>(null); private set
    var dirty by mutableStateOf(false); private set
    var conflict by mutableStateOf(false); private set
    var securityText by mutableStateOf(""); private set
    var securityDirty by mutableStateOf(false); private set
    var securityConflict by mutableStateOf(false); private set
    private var securityDraft: ProfileSecurityDraft? = null
    val hasDraft get() = dirty || securityDirty
    val securityValue get() = PilotSecurityCodec.entry(securityText)

    var section by mutableStateOf(OfflineProfileSection.SKILLS); private set
    var implantPage by mutableStateOf(0); private set
    var implantChoice by mutableStateOf<ProfileImplantChoice?>(null); private set
    var implantReplacement by mutableStateOf<ProfileImplantReplacement?>(null); private set
    var deleteConfirmation by mutableStateOf<OfflineProfileDelete?>(null); private set
    var query by mutableStateOf("")
    var name by mutableStateOf("")
    var replacementId by mutableStateOf("builtin:all5")
    private var draftRevision: Long? = null
    private var draftSession: String? = null
    private var anchor: String? = null
    private var owner: Any? = null
    private var refreshPending = false
    private var cleared = false
    private var requestedProfileId: String? = null
    private var visible = true
    private var screenToken = Any()
    fun open() { if (!visible) { visible = true; screenToken = Any(); error = null; message = null } }
    fun close() {
        visible = false; screenToken = Any(); refreshPending = false
        implantChoice = null; implantReplacement = null; deleteConfirmation = null
        // Keep physical owner and both draft kinds until their own completion/revert.
    }

    val selectedProfile get() = state?.profiles?.find { it.id == profileId }
    val available get() = visible && !cleared && !loading && !saving && !reopenRequired && engineAvailable() && state != null && state?.context == featureContext()
    val implantReplacementCurrent get() = implantReplacement?.let { currentChoice(it.choice) } == true
    val deleteCurrent get() = deleteConfirmation?.let { available && !hasDraft && state?.context == it.context && selectedProfile == it.profile &&
        state?.profiles?.any { row -> row == it.replacement } == true && replacementId == it.replacement.id } == true

    fun load(context: Context, fitId: String?) {
        if (!visible || cleared) return
        anchor = fitId; refreshPending = true
        val currentSession = featureContext()?.sessionId
        if (currentSession != null && state?.context?.sessionId != null && state?.context?.sessionId != currentSession) {
            reopenRequired = false
            if (dirty) conflict = true
            if (securityDirty) securityConflict = true
        }
        if (owner == null) readLatest(context)
    }
    private fun readLatest(context: Context) {
        if (!visible || cleared || owner != null || reopenRequired || !engineAvailable()) return
        val token = Any(); owner = token; refreshPending = false
        val target = anchor; val expected = featureContext(); val view = screenToken
        loading = true; error = null
        val pending = try { read(context, target) }
        catch (_: Exception) { owner = null; loading = false; error = "Profiles could not be loaded. Retry after checking the engine."; return }
        pending.whenCompleteAsync({ value, failure ->
            if (owner === token && !cleared) {
                owner = null; loading = false
                if (!visible || view !== screenToken) { if (visible) refreshPending = true }
                else if (failure != null) error = "Profiles could not be loaded. Try again after checking the engine."
                else if (target != anchor || value.selectedFitId != target || value.context != featureContext() ||
                    expected?.sessionId != value.context.sessionId) refreshPending = true
                else accept(value)
                if (refreshPending) readLatest(context)
            }
        }, ContextCompat.getMainExecutor(context))
    }
    private fun accept(value: OfflineFeatureState) {
        state = value
        if (!hasDraft && requestedProfileId != null && value.profiles.any { it.id == requestedProfileId }) {
            profileId = requestedProfileId; skillId = null; requestedProfileId = null
        }
        if (value.profiles.none { it.id == profileId }) {
            if (hasDraft) {
                conflict = dirty; securityConflict = securityDirty
                error = "The profile for your unsaved change no longer exists. Your draft is kept until you discard it."
                return
            }
            profileId = value.selectedFitId?.let { value.bindings[it]?.profileId } ?: "builtin:all5"
            skillId = null; conflict = false; draftRevision = null
        }
        val profile = selectedProfile ?: return
        if (dirty) conflict = draftRevision != profile.revision || draftSession != value.context.sessionId
        else { draftLevel = skillId?.let(profile::level); draftRevision = profile.revision; draftSession = value.context.sessionId; conflict = false }
        if (securityDirty) securityConflict = securityDraft?.let {
            it.profileId != profile.id || it.revision != profile.revision || it.sessionId != value.context.sessionId || it.original != profile.secStatus
        } != false
        else resetSecurityDraft(profile, value.context)
        implantPage = implantPage.coerceAtMost((profile.implants.size - 1).coerceAtLeast(0) / 25)
    }
    /** Opens the owning character, never whichever fit becomes active after the tap. */
    fun openImplants(id: String) {
        section = OfflineProfileSection.IMPLANTS
        if (hasDraft || saving) { error = "Save or revert the profile draft before editing another character."; return }
        requestedProfileId = id
        if (state?.profiles?.any { it.id == id } == true) { selectProfile(id); requestedProfileId = null }
    }
    fun showSection(value: OfflineProfileSection) { section = value }
    fun selectProfile(id: String) {
        if (saving || hasDraft || state?.profiles?.none { it.id == id } != false) return
        profileId = id; skillId = null; draftRevision = selectedProfile?.revision; draftSession = state?.context?.sessionId
        conflict = false; message = null; error = null; name = ""; implantPage = 0
        implantChoice = null; implantReplacement = null; deleteConfirmation = null
        selectedProfile?.let { profile -> state?.context?.let { resetSecurityDraft(profile, it) } }
    }
    fun selectSkill(id: Int) {
        val profile = selectedProfile ?: return
        if (!available || hasDraft || state?.skills?.none { it.id == id } != false) return
        skillId = id; draftLevel = profile.level(id); draftRevision = profile.revision; draftSession = state?.context?.sessionId
        conflict = false; message = null
    }
    fun editLevel(level: Int?) {
        val profile = selectedProfile ?: return; val skill = skillId ?: return
        if (profile.readonly || !available || conflict || securityDirty) return
        require(level == null || level in 0..5)
        draftLevel = level; dirty = draftLevel != profile.level(skill); message = null
    }
    fun revert() {
        if (saving || securityDirty) return
        val profile = selectedProfile
        if (profile == null) {
            dirty = false; conflict = false; skillId = null; draftLevel = null; draftRevision = null; draftSession = null
            profileId = "builtin:all5"; error = null; return
        }
        draftLevel = skillId?.let(profile::level); draftRevision = profile.revision; draftSession = state?.context?.sessionId
        dirty = false; conflict = false; error = null
    }
    private fun resetSecurityDraft(profile: OfflineProfile, context: OfflineContext) {
        securityDraft = ProfileSecurityDraft(profile.id, profile.revision, context.sessionId, profile.secStatus)
        securityText = profile.secStatus.toString(); securityDirty = false; securityConflict = false
    }
    fun editSecurity(value: String) {
        val profile = selectedProfile ?: return; val current = state ?: return
        if (!available || dirty || profile.readonly || securityConflict) return
        if (!securityDirty) securityDraft = ProfileSecurityDraft(profile.id, profile.revision, current.context.sessionId, profile.secStatus)
        securityText = value; securityDirty = value != profile.secStatus.toString(); message = null
    }
    fun revertSecurity() {
        if (owner != null || saving) return
        val profile = selectedProfile; val current = state
        if (profile != null && current != null) resetSecurityDraft(profile, current.context)
        else {
            securityDirty = false; securityConflict = false; securityDraft = null; securityText = ""
            current?.profiles?.singleOrNull { it.id == "builtin:all5" }?.let {
                profileId = it.id; skillId = null; resetSecurityDraft(it, current.context)
            }
        }
        error = null
    }
    fun saveSecurity(context: Context, saveAs: Boolean = false) {
        val profile = selectedProfile ?: return; val current = state ?: return
        val draft = securityDraft ?: return; val number = securityValue ?: return
        if (!available || dirty || profile.readonly || securityConflict ||
            draft.profileId != profile.id || draft.revision != profile.revision || draft.sessionId != current.context.sessionId || draft.original != profile.secStatus ||
            (!saveAs && !securityDirty) || (saveAs && name.trim().isEmpty())) return
        val before = current.profiles.map { it.id }.toSet()
        val args = JSONObject().put("profile_id", profile.id).put("revision", profile.revision)
            .put("sec_status", number.raw).put("save_as", if (saveAs) name.trim() else JSONObject.NULL)
        dispatch(context, "save_profile_security", args, clearSecurity = true) { value ->
            if (saveAs) value.profiles.singleOrNull { it.id !in before }?.let {
                profileId = it.id; skillId = null; name = ""; implantPage = 0
                resetSecurityDraft(it, value.context)
            }
        }
    }
    fun save(context: Context) {
        val profile = selectedProfile ?: return; val skill = skillId ?: return
        if (!dirty || conflict || profile.readonly || draftRevision != profile.revision || draftSession != state?.context?.sessionId) return
        dispatch(context, "set_profile_skill", JSONObject().put("profile_id", profile.id)
            .put("revision", profile.revision).put("skill_id", skill).put("level", draftLevel ?: JSONObject.NULL), clearDraft = true)
    }
    fun create(context: Context) {
        val source = selectedProfile ?: return; val requestedName = name.trim()
        if (requestedName.isEmpty() || hasDraft) return
        val before = state?.profiles?.map { it.id }?.toSet().orEmpty()
        dispatch(context, "create_profile", JSONObject().put("name", requestedName).put("source", source.id)) { value ->
            value.profiles.singleOrNull { it.id !in before }?.let {
                profileId = it.id; skillId = null; name = ""; implantPage = 0; resetSecurityDraft(it, value.context)
            }
        }
    }
    fun rename(context: Context) {
        val profile = selectedProfile ?: return
        if (profile.readonly || name.trim().isEmpty() || hasDraft) return
        dispatch(context, "rename_profile", JSONObject().put("profile_id", profile.id).put("revision", profile.revision).put("name", name.trim())) { name = "" }
    }
    fun assign(context: Context) {
        val fitId = anchor ?: return; val profile = selectedProfile ?: return
        if (hasDraft) return
        dispatch(context, "assign_profile", JSONObject().put("fit_id", fitId).put("profile_id", profile.id))
    }
    fun requestDelete() {
        val profile = selectedProfile ?: return; val current = state ?: return
        val replacement = current.profiles.singleOrNull { it.id == replacementId && it.id != profile.id } ?: return
        if (!available || profile.readonly || hasDraft) return
        deleteConfirmation = OfflineProfileDelete(current.context, profile, replacement, current.bindings.count { it.value.profileId == profile.id })
    }
    fun dismissDelete() { if (!saving) deleteConfirmation = null }
    fun delete(context: Context) {
        val pending = deleteConfirmation ?: return
        if (!deleteCurrent) { error = "Deletion impact changed. Cancel and review the current profile."; return }
        deleteConfirmation = null
        dispatch(context, "delete_profile", JSONObject().put("profile_id", pending.profile.id).put("replacement", pending.replacement.id))
    }
    fun history(context: Context, redo: Boolean) {
        if (!hasDraft) dispatch(context, if (redo) "redo" else "undo", JSONObject())
    }
    fun beginImplantAdd() {
        val profile = selectedProfile ?: return; val current = state ?: return
        if (!available || hasDraft || profile.readonly) return
        implantChoice = ProfileImplantChoice(current.context, profile, current.bindings.count { it.value.profileId == profile.id }); implantReplacement = null
    }
    fun closeImplantPicker() { if (!saving) { implantChoice = null; implantReplacement = null } }
    private fun currentChoice(choice: ProfileImplantChoice) = available && !hasDraft && state?.context == choice.context &&
        selectedProfile == choice.profile && !choice.profile.readonly
    fun chooseImplant(context: Context, item: CharacterImplantItem) {
        val choice = implantChoice ?: return
        if (!currentChoice(choice)) { error = "This character changed. Close the picker and check its current implants."; return }
        val occupant = choice.profile.implants.singleOrNull { it.slot == item.slot }
        if (occupant != null) implantReplacement = ProfileImplantReplacement(choice, item, occupant)
        else addImplant(context, choice, item, null)
    }
    fun cancelImplantReplacement() { if (!saving) implantReplacement = null }
    fun confirmImplantReplacement(context: Context) {
        val pending = implantReplacement ?: return
        if (!implantReplacementCurrent) { error = "The character changed. Cancel and review the current slot."; return }
        addImplant(context, pending.choice, pending.item, pending.occupant.implantId)
    }
    private fun addImplant(context: Context, choice: ProfileImplantChoice, item: CharacterImplantItem, occupant: String?) {
        if (!currentChoice(choice)) return
        dispatch(context, "add_profile_implant", JSONObject().put("profile_id", choice.profile.id).put("revision", choice.profile.revision)
            .put("item_id", item.itemId).put("replace_implant_id", occupant ?: JSONObject.NULL)) {
            implantChoice = null; implantReplacement = null
        }
    }
    fun removeImplant(context: Context, before: OfflineProfile, row: OfflineProfileImplant) {
        if (!available || hasDraft || before !== selectedProfile || before.readonly || before.implants.none { it === row }) return
        dispatch(context, "remove_profile_implant", JSONObject().put("profile_id", before.id).put("revision", before.revision).put("implant_id", row.implantId))
    }
    fun showImplantPage(page: Int) { if (!saving) implantPage = page.coerceIn(0, ((selectedProfile?.implants?.size ?: 0) - 1).coerceAtLeast(0) / 25) }
    private fun dispatch(context: Context, operation: String, arguments: JSONObject, clearDraft: Boolean = false, clearSecurity: Boolean = false,
        success: (OfflineFeatureState) -> Unit = {}) {
        val before = state ?: return
        if (!available || owner != null) return
        val token = Any(); owner = token; val target = anchor; val view = screenToken
        saving = true; error = null; message = null
        val pending = try { mutate(context, before.context, operation, arguments, target) }
        catch (_: Exception) { owner = null; saving = false; error = "The request was invalid. Check its values before saving."; return }
        pending.whenCompleteAsync({ result, failure ->
            if (owner === token && !cleared) {
                owner = null; saving = false
                if (featureContext()?.sessionId != before.context.sessionId || featureContext()?.datasetSha256 != before.context.datasetSha256) {
                    conflict = dirty; securityConflict = securityDirty; refreshPending = visible
                } else if (!visible || view !== screenToken) {
                    // Release only this physical operation. Never clear/relabel a newer view or draft.
                    if (visible) refreshPending = true
                    if (featureContext()?.sessionId == before.context.sessionId &&
                        (failure != null || result?.reopenRequired == true || result?.committed == null)) reopenRequired = true
                } else if (failure != null || result?.reopenRequired == true || result?.committed == null) {
                    reopenRequired = true
                    error = "The save could not be confirmed. Keep this draft and restart the app to check saved changes."
                } else if (!result.ok) {
                    error = result.error?.message ?: "The change was not saved."
                    if (result.error?.code in setOf("stale_context", "conflict", "stale_profile", "profile_mismatch")) {
                        conflict = dirty; securityConflict = securityDirty
                    }
                } else {
                    val updated = checkNotNull(result.state)
                    if (updated.context == featureContext()) {
                        if (clearDraft) dirty = false
                        if (clearSecurity) securityDirty = false
                        accept(updated); success(updated)
                        message = if (result.committed == true) "Saved. Shared profiles recalculate every assigned fit." else "Already selected. No saved values changed."
                    } else { conflict = dirty; securityConflict = securityDirty; refreshPending = true }
                    if (target != anchor) refreshPending = true
                }
                if (refreshPending && !reopenRequired) readLatest(context)
            }
        }, ContextCompat.getMainExecutor(context))
    }
    override fun onCleared() { cleared = true; super.onCleared() }
}

@Composable
internal fun OfflineProfilesView(model: OfflineProfilesModel, equipmentModel: EquipmentModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val published by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    var confirmLeave by rememberSaveable { mutableStateOf(false) }
    fun leave() {
        when {
            model.implantReplacement != null -> model.cancelImplantReplacement()
            model.implantChoice != null -> model.closeImplantPicker()
            model.hasDraft && model.selectedProfile != null -> confirmLeave = true
            else -> { model.close(); onBack() }
        }
    }
    DisposableEffect(model) { model.open(); onDispose { model.close() } }
    BackHandler { leave() }
    LaunchedEffect(fit?.id, published?.context) {
        model.load(context, fit?.id)
    }
    Text("Offline character profiles", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = { leave() }, modifier = Modifier.testTag("profiles-back")) { Text("Back") }
    Text(fit?.let { "Assign skills and character implants to ${it.name}" } ?: "Manage profiles without opening a fit.")
    if (model.loading) Text("Loading profiles…", Modifier.testTag("profiles-loading"))
    if (model.saving) Text("Saving and recalculating…", Modifier.testTag("profiles-saving"))
    model.error?.let {
        Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.testTag("profiles-error"))
        TextButton(onClick = { model.load(context, fit?.id) }, enabled = !model.saving && !model.loading && !model.reopenRequired,
            modifier = Modifier.testTag("profiles-reload")) { Text("Reload saved profiles") }
    }
    model.message?.let { Text(it, Modifier.testTag("profiles-message")) }
    val state = model.state ?: return
    val available = model.available
    if (model.implantChoice != null) {
        CharacterImplantPicker(model, equipmentModel)
        return
    }
    Row {
        Button(onClick = { model.history(context, false) }, enabled = available && !model.hasDraft && state.history.undoCount > 0,
            modifier = Modifier.testTag("profiles-undo")) { Text("Undo") }
        TextButton(onClick = { model.history(context, true) }, enabled = available && !model.hasDraft && state.history.redoCount > 0,
            modifier = Modifier.testTag("profiles-redo")) { Text("Redo") }
    }
    Text(state.history.undoLabel?.let { "Undo: $it" } ?: "No undo action", Modifier.testTag("profiles-history"))
    for (profile in state.profiles) {
        TextButton(onClick = { model.selectProfile(profile.id) }, enabled = available && !model.hasDraft,
            modifier = Modifier.testTag("profile-select-${profile.id}")) {
            Text((if (model.profileId == profile.id) "✓ " else "") + profile.name + if (profile.readonly) " · built-in" else "")
        }
    }
    val profile = model.selectedProfile
    if (profile == null) {
        if (model.hasDraft) {
            if (model.securityDirty) {
                Text("Unsaved security: ${model.securityText}. The original profile is missing.")
                TextButton(onClick = model::revertSecurity, enabled = available) { Text("Discard security draft") }
            }
            if (model.dirty) Text("Unsaved skill ${model.skillId}: ${model.draftLevel?.toString() ?: "Unlearned"}. The original profile is missing.", Modifier.testTag("profile-orphaned-draft"))
            if (model.dirty) TextButton(onClick = { model.revert() }, enabled = available, modifier = Modifier.testTag("profile-discard-orphan")) { Text("Discard this draft") }
        }
        return
    }
    val assigned = state.bindings.filterValues { it.profileId == profile.id }.keys
    Text("${profile.name} · assigned to ${assigned.size} fit(s)", Modifier.testTag("profile-selected"))
    if (fit != null) Button(onClick = { model.assign(context) },
        enabled = available && !model.hasDraft && state.bindings[fit.id]?.profileId != profile.id,
        modifier = Modifier.testTag("profile-assign")) { Text("Use for ${fit.name}") }
    if (profile.readonly) Text("Built-ins are read-only. Duplicate the complete profile before changing skills, implants or security.", Modifier.testTag("profile-readonly"))
    OutlinedTextField(value = model.name, onValueChange = { model.name = it }, label = { Text("Profile name") },
        enabled = available && !model.dirty, singleLine = true, modifier = Modifier.fillMaxWidth().testTag("profile-name"))
    Row {
        Button(onClick = { model.create(context) }, enabled = available && !model.hasDraft && model.name.isNotBlank(),
            modifier = Modifier.testTag("profile-copy")) { Text("Duplicate complete profile") }
        if (!profile.readonly) TextButton(onClick = { model.rename(context) }, enabled = available && !model.hasDraft && model.name.isNotBlank(),
            modifier = Modifier.testTag("profile-rename")) { Text("Rename") }
    }
    Text("Duplicates copy all skills, implant values and security into an independent character.", Modifier.testTag("profile-copy-scope"))
    Row {
        TextButton(onClick = { model.showSection(OfflineProfileSection.SKILLS) }, modifier = Modifier.testTag("profile-section-skills")) { Text("Skills") }
        TextButton(onClick = { model.showSection(OfflineProfileSection.IMPLANTS) }, modifier = Modifier.testTag("profile-section-implants")) { Text("Implants") }
        TextButton(onClick = { model.showSection(OfflineProfileSection.SECURITY) }, modifier = Modifier.testTag("profile-section-security")) { Text("Security") }
    }
    if (model.securityDirty && model.section != OfflineProfileSection.SECURITY) {
        Text("Unsaved character security. Save or revert it in Security before other profile changes.", Modifier.testTag("profile-security-held-draft"))
    }
    if (model.section == OfflineProfileSection.SECURITY) {
        ProfileSecuritySection(model, profile, assigned.size)
    } else if (model.section == OfflineProfileSection.IMPLANTS) {
        Text("${profile.name} · ${profile.implants.size} character implants · ${assigned.size} assigned fit(s)", Modifier.testTag("profile-implants-summary"))
        if (model.dirty) {
            Text("Unsaved skill change. Save or revert before changing implants, copying, assigning, or deleting this character.", Modifier.testTag("profile-dirty"))
            if (model.conflict) Text("The saved profile changed. Your draft is kept; revert before editing again.", Modifier.testTag("profile-conflict"))
            Row {
                Button(onClick = { model.save(context) }, enabled = available && !model.conflict, modifier = Modifier.testTag("profile-skill-save")) { Text("Save skill") }
                TextButton(onClick = model::revert, enabled = !model.saving, modifier = Modifier.testTag("profile-skill-revert")) { Text("Revert") }
            }
        }
        Button(onClick = { equipmentModel.group(null); model.beginImplantAdd() }, enabled = available && !model.hasDraft && !profile.readonly,
            modifier = Modifier.testTag("profile-implant-add")) { Text("Add / replace implant") }
        if (profile.implants.isEmpty()) Text("No implants on this character.", Modifier.testTag("profile-implants-empty"))
        val pages = ((profile.implants.size + 24) / 25).coerceAtLeast(1)
        if (pages > 1) Row {
            TextButton(onClick = { model.showImplantPage(model.implantPage - 1) }, enabled = model.implantPage > 0, modifier = Modifier.testTag("profile-implants-previous")) { Text("Previous") }
            Text("Page ${model.implantPage + 1} of $pages")
            TextButton(onClick = { model.showImplantPage(model.implantPage + 1) }, enabled = model.implantPage + 1 < pages, modifier = Modifier.testTag("profile-implants-next")) { Text("Next") }
        }
        for (row in profile.displayImplants.drop(model.implantPage * 25).take(25)) key(profile.id, row.implantId) {
            Card(Modifier.fillMaxWidth().testTag("profile-implant-${row.implantId}")) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Slot ${row.slot}: ${row.name}")
                    Text("${profile.name} · ${if (row.active) "Active" else "Inactive"} (read-only state)")
                    TextButton(onClick = { model.removeImplant(context, profile, row) }, enabled = available && !model.hasDraft && !profile.readonly,
                        modifier = Modifier.testTag("profile-implant-remove-${row.implantId}")) { Text("Remove implant") }
                }
            }
        }
    } else {
    OutlinedTextField(value = model.query, onValueChange = { model.query = it }, label = { Text("Search skills") },
        enabled = !model.hasDraft, singleLine = true, modifier = Modifier.fillMaxWidth().testTag("profile-skill-search"))
    val matching = remember(state.skills, model.query) { state.skills.filter { it.name.contains(model.query.trim(), ignoreCase = true) } }
    Text("${matching.size} skills · showing up to 30. Refine the search to find more.")
    for (skill in matching.take(30)) TextButton(onClick = { model.selectSkill(skill.id) }, enabled = available && !model.hasDraft,
        modifier = Modifier.testTag("profile-skill-${skill.id}")) { Text("${skill.name}: ${profile.level(skill.id)?.toString() ?: "Unlearned"}") }
    model.skillId?.let { id ->
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(state.skills.single { it.id == id }.name, Modifier.testTag("profile-skill-selected"))
                Text("Draft level: ${model.draftLevel?.toString() ?: "Unlearned"}", Modifier.testTag("profile-skill-level"))
                TextButton(onClick = { model.editLevel(null) }, enabled = available && !profile.readonly && !model.securityDirty,
                    modifier = Modifier.testTag("profile-level-unlearned")) { Text("Unlearned") }
                for (levels in listOf(0..2, 3..5)) Row {
                    for (level in levels) TextButton(onClick = { model.editLevel(level) }, enabled = available && !profile.readonly && !model.securityDirty,
                        modifier = Modifier.testTag("profile-level-$level")) { Text("$level") }
                }
                if (model.dirty) Text("Unsaved skill change. Save or revert before selecting another skill or profile.", Modifier.testTag("profile-dirty"))
                if (model.conflict) Text("This profile changed. Reload and revert the draft before editing again.", color = MaterialTheme.colorScheme.error)
                Row {
                    Button(onClick = { model.save(context) }, enabled = available && model.dirty && !model.conflict,
                        modifier = Modifier.testTag("profile-skill-save")) { Text("Save skill") }
                    TextButton(onClick = { model.revert() }, enabled = available && model.dirty,
                        modifier = Modifier.testTag("profile-skill-revert")) { Text("Revert") }
                }
            }
        }
    }
    }
    if (!profile.readonly) {
        Text("Replacement if this profile is deleted:")
        for (replacement in state.profiles.filter { it.id != profile.id }) TextButton(onClick = { model.replacementId = replacement.id }, enabled = available && !model.hasDraft,
            modifier = Modifier.testTag("profile-replacement-${replacement.id}")) { Text((if (model.replacementId == replacement.id) "✓ " else "") + replacement.name) }
        TextButton(onClick = model::requestDelete, enabled = available && !model.hasDraft && state.profiles.any { it.id == model.replacementId && it.id != profile.id },
            modifier = Modifier.testTag("profile-delete")) { Text("Delete profile…") }
    }
    model.deleteConfirmation?.let { pending ->
        AlertDialog(onDismissRequest = model::dismissDelete, title = { Text("Delete ${pending.profile.name}?") },
            text = { Column {
                Text("${pending.assignedCount} assigned fit(s) will use ${pending.replacement.name}. Both retained fit-local collections and each fit's source selection stay unchanged. This change can be undone during this session.")
                if (!model.deleteCurrent) Text("This profile or its impact changed. Cancel and review again.", Modifier.testTag("profile-delete-stale"))
            } },
            confirmButton = { TextButton(onClick = { model.delete(context) }, enabled = model.deleteCurrent, modifier = Modifier.testTag("profile-delete-confirm")) { Text("Delete and replace") } },
            dismissButton = { TextButton(onClick = model::dismissDelete, modifier = Modifier.testTag("profile-delete-cancel")) { Text("Cancel") } })
    }
    if (confirmLeave) AlertDialog(onDismissRequest = { confirmLeave = false }, title = { Text("Keep unsaved profile change?") },
        text = { Text("Your draft will stay here while the app remains open.") },
        confirmButton = { TextButton(onClick = { confirmLeave = false; model.close(); onBack() }) { Text("Keep draft and go back") } },
        dismissButton = { TextButton(onClick = { confirmLeave = false }) { Text("Stay") } })
}

@Composable
private fun ProfileSecuritySection(model: OfflineProfilesModel, profile: OfflineProfile, assigned: Int) {
    val context = LocalContext.current
    Text("Saved character security: ${profile.secStatus}", Modifier.testTag("profile-security-saved"))
    Text("Affects Character-inheriting fits among $assigned assigned fit(s), plus their linked dependents. Explicit pilot overrides stay unchanged.")
    if (model.dirty) Text("Save or revert your skill draft in Skills before starting a security draft.", Modifier.testTag("profile-security-skill-draft"))
    OutlinedTextField(model.securityText, model::editSecurity, label = { Text("Character security (-10 to 5)") },
        singleLine = true, enabled = model.available && !profile.readonly && !model.dirty && !model.securityConflict,
        isError = model.securityValue == null, modifier = Modifier.fillMaxWidth().testTag("profile-security-input"))
    if (model.securityConflict) Text("This profile changed. Your draft is kept; review the saved value and revert before editing.", Modifier.testTag("profile-security-conflict"))
    if (model.securityDirty) Text("Unsaved character security.", Modifier.testTag("profile-security-dirty"))
    Row {
        Button(onClick = { model.saveSecurity(context) }, enabled = model.available && !profile.readonly && !model.dirty &&
            model.securityDirty && !model.securityConflict && model.securityValue != null, modifier = Modifier.testTag("profile-security-save")) { Text("Save") }
        TextButton(onClick = { model.saveSecurity(context, true) }, enabled = model.available && !profile.readonly && !model.dirty &&
            !model.securityConflict && model.securityValue != null && model.name.isNotBlank(), modifier = Modifier.testTag("profile-security-save-as")) { Text("Save As") }
        TextButton(onClick = model::revertSecurity, enabled = !model.saving && !model.loading && model.securityDirty,
            modifier = Modifier.testTag("profile-security-revert")) { Text("Revert") }
    }
    Text("Save As uses Profile name above and copies the complete character with this security value. It does not assign the new profile or change its source.")
}

/** Uses the same offline Equipment search, but never any fit action or local occupant. */
@Composable
private fun CharacterImplantPicker(model: OfflineProfilesModel, equipment: EquipmentModel) {
    val context = LocalContext.current
    val choice = model.implantChoice ?: return
    var catalogue by remember(choice.context.sessionId, choice.context.datasetSha256) { mutableStateOf<CharacterImplantCatalog?>(null) }
    var loadError by remember(choice.context.sessionId, choice.context.datasetSha256) { mutableStateOf<String?>(null) }
    val owner = remember(choice.context.sessionId, choice.context.datasetSha256) { booleanArrayOf(true) }
    DisposableEffect(owner) { onDispose { owner[0] = false } }
    LaunchedEffect(owner) {
        equipment.load(context)
        EngineRuntime.characterImplantCatalog(context).whenCompleteAsync({ value, failure ->
            if (owner[0] && EngineRuntime.offlineFeatures.value?.context?.sessionId == choice.context.sessionId) {
                if (failure != null) loadError = "Implant metadata could not be verified. Close and reopen this picker to retry."
                else catalogue = value
            }
        }, ContextCompat.getMainExecutor(context))
    }
    Text("Add implants to ${choice.profile.name}", style = MaterialTheme.typography.titleLarge, modifier = Modifier.testTag("profile-implant-picker"))
    Text("Changes affect ${choice.assignedCount} assigned fit(s). The selected character does not follow fit navigation.")
    TextButton(onClick = model::closeImplantPicker, enabled = !model.saving, modifier = Modifier.testTag("profile-implant-picker-close")) { Text("Cancel / back to character") }
    val current = model.available && !model.hasDraft && model.state?.context == choice.context && model.selectedProfile == choice.profile
    if (!current && !model.saving) Text("The character or session changed. Close the picker and review its current implants.", Modifier.testTag("profile-implant-picker-stale"))
    loadError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    equipment.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    OutlinedTextField(equipment.query, { equipment.query = it }, label = { Text("Search implants") }, enabled = current && !equipment.busy,
        singleLine = true, modifier = Modifier.fillMaxWidth().testTag("profile-implant-search"))
    Text("Equipment search supports words, * or ? wildcards, common abbreviations, and re: regular expressions.")
    Button(onClick = { equipment.search(context) }, enabled = current && !equipment.busy, modifier = Modifier.testTag("profile-implant-search-submit")) { Text("Search") }
    if (equipment.busy || catalogue == null && loadError == null) Text("Loading implant choices…")
    val ids = if (equipment.searched != null) equipment.results.toSet() else null
    val metadata = catalogue
    val matches = equipment.catalog?.items.orEmpty().filter { it.searchable && (ids == null || it.id in ids) }
        .mapNotNull { item -> metadata?.itemById?.get(item.id)?.takeIf { it.name == item.name } }.sortedBy { it.name }
    val pages = ((matches.size + 24) / 25).coerceAtLeast(1)
    val page = equipment.page.coerceAtMost(pages - 1)
    Text("${matches.size} genuine implants · page ${page + 1} of $pages")
    if (pages > 1) Row {
        TextButton(onClick = { equipment.page = page - 1 }, enabled = current && page > 0) { Text("Previous choices") }
        TextButton(onClick = { equipment.page = page + 1 }, enabled = current && page + 1 < pages) { Text("Next choices") }
    }
    for (item in matches.drop(page * 25).take(25)) TextButton(onClick = { model.chooseImplant(context, item) }, enabled = current,
        modifier = Modifier.testTag("profile-implant-choice-${item.itemId}")) { Text("Slot ${item.slot}: ${item.name}") }
    model.implantReplacement?.let { pending ->
        AlertDialog(onDismissRequest = model::cancelImplantReplacement, title = { Text("Replace character implant in slot ${pending.item.slot}?") },
            text = { Column {
                Text("${pending.choice.profile.name}: replace ${pending.occupant.name} with ${pending.item.name}.")
                Text("${pending.choice.assignedCount} assigned fit(s) are affected. The replacement starts active, including re-adding the same item.")
                if (!model.implantReplacementCurrent) Text("The character changed. Cancel and review the current slot.", Modifier.testTag("profile-implant-replace-stale"))
            } },
            confirmButton = { TextButton(onClick = { model.confirmImplantReplacement(context) }, enabled = model.implantReplacementCurrent,
                modifier = Modifier.testTag("profile-implant-replace-confirm")) { Text("Replace implant") } },
            dismissButton = { TextButton(onClick = model::cancelImplantReplacement, modifier = Modifier.testTag("profile-implant-replace-cancel")) { Text("Cancel") } })
    }
}
