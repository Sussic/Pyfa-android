package io.github.sussic.pyfa

import org.json.JSONArray
import org.json.JSONObject

data class ProjectedChargeIdentity(val index: Int, val objectKey: String, val itemId: Int) {
    fun wire() = ProjectedModuleSelectionRow(index, objectKey)
}
enum class ProjectedChargeStatus { CHANGE, UNCHANGED, INCOMPATIBLE }
data class ProjectedChargeTarget(val identity: ProjectedChargeIdentity, val name: String,
    val chargeId: Int?, val chargeName: String?, val status: ProjectedChargeStatus)
data class ProjectedChargeExcluded(val identity: ProjectedChargeIdentity, val reason: String)
data class ProjectedModuleChargePreview(val fitId: String, val revision: Long, val main: ProjectedChargeIdentity,
    val selection: List<ProjectedChargeIdentity>, val scope: BulkScope, val chargeId: Int?,
    val choices: List<ProjectedModuleCharge>, val available: Boolean, val unavailableReason: String?,
    val targets: List<ProjectedChargeTarget>, val excluded: List<ProjectedChargeExcluded>)
data class ProjectedChargeCapture(val details: ProjectedModuleDetails, val selection: ProjectedModuleBulkSelection,
    val main: ProjectedModuleRow, val scope: BulkScope, val chargeId: Int?)

