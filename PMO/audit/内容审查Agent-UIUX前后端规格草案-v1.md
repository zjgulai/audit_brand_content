# 内容审查 Agent · UI/UX 前后端规格草案 v1.3.1

> 起草：audit-multi-content-6d
> 日期：2026-10-18
> 依据：UI/UX 审计 v0.2（已验收）、技术审计 v0.3（已冻结）、用户逐题拍板的技术栈与产品口径。
> 状态：**DRAFT（规格草案，待评审）**；本文件只描述规格，不代表已实现或已验收。
> **设计 ≠ 实现**：本文件所有 [已定] 只表示“设计决策已定”，**P1 代码、页面、API、部署均未实现**；所有 [门] 未清前不得进入实现。P-1 / G-2 / G-3 / G-4 / G-5 / G-6 等上游门仍 open 的，本文不得被读成已闭环（S-3 已于 2026-10-18 关闭定义/登记门）。
>
> **v1.3 变更记录（2026-10-18）**：
> 1. 明确 ContentUnit 仅由 normalizer 产出；Web/报告只读 ReviewIR；`fetch_error` 稳定 id 已随 **S-3 closed**（2026-10-18，T0-02 规则；消费者同步清单见工作流 §S2.8）。
> 2. UJ 头部新增五步 ↔ S0–S9 映射，并写明全量跑完、无提前停。
> 3. 媒体 root hash 明确 **RFC 8785 JCS → UTF-8 canonical bytes → SHA-256**，stable sorted manifest，并要求 Python/TS golden vectors。
> 4. 复核并保留 v1.2 的 `/unclaim`、签名绑定全字段、五类失效输入、draft autosave、session、queue、takedown、appeal、grant、WCAG。
> 5. 所有“实现不存在/门未清”处显式标注，不把设计当实现。
> 6. 源引用改为“章节 + 短 hash”，行号仅辅助。
> 7. 源 hash 更新；上游仍在变动的文件标“待最终冻结”。
> 标注约定：
> - **[已定]** 有用户拍板或文档依据，spec 阶段不得擅改；
> - **[候选]** 方向已定，但 exact 版本/模型/参数待兼容矩阵或压测后锁定；
> - **[待拍]** 仍缺产品/技术决策；
> - **[门]** 开发前必须通过的验证门，未过不得实现。
>
> 证据级别（与 `PMO/audit/内容审查Agent-行业证据矩阵-v1.md` 对齐）：
> **L0** 无证据｜**L1** 官方文档/法规｜**L2** 本仓实测｜**L3** 第三方审计/学术研究（机制证据，非效果证明）｜**L4** 第三方部署 + 独立现场效果（**当前为 0**）。
>
> **源文档清单**（引用一律带短 hash；行号以该 hash 对应快照为准，源文件变更后须重登记）：
>
> | 缩写 | 路径 | 短 sha256 | 行数 | 冻结状态 |
> |---|---|---|---|---|
> | R | `PRD/内容审查Agent-PRD-优化版-v2.0.md` | `9be0c9f7e2fb` | 1745 | **终验后重冻**（2026-10-18） |
> | P | `Playbook/内容审查Agent-产品Playbook-v1.1.md` | `ff51fc87f5aa` | 1666 | **S-1 后重冻**（2026-10-18） |
> | T | `Playbook/技术解决方案-v1.md` | `d3093e2d4d9d` | 1335 | **S-1 后重冻**（2026-10-18） |
> | A | `PMO/audit/验收表-v3-覆盖全部判据-20261017.md` | `432f4a2c073d` | 313 | **S-1 后重冻**（2026-10-18） |
> | D | `PMO/audit/决策溯源账-v1-20261017.md` | `d6b4635590d4` | 242 | 当前快照 |
> | ADR12 | `ADR/ADR-0012-判定引擎产品化与处置分层.md` | `674575a44fa3` | 1066 | 当前快照 |
> | ADR03 | `ADR/ADR-0003-敏感样本分级准入.md` | `2f987b44b45f` | 89 | 当前快照 |
> | ADR05 | `ADR/ADR-0005-工具只补证据不替人过门.md` | `52f3a567a2e7` | 131 | 当前快照 |
> | ADR08 | `ADR/ADR-0008-机制分离白名单独立成表.md` | `953204ee4d12` | 271 | 当前快照 |
> | EV | `PMO/audit/内容审查Agent-行业证据矩阵-v1.md` | `34fda3a04909` | 380 | **v1.2 已最终停写**（2026-10-18） |
>
> **引用规则**：正文一律先写**章节号**，再用 `缩写@短hash` 校准；行号只作辅助。
> 上游 P/T/A 已于 S-1（2026-10-18）重冻。**引用一律带 `@短hash`；行号随快照变，不得当现值。**

---

# 0. 总览与边界

## 0.1 一句话

阶段一交付一个**模块化单体**：飞书群负责提交与通知，Web 复核工作台负责人工动作，静态报告作为不可变存档，多维表只做批量入口与只读状态投影；所有判定由后端域模块计算，Web 不重算、不直写权威。

## 0.2 交互面职责 [已定]

| 交互面 | 职责 | 不做什么 |
|---|---|---|
| **飞书群** | 提交入口、一句话结论 + 报告链接、回执、申诉入口 | 不承载详情、审批、签发、逐条展开 |
| **Web 复核工作台** | 审核 / 法务复核、队列、申诉、签发/撤回、下线任务、通知收件箱、规则只读 | 不重算判定、不直写规则权威、不自动放行 |
| **静态报告** | 不可变存档：六区块、覆盖证明、回执号、指纹、签名链接 | 不承载操作、不原地修改 |
| **多维表** | 批量提交入口、只读状态投影 | 不做状态回写、不做审批、不做权限面 |

依据：R@9be0c9f7e2fb:937/949/951、P@ff51fc87f5aa:941-945/979/993-995、T@d3093e2d4d9d:1092/D-2、ADR-0013:123（历史“不做前端”已被用户“建设完整工作台”决策取代）。

## 0.3 系统状态 vs 人工动作 [已定]

- **人工业务动作只经 Web 工作台**；群/多维表不直接写 `release_status` 与人工结论。
- **系统自身的审查状态/任务状态由后端状态机变更**（受理、排队、解析、判定、重试、超时、死信、失效、重审入队），不依赖 UI。

---

# 1. 产品角色与权限

## 1.1 角色表 [已定]

| 角色 | 职责 | 可见范围 | 关键约束 |
|---|---|---|---|
| 投放侧（DP0） | 不可判内容 / 下线执行 owner | 自己的提交与任务 | 无签发权 |
| 文案提交人（DP1） | 提交、待自决处理、申诉发起 | 仅自己的 submission/case/report | 不得签自己的案件 |
| 内容审核员（DP3） | 人工复核、申诉受理 | tenant + product_line + assigned/actionable | 不得签自己复核的案件 |
| 法务（DP4） | 终审、规则语义 Owner、冲突裁定 | tenant + product_line + assigned/actionable | 签发需人级授权 |
| 签发人 | 受控签发/撤回 | 授权 scope 内 | 独立 allowlist；SoD |
| 项目统筹 | 超时升级、全局协调、改派 | 本租户 scope-all | 不自动获得签发权 |
| IT 管理员 | 身份/运维元数据、grant 执行 | 仅元数据 | 默认不可读内容 |
| 机器 / Agent | 输出五标签、执行任务 | 仅既定 API 能力 | **无签发/撤回权** |

依据：R@9be0c9f7e2fb:916（上游 5 角色）、P@ff51fc87f5aa:832-836（处置层）、ADR-0005:62-65（人的字段 Agent 只读）、ADR-0008:113-122（规则语义法务）、ADR-0012:391-399（品线归属产品）。

## 1.2 Capability 清单 [已定]

| Capability | 含义 | 授权方式 |
|---|---|---|
| `case.review` | 复核案件 | 角色 + scope |
| `appeal.handle` | 受理申诉 | 角色 + scope |
| `release.sign` | 签发 | 人级 allowlist + tenant/product_line + SoD |
| `release.revoke` | 撤回 | 人级 allowlist + tenant/product_line |
| `takedown.execute` | 执行下线 | 人级 allowlist + platform/tenant/product_line |
| `takedown.waive` | 豁免下线 | 人级 allowlist + 双人审批 |
| `rule.request_change` | 规则变更申请（阶段一只读，暂无写路径） | — |
| `admin.grant.execute` | 执行授权 | IT |
| `admin.grant.approve` | 二次审批 | 独立审批人 |

## 1.3 对象 ACL [已定]

| 角色 | 可见 | 额外条件 |
|---|---|---|
| 提交人 | 仅自己的 | — |
| DP3 / DP4 | tenant + product_line | assigned / actionable |
| 签发人 | tenant + product_line | 有 `release.sign` + SoD |
| 项目统筹 | 本租户全部 | — |
| IT | 身份/运维元数据 | 默认不可读内容 |
| 机器 | 既定 API | 无内容浏览 |

反向对照：OA-1…OA-11（跨人/跨品线/未指派/跨租户/IT 读内容均 403）。

## 1.4 职责分离（SoD）[已定]

- 提交人不得签自己的案件（`self_submission`）。
- 最终复核人不得签自己复核的案件（`self_review`）。
- grant 提案 / 执行 / 二次审批必须为不同主体。
- 下线 executor 不得作为自己的 waive 审批人。
- 原 signer 可作为 waive 两名审批人之一，但不得是唯一审批人。

## 1.5 授权名单治理 [已定]

### 签发类（`release.sign` / `release.revoke`）

```
法务提案 propose → IT 执行 execute → 第二审批人 approve
  （仅：新增 / 扩大 scope / 授予 release.revoke）
→ 生效 active（tenant + product_line）
```

- 提案人 ≠ 执行人 ≠ 第二审批人。
- 全留痕：提案/执行/审批人、变更前后、时间、理由。
- grant 撤销后：既有 signature 保持有效；被撤销 grant 的 principal 不能新签；原 signer 仍可撤回自己的历史 signature（例外，不依赖当前 grant，需 step-up + reason + audit）。

### 下线类（`takedown.execute` / `takedown.waive`）

```
投放 owner 提案 → IT 执行 → 第二审批（新增 / 扩大 scope）
→ 生效 active（platform + tenant + product_line）
```

- **人级 allowlist**；无默认 wildcard；跨任一 scope → 403。
- `takedown.waive` 使用需**两名不同的、具备匹配 scope 的审批人**；executor 不可自批；原 signer 可为两名之一但不得唯一；reason + evidence 必填。

---

# 2. 端到端用户旅程

## 2.0 契约总则 [已定]

| 项 | 口径 |
|---|---|
| `ContentUnit v1` | **只由 `normalizer` 产出**（worker 内、orchestrator 第①步）；`submission_router` 只校验/转交，不产单元、不写 IR |
| `ReviewIR` | 运行级唯一真相，由 `orchestrator` 在运行末组装、`artifact_store` 落盘；**Web/报告只读 ReviewIR**，不得改 IR、不得从 UI 推导判定 |
| `fetch_error` 无正文的稳定 id | **S-3 已 closed（2026-10-18，定义/登记）**：`unit_id = sha256(source.kind ‖ 0x1F ‖ normalized_locator)`，不含时间桶；`attempt_id` 单列；消费者同步清单见工作流 §S2.8 |
| 设计 vs 实现 | 以上均为设计口径；P1 未实现，P-1/G-2/G-3/G-4/G-5/G-6 仍 open |

## 2.0.1 五步 ↔ S0–S9 映射 [已定]

