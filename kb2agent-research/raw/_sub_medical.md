# 医疗 AI 临床文档产品：合规/知识架构、人审边界与 FDA 监管路径

**调研方法说明（重要）**
本次全部结论来自 `web_fetch` / `curl` **实际抓取并解析的原文**（含 PDF 全文抽取）。`web_search`、`read_page`、`exa_search` 全程未使用。
- `www.fda.gov` 直接 curl 全部 404/空响应，故 **一律经 `https://web.archive.org/web/2024|2025/<原始URL>` 前缀**抓取（服从任务给定约束）。
- `www.nuance.com/healthcare/*` **现已 302 到 Microsoft 页面**（三份不同 URL 返回字节完全相同的 166,321 字节 Microsoft 模板）；Nuance 原始 DAX Copilot 内容须经 Wayback 2024 快照获取，已在文中标注。
- Wayback **CDX API 本次全程 "Temporarily Offline"**，无法做 URL 枚举；所有 URL 均为手工拼装后**逐个验证 HTTP 200 + 实际内容**，无一杜撰。
- 全文**未使用任何"仅搜索摘要"来源**，故证据强度栏中所有条目要么是「已打开原文」，要么明确写「未找到公开资料」。

---

## 一、Abridge（abridge.com）

### 1. 它解决什么 / 目标用户
面向**大型企业级医疗系统**（非个体诊所）的临床对话 AI 平台，三大产品线：Clinicians（临床文档）、Revenue Cycle（收入循环/计费文档）、Nursing（护理文档）。核心主张是把「诊室对话」当作医疗系统里最有价值的信号，用 AI 承接下游全部文书工作。

原文（已打开原文，https://www.abridge.com/ ）：
> "We believe we can help fix the system by anchoring on the conversation, the most human signal in healthcare."

规模定位（已打开原文，https://www.abridge.com/blog/context-aware-clinical-intelligence-for-every-clinician-partner-systems ）：
> "300+ enterprise health systems representing 250 million patients"

### 2. 规则库怎么组织（AI 输出如何被"规则"约束）
Abridge 的公开材料把"规则"拆成**两层**，而不是一份临床指南库：

**(a) 事实性护栏层（claim-level guardrails）** — 目标不是"审核医学正确性"，而是**逐条 claim 的"是否有原文支撑"（supported / unsupported）**。原文（已打开原文，https://www.abridge.com/ai/science-confabulation-hallucination-elimination ）：
> "The Abridge system for ensuring accuracy in AI-drafted documentation has two components: 01 A proprietary, task-specific AI model for detecting unsupported claims in draft documentation 02 An automated system for correcting unsupported claims, leveraging the conversation transcript and EHR context"

检测模型的训练数据组织方式（同页）：
> "an in-house, task-specific language model trained on a curated set of **over 50,000 training examples**. Our data combine both open-source datasets for hallucination detection in the general domain and domain-specific examples (transcripts, EHR context, and example notes) that cover the breadth of scenarios where unsupported claims can arise in practice."

**双层分类学（这是其"误判分级规则库"的核心）**：
- 轴一 **Support（支撑度）**：Supported / Not supported / **Contradiction**（"A statement is classified as a 'contradiction' if it directly conflicts with statements made in the transcript."）
- 轴二 **Severity（严重度）**：**Major / Moderate / Minimal** 三级。原文定义：
  > "An unsupported claim should be classified as 'major' if most clinicians would agree that, if left uncorrected, the claim would most likely have a negative impact on clinical care and/or has a non-trivial chance of leading to substantial harm."
  > "Any inaccurate claim that could plausibly impact patient care should be rated at least 'moderate'."
  > "An inaccurate claim is classified as 'minimal severity' if most clinicians would agree that it has little to no impact on clinical care, either in the short or long term, even if left uncorrected."

**(b) 临床决策支持层（CDS）内容源** — 走**外部权威文献授权**路线，不自建指南库。原文（已打开原文，https://www.abridge.com/cds ）：
> "Abridge clinical decision support brings together insights from leading sources of medical evidence." / "*American Heart Association licenses selected scientific content to Abridge."

且在 https://www.abridge.com/platform/clinicians 明确列出内容伙伴：
> "Clinical insights from trusted sources—including UpToDate, the New England Journal of Medicine, and JAMA—contextualized to the encounter, surfaced the moment you need it."

**CDS 的"可信证据"排序规则由临床医生手工制定，而非算法决定**（已打开原文，https://www.abridge.com/blog/clinician-builder-cds ）：
> "Within each of these content sources, not all evidence has equal weight for each clinical situation. Is the right source a specialty society guideline? The primary literature? A review article? An opinion piece? Those carry very different weight at the point of care, and knowing how to rank them, and when, **is not a question an algorithm can settle on its own.**"
> "This clinical input shaped CDS at every level: which content partnerships we pursued, how the search prioritizes across those sources, and how results are displayed to a working clinician."

### 3. 案例库怎么组织
Abridge 没有公开"案例库"这一形态；它公开的是**评测数据集（benchmark sets）**，且明确区分公开与自建：

已打开原文，https://www.abridge.com/ai/science-ai-evaluation ：
> "we use several benchmark datasets, including: **Over 10,000 hours of medical conversations** / Internal (non-public) datasets of patient-clinician encounters / Over 10,000 hours of clinical conversations with associated audio, gold-standard reference transcripts, and human annotations. / Curated 'challenge datasets' Designed by our team to pose difficulties and probe weaknesses of clinical ASR models, including clinical conversations laden with new medication names. / Standard research benchmark datasets Such as the Librispeech benchmark dataset."

多语种评测数据集（同页）：
> "One of the datasets we use in evaluation is **FLEURS**, a parallel speech dataset in 102 languages built on top of the machine translation FLoRes-101 benchmark."

**真实案例回流机制**（同页）——由用户自由文本反馈反推出新的测试用例：
> "**New medications are continuously being released** — Does the documentation correctly spell medications that the models have not encountered previously? / **Many visits include multiple speakers** — Given an infant patient, a parent, and a clinician, does the documentation appropriately distinguish between the parent and the (non-speaking) patient? / **Clinicians and patients do not always agree** — If a patient misstates their own diagnosis, and a clinician corrects them, is the conclusion appropriately reflected in the final note?"

### 4. 误判与申诉 / 复核怎么走
这是 Abridge 公开度最高的部分，分**四条互不相同的通道**：

**(a) 上线前的盲评 + 分阶段放行（staged release）** — 已打开原文，https://www.abridge.com/ai/science-ai-evaluation ：
> "Before we release any major model updates, we perform **blinded head-to-head evaluations with our own clinical staff**, and collect rich feedback from staged deployments to alpha and beta users."
> "The first stage is an **'alpha' release with limited rollouts to specially trained early adopters**. These clinicians are in frequent contact with Abridge staff and are trained to be especially vigilant about editing and comprehensive in their feedback. Only once we are satisfied that these users are better served by the improved model do we consider rolling out to wider audiences."

统计方法（同页，含脚注引用）：
> "To allow for early stopping when the results are conclusive, we use **anytime-valid sequential hypothesis testing**, providing guarantees on the false positive rate that hold regardless of how long we run the trial."

**(b) 上线后被动信号 = "医生改了多少"** — 同页：
> "we capture **edits made to the AI-generated note before they are finalized** shared in the medical record. Clinician-generated edits are inherently scalable as a feedback mechanism, as editing is already a natural workflow."
> "we continually collect both **active feedback** in the form of comments and star ratings, and **passive feedback** in the form of edits required to finalize the note"

