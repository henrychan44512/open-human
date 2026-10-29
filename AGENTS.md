# AGENTS.md — 开发规则

## 先读

1. `BUILD.md`（唯一权威规划）
2. 本文件
3. `docs/README.md`（说明哪些是历史文档）

## 项目状态

Phase 0–5 完成，beta v0.1 已收尾；现在处于打磨期 —— 补洞、调手感、接真实数据，不加新框架。
现状数字（227 个用例、仓库体积、persona 用量）都在 `BUILD.md` §12 与 §15，**以那里为准**；
过程记录在 `docs/archive/BUILD-history.md`。

## 做事方式

- **一次只做一个 Phase；到验收就停。**不通过验收，不进下一步。
- 动手前先说明：要改哪些文件、为什么。
- 小文件优先，单文件 < 300 行；一个模块一个职责。
- 不加新依赖，除非先说明理由并等确认。
- 不引入 LangChain、向量数据库、SQL、Docker、前端框架。
- Windows + PowerShell；路径用 `pathlib`。Python 3.12；类型标注；Pydantic v2。
- 每个模块配 pytest；用 `tests/fake_llm.py` 做不依赖真模型的集成测试。

## 禁止

- **打包。** 不装 PyInstaller / electron-builder，不生成 exe、不写安装包。
  用户明确要求开发成熟之前不打包，解冻要先问。见 `BUILD.md` §16。
- 改 `authoring-kit/`（冻结）。
- 接真实人类数据（用 `humans/demo/` 的虚构数据开发和测试）。
- 自动进入下一个 Phase。
- 大重构、过度抽象。
- 把逻辑写进窗口/壳里。窗口只是壳，业务全在 Python。
- 把 API key 写进代码，或让 `/api/settings` 之类把 key 发给前端。

## 常用命令

```powershell
. scripts/env.ps1          # 每个新终端先跑这个：PATH + uv 环境变量
uv sync
uv run oh doctor
uv run oh chat demo
uv run oh serve            # Web 界面 http://127.0.0.1:8710；顺手拉起模型
uv run oh eval demo
uv run pytest
```

执行策略挡 `env.ps1` 的时候（`.. 禁止运行脚本`），直接用 venv 里的解释器：

```powershell
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m openhuman.cli serve --no-open
```

窗口是 **Chrome/Edge 的应用模式**，不是 Electron，而且必须由 **cmd.exe 当父进程**开
（python 只把启动行写成 `data/window.cmd`）—— 从 python 进程里拉浏览器会被杀软在 1–2 秒内杀掉。
见 `BUILD.md` §14。想退回普通标签页用 `oh serve --browser`。工具链都是便携版，在 `vendor/` 下，不进系统。

## 编码红线

**不要在 PowerShell 命令里写中文再落盘。** `Get-Content | Set-Content` 会经过一次
GBK 往返，把中文注释变成乱码；乱码仍是合法 UTF-8，所以不报错，但被破坏的字符串
（比如 `core.js` 里的标点键名）会让整个前端白屏。

- 改带中文的文件，只用编辑工具，不用 shell 管道。
- 改完 JS 跑 `node --check <file>`。
- `pytest` 里有 `test_static_files_are_clean_utf8` 兜底。

**`.cmd` / `.bat` 只能是 ASCII + CRLF。** cmd.exe 按 OEM 代码页读批处理文件，
UTF-8 中文会被读成乱码命令，报一堆 `'xx' is not recognized`；LF 换行也会让解析错位。
中文输出交给 Python（配合 `chcp 65001`），批处理里只写英文。

全项目只有两份批处理，都守这条：`启动.bat`（双击入口，只有一层菜单壳）和
`Open Human.cmd`（真正的启动器，修 `pyvenv.cfg` + 拉窗口 + 跑服务）。中文菜单写在
`scripts\launch.ps1` 里 —— **`.ps1` 必须 UTF-8 带 BOM**，否则 PS 5.1 按 GBK 读，
中文全糊。改完这两个文件跑一次 `scripts\_fix_eol.py` 把 BOM 和 CRLF 补回去。

## 已锁定的实现约束

- `BUILD.md` §11 的 N-01…N-06（prefix cache、开机预热、记忆块位置、裁历史代价、关 thinking、
  短回复）。写代码前先读那一节，不要凭直觉改。
- **`vendor\python\` 下只放一份解释器。** 曾经有两份同名版本，`env.ps1` 取第一个、
  `Open Human.cmd` 取最后一个，靠版本相同才没出事（归档 §37.2）。
- `data/` 是运行时状态，可以随时整个删掉（会话记录除外）；`data/window/` 是 Chrome profile，
  app 开着时会一直长，不进包。
- 人格包有**两种形态**：多文件（`human.yaml` + `SOUL` + `RULES` + `memories/`）和**单文件**
  `human_data.md`（parser 在 `pack/humanfile.py`，模板在 `humans/_template/`）。
  改 loader / 检索 / 界面时两种都要顾到；测试在 `tests/test_humanfile.py`。
- 根目录 `README.md` 是**给使用者看的**（怎么装、怎么用、为什么不是 Electron、2B 的短板）。
  改启动方式 / 改界面 / 换模型时要顺手核对它 —— 它是 beta 的第一屏。

## 不确定时

问一个具体问题，不要猜。
