"""Pure shared-timeline regressions; no EOS/database/native execution."""
from copy import deepcopy
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, os.environ.get('PYFA_CURRENT_REPO', str(Path(__file__).resolve().parents[3])))

from android_bridge.history import EditHistory, LIMIT
from android_bridge.offline.graph_history import GraphHistory, inputs


def state():
    return {
        'fit_graph': {
            'records': {
                'a': {'spec': {'name': 'A', 'notes': '', 'skill_level': 5}, 'skills': {}},
                'b': {'spec': {'name': 'B', 'notes': '', 'skill_level': 5}, 'skills': {}},
            },
            'revisions': {'a': 3, 'b': 4},
            'recent': [42],
            'modified': {'a': 5, 'b': 6},
        },
        'profiles': {
            'profiles': {'p': {'name': 'Pilot', 'levels': {}, 'revision': 2}},
            'bindings': {
                'a': {'profile_id': 'p', 'revision': 2},
                'b': {'profile_id': 'p', 'revision': 3},
            },
        },
        'imports': {'saved-request': {'fit_ids': ['a']}},
    }


def renamed(before, name='Updated pilot'):
    after = deepcopy(before)
    after['profiles']['profiles']['p']['name'] = name
    return after


class GraphHistoryTests(unittest.TestCase):
    def setUp(self):
        self.before = state()
        self.after = renamed(self.before)
        self.shared = GraphHistory().record(self.before, self.after, 'Shared profile', {'a', 'b'})

    def test_shared_undo_and_redo_move_every_cursor(self):
        result, undone, action = self.shared.replay('a', False, self.after)
        self.assertEqual(result, inputs(self.before))
        for key in ('a', 'b'):
            self.assertEqual(undone.details(key)['undo_count'], 0)
            self.assertEqual(undone.details(key)['redo_count'], 1)
        restored, redone, repeated = undone.replay('b', True, self.before)
        self.assertIs(action, repeated)
        self.assertEqual(restored, inputs(self.after))
        for key in ('a', 'b'):
            self.assertEqual(redone.details(key)['undo_count'], 1)
            self.assertEqual(redone.details(key)['redo_count'], 0)
        self.assertEqual(self.shared.details('a')['undo_count'], 1)

    def test_shared_replay_waits_for_later_local_action(self):
        history = self.shared.record_legacy('Rename B', 'b', object())
        original = deepcopy(self.after)
        with self.assertRaisesRegex(ValueError, 'newer edits'):
            history.replay('a', False, self.after)
        self.assertEqual(self.after, original)
        self.assertEqual(history.details('a')['undo_count'], 1)
        self.assertEqual(history.details('b')['undo_count'], 2)

    def test_legacy_branch_removes_shared_redo_everywhere(self):
        _, history, _ = self.shared.replay('a', False, self.after)
        branch = history.record_legacy('Branch A', 'a', object())
        self.assertEqual(branch.details('a')['undo_label'], 'Branch A')
        self.assertEqual(branch.details('b')['redo_count'], 0)
        self.assertEqual(branch.details('b')['undo_count'], 0)
        self.assertEqual(history.details('b')['redo_count'], 1)

    def test_profile_branch_removes_shared_redo_everywhere(self):
        _, history, _ = self.shared.replay('a', False, self.after)
        branch = history.record(self.before, renamed(self.before, 'New branch'), 'Profile branch', {'a'})
        self.assertEqual(branch.details('a')['undo_label'], 'Profile branch')
        self.assertEqual(branch.details('b')['redo_count'], 0)

    def test_branch_retains_unrelated_later_redo_on_other_fit(self):
        token = object()
        history = self.shared.record_legacy('Rename B', 'b', token)
        _, history, _ = history.replay('b', False, self.after)
        _, history, _ = history.replay('a', False, self.after)
        branch = history.record_legacy('Branch A', 'a', object())
        self.assertEqual(branch.details('b')['redo_count'], 1)
        self.assertEqual(branch.details('b')['redo_label'], 'Rename B')
        _, history, action = branch.replay('b', True, self.before)
        self.assertIs(action.legacy_token, token)
        self.assertEqual(history.details('b')['undo_count'], 1)

    def test_legacy_limit_eviction_removes_shared_action_everywhere(self):
        history = self.shared
        for index in range(LIMIT):
            history = history.record_legacy('Local %d' % index, 'a', object())
        self.assertEqual(history.details('a')['undo_count'], LIMIT)
        self.assertEqual(history.details('b')['undo_count'], 0)
        self.assertEqual(history.details('b')['redo_count'], 0)
        self.assertEqual(self.shared.details('b')['undo_count'], 1)

    def test_profile_limit_eviction_removes_shared_action_everywhere(self):
        history = self.shared
        previous = self.after
        for index in range(LIMIT):
            current = renamed(previous, 'Pilot %d' % index)
            history = history.record(previous, current, 'Local profile', {'a'})
            previous = current
        self.assertEqual(history.details('a')['undo_count'], LIMIT)
        self.assertEqual(history.details('b')['undo_count'], 0)

    def test_prune_retains_later_independent_action(self):
        token = object()
        history = self.shared.record_legacy('Rename B', 'b', token)
        pruned = history.prune({'b', 'library'})
        self.assertNotIn('a', pruned.rows)
        self.assertEqual(pruned.details('b')['undo_count'], 1)
        self.assertEqual(pruned.details('b')['undo_label'], 'Rename B')
        _, undone, action = pruned.replay('b', False, self.after)
        self.assertIs(action.legacy_token, token)
        self.assertEqual(undone.details('b')['redo_count'], 1)

    def test_prune_removes_shared_redo_and_keeps_independent_redo(self):
        history = self.shared.record_legacy('Rename B', 'b', object())
        _, history, _ = history.replay('b', False, self.after)
        _, history, _ = history.replay('a', False, self.after)
        pruned = history.prune({'b'})
        self.assertEqual(pruned.details('b')['undo_count'], 0)
        self.assertEqual(pruned.details('b')['redo_count'], 1)
        self.assertEqual(pruned.details('b')['redo_label'], 'Rename B')

    def test_noop_does_not_branch_or_add_history(self):
        _, history, _ = self.shared.replay('a', False, self.after)
        noop = deepcopy(self.before)
        noop['profiles']['profiles']['p']['revision'] += 1
        noop['profiles']['bindings']['a']['revision'] += 1
        noop['fit_graph']['revisions']['a'] += 1
        noop['fit_graph']['modified']['a'] += 1
        noop['fit_graph']['recent'] = [99]
        noop['fit_graph']['records']['a']['skills'] = {'Derived skill': 3}
        noop['fit_graph']['records']['a']['spec']['skill_level'] = 0
        noop['imports']['another-request'] = {'fit_ids': ['b']}
        self.assertIs(history.record(self.before, noop, 'No-op', {'a'}), history)
        self.assertEqual(history.details('b')['redo_count'], 1)

    def test_direct_note_survives_profile_undo(self):
        current = deepcopy(self.after)
        current['fit_graph']['records']['b']['spec']['notes'] = 'Keep this direct note'
        result, _, _ = self.shared.replay('a', False, current)
        self.assertEqual(result['records']['b']['spec']['notes'], 'Keep this direct note')
        self.assertEqual(result['profiles']['profiles']['p']['name'], 'Pilot')

    def test_conflicting_input_rejects_without_moving_cursors(self):
        current = renamed(self.after, 'Untracked change')
        with self.assertRaisesRegex(ValueError, 'Inputs changed'):
            self.shared.replay('a', False, current)
        for key in ('a', 'b'):
            self.assertEqual(self.shared.details(key)['undo_count'], 1)
            self.assertEqual(self.shared.details(key)['redo_count'], 0)

    def test_sync_removes_only_missing_legacy_tokens(self):
        first, second = object(), object()
        history = self.shared.record_legacy('First', 'a', first).record_legacy('Second', 'a', second)
        _, history, _ = history.replay('a', False, self.after)
        synced = history.sync_legacy(EditHistory({'a': ((second,), 0)}))
        self.assertEqual(synced.details('a')['undo_count'], 1)
        self.assertEqual(synced.details('a')['undo_label'], 'Shared profile')
        self.assertEqual(synced.details('a')['redo_count'], 1)
        self.assertEqual(synced.details('a')['redo_label'], 'Second')
        self.assertEqual(synced.details('b')['undo_count'], 1)

    def test_history_inputs_exclude_receipts_and_all_monotonic_metadata(self):
        projected = inputs(self.before)
        self.assertEqual(set(projected), {'records', 'profiles', 'targets', 'damage_patterns', 'implant_sets'})
        self.assertEqual(projected['targets'],dict(version=1,profiles={},bindings={}))
        self.assertEqual(projected['damage_patterns'],dict(version=2,patterns={},bindings={}))
        self.assertEqual(projected['implant_sets'],dict(version=1,sets={}))
        self.assertNotIn('revision', projected['profiles']['profiles']['p'])
        self.assertNotIn('revision', projected['profiles']['bindings']['a'])
        self.assertNotIn('skills', projected['records']['a'])
        self.assertNotIn('skill_level', projected['records']['a']['spec'])
        projected['records']['a']['spec']['name'] = 'Detached'
        self.assertEqual(self.before['fit_graph']['records']['a']['spec']['name'], 'A')


if __name__ == '__main__':
    unittest.main()