| 五步（Playbook §2） | 本文阶段 | 说明 |
|---|---|---|
| ① normalize | S2 | `normalizer` 唯一产出 ContentUnit |
| ② judge | S3 + S4 | 规则/语义/依据 → DraftFinding → ValidatedFinding 落盘 |
| ③ dispose | S5 + S6 | coverage_composer → decision_table → disposition_router |
| ④ output | **S8a 初次 / S8b 事件触发** | S8a：worker 运行末组装 ReviewIR、renderer/store/send；S8b：仅由“改变 finding”或“五类失效重审”事件触发新 run 后的输出 |
| ⑤ evaluate | S9 | metrics_read_model / reviews_ledger / regression_gate |
| 入口 | S0 | submission_router + Attempt |
| 调度 | S1 | job_dispatcher + run_record |
| 人工/申诉/签发/失效 | S7 | 人驱动 + 事件驱动；**不是五步之一** |
| 横切 | S10 | 失败/未测/幂等/审计/原子提交 |

**第一阶段硬约束**：每条内容**跑完全部适用控制点**，无提前停、无回边；S7 的人工动作产生**新的 run / 新 IR / 新报告**，不修改旧 IR，也不构成流水线回边。

**事件分类（v1.3.1）**：只有**改变 finding** 或**触发五类失效重审**的事件才开启**新 run / 新 ReviewIR / 新报告**；`sign` / `revoke` / 申诉状态变化**不开启新 run**（`revoke` 若引发 `invalidated`，则走失效重审链路）。同一次 run 内，**S8a 初次输出发生在 S7 人工复核之前**（worker 先出报告/群消息）；S7 之后只有上述两类事件才由 **S8b 事件触发**输出。因此 S8/S7 不是同一次 run 的顺序颠倒，也不构成回边。

## UJ-1 提交 → 结论 → 报告 [已定]

1. 群内 @Agent 或 Web 提交单提交（文字/图片/视频/链接/文件）。
2. 服务端生成 `Attempt`（accepted / rejected_unsupported / failed），返回受理回执。
3. 异步 worker 执行 normalize → judge → dispose → output → evaluate。
4. 产出五标签结论（BLOCK/REVIEW/未审查/待自决/PASS），群内一句话 + 报告链接。
5. 报告为不可变静态存档，含六区块、覆盖证明、回执号、指纹。
6. 回执号可查，申诉入口可用。

## UJ-2 人工复核 [已定]

1. DP3/DP4 在工作台队列看到未分配案件（tenant+product_line+role）。
2. `claim` 原子独占（optimistic lock；并发失败 → 409）；lease 30 分钟无活动自动 expire/unclaim，释放前保存 draft。
3. 复核详情：结论、findings、覆盖证明、依据、回执、时间线。
4. **Draft handoff**：
   - 新 assignee 可**只读**查看前任 draft / note / evidence，含 author 与 time；
   - 原稿 immutable；新 assignee 必须**显式 adopt** 一份 primary draft 才能复制为新 draft，记录 `derived_from` + adopter + time；
   - 其他 draft **仅可显式引用片段/字段**，记录 `source_draft_id + field_path + fragment`；**不自动 merge**；
   - 字段冲突由新 reviewer 人工裁定，UI 并列展示，不静默取最后一个；
   - 系统只**推荐 latest**（视觉标记），不预选、不自动 adopt；selection/reference 均写审计。
   - **autosave**：表单字段 + notes + evidence selections + references **全量自动快照**；每次快照记录 `snapshot_seq / snapshot_at / content_hash / author`；防抖频率与保留期待拍；**只有 explicit submit review conclusion 才进入 formal finding/decision**；autosave 不得触发 finding/decision/report。
5. 提交结论（放行/改写/拦截），写回执与审计；回流知识库。

## UJ-3 申诉 [已定]

1. 提交人通过回执回复或 Web 发起申诉；案件号 = 回执号。
2. DP3 受理，2 个工作日 SLA（D-5）；撤销需书面理由。
3. 依据冲突升级 DP4。
4. 失效时：旧版本申诉 pause（`version_invalidated`），不自动关闭/迁移。
5. 全量重审完成后，原申诉人确认迁移到新版本；30 天未确认 → `stale`（停止提醒、不关闭、记录长期保留），仍可后续 migrate 或对新版本重新申诉。

## UJ-4 签发 / 撤回 [已定]

1. 待放行案件 → `GET /release/pending`（按 capability + scope + SoD 过滤）。
2. 查看 `release-readiness`：按标签/处置义务返回四前置/义务完成度。
3. 发起 sign/reject → **step-up 飞书 SSO re-auth** → `step_up_token`（5m、single-use、绑定 principal+case+action+nonce）。
4. 服务端校验：权限、租户、乐观锁、四前置、双指纹、幂等、审计。
5. 结果：`signed` / `rejected`；原 signer 或 `release.revoke` 授权人可撤回（reason+step-up+audit）。
6. **自动失效输入**（任一变化即 `invalidated`，无人工确认/override）：
   - content fingerprints（raw_sha256 / text_sha256 及已纳入的媒体指纹）；
   - rule_snapshot（版本 + 内容指纹）；
   - kb_snapshot（版本 + 内容指纹）；
   - **本次审查实际使用过的** authority_ref versions；
   - conflict-table version。
   未使用过的 authority_ref 变化**不触发**失效。每次失效记录 `old/new versions + change_set`；同一窗口多项变化合并为一个事件。
7. **Signature binding**：签发记录必须绑定并记录
   `case_version / ir_id / ir_version / raw_sha256 / text_sha256 / rule_snapshot(version+hash) / kb_snapshot(version+hash) / used_authority_refs[{ref_id,version}] / conflict_table_version / frame_manifest_hash / keyframe_set_hash / ocr_output_hash / asr_output_hash / model_config_hash / sampling_config_hash / media_fingerprints_root_hash / signature_version / signer / signed_at / step_up_ref / decision / reason`。
   签名记录不可变；重新签发 = 新记录 + `derived_from`。
   **媒体 root hash 算法**：每个 item → **RFC 8785 JCS** → **UTF-8 canonical bytes** → **SHA-256**；按 `(kind, stable_id)` **稳定排序**生成 manifest → 对 canonical manifest 再 SHA-256。**Node / TypeScript / Python 必须使用同一 golden vectors 对拍**，同一输入必须得到同一 root。明确：**不是 Merkle tree，不是不可篡改**，只是确定性摘要。
8. 自动失效 → **自动创建 full-review job 并入队**（同一 invalidated 事件只建一个 job）→ 全量重审（全部适用控制点 + 模态提取 + 依据同步 + 判定）→ 新 ReviewIR + 新报告 → 回 `pending_release`。旧 IR / 旧报告 / 旧签发记录全部保留、不可改删。
9. 重审 job 调度：同 case 只允许一个 active job。queued job 合并 change_set；running job 快照不可变，新变化建 successor，串行等待。

## UJ-5 下线任务 [已定]

1. revoke/invalidated 且内容已发布 → 自动创建下线任务；未发布 → `not_applicable`，不创建。
2. 默认 assignee = 投放侧 owner；review owner 监督；coordinator 可 reassign。
3. `takedown.execute` 需匹配 **platform + tenant + product_line**（Amazon ≠ TikTok）；跨任一 scope → 403。
4. 提醒：
   - `pending` / `in_progress`：**每日一次**给 assignee + 投放侧 + 审核负责人；去重键 `task_id + 北京日期`；
   - 状态变化（start/complete/fail/waive）：**即时**通知；去重键 `event_id`；
   - `completed/failed/waived` 停止每日提醒。
5. **无硬 deadline**：不设 `due_at`、不做超时升级；持续显示年龄（age_days/hours）、状态、提醒次数、积压；**不得**把“无期限”显示成绿色“正常/未超时”。
6. 完成回填（`complete` 前校验，缺一 → 400）：
   - 必填：`platform / executed_by / executed_at`（executed_at 不得晚于当前）；
   - `receipt_id` 或**可访问的** `result_url` 至少一个；
   - 平台两者都不提供时，`screenshot` 可替代；
   - 截图落仓外数据根 0700、记录 sha256，不进公开仓。
7. 失败 → 即时通知/升级项目统筹 + 法务；允许 `retry`（保留历次尝试）/ `reassign`（新旧通知 + 审计）/ `waive`。
8. `waive`：**两名不同的、具备匹配 scope 的 `takedown.waive` 审批人**；executor 不可自批；原 signer 可为两名之一但不得唯一；reason + evidence 必填；审计记录两名审批人、scope、时间。

## UJ-6 批量 [已定]

- 多维表/URL 列表提交 → 任务 ID → 逐行状态 → 汇总 → 报告索引。
- 多维表只读投影，不做状态回写。

## UJ-7 通知 [已定]

- 失效/自动重审：**仅 Web 工作台 in-app**（inbox/unread/read_at/ack），不发飞书/个人/群；文案只能说“已产生工作台通知”，不得说“已送达”。
- 下线任务：每日 + 状态变化主动通知（飞书），不受 in-app 口径影响。
- 所有对外发送走 outbox；飞书无幂等键，按来源 at-most/at-least（T@d3093e2d4d9d:381-422）。

---

# 3. 信息架构

## 3.1 站点地图 [已定]

```
/                      → 重定向到 /inbox
/login                 → 飞书 OAuth/SSO
/inbox                 → 我的待办（按角色过滤）
/cases                 → 案件列表（筛选：标签/品线/渠道/时间/负责人）
/cases/:caseId         → 案件详情（结论/findings/覆盖/依据/回执/时间线）
/queue                 → 复核队列（DP3/DP4）
/appeals               → 申诉列表
/appeals/:appealId     → 申诉详情
/release               → 待签发列表
/release/:caseId       → 签发页（G-1）
/takedown              → 下线任务列表
/reports               → 报告索引（只读）
/reports/:reportId     → 报告详情（静态存档渲染）
/rules                 → 规则/控制点/路由（只读）
/admin/grants          → 授权名单（提案/执行/审批）
/admin/sessions        → 会话与安全审计（IT）
```

- 不设独立 metrics dashboard（P-12 阶段一不做）。
- 路由带 capability metadata；前端隐藏/403 只是体验，**服务端仍强制**。

## 3.2 导航 [已定]

- 左侧主导航：Inbox / Cases / Queue / Appeals / Release / Takedown / Reports / Rules / Admin。
- 顶栏：租户/品线切换（有权限时）、通知铃、用户菜单（登出）。
- Admin 仅 IT/授权人可见。

---

# 4. 页面与组件

## 4.1 页面清单 [已定]

| ID | 页面 | 关键内容 | 状态覆盖 |
|---|---|---|---|
| P-01 | 提交单 | 内容阶段/品线/渠道（三必填）、通道选择、附件说明 | 空/校验失败/不支持通道/提交成功/受理回执 |
| P-02 | 我的内容 | 列表、状态、待自决、修改重提 | 空/加载/失败/已终态只读 |
| P-03 | 案件列表 | 五标签筛选、品线、负责人、时间 | 空/加载/失败/权限过滤/未测 |
| P-04 | 案件详情 | 结论、findings、覆盖证明、依据、回执、时间线 | 未测/部分覆盖/冲突/过期/无权限 |
| P-05 | 复核队列 | 分派、claim、lease、批量、下一动作 | 空/超时/升级/冲突/lease 失效 |
| P-06 | 申诉列表/详情 | 案件号=回执号、时限、撤销理由、结果、pause/migrate/stale | 空/超时/已撤销/升级 DP4/version_invalidated |
| P-07 | 待签发/签发页 | 四前置、双指纹、sign/reject、step-up | 指纹不一致/条件缺失/无权限/已签发/失效 |
| P-08 | 下线任务 | 年龄/状态/提醒/积压、执行/回填/重试/豁免 | pending/in_progress/completed/failed/waived/no_deadline |
| P-09 | 报告索引/详情 | 六区块、搜索、失效/重签 | 空/过期/无权限/重建中 |
| P-10 | 规则/控制点/路由 | 只读列表、版本、生效范围 | 只读/无权限 |
| P-11 | 授权管理 | 提案/执行/审批/撤销、scope、审计 | 待审批/生效/已撤销/SoD 拒绝 |
| P-12 | 会话与安全审计 | 登录/撤销/失败事件、access-log | 无权限/只读 |

