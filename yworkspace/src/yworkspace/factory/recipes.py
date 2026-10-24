"""Build recipes: how to turn a project into each kind of installable/distributable file.

A recipe says when it applies, where it builds (this computer, a Docker builder image, or a Mac),
the exact commands, which files it produces, and how the result is verified.
`tested_here` records whether the recipe is exercised by yWorkspace's own test suite.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

EXTRA: list = []  # plugins add recipes here


@dataclass
class Recipe:
    id: str
    output: str  # apk, exe, deb, iso, ...
    category: str  # mobile | windows | macos | linux | os-image | container | web | extension | package | game |
    # embedded | tv-watch | docs
    title: str
    applies: Callable[[Path], bool]
    commands: Callable[[Path, dict], list[str]]
    artifacts: list[str]  # glob patterns relative to the project
    builder: str = "host"  # host | docker:<image> | mac
    verify: str = ""  # verification kind, see factory.verify
    needs: list[str] = field(default_factory=list)  # accounts, licenses, hardware
    tested_here: bool = False
    network: bool = False  # the build downloads dependencies


def _has(*names: str) -> Callable[[Path], bool]:
    return lambda root: any((root / n).exists() for n in names)


def _pkg_json(root: Path) -> dict:
    p = root / "package.json"
    try:
        return json.loads(p.read_text("utf-8")) if p.exists() else {}
    except json.JSONDecodeError:
        return {}


def _deps(root: Path) -> str:
    d = _pkg_json(root)
    return " ".join([*d.get("dependencies", {}), *d.get("devDependencies", {})])


def _flutter(root):
    return (root / "pubspec.yaml").exists() and "flutter" in (root / "pubspec.yaml").read_text("utf-8")


def _android(root):
    return (root / "gradlew").exists() and ((root / "app" / "src" / "main" / "AndroidManifest.xml").exists()
                                            or "com.android" in "".join(p.read_text("utf-8", "ignore") for p in
                                                                         root.glob("*.gradle*")))


def _go(root):
    return (root / "go.mod").exists()


def _gomain(root, opts) -> str:
    return opts.get("main", ".")


def _name(root: Path, opts: dict) -> str:
    return opts.get("name") or root.name.lower().replace(" ", "-")


def _version(root: Path, opts: dict) -> str:
    return opts.get("version") or _pkg_json(root).get("version") or "0.1.0"


GO_IMAGE = "docker:mirror.gcr.io/library/golang:1.23"
FLUTTER_IMAGE = "docker:ghcr.io/cirruslabs/flutter:stable"
ANDROID_IMAGE = "docker:ghcr.io/cirruslabs/android-sdk:35"
WINE_IMAGE = "docker:electronuserland/builder:wine"
DOTNET_IMAGE = "docker:mcr.microsoft.com/dotnet/sdk:8.0"
RUST_IMAGE = "docker:mirror.gcr.io/library/rust:1"
NODE_IMAGE = "docker:mirror.gcr.io/library/node:22"
PACKER_IMAGE = "docker:hashicorp/packer:light"
LIVE_BUILD_IMAGE = "docker:yworkspace/builder-iso"  # factory/images/iso/Dockerfile
LINUXPKG_IMAGE = "docker:yworkspace/builder-linux-pkg"  # factory/images/linux-pkg/Dockerfile
GODOT_IMAGE = "docker:barichello/godot-ci:4.3"
PIO_IMAGE = "docker:yworkspace/builder-embedded"  # factory/images/embedded/Dockerfile


def all_recipes() -> list[Recipe]:
    r: list[Recipe] = [
        # ------------------------------------------------------------------ mobile
        Recipe("flutter-apk", "apk", "mobile", "Flutter → APK (Android)", _flutter,
               lambda root, o: ["flutter pub get", "flutter build apk --release"],
               ["build/app/outputs/flutter-apk/*.apk"], FLUTTER_IMAGE, "apk", network=True),
        Recipe("flutter-aab", "aab", "mobile", "Flutter → AAB (Google Play)", _flutter,
               lambda root, o: ["flutter pub get", "flutter build appbundle --release"],
               ["build/app/outputs/bundle/release/*.aab"], FLUTTER_IMAGE, "zip", ["Google Play developer account"],
               network=True),
        Recipe("flutter-ipa", "ipa", "mobile", "Flutter → IPA (iOS, needs a Mac)", _flutter,
               lambda root, o: ["flutter pub get", "flutter build ipa --release"], ["build/ios/ipa/*.ipa"], "mac",
               "zip", ["A Mac with Xcode", "Apple Developer account (yearly fee) to install on devices / App Store"],
               network=True),
        Recipe("android-apk", "apk", "mobile", "Android (Gradle) → APK", _android,
               lambda root, o: ["chmod +x gradlew", "./gradlew assembleRelease --console=plain"],
               ["app/build/outputs/apk/release/*.apk"], ANDROID_IMAGE, "apk", network=True),
        Recipe("android-aab", "aab", "mobile", "Android (Gradle) → AAB", _android,
               lambda root, o: ["chmod +x gradlew", "./gradlew bundleRelease --console=plain"],
               ["app/build/outputs/bundle/release/*.aab"], ANDROID_IMAGE, "zip", ["Google Play developer account"],
               network=True),
        Recipe("capacitor-android", "apk", "mobile", "Capacitor (web app) → Android APK",
               lambda root: "@capacitor/android" in _deps(root),
               lambda root, o: ["npm ci", "npm run build", "npx cap sync android",
                                "cd android && ./gradlew assembleRelease --console=plain"],
               ["android/app/build/outputs/apk/release/*.apk"], ANDROID_IMAGE, "apk", network=True),
        Recipe("react-native-android", "apk", "mobile", "React Native → Android APK",
               lambda root: "react-native" in _deps(root),
               lambda root, o: ["npm ci", "cd android && ./gradlew assembleRelease --console=plain"],
               ["android/app/build/outputs/apk/release/*.apk"], ANDROID_IMAGE, "apk", network=True),
        Recipe("harmonyos-hap", "hap", "mobile", "HarmonyOS → HAP", _has("hvigorfile.ts", "build-profile.json5"),
               lambda root, o: ["hvigorw assembleHap --mode module -p product=default -p buildMode=release"],
               ["**/build/default/outputs/default/*.hap"], "host", "zip",
               ["DevEco Studio command-line tools (hvigor) installed", "Huawei developer account for signing"]),
        # ------------------------------------------------------------------ windows
        Recipe("go-windows-exe", "exe", "windows", "Go → Windows EXE (cross-compiled)", _go,
               lambda root, o: [f"mkdir -p dist && CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -o "
                                f"dist/{_name(root, o)}.exe {_gomain(root, o)}"],
               ["dist/*.exe"], GO_IMAGE, "pe", tested_here=True),
        Recipe("pyinstaller-exe", "exe", "windows", "Python → Windows EXE (PyInstaller, build on Windows)",
               _has("pyproject.toml", "requirements.txt", "main.py"),
               lambda root, o: ["pip install pyinstaller", f"pyinstaller --onefile --name {_name(root, o)} "
                                f"{o.get('entry', 'main.py')}"], ["dist/*.exe"], "windows", "pe",
               ["A Windows computer or Windows CI runner (PyInstaller does not cross-compile)"]),
        Recipe("dotnet-win-exe", "exe", "windows", ".NET → Windows EXE (self-contained)", lambda root: any(root.glob("*.csproj")),
               lambda root, o: ["dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true "
                                "-o dist/win-x64"], ["dist/win-x64/*.exe"], DOTNET_IMAGE, "pe", network=True),
        Recipe("rust-windows-exe", "exe", "windows", "Rust → Windows EXE (mingw cross)", _has("Cargo.toml"),
               lambda root, o: ["apt-get update -qq && apt-get install -y -qq gcc-mingw-w64-x86-64",
                                "rustup target add x86_64-pc-windows-gnu",
                                "cargo build --release --target x86_64-pc-windows-gnu"],
               ["target/x86_64-pc-windows-gnu/release/*.exe"], RUST_IMAGE, "pe", network=True),
        Recipe("electron-win", "exe", "windows", "Electron → Windows installer (NSIS) via Wine",
               lambda root: "electron" in _deps(root),
               lambda root, o: ["npm ci", "npx electron-builder --win nsis --x64"], ["dist/*.exe"], WINE_IMAGE, "pe",
               ["Code signing certificate to avoid SmartScreen warnings"], network=True),
        Recipe("inno-installer", "exe", "windows", "Any Windows program → Setup.exe (Inno Setup)",
               lambda root: any(root.glob("**/*.iss")),
               lambda root, o: [f"iscc {o.get('iss', next(iter(root.glob('**/*.iss')), Path('setup.iss')))}"],
               ["**/Output/*.exe", "dist/*Setup*.exe"], "windows", "pe", ["Inno Setup on Windows"]),
        Recipe("wix-msi", "msi", "windows", "WiX → MSI", lambda root: any(root.glob("**/*.wxs")),
               lambda root, o: ["wix build -o dist/app.msi " + " ".join(str(p) for p in root.glob("**/*.wxs"))],
               ["dist/*.msi"], "windows", "", ["WiX Toolset v4 on Windows"]),
        Recipe("msix", "msix", "windows", "MSIX (Microsoft Store)", _has("AppxManifest.xml", "Package.appxmanifest"),
               lambda root, o: ["makeappx pack /d build\\msix /p dist\\app.msix"], ["dist/*.msix"], "windows", "",
               ["Windows SDK", "Microsoft Partner Center account for the Store"]),
        Recipe("winget-manifest", "winget", "windows", "winget manifest (from a released installer URL)",
               lambda root: True, lambda root, o: [], ["packaging/winget/*.yaml"], "host", "files", tested_here=True),
        # ------------------------------------------------------------------ macos
        Recipe("go-macos-bin", "macos-bin", "macos", "Go → macOS binary (cross-compiled, arm64 + amd64)", _go,
               lambda root, o: [f"mkdir -p dist && CGO_ENABLED=0 GOOS=darwin GOARCH={a} go build -o "
                                f"dist/{_name(root, o)}-darwin-{a} {_gomain(root, o)}" for a in ("arm64", "amd64")],
               ["dist/*-darwin-*"], GO_IMAGE, "macho", tested_here=True),
        Recipe("macos-dmg", "dmg", "macos", "Mac app → DMG (needs a Mac)", _has("installer/macos/build_dmg.sh"),
               lambda root, o: ["bash installer/macos/build_dmg.sh"], ["dist/*.dmg"], "mac", "",
               ["A Mac", "Apple Developer ID for signing and notarization (otherwise Gatekeeper warns)"]),
        Recipe("macos-pkg", "pkg", "macos", "Mac → PKG installer (needs a Mac)", lambda root: (root / "dist").is_dir(),
               lambda root, o: [f"pkgbuild --root dist/{_name(root, o)} --identifier {o.get('bundle_id', 'com.example.app')} "
                                f"--version {_version(root, o)} dist/{_name(root, o)}.pkg"], ["dist/*.pkg"], "mac", ""),
        Recipe("homebrew-formula", "brew", "macos", "Homebrew formula (from a release tarball URL)", lambda root: True,
               lambda root, o: [], ["packaging/homebrew/*.rb"], "host", "files", tested_here=True),
        # ------------------------------------------------------------------ linux
        Recipe("go-linux-bin", "linux-bin", "linux", "Go → Linux binary (amd64 + arm64)", _go,
               lambda root, o: [f"mkdir -p dist && CGO_ENABLED=0 GOOS=linux GOARCH={a} go build -o "
                                f"dist/{_name(root, o)}-linux-{a} {_gomain(root, o)}" for a in ("amd64", "arm64")],
               ["dist/*-linux-*"], GO_IMAGE, "elf", tested_here=True),
        Recipe("deb", "deb", "linux", "Debian/Ubuntu/Pardus package (.deb) from a built binary",
               lambda root: (root / "dist").is_dir(), lambda root, o: [], ["dist/*.deb"], "host", "deb",
               tested_here=True),
        Recipe("rpm", "rpm", "linux", "Fedora/RHEL/openSUSE package (.rpm) via fpm", lambda root: (root / "dist").is_dir(),
               lambda root, o: [f"fpm -s dir -t rpm -n {_name(root, o)} -v {_version(root, o)} "
                                f"--prefix /opt/{_name(root, o)} -C dist ."], ["*.rpm"], LINUXPKG_IMAGE, "",
               network=True),
        Recipe("appimage", "appimage", "linux", "AppImage (runs on most distributions)",
               _has("installer/linux/build_appimage.sh"), lambda root, o: ["bash installer/linux/build_appimage.sh"],
               ["dist/*.AppImage"], LINUXPKG_IMAGE, "", network=True),
        Recipe("tar-gz", "tar.gz", "linux", "Portable archive (.tar.gz)", lambda root: (root / "dist").is_dir(),
               lambda root, o: [f"tar -czf {_name(root, o)}-{_version(root, o)}-linux.tar.gz -C dist ."],
               ["*.tar.gz"], "host", "targz", tested_here=True),
        Recipe("flatpak", "flatpak", "linux", "Flatpak (Flathub)", lambda root: any(root.glob("*.flatpak.y*ml"))
               or any(root.glob("*.json")) and (root / "flatpak").is_dir(),
               lambda root, o: ["flatpak-builder --repo=repo --force-clean build-dir " +
                                str(next(iter(root.glob("*.flatpak.y*ml")), "app.flatpak.yml")),
                                f"flatpak build-bundle repo dist/{_name(root, o)}.flatpak {o.get('app_id', 'com.example.App')}"],
               ["dist/*.flatpak"], LINUXPKG_IMAGE, "", network=True),
        Recipe("snap", "snap", "linux", "Snap (Snap Store)", _has("snap/snapcraft.yaml", "snapcraft.yaml"),
               lambda root, o: ["snapcraft --destructive-mode"], ["*.snap"], "host", "", ["snapcraft installed"],
               network=True),
        Recipe("aur", "aur", "linux", "Arch Linux AUR PKGBUILD", lambda root: True, lambda root, o: [],
               ["packaging/aur/PKGBUILD"], "host", "files", tested_here=True),
        # ------------------------------------------------------------------ OS and VM images
        Recipe("linux-iso", "iso", "os-image", "Custom bootable Linux ISO (live + installer) with live-build",
               _has("live-build/auto/config", "iso/config"),
               lambda root, o: ["cd live-build && lb clean && lb config && lb build",
                                "mkdir -p ../dist && mv *.iso ../dist/"], ["dist/*.iso"], LIVE_BUILD_IMAGE, "iso",
               ["Docker with --privileged (loop devices)", "10+ GB free disk"], network=True),
        Recipe("raspberry-img", "img", "os-image", "Raspberry Pi image (pi-gen)", _has("pi-gen/config"),
               lambda root, o: ["cd pi-gen && ./build-docker.sh"], ["pi-gen/deploy/*.img*"], "host", "",
               ["Docker with --privileged", "15+ GB free disk"], network=True),
        Recipe("vm-images", "qcow2", "os-image", "VM images: QCOW2 / VMDK / VDI / VHD / OVA (Packer)",
               lambda root: any(root.glob("**/*.pkr.hcl")),
               lambda root, o: ["packer init .", "packer build ."], ["output-*/*"], PACKER_IMAGE, "",
               ["QEMU/VirtualBox/VMware builders as configured"], network=True),
        # ------------------------------------------------------------------ containers
        Recipe("docker-image", "docker", "container", "Docker / OCI image", _has("Dockerfile"),
               lambda root, o: [f"docker build -t {_name(root, o)}:{_version(root, o)} ."], [], "host", "docker",
               tested_here=True),
        Recipe("docker-multiarch", "docker", "container", "Multi-arch image (amd64 + arm64) pushed to a registry",
               _has("Dockerfile"),
               lambda root, o: [f"docker buildx build --platform linux/amd64,linux/arm64 -t "
                                f"{o.get('image', _name(root, o))}:{_version(root, o)} --push ."], [], "host", "",
               ["Logged in to Docker Hub or GHCR", "docker buildx with QEMU binfmt"], network=True),
        Recipe("helm-chart", "helm", "container", "Helm chart package", _has("chart/Chart.yaml", "Chart.yaml"),
               lambda root, o: ["helm package chart -d dist"], ["dist/*.tgz"], "host", "", ["helm installed"]),
        # ------------------------------------------------------------------ web
        Recipe("static-site", "zip", "web", "Static site / PWA bundle (zip)",
               lambda root: (root / "index.html").exists() or (root / "dist" / "index.html").exists()
               or "vite" in _deps(root),
               lambda root, o: (["npm ci", "npm run build"] if (root / "package.json").exists() else []) + [
                   f"cd {o.get('dir', 'dist' if (root / 'dist').exists() or (root / 'package.json').exists() else '.')}"
                   f" && zip -qr {'..' if (root / 'dist').exists() or (root / 'package.json').exists() else '.'}"
                   f"/{_name(root, o)}-web.zip . -x '.yw/*' -x '.git/*' -x '*.zip'"],
               ["*-web.zip"], "host", "web", tested_here=True),
        Recipe("wasm-rust", "wasm", "web", "Rust → WebAssembly (wasm-pack)", _has("Cargo.toml"),
               lambda root, o: ["cargo install wasm-pack", "wasm-pack build --release --target web"], ["pkg/*.wasm"],
               RUST_IMAGE, "", network=True),
        # ------------------------------------------------------------------ extensions
        Recipe("chrome-extension", "zip", "extension", "Chrome / Edge / Brave extension (zip)",
               lambda root: (root / "manifest.json").exists() and "manifest_version" in (root / "manifest.json").read_text("utf-8"),
               lambda root, o: [f"zip -qr {_name(root, o)}-chrome.zip . -x '.yw/*' -x '.git/*' -x '*.zip' -x '*.xpi'"],
               ["*-chrome.zip"], "host", "extension", tested_here=True),
        Recipe("firefox-extension", "xpi", "extension", "Firefox extension (xpi)",
               lambda root: (root / "manifest.json").exists() and "manifest_version" in (root / "manifest.json").read_text("utf-8"),
               lambda root, o: [f"zip -qr {_name(root, o)}-firefox.xpi . -x '.yw/*' -x '.git/*' -x '*.zip' -x '*.xpi'"],
               ["*-firefox.xpi"], "host", "extension", ["Mozilla add-on signing (web-ext sign) to install permanently"],
               tested_here=True),
        Recipe("safari-extension", "safari", "extension", "Safari extension (needs a Mac + Xcode)",
               _has("manifest.json"), lambda root, o: ["xcrun safari-web-extension-converter . --no-open"], [],
               "mac", "", ["A Mac with Xcode", "Apple Developer account"]),
        Recipe("vscode-extension", "vsix", "extension", "VS Code extension (vsix)",
               lambda root: "vscode" in json.dumps(_pkg_json(root).get("engines", {})),
               lambda root, o: ["npm ci", "npx --yes @vscode/vsce package -o dist/"], ["dist/*.vsix"], "host", "zip",
               network=True),
        Recipe("jetbrains-plugin", "zip", "extension", "JetBrains plugin (zip)",
               lambda root: "org.jetbrains.intellij" in "".join(p.read_text("utf-8", "ignore") for p in root.glob("*.gradle*")),
               lambda root, o: ["./gradlew buildPlugin --console=plain"], ["build/distributions/*.zip"], ANDROID_IMAGE,
               "zip", network=True),
        Recipe("wordpress-plugin", "zip", "extension", "WordPress plugin (zip)",
               lambda root: any("Plugin Name:" in p.read_text("utf-8", "ignore") for p in root.glob("*.php")),
               lambda root, o: [f"cd .. && zip -qr {root.name}/{_name(root, o)}-wordpress.zip {root.name} "
                                f"-x '{root.name}/.yw/*' -x '{root.name}/.git/*' -x '*.zip'"],
               ["*-wordpress.zip"], "host", "zip", tested_here=True),
        # ------------------------------------------------------------------ packages
        Recipe("python-wheel", "wheel", "package", "Python wheel + sdist (PyPI)", _has("pyproject.toml", "setup.py"),
               lambda root, o: ["python -m pip wheel --no-deps -w dist ."], ["dist/*.whl"], "host", "wheel",
               tested_here=True),
        Recipe("npm-package", "npm", "package", "npm package (.tgz)", lambda root: bool(_pkg_json(root).get("name")),
               lambda root, o: ["mkdir -p dist && npm pack --pack-destination dist"], ["dist/*.tgz"], "host", "npm",
               tested_here=True),
        Recipe("maven-jar", "jar", "package", "Java/Kotlin library (JAR/AAR)", _has("build.gradle", "build.gradle.kts", "pom.xml"),
               lambda root, o: ["./gradlew build --console=plain" if (root / "gradlew").exists() else "mvn -q package"],
               ["build/libs/*.jar", "target/*.jar", "**/build/outputs/aar/*.aar"], ANDROID_IMAGE, "zip", network=True),
        Recipe("nuget", "nupkg", "package", ".NET NuGet package", lambda root: any(root.glob("*.csproj")),
               lambda root, o: ["dotnet pack -c Release -o dist"], ["dist/*.nupkg"], DOTNET_IMAGE, "zip", network=True),
        Recipe("rust-crate", "crate", "package", "Rust crate (crates.io)", _has("Cargo.toml"),
               lambda root, o: ["cargo package --allow-dirty"], ["target/package/*.crate"], RUST_IMAGE, "",
               network=True),
        Recipe("dart-package", "dart", "package", "Dart package (pub.dev dry run)", _has("pubspec.yaml"),
               lambda root, o: ["dart pub publish --dry-run"], [], FLUTTER_IMAGE, "", network=True),
        # ------------------------------------------------------------------ games
        Recipe("godot-export", "game", "game", "Godot → Windows / Linux / Android / Web", _has("project.godot"),
               lambda root, o: ["mkdir -p dist", "godot --headless --export-release \"Windows Desktop\" dist/game.exe",
                                "godot --headless --export-release \"Linux\" dist/game.x86_64",
                                "godot --headless --export-release \"Web\" dist/index.html"],
               ["dist/*"], GODOT_IMAGE, "", ["export_presets.cfg with these presets"], network=True),
        Recipe("unity-build", "game", "game", "Unity build (all platforms)", _has("ProjectSettings/ProjectVersion.txt"),
               lambda root, o: ["unity-editor -batchmode -quit -projectPath . -executeMethod BuildScript.BuildAll"],
               ["Builds/**"], "host", "", ["Your Unity license (Personal/Pro)", "Mac for macOS/iOS builds"]),
        # ------------------------------------------------------------------ embedded
        Recipe("platformio", "firmware", "embedded", "Arduino / ESP32 / STM32 / Pico firmware (PlatformIO)",
               _has("platformio.ini"), lambda root, o: ["pio run"], [".pio/build/*/firmware.*"], PIO_IMAGE, "",
               network=True),
        Recipe("arduino-cli", "firmware", "embedded", "Arduino sketch → HEX/BIN (arduino-cli)",
               lambda root: any(root.glob("*.ino")),
               lambda root, o: [f"arduino-cli compile --fqbn {o.get('fqbn', 'arduino:avr:uno')} --output-dir dist ."],
               ["dist/*.hex", "dist/*.bin"], PIO_IMAGE, "", network=True),
        # ------------------------------------------------------------------ TV / watch
        Recipe("tizen-wgt", "wgt", "tv-watch", "Samsung Tizen TV app (wgt)", _has("config.xml"),
               lambda root, o: ["tizen build-web", "tizen package -t wgt -s default -- .buildResult"],
               [".buildResult/*.wgt"], "host", "zip", ["Tizen Studio CLI", "Samsung certificate"]),
        Recipe("webos-ipk", "ipk", "tv-watch", "LG webOS TV app (ipk)", _has("appinfo.json"),
               lambda root, o: ["ares-package . -o dist"], ["dist/*.ipk"], "host", "", ["webOS CLI (ares)"]),
        # ------------------------------------------------------------------ docs
        Recipe("docs-pdf", "pdf", "docs", "Markdown → PDF", lambda root: any(root.glob("*.md")),
               lambda root, o: [f"mkdir -p dist && pandoc {o.get('source', 'README.md')} -o dist/{_name(root, o)}.pdf "
                                f"--pdf-engine={o.get('pdf_engine', 'wkhtmltopdf')}"],
               ["dist/*.pdf"], "host", "pdf", ["a PDF engine (wkhtmltopdf, weasyprint or LaTeX)"]),
        Recipe("docs-epub", "epub", "docs", "Markdown → EPUB", lambda root: any(root.glob("*.md")),
               lambda root, o: [f"mkdir -p dist && pandoc {o.get('source', 'README.md')} -o dist/{_name(root, o)}.epub "
                                f"--metadata title='{_name(root, o)}'"], ["dist/*.epub"], "host", "zip", tested_here=True),
        Recipe("docs-docx", "docx", "docs", "Markdown → DOCX", lambda root: any(root.glob("*.md")),
               lambda root, o: [f"mkdir -p dist && pandoc {o.get('source', 'README.md')} -o dist/{_name(root, o)}.docx"],
               ["dist/*.docx"], "host", "zip", tested_here=True),
    ]
    return r + list(EXTRA)


def by_id() -> dict[str, Recipe]:
    return {x.id: x for x in all_recipes()}


def applicable(root: Path) -> list[Recipe]:
    out = []
    for x in all_recipes():
        try:
            if x.applies(Path(root)):
                out.append(x)
        except (OSError, UnicodeDecodeError):
            continue
    return out
