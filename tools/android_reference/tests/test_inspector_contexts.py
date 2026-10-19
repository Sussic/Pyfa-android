"""Guard the complete real fitted-context expectations against lost coverage."""
from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest

from tools.android_reference.inspector_contexts import validate_fixture

ROOT = Path(__file__).resolve().parents[3]


class ContextReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(gzip.decompress((ROOT / 'tools/android_reference/fixtures/inspector-contexts.json.gz').read_bytes()))

    def test_all_real_states_and_original_reversals(self):
        validate_fixture(self.fixture)
        self.assertEqual(107, len(self.fixture['cases']))
        self.assertEqual(805, sum(len(case['states']) for case in self.fixture['cases']))
        self.assertEqual(3030, sum(len(state['targets']) for case in self.fixture['cases'] for state in case['states']))

    def test_omitted_modes_boosters_side_effects_and_reversal_values_fail(self):
        def changed_case(index, mutate):
            fixture = dict(self.fixture)
            fixture['cases'] = list(self.fixture['cases'])
            fixture['cases'][index] = deepcopy(fixture['cases'][index])
            mutate(fixture['cases'][index])
            return fixture
        mutations = [
            lambda: {**self.fixture, 'sourceCommit': 'wrong'},
            lambda: {**self.fixture, 'boosterCatalogue': self.fixture['boosterCatalogue'][:-1]},
            lambda: {**self.fixture, 'boosterRepresentatives': self.fixture['boosterRepresentatives'][:-1]},
            lambda: {**self.fixture, 'cases': self.fixture['cases'][1:]},
            lambda: changed_case(0, lambda case: case['states'].pop()),
            lambda: changed_case(0, lambda case: case['states'][3]['targets'][0]['attributes']['precise'][0].update(current=999999999.0)),
            lambda: changed_case(6, lambda case: case['states'].pop(-2)),
            lambda: changed_case(7, lambda case: case['states'][-1]['targets'].pop()),
            lambda: changed_case(6, lambda case: case['states'][3].pop('replayed')),
            lambda: changed_case(6, lambda case: case['states'][3]['replayed']['targets'].pop()),
            lambda: changed_case(6, lambda case: case['states'][3]['replayed']['targets'][1]['properties'].pop()),
            lambda: changed_case(0, lambda case: case['states'][2]['replayed']['module_inputs'].pop()),
            lambda: changed_case(0, lambda case: case['states'][2]['replayed'].update(ignore_restrictions=True)),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(corruption=index), self.assertRaises((ValueError, KeyError, IndexError)):
                validate_fixture(mutate())


if __name__ == '__main__':
    unittest.main()
