# 【可插入正文】平台侧执法与申诉：TikTok 的公开 SLA/状态机、Meta 的时效数字、以及**对本报告两处结论的实证更正**

> **底稿**：`raw/_sub_ads.md`（472 行 / 59KB；Meta / TikTok / Amazon 广告与上架合规一手证据）。
> **证据分级**：【一手】= 底稿标记「已打开原文」；【一手·已复验】= 本轮我又独立复算/重取过；`[推断]` = 研究者推理；【未找到公开资料】= 官方确实没有。
> **⚠️ 本文件的性质与 `_distill-legal.md` / `_distill-medical.md` 不同**：法律与医疗两支是**纯增量**；这一支在整理过程中发现，**本报告现有的两处结论被本次复算直接证伪**，因此 §1 是更正，§2 才是增量。**请先读 §1。**

---

## 1. 【必须先读】两处结论更正——都由本次实际复算得出

### 1.1 ❌ 证伪：「三家法律 AI 与五家垂直 Agent 均未公开申诉翻案率 → 全行业空白」

本报告 §3.6.3 的结论原文是：

> 「垂直五家中……五家在"误判申诉闭环"上全部缺位或极弱。唯一的替代品是三家分别给出的"回归测试 + 人审队列"……本质上是**厂商侧的质量流程**，不是**用户侧的申诉归途**。」

并在 §3.6 的 `[推断]` 中进一步写成「**一个外部也没人做完的公开空白**」。

**这个结论在"平台侧"不成立。** 本项目自己的证据包里就躺着可算出翻案率的原始数据：

- `research/governance/_evidence/R4/meta-cser-2026Q2.csv`（**5,409 行**，Meta 官方 Community Standards Enforcement Report 的完整 CSV）
- 其中含四个并列指标：**Content Actioned / Content Appealed / Content Restored with appeal / Content Restored without appeal**

`[一手·已复验]` **我用该 CSV 独立复算 2026Q2（结果是本节的核心）**：

| 平台 | Content Actioned | Content Appealed | 申诉率 | Restored **with** appeal | **申诉翻案率** | Restored **without** appeal |
|---|---|---|---|---|---|---|
| **Facebook** | 975,549,000 | 3,742,100 | **0.38%** | 979,400 | **26.17%** | 5,595,600（占已处置 0.574%） |
| **Instagram** | 85,369,600 | 3,380,600 | **3.96%** | 764,100 | **22.60%** | 434,300（占已处置 0.509%） |

同一 CSV 还给出**平台自报的执法精度与假阳性绝对数**（含上下界）：

| 平台 | Enforcement Precision | False Positive（绝对数，区间） |
|---|---|---|
| Facebook | **90.80% – 91.85%** | 30,200,000 – 30,800,000 |
| Instagram | **90.78% – 92.24%** | 9,100,000 – 9,500,000 |

**这三组数字合起来，把本报告那两处结论从"行业空白"改写成"分层事实"**：

1. **申诉翻案率是公开的**（22%–26%），而且是**一等指标**，与"已处置量"并列发布。
2. **申诉率本身极低**（Facebook 0.38% / Instagram 3.96%）——`[推断]` **"申诉率"与"翻案率"必须成对读**：翻案率 26% 听起来很高，但它作用在 0.38% 的基数上；而**无人申诉的那 99.6% 里，有 0.574% 是平台自己撤的**——即**主动纠错量（559 万）是申诉翻案量（98 万）的 5.7 倍**。
3. **精度是有区间的**（不是单点值），且**假阳性以绝对条数发布**（Facebook 约 3,000 万条/季度）。`[推断]` **这是本报告见到的最诚实的质量披露形态**——它同时给了"精度百分比"和"错在哪、错了多少条"，使读者无法只挑一个方向引用。

