# 内容审查 Agent · /implement 阶段计划 v1（2026-10-18）

> **这份文件是什么**：开发阶段计划 + ticket 拆解 + 依赖/验收/回滚/阶段门。
> **它不是什么**：不是实现，不是验收记录。**本文件写出时，P1 代码仍为 0 行。**
>
> **进入条件（已满足）**：优化 PRD、Playbook、验收表、技术方案、UIUX、工作流、证据矩阵七份主文件
> 已互相绑定并全绿（见 §1）。
> **启动条件（未满足）**：第 0 阶段的门关闭 ticket 全部通过前，**不得开始第 1 阶段业务代码**。
>
> 依据：委托方 2026-10-18 决策「**剩余开发门拆成两类：设计类先定稿关闭；实现类作为第 0 阶段关门 ticket，通过后才进第 1 阶段**」。

---

## 1. 冻结基线（2026-10-18 定稿，逐字节核过）

| 文件 | 版本 | 行数 | 字节 | sha256（短） |
|---|---|---:|---:|---|
| `Playbook/内容审查Agent-产品Playbook-v1.1.md` | v1.1（条件性 RATIFIED，S-1 后） | 1666 | 110,908 | `ff51fc87f5aa` |
| `PMO/audit/验收表-v3-覆盖全部判据-20261017.md` | v3（136 项，S-1 后） | 313 | 110,072 | `d4811e055463` |
| `Playbook/技术解决方案-v1.md` | v1（S-3 同步后） | 1,335 | 159,756 | `d3093e2d4d9d` |
| `PMO/audit/内容审查Agent-UIUX前后端规格草案-v1.md` | v1.3.1（引用重冻后） | 1429 | 80,364 | `818561aecf13` |
| `PMO/audit/内容审查Agent-端到端工作流规格草案-v1.md` | v1.2.1（引用重冻后） | 976 | 53,613 | `e9d51e21e9d5` |
| `PMO/audit/内容审查Agent-行业证据矩阵-v1.md` | v1.2 | 380 | 46,714 | `34fda3a04909` |
| `PMO/audit/内容审查Agent-常犯坑点与硬约束-v1.md` | v1.1（K-01…K-52） | 132 | 77,206 | `03b8c0742bd4` |
| `PMO/audit/内容审查Agent-决策总账-v2-20261018.md` | v2（124 决定 / 140 指针） | 219 | 63,523 | `92b2a2c5c9a4` |
| `PRD/内容审查Agent-PRD-优化版-v2.0.md` | v2.0（本地修订，2026-10-18 终验通过） | 1745 | 105,836 | `9be0c9f7e2fb` |

**机器绑定（必须全绿才允许开工）**：

```bash
python3 tools/verify_solution_meta.py        # 模块 27 / 判据 134 / 门 19（7 open / 12 closed）/ 指纹逐位
python3 tools/verify_acceptance_index.py     # 134/134，未覆盖 0
python3 tools/verify_depad.py                # 无 +4096 填充
```

**冻结规则**：本表任一文件改动 → 三处指纹（Playbook 自指纹、验收表、技术方案头部）必须同步重登记，
`verify_solution_meta.py` 变红即为未同步。

---

## 2. 开发门：两类拆法（委托方 2026-10-18 定）

| 类 | 门 | 关闭方式 | 阶段 |
|---|---|---|---|
| **设计类** | S-3（`fetch_error` 稳定 id） | 定稿规则文本 + 契约字段，写入技术方案 §8 | 第 0 阶段 |
| **设计类** | U2 控制点主表（首批 20 码 + 空族 `empty_families` 留白，当前四族） | 交付 `control-points-v1.json` / `routing-v1.json` + schema；**待产品+法务签署** | 第 0 阶段 |
| **设计类** | claim/lease/draft 模块 owner | 指派 `reviews_ledger` + `disposition_router` 边界并写入技术方案 | 第 0 阶段 |
| **实现类** | P-1 原子提交 | 代码 + 六种崩溃点注入 + manifest 对拍 | 第 0 阶段 |
| **实现类** | G-2 outbox | 代码 + 四条反向对照（含卡片/文本合流） | 第 0 阶段 |
| **实现类** | G-3 durable inbox | 代码 + 重复投递/重启续传对照 | 第 0 阶段 |
| **实现类** | G-4 认证/RBAC/session | 代码 + 401/403/409 矩阵 + step-up | 第 0 阶段 |
| **实现类** | G-5 不可信输入 sandbox | 代码 + FS/网络/CPU/时长限制对照 | 第 0 阶段 |
| **实现类** | G-6 外发最小化/PII | 代码 + 词表/正则对照 | 第 0 阶段 |

> **口径**：第 0 阶段通过的标准是**门自己的验收命令全绿**，不是「文件写好了」。
> 未通过前，第 1 阶段一行业务代码都不写。

---

## 3. 总体阶段与顺序

