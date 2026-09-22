package io.github.sussic.pyfa

data class ChargeItem(val id: Int, val name: String)
data class ModuleCharges(val index: Int, val itemId: Int?, val chargeId: Int?, val chargeIds: List<Int>)
data class ChargeOptions(val fitId: String, val revision: Long, val modules: List<ModuleCharges>, val items: List<ChargeItem>)
data class ChargeCompatibility(val id: Int, val chargeIds: List<Int>)