**(c) 专用审计工具：Linked Evidence（逐句回溯对话）** — 同页：
> "Ongoing audits of note quality are essential for building and maintaining trust. However, audits can be inefficient—to evaluate the appropriateness of a single note sentence, an evaluator must parse a long transcript of a conversation that they have never seen before. To aid in efficient review, **we outfit all of our note viewers with a tool for pinpointing the relevant transcript excerpt.** This same feature is available to our clinician users, helping them to verify the output of our system during the editing process."

**(d) 严重度申诉语义**：分级本身即是"哪些错误必须拦、哪些可放过"的判据；上述 Major/Moderate/Minimal 定义中反复使用 "most clinicians would agree"，即**以临床医生共识而非固定阈值**作为判据。

**未找到公开资料**：Abridge 面向客户/监管方的**审计日志具体字段、保留期限、谁可查阅**在任何抓取到的官方页面中均未披露。仅有间接项：BAA 中的账簿查阅权与披露会计义务（见第 4 节末尾）、以及 https://www.abridge.com/platform/clinicians 的 "Analytics & Reporting — Track and monitor Abridge usage across your entire health system" 与 "Custom GOVERNANCE Control — Customize Abridge to fit your compliance and governance"。

### 5. 人机分工边界（最强的公开表述集中在此）
**(a) 强制人审、且责任在医生** — 已打开原文，https://www.abridge.com/ai/science-confabulation-hallucination-elimination ：
> "**All clinician notes generated by Abridge are reviewed and edited (if necessary) by the clinicians who conducted the patient encounter before being entered into the EHR.** No guardrail is perfect, and clinical conversations can contain legitimate sources of ambiguity, for instance, where the 'correct' note may rely on clinical judgements that were not verbalized during the encounter."

同文摘要处再次强调：
> "we stress that even amidst this progress, **clinician review of AI-generated notes remains essential. Clinicians are required to review and verify their own notes before filing in the electronic health record (EHR).**"

**(b) 三个能力面向** — 已打开原文，https://www.abridge.com/ai ：
> "**Provenance tracking for accountability**: Our software allows clinicians to validate each part of a generated note against the underlying patient conversation transcript and audio recording."
> "**Control through intuitive UIs**: We've developed workflows that keep clinicians in charge through user-centric interfaces. Our tools help clinicians **review, fact-check, and revise AI-generated notes before signing off.**"
> "**Guardrails for reliability**: Our team is innovating techniques for preventing mistakes before they happen, catching them before they hit production, and learning rapidly from feedback whenever we fall short."

**(c) 责任归属的设计原则** — 已打开原文，https://www.abridge.com/blog/building-trusted-healthcare-ai （2025-11-12, by Tim Hwang）：
> "**Transparency Builds Trust**: Building a vision for artificial intelligence in healthcare that puts the judgment of the clinician at its center requires designing systems that are easily auditable. **With Linked Evidence, Abridge-generated draft clinical documentation is traceable to the source conversation.** We make it easy for clinicians to verify, question, and trust the technology that supports their work."
> "Our design approach envisions **assistance as a fundamentally humble feature**, which respects the role of clinician judgment and ultimately enables better human-to-human conversation."

**(d) CDS 侧的 "clinician-in-the-loop" 定义** — 已打开原文，https://www.abridge.com/cds ：
> "**Clinician-in-the-loop**: Clinicians decide what information matters, what to include in notes, and what actions to take."

**(e) 免责/责任切割（条款层）** — 已打开原文，https://www.abridge.com/terms/clinician ，§11 Representations, Warranties, and Disclaimer：
> "**ABRIDGE DOES NOT REVIEW, MONITOR, EVALUATE, OR ANALYZE ANY INFORMATION GENERATED FROM OR BY PATIENTS FOR ANY MEDICAL PURPOSE. ABRIDGE DOES NOT ENGAGE IN THE PRACTICE OF MEDICINE AND DOES NOT PROVIDE ANY MEDICAL ADVICE OR DIAGNOSES TO PATIENTS. IT IS YOUR RESPONSIBILITY TO DISPENSE MEDICAL ADVICE TO OR MAKE DIAGNOSES FOR YOUR PATIENTS BASED ON YOUR PROFESSIONAL JUDGMENT, YOUR REVIEW OF ANY USER CONTENT OR PATIENT DATA USING THE ABRIDGE SERVICES OR THE PLATFORM AND YOUR EVALUATION OF YOUR PATIENTS.**"

同条免责：
> "THE ABRIDGE SERVICES ARE OFFERED AND PROVIDED 'AS IS' AND ON AN 'AS AVAILABLE' BASIS, WITHOUT WARRANTY OR CONDITION OF ANY KIND... INCLUDING WITHOUT LIMITATION ANY WARRANTIES OF MERCHANTABILITY, SATISFACTORY QUALITY, **ACCURACY**, NON-INFRINGEMENT, FITNESS FOR A PARTICULAR PURPOSE, OR THAT THE ABRIDGE SERVICES WILL BE AVAILABLE, COMPLETE, ADEQUATE, RELIABLE, ERROR-FREE OR UNINTERRUPTED."
> "**YOU ALSO AGREE THAT THE ABRIDGE SERVICES ARE NOT INTENDED TO BE USED IN A MEDICAL EMERGENCY.**"

责任上限（同页 §13）：
> "IN NO EVENT WILL OUR OR OUR LICENSORS OR SUPPLIERS' AGGREGATE LIABILITY... EXCEED **THE GREATER OF $1,000 OR THE AMOUNT PAID OR PAYABLE TO ABRIDGE** UNDER ANY AGREEMENT, SOW, OR ORDER FORM IN THE PREVIOUS TWELVE (12) MONTHS."

**(f) 翻译能力的产品级免责** — 已打开原文，https://www.abridge.com/ai/science-ai-evaluation ：
> "**Abridge is not designed to serve as a translation service, and it is no substitute for a trained medical interpreter.**"
> "it is our responsibility to continuously improve the Abridge platform and ensure safety, accuracy, and quality"

### 6. 审计日志 / 可追溯性 / 留存（分项）
| 项目 | 公开内容 | 出处 / 强度 |
|---|---|---|
| 可追溯性机制 | Linked Evidence：AI 生成的每个 summary span 可回溯到对话 transcript + 音频；"tying every summary span back to substantiating evidence in the underlying conversation" | https://www.abridge.com/ai ，https://www.abridge.com/ai/science-ai-evaluation ，https://www.abridge.com/abridge-contextual-reasoning-engine —— **已打开原文** |
| 审计日志字段/保留期 | **未找到公开资料** | — |
| 电子记录保管者查阅权 | BAA §2.9 Access to Books and Records：向部长（Secretary）开放内部实践、账簿与记录 | https://www.abridge.com/terms/business-associate-agreement —— **已打开原文** |
| 披露会计（accounting of disclosures） | BAA §2.10：收到请求后 **30 天内**提供 45 C.F.R. §164.528 所需信息 | 同上 —— **已打开原文** |
| 个人查阅/更正 | BAA §2.8：Designated Record Set 内 PHI 须在 **15 个工作日内**可供查阅与复制（45 C.F.R. §164.524） | 同上 —— **已打开原文** |
| 违规通报时限 | BAA §2.4：非许可使用/披露及安全事件 **10 个工作日内**通知；确认的未加密 PHI 泄露须在发现后**不超过 30 个日历日**内书面报告 | 同上 —— **已打开原文** |
| PHI 返还/销毁 | BAA §4.3：终止时返还或销毁全部 PHI；并承认 §4.4 实际多数情况下"不可行返还或销毁"、需按其条款保留 | 同上 —— **已打开原文** |
| 一般数据留存 | 隐私政策 §10：留存至"ongoing legitimate business need"消失为止，与客户数据的留存依客户协议 | https://www.abridge.com/privacy —— **已打开原文** |
| 声纹生物数据留存 | 至目的满足为止；**最后一次使用移动应用后一年**、账户删除或用户请求时永久销毁（含备份） | 同上 —— **已打开原文** |
| 安全控制（产品页） | Single-Sign On；**256-bit encryption in transit and at rest**；美国境内数据中心；HIPAA Compliant | https://www.abridge.com/platform/clinicians —— **已打开原文** |
| SOC 2 / HITRUST / ISO 认证 | **未找到公开资料**（官网可爬页面中无安全/信任中心页；sitemap 中亦无 security/trust 路径） | — |