```
第 0 阶段  关门（设计 3 + 实现 6）           ← 现在在这里
   ↓ 门验收全绿
第 1 阶段  核心流水线（S0–S9）               ← 判定/覆盖/报告真正跑起来
   ↓ 端到端可跑 + 验收子集
第 2 阶段  工作台与放行（API/队列/申诉/签发/下线）
   ↓ G-14 放行链验收
第 3 阶段  多模态（容器 OCR/ASR + benchmark）
   ↓ OB/AB 门
第 4 阶段  部署/可观测/测试（Compose/健康/备份）
   ↓ DC 门
第 5 阶段  验收执行（136 动作逐条执行 + 回归集）
```

**为什么第 1 阶段先于第 2 阶段**：判定链是唯一的状态来源；工作台只呈现与触发。
反过来会把「API 层重算状态」这条死路走成现实。

---

## 4. 第 0 阶段 tickets（关门）

> 每个 ticket 必须给出：owner 模块、依赖、验收命令/断言、反向对照、回滚。
> **验收列写「待建」的，表示测试文件尚未存在，必须先建测试再算通过。**

### T0-01 · 控制点主表与路由表（设计关门）

- **owner**：`control_point_registry`
- **产出**：`research/governance/control-points-v1.json`（9 字段 × 首批 H01–H09 / M01–M07 / U01–U04）、
  `research/governance/routing-v1.json`（5 字段：`owner/layer/due/escalation/appeal`）；空族以 `empty_families` 为准（当前四族：场景/权利/渠道/品牌）显式 `无控制点`。
- **验收**：`L6-1…L6-6` 逐条；`control_code` 集合恰为 20；`安全词` 不在表内；两表 `control_code` 集合恒等。
- **反向对照**：删一个码 → 红；空族写成 `not_applicable` → 红；两表集合不等 → 红。
- **门**：U2 的**结构部分**关闭；**点位内容待产品+法务签署**（签前不得声称 U2 已闭）。
- **回滚**：删两份 JSON，不影响其他模块（无消费者）。

### T0-02 · `fetch_error` 稳定 id 规则（S-3 设计关门）

- **owner**：`normalizer` + `contract_suite`
- **产出**：规则文本 + 无正文 id 生成定义：
  `unit_id = sha256(source.kind ‖ 0x1F ‖ normalized_locator)`，**不含时间桶**；
  同一来源跨小时/跨天/重试得同一 id；不同来源不碰撞；`attempt_id` 单列。
  完整规则、ID-1/2/3 与正反例：`PMO/implement/T0-02-fetch-error-id-rule.md`。
- **验收**：构造无正文 `fetch_error` 样本两次（含跨小时/跨天/重试）→ `unit_id` 相同；换 kind/locator → 不同。
- **反向对照**：id 输入加入时间桶 / 错误文案 / 进程内序号 → ID-1/2/3 必红。
- **消费者同步清单**：8 项登记于技术方案 §8 S-3 与工作流 §S2.8（normalizer/contract_suite、submission_router、job_dispatcher/orchestrator、artifact_store、report_renderer/report_store、disposition_router/case_watch、metrics_read_model、contract_validator）。
- **门**：S-3 closed（**定义/登记**完成；P-1 原子写入仍 open —— 不表示实现已上线）。

### T0-03 · claim/lease/draft 模块归属（设计关门）

- **owner 决定**：`reviews_ledger` 持有 assignment/lease；`disposition_router` 只读路由；
  draft 存储归 `reviews_ledger`。写入技术方案模块表与工作流 S7.1。
- **验收**：技术方案 S7.1 不再出现「待定」；工作流同步。
- **门**：claim owner 开发阻断解除。

### T0-04 · P-1 原子提交实现

- **owner**：`artifact_store`
- **产出**：staging → rename → manifest.tmp → fsync → rename manifest；恢复四态。
- **验收**：六种崩溃点注入（commit 前/中/后各两处）→ 恢复后 `committed/orphan/uncommitted/garbage` 穷举，
  无孤儿可见、无半提交；投影重建后与 manifest 对拍一致。
- **反向对照**：去掉 manifest 单点提交 → 崩溃后出现「文件在、manifest 无」→ 红。

### T0-05 · G-2 outbox 实现

- **owner**：`send_gateway`（台账 `tools/agent/outbound.mjs`）
- **验收**：同一 `logical_delivery_id` 发两次只发一次；卡片+降级文本两个变体只发一次；
  `reply` 崩溃 → 不重发；`proactive-*` 崩溃 → 重发；`pending` 超时标 `unknown`。

### T0-06 · G-3 durable inbox

- **owner**：`feishu_io`
- **验收**：同一 `event_id` 投两次只处理一次；处理中 kill → 重启从游标续传；不重复回答。

### T0-07 · G-4 认证 / RBAC / session

- **owner**：`release_gate`（身份边界）+ `review-api` 装配层
- **验收**：AU-1…AU-29 全绿；401/403/409 矩阵；step-up 5 分钟/一次性/绑定 principal+case+action；
  生产拒绝模拟身份；session 库独立、不备份、故障全失效。

### T0-08 · G-5 不可信输入 sandbox

