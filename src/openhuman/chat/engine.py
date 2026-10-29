"""一轮对话。

顺序（BUILD.md §11）：
    warmup → Director → 检索 → 预算裁剪 → 组装 → 流式 → 落盘

记忆块放在历史之后、问题之前（N-03），这是缓存和延迟的共同要求。
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from ..llm import LLMClient, build_messages, clock_line, warmup_messages
from ..llm.client import Stats
from ..memory import MemoryIndex, QueryPlan, citations, fit, follows_up, plan
from ..pack import Pack, compile_persona
from ..pack.schema import MemoryCard
from ..tools import Tools
from .session import Session

HISTORY_BUDGET = 900
MAX_TOOL_ROUNDS = 4

TOOL_HINT = """
## 工具
你能调用工具去读写 workspace 里的文件。
要动文件就直接调工具，不要在回话里假装已经记下了。
write_file 会把原文件整个冲掉；只是加一句话，用 append_file。
"""


def _parse_args(raw: str | None) -> dict[str, Any]:
    """模型给的 arguments 是字符串，尽量解析；解析不了就当空参数。"""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


@dataclass
class Turn:
    user_text: str = ""
    reply: str = ""
    cards: list[MemoryCard] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    plan: QueryPlan | None = None
    stats: Stats = field(default_factory=Stats)
    tools: list[dict] = field(default_factory=list)


class Engine:
    def __init__(
        self,
        pack: Pack,
        client: LLMClient,
        session: Session,
        *,
        history_budget: int = HISTORY_BUDGET,
        index: MemoryIndex | None = None,
        tools: Tools | None = None,
        on_event: Callable[[dict], None] | None = None,
    ) -> None:
        self.pack = pack
        self.client = client
        self.session = session
        self.history_budget = history_budget
        self.index = index
        self.tools = tools
        self.on_event = on_event
        self.persona = compile_persona(pack)
        self.last: Turn | None = None

    # ---------- 开机预热 ----------

    def warmup(self) -> float:
        """把 persona 前缀灌进 llama.cpp 缓存，返回耗时秒数。

        没有这一步，每次打开 app 的第一句话要多等约 8 秒。
        """
        import time

        start = time.perf_counter()
        self.client.complete(warmup_messages(self.persona), max_tokens=1)
        return time.perf_counter() - start

    # ---------- 检索 ----------

    def prepare(self, text: str) -> tuple[list[MemoryCard], QueryPlan]:
        """这一轮该把哪几张卡放到他脑子里。

        追问（「那天你讲话了吗」）接着上一轮那件事，不重新检索：
        那种句子里没有主语，BM25 只会乱猜。
        """
        p = plan(text, self.pack)
        if self.index is None:
            return [], p

        cards = fit(self.index.search(p))
        if follows_up(text, self.pack) and not p.years and not p.people:
            topic = self._topic_card()
            if topic is not None:
                cards = [topic]
        return cards, p

    def _topic_card(self) -> MemoryCard | None:
        """上一轮说的是哪件事。

        「那天你讲话了吗」这种追问里没有主语，BM25 只能乱猜（问婚礼人数会
        翻到父亲那张卡，答成「来了两个人」）。人接着上一句说的时候，
        用的是刚才那件事，不是重新检索一遍。
        """
        for event in reversed(self.session.events):
            if event.role != "assistant":
                continue
            cid = str(event.usage.get("top") or (event.citations[0] if event.citations else ""))
            for card in self.pack.memories:
                if card.id == cid:
                    return card
            return None
        return None

    # ---------- 一轮 ----------

    def respond(
        self,
        user_text: str,
        cards: list[MemoryCard] | None = None,
    ) -> Iterator[str]:
        turn = Turn(user_text=user_text)
        self.last = turn

        if cards is None:
            cards, turn.plan = self.prepare(user_text)
        else:
            turn.plan = plan(user_text, self.pack)
        turn.cards = cards
        turn.citations = citations(cards)

        messages = build_messages(
            persona=self.persona_for_tools(),
            history=self.session.history(self.history_budget),
            user_text=user_text,
            cards=cards,
            # 真的在问往事、又什么都没检索到 —— 提醒他别编。
            # 问天气、问钟点不算：那些他本来就不该记得，硬提醒会说成「想不起来」。
            # 也没东西可检索的时候不算（「你以前教什么课」答案在人格包里，不在记忆卡里）。
            missed=(
                not cards
                and turn.plan is not None
                and turn.plan.ask
                and turn.plan.about_past
            ),
            clock=clock_line(),
        )
        self.session.append("user", user_text)

        schemas = self.tools.schemas() if self.tools else None
        pieces: list[str] = []
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                for chunk in self.client.stream(messages, tools=schemas):
                    pieces.append(chunk)
                    yield chunk

                calls = self.client.tool_calls
                if not calls or not self.tools:
                    break

                messages.append(
                    {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": calls,
                    }
                )
                for call in calls:
                    name = call["function"]["name"]
                    args = _parse_args(call["function"].get("arguments"))
                    result = self.tools.execute(name, args)
                    turn.tools.append(
                        {
                            "name": name,
                            "args": args,
                            "ok": result.ok,
                            "output": result.output[:400],
                        }
                    )
                    self._emit(
                        {
                            "type": "tool",
                            "name": name,
                            "args": args,
                            "ok": result.ok,
                            "output": result.output[:200],
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": result.as_content(),
                        }
                    )
                # 给外面一个机会把前面的工具事件送出去
                yield ""
        finally:
            turn.reply = "".join(pieces)
            turn.stats = self.client.stats
            if turn.reply.strip():
                self.session.append(
                    "assistant",
                    turn.reply.strip(),
                    model=self.client.model,
                    citations=turn.citations,
                    usage={
                        "prompt_tokens": turn.stats.prompt_tokens,
                        "completion_tokens": turn.stats.completion_tokens,
                        "cached_tokens": turn.stats.cached_tokens,
                        "tools": len(turn.tools),
                        # 这一轮说的是哪件事。下一句追问（「那天……后来呢」）
                        # 靠它接上，不用回头重检索。
                        "top": turn.cards[0].id if turn.cards else "",
                    },
                )

    def _emit(self, event: dict) -> None:
        if self.on_event:
            self.on_event(event)

    def persona_for_tools(self) -> str:
        """开工具时 persona 后面挂一小段说明；不开就一个字不加。"""
        return f"{self.persona}\n{TOOL_HINT}" if self.tools else self.persona

    # ---------- 展示 ----------

    def greeting(self) -> str:
        return self.pack.meta.first_line
