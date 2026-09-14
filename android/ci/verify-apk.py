"""Inspect real APK bytes, including Chaquopy's nested Python/ABI archives."""
import hashlib
import io
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from zipfile import ZipFile, is_zipfile

ROOT = Path(__file__).resolve().parents[1]
APK = ROOT / "app/build/outputs/apk/debug/app-debug.apk"
ABIS = {"arm64-v8a": 183, "x86_64": 62}
SYSTEM = {"libc.so", "libm.so", "libdl.so", "liblog.so", "libandroid.so", "libz.so"}


def main():
    with ZipFile(APK) as apk:
        assert apk.read("assets/LICENSE") == (ROOT.parent / "LICENSE").read_bytes()
        manifest = json.loads(apk.read("assets/engine/manifest.json"))
        database = apk.read("assets/engine/eve.db")
        assert len(database) == manifest["database_bytes"]
        assert hashlib.sha256(database).hexdigest() == manifest["database_sha256"]
        assert apk.read("assets/engine/vexor.json") == (ROOT.parent / "tools/android_reference/vexor.json").read_bytes()
        files = {}
        for name in apk.namelist():
            if name.endswith(".so"):
                files[name] = apk.read(name)
            elif name.startswith("assets/chaquopy/") and name.endswith((".imy", ".zip")):
                raw = apk.read(name)
                assert is_zipfile(io.BytesIO(raw)), name
                with ZipFile(io.BytesIO(raw)) as archive:
                    for inner in archive.namelist():
                        files[name + "!/" + inner] = archive.read(inner)
        for name, digest in manifest["engine_sources"].items():
            current = (ROOT.parent / name).read_bytes().replace(b"\r\n", b"\n")
            assert hashlib.sha256(current).hexdigest() == digest, "Stale generated source: " + name
            matches = [raw for path, raw in files.items() if path.endswith("!/" + name)]
            assert len(matches) == 1, "Missing or duplicated engine source: " + name
            assert hashlib.sha256(matches[0]).hexdigest() == digest, name
        mobile = (ROOT / "app/src/main/python/mobile_runtime.py").read_bytes().replace(b"\r\n", b"\n")
        mobile_files = [raw for path, raw in files.items() if path.endswith("!/mobile_runtime.py")]
        assert len(mobile_files) == 1, "Missing or duplicated mobile_runtime.py in Chaquopy sources"
        # Root .gitattributes uses CRLF for Python. Compare normalized source on
        # both sides, as the engine staging/data provenance checks already do.
        assert mobile_files[0].replace(b"\r\n", b"\n") == mobile, "Stale mobile_runtime.py in APK"
        assert not any("vexor-expected.json" in name or "tools/android_reference/fixtures" in name for name in apk.namelist())
        assert not any("!/wx/" in name or "!/gui/" in name or "!/service/" in name for name in files)
    receipt = {"database_bytes": len(database), "database_sha256": manifest["database_sha256"],
               "database_logical_sha256": manifest["database_logical_sha256"],
               "engine_source_sha256": manifest["engine_source_sha256"],
               "engine_source_files": len(manifest["engine_sources"]), "abis": {}}
    with tempfile.TemporaryDirectory() as directory:
        temporary = Path(directory) / "library.so"
        for abi, machine in ABIS.items():
            libraries = {}
            for name, data in files.items():
                if not name.endswith(".so") or abi not in name:
                    continue
                assert data[:4] == b"\x7fELF" and data[4:6] == b"\x02\x01", name
                assert struct.unpack_from("<H", data, 18)[0] == machine, name
                temporary.write_bytes(data)
                dynamic = subprocess.check_output(["readelf", "-d", str(temporary)], text=True)
                needed = re.findall(r"\(NEEDED\).*?\[(.*?)\]", dynamic)
                libraries[name] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "needed": needed}
            assert any(name.endswith("/libpython3.11.so") for name in libraries), abi
            assert any(name.endswith("/greenlet/_greenlet.so") for name in libraries), abi
            assert any("/_sqlite3" in name for name in libraries), abi
            shipped = {name.rsplit("/", 1)[-1] for name in libraries}
            for name, info in libraries.items():
                assert set(info["needed"]) <= shipped | SYSTEM, (name, set(info["needed"]) - shipped - SYSTEM)
            receipt["abis"][abi] = {"elf_machine": machine, "libraries": libraries, "runtime_tested": False}
    evidence = ROOT / "build/evidence"
    (evidence / "apk-contents.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"Verified bundled database, {receipt['engine_source_files']} source files, ARM64/x86_64 ELF architectures and dependencies")


if __name__ == "__main__":
    main()
