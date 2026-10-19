"""Pure mutation tests for the finite original/candidate comparison helper."""
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[4]/'candidate-integration/candidate.py'
SPEC=importlib.util.spec_from_file_location('d05_candidate_comparison',PATH)
HELPER=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(HELPER)

class TargetCandidateComparatorTests(unittest.TestCase):
    def test_exact_float_hex_types_and_structures(self):
        expected={'values':[0.0,-0.0,5e-324,1.0,1,None,True],'unit':'DPS'}
        HELPER.compare(expected,expected)
    def test_rejects_epsilon_numeric_kind_and_zero_sign(self):
        for expected,actual in ((1.0,1.0+2**-52),(0.0,-0.0),(1,1.0),(0,False),(5e-324,0.0)):
            with self.subTest(expected=expected,actual=actual),self.assertRaises(AssertionError):HELPER.compare(expected,actual)
    def test_rejects_missing_extra_order_and_presentation(self):
        for expected,actual in (({'x':1},{'x':1,'y':2}),({'x':1},{}),([1,2],[2,1]),('0.0','0')):
            with self.assertRaises(AssertionError):HELPER.compare(expected,actual)

if __name__=='__main__':unittest.main()
