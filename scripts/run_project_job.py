"""Run one ordinary Windows job using the repository's canonical execution policy."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from uuid import uuid4

if __package__:
    from . import execution_policy as policy_api
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import execution_policy as policy_api


class MemoryStatus(ctypes.Structure):
    _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
        (key, ctypes.c_ulonglong) for key in
        ('total', 'available', 'commit', 'available_commit', 'virtual', 'available_virtual', 'extended')]


class Basic(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', wintypes.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                ('active', wintypes.DWORD), ('affinity', ctypes.c_size_t),
                ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]


class IO(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]


class Extended(ctypes.Structure):
    _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t),
                ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]


class Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int64) for name in ('user', 'kernel', 'period_user', 'period_kernel')] + [
        (name, wintypes.DWORD) for name in ('faults', 'total', 'active', 'terminated')]


def checked(value, action):
    if not value:
        raise OSError(f'Owned job operation failed: {action}')
    return value


class WindowsJob:
    def __init__(self):
        if os.name != 'nt':
            raise policy_api.AdmissionDeferred('Current owned-job runner requires native Windows capability.')
        self.kernel = kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        signatures = {
            'CreateJobObjectW': ((ctypes.c_void_p, wintypes.LPCWSTR), wintypes.HANDLE),
            'SetInformationJobObject': ((wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD), wintypes.BOOL),
            'QueryInformationJobObject': ((wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p), wintypes.BOOL),
            'AssignProcessToJobObject': ((wintypes.HANDLE, wintypes.HANDLE), wintypes.BOOL),
            'ResumeThread': ((wintypes.HANDLE,), wintypes.DWORD),
            'GetExitCodeProcess': ((wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)), wintypes.BOOL),
            'WaitForSingleObject': ((wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD),
            'TerminateJobObject': ((wintypes.HANDLE, wintypes.UINT), wintypes.BOOL),
            'TerminateProcess': ((wintypes.HANDLE, wintypes.UINT), wintypes.BOOL),
            'CloseHandle': ((wintypes.HANDLE,), wintypes.BOOL),
            'GlobalMemoryStatusEx': ((ctypes.POINTER(MemoryStatus),), wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(kernel, name)
            function.argtypes, function.restype = arguments, result
        self.handle = checked(kernel.CreateJobObjectW(None, None), 'create owned job')
        self.process = self.thread = None
        self.assigned = False
        try:
            limits = Extended()
            limits.basic.flags, limits.basic.priority = 0x2020, 0x4000  # Kill-on-close; below-normal.
            checked(kernel.SetInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)), 'configure owned job')
            actual = Extended()
            checked(kernel.QueryInformationJobObject(self.handle, 9, ctypes.byref(actual), ctypes.sizeof(actual), None), 'read job configuration')
            if actual.basic.flags != limits.basic.flags or actual.basic.priority != limits.basic.priority:
                raise OSError('Owned job security/priority readback mismatch.')
            if actual.process_memory or actual.job_memory:
                raise OSError('Admission estimate was unexpectedly installed as a hard memory cap.')
        except BaseException:
            self.close()
            raise

    def resources(self, disk_root):
        memory = MemoryStatus()
        memory.length = ctypes.sizeof(memory)
        checked(self.kernel.GlobalMemoryStatusEx(ctypes.byref(memory)), 'sample physical memory and commit')
        return dict(available_physical=memory.available, available_commit=memory.available_commit,
                    free_disk=shutil.disk_usage(disk_root).free)

    def launch(self, argv, environment, cwd, log):
        import _winapi
        import msvcrt
        with open(os.devnull, 'r+b', buffering=0) as null:
            handles = [msvcrt.get_osfhandle(null.fileno()), msvcrt.get_osfhandle(log.fileno())]
            startup = subprocess.STARTUPINFO()
            startup.dwFlags = subprocess.STARTF_USESTDHANDLES
            startup.hStdInput, startup.hStdOutput, startup.hStdError = handles[0], handles[1], handles[1]
            startup.lpAttributeList = {'handle_list': handles}
            for handle in handles:
                os.set_handle_inheritable(handle, True)
            try:
                self.process, self.thread, self.pid, _ = _winapi.CreateProcess(
                    None, subprocess.list2cmdline(argv), None, None, True,
                    0x4 | 0x08000000, environment, str(cwd), startup)
            finally:
                for handle in handles:
                    os.set_handle_inheritable(handle, False)
        checked(self.kernel.AssignProcessToJobObject(self.handle, self.process), 'assign suspended worker')
        self.assigned = True
        if self.kernel.ResumeThread(self.thread) != 1:
            raise OSError('Owned worker did not resume from its single suspension.')

    def poll(self):
        signal = self.kernel.WaitForSingleObject(self.process, 0)
        if signal == 258:  # WAIT_TIMEOUT: the process handle is not signalled.
            return None
        checked(signal == 0, 'observe owned worker termination')
        code = wintypes.DWORD()
        checked(self.kernel.GetExitCodeProcess(self.process, ctypes.byref(code)), 'read owned worker exit code')
        return code.value  # An exited process may legitimately return 259.

    def active(self):
        info = Accounting()
        checked(self.kernel.QueryInformationJobObject(self.handle, 1, ctypes.byref(info), ctypes.sizeof(info), None), 'read owned descendants')
        return info.active

    def stop(self, code):
        if self.process is not None and not self.assigned and self.poll() is None:
            checked(self.kernel.TerminateProcess(self.process, code), 'stop unassigned suspended worker')
        if self.handle is not None:
            checked(self.kernel.TerminateJobObject(self.handle, code), 'stop owned job only')

    def telemetry(self):
        limits, accounting = Extended(), Accounting()
        checked(self.kernel.QueryInformationJobObject(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits), None), 'read owned peak commit')
        checked(self.kernel.QueryInformationJobObject(self.handle, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None), 'read owned CPU time')
        result = dict(peak_job_commit_bytes=limits.peak_job, peak_process_commit_bytes=limits.peak_process,
                      owned_cpu_seconds=(accounting.user + accounting.kernel) / 10_000_000)
        if self.process is not None:
            class ProcessMemory(ctypes.Structure):
                _fields_ = [('size', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                    (name, ctypes.c_size_t) for name in ('peak_working_set', 'working_set', 'peak_paged_pool',
                    'paged_pool', 'peak_nonpaged_pool', 'nonpaged_pool', 'pagefile', 'peak_pagefile', 'private')]
            info = ProcessMemory()
            info.size = ctypes.sizeof(info)
            function = self.kernel.K32GetProcessMemoryInfo
            function.argtypes, function.restype = (wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD), wintypes.BOOL
            if function(self.process, ctypes.byref(info), ctypes.sizeof(info)):
                result['leader_peak_working_set_bytes'] = info.peak_working_set
                result['leader_private_bytes_at_completion'] = info.private
        return result

    def close(self):
        errors = []
        for field in ('thread', 'process', 'handle'):
            handle = getattr(self, field, None)
            if handle is not None:
                if not self.kernel.CloseHandle(handle):
                    errors.append(field)
                setattr(self, field, None)
        if errors:
            raise OSError(f'Owned native handle cleanup failed: {errors}')


def run(policy, policy_hash, settings, argv, prefix, disk_forecast, project_bytes, *, job_factory=WindowsJob):
    prefix = Path(prefix).resolve()
    prefix.parent.mkdir(parents=True, exist_ok=True)
    report_path, log_path = Path(str(prefix) + '-result.json'), Path(str(prefix) + '.log')
    if report_path.exists() or log_path.exists():
        raise FileExistsError('Use a new result prefix; retain prior evidence.')
    result = dict(schema_version=1, project=policy['project'], host=settings['host'],
                  workload=settings['workload'], policy_sha256=policy_hash, argv=argv,
                  started_utc=datetime.now(timezone.utc).isoformat(), status='failed',
                  workers=settings['workers'], project_logical_bytes=project_bytes,
                  estimated_disk_write_bytes=disk_forecast, estimated_peak_bytes=settings['estimated_peak_bytes'],
                  hard_memory_cap_bytes=None, cpu_hard_cap_percent=settings['cpu_hard_cap_percent'])
    started, job = time.monotonic(), None
    exit_code = 1
    lease, lease_entered = None, False
    try:
        if settings['preferred_host'] == 'msi' and settings['host'] != 'msi':
            raise policy_api.AdmissionDeferred('This workload belongs in the MSI queue; no automatic Initia fallback.')
        if policy_api.storage_prompt_required(policy, project_bytes):
            raise policy_api.AdmissionDeferred('Measured project storage exceeds the owner prompt threshold; '
                                               'report the specific storage decision once.')
        lease = policy_api.heavy_lease(policy, settings)
        lease.__enter__()
        lease_entered = True
        job = job_factory()
        initial = job.resources(prefix.parent)
        result['admission'] = initial
        reasons = policy_api.admit(settings, initial['available_physical'], initial['available_commit'],
                                   initial['free_disk'], disk_forecast, project_bytes)
        if reasons:
            raise policy_api.AdmissionDeferred('; '.join(reasons) + '; queue this job and continue independent work.')
        result['minimum'] = initial.copy()
        environment = os.environ.copy()
        environment.update(DOTNET_PROCESSOR_COUNT=str(settings['workers']),
                           CMAKE_BUILD_PARALLEL_LEVEL=str(settings['workers']),
                           MAX_JOBS=str(settings['workers']), PYTHONDONTWRITEBYTECODE='1')
        pressure = policy_api.PressureWindow(settings)
        with log_path.open('xb') as log:
            job.launch(argv, environment, Path.cwd(), log)
            result['worker_pid'] = job.pid
            deadline = time.monotonic() + settings['timeout_seconds']
            while True:
                now = time.monotonic()
                values = job.resources(prefix.parent)
                for key, value in values.items():
                    result['minimum'][key] = min(result['minimum'][key], value)
                if pressure.sample(now, values['available_physical'], values['available_commit']):
                    raise policy_api.AdmissionDeferred('Sustained host memory pressure; owned job stopped for requeue.')
                if values['free_disk'] < settings['disk_free_reserve_bytes']:
                    raise policy_api.AdmissionDeferred('Physical free-disk reserve reached; owned job stopped.')
                if now >= deadline:
                    raise TimeoutError('Workload deadline reached; retain results and diagnose before retry.')
                code = job.poll()
                if code is not None:
                    if job.active():
                        raise RuntimeError('Worker exited while owned descendants remain; stopping descendants.')
                    result.update(root_exit_confirmed=True, root_exit_code=code,
                                  remaining_job_processes=0, tree_exit_confirmed=True)
                    exit_code = code
                    result['status'] = 'passed' if code == 0 else 'failed'
                    break
                time.sleep(min(0.25, max(0, deadline - time.monotonic())))
    except policy_api.AdmissionDeferred as error:
        exit_code = 75
        result.update(status='deferred', reason=str(error))
    except (Exception, KeyboardInterrupt) as error:
        result.update(reason=str(error), failure_type=type(error).__name__)
    finally:
        owned_started = job is not None and job.process is not None
        try:
            if job is not None:
                try:
                    if owned_started and not result.get('tree_exit_confirmed'):
                        result['worker_pid'] = getattr(job, 'pid', None)
                        result.update(root_exit_confirmed=None, tree_exit_confirmed=False)
                        job.stop(exit_code)
                        cleanup_end = time.monotonic() + settings['running_pressure_grace_seconds']
                        while True:
                            # An unassigned suspended root is absent from the Job's count.
                            # TerminateProcess is asynchronous: poll its exact retained handle too.
                            root_code = job.poll()
                            remaining = job.active()
                            result.update(root_exit_confirmed=root_code is not None,
                                          root_exit_code=root_code, remaining_job_processes=remaining,
                                          tree_exit_confirmed=root_code is not None and remaining == 0)
                            if result['tree_exit_confirmed'] or time.monotonic() >= cleanup_end:
                                break
                            time.sleep(0.05)
                        if not result['tree_exit_confirmed']:
                            raise RuntimeError('Owned root or descendant closure remains unconfirmed.')
                finally:
                    try:
                        result['final_host'] = job.resources(prefix.parent)
                        result['owned_usage'] = job.telemetry()
                    except Exception as error:
                        result['usage_observation_error'] = str(error)
                    job.close()
        except Exception as error:
            result['status'], exit_code = 'failed', 1
            result['cleanup_error'] = str(error)
        finally:
            try:
                result['reconciliation_required'] = owned_started and not result.get('tree_exit_confirmed', False)
                if result['reconciliation_required']:
                    # Publish before releasing the OS lease; later heavy jobs must not
                    # interpret released lock metadata as proof that this tree has exited.
                    blocker = policy_api.mark_reconciliation_required(policy, settings, dict(
                        worker_pid=result.get('worker_pid'),
                        root_exit_confirmed=result.get('root_exit_confirmed'),
                        root_exit_code=result.get('root_exit_code'),
                        remaining_job_processes=result.get('remaining_job_processes'),
                        cleanup_error=result.get('cleanup_error'), report_path=str(report_path)))
                    result['reconciliation_marker'] = str(blocker)
                result.update(exit_code=exit_code, seconds=time.monotonic() - started,
                              completed_utc=datetime.now(timezone.utc).isoformat())
                with report_path.open('x', encoding='utf-8') as stream:
                    json.dump(result, stream, indent=2)
            finally:
                if lease_entered:
                    lease.__exit__(None, None, None)
    print(json.dumps({'status': result['status'], 'exit_code': exit_code, 'report': str(report_path)}), flush=True)
    return exit_code


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--policy', type=Path, default=policy_api.POLICY_PATH)
    parser.add_argument('--host', choices=('initia', 'msi'), default=os.environ.get('CODEX_EXECUTION_HOST'))
    parser.add_argument('--profile', required=True)
    parser.add_argument('--required-disk-bytes', type=int, required=True)
    parser.add_argument('--project-total-bytes', type=int)
    parser.add_argument('--report-prefix', type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('An exact command vector after -- is required.')
    try:
        policy, digest = policy_api.load_policy(args.policy)
        actual_host = policy_api.detect_host()
        if args.host is not None and args.host != actual_host:
            raise policy_api.PolicyError('Selected host differs from the verified physical executor.')
        settings = policy_api.select(policy, actual_host, args.profile)
        repository = args.policy.resolve().parent
        total = args.project_total_bytes
        if total is None:
            total = policy_api.project_usage(policy, repository, actual_host)
        root = Path(policy['locations']['execution_root'].format(host=actual_host))
        prefix = args.report_prefix or root / 'results' / uuid4().hex / 'job'
        return run(policy, digest, settings, command, prefix, args.required_disk_bytes, total)
    except (policy_api.PolicyError, policy_api.AdmissionDeferred) as error:
        print(json.dumps({'status': 'deferred', 'reason': str(error), 'independent_development': 'continue'}), flush=True)
        return 75


if __name__ == '__main__':
    raise SystemExit(main())
