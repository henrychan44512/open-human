"""评测：检索命中 + 回答里的日期/人名是否都在引用卡里。

`oh eval` 默认只跑检索（快，几秒），加 `--answers` 才会真的让模型答一遍（慢）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .memory import MemoryIndex, plan
from .pack import Pack
from .pack.schema import MemoryCard

DEFAULT_CASES = Path("tests/eval/questions.yaml")

_DATE = re.compile(
    r"(?:19|20)\d{2}\s*年(?:\s*\d{1,2}\s*月)?(?:\s*\d{1,2}\s*[日号])?"
)
_BARE_YEAR = re.compile(r"(?:19|20)\d{2}")


def _parse_date(token: str) -> tuple[int, int | None, int | None]:
    """「2010年5月2日」「2010-05-02」「2019年」都能吃。"""
    nums = [int(n) for n in re.findall(r"\d+", token)]
    year = nums[0]
    month = nums[1] if len(nums) > 1 else None
    day = nums[2] if len(nums) > 2 else None
    return year, month, day


def extract_facts(text: str) -> tuple[list[str], list[str]]:
    """从回答里抠出日期和年份。"""
    dates = [d.group(0).replace(" ", "") for d in _DATE.finditer(text)]
    years = [y for y in _BARE_YEAR.findall(text) if not any(y in d for d in dates)]
    return dates, years


def card_text(cards: list[MemoryCard]) -> str:
    return "\n".join(c.render() for c in cards)


def _matches_any_date(token: str, cards: list[MemoryCard]) -> bool:
    year, month, day = _parse_date(token)
    haystack = card_text(cards)
    for card in cards:
        d = card.date
        if d.year != year:
            continue
        if month is None:
            return True
        if d.month == month and (day is None or d.day == day):
            return True
    # 正文里也写了这个日期（形式可能不同）
    compact = f"{year}年{month}月{day}日" if month and day else ""
    return bool(compact and compact in haystack)


def check_answer(reply: str, cards: list[MemoryCard]) -> list[str]:
    """回答里的日期/年份必须能对上引用卡。返回对不上的那些。"""
    if not reply.strip():
        return []
    dates, years = extract_facts(reply)
    haystack = card_text(cards)
    bad: list[str] = [d for d in dates if not _matches_any_date(d, cards)]
    for year in years:
        if year in haystack or any(c.date.year == int(year) for c in cards):
            continue
        bad.append(year)
    return bad


@dataclass
class Case:
    id: str
    q: str
    kind: str = "memory"
    expect: list[str] = field(default_factory=list)
    # 已知做不到的题：照旧统计，但界面上不画成红叉，免得把红叉训练成背景
    known: bool = False


@dataclass
class Row:
    case: Case
    top: list[str]
    ok: bool
    note: str = ""


def load_cases(path: Path | None = None) -> list[Case]:
    target = path or DEFAULT_CASES
    raw = yaml.safe_load(target.read_text(encoding="utf-8")) or []
    return [Case(**item) for item in raw]


def run_retrieval(index: MemoryIndex, pack: Pack, cases: list[Case], k: int = 5) -> list[Row]:
    rows: list[Row] = []
    for case in cases:
        hits = index.search(plan(case.q, pack), k=k)
        ids = [h.card.id for h in hits]
        if case.kind == "out_of_scope":
            ok = not ids
            note = "" if ok else "不该有命中"
        else:
            ok = bool(set(ids) & set(case.expect))
            note = "" if ok else f"期望 {case.expect}"
        rows.append(Row(case=case, top=ids, ok=ok, note=note))
    return rows


def summarize(rows: list[Row]) -> dict[str, float | int]:
    memory = [r for r in rows if r.case.kind == "memory"]
    scope = [r for r in rows if r.case.kind == "out_of_scope"]
    hit = sum(1 for r in memory if r.ok)
    top1 = sum(1 for r in memory if r.top and r.top[0] in r.case.expect)
    quiet = sum(1 for r in scope if r.ok)
    return {
        "total": len(rows),
        "memory": len(memory),
        "hit": hit,
        "hit_rate": hit / len(memory) if memory else 0.0,
        "top1": top1,
        "top1_rate": top1 / len(memory) if memory else 0.0,
        "scope": len(scope),
        "quiet": quiet,
        "quiet_rate": quiet / len(scope) if scope else 0.0,
    }
