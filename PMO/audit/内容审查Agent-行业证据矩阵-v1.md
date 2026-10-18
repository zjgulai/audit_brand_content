# 内容审查 Agent · 行业证据矩阵 v1.2

> ⚠️ **文件名沿用 `-v1`**（本次未改文件名，避免外部引用断链）。**以本行标题版本号为准：v1.2。**
> 版本历史：v1（2026-10-18 初版）→ v1.1（补 F2/F3 诚实标注、E 段根路径、D4–D7 WEAK、检查器设计）→ **v1.2（本版）**

> **这份文件是什么**：把「内容审查 Agent 的行业依据」按**证据强度**分层落成一张可引用的矩阵。
> 它回答的是「我们能引用什么、以什么强度引用、不能外推到哪」，不是「行业普遍怎么做」。
>
> **它不是什么**：不是行业综述，不是选型建议，也不是「成功案例集」。
> 表里大部分条目是**负面证据**（失败模式）与**代码候选**（无部署），只有极少数够格叫案例。
>
> 建立于 2026-10-18。全部读数截至当日，换日或换机会变，引用请带日期。

---

## 〇、三条必须先读的结论

### 1. 具名第三方部署 ≠ 独立效果

| 说法 | 事实 |
|---|---|
| 具名第三方部署 | **不为 0**。有具名客户：Hive/Yubo（4,000 万用户）、Checkstep/Trustpilot（100+ 人审核团队）、TaskUs/Meta（SEC 10-K 点名占其营收 22%）、Besedo/Kaidee（3,000 万用户）、WebPurify/HUD（1,650 万用户）、Keywords/Noice、Samurai/Freedom Games、TELUS/Meta、Genpact/Facebook（海得拉巴 1,600 人） |
| 带独立效果测量的案例 | **0** |
| 平台自建的生产部署 | **充分证实**（Meta CSER / YouTube / TikTok / Reddit / Twitch / Pinterest 透明度报告与监管申报） |

★ 任何「某供应商服务 N 家企业」的说法，**部署事实成立，效果仍为零证据**。两件事必须分开写。

### 2. 独立现场效果测量 = 0

82 个 Web 候选**初筛**出 **3 个最接近「部署事实 + 独立效果」的候选**；**逐条复核后，0 个达到该口径**。

> ★ **「82」这个数从哪来、为什么不是 83（原写 83 已改，说明在此）**
> - **83** 是 2026-10-18 workflow 单次 run 的原始返回：5 路 `cases[]` 长度之和（10+21+13+25+14 = **83**）。
> - **82** 是**去重后**的候选数：其中 1 条在两路里各出现一次（同一 vendor 案例被两个域都抓到）。
> - **复现方式**：读那次 run 的 journal，按 `result.cases[].name` 去重计数：
>   `python3 -c "import json;[...]"` — **口径 = `name` 字符串完全相同即算重复**。
> - ⚠️ **本文件不声称 82/83 可脱离那次 run 复现**：journal 在
>   `~/.claude/projects/…/subagents/workflows/wf_c4567d2e-20c/journal.jsonl`，
>   **不在本仓、不进版本库、换机即失**。引用时只能写「某次 Web 补证的读数」，不能当仓内常量。
> - 这也是 §十三.1 那条「Web 证据全部未经渲染打开」的一部分：**候选数是那次检索会话的读数，不是可重跑的统计**。

| # | 初筛候选 | 复核后的实际性质 |
|---|---|---|
| 1 | EU Commission DSA 两年复核 | **监管汇总**（平台按 Art.20/21 自报，委员会汇总）；且本审计**只拿到搜索索引、无直链**，按 WEAK 处理 |
| 2 | Digital Guardians（arXiv 2501.01256） | **离线学术基准**：1,592 条德语报纸评论，GPT-4o vs Perspective vs OpenAI Moderation —— **不是现场部署** |
| 3 | GradSafe（ACL 2024, arXiv 2402.13494） | **离线学术基准**：ToxicChat 10,166 prompts / XSTest 450 条 —— 测的是 prompt 安全，**不是内容审核现场** |

★ **口径：初筛 3 个 → 复核后 0 个。** 「部署 + 独立现场效果」的答案是 **0**。
不要为了填满矩阵把离线基准或监管汇总写成现场效果。

### 3. 静态/不可变报告的先例 = 0

五个最强案例里，**没有一张**把「静态/不可变报告」做成产品特性。

- DSA Transparency Database 明确是 **rolling 180-day window**，**不是 immutable 固定报告**
- Pinterest 的 DSA 审计只确认了 PinQueue 与申诉流程，没有确认报告不可变性
- Hive 的 Actions Log 在产品文档里**明确写着「不是不可变账本」**

★ **这条我们是在做没有先例的事。** 写方案时不得引用任何「行业实践」来支撑它。

---

## 一、证据分层定义（本文件唯一口径）

| 层级 | 定义 | 能否写成「行业实践」 |
|---|---|---|
| `internal-deployed` | **我方**在生产运行且有读数；**非第三方** | 不能。只能写「我方生产读数」 |
| `independent-audit` | 第三方审计/监管/法院文件，对**流程**做了核验 | 只能说「被审计确认了机制存在」，不能说「证明有效」 |
| `academic` | 同行评审论文，有样本量与指标定义 | 可以说「有独立研究」，必须带样本与口径 |
| `vendor-self-report` | 供应商/客户自报，**无独立复核** | **不能**。只能写「某供应商自报」 |
| `code-only-unproven` | 只有代码/架构，**无部署证据** | **不能**。只能叫「候选参考实现」 |
| `internal-verified` | 我方本机实测**可重跑**且有读数，无外部采用 | 不能。只能写「我方实测（本机可复现）」 |
| `documented-only` | ★ **只有文档声称，脚本/引擎在本机不可达，无法重跑** | **不能**。只能写「文档记录，本机不可复核」 |
| `regulation` | 法规/标准，有一手原文或可核引文 | 可以，但须标证据形态与有效期 |

> ★ **v1.2 新增 `documented-only` 层**：v1.1 把 F2/F3 标成 `internal-verified` 是**错的** ——
> 那两个引擎（`extract_video_asr.mjs` / `extract_video_keyframes.py`）**本仓没有、本机也没装**，
> 读数只存在于文档记录里。`internal-verified` 的前提是「本机可重跑」，不满足就不能占这一格。

---

## 二、矩阵 A · `internal-deployed`（我方生产，非第三方）

