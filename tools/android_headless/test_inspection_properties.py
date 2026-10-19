"""Property regressions for portable diagnostics and honest absent values."""
import unittest

from android_bridge.inspection import properties


class PropertyTests(unittest.TestCase):
    def test_none_zero_false_and_infinities_remain_distinct(self):
        class Owner:
            missing = None
            zero = 0
            disabled = False
            positive = float('inf')
            negative = float('-inf')
            invalid = float('nan')

        rows = {row['name']: row for row in properties(Owner(), None)}
        self.assertEqual((True, None, 'None'), tuple(rows['missing'][key] for key in ('available', 'value', 'display')))
        self.assertEqual((True, 0, '0'), tuple(rows['zero'][key] for key in ('available', 'value', 'display')))
        self.assertEqual((True, False, 'False'), tuple(rows['disabled'][key] for key in ('available', 'value', 'display')))
        for name, kind, text in (('positive', 'positive_infinity', 'inf'), ('negative', 'negative_infinity', '-inf')):
            self.assertEqual({'number_kind': kind}, rows[name]['value'])
            self.assertEqual(text, rows[name]['display'])
        self.assertFalse(rows['invalid']['available'])
        self.assertIsNone(rows['invalid']['value'])
        self.assertIsNone(rows['invalid']['display'])
        self.assertEqual('Unavailable property (ValueError)', rows['invalid']['reason'])

    def test_proxy_cache_addresses_are_normalized_without_losing_members(self):
        class Owner:
            pass
        owner = Owner()
        setattr(owner, '_AssociationProxy_group_123456_inst', object())
        setattr(owner, '_unrelated_123456_inst', object())
        rows = {row['name']: row for row in properties(owner, None)}
        self.assertIn('_AssociationProxy_group_inst', rows)
        self.assertIn('_unrelated_123456_inst', rows)
        self.assertEqual('Private diagnostic member', rows['_AssociationProxy_group_inst']['reason'])
        setattr(owner, '_AssociationProxy_group_789012_inst', object())
        with self.assertRaisesRegex(ValueError, 'Ambiguous normalized property names'):
            properties(owner, None)


if __name__ == '__main__':
    unittest.main()
