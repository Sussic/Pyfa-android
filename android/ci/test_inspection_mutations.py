"""Guard mutation coverage and fail-closed execution, without native stand-ins."""
import unittest
from android.ci.inspection_mutations import CANONICAL_ROWS, FRESH_ROWS, IDENTITY, LINKED, CONTEXT_ROWS, rejected


class InspectorMutationTest(unittest.TestCase):
    def test_required_cases_are_distinct_and_preserved(self):
        for cases, expected in ((CANONICAL_ROWS, 31), (FRESH_ROWS, 5), (IDENTITY, 20), (LINKED, 14), (CONTEXT_ROWS, 18)):
            self.assertEqual(expected, len(cases))
            self.assertEqual(len(cases), len({name for name, mutate in cases}))
            self.assertTrue(all(callable(mutate) for name, mutate in cases))
        self.assertEqual({'wrong-phase', 'wrong-worker', 'noninteger-worker', 'missing-worker', 'missing-phase'},
                         {name for name, _ in FRESH_ROWS})
        self.assertTrue({'wrong_original_value_all_protocols', 'wrong_original_unit_all_protocols',
                         'wrong_equipment_all_protocols', 'nonempty_reopened_history'} <= {name for name, _ in IDENTITY})

    def test_accepted_mutation_and_unrelated_checker_error_never_become_passes(self):
        with self.assertRaisesRegex(AssertionError, 'corruption accepted'):
            rejected('guard-only', lambda: None, '0' * 64)
        def unrelated(): raise RuntimeError('unexpected checker failure')
        with self.assertRaises(RuntimeError): rejected('guard-only', unrelated, '0' * 64)
        def assertion(): raise AssertionError('guard rejection')
        self.assertEqual(dict(name='guard-only', mutated_sha256='0' * 64), rejected('guard-only', assertion, '0' * 64))


if __name__ == '__main__': unittest.main()
