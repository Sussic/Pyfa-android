package io.github.sussic.pyfa

import io.github.sussic.pyfa.ModuleTestJson.array
import io.github.sussic.pyfa.ModuleTestJson.obj

internal object BulkTestJson {
    fun options(value: BulkChargeOptions) = obj(
        "modules" to array(value.modules.map { row -> obj("index" to row.index, "item_id" to row.itemId,
            "charge_id" to row.chargeId, "charge_ids" to array(row.chargeIds),
            "selection_candidates" to array(row.selectionCandidates), "similar_candidates" to array(row.similarCandidates)) }),
        "items" to array(value.items.map { obj("id" to it.id, "name" to it.name) }))
}
