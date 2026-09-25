package io.github.sussic.pyfa

data class HullModeChoice(val id: Int, val name: String)
data class ModeOptions(val fitId: String, val revision: Long, val current: Int?,
    val choices: List<HullModeChoice>)
