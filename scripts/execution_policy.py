"""Current host policy and pure admission decisions; no product imports or fallback limits."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import ntpath
import os
from pathlib import Path
import stat
from uuid import uuid4

POLICY_PATH = Path(__file__).resolve().parents[1] / 'execution-policy.json'


class PolicyError(ValueError):
    pass


class AdmissionDeferred(RuntimeError):
    """The selected job waits; independent development remains available."""


def _positive(value, name):
    if type(value) is not int or value <= 0:
        raise PolicyError(f'{name} must be a positive integer; repair execution-policy.json.')


def load_policy(path=POLICY_PATH):
    path = Path(path)
    try:
        content = path.read_bytes()
        data = json.loads(content)
    except (OSError, UnicodeError, ValueError) as error:
        raise PolicyError(f'Cannot load current policy {path}; repair it, never reuse old limits.') from error
    try:
        if type(data['schema_version']) is not int or data['schema_version'] != 1:
            raise PolicyError('Expected execution-policy schema 1.')
        if not isinstance(data['project'], str) or not data['project']:
            raise PolicyError('Policy project name is required.')
        if not data['policy_revision']:
            raise PolicyError('Policy revision is required.')
        for host in ('initia', 'msi'):
            settings = data['hosts'][host]
            for key in ('ram_reserve_bytes', 'running_free_floor_bytes', 'running_pressure_grace_seconds',
                        'cpu_workers', 'heavy_slots', 'disk_free_reserve_bytes'):
                _positive(settings[key], f'hosts.{host}.{key}')
            if settings['heavy_slots'] != 1:
                raise PolicyError('Current shared host lease supports one heavy slot.')
            if settings['cpu_hard_cap_percent'] is not None or settings['priority'] != 'below-normal':
                raise PolicyError('Current host runner uses worker limits and below-normal priority, no CPU quota.')
        _positive(data['storage']['project_prompt_threshold_bytes'], 'storage.project_prompt_threshold_bytes')
        if data['storage']['prompt_when'] != 'project_total_exceeds_threshold':
            raise PolicyError('Storage prompt applies to total project use, not free disk.')
        if not isinstance(data['storage']['accounting_roots'], list) or not data['storage']['accounting_roots']:
            raise PolicyError('Declare the owned project storage roots.')
        if not all(isinstance(root, str) and root for root in data['storage']['accounting_roots']):
            raise PolicyError('Storage accounting roots must be nonempty paths.')
        for name in ('light', 'setup', 'focused_test', 'build', 'database_test', 'full_suite'):
            profile = data['workloads'][name]
            for key in ('estimated_peak_bytes', 'timeout_seconds'):
                _positive(profile[key], f'workloads.{name}.{key}')
            if type(profile['needs_heavy_slot']) is not bool or profile['preferred_host'] not in data['hosts']:
                raise PolicyError(f'Invalid workload routing for {name}.')
        for name in ('execution_root', 'shared_root'):
            if not data['locations'][name]:
                raise PolicyError(f'Missing locations.{name}.')
        for name in ('routing', 'github', 'queue', 'development'):
            if not isinstance(data[name], dict):
                raise PolicyError(f'Missing current {name} rules.')
    except (KeyError, TypeError) as error:
        raise PolicyError(f'Incomplete policy {path}; no inherited numeric fallback is permitted.') from error
    return data, hashlib.sha256(content).hexdigest()


def detect_host(hostname=None):
    name = (hostname or os.environ.get('COMPUTERNAME', '')).casefold()
    if name in ('tobylaptop', 'initia'):
        return 'initia'
    if name == 'msi':
        return 'msi'
    raise PolicyError('Unrecognized physical host; select --host only after verifying the actual executor.')


def filesystem_path(path):
    """Normalize before filesystem calls, including Win32 readers without MAX_PATH opt-in."""
    value = os.fsdecode(os.fspath(path))
    if os.name != 'nt':
        return Path(os.path.abspath(value))
    if value.startswith('\\\\?\\'):
        return Path(ntpath.normpath(value))
    absolute = ntpath.abspath(value)
    if absolute.startswith('\\\\'):
        return Path('\\\\?\\UNC\\' + absolute[2:])
    return Path('\\\\?\\' + absolute)


def storage_redirect(info):
    """Python 3.11-compatible symlink/junction and name-surrogate detection."""
    tag = getattr(info, 'st_reparse_tag', 0)
    mount_point = getattr(stat, 'IO_REPARSE_TAG_MOUNT_POINT', 0xA0000003)
    return (stat.S_ISLNK(info.st_mode) or tag == mount_point or
            bool(tag & 0x20000000))


def project_usage(policy, repository, host):
    """Count logical owned file bytes once; declared roots own their link targets."""
    execution_root = policy['locations']['execution_root'].format(host=host)
    roots = [filesystem_path(root.format(repository=str(repository), execution_root=execution_root, host=host))
             for root in policy['storage']['accounting_roots']]
    seen, total = set(), 0
    for root in dict.fromkeys(roots):
        try:
            info = root.stat()
        except FileNotFoundError:
            continue  # This host may not have a declared environment/evidence root.
        except OSError as error:
            raise PolicyError(f'Cannot account owned storage root {root}: {error}') from error
        if not stat.S_ISDIR(info.st_mode):
            raise PolicyError(f'Project accounting root is not a directory: {root}')
        identity = (info.st_dev, info.st_ino)
        if identity in seen:
            continue
        seen.add(identity)
        stack = [root]
        while stack:
            directory = stack.pop()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        path = filesystem_path(entry.path)
                        try:
                            info = path.lstat()
                        except FileNotFoundError:
                            continue  # A real temporary child disappeared after enumeration.
                        if storage_redirect(info):
                            continue
                        # lstat supplies Windows file IDs, unlike cached DirEntry metadata.
                        identity = (info.st_dev, info.st_ino)
                        if identity in seen:
                            continue
                        seen.add(identity)
                        if stat.S_ISDIR(info.st_mode):
                            stack.append(path)
                        elif stat.S_ISREG(info.st_mode):
                            total += info.st_size
            except FileNotFoundError:
                continue  # An enumerated temporary directory can also disappear.
            except OSError as error:
                raise PolicyError(f'Cannot account owned storage at {directory}: {error}; reconcile this root.') from error
    return total



def select(policy, host, workload, logical_cpus=None):
    try:
        settings, profile = policy['hosts'][host], policy['workloads'][workload]
    except KeyError as error:
        raise PolicyError(f'Unknown host/workload {host}/{workload}.') from error
    count = os.cpu_count() if logical_cpus is None else logical_cpus
    return {**settings, **profile, 'host': host, 'workload': workload,
            'workers': min(settings['cpu_workers'], max(1, count or 1))}


def admit(settings, available_physical, available_commit, free_disk, estimated_disk_write_bytes,
          project_total_bytes):
    for value, name in ((estimated_disk_write_bytes, 'disk-write forecast'), (project_total_bytes, 'project usage')):
        if type(value) is not int or value < 0:
            raise PolicyError(f'Provide a measured nonnegative {name}.')
    required = settings['ram_reserve_bytes'] + settings['estimated_peak_bytes']
    reasons = []
    if available_physical < required:
        reasons.append('available physical RAM is below host reserve plus workload estimate')
    if available_commit < required:
        reasons.append('commit headroom is below host reserve plus workload estimate')
    if free_disk < settings['disk_free_reserve_bytes'] + estimated_disk_write_bytes:
        reasons.append('free disk cannot retain the host reserve and forecast writes')
    return reasons


def storage_prompt_required(policy, project_total_bytes):
    if type(project_total_bytes) is not int or project_total_bytes < 0:
        raise PolicyError('Project storage usage must be a measured nonnegative integer.')
    return project_total_bytes > policy['storage']['project_prompt_threshold_bytes']


class PressureWindow:
    def __init__(self, settings):
        self.settings, self.breached_at = settings, None

    def sample(self, now, physical, commit):
        if min(physical, commit) >= self.settings['running_free_floor_bytes']:
            self.breached_at = None
            return False
        if self.breached_at is None:
            self.breached_at = now
        return now - self.breached_at >= self.settings['running_pressure_grace_seconds']


def reconciliation_path(policy, settings, root=None):
    directory = Path(root or policy['locations']['shared_root']) / 'locks'
    return directory / f"{settings['host']}.reconciliation-required.json"


def mark_reconciliation_required(policy, settings, details, root=None):
    """Persist an unresolved-ownership stop; only explicit reconciliation may clear it."""
    path = reconciliation_path(policy, settings, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(schema_version=1, state='OWNED_PROCESS_CLOSURE_UNRESOLVED',
                  host=settings['host'], project=policy['project'],
                  recorded_utc=datetime.now(timezone.utc).isoformat(), details=details)
    try:
        with path.open('x', encoding='utf-8') as stream:
            json.dump(record, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        pass  # Keep the original blocker and its ownership evidence unchanged.
    return path


@contextmanager
def heavy_lease(policy, settings, root=None):
    if not settings['needs_heavy_slot']:
        yield None
        return
    directory = Path(root or policy['locations']['shared_root']) / 'locks'
    directory.mkdir(parents=True, exist_ok=True)
    blocker = reconciliation_path(policy, settings, root)
    if blocker.exists():
        raise AdmissionDeferred(f'{blocker} requires explicit owned-process reconciliation; do not auto-clear it.')
    path = directory / f"{settings['host']}.heavy.lock"
    token = uuid4().hex
    record = {'schema_version': 1, 'token': token, 'pid': os.getpid(), 'project': policy['project'],
              'hostname': os.environ.get('COMPUTERNAME', ''), 'workload': settings['workload'],
              'birthtime': _process_birthtime(),
              'created_utc': datetime.now(timezone.utc).isoformat()}
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT)
    stream = os.fdopen(descriptor, 'r+b')
    try:
        if os.fstat(descriptor).st_size == 0:
            stream.write(b'\n')
            stream.flush()
        stream.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        stream.close()
        raise AdmissionDeferred(f'{path} has an active OS lock; queue this job and continue independent work.') from error
    try:
        # A preceding holder may have published a blocker after our first check.
        if blocker.exists():
            raise AdmissionDeferred(f'{blocker} requires explicit owned-process reconciliation; do not auto-clear it.')
        stream.seek(0)
        stream.write(json.dumps(record).encode('utf-8'))
        stream.truncate()
        stream.flush()
        os.fsync(descriptor)
        yield record
    finally:
        # Closing releases the kernel lock after success, failure, or interpreter death.
        # Metadata remains evidence. The next OS-lock holder may replace abandoned metadata.
        stream.close()


def _process_birthtime():
    if os.name != 'nt':
        return None  # The OS lock, not PID metadata, decides ownership on every platform.
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = (wintypes.HANDLE,) + (ctypes.POINTER(wintypes.FILETIME),) * 4
    kernel.GetProcessTimes.restype = wintypes.BOOL
    times = [wintypes.FILETIME() for _ in range(4)]
    if not kernel.GetProcessTimes(kernel.GetCurrentProcess(), *(ctypes.byref(value) for value in times)):
        raise OSError('Cannot record current process birth time for host lease.')
    return (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
