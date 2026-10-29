"""给他一个窗口，而不是一个标签页。

Electron 在这台机器上起不来（`BUILD.md` §25.5（归档）），退一步用系统自带 Chromium 的
「应用模式」：没有地址栏、没有标签页、独立窗口、任务栏单独一个图标 —— 看上去就是
一个桌面应用。浏览器是签过名的，不会被安全软件误杀，也不需要打包。
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from . import paths

SIZE = (1180, 830)

# 壳（`Open Human.cmd`）用的一对文件：python 写启动脚本，cmd.exe 去执行。
#
# 为什么绕这一圈：这台机器上浏览器从 **python 进程里** 拉不起来 —— 起得来，一两秒后
# 就被杀掉，profile 里留一个 175 KB 的 Crashpad 转储（火绒 HipsDaemon 在跑，§25.6（归档） 里
# Electron 崩在同一个坑里）。同样的命令行从 cmd.exe / powershell 起就活得好好的。
# 所以：业务和参数仍然全在 python，python 只把「该怎么开」写成一个 .cmd，
# 让 cmd.exe 当父进程去开。见 `BUILD.md` §14。
SCRIPT_NAME = "window.cmd"
LOG_NAME = "window.log"
SHELL_ENV = "OPENHUMAN_SHELL_WINDOW"

# Chrome 排前面：Edge 在已经开着默认配置的情况下，会忽略 --app 开出一个空白窗口
CANDIDATES = (
    ("chrome", r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ("chrome", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    ("edge", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    ("edge", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    ("brave", r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"),
)


def find() -> str | None:
    for _name, raw in CANDIDATES:
        if Path(raw).is_file():
            return raw
    return None


def name_of(exe: str) -> str:
    for name, raw in CANDIDATES:
        if raw.lower() == exe.lower():
            return name
    return Path(exe).stem.lower()


def command(exe: str, url: str, size: tuple[int, int] = SIZE) -> list[str]:
    # 每个浏览器一个独立配置：窗口位置能记住，也不去碰用户自己的浏览记录
    profile = paths.data_dir() / "window" / name_of(exe)
    profile.mkdir(parents=True, exist_ok=True)
    return [
        exe,
        f"--app={url}",
        f"--window-size={size[0]},{size[1]}",
        f"--user-data-dir={profile}",
        "--no-first-run",
        "--no-default-browser-check",
        # 下面这几条是拦住 Chrome 往这个独立 profile 里屯自己的东西。实测一个
        # profile 从 1.2 MB 长到 158.8 MB（优化模型 40.1 + crx 缓存 32.6 + WasmTts
        # 24.5 + Safe Browsing 19.1），全跟我们的页面无关（BUILD.md §14）。
        "--disable-component-update",
        "--disable-background-networking",
        "--disable-default-apps",
        "--disable-features=Translate,MediaRouter,OptimizationHints,"
        "OptimizationGuideModelDownloading",
        "--disable-session-crashed-bubble",
    ]


def _quote(arg: str) -> str:
    return "'" + arg.replace("'", "''") + "'"


def _quote_dos(arg: str) -> str:
    return '"' + arg + '"'


def script(exe: str, url: str, size: tuple[int, int] = SIZE) -> str:
    """一行能交给 cmd.exe 的命令：`start "" "chrome.exe" "--app=…" …`

    只写 ASCII：这个文件由 cmd.exe 按 OEM 代码页读，中文会变成乱码命令。
    """
    parts = " ".join(_quote_dos(a) for a in command(exe, url, size))
    return f'start "" {parts}'


def publish(url: str) -> Path | None:
    """把「怎么开这个窗口」写成 `data/window.cmd`，等壳里的 cmd.exe 来执行。

    找不到浏览器返回 None（调用方退回普通标签页）。
    """
    exe = find()
    if exe is None:
        return None
    folder = paths.data_dir()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / SCRIPT_NAME
    # ASCII + CRLF：cmd.exe 只认这个。newline 必须是 ""（不翻译），
    # 传 "\r\n" 会把结尾的 "\n" 再翻一次，变成 "\r\r\n"。
    path.write_text(script(exe, url) + "\r\n", encoding="ascii", newline="")
    _log(f"壳模式：已发布 {path.name} → {Path(exe).name}")
    return path


def _log(line: str) -> None:
    """开窗这件事以前完全静默 —— 失败了没人知道为什么。留一条给下次的自己。"""
    try:
        folder = paths.data_dir()
        folder.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with (folder / LOG_NAME).open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp} {line}\n")
    except OSError:
        pass


def running(exe: str) -> bool:
    """这个浏览器现在有没有进程在跑。查不了就当它活着，别重复开。

    坑：tasklist 按 OEM 代码页说话，中文环境下「没有运行的任务」这句是 GBK 字节。
    以前这里用 `text=True` 让 Python 按 UTF-8 解，reader 线程抛 UnicodeDecodeError、
    stdout 变成 None，于是 `out.lower()` 崩掉 —— 崩在开窗线程里，**双击之后就什么
    都不会出现**。只有浏览器本来就没开着的时候才会踩到。
    """
    name = Path(exe).name
    try:
        done = subprocess.run(  # noqa: S603
            ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",  # 解不开的字节变成替换符，进程名是 ASCII，照样能匹配
            timeout=8,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    out = done.stdout or ""
    if done.returncode != 0 and not out.strip():
        return True  # 命令自己失败了，问不出来，别重复开
    return name.lower() in out.lower()


def start(exe: str, args: list[str]) -> bool:
    """让系统把浏览器拉起来。

    为什么绕一圈走 PowerShell 的 Start-Process：在这台机器上，直接 Popen 或者
    ShellExecuteW 起的 Chromium 会自己判死（退出码 0x80000003，连崩溃记录都没有），
    只有 Start-Process 起的能活。实测见 `BUILD.md` §25.6（归档）。丑，但管用。
    """
    listed = ", ".join(_quote(a) for a in args)
    script = f"Start-Process -FilePath {_quote(exe)} -ArgumentList @({listed})"
    try:
        subprocess.Popen(  # noqa: S603 — 参数是列表，没有 shell 拼接
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except OSError:
        return False
    return True


def open_window(
    url: str, size: tuple[int, int] = SIZE, *, settle: float = 6.0, tries: int = 2
) -> bool:
    """开一个应用窗口。打不开就返回 False，让调用方退回普通标签页 ——
    宁可给个标签页，也不能什么都不弹，让人对着黑窗口发呆。

    会试 `tries` 次：第一次冷启动要过杀软的进程扫描，偶发要三秒以上才见到进程，
    只等一次容易把「慢」当成「死」。每次结果都写进 `data/window.log`。
    """
    exe = find()
    if exe is None:
        _log("没找到 Chrome / Edge，直接退回标签页")
        return False

    already = running(exe)
    for attempt in range(1, tries + 1):
        if not start(exe, command(exe, url, size)[1:]):
            _log(f"第 {attempt} 次：Start-Process 都没起来")
            continue
        if already:
            _log(f"第 {attempt} 次：浏览器本来开着，没法验证，先当成功")
            return True
        deadline = settle
        while deadline > 0:
            time.sleep(0.25)
            deadline -= 0.25
            if running(exe):
                _log(f"第 {attempt} 次：窗口起来了（{exe}）")
                return True
        _log(f"第 {attempt} 次：等了 {settle:g} 秒没见到浏览器进程，重试")
        already = running(exe)

    _log("两次都没开出来 —— 这台机器多半拦了「python 启动浏览器」，见 BUILD.md §14")
    return False
