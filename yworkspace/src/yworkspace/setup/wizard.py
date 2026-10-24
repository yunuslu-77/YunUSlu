"""Setup wizard: checks the computer and installs what yWorkspace needs, step by step, resumable.

Every step: check() → is it already fine?  actions() → exact commands it would run (shown to the user first).
Progress is saved so the wizard continues after a reboot (needed on Windows for WSL2/Docker).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..config import Config, get_secret, home, set_secret
from .system import SystemInfo, detect, recommend_local_model


@dataclass
class Action:
    describe: str
    command: list[str] | str | None = None  # None = manual action, see `manual`
    admin: bool = False
    reboot_after: bool = False
    manual: str = ""  # instructions when it cannot be automated (e.g. open a URL)
    run_python: Callable[[], str] | None = field(default=None, repr=False)


@dataclass
class StepStatus:
    ok: bool
    detail: str = ""


@dataclass
class Step:
    id: str
    title_tr: str
    title_en: str
    check: Callable[[WizardContext], StepStatus]
    actions: Callable[[WizardContext], list[Action]]
    optional: bool = False


@dataclass
class WizardContext:
    cfg: Config
    info: SystemInfo
    answers: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------------------------- helpers
def _ok(cmd: list[str], timeout: int = 20) -> bool:
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def claude_desktop_config_path() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "Claude" / "claude_desktop_config.json"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    return Path.home() / ".config/Claude/claude_desktop_config.json"


def add_mcp_to_claude_desktop(project_dir: str) -> str:
    """Merge the yWorkspace MCP server into Claude Desktop's config, keeping a backup."""
    p = claude_desktop_config_path()
    data = {}
    if p.exists():
        data = json.loads(p.read_text("utf-8") or "{}")
        p.with_suffix(".json.yw-backup").write_text(json.dumps(data, indent=2), "utf-8")
    exe = shutil.which("yw")
    entry = {"command": exe, "args": ["mcp", "-p", project_dir]} if exe else \
        {"command": sys.executable, "args": ["-m", "yworkspace.cli", "mcp", "-p", project_dir]}
    data.setdefault("mcpServers", {})["yworkspace"] = entry
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), "utf-8")
    return f"Wrote {p}. Restart Claude Desktop."


# ---------------------------------------------------------------------------------------------- steps
def _check_docker(ctx: WizardContext) -> StepStatus:
    if ctx.cfg.sandbox == "local":
        return StepStatus(True, "Docker'sız mod seçildi / local mode chosen")
    if not shutil.which("docker"):
        return StepStatus(False, "Docker kurulu değil / not installed")
    if not _ok(["docker", "info"]):
        return StepStatus(False, "Docker kurulu ama çalışmıyor / installed but not running")
    if not _ok(["docker", "run", "--rm", "hello-world"], timeout=180):
        return StepStatus(False, "Docker konteyner çalıştıramadı / cannot run containers")
    return StepStatus(True, "Docker çalışıyor / running")