| # | 主张 | 来源（本地路径:行） | 可复现性 | 仍运营 | 量化读数与口径 | 可借机制 | 不可外推 | 对应 |
|---|---|---|---|---|---|---|---|---|
| A1 | 既有内容审查流程在飞书生产真实运行 | `PMO/audit/核验-收敛报告-20261017.md:58` | **可复现**（docx raw_content 实读） | 是 | 96/96 份《内容审查报告》；整体 **BLOCK 24 / REVIEW 72**；引用「2026-09-09口径放开」的 15 份 **15/15 BLOCK**。<br>★ **这是产出分布，不是准确率/召回率** | 新系统上线前的**对照基线** | 不是新 Agent 的部署或效果；没有 precision/recall | 验收 **#20**（指标成合同）· 模块 **21** `metrics_read_model` |

---

## 三、矩阵 B · `independent-audit`（第三方审计/监管/法院）

| # | 案例 | 来源 | 可复现性 | 仍运营 | 量化读数与口径 | 可借机制 | 不可外推 | 对应 |
|---|---|---|---|---|---|---|---|---|
| B1 | **Pinterest PinQueue**（DSA 独立审计，2025-11-10，redacted） | `https://help.pinterest.com/sites/default/files/dsa/Independent-Audit-of-Pinterest-DSA-Redacted-11102025.pdf` | **中**：PDF 经搜索索引，未渲染打开；审计本身做 walkthrough + 源码检查 + 抽样测试 | 是 | 审计期**未给 appeal 推翻率**。Pinterest 自报 H2 2024：>1M spam 账号停用 / 25,540 申诉 / possible error rate <1%（**仅 spam 口径，且「possible」未给公式**）。PinQueue 博客较早版本：3M+ items / 600+ queues | ① 600+ 队列，Flask + React/Gestalt<br>② **appeals 自动路由进 PinQueue**<br>③ 审计确认**非 solely automated**<br>④ **6 个月**申诉窗口 + notice email 一键 appeal + RVC 内可申诉<br>⑤ filtering 跳过不必要 review；**sampling 做 QA**；复杂报告升级 team leads/specialists<br>⑥ hybrid enforcement | 审计 PDF 为 redacted；定量数据仅 spam 账号、H2 2024；**不能证明全内容表现** | 验收 **#2 / #4 / #11b / #20**；模块 **15 / 16 / 22 / 19** |
| B2 | **Meta 人审工作台 SRT / pIV / VESPA / HERO**（法院专家报告，2025-12-11，N.D. Cal. 4:22-md-03047） | `https://storage.courtlistener.com/recap/gov.uscourts.cand.401490/gov.uscourts.cand.401490.2537.3.pdf` | **中**：PDF 经搜索索引；部分标 Highly Confidential | 是 | **零效果数字**。规模：Meta DSA H1 2025 称 safety/security 团队约 **40,000 人**；法院报告称 Global Operations 有数千 reviewers。**吞吐/SLA/错误率均未公开** | ① SRT 逐条评估<br>② **pIV** 按 `likelihood × virality × severity` 排序，最高先审，队列动态置顶<br>③ ★ **极高 severity（如 child safety）即使低 virality 也优先**<br>④ HERO 端到端处理高 viral；VESPA 预测 virality；MMS 副本匹配<br>⑤ reviewer 可升级 SME | **是诉讼文件不是同行评审**；引用 Meta 自家透明度页 → 属「独立专家对自述的整理」，**不是独立测量** | ★ 支撑验收 **#8**（高危不被数量吞 · L4-1）；模块 **11 / 15 / 16** |
| B3 | **EU Commission DSA 两年复核**（2026-02-17） | ⚠️ **无可引用直链**，只有搜索索引描述 | **低**（WEAK / 待人工核页） | 是 | 165M 被申诉决定中 **30%（约 50M）被推翻**；H1 2025 **99%** 决定依据平台自身 T&Cs；1,800+ 庭外争议，已结案 **52% 推翻** | 平台按 Art.20/21 自报 + 独立争议机构裁决 + 强制披露决定依据 | **推翻率 ≠ 审核准确率**；底层仍是平台自报；只有庭外争议部分是独立裁决 | 验收 **#20 / #4 / #2**；模块 **21 / 22 / 16** |

> ★ **B3 的使用限制**：本审计**只拿到搜索索引、没有直链**，按 **WEAK / 待人工核页**处理，
> **不得作为独立强证**。若决策包需要一条「申诉推翻率」硬读数，优先用 B1（有 PDF URL）。

---

## 四、矩阵 C · `academic`（同行评审，有样本与口径）

| # | 案例 | 来源 | 可复现性 | 仍运营 | 量化读数与口径 | 可借机制 | 不可外推 | 对应 |
|---|---|---|---|---|---|---|---|---|
| C1 | **AppealMod**（CSCW 2024）· Reddit r/pics（>29M 成员）**4 个月随机 field experiment** | `https://arxiv.org/abs/2301.07163` · `https://dl.acm.org/doi/10.1145/3637296` | **高**（论文有分组与指标定义） | **unclear**（研究原型） | 实验组 **约 70% 放弃申诉**；版主只看 **30%** 初始申诉、**<10%** 毒性申诉；**批准数量与对照组大致相同**；**91.3%** 毒性申诉被放弃/隐藏 | ① **结构化申诉摩擦**：要求补充信息后才进人审<br>② 可解释通知反向用于提升申诉质量<br>③ 摩擦把低信息量/毒性申诉挡在人审之前 | ① 志愿版主 + 封禁申诉场景，**不能直接证明商业内容审核**<br>② **「70% 放弃」可能把真实误判用户挡掉** —— 必须配误拒监测<br>③ 「成功」定义为版主工作量减少，**不是申诉准确性/公平**<br>④ 未报告被误拒用户后续<br>⑤ 单社区；实验后是否继续运行无证据 | 验收 **#20**（L5-3 人工复核台账）· **#4**；模块 **22 / 21** |
| C2 | **DSA Transparency Database 审计**（Trujillo/Fagni/Cresci, CSCW 2025） | `https://arxiv.org/abs/2312.10269` · `https://transparency.dsa.ec.europa.eu/` | **高**（8 平台、前 100 天、全部 353.12M 条） | 是 | **353.12M 条 SoR**（占全库 23.8%）。**实测不一致**：TikTok 报告称 45% 非广告内容自动移除，**SoR 库为 95%**（差 2 倍）；Meta 报告 FB 93.94%/IG 98.44% 自动，但 SoR **未区分全自动/部分自动**；YouTube 单日 SoR 732.4K（中位数 112.8K）且被标非自动；Snapchat 把内部同名 Trusted Flagger 计划写进 SoR，**而当时 DSA 尚未指定任何 Trusted Flagger** | ① Art.17 逐条 statement of reasons<br>② 平台通过 **API 逐事件提交**<br>③ **逐条库 vs 报告汇总的交叉对账** | ① 数据库字段**允许平台自由裁量**，口径不统一<br>② **部分「不一致」可能是定义差异而非错报**<br>③ 覆盖早期（2023），字段后被 Delegated Regulation **2024/436** 调整<br>④ 欧盟 VLOP，**非母婴品牌** | ★ **#20**（L5-5 每个比率带 n）· **#12** · **#5**；模块 **21 / 24 / 12** |
| C3 | **Reddit Modqueue 用户研究**（CHI 2026） | 会议论文（搜索索引） | 中 | 是 | 调查 **110 名**活跃版主、覆盖 **400+** subreddit | 集中 triage / 跨社区队列 / 优先级；论文呼吁更 **modular/integrated infrastructure** | 志愿版主场景；无效果指标 | 模块 **15 / 18** |

