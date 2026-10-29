# Phase 0 基准报告

> 生成时间：2026-10-26。机器：`i5-12400F`（6 核 12 线程）× 1，Windows 10 Pro 26H2。
> 模型：`MiniCPM5-2B-Q4_K_M.gguf`（2.52B 参数，1.45 GiB）。
> 结论先行：**8K context 保留；真正的问题是冷启动 prefill，不是内存。**

> **下面的数字一个都没改过。** 但环境变了：Electron / pnpm / `spike/` 都已删除，
> 窗口改用 Chrome/Edge 应用模式（归档 §27.5），所以本文 §8「Electron」那一节是历史证据，
> 不是可执行步骤。速度 / 内存 / prefix cache 的结论仍然有效，`BUILD.md` §11 的硬约束就出自这里。

---

## 1. 环境

| 项 | 值 |
|---|---|
| CPU | 12th Gen Intel Core i5-12400F，6 物理核 / 12 逻辑核 |
| 指令集 | AVX2（llama.cpp 自动选中 `ggml-cpu-alderlake.dll`），无 AVX-512 |
| OS | Windows 10 Pro 26H2 |
| Python | 3.12.15（uv 管理，装在 `vendor/python/`） |

系统沙箱不允许写 `%USERPROFILE%`、`%APPDATA%`，所以**所有工具都是便携版，放在项目内 `vendor/`**，
不污染系统、不需要管理员权限、卸载就是删文件夹。

| 工具 | 路径 | 版本 |
|---|---|---|
| uv | `vendor/uv/uv.exe` | 0.13.5 |
| Python | `vendor/python/cpython-3.12.15-windows-x86_64-none/` | 3.12.15 |
| Git | `vendor/git/cmd/git.exe`（MinGit 便携版） | 2.56.0.windows.3 |
| llama.cpp | `vendor/llama/llama-server.exe` | b11889 (0.7.0-dev) |

跑任何命令前先 `. scripts/env.ps1`（设置 `UV_PYTHON_INSTALL_DIR`、`UV_CACHE_DIR`、把 `vendor/` 加进 PATH）。

---

## 2. 模型事实

- 官方仓库：`openbmb/MiniCPM5-2B-GGUF`，同仓有 F16 / Q4_K_M / Q8_0 三档；Apache-2.0。
- Q4_K_M = 1.45 GiB，2.52B 参数。
- chat template 自带 `enable_thinking` 开关。**默认开**，思考链会吃掉全部输出。
- 关掉之后，模板仍会在 assistant 开头注入一段 thinking 字面量，**必须由客户端剥掉**（字面量与处理见 `src/openhuman/llm/client.py` 的 `_ThinkFilter`）。

### 推荐启动参数

```powershell
vendor\llama\llama-server.exe `
  -m models\MiniCPM5-2B-Q4_K_M.gguf -a MiniCPM5-2B `
  --host 127.0.0.1 --port 8080 `
  -ngl 0 -t 8 -c 8192 -np 1 -fa on `
  --jinja --reasoning-format none
```

`-np 1`：单 slot。多 slot 只会把 8K 切碎，我们没有并发需求。

---

## 3. 速度

### 3.1 线程数（llama-bench，pp512 / tg64）

| 线程 | pp512 tok/s | tg64 tok/s | 说明 |
|---:|---:|---:|---|
| 1 | 30.4 | 7.8 | 单核基线 |
| 2 | 57.9 | 11.9 | |
| 4 | 96.4 | 15.1 | |
| 6 | 121.0 | 16.0 | 物理核数 |
| 8 | 145.2 | 16.0 | **默认选这个** |
| 12 | 153.4 | 14.8 | 超线程收益低，decode 反而掉 |

### 3.2 是否开 flash attention

| 线程 | pp512 (fa off) | pp512 (fa on) | tg64 (fa off) | tg64 (fa on) |
|---:|---:|---:|---:|---:|
| 6 | 117.2 | 124.4 | 16.00 | 16.18 |
| 8 | 135.7 | **148.3** | 16.13 | **16.48** |
| 12 | 137.9 | 154.6 | 14.31 | 14.67 |

