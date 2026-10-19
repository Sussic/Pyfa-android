package io.github.sussic.pyfa

import org.json.JSONArray
import org.json.JSONObject

enum class ProjectedModuleStateAction(val wire: String) { INACTIVE("inactive"), ACTIVE("active"), OVERHEAT("overheat") }
data class ProjectedModuleRow(val index: Int, val objectKey: String, val itemId: Int, val name: String,
    val state: ModuleState, val chargeId: Int?, val chargeName: String?, val rangeM: Double?,
    val editable: Boolean, val unavailableReason: String?)
data class ProjectedModuleDetails(val fitId: String, val revision: Long, val isStructure: Boolean,
    val modules: List<ProjectedModuleRow>)
data class ProjectedModuleAction(val id: ProjectedModuleStateAction, val label: String, val enabled: Boolean)
data class ProjectedModuleCharge(val id: Int, val name: String)
data class ProjectedModuleVariation(val id: Int, val name: String, val enabled: Boolean)
data class ProjectedModuleOptions(val fitId: String, val revision: Long, val index: Int, val objectKey: String,
    val itemId: Int, val stateActions: List<ProjectedModuleAction>, val charges: List<ProjectedModuleCharge>,
    val variations: List<ProjectedModuleVariation>, val spool: ModuleSpoolRow?)
data class ProjectedModuleAddOptions(val fitId: String, val revision: Long, val itemId: Int,
    val isModule: Boolean, val isProjectable: Boolean, val isStructure: Boolean,
    val enabled: Boolean, val unavailableReason: String?)

/** Only fixed engine-unavailable messages, never arbitrary Python text, affect readiness. */
internal fun projectedReadRequiresReopen(failure: Throwable): Boolean = generateSequence(failure) { it.cause }.take(8).any {
    it.message?.let { message -> message.contains("Restart the fitting engine") || message.contains("Reopen the profile fit graph") } == true
}

