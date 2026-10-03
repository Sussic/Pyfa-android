package io.github.sussic.pyfa

import android.content.Context
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModel
import kotlinx.coroutines.Dispatchers

data class OutputScalar(val value: StatValue, val unit: String, val display: String?, val detail: String?)
data class OutputDamage(val amount: OutputScalar, val share: OutputScalar)
data class OutputSpool(val current: OutputScalar, val pre: OutputScalar, val full: OutputScalar, val indicated: Boolean, val tooltip: String)
data class OutputFirepower(val spool: OutputSpool, val damage: Map<String, OutputDamage>)
data class OutputMining(val yieldSecond: OutputScalar, val drainSecond: OutputScalar, val yieldHour: OutputScalar, val drainHour: OutputScalar, val efficiency: OutputScalar)
data class OutputBombing(val signature: OutputScalar, val multiplier: OutputScalar, val levels: List<Map<String, OutputScalar>>)
data class FitOutput(val fitId: String, val revision: Long, val firepower: Map<String, Map<String, OutputFirepower>>,
    val mining: Map<String, OutputMining>, val bombing: OutputBombing, val outgoing: Map<String, OutputSpool>,
    val effective: Boolean, val defaultSpoolPercentage: Double, val targetProfile: TargetProfile?)
data class TargetProfile(val emAmount: Double, val thermalAmount: Double, val kineticAmount: Double, val explosiveAmount: Double,
    val maxVelocity: Double = 0.0, val signatureRadius: Double? = null, val radius: Double = 0.0, val hp: Double? = null)
data class FighterSpec(val name: String, val amount: Int, val active: Boolean)
data class EnvironmentSpec(val name: String, val state: ModuleState)
internal val OUTPUT_DAMAGE = linkedMapOf("em" to "EM", "thermal" to "Thermal", "kinetic" to "Kinetic", "explosive" to "Explosive", "pure" to "Pure")
internal val OUTPUT_REMOTE = linkedMapOf("capacitor" to "Capacitor transfer", "shield" to "Shield repair", "armor" to "Armor repair", "hull" to "Hull repair")

class OutputModel : ViewModel() {
    var details by mutableStateOf<FitOutput?>(null); private set
    var loading by mutableStateOf(false); private set
    var editing by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    private var requested: Pair<String, Long>? = null
    private var generation = 0
    fun load(context: Context, fit: FitSnapshot, retry: Boolean = false) {
        val next = fit.id to fit.revision
        if (!retry && requested == next) return
        requested = next; details = null; error = null; loading = true
        val token = ++generation
        EngineRuntime.outputDetails(context, fit.id).whenCompleteAsync({ value, failure ->
            if (token == generation) {
                loading = false
                if (failure != null) error = "Statistics could not be loaded. Try again." else details = value
            }
        }, ContextCompat.getMainExecutor(context))
    }
    fun apply(context: Context, fit: FitSnapshot, profile: TargetProfile?) {
        if (editing || loading) return
        editing = true; error = null
        EngineRuntime.request(context, BridgeOperation.SetTargetProfile(fit.id, profile), mapOf(fit.id to fit.revision)).whenCompleteAsync({ response, failure ->
            editing = false
            if (failure != null) error = "Target profile could not be saved. Try again."
            else if (response.status != BridgeStatus.OK) error = response.error?.message ?: "Target profile could not be saved."
        }, ContextCompat.getMainExecutor(context))
    }
}

private fun OutputScalar.text(): String = display?.let { "$it $unit" } ?: "Unavailable"
private fun OutputScalar.precision(): String = value.numberOrNull()?.toString() ?: "Unavailable"

@Composable
private fun OutputRow(name: String, label: String, spool: OutputSpool, damage: Map<String, OutputDamage>? = null) {
    var expanded by rememberSaveable(name) { mutableStateOf(false) }
    Card(Modifier.testTag("output-row-$name")) {
        Column(Modifier.padding(16.dp)) {
            Text(label, style = MaterialTheme.typography.titleMedium)
            Text(spool.current.text(), Modifier.testTag("output-value-$name"))
            TextButton(onClick = { expanded = !expanded }, modifier = Modifier.testTag("output-details-$name")) { Text(if (expanded) "Hide details" else "Details") }
            if (expanded) {
                Text("Current: ${spool.current.precision()} ${spool.current.unit}", Modifier.testTag("output-current-$name"))
                Text("Initial: ${spool.pre.text()} · Full precision: ${spool.pre.precision()}", Modifier.testTag("output-pre-$name"))
                Text("Full spool: ${spool.full.text()} · Full precision: ${spool.full.precision()}", Modifier.testTag("output-full-$name"))
                Text(if (spool.indicated) spool.tooltip else "No spool increase", Modifier.testTag("output-spool-$name"))
                damage?.forEach { (kind, value) ->
                    Text("${OUTPUT_DAMAGE.getValue(kind)}: ${value.amount.text()} · ${value.share.text()}", Modifier.testTag("output-share-$name-$kind"))
                    Text("Full precision: ${value.amount.precision()} ${value.amount.unit} · ${value.share.precision()} %")
                }
            }
        }
    }
}

