"""Run one ordinary Windows job using the repository's canonical execution policy."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import ntpath
import os
from pathlib import Path
import shutil
import stat
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


class _CustodyCapture:
    """Private Native2d capture using borrowed handles on the runner thread.

    Bind exact source, runtime and private output before use. The custody call
    samples after custody and before close. The activity callback samples in
    memory before stop. Publish activity after the runner returns, using a
    separate capture instance from the custody callback.
    The two-second query budget is cooperative. Coverage describes the sample.
    """
    MAX_SLOTS, MAX_BYTES, QUERY_SECONDS = 16, 1024 * 1024, 2.0
    FIELDS = ('total_processes', 'retained_identity_count', 'all_identities_accounted',
              'all_retained_descendants_exited', 'complete')

    def __init__(self, path, selected_image, *, clock=time.monotonic):
        self.path, self.selected_image, self.clock = Path(path), str(selected_image), clock
        self.complete, self.error, self.report = False, None, None
        self.query_deadline = float('inf')

    def _budget(self):
        now = self.clock()
        if now - self.started >= self.QUERY_SECONDS or now >= self.query_deadline:
            raise TimeoutError('Diagnostic query budget exhausted')

    def _query(self, kernel, row, name, *args, valid=bool):
        self._budget()
        outcome = dict(api=name, ok=False, outcome='started', error=None)
        row['queries'].append(outcome)
        try:
            value = getattr(kernel, name)(*args)
            ok = valid(value)
        except BaseException as error:
            code = getattr(error, 'winerror', None)
            outcome.update(outcome='interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit))
                           else 'raised', exception_type=type(error).__name__,
                           error=code if type(code) is int and 0 <= code <= 0xffffffff else None)
            raise
        outcome.update(ok=ok, outcome='success' if ok else 'failed',
                       error=None if ok else ctypes.get_last_error())
        self._budget()
        return ok, value

    @staticmethod
    def _filetime(value):
        return (value.dwHighDateTime << 32) | value.dwLowDateTime

    def _read_identity(self, job, handle, row):
        kernel = job.kernel
        ok, pid = self._query(kernel, row, 'GetProcessId', handle)
        row['handle_pid'] = pid if ok else None
        row['pid_matches_ledger'] = ok and pid == row['ledger_pid']
        ok, signal = self._query(kernel, row, 'WaitForSingleObject', handle, 0,
                                valid=lambda value: value in (0, 258))
        row['signalled'] = signal == 0 if ok else None
        row['exit_code'] = None
        if row['signalled'] is True:
            exit_code = wintypes.DWORD()
            ok, _ = self._query(kernel, row, 'GetExitCodeProcess', handle, ctypes.byref(exit_code))
            if ok:
                row['exit_code'] = exit_code.value
        creation, exit_time, kernel_time, user_time = (wintypes.FILETIME() for _ in range(4))
        ok, _ = self._query(kernel, row, 'GetProcessTimes', handle, ctypes.byref(creation),
                           ctypes.byref(exit_time), ctypes.byref(kernel_time), ctypes.byref(user_time))
        row['creation_filetime'] = self._filetime(creation) if ok else None
        row['exit_filetime'] = self._filetime(exit_time) if ok and row['signalled'] is True else None

    def _read_row(self, job, handle, row):
        self._read_identity(job, handle, row)
        kernel = job.kernel
        member = wintypes.BOOL()
        ok, _ = self._query(kernel, row, 'IsProcessInJob', handle, job.handle, ctypes.byref(member))
        row['member_of_exact_job'] = bool(member.value) if ok else None
        image, size = ctypes.create_unicode_buffer(32768), wintypes.DWORD(32768)
        ok, _ = self._query(kernel, row, 'QueryFullProcessImageNameW', handle, 0,
                           image, ctypes.byref(size))
        basename = ntpath.basename(image.value) if ok else ''
        row['image_basename'] = basename[:260] if ok else None
        row['image_truncated'] = bool(ok and (len(basename) > 260 or size.value >= len(image)))
        row['matches_selected_image_path'] = (
            ntpath.normcase(ntpath.normpath(image.value)) ==
            ntpath.normcase(ntpath.normpath(self.selected_image))) if ok else None
        row['ancestry'] = 'unavailable'
        row['complete'] = (row['pid_matches_ledger'] and row['signalled'] is True
            and row['creation_filetime'] is not None and row['creation_filetime'] > 0
            and row['member_of_exact_job'] is True and bool(row['image_basename'])
            and not row['image_truncated']
            and all(query['ok'] for query in row['queries']))

    def _slots(self, job):
        if (job.assigned is not True or type(job.pid) is not int or job.pid <= 0
                or type(job.process) is not int or job.process <= 0
                or type(job.handle) is not int or job.handle <= 0):
            raise ValueError('Assigned native root unavailable')
        handles = job.descendant_handles
        if type(handles) is not dict or len(handles) >= self.MAX_SLOTS:
            raise ValueError('Owned slot cap or ledger layout')
        slots = [('root', job.pid, job.process)]
        for pid, handle in sorted(handles.items()):
            if (type(pid) is not int or pid <= 0 or pid == job.pid
                    or type(handle) is not int or handle <= 0):
                raise ValueError('Invalid retained slot')
            slots.append(('retained', pid, handle))
        return slots

    @staticmethod
    def _bind_queries(kernel, *, custody):
        pointer = ctypes.POINTER
        signatures = {
            'GetProcessId': ((wintypes.HANDLE,), wintypes.DWORD),
            'GetProcessTimes': ((wintypes.HANDLE, pointer(wintypes.FILETIME), pointer(wintypes.FILETIME),
                                 pointer(wintypes.FILETIME), pointer(wintypes.FILETIME)), wintypes.BOOL),
            'WaitForSingleObject': ((wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD),
            'GetExitCodeProcess': ((wintypes.HANDLE, pointer(wintypes.DWORD)), wintypes.BOOL),
        }
        if custody:
            signatures.update(
                IsProcessInJob=((wintypes.HANDLE, wintypes.HANDLE, pointer(wintypes.BOOL)), wintypes.BOOL),
                QueryFullProcessImageNameW=((wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                            pointer(wintypes.DWORD)), wintypes.BOOL),
            )
        for name, (arguments, result) in signatures.items():
            function = getattr(kernel, name)
            function.argtypes, function.restype = arguments, result

    def _collect(self, job, custody, report):
        if not isinstance(custody, dict) or any(key not in custody for key in self.FIELDS):
            raise ValueError('Native custody snapshot unavailable')
        if any(type(custody[key]) is not int or custody[key] < 1 for key in self.FIELDS[:2]):
            raise ValueError('Invalid native lifetime counts')
        if any(type(custody[key]) is not bool for key in self.FIELDS[2:]):
            raise ValueError('Invalid native custody flags')
        report['raw_custody'] = {key: custody[key] for key in self.FIELDS}
        slots = self._slots(job)
        report['expected_slots'] = len(slots)
        self._bind_queries(job.kernel, custody=True)
        for origin, pid, handle in slots:
            self._budget()
            row = dict(slot=len(report['rows']), origin=origin, ledger_pid=pid,
                       complete=False, queries=[])
            report['rows'].append(row)
            self._read_row(job, handle, row)
        report['observed_slots'] = len(report['rows'])
        report['complete'] = (len(slots) == custody['total_processes'] == custody['retained_identity_count']
            and custody['complete'] is True and custody['all_identities_accounted'] is True
            and custody['all_retained_descendants_exited'] is True
            and all(row['complete'] for row in report['rows']))

    def __call__(self, job, custody):
        self.started = self.clock()
        self.query_deadline = float('inf')
        report = dict(schema_version=1, kind='private-owned-custody-diagnostic',
            capture_id=uuid4().hex, expected_native_sha256=policy_api.MSI_SHARED_PINS['native_job.py'],
            stage='after-custody-before-close', complete=False, expected_slots=None,
            observed_slots=0, rows=[], error=None)
        self.report, self.complete, self.error = report, False, None
        try:
            self._collect(job, custody, report)
            self._budget()
        except BaseException as error:
            report['complete'], report['error'] = False, type(error).__name__
        report['observed_slots'] = len(report['rows'])
        report['query_seconds'] = self.clock() - self.started
        return self._publish(report)

    def _publish(self, report):
        try:
            payload = (json.dumps(report, sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
            if len(payload) > self.MAX_BYTES:
                raise ValueError('Diagnostic evidence cap exceeded')
            with self.path.open('xb') as stream:
                if stream.write(payload) != len(payload):
                    raise OSError('Incomplete diagnostic write')
            self.complete = report['complete']
        except BaseException as error:
            self.error, self.complete = type(error).__name__, False
            report['complete'], report['write_error'] = False, self.error
        return self.complete


    def observe_activity(self, job, accounting_type, root_code, remaining, deadline, *,
                         source_commit, policy_sha256, runtime_sha256):
        """Capture a later, non-atomic observation of the existing Job before stop."""
        identities = dict(source_commit=source_commit, policy_sha256=policy_sha256,
                          runtime_sha256=runtime_sha256)
        for value, size in ((source_commit, 40), (policy_sha256, 64), (runtime_sha256, 64)):
            if (not isinstance(value, str) or len(value) != size
                    or any(character not in '0123456789abcdef' for character in value)):
                raise ValueError('Diagnostic source binding requires lowercase hashes')
        self.started, self.query_deadline = self.clock(), deadline
        report = dict(schema_version=1, kind='private-owned-activity-diagnostic',
                      capture_id=uuid4().hex, expected_native_sha256=policy_api.MSI_SHARED_PINS['native_job.py'],
                      stage='root-exit-before-stop', atomic_with_guard=False,
                      original_guard=dict(root_exit_code=root_code, active_return=remaining),
                      started_monotonic=self.started, expected_slots=None, observed_slots=0,
                      accounting=None, retained_unsignalled=None, rows=[], queries=[],
                      complete=False, truncated=False, error=None, **identities)
        self.report, self.complete, self.error = report, False, None
        try:
            self._collect_activity(job, accounting_type, report)
        except BaseException as error:
            report['complete'], report['error'] = False, type(error).__name__
        report['observed_slots'] = sum(bool(row['queries']) for row in report['rows'])
        report['ended_monotonic'] = self.clock()

    def publish_activity(self):
        """Write the captured report after the caller's runner has finalized."""
        if self.report is None or self.report['kind'] != 'private-owned-activity-diagnostic':
            return False
        return self._publish(self.report)

    def _collect_activity(self, job, accounting_type, report):
        self._budget()
        if not isinstance(accounting_type, type) or not issubclass(accounting_type, ctypes.Structure):
            raise ValueError('Pinned native Accounting type unavailable')
        if ctypes.sizeof(accounting_type) != 48:
            raise ValueError('Pinned native Accounting layout differs')
        if isinstance(job.descendant_handles, dict) and len(job.descendant_handles) >= self.MAX_SLOTS:
            report['truncated'] = True
        slots = self._slots(job)
        if len({handle for _, _, handle in slots}) != len(slots):
            raise ValueError('Repeated owned handle')
        report['expected_slots'] = len(slots)
        info = accounting_type()
        ok, _ = self._query(job.kernel, report, 'QueryInformationJobObject', job.handle,
                            1, ctypes.byref(info), ctypes.sizeof(info), None)
        if ok:
            report['accounting'] = dict(active=info.active, total=info.total)
        self._bind_queries(job.kernel, custody=False)
        for origin, pid, handle in slots:
            row = dict(slot=len(report['rows']), origin=origin, ledger_pid=pid, queries=[])
            report['rows'].append(row)
            self._read_identity(job, handle, row)
        self._budget()
        rows = report['rows']
        members = [row for row in rows if row['origin'] == 'retained']
        if all(row['signalled'] is not None for row in members):
            report['retained_unsignalled'] = sum(row['signalled'] is False for row in members)
        report['complete'] = report['accounting'] is not None and all(
            row['pid_matches_ledger'] and (row['creation_filetime'] or 0) > 0
            and all(query['ok'] for query in row['queries']) for row in rows)


