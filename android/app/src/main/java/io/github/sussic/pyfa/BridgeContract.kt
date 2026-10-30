package io.github.sussic.pyfa

import java.util.Collections
import org.json.JSONArray
import org.json.JSONObject

/** Bundled bridge capabilities; this is not yet every Pyfa field. */
enum class ModuleState { OFFLINE, ONLINE, ACTIVE, OVERHEATED }
enum class SystemSecurity { HISEC, LOWSEC, NULLSEC, WSPACE }

data class DamagePattern(
    val emAmount: Double,
    val thermalAmount: Double,
    val kineticAmount: Double,
    val explosiveAmount: Double,
)
data class ProjectedFighterSelectionRow(val position: Int, val objectKey: String)
data class ProjectedDroneSelectionRow(val position: Int, val objectKey: String)
data class ProjectedModuleSelectionRow(val position: Int, val objectKey: String)
data class Security(val system: SystemSecurity, val pilot: Double)
data class ModuleSpec(val name: String, val state: ModuleState, val charge: String? = null, val spoolCycles: Int? = null, val rahPattern: RahPattern? = null)
data class DroneSpec(val name: String, val amount: Int, val active: Int)
data class FitSpec(
    val name: String,
    val ship: String,
    val skillLevel: Int,
    val factorReload: Boolean,
    val damagePattern: DamagePattern,
    val security: Security,
    val modules: List<ModuleSpec>,
    val drones: List<DroneSpec>,
    val modeId: Int? = null,
    val notes: String? = null,
    val targetProfile: TargetProfile? = null,
    val fighters: List<FighterSpec> = emptyList(),
    val environments: List<EnvironmentSpec> = emptyList(),
)

sealed interface BridgeOperation {
    data class SetMutationAttributes(val fitId: String, val kind: String, val position: Int,
        val objectKey: String, val attributes: List<MutationRollInput>) : BridgeOperation
    data class SetMutationDisplayAttributes(val fitId: String, val kind: String, val position: Int,
        val objectKey: String, val edits: List<MutationDisplayEdit>) : BridgeOperation
    data class Snapshot(val fitIds: List<String> = emptyList()) : BridgeOperation
    data class CreateFit(val spec: FitSpec) : BridgeOperation
    data class RenameFit(val fitId: String, val name: String) : BridgeOperation
    data class SetNotes(val fitId: String, val text: String) : BridgeOperation
    data class SetSystemSecurity(val fitId: String, val system: SystemSecurity) : BridgeOperation
    data class Undo(val fitId: String) : BridgeOperation
    data class Redo(val fitId: String) : BridgeOperation
    data class DuplicateFit(val fitId: String, val name: String) : BridgeOperation
    data class DeleteFit(val fitId: String, val resolveReferences: Boolean) : BridgeOperation
    data class SetProjectedFightersActive(val fitId: String, val selection: List<ProjectedFighterSelectionRow>, val active: Boolean) : BridgeOperation
    data class SetProjectedFighterRanges(val fitId: String, val selection: List<ProjectedFighterSelectionRow>, val rangeM: Double?) : BridgeOperation
    data class RemoveProjectedFighters(val fitId: String, val selection: List<ProjectedFighterSelectionRow>) : BridgeOperation
    data class ToggleProjectedFighterAbilities(val fitId: String, val main: ProjectedFighterSelectionRow, val selection: List<ProjectedFighterSelectionRow>, val effectId: Int) : BridgeOperation
    data class SetProjectedDronesActive(val fitId: String, val selection: List<ProjectedDroneSelectionRow>, val active: Boolean) : BridgeOperation
    data class SetProjectedDroneRanges(val fitId: String, val selection: List<ProjectedDroneSelectionRow>, val rangeM: Double?) : BridgeOperation
    data class RemoveProjectedDrones(val fitId: String, val selection: List<ProjectedDroneSelectionRow>) : BridgeOperation
    data class AddProjectedFighter(val fitId: String, val itemId: Int) : BridgeOperation
    data class SetProjectedFighterAmount(val fitId: String, val position: Int, val objectKey: String, val amount: Int) : BridgeOperation
    data class SetProjectedFighterActive(val fitId: String, val position: Int, val objectKey: String, val active: Boolean) : BridgeOperation
    data class ToggleProjectedFighterAbility(val fitId: String, val position: Int, val objectKey: String, val effectId: Int) : BridgeOperation
    data class SetProjectedFighterRange(val fitId: String, val position: Int, val objectKey: String, val rangeM: Double?) : BridgeOperation
    data class ChangeProjectedFighterVariation(val fitId: String, val position: Int, val objectKey: String, val itemId: Int) : BridgeOperation
    data class RemoveProjectedFighter(val fitId: String, val position: Int, val objectKey: String) : BridgeOperation
    data class AddProjectedDrone(val fitId: String, val itemId: Int) : BridgeOperation
    data class SetProjectedDroneAmount(val fitId: String, val position: Int, val objectKey: String, val amount: Int) : BridgeOperation
    data class SetProjectedDroneActive(val fitId: String, val position: Int, val objectKey: String, val active: Boolean) : BridgeOperation
    data class SetProjectedDroneRange(val fitId: String, val position: Int, val objectKey: String, val rangeM: Double?) : BridgeOperation
    data class ChangeProjectedDroneVariation(val fitId: String, val position: Int, val objectKey: String, val itemId: Int) : BridgeOperation
    data class RemoveProjectedDrone(val fitId: String, val position: Int, val objectKey: String, val amount: Int) : BridgeOperation
    data class SetProjectedModuleCharges(val fitId: String, val main: ProjectedModuleSelectionRow,
        val selection: List<ProjectedModuleSelectionRow>, val scope: BulkScope, val chargeId: Int?,
        val expectedTargets: List<ProjectedModuleSelectionRow>, val expectedChanges: List<ProjectedModuleSelectionRow>) : BridgeOperation
    data class SetProjectedModuleStates(val fitId: String, val selection: List<ProjectedModuleSelectionRow>, val state: ProjectedModuleStateAction) : BridgeOperation
    data class SetProjectedModuleRanges(val fitId: String, val selection: List<ProjectedModuleSelectionRow>, val rangeM: Double?) : BridgeOperation
    data class RemoveProjectedModules(val fitId: String, val selection: List<ProjectedModuleSelectionRow>) : BridgeOperation
    data class AddProjectedModule(val fitId: String, val itemId: Int) : BridgeOperation
    data class SetProjectedModuleState(val fitId: String, val position: Int, val objectKey: String, val state: ProjectedModuleStateAction) : BridgeOperation
    data class SetProjectedModuleCharge(val fitId: String, val position: Int, val objectKey: String, val chargeId: Int?) : BridgeOperation
    data class ChangeProjectedModuleVariation(val fitId: String, val position: Int, val objectKey: String, val itemId: Int) : BridgeOperation
    data class SetProjectedModuleRange(val fitId: String, val position: Int, val objectKey: String, val rangeM: Double?) : BridgeOperation
    data class SetProjectedModuleSpool(val fitId: String, val position: Int, val objectKey: String, val cycles: Int?) : BridgeOperation
    data class RemoveProjectedModule(val fitId: String, val position: Int, val objectKey: String) : BridgeOperation
    data class AddModule(val fitId: String, val itemId: Int) : BridgeOperation
    data class ReplaceModule(val fitId: String, val position: Int, val itemId: Int) : BridgeOperation
    data class RemoveModule(val fitId: String, val position: Int) : BridgeOperation
    data class AddFighter(val fitId: String, val itemId: Int) : BridgeOperation
    data class SetFighterAmount(val fitId: String, val position: Int, val amount: Int) : BridgeOperation
    data class RemoveFighters(val fitId: String, val positions: List<Int>) : BridgeOperation
    data class ToggleFighters(val fitId: String, val mainPosition: Int, val positions: List<Int>) : BridgeOperation
    data class ToggleFighterAbility(val fitId: String, val mainPosition: Int, val positions: List<Int>, val effectId: Int) : BridgeOperation
    data class ChangeFighterVariations(val fitId: String, val mainPosition: Int, val positions: List<Int>, val itemId: Int) : BridgeOperation
    data class AddDrone(val fitId: String, val itemId: Int, val amount: Int) : BridgeOperation
    data class AddDroneStack(val fitId: String, val itemId: Int) : BridgeOperation
    data class SetDroneAmount(val fitId: String, val position: Int, val amount: Int) : BridgeOperation
    data class RemoveDrones(val fitId: String, val positions: List<Int>, val amount: Int) : BridgeOperation
    data class ToggleDrones(val fitId: String, val mainPosition: Int, val positions: List<Int>) : BridgeOperation
    data class CloneDrone(val fitId: String, val position: Int) : BridgeOperation
    data class SplitDrone(val fitId: String, val position: Int, val amount: Int) : BridgeOperation
    data class MergeDrones(val fitId: String, val sourcePosition: Int, val destinationPosition: Int) : BridgeOperation
    data class AddCargo(val fitId: String, val itemId: Int, val quantity: Long) : BridgeOperation
    data class TransferCargo(val fitId: String, val direction: CargoTransferDirection,
        val positions: List<Int>, val itemId: Int?, val copy: Boolean) : BridgeOperation
    data class SetCargoQuantity(val fitId: String, val itemId: Int, val quantity: Long) : BridgeOperation
    data class RemoveCargo(val fitId: String, val itemId: Int, val quantity: Long) : BridgeOperation
    data class SetCargoQuantities(val fitId: String, val itemIds: List<Int>, val quantity: Long) : BridgeOperation
    data class RemoveCargos(val fitId: String, val itemIds: List<Int>) : BridgeOperation
    data class AddCargoPreset(val fitId: String, val itemId: Int) : BridgeOperation
    data class FillCargo(val fitId: String, val itemId: Int, val fromCargo: Boolean) : BridgeOperation
    data class ChangeCargoVariations(val fitId: String, val mainItemId: Int,
        val itemIds: List<Int>, val itemId: Int) : BridgeOperation
    data class SetFitRestrictions(val fitId: String, val ignore: Boolean) : BridgeOperation
    data class ChangeMode(val fitId: String, val itemId: Int) : BridgeOperation
    data class SetSubsystem(val fitId: String, val kind: Int, val itemId: Int?) : BridgeOperation
    data class SetCharges(val fitId: String, val moduleIndices: List<Int>, val charge: String?) : BridgeOperation
    data class SetModuleRah(val fitId: String, val position: Int, val mode: RahMode, val patternId: Int? = null) : BridgeOperation
    data class SetModuleSpool(val fitId: String, val position: Int, val cycles: Int?) : BridgeOperation
    data class SetModuleCharge(val fitId: String, val position: Int, val chargeId: Int?) : BridgeOperation
    data class SetBulkCharges(val fitId: String, val mainPosition: Int, val moduleIndices: List<Int>,
        val scope: BulkScope, val chargeId: Int?) : BridgeOperation
    data class SetBulkStates(val fitId: String, val mainPosition: Int, val moduleIndices: List<Int>,
        val scope: BulkScope, val click: StateClick) : BridgeOperation
    data class FillModulesItem(val fitId: String, val itemId: Int) : BridgeOperation
    data class FillModulesClone(val fitId: String, val position: Int) : BridgeOperation
    data class CloneSelectedModules(val fitId: String, val moduleIndices: List<Int>) : BridgeOperation
    data class CloneModuleAt(val fitId: String, val sourcePosition: Int, val destinationPosition: Int) : BridgeOperation
    data class ChangeVariation(val fitId: String, val context: VariationContext, val position: Int, val itemId: Int) : BridgeOperation
    data class ChangeBulkVariations(val fitId: String, val mainPosition: Int, val moduleIndices: List<Int>,
        val scope: BulkScope, val itemId: Int) : BridgeOperation
    data class RemoveBulkModules(val fitId: String, val mainPosition: Int, val moduleIndices: List<Int>,
        val scope: BulkScope) : BridgeOperation
    data class SwapModules(val fitId: String, val fromPosition: Int, val toPosition: Int) : BridgeOperation
    data class SetModuleStates(val fitId: String, val moduleIndices: List<Int>, val state: ModuleState) : BridgeOperation
    data class SetSkillLevel(val fitId: String, val skill: String, val level: Int) : BridgeOperation
    data class SetTargetProfile(val fitId: String, val profile: TargetProfile?) : BridgeOperation
    data class SetDamagePattern(val fitId: String, val pattern: DamagePattern) : BridgeOperation
    data class AddImplant(val fitId: String, val implant: String, val active: Boolean = true) : BridgeOperation
    data class SetImplantActive(val fitId: String, val slot: Int, val active: Boolean) : BridgeOperation
    data class RemoveImplant(val fitId: String, val slot: Int) : BridgeOperation
    data class FitImplant(val fitId: String, val itemId: Int) : BridgeOperation
    data class ToggleImplants(val fitId: String, val mainPosition: Int, val positions: List<Int>) : BridgeOperation
    data class RemoveImplants(val fitId: String, val positions: List<Int>) : BridgeOperation
    data class FitBooster(val fitId: String, val itemId: Int) : BridgeOperation
    data class ToggleBoosters(val fitId: String, val mainPosition: Int, val positions: List<Int>) : BridgeOperation
    data class RemoveBoosters(val fitId: String, val positions: List<Int>) : BridgeOperation
    data class ChangeBoosterVariation(val fitId: String, val position: Int, val itemId: Int) : BridgeOperation
    data class AddBooster(val fitId: String, val itemId: Int, val active: Boolean = true) : BridgeOperation
    data class SetBoosterActive(val fitId: String, val position: Int, val active: Boolean) : BridgeOperation
    data class SetBoosterSideEffect(val fitId: String, val position: Int, val effectId: Int, val active: Boolean) : BridgeOperation
    data class RemoveBooster(val fitId: String, val position: Int) : BridgeOperation
    data class AddProjection(
        val sourceId: String, val targetId: String, val rangeM: Double? = null,
        val active: Boolean = true, val amount: Int = 1,
    ) : BridgeOperation
    data class ConfigureProjection(
        val sourceId: String, val targetId: String, val rangeM: Double?,
        val active: Boolean, val amount: Int,
    ) : BridgeOperation
    data class RemoveProjection(val sourceId: String, val targetId: String) : BridgeOperation
    data class AddProjectedFit(val sourceId: String, val targetId: String) : BridgeOperation
    data class SetProjectedFitAmount(val sourceId: String, val targetId: String, val amount: Int) : BridgeOperation
    data class SetProjectedFitRange(val sourceId: String, val targetId: String, val rangeM: Double?) : BridgeOperation
    data class SetProjectedFitActive(val sourceId: String, val targetId: String, val active: Boolean) : BridgeOperation
    data class RemoveProjectedFit(val sourceId: String, val targetId: String) : BridgeOperation
    data class AddCommandFit(val sourceId: String, val targetId: String) : BridgeOperation
    data class SetCommandFitActive(val sourceId: String, val targetId: String, val active: Boolean) : BridgeOperation
    data class RemoveCommandFit(val sourceId: String, val targetId: String) : BridgeOperation
    data class AddCommand(val sourceId: String, val targetId: String, val active: Boolean = true) : BridgeOperation
    data class SetCommandActive(val sourceId: String, val targetId: String, val active: Boolean) : BridgeOperation
    data class RemoveCommand(val sourceId: String, val targetId: String) : BridgeOperation
}

/** Copy caller-owned collections before enqueueing work on the engine thread. */
fun BridgeOperation.snapshotArguments(): BridgeOperation = when (this) {
    is BridgeOperation.SetMutationAttributes -> copy(attributes = immutableList(attributes))
    is BridgeOperation.SetMutationDisplayAttributes -> copy(edits = immutableList(edits))
    is BridgeOperation.SetProjectedFightersActive -> copy(selection = immutableList(selection))
    is BridgeOperation.SetProjectedFighterRanges -> copy(selection = immutableList(selection))
    is BridgeOperation.RemoveProjectedFighters -> copy(selection = immutableList(selection))
    is BridgeOperation.ToggleProjectedFighterAbilities -> copy(selection = immutableList(selection))
    is BridgeOperation.SetProjectedDronesActive -> copy(selection = immutableList(selection))
    is BridgeOperation.SetProjectedDroneRanges -> copy(selection = immutableList(selection))
    is BridgeOperation.RemoveProjectedDrones -> copy(selection = immutableList(selection))
    is BridgeOperation.SetProjectedModuleCharges -> copy(selection = immutableList(selection),
        expectedTargets = immutableList(expectedTargets), expectedChanges = immutableList(expectedChanges))
    is BridgeOperation.SetProjectedModuleStates -> copy(selection = immutableList(selection))
    is BridgeOperation.SetProjectedModuleRanges -> copy(selection = immutableList(selection))
    is BridgeOperation.RemoveProjectedModules -> copy(selection = immutableList(selection))
    is BridgeOperation.ToggleImplants -> copy(positions = immutableList(positions))
    is BridgeOperation.RemoveImplants -> copy(positions = immutableList(positions))
    is BridgeOperation.ToggleBoosters -> copy(positions = immutableList(positions))
    is BridgeOperation.RemoveBoosters -> copy(positions = immutableList(positions))
    is BridgeOperation.RemoveFighters -> copy(positions = immutableList(positions))
    is BridgeOperation.ToggleFighters -> copy(positions = immutableList(positions))
    is BridgeOperation.ToggleFighterAbility -> copy(positions = immutableList(positions))
    is BridgeOperation.ChangeFighterVariations -> copy(positions = immutableList(positions))
    is BridgeOperation.RemoveDrones -> copy(positions = immutableList(positions))
    is BridgeOperation.ToggleDrones -> copy(positions = immutableList(positions))
    is BridgeOperation.TransferCargo -> copy(positions = immutableList(positions))
    is BridgeOperation.Snapshot -> copy(fitIds = immutableList(fitIds))
    is BridgeOperation.CreateFit -> copy(spec = spec.copy(
        modules = immutableList(spec.modules), drones = immutableList(spec.drones),
        fighters = immutableList(spec.fighters.map { it.copy(abilities = it.abilities?.let(::immutableList)) }),
        environments = immutableList(spec.environments),
    ))
    is BridgeOperation.SetCharges -> copy(moduleIndices = immutableList(moduleIndices))
    is BridgeOperation.SetModuleStates -> copy(moduleIndices = immutableList(moduleIndices))
    is BridgeOperation.SetBulkStates -> copy(moduleIndices = immutableList(moduleIndices))
    is BridgeOperation.ChangeBulkVariations -> copy(moduleIndices = immutableList(moduleIndices))
    is BridgeOperation.RemoveBulkModules -> copy(moduleIndices = immutableList(moduleIndices))
    is BridgeOperation.CloneSelectedModules -> copy(moduleIndices = immutableList(moduleIndices))
    else -> this
}

