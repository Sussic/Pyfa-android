package io.github.sussic.pyfa

import org.json.JSONObject

data class ProjectedFighterRow(val index: Int, val objectKey: String, val itemId: Int, val name: String,
    val amount: Int, val maxSize: Int, val active: Boolean, val rangeM: Double?, val editable: Boolean, val unavailableReason: String?)
data class ProjectedFighterDetails(val fitId: String, val revision: Long, val isStructure: Boolean,
    val squadrons: List<ProjectedFighterRow>)
data class ProjectedFighterVariation(val id: Int, val name: String, val enabled: Boolean)
data class ProjectedFighterOptions(val fitId: String, val revision: Long, val index: Int, val objectKey: String,
    val itemId: Int, val abilities: List<FighterAbility>,
    val variations: List<ProjectedFighterVariation>)
data class ProjectedFighterAddOptions(val fitId: String, val revision: Long, val itemId: Int,
    val isFighter: Boolean, val isProjectable: Boolean, val isStructure: Boolean,
    val enabled: Boolean, val unavailableReason: String?)

/** Surface only the fixed native evaluation-refusal family, never arbitrary Python text. */
internal fun projectedFighterReadError(failure: Throwable, fallback: String): String =
    if (generateSequence(failure) { it.cause }.take(8).any { error -> error.message?.let {
        it.contains("Projected-drone evaluation budget:") || it.contains("Projected-drone capacitor evaluation budget:")
    } == true }) "This configuration exceeds the incoming-projector evaluation budget. Reduce its quantity or complexity before retrying."
    else fallback

/** Counts are source inputs. Storage and evaluation limits are not game fitting limits. */
internal object ProjectedFighterCodec {
    private fun count(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "invalid projected fighter integer")
    }.toInt()
    private fun id(raw: Any) = count(raw).also { OfflineFeatureCodec.expect(it > 0, "invalid projected item ID") }
    private fun label(raw: Any) = OfflineFeatureCodec.text(raw).also { OfflineFeatureCodec.expect(it.isNotBlank(), "empty projected label") }
    private fun reason(raw: Any): String? = if (raw === JSONObject.NULL) null else label(raw)
    private fun revision(raw: Any) = OfflineFeatureCodec.integer(raw).also { OfflineFeatureCodec.expect(it >= 1, "invalid projected revision") }
    private fun range(raw: Any): Double? {
        if (raw === JSONObject.NULL) return null
        val value = when (raw) { is Int -> raw.toDouble(); is Long -> raw.toDouble(); is Double -> raw
            else -> OfflineFeatureCodec.reject("projected range number required") }
        OfflineFeatureCodec.expect(value.isFinite() && value >= 0, "invalid projected range")
        if (raw is Long) OfflineFeatureCodec.expect(java.math.BigDecimal(raw).compareTo(java.math.BigDecimal(value)) == 0,
            "projected range integer loses precision")
        return value
    }
    private fun header(root: JSONObject): Pair<String, Long> = with(OfflineFeatureCodec) {
        expect(integer(root.get("version")) == 1L, "unsupported projected-fighter version")
        identity(root.get("fit_id")) to revision(root.get("revision"))
    }
    fun details(json: String): ProjectedFighterDetails = with(OfflineFeatureCodec) {
        val root = parse(json); keys(root, "version", "fit_id", "revision", "is_structure", "squadrons")
        val (fit, revision) = header(root); val structure = bool(root.get("is_structure"))
        val rawRows = rows(root.get("squadrons")); expect(rawRows.size <= 1024, "too many projected fighter squadrons")
        val squadrons = rawRows.mapIndexed { position, raw ->
            val row = obj(raw)
            keys(row, "index", "object_key", "item_id", "name", "amount", "max_size", "active", "range_m", "editable", "unavailable_reason")
            val index = count(row.get("index")); expect(index == position, "projected squadron position differs")
            val amount = count(row.get("amount")); val maxSize = count(row.get("max_size")); val active = bool(row.get("active"))
            val editable = bool(row.get("editable")); val why = reason(row.get("unavailable_reason"))
            expect(editable == (why == null) && (!structure || !editable), "projected availability differs")
            ProjectedFighterRow(index, ProjectedModuleCodec.objectKey(row.get("object_key")), id(row.get("item_id")),
                label(row.get("name")), amount, maxSize, active, range(row.get("range_m")), editable, why)
        }
        expect(squadrons.map { it.objectKey }.distinct().size == squadrons.size, "duplicate projected identity")
        ProjectedFighterDetails(fit, revision, structure, frozen(squadrons))
    }
    fun options(json: String): ProjectedFighterOptions = with(OfflineFeatureCodec) {
        val root = parse(json)
        keys(root, "version", "fit_id", "revision", "index", "object_key", "item_id", "abilities", "variations")
        val (fit, revision) = header(root)
        val rawAbilities = rows(root.get("abilities")); expect(rawAbilities.size <= 128, "too many projected fighter abilities")
        val abilities = rawAbilities.map { raw ->
            val row = obj(raw); keys(row, "effect_id", "name", "active")
            FighterAbility(id(row.get("effect_id")), label(row.get("name")), bool(row.get("active")))
        }
        expect(abilities.map { it.effectId }.distinct().size == abilities.size, "duplicate projected fighter ability")
        val rawChoices = rows(root.get("variations")); expect(rawChoices.size <= 8192, "too many projected fighter variations")
        val choices = rawChoices.map { raw ->
            val row = obj(raw); keys(row, "id", "name", "enabled")
            ProjectedFighterVariation(id(row.get("id")), label(row.get("name")), bool(row.get("enabled")))
        }
        expect(choices.map { it.id }.distinct().size == choices.size, "duplicate projected variation")
        val index = count(root.get("index")); expect(index < 1024, "projected squadron position exceeds storage boundary")
        ProjectedFighterOptions(fit, revision, index, ProjectedModuleCodec.objectKey(root.get("object_key")),
            id(root.get("item_id")), frozen(abilities), frozen(choices))
    }
    fun addOptions(json: String): ProjectedFighterAddOptions = with(OfflineFeatureCodec) {
        val root = parse(json)
        keys(root, "version", "fit_id", "revision", "item_id", "is_fighter", "is_projectable", "is_structure", "enabled", "unavailable_reason")
        val (fit, revision) = header(root)
        val fighter = bool(root.get("is_fighter")); val projectable = bool(root.get("is_projectable"))
        val structure = bool(root.get("is_structure")); val enabled = bool(root.get("enabled")); val why = reason(root.get("unavailable_reason"))
        expect(enabled == (why == null) && (!enabled || fighter && projectable && !structure), "projected add availability differs")
        ProjectedFighterAddOptions(fit, revision, id(root.get("item_id")), fighter, projectable, structure, enabled, why)
    }
}