> **C2 的正确用法（最容易用错）**：它证明的是「**有逐条记录 ≠ 记录可信**」——
> 同一平台汇总报告与逐条库可以差 **2 倍以上**。对我们的启示是**双轨对账 + 字段词典**，
> **不是**照抄 DSA 字段。

---

## 五、矩阵 D · `vendor-self-report`（自报，无独立复核）

> **本层全部只能写「某供应商自报」。不得写成「已验证」「行业实践」。**

| # | 案例 | 来源 | 可复现性 | 仍运营 | 自报读数（口径多不完整） | 可借机制 | 不可外推 |
|---|---|---|---|---|---|---|---|
| D1 | **Hive Moderation Dashboard**（含 Yubo / Tango / Chatroulette / Plato / Highrise 具名） | `hivemoderation.com` 产品文档与 case study（搜索索引） | 中（产品文档有公开截图与 quickstart） | 是 | Yubo 4,000 万+ 用户、Tango 5 亿+ 注册；**效果数字均为自报，缺样本与口径** | ★ ① Post/User 队列默认各 **10K 上限**，超限替换旧任务<br>② **任务可进多个 feed，但同一时刻只分派给一名审核员**<br>③ 可配每人取件数 / 排序 / **expiry minutes**，超时回收重派<br>④ **Appeals API** 四类（Post/User/Reported Post/Reported User），状态 In Review/Reviewed + overturned/upheld + action_reasons<br>⑤ 审核卡片显示 flag reason、模型分类与分数<br>⑥ **Actions Log / DSA 日志 —— 明确「不是不可变账本」** | 产品文档，**非部署效果**；「audited false positive rate <0.01%」的 auditor 未指名、样本未给 |
| D2 | **Checkstep — Trustpilot** | `checkstep.com/case-studies-trustpilot`（搜索索引） | 低 | 是 | Trustpilot **100+ 人**审核团队（内部+外包），每日数十万条评论；「10,000x」「2.3x」等**无基线定义** | allow/remove/escalate/suspend 工作流；边缘案例升级高级 AI；**模型以 shadow mode 与人审对比** | 供应商 case study，无独立复核 |
| D3 | **Besedo — Kaidee** | Besedo case study（搜索索引） | 低 | 是 | Kaidee 约 3,000 万用户、870 万在架商品；**85% 自动化、94% 广告 5 分钟内上线** | 规则引擎 + 自定义 AI + 人工复核三层 | 同上 |
| D4 | **Samurai Labs — Freedom Games** | ⚠️ **WEAK / URL 未核**：Samurai case study（2023-12-01），**本审计未拿到直链** | 中 | 是 | **340k / 270k** usernames、**4.27%**、recall **88.8%** / precision **99.22%**（本层里样本口径最好的一条） | Username Moderation API | 游戏注册用户名场景，非内容审查；★ **引用前须人工核到原 case study 页** |
| D5 | **TaskUs — Meta** | ⚠️ **WEAK / URL 未核**：SEC 10-K（FY2024，2025-03-06），**未拿到 EDGAR 直链**（可查但本次未定位 accession） | **高**（10-K 是法定披露） | 是 | Meta 占 TaskUs 营收 **22%**；2021 IPO 招股书称约 4,000 名审核员 | 人审外包规模 | 只有规模，无效果；★ **引用前须人工在 SEC EDGAR 按 CIK 核到该 10-K** |
| D6 | **Genpact — Facebook（海得拉巴）** | ⚠️ **WEAK / URL 未核**：路透 2019-02-28 调查，**未拿到直链** | 中 | 是 | **1,600 人**团队，每人每 8 小时约 **2,000 条**（≈每分钟 4 条），准确率**目标 98%**（**是目标不是实际**） | 人审工时基线 | 2019 年读数；目标是目标；★ **引用前须人工核到路透原文** |
| D7 | **Amazon Rekognition + A2I** | ⚠️ **WEAK / URL 未核**：AWS 官方博客（2023-08-15），**未拿到直链** | 中 | 是（**A2I 2026-07-30 起不再接受新客户**） | Amazon Shopping 2022 年 125M 客户、近 1.5B reviews；**每年多约 1M 张图免人审** | A2I：FlowDefinition + work team + human loop；两种触发（ModerationLabelConfidenceCheck / Sampling）；结果写 S3 | **AWS 自家零售团队**，不是第三方客户；A2I 已停收新客；★ **引用前须人工核到 AWS 博客原文** |
| D8 | **Meta CSER H1 2026** | `https://transparency.meta.com/reports/community-standards-enforcement/?locale=en_US` | 中（页面需加 `?locale=en_US`，否则 400） | 是 | FB Content Appealed 8,382,900 / Restored with appeal 2,045,900（**24.4%**）；IG 6,244,700 / 1,430,600（**22.9%**）。★ **分母是被申诉量，不是全部移除量** | 半年度固定周期报告；按 policy 公布 appealed / restored with & without appeal | 全球全内容类型汇总；appeal/restore 跨期口径未完全对齐；**本审计未能交叉验证这两个整数** |
| D9 | **YouTube Transparency Q2 2026** | `https://transparencyreport.google.com/youtube-policy/appeals?hl=en` | 中（JS 渲染，只取到索引摘要） | 是 | removed **11,159,676**；appeals **1,269,277**；reinstated **87,953**（**6.93%**）★ 分母是当季 appeals，跨期未对齐 | 邮件说明决定与「relevant policy or law」；6 个月/1 年申诉窗口 | 无 workbench UI；不能证明非视频内容 |
| D10 | **TikTok CGER Q1 2026** | `https://www.tiktok.com/safety/en/transparency/community-guidelines-enforcement` | 中 | 是 | removed **184,012,576**；automated **178,014,154（96.74%）**；restored **8,838,710（4.80%）**；99.3% proactive；94.4% ≤24h | 公开 corrections log；季度固定报告 | ★ **TikTok 未公布 appeals filed 或 appeal reversal rate**，也未说明 restored 是否来自申诉 —— 关键口径缺口 |

