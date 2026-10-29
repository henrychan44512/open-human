"""评测工具：题库、指标、回答层检查。"""

from __future__ import annotations

from datetime import date

from openhuman.eval import Case, Row, check_answer, extract_facts, load_cases, summarize
from openhuman.pack.schema import MemoryCard


def _card(cid: str, body: str) -> MemoryCard:
    return MemoryCard(
        id=cid, date=date(2010, 5, 2), title="标题", source="s", salience=3, body=body
    )


def test_questions_file_loads():
    cases = load_cases()
    assert len(cases) == 32
    assert sum(1 for c in cases if c.kind == "memory") == 25
    assert sum(1 for c in cases if c.kind == "out_of_scope") == 7
    assert len({c.id for c in cases}) == 32
    # 已知局限单独标记，不和回归混在一起
    assert [c.id for c in cases if c.known] == ["q32"]


def test_every_expect_id_exists_in_demo_pack():
    from openhuman.pack import load_pack
    from openhuman.paths import pack_dir

    ids = {m.id for m in load_pack(pack_dir("demo")).memories}
    for case in load_cases():
        for expect in case.expect:
            assert expect in ids, f"{case.id} 期望的 {expect} 不存在"


def test_summarize_counts():
    rows = [
        Row(Case("a", "q", "memory", ["x"]), ["x"], True),
        Row(Case("b", "q", "memory", ["x"]), ["y"], False),
        Row(Case("c", "q", "out_of_scope", []), [], True),
        Row(Case("d", "q", "out_of_scope", []), ["z"], False),
    ]
    s = summarize(rows)
    assert s["hit"] == 1 and s["hit_rate"] == 0.5
    assert s["top1"] == 1
    assert s["quiet"] == 1 and s["quiet_rate"] == 0.5


def test_extract_facts():
    dates, years = extract_facts("2010年5月2日他结婚，2013年有了孩子，那还是1998年的事。")
    assert "2010年5月2日" in dates
    assert "2013年" in dates
    assert years == []


def test_extract_bare_year():
    dates, years = extract_facts("大概是 1998 那一年。")
    assert dates == []
    assert years == ["1998"]


def test_check_answer_accepts_quoted_dates():
    card = _card("w", "2010 年 5 月 2 日，儿子在杭州办婚礼。")
    assert check_answer("是 2010 年 5 月 2 日结的婚。", [card]) == []


def test_check_answer_flags_invented_date():
    card = _card("w", "2010 年 5 月 2 日，儿子在杭州办婚礼。")
    bad = check_answer("那是 1998 年 3 月的事。", [card])
    assert "1998年3月" in bad


def test_check_answer_empty_reply():
    assert check_answer("", []) == []