**移除**：独立 metrics dashboard（阶段一不做）。

## 4.2 组件 [已定]

- 基础：Radix primitives（dialog/dropdown/tabs/tooltip/toast…）+ 自有 tokens/components。
- 表格：TanStack Table（headless）+ 虚拟滚动。
- 表单：React Hook Form + Zod。
- 状态组件：空 / 加载 / 错误 / 403 / 冲突 / 过期 / 未测 / 部分覆盖 / unsupported。
- 群卡片：五标签卡（C-01）；卡片白名单与上限按 R@9be0c9f7e2fb:1382-1388、P 卡合同。
- 报告：静态 md 只读渲染；Web 不改报告。

---

# 5. 完整状态矩阵

## 5.1 审查案件状态 [已定]

| 状态 | 触发 | UI 表现 | 可执行动作 | 禁止 |
|---|---|---|---|---|
| 草稿 | 提交前 | 可编辑 | 保存/提交 | 计入统计 |
| 已受理 | 入站成功 | 受理回执 + 排队 | 查看 | 显示结论 |
| 解析中/判定中 | 异步任务 | 处理中 | 查看/取消（批量） | 显示五标签 |
| 待人工 DP3 | 规则/语义转人 | 队列 + 负责人 + lease | 复核/退回/升级 | 机器代结论 |
| 待法务 DP4 | 依据冲突/规则争议 | 法务队列 | 终审/退回 | 机器终结 |
| 待自决 DP1 | 干净候选 | 通知提交人 | 修改重提/接受 | 显示“通过/已放行” |
| 不可判 DP0 | 无文案格式 | 未审查 + 原因 | 补材料/人工处置 | 机器终结 |
| 未审查 | 工具失败/未跑 | 未测徽标 + 原因 | 重试/人工 | 与“缺失”合并 |
| 部分覆盖 | 浅档 | coverage=partial 徽标 | 查看未跑项 | 显示 PASS |
| 完成 BLOCK | 规则/人工 | 结论卡 + 回执 + 申诉入口 | 查看/申诉/修改重提 | 自动发布 |
| 完成 REVIEW | 转人 | 结论卡 + 指派 | 复核 | 自动发布 |
| 完成 PASS | 条件满足 | 结论卡 + `release_status=待放行` | 人签发 | 机器写已放行 |

## 5.2 申诉状态 [已定]

| 状态 | 含义 | 允许转移 |
|---|---|---|
| open | 已受理 | → paused / resolved / withdrawn |
| paused (version_invalidated) | 旧版本失效暂停 | → migrated / stale；不得受理/驳回/关闭 |
| migrated | 原申诉人确认迁移 | 终态（可追溯） |
| stale | 30 天未确认 | 仍可 migrate 或新申诉；不关闭 |
| withdrawn | 撤销（书面理由） | 终态 |
| resolved | 成立/驳回 | 终态 |

## 5.3 签发状态 [已定]

| 状态 | 含义 | 允许转移 |
|---|---|---|
| pending_release | 待放行 | sign → signed；reject → rejected |
| signed | 已签发 | revoke → revoked；自动失效 → invalidated |
| rejected | 已拒绝 | 提交人修改 → resubmitted → 审查流程 |
| revoked | 已撤回 | 终态（如需再发，走重审/重签） |
| invalidated | 已失效 | 自动入队全量重审 → 重审完成 → pending_release |

## 5.4 下线任务状态 [已定]

| 状态 | 含义 | 允许转移 |
|---|---|---|
| pending | 待执行 | in_progress / waived |
| in_progress | 执行中 | completed / failed |
| completed | 已完成（回填证据齐全） | 终态 |
| failed | 失败 | retry / reassign / waive |
| waived | 豁免（双人审批 + 理由 + 证据） | 终态（是否可撤销待拍） |

## 5.5 通用状态 [已定]

- 权限拒绝 403：明确页面 + 申请入口，不得空页/假装成功。
- 冲突：两条依据并排展示，人工裁定，不静默取一个。
- 过期：依据/链接过期横幅 + 重签/重拉。
- 未测：独立徽标；不得显示为 0 或通过。
- unsupported：显式说明 + 替代做法，不得从列表消失。

## 5.6 五标签 × 处置层 × 案件状态映射 [已定]

> **唯一判定仍在后端 `decision_table`**；下表只用于 UI 展示与路由说明，前端不得据此推导或改判。

| 对外五标签 | 处置层 | 典型 case 状态 | 能否终结审查标签判定 | UI 可执行动作 | release_status |
|---|---|---|---|---|---|
| **BLOCK** | DP2 工具预审 | 完成 BLOCK | **可终结审查判定（不可放行）** | 查看 / 申诉 / 修改重提 / 人工 release-decision（reason 必填） | 待放行 |
| **REVIEW** | DP3 人工复核（冲突时 DP4） | 待人工 / 待法务 | 不可 | 复核结论 / 指派 / 升级 | 待放行 |
| **未审查** | DP0 不可判 | 不可判 / 未跑 / 失败 | **不可**（ADR-0012:209/231） | 补材料 / 人工处置 / 重试 | 待放行 |
| **待自决** | DP1 业务自审 | 待提交人处理 | **不可**（ADR-0012:213） | 提交人修改重提 / 接受 | 待放行 |
| **PASS** | DP2 附注放行（命名待主合同核） | 完成 PASS | **可输出标签（不可放行）** | 人 `release-decision` | 待放行 |

> **命名说明**：DP2 的“附注放行”沿自主合同旧命名，易与 `release-decision`（签发/放行）混淆；本文只登记“待主合同修订”，不在本文件改其语义。机器对 BLOCK/PASS 均**不可放行**。

**说明**：
- 五标签是审查输出；`release_status` 恒「待放行」，只有人经 `release-decision` 改变发布状态（P@ff51fc87f5aa:137-139、P@ff51fc87f5aa:1014、A@432f4a2c073d:129、R@9be0c9f7e2fb:684-687、ADR-0012:228-230）。
- DP0/DP1 机器终结冲突：本表按 ADR-0012（不可终结）；`agent-skills/内容合规审查/SKILL.md:65-66` 仍写“可终结”，属 C-1 待修文档冲突。

---

# 6. 设计系统与无障碍

## 6.1 组件基础 [已定]

- Radix primitives 提供可访问行为；自有 tokens/components 负责视觉。
- shadcn 仅可借鉴代码组织，**不是运行依赖**；不得无脑生成。
- TanStack Table 负责表格逻辑；Radix 负责 dialog/dropdown/tabs 等交互。

## 6.2 Token 最小集 [已定]

- 语义色：success / warning / danger / neutral / untested / info。
- 字号阶梯、间距阶梯、圆角、阴影、焦点环。
- 五标签不得只靠颜色：文字 + 图标/形状。
- 组件内不得硬编码色值/间距（除 token 定义处）。

## 6.3 无障碍 [已定]

目标：**WCAG 2.2 AA**。

| ID | 检查 | 判据 |
|---|---|---|
| AX-1 | axe 自动扫描 | 关键页面 0 critical / 0 serious |
| AX-2 | 键盘全流程 | 队列/详情/签发/申诉可纯键盘完成 |
| AX-3 | 读屏 | VoiceOver 可读出结构、标签、错误、状态 |
| AX-4 | 焦点可见 | 所有可交互元素有可见焦点环 |
| AX-5 | 对比度 | 正文 ≥4.5:1，大字 ≥3:1，非文本控件 ≥3:1 |
| AX-6 | Target size | ≥24×24 CSS px 或足够间距（2.5.8） |
| AX-7 | Drag alternative | 拖拽必须有单指针/按钮替代（2.5.7） |
| AX-8 | Accessible authentication | 登录不要求认知测试；支持密码管理器/粘贴/SSO（3.3.8） |
| AX-9 | 错误识别 | 错误文字 + 字段关联，可被读屏读出 |
| AX-10 | 状态/五标签 | 不只靠颜色 |

## 6.4 响应式 [已定]

- 最小正式视口 **1280×720**；更大自适应；更小不保证。
- **400% zoom / 320 CSS px reflow 仍按 WCAG 2.2 AA**（1.4.10），表格等 2D 内容除外。
- 正式支持浏览器：**桌面 Chrome 最近两个 major**；Edge/Safari/mobile 非正式支持。

---

# 7. 前端技术规格

## 7.1 栈 [已定/候选]

| 项 | 选择 | 状态 |
|---|---|---|
| 框架 | React 19 | 已定；exact 版本 [候选] |
| 语言 | TypeScript | 已定 |
| 构建 | Vite | 已定 |
| 包管理 | pnpm（packageManager exact + pnpm-lock.yaml + corepack + frozen-lockfile） | 已定；exact 版本 [候选] |
| 路由 | TanStack Router（typed params/search + route capability metadata） | 已定；exact 版本 [候选] |
| 服务端状态 | TanStack Query | 已定；exact 版本 [候选] |
| 表格 | TanStack Table（headless） | 已定；exact 版本 [候选] |
| 组件基础 | Radix primitives + 自有 tokens/components | 已定 |
| 测试 | Playwright + axe | 已定；exact 版本 [候选] |

## 7.2 前端约束 [已定]

- Query keys 按 `tenant + resource + id + filters`；mutation 后失效相关查询。
- 轮询 2–5s，终态停止，页面不可见时降频。
- 401/403/409/网络错误映射明确 UI 状态。
- 500 行表格启用 virtualization；服务端权威排序字段不得仅客户端排序。
- 路由 capability 仅作展示；服务端仍强制。
- 禁止 shadcn 运行依赖；禁止硬编码色值/间距。
- 禁止出现独立 metrics dashboard（阶段一）。

## 7.3 前端开发门 [门]

- FE-1：React 19 / TS / Vite / Router / TanStack / Playwright / axe 兼容矩阵全绿。
- FE-2：`packageManager` exact、`pnpm-lock.yaml` 入库、`--frozen-lockfile` 可复现。
- FE-3：无 `package-lock.json` / `yarn.lock`。
- FE-4：WCAG 2.2 AA 自动 + 人工检查通过。
- FE-5：1280×720 与 400% zoom reflow 验收通过。

---

# 8. 后端技术规格

## 8.1 栈 [已定/候选]

| 项 | 选择 | 状态 |
|---|---|---|
| 语言 | Python 3.12（>=3.12，3.9 禁止作为开发运行时） | 已定；exact patch [候选] |
| 包管理 | uv + pyproject.toml + uv.lock + locked sync | 已定 |
| API | FastAPI + Pydantic + OpenAPI 3.1 | 已定；exact 版本 [候选] |
| 架构 | 模块化单体 | 已定 |
| DB | SQLite WAL（投影）+ 独立 session.db | 已定；迁移门 [门] |
| 权威 | 文件 + manifest 唯一真相 | 已定 |
| 部署 | Docker Compose | 已定；生产兼容 [门] |

## 8.2 服务边界 [已定]

| 服务 | 职责 | 不做什么 |
|---|---|---|
| ingress（Node，复用 ws_daemon） | 飞书长连接、durable inbox、事件去重、提交入口 | 不归一化、不判定 |
| review-api（Python FastAPI） | 工作台读 API、人工动作写 API、OpenAPI、RBAC、审计 | 不跑判定、不写 IR 本体 |
| worker（Python 一次性子进程） | orchestrator 五步、产出 ReviewOutput | 不写 run_record、不发送 |
| report-store（Node） | 静态报告、签名链接、索引 | 不渲染、不改内容 |
| scheduler（Node） | SLA/提醒/retention/outbox 对账/失效检测 | 不判状态、不发消息 |
| static | 只读报告文件服务 | 不做渲染 |

**禁止**：在 API 内重算 decision_table/coverage/evidence；禁止 API 直接写权威文件（写经域模块/artifact_store）。

## 8.3 认证与会话 [已定]

