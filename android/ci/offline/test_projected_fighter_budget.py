"""Pure metadata admission checks; no EOS fit, effects or simulation is run."""
from copy import deepcopy
import sys
import types
import unittest
from unittest.mock import patch
from android_bridge import projected_fighter_budget as fighters, projected_drone_budget as budget
from android_bridge.projected_drone_admission import AdmissionRejected


def effect(identity, *, projected=True, grouped=True, implemented=True):
    return types.SimpleNamespace(ID=identity, isImplemented=implemented, activeByDefault=True,
        runTime='normal', isType=lambda name:projected and name=='projected',
        getattr=lambda name:grouped if name=='grouped' else None)


def row(amount=3, active=True, web=True, prop=False):
    return dict(name='Web fighter',amount=amount,active=active,range_m=None,
                abilities=[dict(effect_id=6435,active=web),dict(effect_id=6441,active=prop)])


def record(rows):
    return dict(spec=dict(modules=[],drones=[],fighters=[],projected_fighters=rows),
                implants=[],boosters=[],commands=[],projections=[])


class ProjectedFighterBudgetTests(unittest.TestCase):
    def setUp(self):
        self.projected=effect(6435);self.prop=effect(6441,projected=False,grouped=False)
        self.item=types.SimpleNamespace(ID=1,category=types.SimpleNamespace(name='Fighter'),
            isType=lambda name:name=='projected',getAttribute=lambda name:3,
            effects={'web':self.projected,'prop':self.prop})
        eos=types.ModuleType('eos');db=types.ModuleType('eos.db');eos.db=db
        db.getItem=lambda name:self.item if name=='Web fighter' else None
        self.context=patch.dict(sys.modules,{'eos':eos,'eos.db':db});self.context.start();self.addCleanup(self.context.stop)

    def test_grouped_zero_and_maximum_have_same_dispatch_cost(self):
        self.assertEqual([fighters.cost([row(amount=n)]) for n in (0,1,3)],[13,13,13])
        self.assertEqual(fighters.cost([row(active=False)]),3)
        self.assertEqual(fighters.cost([row(web=False)]),9)
        self.assertEqual(fighters.cost([row(prop=True)]),13)

    def test_complete_abilities_and_unknown_policy_fail_closed(self):
        bad=row();bad['abilities'].pop()
        with self.assertRaises(AdmissionRejected):fighters.cost([bad])
        for attribute,value in [('ID',99999),('runTime','late'),('activeByDefault',False),('isImplemented',False)]:
            old=getattr(self.projected,attribute);setattr(self.projected,attribute,value)
            with self.assertRaises(AdmissionRejected):fighters.cost([row()])
            setattr(self.projected,attribute,old)
        self.projected.getattr=lambda name:False
        with self.assertRaises(AdmissionRejected):fighters.cost([row(active=False)])

    def test_duplicate_item_rows_are_independent_and_inputs_remain_exact(self):
        rows=[row(),row(amount=0),row(active=False)];before=deepcopy(rows)
        self.assertEqual(fighters.cost(rows),29);self.assertEqual(rows,before)
        value=budget.admit({'a':record(rows)});self.assertTrue(value['enabled'])
        self.assertEqual(value['cold_units'],58)

    def test_fighter_only_graph_and_proposal_activate_guard_without_drones(self):
        values={'a':record([row(active=False)])};before=deepcopy(values)
        proposed=budget.proposed_records(values,'a',[row()],family='projected_fighters')
        self.assertTrue(budget.present(values));self.assertEqual(values,before)
        self.assertGreater(budget.admit(proposed)['cold_units'],budget.admit(values)['cold_units'])
        with self.assertRaises(AdmissionRejected):budget.require_operation('unknown',values)
        with self.assertRaises(ValueError):budget.proposed_records(values,'a',[],family='unknown')

    def test_ordinary_multifit_metadata_admits_and_large_work_refuses_without_clamp(self):
        ordinary={str(i):record([row() for _ in range(8)]) for i in range(18)}
        before=deepcopy(ordinary);self.assertTrue(budget.admit(ordinary)['enabled']);self.assertEqual(ordinary,before)
        huge={'a':record([row() for _ in range(1024)])};before=deepcopy(huge)
        with self.assertRaises(AdmissionRejected):budget.admit(huge)
        self.assertEqual(huge,before)


if __name__=='__main__':unittest.main()