- **owner**：`media_pipeline` + `orchestrator`
- **验收**：skill 命令/OCR/ASR/解析在受限 FS/网络/CPU/内存/时长下运行；
  越界样本被拒；正常样本通过。

### T0-09 · G-6 外发最小化 / PII

- **owner**：`report_renderer` + `send_gateway`
- **验收**：群消息/卡片不出现凭据、身份证、电话、内部路径；词表+正则双向对照；
  误报样本（正常文本）必须不被拦。

### T0-10 · 验收执行器骨架

- **owner**：`contract_validator`
- **产出**：`tests/acceptance/` runner，读取验收表 136 行的 `test_id/fixture/command`；
  缺失即 `untested`（退 2），不伪装通过。
- **验收**：跑一次 → 输出 `passed / failed / untested` 三态；缺 test_id 的行落 untested。

**第 0 阶段退出门**：T0-01…T0-10 全部通过 + `verify_solution_meta.py`/`verify_acceptance_index.py`/`verify_depad.py` 全绿。

> ### ✅ 出门结论（2026-10-18）
>
> 10 个 ticket 全部通过；**11 处假绿已修并做变异验证**；最终变异探针 6/6 真红（rc=1，无假绿、无 rc=2）；
> 契约冻结且引用重冻完成（旧 hash 全仓 0）；`verify_control_points.py` 12/12。
> **四道门仍标「部分」**（P-1 / G-4 / G-5 / G-6），余项作为并行跟进；第 1 阶段入口判据满足。

### 4.1 进度（2026-10-18）

| Ticket | 状态 | 证据 |
|---|---|---|
| T0-04 P-1 原子提交 | ✅ **通过** | `base/artifact_store.py`（212 行）+ `tools/verify_atomic_commit.py`（123 行）；实跑 **8/8，rc=0**，含反向对照「单点提交 bug → orphan」 |
| T0-04 余留（记入下一轮） | ⚠️ | ① 故障注入为进程内模拟，非真实 kill/断电；② 目录 fsync 在 macOS 可能 EINVAL，未掉电验证；③ **stale lock 启动清理未实现**；④ 投影重建/manifest 对拍未接 |
| T0-07 会话与 step-up（切片 1） | ✅ **通过** | `base/auth_session.py`（157 行）+ `tools/verify_auth_session.py`（174 行）；实跑 **22/22，rc=0**，含三条反向对照（去 single-use / 去 absolute / cookie 塞 tenant） |
| T0-07 RBAC/ACL（切片 2） | ✅ **通过** | `base/rbac.py`（137 行）+ `tools/verify_rbac.py`（197 行）；实跑 **35/35，rc=0**，含四条反向对照（去 scope / 去 SoD / 去 IT 内容限制 / 全拒坏实现） |
| T0-07 余留 | ⚠️ | 注入时钟非真实等待；未做并发多写者；cookie 轮换/限流/锁定未做；DB 丢失为删文件模拟；takedown 人级 allowlist 未接入；IT/机器元数据读取未按对象收敛；grant 的 tenant/product_line scope 未校验 |
| T0-01 控制点主表 | ✅ **通过（结构，已返修；补了验证器）** | 20 码 / 九字段 / 两表集合恒等；族分布 宣称14/披露3/事实3；**空 4 族（场景/权利/渠道/品牌）**；routing 20 owner 已填并带 layer/due/escalation/appeal（v2）；U02 停用码有 `authority_ref_exemption` + `known_gaps`；`contract_impact` 已列同步四处。**新增 `tools/verify_control_points.py`：12/12 通过**（L6-1/2/4/6 + routing 集合与字段 + 空族双向一致；四条反向对照）。**点位内容仍待产品+法务签署（U2 未闭）** |
| T0-02 fetch_error id | ✅ **通过** | 规则已改为 `sha256(kind ‖ 0x1F ‖ normalized_locator)`，**不含时间桶**；ID-3 反转为「跨小时/跨天/重试必须同 id」；attempt 区分交给 `attempt_id` |
| T0-03 claim owner | ✅ 内容通过 | 裁定文本已交付；同步进技术方案/工作流留到主合同同步批 |
| T0-09 外发最小化 / PII（G-6） | ✅ **通过** | `tools/redact.py`（10,093B）+ `tools/verify_redact.py`（10,392B）；实跑 **76 项检查 / 0 红 / 正样本 17 / 负样本 8**，rc=0 |
| T0-08 沙箱（G-5） | ✅ **通过** | `base/sandbox.py`（8,198B）+ `tools/verify_sandbox.py`（9,116B）；实跑 **11/11，rc=0**，含四条反向对照（去 CPU 限制 / 去超时 / 去 cwd 隔离 / 正常样本防全拦）；超限与普通失败可区分 |
| T0-05 outbox | ✅ **通过（含两轮对抗审查，38/38）** | `tools/agent/outbound.mjs` + `outbound.test.mjs`；实跑 **21/21**，含「同一 id 只发一次 / 卡片+文本只发一次 / reply 不重发 / proactive 重发 / 缺 id 拒发」，**未发真消息** |
| T0-06 durable inbox | ✅ **通过（含两轮对抗审查，29/29）** | `tools/agent/inbox.mjs` + `inbox.test.mjs`；实跑 **12/12**，含重复投递只处理一次、处理中崩溃续传、坏游标保守回退（宁可重放不跳过） |
| T0-10 验收执行器 | ✅ **通过（含 T0-10b 加固）** | `tools/verify_acceptance_run.py` + 自测；实跑 **0 passed / 0 failed / 136 untested，rc=2**（正确：无执行点不许报通过）；自测 **6/6**，含「命令经 T0-08 沙箱执行」与「去掉 cwd 隔离 → 仓内出现文件」反向对照 |