**`[推断]` 对本项目方法论的含义（比数字本身更重要）**：本报告花了大量篇幅论证"申诉归途是空白、要自己设计"。**更准确的表述是**：
- **平台侧（内容审核）已经做完了**：四指标并列 + 精度区间 + 假阳性绝对数，是可抄的成熟形态；
- **厂商侧（企业软件 / 法律 / 医疗 AI）确实缺位**：它们只公开准确率与节省，不公开申诉翻案率（`_distill-legal.md` §4 与 `_distill-medical.md` §7 均确认）；
- **差别的成因不是能力，是问责对象**：平台要对**内容决定**负责（有透明度报告的法定义务），企业软件只需对**采购方**负责。

→ **建议改写**：把"全行业空白"改为「**厂商侧空白、平台侧已成惯例**」，并把上面四个指标直接作为守衡申诉台账的**字段模板**。这比"没有先例可抄"要有用得多。

### 1.2 ⚠️ 需修正：「Meta 广告审核与申诉的官方原文无法取得」

底稿结论是：Meta 广告审核流程、人审介入条件、广告申诉入口、审核 SLA **全部落在被封的 `facebook.com/business/help/`，本轮彻底没取到**。

**但本项目自己的证据包里已经有这些页面**（抓取日期 2026-09-15，先于本轮）：

| 已存证据文件 | 覆盖内容 |
|---|---|
| `_evidence/R1/meta-ad-bhc-ad-review.md`（**215 行**） | 广告审核流程："review process starts automatically after you create or edit an ad"、"relies primarily on automated technology"、**"in some cases, to manually review ads"**、审核人用于改进系统的表述 |
| `_evidence/R1/meta-ad-bhc-edit-ad.md` | 改稿路径 |
| `_evidence/R1/meta-ad-bhc-advertising-restrictions.md` | 受限情形 |
| `_evidence/R1/meta-ad-enforcement-index.md` / `meta-enforcement-hub.md` / `meta-enforcement-hub-live.md` | "remove, reduce and inform" 三分类（已在项目内） |
| `_evidence/R1/meta-ad-enforcement-counting-strikes.md` | strike 计数规则 |
| `_evidence/R1/meta-enf-restricting-accounts.md` | 账号限制 |

`[推断]` **成因是渠道差异而非事实缺失**：本项目 R4 的抓取经**本机代理 `http://127.0.0.1:7890` + 完整浏览器头**（见 `R4-metrics-and-transparency-evidence.md` 开头自述），而本轮子任务用裸 `curl` 直连，故被 400/403 拦下。**"检索失败被误判为事实缺失"这个失败模式，在本项目里已经是第三次出现了**（前两次见主报告 §1 的两条撤销记录）。

→ **建议改写**：删除"无法取得"的表述；改为引用项目内已存证据 + 本轮新增（§2.2）。

---

## 2. 真正的增量：TikTok 与 Amazon 的**可操作规则**

### 2.1 ★ TikTok：三方中唯一公开「SLA + 状态机 + 申诉终局性」的一家

**为什么这一节最有价值**：法律 AI 三家、医疗两家、以及绝大多数企业软件**都没有公开"时限"与"终局性"**。TikTok 有，而且是运营侧文档（`ads.tiktok.com/help/` 直连可用，无需登录）。

**(a) 审核 SLA（逐字）**——`advertising-on-tiktok-first-things-to-note`（`Last updated: February 2025`）：
> "While some TikTok ads might take longer than usual for the review process to complete, **most are reviewed within 24 hours**."

**小编也给出了审核要素清单**（可直接当判定输入字段表）：
> "Eligibility of the promoted product or services; Ad content (Caption or text / Images or visual content / Audio content); Targeted market and age group; **Consistency between an ad and the landing page; Functionality and eligibility of landing page**"

`[推断]` **"落地页一致性与可用性"被列为独立审核要素**——这一条对守衡有直接映射：**判定对象不应只是"素材文本"，而是"素材 ↔ 落地页 ↔ 目标市场/年龄"的一致性**。这比逐句审文案更接近平台真实的判罚口径。