- prod：飞书 OAuth/SSO；principal = `tenant_id + open_id`。
- dev：受限本地账号/模拟身份；生产启动/请求一律拒绝。
- Session：服务端 SQLite（独立 `session.db`）；cookie 只含 opaque random id；HttpOnly/Secure/SameSite。
- idle 30m / absolute 8h；服务端可撤销；撤销立即 401。
- CSRF：所有状态变更请求校验 token。
- Session 丢失/恢复：所有 session + step-up 失效 → 重新登录；不影响 IR/manifest/projection。
- Step-up：sign/revoke 前飞书 SSO re-auth；`step_up_token` TTL 5m、single-use、绑定 principal+case+action+nonce；成败审计；跨案/跨动作/重放拒绝。

## 8.4 数据模型（逻辑）

```
tenants, principals, roles, role_bindings,
submissions, attempts (outcome/failure_kind/reason/ir_id),
jobs (run_record: attempt/outcome/exit_code/stdout_sha256/stderr_sha256),
cases, findings, receipts, review_ir_index, render_snapshots,
drafts (draft_id, case_id, author_id, content, content_hash, status,
        derived_from, adopted_by, adopted_at,
        references[{source_draft_id, field_path, fragment}]),
appeals (status: open|paused|migrated|stale|withdrawn|resolved,
         version_invalidated_at, migration_confirmed_at, stale_at),
appeal_events,
release_signatures (signature_id, signature_version,
        case_id, case_version, ir_id, ir_version,
        raw_sha256, text_sha256,
        rule_snapshot_version/hash, kb_snapshot_version/hash,
        used_authority_refs[{ref_id, version}], conflict_table_version,
        frame_manifest_hash, keyframe_set_hash, ocr_output_hash, asr_output_hash,
        model_config_hash, sampling_config_hash, media_fingerprints_root_hash,
        signer_id, signed_at, step_up_ref, decision, reason),
invalidation_events (event_id, case_id, occurred_at,
        change_set[{field, old_version, new_version, old_fingerprint, new_fingerprint, source}],
        review_job_id),
takedown_tasks (task_id, case_id, content_id, platform,
        assignee_id, review_owner_id, status,
        created_at, age, last_reminded_at, reminder_count, reminder_dedupe_key,
        attempt_count, failed_at, failure_reason,
        backfill{platform, executed_by, executed_at, receipt_id, result_url, screenshot_ref, screenshot_sha256},
        waiver{waived_by, approver_1, approver_2, reason, evidence, approved_at}),
notifications (recipient, type: invalidation|auto_rereview,
        unread, read_at, acked_at, payload),
signer_grants / takedown_grants (grant_id, tenant_id, product_line, platform?,
        user_id, capability, status, proposed_by, executed_by, approved_by,
        reason, effective_from, effective_to, version),
sessions, step_up_tokens (token_id, principal, case_id, action, nonce,
        expires_at, consumed_at, audit_ref),
audit_ledger (monthly JSONL + prev_month_tail_hash + chain),
access_log (monthly JSONL + chain),
metrics_snapshots, control_points, routing, rule_class_switches, authority_conflicts
```

## 8.5 存储与事务 [已定]

- **文件 + manifest 是唯一真相**；DB 仅投影。
- P-1 原子提交：staging → rename 到最终不可变路径 → 写 manifest.tmp → fsync → rename manifest（唯一可见提交点）。
- 崩溃恢复四态：committed / orphan / uncommitted / garbage（T@d3093e2d4d9d:333-344）。
- 投影写者唯一；启动/定时从 manifest 幂等重建；重建后与 manifest 对拍。
- **权威提交后 DB 失败**：不回滚权威、不返假成功；返回 `202 + projection_lag + authority_snapshot + reconcile_token`；read-your-write 用权威快照。
- SQLite：WAL、busy_timeout、短事务、单写者。
- Postgres 迁移门：写锁 p95 / 并发写者 / DB 体积 / 多主机；阈值压测后锁，不预承诺。

## 8.6 Jobs / outbox / inbox [已定]

- 每 case 唯一 active review job（串行，不并行）。
- queued job 可合并 change_set；running job 快照不可变；新变化建 successor，等待当前结束。
- 入队幂等键：`invalidated_event_id` 或 `case_id + signature_id + change_set_hash`。
- 入站：`events-inbox.jsonl` + fsync + `event_id` 去重 + cursor；进程不在时事件仍会丢（明写）。
- 外发：outbox + `logical_delivery_id`；卡片与降级文本共用；按来源 at-most/at-least。
- 失效自动入队，无人工确认/override；event + job 原子写。
- **失效输入**（任一变化 → invalidated + full review）：content fingerprints、rule_snapshot、kb_snapshot、**本次使用过的** authority_ref versions、conflict-table version；未使用的 authority_ref 变化不触发。
- **签名绑定**：见 §8.4 `release_signatures`；任一绑定字段变化触发失效；签名不可变，重签 `derived_from`。
- **重审 job**：queued 合并 change_set；running 快照不可变，新变化建 successor；同 case 串行不并行。
- **投影一致性**：权威提交后就绪；投影失败 → 202 + `projection_lag` + `authority_snapshot` + `reconcile_token`，不回滚权威、不假成功。

## 8.7 API 目录（草案）

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | `/api/v1/submissions` | 提交（群/表/Web 同路由） |
| GET | `/api/v1/cases` | 案件列表 |
| GET | `/api/v1/cases/{id}` | 案件详情 |
| POST | `/api/v1/cases/{id}/claim` | 原子 claim |
| POST | `/api/v1/cases/{id}/unclaim` | 释放 claim（unclaim，区别于发布 release） |
| POST | `/api/v1/cases/{id}/reassign` | 改派 |
| POST | `/api/v1/cases/{id}/actions` | 复核动作（confirm/reject/reassign） |
| GET | `/api/v1/queue` | 复核队列 |
| GET | `/api/v1/appeals` | 申诉列表 |
| POST | `/api/v1/appeals` | 发起申诉 |
| POST | `/api/v1/appeals/{id}/migrate` | 原申诉人确认迁移 |
| POST | `/api/v1/appeals/{id}/withdraw` | 撤销（理由） |
| GET | `/api/v1/release/pending` | 待签发列表 |
| GET | `/api/v1/cases/{id}/release-readiness` | 四前置/义务 |
| POST | `/api/v1/cases/{id}/release-decision` | sign/reject（唯一受控入口） |
| POST | `/api/v1/cases/{id}/release-revoke` | 撤回 |
| GET | `/api/v1/takedown-tasks` | 下线任务列表 |
| POST | `/api/v1/takedown-tasks/{id}/start` | 开始 |
| POST | `/api/v1/takedown-tasks/{id}/complete` | 完成（回填校验） |
| POST | `/api/v1/takedown-tasks/{id}/fail` | 失败 |
| POST | `/api/v1/takedown-tasks/{id}/retry` | 重试 |
| POST | `/api/v1/takedown-tasks/{id}/reassign` | 改派 |
| POST | `/api/v1/takedown-tasks/{id}/waive` | 双人审批豁免 |
| GET | `/api/v1/reports` | 报告索引 |
| GET | `/api/v1/reports/{id}` | 只读详情 |
| POST | `/api/v1/reports/{id}/resign` | 申请重签（不改报告） |
| GET | `/api/v1/rules` | 规则（只读） |
| GET | `/api/v1/control-points` | 控制点（只读） |
| GET | `/api/v1/routing` | 路由（只读） |
| GET | `/api/v1/notifications` | in-app 通知 |
| POST | `/api/v1/notifications/{id}/read` | 已读 |
| POST | `/api/v1/notifications/{id}/ack` | ack |
| GET/POST | `/api/v1/admin/signer-grants` | 签发授权治理 |
| GET/POST | `/api/v1/admin/takedown-grants` | 下线授权治理 |
| GET | `/api/v1/admin/sessions` | 会话/安全审计 |
| GET | `/metrics` | 指标（内部，不做独立页面） |

- 错误模型：`{code, message, details, request_id}`；401/403/409/422 语义明确。
- 写操作带 `Idempotency-Key`。
- OpenAPI 3.1 由 Pydantic 生成；契约测试保证前后端一致。
- **阶段一规则配置只读**：`/rules` `/control-points` `/routing` 只有 GET，**不提供任何写端点**。变更只在权威源完成：
  - 规则：飞书 Base 权威 / pull（ADR-0013 D2a）；
  - 词表：本地权威 / push（D2b）；
  - 控制点 / 路由：本地治理 JSON + 契约评审。
  同步后受影响案件进入失效/重审流程；Web/API 不得直写权威源。

## 8.8 审计与留存 [已定]

- 安全审计：仓外 append-only JSONL + prefix hash chain；按月轮转 + `prev_month_tail_hash`；每日全链校验；长期保留；明确**非不可篡改**。
- 读取审计：独立 access-log JSONL + 月轮转 + hash chain；法务/审计员/IT 所有读取均记录；不写回主 ledger；只记定位信息。
- 媒体 24h（删除前落指纹）；IR 1 年；报告长期；下线任务无硬 deadline。
- L2 敏感：仅指定人；Agent 仅脱敏摘要；报告只引用编号（ADR-0003:40/48）。

## 8.9 后端开发门 [门]

- BE-1：Python 3.12 下全量 verifier/base 兼容。
- BE-2：`pyproject.toml` + `uv.lock`；`uv lock --check`；locked sync；禁止 pip 未锁安装。
- BE-3：OpenAPI 3.1 与 Pydantic 一致；契约测试通过。
- BE-4：域模块 import 白名单；API 内无判定重算。
- BE-5：权威提交后 DB 失败 → 202 + reconcile；投影重建对拍。
- BE-6：session DB 独立、不备份、恢复全失效。
- BE-7：审计 ledger / access-log 链校验、轮转、权限。
- BE-8：Docker Compose 生产兼容门（见 §9）。

---

# 9. 部署拓扑与运行

## 9.1 Docker Compose（阶段一）[已定]

| 服务 | 容器化 | 说明 |
|---|---|---|
| review-api | ✅ | FastAPI |
| scheduler | ✅ | 提醒/retention/outbox/失效检测 |
| web（构建产物） | ✅ | React 静态文件 |
| static | ✅ | 报告只读服务 |
| db（SQLite 文件） | ⚠️ | 不单独起 DB 容器；文件放卷/绑定挂载；单写者 |
| session.db | ⚠️ | 独立文件；不备份 |
| 飞书 daemon | ⚠️ | 建议与 Compose 共存（launchd），独立决策 |
| OCR / ASR | ✅ | 容器内跨平台模型；不再使用 macOS Vision/Speech 生产路径 |

## 9.2 OCR/ASR 候选 [候选]

| 项 | 候选 | 状态 |
|---|---|---|
| OCR 主选 | PaddleOCR（CPU） | 候选；benchmark 后锁 exact 版本 |
| OCR 基线 | Tesseract | 候选 |
| ASR 主选 | faster-whisper（CPU） | 候选；model size + exact 版本待锁 |
| ASR 基线 | 官方 Whisper | 候选 |
| diarization | **阶段一不做**；segment = start/end/text，speaker=unknown | 已定 |
| 算力 | CPU-first；GPU later evaluation | 已定 |
| 性能 | 未压测前不承诺 20s/60s；不达标显式改 NFR 或拍 GPU | 已定 |

## 9.3 Compose 门 [门]

- DC-1 OCR/ASR 容器内可运行（已改线，无 host bridge）。
- DC-2 飞书 daemon 共存/迁移路径确定。
- DC-3 bind mounts 0700 + UID/GID。
- DC-4 SQLite WAL 单写者。
- DC-5 healthcheck + restart。
- DC-6 日志轮转。
- DC-7 备份/恢复（不含 session.db）。
- DC-8 镜像固定 digest。

## 9.4 可观测与容量 [已定/门]