---

### 4.1c 变异检验发现的 P0 假绿（2026-10-18，9a 只读审计）

> **结论：第 0 阶段的「通过」里有假绿。** 以下必须在第 1 阶段开工前修完，
> 每条都要「删掉修复 → 验证器必须红」。

| # | 位置 | 问题 | 归属 |
|---|---|---|---|
| M-1 | `verify_atomic_commit.py` | 注释掉产物提升后，验证器因 C13 `FileNotFoundError` 退 **rc=2（未测）** 而非 rc=1（失败） | 6d |
| M-2 | `base/auth_session.py:29-30` | 分隔符守卫是死分支（正则已挡），删掉仍 22/22 绿 | 6d |
| M-3 | `artifact_store.recover()` | 多 run 共存时，已提交 run 的 blob 被判 `garbage` | 6d |
| M-4 | `artifact_store` 三处守卫 | 仓内根拒绝 / 同 fs 断言 / manifest 指向 staging·tmp —— 删掉仍绿（无用例） | 6d |
| M-5 | `base/sandbox.py` | macOS `RLIMIT_AS` 抛 ValueError 被吞 → 内存限制未生效且无测试；`limit_hit` 可由 stderr 字符串伪造；`_socket` 可绕过 | 6d |
| M-6 | `base/rbac.py` | `takedown.execute/waive` 无任何角色拥有（死能力）；多角色短路；`release.revoke` SoD 未测 | 6d |
| M-7 | `auth_session` | `invalidate_all()` 与 `create_session` 的 tenant 入参未测 | 6d |
| M-8 | 四个 `base/*.py` | 生产函数裸露 `bad_mode` 测试后门 | 6d |
| M-9 | `verify_redact.py` C 段 | 断言 `disabled={want}` 后 finding 类型 == want —— **数学恒真** | evidence |
| M-10 | `redact` 负样本 B3 | URL 里是 10 位数字，不匹配手机号 → 删 `no_url` 守卫仍绿 | evidence |
| M-11 | `redact` 第二条 `tool_call_id` 规则 | 无独立正样本，删掉仍绿 | evidence |

### 4.1b 门状态（ticket 通过 ≠ 门关闭：按下表如实记）

| 门 | 状态 | 已具备 | 仍缺（跟进 ticket） |
|---|---|---|---|
| S-3 fetch_error id | **关闭（定义/登记）** | T0-02 定稿：`unit_id = sha256(source.kind ‖ 0x1F ‖ normalized_locator)`，不含时间桶；消费者同步清单 8 项登记于技术方案 §8 / 工作流 §S2.8 | — |
| P-1 原子提交 | **部分（组件关闭，真实断电未测）** | 原子提交 + 六崩溃点 + 恢复四态 + **stale lock 清理 + 投影重建/manifest 对拍（27/27，C19–C24）** | 真实断电只能记未测，不冒充 |
| G-2 outbox | **关闭** | 21/21，含四类反向对照 | — |
| G-3 durable inbox | **关闭** | 12/12，含续传与坏游标回退 | — |
| G-4 认证/RBAC | **关闭** | session/step-up 22/22；RBAC/ACL **73/73**（含 takedown 人级 allowlist 两本、元数据按对象收敛、grant 三方 scope 校验）；通知按 recipient 隔离（P0 修复） | — |
| G-5 沙箱 | **关闭（组件）** | **20/20**：绝对路径放行/拒绝、孙进程 killpg 回收、env 白名单、RLIMIT_AS 不可用时显式记未测 | — |
| G-6 最小化 | **关闭（链路接入）** | redact 99 项 + **send_gateway 唯一出口接入（31/31，正样本遮蔽/负样本不误遮/删调用 6 条红）** | — |

**第 1 阶段入口判据**：G-2/G-3 已关闭；P-1 组件可用（stale lock 作为 T0-04b 并行）；
G-5 组件可用（OS 级加固作为 T0-08b 并行）；G-4/G-6 的剩余项在**第 2 阶段（工作台）开工前**必须关闭。

## 4.2 主合同同步批（S-1，第 0 阶段后、第 1 阶段前）

> 第 0 阶段产出改变了若干合同事实，必须一次性同步并重登记指纹；**不做这一步就进第 1 阶段，
> 会出现「代码按新事实、文档写旧事实」**。

