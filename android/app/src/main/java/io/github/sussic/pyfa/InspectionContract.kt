package io.github.sussic.pyfa

import java.util.Collections
import org.json.JSONArray
import org.json.JSONObject

/** Complete immutable values for supported EOS properties and detail metadata. */
sealed interface InspectionValue {
    data object Absent : InspectionValue
    data class Scalar(val value: StatValue) : InspectionValue
    data class Sequence(val values: List<InspectionValue>) : InspectionValue
    data class Fields(val values: Map<String, InspectionValue>) : InspectionValue
}

data class InspectionTarget(val context: String, val index: Int?, val itemId: Int, val objectKey: String? = null) {
    fun json(): String = JSONObject().put("context", context).put("index", index ?: JSONObject.NULL)
        .put("item_id", itemId).apply { objectKey?.let { put("object_key", it) } }.toString()
}
data class InspectionUnit(val id: Int, val name: String, val display: String?)
data class InspectionAttribute(val name: String, val id: Int?, val label: String, val metadata: Boolean,
    val published: Boolean, val current: StatValue, val base: StatValue, val rawCurrent: String, val rawBase: String,
    val displayCurrent: String?, val displayBase: String?, val normal: Boolean, val unit: InspectionUnit?)
data class InspectionOrder(val name: String, val groups: List<String>, val label: String)
data class InspectionOption(val target: InspectionTarget, val name: String)
data class InspectionOptions(val fitId: String, val revision: Long, val targets: List<InspectionOption>)
data class ItemInspection(val fitId: String?, val revision: Long?, val target: InspectionTarget,
    val item: InspectionValue.Fields, val attributes: List<InspectionAttribute>,
    val normal: List<InspectionOrder>, val raw: List<InspectionOrder>,
    val effects: List<InspectionValue.Fields>, val affectors: List<InspectionValue.Fields>,
    val properties: List<InspectionValue.Fields>, val equipment: InspectionValue.Fields?,
    val variations: InspectionValue.Fields, val stack: InspectionValue.Fields,
    val affectorViews: InspectionValue.Fields)

internal object InspectionCodec {
    private fun bad(message: String): Nothing = throw BridgeProtocolException("Inspection: $message")
    private fun requireValue(value: Boolean, message: String) { if (!value) bad(message) }
    private fun obj(value: Any): JSONObject = value as? JSONObject ?: bad("object required")
    private fun rows(value: Any): List<Any> = (value as? JSONArray ?: bad("array required")).let { a ->
        (0 until a.length()).map { a.get(it) }
    }
    private fun text(value: Any): String = value as? String ?: bad("string required")
    private fun textOrNull(value: Any): String? = if (value === JSONObject.NULL) null else text(value)
    private fun bool(value: Any): Boolean = value as? Boolean ?: bad("boolean required")
    private fun integer(value: Any): Long = when (value) { is Int -> value.toLong(); is Long -> value; else -> bad("integer required") }
    private fun id(value: Any): Int = integer(value).also { requireValue(it in 1..Int.MAX_VALUE.toLong(), "invalid ID") }.toInt()
    private fun position(value: Any): Int = integer(value).also { requireValue(it in 0..Int.MAX_VALUE.toLong(), "invalid position") }.toInt()
    private fun keys(row: JSONObject, vararg names: String) {
        requireValue(row.keys().asSequence().toSet() == names.toSet(), "missing or extra fields")
    }
    private fun <T> frozen(values: Collection<T>): List<T> = Collections.unmodifiableList(ArrayList(values))
    private fun scalar(value: Any, boolean: Boolean = false): StatValue = when (value) {
        is Int -> StatValue.Integer(value.toLong())
        is Long -> StatValue.Integer(value)
        is Double -> StatValue.Decimal(value.also { requireValue(it.isFinite(), "non-finite number") })
        is Boolean -> if (boolean) StatValue.BooleanValue(value) else bad("number required")
        else -> bad("number required")
    }
    private fun number(value: Any): Double = scalar(value).numberOrNull() ?: bad("number required")
    private fun value(raw: Any, depth: Int = 0): InspectionValue {
        requireValue(depth <= 32, "excessive nested property")
        return when (raw) {
            JSONObject.NULL -> InspectionValue.Absent
            is String -> InspectionValue.Scalar(StatValue.Text(raw))
            is JSONObject -> InspectionValue.Fields(Collections.unmodifiableMap(LinkedHashMap<String, InspectionValue>().apply {
                raw.keys().forEach { put(it, value(raw.get(it), depth + 1)) }
            }))
            is JSONArray -> InspectionValue.Sequence(frozen(rows(raw).map { value(it, depth + 1) }))
            else -> InspectionValue.Scalar(scalar(raw, true))
        }
    }
    private fun fields(row: JSONObject): InspectionValue.Fields = value(row) as InspectionValue.Fields
    private fun rawMatches(raw: String, scalar: StatValue) {
        when (scalar) {
            is StatValue.BooleanValue -> requireValue(raw == if (scalar.value) "True" else "False", "raw boolean differs")
            else -> requireValue(raw.toDoubleOrNull()?.let { it.isFinite() && it == scalar.numberOrNull() } == true, "raw number differs")
        }
    }