**(b) ★ 账号健康三态 + 30 天申诉窗 + 终局性**——`account-suspensions`（`Last updated: June 2026`）：

> "You can see how well your account and ads align with our policies in the **Account Health** tab in TikTok Ads Manager. If your Account Health status says **Attention Needed**, there are issues… you'll receive **warning notifications and suggestions to improve**. If your Account Health status is **Poor**, your account **will be suspended**."
> "**Note: Some issues can lead to an immediate suspension if the violation is severe.**"
> "**Temporary suspension** — If this is your first violation, you'll have **30 days** to address the issues with your ads or ad account or **submit an appeal**."
> "**Permanent suspension** — If these issues remain or your appeal is rejected after 30 days, the suspension will be permanent. **You won't be able to appeal this decision.**"

**这是本报告全篇唯一一组同时具备以下四要素的一手规则**【一手】：

| 要素 | TikTok 的答案 |
|---|---|
| **状态枚举** | `Attention Needed`（警告 + 改进建议）→ `Poor`（停号） |
| **绕过分数的直通路径** | "Some issues can lead to an **immediate suspension** if the violation is **severe**" |
| **申诉时限** | **30 天** |
| **终局性** | 永久停号 **"You won't be able to appeal this decision"** |

`[推断]` **这两条机制（严重度直通 + 终局性）正好补上本报告 L4 缺的那一轴**：Abridge 用 Support × Severity 两轴分级（见 `_distill-medical.md` §2.1），TikTok 用一套**状态机**表达同一个意思——**"严重度"不是分数的一部分，而是一条旁路**。而且它明确写了**申诉有终点**：不是无限循环的复核，而是"30 天内解决或终局"。**"申诉次数上限"是本报告其它所有案例都没有公开的东西。**

**(c) 人机边界**——`actor-policy`（`Last updated: August 2025`）：
> "Our review processes **may involve manual reviews or automated tools** to detect policy violations and risky behavior. Depending on the severity of the situation, enforcement actions may include **temporary or permanent suspension from all Bytedance platforms or full traffic control restrictions for TikTok**."

**(d) 规则库形态**：**平铺主题清单**（21 篇主题政策 + 22 篇资源政策，总页 `Last updated: August 2025`），单篇骨架是**「禁止清单 + 例外清单」二元式**（`Examples of what is not allowed` / `In some cases, the following may be allowed`）。

⚠️ **一处必须注意的用词**：**"prohibited / restricted / editorial 三分法"是外部通行说法，TikTok 官方政策总页不使用这组词**（底稿已标 `[推断]`）。官方用 "In some cases… may be allowed" 表达受限。**引用时不得把这组词当作 TikTok 的官方 taxonomy。**

**(e) 版本化**：每页顶部 `Last updated:` 月份，**无独立 changelog / 无历史 diff**【未找到公开资料】。实际取到的版本戳：总页 Aug 2025、First Things to Note Feb 2025、Market-specific Mar 2025、Dangerous Products Apr 2025、Alcohol Sep 2025、Deceptive practices Aug 2025、Actor Policy Aug 2025、Account suspensions **Jun 2026**。

**(f) 数字**：仅 `most are reviewed within 24 hours` + `30 days`。**主动检出率 / 翻案率 / 审核人数量：未找到公开资料。**

### 2.2 Meta：本轮新增的三项（其余已在项目内，见 §1.2）

**(a) 分级执法三分类 + strike system**【一手；与项目内已存证据一致】：
> "Meta takes a three-part approach to content enforcement on Facebook and Instagram: **remove, reduce and inform**."
> "**Reduce** — … We'll often reduce the distribution of this content, **even when it doesn't quite meet the standard for removal under our policies.**"
> "We use a **strike system** to count violations and hold you accountable… Depending on which policy your content goes against, your previous history of violations and the number of strikes you have, **your account may also be restricted or disabled.**"（`taking-down-violating-content`，页注 `UPDATED NOV 12, 2024`）

