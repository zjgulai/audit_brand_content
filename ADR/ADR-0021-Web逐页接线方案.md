# ADR-0021 · Web UI/UX 逐页接线：现状审计 + 接线方案

- 状态：**已定案，执行中**
- 日期：2026-10-27
- 触发：委托方要求「结合当前最新状态的 Web UI/UX 做每个页面和整体的接线方案」，
  关键决策需逐条沟通确认。
- 上游：`ADR-0020`（后端七段）。本轮是它的**消费侧**：后端五项能力（T-451…T-455）
  已经落地并有自证，但**前端一个都没接**。

---

## 一 · 审计结论（每条指得出文件:行）

范围：`web/src` 8,626 行 · 13 个页面组件 + 12 个组件 + 3 个 api 模块。
路由唯一来源 `web/src/App.tsx:20-141`，**19 条路由**（1 条无 path 布局 + 18 条页面路径 + catch-all）。

### 1.1 本轮后端能力的前端接线现状：**四项，零接线**

| # | 后端能力 | 后端位置 | 前端接线 | 证据 |
|---|---|---|---|---|
| 1 | `workflow_timing` | `orchestrator.py` 写快照 → `review_api.py:156-162` 模型 / `:776-791` 返回 | **零** | `web/src` 搜 `workflow_timing` / `total_ms` / `slowest` = **0 命中**；`client.ts:157-196` 的 `CaseDetail` 接口**没有这个字段**（后端返回了，TS 类型没声明，页面不读） |
| 2 | `POST /version-diff` | `review_api.py:794-817` + `change_detect.judge()` | **零** | 搜 `version-diff` / `versionDiff` / `消失的声明` = **0 命中** |
| 3 | `intent_inference` | `submission_service.py:506` 写 payload | **零，且后端自己也断了** | 前端 0 命中；★ 见 §1.3 |
| 4 | `receipt.skill_hash` / `skill_version` | `orchestrator.py:565-566` 写快照 | **零** | 搜 `skill_hash` / `skill_version` = **0 命中**；`CaseDetail` 响应只有 7 个键，不含 `receipt` |

### 1.2 比「没接线」更该先说的一件事：提交页那套结果是**前端自己算的**

`web/src/pages/SubmitPage.tsx:67-99` 硬编码三条正则，产出的 `code` 是
`BRD4` / `CLAIM` / `FACT`。

后端控制点表 `research/governance/control-points-v1.json` 的 24 个 code 是
`H01…H09 / M01…M07 / U01…U04 / B01…B04` —— 实测：

```
BRD4   出现 0 次
CLAIM  出现 0 次
FACT   出现 0 次
H01    出现 1 次      ← 正向对照：扫描器是活的
B01    出现 1 次
```

即：**这三个 code 在后端不存在**，它们是 `taxonomy.json` 的七轴标签。

而结论也是本地算的，且两个分支都走向同一档：

```tsx
// SubmitPage.tsx:134-136
const hasL4 = findings.some((f) => f.severity === "L4");
const verdict = hasL4 ? "REVIEW" : findings.length > 0 ? "REVIEW" : "PASS";
```

**本地永不产出 BLOCK。** 它与后端响应**无任何数据通路** ——
`setAuditReport(instant)` 在 `POST /submissions` **之前**执行（`:254` vs `:277`），
`submitErr` 只影响标题那行提示，不改变结论。

它今天可见，是因为开发装配的 `POST /submissions` 是 **501**
（`write_api.py:447-448`，`review_command_service is None`），
拿不到 `case_id`，于是永远走「本地审计块」那一支。

### 1.3 ★ 我自己上一票（T-455）漏的那一环

`intent_inference` 我放进了 payload（`submission_service.py:506`），但
`review_reducer.py:1152-1166` 的 `state.update({...})` 里**没有这个键** —— 实测：

```
state 的键里有没有 intent_inference: False
state 里 content 的 content_stage : None
```

而 `ContentUnit` 里 `content_stage` 出现 **0 次** —— 它只活在提交入参里。

我的 D2 断言写的是「payload 里有」，只证到倒数第二跳。
**这与 `due_at` / 工作流耗时 / `semantic_judge` 是同一个形状，这次是我自己犯的。**

