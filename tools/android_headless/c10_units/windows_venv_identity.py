"""Windows CPython3.11.9 venv identity observations for bounded verification only."""
import ctypes
from ctypes import wintypes
import hashlib
import importlib.metadata
import os
from pathlib import Path
import platform
import site
import struct
import sys

LAUNCHER_SHA256 = "21bb438c0d4a6f1f164b9a646f6ee000340185e5871180aec06db8d3f07c0082"
DEPENDENCIES = {"logbook": "1.7.0.post0", "sqlalchemy": "1.4.50", "greenlet": "3.0.3"}
FORBIDDEN = ("wxPython", "numpy", "cryptography", "pyyaml", "pillow")
_KERNEL = None


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalized(path):
    return os.path.normcase(str(Path(path).resolve(strict=True)))


def api():
    global _KERNEL
    require(os.name == "nt", "Native Windows observations are required")
    if _KERNEL is None:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        declarations = {
            "OpenProcess": ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            "GetProcessId": ([wintypes.HANDLE], wintypes.DWORD),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            "WaitForSingleObject": ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            "GetProcessTimes": ([wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4, wintypes.BOOL),
            "QueryFullProcessImageNameW": ([wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                           ctypes.POINTER(wintypes.DWORD)], wintypes.BOOL),
            "IsProcessInJob": ([wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)], wintypes.BOOL),
        }
        for name, (arguments, result) in declarations.items():
            function = getattr(kernel, name)
            function.argtypes, function.restype = arguments, result
        _KERNEL = kernel
    return _KERNEL


def checked(value, operation):
    if not value:
        raise OSError(ctypes.get_last_error(), operation)
    return value


def creation_time(handle):
    values = [wintypes.FILETIME() for _ in range(4)]
    checked(api().GetProcessTimes(handle, *(ctypes.byref(value) for value in values)), "GetProcessTimes")
    return (int(values[0].dwHighDateTime) << 32) | int(values[0].dwLowDateTime)


class Process:
    """Keep one exact kernel process object; PID enumeration is not liveness."""
    def __init__(self, pid):
        require(type(pid) is int and pid > 0, "A positive process PID is required")
        self.handle = checked(api().OpenProcess(0x1000 | 0x100000, False, pid), "OpenProcess limited query/synchronize")
        self.pid = pid

    def __enter__(self):
        return self

    def __exit__(self, *ignored):
        handle, self.handle = self.handle, None
        checked(api().CloseHandle(handle), "CloseHandle")

    def alive(self):
        result = api().WaitForSingleObject(self.handle, 0)
        if result == 258:  # WAIT_TIMEOUT: nonsignaled, not GetExitCodeProcess's ambiguous259.
            return True
        if result == 0:
            return False
        raise OSError(ctypes.get_last_error(), "Process wait failed")

    def snapshot(self):
        require(self.alive(), "Observed process already exited")
        pid = int(checked(api().GetProcessId(self.handle), "GetProcessId"))
        require(pid == self.pid, "Retained process handle PID differs")
        image = ctypes.create_unicode_buffer(32768)
        count = wintypes.DWORD(len(image))
        checked(api().QueryFullProcessImageNameW(self.handle, 0, image, ctypes.byref(count)),
                "QueryFullProcessImageNameW")
        path = str(Path(image.value).resolve(strict=True))
        in_job = wintypes.BOOL()
        checked(api().IsProcessInJob(self.handle, None, ctypes.byref(in_job)), "IsProcessInJob(any)")
        result = {"pid": pid, "creation_filetime": creation_time(self.handle),
                  "image_path": path, "image_sha256": sha(path), "in_any_job": bool(in_job.value),
                  "live_before_query": True}
        require(self.alive(), "Observed process exited during its identity query")
        result["live_after_query"] = True
        return result


