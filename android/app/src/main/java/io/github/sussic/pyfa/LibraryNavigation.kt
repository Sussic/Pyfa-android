package io.github.sussic.pyfa

import android.util.AtomicFile
import java.io.File
import org.json.JSONArray
import org.json.JSONObject

data class HullGroup(val id: Int, val name: String)
data class Hull(val id: Int, val name: String, val groupId: Int, val race: String?)
data class HullCatalog(val groups: List<HullGroup> = emptyList(), val hulls: List<Hull> = emptyList()) {
    companion object {
        fun decode(text: String): HullCatalog {
            val value = JSONObject(text)
            check(value.getInt("version") == 1)
            val groups = value.getJSONArray("groups").let { rows -> (0 until rows.length()).map {
                rows.getJSONObject(it).let { row -> HullGroup(row.getInt("id"), row.getString("name")) }
            } }
            val hulls = value.getJSONArray("hulls").let { rows -> (0 until rows.length()).map {
                rows.getJSONObject(it).let { row -> Hull(row.getInt("id"), row.getString("name"),
                    row.getInt("group_id"), if (row.isNull("race")) null else row.getString("race")) }
            } }
            check(groups.map { it.id }.distinct().size == groups.size)
            check(hulls.map { it.id }.distinct().size == hulls.size)
            check(hulls.all { hull -> groups.any { it.id == hull.groupId } })
            return HullCatalog(groups, hulls)
        }
    }
}

data class LibraryNavigation(
    val openIds: List<String> = emptyList(),
    val activeId: String? = null,
    val restore: Boolean = false,
    val hideEmpty: Boolean = false,
) {
    fun retain(ids: Set<String>): LibraryNavigation {
        val kept = openIds.filter { it in ids }.distinct()
        return copy(openIds = kept, activeId = activeId?.takeIf { it in kept } ?: kept.lastOrNull())
    }
    fun open(id: String) = copy(openIds = if (id in openIds) openIds else openIds + id, activeId = id)
    fun close(id: String): LibraryNavigation {
        val kept = openIds - id
        val replacement = if (activeId == id) kept.getOrNull((openIds.indexOf(id) - 1).coerceAtLeast(0)) else activeId
        return copy(openIds = kept, activeId = replacement).retain(kept.toSet())
    }
}

/** Small view preferences are separate from fit inputs. All I/O uses the EOS worker. */
internal class NavigationStore(path: File) {
    private val file = AtomicFile(path)
    fun load(): LibraryNavigation? {
        if (!file.baseFile.exists() && !File(file.baseFile.path + ".bak").exists()) return null
        val value = JSONObject(file.openRead().bufferedReader().use { it.readText() })
        check(value.keys().asSequence().toSet() == setOf("version", "open_ids", "active_id", "restore", "hide_empty"))
        check(value.get("version") == 1 && value.get("restore") is Boolean && value.get("hide_empty") is Boolean)
        val rows = value.getJSONArray("open_ids")
        val ids = (0 until rows.length()).map { check(rows.get(it) is String); rows.getString(it) }
        check(ids.distinct().size == ids.size && ids.all { it.isNotEmpty() && it.length <= 128 })
        val active = if (value.isNull("active_id")) null else {
            check(value.get("active_id") is String)
            value.getString("active_id")
        }
        check(active == null && ids.isEmpty() || active in ids)
        return LibraryNavigation(ids, active, value.getBoolean("restore"), value.getBoolean("hide_empty"))
    }
    fun save(state: LibraryNavigation) {
        val text = JSONObject().put("version", 1).put("open_ids", JSONArray(state.openIds))
            .put("active_id", state.activeId ?: JSONObject.NULL).put("restore", state.restore)
            .put("hide_empty", state.hideEmpty).toString()
        val stream = file.startWrite()
        try {
            stream.write(text.toByteArray(Charsets.UTF_8))
            file.finishWrite(stream)
        } catch (error: Exception) {
            file.failWrite(stream)
            throw error
        }
        check(load() == state) { "Navigation preferences could not be confirmed" }
    }
}
