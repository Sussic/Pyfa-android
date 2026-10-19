"""Reject missing, misidentified and keyboard-obscured native search witnesses."""
import copy
import json
import unittest
from cargo_action_summary import validate_search_checks

class SearchChecksTest(unittest.TestCase):
    def setUp(self):
        self.expected=[('Core Scanner Probe I',30013)]
        self.rows=[dict(query='Core Scanner Probe I',item_id=30013,keyboard_visible=True,
                       search_completed=True,viewport_top=24.0,viewport_bottom=960.0,
                       button_top=810.0,button_bottom=920.0,ime_bottom=940)]
    def test_complete_actual_geometry(self):
        validate_search_checks(self.rows,self.expected)
    def test_missing_or_extra_search(self):
        for rows in ([],self.rows*2):
            with self.assertRaises(AssertionError):validate_search_checks(rows,self.expected)
    def test_restored_json_requires_empty_array(self):
        validate_search_checks(json.loads('[]'), [])
        for encoded in ('{}', '""', 'null', 'false', '0'):
            with self.subTest(encoded=encoded), self.assertRaises(AssertionError):
                validate_search_checks(json.loads(encoded), [])
    def test_search_json_requires_object_records(self):
        for encoded in ('[[]]', '[null]', '[false]', '[0]', '["query"]'):
            with self.subTest(encoded=encoded), self.assertRaises(AssertionError):
                validate_search_checks(json.loads(encoded), self.expected)
    def test_identity_completion_and_geometry_corruption(self):
        for key,value in [('query','wrong'),('item_id',222),('keyboard_visible',False),
                ('search_completed',False),('ime_bottom',0),('ime_bottom',True),
                ('button_top',-1),('button_bottom',961),('button_top',920),
                ('viewport_bottom',float('nan')),('button_bottom',float('inf')),
                ('viewport_top',True)]:
            rows=copy.deepcopy(self.rows);rows[0][key]=value
            with self.subTest(key=key,value=value),self.assertRaises((AssertionError,ValueError)):
                validate_search_checks(rows,self.expected)

if __name__=='__main__':unittest.main()
