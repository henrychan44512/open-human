# Open Human — Build Plan v2.0（beta 0.1）

> **这是唯一权威规划。** 上下文压缩后，先读这份，再读根目录 `AGENTS.md`。
>
> 这一份是**现状 + 必须记住的约束**，不是开发流水账。2026-10-26 → 10-29 的 37 节打磨记录
> （每次「为什么这么改」、每个坑怎么排的）原样归档在 **[docs/archive/BUILD-history.md](docs/archive/BUILD-history.md)**。
> 下面出现**本文件里没有的**编号（如 `§25.6`、`§30`、`§33.2`），都指归档里的那一节；
> `§11`、`§14` 这种则是本文件的节。

---

## 1. 一句话

打开一个人格文件夹，AI 以第一人称成为「他」。

像 opencode 打开一个项目文件夹那样：Open Human 打开 `humans/<slug>/`，把它接入人格，然后开始聊天。
数据全是 Markdown；没有数据库、没有账号、没有云。

---

## 2. 现在做什么 / 不做什么

**做**：Windows 10/11 桌面（Chrome/Edge 应用窗口 + Python runtime + 本地 MiniCPM5-2B）、
第一人称对话、Markdown 记忆卡检索（带引用）、终端风格界面、工作区受限的四个工具
（read / write / edit / bash）、用虚构 `humans/demo/` 开发和测试、整包 zip 分发（不是 exe）。

**不做**：人类数据整理 / 访谈 / OCR、接真实人类数据、手机端、语音 / TTS / 声音克隆、
多用户 / 登录 / 云同步、模型微调、关系透镜、打包成安装包（§16）、改 `authoring-kit/`。

---

## 3. 已锁定决策

| # | 决策 |
|---|---|
| D-01 | 一个文件夹 = 一个人：`humans/<slug>/`；Markdown 是唯一真实来源，runtime 只读 |
| D-02 | 第一人称；他知道自己是数位存在；不假设生死 |
| D-03 | 本地优先：MiniCPM5-2B Q4_K_M，**纯 CPU**；DeepSeek API 可切 |
| D-04 | 检索优先、工具其次；Python 编排，2B 只负责说话 |
| D-05 | 最低 8 GB RAM / 4 核 / Windows 10/11 |
| D-06 | 窗口是 **Chrome/Edge 应用模式**；Python 是 runtime；llama.cpp 是推理 |
| D-07 | Context 默认 8K；典型 prompt 2,600 tok |
| D-08 | UI：终端 + 极淡窗框 + 人味打字节奏；不做 3D / 人像 / 光球 |
| D-09 | 工具：read / write / edit / bash，只能碰 `workspace/` |
| D-10 | 精简：Python 核心约 4,300 行；无 LangChain / 向量库 / SQL / 前端框架 |
| D-11 | 检索：BM25 + jieba + 年份 + 人名；**文件就是数据库** |
| D-12 | Session：JSONL，`id + parentId` 树；可回放、可分支 |

---

## 4. 架构

```
Open Human.cmd（Windows）
 ├─ 建/修 .venv，起 llama-server（127.0.0.1:8080），轮询 /health
 ├─ 起 Python sidecar（uvicorn，127.0.0.1:8710）
 └─ 把「怎么开窗口」写成 data\window.cmd，由 cmd.exe 执行（§14）

Python sidecar（FastAPI，业务全在这里）
 ├─ Pack Loader      读 humans/<slug>/（按 mtime 缓存）
 ├─ Director         年份 / 人名 / 关键词 → 检索计划
 ├─ Retriever        BM25 + jieba → top-k 记忆卡（带覆盖率闸门）
 ├─ Context Assembler 按预算拼 prompt（persona → 历史 → 记忆 → 当前问题）
 ├─ Chat Engine      调 LLM、SSE 串流、收引用
 ├─ Session          JSONL 树
 └─ Tools            read / write / edit / bash（沙盒在 workspace/）

llama-server.exe（CPU）
 └─ MiniCPM5-2B-Q4_K_M.gguf，8K context，单 slot
```

