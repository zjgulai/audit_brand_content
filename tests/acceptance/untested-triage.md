# 未接验收行分类（T0-10）

> 生成依据：`PMO/audit/验收表-v3-覆盖全部判据-20261017.md`（不改表）。  
> 初始 runner：mapped=86；补 10 条核心 A 后 **mapped=96 / passed=96 / failed=0 / untested=40**，rc=2。  
> **2026-10-19 第二批：新接 3 条（51 / 59 / 65）→ mapped=99 / passed=99 / failed=0 / untested=37**，rc=2。
> **2026-10-19 行 69/71 批次：71 已接（`verify_control_points.py --row 71`）；69 因 12 项清单缺失保持 untested。**
> 本批最终 runner 读数为 **mapped=101 / passed=100 / failed=1 / untested=35**，rc=1；
> 唯一 failed 是 **#78**：并行会话新接的 `verify_engine_contract.py` 映射在 10s
> sandbox 内超时，与行 69/71 无关。#54 在本批运行中途由并行会话修复后已转 passed。
> 全局读数以当次 `verify_acceptance_run.py` 输出为准。
>
> **2026-10-19 35 条重扫：新接 45 / 46 / 74；并行会话接 21。**
> 当前 runner：**mapped=105 / passed=105 / failed=0 / untested=31**，rc=2。
> 未测 31 条分布：**B 22**（阶段 3–5 / CI）、**C 7**（36/43/44/70/76/103/104）、
> **A 2**（69/77）。行 21 的映射由并行 location 会话写入，本批原样保留。
>
> ★ 此前有 **2 条查过之后决定不接**（21 / 78）—— 它们「看起来能接」。
> **21 已在 2026-10-19 location 扩展批次接上**（schema/normalizer/verifier 同步补齐）；
> **78 现已由并行会话接上并在当前 runner 通过**（`verify_engine_contract.py` 映射带 timeout=60 / cpu_seconds=45）。
> 硬接的后果不是「少验一条」，而是**把未验证的东西标成已验证** —— 那比留空更糟。

## 分类计数

| 分类 | 条数 | 含义 |
|---|---:|---|
| A 现在就能补 | 20 | 模块已实现，只缺 fixture/command；已接 18 条，余 2 条（69 / 77）因清单缺失或现有 verifier 覆盖不足留 untested |
| B 阶段 3–5 | 22 | OCR/ASR/前端/部署/回归集/CI，保持 untested |
| C 口径待定 | 8 | 实现或口径有歧义；78 已接，36/43/44/70/76/103/104 因整行仍有未覆盖部分留 untested |

## 逐行