| 变化源 | 要改的主合同（精确位置） | 内容 |
|---|---|---|
| T0-01 控制点表 | **Playbook** `:616 / :620 / :1390 / :1399 / :1406 / :1409 / :1594`；**验收表** `#30 / #72 / #73 / #85 / SEC-5-10`；**工作流** `:66` | 不再写死「空三族」→ 统一为「**空族以 `control-points-v1.json` 的 `empty_families` 为准（当前四族：场景/权利/渠道/品牌）**」；`routing-v1` 字段 4→5（新增 `layer`，版本 v2）。★ **PRD 不需要改**：全文无「空族」表述（已核） |
| T0-02 fetch id | 技术方案 §8 S-3、工作流 S2 | `fetch_error` id = kind + 规范化地址（**不含时间桶**）；重试归并同一案件；`attempt_id` 单列 |
| T0-03 claim owner | 技术方案模块 22/15、工作流 S7.1 | assignment/lease/draft 归 `reviews_ledger`；`disposition_router` 只读 |
| T0-04…T0-09 | 技术方案 §8 门状态 | 逐门记录「已实现 + 验收命令」与**残差**，但**不得写成已上线** |

**执行纪律**：单文件 owner、按 Playbook → 验收表 → 技术方案顺序重登记，
最后跑 `verify_solution_meta.py` 全绿。

---

### 4.1d 第 1 阶段进行中（2026-10-18 晚，编排器 4b 登记）

| Ticket | 状态 | 验证器读数 | 交付者 | 变异审计 |
|---|---|---|---|---|
| T1-C1 契约 schema | ✅ 返修后 46/46（待 9a 复验变异） | 46/46 rc=0 | 0e | VC-1d/VC-1e/VC-B1..B4 已修，待变异复核 |
| T1-01 提交入口 | ✅ 返修后 40/40（待 9a 复验变异） | 40/40 rc=0 | 6d/0e | SR-ADV1/SR-ADV2 已修，待变异复核 |
| T1-03 任务调度 | ✅ 验收通过（假绿已修） | 58/58 rc=0 | cleanup | JD-ADV1/2/3 已修并复验 |
| T1-07 finding_store | ✅ 返修后 33/33（待 9a 复验变异） | 33/33 rc=0 | 0e | FS-ADV1/2/3 已修（REQUIRED_KEYS 生效、active() 有测试、M1 守卫），待变异复核 |
| T1-04 rule_judge + 控制点注册表 | ✅ 验收通过 | 34/34 rc=0 | cleanup | 待 9a 复核 |
| T1-02 normalizer | ✅ 基线通过，待审计 | 37/37 rc=0（6d 自做 4 变异全红） | 6d | **待 9a 变异审计** |
| T1-06 evidence_sync | ✅ 基线通过，待审计 | 60/60 rc=0（7 组变异全红） | cleanup | **待 9a 变异审计** |
| T1-08 coverage_composer | ✅ 基线通过，待审计 | 26/26 rc=0（6 条反向对照） | 0e | **待 9a 变异审计** |
| T1-05 semantic_judge | ⚠️ 实现 30/30，验证器自身异常 rc=2 | 实现通过；验证器半成品（`unit_pos` 函数当记录传入） | 6d / 9a | 待 9a 修验证器 + 补 6d 的 5 类变异 |
| T1-09 decision_table | ✅ 基线通过（8 变异全红） | 62/62 rc=0 | cleanup | 待 9a 复核 |
| T1-10 disposition_router | ✅ 基线通过（9 变异全红 + AST 扫描） | 74/74 rc=0 | cleanup | 待 9a 复核 |
| T1-11 report_render | ✅ 基线通过（5 变异全红） | 59/59 rc=0（Node） | 6d | 待 9a 复核 |
| T1-12 report_store | ✅ 基线通过（9 变异全红） | 38/38 rc=0 | cleanup | 待 9a 复核 |
| T1-13 send_gateway | ✅ 基线通过（两红为验证器误报已修） | 25/25 rc=0 | 0e | 待 9a 复核 |
| T1-14 metrics_read_model | ✅ 基线通过（9 变异全红） | 38/38 rc=0 | cleanup | 待 9a 复核 |
| T1-15 orchestrator | ✅ 基线通过（6 变异全红） | 26/26 rc=0 | 6d | 待 9a 复核 |

**全仓验证器快照（2026-10-19 00:40，编排器实跑 19 个检查器）**：18 绿 / 1 未测 ——
`contracts 46`、`submission_router 40`、`job_dispatcher 58`、`normalizer 37`、`rule_judge 34`、
`evidence_sync 60`、`finding_store 33`、`coverage_composer 26`、`decision_table 62`、
`disposition_router 74`、`report_store 38`、`report_render 59`、`control_points 12`、
`atomic 21`、`auth 27`、`rbac 49`、`sandbox 14`、`redact 99`；`semantic_judge` = **rc=2（验证器自身异常）**。

