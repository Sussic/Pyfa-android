package io.github.sussic.pyfa

import io.github.sussic.pyfa.ModuleTestJson.array
import io.github.sussic.pyfa.ModuleTestJson.obj

internal object StateTestJson {
    fun options(value: BulkStateOptions) = obj("modules" to array(value.modules.map { row ->
        obj("index" to row.index, "item_id" to row.itemId, "state" to row.state?.name, "editable" to row.editable,
            "similar_candidates" to array(row.similarCandidates),
            "click_states" to obj(*row.clickStates.map { it.key.wire to it.value.name }.toTypedArray()),
            "supported_states" to obj(*row.supportedStates.map { it.key.name to it.value.name }.toTypedArray()))
    }))
}
