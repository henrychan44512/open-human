"""会话记录：一行一个事件，id + parentId 组成树。

存的是**用户原话**，不含注入的记忆块 —— 这样历史部分每轮都不变，
prefix cache 才能一直命中（BUILD.md §11 N-01）。
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from .. import paths, tokens


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


@dataclass
class Event:
    id: str
    parent_id: str | None
    role: str
    ts: str
    content: str
    model: str = ""
    citations: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        raw = asdict(self)
        raw["parentId"] = raw.pop("parent_id")
        return raw

    @classmethod
    def from_json(cls, raw: dict) -> Event:
        return cls(
            id=raw["id"],
            parent_id=raw.get("parentId"),
            role=raw["role"],
            ts=raw.get("ts", ""),
            content=raw.get("content", ""),
            model=raw.get("model", ""),
            citations=raw.get("citations") or [],
            usage=raw.get("usage") or {},
        )

    @property
    def is_dialogue(self) -> bool:
        return self.role in ("user", "assistant")


class Session:
    """一个 JSONL 文件。也支持不落盘的临时会话（path=None）。"""

    def __init__(self, slug: str, path: Path | None = None) -> None:
        self.slug = slug
        self.path = path
        self.events: list[Event] = []
        self._counter = 0

    # ---------- 构造 ----------

    @classmethod
    def create(cls, slug: str) -> Session:
        session = cls(slug, paths.new_session_path(slug))
        session.path.touch()
        return session

    @classmethod
    def resume(cls, slug: str) -> Session:
        """接着最近一次会话。

        关掉再打开要还能记得昨天 —— 不然「他会记得」这句话就是假的。
        没有旧会话就开新的。
        """
        path = paths.latest_session(slug)
        if path is None:
            return cls.create(slug)
        try:
            return cls.load(path)
        except (OSError, ValueError, KeyError):
            return cls.create(slug)  # 文件坏了，别让他起不来

    @classmethod
    def load(cls, path: Path) -> Session:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
        events = [Event.from_json(json.loads(line)) for line in raw_lines if line.strip()]
        slug = path.parent.name
        session = cls(slug, path)
        session.events = events
        session._counter = len(events)
        return session

    # ---------- 写 ----------

    def append(
        self,
        role: str,
        content: str,
        *,
        model: str = "",
        citations: list[str] | None = None,
        usage: dict | None = None,
        parent_id: str | None | object = ...,
    ) -> Event:
        self._counter += 1
        parent = self.head_id if parent_id is ... else parent_id
        event = Event(
            id=f"e{self._counter:04d}",
            parent_id=parent,
            role=role,
            ts=_now(),
            content=content,
            model=model,
            citations=list(citations or []),
            usage=dict(usage or {}),
        )
        self.events.append(event)
        self._persist(event)
        return event

    def _persist(self, event: Event) -> None:
        if self.path is None:
            return
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_json(), ensure_ascii=False) + "\n")

    # ---------- 读 ----------

    @property
    def head_id(self) -> str | None:
        return self.events[-1].id if self.events else None

    def dialogue(self) -> list[Event]:
        return [e for e in self.events if e.is_dialogue]

    def history(self, max_tokens: int = 900) -> list[dict]:
        """最近若干轮，按 token 预算从尾部往前取，返回时间正序。"""
        picked: list[dict] = []
        used = 0
        for event in reversed(self.dialogue()):
            cost = tokens.estimate(event.content)
            if picked and used + cost > max_tokens:
                break
            used += cost
            picked.append({"role": event.role, "content": event.content})
        picked.reverse()
        return picked

    def replay(self) -> str:
        lines: list[str] = []
        for event in self.events:
            stamp = event.ts[11:16] if len(event.ts) > 16 else event.ts
            who = {"user": "你", "assistant": event.model or "他"}.get(event.role, event.role)
            lines.append(f"[{stamp}] {who}: {event.content}")
            if event.citations:
                lines.append(f"         参考: {', '.join(event.citations)}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return len(self.events)
