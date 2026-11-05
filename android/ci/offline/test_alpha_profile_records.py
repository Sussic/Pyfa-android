"""Learned/clone ledger contracts at Profiles; synthetic IDs are not cap data."""
from copy import deepcopy
import unittest
from android_bridge.offline.profiles import Profiles, ProfileError, ALL_FIVE
from android_bridge.offline.profile_graph import MemoryStore


class AlphaProfileRecordTests(unittest.TestCase):
    def model(self, state=None, clones=(41, 42)):
        store = MemoryStore(state)
        return Profiles('memory', 'a'*64, [1, 2], store_type=lambda _:store, clone_ids=clones), store

    def test_clone_choice_copy_save_as_and_same_choice_do_not_rewrite_learned_inputs(self):
        model, store = self.model(); pid = model.create('Pilot', source=ALL_FIVE)['profile_id']
        draft = model.begin(pid); draft.values['levels'] = {'1': None, '2': 0}; model.save(draft)
        model.bind('first', pid); model.bind('second', pid)
        model.save_clone(pid, model._profile(pid)['revision'], 41)
        before = model.snapshot(); durable = store.current
        model.save_clone(pid, model._profile(pid)['revision'], 41)
        self.assertEqual(model.snapshot(), before); self.assertIs(store.current, durable)
        copied = model.create('Copy', source=pid)['profile_id']
        saved = model.save(model.begin(pid), save_as='Save As')['profile_id']
        for identity in (copied, saved):
            self.assertEqual(model._profile(identity)['alpha_clone_id'], 41)
            self.assertEqual(model._profile(identity)['levels'], {'1':None, '2':0})
        model.save_clone(copied, model._profile(copied)['revision'], 42)
        model.save_clone(pid, model._profile(pid)['revision'], None)
        self.assertEqual(model._profile(pid)['levels'], {'1':None, '2':0})
        self.assertEqual(model._profile(saved)['alpha_clone_id'], 41)
        self.assertEqual(model._profile(copied)['alpha_clone_id'], 42)
        self.assertEqual(model.snapshot()['bindings']['first'], model.snapshot()['bindings']['second'])

    def test_all_legacy_formats_open_without_write_noop_then_first_edit_format4(self):
        model, _ = self.model(); pid = model.create('Pilot')['profile_id']
        for version in (1, 2, 3):
            state = model.snapshot(); state['format'] = version
            for row in state['profiles'].values():
                row.pop('alpha_clone_id')
                if version < 3: row.pop('sec_status')
                if version == 1: row.pop('implants')
            opened, store = self.model(state); durable = store.current
            self.assertEqual(opened.snapshot()['format'], 4)
            self.assertIsNone(opened._profile(pid)['alpha_clone_id'])
            opened.save_clone(pid, opened._profile(pid)['revision'], None)
            self.assertIs(store.current, durable)
            opened.save_clone(pid, opened._profile(pid)['revision'], 41)
            self.assertEqual(store.current.generation, durable.generation+1)
            self.assertEqual(opened.snapshot()['format'], 4)

    def test_unknown_clone_mixed_schema_stale_and_builtins_are_exact_refusals(self):
        model, store = self.model(); pid = model.create('Pilot')['profile_id']
        original = model.snapshot(); durable = store.current
        for value in (True, False, 0, -1, 41.0, '41', [], {}, 43):
            with self.assertRaises(ProfileError): model.save_clone(pid, model._profile(pid)['revision'], value)
            self.assertEqual(model.snapshot(), original); self.assertIs(store.current, durable)
        for builtin in ('builtin:all0', 'builtin:all5'):
            with self.assertRaises(ProfileError): model.save_clone(builtin, 0, 41)
        with self.assertRaises(ProfileError): model.save_clone(pid, True, 41)
        with self.assertRaises(ProfileError): model.save_clone(pid, model._profile(pid)['revision']+1, 41)
        for operation in (lambda s:s['profiles'][pid].pop('alpha_clone_id'),
                          lambda s:s.update(format=3), lambda s:s.update(format=5),
                          lambda s:s['profiles']['builtin:all5'].update(alpha_clone_id=41)):
            bad = deepcopy(original); operation(bad)
            with self.assertRaises(ProfileError): self.model(bad)


if __name__ == '__main__': unittest.main()
