package io.github.sussic.pyfa

enum class StateClick(val wire: String) { CYCLE("left"), OVERHEAT("right"), OFFLINE("ctrl") }

data class BulkModuleStates(val index: Int, val itemId: Int?, val state: ModuleState?, val editable: Boolean,
    val similarCandidates: List<Int>, val clickStates: Map<StateClick, ModuleState>,
    val supportedStates: Map<ModuleState, ModuleState>)

data class BulkStateOptions(val fitId: String, val revision: Long, val modules: List<BulkModuleStates>)
