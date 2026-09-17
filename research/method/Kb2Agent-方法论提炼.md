# Kb2Agent 方法论提炼

> 分析对象：本地仓库 `/Users/lute/Project/audit_multi_content/research/method/Kb2Agent`（git HEAD `57f8e3e`，工作区干净）
> 分析方式：实际打开文件逐个阅读，不依据目录名推断。所有结论均附文件路径与原文摘录。
> 用途：为「Momcozy 营销内容合规审查 Agent」项目的需求知识库设计提供可直接照搬的规则集。

---

## 0. 阅读范围与事实边界

### 0.1 实际读取的文件

| 类别 | 文件 |
|---|---|
| 知识章节 | `docs/knowledge/` 下 `00-introduction`、`01-framework`、`02-decision-matrix`、`11-kb-evolution`、`appendix-validation` |
| ADR | `docs/architecture/adrs/` 的 `README.md` 与 `001`–`005` 全部 |
| 注册表 | `knowledge-system/` 下 `claims.yml`、`concepts.yml`、`documents.yml`、`roles.json`、`product-claims.json`、`product-decisions.json`、`product-lines.json`、`capability-map.json`、`acceptance.yml`、`public-projection-manifest.json` |
| Schema | `knowledge-system/schemas/` 的 `claim`、`concept`、`acceptance`、`roles`、`product-claims`、`product-decisions`、`product-lines`、`capability-map`、`g6-a3-review-record`、`g6-a10-r1-accepted-review-record` |
| 门禁设计 | `docs/architecture/` 的 `m1-a-product-contract`、`m1-a-schema-catalog`、`g6-a1`、`g6-a2`、`g6-a3`、`g6-a5-r1`、`g6-a6`、`g6-a10-r1`、`g6-a11`、`g7-a1` |
| 审计与回执 | `content-audit.md`、`knowledge-system-audit.md`、`qa-receipt.md`、`g2-1`–`g2-4` 审计 |
| 产物实证 | `docs/public/reference/m1b/` 全部 7 个文件、`runs/RUN-AMZ-M1B-001/` 全部 5 个文件、`docs/public/reference/g6/agent-lab-bundle.json` |
| 机器可执行规则 | `scripts/acceptance-registry.mjs`、`claim-registry.mjs`、`check-acceptance.mjs`；`reference/ontology/{relations,permissions,terms}.json`；`reference/schemas/common.schema.json` |

### 0.2 仓库中未见的内容（不编造）

- **G3 门**：全仓未见任何 G3 门禁定义或回执（`G4`/`G5` 系列仅作为历史引用出现，如 `docs/architecture/g6-a6-…md` 的 `D["G5-R2 current static closeout"]`）。
- **G2.5 的执行回执**：`knowledge-system-audit.md:136` 只写了计划「G2.5 学习与检索验证：为 10–15 个核心问题建立黄金查询集」，未见对应回执。
- **replay bundle 的访问控制规格**：只知「无 provider key 也必须能复放」，未见谁/如何被授权的鉴权矩阵。
- **Momcozy、母婴、营销合规**：仓库中完全未见。F 节全部为我的映射推演，非仓库事实。

---

## A. 对象模型

### A.1 五类对象各自的字段

Kb2Agent 实际存在**两套并存的对象模型**：Guide 侧（注册表形态，管理"文档内容的可信度"）与 Reference 侧（Schema 形态，管理"知识对象到行动包的编译链"）。A.1–A.4 讲 Guide 侧，A.5 讲 Reference 侧。

#### （1）document —— 文档身份

字段来自 `knowledge-system/documents.yml`，契约明文写在文件头：

```yaml
identityContract:
  docId: Stable semantic identity; must not change when a title, route, or reading order changes.
  displayNumber: Human-facing chapter or appendix identifier.
  route: Existing public route; G1 preserves every route in this registry.
  learningOrder: Zero-based recommended reading order; independent from displayNumber.
```

即每个文档有 4 个**互不推导**的身份字段。`knowledge-system-audit.md:43-52` 给出稳定性规则：

| 字段 | 职责 | 稳定性规则 |
|---|---|---|
| `docId` | 文档的稳定语义身份 | 标题、路由、顺序改变时也不改 |
| `displayNumber` | 读者看到的章节或附录编号 | 只表达出版编号，不表达文件名或阅读顺序 |
| `route` | 当前公开 URL | 变更必须提供兼容路由 |
| `learningOrder` | 推荐学习路径 | 可独立调整，不改变章节身份 |

另含 `maturity`（Guide 账本等级）、`prerequisites`（先修文档 ID 数组）。

#### （2）claim —— 断言（本方法论的核心对象）

Schema：`knowledge-system/schemas/claim.schema.json:229-295`。18 个必填字段，`additionalProperties: false`：

```json
"required": ["claimId","documentId","anchor","locatorText","statement","claimType",
             "risk","volatility","verification","evidenceGrade","asOf","ownership",
             "applicability","limitations","sourceRefs","evidenceRefs","nextAction"]
```

关键枚举与最小长度约束（**字段设计本身就是方法论**，逐条列出）：

| 字段 | 约束 | 方法论含义 |
|---|---|---|
| `claimId` / `documentId` / `anchor` | `^CLM-…$` / `^KS-…$` / `^claim-clm-[a-z0-9-]+$` | 稳定 ID + 外键 + 正文锚点，强制双向回链 |
| `locatorText` / `statement` | minLength **8** / **12** | 定位原文不能空指向；断言必须有实体内容 |
| `claimType` | `external-fact`/`legal-context`/`normative-control`/`calculation`/`interface-contract`/`current-state`/`methodology` | 按**证据类型**分类，不同类型走不同复核路径 |
| `risk` | **仅** `high`/`critical` | 只有高风险断言才准进注册表（低风险不值得治理成本） |
| `volatility` | `low`/`medium`/`high` | 单独字段刻画"多久会失效" |
| `verification` | `pending`/`source-reviewed`/`synthetic-supported`/`fixture-verified`/`production-observed`/`authorized-live`/`blocked` | 状态机，与 `evidenceGrade` 机器一一映射 |
| `evidenceGrade` | `L0-unverified`/`L1-public-or-runtime`/`LO-S-synthetic`/`L2-fixture-or-dry-run`/`L3-production-read-only`/`L4-authorized-live` | 证据等级天花板 |
| `asOf` | date 或 null | 时效锚点 |
| `ownership` | 4 个 ROLE 外键（见下） | **责任不可为空** |
| `applicability` / `limitations` | 均 minLength 1 | 适用边界与"不能证明什么"，**都必填** |
| `sourceRefs` / `evidenceRefs` | `SRC-*` / `EVD-*` 数组 | 来源与证据外键 |
| `nextAction` | minLength 1 | 每个断言必须写明下一步动作 |