- 结构化 JSONL 日志（run_id/case_id/request_id）。
- 指标：队列深度、处理时延 p50/p95、失败率、SLA、留存任务、积压、最老任务年龄。
- 健康：`/healthz` / `/readyz`，两个 DB 分别报告。
- 告警：飞书（现有）+ 工作台。
- 媒体压测门 MC-1…MC-7：CPU 资源画像、并发、队列 100/500、limits、NFR 校准、不达标决策、GPU 触发。

---

# 10. G-1 签发与撤回（单章）

## 10.1 状态机 [已定]

```
pending_release ──sign──> signed ──revoke──> revoked
       └────────reject──> rejected ──修改重提──> 审查流程

signed ──内容/依据/指纹/冲突变化──> invalidated ──全量重审──> pending_release
```

## 10.2 权限 [已定]

- `release.sign`：人级 allowlist + tenant/product_line + SoD（非提交人、非最终复核人）。
- `release.revoke`：人级 allowlist + tenant/product_line；原 signer 可撤回自己的历史签名（例外，不依赖当前 grant）。
- 机器/前端直写 `release_status` → 禁止；唯一受控入口 `POST /cases/{id}/release-decision`。
- sign/revoke 必须 step-up（5m、single-use、绑定 principal+case+action+nonce）。

## 10.3 Readiness [已定]

`GET /cases/{id}/release-readiness` 按标签/处置义务返回：

| 标签 | 判据 |
|---|---|
| BLOCK | 已修改并重提 / 或人工决定放行（reason 必填） |
| REVIEW | 人工结论已出；并行义务完成 |
| 未审查 | 补审完成或明确豁免（reason 必填） |
| 待自决 | 提交人已处理或人工决定 |
| PASS | 五条件满足；`release_status` 仍待放行 |

共同：双指纹一致、版本一致、无未结申诉（按政策）、无未裁冲突。

## 10.4 验收（摘要）

- RLS-1…RLS-8：机器/前端/越权/指纹/前置/版本/幂等/跨租户。
- INV-1…INV-9：变化触发失效、change_set、全量重审、旧记录不可改。
- RV-1…RV-10：原 signer / revoke 授权人 / 重复/空理由/审计。
- GR-10…GR-18：grant 撤销后既有签名有效、原 signer 历史 revoke 例外。
- SB-1…SB-11：签名绑定字段齐全、不可变、重签 derived_from。
- IA-1…IA-7：自动失效无 override、event+job 原子。

---

# 11. 测试与验收

## 11.1 测试栈 [已定]

- 前端：Vitest + React Testing Library + Playwright + axe。
- 后端：pytest；OpenAPI 契约测试；Pydantic/schema 对拍。
- 故障注入：P-1 六种崩溃点；inbox 去重；outbox 分档；投影重建。
- 性能：k6/locust（API）；媒体压测（MC）。
- 安全：RBAC 矩阵逐格、跨租户、机器 token、L2 访问。

## 11.2 验收 ID 索引 [已定]

> 下表只是分组；**逐 ID 定义/映射见 Appendix A**（每个 ID 一句话判据 + 所在章节）。

| 组 | 覆盖 |
|---|---|
| AU-1…AU-29 | 认证、会话、CSRF、step-up |
| BE-1…BE-8 | 后端装配、契约、域边界 |
| BR-1…BR-12 | 浏览器、视口、zoom reflow |
| DC-1…DC-8 | Compose 部署门 |
| FE-1…FE-7 | 前端栈与锁文件 |
| GR-1…GR-18 | 签发授权治理 |
| IA-1…IA-7 | 自动失效 |
| INV-1…INV-9 | 失效输入与 change_set |
| JQ-1…JQ-7 | 重审 job 合并/串行 |
| OA-1…OA-11 | 对象 ACL / 403 |
| OB-1…OB-7 | OCR benchmark |
| AB-1…AB-7 | ASR benchmark |
| AP-1…AP-15 | 申诉 pause/migrate/stale |
| QC-1…QC-35 | claim / lease / draft |
| RM-1…RM-8 | 下线提醒 |
| RT-1…RT-7 | 前端路由 |
| SB-1…SB-11 | 签名绑定 |
| SD-1…SD-18 | session / 安全 |
| TD-1…TD-21 | 下线任务 |
| TF-1…TF-19 | 下线失败 / waive |
| TQ-1…TQ-8 | Query/Table |
| UX-01…UX-10 | 页面与无障碍原型 |

---

# 12. 已定 / 候选 / 待拍 / 开发门

## 12.1 已定（用户拍板或文档依据）

- 四面职责；完整 Web 工作台。
- React 19 + TS + Vite + pnpm + TanStack Router/Query/Table + Radix。
- FastAPI + OpenAPI 3.1 + Pydantic；Python 3.12 + uv。
- 模块化单体；**Docker Compose 为阶段一生产形态**；SQLite 投影 + manifest 权威。
- Job 串行/合并/successor；outbox/inbox；失效自动入队无 override。
- **失效输入**：content fingerprints / rule_snapshot / kb_snapshot / used authority_ref versions / conflict-table version；未使用 ref 不触发。
- **签名绑定**：case_version、IR id/version、raw/text hashes、rule/kb snapshots、used refs、conflict version、媒体各类 hash + 集合 root hash、signature_version；签名不可变。
- **重审**：invalidated → 新 full-review job（幂等）；queued 合并 change_set；running 建 successor；同 case 串行；全量重审；新 IR/新报告；旧记录不可改删。
- **Draft handoff**：只读查看、显式 adopt 单 primary、其他仅引用不 merge、冲突人工裁定、selection/reference 审计。
- **授权治理**：signer / takedown grant 均为提案→执行→二次审批；人级 allowlist；SoD；无默认 wildcard。
- G-1 完整签发/撤回状态机、capability、SoD、step-up、自动失效、全量重审。
- 下线任务：默认投放侧 owner、review owner 监督、coordinator 改派、三维 scope、无硬 deadline、每日提醒 + 状态即时通知、回填证据、失败升级、双人 waive。
- 通知：失效/重审仅 in-app；下线每日+状态变化飞书。
- 审计：主 ledger + access-log，月轮转 + hash chain，非不可篡改；session 不备份、恢复全失效。
- WCAG 2.2 AA；桌面 Chrome 最近两个 major；1280×720 最小视口。
- 阶段一不做独立 metrics dashboard。
- **证据口径**：有具名第三方部署，但“部署+独立现场效果”= 0（无 L4）；五案例见 §13。

## 12.2 候选（方向已定，版本/参数待锁）

- React / Router / TanStack / Playwright / axe exact 版本。
- pnpm / Node exact 版本。
- FastAPI / Pydantic / uvicorn exact 版本。
- Python 3.12 exact patch。
- OCR：PaddleOCR（主）/ Tesseract（基线）on CPU。
- ASR：faster-whisper（主）/ 官方 Whisper（基线）on CPU；model size 待 benchmark。
- SQLite → Postgres 迁移阈值（压测后锁）。

## 12.3 待拍（v1.1 重算）

> 只列**仍未拍**的；已拍项已移入 §12.1 或各章 [已定]。

| # | 待拍 | 影响 |
|---|---|---|
| Q-01 | 各栈 exact 版本：React 19.x / Router / TanStack / Playwright / axe / pnpm / Node / FastAPI / Pydantic / uvicorn / Python 3.12.x | 兼容矩阵与锁文件 |
| Q-02 | access-log 保留期、谁能读取（IT/审计员/法务） | 审计治理 |
| Q-03 | 下线 waive 两次审批的时效窗口；waive 后是否允许撤销 | TD/TF |
| Q-04 | 下线任务是否设最大重试次数（无硬 deadline，但重试可不限次？） | TD |
| Q-05 | OCR benchmark：样本量、低清/旋转定义、准确率指标与阈值、bbox IoU 口径 | OB |
| Q-06 | ASR benchmark：噪声/多人/长视频定义、WER/CER 阈值、model size、segment 时间码格式 | AB |
| Q-07 | 媒体压测：硬件规格、并发目标、队列配比、不达标优先路径（延长/降采样/改 NFR/GPU） | MC |
| Q-08 | 飞书 daemon 与 Compose 共存还是迁移（Compose 生产形态已定） | DC |
| Q-09 | 是否需要对象存储（S3/MinIO）；当前为本地文件 + 内容寻址 | 部署 |
| Q-10 | 第二审批人（grant）由谁担任；收窄/撤销是否也需第二审批 | GR/TE |
| Q-11 | 指标在 case/queue/report 三处的具体 counts 与 trend 时间窗 | MX |
| Q-12 | 读取 access-log 本身是否也纳入“读取留痕”范围（当前设计为是） | AL |
| Q-13 | 外部证据矩阵中 B3（EU DSA 复核）无直链，需人工核页后定级 | §13 |

## 12.4 开发门总表（未过不得实现）

| 门 ID | 门 | 判据 | 证据 | 状态 |
|---|---|---|---|---|
| G-01 | Python 3.12 兼容 | 全量 verifier/base 在 3.12 下全绿 | BE-1、PY-1…PY-7 | [门] |
| G-02 | uv 锁文件 | `pyproject.toml` + `uv.lock`；`uv lock --check`；locked sync；禁止 pip 未锁 | BE-2、UV-1…UV-7 | [门] |
| G-03 | 前端兼容矩阵 | React 19 / TS / Vite / Router / TanStack / Playwright / axe 全绿 | FE-1…FE-7 | [门] |
| G-04 | pnpm 锁文件 | `packageManager` exact；`pnpm-lock.yaml`；`--frozen-lockfile` | PN-1…PN-7 | [门] |
| G-05 | OpenAPI/Pydantic 契约 | OpenAPI 3.1 与模型一致；契约测试通过 | BE-3 | [门] |
| G-06 | 域边界 | API 内无判定重算；import 白名单 | BE-4 | [门] |
| G-07 | 投影一致性 | 权威提交后 DB 失败 → 202 + reconcile；重建对拍 | BE-5、DB-1…DB-7 | [门] |
| G-08 | 权威写入安全 | 文件 + manifest 唯一真相；单写者；崩溃恢复 | P-1、IA-1…IA-7 | [门] |
| G-09 | OCR benchmark | PaddleOCR vs Tesseract；语料/准确率/bbox/延迟 | OB-1…OB-7 | [门] |
| G-10 | ASR benchmark | faster-whisper vs Whisper；WER/CER/时间码/延迟 | AB-1…AB-7 | [门] |
| G-11 | 媒体 CPU 压测 | 资源/并发/队列；不达标改 NFR 或 GPU | MC-1…MC-7 | [门] |
| G-12 | Compose 兼容 | OCR/ASR 容器、daemon、挂载、WAL、健康、备份 | DC-1…DC-8 | [门] |
| G-13 | RBAC/ACL/SoD | 角色矩阵、对象 ACL、签发/下线 grant、SoD | OA/GR/TE/TF | [门] |
| G-14 | G-1 签发链 | readiness/step-up/失效/重审/撤回 | RLS/INV/RV/SB/IA | [门] |
| G-15 | 无障碍与响应式 | WCAG 2.2 AA；1280×720；400% reflow | AX-1…AX-10、BR-1…BR-12 | [门] |
| G-16 | 外部证据 | **每依赖必须有 level + source + 抓取日期**；B3 标 WEAK；无 L4 不外推；不得夸大 | §13、EV `34fda3a04909`（**待最终冻结**） | [门] |
| G-17 | 文档一致性 | **C-1…C-7 全部关闭**（含源文档行号漂移 C-7） | §14 | [门] |

## 12.5 仍 open 的上游门 / 实现状态 [重要]

