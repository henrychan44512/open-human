# CONTRIBUTING

这个项目是 Windows 上一人维护的 beta。下面几条比通常的开源项目**硬**一些，先说清楚。

## 先读

1. [`README.md`](README.md) —— 它是什么、怎么用
2. [`AGENTS.md`](AGENTS.md) —— 开发规矩，尤其是「编码红线」和「禁止」两节
3. [`BUILD.md`](BUILD.md) —— 唯一权威规划：架构、硬约束、体积、已知短板

## 环境

```powershell
uv sync                 # 依赖
. scripts/env.ps1       # 每个新终端先跑：PATH + uv 变量
uv run oh doctor
```

执行策略挡住 `env.ps1` 时直接用解释器：`.venv\Scripts\python.exe -m pytest`。

## 测试

```powershell
.venv\Scripts\python.exe -m pytest     # 227 个用例，约 25 秒
```

全部用 `tests/fake_llm.py`，**不需要模型、不需要网、不需要显卡**。改后端或改提示词时
先跑一遍全绿，再看实际手感。

## 改代码时

- **一次一个小改动。**先说要改哪些文件、为什么，再动手。
- **不加依赖**，除非先说理由。不引入 LangChain / 向量库 / SQL / Docker / 前端框架。
- **不打包。**不装 PyInstaller / electron-builder，不生成 exe、不写安装包 —— 见 `BUILD.md` §16。
- 单文件 < 300 行，一个模块一个职责；路径用 `pathlib`，类型标注，Pydantic v2。
- **人格包有两种形态**（多文件 `human.yaml` + 单文件 `human_data.md`），改 loader / 检索 /
  界面时两种都要顾到，测试在 `tests/test_humanfile.py`。
- 动 `src/openhuman/server/static/` 下的 JS，改完跑 `node --check <file>`。

## 编码红线

- **不要用 PowerShell 管道写中文。**`Get-Content | Set-Content` 会走一次 GBK 往返，
  把中文注释变成乱码；乱码仍是合法 UTF-8，所以不报错，但会让前端白屏。改带中文的文件
  只用编辑器。
- **`.cmd` / `.bat` 只能是 ASCII + CRLF。**cmd.exe 按 OEM 代码页读批处理，中文会被读成
  乱码命令。`Open Human.cmd` 是唯一一份。
- `.ps1` 需要 UTF-8 BOM（`Windows PowerShell 5.1` 的坑）。

## 提改动

- 说清楚**为什么**，不只是做了什么；行为有变化就顺手改 `CHANGELOG.md` 的未发布一节。
- 动启动方式 / 界面 / 模型时顺手核对 `README.md` —— 它是第一屏。
- 不加新文档；能写进现有小节的就写进现有小节。

## 提 issue

带上：`oh doctor > log.txt` 的输出、`data/llama.log`、`data/window.log`，
以及模型后端是本地还是 DeepSeek。

## 许可

提交即表示同意以 **GPL-3.0** 发布，见 [`LICENSE`](LICENSE)。
