# T0-03 · claim / lease / draft 的模块归属裁定

## 裁定

| 东西 | 归谁 | 理由 |
|---|---|---|
| **`assignment`**（谁领了这个案件） | `reviews_ledger` | 它本质是「人工复核台账」的一行 |
| **`lease`**（30 分钟空闲过期、心跳） | `reviews_ledger` | lease 是 assignment 的生命周期字段，同一写者 |
| **`draft`**（草稿、快照、引用关系） | `reviews_ledger` | 草稿是**复核过程的中间产物**，不是处置结论 |
| **`disposition_router`** | **只读** | 它按 `state/layer` 补 owner/due/release_status，**不写 assignment** |

## 为什么不是 `disposition_router`

| 方案 | 否决理由 |
|---|---|
| **A. `disposition_router` 持有 claim/lease** | 它的职责是「按判定结果补处置字段」，是**判定之后**的一次映射。而 claim 发生在**人工介入时**，与判定无关 —— 让一个纯映射模块持有可变状态，等于把它变成第二个状态中心 |
| **B. 新建 `assignment_store` 模块** | 会增加第 28 个模块，而 assignment 的字段（actor / 权限 / 幂等 / 结论）与 `reviews_ledger` 已有字段高度重合。再造一个会出现「同一件事两个台账」 |
| **C. `artifact_store` 持有** | 它是**物理追加写者**，不解释业务语义。lease 过期是业务规则（30 分钟），不是存储规则 |
| **D. `orchestrator` 持有** | 它明确「不写 run_record（job_dispatcher）」，同样不该持有业务可变状态 |

## 与既有职责的接法

`reviews_ledger` 现在的职责（技术方案模块 22）：

> 唯一人工复核台账：L5-3 抽样分层；记录 actor/权限/幂等、抽样清单、人工结论；供 metrics_read_model 计算召回/误判/推翻率。

**新增三块后，它的「不负责什么」栏要补两行**：

- 不判 state/layer（`decision_table`）
- **不决定处置路由、不写 `release_status`**（`disposition_router`）

## 三条不变量

| # | 不变量 | 反向对照 |
|---|---|---|
| **CL-1** | 同一案件同时**只能有一个** `assignment` | 两人并发领取，只有一个成功；另一个收到明确失败（不是静默成功） |
| **CL-2** | lease 过期释放**前**必须保存 draft | 构造 lease 到期，断言 draft 仍可读且内容完整 |
| **CL-3** | `disposition_router` **不写** `assignment` / `lease` / `draft` | 静态断言：该模块的写接口白名单里不含这三张表 |

## 需要同步的地方

| 文件 | 改什么 |
|---|---|
| `Playbook/技术解决方案-v1.md` 模块 22 | 「负责什么」补 assignment/lease/draft；「不负责什么」补两行 |
| 同上 模块 15 | 「不负责什么」补「不持有 assignment/lease/draft」 |
| `PMO/audit/内容审查Agent-端到端工作流规格草案-v1.md` S7.1 | 把「待定」改成这里的三行裁定 |

## 未决

| # | 什么 | 谁定 |
|---|---|---|
| 1 | lease 30 分钟是否对所有角色一致（法务终审可能更久） | 产品 |
| 2 | 一个案件能否同时有「复核 assignment」与「法务 assignment」两个 | 产品 |
| 3 | draft 的保留期（与 IR 的 1 年同期？还是跟 assignment 走） | 产品 + 法务 |
