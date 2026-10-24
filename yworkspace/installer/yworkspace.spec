# PyInstaller spec: one folder build of yWorkspace for Windows, macOS and Linux.
# Build: pyinstaller installer/yworkspace.spec  (run from the yworkspace/ folder)
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent
datas = collect_data_files("yworkspace", includes=["**/*.json", "**/*.md", "**/*.html", "**/*.js", "**/*.css",
                                                    "**/Dockerfile", "**/*.yaml", "**/*.png"])
hidden = collect_submodules("yworkspace") + collect_submodules("uvicorn") + ["fastapi", "httpx"]

a = Analysis([str(root / "installer" / "launcher.py")], pathex=[str(root / "src")], datas=datas,
             hiddenimports=hidden, excludes=["tkinter", "matplotlib", "torch"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="yworkspace", console=True,
          icon=str(root / "installer" / "icon.ico") if sys.platform == "win32" and (root / "installer" / "icon.ico").exists() else None)
coll = COLLECT(exe, a.binaries, a.datas, name="yworkspace")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="yWorkspace.app", bundle_identifier="dev.yunuslu.yworkspace",
                 info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "0.1.0"})