---

## 六、矩阵 E · `code-only-unproven`（只有代码，无部署证据）

> **13 个目录 → 10 个独立代码库。** 去重实测见 §九。
> **全部不得称为「成功案例」，只能叫「候选参考实现」。**

| # | 仓库 | 规模 | 部署面（实测） | 可借机制 | 不可外推 |
|---|---|---|---|---|---|
| E1 | **ad-review-agent**<br>`research/repos/ad-review-agent/` | 55 `.py` / 14,466 行；21 commit **全在两天内**（2026-03-29/30）、单一作者、此后停更 | Docker ✓ CI ✓ **LICENSE ✗**；`grep 'def test_'` = **0** | ① **双读者详情页**（业务 reason / 审员 reviewer_hint，`detail.html:155-171`）<br>② 声明式 `constraints.yaml`（auto_pass=0.92、human_review_forced=0.70）<br>③ 非对称匹配评测 + 四桶<br>④ 双轨置信度聚合（有违规取 max、无违规取 min） | README「替代 80% 人工初审」是 **ADD.md 的目标值**，不是实测；规则是 vivo/中国广告法语境 |
| E2 | **OmniGuard（= PolySafe）**<br>`research/repos/omniguard/`（同源副本 `research/repos/PolySafe/`） | 后端 1,288 行 / 18 `.py`；前端 2,747 行 / 23 TS | **Docker ✗ CI ✗ tests ✗**；单 squash commit（2026-07-11） | ★ **主要价值是反面教材**（见 §七）<br>四区 IA + 任务六阶段回放时间线可作展示骨架 | 演示级；LICENSE 是模板未填（`LICENSE:189` 仍是 `[yyyy]/[name of copyright owner]`） |
| E3 | **crossborder (cbi)**<br>`research/repos/cbi/`（源码扁平副本 `research/repos/cbi_src/`） | ★ **两个口径必须分开**：<br>· **仓内快照**：只有 `backend/` + `README.md`，**test 脚本 3 个**（`backend/scripts/testVisionRecognition.js` 等）<br>· **完整克隆**（`/tmp/repo-xborder`，**非仓内、会过期**）：**117 个测试文件 / 19,421 行**（backend 85 + frontend 32）<br>· backend `.js` 共 **29,778 行** | **Docker ✗ CI ✗ LICENSE ✗**；单日建完即停 | ① **逐字段证据账本** `fieldEvidence`（来源/图片/原文/置信度）<br>② **推测隔离区** `inferredCandidates`<br>③ **地址用稳定锚，不用数组下标** | 验收 443/170 pass **不在仓内快照**，只在 `/tmp/repo-xborder` 完整克隆（**/tmp 会过期，引用须重跑**）；有 117 个测试仍没拦住自身地址缺陷；★ **仓内可核的只有 3 个 test 脚本，117 这个数不可从仓内复现** |
| E4 | **ad-compliance-agent**<br>`research/repos/ad-compliance-agent/` | 84 文件 / ~6.8k 行 | Docker ✓ 但生产清单**全未勾选**；`.env` 硬编码 `D:\AdvertingReview` | RAG 三工具 + 证据分级（confirmed/missing/conflict）+ 规则链「广告表达→规则→适用条件→结论」 | README「4 Agent handoff」实查不存在（单 Agent）；挂 MIT 徽章但**无 LICENSE** |
| E5 | **contract_audit**<br>`research/repos/contract_audit/` | — | 无 Docker/CI/测试 | LangGraph 条件边（仅 High risk 走 redliner，`graph.py:16-28`）；AgentState 分层建模 | 合同条款结构，**不能直接套广告 claim/rule/evidence** |
| E6 | **invoice**<br>`research/repos/invoice/`（同源副本 `research/repos/verify/`） | 44 个测试 + 完整前后端 | systemd/nginx | 规则先行 + AI 可选；coverage 覆盖率 | ★ `DEPLOYMENT.md:17` **含默认 admin 明文密码**；`nginx.conf.example:15` 代理 **8080** 而服务监听 **8000** → 按文档部署会 502 |
| E7 | **sinyard**<br>`research/repos/sinyard/` | 本地工具，夹带 contract_review 模块 | — | NumPy 纯逻辑回归分类器（**不依赖 sklearn**）；可解释正则规则 | README 完全没提合同功能 |
| E8 | **soe-legal**<br>`research/repos/soe-legal/` | 254 行 skill | 纯文档 | 双层审查 + **9 维专项核查表** + 6 类合同差异化清单 | 中国国企合同语境 |
| E9 | **sceneforge**<br>`research/repos/sceneforge/` | 18 文件 / **0 代码** | — | framework-only 模式；隐私/密钥/路径白名单；质检清单（文档层，未实现） | README 明说「不提供一键运行」 |
| E10 | **source-reading-methodology**<br>`research/repos/source-reading-methodology/` | — | — | ★ **零幻觉引用纪律**：引用写成「起始行:结束行:路径」、代码块与源文件**逐字节一致**、静默删行判 FABRICATION、**校验器必须在批量生产之前建好** | 自报 61 节 / 1270 处引用，**仓内只有 3 章样张**，无法复核 |

---

## 七、矩阵 F · 我方实测（**v1.2 拆两层**）

### 7.1 `internal-verified`（本机**可重跑**，无外部采用）

| # | 能力 | 本地路径 | 可复现性 | 量化读数 | 不可外推 |
|---|---|---|---|---|---|
| F1 | macOS Vision OCR | `base/media.py`、`base/ocr_vision.m` | **高**（本机可重跑） | B1 实测有读数 | **无外部采用**；只覆盖图内文字，不含画面语义 |
| F4 | 7 品牌 FDA 用词对照 | `research/governance/R5-category-and-competitors.md:47` | 高 | Momcozy 全站仅 **3 处** FDA 字符串，无 approved/registered/listed/compliant | ★ **「最规范」是 7 品牌相对值，不是法律安全港**；一次抓取不代表现在；M9 那处仍需整改 |

### 7.2 `documented-only`（★ **v1.2 降级**：只有文档声称，本机不可重跑）

> **为什么从 `internal-verified` 降到这里**：v1.1 把它们标成「我方实测」是**过度声称**。
> 这两个引擎的脚本 **本仓没有**（`ls -d kb` → 不存在；远端知识库 `kb/` 下也只有 `l7/`，**无 `l8/`**），
> 本机也没有安装对应工具链。因此**读数只存在于文档记录里，无法在任何可及环境重跑**。
> `internal-verified` 的前提是「本机可重跑」——不满足就不能占这一格。

