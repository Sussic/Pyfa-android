package io.github.sussic.pyfa

import android.os.Bundle
import androidx.lifecycle.ViewModelProvider
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.BackHandler
import androidx.activity.compose.ReportDrawnWhen
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.text.NumberFormat
import kotlinx.coroutines.Dispatchers

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        EngineRuntime.start(applicationContext)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
        )
        setContent {
            // Keep worker emissions on the Android UI queue, including when a
            // test recomposer uses an unconfined effect dispatcher.
            val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
            ReportDrawnWhen { engine is EngineState.Ready || engine is EngineState.Empty }
            PyfaApp(ViewModelProvider(this)[FitLibraryModel::class.java],
                ViewModelProvider(this)[EquipmentModel::class.java], ViewModelProvider(this)[ModuleEditorModel::class.java],
                ViewModelProvider(this)[ChargeEditorModel::class.java], ViewModelProvider(this)[VariationEditorModel::class.java],
                ViewModelProvider(this)[RackEditorModel::class.java], ViewModelProvider(this)[BulkChargeEditorModel::class.java],
                ViewModelProvider(this)[BulkStateEditorModel::class.java],
                ViewModelProvider(this)[ModeEditorModel::class.java],
                ViewModelProvider(this)[SubsystemEditorModel::class.java],
                ViewModelProvider(this)[StructureServiceEditorModel::class.java],
                ViewModelProvider(this)[CargoEditorModel::class.java], ViewModelProvider(this)[DroneEditorModel::class.java],
                ViewModelProvider(this)[NotesModel::class.java], ViewModelProvider(this)[EditHistoryModel::class.java],
                ViewModelProvider(this)[ResourcesModel::class.java], ViewModelProvider(this)[CapacitorModel::class.java], ViewModelProvider(this)[DefenseModel::class.java], ViewModelProvider(this)[TankModel::class.java], ViewModelProvider(this)[OutputModel::class.java], ViewModelProvider(this)[TargetingModel::class.java], ViewModelProvider(this)[InspectionModel::class.java],
                ViewModelProvider(this)[OfflineProfilesModel::class.java],
                ViewModelProvider(this)[OfflineTargetProfilesModel::class.java],
                ViewModelProvider(this)[OfflineDamagePatternsModel::class.java],
                ViewModelProvider(this)[OfflineImplantSetsModel::class.java],
                ViewModelProvider(this)[OfflineImportModel::class.java],
                ViewModelProvider(this)[OfflineCapacitorModel::class.java],
                ViewModelProvider(this)[OfflineLockTimeModel::class.java],
                ViewModelProvider(this)[OfflineMobilityModel::class.java],
                ViewModelProvider(this)[OfflineRemoteRepairModel::class.java],
                ViewModelProvider(this)[OfflineEwarModel::class.java],
                ViewModelProvider(this)[OfflineShieldRegenerationModel::class.java],
                ViewModelProvider(this)[OfflineExportModel::class.java],
                ViewModelProvider(this)[FighterEditorModel::class.java],
                ViewModelProvider(this)[BoosterEditorModel::class.java],
                ViewModelProvider(this)[ModuleSpoolModel::class.java],
                ViewModelProvider(this)[ModuleRahModel::class.java],
                ViewModelProvider(this)[ImplantEditorModel::class.java],
                ViewModelProvider(this)[PilotSecurityModel::class.java], ViewModelProvider(this)[SystemSecurityModel::class.java], ViewModelProvider(this)[ProjectedFitModel::class.java], ViewModelProvider(this)[CommandFitModel::class.java], ViewModelProvider(this)[ProjectedModuleModel::class.java], ViewModelProvider(this)[ProjectedDroneModel::class.java], ViewModelProvider(this)[ProjectedFighterModel::class.java], ViewModelProvider(this)[MutationEditorModel::class.java])
        }
    }

    override fun reportFullyDrawn() {
        super.reportFullyDrawn()
        EngineRuntime.recordStartupDraw(applicationContext)
    }

    override fun onStop() {
        ViewModelProvider(this)[NotesModel::class.java].flush(applicationContext)
        super.onStop()
    }
}

