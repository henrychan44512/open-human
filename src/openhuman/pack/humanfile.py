"""单文件人格包：一份 human_data.md 就是一个人的全部资料。

为什么要有这条路：多文件的人格包（human.yaml + SOUL + RULES + memories/*.md）对写代码的人
方便，对「被蒸馏的那个人」是一堵墙 —— 他要写 YAML、要按目录摆、要知道 front-matter。
单文件形态把这些全折叠掉：他拿到一份 Markdown 考卷，从头往下填，填完把文件夹丢进 `humans/`，
runtime 直接读。**没有转换步骤。**

约定只有两条：
- 小节用 `##`，每段记忆用 `###`，`###` 后面写「年-月-日 标题」；
- 其余尽量宽容 —— 认不出来的东西进 warnings，而不是让人白填。
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .. import tokens
from ..paths import SINGLE_NAME
from .persona import PERSONA_BUDGET
from .schema import HumanMeta, MemoryCard, Pack, Person, Presence

# 小节标题里出现这些词就当它是那个小节；顺序有意义（先匹配先得）
SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("soul", ("我是谁", "关于我", "这个人是")),
    ("speech", ("说话", "语气", "口气", "口头禅", "讲话")),
    ("rules", ("不会", "边界", "规矩", "规则", "底线")),
    ("people", ("人物", "家人", "关系", "身边的人")),
    ("memories", ("记忆", "经历", "往事", "事情", "故事")),
    ("samples", ("常说的话", "原话", "语料", "我说过")),
    ("basic", ("基本", "资料", "身份")),
)

_PRESENCE = {
    "活着": Presence.living,
    "在": Presence.living,
    "living": Presence.living,
    "已备份": Presence.archived,
    "归档": Presence.archived,
    "archived": Presence.archived,
}

_DATE_RE = re.compile(
    r"^(?P<y>\d{4})(?:[-./年](?P<m>\d{1,2}))?(?:[-./月](?P<d>\d{1,2}))?日?\s*(?P<title>.*)$"
)
_FIELD_RE = re.compile(r"^(?P<key>[^：:]{1,8})[：:]\s*(?P<value>.*)$")
_HEADING_RE = re.compile(r"^(?P<hashes>#{1,3})\s*(?P<title>.*)$")


_PLACEHOLDER_RE = re.compile(r"^[（(][^）)]{0,20}[）)]$")


def _is_placeholder(text: str) -> bool:
    """整段都是「（在这里写）」这种提示 —— 空表单，不是一个人。"""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return bool(lines) and all(_PLACEHOLDER_RE.match(line) for line in lines)


def _field(line: str) -> tuple[str, str] | None:
    """`键：值`。容忍前面的 `>`、`-`、空格（模板里的提示都这么写）和行尾的 `← 说明`。"""
    cleaned = line.strip().lstrip(">*-").strip()
    match = _FIELD_RE.match(cleaned)
    if not match:
        return None
    value = match.group("value").split("←")[0].strip()
    return match.group("key").strip(), value


def _as_list(raw: str) -> list[str]:
    return [v.strip() for v in re.split(r"[,，、/]", raw) if v.strip()]


def _blocks(lines: list[str]) -> list[list[str]]:
    """按 `###` 切段，返回每段的行。代码块里的 `###` 不算标题。"""
    out: list[list[str]] = []
    current: list[str] = []
    fence = False
    for line in lines:
        if line.strip().startswith("```"):
            fence = not fence
            if current:
                current.append(line)
            continue
        if not fence and line.startswith("###"):
            if current:
                out.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        out.append(current)
    return out


def _parse_when(title: str) -> tuple[date, str] | None:
    match = _DATE_RE.match(title.strip())
    if not match:
        return None
    year = int(match.group("y"))
    month = int(match.group("m") or 1)
    day = int(match.group("d") or 1)
    try:
        when = date(year, month, day)
    except ValueError:
        try:
            when = date(year, month, 1)
        except ValueError:
            return None
    return when, match.group("title").strip()


def _card(when: date, title: str, lines: list[str], source: str) -> MemoryCard:
    people: list[str] = []
    places: list[str] = []
    body: list[str] = []
    for line in lines:
        pair = _field(line)
        if pair:
            key, value = pair
            if key in ("人物", "在场", "谁"):
                people = _as_list(value)
                continue
            if key in ("地点", "在哪"):
                places = _as_list(value)
                continue
        body.append(line)

    return MemoryCard(
        id=f"{when.isoformat()}-{title}" if title else when.isoformat(),
        date=when,
        title=title or when.isoformat(),
        source=source,
        body="\n".join(body).strip(),
        people=people,
        places=places,
        confidence="high",
    )


def parse(text: str, *, slug: str, root: Path | None = None) -> Pack:
    """把一份 human_data.md 解析成 Pack。"""
    warnings: list[str] = []
    fields: dict[str, str] = {}
    soul: list[str] = []
    speech: list[str] = []
    rules: list[str] = []
    samples: list[str] = []
    people: list[Person] = []
    memories: list[MemoryCard] = []
    unknown: list[str] = []
    dateless: list[str] = []

    lines = text.replace("\r\n", "\n").split("\n")
    kind: str | None = None
    level = 0
    fence = False
    section: list[str] = []

    def flush() -> None:
        """把刚结束的那个 `##` 小节收进结果。"""
        if kind is None or not section:
            return
        # `>` 开头的是写给人看的提示，不是内容（问卷里所有说明都这么写）；`---` 是分隔线
        answer = [
            line
            for line in section
            if not line.strip().startswith(">") and not re.fullmatch(r"-{3,}", line.strip())
        ]
        body = "\n".join(answer).strip()
        if kind == "soul":
            soul.append(body)
        elif kind == "speech":
            speech.append(body)
        elif kind == "rules":
            rules.append(body)
        elif kind == "samples":
            for line in answer:
                quote = line.strip().lstrip("-*").strip().strip("「」“”\"'")
                if quote:
                    samples.append(f"> {quote}")
        elif kind == "people":
            people.extend(_people(answer, warnings))
        elif kind == "memories":
            for block in _blocks(answer):
                title = block[0].lstrip("#").strip()
                if not title:  # 模板里那个空的 `### ` 不算一条
                    continue
                parsed = _parse_when(title)
                if parsed is None:
                    dateless.append(title)
                    continue
                when, name = parsed
                memories.append(_card(when, name, block[1:], f"{SINGLE_NAME}#{title}"))

    for line in lines:
        # 代码块里的东西只是示范，不当真（模板里的示例记忆就靠这条躲过去）
        if line.strip().startswith("```"):
            fence = not fence
            if level == 2:
                section.append(line)
            continue
        if fence:
            if level == 2:
                section.append(line)
            continue

        heading = _HEADING_RE.match(line)
        if heading and len(heading.group("hashes")) <= 2:
            flush()
            level = len(heading.group("hashes"))
            title = heading.group("title").strip()
            kind = None if level == 1 else _kind(title)
            if level == 2 and kind is None and title:
                unknown.append(title)
            section = []
            continue
        if level == 2 and kind == "basic":
            pair = _field(line)
            if pair:
                fields[pair[0]] = pair[1]
            continue
        if level == 2:
            section.append(line)
    flush()

    name = fields.get("名字") or fields.get("姓名") or slug
    presence_raw = (fields.get("状态") or fields.get("在不在") or "").strip()
    presence = _PRESENCE.get(presence_raw.lower(), Presence.unknown if presence_raw else Presence.living)

    soul_text = "\n\n".join(s for s in soul if s).strip()
    if not soul_text or _is_placeholder(soul_text):
        raise ValueError(f"{SINGLE_NAME} 里「我是谁」是空的 —— 他得先有个人。")

    speech_text = "\n\n".join(s for s in speech if s).strip()
    rules_text = "\n".join(r for r in rules if r).strip()
    if not rules_text:
        warnings.append("没写「我不会」—— 模型没有边界约束")

    if not memories:
        warnings.append("一张记忆卡都没有，他会没什么可说")
    for title in dateless:
        warnings.append(f"「{title}」没写年份，已跳过（改成「### 1985-06-15 {title}」就会进检索）")
    for title in unknown:
        warnings.append(f"没认出的小节「{title}」，已忽略")

    meta = HumanMeta(
        slug=slug,
        name=name,
        presence=presence,
        last_record=_parse_last(fields.get("最后一条") or fields.get("最后记录")),
        first_line=fields.get("第一句") or "……你来了。",
        sleep_line=fields.get("晚安句") or "那我等你。",
        wake_line=fields.get("回来句") or "你回来了。",
        idle_line=fields.get("沉默句") or "",
        aliases=_as_list(fields.get("称呼", "")),
    )

    pack = Pack(
        meta=meta,
        soul=soul_text,
        speech=speech_text,
        rules=rules_text,
        samples="\n".join(samples),
        memories=memories,
        people=people,
        root=root,
        warnings=warnings,
    )

    used, _ = tokens.count("\n".join([pack.soul, pack.speech, pack.rules]))
    if used > PERSONA_BUDGET:
        warnings.append(
            f"「我是谁」+「我怎么说话」+「我不会」约 {used} tok，超过预算 {PERSONA_BUDGET}，先删一些"
        )
    return pack


def _kind(title: str) -> str | None:
    for kind, words in SECTIONS:
        if any(word in title for word in words):
            return kind
    return None


def _parse_last(raw: str | None) -> date | None:
    if not raw:
        return None
    parsed = _parse_when(raw)
    return parsed[0] if parsed else None


def _people(lines: list[str], warnings: list[str]) -> list[Person]:
    out: list[Person] = []
    for block in _blocks(lines):
        name = block[0].lstrip("#").strip()
        if not name:
            continue
        relation = ""
        aliases: list[str] = []
        body: list[str] = []
        for line in block[1:]:
            pair = _field(line)
            if pair:
                key, value = pair
                if key in ("关系", "是谁"):
                    relation = value
                    continue
                if key in ("称呼", "叫法"):
                    aliases = _as_list(value)
                    continue
            body.append(line)
        out.append(
            Person(name=name, relation=relation, aliases=aliases, body="\n".join(body).strip())
        )
    if not out and any(line.strip() for line in lines):
        warnings.append("「人物」小节里没有 `###` 小标题，当没人处理")
    return out
