"""Pure candidate receipt/decoder/history tests; no EOS execution or boot."""
from copy import deepcopy
from dataclasses import dataclass
from types import SimpleNamespace
import unittest

from tools.android_headless.check_remote_support_parity import scalar, frozen, full_history, changed_paths, deletion_histories
from tools.android_reference.remote_support.preflight import exact
from tools.android_reference.reference import compare


@dataclass(frozen=True)
class Action:
    label: str
    participants: frozenset
    changes: tuple
    legacy_token: object = None


class CandidateTests(unittest.TestCase):
    def test_scalar_preserves_type_and_unit(self):
        for value, kind in ((4, 'integer'), (4.0, 'decimal'), (None, 'unavailable')):
            row = dict(value=value, value_type=kind, unit='HP/s', display=None, detail=None)
            self.assertIs(type(value), type(scalar(row, 'HP/s')))
            with self.assertRaises(AssertionError): scalar(row, 'GJ/s')

    def test_scalar_rejects_boolean_and_wrong_type(self):
        row = dict(value=True, value_type='decimal', unit='HP/s', display='1', detail='1')
        with self.assertRaises(AssertionError): scalar(row, 'HP/s')
        row.update(value=1.0, value_type='integer')
        with self.assertRaises(AssertionError): scalar(row, 'HP/s')

    def test_raw_never_uses_numeric_tolerance(self):
        for actual in (0, False, 1e-12):
            with self.assertRaises(AssertionError): exact(0.0, actual, 'raw')
        compare(0.0, 1e-12, 'observed value')
        with self.assertRaises(ValueError): compare(False, 0, 'boolean observation')

    def test_full_history_payload_and_shared_identity(self):
        legacy = Action('old', frozenset(), (('field', None, 0.0),))
        shared = Action('shared', frozenset(('b', 'a')), (('range', None, 0.0),), legacy)
        session = SimpleNamespace(history=SimpleNamespace(sequence=4, rows={'a':((shared,), 1), 'b':((shared,), 1)}),
            graph=SimpleNamespace(_bridge=SimpleNamespace(_history=SimpleNamespace(rows={'a':((legacy,), 1)}))))
        first = full_history(session)
        self.assertEqual(first['rows']['a']['actions'], first['rows']['b']['actions'])
        self.assertEqual(first['actions'][0]['legacy_token_ref'], 0)
        changed = deepcopy(session)
        changed.history.rows['b'] = ((deepcopy(shared),), 1)
        with self.assertRaises(AssertionError): exact(first, full_history(changed), 'lost shared history action')
        changed = deepcopy(first); changed['actions'][0]['changes'][0][2] = 1e-12
        with self.assertRaises(AssertionError): exact(first, changed, 'history payload drift')

    def test_delete_prunes_conflicting_legacy_and_shared_actions(self):
        @dataclass(frozen=True)
        class Change:
            path: tuple
        legacy = Action('link', frozenset(), (Change(('projections',)),))
        action = Action('link', frozenset(('b',)), (), legacy)
        shared = Action('shared', frozenset(('a', 'b')), ())
        unaffected = Action('profile', frozenset(('b',)), ())
        before = {'a':{'projections':[]}, 'b':{'projections':['a']}, 'c':{'projections':['a']}}
        after = {'b':{'projections':[]}, 'c':{'projections':[]}}
        third = Action('link c', frozenset(('c',)), (), legacy)
        graph, old = deletion_histories({'a':((shared,),1), 'b':((action,shared,unaffected),3), 'c':((third,),1)}, {'b':((legacy,),1), 'c':((legacy,),1)}, before, after)
        self.assertEqual(old, {})
        self.assertEqual(graph, {'b':((unaffected,),1), 'c':((),0)})
        self.assertIs(graph['b'][0][0], unaffected)

    def test_changed_paths_preserves_typed_raw_input(self):
        self.assertEqual(list(changed_paths({'range':None, 'nested':{'x':0.0}}, {'range':0.0, 'nested':{'x':0}})),
                         [('nested','x'), ('range',)])

    def test_frozen_retains_none_and_present_markers(self):
        self.assertEqual(frozen(Action('x', frozenset(('b', 'a')), ((True, None, False, 0),))),
            dict(label='x', participants=['a', 'b'], changes=[[True, None, False, 0]], legacy_token=None))


if __name__ == '__main__': unittest.main()
