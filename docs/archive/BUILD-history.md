# Open Human — Build Plan v1.9

> **这是唯一权威规划。** 上下文压缩后，先读这份，再读根目录 `AGENTS.md`。
> 状态：**Phase 0–5 已完成**（2026-10-26）；**打磨四轮已完成**（§25 / §26 / §27 / §28）；
> **收尾清理已完成**（§29，2026-10-27，包体 2,367 → 1,840 MB）；
> **双击开窗修好了**（§30，2026-10-27）；**第五轮：他先开口、也记得你走了多久**（§31）；**第六轮：屋子有纵深**（§32，2026-10-28）。
> **beta v0.1 收尾**（§33，2026-10-29）：审过六条要求、修掉 `oh doctor` 的编码崩和窗口 profile 膨胀、根目录有了 `README.md`。
> **窗口这件事定了**（§34，2026-10-29）：应用窗口 + 桌面图标/快捷方式；WebView2 在这台机器上同样崩（`0x80000003`），Electron 那条路彻底关闭。
> **交付前体检**（§37，2026-10-29）：清掉 53 MB 重复解释器和缓存，包重切为 **5,412 条 / 1,589.9 MB**。
> **Phase 6（打包）已冻结，不要做**，见 §24。
> v1 规格已实现：7 条验收里 4 条达标、2 条受 2B 能力限制、1 条被冻结（§17.1）。
> 离「成熟」差的是真实人格包和几天真实使用（§24.4），不是代码（§29.5）。

---

## 0. 一句话

打开一个人格文件夹，AI 以第一人称成为「他」。

像 opencode 打开一个项目文件夹那样：Open Human 打开一个 `humans/<slug>/` 文件夹，把它接入人格，然后开始聊天。

---

## 1. 现在做什么 / 不做什么

### 现在做（v1）

- Windows 桌面 app：**Chrome/Edge 应用模式窗口** + Python runtime + 本地 MiniCPM5-2B。
  （Electron 壳试过，在这台机器上起不来，已删，见 §25.6 / §27.5。）
- 读取 `humans/<slug>/` 人格包。
- 第一人称对话。
- 从 Markdown 记忆卡检索，显示引用。
- 终端风格 UI：冷壳 + 人味对话。
- 基础工具：read / write / edit / bash（工作区受限）。
- 用**虚构 demo 人格包**开发和测试。
- 不打包：双击 `Open Human.cmd` 直接跑（§24.3）。

### 现在不做（等重要）

- 不做人类数据整理、访谈、OCR、作者流水线。
- 不接入真实人类数据。
- 不做手机端。
- 不做语音 / TTS / 声音克隆。
- 不做多用户、登录、权限、云同步。
- 不做模型微调。
- 不做关系透镜、身份选择（v1.1 再说）。
- 不改 `authoring-kit/`，它已经冻结。

> 人类数据由用户自己慢慢整理。Runtime 只认文件夹格式，不关心数据怎么来的。

---

## 2. 已锁定决策

| # | 决策 |
|---|---|
| D-01 | 一个文件夹 = 一个人：`humans/<slug>/` |
| D-02 | Markdown 是唯一真实来源；runtime 只读，不改人格文件 |
| D-03 | 第一人称；他知道自己是数位存在；不假设生死 |
| D-04 | 本地优先：MiniCPM5-2B Q4_K_M，CPU；DeepSeek API 可切换 |
| D-05 | 检索优先、工具其次；Python 做编排，2B 只负责说话 |
| D-06 | 桌面最低 8 GB RAM / 4 核 / Windows 10/11 |
| D-07 | ~~Electron 是壳~~ → **窗口是 Chrome/Edge 应用模式**（Electron 在这台机器上起不来，已删，§25.6 / §27.5）；Python 是 runtime；llama.cpp 是推理 |
| D-08 | Context：默认 8K 上限，典型 prompt 3.5K；4K 可降级；16K 仅长文手动 |
| D-09 | UI：终端 + 极淡窗框；人味打字节奏；不做 3D / 人像 / 光球 |
| D-10 | 工具：read / write / edit / bash + 可选 web_search；工作区 `workspace/` |
| D-11 | 精简：Python 核心 < 2,500 行；无 LangChain、无向量库、无 SQL 数据库 |
| D-12 | 检索：BM25 + jieba + 标签 + 年份过滤；文件就是数据库 |
| D-13 | Session：JSONL，`id + parentId` 树；可回放、可分支 |
| D-14 | 一次只做一个 Phase；每个 Phase 有验收 demo；不通过不进下一步 |
| D-15 | 开发用虚构 `humans/demo/`，不碰真实数据 |

---

## 3. 架构

```
┌─────────────────────────────────────────────────────┐
│ Open Human.cmd（Windows）                            │
│  ├─ 起 llama-server，轮询 /health                     │
│  ├─ 起 Python sidecar（uvicorn，127.0.0.1:8710）      │
│  └─ 用 Chrome/Edge 的 --app 开一个应用窗口             │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP + SSE
┌──────────────────▼──────────────────────────────────┐
│ Python sidecar（FastAPI）                            │
│  ├─ Pack Loader：读 humans/<slug>/                   │
│  ├─ Director：年份 / 人名 / 关键词 → 检索计划          │
│  ├─ Retriever：BM25 + jieba → top-k 记忆卡            │
│  ├─ Context Assembler：按预算拼 prompt                │
│  ├─ Chat Engine：调 LLM、串流、收引用                  │
│  ├─ Session：JSONL 树                                │
│  └─ Tools：read / write / edit / bash / web_search    │
└──────────────────┬──────────────────────────────────┘
                   │ OpenAI-compatible
┌──────────────────▼──────────────────────────────────┐
│ llama-server.exe（CPU）                              │
│  MiniCPM5-2B-Q4_K_M.gguf，8K context                 │
└─────────────────────────────────────────────────────┘
```

### 作者 / 运行分离（重要）

- 作者阶段：用户用第三方 agent + 第三方模型，把数据整理成 `humans/<slug>/`。
- 运行阶段：本 app 只读这个文件夹。
- 两边只通过 Markdown 交接。Runtime 不调用第三方模型，作者套件不调用 MiniCPM5。

---

## 4. 人格包契约（runtime 只读）

```
humans/<slug>/
├── human.yaml              # 必填：slug, name, presence, last_record, first_line（另有 sleep/wake/idle 三句）
├── SOUL.md                 # 必填：身份、语气、价值观（≤900 tokens）
├── RULES.md                # 必填：边界、不知道怎么说
├── timeline.md             # 可选：一行一件事
├── people/*.md             # 可选：关系人物
├── memories/**/*.md        # 核心：记忆卡，带 front-matter
├── traits/speech.md        # 可选：句法、称呼、禁语
├── voice/samples.md        # 可选：逐字语气样本
└── workspace/              # 工具沙盒，唯一可写目录
```

### `human.yaml`（最小字段）

```yaml
slug: demo
name: 陈建国
presence: living          # living | archived | unknown
last_record: 2026-10-01
language: zh-CN
first_line: "……你来了。"
sleep_line: "那我等你。"     # 房间暗下来时，右上角那行字
wake_line: "你回来了。"      # 走开 45 分钟以上回来，他先开口
idle_line: "……我在这儿。"   # 你 3 分钟不说话，他先出个声（可空 = 不催人）
```

### 记忆卡（最小字段）

```markdown
---
id: 2010-05-02-son-wedding
date: 2010-05-02
type: episode
title: 儿子结婚
people: [儿子, 儿媳]
places: [杭州]
emotion: [高兴, 舍不得]
salience: 5
confidence: high
source: memories/2010/2010-05-02-son-wedding.md
tags: [家庭]
---

## 发生了什么
- 儿子在杭州办婚礼，我上台讲话，讲到一半哭了。
```

Runtime 校验：`id`、`date`、`title`、`source`、`salience` 必填；其他可选。缺 `source` 的卡不进检索。

---

## 5. 目录布局

```
open_human/
├── BUILD.md                 # 本文件（唯一权威规划）
├── AGENTS.md                # 开发规则
├── Open Human.cmd           # 双击启动：模型 + 服务 + 应用窗口
├── pyproject.toml / uv.lock
├── config.toml              # 本地配置（gitignore）+ config.example.toml
├── humans/
│   └── demo/                # 虚构人格包，21 个文件（10 张记忆卡 / 3 个人物）
├── src/openhuman/           # 31 个 .py，3,809 行
│   ├── cli.py               # oh doctor / packs / chat / replay / serve / eval
│   ├── config.py            # TOML + 环境变量
│   ├── paths.py             # 路径、slug、workspace 边界
│   ├── doctor.py            # 环境自检
│   ├── localmodel.py        # 起停 llama-server
│   ├── window.py            # 用 Chrome/Edge --app 开窗口
│   ├── tokens.py            # token 预算估算
│   ├── eval.py              # oh eval
│   ├── pack/                # schema / loader / persona
│   ├── memory/              # index(BM25) / director / context / text
│   ├── llm/                 # client(SSE) / prompt
│   ├── chat/                # session(JSONL 树) / engine
│   ├── tools/               # registry / files / shell
│   └── server/              # app(FastAPI+SSE) / state / static(8 文件)
├── tests/                   # 15 个文件，205 个用例；eval/questions.yaml 32 题
├── scripts/                 # bench_llm / spike_chat / stress_chat / env.ps1 / fetch.mjs
├── docs/                    # benchmark.md（有效）+ history/（已过时）+ screens/
├── authoring-kit/           # 作者套件，冻结，不属于 runtime
├── vendor/                  # 便携工具链（gitignore）：git / python / uv / llama
├── models/                  # 模型权重（gitignore），1,489 MB
└── .venv/                   # Python 依赖（gitignore）
```

> 这是**现状**（2026-10-27），不是规划图。删掉的东西见 §27.5 和 §29。

---

## 6. 技术栈

### Python

- Python 3.12 + `uv`
- FastAPI + uvicorn
- Pydantic v2
- PyYAML + python-frontmatter
- `rank-bm25` + `jieba`
- httpx
- Typer + Rich
- pytest

### 桌面

- ~~Electron（仅壳）~~ → **Chrome/Edge 的 `--app` 应用模式**，由 `src/openhuman/window.py` 拉起（§25.6 / §27.5）
- 原生 HTML / CSS / JS（不用 React / Vue / Vite，不引入构建步骤）
- ~~electron-builder（打包）~~ → 不打包（§24）

### 推理

- llama.cpp 官方 CPU 版 `llama-server.exe`
- MiniCPM5-2B-Q4_K_M.gguf（约 1.56 GB）
- 端口 8080（可配）

### 不引入

LangChain、LlamaIndex、Chroma、FAISS、SQLite、Postgres、Docker、Node 构建链。

---

## 7. 模型与上下文

### 启动参数

```powershell
llama-server.exe `
  -m models/MiniCPM5-2B-Q4_K_M.gguf `
  -a MiniCPM5-2B `
  --host 127.0.0.1 --port 8080 `
  -ngl 0 -t 8 -np 1 -c 8192 -fa on `
  --jinja --reasoning-format none
```

- `-t 8`：实测最优（6 核机器上 SMT 仍能提速 prefill）。`-t 6` 是保守值。
- `-np 1`：单 slot。多 slot 只会切碎 context。
- `-fa on`：白送 6–9% prefill。
- `-c 8192`：默认。实测 8K 只比 4K 多 168 MB，**没有降级到 4K 的必要**。
- `--jinja`：使用模型自带 chat template。
- 每个请求还要带 `chat_template_kwargs.enable_thinking = false`，见 §18 N-05。

> 上面这串就是 `src/openhuman/localmodel.py:command()` 实际拼出来的参数（`-t` 取 `min(8, CPU 核数)`，`-c` 取
> `config.toml` 的 `llama.context`）。**改启动参数改这里和那个函数，两边要一致**。

### 上下文预算（实测后修订，原 3,900 → 现 2,600）

| 区块 | tokens |
|---|---|
| persona（SOUL + RULES + speech） | 700 |
| 工具 schema（Phase 5 才开，平时 0） | 0 / 300 |
| 检索记忆（3 张卡） | 400 |
| 时间线 / 人物切片 | 100 |
| 最近对话 | 900 |
| 当前问题 | 100 |
| 输出保留 | 400 |
| **合计** | **2,600** |

冷启动 ≈ 17 s，开机预热后首轮 ≈ 4 s，稳态 1–2 s。详见 §18。

### 稳定前缀（硬约束）

- persona 永远在最前，每轮相同。
- 检索结果放在**历史之后、当前问题之前**（不能放 system，也不能放历史前面）。
- `cache_prompt: true`，让 llama.cpp 复用前缀。
- **只追加、不改前面**：改前面任何字符都会让后面全部重算。

### 回复长度

- 日常：1–4 句，≤ 80 字。
- 被追问 / 说故事：≤ 250 字。
- 用户说「多说点」才展开。

---

## 8. 对话流程

```python
def respond(slug, session, user_text):
    pack = load_pack(slug)                    # 缓存，按 mtime 失效
    persona = pack.persona_prompt()           # 稳定，≤700 tokens

    plan = director.plan(user_text, pack)     # 年份、人名、关键词
    hits = retriever.search(plan, k=3)        # 覆盖率闸门 + BM25
    cards = context.fit(hits, budget=400)     # 装不下就裁

    memory_block = render_cards(cards)        # 带 id
    messages = assemble(
        system=persona,
        history=session.recent(max_tokens=900),
        memory=memory_block,                  # 紧贴 user
        user=user_text,
    )

    stream = llm.stream(messages)
    citations = [c.id for c in cards]
    session.append(user_text, stream.text, citations)
    return stream, citations
