"""单文件人格包：一份「human_data.md」塞进 humans/ 就能用。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from openhuman import paths
from openhuman.pack import PackError, load_pack
from openhuman.pack.humanfile import parse

SAMPLE = """\
# human_data

## 基本

名字：陈建国
称呼：老陈，陈老师
状态：活着

## 我是谁

退休中学语文老师，教了三十八年。不爱说漂亮话，学生怕我又来蹭饭。

## 我怎么说话

短句。爱用「你懂我意思吧」。损人的时候是笑着说的。

## 我不会

- 不知道就说「我不记得了」。
- 不评价没见过的家人。

## 记忆

### 2010-05-02 儿子结婚
地点：杭州
人物：儿子、儿媳
我在台上讲话，讲到一半哭了。稿子是前一晚写的。

### 1985 那场洪水

水漫到膝盖，我把备课笔记顶在头上走回来的。

### 没有年份的一件事

这张卡没有日期，应该被跳过。

## 人物

### 秀兰
称呼：秀兰
关系：妻子
话不多，爱操心。

## 我常说的话

- 「吃了饭再说。」
> 「怕什么，天塌下来当被子盖。」
"""


def test_a_single_file_is_a_whole_person(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(paths, "humans_dir", lambda: tmp_path)
    folder = tmp_path / "我爸"
    folder.mkdir()
    (folder / "human_data.md").write_text(SAMPLE, encoding="utf-8")

    assert paths.list_packs() == ["我爸"]           # 中文文件夹名也算
    pack = load_pack(folder)

    assert pack.name == "陈建国"
    assert pack.meta.aliases == ["老陈", "陈老师"]
    assert pack.meta.presence == "living"
    assert "教了三十八年" in pack.soul
    assert "你懂我意思吧" in pack.speech
    assert "不记得了" in pack.rules
    assert pack.people[0].name == "秀兰"
    assert pack.people[0].relation == "妻子"


def test_memories_come_from_h3_headings():
    pack = parse(SAMPLE, slug="我爸")
    ids = [m.id for m in pack.memories]

    assert ids == ["2010-05-02-儿子结婚", "1985-01-01-那场洪水"]   # 没日期那张被跳过
    wedding = pack.memories[0]
    assert wedding.date == date(2010, 5, 2)
    assert wedding.people == ["儿子", "儿媳"]
    assert wedding.places == ["杭州"]
    assert wedding.source.startswith("human_data.md#")
    assert wedding.retrievable                     # 有 source 就进检索
    assert "讲到一半哭了" in wedding.body


def test_missing_year_is_a_warning_not_a_crash():
    pack = parse(SAMPLE, slug="我爸")
    assert any("没有年份的一件事" in w for w in pack.warnings)


def test_a_fenced_example_is_not_a_memory():
    text = SAMPLE + """
```
### 1999-01-01 这是示范，不该变成一张卡
```
"""
    pack = parse(text, slug="我爸")
    assert all("示范" not in m.title for m in pack.memories)


def test_empty_soul_is_a_clear_error(tmp_path: Path):
    (tmp_path / "human_data.md").write_text("## 基本\n名字：某人\n", encoding="utf-8")
    with pytest.raises(PackError, match="我是谁"):
        load_pack(tmp_path)


def test_folder_without_anything_says_what_is_missing(tmp_path: Path):
    with pytest.raises(PackError, match="human_data.md"):
        load_pack(tmp_path)


def test_the_blank_form_does_not_load_as_a_person():
    """`humans/_template/` 是空表单：它不该被当成一个人，也不该静默加载。"""
    template = Path(__file__).resolve().parent.parent / "humans" / "_template"
    assert (template / "human_data.md").is_file()

    names = paths.list_packs() if paths.humans_dir().is_dir() else []
    assert "_template" not in names

    with pytest.raises(PackError, match="我是谁"):
        load_pack(template)


def test_the_old_filename_says_rename_it(tmp_path: Path):
    """改名前填好的文件不能静默失效：得说清楚改成什么。"""
    (tmp_path / "人类数据.md").write_text(SAMPLE, encoding="utf-8")
    with pytest.raises(PackError, match="改名"):
        load_pack(tmp_path)


def test_old_style_pack_still_wins_when_both_exist(tmp_path: Path):
    (tmp_path / "human.yaml").write_text("slug: t\nname: 老形态\n", encoding="utf-8")
    (tmp_path / "SOUL.md").write_text("你叫老形态。", encoding="utf-8")
    (tmp_path / "RULES.md").write_text("说短句。", encoding="utf-8")
    (tmp_path / "human_data.md").write_text(SAMPLE, encoding="utf-8")

    pack = load_pack(tmp_path)
    assert pack.name == "老形态"
    assert any("传统文件" in w for w in pack.warnings)


def test_missing_presence_defaults_to_living():
    pack = parse("## 我是谁\n某人。\n", slug="x")
    assert pack.meta.presence == "living"
    assert pack.meta.name == "x"                   # 没写名字就用文件夹名
