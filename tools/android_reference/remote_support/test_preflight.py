"""No-EOS-run tests of the data-only boundary and finite source-work diagnostic."""
import inspect
from pathlib import Path
import sys
import unittest
from types import ModuleType
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.android_reference.remote_support.preflight import Boundary, diagnostic, HORIZONS, exact
from tools.android_reference.remote_support.cases import fixtures,scenario,SUITES


class DiagnosticTests(unittest.TestCase):
    def test_exact_identity_does_not_use_numerical_tolerance(self):
        for left,right in ((1.0,1.00000000001),(0.0,0),(True,1)):
            with self.assertRaises(AssertionError):exact(left,right,'raw')
        exact([(1,2.0)],[[1,2.0]],'serialized tuples')

    def test_exact_normalized_grouping_and_negative_need(self):
        result=diagnostic([(6000,-100,2,False,700,False),(6000,-100,0,False,0,False)])
        self.assertEqual(result['states'],[[0,3000,-100,0,0,0,False]])
        self.assertEqual(result['horizons'][str(HORIZONS[0])]['events'],7201)
    def test_disable_stagger_multiplies_need(self):
        result=diagnostic([(6000,100,0,True,0,False)]*2)
        self.assertEqual(result['states'],[[0,6000,200,0,0,0,False]])
    def test_distinct_drain_signs_are_not_grouped(self):
        self.assertEqual(diagnostic([(6000,x,0,False,0,False) for x in (-100,100)])['groups'],2)
    def test_unsafe_effective_duration_stops_before_simulator(self):
        with self.assertRaisesRegex(AssertionError,'zero grouped cycle'):
            diagnostic([(1,100,0,False,0,False)]*2)
    def test_inexact_float_lcm_is_not_certified(self):
        with self.assertRaisesRegex(AssertionError,'float LCM'):
            diagnostic([(100000007,1,0,False,0,False),(100000037,2,0,False,0,False)])
    def test_nonfinite_and_unsupported_semantics(self):
        for row in ((6000,float('nan'),0,False,0,False),(0,1,0,False,0,False),(6000,-100,1,False,0,True)):
            with self.assertRaises(AssertionError):diagnostic([row])
    def test_finite_module_only_schedule(self):
        ranges=dict(transfer_max=3000.0,armor_falloff=13500.0,beyond_support=50000.0,neut_falloff=15000.0,neut_beyond=25001.0)
        for suite in SUITES:
            for reverse in (False,True):
                steps=scenario(suite,ranges,reverse)
                self.assertEqual(len({s['name'] for s in steps}),len(steps))
                self.assertEqual(len(fixtures(suite)),3)
                for spec in fixtures(suite).values():
                    self.assertFalse(spec['drones']);self.assertFalse(spec['factor_reload'])
    def test_boundary_blocks_every_entry_without_invoking_source(self):
        fitmod=ModuleType('eos.saveddata.fit');capmod=ModuleType('eos.capSim')
        effectmod=ModuleType('eos.effects');eos=ModuleType('eos');eos.effects=effectmod
        calls=[]
        class Fit:pass
        class CapSimulator:pass
        methods=('simulateCap','_Fit__runCapSim','getCapSimData','calculateSustainableTank')
        getters=('capUsed','capRecharge','capStable','capState','capDelta','tank','effectiveTank','sustainableTank','effectiveSustainableTank')
        def original(*args,**kwargs):calls.append('source')
        Fit.calculateModifiedAttributes=original
        for name in methods:setattr(Fit,name,original)
        for name in getters:setattr(Fit,name,property(original))
        CapSimulator.reset=original;CapSimulator.run=original
        fitmod.Fit=Fit;capmod.CapSimulator=CapSimulator
        for ident in (6184,6185,6186,6187,6188,6197):
            setattr(effectmod,'Effect'+str(ident),type('Effect',(),{'handler':staticmethod(original)}))
        with patch.dict(sys.modules,{'eos':eos,'eos.saveddata.fit':fitmod,'eos.capSim':capmod,'eos.effects':effectmod}):
            boundary=Boundary();boundary.install()
            for name in methods:
                with self.assertRaisesRegex(AssertionError,'boundary'):getattr(Fit(),name)()
            for name in getters:
                with self.assertRaisesRegex(AssertionError,'boundary'):getattr(Fit(),name)
            for name in ('reset','run'):
                with self.assertRaisesRegex(AssertionError,'boundary'):getattr(CapSimulator(),name)()
            self.assertEqual(calls,[])
            self.assertEqual(len(boundary.attempts),len(methods)+len(getters)+2)
            boundary.close()
            self.assertIs(Fit.simulateCap,original)


if __name__=='__main__':unittest.main()