**作者 / 运行分离**：作者阶段用第三方 agent 把数据整理成 `humans/<slug>/`；
运行阶段本 app 只读这个文件夹。两边只通过 Markdown 交接。

---

## 5. 目录布局

```
open_human/
├── 启动.bat                             # 双击入口：选 1B / 2B，然后交给 Open Human.cmd
├── Open Human.cmd                       # 真正的启动器：模型 + 服务 + 应用窗口（ASCII + CRLF）
├── 先读我.md                            # 解压后第一份该看的（三步起来 + 常见坑）
├── BUILD.md / AGENTS.md / README.md     # 规划 / 开发规则 / 使用者第一屏
├── CONTRIBUTING.md / CHANGELOG.md       # 上手规矩 / 版本变化
├── LICENSE                              # GPL-3.0
├── pyproject.toml / uv.lock / config.example.toml
├── assets/OpenHuman.ico                 # 桌面图标（7 个尺寸，脚本生成）
├── humans/demo/                         # 虚构人格包：human_data.md + workspace/
├── src/openhuman/                       # 32 个 .py / 4,285 行；server/static 8 文件 / 1,644 行
│   ├── cli.py                           # oh doctor / packs / chat / replay / serve / eval
│   ├── config / paths / doctor / localmodel / window / tokens / eval
│   ├── pack/        # schema / loader / humanfile（单文件解析）/ persona
│   ├── memory/      # index(BM25) / director / context / text
│   ├── llm/         # client(SSE) / prompt
│   ├── chat/        # session(JSONL 树) / engine
│   ├── tools/       # registry / files / shell
│   └── server/      # app(FastAPI+SSE) / state / static
├── tests/                               # 18 个 .py / 227 个用例；eval/questions.yaml 32 题
├── scripts/                             # env.ps1 / pack_beta / zip_tree / make_icon /
│                                        #   install_shortcut / launch.ps1（中文菜单）/
│                                        #   bench_llm / stress_chat / _fix_eol
├── docs/                                # benchmark.md + archive/（开发史）
├── authoring-kit/                       # 3 个文件的作者套件，冻结，不属于 runtime
├── vendor/                              # 便携工具链（gitignore）：git / python / uv / llama
├── models/                              # 权重（gitignore）1B 656 + 2B 1,489 MB
└── .venv/                               # 依赖（gitignore）
```

---

## 6. 人格包契约（runtime 只读）

```
humans/<slug>/
├── human.yaml          # slug / name / presence / last_record / first_line
│                       #   + sleep_line / wake_line / idle_line（三句自己起头的话）
├── SOUL.md             # 身份、语气、价值观
├── RULES.md            # 边界、不知道怎么说
├── timeline.md         # 一行一件事
├── people/*.md         # 关系人物
├── memories/**/*.md    # 记忆卡，带 front-matter（核心）
├── traits/speech.md    # 句法、称呼、禁语
├── voice/samples.md    # 逐字语气样本
└── workspace/          # 工具沙盒，唯一可写目录
```

记忆卡必填：`id` / `date` / `title` / `source` / `salience`；可选 `type` / `people` /
`places` / `emotion` / `confidence` / `tags`。**缺 `source` 的卡不进检索。**

### 6.1 单文件形态：一份 human_data.md 就是全部

上面那套目录是给写代码的人方便；**给「被蒸馏的那个人」，它是一堵墙**（要写 YAML、要按目录摆、
要知道 front-matter）。所以还有第二种形态 —— `humans/<slug>/` 里只放一份
**`human_data.md`**，parser 在 `src/openhuman/pack/humanfile.py`：

