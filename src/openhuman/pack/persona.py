"""把人格包编译成 system prompt。

规则：
- 完全由人格包决定，同样的包永远编译出同样的字符串（这样 prefix cache 才有用）。
- 不加时间戳、不加随机内容、不加运行时状态。
- 顺序固定：你是谁 → 怎么说话 → 边界。

`voice/samples.md`（他以前说过的原话）试过塞进这里，第三轮测下来不行：
2B 会在没话说的时候直接照抄其中一句。结论记在 BUILD.md §27.7（归档）。
"""

from __future__ import annotations

from .. import tokens
from .schema import Pack

SOUL_HEADER = "## 你是谁"
SPEECH_HEADER = "## 你说话的口气"
RULES_HEADER = "## 边界"

# BUILD.md §11 修订后的预算
PERSONA_BUDGET = 700


def compile_persona(pack: Pack) -> str:
    parts = [f"你是{pack.name}。", "", SOUL_HEADER, pack.soul.strip()]

    if pack.speech.strip():
        parts += ["", SPEECH_HEADER, pack.speech.strip()]

    if pack.rules.strip():
        parts += ["", RULES_HEADER, pack.rules.strip()]

    return "\n".join(parts).strip()


def persona_tokens(pack: Pack, base_url: str | None = None) -> tuple[int, bool]:
    return tokens.count(compile_persona(pack), base_url)