def _docker_actions(ctx: WizardContext) -> list[Action]:
    i = ctx.info
    if shutil.which("docker") and not _ok(["docker", "info"]):
        if i.os == "linux":
            return [Action("Docker servisini başlat / start the Docker service",
                           ["sudo", "systemctl", "enable", "--now", "docker"], admin=True)]
        return [Action("Docker Desktop'ı aç / open Docker Desktop", None,
                       manual="Docker Desktop uygulamasını başlatın ve balina simgesi sabitlenince devam edin.")]
    if i.os == "windows":
        return [
            Action("WSL2'yi etkinleştir / enable WSL2", ["wsl", "--install", "--no-distribution"], admin=True,
                   reboot_after=True),
            Action("Docker Desktop'ı kur / install Docker Desktop",
                   ["winget", "install", "-e", "--id", "Docker.DockerDesktop", "--accept-package-agreements",
                    "--accept-source-agreements"], admin=True),
            Action("Docker Desktop'ı ilk kez aç / first start", None,
                   manual="Başlat menüsünden Docker Desktop'ı açın, lisans ekranını kabul edin."),
        ]
    if i.os == "macos":
        if shutil.which("brew"):
            return [Action("Docker Desktop'ı kur / install Docker Desktop", ["brew", "install", "--cask", "docker"])]
        chip = "arm64" if i.arch in ("arm64", "aarch64") else "amd64"
        return [Action("Docker Desktop'ı indir / download Docker Desktop", None,
                       manual=f"https://desktop.docker.com/mac/main/{chip}/Docker.dmg dosyasını indirip Applications'a sürükleyin.")]
    fam = i.distro
    if fam in ("debian", "fedora"):
        return [
            Action("Docker Engine'i kur (resmi betik) / install Docker Engine (official script)",
                   "curl -fsSL https://get.docker.com | sudo sh", admin=True),
            Action("Kullanıcıyı docker grubuna ekle / add user to docker group",
                   ["sudo", "usermod", "-aG", "docker", os.environ.get("USER", "")], admin=True),
            Action("Servisi başlat / start service", ["sudo", "systemctl", "enable", "--now", "docker"], admin=True),
            Action("Oturumu kapatıp açın / log out and in", None,
                   manual="Grup değişikliğinin geçerli olması için oturumu kapatıp açın (ya da `newgrp docker`)."),
        ]
    if fam == "arch":
        return [Action("Docker'ı kur / install Docker", ["sudo", "pacman", "-S", "--noconfirm", "docker"], admin=True),
                Action("Servisi başlat / start service", ["sudo", "systemctl", "enable", "--now", "docker"], admin=True)]
    return [Action("Docker'ı kurun / install Docker", None, manual="https://docs.docker.com/engine/install/")]


def _check_models(ctx: WizardContext) -> StepStatus:
    from ..models.profiles import get_profile
    try:
        prof = get_profile(ctx.cfg.model)
    except KeyError as e:
        return StepStatus(False, str(e))
    if prof.local:
        ok = _ok(["ollama", "list"]) if shutil.which("ollama") else False
        return StepStatus(ok, "Ollama hazır / ready" if ok else "Ollama kurulu değil / not installed")
    has = bool(prof.key_env and get_secret(prof.key_env))
    return StepStatus(has, f"{prof.key_env} {'var' if has else 'eksik / missing'}")


def _model_actions(ctx: WizardContext) -> list[Action]:
    from ..models.profiles import get_profile
    prof = get_profile(ctx.cfg.model)
    if prof.local:
        tag, why = recommend_local_model(ctx.info)
        acts = []
        if not shutil.which("ollama"):
            if ctx.info.os == "linux":
                acts.append(Action("Ollama'yı kur / install Ollama", "curl -fsSL https://ollama.com/install.sh | sh",
                                   admin=True))
            elif ctx.info.os == "windows":
                acts.append(Action("Ollama'yı kur / install Ollama", ["winget", "install", "-e", "--id", "Ollama.Ollama"]))
            else:
                acts.append(Action("Ollama'yı kur / install Ollama",
                                   ["brew", "install", "ollama"] if shutil.which("brew") else None,
                                   manual="https://ollama.com/download"))
        acts.append(Action(f"Modeli indir: {tag} ({why}) / download model", ["ollama", "pull", tag]))

        def set_model() -> str:
            ctx.cfg.model = f"ollama:{tag}"
            ctx.cfg.save()
            return f"Model set to ollama:{tag}"
        acts.append(Action("Bu modeli varsayılan yap / make it the default", run_python=set_model))
        return acts
    key_url = {"DEEPSEEK_API_KEY": "https://platform.deepseek.com/api_keys",
               "GEMINI_API_KEY": "https://aistudio.google.com/apikey",
               "ANTHROPIC_API_KEY": "https://console.anthropic.com/settings/keys",
               "OPENAI_API_KEY": "https://platform.openai.com/api-keys"}.get(prof.key_env or "", "")
    value = ctx.answers.get(prof.key_env or "")
    if value:
        def store() -> str:
            where = set_secret(prof.key_env, value)
            return f"{prof.key_env} saved ({where})" + test_key(prof.id)
        return [Action(f"{prof.key_env} kaydet ve test et / save and test", run_python=store)]
    return [Action(f"{prof.key_env} gerekli / needed", None,
                   manual=f"Anahtarı {key_url or 'sağlayıcınızın sitesinden'} alın, sonra: yw key {prof.key_env} <anahtar>")]


