package io.github.sussic.pyfa

import android.os.Bundle
import androidx.lifecycle.ViewModelProvider
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.BackHandler
import androidx.activity.compose.ReportDrawnWhen
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import java.text.NumberFormat
import kotlinx.coroutines.Dispatchers

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        EngineRuntime.start(applicationContext)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
        )
        setContent {
            // Keep worker emissions on the Android UI queue, including when a
            // test recomposer uses an unconfined effect dispatcher.
            val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
            ReportDrawnWhen { engine is EngineState.Ready || engine is EngineState.Empty }
            PyfaApp(ViewModelProvider(this)[FitLibraryModel::class.java],
                ViewModelProvider(this)[EquipmentModel::class.java], ViewModelProvider(this)[ModuleEditorModel::class.java],
                ViewModelProvider(this)[ChargeEditorModel::class.java], ViewModelProvider(this)[VariationEditorModel::class.java],
                ViewModelProvider(this)[RackEditorModel::class.java])
        }
    }

    override fun reportFullyDrawn() {
        super.reportFullyDrawn()
        EngineRuntime.recordStartupDraw(applicationContext)
    }
}

@Composable
private fun PyfaApp(libraryModel: FitLibraryModel, equipmentModel: EquipmentModel, moduleModel: ModuleEditorModel, chargeModel: ChargeEditorModel, variationModel: VariationEditorModel, rackModel: RackEditorModel) {
    var showAbout by rememberSaveable { mutableStateOf(false) }
    var showEquipment by rememberSaveable { mutableStateOf(false) }
    var showModules by rememberSaveable { mutableStateOf(false) }
    var showCharges by rememberSaveable { mutableStateOf(false) }
    var showVariations by rememberSaveable { mutableStateOf(false) }
    var showRack by rememberSaveable { mutableStateOf(false) }
    fun variations(position: Int?) {
        variationModel.open((EngineRuntime.state.value as? EngineState.Ready)?.fit?.id, position)
        showVariations = true
    }
    fun charges(position: Int?) {
        chargeModel.open((EngineRuntime.state.value as? EngineState.Ready)?.fit?.id, position)
        showCharges = true
    }
    BackHandler(enabled = showAbout) { showAbout = false }
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Color(0xFFACD8B3),
            onPrimary = Color(0xFF153820),
            background = Color(0xFF111713),
            surface = Color(0xFF111713),
            surfaceVariant = Color(0xFF29352C),
            onBackground = Color(0xFFE0E6DD),
            onSurface = Color(0xFFE0E6DD),
        ),
    ) {
        Scaffold { insets ->
            Box(Modifier.fillMaxSize().padding(insets), contentAlignment = Alignment.TopCenter) {
                key(showAbout, showEquipment, showModules, showCharges, showVariations, showRack) {
                    Column(
                        Modifier.widthIn(max = 600.dp).fillMaxWidth()
                            .verticalScroll(rememberScrollState()).padding(24.dp),
                        verticalArrangement = Arrangement.spacedBy(if (showEquipment || showModules || showCharges || showVariations || showRack) 8.dp else 24.dp),
                    ) {
                        Text(
                            stringResource(R.string.brand),
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        if (showRack) {
                            RackEditor(rackModel, onBack = { showRack = false })
                        } else if (showVariations) {
                            VariationEditor(variationModel, onBack = { showVariations = false })
                        } else if (showCharges) {
                            ChargeEditor(chargeModel, onBack = { showCharges = false })
                        } else if (showEquipment) {
                            EquipmentBrowser(equipmentModel, moduleModel, onBack = { showEquipment = false },
                                onViewFit = { showEquipment = false; showModules = true }, onCharges = { charges(null) })
                        } else if (showModules) {
                            ModuleEditor(moduleModel, onBrowse = { showEquipment = true }, onBack = { showModules = false },
                                onCharges = { charges(it) }, onVariations = { variations(it) }, onArrange = {
                                    rackModel.open((EngineRuntime.state.value as? EngineState.Ready)?.fit?.id, null)
                                    showRack = true
                                })
                        } else if (showAbout) {
                            AboutBuild(onBack = { showAbout = false })
                        } else {
                            Home(libraryModel, onAbout = { showAbout = true },
                                onEquipment = { moduleModel.replacePosition = null; showEquipment = true },
                                onModules = { showModules = true }, onVariations = { variations(null) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Home(libraryModel: FitLibraryModel, onAbout: () -> Unit, onEquipment: () -> Unit, onModules: () -> Unit, onVariations: () -> Unit) {
    val context = LocalContext.current
    val focus = LocalFocusManager.current
    val engine by EngineRuntime.state.collectAsState(context = Dispatchers.Main)
    var expanded by rememberSaveable { mutableStateOf(false) }
    val selectedTitle = remember { BringIntoViewRequester() }
    LaunchedEffect(libraryModel.fitJump.value) {
        if (libraryModel.fitJump.value > 0) selectedTitle.bringIntoView()
    }
    Text(
        stringResource(R.string.home_title),
        style = MaterialTheme.typography.headlineLarge,
        fontWeight = FontWeight.SemiBold,
    )
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Text(
                stringResource(R.string.milestone),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(stringResource(R.string.status_title), style = MaterialTheme.typography.titleLarge)
            Text(stringResource(R.string.status_body), style = MaterialTheme.typography.bodyLarge)
        }
    }
    Button(onClick = onAbout, contentPadding = PaddingValues(horizontal = 24.dp, vertical = 16.dp)) {
        Text(stringResource(R.string.about_button))
    }
    if (engine is EngineState.Ready || engine is EngineState.Empty) {
        Button(onClick = onEquipment, modifier = Modifier.testTag("equipment-open")) { Text("Browse equipment") }
        OpenFits()
    }
    when (val current = engine) {
        EngineState.Loading -> Text(stringResource(R.string.engine_loading))
        is EngineState.Failed -> {
            Text(stringResource(R.string.engine_failed), color = MaterialTheme.colorScheme.error)
            Text(current.message, style = MaterialTheme.typography.bodySmall)
        }
        is EngineState.Empty -> {
            current.error?.let { Text(it.message, color = MaterialTheme.colorScheme.error) }
        }
        is EngineState.Ready -> {
            val stats = current.fit.stats
            val ammunition = current.fit.modules.firstOrNull()?.charge ?: stringResource(R.string.no_ammunition)
            current.error?.let { Text(it.message, color = MaterialTheme.colorScheme.error) }
            Text(current.fit.name, style = MaterialTheme.typography.titleLarge, modifier = Modifier.bringIntoViewRequester(selectedTitle))
            TextButton(onClick = {
                focus.clearFocus()
                EngineRuntime.catalog.value.hulls.find { it.name == current.fit.ship }?.let(libraryModel::showHull)
            }, modifier = Modifier.testTag("back-to-hull")) { Text("Browse ${current.fit.ship} fits") }
            val sampleGuns = current.fit.modules.take(2).size == 2 &&
                current.fit.modules.take(2).all { it.name == "Dual 150mm Railgun II" }
            if (sampleGuns) Text(stringResource(R.string.sample_ammunition, ammunition))
            else Text(current.fit.ship + " · " + current.fit.modules.count { it.emptySlot == null } + " modules")
            Button(onClick = onModules, modifier = Modifier.testTag("modules-open")) { Text("Edit modules") }
            TextButton(onClick = onVariations, modifier = Modifier.testTag("variations-open")) { Text("Item variations") }
            if (sampleGuns) Button(onClick = {
                EngineRuntime.setAmmunition(context, if (ammunition == "Iron Charge M") "Antimatter Charge M" else "Iron Charge M")
            }) { Text(stringResource(R.string.switch_ammunition)) }
            for ((name, label) in listOf(
                "total_dps" to R.string.total_dps,
                "drone_control_range" to R.string.drone_control_range,
                "gun_optimal" to R.string.gun_optimal,
            )) {
                Text(stringResource(label) + ": " + formatStat(stats.getValue(name)))
            }
            TextButton(onClick = { expanded = !expanded }) {
                Text(stringResource(if (expanded) R.string.hide_attributes else R.string.all_attributes))
            }
            if (expanded) {
                for (name in stats.keys.sorted()) {
                    Text(name.replace('_', ' ') + ": " + formatStat(stats.getValue(name)))
                }
            }
        }
    }
    if (engine is EngineState.Ready || engine is EngineState.Empty) FitLibrary(libraryModel)
}

internal fun formatStat(stat: Stat): String {
    if (stat.value == StatValue.Unavailable) return "Unavailable"
    val value = stat.value.raw
    val unit = stat.unit
    val formatted = if (value is Number) NumberFormat.getNumberInstance().apply {
        maximumFractionDigits = 3
    }.format(value) else value.toString()
    return if (unit == "boolean") formatted else "$formatted $unit"
}

@Composable
private fun AboutBuild(onBack: () -> Unit) {
    Text(stringResource(R.string.about_title), style = MaterialTheme.typography.headlineLarge)
    Text(stringResource(R.string.version, BuildConfig.VERSION_NAME), style = MaterialTheme.typography.labelLarge)
    Text(stringResource(R.string.about_goal), style = MaterialTheme.typography.bodyLarge)
    Text(stringResource(R.string.about_scope), style = MaterialTheme.typography.bodyLarge)
    Text(stringResource(R.string.about_credit), style = MaterialTheme.typography.bodyMedium)
    Text(stringResource(R.string.source_url), color = MaterialTheme.colorScheme.primary)
    Text(stringResource(R.string.license_label), style = MaterialTheme.typography.bodySmall)
    TextButton(onClick = onBack) { Text(stringResource(R.string.back)) }
}
