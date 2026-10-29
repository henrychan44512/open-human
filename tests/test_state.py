"""Runtime：在线判断、等他醒、云端不预热、改配置之后会话还在。"""

from __future__ import annotations

import time
from types import SimpleNamespace

from openhuman import paths
from openhuman.config import load_config
from openhuman.server import state
from openhuman.server.state import Runtime


def _runtime(backend: str = "llama", key: str = "") -> Runtime:
    cfg = load_config()
    cfg.app.default_model = backend  # type: ignore[assignment]
    cfg.deepseek.api_key = key
    return Runtime(cfg)


# ---------- 在线 ----------


def test_online_local_asks_server(monkeypatch):
    rt = _runtime()
    monkeypatch.setattr(
        rt, "client", lambda backend=None: SimpleNamespace(health=lambda: False)
    )
    assert rt.online() is False


def test_online_cloud_needs_key():
    """云端没有 /health 可探，有 key 才算在线 —— 否则切到 DeepSeek 界面就死了。"""
    assert _runtime("deepseek", "").online() is False
    assert _runtime("deepseek", "sk-x").online() is True


def test_warm_does_nothing_on_cloud():
    """云端没有前缀缓存，别为了预热白花一次请求。"""
    assert _runtime("deepseek", "sk-x").warm("demo") == 0.0


# ---------- 等他醒（窗口比模型先出来的代价） ----------


def test_wait_online_returns_at_once_when_awake(monkeypatch):
    rt = _runtime()
    monkeypatch.setattr(rt, "online", lambda: True)
    started = time.monotonic()
    assert rt.wait_online(timeout=10) is True
    assert time.monotonic() - started < 0.5


def test_wait_online_gives_up_at_once_without_model_files(monkeypatch):
    """二进制或权重都没有，等也等不来 —— 别让页面挂七十秒。"""
    rt = _runtime()
    monkeypatch.setattr(rt, "online", lambda: False)
    monkeypatch.setattr(state.localmodel, "program", lambda cfg: None)
    started = time.monotonic()
    assert rt.wait_online(timeout=10) is False
    assert time.monotonic() - started < 0.5


def test_wait_online_notices_the_model_waking_up(monkeypatch):
    rt = _runtime()
    seen = {"n": 0}

    def waking() -> bool:
        seen["n"] += 1
        return seen["n"] > 2  # 前两次还没醒

    monkeypatch.setattr(rt, "online", waking)
    monkeypatch.setattr(state.localmodel, "program", lambda cfg: (None, None))
    assert rt.wait_online(timeout=5) is True
    assert seen["n"] == 3


def test_warm_says_so_when_it_never_wakes(monkeypatch):
    rt = _runtime()
    monkeypatch.setattr(rt, "wait_online", lambda timeout=0: False)
    assert rt.warm("demo") == -1.0


def test_warm_warms_only_once(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "sessions_dir", lambda: tmp_path / "sessions")

    rt = Runtime(load_config())
    monkeypatch.setattr(rt, "wait_online", lambda timeout=0: True)
    entry = rt.entry("demo")
    calls = {"n": 0}

    def warmup() -> float:
        calls["n"] += 1
        return 0.25

    monkeypatch.setattr(entry.engine, "warmup", warmup)
    assert rt.warm("demo") == 0.25
    assert rt.warm("demo") == 0.25
    assert calls["n"] == 1


# ---------- 改配置 ----------


def test_invalidate_keeps_session(tmp_path, monkeypatch):
    """改个温度不该让人失忆。"""
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "sessions_dir", lambda: tmp_path / "sessions")

    rt = Runtime(load_config())
    before = rt.entry("demo").engine.session
    before.append("user", "刚才说到哪儿了")

    rt.invalidate()

    after = rt.entry("demo").engine.session
    assert after is before
    assert [e.content for e in after.events] == ["刚才说到哪儿了"]


def test_restart_session_really_forgets(tmp_path, monkeypatch):
    """[新] 要真的忘。

    只把引擎丢掉是不够的：下一次请求会 resume 到最近那个文件，
    旧对话原封不动回来，界面上看就是「点了没反应」。
    """
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(paths, "sessions_dir", lambda: tmp_path / "sessions")

    rt = Runtime(load_config())
    old = rt.entry("demo").engine.session
    old.append("user", "刚才说到哪儿了")
    old_path = old.path

    rt.restart_session("demo")

    fresh = rt.entry("demo").engine.session
    assert fresh.path != old_path
    assert fresh.events == []
