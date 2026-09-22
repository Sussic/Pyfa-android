package io.github.sussic.pyfa

import io.github.sussic.pyfa.ModuleTestJson.array
import io.github.sussic.pyfa.ModuleTestJson.obj

internal object VariationTestJson {
    fun choice(value: VariationChoice) = obj("id" to value.id, "name" to value.name,
        "group" to value.group, "enabled" to value.enabled)
    fun options(value: VariationOptions) = obj("targets" to array(value.targets.map { target ->
        obj("context" to target.context.wire, "index" to target.index, "item_id" to target.itemId,
            "name" to target.name, "choices" to array(target.choices.map(::choice)), "current" to when (val current = target.current) {
                is VariationInput.Module -> obj("state" to current.state.name, "charge_id" to current.chargeId)
                is VariationInput.Drone -> obj("amount" to current.amount, "active" to current.active)
                is VariationInput.Implant -> obj("slot" to current.slot, "active" to current.active, "location" to current.location)
            })
    }))
}
