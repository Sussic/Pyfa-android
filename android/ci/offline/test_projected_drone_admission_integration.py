"""Admission preserves large inactive user inputs; activation never silently caps."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from test_projected_drone_editor import ProjectedDroneTests


class AdmissionIntegrationTests(ProjectedDroneTests):
    def test_large_inactive_stack_reopen_copy_history_and_pre_effect_rejection(self):
        self.seeded([self.drone(amount=2**31-1,active=0)])
        saved=deepcopy(self.session._records); self.reopen()
        self.assertEqual(self.session._records,saved)
        from eos.saveddata.drone import Drone
        original=Drone.calculateModifiedAttributes
        evaluated=[]
        def spy(drone,*args,**kwargs):
            if drone.projected:
                evaluated.append(drone.amountActive)
                self.assertEqual(drone.amountActive,0,'Unadmitted active drone reached EOS')
            return original(drone,*args,**kwargs)
        row=self.rows()[0]
        with patch.object(Drone,'calculateModifiedAttributes',spy):
            self.reject('set_projected_drone_active',dict(fit_id=self.key,position=0,
                object_key=row['object_key'],active=True),'Projected-drone evaluation budget:')
        self.assertTrue(evaluated)
        self.edit('duplicate_fit',dict(fit_id=self.key,name='Large inactive copy'))
        other=next(k for k in self.session._records if k not in saved)
        self.assertEqual(self.session._records[other]['spec']['projected_drones'],saved[self.key]['spec']['projected_drones'])
        self.assertNotEqual(self.rows(other)[0]['object_key'],self.rows()[0]['object_key'])
        before=deepcopy(self.session._records[self.key]['spec'])
        self.change('remove_projected_drone',amount=2**31-1)
        self.assertEqual(self.rows(),[])
        self.undo();self.assertEqual(self.session._records[self.key]['spec'],before)
        self.redo();self.assertEqual(self.rows(),[])

    def test_inactive_source_merge_into_active_destination_is_admitted_as_result(self):
        self.seeded([self.drone(name='Light Armor Maintenance Bot I',amount=100000,active=0),
                     self.drone(name='Light Armor Maintenance Bot II',amount=1,active=1)])
        row=self.rows()[0]
        self.reject('change_projected_drone_variation',dict(fit_id=self.key,position=0,
            object_key=row['object_key'],item_id=self.item('Light Armor Maintenance Bot II')),
            'Projected-drone evaluation budget:')
        # A new inactive destination stays inactive and retains the whole total.
        self.change('remove_projected_drone',index=1,amount=1)
        self.change('change_projected_drone_variation',item_id=self.item('Light Armor Maintenance Bot II'))
        self.assertEqual((self.rows()[0]['amount'],self.rows()[0]['active']),(100000,0))
        self.assertIsNone(self.rows()[0]['range_m'])


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(AdmissionIntegrationTests(name) for name in AdmissionIntegrationTests.__dict__
                              if name.startswith('test_'))