`ownership` 子结构（`claim.schema.json:218-228`）是**四个互相独立**的角色外键：

```json
"required": ["contentOwner","evidenceReviewer","testOwner","finalApprover"]
```

实例见 `knowledge-system/claims.yml:236-256`（CLM-SEC-001）：`applicability: 用于工程风险管理参考，不是法律合规结论。` `limitations: 一手网页复核只能证明公开表述；不能证明组织已实施框架，也不能替代适用法律。`

状态→等级的映射被写死在代码里（`scripts/claim-registry.mjs:16-24`），不是文档约定：

```js
['pending', 'L0-unverified'], ['blocked', 'L0-unverified'],
['source-reviewed', 'L1-public-or-runtime'], ['synthetic-supported', 'LO-S-synthetic'],
['fixture-verified', 'L2-fixture-or-dry-run'], ['production-observed', 'L3-production-read-only'],
['authorized-live', 'L4-authorized-live']
```

#### （3）concept —— 概念（术语治理）

Schema：`knowledge-system/schemas/concept.schema.json:79-124`。必填 10 字段：

```json
["conceptId","term","aliases","definition","canonicalDocument",
 "definedIn","usedIn","prerequisiteOf","conflictsWith","related"]
```

约束要点：

- `definition` minLength **16**；`term`/`aliases` 不得跨概念冲突（`knowledge-system-audit.md:102`：「术语/别名不跨概念冲突」）。
- `definedIn`：`{documentId, anchor(^concept-[a-z0-9-]+$), locatorText(min 8)}`。
- `usedIn`：数组，每项 `{usageId(^USE-…-\d{3}$), documentId, anchor, locatorText, usageType}`，`usageType` 枚举 `applies`/`compares`/`depends-on`/`validates`/`implements`/`governs` —— **概念被"使用"也要登记，并且要标注使用语义**。
- `prerequisiteOf`：有向图，全图必须无环（`concepts.yml:12`：「A directed learning dependency; the complete graph must remain acyclic.」）。
- `conflictsWith`：**对称**关系，`kind` 枚举 `not-equivalent` / `boundary-conflict`，`reason` minLength 12。原文契约：`concepts.yml:13`「A symmetric non-equivalence or boundary warning; it means the concepts must not be conflated.」
- `canonicalDocument` 与 `definedIn.documentId` **刻意分离**：`knowledge-system-audit.md:184`「`canonicalDocument` 与 `definedIn` 分离，允许专题页晚于首次解释而不破坏学习路径。」

#### （4）role —— 责任角色

两处定义，粒度不同：

**文档级 owner roles**（`claims.yml:8-127`，schema 在 `claim.schema.json:176-216`）：每章 4 个角色，功能枚举固定：

```json
"ownerFunction": { "enum": ["content-owner","evidence-reviewer","test-owner","final-approver"] }
```

每角色字段：`roleId`(`^ROLE-…`)、`documentId`、`function`、`label`(min 4)、`responsibilities`(**min 12**)、`assignmentState`、`assignee`、`acceptedAt`、`acceptanceEvidenceRef`。

**产品级 4 角色**（`roles.json` + `roles.schema.json`）：恰好 4 个（`minItems:4, maxItems:4`），各有 `roleId`/`name`/`responsibilities`(min 3 项)/`assignee`/`acceptanceState`（`unassigned`/`assigned`/`accepted`）。文件顶部写着全方法论的治理总则：

```json
"acceptanceRule": "四个角色必须由互相独立的具名人员签署；角色映射不是接受。"
```

三层状态被刻意分开：`role-mapped` → `assigned` → `accepted`（`claim.schema.json:202`）。`qa-receipt.md:56`：「`authorized-live` 越级测试除要求 L4 回执外，还要求四角色全部 `accepted`；仅有角色占位不能成为在线授权。」

#### （5）capability —— 能力（对外可声明的产品力）

Schema：`knowledge-system/schemas/capability-map.schema.json`。必填 9 字段：

```json
["id","name","line","status","evidenceGrade","deployment","evidenceRefs","ownerGate","forbiddenClaims"]
```

- `evidenceRefs` **minItems 1**：每项 `{kind: path|commit|url, value}`。
- `forbiddenClaims` **minItems 1**：**每项能力都必须显式写明"不得声称什么"**，这是最反直觉、也最值得照搬的设计。
- `status` 枚举 `live`/`accepted`/`replayable`/`draft`/`blocked`/`design-only`。
- `ownerGate` 正则 `^G[0-9][A-Za-z0-9-]*$` —— 能力必须挂在某个门上。

注册表级 `scopeNote` 写明总则（`capability-map.json:5`）：

> 能力图谱的机器可读注册表：每项能力必须绑定证据引用与禁止声明；状态只能由门禁回执支撑，不得由页面完整或上线事实自动抬升。

#### （6）附带的两个支撑对象

**Source**（`claim.schema.json:54-81`）：`sourceId`(`^SRC-…`)、`title`、`kind`(`official-web`|`repository`)、`authority`(`first-party`|`project`)、`reviewedAt`、`notes`，并用 `if/then` 强制：`official-web` 必须有 `url`，`repository` 必须有 `path`。

**Evidence**（`claim.schema.json:82-112`）：`evidenceId`(`^EVD-…`)、`title`、`kind`(`fixture`|`test`|`read-only-audit`|`acceptance-receipt`|`production-observation`|`authorized-live-receipt`)、`path`、`grade`、`command`、`assertion`、可选 `receipt`。且有一条硬约束（同文件 99-111 行）：

```json
"if": {"properties":{"kind":{"const":"acceptance-receipt"}}},
"then": {"required":["receipt"], "properties":{"grade":{"const":"L4-authorized-live"}}},
"else": {"not": {"required":["receipt"]}}
```

即**验收回执型证据只允许 L4 等级**，别的等级不得携带 receipt 字段。

### A.2 对象间关联与外键规则

七条规则，全部为机器强制：

1. **ID 前缀即类型**：`KS-`(document)、`CLM-`(claim)、`CONCEPT-`/`USE-`、`ROLE-`、`SRC-`、`EVD-`、`ACC-`、`ACT-`、`ADS-`、`CAP-`、`PRODUCT-CLAIM-`。
2. **外键必须能在同注册表内解析**，否则视为悬空引用。
3. **双向回链**：claim 通过 `documentId`+`anchor` 指向正文，正文通过 `claimRefs`+可见账本指回 claim（`knowledge-system-audit.md:160`：「每页通过 `claimRefs`、稳定正文锚点与可见 `ClaimLedger` 形成双向回链」）。
4. **对称关系必须双向一致**（`conflictsWith`、`related`）；**有向图必须无环**（`prerequisiteOf`）。
5. **端点为白名单**（Reference 侧）：`reference/ontology/relations.json` 逐条声明每种关系的 `from`/`to` 类型集合，例如 `{"type":"supersedes", …, "sameType":true, "acyclic":true}`。`m1-a-schema-catalog.md:29-35` 列出校验器同时阻止的五类错误：悬空引用、声明类型/真实类型不一致、不允许的 `fromType → toType`、`supersedes` 有向环、Case 绕过 PromotionDecision 直接产生 Skill。
6. **引用等级必须"够得着"**：验收契约的 owner 必须恰好 4 个（`minItems:4,maxItems:4`），其中 `authorizationRoleId` 必须是 `evidence-reviewer`、阈值批准人必须是 `final-approver`（`scripts/acceptance-registry.mjs:512-518`）。

