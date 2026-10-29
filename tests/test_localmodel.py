"""localmodel：判活、拼参数、起不来要收尾。不真的起 llama-server。"""

from __future__ import annotations

import subprocess

from openhuman import localmodel
from openhuman.config import load_config


class FakeProc:
    """够用的子进程替身：记下被怎么对待过。"""

    def __init__(self, *, wait_raises: bool = False) -> None:
        self.terminated = False
        self.killed = False
        self.waited = False
        self._dead = False
        self._wait_raises = wait_raises

    def poll(self):
        return 0 if self._dead else None

    def terminate(self):
        self.terminated = True
        if not self._wait_raises:
            self._dead = True

    def wait(self, timeout=None):
        self.waited = True
        if self._wait_raises:
            raise subprocess.TimeoutExpired("llama-server", timeout or 1)
        return 0

    def kill(self):
        self.killed = True
        self._dead = True


# ---------- 基础 ----------


def test_port_of():
    assert localmodel.port_of("http://127.0.0.1:8080") == 8080
    assert localmodel.port_of("http://127.0.0.1:8080/v1") == 8080
    assert localmodel.port_of("http://example.com") == 80
    assert localmodel.port_of("https://example.com") == 443


def test_threads_is_sane():
    assert 2 <= localmodel.threads() <= 8


def test_healthy_false_when_nothing_listens():
    """端口 9 是 discard，本机不会有人监听。"""
    assert localmodel.healthy("http://127.0.0.1:9", timeout=0.2) is False


def test_healthy_false_on_garbage_url():
    assert localmodel.healthy("not a url", timeout=0.2) is False


# ---------- 程序与参数 ----------


def test_program_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(localmodel.paths, "root", lambda: tmp_path)
    monkeypatch.setattr(localmodel.paths, "vendor_dir", lambda: tmp_path / "vendor")
    assert localmodel.program(load_config()) is None


def test_program_found(tmp_path, monkeypatch):
    monkeypatch.setattr(localmodel.paths, "root", lambda: tmp_path)
    monkeypatch.setattr(localmodel.paths, "vendor_dir", lambda: tmp_path / "vendor")
    exe = tmp_path / "vendor" / "llama" / "llama-server.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    cfg = load_config()
    model = tmp_path / cfg.llama.model_file
    model.parent.mkdir(parents=True)
    model.write_bytes(b"")

    found = localmodel.program(cfg)
    assert found == (exe, model)


def test_command_carries_config(tmp_path):
    cfg = load_config()
    exe, model = tmp_path / "llama-server.exe", tmp_path / "m.gguf"
    args = localmodel.command(cfg, exe, model)

    assert str(exe) == args[0]
    assert str(model) in args
    assert cfg.llama.model in args  # -a，给模型起别名
    assert str(cfg.llama.context) in args  # -c
    assert str(localmodel.port_of(cfg.llama.base_url)) in args
    assert "--jinja" in args
    # 关掉思考（BUILD.md §11 N-05）
    assert args[args.index("--reasoning-format") + 1] == "none"


# ---------- ensure ----------


def test_ensure_reuses_existing_server(monkeypatch):
    monkeypatch.setattr(localmodel, "healthy", lambda *a, **k: True)
    started = []
    monkeypatch.setattr(localmodel, "start", lambda cfg: started.append(1))

    said: list[str] = []
    assert localmodel.ensure(load_config(), out=said.append) is None
    assert started == []
    assert "已经在线" in said[0]


def test_ensure_skips_when_no_model(monkeypatch):
    monkeypatch.setattr(localmodel, "healthy", lambda *a, **k: False)
    monkeypatch.setattr(localmodel, "program", lambda cfg: None)

    said: list[str] = []
    assert localmodel.ensure(load_config(), out=said.append) is None
    assert "没找到" in said[-1]


def test_ensure_returns_proc_when_ready(monkeypatch):
    proc = FakeProc()
    monkeypatch.setattr(localmodel, "healthy", lambda *a, **k: False)
    monkeypatch.setattr(localmodel, "program", lambda cfg: ("exe", "model"))
    monkeypatch.setattr(localmodel, "start", lambda cfg: proc)
    monkeypatch.setattr(localmodel, "wait", lambda url, seconds: True)

    assert localmodel.ensure(load_config(), out=lambda _: None) is proc


def test_ensure_kills_proc_when_never_ready(monkeypatch):
    proc = FakeProc()
    monkeypatch.setattr(localmodel, "healthy", lambda *a, **k: False)
    monkeypatch.setattr(localmodel, "program", lambda cfg: ("exe", "model"))
    monkeypatch.setattr(localmodel, "start", lambda cfg: proc)
    monkeypatch.setattr(localmodel, "wait", lambda url, seconds: False)

    said: list[str] = []
    assert localmodel.ensure(load_config(), out=said.append) is None
    assert proc.terminated is True
    assert "没起来" in said[-1]


# ---------- stop ----------


def test_stop_ignores_none_and_exited():
    localmodel.stop(None)
    dead = FakeProc()
    dead._dead = True
    localmodel.stop(dead)
    assert dead.terminated is False


def test_stop_terminates():
    proc = FakeProc()
    localmodel.stop(proc)
    assert proc.terminated is True
    assert proc.waited is True
    assert proc.killed is False


def test_stop_kills_when_terminate_hangs():
    proc = FakeProc(wait_raises=True)
    localmodel.stop(proc)
    assert proc.killed is True
