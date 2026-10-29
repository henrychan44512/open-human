"""Director：从一句话里看出该去哪儿找。

第一版不用 LLM（BUILD.md §9）：正则抽年份、对照人名表、剩下的交给 BM25。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..pack import Pack
from .text import content_terms, strip_weak

_YEAR = re.compile(r"(?:19|20)\d{2}")

# 「这句话是在问他自己的事」—— 有问句的样子，或者直接让他讲。
# 第四轮之前这里只排除几句固定的寒暄，结果「今天有点累」被当成问往事，
# 他张口就是「嗯……记得。2019 年 10 月 26 号，和秀兰去黄山」。
_ASK = re.compile(
    r"[？?]|吗|呢|什么|怎么|怎样|干嘛|干吗|哪|谁|多少|多久|多大|几岁|几点|几号|几时"
    r"|星期几|周几|是不是|有没有|讲讲|说说|聊聊|谈谈|告诉我"
)

# 没问号，但明显在提往事（「台风那年」「你以前教什么」）。
_PAST = re.compile(
    r"记得|想起|那年|那次|那回|那天|那时|那会儿|那时候|当时|当年"
    r"|以前|从前|小时候|后来|过去|那年头|年轻的时候|年轻时"
)

# 指向某一件具体的事（而不是「以前」这种笼统的时段）。
# 只有具体的事才谈得上「检索不到就别编」：「你以前教什么课」的答案
# 在人格包里，提醒他「想不起来」等于把他自己会的东西也堵死。
_EVENT = re.compile(r"记得|想起|那年|那次|那回|那天|那时|那会儿|那时候|当时|后来")

# 追问的开头：「那天你讲话了吗」「后来呢」。
# 这种话本身没有新信息，指的就是上一轮在说的那件事。
_FOLLOW_UP = re.compile(r"^(那天|那次|那回|那时候|那会儿|当时|后来|然后|接着|还有呢)")


@dataclass
class QueryPlan:
    query: str
    years: list[int] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    tokens: set[str] = field(default_factory=set)
    ask: bool = True  # 要不要检索
    cue: bool = False  # 有没有明确的往事指向
    event: bool = False  # 指向的是不是某一件具体的事

    @property
    def about_past(self) -> bool:
        """在问他自己的某件往事吗。

        检索空了、要不要提醒「别编」看的是这个，不是 `ask`：
        问天气、问钟点也是问句，但那些他本来就不该记得；
        「以前教什么课」是笼统的一段，答案在人格包里。
        """
        return self.event or bool(self.years) or bool(self.people)

    def summary(self) -> str:
        bits = []
        if self.years:
            bits.append("年份 " + "/".join(str(y) for y in self.years))
        if self.people:
            bits.append("人物 " + "/".join(self.people))
        if self.tokens:
            bits.append("词 " + " ".join(sorted(self.tokens)))
        return " · ".join(bits) or "（无信号）"


def extract_years(text: str) -> list[int]:
    seen: list[int] = []
    for raw in _YEAR.findall(text):
        year = int(raw)
        if year not in seen:
            seen.append(year)
    return seen


def extract_people(text: str, known: list[str]) -> list[str]:
    """长的名字优先匹配，避免「陈」吃掉「陈建国」。"""
    hits: list[str] = []
    for name in sorted(set(known), key=len, reverse=True):
        if name and name in text and not any(name in h for h in hits):
            hits.append(name)
    return hits


def follows_up(text: str, pack: Pack) -> bool:
    """这句是不是在接着说上一轮的事。

    两个条件：
    - 短，而且是从「那天／后来／然后」起头的。长了就是自己带了主语。
    - 句子里没有年份、人名、地名 —— 有的话它自己能检索到东西
      （「那次去黄山怎么走的」不该被拽回婚礼那张卡）。
    """
    bare = text.strip()
    if len(bare) > 12 or not _FOLLOW_UP.match(bare):
        return False
    if extract_years(bare) or extract_people(bare, pack.person_names()):
        return False
    places = {place for card in pack.memories for place in card.places if place}
    return not any(place in bare for place in places)


def plan(query: str, pack: Pack) -> QueryPlan:
    text = query.strip()
    if not text:
        return QueryPlan(query=query, ask=False)

    cue = bool(_PAST.search(text))
    wants = cue or bool(_ASK.search(text))
    tokens = content_terms(text) if wants else set()

    return QueryPlan(
        query=query,
        years=extract_years(text),
        people=extract_people(strip_weak(text), pack.person_names()),
        tokens=tokens,
        ask=wants and bool(tokens),
        cue=cue,
        event=bool(_EVENT.search(text)),
    )
