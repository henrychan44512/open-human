"""工具：边界、越界、超时、诚实失败。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from openhuman.tools import Scope, ToolError, Tools, scope_for
from openhuman.tools import files, shell


@pytest.fixture
def pack(tmp_path: Path) -> Path:
    root = tmp_path / "demo"
    (root / "workspace").mkdir(parents=True)
    (root / "memories").mkdir()
    (root / "SOUL.md").write_text("你叫陈建国。", encoding="utf-8")
    (root / "memories" / "a.md").write_text("---\nid: a\n---\n正文", encoding="utf-8")
    (root / "workspace" / "notes.md").write_text("三行笔记\n第二行\n第三行", encoding="utf-8")
    return root


@pytest.fixture
def scope(pack: Path) -> Scope:
    return scope_for(pack)


# ---------- 读 ----------


def test_read_inside_pack(scope):
    assert "三行笔记" in files.read_file(scope, "workspace/notes.md")


def test_read_workspace_file_with_bare_name(scope):
    """模型爱说 notes.md，指的就是 workspace 里那份。"""
    assert "三行笔记" in files.read_file(scope, "notes.md")


def test_read_prefers_workspace_over_pack_root(pack: Path, scope: Scope):
    (pack / "notes.md").write_text("根目录的那份", encoding="utf-8")
    assert "三行笔记" in files.read_file(scope, "notes.md")


def test_read_persona_file_is_allowed(scope):
    assert "陈建国" in files.read_file(scope, "SOUL.md")


def test_read_outside_pack_is_rejected(scope):
    with pytest.raises(ToolError, match="越界"):
        files.read_file(scope, "../../config.toml")


def test_read_absolute_escape_is_rejected(scope):
    outside = Path("C:/Windows/win.ini") if sys.platform == "win32" else Path("/etc/passwd")
    with pytest.raises(ToolError, match="越界"):
        files.read_file(scope, str(outside))


def test_read_missing_file(scope):
    with pytest.raises(ToolError, match="没有这个文件"):
        files.read_file(scope, "workspace/nope.md")


def test_read_directory_says_use_list(scope):
    with pytest.raises(ToolError, match="list_dir"):
        files.read_file(scope, "workspace")


def test_list_dir(scope):
    out = files.list_dir(scope, "workspace")
    assert "notes.md" in out


def test_list_dir_hides_dotfiles(pack: Path, scope: Scope):
    (pack / "workspace" / ".secret").write_text("x", encoding="utf-8")
    assert ".secret" not in files.list_dir(scope, "workspace")


def test_read_truncates_long_file(scope):
    out = files.read_file(scope, "workspace/notes.md", max_chars=5)
    assert "还有" in out


# ---------- 写 ----------


def test_write_only_into_workspace(scope, pack: Path):
    files.write_file(scope, "new.md", "内容")
    assert (pack / "workspace" / "new.md").read_text(encoding="utf-8") == "内容"


def test_write_tolerates_workspace_prefix(scope, pack: Path):
    files.write_file(scope, "workspace/new2.md", "内容")
    assert (pack / "workspace" / "new2.md").exists()
    assert not (pack / "workspace" / "workspace").exists()


def test_write_outside_workspace_is_rejected(scope, pack: Path):
    with pytest.raises(ToolError, match="越界"):
        files.write_file(scope, "../SOUL.md", "改掉")
    assert "陈建国" in (pack / "SOUL.md").read_text(encoding="utf-8")


def test_write_escape_is_rejected(scope):
    with pytest.raises(ToolError, match="越界"):
        files.write_file(scope, "../../escape.txt", "x")


def test_write_cannot_hit_workspace_root(scope):
    with pytest.raises(ToolError, match="不能覆盖"):
        files.write_file(scope, ".", "x")


def test_append_keeps_existing_content(scope, pack: Path):
    files.append_file(scope, "notes.md", "- 新加的一条")
    text = (pack / "workspace" / "notes.md").read_text(encoding="utf-8")
    assert "三行笔记" in text
    assert "- 新加的一条" in text
    assert text.index("三行笔记") < text.index("- 新加的一条")


def test_append_creates_missing_file(scope, pack: Path):
    files.append_file(scope, "todo.md", "买药")
    assert (pack / "workspace" / "todo.md").read_text(encoding="utf-8").strip() == "买药"


def test_append_rejects_empty(scope):
    with pytest.raises(ToolError, match="空的"):
        files.append_file(scope, "notes.md", "   ")


def test_append_escape_is_rejected(scope):
    with pytest.raises(ToolError, match="越界"):
        files.append_file(scope, "../SOUL.md", "x")


def test_edit_replaces_unique_block(scope, pack: Path):
    files.edit_file(scope, "notes.md", "第二行", "改过的第二行")
    assert "改过的第二行" in (pack / "workspace" / "notes.md").read_text(encoding="utf-8")


def test_edit_missing_block(scope):
    with pytest.raises(ToolError, match="找不到"):
        files.edit_file(scope, "notes.md", "不存在的句子", "x")


def test_edit_ambiguous_block(scope):
    files.write_file(scope, "dup.md", "a\na\n")
    with pytest.raises(ToolError, match="出现了 2 次"):
        files.edit_file(scope, "dup.md", "a", "b")


def test_edit_outside_workspace_is_rejected(scope):
    with pytest.raises(ToolError, match="越界"):
        files.edit_file(scope, "../SOUL.md", "陈建国", "别人")


# ---------- 命令 ----------


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 命令")
def test_run_command_runs_in_workspace(scope, pack: Path):
    files.write_file(scope, "hello.txt", "hi")
    out = shell.run_command(scope, "type hello.txt")
    assert "hi" in out


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 命令")
def test_run_command_timeout_kills(scope):
    with pytest.raises(ToolError, match="秒没跑完"):
        shell.run_command(scope, "ping -n 20 127.0.0.1 >nul", timeout=1.0)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows 命令")
def test_run_command_reports_failure_honestly(scope):
    with pytest.raises(ToolError, match="命令失败"):
        shell.run_command(scope, "exit 3")


def test_run_command_empty(scope):
    with pytest.raises(ToolError, match="空的"):
        shell.run_command(scope, "")


# ---------- 注册表 ----------


def test_unknown_tool(scope):
    tools = Tools(scope)
    result = tools.execute("delete_everything", {})
    assert not result.ok
    assert "没有这个工具" in result.output


def test_mutating_tool_denied_by_default(scope, pack: Path):
    tools = Tools(scope)
    result = tools.execute("write_file", {"path": "x.md", "content": "hi"})
    assert not result.ok
    assert "没有同意" in result.output
    assert not (pack / "workspace" / "x.md").exists()


def test_mutating_tool_allowed_when_confirmed(scope, pack: Path):
    tools = Tools(scope, confirm=lambda spec, args: True)
    result = tools.execute("write_file", {"path": "x.md", "content": "hi"})
    assert result.ok
    assert (pack / "workspace" / "x.md").exists()


def test_read_tool_needs_no_confirmation(scope):
    tools = Tools(scope)
    assert tools.execute("read_file", {"path": "workspace/notes.md"}).ok


def test_error_is_surfaced_not_faked(scope):
    tools = Tools(scope)
    result = tools.execute("read_file", {"path": "workspace/nope.md"})
    assert not result.ok
    assert result.as_content().startswith("失败：")


def test_schemas_are_openai_shaped():
    tools = Tools(Scope(Path("."), Path(".")))
    for schema in tools.schemas():
        assert schema["type"] == "function"
        assert schema["function"]["name"]
        assert schema["function"]["parameters"]["type"] == "object"


def test_calls_are_logged(scope):
    tools = Tools(scope)
    tools.execute("read_file", {"path": "workspace/notes.md"})
    assert tools.calls[-1][0] == "read_file"
    assert tools.calls[-1][2] is True