    fun options(root: JSONObject): InspectionOptions {
        keys(root, "version", "fit_id", "revision", "targets")
        requireValue(integer(root.get("version")) == 1L, "unsupported version")
        val fitId = text(root.get("fit_id")); requireValue(fitId.isNotEmpty() && fitId.length <= 128, "invalid fit identity")
        val revision = integer(root.get("revision")); requireValue(revision >= 1, "invalid revision")
        val targets = rows(root.get("targets")).map { entry -> obj(entry).let { row ->
            keys(row, "context", "index", "item_id", "name", "object_key")
            val context = text(row.get("context"))
            requireValue(context in setOf("ship", "module", "charge", "drone", "fighter", "implant", "booster", "cargo", "mode"), "unknown fitted context")
            val index = position(row.get("index"))
            requireValue(context !in setOf("ship", "mode") || index == 0, "invalid singleton position")
            val name = text(row.get("name")); requireValue(name.isNotEmpty(), "empty inspection target name")
            val objectKey = text(row.get("object_key"))
            requireValue(objectKey.matches(Regex("[0-9a-f]{32}")), "invalid saved object identity")
            InspectionOption(InspectionTarget(context, index, id(row.get("item_id")), objectKey), name)
        } }
        requireValue(targets.map { it.target.context to it.target.index }.distinct().size == targets.size, "duplicate target positions")
        requireValue(targets.map { it.target.context to it.target.objectKey }.distinct().size == targets.size, "duplicate saved target identities")
        requireValue(targets.firstOrNull()?.target?.context == "ship" && targets.count { it.target.context == "ship" } == 1, "missing or duplicate ship target")
        return InspectionOptions(fitId, revision, frozen(targets))
    }