| # | 能力 | 唯一可核出处 | 可复现性 | 文档记录的读数 | 不可外推 |
|---|---|---|---|---|---|
| F2 | macOS Speech.framework ASR | `skill/kb-media-extractor/references/capability-matrix.md:14`<br>（其中点名的 `l8/extract_video_asr.mjs` **本仓不存在**） | ★ **不可重跑**（脚本与引擎均不可达） | 文档记：14 视频 → **13 条有文本 / 4,236 字** + 1 条 `no_speech`<br>★ **该读数本仓无法复核** | ★ 整段文本、**无逐句时间码** → 产不出 `asr:毫秒区间` ref；ASR 可能误识别，**不得当逐字引用**；★ **对本仓当前形态属「文档声称有、实机不可跑」** |
| F3 | 视频关键帧 OCR | `skill/kb-media-extractor/references/capability-matrix.md:15`<br>（其中点名的 `l8/extract_video_keyframes.py` **本仓不存在**） | ★ **不可重跑** | 文档记：RUN 20261008-4000，11 视频 → **253 帧 → 10,916 字**<br>★ **该读数本仓无法复核** | 重复文本按归一化去重但合并时间窗；★ **引擎本机不可达** |

> ⚠️ **引用纪律**：F2/F3 只能写成
> 「**知识库文档记录**（`capability-matrix.md:14/15`）称……；**本仓无对应脚本，未能复核**」。
> **不得**写成「我方实测」「已验证」「引擎已就绪」。这与 §〇 的三条结论同级 —— 都是「看起来有、实际不可核」。

---

## 八、矩阵 G · `regulation`（**13 条**，含证据形态与有效期）

> ★ **v1.2 口径变更**：v1.1 是 12 条，把「FTC 1984 Policy Statement」与「15 U.S.C. §45」合成一行。
> v1.2 拆成 **G10 / G10b** 两行（**证据对象不同**：一份是机构政策声明、一份是成文法条；
> 且两者的本地证据文件也不同），因此**实算 13 行**。
> 复现：`grep -cE '^\| G[0-9]+b? \|' PMO/audit/内容审查Agent-行业证据矩阵-v1.md` → **13**

| # | 法规/标准 | 主张 | 仓内引用 | **证据形态** | **有效期** | 本地一手证据 |
|---|---|---|---|---|---|---|
| G1 | **21 CFR 807.97** | 510(k) 注册「does not in any way denote official approval」；说成批准构成 misbranding | `R5:40` | **引文已核、原文未落盘** | 现行 | ⚠️ **本地无 eCFR 807 原文**；`_evidence/R2/ecfr-*` 是 **16 CFR**，不是 21 CFR |
| G2 | **FTC HPCG (2022-12)** | 健康益处 substantiation 需 **RCT 级**证据（第 13 页） | `R5:55` | **官方原文** | 现行 | `_evidence/R2/ftc-health-products-compliance-guidance-2022.txt/.html` + `_evidence/R5/ftc/…PDFTEXT.txt` |
| G3 | **EU UCPD 2005/29/EC Annex I §4** | 谎称经机构批准，全欧范围内一律视为误导 | `R5:41` | **引文已核、原文未落盘** | 现行 | 未见 Annex I 原文落盘 |
| G4 | **FDA 官方消费者页** | 「FDA Registered/Certified/Registration Certificate」均为误导性用法 | `R5:42` | **引文已核、原文未落盘** | 现行 | 未定位到该页快照 |
| G5 | **21 CFR 884.5160**（product code HGX） | 电动吸奶器 = Class II，需 510(k) | `R5:21` | **引文已核、原文未落盘** | 现行 | 本地无 21 CFR 原文 |
| G6 | **Santa Clara Principles 2.0 — Notice** | 通知须含 URL/内容片段、**被违反的具体条款**、检测与移除方式、申诉流程 | `R4:1201` | **官方原文（逐字）** | **现行 2.0** | `_evidence/R4/santaclara-2.0.txt` 等。<br>⚠️ 仓内**另有 SCP 1.0 (2018) 已过期版**，引用须指版本 |
| G7 | **DSA 第 17 条** | 平台须提供 statement of reasons（**法定义务**，非建议） | `R8-W3:92`（转述） | ⚠️ **引文/转述已核、Art.17 原文未落盘**（本地只有 **Art.34**，见右列） | 现行（2024-02-17 起全面适用） | ⚠️ **本地落的是 Art. 34**（`_evidence/R8/dsa-art34-eurlex.txt`），**不是 Art.17** —— 引用 Art.17 只能引 `R8-W3:92` 的转述 |
| G8 | **IAB Content Taxonomy 3.x** | 「1 主题分类（37 顶层/704 节点/4 层）+ 6 正交向量」，**不是四维笛卡尔积** | `R6:15` | **官方原文（机器可读）** | 3.1 为当前 | `_evidence/R6/iab-content-taxonomy-3.0.tsv` / `3.1.tsv` |
| G9 | **UK CAP Code 3.7** | 无实证不得声称 | `README:165` | **官方原文** | 现行 | `_evidence/R2/The-CAP-Code.txt` |
| G10 | **US FTC 1984 Policy Statement**（广告实证政策声明） | 五法域「无实证即不得声称」对照之一；「a firm's failure to possess and rely upon a reasonable basis for objective claims constitutes an unfair and deceptive act」 | `README:165` | **官方原文已落盘**（两份，均含实质条文：`reasonable basis` ×10、`Thompson Medical` ×1） | 1984 声明**仍被引用但非唯一现行口径** | `_evidence/R2/ftc-advertising-substantiation-policy-statement-1984.txt`（14,121 B）<br>`_evidence/R5/ftc/ftc-policy-statement-advertising-substantiation-1984.CLEAN.txt`（11,854 B，含 Thompson Medical 判例出处） |
| G10b | **15 U.S.C. §45**（FTC Act §5） | 不公平/欺骗性行为的一般授权条款 | `README:165` | **官方原文已落盘** | 现行 | `_evidence/R2/uscode-15-45-ftc-act-section5.html`（113,894 B） |

> ★ **G10/G10b 拆分说明（v1.2）**：v1.1 把两者合成一行、只挂 §45 的路径，会让读者以为 1984 声明没有原文。
> 实查：**1984 声明有两份本地原文**（R2 抓取件 + R5 清洗件），内容可核。**两者都落盘，不存在「未落」**。
| G11 | **中国《广告法》第 28 条第 1 款第（三）项** | 虚假广告认定 | `README:165` | **官方原文（PDF 提取）** | 现行（2015 施行，2018/2021 修正） | `_evidence/R2/cn-ad-law-samr-pdf-extract.txt` |
| G12 | **FTC/Roca Labs「generally accepted in the profession」三要件** | ①客观执行+相关专家 ②学界公认能产出可靠结果 ③质量与数量都足够 | `R2:1737`、`R5:857` | **官方原文（案例文书）** | **案例判例**（非条文） | `_evidence/R2/ftc-case-roca-labs.html` |

