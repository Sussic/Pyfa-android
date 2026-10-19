"""Real original context membership/coverage guards; no native pass is fabricated."""
from copy import deepcopy
import unittest
from android.ci.inspection_context_summary import load_fixture, context_roles, sequence, state_inputs, COUNTS


class ContextReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_fixture()

    def test_every_original_state_survives_phase_and_history_expansion(self):
        fixture = self.fixture
        self.assertEqual(107, len(fixture['cases']))
        for part, (low, high) in enumerate(((0, 8), (8, 33), (33, 58), (58, 83), (83, 107))):
            cases = fixture['cases'][low:high]
            states = [state for case in cases for _, state, original in sequence(case) if original]
            self.assertEqual(COUNTS[part], (len(cases), len(states), sum(len(state['targets']) for state in states)))
            for case in cases:
                expanded = sequence(case)
                expected_states = [state['replayed'] if state['action']['kind'].startswith('reverse') and
                                   not (state['action']['kind'] == 'reverse_remove' and case['family'] == 'booster')
                                   else state for state in case['states']]
                self.assertEqual(expected_states, [state for _, state, original in expanded if original])
                self.assertEqual('copy', expanded[-1][0])
                for restart in (1, 2):
                    phase = f'contexts{part}-restored{restart}'
                    self.assertEqual([(phase, case['states'][-1]['replayed'], False)], sequence(case, phase))

    def test_every_original_membership_accepts_only_proven_identity_changes(self):
        for case_index, case in enumerate(self.fixture['cases']):
            for state in case['states']:
                before = state['roles']; after = deepcopy(before)
                fit_id = 10000 + case_index
                after['fit'][0]['ID'] = fit_id
                booster_ids = {}
                for table in ('modules', 'drones', 'fighters', 'cargo', 'implants', 'boosters'):
                    key = 'groupID' if table in ('drones', 'fighters') else 'ID'
                    for index, row in enumerate(after[table]):
                        old = row[key]; row[key] = 100000 + index
                        if 'fitID' in row: row['fitID'] = fit_id
                        if table == 'boosters': booster_ids[old] = row[key]
                for row in after['booster_side_effects']: row['boosterID'] = booster_ids[row['boosterID']]
                context_roles(before, after)
                for table in ('cargo', 'implants', 'boosters'):
                    if not after[table]: continue
                    changes = (
                        lambda rows: rows[table][0].update(ID=True),
                        lambda rows: rows[table][0].update(itemID=0),
                        lambda rows: rows[table].pop(),
                        lambda rows: rows[table].append(deepcopy(rows[table][0])),
                    )
                    field = 'amount' if table == 'cargo' else 'active'
                    changes += (lambda rows: rows[table][0].update({field: 987654321}),)
                    for mutate in changes:
                        bad = deepcopy(after); mutate(bad)
                        with self.subTest(case=case_index, action=state['action'], table=table), self.assertRaises(AssertionError):
                            context_roles(before, bad)
                if after['booster_side_effects']:
                    for field, value in (('boosterID', 0), ('effectID', 0), ('active', 987654321)):
                        bad = deepcopy(after); bad['booster_side_effects'][0][field] = value
                        with self.subTest(case=case_index, field=field), self.assertRaises(AssertionError): context_roles(before, bad)
                bad = deepcopy(after); bad['mode'][0]['modeID'] = 0
                with self.assertRaises(AssertionError): context_roles(before, bad)

    def test_saved_inputs_reject_changed_original_flags_and_members(self):
        for case in self.fixture['cases']:
            expected = case['states'][1]
            spec = deepcopy(case['spec']); spec['implants'] = []; spec['boosters'] = []
            record = dict(spec=spec, skills={}, implants=[], projections=[], commands=[], inspection_ids={})
            for family in ('implant', 'booster'):
                targets = [target for target in expected['targets'] if target['context'] == family]
                if not targets: continue
                target = targets[0]
                values = {row['contract']['name']: row['contract']['value'] for row in target['properties'] if row['contract']['available']}
                row = dict(name=values['item']['name'], slot=values['slot'], active=True)
                if family == 'booster':
                    row['side_effects'] = [dict(effect_id=effect['effectID'], active=False) for effect in expected['roles']['booster_side_effects']]
                    record['boosters'] = [row]
                else: record['implants'] = [row]
            state_inputs(case, expected, record)
            changes = [lambda row: row['skills'].update(Synthetic=0),
                       lambda row: row['spec'].update(name='altered input'),
                       lambda row: row.update(extra=False)]
            if record['spec']['cargo']: changes.append(lambda row: row['spec']['cargo'][0].update(amount=987654321))
            if record['implants']: changes.append(lambda row: row['implants'][0].update(active=False))
            if 'boosters' in record:
                changes.extend([lambda row: row['boosters'][0].update(active=False), lambda row: row['boosters'][0].update(slot=0)])
                if record['boosters'][0]['side_effects']: changes.append(lambda row: row['boosters'][0]['side_effects'][0].update(active=True))
            for mutate in changes:
                bad = deepcopy(record); mutate(bad)
                with self.subTest(case=case['spec']['name']), self.assertRaises(AssertionError): state_inputs(case, expected, bad)

    def test_mode_edit_inputs_keep_original_vacancies_and_restrictions(self):
        for case in self.fixture['cases']:
            if case['family'] != 'mode': continue
            for expected in case['states']:
                if expected['action']['kind'] != 'set_mode': continue
                spec = deepcopy(case['spec'])
                spec.update(modules=deepcopy(expected['module_inputs']), implants=[], boosters=[],
                            mode=expected['action']['item_id'], ignore_restrictions=expected['ignore_restrictions'])
                record = dict(spec=spec, skills={}, implants=[], projections=[], commands=[], inspection_ids={})
                self.assertTrue(spec['modules'])
                self.assertEqual(len(expected['roles']['modules']), len(spec['modules']))
                state_inputs(case, expected, record)
                for mutate in (lambda row: row['spec']['modules'].pop(),
                               lambda row: row['spec']['modules'].append(deepcopy(row['spec']['modules'][0])),
                               lambda row: row['spec']['modules'][0].update(empty_slot='invalid'),
                               lambda row: row['spec'].update(ignore_restrictions=True),
                               lambda row: row['spec'].update(mode=0)):
                    bad = deepcopy(record); mutate(bad)
                    with self.subTest(hull=case['spec']['ship'], mode=expected['action']['item_id']), self.assertRaises(AssertionError):
                        state_inputs(case, expected, bad)


if __name__ == '__main__': unittest.main()