> ⚠️ **rc=0 不等于通过**：9a 已证明其中 4 张 ticket（T1-C1/T1-01/T1-07/T1-03 修复前）在删掉关键守卫后
> 仍全绿。**放行判据 = 基线 rc=0 + 9a 变异审计全探针真红**，缺一不可。

**第 1 阶段存活假绿清单（9a 批次②③④⑤抓到，全部未修复前不得放行）：**

| # | 位置 | 问题 | 修法要点 | 归属 | 状态 |
|---|---|---|---|---|---|
| SR-ADV1 | `submission_router.py:122-127` | 文档类型走非飞书链接未被拒（无用例覆盖） | 补 content_type=文档 + 群消息/free_text → rejected_unsupported | 6d | 待修 |
| SR-ADV2 | `submission_router.py:291` | 同 submission_id 重试序号可恒为 1 | 补同 id 连续 submit 两次断言 attempt_id 不同 | 6d | 待修 |
| JD-ADV1 | `job_dispatcher.py:257` | _stale() 死 PID 锁清理无用例覆盖 | 补死锁清理成功 + 活锁保留两条用例 | cleanup | **已修** ✅ |
| JD-ADV2 | `job_dispatcher.py:430-431` | commit_failed 退路可绕过（未模拟 commit 失败） | mock store.commit 抛异常，断言 outcome=commit_failed | cleanup | **已修** ✅ |
| JD-ADV3 | `job_dispatcher.py:149-150` | external_label 校验可绕过；run_state=OK 时 None 被放行 | 按 Playbook §3.3.2 改五值校验 + D 段补拒收断言 | cleanup | **已修** ✅ |
| VC-1d | `attempt-v1.schema.json:66` | rejected_unsupported 允许带 receipt_id（漏负样本） | 补 rejected+receipt_id 与 failed+receipt_id 两条负样本 | 0e | 待修 |
| VC-1e | `verify_contracts.py:175` | `unsupported_keywords()` 不递归 `allOf` | 递归遍历 allOf 列表元素 | 0e | 待修 |
| VC-B1..B4 | `verify_contracts.py:300-352` | 行为断言与 schema 零连接（`rc` 赋值不用） | 真读 contracts/ 或改名 helper 单测并剔出契约验收 | 0e | 待修 |
| FS-ADV1 | `finding_store.py:77-81` | `REQUIRED_KEYS` 死常量，`quote`/`derived_from` 未校验 | 接上校验 + 两条负样本 | 0e | 待修 |
| FS-ADV2 | `finding_store.py:300` | `active()` 从未被测试（改恒返 [] 仍绿） | 补四态过滤用例 | 0e | 待修 |
| FS-ADV3 | `finding_store.py` | M1（semantic 直接 confirmed 须 `confirmed_by_rule_class=True`）未实现 | 补守卫 + 正反断言 | 0e | 待修 |

**委托方裁定（2026-10-18 晚）**：`commit_failed` outcome **保留并写入规格**（job_dispatcher 五态之一，表达「worker 成功但产物落盘失败」）。

---

### 4.1e 第 2 阶段进行中 + 公开仓历史重写（2026-10-19，编排器 4b 登记）

**历史重写（委托方授权，一次性）**：
- 58 张客户素材图 `PMO/audit/momcozy-assets/sref-candidates/`（14.3MB）已从全部 81 个提交历史移除。
- 远端 main `0f140909` → **`fa97050d`**（只推重写后的远端当前位置，未发布本地领先的 13 个提交）。
- 本地 main → **`04ca8089`**；`.git` 25M → 11M；旧提交 `890d50e` 已不可达；工作区未提交文件全部保留。
- 备份：`~/audit_backups/audit_repo_backup_20261019_0316.bundle`（旧历史唯一副本，勿删）。
- 残留：`verify_no_media_in_repo` DL-3a 仍报 17 个二进制，全部为 `dsh-browser-ext/assets/icons/`（产品自身资产）；DL-3b 未测（`AUDIT_MEDIA_ROOT` 未配置）。

**第 2 阶段验收读数（编排器实跑）**：

| 验证器 | 读数 | 变异抽查 | 判定 |
|---|---|---|---|
| `verify_review_api` | 15/15 rc=0（uv 环境，OpenAPI 3.1） | — | ✅ 越权三连挡住、API 不重算 |
| `verify_write_api` | 31/31 rc=0 | — | ✅ sign/revoke/reject 真实成功，403/409 矩阵成立 |
| `verify_reviews_ledger` | 20/20 rc=0 | 删 claim 守卫 → 2 条断言级红 | ✅ |
| `verify_release_gate` | 53/53 rc=0 | 删 SoD 守卫 → **6 条断言级红、0 Traceback**（假红已修） | ✅ |
| `verify_takedown` | 54/54 rc=0 | 删 never_tracked/仓外判定 → 2 条断言级红 | ✅ |
| `smoke_end_to_end`（核心链路） | **38/38 rc=0**（真实模块全链路） | 内置「partial 永不 PASS」反向对照 | ✅ 核心流水线跑通 |
| `verify_metrics_read_model` | 38/38 rc=0 | — | ✅ |
| `verify_notifications` | 40/40 rc=0 | — | ✅ |

