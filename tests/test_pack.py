"""人格包加载与校验。"""

from __future__ import annotations

from pathlib import Path

import pytest

from openhuman import paths
from openhuman.pack import PackError, compile_persona, load_pack, persona_tokens
from openhuman.pack.persona import PERSONA_BUDGET


@pytest.fixture(scope="module")
def demo():
    return load_pack(paths.pack_dir("demo"))


def test_demo_pack_loads(demo):
    assert demo.meta.slug == "demo"
    assert demo.meta.name == "陈建国"
    assert demo.meta.presence == "living"
    assert demo.soul
    assert demo.rules


def test_demo_memories(demo):
    assert len(demo.memories) == 10
    assert all(m.retrievable for m in demo.memories)
    assert all(m.source for m in demo.memories)
    assert all(m.body for m in demo.memories)
    ids = [m.id for m in demo.memories]
    assert len(ids) == len(set(ids)), "id 必须唯一"


def test_lines_he_says_on_his_own(demo):
    """他不用你开口也能说三句：进门、隔天、还有你半天不出声。"""
    assert demo.meta.first_line and demo.meta.wake_line and demo.meta.sleep_line
    assert demo.meta.idle_line, "demo 里那句「我在这儿」是他先开口的凭据"
    # 老包没有这个字段，不许因为多了它加载失败
    from openhuman.pack.schema import HumanMeta

    assert HumanMeta(slug="x", name="某人").idle_line == ""


def test_demo_people(demo):
    names = {p.name for p in demo.people}
    assert names == {"李秀兰", "陈磊", "陈念"}
    all_names = demo.person_names()
    assert "秀兰" in all_names and "磊磊" in all_names and "念念" in all_names


def test_persona_is_deterministic(demo):
    assert compile_persona(demo) == compile_persona(demo)


def test_persona_within_budget(demo):
    n, exact = persona_tokens(demo)
    assert not exact  # 没有 server 时走估算
    assert n <= PERSONA_BUDGET, f"persona {n} tok 超过预算 {PERSONA_BUDGET}"


def test_persona_order(demo):
    text = compile_persona(demo)
    assert text.index("## 你是谁") < text.index("## 你说话的口气") < text.index("## 边界")


def test_missing_required_file(tmp_path: Path):
    (tmp_path / "SOUL.md").write_text("x", encoding="utf-8")
    with pytest.raises(PackError, match="缺少必填文件"):
        load_pack(tmp_path)


def test_empty_soul(tmp_path: Path):
    (tmp_path / "human.yaml").write_text("slug: t\nname: 测试\n", encoding="utf-8")
    (tmp_path / "SOUL.md").write_text("   \n", encoding="utf-8")
    (tmp_path / "RULES.md").write_text("规矩", encoding="utf-8")
    with pytest.raises(PackError, match="SOUL.md 是空的"):
        load_pack(tmp_path)


def test_memory_without_source_is_not_retrievable(tmp_path: Path):
    (tmp_path / "human.yaml").write_text("slug: t\nname: 测试\n", encoding="utf-8")
    (tmp_path / "SOUL.md").write_text("你叫测试。", encoding="utf-8")
    (tmp_path / "RULES.md").write_text("说短句。", encoding="utf-8")
    mem = tmp_path / "memories"
    mem.mkdir()
    (mem / "a.md").write_text(
        "---\nid: a\ndate: 2020-01-01\ntitle: 一件事\nsource: ''\nsalience: 3\n---\n\n正文\n",
        encoding="utf-8",
    )
    pack = load_pack(tmp_path)
    assert len(pack.memories) == 1
    assert not pack.memories[0].retrievable
    assert pack.working_memories() == []
    assert any("缺 source" in w for w in pack.warnings)


def test_bad_memory_is_skipped_with_warning(tmp_path: Path):
    (tmp_path / "human.yaml").write_text("slug: t\nname: 测试\n", encoding="utf-8")
    (tmp_path / "SOUL.md").write_text("你叫测试。", encoding="utf-8")
    (tmp_path / "RULES.md").write_text("说短句。", encoding="utf-8")
    mem = tmp_path / "memories"
    mem.mkdir()
    (mem / "bad.md").write_text("---\nid: bad\n---\n\n少了日期和标题\n", encoding="utf-8")
    pack = load_pack(tmp_path)
    assert pack.memories == []
    assert any("跳过 bad.md" in w for w in pack.warnings)


def test_slug_rules():
    assert paths.check_slug("demo") == "demo"
    assert paths.check_slug("chen-jianguo_2") == "chen-jianguo_2"
    # 递给人填的时候，文件夹名往往是「我爸」这种；不许中文等于劝退
    assert paths.check_slug("我爸") == "我爸"
    assert paths.check_slug("陈建国") == "陈建国"
    for bad in ["..", "Demo", "a/b", "a" * 65, "", "我爸 的"]:
        with pytest.raises(ValueError):
            paths.check_slug(bad)
