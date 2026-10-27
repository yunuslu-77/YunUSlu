# PyInstaller spec: yWorkspace Qwen edition as a single Windows exe (only Qwen3-Coder-Next through Janas-LLM).
# Build: pyinstaller installer/yworkspace-qwen.spec  (run from the yworkspace/ folder)
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parent
datas = collect_data_files("yworkspace", includes=["**/*.json", "**/*.md", "**/*.html", "**/*.js", "**/*.css",
                                                    "**/Dockerfile", "**/*.yaml", "**/*.png"])
datas += collect_data_files("yworkspace", includes=["saas_kit/templates/**/*", "saas_kit/templates/**/.*"])
hidden = collect_submodules("yworkspace") + collect_submodules("uvicorn") + ["fastapi", "httpx"]

a = Analysis([str(root / "installer" / "launcher_qwen.py")], pathex=[str(root / "src")], datas=datas,
             hiddenimports=hidden, excludes=["tkinter", "matplotlib", "torch"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="yWorkspace-Qwen", console=True,
          icon=str(root / "installer" / "icon.ico") if sys.platform == "win32" and (root / "installer" / "icon.ico").exists() else None)
