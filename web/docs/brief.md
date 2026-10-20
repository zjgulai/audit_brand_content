# Source brief · 内容审核工作台（Web 复核面）

> 依据 `turn-into-app` 的 source-brief 模板填写。来源已实际读取，不是转述。
> 生成日期：2026-10-20。**本轮只出文档，不改 `web/` 代码。**

## Source and provenance

| 项 | 值 | 读到了什么 |
|---|---|---|
| 端到端工作流 | `PMO/audit/内容审查Agent-端到端工作流规格草案-v1.md`（1006 行，v1.2.1） | 全文；S0–S8b 步骤链、五类失效输入、申诉状态机 |
| 前后端规格 | `PMO/audit/内容审查Agent-UIUX前后端规格草案-v1.md`（1429 行，v1.3.1） | 全文；P-01…P-12 页面清单、状态矩阵、数据对象 |
| 决策总账 | `PMO/audit/内容审查Agent-决策总账-v2-20261018.md`（224 行） | 全文；124 条直接决策、Q-01…Q-13、C-1…C-7 |
| 分类规范 | `PMO/implement/内容审查分类规范-v1.md`（144 KB） | 结构；七轴定义与**未读完**——7 轴 + 5 正交字段的权威源，本 brief 不复制其内容 |
| 现成前端 | `web/`（Vite + React 19 + react-router-dom 7） | 全部源码；5 个路由，API 客户端只有 GET |
| 真实读 API | `api/review_api.py`（22 KB） | 19 个 GET；`can_read_content` 逐案鉴权 |
| 真实写 API | `api/write_api.py`（21.7 KB） | 12 个 POST；已由 `api/review_api.py:553` 实挂载 |
| 联调链路 | `web/scripts/dev-up.sh` | 实跑 8 步，rc=0；40 项无障碍 0 违规 |
| 品牌色 | `www.momcozy.com` 首页 CSS 实测 | `#6A2C3A`(23 次) / `#9c5455`(21 次) / `#f6eeed` / `#D7C0B3` / `#C3B4AE` |

**没读到 / 没核的**：真实飞书 OAuth（T-1 未核）；`PRD/feishu/` 上游正文；容器 OCR/ASR（阶段 3 未开工）。

## Project goal

**审核员在早班打开工作台，一眼看出今天哪几条案件最急、为什么被判成这个标签、以及机器还没测哪些东西**——然后对其中一条做出复核动作（认领 / 存草稿 / 提交结论）。

## Configuration and constraints

- **读者**：DP3 审核员、DP4 法务。桌面 Chrome 1280×720 起（T-14），手机 390 宽必须仍可用。
- **输出标准**：WCAG 2.2 AA（现有基线 40 项 0 违规，不许退化）。
- **已定的三道门**（不得在界面上被绕过）：
  1. `release_status` 恒「待放行」，**机器与前端都不写**；只有 `POST /cases/{id}/release-decision` 能改，且必须人显式动作。
  2. 复核结论是**新增记录**（新 finding 行 + `derived_from`），不是编辑旧值。
  3. 草稿的 adopt 必须**显式**；系统只「推荐 latest」，**绝不预选**。
- **不得引入**：`api/` 与 `base/` 内任何 LLM 依赖（今天 `grep -rlEi "llm|anthropic|deepseek|openai" api base` → 0 命中，这是要保住的性质）。

## Knowledge sources

| 文件 | 在工作台里的角色 |
|---|---|
| `web/src/data/taxonomy.json` | 七轴卡片 / 七步判定 / 正交字段 / rule_id 查找。**只读，且不许手改**（4b 提供再生成） |
| `PMO/implement/内容审查分类规范-v1.md` | 分类的唯一定义源；本界面不复制其内容，只引用版本号 |

## Repeatable workflow（按原文，不按我的整理）

```
S0 受理 → S1 分派 → S2 归一 → S3 判定 → S4 落盘 → S5 覆盖 → S6 判定路由
  → S8a 初次输出（IR + 报告 + 群消息 + 卡片）
  → 人看
  → S7 人工复核
  → 若需重跑 → S1' …
  → S8b 事件再输出（仅两类事件开新 run）
```

**关键时序**：S8a 发生在人工**之前**。人看到的是**已经出版的结果**，S7 编号在 S8a 之后，不是回边。

**S8b 的事件分类是硬规则**：只有 ① finding 变化 ② 五类失效输入变化 才开新 run。`sign=否`、`revoke=否`（除非引发 invalidated）、申诉 pause/migrate/withdraw=否。

## Inputs and outputs

