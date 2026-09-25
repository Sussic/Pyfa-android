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
data class Security(val system: SystemSecurity, val pilot: Double)
data class ModuleSpec(val name: String, val state: ModuleState, val charge: String? = null)
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
)

sealed interface BridgeOperation {
    data class Snapshot(val fitIds: List<String> = emptyList()) : BridgeOperation
    data class CreateFit(val spec: FitSpec) : BridgeOperation
    data class RenameFit(val fitId: String, val name: String) : BridgeOperation
    data class DuplicateFit(val fitId: String, val name: String) : BridgeOperation
    data class DeleteFit(val fitId: String, val resolveReferences: Boolean) : BridgeOperation
    data class AddModule(val fitId: String, val itemId: Int) : BridgeOperation
    data class ReplaceModule(val fitId: String, val position: Int, val itemId: Int) : BridgeOperation
    data class RemoveModule(val fitId: String, val position: Int) : BridgeOperation
    data class SetFitRestrictions(val fitId: String, val ignore: Boolean) : BridgeOperation
    data class SetCharges(val fitId: String, val moduleIndices: List<Int>, val charge: String?) : BridgeOperation
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
    data class SwapModules(val fitId: String, val fromPosition: Int, val toPosition: Int) : BridgeOperation
    data class SetModuleStates(val fitId: String, val moduleIndices: List<Int>, val state: ModuleState) : BridgeOperation
    data class SetSkillLevel(val fitId: String, val skill: String, val level: Int) : BridgeOperation
    data class AddImplant(val fitId: String, val implant: String, val active: Boolean = true) : BridgeOperation
    data class SetImplantActive(val fitId: String, val slot: Int, val active: Boolean) : BridgeOperation
    data class RemoveImplant(val fitId: String, val slot: Int) : BridgeOperation
    data class AddProjection(
        val sourceId: String, val targetId: String, val rangeM: Double? = null,
        val active: Boolean = true, val amount: Int = 1,
    ) : BridgeOperation
    data class ConfigureProjection(
        val sourceId: String, val targetId: String, val rangeM: Double?,
        val active: Boolean, val amount: Int,
    ) : BridgeOperation
    data class RemoveProjection(val sourceId: String, val targetId: String) : BridgeOperation
    data class AddCommand(val sourceId: String, val targetId: String, val active: Boolean = true) : BridgeOperation
    data class SetCommandActive(val sourceId: String, val targetId: String, val active: Boolean) : BridgeOperation
    data class RemoveCommand(val sourceId: String, val targetId: String) : BridgeOperation
}

