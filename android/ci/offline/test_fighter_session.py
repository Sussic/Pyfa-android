"""C05 durable fighter editing through the current integrated graph facade."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from test_native_session import NativeSessionTests,spec
from android_bridge.offline.profile_store import StoreWriteRejected
from android_bridge.fighter_records import validate
class FighterTests(NativeSessionTests):
    def setUp(self):
        super().setUp()
        result=self.edit('create_fit',dict(spec=dict(spec(),ship='Thanatos',name='Synthetic carrier')))
        self.key=result['fits'][0]['fit_id'] if 'fit_id' in result['fits'][0] else result['fits'][0]['id']
    def add(self,name='Firbolg I'):
        self.edit('add_fighter',dict(fit_id=self.key,item_id=self.engine._item(name).ID))
    def details(self):return self.session.fighter_details(self.key)
    def rows(self):return self.details()['squadrons']
    def rejected(self,op,args):
        before=self.path.read_bytes();state=self.session.graph.snapshot();hist=self.session.history_details(self.key)
        value=json.loads(self.session.dispatch(json.dumps(self.request(op,args))))
        self.assertEqual(value['status'],'error',value);self.assertEqual(before,self.path.read_bytes());self.assertEqual(state,self.session.graph.snapshot());self.assertEqual(hist,self.session.history_details(self.key))
        return value
    def test_add_independent_squadrons_auto_state_and_explicit_overrun(self):
        for _ in range(4):self.add()
        rows=self.rows();self.assertEqual(len(rows),4);self.assertEqual(len({r['object_key'] for r in rows}),4)
        capacity=self.details()['tubes_total'];category=next(c['total'] for c in self.details()['categories'] if c['slot']==rows[0]['slot']);self.assertEqual(sum(r['active'] for r in rows),min(capacity,category,4))
        inactive=next(i for i,r in enumerate(rows) if not r['active'])
        self.edit('toggle_fighters',dict(fit_id=self.key,main_position=inactive,positions=list(range(4))))
        self.assertTrue(all(r['active'] for r in self.rows()));self.assertEqual(self.details()['tubes_used'],4)
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows(),rows)
    def test_abilities_persist_undo_redo_and_restart(self):
        self.add();row=self.rows()[0];effect=next(a['effect_id'] for a in row['abilities'] if a['active'])
        self.edit('toggle_fighter_ability',dict(fit_id=self.key,main_position=0,positions=[],effect_id=effect))
        changed=deepcopy(self.session._records[self.key]['spec']['fighters']);self.assertIn('abilities',changed[0])
        self.assertFalse(next(a['active'] for a in changed[0]['abilities'] if a['effect_id']==effect))
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows()[0]['abilities'],row['abilities'])
        self.edit('redo',dict(fit_id=self.key));self.assertEqual(self.session._records[self.key]['spec']['fighters'],changed)
        self.reopen();self.assertEqual(self.session._records[self.key]['spec']['fighters'],changed)
        self.assertEqual(self.session.history_details(self.key)['undo_count'],0)
    def test_bulk_ability_missing_effect_skips_and_history_is_one_action(self):
        self.add();self.add('Satyr I');self.add('Dromi I')
        rows=self.rows();effect=next(a['effect_id'] for a in rows[0]['abilities'] if a['active']);before={r['index']:{a['effect_id']:a['active'] for a in r['abilities']} for r in rows}
        old=self.session.history_details(self.key)['undo_count']
        self.edit('toggle_fighter_ability',dict(fit_id=self.key,main_position=0,positions=[1,2],effect_id=effect))
        self.assertEqual(self.session.history_details(self.key)['undo_count'],old+1)
        for r in self.rows():
            states={a['effect_id']:a['active'] for a in r['abilities']}
            for e,value in states.items():self.assertEqual(value,not before[0][effect] if e==effect else before[r['index']][e])
    def test_quantity_caps_zero_removes_and_undo_restores_identity(self):
        self.add();old=self.rows()[0]
        self.edit('set_fighter_amount',dict(fit_id=self.key,position=0,amount=2**31-1));self.assertEqual(self.rows()[0]['amount'],old['max_size'])
        self.edit('set_fighter_amount',dict(fit_id=self.key,position=0,amount=1));self.assertEqual(self.rows()[0]['amount'],1)
        self.edit('set_fighter_amount',dict(fit_id=self.key,position=0,amount=0));self.assertFalse(self.rows())
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows()[0]['object_key'],old['object_key']);self.assertEqual(self.rows()[0]['amount'],1)
    def test_variation_reorders_matching_rows_and_preserves_states(self):
        self.add();self.add('Templar I');self.add()
        effect=self.rows()[0]['abilities'][0]['effect_id'];self.edit('toggle_fighter_ability',dict(fit_id=self.key,main_position=0,positions=[2],effect_id=effect))
        before=self.rows();self.edit('change_fighter_variations',dict(fit_id=self.key,main_position=0,positions=[1,2],item_id=self.engine._item('Firbolg II').ID))
        rows=self.rows();self.assertEqual([r['name'] for r in rows],['Templar I','Firbolg II','Firbolg II'])
        self.assertEqual(rows[0]['object_key'],before[1]['object_key'])
        for r in rows[1:]:self.assertEqual({a['effect_id']:a['active'] for a in r['abilities']},{a['effect_id']:a['active'] for a in before[0]['abilities']})
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows(),before)
    def test_failed_durable_write_rolls_back_ability_history_and_records(self):
        self.add();effect=self.rows()[0]['abilities'][0]['effect_id']
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('injected')):
            self.rejected('toggle_fighter_ability',dict(fit_id=self.key,main_position=0,positions=[],effect_id=effect))
        self.edit('toggle_fighters',dict(fit_id=self.key,main_position=0,positions=[]))
    def test_invalid_and_stale_requests_are_atomic(self):
        self.add()
        for op,args in [('remove_fighters',dict(fit_id=self.key,positions=[0,0])),('set_fighter_amount',dict(fit_id=self.key,position=0,amount=True)),('toggle_fighter_ability',dict(fit_id=self.key,main_position=0,positions=[],effect_id=1)),('change_fighter_variations',dict(fit_id=self.key,main_position=0,positions=[],item_id=self.engine._item('Templar I').ID))]:self.rejected(op,args)
        request=self.request('toggle_fighters',dict(fit_id=self.key,main_position=0,positions=[]));self.edit('rename_fit',dict(fit_id=self.key,name='New carrier'))
        before=self.path.read_bytes();self.assertEqual(json.loads(self.session.dispatch(json.dumps(request)))['status'],'error');self.assertEqual(before,self.path.read_bytes())
    def test_legacy_record_absence_survives_unrelated_replay(self):
        self.add();old=self.session._records[self.key]['spec']['fighters'];self.assertNotIn('abilities',old[0])
        self.edit('rename_fit',dict(fit_id=self.key,name='Renamed'));self.reopen();self.assertEqual(self.session._records[self.key]['spec']['fighters'],old)
    def test_hull_and_item_restrictions(self):
        original=self.key;self.key=next(k for k in self.session._fits if k!=original)
        before=deepcopy(self.session._records);revisions=dict(self.session._revisions)
        history=self.session.history_details(self.key);generation=self.session.context()['generation']
        item_id=self.engine._item('Firbolg I').ID
        result=json.loads(self.session.dispatch(json.dumps(self.request('add_fighter',dict(fit_id=self.key,item_id=item_id)))))
        self.assertEqual(result['status'],'error');self.assertEqual(before,self.session._records)
        self.assertEqual(revisions,self.session._revisions);self.assertEqual(history,self.session.history_details(self.key))
        self.assertEqual(self.session.recent_items()['item_ids'][0],item_id)
        self.assertGreater(self.session.context()['generation'],generation)
        self.key=original
        self.rejected('add_fighter',dict(fit_id=self.key,item_id=self.engine._item('Hobgoblin I').ID))
    def test_profile_copy_and_linked_publication_preserve_abilities(self):
        self.add();effect=self.rows()[0]['abilities'][0]['effect_id']
        self.edit('toggle_fighter_ability',dict(fit_id=self.key,main_position=0,positions=[],effect_id=effect))
        expected=deepcopy(self.session._records[self.key]['spec']['fighters'])
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'))
        self.assertEqual(expected,self.session._records[self.key]['spec']['fighters'])
        previous=set(self.session._fits)
        self.edit('duplicate_fit',dict(fit_id=self.key,name='Copied carrier'))
        copied=next(k for k in self.session._fits if k not in previous)
        self.assertEqual(expected,self.session._records[copied]['spec']['fighters'])
        self.assertNotEqual(self.rows()[0]['object_key'],self.session.fighter_details(copied)['squadrons'][0]['object_key'])
        other=next(k for k,v in self.session._records.items() if v['spec']['ship']=='Rifter')
        self.edit('add_projection',dict(source_id=self.key,target_id=other,range_m=0.0,active=True,amount=1))
        rev=self.session._revisions[other]
        self.edit('toggle_fighters',dict(fit_id=self.key,main_position=0,positions=[]))
        self.assertGreater(self.session._revisions[other],rev)
    def test_incomplete_or_unknown_ability_record_is_rejected_atomically(self):
        row=dict(name='Firbolg I',amount=1,active=True,abilities=[])
        for abilities in ([],[dict(effect_id=1,active=True)]):
            row['abilities']=abilities
            self.rejected('create_fit',dict(spec=dict(spec(),ship='Thanatos',fighters=[row])))
    def test_record_validation(self):
        base=dict(name='Firbolg I',amount=1,active=True)
        for abilities in ([dict(effect_id=1,active=True)]*2,[dict(effect_id=True,active=False)],[dict(effect_id=1,active=1)]):
            with self.assertRaises(ValueError):validate(dict(base,abilities=abilities))
def load_tests(loader,tests,pattern):
    return unittest.TestSuite(FighterTests(name) for name in FighterTests.__dict__ if name.startswith('test_'))
