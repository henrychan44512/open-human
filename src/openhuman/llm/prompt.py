"""prompt 组装。

布局是性能问题，不只是排版问题（BUILD.md §11）：

    [system: persona]        ← 每轮完全一样，缓存命中
    [history ...]            ← 只追加
    [user: 记忆块 + 问题]     ← 只有这一段每轮变

记忆块必须放在历史之后、问题之前。放到 system 或历史前面，
会把后面所有 token 一起作废。
"""

from __future__ import annotations

from datetime import datetime

from ..pack.schema import MemoryCard

MEMORY_OPEN = "<记忆>"
MEMORY_CLOSE = "</记忆>"

MEMORY_NOTE = (
    "（下面是你自己想起来的东西，不是对方说的。别念出来，"
    "只挑一句用得上的说，剩下的等对方问。卡片里没写的就是没记下来。）"
)

# 检索空了，但对方确实在问一件往事：先把「不许编」摆在问题前面。
# 不加这句，2B 会顺手编一个年份出来 —— 比说记不清糟得多。
MISS_NOTE = (
    "（这件事你脑子里是空的，一个字都想不起来。别顺着上面的话往下编，"
    "也别补年份、地点、天气。就说想不起来。）"
)

# 卡片就在眼前的时候，2B 倾向把整张卡念一遍（实测 101–153 字），
# 屏幕上一整段话不像人在说话，也没人等你读。
# 放在问题**后面**；措辞要「带一个细节」，只说「短一点」它会缩成光秃秃的日期，
# 或者干脆不理。
SHORT_NOTE = "（一两句话，挑一个细节说。）"

_WEEK = "一二三四五六日"


def _part(hour: int) -> str:
    if hour < 5:
        return "凌晨"
    if hour < 9:
        return "早上"
    if hour < 12:
        return "上午"
    if hour < 13:
        return "中午"
    if hour < 17:
        return "下午"
    if hour < 19:
        return "傍晚"
    return "晚上"


def clock_line(now: datetime | None = None) -> str:
    """他知道现在几点。

    他住在这台机器里，看得见钟 —— 第四轮之前问「现在几点了」，他答
    「想不起来」，因为每一轮他都只收到一句话和几张记忆卡。
    这一行放在最后一轮的用户消息里（不是 system）：每轮都会变，
    放进 system 会把 prefix cache 整个作废（§11 N-01）。
    """
    now = now or datetime.now().astimezone()
    hour = now.hour % 12 or 12
    return (
        f"（此刻：{now.month} 月 {now.day} 日，星期{_WEEK[now.weekday()]}，"
        f"{_part(now.hour)} {hour} 点 {now.minute:02d} 分。）"
    )


def render_memory(cards: list[MemoryCard]) -> str:
    """把检索结果压成紧凑文本。带上 id 方便模型引用。"""
    if not cards:
        return ""
    lines = [MEMORY_OPEN, MEMORY_NOTE]
    for card in cards:
        lines.append(card.render())
    lines.append(MEMORY_CLOSE)
    return "\n".join(lines)


def build_user_message(
    user_text: str,
    cards: list[MemoryCard] | None = None,
    *,
    missed: bool = False,
    clock: str = "",
) -> str:
    parts: list[str] = []
    if clock:
        parts.append(clock)
    block = render_memory(cards or [])
    if block:
        parts.append(block)
    elif missed:
        parts.append(MISS_NOTE)
    parts.append(user_text)
    if block:
        parts.append(SHORT_NOTE)
    return "\n\n".join(parts)


def build_messages(
    persona: str,
    history: list[dict],
    user_text: str,
    cards: list[MemoryCard] | None = None,
    *,
    missed: bool = False,
    clock: str = "",
) -> list[dict]:
    """history 里的条目已经是 {role, content}，原样透传。"""
    messages: list[dict] = [{"role": "system", "content": persona}]
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": build_user_message(user_text, cards, missed=missed, clock=clock),
        }
    )
    return messages


def warmup_messages(persona: str, marker: str = "在。") -> list[dict]:
    """开机预热用。越短越好，只为把 persona 前缀灌进缓存（§11 N-02）。"""
    return [
        {"role": "system", "content": persona},
        {"role": "user", "content": marker},
    ]