    fun decode(root: JSONObject): ItemInspection {
        keys(root, "version", "fit_id", "revision", "selection", "item", "attributes", "effects", "affectors",
            "properties", "equipment", "variations", "stack", "affector_views")
        requireValue(integer(root.get("version")) == 1L, "unsupported version")
        val fitId = textOrNull(root.get("fit_id"))?.also { requireValue(it.isNotEmpty() && it.length <= 128, "invalid fit identity") }
        val revision = root.get("revision").let { if (it === JSONObject.NULL) null else integer(it).also { n -> requireValue(n >= 1, "invalid revision") } }
        requireValue((fitId == null) == (revision == null), "fit/revision availability differs")
        val selection = obj(root.get("selection"))
        if (selection.has("object_key")) keys(selection, "context", "index", "item_id", "object_key")
        else keys(selection, "context", "index", "item_id")
        val context = text(selection.get("context"))
        requireValue(context in setOf("ship", "module", "charge", "drone", "fighter", "implant", "booster", "cargo", "mode", "base"), "unknown context")
        val index = selection.get("index").let { if (it === JSONObject.NULL) null else position(it) }
        requireValue((context == "base") == (index == null) && (fitId != null || context == "base"), "invalid target position/context")
        val objectKey = if (selection.has("object_key")) text(selection.get("object_key")).also {
            requireValue(context != "base" && it.matches(Regex("[0-9a-f]{32}")), "invalid saved object identity")
        } else null
        val target = InspectionTarget(context, index, id(selection.get("item_id")), objectKey)
        val item = obj(root.get("item")); keys(item, "id", "name", "category", "group", "description", "traits")
        requireValue(id(item.get("id")) == target.itemId, "target item differs")
        for (name in listOf("name", "category", "group")) requireValue(text(item.get(name)).isNotEmpty(), "empty item name")
        textOrNull(item.get("description")); textOrNull(item.get("traits"))
        val attributes = obj(root.get("attributes")); keys(attributes, "rows", "normal", "raw")
        val members = rows(attributes.get("rows")).map { raw ->
            val row = obj(raw)
            keys(row, "name", "id", "label", "metadata", "published", "current", "base", "raw_current", "raw_base",
                "display_current", "display_base", "normal", "unit")
            val name = text(row.get("name")); requireValue(name.isNotEmpty(), "empty attribute name")
            val metadata = bool(row.get("metadata")); val published = bool(row.get("published"))
            val attributeId = row.get("id").let { if (it === JSONObject.NULL) null else id(it) }
            requireValue(metadata == (attributeId != null) && (!published || metadata), "invalid metadata availability")
            val current = scalar(row.get("current"), true); val base = scalar(row.get("base"), true)
            val rawCurrent = text(row.get("raw_current")); val rawBase = text(row.get("raw_base"))
            rawMatches(rawCurrent, current); rawMatches(rawBase, base)
            val normal = bool(row.get("normal")); val displayCurrent = textOrNull(row.get("display_current")); val displayBase = textOrNull(row.get("display_base"))
            requireValue(normal == (displayCurrent != null && displayBase != null) && (!normal || published), "invalid display availability")
            val unit = row.get("unit").let { if (it === JSONObject.NULL) null else obj(it).let { u ->
                keys(u, "id", "name", "display"); InspectionUnit(id(u.get("id")), text(u.get("name")), textOrNull(u.get("display")))
            } }
            requireValue(metadata || unit == null, "unit without metadata")
            InspectionAttribute(name, attributeId, text(row.get("label")), metadata, published, current, base,
                rawCurrent, rawBase, displayCurrent, displayBase, normal, unit)
        }
        val names = members.map { it.name }
        requireValue(names == names.sorted() && names.distinct().size == names.size, "unordered or duplicate attributes")
        val ids = members.mapNotNull { it.id }; requireValue(ids.distinct().size == ids.size, "duplicate attribute IDs")
        fun order(name: String, expected: Set<String>): List<InspectionOrder> {
            val entries = rows(attributes.get(name)).map { entry -> obj(entry).let { row ->
                keys(row, "name", "groups", "label")
                InspectionOrder(text(row.get("name")), frozen(rows(row.get("groups")).map(::text)), text(row.get("label")))
            } }
            val keys = entries.map { it.name }
            requireValue(keys.size == expected.size && keys.toSet() == expected, "incomplete/duplicate $name grouping")
            return frozen(entries)
        }
        val normal = order("normal", members.filter { it.normal }.map { it.name }.toSet())
        val raw = order("raw", names.toSet())
        val effects = rows(root.get("effects")).map { entry -> obj(entry).also { row ->
            keys(row, "id", "name", "implemented", "active", "types", "runtime", "published", "description")
            id(row.get("id")); text(row.get("name")); bool(row.get("published")); textOrNull(row.get("description"))
            val implemented = bool(row.get("implemented"))
            requireValue(implemented == (row.get("active") !== JSONObject.NULL), "effect activity availability")
            if (implemented) bool(row.get("active"))
            rows(row.get("types")).forEach { requireValue(text(it) in setOf("passive", "active", "projected", "gang", "structure", "offline", "overheat", "boosterSideEffect"), "unknown effect type") }
            textOrNull(row.get("runtime")); requireValue(implemented || row.get("runtime") === JSONObject.NULL, "unimplemented effect runtime")
            if (row.get("runtime") !== JSONObject.NULL) requireValue(text(row.get("runtime")) in setOf("early", "normal", "late"), "unknown effect runtime")
        } }
        val effectNames = effects.map { text(it.get("name")) }; val effectIds = effects.map { id(it.get("id")) }
        requireValue(effectNames == effectNames.sorted() && effectNames.distinct().size == effectNames.size && effectIds.distinct().size == effectIds.size, "invalid effect order/IDs")
        val affectors = rows(root.get("affectors")).map { entry -> obj(entry).also { row ->
            keys(row, "attribute", "changed", "used", "source_type", "source_id", "source_fit_id", "source_fit_name", "source_ship_id",
                "item_id", "item_name", "source_fit_key", "source_target", "projected", "operator", "stacking", "before", "after")
            text(row.get("attribute")); bool(row.get("changed")); bool(row.get("used")); bool(row.get("projected"))
            text(row.get("source_type")); text(row.get("source_fit_name")); id(row.get("source_ship_id"))
            for (name in listOf("source_id", "source_fit_id", "item_id")) if (row.get(name) !== JSONObject.NULL) id(row.get(name))
            textOrNull(row.get("item_name")); requireValue((row.get("item_id") === JSONObject.NULL) == (row.get("item_name") === JSONObject.NULL), "affector item availability")
            textOrNull(row.get("source_fit_key"))?.let { requireValue(it.isNotEmpty() && it.length <= 128, "invalid affector fit identity") }
            if (row.get("source_target") !== JSONObject.NULL) obj(row.get("source_target")).also { target ->
                if (target.has("object_key")) {
                    keys(target, "context", "index", "item_id", "object_key")
                    requireValue(text(target.get("object_key")).matches(Regex("[0-9a-f]{32}")), "invalid affector object identity")
                } else keys(target, "context", "index", "item_id")
                requireValue(text(target.get("context")) in setOf("ship", "mode", "module", "charge", "drone", "fighter", "implant", "booster"), "invalid affector target")
                position(target.get("index")); requireValue(id(target.get("item_id")) == id(row.get("item_id")), "affector target item differs")
            }
            requireValue(text(row.get("operator")) in setOf("PREASSIGN", "PREINCREASE", "MULTIPLY", "POSTINCREASE", "FORCE"), "unknown affector operator")
            number(row.get("before")); number(row.get("after"))
        } }
        val affectorViews = obj(root.get("affector_views")); keys(affectorViews, "source", "attribute")
        fun tree(nodes: Any, depth: Int = 0) {
            requireValue(depth <= 16, "excessive affector tree")
            rows(nodes).forEach { entry ->
                val node = obj(entry); keys(node, "label", "alternate", "sources", "children")
                requireValue(text(node.get("label")).isNotEmpty(), "empty affector tree label")
                textOrNull(node.get("alternate"))
                rows(node.get("sources")).forEach { raw ->
                    val source = obj(raw)
                    keys(source, "source_fit_id", "source_fit_key", "source_fit_name", "item_id", "source_target")
                    id(source.get("source_fit_id")); id(source.get("item_id")); text(source.get("source_fit_name"))
                    textOrNull(source.get("source_fit_key"))?.let { requireValue(it.isNotEmpty() && it.length <= 128, "invalid tree fit identity") }
                    if (source.get("source_target") !== JSONObject.NULL) obj(source.get("source_target")).also { target ->
                        if (target.has("object_key")) {
                            keys(target, "context", "index", "item_id", "object_key")
                            requireValue(text(target.get("object_key")).matches(Regex("[0-9a-f]{32}")), "invalid tree object identity")
                        } else keys(target, "context", "index", "item_id")
                        requireValue(text(target.get("context")) in setOf("ship", "mode", "module", "charge", "drone", "fighter", "implant", "booster"), "invalid tree target")
                        position(target.get("index")); requireValue(id(target.get("item_id")) == id(source.get("item_id")), "tree target item differs")
                    }
                }
                tree(node.get("children"), depth + 1)
            }
        }
        tree(affectorViews.get("source")); tree(affectorViews.get("attribute"))
        val properties = rows(root.get("properties")).map { entry -> obj(entry).also { row ->
            keys(row, "name", "label", "available", "value", "reason", "display")
            text(row.get("name")); text(row.get("label")); val available = bool(row.get("available"))
            requireValue(available == (row.get("reason") === JSONObject.NULL), "property availability differs")
            val display = textOrNull(row.get("display")); val property = row.get("value")
            if (!available) { requireValue(property === JSONObject.NULL && display == null, "unavailable property value"); text(row.get("reason")) }
            else when (property) {
                JSONObject.NULL -> requireValue(display == "None", "null property display")
                is Boolean -> requireValue(display == if (property) "True" else "False", "boolean property display")
                is String -> requireValue(display == property, "text property display")
                is Int, is Long -> requireValue(display == integer(property).toString(), "integer property display")
                is Double -> requireValue(display?.toDoubleOrNull()?.let { it.isFinite() && it == property } == true, "decimal property display")
                is JSONObject -> {
                    val kind = if (property.keys().asSequence().toSet() == setOf("number_kind")) property.optString("number_kind") else ""
                    requireValue(display == when (kind) { "positive_infinity" -> "inf"; "negative_infinity" -> "-inf"; else -> null }, "structured property display")
                }
                is JSONArray -> requireValue(display == null, "collection property display")
            }
        } }
        requireValue(properties.map { text(it.get("name")) }.distinct().size == properties.size, "duplicate properties")
        val equipment = root.get("equipment").let { if (it === JSONObject.NULL) null else obj(it).also { row ->
            keys(row, "misc", "range", "capacitor", "effective"); bool(row.get("effective"))
            for (name in listOf("misc", "range", "capacitor")) if (row.get(name) !== JSONObject.NULL) obj(row.get(name)).also { field ->
                keys(field, "display", "detail"); text(field.get("display")); textOrNull(field.get("detail"))
            }
        } }
        val variations = obj(root.get("variations")); keys(variations, "columns", "rows")
        val columns = rows(variations.get("columns")).map { obj(it).also { c -> keys(c, "name", "id", "label"); text(c.get("name")); id(c.get("id")); text(c.get("label")) } }
        val columnNames = columns.map { text(it.get("name")) }; requireValue(columnNames.distinct().size == columnNames.size, "duplicate comparison columns")
        val variants = rows(variations.get("rows")).map { obj(it).also { row ->
            keys(row, "id", "name", "meta", "selected", "values", "price"); id(row.get("id")); text(row.get("name")); number(row.get("meta")); bool(row.get("selected"))
            val values = rows(row.get("values")).map { obj(it).also { cell ->
                keys(cell, "name", "available", "value", "raw", "display"); text(cell.get("name"))
                if (bool(cell.get("available"))) { rawMatches(text(cell.get("raw")), scalar(cell.get("value"), true)); text(cell.get("display")) }
                else requireValue(listOf("value", "raw", "display").all { key -> cell.get(key) === JSONObject.NULL }, "absent comparison cell has value")
            } }
            requireValue(values.map { text(it.get("name")) } == columnNames, "comparison columns differ")
            val price = obj(row.get("price")); keys(price, "available", "value", "currency", "timestamp", "display")
            requireValue(text(price.get("currency")) == "ISK", "invalid price unit")
            if (bool(price.get("available"))) { requireValue(number(price.get("value")) > 0, "invalid price"); text(price.get("display")) }
            else requireValue(listOf("value", "timestamp", "display").all { key -> price.get(key) === JSONObject.NULL }, "unavailable price has value")
            if (price.get("timestamp") !== JSONObject.NULL) requireValue(number(price.get("timestamp")) > 0, "invalid price age")
        } }
        requireValue(variants.map { id(it.get("id")) }.distinct().size == variants.size, "duplicate variations")
        requireValue(variants.count { bool(it.get("selected")) } <= 1 && variants.all { !bool(it.get("selected")) || id(it.get("id")) == target.itemId }, "invalid selected variation")
        val stack = obj(root.get("stack")); keys(stack, "amount", "volume", "total_volume", "unit", "display")
        val amount = integer(stack.get("amount")); requireValue(amount >= 0 && text(stack.get("unit")) == "m³", "invalid stack")
        if (stack.get("volume") === JSONObject.NULL) requireValue(stack.get("total_volume") === JSONObject.NULL && stack.get("display") === JSONObject.NULL, "absent volume has value")
        else { requireValue(number(stack.get("volume")) * amount == number(stack.get("total_volume")), "stack volume differs"); text(stack.get("display")) }
        return ItemInspection(fitId, revision, target, fields(item), frozen(members), normal, raw,
            frozen(effects.map(::fields)), frozen(affectors.map(::fields)), frozen(properties.map(::fields)),
            equipment?.let(::fields), fields(variations), fields(stack), fields(affectorViews))
    }
}