| 项 | 状态 | 说明 |
|---|---|---|
| **S-3** | `closed`（**仅定义/登记**） | 2026-10-18 T0-02 定稿：`unit_id = sha256(source.kind ‖ 0x1F ‖ normalized_locator)`，不含时间桶；`attempt_id` 单列；消费者同步清单 8 项见工作流 §S2.8。**P-1 原子写入仍 open，不表示实现已上线** |
| P-1 | open | 跨产物原子提交仅有设计，代码未写 |
| G-2 | open | outbox 仅有设计，代码未写 |
| G-3 | open | durable inbox 只覆盖“已推进来的事件”；进程不在时仍丢 |
| G-4 | open | 认证/租户边界；本文件只给设计 |
| G-5 | open | 不可信输入 sandbox 未定 |
| G-6 | open | 外发原文最小化未定 |
| OCR/ASR benchmark | 未做 | PaddleOCR/Tesseract、faster-whisper/Whisper 均为候选 |
| Compose 生产兼容 | 未验 | DC-1…DC-8 全为门 |
| exact 版本 | 未锁 | React/Python/FastAPI/pnpm/Node 等 |
| 外部证据 | 无 L4 | 有部署事实，无独立现场效果 |

> 以上任一项未清，本文不得被读成“可上线”或“已实现”。

---

# 13. 外部证据矩阵

> 口径与 `PMO/audit/内容审查Agent-行业证据矩阵-v1.md`（短 hash `34fda3a04909`，**待最终冻结**）一致。
> **关键结论：具名第三方部署 ≠ 独立效果。** 有具名客户（Hive/Yubo、Checkstep/Trustpilot、TaskUs/Meta 等），但「部署 + 独立现场效果」目前为 **0**。
> 不得写「无第三方案例」；准确说法是「有部署事实，无独立现场效果测量」。

## 13.1 技术依赖证据级别

| 依赖 | 级别 | 说明 |
|---|---|---|
| React 19 / TS / Vite | L1 | 官方文档与成熟生态；无本产品成功案例 |
| pnpm / TanStack | L1 | 官方文档；无本产品成功案例 |
| FastAPI / Pydantic | L1 | 官方文档；无本产品成功案例 |
| Python 3.12 | L1 | 官方发布；本仓兼容待测（门） |
| uv | L1 | 官方文档；锁文件策略待落地（门） |
| SQLite WAL | L1 | 官方文档；本仓并发/卷行为待测（门） |
| Docker Compose（macOS） | L1 | 官方文档；生产兼容待验（门） |
| PaddleOCR / Tesseract | L1 | 开源项目；本仓 benchmark 待做（门） |
| faster-whisper / Whisper | L1 | 开源项目；本仓 benchmark 待做（门） |
| 本仓既有引擎/verifier | L2 | 本仓实测；不可外推为行业效果 |

## 13.2 五案例证据矩阵（可引用，但不得外推）

| # | 案例 | 来源（EV § + URL/定位） | 抓取日期 | 级别 | 可借机制 | 不可外推 |
|---|---|---|---|---|---|---|
| 1 | **Pinterest PinQueue**（DSA 独立审计） | EV §三 B1 · `https://help.pinterest.com/sites/default/files/dsa/Independent-Audit-of-Pinterest-DSA-Redacted-11102025.pdf` | 2026-10-18 | **L3** independent-audit | 600+ 队列；appeals 自动路由；非 solely automated；6 个月申诉窗口；sampling QA；升级 team leads | 审计 PDF redacted；定量仅 spam 口径；**不能证明全内容效果** |
| 2 | **Meta SRT / pIV / VESPA / HERO**（法院专家报告） | EV §三 B2 · `https://storage.courtlistener.com/recap/gov.uscourts.cand.401490/gov.uscourts.cand.401490.2537.3.pdf` | 2026-10-18 | **L3** independent-audit（诉讼文件，非同行评审） | pIV 按 likelihood×virality×severity 排序；极高 severity 即使低 virality 也优先；reviewer 可升级 SME | 零效果数字；是诉讼文件不是独立测量 |
| 3 | **EU Commission DSA 两年复核** | EV §三 B3 · **无直链（WEAK）** | 2026-10-18 | **L3-WEAK**（待人工核页） | 平台自报 + 独立争议机构裁决 + 强制披露 | 推翻率 ≠ 审核准确率；底层仍平台自报 |
| 4 | **AppealMod**（CSCW 2024，Reddit r/pics 4 个月 field experiment） | EV §四 C1 · `https://arxiv.org/abs/2301.07163` | 2026-10-18 | **L3** academic | 结构化申诉摩擦；可解释通知；低信息量/毒性申诉挡在人审前 | 志愿版主 + 封禁申诉；70% 放弃可能挡掉真实误判；非商业内容审核 |
| 5 | **DSA Transparency Database 审计**（CSCW 2025） | EV §四 C2 · `https://arxiv.org/abs/2312.10269` | 2026-10-18 | **L3** academic | Art.17 逐条 SoR；API 逐事件提交；逐条库 vs 报告汇总交叉对账 | 字段平台自由裁量；部分不一致是定义差异；欧盟 VLOP，非母婴品牌 |

> 证据形态说明（照 EV §十三）：Web 证据均未渲染打开；B3 无直链按 WEAK；不得把 L3 机制证据写成 L4 效果证明。

## 13.3 使用约束

1. **没有 L4**：部署 + 独立现场效果 = 0；任何「行业成功案例」表述不得使用。
2. **静态/不可变报告先例 = 0**：五个最强案例中没有一张把静态/不可变报告做成产品特性；本产品的报告不可变性没有行业实践可引用（EV §〇.3）。
3. **vendor-self-report 数字不可当效果**：Hive/Checkstep/Besedo 等自报读数只可写「某供应商自报」。
4. **code-only-unproven 只可叫「候选参考实现」**：PolySafe ≡ OmniGuard（61/68 文件逐字节相同），13 目录 = 10 独立代码库。
5. **法规引用须带版本与证据形态**（DSA Art.17 vs 本地只落 Art.34；Santa Clara 2.0 vs 已过期 1.0）。

---

# 14. 仍未闭合的文档冲突（必须在实现前修）

| # | 冲突 | 证据 | 处理 |
|---|---|---|---|
| C-1 | SKILL 允许机器终结 DP0/DP1 vs ADR-0012 禁止 | SK:65-66 vs ADR-0012:209/213/231/531 | 以 ADR 为准，修 SKILL |
| C-2 | Playbook 报告五区块 vs 六区块 | P@ff51fc87f5aa:967 vs P@ff51fc87f5aa:1019 | 以六区块为准，修 P@ff51fc87f5aa:967 |
| C-3 | 验收 #58 字段缺“原因/修改建议” | A@432f4a2c073d:119 vs R@9be0c9f7e2fb:152/1487 | 修验收字段 |
| C-4 | 角色/权限矩阵三套计数（8/5/6） | R@9be0c9f7e2fb:883/916、DIFF:105 | 以 §1 本文件角色表为准，回写 |
| C-5 | 抽检分层 PRD 两层 vs 验收四层 | R@9be0c9f7e2fb:750-751 vs P@ff51fc87f5aa:1244/A@432f4a2c073d:159 | 以验收四层为准，回写 PRD |
| C-6 | 规则文本“已放开” vs 行为“仍在拦” | R@9be0c9f7e2fb:661-667 | 法务裁定后回写 |
| C-7 | **源文档行号漂移**：P 由 1381→1666 行（`ff51fc87f5aa`）、T 由 1281→1335 行（`d3093e2d4d9d`），旧行号可能指错 | §0 源文档清单 | v1.3.1 已按 S-1 后的 hash 重冻；每次引用校验必须带 `@短hash`，裸行号不得当现值 |

---

# 15. 附：关键引用

> **引用规则（v1.3）**：正文引用一律**先写章节号**，再用 `缩写@短hash` 校准；**行号只作辅助**，不得当现值。
> 当前短 hash：T=`d3093e2d4d9d`、P=`ff51fc87f5aa`、A=`432f4a2c073d`、EV=`34fda3a04909`；**UIUX 自身=待最终冻结**（自指纹采用遮罩算法：把记录自身 hash 的行替换为 `<SELF>` 后算 sha256，不得直接嵌入自身 hash）。
> ⚠️ P/T/A 仍在变动（17:13–17:29 有写入），标“待最终冻结”；冻结前必须重跑引用校验。

- 部署形态：T@d3093e2d4d9d:42-43
- P-1 原子提交：T@d3093e2d4d9d:294-359
- G-2 outbox：T@d3093e2d4d9d:381-422
- G-3 inbox：T@d3093e2d4d9d:426-444
- artifact_store 数据根：T@d3093e2d4d9d:475
- G-1 open：T@d3093e2d4d9d:1071
- G-4 auth/tenant：T@d3093e2d4d9d:1074
- D-2 静态报告：T@d3093e2d4d9d:1092、T@d3093e2d4d9d:1136-1148
- D-4 留存：T@d3093e2d4d9d:1181-1205
- D-5 SLA：T@d3093e2d4d9d:1209-1234
- 五标签/不等于放行：P@ff51fc87f5aa:137-139、P@ff51fc87f5aa:1014、A@432f4a2c073d:129 #68、R@9be0c9f7e2fb:684-687、ADR-0012:228-230
- 报告六区块：P@ff51fc87f5aa:1019
- 群消息一句+链接：P@ff51fc87f5aa:979/995
- 人的字段 Agent 只读：ADR-0005:62-65
- 规则语义法务：ADR-0008:113-122
- 品线归属产品：ADR-0012:391-399
- L2 敏感：ADR-0003:40/48
- NFR：PRD差异对照:104

---

# Appendix A · 逐验收 ID 定义

> 每个 ID 一句话判据；章节号指向本文件对应规则。未实现、未验收。

## A.1 AU（认证/会话/step-up）— §8.3

| ID | 判据 |
|---|---|
| AU-1 | prod 飞书 OAuth 登录，principal = tenant_id + open_id |
| AU-2 | dev 模拟身份在生产启动/请求被拒绝 |
| AU-3 | session cookie 具备 HttpOnly/Secure/SameSite |
| AU-4 | 状态变更请求缺 CSRF → 403 |
| AU-5 | 登出后旧 session → 401 |
| AU-6 | session 过期/空闲超时 → 401 |
| AU-7 | 客户端自报 tenant 覆盖 principal → 403 |
| AU-8 | 跨租户访问对象 → 403 |
| AU-9 | 未认证访问 API → 401 |
| AU-10 | 机器 principal 调用签发 → 403 |
| AU-11 | 空闲 30 分钟 → 401 |
| AU-12 | 会话满 8 小时 → 401 |
| AU-13 | sign 无二次确认 → 400/403 |
| AU-14 | revoke 无二次确认 → 400/403 |
| AU-15 | step-up 超过 5 分钟 → 需重新确认 |
| AU-16 | 服务端撤销 session → 立即 401 |
| AU-17 | 撤销审计含 actor/time/reason/session_id |
| AU-18 | 撤销后继续访问 API → 401 |
| AU-19 | 活动重置 idle，但不重置 absolute |
| AU-20 | sign 无 step_up_token → 403 `step_up_required` |
| AU-21 | token 过期 → 403 |
| AU-22 | token 重复使用 → 403 `token_replayed` |
| AU-23 | 跨案件使用 token → 403 |
| AU-24 | 跨动作使用 token → 403 |
| AU-25 | principal 不匹配 → 403 |
| AU-26 | nonce 不匹配/重放 → 403 |
| AU-27 | step-up 成功/失败均留审计 |
| AU-28 | token 明文进入日志 → 红 |
| AU-29 | step-up 后案件版本变化 → 409，需重新 step-up |

## A.2 BE（后端装配）— §8

| ID | 判据 |
|---|---|
| BE-1 | OpenAPI 3.1 与 Pydantic 模型一致，不手写第二份 |
| BE-2 | API 内出现判定重算 → 红（import 白名单） |
| BE-3 | OpenAPI ↔ Pydantic ↔ 前端客户端契约测试一致 |
| BE-4 | 非 Python 3.12 或未锁安装 → 红 |
| BE-5 | SSO/RBAC：未认证 401、越权 403 |
| BE-6 | queue/appeal/release API 覆盖且符合状态机 |
| BE-7 | 投影落后 → 回退 manifest，不返回旧状态冒充新状态 |
| BE-8 | API 直接写权威文件 → 不存在该路径 |

