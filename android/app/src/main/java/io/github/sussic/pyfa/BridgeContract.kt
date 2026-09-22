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
    data class SetCharges(val fitId: String, val moduleIndices: List<Int>, val charge: String?) : BridgeOperation
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
data class ModuleSnapshot(val index: Int, val name: String, val charge: String?, val state: ModuleState)
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
        is BridgeOperation.CreateFit -> "create_fit" to obj("spec" to encodeFitSpec(operation.spec))
        is BridgeOperation.SetCharges -> "set_charges" to obj("fit_id" to operation.fitId,
            "module_indices" to indices(operation.moduleIndices), "charge" to operation.charge?.let { nonempty(it, "charge") })
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
            keys(module, setOf("index", "name", "charge", "state"), path = "$path.modules[$index]")
            val position = integer(module.get("index"), "module.index", 0)
            requireProtocol(position == index, "Module indices must match their array positions")
            ModuleSnapshot(position, nonempty(module.get("name"), "module.name"),
                nullable(module.get("charge"))?.let { nonempty(it, "module.charge") },
                enumValue<ModuleState>(module.get("state"), "module.state"))
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