### A.3 dual-product-ledgers：到底是哪两个账本

答案在 `docs/architecture/adrs/001-dual-product-ledgers.md`：

> ## 决策
> Guide 使用 `principle/solution/runnable/acceptance`；Reference 使用 `draft/replayable/live-candidate/accepted`。**两套账本只能通过显式引用关联，不允许互相继承等级。**

即：

| 账本 | 产品线 | 权威资产 | 等级阶梯 | 当前状态 |
|---|---|---|---|---|
| **Guide 账本** | MKD Guide（26 章知识站） | documents、concepts、claims、sources、learning-paths | `principle → solution → runnable → acceptance` | 2/22/2/0（`product-lines.json:14`） |
| **Reference 账本** | MKD Reference Lab（编译器/Agent 运行时） | schemas、fixtures、compiler、runtime、tasks、traces、evaluations、receipts | `draft → replayable → live-candidate → accepted` | `replayable` / L2（`product-lines.json:25-26`） |

职责边界由 ADR-001 的「后果」明确定义：

> - 页面必须说明自己引用的是哪条产品线的证据。
> - Reference fixture 通过**不改变** 26 个 Guide 页面的成熟度。
> - Guide Claim 通过也**不允许**把 runtime 标为 replayable。

`docs/architecture/m1-a-product-contract.md:24` 复述：

> 两条成熟度必须分账。Guide 的文章完整度不能证明 Reference 已运行；Reference 的固定 fixture 也不能证明 Guide 全文事实已验收。

**双账本还带出第三个对象：产品声明（product-claim）**。`product-claims.json` 的每条声明有 7 个必填字段，其中 `forbidden` 与 `supported` 等长（都 min 10）：

```json
{"claimId":"PRODUCT-CLAIM-REFERENCE-M1A","productLineId":"REFERENCE",
 "decision":"allowed-with-label","maxEvidenceGrade":"L2-fixture-or-dry-run",
 "supported":"通过机器校验的 Schema、固定 fixture 与本地交互原型可称为可重复校验的 M1-A candidate。",
 "forbidden":"不得把 fixture/UI replay 称为 compiler runtime、live Agent、accepted 或 production-ready。",
 "nextEvidence":"由 Owner、Amazon Ads 领域复核人、工程测试与安全发布角色完成独立审阅；M1-B 另行授权。"}
```

`decision` 枚举 `allowed`/`allowed-with-label`/`blocked`。也就是说：**对外的每一句话都被登记，并绑定它允许引用的最高证据等级**。

### A.4 双账本能否互推：一条硬规则

`product-lines.json:5`：

> Guide 与 Reference 的成熟度独立计算；**任一产品线的通过不得抬升另一产品线**。

这条规则的实现是 `scripts/acceptance-registry.mjs:582-591`：如果页面在 frontmatter 里声称 `maturity: acceptance`，但其契约的计算态不是 `accepted`，直接报错 `cannot claim acceptance while … is not accepted`。

### A.5 补充：Reference 侧的 L0–L6 对象链（另一套对象模型）

`docs/architecture/m1-a-schema-catalog.md:15-23` 给出分层与"进入下一层的必要条件"：

| 层 | 主要对象 | 进入下一层的必要条件 |
|---|---|---|
| L0 | SourceArtifact / SourceRevision / StructuralElement | revision、hash、来源与结构定位完整 |
| L1 | EvidenceFragment / Claim | locator 可解析、支持与冲突引用可追溯 |
| L2 | Concept / Metric / DecisionModel / Case / Playbook | 类型化、版本化、关系端点合法 |
| L3 | Skill | **PromotionDecision 存在**，首案最高 E2 |
| L4 | TaskPackage | Skill、对象闭包和 EvaluationContract 均可解析 |
| L5 | ActionPackage / RunTrace | 固定 fixture 可重放，事件输入输出闭合 |
| L6 | KnowledgeReceipt / ReleaseSnapshot | 评估引用、trace、manifest hash 一致 |

执行权限分级另有一张表（`reference/ontology/permissions.json`）：E0 只读解释 / E1 只读检索 / E2 只读检索+受控计算+行动草案 / E3 可逆外部写入 / E4 高影响或不可逆动作，且 `"publicMaximum": "E2"`、`"externalWrite": false`、`"canonicalKnowledgeWrite": false`。

---

## B. 门与产物

### B.1 G 门系列：每个门是什么，谁有权通过

仓库中出现的 G 门系列（按证据强度排列）：

| 门 | 名称 | 解决什么问题 | 出处 |
|---|---|---|---|
| **G0** | 真实计量基线 | "计量是否可信"——修掉 AST visitor 误用 `Array.push()` 返回值导致的虚报，锁定 26 页/265 H2/352 代码块基线 | `knowledge-system-audit.md:19-39` |
| **G1** | 文档身份契约 | "文档身份是否稳定"——`docId`/`displayNumber`/`route`/`learningOrder` 四字段分离，26/26 唯一 | `knowledge-system-audit.md:41-52` |
| **G2.1–G2.4** | Claim Schema 与三章试点 / 责任链与首批 Lab / 概念使用图 / 验收契约 | 依次解决"断言可否逐条治理""责任能否落到角色""概念能否跨章一致""成熟度升级能否机器验收" | `knowledge-system-audit.md:132-135` |
| **G2.5** | 学习与检索验证 | **仅计划，未见回执** | `knowledge-system-audit.md:136` |
| **G3** | —— | **仓库中未见** | —— |
| **G4-R1/R5/R6** | 交付链（hydration 修复 / 公网 P9 / 公网四角色评审） | 静态站点从本地候选走到公网 | `knowledge-system/capability-map.json:137,143`；`knowledge-system/mkd-distill-g4r6-public-review-packet.json:4` |
| **G5 / G5-R2** | 延迟稳定性 / 静态 closeout | 观察窗与收口 | `docs/architecture/g6-a6-…md:35,60` |
| **G6-A1 … A11** | Replay-first 单 E2 Agent 垂直切片 → 公网静态接受 | 见 B.2 | `docs/architecture/g6-a*.md` |
| **G7-A1 … A5** | Provider 阴影 → 认证内部 Agent → 公网 live 候选 | 见 B.3 | `docs/architecture/g6-a11-…md:85-89` |
| **G8** | live Agent 灰度 | **仅设计草案，未授权** | `knowledge-system/capability-map.json:224,229` |

