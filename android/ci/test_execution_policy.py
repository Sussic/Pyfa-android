"""Current policy admission and migration tests; no product/Android execution."""
import copy
from contextlib import redirect_stderr
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import artifact_retention as retention
import local_verification
import drone_delivery
import policy_host_metrics
from execution_policy import (AdmissionDeferred, POLICY_PATH, PolicyError,
                              PressureWindow, admit, load_policy, select,
                              storage_prompt_required, project_usage)


class ExecutionPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy,self.digest=load_policy()
        self.settings=select(self.policy,'initia','focused_test')

    @unittest.skipUnless(os.name == 'nt', 'Windows extended-path accounting')
    def test_project_accounting_includes_restored_long_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path('\\\\?\\' + str(Path(directory).resolve()))
            try:
                nested = root
                for index in range(12):
                    nested = nested / ('retained-directory-' + str(index))
                nested.mkdir(parents=True)
                (nested / 'contract.txt').write_bytes(b'long-path-proof')
                policy=copy.deepcopy(self.policy)
                policy['storage']['accounting_roots']=[directory,directory]
                self.assertEqual(len(b'long-path-proof'),project_usage(policy,Path(directory),'initia'))
            finally:
                self.assertEqual(Path(str(root)[4:]).resolve(),Path(directory).resolve())
                shutil.rmtree(root)

    def test_project_accounting_refuses_unreadable_declared_root(self):
        policy=copy.deepcopy(self.policy)
        policy['storage']['accounting_roots']=['{repository}']
        with patch.object(Path,'stat',side_effect=PermissionError('denied-root')):
            with self.assertRaisesRegex(PolicyError,'Cannot account owned storage root'):
                project_usage(policy,Path.cwd(),'initia')

    def test_project_accounting_requires_no_python312_path_method(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'ordinary-file').write_bytes(b'python311-proof')
            policy=copy.deepcopy(self.policy)
            policy['storage']['accounting_roots']=[directory]
            with patch.object(Path,'is_junction',side_effect=AssertionError('Python3.12-only API'),create=True):
                self.assertEqual(len(b'python311-proof'),project_usage(policy,root,'initia'))

    def test_missing_policy_has_no_historical_default(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PolicyError):
                load_policy(Path(directory)/'missing.json')

    def test_incomplete_policy_rejects_missing_resource_field(self):
        policy=copy.deepcopy(self.policy)
        del policy['hosts']['initia']['ram_reserve_bytes']
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'policy.json'
            path.write_text(json.dumps(policy),encoding='utf-8')
            with self.assertRaises(PolicyError):load_policy(path)

    def test_both_physical_memory_and_commit_must_cover_workload(self):
        required=self.settings['ram_reserve_bytes']+self.settings['estimated_peak_bytes']
        disk=self.settings['disk_free_reserve_bytes']
        self.assertEqual([],admit(self.settings,required,required,disk,0,0))
        self.assertTrue(admit(self.settings,required-1,required,disk,0,0))
        self.assertTrue(admit(self.settings,required,required-1,disk,0,0))

    def test_disk_forecast_is_added_to_host_reserve(self):
        required=self.settings['ram_reserve_bytes']+self.settings['estimated_peak_bytes']
        forecast=29
        disk=self.settings['disk_free_reserve_bytes']+forecast
        self.assertEqual([],admit(self.settings,required,required,disk,forecast,0))
        self.assertTrue(admit(self.settings,required,required,disk-1,forecast,0))

    def test_storage_prompt_uses_actual_project_total_and_strict_exceeds(self):
        threshold=self.policy['storage']['project_prompt_threshold_bytes']
        self.assertFalse(storage_prompt_required(self.policy,threshold))
        self.assertTrue(storage_prompt_required(self.policy,threshold+1))

    def test_worker_count_is_clamped_to_real_logical_processors(self):
        self.assertEqual(1,select(self.policy,'msi','build',logical_cpus=1)['workers'])
        configured=self.policy['hosts']['msi']['cpu_workers']
        self.assertEqual(configured,select(self.policy,'msi','build',logical_cpus=configured+1)['workers'])

    def test_transient_pressure_recovers_and_sustained_pressure_defers(self):
        window=PressureWindow(self.settings)
        floor=self.settings['running_free_floor_bytes']
        grace=self.settings['running_pressure_grace_seconds']
        self.assertFalse(window.sample(0,floor-1,floor))
        self.assertFalse(window.sample(grace-1,floor,floor))
        self.assertFalse(window.sample(grace,floor,floor-1))
        self.assertFalse(window.sample(grace*2-1,floor,floor-1))
        self.assertTrue(window.sample(grace*2,floor,floor-1))

    def test_artifact_budget_reads_current_storage_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            budget=retention.ArtifactBudget([directory],host='initia')
            self.assertEqual(self.policy['storage']['project_prompt_threshold_bytes'],budget.limit)
            self.assertEqual(self.settings['disk_free_reserve_bytes'],budget.minimum_free)
            self.assertEqual(self.digest,budget.policy_sha256)

    def test_legacy_run_roots_survive_without_restoring_their_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            previous=root/'previous';previous.mkdir()
            (previous/'proof').write_text('preserve',encoding='utf-8')
            budget=retention.ArtifactBudget([root/'current'],host='initia',minimum_free=0)
            current=budget.limit
            for version in (1,2):
                budget.include_previous({'version':version,'roots':[str(previous)],'limit_bytes':1})
            self.assertEqual(current,budget.limit)
            self.assertIn(str(previous.resolve()),budget.roots)
            self.assertEqual([1,1],[row['limit_bytes'] for row in budget.historical_policies])
            budget.check()
            self.assertEqual('preserve',(previous/'proof').read_text(encoding='utf-8'))

    def test_forecast_crossing_prompt_threshold_does_not_restore_old_cap(self):
        with tempfile.TemporaryDirectory() as directory:
            budget=retention.ArtifactBudget([directory],host='initia',minimum_free=0)
            threshold=budget.limit
            with patch.object(retention,'usage',return_value={'allocated_bytes':threshold}), \
                    patch.object(retention.shutil,'disk_usage',return_value=SimpleNamespace(free=threshold+1)):
                budget.check(reserve=1)
            with patch.object(retention,'usage',return_value={'allocated_bytes':threshold+1}):
                with self.assertRaises(retention.ResourceDeferred):budget.check()

    def test_copy_forecast_refuses_real_disk_shortage_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source';source.write_bytes(b'payload')
            target=Path(directory)/'copy'
            budget=retention.ArtifactBudget([directory],host='initia')
            with patch.object(retention.shutil,'disk_usage',return_value=SimpleNamespace(free=budget.minimum_free)):
                with self.assertRaises(retention.ResourceDeferred):budget.copy(source,target)
            self.assertFalse(target.exists())
            self.assertEqual(b'payload',source.read_bytes())

    def test_local_verifier_refuses_before_appending_attempt_or_launching_child(self):
        runner=local_verification.Run.__new__(local_verification.Run)
        runner.settings=self.settings
        runner.state={'attempts':[]}
        runner.execution_started=time.monotonic()
        required=self.settings['ram_reserve_bytes']+self.settings['estimated_peak_bytes']
        runner.artifact_budget=SimpleNamespace(check=lambda:None,latest={'allocated_bytes':0})
        runner.directory=Path(tempfile.gettempdir())
        with patch.object(local_verification,'host_memory',return_value=(required,required-1)), \
                patch.object(local_verification.shutil,'disk_usage',return_value=SimpleNamespace(free=self.settings['disk_free_reserve_bytes'])):
            with self.assertRaises(AdmissionDeferred):runner.execute('host:fixture',['never-launched'])
        self.assertEqual([],runner.state['attempts'])

    def test_cli_old_budget_override_is_rejected_before_run_creation(self):
        with patch.object(sys,'argv',['local_verification.py','plan','--artifact-budget-gib','32']), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as stopped:local_verification.main()
        self.assertNotEqual(0,stopped.exception.code)

    def test_current_policy_receipts_keep_required_owned_cleanup_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(retention.RetentionError):
                retention.validate_cleanup_receipt(directory,{'artifact_retention':{'version':2}}, {})

    def test_native_start_uses_policy_memory_and_avd_disk_forecast(self):
        settings=select(self.policy,'msi','full_suite')
        required=settings['ram_reserve_bytes']+settings['estimated_peak_bytes']
        disk=settings['disk_free_reserve_bytes']+self.policy['android_runtime']['new_avd_disk_forecast_bytes']
        with patch.dict('os.environ',{'CODEX_EXECUTION_HOST':'msi'}), \
                patch('execution_policy.detect_host',return_value='msi'), \
                patch.object(policy_host_metrics,'host_memory',return_value=(required,required)), \
                patch.object(drone_delivery.shutil,'disk_usage',return_value=SimpleNamespace(free=disk)):
            result=drone_delivery.admit_native(starting=True)
            self.assertEqual(self.digest,result['policy_sha256'])
            self.assertEqual('full_suite',result['workload'])
        with patch.dict('os.environ',{'CODEX_EXECUTION_HOST':'msi'}), \
                patch('execution_policy.detect_host',return_value='msi'), \
                patch.object(policy_host_metrics,'host_memory',return_value=(required,required-1)), \
                patch.object(drone_delivery.shutil,'disk_usage',return_value=SimpleNamespace(free=disk)):
            with self.assertRaises(AdmissionDeferred):drone_delivery.admit_native(starting=True)

    def test_initia_full_selection_defers_for_msi_before_creating_run(self):
        args=SimpleNamespace(mode='full',gate=None,execution_host='initia')
        with patch.object(local_verification,'detect_host',return_value='initia'):
            with self.assertRaisesRegex(AdmissionDeferred,'durable MSI queue'):
                local_verification.Run(args)


if __name__=='__main__':unittest.main(verbosity=2)
