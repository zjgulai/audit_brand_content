# 未接验收行分类（T0-10）

> 生成依据：`PMO/audit/验收表-v3-覆盖全部判据-20261017.md`（不改表）。  
> 初始 runner：mapped=86；补 10 条核心 A 后 **mapped=96 / passed=96 / failed=0 / untested=40**，rc=2。  
> **2026-10-19 第二批：新接 3 条（51 / 59 / 65）→ mapped=99 / passed=99 / failed=0 / untested=37**，rc=2。
>
> ★ 本批有 **2 条查过之后决定不接**（21 / 78）—— 它们「看起来能接」：
> 21 有 `verify_normalizer.py` 的 C2b 段，78 有 `verify_engine_contract.py` 的 V61 段。
> 但逐字段核对后，**字段名或形状与判据对不上**。
> 硬接的后果不是「少验一条」，而是**把未验证的东西标成已验证** —— 那比留空更糟。
> 两条的差异都写在下表「理由」里，可直接复核。

## 分类计数

| 分类 | 条数 | 含义 |
|---|---:|---|
| A 现在就能补 | 16 | 模块已实现，只缺 fixture/command；已接 13 条，余 3 条因现有 verifier 覆盖不足留 untested |
| B 阶段 3–5 | 22 | OCR/ASR/前端/部署/回归集/CI，保持 untested |
| C 口径待定 | 12 | 实现或口径有歧义，需补专项验证器或委托方确认 |

## 逐行

