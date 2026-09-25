package io.github.sussic.pyfa

data class SubsystemChoice(val id: Int, val name: String)
data class SubsystemGroup(val kind: Int, val name: String, val current: Int?,
    val choices: List<SubsystemChoice>)
data class SubsystemOptions(val fitId: String, val revision: Long, val capacity: Int,
    val groups: List<SubsystemGroup>)
