package io.github.sussic.pyfa

import io.github.sussic.pyfa.ModuleTestJson.array
import io.github.sussic.pyfa.ModuleTestJson.obj

internal object RackTestJson {
    fun options(value: RackOptions) = obj("modules" to array(value.modules.map { module ->
        obj("index" to module.index, "id" to module.id, "name" to module.name,
            "slot" to module.slot.name, "state" to module.state.name, "charge_id" to module.chargeId,
            "charge" to module.charge, "heat" to module.heat?.let { heat ->
                obj("cycles" to obj("value" to heat.cycles.value.raw, "unit" to heat.cycles.unit),
                    "seconds" to obj("value" to heat.seconds.value.raw, "unit" to heat.seconds.unit),
                    "probabilities" to array(heat.probabilities.map {
                        obj("seconds" to it.seconds, "value" to it.value, "unit" to "probability")
                    }))
            })
    }))
}
