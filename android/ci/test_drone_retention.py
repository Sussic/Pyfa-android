"""Filesystem safety and real process-budget tests; no Android/emulator execution."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import artifact_retention as retention
import drone_delivery


class RetentionCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)/'run-123'; self.root.mkdir()
        self.state=dict(status='passed',plan=['native:synthetic'],completed=['native:synthetic'],
                        attempts=[dict(gate='native:synthetic',exit_code=0)])
        (self.root/'report.json').write_text('{"verified":true}')
    def tearDown(self):
        self.temp.cleanup()
    def runtime(self,relative):
        name='pyfa-local-'+self.root.name
        if relative!='avd':
            name+='-r'+relative.split('-r')[1]
            if relative.startswith('avd-c04-'): name+='-c04'
        folder=self.root/relative; folder.mkdir()
        guest=folder/(name+'.avd');guest.mkdir()
        (guest/'userdata.img').write_bytes(b'owned synthetic guest')
        (folder/(name+'.ini')).write_text('path='+str(guest.resolve())+'\n')
        retention.register_runtime(self.state,self.root,folder,name)
        return folder
    def seal(self):
        (self.root/'run.json').write_text(json.dumps(self.state))
        files={}
        for p in self.root.iterdir():
            if p.is_file() and p.name!='files.json':
                files[p.name]=dict(bytes=p.stat().st_size,sha256=retention.digest(p))
        (self.root/'files.json').write_text(json.dumps(files))
    def test_cleans_all_owned_roots_and_preserves_exact_reports(self):
        roots=[self.runtime(name) for name in ('avd','avd-r1','avd-c04-r0','avd-c04-r2')]
        (self.root/'avd-c04-r0-evidence').mkdir()
        self.seal()
        before={p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        result=retention.cleanup_verified_runtime(self.root,stopped=True)
        self.assertEqual(4,len(result['removed']))
        self.assertTrue(all(not p.exists() for p in roots))
        self.assertTrue((self.root/'avd-c04-r0-evidence').is_dir())
        for name,raw in before.items():
            if name!='files.json': self.assertEqual(raw,(self.root/name).read_bytes())
        self.assertIn('runtime-cleanup.json',json.loads((self.root/'files.json').read_text()))
        self.assertEqual([],retention.cleanup_verified_runtime(self.root,stopped=True)['removed'])
    def test_failed_paused_running_and_incomplete_runs_keep_runtime(self):
        for state in ('failed','paused','running','pending'):
            with self.subTest(state=state):
                self.state['status']=state
                if not (self.root/'avd').exists(): self.runtime('avd')
                self.seal()
                with self.assertRaises(retention.RetentionError):
                    retention.cleanup_verified_runtime(self.root,stopped=True)
                self.assertTrue((self.root/'avd').exists())
        self.state['status']='passed'; self.state['completed']=[];self.seal()
        with self.assertRaises(retention.RetentionError): retention.cleanup_verified_runtime(self.root,stopped=True)
    def test_live_emulator_and_failed_gate_prevent_cleanup(self):
        root=self.runtime('avd');self.seal()
        with self.assertRaises(retention.RetentionError): retention.cleanup_verified_runtime(self.root,stopped=False)
        self.state['attempts'][0]['exit_code']=1;self.seal()
        with self.assertRaises(retention.RetentionError): retention.cleanup_verified_runtime(self.root,stopped=True)
        self.assertTrue(root.exists())
    def test_corrupt_or_missing_evidence_keeps_every_runtime(self):
        roots=[self.runtime('avd'),self.runtime('avd-c04-r0')];self.seal()
        (self.root/'report.json').write_text('changed')
        with self.assertRaises(retention.RetentionError): retention.cleanup_verified_runtime(self.root,stopped=True)
        self.assertTrue(all(p.exists() for p in roots))
        (self.root/'report.json').unlink()
        with self.assertRaises((retention.RetentionError,FileNotFoundError)): retention.cleanup_verified_runtime(self.root,stopped=True)
    def test_unregistered_runtime_blocks_all_cleanup(self):
        root=self.runtime('avd');self.seal();(self.root/'avd-c04-r9').mkdir()
        with self.assertRaises(retention.RetentionError): retention.cleanup_verified_runtime(self.root,stopped=True)
        self.assertTrue(root.exists())
    def test_foreign_child_or_external_locator_preserves_all_roots(self):
        root=self.runtime('avd'); other=self.runtime('avd-c04-r0');self.seal()
        (other/'unrelated.txt').write_text('preserve')
        with self.assertRaises(retention.RetentionError): retention.cleanup_verified_runtime(self.root,stopped=True)
        self.assertTrue(root.exists())
        (other/'unrelated.txt').unlink()
        next(other.glob('*.ini')).write_text('path='+str(Path(self.temp.name))+'\n')
        with self.assertRaises(retention.RetentionError): retention.cleanup_verified_runtime(self.root,stopped=True)
        self.assertTrue(root.exists())
    def test_path_escape_and_wrong_identity_are_rejected(self):
        for relative in ('../avd','native','avd-c04-r0-evidence'):
            with self.subTest(relative=relative),self.assertRaises(retention.RetentionError):
                retention.register_runtime(self.state,self.root,self.root/relative,'pyfa-local-run-123')
    def test_runtime_referenced_by_manifest_is_preserved(self):
        root=self.runtime('avd');self.seal()
        p=next(root.glob('*.avd'))/'userdata.img'
        files=json.loads((self.root/'files.json').read_text())
        files[p.relative_to(self.root).as_posix()]=dict(bytes=p.stat().st_size,sha256=retention.digest(p))
        (self.root/'files.json').write_text(json.dumps(files))
        with self.assertRaises(retention.RetentionError): retention.cleanup_verified_runtime(self.root,stopped=True)
        self.assertTrue(p.exists())
    def test_real_junction_or_symlink_never_deletes_target(self):
        root=self.runtime('avd');self.seal()
        external=Path(self.temp.name)/'unrelated';external.mkdir()
        protected=external/'keep.txt';protected.write_text('do not remove')
        link=next(root.glob('*.avd'))/'redirect'
        if os.name=='nt':
            result=subprocess.run(['cmd','/c','mklink','/J',str(link),str(external)],capture_output=True)
            self.assertEqual(0,result.returncode,result.stderr)
        else: link.symlink_to(external,target_is_directory=True)
        with self.assertRaises(retention.RetentionError): retention.cleanup_verified_runtime(self.root,stopped=True)
        self.assertEqual('do not remove',protected.read_text())
        self.assertTrue(root.exists())
    def test_retry_runtime_is_excluded_but_proof_folder_is_not(self):
        for relative in ('avd/data','avd-r2/data','avd-c04-r3/data'):
            self.assertTrue(drone_delivery.is_emulator_data(self.root,self.root/relative))
        self.assertFalse(drone_delivery.is_emulator_data(self.root,self.root/'avd-r2-evidence/proof.json'))
    def test_new_report_requires_hash_bound_cleanup_but_old_report_is_unchanged(self):
        retention.validate_cleanup_receipt(self.root,self.state,{})
        self.state['artifact_retention']={'version':1}
        self.runtime('avd');self.seal()
        with self.assertRaises(retention.RetentionError): retention.validate_cleanup_receipt(self.root,self.state,{})
        retention.cleanup_verified_runtime(self.root,stopped=True)
        manifest=json.loads((self.root/'files.json').read_text())
        retention.validate_cleanup_receipt(self.root,self.state,manifest)
        (self.root/'avd').mkdir()
        with self.assertRaises(retention.RetentionError): retention.validate_cleanup_receipt(self.root,self.state,manifest)
    def test_isolated_launcher_entrypoint_keeps_all_190_gates(self):
        output=subprocess.check_output([sys.executable,'-I','-B',str(Path(__file__).parent/'local_verification.py'),'plan','--mode','full'],text=True)
        self.assertEqual(190,len(output.strip().splitlines()))


class ArtifactBudgetTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'nt', 'Windows extended-path allocated-byte accounting')
    def test_allocated_usage_includes_restored_long_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=retention.filesystem_path(Path(directory).resolve()/'long-root')
            try:
                nested=root
                for index in range(12):
                    nested=nested/('retained-directory-'+str(index))
                nested.mkdir(parents=True)
                (nested/'proof.bin').write_bytes(b'long-path-proof'*2048)
                ordinary=Path(directory)/'long-root'
                result=retention.usage([ordinary,ordinary])
                self.assertEqual(1,result['files'])
                self.assertGreater(result['allocated_bytes'],0)
            finally:
                self.assertEqual(Path(str(root)[4:]).resolve(),(Path(directory)/'long-root').resolve())
                shutil.rmtree(root)

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
    def tearDown(self):
        self.temp.cleanup()
    def test_combined_roots_count_and_hardlinks_do_not_double_count(self):
        a=self.root/'one';a.mkdir();b=self.root/'two';b.mkdir()
        p=a/'data';p.write_bytes(b'x'*8192)
        initial=retention.usage([a])['allocated_bytes']
        os.link(p,b/'same-bytes')
        self.assertEqual(initial,retention.usage([a,a,b])['allocated_bytes'])
        (b/'different').write_bytes(b'y'*8192)
        with self.assertRaises(retention.RetentionError):
            retention.ArtifactBudget([a,b],limit=initial,minimum_free=0).check()
    def test_copy_reservation_refuses_before_any_output_or_deletion(self):
        p=self.root/'original';p.write_bytes(b'x'*8192)
        amount=retention.usage([self.root])['allocated_bytes']
        budget=retention.ArtifactBudget([self.root],limit=amount-1,minimum_free=0)
        with self.assertRaises(retention.RetentionError): budget.copy(p,self.root/'copy')
        self.assertFalse((self.root/'copy').exists());self.assertEqual(8192,p.stat().st_size)
    def test_budget_rejects_unreviewed_limit_increase(self):
        with self.assertRaises(retention.RetentionError):
            retention.ArtifactBudget([self.root],limit=retention.load_policy()[0]['storage']['project_prompt_threshold_bytes']+1)
    def test_live_growth_stops_owned_parent_and_descendant_without_truncation(self):
        import time
        output=self.root/'grown.bin';pidfile=self.root/'child.pid';log=self.root/'output.log'
        ready=self.root/'write-complete'
        script=("import pathlib,subprocess,sys,time;"
                "p=subprocess.Popen([sys.executable,'-I','-B','-c','import time;time.sleep(30)']);"
                f"pathlib.Path({str(pidfile)!r}).write_text(str(p.pid));"
                f"pathlib.Path({str(output)!r}).write_bytes(b'x'*2097152);"
                f"pathlib.Path({str(ready)!r}).touch();"
                "time.sleep(30)")
        budget=retention.ArtifactBudget([self.root],limit=1024*1024,minimum_free=0,interval=.05)
        original_usage = retention.usage
        preflight = True
        def after_complete_write(roots):
            nonlocal preflight
            if preflight:
                preflight = False
            else:
                # This fixture checks preservation of a completed write. Without
                # a barrier the guard may correctly kill it mid-write instead.
                deadline = time.monotonic() + 5
                while not ready.exists():
                    if time.monotonic() >= deadline:
                        self.fail('Synthetic output write did not complete')
                    time.sleep(.01)
            return original_usage(roots)
        with log.open('wb') as stream, patch.object(retention, 'usage', side_effect=after_complete_write), self.assertRaises(retention.RetentionError):
            budget.run([sys.executable,'-I','-B','-c',script],stdout=stream,stderr=subprocess.STDOUT,timeout=10)
        self.assertEqual(2097152,output.stat().st_size,'Budget enforcement must not truncate failed output')
        pid=int(pidfile.read_text())
        if os.name=='nt':
            import ctypes
            from ctypes import wintypes
            k=ctypes.WinDLL('kernel32',use_last_error=True)
            k.OpenProcess.restype=wintypes.HANDLE
            k.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
            k.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
            k.CloseHandle.argtypes=[wintypes.HANDLE]
            handle=k.OpenProcess(0x1000,False,pid)
            if handle:
                code=wintypes.DWORD()
                self.assertTrue(k.GetExitCodeProcess(handle,ctypes.byref(code)))
                k.CloseHandle(handle);self.assertNotEqual(259,code.value)
    @unittest.skipUnless(sys.platform.startswith('linux'), 'Descendant proof uses Linux pidfds')
    def test_exited_parent_still_stops_its_owned_descendant(self):
        import select
        import signal

        if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
            self.skipTest('Linux pidfd APIs and kernel support are required for this regression')
        for exit_code in (0, 7):
            with self.subTest(exit_code=exit_code):
                pidfile = self.root / f'exited-{exit_code}.pid'
                release = self.root / f'exited-{exit_code}.release'
                script = (
                    "import pathlib,subprocess,sys,time\n"
                    "child=subprocess.Popen([sys.executable,'-I','-B','-c',"
                    "'import signal;signal.pause()'])\n"
                    f"pidfile=pathlib.Path({str(pidfile)!r})\n"
                    "pending=pidfile.with_suffix('.tmp')\n"
                    "pending.write_text(str(child.pid));pending.replace(pidfile)\n"
                    f"while not pathlib.Path({str(release)!r}).exists(): time.sleep(.01)\n"
                    f"print('parent completed');sys.exit({exit_code})\n"
                )
                foreign = subprocess.Popen(
                    [sys.executable, '-I', '-B', '-c', 'import time;time.sleep(30)'],
                    start_new_session=True,
                )
                child_fd = None
                original_usage = retention.usage
                def bind_child_before_parent_exit(roots):
                    nonlocal child_fd
                    if pidfile.exists() and child_fd is None:
                        # The original parent keeps its child unreaped behind a
                        # barrier until this identity-safe cleanup handle exists.
                        child_fd = os.pidfd_open(int(pidfile.read_text()))
                        release.touch()
                    return original_usage(roots)
                try:
                    log_path = self.root / f'exited-{exit_code}.log'
                    with log_path.open('wb') as log, patch.object(
                            retention, 'usage', side_effect=bind_child_before_parent_exit):
                        result = retention.ArtifactBudget(
                            [self.root], limit=1024*1024, minimum_free=0, interval=.05,
                        ).run([sys.executable, '-I', '-B', '-c', script],
                              stdout=log, stderr=subprocess.STDOUT, timeout=5)
                    self.assertEqual(exit_code, result.returncode)
                    self.assertIn('parent completed', log_path.read_text())
                    self.assertIsNone(foreign.poll(), 'Unrelated process must remain running')
                    self.assertIsNotNone(child_fd)
                    self.assertTrue(select.select([child_fd], [], [], 2)[0],
                                    'Owned descendant is still running')
                finally:
                    if child_fd is not None:
                        try:
                            signal.pidfd_send_signal(child_fd, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        finally:
                            os.close(child_fd)
                    foreign.kill()
                    foreign.wait()

    def test_resume_keeps_external_roots_without_reviving_prior_limit(self):
        prior=self.root/'prior';prior.mkdir();(prior/'data').write_bytes(b'x'*8192)
        current=self.root/'current';current.mkdir()
        budget=retention.ArtifactBudget([current],limit=32768,minimum_free=0)
        budget.include_previous(dict(version=1,roots=[str(prior)],limit_bytes=4096))
        self.assertIn(str(prior.resolve()),budget.roots)
        self.assertEqual(32768,budget.limit)
        self.assertEqual(4096,budget.historical_policies[0]['limit_bytes'])
        budget.check()
        for policy in ({'version':3},dict(version=1,roots=['relative'],limit_bytes=4096)):
            with self.assertRaises(retention.RetentionError): budget.include_previous(policy)
    def test_timeout_is_not_extended_to_storage_poll_interval(self):
        with (self.root/'log').open('wb') as log,self.assertRaises(subprocess.TimeoutExpired):
            retention.ArtifactBudget([self.root],limit=1024*1024,minimum_free=0,interval=5).run(
                [sys.executable,'-I','-B','-c','import time;time.sleep(2)'],
                stdout=log,stderr=subprocess.STDOUT,timeout=.1)
    def test_ordinary_success_preserves_output(self):
        with (self.root/'log').open('wb') as log:
            result=retention.ArtifactBudget([self.root],limit=1024*1024,minimum_free=0,interval=.05).run(
                [sys.executable,'-I','-B','-c','print("passed")'],stdout=log,stderr=subprocess.STDOUT,timeout=10)
        self.assertEqual(0,result.returncode)
        self.assertIn('passed',(self.root/'log').read_text())


@unittest.skipUnless(sys.platform.startswith('linux'), 'Lifecycle proof uses Linux waitid')
class OwnedPosixLifecycleTests(unittest.TestCase):
    def command(self, code, log):
        return retention.OwnedCommand(
            [sys.executable, '-I', '-B', '-c', code], cwd=None,
            stdout=log, stderr=subprocess.STDOUT, input=None,
        )

    def test_wait_keeps_leader_reserved_until_group_signal(self):
        import signal

        cases = [('raise SystemExit(0)', 0), ('raise SystemExit(7)', 7),
                 ('import os,signal;os.kill(os.getpid(),signal.SIGTERM)', -signal.SIGTERM)]
        for code, expected in cases:
            with self.subTest(expected=expected), tempfile.TemporaryFile() as log:
                original = os.killpg
                signalled = []
                owned = self.command(code, log)
                def verify_then_signal(pgid, sig):
                    # This proof is made at the signal boundary, after wait and
                    # repeated poll. A reaped/reusable leader fails before killpg.
                    status = os.waitid(os.P_PID, pgid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                    self.assertIsNotNone(status)
                    self.assertEqual(owned.process.pid, status.si_pid)
                    self.assertEqual(expected, status.si_status if status.si_code == os.CLD_EXITED else -status.si_status)
                    signalled.append(pgid)
                    return original(pgid, sig)
                with patch.object(retention.os, 'killpg', side_effect=verify_then_signal):
                    with owned:
                        self.assertEqual(expected, owned.wait(5))
                        self.assertEqual(expected, owned.poll())
                        self.assertEqual(expected, owned.poll())
                    self.assertEqual(expected, owned.process.returncode)
                    owned.__exit__(None, None, None)
                self.assertEqual([owned.process.pid], signalled)
                with self.assertRaises(ChildProcessError):
                    os.waitid(os.P_PID, owned.process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)

    def test_external_reap_refuses_group_signal(self):
        with tempfile.TemporaryFile() as log:
            owned = self.command('raise SystemExit(0)', log)
            self.assertEqual(0, owned.process.wait(timeout=5))
            with patch.object(retention.os, 'killpg') as kill:
                with self.assertRaisesRegex(retention.RetentionError, 'reaped'):
                    owned.__exit__(None, None, None)
                kill.assert_not_called()

    def test_missing_non_reaping_support_refuses_before_spawn(self):
        with patch.dict(os.__dict__), patch.object(retention.subprocess, 'Popen') as spawn:
            del os.WNOWAIT
            with self.assertRaisesRegex(retention.RetentionError, 'non-reaping waitid'):
                self.command('raise SystemExit(0)', None)
            spawn.assert_not_called()

    def test_external_sigchld_handler_refuses_before_spawn(self):
        import signal

        with patch.object(signal, 'getsignal', return_value=signal.SIG_IGN), \
                patch.object(retention.subprocess, 'Popen') as spawn:
            with self.assertRaisesRegex(retention.RetentionError, 'SIGCHLD'):
                self.command('raise SystemExit(0)', None)
            spawn.assert_not_called()


if __name__=='__main__':
    unittest.main()

