package io.github.sussic.pyfa

data class StructureServiceChoice(val id: Int, val name: String)
data class StructureServiceOptions(val fitId: String, val revision: Long,
    val isStructure: Boolean, val capacity: Int, val choices: List<StructureServiceChoice>)