| 文件里的小节 | 变成什么 |
|---|---|
| `## 基本`（`名字：` `称呼：` `状态：` `最后一条：` + 四句台词） | `human.yaml` 的字段 |
| `## 我是谁` | `SOUL`（要 ≤300 字，否则超 persona 预算会警告） |
| `## 我怎么说话` | `traits/speech` |
| `## 我不会` | `RULES` |
| `## 记忆` 里每个 `### 年-月-日 标题` | 一张记忆卡（`id`/`date`/`source` 从标题推，**不用写 YAML**） |
| `## 人物` 里每个 `### 名字` | `people/`（`称呼：` / `关系：` 当字段） |
| `## 我常说的话` 里每个 `-` | `voice/samples` |

两条约定，其余尽量宽容（认不出的进 warnings，不吞）：

1. **`>` 开头的是写给人看的提示，不进内容**；代码块里的示例也不算。
2. 记忆卡没有日期 → 跳过并警告（**不能默认成 1 月 1 日**，那会让「哪一年」全部答错）。

- 模板：`humans/_template/human_data.md`（`_` 开头的目录不算一个人）。
- **文件夹名可以是中文**（`humans/我爸/`）；slug 规则见 `paths.check_slug`。
- 改名前的 `人类数据.md` 不再读；目录里还是旧名字时，报错直接说「改成 human_data.md」。
- 两种形态同时存在 → 用传统文件，并给一条 warning。
- **id 是「日期-标题」推出来的，标题写中文 id 就是中文**：`humans/demo/` 里是
  `2010-05-02-儿子结婚`。引用、`/api/humans/<slug>/cards/<id>` 都长这样，前端按 UTF-8 传。
- 校验：`oh doctor` 对两种形态一视同仁。

---

## 7. 技术栈

- **Python 3.12** + `uv`（便携，装在 `vendor/`）
- FastAPI + uvicorn、Pydantic v2、PyYAML + python-frontmatter、`rank-bm25` + `jieba`、
  httpx、Typer + Rich、pytest
- **前端**：原生 HTML / CSS / JS（无 React / Vue / Vite，**无构建步骤**）
- **推理**：llama.cpp 官方 CPU 版 `llama-server.exe`（b11889），MiniCPM5-2B-Q4_K_M
- 不引入：LangChain、LlamaIndex、Chroma、FAISS、SQLite、Docker、Node 构建链、Electron

---

## 8. 模型与上下文

```powershell
llama-server.exe -m models/MiniCPM5-2B-Q4_K_M.gguf -a MiniCPM5-2B `
  --host 127.0.0.1 --port 8080 -ngl 0 -t 8 -np 1 -c 8192 -fa on `
  --jinja --reasoning-format none
```

`-t` 取 `min(8, CPU 核数)`；`-c` 取 `config.toml` 的 `llama.context`。
**这串参数就是 `src/openhuman/localmodel.py:command()` 拼的；两边要一致。**

| 区块 | tokens |
|---|---|
| persona（SOUL + RULES + speech） | 700 |
| 工具 schema（默认关） | 0 / 300 |
| 检索记忆（3 张卡） | 400 |
| 时间线 / 人物切片 | 100 |
| 最近对话 | 900 |
| 当前问题 + 输出保留 | 100 + 400 |
| **合计** | **2,600** |

冷启动 ≈ 17 秒；开机预热后首轮 ≈ 4 秒；稳态首字 0.3–1.7 秒。

**稳定前缀**：persona 永远在最前且每轮相同 → 检索结果放**历史之后、当前问题之前**
（不能进 system，也不能放历史前面）→ `cache_prompt: true` → **只追加、不改前面**。

**回复长度**：日常 1–4 句、≤80 字；被追问 / 讲故事 ≤250 字；说「多说点」才展开。

---

## 9. 对话流程

```
load_pack → persona（≤700 tok，稳定不变）
  → director.plan（年份 / 人名 / 关键词；top-1 低于阈值就不注入记忆）
  → retriever.search（BM25，k=3）
  → context.fit（预算 400 tok，装不下裁最后一张）
  → 拼 messages：system=persona, history=最近 900 tok, memory=卡片, user=当前问题
  → llm.stream（SSE）→ session.append（user / 回复 / 引用 id）
```