## A.3 BR（浏览器/响应式）— §6.4、§9

| ID | 判据 |
|---|---|
| BR-1 | Chrome 最近两个 major 全流程通过 |
| BR-2 | 更旧 Chrome 不纳入验收，可提示升级 |
| BR-3 | Edge/Safari/Firefox 不纳入 CI 门禁 |
| BR-4 | 1280×720 布局不破、关键操作可用 |
| BR-5 | 400% zoom / 320px reflow 满足 WCAG 1.4.10（2D 内容除外） |
| BR-6 | 移动端不作为正式验收对象 |
| BR-7 | 1280×720 关键按钮/表单可达 |
| BR-8 | 1366/1440/1920 自适应无内容遮挡 |
| BR-9 | 小于 1280 不纳入正式验收 |
| BR-10 | 1280 + 400% zoom 无二维滚动（表格除外） |
| BR-11 | 缩放后关键操作仍可达、不被裁切 |
| BR-12 | 至少覆盖浏览器缩放路径 |

## A.4 DC（Compose 部署）— §9

| ID | 判据 |
|---|---|
| DC-1 | OCR/ASR 在 Linux 容器内可运行（无 host bridge） |
| DC-2 | 飞书 daemon 共存/迁移路径确定并可运行 |
| DC-3 | bind mounts 0700，容器 UID/GID 与宿主一致 |
| DC-4 | SQLite WAL 单写者，无锁死/corrupt |
| DC-5 | healthcheck + restart policy 生效 |
| DC-6 | 日志轮转，不无限增长 |
| DC-7 | 备份/恢复可用（不含 session.db） |
| DC-8 | 镜像固定 digest，无 latest |

## A.5 FE（前端栈）— §7

| ID | 判据 |
|---|---|
| FE-1 | package.json 锁定 React 19.x 等确切版本 |
| FE-2 | pnpm-lock.yaml 入库 |
| FE-3 | 同 lock 重装版本一致 |
| FE-4 | Node 24 + React 19 + Vite + TS + Router + TanStack + Playwright + axe 兼容矩阵全绿 |
| FE-5 | Router 选型/版本已锁 |
| FE-6 | 浮动 major 未锁 → 红 |
| FE-7 | Playwright/axe 版本固定 |

## A.6 GR（签发授权治理）— §1.5、§10

| ID | 判据 |
|---|---|
| GR-1 | 法务自己执行提案 → 403（SoD） |
| GR-2 | IT 自己批自己执行 → 403（SoD） |
| GR-3 | 新增授权缺第二审批 → 409 |
| GR-4 | 扩大 scope 缺第二审批 → 409 |
| GR-5 | 授予 release.revoke 缺第二审批 → 409 |
| GR-6 | 跨租户授权 → 403 |
| GR-7 | scope 与案件不匹配 → 403 |
| GR-8 | 变更审计含 proposer/executor/approver |
| GR-9 | 授权撤销后仍能签发 → 403 |
| GR-10 | grant 撤销后新 sign → 403 `no_active_grant` |
| GR-11 | 既有 signature 仍有效，不自动失效 |
| GR-12 | 原 signer（grant 已撤）撤回自己历史 signature → 允许 |
| GR-13 | 原 signer 尝试签新案件 → 403 |
| GR-14 | 非签发人、无 revoke grant → 403 |
| GR-15 | 历史 revoke 缺 step-up → 403 |
| GR-16 | 历史 revoke 缺 reason → 400 |
| GR-17 | 审计记录 basis（historical_signer / release_revoke_grant） |
| GR-18 | 已 invalidated/revoked 的 signature 再 revoke → 409 |

## A.7 IA（自动失效）— §10

| ID | 判据 |
|---|---|
| IA-1 | 检测到变化 → 自动失效，无确认步骤 |
| IA-2 | invalidated event + job 原子写入 |
| IA-3 | override / 取消失效端点不存在 |
| IA-4 | 人工只读查看 change_set |
| IA-5 | 崩溃恢复：event 与 job 要么都在，要么重试 |
| IA-6 | 重复检测不重复建 job |
| IA-7 | 误报无 override，走明确运维流程 |

## A.8 INV（失效输入）— §2 UJ-4、§8.6

| ID | 判据 |
|---|---|
| INV-1 | content fingerprint 变化 → invalidated + full review |
| INV-2 | rule_snapshot 变化 → 同上 |
| INV-3 | kb_snapshot 变化 → 同上 |
| INV-4 | 使用过的 authority_ref 版本变化 → 同上 |
| INV-5 | 未使用过的 authority_ref 变化 → 不触发 |
| INV-6 | conflict-table 版本变化 → 同上 |
| INV-7 | change_set 记录 old/new 版本 |
| INV-8 | 多项同时变化合并为一个事件，不丢项 |
| INV-9 | 未变化 → 不失效 |

## A.9 JQ（重审 job）— §8.6

| ID | 判据 |
|---|---|
| JQ-1 | queued + 新变化 → 合并 change_set，只有一个 job |
| JQ-2 | running + 新变化 → 创建 successor，当前继续 |
| JQ-3 | successor 等待当前 job 结束 |
| JQ-4 | 同 case 不存在并行 job |
| JQ-5 | 重复 invalidated 事件不建第二个 successor |
| JQ-6 | 合并不得丢失变化项 |
| JQ-7 | 崩溃重启 successor 不重复、不丢失 |

## A.10 OA（对象 ACL）— §1.3

| ID | 判据 |
|---|---|
| OA-1 | 提交人访问他人案件 → 403 |
| OA-2 | 审核员跨 product_line → 403 |
| OA-3 | 审核员未 assigned/非 actionable → 403 |
| OA-4 | 法务跨 product_line → 403 |
| OA-5 | 签发人跨 scope → 403 |
| OA-6 | 统筹访问本租户任意案件 → 允许 |
| OA-7 | 统筹跨租户 → 403 |
| OA-8 | IT 读案件内容 → 403（默认） |
| OA-9 | IT 读身份/审计元数据 → 允许 |
| OA-10 | 提交人读自己案件/报告 → 允许 |
| OA-11 | 历史复核人（已改派）按 assigned/actionable 判定，不自动放行 |

## A.11 OB（OCR benchmark）— §9.2

| ID | 判据 |
|---|---|
| OB-1 | PaddleOCR 在 Linux 容器 CPU 运行成功 |
| OB-2 | 缺低清/旋转样本 → benchmark 无效 |
| OB-3 | 未记录准确率口径与样本量 → 红 |
| OB-4 | bbox 与 LOC 契约不符 → 红 |
| OB-5 | 许可证未登记 → 红 |
| OB-6 | 未锁 exact 版本 → 红 |
| OB-7 | 引用旧 macOS 基线外推 → 红 |

## A.12 AB（ASR benchmark）— §9.2

| ID | 判据 |
|---|---|
| AB-1 | faster-whisper 在 Linux 容器 CPU 运行成功 |
| AB-2 | 缺噪声/多人/长视频样本 → benchmark 无效 |
| AB-3 | 未记录 WER/CER 口径 → 红 |
| AB-4 | segment timestamps 缺失/格式不符 → 红 |
| AB-5 | 未锁 model size/版本 → 红 |
| AB-6 | 长视频无分段策略 → 红 |
| AB-7 | 引用旧基线外推 → 红 |

## A.13 AP（申诉）— §2 UJ-3、§5.2

| ID | 判据 |
|---|---|
| AP-1 | 失效时旧申诉 `version_invalidated`，不自动关闭 |
| AP-2 | 不存在自动迁移路径 |
| AP-3 | 重审完成后原申诉人确认 → 迁移成功 |
| AP-4 | 非原申诉人确认 → 403 |
| AP-5 | paused 状态被受理/驳回/关闭 → 409 |
| AP-6 | 旧材料迁移前后 sha256 不变 |
| AP-7 | 原申诉人不响应 → 保持 `version_invalidated`，材料保留 |
| AP-8 | 新申诉可追溯到旧申诉 id |
| AP-9 | 暂停满 30 天未确认 → `stale` |
| AP-10 | stale 后停止提醒 |
| AP-11 | stale 后不自动 close |
| AP-12 | 记录/材料长期保留 |
| AP-13 | stale 后仍可 migrate |
| AP-14 | stale 后允许新申诉 |
| AP-15 | 转 stale 写审计 |

## A.14 QC（claim/lease/draft）— §2 UJ-2、§5

| ID | 判据 |
|---|---|
| QC-1 | 两用户同时 claim → 一个成功一个 409 |
| QC-2 | 跨 tenant/product_line claim → 403 |
| QC-3 | 非 assignee 操作已 claim 案件 → 403 |
| QC-4 | claim 后版本变化 → 409 |
| QC-5 | unclaim 回到未分配 + 审计 |
| QC-6 | reassign 通知新旧 assignee + 审计 |
| QC-7 | 重复 claim 自己案件：幂等或 409（待拍） |
| QC-8 | 无 DP3/DP4 角色 claim → 403 |
| QC-9 | 心跳更新延长 lease |
| QC-10 | idle 30 分钟 → expire/unclaim |
| QC-11 | 释放前 draft 已保存且可追溯 |
| QC-12 | 通知原 reviewer + 新 claimer |
| QC-13 | 并发 claim/心跳 CAS 一个胜出，其余 409 |
| QC-14 | unclaim 后原 reviewer 操作 → 403 |
| QC-15 | expire/unclaim 有审计 |
| QC-16 | 新 assignee 只读查看前 draft，含 author/time |
| QC-17 | 修改原 draft → 403 |
| QC-18 | adopt 生成新 draft + derived_from |
| QC-19 | 原 draft hash adopt 前后不变 |
| QC-20 | draft 自动进结论 → 不存在 |
| QC-21 | adopt 审计含 adopter/time/derived_from |
| QC-22 | 同一 reviewer 重新 claim 可 adopt 自己 draft |
| QC-23 | adopt 非 primary draft → 400/403 |
| QC-24 | 引用其他 draft 片段，记录 source ids |
| QC-25 | 自动 merge 多份 draft → 不存在 |
| QC-26 | 字段冲突 UI 并列展示，人工裁定 |
| QC-27 | 引用审计含 source/field/fragment/time |
| QC-28 | 未引用内容进入新 draft → 红 |
| QC-29 | 系统自动 adopt → 不存在 |
| QC-30 | latest 仅推荐标记，不预选 |
| QC-31 | primary selection 审计 |
| QC-32 | 选择“从空白开始”允许 |
| QC-33 | reference 审计字段齐全 |
| QC-34 | 未选择就 adopt → 400 |
| QC-35 | 选择/adopt 前写入结论 → 红 |

## A.15 RM（下线提醒）— §2 UJ-5

| ID | 判据 |
|---|---|
| RM-1 | pending 任务每日提醒 assignee+投放侧+审核负责人 |
| RM-2 | in_progress 同样每日提醒 |
| RM-3 | 同一天多次轮询只发一次（task_id+北京日期） |
| RM-4 | completed/failed/waived 停止每日提醒 |
| RM-5 | 状态变化即时通知，event_id 去重 |
| RM-6 | 按北京日期切日，不按 UTC |
| RM-7 | 不存在硬超时/overdue 逻辑 |
| RM-8 | last_reminded_at/reminder_count 更新可查 |

## A.16 RT（前端路由）— §3、§7

| ID | 判据 |
|---|---|
| RT-1 | 非法 path param → 404/重定向，不崩溃 |
| RT-2 | 非法 search param → 校验失败/默认值 |
| RT-3 | 无 capability 访问受保护路由 → 隐藏或 403 页 |
| RT-4 | 绕过前端直接调用 API → 服务端 403 |
| RT-5 | capability 字符串前后端不一致 → 红 |
| RT-6 | 深链访问无权页面 → 明确 403 |
| RT-7 | Router exact 版本未锁 → 红 |

