"""人格包的数据模型。runtime 只读，不改人格文件。"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class Presence(StrEnum):
    living = "living"      # 仍在，日常对话
    archived = "archived"  # 意识已备份，停止新增记录
    unknown = "unknown"


class HumanMeta(BaseModel):
    """human.yaml。最小字段就是 BUILD.md §6 那一份。"""

    slug: str
    name: str
    presence: Presence = Presence.living
    last_record: date | None = None
    language: str = "zh-CN"
    first_line: str = "……你来了。"
    sleep_line: str = "那我等你。"
    wake_line: str = "你回来了。"
    # 你很久没出声，他先出个声。空着就不说 —— 不催人也是一个人的脾气。
    idle_line: str = ""
    aliases: list[str] = Field(default_factory=list)


class MemoryCard(BaseModel):
    """memories/**/*.md 的 front-matter + 正文。"""

    id: str
    date: date
    title: str
    source: str = ""
    salience: int = Field(default=3, ge=0, le=5)
    type: str = "episode"
    people: list[str] = Field(default_factory=list)
    places: list[str] = Field(default_factory=list)
    emotion: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    body: str = ""
    path: Path | None = None

    @field_validator("type", "confidence", mode="before")
    @classmethod
    def _lower(cls, v: object) -> object:
        return v.strip().lower() if isinstance(v, str) else v

    @property
    def retrievable(self) -> bool:
        """缺 source 的卡不进检索（BUILD.md §6）。"""
        return bool(self.source.strip())

    def render(self) -> str:
        """注入 prompt 时的紧凑形式。"""
        bits = [f"[mem: {self.id}] {self.date.isoformat()}　{self.title}。"]
        if self.body.strip():
            bits.append(self.body.strip().replace("\n", " "))
        return " ".join(bits)


class Person(BaseModel):
    """people/*.md。"""

    slug: str = ""
    name: str
    relation: str = ""
    aliases: list[str] = Field(default_factory=list)
    body: str = ""
    path: Path | None = None


class Pack(BaseModel):
    """一个 humans/<slug>/ 文件夹加载后的全部内容。"""

    meta: HumanMeta
    soul: str
    rules: str
    speech: str = ""
    samples: str = ""
    timeline: str = ""
    people: list[Person] = Field(default_factory=list)
    memories: list[MemoryCard] = Field(default_factory=list)
    root: Path | None = None
    warnings: list[str] = Field(default_factory=list)

    @property
    def name(self) -> str:
        return self.meta.name

    def working_memories(self) -> list[MemoryCard]:
        return [m for m in self.memories if m.retrievable]

    def person_names(self) -> list[str]:
        """检索时用来认人的名字 + 别名，再加上记忆卡里出现过的称呼。

        有些人只在某一两张卡里出现（比如儿媳），没有 people/*.md。
        认不出来就会答错一张卡 —— 问「王倩第一次来家里」，他翻出一张
        「第一次上讲台」照着念，比说记不清糟糕得多。
        """
        out: list[str] = []
        for p in self.people:
            out.append(p.name)
            out.extend(p.aliases)
        for card in self.memories:
            out.extend(card.people)
        return [n for n in dict.fromkeys(out) if n]
