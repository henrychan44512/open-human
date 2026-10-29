"""工具注册表：给模型看的 schema，和真正执行的入口。

两条规矩（BUILD.md §4）：
1. 读只能读人格包内，写只能写 workspace/。
2. 有副作用的工具（写、改、跑命令）必须先问人。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import files, shell
from .files import Scope, ToolError


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict
    mutating: bool = False

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class ToolResult:
    ok: bool
    output: str

    def as_content(self) -> str:
        """回给模型的内容。失败也照实说。"""
        return self.output if self.ok else f"失败：{self.output}"


SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="read_file",
        description="读一个文本文件。只能读人格包目录里的文件。",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "相对路径，如 notes.md"}},
            "required": ["path"],
        },
    ),
    ToolSpec(
        name="list_dir",
        description="列一个目录里的东西。不传 path 就是根目录。",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "相对路径"}},
            "required": [],
        },
    ),
    ToolSpec(
        name="write_file",
        description=(
            "新建一个文件，或者整个覆盖已有的文件。"
            "注意：它会用你给的内容替换掉原文件的全部内容。"
            "只是想在已有文件里加一句话，别用这个，用 append_file。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对 workspace 的路径"},
                "content": {"type": "string", "description": "完整内容"},
            },
            "required": ["path", "content"],
        },
        mutating=True,
    ),
    ToolSpec(
        name="append_file",
        description="在一个文件的末尾加内容，原来的内容不动。文件不存在就新建。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "相对 workspace 的路径"},
                "content": {"type": "string", "description": "要加到末尾的内容"},
            },
            "required": ["path", "content"],
        },
        mutating=True,
    ),
    ToolSpec(
        name="edit_file",
        description="把文件里的一段原文替换成新的。原文必须唯一出现。只能改 workspace/ 里的文件。",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old": {"type": "string", "description": "要被替换的原文"},
                "new": {"type": "string", "description": "替换成什么"},
            },
            "required": ["path", "old", "new"],
        },
        mutating=True,
    ),
    ToolSpec(
        name="run_command",
        description=(
            "在 workspace/ 里跑一条命令。10 秒超时，输出会被截断。"
            "这是 Windows，用 cmd 命令：dir 不是 ls，type 不是 cat，用 \\ 不用 /。"
        ),
        parameters={
            "type": "object",
            "properties": {"cmd": {"type": "string", "description": "要执行的命令"}},
            "required": ["cmd"],
        },
        mutating=True,
    ),
)

BY_NAME = {spec.name: spec for spec in SPECS}

ConfirmFn = Callable[[ToolSpec, dict], bool]


def _ask(spec: ToolSpec, args: dict) -> bool:  # 默认：不许
    return False


class Tools:
    def __init__(self, scope: Scope, confirm: ConfirmFn | None = None) -> None:
        self.scope = scope
        self.confirm = confirm or _ask
        self.calls: list[tuple[str, dict, bool]] = []

    def __len__(self) -> int:
        return len(SPECS)

    def schemas(self) -> list[dict]:
        return [spec.schema() for spec in SPECS]

    def execute(self, name: str, args: dict[str, Any]) -> ToolResult:
        spec = BY_NAME.get(name)
        if spec is None:
            return ToolResult(False, f"没有这个工具: {name}")

        if not isinstance(args, dict):
            return ToolResult(False, "参数不是一个对象")

        if spec.mutating and not self.confirm(spec, args):
            self.calls.append((name, args, False))
            return ToolResult(False, "对方没有同意，这个操作没做")

        try:
            output = self._dispatch(name, args)
        except ToolError as exc:
            self.calls.append((name, args, False))
            return ToolResult(False, str(exc))
        except Exception as exc:  # noqa: BLE001 — 工具出错不能把整个对话带崩
            self.calls.append((name, args, False))
            return ToolResult(False, f"工具出错（{type(exc).__name__}）: {exc}")

        self.calls.append((name, args, True))
        return ToolResult(True, output)

    def _dispatch(self, name: str, args: dict[str, Any]) -> str:
        if name == "read_file":
            return files.read_file(self.scope, str(args.get("path", "")))
        if name == "list_dir":
            return files.list_dir(self.scope, str(args.get("path", ".")))
        if name == "write_file":
            return files.write_file(
                self.scope, str(args.get("path", "")), str(args.get("content", ""))
            )
        if name == "append_file":
            return files.append_file(
                self.scope, str(args.get("path", "")), str(args.get("content", ""))
            )
        if name == "edit_file":
            return files.edit_file(
                self.scope,
                str(args.get("path", "")),
                str(args.get("old", "")),
                str(args.get("new", "")),
            )
        if name == "run_command":
            return shell.run_command(self.scope, str(args.get("cmd", "")))
        raise ToolError(f"没有这个工具: {name}")


def scope_for(pack_root: Path) -> Scope:
    """人格包根目录可读，workspace/ 可写。"""
    return Scope(read_root=pack_root, write_root=pack_root / "workspace")