data class BridgeRequest(
    val requestId: String,
    val sessionId: String,
    val operation: BridgeOperation,
    val expectedRevisions: Map<String, Long> = emptyMap(),
)

/** Keep integer, decimal and boolean wire types distinct; never invent zero. */
sealed interface StatValue {
    val raw: Any
    fun numberOrNull(): Double? = when (this) {
        is Integer -> value.toDouble()
        is Decimal -> value
        is BooleanValue, is Text, Unavailable -> null
    }
    data class Integer(val value: Long) : StatValue { override val raw: Any get() = value }
    data class Decimal(val value: Double) : StatValue { override val raw: Any get() = value }
    data class BooleanValue(val value: Boolean) : StatValue { override val raw: Any get() = value }
    data class Text(val value: String) : StatValue { override val raw: Any get() = value }
    data object Unavailable : StatValue { override val raw: Any get() = JSONObject.NULL }
}

data class Stat(val value: StatValue, val unit: String)
data class ModuleSnapshot(val index: Int, val name: String?, val charge: String?, val state: ModuleState?,
    val emptySlot: ModuleSlot? = null)
data class ImplantSnapshot(val name: String, val slot: Int, val active: Boolean)
data class ProjectionSnapshot(val sourceId: String, val rangeM: Double?, val active: Boolean, val amount: Int)
data class CommandSnapshot(val sourceId: String, val active: Boolean)
data class FitSnapshot(
    val id: String,
    val revision: Long,
    val name: String,
    val ship: String,
    val stats: Map<String, Stat>,
    val modules: List<ModuleSnapshot>,
    val skills: Map<String, Int?>,
    val implants: List<ImplantSnapshot>,
    val projections: List<ProjectionSnapshot>,
    val commands: List<CommandSnapshot>,
)

enum class BridgeErrorCode {
    INVALID_REQUEST, UNSUPPORTED_VERSION, UNKNOWN_OPERATION, UNKNOWN_FIT,
    REVISION_CONFLICT, INVALID_EDIT, ENGINE_ERROR, ENGINE_UNAVAILABLE,
}
enum class BridgeStatus { OK, ERROR }
data class BridgeError(val code: BridgeErrorCode, val message: String)
data class BridgeResponse(
    val requestId: String?,
    val sessionId: String,
    val status: BridgeStatus,
    val fits: List<FitSnapshot>,
    val error: BridgeError?,
) {
    val isSuccess: Boolean get() = status == BridgeStatus.OK
}

class BridgeProtocolException(message: String) : IllegalArgumentException(message)

object BridgeCodec {
    const val VERSION = 1

    fun decodeInspection(json: String): ItemInspection = InspectionCodec.decode(objectValue(StrictJson(json).parse(), "inspection"))
    fun decodeInspectionOptions(json: String): InspectionOptions = InspectionCodec.options(objectValue(StrictJson(json).parse(), "inspection options"))

    private fun decodeTargetProfile(raw: Any): TargetProfile? {
        if (raw == JSONObject.NULL) return null
        val row = objectValue(raw, "target profile")
        keys(row, setOf("emAmount", "thermalAmount", "kineticAmount", "explosiveAmount", "maxVelocity", "signatureRadius", "radius", "hp"), path = "target profile")
        fun required(key: String, resistance: Boolean = false): Double {
            val value = number(row.get(key), key)
            requireProtocol(if (resistance) value in 0.0..1.0 else value >= 0, "Invalid target profile value")
            return value
        }
        fun dimension(key: String): Double? = nullable(row.get(key))?.let { number(it, key).also { v -> requireProtocol(v >= 0, "Invalid target dimension") } }
        return TargetProfile(required("emAmount", true), required("thermalAmount", true), required("kineticAmount", true), required("explosiveAmount", true),
            required("maxVelocity"), dimension("signatureRadius"), required("radius"), dimension("hp"))
    }

    private fun encodeTargetProfile(profile: TargetProfile?): JSONObject? = profile?.let {
        obj("emAmount" to it.emAmount, "thermalAmount" to it.thermalAmount, "kineticAmount" to it.kineticAmount, "explosiveAmount" to it.explosiveAmount,
            "maxVelocity" to it.maxVelocity, "signatureRadius" to it.signatureRadius, "radius" to it.radius, "hp" to it.hp).also { decodeTargetProfile(it) }
    }

    fun decodeTargeting(json: String): FitTargeting {
        val root = objectValue(StrictJson(json).parse(), "targeting")
        keys(root, setOf("version", "fit_id", "revision", "targeting"), path = "targeting")
        requireProtocol(long(root.get("version"), "version") == 1L, "Unsupported targeting version")
        val revision = long(root.get("revision"), "revision"); requireProtocol(revision >= 1, "Invalid targeting revision")
        fun scalar(raw: Any, unit: String, signed: Boolean = false): TargetingScalar {
            val row = objectValue(raw, "targeting scalar")
            keys(row, setOf("value", "value_type", "unit", "display", "detail"), path = "targeting scalar")
            requireProtocol(text(row.get("unit"), "unit") == unit, "Incorrect targeting unit")
            val value = when (text(row.get("value_type"), "value_type")) {
                "unavailable" -> { requireProtocol(row.get("value") == JSONObject.NULL, "Unavailable targeting has value"); StatValue.Unavailable }
                "integer" -> StatValue.Integer(long(row.get("value"), "value"))
                "decimal" -> { val v = row.get("value"); requireProtocol(v is Double, "Decimal targeting lost type"); StatValue.Decimal(finite(v as Double, "value")) }
                else -> fail("Invalid targeting scalar type")
            }
            fun label(key: String): String? = nullable(row.get(key))?.let { nonempty(it, key) }.also {
                requireProtocol((it == null) == (value == StatValue.Unavailable), "Targeting availability differs")
            }
            requireProtocol(signed || value.numberOrNull()?.let { it >= 0 } != false, "Invalid targeting value")
            return TargetingScalar(value, unit, label("display"), label("detail"))
        }
        val stats = objectValue(root.get("targeting"), "targeting values")
        keys(stats, setOf("main", "lock_times", "sensor_type", "holds") + TARGETING_DETAIL_UNITS.keys, path = "targeting values")
        val main = objectValue(stats.get("main"), "main"); keys(main, TARGETING_UNITS.keys, path = "main")
        val sensor = text(stats.get("sensor_type"), "sensor_type")
        requireProtocol(sensor in setOf("Magnetometric", "Ladar", "Radar", "Gravimetric", "Multispectral"), "Unknown sensor type")
        val locks = array(stats.get("lock_times"), "lock_times").mapIndexed { index, raw ->
            val row = objectValue(raw, "lock time"); keys(row, setOf("name", "radius", "time"), path = "lock time")
            val name = text(row.get("name"), "name"); val radius = integer(row.get("radius"), "radius", 1)
            requireProtocol(index < TARGETING_RADII.size && name == TARGETING_RADII.keys.elementAt(index) && radius == TARGETING_RADII.getValue(name), "Incorrect reference target")
            ReferenceLockTime(name, radius, scalar(row.get("time"), "s"))
        }
        requireProtocol(locks.size == TARGETING_RADII.size, "Missing reference target")
        val holds = array(stats.get("holds"), "holds").mapIndexed { index, raw ->
            val row = objectValue(raw, "hold"); keys(row, setOf("attribute", "name", "present", "capacity"), path = "hold")
            val attribute = text(row.get("attribute"), "attribute"); val name = text(row.get("name"), "name")
            requireProtocol(index < TARGETING_HOLDS.size && attribute == TARGETING_HOLDS.keys.elementAt(index) && name == TARGETING_HOLDS.getValue(attribute), "Incorrect special hold")
            val present = bool(row.get("present"), "present"); val capacity = scalar(row.get("capacity"), "m³")
            requireProtocol(present == ((capacity.value.numberOrNull() ?: 0.0) > 0), "Hold presence differs from capacity")
            SpecialHold(attribute, name, present, capacity)
        }
        requireProtocol(holds.size == TARGETING_HOLDS.size, "Missing special hold")
        val mainValues = immutableMap(TARGETING_UNITS.mapValues { (key, unit) -> scalar(main.get(key), unit) })
        requireProtocol(mainValues.getValue("targets").value is StatValue.Integer || mainValues.getValue("targets").value == StatValue.Unavailable, "Target count lost integer type")
        return FitTargeting(identifier(root.get("fit_id"), "fit_id"), revision,
            mainValues, immutableList(locks), sensor,
            immutableMap(TARGETING_DETAIL_UNITS.mapValues { (key, unit) -> scalar(stats.get(key), unit, signed = key == "warp_core") }), immutableList(holds))
    }

    fun decodeOutput(json: String): FitOutput {
        val root = objectValue(StrictJson(json).parse(), "output")
        keys(root, setOf("version", "fit_id", "revision", "output", "target_profile"), path = "output")
        requireProtocol(long(root.get("version"), "version") == 1L, "Unsupported output version")
        val revision = long(root.get("revision"), "revision"); requireProtocol(revision >= 1, "Invalid output revision")
        fun scalar(raw: Any, unit: String): OutputScalar {
            val row = objectValue(raw, "output scalar")
            keys(row, setOf("value", "value_type", "unit", "display", "detail"), path = "output scalar")
            requireProtocol(text(row.get("unit"), "unit") == unit, "Incorrect output unit")
            val value = when (text(row.get("value_type"), "value_type")) {
                "unavailable" -> { requireProtocol(row.get("value") == JSONObject.NULL, "Unavailable output has value"); StatValue.Unavailable }
                "integer" -> StatValue.Integer(long(row.get("value"), "value"))
                "decimal" -> { val v = row.get("value"); requireProtocol(v is Double, "Decimal output lost type"); StatValue.Decimal(finite(v as Double, "value")) }
                else -> fail("Invalid output scalar type")
            }
            fun label(key: String): String? = nullable(row.get(key))?.let { nonempty(it, key) }.also {
                requireProtocol((it == null) == (value == StatValue.Unavailable), "Output availability differs")
            }
            requireProtocol(value.numberOrNull()?.let { it >= 0 } != false, "Invalid output value")
            return OutputScalar(value, unit, label("display"), label("detail"))
        }
        fun spool(row: JSONObject, unit: String): OutputSpool = OutputSpool(scalar(row.get("current"), unit), scalar(row.get("pre"), unit),
            scalar(row.get("full"), unit), bool(row.get("indicated"), "indicated"), text(row.get("tooltip"), "tooltip"))
        val output = objectValue(root.get("output"), "output values")
        keys(output, setOf("firepower", "mining", "bombing", "outgoing", "effective", "default_spool_percentage"), path = "output values")
        val firepower = objectValue(output.get("firepower"), "firepower"); keys(firepower, setOf("raw", "effective"), path = "firepower")
        val modes = listOf("raw", "effective").associateWith { mode ->
            val rows = objectValue(firepower.get(mode), mode); keys(rows, setOf("weapon", "drone", "total", "volley"), path = mode)
            java.util.Collections.unmodifiableMap(listOf("weapon", "drone", "total", "volley").associateWith { name ->
                val row = objectValue(rows.get(name), name); keys(row, setOf("current", "pre", "full", "indicated", "tooltip", "damage"), path = name)
                val unit = if (name == "volley") "HP" else "DPS"
                val damage = objectValue(row.get("damage"), "damage"); keys(damage, OUTPUT_DAMAGE.keys, path = "damage")
                OutputFirepower(spool(row, unit), java.util.Collections.unmodifiableMap(OUTPUT_DAMAGE.keys.associateWith { kind ->
                    val cell = objectValue(damage.get(kind), kind); keys(cell, setOf("amount", "share"), path = kind)
                    OutputDamage(scalar(cell.get("amount"), unit), scalar(cell.get("share"), "%"))
                }))
            })
        }
        val mining = objectValue(output.get("mining"), "mining"); keys(mining, setOf("module", "drone", "total"), path = "mining")
        val miners = listOf("module", "drone", "total").associateWith { name ->
            val row = objectValue(mining.get(name), name); keys(row, setOf("yield_second", "drain_second", "yield_hour", "drain_hour", "efficiency"), path = name)
            OutputMining(scalar(row.get("yield_second"), "m³/s"), scalar(row.get("drain_second"), "m³/s"), scalar(row.get("yield_hour"), "m³/hour"),
                scalar(row.get("drain_hour"), "m³/hour"), scalar(row.get("efficiency"), "%"))
        }
        val bombing = objectValue(output.get("bombing"), "bombing"); keys(bombing, setOf("signature", "environment_multiplier", "levels"), path = "bombing")
        val levels = array(bombing.get("levels"), "levels"); requireProtocol(levels.size == 6, "Missing bomb levels")
        val bombs = levels.mapIndexed { level, raw ->
            val row = objectValue(raw, "bomb level"); keys(row, setOf("covert_ops_level", "counts"), path = "bomb level")
            requireProtocol(integer(row.get("covert_ops_level"), "covert_ops_level", 0, 5) == level, "Incorrect bomb level")
            val counts = objectValue(row.get("counts"), "counts"); keys(counts, OUTPUT_DAMAGE.keys - "pure", path = "counts")
            java.util.Collections.unmodifiableMap((OUTPUT_DAMAGE.keys - "pure").associateWith { scalar(counts.get(it), "bombs") })
        }
        val outgoing = objectValue(output.get("outgoing"), "outgoing"); keys(outgoing, OUTPUT_REMOTE.keys, path = "outgoing")
        val remote = OUTPUT_REMOTE.keys.associateWith { name ->
            val row = objectValue(outgoing.get(name), name); keys(row, setOf("current", "pre", "full", "indicated", "tooltip"), path = name)
            spool(row, if (name == "capacitor") "GJ/s" else "HP/s")
        }
        val percentage = number(output.get("default_spool_percentage"), "default_spool_percentage"); requireProtocol(percentage in 0.0..100.0, "Invalid spool percentage")
        val profile = decodeTargetProfile(root.get("target_profile")); val effective = bool(output.get("effective"), "effective")
        requireProtocol(effective == (profile != null), "Target profile availability differs")
        return FitOutput(identifier(root.get("fit_id"), "fit_id"), revision, java.util.Collections.unmodifiableMap(modes), java.util.Collections.unmodifiableMap(miners),
            OutputBombing(scalar(bombing.get("signature"), "m"), scalar(bombing.get("environment_multiplier"), "x"), immutableList(bombs)),
            java.util.Collections.unmodifiableMap(remote), effective, percentage, profile)
    }