`-fa on` 白送 6–9% prefill，无副作用，**默认开**。

### 3.3 冷 prefill 曲线（单次、无缓存）

| prompt tokens | prefill tok/s | 耗时 |
|---:|---:|---:|
| 505 | 138 | 3.6 s |
| 2,020 | 134 | 16.6 s |
| 3,434 | 119 | 28.5 s |
| 3,500（流式首字） | — | **29.0 s** |

**这是本次最关键的坏消息。** prefill 只有 ~120–150 tok/s，3.5K prompt 冷启动要 29 秒。

### 3.4 decode

| 场景 | tok/s |
|---|---|
| llama-bench tg64 | 16.5 |
| 真实会话（短回复，10 轮中位数） | 17.4 |
| 连续 200 token 长生成 | 11.4 – 14.4 |

长生成会掉速（AVX 降频 / 持续满载）。换算成体感：80 字回复（≈100 tok）约 6 秒；
200 字回复（≈250 tok）约 15 秒，满载长跑时约 20 秒。

---

## 4. Prefix cache —— 方案能否成立全看它

llama.cpp 的 prompt cache 是**前缀缓存**：只要这轮 prompt 的开头跟上一轮一致，一致的部分不重算。

实测（t=8 + fa on，prompt 前缀 3,163 tok）：

| 场景 | TTFT | 重算 tokens | 命中 tokens |
|---|---:|---:|---:|
| 冷启动，`cache_prompt: false` | 27.07 s | 3,163 | 0 |
| 同样的 prompt，`cache_prompt: true` | **0.10 s** | 1 | 3,195 |
| 末尾追加一轮 | **0.21 s** | 1 | 3,201 |

**结论：暖缓存时 TTFT 是 0.1 秒级，不是秒级。** 所有延迟问题都集中在「第一次」。

### 4.1 真实 10 轮会话（现在 `BUILD.md` 的 prompt 布局）

persona 1,218 tok；有记忆的轮次在前面插 3 张卡；历史超长时裁掉中间。

| 轮 | 带记忆 | TTFT | 重算 | 命中 | 输出 |
|---:|:---:|---:|---:|---:|---:|
| 1 | . | 8.03 s | 1,247 | 0 | 4 tok |
| 2 | . | 0.24 s | 20 | 1,250 | 4 tok |
| 3 | Y | 1.21 s | 138 | 1,273 | 9 tok |
| 4 | Y | 1.28 s | 140 | 1,419 | 13 tok |
| 5 | . | 0.29 s | 20 | 1,571 | 7 tok |
| 6 | Y | 3.56 s | 480 | 1,227 | 6 tok |
| 7 | Y | 4.49 s | 600 | 1,227 | 8 tok |
| 8 | . | 2.74 s | 366 | 1,345 | 4 tok |
| 9 | . | 2.70 s | 355 | 1,227 | 5 tok |
| 10 | . | 2.75 s | 355 | 1,227 | 5 tok |

TTFT 中位数 **2.72 s**，最差 8.03 s（第一轮）。第 6 轮开始变慢是因为测试脚本裁剪了历史中间段 ——
**裁历史会打断前缀，每次裁剪都要重算一遍**。这是设计约束，不是 bug。

### 4.2 开机预热：把第一轮的 8 秒藏起来

App 启动、加载完人格包之后，先发一个极短请求把 persona 前缀灌进缓存（用户这时还在看开机动画）：

| 场景 | TTFT | 重算 |
|---|---:|---:|
| 开机预热请求 | 0.17 s | 11 |
| 之后第一个真实问题（无记忆） | 0.26 s | 20 |
| 之后第一个真实问题（带记忆） | **0.63 s** | 59 |

**这条必须写进实现**：`boot → warm(persona) → 等用户输入`。没有它，每次打开 app 第一句要等 8 秒。

---

## 5. 内存

| context | Working Set | Private | KV 理论值 |
|---|---:|---:|---:|
| 4,096 | 2,486 MB | 1,261 MB | 0.17 GB |
| 8,192 | 2,654 MB | 1,434 MB | 0.33 GB |

