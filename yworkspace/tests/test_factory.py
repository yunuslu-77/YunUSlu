import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from yworkspace.app import build_session
from yworkspace.config import Config
from yworkspace.factory.recipes import all_recipes
from yworkspace.sandbox import docker_available

EXT = Path(__file__).resolve().parents[1] / "src/yworkspace/extension/browser"


def session(tmp_path, monkeypatch, name="proj"):
    monkeypatch.setenv("YW_HOME", str(tmp_path / "home"))
    return build_session(tmp_path / name, Config(sandbox="local"), with_engine=False)


def test_catalog_covers_the_plan():
    outputs = {r.output for r in all_recipes()}
    for o in ("apk", "aab", "ipa", "hap", "exe", "msi", "msix", "winget", "dmg", "pkg", "brew", "deb", "rpm",
              "appimage", "flatpak", "snap", "tar.gz", "aur", "iso", "img", "qcow2", "docker", "helm", "zip", "wasm",
              "xpi", "vsix", "wheel", "npm", "jar", "nupkg", "crate", "game", "firmware", "wgt", "ipk", "pdf", "epub",
              "docx"):
        assert o in outputs, o
    assert len({r.id for r in all_recipes()}) == len(all_recipes())


@pytest.mark.skipif(not shutil.which("go"), reason="Go not installed")
def test_go_cross_compile_and_deb(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch, "merhaba")
    root = sess.workspace.root
    (root / "go.mod").write_text("module merhaba\n\ngo 1.21\n", encoding="utf-8")
    (root / "main.go").write_text('package main\n\nimport "fmt"\n\nfunc main() { fmt.Println("merhaba 1.0") }\n', encoding="utf-8")
    call = sess.registry.call
    detected = call("factory_detect", {}).text
    assert "go-windows-exe" in detected and "go-macos-bin" in detected
    out = call("factory_build", {"recipes": ["go-linux-bin", "go-windows-exe", "go-macos-bin", "tar-gz"],
                                 "options": {"name": "merhaba", "version": "1.0.0"}}).text
    assert "✓ go-linux-bin: dist/merhaba-linux-amd64" in out
    if sys.platform == "linux":  # elsewhere a Linux program can only be checked, not run
        assert "Linux binary ran: merhaba 1.0" in out
    assert "valid Windows PE executable" in out and "valid macOS Mach-O" in out
    assert "✓ tar-gz" in out and "✗" not in out, out
    if docker_available() and shutil.which("dpkg-deb"):
        deb = call("factory_build", {"recipes": ["deb"], "options": {"name": "merhaba", "version": "1.0.0"}}).text
        assert "installed cleanly in a fresh Debian container" in deb, deb


@pytest.mark.docker
@pytest.mark.skipif(not docker_available(), reason="Docker not available")
def test_docker_image_build_and_health(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch, "webimg")
    root = sess.workspace.root
    (root / "Dockerfile").write_text(
        "FROM mirror.gcr.io/library/python:3.12-slim\nRUN useradd -m app\nUSER app\nWORKDIR /home/app\n"
        "RUN mkdir health && echo ok > health/index.html\nEXPOSE 8000\n"
        "CMD [\"python\", \"-m\", \"http.server\", \"8000\"]\n", encoding="utf-8")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    out = sess.registry.call("factory_build", {"recipes": ["docker-image"],
                                               "options": {"name": "webimg", "port": 8000}}).text
    assert "✓ docker-image" in out and "HTTP 200" in out, out


def test_extension_wheel_npm_docs_manifests(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch, "ext")
    root = sess.workspace.root
    for f in EXT.iterdir():
        shutil.copy2(f, root / f.name)
    call = sess.registry.call
    out = call("factory_build", {"recipes": ["chrome-extension", "firefox-extension"]}).text
    assert "extension manifest v3" in out and "✗" not in out, out

    sess2 = session(tmp_path, monkeypatch, "lib")
    r2 = sess2.workspace.root
    (r2 / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools>=61"]\nbuild-backend = '
                                       '"setuptools.build_meta"\n[project]\nname = "kucuk"\nversion = "0.1.0"\n', encoding="utf-8")
    (r2 / "kucuk.py").write_text("def selam():\n    return 'selam'\n", encoding="utf-8")
    (r2 / "package.json").write_text(json.dumps({"name": "kucuk", "version": "0.1.0"}), encoding="utf-8")
    (r2 / "README.md").write_text("# Küçük\n\nMerhaba dünya.\n", encoding="utf-8")
    docs = ["docs-epub", "docs-docx"] if shutil.which("pandoc") else []
    out = sess2.registry.call("factory_build", {"recipes": ["python-wheel", "npm-package", *docs],
                                                "options": {"name": "kucuk"}}).text
    assert "wheel installs into a clean environment" in out and "npm package contains package.json" in out
    assert all(d in out for d in docs) and "✗" not in out, out
    m = sess2.registry.call("package_manifests", {"kind": "homebrew", "version": "0.1.0",
                                                  "url": "https://example.com/kucuk.tar.gz"}).text
    assert "packaging/homebrew/lib.rb" in m
    assert "PackageIdentifier" in (sess2.registry.call("package_manifests", {"kind": "winget", "version": "0.1.0",
                                   "url": "https://example.com/s.exe"}) and
                                   (r2 / "packaging/winget/YunUSlu.lib.installer.yaml").read_text(encoding="utf-8"))


@pytest.mark.skipif(sys.platform == "darwin", reason="on a Mac the recipe really runs")
def test_mac_only_recipe_explains_instead_of_failing(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch, "fl")
    (sess.workspace.root / "pubspec.yaml").write_text("name: fl\ndependencies:\n  flutter:\n    sdk: flutter\n", encoding="utf-8")
    out = sess.registry.call("factory_build", {"recipes": ["flutter-ipa"]}).text
    assert "must be built on a Mac" in out and "flutter build ipa" in out


def test_options_are_sanitized(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch)
    r = sess.registry.call("factory_build", {"recipes": ["tar-gz"], "options": {"name": "x; rm -rf /"}})
    assert r.is_error and "not allowed" in r.text


@pytest.mark.skipif(not shutil.which("keytool"), reason="JDK keytool not installed")
def test_android_keystore_never_shows_secrets(tmp_path, monkeypatch):
    sess = session(tmp_path, monkeypatch, "mobil")
    out = sess.registry.call("signing_create_android", {}).text
    assert "sha256=" in out and "Back up" in out
    listed = sess.registry.call("signing_list", {}).text
    keys = json.loads((tmp_path / "home/signing/mobil/keys.json").read_text(encoding="utf-8"))
    from yworkspace.config import get_secret
    pw = get_secret(keys[0]["password_secret"])
    assert pw and pw not in out and pw not in listed
    assert not list(sess.workspace.root.rglob("*.jks"))  # key is outside the project
    r = subprocess.run(["keytool", "-list", "-keystore", keys[0]["file"], "-storepass", pw], capture_output=True)
    assert r.returncode == 0
