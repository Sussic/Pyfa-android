"""Read-only export, stale-request and atomic re-import checks against real EOS."""
import os
import sys
sys.path[:0]=[os.environ['PYFA_CURRENT_REPO'],os.environ['PYFA_REFERENCE_SOURCE']]
from test_native_session import NativeSessionTests
import json
from copy import deepcopy

class ExportSessionTests(NativeSessionTests):
    # Only this class's new tests are collected below, not inherited test cases.
    def export_request(self, **changes):
        value=dict(version=1,request_id='export-test',context=self.session.context(),fit_id=self.key,
                   revision=self.session._revisions[self.key],options=dict.fromkeys(
                   ('loaded_charges','cargo','implants','boosters','mutations'),True))
        value.update(changes);return value
    def export(self, **changes):return json.loads(self.session.export_preview(json.dumps(self.export_request(**changes))))
    def test_export_empty_hull_is_valid_and_readonly(self):
        before=self.path.read_bytes();state=deepcopy(self.session.graph._state);history=self.session.history_details(self.key)
        result=self.export();self.assertTrue(result['ok'],result)
        self.assertTrue(result['text'].startswith('[Rifter, Synthetic Rifter]'))
        self.assertEqual(before,self.path.read_bytes());self.assertEqual(state,self.session.graph._state)
        self.assertEqual(history,self.session.history_details(self.key));self.assertEqual(result,self.export())
    def test_export_rejects_stale_and_unknown(self):
        self.assertEqual(self.export(revision=999)['error']['code'],'stale_context')
        self.assertEqual(self.export(fit_id='missing')['error']['code'],'missing_fit')
        ctx=self.session.context();ctx['generation']+=1
        self.assertEqual(self.export(context=ctx)['error']['code'],'stale_context')
    def test_export_invalid_options_never_output(self):
        for options in ({},{'cargo':True},dict.fromkeys(('loaded_charges','cargo','implants','boosters','mutations'),1)):
            result=self.export(options=options);self.assertFalse(result['ok']);self.assertIsNone(result['text'])
    def test_export_header_injection_refused(self):
        self.edit('rename_fit',dict(fit_id=self.key,name='bad [name]'))
        result=self.export();self.assertFalse(result['ok']);self.assertEqual(result['error']['code'],'unrepresentable_name')
    def test_export_reimport_preview_does_not_write(self):
        text=self.export()['text'];before=self.path.read_bytes()
        result=json.loads(self.session.import_preview(json.dumps(dict(version=1,request_id='roundtrip',profile_id='builtin:all5',documents=[dict(label='Export',text=text)]))))
        self.assertTrue(result['ok'],result);self.assertEqual(before,self.path.read_bytes())
    def test_export_explicit_empty_racks_roundtrip(self):
        raw='[Rifter, Vacant]\n\n[Empty Low slot]\n[Empty Low slot]\n\n[Empty High slot]'
        result=json.loads(self.session.import_preview(json.dumps(dict(version=1,request_id='vacant',profile_id='builtin:all5',documents=[dict(label='Vacant',text=raw)]))))
        self.assertTrue(result['ok'],result)
        mixed=raw.replace('[Empty Low slot]\n[Empty Low slot]','[Empty Low slot]\n[Empty High slot]')
        result=json.loads(self.session.import_preview(json.dumps(dict(version=1,request_id='mixed',profile_id='builtin:all5',documents=[dict(label='Mixed',text=mixed)]))))
        self.assertFalse(result['ok']);self.assertTrue(any(d['code']=='ambiguous_section' for d in result['diagnostics']))
    def test_export_duplicate_json_fields_refused(self):
        raw=json.dumps(self.export_request());raw=raw[:-1]+',"version":1}'
        result=json.loads(self.session.export_preview(raw));self.assertFalse(result['ok']);self.assertIsNone(result['text'])
    def test_export_unavailable_session_refused(self):
        request=self.export_request();self.session._disable()
        result=json.loads(self.session.export_preview(json.dumps(request)));self.assertFalse(result['ok']);self.assertIsNone(result['text'])

def load_tests(loader, tests, pattern):
    import unittest
    return unittest.TestSuite(ExportSessionTests(name) for name in ExportSessionTests.__dict__ if name.startswith('test_'))