### 7. 可量化公开数字（全部「已打开原文」）
| 数字 | 内容 | 出处 |
|---|---|---|
| **12.7% / 97.0%** | 自有 ASR 模型：Word Error Rate 12.7%，Medical Term Recall 97.0% | https://www.abridge.com/ai/science-ai-evaluation |
| 16.6% / 96.4% | Google Medical Conversations | 同上 |
| 17.1% / 92.9% | AWS Transcribe Medical | 同上 |
| 17.9% / 94.6% | AssemblyAI Universal-2 | 同上 |
| 24% | 相对 Google Medical Conversations 的 WER 相对下降 | 同上 |
| 6.2% / 3.1% | 英语 / 西班牙语 WER（FLEURS 上） | 同上 |
| **4.3 / 5** | 近三个月（5–7 月）英语问诊笔记医生星评均值，"tens of thousands of star ratings" | 同上 |
| 3.7 → 4.1 | 西班牙语问诊评分从 2 月的 3.7 提升至近期 4.1 | 同上 |
| 15.8% | 口音英语（南亚/东亚/欧洲/南非/中东）转写准确率相对提升 | 同上 |
| **97% vs 82%** | 自有护栏模型捕获 confabulation 比例 97%，GPT-4o 仅 82%；"a standard off-the-shelf model misses **six times** as many confabulations" | https://www.abridge.com/ai/science-confabulation-hallucination-elimination |
| 50,000+ | 护栏检测模型训练样本数 | 同上 |
| 1,000+ 小时 | 人类验证时长，"supported by over one thousand hours of human validation" | 同上 |
| 10,000+ 小时 | ASR 评测用医疗对话音频 | https://www.abridge.com/ai/science-ai-evaluation |
| 28 种语言 | 官方支持的临床对话语言，"including the 16 most spoken languages in the United States" | 同上 |
| 14+ 种语言 | https://www.abridge.com/ai 页面表述为 "across 14+ languages" | https://www.abridge.com/ai |
| **90%+** | "month-over-month retention rates for clinicians who regularly use Abridge are well above 90%" | https://www.abridge.com/ai/science-confabulation-hallucination-elimination |
| **150+ / 50,000,000 / 95%+ / 19** | 150+ 企业医疗系统；2025 年将支撑 5000 万次对话；95%+ 留存率；报告覆盖 19 家医疗系统 | https://www.abridge.com/reports/adoption-scale-impact |
| **300+ / 250,000,000** | 300+ 企业医疗系统，覆盖 2.5 亿患者 | https://www.abridge.com/blog/context-aware-clinical-intelligence-for-every-clinician-partner-systems ；https://www.abridge.com/reports/innovation-at-the-speed-of-trust |
| 40+ | 已使用 Abridge 的专科数 | https://www.abridge.com/platform/clinicians |
| 90% / 78% / 85% | Akron Children's 专注度 +90%；Christus Health 认知负荷 -78%；Corewell Health 医生满意度 +85% | https://www.abridge.com/platform/clinicians |
| 78% | Sutter Health 医生工作满意度改善比例 | https://www.abridge.com/ |
| 21% / 42% | 引用的 2020 年研究：近 30,000 名患者中 21% 认为笔记有错，其中 42% 为严重错误 | https://www.abridge.com/ai/science-confabulation-hallucination-elimination |
| 48 项研究中 47 项 | 引用的 2024 年综述：48 项病历错误研究中 47 项发现存在错误 | 同上 |

> **[推断]** 「150+ health systems」（AI Impact Report，2025 时点）与「300+ health system partners」（2025-11 起的 trust/CDS 页面、2026 时点）并存，**并非矛盾而是口径与时点差异**（前者含"已部署"口径，后者含"合作"口径）；需按页面时间戳引用，不可混用。
> **[推断]** 「14+ languages」（/ai 页）与「28 languages」（评测页）差异同理，前者为 ASR 覆盖口径、后者为"官方支持"口径。

### 8. 出处链接 + 证据强度汇总
| URL | 内容 | 强度 |
|---|---|---|
| https://www.abridge.com/ | 平台导航、客户数 | 已打开原文 |
| https://www.abridge.com/ai | Provenance/Linked Evidence、人审前修改 | 已打开原文 |
| https://www.abridge.com/ai/science-ai-evaluation | 评测体系、ASR 指标、语言、星评 | 已打开原文 |
| https://www.abridge.com/ai/science-confabulation-hallucination-elimination | 护栏模型、严重度分级、强制人审 | 已打开原文 |
| https://www.abridge.com/abridge-contextual-reasoning-engine | "auditable notes … powered by Linked Evidence" | 已打开原文 |
| https://www.abridge.com/cds | clinician-in-the-loop、内容源 | 已打开原文 |
| https://www.abridge.com/platform/clinicians | SSO/加密/治理/分析 | 已打开原文 |
| https://www.abridge.com/terms/clinician | 免责、责任上限、仲裁 | 已打开原文 |
| https://www.abridge.com/terms/business-associate-agreement | 审计/留存/披露会计 | 已打开原文 |
| https://www.abridge.com/privacy | 留存、声纹销毁、BAA 关系 | 已打开原文 |
| https://www.abridge.com/reports/adoption-scale-impact | 规模数字 | 已打开原文（正文，报告本体需表单下载） |
| https://www.abridge.com/reports/innovation-at-the-speed-of-trust | 300+ 系统、模型上线流程 | 已打开原文（仅落地页摘要，报告本体门控） |
| https://www.abridge.com/blog/building-trusted-healthcare-ai | 三原则、可审计性 | 已打开原文 |
| https://www.abridge.com/blog/clinician-builder-cds | 证据排序由临床医生定 | 已打开原文 |
| https://www.abridge.com/blog/context-aware-clinical-intelligence-for-every-clinician-partner-systems | 300+/2.5 亿患者 | 已打开原文 |
| https://www.abridge.com/best-in-klas | KLAS 2025 Ambient AI 冠军（无评分数字） | 已打开原文 |

---

## 二、Nuance DAX / DAX Copilot（→ Microsoft Dragon Copilot）

### 0. 重大前置事实：品牌与域名已迁移
**nuance.com 的 healthcare 路径现全部 302 到 Microsoft 页面**。实测：`https://www.nuance.com/healthcare/ambient-clinical-intelligence.html`、`.../dax-copilot.html`、`.../clinical-documentation.html` 三个不同 URL 返回**完全相同**的 166,321 字节 Microsoft「Health solutions」模板（已打开原文，可复现）。产品已更名为 **Microsoft Dragon Copilot**（`https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot`）。