/** Copy caller-owned collections before enqueueing work on the engine thread. */
fun BridgeOperation.snapshotArguments(): BridgeOperation = when (this) {
    is BridgeOperation.Snapshot -> copy(fitIds = immutableList(fitIds))
    is BridgeOperation.CreateFit -> copy(spec = spec.copy(
        modules = immutableList(spec.modules), drones = immutableList(spec.drones),
    ))
    is BridgeOperation.SetCharges -> copy(moduleIndices = immutableList(moduleIndices))
    is BridgeOperation.SetModuleStates -> copy(moduleIndices = immutableList(moduleIndices))
    is BridgeOperation.SetBulkStates -> copy(moduleIndices = immutableList(moduleIndices))
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
        return obj("version" to VERSION, "request_id" to request.requestId, "session_id" to request.sessionId,
            "operation" to name, "expected_revisions" to revisions, "arguments" to arguments).toString()
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
            "modules", "drones", "target_profile", "implants", "boosters", "projections", "commands", "environments"), path = "spec")
        requireProtocol(value.get("target_profile") === JSONObject.NULL, "target_profile is unsupported")
        for (key in listOf("implants", "boosters", "projections", "commands", "environments")) {
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
                keys(module, setOf("name", "state"), setOf("charge"), "modules[$index]")
                ModuleSpec(nonempty(module.get("name"), "module.name"), enumValue<ModuleState>(module.get("state"), "module.state"),
                    if (module.has("charge")) nullable(module.get("charge"))?.let { nonempty(it, "module.charge") } else null)
            },
            array(value.get("drones"), "drones").mapIndexed { index, entry ->
                val drone = objectValue(entry, "drones[$index]")
                keys(drone, setOf("name", "amount", "active"), path = "drones[$index]")
                val amount = integer(drone.get("amount"), "drone.amount", 1)
                DroneSpec(nonempty(drone.get("name"), "drone.name"), amount,
                    integer(drone.get("active"), "drone.active", 0, amount))
            },
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
            "modules" to jsonArray(spec.modules.map { obj("name" to it.name, "state" to it.state.name, "charge" to it.charge) }),
            "drones" to jsonArray(spec.drones.map { obj("name" to it.name, "amount" to it.amount, "active" to it.active) }),
            "target_profile" to null, "implants" to JSONArray(), "boosters" to JSONArray(),
            "projections" to JSONArray(), "commands" to JSONArray(), "environments" to JSONArray(),
        )
        decodeFitSpec(value) // Keep construction and fixture decoding subject to the same shape checks.
        return value
    }

    private fun operation(operation: BridgeOperation): Pair<String, JSONObject> = when (operation) {
        is BridgeOperation.Snapshot -> {
            operation.fitIds.forEach { identifier(it, "fit_ids") }
            unique(operation.fitIds, "fit_ids")
            "snapshot" to obj("fit_ids" to jsonArray(operation.fitIds))
        }
        is BridgeOperation.RenameFit -> "rename_fit" to obj("fit_id" to operation.fitId, "name" to fitName(operation.name))
        is BridgeOperation.DuplicateFit -> "duplicate_fit" to obj("fit_id" to operation.fitId, "name" to fitName(operation.name))
        is BridgeOperation.DeleteFit -> "delete_fit" to obj("fit_id" to operation.fitId, "resolve_references" to operation.resolveReferences)
        is BridgeOperation.AddModule -> "add_module" to obj("fit_id" to operation.fitId,
            "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.ReplaceModule -> "replace_module" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0), "item_id" to integer(operation.itemId, "item_id", 1))
        is BridgeOperation.RemoveModule -> "remove_module" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0))
        is BridgeOperation.SetFitRestrictions -> "set_fit_restrictions" to obj("fit_id" to operation.fitId, "ignore" to operation.ignore)
        is BridgeOperation.CreateFit -> "create_fit" to obj("spec" to encodeFitSpec(operation.spec))
        is BridgeOperation.SetCharges -> "set_charges" to obj("fit_id" to operation.fitId,
            "module_indices" to indices(operation.moduleIndices), "charge" to operation.charge?.let { nonempty(it, "charge") })
        is BridgeOperation.SetModuleCharge -> "set_module_charge" to obj("fit_id" to operation.fitId,
            "position" to integer(operation.position, "position", 0),
            "charge_id" to operation.chargeId?.let { integer(it, "charge_id", 1) })
        is BridgeOperation.ChangeVariation -> "change_variation" to obj("fit_id" to operation.fitId,
            "context" to operation.context.wire, "position" to integer(operation.position, "position", 0),
            "item_id" to integer(operation.itemId, "item_id", 1))
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
        is BridgeOperation.AddImplant -> "add_implant" to obj("fit_id" to operation.fitId,
            "implant" to nonempty(operation.implant, "implant"), "active" to operation.active)
        is BridgeOperation.SetImplantActive -> "set_implant_active" to obj("fit_id" to operation.fitId,
            "slot" to integer(operation.slot, "slot", 1), "active" to operation.active)
        is BridgeOperation.RemoveImplant -> "remove_implant" to obj("fit_id" to operation.fitId,
            "slot" to integer(operation.slot, "slot", 1))
        is BridgeOperation.AddProjection -> "add_projection" to projectionArguments(
            operation.sourceId, operation.targetId, operation.rangeM, operation.active, operation.amount)
        is BridgeOperation.ConfigureProjection -> "configure_projection" to projectionArguments(
            operation.sourceId, operation.targetId, operation.rangeM, operation.active, operation.amount)
        is BridgeOperation.RemoveProjection -> "remove_projection" to endpoints(operation.sourceId, operation.targetId)
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

    fun decodeVariationOptions(json: String): VariationOptions {
        val value = objectValue(StrictJson(json).parse(), "variations")
        keys(value, setOf("version", "fit_id", "revision", "targets"), path = "variations")
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
        return VariationOptions(identifier(value.get("fit_id"), "fit_id"), revision, immutableList(targets))
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
private class StrictJson(private val input: String) {
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
