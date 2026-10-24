import json

from yworkspace.config import Config
from yworkspace.setup import system, wizard
from yworkspace.setup.system import GPU, SystemInfo


def info(os_="linux", ram=16, gpus=(), distro="debian", arch="x86_64"):
    return SystemInfo(os_, "1", arch, ram, 100, list(gpus), distro)


def test_detect_runs_here():
    i = system.detect()
    assert i.os in ("linux", "macos", "windows") and i.ram_gb > 0 and i.disk_free_gb > 0
    assert "RAM" in i.describe()


def test_model_recommendations():
    assert system.recommend_local_model(info(ram=8))[0].endswith(":3b")
    assert system.recommend_local_model(info(ram=16))[0].endswith(":7b")
    assert system.recommend_local_model(info(gpus=[GPU("nvidia", "4090", 24)]))[0].endswith(":32b")
    assert system.recommend_local_model(info("macos", 32, [GPU("apple", "M2", 21)], arch="arm64"))[0].endswith(":14b")


def test_docker_plans_per_os(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path))
    monkeypatch.setattr(wizard.shutil, "which", lambda name: None)
    cfg = Config()
    win = wizard._docker_actions(wizard.WizardContext(cfg, info("windows")))
    assert win[0].command[:2] == ["wsl", "--install"] and win[0].reboot_after
    assert "Docker.DockerDesktop" in win[1].command
    mac = wizard._docker_actions(wizard.WizardContext(cfg, info("macos", arch="arm64")))
    assert "arm64/Docker.dmg" in mac[0].manual
    deb = wizard._docker_actions(wizard.WizardContext(cfg, info("linux", distro="debian")))
    assert "get.docker.com" in deb[0].command and deb[0].admin


def test_reboot_resume_and_skip(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path))
    w = wizard.Wizard(Config(), info("windows"))
    out = w.run_action(wizard.Action("x", ["wsl"], reboot_after=True), runner=lambda c: (0, "ok"))
    assert "REBOOT REQUIRED" in out
    assert json.loads((tmp_path / "setup.json").read_text())["_resume_after_reboot"] is True
    w.mark("bridge", "skipped")
    assert next(s for s in wizard.Wizard(Config(), info()).status() if s["id"] == "bridge")["skipped"]


def test_claude_desktop_merge(tmp_path, monkeypatch):
    cfgfile = tmp_path / "claude" / "claude_desktop_config.json"
    cfgfile.parent.mkdir()
    cfgfile.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}))
    monkeypatch.setattr(wizard, "claude_desktop_config_path", lambda: cfgfile)
    wizard.add_mcp_to_claude_desktop(str(tmp_path / "proj"))
    data = json.loads(cfgfile.read_text())
    assert set(data["mcpServers"]) == {"other", "yworkspace"} and data["theme"] == "dark"
    assert data["mcpServers"]["yworkspace"]["args"][-2:] == ["-p", str(tmp_path / "proj")]
    assert cfgfile.with_suffix(".json.yw-backup").exists()


def test_key_step_stores_secret(tmp_path, monkeypatch):
    monkeypatch.setenv("YW_HOME", str(tmp_path))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(wizard, "test_key", lambda preset: " — test skipped")
    ctx = wizard.WizardContext(Config(model="deepseek-chat"), info(), {"DEEPSEEK_API_KEY": "sk-abc"})
    assert not wizard._check_models(ctx).ok
    acts = wizard._model_actions(ctx)
    assert "saved" in acts[0].run_python()
    assert wizard._check_models(ctx).ok