    fun decodeTank(json: String): FitTank {
        val root = objectValue(StrictJson(json).parse(), "tank")
        keys(root, setOf("version", "fit_id", "revision", "tank"), path = "tank")
        requireProtocol(long(root.get("version"), "version") == 1L, "Unsupported tank version")
        val revision = long(root.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid tank revision")
        fun scalar(raw: Any, unit: String): TankScalar {
            val row = objectValue(raw, "tank scalar")
            keys(row, setOf("value", "value_type", "unit", "display", "detail"), path = "tank scalar")
            requireProtocol(text(row.get("unit"), "unit") == unit, "Incorrect tank unit")
            val value = when (text(row.get("value_type"), "value_type")) {
                "unavailable" -> { requireProtocol(row.get("value") == JSONObject.NULL, "Unavailable tank has value"); StatValue.Unavailable }
                "integer" -> StatValue.Integer(long(row.get("value"), "value"))
                "decimal" -> { val v = row.get("value"); requireProtocol(v is Double, "Decimal tank lost type"); StatValue.Decimal(finite(v as Double, "value")) }
                else -> fail("Invalid tank scalar type")
            }
            // EOS can produce negative sustained endpoints under capacitor limits;
            // retain its result instead of clamping it in presentation.
            fun label(name: String): String? {
                val result = nullable(row.get(name))?.let { nonempty(it, name) }
                requireProtocol((result == null) == (value == StatValue.Unavailable), "Tank availability differs")
                return result
            }
            return TankScalar(value, unit, label("display"), label("detail"))
        }
        val tank = objectValue(root.get("tank"), "tank modes")
        keys(tank, setOf("raw", "effective"), path = "tank modes")
        val modes = listOf("raw", "effective").associateWith { mode ->
            val unit = if (mode == "raw") "HP/s" else "EHP/s"
            val row = objectValue(tank.get(mode), mode)
            keys(row, setOf("passive_shield", "reinforced", "sustained"), path = mode)
            val variants = listOf("reinforced", "sustained").associateWith { stability ->
                val variant = objectValue(row.get(stability), stability)
                keys(variant, setOf("repairs", "armor_spool"), path = stability)
                val repairs = objectValue(variant.get("repairs"), "repairs")
                keys(repairs, TANK_REPAIRS.keys, path = "repairs")
                val spool = objectValue(variant.get("armor_spool"), "armor spool")
                keys(spool, setOf("pre", "full", "indicated", "tooltip"), path = "armor spool")
                val indicated = bool(spool.get("indicated"), "indicated")
                val tooltip = text(spool.get("tooltip"), "tooltip")
                requireProtocol(indicated == tooltip.isNotEmpty(), "Spool indication differs")
                TankVariant(Collections.unmodifiableMap(TANK_REPAIRS.keys.associateWith { scalar(repairs.get(it), unit) }),
                    scalar(spool.get("pre"), unit), scalar(spool.get("full"), unit), indicated, tooltip)
            }
            TankMode(scalar(row.get("passive_shield"), unit), variants.getValue("reinforced"), variants.getValue("sustained"))
        }
        return FitTank(identifier(root.get("fit_id"), "fit_id"), revision, Collections.unmodifiableMap(modes))
    }

    fun decodeDefenses(json: String): FitDefenses {
        val root = objectValue(StrictJson(json).parse(), "defenses")
        keys(root, setOf("version", "fit_id", "revision", "defenses"), path = "defenses")
        requireProtocol(long(root.get("version"), "version") == 1L, "Unsupported defenses version")
        val revision = long(root.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid defenses revision")
        fun scalar(raw: Any, unit: String): DefenseScalar {
            val row = objectValue(raw, "defense scalar")
            keys(row, setOf("value", "value_type", "unit", "display", "detail"), path = "defense scalar")
            requireProtocol(text(row.get("unit"), "unit") == unit, "Incorrect defense unit")
            val value = when (text(row.get("value_type"), "value_type")) {
                "unavailable" -> { requireProtocol(row.get("value") == JSONObject.NULL, "Unavailable defense has value"); StatValue.Unavailable }
                "integer" -> StatValue.Integer(long(row.get("value"), "value"))
                "decimal" -> { val v = row.get("value"); requireProtocol(v is Double, "Decimal defense lost type"); StatValue.Decimal(finite(v as Double, "value")) }
                else -> fail("Invalid defense scalar type")
            }
            requireProtocol(value.numberOrNull()?.let { if (unit == "%") it <= 100 else it >= 0 } != false, "Invalid defense value")
            fun label(name: String): String? {
                val result = nullable(row.get(name))?.let { nonempty(it, name) }
                requireProtocol((result == null) == (value == StatValue.Unavailable), "Defense availability differs")
                return result
            }
            return DefenseScalar(value, unit, label("display"), label("detail"))
        }
        val defenses = objectValue(root.get("defenses"), "defenses")
        keys(defenses, setOf("layers", "total", "pattern"), path = "defenses")
        val layers = objectValue(defenses.get("layers"), "layers")
        keys(layers, DEFENSE_LAYERS.keys, path = "layers")
        val decoded = DEFENSE_LAYERS.keys.associateWith { name ->
            val row = objectValue(layers.get(name), name)
            keys(row, setOf("hp", "ehp", "multiplier", "resistances"), path = name)
            val resist = objectValue(row.get("resistances"), "resistances")
            keys(resist, DAMAGE_TYPES.keys, path = "resistances")
            DefenseLayer(scalar(row.get("hp"), "HP"), scalar(row.get("ehp"), "HP"), scalar(row.get("multiplier"), "x"),
                Collections.unmodifiableMap(DAMAGE_TYPES.keys.associateWith { scalar(resist.get(it), "%") }))
        }
        val total = objectValue(defenses.get("total"), "total")
        keys(total, setOf("hp", "ehp"), path = "total")
        val pattern = objectValue(defenses.get("pattern"), "pattern")
        keys(pattern, DAMAGE_TYPES.keys, path = "pattern")
        val incoming = DAMAGE_TYPES.keys.associateWith { name ->
            val row = objectValue(pattern.get(name), name)
            keys(row, setOf("amount", "percentage", "display"), path = name)
            val amount = number(row.get("amount"), "amount")
            val percent = number(row.get("percentage"), "percentage")
            requireProtocol(amount >= 0 && percent in 0.0..100.0, "Invalid incoming contribution")
            IncomingContribution(amount, percent, nonempty(row.get("display"), "display"))
        }
        requireProtocol(incoming.values.sumOf { it.amount }.let { it.isFinite() && it > 0 }, "Empty incoming pattern")
        return FitDefenses(identifier(root.get("fit_id"), "fit_id"), revision, Collections.unmodifiableMap(decoded),
            scalar(total.get("hp"), "HP"), scalar(total.get("ehp"), "HP"), Collections.unmodifiableMap(incoming))
    }

    fun decodeCapacitor(json: String): FitCapacitor {
        val root = objectValue(StrictJson(json).parse(), "capacitor")
        keys(root, setOf("version", "fit_id", "revision", "capacitor", "stability"), path = "capacitor")
        requireProtocol(long(root.get("version"), "version") == 1L, "Unsupported capacitor version")
        val revision = long(root.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid capacitor revision")
        fun scalar(raw: Any, kind: String): StatValue = when (kind) {
            "unavailable" -> { requireProtocol(raw == JSONObject.NULL, "Unavailable capacitor has a value"); StatValue.Unavailable }
            "integer" -> StatValue.Integer(long(raw, "value"))
            "decimal" -> { requireProtocol(raw is Double, "Decimal capacitor lost its scalar type"); StatValue.Decimal(finite(raw as Double, "value")) }
            else -> fail("Invalid capacitor scalar type")
        }
        fun label(raw: Any, unavailable: Boolean): String? {
            val result = nullable(raw)?.let { nonempty(it, "display") }
            requireProtocol((result == null) == unavailable, "Capacitor display availability differs")
            return result
        }
        val rows = objectValue(root.get("capacitor"), "capacitor values")
        keys(rows, CAPACITOR_LABELS.keys, path = "capacitor values")
        val values = CAPACITOR_LABELS.keys.associateWith { name ->
            val row = objectValue(rows.get(name), name)
            keys(row, setOf("value", "value_type", "unit", "display", "detail"), path = name)
            val value = scalar(row.get("value"), text(row.get("value_type"), "value_type"))
            val unit = text(row.get("unit"), "unit")
            requireProtocol(unit == when(name) { "capacity", "effective_capacity" -> "GJ"; "neutralizer_resistance" -> "%"; else -> "GJ/s" }, "Incorrect capacitor unit")
            requireProtocol(value.numberOrNull()?.let { name == "delta" || it >= 0 } != false, "Negative capacitor value")
            if (name == "neutralizer_resistance") requireProtocol(value.numberOrNull()?.let { it <= 100 } != false, "Invalid resistance")
            CapacitorScalar(value, unit, label(row.get("display"), value == StatValue.Unavailable), label(row.get("detail"), value == StatValue.Unavailable))
        }
        val state = objectValue(root.get("stability"), "stability")
        keys(state, setOf("kind", "unit", "values", "value_types", "display"), path = "stability")
        val kind = text(state.get("kind"), "kind")
        requireProtocol(kind in setOf("stable", "stable_range", "depletion", "unavailable"), "Invalid capacitor state")
        val unit = text(state.get("unit"), "unit")
        requireProtocol(unit in setOf("%", "s") && (kind == "unavailable" || unit == if (kind == "depletion") "s" else "%"), "Incorrect stability unit")
        val raw = array(state.get("values"), "values"); val types = array(state.get("value_types"), "value_types")
        requireProtocol(raw.size == if (kind == "stable_range") 2 else 1, "Incorrect stability bounds")
        requireProtocol(types.size == raw.size, "Incorrect stability types")
        val bounds = raw.indices.map { scalar(raw[it], text(types[it], "value_types")) }
        requireProtocol(bounds.all { (it == StatValue.Unavailable) == (kind == "unavailable") }, "Incorrect stability availability")
        val numbers = bounds.mapNotNull { it.numberOrNull() }
        requireProtocol(numbers.all { it >= 0 && (kind == "depletion" || it <= 100) }, "Invalid stability bounds")
        requireProtocol(numbers.size != 2 || numbers[0] <= numbers[1], "Reversed stability range")
        return FitCapacitor(identifier(root.get("fit_id"), "fit_id"), revision, Collections.unmodifiableMap(values),
            CapacitorStability(kind, unit, Collections.unmodifiableList(bounds), label(state.get("display"), kind == "unavailable")))
    }

    fun decodeResources(json: String): FitResources {
        val value = objectValue(StrictJson(json).parse(), "resources")
        keys(value, setOf("version", "fit_id", "revision", "resources"), path = "resources")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported resources version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid resource revision")
        val rows = objectValue(value.get("resources"), "resource pairs")
        keys(rows, RESOURCE_LABELS.keys, path = "resource pairs")
        val units = mapOf("calibration" to "points", "cpu" to "tf", "powergrid" to "MW",
            "drone_bay" to "m³", "fighter_bay" to "m³", "cargo_bay" to "m³", "drone_bandwidth" to "Mbit/s")
        val result = RESOURCE_LABELS.keys.associateWith { name ->
            val row = objectValue(rows.get(name), name)
            keys(row, setOf("used", "total", "used_type", "total_type", "unit", "overloaded",
                "used_display", "total_display", "used_detail", "total_detail"), path = name)
            fun number(key: String): StatValue {
                val raw = row.get(key)
                val kind = text(row.get("${key}_type"), "${key}_type")
                return when (kind) {
                    "unavailable" -> { requireProtocol(raw == JSONObject.NULL, "Unavailable resource has a value"); StatValue.Unavailable }
                    "integer" -> StatValue.Integer(long(raw, key))
                    "decimal" -> { requireProtocol(raw is Double, "Decimal resource lost its scalar type"); StatValue.Decimal(finite(raw as Double, key)) }
                    else -> fail("Invalid resource scalar type")
                }
            }
            val used = number("used"); val total = number("total")
            val unit = text(row.get("unit"), "unit")
            requireProtocol(unit == (units[name] ?: "count"), "Incorrect resource unit")
            fun label(key: String, scalar: StatValue): String? {
                val result = nullable(row.get(key))?.let { nonempty(it, key) }
                requireProtocol((result == null) == (scalar == StatValue.Unavailable), "Resource display availability differs")
                return result
            }
            val overloaded = nullable(row.get("overloaded"))?.let { bool(it, "overloaded") }
            val left = used.numberOrNull(); val right = total.numberOrNull()
            requireProtocol(overloaded == if (left == null || right == null) null else left > right,
                "Resource overload differs from raw values")
            ResourceDetails(used, total, unit, overloaded, label("used_display", used), label("total_display", total),
                label("used_detail", used), label("total_detail", total))
        }
        return FitResources(identifier(value.get("fit_id"), "fit_id"), revision, Collections.unmodifiableMap(result))
    }

    fun encodeRequest(request: BridgeRequest): String {
        identifier(request.requestId, "request_id")
        identifier(request.sessionId, "session_id")
        val (name, arguments) = operation(request.operation)
        val namedFits = when {
            arguments.has("fit_id") -> setOf(identifier(arguments.get("fit_id"), "fit_id"))
            arguments.has("source_id") -> setOf(
                identifier(arguments.get("source_id"), "source_id"),
                identifier(arguments.get("target_id"), "target_id"),
            )
            else -> emptySet()
        }
        requireProtocol(request.expectedRevisions.keys == namedFits, "Expected revisions must name exactly the edited fits")
        val revisions = JSONObject()
        for ((id, revision) in request.expectedRevisions) {
            identifier(id, "expected_revisions key")
            requireProtocol(revision >= 0, "Revision must be nonnegative")
            revisions.put(id, revision)
        }
        val envelope = obj("version" to VERSION, "request_id" to request.requestId, "session_id" to request.sessionId,
            "operation" to name, "expected_revisions" to revisions, "arguments" to arguments)
        // JSONObject strips the decimal suffix from integral doubles. EOS uses
        // the profile's numeric types when applying even zero/100% resistance.
        val path = when (val op = request.operation) {
            is BridgeOperation.CreateFit -> if (op.spec.targetProfile != null) listOf("arguments", "spec", "target_profile") else null
            is BridgeOperation.SetTargetProfile -> if (op.profile != null) listOf("arguments", "profile") else null
            else -> null
        }
        return if (path == null) envelope.toString() else encodeProfilePath(envelope, path)
    }

    private fun encodeProfilePath(value: JSONObject, path: List<String>): String =
        value.keys().asSequence().joinToString(",", "{", "}") { key ->
            val item = value.get(key)
            when {
                path.isEmpty() -> {
                    requireProtocol(item == JSONObject.NULL || item is Double, "Invalid profile numeric type")
                    JSONObject.quote(key) + ":" + item.toString()
                }
                key == path.first() -> JSONObject.quote(key) + ":" + encodeProfilePath(value.getJSONObject(key), path.drop(1))
                else -> JSONObject().put(key, item).toString().let { it.substring(1, it.length - 1) }
            }
        }

    fun decodeResponse(json: String): BridgeResponse {
        val value = objectValue(StrictJson(json).parse(), "response")
        keys(value, setOf("version", "request_id", "session_id", "status", "fits", "error"), path = "response")
        requireProtocol(long(value.get("version"), "version") == VERSION.toLong(), "Unsupported response version")
        val requestId = nullable(value.get("request_id"))?.let { identifier(it, "request_id") }
        val sessionId = identifier(value.get("session_id"), "session_id")
        val status = when (text(value.get("status"), "status")) {
            "ok" -> BridgeStatus.OK
            "error" -> BridgeStatus.ERROR
            else -> fail("Unknown response status")
        }
        val fits = array(value.get("fits"), "fits").mapIndexed { index, fit -> decodeFit(fit, "fits[$index]") }
        unique(fits.map { it.id }, "fit IDs")
        val error = nullable(value.get("error"))?.let {
            val details = objectValue(it, "error")
            keys(details, setOf("code", "message"), path = "error")
            BridgeError(enumValue<BridgeErrorCode>(details.get("code"), "error.code"),
                text(details.get("message"), "error.message"))
        }
        requireProtocol((status == BridgeStatus.OK && error == null) ||
            (status == BridgeStatus.ERROR && error != null && fits.isEmpty()), "Inconsistent response status, fits or error")
        requireProtocol(status != BridgeStatus.OK || requestId != null, "Successful response must identify its request")
        return BridgeResponse(requestId, sessionId, status, immutableList(fits), error)
    }

    fun decodeFitSpec(json: String): FitSpec = decodeFitSpec(objectValue(StrictJson(json).parse(), "spec"))

    /** A JSONObject has already lost duplicate-key information. Use String for untrusted JSON. */
    fun decodeFitSpec(value: JSONObject): FitSpec {
        keys(value, setOf("name", "ship", "skill_level", "factor_reload", "damage_pattern", "security",
            "modules", "drones", "target_profile", "implants", "boosters", "projections", "commands", "environments"),
            setOf("mode", "notes", "fighters"), path = "spec")
        val targetProfile = decodeTargetProfile(value.get("target_profile"))
        for (key in listOf("implants", "boosters", "projections", "commands")) {
            requireProtocol(array(value.get(key), "spec.$key").isEmpty(), "Initial $key are unsupported")
        }
        val damage = objectValue(value.get("damage_pattern"), "damage_pattern")
        keys(damage, setOf("emAmount", "thermalAmount", "kineticAmount", "explosiveAmount"), path = "damage_pattern")
        val amounts = listOf("emAmount", "thermalAmount", "kineticAmount", "explosiveAmount")
            .map { number(damage.get(it), "damage_pattern.$it") }
        requireProtocol(amounts.all { it >= 0 } && amounts.sum().isFinite() && amounts.sum() > 0, "Invalid damage pattern")
        val security = objectValue(value.get("security"), "security")
        keys(security, setOf("system", "pilot"), path = "security")
        val pilot = number(security.get("pilot"), "security.pilot")
        requireProtocol(pilot in -10.0..5.0, "Invalid pilot security")
        return FitSpec(
            nonempty(value.get("name"), "spec.name"), nonempty(value.get("ship"), "spec.ship"),
            integer(value.get("skill_level"), "skill_level", 0, 5), bool(value.get("factor_reload"), "factor_reload"),
            DamagePattern(amounts[0], amounts[1], amounts[2], amounts[3]),
            Security(enumValue<SystemSecurity>(security.get("system"), "security.system"), pilot),
            array(value.get("modules"), "modules").mapIndexed { index, entry ->
                val module = objectValue(entry, "modules[$index]")
                keys(module, setOf("name", "state"), setOf("charge", "spool_cycles", "rah_pattern"), "modules[$index]")
                ModuleSpec(nonempty(module.get("name"), "module.name"), enumValue<ModuleState>(module.get("state"), "module.state"),
                    if (module.has("charge")) nullable(module.get("charge"))?.let { nonempty(it, "module.charge") } else null,
                    if (module.has("spool_cycles")) integer(module.get("spool_cycles"), "module.spool_cycles", 0) else null,
                    if (module.has("rah_pattern")) ModuleRahCodec.pattern(module.get("rah_pattern")) else null)
            },
            array(value.get("drones"), "drones").mapIndexed { index, entry ->
                val drone = objectValue(entry, "drones[$index]")
                keys(drone, setOf("name", "amount", "active"), path = "drones[$index]")
                val amount = integer(drone.get("amount"), "drone.amount", 1)
                DroneSpec(nonempty(drone.get("name"), "drone.name"), amount,
                    integer(drone.get("active"), "drone.active", 0, amount))
            },
            if (value.has("mode")) integer(value.get("mode"), "spec.mode", 1) else null,
            if (value.has("notes")) noteText(value.get("notes")) else null,
            targetProfile,
            if (value.has("fighters")) array(value.get("fighters"), "fighters").map { raw ->
                val row = objectValue(raw, "fighter"); keys(row, setOf("name", "amount", "active"), setOf("abilities"), path = "fighter")
                val abilities = if (row.has("abilities")) array(row.get("abilities"), "fighter.abilities").map { abilityRaw ->
                    val ability = objectValue(abilityRaw, "ability"); keys(ability, setOf("effect_id", "active"), path = "ability")
                    FighterAbilityState(integer(ability.get("effect_id"), "effect_id", 1), bool(ability.get("active"), "active"))
                }.also {
                    val ids = it.map { ability -> ability.effectId }
                    requireProtocol(it.size <= 128 && ids == ids.sorted(), "Fighter abilities must be sorted by effect ID")
                    unique(ids, "fighter abilities")
                } else null
                FighterSpec(nonempty(row.get("name"), "name"), integer(row.get("amount"), "amount", 0), bool(row.get("active"), "active"),
                    abilities?.let(::immutableList))
            } else emptyList(),
            array(value.get("environments"), "environments").map { raw ->
                val row = objectValue(raw, "environment"); keys(row, setOf("name", "state"), path = "environment")
                val name = text(row.get("name"), "name"); val state = enumValue<ModuleState>(row.get("state"), "state")
                requireProtocol(name in (1..6).map { "Class $it Red Giant Effects" } && state in listOf(ModuleState.ONLINE, ModuleState.OFFLINE), "Invalid bomb environment")
                EnvironmentSpec(name, state)
            }.also { rows -> unique(rows.map { it.name }, "environment names") },
        )
    }

    fun encodeFitSpec(spec: FitSpec): JSONObject {
        val value = obj(
            "name" to spec.name, "ship" to spec.ship, "skill_level" to spec.skillLevel,
            "factor_reload" to spec.factorReload,
            "damage_pattern" to obj("emAmount" to finite(spec.damagePattern.emAmount, "emAmount"),
                "thermalAmount" to finite(spec.damagePattern.thermalAmount, "thermalAmount"),
                "kineticAmount" to finite(spec.damagePattern.kineticAmount, "kineticAmount"),
                "explosiveAmount" to finite(spec.damagePattern.explosiveAmount, "explosiveAmount")),
            "security" to obj("system" to spec.security.system.name, "pilot" to finite(spec.security.pilot, "pilot")),
            "modules" to jsonArray(spec.modules.map { module ->
                obj("name" to module.name, "state" to module.state.name, "charge" to module.charge).also { row ->
                    module.spoolCycles?.let { row.put("spool_cycles", integer(it, "module.spool_cycles", 0)) }
                    module.rahPattern?.let { row.put("rah_pattern", ModuleRahCodec.encodePattern(it)) }
                }
            }),
            "drones" to jsonArray(spec.drones.map { obj("name" to it.name, "amount" to it.amount, "active" to it.active) }),
            "target_profile" to encodeTargetProfile(spec.targetProfile), "implants" to JSONArray(), "boosters" to JSONArray(),
            "projections" to JSONArray(), "commands" to JSONArray(), "environments" to jsonArray(spec.environments.map { obj("name" to it.name, "state" to it.state.name) }),
        )
        if (spec.fighters.isNotEmpty()) value.put("fighters", jsonArray(spec.fighters.map { fighter ->
            obj("name" to fighter.name, "amount" to fighter.amount, "active" to fighter.active).also { row ->
                fighter.abilities?.let { abilities -> row.put("abilities", jsonArray(abilities.map {
                    obj("effect_id" to it.effectId, "active" to it.active)
                })) }
            }
        }))
        spec.modeId?.let { value.put("mode", integer(it, "spec.mode", 1)) }
        spec.notes?.let { value.put("notes", noteText(it)) }
        decodeFitSpec(value) // Keep construction and fixture decoding subject to the same shape checks.
        return value
    }

    private fun projectedModuleArguments(fitId: String, position: Int, objectKey: String): JSONObject {
        requireProtocol(objectKey.matches(Regex("[0-9a-f]{32}")), "Invalid projected object identity")
        return obj("fit_id" to fitId, "position" to integer(position, "position", 0), "object_key" to objectKey)
    }

    private fun projectedModuleSelection(fitId: String, selection: List<ProjectedModuleSelectionRow>): JSONObject {
        requireProtocol(selection.size in 1..1024, "Select between one and 1024 projected modules")
        unique(selection.map { it.position }, "projected module positions")
        unique(selection.map { it.objectKey }, "projected module identities")
        val rows = JSONArray()
        selection.forEach { row ->
            requireProtocol(row.objectKey.matches(Regex("[0-9a-f]{32}")), "Invalid projected object identity")
            rows.put(obj("position" to integer(row.position, "position", 0), "object_key" to row.objectKey))
        }
        return obj("fit_id" to fitId, "selection" to rows)
    }

    private fun projectedDroneSelection(fitId: String, selection: List<ProjectedDroneSelectionRow>): JSONObject {
        requireProtocol(selection.size in 1..1024, "Select between one and 1024 projected drone stacks")
        unique(selection.map { it.position }, "projected drone positions")
        unique(selection.map { it.objectKey }, "projected drone identities")
        val rows = JSONArray()
        selection.forEach { row ->
            requireProtocol(row.objectKey.matches(Regex("[0-9a-f]{32}")), "Invalid projected object identity")
            rows.put(obj("position" to integer(row.position, "position", 0), "object_key" to row.objectKey))
        }
        return obj("fit_id" to fitId, "selection" to rows)
    }

    private fun projectedFighterSelection(fitId: String, selection: List<ProjectedFighterSelectionRow>): JSONObject {
        requireProtocol(selection.size in 1..1024, "Select between one and 1024 projected fighter squadrons")
        unique(selection.map { it.position }, "projected fighter positions")
        unique(selection.map { it.objectKey }, "projected fighter identities")
        val rows = JSONArray()
        selection.forEach { row ->
            requireProtocol(row.objectKey.matches(Regex("[0-9a-f]{32}")), "Invalid projected object identity")
            rows.put(obj("position" to integer(row.position, "position", 0), "object_key" to row.objectKey))
        }
        return obj("fit_id" to fitId, "selection" to rows)
    }

    private fun projectedFighterMain(main: ProjectedFighterSelectionRow, selection: List<ProjectedFighterSelectionRow>): JSONObject {
        // The original helper appends main when absent; contradictory identities never qualify.
        val combined = if (main in selection) selection else selection + main
        projectedFighterSelection("", combined)
        return obj("position" to main.position, "object_key" to main.objectKey)
    }

    private fun operation(operation: BridgeOperation): Pair<String, JSONObject> = when (operation) {
        is BridgeOperation.Snapshot -> {
            operation.fitIds.forEach { identifier(it, "fit_ids") }
            unique(operation.fitIds, "fit_ids")
            "snapshot" to obj("fit_ids" to jsonArray(operation.fitIds))
        }
        is BridgeOperation.RenameFit -> "rename_fit" to obj("fit_id" to operation.fitId, "name" to fitName(operation.name))
        is BridgeOperation.SetNotes -> "set_notes" to obj("fit_id" to operation.fitId, "text" to noteText(operation.text))
        is BridgeOperation.SetTargetProfile -> {
            "set_target_profile" to obj("fit_id" to operation.fitId, "profile" to encodeTargetProfile(operation.profile))
        }
        is BridgeOperation.SetDamagePattern -> {
            val p = operation.pattern
            val values = listOf(p.emAmount, p.thermalAmount, p.kineticAmount, p.explosiveAmount)
            requireProtocol(values.all { it.isFinite() && it >= 0 } && values.sum().let { it.isFinite() && it > 0 }, "Invalid incoming damage")
            "set_damage_pattern" to obj("fit_id" to operation.fitId, "pattern" to obj("emAmount" to p.emAmount,
                "thermalAmount" to p.thermalAmount, "kineticAmount" to p.kineticAmount, "explosiveAmount" to p.explosiveAmount))
        }
        is BridgeOperation.Undo -> "undo" to obj("fit_id" to operation.fitId)
        is BridgeOperation.Redo -> "redo" to obj("fit_id" to operation.fitId)
        is BridgeOperation.DuplicateFit -> "duplicate_fit" to obj("fit_id" to operation.fitId, "name" to fitName(operation.name))
        is BridgeOperation.DeleteFit -> "delete_fit" to obj("fit_id" to operation.fitId, "resolve_references" to operation.resolveReferences)
        is BridgeOperation.SetProjectedDronesActive -> "set_projected_drones_active" to projectedDroneSelection(
            operation.fitId, operation.selection).put("active", operation.active)
        is BridgeOperation.SetProjectedDroneRanges -> "set_projected_drone_ranges" to projectedDroneSelection(
            operation.fitId, operation.selection).put("range_m", operation.rangeM?.also {
                requireProtocol(it.isFinite() && it >= 0, "Invalid projected range") } ?: JSONObject.NULL)
        is BridgeOperation.RemoveProjectedDrones -> "remove_projected_drones" to projectedDroneSelection(operation.fitId, operation.selection)
        is BridgeOperation.SetProjectedFightersActive -> "set_projected_fighters_active" to projectedFighterSelection(
            operation.fitId, operation.selection).put("active", operation.active)
        is BridgeOperation.SetProjectedFighterRanges -> "set_projected_fighter_ranges" to projectedFighterSelection(
            operation.fitId, operation.selection).put("range_m", operation.rangeM?.also {
                requireProtocol(it.isFinite() && it >= 0, "Invalid projected range") } ?: JSONObject.NULL)
        is BridgeOperation.RemoveProjectedFighters -> "remove_projected_fighters" to projectedFighterSelection(operation.fitId, operation.selection)
        is BridgeOperation.ToggleProjectedFighterAbilities -> "toggle_projected_fighter_abilities" to projectedFighterSelection(
            operation.fitId, operation.selection).put("main", projectedFighterMain(operation.main, operation.selection))
            .put("effect_id", operation.effectId.also { requireProtocol(it > 0, "Invalid projected ability") })
        is BridgeOperation.AddProjectedFighter -> "add_projected_fighter" to obj("fit_id" to operation.fitId,
            "item_id" to operation.itemId.also { requireProtocol(it > 0, "Invalid projected item") })
        is BridgeOperation.SetProjectedFighterAmount -> "set_projected_fighter_amount" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("amount", operation.amount.also { requireProtocol(it >= 0, "Invalid projected quantity") })
        is BridgeOperation.SetProjectedFighterActive -> "set_projected_fighter_active" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("active", operation.active)
        is BridgeOperation.SetProjectedFighterRange -> "set_projected_fighter_range" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("range_m", operation.rangeM?.also {
                requireProtocol(it.isFinite() && it >= 0, "Invalid projected range") } ?: JSONObject.NULL)
        is BridgeOperation.ChangeProjectedFighterVariation -> "change_projected_fighter_variation" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("item_id", operation.itemId.also { requireProtocol(it > 0, "Invalid projected item") })
        is BridgeOperation.RemoveProjectedFighter -> "remove_projected_fighter" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey)
        is BridgeOperation.ToggleProjectedFighterAbility -> "toggle_projected_fighter_ability" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("effect_id", operation.effectId.also { requireProtocol(it > 0, "Invalid fighter ability") })
        is BridgeOperation.AddProjectedDrone -> "add_projected_drone" to obj("fit_id" to operation.fitId,
            "item_id" to operation.itemId.also { requireProtocol(it > 0, "Invalid projected item") })
        is BridgeOperation.SetProjectedDroneAmount -> "set_projected_drone_amount" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("amount", operation.amount.also { requireProtocol(it >= 0, "Invalid projected quantity") })
        is BridgeOperation.SetProjectedDroneActive -> "set_projected_drone_active" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("active", operation.active)
        is BridgeOperation.SetProjectedDroneRange -> "set_projected_drone_range" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("range_m", operation.rangeM?.also {
                requireProtocol(it.isFinite() && it >= 0, "Invalid projected range") } ?: JSONObject.NULL)
        is BridgeOperation.ChangeProjectedDroneVariation -> "change_projected_drone_variation" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("item_id", operation.itemId.also { requireProtocol(it > 0, "Invalid projected item") })
        is BridgeOperation.RemoveProjectedDrone -> "remove_projected_drone" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("amount", operation.amount.also { requireProtocol(it > 0, "Invalid projected removal quantity") })
        is BridgeOperation.SetProjectedModuleCharges -> "set_projected_module_charges" to
            ProjectedModuleChargeCodec.request(operation.main, operation.selection, operation.scope, operation.chargeId)
                .put("fit_id", operation.fitId).put("expected_targets", ProjectedModuleChargeCodec.wireRows(operation.expectedTargets))
                .put("expected_changes", ProjectedModuleChargeCodec.wireRows(operation.expectedChanges, allowEmpty = true)).also {
                    requireProtocol(operation.main in operation.expectedTargets, "Charge main must be a target")
                    requireProtocol(operation.expectedTargets.zipWithNext().all { (a,b) -> a.position < b.position } &&
                        operation.expectedChanges == operation.expectedTargets.filter { it in operation.expectedChanges }, "Charge preview order differs")
                }
        is BridgeOperation.SetProjectedModuleStates -> "set_projected_module_states" to projectedModuleSelection(
            operation.fitId, operation.selection).put("state", operation.state.wire)
        is BridgeOperation.SetProjectedModuleRanges -> "set_projected_module_ranges" to projectedModuleSelection(
            operation.fitId, operation.selection).put("range_m", operation.rangeM?.also {
                requireProtocol(it.isFinite() && it >= 0, "Invalid projected range") } ?: JSONObject.NULL)
        is BridgeOperation.RemoveProjectedModules -> "remove_projected_modules" to projectedModuleSelection(operation.fitId, operation.selection)
        is BridgeOperation.AddProjectedModule -> "add_projected_module" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.SetProjectedModuleState -> "set_projected_module_state" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("state", operation.state.wire)
        is BridgeOperation.SetProjectedModuleCharge -> "set_projected_module_charge" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("charge_id", operation.chargeId?.let { integer(it, "charge_id", 1) } ?: JSONObject.NULL)
        is BridgeOperation.ChangeProjectedModuleVariation -> "change_projected_module_variation" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("item_id", integer(operation.itemId, "item_id", 1))
        is BridgeOperation.SetProjectedModuleRange -> "set_projected_module_range" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("range_m", operation.rangeM?.also {
                requireProtocol(it.isFinite() && it >= 0, "Invalid projected range") } ?: JSONObject.NULL)
        is BridgeOperation.SetProjectedModuleSpool -> "set_projected_module_spool" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey).put("cycles", operation.cycles?.let { integer(it, "cycles", 0) } ?: JSONObject.NULL)
        is BridgeOperation.RemoveProjectedModule -> "remove_projected_module" to projectedModuleArguments(
            operation.fitId, operation.position, operation.objectKey)
        is BridgeOperation.AddModule -> "add_module" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.ReplaceModule -> "replace_module" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0), "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.RemoveModule -> "remove_module" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0))
        is BridgeOperation.SetCargoQuantities -> "set_cargo_quantities" to obj("fit_id" to operation.fitId,
            "item_ids" to cargoIds(operation.itemIds), "quantity" to operation.quantity.also {
                requireProtocol(it >= 0, "Cargo quantity must not be negative") })
        is BridgeOperation.RemoveCargos -> "remove_cargos" to obj("fit_id" to operation.fitId,
            "item_ids" to cargoIds(operation.itemIds))
        is BridgeOperation.AddCargoPreset -> "add_cargo_preset" to obj("fit_id" to operation.fitId,
            "item_id" to operation.itemId.also { requireProtocol(it > 0, "Invalid cargo item") })
        is BridgeOperation.FillCargo -> "fill_cargo" to obj("fit_id" to operation.fitId,
            "item_id" to operation.itemId.also { requireProtocol(it > 0, "Invalid cargo item") },
            "from_cargo" to operation.fromCargo)
        is BridgeOperation.ChangeCargoVariations -> "change_cargo_variations" to obj("fit_id" to operation.fitId,
            "main_item_id" to operation.mainItemId.also {
                requireProtocol(it in operation.itemIds, "Select the main cargo stack") },
            "item_ids" to cargoIds(operation.itemIds),
            "item_id" to operation.itemId.also { requireProtocol(it > 0, "Invalid cargo variation") })
        is BridgeOperation.TransferCargo -> "transfer_cargo" to obj("fit_id" to operation.fitId,
            "direction" to operation.direction.name, "positions" to JSONArray(operation.positions.also {
                requireProtocol(it.isNotEmpty() && it.all { index -> index >= 0 }, "Choose fitting positions")
                unique(it, "transfer positions")
                requireProtocol(operation.direction != CargoTransferDirection.FROM_CARGO ||
                    it.size == 1 && operation.itemId != null, "Choose one cargo fitting destination")
            }), "item_id" to operation.itemId?.also { requireProtocol(it > 0, "Invalid cargo item") },
            "copy" to operation.copy)
        is BridgeOperation.AddFighter -> "add_fighter" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.SetFighterAmount -> "set_fighter_amount" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0), "amount" to integer(operation.amount, "amount", 0))
        is BridgeOperation.RemoveFighters -> "remove_fighters" to obj("fit_id" to operation.fitId,
            "positions" to fighterPositions(operation.positions, required = true))
        is BridgeOperation.ToggleFighters -> "toggle_fighters" to obj("fit_id" to operation.fitId,
            "main_position" to integer(operation.mainPosition, "main_position", 0), "positions" to fighterPositions(operation.positions))
        is BridgeOperation.ToggleFighterAbility -> "toggle_fighter_ability" to obj("fit_id" to operation.fitId,
            "main_position" to integer(operation.mainPosition, "main_position", 0), "positions" to fighterPositions(operation.positions),
            "effect_id" to integer(operation.effectId, "effect_id", 1))
        is BridgeOperation.ChangeFighterVariations -> "change_fighter_variations" to obj("fit_id" to operation.fitId,
            "main_position" to integer(operation.mainPosition, "main_position", 0), "positions" to fighterPositions(operation.positions),
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.AddDrone -> "add_drone" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1), "amount" to integer(operation.amount, "amount", 1))
        is BridgeOperation.AddDroneStack -> "add_drone_stack" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.SetDroneAmount -> "set_drone_amount" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0), "amount" to integer(operation.amount, "amount", 0))
        is BridgeOperation.RemoveDrones -> "remove_drones" to obj("fit_id" to operation.fitId,
            "positions" to JSONArray(operation.positions.also {
                requireProtocol(it.isNotEmpty() && it.all { position -> position >= 0 }, "Choose drone stacks")
                unique(it, "drone positions")
            }), "amount" to integer(operation.amount, "amount", 1))
        is BridgeOperation.ToggleDrones -> "toggle_drones" to obj("fit_id" to operation.fitId,
            "main_position" to integer(operation.mainPosition, "main_position", 0),
            "positions" to JSONArray(operation.positions.also {
                requireProtocol(it.all { position -> position >= 0 }, "Choose drone stacks")
                unique(it, "drone positions")
            }))
        is BridgeOperation.CloneDrone -> "clone_drone" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0))
        is BridgeOperation.SplitDrone -> "split_drone" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0), "amount" to integer(operation.amount, "amount", 1))
        is BridgeOperation.MergeDrones -> "merge_drones" to obj("fit_id" to operation.fitId,
            "source_position" to integer(operation.sourcePosition, "source_position", 0),
            "destination_position" to integer(operation.destinationPosition, "destination_position", 0))
        is BridgeOperation.AddCargo -> "add_cargo" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1),
            "quantity" to operation.quantity.also { requireProtocol(it > 0, "Cargo quantity must be positive") })
        is BridgeOperation.SetCargoQuantity -> "set_cargo_quantity" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1),
            "quantity" to operation.quantity.also { requireProtocol(it > 0, "Cargo quantity must be positive") })
        is BridgeOperation.RemoveCargo -> "remove_cargo" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1),
            "quantity" to operation.quantity.also { requireProtocol(it > 0, "Cargo quantity must be positive") })
        is BridgeOperation.SetFitRestrictions -> "set_fit_restrictions" to obj("fit_id" to operation.fitId, "ignore" to operation.ignore)
        is BridgeOperation.ChangeMode -> "change_mode" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.SetSubsystem -> {
            requireProtocol(operation.kind in 125..128, "Unknown subsystem type")
            "set_subsystem" to obj("fit_id" to operation.fitId, "kind" to operation.kind,
                "item_id" to operation.itemId?.let { integer(it, "item_id", 1) })
        }
        is BridgeOperation.CreateFit -> "create_fit" to obj("spec" to encodeFitSpec(operation.spec))
        is BridgeOperation.SetCharges -> "set_charges" to obj("fit_id" to operation.fitId,
            "module_indices" to indices(operation.moduleIndices), "charge" to operation.charge?.let { nonempty(it, "charge") })
        is BridgeOperation.SetModuleRah -> "set_module_rah" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0), "mode" to operation.mode.wire).also { row ->
                requireProtocol(operation.mode != RahMode.NAMED, "Named RAH requires the guarded damage route")
                requireProtocol((operation.mode == RahMode.BUILTIN) == (operation.patternId != null), "Invalid RAH pattern applicability")
                operation.patternId?.let { row.put("pattern_id", integer(it, "pattern_id", Int.MIN_VALUE, -1)) }
            }
        is BridgeOperation.SetModuleSpool -> "set_module_spool" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0),
            "cycles" to operation.cycles?.let { integer(it, "cycles", 0) })
        is BridgeOperation.SetMutationAttributes -> {
            requireProtocol(operation.kind in setOf("module", "drone"), "Invalid mutation kind")
            requireProtocol(operation.objectKey.matches(Regex("[0-9a-f]{32}")), "Invalid mutation identity")
            requireProtocol(operation.attributes.isNotEmpty() && operation.attributes.zipWithNext().all { (a, b) -> a.attributeId < b.attributeId },
                "Complete ordered roll set required")
            "set_mutation_attributes" to obj("fit_id" to operation.fitId, "kind" to operation.kind,
                "position" to integer(operation.position, "position", 0), "object_key" to operation.objectKey,
                "attributes" to JSONArray().also { rows -> operation.attributes.forEach { roll ->
                    rows.put(obj("attribute_id" to integer(roll.attributeId, "attribute_id", 1), "value" to finite(roll.value, "value")))
                } })
        }
        is BridgeOperation.SetMutationDisplayAttributes -> {
            requireProtocol(operation.kind in setOf("module", "drone"), "Invalid mutation kind")
            requireProtocol(operation.objectKey.matches(Regex("[0-9a-f]{32}")), "Invalid mutation identity")
            requireProtocol(operation.edits.isNotEmpty() && operation.edits.zipWithNext().all { (a, b) -> a.attributeId < b.attributeId },
                "Nonempty unique ordered mutation edits required")
            "set_mutation_display_attributes" to obj("fit_id" to operation.fitId, "kind" to operation.kind,
                "position" to integer(operation.position, "position", 0), "object_key" to operation.objectKey,
                "edits" to JSONArray().also { rows -> operation.edits.forEach { edit ->
                    rows.put(obj("attribute_id" to integer(edit.attributeId, "attribute_id", 1),
                        "value" to finite(edit.value, "value"), "representation" to edit.representation.wire))
                } })
        }
        is BridgeOperation.SetModuleCharge -> "set_module_charge" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0),
            "charge_id" to operation.chargeId?.let { integer(it, "charge_id", 1) })
        is BridgeOperation.ChangeVariation -> "change_variation" to obj("fit_id" to operation.fitId,
            "context" to operation.context.wire, "position" to integer(operation.position, "position", 0),
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.ChangeBulkVariations -> "change_bulk_variations" to obj("fit_id" to operation.fitId,
            "main_position" to integer(operation.mainPosition, "main_position", 0),
            "module_indices" to indices(operation.moduleIndices), "scope" to operation.scope.name,
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.RemoveBulkModules -> "remove_bulk_modules" to obj("fit_id" to operation.fitId,
            "main_position" to integer(operation.mainPosition, "main_position", 0),
            "module_indices" to indices(operation.moduleIndices), "scope" to operation.scope.name)
        is BridgeOperation.SetBulkCharges -> "set_bulk_charges" to obj("fit_id" to operation.fitId,
            "main_position" to integer(operation.mainPosition, "main_position", 0),
            "module_indices" to indices(operation.moduleIndices), "scope" to operation.scope.name,
            "charge_id" to operation.chargeId?.let { integer(it, "charge_id", 1) })
        is BridgeOperation.SetBulkStates -> "set_bulk_states" to obj("fit_id" to operation.fitId,
            "main_position" to integer(operation.mainPosition, "main_position", 0),
            "module_indices" to indices(operation.moduleIndices), "scope" to operation.scope.name,
            "click" to operation.click.wire)
        is BridgeOperation.FillModulesItem -> "fill_modules_item" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.FillModulesClone -> "fill_modules_clone" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0))
        is BridgeOperation.CloneSelectedModules -> "clone_selected_modules" to obj("fit_id" to operation.fitId,
            "module_indices" to indices(operation.moduleIndices))
        is BridgeOperation.CloneModuleAt -> "clone_module_at" to obj("fit_id" to operation.fitId,
            "source_position" to integer(operation.sourcePosition, "source_position", 0),
            "destination_position" to integer(operation.destinationPosition, "destination_position", 0))
        is BridgeOperation.SwapModules -> "swap_modules" to obj("fit_id" to operation.fitId,
            "from_position" to integer(operation.fromPosition, "from_position", 0),
            "to_position" to integer(operation.toPosition, "to_position", 0))
        is BridgeOperation.SetModuleStates -> "set_module_states" to obj("fit_id" to operation.fitId,
            "module_indices" to indices(operation.moduleIndices), "state" to operation.state.name)
        is BridgeOperation.SetSkillLevel -> "set_skill_level" to obj("fit_id" to operation.fitId,
            "skill" to nonempty(operation.skill, "skill"), "level" to integer(operation.level, "level", 0, 5))
        is BridgeOperation.SetSystemSecurity -> "set_system_security" to obj("fit_id" to operation.fitId, "system" to operation.system.name)
        is BridgeOperation.AddImplant -> "add_implant" to obj("fit_id" to operation.fitId,
            "implant" to nonempty(operation.implant, "implant"), "active" to operation.active)
        is BridgeOperation.SetImplantActive -> "set_implant_active" to obj("fit_id" to operation.fitId,
            "slot" to integer(operation.slot, "slot", 1), "active" to operation.active)
        is BridgeOperation.RemoveImplant -> "remove_implant" to obj("fit_id" to operation.fitId,
            "slot" to integer(operation.slot, "slot", 1))
        is BridgeOperation.FitImplant -> "fit_implant" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.ToggleImplants -> "toggle_implants" to obj("fit_id" to operation.fitId,
            "main_position" to integer(operation.mainPosition, "main_position", 0), "positions" to implantPositions(operation.positions))
        is BridgeOperation.RemoveImplants -> "remove_implants" to obj("fit_id" to operation.fitId,
            "positions" to implantPositions(operation.positions, required = true))
        is BridgeOperation.FitBooster -> "fit_booster" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.ToggleBoosters -> "toggle_boosters" to obj("fit_id" to operation.fitId,
            "main_position" to integer(operation.mainPosition, "main_position", 0), "positions" to boosterPositions(operation.positions))
        is BridgeOperation.RemoveBoosters -> "remove_boosters" to obj("fit_id" to operation.fitId,
            "positions" to boosterPositions(operation.positions, required = true))
        is BridgeOperation.ChangeBoosterVariation -> "change_booster_variation" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0), "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.AddBooster -> "add_booster" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1), "active" to operation.active)
        is BridgeOperation.SetBoosterActive -> "set_booster_active" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0), "active" to operation.active)
        is BridgeOperation.SetBoosterSideEffect -> "set_booster_side_effect" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0),
            "effect_id" to integer(operation.effectId, "effect_id", 1), "active" to operation.active)
        is BridgeOperation.RemoveBooster -> "remove_booster" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0))
        is BridgeOperation.AddProjection -> "add_projection" to projectionArguments(
            operation.sourceId, operation.targetId, operation.rangeM, operation.active, operation.amount)
        is BridgeOperation.ConfigureProjection -> "configure_projection" to projectionArguments(
            operation.sourceId, operation.targetId, operation.rangeM, operation.active, operation.amount)
        is BridgeOperation.RemoveProjection -> "remove_projection" to endpoints(operation.sourceId, operation.targetId)
        is BridgeOperation.AddProjectedFit -> "add_projected_fit" to endpoints(operation.sourceId, operation.targetId)
        is BridgeOperation.SetProjectedFitAmount -> "set_projected_fit_amount" to endpoints(operation.sourceId, operation.targetId)
            .put("amount", integer(operation.amount, "amount", 0))
        is BridgeOperation.SetProjectedFitRange -> {
            operation.rangeM?.let { requireProtocol(finite(it, "range_m") >= 0, "Negative projection range") }
            "set_projected_fit_range" to endpoints(operation.sourceId, operation.targetId)
                .put("range_m", operation.rangeM ?: JSONObject.NULL)
        }
        is BridgeOperation.SetProjectedFitActive -> "set_projected_fit_active" to endpoints(operation.sourceId, operation.targetId)
            .put("active", operation.active)
        is BridgeOperation.RemoveProjectedFit -> "remove_projected_fit" to endpoints(operation.sourceId, operation.targetId)
        is BridgeOperation.AddCommandFit -> "add_command_fit" to endpoints(operation.sourceId, operation.targetId)
        is BridgeOperation.SetCommandFitActive -> "set_command_fit_active" to endpoints(operation.sourceId, operation.targetId).put("active", operation.active)
        is BridgeOperation.RemoveCommandFit -> "remove_command_fit" to endpoints(operation.sourceId, operation.targetId)
        is BridgeOperation.AddCommand -> "add_command" to endpoints(operation.sourceId, operation.targetId).put("active", operation.active)
        is BridgeOperation.SetCommandActive -> "set_command_active" to endpoints(operation.sourceId, operation.targetId).put("active", operation.active)
        is BridgeOperation.RemoveCommand -> "remove_command" to endpoints(operation.sourceId, operation.targetId)
    }

    private fun fitName(name: String): String = name.also {
        requireProtocol(it.isNotBlank() && it.codePointCount(0, it.length) <= 200 && it.none { c -> c.code < 32 },
            "Fit names must contain 1–200 characters without control characters")
    }

    private fun projectionArguments(source: String, target: String, range: Double?, active: Boolean, amount: Int): JSONObject {
        if (range != null) requireProtocol(finite(range, "range_m") >= 0, "Negative projection range")
        return endpoints(source, target).put("range_m", range ?: JSONObject.NULL)
            .put("active", active).put("amount", integer(amount, "amount", 1))
    }

    private fun endpoints(source: String, target: String) = obj("source_id" to source, "target_id" to target)

    private fun implantPositions(values: List<Int>, required: Boolean = false): JSONArray {
        requireProtocol(!required || values.isNotEmpty(), "Choose implants")
        requireProtocol(values.size <= 1024, "Select at most 1024 implants")
        values.forEach { integer(it, "implant position", 0) }
        unique(values, "implant positions")
        return jsonArray(values)
    }

    private fun boosterPositions(values: List<Int>, required: Boolean = false): JSONArray {
        requireProtocol(!required || values.isNotEmpty(), "Choose boosters")
        requireProtocol(values.size <= 1024, "Select at most 1024 boosters")
        values.forEach { integer(it, "booster position", 0) }
        unique(values, "booster positions")
        return jsonArray(values)
    }

    private fun fighterPositions(values: List<Int>, required: Boolean = false): JSONArray {
        requireProtocol(!required || values.isNotEmpty(), "Choose fighter squadrons")
        requireProtocol(values.size <= 1024, "Select at most 1024 fighter squadrons")
        values.forEach { integer(it, "fighter position", 0) }
        unique(values, "fighter positions")
        return jsonArray(values)
    }

    private fun indices(values: List<Int>): JSONArray {
        requireProtocol(values.isNotEmpty(), "Select at least one module")
        values.forEach { integer(it, "module index", 0) }
        unique(values, "module_indices")
        return jsonArray(values)
    }

    private fun decodeFit(raw: Any, path: String): FitSnapshot {
        val value = objectValue(raw, path)
        keys(value, setOf("id", "revision", "name", "ship", "stats", "modules", "skills", "implants", "projections", "commands"), path = path)
        val revision = long(value.get("revision"), "$path.revision")
        requireProtocol(revision >= 1, "Fit revision must be positive")
        val stats = objectValue(value.get("stats"), "$path.stats")
        keys(stats, STAT_NAMES, path = "$path.stats")
        val decodedStats = stats.keys().asSequence().associateWith { name ->
            val stat = objectValue(stats.get(name), "$path.stats.$name")
            keys(stat, setOf("value", "unit"), path = "$path.stats.$name")
            val scalar = when (val item = stat.get("value")) {
                JSONObject.NULL -> StatValue.Unavailable
                is Int -> StatValue.Integer(item.toLong())
                is Long -> StatValue.Integer(item)
                is Double -> StatValue.Decimal(finite(item, "$path.stats.$name.value"))
                is Boolean -> StatValue.BooleanValue(item)
                is String -> StatValue.Text(item)
                else -> fail("$path.stats.$name.value must be a scalar or explicit null")
            }
            Stat(scalar, text(stat.get("unit"), "$path.stats.$name.unit"))
        }
        val modules = array(value.get("modules"), "$path.modules").mapIndexed { index, entry ->
            val module = objectValue(entry, "$path.modules[$index]")
            val position = integer(module.get("index"), "module.index", 0)
            requireProtocol(position == index, "Module indices must match their array positions")
            if (module.has("empty_slot")) {
                keys(module, setOf("index", "empty_slot"), path = "$path.modules[$index]")
                ModuleSnapshot(position, null, null, null, enumValue<ModuleSlot>(module.get("empty_slot"), "module.empty_slot"))
            } else {
                keys(module, setOf("index", "name", "charge", "state"), path = "$path.modules[$index]")
                ModuleSnapshot(position, nonempty(module.get("name"), "module.name"),
                    nullable(module.get("charge"))?.let { nonempty(it, "module.charge") },
                    enumValue<ModuleState>(module.get("state"), "module.state"))
            }
        }
        val skillObject = objectValue(value.get("skills"), "$path.skills")
        val skills = skillObject.keys().asSequence().associateWith { name ->
            nonempty(name, "skill name")
            nullable(skillObject.get(name))?.let { integer(it, "skill level", 0, 5) }
        }
        val implants = array(value.get("implants"), "$path.implants").map { entry ->
            val implant = objectValue(entry, "implant")
            keys(implant, setOf("name", "slot", "active"), path = "implant")
            ImplantSnapshot(nonempty(implant.get("name"), "implant.name"), integer(implant.get("slot"), "implant.slot", 1),
                bool(implant.get("active"), "implant.active"))
        }
        unique(implants.map { it.slot }, "implant slots")
        val projections = array(value.get("projections"), "$path.projections").map { entry ->
            val link = objectValue(entry, "projection")
            keys(link, setOf("source_id", "range_m", "active", "amount"), path = "projection")
            val range = nullable(link.get("range_m"))?.let { number(it, "projection.range_m") }
            requireProtocol(range == null || range >= 0, "Negative projection range")
            ProjectionSnapshot(identifier(link.get("source_id"), "projection.source_id"), range,
                bool(link.get("active"), "projection.active"), integer(link.get("amount"), "projection.amount", 1))
        }
        unique(projections.map { it.sourceId }, "projection source IDs")
        val commands = array(value.get("commands"), "$path.commands").map { entry ->
            val link = objectValue(entry, "command")
            keys(link, setOf("source_id", "active"), path = "command")
            CommandSnapshot(identifier(link.get("source_id"), "command.source_id"), bool(link.get("active"), "command.active"))
        }
        unique(commands.map { it.sourceId }, "command source IDs")
        return FitSnapshot(identifier(value.get("id"), "$path.id"), revision,
            nonempty(value.get("name"), "$path.name"), nonempty(value.get("ship"), "$path.ship"),
            immutableMap(decodedStats), immutableList(modules), immutableMap(skills), immutableList(implants),
            immutableList(projections), immutableList(commands))
    }

    fun decodeRecent(json: String): List<Int> {
        val value = objectValue(StrictJson(json).parse(), "recent")
        keys(value, setOf("version", "item_ids"), path = "recent")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported recent-use version")
        val ids = array(value.get("item_ids"), "item_ids").map { integer(it, "item_id", 1) }
        requireProtocol(ids.size <= 20, "Recent-use list exceeds 20 items")
        unique(ids, "recent IDs")
        return immutableList(ids)
    }

    fun decodeModuleDefaults(json: String): List<ModuleDefault> {
        val rows = array(StrictJson(json).parse(), "module_defaults").map { entry ->
            val row = objectValue(entry, "module_default")
            keys(row, setOf("id", "name", "slot", "state", "limit"), path = "module_default")
            ModuleDefault(integer(row.get("id"), "item_id", 1), nonempty(row.get("name"), "name"),
                enumValue<ModuleSlot>(row.get("slot"), "slot"), enumValue<ModuleState>(row.get("state"), "state"),
                enumValue<ModuleState>(row.get("limit"), "limit"))
        }
        unique(rows.map { it.id }, "module default IDs")
        return immutableList(rows)
    }

    private fun chargeIds(value: Any): List<Int> {
        val ids = array(value, "charge_ids").map { integer(it, "charge_id", 1) }
        unique(ids, "charge IDs")
        return immutableList(ids)
    }

    fun decodeChargeCompatibility(json: String): List<ChargeCompatibility> {
        val rows = array(StrictJson(json).parse(), "compatibility").map { entry ->
            val row = objectValue(entry, "module")
            keys(row, setOf("id", "charge_ids"), path = "module")
            ChargeCompatibility(integer(row.get("id"), "module.id", 1), chargeIds(row.get("charge_ids")))
        }
        unique(rows.map { it.id }, "module IDs")
        return immutableList(rows)
    }

    fun decodeChargeOptions(json: String): ChargeOptions {
        val value = objectValue(StrictJson(json).parse(), "charges")
        keys(value, setOf("version", "fit_id", "revision", "modules", "items"), path = "charges")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported charge version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid charge revision")
        val modules = array(value.get("modules"), "modules").mapIndexed { index, entry ->
            val row = objectValue(entry, "module")
            keys(row, setOf("index", "item_id", "charge_id", "charge_ids"), path = "module")
            val position = integer(row.get("index"), "module.index", 0)
            requireProtocol(index == position, "Module positions are not contiguous")
            val item = nullable(row.get("item_id"))?.let { integer(it, "item_id", 1) }
            val charge = nullable(row.get("charge_id"))?.let { integer(it, "charge_id", 1) }
            val ids = chargeIds(row.get("charge_ids"))
            requireProtocol(item != null || charge == null && ids.isEmpty(), "Vacant slot has charges")
            ModuleCharges(position, item, charge, ids)
        }
        val items = array(value.get("items"), "items").map { entry ->
            val row = objectValue(entry, "charge")
            keys(row, setOf("id", "name"), path = "charge")
            ChargeItem(integer(row.get("id"), "charge.id", 1), nonempty(row.get("name"), "charge.name"))
        }
        unique(items.map { it.id }, "charge items")
        requireProtocol(modules.flatMap { it.chargeIds }.toSet() == items.map { it.id }.toSet(), "Charge union differs from modules")
        return ChargeOptions(identifier(value.get("fit_id"), "fit_id"), revision, immutableList(modules), immutableList(items))
    }

    fun decodeBulkChargeOptions(json: String): BulkChargeOptions {
        val value = objectValue(StrictJson(json).parse(), "charges")
        keys(value, setOf("version", "fit_id", "revision", "modules", "items"), path = "charges")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported charge version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid charge revision")
        val modules = array(value.get("modules"), "modules").mapIndexed { index, entry ->
            val row = objectValue(entry, "module")
            keys(row, setOf("index", "item_id", "charge_id", "charge_ids", "selection_candidates", "similar_candidates"), path = "module")
            val position = integer(row.get("index"), "module.index", 0)
            requireProtocol(index == position, "Module positions are not contiguous")
            val item = nullable(row.get("item_id"))?.let { integer(it, "item_id", 1) }
            val charge = nullable(row.get("charge_id"))?.let { integer(it, "charge_id", 1) }
            val ids = chargeIds(row.get("charge_ids"))
            requireProtocol(item != null || charge == null && ids.isEmpty(), "Vacant slot has charges")
            fun candidates(key: String): List<Int> {
                val positions = array(row.get(key), key).map { integer(it, key, 0) }
                unique(positions, key)
                requireProtocol(positions == positions.sorted(), "Bulk candidates must follow fit order")
                requireProtocol(item != null || positions.isEmpty(), "Vacancy has bulk candidates")
                requireProtocol(item == null || position in positions, "Reference missing from bulk candidates")
                return immutableList(positions)
            }
            BulkModuleCharges(position, item, charge, ids, candidates("selection_candidates"), candidates("similar_candidates"))
        }
        val items = array(value.get("items"), "items").map { entry ->
            val row = objectValue(entry, "charge")
            keys(row, setOf("id", "name"), path = "charge")
            ChargeItem(integer(row.get("id"), "charge.id", 1), nonempty(row.get("name"), "charge.name"))
        }
        unique(items.map { it.id }, "charge items")
        requireProtocol(modules.flatMap { it.chargeIds }.toSet() == items.map { it.id }.toSet(), "Charge union differs from modules")
        for (module in modules) {
            requireProtocol((module.selectionCandidates + module.similarCandidates).all {
                modules.getOrNull(it)?.itemId != null
            }, "Bulk candidate is outside fitted modules")
            val expected = if (module.itemId == null) emptyList() else modules.filter {
                it.itemId != null && module.chargeIds.containsAll(it.chargeIds)
            }.map { it.index }
            requireProtocol(module.selectionCandidates == expected, "Bulk selection capability differs from charges")
            if (module.itemId != null) requireProtocol(modules.filter { it.itemId == module.itemId }.all {
                it.index in module.similarCandidates
            }, "Identical module absent from similar scope")
        }
        return BulkChargeOptions(identifier(value.get("fit_id"), "fit_id"), revision, immutableList(modules), immutableList(items))
    }

    fun decodeBulkStateOptions(json: String): BulkStateOptions {
        val value = objectValue(StrictJson(json).parse(), "states")
        keys(value, setOf("version", "fit_id", "revision", "modules"), path = "states")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported state-options version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid state-options revision")
        val modules = array(value.get("modules"), "modules").mapIndexed { index, entry ->
            val row = objectValue(entry, "module")
            keys(row, setOf("index", "item_id", "state", "editable", "similar_candidates", "click_states", "supported_states"), path = "module")
            val position = integer(row.get("index"), "index", 0)
            requireProtocol(position == index, "State module positions are not contiguous")
            val item = nullable(row.get("item_id"))?.let { integer(it, "item_id", 1) }
            fun state(raw: Any, label: String): ModuleState =
                ModuleState.entries.find { it.name == nonempty(raw, label) } ?: fail("Invalid module state")
            val current = nullable(row.get("state"))?.let { state(it, "state") }
            requireProtocol((item == null) == (current == null), "Vacant slot has a state")
            val editable = bool(row.get("editable"), "editable")
            requireProtocol(item != null || !editable, "Vacant slot is editable")
            val similar = array(row.get("similar_candidates"), "similar_candidates").map {
                integer(it, "similar candidate", 0)
            }
            unique(similar, "similar candidates")
            requireProtocol(similar == similar.sorted(), "Similar candidates are out of order")
            requireProtocol(editable || similar.isEmpty(), "Unsupported slot has similar candidates")
            requireProtocol(!editable || position in similar, "Reference missing from similar scope")
            val clicks = objectValue(row.get("click_states"), "click_states")
            keys(clicks, if (item == null) emptySet() else StateClick.entries.map { it.wire }.toSet(), path = "click_states")
            val clickStates = if (item == null) emptyMap() else StateClick.entries.associateWith {
                state(clicks.get(it.wire), "click state")
            }
            val supported = objectValue(row.get("supported_states"), "supported_states")
            keys(supported, if (item == null) emptySet() else ModuleState.entries.map { it.name }.toSet(), path = "supported_states")
            val supportedStates = if (item == null) emptyMap() else ModuleState.entries.associateWith { requested ->
                state(supported.get(requested.name), "supported state").also { outcome ->
                    requireProtocol(outcome.ordinal <= requested.ordinal, "State fallback exceeds requested state")
                }
            }
            BulkModuleStates(position, item, current, editable, immutableList(similar), clickStates, supportedStates)
        }
        for (module in modules) {
            requireProtocol(module.similarCandidates.all { modules.getOrNull(it)?.editable == true },
                "Similar scope contains a vacant or missing module")
            if (module.editable) requireProtocol(modules.filter { it.editable && it.itemId == module.itemId }.all {
                it.index in module.similarCandidates
            }, "Identical module absent from similar scope")
        }
        return BulkStateOptions(identifier(value.get("fit_id"), "fit_id"), revision, immutableList(modules))
    }

    fun decodeFillItemOptions(json: String): FillItemOptions {
        val value = objectValue(StrictJson(json).parse(), "fill_item")
        keys(value, setOf("version", "fit_id", "revision", "item_id", "slot",
            "vacancies", "ignore_restrictions"), path = "fill_item")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported fill-options version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid fill-options revision")
        val slot = enumValue<ModuleSlot>(value.get("slot"), "slot")
        requireProtocol(slot.editable, "Unsupported fill slot")
        return FillItemOptions(identifier(value.get("fit_id"), "fit_id"), revision,
            integer(value.get("item_id"), "item_id", 1), slot,
            integer(value.get("vacancies"), "vacancies", 0, 1024),
            bool(value.get("ignore_restrictions"), "ignore_restrictions"))
    }

    fun decodeCloneVacancyOptions(json: String): CloneVacancyOptions {
        val value = objectValue(StrictJson(json).parse(), "clone_vacancies")
        keys(value, setOf("version", "fit_id", "revision", "vacancies"), path = "clone_vacancies")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported vacancy-options version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid vacancy-options revision")
        val rows = array(value.get("vacancies"), "vacancies").map { entry ->
            val row = objectValue(entry, "vacancy")
            keys(row, setOf("index", "slot"), path = "vacancy")
            val slot = enumValue<ModuleSlot>(row.get("slot"), "slot")
            requireProtocol(slot.editable, "Unsupported clone vacancy")
            CloneVacancy(integer(row.get("index"), "index", 0), slot)
        }
        unique(rows.map { it.index }, "vacancy positions")
        requireProtocol(rows.map { it.index } == rows.map { it.index }.sorted(), "Vacancies out of order")
        return CloneVacancyOptions(identifier(value.get("fit_id"), "fit_id"), revision, immutableList(rows))
    }

    private fun variationContext(raw: Any): VariationContext =
        VariationContext.entries.find { it.wire == nonempty(raw, "context") } ?: fail("Unknown variation context")

    private fun variationChoices(raw: Any): List<VariationChoice> {
        val rows = array(raw, "choices").map { entry ->
            val row = objectValue(entry, "choice")
            keys(row, setOf("id", "name", "group", "enabled"), path = "choice")
            VariationChoice(integer(row.get("id"), "choice.id", 1), nonempty(row.get("name"), "choice.name"),
                nullable(row.get("group"))?.let { nonempty(it, "choice.group") }, bool(row.get("enabled"), "choice.enabled"))
        }
        unique(rows.map { it.id }, "variation choices")
        return immutableList(rows)
    }

    fun decodeVariationFamilies(json: String): List<VariationFamily> {
        val rows = array(StrictJson(json).parse(), "families").map { entry ->
            val row = objectValue(entry, "family")
            keys(row, setOf("id", "context", "choices"), path = "family")
            VariationFamily(integer(row.get("id"), "family.id", 1), variationContext(row.get("context")),
                variationChoices(row.get("choices")))
        }
        unique(rows.map { it.id }, "variation families")
        return immutableList(rows)
    }

    fun decodeModeOptions(json: String): ModeOptions {
        val value = objectValue(StrictJson(json).parse(), "modes")
        keys(value, setOf("version", "fit_id", "revision", "current", "choices"), path = "modes")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported mode version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid mode revision")
        val choices = array(value.get("choices"), "choices").map { entry ->
            val row = objectValue(entry, "mode")
            keys(row, setOf("id", "name"), path = "mode")
            HullModeChoice(integer(row.get("id"), "mode.id", 1), nonempty(row.get("name"), "mode.name"))
        }
        unique(choices.map { it.id }, "mode choices")
        val current = nullable(value.get("current"))?.let { integer(it, "current", 1) }
        requireProtocol((choices.isEmpty() && current == null) ||
            (choices.isNotEmpty() && choices.any { it.id == current }), "Current mode is outside hull choices")
        return ModeOptions(nonempty(value.get("fit_id"), "fit_id"), revision, current, immutableList(choices))
    }

    fun decodeSubsystemOptions(json: String): SubsystemOptions {
        val value = objectValue(StrictJson(json).parse(), "subsystems")
        keys(value, setOf("version", "fit_id", "revision", "capacity", "groups"), path = "subsystems")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported subsystem version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid subsystem revision")
        val capacity = integer(value.get("capacity"), "capacity", 0)
        val names = mapOf(125 to "Core", 126 to "Defensive", 127 to "Offensive", 128 to "Propulsion")
        val groups = array(value.get("groups"), "groups").map { entry ->
            val row = objectValue(entry, "subsystem group")
            keys(row, setOf("kind", "name", "current", "choices"), path = "subsystem group")
            val kind = integer(row.get("kind"), "kind", 125, 128)
            requireProtocol(nonempty(row.get("name"), "name") == names[kind], "Unknown subsystem group")
            val choices = array(row.get("choices"), "choices").map { item ->
                val choice = objectValue(item, "subsystem choice")
                keys(choice, setOf("id", "name"), path = "subsystem choice")
                SubsystemChoice(integer(choice.get("id"), "id", 1), nonempty(choice.get("name"), "name"))
            }
            requireProtocol(choices.isNotEmpty(), "Empty subsystem group")
            unique(choices.map { it.id }, "subsystem choices")
            val current = nullable(row.get("current"))?.let { integer(it, "current", 1) }
            requireProtocol(current == null || choices.any { it.id == current }, "Current subsystem is outside choices")
            SubsystemGroup(kind, names.getValue(kind), current, immutableList(choices))
        }
        requireProtocol(groups.isEmpty() || groups.map { it.kind } == listOf(125, 126, 127, 128),
            "Missing or reordered subsystem groups")
        requireProtocol((groups.isEmpty() && capacity == 0) ||
            (groups.isNotEmpty() && capacity == groups.size), "Invalid subsystem capacity")
        unique(groups.flatMap { group -> group.choices.map { it.id } }, "subsystem IDs")
        return SubsystemOptions(nonempty(value.get("fit_id"), "fit_id"), revision, capacity, immutableList(groups))
    }

    fun decodeStructureServiceOptions(json: String): StructureServiceOptions {
        val value = objectValue(StrictJson(json).parse(), "structure services")
        keys(value, setOf("version", "fit_id", "revision", "is_structure", "capacity", "choices"),
            path = "structure services")
        requireProtocol(long(value.get("version"), "version") == 1L,
            "Unsupported structure-service version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid structure-service revision")
        val isStructure = bool(value.get("is_structure"), "is_structure")
        val capacity = integer(value.get("capacity"), "capacity", 0)
        val choices = array(value.get("choices"), "choices").map { entry ->
            val row = objectValue(entry, "service choice")
            keys(row, setOf("id", "name"), path = "service choice")
            StructureServiceChoice(integer(row.get("id"), "id", 1), nonempty(row.get("name"), "name"))
        }
        unique(choices.map { it.id }, "structure service choices")
        requireProtocol(isStructure || capacity == 0 && choices.isEmpty(),
            "Non-structure hull cannot have service choices")
        return StructureServiceOptions(nonempty(value.get("fit_id"), "fit_id"), revision,
            isStructure, capacity, immutableList(choices))
    }

    private fun cargoIds(values: List<Int>): JSONArray {
        requireProtocol(values.isNotEmpty() && values.all { it > 0 }, "Select cargo stacks")
        unique(values, "selected cargo IDs")
        return JSONArray(values)
    }

    fun decodeCargoActionOptions(json: String): CargoActionOptions {
        val value = objectValue(StrictJson(json).parse(), "cargo actions")
        keys(value, setOf("version", "fit_id", "revision", "item_id", "from_cargo",
            "preset_quantity", "fill_quantity", "variations"), path = "cargo actions")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported cargo actions version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid cargo revision")
        val fromCargo = bool(value.get("from_cargo"), "from_cargo")
        val preset = nullable(value.get("preset_quantity"))?.let { long(it, "preset_quantity") }
        requireProtocol(preset == null || preset in listOf(8L, 1000L), "Invalid cargo preset")
        val fill = nullable(value.get("fill_quantity"))?.let { long(it, "fill_quantity") }
        requireProtocol(fill == null || fill >= 0, "Invalid cargo fill quantity")
        val variations = variationChoices(value.get("variations"))
        requireProtocol(variations.all { it.group != null }, "Missing cargo variation group")
        requireProtocol(if (fromCargo) preset == null && fill != null else variations.isEmpty(),
            "Cargo actions do not match their context")
        return CargoActionOptions(identifier(value.get("fit_id"), "fit_id"), revision,
            integer(value.get("item_id"), "item_id", 1), fromCargo, preset, fill, variations)
    }

    fun decodeEditHistory(json: String): EditHistory {
        val value = objectValue(StrictJson(json).parse(), "history")
        keys(value, setOf("version", "fit_id", "revision", "undo_count", "redo_count", "limit", "undo_label", "redo_label"), path = "history")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported history version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid history revision")
        val limit = integer(value.get("limit"), "limit", 100, 100)
        val undo = integer(value.get("undo_count"), "undo_count", 0, limit)
        val redo = integer(value.get("redo_count"), "redo_count", 0, limit)
        requireProtocol(undo + redo <= limit, "History exceeds its limit")
        fun label(key: String, count: Int): String? {
            val raw = value.get(key)
            if (count == 0) { requireProtocol(raw === JSONObject.NULL, "Empty history must not name an action"); return null }
            return text(raw, key).also { requireProtocol(it.isNotBlank(), "History action needs a label") }
        }
        return EditHistory(identifier(value.get("fit_id"), "fit_id"), revision, undo, redo, limit,
            label("undo_label", undo), label("redo_label", redo))
    }

    fun decodeNoteDetails(json: String): NoteDetails {
        val value = objectValue(StrictJson(json).parse(), "notes")
        keys(value, setOf("version", "fit_id", "revision", "text", "characters", "editable"), path = "notes")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported notes version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid notes revision")
        val text = noteText(value.get("text"))
        val count = integer(value.get("characters"), "characters", 0)
        requireProtocol(count == text.codePointCount(0, text.length), "Notes character count disagrees with text")
        return NoteDetails(identifier(value.get("fit_id"), "fit_id"), revision, text, count,
            bool(value.get("editable"), "editable"))
    }

    private fun noteText(value: Any): String = text(value, "notes").also { text ->
        var index = 0
        while (index < text.length) {
            val char = text[index++]
            if (char.isHighSurrogate()) {
                requireProtocol(index < text.length && text[index++].isLowSurrogate(), "Invalid Unicode notes")
            } else requireProtocol(!char.isLowSurrogate(), "Invalid Unicode notes")
        }
    }

    fun decodeDroneDetails(json: String): DroneDetails {
        val value = objectValue(StrictJson(json).parse(), "drones")
        keys(value, setOf("version", "fit_id", "revision", "stacks", "active", "active_limit",
            "bay_used", "bay_capacity", "bandwidth_used", "bandwidth_capacity"), path = "drones")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported drone version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid drone revision")
        fun nonnegative(raw: Any, name: String): Double = number(raw, name).also {
            requireProtocol(it >= 0, "Negative drone resource")
        }
        val stacks = array(value.get("stacks"), "stacks").mapIndexed { index, entry ->
            val row = objectValue(entry, "drone stack")
            keys(row, setOf("index", "object_key", "item_id", "name", "group", "amount", "active", "mutation", "metrics"), path = "drone stack")
            requireProtocol(integer(row.get("index"), "index", 0) == index, "Drone positions must be contiguous")
            val objectKey = nonempty(row.get("object_key"), "object_key")
            requireProtocol(objectKey.matches(Regex("[0-9a-f]{32}")), "Invalid drone identity")
            val amount = integer(row.get("amount"), "amount", 1)
            val active = integer(row.get("active"), "active", 0)
            requireProtocol(active <= amount, "Active drones exceed stored amount")
            val mutation = nullable(row.get("mutation"))?.let { raw ->
                val m = objectValue(raw, "mutation")
                keys(m, setOf("base_item_id", "base_name", "mutaplasmid_id", "mutaplasmid_name", "attributes"), path = "mutation")
                val rolls = array(m.get("attributes"), "attributes").map { item ->
                    val r = objectValue(item, "mutation attribute")
                    keys(r, setOf("attribute_id", "value"), path = "mutation attribute")
                    DroneRoll(integer(r.get("attribute_id"), "attribute_id", 1), number(r.get("value"), "value"))
                }
                requireProtocol(rolls.isNotEmpty(), "Missing mutation attributes")
                val ids = rolls.map { it.attributeId }
                unique(ids, "mutation attributes")
                requireProtocol(ids == ids.sorted(), "Unordered mutation attributes")
                DroneMutation(integer(m.get("base_item_id"), "base_item_id", 1), nonempty(m.get("base_name"), "base_name"),
                    integer(m.get("mutaplasmid_id"), "mutaplasmid_id", 1), nonempty(m.get("mutaplasmid_name"), "mutaplasmid_name"), immutableList(rolls))
            }
            val metrics = array(row.get("metrics"), "metrics").map { item ->
                val m = objectValue(item, "drone metric")
                keys(m, setOf("key", "label", "unit", "value", "text"), path = "drone metric")
                val raw = nullable(m.get("value"))?.let { number(it, "value") }
                val text = nullable(m.get("text"))?.let { nonempty(it, "text") }
                requireProtocol((raw == null) == (text == null), "Drone metric availability differs")
                DroneMetric(nonempty(m.get("key"), "key"), nonempty(m.get("label"), "label"),
                    nonempty(m.get("unit"), "unit"), raw, text)
            }
            requireProtocol(metrics.map { it.key }.toSet() == droneMetricUnits.keys, "Missing or unknown drone metrics")
            requireProtocol(metrics.all { droneMetricUnits[it.key] == it.unit }, "Unexpected drone metric unit")
            unique(metrics.map { it.key }, "drone metrics")
            DroneStack(index, objectKey, integer(row.get("item_id"), "item_id", 1), nonempty(row.get("name"), "name"),
                nonempty(row.get("group"), "group"), amount, active, mutation, immutableList(metrics))
        }
        unique(stacks.map { it.objectKey }, "drone identities")
        val active = long(value.get("active"), "active")
        requireProtocol(active >= 0 && active == stacks.sumOf { it.active.toLong() }, "Drone active count disagrees")
        return DroneDetails(identifier(value.get("fit_id"), "fit_id"), revision, active,
            nonnegative(value.get("active_limit"), "active_limit"), nonnegative(value.get("bay_used"), "bay_used"),
            nullable(value.get("bay_capacity"))?.let { nonnegative(it, "bay_capacity") },
            nonnegative(value.get("bandwidth_used"), "bandwidth_used"),
            nullable(value.get("bandwidth_capacity"))?.let { nonnegative(it, "bandwidth_capacity") }, immutableList(stacks))
    }

    fun decodeCargoDetails(json: String): CargoDetails {
        val value = objectValue(StrictJson(json).parse(), "cargo")
        return cargoDetails(value)
    }

    private fun cargoDetails(value: JSONObject, extra: Set<String> = emptySet()): CargoDetails {
        keys(value, setOf("version", "fit_id", "revision", "is_structure", "capacity_m3", "used_m3", "over_capacity", "cargo") + extra,
            path = "cargo")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported cargo version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid cargo revision")
        val capacity = number(value.get("capacity_m3"), "capacity_m3")
        val used = number(value.get("used_m3"), "used_m3")
        requireProtocol(capacity >= 0 && used >= 0, "Negative cargo volume")
        val over = bool(value.get("over_capacity"), "over_capacity")
        requireProtocol(over == (used > capacity), "Cargo over-capacity state disagrees with volume")
        val stacks = array(value.get("cargo"), "cargo").map { entry ->
            val row = objectValue(entry, "cargo stack")
            keys(row, setOf("id", "name", "amount", "unit_volume_m3"), path = "cargo stack")
            val amount = long(row.get("amount"), "amount")
            requireProtocol(amount > 0, "Cargo amount must be positive")
            val volume = number(row.get("unit_volume_m3"), "unit_volume_m3")
            requireProtocol(volume >= 0, "Negative cargo item volume")
            CargoStack(integer(row.get("id"), "id", 1), nonempty(row.get("name"), "name"), amount, volume)
        }
        unique(stacks.map { it.id }, "cargo stack IDs")
        return CargoDetails(identifier(value.get("fit_id"), "fit_id"), revision,
            bool(value.get("is_structure"), "is_structure"), capacity, used, over, immutableList(stacks))
    }

    fun decodeCargoTransferDetails(json: String): CargoTransferDetails {
        val value = objectValue(StrictJson(json).parse(), "cargo transfers")
        val cargo = cargoDetails(value, setOf("modules"))
        val modules = array(value.get("modules"), "modules").mapIndexed { index, entry ->
            val row = objectValue(entry, "transfer module")
            keys(row, setOf("index", "id", "name", "slot", "state", "charge_id", "charge", "charge_amount", "legal"),
                path = "transfer module")
            val position = integer(row.get("index"), "index", 0)
            requireProtocol(position == index, "Transfer positions must be contiguous")
            val id = nullable(row.get("id"))?.let { integer(it, "id", 1) }
            val name = nullable(row.get("name"))?.let { nonempty(it, "name") }
            val chargeId = nullable(row.get("charge_id"))?.let { integer(it, "charge_id", 1) }
            val charge = nullable(row.get("charge"))?.let { nonempty(it, "charge") }
            val amount = long(row.get("charge_amount"), "charge_amount")
            val legal = nullable(row.get("legal"))?.let { bool(it, "legal") }
            val slot = nonempty(row.get("slot"), "slot")
            requireProtocol(slot in setOf("LOW", "MED", "HIGH", "RIG", "SUBSYSTEM", "SERVICE"), "Invalid transfer slot")
            val state = enumValue<ModuleState>(row.get("state"), "state")
            requireProtocol((id == null) == (name == null) && (id == null) == (legal == null), "Incomplete transfer module")
            requireProtocol((chargeId == null) == (charge == null) && amount >= 0 &&
                (chargeId != null || amount == 0L) && (id != null || chargeId == null), "Invalid transfer charge")
            CargoTransferModule(position, id, name, slot, state, chargeId, charge, amount, legal)
        }
        return CargoTransferDetails(cargo, immutableList(modules))
    }

    fun decodeVariationOptions(json: String): VariationOptions {
        val value = objectValue(StrictJson(json).parse(), "variations")
        keys(value, setOf("version", "fit_id", "revision", "targets"), setOf("module_families"), "variations")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported variation version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid variation revision")
        val targets = array(value.get("targets"), "targets").map { entry ->
            val row = objectValue(entry, "target")
            keys(row, setOf("context", "index", "item_id", "name", "current", "choices"), path = "target")
            val context = variationContext(row.get("context"))
            val current = objectValue(row.get("current"), "current")
            val input = when (context) {
                VariationContext.MODULE -> {
                    keys(current, setOf("state", "charge_id"), path = "current")
                    val state = ModuleState.entries.find { it.name == nonempty(current.get("state"), "state") }
                        ?: fail("Invalid module state")
                    VariationInput.Module(state, nullable(current.get("charge_id"))?.let { integer(it, "charge_id", 1) })
                }
                VariationContext.DRONE -> {
                    keys(current, setOf("amount", "active"), path = "current")
                    val amount = integer(current.get("amount"), "amount", 1)
                    VariationInput.Drone(amount, integer(current.get("active"), "active", 0, amount))
                }
                VariationContext.IMPLANT -> {
                    keys(current, setOf("slot", "active", "location"), path = "current")
                    val location = nonempty(current.get("location"), "location")
                    requireProtocol(location == "FIT", "Unsupported implant location")
                    VariationInput.Implant(integer(current.get("slot"), "slot", 1), bool(current.get("active"), "active"), location)
                }
            }
            val choices = variationChoices(row.get("choices"))
            requireProtocol(choices.all { (it.group == null) == (context == VariationContext.IMPLANT) }, "Incorrect variation group")
            VariationTarget(context, integer(row.get("index"), "index", 0), integer(row.get("item_id"), "item_id", 1),
                nonempty(row.get("name"), "name"), input, choices)
        }
        unique(targets.map { it.context to it.index }, "variation targets")
        requireProtocol(targets == targets.sortedWith(compareBy<VariationTarget> { it.context.ordinal }.thenBy { it.index }),
            "Variation targets are out of order")
        for (context in listOf(VariationContext.DRONE, VariationContext.IMPLANT))
            requireProtocol(targets.filter { it.context == context }.map { it.index }.withIndex().all { it.index == it.value },
                "Addition positions are not contiguous")
        unique(targets.mapNotNull { (it.current as? VariationInput.Implant)?.slot }, "implant slots")
        val modules = targets.filter { it.context == VariationContext.MODULE }
        val families = if (!value.has("module_families")) emptyMap() else {
            val rows = array(value.get("module_families"), "module_families").map { entry ->
                val row = objectValue(entry, "module family")
                keys(row, setOf("index", "candidates"), path = "module family")
                val index = integer(row.get("index"), "family index", 0)
                val candidates = array(row.get("candidates"), "family candidates").map {
                    integer(it, "family candidate", 0)
                }
                unique(candidates, "family candidates")
                requireProtocol(candidates == candidates.sorted() && index in candidates,
                    "Module family candidates must be ordered and contain the reference")
                index to immutableList(candidates)
            }
            unique(rows.map { it.first }, "module families")
            requireProtocol(rows.map { it.first } == modules.map { it.index },
                "Module families differ from fitted module targets")
            val mapping = rows.toMap()
            requireProtocol(rows.all { (_, candidates) -> candidates.all { mapping[it] == candidates } },
                "Module family candidates are not symmetric")
            immutableMap(mapping)
        }
        return VariationOptions(identifier(value.get("fit_id"), "fit_id"), revision, immutableList(targets), families)
    }

    fun decodeRackOptions(json: String): RackOptions {
        val value = objectValue(StrictJson(json).parse(), "rack")
        keys(value, setOf("version", "fit_id", "revision", "modules"), path = "rack")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported rack version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid rack revision")
        fun decimal(raw: Any, path: String): Double =
            finite(raw as? Double ?: fail("$path must be decimal"), path)
        val modules = array(value.get("modules"), "modules").mapIndexed { index, entry ->
            val row = objectValue(entry, "module")
            keys(row, setOf("index", "id", "name", "slot", "state", "charge_id", "charge", "heat"), path = "module")
            requireProtocol(integer(row.get("index"), "index", 0) == index, "Module positions are not contiguous")
            val id = nullable(row.get("id"))?.let { integer(it, "id", 1) }
            val name = nullable(row.get("name"))?.let { nonempty(it, "name") }
            val chargeId = nullable(row.get("charge_id"))?.let { integer(it, "charge_id", 1) }
            val charge = nullable(row.get("charge"))?.let { nonempty(it, "charge") }
            val state = enumValue<ModuleState>(row.get("state"), "state")
            val slot = enumValue<ModuleSlot>(row.get("slot"), "slot")
            requireProtocol((id == null) == (name == null) && (chargeId == null) == (charge == null) &&
                (id != null || chargeId == null && state == ModuleState.ONLINE), "Inconsistent vacant module")
            val heat = nullable(row.get("heat"))?.let { raw ->
                val h = objectValue(raw, "heat")
                keys(h, setOf("cycles", "seconds", "probabilities"), path = "heat")
                fun measure(key: String, unit: String): Any? {
                    val metric = objectValue(h.get(key), key)
                    keys(metric, setOf("value", "unit"), path = key)
                    requireProtocol(text(metric.get("unit"), "unit") == unit, "Unexpected heat unit")
                    return nullable(metric.get("value"))
                }
                val cycles = measure("cycles", "cycles")?.let { long(it, "cycles").also { count ->
                    requireProtocol(count >= 0, "Invalid burnout cycles") } }
                val seconds = measure("seconds", "s")?.let { decimal(it, "seconds").also { time ->
                    requireProtocol(time >= 0, "Invalid burnout time") } }
                requireProtocol((cycles == null) == (seconds == null), "Incomplete heat estimate")
                val probabilities = array(h.get("probabilities"), "probabilities").map { sample ->
                    val p = objectValue(sample, "probability")
                    keys(p, setOf("seconds", "value", "unit"), path = "probability")
                    requireProtocol(text(p.get("unit"), "unit") == "probability", "Unexpected probability unit")
                    HeatProbability(decimal(p.get("seconds"), "seconds"), decimal(p.get("value"), "value").also {
                        requireProtocol(it in 0.0..1.0, "Invalid heat probability") })
                }
                requireProtocol(probabilities.map { it.seconds } == if (cycles == null) emptyList<Double>()
                    else listOf(1.0, 10.0, 60.0, 600.0), "Incomplete heat samples")
                HeatEstimate(Stat(cycles?.let { StatValue.Integer(it) } ?: StatValue.Unavailable, "cycles"),
                    Stat(seconds?.let { StatValue.Decimal(it) } ?: StatValue.Unavailable, "s"), immutableList(probabilities))
            }
            requireProtocol((heat != null) == (state == ModuleState.OVERHEATED), "Heat estimate has wrong module state")
            RackModule(index, id, name, slot, state, chargeId, charge, heat)
        }
        return RackOptions(identifier(value.get("fit_id"), "fit_id"), revision, immutableList(modules))
    }

    fun decodeFitting(json: String): FittingDetails {
        val value = objectValue(StrictJson(json).parse(), "fitting")
        keys(value, setOf("version", "fit_id", "revision", "ignore_restrictions", "modules", "resources",
            "slots", "hardpoints", "skill_warnings"), path = "fitting")
        requireProtocol(long(value.get("version"), "version") == 1L, "Unsupported fitting version")
        val revision = long(value.get("revision"), "revision")
        requireProtocol(revision >= 1, "Invalid fitting revision")
        fun numeric(raw: Any, path: String): StatValue = when (raw) {
            is Int -> StatValue.Integer(raw.toLong())
            is Long -> StatValue.Integer(raw)
            is Double -> StatValue.Decimal(finite(raw, path))
            else -> fail("$path must be a numeric scalar")
        }
        fun requirements(raw: Any, depth: Int = 0): List<SkillRequirement> {
            requireProtocol(depth <= 16, "Skill requirements exceed nesting limit")
            val rows = array(raw, "requirements").map { entry ->
                val row = objectValue(entry, "requirement")
                keys(row, setOf("id", "name", "required", "actual", "requirements"), path = "requirement")
                SkillRequirement(integer(row.get("id"), "skill.id", 1), nonempty(row.get("name"), "skill.name"),
                    integer(row.get("required"), "required", 1, 5), integer(row.get("actual"), "actual", 0, 5),
                    requirements(row.get("requirements"), depth + 1))
            }
            unique(rows.map { it.id }, "requirement IDs")
            return immutableList(rows)
        }
        val modules = array(value.get("modules"), "modules").mapIndexed { index, entry ->
            val row = objectValue(entry, "module")
            keys(row, setOf("index", "id", "name", "slot", "state", "charge", "legal", "overridden"), path = "module")
            val position = integer(row.get("index"), "module.index", 0)
            requireProtocol(position == index, "Module positions are not contiguous")
            val id = nullable(row.get("id"))?.let { integer(it, "module.id", 1) }
            val name = nullable(row.get("name"))?.let { nonempty(it, "module.name") }
            val charge = nullable(row.get("charge"))?.let { nonempty(it, "module.charge") }
            val legal = nullable(row.get("legal"))?.let { bool(it, "module.legal") }
            val overridden = bool(row.get("overridden"), "overridden")
            requireProtocol(if (id == null) name == null && charge == null && legal == null && !overridden
                else name != null && legal != null, "Inconsistent empty or fitted module")
            FittingModule(position, id, name, enumValue<ModuleSlot>(row.get("slot"), "module.slot"),
                enumValue<ModuleState>(row.get("state"), "module.state"), charge, legal, overridden)
        }
        val resourceObject = objectValue(value.get("resources"), "resources")
        keys(resourceObject, setOf("cpu", "powergrid", "calibration"), path = "resources")
        val resources = resourceObject.keys().asSequence().associateWith { name ->
            val row = objectValue(resourceObject.get(name), "resource")
            keys(row, setOf("used", "total", "unit", "overloaded"), path = "resource")
            val unit = nonempty(row.get("unit"), "resource.unit")
            requireProtocol(unit == mapOf("cpu" to "tf", "powergrid" to "MW", "calibration" to "points").getValue(name),
                "Unexpected resource unit")
            ResourceUse(numeric(row.get("used"), "used"), numeric(row.get("total"), "total"), unit,
                bool(row.get("overloaded"), "overloaded"))
        }
        val slots = array(value.get("slots"), "slots").map { entry ->
            val row = objectValue(entry, "slot")
            keys(row, setOf("slot", "used", "total"), path = "slot")
            SlotUse(enumValue<ModuleSlot>(row.get("slot"), "slot"), integer(row.get("used"), "slot.used", 0),
                numeric(row.get("total"), "slot.total"))
        }
        unique(slots.map { it.slot }, "slot types")
        requireProtocol(slots.map { it.slot }.toSet() == ModuleSlot.entries.filter { it.editable }.toSet(), "Missing slot totals")
        val hardpoints = array(value.get("hardpoints"), "hardpoints").map { entry ->
            val row = objectValue(entry, "hardpoint")
            keys(row, setOf("kind", "used", "total"), path = "hardpoint")
            HardpointUse(nonempty(row.get("kind"), "hardpoint.kind"), integer(row.get("used"), "hardpoint.used", 0),
                numeric(row.get("total"), "hardpoint.total"))
        }
        requireProtocol(hardpoints.size == 2 && hardpoints.map { it.kind }.toSet() == setOf("TURRET", "MISSILE"),
            "Missing or unknown hardpoint types")
        val warnings = array(value.get("skill_warnings"), "skill_warnings").map { entry ->
            val row = objectValue(entry, "skill_warning")
            keys(row, setOf("id", "name", "requirements"), path = "skill_warning")
            SkillWarning(integer(row.get("id"), "warning.id", 1), nonempty(row.get("name"), "warning.name"),
                requirements(row.get("requirements")))
        }
        unique(warnings.map { it.id }, "skill warning IDs")
        return FittingDetails(identifier(value.get("fit_id"), "fit_id"), revision,
            bool(value.get("ignore_restrictions"), "ignore_restrictions"), immutableList(modules),
            immutableMap(resources), immutableList(slots), immutableList(hardpoints), immutableList(warnings))
    }

    private val STAT_NAMES = setOf(
        "cpu_output", "powergrid_output", "capacitor_capacity", "capacitor_recharge_time", "max_velocity", "max_target_range",
        "cpu_used", "powergrid_used", "drone_control_range", "drone_bandwidth_used", "weapon_dps", "drone_dps", "total_dps",
        "total_volley", "capacitor_used", "capacitor_recharge", "capacitor_stable", "capacitor_state", "gun_optimal", "gun_falloff",
        "shield_hp", "shield_ehp_uniform", "shield_em_resonance", "shield_thermal_resonance", "shield_kinetic_resonance", "shield_explosive_resonance",
        "armor_hp", "armor_ehp_uniform", "armor_em_resonance", "armor_thermal_resonance", "armor_kinetic_resonance", "armor_explosive_resonance",
        "hull_hp", "hull_ehp_uniform", "hull_em_resonance", "hull_thermal_resonance", "hull_kinetic_resonance", "hull_explosive_resonance", "scan_resolution",
    )

    private fun keys(value: JSONObject, required: Set<String>, optional: Set<String> = emptySet(), path: String) {
        val actual = value.keys().asSequence().toSet()
        requireProtocol(actual.containsAll(required) && (actual - required - optional).isEmpty(), "$path has missing or unsupported fields")
    }

    private fun obj(vararg fields: Pair<String, Any?>): JSONObject = JSONObject().apply {
        for ((key, value) in fields) put(key, value ?: JSONObject.NULL)
    }
    private fun jsonArray(values: Collection<*>): JSONArray = JSONArray().apply { for (value in values) put(value ?: JSONObject.NULL) }
    private fun objectValue(value: Any, path: String): JSONObject = value as? JSONObject ?: fail("$path must be an object")
    private fun array(value: Any, path: String): List<Any> {
        val array = value as? JSONArray ?: fail("$path must be an array")
        return (0 until array.length()).map { array.get(it) }
    }
    private fun nullable(value: Any): Any? = if (value === JSONObject.NULL) null else value
    private fun text(value: Any, path: String): String = value as? String ?: fail("$path must be a string")
    private fun nonempty(value: Any, path: String): String = text(value, path).also { requireProtocol(it.isNotEmpty(), "$path must not be empty") }
    private fun identifier(value: Any, path: String): String = nonempty(value, path).also {
        requireProtocol(it.codePointCount(0, it.length) <= 128, "$path exceeds 128 characters")
    }
    private fun bool(value: Any, path: String): Boolean = value as? Boolean ?: fail("$path must be boolean")
    private fun long(value: Any, path: String): Long = when (value) {
        is Int -> value.toLong()
        is Long -> value
        else -> fail("$path must be an integer")
    }
    private fun integer(value: Any, path: String, minimum: Int, maximum: Int = Int.MAX_VALUE): Int {
        val number = long(value, path)
        requireProtocol(number in minimum.toLong()..maximum.toLong(), "$path is out of range")
        return number.toInt()
    }
    private fun number(value: Any, path: String): Double = when (value) {
        is Int -> value.toDouble()
        is Long -> value.toDouble()
        is Double -> finite(value, path)
        else -> fail("$path must be numeric")
    }
    private fun finite(value: Double, path: String): Double = value.also { requireProtocol(it.isFinite(), "$path must be finite") }
    private inline fun <reified T : Enum<T>> enumValue(value: Any, path: String): T {
        val name = text(value, path)
        return enumValues<T>().firstOrNull { it.name == name } ?: fail("Unknown $path value")
    }
    private fun <T> unique(values: List<T>, path: String) = requireProtocol(values.toSet().size == values.size, "Duplicate $path")
}

