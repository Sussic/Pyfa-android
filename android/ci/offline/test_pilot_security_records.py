"""D04.2 M1/M2 pure authority contracts; source prepared, not execution proof."""
from copy import deepcopy
import math
import os
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, os.environ['PYFA_CURRENT_REPO'])
from android_bridge import pilot_security as security
from android_bridge.offline.profile_graph import MemoryStore
from android_bridge.offline.profiles import Profiles, ProfileError, BUILTINS
from android_bridge.offline.target_profiles import exact


class PilotSecurityRecordTests(unittest.TestCase):
    def model(self, state=None):
        store = MemoryStore(state)
        return Profiles('memory', 'a' * 64, [1, 2], store_type=lambda _: store), store

    def test_security_scalar_and_nullable_private_domain(self):
        for value in (-10, 5, 0, -0.0, 2.75, -6.25):
            self.assertIs(security.number(value), value)
        self.assertIsNone(security.number(None, nullable=True))
        for value in (None, True, False, '0', -10.01, 5.01, math.inf, -math.inf, math.nan, {}, []):
            with self.subTest(value=value), self.assertRaises(ProfileError):
                security.number(value)

    def test_only_exact_six_id_name_pairs_are_eligible(self):
        expected = {44993: 'Pacifier', 44995: 'Enforcer', 44996: 'Marshal',
                    85062: 'Sidewinder', 85229: 'Cobra', 85236: 'Python'}
        self.assertEqual(security.HULLS, expected)
        for identity, name in expected.items():
            self.assertTrue(security.eligible(SimpleNamespace(ID=identity, name=name)))
            self.assertFalse(security.eligible(SimpleNamespace(ID=identity, name='Rifter')))
        self.assertFalse(security.eligible(SimpleNamespace(ID=587, name='Pacifier')))
        self.assertEqual(security.PRESETS, [-10, -8, -6, -4, -2, 0, 1, 2, 3, 4, 5])
        self.assertTrue(all(type(value) is int for value in security.PRESETS))

    def test_profile_formats_migrate_in_memory_only(self):
        modern, _ = self.model()
        pid = modern.create('Custom')['profile_id']
        for version in (1, 2):
            old = modern.snapshot(); old['format'] = version
            for row in old['profiles'].values():
                row.pop('sec_status')
                if version == 1: row.pop('implants')
            model, store = self.model(old); durable = store.current
            self.assertEqual(model.snapshot()['format'], 3)
            self.assertTrue(exact(model._profile(pid)['sec_status'], 0.0))
            self.assertTrue(exact(model._profile('builtin:all0')['sec_status'], 0.0))
            self.assertTrue(exact(model._profile('builtin:all5')['sec_status'], 5.0))
            model.save_security(pid, model._profile(pid)['revision'], -0.0, save_as=None)
            self.assertIs(store.current, durable)
            model.save_security(pid, model._profile(pid)['revision'], -6.25, save_as=None)
            self.assertEqual(store.current.generation, durable.generation + 1)

    def test_strict_profile_schema_and_representation_exact_builtins(self):
        model, _ = self.model(); state = model.snapshot()
        mutations = [lambda s: s['profiles']['builtin:all0'].update(sec_status=-0.0),
                     lambda s: s['profiles']['builtin:all0'].update(sec_status=0),
                     lambda s: s['profiles']['builtin:all5'].update(sec_status=5),
                     lambda s: s['profiles']['builtin:all5'].pop('sec_status'),
                     lambda s: s.update(format=2),
                     lambda s: s['profiles']['builtin:all0'].update(extra=0)]
        for mutate in mutations:
            bad = deepcopy(state); mutate(bad)
            with self.assertRaises((ProfileError, ValueError)): self.model(bad)

    def test_save_scalar_noop_guard_and_complete_save_as(self):
        model, store = self.model(); pid = model.create('Original', source='builtin:all5')['profile_id']
        row = deepcopy(model._profile(pid)); saved = store.current
        model.save_security(pid, row['revision'], 5, save_as=None)
        self.assertIs(store.current, saved)
        self.assertTrue(exact(model._profile(pid)['sec_status'], 5.0))
        for revision in (True, 0, row['revision'] + 1):
            with self.assertRaises(ProfileError): model.save_security(pid, revision, 5, save_as=None)
        for builtin in BUILTINS:
            with self.assertRaises(ProfileError): model.save_security(builtin, 0, 0, save_as='Copy')
        copied = model.save_security(pid, row['revision'], -0.0, save_as='Saved copy')['profile_id']
        self.assertNotEqual(copied, pid); self.assertTrue(exact(model._profile(pid), row))
        self.assertTrue(exact(model._profile(copied)['sec_status'], -0.0))
        self.assertEqual(model._profile(copied)['default_level'], row['default_level'])
        self.assertEqual(model._profile(copied)['levels'], row['levels'])

    def test_fit_local_cache_restores_raw_kind_and_signed_zero_before_capture(self):
        fit = SimpleNamespace(character=SimpleNamespace(secStatus=4), pilotSecurity=5)
        with self.assertRaises(ProfileError): security.restore(fit)
        for pilot, character in ((0, -0.0), (-0.0, 5.0), (None, -6.25)):
            security.install(fit, pilot, character)
            fit.pilotSecurity = 0.0; fit.character.secStatus = 0.0
            security.restore(fit)
            self.assertTrue(exact(fit.pilotSecurity, pilot))
            self.assertTrue(exact(fit.character.secStatus, character))
            self.assertTrue(exact(security.capture(fit), {'character_security': character}))
            security.check_live({'spec': {'security': {'pilot': pilot}}, 'character_security': character}, fit)
            with self.assertRaises(ProfileError):
                security.check_live({'spec': {'security': {'pilot': pilot}}, 'character_security': 2.75}, fit)


if __name__ == '__main__': unittest.main()
