"""D04.1 structure security persistence and EOS targeting effects."""
import json
from copy import deepcopy
from unittest.mock import patch
from test_native_session import NativeSessionTests, spec
from android_bridge.offline.profile_store import StoreWriteRejected


def structure_spec():
    value = spec()
    value.update(ship='Fortizar', name='Synthetic Fortizar', modules=[dict(
        name='Standup L-Set Target Acquisition Array I', charge=None, state='ONLINE')])
    return value


class SystemSecurityTests(NativeSessionTests):
    def structure(self):
        self.key = self.edit('create_fit', dict(spec=structure_spec()))['fits'][0]['id']

    def choose(self, value):
        return self.edit('set_system_security', dict(fit_id=self.key, system=value))

    def reject(self, value):
        before = self.path.read_bytes()
        state = self.session.graph.snapshot()
        history = self.session.history_details(self.key)
        result = json.loads(self.session.dispatch(json.dumps(self.request(
            'set_system_security', dict(fit_id=self.key, system=value)))))
        self.assertEqual(result['status'], 'error', result)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.session.graph.snapshot(), state)
        self.assertEqual(self.session.history_details(self.key), history)

    def test_ship_unavailable_and_query_read_only(self):
        before = self.path.read_bytes()
        data = self.session.system_security_details(self.key)
        self.assertFalse(data['is_structure'])
        self.assertEqual(data['choices'], [])
        self.assertEqual(self.path.read_bytes(), before)
        self.reject('LOWSEC')

    def test_four_choices_eos_effect_and_history_restart(self):
        self.structure()
        data = self.session.system_security_details(self.key)
        self.assertEqual(data['choices'], [dict(id=k, label=v) for k,v in (
            ('HISEC','High Security'),('LOWSEC','Low Security'),
            ('NULLSEC','Null Security'),('WSPACE','W-Space'))])
        for value in ('LOWSEC', 'NULLSEC', 'WSPACE', 'HISEC'):
            self.choose(value)
            main = self.session.targeting_details(self.key)['targeting']['main']
            self.assertAlmostEqual(main['range']['value'], 418000 if value=='HISEC' else 425600)
            self.assertEqual(main['scan_resolution']['value'], 90 if value=='HISEC' else 100)
            self.assertEqual(self.session._records[self.key]['spec']['security']['system'], value)
        self.edit('undo',dict(fit_id=self.key))
        self.assertEqual(self.session.system_security_details(self.key)['system'],'WSPACE')
        self.edit('redo',dict(fit_id=self.key))
        self.reopen()
        self.assertEqual(self.session.system_security_details(self.key)['system'],'HISEC')
        self.assertAlmostEqual(self.session.targeting_details(self.key)['targeting']['main']['range']['value'],418000)

    def test_same_choice_has_no_semantic_history_entry(self):
        self.structure()
        record = deepcopy(self.session._records[self.key])
        history = self.session.history_details(self.key)
        self.choose('HISEC')
        self.assertEqual(self.session._records[self.key],record)
        result = self.session.history_details(self.key)
        self.assertEqual(result['undo_count'],history['undo_count'])
        self.assertEqual(result['redo_count'],history['redo_count'])
        self.assertGreater(result['revision'],history['revision'])

    def test_invalid_stale_and_commit_failure_are_atomic(self):
        self.structure()
        for value in ('highsec','',None,True,0,[],{}):
            self.reject(value)
        request = self.request('set_system_security',dict(fit_id=self.key,system='WSPACE'))
        self.choose('LOWSEC')
        before = self.path.read_bytes()
        self.assertEqual(json.loads(self.session.dispatch(json.dumps(request)))['status'],'error')
        self.assertEqual(self.path.read_bytes(),before)
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('synthetic')):
            self.reject('WSPACE')
        self.assertEqual(self.session.system_security_details(self.key)['system'],'LOWSEC')

    def test_copy_profiles_links_and_restart_preserve_security(self):
        self.structure(); self.choose('WSPACE')
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'))
        copied = self.edit('duplicate_fit',dict(fit_id=self.key,name='Structure copy'))
        other = next(x['id'] for x in copied['fits'] if x['name']=='Structure copy')
        for operation in ('add_projection','remove_projection','add_command','remove_command'):
            args = dict(source_id=self.key,target_id=other)
            if operation=='add_projection': args.update(range_m=0.0,active=True,amount=1)
            if operation=='add_command': args.update(active=True)
            self.edit(operation,args)
            self.assertEqual(self.session.system_security_details(self.key)['system'],'WSPACE')
            self.assertEqual(self.session.system_security_details(other)['system'],'WSPACE')
        self.reopen()
        for key in (self.key,other):
            self.assertEqual(self.session.system_security_details(key)['system'],'WSPACE')
            self.assertEqual(self.session._records[key]['spec']['security']['pilot'],0.0)

    def test_nullable_source_default_query_and_fail_closed_capture(self):
        from android_bridge.system_security import details,live_name
        self.structure()
        fit = self.session._fits[self.key]
        previous=fit.systemSecurity
        try:
            fit.systemSecurity=None
            self.assertEqual(details(self.engine,fit)['system'],'NULLSEC')
            with self.assertRaises(ValueError):
                self.session.graph._bridge._capture(self.session._fits,
                    {k:v['spec'] for k,v in self.session._records.items()})
            for invalid in (None,True,False,99,0.0,"HISEC"):
                with self.assertRaises(ValueError):live_name(invalid)
        finally:
            fit.systemSecurity=previous


def load_tests(loader, tests, pattern):
    import unittest
    return unittest.TestSuite(SystemSecurityTests(name) for name in SystemSecurityTests.__dict__
                              if name.startswith('test_'))
