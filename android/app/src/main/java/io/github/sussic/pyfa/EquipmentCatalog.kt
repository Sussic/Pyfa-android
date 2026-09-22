package io.github.sussic.pyfa

import org.json.JSONObject

data class EquipmentGroup(val id: Int, val name: String, val parentId: Int?, val itemIds: List<Int>)
data class EquipmentItem(val id: Int, val name: String, val category: String, val metaId: Int,
    val meta: String, val parentId: Int, val marketGroupId: Int?, val searchable: Boolean)
data class EquipmentCatalog(val roots: List<Int>, val groups: List<EquipmentGroup>, val items: List<EquipmentItem>) {
    val groupById = groups.associateBy { it.id }
    val itemById = items.associateBy { it.id }
    fun children(id: Int?) = groups.filter { it.parentId == id }.sortedBy { it.name.lowercase() }
    fun path(id: Int): List<EquipmentGroup> {
        val result = mutableListOf<EquipmentGroup>()
        var current: Int? = id
        while (current != null) {
            val group = checkNotNull(groupById[current])
            check(result.none { it.id == current }) { "Cyclic equipment groups" }
            result += group
            current = group.parentId
        }
        return result.reversed()
    }
    companion object {
        val metas = listOf("Normal", "Faction", "Complex", "Officer")
        fun decode(text: String): EquipmentCatalog {
            val value = JSONObject(text)
            check(value.getInt("version") == 1)
            fun ints(key: String) = value.getJSONArray(key).let { rows -> (0 until rows.length()).map { rows.getInt(it) } }
            val roots = ints("roots")
            val groups = value.getJSONArray("groups").let { rows -> (0 until rows.length()).map {
                val row = rows.getJSONObject(it)
                EquipmentGroup(row.getInt("id"), row.getString("name"),
                    if (row.isNull("parent_id")) null else row.getInt("parent_id"),
                    row.getJSONArray("item_ids").let { ids -> (0 until ids.length()).map { ids.getInt(it) } })
            } }
            val items = value.getJSONArray("items").let { rows -> (0 until rows.length()).map {
                val row = rows.getJSONObject(it)
                EquipmentItem(row.getInt("id"), row.getString("name"), row.getString("category"),
                    row.getInt("meta_id"), row.getString("meta"), row.getInt("parent_id"),
                    if (row.isNull("market_group_id")) null else row.getInt("market_group_id"), row.getBoolean("searchable"))
            } }
            val result = EquipmentCatalog(roots, groups, items)
            check(roots.distinct().size == roots.size && groups.size == result.groupById.size && items.size == result.itemById.size)
            check(roots.toSet() == groups.filter { it.parentId == null }.map { it.id }.toSet())
            check(items.all { it.id > 0 && it.name.isNotBlank() && it.meta in metas })
            for (group in groups) {
                check(group.id > 0 && group.name.isNotBlank())
                check(group.itemIds.distinct().size == group.itemIds.size && group.itemIds.all { it in result.itemById })
                result.path(group.id) // Reject orphan/cyclic parent chains before publishing.
            }
            return result
        }
    }
}