| 行号 | 判据 | 验收动作 | 分类 | 理由 | 下一步 |
|---:|---|---|---|---|---|
| 11 | L1-4b | 非确定性解析（OCR/VLM）结论集合一致 | B | OCR/VLM 非确定性收敛：属阶段 3 媒体能力，当前无真实模型采样环境 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 21 | SEC-3.3.4-5 / SEC-3.3.4.4-1 / SEC-3.3.4.4-2 / SEC-3.3.4.4-3 / LOC-1 / LOC-2 / LOC-3 / LOC-4 / SEC-3.3.4.4-4 / L1-3 | location 三形态可点回原片、帧号与抽帧参数可复算 | **A（已接）** | **2026-10-19 委托方批准「拓展」后已接 `verify_normalizer.py`**：schema 三形态扩为 `text_span{start,end,quote}` / `image_region{image_id,bbox[x1,y1,x2,y2],frame_ref?,frame_thumb?}` / `video_timecode{video_id,time_start,time_end,frame_no,frame_thumb,bbox?}`；`start/end` 与判据的 `char_start/char_end` 等价（在 `base/README.md` 写明，**不新增同义字段**）；normalizer 是唯一组装者，旧对象 bbox 输入规范化为数组；验证器覆盖 quote=text[start:end]、image_id/video_id/frame_thumb 必填、bbox 数组与 0–1 边界、绝对像素拒绝、自然语言位置拒绝、时间 0.1 精度、frame_no 独立复算（换 interval 同步变化）、frame_thumb 实际读取并可解码。**残留未测**：image bbox 裁剪后与 finding 描述一致、frame_thumb 与重抽帧的感知哈希/人工比对（当前无媒体管道/裁图器/抽帧器），已在 README 和验证器输出明说，不冒充已测。 | ✅ 已接 `verify_normalizer.py`；感知哈希/人工比对留阶段 3 媒体管道 |
| 35 | KB-1 / KB-2 / KB-3 / KB-4 / KB-5 / KB-6 / L2-8 / SEC-8-14 | 知识库失败路径三分法 | A | 模块已实现，只缺 fixture/command | 已接 `verify_evidence_sync` |
| 36 | STOP-1 / STOP-2 / STOP-3 / STOP-4 / STOP-5 / STOP-6 / STOP-7 / STOP-9 | 停机条件登记与行为 | C | **2026-10-19 复核：** `verify_case_watch.py` 覆盖「转出→超时→升级项目统筹」一角，`verify_orchestrator.py` 覆盖不提前停；但行 36 还要求停机登记恰 6 条且状态 `not_applicable_stage1`、P0/P1/P2/P3 全不提前停、failure_kind 回执/IR 记录、依据只查一次等复合判据，无单一执行点 | 补 STOP 登记与行为专项验证器；当前保持 untested |
| 37 | V1 / V2 / V4 / V5 | 视频五项覆盖声明与关键帧读数 | A | 模块已实现，只缺 fixture/command | 已接 `verify_report_render` |
| 43 | SEC-0-2 | 强制词均可证伪（元判据） | C | 强制词均可证伪（元判据）：人工通读，无机器样本 | 补专项验证器或先由委托方确认口径 |
| 44 | IN-2 | 判定输入来源可追溯 | C | 判定输入来源可追溯：人工沿 pipeline 追字段，无自动判据 | 补专项验证器或先由委托方确认口径 |
| 45 | EQ-1 | E01-E14 只是等价展开、不得成第二套规则 | **A（已接）** | **2026-10-19 D-125 采纳 C-45 建议：15 链覆盖即门，E01–E14 逐格对拍降为一次性 golden、不进 CI。** `verify_decision_table.py` 的 A01–A15 逐链断言 chain/state/layer/external_label；H3a–H3c 再与独立期望表对拍 | ✅ 已接 `verify_decision_table` |
| 46 | L2-1a | 判定逻辑只存在于 §3.3.8.1 | **A（已接）** | **2026-10-19 D-125 采纳 C-46 建议：全仓静态扫描。** `verify_decision_table.py` J1 扫 base/api/tools 全部 .py；除白名单 `base/orchestrator.py`（parse_status=failed 契约回退，理由已登记）外，任何模块写 state/external_label/layer 即红；J5 反向对照证明扫描器会命中 | ✅ 已接 `verify_decision_table` |
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
| 69 | SEC-5-1 / SEC-5-1b | 七族骨架与 12 个一级分类无遗漏归并 | A | **2026-10-19 已加条件执行点**：`verify_control_points.py --row 69` 校验七族骨架；若 `research/governance/category-to-family-v1.json` 存在，则校验 12 项、category 唯一、family ∈ 七族、count 一致。**盘上当前没有 12 项一级分类清单，不编造** → 该命令退 2，行 69 保持 untested | 待产品提供 12 项清单后落上述 JSON，**再把行 69 接到 `--row 69`**（命令已就绪）；在此之前保持 untested，不接为 passed |
| 70 | SEC-5-2 / SEC-5-3 / SEC-5-4 | 族调整必须升版本、留痕、回执记实际版本 | C | **2026-10-19 复核：** `verify_control_points.py` 的 H-2..H-5 已检查历史字段/最后版本/码集合/族归属一致，`--selftest` ⑫ 证明「改族未升版本」会红；但「改族→版本号加一且追加显式历史条目」的正样本、以及回执记实际使用版本仍未落在同一执行点（后者见 `verify_orchestrator` C5，且是注入值） | 补正样本 + 回执实际版本串联；当前保持 untested |
| 71 | SEC-5-5 / SEC-5-6 / SEC-5-7 / SEC-5-21 / SEC-5-23 / SEC-5-24 | 首批 20 真码、安全词、历史码保留 | **A（已接）** | **2026-10-19 已接 `verify_control_points.py --row 71`**：B-1 断言码集**精确等于** H01–H09/M01–M07/U01–U04；B-2 断言 `安全词` 不是控制点码；B-3 断言安全词已落白名单或显式退役；B-4 对每个 active 码反查 enabled 规则且 external_ref 非空；B-5 断言 U02 存在、deprecated、无 enabled 规则；B-6 对历史每条 `codes` 快照断言首批码不消失；B-7 有 `name_by_code` 时对拍语义、没有时不冒充 | ✅ 已接 `verify_control_points --row 71` |
| 74 | SEC-5-9 | 新增控制点三条件 | **A（已接）** | **2026-10-19 D-125 采纳 C-74 建议：校验入口放 `verify_control_points.py`。** C74-0..4 分别检查新增码缺规则/依据/版本/版本未递增；`--selftest` ⑬⑭用坏样本证明这些断言会红、⑪好样本会绿 | ✅ 已接 `verify_control_points`（默认 + `--selftest`） |
| 76 | SEC-5-22 / SEC-5-25 / SEC-5-26 / SEC-5-27 | 唯一归属、码分配登记表、跨族拆分 | C | **2026-10-19 复核：** C76-1/2/3 已覆盖 family 单值且在族清单内、跨族拆分必须带批准、同码跨族；但行 76 还要求「首字母与族不一致时按 family 走」并跑路由/报告，验证器没有该行为样本 | 补前缀不一致的路由/报告样本；当前保持 untested |
| 77 | SEC-5-28 / SEC-5-29 / SEC-5-30 / SEC-5-31 / SEC-5-32 | 未知桶四值强制转人工并计数 | A | 模块已实现，只缺 fixture/command | 现有 verifier 覆盖不足，留 untested；需补专项 fixture |
| 78 | SEC-5-33 | rule_code 是唯一机器键、不以 58 子类当全集 | C | **2026-10-19 二次复核（D-126 之后）：术语障碍已消除，但仍有两条验法没有执行点，仍不能接。**<br>**已解决**：Playbook `0b26bbc6…` / 验收表 `ed26e413…` 已统一为 `rule_key`（`rule_code` 在两者中均 0 处），V61 段的键名现在与判据一致。<br>**仍然对不上的部分** —— 行 78 的「怎么验」有三条，V61 只覆盖第一条的一半：<br>① 「所有机器连接与报告生成都以 rule_key（或 control_code）为键」→ V61e 只查了 `reject.hits` **一个样本**的键，没有全仓扫描；`tools/audit/report_render.mjs` 用的是 `control_code`（符合「或」），但同样没有断言钉住。<br>② 「控制点数量口径来自主表而不是 58」→ **全仓无任何断言**（`verify_control_points.py` 的 CP-2 查的是码重复，不是数量口径）。<br>③ 「构造一份只按 58 子类统计的报告，断言与主表口径不一致时报警」→ **全仓无实现**：`base/` 下 `subclass` 出现 0 次，无报警路径。<br>**若现在接上，runner 会把「键名唯一」记成「整条 SEC-5-33 已验证」—— 那是把 1/3 的覆盖说成 3/3。** | 补 ②③ 的执行点后可接：② 在 `verify_control_points.py` 加「控制点数量以主表行数为准、与 58 子类计数不等价」；③ 加「构造纯 58 口径报告 → 与主表口径比较 → 不一致必须报警」的正反样本。这两条补完后 V61 + 它们一起接行 78 |
| 85 | SEC-6-GS-1 / SEC-6-GS-2 / SEC-6-GS-3 / SEC-6-GS-6 / SEC-6-GS-7 / L5-4 | 冻结回归集规模、陷阱样本、覆盖、指纹与变更门 | B | 冻结回归集规模/陷阱样本/变更门：属阶段 5 回归治理 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 86 | SEC-6-GS-4 | 回归集维护归属与法务确认 | B | 回归集 owner 与法务确认：人工签署，阶段 5 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 87 | 戊 / SEC-6-GS-5 / SEC-8-6 | 规则变更前后对比读数 | B | 规则变更前后对比读数：依赖冻结回归集，阶段 5 | 阶段 3–5 环境/模块落地后接；当前保持 untested |
| 100 | RL-12 | 失效时申诉自动暂停，重审后由原申诉人决定是否迁移 | A | 模块已实现，只缺 fixture/command | 已接 `verify_write_api` |
| 103 | RL-15 | 规则变更入口：Web 只读，权威源在别处 | C | **2026-10-19 复核：** C-103 已落地并接 `verify_review_api.py` C7–C10：三个只读入口的 POST/PUT/PATCH/DELETE 全部 403、每次写拒绝恰好一行 JSONL 审计、GET 不记日志；但行 103 后半「从既有权威源同步拉取、变更后自动触发重审（对照行 94 失效链路）」仍无执行点 | 补权威源同步→重审链路；当前保持 untested |
| 104 | TS-1 | 身份绑定 tenant+open_id，开发身份不得进生产 | C | **2026-10-19 复核：** C-104 已落地并接 `verify_review_api.py` C11–C17：生产缺 `tenant_id/open_id` → 401 + 审计、生产模拟身份 → 403 + 审计、dev 显式开关放行、启动校验、principal tenant 与 session 不一致 → 403；但行 104 要求对提交/复核/申诉/签发/撤回/豁免每个写操作各跑 a/b/c 三样本，并校验 principal tenant 与**案件** tenant 不一致 —— 跨写矩阵尚未覆盖 | 按写操作矩阵补断言；当前保持 untested |
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
