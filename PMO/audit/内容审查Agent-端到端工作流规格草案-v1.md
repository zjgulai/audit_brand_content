# 内容审查 Agent · 端到端工作流规格草案 v1.2.1

> 状态:**DRAFT(草案)**。本文**不裁定任何未决项**,只把盘上已有的规格按端到端顺序串起来,
> 并逐段登记 owner / 契约 / 状态机 / 失败与未测口径 / UI 触点 / API / 验收与反向对照。
> 上游事实来源(只读):
> - `Playbook/内容审查Agent-产品Playbook-v1.1.md`(产品契约)
> - `Playbook/技术解决方案-v1.md`(27 模块、判据归属、S/P/G 门)
> - `PMO/audit/内容审查Agent-UIUX前后端规格草案-v1.md`(角色、页面、API、G-1、测试)
> - `PRD/内容审查Agent-PRD-优化版-v2.0.md`(分类、分层审查、知识库、人工复核)
> - `PMO/audit/验收表-v3-覆盖全部判据-20261017.md`(验收口径)
> - `PMO/audit/待确认-技术栈与工程选型-v1.md`(未决技术项)
>
> **本文不是实现计划,也不是验收表**:方案整体仍是 DRAFT·NO-GO(`技术解决方案-v1.md` §8)。
> 凡本文写「推荐」的,均标注为**建议**,不改变任何已冻结文档。
>
> **v1.2 修订(2026-10-18,只改本文件)**:① 纠正 S7/S8 语义(初次 output 在人工前;人工动作只新建,
> 旧 IR/report 不可改,不是回边),并拆 S8a/S8b;② 明确 S0–S9 十阶段 + S10 横切,补五步↔十阶段映射;
> ③ 增 27 模块→阶段/owner/UI/API/验收组矩阵;④ `/release` 统一改为 `/unclaim`,引用 UIUX 章节;
> ⑤ 对齐签名绑定全字段、五类失效、autosave、JCS、session/step-up、ACL、appeal/takedown/grant;
> ⑥ 补 ContentUnit/ReviewIR/Finding/decision schema 指针,`fetch_error` id 标 S-3 open;
> ⑦ 每阶段补幂等/未测/失败/审计与验收可执行性标注;⑧ 删除已解决的计数漂移段落;
> ⑨ Compose/OCR/ASR/WCAG/证据只引用;⑩ 引用改为「章节 + 短 hash」,变动源标「待最终冻结」。

---

## 0. 端到端总览

### 0.1 五步流水线与模块映射

Playbook §2 定死五步、每步恰好一次、无回边(`P@ff51fc87 §2`)。技术方案把它展开为模块链
(`T@28498c99 头部状态4-69`):

```
输入四维 ──> submission_router ──> job_dispatcher ──> orchestrator
                                                        ├─① normalizer
                                                        ├─② judge: rule_judge / semantic_judge / evidence_sync
                                                        ├─③ dispose: decision_table / disposition_router
                                                        ├─④ output: report_renderer / report_store / send_gateway
                                                        └─⑤ evaluate: metrics_read_model
```

### 0.2 阶段编号(本文用)

| 阶段 | 名称 | 主 owner | 同步/异步 |
|---|---|---|---|
| S0 | 输入采集与受理 | `submission_router`(+`feishu_io`, ingress) | 入口同步校验;`Attempt` 同步写 |
| S1 | 任务分派与执行 | `job_dispatcher` | 异步(每 case 串行 job,spawn worker) |
| S2 | 归一化 | `normalizer`(+`media_pipeline`) | worker 内同步 |
| S3 | 判定 | `rule_judge` / `semantic_judge` / `evidence_sync` / `rule_class_registry` | worker 内同步(可含外部 KB/模型调用) |
| S4 | Finding 落盘 | `finding_store`(+`evidence_sync` enrich) | worker 内同步(append-only) |
| S5 | 覆盖证明合成 | `coverage_composer` | worker 内同步 |
| S6 | 唯一判定与处置路由 | `decision_table` → `disposition_router` → `case_watch` | worker 内同步;`case_watch` 定时异步 |
| S7 | 人工复核 / 申诉 / 签发 / 失效重审 | `reviews_ledger` / `release_gate` / `case_watch` / scheduler | 人驱动 + 事件驱动(异步) |
| S8 | 产物输出 | orchestrator 组装 `ReviewIR`;`report_renderer` / `report_store` / `send_gateway` | 同步渲染 + 异步发送(outbox) |
| S9 | 指标与回流 | `metrics_read_model` / `reviews_ledger` / `regression_gate` | 只读聚合 + CI 门禁 |
| S10 | 横切:失败 / 未测 / 幂等 / 审计 | 各阶段 owner + `artifact_store` | — |

### 0.3 第一阶段硬边界(来自 Playbook,不是本文新增)

| 约束 | 出处 |
|---|---|
| 无回边、无提前停;每条内容跑完全部控制点 | `P@ff51fc87 §2`, `P@ff51fc87 §3.3.7` |
| NAS / 上传文件两条通道标 `unsupported`,不许从取值域删除 | `P@ff51fc87 §3.1` |
| 文档形态仅飞书文档;`.docx/.pdf` 直传 unsupported | `P@ff51fc87 §3.1`, `P@ff51fc87 §3.1` |
| 五标签全部停「待放行」,机器不给放行 | `P@ff51fc87 §4.2`, `P@ff51fc87 §4.3` |
| 空族（以 `control-points-v1.json` 的 `empty_families` 为准，当前四族：场景/权利/渠道/品牌）无控制点,coverage 恒 partial,阶段一 PASS 出不来 | `P@ff51fc87 §3.3.8.0` |

### 0.4 五步 ↔ 十阶段映射

Playbook 的**五步**是产品流水线;本文的 **S0–S9** 是工程阶段(含前置与人工段),**S10 是横切**。
二者不是两套流程,映射如下:

| Playbook 五步 | 本文阶段 | 说明 |
|---|---|---|
| (前置) | **S0 受理、S1 分派** | 不在五步内;入口校验与 worker spawn |
| ① 归一化(normalize) | **S2** | normalizer 产 ContentUnit v1 |
| ② 判定(judge) | **S3 判定 + S4 Finding 落盘** | Draft→Validated,append-only |
| ③ 处置(dispose) | **S5 覆盖证明 + S6 唯一判定/路由** | decision_table 是唯一状态来源 |
| ④ 输出(output) | **S8a 初次输出** | worker 产出 IR/report/message/card |
| (人工段) | **S7 人工动作** | 复核/申诉/签发/失效;**不是五步中的一步** |
| (人工触发的新运行) | **S7 → S1' → S2'…S8b** | 新 run/new IR/new report;旧记录不可改 |
| ⑤ 评估(evaluate) | **S9** | 只读指标与回流 |
| (横切) | **S10** | 失败/未测/幂等/审计,贯穿全部阶段 |

> **关键语义**:S7 不是回边。人工动作(确认/驳回/申诉/签发/撤回/失效重审)**只能创建新记录或新 run**,
> 不能改写既有 IR/report/finding;新 run 有自己的 `run_id` 与 `ReviewIR` 版本。旧版本永久保留。

### 0.5 27 模块 → 阶段 / owner / UI / API / 验收组

> 模块定义以 `技术解决方案-v1.md` §2(27 模块)为准;本表只做**工作流定位**,不复制模块职责。