**假绿修复进展**：`contracts` 43→46、`finding_store` 25→33、`submission_router` 38→40，均 rc=0（待 9a 复跑确认）。

> ⚠️ **这张表的 ✅ 只表示「验证器自己跑绿了」，不表示「生产可用」。**（2026-10-20 补）
>
> 上表里凡是涉及**写链**的（`verify_write_api` / `verify_reviews_ledger` / `smoke_end_to_end`），
> 跑的都是**本地内存台账**：`SessionStore(":memory:")`、`FindingStore()` 从没从投影载入过、
> 幂等只在进程内成立。**生产持久 review 台账、原子幂等、真实身份接口、draft/formal GET、
> 权威追加→投影新鲜度，这五项一个都没实现，也没派工。**
>
> 复核员/委托方读这张表时，请读成「子系统自证通过」，不要读成「可以上生产」。
> 这条边界与 `AGENTS.md` §2.4.1 是同一个形状：**验证器绿 ≠ 真实路径通**。

**过程中发现并修复的环境问题**：`base/__pycache__/coverage_composer.cpython-312.pyc` 与 `base/coverage_composer.cpython-39.pyc` 损坏（UTF-8 解码失败），导致端到端冒烟导入失败——K-27 同形；清除项目缓存子树后即绿。`base/` 目录下直接躺着 `.pyc` 属异常，已删除。

**并行分工（2026-10-19）**：0e=G-4 门残差（takedown 人级 allowlist / IT 按对象收敛 / grant scope）；6d=API↔IR 联调测试；cleanup=前端工作台 v0 脚手架；9a=decision_table/disposition_router/orchestrator/report_store 四批变异审计。

---

## 5. 第 1 阶段：核心流水线（S0–S9）

> 目标：**一条内容从入口到报告真的跑通**，判定只有一个来源。

| Ticket | 内容 | owner | 依赖 | 验收（摘） |
|---|---|---|---|---|
| T1-01 | `submission_router` 四维校验 + `Attempt` | submission_router | T0-02 | L1-0/0b/0c、AT-1…3 |
| T1-02 | `normalizer` 产 `ContentUnit v1` | normalizer | T1-01 | L1-1…L1-5、H1–H14 |
| T1-03 | `job_dispatcher` + `run_record` | job_dispatcher | T1-01 | JQ-1…7 |
| T1-04 | `rule_judge` + `control_point_registry` 接入 | rule_judge | T0-01 | L2-4、C1 |
| T1-05 | `semantic_judge` 默认 candidate | semantic_judge | T1-04 | L2-9、C2/C4 |
| T1-06 | `evidence_sync` + 冲突表 | evidence_sync | T1-04 | L2-8、KB-1…6 |
| T1-07 | `finding_store` append-only | finding_store | T1-05/06 | L2-5、ID-1…4 |
| T1-08 | `coverage_composer` | coverage_composer | T1-02 | L2-3、COV-1…7 |
| T1-09 | `decision_table` 15 链 + I1–I7 | decision_table | T1-07/08 | L2-1、EQ-1、L2-1b |
| T1-10 | `disposition_router` 五档停待放行 | disposition_router | T1-09 | L3-1/3/5、L3-4 |
| T1-11 | `report_renderer` 六区块 + 去 AI 味 | report_renderer | T1-09 | F1/F2、L4-3、L4-7 |
| T1-12 | `report_store` 静态报告 + 重签 | report_store | T1-11 | R1/R2/R3、L4-2 |
| T1-13 | `send_gateway` 卡片/文本 + 兜底 | send_gateway | T1-11 | L4-4/6、MSG-1…4 |
| T1-14 | `metrics_read_model` 四指标 | metrics_read_model | T1-12 | L5-1/2/5 |
| **T1-15** | **`orchestrator` 五步串联 + ReviewIR 组装 + 回执**（**2026-10-19 补：原计划漏了编排器本体**） | orchestrator | T1-01…T1-13 | L2-7、L6-6、V5；五步各一次、无回边、无提前停；`skipped=[]` |

**第 1 阶段退出门**：T1-01…T1-15 通过 + 一条端到端样本产出 IR/报告/群消息（**2026-10-19 已达成：smoke 38/38；全量 27 检查器 rc=0；提交 `2a397cf`**）；
`coverage=partial → REVIEW` 与「五档全部待放行」两条反向对照必须红过。

---

## 6. 第 2 阶段：工作台与放行

| Ticket | 内容 | 依赖 | 验收（摘） |
|---|---|---|---|
| T2-01 | `review-api`（FastAPI）读 API | T1 | BE-3/4，API 不重算状态 |
| T2-02 | 写 API：复核/申诉/claim/unclaim | T2-01 | QC-1…35 |
| T2-03 | `release_gate` 签发/撤回/失效 | T2-02 | RL-1…15、SB-1…11、INV-1…9 |
| T2-04 | 下线任务 + 双人 waive | T2-03 | TD-1…21、TF-1…19 |
| T2-05 | 通知（in-app + 飞书） | T2-03 | TS-22、RM-1…8 |
| T2-06 | 前端工作台（React 19 + TS + Vite） | T2-01 | FE-1…7、UX-01…10 |
| **T2-02a** | **`reviews_ledger`（领取/lease/draft/抽样台账）**——写 API 的前置（2026-10-19 补） | T2-01 | QC-1…35、L5-3 |