@Composable
private fun TargetProfileEditor(model: OutputModel, fit: FitSnapshot, result: FitOutput) {
    val context = LocalContext.current
    var expanded by rememberSaveable(fit.id) { mutableStateOf(false) }
    TextButton(onClick = { expanded = !expanded }, modifier = Modifier.testTag("output-profile-open")) { Text("Target profile") }
    if (!expanded) return
    val profile = result.targetProfile
    var em by remember(fit.id, result.revision) { mutableStateOf(((profile?.emAmount ?: 0.0)*100).toString()) }
    var thermal by remember(fit.id, result.revision) { mutableStateOf(((profile?.thermalAmount ?: 0.0)*100).toString()) }
    var kinetic by remember(fit.id, result.revision) { mutableStateOf(((profile?.kineticAmount ?: 0.0)*100).toString()) }
    var explosive by remember(fit.id, result.revision) { mutableStateOf(((profile?.explosiveAmount ?: 0.0)*100).toString()) }
    var speed by remember(fit.id, result.revision) { mutableStateOf((profile?.maxVelocity ?: 0.0).toString()) }
    var signature by remember(fit.id, result.revision) { mutableStateOf(profile?.signatureRadius?.toString() ?: "") }
    var radius by remember(fit.id, result.revision) { mutableStateOf((profile?.radius ?: 0.0).toString()) }
    var hp by remember(fit.id, result.revision) { mutableStateOf(profile?.hp?.toString() ?: "") }
    fun parsed(text: String, nullable: Boolean = false): Double? = if (nullable && text.isBlank()) null else text.toDoubleOrNull()?.takeIf { it.isFinite() }
    val resistances = listOf(em, thermal, kinetic, explosive).map { parsed(it) }
    val valid = resistances.all { it != null && it in 0.0..100.0 } && parsed(speed)?.let { it >= 0 } == true && parsed(radius)?.let { it >= 0 } == true &&
        (signature.isBlank() || parsed(signature)?.let { it > 0 } == true) && (hp.isBlank() || parsed(hp)?.let { it > 0 } == true)
    Text("Target resistances (%)", style = MaterialTheme.typography.titleMedium)
    for ((key, value, update) in listOf(Triple("em", em, { v: String -> em = v }), Triple("thermal", thermal, { v: String -> thermal = v }),
        Triple("kinetic", kinetic, { v: String -> kinetic = v }), Triple("explosive", explosive, { v: String -> explosive = v }))) {
        OutlinedTextField(value, update, label = { Text("${OUTPUT_DAMAGE.getValue(key)} resistance (%)") }, modifier = Modifier.testTag("output-profile-$key"))
    }
    for ((key, value, update) in listOf(Triple("speed", speed, { v: String -> speed = v }), Triple("signature", signature, { v: String -> signature = v }),
        Triple("radius", radius, { v: String -> radius = v }), Triple("hp", hp, { v: String -> hp = v }))) {
        val label = mapOf("speed" to "Maximum velocity (m/s)", "signature" to "Signature radius (m; blank means unlimited)", "radius" to "Radius (m)", "hp" to "HP (blank means unlimited)").getValue(key)
        OutlinedTextField(value, update, label = { Text(label) }, modifier = Modifier.testTag("output-profile-$key"))
    }
    if (!valid) Text("Enter finite values. Resistances must be 0–100%; speed and radius must be nonnegative; signature and HP must be positive.")
    Button(onClick = { model.apply(context, fit, TargetProfile(resistances[0]!!/100, resistances[1]!!/100, resistances[2]!!/100, resistances[3]!!/100,
        parsed(speed)!!, parsed(signature, true), parsed(radius)!!, parsed(hp, true))) }, enabled = valid && !model.editing && !model.loading,
        modifier = Modifier.testTag("output-profile-apply")) { Text("Apply target profile") }
    TextButton(onClick = { model.apply(context, fit, null) }, enabled = profile != null && !model.editing && !model.loading,
        modifier = Modifier.testTag("output-profile-clear")) { Text("Use no target profile") }
}

