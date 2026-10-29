"""中文分词与检索词。

检索只需要「能对上号」，不需要语言学精度。

用两套词：
- jieba 词：语义单位，命中就很有说服力。
- 汉字二元组：补 jieba 切分和原文切分不一致的情况
  （问句说「手在抖」，卡里写「手在抖」，但 jieba 可能切成「手」「在」「抖」）。
"""

from __future__ import annotations

import logging
import re

import jieba

from .. import paths

# jieba 默认往 stderr 打 "Building prefix dict..."，命令行里看着像报错
jieba.setLogLevel(logging.WARNING)

# 别把 jieba.cache 丢到仓库根
_cache = paths.data_dir() / "jieba"
_cache.mkdir(parents=True, exist_ok=True)
jieba.dt.tmp_dir = str(_cache)

_PUNCT = re.compile(r"[\s，。！？、；：,.!?;:\"'“”‘’（）()【】\[\]《》<>—…·~`|/\\]+")
_CJK_RUN = re.compile(r"[\u4e00-\u9fff]+")

# 这些词在几乎每个问句里都出现，留着只会稀释分数
STOPWORDS: frozenset[str] = frozenset(
    """的 了 是 在 有 和 与 就 都 也 还 又 很 太 更 最 不 没 别 要 会 能 可以 说 讲 告诉
    我 你 他 她 它 我们 你们 他们 自己 人家 别人
    这 那 这个 那个 这里 那里 这样 那样 这么 那么
    什么 怎么 怎么样 为什么 哪 哪个 哪些 多少 几
    吗 呢 吧 啊 呀 哦 嗯 唉 哈 嘛 咯 着 过 地 得
    一个 一下 一些 一点 一起 一直 一样 一边 一定
    现在 今天 昨天 明天 时候 当时 那天 以前 从前 那年 那次 那回
    那时 那会儿 那时候 后来 过去 当年 那年头
    记得 想起 想到 知道 觉得 认为 应该
    老人 事情 东西 问题 感觉
    """.split()
)

# 问句里常见的、但不带信息量的开头
WEAK_PREFIXES = ("你还记得", "你记得", "还记得", "你知道", "你知不知道")

# 二元组里出现这些，多半是跨词噪音
JUNK_BIGRAMS = frozenset(
    """你还 还记 你记 得儿 的哪 了哪 是你 是我 是你 了吗 的时 什么 么样""".split()
)


def strip_weak(text: str) -> str:
    for prefix in WEAK_PREFIXES:
        if text.startswith(prefix):
            return text[len(prefix) :]
    return text


def tokenize(text: str) -> list[str]:
    """jieba 分词，去掉标点和停用词。数字保留。"""
    if not text:
        return []
    cleaned = _PUNCT.sub(" ", text)
    out: list[str] = []
    for word in jieba.lcut(cleaned, cut_all=False):
        word = word.strip()
        if not word or word in STOPWORDS or word in JUNK_BIGRAMS:
            continue
        if len(word) == 1 and not word.isdigit():
            continue
        out.append(word)
    return out


def bigrams(text: str) -> list[str]:
    """连续汉字的二元组，去掉停用词和跨词噪音。"""
    out: list[str] = []
    for run in _CJK_RUN.findall(text):
        for i in range(len(run) - 1):
            pair = run[i : i + 2]
            if pair in STOPWORDS or pair in JUNK_BIGRAMS:
                continue
            out.append(pair)
    return out


def index_tokens(text: str) -> list[str]:
    """建索引用：词 + 二元组。"""
    return tokenize(text) + bigrams(text)


def query_tokens(text: str) -> list[str]:
    """查询用：先剥掉「你还记得」这类开头。"""
    body = strip_weak(text)
    return index_tokens(body)


def content_terms(text: str) -> set[str]:
    return set(query_tokens(text))
