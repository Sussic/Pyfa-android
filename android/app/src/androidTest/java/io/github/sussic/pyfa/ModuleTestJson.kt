package io.github.sussic.pyfa

import kotlin.math.abs
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*

/** JSON report writers normalize integral decimals; retain the DTO numeric kinds. */
internal object ModuleTestJson {
    fun obj(vararg pairs: Pair<String, Any?>) = JSONObject().apply { pairs.forEach { put(it.first, it.second ?: JSONObject.NULL) } }
    fun array(rows: Collection<*>) = JSONArray(rows)
    fun stats(fit: FitSnapshot) = JSONObject().apply {
        fit.stats.forEach { (name, stat) -> put(name, obj("value" to stat.value.raw, "unit" to stat.unit)) }
    }
    fun fit(fit: FitSnapshot): JSONObject = obj(
        "id" to fit.id, "revision" to fit.revision, "name" to fit.name, "ship" to fit.ship, "stats" to stats(fit),
        "modules" to array(fit.modules.map {
            if (it.emptySlot != null) obj("index" to it.index, "empty_slot" to it.emptySlot.name)
            else obj("index" to it.index, "name" to checkNotNull(it.name), "charge" to it.charge, "state" to checkNotNull(it.state).name)
        }), "skills" to JSONObject(fit.skills),
        "implants" to array(fit.implants.map { obj("name" to it.name, "slot" to it.slot, "active" to it.active) }),
        "projections" to array(fit.projections.map { obj("source_id" to it.sourceId, "range_m" to it.rangeM, "active" to it.active, "amount" to it.amount) }),
        "commands" to array(fit.commands.map { obj("source_id" to it.sourceId, "active" to it.active) }),
    )
    private fun requirements(rows: List<SkillRequirement>): JSONArray = array(rows.map {
        obj("id" to it.id, "name" to it.name, "required" to it.required, "actual" to it.actual,
            "requirements" to requirements(it.requirements))
    })
    fun details(value: FittingDetails): JSONObject = obj(
        "modules" to array(value.modules.map { obj("index" to it.index, "id" to it.id, "name" to it.name,
            "slot" to it.slot.name, "state" to it.state.name, "charge" to it.charge, "legal" to it.legal, "overridden" to it.overridden) }),
        "ignore_restrictions" to value.ignoreRestrictions,
        "resources" to JSONObject().apply { value.resources.forEach { (name, use) ->
            put(name, obj("used" to use.used.raw, "total" to use.total.raw, "unit" to use.unit, "overloaded" to use.overloaded)) } },
        "slots" to array(value.slots.map { obj("slot" to it.slot.name, "used" to it.used, "total" to it.total.raw) }),
        "hardpoints" to array(value.hardpoints.map { obj("kind" to it.kind, "used" to it.used, "total" to it.total.raw) }),
        "skill_warnings" to array(value.skillWarnings.map { obj("id" to it.id, "name" to it.name, "requirements" to requirements(it.requirements)) }),
    )
    fun numericKinds(value: Any): JSONObject {
        val result = JSONObject()
        fun visit(value: Any, path: String) {
            when (value) {
                is JSONObject -> value.keys().forEach { visit(value.get(it), "$path.$it") }
                is JSONArray -> (0 until value.length()).forEach { visit(value.get(it), "$path[$it]") }
                is Int, is Long -> result.put(path, "integer")
                is Double -> result.put(path, "decimal")
            }
        }
        visit(value, "root")
        return result
    }
    fun typed(value: Any) = obj("data" to value, "numeric_types" to numericKinds(value))
    fun compare(expected: Any, actual: Any, path: String = "root", strict: Boolean = true) {
        when (expected) {
            is JSONObject -> {
                assertTrue(path, actual is JSONObject); actual as JSONObject
                assertEquals(path, expected.keys().asSequence().toSet(), actual.keys().asSequence().toSet())
                expected.keys().forEach { compare(expected.get(it), actual.get(it), "$path.$it", strict) }
            }
            is JSONArray -> {
                assertTrue(path, actual is JSONArray); actual as JSONArray
                assertEquals(path, expected.length(), actual.length())
                (0 until expected.length()).forEach { compare(expected.get(it), actual.get(it), "$path[$it]", strict) }
            }
            is Number -> {
                assertTrue(path, actual is Number); actual as Number
                val leftInteger = expected is Int || expected is Long
                val rightInteger = actual is Int || actual is Long
                if (strict) assertEquals("$path numeric kind", leftInteger, rightInteger)
                if (leftInteger && rightInteger) assertEquals(path, expected.toLong(), actual.toLong())
                else {
                    val left = expected.toDouble(); val right = actual.toDouble()
                    assertTrue(path, left.isFinite() && right.isFinite())
                    assertEquals(path, left, right, maxOf(1e-9, 1e-10 * maxOf(abs(left), abs(right))))
                }
            }
            else -> assertEquals(path, expected, actual)
        }
    }
}
