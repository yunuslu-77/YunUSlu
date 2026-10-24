"""Packagers implemented in Python: .deb from built binaries, and manifests for winget, Homebrew and the AUR."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile
from pathlib import Path


def build_deb(root: Path, name: str, version: str, binary: Path, description: str, maintainer: str,
              arch: str = "amd64") -> Path:
    if not shutil.which("dpkg-deb"):
        raise RuntimeError("dpkg-deb is not installed (it is available on Debian/Ubuntu, or in the linux-pkg builder).")
    pkg = Path(tempfile.mkdtemp()) / f"{name}_{version}_{arch}"
    (pkg / "DEBIAN").mkdir(parents=True)
    (pkg / "usr/bin").mkdir(parents=True)
    shutil.copy2(binary, pkg / "usr/bin" / name)
    (pkg / "usr/bin" / name).chmod(0o755)
    (pkg / "DEBIAN/control").write_text(
        f"Package: {name}\nVersion: {version}\nArchitecture: {arch}\nMaintainer: {maintainer}\n"
        f"Section: utils\nPriority: optional\nDescription: {description}\n", "utf-8")
    out = Path(root) / "dist"
    out.mkdir(exist_ok=True)
    subprocess.run(["dpkg-deb", "--build", "--root-owner-group", str(pkg), str(out)], check=True, capture_output=True)
    shutil.rmtree(pkg.parent, ignore_errors=True)
    return out / f"{name}_{version}_{arch}.deb"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def winget_manifest(root: Path, publisher: str, name: str, version: str, installer_url: str, sha256: str,
                    description: str, license_name: str) -> list[Path]:
    ident = f"{publisher}.{name}".replace(" ", "")
    d = Path(root) / "packaging" / "winget"
    d.mkdir(parents=True, exist_ok=True)
    files = {
        f"{ident}.yaml": f"PackageIdentifier: {ident}\nPackageVersion: {version}\nDefaultLocale: tr-TR\n"
                         "ManifestType: version\nManifestVersion: 1.6.0\n",
        f"{ident}.installer.yaml": f"PackageIdentifier: {ident}\nPackageVersion: {version}\nInstallers:\n"
                                   f"  - Architecture: x64\n    InstallerType: inno\n    InstallerUrl: {installer_url}\n"
                                   f"    InstallerSha256: {sha256.upper()}\nManifestType: installer\nManifestVersion: 1.6.0\n",
        f"{ident}.locale.tr-TR.yaml": f"PackageIdentifier: {ident}\nPackageVersion: {version}\nPackageLocale: tr-TR\n"
                                      f"Publisher: {publisher}\nPackageName: {name}\nLicense: {license_name}\n"
                                      f"ShortDescription: {description}\nManifestType: defaultLocale\nManifestVersion: 1.6.0\n",
    }
    out = []
    for fname, text in files.items():
        (d / fname).write_text(text, "utf-8")
        out.append(d / fname)
    return out


def homebrew_formula(root: Path, name: str, version: str, url: str, sha256: str, description: str,
                     homepage: str, license_name: str, binary: str | None = None) -> Path:
    cls = "".join(p.capitalize() for p in name.replace("_", "-").split("-"))
    d = Path(root) / "packaging" / "homebrew"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{name}.rb"
    p.write_text(f'class {cls} < Formula\n  desc "{description}"\n  homepage "{homepage}"\n  url "{url}"\n'
                 f'  sha256 "{sha256}"\n  version "{version}"\n  license "{license_name}"\n\n'
                 f'  def install\n    bin.install "{binary or name}"\n  end\n\n'
                 f'  test do\n    system "#{{bin}}/{binary or name}", "--version"\n  end\nend\n', "utf-8")
    return p


def aur_pkgbuild(root: Path, name: str, version: str, url: str, sha256: str, description: str, homepage: str,
                 license_name: str, maintainer: str) -> Path:
    d = Path(root) / "packaging" / "aur"
    d.mkdir(parents=True, exist_ok=True)
    p = d / "PKGBUILD"
    p.write_text(f"# Maintainer: {maintainer}\npkgname={name}-bin\npkgver={version}\npkgrel=1\n"
                 f"pkgdesc=\"{description}\"\narch=('x86_64')\nurl=\"{homepage}\"\nlicense=('{license_name}')\n"
                 f"source=(\"{url}\")\nsha256sums=('{sha256}')\n\npackage() {{\n"
                 f"  install -Dm755 \"$srcdir/{name}\" \"$pkgdir/usr/bin/{name}\"\n}}\n", "utf-8")
    return p
