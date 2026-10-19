"""Metadata-only admission invariants; no fit, effects, simulation or disk writes."""
from copy import deepcopy
import sys
import types
import unittest
from unittest.mock import patch
from android_bridge import projected_drone_budget as budget
from android_bridge.projected_drone_admission import AdmissionRejected


def effect(identity=6687, kind='projected', grouped=False):
    return types.SimpleNamespace(ID=identity, activeByDefault=True,
        runTime='late' if identity==6689 else 'normal',
        isType=lambda name:name==kind, getattr=lambda name:grouped if name=='grouped' else None)


def item(identity, *, drone=True, category='Drone', effects=None):
    return types.SimpleNamespace(ID=identity,isDrone=drone,isAbyssal=False,
        isType=lambda name:name=='projected',category=types.SimpleNamespace(name=category),
        effects={str(e.ID):e for e in (effects if effects is not None else [effect()])})


def record(name='Web', amount=1, active=1):
    return dict(spec=dict(modules=[],drones=[],fighters=[],projected_drones=[
        dict(name=name,amount=amount,active=active,range_m=None)]),
        implants=[],boosters=[],commands=[],projections=[])


class ProjectedDroneBudgetTests(unittest.TestCase):
    def setUp(self):
        self.catalog={'Web':item(1),'Alias':item(1),'Disruptor':item(2,effects=[effect(6694)]),
                      'Unaudited':item(3,effects=[effect(9999)]),
                      'Subsystem':item(4,drone=False,category='Subsystem',effects=[])}
        eos=types.ModuleType('eos'); db=types.ModuleType('eos.db')
        db.getItem=self.catalog.get; eos.db=db
        self.context=patch.dict(sys.modules,{'eos':eos,'eos.db':db});self.context.start()
        self.addCleanup(self.context.stop)

    def test_actual_active_reservation_is_input_only_and_never_clamps(self):
        rows={'a':record(amount=5,active=0)}; before=deepcopy(rows)
        inactive=budget.admit(rows)
        self.assertEqual(rows,before)
        rows['a']['spec']['projected_drones'][0]['active']=5
        self.assertLess(inactive['cold_units'],budget.admit(rows)['cold_units'])
        rows['a']['spec']['projected_drones'][0].update(amount=2**31-1,active=0)
        self.assertEqual(inactive,budget.admit(rows))
        rows['a']['spec']['projected_drones'][0]['active']=2**31-1
        with self.assertRaisesRegex(AdmissionRejected,'evaluation budget'):
            budget.admit(rows)

    def test_catalogue_fail_closed_duplicate_identity_and_legacy_exemption(self):
        for name in ('Missing','Unaudited'):
            with self.assertRaises(AdmissionRejected):budget.admit({'a':record(name)})
        rows={'a':record()};rows['a']['spec']['projected_drones'] += record('Alias')['spec']['projected_drones']
        with self.assertRaisesRegex(AdmissionRejected,'duplicate'):budget.admit(rows)
        rows['a']['spec'].pop('projected_drones')
        with patch.object(sys.modules['eos.db'],'getItem',side_effect=AssertionError('legacy catalogue access')):
            self.assertFalse(budget.admit(rows)['enabled'])

    def test_projection_multiplicity_and_all_subsystem_rows_are_counted(self):
        rows={'a':record('Disruptor')}
        baseline=budget.admit(rows)
        rows['a']['spec']['modules']=[dict(name='Subsystem')]*3
        grown=budget.admit(rows)
        self.assertEqual(grown['module_bounds']['a']-baseline['module_bounds']['a'],42)
        self.assertGreater(grown['cold_units'],baseline['cold_units'])
        rows['a']['projections']=[dict(source_id='a',amount=2**31-1)]
        with self.assertRaisesRegex(AdmissionRejected,'cold-read'):budget.admit(rows)

    def test_frozen_operation_surface_unknown_future_calls_fail_closed(self):
        # Importing the contract is input-schema loading, not engine startup.
        from android_bridge.contract import ARGUMENTS
        self.assertEqual(set(ARGUMENTS),set(budget.ADMITTED_OPERATIONS))
        for operation in ARGUMENTS:budget.require_operation(operation,{'a':record()})
        with self.assertRaises(AdmissionRejected):budget.require_operation('future_unknown',{'a':record()})
        budget.require_operation('future_unknown',{'a':dict(spec=dict(modules=[]))})


if __name__=='__main__':unittest.main()
