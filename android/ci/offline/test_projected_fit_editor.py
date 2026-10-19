"""Saved-fit projection command policy through durable NativeSession."""
import json
from copy import deepcopy
import unittest
from unittest.mock import patch
from test_native_session import NativeSessionTests, spec
from android_bridge.offline.profile_store import StoreWriteRejected


class ProjectedFitTests(NativeSessionTests):
    def create(self, name, modules=(), ship='Rifter'):
        return self.edit('create_fit',dict(spec=dict(spec(),name=name,ship=ship,modules=list(modules))))['fits'][0]['id']
    def endpoints(self, source, target=None, **kwargs):
        return dict(source_id=source,target_id=target or self.key,**kwargs)
    def links(self, target=None):return self.session._records[target or self.key]['projections']
    def source(self):
        return self.create('Remote sensor', [dict(name='Remote Sensor Booster II',state='ACTIVE',charge='Scan Resolution Script')])
    def scan(self, key=None):
        return self.session._fits[key or self.key].ship.getModifiedItemAttr('scanResolution')

    def test_real_remote_effect_options_count_clamp_and_history(self):
        source=self.source();base=self.scan();history=self.session.history_details(self.key)['undo_count']
        self.edit('add_projected_fit',self.endpoints(source));boosted=self.scan();self.assertGreater(boosted,base)
        self.assertEqual(self.links(),[dict(source_id=source,range_m=None,active=True,amount=1)])
        self.edit('add_projected_fit',self.endpoints(source));self.assertEqual(self.links()[0]['amount'],2)
        self.edit('set_projected_fit_amount',self.endpoints(source,amount=999));self.assertEqual(self.links()[0]['amount'],20)
        count=self.session.history_details(self.key)['undo_count']
        self.edit('add_projected_fit',self.endpoints(source));self.assertEqual(self.session.history_details(self.key)['undo_count'],count)
        self.edit('set_projected_fit_active',self.endpoints(source,active=False));self.assertAlmostEqual(self.scan(),base)
        self.edit('set_projected_fit_range',self.endpoints(source,range_m=0));self.assertEqual(self.links()[0]['range_m'],0.0)
        self.edit('set_projected_fit_range',self.endpoints(source,range_m=None));self.assertIsNone(self.links()[0]['range_m'])
        self.edit('set_projected_fit_amount',self.endpoints(source,amount=0));self.assertFalse(self.links())
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.links()[0]['amount'],20)
        self.edit('redo',dict(fit_id=self.key));self.assertFalse(self.links())
        self.assertGreater(self.session.history_details(self.key)['undo_count'],history)

    def test_scrambler_reconciles_active_mwd_and_exact_undo_redo(self):
        target=self.create('MWD target',[dict(name='5MN Microwarpdrive II',state='ACTIVE',charge=None)])
        source=self.create('Scrambler',[dict(name='Warp Scrambler II',state='ACTIVE',charge=None)])
        before=deepcopy(self.session._records[target]);self.edit('add_projected_fit',self.endpoints(source,target))
        after=deepcopy(self.session._records[target]);self.assertEqual(after['spec']['modules'][0]['state'],'ONLINE')
        self.assertGreater(self.session._fits[target].modules[0].getModifiedItemAttr('activationBlocked'),0)
        self.edit('undo',dict(fit_id=target));self.assertEqual(self.session._records[target],before)
        self.edit('redo',dict(fit_id=target));self.assertEqual(self.session._records[target],after)
        self.reopen();self.assertEqual(self.session._records[target],after)

    def test_unusual_legacy_count_preserved_until_explicit_change(self):
        source=self.source();self.edit('add_projection',self.endpoints(source,range_m=123.0,active=False,amount=42))
        original=deepcopy(self.links())
        self.edit('set_projected_fit_range',self.endpoints(source,range_m=456.0));self.assertEqual(self.links()[0]['amount'],42)
        self.edit('set_projected_fit_active',self.endpoints(source,active=True));self.assertEqual(self.links()[0]['amount'],42)
        self.edit('set_projected_fit_amount',self.endpoints(source,amount=42));self.assertEqual(self.links()[0]['amount'],20)
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.links()[0]['amount'],42)
        self.edit('undo',dict(fit_id=self.key));self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.links(),original)
        self.reopen();self.assertEqual(self.links(),original)

    def test_self_reciprocal_links_delete_and_restart(self):
        source=self.source();self.edit('add_projected_fit',self.endpoints(source,source))
        self.edit('add_projected_fit',self.endpoints(source));self.edit('add_projected_fit',self.endpoints(self.key,source))
        records=deepcopy(self.session._records);self.reopen();self.assertEqual(self.session._records,records)
        rejected=json.loads(self.session.dispatch(json.dumps(self.request('delete_fit',dict(fit_id=source,resolve_references=False)))))
        self.assertEqual(rejected['status'],'error')
        self.edit('delete_fit',dict(fit_id=source,resolve_references=True));self.assertFalse(self.links())
        self.reopen();self.assertNotIn(source,self.session._records);self.assertFalse(self.links())

    def test_invalid_stale_and_rejected_write_preserve_graph(self):
        source=self.source();self.edit('add_projected_fit',self.endpoints(source))
        stale=self.request('set_projected_fit_active',self.endpoints(source,active=False))
        self.edit('rename_fit',dict(fit_id=source,name='Changed source'))
        before=self.path.read_bytes();records=deepcopy(self.session._records);history=self.session.history_details(self.key)
        bad=[stale]
        for op,values in [('set_projected_fit_amount',dict(amount=-1)),('set_projected_fit_amount',dict(amount=True)),
                          ('set_projected_fit_range',dict(range_m=-1)),('set_projected_fit_active',dict(active=1))]:
            bad.append(self.request(op,self.endpoints(source,**values)))
        for request in bad:
            result=json.loads(self.session.dispatch(json.dumps(request)));self.assertEqual(result['status'],'error')
            self.assertEqual(self.path.read_bytes(),before)
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('injected')):
            result=json.loads(self.session.dispatch(json.dumps(self.request('remove_projected_fit',self.endpoints(source)))))
            self.assertEqual(result['status'],'error')
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.session._records,records)
        self.assertEqual(self.session.history_details(self.key),history)

    def test_profile_changes_and_source_edits_update_both_recipients(self):
        source=self.source();other=self.create('Other recipient')
        self.edit('add_projected_fit',self.endpoints(source));self.edit('add_projected_fit',self.endpoints(source,other))
        before=[self.scan(k) for k in (self.key,other)]
        response=self.edit('set_module_states',dict(fit_id=source,module_indices=[0],state='OFFLINE'))
        self.assertEqual({r['id'] for r in response['fits']},{source,self.key,other})
        self.assertTrue(all(self.scan(k)<value for k,value in zip((self.key,other),before)))
        self.edit('undo',dict(fit_id=source));self.assertEqual([self.scan(k) for k in (self.key,other)],before)
        self.feature('assign_profile',dict(fit_id=source,profile_id='builtin:all0'))
        records=deepcopy(self.session._records);self.reopen();self.assertEqual(self.session._records,records)
        self.assertTrue(all(self.session.history_details(k)['undo_count']==0 for k in records))


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(ProjectedFitTests(name) for name in ProjectedFitTests.__dict__ if name.startswith('test_'))