### 1.4 界面把「缺失」渲染成「确定状态」：六处

| # | 位置 | 写法 | 后果 |
|---|---|---|---|
| 1 | `ContentUnitViewer.tsx:116` | `parse_status ?? "ok"` → 显示「已提取正文」 | 没解析的图看起来解析成功了 |
| 2 | `AdminGrantsPage.tsx:330` | `product_line ?? "all"` | `all` 是**权限语义**，缺失被读成全品线授权 |
| 3 | `AdminGrantsPage.tsx:338` | 徽标恒 `badge--pending`，文案 `state ?? status ?? "active"` | 任何状态都长成「待定」，且兜底值 `active` 冒充真实状态 |
| 4 | `TakedownPage.tsx:543` | `t.tenant ?? "t1"` | `t1` 是真实租户号格式，缺失被读成「属于 t1」 |
| 5 | `ReleasePage.tsx:205` | `submitter_id: null` 写死 | 自签检查 `isSelfSub` 恒 `false` |
| 6 | `ReleasePage.tsx:278-280` | 三元两分支文案相同（`? "不可自签" : "不可自签"`） | 死分支，改一个分支不会有任何可见变化 |

### 1.5 数据源的根因（第 5 处不是前端能单独修的）

`GET /api/v1/release/pending` 的实现是：

```python
# api/review_api.py:990-993
def release_pending(principal=Depends(principal_dep)):
    tenant = principal.get("tenant")
    return [row for row in repo.release_pending if row.get("tenant") == tenant]
```

而 `repo.release_pending` 只来自冻结投影 `release-pending.json`
（`review_api.py:287`），**authority 新建案件的放行队列不在其中**。

**实测**（开发装配接通写路径后）：

```
提交成功, case_id = case-c1fb0c5d19e2c6385b66
GET /release/pending → []
  ↑ 空列表 = authority 新案件不在放行队列里
```

所以拿不到 `submitter_id`，前端才写了 `null` 兜底 —— **第 5 处必须从后端修。**

★ 这条比「前端少渲染一个字段」严重：`isSelfSub = submitter_id === current.id`
恒为 false，意味着**自签拦截在这个路径上完全失效**，而界面上看不出任何异常
（按钮照常可点，后端 SoD 也照常会拒 —— 但那是另一道门，且报的是 403 而不是
「你不能签自己提交的」）。

### 1.6 三条全局缺口

| 缺口 | 事实 | 后果 |
|---|---|---|
| **无轮询** | 全仓 `setInterval` = **0 命中**，`WebSocket` / `EventSource` = 0，`visibilitychange` = 0 | 队列页不自动刷新，审核员必须 F5 才看到新案件；多人协作会漏案件 |
| **无 ErrorBoundary** | `grep ErrorBoundary\|componentDidCatch` = **0 命中** | 任意页面一个渲染异常 → 整站白屏 |
| **前端无角色门** | 全仓 `current?.roles` = **0 命中**（`IdentitySwitcher.tsx:53` 赋了值，从未被读） | `/admin/grants`、`/admin/sessions` 谁都能点进去，只靠后端 403 兜 |

### 1.7 页面分三级（这是排期依据）

| 级 | 判据 | 页面 |
|---|---|---|
| **A 现在就会误导人** | 显示的东西与事实不符，或缺失装成有值 | SubmitPage、CaseDetailPage、ReleasePage、AdminGrantsPage、ContentUnitViewer |
| **B 后端有、前端零接线** | 能力已上线但用户看不见 | CaseDetailPage（`workflow_timing`）、ReportPage（`receipt`）、全站（`version-diff`、`intent_inference`） |
| **C 只是难看，不误导** | 原样 `JSON.stringify`、声明了不渲染 | TaxonomyPage（三个 tab 原样 JSON）、AdminSessionsPage（整行 JSON）、AppealsPage（7 个时间字段声明了不渲染）、TakedownPage |

★ **A 与 B 有重叠**（CaseDetailPage 两边都在）—— 因为它的空白块与假数据来自同一个断点：
读数没接上，于是界面用兜底值填空。

---

## 二 · 已确认的关键决策（D1–D6）