| # | 模块 | 阶段 | owner 归属 | UI 触点 | API(UIUX@6252cdee §8.7) | 验收组 |
|---:|---|---|---|---|---|---|
| 1 | submission_router | S0 | 后端 | 提交入口 | POST /submissions | AU/SD、L1-0b/c |
| 2 | normalizer | S2 | 后端 | 案件详情(解析态) | GET /cases/{id} | L1-1…L1-4b |
| 3 | orchestrator | S1-S9 | 后端 | 无 | — | L2-7、V5、L6-6 |
| 4 | job_dispatcher | S1 | 后端 | 案件详情(job 态) | GET /cases/{id} | JQ-1…JQ-7 |
| 5 | skill_registry | S3 | 后端 | 无 | — | SK-1…SK-3 |
| 6 | rule_judge | S3 | 后端 | 无 | — | L2-4 |
| 7 | semantic_judge | S3 | 后端 | 无 | — | L2-9、V3、C2/C4 |
| 8 | rule_class_registry | S3 | 后端 | 规则只读页(只读) | GET /rules | C3、M2/M3 |
| 9 | evidence_sync | S3 | 后端 | finding 依据 | GET /cases/{id} | L2-8、L3-1 |
| 10 | coverage_composer | S5 | 后端 | 覆盖证明 | GET /cases/{id} | L2-3 |
| 11 | decision_table | S6 | 后端 | 案件详情(标签/义务) | GET /cases/{id} | L2-1、L2-6a/b、L4-9、I1–I7 |
| 12 | finding_store | S4 | 后端 | 复核详情 | GET /cases/{id}、POST /cases/{id}/actions | L2-5、M1、ID-1…ID-4 |
| 13 | contract_validator | 横切(S10) | 后端/CI | 无 | — | L2-1a/b/d、L2-4、L3-4 |
| 14 | control_point_registry | S3/S6 | 后端 | 控制点只读 | GET /control-points | L3-1、L6-1…L6-4、C1 |
| 15 | disposition_router | S6 | 后端 | 队列/案件 | GET /queue | L3-3、L3-5 |
| 16 | case_watch | S6/S7 | 后端定时 | 案件时限/升级 | GET /cases/{id} | L3-2 |
| 17 | media_pipeline | S2 | 后端 | 覆盖证明(媒体) | GET /cases/{id} | V1、LOC-1…LOC-4 |
| 18 | report_renderer | S8a/S8b | 后端 | 报告详情 | GET /reports/{id} | L4-1/3/5/7/8、F1/F2、R1、V2/V4、L1-8、L6-5 |
| 19 | report_store | S8a/S8b | 后端 | 报告索引/详情 | GET /reports、GET /reports/{id} | L4-2、R2/R3 |
| 20 | send_gateway | S8a/S8b | 后端 | 群消息/卡片 | —(内部) | L4-4、L4-6 |
| 21 | metrics_read_model | S9 | 后端只读 | 无独立 dashboard | GET /metrics | L1-7、L5-1/2/5 |
| 22 | reviews_ledger | S7/S9 | 后端 | 复核台账/抽样 | GET /queue、POST /cases/{id}/actions | L5-3 |
| 23 | regression_gate | S9/CI | 后端 CI | 无 | — | L5-4 |
| 24 | artifact_store | 横切(S10) | 后端 | 无 | — | R2/R3、P-1、IA |
| 25 | feishu_io | S0/S8 | 后端 | 入口/发送 | —(内部) | AU/SD、DG |
| 26 | contract_suite | 横切(S10) | 后端 | 无 | —(OpenAPI 生成) | schema 契约 |
| 27 | release_gate | S7 | 后端 | 签发/撤回/下线 | /release/*、/takedown-tasks/* | RL-1…RL-15、GR/TD/TF |

> `skill_registry` / `contract_validator` / `contract_suite` / `artifact_store` 在 v1.1 的阶段表里没有落点,
> 本表补齐:它们分别是 S3、S10、S10、S10 的**横切/支撑**模块,不占业务阶段但必须有 owner。
> 验收组 ID 见 UIUX Appendix A;本文只引用,不复制定义。

### 0.6 契约 / schema 指针(只引用,不复制字段)

| 对象 | 定义位置 | 说明 |
|---|---|---|
| `ContentUnit v1` | P@ff51fc87 §3.2;T@28498c99 §1bis | normalizer 产;双指纹 + covers/does_not_cover + parse_status |
| `ReviewIR` | P@ff51fc87 §4.3;T@28498c99 §1bis/§1ter | 运行级唯一真相;由 orchestrator 组装、artifact_store 落盘 |
| `Finding` / `ValidatedFinding` | P@ff51fc87 §3.3.4;T@28498c99 §1bis.1 | append-only;Draft 不落盘 |
| `decision_table` 输入/输出 | P@ff51fc87 §3.3.8;T@28498c99 §2 #11 | 15 链 + I1–I7;唯一状态来源 |
| 回执 `Receipt` | P@ff51fc87 §3.3.3;T@28498c99 §1bis.3 | 含 `skipped` 空数组、obligations |
| 签发绑定字段 | UIUX@6252cdee §8.4 / Appendix A SB | 全字段,本文件不复述 |
| API 起止状态/409/幂等 | UIUX@6252cdee Appendix B | 本文件只引用 |

> **`fetch_error` 稳定 id**:仍属 **S-3 open**(`T@28498c99 §8 S-3`);本文不裁定。

### 0.7 与 UIUX v1.3.1 的对齐(只引用)

| 决策 | 对齐方式 |
|---|---|
| 五类失效输入(内容指纹 / rule_snapshot / kb_snapshot / 已用 authority_ref 版本 / 冲突表版本) | 引 UIUX@6252cdee §UJ-4 / Appendix A INV;本文 S7.7 展开五类 |
| 签名绑定全字段 | 引 UIUX@6252cdee §8.4 / SB-1…SB-11;本文 S7.5 只列类别 |
| Draft autosave | 引 UIUX@6252cdee §UJ-2 / Appendix C D-101;本文 S7.2 只写「保存 draft」 |
| JCS 媒体指纹(TS-27) | 引 P@ff51fc87 §4.5.8 + A@432f4a2c #130;本文 S8a.2 只在媒体产物处引用 |
| session / step-up | 引 UIUX@6252cdee §8.3 / §10.2 + P@ff51fc87 §4.5.1(TS-1/11/13) |
| ACL / SoD | 引 UIUX@6252cdee §1.3 / §1.4 |
| appeal / takedown / grant | 引 UIUX@6252cdee §UJ-3/§UJ-5/§1.5 + Appendix A AP/TD/TF/GR |
| Compose / OCR / ASR / WCAG / 证据级别 | 引 UIUX@6252cdee §9/§6.3/§13;本文不复制 UI 细节 |

### 0.8 验收可执行性约定

- 本文各阶段的「验收 / 反向对照」是**设计意图**,不是可执行验收。
- 除非该行明确给出 `test_id + fixture + command`,否则一律视为**待建**;
  不得写成「已验证」「已通过」,也不得据此宣称系统可执行。
- 当前**没有任何一行**同时具备 test_id / fixture / command。

---

## S0 · 输入采集与受理

### S0.1 Owner 与职责

- **唯一入口**:`submission_router`(`T@28498c99 §2 #1`)。四维取值校验、`unsupported` 拒绝、不归一化。
- **入口传输**:`feishu_io`(只读接入与传输原语,`T@28498c99 §2 #25`);ingress 复用 `ws_daemon`(`UIUX@6252cdee §8.2`)。
- **Attempt 唯一写者**:`submission_router`(`T@28498c99 §1bis.2`)。

### S0.2 输入四维契约

| 维度 | 字段 | 取值域 | 第一阶段 |
|---|---|---|---|
| 内容形态 | `content_type` | 文本 / 图片 / 视频 / 文档 / 结构化记录 | 文本、图片、视频、结构化记录 ✅;文档仅飞书文档 ⚠️ |
| 内容阶段 | `content_stage` | `brief` / `final_content` | 两者都收 |
| 入口通道 | `entry_channel` | 群消息 / 飞书文档链接 / 落地页 URL / 多维表批量 / NAS / 上传文件 | 前四 ✅;NAS、上传文件 ⛔ `unsupported` |
| 来源种类 | `source.kind` | 广告记录 / 自由文本 / 落地页 / 结构化 JSON / 图片 / 视频 / 文档 | 除文档外全支持;`source.kind=文档` 语义歧义未见消歧句 |

> 出处:`P@ff51fc87 §3.1`。**`source.kind=文档` 与 `content_type=文档` 的读混风险在技术方案里被登记为残留待裁定**
> (`T@28498c99 §4 残留`),本文不裁定。

### S0.3 输入 / 输出 schema

- 输入:`RawInput`(入口原始载荷 + 四维字段)。
- 输出:
  - 受支持 → 交 `normalizer`,由 `normalizer` 产出 `ContentUnit v1`(`submission_router` 只转交,不产单元);
  - 不支持 → `Attempt{outcome=rejected_unsupported, failure_kind=unsupported, ir_id 不存在}`;
  - 失败 → `Attempt{outcome=failed, failure_kind∈{fetch_error,parse_error,empty,unsupported}}`。

`attempt-v1` 字段与三条恒等式见 `T@28498c99 §1bis.2`。

### S0.4 状态机

```
submitted ──accepted──> (进入 S1)
    ├──rejected_unsupported──> 终态(计入 L1-7/L1-8 计数)
    └──failed(failure_kind)──> 终态(计入 L1-7/L1-8 计数)
```

### S0.5 失败 / 未测 / 幂等 / 审计

| 项 | 口径 | 出处 |
|---|---|---|
| 失败 | `Attempt.failure_kind` 四值;`reason` 不许写「其他/未知错误」 | `T@28498c99 §1bis.2` |
| 未测 | `Attempt` 读不出 → 报告 L1-7 显示「未测」而非 0 | `T@28498c99 §1bis.2` |
| 幂等 | 同一 `submission_id` 可含多次 attempt;`attempt_id` 稳定 | `T@28498c99 §1bis.2` |
| 审计 | `entered_at`、`outcome`、`ir_id|不存在`、`receipt_id|不存在` | `T@28498c99 §1bis.2` |
| 入站去重 | `event_id` 去重 + `events-inbox.jsonl` + cursor(进程不在时事件仍丢,明写) | `UIUX@6252cdee §8.6` |

### S0.6 UI 触点与 API

- API:`POST /api/v1/submissions`(群/表/Web 同路由),`UIUX@6252cdee §8.7`。
- UI:提交入口(群消息、飞书文档链接、多维表批量、Web);NAS/上传文件若出现,必须显示「未支持」而不是静默失败。
- 工作台不展示原始媒体内容以外的敏感信息;读取审计单独记录(`UIUX@6252cdee §8.8`)。

### S0.7 验收与反向对照

| 验收 | 反向对照 |
|---|---|
| 四个维度每个取值单独提交都能产出内容单元(L1-0) | 逐取值断言,不抽样;删掉一个取值 → 必须红 |
| unsupported 取值显式报未支持(L1-0b/L1-0c) | 提交 NAS/上传文件 → 必须报 `unsupported`,不许静默跳过;`Attempt` 中必须出现对应行 |
| 三 outcome 之和 == 入口提交总数(AT-1) | 丢掉一条 unsupported → 必须红(`T@28498c99 §1bis.3`) |
| `rejected_unsupported` 无 `ir_id`(AT-2) | 填了 → 必须红 |

---

## S1 · 任务分派与执行

### S1.1 Owner

`job_dispatcher`(`T@28498c99 §2 #4`):唯一进程调度与 `run_record` 作者。

### S1.2 输入 / 输出

- 输入:已受理的 submission(含 `content_unit` 待产)。
- 输出:`run_record{run_id, job_id, submission_id, attempt, worker_pid, started_at, ended_at, exit_code, signal, outcome, stdout_sha256, stderr_sha256, receipt_id|null, manifest_ref|null}`。
- 校验:worker stdout 必须是**恰好一个**合法 `ReviewOutput` 且 `run_id` 匹配,才触发 `artifact_store.commit`。

### S1.3 同步 / 异步

- 每 case 唯一 active review job,串行不并行(`UIUX@6252cdee §8.6`)。
- 每次 spawn 一个一次性 worker 子进程(架构,`T@28498c99 §1`)。

### S1.4 状态机

```
queued ──spawn──> running ──exit──> succeeded | failed | timeout
   ▲                                  │
   └──── successor(新变化)────────────┘
```

- queued job 可合并 `change_set`;running job 快照不可变;新变化建 successor 等待当前结束(`UIUX@6252cdee §8.6`)。
- 入队幂等键:`invalidated_event_id` 或 `case_id + signature_id + change_set_hash`(`UIUX@6252cdee §8.6`)。

### S1.5 失败 / 未测 / 幂等 / 审计

| 项 | 口径 | 出处 |
|---|---|---|
| 失败 | worker_crash / timeout / bad_output 只落 `run_record`,不写回执 `run_state=ERROR` | `T@28498c99 §2 #4` |
| 未测 | `run_record` 读不出 → 该次运行计「未测」,不得当 0 | 沿用 L1-7 口径 |
| 幂等 | job 入队幂等键(见上) | `UIUX@6252cdee §8.6` |
| 审计 | `run_id` / `exit_code` / `signal` / stdout+stderr sha256 | `T@28498c99 §2 #4` |
| 第一阶段 | **不做自动重试、不做 TTL 回收重跑** | `T@28498c99 §2 #4` |

### S1.6 UI 触点与 API

- API:案件列表/详情 `GET /api/v1/cases`、`GET /api/v1/cases/{id}`(`UIUX@6252cdee §8.7`)。
- UI:案件详情显示 job 状态、最近一次 run 的 outcome;失败时展示原因类别(不展示 stderr 全文)。

### S1.7 验收与反向对照

| 验收 | 反向对照 |
|---|---|
| 每次 spawn 恰好一条 run_record | 少写一条 → 红 |
| worker stdout 非合法 ReviewOutput 时**不**触发 commit | 喂两个 ReviewOutput / run_id 不匹配 → 必须拒 |
| 每 case 同时只有一个 running job | 并发两个 job → 第二个必须排队或拒 |

---

## S2 · 归一化(ContentUnit)

### S2.1 Owner

`normalizer`(`T@28498c99 §2 #2`):唯一归一化点,只产 `ContentUnit v1`,**不产 `ReviewIR`**。
媒体原料由 `media_pipeline` 提供(`T@28498c99 §2 #17`)。

### S2.2 输入 / 输出契约

`ContentUnit v1` 必含(`P@ff51fc87 §3.2`):

| 项 | 要求 |
|---|---|
| 双指纹 | `raw_sha256` + `text_sha256` |
| 覆盖声明 | `covers` 与 `does_not_cover` **两字段必须存在**,不给默认值 |
| 失败可读 | `parse_status ∈ {ok, partial, failed}`;`failed` 带 `failure_kind ∈ {fetch_error, parse_error, empty, unsupported}` |
| 位置 | 文本 char 区间 / 图片 bbox / 视频 time_start+time_end+frame_no+bbox+frame_thumb(`P@ff51fc87 §3.3.4.4`) |

### S2.3 同步 / 异步

worker 内同步;OCR/ASR/VLM 为同步外部调用(CPU-first,`UIUX@6252cdee §9.2`),超时归 S1 的 timeout。

### S2.4 状态机

```
raw ──parse──> ok | partial | failed(failure_kind)
ok/partial ──> 进入 S3
failed ──> 不进入判定,只落「未审查」(L1-5)
```

### S2.5 失败 / 未测 / 幂等 / 审计

| 项 | 口径 | 出处 |
|---|---|---|
| 失败 | `failed` 单元不得进入判定(L1-5) | `P@ff51fc87 §3.2` |
| 未测 | `empty` 与 `failed` 必须分别计数(L1-7);四种 `failure_kind` 条数必须出现,全 0 也写(L1-8) | `P@ff51fc87 §3.2` |
| 幂等 | 确定性解析:同输入+同解析器版本 → `text_sha256` 相同(L1-4a);OCR/VLM:结论集合差集为空(L1-4b) | `P@ff51fc87 §3.2` |
| 审计 | 解析器版本、模型版本、采样配置随单元记录 | `P@ff51fc87 §3.2` |

### S2.6 UI 触点与 API

- 工作台案件详情展示:parse_status、覆盖声明、失败原因;`partial` 必须标「仅已覆盖部分可判」。
- 无独立「归一化」API;结果经 `GET /cases/{id}` 读取。

### S2.7 验收与反向对照

| 验收 | 反向对照 |
|---|---|
| 每个单元可复算 unit_id(L1-1) | 改一个字节 → id 必须变 |
| covers/does_not_cover 字段存在(L1-2) | 删字段 / 给默认值 → 必须红 |
| failed 不进判定(L1-5) | 构造 failed+finding → 必须 ERROR(I5) |
| partial 永不 PASS(L1-6) | 构造 partial 且其余全干净 → 必须 REVIEW |

---

## S3 · 判定(规则 / 语义 / 依据)

### S3.1 Owner

| 部件 | owner | 产出 |
|---|---|---|
| 规则判定 | `rule_judge` | P0/confirmed 命中、severity、location |
| 语义判定 | `semantic_judge` | 默认 candidate;满足 C1–C4 且开关开启才 confirmed |
| 明确规则类开关 | `rule_class_registry` | 按 control_code 的开关与 C3 一致率 |
| 依据同步 | `evidence_sync` | `authority_state`、`rule_conflict`、快照指纹(enrich 阶段) |

出处:`T@28498c99 §2 #6-9`。

### S3.2 输入 / 输出

- 输入:`ContentUnit v1` + `control_points` + `rule_snapshot` + `kb_snapshot` + `skill_allowlist`(`P@ff51fc87 §3.3.1`)。
- 中间产物:`DraftFinding`(Playbook §3.3.4 全部字段,但 `authority_state` / `rule_conflict` **缺省**)(`T@28498c99 §1bis.1`)。
- 输出:`ValidatedFinding`(含 `authority_state` / `rule_conflict` / 两个快照),只由 `finding_store` 接收。

### S3.3 同步 / 异步

worker 内同步;KB 检索与多模态模型为同步外部调用;失败按 `Playbook §3.3.6` 三分法降级。

### S3.4 状态机(Draft → Validated)

```
DraftFinding(内存,从未落盘,无 id)
   └─ evidence_sync enrich ─> ValidatedFinding(首次落盘,首次分配 finding_id)
                                  └─ 后续状态变化:新建条目 + derived_from,旧条 status→superseded
```

不变量:`DF-1`(Draft 进 store 必须拒)、`DF-2`(confirmed 缺 authority 拒收)、`DF-3`(decision_table 收 Draft 违约)
(`T@28498c99 §1bis.1`)。

### S3.5 失败 / 未测 / 幂等 / 审计

| 项 | 口径 | 出处 |
|---|---|---|
| 依据缺失 | 降 REVIEW,标「依据缺失」 | `P@ff51fc87 §3.3.6` |
| 依据过期 | 降 REVIEW,标「依据过期」 | 同上 |
| 依据冲突 | 强制转人工 **DP4 法务** | 同上 |
| 未测 | 依据状态 `untested` 合法(与「未算过」不同);报告必须能区分 | `T@28498c99 §1bis.1` |
| 幂等 | 同一单元+同一 snapshots 重跑,结论集合差集为空(L1-4b) | `P@ff51fc87 §3.2` |
| 审计 | `authority_ref` 可多条;`produced_by` / `derived_from` / `confirmed_by_rule_class` | `P@ff51fc87 §3.3.4` |
| C3 统计 | 一致率必须统计并公示;阈值未定前该 control_code 的开关默认关闭(M2/M3) | `P@ff51fc87 §3.3.4.1` |

### S3.6 UI 触点与 API

- 工作台展示每条 finding 的依据与状态;「依据缺失/过期/冲突」用不同标记。
- 规则/控制点为只读:`GET /api/v1/rules`、`GET /api/v1/control-points`、`GET /api/v1/routing`(`UIUX@6252cdee §8.7`)。
- 无「人工直接改判定」API;人工动作只能新建 finding(S4)。

### S3.7 验收与反向对照

| 验收 | 反向对照 |
|---|---|
| 语义默认 candidate(V3) | 关掉开关 → 必须只有 candidate |
| C1–C4 缺一降候选 | 逐条构造反例(C2 无 object/attribute、C4 无 bbox)→ 必须降 |
| 依据三分法 | 构造缺失/过期/冲突三种 → 三种标记必须可分别数出 |
| 规则冲突先于 BLOCK(链 4 vs 7) | 构造 rule_conflict + L4 → 必须 REVIEW/DP4 |

---

## S4 · Finding 落盘与状态

### S4.1 Owner

`finding_store`(`T@28498c99 §2 #12`):append-only;L2-5 三要素合取(控制点+权威依据+原文位置)缺一拒收。

### S4.2 输入 / 输出

- 只收 `ValidatedFinding`。
- 输出:不可变 finding 行;实质状态变化=新建行 + `derived_from`。

### S4.3 状态机

`candidate` / `confirmed` / `rejected` / `superseded`;合法组合白名单见 `P@ff51fc87 §3.3.4.1`。
`rejected` 与 `superseded` 不参与状态计算(`P@ff51fc87 §3.3.4.2`)。

### S4.4 失败 / 未测 / 幂等 / 审计

| 项 | 口径 | 出处 |
|---|---|---|
| 写入闸 | 缺三要素任一 → 拒收 | `T@28498c99 §2 #12` |
| 未测 | `authority_state` 读不出 → 该 finding 不进 confirmed;报告标「未测」 | `T@28498c99 §1bis.1` |
| 幂等 | 同 `finding_id` 两条 → 拒绝(ID-1) | `T@28498c99 §1bis.2b` |
| 审计 | 人工确认/驳回四字段必填:`reviewer` / `reviewed_at` / `reason` / `source_finding_id` | `P@ff51fc87 §3.3.4.3` |
| 不变 | 判断内容永不改;仅允许 `status→superseded` | `P@ff51fc87 §3.3.4.2` |

### S4.5 UI 触点与 API

- 复核动作:`POST /api/v1/cases/{id}/actions`(confirm/reject/reassign)(`UIUX@6252cdee §8.7`)。
- UI 必须显示「这条当初是机器看出来的还是人提出来的」(`source_finding_id` 链路)。

### S4.6 验收与反向对照

| 验收 | 反向对照 |
|---|---|
| ID-1 同 id 拒绝 | 喂一对同 id → 红 |
| ID-2 旧条除 status 外不变 | 改 severity → 红 |
| ID-3 derived_from 指向旧 id | 悬空/自指 → 红 |
| ID-4 Draft 入 store 拒 | 喂 Draft → 红 |

---

## S5 · 覆盖证明合成

### S5.1 Owner

`coverage_composer`(`T@28498c99 §2 #10`),按 `P@ff51fc87 §3.3.5` 四项合成,派生 `missing/partial/full`。

### S5.2 契约与状态

```
三项缺失/为空或模态未填 → missing
字段齐全且(does_not_cover 非空 或「未跑的为什么」非空) → partial
字段齐全且两者皆空 → full
```

空族（以 `control-points-v1.json` 的 `empty_families` 为准，当前四族：场景/权利/渠道/品牌）记 `未做·无控制点`,计入「未跑的为什么」→ 第一阶段 coverage 恒 partial, PASS 出不来(`P@ff51fc87 §3.3.8.0`)。

### S5.3 失败 / 未测 / 幂等 / 审计

- `missing` → 结论只能 `未审查`(链 1)。
- 覆盖证明四项必须出现在报告;缺一项即 `UNASSESSED`(L2-3)。
- 未测:无法派生 coverage_state → 标「未测」,不得当 full。
- 幂等:同一 unit + 同一 rule/kb 快照重算,coverage_state 与四项声明必须一致。
- 审计:规则版本 + 指纹、适用控制点清单随回执记录。

### S5.4 UI / API

- 报告与案件详情展示四项;部分覆盖时显著标注「未覆盖部分」。
- API 无独立写入端点;由 `GET /cases/{id}` 返回。

### S5.5 验收与反向对照

| 验收 | 反向对照 |
|---|---|
| covers 为空 → missing | 构造空 covers → 必须未审查 |
| 字段齐全但未跑非空 → partial | 构造 → 必须 partial 且永不 PASS |
| 四项全空且无未跑 → full | 构造 → 才允许链 15 |

---

## S6 · 唯一判定与处置路由

### S6.1 Owner

- `decision_table`:唯一状态来源,15 条链 + I1–I7(`T@28498c99 §2 #11`,`P@ff51fc87 §3.3.8`)。
- `disposition_router`:补 owner/finalizer/can_finalize/release_status/appeal_channel/due_at(`T@28498c99 §2 #15`)。
- `case_watch`:时限与升级(`T@28498c99 §2 #16`)。

### S6.2 输入 / 输出

- 输入:`parse_status`、`failure_kind`、`coverage_state`、`findings`、`rule_conflict`(`P@ff51fc87 §3.3.8.0`)。
- 输出:`state` / `external_label` / `layer` / `obligations` / `max_sev` + 回执字段。

### S6.3 同步 / 异步

worker 内同步;`case_watch` 定时异步。

### S6.4 状态机(判定链)

按 `P@ff51fc87 §3.3.8.1` 的 15 条链短路执行;`ERROR` 是独立运行态,不产出标签(`P@ff51fc87 §3.3.8.0`)。

### S6.5 失败 / 未测 / 幂等 / 审计

| 项 | 口径 |
|---|---|
| 不变量违反 | `run_state=ERROR`,回执记 `invariant_violation: I*` |
| 未测 | 判定输入读不出 → `ERROR`(不产出标签),不得当 PASS/REVIEW | `P@ff51fc87 §3.3.8.0` |
| 并行义务 | `pending_candidate` / `partial_coverage` / `evidence_gap` / `invariant_violation`,空数组也要出现(`P@ff51fc87 §3.3.8.1b`) |
| 处置五层 | DP0–DP4;五档全部停「待放行」(`P@ff51fc87 §4.1`/§4.3) |
| 时限 | 转出→超时→升级项目统筹,升级可查(L3-2) |
| 审计 | 层与 owner 来自 routing 表;案件号即回执号(L3-3) |

### S6.6 UI / API

- 复核队列 `GET /api/v1/queue`;案件 claim/**unclaim**/reassign(`UIUX@6252cdee §8.7`;unclaim 是释放领取,不是发布 release)。
- 案件详情显示标签、层、并行义务、时限。

