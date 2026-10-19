"""Actual target wire/GraphHistory/commit hooks with pure deterministic replay.

This deliberately does not claim EOS calculation, SQL or native acceptance.
Only the existing EOS restoration boundary is replaced; candidate preparation,
monotonic floors, history, complete wire, recovery and commit protocol are real.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from android_bridge.contract import _json
from android_bridge.history import EditHistory
from android_bridge.offline.native_session import IntegratedGraph, NativeSession
from android_bridge.offline.profile_graph import MemoryStore
from android_bridge.offline.profile_store import StoreUncertain
from android_bridge.offline.graph_history import GraphHistory
from android_bridge.offline import target_profiles as target
from android_bridge.offline import damage_patterns as damage
from test_target_profiles import F,G,CONTEXT,raw,state,wire


class Store(MemoryStore):
    def __init__(self,state):
        super().__init__(state);self.path=Path('pure-memory-only');self.writes=0
    def _read(self):return self._durable
    def write(self,attempt):self.writes+=1;super().write(attempt)


class ReplayGraph(IntegratedGraph):
    def __init__(self,initial):
        self.engine=SimpleNamespace(_check_thread=lambda:None)
        self.dataset=CONTEXT['dataset_sha256']
        self._store=Store(initial);self._available=True;self._revision_floor={}
        self._bridge=SimpleNamespace(session_id=CONTEXT['session_id'],_available=True,_history=EditHistory(),engine=self.engine)
        self._bridge.bootstrap=lambda:_json(dict(version=1,status='ok',session_id=self._bridge.session_id,fits=list(self._bridge._snapshots.values())))
        self._state=deepcopy(initial);self.migration_pending=initial['version']!=9
        self._snapshots=self._restore(initial['fit_graph'])
    def _validate(self,candidate,*,prospective=False):
        self.assertion(candidate['version']==9 and set(candidate)=={'kind','version','fit_graph','profiles','imports','targets','damage_patterns','implant_sets'})
        target.validate(candidate['targets'],candidate['fit_graph']['records'])
        damage.validate(candidate['damage_patterns'],candidate['fit_graph']['records'])
        for revision in candidate['fit_graph']['revisions'].values():target.integer(revision,1)
    @staticmethod
    def assertion(condition):
        if not condition:raise AssertionError('Invalid test graph envelope')
    def _restore(self,graph,*,damage_ledger=None):
        self._bridge._records=deepcopy(graph['records']);self._bridge._revisions=deepcopy(graph['revisions'])
        self._bridge._fits={key:object() for key in graph['records']}
        snapshots={key:dict(id=key,revision=graph['revisions'][key],name=row['spec']['name'],target_profile=deepcopy(row['spec']['target_profile'])) for key,row in graph['records'].items()}
        self._bridge._snapshots=snapshots
        return snapshots
    def _apply_profiles(self,candidate):
        for row in candidate['fit_graph']['records'].values():
            row.setdefault('skills',{});row['spec'].setdefault('skill_level',5)
        target.apply(candidate)


def session(initial=None):
    value=NativeSession.__new__(NativeSession);value.graph=ReplayGraph(state() if initial is None else initial)
    value.history=GraphHistory();value._profile_floor={};value._binding_floor={}
    value._target_profile_floor={};value._target_binding_floor={}
    value._damage_pattern_floor={};value._damage_binding_floor={};value._implant_set_floor={};value._remember_versions()
    return value


class TargetSessionTests(unittest.TestCase):
    def setUp(self):self.session=session()
    def request(self,op='read',args=None,fit=F,selected=None,**view):
        return wire(op,args,context=self.session.context(),fit_id=fit,
            view=wire()['view']|dict(selected_target_id=selected)|view)
    def call(self,op='read',args=None,**kwargs):
        before=self.session._store.current.generation
        response=json.loads(self.session.target_dispatch(_json(self.request(op,args,**kwargs))))
        self.assertTrue(response['ok'],response)
        self.assertEqual(response['state']['context']['generation'],before+int(response['committed']))
        self.assertEqual(set(response),{'version','request_id','ok','committed','reopen_required','state','bridge','error'})
        return response
    def create(self,name='Shared',value=None):
        return self.call('create',dict(name=name,values=raw() if value is None else value),fit=None)['state']['detail']['target_id']
    def revision(self,key):return target.resolve(self.session.graph._state.get('targets',target.empty()),key)['revision']
    def assign(self,key,fit=F):
        return self.call('assign',dict(target_id=key,revision=self.revision(key),fit_revision=self.session._revisions[fit]),fit=fit,selected=key)
    def test_legacy_reads_noop_first_edit_and_empty_library(self):
        store=self.session._store;before=store.current
        value=self.call();self.assertIsNone(value['bridge']);self.assertFalse(value['committed'])
        self.assertEqual(store.current,before);self.assertTrue(self.session.graph.migration_pending)
        value=self.call('clear',dict(fit_revision=1));self.assertFalse(value['committed'])
        self.assertEqual(store.current,before);self.assertEqual(self.session.graph._state['version'],1)
        key=self.create();self.assertEqual(self.session.graph._state['version'],9)
        self.assertEqual(self.session.graph._state['imports'],{});self.assertFalse(self.session.graph.migration_pending)
        initial=state();initial['fit_graph'].update(records={},revisions={},fit_order=[],sample_id=None,format=2,modified={})
        self.session=session(initial);self.create('No fits')
        self.assertEqual(self.call(fit=None)['state']['selection']['kind'],'no_fit')
    def test_shared_update_rename_delete_undo_redo_with_floors(self):
        key=self.create();self.assign(key);self.assign(key,G)
        self.call('update_values',dict(target_id=key,revision=1,values=raw(hp=0.0)),selected=key)
        versions=(self.revision(key),self.session._revisions[F],self.session.graph._state['targets']['bindings'][F]['revision'])
        self.assertEqual(self.session._records[F]['spec']['target_profile']['hp'],0.0)
        self.assertEqual(self.session._records[G]['spec']['target_profile']['hp'],0.0)
        self.call('undo',fit=None,selected=key)
        self.assertGreater(self.revision(key),versions[0]);self.assertGreater(self.session._revisions[F],versions[1])
        self.assertGreater(self.session.graph._state['targets']['bindings'][F]['revision'],versions[2])
        self.assertIsNone(self.session._records[F]['spec']['target_profile']['hp'])
        self.call('redo',fit=None,selected=key)
        self.call('rename',dict(target_id=key,revision=self.revision(key),name='Renamed'),selected=key)
        self.call('delete',dict(target_id=key,revision=self.revision(key),bound_fit_count=2),selected=key)
        self.assertEqual(self.session.graph._state['targets'],target.empty())
        self.assertIsNone(self.session._records[F]['spec']['target_profile'])
        self.call('undo',fit=None)
        self.assertEqual(self.session.graph._state['targets']['profiles'][key]['name'],'Renamed')
        self.assertEqual(len(self.session.graph._state['targets']['bindings']),2)
        self.call('redo',fit=None,selected=key)
        self.assertEqual(self.session.graph._state['targets'],target.empty())
    def test_signedzero_and_integral_floats_survive_wire_history(self):
        key=self.create(value=raw(emAmount=0.0,explosiveAmount=1.0,hp=0.0,maxVelocity=-0.0));self.assign(key)
        self.call('update_values',dict(target_id=key,revision=1,values=raw(emAmount=0.0,explosiveAmount=1.0,hp=-0.0,maxVelocity=-0.0)),selected=key)
        detail=self.call(selected=key)['state']['detail']
        self.assertEqual(math.copysign(1,detail['values']['hp']),-1)
        self.assertIs(type(detail['values']['emAmount']),float);self.assertIs(type(detail['values']['explosiveAmount']),float)
        self.assertIs(type(detail['effective']['maxVelocity']),int)
        self.call('undo',selected=key)
        self.assertEqual(math.copysign(1,self.call(selected=key)['state']['detail']['values']['hp']),1)
        self.call('redo',selected=key)
        self.assertEqual(math.copysign(1,self.call(selected=key)['state']['detail']['values']['hp']),-1)
        initial=json.loads(self.session._store.current.payload);self.session=session(initial)
        self.assertEqual(math.copysign(1,self.call(selected=key)['state']['detail']['values']['hp']),-1)
        self.assertEqual(self.session.history.details(F)['undo_count'],0)
    def test_noops_keep_context_history_and_revision_floors(self):
        key=self.create();self.assign(key)
        before=self.session._store.current;history=self.session.history;floors=deepcopy(self.session.graph._revision_floor)
        self.assertFalse(self.assign(key)['committed'])
        self.assertFalse(self.call('rename',dict(target_id=key,revision=1,name=' Shared '),selected=key)['committed'])
        self.assertFalse(self.call('update_values',dict(target_id=key,revision=1,values=raw()),selected=key)['committed'])
        self.assertEqual(self.session._store.current,before);self.assertIs(self.session.history,history)
        self.assertEqual(self.session.graph._revision_floor,floors)
    def test_stale_missing_malformed_and_oversized_are_certain_no_write(self):
        key=self.create();before=self.session._store.current
        requests=[self.request('assign',dict(target_id=key,revision=0,fit_revision=1)),
                  self.request('assign',dict(target_id=key,revision=1,fit_revision=2)),
                  self.request('delete',dict(target_id=key,revision=1,bound_fit_count=1)),
                  self.request(context='not-a-view-key')]
        requests[-1]['view']['limit']=True
        for request in requests:
            response=json.loads(self.session.target_dispatch(_json(request)))
            self.assertFalse(response['ok']);self.assertFalse(response['committed']);self.assertIsNone(response['state']);self.assertIsNone(response['bridge'])
            self.assertEqual(self.session._store.current,before)
        for text in (' '*16385,'{"version":1,"version":1}','{"x":NaN}'):
            response=json.loads(self.session.target_dispatch(text));self.assertFalse(response['ok']);self.assertFalse(response['committed'])
    def test_precommit_size_and_serialization_failure_preserve_all_authority(self):
        key=self.create();self.assign(key)
        before=self.session._store.current;graph=deepcopy(self.session.graph._state);history=self.session.history
        request=_json(self.request('rename',dict(target_id=key,revision=1,name='Rejected'),selected=key))
        with patch.object(target,'MAX_STATE_BYTES',1):response=json.loads(self.session.target_dispatch(request))
        self.assertEqual(response['error']['code'],'response_size');self.assertFalse(response['committed'])
        self.assertEqual(self.session._store.current,before);self.assertTrue(target.exact(graph,self.session.graph._state));self.assertIs(self.session.history,history)
        with patch.object(self.session.graph._bridge,'bootstrap',side_effect=RuntimeError('secret raw exception')):
            response=json.loads(self.session.target_dispatch(request))
        self.assertFalse(response['committed']);self.assertNotIn('secret',response['error']['message'])
        self.assertEqual(self.session._store.current,before);self.assertIs(self.session.history,history)
    def test_failed_write_and_ambiguous_commit_have_distinct_ownership(self):
        key=self.create();before=self.session._store.current;history=self.session.history
        request=_json(self.request('rename',dict(target_id=key,revision=1,name='New'),selected=key))
        with patch.object(self.session._store,'write',side_effect=OSError('not written')):
            response=json.loads(self.session.target_dispatch(request))
        self.assertFalse(response['committed']);self.assertFalse(response['reopen_required']);self.assertEqual(self.session._store.current,before);self.assertIs(self.session.history,history)
        self.call(selected=key)
        with patch.object(self.session._store,'confirm',side_effect=RuntimeError('unknown')):
            response=json.loads(self.session.target_dispatch(request))
        self.assertIsNone(response['committed']);self.assertTrue(response['reopen_required']);self.assertFalse(self.session._available)
    def test_postcommit_history_publication_and_external_store_change_disable(self):
        request=_json(self.request('create',dict(name='Committed',values=raw())))
        before=self.session._store.current
        with patch.object(self.session,'_remember_versions',side_effect=RuntimeError('publication')):
            response=json.loads(self.session.target_dispatch(request))
        self.assertIsNone(response['committed']);self.assertTrue(response['reopen_required']);self.assertNotEqual(self.session._store.current,before)
        self.session=session();self.session._store._durable=self.session._store.current._replace(generation=2)
        response=json.loads(self.session.target_dispatch(_json(wire())))
        self.assertIsNone(response['committed']);self.assertTrue(response['reopen_required']);self.assertFalse(self.session._available)
    def test_builtin_server_copy_and_binding_revision_floor_after_clear(self):
        key=target.builtin_id(-149);self.assign(key)
        row=self.call(selected=key)['state']['detail'];self.assertIs(type(row['values']['explosiveAmount']),int)
        old=self.session.graph._state['targets']['bindings'][F]['revision']
        self.call('clear',dict(fit_revision=self.session._revisions[F]));self.assign(key)
        self.assertGreater(self.session.graph._state['targets']['bindings'][F]['revision'],old)
        copy=self.call('duplicate',dict(target_id=key,revision=0,name='Copied'),selected=key)['state']['detail']
        self.assertTrue(target.exact(copy['values'],row['values']))
    def test_dependency_closure_and_later_assignment_block_reversal(self):
        # Existing projection records carry target_id (recipient) to source_id (source).
        self.session.graph._state['fit_graph']['records'][G]['projections']=[dict(source_id=F)]
        self.session.graph._bridge._records=deepcopy(self.session.graph._state['fit_graph']['records'])
        key=self.create();self.assign(key)
        before=self.session._revisions[G]
        self.call('rename',dict(target_id=key,revision=1,name='New'),selected=key)
        self.assertGreater(self.session._revisions[G],before)
        self.assertIn(G,self.session.history.rows[F][0][-1].participants)
        # A later named-bound fit introduced outside the timeline must prevent
        # reversing a shared target definition out from underneath that fit.
        other='e'*32;s=self.session.graph._state
        s['fit_graph']['records'][other]=deepcopy(s['fit_graph']['records'][F]);s['fit_graph']['fit_order'].append(other)
        s['fit_graph']['revisions'][other]=1;s['targets']['bindings'][other]=dict(target_id=key,revision=1)
        self.session.graph._bridge._fits[other]=object();self.session._remember_versions()
        with self.assertRaisesRegex(ProfileError,'later target assignments'):
            self.session._replay('library',False)


from android_bridge.offline.profiles import ProfileError
if __name__=='__main__':unittest.main()
