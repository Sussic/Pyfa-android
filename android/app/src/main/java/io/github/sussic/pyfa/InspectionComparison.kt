package io.github.sussic.pyfa

/** Presentation ordering from pinned ItemCompare.PopulateList; EOS owns values. */
internal fun sortInspectionVariations(rows: List<InspectionValue.Fields>, key: String,
    reverse: Boolean, previousOrder: List<Int>): List<InspectionValue.Fields> {
    fun InspectionValue.Fields.number(name: String): Double? =
        (values.getValue(name) as? InspectionValue.Scalar)?.value?.numberOrNull()
    fun InspectionValue.Fields.text(name: String) =
        ((values.getValue(name) as InspectionValue.Scalar).value as StatValue.Text).value
    fun identity(row: InspectionValue.Fields) = checkNotNull(row.number("id")).toInt()
    val members = rows.associateBy(::identity)
    check(members.size == rows.size)
    check(previousOrder.toSet().size == previousOrder.size)
    val known = previousOrder.toSet()
    val previous = previousOrder.mapNotNull(members::get) + rows.filter { identity(it) !in known }
    fun numeric(row: InspectionValue.Fields): Double {
        if (key == "price") {
            val price = row.values.getValue("price") as InspectionValue.Fields
            val value = price.number("value")
            return if (value == null || value == 0.0) Double.POSITIVE_INFINITY else value
        }
        val values = row.values.getValue("values") as InspectionValue.Sequence
        val cell = values.values.map { it as InspectionValue.Fields }.firstOrNull { it.text("name") == key }
        return cell?.number("value") ?: 0.0
    }
    fun names(left: String, right: String): Int {
        var l = 0; var r = 0
        while (l < left.length && r < right.length) {
            val a = left.codePointAt(l); val b = right.codePointAt(r)
            if (a != b) return a.compareTo(b)
            l += Character.charCount(a); r += Character.charCount(b)
        }
        return (left.length - l).compareTo(right.length - r)
    }
    val nameOrder = Comparator<InspectionValue.Fields> { left, right -> names(left.text("name"), right.text("name")) }
    val comparator = when (key) {
        "default" -> compareBy<InspectionValue.Fields> { it.number("meta") ?: 0.0 }.then(nameOrder)
        "name" -> nameOrder
        else -> Comparator { left, right ->
            val a = numeric(left); val b = numeric(right)
            if (a == b) 0 else a.compareTo(b)
        }
    }
    // Comparator reversal preserves equal-key order, unlike reversing a list.
    return previous.sortedWith(if (reverse && key != "default") comparator.reversed() else comparator)
}