### S6.7 验收与反向对照

| 验收 | 反向对照 |
|---|---|
| 判定表穷举对拍(L2-1b) | 漏写一格 → 红(L2-1d) |
| candidate 不贡献严重度(L2-6a) | 删掉全部 candidate 后状态若变重 → 红 |
| candidate 可作 REVIEW 门(L2-6b) | 有 candidate 无 confirmed → REVIEW |
| ERROR 不产出标签 | 构造 I1–I7 违反 → 标签必须 null |

---

## S7 · 人工复核 / 申诉 / 签发 / 失效重审

> **v1.2 语义纠正(先读这一段)**
>
> 1. **worker 的初次 output 发生在人工之前**:S1 worker 跑完 S2–S6 后,先由 S8a 产出
>    `ReviewIR` / Markdown / 群消息 / 卡片;此时内容已经有一份可看的结果。
> 2. **人工动作不是「修改那次输出」**:确认/驳回/申诉/签发/撤回/失效重审,
>    只能**新建 finding / 新建 run / 新建 IR / 新建 report**;旧 IR、旧 report、旧签发记录
>    **永久保留、不可改删**(Playbook §3.3.4.2 append-only;§4.3 R2)。
> 3. **S7 不是回边**:人工触发的新运行是**新的 pipeline 实例**(新 `run_id`、新 `ReviewIR` 版本),
>    不是把内容送回 S2 原地重跑;五步流水线的「无回边」结论不变。
> 4. 因此端到端时序是:`S0→S1→S2→…→S6→S8a→(人看)→S7→(若需重跑)→S1'→…→S8b`;
>    S7 在 S8a 之后发生,编号顺序不代表执行顺序。

