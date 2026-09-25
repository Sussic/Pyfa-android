package io.github.sussic.pyfa

enum class BulkScope { SELECTED, SIMILAR }

data class BulkModuleCharges(val index: Int, val itemId: Int?, val chargeId: Int?, val chargeIds: List<Int>,
    val selectionCandidates: List<Int>, val similarCandidates: List<Int>)

data class BulkChargeOptions(val fitId: String, val revision: Long, val modules: List<BulkModuleCharges>,
    val items: List<ChargeItem>)