private fun requireProtocol(condition: Boolean, message: String) { if (!condition) fail(message) }
private fun fail(message: String): Nothing = throw BridgeProtocolException(message)
private fun <T> immutableList(values: Collection<T>): List<T> = Collections.unmodifiableList(ArrayList(values))
private fun <K, V> immutableMap(values: Map<K, V>): Map<K, V> = Collections.unmodifiableMap(LinkedHashMap(values))

/** Android's JSONTokener accepts duplicate keys, comments and other non-JSON input. */
internal class StrictJson(private val input: String) {
    private var position = 0

    fun parse(): Any {
        val value = value(0)
        whitespace()
        requireProtocol(position == input.length, "Trailing JSON input")
        return value
    }

    private fun value(depth: Int): Any {
        requireProtocol(depth <= 128, "JSON nesting is too deep")
        whitespace()
        requireProtocol(position < input.length, "Missing JSON value")
        return when (input[position]) {
            '{' -> objectValue(depth + 1)
            '[' -> arrayValue(depth + 1)
            '"' -> string()
            't' -> literal("true", true)
            'f' -> literal("false", false)
            'n' -> literal("null", JSONObject.NULL)
            '-', in '0'..'9' -> number()
            else -> fail("Invalid JSON value")
        }
    }

    private fun objectValue(depth: Int): JSONObject {
        position++
        val result = JSONObject()
        val keys = mutableSetOf<String>()
        whitespace()
        if (take('}')) return result
        while (true) {
            whitespace()
            requireProtocol(position < input.length && input[position] == '"', "JSON object keys must be quoted")
            val key = string()
            requireProtocol(keys.add(key), "Duplicate JSON key")
            whitespace()
            requireProtocol(take(':'), "Missing JSON colon")
            result.put(key, value(depth))
            whitespace()
            if (take('}')) return result
            requireProtocol(take(','), "Missing JSON object separator")
        }
    }