### S7.1 Owner

| 环节 | owner |
|---|---|
| 复核台账与抽样 | `reviews_ledger` |
| 签发 / 撤回 / 失效重审 | `release_gate` |
| 超时升级 | `case_watch` |
| 定时任务(SLA/retention/outbox 对账) | scheduler(UIUX@6252cdee §8.2) |
| 领取 / lease / 草稿交接 | **owner 未定 → 开发阻断**;候选 `disposition_router`(队列/分派)与 `reviews_ledger`(草稿/台账),未拍板前不得实现。交互见 `UIUX@6252cdee §UJ-2`;TS-33/34 见 `待确认 §二之四` |

### S7.2 输入 / 输出

- 复核:案件 + finding → 人工结论(新建 confirmed/rejected)。
- **领取与草稿**:claim 原子独占;lease 30 分钟无活动自动释放并保存 draft;新审核员可只读查看前任 draft,
  **显式 adopt 一份 primary draft**(其余 draft 仅引用片段/字段并记 `source_draft_id`)。
  细节以 `UIUX@6252cdee §UJ-2` 与 `待确认 §二之四`(TS-33/34、多草稿采纳、主草稿选择)为准,本文不复述权限细节。
- 签发:案件 + `ReviewIR` 版本 + **全字段绑定**(内容/双指纹/规则与 KB 快照/已用 refs/冲突表版本/媒体指纹 root/签名人/时间/step-up/理由,见 `UIUX@6252cdee §8.4` 与 Appendix A SB)→ `release_signatures`。
- 失效:内容/依据/冲突裁定/送审指纹变化 → `invalidated` → 全量重审 job。
- 申诉:appeal 事件 → 暂停/迁移/撤回。

