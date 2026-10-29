"""HTTP 层：页面、API、SSE、设置写回。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import openhuman.server.app as server_app
from openhuman.server.app import _set_toml, app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_pages_render():
    for path, must in [
        ("/", "open human"),
        ("/chat/demo", "PERSONA LOADING"),
        ("/settings", "temperature"),
    ]:
        res = client.get(path)
        assert res.status_code == 200
        assert must in res.text


def test_every_page_is_the_same_room():
    """三层光（上面冷、下面暖、四周暗）三页都得在。

    屋子是同一间屋子：从门口走到他面前，光不该换一套。
    """
    for path in ("/", "/chat/demo", "/settings"):
        html = client.get(path).text
        for layer in ('class="aura"', 'class="glow"', 'class="vignette"'):
            assert layer in html, f"{path} 里少了 {layer}"


def test_chat_has_something_behind_the_card():
    """记忆卡打开时屋子要退到后面去，所以得有一层能挡住、能点的幕。"""
    assert 'class="scrim"' in client.get("/chat/demo").text


def test_static_files():
    for name in ("style.css", "core.js", "chat.js", "index.js", "settings.js"):
        assert client.get(f"/s/{name}").status_code == 200


def test_static_files_are_clean_utf8():
    """防编码事故：中文被 GBK 往返一次后仍是合法 UTF-8，不会报错，但会白屏。"""
    from pathlib import Path

    root = Path(server_app.STATIC)
    for path in root.iterdir():
        if path.suffix not in (".js", ".css", ".html"):
            continue
        text = path.read_text(encoding="utf-8")
        assert "\ufffd" not in text, f"{path.name} 有替换字符"
        # 典型乱码残骸：GBK 误读后常出现的生僻字
        for marker in ("銆", "锛", "鍜", "鐨", "涓€", "璁剧"):
            assert marker not in text, f"{path.name} 含乱码 {marker}"


def test_core_js_punctuation_is_intact():
    from pathlib import Path

    core = (Path(server_app.STATIC) / "core.js").read_text(encoding="utf-8")
    for ch in "，。！？…":
        assert ch in core, f"core.js 里缺标点 {ch}"
    assert "共享工具" in core
    assert "函数" not in core  # 老注释里没有这个词，出现说明被串改了


def test_humans_lists_demo():
    data = client.get("/api/humans").json()
    slugs = [h["slug"] for h in data["humans"]]
    assert "demo" in slugs
    demo = next(h for h in data["humans"] if h["slug"] == "demo")
    assert demo["name"] == "陈建国"
    assert demo["memories"] == 10


def test_human_detail():
    data = client.get("/api/humans/demo").json()
    assert data["first_line"]
    assert data["indexed"] == 10
    # 页面靠它决定「你不说话的时候他先开口说什么」
    assert data["idle_line"] == "……我在这儿。"


def test_unknown_slug_is_404():
    assert client.get("/api/humans/nope").status_code == 404


def test_card_detail():
    data = client.get("/api/humans/demo/cards/2010-05-02-儿子结婚").json()
    assert data["date"] == "2010-05-02"
    assert "王倩" in data["body"]
    # 抽屉只画这些；type / source / emotion 没上屏，就别过网络
    assert set(data) == {"id", "date", "title", "people", "places", "tags", "body"}


def test_missing_card_is_404():
    assert client.get("/api/humans/demo/cards/nope").status_code == 404


def test_empty_message_rejected():
    assert client.post("/api/chat/demo", json={"text": "  "}).status_code == 400


def _install_fake_engine(monkeypatch, chunks=("记", "得。")):
    """换掉 runtime()，别让测试碰到真模型：以前这条用例只有在 llama-server
    恰好开着的时候才过，等于没测。"""
    import threading
    from types import SimpleNamespace

    from openhuman.chat.engine import Turn
    from openhuman.memory import plan
    from openhuman.pack import load_pack
    from openhuman.paths import pack_dir

    recorded: dict = {}

    class FakeEngine:
        persona = "P"
        tools = None
        on_event = None
        pack = SimpleNamespace(root=pack_dir("demo"))

        def __init__(self):
            self.last = None
            self.session = SimpleNamespace(path=None)

        def prepare(self, text):
            # 网页这条路必须先问引擎拿卡：追问要不要接上一轮，只有引擎知道。
            recorded["prepared"] = text
            return [], plan(text, load_pack(pack_dir("demo")))

        def respond(self, text, cards=None):
            recorded["tools"] = self.tools is not None
            self.last = Turn(user_text=text, reply="".join(chunks), citations=[])
            yield from chunks

    entry = SimpleNamespace(engine=FakeEngine(), lock=threading.Lock())
    monkeypatch.setattr(
        server_app, "runtime", lambda: SimpleNamespace(entry=lambda slug: entry)
    )
    return recorded


def test_chat_streams_sse(monkeypatch):
    recorded = _install_fake_engine(monkeypatch)

    with client.stream("POST", "/api/chat/demo", json={"text": "记得吗"}) as res:
        assert res.status_code == 200
        body = "".join(res.iter_text())

    events = [line[7:] for line in body.splitlines() if line.startswith("event: ")]
    assert events[0] == "meta"
    assert "delta" in events
    assert events[-1] == "done"
    assert "记得。" in body
    assert recorded["prepared"] == "记得吗"


def test_chat_accepts_tool_flags(monkeypatch):
    """带 tools 的请求要真的把工具装上，并且正常收尾。"""
    recorded = _install_fake_engine(monkeypatch)

    with client.stream(
        "POST", "/api/chat/demo", json={"text": "看看笔记", "tools": True, "allow_mutating": False}
    ) as res:
        assert res.status_code == 200
        body = "".join(res.iter_text())

    assert "event: done" in body
    assert recorded["tools"] is True


def test_new_session():
    assert client.post("/api/session/demo/new").json() == {"ok": True}


def test_session_state_empty_when_no_engine():
    """没开过会话就返回空，不新建文件。"""
    data = client.get("/api/session/demo").json()
    assert data["messages"] == []


def test_session_state_replays_dialogue(monkeypatch):
    """刷新页面靠这个把记录画回来，所以角色、引文、卡片信息都要在。"""
    import threading
    from types import SimpleNamespace

    from openhuman.chat import Session
    from openhuman.pack import load_pack
    from openhuman.paths import pack_dir

    session = Session("demo", None)
    session.append("user", "你还记得王倩吗")
    session.append(
        "assistant",
        "记得。",
        model="MiniCPM5-2B",
        citations=["2010-05-02-儿子结婚"],
    )
    entry = SimpleNamespace(
        engine=SimpleNamespace(session=session, pack=load_pack(pack_dir("demo"))),
        lock=threading.Lock(),
    )

    monkeypatch.setattr(
        server_app, "runtime", lambda: SimpleNamespace(existing=lambda slug: entry)
    )
    data = client.get("/api/session/demo").json()

    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]
    assert data["messages"][0]["text"] == "你还记得王倩吗"
    assert data["messages"][1]["citations"] == ["2010-05-02-儿子结婚"]
    # 引用要能画成「2010.05.02 儿子结婚」，而不是一串 id
    card = data["cards"]["2010-05-02-儿子结婚"]
    assert card["date"] == "2010-05-02"
    assert card["title"] == "儿子结婚"


# ---------- 配置写回 ----------


def test_set_toml_replaces_existing_key():
    text = "[app]\ndefault_model = 'llama'\n\n[llama]\ntemperature = 0.75\ntop_p = 0.9\n"
    out = _set_toml(text, "llama", "temperature", 0.8)
    assert "temperature = 0.8" in out
    assert "top_p = 0.9" in out
    assert out.count("temperature") == 1


def test_set_toml_keeps_other_sections():
    text = "[llama]\ntemperature = 0.75\n\n[deepseek]\ntemperature = 0.95\n"
    out = _set_toml(text, "llama", "temperature", 0.8)
    assert "temperature = 0.8" in out
    assert "temperature = 0.95" in out


def test_set_toml_adds_missing_section():
    out = _set_toml("[app]\nx = 1\n", "llama", "top_p", 0.9)
    assert "[llama]" in out
    assert "top_p = 0.9" in out


def test_set_toml_preserves_comments():
    text = "# 注释\n[llama]\n# 温度\ntemperature = 0.75\n"
    out = _set_toml(text, "llama", "temperature", 0.8)
    assert "# 注释" in out and "# 温度" in out


def test_settings_roundtrip(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "config.toml"
    cfg.write_text("[llama]\ntemperature = 0.75\n", encoding="utf-8")
    monkeypatch.setattr(server_app, "config_path", lambda: cfg)

    res = client.post("/api/settings", json={"temperature": 0.8})
    assert res.status_code == 200
    assert "temperature = 0.8" in cfg.read_text(encoding="utf-8")

    data = client.get("/api/settings").json()
    assert data["llama"]["temperature"] == 0.8


# ---------- 等他醒 ----------


def test_settings_tells_you_which_beta_this_is():
    """设置页脚显示版本：拿到 beta 的人得知道自己手上是哪一版。"""
    from openhuman import __version__

    assert client.get("/api/settings").json()["version"] == __version__


def test_settings_never_returns_a_key():
    """/api/settings 是给页面看的。key 一律不出这个进程。"""
    data = client.get("/api/settings").json()
    assert "api_key" not in data["llama"]
    assert "api_key" not in data["deepseek"]
    assert data["has_deepseek_key"] is False


def test_warm_reports_failure_instead_of_hanging(monkeypatch):
    """模型起不来时给 ok:false，页面才能说「他没醒」，而不是永远转圈。"""
    from types import SimpleNamespace

    monkeypatch.setattr(
        server_app, "runtime", lambda: SimpleNamespace(warm=lambda slug: -1.0)
    )
    assert client.post("/api/warm/demo").json() == {"ok": False, "seconds": 0.0}


def test_warm_reports_seconds(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        server_app, "runtime", lambda: SimpleNamespace(warm=lambda slug: 1.234)
    )
    assert client.post("/api/warm/demo").json() == {"ok": True, "seconds": 1.23}
