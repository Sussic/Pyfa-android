package io.github.sussic.pyfa

import org.json.JSONObject

enum class ImplantLocation { FIT, CHARACTER }
data class ImplantRow(val index: Int, val objectKey: String, val itemId: Int, val name: String, val slot: Int, val active: Boolean)
data class ImplantDetails(val fitId: String, val revision: Long, val isStructure: Boolean,
    val location: ImplantLocation, val implants: List<ImplantRow>) {
    val editable get() = !isStructure && location == ImplantLocation.FIT
    val displayRows get() = implants.sortedBy { it.slot }
}
data class ImplantOccupant(val index: Int, val objectKey: String, val itemId: Int, val name: String)
data class ImplantAddOptions(val fitId: String, val revision: Long, val itemId: Int, val isImplant: Boolean,
    val isStructure: Boolean, val location: ImplantLocation, val slot: Int?, val occupant: ImplantOccupant?, val alreadyFitted: Boolean) {
    val editable get() = !isStructure && isImplant
    val sourceOnly get() = editable && location == ImplantLocation.CHARACTER && alreadyFitted
    val canAdd get() = editable && (!alreadyFitted || sourceOnly)
}

internal object ImplantDetailsCodec {
    private fun count(raw: Any): Int = OfflineFeatureCodec.integer(raw).also {
        OfflineFeatureCodec.expect(it in 0..Int.MAX_VALUE.toLong(), "invalid implant integer")
    }.toInt()
    private fun id(raw: Any): Int = count(raw).also { OfflineFeatureCodec.expect(it > 0, "invalid implant ID or slot") }
    private fun name(raw: Any): String = OfflineFeatureCodec.text(raw).also { OfflineFeatureCodec.expect(it.isNotBlank(), "empty implant label") }
    private fun revision(raw: Any) = OfflineFeatureCodec.integer(raw).also { OfflineFeatureCodec.expect(it >= 1, "invalid implant revision") }
    private fun location(raw: Any): ImplantLocation = ImplantLocation.entries.singleOrNull { it.name == OfflineFeatureCodec.text(raw) }
        ?: OfflineFeatureCodec.reject("invalid implant location")
    fun details(json: String): ImplantDetails = with(OfflineFeatureCodec) {
        val root = parse(json); keys(root, "version", "fit_id", "revision", "is_structure", "location", "implants")
        expect(integer(root.get("version")) == 1L, "unsupported implant details version")
        val implants = rows(root.get("implants")).mapIndexed { index, raw ->
            val row = obj(raw); keys(row, "index", "object_key", "item_id", "name", "slot", "active")
            expect(count(row.get("index")) == index, "unordered implant indices")
            ImplantRow(index, identity(row.get("object_key")), id(row.get("item_id")), name(row.get("name")), id(row.get("slot")), bool(row.get("active")))
        }
        expect(implants.map { it.objectKey }.distinct().size == implants.size, "duplicate implant identity")
        expect(implants.map { it.slot }.distinct().size == implants.size, "duplicate implant slot")
        expect(implants.map { it.itemId }.distinct().size == implants.size, "duplicate fitted implant")
        ImplantDetails(identity(root.get("fit_id")), revision(root.get("revision")), bool(root.get("is_structure")),
            location(root.get("location")), frozen(implants))
    }
    fun addOptions(json: String): ImplantAddOptions = with(OfflineFeatureCodec) {
        val root = parse(json)
        keys(root, "version", "fit_id", "revision", "item_id", "is_implant", "is_structure", "location", "slot", "occupant", "already_fitted")
        expect(integer(root.get("version")) == 1L, "unsupported implant add version")
        val itemId = id(root.get("item_id")); val isImplant = bool(root.get("is_implant"))
        val slot = if (root.isNull("slot")) null else id(root.get("slot"))
        val occupant = if (root.isNull("occupant")) null else obj(root.get("occupant")).let { row ->
            keys(row, "index", "object_key", "item_id", "name")
            ImplantOccupant(count(row.get("index")), identity(row.get("object_key")), id(row.get("item_id")), name(row.get("name")))
        }
        val already = bool(root.get("already_fitted"))
        expect(isImplant == (slot != null), "implant slot applicability differs")
        expect(isImplant || occupant == null && !already, "nonimplant has fitting state")
        expect(already == (occupant?.itemId == itemId), "already-fitted implant identity differs")
        ImplantAddOptions(identity(root.get("fit_id")), revision(root.get("revision")), itemId, isImplant,
            bool(root.get("is_structure")), location(root.get("location")), slot, occupant, already)
    }
}
