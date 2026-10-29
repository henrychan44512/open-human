"""启动入口：双击之后该直接看见谁；排障命令不该自己先崩。"""

from __future__ import annotations

import io

from typer.testing import CliRunner

from openhuman import __version__, cli, paths
from openhuman.cli import landing


def test_landing_goes_straight_to_the_only_person(monkeypatch):
    """只有一个人格包时，中间那层「点一下他」的菜单是多余的。"""
    monkeypatch.setattr(paths, "list_packs", lambda: ["demo"])
    assert landing("http://127.0.0.1:8710") == "http://127.0.0.1:8710/chat/demo"


def test_landing_keeps_the_list_for_zero_or_many(monkeypatch):
    url = "http://127.0.0.1:8710"

    monkeypatch.setattr(paths, "list_packs", lambda: [])
    assert landing(url) == url  # 一个包都没有：至少让人看见怎么放一个进去

    monkeypatch.setattr(paths, "list_packs", lambda: ["a", "b"])
    assert landing(url) == url  # 多人格才需要列表页来做选择


# ---------- 版本 ----------


def test_version_is_visible_without_starting_anything():
    """beta 得报得出自己是哪一版：`oh --version`，不碰模型、不碰网络。"""
    result = CliRunner().invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
    assert "beta" in result.output


# ---------- 编码 ----------


def test_gbk_redirect_does_not_kill_the_doctor_table(monkeypatch):
    """`oh doctor > log.txt` 以前直接崩：cp936 编不出 ✓（U+2713）。

    重定向出去的不是终端，按 UTF-8 写；编码错误降级成替换符而不是抛异常。
    排障命令自己先崩，等于没有排障命令。
    """
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="gbk", errors="strict")
    monkeypatch.setattr(cli.sys, "stdout", stream)
    monkeypatch.setattr(cli.sys, "stderr", stream)

    cli._tame_streams()
    stream.write("✓ 都通过\n")  # 以前这一行就是 UnicodeEncodeError
    stream.flush()

    assert raw.getvalue().decode("utf-8").startswith("✓ 都通过")
