"""测试的公共约束：谁都不许往仓库的 data/ 里写东西。

不隔离的话，任何一次 `Session.create` 都会在 `data/sessions/<slug>/` 留下一个空
`.jsonl`；而 `Session.resume` 挑的是**最新**那个文件 —— 于是跑几次测试，用户真正的
对话就被一串空文件挤到后面去了，界面上看就是「他忽然什么都想不起来了」。
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from openhuman import paths

# 这台机器上 %TEMP% 不可用：Python 在里面建临时文件会卡住，tempfile 于是退到
# 「当前目录」，每跑一次测试就在仓库根留一个 `pytest-of-henry/`（几百个文件）。
# 把 pytest 的 tmp 根钉在 `data/pytest-tmp`：一样是丢弃目录，但不会出现在根目录。
TMP_ROOT = Path(__file__).resolve().parents[1] / "data" / "pytest-tmp"
TMP_ROOT.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(TMP_ROOT)


def pytest_unconfigure(config):
    """跑完把它收掉 —— 否则每跑一次就在 data/ 里留一百多个文件。"""
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


@pytest.fixture(autouse=True)
def isolated_data(tmp_path, monkeypatch):
    """把 data/ 指到一个临时目录，测试结束即销毁。"""
    data = tmp_path / "data"
    data.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(paths, "data_dir", lambda: data)
    return data
