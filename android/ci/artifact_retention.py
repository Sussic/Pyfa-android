"""Owned runtime cleanup and aggregate local artifact admission; no evidence eviction."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import time

GIB = 1024 ** 3
DEFAULT_LIMIT = 32 * GIB
MIN_FREE = 4 * GIB
RUNTIME = re.compile(r'avd(?:-r[0-9]+|-c04-r[0-9]+)?\Z')


class RetentionError(RuntimeError):
    pass


def redirect(path):
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_reparse_tag', 0) & 0x20000000)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def usage(roots):
    """Allocated bytes, deduplicated by filesystem identity (including hardlinks)."""
    directories = set()
    files = set()
    total = 0
    if os.name == 'nt':
        from ctypes import wintypes
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        compressed = k.GetCompressedFileSizeW
        compressed.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
        compressed.restype = wintypes.DWORD
    for supplied in roots:
        root = Path(supplied)
        if not root.exists():
            continue
        root = root.resolve(strict=True)
        stack = [root]
        while stack:
            path = stack.pop()
            try:
                if redirect(path):
                    raise RetentionError('Artifact accounting refuses redirected child: ' + str(path))
                info = path.stat()
            except FileNotFoundError:
                continue  # Build temporaries can disappear between directory scans.
            identity = (info.st_dev, info.st_ino)
            if path.is_dir():
                if identity in directories:
                    continue
                directories.add(identity)
                try:
                    stack.extend(path.iterdir())
                except FileNotFoundError:
                    continue
            elif path.is_file() and identity not in files:
                files.add(identity)
                if os.name == 'nt':
                    high = wintypes.DWORD()
                    ctypes.set_last_error(0)
                    low = compressed(str(path), ctypes.byref(high))
                    if low == 0xffffffff and ctypes.get_last_error():
                        if ctypes.get_last_error() in (2, 3):
                            continue
                        raise ctypes.WinError(ctypes.get_last_error())
                    total += (high.value << 32) | low
                else:
                    total += getattr(info, 'st_blocks', 0) * 512 or info.st_size
    return dict(allocated_bytes=total, files=len(files), directories=len(directories))


class ArtifactBudget:
    def __init__(self, roots, limit=DEFAULT_LIMIT, minimum_free=MIN_FREE, interval=5):
        if not 0 < limit <= DEFAULT_LIMIT:
            raise RetentionError('Artifact limit must be positive and at most 32 GiB')
        self.roots = list(dict.fromkeys(str(Path(p).resolve()) for p in roots))
        self.limit = limit
        self.minimum_free = minimum_free
        self.interval = interval
        self.latest = None

    def include_previous(self, policy):
        if policy is None:
            return
        if not isinstance(policy, dict) or policy.get('version') != 1:
            raise RetentionError('Unrecognized saved artifact policy')
        roots, limit = policy.get('roots'), policy.get('limit_bytes')
        if (not isinstance(roots, list) or not roots or
                any(not isinstance(p, str) or not Path(p).is_absolute() for p in roots) or
                type(limit) is not int or not 0 < limit <= DEFAULT_LIMIT):
            raise RetentionError('Invalid saved artifact policy')
        self.roots = list(dict.fromkeys(self.roots + [str(Path(p).resolve()) for p in roots]))
        self.limit = min(self.limit, limit)

    def check(self, reserve=0):
        result = usage(self.roots)
        result.update(limit_bytes=self.limit, reserved_bytes=reserve, roots=self.roots)
        self.latest = result
        if result['allocated_bytes'] + reserve > self.limit:
            raise RetentionError('Aggregate artifact budget exceeded: ' + json.dumps(result))
        for root in self.roots:
            path = Path(root)
            while not path.exists():
                path = path.parent
            free = shutil.disk_usage(path).free
            if free < self.minimum_free:
                raise RetentionError(f'Free disk reserve reached: {free} bytes at {path}')
        return result

    def copy(self, source, destination):
        source, destination = Path(source), Path(destination)
        # Copying sparse inputs may allocate their entire logical length.
        paths = source.rglob('*') if source.is_dir() else [source]
        reserve = sum(p.stat().st_size for p in paths if p.is_file())
        self.check(reserve)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copyfile(source, destination)
        self.check()

    def run(self, command, *, cwd=None, stdout=None, stderr=None, timeout=None, input=None, check=False):
        """Poll aggregate storage while an independently owned command runs."""
        self.check()
        start = time.monotonic()
        with OwnedCommand(command, cwd=cwd, stdout=stdout, stderr=stderr, input=input) as process:
            while process.poll() is None:
                remaining = None if timeout is None else timeout - (time.monotonic() - start)
                if remaining is not None and remaining <= 0:
                    raise subprocess.TimeoutExpired(command, timeout)
                process.wait(self.interval if remaining is None else min(self.interval, remaining))
                if process.poll() is None:
                    self.check()
            result = subprocess.CompletedProcess(command, process.poll())
        self.check()
        if check:
            result.check_returncode()
        return result


class OwnedCommand:
    """Own one command group until teardown.

    Windows suspended assignment closes the child-spawn race before monitoring.
    POSIX callers must not let another thread/library reap this child or change
    SIGCHLD handling during its lifetime. Only this wrapper may release its PID;
    a detected external reap fails closed but cannot make concurrent reaping safe.
    """
    def __init__(self, command, *, cwd, stdout, stderr, input):
        self.job = self.handle = None
        self.process = None
        self.stdin = None
        if os.name != 'nt':
            import signal
            if not all(hasattr(os, name) for name in (
                    'waitid', 'P_PID', 'WEXITED', 'WNOHANG', 'WNOWAIT',
                    'CLD_EXITED', 'CLD_KILLED', 'CLD_DUMPED')):
                raise RetentionError('Owned POSIX commands require non-reaping waitid support')
            if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
                raise RetentionError('Owned POSIX commands require the default SIGCHLD handler')
            self._posix_closed = False
            self.process = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr,
                                            stdin=subprocess.PIPE if input is not None else None,
                                            start_new_session=True)
            if input is not None:
                self.process.stdin.write(input)
                self.process.stdin.close()
            return
        import _winapi
        import msvcrt
        from ctypes import wintypes as w
        self.winapi = _winapi
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        def bind(name, result, args):
            f = getattr(self.k, name)
            f.restype, f.argtypes = result, args
            return f
        self.close = bind('CloseHandle', w.BOOL, [w.HANDLE])
        self.stop = bind('TerminateJobObject', w.BOOL, [w.HANDLE, w.UINT])
        create = bind('CreateJobObjectW', w.HANDLE, [ctypes.c_void_p, w.LPCWSTR])
        assign = bind('AssignProcessToJobObject', w.BOOL, [w.HANDLE, w.HANDLE])
        setinfo = bind('SetInformationJobObject', w.BOOL, [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD])
        resume = bind('ResumeThread', w.DWORD, [w.HANDLE])
        class Basic(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64), ('flags', w.DWORD),
                        ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t), ('active', w.DWORD),
                        ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        # Basic information accepts KILL_ON_JOB_CLOSE only via the extended structure.
        class Extended(ctypes.Structure):
            _fields_ = [('basic', Basic), ('io', ctypes.c_uint64 * 6),
                        ('limits', ctypes.c_size_t * 4)]
        self.job = create(None, None)
        if not self.job:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = Extended()
        limits.basic.flags = 0x2000 | 0x20
        limits.basic.priority = 0x4000
        if not setinfo(self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            self.close(self.job)
            raise ctypes.WinError(ctypes.get_last_error())
        import tempfile
        self.stdin = tempfile.TemporaryFile()
        if input is not None:
            self.stdin.write(input)
            self.stdin.seek(0)
        si = subprocess.STARTUPINFO()
        si.dwFlags = subprocess.STARTF_USESTDHANDLES
        if stdout is None or not hasattr(stdout, 'fileno'):
            self.stdin.close()
            self.close(self.job)
            raise RetentionError('Owned command requires a retained output log')
        si.hStdInput = msvcrt.get_osfhandle(self.stdin.fileno())
        si.hStdOutput = msvcrt.get_osfhandle(stdout.fileno())
        si.hStdError = si.hStdOutput if stderr == subprocess.STDOUT else msvcrt.get_osfhandle(stderr.fileno())
        for handle in (si.hStdInput, si.hStdOutput, si.hStdError):
            os.set_handle_inheritable(handle, True)
        thread = None
        try:
            self.handle, thread, self.pid, _ = _winapi.CreateProcess(
                None, subprocess.list2cmdline(list(map(str, command))), None, None, True,
                0x4 | 0x08000000 | 0x4000, None, str(cwd) if cwd else None, si)
            if not assign(self.job, self.handle):
                _winapi.TerminateProcess(self.handle, 90)
                raise ctypes.WinError(ctypes.get_last_error())
            if resume(thread) == 0xffffffff:
                raise ctypes.WinError(ctypes.get_last_error())
        except BaseException:
            self.__exit__(None, None, None)
            raise
        finally:
            if thread:
                self.close(thread)

    def poll(self):
        if self.process is not None:
            if self._posix_closed:
                return self.process.returncode
            try:
                # Keep the leader waitable, reserving its PID/PGID until the
                # entire owned group is signalled. Popen.poll/wait would reap.
                result = os.waitid(os.P_PID, self.process.pid,
                                   os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except ChildProcessError as error:
                raise RetentionError('Owned leader was reaped; refusing process-group signal') from error
            if result is None:
                return None
            if result.si_pid != self.process.pid:
                raise RetentionError('Unexpected owned-process wait identity')
            if result.si_code == os.CLD_EXITED:
                return result.si_status
            if result.si_code in (os.CLD_KILLED, os.CLD_DUMPED):
                return -result.si_status
            raise RetentionError('Unexpected owned-process wait status')
        code = self.winapi.GetExitCodeProcess(self.handle)
        return None if code == 259 else code

    def __enter__(self):
        return self

    def wait(self, seconds):
        if self.process is not None:
            deadline = time.monotonic() + seconds
            while True:
                result = self.poll()
                if result is not None:
                    return result
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                time.sleep(min(.05, remaining))
        self.winapi.WaitForSingleObject(self.handle, int(seconds * 1000))
        return self.poll()

    def __exit__(self, *exc):
        if self.process is not None:
            if self._posix_closed:
                return
            import signal
            self.poll()  # Fail closed if an external reaper broke ownership.
            # No monitoring path reaps the leader, so this numeric group ID
            # cannot be reused even if all descendants have already exited.
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self._posix_closed = True
            self.process.wait()  # Reap only after the final group signal.
            return
        if self.job:
            self.stop(self.job, 90)
            if self.handle:
                self.winapi.WaitForSingleObject(self.handle, 10000)
                self.close(self.handle)
            self.close(self.job)
            self.job = None
        if self.stdin:
            self.stdin.close()


def register_runtime(state, directory, runtime, name):
    directory, runtime = Path(directory).resolve(), Path(runtime).absolute()
    if runtime.parent != directory or not RUNTIME.fullmatch(runtime.name):
        raise RetentionError('Runtime must be a direct owned run subdirectory')
    expected = 'pyfa-local-' + directory.name.replace('.', '-')
    if runtime.name != 'avd':
        expected += '-r' + runtime.name.split('-r')[1]
        if runtime.name.startswith('avd-c04-'):
            expected += '-c04'
    if name != expected:
        raise RetentionError('Unexpected runtime identity')
    row = dict(directory=runtime.name, avd_name=name)
    owners = state.setdefault('owned_runtime_avds', [])
    if row not in owners:
        owners.append(row)


def cleanup_verified_runtime(directory, *, stopped):
    """Delete only registered, unredirected runtimes after all evidence validates."""
    directory = Path(directory).resolve(strict=True)
    state = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
    if not stopped or state.get('status') != 'passed' or state.get('plan') != state.get('completed'):
        raise RetentionError('Preserve non-completed or running guest state')
    latest = {r['gate']: r for r in state['attempts']}
    if not state['plan'] or any(g not in latest or latest[g].get('exit_code') != 0 for g in state['plan']):
        raise RetentionError('Missing successful gate proof')
    manifest = json.loads((directory / 'files.json').read_text(encoding='utf-8'))
    if 'run.json' not in manifest:
        raise RetentionError('Run state must be hash-bound')
    for relative, row in manifest.items():
        path = directory / relative
        if RUNTIME.fullmatch(Path(relative).parts[0]):
            raise RetentionError('Runtime is referenced by retained evidence; preserve it')
        if not path.resolve().is_relative_to(directory) or redirect(path):
            raise RetentionError('Redirected evidence')
        if path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            raise RetentionError('Changed retained evidence: ' + relative)
    targets = []
    if len({row['directory'] for row in state.get('owned_runtime_avds', [])}) != len(state.get('owned_runtime_avds', [])):
        raise RetentionError('Duplicate runtime ownership record')
    for owner in state.get('owned_runtime_avds', []):
        relative, name = owner['directory'], owner['avd_name']
        register_runtime({}, directory, directory / relative, name)
        target = directory / relative
        if not target.exists():
            continue
        if target.resolve().parent != directory or redirect(target):
            raise RetentionError('Unsafe runtime target')
        if {p.name for p in target.iterdir()} != {name + '.ini', name + '.avd'}:
            raise RetentionError('Unrecognized contents in owned runtime root')
        # Validate every deletion target before removing any root.
        pending = [target]
        while pending:
            path = pending.pop()
            if redirect(path) or not path.resolve().is_relative_to(target.resolve()):
                raise RetentionError('Runtime contains redirected data')
            if path.is_dir():
                pending.extend(path.iterdir())
        ini = dict(line.split('=', 1) for line in (target / (name + '.ini')).read_text().splitlines() if '=' in line)
        if Path(ini.get('path', '')).resolve() != (target / (name + '.avd')).resolve():
            raise RetentionError('AVD locator points outside its owned root')
        targets.append(target)
    unregistered = [p.name for p in directory.iterdir() if RUNTIME.fullmatch(p.name) and p not in targets]
    existing_registered = {row['directory'] for row in state.get('owned_runtime_avds', [])}
    if any(name not in existing_registered for name in unregistered):
        raise RetentionError('Unregistered runtime: preserve until ownership is reviewed')
    for target in targets:
        # Absolute resolved paths were checked within the exact run above.
        shutil.rmtree(target)
    result = dict(removed=[p.name for p in targets], evidence_preserved=True,
                  registered=sorted(existing_registered), all_owned_absent=True)
    receipt = directory / 'runtime-cleanup.json'
    if targets or not receipt.exists():
        temporary = directory / 'runtime-cleanup.json.tmp'
        temporary.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        temporary.replace(receipt)
        manifest[receipt.name] = dict(bytes=receipt.stat().st_size, sha256=digest(receipt))
        temporary = directory / 'files.json.tmp'
        temporary.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
        temporary.replace(directory / 'files.json')
    return result


def validate_cleanup_receipt(directory, state, manifest):
    if state.get('artifact_retention', {}).get('version') != 1:
        return  # Historical receipts retain their original evidence contract.
    directory = Path(directory)
    receipt = directory / 'runtime-cleanup.json'
    expected = manifest.get(receipt.name)
    if (not expected or not receipt.is_file() or receipt.stat().st_size != expected['bytes'] or
            digest(receipt) != expected['sha256']):
        raise RetentionError('Missing or changed runtime cleanup receipt')
    result = json.loads(receipt.read_text(encoding='utf-8'))
    for owner in state.get('owned_runtime_avds', []):
        register_runtime({}, directory, directory / owner['directory'], owner['avd_name'])
    registered = sorted(row['directory'] for row in state.get('owned_runtime_avds', []))
    if (result.get('registered') != registered or result.get('all_owned_absent') is not True or
            result.get('evidence_preserved') is not True):
        raise RetentionError('Incomplete owned runtime cleanup')
    if any((directory / name).exists() for name in registered):
        raise RetentionError('Owned runtime still exists after claimed cleanup')