**谁能过门（关键）**：门不由工具过，门由**具名角色**过。

- `product-decisions.json:81`（决策 AA1）：`"Owner 做产品决策；Codex 实施；专业角色在门禁复核"`。
- `product-decisions.json:63`（决策 I2）：`"四角色独立验收"`。
- `docs/architecture/g6-a3-independent-acceptance-design.md:21`：「准备器只生成待签记录、证据包和 preparation receipt；**独立的验收器只消费人工提供的结构化评审结果。准备器没有生成 accepted/current 记录的路径。**」
- `adrs/README.md:20`：「任何提高权限、改变证据语言、开放公网输入或改变权威存储的 ADR 必须由 Owner 重新确认。」
- `adrs/README.md:21`：「ADR 接受仅代表设计决策，不代表实现、验收或生产状态。」

### B.2 A 系列产物（G6 内部子门）

从 `docs/architecture/g6-a*.md` 的文件标题与内容逐项确认：

| 门 | 产物/决策内容 | 出处 |
|---|---|---|
| **A1** | Replay-first 单 E2 Agent 垂直切片：本地确定性 runtime、20 条门禁案例、Agent Lab 冻结设计 | `g6-a1-replay-first-e2-agent-design.md:7` |
| **A2 / A2-R1** | 本地产品与证据评审（产出 3 个 P1 + 2 个 P2 findings，判定 `blocked-revision-required`）/ 五项 findings 的最小修复与 source-locked 复审边界 | `g6-a2-…md:62-63`；`g6-a2-r1-remediation-design.md:4` |
| **A3 / A3-R1** | 独立产品与证据验收（四角色 assigned/accepted 分离的 fail-closed 方案）/ 追加式 Schema Reference 修正 | `g6-a3-independent-acceptance-design.md:14`；`g6-a3-r1-schema-ref-correction-design.md:4` |
| **A4** | corrected-current 绑定的本地静态候选 | `g6-a4-local-static-candidate-design.md:4` |
| **A5 / A5-R1** | 精确静态候选四角色评审准备 / 评审决定物化（追加式 current records + accepted packet + 独立 receipt） | `g6-a5-…md:4`；`g6-a5-r1-…md:21` |
| **A6 / A6-R1** | 438e 部署准备与只读基线（一次严格 SSH 只读采集）/ 只读 reconciliation | `g6-a6-deployment-preparation-readonly-baseline-design.md:12` |
| **A7 / R1 / R2** | 隔离候选运行态部署（状态 `blocked-and-rolled-back`）/ Package Manifest 校验修正 / 网络路由归属 | `g6-a7-isolated-candidate-runtime-design.md:3` |
| **A8 / A8-R1** | Exact 88d4 → 438e 边缘切换 / 有界旧站探针边缘切换（已完成） | `g6-a8-…md:4`；`g6-a8-r1-…md:3` |
| **A9** | 公网 P9 与短延迟稳定性 | `g6-a9-public-p9-delayed-stability-design.md:4` |
| **A10 / A10-R1** | 精确公网证据的四角色独立评审准备 / 系统记账时间的四角色接受物化 | `g6-a10-…md:4`；`g6-a10-r1-…md:2` |
| **A11** | 公网静态 closeout + G7 路线决策（Option A/B） | `g6-a11-public-static-closeout-and-g7-roadmap.md:13-15` |

### B.3 G7-A1…A5（下一阶段门禁）

`docs/architecture/g6-a11-…md:83-89` 给出完整表格，每个门都有「Exit criteria」与「Live authority」两列：**G7-A1**（本地 provider-readiness 合同：typed adapter、脱敏、白名单、token/成本预算、超时重试分类、kill switch、provider receipt schema、5 个 canary 输入）——Live authority 为 `None; provider calls remain 0`；**G7-A2**（有界 shadow canary：至多 5 次调用、固定预算、合成/脱敏输入、无副作用工具、不可变回执）——仅显式有界 provider 调用；**G7-A3**（Replay vs provider 评测）——仅本地评测；**G7-A4**（认证内部 Agent 候选）——另行隔离运行时授权；**G7-A5**（公网产品候选）——另行公开发布授权。

`g7-a1-provider-readiness-design.md:20-24` 进一步说明 A1 的"零调用"不是修辞，而是实现约束：`maxCalls=0`、`maxCostUsdMicros=0`、`maxRetries=0`，且「The implementation imports no HTTP/HTTPS/net/TLS modules and does not call `fetch` or a provider SDK.」

### B.4 一次完整 run 的产物清单（RUN-AMZ-M1B-001 实证）

目录：`docs/public/reference/m1b/`

**run 级（`runs/RUN-AMZ-M1B-001/`，5 份）**：

| 文件 | 作用 | 关键内容 |
|---|---|---|
| `report.md` | 人读结论页 | 状态 `draft-for-review`、等级 `LO-S-synthetic`、外部调用 0、副作用 0、快照 ID/版本；结论/建议/停止条件三段 |
| `action-package.json` | 决策行动包 | `facts`/`inferences`/`unknowns`/`options`/`recommendation`/`calculations`/`risks`/`stopConditions`/`approvalRequirements`/`evidenceRefs`/`status` |
| `trace.json` | 执行轨迹 | `mode:"replay"`、`externalCalls:0`、`sideEffects:0`、5 个事件（source→agent×3→receipt），每事件含 `inputRefs`/`outputRefs` |
| `receipt.json` | 回执 | run/taskPackage/skill/model/prompt/8 个 tools 的 **ID+version**、`artifactHashes`（3 个 sha256）、`issuedAt` |
| `replay-bundle.json` | 复放包 | 打包上述全部 + `toolRegistry`（8 工具全部 `sideEffect:false`）+ `state` |

**包级（`m1b/` 根，7 份）**：`snapshot.json`（143 个对象 ID、7 条关系 ID、`manifestHash`、`"immutable": true`）；`extraction-receipt.json`（6 格式/6 源/88 结构元素，每源独立 sha256）；`knowledge-map.json`（7 节点 + 7 条类型化边）；`evaluation-report.json`（20/20 = 8 正例 + 8 负例 + 4 对抗，每例 5 项检查）；`canonical-dry-run.json`（`apply:false`、`canonicalWrites:0`、`decision:"pending-review"`）；`review-packet.json`（6 候选 + 3 证据 + 3 条 `unresolved`）；`m1-b-execution-receipt.json`（7 个 artifact hash、四类计数全 0、`deployed/gitCommitted/gitPushed` 全 false）。