### 三条使用约束
1. **G1/G3/G4/G5 是「引文已核、原文未落盘」** —— 可引 `R5` 的逐字转录，但**不得声称「本地有 eCFR 原文」**。⚠️ `_evidence/R2/ecfr-*` 是 **16 CFR**，不是 21 CFR。
2. **G7 本地落的是 DSA Art. 34，不是 Art. 17** —— 引用 Art.17 只能引 `R8-W3:92` 的转述。
3. **G6 仓内有两版**：2.0（现行）+ SCP 1.0 2018（**已过期**）。引用必须指明版本。

---

## 九、去重与同一性（引用前必须核）

| 关系 | 实测证据 |
|---|---|
| **PolySafe ≡ OmniGuard** | 排除 `.git` 后各 **68 文件**，`diff -rq` 只报 **7 个差异**，其余 **61/68 逐字节相同**；7 处全是改名（README 首行、`index.html:7` title、品牌字样、`.gitignore` 仍写「PolySafe — .gitignore」、`omniguard/README.md:48` 仍写 `cd PolySafe`）。**只能算 1 个案例** |
| `cbi_src` ≡ `cbi/backend/src` | 26 个文件**全部逐字节相同**，只是路径扁平化 |
| `verify` ≡ `invoice`/`sinyard` | 25 个文件中 **24 个逐字节相同**；第 25 个 `sy2_cli.py` 内容为 `404: Not Found` |
| 结论 | **13 个目录 = 10 个独立代码库** |

> ★ **仓内有一处自相矛盾**：`research/repos/跨仓对照-三仓库.md:5-9` 写「三条独立谱系、统计成立」，
> 而 `Playbook/内容审查Agent-产品Playbook-v0.md:537`（G19）写「同一个代码库…推论不成立」。
> **G19 是对的**（本节实测支持）。任何「三仓共识」表述必须按独立样本重算。

---

## 十、16 条措辞修正（逐条 file:line + 替换建议）

> 正面结论先说：`业界最强 / 已被验证 / 实践证明` 五目录 **0 命中**；
> `成功案例` 12 处**全是否定式**。**没有一处把候选写成成功案例。** 下面 16 条是真正要改的。

| # | file:line | 原句 | 替换建议 |
|---|---|---|---|
| 1 | `PRD/内容审查Agent-PRD-优化版-v2.0.md:130` | 「通知里必须有具体条款」是内容审核行业的**公认最低标准**（依据见文末《依据索引》） | 删「行业公认」。改：「在我们核过的 N 份平台政策/法条中，M 份要求通知具体条款（列条款号）」；或只留设计理由。★ 文末《依据索引》1643-1688 共 14 行**无一条**支撑此句 |
| 2 | `PRD/feishu/内容审查Agent-PRD-v1.0.md:256` | 审核报告**最佳实践**采用「摘要+钻取」模式 | 改：「本产品设计假设（未做用户测试）：单次超过 3 条可能超出快速浏览范围」 |
| 3 | `PRD/内容审查Agent-PRD-优化版-v2.0.md:174/176` | 美国母婴内容里**最高频**的违规表述是… | ★ **已自陈撤回**（原文：「那是断言，盘上没有任何测量支撑」）。建议删掉这两行 |
| 4 | `research/governance/R4-trust-and-safety-ops.md:37` | **所有主流平台**政策里都有「兜底条款」 | 改：「我们核过的五家平台（Meta/YouTube/TikTok/Amazon/Google）政策里都有兜底条款」 |
| 5 | `research/governance/R6-peer-practice-and-standards.md:1` | 跨境电商**标杆企业**的内容治理公开证据 | 标题改：「四家 A 股跨境电商上市公司的内容治理公开证据」 |
| 6 | `research/governance/R5-category-and-competitors.md:1230` | 可以直接作为……「**最佳实践模板**」 | 改：「单个样本（Willow，n=1）的脚注格式，可作格式参考；普适性与执法认可未核」 |
| 7 | `research/governance/R5-category-and-competitors.md:2609` | 写入改写建议库作为**最佳实践模板** | 改：「写入改写建议库作为格式参考（n=1）」 |
| 8 | `research/governance/_shards/R7-W3-category-and-coldstart.md:463` | 在品类内是**领先**位置 | 改：「竞品公开面未发现同类规则库；若我们公开结构可能形成差异化——是否领先未测」 |
| 9 | `research/governance/_shards/R7-W2-axis-design.md:2019` | 说明「品类 × 国家」**没有公认的结构** | 改：「在我们核过的三家平台里，品类×法域有三种不同解法，未发现统一结构；是否还有别的结构未核」 |
| 10 | `research/repos/跨仓对照-三仓库.md:197` | 三仓合计只做到 1/3——**照做即领先** | 改：「这是三仓对照中的相对差异项；是否构成行业领先未测」 |
| 11 | `research/repos/跨仓对照-三仓库.md:267` | 这是卡片形态也做得到的**领先项** | 改：「这是卡片形态可实现的差异项」 |
| 12 | `PMO/audit/momcozy-assets/rules/brand_semantic_library.md:336` | 基于…+**行业最佳实践** | 改：「基于 185 图 + 22 视频 + 品牌知识库 + **内部经验**」；若确用行业资料，列标准名与版本 |
| 13 | `research/repos/跨仓对照-三仓库.md:5-9` | 三个不同账号、三种技术栈→「三条独立谱系、统计成立」 | ★ **与 `Playbook v0:537` 矛盾且 G19 对**。改：「三个仓库，其中 PolySafe 与 omniguard 同源，独立样本为 3」 |
| 14 | `Playbook/内容审查Agent-产品Playbook-v0.md:537` | （这条是对的） | 建议**反向操作**：把 G19 这个更正**上提到 v1.1**，并记录「行业产品案例仍为空」这个空缺（v1/v1.1 未承接） |
| 15 | `PMO/audit/核验账本-v1.csv:10,13,21` | 三条未复核的原始发现 | 保持「未复核」标记，**不得在任何下游文档里被当结论引用** |
| 16 | `PRD/内容审查Agent-PRD-优化版-v2.0.md:1133` | PolySafe 视频管道… | 这条是**准确的负面描述**，保留；建议补一句「demo 级，非生产」 |

---

## 十一、外推边界（三条最容易写错的地方）

