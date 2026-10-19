"""Original fighter Recent-use side effects through the durable native facade."""
import json
import unittest
from copy import deepcopy
from unittest.mock import patch
from test_fighter_session import FighterTests
from android_bridge.offline.profile_store import StoreWriteRejected


class FighterRecentTests(FighterTests):
    def recent(self):return self.session.recent_items()['item_ids']
    def ident(self,name):return self.engine._item(name).ID

    def test_successful_add_deduplicates_and_promotes(self):
        self.add('Firbolg I'); self.add('Satyr I'); self.add('Firbolg I')
        expected=[self.ident('Firbolg I'),self.ident('Satyr I')]
        self.assertEqual(self.recent()[:2],expected)
        self.assertEqual(self.recent().count(expected[0]),1)
        self.reopen();self.assertEqual(self.recent()[:2],expected)

    def test_remove_descending_order_and_undo_redo_side_effect(self):
        self.add('Firbolg I');self.add('Satyr I');self.add('Dromi I')
        ids=[self.ident(n) for n in ('Firbolg I','Satyr I','Dromi I')]
        self.edit('remove_fighters',dict(fit_id=self.key,positions=[0,2]))
        self.assertEqual(self.recent()[:3],[ids[0],ids[2],ids[1]])
        self.edit('undo',dict(fit_id=self.key))
        self.assertEqual(self.recent()[:3],[ids[0],ids[2],ids[1]])
        # Another fit can promote a type before this fit redoes its removal.
        other=next(k for k,v in self.session._records.items() if v['spec']['ship']=='Rifter')
        response=json.loads(self.session.dispatch(json.dumps(self.request('add_fighter',dict(fit_id=other,item_id=ids[1])))))
        self.assertEqual(response['status'],'error');self.assertEqual(self.recent()[0],ids[1])
        self.edit('redo',dict(fit_id=self.key))
        self.assertEqual(self.recent()[:3],[ids[0],ids[2],ids[1]])
        self.reopen();self.assertEqual(self.recent()[:3],[ids[0],ids[2],ids[1]])

    def test_quantity_zero_variation_and_state_do_not_promote(self):
        self.add('Firbolg I');self.add('Satyr I');before=list(self.recent())
        self.edit('toggle_fighters',dict(fit_id=self.key,main_position=0,positions=[]))
        effect=self.rows()[0]['abilities'][0]['effect_id']
        self.edit('toggle_fighter_ability',dict(fit_id=self.key,main_position=0,positions=[],effect_id=effect))
        self.edit('change_fighter_variations',dict(fit_id=self.key,main_position=0,positions=[],item_id=self.ident('Firbolg II')))
        self.assertEqual(self.recent(),before)
        self.edit('set_fighter_amount',dict(fit_id=self.key,position=0,amount=0))
        self.assertEqual(self.recent(),before)
        self.edit('undo',dict(fit_id=self.key));self.edit('redo',dict(fit_id=self.key))
        self.assertEqual(self.recent(),before)

    def test_rejected_valid_attempt_only_changes_metadata_and_survives_restart(self):
        self.key=next(k for k,v in self.session._records.items() if v['spec']['ship']=='Rifter')
        records=deepcopy(self.session._records);revisions=dict(self.session._revisions)
        history=self.session.history_details(self.key);context=self.session.context()
        request=self.request('add_fighter',dict(fit_id=self.key,item_id=self.ident('Firbolg I')))
        result=json.loads(self.session.dispatch(json.dumps(request)))
        self.assertEqual(result['status'],'error')
        self.assertEqual(records,self.session._records);self.assertEqual(revisions,self.session._revisions)
        self.assertEqual(history,self.session.history_details(self.key));self.assertGreater(self.session.context()['generation'],context['generation'])
        self.assertEqual(self.recent(),[self.ident('Firbolg I')])
        self.reopen();self.assertEqual(records,self.session._records);self.assertEqual(self.recent(),[self.ident('Firbolg I')])

    def test_success_and_rejected_attempt_save_failure_rolls_back_all_state(self):
        self.add('Satyr I')
        with patch.object(self.session._store,'write',side_effect=StoreWriteRejected('synthetic')):
            self.rejected('add_fighter',dict(fit_id=self.key,item_id=self.ident('Firbolg I')))
            self.rejected('remove_fighters',dict(fit_id=self.key,positions=[0]))
            self.key=next(k for k,v in self.session._records.items() if v['spec']['ship']=='Rifter')
            self.rejected('add_fighter',dict(fit_id=self.key,item_id=self.ident('Firbolg I')))

    def test_invalid_or_stale_request_does_not_promote(self):
        for item_id in (True,0,-1,2**31,'123',self.ident('Hobgoblin I')):
            self.rejected('add_fighter',dict(fit_id=self.key,item_id=item_id))
        request=self.request('add_fighter',dict(fit_id=self.key,item_id=self.ident('Firbolg I')))
        self.edit('rename_fit',dict(fit_id=self.key,name='Changed'))
        before=self.path.read_bytes()
        self.assertEqual(json.loads(self.session.dispatch(json.dumps(request)))['status'],'error')
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.recent(),[])


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(FighterRecentTests(name) for name in FighterRecentTests.__dict__ if name.startswith('test_'))