由此可提炼**一次 run 的最小产物集**：报告 + 行动包 + 轨迹 + 回执 + 复放包（run 级），外加快照、抽取回执、评测报告、评审包、构建总回执（包级）。

---

## C. 可复现与验收

### C.1 replay-first 的具体含义

`docs/architecture/adrs/003-replay-first-e2.md`：

> ## 决策
> **默认产品证据是不可变 Replay。** 首版只使用单任务 E2 Agent 和确定性只读/计算工具；live 只作为同一 TaskPackage 的限频对比，**不覆盖 Replay 基线**。
>
> ## 后果
> - 无 provider key 也必须能复放固定 bundle。
> - 模型、prompt、tool、snapshot 和 eval 版本写入 Receipt。
> - **没有任何写工具、消息工具或 canonical promotion 工具。**
> - 多 Agent 不进入 V1。

三层含义：

1. **默认证据是回放，不是实时运行**：产品上对外展示的是构建产物回放，`agent-lab-bundle.json` 的 `"mode":"replay"`、`"dataClass":"synthetic"` 即此。
2. **回放必须能在无凭据环境跑通**：所以 `receipt.json` 里 `model.id` 是 `deterministic-rule-engine`、`prompt.id` 是 `no-provider-structured-replay`。
3. **确定性是可验证属性**：`g6-a1-…md:121`「执行 G6 Runner 两次并比较 canonical JSON 字节」；`g6-a1-…md:140`「同一 case 两次运行的 canonical JSON 相同」。

### C.2 replay bundle 里装什么

`replay-bundle.json` 顶层 6 个键，逐项对应：

```json
{ "input": {...}, "actionPackage": {...}, "trace": {...}, "receipt": {...},
  "toolRegistry": [...], "state": "completed" }
```

- `input`：`{caseId:"CASE-AMZ-ACOS-SYNTHETIC", comparisonWindow:"7d-vs-7d"}` —— 输入被压缩为**白名单枚举参数**，无自由文本。
- `actionPackage`：完整决策包（含 facts/inferences/unknowns 分栏）。
- `trace`：逐事件 `inputRefs`/`outputRefs`，闭合可核。
- `receipt`：版本三元组（snapshot/taskPackage/skill/model/prompt/tools）+ 三个 artifact sha256。
- `toolRegistry`：8 个工具及其 `mode` 与 `sideEffect:false`。
- `state`：终态。

另有一份面向 UI 的回放包 `docs/public/reference/g6/agent-lab-bundle.json`：`bundleId`/`schemaVersion`/`generatedAt`/`evidenceGrade`/`dataClass`/`mode`/`capabilityManifest`/`evaluation`/`cases`/`boundaries`。

### C.3 谁能重放

**仓库中未见**关于重放权限的明确鉴权矩阵。可确定的事实是：

- 侧信道要求：`adrs/003` 的「无 provider key 也必须能复放固定 bundle」——即重放**不需要凭据**。
- 公开边界：`public-projection-manifest.json` 定义公开投影包含哪些文件，`reference/receipts/**`、`reference/{build,evidence,attestations,reviews,runtime}/**`、`reference/schemas/g7/**`、`deploy/**` 等被明确排除；`g6-a1-…md:126`「导出中不得包含密钥、主机信息、真实账户数据或任意用户输入。」
- 公网侧：`g6-a11-…md:51-52` 明确禁止声称「A production/live Agent is running on the public site.」

### C.4 独立验收（independent acceptance）怎么定义

`docs/architecture/g6-a3-independent-acceptance-design.md` 给出完整定义。

**定义**（第 14-23 行）：采用"四角色 assigned/accepted 分离"的 fail-closed 方案，四个角色各有不可替代的审查面：

- `pray / ROLE-PRODUCT-EXPERIENCE`：产品叙事、交互、响应式与无障碍；
- `ll / ROLE-EVIDENCE-INTEGRITY`：finding 闭环、fixture/golden、lineage 与证据等级；
- `zy / ROLE-SCHEMA-CAPABILITY`：schema 反例、终态相关性、工具回执与 import graph 能力审计；
- `ly / ROLE-SECURITY-GOVERNANCE`：审批/拒绝、零副作用、网络披露与发布边界。

**两条被明确拒绝的替代方案**（第 23 行）：

> 未采用单评审人方案，因为它不能覆盖既定的多角色独立性要求；未采用模型自动代签，因为本门禁禁止 provider，且**模型评审不能替代人工独立性声明**。

**状态机**（第 40-45 行）：

```text
prepared / assigned
  ├─ 任一缺签、检查失败、independence=false 或 decision!=accepted → blocked/rejected
  └─ 四人、三项检查全部 passed、findings 已显式记录、independence=true、decision=accepted
       → accepted-local-product-and-evidence
```

**人工输入合同**（第 51-58 行）：每名评审必须提供 `roleId`+`assignee`、三项检查逐项 `passed`/`failed`、`findings` 数组（**无问题也必须显式为空数组**）、`independenceAttestation`、`decision`、UTC 秒级 `signedAt`。

**最锋利的一条**（第 60 行）：

> 验收器**不会把"全部通过"自动扩写成缺失的签名事实**；只有用户明确提供完整字段后才能物化 accepted 记录。

一个反面实证：`g6-a2-local-product-evidence-review.md:12` 记录了一次"同任务内交叉审计"被拒绝承认为独立验收：

> 这是同一 Codex 任务中的 source-locked 新鲜交叉审计，不是组织意义上的独立人工签名；`independenceAttestation=false`。因此，即使没有产品 findings，**也不能自动伪造人类独立接受**。

### C.5 receipt 里记什么

三层回执，字段逐级加严：

**（1）运行回执**（`receipt.json`，12 字段）：runId、mode、evidenceGrade、snapshot{id,version}、taskPackage{id,version}、skill{id,version}、model{id,version}、prompt{id,version}、tools[{id,version}]×8、traceRef、evaluationRefs、artifactHashes{actionPackage,trace,input}、externalCalls、sideEffects、issuedAt。

**（2）评审记录**（`knowledge-system/schemas/g6-a3-review-record.schema.json`，15 个必填字段）：`schemaVersion`、`reviewId`、`gateId`、`roleId`、`assignee`、`candidateId`、`candidateDigest`、`assignedAt`、`independenceAttestation`、`state`、`decision`、`signedAt`、`evidenceRefs`、`reviewItems`、`findings`。其中 `reviewItems` 强制**恰好 3 项**（`minItems:3, maxItems:3`），每项 `{check, status: pending|passed|failed, note}`；`candidateDigest` 必须 `^sha256:[a-f0-9]{64}$`。

**（3）验收契约回执**（`acceptance.schema.json:113-136`）的 `acceptanceReceiptMetadata` 必填 7 字段：`acceptanceId`、`purpose`（枚举 `owner-acceptance`/`dataset-authorization`/`threshold-approval`/`final-acceptance`）、`subjectId`、`approverRoleId`、`issuedAt`、`decision`（**const "accepted"**）、`artifactSha256`。