> **[推断]** 引用 DAX Copilot 旧口径数据时必须同时标注抓取时点，因为该域名不再提供独立 Nuance 内容，旧页仅存于 Wayback。

### 1. 它解决什么 / 目标用户
Microsoft 官方定位（已打开原文，https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot ）：
> "Microsoft Dragon Copilot is an **AI clinical assistant** built to simplify and transform the way care teams work. Designed with **role-based experiences** at its core..."

目标用户分三类角色：医师、护士、放射科医师。可用地域（同页 FAQ）：
> "For physicians—available in the United States, Canada, the United Kingdom, Ireland, France, Germany, Austria, Belgium, the Netherlands, and Switzerland. For nurses—available in the United States. For radiologists—currently in preview in the United States."

### 2. 规则库怎么组织
走**"接地生成 + 引用 + 第三方医学参考"**路线，而非自建规则库。已打开原文，https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot ：
> "Surface information — Information is brought directly into Dragon Copilot. Ask questions and receive responses drawn from transcripts, notes, and **trusted third-party medical references with clear citations**."

护士侧的"规则"是**结构化 flowsheet 映射**（同页）：
> "Capture realtime observations ambiently, converting them into **structured flowsheet documentation** for quick nurse review and approval and seamless EHR transfer—reducing end-of-shift charting"

**AI 治理原则**（已打开原文，Microsoft 发布博文）："Our AI aligns with Microsoft's **responsible AI practices** and incorporates **healthcare-specific clinical, chat, and compliance safeguards** to ensure accurate and safe outputs."

### 3. 案例库怎么组织
公开材料中**未披露 DAX/Dragon Copilot 的评测数据集或案例库结构**——**未找到公开资料**。
唯一可量化的"训练语料"口径（已打开原文，Wayback 2024 Nuance DAX Copilot 页）：
> "Uses the latest AI technologies and is **trained on over 15M encounters** to produce accurate documentation efficiently and consistently."

客户案例以**医疗系统署名研究**形式组织（非匿名 case library）：
- University of Michigan Health-West（Advisory Board 研究）
- WellSpan Health（与 Nuance 合作研究）
- Intermountain Health、Mercy、Cooper University Health Care、Vail Health、University of Rochester Medical Center、Greater Baltimore Medical Center、Valley View Hospital

### 4. 误判与申诉 / 复核怎么走
**未找到公开资料**：未发现 DAX/Dragon Copilot 公开任何**误判申诉通道、纠错上报流程、分级处理规则或 SLA**。已抓取页面中仅有：
- 产品内反馈：「Product and AI feedback: **In-app feedback and dedicated channels enables clinicians to rate Dragon Copilot and provide feedback** that helps improve the product experience, note quality and AI responses.」（已打开原文，Microsoft 发布博文）
- 支持通道：「Integrated live chat and virtual support room」（同页）
- **[推断]** 产品内 star rating / 反馈属"改进信号"而非"个案申诉裁决"机制，二者不可混同。

### 5. 人机分工边界
Microsoft/Nuance 的公开表述**弱于 Abridge**：Abridge 有明确的"必须审阅签署后才入 EHR"强制语，Microsoft 侧最高只到"供医生审阅与编辑 / 快速审阅与批准 / 定稿前"。逐条原文：

**(a) 医生侧**（已打开原文，Wayback 2024 Nuance DAX Copilot 页）：
> "Converts encounter conversations into comprehensive specialty-specific clinical documentation summaries, and delivers the summary into the mobile and desktop application **for clinician review and editing**."

**(b) 护士侧**（已打开原文，https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot ）：
> "converting them into structured flowsheet documentation for **quick nurse review and approval** and seamless EHR transfer"

**(c) 定稿前复核**（已打开原文，Microsoft 发布博文）：
> "Summarize notes: Get an instant synopsis of each encounter, including key facts and details, streamlining workflow and reducing cognitive load. Dragon Copilot makes it easy to get **a quick refresher on the patient before finalizing a note.**"

**(d) 证据摘要的定位是"辅助验证"而非"结论"**（同页）：
> "Summarize evidence: **Receive more than just linked notes to transcripts.** Dragon Copilot curates diagnosis evidence from subjective elements such as symptoms, objective elements such as labs and imaging, and other relevant information shared during the encounter."

**(e) 自主性边界**：**产品页明确存在"自动写入 EHR"的能力**，这是与 Abridge 文档类表述的重要差异（已打开原文，Microsoft 发布博文）：
> "Make orders easy: Automatically capture over a dozen order types during clinician-patient conversations. **With supported EHRs, orders are directly entered into the EHR order module.**"
> **[推断]** 该表述与"人审边界"存在张力：订单条目可直接进 EHR order module，公开材料未说明是否强制人审确认后写入。

**(f) 免责/责任语言**：在本次抓取的全部 Microsoft 与 Nuance 页面中，**未找到任何 "clinician remains responsible" 或等同的免责/责任归属语句**——**未找到公开资料**。
> **[推断]** 此类条款很可能存在于 Microsoft 产品条款 / Online Services Data Protection Addendum / 客户合同中，但**未在本次可抓取的公开产品页面上出现**，不应据现有证据推断其内容。

### 6. 审计日志 / 可追溯性 / 合规认证
| 项目 | 公开内容 | 出处 / 强度 |
|---|---|---|
| 笔记-转写关联 | "linked notes to transcripts"（作为对比基线被提及） | Microsoft 发布博文 —— **已打开原文** |
| 审计日志字段/保留期/查阅权 | **未找到公开资料** | — |
| HIPAA / HITECH | Microsoft 以 business associate 身份签 BAA；"There's currently no certification standard that the Department of Health and Human Services approves to demonstrate compliance with HIPAA" | https://learn.microsoft.com/en-us/compliance/regulatory/offering-hipaa-hitech —— **已打开原文** |
| 独立审计 | "Microsoft services covered under the BAA undergo audits conducted by **accredited independent auditors** for the Microsoft **ISO/IEC 27001** certification and the **HITRUST Common Security Framework (CSF)** certification." | 同上 —— **已打开原文** |
| 认证清单 | **SOC 1 / SOC 2 / SOC 3**、ISO 27001 / 27017 / 27018 / 27701 / **42001** / 9001 / 20000-1 / 22301、**FedRAMP**、**HITRUST**、PCI-DSS | https://learn.microsoft.com/en-us/compliance/regulatory/offering-home —— **已打开原文** |
| 认证总量与审计报告获取 | "more than **90 offerings**"；Service Trust Portal 提供独立审计报告；"Compliance Score"、"Audit reports" | https://www.microsoft.com/en-us/trust-center —— **已打开原文** |
| Dragon Copilot 专属认证 | **未找到公开资料**（仅有 Microsoft 平台级认证，无产品级声明） | — |
| 责任划分（HIPAA） | "using Microsoft services **doesn't on its own achieve HIPAA compliance**. Your organization is responsible for ensuring that you have an adequate compliance program and internal processes in place" | https://learn.microsoft.com/en-us/compliance/regulatory/offering-hipaa-hitech —— **已打开原文** |