def test_key(preset: str) -> str:
    from ..models.base import Message, ProviderError
    from ..models.profiles import create_provider, get_profile
    try:
        prof = get_profile(preset)
        p = create_provider(prof, api_key=get_secret(prof.key_env) if prof.key_env else None)
        r = p.chat([Message("user", "Reply with the single word OK.")], max_tokens=20)
        return f" — test OK ({r.message.content.strip()[:20]})"
    except (ProviderError, Exception) as e:
        return f" — test FAILED: {str(e)[:200]}"


def _check_folder(ctx: WizardContext) -> StepStatus:
    p = Path(ctx.cfg.projects_dir).expanduser()
    return StepStatus(p.is_dir() and os.access(p, os.W_OK), str(p))


def _folder_actions(ctx: WizardContext) -> list[Action]:
    p = Path(ctx.answers.get("projects_dir") or ctx.cfg.projects_dir).expanduser()

    def make() -> str:
        p.mkdir(parents=True, exist_ok=True)
        ctx.cfg.projects_dir = str(p)
        ctx.cfg.save()
        return f"Projects folder: {p}"
    return [Action(f"Proje klasörünü oluştur / create projects folder: {p}", run_python=make)]


def _check_mcp(ctx: WizardContext) -> StepStatus:
    p = claude_desktop_config_path()
    if not p.parent.exists():
        return StepStatus(True, "Claude Desktop yok, atlandı / not installed, skipped")
    try:
        ok = "yworkspace" in json.loads(p.read_text("utf-8") or "{}").get("mcpServers", {})
    except (OSError, json.JSONDecodeError):
        ok = False
    return StepStatus(ok, "Claude Desktop'a bağlı / connected" if ok else "Claude Desktop'a bağlanmamış")


def _mcp_actions(ctx: WizardContext) -> list[Action]:
    d = ctx.cfg.projects_dir
    return [Action("yWorkspace'i Claude Desktop'a MCP ile bağla / connect via MCP",
                   run_python=lambda: add_mcp_to_claude_desktop(d))]


def _check_extension(ctx: WizardContext) -> StepStatus:
    return StepStatus(bool(ctx.answers.get("extension_done")), "")


def _extension_actions(ctx: WizardContext) -> list[Action]:
    ext = Path(__file__).resolve().parent.parent / "extension" / "browser"
    return [Action("Tarayıcı eklentisini yükle / load the browser extension", None,
                   manual=f"Chrome/Edge: chrome://extensions → Geliştirici modu → 'Paketlenmemiş öğe yükle' → {ext}\n"
                          "Sonra `yw bridge-web` çalıştırıp verilen kodu eklentiye girin.")]


def _check_bridge(ctx: WizardContext) -> StepStatus:
    try:
        import pyautogui  # noqa: F401
        import pynput  # noqa: F401
        return StepStatus(True, "Masaüstü Köprüsü paketleri hazır / bridge packages ready")
    except ImportError:
        return StepStatus(False, "Masaüstü Köprüsü paketleri eksik / bridge packages missing")


def _bridge_actions(ctx: WizardContext) -> list[Action]:
    acts = [Action("Köprü paketlerini kur / install bridge packages",
                   [sys.executable, "-m", "pip", "install", "yworkspace[bridge]"])]
    if ctx.info.os == "macos":
        acts.append(Action("Erişilebilirlik izni / accessibility permission", None,
                           manual="Sistem Ayarları → Gizlilik ve Güvenlik → Erişilebilirlik → Terminal (veya yWorkspace) "
                                  "için izni açın. Ekran OCR kullanacaksanız 'Ekran Kaydı' iznini de verin."))
    if ctx.info.os == "linux" and os.environ.get("WAYLAND_DISPLAY"):
        acts.append(Action("Wayland notu / Wayland note", None,
                           manual="Wayland klavye/fare otomasyonunu kısıtlar. Köprü için X11 oturumu önerilir."))
    return acts


