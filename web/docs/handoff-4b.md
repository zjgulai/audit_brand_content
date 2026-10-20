# 交接包 · 内容审核工作台（Web 复核面）

> 交给 `audit-multi-content-4b`。配套 `web/docs/brief.md` 与 `web/DESIGN.md`。
> 日期：2026-10-20。**本文件不含任何要求你改动规范正文的内容——只有两项输入需求与一份交底。**

---

## 一、输入需求（✅ 2026-10-20 已由 4b 交付，本节目的是留档口径）

### 1. `taxonomy.json` 的版本字段 ——**已落地**

4b 加了生成器 `tools/gen_taxonomy_json.py`，三个值**机器生成、不是手抄**：

| 项 | 实测值 | 复现 |
|---|---|---|
| `meta.spec_version` | `v1.1` | `python3 tools/gen_taxonomy_json.py --check` |
| `meta.spec_fingerprint` | `562a90352c23` | 同上（正文剥掉版本说明块后 sha256 前 12 位） |
| `meta.boundary_disputes` | **7 条**，全部 `status: underdetermined`、`resolved_in: null` | 同上 |
| `meta.version` | `v1`（**兼容旧读取方，不得当版本用**） | 同上 |

生成器三条命令（`--check` 与磁盘对拍不一致退 1；`--selftest` 6 项反向对照）：
`python3 tools/gen_taxonomy_json.py [--check|--selftest]`。

**界面读取口径（已定，不许简化）**：

- 「按 spec vN 判定」这行用 `spec_version` + `spec_fingerprint` **两个一起**。
  只写版本号会漂：同名 `-v1` 文件可以装不同内容。
- 对 7 条 `boundary_disputes` 的规则，详情页显示 **`status: underdetermined`**，
  **不显示某个轴**。理由（4b 原话）：**规范确实定不住它们**，写一个轴等于替规范做了它没做的判断。
- `boundary_disputes[].axis` 字段里装的是**争议描述**（如「FCT5 的排除句与规则触发条件正相反」），
  不是七轴枚举值。**字段名有误导，读取时按描述处理。**

> ⚠️ 旧 `taxonomy.json` 有 114 条 criteria，**漏掉 DSC11 / DSC12 / FCT10 三条**——
> 界面之前展示的判据比规范落后。现在 158 条、编号条件 63 条（CHN6 / RGT8 / SCN8 / DSC12 /
> BRD10 / FCT10 / CLM9），`--check` 会挡住再次漂移。

### 2. 规范补丁的变更说明

已拿到：`v1.1 / 562a90352c23`。**后续每改一次正文，要同步给新的这一对值**，
界面那行随之更新；给不出新值的改动，视为未发布。

---

## 二、给你的交底（**2026-10-20 更新：UI 已由我实现，你是验收方，不是实现方**）

> 委托方后来把 `web/` 的设计与开发**全权交给我**了，所以原先「你收口后接手实现」
> 那条作废。你的角色改成：**按下面这 13 条断言复核我的实现，并告诉我哪里不符合规范语义。**

### 2.1 现状（2026-10-20 实测，**已不是只读骨架**）

| 项 | 读数 | 复现 |
|---|---|---|
| 前端 | Vite + React 19 + **react-router-dom 7**；npm（不是 pnpm，本机 `pnpm: command not found`） | `cat web/package.json` |
| 队列 | A1 Triage queue：只列 REVIEW / 待自决；**口径 bug 已修**（见 §2.2 坑 1） | `web/src/pages/QueuePage.tsx` |
| 详情页 | A7 研究简报：判定 + 覆盖证明 + **证据链（本地渲染，不接模型）** + 复核动作 | `web/src/pages/CaseDetailPage.tsx` |
| API 客户端 | **5 个 GET + 2 个写端点**（claim / actions） | `web/src/api/client.ts` |
| 后端读 | 19 个 GET，逐案 `can_read_content` | `api/review_api.py` |
| 后端写 | **12 个 POST，已挂载**（`api/review_api.py:553`）；前端只用了 2 个 | `grep register_write_routes` |
| 权限 | `actions` 走 `require_review` → `can_act(principal,"case.review",case)` | `api/write_api.py:265` |
| 身份 | 本地切换器 `POST /dev/session`（**只在 `web/scripts/review_api_dev.py`，`api/` 一行未改**） | 见 README |
| 夹具 | 21 条确定性夹具 + `case-smoke`，`sample:true`，12 项自证 | `python3 web/scripts/seed_fixture.py --selftest` |
| 联调 | `bash web/scripts/dev-up.sh` → **rc=0**；无障碍 40 项 0 违规；切片断言 13/13 | 实跑 |
| 真实案件数 | **1 条**（`case-smoke`，BLOCK —— 它**不该**进待办队列） | 临时投影 |

