"""Reject changed host inputs and any deviation from the pinned keyboard repair."""
import subprocess
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import charge_keyboard_retry as repair
import local_verification as launcher

ROOT=Path(__file__).resolve().parents[2]

class KeyboardRetryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths=(repair.PATH,'android/ci/local_verification.py')
        cls.before={p:subprocess.check_output(['git','show',repair.BEFORE+':'+p],cwd=ROOT) for p in paths}
        cls.after={p:subprocess.check_output(['git','show',repair.TEST_REVISION+':'+p],cwd=ROOT) for p in paths}
    def setUp(self):
        self.old=dict(self.before);self.new=dict(self.after)
        self.changed=[repair.PATH,'docs/android/STATUS.md','android/ci/charge_keyboard_retry.py']
        self.completed=launcher.plan('full',None)[:76]
    def output(self,args,**kwargs):
        if args[1]=='diff':return '\n'.join(self.changed)
        revision,path=args[2].split(':',1)
        result=(self.old if revision==repair.BEFORE else self.new)[path]
        return result.decode('utf-8') if kwargs.get('text') else result
    def validate(self,before=None):
        with patch.object(repair.subprocess,'check_output',side_effect=self.output):
            repair.exact_source(ROOT,before or repair.BEFORE,'after',self.completed)
    def test_exact_keyboard_repair_passes(self):self.validate()
    def test_changed_engine_fixture_app_or_deadline_fails(self):
        for path in ('android_bridge/charges.py','tools/android_reference/fixtures/charge_edits.json',
                     'android/app/src/main/java/io/github/sussic/pyfa/ChargeEditor.kt','android/ci/check-charge-edits.py'):
            with self.subTest(path=path):
                self.changed.append(path)
                with self.assertRaises(AssertionError):self.validate()
                self.changed.pop()
    def test_removed_visibility_assertion_fails(self):
        self.new[repair.PATH]=self.new[repair.PATH].replace(b'.assertIsDisplayed()',b'')
        with self.assertRaises(AssertionError):self.validate()
    def test_weakened_geometry_assertion_fails(self):
        self.new[repair.PATH]=self.new[repair.PATH].replace(b'fieldBottom <= viewport.bottom',b'true')
        with self.assertRaises(AssertionError):self.validate()
    def test_changed_keyboard_deadline_fails(self):
        self.new[repair.PATH]=self.new[repair.PATH].replace(b'+ 10_000',b'+ 60_000')
        with self.assertRaises(AssertionError):self.validate()
    def test_arbitrary_test_change_fails(self):
        self.new[repair.PATH]+=b'\n'
        with self.assertRaises(AssertionError):self.validate()
    def test_changed_host_execution_fails(self):
        path='android/ci/local_verification.py'
        original=b"self.db=output/'eve.db'"
        self.assertIn(original,self.new[path])
        self.new[path]=self.new[path].replace(original,b"self.db=output/'changed.db'")
        with self.assertRaises(AssertionError):self.validate()
    def test_incomplete_or_executed_failed_gate_fails(self):
        for completed in (self.completed[:-1],self.completed+['native:check-charge-edits.py']):
            with self.subTest(completed=completed):
                original=self.completed;self.completed=completed
                with self.assertRaises(AssertionError):self.validate()
                self.completed=original
    def test_other_source_revision_fails(self):
        with self.assertRaises(AssertionError):self.validate('different')

    def test_constructor_retains_only62_hosts_and_original_commit_stamps(self):
        def git(*args):
            if args[0]=='-C':return launcher.PIN
            if args[0]=='status':return ''
            if args[0]=='rev-parse':return 'after' if args[1]=='HEAD' else 'tree'
            raise AssertionError(args)
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory)
            attempts=[dict(gate=g,exit_code=0,log_sha256='hash-'+g) for g in self.completed]
            attempts[0]['tested_commit']='bfbbe1570c82b0e884f18461fa379f59b793dfbd'
            attempts.append(dict(gate='native:check-charge-edits.py',exit_code=1))
            state=dict(status='failed',mode='full',gate=None,plan=launcher.plan('full',None),
                       completed=self.completed,attempts=attempts,commit=repair.BEFORE,tree='old')
            (run/'run.json').write_text(json.dumps(state))
            args=SimpleNamespace(run=str(run),action='resume',restart_native=True,adopt_launcher_fix=False,
                source=None,reference_python=None,adopt_tank_history_fix=False,adopt_capacitor_runner_fix=False,
                adopt_resource_test_fix=False,adopt_projection_report_fix=False,adopt_stale_history_fix=False,
                adopt_cargo_observer_fix=False,adopt_pending_settings_fix=False,adopt_pending_runner_fix=False)
            with patch.object(launcher,'git',side_effect=git),patch.object(repair.subprocess,'check_output',side_effect=self.output):
                runner=launcher.Run(args)
            self.assertEqual(launcher.plan('full',None)[:62],runner.state['completed'])
            proof=runner.state['charge_keyboard_host_reuse']
            self.assertEqual(self.completed,proof['completed_before_adoption'])
            self.assertEqual(set(runner.state['completed']),set(proof['retained_log_hashes']))
            self.assertFalse(any(g.startswith(('build:','native:')) for g in runner.state['completed']))
            self.assertEqual('bfbbe1570c82b0e884f18461fa379f59b793dfbd',runner.state['attempts'][0]['tested_commit'])
            self.assertTrue(all(row['tested_commit']==repair.BEFORE for row in runner.state['attempts'][1:]))
            self.assertEqual(1,runner.state['attempts'][-1]['exit_code'])
            self.assertEqual('after',runner.state['commit'])

class BuildReuseTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        parent=Path(self.temporary.name);self.run=parent/'full';self.run.mkdir()
        self.source=parent/'build';self.source.mkdir();(self.source/'apks').mkdir();(self.source/'logs').mkdir()
        self.state=dict(mode='build',status='passed',gate=None,commit='current',plan=launcher.plan('build',None),
                        completed=launcher.plan('build',None),attempts=[])
        for index,gate in enumerate(self.state['completed']):
            log=f'logs/{index}.log';(self.source/log).write_text('actual build '+gate)
            self.state['attempts'].append(dict(gate=gate,exit_code=0,tested_commit='current',log=log,log_sha256=repair.sha(self.source/log)))
        manifest={}
        for name in ('app-debug.apk','app-debug-androidTest.apk'):
            key='apks/'+name;(self.source/key).write_bytes(name.encode())
            manifest[key]=dict(bytes=(self.source/key).stat().st_size,sha256=repair.sha(self.source/key))
        (self.source/'files.json').write_text(json.dumps(manifest))
        self.refresh_state()
    def refresh_state(self):
        (self.source/'run.json').write_text(json.dumps(self.state))
        self.proof=dict(source_run=self.source.name,state_sha256=repair.sha(self.source/'run.json'),
            manifest_sha256=repair.sha(self.source/'files.json'),
            apk_hashes={p.name:repair.sha(p) for p in (self.source/'apks').glob('*.apk')})
    def validate(self):return repair.validated_build(self.run,self.proof,'current')
    def test_exact_commit_complete_build_passes(self):self.validate()
    def test_wrong_revision_or_incomplete_or_nonbuild_fails(self):
        for key,value in (('commit','older'),('completed',self.state['completed'][:-1]),('mode','full'),('status','failed'),('gate','package')):
            with self.subTest(key=key):
                old=self.state[key];self.state[key]=value;self.refresh_state()
                with self.assertRaises(AssertionError):self.validate()
                self.state[key]=old;self.refresh_state()
    def test_changed_gate_log_fails(self):
        (self.source/'logs/0.log').write_text('changed')
        with self.assertRaises(AssertionError):self.validate()
    def test_changed_test_apk_fails(self):
        (self.source/'apks/app-debug-androidTest.apk').write_bytes(b'changed')
        with self.assertRaises(AssertionError):self.validate()
    def test_changed_manifest_fails(self):
        (self.source/'files.json').write_text('{}')
        with self.assertRaises(AssertionError):self.validate()
    def test_failed_or_other_commit_gate_fails(self):
        for key,value in (('exit_code',1),('tested_commit','older')):
            with self.subTest(key=key):
                old=self.state['attempts'][0][key];self.state['attempts'][0][key]=value;self.refresh_state()
                with self.assertRaises(AssertionError):self.validate()
                self.state['attempts'][0][key]=old
    def test_build_import_keeps_original_provenance(self):
        (self.run/'logs').mkdir();(self.run/'apks').mkdir()
        retained=launcher.plan('full',None)[:62]
        runner=SimpleNamespace(directory=self.run,state=dict(completed=list(retained),attempts=[]))
        proof=dict(to_commit='current',retained_gates=retained)
        repair.reuse_build(runner,proof)
        self.assertEqual(launcher.plan('full',None)[:67],runner.state['completed'])
        self.assertEqual(5,len(runner.state['attempts']))
        for row,original in zip(runner.state['attempts'],self.state['attempts']):
            self.assertEqual(original['tested_commit'],row['tested_commit'])
            self.assertEqual(original['log_sha256'],repair.sha(self.run/row['log']))
            self.assertEqual(self.source.name,row['reused_from_run'])

if __name__=='__main__':unittest.main()
