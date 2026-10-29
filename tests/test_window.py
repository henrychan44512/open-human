"""window：找浏览器、拼参数。不真的开窗口。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import typer

from openhuman import window


def test_find_is_safe_when_nothing_installed(monkeypatch):
    monkeypatch.setattr(window.Path, "is_file", lambda self: False)
    assert window.find() is None


def test_find_returns_an_existing_exe():
    exe = window.find()
    # 这台机器上装了 Chrome/Edge，正常能找到一个；找不到也不该崩
    assert exe is None or Path(exe).is_file()


def test_command_uses_app_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(window.paths, "data_dir", lambda: tmp_path)
    exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    args = window.command(exe, "http://127.0.0.1:8710", (1000, 700))
    assert args[0] == exe
    assert "--app=http://127.0.0.1:8710" in args
    assert "--window-size=1000,700" in args
    assert any(a.startswith("--user-data-dir=") for a in args)
    # 每个浏览器一个独立配置目录，别去动用户自己的浏览记录
    assert (tmp_path / "window" / "chrome").is_dir()


def test_the_profile_does_not_fill_itself_with_chrome_junk(tmp_path, monkeypatch):
    """Chrome 会往 --user-data-dir 里屯自己的东西：实测 1.2 MB → 158.8 MB。

    优化模型 40.1 + crx 缓存 32.6 + WasmTts 24.5 + Safe Browsing 19.1，全是它自己的
    组件，跟我们的页面无关。留着就是让「精简」这条要求慢慢烂掉（BUILD.md §14）。
    """
    monkeypatch.setattr(window.paths, "data_dir", lambda: tmp_path)

    args = window.command(r"C:\x\chrome.exe", "http://127.0.0.1:8710", (900, 600))
    assert "--disable-component-update" in args
    assert "--disable-background-networking" in args
    features = next(a for a in args if a.startswith("--disable-features="))
    assert "OptimizationHints" in features
    assert "OptimizationGuideModelDownloading" in features


def test_name_of_known_and_unknown():
    assert window.name_of(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe") == "edge"
    assert window.name_of(r"C:\Program Files\Google\Chrome\Application\chrome.exe") == "chrome"
    assert window.name_of(r"D:\stuff\thing.exe") == "thing"


def test_open_window_false_without_browser(monkeypatch):
    monkeypatch.setattr(window, "find", lambda: None)
    assert window.open_window("http://127.0.0.1:8710") is False


def test_open_window_falls_back_when_browser_dies(monkeypatch):
    """浏览器起来就退（沙箱/杀软拦）→ 返回 False，让上面开普通标签页。"""
    monkeypatch.setattr(window, "find", lambda: r"C:\x\chrome.exe")
    monkeypatch.setattr(window, "start", lambda exe, args: True)
    monkeypatch.setattr(window, "running", lambda exe: False)
    assert window.open_window("http://127.0.0.1:8710", settle=0.5) is False


def test_open_window_succeeds_when_browser_appears(monkeypatch):
    seen = {"n": 0}

    def fake_running(exe):
        seen["n"] += 1
        return seen["n"] > 1  # 第一次问"本来开着吗"=没有，之后就有了

    monkeypatch.setattr(window, "find", lambda: r"C:\x\chrome.exe")
    monkeypatch.setattr(window, "start", lambda exe, args: True)
    monkeypatch.setattr(window, "running", fake_running)
    assert window.open_window("http://127.0.0.1:8710", settle=1.0) is True


def test_open_window_optimistic_when_already_running(monkeypatch):
    """浏览器本来开着，没法判断是不是我们开的 —— 就当成功，别重复弹标签页。"""
    monkeypatch.setattr(window, "find", lambda: r"C:\x\chrome.exe")
    monkeypatch.setattr(window, "start", lambda exe, args: True)
    monkeypatch.setattr(window, "running", lambda exe: True)
    assert window.open_window("http://127.0.0.1:8710", settle=0.1) is True


# ---------- 交给 cmd.exe 的那一行 ----------


def test_script_is_one_ascii_start_line(tmp_path, monkeypatch):
    """`start "" "chrome.exe" "--app=…"`：一整行，纯 ASCII。

    这个文件由 cmd.exe 按 OEM 代码页读，一个中文注释就能让窗口开不出来。
    """
    monkeypatch.setattr(window.paths, "data_dir", lambda: tmp_path)
    exe = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    line = window.script(exe, "http://127.0.0.1:8710", (900, 600))
    assert line.startswith('start "" "')
    assert f'"{exe}"' in line
    assert '"--app=http://127.0.0.1:8710"' in line
    assert '"--window-size=900,600"' in line
    assert line.isascii()


def test_publish_writes_crlf_ascii(tmp_path, monkeypatch):
    """发布出去的文件必须是 ASCII + CRLF，且不能有 `\\r\\r\\n`。

    TextIOWrapper 的 newline="\\r\\n" 会把已经写好的 "\\n" 再翻一次 —— 结尾变成
    `\\r\\r\\n`，cmd.exe 读到空命令，窗口就不出来了。
    """
    monkeypatch.setattr(window.paths, "data_dir", lambda: tmp_path)
    monkeypatch.setattr(window, "find", lambda: r"C:\x\chrome.exe")

    path = window.publish("http://127.0.0.1:8710")
    assert path == tmp_path / window.SCRIPT_NAME
    raw = path.read_bytes()
    assert raw.decode("ascii").startswith('start "" ')
    assert raw.endswith(b"\r\n")
    assert b"\r\r\n" not in raw
    assert b"\n" not in raw[:-2]


def test_publish_without_browser_is_none(monkeypatch):
    monkeypatch.setattr(window, "find", lambda: None)
    assert window.publish("http://127.0.0.1:8710") is None


def test_serve_in_shell_publishes_instead_of_opening(monkeypatch):
    """壳里跑（有 OPENHUMAN_SHELL_WINDOW）→ 只写 data\\window.cmd，让 cmd.exe 去开。

    从 python 里直接拉浏览器，这台机器上会被杀软杀掉（BUILD.md §14），
    所以这条分支绝不能退化回 open_window / webbrowser。
    """
    from openhuman import cli, window as win

    published: list[str] = []
    opened: list[str] = []
    monkeypatch.setenv(win.SHELL_ENV, "1")
    monkeypatch.setattr(cli, "_listening", lambda host, port: True)
    monkeypatch.setattr(win, "publish", lambda url: published.append(url))
    monkeypatch.setattr(win, "open_window", lambda url: opened.append(url))
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url))

    with pytest.raises(typer.Exit):
        cli.serve()

    assert published == [cli.landing("http://127.0.0.1:8710")]
    assert opened == []


# ---------- tasklist 的坑 ----------


def test_running_pins_the_decoding(monkeypatch):
    """tasklist 按 OEM 代码页说话。这里的 text=True 必须带 encoding/errors ——
    不带的话中文环境下 reader 线程抛 UnicodeDecodeError、stdout 变成 None，
    开窗线程当场崩掉：双击之后什么都不会出现（只有浏览器本来没开时才踩得到）。"""
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(stdout="", returncode=0)

    monkeypatch.setattr(window.subprocess, "run", fake_run)
    window.running(r"C:\x\chrome.exe")
    assert seen.get("text") is True
    assert seen.get("encoding") == "utf-8"
    assert seen.get("errors") == "replace"


def test_running_survives_a_dead_tasklist(monkeypatch):
    monkeypatch.setattr(
        window.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=None, returncode=1)
    )
    assert window.running(r"C:\x\chrome.exe") is True  # 问不出来就别重复开


def test_running_reads_the_no_tasks_message(monkeypatch):
    """中文 Windows 上「没有运行的任务」是 GBK 字节，解码后会变成替换符 —— 不影响判断。"""
    msg = "\ufffd\ufffd: 没有运行的任务匹配指定标准。"
    monkeypatch.setattr(
        window.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=msg, returncode=0)
    )
    assert window.running(r"C:\x\chrome.exe") is False


def test_running_finds_our_browser(monkeypatch):
    row = "chrome.exe                   12345 Console      1    123,456 K"
    monkeypatch.setattr(
        window.subprocess, "run", lambda *a, **k: SimpleNamespace(stdout=row, returncode=0)
    )
    assert window.running(r"C:\x\chrome.exe") is True
