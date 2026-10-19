package io.github.sussic.pyfa

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

internal data class OfflinePlotSeries(val label: String, val x: List<Double>, val y: List<Double>)
private val CURVE_COLORS = listOf(Color(0xFFACD8B3), Color(0xFF90CAF9), Color(0xFFFFCC80), Color(0xFFCE93D8),
    Color(0xFFEF9A9A), Color(0xFF80CBC4), Color(0xFFFFFF8D), Color(0xFFB0BEC5))

/** Finite source coordinates may span more than Double.MAX_VALUE without being invalid. */
internal fun offlinePlotFraction(value: Double, low: Double, high: Double): Double {
    if (low == high) return 0.5
    val span = high - low
    return if (span.isFinite()) (value - low) / span
        else (value / 2.0 - low / 2.0) / (high / 2.0 - low / 2.0)
}

/** Shared drawing surface only: preserve engine sample order, including vertical capacitor steps. */
@Composable
internal fun OfflineSamplePlot(series: List<OfflinePlotSeries>, minX: Double, maxX: Double,
    xUnit: String, yUnit: String, tagPrefix: String, emptyMessage: String) {
    val values = series.flatMap { it.y }
    if (values.isEmpty()) { Text(emptyMessage, Modifier.testTag("$tagPrefix-empty")); return }
    val minY = values.minOrNull()!!; val maxY = values.maxOrNull()!!
    Text("X: $minX–$maxX $xUnit · Y: $minY–$maxY $yUnit", Modifier.testTag("$tagPrefix-axes"))
    Canvas(Modifier.fillMaxWidth().height(240.dp).testTag("$tagPrefix-canvas")) {
        val inset = 12.dp.toPx(); val width = size.width - 2 * inset; val height = size.height - 2 * inset
        fun point(x: Double, y: Double) = Offset(
            inset + offlinePlotFraction(x, minX, maxX).toFloat() * width,
            inset + (1 - offlinePlotFraction(y, minY, maxY)).toFloat() * height)
        drawLine(Color.Gray, Offset(inset, inset), Offset(inset, size.height - inset))
        drawLine(Color.Gray, Offset(inset, size.height - inset), Offset(size.width - inset, size.height - inset))
        series.forEachIndexed { index, row ->
            if (row.x.isNotEmpty()) {
                val path = Path(); val first = point(row.x.first(), row.y.first()); path.moveTo(first.x, first.y)
                for (i in 1 until row.x.size) { val p = point(row.x[i], row.y[i]); path.lineTo(p.x, p.y) }
                if (row.x.size == 1) drawCircle(CURVE_COLORS[index], 3.dp.toPx(), first)
                else drawPath(path, CURVE_COLORS[index], style = Stroke(2.dp.toPx()))
            }
        }
    }
    series.forEachIndexed { index, row -> Text("${index + 1}. ${row.label}", color = CURVE_COLORS[index]) }
}