| # | 决策点 | 裁定 | 影响 |
|---|---|---|---|
| D1 | 提交页那段前端自算结果 | **接通开发写路径；本地正则降级为「预检」并让位给真判定** | 要改 `web/scripts/review_api_dev.py` 装配；SubmitPage 结论区改为主次两层 |
| D2 | `version-diff` 放哪 | **案件详情页里一块「变更比对」** | 不改提交页（已 589 行）；比对块嵌在 `CaseDetailPage` |
| D3 | 「上一版正文」从哪来 | **手动粘贴两版正文** | 不碰已冻结的写路径；不建版本链 |
| D4 | `intent_inference` / `content_stage` 落库 | **两样都落：inference 进 state，stage 进 ContentUnit** | 要改 `review_reducer.py` + `contract.py` + `CaseDetail` |
| D5 | 队列刷新 | **只给三个列表页加轮询，标签页隐藏时不跑** | 新建一个轮询 hook；不动详情页（有未保存草稿） |
| D6 | 六处「缺失装成有值」 | **六处全改，且修 ReleasePage 的自签检查** | 见 §1.5，第 5 处要连后端一起修 |

---

## 三 · 接线方案（逐页）

### 3.1 全局层（先做，后面每一页都受益）

#### W-1 · 数据源与形态分离

现在 **18 处**页面**直接**调 `request()`（逐一数过：SubmitPage 1、InboxPage 1、
TakedownPage 5、AdminSessionsPage 1、AdminGrantsPage 2、TaxonomyPage 3、
ReportPage 1、AppealsPage 4），与 `api/client.ts` 的封装并存。

★ 这个数字**不能照抄审计报告**：它写的是「12 处」，而实测 grep
`await request|void request|= request` 得 22 行，逐行看有 4 行是
`requestGeneration.current`（不是 HTTP 调用）→ **18 处**。
「12」是另一份口径（按当时见过的文件数），复现不出来就不该写进方案
（AGENTS.md §2.2 第 1 条）。

不统一，就会出现「同一接口两处拼 URL」—— 那正是 `version-diff` 这类新接口
有一处漏改就会 404 的形状。

做法：
- 把 18 处裸调用按资源收进 `client.ts` / `write-client.ts` / `release-client.ts`。
- **只搬不改语义**；搬完 `request(` 在 `pages/` 下的出现次数必须为 0（一条断言）。

#### W-2 · 三态展示的统一组件

现在三态（有值 / 没值 / 读不出）在六个地方各自实现，且**全部把「没值」渲染成有值**。

做法：新建 `components/FieldState.tsx`：

```
<FieldState value={x} unit="阶段" reason={...} />
   有值   → 显示值
   没值   → 「未测」+ reason（不许给默认值）
   读不出 → 「读不出：<原因>」（与「没测」区分）
```

★ 这是六处修复的**同一个执行点**。分散改六次，下次加第七处还会错。

#### W-3 · ErrorBoundary + 轮询 hook

- `components/ErrorBoundary.tsx`：包在每个路由元素外层，单页崩不带走整站。
- `hooks/usePolling.ts`：`visibilitychange` 隐藏即停；**写动作期间暂停**
  （避免重取覆盖用户正在编辑的内容）；间隔 20 秒（可配）。
- 只挂三个列表页：`QueuePage` / `InboxPage` / `ReleasePage`（列表态）。

★ **详情页不挂轮询** —— 它有未保存草稿，自动刷新会冲掉。这是有意的排除，写进代码注释。

### 3.2 A 级：会误导人的地方

| 页 | 改什么 | 执行点 |
|---|---|---|
| `SubmitPage` | ① 结论区改两层：**真判定在上**（有 `case_id` 时），本地预检在下，标题写明「本地预检（不是判定）」+ 「只覆盖 3 类词、不产出 BLOCK」；② 后端起不来时不得让预检看起来像判定 | 两段渲染分支的顺序与文案；一条断言钉住「有 case_id 时预检块必须在真判定块之后」 |
| `ContentUnitViewer` | 去掉 `?? "ok"`，改三态 | W-2 组件 |
| `AdminGrantsPage` | 去掉 `?? "all"`、`?? "active"`；徽标跟随真实 state | W-2 组件 |
| `TakedownPage` | 去掉 `?? "t1"` | W-2 组件 |
| `ReleasePage` | 自签检查：**后端补 `submitter_id`**（见 §3.4），前端去掉 `null` 兜底；删死分支 | 后端 `release_pending` + 前端一处 |

