"""文件工具。所有路径先 resolve，再判断落在不在允许的根里。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..paths import is_within

MAX_READ = 12_000  # 字符
MAX_LIST = 200      # 条目


class ToolError(Exception):
    """工具拒绝执行，消息直接给模型看。"""


@dataclass
class Scope:
    """读的边界和写的边界不是同一个。"""

    read_root: Path
    write_root: Path


def _resolve(path: str, root: Path, what: str) -> Path:
    if not path or path.strip() in ("", ".", "/", "\\"):
        return root.resolve()
    raw = Path(path.strip())
    candidate = raw if raw.is_absolute() else (root / raw)
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise ToolError(f"路径无效: {path}") from exc
    if not is_within(resolved, root):
        raise ToolError(f"越界了：{path} 不在允许的目录里（{what}）")
    return resolved


def _candidates(scope: Scope, path: str) -> list[Path]:
    """读的时候先看 workspace，再看人格包根目录。

    模型说 "notes.md" 的时候，指的是他能看见的那个 notes.md，
    也就是 workspace 里的；说 "SOUL.md" 才是人格包根目录那份。
    """
    raw = (path or "").strip().replace("\\", "/")
    if raw.startswith("workspace/"):
        raw = raw[len("workspace/") :]
    if raw in ("", ".", "workspace"):
        return [scope.write_root.resolve(), scope.read_root.resolve()]

    out: list[Path] = []
    for base in (scope.write_root, scope.read_root):
        candidate = (base / raw) if not Path(raw).is_absolute() else Path(raw)
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if not is_within(resolved, base):
            continue
        if resolved not in out:
            out.append(resolved)
    if not out:
        raise ToolError(f"越界了：{path} 不在允许的目录里（只能读人格包内的文件）")
    return out


def read_path(scope: Scope, path: str) -> Path:
    candidates = _candidates(scope, path)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def write_path(scope: Scope, path: str) -> Path:
    """写路径相对 workspace。模型爱写 "workspace/x.md"，顺手容忍一下。"""
    raw = (path or "").strip().replace("\\", "/")
    if raw in ("", ".", "workspace", "workspace/"):
        return scope.write_root.resolve()
    if raw.startswith("workspace/"):
        raw = raw[len("workspace/") :]
    return _resolve(raw, scope.write_root, "只能写 workspace/")


# ---------- 读 ----------


def read_file(scope: Scope, path: str, max_chars: int = MAX_READ) -> str:
    target = read_path(scope, path)
    if not target.exists():
        raise ToolError(f"没有这个文件: {path}")
    if target.is_dir():
        raise ToolError(f"{path} 是目录，用 list_dir")
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ToolError(f"{path} 不是 UTF-8 文本") from exc
    except OSError as exc:
        raise ToolError(f"读不了 {path}: {exc}") from exc

    if len(text) > max_chars:
        cut = text[:max_chars]
        dropped = len(text) - max_chars
        return f"{cut}\n\n…（还有 {dropped} 个字符没显示）"
    return text


def list_dir(scope: Scope, path: str = ".") -> str:
    target = read_path(scope, path)
    if not target.exists():
        raise ToolError(f"没有这个目录: {path}")
    if not target.is_dir():
        raise ToolError(f"{path} 不是目录")

    try:
        entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name))
    except OSError as exc:
        raise ToolError(f"列不了 {path}: {exc}") from exc

    lines: list[str] = []
    for entry in entries[:MAX_LIST]:
        if entry.name.startswith("."):
            continue
        mark = "/" if entry.is_dir() else ""
        size = "" if entry.is_dir() else f"  {entry.stat().st_size:,} B"
        lines.append(f"{entry.name}{mark}{size}")
    if len(entries) > MAX_LIST:
        lines.append(f"…（还有 {len(entries) - MAX_LIST} 项）")
    return "\n".join(lines) or "（空目录）"


# ---------- 写 ----------


def write_file(scope: Scope, path: str, content: str) -> str:
    target = write_path(scope, path)
    if target == scope.write_root.resolve():
        raise ToolError("不能覆盖 workspace 目录本身")
    existed = target.exists()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"写不了 {path}: {exc}") from exc
    action = "整个覆盖了" if existed else "新建了"
    return f"已{action} {path}（{len(content)} 字）"


def append_file(scope: Scope, path: str, content: str) -> str:
    """加东西用这个。write_file 会把原文件冲掉。"""
    target = write_path(scope, path)
    if target == scope.write_root.resolve():
        raise ToolError("不能往 workspace 目录本身追加")
    if not content.strip():
        raise ToolError("要追加的内容是空的")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        glue = "" if not existing or existing.endswith("\n") else "\n"
        with target.open("a", encoding="utf-8") as fh:
            fh.write(f"{glue}{content.strip()}\n")
    except OSError as exc:
        raise ToolError(f"追加不了 {path}: {exc}") from exc
    return f"已在 {path} 末尾加了一句（{len(content.strip())} 字）"


def edit_file(scope: Scope, path: str, old: str, new: str) -> str:
    target = write_path(scope, path)
    if not target.exists():
        raise ToolError(f"没有这个文件: {path}")
    if not old:
        raise ToolError("old 不能为空")

    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0:
        raise ToolError(f"{path} 里找不到那段原文")
    if count > 1:
        raise ToolError(f"那段原文在 {path} 里出现了 {count} 次，不确定改哪个")
    try:
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
    except OSError as exc:
        raise ToolError(f"写不了 {path}: {exc}") from exc
    return f"已改 {path}"