### S7.3 同步 / 异步

人工动作同步(带 step-up);失效检测与重审入队异步(事件+job 原子写,`UIUX@6252cdee §8.6`)。

### S7.4 状态机

```
pending_release ──sign──> signed ──revoke──> revoked
       └──reject──> rejected ──修改重提──> 审查流程
signed ──内容/依据/指纹/冲突变化──> invalidated ──全量重审──> pending_release
```
(`UIUX@6252cdee §10.1`)

复核对列/领取:

```
unassigned ──claim──> claimed ──submit──> closed
claimed ──lease 30m 无活动──> released(draft 已保存)
claimed ──lease/version 冲突──> conflict(乐观锁拒绝,不静默覆盖)
```

申诉状态与下线任务状态分别见 `UIUX@6252cdee §5.2/§5.4`。

### S7.5 失败 / 未测 / 幂等 / 审计

| 项 | 口径 | 出处 |
|---|---|---|
| 权限 | 人级 allowlist + tenant/product_line + SoD(非提交人、非最终复核人) | `UIUX@6252cdee §10.2` |
| 幂等 | 写操作带 `Idempotency-Key`;重复 sign/revoke 必须拒 | `UIUX@6252cdee §8.7` |
| 审计 | 签发绑定**全字段**(内容版本/IR id+version/双指纹/规则与 KB 快照/已用 authority_ref 版本/冲突表版本/媒体各类指纹+集合 root/签名版本/签名人/时间/step-up ref/理由);撤销审计独立账本。字段清单以 `UIUX@6252cdee §8.4` + Appendix A SB-1…SB-11 为准,本文不复述 | `UIUX@6252cdee §8.4`,`验收表-v3` SB 组 |
| 未测 | readiness 无法判时显示「未测」,不显示通过 | `UIUX@6252cdee §10.3` |
| 失效 | 自动失效无 override;event+job 原子写 | `UIUX@6252cdee §8.6` |
| 领取幂等 | 两个用户并发 claim 同一案件:恰好一个成功,另一个明确失败;重复 claim 拒绝 | `验收表-v3` TS-31 |
| lease 幂等 | lease/version 乐观锁:并发写只有一个成功,另一个收到明确冲突 | `验收表-v3` TS-33 |
| 草稿审计 | adopt 记录 `source_draft_id`;原稿不可改;不自动进入结论 | `待确认 §二之四`(TS-34 拟) |
| autosave | 表单字段/notes/evidence selections/references 全量快照;只有 explicit submit 才进 formal finding/decision | `UIUX@6252cdee Appendix C D-101` |

### S7.6 UI / API

- 待签发 `GET /api/v1/release/pending`;readiness `GET /api/v1/cases/{id}/release-readiness`;
  **唯一受控入口** `POST /api/v1/cases/{id}/release-decision`;撤回 `.../release-revoke`(`UIUX@6252cdee §8.7`)。
- 申诉:`GET/POST /api/v1/appeals`,迁移/撤回(同上)。
- 下线任务:`GET /api/v1/takedown-tasks` + start/complete/fail/retry/reassign/waive(同上)。

### S7.7 验收与反向对照

| 验收 | 反向对照 |
|---|---|
| 机器/前端直写 release_status → 禁止(RLS) | 构造直写 → 必须 403 |
| step-up 缺失 → 拒 | 去掉 step_up_token → 拒 |
| 失效**五类**触发源逐条:① 内容指纹 ② rule_snapshot ③ kb_snapshot ④ 已用 authority_ref 版本 ⑤ 冲突表版本 | 逐类构造变化 → 必须 invalidated + 建 job;**未使用过的 ref 变化不触发** |
| 授权撤销后既有签名有效(GR-10…18) | 撤销 grant 后旧签名仍有效 |
| 并发 claim 恰好一个成功(TS-31) | 两个用户同时 claim 同一案件 → 另一个必须明确失败 |
| lease 30 分钟自动释放且 draft 已保存(TS-33) | 29 分钟仍独占、30 分 01 秒释放;释放前 draft 可见 |
| 草稿 adopt 留痕(TS-34 拟) | 未 adopt 的草稿不得进入结论;引用须记 `source_draft_id` |

---

## S8 · 产物输出(初次 S8a / 人工触发 S8b)

