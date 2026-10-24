"""Verify build outputs: check the real file format, and run/install them where this computer can."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path


def _magic(path: Path, n: int = 4) -> bytes:
    with open(path, "rb") as f:
        return f.read(n)


def check(kind: str, path: Path, sandbox_image: str = "mirror.gcr.io/library/debian:trixie-slim") -> tuple[bool, str]:
    path = Path(path)
    if kind == "pe":
        ok = _magic(path, 2) == b"MZ"
        note = " Run it with Wine or on Windows to test behaviour." if not shutil.which("wine") else ""
        if ok and shutil.which("wine"):
            r = subprocess.run(["wine", str(path), "--version"], capture_output=True, text=True, timeout=120)
            return r.returncode == 0, f"Windows EXE ran under Wine: {r.stdout.strip()[:200]}"
        return ok, ("valid Windows PE executable." + note) if ok else "not a Windows executable"
    if kind == "elf":
        ok = _magic(path) == b"\x7fELF"
        native = sys.platform.startswith("linux") and platform.machine().lower() in ("x86_64", "amd64") and \
            ("amd64" in path.name or "x86_64" in path.name)
        if ok and native:
            r = subprocess.run([str(path), "--version"], capture_output=True, text=True, timeout=60)
            return r.returncode == 0, f"Linux binary ran: {(r.stdout + r.stderr).strip()[:200]}"
        return ok, "valid ELF executable" if ok else "not an ELF executable"
    if kind == "macho":
        ok = _magic(path) in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xce\xfa\xed\xfe")
        return ok, "valid macOS Mach-O executable (run it on a Mac to test behaviour)" if ok else "not a Mach-O binary"
    if kind == "apk":
        try:
            names = set(zipfile.ZipFile(path).namelist())
        except zipfile.BadZipFile:
            return False, "not a valid APK (zip) file"
        ok = "AndroidManifest.xml" in names and any(n.startswith("classes") and n.endswith(".dex") for n in names)
        signed = any(n.startswith("META-INF/") and n.endswith((".RSA", ".EC", ".DSA")) for n in names)
        return ok, f"APK structure ok, {'signed (v1)' if signed else 'v1 signature not found (v2+ may still exist)'}; " \
                   "install on an emulator/device to test behaviour"
    if kind in ("zip", "extension", "web"):
        try:
            z = zipfile.ZipFile(path)
            bad = z.testzip()
        except zipfile.BadZipFile:
            return False, "not a valid zip"
        if bad:
            return False, f"corrupt entry {bad}"
        names = z.namelist()
        if kind == "extension":
            if "manifest.json" not in names:
                return False, "manifest.json missing at the root"
            m = json.loads(z.read("manifest.json"))
            return m.get("manifest_version") in (2, 3), f"extension manifest v{m.get('manifest_version')}, {len(names)} files"
        if kind == "web":
            return "index.html" in names, f"{len(names)} files" + ("" if "index.html" in names else ", index.html missing")
        return True, f"valid archive with {len(names)} files"
    if kind == "targz":
        with tarfile.open(path) as t:
            return True, f"valid tar.gz with {len(t.getnames())} entries"
    if kind == "wheel":
        venv = Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True)
        py = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        r = subprocess.run([str(py), "-m", "pip", "install", "--no-deps", "-q", str(path)], capture_output=True, text=True)
        shutil.rmtree(venv, ignore_errors=True)
        return r.returncode == 0, "wheel installs into a clean environment" if r.returncode == 0 else r.stderr[-500:]
    if kind == "npm":
        with tarfile.open(path) as t:
            ok = "package/package.json" in t.getnames()
        return ok, "npm package contains package.json" if ok else "package.json missing"
    if kind == "deb":
        if not shutil.which("docker"):
            r = subprocess.run(["dpkg-deb", "--info", str(path)], capture_output=True, text=True)
            return r.returncode == 0, "deb metadata ok (Docker not available for an install test)"
        cmd = ["docker", "run", "--rm", "-v", f"{path.parent}:/pkg", sandbox_image, "sh", "-c",
               f"dpkg -i /pkg/{path.name} && dpkg -L $(dpkg-deb -f /pkg/{path.name} Package) | head -20"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return r.returncode == 0, ("installed cleanly in a fresh Debian container:\n" + r.stdout[-800:]) \
            if r.returncode == 0 else r.stderr[-800:]
    if kind == "iso":
        with open(path, "rb") as f:
            f.seek(0x8001)
            ok = f.read(5) == b"CD001"
        boot = " Boot test: install QEMU to boot it and capture the screen." if not shutil.which("qemu-system-x86_64") else ""
        return ok, ("valid ISO 9660 image." + boot) if ok else "not an ISO 9660 image"
    if kind == "pdf":
        return _magic(path, 4) == b"%PDF", "valid PDF" if _magic(path, 4) == b"%PDF" else "not a PDF"
    return True, "no automatic check for this output"


def check_docker_image(tag: str, port: int | None = None, health_path: str = "/health") -> tuple[bool, str]:
    args = ["docker", "run", "-d", "--rm"] + (["-p", f"127.0.0.1::{port}"] if port else []) + [tag]
    r = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        return False, r.stderr[-800:]
    cid = r.stdout.strip()
    try:
        import time
        time.sleep(3)
        state = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", cid], capture_output=True, text=True)
        if state.stdout.strip() != "true":
            logs = subprocess.run(["docker", "logs", cid], capture_output=True, text=True).stdout
            return False, "container exited:\n" + logs[-800:]
        if port:
            mapped = subprocess.run(["docker", "port", cid, str(port)], capture_output=True, text=True).stdout.strip()
            import httpx
            hp = mapped.split(":")[-1]
            for _ in range(10):
                try:
                    resp = httpx.get(f"http://127.0.0.1:{hp}{health_path}", timeout=5, follow_redirects=True)
                    return resp.status_code < 400, f"container answers {health_path}: HTTP {resp.status_code}"
                except httpx.HTTPError:
                    time.sleep(2)
            return False, "container is running but does not answer HTTP"
        return True, "container starts and keeps running"
    finally:
        subprocess.run(["docker", "rm", "-f", cid], capture_output=True)