### 3.3 B 级：把已上线能力接到界面

| 页 | 接什么 | 做法 |
|---|---|---|
| `CaseDetailPage` | `workflow_timing` | 新增「耗时」区块：总耗时 + 最慢三步。**`status=untested` 时写「未测（原因）」，不写 0 ms** |
| `CaseDetailPage` | 变更比对（D2/D3） | 一块「变更比对」：两个文本框（新版默认填当前案件正文）+ 按钮 → `POST /version-diff` → 三值结论 + 消失/新增声明 |
| `CaseDetailPage` | `intent_inference`（D4） | 阶段徽标：「阶段：提纲（**推断**）」+ 命中证据；`absent` 时显示「调用方申报」 |
| `ReportPage` | `receipt` 的 skill 指纹与耗时 | 「存证与校验」块补 `skill_id` / `version` / 指纹；与报告 md 那一行**同源** |
| 全局 | 前端拿到 `receipt` | `CaseDetail` 响应要带 `receipt`（现在只有 7 个键，没有它） |

### 3.4 后端要补的四处（前端接线的前提）

| # | 补什么 | 为什么必须从后端补 |
|---|---|---|
| B-1 | `review_pending` 补 authority 来源（`submitter_id`） | 前端拿不到这个值就只能写 `null`，自签检查恒 false —— 这是**静默的合规失效** |
| B-2 | `intent_inference` 进 `review_reducer.state` + `CaseDetail` 返回 | 现在 payload 里有、state 里没有 = **我的 T-455 漏的那一环** |
| B-3 | `content_stage` 进 `ContentUnit` | 现在 `contract.py` 里 0 次。已验：`unit_id` 只由 `kind\|raw_sha256\|text_sha256` 算出，**加字段不改 id**；`validate()` 查不变量不查白名单，**不会因多字段变红** |
| B-4 | `CaseDetail` 响应带 `receipt` | 前端要显示 skill 指纹，现在拿不到 |

### 3.5 开发装配接通写路径（D1 的前提）

`web/scripts/review_api_dev.py` 现在**没有** `review_command_service`，所以
`POST /submissions` 恒 501。**已实测跑通**，需要四个部件齐全：

```python
lease     = WriterLease(RUN_DIR/"authority"/"w.lock"); lease.acquire()
authority = BusinessEventStore(RUN_DIR/"authority", lease=lease)
projection= ProjectionStore(RUN_DIR/"projection.sqlite")
service   = ReviewCommandService(authority, projection)   # report_store 可 None
ingestor  = SubmissionIngestor(authority_query=...)       # ★ 缺它也是 501
create_app(..., review_command_service=service,
           submission_ingestor=ingestor,
           case_source=AuthorityCaseSource(authority), app_env="dev")
```

★ **两道门，只补一道不够**：`write_api.py:447` 判
`review_command_service is None or submission_ingestor is None` → 501。
只传 service 实测仍 501（我第一版就是这么试的）。

★ `case_source` 要包 `AuthorityCaseSource(authority)`，**不能直接传 store**：
`CaseOverlayRepository.get_case` 调的是 `case_source.get_case(...)`，
而 `BusinessEventStore` 没有这个方法（实测 `AttributeError`）。

★ 三个路径都必须在仓外：`ProjectionStore.__init__` 硬性拒绝仓内路径
（`projection_store.py:37-38`）。`RUN_DIR` 本来就在仓外，够用。

★ `report_store` / `report_bridge` 可以传 None：`review_command_service.py:101-104`
明写「未装配不返回失败，开发装配走这条路」。**提交能通，只是不产出报告。**

**实测读数**（2026-10-27，上述装配）：

```
POST /api/v1/submissions → 200
案件详情键: case_id, content_unit, ir, multimodal_note,
            multimodal_observations, review, workflow_timing
workflow_timing 有值: True | total_ms = 3.705
receipt 有没有返回: False          ← B-4 要补的就是它
```

