"""OpenAI 兼容的流式客户端。

同时支持 llama-server（本地）和 DeepSeek（云端）：
- 本地特有参数（cache_prompt / chat_template_kwargs）只在 llama 后端发。
- thinking 一律关掉，并把模板塞进去的字面量 <think> 前缀剥掉。
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx

THINK_OPEN = "<think>"
THINK_CLOSE = "</think>"


class LLMError(Exception):
    """调模型失败，消息直接给用户看。"""


def _endpoint(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


class _ThinkFilter:
    """把开头的 <think>…</think> 吃掉，其余原样吐出。

    关闭 thinking 时模型仍会输出字面量 `<think>\n\n</think>\n\n`，
    打开时则是完整思考链。两种情况都要吃掉。
    """

    MAX_HOLD = 4000  # 思考链过长就不再等，直接放行

    def __init__(self) -> None:
        self.buf = ""
        self.done = False

    def feed(self, piece: str) -> str:
        if self.done:
            return piece
        self.buf += piece
        head = self.buf.lstrip()
        if not head:
            return ""

        if THINK_CLOSE in head:
            rest = head.split(THINK_CLOSE, 1)[1]
            self.done = True
            self.buf = ""
            return rest.lstrip("\n")

        if head.startswith(THINK_OPEN) or THINK_OPEN.startswith(head.rstrip("\n")):
            if len(head) > self.MAX_HOLD:
                self.done = True
                self.buf = ""
                return head
            return ""

        # 不是思考块，正常内容
        self.done = True
        self.buf = ""
        return head

    def flush(self) -> str:
        out, self.buf, self.done = self.buf, "", True
        return out


@dataclass
class Stats:
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    ttft_s: float | None = None
    extra: dict = field(default_factory=dict)


class LLMClient:
    """一个后端。构造后可以反复用。"""

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str = "",
        temperature: float = 0.75,
        top_p: float = 0.9,
        max_tokens: int = 400,
        local: bool = True,
        timeout: float = 300.0,
        disable_thinking: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.top_p = top_p
        self.max_tokens = max_tokens
        self.local = local
        self.timeout = timeout
        self.disable_thinking = disable_thinking
        self.stats = Stats(model=model)
        self.tool_calls: list[dict] = []
        self._tool_buf: dict[int, dict] = {}

    # ---------- 基础 ----------

    def _headers(self) -> dict[str, str]:
        head = {"Content-Type": "application/json"}
        if self.api_key:
            head["Authorization"] = f"Bearer {self.api_key}"
        return head

    def _payload(
        self,
        messages: list[dict],
        stream: bool,
        max_tokens: int | None,
        tools: list[dict] | None = None,
    ) -> dict:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": stream,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if self.local:
            # BUILD.md §11 N-01：前缀缓存，必须开
            body["cache_prompt"] = True
        if self.disable_thinking and self.local:
            # N-05：关掉思考链。云端靠选模型，不发这个字段。
            body["chat_template_kwargs"] = {"enable_thinking": False}
        return body

    def _absorb_tool_delta(self, delta: dict) -> None:
        """流式 tool_call 是按 index 分片来的，拼起来才是一整个。"""
        for part in delta.get("tool_calls") or []:
            index = part.get("index", 0)
            slot = self._tool_buf.setdefault(
                index, {"id": "", "name": "", "arguments": ""}
            )
            if part.get("id"):
                slot["id"] = part["id"]
            fn = part.get("function") or {}
            if fn.get("name"):
                slot["name"] += fn["name"]
            if fn.get("arguments"):
                slot["arguments"] += fn["arguments"]
            self.tool_calls = [
                {
                    "id": v["id"] or f"call_{i}",
                    "type": "function",
                    "function": {"name": v["name"], "arguments": v["arguments"] or "{}"},
                }
                for i, v in sorted(self._tool_buf.items())
                if v["name"]
            ]

    # ---------- 健康检查 ----------

    def health(self, timeout: float = 3.0) -> bool:
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.get(self.base_url + "/health")
                return r.status_code == 200
        except httpx.HTTPError:
            return False

    def props(self, timeout: float = 5.0) -> dict:
        try:
            with httpx.Client(timeout=timeout) as client:
                r = client.get(self.base_url + "/props")
                r.raise_for_status()
                return r.json()
        except (httpx.HTTPError, ValueError):
            return {}

    # ---------- 对话 ----------

    def stream(
        self,
        messages: list[dict],
        *,
        max_tokens: int | None = None,
        tools: list[dict] | None = None,
    ) -> Iterator[str]:
        """逐段吐字。结束后 self.stats / self.tool_calls 是这一轮的结果。"""
        self.stats = Stats(model=self.model)
        self.tool_calls = []
        self._tool_buf = {}
        body = self._payload(messages, stream=True, max_tokens=max_tokens, tools=tools)
        filt = _ThinkFilter()
        start = _now()

        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST", _endpoint(self.base_url), json=body, headers=self._headers()
                ) as resp:
                    if resp.status_code >= 400:
                        detail = resp.read().decode("utf-8", "replace")[:400]
                        raise LLMError(f"模型返回 {resp.status_code}: {detail}")
                    for line in resp.iter_lines():
                        if not line.startswith("data: "):
                            continue
                        raw = line[6:].strip()
                        if raw == "[DONE]":
                            break
                        try:
                            event = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        self._absorb(event, start)
                        for choice in event.get("choices") or []:
                            delta = choice.get("delta") or {}
                            self._absorb_tool_delta(delta)
                            piece = delta.get("content") or ""
                            if not piece:
                                continue
                            if self.stats.ttft_s is None:
                                self.stats.ttft_s = _now() - start
                            out = filt.feed(piece)
                            if out:
                                yield out
        except httpx.HTTPError as exc:
            raise LLMError(f"连不上模型（{self.base_url}）: {exc}") from exc

        tail = filt.flush()
        if tail:
            yield tail

    def complete(self, messages: list[dict], *, max_tokens: int | None = None) -> str:
        return "".join(self.stream(messages, max_tokens=max_tokens))

    # ---------- 内部 ----------

    def _absorb(self, event: dict, start: float) -> None:
        usage = event.get("usage") or {}
        if usage:
            self.stats.prompt_tokens = usage.get("prompt_tokens", self.stats.prompt_tokens)
            self.stats.completion_tokens = usage.get(
                "completion_tokens", self.stats.completion_tokens
            )
            details = usage.get("prompt_tokens_details") or {}
            self.stats.cached_tokens = details.get("cached_tokens", self.stats.cached_tokens)
        timings = event.get("timings") or {}
        if timings:
            self.stats.prompt_tokens = timings.get("prompt_n", self.stats.prompt_tokens)
            self.stats.completion_tokens = timings.get("predicted_n", self.stats.completion_tokens)
            self.stats.cached_tokens = timings.get("cache_n", self.stats.cached_tokens)
            self.stats.extra["prefill_tps"] = round(timings.get("prompt_per_second", 0), 1)
            self.stats.extra["decode_tps"] = round(timings.get("predicted_per_second", 0), 1)


def _now() -> float:
    import time

    return time.perf_counter()
