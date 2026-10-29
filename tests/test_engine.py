"""对话引擎：一轮、多轮、预热、落盘、检索接入、工具循环。"""

from __future__ import annotations

from fake_llm import FakeClient
from openhuman.chat import Engine, Session
from openhuman.memory import build as build_index
from openhuman.pack import load_pack
from openhuman.paths import pack_dir
from openhuman.tools import Tools, scope_for


def _engine(replies: list[str] | str = "嗯。", *, index: bool = False) -> tuple[Engine, FakeClient, Session]:
    pack = load_pack(pack_dir("demo"))
    client = FakeClient(replies)
    session = Session("demo", None)
    idx = build_index(pack) if index else None
    return Engine(pack, client, session, index=idx), client, session


def _tool_engine(
    replies: list[str],
    calls: list[list[dict]],
    *,
    confirm=None,
    events: list | None = None,
) -> tuple[Engine, FakeClient, Session]:
    pack = load_pack(pack_dir("demo"))
    client = FakeClient(replies, calls=calls)
    session = Session("demo", None)
    tools = Tools(scope_for(pack.root), confirm=confirm)
    sink = events if events is not None else []
    engine = Engine(pack, client, session, tools=tools, on_event=sink.append)
    return engine, client, session


def _call(name: str, args: str, call_id: str = "c1") -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": args},
    }


def test_one_turn_streams_and_persists():
    engine, client, session = _engine("我记得的。")
    out = "".join(engine.respond("你还记得吗？"))

    assert out == "我记得的。"
    assert len(session) == 2
    assert session.events[0].role == "user"
    assert session.events[0].content == "你还记得吗？"
    assert session.events[1].role == "assistant"
    assert session.events[1].model == client.model
    assert engine.last is not None and engine.last.reply == "我记得的。"


def test_prompt_layout_on_first_turn():
    engine, client, _ = _engine()
    list(engine.respond("你好"))
    messages = client.last_messages
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"].endswith("你好")
    assert messages[0]["content"] == engine.persona


def test_every_turn_gets_the_clock():
    """他看得见钟：这一行每轮都在，而且只在最后一轮。"""
    engine, client, _ = _engine(["嗯。", "嗯。"])
    list(engine.respond("你好"))
    list(engine.respond("几点了"))

    messages = client.last_messages
    assert "此刻" in messages[-1]["content"]
    assert "此刻" not in messages[1]["content"]
    assert "此刻" not in messages[0]["content"]
    # 钟点不能落进会话 —— 历史要只追加、每轮不变
    assert all("此刻" not in e.content for e in engine.session.events)


def test_second_turn_carries_history():
    engine, client, session = _engine(["第一次。", "第二次。"])
    list(engine.respond("一"))
    list(engine.respond("二"))

    messages = client.last_messages
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[1]["content"] == "一"
    assert messages[2]["content"] == "第一次。"
    assert len(session) == 4


def test_memory_cards_land_in_last_user_message():
    engine, client, _ = _engine()
    pack = engine.pack
    card = pack.memories[0]
    list(engine.respond("你记得吗？", cards=[card]))
    content = client.last_messages[-1]["content"]
    assert f"[mem: {card.id}]" in content
    assert "你记得吗？" in content
    assert content.index("<记忆>") < content.index("你记得吗？")


def test_empty_reply_is_not_persisted():
    engine, _, session = _engine("")
    list(engine.respond("在吗"))
    assert len(session) == 1
    assert session.events[0].role == "user"


def test_warmup_sends_only_persona_and_marker():
    engine, client, session = _engine()
    cost = engine.warmup()
    assert cost >= 0
    assert len(session) == 0, "预热不能污染会话"
    messages = client.last_messages
    assert len(messages) == 2
    assert messages[0]["content"] == engine.persona


def test_history_budget_caps_old_turns():
    engine, client, session = _engine(["好。"])
    for i in range(30):
        list(engine.respond(f"第{i}个问题" * 5))

    capped = session.history(100)
    assert 0 < len(capped) < 60
    assert capped[-1]["role"] == "assistant"

    # 预算内的部分总量必须不超
    from openhuman import tokens

    total = sum(tokens.estimate(m["content"]) for m in capped)
    assert total <= 100 + max(tokens.estimate(m["content"]) for m in capped)


# ---------- 检索接入 ----------