@Composable
internal fun OutputView(model: OutputModel, onBack: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    val fit = (engine as? EngineState.Ready)?.fit
    BackHandler { onBack() }
    Text("Output statistics", style = MaterialTheme.typography.headlineLarge)
    TextButton(onClick = onBack, modifier = Modifier.testTag("output-back")) { Text("Back") }
    if (fit == null) { Text("Open a fit to view its output."); return }
    LaunchedEffect(fit.id, fit.revision) { model.load(context, fit) }
    Text("${fit.name} · ${fit.ship}", style = MaterialTheme.typography.titleLarge)
    if (model.loading) Text("Loading statistics…", Modifier.testTag("output-loading"))
    model.error?.let {
        Text(it, Modifier.testTag("output-error"), color = MaterialTheme.colorScheme.error)
        TextButton(onClick = { model.load(context, fit, true) }) { Text("Try again") }
    }
    val result = model.details?.takeIf { it.fitId == fit.id && it.revision == fit.revision } ?: return
    var page by rememberSaveable(fit.id) { mutableStateOf("firepower") }
    for ((name, label) in listOf("firepower" to "Firepower", "mining" to "Mining yield", "bombing" to "Bombing", "outgoing" to "Outgoing repairs")) {
        TextButton(onClick = { page = name }, modifier = Modifier.testTag("output-page-$name")) { Text(label) }
    }
    Text("Default spool: ${result.defaultSpoolPercentage}%", Modifier.testTag("output-default-spool"))
    TargetProfileEditor(model, fit, result)
    when (page) {
        "firepower" -> {
            var raw by rememberSaveable(fit.id) { mutableStateOf(false) }
            Text(if (result.effective && !raw) "Effective damage · target profile applied" else "Raw damage · no target profile", Modifier.testTag("output-mode"))
            TextButton(onClick = { raw = !raw }, modifier = Modifier.testTag("output-toggle")) { Text(if (raw) "Show effective damage" else "Show raw damage") }
            for ((name, row) in result.firepower.getValue(if (raw) "raw" else "effective")) {
                OutputRow(name, mapOf("weapon" to "Weapon DPS", "drone" to "Drone and fighter DPS", "total" to "Total DPS", "volley" to "Total volley").getValue(name), row.spool, row.damage)
            }
        }
        "mining" -> for ((name, row) in result.mining) {
            Card(Modifier.testTag("output-mining-$name")) {
                Column(Modifier.padding(16.dp)) {
                    Text(mapOf("module" to "Mining modules", "drone" to "Mining drones", "total" to "Combined mining").getValue(name), style = MaterialTheme.typography.titleMedium)
                    for ((field, label, scalar) in listOf(Triple("yield-second", "Yield", row.yieldSecond), Triple("drain-second", "Drain", row.drainSecond),
                        Triple("yield-hour", "Hourly yield", row.yieldHour), Triple("drain-hour", "Hourly drain", row.drainHour), Triple("efficiency", "Efficiency", row.efficiency))) {
                        Text("$label: ${scalar.text()}", Modifier.testTag("output-mining-$name-$field"))
                        Text("Full precision: ${scalar.precision()} ${scalar.unit}")
                    }
                }
            }
        }
        "bombing" -> {
            Text("Target signature: ${result.bombing.signature.text()}")
            Text("Environment damage multiplier: ${result.bombing.multiplier.text()}")
            Text("Bombs needed to destroy this fit", style = MaterialTheme.typography.titleMedium)
            result.bombing.levels.forEachIndexed { level, cells ->
                Card { Column(Modifier.padding(16.dp)) {
                    Text("Covert Ops level $level")
                    cells.forEach { (kind, scalar) -> Text("${OUTPUT_DAMAGE.getValue(kind)}: ${scalar.text()}", Modifier.testTag("output-bomb-$level-$kind")) }
                } }
            }
        }
        "outgoing" -> for ((name, row) in result.outgoing) OutputRow("outgoing-$name", OUTPUT_REMOTE.getValue(name), row)
    }
}
