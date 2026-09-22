# `.ua/` · 2026-09-22 结构性诊断的工作目录

> 这一页是**入口**，不是简介。它存在的理由有执行点：
> `python3 tools/verify_doc_reachability.py`（一份走不到的文档，和一个不存在的文档，对读者是同一件事）。

## 一、这里是什么

2026-09-22 用 `Understand-Anything` 的 `understand` 管线对**当时的工作区**做了一次结构性诊断：
455 个文件 → 43 批 → 1362 节点 / 2657 边 / 12 层，产物落在这个目录里，
按工程债务 / 逻辑债务 / 文档债务三类给出 **TOP20 优化点**，随后逐条复核并修复。

**这次分析读的是哪一个快照**：`.ua/meta.json` 的 `gitCommitHash`（`analyzedFiles: 455`）——
正文里所有的「实测」都是那一刻的读数，不是常量。按 `AGENTS.md` §2.2 第 1 条引用它们时，
要么带复现命令，要么标明时刻。

## 二、哪些在库里、哪些只在盘上（分级裁定 = Q38 选项 A）

`ADR-0013` §三 的 L1/L2 两行写明了归属，`.gitignore` 里逐条对应。简述：

| | 内容 |
|---|---|
| **L1 · 入历史** | 本页 · 下面那 10 份**正文** · 9 个**复现入口**脚本 · 管线输入（`.understandignore` / `config.json`）· 快照凭证（`meta.json`） |
| **L2 · 入盘不入历史** | `knowledge-graph.json`(1.8M) · `fingerprints.json`(495K) · `dispatch/`(43 批 + 4 个图) · `intermediate/` · `.trash-1790050761/`(11M，管线自己的回收站) |

**为什么正文与脚本必须一起进**：正文里一条条写着 `node .ua/xxx.cjs` 这样的复现命令 ——
只收正文会让那些命令指向不在库里的文件，正是 `AGENTS.md` §2.2 第 1 条的坑
（本仓刚为同一个坑付过一次学费，见诊断 #6）。

> ⚠️ **一处已知口径外**：`tools/verify_reference_census.py` 的**可执行面**继承诊断的口径
> （`.py .mjs .js .sh .plist`），**不含 `.cjs`** —— 所以上面那 9 个脚本既不会被报成零引用、
> 也不会被棘轮拦住。这条盲区在脚本输出里**每次都会打印出来**，不藏着。

## 三、十份正文（按债务类别）

| 报告 | 它回答的问题 |
|---|---|
| [`debt-engineering.md`](./debt-engineering.md) | 工程债务 39 条：零引用文件、同形副本、自证入口实跑读数 |
| [`debt-logic.md`](./debt-logic.md) | 逻辑债务：85 条语境守卫词里 39 条对判定零影响（45.9%） |
| [`debt-documentation.md`](./debt-documentation.md) | 文档债务：8 类 38 条 finding，每条带 file:line 与复现命令 |
| [`debt-graph-and-crosscut.md`](./debt-graph-and-crosscut.md) | 体量真相 / 运行时可达面 25 反 464 / 引用普查 / 层耦合矩阵 |
| [`graph-diagnosis.md`](./graph-diagnosis.md) | 图谱自身的质量读数（诚实项：哪些结论不可靠） |
| [`doc-reachability.md`](./doc-reachability.md) | 从 README ∪ AGENTS.md 出发，226 份文档里多少份走不到 |
| [`duplication-check.md`](./duplication-check.md) | 重复与近似重复：同形函数副本而不是「重复行占比」 |
| [`runtime-surface.md`](./runtime-surface.md) | 运行时真正会加载的文件面（不是「存在」而是「可达」） |
| [`adr-status-check.md`](./adr-status-check.md) | ADR 台账与 ADR 文件的**状态双源冲突** |
| [`reference-census.md`](./reference-census.md) | 每个可执行文件被多少份其它在册文件提到过（0 次 = 最强死代码候选） |

## 四、九条复现入口

`assemble.cjs` · `gen-dispatch.cjs` · `gen-phase45.cjs`（管线组装与分批）·
`graph-diagnosis.cjs` · `doc-reachability.cjs` · `duplication-check.cjs` ·
`runtime-surface.cjs` · `adr-status-check.cjs` · `reference-census.cjs`（各份读数）。

用法就是正文里写的那一行，例如 `node .ua/reference-census.cjs`。

> ★ 其中三条的**口径已经搬进常驻验算器**，不再只是「跑一次看看」：
> `reference-census.cjs` → `tools/verify_reference_census.py`（棘轮：零引用面只许缩小）·
> `doc-reachability.cjs` → `tools/verify_doc_reachability.py` ·
> `adr-status-check.cjs` → `tools/verify_adr_status.py`。**搬进去的是判据，留下的是当时那份读数。**

## 五、这一轮之后留下了什么执行点

| 执行点 | 拦什么 |
|---|---|
| `python3 tools/verify_reference_census.py` | 零引用可执行文件**只许减不许增**（31 个基线，2026-09-22） |
| `python3 tools/verify_doc_reachability.py` | 本页与上面 10 份正文必须**从 README 走得到** |
| `python3 tools/verify_open_items.py` | 这轮开出的未决项（含 `.ua/` 分级本身）**带着「等了几天、在等谁」** |
| `python3 base/verify_base.py` | `.gitignore` 的每条规则都要被登记表认领、且在 ADR §三 有出处 |