- **引用**：SSE `meta` 事件带回本次检索到的 id；UI 显示「本次参考」，点开是卡片。
- **闸门**：闲聊不问往事就不翻记忆（`small_talk` / `about_past` / `follows_up`）。
- **他的钟**：每轮带当前时间；走开 ≥45 分钟回来他说 `wake_line`；沉默 3 分钟说一次 `idle_line`。

---

## 10. 界面（现状）

- 背景 `#0a0c0f`，暖白字，等宽字体；双层窗框 + 上下暗角（像有厚度的窗）。
- **三层光**：冷（窗外）在上、暖（屋里）在下，鼠标移动时按不同幅度错开 —— 这是「纵深」。
- **天光**：`body[data-phase]` 按小时切 dawn / day / dusk / night，几组光只差几个百分点。
- 打字：短句快长句慢，标点后停 120–250 ms，偶尔打错再删；他说话时输入行不抢。
- 记忆卡打开时屋子**退到后面**（模糊 + 压暗 + 幕），卡片是翻出来的一张纸。
- 工具开关在 `/settings`；页脚有版本号（`v0.1.0 · beta`）。
- 页面：`/`（列表）· `/chat/<slug>`（直接开在他身上）· `/settings`。
- 全部 CSS + Canvas 2D，没有 WebGL / Three.js / React / Vite。

---

## 11. 硬约束 N-01…N-06（Phase 0 实测，已锁定）

| # | 约束 | 为什么 |
|---|---|---|
| **N-01** | `cache_prompt: true`，prompt **只追加、不改前面** | 前面改一个字符，后面全部重算 |
| **N-02** | 开机预热：加载人格包后先发一个极短请求，把 persona 灌进缓存，藏在启动动画后面 | 没有它，每次开 app 第一句要等 **8 秒** |
| **N-03** | 记忆块放**历史之后、当前问题之前**，3 张卡、≤400 tok | 每轮只重算 ~400 tok ≈ 3 秒 |
| **N-04** | 裁历史 = 一次重算（3–4 秒）；要少裁、一次裁多轮 | 每轮裁一点最贵 |
| **N-05** | 每请求带 `chat_template_kwargs: {"enable_thinking": false}`，并剥掉 thinking 前缀 | 不然他会把思考过程念出来 |
| **N-06** | 默认回复 **≤80 字** | decode 17 tok/s：80 字≈6 秒，250 字≈15–20 秒 |

Phase 0 实测（完整数据在 `docs/benchmark.md`）：冷 prefill 120–150 tok/s（3,500 tok = 29 s）；
暖 prefill TTFT 0.1–0.2 s；decode 16–17 tok/s；8K context 占 2.65 GB；模型加载 1.9 s。

---

## 12. 已知短板与实测数字（2026-10-29）

| 项 | 数字 |
|---|---|
| 测试 | **227 passed**（15–25 秒） |
| 模型 | 1B 656 MB / 2B 1,489 MB，两份 Q4_K_M 都随包发，双击时选 |
| 检索 | 25/25 命中、top-1 24/25；资料外 7 条里 6 条不编 |
| persona | 546 tok / 预算 700（`humans/demo/`，估算） |
| 真机首字 | 0.31–1.68 s；预热 3.4 s |
| 连续 20 轮 | 0 失败（76 秒） |

**2B 自己的四个短板（不是代码问题）**：会把你问的话复述一遍再答；岁数算不对（念念 2013 年生，
问「孙女多大」答「十岁」）；情绪句接得冷（「我想你了」→「嗯。」）；偶尔一口气念 153 字的卡片。

代码层面的余量已见底；下一步的收益只能来自**换更大的模型**或**接真实数据**。
逐条文字例子见根目录 `README.md`「已知短板」。

---

## 13. 验收与测试

```powershell
.venv\Scripts\python.exe -m pytest          # 227 passed
.venv\Scripts\python.exe -m openhuman.cli doctor
.venv\Scripts\python.exe -m openhuman.cli eval demo
```

