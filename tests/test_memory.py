"""检索：分词、Director、BM25、预算。"""

from __future__ import annotations

import pytest

from openhuman.memory import build, citations, fit, plan
from openhuman.memory.index import MIN_COVERAGE, MemoryIndex
from openhuman.memory.text import bigrams, strip_weak, tokenize
from openhuman.pack import load_pack
from openhuman.pack.schema import MemoryCard
from openhuman.paths import pack_dir


@pytest.fixture(scope="module")
def pack():
    return load_pack(pack_dir("demo"))


@pytest.fixture(scope="module")
def index(pack):
    return build(pack)


# ---------- 分词 ----------


def test_tokenize_drops_stopwords():
    assert "记得" not in tokenize("你还记得吗")
    assert "怎么样" not in tokenize("今天怎么样")


def test_tokenize_keeps_years():
    assert "2010" in tokenize("2010年的事")


def test_bigrams_overlap_words():
    assert "手在" in bigrams("手在抖")
    assert strip_weak("你还记得那次") == "那次"


# ---------- Director ----------


def test_plan_extracts_year(pack):
    p = plan("2019年你们去哪儿了？", pack)
    assert p.years == [2019]
    assert p.ask is True


def test_plan_extracts_people(pack):
    p = plan("秀兰那天怎么样？", pack)
    assert "秀兰" in p.people


def test_plan_prefers_longer_names():
    from openhuman.memory.director import extract_people

    hits = extract_people("陈建国和陈磊", ["陈", "陈磊", "陈建国"])
    assert "陈建国" in hits


def test_casual_is_not_retrieved(pack):
    p = plan("你好", pack)
    assert p.ask is False


def test_talking_about_yourself_is_not_a_memory_question(pack):
    """「今天有点累」不是问他往事。

    第四轮之前这一句会翻出黄山那张卡，他张口就是「嗯……记得。2019 年
    10 月 26 号，和秀兰去黄山」—— 一个人不会因为你喊累就开始讲自己的旅行。
    """
    for text in ["今天有点累", "我回来了", "外面下雨了", "我想你了"]:
        p = plan(text, pack)
        assert p.ask is False, text
        assert p.about_past is False, text


def test_past_cue_opens_recall(pack):
    p = plan("台风那年", pack)
    assert p.ask is True
    assert p.about_past is True


def test_general_past_is_not_an_event(pack):
    """「以前教什么课」答案是人格包里的，不该被提醒「想不起来」。"""
    p = plan("你以前教什么课", pack)
    assert p.ask is True
    assert p.cue is True
    assert p.about_past is False


def test_weather_question_is_asked_but_is_not_the_past(pack):
    p = plan("今天天气怎么样？", pack)
    assert p.ask is True
    assert p.about_past is False, "问天气不该被提醒「想不起来」"


def test_small_talk_gets_no_cards(index, pack):
    assert index.search(plan("今天有点累", pack)) == []
    assert index.search(plan("我回来了", pack)) == []


def test_follow_up_detection(pack):
    from openhuman.memory import follows_up

    assert follows_up("那天你讲话了吗", pack)
    assert follows_up("后来呢", pack)
    assert not follows_up("那次去黄山怎么走的", pack), "自带地名，自己能检索"
    assert not follows_up("那你老伴呢", pack)


# ---------- 检索 ----------


def test_known_question_hits_right_card(index, pack):
    hits = index.search(plan("你还记得儿子结婚那天吗？", pack))
    assert hits and hits[0].card.id == "2010-05-02-儿子结婚"


def test_year_routes_to_that_year(index, pack):
    hits = index.search(plan("2019年你们去哪儿玩了？", pack))
    assert hits and hits[0].card.id == "2019-10-26-和老伴去黄山"


def test_out_of_scope_returns_nothing(index, pack):
    assert index.search(plan("今天天气怎么样？", pack)) == []
    assert index.search(plan("帮我写个 Python 脚本", pack)) == []


def test_casual_returns_nothing(index, pack):
    assert index.search(plan("你好", pack)) == []


def test_coverage_gate_is_real(index, pack):
    hits = index.search(plan("量子力学是什么", pack))
    assert hits == []


def test_person_only_in_cards_is_known(pack):
    """王倩没写进「人物」，只在卡里出现；问到她时也要认得出来。"""
    assert "王倩" in pack.person_names()
    assert "王倩" in plan("你还记得王倩第一次来家里吗", pack).people


def test_asking_about_unrecorded_person_returns_nothing(index, pack):
    """问了具体某个人，但没有一张卡讲这件事 —— 宁可空手，也别拿错卡顶上。"""
    hits = index.search(plan("你还记得王倩第一次来家里吗", pack))
    assert hits == []


def test_person_gate_keeps_the_right_card(index, pack):
    hits = index.search(plan("秀兰做手术那天你在干嘛？", pack))
    assert hits and hits[0].card.id == "2023-05-12-老伴做手术"


def test_index_skips_cards_without_source(pack):
    broken = pack.model_copy(deep=True)
    broken.memories[0] = broken.memories[0].model_copy(update={"source": ""})
    idx = MemoryIndex(broken)
    assert len(idx) == len(pack.memories) - 1


def test_empty_pack_index():
    from openhuman.pack.schema import HumanMeta, Pack

    empty = Pack(meta=HumanMeta(slug="x", name="无"), soul="s", rules="r")
    idx = MemoryIndex(empty)
    assert len(idx) == 0
    assert idx.search(plan("随便问问", empty)) == []


# ---------- 预算 ----------


def _card(cid: str, body: str) -> MemoryCard:
    from datetime import date

    return MemoryCard(
        id=cid, date=date(2020, 1, 1), title="标题", source="s", salience=3, body=body
    )


def test_fit_respects_budget():
    from openhuman.memory.index import Hit

    hits = [Hit(card=_card(f"c{i}", "字" * 200), score=1.0, coverage=1.0) for i in range(5)]
    cards = fit(hits, budget=200)
    assert cards
    from openhuman import tokens

    total = sum(tokens.estimate(c.render()) for c in cards)
    assert total <= 200


def test_fit_trims_last_card():
    from openhuman.memory.index import Hit

    hits = [Hit(card=_card("long", "很长的一段回忆。" * 60), score=1.0, coverage=1.0)]
    cards = fit(hits, budget=150)
    assert len(cards) == 1
    assert len(cards[0].body) < 60 * 7


def test_citations():
    assert citations([_card("a", ""), _card("b", "")]) == ["a", "b"]


def test_min_coverage_sane():
    assert 0 < MIN_COVERAGE <= 1
