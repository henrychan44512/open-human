"""prompt 组装：顺序就是性能（BUILD.md §11 N-01 / N-03）。"""

from __future__ import annotations

from openhuman.llm import build_messages, render_memory, warmup_messages
from openhuman.pack.schema import MemoryCard


def _card(cid: str, title: str, body: str = "正文") -> MemoryCard:
    from datetime import date

    return MemoryCard(
        id=cid,
        date=date(2020, 1, 1),
        title=title,
        source=f"memories/{cid}.md",
        salience=3,
        body=body,
    )


def test_system_is_first_and_stable():
    persona = "## 你是谁\n你叫陈建国。"
    messages = build_messages(persona, [], "你好")
    assert messages[0] == {"role": "system", "content": persona}


def test_history_sits_between_system_and_user():
    history = [
        {"role": "user", "content": "第一句"},
        {"role": "assistant", "content": "第二句"},
    ]
    messages = build_messages("P", history, "第三句")
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[3]["content"] == "第三句"


def test_memory_goes_right_before_the_question():
    cards = [_card("2023-05-12-hospital", "老伴做手术")]
    messages = build_messages("P", [], "你还记得吗？", cards)
    content = messages[-1]["content"]
    assert content.index("<记忆>") < content.index("你还记得吗？")
    assert "[mem: 2023-05-12-hospital]" in content
    # 记忆不能进 system
    assert "记忆" not in messages[0]["content"]


def test_no_memory_means_plain_text():
    messages = build_messages("P", [], "随便聊聊", [])
    assert messages[-1]["content"] == "随便聊聊"


def test_missed_memory_gets_a_no_fabrication_note():
    """问了往事又检索不到：先把「不许编」放在问题前面。"""
    messages = build_messages("P", [], "你还记得王倩第一次来家里吗", [], missed=True)
    content = messages[-1]["content"]
    assert "想不起来" in content
    assert content.endswith("你还记得王倩第一次来家里吗")


def test_casual_turn_gets_no_note():
    """打招呼不该被塞一句「你脑子里是空的」。"""
    assert build_messages("P", [], "你好", [], missed=False)[-1]["content"] == "你好"


def test_cards_win_over_miss_note():
    cards = [_card("a", "甲")]
    content = build_messages("P", [], "问", cards, missed=True)[-1]["content"]
    assert content.startswith("<记忆>")
    assert "脑子里是空的" not in content


def test_render_memory_shape():
    cards = [_card("a", "甲"), _card("b", "乙")]
    block = render_memory(cards)
    assert block.startswith("<记忆>")
    assert block.endswith("</记忆>")
    assert block.count("[mem: ") == 2
    assert render_memory([]) == ""


def test_warmup_messages_are_minimal():
    warm = warmup_messages("P")
    assert len(warm) == 2
    assert warm[0]["role"] == "system"
    assert len(warm[1]["content"]) <= 8


# ---------- 钟点 ----------


def _tz():
    from datetime import timedelta, timezone

    return timezone(timedelta(hours=8))


def test_clock_reads_like_a_person():
    from datetime import datetime

    from openhuman.llm import clock_line

    assert clock_line(datetime(2026, 10, 27, 19, 52, tzinfo=_tz())) == (
        "（此刻：10 月 27 日，星期二，晚上 7 点 52 分。）"
    )
    assert "早上 8 点 05 分" in clock_line(datetime(2026, 10, 27, 8, 5, tzinfo=_tz()))
    assert "凌晨 12 点 30 分" in clock_line(datetime(2026, 10, 27, 0, 30, tzinfo=_tz()))
    assert "中午 12 点" in clock_line(datetime(2026, 10, 27, 12, 0, tzinfo=_tz()))


def test_clock_goes_before_the_question_and_after_memory():
    cards = [_card("a", "甲")]
    content = build_messages("P", [], "问", cards, clock="（此刻：…）")[-1]["content"]
    assert content.startswith("（此刻：…）")
    assert content.index("<记忆>") < content.index("问")
    assert content.index("问") < content.index("挑一个细节")


def test_cards_bring_a_brevity_note():
    """卡片在眼前时，2B 会把整张卡念出来；这句是压在问题后面的闸。"""
    content = build_messages("P", [], "问", [_card("a", "甲")])[-1]["content"]
    assert content.endswith("（一两句话，挑一个细节说。）")


def test_no_cards_no_brevity_note():
    assert build_messages("P", [], "问")[-1]["content"] == "问"


def test_no_clock_by_default():
    assert build_messages("P", [], "你好")[-1]["content"] == "你好"
