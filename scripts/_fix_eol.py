"""把启动器写成 cmd.exe 和 Windows PowerShell 5.1 能正确读取的样子。

- `启动.bat`：纯 ASCII + CRLF —— cmd.exe 按 OEM 代码页读批处理文件
- `scripts\\launch.ps1`：UTF-8 **带 BOM** + CRLF —— PS 5.1 没 BOM 会按 GBK 读中文

改完这两个文件跑一次：`.venv\\Scripts\\python.exe scripts\\_fix_eol.py`
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# (路径, 编码, 要不要 BOM)
TARGETS = [
    (ROOT / "\u542f\u52a8.bat", "ascii", False),
    (ROOT / "Open Human.cmd", "ascii", False),
    (ROOT / "scripts" / "launch.ps1", "utf-8", True),
]


def main() -> None:
    for path, encoding, bom in TARGETS:
        text = path.read_text(encoding="utf-8-sig")
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\r\n")
        if encoding == "ascii":
            text.encode("ascii")  # 明确报错：别把中文写进批处理
            path.write_text(text, encoding="ascii", newline="")
        else:
            path.write_text(
                text, encoding="utf-8-sig" if bom else "utf-8", newline=""
            )
        print(f"{path.name}: CRLF, {'utf-8-sig' if bom else encoding}")


if __name__ == "__main__":
    main()