> **S8a(初次输出)**:worker 在**人工动作之前**产出第一份 `ReviewIR`、Markdown、群消息、卡片。
> **S8b(人工触发的新输出)**:人工确认/驳回/申诉/签发/失效重审后,由**新 run** 产出**新 IR / 新 report**;
> 旧 IR/report 不改不删(R2)。两份输出的 owner 与契约相同,差别只在触发源与版本号。

### S8a.1 Owner

| 产物 | owner |
|---|---|
| `ReviewIR` 组装 | `orchestrator`;物理落盘 `artifact_store` |
| Markdown 报告 / MessageView | `report_renderer` |
| 静态报告载体与索引 | `report_store` |
| 形态决策与发送兜底 | `send_gateway` |
| 传输原语 | `feishu_io` |

### S8a.2 输入 / 输出契约

- `ReviewIR`:唯一真相,保留 1 年;报告记 `source_ir_version` + 指纹,只指向 `ReviewIR`(`P@ff51fc87 §4.3`)。
- Markdown 六区块逐字标题(`P@ff51fc87 §4.3.3`),F1/F2。
- 群消息:每标签恰好一句 + 报告链接;MSG-1…4(`P@ff51fc87 §4.3.2`)。
- 卡片:唯一形态决策在 `send_gateway`;卡片被拒降级纯文本;群内永不出现卡片标记原始字符(L4-4/L4-6)。
- **媒体集合指纹**:按 `P@ff51fc87 §4.5.8`(TS-27)执行——每项 RFC 8785 JCS 规范化 → SHA-256,
  按 `kind + stable_id` 排序 → root hash;跨语言(Node/TypeScript/Python)逐字节一致;不称 Merkle。
  签发绑定的 `media_fingerprints_root_hash` 以该算法为准(`UIUX@6252cdee §8.4`)。

### S8a.3 同步 / 异步

renderer 同步;report_store 落盘同步(内容寻址);发送经 outbox 异步(`UIUX@6252cdee §8.6`)。

### S8a.4 状态机(初次输出)

```
IR committed ──render──> report file ──index──> report_id
IR changed ──新文件,旧报告不改不删(R2)
```

### S8a.5 失败 / 未测 / 幂等 / 审计

| 项 | 口径 |
|---|---|
| 发送 | 按来源分档 at-most/at-least;`logical_delivery_id` 共用;不做 exactly-once 承诺(G-2) |
| 未测 | 指标/计数读不出 → 写「未测」 |
| 幂等 | 外发 outbox 幂等键;重复发送不得产生两条逻辑投递 |
| 审计 | 每次发送记录 logical_delivery_id、来源、结果 |

### S8a.6 UI / API

- 报告:`GET /api/v1/reports`、`GET /api/v1/reports/{id}`、`POST .../resign`(`UIUX@6252cdee §8.7`)。
- UI:静态报告只读;工作台不提供「编辑报告」。

### S8a.7 验收与反向对照

| 验收 | 反向对照 |
|---|---|
| 五标签必带字段(L4-8) | 去掉严重度/覆盖句 → 红 |
| 卡片拒绝降级纯文本(L4-4) | 注入卡片失败 → 文本必须发出 |
| 六区块齐全、字段逐字(F1/F2) | 省空块/同义替换 → 红 |
| IR 变则新报告(R2) | 改 IR 后旧报告不得被改 |

### S8b · 人工触发的新 run 输出(仅限会改变结论/触发失效的事件)

> **不是所有人工事件都产生新 run。** 先按事件分类,避免无意义重跑:

| 事件 | 是否新 run | 产出 |
|---|---|---|
| 确认候选 / 驳回候选 / 撤销已确认 finding | **是**(finding 变了) | 新 finding(`derived_from` 指旧 id,旧条 `status→superseded`)→ 新 run → 新 IR 版本 → 新 report |
| **签发 sign** | **否** | **只新增不可变 `release_signatures` 记录**;finding/IR/report 均不变 |
| **撤回 revoke** | **否**(除非随后触发失效) | release 状态 signed→revoked;若内容已发布 → 创建下线任务;**不自动新 run** |
| 五类失效输入变化 | **是** | `invalidated` → 新 full-review run → 新 IR 版本 → 新 report;已发布则加下线任务 |
| 申诉 pause/migrate/withdraw | **否**(除非底层 finding 变) | 只改 appeal 状态;不产新 IR/report |

> **结论**:只有「finding 变化」与「失效重审」进入 S8b;sign/revoke/申诉单独走 S7 的记录变更。

#### S8b.1 输入 / 输出

- 输入:会改变结论的事件(确认/驳回/撤销)或失效事件 + 旧 `ReviewIR` 指针 + `change_set`。
- 输出:新 `run_id`;新 `ReviewIR`(新 `ir_id/ir_version`);新 report(`source_ir_version` 指向新 IR);
  旧 IR/report/签发记录**原样保留**。
- **字段约束**:finding 沿用 `derived_from` + `status=superseded`(权威定义见 `P@ff51fc87 §3.3.4.2`);
  **不新增 schema 未定义的字段** —— 该语义已由上述两字段承载,不再自创第五个字段名。

#### S8b.2 状态机(仅上述两类事件)

```
旧 IR vN ──finding 变化/失效──> 新 run queued ──> running ──> 新 IR 版本 committed ──> 新 report
旧 IR / 旧 report 始终可读;不覆盖、不删除、不改写
```

#### S8b.3 失败 / 未测 / 幂等 / 审计

| 项 | 口径 |
|---|---|
| 失败 | 新 run 失败 → 落 `run_record`,旧版本保持原状态;不得把旧报告改成「失败」 |
| 未测 | 新 run 未产出可判结果 → 新报告标「未测」,不得沿用旧结论冒充 |
| 幂等 | 同一人工动作/同一 `change_set_hash` 只建一个 job;重复提交返回首次结果 |
| 审计 | 记录 `old_ir_version → new_ir_version`、`derived_from`、操作者、理由、时间 |

#### S8b.4 验收(待建)

| 验收 | 反向对照 |
|---|---|
| 人工动作后旧 IR/report 字节不变 | 构造旧版本修改 → 必须红 |
| 新 report 的 `source_ir_version` 指向新 IR | 指向旧 IR → 必须红 |
| `derived_from` 链完整、旧 finding `status=superseded` | 悬空/自指 → 必须红 |
| 同一动作重复提交只建一个 job | 两个 job → 必须红 |

> 本节验收均为**待建**(test_id/fixture/command 未落),不得当可执行。

---

## S9 · 指标与回流

### S9.1 Owner

`metrics_read_model`(只读聚合)、`reviews_ledger`(人工台账)、`regression_gate`(冻结回归集与 CI 门)。

### S9.2 指标与口径

- 四指标七要素、未测显示未测、每比率带 n/样本不足(`T@28498c99 §2 #21`)。
- 数据源:IR + reviews_ledger + submissions/receipts;`events.jsonl` 只作定位索引。
- 抽检分层:BLOCK 全量 + PASS/待自决/REVIEW/未审查四层(`T@28498c99 §2 #22`)。

### S9.3 回流

- 回归集 50–100 条,含四条已知陷阱负样本;规则变更必须跑并产出前后读数,不跑不得合入(`T@28498c99 §2 #23`)。
- C3 一致率统计回流到 `rule_class_registry`,低于基线阈值自动降回 candidate。

### S9.4 UI / API

- `/metrics` 仅内部,阶段一**禁止独立 metrics dashboard**(`UIUX@6252cdee §12.1`,`UIUX@6252cdee §8.7`)。
- 工作台只在案件/报告内展示与本案相关的计数。

### S9.5 失败 / 未测 / 幂等 / 审计

| 项 | 口径 |
|---|---|
| 失败 | 指标源读失败 → 该指标显示「未测」,不得补 0 |
| 未测 | 无真实复核数据时,召回/误判/推翻率只能显示「未测」 |
| 幂等 | 同一 IR + 同一窗口重复聚合 → 结果一致;不得重复计数 |
| 审计 | 每次聚合记录窗口、数据源版本、样本量 n |

### S9.6 验收与反向对照(待建)

| 验收 | 反向对照 |
|---|---|
| 未测不得显示 0(L5-2) | 断开数据源 → 必须显示未测 |
| 比率带 n / 样本不足(L5-5) | n=0 → 不许显示百分比 |
| 回归集规模与四条陷阱(L5-4) | 49/101 条 → 红;缺一条陷阱 → 红 |

