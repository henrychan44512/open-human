"""BM25 检索。文件本身是数据库，没有向量、没有 SQL（BUILD.md D-12）。

打分 = BM25 + 年份/人物加权，最后用「问句内容词覆盖率」当闸门。
闸门是为了让资料外的问题检索不到东西，而不是硬塞三张不相关的卡。
"""

from __future__ import annotations

from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from ..pack import Pack
from ..pack.schema import MemoryCard
from .director import QueryPlan
from .text import index_tokens

# 低于这个覆盖率就认为「没有相关的」，不注入
MIN_COVERAGE = 0.34
# 单卡命中率也要够
MIN_CARD_COVERAGE = 0.3
# 分数不到第一名的这个比例，就不算同一档
RELATIVE_MARGIN = 0.4

YEAR_BOOST = 4.0
PERSON_BOOST = 2.0
TITLE_BOOST = 1.5


@dataclass
class Hit:
    card: MemoryCard
    score: float
    coverage: float


def _document(card: MemoryCard) -> str:
    """索引用的文本。标题、标签、人名权重更高。"""
    parts = [
        card.title,
        card.title,
        str(card.date.year),
        card.date.isoformat(),
        " ".join(card.people),
        " ".join(card.people),
        " ".join(card.tags),
        " ".join(card.tags),
        " ".join(card.places),
        card.body,
    ]
    return "\n".join(p for p in parts if p.strip())


def mentions_person(card: MemoryCard, people: list[str]) -> bool:
    if not people:
        return False
    hay = f"{card.title} {card.body} {' '.join(card.people)}"
    return any(name in hay for name in people)


class MemoryIndex:
    def __init__(self, pack: Pack) -> None:
        self.pack = pack
        self.cards: list[MemoryCard] = pack.working_memories()
        self.docs: list[list[str]] = [index_tokens(_document(c)) for c in self.cards]
        self.doc_sets: list[set[str]] = [set(d) for d in self.docs]
        self.title_sets: list[set[str]] = [set(index_tokens(c.title)) for c in self.cards]
        self.vocab: set[str] = set().union(*self.doc_sets) if self.doc_sets else set()
        self._bm25 = BM25Okapi(self.docs) if any(self.docs) else None

    def __len__(self) -> int:
        return len(self.cards)

    # ---------- 打分 ----------

    def _raw_scores(self, tokens: list[str]) -> list[float]:
        if self._bm25 is None:
            return [0.0] * len(self.cards)
        return [float(x) for x in self._bm25.get_scores(tokens)]

    def _matches(self, card: MemoryCard, plan: QueryPlan) -> tuple[bool, bool]:
        year_hit = bool(plan.years) and card.date.year in plan.years
        return year_hit, mentions_person(card, plan.people)

    def search(self, plan: QueryPlan, k: int = 3) -> list[Hit]:
        if not plan.ask or not self.cards or not plan.tokens:
            return []

        # 只用「语料里确实出现过」的词来算覆盖率：
        # 问句里那些语料完全没有的词，谁都匹配不上，算进分母只会误伤。
        qterms = plan.tokens & self.vocab
        if not qterms:
            return []

        tokens = sorted(qterms)
        raw = self._raw_scores(tokens)

        scored: list[Hit] = []
        for card, base, doc_set, title_set in zip(
            self.cards, raw, self.doc_sets, self.title_sets
        ):
            coverage = len(qterms & doc_set) / len(qterms)
            year_hit, person_hit = self._matches(card, plan)
            score = base
            if year_hit:
                score += YEAR_BOOST
            if person_hit:
                score += PERSON_BOOST
            if qterms & title_set:
                score += TITLE_BOOST
            scored.append(Hit(card=card, score=score, coverage=coverage))

        # 提到年份、且确实有那年的卡，就只看那一年
        if plan.years:
            narrowed = [h for h in scored if h.card.date.year in plan.years]
            if narrowed:
                scored = narrowed

        scored.sort(key=lambda h: (h.score, h.coverage), reverse=True)

        top = [h for h in scored if h.coverage >= MIN_CARD_COVERAGE]
        if not top or top[0].coverage < MIN_COVERAGE:
            return []

        # 问到了具体某个人，却没有任何一张卡真的提到他：
        # 那就是记不得。拿一张不相干的卡顶上比空手更糟。
        if plan.people:
            named = [h for h in top if mentions_person(h.card, plan.people)]
            if not named:
                return []
            top = named

        floor = top[0].score * RELATIVE_MARGIN
        return [h for h in top if h.score >= floor][:k]


def build(pack: Pack) -> MemoryIndex:
    return MemoryIndex(pack)
