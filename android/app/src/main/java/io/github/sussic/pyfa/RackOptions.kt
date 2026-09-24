package io.github.sussic.pyfa

data class HeatProbability(val seconds: Double, val value: Double)
data class HeatEstimate(val cycles: Stat, val seconds: Stat, val probabilities: List<HeatProbability>)
data class RackModule(val index: Int, val id: Int?, val name: String?, val slot: ModuleSlot,
    val state: ModuleState, val chargeId: Int?, val charge: String?, val heat: HeatEstimate?)
data class RackOptions(val fitId: String, val revision: Long, val modules: List<RackModule>)