### 7. 可量化公开数字
| 数字 | 内容 | 出处 / 强度 |
|---|---|---|
| **5 分钟** | 每次问诊平均节省 5 分钟（"5 min saved per clinician, per encounter on average"） | Wayback 2024 Nuance DAX Copilot 页 —— **已打开原文** |
| **13 个** | 每月每位医生因此多出 13 个预约档期 | Microsoft 发布博文 —— **已打开原文** |
| **70%** | 自述工作-生活平衡改善、倦怠与疲劳感下降 | 两处均载 —— **已打开原文** |
| **77%** | 自述文档质量提升 | Wayback 2024 Nuance DAX Copilot 页 —— **已打开原文** |
| **93%** | 患者称医生更亲切、更善于交谈 | 两处均载 —— **已打开原文** |
| 调查样本 | "Microsoft survey of **879 clinicians across 340 healthcare organizations** using DAX Copilot; July 2024"；"Survey of **413 patients**...; June 2024" | Microsoft 发布博文脚注 —— **已打开原文** |
| **15M+** | 训练问诊量 | Wayback 2024 Nuance DAX Copilot 页 —— **已打开原文** |
| **200+** | Dragon Medical One 集成的 EHR 数量 | 同上 —— **已打开原文** |
| 12 / 20 / 80% | UMHW（Advisory Board 研究）：每月多看 12 名患者、wRVU 每月 +20、额外 **80% ROI** | 同上 —— **已打开原文** |
| ~2 小时 | Mercy 一位护士称 12 小时班次中节省约 2 小时记录时间 | https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot —— **已打开原文** |
| 27% | Intermountain Health：每次预约的笔记耗时下降 27% | 同上 —— **已打开原文** |
| 2,500+ | Intermountain Health 活跃医生用户数 | 同上 —— **已打开原文** |
| 24+ | 其构建的 AI Agents 数 | 同上 —— **已打开原文** |
| 150+ | 参赛者中赢得美国退伍军人事务部（VA）AI Tech Sprint | Wayback 2024 Nuance DAX Copilot 页 —— **已打开原文** |

---

## 三、FDA 对 AI/ML 医疗软件的监管路径

### 1. 它解决什么 / 目标用户
FDA 面对的核心矛盾（已打开原文，https://web.archive.org/web/2024/https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-and-machine-learning-software-medical-device ）：
> "**The FDA's traditional paradigm of medical device regulation was not designed for adaptive artificial intelligence and machine learning technologies. Many changes to artificial intelligence and machine learning-driven devices may need a premarket review.**"

受众：器械厂商（510(k)/De Novo/PMA/HDE/BLA 申报方）、数字健康创新企业、监管同行（IMDRF）。

### 2. 规则库怎么组织

**(a) SaMD 定义与 IMDRF 风险分类框架**（已打开原文，https://web.archive.org/web/2025/https://www.fda.gov/medical-devices/software-medical-device-samd ）：
> "The term Software as a Medical Device is defined by the **International Medical Device Regulators Forum (IMDRF)** as '**software intended to be used for one or more medical purposes that perform these purposes without being part of a hardware medical device.**'"

IMDRF SaMD 工作组的产出（同页）："the key definitions for Software as a Medical Device, **framework for risk categorization** for Software as a Medical Device, the Quality Management System for Software as a Medical Device, and the clinical evaluation of Software as a Medical Device."（该工作组由 FDA 主持）

**四类风险框架**（已打开原文，https://web.archive.org/web/2025/https://www.fda.gov/medical-devices/software-medical-device-samd/global-approach-software-medical-device ）：
> "The Software as a Medical Device risk categorization framework has **four categories (I, II, III, and IV)**. These categories are based on the levels of impact on the patient or public health where accurate information provided by the Software as a Medical Device to treat or diagnose, drive or inform clinical management is vital to avoid death, long-term disability or other serious deterioration of health, mitigating public health. **The Level IV category is Software as a Medical Device with the highest impact on the patient or public health and Level I is the lowest.**"

矩阵两轴（同页，原文以表格呈现，抽取时单元格合并）：
- **State of Health care situation or condition**：Critical / Serious / Non-serious
- **Significance of information provided by SaMD to health care decision**：treat or diagnose / drive clinical management / inform clinical management

> **[推断]** 标准 IMDRF 矩阵为 3×3 映射到 I–IV 四级；FDA 该页仅呈现轴与分类级数，**具体 3×3 单元格到 I–IV 的映射未在本页文本中完整呈现**，需查 IMDRF 原文件。

**(b) 非器械 CDS 四要件（人审边界在监管上的定义）** — 已打开原文，https://web.archive.org/web/2025/https://www.fda.gov/medical-devices/software-medical-device-samd/clinical-decision-support-software-frequently-asked-questions-faqs ：
> "Your software function must meet **all four criteria** to be considered Non-Device CDS."
> 1. "Your software function does **NOT** acquire, process, or analyze medical images, signals, or patterns."
> 2. "Your software function displays, analyzes, or prints **medical information normally communicated between health care professionals (HCPs)**."
> 3. "Your software function provides **recommendations (information/options) to a HCP rather than provide a specific output or directive**."
> 4. "Your software function **provides the basis of the recommendations so that the HCP does not rely primarily on any recommendations** to make a decision."

时敏场景被明确排除（同页 Q3）：
> "Software that is meant to support **time-critical** decision making do not meet the definition of Non-Device CDS... In such situations, **it is difficult to support that a clinician is not meant to solely rely on a provided recommendation** or that the clinician will spend time to understand its specific basis."

**人机分工在监管上的核心语句**（已打开原文，FDA 生命周期指南草案 PDF, 第 28–29 页）：
> "Principle Seven discusses placing focus on '**the performance of the Human-AI Team**.' This principle explains that it is important to understand the performance of the '**Human-AI team, rather than just the performance of the model in isolation**' when a model has a '**human in the loop**.' The intended use and clinical workflow of AI-enabled devices span **a continuum of decision-making roles from more autonomous systems to supportive (aid) tools that assist specific users, but rely on the human to interpret the AI outputs and ultimately make clinical decisions.**"

**(c) TPLC（全产品生命周期）方法** — 已打开原文，FDA 生命周期指南草案（2025 年 1 月）：
> "The recommendations reflect a comprehensive approach to the management of risk throughout the device **total product life cycle (TPLC)**."
> "This guidance acknowledges the importance of a **TPLC approach** to the management of AI-enabled devices... recommendations for the design, development, deployment, and maintenance of AI-enabled devices, including the performance management."

TPLC 的三大贯穿主题（同 PDF）：
> "This guidance also includes FDA's current thinking on strategies to address **transparency and bias throughout the TPLC** of AI-enabled devices. These interconnected considerations are important throughout the TPLC and **should be incorporated from the earliest stage of device design through decommission**"
> "**Transparency** involves ensuring that important information is both accessible and **functionally comprehensible** and is connected both to the sharing of information, and to the usability of a device."

透明度设计（同 PDF, Appendix B）：
> "In this guidance, transparency refers to clearly communicating the **contextually relevant performance and design information** of a device to the appropriate stakeholders in a manner that they can understand and act on... **Including appropriate transparency information has also been shown to more than double willingness to use a device.**"

**风险控制中用户界面的角色**（同 PDF）：
> "the user interface can communicate important information to users that supports safe and effective use of the device, and the user interface design may play a crucial role in **controlling or eliminating risks associated with not knowing or misunderstanding information that is critical to the safe and effective use of the device**."

