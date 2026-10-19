"""Saved command-fit UI policy through atomic NativeSession persistence."""
import json
import os
from pathlib import Path
from copy import deepcopy
import unittest
from unittest.mock import patch
from test_native_session import NativeSessionTests, spec
from android_bridge.offline.profile_store import StoreWriteRejected


class CommandFitTests(NativeSessionTests):
    def create(self, name, ship='Vexor', modules=()):
        return self.edit('create_fit',dict(spec=dict(spec(),name=name,ship=ship,modules=list(modules))))['fits'][0]['id']
    def source(self):
        value=dict(spec(),**json.loads((Path(os.environ['PYFA_REFERENCE_SOURCE'])/'tools/android_reference/command.json').read_text())['source'])
        return self.edit('create_fit',dict(spec=value))['fits'][0]['id']
    def endpoints(self,source,target=None,**values):return dict(source_id=source,target_id=target or self.key,**values)
    def links(self,target=None):return self.session._records[target or self.key]['commands']
    def shield(self,key=None):return self.session.defense_details(key or self.key)['defenses']['layers']['shield']['hp']['value']
    def reject(self,op,args,request=None):
        before=(self.path.read_bytes(),deepcopy(self.session.graph.snapshot()),deepcopy(self.session._records))
        result=json.loads(self.session.dispatch(json.dumps(request or self.request(op,args))))
        self.assertEqual(result['status'],'error',result)
        self.assertEqual((self.path.read_bytes(),self.session.graph.snapshot(),self.session._records),before)
        return result

    def test_real_burst_duplicate_noop_active_remove_history_restart(self):
        source=self.source();base=self.shield()
        self.edit('add_command_fit',self.endpoints(source));boost=self.shield();self.assertGreater(boost,base)
        self.assertEqual(self.links(),[dict(source_id=source,active=True)])
        history=self.session.history_details(self.key)['undo_count'];records=deepcopy(self.session._records)
        self.edit('add_command_fit',self.endpoints(source));self.assertEqual(self.session._records,records)
        self.assertEqual(self.session.history_details(self.key)['undo_count'],history)
        self.edit('set_command_fit_active',self.endpoints(source,active=False));self.assertEqual(self.shield(),base)
        self.edit('add_command_fit',self.endpoints(source));self.assertFalse(self.links()[0]['active'])
        self.edit('set_command_fit_active',self.endpoints(source,active=True));self.assertEqual(self.shield(),boost)
        self.edit('remove_command_fit',self.endpoints(source));self.assertFalse(self.links());self.assertEqual(self.shield(),base)
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.links(),[dict(source_id=source,active=True)])
        self.assertEqual(self.shield(),boost);self.edit('redo',dict(fit_id=self.key));self.assertFalse(self.links())
        self.edit('undo',dict(fit_id=self.key));records=deepcopy(self.session._records)
        self.reopen();self.assertEqual(self.session._records,records);self.assertEqual(self.shield(),boost)

    def test_source_module_charge_edits_publish_two_recipients(self):
        source=self.source();other=self.create('Second recipient');keys=[self.key,other]
        base=[self.shield(k) for k in keys]
        for key in keys:self.edit('add_command_fit',self.endpoints(source,key))
        boost=[self.shield(k) for k in keys];self.assertTrue(all(a>b for a,b in zip(boost,base)))
        position=next(i for i,m in enumerate(self.session._fits[source].modules) if not m.isEmpty and m.item.name=='Shield Command Burst II')
        result=self.edit('set_module_states',dict(fit_id=source,module_indices=[position],state='OFFLINE'))
        self.assertEqual({r['id'] for r in result['fits']},{source,*keys});self.assertEqual([self.shield(k) for k in keys],base)
        self.edit('undo',dict(fit_id=source));self.assertEqual([self.shield(k) for k in keys],boost)
        self.edit('set_module_charge',dict(fit_id=source,position=position,charge_id=self.engine._item('Shield Harmonizing Charge').ID))
        self.assertEqual([self.shield(k) for k in keys],base)
        self.edit('undo',dict(fit_id=source));self.assertEqual([self.shield(k) for k in reversed(keys)],list(reversed(boost)))
        records=deepcopy(self.session._records);self.reopen();self.assertEqual(self.session._records,records)
        self.assertEqual([self.shield(k) for k in keys],boost)

    def test_source_profile_and_fit_local_mindlink_recalculate_recipients(self):
        source=self.source();other=self.create('Profile recipient');keys=[self.key,other]
        for key in keys:self.edit('add_command_fit',self.endpoints(source,key))
        before=[self.shield(k) for k in keys]
        self.edit('fit_implant',dict(fit_id=source,item_id=self.engine._item('Shield Command Mindlink').ID))
        implanted=[self.shield(k) for k in keys];self.assertTrue(all(a>b for a,b in zip(implanted,before)))
        self.edit('toggle_implants',dict(fit_id=source,main_position=0,positions=[]));self.assertEqual([self.shield(k) for k in keys],before)
        self.edit('undo',dict(fit_id=source));self.assertEqual([self.shield(k) for k in keys],implanted)
        target=self.key;self.key=source
        self.feature('create_profile',dict(name='Burst pilot',source='builtin:all5'))
        pid=next(k for k,v in self.session.graph._state['profiles']['profiles'].items() if v['name']=='Burst pilot')
        self.feature('assign_profile',dict(fit_id=source,profile_id=pid))
        row=self.session.graph._state['profiles']['profiles'][pid]
        self.feature('set_profile_skill',dict(profile_id=pid,revision=row['revision'],skill_id=self.engine._item('Shield Command Specialist').ID,level=0))
        self.assertTrue(all(self.shield(k)<old for k,old in zip(keys,implanted)))
        self.edit('undo',dict(fit_id=source));self.assertEqual([self.shield(k) for k in keys],implanted)
        self.key=target;records=deepcopy(self.session._records);profiles=deepcopy(self.session.graph._state['profiles'])
        self.reopen();self.assertEqual(self.session._records,records);self.assertEqual(self.session.graph._state['profiles'],profiles)
        self.assertEqual([self.shield(k) for k in reversed(keys)],list(reversed(implanted)))

    def test_empty_self_reciprocal_links_and_reference_deletion(self):
        source=self.create('No burst');base=self.shield()
        self.edit('add_command_fit',self.endpoints(source));self.assertEqual(self.shield(),base)
        self.edit('add_command_fit',self.endpoints(self.key,self.key));self.assertEqual(self.shield(),base)
        self.edit('add_command_fit',self.endpoints(self.key,source));self.assertEqual(self.shield(),base)
        records=deepcopy(self.session._records);self.reopen();self.assertEqual(self.session._records,records)
        self.reject('delete_fit',dict(fit_id=source,resolve_references=False))
        self.edit('delete_fit',dict(fit_id=source,resolve_references=True));self.assertNotIn(source,self.session._records)
        self.assertEqual(self.links(),[dict(source_id=self.key,active=True)])
        self.reopen();self.assertEqual(self.links(),[dict(source_id=self.key,active=True)])

    def test_strict_endpoint_state_staleness_and_rejected_commit(self):
        source=self.source()
        self.reject('set_command_fit_active',self.endpoints(source,active=True))
        self.reject('remove_command_fit',self.endpoints(source))
        for bad in (0,1,None,'true',[],{}):self.reject('set_command_fit_active',self.endpoints(source,active=bad))
        stale=self.request('add_command_fit',self.endpoints(source));self.edit('rename_fit',dict(fit_id=source,name='Changed'))
        self.reject('add_command_fit',self.endpoints(source),stale)
        request=self.request('add_command_fit',self.endpoints(source));request['expected_revisions'].pop(source)
        self.reject('add_command_fit',self.endpoints(source),request)
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('synthetic')):
            self.reject('add_command_fit',self.endpoints(source))
        self.edit('add_command_fit',self.endpoints(source));self.assertGreater(self.shield(),0)


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(CommandFitTests(name) for name in CommandFitTests.__dict__ if name.startswith('test_'))
