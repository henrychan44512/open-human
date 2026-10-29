"""人格包加载与校验。"""

from __future__ import annotations

import re
from pathlib import Path

import frontmatter
import yaml
from pydantic import ValidationError

from ..paths import LEGACY_SINGLE_NAME
from . import humanfile
from .schema import HumanMeta, MemoryCard, Pack, Person

REQUIRED = ("human.yaml", "SOUL.md", "RULES.md")


class PackError(Exception):
    """人格包有问题，消息直接给用户看。"""


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _frontmatter(path: Path) -> tuple[dict, str]:
    post = frontmatter.load(path)
    return dict(post.metadata), post.content.strip()


def _as_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in re.split(r"[,，、]", value) if v.strip()]
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [str(value)]


def load_meta(root: Path) -> HumanMeta:
    path = root / "human.yaml"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise PackError(f"{path.name} 不是合法 YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise PackError(f"{path.name} 应该是一个映射")
    try:
        return HumanMeta.model_validate(raw)
    except ValidationError as exc:
        raise PackError(f"{path.name} 字段有误:\n{exc}") from exc


def load_memories(root: Path, warnings: list[str]) -> list[MemoryCard]:
    folder = root / "memories"
    if not folder.is_dir():
        return []

    cards: list[MemoryCard] = []
    seen: dict[str, Path] = {}
    for path in sorted(folder.rglob("*.md")):
        meta, body = _frontmatter(path)
        meta.setdefault("source", str(path.relative_to(root)).replace("\\", "/"))
        meta.setdefault("body", body)
        for key in ("people", "places", "emotion", "tags", "aliases"):
            if key in meta:
                meta[key] = _as_list(meta[key])
        try:
            card = MemoryCard.model_validate(meta)
        except ValidationError as exc:
            warnings.append(f"跳过 {path.name}: 字段不全（{_first_error(exc)}）")
            continue
        card.path = path
        if not card.source.strip():
            warnings.append(f"{card.id}: 缺 source，不进检索")
        if card.id in seen:
            warnings.append(
                f"duplicate id {card.id}: {seen[card.id].name} 与 {path.name}，保留后者"
            )
            cards = [c for c in cards if c.id != card.id]
        seen[card.id] = path
        cards.append(card)
    return cards


def load_people(root: Path, warnings: list[str]) -> list[Person]:
    folder = root / "people"
    if not folder.is_dir():
        return []

    people: list[Person] = []
    for path in sorted(folder.glob("*.md")):
        meta, body = _frontmatter(path)
        if "name" not in meta:
            meta["name"] = path.stem
            warnings.append(f"people/{path.name} 没写 name，用文件名代替")
        meta.setdefault("body", body)
        meta["slug"] = path.stem
        meta["aliases"] = _as_list(meta.get("aliases"))
        try:
            person = Person.model_validate(meta)
        except ValidationError as exc:
            warnings.append(f"跳过 people/{path.name}: {_first_error(exc)}")
            continue
        person.path = path
        people.append(person)
    return people


def _first_error(exc: ValidationError) -> str:
    err = exc.errors()[0]
    loc = ".".join(str(x) for x in err["loc"])
    return f"{loc}: {err['msg']}"


def load_pack(root: Path) -> Pack:
    root = Path(root)
    if not root.is_dir():
        raise PackError(f"找不到人格包目录: {root}")

    missing = [name for name in REQUIRED if not (root / name).is_file()]
    single = root / humanfile.SINGLE_NAME
    legacy = root / LEGACY_SINGLE_NAME
    if missing and legacy.is_file() and not single.is_file():
        raise PackError(f"{legacy.name} 改过名字了：把它改名成 {humanfile.SINGLE_NAME} 就能用。")
    if missing and single.is_file():
        # 单文件人格包：一份 human_data.md 就是全部（BUILD.md §6.1）
        try:
            return humanfile.parse(single.read_text(encoding="utf-8"), slug=root.name, root=root)
        except ValueError as exc:
            raise PackError(str(exc)) from exc
    if missing:
        hint = ""
        if not single.is_file():
            hint = f"（也可以只放一份 {humanfile.SINGLE_NAME}）"
        raise PackError(f"{root.name} 缺少必填文件: {', '.join(missing)}{hint}")

    warnings: list[str] = []
    meta = load_meta(root)

    soul = _read(root / "SOUL.md")
    rules = _read(root / "RULES.md")
    if not soul:
        raise PackError("SOUL.md 是空的")
    if not rules:
        warnings.append("RULES.md 是空的，模型没有边界约束")

    def optional(rel: str) -> str:
        path = root / rel
        return _read(path) if path.is_file() else ""

    pack = Pack(
        meta=meta,
        soul=soul,
        rules=rules,
        speech=optional("traits/speech.md"),
        samples=optional("voice/samples.md"),
        timeline=optional("timeline.md"),
        people=load_people(root, warnings),
        memories=load_memories(root, warnings),
        root=root,
        warnings=warnings,
    )
    if single.is_file():
        pack.warnings.append(f"同时有传统文件和 {humanfile.SINGLE_NAME}，这次用的是传统文件")
    return pack