def _check_media(ctx: WizardContext) -> StepStatus:
    return StepStatus(bool(shutil.which("ffmpeg")), "ffmpeg " + ("var" if shutil.which("ffmpeg") else "yok"))


def _media_actions(ctx: WizardContext) -> list[Action]:
    from ..studio.pack import pack_actions
    return pack_actions(ctx)


def _check_trial(ctx: WizardContext) -> StepStatus:
    p = Path(ctx.cfg.projects_dir).expanduser() / "yw-deneme" / ".yw" / "state.json"
    ok = p.exists() and json.loads(p.read_text("utf-8")).get("phase") == "done"
    return StepStatus(ok, "Deneme projesi tamam / trial project done" if ok else "")


def _trial_actions(ctx: WizardContext) -> list[Action]:
    def trial() -> str:
        from ..app import build_session
        cfg = Config(**asdict(ctx.cfg))
        cfg.autonomy, cfg.quality, cfg.budget_usd = "auto", "economy", 0.5
        p = Path(cfg.projects_dir).expanduser() / "yw-deneme"
        sess = build_session(p, cfg)
        report = sess.engine.run("Write a Python function is_palindrome(text) that ignores case, spaces and "
                                 "punctuation, with pytest tests.")
        sess.close()
        return report.text()
    return [Action("Küçük bir deneme projesini uçtan uca yaptır / run a small end-to-end trial", run_python=trial)]


STEPS: list[Step] = [
    Step("docker", "Docker (yalıtılmış çalışma alanı)", "Docker (isolated workspace)", _check_docker, _docker_actions),
    Step("model", "Yapay zekâ modeli", "AI model", _check_models, _model_actions),
    Step("folder", "Proje klasörü", "Projects folder", _check_folder, _folder_actions),
    Step("mcp", "Claude Desktop bağlantısı (MCP)", "Claude Desktop connection (MCP)", _check_mcp, _mcp_actions, True),
    Step("extension", "Tarayıcı eklentisi", "Browser extension", _check_extension, _extension_actions, True),
    Step("bridge", "Masaüstü Köprüsü", "Desktop Bridge", _check_bridge, _bridge_actions, True),
    Step("media", "Medya paketi", "Media pack", _check_media, _media_actions, True),
    Step("trial", "Deneme projesi", "Trial project", _check_trial, _trial_actions),
]


class Wizard:
    def __init__(self, cfg: Config | None = None, info: SystemInfo | None = None):
        self.cfg = cfg or Config.load()
        self.ctx = WizardContext(self.cfg, info or detect())
        self.state_path = home() / "setup.json"
        self.done: dict[str, bool] = json.loads(self.state_path.read_text("utf-8")) if self.state_path.exists() else {}

    def save(self) -> None:
        home().mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(self.done, indent=2), "utf-8")

    def status(self) -> list[dict]:
        out = []
        for s in STEPS:
            st = s.check(self.ctx)
            out.append({"id": s.id, "title_tr": s.title_tr, "title_en": s.title_en, "ok": st.ok, "detail": st.detail,
                        "optional": s.optional, "skipped": self.done.get(s.id) == "skipped"})
        return out

    def plan(self, step_id: str) -> list[Action]:
        step = next(s for s in STEPS if s.id == step_id)
        return step.actions(self.ctx)

    def run_action(self, action: Action, runner: Callable[[list[str] | str], tuple[int, str]] | None = None) -> str:
        if action.run_python:
            return action.run_python()
        if action.command is None:
            return "MANUAL: " + action.manual
        runner = runner or _default_runner
        code, out = runner(action.command)
        if code != 0:
            raise RuntimeError(f"Command failed ({code}): {out[-1500:]}")
        if action.reboot_after:
            self.done["_resume_after_reboot"] = True
            self.save()
            return out + "\nREBOOT REQUIRED: restart the computer, then run `yw setup` again; it continues here."
        return out

    def mark(self, step_id: str, value) -> None:
        self.done[step_id] = value
        self.save()


def _default_runner(cmd: list[str] | str) -> tuple[int, str]:
    r = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=3600)
    return r.returncode, (r.stdout or "") + (r.stderr or "")