def _activity_receipt(record):
    """Validate the optional private extension before touching the raw result."""
    unavailable = {'status': 'unavailable'}
    try:
        if type(record) is not dict or record.get('kind') != 'private-owned-activity-diagnostic':
            return unavailable
        encoded = json.dumps({'pre_stop_activity': record}, indent=2,
                             allow_nan=False).encode('utf-8')
        if len(encoded) > _CustodyCapture.MAX_BYTES:
            return unavailable
        return json.loads(encoded)['pre_stop_activity']
    except BaseException:
        return unavailable


def run(policy, policy_hash, settings, argv, prefix, disk_forecast, project_bytes, *,
        job_factory=None, host_factory=None, attempt_observer=None, custody_observer=None,
        activity_observer=None):
    """Return raw outcomes. Optional custody observer is MSI-only, post-custody/pre-close.

    It receives the same job and a shallow snapshot (None if unavailable). It owns
    its private diagnostic verdict; even cancellation cannot skip real close or
    alter the authoritative raw result. Optional activity observation uses the
    same registered MSI Job and loaded Accounting type before stopping. Its
    callback samples in memory. An optional validated observation joins the
    existing private receipt after lifecycle finalization.
    """
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
    started, job, native = time.monotonic(), None, None
    host, host_token, launch_succeeded, job_closed = None, None, False, False
    exit_code = 1
    activity_attempted, activity_record = False, None
    lease, lease_entered = None, False
    try:
        if settings['preferred_host'] == 'msi' and settings['host'] != 'msi':
            raise policy_api.AdmissionDeferred('This workload belongs in the MSI queue; no automatic Initia fallback.')
        if policy_api.storage_prompt_required(policy, project_bytes):
            raise policy_api.AdmissionDeferred('Measured project storage exceeds the owner prompt threshold; '
                                               'report the specific storage decision once.')
        host = (host_factory or policy_api.msi_host_control)(policy, settings)
        if settings['host'] == 'msi' and host is None:
            raise policy_api.AdmissionDeferred('MSI requires its reviewed host admission interface.')
        if host is not None:
            with host.locked():
                host.assert_development()
        if job_factory is None:
            native = policy_api.msi_native_job(policy, settings)
            if settings['host'] == 'msi' and native is None:
                raise policy_api.AdmissionDeferred('MSI requires its reviewed owned-job interface.')
            job_factory = native.WindowsJob if native is not None else WindowsJob
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
            if host is None:
                if attempt_observer is not None:
                    attempt_observer('creation')
                job.launch(argv, environment, Path.cwd(), log)
            else:
                # The final fence check and actual child creation share the mutex.
                # The registration outlives the mutex until custody is proven.
                with host.locked():
                    host.assert_development()
                    if attempt_observer is not None:
                        attempt_observer('registration')
                    host_token = host.register_locked('direct', dict(
                        project=policy['project'], workload=settings['workload'],
                        policy_sha256=policy_hash, report_path=str(report_path)))
                    result['msi_admission'] = dict(token=host_token, closure_confirmed=False)
                    if attempt_observer is not None:
                        attempt_observer('creation')
                    job.launch(argv, environment, Path.cwd(), log)
            launch_succeeded = True
            result['worker_pid'] = job.pid
            deadline = time.monotonic() + settings['timeout_seconds']
            while True:
                now = time.monotonic()
                # Retain descendants before resource/deadline stops can intervene.
                if host is not None:
                    try:
                        job.active()
                    except (Exception, KeyboardInterrupt) as error:
                        result['ownership_observation_error'] = str(error)
                        raise
                values = job.resources(prefix.parent)
                for key, value in values.items():
                    result['minimum'][key] = min(result['minimum'][key], value)
                if pressure.sample(now, values['available_physical'], values['available_commit']):
                    raise policy_api.AdmissionDeferred('Sustained host memory pressure; owned job stopped for requeue.')
                if values['free_disk'] < settings['disk_free_reserve_bytes']:
                    raise policy_api.AdmissionDeferred('Physical free-disk reserve reached; owned job stopped.')
                if now >= deadline:
                    raise TimeoutError('Workload deadline reached; retain results and diagnose before retry.')
                try:
                    code = job.poll()
                    remaining = job.active() if code is not None else None
                except (Exception, KeyboardInterrupt) as error:
                    if host is not None:
                        result['ownership_observation_error'] = str(error)
                    raise
                if code is not None:
                    if remaining:
                        if (code == 0 and activity_observer is not None and native is not None
                                and host_token is not None and settings['host'] == 'msi'):
                            activity_attempted = True
                            try:
                                activity_record = activity_observer(job, native.Accounting, code,
                                                                    remaining, deadline)
                            except BaseException:
                                # Observation cannot replace the guard or skip finalization.
                                pass
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
        if host is not None and isinstance(error, host.denied_error):
            exit_code = 75
            result.update(status='deferred', reason=str(error))
        else:
            result.update(reason=str(error), failure_type=type(error).__name__)
    finally:
        owned_started = job is not None and job.process is not None
        try:
            if job is not None:
                try:
                    if owned_started and not result.get('tree_exit_confirmed'):
                        result['worker_pid'] = getattr(job, 'pid', None)
                        result.update(root_exit_confirmed=None, tree_exit_confirmed=False)
                        if host is not None:
                            try:
                                job.active()
                            except (Exception, KeyboardInterrupt) as error:
                                result['ownership_observation_error'] = str(error)
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
                    except (Exception, KeyboardInterrupt) as error:
                        result['usage_observation_error'] = str(error)
                    if host_token is not None:
                        custody = None
                        try:
                            custody = job.custody()
                            counts = [custody[key] for key in ('total_processes', 'retained_identity_count')]
                            complete = (all(type(value) is int and value >= 1 for value in counts)
                                        and counts[0] == counts[1]
                                        and all(custody[key] is True for key in (
                                            'all_identities_accounted', 'all_retained_descendants_exited', 'complete')))
                            result['owned_custody'] = custody
                            result['msi_admission']['custody_complete'] = complete
                        except (Exception, KeyboardInterrupt) as error:
                            result['custody_observation_error'] = str(error)
                        if custody_observer is not None:
                            try:
                                snapshot = dict(custody) if isinstance(custody, dict) else None
                                custody_observer(job, snapshot)
                            except BaseException:
                                # Diagnosis cannot replace raw custody or interrupt real finalization.
                                # Its private report/status must be checked independently of exit0.
                                pass
                    job.close()
                    job_closed = True
        except (Exception, KeyboardInterrupt) as error:
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
                if host_token is not None:
                    closure = (launch_succeeded and job_closed and result.get('root_exit_confirmed') is True
                               and result.get('tree_exit_confirmed') is True
                               and result['msi_admission'].get('custody_complete') is True
                               and not any(key in result for key in (
                                   'cleanup_error', 'usage_observation_error', 'custody_observation_error',
                                   'ownership_observation_error')))
                    if closure:
                        try:
                            host.complete(host_token, closure=True)
                            result['msi_admission']['closure_confirmed'] = True
                        except (Exception, KeyboardInterrupt) as error:
                            result['status'], exit_code = 'failed', 1
                            result['host_completion_error'] = str(error)
                    result['msi_admission']['hold_retained'] = not result['msi_admission']['closure_confirmed']
                result.update(exit_code=exit_code, seconds=time.monotonic() - started,
                              completed_utc=datetime.now(timezone.utc).isoformat())
                if activity_attempted:
                    result['pre_stop_activity'] = _activity_receipt(activity_record)
                with report_path.open('x', encoding='utf-8') as stream:
                    json.dump(result, stream, indent=2)
            finally:
                if lease_entered:
                    lease.__exit__(None, None, None)
    print(json.dumps({'status': result['status'], 'exit_code': exit_code, 'report': str(report_path)}), flush=True)
    return exit_code