1. **`code-only-unproven` ≠ 失败案例，也 ≠ 成功案例。** 它们是「可借鉴的形状」，代码本身多数**无许可证不可拷贝**（ad-review、ad-compliance、crossborder、OmniGuard 全部无 LICENSE 或模板未填）。
2. **`vendor-self-report` 的数字一律不可直接引用为效果。** 典型反例：Highrise「99%+ accuracy」（无样本）、Hive Yubo「<0.01% FPR」（auditor 未指名）、Checkstep「10,000x」（无基线定义）、Concentrix「31% of abuse incidents addressed」（分母不明）。
3. **平台透明度报告的口径全部是「全球 + 全内容类型汇总」。** 分母常是「被申诉量」而非「全部移除量」；appeal 与 restore 跨期未对齐；TikTok 甚至**不公布 appeals filed**。不能拿它当我们的准确率基准。

---

## 十二、复现命令

```bash
cd /Users/lute/Project/audit_multi_content

# 1) 去重实测：PolySafe vs OmniGuard
diff -rq --exclude=.git research/repos/PolySafe research/repos/omniguard | wc -l   # 7
find research/repos/PolySafe -type f -not -path '*/.git/*' | wc -l                 # 68

# 2) 三仓部署面
for r in ad-review-agent omniguard cbi; do
  printf '%-16s tests=%s docker=%s ci=%s LICENSE=%s\n' "$r" \
    "$(find research/repos/$r -name 'test_*.py' -o -name '*.test.js' 2>/dev/null | wc -l)" \
    "$([ -f research/repos/$r/Dockerfile ] && echo Y || echo N)" \
    "$([ -d research/repos/$r/.github/workflows ] && echo Y || echo N)" \
    "$([ -f research/repos/$r/LICENSE ] && echo Y || echo N)"
done

# 3) 法规本地证据是否存在（G1/G3/G4/G5 应为空）
ls research/governance/_evidence/R2/ecfr-*          # 注意：是 16 CFR，不是 21 CFR
ls research/governance/_evidence/R4/santaclara-2.0.txt
ls research/governance/_evidence/R8/dsa-art34-eurlex.txt   # 注意：Art.34，不是 Art.17

# 4) 措辞扫描
grep -rnE "行业公认|最高频|最佳实践|标杆|领先|主流|成功案例|业界最强|已被验证|实践证明" \
  --include='*.md' research/repos PMO/audit PRD Playbook research/governance
```

---

## 十三、本文件的边界（照实写）

1. **Web 证据全部未经渲染打开。** 本会话 WebFetch 对所有域名返回安全校验失败、`curl` 全超时，唯一通道是 WebSearch。矩阵 B/C/D 里的 URL 均来自**官方域名/监管 PDF/法院 PDF 的索引内容 + 多次独立查询交叉一致**；凡只在 CSV/图表里的整数，已标 WEAK 或「未证实」。
2. **未能交叉验证的整数**：Meta 8,382,900 / 2,045,900；Meta DSA 3,802,328 / 861,537；X 959,571 / 72,754；EU DSA DB 4,411,790,041 / 375 / 41%；Reddit 154,198,211（且 52.7%+44.7%=97.4%，与 54.4M/154M=35.3% 自相矛盾）。**只能当候选自报**。
3. **B3（EU 2026 复核）无直链**，标 WEAK / 待人工核页，**不得当独立强证**。
4. **矩阵 A 是我方生产读数，不是第三方部署。** 不要与 B/C/D 层的第三方案例混写。
5. **§10 的 16 条措辞修正未经修改验证** —— 本文件只登记「该改成什么」，不声称已改。
6. 本文件**没有执行点**：没有任何检查器会在它与代码失配时变红。它的价值取决于引用者是否按 §一 的分层口径引用。

---

## 十四、建议检查器（★ **仅设计，全部待实现**）

> ⚠️ **这三个检查器一个都还没建。** 本节只是规格，**不是「已实现」**，也**不能**据此说
> 任何一条判据现在被拦住了。按 `AGENTS.md` §2.4：**写进文档的每一条上限/约束，
> 必须能指出是哪一行代码在拦它；指不出来就是注释，不是约束。**
> 本节目前**全部是注释**，状态一律 `待实现`。
>
> 三者都按本仓惯例：**退 0 全过 / 退 1 有红 / 退 2 未测**（未测 ≠ 通过 ≠ 红），
> 且**必须带反向对照** —— 喂已知坏样本必须红，喂已知好样本必须绿（§2.4.1：没红过的断言不算验证过它）。

### 14.1 `verify_evidence_wording.py` — 防 16 条无证据措辞复活

| 项 | 规格 |
|---|---|
| **状态** | `待实现`（文件**未建**） |
| **test_id** | `T-EW-01` 正向全绿 / `T-EW-02` 措辞复活 / `T-EW-03` 白名单被删 / `T-EW-04` 路径指空 |
| **fixture** | `tests/fixtures/evidence_matrix/`（**拟、未建**）：<br>`wording_good.md`（16 条全改干净）· `wording_bad.md`（含「行业公认最佳实践」）· `ledger_15rows.md`（白名单少 1 条）· `dangling_path.md:999` |
| **command** | `python3 tools/verify_evidence_wording.py --fixture tests/fixtures/evidence_matrix/<name>` |
| **预期 rc** | `T-EW-01 → 0` · `T-EW-02 → 1` · `T-EW-03 → 1` · `T-EW-04 → 1` · **fixture 目录不存在 → 2（未测）** |
| **输入** | 本文件 §10 的 16 条表（作**白名单**）；扫描面 `research/repos` `PMO/audit` `PRD` `Playbook` `research/governance` |
| **判据 A** | 对 §10 每个 `file:line`，原句**不得再出现**强断言词（行业公认 / 最高频 / 最佳实践模板 / 标杆企业 / 照做即领先 / 领先位置 / 领先项 / 所有主流平台）—— 命中即红 |
| **判据 B** | §10 每条 `file:line` 必须**真实存在**（路径在盘上 + 行号 ≤ 文件行数）—— 指不到即红（否则「修了」可能只是改了表） |
| **判据 C** | §10 必须**恰好 16 条** —— 少一条即红（防悄悄删掉难改的那几条） |
| **输出** | `A 通过 n/16 · B 通过 n/16 · C 16 条`，有红时列 `file:line` + 命中词 |
| **反向对照** | ① `T-EW-02` 写「行业公认最佳实践」→ A 必须红<br>② `T-EW-03` 白名单删一条 → C 必须红<br>③ `T-EW-04` 指不存在路径 → B 必须红<br>④ **`T-EW-01` 正面**：16 条全改干净 → **必须 rc=0**（否则检查器成砖头） |
| **已知难点** | 不能只查「词是否出现过」——必须**只在 §10 那 16 个位置**查，且要区分「原句」与「引用原句的修正说明」 |