def test_retrieval_fills_citations():
    engine, client, session = _engine(index=True)
    out = "".join(engine.respond("你还记得儿子结婚那天吗？"))

    last = engine.last
    assert last is not None
    assert last.citations == ["2010-05-02-儿子结婚"]
    assert "[mem: 2010-05-02-儿子结婚]" in client.last_messages[-1]["content"]
    assert out
    # 引用要落盘
    assistant = session.events[-1]
    assert assistant.citations == ["2010-05-02-儿子结婚"]


def test_retrieval_skips_out_of_scope():
    engine, client, _ = _engine(index=True)
    list(engine.respond("今天天气怎么样？"))

    last = engine.last
    assert last is not None
    assert last.citations == []
    assert "记忆" not in client.last_messages[-1]["content"]


def test_plan_is_recorded():
    engine, _, _ = _engine(index=True)
    list(engine.respond("2019年你们去哪儿玩了？"))
    assert engine.last is not None
    assert engine.last.plan is not None
    assert 2019 in engine.last.plan.years


def test_explicit_cards_win_over_retrieval():
    engine, client, _ = _engine(index=True)
    card = engine.pack.memories[0]
    list(engine.respond("随便说说", cards=[card]))
    assert engine.last is not None
    assert engine.last.citations == [card.id]


def test_follow_up_continues_the_same_memory():
    """「那天你讲话了吗」说的是婚礼，不该重新检索成父亲那张卡。"""
    engine, client, _ = _engine(index=True)
    list(engine.respond("你还记得儿子结婚那天吗？"))
    list(engine.respond("那天你讲话了吗"))

    assert engine.last is not None
    assert engine.last.citations == ["2010-05-02-儿子结婚"]
    assert "[mem: 2010-05-02-儿子结婚]" in client.last_messages[-1]["content"]


def test_new_memory_question_drops_the_old_topic():
    engine, _, _ = _engine(index=True)
    list(engine.respond("你还记得你第一次上讲台吗"))
    list(engine.respond("你还记得发大水那年吗"))
    assert engine.last is not None
    assert engine.last.citations == ["1985-06-15-发大水那年在走廊上课"]


def test_follow_up_without_a_topic_is_just_a_question():
    """上一轮没说过什么事，追问就退回普通检索，不能凭空拽一张卡。"""
    engine, _, _ = _engine(index=True)
    assert engine._topic_card() is None
    list(engine.respond("你好"))
    assert engine._topic_card() is None


# ---------- 工具循环 ----------


def test_tool_loop_reads_file_then_answers():
    events = []
    engine, client, session = _tool_engine(
        ["", "笔记里写了血压，还有念念想学画画。"],
        [[_call("read_file", '{"path":"workspace/notes.md"}')], []],
        events=events,
    )
    out = "".join(engine.respond("看看我的笔记"))

    assert "笔记里写了" in out
    assert engine.last is not None
    assert len(engine.last.tools) == 1
    assert engine.last.tools[0]["name"] == "read_file"
    assert engine.last.tools[0]["ok"] is True

    assert events and events[0]["type"] == "tool"
    assert events[0]["ok"] is True

    roles = [m["role"] for m in client.last_messages]
    assert "tool" in roles
    assert any(m.get("tool_calls") for m in client.last_messages)

    assert session.events[-1].role == "assistant"
    assert "笔记里写了" in session.events[-1].content


def test_mutating_tool_denied_is_reported_honestly():
    engine, _, _ = _tool_engine(
        ["", "好，那我不写了。"],
        [[_call("write_file", '{"path":"x.md","content":"hi"}')], []],
        confirm=lambda spec, args: False,
    )
    out = "".join(engine.respond("帮我写个文件"))

    assert engine.last is not None
    assert engine.last.tools[0]["ok"] is False
    assert "没有同意" in engine.last.tools[0]["output"]
    assert out == "好，那我不写了。"


def test_tool_loop_stops_after_max_rounds():
    calls = [[_call("list_dir", "{}", f"c{i}")] for i in range(10)]
    engine, client, _ = _tool_engine([""] * 10, calls)
    list(engine.respond("一直看目录"))
    assert len(client.calls) <= 5


def test_no_tools_means_no_tool_fields():
    engine, client, _ = _engine("嗯。")
    list(engine.respond("你好"))
    assert client.tools_seen is None


def test_bad_arguments_do_not_crash():
    engine, _, _ = _tool_engine(
        ["", "看不懂。"],
        [[_call("read_file", "这不是 JSON")], []],
    )
    list(engine.respond("读一下"))
    assert engine.last is not None
    assert engine.last.tools[0]["ok"] is False
