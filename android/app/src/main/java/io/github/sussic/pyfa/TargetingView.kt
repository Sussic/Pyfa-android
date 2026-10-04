package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

data class TargetingScalar(val value: StatValue, val unit: String, val display: String?, val detail: String?)
data class ReferenceLockTime(val name: String, val radius: Int, val time: TargetingScalar)
data class SpecialHold(val attribute: String, val name: String, val present: Boolean, val capacity: TargetingScalar)
data class FitTargeting(val fitId: String, val revision: Long, val main: Map<String, TargetingScalar>,
    val lockTimes: List<ReferenceLockTime>, val sensorType: String, val details: Map<String, TargetingScalar>, val holds: List<SpecialHold>)
internal val TARGETING_ROWS = linkedMapOf("targets" to "Maximum locked targets", "range" to "Maximum targeting range",
    "scan_resolution" to "Scan resolution", "sensor" to "Sensor strength", "drone_range" to "Drone control range",
    "speed" to "Maximum speed", "align" to "Align time", "signature" to "Signature radius", "warp_speed" to "Warp speed", "cargo" to "Cargo capacity")
internal val TARGETING_UNITS = linkedMapOf("targets" to "count", "range" to "m", "scan_resolution" to "mm", "sensor" to "points",
    "drone_range" to "m", "speed" to "m/s", "align" to "s", "signature" to "m", "warp_speed" to "AU/s", "cargo" to "m³")
internal val TARGETING_DETAILS = linkedMapOf("jam_chance" to "Chance to be jammed", "mass" to "Mass", "agility" to "Agility",
    "probe_size" to "Probe size", "warp_distance" to "Maximum warp distance", "warp_core" to "Warp core strength",
    "cargo_used" to "Cargo used", "additional_cargo" to "Additional cargo holds")
internal val TARGETING_DETAIL_UNITS = linkedMapOf("jam_chance" to "%", "mass" to "kg", "agility" to "x", "probe_size" to "x",
    "warp_distance" to "AU", "warp_core" to "points", "cargo_used" to "m³", "additional_cargo" to "m³")
internal val TARGETING_HOLDS = linkedMapOf("fleetHangarCapacity" to "Fleet hangar", "shipMaintenanceBayCapacity" to "Maintenance bay",
    "specialColonyResourcesHoldCapacity" to "Infrastructure hold", "specialAmmoHoldCapacity" to "Ammo hold", "specialFuelBayCapacity" to "Fuel bay",
    "specialShipHoldCapacity" to "Ship hold", "specialSmallShipHoldCapacity" to "Small ship hold", "specialMediumShipHoldCapacity" to "Medium ship hold",
    "specialLargeShipHoldCapacity" to "Large ship hold", "specialIndustrialShipHoldCapacity" to "Industrial ship hold", "generalMiningHoldCapacity" to "Mining hold",
    "specialIceHoldCapacity" to "Ice hold", "specialGasHoldCapacity" to "Gas hold", "specialMineralHoldCapacity" to "Mineral hold", "specialMaterialBayCapacity" to "Material bay",
    "specialSalvageHoldCapacity" to "Salvage hold", "specialCommandCenterHoldCapacity" to "Command center hold", "specialPlanetaryCommoditiesHoldCapacity" to "Planetary goods hold",
    "specialQuafeHoldCapacity" to "Quafe hold", "specialMobileDepotHoldCapacity" to "Mobile depot hold", "specialExpeditionHoldCapacity" to "Expedition hold")
internal val TARGETING_RADII = linkedMapOf("Pod" to 25, "Interceptor" to 33, "Frigate" to 38, "Destroyer" to 83, "Cruiser" to 130,
    "Battlecruiser" to 265, "Battleship" to 420, "Carrier" to 3000)

class TargetingModel : ViewModel() {
    var details by mutableStateOf<FitTargeting?>(null); private set
    var loading by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        requested = next; details = null; error = null; loading = true
        val token = ++generation
        EngineRuntime.targetingDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Statistics could not be loaded. Try again." else details = value
            }
        }, ContextCompat.getMainExecutor(context))
    }
}

