"""token 估算。

有 llama-server 就用它的 /tokenize 精确算；没有就按启发式估。
实测这个 tokenizer ≈ 0.65 token / 汉字（常用词会合并），
这里取 0.7 偏保守，宁可高估也不让 prompt 撑爆。
"""

from __future__ import annotations

import re

import httpx

_CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")

CJK_PER_TOKEN = 0.7
OTHER_CHARS_PER_TOKEN = 3.5


def estimate(text: str) -> int:
    if not text:
        return 0
    cjk = len(_CJK.findall(text))
    other = len(text) - cjk
    return int(cjk * CJK_PER_TOKEN + other / OTHER_CHARS_PER_TOKEN) + 1


def exact(text: str, base_url: str, timeout: float = 5.0) -> int | None:
    """调用 /tokenize。失败返回 None，调用方自己降级。"""
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(base_url.rstrip("/") + "/tokenize", json={"content": text})
            r.raise_for_status()
            return len(r.json()["tokens"])
    except (httpx.HTTPError, KeyError, ValueError):
        return None


def count(text: str, base_url: str | None = None) -> tuple[int, bool]:
    """返回 (tokens, 是否精确)。"""
    if base_url:
        got = exact(text, base_url)
        if got is not None:
            return got, True
    return estimate(text), False