def _queue_metadata(raw, outer, attempted, reason):
    print(json.dumps(dict(record_type='queue_disposition', raw_source_exit=raw,
                          queue_return_code=outer, creation_attempted=attempted,
                          reason=reason)), flush=True)
    return outer


def _queue_receipt(report, policy, digest, settings, command, disk_forecast, total, raw, began, ended):
    """Read this call's final schema-1 evidence without changing its raw meaning."""
    value = json.loads(report.read_text(encoding='utf-8'))
    expected = dict(project=policy['project'], host=settings['host'], workload=settings['workload'],
                    policy_sha256=digest, argv=command, workers=settings['workers'],
                    project_logical_bytes=total, estimated_disk_write_bytes=disk_forecast,
                    estimated_peak_bytes=settings['estimated_peak_bytes'],
                    hard_memory_cap_bytes=None, cpu_hard_cap_percent=settings['cpu_hard_cap_percent'])
    if (not isinstance(value, dict) or type(value.get('schema_version')) is not int
            or value['schema_version'] != 1 or type(value.get('exit_code')) is not int
            or value['exit_code'] != raw or any(key not in value or value[key] != item
                                             for key, item in expected.items())):
        raise ValueError('Receipt identity or raw outcome differs from this invocation.')
    started = datetime.fromisoformat(value['started_utc'])
    completed = datetime.fromisoformat(value['completed_utc'])
    seconds = value['seconds']
    if (not began <= started <= completed <= ended
            or type(seconds) not in (int, float) or not 0 <= seconds < float('inf')
            or type(value.get('reconciliation_required')) is not bool):
        raise ValueError('Receipt lacks complete same-attempt finalization evidence.')
    statuses = ('deferred', 'failed') if raw == 75 else ('passed' if raw == 0 else 'failed',)
    if value.get('status') not in statuses:
        raise ValueError('Receipt status differs from the raw outcome.')
    return value


