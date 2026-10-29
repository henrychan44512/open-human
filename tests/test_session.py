"""会话 JSONL：写入、读回、树结构、预算、回放、续聊。"""

from __future__ import annotations

import json
from pathlib import Path

from openhuman import paths
from openhuman.chat import Session


def test_append_and_reload(tmp_path: Path):
    path = tmp_path / "s.jsonl"
    path.touch()
    session = Session("demo", path)
    session.append("user", "你还记得吗？")
    session.append("assistant", "嗯，记得。", model="MiniCPM5-2B", citations=["x"])

    again = Session.load(path)
    assert len(again) == 2
    assert again.events[0].content == "你还记得吗？"
    assert again.events[1].model == "MiniCPM5-2B"
    assert again.events[1].citations == ["x"]


# ---------- 续聊 ----------


def _line(session_id: str, content: str) -> str:
    return json.dumps(
        {
            "id": session_id,
            "parentId": None,
            "role": "user",
            "ts": "2026-01-01T00:00:00+08:00",
            "content": content,
            "model": "",
            "citations": [],
            "usage": {},
        },
        ensure_ascii=False,
    )


def test_resume_picks_the_newest(tmp_path: Path, monkeypatch):
    """关掉再打开，他该记得最近那次。"""
    folder = tmp_path / "demo"
    folder.mkdir()
    (folder / "2026-01-01-001.jsonl").write_text(_line("e1", "旧的") + "\n", encoding="utf-8")
    (folder / "2026-01-02-001.jsonl").write_text(_line("e1", "新的") + "\n", encoding="utf-8")
    monkeypatch.setattr(paths, "sessions_dir", lambda: tmp_path)

    session = Session.resume("demo")
    assert session.path.name == "2026-01-02-001.jsonl"
    assert [e.content for e in session.events] == ["新的"]


def test_resume_starts_fresh_when_empty(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(paths, "sessions_dir", lambda: tmp_path / "sessions")
    session = Session.resume("demo")
    assert session.events == []
    assert session.path is not None and session.path.exists()


def test_resume_ignores_a_broken_file(tmp_path: Path, monkeypatch):
    """文件坏了也不能让他起不来。"""
    folder = tmp_path / "demo"
    folder.mkdir()
    (folder / "2026-01-01-001.jsonl").write_text("这不是 json\n", encoding="utf-8")
    monkeypatch.setattr(paths, "sessions_dir", lambda: tmp_path)
    monkeypatch.setattr(
        paths, "new_session_path", lambda slug: folder / "2026-01-02-001.jsonl"
    )

    session = Session.resume("demo")
    assert session.events == []


def test_resume_skips_empty_files(tmp_path: Path, monkeypatch):
    """连点两次 [新]、或者跑一次测试，都会留下 0 字节的 .jsonl。

    按名字取最新就会挑中它 —— 于是界面刷新一看，他「什么都想不起来了」。
    这是真发生过的事，不是假想。
    """
    folder = tmp_path / "demo"
    folder.mkdir()
    (folder / "2026-01-01-001.jsonl").write_text(
        _line("e1", "昨天说的") + "\n", encoding="utf-8"
    )
    (folder / "2026-01-02-001.jsonl").touch()  # 空文件，比谁都新
    monkeypatch.setattr(paths, "sessions_dir", lambda: tmp_path)

    assert paths.latest_session("demo").name == "2026-01-01-001.jsonl"
    session = Session.resume("demo")
    assert [e.content for e in session.events] == ["昨天说的"]


def test_resume_starts_fresh_when_every_file_is_empty(tmp_path: Path, monkeypatch):
    folder = tmp_path / "demo"
    folder.mkdir()
    (folder / "2026-01-02-001.jsonl").touch()
    monkeypatch.setattr(paths, "sessions_dir", lambda: tmp_path)
    monkeypatch.setattr(
        paths, "new_session_path", lambda slug: tmp_path / "2026-01-02-002.jsonl"
    )

    session = Session.resume("demo")
    assert session.events == []
    assert session.path.name == "2026-01-02-002.jsonl"


def test_parent_chain(tmp_path: Path):
    session = Session("demo", None)
    a = session.append("user", "一")
    b = session.append("assistant", "二")
    c = session.append("user", "三")
    assert a.parent_id is None
    assert b.parent_id == a.id
    assert c.parent_id == b.id
    assert session.head_id == c.id


def test_branching(tmp_path: Path):
    session = Session("demo", None)
    root = session.append("user", "根")
    session.append("assistant", "答案一")
    session.append("assistant", "答案二", parent_id=root.id)
    assert session.events[2].parent_id == root.id


def test_history_respects_budget():
    session = Session("demo", None)
    for i in range(20):
        session.append("user", "问" * 40)
        session.append("assistant", "答" * 40)
    history = session.history(max_tokens=200)
    assert history
    assert len(history) < 40
    # 时间正序
    assert history[-1]["role"] == "assistant"
    assert history[0]["role"] == "user"


def test_history_is_plain_text():
    """历史里存的必须是用户原话，不能含注入的记忆块。"""
    session = Session("demo", None)
    session.append("user", "你还记得妈妈做手术那天吗？")
    session.append("assistant", "记得。")
    history = session.history(900)
    assert history[0]["content"] == "你还记得妈妈做手术那天吗？"
    assert "记忆" not in history[0]["content"]


def test_replay():
    session = Session("demo", None)
    session.append("user", "你来了。")
    session.append("assistant", "嗯。", model="MiniCPM5-2B", citations=["2023-05-12"])
    text = session.replay()
    assert "你: 你来了。" in text
    assert "参考: 2023-05-12" in text


def test_empty_session():
    session = Session("demo", None)
    assert len(session) == 0
    assert session.history(900) == []
    assert session.head_id is None
