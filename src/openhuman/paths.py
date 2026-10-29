"""路径解析。

项目根目录按这个顺序确定：
1. 环境变量 OPENHUMAN_HOME
2. 当前工作目录（开发时就是仓库根）
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path


def root() -> Path:
    env = os.environ.get("OPENHUMAN_HOME")
    return Path(env).expanduser().resolve() if env else Path.cwd().resolve()


def humans_dir() -> Path:
    return root() / "humans"


def data_dir() -> Path:
    return root() / "data"


def sessions_dir() -> Path:
    return data_dir() / "sessions"


def latest_session(slug: str) -> Path | None:
    """最近一次**说过话**的会话；没有就 None。

    空文件不算。`Session.create` 会先 touch 一个 0 字节的文件 —— 连点两次 [新]、
    或者跑一次测试，都会在 data/sessions/ 里留下几个。按名字取最新就会挑中它，
    于是他「什么都想不起来了」。文件里有一条事件，才算一次会话。
    """
    folder = sessions_dir() / slug
    if not folder.is_dir():
        return None
    files = [p for p in sorted(folder.glob("*.jsonl")) if p.stat().st_size > 0]
    return files[-1] if files else None


def vendor_dir() -> Path:
    return root() / "vendor"


_SLUG_RE = re.compile(r"^[a-z0-9_\-\u4e00-\u9fff]{1,64}$")

# 单文件人格包：一份 Markdown 就是一个人的全部资料。
# 允许中文文件夹名，因为递给它的往往是「我爸」这种名字，不是 `father`。
SINGLE_NAME = "human_data.md"
# 改名前的旧名字，只在报错时提一句（别让填好的文件静默失效）。
LEGACY_SINGLE_NAME = "人类数据.md"
SINGLE_NAMES = (SINGLE_NAME, LEGACY_SINGLE_NAME)


def check_slug(slug: str) -> str:
    """slug：小写字母、数字、下划线、连字符，外加中日韩汉字。"""
    if not _SLUG_RE.match(slug):
        raise ValueError(f"非法 slug: {slug!r}（只能是小写字母/数字/_/-/汉字，最长 64）")
    return slug


def pack_dir(slug: str) -> Path:
    return humans_dir() / check_slug(slug)


def list_packs() -> list[str]:
    """humans/ 下能用的人格包。

    两种形态：传统多文件（有 `human.yaml`），或**单文件**（只有一份 `human_data.md`）。
    `_` 开头的目录是模板/临时目录，不算一个人。
    """
    base = humans_dir()
    if not base.is_dir():
        return []
    return sorted(
        p.name
        for p in base.iterdir()
        if p.is_dir()
        and not p.name.startswith("_")
        and ((p / "human.yaml").is_file() or any((p / n).is_file() for n in SINGLE_NAMES))
    )


def new_session_path(slug: str) -> Path:
    """data/sessions/<slug>/<date>-<n>.jsonl，序号在同一 date 内递增。"""
    folder = sessions_dir() / check_slug(slug)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    n = 1
    while True:
        candidate = folder / f"{stamp}-{n:03d}.jsonl"
        if not candidate.exists():
            return candidate
        n += 1


def is_within(path: Path, base: Path) -> bool:
    """path 解析后是否落在 base 内部（含 base 本身）。"""
    try:
        path.resolve().relative_to(base.resolve())
    except ValueError:
        return False
    return True