# The dedicated diagnostic snapshot binds the original #237 payload.
_DIAGNOSTIC_ARGV = (
    'C:/Program Files/Python313/python.exe', '-B', '-m', 'unittest', 'discover',
    '-s', 'scripts', '-p', 'test_run_project_job.py', '-v',
)
_DIAGNOSTIC_POLICY_SHA256 = '8a5ef27c6051ae6268ee7735c767aea3457779525f191b2cb4313146ab8d5827'
_DIAGNOSTIC_FIXTURE_SHA256 = 'a84294405c998dcb2a131ad2e3e245ec8e3c8c89c7d134569c96d6cf508cab94'
_DIAGNOSTIC_RUNTIME_SHA256 = 'ef8f51028ac5329641985112f8efb1c2d4c47c86b8011ddf7e6fae21e2b4e5a1'


def _plain_owned_path(path, is_expected_type):
    info = path.lstat()
    if (not is_expected_type(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ValueError('Unexpected diagnostic path type')


def _read_diagnostic_input(path, limit):
    _plain_owned_path(path, stat.S_ISREG)
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Diagnostic input exceeds size bound')
    return data


def _bind_activity_observer(policy, digest, settings, command, prefix, disk_forecast):
    """Bind the worker's first-attempt request to the dedicated diagnostic."""
    if tuple(command) != _DIAGNOSTIC_ARGV:
        return None
    if (policy['project'] != 'pyfa' or settings['host'] != 'msi'
            or settings['workload'] != 'focused_test' or digest != _DIAGNOSTIC_POLICY_SHA256
            or disk_forecast != 268435456):
        raise ValueError('Diagnostic policy or profile differs')
    identity = os.environ.get('CODEX_QUEUE_JOB_ID', '')
    if len(identity) != 64 or any(char not in '0123456789abcdef' for char in identity):
        raise ValueError('Diagnostic queue key unavailable')
    root = Path(policy['locations']['execution_root'].format(host='msi')).resolve(strict=True)
    jobs = root / 'jobs'
    job = jobs / identity
    source, results = job / 'source', job / 'results'
    attempt = results / 'attempt-0001'
    if (prefix != attempt / 'policy' or Path.cwd().resolve() != source
            or Path(__file__).resolve() != source / 'scripts' / 'run_project_job.py'):
        raise ValueError('Diagnostic first-attempt checkout or prefix differs')
    for directory in (jobs, job, source, source / 'scripts', source / '.git', results, attempt):
        _plain_owned_path(directory, stat.S_ISDIR)
    commit = _read_diagnostic_input(source / '.git' / 'HEAD', 64).decode('ascii').strip()
    if len(commit) != 40 or any(char not in '0123456789abcdef' for char in commit):
        raise ValueError('Diagnostic checkout is not detached at a full commit')
    expected = dict(schema_version=1, kind='codex-msi-validation', project='pyfa',
                    repository='Sussic/Pyfa-android', commit=commit,
                    policy_path='execution-policy.json', policy_sha256=digest,
                    workload='focused_test', argv=list(_DIAGNOSTIC_ARGV),
                    required_capabilities=['windows', 'python'],
                    estimated_disk_write_bytes=disk_forecast)
    canonical = dict(sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    key = hashlib.sha256(json.dumps(expected, **canonical).encode('utf-8')).hexdigest()
    request = json.loads(_read_diagnostic_input(attempt / 'request.json', 16384))
    if key != identity or json.dumps(request, **canonical) != json.dumps(
            dict(expected, idempotency_key=key), **canonical):
        raise ValueError('Diagnostic request binding differs')
    marker = json.loads(_read_diagnostic_input(job / '.msi-job-owner.json', 16384))
    if (not isinstance(marker, dict) or type(marker.get('schema_version')) is not int
            or marker['schema_version'] != 1 or marker.get('kind') != 'codex-msi-owned-job'
            or not isinstance(marker.get('job_root'), str) or Path(marker['job_root']) != job
            or marker.get('request_sha256') != key
            or any(marker.get(field) != expected[field] for field in
                   ('project', 'repository', 'commit', 'policy_sha256'))):
        raise ValueError('Diagnostic worker ownership binding differs')
    fixture = _read_diagnostic_input(source / 'scripts' / 'test_run_project_job.py', 128 * 1024)
    runtime = _read_diagnostic_input(Path(command[0]), 4 * 1024 * 1024)
    if (hashlib.sha256(fixture).hexdigest() != _DIAGNOSTIC_FIXTURE_SHA256
            or hashlib.sha256(runtime).hexdigest() != _DIAGNOSTIC_RUNTIME_SHA256):
        raise ValueError('Diagnostic fixture or interpreter differs')

    # The private activity path uses the existing receipt and never publishes a sidecar.
    capture = _CustodyCapture(Path(str(prefix) + '-result.json'), '')
    def observe(job, accounting_type, code, remaining, deadline):
        capture.observe_activity(job, accounting_type, code, remaining, deadline,
                                 source_commit=commit, policy_sha256=digest,
                                 runtime_sha256=_DIAGNOSTIC_RUNTIME_SHA256)
        return capture.report
    return observe


def _queue_run(policy, digest, settings, command, prefix, disk_forecast, total):
    diagnostic = tuple(command) == _DIAGNOSTIC_ARGV
    attempted, registration_attempted = False, False
    def observe_attempt(event):
        nonlocal attempted, registration_attempted
        # This is deliberately before creation, including partial/unknown failure.
        if event == 'creation':
            attempted = True
        elif event == 'registration':
            # A registration can retain a hold and then fail before returning its token.
            registration_attempted = True
        else:
            raise ValueError('Unknown attempt observer phase.')
    try:
        prefix = Path(prefix).resolve()
        report = Path(str(prefix) + '-result.json')
        # run() also enforces exclusive creation. A pre-existing prefix is never
        # evidence for this invocation, even if it contains a plausible receipt.
        if report.exists() or Path(str(prefix) + '.log').exists():
            raise FileExistsError('Use a new result prefix; retain prior evidence.')
        options = dict(attempt_observer=observe_attempt)
        if diagnostic:
            try:
                options['activity_observer'] = _bind_activity_observer(
                    policy, digest, settings, command, prefix, disk_forecast)
            except (OSError, ValueError, KeyError, TypeError):
                return _queue_metadata(None, 1, False, 'diagnostic_binding_refused')
        began = datetime.now(timezone.utc)
        raw = run(policy, digest, settings, command, prefix, disk_forecast, total, **options)
    except (Exception, KeyboardInterrupt) as error:
        return _queue_metadata(None, 1, attempted, f'run_did_not_return: {type(error).__name__}: {error}')
    try:
        if type(raw) is not int:
            raise ValueError('run() did not return a numeric raw outcome.')
        receipt = _queue_receipt(report, policy, digest, settings, command, disk_forecast,
                                 total, raw, began, datetime.now(timezone.utc))
        if raw != 75:
            return _queue_metadata(raw, raw, attempted, 'raw_outcome_preserved')
        if diagnostic:
            return _queue_metadata(raw, 1, attempted, 'diagnostic_attempt_consumed')
        if attempted:
            return _queue_metadata(raw, 1, True, 'creation_attempted')
        if registration_attempted:
            return _queue_metadata(raw, 1, False, 'ownership_registration_attempted')
        uncertainty = ('worker_pid', 'root_exit_confirmed', 'root_exit_code', 'tree_exit_confirmed',
                       'remaining_job_processes', 'msi_admission', 'owned_custody', 'reconciliation_marker',
                       'failure_type', 'cleanup_error', 'usage_observation_error',
                       'custody_observation_error', 'ownership_observation_error', 'host_completion_error')
        if (receipt['status'] != 'deferred' or receipt['reconciliation_required'] is not False
                or not isinstance(receipt.get('reason'), str) or not receipt['reason']
                or any(key in receipt for key in uncertainty)):
            raise ValueError('Nonlaunching deferral has creation, ownership or finalization uncertainty.')
    except (Exception, KeyboardInterrupt) as error:
        return _queue_metadata(raw, 1, attempted, f'invalid_final_receipt: {type(error).__name__}: {error}')
    return _queue_metadata(raw, 75, False, 'proven_nonlaunching_deferral')


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
    queued = 'CODEX_QUEUE_JOB_ID' in os.environ
    diagnostic = tuple(command) == _DIAGNOSTIC_ARGV
    if diagnostic and (
            not queued or args.policy.resolve() != policy_api.POLICY_PATH.resolve()):
        return _queue_metadata(None, 1, False, 'diagnostic_binding_refused')
    if queued:
        identity = os.environ['CODEX_QUEUE_JOB_ID']
        if len(identity) != 64 or any(char not in '0123456789abcdef' for char in identity):
            return _queue_metadata(None, 1, False, 'invalid_queue_identity')
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
        if queued:
            return _queue_run(policy, digest, settings, command, prefix, args.required_disk_bytes, total)
        return run(policy, digest, settings, command, prefix, args.required_disk_bytes, total)
    except (policy_api.PolicyError, policy_api.AdmissionDeferred) as error:
        print(json.dumps({'status': 'deferred', 'reason': str(error), 'independent_development': 'continue'}), flush=True)
        if queued:
            if diagnostic:
                return _queue_metadata(75, 1, False, 'diagnostic_setup_refused')
            return _queue_metadata(75, 75, False, 'initial_setup_refusal')
        return 75


if __name__ == '__main__':
    raise SystemExit(main())