### C.6 "系统记录的验收" vs "人工声称的验收"如何区分

这是本仓库最精细的一处设计。做法是**把时间戳的来源变成 schema 里的常量字段**。

`docs/architecture/g6-a10-r1-system-recorded-review-acceptance-design.md:15-25`：

```
- mode: `system-recorded-on-user-confirmation`
- recordedAt: `2026-08-12T05:32:43Z`
- local display: `2026-08-12 13:32:43 +08:00`
- meaning: time when the system processed the user's complete four-reviewer confirmation
- non-claim: this is not represented as four separately handwritten timestamps
```

对应的 schema 里，`timestampProvenance` 是**必填对象**，并且 `humanProvidedSignedAt` 被写死为 `const null`（`schemas/g6-a10-r1-accepted-review-record.schema.json:22-32`）：

```json
"timestampProvenance": {
  "required": ["mode","recordedAt","humanProvidedSignedAt","meaning"],
  "properties": {
    "mode": { "const": "system-recorded-on-user-confirmation" },
    "humanProvidedSignedAt": { "const": null },
    "meaning": { "const": "system processing time for the user's complete four-reviewer confirmation; not four separately handwritten timestamps" }
  }
}
```

同一 schema 还把 `roleId → assignee` 用 `allOf`+`if/then` 锁死为 4 组常量映射（`pray`/`ll`/`zy`/`ly`），并强制 `state:"completed"`、`decision:"accepted"`、`independenceAttestation:true`、`reviewItems[].status:"passed"`、`findings` 为**空数组**（`maxItems:0`）。

另一处证据是**时序校验**（`g6-a5-r1-review-decision-materialization-design.md:36-40`）：

> - `signedAt` 不得早于 packet `preparedAt` 或 record `assignedAt`；
> - submission `submittedAt` 不得早于任一 `signedAt`；
> - 首次用户输入 `2026-08-11T11:31:51Z` 早于冻结的 `preparedAt=2026-08-11T14:42:30Z`，执行器因此在**零输出状态失败关闭**。

以及身份绑定：`capability-map.json:193` 明确把「系统记账时间不是 reviewer 手写签名时间，不得伪造时间来源」列为一条 forbidden claim。

**归纳**：区分手段有三 —— ①独立的 provenance 字段（mode + 是否手写）；②时序单调性校验（签署 ≥ 准备、提交 ≥ 签署）；③对象身份三重锁定（release + site digest + archive SHA 必须同时匹配，见 `g6-a5-r1-…md:11-15`）。

---

## D. 存储与版本

### D.1 git-native sqlite 具体怎么做

`docs/architecture/adrs/002-git-native-sqlite.md`：

> ## 决策
> JSON/YAML/Markdown、稳定 ID、typed relations 和 immutable snapshot 是**权威合同**。SQLite FTS5、edge table 和预计算向量是**可重建运行投影，不是 canonical source**。
>
> ## 理由
> V1 的主要风险是语义、来源、版本与审批，而不是图查询吞吐。**Git diff 与 snapshot hash 更适合审查和复放**；SQLite 足以支持有界闭包。
>
> ## 重新评估触发器
> 只有出现经测量的对象规模、并发、复杂图算法或恢复时间瓶颈，才评估专用图/向量存储。

具体落地：

- 权威对象以 JSON/YAML/Markdown 落盘（`claims.yml`、`concepts.yml`、`snapshot.json`…）。
- 派生索引为 SQLite FTS5 + 边表（`m1-b-execution-receipt.json:32` 记录 `sqlite` 产物的 sha256）。
- 不可变由 hash 保证：`snapshot.json:153-156` 有 `"canonicalization":"sorted-object-and-relation-ids-v1"`、`manifestHash`、`"immutable": true`。
- 版本即可审查：`adrs/README.md:18-19`「新决策创建新 ADR，不静默改写已接受 ADR 的结论」；「替代旧决策时填写 `supersedes`，旧 ADR 改为 `superseded` 但保留」。

### D.2 为什么不用服务端数据库

ADR-002 的「理由」直接回答：V1 的风险不是吞吐，而是**语义、来源、版本与审批**。四条判据：①**审查需要 diff，而服务端数据库没有 diff**——Git diff + snapshot hash 才能让审查者看到"这次到底改了什么"；②**复放需要确定性**——`canonicalization: sorted-object-and-relation-ids-v1` 这类规范化只有在文件级可字节比较时才有意义；③**规模不构成压力**——真实计量是 26 页 / 352 代码块（`knowledge-system-audit.md:31-39`），Reference 侧 `snapshot.json` 只有 143 个对象，SQLite 的"有界闭包"完全够用；④**延迟决策的纪律**——ADR-002 给出明确的重新评估触发条件（对象规模、并发、复杂图算法、恢复时间四类瓶颈），而不是"以后再优化"。

### D.3 public-input-contract 解决什么问题

`docs/architecture/adrs/004-public-input-contract.md`：

> ## 决策
> 公网只接受**白名单 case、task、枚举与有界数值参数**。禁止文件、自由文本、任意 URL 和动态工具定义。
> Observation 只接受问题类型、case/run/artifact 引用和严重度。文字说明转到本地 Candidate 流程或代码仓库 Issue。
>
> ## 后果
> - API Schema 可以严格拒绝未知字段。
> - **日志不需要保存 prompt 或文件正文。**
> - 本地 Runner 可有不同输入合同，但必须保留 **SSRF、大小、格式和许可门禁**。

它解决的是：**把攻击面和数据留存面同时压到最小**。输入是枚举 → 无 SSRF、无提示注入、无文件解析漏洞；不含正文 → 日志无隐私负债。实证见 `replay-bundle.json` 的 `input` 只有 `caseId` + `comparisonWindow` 两个字段。

### D.4 license-gate 解决什么问题

`docs/architecture/adrs/005-license-gate.md`（状态 `proposed-blocking`，blocker `LICENSE_DECISION_PENDING`）：

> ## 决策
> 在 Owner 确认项目许可证前，**Schema、fixture 和未来 Runner 只允许本地开发与审查，禁止 package/container 公开发布。**
>
> ## 候选
> 1. Apache-2.0：推荐，包含明确专利授权条款。
> 2. MIT：更短、更宽松，但不包含同等明确的专利条款。
>
> ## 关闭条件
> Owner 选择许可证；安全/发布角色复核第三方依赖和 corpus 再分发边界；随后才创建 LICENSE 与包元数据。