    private fun arrayValue(depth: Int): JSONArray {
        position++
        val result = JSONArray()
        whitespace()
        if (take(']')) return result
        while (true) {
            result.put(value(depth))
            whitespace()
            if (take(']')) return result
            requireProtocol(take(','), "Missing JSON array separator")
        }
    }

    private fun string(): String {
        position++
        val result = StringBuilder()
        while (position < input.length) {
            val char = input[position++]
            when {
                char == '"' -> return result.toString()
                char == '\\' -> {
                    requireProtocol(position < input.length, "Incomplete JSON escape")
                    when (val escaped = input[position++]) {
                        '"', '\\', '/' -> result.append(escaped)
                        'b' -> result.append('\b')
                        'f' -> result.append('\u000C')
                        'n' -> result.append('\n')
                        'r' -> result.append('\r')
                        't' -> result.append('\t')
                        'u' -> {
                            requireProtocol(position + 4 <= input.length, "Incomplete Unicode escape")
                            val digits = input.substring(position, position + 4)
                            requireProtocol(digits.all { it in '0'..'9' || it in 'a'..'f' || it in 'A'..'F' }, "Invalid Unicode escape")
                            result.append(digits.toInt(16).toChar())
                            position += 4
                        }
                        else -> fail("Invalid JSON escape")
                    }
                }
                char.code < 0x20 -> fail("Unescaped JSON control character")
                else -> result.append(char)
            }
        }
        fail("Unterminated JSON string")
    }