### 2.2 已经踩到的四个坑（别重复踩）

**坑 1 —— 队列口径是错的（真 bug，不是风格问题）**

```
web/src/api/client.ts:80   getQueue: () => getJson("/queue")
        ↓ vite 代理
vite.config.ts              /review-api/queue 保持原样（不改写）
        ↓
api/review_api.py:465       """联调别名：只读列出所有可读案件"""
```

于是「复核队列」页里**BLOCK 与 PASS 也出现了**。真正的待办队列是 `GET /api/v1/queue`（只返回 `REVIEW` + `待自决`，见 `api/review_api.py:459`）。

**修法**：客户端改走 `/cases` 之外的正确路径时，注意 vite 代理只对 `/review-api/queue` 做了原样保留；要拿真队列得让它重写成 `/api/v1/queue`。**这是一处要动 `vite.config.ts` 与 `client.ts` 两处的地方，改完必须有断言。**

**坑 2 —— 未测被折叠成空值**

`QueuePage.tsx` 里 `{c.state ?? "—"}`、`{c.layer ?? "—"}`。按 `UIUX:463` 的「未测独立徽标，不得显示为 0 或通过」，这写法是**反例**。`—` 与「未测」在视觉上不可区分。

**坑 3 —— 品牌红与告警红撞色**

`#6A2C3A`（品牌，色相 346.5°）与 `--bad`（色相 356°）只差 9.5°。**规则：品牌红只用于人要做的高风险动作，绝不用在状态徽标上。** 详见 `DESIGN.md` §7。

### 2.3 已定的十条决策（不要重新讨论）

| # | 决策 |
|---|---|
| 1 | 改造现有 `web/`，**不新起** `@agent-native/core` 脚手架 |
| 2 | 首个切片 = 队列 → 详情 + 复核动作（claim / save_draft / submit） |
| 3 | 智能体只做「解释判定」，零新写权限 |
| 4 | 解释 = **纯本地渲染，不接模型**（保住 `api/`/`base/` 零 LLM 依赖） |
| 5 | 本地开发身份切换器，**绝不进生产** |
| 6 | **你收口后接手 UI 实现** |
| 7 | 首屏用确定性夹具（18–24 条，真实 schema，`sample: true`） |
| 8 | 品牌色 `#6A2C3A` / `#9c5455` / `#f6eeed`（取自 momcozy.com 实测） |
| 9 | 「做成了」= 机器可执行断言（纳入 `dev-up.sh`），不是截图评分 |
| 10 | 七种一等状态先做六个；**投影滞后不做**（当前读文件的后端永远不产生 202） |

### 2.4 你接手时要做的事（按顺序）

1. **先跑** `bash web/scripts/dev-up.sh`，确认 rc=0。它现在是绿的，红了就是环境问题不是你的问题。
2. **先修队列口径**（§2.2 坑 1），并**给它写断言**——这是唯一一个「已经错了但没有任何东西会红」的地方。
3. **读** `web/docs/brief.md` 的 Invariants 八条，逐条找到代码落点；找不到的，说明它还是注释。
4. 再做详情页与三个动作。
5. 最后接确定性夹具。

### 2.5 需要你写的断言（`web/scripts/check_review_slice.mjs` 或扩充 `a11y_check.mjs`）