它解决的是：**"能不能合法分发"是一个必须先于"能不能发布"回答的问题**。注意它采用 `proposed-blocking` 状态——即一条**未决**的 ADR 也具备阻断力，而不是等待决定后再阻断。这与 `product-decisions.json:43-51` 的 `forbiddenWithoutNewAuthorization` 清单（`provider-call`/`production-deploy`/`canonical-knowledge-write`/`external-send`/`git-commit`/`git-push`/`package-publication`）构成同一种"默认拒绝"结构。

---

## E. 可迁移的硬约束

### E.1 必须照搬、不能妥协的规则（每条一句话 + 出处）

1. **工具只能补证据，不能过门**：门禁脚本只做校验与失败关闭，accepted 记录只能由人工输入物化，准备器没有生成 accepted 的代码路径。→ `docs/architecture/g6-a3-independent-acceptance-design.md:21`
2. **禁止模型代签**：模型评审不能替代人工独立性声明。→ `docs/architecture/g6-a3-independent-acceptance-design.md:23`
3. **没有独立签名就不能伪造接受**：即使零 findings，`independenceAttestation=false` 也不得生成 accepted。→ `docs/architecture/g6-a2-local-product-evidence-review.md:12`
4. **"全部通过"不等于"已签名"**：验收器不得把汇总结果自动扩写成缺失的签名事实。→ `g6-a3-independent-acceptance-design.md:60`
5. **角色映射 ≠ 责任接受**：三层状态 `role-mapped → assigned → accepted` 必须分开记录，只有具名自然人可推进最后一层。→ `knowledge-system/roles.json:5`
6. **两套账本不得互推**：任一产品线的通过不得抬升另一产品线的成熟度。→ `docs/architecture/adrs/001-dual-product-ledgers.md`；`product-lines.json:5`
7. **页面/能力不得自行升级状态**：申报值与机器计算值不一致即失败关闭。→ `scripts/acceptance-registry.mjs:535-543`
8. **每个对外声明必须同时写"不得声称什么"**：`forbiddenClaims` 必填且至少 1 条。→ `knowledge-system/schemas/capability-map.schema.json`
9. **每条高风险断言必须绑定四个独立角色**：内容维护、证据复核、测试维护、最终批准缺一不可。→ `knowledge-system/schemas/claim.schema.json:218-228`
10. **每个断言必须写"不能证明什么"**：`applicability` 与 `limitations` 均必填。→ `knowledge-system/schemas/claim.schema.json:282-283`
11. **状态与证据等级必须机器映射**：`verification` → `evidenceGrade` 的对应写在代码里，不靠人记。→ `scripts/claim-registry.mjs:16-24`
12. **验收回执只允许 L4**：`kind: acceptance-receipt` 的证据其 `grade` 被 `const` 锁为 `L4-authorized-live`；其余等级携带 receipt 字段直接失败。→ `knowledge-system/schemas/claim.schema.json:99-111`
13. **被证据门禁否决的数字不得作为 FACT 陈述**：`blocked` 计算不得继续输出精确值（这是 G6-A2 第一个 P1 finding 的成因）。→ `docs/architecture/g6-a2-local-product-evidence-review.md:25-29`
14. **输入不足时只输出公式/区间/未知**：不允许伪造精确数值。→ `docs/architecture/m1-a-product-contract.md:83`
15. **默认不可写**：无写工具、无消息工具、无 canonical promotion 工具；写入演练必须 `apply:false`。→ `docs/architecture/adrs/003-replay-first-e2.md`；`docs/public/reference/m1b/canonical-dry-run.json`
16. **每条能力/发布都必须留下效果账**：`externalCalls`/`sideEffects`/`canonicalWrites`/`providerCalls`/`deployed`/`gitCommitted`/`gitPushed` 逐项记数，全 0 才算合规。→ `docs/public/reference/m1b/m1-b-execution-receipt.json:36-43`
17. **时间戳必须带 provenance、时序必须单调**：手写与系统记账不得混同（schema 用 `const` 锁死）；签署时间不得早于准备时间，提交不得早于签署。→ `knowledge-system/schemas/g6-a10-r1-accepted-review-record.schema.json:22-32`；`g6-a5-r1-review-decision-materialization-design.md:36-40`
18. **历史不可覆盖**：assigned 历史字节不变，新结果以 `wx` 独占创建追加，重复执行必须拒绝覆盖。→ `g6-a5-r1-review-decision-materialization-design.md:21,50`
19. **能力与状态只能由门禁回执支撑**：不得由"页面完整"或"已上线"自动抬升。→ `knowledge-system/capability-map.json:5`
20. **不确定就阻断**：未决 ADR（`proposed-blocking`）即具备阻断力。→ `docs/architecture/adrs/005-license-gate.md:6`
21. **存储权威在文件，索引只是投影**：服务端存储只能在测得瓶颈后才评估。→ `docs/architecture/adrs/002-git-native-sqlite.md:12,18-19`
22. **公网输入只收枚举**：白名单 case/task/枚举/有界数值，禁止文件、自由文本、任意 URL。→ `docs/architecture/adrs/004-public-input-contract.md:12`
23. **公开与内部分离是显式清单**：`inclusionRules`/`exclusionRules` 逐条写理由，含凭据指纹的文件一律 `public projection=false`。→ `knowledge-system/public-projection-manifest.json`
24. **ID 稳定且与标题解耦**：标题、路由、顺序变化不得改 `docId`。→ `knowledge-system/documents.yml:5`

### E.2 依赖其特定业务、我们不该照搬的部分

| 不该照搬的 | 为什么 |
|---|---|
| **四角色具体分工**（产品体验 / 证据完整性 / schema 能力 / 安全治理） | 为"知识到 Agent 平台"设计；Momcozy 需要的是合规法务面、品类知识面、投放/内容面。但"恰好 4 个、互相独立、具名"的形式应保留。→ `g6-a3-independent-acceptance-design.md:16-19` |
| **L0–L6 七层对象链** | 为"多格式资料 → 可执行 Skill"的编译链设计，我们的知识库不需要 Skill/TaskPackage 层。→ `m1-a-schema-catalog.md:15-23` |
| **E0–E4 执行权限分级 + `publicMaximum: E2`** | 面向公网只读演示的产品形态；若 Agent 只在内部用，边界定义完全不同。→ `reference/ontology/permissions.json` |
| **20 条合成 golden case 的亚马逊广告语义** | 完全业务绑定。→ `reference/fixtures/g6/agent-cases-v1.json` |
| **G4/G5 交付链**（Docker/Nginx/腾讯云 edge/certbot/Playwright P9/Lighthouse） | 属于"把静态站部署到公网"的运维方法论。→ `g6-a6-…md`、`g6-a8-…md` |
| **`LO-S-synthetic` 这一级 / `sample-by-review` 的抽样口径** | 前者为合成语料特设；后者是小团队可承受的抽样量（13 概念 / 71 个未迁移线索），规模不同则不同。→ `content-audit.md:106` |
| **26 章文档站的 VitePress / Mermaid / 搜索门禁、`G2.5` 的 10–15 条黄金查询数量** | 前者是"知识产品站点"的工程税，与"需求知识库"目标无关；后者数量级由内容规模决定，应重估。→ `qa-receipt.md:11-17`；`knowledge-system-audit.md:136` |

