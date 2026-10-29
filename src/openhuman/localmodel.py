"""本地模型进程：判活、拉起、收尾。

双击启动时不该让人先手打一长串 llama-server 参数。这个模块只做一件事：
需要时把 llama-server 拉起来，退出时收掉。对话逻辑一行都不在这里。

已经有人在跑（比如手启动的）就什么都不做 —— 不是我们拉起来的，也不归我们关。
"""

from __future__ import annotations

import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from . import paths
from .config import Config

START_TIMEOUT = 90.0
POLL = 0.4


def port_of(base_url: str) -> int:
    parsed = urlparse(base_url)
    return parsed.port or (443 if parsed.scheme == "https" else 80)


def healthy(base_url: str, timeout: float = 1.5) -> bool:
    """llama-server 有 /health；200 才算真的能推理。"""
    url = f"{base_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as res:
            return res.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


def model_path(cfg: Config) -> Path:
    return paths.root() / cfg.llama.model_file


def program(cfg: Config) -> tuple[Path, Path] | None:
    """二进制和权重都在才返回 (exe, model)，否则 None。"""
    exe = paths.vendor_dir() / "llama" / "llama-server.exe"
    model = model_path(cfg)
    if exe.is_file() and model.is_file():
        return exe, model
    return None


def threads() -> int:
    return max(2, min(os.cpu_count() or 4, 8))


def command(cfg: Config, exe: Path, model: Path) -> list[str]:
    return [
        str(exe),
        "-m", str(model),
        "-a", cfg.llama.model,
        "--host", "127.0.0.1",
        "--port", str(port_of(cfg.llama.base_url)),
        "-ngl", "0",
        "-t", str(threads()),
        "-c", str(cfg.llama.context),
        "-np", "1",
        "-fa", "on",
        "--jinja",
        "--reasoning-format", "none",
    ]


def start(cfg: Config) -> subprocess.Popen | None:
    found = program(cfg)
    if found is None:
        return None
    exe, model = found

    log = paths.data_dir() / "llama.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log.open("ab") as handle:
        return subprocess.Popen(  # noqa: S603 — 参数是拼好的列表，没有 shell
            command(cfg, exe, model),
            cwd=paths.root(),
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
        )


def wait(base_url: str, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if healthy(base_url):
            return True
        time.sleep(POLL)
    return False


def stop(proc: subprocess.Popen | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()


def ensure(
    cfg: Config,
    *,
    wait_s: float = START_TIMEOUT,
    out=print,
) -> subprocess.Popen | None:
    """确保模型能用。返回子进程（归我们管），或 None（已在线 / 没装 / 起不来）。"""
    if healthy(cfg.llama.base_url):
        out(f"  模型已经在线（{cfg.llama.base_url}）")
        return None
    if program(cfg) is None:
        out("  没找到 llama-server 或权重，界面会显示离线")
        return None

    out("  正在把模型读进内存…")
    proc = start(cfg)
    if proc is None:
        return None
    if wait(cfg.llama.base_url, wait_s):
        out(f"  模型就绪（{cfg.llama.model}）")
        return proc
    stop(proc)
    out("  模型 90 秒内没起来，看看 data/llama.log")
    return None