### 6.1 进度（2026-10-19）

| Ticket | 状态 | 读数 |
|---|---|---|
| 环境门（uv/pyproject/uv.lock） | ✅ 通过 | uv 0.13.1；FastAPI 0.115.6 / Pydantic 2.10.4 / uvicorn 0.34.0；`uv sync --locked` 通过 |
| 仓库治理（验证器登记 / 文档可达性） | ✅ 通过 | 登记 53 个、203/203 + 反向 209/209；可达性 12/12 + 反向 34/34；`CAPTURED_ASSET` 窄豁免带反向对照 |
| T2-01 只读 API | ✅ 通过（5 变异全红） | 15/15；OpenAPI 3.1；API 不 import 判定模块；401/403 矩阵 |
| T2-02a reviews_ledger | ✅ 通过（5 变异全红） | 20/20；并发 claim、lease+draft、autosave 不产 formal、adopt derived_from、四层抽样 |
| T2-02 写 API | ✅ 通过（5 变异全红） | 25/25；claim/unclaim/reassign/actions/appeals/takedown；release 端点当时 501 占位 |
| T2-03 release_gate | ✅ 通过（6 项指定变异全红） | 53/53；全字段绑定+signature_hash、五类失效、自动重审 job、SoD+step-up、机器写放行被拒 |
| T2-04 takedown | ✅ 通过 | 54/54；状态机、回填三选一、双人 waive、每日提醒去重、无硬时限 |
| T2-05 notifications | ⏳ 进行中 | — |
| T2-06 前端工作台 | ⏳ 未派 | — |

**第 2 阶段退出门**：G-13/G-14 通过；「机器/前端直写 release_status」反向对照必须 403。

---

## 7. 第 3 阶段：多模态

| Ticket | 内容 | 依赖 | 验收 |
|---|---|---|---|
| T3-01 | 容器内 OCR（PaddleOCR/Tesseract） | T0-08 | OB-1…7 |
| T3-02 | 容器内 ASR（faster-whisper/Whisper） | T0-08 | AB-1…7 |
| T3-03 | 抽帧/时码/bbox（LOC） | T3-01 | LOC-1…4、V1/V2 |
| T3-04 | VLM 三类过滤（人脸/未成年人/未上市） | T3-03 | D-3、VLM-1…3 |

**第 3 阶段退出门**：OB/AB benchmark 读数齐备并锁版本；旧 macOS 读数不得沿用（反向对照：引用旧读数 → 红）。

---

## 8. 第 4 阶段：部署 / 可观测 / 测试

| Ticket | 内容 | 验收 |
|---|---|---|
| T4-01 | Docker Compose（review-api/scheduler/web/static） | DC-1…8 |
| T4-02 | 数据卷 0700 / SQLite 单写者 | DC-3/4 |
| T4-03 | 健康检查 + 重启策略 | DC-5 |
| T4-04 | 日志轮转 + 指标 + 告警 | 可观测 |
| T4-05 | 备份恢复（不含 session.db） | DC-7 |

---

## 9. 第 5 阶段：验收执行

- 逐条执行验收表 136 项，产出 `passed / failed / untested` 三态；
- **126 条 machine 动作在测试文件建好前全部记 `untested`**，不得写「通过」；
- 冻结回归集 50–100 条 + 四条陷阱负样本；
- 终点：`verify_acceptance_index.py` 只证明编号覆盖，**行为验收以 runner 结果为准**。

---

## 10. 分发与验收规则

1. **单一文件 owner**：任一时刻一个文件只有一个写者；跨文件改动拆批。
2. **每批必须先验收再发下一批**；未过退出门不发下一批。
3. **提交政策**：未获委托方明确授权，不 `git add`/commit/push；共享工作区禁止 `git add -A`。
4. **测试先行**：ticket 必须先有可执行断言（test_id/fixture/command），再写实现。
5. **未测 ≠ 通过**：读不到、跑不了、依赖缺失，一律记 `untested` 并退 2。
6. **回滚**：每阶段代码独立目录/模块；回滚 = 停用该模块入口 + 保留数据，不删历史产物。

---

## 11. 现在就能开始的第一批（本文件交付后）

- **T0-01、T0-02、T0-03**（设计类，纯文档/JSON，不写业务代码）
- **T0-10**（测试骨架，纯工具）
- 其后 **T0-04…T0-09**（实现类，按 P-1 → G-2/G-3 → G-4 → G-5 → G-6 顺序）

> **一句话**：先把「门」变成代码与测试，再写业务；每个门通过都有反向对照，否则不算关门。
