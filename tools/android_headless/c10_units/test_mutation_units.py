"""Unit-layer contracts; full EOS/transaction/reopen and Android proof are separate.

The expected scalar conversions come from pinned original Unit methods, not the
candidate adapter. A spy replaces the old raw commit to inspect prevalidation.
"""
import argparse
import importlib.util
import math
from pathlib import Path
import sys
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from reference_units import CASES,load_unit,observe,unit_for

PACKAGE='c10_units_candidate'
CANDIDATE_SOURCE=None
REFERENCE_SOURCE=None


def configure_sources(candidate,reference):
    global CANDIDATE_SOURCE,REFERENCE_SOURCE
    CANDIDATE_SOURCE=candidate.resolve(strict=True)
    REFERENCE_SOURCE=reference.resolve(strict=True)
    if CANDIDATE_SOURCE==REFERENCE_SOURCE:
        raise ValueError('Candidate and independent pinned reference must be distinct')
    if not (CANDIDATE_SOURCE/'android_bridge').is_dir():
        raise ValueError('Candidate source must contain android_bridge')
    package=ModuleType(PACKAGE);package.__path__=[str(CANDIDATE_SOURCE/'android_bridge')]
    sys.modules[PACKAGE]=package
def load(name):
    if CANDIDATE_SOURCE is None:
        raise RuntimeError('Supply explicit --candidate-source and --reference-source')
    full=PACKAGE+'.'+name
    if full in sys.modules:return sys.modules[full]
    spec=importlib.util.spec_from_file_location(full,CANDIDATE_SOURCE/'android_bridge'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[full]=module;spec.loader.exec_module(module);return module

class UnitLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if CANDIDATE_SOURCE is None or REFERENCE_SOURCE is None:
            raise RuntimeError('Use the explicit candidate/reference source CLI')
        cls.Unit,cls.provenance=load_unit(REFERENCE_SOURCE)
        cls.adapter=load('mutation_units');cls.raw=load('mutation_editor')

    def mutator(self,case,attribute_id=1,high=True,name='testAttribute'):
        unit=unit_for(self.Unit,case['name'],case['label'])
        attribute=SimpleNamespace(unit=unit,unitID=None if unit is None else attribute_id,
                                  name=name,displayName=name)
        return SimpleNamespace(attrID=attribute_id,attribute=attribute,value=case['raw'],
            minValue=case['minimum'],maxValue=case['maximum'],baseValue=case['base'],highIsGood=high)

    def thing(self,mutators,group='Synthetic module'):
        return SimpleNamespace(isMutated=True,mutators={m.attrID:m for m in mutators},
            item=SimpleNamespace(group=SimpleNamespace(name=group)))

    def context(self,mutators,kind='module'):
        thing=self.thing(mutators)
        fit=SimpleNamespace(modules=[thing] if kind=='module' else [],drones=[thing] if kind=='drone' else [])
        engine=SimpleNamespace(_check_fit=lambda candidate:self.assertIs(candidate,fit))
        return thing,fit,engine

    def request(self,edits,kind='module'):
        return {'kind':kind,'position':0,'object_key':'1'*32,'edits':edits}

    def identity(self):
        module=ModuleType(PACKAGE+'.inspection_identity');module.identity=lambda fit,thing:'1'*32
        return patch.dict(sys.modules,{module.__name__:module})

    def test_original_source_numeric_witnesses_and_sorted_display_anchor(self):
        for case in CASES:
            with self.subTest(unit=case['name'],raw=case['raw']):
                mutator=self.mutator(case);result=self.adapter.display_metadata(self.thing([mutator]),mutator)
                expected=observe(self.Unit,case);values=expected['display']
                self.assertTrue(result['available']);self.assertIsNone(result['reason'])
                self.assertEqual(values[0],result['value'])
                self.assertEqual(min(values[1:3]),result['minimum'])
                self.assertEqual(max(values[1:3]),result['maximum'])
                self.assertEqual(values[3],result['slider_base'])
                self.assertEqual(expected['display_unit'] or '',result['unit_label'])
                self.assertEqual(not expected['endpoint_order_reversed'],result['higher_is_better'])

    def test_desktop_group_direction_override_is_applied_before_display_order(self):
        case={'name':'Inverse Absolute Percent','label':'%','raw':0.875,'minimum':0.75,'maximum':0.9375,'base':0.875}
        mutator=self.mutator(case,name='speedFactor',high=True)
        result=self.adapter.display_metadata(self.thing([mutator],'Stasis Web'),mutator)
        self.assertTrue(result['higher_is_better'])

    def test_nonnumeric_units_are_explicit_and_do_not_invent_display_values(self):
        for name in ('Boolean','Sizeclass','typeID','groupID','attributeID'):
            case={'name':name,'label':'','raw':1.0,'minimum':1.0,'maximum':2.0,'base':1.0}
            with self.subTest(unit=name):
                mutator=self.mutator(case);result=self.adapter.display_metadata(self.thing([mutator]),mutator)
                self.assertFalse(result['available']);self.assertTrue(result['reason'])
                for key in ('value','minimum','maximum','slider_base','higher_is_better','unit_label'):
                    self.assertIsNone(result[key])

    def test_sparse_display_edit_preserves_omitted_raw_bits_and_delegates_once(self):
        case={'name':'Absolute Percent','label':'%','raw':0.125,'minimum':0.0,'maximum':1.0,'base':0.125}
        first=self.mutator(case,1)
        second=self.mutator({'name':None,'label':None,'raw':-0.0,'minimum':0.0,'maximum':0.0,'base':0.0},2)
        for kind in ('module','drone'):
            with self.subTest(kind=kind):
                thing,fit,engine=self.context([first,second],kind)
                args=self.request([{'attribute_id':1,'value':25.0,'representation':'display'}],kind)
                with self.identity(),patch.object(self.raw,'change',return_value=['delegated']) as commit:
                    self.assertEqual(['delegated'],self.adapter.change(engine,fit,args))
                commit.assert_called_once();raw=commit.call_args.args[2]
                self.assertEqual([1,2],[row['attribute_id'] for row in raw['attributes']])
                self.assertEqual(0.25,raw['attributes'][0]['value'])
                self.assertEqual(second.value.hex(),raw['attributes'][1]['value'].hex())
                self.assertEqual(0.125,first.value)

    def test_missing_declared_unit_is_unavailable_while_true_unitless_is_identity(self):
        mutator=self.mutator(CASES[0]);thing=self.thing([mutator])
        self.assertTrue(self.adapter.display_metadata(thing,mutator)['available'])
        for unit_id in (0,105):
            mutator.attribute.unitID=unit_id
            display=self.adapter.display_metadata(thing,mutator)
            self.assertFalse(display['available']);self.assertTrue(display['reason'])
            thing,fit,engine=self.context([mutator])
            with self.identity(),patch.object(self.raw,'change') as commit:
                with self.assertRaises(ValueError):
                    self.adapter.change(engine,fit,self.request([{'attribute_id':1,'value':0.15,'representation':'display'}]))
            commit.assert_not_called()

    def test_unavailable_converted_unit_keeps_explicit_raw_entry(self):
        case={'name':'Boolean','label':'','raw':1.0,'minimum':0.0,'maximum':2.0,'base':1.0}
        mutator=self.mutator(case);thing,fit,engine=self.context([mutator])
        self.assertFalse(self.adapter.display_metadata(thing,mutator)['available'])
        with self.identity(),patch.object(self.raw,'change',return_value=[]) as commit:
            self.adapter.change(engine,fit,self.request([{'attribute_id':1,'value':2.0,'representation':'raw'}]))
        self.assertEqual(2.0,commit.call_args.args[2]['attributes'][0]['value'])

    def test_inverse_display_endpoint_uses_the_exact_raw_endpoint(self):
        case={'name':'Inverse Absolute Percent','label':'%','raw':0.5,'minimum':0.1,'maximum':0.9,'base':0.5}
        mutator=self.mutator(case);thing,fit,engine=self.context([mutator])
        display=mutator.attribute.unit.SimplifyValue(mutator.minValue)
        self.assertNotEqual(mutator.minValue,mutator.attribute.unit.ComplicateValue(display))
        with self.identity(),patch.object(self.raw,'change',return_value=[]) as commit:
            self.adapter.change(engine,fit,self.request([{'attribute_id':1,'value':display,'representation':'display'}]))
        self.assertEqual(mutator.minValue.hex(),commit.call_args.args[2]['attributes'][0]['value'].hex())

    def test_invalid_second_edit_never_delegates_a_partial_change(self):
        case={'name':'Absolute Percent','label':'%','raw':0.125,'minimum':0.0,'maximum':1.0,'base':0.125}
        mutators=[self.mutator(case,1),self.mutator(case,2)];thing,fit,engine=self.context(mutators)
        edits=[{'attribute_id':1,'value':25.0,'representation':'display'},
               {'attribute_id':2,'value':1000.0,'representation':'display'}]
        with self.identity(),patch.object(self.raw,'change') as commit:
            with self.assertRaises(ValueError):self.adapter.change(engine,fit,self.request(edits))
        commit.assert_not_called();self.assertEqual([0.125,0.125],[m.value for m in mutators])

    def test_unknown_stale_identity_or_attribute_never_delegates(self):
        mutator=self.mutator(CASES[0]);thing,fit,engine=self.context([mutator])
        for edits,key in (([{'attribute_id':99,'value':0.2,'representation':'raw'}],'1'*32),
                          ([{'attribute_id':1,'value':0.2,'representation':'raw'}],'2'*32)):
            args=self.request(edits);args['object_key']=key
            with self.identity(),patch.object(self.raw,'change') as commit:
                with self.assertRaises(ValueError):self.adapter.change(engine,fit,args)
            commit.assert_not_called()

    def test_nonfinite_duplicate_unordered_and_empty_edits_are_rejected(self):
        bad=[[],[{'attribute_id':1,'value':float('nan'),'representation':'display'}],
            [{'attribute_id':1,'value':True,'representation':'raw'}],
            [{'attribute_id':1,'value':0.1,'representation':'raw'}]*2,
            [{'attribute_id':2,'value':0.1,'representation':'raw'},{'attribute_id':1,'value':0.1,'representation':'raw'}]]
        for edits in bad:
            with self.subTest(edits=edits),self.assertRaises(ValueError):
                self.adapter.validate_request(self.request(edits))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-source',type=Path,required=True)
    parser.add_argument('--reference-source',type=Path,required=True)
    parser.add_argument('-v','--verbose',action='store_true')
    args=parser.parse_args()
    configure_sources(args.candidate_source,args.reference_source)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(UnitLayerTests)
    if suite.countTestCases()!=10:
        raise RuntimeError('The complete ten-method scalar contract must be selected')
    result=unittest.TextTestRunner(verbosity=2 if args.verbose else 1).run(suite)
    complete=(result.wasSuccessful() and result.testsRun==10 and not result.skipped
              and not result.expectedFailures and not result.unexpectedSuccesses)
    return 0 if complete else 1


if __name__=='__main__':raise SystemExit(main())