`[推断]` **"reduce" 这一档是本次调研里最值得守衡抄的一个概念**：**"没到删的程度，但也不给流量"** 是一个**介于通过与否决之间的第三种处置**。本报告 L4/L5 目前只有二值（合规/不合规），而平台的真实处置是**三档以上**。

**(b) 人机边界的官方措辞**【一手】——`/enforcement/detecting-violations/how-review-teams-work/`（页注 `UPDATED NOV 12, 2024`）：
> "**In those instances where our technology misses something or needs more input, we rely on thousands of reviewers around the world to enforce our Community Standards.**"
> "…our technology might be **unsure** whether a post contains bullying… we'll send the post to review teams that have the right subject matter and language expertise… **If necessary, they can also escalate it to subject matter experts on the Global Operations or Content Policy teams.**"

→ **官方只给定性触发词**（misses / needs more input / unsure），**无数值阈值**。`[推断]` 这与 OpenAI Moderation 与 Perspective API 的结论一致：**阈值所有权归部署方，是行业惯例**。注意这里还有**两级升级**（generalist reviewers → subject matter experts），本报告此前未记录"复核本身还有层级"。

**(c) 内容侧申诉五步流程的第 4 步**【一手】：
> "**Option for review** — If people disagree with the decision, they can ask for another review and provide more information."
> "We occasionally make mistakes. If you believe we made a mistake by removing your content, **you usually can let us know**, and we'll take another look."（入口：Facebook 的 **Support Inbox** / Instagram 的 **Support Requests**）

`[推断]` 注意 "**usually** can" 这个限定——**申诉入口本身不是无条件的**。

**(d) 版本化——Meta 是三方最强**【一手】：每政策页有独立 `Change log` 标签，格式为日期 + 变更主题，例如：
```
Oct 22, 2024   Online Gambling and Games
Mar 24, 2023   Cryptocurrency Products and Services
```
`[推断]` **这一条与附录 G4（规则版本只有内容指纹）直接对应**：Meta 给的是**可读的变更记录**，不是 hash。守衡现在有内容指纹（能判断"变了"），但没有"**变了什么、什么时候生效的、因为什么**"。

**(e) 数字**：仅 `Over 15,000 reviewers across the globe` + `more than 80 languages`（各广告政策页页脚复用同一口径）。

### 2.3 Amazon：公开数字最丰富的一家（但均为**买家评论侧 + 公开报告侧**）

**(a) Community Guidelines（买家评论侧）**【一手】：准入须 "**spent $50 on Amazon.com, using a credit or debit card, in the past 12 months**"；分级执法 "If someone violates the guidelines, we may: **Remove their content / Limit their ability to use community features / Suspend or terminate their account / Withhold payments**"；一条罕见的**一罪不再审**规则："If we reject or remove your review for guidelines violation, **you won't be allowed to review that product again.**"

**(b) 申诉/举报入口 4 条并列**【一手】：Report Review Compensation 表单（可传 4 张图）/ 评论下 Report 按钮 / 产品页 "Report an issue with this Product or Seller" / **卖家侧 "Get Support" 或 Account Health Dashboard**。

**(c) 上架侧两层决策 + AHR 双因停号**【一手】：
> "**We make decisions at two levels: what products can be sold, and what requirements must be met to sell them.**"
> "When AHR suspends a seller, it happens for one of two reasons: **Poor historical performance** — A seller's score falls below our thresholds due to accumulated violations… **Having a single critical issue** — Immediate zero-tolerance violations, primarily involving abuse, compliance issues, or confirmed counterfeit."
> "The score **decreases** when a seller incurs policy violations and **improves through violation resolution and successful order fulfillment.**"