### 14.2 `verify_case_dedup.py` — 防同源案例重复计数

| 项 | 规格 |
|---|---|
| **状态** | `待实现`（文件**未建**） |
| **test_id** | `T-CD-01` 正向全绿 / `T-CD-02` 同源各计一行 / `T-CD-03` 去重声明数字被改 / `T-CD-04` 阈值边界 |
| **fixture** | `tests/fixtures/evidence_matrix/`（**拟、未建**）：<br>`dedup_good.md`（只计 PolySafe 一行）· `dedup_bad.md`（PolySafe 与 Omniguard 各一行）· `dedup_decl_wrong.md`（§九 写 68/68）· `dedup_boundary.md`（差异恰好 8 / 共同恰好 60） |
| **command** | `python3 tools/verify_case_dedup.py --fixture tests/fixtures/evidence_matrix/<name>` |
| **预期 rc** | `T-CD-01 → 0` · `T-CD-02 → 1` · `T-CD-03 → 1` · `T-CD-04 → 0`（**边界值应放行**，>8 才红）· **fixture 缺失 → 2（未测）** |
| **输入** | 本文件 E 段所有 `research/repos/<name>` 引用 + 盘上实际目录 |
| **判据 A** | 对每对仓库跑 `diff -rq --exclude=.git`；**差异项 ≤ 8 且共同文件 ≥ 60** → 判为同源，**不得在矩阵里各计一行** |
| **判据 B** | 同源组必须有一条**显式去重声明**（如本文件 §九），且声明的文件数/相同数要与**实算一致** |
| **判据 C** | `独立代码库数 = E 段行数 − 同源重复数`，**两个数都必须打印**（只打一个等于把口径藏起来） |
| **输出** | `独立代码库 N · 同源组 M · 被合并 K 行` |
| **反向对照** | ① `T-CD-02` PolySafe 与 Omniguard 各计一行 → A 必须红<br>② `T-CD-03` 把 §九 的「61/68」改成「68/68」→ B 必须红（声明与实算不符）<br>③ `T-CD-04` 边界（8 差异 / 60 共同）→ **必须绿**（阈值含等号）<br>④ **`T-CD-01` 正面**：只计 PolySafe 一个 → 必须绿 |
| **阈值依据** | `≤8 差异 / ≥60 共同` 来自 2026-10-18 实测（**7 差异 / 68 文件**）；阈值要写进注释，日后新增同源对要重核 |

### 14.3 `verify_regulation_shape.py` — 防法规证据形态误标

| 项 | 规格 |
|---|---|
| **状态** | `待实现`（文件**未建**） |
| **test_id** | `T-RS-01` 正向全绿 / `T-RS-02` 有原文却标「未落盘」 / `T-RS-03` 标「官方原文」但路径不存在 / `T-RS-04` 16 CFR 误标 21 CFR / `T-RS-05` DSA Art.34 误标 Art.17 / `T-RS-06` Santa Clara 版本未指 |
| **fixture** | `tests/fixtures/evidence_matrix/`（**拟、未建**）：<br>`reg_good.md`（13 行全标对）· `reg_b_mislabel.md`（G2 标「未落盘」）· `reg_a_missing.md`（G1 标「官方原文」而路径不存在）· `reg_d1_16cfr.md`（把 `ecfr-16cfr*` 引作 21 CFR）· `reg_d2_dsa34.md`（把 `dsa-art34-eurlex.txt` 引作 Art.17）· `reg_d3_scp.md`（引 Santa Clara 未指版本） |
| **command** | `python3 tools/verify_regulation_shape.py --fixture tests/fixtures/evidence_matrix/<name>` |
| **预期 rc** | `T-RS-01 → 0` · `T-RS-02…06 → 1`（各 1）· **fixture 缺失 → 2（未测）** |
| **输入** | 本文件 **G1…G12 + G10b（共 13 行）** 的「证据形态」「有效期」「本地一手证据」三列 |
| **行数口径** | ★ **动态取**：`grep -cE '^\| G[0-9]+b? \|'` → 当前 **13**。**不许写死 12**（v1.1 的 12 条口径在 v1.2 拆出 G10b 后已失效）。输出一律按 `n/13` |
| **判据 A** | 标「**官方原文**」的行，其本地路径**必须存在** —— 不存在即红 |
| **判据 B** | 标「**引文已核、原文未落盘**」/「**引文/转述已核、原文未落盘**」的行，其路径列**不得**指向一个存在的原文（否则是误标：有原文却声称没有） |
| **判据 C** | 每行必须有「有效期/状态」且非空（现行 / 已停运 / 案例判例） |
| **判据 D** | ★ **专查三个已知坑**：① `_evidence/R2/ecfr-*` 是 **16 CFR**，不得被引为 21 CFR；② 本地 DSA 落地文件是 **Art. 34**，不得被引为 Art. 17；③ Santa Clara 仓内有 **2.0（现行）** 与 **scp1-2018（已过期）** 两版，引用点必须指版本 |
| **输出** | `A n/13 · B n/13 · C n/13 · D 三坑各 0 命中`（**n 的分母从表行数动态取，不写死**） |
| **反向对照** | ① `T-RS-02` 把 G2（有原文）改「未落盘」→ B 必须红<br>② `T-RS-03` 把 G1 改「官方原文」而路径不存在 → A 必须红<br>③ `T-RS-04` 造「依据 21 CFR 807.97，原文见 `_evidence/R2/ecfr-16cfr255…`」→ D① 必须红<br>④ `T-RS-05` 把 Art.34 引作 Art.17 → D② 必须红<br>⑤ `T-RS-06` 引 Santa Clara 不指版本 → D③ 必须红<br>⑥ **`T-RS-01` 正面**：13 行全标对 → 必须绿 |
| **D 段性质** | 三条是**硬编码的已知坑**（2026-10-18 实测），不是通用规则；新增同类坑要追加到这里 |

### 14.4 这三个检查器**现在都没有**，所以本文件的哪些话当前不受保护

| 本文件里的说法 | 现在谁在拦它 |
|---|---|
| 16 条措辞不会被改回去 | **没有人**。§10 只是登记，代码里没有任何断言 |
| 同源案例不会被重复计数 | **没有人**。§九 是散文，`diff` 只在本文件里被引用，没有常驻检查 |
| 法规证据形态不会被误标 | **没有人**。G1–G12 + G10b（共 13 行）的「形态」列是手填的，没有任何东西校验它 |

★ 换句话说：**本文件 §一 的分层口径，今天完全靠引用者自觉。**
要让它变成约束，得先建 14.1–14.3 三个检查器，并各带反向对照。
在那之前，把这三节读成「已解决」就是 `AGENTS.md` §2.4 点名的那个病。

