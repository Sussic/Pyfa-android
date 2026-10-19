"""C07.3 actual admission/commit ordering with finite count-only metadata.

The merge and admission are production functions at unchanged production caps.
EOS replay and full graph metadata validation are deliberately replaced here;
real-EOS replay counts and numerical parity have separate integration witnesses.
"""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from android_bridge import character_implants
from android_bridge import projected_drone_budget as budget
from android_bridge.projected_drone_admission import AdmissionRejected
from android_bridge.offline import implant_sets as sets
from android_bridge.offline.profile_graph import ProfileGraph, MemoryStore
from test_character_implant_resources import Fixture, record
from test_implant_sets import fake_item, INFO


class ImplantSetResourceTests(Fixture):
    def test_actual_merge_crosses_unchanged_request_cap_before_any_live_stage(self):
        row=record(incoming=True)
        row['spec']['projected_drones'][0].update(amount=2047,active=2047)
        # Cargo rows are counted, not interpreted, by this metadata budget.
        # 189 rows place the one-implant old side at roots=1024.
        row['spec']['cargo']=[None]*189
        row['implants']=[dict(name='One',slot=6,active=False)]
        row['inspection_ids']=dict(implants=['1'*32])
        row['implant_source']='CHARACTER'
        graph=dict(records={'fit':row},revisions={'fit':1},modified={'fit':1},
                   fit_order=['fit'],recent=[],sample_id='fit')
        state=dict(kind='pyfa.profile-fit-graph',version=7,fit_graph=graph,
                   profiles=dict(profiles={},bindings={}),implant_sets=sets.empty())
        owner=ProfileGraph.__new__(ProfileGraph)
        owner._available=True;owner.migration_pending=False
        owner.engine=SimpleNamespace(_check_thread=lambda:None,resolved_item_ids={})
        owner._state=deepcopy(state);owner._store=MemoryStore(state);owner._snapshots={}
        owner._bridge=SimpleNamespace(_records=deepcopy(graph['records']),_revisions={'fit':1},_provenance={})
        owner._validate=lambda candidate,**kwargs:None
        initial=budget.admit(graph['records'])
        self.assertEqual((budget.MAX_COLD_UNITS,budget.MAX_REQUEST_UNITS,budget.REQUEST_PHASES),
                         (16384,134217728,8))
        self.assertEqual((initial['cold_units'],initial['root_calls_per_phase'],initial['request_units']),
                         (16382,1024,134201344))
        before=deepcopy(owner._state);durable=owner._store.current;candidate=deepcopy(before)
        lookup=lambda name:next(key for key,value in INFO.items() if value[0]==name)
        with patch.object(character_implants,'catalogue',side_effect=fake_item):
            sets.merge_fit(candidate['fit_graph']['records']['fit'],[1,79],lookup)
            self.assertEqual(len(candidate['fit_graph']['records']['fit']['implants']),2)
            self.assertEqual(candidate['fit_graph']['records']['fit']['implants'][0],row['implants'][0])
            with patch.object(owner,'_restore',side_effect=AssertionError('No live stage on refusal')) as restore:
                with self.assertRaisesRegex(AdmissionRejected,'complete-request'):
                    owner._commit(candidate,{'fit'})
                self.assertEqual(restore.call_count,0)
            self.assertEqual(owner._state,before);self.assertEqual(owner._store.current,durable)
            self.assertEqual(owner._bridge._records,graph['records']);self.assertTrue(owner._available)
            # Replacing the occupied slot instead stays at the exact admitted
            # bound and reaches one candidate stage, without a recovery stage.
            candidate=deepcopy(before);sets.merge_fit(candidate['fit_graph']['records']['fit'],[2],lookup)
            admitted=budget.admit_transition(graph['records'],candidate['fit_graph']['records'])
            self.assertEqual(admitted['request_units'],134201344)
            with patch.object(owner,'_restore',return_value={}) as restore:
                result=owner._commit(candidate,{'fit'});self.assertEqual(restore.call_count,1)
            self.assertTrue(result['committed']);self.assertEqual(owner._store.current.generation,durable.generation+1)
            self.assertEqual(owner._state['fit_graph']['records']['fit']['implant_source'],'CHARACTER')


if __name__=='__main__':unittest.main()