## A.17 SB（签名绑定）— §2 UJ-4、§8.4

| ID | 判据 |
|---|---|
| SB-1 | 签发记录包含全部绑定字段 |
| SB-2 | case_version 变化 → 409/失效 |
| SB-3 | IR id/version 变化 → invalidated |
| SB-4 | raw/text 指纹变化 → invalidated |
| SB-5 | rule/kb snapshot 变化 → invalidated |
| SB-6 | used authority_ref 版本变化 → invalidated |
| SB-7 | conflict version 变化 → invalidated |
| SB-8 | 未使用 authority_ref 变化 → 不失效 |
| SB-9 | 签名记录被修改 → 红（不可变） |
| SB-10 | 重新签发 → 新记录 + derived_from |
| SB-11 | signature_version 缺失/错 → 红 |

## A.18 SD（session/安全）— §8.3、§8.8

| ID | 判据 |
|---|---|
| SD-1 | cookie 只有 opaque id，无 PII/claims |
| SD-2 | 过期 session → 401 |
| SD-3 | 撤销 session → 立即 401 |
| SD-4 | step-up token 重复使用 → 拒绝 |
| SD-5 | session DB 损坏不影响 IR/manifest |
| SD-6 | 清理任务清除过期 session 且留痕 |
| SD-7 | session DB 与 projection 独立文件 |
| SD-8 | session DB 丢失 → 重登，IR/manifest/projection 完好 |
| SD-9 | projection DB 丢失 → 从 manifest 重建，session 完好 |
| SD-10 | 两 DB WAL 独立 |
| SD-11 | 备份/清理独立 |
| SD-12 | 两个 DB 健康状态分别可见 |
| SD-13 | 两个 DB 均 0700 |
| SD-14 | 备份包含 session.db → 红 |
| SD-15 | session 丢失 → 全部 session+step-up 失效 |
| SD-16 | session.db 丢失后 audit ledger 完整 |
| SD-17 | 登录/失败/撤销/grant/step-up 失败均写审计 |
| SD-18 | 恢复后旧 session 仍有效 → 红 |

## A.19 TD（下线任务）— §2 UJ-5、§5.4

| ID | 判据 |
|---|---|
| TD-1 | revoke 已发布案件 → 创建 takedown_task |
| TD-2 | invalidated 已发布案件 → 创建任务 |
| TD-3 | 未发布案件 revoke → not_applicable |
| TD-4 | 无回填直接 complete → 400 |
| TD-5 | 未授权人 complete → 403 |
| TD-6 | 通知投放侧/签发人/审核负责人三者齐全 |
| TD-7 | 阶段一自动写平台 → 不存在 |
| TD-8 | 任务年龄/状态/提醒/积压持续可见，不得显示“正常” |
| TD-8a | 不填 due_at 可创建 |
| TD-8b | 未完成显示年龄/状态/提醒，不显示正常 |
| TD-8c | 提醒更新 last_reminded_at/reminder_count |
| TD-8d | 积压可按平台/负责人/状态列出 |
| TD-8e | 扫描无 due_at/overdue 逻辑 |
| TD-8f | API 返回 no_hard_deadline |
| TD-9 | 任务与 case/audit 关联 |
| TD-10 | 默认 assignee = 投放侧 owner |
| TD-11 | review owner 可见并监督 |
| TD-12 | coordinator 可 reassign |
| TD-13 | assignee 跨 tenant/product_line → 403 |
| TD-14 | assignee 无平台 capability → 403 |
| TD-15 | reassign 审计与通知 |
| TD-16 | Amazon capability 执行 TikTok → 403 |
| TD-17 | 跨 tenant → 403 |
| TD-18 | 跨 product_line → 403 |
| TD-19 | 三维全匹配 → 允许 |
| TD-20 | reassign 到不匹配 assignee → 403 |
| TD-21 | 授权审计含 platform/tenant/product_line |

## A.20 TF（下线失败/waive）— §2 UJ-5

| ID | 判据 |
|---|---|
| TF-1 | failed 即时通知项目统筹 + 法务 |
| TF-2 | retry 保留历次尝试 |
| TF-3 | reassign 通知新旧负责人 |
| TF-4 | 无 takedown.waive → 403 |
| TF-5 | executor 自豁免 → 403 |
| TF-6 | 缺 reason/evidence → 400 |
| TF-7 | waive 审批留痕 |
| TF-8 | failed 被直接关闭 → 红 |
| TF-9 | 升级通知可查 |
| TF-10 | 只有 1 个审批人 → 400/409 |
| TF-11 | 两个审批人同一人 → 400 |
| TF-12 | executor 作为审批人 → 403 |
| TF-13 | 原 signer 作为唯一审批人 → 403 |
| TF-14 | 原 signer + 独立审批人 → 允许 |
| TF-15 | 缺 reason/evidence → 400 |
| TF-16 | 审批人 scope 不匹配 → 403 |
| TF-17 | 审计含两名审批人/scope/time/reason/evidence |
| TF-18 | 两名审批人都不是原 signer → 允许 |
| TF-19 | 一名 scope 不匹配 → 403 |

## A.21 TQ（Query/Table）— §7.2

| ID | 判据 |
|---|---|
| TQ-1 | 同资源不同 filters → query key 不同、不串缓存 |
| TQ-2 | mutation 成功 → 相关 query 失效刷新 |
| TQ-3 | 轮询到终态 → 停止 |
| TQ-4 | 403/409 → 明确 UI 状态，不白屏 |
| TQ-5 | 500 行表格 virtualization 生效 |
| TQ-6 | 客户端绕过权限 → 服务端 403 |
| TQ-7 | 服务端权威排序仅客户端排序 → 红 |
| TQ-8 | exact 版本未锁 → 红 |

## A.22 UX（原型/无障碍）— §4、§6

| ID | 判据 |
|---|---|
| UX-01 | 提交单 + 受理回执可用 |
| UX-02 | 五标签卡必带字段齐全，PASS 卡≠申诉卡 |
| UX-03 | 报告六区块逐字，未测≠缺失 |
| UX-04 | 复核队列有负责人/下一动作/SLA |
| UX-05 | 申诉案件号=回执号、时限、撤销理由 |
| UX-06 | 签发页四前置/双指纹/step-up |
| UX-07 | 越权 403 + 申请入口 |
| UX-08 | 空/加载/错误/403/冲突/过期/未测/部分覆盖/unsupported |
| UX-09 | 多维表只读投影，状态列与 IR 单向一致 |
| UX-10 | WCAG 2.2 AA：AX-1…AX-10 |

---

# Appendix B · API 起止状态 / 409 / 幂等

> 唯一判定仍由后端决定；下表是服务端契约。`Key` = `Idempotency-Key`。

| 端点 | 合法起始状态 | 目标状态 | 409 / 拒绝条件 | 幂等 |
|---|---|---|---|---|
| POST /submissions | 无 | accepted / rejected_unsupported / failed | 重复提交同键 → 返回首次结果 | Key |
| GET /cases | — | — | 无 | 只读 |
| GET /cases/{id} | — | — | 无权限 403 | 只读 |
| POST /cases/{id}/claim | 未分配 | assigned | 已被 claim / 版本变化 → 409 | Key |
| POST /cases/{id}/unclaim | assigned（本人） | 未分配 | 非 assignee → 403 | Key |
| POST /cases/{id}/reassign | assigned | assigned（新） | 版本冲突 / 越权 → 409/403 | Key |
| POST /cases/{id}/actions | pending_review | 结论 | 非法状态 / 版本冲突 → 409 | Key |
| GET /queue | — | — | 无 | 只读 |
| GET /appeals | — | — | 无 | 只读 |
| POST /appeals | 无 | open | 重复 / 案件不可申诉 → 409 | Key |
| POST /appeals/{id}/migrate | paused(version_invalidated) | migrated | 非原申诉人 403 / 非 paused 409 | Key |
| POST /appeals/{id}/withdraw | open/paused | withdrawn | 已终态 409 / 缺理由 400 | Key |
| GET /release/pending | — | — | 无 | 只读 |
| GET /cases/{id}/release-readiness | — | — | 无 | 只读 |
| POST /cases/{id}/release-decision | pending_release | signed / rejected | 前置缺失/指纹/版本/无权限 → 409/403 | Key |
| POST /cases/{id}/release-revoke | signed | revoked | 非 signed 409 / 无 capability 403 / 缺理由 400 | Key |
| GET /takedown-tasks | — | — | 无 | 只读 |
| POST /takedown-tasks/{id}/start | pending | in_progress | 非法状态 409 | Key |
| POST /takedown-tasks/{id}/complete | in_progress | completed | 回填不全 400 / 越权 403 | Key |
| POST /takedown-tasks/{id}/fail | in_progress | failed | 非法状态 409 | Key |
| POST /takedown-tasks/{id}/retry | failed | pending | 非法状态 409 | Key |
| POST /takedown-tasks/{id}/reassign | pending/in_progress/failed | 同状态新 assignee | scope 不匹配 403 / 版本 409 | Key |
| POST /takedown-tasks/{id}/waive | failed | waived | 双人审批不全/scope/缺证据 → 409/403/400 | Key |
| GET /reports | — | — | 无 | 只读 |
| GET /reports/{id} | — | — | 无权限 403 | 只读 |
| POST /reports/{id}/resign | 已过期链接 | 新签名链接 | 报告不存在 404 | Key |
| GET /rules /control-points /routing | — | — | 无（只读） | 只读 |
| GET /notifications | — | — | 无 | 只读 |
| POST /notifications/{id}/read\|ack | 未读 | 已读/acked | 无 | 幂等 |
| GET/POST /admin/signer-grants | proposed | pending_approval/active/revoked | SoD/缺第二审批/scope → 403/409 | Key |
| GET/POST /admin/takedown-grants | proposed | pending_approval/active/revoked | SoD/缺第二审批/scope → 403/409 | Key |
| GET /admin/sessions | — | — | 无权限 403 | 只读 |
| GET /metrics | — | — | 无 | 只读 |

---

# Appendix C · 决策增量表（v1.2 新增/未落主合同）

> 来源：交叉审计后用户已拍板、但 v1.1 未完整落主合同的事项。

| # | 决策 | 状态 | 主合同落点 |
|---|---|---|---|
| D-101 | **Draft autosave**：表单字段 + notes + evidence selections + references 全量自动快照；每次可追溯；只有 explicit submit review conclusion 才进入 formal finding/decision | **已定** | 本文件 §2 UJ-2 已记原则；**字段/频率/保留期未落主合同**（待补） |
| D-102 | **Docker Compose 为阶段一生产形态** | **已定** | 本文件 §12.1/§9 已改；生产兼容仍由 DC 门验证 |
| D-103 | **原 signer 可作为 waive 两名审批人之一，但不得唯一** | **已定** | §1.5、§2 UJ-5、Appendix A TF-14 |
| D-104 | **失效/重审仅 in-app 通知** | **已定** | §2 UJ-7，已落 |
| D-105 | **静态报告不可变；Web 只渲染/索引/重签** | **已定** | §0.2、§4、§9 |
| D-106 | **阶段一规则配置只读，权威源修改** | **已定** | §8.7 已落 |
| D-107 | **P1 设计未实现** | **已定** | 文件头声明 |
| D-108 | **draft autosave 与 adopt/reference 的关系**：adopt 只复制，不改变原快照 | **已定** | §2 UJ-2；细节待补 |
| D-109 | **access-log 记录读取本身（不递归）** | **已定** | §8.8，已落 |
| D-110 | **下线任务无硬 deadline；年龄/积压可见** | **已定** | §2 UJ-5、§5.4，已落 |

> 标注「未落主合同」的项，必须在下一次主合同修订中补齐；不得当作已实现。

---

**完**。本文件为规格草案（v1.3.1），未实现、未验收；所有 [门] 通过前不得进入实现。