**(d) 上市后性能监测**（同 PDF）：
> "The performance of AI-enabled devices deployed in a real-world environment... **may change or degrade over time, presenting a risk to patients.**... manufacturers should have a **postmarket performance monitoring plan** to help identify and respond to changes in performance"
> "manufacturers must monitor device performance and report to FDA information about deaths, serious injuries, and malfunctions in accordance with **21 CFR Parts 803 and 806**"
> "When performance changes do occur, **users may be less likely to identify them** in AI-enabled devices if, for example, the devices are part of a **highly automated process with limited on-going human interaction**"

### 3. 案例库怎么组织（FDA 侧）
FDA 公开组织的是**授权器械清单**与**示例场景**，而非评测数据集：

**(a) AI 器械授权清单**（已打开原文，https://web.archive.org/web/2025/https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-and-machine-learning-aiml-enabled-medical-devices ）：
> "The AI-Enabled Medical Device List is a resource intended to identify AI-enabled medical devices that are **authorized for marketing in the United States**."

**实测计数**：本次抓取的该清单快照 HTML 中，**唯一 submission number 共计 1,357 个**（`K######` / `DEN######` / `P######` 形式去重后），表格行 1,358 行。
> **[推断]** 1,357 为本次快照的**请求级计数**（按 submission number 去重），非 FDA 官方公布总数；页面本身**未给出总数声明**，且明确声明清单不完整：
> "The list is **not a comprehensive resource** of AI-enabled medical devices. Instead, the list includes AI-enabled medical devices that were identified primarily based on the use of AI-related terms in the summary descriptions of their marketing authorization document and/or the device's classification."
> 页面提供 CSV / Excel / XML 下载，可用于精确复核。

**(b) PCCP 示例场景库**（已打开原文，PCCP 终版指南 PDF, Appendix B）——6 个具名场景：
> "(1) Patient Monitoring Software (2) Skin Lesion Software (3) Ventilator Settings Software (4) Image Acquisition Assistance Device (5) Feeding Tube Placement Radiograph Analysis Software (6) Optical Imaging System Co-packaged with Imaging Drug"

**(c) 透明度示例标签**（生命周期指南 PDF, Appendix C）：给出一个完整示例的器械公开摘要，含 Sensitivity 84%、Specificity 83%、PPV 55.3%、NPV 95.4% 等。

### 4. 误判与申诉 / 复核怎么走（监管侧）
**(a) 上市前交互式审查**（已打开原文，PCCP 终版指南 PDF, §V.F）：
> "FDA anticipates that review of a marketing submission that includes a PCCP will be **interactive**. It is possible that a PCCP submitted as part of a marketing submission may need revisions before FDA can make a determination of reasonable assurance of safety and effectiveness or substantial equivalence... FDA should work with the manufacturer to revise the PCCP, and will do so using FDA's existing processes to request additional information **through interactive review or through a deficiency letter**. If deficiencies with the PCCP remain unresolved, **FDA may authorize the device upon withdrawal of the PCCP.**"

**(b) 复议锚点**：PCCP 被授权后**写入授权函**（同 PDF）：
> "the PCCP will be **referenced in the device's letter of authorization, including the PCCP title and version number.**"

### 5. 人机分工边界（PCCP 对"自动 vs 人工"的法定区分）
这是本次调研中**对"变更是否需要人审"最精确的监管定义**（已打开原文，PCCP 终版指南 PDF, §VI.B）：
> "The Description of Modifications should clearly state if the planned modifications are proposed to be implemented **automatically** (i.e., whether the modifications are implemented automatically by software), whether modifications are implemented **manually (i.e., involving steps that require human input, action, review, and/or decision-making, and therefore are not implemented automatically)**, or a combination of both."

自动实施的额外审慎（同 PDF）：
> "FDA will consider PCCPs for AI-DSFs for modifications that are implemented automatically. The Agency recognizes that **this subset of AI-DSFs has an additional degree of complexity**; as with all AI-DSFs, FDA will consider the benefit-risk profile of the specific device..."

### 6. 审计轨迹 / 可追溯性（21 CFR Part 11）
**注意**：PCCP 终版指南全文 **"audit" 出现 0 次**（实测）。审计轨迹要求来自 **21 CFR Part 11**，非 PCCP 指南。以下均**已打开原文**（https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11 ）：

**核心审计轨迹条款 §11.10(e)**：
> "Use of **secure, computer-generated, time-stamped audit trails** to independently record the **date and time of operator entries and actions that create, modify, or delete electronic records**. **Record changes shall not obscure previously recorded information.** Such audit trail documentation shall be **retained for a period at least as long as that required for the subject electronic records** and shall be **available for agency review and copying.**"

**§11.10 全套控制项**（逐条）
- (a) 系统验证，确保准确、可靠、一致预期性能，且**能辨别无效或被篡改的记录**
- (b) 能生成**人类可读与电子两种形式**的准确完整记录副本，供**机构检查、审阅与复制**
- (c) 保护记录，确保在整个**记录保留期内**准确且可随时检索
- (d) 限制系统访问于授权个人
- (e) 上述审计轨迹
- (f) 运行系统检查，以强制步骤与事件的许可顺序
- (g) **权限检查**：仅授权个人可操作系统、**电子签署记录**、访问输入/输出设备、改动记录
- (h) 设备（终端）检查
- (i) 开发/维护/使用电子记录系统者须具备相应教育、培训与经验
- (j) **建立并遵守书面政策，使个人对其电子签名下发起的行为负责**，"in order to deter record and signature falsification"
- (k) 系统文档控制：(1) 文档分发/访问/使用的充分控制；(2) **修订与变更控制程序，维护记录系统文档时间序列性开发与修改的审计轨迹**

**签名与记录（§11.50 / §11.70）**：
> §11.50(a): "Signed electronic records shall contain information associated with the signing that clearly indicates all of the following: (1) **The printed name of the signer**; (2) **The date and time when the signature was executed**; and (3) **The meaning (such as review, approval, responsibility, or authorship) associated with the signature.**"
> §11.70: "Electronic signatures and handwritten signatures executed to electronic records shall be **linked to their respective electronic records to ensure that the signatures cannot be excised, copied, or otherwise transferred to falsify an electronic record by ordinary means.**"

**§11.100 / §11.200**：电子签名须**唯一对应个人**、不得重用或转授；机构须先核验身份；使用前或使用时须向 FDA 认证其等同手写签名；非生物特征签名须**至少两个不同身份要素**（如 ID + 密码）。

**开放系统（§11.30）**：除 §11.10 外，还须"**document encryption and use of appropriate digital signature standards**"。

### 7. 变更控制版本化（PCCP 概念）——本次调研的核心产出

**起源**（已打开原文，2019 讨论稿 PDF, https://web.archive.org/web/2025/https://www.fda.gov/media/122535/download ）：最初名为 **SaMD Pre-Specifications (SPS)**（"what" 要改）+ **Algorithm Change Protocol (ACP)**（"how" 改而保持安全有效）。
后经 **AI/ML SaMD Action Plan（2021 年 1 月）**（已打开原文，https://web.archive.org/web/2025/https://www.fda.gov/media/145022/download ）定型：
> "with appropriately tailored **total product lifecycle-based regulatory oversight**, AI/ML-based Software as a Medical Device (SaMD) will deliver safe and effective software functionality"
> "FDA described a '**Predetermined Change Control Plan**' in premarket submissions. This plan would include the types of anticipated modifications—referred to as the '**SaMD Pre-Specifications**'—and the associated methodology being used to implement those changes in a controlled manner that manages risks to patients—referred to as the '**Algorithm Change Protocol**.'"