@Composable
private fun PyfaApp(libraryModel: FitLibraryModel, equipmentModel: EquipmentModel, moduleModel: ModuleEditorModel, chargeModel: ChargeEditorModel, variationModel: VariationEditorModel, rackModel: RackEditorModel, bulkModel: BulkChargeEditorModel, bulkStateModel: BulkStateEditorModel, modeModel: ModeEditorModel, subsystemModel: SubsystemEditorModel, structureModel: StructureServiceEditorModel, cargoModel: CargoEditorModel, droneModel: DroneEditorModel, notesModel: NotesModel, historyModel: EditHistoryModel, resourcesModel: ResourcesModel, capacitorModel: CapacitorModel, defenseModel: DefenseModel, tankModel: TankModel, outputModel: OutputModel, targetingModel: TargetingModel, inspectionModel: InspectionModel, profilesModel: OfflineProfilesModel, targetProfilesModel: OfflineTargetProfilesModel, damagePatternsModel: OfflineDamagePatternsModel, implantSetsModel: OfflineImplantSetsModel, importModel: OfflineImportModel, capGraphModel: OfflineCapacitorModel, lockGraphModel: OfflineLockTimeModel, mobilityGraphModel: OfflineMobilityModel, remoteRepairGraphModel: OfflineRemoteRepairModel, ewarGraphModel: OfflineEwarModel, shieldRegenerationGraphModel: OfflineShieldRegenerationModel, exportModel: OfflineExportModel, fighterModel: FighterEditorModel, boosterModel: BoosterEditorModel, spoolModel: ModuleSpoolModel, rahModel: ModuleRahModel, implantModel: ImplantEditorModel, pilotSecurityModel: PilotSecurityModel, systemSecurityModel: SystemSecurityModel, projectedFitModel: ProjectedFitModel, commandFitModel: CommandFitModel, projectedModuleModel: ProjectedModuleModel, projectedDroneModel: ProjectedDroneModel, projectedFighterModel: ProjectedFighterModel, mutationModel: MutationEditorModel) {
    var showMutations by rememberSaveable { mutableStateOf(false) }
    if (showMutations) MutationEditorDialog(mutationModel, onClose = { showMutations = false })
    var showProjectedFighters by rememberSaveable { mutableStateOf(false) }
    var showProjectedDrones by rememberSaveable { mutableStateOf(false) }
    var showProjectedModules by rememberSaveable { mutableStateOf(false) }
    var showCommands by rememberSaveable { mutableStateOf(false) }
    var showProjections by rememberSaveable { mutableStateOf(false) }
    var showExport by rememberSaveable { mutableStateOf(false) }
    var showRemoteRepairGraph by rememberSaveable { mutableStateOf(false) }
    var showEwarGraph by rememberSaveable { mutableStateOf(false) }
    var showShieldRegenerationGraph by rememberSaveable { mutableStateOf(false) }
    var showMobilityGraph by rememberSaveable { mutableStateOf(false) }
    var showLockGraph by rememberSaveable { mutableStateOf(false) }
    var showCapGraph by rememberSaveable { mutableStateOf(false) }
    var showImport by rememberSaveable { mutableStateOf(false) }
    var showProfiles by rememberSaveable { mutableStateOf(false) }
    var showTargetProfiles by rememberSaveable { mutableStateOf(false) }
    var showDamagePatterns by rememberSaveable { mutableStateOf(false) }
    var showImplantSets by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(profilesModel.hasDraft, profilesModel.saving) {
        implantSetsModel.preserveSkillDraft(profilesModel.hasDraft || profilesModel.saving)
    }
    val featureEpoch by EngineRuntime.featureEpoch.collectAsState(context = Dispatchers.Main)
    val context = LocalContext.current
    LaunchedEffect(featureEpoch) {
        if (featureEpoch > 0) historyModel.load(context, (EngineRuntime.state.value as? EngineState.Ready)?.fit, retry = true)
    }
    var showAbout by rememberSaveable { mutableStateOf(false) }
    var showEquipment by rememberSaveable { mutableStateOf(false) }
    var showModules by rememberSaveable { mutableStateOf(false) }
    var showCharges by rememberSaveable { mutableStateOf(false) }
    var showVariations by rememberSaveable { mutableStateOf(false) }
    var showRah by rememberSaveable { mutableStateOf(false) }
    var showSpool by rememberSaveable { mutableStateOf(false) }
    var showRack by rememberSaveable { mutableStateOf(false) }
    var showBulk by rememberSaveable { mutableStateOf(false) }
    var showBulkStates by rememberSaveable { mutableStateOf(false) }
    var showModes by rememberSaveable { mutableStateOf(false) }
    var showSubsystems by rememberSaveable { mutableStateOf(false) }
    var showServices by rememberSaveable { mutableStateOf(false) }
    var showPilotSecurity by rememberSaveable { mutableStateOf(false) }
    var showSystemSecurity by rememberSaveable { mutableStateOf(false) }
    var showImplants by rememberSaveable { mutableStateOf(false) }
    var showBoosters by rememberSaveable { mutableStateOf(false) }
    var showFighters by rememberSaveable { mutableStateOf(false) }
    var showDrones by rememberSaveable { mutableStateOf(false) }
    var showCargo by rememberSaveable { mutableStateOf(false) }
    var showTransfers by rememberSaveable { mutableStateOf(false) }
    var showNotes by rememberSaveable { mutableStateOf(false) }
    var showResources by rememberSaveable { mutableStateOf(false) }
    var showDefenses by rememberSaveable { mutableStateOf(false) }
    var showTank by rememberSaveable { mutableStateOf(false) }
    var showOutput by rememberSaveable { mutableStateOf(false) }
    var showTargeting by rememberSaveable { mutableStateOf(false) }
    var showInspection by rememberSaveable { mutableStateOf(false) }
    var inspectionItemId by rememberSaveable { mutableStateOf<Int?>(null) }
    var showCapacitor by rememberSaveable { mutableStateOf(false) }
    fun returnToProjections() {
        showProjectedFighters = false; showProjectedDrones = false; showProjectedModules = false
        showCommands = false
        showExport = false
        showRemoteRepairGraph = false
        showEwarGraph = false
        showShieldRegenerationGraph = false
        showMobilityGraph = false
        showLockGraph = false
        showCapGraph = false
        showImport = false
        showProfiles = false
        showTargetProfiles = false
        showDamagePatterns = false
        showImplantSets = false
        showAbout = false
        showEquipment = false
        showModules = false
        showCharges = false
        showVariations = false
        showRah = false
        showSpool = false
        showRack = false
        showBulk = false
        showBulkStates = false
        showModes = false
        showSubsystems = false
        showServices = false
        showPilotSecurity = false; pilotSecurityModel.close()
        showSystemSecurity = false
        showImplants = false
        showBoosters = false
        showFighters = false
        showDrones = false
        showCargo = false
        showTransfers = false
        showNotes = false
        showResources = false
        showDefenses = false
        showTank = false
        showOutput = false
        showTargeting = false
        showInspection = false
        showCapacitor = false
        showProjections = true
    }
    fun returnToCommands() {
        returnToProjections(); showProjections = false; showCommands = true
    }
    fun projectedFighterSaved() {
        returnToProjections(); showProjections = false; showProjectedFighters = true
    }
    fun projectedDroneSaved() {
        returnToProjections(); showProjections = false; showProjectedDrones = true
    }
    fun projectedModuleSaved() {
        returnToProjections(); showProjections = false; showProjectedModules = true
    }
    fun variations(position: Int?) {
        showProjectedFighters = false; showProjectedDrones = false; showProjectedModules = false
        variationModel.open((EngineRuntime.state.value as? EngineState.Ready)?.fit?.id, position)
        showVariations = true
    }
    fun charges(position: Int?) {
        showProjectedFighters = false; showProjectedDrones = false; showProjectedModules = false
        chargeModel.open((EngineRuntime.state.value as? EngineState.Ready)?.fit?.id, position)
        showCharges = true
    }
    fun implantsSaved() {
        showProjectedFighters = false; showProjectedDrones = false; showProjectedModules = false
        showEquipment = false; showCargo = false; showDrones = false; showFighters = false; showModules = false; showBoosters = false; showImplants = true
    }
    fun boostersSaved() {
        showProjectedFighters = false; showProjectedDrones = false; showProjectedModules = false
        showEquipment = false; showCargo = false; showDrones = false; showFighters = false; showModules = false; showImplants = false; showBoosters = true
    }
    BackHandler(enabled = showAbout) { showAbout = false }
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Color(0xFFACD8B3),
            onPrimary = Color(0xFF153820),
            background = Color(0xFF111713),
            surface = Color(0xFF111713),
            surfaceVariant = Color(0xFF29352C),
            onBackground = Color(0xFFE0E6DD),
            onSurface = Color(0xFFE0E6DD),
        ),
    ) {
        ImplantReplacementDialog(implantModel, onSaved = ::implantsSaved)
        BoosterReplacementDialog(boosterModel, onSaved = ::boostersSaved)
        Scaffold { insets ->
            Box(Modifier.fillMaxSize().padding(insets).consumeWindowInsets(insets)
                .imePadding().clipToBounds().testTag("app-content-viewport"),
                contentAlignment = Alignment.TopCenter) {
                key(showPilotSecurity, showImplantSets, showDamagePatterns, showTargetProfiles, showEwarGraph, showProjectedFighters, showProjectedDrones, showProjectedModules, showCommands, showProjections, showExport, showShieldRegenerationGraph, showRemoteRepairGraph, showMobilityGraph, showLockGraph, showCapGraph, showImport, showProfiles, showAbout, showEquipment, showModules, showCharges, showVariations, showRah, showSpool, showRack, showBulk, showBulkStates, showModes, showSubsystems, showServices, showSystemSecurity, showCargo, showDrones, showFighters, showImplants, showBoosters, showTransfers, showNotes, showResources, showCapacitor, showDefenses, showTank, showOutput, showTargeting, showInspection) {
                    Column(
                        Modifier.widthIn(max = 600.dp).fillMaxWidth()
                            .verticalScroll(rememberScrollState()).padding(24.dp),
                        verticalArrangement = Arrangement.spacedBy(if (showProjectedFighters || showProjectedDrones || showProjectedModules || showCommands || showProjections || showEquipment || showModules || showCharges || showVariations || showRah || showSpool || showRack || showBulk || showBulkStates || showModes || showSubsystems || showServices || showSystemSecurity || showCargo || showDrones || showFighters || showImplants || showBoosters) 8.dp else 24.dp),
                    ) {
                        Text(
                            stringResource(R.string.brand),
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        if (!showCommands) CommandFitReturn(commandFitModel, onReturned = ::returnToCommands)
                        if (!showProjections) ProjectedFitReturn(projectedFitModel, onReturned = ::returnToProjections)
                        if (!showPilotSecurity && !showAbout && !showNotes && !showProfiles && !showTargetProfiles && !showDamagePatterns && !showImplantSets && !showImport && !showExport) EditHistoryControls(historyModel)
                        if (showPilotSecurity) {
                            PilotSecurityEditor(pilotSecurityModel, onBack = { pilotSecurityModel.close(); showPilotSecurity = false })
                        } else if (showImplantSets) {
                            OfflineImplantSetsView(implantSetsModel, onBack = { showImplantSets = false })
                        } else if (showDamagePatterns) {
                            OfflineDamagePatternsView(damagePatternsModel, onBack = { damagePatternsModel.close(); showDamagePatterns = false })
                        } else if (showTargetProfiles) {
                            OfflineTargetProfilesView(targetProfilesModel, onBack = { showTargetProfiles = false })
                        } else if (showCommands) {
                            CommandFitEditor(commandFitModel, onBack = { showCommands = false }, onSource = { showCommands = false })
                        } else if (showProjections) {
                            ProjectedFitEditor(projectedFitModel, onBack = { showProjections = false }, onSource = { showProjections = false })
                        } else if (showExport) {
                            OfflineExportView(exportModel, onBack = { showExport = false })
                        } else if (showShieldRegenerationGraph) {
                            OfflineShieldRegenerationView(shieldRegenerationGraphModel, onBack = { showShieldRegenerationGraph = false })
                        } else if (showEwarGraph) {
                            OfflineEwarView(ewarGraphModel, onBack = { showEwarGraph = false })
                        } else if (showRemoteRepairGraph) {
                            OfflineRemoteRepairView(remoteRepairGraphModel, onBack = { showRemoteRepairGraph = false })
                        } else if (showMobilityGraph) {
                            OfflineMobilityView(mobilityGraphModel, onBack = { showMobilityGraph = false })
                        } else if (showLockGraph) {
                            OfflineLockTimeView(lockGraphModel, onBack = { showLockGraph = false })
                        } else if (showCapGraph) {
                            OfflineCapacitorView(capGraphModel, onBack = { showCapGraph = false })
                        } else if (showImport) {
                            OfflineImportView(importModel, onBack = { showImport = false })
                        } else if (showProfiles) {
                            TextButton(onClick = {
                                implantSetsModel.preserveSkillDraft(profilesModel.hasDraft || profilesModel.saving)
                                profilesModel.profileId?.let { if (implantSetsModel.openForProfile(it)) showImplantSets = true }
                            }, enabled = profilesModel.available && !profilesModel.hasDraft && !implantSetsModel.dirty && !implantSetsModel.saving,
                                modifier = Modifier.testTag("profile-open-implant-sets")) { Text("Browse / apply implant sets to this character") }
                            OfflineProfilesView(profilesModel, equipmentModel, onBack = { showProfiles = false })
                        } else if (showNotes) {
                            NotesEditor(notesModel, onBack = { showNotes = false })
                        } else if (showInspection) {
                            InspectionView(inspectionModel, inspectionItemId, onBack = { showInspection = false },
                                onInspectBase = { inspectionItemId = it })
                        } else if (showTargeting) {
                            TargetingView(targetingModel, onBack = { showTargeting = false })
                        } else if (showOutput) {
                            OutputView(outputModel, onBack = { showOutput = false }, onNamedProfiles = { showTargetProfiles = true })
                        } else if (showTank) {
                            TankView(tankModel, onBack = { showTank = false })
                        } else if (showDefenses) {
                            DefenseView(defenseModel, damagePatternsModel, onBack = { showDefenses = false }, onNamedPatterns = { showDamagePatterns = true })
                        } else if (showCapacitor) {
                            CapacitorView(capacitorModel, onBack = { showCapacitor = false })
                        } else if (showResources) {
                            ResourcesView(resourcesModel, onBack = { showResources = false })
                        } else if (showEquipment) {
                            EquipmentBrowser(equipmentModel, moduleModel, cargoModel, damagePatternsModel = damagePatternsModel, projectedModuleModel = projectedModuleModel, onProjectedModules = ::projectedModuleSaved,
                                projectedDroneModel = projectedDroneModel, onProjectedDrones = ::projectedDroneSaved,
                                projectedFighterModel = projectedFighterModel, onProjectedFighters = ::projectedFighterSaved, boosterModel = boosterModel, onBoosters = ::boostersSaved, implantModel = implantModel, onImplants = ::implantsSaved, fighterModel = fighterModel,
                                onFighters = { showProjectedFighters = false; showProjectedDrones = false; showProjectedModules = false; showEquipment = false; showCargo = false; showDrones = false; showModules = false; showBoosters = false; showImplants = false; showFighters = true },
                                droneModel = droneModel, onDrones = { showProjectedFighters = false; showProjectedDrones = false; showProjectedModules = false; showEquipment = false; showCargo = false; showFighters = false; showBoosters = false; showImplants = false; showDrones = true }, onBack = { showEquipment = false },
                                onInspect = { inspectionItemId = it; showInspection = true },
                                onViewFit = { showProjectedFighters = false; showProjectedDrones = false; showProjectedModules = false; showEquipment = false; showCargo = false; showDrones = false; showFighters = false; showBoosters = false; showImplants = false; showModules = true },
                                onCharges = { showEquipment = false; showCargo = false; charges(null) }, onCargo = {
                                    showProjectedFighters = false; showProjectedDrones = false; showProjectedModules = false; showEquipment = false; showCargo = true
                                })
                        } else if (showProjectedFighters) {
                            ProjectedFighterEditor(projectedFighterModel, onBack = { showProjectedFighters = false },
                                onBrowse = { moduleModel.replacePosition = null; showEquipment = true },
                                onInspectBase = { inspectionItemId = it; showInspection = true })
                        } else if (showProjectedDrones) {
                            ProjectedDroneEditor(projectedDroneModel, onBack = { showProjectedDrones = false },
                                onBrowse = { moduleModel.replacePosition = null; showEquipment = true },
                                onInspectBase = { inspectionItemId = it; showInspection = true })
                        } else if (showProjectedModules) {
                            ProjectedModuleEditor(projectedModuleModel, onBack = { showProjectedFighters = false; showProjectedDrones = false; showProjectedModules = false },
                                onBrowse = { moduleModel.replacePosition = null; showEquipment = true },
                                onInspectBase = { inspectionItemId = it; showInspection = true })
                        } else if (showTransfers) {
                            CargoTransferEditor(cargoModel.transfers, onBack = { showTransfers = false })
                        } else if (showCargo) {
                            CargoEditor(cargoModel, onBrowse = { showEquipment = true }, onBack = { showCargo = false },
                                onTransfers = { cargoModel.transfers.open(); showTransfers = true })
                        } else if (showSystemSecurity) {
                            SystemSecurityEditor(systemSecurityModel, onBack = { showSystemSecurity = false })
                        } else if (showServices) {
                            StructureServiceEditor(structureModel, onBack = { showServices = false },
                                onSystemSecurity = { showSystemSecurity = true })
                        } else if (showSubsystems) {
                            SubsystemEditor(subsystemModel, onBack = { showSubsystems = false })
                        } else if (showModes) {
                            ModeEditor(modeModel, onBack = { showModes = false })
                        } else if (showBulkStates) {
                            BulkStateEditor(bulkStateModel, onBack = { showBulkStates = false })
                        } else if (showBulk) {
                            BulkChargeEditor(bulkModel, onBack = { showBulk = false })
                        } else if (showRah) {
                            ModuleRahEditor(rahModel, onBack = { rahModel.close(); showRah = false })
                        } else if (showSpool) {
                            ModuleSpoolEditor(spoolModel, onBack = { showSpool = false })
                        } else if (showRack) {
                            RackEditor(rackModel, onBack = { showRack = false })
                        } else if (showVariations) {
                            VariationEditor(variationModel, onBack = { showVariations = false })
                        } else if (showCharges) {
                            ChargeEditor(chargeModel, onBack = { showCharges = false })
                        } else if (showImplants) {
                            TextButton(onClick = { if (implantSetsModel.openForFit()) showImplantSets = true },
                                enabled = !implantSetsModel.dirty && !implantSetsModel.saving,
                                modifier = Modifier.testTag("implants-open-sets")) { Text("Named sets / save current applied implants") }
                            ImplantEditor(implantModel, onBrowse = { showEquipment = true }, onBack = { showImplants = false },
                                onCharacter = { id -> profilesModel.openImplants(id); showProfiles = true },
                                onInspect = { inspectionItemId = null; showInspection = true }, onVariations = { position ->
                                    variationModel.open((EngineRuntime.state.value as? EngineState.Ready)?.fit?.id, null)
                                    variationModel.context = VariationContext.IMPLANT; variationModel.position = position
                                    showVariations = true
                                })
                        } else if (showBoosters) {
                            BoosterEditor(boosterModel, onBrowse = { showEquipment = true }, onBack = { showBoosters = false },
                                onInspect = { inspectionItemId = null; showInspection = true })
                        } else if (showFighters) {
                            FighterEditor(fighterModel, onBrowse = { showEquipment = true }, onBack = { showFighters = false },
                                onInspect = { inspectionItemId = null; showInspection = true })
                        } else if (showDrones) {
                            DroneEditor(droneModel, onBrowse = { showEquipment = true }, onBack = { showDrones = false },
                                onVariations = { position ->
                                    variationModel.open((EngineRuntime.state.value as? EngineState.Ready)?.fit?.id, null)
                                    variationModel.context = VariationContext.DRONE; variationModel.position = position
                                    showVariations = true
                                }, onInspect = { inspectionItemId = null; showInspection = true })
                        } else if (showModules) {
                            ModuleEditor(moduleModel, onBrowse = { showEquipment = true }, onBack = { showModules = false },
                                onCharges = { charges(it) }, onVariations = { variations(it) }, onSpool = { showSpool = true }, onRah = { showRah = true }, onBulk = {
                                    bulkModel.open(); showBulk = true
                                }, onBulkStates = {
                                    bulkStateModel.open(); showBulkStates = true
                                }, onArrange = {
                                    rackModel.open((EngineRuntime.state.value as? EngineState.Ready)?.fit?.id, null)
                                    showRack = true
                                })
                        } else if (showAbout) {
                            AboutBuild(onBack = { showAbout = false })
                        } else {
                            TextButton(onClick = { showMutations = true }, modifier = Modifier.testTag("mutation-open")) { Text("Exact mutation rolls") }
                            Home(libraryModel, onPilotSecurity = { showPilotSecurity = true }, onAbout = { showAbout = true }, onProfiles = { showProfiles = true }, onTargetProfiles = { showTargetProfiles = true }, onDamagePatterns = { showDamagePatterns = true }, onImplantSets = { showImplantSets = true }, onImport = { showImport = true }, onCapGraph = { showCapGraph = true }, onLockGraph = { showLockGraph = true }, onMobilityGraph = { showMobilityGraph = true }, onRemoteRepairGraph = { showRemoteRepairGraph = true }, onEwarGraph = { showEwarGraph = true }, onShieldRegenerationGraph = { showShieldRegenerationGraph = true }, onExport = { showExport = true },
                                onEquipment = { moduleModel.replacePosition = null; showEquipment = true },
                                onModules = { showModules = true }, onVariations = { variations(null) },
                                onModes = { modeModel.open(); showModes = true },
                                onSubsystems = { subsystemModel.open(); showSubsystems = true },
                                onServices = { structureModel.open(); showServices = true },
                                onCommands = { showCommands = true }, onProjections = { showProjections = true }, onProjectedModules = { showProjectedModules = true }, onProjectedDrones = { showProjectedDrones = true }, onProjectedFighters = { showProjectedFighters = true },
                                onCargo = { cargoModel.open(); showCargo = true },
                                onDrones = { droneModel.open(); showDrones = true }, onFighters = { showFighters = true }, onBoosters = { showBoosters = true }, onImplants = { showImplants = true },
                                onNotes = { showNotes = true }, onResources = { showResources = true }, onCapacitor = { showCapacitor = true }, onDefenses = { showDefenses = true }, onTank = { showTank = true }, onOutput = { showOutput = true }, onTargeting = { showTargeting = true },
                                onInspect = { inspectionItemId = null; showInspection = true })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Home(libraryModel: FitLibraryModel, onPilotSecurity: () -> Unit, onAbout: () -> Unit, onProfiles: () -> Unit, onTargetProfiles: () -> Unit, onDamagePatterns: () -> Unit, onImplantSets: () -> Unit, onImport: () -> Unit, onCapGraph: () -> Unit, onLockGraph: () -> Unit, onMobilityGraph: () -> Unit, onRemoteRepairGraph: () -> Unit, onEwarGraph: () -> Unit, onShieldRegenerationGraph: () -> Unit, onExport: () -> Unit, onEquipment: () -> Unit, onModules: () -> Unit, onVariations: () -> Unit, onModes: () -> Unit, onSubsystems: () -> Unit, onServices: () -> Unit, onProjections: () -> Unit, onProjectedModules: () -> Unit, onProjectedDrones: () -> Unit, onProjectedFighters: () -> Unit, onCommands: () -> Unit, onCargo: () -> Unit, onDrones: () -> Unit, onFighters: () -> Unit, onBoosters: () -> Unit, onImplants: () -> Unit, onNotes: () -> Unit, onResources: () -> Unit, onCapacitor: () -> Unit, onDefenses: () -> Unit, onTank: () -> Unit, onOutput: () -> Unit, onTargeting: () -> Unit, onInspect: () -> Unit) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val offlineFeatures by EngineRuntime.offlineFeatures.collectAsState(context = Dispatchers.Main)
    var expanded by rememberSaveable { mutableStateOf(false) }
    val selectedTitle = remember { BringIntoViewRequester() }
    LaunchedEffect(libraryModel.fitJump.value) {
        if (libraryModel.fitJump.value > 0) selectedTitle.bringIntoView()
    }
    Text(
        stringResource(R.string.home_title),
        style = MaterialTheme.typography.headlineLarge,
        fontWeight = FontWeight.SemiBold,
    )
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text(
                stringResource(R.string.milestone),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(stringResource(R.string.status_title), style = MaterialTheme.typography.titleLarge)
            Text(stringResource(R.string.status_body), style = MaterialTheme.typography.bodyLarge)
        }
    }
    Button(onClick = onAbout, contentPadding = PaddingValues(horizontal = 24.dp, vertical = 16.dp)) {
        Text(stringResource(R.string.about_button))
    }
    if (engine is EngineState.Ready || engine is EngineState.Empty) {
        Button(onClick = onEquipment, modifier = Modifier.testTag("equipment-open")) { Text("Browse equipment") }
        if (offlineFeatures != null) Button(onClick = onTargetProfiles, modifier = Modifier.testTag("targets-open")) { Text("Named target profiles") }
        if (offlineFeatures != null) Button(onClick = onDamagePatterns, modifier = Modifier.testTag("damage-patterns-open")) { Text("Named incoming damage patterns") }
        if (offlineFeatures != null) Button(onClick = onImplantSets, modifier = Modifier.testTag("implant-sets-open")) { Text("Named implant sets") }
        if (offlineFeatures != null) Button(onClick = onProfiles, modifier = Modifier.testTag("profiles-open")) { Text("Offline character profiles") }
        if (offlineFeatures != null) Button(onClick = onImport, modifier = Modifier.testTag("eft-open")) { Text("Import EFT fits") }
        if (offlineFeatures != null) Button(onClick = onCapGraph, modifier = Modifier.testTag("cap-graph-open")) { Text("Capacitor comparison") }
        if (offlineFeatures != null) Button(onClick = onLockGraph, modifier = Modifier.testTag("lock-graph-open")) { Text("Lock-time comparison") }
        if (offlineFeatures != null) Button(onClick = onMobilityGraph, modifier = Modifier.testTag("mobility-graph-open")) { Text("Mobility comparison") }
        if (offlineFeatures != null) Button(onClick = onEwarGraph, modifier = Modifier.testTag("ewar-graph-open")) { Text("Electronic warfare comparison") }
        if (offlineFeatures != null) Button(onClick = onRemoteRepairGraph, modifier = Modifier.testTag("remote-repair-graph-open")) { Text("Remote repair comparison") }
        if (offlineFeatures != null) Button(onClick = onShieldRegenerationGraph, modifier = Modifier.testTag("shield-regeneration-graph-open")) { Text("Shield regeneration comparison") }
        OpenFits()
    }
    when (val current = engine) {
        EngineState.Loading -> Text(stringResource(R.string.engine_loading))
        is EngineState.Failed -> {
            Text(stringResource(R.string.engine_failed), color = MaterialTheme.colorScheme.error)
            Text(current.message, style = MaterialTheme.typography.bodySmall)
        }
        is EngineState.Empty -> {
            current.error?.let { Text(it.message, color = MaterialTheme.colorScheme.error) }
        }
        is EngineState.Ready -> {
            val stats = current.fit.stats
            val ammunition = current.fit.modules.firstOrNull()?.charge ?: stringResource(R.string.no_ammunition)
            current.error?.let { Text(it.message, color = MaterialTheme.colorScheme.error) }
            Text(current.fit.name, style = MaterialTheme.typography.titleLarge, modifier = Modifier.bringIntoViewRequester(selectedTitle))
            TextButton(onClick = {
                focus.clearFocus()
                EngineRuntime.catalog.value.hulls.find { it.name == current.fit.ship }?.let(libraryModel::showHull)
            }, modifier = Modifier.testTag("back-to-hull")) { Text("Browse ${current.fit.ship} fits") }
            val sampleGuns = current.fit.modules.take(2).size == 2 &&
                current.fit.modules.take(2).all { it.name == "Dual 150mm Railgun II" }
            if (sampleGuns) Text(stringResource(R.string.sample_ammunition, ammunition))
            else Text(current.fit.ship + " · " + current.fit.modules.count { it.emptySlot == null } + " modules")
            if (offlineFeatures != null) Button(onClick = onExport, modifier = Modifier.testTag("eft-export-open")) { Text("Export EFT fit") }
            if (offlineFeatures != null) Button(onClick = onPilotSecurity, modifier = Modifier.testTag("pilot-security-open")) { Text("Pilot security") }
            Button(onClick = onResources, modifier = Modifier.testTag("resources-open")) { Text("Resources") }
            Button(onClick = onDefenses, modifier = Modifier.testTag("defense-open")) { Text("Defenses") }
            Button(onClick = onOutput, modifier = Modifier.testTag("output-open")) { Text("Output statistics") }
            Button(onClick = onTargeting, modifier = Modifier.testTag("targeting-open")) { Text("Targeting and navigation") }
            Button(onClick = onInspect, modifier = Modifier.testTag("inspection-open")) { Text("Inspect ship and fitted items") }
            Button(onClick = onTank, modifier = Modifier.testTag("tank-open")) { Text("Repair and tank") }
            Button(onClick = onCapacitor, modifier = Modifier.testTag("capacitor-open")) { Text("Capacitor") }
            Button(onClick = onModules, modifier = Modifier.testTag("modules-open")) { Text("Edit modules") }
            TextButton(onClick = onVariations, modifier = Modifier.testTag("variations-open")) { Text("Item variations") }
            TextButton(onClick = onModes, modifier = Modifier.testTag("modes-open")) { Text("Hull modes") }
            TextButton(onClick = onSubsystems, modifier = Modifier.testTag("subsystems-open")) { Text("Strategic cruiser subsystems") }
            TextButton(onClick = onServices, modifier = Modifier.testTag("services-open")) { Text("Structure services") }
            TextButton(onClick = onDrones, modifier = Modifier.testTag("drones-open")) { Text("Drones") }
            TextButton(onClick = onFighters, modifier = Modifier.testTag("fighters-open")) { Text("Fighters") }
            TextButton(onClick = onImplants, modifier = Modifier.testTag("implants-open")) { Text("Implants") }
            TextButton(onClick = onBoosters, modifier = Modifier.testTag("boosters-open")) { Text("Boosters") }
            TextButton(onClick = onCargo, modifier = Modifier.testTag("cargo-open")) { Text("Cargo") }
            TextButton(onClick = onCommands, modifier = Modifier.testTag("commands-open")) { Text("Saved command fits") }
            TextButton(onClick = onProjectedModules, modifier = Modifier.testTag("projected-modules-open")) { Text("Individual projected modules") }
            TextButton(onClick = onProjectedDrones, modifier = Modifier.testTag("projected-drones-open")) { Text("Individual projected drones") }
            TextButton(onClick = onProjectedFighters, modifier = Modifier.testTag("projected-fighters-open")) { Text("Individual projected fighters") }
            TextButton(onClick = onProjections, modifier = Modifier.testTag("projections-open")) { Text("Saved-fit projections") }
            TextButton(onClick = onNotes, modifier = Modifier.testTag("notes-open")) { Text("Fit notes") }
            if (sampleGuns) Button(onClick = {
                EngineRuntime.setAmmunition(context, if (ammunition == "Iron Charge M") "Antimatter Charge M" else "Iron Charge M")
            }) { Text(stringResource(R.string.switch_ammunition)) }
            for ((name, label) in listOf(
                "total_dps" to R.string.total_dps,
                "drone_control_range" to R.string.drone_control_range,
                "gun_optimal" to R.string.gun_optimal,
            )) {
                Text(stringResource(label) + ": " + formatStat(stats.getValue(name)))
            }
            TextButton(onClick = { expanded = !expanded }) {
                Text(stringResource(if (expanded) R.string.hide_attributes else R.string.all_attributes))
            }
            if (expanded) {
                for (name in stats.keys.sorted()) {
                    val label = if (name.endsWith("_ehp_uniform")) name.removeSuffix("_uniform") else name
                    Text(label.replace('_', ' ') + ": " + formatStat(stats.getValue(name)))
                }
            }
        }
    }
    if (engine is EngineState.Ready || engine is EngineState.Empty) FitLibrary(libraryModel)
}

internal fun formatStat(stat: Stat): String {
    if (stat.value == StatValue.Unavailable) return "Unavailable"
    val value = stat.value.raw
    val unit = stat.unit
    val formatted = if (value is Number) NumberFormat.getNumberInstance().apply {
        maximumFractionDigits = 3
    }.format(value) else value.toString()
    return if (unit == "boolean") formatted else "$formatted $unit"
}

@Composable
private fun AboutBuild(onBack: () -> Unit) {
    Text(stringResource(R.string.about_title), style = MaterialTheme.typography.headlineLarge)
    Text(stringResource(R.string.version, BuildConfig.VERSION_NAME), style = MaterialTheme.typography.labelLarge)
    Text(stringResource(R.string.about_goal), style = MaterialTheme.typography.bodyLarge)
    Text(stringResource(R.string.about_scope), style = MaterialTheme.typography.bodyLarge)
    Text(stringResource(R.string.about_credit), style = MaterialTheme.typography.bodyMedium)
    Text(stringResource(R.string.source_url), color = MaterialTheme.colorScheme.primary)
    Text(stringResource(R.string.license_label), style = MaterialTheme.typography.bodySmall)
    TextButton(onClick = onBack) { Text(stringResource(R.string.back)) }
}
