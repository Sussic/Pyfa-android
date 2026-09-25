package io.github.sussic.pyfa

enum class ModuleSlot(val label: String) {
    LOW("Low"), MED("Medium"), HIGH("High"), RIG("Rig"), SERVICE("Service"), SUBSYSTEM("Subsystems");
    val editable: Boolean get() = this != SUBSYSTEM
}

data class ResourceUse(val used: StatValue, val total: StatValue, val unit: String, val overloaded: Boolean)
data class SlotUse(val slot: ModuleSlot, val used: Int, val total: StatValue)
data class HardpointUse(val kind: String, val used: Int, val total: StatValue)
data class SkillRequirement(val id: Int, val name: String, val required: Int, val actual: Int,
    val requirements: List<SkillRequirement>)
data class SkillWarning(val id: Int, val name: String, val requirements: List<SkillRequirement>)
data class FittingModule(val index: Int, val id: Int?, val name: String?, val slot: ModuleSlot,
    val state: ModuleState, val charge: String?, val legal: Boolean?, val overridden: Boolean)
data class FittingDetails(val fitId: String, val revision: Long, val ignoreRestrictions: Boolean,
    val modules: List<FittingModule>, val resources: Map<String, ResourceUse>, val slots: List<SlotUse>,
    val hardpoints: List<HardpointUse>, val skillWarnings: List<SkillWarning>)
data class ModuleDefault(val id: Int, val name: String, val slot: ModuleSlot,
    val state: ModuleState, val limit: ModuleState)
data class FillItemOptions(val fitId: String, val revision: Long, val itemId: Int,
    val slot: ModuleSlot, val vacancies: Int, val ignoreRestrictions: Boolean)
data class CloneVacancy(val index: Int, val slot: ModuleSlot)
data class CloneVacancyOptions(val fitId: String, val revision: Long, val vacancies: List<CloneVacancy>)