**时间线**（已打开原文，https://web.archive.org/web/2024/https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-and-machine-learning-software-medical-device ）：
> 2019-04-02 讨论稿 → 2021-01 AI/ML SaMD Action Plan → 2021-10 Good Machine Learning Practice → **2023-04 草案**：Marketing Submission Recommendations for a PCCP for AI/ML-Enabled Device Software Functions → 2023-10 PCCP Guiding Principles → 2024-06 Transparency Guiding Principles → **2024-12 终版指南**

**终版指南 PDF 页眉**（已打开原文，https://web.archive.org/web/20251220072255/https://www.fda.gov/media/166704/download ）：
> "**Document issued on August 18, 2025. Document originally issued on December 4, 2024.**"
（Docket No. **FDA-2022-D-2628**；文档编号 **GUI00020049**；共 **49 页**）

**适用范围**：
> "The recommendations in this guidance apply to AI-enabled devices, including the device constituent part of device-led combination products, reviewed through the **510(k), De Novo, and PMA** pathways."

**核心机制**：
> "The FDA reviews the PCCP as part of a marketing submission for an AI-enabled device to ensure the continued safety and effectiveness of the device **without necessitating additional marketing submissions for implementing each modification described in the PCCP.**"

**PCCP 三大组成部分 + 强制预规格化内容**：

**(i) Description of Modifications（要改什么）**——必须**具体、可验证、可确认**：
> "FDA recommends that a PCCP include modifications that are **specific, and that can be verified and validated**."
> "The Description of Modifications should **clearly state if the planned modifications are proposed to be implemented automatically..., manually..., or a combination of both.**"

**允许纳入 PCCP 的三类变更**：
> "(i) modifications related to **quantitative measures of AI-DSF performance specifications**; (ii) modifications related to **device inputs to, and compatibility with, the AI-DSF**; and (iii) certain modifications related to the **device's use and performance** (e.g., for use within a specific subpopulation)."
> "Modifications included in a PCCP **must maintain the device within the device's intended use**"

**(ii) Modification Protocol（怎么改）——四个强制组件**：
1. **Data management practices**：
   > "The data management practices in a Modification Protocol should outline **how those new data will be collected, annotated, curated, stored, retained, controlled, and used** by the manufacturer for each modification."
   > "Training data, tuning data, and test data are **sequestered** (i.e., the test data set is a unique data set compared to the data set used for training and tuning) to prevent overfitting and misquotes of test performance."
   > "The training, tuning, and testing methods aim to **identify and mitigate unwanted bias in the data** (which may be inherent from historical datasets)... Additional methods to mitigate bias may be helpful, such as cross-validation, bootstrapping, bagging, ensembling, and the use of synthetic or augmented data."
2. **Re-training practices**（§VII.B.(2)）
3. **Performance evaluation**：
   > "The content of this section in a Modification Protocol should provide details on the **study design, performance metrics, pre-defined acceptance criteria, and statistical tests for each planned modification**."
   > "...comparing the newly modified device to **both the original device** (the version of the device without any modifications implemented) **and the last modified version** of the device."
4. **Update procedures**：
   > "The update procedures should clearly describe **which planned modifications will be implemented automatically, implemented manually, or a combination of both**, and **how the manufacturer plans to communicate this information to users.**"
   > "The manufacturer should also describe their **post-market surveillance plans and procedures**, which may include real-world monitoring and notification requirements **if the device does not function as intended pursuant to the authorized PCCP.**"
   > "The update procedures in a Modification Protocol should also address **how labeling will be updated** when modifications are implemented"
   > "**Monitoring activities may differ for AI-DSFs for which updates are deployed manually compared to automatically, or for which updates are deployed globally or locally.**"

**(iii) Impact Assessment（影响评估）——5 项强制内容**：
> "1) Compare the version of the device with **each modification implemented individually** to the version of the device without any modifications implemented;
> 2) Discuss the **benefits and risks, including risks of harm and unintended bias, of each individual modification**;
> 3) Discuss how the verification and validation activities proposed within the Modification Protocol continue to reasonably ensure the safety and effectiveness of the device;
> 4) Discuss **how the implementation of one modification impacts the implementation of another**; and
> 5) Describe the **cumulative impact** of implementing all modifications."
> "The manufacturer's **existing quality system should be used as the framework** in which to conduct an Impact Assessment"

**可追溯性表（PCCP 内部规则-变更映射）**——已打开原文，§VII.C：
> "The PCCP should clearly delineate **which parts of the Modification Protocol are applicable to each modification** within the Description of Modifications. For a PCCP with multiple modifications, this may be accomplished through a **traceability table**"
（Table 1 示例：行 = Modification #1/#2/#3，列 = Data management practices / Re-training practices / Performance evaluation / Update procedures，单元格内填 Method 编号 + 章节交叉引用）

**版本控制**——已打开原文，§V.F：
> "a copy of the PCCP with a **title and version number** should be included in the marketing submission for the device. If the PCCP is revised during review, such as in response to deficiencies, a **final, revised version of the PCCP should be submitted as a clean copy** to FDA and should include a **title and current version number** for the PCCP. FDA authorizes the PCCP as part of the marketing authorization of a device. To that end, **the PCCP will be referenced in the device's letter of authorization, including the PCCP title and version number.**"

**修改已授权的 PCCP**：经 PMA supplement 或新的 traditional 510(k) 提交（脚注 79）。

### 8. 可量化公开数字（FDA 侧）
| 数字 | 内容 | 出处 / 强度 |
|---|---|---|
| **1,357** | 本次抓取的 AI 器械授权清单快照中唯一 submission number 数（实测去重计数） | https://web.archive.org/web/2025/.../artificial-intelligence-and-machine-learning-aiml-enabled-medical-devices —— **已打开原文**（**[推断]** 计数为本人实测，非 FDA 官方声明；页面未给总数） |
| **90+** | Microsoft 合规 offering 数（对照项，非 FDA） | https://www.microsoft.com/en-us/trust-center —— 已打开原文 |
| 4 | IMDRF SaMD 风险类别 I–IV | https://web.archive.org/web/2025/.../global-approach-software-medical-device —— **已打开原文** |
| 4 | Non-Device CDS 四要件 | https://web.archive.org/web/2025/.../clinical-decision-support-software-frequently-asked-questions-faqs —— **已打开原文** |
| 6 | PCCP 附录 B 示例场景数 | PCCP 终版指南 PDF Appendix B —— **已打开原文** |
| 49 / 67 | PCCP 终版指南页数 / 生命周期草案指南页数 | 两份 PDF —— **已打开原文** |

