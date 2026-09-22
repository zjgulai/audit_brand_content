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

## 二、哪些在库里、哪些只在盘上（裁定 = Q38，Owner 最终裁定「只收正文」）

`ADR-0013` §三 的 L1/L2 两行写明了归属，`.gitignore` 里逐条对应。简述：

| | 内容 |
|---|---|
| **L1 · 入历史** | 本页 · 下面那 10 份**正文** · 管线输入（`.ua/.understandignore` / `config.json`）· 快照凭证（`meta.json`） |
| **L2 · 入盘不入历史** | **9 个复现入口脚本（`*.cjs`）** · `knowledge-graph.json`(1.8M) · `fingerprints.json`(495K) · `dispatch/`(43 批 + 4 个图) · `intermediate/` · `.trash-1790050761/`(11M，管线自己的回收站) |

**★ 代价写在明处：正文里的复现命令，在库里没有对应的文件。**

正文里一条条写着 `node .ua/<脚本>.cjs`。Owner 的裁定是**只收正文** —— 于是那 9 条命令
**换台机器之后会指向不存在的文件**，正是 `AGENTS.md` §2.2 第 1 条的坑（本仓为同一个坑
付过一次学费，见诊断 #6）。这不是疏忽，是裁定时已知并接受的代价；它被**逐条登记**在
`tools/verify_doc_reachability.py` 的 `ON_DISK_ONLY`（G 段），由 G1–G4 盯着：

* **G1** 正文点名一个不在库里的脚本 → 必须在那张单子上（**不许悄悄多出一条**）；
* **G2** 单子上每条都必须仍被点名（**过期声明 = 提前发出去的免死金牌**）；
* **G3** 每条都要有理由；**G4** 单子非空（否则 G1 恒真）。

同一裁定还有第二处代价：`dispatch/` 与 `intermediate/` 的**生成脚本因此不在 L1**，
`base/verify_base.py` 的异议一判据对它们不成立 —— 那两个登记项的 `class`
由 `derived` 改判为 **`derived_l2_generator`**，B 面逐条打印，不许混进「判据不适用」里。

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

## 四、九条复现入口（**只在盘上**，不入历史 —— 见 §二）

`assemble.cjs` · `gen-dispatch.cjs` · `gen-phase45.cjs`（管线组装与分批）·
`graph-diagnosis.cjs` · `doc-reachability.cjs` · `duplication-check.cjs` ·
`runtime-surface.cjs` · `adr-status-check.cjs` · `reference-census.cjs`（各份读数）。

用法就是正文里写的那一行，例如 `node .ua/reference-census.cjs` —— 但**这一行只在
本机跑得通**：这 9 个文件按 Q38 的裁定留在 L2（`.gitignore` 里逐条列出）。
换台机器、或者 `.ua/` 被清掉，正文里所有这类命令都会指向一个不存在的文件。
这张「哪些命令是空头支票」的单子就是 `ON_DISK_ONLY`，**不许悄悄变长**。

> ★ 其中三条的**口径已经搬进常驻验算器**，不再只是「跑一次看看」：
> `reference-census.cjs` → `tools/verify_reference_census.py`（棘轮：零引用面只许缩小）·
> `doc-reachability.cjs` → `tools/verify_doc_reachability.py` ·
> `adr-status-check.cjs` → `tools/verify_adr_status.py`。**搬进去的是判据，留下的是当时那份读数。**
> 这也是「脚本不在库」没有把这件事变成死账的原因：三条判据各自有常驻执行点，
> 不依赖那 9 个 `.cjs` 还在不在盘上。

## 五、这一轮之后留下了什么执行点

| 执行点 | 拦什么 |
|---|---|
| `python3 tools/verify_reference_census.py` | 零引用可执行文件**只许减不许增**（31 个基线，2026-09-22） |
| `python3 tools/verify_doc_reachability.py` | 本页与上面 10 份正文必须**从 README 走得到**；**G 段**另拦「正文点名了不在库里的脚本却没登记」 |
| `python3 tools/verify_open_items.py` | 这轮开出的未决项（含 `.ua/` 分级本身）**带着「等了几天、在等谁」** |
| `python3 base/verify_base.py` | `.gitignore` 的每条规则都要被登记表认领、且在 ADR §三 有出处；**B 面另逐条打印 `derived_l2_generator` 那两组的降级** |
| `python3 tools/verify_browser_ext_artifact.py` | 与本页无关，但同属「这一轮照出来的产物问题」：L1 里 418KB 浏览器扩展产物**能不能按配方重建**（Q39 选项 A） |
