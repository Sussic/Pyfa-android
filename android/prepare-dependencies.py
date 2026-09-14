"""Build upstream's supported pure-Python wheels and fetch pinned Android wheels.

Build-time networking only. No host-native wheel is copied into the APK.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
from zipfile import ZipFile
from wheel.wheelfile import WheelFile

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build/python-wheels"
SOURCES = (
    ("https://files.pythonhosted.org/packages/cc/98/c1d93c1d7593f58515333a6217aa4ae647d9ee9c1aa2dfdf77b28b7bb7c7/Logbook-1.7.0.post0.tar.gz",
     "a5e8016701ca3beea6a390b0ba1541037f663543ca508ccd36cfdc841639cdd7"),
    ("https://files.pythonhosted.org/packages/5a/0a/dabe332c40afebb0a979d3e66b34570fce2f8611bae19b186f0c69f54643/SQLAlchemy-1.4.50.tar.gz",
     "3b97ddf509fc21e10b09403b5219b06c5b558b27fc2453150274fa4e70707dbf"),
)
NATIVE = {
    "arm64_v8a": "0e3b535f8f3d52a270a8638150934f0d88f6951191f27c350a66d8a0ab88a4e6",
    "x86_64": "b0d0eaef9d0fbfdacd9bbd09fb1c64403fa640610d9ce7021df842af217bbb03",
}
LIBCXX = {
    "arm64_v8a": "811547210b01eefb0fb850fd35bd27b53a00a76b9466b8c03e049b7e8175004b",
    "x86_64": "dd56e48a66d08e352a1aacb6e3e9ff50788ae1b140b30bbd33d8bbb6854390c4",
}


def download(url, sha, directory):
    path = directory / url.rsplit("/", 1)[1]
    if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != sha:
            raise ValueError("Dependency checksum mismatch: " + path.name)
        path.write_bytes(data)
    return path


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sources = ROOT / "build/python-sources"
    sources.mkdir(exist_ok=True)
    env = dict(os.environ, DISABLE_LOGBOOK_CEXT="1", DISABLE_SQLALCHEMY_CEXT="1")
    for url, sha in SOURCES:
        path = download(url, sha, sources)
        subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation",
                        "--no-cache-dir", "--wheel-dir", str(OUT), str(path)], env=env, check=True)
    # SQLAlchemy 1.4's Distribution.has_ext_modules always returns True, even
    # with its supported DISABLE_SQLALCHEMY_CEXT switch. Correct only the wheel
    # metadata after proving the build contains no native binaries. Never retag
    # a compiled host library. WheelFile regenerates all RECORD hashes.
    for host in OUT.glob("SQLAlchemy-1.4.50-*.whl"):
        if host.name.endswith("-none-any.whl"):
            continue
        with ZipFile(host) as source:
            entries = {name: source.read(name) for name in source.namelist()}
        assert not any(name.endswith((".so", ".pyd", ".dll", ".dylib")) or
                       raw.startswith(b"\x7fELF") or ".data/platlib/" in name
                       for name, raw in entries.items())
        with WheelFile(OUT / "SQLAlchemy-1.4.50-py3-none-any.whl", "w") as target:
            for name, raw in entries.items():
                if name.endswith(".dist-info/RECORD"):
                    continue
                if name.endswith(".dist-info/WHEEL"):
                    raw = ("Wheel-Version: 1.0\nGenerator: pyfa-pure-sqlalchemy\n"
                           "Root-Is-Purelib: true\nTag: py3-none-any\n").encode()
                target.writestr(name, raw)
        host.unlink()
    for abi, sha in NATIVE.items():
        download(f"https://chaquo.com/pypi-13.1/greenlet/greenlet-3.0.1-1-cp311-cp311-android_24_{abi}.whl", sha, OUT)
    for abi, sha in LIBCXX.items():
        download(f"https://chaquo.com/pypi-13.1/chaquopy-libcxx/chaquopy_libcxx-180000-0-py3-none-android_24_{abi}.whl", sha, OUT)
    wheels = sorted(OUT.glob("*.whl"))
    if len(wheels) != 6:
        raise ValueError("Expected exactly two pure and four Android wheels; clean build/python-wheels")
    receipt = {}
    for path in wheels:
        with ZipFile(path) as wheel:
            if path.name.startswith(("Logbook-", "SQLAlchemy-")):
                assert path.name.endswith("-none-any.whl")
                assert not any(name.endswith((".so", ".pyd")) for name in wheel.namelist())
            metadata = wheel.read(next(n for n in wheel.namelist() if n.endswith(".dist-info/METADATA"))).decode()
            receipt[path.name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                  "requires": [line for line in metadata.splitlines() if line.startswith("Requires-Dist:")]}
    evidence = ROOT / "build/evidence"
    evidence.mkdir(exist_ok=True)
    (evidence / "python-wheels.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