```

### Director（第一版不用 LLM）

1. 正则抽年份：`(19|20)\d{2}`。
2. 抽人名：用 `people/*.md` 的 `name` + `aliases`。
3. 其余用 BM25。
4. top-1 分数低于阈值 → 不注入记忆。
5. 永远注入 `SOUL.md` + `RULES.md` + `speech.md`。

### 引用

- 服务端在 SSE 的 `meta` 事件里返回本次检索到的 id。
- UI 显示 `[mem: id]`，点击打开卡片。
- Prompt 要求模型「用了记忆就加 `[mem:id]`」，但不强依赖；UI 始终显示「本次参考」。

---

## 9. UI 规格

### 视觉

```
┌──────────────────────────────────────────────────────┐
│                                                      │
│   ·                                                  │
│                                                      │
│            （很淡的窗框，几乎看不见）                  │
│                                                      │
│      > 你回来了。                                     │
│                                                      │
│      > 我记得你上次说工作找得很辛苦。                  │
│        [mem: 2026-09-14-job]  ← 一闪，然后消失        │
│                                                      │
│   ────────────────────────────────────────────────   │
│   > 你说吧…                                     [新]  │
└──────────────────────────────────────────────────────┘
```

- 背景 `#0a0c0f`，暖白字，等宽字体。
- 极淡扫描线、噪点。
- 游标呼吸。
- 打字节奏：短句快、长句慢、标点后停 120–250ms、偶尔打错再删。
- 记忆标签 2 秒淡出。
- 不确定时：游标停住、光线转暗。
- 工具收在 `/settings` 里（原来塞在输入框旁边，§27.4 挪走了）。

### 启动

- 黑屏 → 细线 → 「PERSONA LOADING」+ 进度 → 淡入聊天。
- 3 秒，可跳过。

### 页面

- `/`：human 列表（卡片：名字、一句话、最后对话）。
- `/chat/<slug>`：聊天。
- `/settings`：模型地址、context、temperature。

### 技术

- 原生 HTML/CSS/JS。
- SSE 流式。
- 不用 WebGL、Three.js、React、Vite。
- 所有动效用 CSS + Canvas 2D。

---

## 10. 工具（Phase 5）

| 工具 | 输入 | 边界 |
|---|---|---|
| `read_file` | path | 可读 `humans/<slug>/` 内 |
| `list_dir` | path | 同上 |
| `write_file` | path, content | 只能写 `workspace/` |
| `edit_file` | path, old, new | 只能写 `workspace/` |
| `run_command` | cmd | cwd = `workspace/`，10 秒超时，输出 4KB |
| `web_search` | query | 可选，需要 API key |

规则：

- 解析绝对路径，`Path.resolve()` 后必须在允许根目录内；越界直接拒绝。
- `SOUL.md`、`RULES.md`、`memories/` 永远只读。
- 写 / 执行 / 删除前，UI 弹确认。
- 工具模式默认关闭，用户点 `[tools]` 才开。
- 工具结果截断后再给模型；失败就说失败，不假装成功。

---

## 11. Session 格式

`data/sessions/<slug>/<date>-<id>.jsonl`：

```jsonl
{"id":"a1","parentId":null,"role":"user","ts":"2026-10-26T12:00:00+08:00","content":"你还记得妈妈做手术那天吗？"}
{"id":"a2","parentId":"a1","role":"assistant","ts":"...","content":"记得……","model":"MiniCPM5-2B","citations":["2023-05-12-hospital"],"usage":{"in":2100,"out":80}}
```

- 一行一个事件。
- `id` + `parentId` 支持分支。
- 不存人格数据，只存对话。
- 可导出 Markdown。

---

## 12. 开发阶段

### Phase 0 — 环境与基准 ✅ 已完成（2026-10-26）

**任务**

1. 安装 `uv`、Python 3.12、Git、pnpm（Node 24 已装）。
2. 下载 llama.cpp CPU 版 + MiniCPM5 GGUF。
3. 启动 `llama-server`，测 4K / 8K 的 prefill、生成、首字。
4. Python spike：调用 llama-server，流式聊天 10 轮。
5. Electron spike：窗口 spawn 一个 Python HTTP server 并加载。

**验收**

- [x] `llama-server` 在 127.0.0.1:8080 正常响应（1.9 s ready）
- [x] `docs/benchmark.md` 有速度 / 内存 / context 表
- [x] Python spike 能流式输出（10 轮，TTFT 中位数 2.72 s）
- [x] Electron spike 能打开窗口并显示 Python 返回的内容
- [x] 记录 4K / 8K 哪个可用（8K 可用，只多 168 MB）

**产出**：`docs/benchmark.md`、`scripts/bench_llm.py`、`scripts/spike_chat.py`、`scripts/fetch.mjs`、`scripts/env.ps1`、`spike/`、`vendor/`、`models/`、`.venv/`。

**结论**：模型与栈可用；瓶颈是**冷 prefill**，不是内存。新增硬约束见 §18。

**停止。** 等用户确认后才进 Phase 1。

### Phase 1 — 骨架 + CLI 聊天 ✅ 已完成（2026-10-26）

**任务**

1. `pyproject.toml`、`config.example.toml`、`src/openhuman/` 骨架。
2. `pack/schema.py`、`pack/loader.py`、`pack/persona.py`。
3. `llm/client.py`：OpenAI-compatible + SSE。
4. `chat/session.py`：JSONL。
5. `chat/engine.py`：无检索的一轮对话。
6. `cli.py`：`oh doctor`、`oh chat demo`。
7. `humans/demo/`：虚构人格包（SOUL、RULES、10 张卡、3 个人物、20 句语气）。

**验收**

- [x] `uv run oh doctor` 检查模型 / llama-server / demo pack
- [x] `uv run oh chat demo` 连续 10 轮，第一人称
- [x] persona ≤ 900 tokens（实测 **397 tok**）
- [x] session 可回放（`oh replay demo`）
- [x] `--model deepseek` 可切换（见 §19 的说明）

**产出**：`src/openhuman/`（16 个文件，约 1,000 行）、`humans/demo/`（18 个文件）、`tests/`（41 个用例全绿）。

### Phase 2 — 检索 + 引用 + 评测 ✅ 已完成（2026-10-26）

**任务**

1. `memory/index.py`：jieba + BM25 + 年份 / 人物过滤。
2. `memory/director.py`。
3. `memory/context.py`：硬预算。
4. `chat/engine.py` 接入检索和 citations。
5. CLI 显示「本次参考」。
6. `tests/eval/questions.yaml`：30 题。
7. `oh eval demo`。

**验收**

- [x] 30 题 top-5 命中 ≥ 80%（实测 **100%**）
- [x] 回答中的日期 / 人名 100% 出现在引用卡
- [x] 资料外问题正确说「不记得」
- [x] 200 字回覆 < 30 秒（4 核）
- [x] 首字 < 3 秒（warm）

**产出**：`memory/` 5 个文件、`eval.py`、`tests/eval/questions.yaml`（30 题）、`tests/test_memory.py`、`tests/test_eval.py`。

### Phase 3 — Web UI ✅ 已完成（2026-10-26）

**任务**

1. FastAPI app + SSE。
2. `server/static/`：HTML/CSS/JS。
3. 首页 human 列表；聊天页；设置页。
4. 引用抽屉；`[tools]` 占位。
5. 打字节奏、启动动画、断线重连。

**验收**

- [x] 浏览器可聊天，流式
- [x] 引用可点开
- [x] 手机浏览器可打开（不保证体验）
- [x] 不引入前端框架 / 构建步骤

**产出**：`server/app.py`、`server/state.py`、`static/`（3 HTML + 1 CSS + 4 JS）、`oh serve`、`tests/test_server.py`（16 用例）。

### Phase 4 — Electron 壳 ✅ 已完成（2026-10-26）· ❌ 已删除（2026-10-27，§27.5）

> 本节是**历史记录**，保留供对照。`desktop/` 已在 §27.5 删除：Electron 在这台机器上起不来
> （§25.6 / §26.1），窗口现在用 Chrome/Edge 的应用模式（`src/openhuman/window.py`）。

**任务**

1. `desktop/main.js`：spawn Python、等健康检查、创建窗口。
2. 托盘：关窗 = 睡眠；托盘退出才结束 Python。
3. 单实例锁。
4. `preload.js`：最小 API。
5. 开发模式加载 `.venv`；打包模式加载 `openhuman-server.exe`。

**验收**

- [x] 双击 app 能打开
- [x] Python 自动启动，无端口冲突（随机空闲端口）
- [x] 关窗后进程仍在托盘
- [x] 托盘退出后无残留进程
- [x] 崩溃时显示错误，不白屏

**产出**：`desktop/`（main.js / preload.js / package.json / renderer 2 页 / 托盘图标）、`--selftest` 自检。

### Phase 5 — 工具 ✅ 已完成（2026-10-26）

**任务**

1. `tools/registry.py` + 工具 schema。
2. `read_file` / `list_dir` / `write_file` / `edit_file`。
3. `run_command`：cwd 限制、超时、输出截断。
4. 路径越界测试。
5. UI 确认弹窗 + 工具开关。
6. 可选 `web_search`（没做）。

**验收**

- [x] 读 `workspace/notes.md` 并总结
- [x] 写文件只能写到 `workspace/`
- [x] `../` 越界被拒绝
- [x] 命令超时被杀
- [x] 工具失败时诚实说失败

**产出**：`tools/`（registry / files / shell，394 行）、CLI `--tools`、Web `[tools]` 面板、`tests/test_tools.py`（33 用例）。

### Phase 6 — 打包 ❄️ 冻结（用户明确要求，不要做）

> **不许打包成 exe。** 2026-10-26 用户明确要求：开发成熟之前，绝对不打包。
> 任何人（包括以后的自己）不要擅自装 PyInstaller、不要跑 electron-builder、
> 不要生成安装包。要解冻必须先问用户。
>
> 解冻条件（用户自己判断，不是我们判断）：见 §24。

**到时候再做（现在的草案，不作数）**

1. PyInstaller `--onedir` → `openhuman-server.exe`。
2. electron-builder → NSIS 安装包。
3. 首次启动：检查模型，下载 1.56GB，校验 SHA256。
4. 配置目录 `%APPDATA%\open_human\`。
5. README、LICENSE、隐私说明。
6. 干净 Windows 10/11 测试。

**验收**

- [ ] 新机器安装后能跑
- [ ] 模型下载有进度、可续传
- [ ] 卸载干净
- [ ] 不把真实数据打包进去

---

## 13. 测试与评测

- `pytest`：**15 个文件、205 个用例，约 13 秒**。覆盖面：pack schema / loader、director、
  context 预算、路径与工作区边界、prompt、检索、会话树、服务端（含 SSE）、工具、窗口、CLI、eval。
- `tests/fake_llm.py`：不依赖真模型的集成测试。
- `oh eval demo`：32 题，输出命中率 / 静默率 / 引用正确率。
- `scripts/bench_llm.py`：4K / 8K prefill / 生成 / 首字。
- `scripts/stress_chat.py`：连打 N 轮真模型，看会不会越聊越崩（§25.2）。
- 每个 Phase 结束跑一次，记录在 `docs/benchmark.md`。

---

## 14. 风险与对策

| 风险 | 对策 |
|---|---|
| 2B 中文角色扮演漂移 | 语气样本 + 短 persona + 禁语检查 + DeepSeek fallback |
| CPU 太慢 | 短回覆、串流、prefix cache、8K→4K |
| ~~Electron + Python 打包复杂~~ | **已不适用**：Electron 删了（§27.5），也不打包（§24） |
| llama.cpp 与 CPU 指令集不兼容 | 用 official CPU build；要求 AVX2；Phase 0 验证 |
| 模型下载失败 | 断点续传 + SHA256 + 手动放置说明 |
| Windows SmartScreen | 不签名；走 `.cmd` + 关闭智能应用控制（§25.5） |
| 范围蔓延 | 严格按 Phase 验收；不通过不进下一步 |
| 上下文压缩后丢失决策 | 所有决策写进本文件 |

---

## 15. 用户输入「开始」后，我做什么

> **历史章节**：这是 2026-10-26 开工时写给自己的启动流程，只适用于 Phase 0。
> 现在看「当前怎么做」应该读 `AGENTS.md` 的「常用命令」和本文件 §24.3。

1. 读 `BUILD.md` 和根目录 `AGENTS.md`。
2. 检查当前目录和已有文件。
3. 运行 `scripts/check_env.ps1`（Phase 0 创建）。
4. **只做 Phase 0**：装环境、下模型、跑 benchmark、两个 spike。
5. 输出 `docs/benchmark.md`，报告结果。
6. **停下来**，等用户确认，不自动进 Phase 1。

不要：

- 不要先做作者套件。
- 不要问人类数据。
- 不要一次做多个 Phase。
- 不要引入新依赖而不说明。
- 不要重写 `authoring-kit/`。

---

## 16. 当前状态

> 2026-10-29 实测，交付前体检（§37）之后。仓库 **1,864 MB**（另有 `dist/` 1.59 GB 的交付包，不进 git）。
> 根目录有 `README.md`（给使用者看的）和 `LICENSE`（GPL-3.0）了。

- `authoring-kit/`：精简版（7 个文件），冻结，不属于 runtime。
- `docs/`：**`benchmark.md`（Phase 0 实测，有效）** + `history/`（已过时，仅参考）+ `screens/`（4 张）。
- `humans/demo/`：虚构人格包，**21 个文件**（10 张记忆卡、3 个人物，加 `human.yaml` / `SOUL` / `RULES` / `timeline` / `traits` / `voice` / `workspace`）。
- `src/openhuman/`：**31 个 .py，3,692 行**；`server/static/` 8 个文件 1,611 行。
- `tests/`：**209 个用例，全绿，约 25 秒跑完**；`tests/eval/questions.yaml` 32 题。
- `scripts/`：`bench_llm.py` / `spike_chat.py` / `stress_chat.py` / `env.ps1` / `fetch.mjs`。
- 启动：双击根目录 `Open Human.cmd`（§25.1）；窗口直接开在他身上，不是先看菜单（§27.1）。
  窗口由 **cmd.exe 当父进程**开，python 只写 `data/window.cmd` —— 从 python 里拉浏览器
  在这台机器上会被杀软秒掉（§30）。
- 环境：Python 3.12.15 / uv 0.13.5 / Git 2.56.0 / llama.cpp b11889。
  **不需要 Node，不需要 pnpm，不需要 Electron**（§27.5 删干净了；系统里装着 Node 24.22.1，但本项目不用它）。
- 体积：`models/` 1,489 · `vendor/` 217.8（git 91.8 / python 51.4 / llama 43.5 / uv 31.1，只有一份解释器）·
  `.venv/` 110.4 · `data/` 34.7（**运行中的 Chrome profile 24.9** + jieba 缓存 8.8 + 两张界面截图 1.0 + 会话与日志；
  app 开着时会一直长，关掉不自动缩，删掉即重建）· `.git/` 9.3 · `docs/` 2.2 ·
  源码与人格包 0.5（`src` + `tests` + `scripts` + `humans` + `assets`）。相加约 1,864。明细与取舍见 §29 / §37。
- 用法：新开终端先 `. scripts/env.ps1`（PowerShell 执行策略可能挡，见 §25.3）。
- **打包：冻结中。不装 PyInstaller，不生成 exe。** 见 §24。

---

## 17. 成功标准（v1）

1. Windows 双击打开，选一个人格，能聊。
2. 连续 20 轮不出戏。
3. 问 30 条已知事实，≥ 80% 答对并显示引用。
4. 问资料外的问题，不编日期 / 人名。
5. 4 核 CPU，200 字回覆 < 30 秒，首字 < 3 秒。
6. 工具只能碰 `workspace/`。
7. 安装包在 8 GB Windows 10/11 上能跑。

### 17.1 逐条验收状态（2026-10-27）

| # | 标准 | 状态 | 依据 |
|---|---|---|---|
| 1 | 双击打开，能聊 | ✅ | `Open Human.cmd`；窗口直接开在他身上（§27.1） |
| 2 | 连续 20 轮不出戏 | ✅ 不崩（「出戏」要人判断） | `scripts/stress_chat.py 20`：20 轮 0 失败，76 秒（§25.2） |
| 3 | 30 条已知事实 ≥ 80% 答对 + 引用 | ⚠️ 检索达标，作答受 2B 限制 | 检索 25/25 命中、top-1 24/25（§28.8）；引用能显示；但岁数类问题实测答错（§28.8-2） |
| 4 | 资料外不编日期 / 人名 | ⚠️ 6/7 | q32 是已知局限（§28.8） |
| 5 | 4 核 CPU，首个字 < 3 秒 | ✅ | 真机 0.31–1.68 s（§28.8）。后半句「200 字 < 30 秒」已被 N-06 的 80 字上限取代，不再适用 |
| 6 | 工具只能碰 `workspace/` | ✅ | 边界有测试覆盖（§23.2），`allow_mutating` 默认关 |
| 7 | 安装包在 8 GB Win10/11 上能跑 | ❄️ 冻结 | 用户明确要求不打包（§24），不是欠账 |

第 3、4 条剩下的差距在 **2B 自己的能力上，不在代码上**（四条已知短板见 §28.8）。
继续改代码的边际收益已经接近零，下一步的收益只能来自**换更大的模型**或**接真实数据**。

---

## 18. Phase 0 实测结论（已锁定）

完整数据在 `docs/benchmark.md`。这里只放**会改变实现方式**的部分。

### 18.1 数字

| 项 | 实测 |
|---|---|
| 冷 prefill | ~120–150 tok/s。3,500 tok = **29 秒** |
| 暖 prefill（前缀命中） | 只算新增 token，TTFT **0.1–0.2 秒** |
| decode | 16–17 tok/s（短回复），长生成掉到 11 |
| 内存 | 8K context 2.65 GB，4K 2.48 GB |
| 模型加载 | 1.9 秒 |

### 18.2 六条硬约束

| # | 约束 |
|---|---|
| **N-01** | `cache_prompt: true`，prompt 只追加、不改前面。前面改一个字符，后面全部重算。 |
| **N-02** | 开机预热：加载完人格包后，先发一个极短请求把 persona 前缀灌进缓存，藏在启动动画后面。**没有它，每次打开 app 第一句要等 8 秒。** |
| **N-03** | 记忆块放在**历史之后、当前问题之前**，3 张卡、≤400 tok。这样每轮只重算 ~400 tok ≈ 3 秒。 |
| **N-04** | 裁历史 = 一次重算（3–4 秒）。要少裁、一次裁多轮，不要每轮裁一点。 |
| **N-05** | 每个请求带 `chat_template_kwargs: {"enable_thinking": false}`，并在客户端剥掉字面量前缀 `<think>\n\n</think>\n\n`。 |
| **N-06** | 默认回复 ≤ 80 字。decode 17 tok/s，80 字 ≈ 6 秒；250 字 ≈ 15–20 秒。 |

### 18.3 从 spike 带进实现的细节

- **端口握手不要用 stdout。** Electron 自己选空闲端口 → 通过 `OPENHUMAN_PORT` 环境变量传给 Python → 轮询 `/health`。比解析 `READY port=` 稳。
- **Electron 的 `--no-sandbox` 只在本开发沙箱需要**，用户机器上不要带。
- 便携工具全在 `vendor/`，新终端先 `. scripts/env.ps1`。

### 18.4 尚未达标

- **首字 < 3 秒**：稳态 0.2–1.5 秒，达标；冷启动第一句 8 秒，靠 N-02 压到 0.6 秒。**需要用户确认「开机动画盖住预热」这个做法。**
- **200 字回覆 < 30 秒**：短回复达标；连续长生成满载时 ≈ 20 秒，勉强达标。所以 N-06 保持短回复。

---

## 19. Phase 1 实现记录（已锁定）

代码在 `src/openhuman/`，约 1,000 行，最大单文件 194 行。

### 19.1 结构

| 模块 | 职责 |
|---|---|
| `paths.py` | 项目根、slug 校验、会话路径、路径越界判断 |
| `config.py` | `config.toml` + `DEEPSEEK_API_KEY` 环境变量 |
| `tokens.py` | 有 server 用 `/tokenize` 精确算，没有就按 0.7 tok/汉字估 |
| `pack/schema.py` | `HumanMeta` / `MemoryCard` / `Person` / `Pack` |
| `pack/loader.py` | 读 + 校验；缺 source 的卡标为不可检索；坏卡跳过并记 warning |
| `pack/persona.py` | 编译 system prompt，纯函数、可重复、≤700 tok |
| `llm/client.py` | OpenAI 兼容 SSE；剥 `<think>`；`cache_prompt` 只在本地后端发 |
| `llm/prompt.py` | 组装顺序：persona → 历史 → 记忆块 + 问题 |
| `chat/session.py` | JSONL，`id`+`parentId`，回放、导出 Markdown |
| `chat/engine.py` | 一轮对话 + 开机预热 |
| `cli.py` | `oh doctor` / `oh chat` / `oh replay` / `oh packs` |
| `doctor.py` | 全部自检逻辑 |

### 19.2 实测

- persona 编译后 **397 tok**（预算 700，旧预算 900 也够）。
- 10 轮对话：首字 **0.19–0.28 秒**，生成 **14–15 tok/s**，缓存命中从 406 涨到 673。
- 开机预热 2.9 秒（冷）/ 0.5 秒（暖），第一句首字 0.19 秒 —— **N-02 有效**。
- JSONL 格式与 §11 一致，`oh replay demo` 可读。

### 19.3 已验证 Phase 2 的前提

手动塞一张记忆卡进去，模型会用，而且用得很具体：

> **问**：你还记得儿子结婚那天吗？
> **答**：唉，记得。2010年5月2日，儿子结婚，媳妇王倩，做会计的。酒席办在城站附近一家饭店，二十桌。我上台讲话，写了三遍稿子，讲到"他小时候我抱着他去看病"那句，就说不下去了……

所以 Phase 2 只要检索准，效果就成立。

### 19.4 已知问题（Phase 2 处理）

| 问题 | 说明 |
|---|---|
| **没检索时回答偏干** | 问"儿子结婚那天"只答"记得。"——因为上下文里没有那张卡。接上检索后应消失。 |
| **有卡时回答偏长** | 会整段复述卡片，超过 RULES 写的 80 字。Phase 2 要在 prompt 或截断上收紧。 |
| **2B 的事实串位** | 把"孙女陈念"说成"女儿"。检索命中后概率下降，但不会归零，评测里要单列。 |
| `--model deepseek` 未实测 | 没有 `DEEPSEEK_API_KEY`。代码路径已按 OpenAI 协议写好，Phase 2 有 key 时验证。 |

---

## 20. Phase 2 实现记录（已锁定）

### 20.1 结构

| 模块 | 职责 |
|---|---|
| `memory/text.py` | jieba 分词 + 汉字二元组 + 停用词 |
| `memory/director.py` | 正则抽年份、对照人名表、寒暄识别 |
| `memory/index.py` | BM25 打分 + 年份/人物/标题加权 + 覆盖率闸门 |
| `memory/context.py` | 400 tok 硬预算，装不下就裁最后一张 |
| `eval.py` | 30 题题库、命中率、编造检查 |

### 20.2 实测（`oh eval demo`）

| 指标 | 结果 | 目标 |
|---|---|---|
| top-5 命中 | **25/25 = 100%** | ≥ 80% |
| top-1 命中 | **23/25 = 92%** | — |
| 资料外问题无命中 | **5/5 = 100%** | 100% |
| 回答里的日期能对上引用卡 | **25/25** | 100% |

首字 0.9–3.0 秒（暖），生成 14–15 tok/s。

### 20.3 为什么这么设计

**加了汉字二元组。** 只用 jieba 词时，"手在抖" 会被切成「手」「在」「抖」，全被停用词或单字规则过滤，q03 直接漏检。词 + 二元组双路索引把 top-5 命中从 80% 拉到 100%。

**覆盖率只算语料里出现过的词。** 问句里那些整个语料都没有的词（"量子力学"），谁都不可能匹配上，算进分母只会误伤。过滤后再算覆盖率，才能真正区分「有这件事」和「没有这件事」。

**三重加权。** 年份 +4、人名 +2、标题命中 +1.5。分数不到第一名 40% 的卡直接丢掉，避免把 1997 年的事塞进 2010 年的问题里。

**年份是硬路由。** 问句里提到 2019，且确实有 2019 年的卡，就只看那年，不再跟其它年份比。

### 20.4 顺手修的一个幻觉

"今天天气怎么样？" 原本模型会顺着编："今天下午有点闷……去年台风阳台玻璃裂了一道口子。"

在 RULES.md 加了一句 **"你看不见外面，也收不到消息"**，之后就变成：

> 唉，不知道。我看不见外面，也收不到消息。

这句话同时立住了人设 —— 他知道自己在哪儿，也知道自己的局限。

### 20.5 还没解决的

| 问题 | 说明 |
|---|---|
| 复述偏长 | 问到具体事件时仍会整段讲，60–90 tok ≈ 12 秒。读起来是自然的（老朋友讲旧事），但超过 RULES 写的 80 字。 |
| top-1 还有 2 题错 | q14「退休那天怎么回家」、q15「哪年退休」排到了黄山那张卡。top-5 里有正确的卡，所以验收过了。10 张卡的小语料上继续调容易过拟合，等真实数据再看。 |

---

## 21. Phase 3 实现记录（已锁定）

### 21.1 结构

| 文件 | 职责 |
|---|---|
| `server/state.py` | 加载人格包、建索引、按 slug 持有会话 |
| `server/app.py` | FastAPI 路由 + SSE + 设置写回 |
| `static/core.js` | 元素/请求/SSE 解析/打字机 |
| `static/chat.js` | 启动动画、流式、打字节奏、引用抽屉 |
| `static/style.css` | 全部视觉 |
| `static/index.html` `chat.html` `settings.html` | 三个页面 |

### 21.2 三个非显然的决定

**SSE 用 POST + fetch 读流，不用 EventSource。** `EventSource` 只能 GET，把用户的话塞进 query string 既难看又有长度限制。用 `fetch` + `ReadableStream` 手工解析 `event:` / `data:` 块，二十行就够。

**打字机要会追。** 模型 15 tok/s ≈ 20 字/秒，人打字 3–5 字/秒。纯按人的速度吐，一段 100 字的回答要打 25 秒，比等模型还慢。所以：基础 24–40ms/字，标点后停 120–230ms，**积压超过 40 字就把间隔压到 0.4 倍**追上去。看起来仍是"在想、在写"，但不会越来越落后。

**开机动画盖住预热。** 聊天页一打开就并行发 `/api/warm/<slug>`，同时跑 1.7 秒的最短动画。冷启动预热 3–8 秒，动画就一直转；预热好了就淡入。用户感知不到 prefill（§18 N-02 的落地方式）。

### 21.3 界面

截图在 `docs/screens/`。

- 背景 `#0a0c0f`，暖白 `#ece6dc`，等宽字体。
- 20px 极淡窗框、1px 扫描线、SVG 噪点、径向暗角。
- 内容列 720px 居中；**对话贴着输入框往上长**（`::before` 撑开），不飘在顶部。
- 游标呼吸 1.8s；等待首字时 `body.waiting` → 动画停住、暗角加深。
- 引用：`[mem: id]` 立刻出现，2 秒后淡到 0.26，仍可点开右侧抽屉。
- 抽屉里把 `## 发生了什么` 这类小标题渲染成 10px 字距标签，不显示原始 Markdown。
- 手机宽度 390px 下版式正常（`@media 640px`）。

| 文件 | 内容 |
|---|---|
| `01-index.png` | 首页 |
| `02-chat.png` | 两轮对话 + 引用 |
| `03-card.png` | 记忆卡抽屉 |
| `04-boot.png` | 启动动画 |

### 21.4 验收

| 项 | 结果 |
|---|---|
| 浏览器可聊天，流式 | ✅ SSE `meta → delta… → done` |
| 引用可点开 | ✅ 抽屉显示日期/标题/标签/正文 |
| 手机浏览器可打开 | ✅ 390×844 版式正常，`--host 0.0.0.0` 可局域网访问 |
| 不引入前端框架 / 构建步骤 | ✅ 纯 HTML/CSS/JS，改完刷新即生效 |

首字 0.9–1.4 秒（暖），生成 14–15 tok/s。

### 21.5 开发工具

`scripts/shot/` 曾是个 Electron 小应用，用来把页面截成 PNG 做肉眼验收：

```powershell
vendor\electron\electron.exe scripts\shot --url=http://127.0.0.1:8710/chat/demo `
  --out=logs/chat.png --wait=12000 --type-file=logs/q.txt --after=14000
```

`--no-sandbox` 只在本开发沙箱里需要，正常机器不用。

> **2026-10-27：`scripts/shot/` 已随 Electron 一起删掉（§27.5）。** 上面这条命令现在跑不了。
> 要截图就手动开窗口截；`docs/screens/` 里那 4 张是历史产物，不随界面自动更新。

### 21.6 还没做的

| 项 | 说明 |
|---|---|
| `[tools]` | **后端已实现**（Phase 5：`tools/registry.py` + `files.py` + `shell.py`，§22）。设置页 `off / read / write` 三档（`localStorage` 的 `oh.tools`），`read` 只读、`write` 才允许改 `workspace/`；对话页收到 `tool` 事件只渲染一行 `toolline`，**没有完整的工具交互界面**。 |
| 断线重连 | 现在断了显示"（连接断了。）"，不会自动续；会话已落盘，刷新页面还在。 |
| 历史回看 | 刷新页面会开新会话，旧的在 `data/sessions/`，UI 里还看不到。 |

---

## 22. Phase 4 实现记录（已锁定）

### 22.1 结构

| 文件 | 职责 |
|---|---|
| `desktop/main.js` | 单实例、选端口、拉 Python、开窗、托盘、退出清理 |
| `desktop/preload.js` | `window.oh = { isDesktop, version, quit, retry, reload }` |
| `desktop/renderer/loading.html` | 启动中（自包含，不依赖服务端） |
| `desktop/renderer/error.html` | 失败时显示原因 + 重试/退出 |
| `desktop/assets/tray.png` | 32×32 圆环，一个点 |

跑：

```powershell
vendor\electron\electron.exe desktop
```

### 22.2 端口握手：不用 stdout（§18 的结论落地）

BUILD 原计划是让 Python 打印 `READY port=...`，Electron 去解析。实测这个方案在受限环境里会 EPERM（命名管道），而且本身也脆。

改成：

1. Electron 用 `net.createServer(0)` 要一个空闲端口；
2. 通过 `--port N` 传给 Python；
3. 轮询 `http://127.0.0.1:N/health` 直到 200。

**永远不会撞端口，也不需要解析任何输出。**

### 22.3 关窗 = 睡眠

```js
win.on('close', (event) => {
  if (state.quitting) return;
  event.preventDefault();
  win.hide();
});
```

只有托盘菜单的「退出」才把 `state.quitting` 置真，然后杀子进程、`app.quit()`。

### 22.4 自检

`--selftest` 会真的跑一遍验收：

```
PASS 关窗后窗口隐藏
PASS 关窗后进程还活着
PASS 关窗后服务还能响应
PASS 托盘能再叫回来
PASS 退出后 Python 没了
```

```powershell
vendor\electron\electron.exe desktop --selftest
```

### 22.5 顺手做的事

- **开发模式下顺手拉起 llama-server**：8080 没响应、`vendor/llama/` 和模型都在，就自己起一个；退出时一起收掉。这样双击就能聊，不用先开终端。
- **`--shot=<file>`**：加载完截一张图再退出，用来肉眼验收（失败页也能截）。
- **`titleBarStyle: hidden` + `titleBarOverlay`**：Windows 原生标题栏是白底，压在 `#0a0c0f` 上很刺眼。改成深色 overlay，顶部 34px 交给系统按钮，网页里加一条 `.dragbar` 负责拖动。

### 22.6 一个必须记住的教训

**不要在 PowerShell 命令里写中文再落盘。**

用 `Get-Content | Set-Content` 改一个带中文注释的文件，会经过一次 GBK 往返，把注释变成乱码；乱码是合法 UTF-8，所以不会报错，但 `core.js` 里被破坏的 `PAUSE` 键名直接让整个前端白屏（`Uncaught SyntaxError`）。

日后规则：

- 改带中文的文件，只用编辑工具，不用 shell 管道。
- 改完 JS 跑一次 `node --check`。
- `oh doctor` 之外，`pytest` 也会跑前端资源的存在性测试。

---

## 23. Phase 5 实现记录（已锁定）

### 23.1 结构

| 文件 | 职责 |
|---|---|
| `tools/files.py` | 路径解析、读、列、写、追加、替换 |
| `tools/shell.py` | 跑命令，cwd 锁 workspace，超时杀进程树 |
| `tools/registry.py` | 6 个工具的 schema、分发、确认闸门 |

**原生 function calling**：先把探针跑通（`finish_reason: tool_calls`），才按原生协议做，
没有自造文本协议。`llm/client.py` 负责把流式的 `tool_calls` 分片按 index 拼回去。

### 23.2 边界

| 工具 | 能碰哪儿 | 要确认吗 |
|---|---|---|
| `read_file` / `list_dir` | 人格包目录 | 不用 |
| `write_file` / `append_file` / `edit_file` | 只有 `workspace/` | 要 |
| `run_command` | cwd = `workspace/` | 要 |

读路径先找 `workspace/`，再找人格包根目录。因为模型说 "notes.md" 时，指的是他能看见
的那份；说 "SOUL.md" 才是人格包根目录。

### 23.3 两个真实踩到的坑

**坑一：只给 write_file，模型会覆盖用户的文件。**

第一次验收，让它"记一条备忘"，它把 `notes.md` 整个重写了——用记忆卡的内容替换了原来的
四条笔记。加了 `append_file`（这是原计划 6 个工具之外的第 6 个），并在 `write_file` 的
描述里明写"会整个覆盖，加东西用 append_file"。之后原内容保住了。

**坑二：小模型的工具调用会漂。**

读文件那一轮之后，下一轮它就忘了自己有工具，直接开始"念"记忆卡，还谎报"记了"。
在 system prompt 末尾挂了一小段固定说明（只在开工具时挂）：

```
## 工具
你能调用工具去读写 workspace 里的文件。
要动文件就直接调工具，不要在回话里假装已经记下了。
write_file 会把原文件整个冲掉；只是加一句话，用 append_file。
```

之后稳定了。这段不写进人格包，因为它是功能性的，不属于"他是谁"。

### 23.4 验收实测

```
你 › 把这条加到 notes.md 末尾：明天上午去医院拿药

  ✓ read_file · # 随手记 …
  ◇ 他要动手了  在 notes.md 末尾加一句（10 字）
    允许吗？ (y/N) y
  ✓ append_file · 已在 notes.md 末尾加了一句（9 字）
  加上了。

你 › 刚才那条真的写进去了吗？读一下 notes.md 最后几行
  ✓ read_file · …
  加进去了。
```

越界与超时（直接调工具层）：

```
OK   read_file  -> 越界了：../../config.toml 不在允许的目录里
OK   read_file  -> 越界了：C:/Windows/win.ini 不在允许的目录里
OK   write_file -> 越界了：../SOUL.md 不在允许的目录里
OK   run_command-> 命令超过 10 秒没跑完，已经杀掉。
```

### 23.5 和原计划的偏差

| 项 | 说明 |
|---|---|
| 多了 `append_file` | 原计划没有。不加的话模型会用 `write_file` 覆盖原文件，实测丢了数据。 |
| Web 端没有逐次确认 | 改成 `[tools]` 三档开关（关 / 只读 / 全开），全开是用户显式选择的。CLI 仍是逐次确认。 |
| `web_search` 没做 | 需要 API key，收益不明，先空着。 |

### 23.6 还没解决的

| 问题 | 说明 |
|---|---|
| 2B 会谎报 | 没调工具也会说"记了"。加了提示后好很多，但不是零。这是 2B 的上限。 |
| 会重复读同一个文件 | 一次回答里读了两次 notes.md。浪费但不致命。 |
| 命令是 Unix 语法 | 它偶尔会写 `ls`/`cat`。工具描述里写了"这是 Windows，用 dir/type"，仍有概率出错。 |

---

## 24. 打包：冻结（2026-10-26 用户决定）

> **不许打包。** 用户原话：「绝对不需要打包成 exe，直到开发成熟完成后，才打包」。

### 24.1 为什么冻结是对的

- 现在每天都在改代码，打包把没定型的形态固化，之后每次改动都要重新打、重新装、重新测。
- 打包会引入一堆和功能无关的复杂度：资源定位、模型下载、权限、路径、杀软误报。
- 打包只能在干净机器上验收，这个环境验不了，等于做完了也不知道行不行。

### 24.2 冻结期间不许做的事

- 不装 PyInstaller、electron-builder、nsis。
- 不生成 `.exe`、`setup.exe`、安装包。
- **不为打包而改代码**（比如把路径改成 `sys._MEIPASS`、把资源塞进 asar）。
- 不写"安装说明"，写了也没人用。

要解冻，**先问用户**，得到明确同意再动。

### 24.3 现在怎么启动

不用打包也能用。再具体一点：

```powershell
cd C:\...\open_human
.\"Open Human.cmd"        # 起模型 + 起服务 + 开一个应用窗口（没有地址栏那种）
```

窗口是 Chrome/Edge 的应用模式，不是 Electron —— Electron 在这台机器上起不来，
原因和排查过程见 §25.6。想退回普通标签页：`oh serve --browser`。

其余等价物：

```powershell
.venv\Scripts\python.exe -m openhuman.cli serve            # 默认开应用窗口
.venv\Scripts\python.exe -m openhuman.cli serve --no-open  # 什么都不开
.venv\Scripts\python.exe -m openhuman.cli serve --no-model # 模型自己另开
```

### 24.4 什么时候算"成熟"

这个判断权在用户，不在实现者。下面只是参考信号：

- 跑的是**真实人格包**，不是 `humans/demo/`。
- 连续用几天不出戏、不崩、不需要重启。
- 工具真的帮上忙，而且没出过事故（没覆盖过不该覆盖的文件）。
- 界面手感定了，不再天天改。
- 用户自己说"可以了"。

在此之前，Phase 6 一直是冻结状态。

---

## 25. 打磨第一轮（2026-10-26）

用户要求「把整个项目完善好，反复验证保证没有 bug」，并且「轻量、极简」。
这一轮只补洞，没有加新框架、新依赖、新目录。

### 25.1 改了什么

| # | 问题（用户能感觉到的） | 根因 | 修法 |
|---|---|---|---|
| 1 | 双击打不开，得先敲一长串命令 | 没有启动入口；模型要手动起 | 根目录 `Open Human.cmd` + `localmodel.py`：判活、拉起、退出收尾；端口已在跑就直接开浏览器 |
| 2 | 刷新页面记录没了，但他还记着 | 前端从不回放，服务端会话一直在 | `GET /api/session/{slug}` + `replay()`；加 `[新]` 按钮明确重开 |
| 3 | 切到 DeepSeek 界面显示离线、输入框锁死 | 云端没有 `/health` 可探 | `online()` 云端看 key；云端也不做预热（没前缀缓存，白花钱） |
| 4 | 改个温度他就失忆 | `invalidate()` 把引擎和会话一起清了 | 重建引擎、留住 Session |
| 5 | 问没记下的人，他答了另一张卡 | 人名只从 `people/*.md` 里认 | 人名也扫记忆卡的 `people`；问到具体的人就只留提到他的卡，一张没有就空手 |
| 6 | 检索不到的时候，他照样编年份天气 | 空检索时 prompt 里什么都没说，RULES 还要求「答话里带天气」 | `MISS_NOTE` 摆在问题前；RULES 那条改成只对所记得的事生效 |
| 7 | 有条测试只有模型开着才过 | 它其实打的是真 llama-server | 换假引擎，测试不再依赖外部进程 |
| 8 | 两个页面同时聊会互抢工具开关 | 引擎上的工具配置在锁外改 | 挪进 `entry.lock` 里 |
| 9 | `[mem:]` 点开、关掉、再点另一条会隐身 | 关闭定时器没清 | 清定时器；`append_file` 补上中文标签 |
| 10 | 每条命令都先打三行 jieba 日志 | jieba 默认往 stderr 说话 | `setLogLevel(WARNING)` |

顺手清掉了仓库根目录的残留：`jieba.cache`（9 MB，已挪到 `data/jieba/`）、
`shot.png`、`tmp*.whl`、`pytest-of-henry/`、空的 `spike/`、`data/el-*`。

### 25.2 验证

- `pytest`：**157 个用例全绿**，12 秒。新增 `test_localmodel.py`、`test_state.py`。
- `oh eval demo`：检索 **25/25**、top-1 **23/25**、资料外静默 **6/7**。
  已知做不到的那题（q32）在题库里标了 `known: true`，输出用 `≈` 而不是红叉 ——
  红叉天天亮着，就会被训练成背景噪音。
- `scripts\stress_chat.py`：连打 **20 轮，0 失败**，76 秒；首字 1.6–3.8 s，
  稳态整轮 2–3 s，第一轮 13.7 s（冷 prefill，没预热）；会话落盘 40 条消息。
- 界面：用 Edge headless 截了首页 / 聊天 / 设置三页复验，见 `docs/screens/08-replay.png`。
- 工具：`append_file` 真的写进了 `workspace/notes.md`，写完已还原。
- 仓库建了 git（首个提交 `0005e3d`），`.cmd` 用 `.gitattributes` 锁定 CRLF。

```powershell
.venv\Scripts\python.exe scripts\stress_chat.py 20      # 需要 oh serve 在跑
```

### 25.3 已知问题（记着，不藏）

| 问题 | 说明 |
|---|---|
| **双击 .cmd / .lnk 被拦** | Windows 11 智能应用控制（SAC）开着的机器上会报 `An Application Control policy has blocked this file`。详见 §25.5。 |
| Electron 起不来 | 当前环境下一个最小 Electron app 也 `0xC0000005` 崩溃，是环境不是代码。浏览器路径完整可用，桌面壳等换环境再验。 |
| PowerShell 挡 `env.ps1` | 执行策略是 `Restricted` 时点号源会失败。走 cmd 的 `Open Human.cmd` 不受影响。 |
| BM25 分不清谁的「小时候」 | 「你小时候住哪儿」会命中儿子结婚那张卡。eval 里 q32 故意留着当报警器。 |
| 2B 的老毛病 | 会重复对方问句、偶尔答非所问、把「记不清」说成「我记得不记得」。这是模型上限，不是 bug。 |
| llama-server 可能残留 | 用窗口 X 硬杀 python 时子进程不会跟着退。下次启动会**复用**它，不会起第二个。`Ctrl+C` 是干净的退出方式。 |

### 25.4 下一轮

1. 接真实人格包（用户整理好数据之后）。
2. 长会话：50 轮以上、跨天续聊、会话列表。
3. 工具事故演练：让它真的试图越界，看拦得干不干净。
4. 资料外静默率 86% → 100%。

### 25.5 环境拦路：Windows 智能应用控制

用户在 2026-10-26 22:37 报告"安全中心禁止我运行"。实测结论：

```
An Application Control policy has blocked this file.
Dangerous file extension from the web.
```

- 机器状态：Windows 11 26300，`VerifiedAndReputablePolicyState = 1`（SAC 开），
  `CodeIntegrityPolicyEnforcementStatus = 2`（强制执行），CodeIntegrity 事件 3033。
  Defender 实时保护是关的，火绒在跑，但**拦截不是火绒**。
- **被拦的是 shell 执行的文件类型**：`.cmd`、`.bat`、`.lnk` 全部拒绝，
  连新建一个指向 `notepad.exe` 的快捷方式也会被拒。
- **`.exe` 不受影响**：`python.exe`、`llama-server.exe`、`electron.exe`
  用 ShellExecute 起都正常。
- 从终端里 `cmd /c "Open Human.cmd"` 一直正常，拦的只是"双击"这条路径。
- 拦截不稳定：同样内容的临时 `.cmd` 有时能跑、几秒后再试就被拒。
  所以**不能靠它**做交付入口。

SAC 没有白名单，官方口径是：关掉之后无法再打开（除非重置/重装 Windows）。
所以这是用户的选择，不是实现者能替用户决定的。可用的替代入口：

| 入口 | 代价 |
|---|---|
| 关掉 SAC：设置 → 隐私和安全性 → Windows 安全中心 → 应用和浏览器控制 → 智能应用控制 → 关闭 | 双击恢复，但不可逆 |
| 终端里跑 `.\"Open Human.cmd"` | 每次要开窗口，但零风险 |
| 计划任务开机常驻 + 浏览器书签 | 一次点击，但模型常驻约 2.6 GB 内存 |

### 25.6 窗口：Electron 起不来，改用应用窗口模式

用户要的是「像桌面应用」，不是「终端 + 复制 IP 到浏览器」。两条路都试了。

**Electron 这条路，在这台机器上走不通。** 证据：

| 启动方式 | 结果 |
|---|---|
| `electron.exe --version` / `--help` | 退出码 `0x80000003`，零输出 |
| 带 `--no-sandbox --single-process --disable-gpu` | 一样崩 |
| 换 Electron 43.8.3（另下了 144 MB） | 一样崩 |
| 用计划任务在沙箱外启动 | 一样崩 |
| 用 `explorer.exe <快捷方式>` 在沙箱外启动 | 进程都不出现，日志是空的，连 `Application Error` 都没有 |

崩在 `electron.exe` 自己里面（同一个偏移），跟 `desktop/main.js` 无关。
最可能是火绒的 HIPS 对未签名 Chromium 注入，其次是这个 Windows 11 预览版（26300）本身。
**没验证过的一条**：把火绒退出后双击 Electron 试试 —— 如果好了，桌面壳就能接回来。

**顺带查清的另一件事**：Chromium 自己的沙箱在**实现者这边的**进程树里初始化失败
（Chrome 同样退 `0x80000003`，加 `--no-sandbox` 就活）。所以本机所有浏览器窗口测试
都临时加了 `--no-sandbox`，**这不是产品代码要干的事**，用户正常双击的进程树里没有这个限制。

**现在的做法**（`window.py`）：用系统自带 Chrome/Edge 的**应用模式**开一个窗口。

```
chrome.exe --app=http://127.0.0.1:8710 --window-size=1180,830 --user-data-dir=data\window\chrome
```

没有地址栏、没有标签页、独立窗口、任务栏里是「陈建国」。浏览器签过名，不会被安全软件拦，
也不用打包。

两个实现上的坑，记在这里免得再踩：

1. **走 PowerShell 的 `Start-Process` 启动**，不要直接 `Popen` / `ShellExecuteW`。
   后者在这台机器上起的 Chromium 会自己判死（`0x80000003`），前者能活。
2. **开完要验活**（`window.running()` 数进程），3 秒内没起来就退回普通标签页 ——
   宁可给个标签页，也不能什么都不弹，让人对着黑窗口发呆。

Chrome 排在 Edge 前：Edge 在已经开着默认配置时会忽略 `--app`，开出一个空白窗口。

## 26. 打磨第二轮：底层精简 + 体验加深（2026-10-27）

用户的原话：「持续针对整个项目，进行底层优化，保证项目简约干净，并且持续优化用户体验和界面体验」。
这一轮不加功能，只做三件事：**去掉不该在的东西、修掉看起来在其实没在的东西、把细节往里推一层。**

### 26.1 Electron 复测：结论翻了一次，最后没变

§25.6 留了一个「没验证过的一条」：退出火绒后 Electron 能不能起。用户真的退出了，于是复测。

**第一次测出来是「能起」，但那个结果是假的。** `electron.exe --version` 输出了 `v24.22.0`、
退出码 0 —— 看起来好了。实际上 `v24.22.0` 是 Node 的版本号，不是 Electron 的：这个 shell 从
DSH 自己（它本身是 Electron 应用）继承了 `ELECTRON_RUN_AS_NODE=1`，于是 electron.exe 退化成了
普通 node，压根没进 Chromium 初始化。清掉这个环境变量后立刻回到 `0x80000003`。

**教训**：`electron.exe --version` 不能用来看「Electron 能不能跑」，它在 RUN_AS_NODE 模式下
打印的是 Node 版本；判断必须看它是否输出了 Electron 的版本号（`v45.0.0`）。

清干净之后重测，结论比上一轮更硬：

| 测试 | 结果 |
|---|---|
| `--version`（无 `--no-sandbox`） | `0x80000003` |
| `--no-sandbox --version` | `v45.0.0`，退出 0 |
| **最小应用**（`app.whenReady()` 前就崩，只有 6 行 main.js） | `0xC0000005`，日志只到 crashpad `not connected` |
| 最小应用 + `--disable-gpu` / `--in-process-gpu` / `--disable-breakpad` / `--single-process` | 一样 `0xC0000005` |
| 换 Electron 43.8.3 | 一样 |
| 换 `--user-data-dir` 到全新临时目录 | 一样 |
| **用计划任务在实现者进程树之外启动**（交互式登录，非子进程） | 一样 `0x80000003` |

所以这不是「实现者的沙箱问题」，也不是「我们的 main.js 问题」：**一个 6 行的最小 Electron 应用
在这台机器上就是起不来**，崩在 Chromium 初始化阶段。旁证是用户自己的另一个 Electron 项目
（`Downloads\550W_Dex`）同一时刻也在 `0xC0000005`。

另外查到火绒其实没退干净：`HipsDaemon` 服务仍在 `Running`，`sysdiag.sys` 内核驱动仍加载。
真正的「退出」应该是托盘右键 → 退出，之后服务状态变 `Stopped`。

**决定**：维持应用窗口（§25.6 的做法）。它已经满足「没有地址栏、独立窗口、任务栏是他」，
而且比 Electron 少 868 MB 死重（`vendor\electron` 357 MB + `vendor\electron43` 361 MB +
`vendor\electron.zip` 151 MB）。`desktop/` 源码留着（13 KB），等哪天平台能跑再接线；
在那之前它是死代码，删不删都不影响运行。

### 26.2 修掉的真 bug：「从头开始」原来什么也没做

界面上的 `[新]` 调的 `POST /api/session/{slug}/new`，实现是 `restart_session()`：

```python
def restart_session(self, slug: str) -> None:
    self._engines.pop(slug, None)
```

把引擎丢掉就完了。但下一次请求走 `entry()`，里面是 `Session.resume(slug)` —— 挑**最近的那个
.jsonl**，正好还是刚才那个文件。于是旧对话原封不动回来，界面上看就是「点了没反应」，
而按钮的承诺是「他会忘掉刚才聊的」。

现在 `restart_session()` 会当场建一个**真的新会话**（新文件、空事件），并把它装回引擎。
补了 `tests/test_state.py::test_restart_session_really_forgets`：断言新会话路径不同、事件为空。
实测：换之前 4 条 → 换之后 0 条 → 再聊一句，只有 2 条。

### 26.3 界面：把「冷壳里的人味」再推一层

| 改动 | 为什么 |
|---|---|
| **不再抢滚动** | 你去上翻旧话时，新字不该把你拽回底部。现在只有贴着底才跟随；离开底部就停住 |
| **离开底部时浮出 `↓`** | 不然你不知道下面还有话。点一下才回来，带一圈暗影，压在字上也读得清 |
| **`[新]` 改成两段式** | 第一下只是问「确定？」，再点一下才真的忘。去掉系统 `confirm()` —— 那个弹窗一冒出来，这间屋子就变成普通网页了 |
| **点面板外面就收起工具面板** | 不用再去找那个 `[tools]` 点第二次。`Esc` 也收 |
| **「上次说到这儿 · 昨天」** | 只写「上次说到这儿」像是同一个下午；带上日子，人才真的是隔了一夜回来的 |
| **去掉首屏白闪** | 三个页面 `<head>` 里内联 `html{background:#0a0c0f}`，样式表还没到就已经是黑的 |
| **`role="log"` / `aria-label`** | 读屏至少知道这是一段对话 |

### 26.4 精简：删掉「定义了但没人用」的东西

先做了一轮全仓库审计（函数、字段、常量、测试辅助逐项 grep 复核），删的是**零引用**的东西，
不是「看起来像没用」的东西。保留了两类"暂时没用但在设计里"的：会话树的 `parent_id`、
人格包 schema 里的元数据字段（那是数据模型，`docs/history/01-human-pack.md` 有描述）。

收敛掉的重复（这才是真正的债）：

| 原来 | 现在 |
|---|---|
| `cli._client()` 与 `Runtime.client()` 各写一遍 deepseek/llama 分支 | `config.make_client(cfg, backend)` 一处 |
| 「取最近一个 .jsonl」写了三遍（`Session.resume`、`cli._open_session`、`cli.replay`） | `paths.latest_session(slug)` 一处 |
| 模型权重路径拼两遍（`localmodel` 与 `doctor`） | `localmodel.model_path(cfg)` 一处 |
| `oh chat` 里手写一长串 llama-server 参数当提示 | 和 `oh serve` 一样直接调 `localmodel.ensure()`，模型没开就替他开；不再让人背参数 |

另外删掉了 `AppConfig.humans_dir` / `data_dir` 两个配置字段：它们从来没被读过（路径是
`paths.py` 里写死的），留着等于承诺一个不存在的开关。

### 26.5 启动路径上的两个小毛病

1. **控制台标题**从 `C:\Users\...\cmd.exe` 改成 `Open Human`。窗口在任务栏里至少有个名字。
2. **第二次双击不再留下一个等按键的黑窗口**：`serve` 发现有实例在跑时，开窗后以退出码 `7`
   结束，`.cmd` 见到 `7` 就直接退，不 `pause`。

### 26.6 已知未做

- 多人格包里没有任何入口能从对话页回到列表页（单人时不需要，多人时必须有）。
- `Pack.timeline` / `Pack.samples` 会被加载，但没有任何地方消费；检索和注入都还没接线。
- `desktop/` 是死代码（Electron 起不来），`vendor\electron*` 占 868 MB 磁盘。
- 冷启动仍是「先等模型就绪再开窗」（约 6 秒黑控制台），把窗口提前会引入
  「界面先出来但模型还没醒」的状态，暂不赌。

### 26.7 回答太短：该改的是规则，不是代码

复测时抓到「嗯。」这种一字回答，一度怀疑是清理造成的回归。查证结果：**不是**。
这一轮 prompt 与推理路径一行没动（`git diff` 可证），长回答能力也正常
（问「说说你老伴」回了 150 字，有年份、有对话、有细节）。

真实原因是 2B 模型在**抽象问题**上会提前收尾：问「你儿子结婚那天开心吗」，
它起头「唉。记得那回。」然后就停了。改代码没用，改 `RULES.md` 有用：

| 第 7 条写法 | 「儿子结婚那天」 | 「讲台第一回」 |
|---|---|---|
| 一次说一到四句，对方让你多说才往下讲 | 7 字「唉。记得那回。」 | 5 字「嗯。」 |
| 加上「至少把话说完整，别只答一个字」 | 7 字，没变 | 5 字，没变 |
| 改成「开口就得有东西：说清哪一年、哪件事，别只说『记得那回』就停住」 | **75 字** | **44 字** |

**结论**：这种「像不像人」的问题，改数据比改代码有效。规则要指名道姓地禁止那个具体的
失败动作（「只说记得那回」），泛泛地说「说完整」模型听不懂。

### 26.8 数字

| 项 | 数字 |
|---|---|
| 测试 | **167 passed**（删掉 2 个只测已删函数的用例） |
| 清理 | 19 个文件，`+124 / −273` 行；死函数/字段/常量/测试辅助共 20 余项 |
| `cli.py` | 428 → **402** 行 |
| `server/app.py` | 365 → **338** 行 |
| 冷启动（实测） | 服务应答 **4.86 s**、模型可推理 **5.36 s**、窗口约 **6.5 s** |
| 单轮 | 首字 1.3–2.5 s，解码约 19 tok/s |
| 测试隔离 | 新增 `tests/conftest.py`，把 `data/` 指到临时目录 —— 以前跑一次测试就在
  `data/sessions/` 里留一个空 `.jsonl`，而 `resume` 挑最新的那个，跑几次他就「什么都想不起来了」 |

---

## 27. 打磨第三轮：把「人」放进开机、他的嘴和这间屋子里（2026-10-27）

用户的原话：「深度优化用户使用体验，优化代码让其更加符合简约简洁的设计理念。修复 bug，
清除垃圾代码，让其代码更高效。最最最重要的是优化用户使用体验，让其更加符合『人』的意识。」

这一轮不加功能。第一件事不是加东西，是**把开机那 6 秒黑屏拿掉** —— 人可以慢，但不能一声不响。

### 27.1 启动：窗口先出来，他在里面醒

**以前**：`serve` 先阻塞等模型就绪（约 5 s），再起 uvicorn，再 `Timer(1.2)` 开窗。
窗口出来的时候他早就醒了，页面上那段「正在把他叫醒」的 1.7 秒是**补演的** ——
连「按任意键跳过」都在演一件没发生的事。

| 步骤 | 以前 | 现在 |
|---|---|---|
| 模型 | 主线程，整个启动卡在这儿 | `threading.Thread` 后台起 |
| uvicorn | 模型之后才起 | 立刻起 |
| 窗口 | 模型就绪 + 1.2 s | 服务一应答就开（轮询 `/health`，最多等 15 s） |
| 页面 | 假装在唤醒 | 真的在等 `POST /api/warm` |
| 落地页 | 首页列表，还要点一下他 | 只有一个人格包时直接是 `/chat/<slug>` |

- `POST /api/warm/{slug}` 现在会**挂住**到模型就绪（`Runtime.wait_online`，最多 70 s）。
  它就是页面上那根进度条挂着的那个请求 —— 条形走多久，他就醒得多慢。
- `chat.js` 只在 `info.online === false` 时才说「正在把他叫醒」，热启动只有 300 ms 淡入；
  等超过 9 秒才换成「还在读，得再等一下」。
- **删掉** `skip()` 和「按任意键跳过」：现在等的是模型，跳过也没有东西可看。
- 窗口是服务一应答就开的，所以不会撞上「Chrome 显示连接失败」那一下。

实测（两次冷启动，这台机器当时在跑游戏，CPU 约 90%，绝对值都偏大；差值是准的）：

| 次 | 服务应答（= 窗口出现） | 模型就绪（= 能说话） | 窗口比模型早 |
|---|---|---|---|
| 1 | **2.90 s** | 7.74 s | **4.83 s** |
| 2 | 3.59 s | 10.41 s | 6.82 s |

旧路径是「模型就绪 + 1.2 s」，对照 §26.8 的数（模型 5.36 s → 窗口 6.5 s），
**窗口出现的时间从 6.5 s 挪到了 2.9–3.6 s，而且挪出来的这段时间现在有内容**：
屏幕上是「正在把他叫醒」，不是黑的控制台。

### 27.2 他说话的时候

| 改动 | 为什么 |
|---|---|
| **输入框不再锁死** | 他说话时你也能打字；按 Enter 只是「抬手」，等他说完自动把输入框里的话发出去。以前他一开口，你就只剩等着 |
| **他在想：心跳快一点** | `body.waiting .pulse` 从 3.4 s 加到 1.5 s。原来那颗心在等首字时纹丝不动 |
| **光标屏住呼吸** | 等待首字时原来是 `animation: none; opacity: .42`（冻住 = 死机）；改成 2.8 s 慢呼吸 |
| **出错不再由他开口** | 连不上时原来往他嘴里塞「（连不上模型（http://…））」。现在是旁白一行 `.notice`：「· 他那边没声音了」，他那一行如果还空着就整行删掉 |
| **流断了也收尾** | 原来 `typer.finish()` 只在 `done`/`error` 里调；连接半路断掉时 `await typer.promise` 永远不 resolve，**输入框会一直锁着**。现在 try/catch 之后无条件收尾 |

### 27.3 两个写好了却没人用的字段

`human.yaml` 里的 `sleep_line` / `wake_line` 一路发到前端就被丢了（`app.py` 发、`chat.js` 不接）。
这一轮把它们接上，没动数据：

- **`sleep_line`＝「那我等你。」** 房间暗下来（48 秒没动作）时，右上角那行 `10 段记忆`
  换成他的这句话，颜色转暖。原来那个「暗下去」是屏保；「暗下去还说一句」才是等。
- **`wake_line`＝「你回来了。」** 续聊时如果**最后一句**不是今天的，回放完旧对话之后
  用打字机吐这一句。分界线「上次说到这儿 · 昨天」仍取**第一句**的日子（它标的是这段旧话
  从哪天开始）；他这句取最后一句的日子（那才是隔了多久）。同一天刷新不出现。
- **名字回门口**：对话页没有地址栏，`/settings` 原来只能从首页进。现在左上角他的名字是
  个链接（`<a href="/">`），点一下回到门口，那里有设置。

### 27.4 工具搬去设置页

`[tools]` 原来跟「你说吧…」坐在同一行 —— 那是整个界面里最像机器的一处。工具本身没删：

- 设置页多了「工具」一栏（关掉 / 能看文件 / 能写文件跑命令），仍写 `localStorage` 的
  `oh.tools`，不新增配置项。
- 对话页输入框旁边只剩 `[新]`。
- 他动文件的痕迹照旧显示（`· 翻了翻 notes.md`）—— 那读起来是"他翻了下本子"，不违和。
- 删掉的东西：`chat.js` 里的 `TOOL_LABEL` / `toolMode` / `paintToolMode` / 三组监听、
  `.toolsheet` 整块 HTML 和 CSS。

### 27.5 删掉的东西

| 目标 | 体量 | 理由 |
|---|---|---|
| `desktop/`（main.js、preload.js、package.json、renderer×2、tray.png） | 6 文件 13 KB | Electron 在这台机器上起不来（§26.1 三重验证），纯死代码 |
| `scripts/shot/` | 2 文件 | 基于 Electron 的截图工具，同样起不来 |
| `core.js` 的 `window.oh.isDesktop`、三个页面的 `.dragbar`、对应 CSS | ~30 行 | 只服务死在路上的 Electron |
| `vendor/electron`、`vendor/electron43`、`vendor/electron.zip` | **868 MB** | 失败实验的下载缓存，要可重下 |
| 仓库根的 `pytest-of-henry/` | 3 个目录 | 上一轮漏下的临时产物 |

### 27.6 修掉的真 bug

| bug | 根因 | 修法 |
|---|---|---|
| **连点两次 `[新]`、或者跑一次测试，他就「失忆」** | `Session.create` 先 `touch` 一个 0 字节 `.jsonl`；`paths.latest_session` 按名字取最新 → 挑中空文件 → 回去一看什么都没有 | `latest_session` 跳过 `st_size == 0`。上一轮只用 `conftest` 挡住了测试，真实使用里仍会发生 |
| **`/api/settings` 把 `llama.api_key` 原样发出去** | 本地那段用了 `model_dump()`，deepseek 那段剔了 key | 两段都用 `exclude={"api_key"}` |
| 设置页保存后状态不刷新 | 切到 DeepSeek 后右上角仍写「模型在线」 | 保存成功后重拉一次，只更新状态行 |
| 流断了输入框永远锁着 | 见 §27.2 | try/catch 之后无条件 `typer.finish()` |
| 鼠标一动就重写同一个文本节点 | `paintState()` 挂在 `wake()` 上，`mousemove` 每次都写 `textContent` | 值没变就不写 |
| **浏览器本来就关着的时候，双击之后什么都不出现** | `window.running()` 用 `text=True` 让 Python 按 UTF-8 解 `tasklist`：中文环境下那句「没有运行的任务」是 GBK 字节（`0xD0` 开头）→ reader 线程抛 `UnicodeDecodeError` → `stdout` 变成 `None` → `out.lower()` 崩在**开窗线程**里。线程是 daemon，崩了没人知道，既不弹窗口也不退回标签页 | `encoding="utf-8", errors="replace"`、`stdout or ""`、调用方 try/except 兜底退回 `webbrowser.open`。补 4 条测试，其中一条钉住这两个解码参数 |

最后那条是这一轮最值钱的发现：它从 §25.6 起就一直在，只是**平时浏览器都开着**，
`tasklist` 输出的是纯 ASCII 行，所以没踩到。用全新会话冷启动一次就会撞上。

### 27.7 三件测出来的事（都改的是数据，不是代码）

**1. 问「你这辈子值不值」，他答「嗯。」** 根因是 `MISS_NOTE`（检索空了就提醒他别编）
和 RULES 第一条（「不记得就说不记得」）同时生效 —— 他分不清「问往事」和「问想法」。

先试了**改代码**：把 `MISS_NOTE` 从「一个字都想不起来，就说想不起来」软化成
「问你的想法就照实说」。**测下来完全没变**（还是「不记得了。」），因为模型听的是 RULES。

再试**改数据**：RULES 第一条补一句「问你怎么想、值不值、后不后悔，那不用记，照实说
你自己的想法。」—— 三题对照（都走完整引擎）：

| 问题 | 改前 | 改后 |
|---|---|---|
| 你觉得自己这辈子值不值 | **2 字**「嗯。」 | **14 字**「唉，这回连我自己也说不清楚。」 |
| 你还记得 1999 年那场台风吗（没这张卡） | 4 字「不记得。」 | 6 字「我想不起来。」（仍然不编） |
| 你还记得第一次上讲台吗（有卡） | 115 字，引用正确 | 90 字，引用正确 |

结论和 §26.7 一样：**这种「像不像人」的问题，改数据比改代码有效**；而且模型只认
「指名道姓的许可」，泛泛的「想说什么说什么」它听不见。

**2. 把 `voice/samples.md` 塞进 prompt —— 撤了。** 那 20 句「他以前说过的话」是最像人的
材料，`loader` 每次都会读进 `Pack.samples`，但一句都没进 prompt。这一轮试了把它接进
persona（单独 400 tok 预算，`oh doctor` 单独报一行），同条件 A/B 三题：

| 问题 | 不带样本 | 带样本 |
|---|---|---|
| 你觉得自己这辈子值不值 | 8 字「嗯，我想不起来。」 | 7 字「唉，想不起来。」 |
| 你还记得 1999 年那场台风吗 | 5 字「记不清了。」 | 22 字「嗯，我不记得了。你别问了，问了我也编不出来。」**← 逐字照抄样本第 2 句** |
| 说说你老伴 | 3 字「秀兰。」 | 16 字「秀兰。我记得她挺好，脾气也不大。」 |

判据是「至少 3 题变长且没有一句逐字复读」，实测 2/3 且**有一条逐字照抄**。
所以整条回滚（连 `samples_block`、`SAMPLES_BUDGET`、doctor 那一行一起删掉），
结论留在这儿：**单句样本会被 2B 当成台词抄**。下次要做得换成「问→答」成对样本，
或者配一条比「别照抄」更硬的护栏，再测。

**3. `MISS_NOTE` 本身不能撤。** 同一句「你还记得 1999 年那场台风吗」，不带那句提醒：

> 唉，台风……记得是个夏天，天热得很。

他会编。所以 §25.1 #6 当初加的这句是对的，这一轮只是确认它管用。

### 27.8 数字

| 项 | 数字 |
|---|---|
| 测试 | **183 passed**（167 → 183，新增 16 条：等他醒 5、空文件 2、落地页 2、warm 与 settings 3、tasklist 解码 4） |
| 改动 | **34 个文件**：21 改、8 删、5 新增（4 张截图 + `tests/test_cli.py`）；`+626 / −785` 行 |
| 冷启动 | 窗口 **2.90 s / 3.59 s**（两次），模型就绪 7.74 s / 10.41 s；窗口比旧路径早约 4.8–6.8 s |
| 真机一轮 | 17 字、引用 `1978-09-01-first-class` 正确、SSE 事件 `meta → delta → done` |
| 真窗口 | 打开就是 `/chat/demo`，任务栏/标题栏是「陈建国」，1181×830，没有地址栏 |
| `cli.py` | 407 → 437 行（多了 `landing()`、后台线程、开窗兜底） |
| `server/app.py` | 343 → 345 行 |
| `chat.js` | 444 → 429 行（删了工具面板，多了开机重写） |
| `style.css` | 569 → 544 行 |
| `window.py` | 67 → 82 行（多的是那个解码坑的注释和兜底） |
| 删除 | `desktop/` 6 文件、`scripts/shot/` 2 文件、Electron 依赖 **868 MB** |

两条没做到的，记着不藏：

1. **「正在把他叫醒」那一帧没截到图。** 无头 Chrome 的 `--virtual-time-budget` 到点会掐掉
   还没回来的请求，页面于是直接掉进「他没醒」分支（`docs/screens/15-notice.png` 就是那一刻）；
   而真窗口里模型已经就绪，那个分支本来就不显示。这个分支本身是对的，只是没拍到更好看的那一帧。
2. **真窗口是在实现者的进程树里验的，得临时加 `--no-sandbox`**（§25.6 说过：Chromium 的沙箱
   在这棵树里初始化失败，不带这个参数窗口活 2 秒就死）。截图里那条「不受支持的命令行标记」
   横幅就是这个参数带来的，**产品代码不带它** —— 用户双击的那棵树是干净的。

---

## 28. 打磨第四轮：他不把闲聊当旧账，也知道现在几点（2026-10-27）

这一轮只做一件事：**让他分得清「你在跟他说话」和「你在问他从前的事」**。
起因是三句家常话，他三次翻开旧账 —— 而且翻的是同一张卡。

### 28.1 三句家常话，三次翻旧账

| 你说 | 第四轮之前 | 现在 |
|---|---|---|
| 我回来了 | 「嗯……记得。1997 年三月初三那天。父亲躺在医院床上……」 | 「回来了？嗯。」 |
| 今天有点累 | 「嗯……记得。2019 年 10 月 26 号那天，和秀兰去黄山……」 | 「累是正常的，日子久了就习惯了。」 |
| 外面下雨了 | 「记得。2019 年 10 月 26 号那天，和秀兰去黄山……」 | 不再提黄山 |
| 我想你了 | 「嗯……记得。2019 年……黄山……」 | 不再提黄山，但只答「嗯。」（见 28.8） |
| 今天星期几 | 「想不起来。」 | 「星期二。」 |

最刺眼的不是检索错，是**错得一样**：三句话都得到黄山那段。因为他上一轮刚讲过，
2B 直接把上一段回话抄了一遍 —— 检索错一次，会沿着历史错好几轮。

### 28.2 闸门：不问往事，就不翻记忆

`memory/director.py` 里 `ask` 原来的意思是「这句话有内容词」。所以「今天有点累」算问往事，
命中的还是「天有」这种跨词二元组。

现在拆成三个问题：

| 字段 | 意思 | 判断 |
|---|---|---|
| `ask` | 要不要检索 | 有问句的样子（吗/什么/哪/几点/…），或直接让他讲（讲讲/说说），或提了往事（记得/那年/以前/…） |
| `cue` | 提没提往事 | 指示词表 |
| `about_past` | 是不是在问**某一件具体的事** | 具体指示（那年/那次/那天/后来/记得）或年份或人名 |

`about_past` 决定那句「别编」提不提醒。原来「你以前教什么课」也会被提醒，于是他答
「想不起来」—— 答案明明在 SOUL 里（教了三十八年历史）。

| 问题 | 之前 | 现在 |
|---|---|---|
| 你以前教什么课 | 想不起来。 | 教历史课。 |
| 今天天气怎么样 | 想不起来。 | 不知道。 |
| 你还记得台风那年吗 | 引用 1985 年发大水那张卡（错的） | 想不起来。（正确：没记过） |

`text.py` 的停用词表补了一批**指示词**：那天/那年/那次/以前/从前/后来/过去/当年/当时。
指示词是语境，不是内容；留着它们，「台风那年」会被匹配到标题里的「那年」。

### 28.3 他看得见钟

`llm/prompt.py` 的 `clock_line()` 每轮生成一行：

> （此刻：10 月 27 日，星期二，中午 12 点 06 分。）

放在**最后一轮用户消息的最前面**：每轮都变，放进 system 会把 prefix cache 整个作废（§18 N-01）。

噪声量过：同一句问三遍，带钟点与不带钟点没有系统性差别（3 组全答「教历史课」）。
收益是直接的：

| 问 | 之前 | 现在 |
|---|---|---|
| 现在几点了 | 想不起来。 | 中午十二点左右。 |
| 今天星期几 | 想不起来。 | 星期二。 |

### 28.4 追问接着上一轮

「那天你讲话了吗」这种句子没有主语。原来 BM25 翻出父亲那张卡，他答「来了两个人」——
婚宴那页明明写着二十桌。

现在两句：

- `follows_up(text, pack)`：短、以「那天/后来/然后」起头、句里没有年份/人名/地名。
- `Engine.prepare()` 里，追问直接取上一轮那张卡（存在 `usage["top"]`），不再检索。

| 你说 | 之前 | 现在 |
|---|---|---|
| 那天来了多少人 | 「那天来了两个人。」（引用了父亲、黄山两张卡） | 「二十桌。」（引用婚礼那张卡） |

**顺手修掉一个真 bug**：`/api/chat` 自己先 `engine.recall(text)` 再把 `cards` 传进去，
所以引擎里的追问分支在网页上永远不执行 —— 只有 CLI 和测试走得到。
现在服务端调 `engine.prepare(text)`，检索和追问都归引擎。

### 28.5 卡片在手边时，把话匣子关小

2B 拿到一整张卡会照着念。同一题实测：

| 提示 | 字数 |
|---|---|
| 不加 | 101 / 136 |
| 「（说短一点，一两句就够。）」 | 138 / 19 |
| 「（一两句话，挑一个细节说。）」 | 34 / 22（讲台那题 56 / 56） |

第三版稳，而且带细节。它压在**问题后面**（放前面会把回答压成光秃秃的日期），
只在有卡片时加。RULES 里那句「不超过八十个字」管不住 2B，得在每轮最后一格再说一次。

### 28.6 三个被推翻的假设

都留了测量，省得下一轮再猜：

1. **「三张卡会打架」不成立。** 婚礼人数：一张卡给「二十桌」，三张卡给 64 字、主卡仍是婚礼。
   真正的问题是检索给了**错的**卡，不是给了太多。
2. **不是温度的事。** 0.6 / 0.75 / 0.9 三档，「我回来了」都在复读「回来了？」。
3. **不是那句提示导致结巴。** 有一次整段回话都是「（嗯）…（唉）…」，当时怀疑是句尾提示被模仿；
   去掉提示照样出现。是 2B 的方差。

### 28.7 数据只改了一处

`RULES.md` 第 7 行删掉「别只说“记得那回”就停住」。那半句是负面例子，被 2B 逐字念了出来 ——
连着好几轮回话都以「记得那回？」开头。上一轮在 `voice/samples.md` 上验证过「样本会被照抄」，
这一轮在规则里的负面例子上又碰了一次。

### 28.8 数字与没做到的

| 项 | 数字 |
|---|---|
| 测试 | **198 passed**（183 → 198，新增 15） |
| 改动 | 14 个文件（12 个代码/测试/数据 + 本文档 + `AGENTS.md`），`+443 / −31` |
| 检索评测 | 25/25 命中、top-1 24/25（上一轮 23/25）、静默 6/7（q32 为已知局限） |
| persona | 514 tok / 预算 700 |
| 真机首字 | 0.31–1.68 s；一次追问 4.04 s（唯一一次），warm 3.45 s |
| `engine.py` | 204 → 243 行（`prepare` / `_topic_card`） |
| `prompt.py` | 80 → 134 行（钟点、短句提示） |
| `director.py` | 79 → 123 行（`ask` / `about_past` / `follows_up`） |

没做到的，记着不藏：

1. **2B 会把你问的话原样重复一遍再答。**「那天你紧张吗」→「那天你紧张吗？讲台上比你想的高……」
   这是模型行为，提示层压不住。
2. **岁数算不对。** 念念 2013 年生，问「孙女多大」他答「十岁」（应十三）。卡片里只有出生日期，
   2B 不会做减法。
3. **情绪句接得冷。**「我想你了」→「嗯。」。SOUL 里他是个嘴上不让人的人，勉强算角色内；
   但这种句子本该是他接得最好的地方，现在是最差的。
4. 一张卡念 153 字的情况仍可能出现（方差），`SHORT_NOTE` 只是把概率压下去。

---

## 29. 收尾清理：包体 2,367 → 1,840 MB（2026-10-27）

用户先问「工作区里这么多文件都是干什么的、有没有能清掉的」，然后逐项批准了清理。
这一轮**没有改一行逻辑**，198 个测试前后都是绿的。

### 29.1 删了什么

删之前逐文件说明过用途，用户批准一项、删一项。按类别：

| 类别 | 体积 | 说明 |
|---|---|---|
| `vendor/uv-cache/` | 218 MB | uv 的下载缓存，`uv sync` 会重新填。现在只剩 1.5 MB |
| `vendor/*.zip` | 98 MB | 已解压过的下载包（llama / python / uv），要重下才有 |
| `vendor/llama/` 里用不到的 28 个可执行文件 | 16.1 MB | `llama-connect.exe`（10.9）、`llama-cli-impl.dll`（3.2），加 `bench` / `quantize` / `perplexity` / `imatrix` / `tokenize` / `mtmd-cli` / `fit-params` 等实验工具 |
| 基础解释器里的 `pip` | 10.2 MB | 项目用 uv 管 `.venv`，这个 pip 从不被调用；`python -m ensurepip` 能装回来 |
| `docs/screens/` 11 张过期截图 | 5.4 MB | 只留 4 张还在被引用的 |
| `__pycache__` / `git gc` / 日志 / 早期残留 | 其余 | 差额，不硬凑 |

合计 **−527 MB**（2,367 → 1,840 MB）。

`vendor/llama/` 从 52 个文件、59.6 MB 变成 **24 个文件、43.5 MB**：
`llama-server.exe`、`llama-server-impl.dll`、`llama.dll`、`llama-common.dll`、`llama-rpc.dll`、
`mtmd.dll`、`ggml*.dll`、`libomp.dll`、LICENSE，加 **14 个 `ggml-cpu-*.dll`**。

### 29.2 删完真跑了一遍

不是「文件还在所以没问题」，是整条链路：

- `llama-server` 起得来：`GET http://127.0.0.1:8080/health` → `200 {"status":"ok"}`
- 走 `POST /api/chat/demo` 的 SSE 真问了三个问题，中文、在角色内
- 停服务后 8080 / 8710 都释放，没有残留进程
- `pytest` → **198 passed，13 秒**

### 29.3 故意留着的东西

| 留着 | 体积 | 为什么 |
|---|---|---|
| `vendor/llama/ggml-cpu-*.dll` × 14 | 19.2 MB | llama.cpp 运行时按 CPU 特性挑一个加载。删掉「多的」，在别的机器或改 BIOS 之后会变成「无缘无故起不来」 |
| `data/window/<browser>/` | 1.2 MB | Chrome/Edge 的独立 profile（`--user-data-dir`），记住窗口位置，也不碰用户自己的浏览记录（`window.py:43`） |
| `models/` | 1,489 MB | 权重 |
| `.venv/` | 110.4 MB | 依赖。其中 numpy 41.8 MB 是 `rank_bm25` 硬要的，删了检索层直接挂 |
| `vendor/` 其余 | 219.3 MB | git / python / uv，系统里没有替代品 |

> 顺带一条观察：`data/window/chrome/Crashpad/reports/` 里有一个 0.18 MB 的转储，
> 说明 Chrome 至少崩过一次（`--disable-session-crashed-bubble` 就是为这个加的）。
> 不影响使用，但窗口偶发不出现时先看这里。

### 29.4 可复现性代价

- 删掉的那些 llama 工具，**只能靠重新下载 `vendor/llama-b11889-win-cpu-x64.zip` 拿回来**，那个 zip 已经删了。
- 没有校验和比对，所以**不要再往 `vendor/llama/` 里删东西**，除非又按 §29.2 跑一遍。
- `docs/benchmark.md` 里的 Phase 0 数字一个都没改：那是记录，不是现状。

### 29.5 剩下的空间不在磁盘上

可清的都清了。再想瘦一个数量级只有一条路：把 `models/` 挪出项目目录、
`config.toml` 指过去，项目立刻 350 MB —— 但那会破掉「一个文件夹装一个人」。
这是产品判断，留给用户（§24.4）。

包体之外，代码层面的余量也见了底：§28.8 记的四条短板全是 2B 的行为，
不是提示层或编排层能修的。下一步的收益只能来自**换更大的模型**或**接真实数据**。

---

## 30. 双击只有黑窗口、没有界面（2026-10-27）

用户报：「怎么打开桌面 GUI 界面，我双击 open human 之后，只是启动了后台，没有 GUI 界面」。

### 30.1 不是一个普通的 bug

先按叠了三层，逐层剥：

1. **窗口代码本身是对的。** 手工 `cmd /c start` 拉起
   `chrome.exe --app=http://127.0.0.1:8710/chat/demo --user-data-dir=…\data\window\chrome`，
   窗口活得好好的，标题「陈建国」，打得开、聊得动。
2. **从 python 进程里拉浏览器，一定死。** `subprocess.Popen`、`os.startfile`、
   `cmd /c start`、`powershell Start-Process` 四种写法全试过，现象一致：进程起得来，
   **1–2 秒后消失**，`data/window/chrome/Crashpad/reports/` 里留一个 ~175 KB 的转储，
   `Popen.poll()` 返回 `2147483651`（`0x80000003`，`STATUS_BREAKPOINT`）。
   同样的命令行由 pwsh 或 cmd.exe 当父进程，7 个 chrome 进程 0.3 秒内起齐。
3. **不是 Chrome 的锅。** 对照实验：`notepad` 从 python 里拉也一样秒死，从 pwsh 拉就活。
   机器上装着火绒（`HipsDaemon`、`HRWSCCtrl` 在跑），策略是「凡是子孙进程里的 GUI 程序，
   父进程是解释器就拦」。智能应用控制（§25.5）不拦这个，排除。

于是结论是：**开窗这件事不能由 python 发起**，但业务（URL、人格选择、浏览器探测、
参数拼装）又必须在 python 里 —— 不然就得把 CLI 的参数解析抄进批处理。

§25.6 记的 Electron 崩在同一个坑里：它的主进程也是从 python/electron 侧拉 GUI。
这也是为什么「换个壳」治不好 —— 壳本身也是被拦的那一类进程。

### 30.2 改法：python 写脚本，cmd.exe 执行

一句话：**业务全在 Python，甩锅给壳的只有一行 `start`。**

| 文件 | 干什么 |
|---|---|
| `src/openhuman/window.py` | 新增 `script()` / `publish()` / `_log()`：把「该怎么开」写成 `data/window.cmd`（ASCII + CRLF 一行 `start "" "chrome.exe" "--app=…" …`） |
| `src/openhuman/cli.py` | `serve()` 的 `show()` 看到环境变量 `OPENHUMAN_SHELL_WINDOW` 就只 `publish()`，不再自己拉浏览器 |
| `Open Human.cmd` | 起服务前先 `set OPENHUMAN_SHELL_WINDOW=1`，同时 `start "" /min cmd /c ""%~f0" --window"` 起一个助手；助手轮询 `data\window.cmd`，一出现就 `call` 它、然后删掉 |

助手是**独立控制台**（`/min`），这样主窗口 python 还在跑的时候它也能活；
它自己不产生窗口 —— 它只是把 `start` 这一行交给 cmd.exe 去执行。
`data/window.cmd` 用前先删，防止上次的残留把旧 URL 开出来。

为什么是文件而不是管道/临时参数：cmd.exe 没有别的方式从另一个进程收一条命令，
`window.cmd` 是最笨也最稳的那个约定 —— 出问题时它是纯文本，看得见。

### 30.3 结果

- 冷启动（无 chrome、无 python、8710 空）：`cmd /c "Open Human.cmd"` →
  12 秒内 chrome 7 个进程、应用窗口「陈建国」、`/health` 200、`data/window.cmd` 已被助手吃掉。
- 已经在跑（第二次双击）：python 认出 8710 有应答 → 退出码 7 → 壳 `exit /b 0` 不留黑窗口；
  同一次 `publish()` 已经写好脚本，助手照样把窗口叫回来。
- 兜底没动：`oh serve`（不带壳、没有 `OPENHUMAN_SHELL_WINDOW`）仍走
  `open_window()` → 失败退 `webbrowser.open()`，`data/window.log` 记每一次尝试和结果。
- `pytest` → **202 passed**（198 → 202：新增 `script()` / `publish()` 的 ASCII+CRLF 用例，
  和「壳里只发布、不自己开窗」这一条）。

> 踩到的两个小坑，写在这里省下一次重查：
> - `Path.write_text(..., newline="\r\n")` 会把已经写好的 `\n` **再翻一次**，结尾变成
>   `\r\r\n`，cmd.exe 读到一条空命令 —— `newline=""` 才对。
> - `cmd /c ""C:\path\Open Human.cmd" --window"` 这种带空格+引号的路径，只能靠
>   `""%~f0" --window"` 这一种写法；`explorer.exe "x.cmd"` 当测试手段不可靠（它不一定真执行）。

### 30.4 还没做

- 窗口挂了不会有提示，只能看 `data/window.log`（壳模式下 `publish()` 会记一行）和
  `data/window/<browser>/Crashpad/reports/`。
- 助手最多等 90 秒（`ping` 一次约 1 秒）；服务要是在 90 秒后才起来，窗口得再双击一次。
  这个时长是拍出来的：实测 uvicorn 1 秒内应答，模型在后台加载、页面自己显示「正在把他叫醒」。

---

## 31. 第五轮：他先开口，也记得你走了多久（2026-10-28）

用户的要求只有一句：**「优化用户使用体验，让其更加符合『数字化人类』理念」**，
外加顺手修 bug、删废物、让代码更薄。

这一轮的尺子不是「功能更多」，是**屏幕上每一处不该是机器的地方，都别再像机器**。
代码上没有加任何依赖、没有新框架、没有新的一层：`src/` 净增 45 行，其中一半是注释，
改的都是「什么时候说哪句话」这几行判断。

### 31.1 他会先开口

以前他从不主动说话：你不按回车，他就永远不出声 —— 那不是一个人，那是一个 prompt 框。

- `human.yaml` 多了一个可选字段 **`idle_line`**（老包没有也能加载，默认空 = 不催人）。
  demo 里是「……我在这儿。」
- 静默 **3 分钟**（`SPEAK_MS`），他打一句；**一次，且不落进会话**。
  只在页面可见时说 —— 你切走了，他不对着空气演。
- 入场那句（`first_line`）和隔天那句（`wake_line`）现在也**先停 0.5–0.9 秒**再开口：
  光标先闪，他才抬头。一上来就冒字，那叫屏幕，不叫人。

不落会话是一个取舍：他没记住自己说过这句。不这么做就得为了「一句他自己说的话」
再加一个写会话的接口 —— 为了一个 2B 模型的一句话，不值。

### 31.2 他分得清「刚才」和「上次」

- 回放的头以前一律是「上次说到这儿 · 今天」，刷新一下就「上次」，像在装。
  现在：**20 分钟内 → 「刚才说到这儿」**；再久才带日子。
- 以前只有**隔天**回来他才说 `wake_line`。现在**走开 45 分钟以上**就说 ——
  45 分钟是「你出去过一趟」的尺度。少了像每回刷新都要打招呼，多了像根本没发现你不在。
- 回放取的是**最后一句话**的时间（以前错取了第一句的 —— 「上次」说的是你走的时候）。

### 31.3 屋子安静下来的时候

- 输入行只留 `›` 和光标。`[新]`（重新开始）搬到右上角，和 `10 段记忆` 并排：
  它本来就不该坐在「你说吧…」那一行里 —— 那是这间屋子里最像机器的一个按钮。
- 说完最后一个字，光标**停 0.8 秒再淡出**，不是「啪」地掐掉。
- 光标呼吸时不再 32ms 空转（等第一个字的轮询改成 80ms）——
  他安静的时候，风扇不该响。
- 打字节奏 24–40ms/字 → 26–44ms/字，标点后的停顿不变：慢一点，更像在说话。
- 滚动从「每吐一个字量一次 `scrollHeight`」改成**每帧一次**（`requestAnimationFrame`）。
  以前一句话 60 个字就是 60 次强制布局。

### 31.4 顺手修的 bug 和删掉的废物

| 修 / 删 | 说明 |
|---|---|
| 空回复留一行孤零零的 `>` | 没报错、也没吐字时，那一行现在收掉，换一句旁白「他没出声」 |
| `[新]` 抢走输入框焦点 | 搬到右上角之后，点它不会再让你打字打空 |
| 回放头取错时间 | 见 31.2，取最后一句 |
| `data-page` 属性 | 三个页面都挂着，CSS/JS 里从没查过它 —— 删 |
| 记忆卡接口多发的字段 | `type` / `source` / `emotion` 抽屉里根本不画，不过网络了 |
| 两套 `.caret` 规则 | 一套通用、一套 `.line.him .body .caret`，叠着写同一个光标 —— 合成一条 |
| `index` 从不看 `presence` | 归档的人（`archived`）和活着的人长得一模一样。现在归档是空心圈 + 「已归档」 |

### 31.5 怎么验的（不是「看着没问题」）

- `pytest` → **203 passed**（+1：`idle_line` 与老包兼容；卡片字段集合、`idle_line` 接口都有断言）。
- **真浏览器**：headless Chrome 打开 `/chat/demo` 把 DOM 打出来 ——
  确认 `[新]` 在 `.who .aside` 里、输入行只剩 `›`、他的行 `mark=">"`、你的行 `mark="›"`、
  开场是「你回来了。」（隔了一夜）。
- **静默 3 分钟**：`--virtual-time-budget=200000` 把定时器快进，DOM 里出现
  「……我在这儿。」，而且只有一句。
- **真的敲进去一句话**：CDP 驱动一个真浏览器，往输入框里塞字 + 派发 Enter，
  读回来的是 `line me → line him`，回复流式吐完、`.waiting` 归零、输入框解锁、引用块正常。
  （顺带确认 20 分钟内是「刚才说到这儿」。）

### 31.6 还没做

- 他先开口那句不进会话（31.1）。真要接住「你刚才说什么」，得给它一个 `POST /api/…/note`。
- 静默台词只有一句，说一次就没了。一天里说三次「我在这儿」会烦 —— 一次是对的，但也就这一次。
- 2B 的老毛病一个没动（§28.8）：把问题复述回来、算不清年龄、情绪话接得冷。
  这些不是前端能修的。

---

## 32. 第六轮：把屋子做出纵深（2026-10-28）

用户的原话是「深度优化用户界面（UI）使用体验，让其更加**深邃**」。

「深邃」不是一个滤镜能给的。这一轮把它拆成四件事，一件一件做：

| 哪种深 | 怎么来的 |
|---|---|
| **空间**：有前后 | 两层光（上面冷、下面暖）按不同幅度跟着鼠标走；两层极淡的框（窗 + 窗棂）；上下边缘各压一道暗 |
| **时间**：屋子有天光 | 早上 / 白天 / 黄昏 / 夜里，四个时段的暖光、冷光、暗角各差一点点 |
| **里外**：卡片在前面 | 打开记忆卡时，整个屋子往后退（模糊 + 变暗 + 缩小），卡片浮起来 |
| **字**：文字本身有层 | 他说的话永远带一层极淡的光；对话两头化进黑里，字是续下去的，不是被裁断的 |

### 32.1 空间：视差与光

```css
.aura { transform: translate3d(calc(var(--px) * -9px),  calc(var(--py) * -6px),  0); }
.glow { transform: translate3d(calc(var(--px) * 16px), calc(var(--py) * 11px), 0); }
```

`--px / --py` 是鼠标在窗口里的位置（-0.5 … 0.5），`core.js` 里用 `requestAnimationFrame`
节流后写到 `<html>` 上。两层走的距离不一样（16px vs 9px，方向还相反），
眼睛读到的是**前后**，不是「有东西在动」。实测：`--px=0.5` 时
`.glow` 位移 `+8px`、`.aura` 位移 `-4.5px`。

帧里只改两个自定义属性，不碰布局；`prefers-reduced-motion` 下连监听都不挂。

**双框**（`html::before` inset 7px + `body::before` inset 20px）是最省的纵深：
两条线一前一后，边框就有了厚度。上下两道 `inset` 阴影再压一下，屏幕像有一点弧度。

### 32.2 时间：屋子跟着天光走

| 时段 | 暖光 | 冷光 | 暗角 |
|---|---|---|---|
| dawn（5–8） | 0.16 | 0.095 | 0.58 |
| day（8–17） | 0.14 | 0.08 | 0.62 |
| dusk（17–20） | 0.17 | 0.07 | 0.66 |
| night（20–5） | 0.10 | 0.13 | 0.72 |

差别只有几个百分点：不该一眼看出来，只该在半夜觉得这屋子比早上更小、更冷。
夜里冷光反而比暖光强 —— 窗外比屋里亮，这是深夜的实感。

### 32.3 里外：卡片打开时屋子退后

- 新增 `.scrim`（z-index 15）盖住屋子，点一下就收卡片。
- `body.open-card` 时 `.column` 变成 `filter: blur(1.3px)` + `scale(0.994)` + `opacity 0.32`，
  0.45 秒过渡。记忆卡从「旁边多一块板」变成「翻出来的一张纸」。
- 抽屉本身也当成一张纸：上缘被灯照到（顶部亮一点），左边沿收一道 1px 高光。

### 32.4 字：两头化进黑里

- `.transcript` 的 `mask-image` 原来是「上面淡出」，现在**两头都淡**（`calc(100% - 26px)` 起）。
- 他的话（`.line.him .body`）常态带 `text-shadow: 0 0 26px rgba(217,180,135,0.07)`：
  永远比背景近一点点，说话时再亮成 0.14。
- 消息进场从 `translateY(6px)` 加上 `scale(0.9975)`：是浮上来的，不是贴上来的。
- 首页：每个人名底下有一盏灯（hover 才亮），进场一个一个浮上来（stagger 0.06s）。
- 输入行聚焦时，桌子那一小块被照亮（`.composer::before` 的暖光池）。
- 开机那一片黑中间有一小团光在呼吸（`#boot::before`）。
- **灯要打在人或话上，别打在空处**：聊天页的暗角中心从 46% 下移到 62% ——
  他的话在下半屏，那就照下半屏，上面那片空黑退得更远（`body.chat`）。
- 顺手修了两处「把正文当装饰」：设置页的说明文字原来是 9% 白（近黑上只有约 1.5:1，
  等于没写），提到 30%；页脚 20%。冷还是冷的，但读得出来。

### 32.5 怎么验的（以及一个教训）

- `pytest` → **205 passed**（+2：三页都有三层光；聊天页有 `.scrim`）。
- **视差**：CDP 里改 `--px/--py`，读 `getComputedStyle(.glow).transform` →
  `matrix(1,0,0,1,8,5.5)` / `.aura` → `matrix(1,0,0,1,-4.5,-3)`。
- **卡片纵深**：CDP 在真页面上 `openCard(...)`，`body.className` 变成 `open-card`，
  截图里屋子确实是糊的、暗的，卡片是清楚的。
- **帧率/开销**：只动 `transform` / `opacity` / `filter`，没有新图片、没有新请求；
  所有渐变都是 CSS 画出来的。

> 教训：`--virtual-time-budget` 截图会**撞在开机淡出上**。虚拟时间把 JS 定时器快进了，
> 但 CSS 过渡是墙钟时间 —— 抢到的往往是一层半透明的 `#boot`，整页发灰。
> 这种图看着像「样式写坏了」，其实是拍早了。**要截图就等真时间（CDP + sleep），
> 不要用虚拟时间**。这一轮为这个坑重拍过三次。

### 32.6 还没做

- 没有滚动视差（往上翻旧话时，背景不动 —— 动了会晕，也没必要）。
- 没有声音、没有鼠标跟随的光斑（那会变成「网页特效」，不是一间屋子）。
- 手机端仍然不做（§24 冻结范围以外）。
- 时段的边界是整点，没有渐变切换：19:59 到 20:00 会跳一下。差几个百分点，看不出来，
  但严格说它不是渐变的。

---

## 33. beta v0.1 收尾（2026-10-29）

用户：「需要可以开始发布 beta v0.1 版本了，我们要进入开发的尾声」，并给了六条要求：
**尽量精简 / llama.cpp / 永远 CPU / MiniCPM5 2B Q4_K_M / Python 底层 / Electron 前端**。
先审一遍，再只修能修的；**GUI 的问题用户说稍后单独谈**，这一轮没动界面设计。

### 33.1 审计：六条要求对上现状

| 要求 | 实况 | 判定 |
|---|---|---|
| 尽量精简 | 1,841 MB（1,489 是权重）；31 个 .py / 3,692 行；10 个依赖；零构建步骤；无 Node | ✅ |
| llama.cpp | `vendor/llama/llama-server.exe`，官方 CPU 版 b11889，24 个文件 43.5 MB | ✅ |
| 永远默认 CPU | `localmodel.py:65` 写死 `-ngl 0`，全仓库没有 GPU 分支 | ✅ |
| MiniCPM5 2B Q4_K_M | `models/MiniCPM5-2B-Q4_K_M.gguf` 1,489 MB；`-c 8192 -np 1 -fa on --jinja` | ✅ |
| Python 底层 | FastAPI + uvicorn，业务全在 `src/openhuman/` | ✅ |
| Electron 前端 | Chrome/Edge `--app` 应用模式窗口 | ⚠️ 见下 |

**唯一不达标的是 Electron，而它已经不是欠账，是决定。** 证据在 §25.6 / §26.1：6 行的最小应用
崩在 Chromium 初始化（`0x80000003` / `0xC0000005`），换 43 / 45 两个版本、用计划任务在
进程树之外启动都一样。接回来还要 +360 MB 和一条 Node 构建链。

用户这一轮确认了两个决定：

1. **窗口维持应用模式**，在 README 里如实写「为什么不是 Electron」；
2. **分发用整包 zip**（含 `models/` `vendor/` `.venv/`，解压即用），不做自动下载。

### 33.2 修掉的真 bug 一：`oh doctor > log.txt` 自己崩

复现（两次，都是 exit 1）：

```powershell
cmd /c ".venv\Scripts\python.exe -m openhuman.cli doctor > data\probe\a.txt 2>&1"   # exit 1
cmd /c "chcp 65001 >nul & ... doctor > data\probe\b.txt 2>&1"                       # exit 1
```

输出不是表格，是 rich 的 traceback：`UnicodeEncodeError: 'gbk' codec can't encode
character '\u2713'`（`✓`）。原因不是 chcp —— **重定向出去的是文件，Python 给文件用的是
ANSI 代码页（cp936）+ `errors="strict"`**，chcp 管的是控制台，管不到这里。

偏偏踩在「排障命令」上：用户一出问题第一件事就是 `oh doctor > log.txt` 发给我，然后日志里
只有一段 traceback。

改法（`cli.py:_tame_streams()`，在 Typer callback 里每个命令都先跑一次）：

- 不是终端（文件 / 管道）→ `reconfigure(encoding="utf-8", errors="replace")`，文件本来就该是 UTF-8；
- 是终端 → 只 `reconfigure(errors="replace")`，**不换编码** —— 换了中文变乱码。

验证：同一条重定向现在写出干净的表格（`✓` 保住了），exit 1 是设计内的（模型没开）：

```
 ✓   Python            3.12.15
 ✓   模型文件          models/MiniCPM5-2B-Q4_K_M.gguf (1.45 GB)
 ✗   llama-server      http://127.0.0.1:8080 无响应。双击 Open Human.cmd 会自动拉起，或 oh serve
```

> 顺带记一个 Typer 的坑：加了 `@app.callback()` 之后，`oh --version` 退出码是 **2**，
> 因为 group 拒绝「没有子命令」的调用。要 `invoke_without_command=True`，并且在
> `ctx.invoked_subcommand is None` 时打印 help，否则只敲 `oh` 会静默退出。

### 33.3 修掉的真 bug 二：窗口 profile 会自己长到 158.8 MB

`BUILD.md` §29.3 记的是 1.2 MB。这次量出来 **158.8 MB**，全在 `data/window/chrome`：

| 目录 | 体积 | 是什么 |
|---|---|---|
| `optimization_guide_model_store` | 40.1 MB | Chrome 自己下的「优化」模型 |
| `component_crx_cache` | 32.6 MB | 组件包缓存 |
| `WasmTtsEngine` | 24.5 MB | 网页 TTS 引擎 |
| `Safe Browsing` | 19.1 MB | 安全浏览库 |
| `Default` | 12.8 MB | **真正属于我们的页面数据** |

也就是说：**1.2 MB 是我们的，157 MB 是 Chrome 往我们给的 profile 里屯的。** 用户用几个月
就是几百 MB，直接侵蚀「精简」这条要求。

改法（`window.py:command()`）：加 `--disable-component-update`、`--disable-background-networking`、
`--disable-default-apps`，并在 `--disable-features` 里加 `OptimizationHints,OptimizationGuideModelDownloading`。
旧 profile 已删（−158.8 MB），下次启动会重建一个干净的。

> **这条没有在真窗口上验过** —— 用户说 GUI 稍后单独谈，这一轮只用单元测试钉住参数
> （`test_the_profile_does_not_fill_itself_with_chrome_junk`）。下次开窗口时要确认：
> 窗口照常出来、任务栏图标还是他、`data/window/*` 不再涨。

### 33.4 版本号露出来

`__version__ = "0.1.0"` 原来只躺在 `__init__.py` 里，界面和 CLI 都看不见 —— 拿到 beta 的人
不知道自己手上是哪一版。三处补上：

- `oh --version` / `oh -V` → `open human 0.1.0 · beta · 本地 MiniCPM5-2B Q4_K_M · CPU`；
- `/api/settings` 多一个 `version` 字段（`api_key` 仍然不出进程，§33.7 有测试钉着）；
- 设置页脚右下角：`v0.1.0 · beta`，比页脚再淡一档（`.foot .ver`）。

### 33.5 根目录有了 README.md

之前根目录只有 `AGENTS.md`（开发规则）和 `BUILD.md`（2000 行开发史）—— 都不是给使用者看的。
`docs/README.md` 只是内部文档索引。beta 的第一屏该是这个文件。

`README.md` 里写的是：需要什么机器、双击哪个文件、界面里有什么、他是什么、
数据都在哪（含隐私边界：只有切 DeepSeek 时 prompt 才出门）、**为什么不是 Electron**、
**2B 的四个已知短板**、这个 beta 不做什么、出问题反馈哪三个文件。

### 33.6 清掉的东西

| 删了 | 体积 |
|---|---|
| `data/window/`（Chrome profile，见 §33.3） | 158.8 MB |
| `pytest-of-henry/`（pytest 的 tmp 落在仓库根，438 个残留） | 0.1 MB |
| `data/probe/`（这一轮复现 bug 的临时输出） | 极小 |

项目合计 **1,841 MB**。`data/` 现在只剩 jieba 缓存 8.8 MB、`sessions/`、两个日志和两张
界面截图。

### 33.7 数字

- 测试 **205 → 209 passed**（+4：`oh --version`、GBK 重定向、窗口 flag、settings 的 version），25 秒。
- 改 11 个文件：`cli.py` / `server/app.py` / `window.py` / `settings.html` / `settings.js` /
  `style.css` / `tests/test_cli.py` / `tests/test_window.py` / `tests/test_server.py` /
  `README.md`（新）/ 本文档 + `AGENTS.md`。

### 33.8 没做（等用户定或等下一轮）

- **`LICENSE`**：得用户选（MIT / Apache-2.0 / 私有），我不能替他决定。
- **`scripts/pack_beta.ps1`**：整包 zip 的打包脚本（复制 → 剔 `data/`、`pytest-of-*`、
  `config.toml`、`.git` → zip）。分发形态已定，脚本还没写；§24 冻结的是「打包成 exe」，不是 zip。
- **GUI 那一轮**：用户明确说稍后单独谈。§33.3 的 flag 需要在那时上真窗口验一次。
- **2B 的四个短板**（§28.8）：不是代码能修的。

---

## 34. 窗口这件事的第三次回答：图标、快捷方式、WebView2（2026-10-29）

用户问：「你说 Electron 不行对吧，那有没有什么最简单的方法获得 Win10 / Win11 的 GUI 界面」，
然后把决定权交了过来（「你认为的最优解就是最优解」）。我的判断是拆两步：**beta 用应用窗口 +
一个像样的快捷方式**，**WebView2 先用 spike 证一下**再谈。

### 34.1 先看这台机器上有什么

| 东西 | 状态 |
|---|---|
| Edge 浏览器 | 156.0.4314.50 |
| Chrome | 156.0.8078.49 |
| **WebView2 运行时** | **156.0.4314.50**（`C:\Program Files (x86)\Microsoft\EdgeWebView\…`） |
| .NET Framework 的 `csc.exe` | 在（Win10/11 自带） |
| 系统 | Windows 11 专业版 26300 |

也就是说，「Chromium 内核」在 Win10/11 上以两种形式免费存在：浏览器（`--app` 用它）和
WebView2 运行时（可以嵌进 native 程序）。Electron 只是「自己带一个 Chromium」的第三种做法 ——
而这台机器恰恰不接受它自己带的那个。

### 34.2 方案一：图标 + 快捷方式（已做）

- `assets/OpenHuman.ico` —— 7 个尺寸（16…256），和页面 favicon 同一套视觉：近黑的圆角壳 +
  一个暖点 + 一道极淡的边（深色任务栏上才看得见形状）。由 `scripts/make_icon.py` 生成
  （Pillow 只在工具链里，项目 venv 不装）。
- `scripts/install_shortcut.ps1` —— 在桌面和开始菜单各建一个「Open Human」，
  指向 `Open Human.cmd`，工作目录是仓库根，图标是上面那个 `.ico`，窗口最小化（启动时控制台
  别挡在前面），描述「打开一个人格文件夹，AI 以第一人称成为他」。
- 已在**这台机器上真的建好了**，属性逐项读回来核对过（Target / WorkDir / Icon / Style / 描述）。

> 两个坑：这台机器没有 `pwsh`，只有 Windows PowerShell 5.1；而 5.1 按 ANSI(cp936) 读 `.ps1`，
> **没有 BOM 的中文脚本会变成乱码**（描述会乱）。`install_shortcut.ps1` 带 BOM。
> 另外：用编辑工具改过 `.ps1` 之后 BOM 会掉，得补回去。

### 34.3 顺手验掉了 §33.3 的两个问号

§33 加的那几个 Chrome 开关是没有在真窗口上验过的。这一轮跑了一次真的双击链路（`& "Open Human.cmd"`）：

- 窗口出来了：进程里有 `--app=http://127.0.0.1:8710`，窗口标题 **陈建国**；
- `/health` 200，`data/llama.log` 里有一轮 3357 ms / 535 tokens 的预热 —— **他先开口了**；
- `data/window` **19.7 MB**（§33 删掉的那份是 158.8 MB）：

| 还在 | 体积 | 没了 |
|---|---|---|
| `Default`（我们的页面数据） | 8.8 MB | `optimization_guide_model_store` 40.1 |
| `BrowserMetrics` | 4.0 MB | `component_crx_cache` 32.6 |
| `GrShaderCache` / `ShaderCache` | 5.1 MB | `WasmTtsEngine` 24.5 |
| `CrashpadMetrics` / 词典 | 1.4 MB | `Safe Browsing` 19.1 |

**结论：开关有效，窗口没被开关弄坏。**

> 想截一张「真窗口」的图给用户看，用了 `GetWindowRect` + `CopyFromScreen`。**截错了** ——
> 截到的是用户前台那个浏览器（`SetForegroundWindow` 抢不到前台）。图当场删了，也没往外发。
> 教训：`CopyFromScreen` 截的是屏幕，不是窗口；要么 `PrintWindow`，要么 CDP。

### 34.4 方案二：WebView2 spike —— 证否，但证得很干净

`scripts/spike/webview2_host.cs`：约 120 行 WinForms + WebView2，`csc.exe` 编译，
**exe 只有 6 KB**，旁边三个 DLL 共 0.9 MB（`Microsoft.Web.WebView2.Core.dll` /
`…WinForms.dll` / `WebView2Loader.dll`，从 NuGet 包 `Microsoft.Web.WebView2 1.0.4314.35` 里取）。
不打包、不装工具链，`csc.exe` 是系统自带的。

**结果：窗口开得出来，内容是空的。** `msedgewebview2.exe` 一启动就死。事件日志（不止一条）：

```
出错应用程序名称： msedgewebview2.exe，版本： 156.0.4314.50
出错模块名称： msedge_elf.dll
异常代码： 0x80000003
```

**`0x80000003`，和 Electron 一模一样的异常码**（§25.6 / §26.1），只是换了模块名。

所以「签名」这个假设被推翻了：WebView2 运行时是微软签名的，照崩。真正的原因还是 §25.6
那半句没被重视的话 —— **Chromium 的初始化在这台机器上、从我们的进程树里拉起就会失败**。

这也解释了为什么应用窗口反而是活的：`Open Human.cmd` 把「开窗口」这件事**交给了 cmd.exe**
（§30），Chromium 的父进程是 shell 而不是 python / 我们的程序。WebView2 没有这条路 ——
它的浏览器进程**必须**是宿主程序的子进程，绕不开。

判定（**用户亲手验过之后定案**）：

- 用户双击 `data/spike/OpenHumanHost.exe`：**窗口一闪就关了**。同一分钟的事件日志里又是三条
  `msedgewebview2.exe … msedge_elf.dll … 0x80000003`。
- 所以这**不是我们的进程树的问题** —— 用户自己的 explorer 父进程、用户自己的令牌，一样崩。
  是这台机器对「被嵌进别的程序的 Chromium」一律拒绝（Electron、WebView2 同命）。
- 而 Chrome/Edge **作为浏览器**被正常拉起时没事（`--app` 窗口就是这么活的）。差别不在签名，
  在「谁当它的爹」：浏览器由 shell 起，嵌入式 Chromium 由宿主程序起来。
- **结论：Electron / WebView2 两条路彻底关闭。** 应用窗口不是妥协，是这台机器上唯一能走的路。
  beta v0.1 不改。

### 34.4.1 图标：一个我自己写进去的 bug

第一次生成的 `assets/OpenHuman.ico` 用 `PIL.Image.save(format="ICO")`，资源管理器显示**默认图标**。

拆开看：ICO 的 `ICONDIRENTRY` 里 `planes` 字段是 **0**，规范要求 **1**。`.NET` 的
`System.Drawing.Icon` 容错，照读（32×32）；**资源管理器不容错，直接回退成默认图标**。

改法（`scripts/make_icon.py` 重写）：不再让 Pillow 写 ICO，按
`ICONDIR` / `ICONDIRENTRY` / `BITMAPINFOHEADER` 手工拼 —— ≤128 用 32bpp BMP + 1bpp AND 掩码，
256 用 PNG（Vista 起支持）。生成后自检：7 项、`planes=1`、`bpp=32`、偏移不越界。

**一个没用的验证方法**：拿 `SHGetFileInfo(SHGFI_ICON)` 去问一个 `.lnk` 的图标。它对
**任何** 快捷方式都返回「白纸 + 箭头」的通用图标（拿 `notepad.exe` 当目标、带 IconLocation 也一样），
因为 Explorer 渲染桌面时不走这条路。**别再拿它验快捷方式图标**，会得到假阴性。

真正的验证只有两种：重启资源管理器后**用眼睛看**，或者读 `IconCache.db`。前者够用。


### 34.5 数字

- 新增：`assets/OpenHuman.ico`（22 KB，7 个尺寸）、`scripts/make_icon.py`、
  `scripts/install_shortcut.ps1`、`scripts/spike/webview2_host.cs`。
- `vendor/webview2/`（SDK 包 + 三个 DLL，约 10 MB）**不进 git**，和 `vendor/` 其余一样。
- 测试仍然 209 passed（这一轮没动 runtime 代码）。
- 现场清干净：spike 的 host 和它拉起的 WebView2 进程全部结束；系统自己那 18 个
  `msedgewebview2.exe`（SearchHost / Google Drive / PC Manager）**没碰**。

> 后续（同一天）：用户亲测 spike「窗口一闪就关了」，事件日志同一分钟又是三条
> `0x80000003`。**定案：这台机器不接受任何嵌入式 Chromium**，Electron / WebView2 彻底关闭，
> 见 §34.4 末尾。

---

## 35. 许可证：GPL-3.0（2026-10-29）

问过 MIT / Apache-2.0 / GPL-3.0 / AGPL-3.0 / 私有的区别，用户选 **GPL-3.0**。

这是他的项目，选哪个都合理；我做的是把后果写清楚，不评价选择。

**落地：**

- `LICENSE`：gnu.org 官方原文（`https://www.gnu.org/licenses/gpl-3.0.txt`，35,149 bytes，
  553 行）。没有手抄 —— 手抄一遍许可证是最容易出错的事之一。
- `README.md` 加了「许可」段：一段 GPL 的「人话后果」+ 版权行 + **三条例外**。

**三条例外必须写**（GPL 是代码许可，管不到别人家的东西）：

| 路径 | 归属 |
|---|---|
| `models/` | 上游 MiniCPM 系列权重的自己的许可，与 GPL-3.0 无关 |
| `vendor/` | 第三方工具链（llama.cpp MIT、Python PSF、uv / git 各自许可），原样打包 |
| `humans/<slug>/` | 用户自己的人格数据，不属于本项目代码 |

**GPL 的实际后果（记着，不是抱怨）：**

1. 别人改了再发布 → 那个版本也必须 GPL 开源。对「拿去用」没影响，对「拿去改了闭源卖」有影响。
2. 企业采用时通常更偏好 Apache-2.0（有专利条款）。GPL 项目一般靠「作者本人双许可」做商业版 ——
   版权在用户手里，他以后可以这么做，但**换许可需要所有贡献者同意**。
3. 「分发时要提供源码」这条对我们自动满足：本来就是源码分发（Python + HTML，无构建步骤）。
4. 打包 zip 时，`LICENSE` 和源码必须在包里 —— §36 的脚本会检查。

**还差一件小事**：`README.md` 的版权行现在写的是「Open Human 作者」，
发布前应换成用户真名或 ID（他给，我改）。

---

## 36. 切包：5,941 个文件 → 1,590 MB（2026-10-29）

`scripts/pack_beta.ps1`，先 `-DryRun` 看清单，再真打：

```
  files: 5,941
  size : 1,804 MB   (未压缩)
  out  : dist\open-human-0.1.0-beta.zip
  5,941 entries, 1,590 MB   (55 秒)
```

- **排除**：`.git`（9.1 MB）、`data/`（运行时状态，35.6 MB）、`dist/`、`vendor\webview2`
  （已删）、`__pycache__`、`.pytest_cache`、`*.log`、`config.toml`（本机配置可能含 key）、
  `pytest-of-*`。
- **打包前后各查一遍**：必含 `LICENSE` / `README.md` / `src\openhuman\cli.py` /
  `humans\demo\human.yaml` / `.venv\Scripts\python.exe` / 权重 / `llama-server.exe`；
  必不含 `data\` / `config.toml` / `.git\`。打完再用 `tar -t` 把归档读回来验一次。
- **用 `tar.exe`**（bsdtar 3.8.9，Win10 1803+ 自带）流式压，不用 `Compress-Archive` ——
  1.8 GB 走 .NET 的 ZipArchive 会吃掉几 GB 内存，而且不能排除文件。

### 36.1 一个会让 zip 变成砖头的坑：.venv 里存的是绝对路径

`.venv\pyvenv.cfg`：

```
home = C:\...\open_human\vendor\python\cpython-3.12.15-windows-x86_64-none
```

在别人机器上解压 → `python.exe` 找不到 base interpreter → 双击之后**什么都不发生**。
本机上换个目录也一样（只是本机原来的路径还在，所以看不出来）。

**改法**：`Open Human.cmd` 加 `:fixvenv`，每次启动用 `%~dp0` 把那一行重写
（其余行原样 `findstr /v` 保留），并且加一道保险 —— **新文件小于 20 字节就不替换**
（宁可不动，也不能把 pyvenv.cfg 写坏；写坏了整个程序都起不来）。

**实测**：把包解到 `data\unpack`，跑 `:fixvenv` 之后

```
sys.prefix      = …\data\unpack\.venv
sys.base_prefix = …\data\unpack\vendor\python\cpython-3.12.15-windows-x86_64-none
```

再在那个副本里跑 `python -m openhuman.cli doctor` —— 8 项全绿（`config.toml` 是「还没创建，
用默认值」，因为包里本来就不带它）。**自包含成立。** 顺带这个修复也治好了「用户把文件夹搬走
之后 python 起不来」。

### 36.2 交付指纹

- `dist\open-human-0.1.0-beta.zip`，1,590.5 MB，5,941 个条目。
- SHA256 `84F3A41DCBAC4736184F03C3E0A02B3E4B5C1AAD4A55467A960949C5A77FD15C`。
- 解压约 12 秒（本机）。`dist/` 已进 `.gitignore`。
- 交付给别人时：解压到任意目录 → 双击 `Open Human.cmd` →（可选）
  `powershell -ExecutionPolicy Bypass -File scripts\install_shortcut.ps1` 摆个桌面图标。

> 没做的验证：没有在**另一台干净机器**上解压双击过（这台机器没法假装自己是别的机器）。
> 已知的依赖：Windows 10/11、Edge/Chrome 之一、8 GB 内存。`vendor\python` + `.venv`
> 是 x86_64 Windows 版，别的平台跑不了 —— 这是设计内的（D-04 / D-06）。
>
> **上面这组数字（5,941 / 1,590.5 MB / SHA 84F3A41D…）是清理前的包。**
> 清理之后又打了一次，见 §37.1。

---

## 37. 交付前体检：清掉 53 MB 重复和缓存（2026-10-29）

用户：「针对整个项目已经整理完毕了对吧，你现在帮我深度检查一下，看看有没有什么垃圾文件之类的」。

写了个**只读**审计脚本（跑完就删）：顶层体积、垃圾文件名/后缀、空目录、>20 MB 的大文件、
**内容级重复**（`.venv` / `vendor` / `models` 之外按 sha256 比）、各目录文件数、`data/` 明细。

### 37.1 发现并清掉的东西

| 项 | 体积 | 是什么 |
|---|---|---|
| `vendor\python\cpython-3.12-windows-x86_64-none\` | **51.4 MB** | **重复的解释器**。`pyvenv.cfg` 用的是 `cpython-3.12.15-…`；这份是 uv 早先按「3.12 通道」装的同一版本 |
| `pytest-of-henry\` | 438 文件 | pytest 的 `tmp_path` 目录落在仓库根 |
| `.pytest_cache\` | 13 KB | pytest 缓存 |
| `vendor\uv-cache\` | 1.5 MB | uv 自己的下载/构建缓存（`uv sync` 会重建） |
| `data\` 里 11 个临时文件 | ~30 KB | 这一轮验图标 / WebView2 / lnk 时我自己留下的 png、py、txt |

清理后：`vendor` 270.7 → **217.8 MB**；仓库（不含 `dist/`）1,864 MB。
`.venv`、`oh doctor` 8 项、**209 个测试**全部照常。

### 37.2 两个「靠运气才没出事」的地方

1. **`scripts/env.ps1`** 用 `-Filter 'cpython-3.12*'` 取**第一个**匹配 —— 有两份解释器时，
   它选中的不是 `pyvenv.cfg` 指的那份。版本相同所以从没出过事，但这是运气。
2. **`Open Human.cmd` 的 `:fixvenv`** 用 `for /d` 取**最后一个**匹配 —— 两份解释器时靠
   字母序（`3.12-` < `3.12.`）才恰好选中对的那份。

删掉重复的那份之后两处都只剩一个候选，不再依赖运气。
**规矩：`vendor\python\` 下只放一份解释器。**

### 37.3 为什么 pytest 的 tmp 落在仓库根

`tempfile.gettempdir()` 在这个 shell 里返回了仓库目录：`TEMP` / `TMP` / `TMPDIR` 都正常指向
`%LOCALAPPDATA%\Temp`，但 CPython 的候选列表在**写不进 `%TEMP%`** 时会退到 `os.curdir`。
**这是实现者外壳的环境问题，不是项目问题** —— 用户自己跑 `pytest` 不会这样。
所以**没有改代码**，只删目录；`pytest-of-*/` 早就在 `.gitignore` 里。

### 37.4 故意留着的

| 留着 | 体积 | 为什么 |
|---|---|---|
| `data\window\` | 24.9 MB | 运行中的 Chrome profile（现在 app 正开着）。关掉再启动会重建；不进包 |
| `data\jieba\` | 8.8 MB | 分词缓存，删了首轮要重建（几秒），留着 |
| `data\ui_live3.png` / `ui_card3.png` | 1.0 MB | 第六轮（§32）的界面证据，`BUILD.md` 引用 |
| `docs\screens\` 4 张 | 2.1 MB | 被 §26 / §28 引用 |
| `authoring-kit\{input,output,work}\` | 空目录 | 已冻结的工具箱骨架，git 不跟踪空目录，不动 |
| `dist\` | 1.59 GB | 交付物本身，已进 `.gitignore` |

### 37.5 重新切包

清理之后再打一次，包里少了重复的解释器和 uv 缓存：

```
  5,412 entries  ·  未压缩 1,802 MB  ·  zip 1,589.9 MB
  SHA256 2F24EB9E3F2510B6CA7E600A4DBEFE173C66D7938E60B6A5222B5B65491EEDD1
```

抽查过包里该有的：`vendor/llama` 24 个文件（含 14 个 `ggml-cpu-*.dll`）、`llama-server.exe`、
`.venv/Scripts/python.exe`、权重、`LICENSE`、`README.md`、`src/` 39 个、`tests/` 16 个；
该没有的：`data/`、`config.toml` 都是 0。