v1 的 7 条成功标准：① 双击能聊 ✅ ② 连续 20 轮不崩 ✅ ③ 30 条已知事实 ≥80% 命中
⚠️（检索达标、作答受 2B 限制）④ 资料外不编日期人名 ⚠️（6/7）⑤ 4 核首字 <3 秒 ✅
⑥ 工具只碰 `workspace/` ✅ ⑦ 安装包在 8 GB 机器能跑 ❄️（冻结，见 §16）。

---

## 14. 环境与坑（每一条都真踩过）

| 现象 | 原因 | 对策 |
|---|---|---|
| 双击只有黑窗口，没有界面 | 从 python 进程里拉 Chromium，1–2 秒内被杀软杀掉 | 窗口交给 **cmd.exe** 当父进程（python 只写 `data\window.cmd`） |
| Electron 起不来 | 6 行最小应用崩在 Chromium 初始化 `0x80000003`；换版本、计划任务、进程树外启动都一样 | 改用 Chrome/Edge `--app` 应用窗口 |
| WebView2 同样崩 | `msedgewebview2.exe` 崩在 `msedge_elf.dll`，异常码**一模一样** `0x80000003` | 彻底放弃：它的浏览器进程必须是宿主子进程，绕不开 cmd.exe 那条路 |
| `.cmd` 里写中文报 `'xx' is not recognized` | cmd.exe 按 OEM 代码页读批处理 | `.cmd` / `.bat` **只能 ASCII + CRLF**；中文输出交给 Python |
| `.ps1` 里的中文变乱码 | Windows PowerShell 5.1 没有 BOM 时按 ANSI(cp936) 读 | `.ps1` 必须带 **UTF-8 BOM**（编辑工具改过之后 BOM 会掉，要补） |
| `oh doctor > log.txt` 崩出一段 traceback | cp936 编不出 `✓`；重定向时 errors=strict | 非终端按 UTF-8 写，终端只把编码错误降级成替换符 |
| 窗口用久了 `data/window` 涨到 158 MB | Chrome 往 profile 里屯组件（优化模型 40 / crx 32.6 / WasmTts 24.5 / SafeBrowsing 19.1） | `--disable-component-update` 等四个开关；现在稳定 ~20 MB |
| 桌面快捷方式显示默认图标 | ICO 的 `ICONDIRENTRY.planes` 写成 0（规范要 1）；资源管理器不容错 | 按规范手工拼 ICO（`scripts/make_icon.py`），生成后自检 |
| 换台机器 / 搬目录后双击没反应 | `.venv\pyvenv.cfg` 的 `home` 是**绝对路径** | `Open Human.cmd` 的 `:fixvenv` 每次启动重写（小于 20 字节不替换） |
| 搬目录后 `import openhuman` 失败（界面打不开） | `uv sync` 的 editable 安装把**源路径**写进 `.venv\Lib\site-packages\_editable_impl_openhuman.pth`，也是绝对路径 | `:fixvenv` 一并把它改成 `..\..\..\src`：从 site-packages 往上三级正好是项目根 |
| `env.ps1` 和 `:fixvenv` 选中的解释器不一致 | 曾有两份同名 Python；一个取第一个匹配、一个取最后一个 | **`vendor\python\` 下只放一份解释器** |
| `pytest-of-henry/` 出现在仓库根，几百个文件 | 这台机器的 `%TEMP%` 对 Python 不可用：建临时文件会卡住，`tempfile` 于是退到 cwd | `tests/conftest.py` 把 `tempfile.tempdir` 钉在 `data/pytest-tmp/`；`pytest-of-*/` 也仍旧 gitignore |
| 加了 Typer callback 之后 `--version` 退出码 2 | group 拒绝「没有子命令」的调用 | `invoke_without_command=True` + 自己打印 help |

---

## 15. 体积与文件（2026-10-29 实测）

仓库 **2,493 MB**（`dist/` 平时是空的：交付包现打现给，见 §16）：

| 项 | 体积 |
|---|---|
| `models/` 权重（1B 656 + 2B 1,489） | 2,145 MB |
| `vendor/`（git 91.8 / python 51.4 / llama 43.5 / uv 31.1；**git 不进包**） | 217.8 MB |
| `.venv/`（numpy 21.6 是 `rank_bm25` 硬要的） | 110.4 MB |
| `data/`（jieba 缓存 8.8；Chrome profile 只在 app 开着时存在） | 8.9 MB |
| `.git/` | 9.0 MB |
| `docs/`（含归档 37 节） | 0.12 MB |
| 源码 + 测试 + 人格包 + 图标 + 脚本（**进 git 的只有 92 个文件 / 750 KB**） | ~1 MB |

`data/` 是运行时状态，**可以整个删掉**（会话记录除外）；`data/window/` 是 Chrome profile，
app 开着时会一直长，不进包；`data/pytest-tmp/` 是测试的临时根（这台机器的 `%TEMP%`
不可用，见 §14）。

---

## 16. 分发与打包

**没有安装包，也不做 exe。** 用户原话：「绝对不需要打包成 exe，直到开发成熟完成后，才打包」（归档 §24）。
冻结期间不许装 PyInstaller / electron-builder / nsis，不许为打包改代码。
**分发形态：整包 zip，解压即用。**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\pack_beta.ps1 -DryRun   # 先看清单
powershell -ExecutionPolicy Bypass -File scripts\pack_beta.ps1           # 真打
```

