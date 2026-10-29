# Docs

**唯一权威规划在根目录 [BUILD.md](../BUILD.md)** —— 只写**现状 + 必须记住的约束**。
**给使用者的说明在根目录 [README.md](../README.md)** —— 需要什么机器、双击哪个文件、数据在哪、
为什么不是 Electron、2B 的短板。
**开发规矩在 [AGENTS.md](../AGENTS.md)，上手步骤和红线在 [CONTRIBUTING.md](../CONTRIBUTING.md)，
版本变化在 [CHANGELOG.md](../CHANGELOG.md)。**

这个目录只剩两样东西：

| 文件 | 是什么 |
|---|---|
| [benchmark.md](benchmark.md) | Phase 0 的实测报告（速度 / 内存 / context / prefix cache）。**速度与 prefix cache 的结论仍然有效**，`BUILD.md` §11 的硬约束就是从这里来的。注意它是 2026-10-26 的**记录**，Electron 那一节已作废，文件开头有说明。 |
| [archive/BUILD-history.md](archive/BUILD-history.md) | **37 节完整开发史**：Phase 0–5 的实现与验收、六轮打磨、收尾清理、窗口排查（Electron / WebView2 为什么在这台机器上不行）、beta 收尾、切包、交付前体检。代码和文档里写「**归档 §N**」的地方，指的就是它的第 N 节。 |

## 旧节号对照（代码注释里还会遇到 `§N`）

| 旧 | 现在是 | 旧 | 现在是 |
|---|---|---|---|
| §4 | §6 人格包契约 | §18 | §11 硬约束 N-01…N-06 |
| §7 | §8 模型与上下文 | §24 | §16 分发与打包 |
| §8 | §9 对话流程 | §28.8 | §12 已知短板 |
| §10 / §11 | §4 架构 | §16 | §15 体积 |

其余（`§25.x` / `§26.x` / `§27.x` / `§29` / `§30` / `§32.x` / `§33.x` / `§34.x` / `§35` /
`§36` / `§37`）在新 `BUILD.md` 里没有对应小节 —— 它们只在归档里，代码注释写成 **`§N（归档）`**。

## 已删除的（beta 收尾时）

- `history/` —— 10 个访谈记录文件（需求怎么一步步收敛的）。它们自己的 README 就写着
  「已过时，不要根据它们做开发决策」。
- `screens/` —— 4 张界面截图，拍的是三个版本前的界面，而且不会自动更新。

两份都在同一个提交（`af6ea0e`）里删的，git 历史里还在。要找回：

```powershell
git log --diff-filter=D --oneline -- docs/history docs/screens   # 看是哪一次删的
git show af6ea0e^:docs/history/00-plan.md                        # 换个文件名同理
```

## 现在读什么

开发前：`BUILD.md` → 遇到「为什么要这么做」再按关键词搜归档
（`Select-String -Path docs\archive\BUILD-history.md -Pattern '关键词'`）。
