package io.github.sussic.pyfa

import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.semantics.ProgressBarRangeInfo
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/** Synthetic presentation contracts, not independent EOS or persistence oracles. */
@RunWith(AndroidJUnit4::class)
class MutationSliderPresentationTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()
    private val objectKey = "2".repeat(32)
    private val suffix = "$objectKey-10"
    private val valueTag = "mutation-value-$suffix"
    private val sliderTag = "mutation-slider-$suffix"
    private var changes = 0

    private fun available(value: Double, minimum: Double, maximum: Double, base: Double,
        higherIsBetter: Boolean = true) = MutationDisplayValue.Available(value, minimum, maximum,
            base, "%", higherIsBetter)
    private fun show(display: MutationDisplayValue, raw: Double = .75) {
        changes = 0
        val attribute = MutationDisplayAttribute(MutationAttribute(10, raw, "Synthetic roll", 108,
            -Double.MAX_VALUE, Double.MAX_VALUE, true), display)
        compose.runOnUiThread {
            compose.activity.setContent {
                MaterialTheme { Column {
                    var text by remember(attribute) { mutableStateOf(attribute.sourceValue(attribute.initialRepresentation).toString()) }
                    MutationRollEditor(attribute, objectKey, attribute.initialRepresentation, text, true,
                        onRepresentationChange = {}, onTextChange = { text = it; changes += 1 })
                } }
            }
        }
        compose.waitForIdle()
    }
    private fun text() = compose.onNodeWithTag(valueTag).fetchSemanticsNode()
        .config[SemanticsProperties.EditableText].text
    private fun progress(): ProgressBarRangeInfo = compose.onNodeWithTag(sliderTag).fetchSemanticsNode()
        .config[SemanticsProperties.ProgressBarRangeInfo]
    private fun setProgress(value: Float) {
        compose.onNodeWithTag(sliderTag).performSemanticsAction(SemanticsActions.SetProgress) { action ->
            assertTrue(action(value))
        }
        compose.waitForIdle()
    }
    private fun exact(expected: Double) = assertEquals(expected.toRawBits(), text().toDouble().toRawBits())

    @Test fun renderingAndFocusKeepExactSourceWhileTouchAndNumericShareOneDraft() {
        val source = 12.345678901234567
        show(available(source, 0.0, 100.0, 20.0))
        exact(source); assertEquals(0, changes)
        compose.onNodeWithTag(sliderTag).assert(SemanticsMatcher.expectValue(
            SemanticsProperties.StateDescription, "$source %; base 20.0 %"))
        compose.onNodeWithTag(valueTag).performClick(); compose.waitForIdle()
        exact(source); assertEquals(0, changes)
        // Real touch reaches the material track's better endpoint; it changes only
        // the same numeric draft that a caller later submits through existing Save.
        compose.onNodeWithTag(sliderTag).performTouchInput {
            swipe(center, Offset(width.toFloat() - 1f, center.y))
        }
        compose.waitForIdle(); exact(100.0); assertTrue(changes > 0)
        compose.onNodeWithTag(valueTag).performTextReplacement("10.0"); compose.waitForIdle()
        assertEquals(-.5f, progress().current, 0f)
        val precise = "13.123456789012345"
        compose.onNodeWithTag(valueTag).performTextReplacement(precise); compose.waitForIdle()
        assertEquals(precise, text())
    }

    @Test fun signedPiecewiseProgressUsesReturnedBaseAndDirectionWithoutAForcedGrid() {
        show(available(25.0, 0.0, 50.0, 20.0, higherIsBetter = false))
        // Pinned desktop AttributeSlider.SetValue: (25−20)/(50−20), inverted.
        assertEquals(-1f / 6f, progress().current, .000001f)
        assertEquals(-1f..1f, progress().range)
        setProgress(-1f); exact(50.0)
        setProgress(0f); exact(20.0)
        setProgress(1f); exact(0.0)
        setProgress(.1234567f)
        assertEquals(20.0 - .1234567f.toDouble() * 20.0, text().toDouble(), 0.0)
        assertEquals(0, progress().steps)
    }

    @Test fun negativeBoundsAndEndpointAnchorExposeOnlyTheAvailableSignedSide() {
        // Metadata is already sorted/converted by EOS; this adapter never does
        // an inverse-unit conversion or infers a base from the current roll.
        show(available(-6.0, -10.0, -2.0, -10.0, higherIsBetter = false))
        assertEquals(-1f..0f, progress().range)
        assertEquals(-.5f, progress().current, 0f)
        setProgress(-1f); exact(-2.0)
        setProgress(0f); exact(-10.0)
        show(available(0.0, 0.0, 10.0, 10.0))
        assertEquals(-1f..0f, progress().range)
        setProgress(0f); exact(10.0)
        setProgress(-1f); exact(0.0)
    }

    @Test fun exactDoubleEndpointsAndBaseRemainIndependentOfFloatCoordinates() {
        val minimum = .10000000000000002
        val base = .20000000000000004
        val maximum = .7000000000000001
        show(available(.4567890123456789, minimum, maximum, base))
        setProgress(-1f); exact(minimum)
        setProgress(1f); exact(maximum)
        setProgress(0f); exact(base)
    }

    @Test fun equalBoundsDisableDraggingAndPreserveTheFixedExactValue() {
        val fixed = .12345678901234568
        show(available(fixed, fixed, fixed, fixed))
        compose.onNodeWithTag(sliderTag).assertIsNotEnabled()
        compose.onNodeWithTag("mutation-slider-fixed-$suffix").assertExists()
        compose.onNodeWithTag(sliderTag).performTouchInput { swipeLeft() }
        compose.waitForIdle(); exact(fixed); assertEquals(0, changes)
    }

    @Test fun unavailableConversionAndNonfinitePresentationKeepHonestNumericFallbacks() {
        show(MutationDisplayValue.Unavailable("Unsupported numeric inverse"))
        compose.onNodeWithTag(sliderTag).assertDoesNotExist()
        compose.onNodeWithTag("mutation-display-$suffix").assertIsNotEnabled()
        compose.onNodeWithTag("mutation-display-unavailable-$suffix")
            .assertTextContains("Unsupported numeric inverse", substring = true)
        exact(.75); assertEquals(0, changes)
        // The saved scalar and bounds are finite, but this half-span overflows.
        // Refuse the touch representation rather than inventing a finite roll.
        show(available(1.0, -Double.MAX_VALUE, Double.MAX_VALUE, Double.MAX_VALUE))
        compose.onNodeWithTag(sliderTag).assertDoesNotExist()
        compose.onNodeWithTag("mutation-slider-unavailable-$suffix").assertExists()
        exact(1.0); assertEquals(0, changes)
    }

    @Test fun invalidNumericDraftNeverSilentlyBecomesATouchValue() {
        show(available(25.0, 0.0, 50.0, 20.0))
        for (invalid in listOf("NaN", "Infinity", "51", "")) {
            compose.onNodeWithTag(valueTag).performTextReplacement(invalid); compose.waitForIdle()
            assertEquals(invalid, text())
            compose.onNodeWithTag(sliderTag).assertDoesNotExist()
            compose.onNodeWithTag("mutation-slider-unavailable-$suffix").assertExists()
        }
        compose.onNodeWithTag(valueTag).performTextReplacement("25.0"); compose.waitForIdle()
        assertEquals(1f / 6f, progress().current, .000001f)
    }
}