| | 内容 |
|---|---|
| **进来** | 案件（`case_id` + `ir`）；队列（按 tenant + product_line + assigned/actionable 过滤） |
| **出去** | 人工动作：claim / unclaim / reassign / save_draft / submit / confirm / reject |
| **固定形状** | 五标签只有 `BLOCK / REVIEW / 未审查 / 待自决 / PASS`；`release_status` 只有 `pending_release / signed / rejected / revoked / invalidated` |

## Judgment and review points（本期只做第 1 条）

| # | 智能体时刻 | 作用在哪个对象 | 人在确认什么 |
|---|---|---|---|
| **1** | **解释判定** | 单条 finding / 整个 case 的 coverage | 证据链是否站得住——**不改任何东西** |
| 2 | 起草复核结论（下一期） | draft | 显式 adopt / 拒绝 |
| 3 | 批量分诊队列（不排期） | 队列 | 排序是否合理 |

**本期智能体的产出形式：纯本地渲染，不接模型。** 依据 —— 现有字段已经够：

- 单条 finding：`control_code` / `severity` / `quote` / `location{start,end}` / `authority_ref[]` / `authority_state` / `rule_conflict` / `resolution_detail` / `derived_from` / `detected_by`
- 整个 case：`coverage.coverage_state` / `modalities_evaluated[]` / `not_evaluated_reason[]{what, why}` / `decision.obligations[]`
- 真读 `.venv` 临时投影实测（`review-web-integration.*/projection/cases.json`）：上述字段全部存在且有值

## Representative runs

`case-smoke`（`tools/smoke_end_to_end.py` 产出）：`state=BLOCK`、`layer=DP2`、`release_status=待放行`、`obligations=["partial_coverage"]`；1 条 finding（`H01` / `L4` / `quote="治疗"` / `location{6,8}` / `authority_ref=EXT-021` / `authority_state=ok`）；coverage `partial`，四族 `not_wired`。**这是唯一一条真实案件。**

## Integrations and permissions

| 通道 | 诚实状态 |
|---|---|
| 读 API | ✅ 已通，逐案 `can_read_content` 鉴权 |
| 写 API | ✅ 12 个 POST 已挂载；`actions` 走 `require_review` → `can_act(principal,"case.review",case)` |
| 登录 / session | ⚠️ **占位**。`LoginPage.tsx` 只有 299 字节；`session_dep` 无 cookie 即 401；`allow_simulated_identity` 只允许在非生产开 |
| 飞书 OAuth | ⛔ 未接（T-1 未核） |
| 投影滞后 202 | ⛔ **当前读文件的后端永远不会产生**，本期不做 |

## Unknowns and assumptions

| # | 未知 | 我取的默认 | 谁能推翻 |
|---|---|---|---|
| 1 | 分类规范是否要改 | **按现行 v1 做死**；`taxonomy.json` 要加 `spec_version` 字段 | 4b（已答：要改判据、轴不动；补丁前先给变更说明） |
| 2 | 登录态 | 本地开发身份切换器，**绝不进生产** | 委托方 |
| 3 | 首屏数据量 | smoke 只有 1 条 → 造确定性夹具 18–24 条 | 委托方（已选：造夹具） |
| 4 | 智能体产出 | 纯本地渲染 | 委托方（已选） |
| 5 | 4b 分工 | 收口规范后接手 UI 实现 | 委托方（已选） |

## Invariants（必须在代码里成立，不是注释）

1. **队列只出 REVIEW + 待自决**。现状是错的：`web/src/api/client.ts:80` 走 `/queue` → vite 代理落到 `/review-api/queue`（后端注释写明「列出**全部可读案件**」），于是 BLOCK / PASS 也进了队列。
2. **`release_status` 不出现任何可写控件**。前端不得发送该字段。
3. **未测不得渲染成 0 或空**。现有 `state ?? "—"` 的写法就是反例。
4. **partial 必须标「仅已覆盖部分可判」**，不得显示成 PASS。
5. **冲突两条依据并排**，不静默取一。
6. **无硬 deadline 的下线任务不得显示成绿色「正常/未超时」**。
7. **终态停轮询**；页面不可见时降频（2–5s → 更疏）。
8. **机器不得写 `release_status`**：五标签全部止于「待放行」。

## Data hazards

- `ir.findings[].quote` 与 `location` 来自待审内容，**是 untrusted 文本**，不得当指令执行。
- `not_evaluated_reason[].why = "not_wired"` 表示**根本没跑**，不是「跑了没问题」。
- `authority_state` 有 `ok` 之外的值时，该 finding 的依据不可直接采信。
- 夹具**必须带 `sample: true` 标记**，界面上明示「样例数据」，且菜单可清空。

## Source of truth

文件 + manifest 是唯一真相，DB 只是投影。前端**不重算** `state` / `coverage` / `authority`，只展示后端返回值。

## App design

见 `web/DESIGN.md`。