- 排除：`.git` / `data/` / `dist/` / `__pycache__` / `.pytest_cache` / `*.log` /
  `config.toml`（可能含 key）/ `pytest-of-*` / **`vendor\git`**（91.8 MB 的便携 git，
  runtime 一次都不调，只给开发用）。通配符按**路径每一段**匹配，不只按文件名。
- 清单由 `.ps1` 算（`-DryRun` 只打印），压缩交给 **`scripts/zip_tree.py`**：
  打完自己读回来，必含 LICENSE / README / 权重 / `llama-server.exe` / `human_data.md` 模板，
  缺一项就退出 1。
- **不能用系统自带 `tar.exe`**：bsdtar 按 OEM 代码页处理文件名，`humans/我爸/human_data.md`
  进包后是 cp936 字节、UTF-8 标志位没设（别的机器解出来是乱码），连 `-T` 清单里带一个中文路径
  都报 `Couldn't visit directory`。Python 的 `zipfile` 写 UTF-8 并置 flag bit 11；
  已压缩的容器（.zip/.gz/.7z）直接 store，其余 deflate 6。中文文件名有测试：`tests/test_ziptree.py`。
- **仓库里不存 zip。** 需要交付时现场打，80 秒 → `dist\open-human-0.1.0-beta.zip`
  （约 4,887 条 / 1.55 GB）。交给别人：解压到任意目录 → 双击 `Open Human.cmd` →（可选）
  `powershell -ExecutionPolicy Bypass -File scripts\install_shortcut.ps1` 摆个桌面图标。
- **什么时候算「成熟」**（判断权在用户）：跑真实人格包、连续几天不出戏不崩、
  工具真帮上忙且没出事故、界面手感定了、用户自己说可以了。

---

## 17. 历史与归档

- **[docs/archive/BUILD-history.md](docs/archive/BUILD-history.md)** —— 2026-10-26 → 10-29
  的 37 节完整开发记录：Phase 0–5 的实现与验收、六轮打磨、收尾清理、窗口排查、
  beta 收尾、WebView2 证否、切包与体检。**要查「当时为什么这么改 / 那个坑怎么排的」去这里。**
- **[docs/benchmark.md](docs/benchmark.md)** —— Phase 0 的速度 / 内存实测（§11 的数字来源）。
- 访谈记录（`docs/history/`）和过期截图（`docs/screens/`）在 beta 收尾时删掉了；要找回看 git 历史。
- 旧节号与本文件的对应用表在 **[docs/README.md](docs/README.md)**（代码注释里还会遇到 `§N`）。