### 9. 出处链接 + 证据强度（FDA）
| URL | 内容 | 强度 |
|---|---|---|
| https://web.archive.org/web/2024/https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-and-machine-learning-software-medical-device | AI/ML SaMD 总览、完整政策时间线 | 已打开原文 |
| https://web.archive.org/web/2025/https://www.fda.gov/medical-devices/software-medical-device-samd | SaMD 定义、IMDRF 工作组产出 | 已打开原文 |
| https://web.archive.org/web/2025/https://www.fda.gov/medical-devices/software-medical-device-samd/global-approach-software-medical-device | IMDRF 四类风险框架、QMS 框架 | 已打开原文 |
| https://web.archive.org/web/2025/https://www.fda.gov/medical-devices/software-medical-device-samd/clinical-decision-support-software-frequently-asked-questions-faqs | Non-Device CDS 四要件、时敏排除、Q1–Q7 | 已打开原文 |
| https://web.archive.org/web/2025/https://www.fda.gov/medical-devices/software-medical-device-samd/artificial-intelligence-and-machine-learning-aiml-enabled-medical-devices | AI 器械授权清单 | 已打开原文 |
| https://web.archive.org/web/2025/https://www.fda.gov/regulatory-information/search-fda-guidance-documents/marketing-submission-recommendations-predetermined-change-control-plan-artificial-intelligence | PCCP 终版指南落地页（Docket FDA-2022-D-2628） | 已打开原文 |
| **https://web.archive.org/web/20251220072255/https://www.fda.gov/media/166704/download** | **PCCP 终版指南 PDF 全文（49 页，148,006 字符抽取）** | 已打开原文 |
| https://web.archive.org/web/2025/https://www.fda.gov/media/145022/download | AI/ML SaMD Action Plan PDF（2021-01，8 页） | 已打开原文 |
| https://web.archive.org/web/2025/https://www.fda.gov/media/122535/download | 2019 讨论稿 PDF（20 页，SPS/ACP 起源） | 已打开原文 |
| https://web.archive.org/web/2025/https://www.fda.gov/regulatory-information/search-fda-guidance-documents/artificial-intelligence-enabled-device-software-functions-lifecycle-management-and-marketing | TPLC 生命周期指南草案落地页（2025-01，草案） | 已打开原文 |
| **https://web.archive.org/web/20260109143947/https://www.fda.gov/media/184856/download** | **生命周期指南草案 PDF 全文（67 页，202,772 字符抽取）** | 已打开原文 |
| https://web.archive.org/web/2025/https://www.fda.gov/medical-devices/digital-health-center-excellence | DHCoE 入口 | 已打开原文 |
| **https://www.ecfr.gov/current/title-21/chapter-I/subchapter-A/part-11** | **21 CFR Part 11 全文（§11.10/11.30/11.50/11.70/11.100/11.200）** | 已打开原文 |

---

## 四、三项横向对比要点（供审计/合规架构参考）

| 维度 | Abridge | Microsoft Dragon Copilot（原 Nuance DAX） | FDA |
|---|---|---|---|
| **可追溯性机制名称** | **Linked Evidence**（段落→transcript/audio 双向定位） | "linked notes to transcripts"（仅作对比提及） | 21 CFR Part 11 §11.10(e) 审计轨迹 |
| **是否明示"必须人审后才入 EHR"** | **是，且为强制语**："All clinician notes... are reviewed and edited... before being entered into the EHR"；"Clinicians are required to review and verify their own notes before filing" | **否**，最高表述为 "for clinician review and editing"、"quick nurse review and approval"、"before finalizing a note" | 以 "human in the loop" / "Human-AI Team" 性能评估要求体现，非产品级强制语 |
| **免责/责任条款** | 有明确条款页：不从事医疗、不做诊断、责任在医生、责任上限 $1,000 或 12 个月已付费用 | **未找到公开资料**（产品页未载此类语句） | 以 "continuum... rely on the human to interpret the AI outputs and ultimately make clinical decisions" 表述 |
| **审计日志具体规范** | **未找到公开资料** | **未找到公开资料** | §11.10(e)：安全、计算机生成、**时间戳**、独立记录创建/修改/删除的日期时间、**改动不得遮蔽先前记录**、保留期≥记录本身、可**供机构审阅复制** |
| **误判分级/申诉规则** | 有：Support × Severity 双层分类（Supported/Not supported/Contradiction × Major/Moderate/Minimal） | **未找到公开资料** | 无"误判"概念；以上市前 deficiency letter + 上市后 803/806 报告替代 |
| **变更控制版本化** | 未公开 PCCP 式机制；有 alpha→beta→全面发布的**分阶段放行** + 盲评 + 顺序检验 | 未公开 | **PCCP**：Description of Modalities + Modification Protocol（4 组件）+ Impact Assessment（5 项）三件套，含 traceability table 与 title+version 管理 |
| **量化准确性公开度** | 高（WER/MTR/星评/confabulation 捕获率 + 样本量） | 中（时间节省/满意度/患者反馈 + 调查样本量 879 医生 / 413 患者），**无准确性指标** | 高（示例标签含 Sens/ Spec/ PPV/ NPV） |
| **上市途径** | 未公开声明 | 未公开声明 | 510(k) / De Novo / PMA（PCCP 三途皆适用） |

---

## 五、明确的调研缺口（诚实列出）

以下项目**在本次实际抓取的全部官方页面中确实未出现**，标注为「未找到公开资料」，**不做推断填充**：

1. **Abridge**：安全/信任中心页（SOC 2、HITRUST、ISO 27001 认证状态）；审计日志字段、保留期限、客户/监管方查阅接口；PCCP 或类似变更控制文档。
2. **Nuance DAX / Dragon Copilot**：产品级 SOC 2 / HITRUST 认证声明；审计日志规范；任何免责或"医生最终负责"的责任条款页面；评测数据集与准确性指标；误判申诉流程。
3. **FDA**：TPLC **独立项目页**——多个候选 URL 均 404（`/medical-devices/total-product-life-cycle-tplc-program`、`/medical-devices/medical-device-safety/total-product-life-cycle-tplc-program`、`/about-fda/cdrh-reports/total-product-life-cycle-tplc-program` 全部失败）；TPLC 内容改由**生命周期指南草案 PDF** 与 **AI/ML SaMD Action Plan PDF** 提供，二者均已打开原文。
4. **IMDRF 原始风险分类文件**：未直接获取（仅得 FDA 摘要页），故 3×3 → I–IV 的完整映射**未在本报告中给出**。
5. **工具限制（非内容限制）**：Wayback CDX API 全程 "Temporarily Offline"，无法做站点级 URL 枚举，故**不能保证已穷尽各站点所有相关页面**；本报告仅覆盖经手工构造并实测 200 的 URL。

---

## 六、本次实际抓取清单（全部 HTTP 200 且内容已解析）
**Abridge（16 个）**：`/`、`/ai`、`/ai/science-ai-evaluation`、`/ai/science-confabulation-hallucination-elimination`、`/abridge-contextual-reasoning-engine`、`/cds`、`/platform/clinicians`、`/terms/clinician`、`/terms/business-associate-agreement`、`/privacy`、`/reports/adoption-scale-impact`、`/reports/innovation-at-the-speed-of-trust`、`/best-in-klas`、`/blog/building-trusted-healthcare-ai`、`/blog/clinician-builder-cds`、`/blog/context-aware-clinical-intelligence-for-every-clinician-partner-systems`、`/sitemap.xml`

**Microsoft / Nuance（8 个）**：`microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot`、`.../clinical-workflow`、`microsoft.com/en-us/trust-center`、`learn.microsoft.com/.../offering-home`、`learn.microsoft.com/.../offering-hipaa-hitech`、Wayback `nuance.com/healthcare/ambient-clinical-intelligence.html` (2024)、Wayback Microsoft 发布博文 "Meet Microsoft Dragon Copilot"、Wayback Microsoft healthcare blog index。（另：`nuance.com` 三个 healthcare URL 现均 302 至同一 Microsoft 模板，已作为事实记录）

**FDA（13 个，含 4 份 PDF 全文抽取）**：AI/ML SaMD 页、SaMD 页、Global Approach 页、CDS FAQ 页、AI 器械清单页、PCCP 指南落地页、**PCCP 终版指南 PDF**、**Action Plan PDF**、**2019 讨论稿 PDF**、生命周期指南落地页、**生命周期草案指南 PDF**、DHCoE 页、**21 CFR Part 11（eCFR 直连）**