@Composable
private fun TargetingCard(name: String, tag: String, scalar: TargetingScalar, fitId: String,
    wholeDisplay: Boolean = false, absent: Boolean = false, children: @Composable () -> Unit = {}) {
    var expanded by rememberSaveable(fitId, tag) { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth().testTag("targeting-$tag")) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(name, style = MaterialTheme.typography.titleSmall)
            val label = if (absent) "Not present on this hull" else scalar.display?.let { if (wholeDisplay) it else "$it ${scalar.unit}" } ?: "Unavailable"
            Text(label, Modifier.testTag("targeting-$tag-value"))
            TextButton(onClick = { expanded = !expanded }, modifier = Modifier.testTag("targeting-$tag-details")) {
                Text(if (expanded) "Hide details" else "Details")
            }
            if (expanded) {
                scalar.detail?.let { Text(it, Modifier.testTag("targeting-$tag-desktop-detail")) }
                val exact = when (val value = scalar.value) {
                    is StatValue.Integer -> value.value.toString()
                    is StatValue.Decimal -> value.value.toString()
                    StatValue.Unavailable -> if (absent) "Not present on this hull" else "Unavailable"
                    else -> error("Non-numeric targeting value")
                }
                Text("Full precision: $exact ${scalar.unit}", Modifier.testTag("targeting-$tag-precision"))
                children()
            }
        }
    }
}

@Composable
internal fun TargetingView(model: TargetingModel, onBack: () -> Unit) {
    BackHandler(onBack = onBack)
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    val detailState = rememberSaveableStateHolder()
    Text("Targeting and navigation", style = MaterialTheme.typography.headlineMedium)
    TextButton(onClick = onBack, modifier = Modifier.testTag("targeting-back")) { Text("Back") }
    if (fit == null) { Text("Select a fit to view its statistics."); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}")
    model.error?.let {
        Text(it)
        Button(onClick = { model.load(context, fit, true) }, modifier = Modifier.testTag("targeting-retry")) { Text("Try again") }
    }
    val values = model.details?.takeIf { it.fitId == fit.id && it.revision == fit.revision }
    if (values == null) { Text("Loading statistics…"); return }
    detailState.SaveableStateProvider(fit.id) {
    for ((key, label) in TARGETING_ROWS) {
        TargetingCard(label, key, values.main.getValue(key), fit.id, wholeDisplay = true) {
            when (key) {
                "scan_resolution" -> for (row in values.lockTimes) {
                    Text("${row.name} [${row.radius} m]: ${row.time.display}", Modifier.testTag("targeting-lock-${row.radius}"))
                    Text("Full precision: ${row.time.value.numberOrNull()} s", Modifier.testTag("targeting-lock-${row.radius}-precision"))
                }
                "sensor" -> {
                    Text("Sensor type: ${values.sensorType}", Modifier.testTag("targeting-sensor-type"))
                    TargetingCard(TARGETING_DETAILS.getValue("jam_chance"), "jam_chance", values.details.getValue("jam_chance"), fit.id)
                }
                "align" -> for (detail in listOf("mass", "agility")) TargetingCard(TARGETING_DETAILS.getValue(detail), detail, values.details.getValue(detail), fit.id)
                "signature" -> TargetingCard("Probe size", "probe_size", values.details.getValue("probe_size"), fit.id)
                "warp_speed" -> for (detail in listOf("warp_distance", "warp_core")) TargetingCard(TARGETING_DETAILS.getValue(detail), detail, values.details.getValue(detail), fit.id)
                "cargo" -> {
                    for (detail in listOf("cargo_used", "additional_cargo")) TargetingCard(TARGETING_DETAILS.getValue(detail), detail, values.details.getValue(detail), fit.id)
                    for (hold in values.holds) TargetingCard(hold.name, hold.attribute, hold.capacity, fit.id, absent = !hold.present)
                }
            }
        }
    }
    }
}