`[推断]` 最后一句是**三方里最接近"翻案回流"的官方表述，但它只说了"账号分数回升"，没说"规则会因申诉而改"**。这与 §1.1 的 Meta 数据形成对照：**平台会公开"撤回了多少条"，但不会公开"因此改了哪条规则"**。→ **"裁决回流到规则"这一环，平台侧也是空白。** 这才是本报告真正站得住的"行业空白"表述。

**(d) 公开数字**（全部【一手】，本轮最丰富的一组）：

| 数字 | 原文要点 |
|---|---|
| **99.9%+** | "blocked **more than 99.9% of suspected infringing listings** before a brand owner ever had to find and report them" |
| **3 billion+** | 2018 年主动拦截可疑 listing |
| **5 billion+** | **每日**扫描的详情页改动尝试 |
| **$400M+** | 2018 年投入 |
| **32,000+ / 14 国** | CCU 追诉 bad actors |
| **15 million+** | 2025 年查获并处置的假货 |
| **hundreds of millions** | 2025 年主动拦截的可疑假评 |
| **12 million+** | Omniscan 生成图像集的商品数 |
| **8 天** | 比品牌方自己发现更早拦截侵权 listing |
| **100%** | 新卖家须完成验证 |
| **70+** | 中国区执法突袭行动 |

**(e) 2025 口径的新机制**【一手】：**agentic AI 做审计**——"new agentic AI that **continuously scans for products that may have evaded our existing controls—serving as an audit**"。`[推断]` 这是"**用 AI 审计 AI 的漏网**"，与本报告 §6.1 的"护栏独立调用"同源，但方向相反：不是拦入口，而是**回头查已经进来的**。

**(f) 【未找到公开资料】**：卖家 listing 合规原文（Restricted Products / Condition Guidelines / Product Detail Page Rules / BSSA）**在 Seller Central 登录墙后**，本轮 14 次请求全部失败；因此 **POA（Plan of Action）三要素（root cause / immediate corrective action / preventive measures）的官方措辞未取到**——底稿已明确标注为 `[推断]` 其存在于登录墙内，**不得当作 Amazon 官方要求引用**。**申诉 SLA / 申诉次数限制 / 翻案率：均未找到公开资料。**

> **但是（重要）**：本项目 `_evidence/R1/` 下**已存有 Amazon 的申诉与账号健康原文**，包括 `amazon-appeal-restriction-removal-G200370560`（含 "appeal within two days"）、`amazon-appeal-questionnaire-reinstate-G201623610`、`amazon-account-health-assurance-GGQY933W4RDPJT29`、`amazon-ahr-faq-GR786P4BPEVKTBAG`、`amazon-ahr-included-policies-*`、`amazon-ads-change-log-G8X8M375UPCN4UUC`、以及**完整的 Amazon Ads 政策集（30+ 篇）**。**这些页面在登录墙外，本项目已抓到**——底稿的"登录墙"结论对它覆盖的那几条成立，但**不适用于 Amazon 广告政策与 AHR 部分**。

---

## 3. 三方横向对照（并入 §4.1 案例族 C 用）

