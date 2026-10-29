"""把检索到的卡裁进预算。

BUILD.md §11 N-03：记忆块 ≤ 400 tok，放在历史之后、问题之前。
每轮都要重算这一段，所以它的大小直接等于用户的等待时间。
"""

from __future__ import annotations

from .. import tokens
from ..pack.schema import MemoryCard
from .index import Hit

MEMORY_BUDGET = 400


def _card_tokens(card: MemoryCard) -> int:
    return tokens.estimate(card.render())


def trim(card: MemoryCard, limit: int) -> MemoryCard:
    """正文太长就把正文砍掉，标题保留。"""
    head = tokens.estimate(f"[mem: {card.id}] {card.date.isoformat()}　{card.title}。")
    room = max(0, limit - head)
    if room <= 0 or _card_tokens(card) <= limit:
        return card
    # 0.7 tok/汉字 → 大约留 room/0.7 个字
    keep = max(0, int(room / tokens.CJK_PER_TOKEN) - 1)
    body = card.body.strip().replace("\n", " ")
    if len(body) > keep:
        body = body[:keep].rstrip("，。、；") + "…"
    return card.model_copy(update={"body": body})


def fit(hits: list[Hit], budget: int = MEMORY_BUDGET) -> list[MemoryCard]:
    """按分数顺序装卡，装不下就裁剪最后一张。"""
    out: list[MemoryCard] = []
    used = 0
    for hit in hits:
        cost = _card_tokens(hit.card)
        if used + cost <= budget:
            out.append(hit.card)
            used += cost
            continue
        room = budget - used
        if room > 80:  # 小于这个数就别硬塞了
            trimmed = trim(hit.card, room)
            out.append(trimmed)
        break
    return out


def citations(cards: list[MemoryCard]) -> list[str]:
    return [c.id for c in cards]
