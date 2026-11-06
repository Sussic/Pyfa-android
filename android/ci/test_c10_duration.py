"""Synthetic V3-shaped duration artifacts; no device/database/controller calls."""
import copy
import hashlib
import json
import unittest
from xml.sax.saxutils import escape

from c10_collection import CollectionError
from c10_duration import check_duration


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class DurationTests(unittest.TestCase):
    def setUp(self):
        self.required = dict(case_id='module399-duration73', oracle_sha256='a'*64,
                             seed_sha256='b'*64, fit_id='synthetic', object_key='object', position=0,
                             package='io.github.sussic.pyfa.dev')
        self.edit = {k:v for k,v in self.required.items() if k != 'package'}
        self.edit.update(revision=2, generation=3, session='c'*32, pid=42, process_start_elapsed_ms=100,
                         graph_sha256=sha(b'synthetic-store-bytes'), external_force_stop_required=True,
                         writer_process_death_proved_by_this_test=False)
        argv=['adb.exe','-H','127.0.0.1','-P','1234','-s','synthetic-device',
              'shell','pidof',self.required['package']]
        self.required['pid_absence_argv']=argv
        self.artifacts = dict(startup_edit=json.dumps(dict(pid=42,process_start_elapsed_ms=100)).encode(),
                              startup_reopen=json.dumps(dict(pid=42,process_start_elapsed_ms=200)).encode(),
                              graph_edit=b'synthetic-store-bytes',graph_stopped=b'synthetic-store-bytes',
                              graph_reopen=b'synthetic-store-bytes',
                              pid_absence=json.dumps(dict(argv=argv,exit_code=1,stdout='',stderr='')).encode())
        self.encode_edit()
        self.bind()

    def encode_edit(self):
        self.artifacts['edit_receipt']=('<map><string name="edit">'+escape(json.dumps(self.edit))+'</string></map>').encode()

    def bind(self):
        self.required['sha256']={k:sha(v) for k,v in self.artifacts.items()}

    def check(self):
        return check_duration(self.artifacts,self.required)

    def test_valid_content_remains_pending_and_does_not_mutate_inputs(self):
        before=copy.deepcopy((self.artifacts,self.required))
        result=self.check()
        self.assertIs(False,result['native_accepted'])
        self.assertIn('trace_completeness_and_no_reseed',result['remaining'])
        self.assertEqual(before,(self.artifacts,self.required))

    def test_missing_extra_or_tampered_artifact_is_rejected(self):
        original=copy.deepcopy(self.artifacts)
        for artifacts in ({k:v for k,v in original.items() if k!='graph_reopen'},
                          {**original,'extra':b'x'},{**original,'graph_edit':b'tampered'}):
            with self.subTest(roles=artifacts.keys()):
                self.artifacts=artifacts
                with self.assertRaises(CollectionError):self.check()

    def test_metadata_identity_and_unsupported_claims_are_rejected(self):
        for key,bad in [('case_id','wrong'),('oracle_sha256','wrong'),('seed_sha256','wrong'),
                        ('fit_id','wrong'),('object_key','wrong'),('position',False),
                        ('revision',True),('generation',1),('session',''),('pid',True),
                        ('external_force_stop_required',False),('writer_process_death_proved_by_this_test',True)]:
            with self.subTest(key=key):
                old=self.edit[key];self.edit[key]=bad;self.encode_edit();self.bind()
                with self.assertRaises(CollectionError):self.check()
                self.edit[key]=old

    def test_same_or_older_process_and_bad_birth_types_are_rejected(self):
        for startup in (dict(pid=42,process_start_elapsed_ms=100),dict(pid=99,process_start_elapsed_ms=99),
                        dict(pid=True,process_start_elapsed_ms=200),dict(pid=42,process_start_elapsed_ms=200.0)):
            with self.subTest(startup=startup):
                self.artifacts['startup_reopen']=json.dumps(startup).encode();self.bind()
                with self.assertRaises(CollectionError):self.check()

    def test_edited_stopped_or_reopened_store_change_is_rejected(self):
        for role in ('graph_edit','graph_stopped','graph_reopen'):
            with self.subTest(role=role):
                old=self.artifacts[role];self.artifacts[role]=b'changed';self.bind()
                with self.assertRaises(CollectionError):self.check()
                self.artifacts[role]=old

    def test_process_absence_and_device_command_must_match(self):
        original=json.loads(self.artifacts['pid_absence'])
        for patch in ({'exit_code':0},{'exit_code':True},{'stdout':'42'},
                      {'argv':['adb','shell','pidof','other']},{'argv':None},
                      {'stderr':'error: device offline'},{'stderr':None}):
            with self.subTest(patch=patch):
                self.artifacts['pid_absence']=json.dumps({**original,**patch}).encode();self.bind()
                with self.assertRaises(CollectionError):self.check()
        self.artifacts['pid_absence']=json.dumps({key:value for key,value in original.items() if key!='stderr'}).encode()
        self.bind()
        with self.assertRaises(CollectionError):self.check()

    def test_malformed_duplicate_or_missing_edit_receipt_is_rejected(self):
        original=self.artifacts['edit_receipt']
        duplicate=original.replace(b'</map>',original.split(b'<map>')[1])
        for raw in (b'<map>',b'<map/>',duplicate,b'<map><string name="edit">[]</string></map>',
                    b'<map><string name="edit">{"pid":1,"pid":2}</string></map>'):
            with self.subTest(raw=raw):
                self.artifacts['edit_receipt']=raw;self.bind()
                with self.assertRaises(CollectionError):self.check()

    def test_edit_and_startup_birth_mismatch_is_rejected(self):
        self.artifacts['startup_edit']=json.dumps(dict(pid=43,process_start_elapsed_ms=100)).encode();self.bind()
        with self.assertRaises(CollectionError):self.check()