> S9 验收当前均为**待建**(test_id/fixture/command 未落)。

---

## S10 · 横切:失败 / 未测 / 幂等 / 审计

### S10.1 统一口径(全链路)

| 形状 | 要求 | 出处 |
|---|---|---|
| 失败 | 四类 `failure_kind` 分别可数;不许静默跳过 | `P@ff51fc87 §3.2` |
| 未测 | 与「通过」「红」三态不同;读不出必须写「未测」 | `T@28498c99 §1bis.2` |
| 幂等 | 入口 `attempt_id`、job 幂等键、finding id、外发 logical_delivery_id、写 API `Idempotency-Key` | 各阶段 |
| 审计 | 安全审计独立 append-only JSONL + 前缀哈希链;读取审计独立 access-log | `UIUX@6252cdee §8.8` |
| 原子提交 | P-1:staging→rename→manifest.tmp→fsync→rename manifest(唯一可见提交点) | `T@28498c99 §1ter.5` |
| 崩溃恢复 | committed / orphan / uncommitted / garbage 四态穷举 | `T@28498c99 §1ter.5` |

### S10.2 媒体字节边界

- 允许下载(红线 2026-10-17 改线),但:每个调用点登记(`tools/download_callers.json`)、只落临时目录或仓外数据根、不许进公开仓(MB-1…MB-3,`P@ff51fc87 §3.3.9`)。
- 采集器侧仍受 `AGENTS.md` §2.6 现行口径约束;本文不新增下载授权。

---

## 11. UI 触点与 API 边界总表

| 阶段 | UI 触点 | API | 只读/写 |
|---|---|---|---|
| S0 | 提交入口(群/表/Web) | `POST /submissions` | 写 |
| S1 | 案件列表/详情 | `GET /cases`, `GET /cases/{id}` | 读 |
| S2 | 案件详情中的解析状态与覆盖声明 | 同 S1 | 读 |
| S3 | finding 依据与状态 | `GET /rules`, `/control-points`, `/routing` | 读 |
| S4 | 复核动作 | `POST /cases/{id}/actions` | 写 |
| S5 | 覆盖证明展示 | 同 S1 | 读 |
| S6 | 队列、claim/unclaim/reassign、并行义务 | `GET /queue`, `POST /cases/{id}/claim|unclaim|reassign` | 读/写 |
| S7 | 复核/申诉/签发/下线任务 | `/appeals*`, `/release*`, `/takedown-tasks*` | 读/写 |
| S8 | 报告列表与只读详情 | `GET /reports`, `/reports/{id}` | 读 |
| S9 | 无独立 dashboard(阶段一) | `/metrics`(内部) | 读 |

**核对结论(模块 vs UI/API)**:
- 27 个模块中,**有直接 UI 触点的是** `release_gate`、`reviews_ledger`、`disposition_router`(经队列)、`report_store`(经报告页)、`case_watch`(经案件时限展示)、`control_point_registry`(只读页)。
- **纯后台、无 UI** 的模块:`normalizer`、`rule_judge`、`semantic_judge`、`evidence_sync`、`coverage_composer`、`decision_table`、`finding_store`、`contract_validator`、`contract_suite`、`artifact_store`、`metrics_read_model`、`regression_gate`、`rule_class_registry`、`skill_registry`、`job_dispatcher`、`orchestrator`、`submission_router`、`feishu_io`、`send_gateway`、`media_pipeline`、`report_renderer`。
- **API 边界**:以 UIUX v1.2 §8.7 + Appendix B 为准(端点、起止状态、409、幂等);三个唯一受控入口:提交、复核动作、`release-decision`。
  规则/控制点/路由为 **Web 只读**,配置修改走权威源(UIUX Appendix C D-106),**不补管理 API**;这一条已定,不再是待补项。

---

## 12. 冲突与缺口登记(本文不裁定)

### 12.1 P / L 口径冲突(PRD vs Playbook)

| # | 冲突 | 证据 |
|---|---|---|
| C-1 | `P0` 在盘上有**四个答案**:PRD §6.2 举例 5 个、§7.3 列 7 条、`P0规则` 表 17 条、引擎标 `L4 高危` 11 条 | `R@9be0c9f7 §2.2/§6` |
| C-2 | PRD 用 `P0` 表示「检测层/优先级」,同时用 `L4/L5` 表示严重度;Playbook §1.1.1 明确 `P` 是检测层、`L` 是严重度,两者不是一回事 | `P@ff51fc87 §1.1.1`;`R@9be0c9f7 §2.2` |
| C-3 | PRD §2.2 把 P0 拆成「P0-字面/P0-语义」;引擎输出 `L4 高危`。**同一控制点 M03 在两处分别被读成 P0 红线与「审慎关注」** | `R@9be0c9f7 §6` |

> **本文不裁定哪套对**。进入开发前必须由产品/法务给出一份唯一映射:P0/P1/P2/P3(检测层)↔ L0–L5(严重度)↔ control_code。
> 否则 `detected_by` 与 `severity` 的取值会在实现时各写一套。

### 12.2 「二级控制点」:定义已存在,未交付的是 U2 与主表

> **v1.1 更正**:v1 写「全仓 0 命中 → 无定义」是**结论过强**。字面词「二级控制点」确实 0 命中,
> 但 Playbook 已经把该概念定义成「控制族 → 控制点」并给了主表结构。

| 项 | 状态 | 证据 |
|---|---|---|
| 三层结构(控制族 → 控制点 → 双键) | **已定义** | `P@ff51fc87 §5.3` |
| 七个控制族 | **已定义** | `P@ff51fc87 §5.2` |
| 控制点主表结构(交付物) | **已定义** | `P@ff51fc87 §5.3`(「第二层:控制点主表(交付物,不是概念)」)、字段表 `P@ff51fc87 §5.3` |
| 主表判据 L6-1…L6-4 | **已定义** | `P@ff51fc87 §5.3` |
| 主表**内容** | **结构已交付，点位未签** | `P@ff51fc87 §6(U2)` U2:结构与首批 20 个真码已落 `control-points-v1.json`；**剩余空族（以 `empty_families` 为准，当前四族：场景/权利/渠道/品牌）的点位未定，待产品+法务签署** |
| 空族（`empty_families`）对 coverage 的后果 | **已承认** | `P@ff51fc87 §3.3.8.0` |

- **准确表述**:不是「没有定义」,而是「**定义与首批 20 码结构已落盘，剩余空族（`empty_families`）点位未定、待签署（U2）**」。
- **修法**:补剩余空族（`empty_families`）点位并完成产品+法务签署;在补齐前,coverage 恒 partial、PASS 出不来是**已知且已登记的后果**。

### 12.3 开工门状态(S-3 / P-1 / G 门)

| 门 | 状态 | 事实 |
|---|---|---|
| **S-1** | `closed` | Draft→Validated 三段式已定义(`T@28498c99 §8 S-1`) |
| **S-2** | `closed` | `attempt-v1` 已定义(`T@28498c99 §8 S-2`) |
| **S-3** | **`open`** | 仍缺两块:① `fetch_error` 无正文时的稳定 id 规则;② 其余消费者待同步(`T@28498c99 §8 S-3`) |
| **P-1** | **`open`** | 设计已重写,但**代码一行没写**(`T@28498c99 §8 P-1`) |
| **G-1** | `closed`(**仅定义**) | 放行状态机 + 身份契约已定义;**实现不存在**;认证归 **G-4 仍 open**(`T@28498c99 §8 G-1` / `§8 G-4`) |
| **G-2** | **`open`** | outbox 设计已重写,代码未写(`T@28498c99 §8 G-2`) |
| **G-3** | **部分 open** | durable inbox 有设计;「进程不在时事件仍丢」那一半仍 open(`T@28498c99 §8 G-3`) |
| **G-4** | **`open`** | 认证/租户边界缺失(`T@28498c99 §8 G-4`) |
| **G-5** | **`open`** | 不可信输入无 sandbox(`T@28498c99 §8 G-5`) |
| **G-6** | **`open`** | 外发原文无最小化(`T@28498c99 §8 G-6`) |

> **G-1 `closed` 的准确语义**:只关闭「定义类」子项,**不等于开发放行**。
> 主方案整体仍是 **DRAFT·NO-GO**(`T@28498c99 头部状态`),代码一行没写;认证仍归 G-4 open。

> **计数口径**:以 `T@28498c99 §8` 为准;本文不再登记计数漂移。

