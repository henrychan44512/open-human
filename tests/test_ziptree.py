"""打包器的两条底线：中文文件名不能坏，漏出来的东西要在打包时就炸。

bsdtar 的坑（OEM 代码页 + 拒绝带中文的 -T 清单）见 scripts/zip_tree.py 开头。
这里只测 zip_tree，不跑真打包 —— 真包有 1.8 GB。
"""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def zip_tree():
    spec = importlib.util.spec_from_file_location("zip_tree", ROOT / "scripts" / "zip_tree.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _tree(root: Path, names: dict[str, str]) -> list[str]:
    for rel, body in names.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return list(names)


def test_chinese_name_survives_the_roundtrip(zip_tree, tmp_path):
    root = tmp_path / "repo"
    items = _tree(root, {"中间/记忆.md": "2010 年儿子结婚。\n"})
    out = tmp_path / "out.zip"

    zip_tree.build(root, items, out, required=("中间/记忆.md",), forbidden=("data/",))

    with zipfile.ZipFile(out) as zf:
        info = zf.getinfo("中间/记忆.md")
        assert zf.read("中间/记忆.md") == (root / "中间/记忆.md").read_bytes()
    # 没有这一位，别的机器上解出来就是乱码。
    assert info.flag_bits & 0x800


def test_a_missing_required_entry_stops_the_pack(zip_tree, tmp_path):
    root = tmp_path / "repo"
    items = _tree(root, {"README.md": "hi\n"})
    with pytest.raises(SystemExit, match="archive is missing"):
        zip_tree.build(root, items, tmp_path / "out.zip", required=("README.md", "human_data.md"))


def test_forbidden_paths_stop_the_pack(zip_tree, tmp_path):
    root = tmp_path / "repo"
    items = _tree(root, {"README.md": "hi\n", "data/llama.log": "chat noise\n"})
    with pytest.raises(SystemExit, match="archive leaked"):
        zip_tree.build(root, items, tmp_path / "out.zip", required=("README.md",), forbidden=("data/",))


def test_a_file_that_vanished_mid_pack_is_skipped(zip_tree, tmp_path):
    root = tmp_path / "repo"
    items = _tree(root, {"README.md": "hi\n"})
    items.append("data/window/gone.lock")  # never written: a live Chrome profile
    assert zip_tree.build(root, items, tmp_path / "out.zip", required=("README.md",),
                          forbidden=("data/",)) == 0


def test_the_questionnaire_is_on_the_required_list(zip_tree):
    template = "humans/_template/human_data.md"
    assert template in zip_tree.REQUIRED
    assert (ROOT / template).is_file()
