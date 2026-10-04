"""Corrupted or obscured native keyboard evidence cannot satisfy visual geometry."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from charge_edit_summary import keyboard_viewport


class KeyboardViewportTests(unittest.TestCase):
    def setUp(self):
        self.good = dict(keyboard_visible=True, window_height=1920, status_top=72,
            navigation_bottom=72, ime_bottom=872, viewport_top=72.0, viewport_bottom=1048.0,
            field_top=880.0, field_bottom=1048.0, resize_mode=16)

    def test_complete_measured_viewport(self):
        keyboard_viewport(self.good)

    def test_each_obscured_boundary_is_rejected(self):
        for key, value in [('viewport_top', 0.0), ('viewport_bottom', 1049.0),
            ('field_top', 71.0), ('field_bottom', 1049.0), ('resize_mode', 32),
            ('ime_bottom', 72), ('keyboard_visible', False)]:
            with self.subTest(key=key):
                bad = deepcopy(self.good); bad[key] = value
                self.assertRaises(AssertionError, keyboard_viewport, bad)

    def test_missing_or_extra_measurement_is_rejected(self):
        for key in self.good:
            bad = deepcopy(self.good); del bad[key]
            with self.subTest(missing=key):self.assertRaises(AssertionError, keyboard_viewport, bad)
        bad = deepcopy(self.good); bad['invented'] = 0
        self.assertRaises(AssertionError, keyboard_viewport, bad)

    def test_boolean_nonfinite_and_fractional_insets_are_rejected(self):
        for key, value in [('field_top', True), ('viewport_top', float('nan')),
            ('viewport_bottom', float('inf')), ('ime_bottom', 872.5), ('window_height', True)]:
            bad = deepcopy(self.good); bad[key] = value
            with self.subTest(key=key):self.assertRaises(AssertionError, keyboard_viewport, bad)

    def test_closed_keyboard_preserves_safe_content(self):
        closed = dict(self.good, keyboard_visible=False, ime_bottom=0, viewport_bottom=1848.0)
        keyboard_viewport(closed, False)
        closed['ime_bottom'] = 872
        self.assertRaises(AssertionError, keyboard_viewport, closed, False)


if __name__ == '__main__':unittest.main()