| # | 断言 | 为什么 |
|---|---|---|
| **A1** | ① **正向**：`GET /api/v1/queue` 每条 `state ∈ {REVIEW, 待自决}`；② **反向对照**：塞一条 **PASS** 案件进去，断言它**不出现**；同理塞一条 **BLOCK** | 坑 1。**只改 URL 不够** |
| A2 | 页面源码里不存在 `?? "—"` 这类把 null 折叠成符号的写法 | 坑 2 |
| A3 | 详情页对 `coverage_state=partial` 必须渲染出「仅已覆盖部分可判」字样 | UIUX:463 |
| A4 | 前端源码里**不含** `release-decision` 的 POST 调用 | 硬门 #90 |
| A5 | 提交 `submit` 未带 `conclusion` → 后端 400（这是后端已有行为，断言它端到端仍成立） | 防「能点」变成「能改」 |
| A6 | 品牌红 `#6A2C3A` 不出现在状态徽标的样式规则里 | DESIGN §7 |
| A7 | 夹具生成物逐条过契约校验 | 防夹具与 schema 漂移 |
| **A8** | 详情页对 7 条 `boundary_disputes` 的规则，渲染出 `underdetermined`，且**不渲染任何单一轴**（正向 + 反向：非争议规则必须渲染出轴） | 规范定不住它们 |
| **A9** | 「按 spec」那行**同时**出现 `spec_version` 与 `spec_fingerprint`；删掉任一个即红 | 只写版本号会漂 |

> **A1 为什么必须有反向对照**（4b 的根因诊断，值得单独记）：
> 这条 bug 活了这么久，是因为**没有任何测试断言过「队列里不该有什么」**。
> `check_queue_page.mjs` 断言的是「页面上有队列」「能点到案件」——都是**肯定**断言；
> 而「队列里出现 PASS」是一个**否定**断言。
> **否定断言永远比肯定断言少写**，于是下次换端点，同一个 bug 会静默回来。
> 这与 `AGENTS.md` §2.4.1 第 4 行是同一个形状：**否定结论的输入不是「我采的那条通道里没有」。**

> **A2 与 A6 是文本级断言，容易被自己的解释文字骗到**（本仓 §2.4.4 的教训：第一版判据被它自己的注释绊倒）。写的时候把「注释不算代码」这条读法带上。

---

## 三、我不做的事

- 不改 `PMO/implement/` 下任何规范与评测文档
- 不碰 `research/governance/`
- 不碰 `tools/llm_rule_axis_eval.mjs`
- 不手改 `web/src/data/taxonomy.json`
- 不碰任何 `release_status` 路径

---

## 四、边界那条 —— ✅ 已由委托方裁定（2026-10-20）

4b 的判断是对的：这句应该改，但**不是改成「只写」**。委托方已同意按下面这条落。

`web/README.md` 的「边界」一节已重写为五条（本轮唯一改动的既有文件）：

| # | 条款 | 落点 |
|---|---|---|
| 1 | **不重算判定**。`state`/`coverage`/`authority`/`release_status` 一律读后端 | 断言 A4 / A9 |
| 2 | **人工动作只经写 API**。claim / save_draft / submit 只走已挂载端点 | 断言 A5 |
| 3 | **`release_status` 不出现任何可写控件** | 断言 A4 |
| 4 | **不碰 `base/`、`api/`、`tools/` 的源码**；调 HTTP 接口不算碰 | 代码评审 |
| 5 | 报告是不可变静态存档，Web 不编辑、不重算 | 无代码落点（现状即满足） |

**关键的一句**（留在 README 里，防止后来人误读）：

> `reviews_ledger.version` 变化**不是「Web 在改判定」**，是**人工动作被记录**。
> 把这两件事混成一句「Web 只读」，会让后来的人以为界面不许有人工操作 ——
> 而产品本身要求复核员必须能操作。

README 末尾已加执行点承诺：第 1、2、3 条必须在 `web/scripts/check_review_slice.mjs` 里有断言，
指不出断言的上限按 `AGENTS.md` §2.4 就是注释不是约束。
