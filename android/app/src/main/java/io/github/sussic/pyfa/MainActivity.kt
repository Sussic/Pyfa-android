package io.github.sussic.pyfa

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.BackHandler
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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.json.JSONObject
import java.text.NumberFormat

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        EngineRuntime.start(applicationContext)
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.dark(android.graphics.Color.TRANSPARENT),
        )
        setContent { PyfaApp() }
    }
}

@Composable
private fun PyfaApp() {
    var showAbout by rememberSaveable { mutableStateOf(false) }
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
                key(showAbout) {
                    Column(
                        Modifier.widthIn(max = 600.dp).fillMaxWidth()
                            .verticalScroll(rememberScrollState()).padding(24.dp),
                        verticalArrangement = Arrangement.spacedBy(24.dp),
                    ) {
                        Text(
                            stringResource(R.string.brand),
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        if (showAbout) {
                            AboutBuild(onBack = { showAbout = false })
                        } else {
                            Home(onAbout = { showAbout = true })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun Home(onAbout: () -> Unit) {
    val context = LocalContext.current
    val engine by EngineRuntime.state.collectAsState()
    var expanded by rememberSaveable { mutableStateOf(false) }
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
    when (val current = engine) {
        EngineState.Loading -> Text(stringResource(R.string.engine_loading))
        is EngineState.Failed -> {
            Text(stringResource(R.string.engine_failed), color = MaterialTheme.colorScheme.error)
            Text(current.message, style = MaterialTheme.typography.bodySmall)
        }
        is EngineState.Ready -> {
            val result = JSONObject(current.result)
            val stats = result.getJSONObject("stats")
            val ammunition = result.getString("ammunition")
            Text(stringResource(R.string.sample_title), style = MaterialTheme.typography.titleLarge)
            Text(stringResource(R.string.sample_ammunition, ammunition))
            Button(onClick = {
                EngineRuntime.setAmmunition(context, if (ammunition == "Iron Charge M") "Antimatter Charge M" else "Iron Charge M")
            }) { Text(stringResource(R.string.switch_ammunition)) }
            for ((name, label) in listOf(
                "total_dps" to R.string.total_dps,
                "drone_control_range" to R.string.drone_control_range,
                "gun_optimal" to R.string.gun_optimal,
            )) {
                Text(stringResource(label) + ": " + formatStat(stats.getJSONObject(name)))
            }
            TextButton(onClick = { expanded = !expanded }) {
                Text(stringResource(if (expanded) R.string.hide_attributes else R.string.all_attributes))
            }
            if (expanded) {
                for (name in stats.keys().asSequence().sorted()) {
                    Text(name.replace('_', ' ') + ": " + formatStat(stats.getJSONObject(name)))
                }
            }
        }
    }
}

private fun formatStat(stat: JSONObject): String {
    val value = stat.get("value")
    val unit = stat.getString("unit")
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