| 维度 | Meta | TikTok | Amazon |
|---|---|---|---|
| 规则库形态 | **两轴**：Ad Content（7 大类 / 100 条二级路径）+ Business Assets；每页 `Policy details \| Change log` 双标签 | **平铺主题清单**（21 + 22 篇）；单篇「禁止 + 例外」二元式 | **按对象分体系**：买家社区 / 卖家上架两层 / AHR 绩效分 |
| 处置分级 | `remove / reduce / inform` + strike system → restricted or disabled | `Attention Needed` → `Poor` → 30 天临时 → **permanent（不可再申诉）** + **严重度直通停号** | Remove content / Limit features / Suspend or terminate / **Withhold payments**；AHR **双因停号** |
| 人机边界措辞 | "where our technology **misses something or needs more input**"；两级升级（reviewers → subject matter experts） | "may involve **manual reviews or automated tools**" | "proprietary machine learning" + "dedicated global team of compliance specialists" + agentic AI 审计 |
| **SLA** | 【未找到公开资料】 | ✅ **"most are reviewed within 24 hours"** | 【未找到公开资料】（项目内证据含一处 "appeal within two days"，待核） |
| **申诉时限/次数** | 五步流程含 "Option for review"，措辞为 "you **usually** can" | ✅ **30 天**；永久停号 **"You won't be able to appeal"** | 【未找到公开资料】 |
| **翻案率** | ✅ **可算**：FB 26.17% / IG 22.60%（§1.1，本报告复算） | 【未找到公开资料】（但有"Videos restored"绝对数，见 R4） | 【未找到公开资料】 |
| 版本化 | ✅ **每页 Change log（日期 + 主题）** | 每页 `Last updated:` 月份，**无 diff** | 条款有日期，**政策无 changelog**；Amazon Ads 另有独立 change log 页（项目内已存） |
| 数值型触发阈值 | ❌ 只有定性词 | ❌ | ❌ |

**`[推断]` 三方共性（可直接进 §6.0 速查表）**：**"关键分支的执行者是人还是机器"三方都不隐藏**（都明说"AI 预筛 + 人工兜底/升级"），**但"在什么数值条件下交接"三方都不公开**。这与本报告 §4 C1/C2 的结论完全一致，可视为该结论在平台侧的第四次独立验证。

---

## 4. 并入主报告的具体行

| 主报告位置 | 并入什么 |
|---|---|
| **§3.6.3 结论行（"五家在误判申诉闭环上全部缺位或极弱"）** | **必须改写**：区分**平台侧 vs 厂商侧**。平台侧已成熟（Meta 四指标并列 + 精度区间 + 假阳性绝对数 + 翻案率 22–26%）；厂商侧确实缺位。**并删去"外部也没人做完的公开空白"这一 `[推断]`** |
| **§3.6 的 `[推断]`（"一个外部也没人做完的公开空白"）** | **删除或降级**为：「**"裁决回流到规则"这一环，平台侧同样空白**」（依据：Amazon AHR 只说账号分数回升、未说规则会改；Meta 公开撤回量但不公开规则变更归因） |
| **§1 工具限制 / 证据取得记录** | 新增第三条同类失败记录：**本轮子任务裸 `curl` 被 Meta 400/403 拦下，误判为"官方文档无法取得"；而项目 R4 经本机代理 + 完整浏览器头已抓到同一批页面**。→ 与 §1 已记录的两条撤销合并为一条方法论教训：**"检索失败 ≠ 事实缺失"，且它在本项目已出现三次** |
| **§6.0 共识度速查表** | 新增一行：**「申诉翻案率必须与申诉率成对发布，并同时给精度区间与假阳性绝对数」**——证据强度：**个别但极强**（Meta CSER 四指标并列：Actioned / Appealed / Restored with appeal / Restored without appeal + Precision 区间 + False Positive 区间）。**本报告的 §1.1 复算即为其可用性证明** |
| **§6.0 共识度速查表** | 新增一行：**「处置分级应≥三档：否决 / 限制（降流量）/ 通过」**——证据强度：**两家独立**（Meta `remove / reduce / inform`，其中 reduce 明确"even when it doesn't quite meet the standard for removal"；Amazon 四级含 `Withhold payments`） |
| **§6.0 共识度速查表** | 新增一行：**「严重度应是一条旁路，而不是分数的一部分」**——证据强度：**个别但极强**（TikTok："Some issues can lead to an **immediate suspension** if the violation is **severe**"；Abridge 的 Severity 轴同源） |
| **§6.0 共识度速查表** | 新增一行：**「申诉必须有明确的时限与终局性」**——证据强度：**个别**（TikTok：30 天窗口 + "You won't be able to appeal this decision"）。`[推断]` **这是全篇唯一一家明确写出"申诉有终点"的**，恰好补上 G7 的半个答案 |
| **§6.1 · L4 规则与阈值层** | 补注：**版本化的三档形态**——① Meta **每页 Change log（日期 + 主题）**（最强，可读变更史）＞ ② TikTok `Last updated:` 月份（只知最新，不知改了什么）＞ ③ Amazon 政策无 changelog（最弱）。对照 G4：**守衡今天连"月份"这一档都没有，只有内容指纹** |
| **§6.1 · L5 先例与申诉层** | 补注：**申诉台账的字段模板直接照 Meta CSER 四指标设**（Actioned / Appealed / Restored-with-appeal / Restored-without-appeal），并额外记录**平台自撤量**（Restored without appeal）——`[推断]` 后者是"我们主动纠错"的唯一度量，且必须与申诉分开算 |
| **§6.1 · L8 评测与回归层** | 补注：**精度必须给区间 + 假阳性必须给绝对数**（Meta：Precision 90.80–91.85%，False Positive 3,020–3,080 万）。`[推断]` 单点精度（"准确率 9x%"）不构成可问责的披露 |
| **§5.4（官方承认的产品级失效模式）** | 补强：TikTok 的"**严重度直通停号**"与 Amazon 的"**single critical issue → 立即停号**"是同一机制的两处独立实现——**零容忍类目必须能绕过累积积分** |
| **§6.3 失败模式清单** | 补强一条：**"降流量"这一档缺失会导致二值化误判**——平台承认存在"没到删、但该降"的中间档，若系统只有合规/不合规，这一档会被迫二选一（要么放过、要么误杀） |
| **附 A · 文件清单** | 新增一行：`kb2agent-research/raw/_sub_ads.md`（Meta / TikTok / Amazon 广告与上架合规，472 行）。**并注明：底稿的若干"未找到"结论与项目内 `_evidence/R1/`、`R4/` 的已存证据存在重叠，引用时以项目内已存证据为准** |

