package io.github.sussic.pyfa

data class CargoStack(val id: Int, val name: String, val amount: Long, val unitVolumeM3: Double)
data class CargoDetails(val fitId: String, val revision: Long, val isStructure: Boolean, val capacityM3: Double,
    val usedM3: Double, val overCapacity: Boolean, val cargo: List<CargoStack>)