/** Source owns compatibility, subset/similar membership and per-row skips. */
internal object ProjectedModuleChargeCodec {
    fun failureMessage(failure: Throwable): String {
        if (generateSequence(failure) { it.cause }.take(8).any {
            it.message?.contains("Choose a reference module with compatible charges") == true
        }) return "Choose a reference module with compatible charges. This module has no charge or script choices."
        if (generateSequence(failure) { it.cause }.take(8).any {
            it.message?.contains("Projected-charge compatibility budget:") == true
        }) return "This charge preview exceeds the compatibility work budget. Reduce the selected configuration before retrying."
        return projectedDroneReadError(failure, "Charge preview could not be verified. Refresh before applying.")
    }
    private fun count(raw: Any) = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "invalid charge position")
    }.toInt()
    private fun id(raw: Any) = count(raw).also { OfflineFeatureCodec.expect(it > 0, "invalid charge item") }
    private fun nullableId(raw: Any) = if (raw === JSONObject.NULL) null else id(raw)
    private fun label(raw: Any) = OfflineFeatureCodec.text(raw).also { OfflineFeatureCodec.expect(it.isNotBlank(), "empty charge label") }
    private fun optionalLabel(raw: Any) = if (raw === JSONObject.NULL) null else label(raw)
    private fun rowIdentity(row: JSONObject) = ProjectedChargeIdentity(count(row.get("index")),
        ProjectedModuleCodec.objectKey(row.get("object_key")), id(row.get("item_id")))
    private fun identities(raw: Any): List<ProjectedChargeIdentity> = with(OfflineFeatureCodec) {
        val values = rows(raw); expect(values.size <= 1024, "too many charge rows")
        frozen(values.map { obj(it).let { row -> keys(row, "index", "object_key", "item_id"); rowIdentity(row) } })
    }
    private fun unique(values: List<ProjectedChargeIdentity>, ordered: Boolean = false) = with(OfflineFeatureCodec) {
        expect(values.size <= 1024 && values.map { it.index }.distinct().size == values.size &&
            values.map { it.objectKey }.distinct().size == values.size, "duplicate charge identity")
        if (ordered) expect(values.zipWithNext().all { (a,b) -> a.index < b.index }, "unordered charge targets")
    }
    fun decode(json: String): ProjectedModuleChargePreview = with(OfflineFeatureCodec) {
        val root = parse(json)
        keys(root, "version", "fit_id", "revision", "main", "selection", "scope", "charge_id", "choices",
            "available", "unavailable_reason", "targets", "excluded")
        expect(integer(root.get("version")) == 1L, "unsupported projected charge version")
        val fit = identity(root.get("fit_id")); val revision = integer(root.get("revision"))
        expect(revision >= 1, "invalid charge revision")
        val main = obj(root.get("main")).let { keys(it,"index","object_key","item_id"); rowIdentity(it) }
        val selection = identities(root.get("selection")); unique(selection)
        expect(selection.isNotEmpty() && main in selection, "charge main must be selected")
        val scope = BulkScope.entries.singleOrNull { it.name == text(root.get("scope")) } ?: reject("invalid charge scope")
        val charge = nullableId(root.get("charge_id"))
        val rawChoices = rows(root.get("choices")); expect(rawChoices.size <= 8192, "too many charge choices")
        val choices = rawChoices.map { obj(it).let { row -> keys(row,"id","name"); ProjectedModuleCharge(id(row.get("id")),label(row.get("name"))) } }
        expect(choices.map { it.id }.distinct().size == choices.size, "duplicate charge choice")
        val available = bool(root.get("available")); val reason = optionalLabel(root.get("unavailable_reason"))
        expect(available == (reason == null), "charge availability differs")
        if (available) expect(choices.isNotEmpty() && (charge == null || choices.any { it.id == charge }), "unavailable charge choice")
        val rawTargets = rows(root.get("targets")); expect(rawTargets.size <= 1024, "too many charge targets")
        val targets = rawTargets.map { obj(it).let { row ->
            keys(row,"index","object_key","item_id","name","charge_id","charge_name","status")
            val loaded = nullableId(row.get("charge_id")); val name = optionalLabel(row.get("charge_name"))
            expect((loaded == null) == (name == null), "loaded charge fields differ")
            val status = ProjectedChargeStatus.entries.singleOrNull { it.name.lowercase() == text(row.get("status")) }
                ?: reject("invalid charge target status")
            expect((status == ProjectedChargeStatus.UNCHANGED) == (loaded == charge), "unchanged charge differs")
            expect(status != ProjectedChargeStatus.CHANGE || loaded != charge, "changed charge is identical")
            ProjectedChargeTarget(rowIdentity(row),label(row.get("name")),loaded,name,status)
        } }
        val rawExcluded = rows(root.get("excluded")); expect(rawExcluded.size <= 1024, "too many excluded charge rows")
        val excluded = rawExcluded.map { obj(it).let { row ->
            keys(row,"index","object_key","item_id","reason"); ProjectedChargeExcluded(rowIdentity(row),label(row.get("reason")))
        } }
        unique(targets.map { it.identity }, true); unique(excluded.map { it.identity }, true)
        unique(targets.map { it.identity } + excluded.map { it.identity })
        ProjectedModuleChargePreview(fit,revision,main,selection,scope,charge,frozen(choices),available,reason,frozen(targets),frozen(excluded))
    }
    fun wireRows(values: List<ProjectedModuleSelectionRow>, allowEmpty: Boolean = false): JSONArray = with(OfflineFeatureCodec) {
        expect(values.size in (if (allowEmpty) 0 else 1)..1024, "invalid charge selection size")
        expect(values.map { it.position }.distinct().size == values.size && values.map { it.objectKey }.distinct().size == values.size,
            "duplicate charge selection")
        JSONArray().also { array -> values.forEach { row ->
            expect(row.position >= 0, "negative charge position"); ProjectedModuleCodec.objectKey(row.objectKey)
            array.put(JSONObject().put("position",row.position).put("object_key",row.objectKey))
        } }
    }
    fun request(main: ProjectedModuleSelectionRow, selection: List<ProjectedModuleSelectionRow>, scope: BulkScope, chargeId: Int?): JSONObject {
        OfflineFeatureCodec.expect(main in selection && (chargeId == null || chargeId > 0), "invalid charge request")
        return JSONObject().put("main",wireRows(listOf(main)).getJSONObject(0)).put("selection",wireRows(selection))
            .put("scope",scope.name).put("charge_id",chargeId ?: JSONObject.NULL)
    }
    fun correlate(value: ProjectedModuleChargePreview, capture: ProjectedChargeCapture) = with(OfflineFeatureCodec) {
        val d=capture.details; val s=capture.selection; val main=capture.main
        fun identityOf(row: ProjectedModuleRow) = ProjectedChargeIdentity(row.index,row.objectKey,row.itemId)
        expect(!d.isStructure && d.fitId==s.fitId && d.revision==s.revision && s.rows.isNotEmpty() &&
            s.rows.all { row -> row.editable && d.modules.any { it === row } } && s.rows.any { it === main }, "stale charge capture")
        expect(value.fitId==d.fitId && value.revision==d.revision && value.main==identityOf(main) &&
            value.selection==s.rows.map(::identityOf) && value.scope==capture.scope && value.chargeId==capture.chargeId,
            "charge preview capture differs")
        fun row(identity: ProjectedChargeIdentity): ProjectedModuleRow = d.modules.singleOrNull { identityOf(it)==identity }
            ?: reject("charge target identity differs")
        value.targets.forEach { target -> val r=row(target.identity)
            expect(r.name==target.name && r.chargeId==target.chargeId && r.chargeName==target.chargeName, "charge target inputs differ")
            expect(!value.available || r.editable, "read-only charge target")
        }
        value.excluded.forEach { row(it.identity) }
        val selected=value.selection.toSet(); val targets=value.targets.map { it.identity }.toSet()
        expect(value.excluded.map { it.identity }.toSet()==selected-targets, "charge exclusions differ")
        if (value.scope==BulkScope.SELECTED) expect(targets.all { it in selected }, "unselected charge target")
        if (value.available) expect(value.main in targets, "charge main not resolved")
    }
}
