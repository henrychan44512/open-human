"""LLM 客户端：SSE 解析、think 剥离、请求参数。"""

from __future__ import annotations

import pytest

from fake_llm import FakeServer
from openhuman.llm import LLMClient, LLMError


def _client(url: str, **kw) -> LLMClient:
    return LLMClient(url, "fake-model", local=True, **kw)


def test_stream_yields_reply():
    with FakeServer("嗯，我记得。") as srv:
        got = _client(srv.base_url).complete([{"role": "user", "content": "hi"}])
    assert got == "嗯，我记得。"


def test_thinking_prefix_is_stripped():
    with FakeServer("嗯。", prefix="<think>\n\n</think>\n\n") as srv:
        client = _client(srv.base_url)
        got = client.complete([{"role": "user", "content": "hi"}])
    assert got == "嗯。"
    assert not got.startswith("<think>")


def test_thinking_block_is_stripped():
    with FakeServer("记得。", prefix="<think>\n想一想他在问什么。\n</think>\n\n") as srv:
        got = _client(srv.base_url).complete([{"role": "user", "content": "hi"}])
    assert got == "记得。"


def test_stats_are_filled():
    with FakeServer("你好。", usage={"prompt_tokens": 30, "completion_tokens": 4}) as srv:
        client = _client(srv.base_url)
        client.complete([{"role": "user", "content": "hi"}])
    assert client.stats.prompt_tokens == 30
    assert client.stats.completion_tokens == 4
    assert client.stats.ttft_s is not None


def test_local_request_carries_cache_and_thinking_flags():
    with FakeServer() as srv:
        _client(srv.base_url).complete([{"role": "user", "content": "hi"}])
        body = srv.requests[-1]
    assert body["cache_prompt"] is True
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["stream"] is True


def test_remote_request_stays_plain():
    with FakeServer() as srv:
        LLMClient(srv.base_url, "deepseek-chat", local=False).complete(
            [{"role": "user", "content": "hi"}]
        )
        body = srv.requests[-1]
    assert "cache_prompt" not in body
    assert "chat_template_kwargs" not in body


def test_health_and_props():
    with FakeServer() as srv:
        client = _client(srv.base_url)
    assert client.health() is False  # 服务已经关了


def test_health_while_running():
    with FakeServer() as srv:
        assert _client(srv.base_url).health() is True


def test_unreachable_server_raises():
    client = LLMClient("http://127.0.0.1:1", "x", timeout=1.0)
    with pytest.raises(LLMError, match="连不上模型"):
        client.complete([{"role": "user", "content": "hi"}])