**8K 只比 4K 多 168 MB。** 之前「8K 会让内存紧张」的估算不成立。

- 模型加载到 `/health` ready：**1.9 秒**。
- 8 GB 机器上，llama-server 占 2.7 GB，剩 5.3 GB 给 Python + 一个浏览器进程，够。

---

## 6. 结论与修订

### 6.1 保留的决定

- **8K context**：内存不是瓶颈，8K 只多 168 MB。
- `-t 8 -fa on -np 1`。
- 模型选型正确：2B 中文口语可用，语气自然，没有明显出戏。

### 6.2 新增的硬约束

本报告新增了 N-01…N-06 六条（prefix cache、开机预热、记忆块位置、裁历史代价、关 thinking、
短回复），**已原样搬进 `BUILD.md` §11**，理由和「为什么」都在那张表里，这里不再复述。

### 6.3 prompt 预算

原预算 3,900 tok（冷启动 ≈29 s）→ 改为 **2,600 tok**（冷启动 ≈17 s，预热后首轮 ≈4 s）。
分块预算表在 `BUILD.md` §8。

### 6.4 验收对照

| 项 | 结果 |
|---|---|
| `llama-server` 在 127.0.0.1:8080 正常响应 | ✅ 1.9 s ready |
| Python spike 能流式输出 | ✅ 10 轮，TTFT 中位数 2.72 s |
| 4K / 8K 哪个可用 | ✅ 8K 可用，4K 只省 168 MB |

### 6.5 没做到 / 待用户确认

- **首字 < 3 秒**：稳态达到（0.2–1.5 s），但**冷启动第一句 8 s**。靠 N-02 预热降到 0.6 s。
- **200 字回复 < 30 秒**：短回复没问题；连续 200 字满载会掉到 11 tok/s ≈ 20 s，**勉强合格**，
  所以规则里坚持短回复。

---

## 7. 复现命令

```powershell
. scripts/env.ps1                       # PATH / uv 环境变量

# 启动推理
vendor\llama\llama-server.exe -m models\MiniCPM5-2B-Q4_K_M.gguf -a MiniCPM5-2B `
  --host 127.0.0.1 --port 8080 -ngl 0 -t 8 -c 8192 -np 1 -fa on `
  --jinja --reasoning-format none

# 冷 prefill 曲线
.venv\Scripts\python.exe scripts/bench_llm.py --label manual --targets 512,2048,3500

# 10 轮真实会话（需要 oh serve 在跑）
.venv\Scripts\python.exe scripts/stress_chat.py 10
```

三条今天都还能跑。看窗口用 `.\"Open Human.cmd"`（模型 + 服务 + 应用窗口）。

---

## 8. Electron spike（历史）

> `spike/` 和 `vendor/electron*` 都已删除：Electron 在这台机器上起不来（归档 §25.6 / §26.1）。
> 这条 spike 证明的是「Python 起得来、浏览器能显示它返回的内容」，这一点仍然成立，
> 后来被 Chrome `--app` 应用模式用上了。

链路：Electron 主进程 → 选一个空闲端口 → `spawn` Python，端口经环境变量传入 → 轮询 `/health`
直到 200 → `BrowserWindow` 加载 `http://127.0.0.1:<port>/` → 页面 fetch `/api/ping`，
把返回的一句话写进 `document.title` → 主进程读回 title，断言是 Python 给的。

实际输出：

```
[spike] picked free port 51706
[spike] python health: OK
[spike] window title = "up:……你来了。"
[spike] OK renderer rendered content served by python
```

**两个环境坑（不是代码问题）**：

1. **不能用 stdout 握手。** 这个环境里 `spawn` 配 `stdio: 'pipe'` 会 `EPERM`（命名管道被禁）。
   改成「选端口 → 环境变量传进去 → 轮询 `/health`」反而更稳，现在的启动脚本就是这么做的。
2. **Electron 需要 `--no-sandbox` 才能启动。** mojo IPC 在这里被拒
   （`platform_channel.cc:112`）。这是开发环境沙箱的限制，不是用户机器的问题。
