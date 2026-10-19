"""Regression cases for truthful local-result reporting, using small synthetic receipts."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import report_local
from local_verification import plan

ROOT=Path(__file__).resolve().parents[2]
COMMIT='a'*40

class LocalResultTest(unittest.TestCase):
    def setUp(self):
        # Preserve original reporter regressions against the delivered inherited
        # plan; current inspector reference-only plans deliberately cannot publish.
        self.inherited_plan=[gate for gate in plan('full',None)[:175] if not gate.startswith(('reference:inspector_','headless:inspector_','native:inspection-'))]
        self.plan_patch=patch('local_verification.plan',return_value=self.inherited_plan)
        self.plan_patch.start();self.addCleanup(self.plan_patch.stop)
        # This suite retains the original reporter fixtures; C04 validation is
        # tested independently with explicit missing-gate and decision failures.
        c04=patch('report_local.validate_c04_delivery'); c04.start(); self.addCleanup(c04.stop)
        self.directory=tempfile.TemporaryDirectory()
        self.run=Path(self.directory.name)
        self.state={'mode':'full','gate':None,'status':'passed','plan':self.inherited_plan,
            'completed':self.inherited_plan.copy(),'commit':COMMIT,'hosted_actions_pass':False,
            'attempts':[{'gate':g,'exit_code':0,'tested_commit':COMMIT,'log':'gate.log',
                'log_sha256':hashlib.sha256(b'actual fixture log').hexdigest()} for g in self.inherited_plan]}
        (self.run/'gate.log').write_bytes(b'actual fixture log')
        native=self.run/'native';(native/'junit').mkdir(parents=True)
        (native/'junit/TEST-windows-initial.xml').write_text('<testsuite tests="5"/>')
        (native/'native-summary.json').write_text(json.dumps({'checkout_sha':COMMIT,'workflow_run':None,
            'execution':{'kind':'local_windows','local_run_id':self.run.name}}))
        self.review={'tested_commit':COMMIT,'screenshots':[]}
        for name in ('home.png','about.png','about-landscape.png','fit.png'):
            (native/name).write_bytes(b'synthetic screenshot '+name.encode())
            self.review['screenshots'].append({'name':name,'reviewed':True,'observation':'Synthetic reporter fixture.',
                'sha256':report_local.sha(native/name)})
        self.save()
        self.git=patch.object(report_local.subprocess,'check_output',side_effect=self.git_output)
        self.git.start()
        self.addCleanup(self.git.stop);self.addCleanup(self.directory.cleanup)
        self.changed=[]
    def git_output(self,args,**kwargs):
        if args[1]=='status':return getattr(self,'dirty','')
        if args[1]=='rev-parse':return COMMIT
        if args[1]=='diff':return '\n'.join(self.changed)
        raise AssertionError(args)
    def save(self):
        (self.run/'run.json').write_text(json.dumps(self.state))
        (self.run/'screenshots-reviewed.json').write_text(json.dumps(self.review))
        files={str(p.relative_to(self.run)):{'bytes':p.stat().st_size,'sha256':report_local.sha(p)}
            for p in self.run.rglob('*') if p.is_file() and p.name!='files.json'}
        (self.run/'files.json').write_text(json.dumps(files))
    def validate(self):return report_local.validate(self.run,ROOT)
    def reject(self):
        with self.assertRaises((AssertionError,KeyError,FileNotFoundError)):self.validate()
    def test_exact_library_reuse_provenance_and_failed_gate_exclusion(self):
        before='b'*40
        completed=self.inherited_plan[:36]
        proof=dict(from_commit=before,to_commit=COMMIT,completed_before_adoption=completed)
        self.state['launcher_fix_reuse']=[proof]
        self.state['attempts'][0]['tested_commit']=before
        changes=['tools/android_headless/tests/test_library.py','android/ci/local_verification.py','android/ci/test_inspector_plan.py']
        def git_output(args,**kwargs):
            if args[1]=='diff': return '\n'.join(changes) if args[-2]==before else ''
            if args[1]=='show': return 'def plan(): pass\ndef host(): pass\ndef build(): pass\ndef execute(): pass\n'
            return self.git_output(args,**kwargs)
        self.save()
        with patch.object(report_local.subprocess,'check_output',side_effect=git_output):
            with patch('local_verification.pending_inspector_library_copy_fix') as guard:
                self.validate()
                guard.assert_called_once_with(ROOT,before,COMMIT,completed)
            with patch('local_verification.pending_inspector_library_copy_fix',side_effect=AssertionError): self.reject()
            self.state['attempts'][36]['tested_commit']=before; self.save()
            with patch('local_verification.pending_inspector_library_copy_fix'): self.reject()

    def test_c03_reuse_chain_preserves_every_gate_membership(self):
        library='fb35ca91c6cd73e3e9ecd71037984d2d3da268a5'
        booster='750e4a7df002a44a9da6f907176e974c0bd2627b'
        metadata='e9a2baa24c4eed986673ebf0e2da0ef4e07bfc87'
        first=self.inherited_plan[:36];second=self.inherited_plan[:55];third=self.inherited_plan[:79]
        changes=['tools/android_headless/tests/test_library.py']
        state=dict(commit=COMMIT,launcher_fix_reuse=[
            dict(from_commit=library,to_commit=booster,completed_before_adoption=first,
                 changed_files=changes,unchanged_completed_host_build_inputs=True),
            dict(from_commit=booster,to_commit=metadata,completed_before_adoption=second,
                 changed_files=changes,unchanged_completed_host_build_inputs=True),
            dict(from_commit=metadata,to_commit=COMMIT,completed_before_adoption=third,
                 changed_files=changes,unchanged_completed_host_build_inputs=True)])
        def git_output(args,**kwargs):
            if args[1]=='diff': return '\n'.join(changes)
            if args[1]=='show': return 'def plan(): pass\ndef host(): pass\ndef build(): pass\ndef execute(): pass\n'
            raise AssertionError(args)
        with patch.object(report_local.subprocess,'check_output',side_effect=git_output), \
                patch('local_verification.pending_inspector_library_copy_fix') as a, \
                patch('local_verification.pending_inspector_booster_history_fix') as b, \
                patch('local_verification.pending_inspector_context_metadata_fix') as c:
            checked=set()
            self.assertTrue(report_local.validate_c03_host_reuse(ROOT,state,first[0],library,checked))
            a.assert_called_once_with(ROOT,library,booster,first)
            b.assert_called_once_with(ROOT,booster,metadata,second)
            c.assert_called_once_with(ROOT,metadata,COMMIT,third)
            # Source checks are cached; membership checks remain mandatory.
            for gate,source in ((self.inherited_plan[36],library),(self.inherited_plan[55],booster),(self.inherited_plan[79],metadata)):
                with self.assertRaises(AssertionError): report_local.validate_c03_host_reuse(ROOT,state,gate,source,checked)
            state['launcher_fix_reuse'][1]['unchanged_completed_host_build_inputs']=False
            with self.assertRaises(AssertionError): report_local.validate_c03_host_reuse(ROOT,state,first[0],library,checked)
            state['launcher_fix_reuse'].pop()
            with self.assertRaises(AssertionError): report_local.validate_c03_host_reuse(ROOT,state,first[0],library,set())

    def test_valid_local_receipt(self):
        state,head=self.validate();self.assertEqual(head,COMMIT);self.assertEqual(state['status'],'passed')
    def test_failed_status(self):
        self.state['status']='failed';self.save();self.reject()
    def test_missing_gate(self):
        self.state['completed'].pop();self.save();self.reject()
    def test_inspector_reference_only_plan_cannot_publish(self):
        current=self.inherited_plan+['reference:inspector_attributes','headless:inspector_attributes']
        self.state['plan']=current;self.state['completed']=current.copy();self.save()
        with patch('local_verification.plan',return_value=current):self.reject()
    def test_failed_latest_attempt(self):
        self.state['attempts'].append(dict(self.state['attempts'][0],exit_code=1));self.save();self.reject()
    def test_modified_log(self):
        (self.run/'gate.log').write_bytes(b'changed log');self.reject()
    def test_wrong_log_digest_even_with_manifest(self):
        self.state['attempts'][0]['log_sha256']='0'*64;self.save();self.reject()
    def test_unreviewed_screenshot(self):
        self.review['screenshots'][0]['reviewed']=False;self.save();self.reject()
    def test_missing_screenshot_review(self):
        self.review['screenshots'].pop();self.save();self.reject()
    def test_wrong_review_hash(self):
        self.review['screenshots'][0]['sha256']='0'*64;self.save();self.reject()
    def test_wrong_native_revision(self):
        p=self.run/'native/native-summary.json';s=json.loads(p.read_text());s['checkout_sha']='b'*40;p.write_text(json.dumps(s))
        self.save();self.reject()
    def test_cannot_claim_actions(self):
        self.state['hosted_actions_pass']=True;self.save();self.reject()
    def test_product_input_change(self):
        self.changed=['android_bridge/engine.py'];self.reject()
    def test_docs_only_equivalence(self):
        self.changed=['docs/android/STATUS.md','.github/workflows/android.yml'];self.validate()
    def test_dirty_checkout(self):
        self.dirty=' M android/app/src/main/Example.kt';self.reject()
    def test_native_revision_cannot_be_relabelled(self):
        self.state['attempts'][-1]['tested_commit']='b'*40;self.save();self.reject()
    def test_host_reuse_rejects_changed_product_inputs(self):
        self.state['attempts'][0]['tested_commit']='b'*40;self.changed=['android_bridge/engine.py'];self.save();self.reject()
    def test_timeout_exception_rejects_every_other_history_change(self):
        self.state['attempts'][0]['tested_commit']='b'*40
        self.changed=['android/ci/check-history.py'];self.save()
        before='import json\noutput=adb(timeout=900)\nassert result\n'
        approved=before.replace('import json\n','import json\nimport os\n',1).replace('timeout=900)',"timeout=2400 if os.name == 'nt' else 900)",1)
        def output(args,**kwargs):
            if args[1]=='show': return before if args[2].startswith('b'*40) else self.changed_history
            return self.git_output(args,**kwargs)
        for changed in (approved.replace('assert result','assert True'),
                approved.replace('2400','2401'),approved+'import os\n'):
            self.changed_history=changed
            with self.subTest(change=changed),patch.object(report_local.subprocess,'check_output',side_effect=output):
                self.reject()
    def test_missing_required_manifest_entry(self):
        p=self.run/'files.json';s=json.loads(p.read_text());s.pop('run.json');p.write_text(json.dumps(s));self.reject()


from native_suite import initial_junit
SUCCESS_OUTPUT='INSTRUMENTATION_STATUS: class=io.github.sussic.pyfa.AppShellTest\nINSTRUMENTATION_STATUS: current=1\nINSTRUMENTATION_STATUS: id=AndroidJUnitRunner\nINSTRUMENTATION_STATUS: numtests=5\nINSTRUMENTATION_STATUS: stream=\nio.github.sussic.pyfa.AppShellTest:\nINSTRUMENTATION_STATUS: test=aboutSurvivesActivityRecreationAndLandscapeWithSystemBack\nINSTRUMENTATION_STATUS_CODE: 1\nINSTRUMENTATION_STATUS: class=io.github.sussic.pyfa.AppShellTest\nINSTRUMENTATION_STATUS: current=1\nINSTRUMENTATION_STATUS: id=AndroidJUnitRunner\nINSTRUMENTATION_STATUS: numtests=5\nINSTRUMENTATION_STATUS: stream=.\nINSTRUMENTATION_STATUS: test=aboutSurvivesActivityRecreationAndLandscapeWithSystemBack\nINSTRUMENTATION_STATUS_CODE: 0\nINSTRUMENTATION_STATUS: class=io.github.sussic.pyfa.AppShellTest\nINSTRUMENTATION_STATUS: current=2\nINSTRUMENTATION_STATUS: id=AndroidJUnitRunner\nINSTRUMENTATION_STATUS: numtests=5\nINSTRUMENTATION_STATUS: stream=\nINSTRUMENTATION_STATUS: test=offlineLaunchShowsHonestStatusAndNavigatesBack\nINSTRUMENTATION_STATUS_CODE: 1\nINSTRUMENTATION_STATUS: class=io.github.sussic.pyfa.AppShellTest\nINSTRUMENTATION_STATUS: current=2\nINSTRUMENTATION_STATUS: id=AndroidJUnitRunner\nINSTRUMENTATION_STATUS: numtests=5\nINSTRUMENTATION_STATUS: stream=.\nINSTRUMENTATION_STATUS: test=offlineLaunchShowsHonestStatusAndNavigatesBack\nINSTRUMENTATION_STATUS_CODE: 0\nINSTRUMENTATION_STATUS: class=io.github.sussic.pyfa.EngineParityTest\nINSTRUMENTATION_STATUS: current=3\nINSTRUMENTATION_STATUS: id=AndroidJUnitRunner\nINSTRUMENTATION_STATUS: numtests=5\nINSTRUMENTATION_STATUS: stream=\nio.github.sussic.pyfa.EngineParityTest:\nINSTRUMENTATION_STATUS: test=projectedEffectsMatchDesktopAndRefreshAllRecipientsOffline\nINSTRUMENTATION_STATUS_CODE: 1\nINSTRUMENTATION_STATUS: class=io.github.sussic.pyfa.EngineParityTest\nINSTRUMENTATION_STATUS: current=3\nINSTRUMENTATION_STATUS: id=AndroidJUnitRunner\nINSTRUMENTATION_STATUS: numtests=5\nINSTRUMENTATION_STATUS: stream=.\nINSTRUMENTATION_STATUS: test=projectedEffectsMatchDesktopAndRefreshAllRecipientsOffline\nINSTRUMENTATION_STATUS_CODE: 0\nINSTRUMENTATION_STATUS: class=io.github.sussic.pyfa.EngineParityTest\nINSTRUMENTATION_STATUS: current=4\nINSTRUMENTATION_STATUS: id=AndroidJUnitRunner\nINSTRUMENTATION_STATUS: numtests=5\nINSTRUMENTATION_STATUS: stream=\nINSTRUMENTATION_STATUS: test=commandBurstsMatchDesktopAndClearRecipientBonusesOffline\nINSTRUMENTATION_STATUS_CODE: 1\nINSTRUMENTATION_STATUS: class=io.github.sussic.pyfa.EngineParityTest\nINSTRUMENTATION_STATUS: current=4\nINSTRUMENTATION_STATUS: id=AndroidJUnitRunner\nINSTRUMENTATION_STATUS: numtests=5\nINSTRUMENTATION_STATUS: stream=.\nINSTRUMENTATION_STATUS: test=commandBurstsMatchDesktopAndClearRecipientBonusesOffline\nINSTRUMENTATION_STATUS_CODE: 0\nINSTRUMENTATION_STATUS: class=io.github.sussic.pyfa.EngineParityTest\nINSTRUMENTATION_STATUS: current=5\nINSTRUMENTATION_STATUS: id=AndroidJUnitRunner\nINSTRUMENTATION_STATUS: numtests=5\nINSTRUMENTATION_STATUS: stream=\nINSTRUMENTATION_STATUS: test=bundledEngineMatchesIndependentDesktopAmmunitionStatesOffline\nINSTRUMENTATION_STATUS_CODE: 1\nINSTRUMENTATION_STATUS: class=io.github.sussic.pyfa.EngineParityTest\nINSTRUMENTATION_STATUS: current=5\nINSTRUMENTATION_STATUS: id=AndroidJUnitRunner\nINSTRUMENTATION_STATUS: numtests=5\nINSTRUMENTATION_STATUS: stream=.\nINSTRUMENTATION_STATUS: test=bundledEngineMatchesIndependentDesktopAmmunitionStatesOffline\nINSTRUMENTATION_STATUS_CODE: 0\nINSTRUMENTATION_RESULT: stream=\n\nTime: 45.178\n\nOK (5 tests)\n\n\nINSTRUMENTATION_CODE: -1\n'

class InitialRunnerResultTest(unittest.TestCase):
    def test_actual_android_runner_output(self):
        self.assertEqual(initial_junit(SUCCESS_OUTPUT).count(b'<testcase'),5)
    def test_failed_incomplete_and_duplicate_results(self):
        bad=[SUCCESS_OUTPUT.replace('OK (5 tests)','OK (4 tests)'),
            SUCCESS_OUTPUT.replace('INSTRUMENTATION_CODE: -1','INSTRUMENTATION_CODE: 0'),
            SUCCESS_OUTPUT.replace('INSTRUMENTATION_STATUS_CODE: 0','INSTRUMENTATION_STATUS_CODE: -2',1),
            SUCCESS_OUTPUT.replace('numtests=5','numtests=4',1),
            SUCCESS_OUTPUT.replace('current=1','current=2',1),
            SUCCESS_OUTPUT.replace('aboutSurvivesActivityRecreationAndLandscapeWithSystemBack','unknown'),
            SUCCESS_OUTPUT.replace('INSTRUMENTATION_STATUS_CODE: 0','INSTRUMENTATION_STATUS_CODE: 1',1),
            SUCCESS_OUTPUT+'\nINSTRUMENTATION_FAILED: process crash',
            SUCCESS_OUTPUT+'\nINSTRUMENTATION_CODE: -1',
            SUCCESS_OUTPUT[SUCCESS_OUTPUT.find('INSTRUMENTATION_STATUS: class=',80):]]
        for i,value in enumerate(bad):
            with self.subTest(corruption=i):
                with self.assertRaises((AssertionError,KeyError,ValueError)):initial_junit(value)

class PendingCountCorrectionTest(unittest.TestCase):
    def test_only_exact_unexecuted_suite_count_change_is_accepted(self):
        from local_verification import pending_mutation_count_fix
        before = 'if result.testsRun != (2 if args.matrix_only else 22) or not result.wasSuccessful():\n    raise RuntimeError()\n'
        after = before.replace('else 22', 'else 23')
        with patch.object(report_local.subprocess, 'check_output', side_effect=[before, after]):
            pending_mutation_count_fix(ROOT, 'before', 'after', ['desktop:reference'])
        for bad in (after.replace('23', '24'), after.replace('not result.wasSuccessful()', 'False'), after + 'extra = True\n'):
            with patch.object(report_local.subprocess, 'check_output', side_effect=[before, bad]):
                with self.assertRaises(AssertionError): pending_mutation_count_fix(ROOT, 'before', 'after', [])
    def test_already_executed_suite_cannot_be_reused(self):
        from local_verification import pending_mutation_count_fix
        with self.assertRaises(AssertionError):
            pending_mutation_count_fix(ROOT, 'before', 'after', ['headless:history_mutations'])

if __name__=='__main__':unittest.main()