    private fun number(): Number {
        val begin = position
        take('-')
        requireProtocol(position < input.length, "Incomplete JSON number")
        if (take('0')) {
            requireProtocol(position == input.length || input[position] !in '0'..'9', "Leading zero in JSON number")
        } else {
            requireProtocol(position < input.length && input[position] in '1'..'9', "Invalid JSON number")
            digits()
        }
        var decimal = false
        if (take('.')) {
            decimal = true
            requiredDigits()
        }
        if (take('e') || take('E')) {
            decimal = true
            if (!take('+')) take('-')
            requiredDigits()
        }
        val token = input.substring(begin, position)
        return if (decimal) {
            val number = token.toDoubleOrNull() ?: fail("Invalid decimal")
            requireProtocol(number.isFinite(), "Nonfinite JSON number")
            number
        } else token.toLongOrNull() ?: fail("JSON integer exceeds signed 64-bit range")
    }

    private fun requiredDigits() {
        requireProtocol(position < input.length && input[position] in '0'..'9', "Missing number digits")
        digits()
    }
    private fun digits() { while (position < input.length && input[position] in '0'..'9') position++ }
    private fun literal(token: String, value: Any): Any {
        requireProtocol(input.startsWith(token, position), "Invalid JSON literal")
        position += token.length
        return value
    }
    private fun take(char: Char): Boolean {
        if (position >= input.length || input[position] != char) return false
        position++
        return true
    }
    private fun whitespace() { while (position < input.length && input[position] in " \t\r\n") position++ }
}
