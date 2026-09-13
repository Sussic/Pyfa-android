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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
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
    Text(stringResource(R.string.next_body), style = MaterialTheme.typography.bodyLarge)
    Button(onClick = onAbout, contentPadding = PaddingValues(horizontal = 24.dp, vertical = 16.dp)) {
        Text(stringResource(R.string.about_button))
    }
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