### 12.4 模块计数

- 27 个模块,见 `T@28498c99 §0` / `§2`(模块 27 = `release_gate`)。

### 12.5 其他已知缺口(盘上自认)

| # | 缺口 | 出处 |
|---|---|---|
| GAP-1 | 空族（以 `control-points-v1.json` 的 `empty_families` 为准，当前四族：场景/权利/渠道/品牌）无控制点 → coverage 恒 partial → 阶段一 PASS 出不来 | `P@ff51fc87 §3.3.8.0` |
| GAP-2 | `source.kind=文档` 与 `content_type=文档` 读混 | `T@28498c99 §4 残留` |
| GAP-3 | 语义直接确认绕过人工进 BLOCK 的代价,依赖 C1–C4 + M1–M3 七条 | `P@ff51fc87 §3.3.4.1` |
| GAP-4 | 阈值一律「先跑基线再定」,未定前开关默认关闭 | `P@ff51fc87 §3.3.4.1` |
| GAP-5 | ~~`rule_class_registry` 无管理 API~~ → **已定**:规则/控制点 Web 只读,配置走权威源 | `UIUX@6252cdee Appendix C D-106` |

---

## 13. 进入开发前必须补的 spec(按阶段)

> **验收可执行性标注**:下表全部是**待建 spec**;「验收方式」是设计意图,当前**没有** test_id / fixture / command。
> 任何一条在补齐 `test_id + fixture + command` 之前,都不得写成「可执行」或「已验证」。

| 阶段 | 必须补的 spec | 验收方式(待建) |
|---|---|---|
| S0 | `source.kind=文档` 消歧句;Attempt 的 `reason` 禁止词表 | test_id 待建;fixture 待建;command 待建 |
| S1 | run_record schema 定稿;successor 合并规则 | 待建 |
| S2 | `fetch_error` 稳定 id 规则(S-3 剩余) | 待建 |
| S3 | P/L 唯一映射表;C3 阈值基线与开关默认值 | 待建 |
| S4 | finding 状态转换的代码级对拍 | 待建 |
| S5 | 「空族（`empty_families`）」在报告中的固定文案 | 待建 |
| S6 | 判定表 2592 组合穷举对拍脚本 | 待建 |
| S7 | release-readiness 五标签逐条样本;claim/lease/draft/adopt 并发与交接样本 | 待建(TS-31/33/34) |
| S8a | MessageView 四档模板逐字定稿 | 待建 |
| S8b | 人工触发新 run 的 new IR/new report 样本;旧版本不可改断言 | 待建 |
| S9 | 四指标数据源与「未测」显示规则 | 待建 |
| S10 | P-1 六种崩溃点注入脚本;G-2/G-3 对账脚本 | 待建 |

---

## 14. 明确不做裁定的事项

1. P0/P1/P2/P3 与 L0–L5 的映射(**产品/法务**)
2. 控制点主表的剩余空族（`empty_families`，当前四族）点位与签署(U2)(**产品 + 法务**;定义与结构已存在,见 §12.2)
3. S-3 的 `fetch_error` id 规则(**架构 + 产品**)
4. P-1/G-2/G-3 的实现时序(**工程**)
5. 空族（`empty_families`）何时补控制点、补完后 PASS 是否解锁(**产品**)
6. C3 一致率阈值(**产品 + 评估**,先跑基线)

> 已关闭、不再列为未决:rule_class_registry 管理入口(已定 Web 只读/配置走权威源)。

---

## 15. 本文的证据化索引

> 引用统一写成「缩写@短hash 章节」;行号不再作为主引用(会漂移)。

| 主题 | 引用 |
|---|---|
| 五步流水线 / 无回边 | P@ff51fc87 §2 |
| 四维输入 | P@ff51fc87 §3.1 |
| ContentUnit 契约 | P@ff51fc87 §3.2 |
| 编排器输入/输出 | P@ff51fc87 §3.3.1–3.3.2 |
| 回执 schema | P@ff51fc87 §3.3.3 |
| Finding 分型与 append-only | P@ff51fc87 §3.3.4 |
| Coverage | P@ff51fc87 §3.3.5 |
| 知识库三分法 | P@ff51fc87 §3.3.6 |
| 唯一判定表 15 链 | P@ff51fc87 §3.3.8 |
| 停机条件(阶段一无提前停) | P@ff51fc87 §3.3.7 |
| 处置五层 / 五标签 | P@ff51fc87 §4.1–4.2 |
| 输出三产物 / 六区块 | P@ff51fc87 §4.3 |
| 放行门 RL-1…15 | P@ff51fc87 §4.4 |
| 交付与界面 TS-1…33 | P@ff51fc87 §4.5(含 TS-27 JCS) |
| 27 模块表 | T@28498c99 §2 |
| Draft→Validated(S-1) | T@28498c99 §1bis.1 |
| Attempt(S-2) | T@28498c99 §1bis.2 |
| P-1 原子提交 | T@28498c99 §1ter.5 |
| G-2/G-3 | T@28498c99 §1ter.7–8 |
| 开工门状态 | T@28498c99 §8 |
| 模块计数(已统一 27) | T@28498c99 §0 / §2 |
| 控制点主表定义 / U2 | P@ff51fc87 §5.2–5.3 + §6(U2) |
| claim / lease / draft / adopt | UIUX@6252cdee §UJ-2 / Appendix A QC |
| 签名绑定字段 | UIUX@6252cdee §8.4 / Appendix A SB |
| 五类失效输入 | UIUX@6252cdee §UJ-4 / Appendix A INV |
| JCS 媒体指纹 | P@ff51fc87 §4.5.8(TS-27);A@432f4a2c #130 |
| UI/UX 角色与旅程 | UIUX@6252cdee §1–§2 |
| 页面与状态矩阵 | UIUX@6252cdee §3–§5 |
| 前端/后端规格 | UIUX@6252cdee §7–§9 |
| API 目录/状态机 | UIUX@6252cdee §8.7 + Appendix B |
| G-1 单章 | UIUX@6252cdee §10 |
| 测试与验收 ID | UIUX@6252cdee §11 + Appendix A |
| 证据矩阵 | EV@34fda3a0 §一 / §十三 |
| PRD P0 四答案 | R@9be0c9f7 §2.2 / §6 |
| 验收表 v3 | A@432f4a2c |
| 待确认技术栈 | D@2e6340ab |

### 15.1 源文件 hash 清单(2026-10-18 本轮审计基准)

> 行号会漂移;**以 hash 为准**。引用本文任何 `file:line` 时,先核对应行号属于该 hash 的文件。

| 文件 | sha256 | 字节 |
|---|---|---|
| `Playbook/内容审查Agent-产品Playbook-v1.1.md` | `ff51fc87f5aa477ba9536355d8f38fcadab2c2fb39f3cb6471e7ebd9fa9e03b8` | 110908 |
| `Playbook/技术解决方案-v1.md` | `28498c99716b0f45a39b65f5efec279e30c30c8a145621f8f5b7df1feeec4ef2` | 159522 |
| `PMO/audit/内容审查Agent-UIUX前后端规格草案-v1.md` | `6252cdeedc23b2e8abe382d067b16dfaa472bd54b5cac8141b6067c7f98d264a` | 80364 |
| `PRD/内容审查Agent-PRD-优化版-v2.0.md` | `9be0c9f7e2fb8afe835bc426d760770f5df2391984a2a9eb94d23507eb2d540f` | 105836 |
| `PMO/audit/验收表-v3-覆盖全部判据-20261017.md` | `432f4a2c073dc87d13f52df4574262ac9d1a7d170b0831efe0283db85d450c69` | 110129 |
| `PMO/audit/待确认-技术栈与工程选型-v1.md` | `2e6340ab36b5d1332b802440ca232e40b26433f41078a39c3bea03c827ec68c8` | 14168 |
| `PMO/audit/内容审查Agent-行业证据矩阵-v1.md` | `34fda3a04909beb50e0fae2ca688f451dfb8ae7a75d4bbe1e1fcb3adf5ce3872` | 46714 |

> **冻结口径（2026-10-18 S-1 后重冻）**：上表七份全部为**现行值**，不再是「待最终冻结」。
> 任何一份改动后，本表与引用它的文档必须同步重登记；`SHASUM` 以全 64 位为准，短 hash 仅用于正文。
> 引用本文任何位置时用「缩写@短hash 章节」；裸行号不再使用。