---

## 5. 本文件的边界

1. **§1.1 的复算是我做的**（用项目内 `meta-cser-2026Q2.csv`，5,409 行，2026Q2 汇总行），**不是 Meta 公布的比率**——Meta 公布的是四个绝对数指标，**比率是推导值**。对外引用时必须连口径一起说："**由 Meta CSER 公开的 Actioned / Appealed / Restored-with-appeal 三项绝对数推导**"。同时注意：这是**跨该平台全部政策域的汇总**，未按政策域拆分；`[推断]` 分政策域的翻案率差异可能很大，值得单独算。
2. **§1.2 的"项目内已有"是文件级核实**（文件存在、行数、内含关键句），**未逐篇全文复核**；建议引用前打开 `meta-ad-bhc-ad-review.md` 确认具体表述。
3. **底稿的一项 load-bearing 推断**：Meta 的"7 个一级类目"是**底稿作者对路径段的归纳**，Meta 页面本身只暴露二级路径；**100 条二级路径是真实的**。引用时不得把 7 大类写成 Meta 官方 taxonomy。
4. **Amazon POA 三要素**：底稿未取到官方页面用该措辞，已标 `[推断]`；**本文件同样不作为事实使用**。
5. **TikTok 的 "prohibited / restricted / editorial" 三分法**不是官方用词（见 §2.1(d)），**不得当作 TikTok 官方 taxonomy 引用**。
6. **底稿未能启动子代理**（`subagent depth 4 exceeds maxDepth 3`），全部抓取为串行；Internet Archive 间歇宕机，Wayback 需重试循环。**CDX 索引 API 与 `robots.txt → sitemap` 是它发现真实 URL 的两条主要手段**（用它把 3 个猜测的 404 换成了真实页面）——**这两条方法建议写进主报告 §1 的工具记录，供后续复核者复用**。
7. 本文件**不含**对守衡的落地建议；§4 只标明"并到哪一行"。