| 行号 | 判据 | 验收动作 | 分类 | 理由 | 下一步 |
|---:|---|---|---|---|---|
| 11 | L1-4b | 非确定性解析（OCR/VLM）结论集合一致 | B | OCR/VLM 非确定性收敛：属阶段 3 媒体能力，当前无真实模型采样环境 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 21 | SEC-3.3.4-5 / SEC-3.3.4.4-1 / SEC-3.3.4.4-2 / SEC-3.3.4.4-3 / LOC-1 / LOC-2 / LOC-3 / LOC-4 / SEC-3.3.4.4-4 / L1-3 | location 三形态可点回原片、帧号与抽帧参数可复算 | C | **2026-10-19 复核：形似而实不覆盖，不能接。** `verify_normalizer.py` 的 C2b 段（8 条）验的是「location 形状合法 + normalizer 是唯一生产者」，与行 21 要的**字段名和形状都不一样**：<br>· 行 21 要 `char_start/char_end/quote` → 实际 schema 是 `start/end`（无 `quote`）<br>· 行 21 要 `bbox` 为四元数组 `[x1,x2,y1,y2]` → 实际是对象 `{x,y,w,h}`<br>· 行 21 要 `image_id` / `video_id` / `frame_thumb` → schema 里**这三个字段都不存在**（只有 `frame_ref`）<br>· 行 21 要「按抽帧参数独立复算 frame_no」与「frame_thumb 可解码」→ 验证器里**完全没有**<br>**硬接会把「形状合法」冒充成「可点回原片」，比不接更糟。** | 先定 location 字段口径（`char_start` vs `start`、`bbox` 对象 vs 四元数组、`frame_thumb` 是否入契约），再补「按 `frame_no=round((time_start-offset)/interval)` 独立复算」与「frame_thumb 可解码」两条专项断言 |
| 35 | KB-1 / KB-2 / KB-3 / KB-4 / KB-5 / KB-6 / L2-8 / SEC-8-14 | 知识库失败路径三分法 | A | 模块已实现，只缺 fixture/command | 已接 `verify_evidence_sync` |
| 36 | STOP-1 / STOP-2 / STOP-3 / STOP-4 / STOP-5 / STOP-6 / STOP-7 / STOP-9 | 停机条件登记与行为 | C | 停机条件登记 6 条与行为：登记/提前停口径仍待实现与确认 | 补专项验证器或先由委托方确认口径 |
| 37 | V1 / V2 / V4 / V5 | 视频五项覆盖声明与关键帧读数 | A | 模块已实现，只缺 fixture/command | 已接 `verify_report_render` |
| 43 | SEC-0-2 | 强制词均可证伪（元判据） | C | 强制词均可证伪（元判据）：人工通读，无机器样本 | 补专项验证器或先由委托方确认口径 |
| 44 | IN-2 | 判定输入来源可追溯 | C | 判定输入来源可追溯：人工沿 pipeline 追字段，无自动判据 | 补专项验证器或先由委托方确认口径 |
| 45 | EQ-1 | E01-E14 只是等价展开、不得成第二套规则 | C | E01-E14 等价展开：decision_table 验证器覆盖 15 链，但未做文档逐格等价对拍 | 补专项验证器或先由委托方确认口径 |
| 46 | L2-1a | 判定逻辑只存在于 §3.3.8.1 | C | 判定逻辑只存在一处：现有验证器只查 decision_table 自身，未扫全仓第二套实现 | 补专项验证器或先由委托方确认口径 |
| 47 | PO-4 / I1 / I2 / I3 / I4 / I5 / I6 / I7 | 违反不变量时的并行义务 | A | 模块已实现，只缺 fixture/command | 已接 `verify_decision_table` |
| 48 | STOP-3b / MC-1 / MC-2 / MC-3 | 提前停：第一阶段不启用，四条样本都必须跑完全程 | A | 模块已实现，只缺 fixture/command | 已接 `verify_orchestrator` |
| 51 | 丙 / L3-2 / SEC-8-4 / STOP-6 | 转出后超时未回音升级项目统筹 | **A（已接）** | **2026-10-19 已接 `verify_case_watch.py`（51 条）**：阈值默认 2 个工作日且可配、超时前不升级（反向对照）、超时后产生升级事件、目标项目统筹（角色可配）、事件按 case_id 可查、同一 `due_at` 只升级一次而 `due_at` 变化后再升级、日历口径 `weekends_only` 明示 | ✅ 已接 `verify_case_watch` |
| 53 | SEC-4.1-2 | can_finalize 与 release 是两个独立字段 | A | 模块已实现，只缺 fixture/command | 已接 `verify_disposition_router` |
| 54 | SEC-0-1 / SEC-4.3-1 | 三类产物且 IR 是唯一真相 | A | 模块已实现，只缺 fixture/command | 已接 `smoke_end_to_end` |
| 55 | SEC-4.3-2 / SEC-4.3-3 | IR 长期保存、群消息不单独保存 | B | IR 保存期与群消息留存：需法务给定保存期，属阶段 5 合规验收 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 57 | SEC-4.3.1-1 / SEC-4.3.1-2 / SEC-4.3.1-3 | Markdown 渲染必跑、时点、输入输出 | A | 模块已实现，只缺 fixture/command | 已接 `verify_report_render` |
| 59 | SEC-4.3.1-5 | md 与 IR 一致、无遗漏无多出 | **A（已接）** | **2026-10-19 已接 `verify_report_consistency.py`**：用真实渲染器生成报告、验证器**自己解析** finding_id / control_code / decision.state 与 IR 对拍（不在渲染器里自证），并断言 `ReportStore.publish` 对不一致文本**物理阻断**（不落盘、不给 URL） | ✅ 已接 `verify_report_consistency` |
| 65 | L3-4 | 回执禁词 | **A（已接）** | **2026-10-19 已接 `verify_send_gateway.py` 第 7 段（7a/7b/7c）**：四个禁词（通过 / 已通过 / 无需处理 / 审批完成）扫回执文本与卡片 payload；注入 `"本次审批已通过，无需处理。"` 断言**阻断并报出命中词**（证明扫描不是恒真）；反向对照 `"本周审核通过率为 98%"` 不误拦（`(?!率)` 负向断言） | ✅ 已接 `verify_send_gateway` |
| 66 | L4-1 / SEC-8-8 | 群里不刷屏、L4/L5 不被数量吞掉 | A | 模块已实现，只缺 fixture/command | 已接 `verify_report_render` |
| 69 | SEC-5-1 / SEC-5-1b | 七族骨架与 12 个一级分类无遗漏归并 | A | 模块已实现，只缺 fixture/command | 现有 verifier 覆盖不足，留 untested；需补专项 fixture |
| 70 | SEC-5-2 / SEC-5-3 / SEC-5-4 | 族调整必须升版本、留痕、回执记实际版本 | C | 族调整升版本/留痕：控制点版本变更审计未实现 | 补专项验证器或先由委托方确认口径 |
| 71 | SEC-5-5 / SEC-5-6 / SEC-5-7 / SEC-5-21 / SEC-5-23 / SEC-5-24 | 首批 20 真码、安全词、历史码保留 | A | 模块已实现，只缺 fixture/command | 现有 verifier 覆盖不足，留 untested；需补专项 fixture |
| 74 | SEC-5-9 | 新增控制点三条件 | C | 新增控制点三条件：规则+依据+版本联动未实现 | 补专项验证器或先由委托方确认口径 |
| 76 | SEC-5-22 / SEC-5-25 / SEC-5-26 / SEC-5-27 | 唯一归属、码分配登记表、跨族拆分 | C | 唯一归属/码分配登记：登记表与跨族拆分未实现 | 补专项验证器或先由委托方确认口径 |
| 77 | SEC-5-28 / SEC-5-29 / SEC-5-30 / SEC-5-31 / SEC-5-32 | 未知桶四值强制转人工并计数 | A | 模块已实现，只缺 fixture/command | 现有 verifier 覆盖不足，留 untested；需补专项 fixture |
| 78 | SEC-5-33 | rule_code 是唯一机器键、不以 58 子类当全集 | C | **2026-10-19 复核：键名对不上，不能接。** `verify_engine_contract.py` 的 V61 段（8 条：唯一键 / 一条 subclass 至多映射一条 / 三个坏样本必红）验的是 **`rule_key`**，而本行与 Playbook §5 写的是 **`rule_code`**。实测 `research/governance/skeleton/rules-v1.json` 26 条规则全部用 `rule_key`，`rule_code` 出现 **0 次**。<br>V61 的断言本身是好的，但它钉的键名与判据写的不是同一个 —— **接上去等于用 A 字段的验证冒充 B 字段已验证**。 | 先定口径：判据的 `rule_code` 改 `rule_key`（跟随实现），还是规则数据改名 `rule_code`（跟随 Playbook）。定了之后 V61 可直接接，无需改验证器 |
| 85 | SEC-6-GS-1 / SEC-6-GS-2 / SEC-6-GS-3 / SEC-6-GS-6 / SEC-6-GS-7 / L5-4 | 冻结回归集规模、陷阱样本、覆盖、指纹与变更门 | B | 冻结回归集规模/陷阱样本/变更门：属阶段 5 回归治理 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 86 | SEC-6-GS-4 | 回归集维护归属与法务确认 | B | 回归集 owner 与法务确认：人工签署，阶段 5 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 87 | 戊 / SEC-6-GS-5 / SEC-8-6 | 规则变更前后对比读数 | B | 规则变更前后对比读数：依赖冻结回归集，阶段 5 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 100 | RL-12 | 失效时申诉自动暂停，重审后由原申诉人决定是否迁移 | A | 模块已实现，只缺 fixture/command | 已接 `verify_write_api` |
| 103 | RL-15 | 规则变更入口：Web 只读，权威源在别处 | C | 规则只读入口：API 有 GET，但「POST/PUT/PATCH 必须拒绝并留痕」未专项断言 | 补专项验证器或先由委托方确认口径 |
| 104 | TS-1 | 身份绑定 tenant+open_id，开发身份不得进生产 | C | 身份绑定 tenant+open_id/模拟身份：跨写操作的身份矩阵未实现 | 补专项验证器或先由委托方确认口径 |
| 105 | TS-2 | 后端运行时 3.12 下全部既有 verifier 全绿 | B | Python 3.12 全量 verifier 对照：CI/阶段 5 环境门 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 106 | TS-3 | 依赖锁定安装：没有锁就装不上 | B | 依赖锁定安装失败语义：CI/阶段 5 环境门 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 107 | TS-4 | 投影库只是视图：删掉它必须能从文件重建 | A | 模块已实现，只缺 fixture/command | 已接 `verify_atomic_commit` |
| 108 | TS-5 | 前端栈版本锁定与兼容矩阵 | B | 前端栈精确版本与兼容矩阵：阶段 3 前端 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 109 | TS-6 | 前端依赖锁定，开发与 CI 一致 | B | pnpm 锁文件与 CI 一致：阶段 3 前端 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 110 | TS-7 | 路由库为 TanStack Router 且无第二套路由实现 | B | TanStack Router 唯一实现：阶段 3 前端 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 111 | TS-8 | 组件基础为 Radix 原语 + 自有 token，不依赖生成模板 | B | Radix + 自有 token：阶段 3 前端 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 112 | TS-9 | WCAG 2.2 AA：自动 axe + 关键流程人工核验，两者缺一不可 | B | WCAG axe + 人工核验：阶段 3 前端/人工 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 113 | TS-12 | 仅桌面 Chrome 最近两个主要版本，且范围明示 | B | 桌面 Chrome 支持范围：阶段 3 前端 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 116 | TS-14 | 最小视口 1280×720，400% 缩放仍满足 AA | B | 1280×720 与 400% 缩放：阶段 3 前端 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 117 | TS-15 | 容器化部署：可复现、0700、健康检查、重启策略 | B | 容器化部署/卷权限/健康检查：阶段 5 部署 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 118 | TS-16 | 媒体能力全部走容器内跨平台模型，不使用宿主原生能力 | B | 容器内跨平台 OCR/ASR：阶段 3 媒体 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 119 | TS-17 | 阶段一 CPU 优先，不预设 GPU | B | CPU 优先/无 GPU 依赖：阶段 5 部署 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 120 | TS-18 | OCR 候选评测四项读数齐备后才锁版本 | B | OCR 候选评测四读数：阶段 3 媒体 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 121 | TS-19 | ASR 候选评测五项读数齐备后才锁版本 | B | ASR 候选评测五读数：阶段 3 媒体 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 124 | TS-21 | ASR 不做说话人分离，多人完整转写不丢内容 | B | ASR 多人完整转写：阶段 3 媒体 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 128 | TS-25 | 服务端状态与表格库锁定，且无第二套实现 | B | TanStack Query/Table 唯一实现：阶段 3 前端 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 129 | TS-26 | 阶段一不做独立指标看板，只显示必要计数与未测 | B | 阶段一不做独立指标看板：阶段 3 前端 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
