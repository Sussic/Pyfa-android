package io.github.sussic.pyfa

enum class VariationContext(val wire: String, val label: String) {
    MODULE("module", "Modules"), DRONE("drone", "Drones"), IMPLANT("implant", "Fit implants")
}
data class VariationChoice(val id: Int, val name: String, val group: String?, val enabled: Boolean)
sealed interface VariationInput {
    data class Module(val state: ModuleState, val chargeId: Int?) : VariationInput
    data class Drone(val amount: Int, val active: Int) : VariationInput
    data class Implant(val slot: Int, val active: Boolean, val location: String) : VariationInput
}
data class VariationTarget(
    val context: VariationContext, val index: Int, val itemId: Int, val name: String,
    val current: VariationInput, val choices: List<VariationChoice>,
)
data class VariationOptions(val fitId: String, val revision: Long, val targets: List<VariationTarget>)
data class VariationFamily(val id: Int, val context: VariationContext, val choices: List<VariationChoice>)
