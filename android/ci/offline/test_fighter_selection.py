"""Read-only original similar-fighter selection and existing bulk-edit integration."""
import unittest
from types import SimpleNamespace as N
from test_fighter_session import FighterTests
from android_bridge.fighter_selection import similar,selection


class FighterSelectionTests(FighterTests):
    def prepare(self):
        for name in ('Firbolg I','Firbolg II','Dromi I'):self.add(name)

    def query(self,position=0):
        return self.session.fighter_similar_selection(self.key,position)

    def test_cross_type_source_membership_and_readonly_identity(self):
        self.prepare();before=self.path.read_bytes();state=self.session.graph.snapshot()
        history=self.session.history_details(self.key);recent=self.session.recent_items()
        result=self.query();self.assertEqual([r['index'] for r in result['matches']],[0,1])
        self.assertEqual(result['main'],result['matches'][0])
        self.assertEqual(result['fit_id'],self.key);self.assertEqual(result['revision'],self.session._revisions[self.key])
        self.assertEqual(self.query(),result)
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.session.graph.snapshot(),state)
        self.assertEqual(self.session.history_details(self.key),history);self.assertEqual(self.session.recent_items(),recent)
        self.assertEqual([r['index'] for r in self.query(2)['matches']],[2])

    def test_activation_quantity_and_ability_state_do_not_change_membership(self):
        self.prepare();expected=self.query()['matches']
        self.edit('toggle_fighters',dict(fit_id=self.key,main_position=1,positions=[]))
        self.edit('set_fighter_amount',dict(fit_id=self.key,position=1,amount=1))
        effect=self.rows()[1]['abilities'][0]['effect_id']
        self.edit('toggle_fighter_ability',dict(fit_id=self.key,main_position=1,positions=[],effect_id=effect))
        self.assertEqual(self.query()['matches'],expected)

    def test_selected_existing_bulk_operation_undo_redo_and_restart(self):
        self.prepare();selected=self.query();before=self.rows()
        self.edit('toggle_fighters',dict(fit_id=self.key,main_position=selected['main']['index'],positions=[r['index'] for r in selected['matches']]))
        after=self.rows();self.assertTrue(all(not after[i]['active'] for i in (0,1)))
        self.assertEqual(after[2],before[2])
        self.edit('undo',dict(fit_id=self.key));self.assertEqual(self.rows(),before)
        self.edit('redo',dict(fit_id=self.key));self.reopen();self.assertEqual(self.rows(),after)
        self.assertEqual(self.query()['matches'],selected['matches'])

    def test_invalid_positions_preserve_all_saved_state(self):
        self.prepare();before=self.path.read_bytes();state=self.session.graph.snapshot();history=self.session.history_details(self.key)
        for value in (-1,3,True,None,'0',0.0,[],{}):
            with self.assertRaises(ValueError):self.query(value)
        self.assertEqual(self.path.read_bytes(),before);self.assertEqual(self.session.graph.snapshot(),state)
        self.assertEqual(self.session.history_details(self.key),history)

    def test_profile_and_link_refresh_keep_match_identities(self):
        self.prepare();matches=self.query()['matches']
        self.feature('assign_profile',dict(fit_id=self.key,profile_id='builtin:all0'))
        other=next(k for k,v in self.session._records.items() if v['spec']['ship']=='Rifter')
        self.edit('add_projection',dict(source_id=self.key,target_id=other,range_m=0.0,active=True,amount=1))
        self.assertEqual(self.query()['matches'],matches)
        self.edit('remove_projection',dict(source_id=self.key,target_id=other))
        self.reopen();self.assertEqual(self.query()['matches'],matches)


class PredicateTests(unittest.TestCase):
    def fighter(self,item_id,group,abilities):
        return N(itemID=item_id,item=N(group=None if group is None else N(ID=group)),
                 abilities=[N(effectID=x,effect=N(isImplemented=False),active=False) for x in abilities])

    def test_complete_ability_set_same_item_and_missing_groups(self):
        main=self.fighter(1,10,[7,8]);same=self.fighter(1,None,[])
        matching=self.fighter(2,10,[8,7,7]);hidden_difference=self.fighter(3,10,[7])
        empty=self.fighter(4,10,[]);other=self.fighter(5,11,[7,8]);missing=self.fighter(None,10,[7,8])
        rows=[other,matching,main,same,hidden_difference,empty,missing]
        actual=similar(rows,main)
        self.assertEqual([id(x) for x in actual],[id(matching),id(main),id(same)])
        main.item.group=None;self.assertEqual([id(x) for x in similar(rows,main)],[id(main),id(same)])

    def test_over_limit_refuses_without_truncation(self):
        rows=[self.fighter(1,10,[]) for _ in range(1025)]
        with self.assertRaisesRegex(ValueError,'Select at most 1024'):
            selection(N(_check_fit=lambda fit:None),N(fighters=rows),0)


def load_tests(loader,tests,pattern):
    return unittest.TestSuite([*(FighterSelectionTests(name) for name in FighterSelectionTests.__dict__ if name.startswith('test_')),
                              *loader.loadTestsFromTestCase(PredicateTests)])