---

## F. 对 Momcozy 营销内容合规审查 Agent 的启示

> 本节全部为映射推演，**非仓库事实**。

### F.1 可直接映射的结构

| Kb2Agent 对象 | Momcozy 对应物 | 映射理由与需改造处 |
|---|---|---|
| **claim**（断言） | **风险规则** | 最直接的映射。`claimType` 改为风险类型（`platform-policy`/`ad-law`/`brand-voice`/`product-claim-substantiation`）；`risk` 保留 `high`/`critical` 两档（合规领域天然只有高与极高）；`volatility` 尤其关键——平台政策半衰期短，广告法条款长。 |
| **concept**（术语） | **措辞 / 禁用词 / 表达模板** | `definition` + `aliases` 正好承载"同一禁令的多种措辞"；`conflictsWith(not-equivalent)` 可承载"看起来像但不算违规"的边界（如"温和"vs"治疗"）；`usedIn.usageType` 可改造成"该措辞在哪类素材里出现"。 |
| **document** | **规则来源文档**（平台政策页、法规条文、品牌手册、法务备忘） | 四字段身份分离直接可用，尤其 `route` 的"变更必须提供兼容路由"对政策版本迭代非常有用。 |
| **source / evidence / evidenceGrade** | **规则出处与判定依据** | 整个方法论里对合规场景**价值最高**的一件事：把"这条规则从哪来、我们凭什么这么判"变成必填外键。 |
| **role + ownership 四角色** | **合规审查责任链** | 改成：规则维护人 / 法规复核人 / 测试集维护人 / 最终批准人。 |
| **acceptance contract** | **审查质量验收契约** | 固定评测集 + 负例 + 阈值 + 回归基线 + 责任接受 + 最终回执，六项独立计算的机制可原样搬。→ `docs/knowledge/appendix-validation.md:68` |
| **product-claim（含 forbidden）/ capability-map** | **对外服务能力声明 + 授权门** | 直接回答"我们现在敢对外说什么、绝不敢说什么"；`ownerGate` 对应"这项能力由哪个门授权"。 |
| **replay-first + replay bundle** | **审查结果可复现** | 同一份素材 + 同一份规则快照 → 两次运行字节一致。对合规场景这是**可辩护性的基础**。 |
| **public-input-contract / projection-manifest** | **素材输入合同 + 内外知识分离** | 内部工具版改为"只接受素材 ID + 渠道枚举 + 品类枚举"；品牌红线、法务口径、竞品情报不得出现在对外产物里。 |

### F.2 需要重新设计的部分

1. **`claim.verification` 枚举不合适**。Kb2Agent 的取值围绕"公开来源/合成/生产只读/授权在线"展开，合规审查需要的是"来源已核 / 法务已确认 / 案例已验证 / 待外部律师意见"。应重定义，但**保留"状态→等级机器映射"这一机制**。→ `scripts/claim-registry.mjs:16-24`
2. **缺少"规则冲突"的一等公民**。Kb2Agent 有 `conflictsWith`（概念层）与 `relations.json` 的 `contradicts`（对象层），但合规场景的典型难题是**同一素材同时命中两条互斥规则**（例如"必须标注功效"与"禁止功效宣称"），需要一个新的对象或关系类型，并规定冲突时的裁决顺序。
3. **缺少"素材—规则"匹配的中间对象**。Kb2Agent 的 L1 `EvidenceFragment` 近似，但我们需要的是"某条素材片段命中某条规则的某个要件"，需要有 `locator`（素材中的位置）+ `ruleRef` + `matchStrength`。可借鉴其 `sourceLocator` 结构（`reference/schemas/common.schema.json`：`sourceRevisionId`/`structuralElementId`/`locator`/`contentHash`）。
4. **双账本应改为"规则账本 + 审查能力账本"**。ADRs 001 的两个账本（内容 vs 运行时）在合规场景对应为：规则库成熟度（`principle → solution → runnable → acceptance` 可沿用）与审查 Agent 能力成熟度（`draft → replayable → live-candidate → accepted` 可沿用）。**"不得互推"这条必须原样保留。**
5. **复核周期必须是一等字段**。Kb2Agent 的 `volatility` 只是枚举，平台政策实际需要 `reviewDueAt` + `ownerRoleRef`，到期自动降权或阻断。仓库的 `freshness` 结构（`asOf`/`reviewedAt`/`expiresAt`/`state`）可直接采用。→ `reference/schemas/common.schema.json`
6. **需要"零结果也是结论"的表达**。合规审查的输出不只是"违规项"，还包括"没有发现问题"——而后者必须有覆盖度声明，否则就是假安全。Kb2Agent 的 `limitations`/`forbiddenClaims` 机制可承接，但需要为"未命中"设计专门的输出形态。
7. **需要中英双语 ID 与措辞治理**。Momcozy 出海意味着同一禁令在不同市场的措辞不同，`concept.aliases` 只支持同语言别名，可能需要 `locale` 维度。

### F.3 建议的最小落地集（按性价比排序）

**第一批（直接照搬，成本最低、收益最高）**：①`capability-map.json` 的 `forbiddenClaims` 必填机制——先写清楚"我们绝不敢说什么"；②`roles.json` 的 `acceptanceRule` 与三层状态——明确谁签字、签什么字、签完才叫接受；③`product-claims.json` 的 `supported`/`forbidden`/`maxEvidenceGrade` 三元组——每一句对外承诺都绑定最高证据等级；④`claims.yml` + `claim.schema.json` 的 claim 对象骨架（`applicability`/`limitations`/`nextAction` 必填）；⑤`public-input-contract` 的枚举输入纪律。

**第二批（需要一个门禁脚本才能生效）**：⑥`acceptance.yml` 的六条件验收契约 + 机器计算状态（**申报值 ≠ 计算值即失败**）；⑦`verification → evidenceGrade` 的代码级映射表；⑧`replay bundle` + 双次运行字节一致校验。

**第三批（规模化后再上）**：⑨`concepts.yml` 的措辞图谱；⑩`documents.yml` 的四字段身份与兼容路由；⑪`public-projection-manifest` 的内外分离清单。

**一句话总纲**（提炼自 `docs/architecture/adrs/001-dual-product-ledgers.md` 与 `knowledge-system/capability-map.json:5`）：

> **把"我们凭什么这么说"变成必填字段，把"我们不能说什么"变成必填字段，把"谁签字才算数"变成必填字段——三者齐备之前，任何状态都不准自动上升。**