/** No projected state/charge/variation or spool calculation is reproduced in Kotlin. */
internal object ProjectedModuleCodec {
    private fun count(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "invalid projected module integer")
    }.toInt()
    private fun id(raw: Any) = count(raw).also { OfflineFeatureCodec.expect(it > 0, "invalid projected item ID") }
    private fun label(raw: Any) = OfflineFeatureCodec.text(raw).also { OfflineFeatureCodec.expect(it.isNotBlank(), "empty projected label") }
    private fun reason(raw: Any): String? = if (raw === JSONObject.NULL) null else label(raw)
    private fun revision(raw: Any) = OfflineFeatureCodec.integer(raw).also { OfflineFeatureCodec.expect(it >= 1, "invalid projected revision") }
    internal fun objectKey(raw: Any) = OfflineFeatureCodec.text(raw).also {
        OfflineFeatureCodec.expect(it.matches(Regex("[0-9a-f]{32}")), "invalid projected object identity")
    }
    private fun range(raw: Any): Double? {
        if (raw === JSONObject.NULL) return null
        val value = when (raw) { is Int -> raw.toDouble(); is Long -> raw.toDouble(); is Double -> raw
            else -> OfflineFeatureCodec.reject("projected range number required") }
        OfflineFeatureCodec.expect(value.isFinite() && value >= 0, "invalid projected range")
        return value
    }
    private fun header(root: JSONObject): Pair<String, Long> = with(OfflineFeatureCodec) {
        expect(integer(root.get("version")) == 1L, "unsupported projected-module version")
        identity(root.get("fit_id")) to revision(root.get("revision"))
    }
    fun details(json: String): ProjectedModuleDetails = with(OfflineFeatureCodec) {
        val root = parse(json); keys(root, "version", "fit_id", "revision", "is_structure", "modules")
        val (fit, revision) = header(root); val structure = bool(root.get("is_structure"))
        val rawRows = rows(root.get("modules")); expect(rawRows.size <= 1024, "too many projected modules")
        val modules = rawRows.map { raw ->
            val row = obj(raw)
            keys(row, "index", "object_key", "item_id", "name", "state", "charge_id", "charge_name", "range_m", "editable", "unavailable_reason")
            val state = ModuleState.entries.singleOrNull { it.name == text(row.get("state")) }
                ?: reject("unknown projected state")
            val charge = if (row.get("charge_id") === JSONObject.NULL) null else id(row.get("charge_id"))
            val chargeName = reason(row.get("charge_name"))
            expect((charge == null) == (chargeName == null), "projected charge availability differs")
            val editable = bool(row.get("editable")); val why = reason(row.get("unavailable_reason"))
            expect(editable == (why == null) && (!structure || !editable), "projected availability differs")
            ProjectedModuleRow(count(row.get("index")), objectKey(row.get("object_key")), id(row.get("item_id")),
                label(row.get("name")), state, charge, chargeName, range(row.get("range_m")), editable, why)
        }
        expect(modules.zipWithNext().all { (a, b) -> a.index < b.index }, "unordered projected modules")
        expect(modules.map { it.objectKey }.distinct().size == modules.size, "duplicate projected identity")
        ProjectedModuleDetails(fit, revision, structure, frozen(modules))
    }
    fun options(json: String): ProjectedModuleOptions = with(OfflineFeatureCodec) {
        val root = parse(json)
        keys(root, "version", "fit_id", "revision", "index", "object_key", "item_id", "state_actions", "charges", "variations", "spool")
        val (fit, revision) = header(root)
        val index = count(root.get("index")); val key = objectKey(root.get("object_key")); val item = id(root.get("item_id"))
        val actions = rows(root.get("state_actions")).map { raw ->
            val row = obj(raw); keys(row, "id", "label", "enabled")
            val action = ProjectedModuleStateAction.entries.singleOrNull { it.wire == text(row.get("id")) }
                ?: reject("unknown projected state action")
            ProjectedModuleAction(action, label(row.get("label")), bool(row.get("enabled")))
        }
        expect(actions.size <= 3 && actions.map { it.id }.distinct().size == actions.size, "duplicate projected state action")
        val rawCharges = rows(root.get("charges")); expect(rawCharges.size <= 8192, "too many projected charge choices")
        val charges = rawCharges.map { raw ->
            val row = obj(raw); keys(row, "id", "name"); ProjectedModuleCharge(id(row.get("id")), label(row.get("name")))
        }
        expect(charges.map { it.id }.distinct().size == charges.size, "duplicate projected charge choice")
        val rawVariations = rows(root.get("variations")); expect(rawVariations.size <= 8192, "too many projected variation choices")
        val variations = rawVariations.map { raw ->
            val row = obj(raw); keys(row, "id", "name", "enabled")
            ProjectedModuleVariation(id(row.get("id")), label(row.get("name")), bool(row.get("enabled")))
        }
        expect(variations.map { it.id }.distinct().size == variations.size, "duplicate projected variation choice")
        // Reuse the exact existing strict spool decoder for this one selected object.
        val spool = if (root.get("spool") === JSONObject.NULL) null else ModuleSpoolCodec.decode(JSONObject()
            .put("version", 1).put("fit_id", fit).put("revision", revision)
            .put("modules", JSONArray().put(obj(root.get("spool")))).toString()).modules.single().also {
                expect(it.index == index && it.objectKey == key && it.itemId == item, "projected spool identity differs")
            }
        ProjectedModuleOptions(fit, revision, index, key, item, frozen(actions), frozen(charges), frozen(variations), spool)
    }
    fun addOptions(json: String): ProjectedModuleAddOptions = with(OfflineFeatureCodec) {
        val root = parse(json)
        keys(root, "version", "fit_id", "revision", "item_id", "is_module", "is_projectable", "is_structure", "enabled", "unavailable_reason")
        val (fit, revision) = header(root)
        val module = bool(root.get("is_module")); val projectable = bool(root.get("is_projectable"))
        val structure = bool(root.get("is_structure")); val enabled = bool(root.get("enabled")); val why = reason(root.get("unavailable_reason"))
        expect(enabled == (why == null) && (!enabled || module && projectable && !structure), "projected add availability differs")
        ProjectedModuleAddOptions(fit, revision, id(root.get("item_id")), module, projectable, structure, enabled, why)
    }
}
