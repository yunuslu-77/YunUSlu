import os
import time

import pytest

from yworkspace.core import ToolError
from yworkspace.sandbox import DockerSandbox, LocalSandbox, docker_available


@pytest.fixture
def local(tmp_path):
    sb = LocalSandbox(tmp_path)
    yield sb
    sb.stop()


def test_local_run(local):
    r = local.run("echo hello && exit 3")
    assert r.exit_code == 3 and "hello" in r.output


def test_local_timeout(local):
    r = local.run("sleep 5", timeout=1)
    assert r.timed_out


def test_local_background(local, tmp_path):
    local.start_process("ticker", "for i in 1 2 3; do echo tick$i; sleep 0.2; done; sleep 30")
    time.sleep(1.2)
    assert "tick3" in local.logs("ticker")
    assert "running" in local.processes()
    assert local.stop_process("ticker") == "Stopped ticker."


def test_local_cwd_escape(local):
    with pytest.raises(ToolError):
        local.run("ls", cwd="..")


needs_docker = pytest.mark.skipif(not docker_available(), reason="Docker daemon not available")


@pytest.fixture(scope="module")
def docker_sb(tmp_path_factory):
    root = tmp_path_factory.mktemp("dockerproj")
    sb = DockerSandbox(root, network=False)
    yield sb
    sb.stop()


@pytest.mark.docker
@needs_docker
def test_docker_isolation_and_files(docker_sb):
    r = docker_sb.run("echo inside && cat /etc/os-release | head -1 && pwd && touch made.txt")
    assert r.exit_code == 0 and "inside" in r.output and "/workspace" in r.output
    made = docker_sb.root / "made.txt"
    assert made.exists()
    if hasattr(os, "getuid"):
        assert made.stat().st_uid == os.getuid()
    r = docker_sb.run("ls /root 2>&1; ls /home/user 2>&1")
    assert "YunUSlu" not in r.output


@pytest.mark.docker
@needs_docker
def test_docker_timeout_and_exit_codes(docker_sb):
    assert docker_sb.run("exit 7").exit_code == 7
    r = docker_sb.run("sleep 10", timeout=2)
    assert r.timed_out and r.duration < 9


@pytest.mark.docker
@needs_docker
def test_docker_background_server(docker_sb):
    out = docker_sb.start_process("web", "python -m http.server 8000")
    assert "running" in out
    r = docker_sb.run("python -c \"import urllib.request,time;time.sleep(1);"
                      "print(urllib.request.urlopen('http://127.0.0.1:8000').status)\"")
    assert "200" in r.output
    assert "GET /" in docker_sb.logs("web")
    assert docker_sb.stop_process("web") == "Stopped web."
    assert "stopped" in docker_sb.processes()


@pytest.mark.docker
@needs_docker
def test_docker_no_network(docker_sb):
    r = docker_sb.run("python -c \"import urllib.request;urllib.request.urlopen('http://example.com',timeout=3)\"")
    assert r.exit_code != 0
