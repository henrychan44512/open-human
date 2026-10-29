"""跑命令。cwd 锁在 workspace，超时连子进程一起杀。"""

from __future__ import annotations

import subprocess
import sys

from .files import Scope, ToolError

TIMEOUT_S = 10.0
MAX_OUTPUT = 4_000  # 字符
MAX_COMMAND = 500


def _decode(raw: bytes) -> str:
    for encoding in ("utf-8", "gbk", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _kill_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            check=False,
        )
    else:
        try:
            import os
            import signal

            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except OSError:
            pass


def run_command(scope: Scope, cmd: str, timeout: float = TIMEOUT_S) -> str:
    cmd = (cmd or "").strip()
    if not cmd:
        raise ToolError("命令是空的")
    if len(cmd) > MAX_COMMAND:
        raise ToolError(f"命令太长（{len(cmd)} 字），请拆开")

    cwd = scope.write_root
    cwd.mkdir(parents=True, exist_ok=True)

    proc = subprocess.Popen(
        ["cmd", "/c", cmd] if sys.platform == "win32" else ["/bin/sh", "-c", cmd],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
    )

    try:
        out, _ = proc.communicate(timeout=timeout)
        code = proc.returncode
    except subprocess.TimeoutExpired:
        _kill_tree(proc.pid)
        try:
            out, _ = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            out = b""
        text = _decode(out or b"")
        raise ToolError(
            f"命令超过 {timeout:.0f} 秒没跑完，已经杀掉。\n输出：\n{_clip(text)}"
        ) from None

    text = _decode(out or b"")
    if code != 0:
        raise ToolError(f"命令失败（退出码 {code}）：\n{_clip(text)}")
    return _clip(text) or "（没有输出）"


def _clip(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_OUTPUT:
        return text
    return text[:MAX_OUTPUT] + f"\n…（输出被截断，共 {len(text)} 字）"