★ 最后一行同时证明了两件事：**B 级接线现在就能做**（`workflow_timing` 已经在
`GET /cases/{id}` 的响应里），而 **B-4 是真实缺口**（`receipt` 不在响应里，
所以前端无论如何拿不到 skill 指纹）。

---

## 四 · 次序与依赖

```
W-1 数据收敛 ──┐
W-2 FieldState ─┼─→ A 级六处（都用 W-2）
W-3 ErrorBound/轮询 ─┘        │
                              ↓
B-1..B-4 后端补四处 ──→ B 级接线（CaseDetail/ReportPage）
                              │
开发装配接写路径 ──→ SubmitPage 两层结论
```

**为什么 W-2 排在 A 级之前**：六处修复是同一个病的六个症状。
先有统一组件，六处变成六个调用点；否则改六次，第七处还会错。

**为什么 B-1 必须和 ReleasePage 同一票**：前端去掉 `null` 兜底之后，
如果后端还没补 `submitter_id`，自签检查会从「恒 false」变成「恒 未测」——
**看起来仍然正常**。两件事必须同时。

---

## 五 · 验收口径

| 组 | 判据 | 什么变异让它红 |
|---|---|---|
| V1 | `pages/` 下裸 `request(` 出现次数为 **0** | 新增一处裸调用 → 红 |
| V2 | `FieldState` 对「没值」必须输出「未测」，且**不含**任何看起来像值的字 | 把兜底值加回去 → 红 |
| V3 | 六处修复点逐个断言：源码里不再有 `?? "ok"` / `?? "all"` / `?? "t1"` / `submitter_id: null` | 任一处复发 → 红 |
| V4 | 轮询在 `document.hidden` 时不发请求 | 去掉 visibility 判断 → 红 |
| V5 | 详情页**没有**挂轮询（有意的排除） | 挂上去 → 红 |
| V6 | 有 `case_id` 时，预检块必须排在真判定块**之后** | 调换顺序 → 红 |
| V7 | `workflow_timing.status=untested` 时界面不含 `0 ms` | 改成报 0 → 红 |
| V8 | `intent_inference` 能从 `GET /cases/{id}` 读到（端到端） | reducer 又把它丢掉 → 红 |
| V9 | `content_stage` 在 `ContentUnit` 里可读，且 `unit_id` 与加字段前**相同** | 改了 id 算法 → 红 |
| V10 | `release_pending` 对 authority 新案件返回真实 `submitter_id` | 回落到 `null` → 红 |

★ 每条都要**真变异**验一遍（喂坏样本必红、喂好样本必绿）。
★ 断言里不许出现「名字出现过就算」这类恒真判据 —— 本 ADR §1.3 就是被这种判据放过去的。

---

## 六 · 不做什么（明确排除）

- **不删提交页的本地正则**（D1 裁定是降级不是删）—— 但必须让位、必须贴标签。
- **不建案件版本链**（D3）—— 手动粘贴两版。
- **不给详情页加轮询** —— 有未保存草稿。
- **不改 `taxonomy.json` 的本地数据** —— C 级，另票。
- **不重开守衡**（长期停令仍有效）。
- **不动判定规则内容**（`rules-v1.json` 36 条）。

---

## 七 · 可证伪性

| 断言 | 什么让它过期 |
|---|---|
| 「四项后端能力前端零接线」 | 搜 `workflow_timing\|version-diff\|intent_inference\|skill_hash` 于 `web/src` 非空 |
| 「提交页结论永不产出 BLOCK」 | `verdict` 的三元里出现 `"BLOCK"` |
| 「六处把缺失渲染成有值」 | 上述四个兜底字面量在源码里消失 |
| 「前端无轮询」 | `setInterval` 于 `web/src` 非空 |
| 「前端无角色门」 | `current?.roles` 非 0 命中 |
| 「`intent_inference` 不进 state」 | `review_reducer.py` 出现该键且端到端读得到 |

★ 本节每条都应在补上之后**从本节删掉**，不留成一份永远正确的清单
（与 ADR-0020 §六 同一条自我要求）。