def same_process(actual, expected):
    for key in ("pid", "creation_filetime", "image_sha256"):
        require(type(actual[key]) is type(expected[key]) and actual[key] == expected[key],
                "Retained process identity differs: " + key)
    require(normalized(actual["image_path"]) == normalized(expected["image_path"]), "Process image path differs")
    require(actual["in_any_job"] is True and expected["in_any_job"] is True,
            "Job membership corroboration is missing")


def runtime_snapshot():
    require(sys.implementation.name == "cpython" and sys.version_info[:3] == (3, 11, 9),
            "Qualified CPython3.11.9 is required")
    require(sys.flags.isolated and sys.flags.ignore_environment and not sys.flags.no_site
            and sys.dont_write_bytecode and site.ENABLE_USER_SITE is False, "Use isolated -I -B with venv site enabled")
    require(struct.calcsize("P") == 8 and platform.machine().casefold() in ("amd64", "x86_64"),
            "Qualified native x64 interpreter is required")
    executable, base = normalized(sys.executable), normalized(sys._base_executable)
    prefix, base_prefix = normalized(sys.prefix), normalized(sys.base_prefix)
    require(executable != base and prefix != base_prefix, "Expected a qualified Windows venv redirector")
    cfg = Path(prefix) / "pyvenv.cfg"
    settings = {}
    for line in cfg.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.partition("=")
        if separator:
            settings[key.strip().casefold()] = value.strip()
    require(settings.get("include-system-site-packages", "").casefold() == "false", "System site packages are forbidden")
    require(normalized(settings["home"]) == normalized(Path(base).parent), "Venv home/base mismatch")
    require(sha(executable) == LAUNCHER_SHA256, "Qualified launcher bytes differ")
    roots = {}
    for name, version in DEPENDENCIES.items():
        distribution = importlib.metadata.distribution(name)
        require(distribution.version == version, "Pinned metadata differs: " + name)
        root = Path(distribution.locate_file("")).resolve(strict=True)
        require(root.is_relative_to(Path(prefix)), "Dependency metadata escaped selected venv: " + name)
        roots[name] = str(root)
    for name in FORBIDDEN:
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            continue
        raise RuntimeError("Forbidden headless package: " + name)
    return {"version": list(sys.version_info[:3]), "bits": 64, "executable": executable,
            "base_executable": base, "prefix": prefix, "base_prefix": base_prefix,
            "launcher_sha256": sha(executable), "base_sha256": sha(base),
            "pyvenv_cfg_sha256": sha(cfg), "dependencies": DEPENDENCIES,
            "distribution_roots": roots, "isolated": True, "user_site_enabled": False}


def current_identity():
    runtime = runtime_snapshot()
    with Process(os.getpid()) as process:
        identity = process.snapshot()
    require(normalized(identity["image_path"]) == runtime["base_executable"]
            and identity["image_sha256"] == runtime["base_sha256"], "Actual interpreter image differs from base")
    require(identity["in_any_job"], "Canonical guarded job membership is required")
    identity.update(parent_pid=os.getppid(), runtime=runtime)
    return identity


def launcher_parent(identity):
    with Process(identity["parent_pid"]) as process:
        parent = process.snapshot()
    require(parent["creation_filetime"] < identity["creation_filetime"], "Parent birth is not earlier")
    require(normalized(parent["image_path"]) == identity["runtime"]["executable"]
            and parent["image_sha256"] == LAUNCHER_SHA256 and parent["in_any_job"],
            "Writer parent is not the qualified guarded venv redirector")
    parent["role"] = "qualified_venv_redirector"
    return parent


def direct_venv_command(command):
    runtime = runtime_snapshot()
    require(normalized(command[0]) == runtime["executable"], "Only the qualified venv command may be redirected")
    child = [runtime["base_executable"], *command[1:]]
    environment = os.environ.copy()
    environment.pop("PYTHONEXECUTABLE", None)
    environment["__PYVENV_LAUNCHER__"] = runtime["executable"]
    return child, environment

