package io.github.sussic.pyfa

data class CargoStack(val id: Int, val name: String, val amount: Long, val unitVolumeM3: Double)
enum class CargoTransferDirection { TO_CARGO, FROM_CARGO }
data class CargoTransferModule(val index: Int, val id: Int?, val name: String?, val slot: String,
    val state: ModuleState, val chargeId: Int?, val charge: String?, val chargeAmount: Long, val legal: Boolean?)
data class CargoTransferDetails(val cargo: CargoDetails, val modules: List<CargoTransferModule>)
data class CargoDetails(val fitId: String, val revision: Long, val isStructure: Boolean, val capacityM3: Double,
    val usedM3: Double, val overCapacity: Boolean, val cargo: List<CargoStack>)

data class CargoActionOptions(val fitId: String, val revision: Long, val itemId: Int,
    val fromCargo: Boolean, val presetQuantity: Long?, val fillQuantity: Long?,
    val variations: List<VariationChoice>)
