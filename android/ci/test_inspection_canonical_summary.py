"""Mutation checks for strict canonical report decoding and original SQL roles."""
from copy import deepcopy
from pathlib import Path
import unittest
from android.ci.inspection_canonical_summary import decode, sql_roles, observation_header


class CanonicalReportTest(unittest.TestCase):
    def test_fresh_observations_reject_preparation_bytes_and_wrong_worker(self):
        legacy = dict(case_index=0, fit_id='synthetic', sql_roles={}, targets=[])
        observation_header(legacy, 'canonical-restored1', 123)
        fresh = dict(legacy, phase='canonical-restored1', pid=123)
        observation_header(fresh, 'canonical-restored1', 123, fresh=True)
        for mutate in (lambda row: row.pop('phase'), lambda row: row.pop('pid'),
                       lambda row: row.update(phase='canonical'), lambda row: row.update(pid=122),
                       lambda row: row.update(pid=True), lambda row: row.update(pid=123.0),
                       lambda row: row.update(extra='unproven')):
            bad = deepcopy(fresh); mutate(bad)
            with self.subTest(mutation=mutate), self.assertRaises(AssertionError):
                observation_header(bad, 'canonical-restored1', 123, fresh=True)
        with self.assertRaises(AssertionError): observation_header(legacy, 'canonical-restored1', 123, fresh=True)
        with self.assertRaises(AssertionError): observation_header(fresh, 'canonical-restored1', 123)

    def test_duplicate_keys_and_nonfinite_numbers_are_rejected(self):
        for raw in ('{"x":1,"x":2}', '{"x":{"id":1,"id":2}}',
                    '{"x":NaN}', '{"x":Infinity}', '{"x":-Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(AssertionError): decode(raw)
        self.assertEqual({'x': [1, None, True, 1.5]}, decode('{"x":[1,null,true,1.5]}'))

    def test_original_sql_memberships_reject_changed_values_and_incomplete_tables(self):
        fixture = decode((Path(__file__).resolve().parents[2] /
                          'tools/android_reference/fixtures/inspector-identities.json').read_bytes())
        original = fixture['cases'][0]['expected']
        actual = deepcopy(original)
        actual['fit'][0]['ID'] = 100
        for table in ('modules', 'drones', 'fighters'):
            key = 'ID' if table == 'modules' else 'groupID'
            for index, row in enumerate(actual[table]):
                row[key] = 1000 + index; row['fitID'] = 100
        sql_roles(original, actual)
        changes = (
            lambda row: row.pop('fighters'),
            lambda row: row['fit'][0].update(shipID=0),
            lambda row: row['modules'][0].update(itemID=0),
            lambda row: row['modules'][0].update(chargeID=None),
            lambda row: row['modules'][0].update(position=999),
            lambda row: row['modules'][0].update(fitID=101),
            lambda row: row['modules'][0].update(ID=True),
            lambda row: row['modules'][0].update(ID=0),
            lambda row: row['modules'][1].update(ID=row['modules'][0]['ID']),
            lambda row: row['modules'].pop(),
            lambda row: row['drones'][0].update(amountActive=0),
            lambda row: row['fit'].append(deepcopy(row['fit'][0])),
        )
        for mutate in changes:
            bad = deepcopy(actual); mutate(bad)
            with self.subTest(mutation=mutate), self.assertRaises(AssertionError): sql_roles(original, bad)


if __name__ == '__main__': unittest.main()
