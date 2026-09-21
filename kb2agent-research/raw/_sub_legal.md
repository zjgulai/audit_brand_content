# 法律 AI 合同审查产品：知识库/Playbook 设计的一手证据调研

**调研对象**：Harvey (harvey.ai)、Robin AI (robinai.com)、Luminance (luminance.com)
**调研方法**：`curl` 直取官方站点 HTML + Wayback Machine 兜底（`web_search` / `read_page` / `exa_search` 在本环境不可用，全程未使用）
**调研日期**：2026-09（以本轮抓取为准）
**证据强度标记**：
- **【已打开原文】** = 本轮实际用 curl/wayback 取回页面正文并阅读
- **【仅搜索摘要，未打开】** = 未取得正文（本报告中极少使用，凡出现必显式标注）
- **「未找到公开资料」** = 官方一手渠道（含 sitemap 全量枚举）中确实没有
- `[推断]` = 我的推断，非原文

## 抓取覆盖度与已知限制（先读）

| 项 | 状态 |
|---|---|
| harvey.ai sitemap.xml（714 条 URL） | 已枚举并解析，用于定位全部相关 slug |
| luminance.com sitemap 索引 + page/blog/insight/white-paper/customer/video 子 sitemap（323 条） | 已枚举 |
| robinai.com sitemap 索引 + pages/resources/helpCenter 子 sitemap（243 条） | 已枚举 |
| `docs.harvey.ai` | **DNS 不可解析（curl exit 6 / HTTP 000）**，不存在可访问的公开文档站 |
| `www.robinai.com/*` | **全部连接失败（HTTP 000）**；规范域名是 `robinai.com`（无 www） |
| `docs.robinai.com` / `support.robinai.com` | 不存在（404 / 连接失败） |
| Luminance 三份白皮书 PDF 全文 | **未能提取**：官方 PDF 为图片型 PDF + 子集化自定义字体编码，本地无 pdftotext/PyPDF2/Quartz，自写 zlib+content-stream 解析器只能得到二进制噪声。白皮书**落地页**已打开，PDF 本体视为未读 |
| Robin AI 两份白皮书 PDF（`LIP-white-paper-PDF.pdf` 等，已下载 17.8MB/23.1MB） | 同上，**正文未读** |
| `robinai.com/first-pass`、`robinai.com/news-and-resources/blog/earning-your-confidence-evaluations-at-robin` | 线上返回 JS 骨架（正文由客户端渲染）。后者已通过 Wayback 快照 `20260113124256` **取回全文**；前者 Wayback 亦只有骨架，**视为未读** |
| Harvey 部分 URL（`/about`、`/pricing`、`/workflows`、`/knowledge`、`/assistant`、`/solutions/*`） | 均 404，Harvey 使用 `/platform/<x>` 与 `/blog/<slug>` 结构 |

---

# 一、Harvey（harvey.ai）

## 1. 它解决什么 / 目标用户

- **定位**：面向律所与法务的一体化法律 AI 平台，合同审查是其"Contract Intelligence"产品线的一部分。
- **目标用户**：AmLaw 100 律所 + 企业法务。官方口径：**"over 60 AmLaw 100 firms"、"more than 1,500 legal teams"、"142,000+ legal professionals"**【已打开原文：[Why Attorney Oversight Makes Legal AI More Powerful](https://www.harvey.ai/blog/legal-ai-oversight)】
- 合同审查痛点定量（引 Gartner）：**法务部门 21% 的产能花在 contracting 上，高于任何其他活动；单份合同审查通常需要 20 分钟到 5 小时**。【已打开原文：[Rebuilding Playbook Review as a Multi-Agent System](https://www.harvey.ai/blog/rebuilding-playbook-review-as-a-multi-agent-system)】

## 2. 规则库怎么组织（taxonomy / 政策层级 / 阈值 / 优先级）

这是 Harvey 公开得最充分的一块。**Playbook 规则有明确的五元结构**，原文（Harvey 自己定义为 "Playbook rules are conceptually simple, and include the following elements"）：

| 字段 | 原文定义 |
|---|---|
| **Standard position** | "the ideal term a company wants to see in their contracts" |
| **Acceptable deviations** | "fallback provisions a company is willing to negotiate" |
| **Unacceptable deviations** | "dealbreakers for the contract" |
| **Guidance** | "how to interpret and apply the rule given specific deal context" |
| **Optional** | "whether or not it is ok for a clause to be absent in a contract" |

出处：**【已打开原文】[Rebuilding Playbook Review as a Multi-Agent System](https://www.harvey.ai/blog/rebuilding-playbook-review-as-a-multi-agent-system)**

**规则创建（Playbook Builder）**——规则来源与质量门：
- 可从四种来源构建：① 客户既有 playbook ② 已标注（marked up）的合同 ③ Harvey 预置模板 ④ 从零对话式引导。
- Harvey 分析来源材料后**主动提问澄清**，并在侧栏实时呈现规则成形过程；能识别偏好责任上限、保留常见 fallback、**把 outlier 条款"surface for confirmation"而不是自动写入**。
- 每条规则带 **summary、explanation、以及指向源文档的 citations**，供 playbook owner 快速审批。
- 方法论来源：Harvey 称其内置了法律工程师与内部产品律师在**构建 300+ 客户 playbook** 过程中沉淀的方法论（"how to weigh different inputs, reconcile conflicting precedents, and translate them into rules"）。
- 规则可编码：**positions, fallback language, guidance, actions, conditions, and escalation paths**。原文举例：一条数据处理规则可要求 Harvey **把非标 breach notification 条款标记给 privacy counsel，而不是自动 redline**。
- 质量校验：Harvey 会 **surface coverage gaps（覆盖缺口）、让规则更具体、建议 fallback 位置**。

出处：**【已打开原文】[Turn Your Standards Into Stronger Reviews](https://www.harvey.ai/blog/playbook-builder-in-harvey)**

**状态/风险分级 taxonomy（UI 层可见）**——Contract Intelligence 的评审界面用三态计数：
> `0 Aligned` / `0 Needs review` / `0 Deviates`

即 **Aligned（符合）/ Needs review（需复核）/ Deviates（偏离）** 三分类。【已打开原文：[harvey.ai/platform/contract-intelligence](https://www.harvey.ai/platform/contract-intelligence)】

**风险分类作为可评测任务**：Harvey 自建 benchmark 把 "Risk classification"（识别并按风险等级归类问题）作为独立指标，说明其内部确有风险等级维度，但**未公开等级名称或阈值表**。【已打开原文：Rebuilding Playbook Review...】

**阈值/优先级**：**未找到公开资料**——Harvey 未公开任何数值型阈值（如"风险分 > X 即升级"）、置信度阈值或优先级排序规则。公开材料只到"escalation paths 可配置"这一层。

## 3. 案例库怎么组织（黄金样本 / 正负例 / few-shot / 历史裁决）

Harvey 有**两条并行的"案例"通路**，都有一手描述：

**(a) Workflow / Agent 的 golden examples（few-shot 层）**
- 原文：团队可用"**their own organization's templates, golden examples, and guidelines**"来定制 agent，使 Harvey 复刻其工作方式。【已打开原文：[How Legal Teams are Working Better With 25,000+ Workflows](https://www.harvey.ai/blog/25000-custom-workflows)】
- 规模：客户已创建 **25,000+ custom workflows**。【同上】

**(b) Precedent bank（历史裁决/先例层）**
- Contract Review Agents 可**搜索 attached precedent bank**，把"我们以前到底同意过什么"直接带入当前审查；**每条 redline 旁边展示对方提案与我方已签合同中被接受立场的对比，按 clause 粒度可视化，并引回源文档**。【已打开原文：[Contract Review Agents That Turn Past Deals Into Better Outcomes](https://www.harvey.ai/blog/contract-review-agents-in-harvey)】
- 该文给出的"历史裁决回流"机制：**当最近 5 份 NDA 都接受了某条款而 agent 仍在 flag 时，Harvey 识别该 pattern 并主动建议新 standard**。同时会 **flag agent 立场已落后于最近谈判**、surface 团队实际签署结果与写定标准的不一致。
- 用户可把 **precedent documents 作为附加 context 附上**，orchestrator 与 worker 都能看到并据此调整行为。【已打开原文：Rebuilding Playbook Review...】
- Sign-off 反馈闭环（harvey 明确写为"未来/正在构建"）：原文 "**Every accepted, edited, or rejected redline helps agents understand a legal team's preferences.**" 目标是"从 users 到 accounts 的个性化系统，每份新合同需要的指引更少"。【同上】
- 团队历史合同作为新输入："search across thousands of documents for previous examples to trust agent outputs"。【同上】

**(c) 评测用黄金集（golden query sets）**
- 检索侧：与领域专家共建 **retrieval datasets — curated "golden" query sets**，专家为每条 query 标出最相关支持文档，用 precision / recall / NDCG 评分。【已打开原文：[Scaling AI Evaluation Through Expertise](https://www.harvey.ai/blog/scaling-ai-evaluation-through-expertise)】
- 合同理解侧：Contract Intelligence benchmark 的 ground truth 由**签约的 transactional attorney 与 Review tables 分别作答 → 比对分歧 → 由 Harvey 内部 Applied Legal Researchers (ALRs) 裁决分歧**；**双方一致的样本也会被抽样复核**（"ensure that agreement didn't cover up misunderstanding"）。此后每月新增、复核、评测数千个数据点。【已打开原文：[Contract Intelligence: A Scaled Benchmark](https://www.harvey.ai/blog/contract-intelligence-benchmark)】
- 数据集治理：**published 后的评测集会被 lock（不可变）**，作为可复现基线；行级 RBAC 分 public / confidential / restricted 三层。【已打开原文：Scaling AI Evaluation Through Expertise】

## 4. 误判与申诉怎么走

- **申诉入口 / 复核 SLA / 翻案回流流程**：**未找到公开资料**。Harvey 未公开任何面向终端用户的"AI 判错了 → 申诉 → 翻案"流程或时限承诺。
- 但**误判的工程处理**有明确公开描述（多 agent 冲突消解）：
  - 每个 subagent 在**自己的文档分支**上工作，每个 proposed edit 是**带 rule 标签的 tracked change**；
  - 收尾时像版本控制系统一样 merge branches：**无冲突编辑干净合入，两条规则触碰同一文本的 collision 会 escalate 给 lead agent 裁决**；
  - orchestrator 像资深律师一样"draft edits that satisfies all conflicting rules"，并做最终整体质量校验，确保**每条规则都被分类且有对应编辑**。
  - 出处：**【已打开原文】Rebuilding Playbook Review...**
- **失败模式定性**（Harvey 公开承认旧系统的误判形态）："reviews could **over-redline, miss flags, insert suggestions in the wrong location, and miss whose paper the contract was on**"。【同上】
- **人工复核入口**：Review Queue & Assignment —— 可按**自定义规则分派**合同，每个 reviewer 有独立队列；界面有 `Ready for review` 状态与 assignee。【已打开原文：platform/contract-intelligence】

## 5. 人机分工边界

Harvey 的公开立场非常明确：**AI 做 first pass，律师保留最终判断**。

- 组织级（Harvey 自己给的框架）：**AI oversight committee**"不需要 review 每一次输出"，职责是定义 approved tools、acceptable use cases、data restrictions、review standards、disclosure requirements、**escalation paths**。【已打开原文：legal-ai-oversight】
- 产品级：
  - "**agents finish the first pass before a reviewer opens the file**"；审查可后台运行，"giving users a well reasoned draft as a starting point"。
  - 所有输出给 **recommended edits + reasoning + citations to the sources behind each decision**。
  - **明确不可委托项**（Harvey 原文列举的"escalate 给人类"的判据）：
    - "Some decisions cannot be delegated... A good system identifies when a clause requires **escalating to a human with the reasoning laid out** based on the context of a deal."
    - 交易姿态（first party paper vs third party paper / 代表哪一方 / 第几轮谈判）会改变同一 clause 的可接受性。
    - 重要客户会获得更多 leeway。
    - 示例：非标 breach notification 条款 → **flag 给 privacy counsel，不自动 redline**。
  - 三个"不可自动化"的失败点：契约逻辑复杂、规则跨文档交互、**"the best edit is usually the smallest one"（lightest touch）**——Harvey 把最小改动列为"out-of-the-box AI 达不到的质量门槛"。
  - 出处：**【已打开原文】Rebuilding Playbook Review... / playbook-builder-in-harvey / contract-review-agents-in-harvey**

## 6. 可量化的公开数字（全部【已打开原文】）

| 数字 | 内容 | 出处 |
|---|---|---|
| 59% → **77%**（+18%） | Playbook review 风险分类准确率（重构前→多 agent 后） | Rebuilding Playbook Review |
| 53% → **87%**（+34%） | Redline rubric 得分 | 同上 |
| 2.6 → 3.8 分钟（+47%） | 平均延迟（为质量换取的代价） | 同上 |
| **0.2%**（≈1/500 claims） | Harvey Assistant 幻觉率；对照 Claude 0.7%、ChatGPT 1.3%、Gemini 1.9%（样本 1688 / 1140 / 1176 / 1067 句） | [BigLaw Bench: Hallucinations](https://www.harvey.ai/blog/biglaw-bench-hallucinations) |
| **-60%** 幻觉 / **+23%** 引用源准确率 / **+80%** time-to-first-word | Assistant 改版（2024-08）内部评测 | [Introducing the Next Version of Assistant](https://www.harvey.ai/blog/introducing-the-next-version-of-assistant) |
| **>95%** | 引用（citation）识别系统的内部 benchmark 准确率，经律师验证 | Scaling AI Evaluation Through Expertise |
| **65–70%** | out-of-the-box LLM 在合同 deal point 抽取上的召回（Harvey 基线对照） | Contract Intelligence Benchmark |
| **≥5%** | **律师 + Review tables 的得分比"纯律师"或"纯 LLM"单独作答高出 5% 或更多** | Contract Intelligence Benchmark |
| 22–37 | 每类合同的数据点数量区间（Side Letters 22 → LPAs 37） | 同上 |
| **4,000+** | Contract Intelligence benchmark 数据点 | 同上 |
| **200** 数据源 / **25+** 新增法域 / **60+** 法域 / **400+** 法律数据源 | Knowledge Sources 覆盖（不同时间点口径） | [Knowledge and Workflow Enhancements](https://www.harvey.ai/blog/knowledge-workflows-enhancements)、[Using Agents to Scale Harvey's Knowledge Sources](https://www.harvey.ai/blog/using-agents-to-scale-harveys-knowledge-sources) |
| **150,000 tokens** / 每源评测 | Data Factory 单源评测算力 | Using Agents to Scale... |
| 1–2 → **2–4 源/小时** | 律师合规复核吞吐量（引入 Legal Review Agent 后） | 同上 |
| **$50.90 / 22 分钟** | 最高分模型在 LAB 上的单任务成本与延迟 | [Legal Agent Benchmark: Initial Results](https://www.harvey.ai/blog/legal-agent-benchmark-initial-results) |
| **<10%** | 前沿模型在 LAB all-pass 标准下端到端完成率（Opus 4.7 7.1% 最高） | 同上 |
| **80%** | Carvana 用 Harvey 扩展 playbook 后"drafting and review time"下降幅度 | playbook-builder-in-harvey |
| 5 小时/周；**75%** | Filip & Company 每周节省；GSK Stockmann 尽调时间节省 | 25,000+ Workflows |

**明确未找到**：Harvey **未公开 auto-approval 比例、auto-clear 比例、人工复核率**。所有公开数字都是准确率/质量分/时间节省，没有"多少比例无需律师介入"的口径。

## 7. 引用 / grounding / 可解释性

- **每条规则自带 citations 指回源文档**；每条 redline 带 reasoning + citations。【已打开原文】playbook-builder / contract-review-agents-in-harvey
- **cell 级 sentence-level citations + model reasoning 直接展示**在 review table 单元格里。【已打开原文：[Review Tables That Keep Legal Teams in Sync](https://www.harvey.ai/blog/collaborative-review-tables)】
- Precedent 引用的可点击性："The citations are clickable, so you can preview the source language or jump directly to it in the uploaded agreement."【已打开原文：[Turn Precedent into Tailored Drafts](https://www.harvey.ai/blog/harvey-in-practice-turn-precedent-into-tailored-drafts)】
- **幻觉的形式化定义**（少见的严谨表述）："a factual claim made by an LLM that can be **demonstrably disproven by reference to a source of truth**"；并明确**不把理解/推理错误计入幻觉**。检测方法：先用模型把答案拆成 factual claims，再逐条对照 source of truth 判定，**并对全部模型判断做人工复核**以确认系统与人类一致性。【已打开原文：BigLaw Bench: Hallucinations】
- **不编造的工程约束**：contract 理解 benchmark 发现 LLM 两大失败模式——"overeager"（对合同四角之外的信息做假设，如 reference 引入的主协议）与"overthink"（技术上正确但过度字面）。**Harvey 明确把"模型会 surface reasoning and citations back to the source material"作为人类可纠正其错误的前提**。【已打开原文：Contract Intelligence Benchmark】
- **Auditability**：完整带时间戳的 audit log 记录每次协作事件（approvals、denials、permission changes、guest activity）；Usage and Query History APIs 与 Export Reports 提供 event-based 细粒度数据；SAML SSO、IP allow-listing、audit logs、data lifecycle management；认证 SOC2 II / ISO 27001 / ISO 27701 / ISO 42001 / CCPA / GDPR。【已打开原文：[Harvey's Governance Controls](https://www.harvey.ai/blog/harveys-governance-controls)、platform/contract-intelligence】
- **知识源权威性**（对 grounding 有直接约束）：Harvey **不用开放 web 搜索**作为法律依据，而是 **"curated domain lists ensure every result comes from a vetted government portal or authoritative legal database"**。理由原文："A law firm advising on German tax law needs results from official Bundesministerium der Finanzen guidance — not a blog post that happens to rank well."【已打开原文：Using Agents to Scale Harvey's Knowledge Sources】

**Harvey 未打开但对读者有用的链接**（存在于 sitemap，本轮未读正文）：`/blog/a-framework-for-domain-specific-evaluations`、`/blog/evaluate-law-firm-agent-governance`、`/blog/memory-in-harvey`、`/blog/governance-iso-42001`。

---

# 二、Robin AI（robinai.com）

## 1. 它解决什么 / 目标用户

- **定位**："Legal Intelligence Platform (LIP)"——合同审查、Chat 问答、Tables（结构化抽取）、Reports、Obligations、Word 插件。
- **目标用户**：企业法务（in-house）+ 私募/资管（private markets 是其显著垂直：LPA、side letters 内容极多）。行业页覆盖 private markets / insurance / financial services / technology / manufacturing / entertainment。
- 官方量化主张（首页大字）：**"80% Faster review"、"500k+ Docs processed"、"3 seconds to search for a clause"**。【已打开原文：[robinai.com](https://robinai.com/)】

## 2. 规则库怎么组织（taxonomy / 政策层级 / 阈值 / 优先级）

**关键发现：Robin 的 playbook 不是结构化 schema，而是一份"自然语言指令文档"。**

官方 Help Center 原文：
> "You'll be prompted to upload: The .docx document you want Robin to analyse and edit; and thereafter **Your playbook, which can be in either .docx or .pdf format and contains your negotiation positions or instructions.**"

- 上传后可选择**复用 Robin Library 中已存在的 playbook**，或在审查时**追加额外 context/instructions**。
- **重要限制（官方明示）**：截止该文档页面，"**At this time, Robin applies only first round playbook positions. Additional fallback or escalation positions are not yet supported.**" 且 "**Robin Review works best with clean (non-redlined) documents**"。
- 出处：**【已打开原文】[Reviewing Documents with Playbook (Help Center)](https://robinai.com/help/review-documents-with-playbook)**（该页版权年为 2019–2025）

**但 Robin 在 2025-09 宣布扩展了 playbook 能力**——这条更接近结构化政策层级：
- 支持**多轮**对方改动（edit upon edit），不再只对干净模板做 first pass。
- 能 **accept or reject counterparty edits**，并提出**最小化的、类人的 redline**。
- 官方举例给出**显式的 fallback 阶梯**：责任上限 1x 年费（standard）→ 对方改成 3x → Robin 提出 **2x（pre-approved compromise）** → 对方再提"数据泄露无限责任" → Robin 直接 redline 成 **"capped at 3x annual fees"，"preserving your further fallback position"**。
- 原文明确称这是"a compromise you've **pre-approved**"与"your **further fallback position**"——说明 Robin 的 playbook 文档中确实承载 **standard / fallback / further fallback** 的层级语义，只是以自然语言而非字段承载。
- 出处：**【已打开原文】[Robin expands playbooks to support smarter contract negotiations](https://robinai.com/news-and-resources/blog/robin-expands-playbooks-smarter-contract-negotiations)**

**风险分级 taxonomy（RAG 三色）**——这是 Robin 公开得最清楚的分级体系，出现在其 Robin University 教程中：
> - **High Risk (Red)** – Terms that significantly deviate from standard positions and require renegotiation（例：unlimited liability clauses）
> - **Medium Risk (Amber)** – Acceptable but suboptimal terms that may need adjustments（例：indemnity caps that are too low）
> - **Low Risk (Green)** – Clauses that align with preferred positions or require minimal changes

并给出实施路径："**Choose the Select answer type and assign Red, Amber, and Green options. Define clear criteria for each rating to ensure AI flags clauses that deviate from preferred positions.**"；也可退化为更简单的 **compliant / not compliant** 二值。
出处：**【已打开原文】[Best practices for identifying risks in third-party paper](https://robinai.com/news-and-resources/robin-university/best-practices-for-identifying-risks-in-third-party-paper)**

**关键限定**：RAG 分级是通过 **Robin Reports/Tables 的 `Select` answer type** 实现的**可配置输出枚举**，阈值由客户自己定义——**Robin 不提供内置的默认风险阈值或数值分**。

**Playbook/Rule 的其它结构线索**：
- Robin 的"Prompt Set / Template"体系是规则的可复用单元：**Template 由 Prompt 组成**（每条 prompt 有 Name、Answer Type），可被 Duplicate、`Save as Template`、在 Table 与 Reports 间复用；Template 的编辑会影响所有用户，而基于 Template 建的表可自由改而不回写模板。【已打开原文：[Manage Prompt Set Templates](https://robinai.com/help/manage-prompt-set-templates)、[Robin Tables](https://robinai.com/help/tables-in-robin)】
- **Answer Types**（输出 schema）：date / currency / percentage / number / drop-down selection / yes-no。【已打开原文：[Answer types now available in Robin AI Reports](https://robinai.com/news-and-resources/blog/answer-types-now-available-in-robin-ai-reports)】
- **权限层级**：Personal / Private（invite-only）/ Public 三类 Permission Group，每份上传文档必须归属一个 group；仅 Owner/Admin 可建组。【已打开原文：[Permission Groups](https://robinai.com/help/permission-groups)】

## 3. 案例库怎么组织

**(a) 先例库 = 你自己的文档库，用分类+过滤而非"golden set"**
Robin 的 precedent 机制不预制黄金样本，而是**让客户把已签合同与批准模板上传，再用多维过滤构造"precedent set"**。官方列出的过滤维度：
> Document type（MSAs/NDAs/licensing）、Counterparty characteristics（repeat vendors / strategic partners / one-off）、Time（past 18 months vs historical）、Jurisdictional considerations、Transaction size or risk profile

**(b) Robin 明确承认"先例不平等"，并把这作为卖点**
原文："**Not all precedent is equal**, with hastily agreed terms from three years ago representing undesirable contract terms, whilst a carefully crafted agreement last quarter with a similar counterparty providing invaluable guidance. Legal teams must be equipped to **discern 'gold standard' precedents from outlier agreements** containing unusual concessions."

**(c) 具体的"先例分层"prompt 模式**（可直接复用的方法论）：
- **"Have we ever?" 框架**——用接受史而非声称立场来还原真实边界：*"Have we ever accepted unlimited liability for breach of confidentiality in a vendor agreement? If so, what were the specific circumstances..."*
- **Request precedent hierarchies**——要求按 favorable/unfavorable 或频次给先例排序并标出 outlier：*"Rank the indemnification provisions in these supplier agreements from most to least favourable to [Company], noting which appear most frequently. Identify any outliers..."*
- **Combine precedent with playbook validation**——把 playbook/policy 文档一并放进 document set，让 AI 做一致性比对。
- 出处：**【已打开原文】[Use case: Close deals faster with precedent analysis](https://robinai.com/news-and-resources/robin-university/use-case-close-deals-faster-with-precedent-analysis)**

**(d) 合同"家族"关系（contract families）**
Robin 公开了自动化的**文档关联与推理**目标：master agreements / amendments / renewals / supplemental agreements 的关联，判定"哪个版本currently in force"。痛点原文："determining the current contract version requires **manually cross-referencing ten or more related documents**"。这是其"案例库"的结构维度之一（按关系链而非按单文档组织）。【已打开原文：[The Hidden Network Behind Your Contracts](https://robinai.com/news-and-resources/blog/the-hidden-network-behind-your-contracts)】（正文仅读到引言与前半部分，后文因页面结构未完整取得）

**(e) 内部评测用的 golden set（数据侧）**
- **multi-contract chat experience 含 8,500+ 样本**的 gold-standard 数据集，采用 **"four-eye" 双人复核**流程（每份标注由多于一名成员审阅批准）。
- Q&A 评测中**标注出回答所需的精确文本段落**，以便自动评估。
- 出处：**【已打开原文】[Earning Your Confidence: Evaluations at Robin](https://robinai.com/news-and-resources/blog/earning-your-confidence-evaluations-at-robin)**（线上为 JS 骨架；本报告正文取自 Wayback 快照 `https://web.archive.org/web/20260113124256/https://robinai.com/news-and-resources/blog/earning-your-confidence-evaluations-at-robin`）
- 注：该文提到的论文 **arXiv 2510.07243v1**（NLLP @ EMNLP）**本轮未打开**，仅知其存在。

## 4. 误判与申诉怎么走

- **面向用户的"AI 判错了 → 申诉 → 翻案"入口**：**未找到公开资料**。
- **复核 SLA**：**未找到公开资料**。
- **翻案后如何回流**：**未找到公开资料**（Robin 未公开任何由终端用户纠正驱动的模型/规则更新回路）。
- **可确认存在的相关机制**：
  - **人工修正通道是"导出后自己改"**：Review 完成后 "**Download File**" 得到带 redline 的 .docx，"**Open the document in Word to further review and edit the markup version provided by Robin as needed**"。【已打开原文：review-documents-with-playbook】
  - **协作与可见性**：所有 Review 会话默认私密、保存到 Workspaces，可 public 或邀请 collaborator；Tables 结果可 CSV 邮件发送。【同上 + tables-in-robin】
  - **生产环境回归测试**是 Robin 对"质量漂移"的官方应答（详见第 6 节），监控项含 **sudden hallucinations、相对 gold standard 的 accuracy/correctness/relevance 漂移、回复一致性、context 变化**。【已打开原文：Earning Your Confidence】
  - **支持入口**：help 页底部有 "Submit a Support Request"（`/help/request`）——是**支持工单**，不是误判申诉机制。【已打开原文：[robinai.com/help](https://robinai.com/help)】

## 5. 人机分工边界

- **AI 做**：自动 clause type 分析、识别 negotiation position、套用 playbook 指令、产出 redline、**在对方多轮改动中 accept/reject 并提 fallback**、生成带引用的答案与报告。
- **人做**：最终判断。Robin 的官方措辞较 Harvey 保守，明确写"amplify rather than replace"：
  > "Robin's precedent research capabilities **amplify rather than replace legal judgement**... Robin may identify that a particular fallback position consistently appears with a specific counterparty type, but it **will not have full context of a deal which may create precedent with unusual concessions**. Legal professionals use Robin to rapidly identify relevant precedents and understand their variations, then **apply professional judgement about their applicability**."
  【已打开原文：use-case-close-deals-faster-with-precedent-analysis】

- **"AI 与律师并排编辑"的边界设计**（差异化点）：Robin 能**区分"你的改动"与"对方的改动"**，只对应当响应的部分作答，"**supporting you without overriding your judgment**"。【已打开原文：robin-expands-playbooks...】

- **明确不由 AI 决定的**：`N/A` 处理——Robin 有官方文档 "**How Robin AI handles uncertainty with N/A answers**"，说明系统对无法确定的问题返回 N/A 而非猜测（**该页本轮未打开正文**，仅从 help sitemap 得知其存在；`https://robinai.com/news-and-resources/robin-university/how-robin-ai-handles-uncertainty-with-n-a-answers`）。

## 6. 可量化的公开数字（全部【已打开原文】）

| 数字 | 内容 | 出处 |
|---|---|---|
| **80% faster review** / **500k+ docs processed** / **3 秒**定位条款 | 首页主张 | robinai.com |
| **98%** | University of Cambridge Investment Management 团队在 LPA Review 上的时间节省 | Answer types now available in Robin AI Reports |
| **~90%** | 某客户跨近 10,000 份文档做网络安全通知义务排查的时间与成本节省 | 同上 |
| **80%**（内部数据集）/ **50%**（LegalBench） | LeMAJ 自动评测相对人工标注的时间节省；"especially when involved in the triaging stage" | Earning Your Confidence |
| **+11%** | LeMAJ 方法使**标注者间一致性（inter-annotator agreement）**在答案正确性维度提升 | 同上 |
| **8,500+** 样本 | multi-contract chat 的 gold-standard 数据集规模 | 同上 |
| 10 分钟 vs 半天；1.5 小时 vs 一整天；分钟 vs 数周 | Impact Food Group：定位关键条款 / 审查复杂供应商合同 / 多合同报表 | [Impact Food Group 案例](https://robinai.com/news-and-resources/blog/impact-food-group-speeds-up-contract-reviews-and-finds-answers-faster-with-robin) |
| **9/10** | 同上客户对工作负载改善的满意度评分 | 同上 |

**明确未找到**：
- Robin **未公开准确率/召回率的具体数值**（只有相对提升 +11% 与时间节省）。
- Robin **未公开 false positive 率、auto-approval 比例、% auto-cleared、人工复核率**。
- Robin **未公开任何模型准确率 benchmark 的绝对分数**（其 LeMAJ 论文在 arXiv，但本轮未打开）。

## 7. 引用 / grounding / 可解释性

- **Clickable citations 是其核心卖点**，多处强调。Reports 中可选 "**Choose whether you'd like citations URLs to be included in your Report**"；引用"takes you directly to underlined language in the relevant section in the contract for faster verification"。（**注意：Reports 的引用是 URL；Chat 的引用是可直接跳转到条款的 clickable citation。**）
- **Chat 的引用与验证流程被写成标准动作**："**4. Check the Citations** — For every answer, click the citations to view the original document clauses and provisions for verification."
- **Research 模式的引用指向外部权威源**：调用 "Research with Legal Authorities" 后，"Robin will respond with an answer that includes **citations to web sources**"，可点击打开。
- **Platform 页主张**："**AI you can validate, with pinpoint citations.** Click on citations to verify answers quickly in the underlying primary documents."
- **系统提示用户收窄 context 以保准确**（罕见的诚实工程约束）："Select the **narrowest possible document set** to ensure answers do not incorporate out of scope documents/information."
- 出处：**【已打开原文】chat-get-instant-verifiable-legal-analysis、research-with-legal-authorities-in-robin、answer-types-now-available-in-robin-ai-reports、[robinai.com/platform](https://robinai.com/platform)**
- **数据用途承诺**："Customer data will **not be used for model training, fine-tuning, or other feature development without express consent**."；AES-256 静态加密、TLS 传输加密、数据不出 Robin 的 AWS 环境；ISO27001 + SOC2 认证。【已打开原文：[robinai.com/security](https://robinai.com/security)】

---

# 三、Luminance（luminance.com）

## 1. 它解决什么 / 目标用户

- **定位**："Contract Intelligence platform"，自建专有法律模型（LPT/Luna）+ 多模型架构，覆盖 draft → negotiate → analyze → comply → investigate → collaborate 全生命周期。
- **目标用户**：**企业**（不限于法务）——官方明确把采购、财务、销售、HR、市场、合规、高管都列为 "Teams"，并以此与"只服务律师"的竞品作区隔。
- 官方主张：**1,000+ 客户**；2025 年 Series C（$75M）。【已打开原文：ai-technology、[Luminance Autopilot: A Week in the News](https://www.luminance.com/resources/blog/luminance-autopilot-a-week-in-the-news/)】

## 2. 规则库怎么组织（taxonomy / 政策层级 / 阈值 / 优先级）

**Luminance 的规则组织单元叫 "Checklist"，按"position（立场）"而非按 clause 组织。**

官方原文（VP of Product Ella Hislop）：
> "Luminance now focuses any negotiation around a business's core positions, instantly directing attention to the clauses you care about, whether they're **unacceptable, non-standard or missing altogether**. Displayed in a clear **step-by-step Checklist**, users can simply tick off each position as they complete their review, ensuring nothing gets missed."

**每个 position 输出三元组**：
> - **Summary**: what's being proposed.
> - **Reason**: **why it's not standard against internal benchmarks**.
> - **Mark-Up**: suggested alternative language which can be inserted in a click.

**政策层级（明显的 multi-tier）**：
> "Luminance also provides various mark-up options, including **preferred and fallback positions**, as well as **a clear comparison with what the business has or hasn't accepted during similar negotiations in the past**."

**"position 级分析"而非 clause 级**——这是 Luminance 的核心技术主张：
> "the analysis is provided on a **position level**... Luminance's proprietary LLM is able to apply an analysis to legal positions **across the entire contract**, ensuring any reference — conceptual or explicit — is taken into account, **rather than assessing language clause-by-clause**. For example, let's say there's a Limitation of Liability on page three, and then a reference to Limitation on Liability in the Intellectual Property clause on page five — **all of this will be considered**."

出处：**【已打开原文】[Product Feature Spotlight: Accelerate Negotiations with Luminance's AI-Powered Checklists](https://www.luminance.com/resources/blog/product-feature-spotlight-accelerate-negotiations-with-luminance%C2%92s-ai-powered-checklists/)**

**风险分级的视觉 taxonomy（红/黄）**：
> "it can conduct the first pass review of the contract in seconds, navigating to any **high-risk (the red highlights)** or **non-standard (the yellow highlights)**, and suggesting acceptable alternatives."

即 **Red = high-risk，Yellow = non-standard** 两级色标。
出处：**【已打开原文】[Auto Mark-Up: Redraft Any Contract in a Click](https://www.luminance.com/resources/blog/auto-mark-up-redraft-any-contract-in-a-click/)**

**规则库搭建方式（self-serve playbook）**：
- 官方 webinar 页标题即 "**Launch Contract Workflows Faster with Self-Serve Playbooks and Templates**"，议程包括：
  - "**End-to-end self-service playbook setup** from creation to **checklist analysis applied against all incoming contracts**"
  - "**Self-validation tools on Agent outputs** to maintain confidence and consistency in results"
  - "**Templating agents (in beta)** that turn a simple description of your template needs into an automated workflow"
  - "pre-built agents accelerate time-to-value by **handling the set-up work for you**... **apply institutional standards automatically**"
- 出处：**【已打开原文】[Launch Contract Workflows Faster with Self-Serve Playbooks and Templates](https://www.luminance.com/launch-contract-workflows-faster-with-self-serve-playbooks-and-templates/)**
- 注：该页是 webinar 落地页，**没有**给出 playbook 的字段 schema、阈值或优先级排序规则。

**"gold standards" 与"标准措辞"**：
> "AI instantly flagging **where language differs from standard wording** and acceptable, insertable alternatives suggested"；"Create **gold-standard templates** for business users"；"Enable non-legal professionals to review and amend contracts **autonomously in line with internal standards**... **all based on previously agreed language approved by Legal**."
出处：**【已打开原文】[luminance.com/solutions/legal](https://www.luminance.com/solutions/legal/)**

**阈值 / 数值分 / 优先级**：**未找到公开资料**。Luminance 公开的是红/黄二色 + unacceptable/non-standard/missing 三态 + preferred/fallback 两级，**没有任何数值阈值或置信度阈值**。

## 3. 案例库怎么组织

- **训练语料（案例库的最底层）**：
  - **220 million+ verified legal documents**（2026-06 Luna 发布文口径）。【已打开原文：[The Era of Vertical AI is Here: Introducing Luna Crescent](https://www.luminance.com/resources/insights/the-era-of-vertical-ai-is-here-introducing-luna-crescent-luminances-proprietary-legal-intelligence-model/)】
  - 早期白皮书落地页口径：**150+ million verified legal documents**（时间较早）。【已打开原文：[Building Luminance's Artificial Intelligence](https://www.luminance.com/resources/white-papers/building-luminances-artificial-intelligence/)】
  - 官网技术页口径：**"hundreds of millions of legally verified documents"**；并强调"**spent the first five years on the market working exclusively with top law firms**"，因此数据"trained, used and validated at the very highest level"。【已打开原文：[Legal AI Technology](https://www.luminance.com/ai-technology/)】
  - Luna 训练集细化：**"a carefully curated selection of challenging examples spanning around 3.4 million legal concepts and data points"**，刻意覆盖"highly complex agreements, difficult file formats, obscure drafting styles and diverse legal language"。【已打开原文：Luna Crescent】
  - 数据质量主张："**millions of contracts with a high density of legally verified labels**"、"high-quality, **sanitised** legal dataset"。【已打开原文：[What Makes Luminance's AI Legal-Grade™?](https://www.luminance.com/resources/blog/what-makes-luminances-ai-legal-grade/)】

- **客户侧案例库 = 客户自己的历史合同**（不是平台预置的 golden set）：
  > "Luminance's AI already knows how your business prefers to contract, having read and formed a conceptual understanding from **your existing contracts and past decision-making**."（Auto Mark-Up 文）
  > "Precedent is available in context, not buried in a folder."；"**Every negotiation is preserved and searchable**, so the next negotiation starts from a position of institutional knowledge rather than a blank page."（[The Future of Contract Intelligence: Why the Foundation Will Define the Winner](https://www.luminance.com/resources/insights/the-future-of-contract-intelligence-why-the-foundation-will-define-the-winner/)）

- **benchmark（评测用黄金集）**：
  - **ContractIQ Bench**——Luminance 剑桥 R&D 团队自建，"**189,000 manually annotated and reviewed data points**"，评估模型解读 liability caps、termination for convenience、confidentiality obligations 等关键条款的能力；**并用 held-out 文档 + 法律专家盲评**验证。【已打开原文：Luna Crescent】
  - 这是三家中**唯一公开了"人工标注+复核"黄金集规模**的评测集。

- **正面/负面例的显式用法**：Luna 的训练目标被描述为 **"prioritize faithful extraction from source documents. When information is not present, it is designed to identify that absence rather than invent an answer"**——即把"缺失"作为一等输出类别训练。【已打开原文：Luna Crescent】

## 4. 误判与申诉怎么走

- **面向用户的申诉入口 / 复核 SLA / 翻案回流**：**未找到公开资料**。
- **但 Luminance 对"误判/幻觉"给出了三家之中最系统的公开设计立场**，见其官方 Insight 文章 **"Human-in-the-Loop Won't Save You – Systems Designed for Accuracy and Transparency Will"**（2026-04-27）。核心论点与机制：
  1. **否定"人工兜底"作为可靠性来源**："This wasn't just a failure of AI... It was a failure of an assumption that **human oversight is a reliable safety net**."；"**the more routine verification becomes, the less reliable it gets**"；"accuracy cannot be enforced through policy alone... **policy and process are no substitutes for system design**."
  2. **准确性的三层设计**：
     - **Understanding**：合同"both iteratively and holistically"处理，"**Decomposed clause by clause, provision by provision**"；且"**Contracts are incomplete in isolation.** Their interpretation depends on prior agreements, business context, previous legal transactions."
     - **Validation**："**most systems generate an answer and trust it. We don't.** Our **verifier independently audits the answer**, automatically checked, claims examined, **citations verified, sources cross-referenced** before anything reaches the user." + "**Where confidence is low, outputs are flagged rather than presented as fact.**"
     - **Transparency**："Every answer is presented with the system's **legal reasoning (from its internal thoughts), and traceable citations** to sources from the underlying material."
  3. **对低置信的官方处理 = flag，而非输出为事实**（这是三家唯一明文写出"低置信 → 标注而非断言"的表述）。
- **出处**：**【已打开原文】[Human-in-the-Loop Won't Save You](https://www.luminance.com/resources/insights/human-in-the-loop-wont-save-you-systems-designed-for-accuracy-and-transparency-will/)**
- **对"信息不足"的官方行为**："when the AI doesn't have enough information, it **returns the question and outlines what's missing rather than guessing**."（What Makes Luminance's AI Legal-Grade?）——**这不是申诉机制，但是"拒答 + 说明缺什么"的误判防护设计**。
- **冲突/异常的处理思路**：多模型交叉验证（Panel of Judges）+ 编排层裁决，见第 7 节。

## 5. 人机分工边界

Luminance 是三家中**自动化主张最激进**的一家，且其边界表述最值得注意：

- **官方口号**："**Autonomous by default. Human by choice.**"【已打开原文：[luminance.com/autonomous-negotiation](https://www.luminance.com/autonomous-negotiation/)】
- **Autopilot（2023 年末发布，"全球首个"）**：AI 之间端到端自动谈判，**"without human intervention, between two opposing parties"**，直到签署。原文流程："each AI conducts its auto-analysis of the contract in Word, the counterparty AI can then accept or negotiate the suggested changes, continuing until both parties are satisfied, and the contract is ready for **human signature** within minutes."
- **人类保留的三件事（官方明文）**：
  > "lawyers still have full control: they can **determine how aggressively the AIs negotiate on certain positions**, **review a log of all changes made by the AI**, and always **make the final decision on whether to sign** the contract."
- **分工的行业定位**："allow AI to handle the **day-to-day negotiations of routine contracts**... so that human lawyers get time back... to focus on **complex, higher-value tasks**"；起步范围明确限定为 "**starting out with simpler, routine contracts** before moving on to more complex agreements"。
- **"Legal 保留治理"**：企业内非法律用户可自行发起自动谈判，但 "**Legal retains governance and oversight**"。
- **出处**：**【已打开原文】Luminance Autopilot: A Week in the News、autonomous-negotiation、Auto Mark-Up**
- **Agent 安全壳（"constrained subagents"）**：
  > "These **constrained subagents are orchestrated and controlled through supervisor agents**, so activities are **focused, auditable and safe**. Multiple workflows can run in parallel, and **outputs are cross validated** to keep the AI on track."
  出处：**【已打开原文】What Makes Luminance's AI Legal-Grade?**
- **"minimal manual checkpoints"** 被明确写成卖点："increased levels of efficiency and precision and **minimal setup or manual checkpoints**"。【已打开原文：[ai-technology](https://www.luminance.com/ai-technology/)】

**与 Harvey 的立场差异（重要）**：Harvey 官方文章专门论证"**广告里少讲 oversight 是 red flag**"、"Fewer checkpoints are often a risk signal, not a benefit"；Luminance 则主张"**human-in-the-loop 不是安全网**"、以"**minimal manual checkpoints**"为卖点。**两家在同一问题上给出了相反的一手立场**——这是本调研中最有对比价值的发现。

## 6. 可量化的公开数字（全部【已打开原文】）

| 数字 | 内容 | 出处 |
|---|---|---|
| **90%** | time-savings on contract review（全站复用的客户成果口径） | ai-technology / autonomous-negotiation / contract-intelligence 等 |
| **98%** | reduction in contract management costs | 同上 |
| **500+ hours** | saved on contract generation | 同上 |
| **50%** | Staples 案例的合同审查时间节省 | [legal-contract-management-software](https://www.luminance.com/legal-contract-management-software/) |
| **<5 mins** | Hitachi 案例：NDA 生成到签署 | solutions/legal |
| **16%** | NDAs 占企业合同的比例（用来说明高量产值的自动化标的） | autonomous-negotiation |
| **220 million+** | verified legal documents（Luna 训练语料，2026-06） | Luna Crescent |
| **150+ million** | verified legal documents（较早口径） | 白皮书落地页 |
| **~3.4 million** | legal concepts and data points（Luna 精选训练集） | Luna Crescent |
| **189,000** | ContractIQ Bench 人工标注并复核的数据点 | Luna Crescent |
| **+5%** | Luna 在合同理解任务上相对领先通用模型的准确率优势（held-out + 专家盲评） | Luna Crescent |
| **~4x** / **200–400 tokens/s** | Luna 生成速度；"Work that takes 30 seconds on a general model takes under eight on Luna" | Luna Crescent |
| 20 分钟–2 小时 | 律师通常花在 NDA 审查上的时间（对照基准） | Luminance Autopilot |

**明确未找到**：
- Luminance **未公开 false positive 率**。
- Luminance **未公开 % auto-cleared / auto-approval 比例 / 人工复核率**——尽管其 Autopilot 号称无人干预，**没有给出"多少比例的合同可以完全自动走完"的数字**。
- Luminance **未公开 ContractIQ Bench 的绝对分数**（只说 +5% 相对优势）。
- 官网上的 90%/98%/500+ 三个数字是**跨页面复用的营销口径**，无客户名与方法学披露（Staples 50% 与 Hitachi <5min 有具名案例）。

## 7. 引用 / grounding / 可解释性

- **"Panel of Judges"（多模型互检）**——Luminance 的核心可解释性/准确性叙事：
  > "We refer to our multi-model approach as the '**panel of judges**', similar to the way the Supreme Court brings together different expertise to come to a reliable final judgment. Working together, these models **check each other's homework** as they process a request. The final output is **validated by an orchestration layer acting like a supreme judge**. These thorough **guardrails** help deliver clear, transparent and trusted outputs."
  出处：**【已打开原文】ai-technology**
- **显式推理展示**：
  > "We use advanced reasoning models and agents that **show their workings — step-by-step logic, calculations, and clear rationales**... And crucially, when the AI doesn't have enough information, it **returns the question and outlines what's missing rather than guessing**. We also **point directly to the source passages the AI relied on** to reach its outcome, so users can quickly verify the answer themselves. That's how lawyers work in practice; no associate simply says, 'Yes, they're liable.' They present the evidence, logic and calculations behind the conclusion."
  出处：**【已打开原文】What Makes Luminance's AI Legal-Grade?**
- **Autonomous negotiation 也要求可追溯**："Every decision is backed by **full transparency into the reasoning and negotiation history** behind it."；"Users see not just the outcome, but the **reasoning and references** that informed it."【已打开原文：autonomous-negotiation】
- **审计日志（Autopilot 场景）**：律师可 "**review a log of all changes made by the AI**"。【已打开原文：Luminance Autopilot】
- 合同情报页："delivering **cited answers** from first review through portfolio insight"；"**retaining not just what was agreed, but the reasoning behind every decision**"。【已打开原文：contract-intelligence】
- **安全/合规**：ISO 27001 + SOC2；AWS 托管或客户本地部署；设有由 Lord Evans（前 MI5 总干事）、Darktrace 创始 CTO 等组成的安全顾问委员会。【已打开原文：[luminance.com/security](https://www.luminance.com/security/)】
- **Luna 的自研动机含可解释/可控**："Luna is deployed within **Luminance's own AWS environment**, reducing reliance on external model providers and limiting data exposure to additional sub-processors."【已打开原文：Luna Crescent】
- **术语表（可作为其概念体系的旁证）**：Luminance 维护公开的 Legal AI Glossary，其中与本主题直接相关条目包括
  - **Grounded Generation**："Forcing AI outputs to cite retrieved sources. In legal practice, grounding improves trust, auditability, and defensibility by tying summaries or redrafts to verifiable documents."
  - **Human-in-the-Loop**："Attorney validation within AI workflows. Balances speed with accuracy and ethical responsibility."
  - **AI Risk Scoring**："Algorithms that assign risk levels to contracts, vendors, or matters based on **clauses, obligations, and counterparty posture**."
  - **Automated Clause Tagging**："AI that classifies clauses by **type, obligation, and risk level**."
  - **Audit Trails**："Chronological records of every action taken in a system... automatically **tagging risky changes, detecting anomalies**, and generating defensible reports."
  - **Hallucination Mitigation**、"Black-Box Models"（"raise risks for explainability and admissibility"）、**Chain-of-Thought**（"improves transparency in how conclusions (e.g., risk scores) are reached"）
  出处：**【已打开原文】[Legal AI Glossary](https://www.luminance.com/legal-ai-glossary/)**
  **注意**：这是营销站的术语表（定义偏通用），**不等于 Luminance 产品的实际 schema**；引用时须谨慎。

---

# 四、横向对比与关键结论

## 4.1 规则库组织：三种截然不同的范式

| 维度 | Harvey | Robin AI | Luminance |
|---|---|---|---|
| 规则的载体 | **显式结构化 schema**（5 字段） | **自然语言文档**（.docx/.pdf 上传） | **Checklist / position**（红黄标注 + preferred/fallback） |
| 层级 | standard / acceptable / unacceptable / guidance / optional | standard → pre-approved compromise → further fallback（文内语义，非字段） | preferred / fallback + accepted-history 对比 |
| 状态分类 | **Aligned / Needs review / Deviates** | **Red / Amber / Green**（可配置 Select） | **unacceptable / non-standard / missing**；Red=high-risk，Yellow=non-standard |
| 阈值 | 未公开 | 由客户自行定义（无默认值） | 未公开 |
| 规则创建 | Playbook Builder：从标准/历史合同/模板/对话生成 + 覆盖缺口检测 + 每条规则带 summary/explanation/citations | 客户自撰文档；Template/Prompt Set 复用 | Self-serve playbook setup；checklist 自动套用于所有 incoming contracts |
| 规则维护 | 用户指令更新 + 基于已签数据主动建议更新 | 未找到公开资料 | Self-validation tools on Agent outputs |
| 规则粒度 | 单条 rule 一个 subagent | prompt 级 | **position 级（跨条款聚合）** |

**要点**：**只有 Harvey 公开了 playbook 的字段级 schema**。Robin 的 playbook 本质是"给 AI 读的谈判立场文档"，Luminance 的规则单元是 Checklist 里的 position。三家都很默契地**不公开数值阈值**。

## 4.2 案例库组织

| | Harvey | Robin AI | Luminance |
|---|---|---|---|
| 黄金样本 | workflow 支持 "golden examples"；评测侧有 golden query sets | 8,500+ 样本 gold-standard 数据集（four-eye 复核） | **ContractIQ Bench：189,000 人工标注并复核的数据点** |
| 客户历史数据 | Precedent bank（附加上下文），clause 级可视化对比 | 客户自有文档库 + 多维过滤构造 precedent set | 客户既有合同与 past decision-making |
| 正负例 / 拒答 | LLM 幻觉的 form 化定义（可被 source of truth 证伪） | **N/A answers**（专门的 help 文档，本轮未打开） | **把"缺失"作为一等输出类别训练**（"identify that absence rather than invent an answer"） |
| 数据治理 | published 评测集 lock；行级 RBAC 三层 | Permission Groups（Personal/Private/Public） | 数据不自研模型外流；自建 AWS 部署 |

## 4.3 误判、申诉、回流

- **三家均未公开面向终端用户的"申诉入口 + 复核 SLA + 翻案回流"机制。** 这是本次调研最一致的空白。
- 三者提供的是**不同替代物**：
  - Harvey：**多 agent 冲突自动 escalate 到 lead agent**；人工通过 Review Queue/Assignment 介入；接受的 redline 反馈用于个性化（官方表述为"未来能力"）。
  - Robin：**导出 .docx 到 Word 自行修改**；生产环境回归测试监控质量漂移；支持工单。
  - Luminance：**低置信输出被 flag 而非断言**；多模型交叉验证 + 编排层裁决；信息不足时**回问并说明缺什么**。

## 4.4 人机分工：两家给出了相反的一手立场（最有价值的对比）

- **Harvey**（[legal-ai-oversight](https://www.harvey.ai/blog/legal-ai-oversight)）："**Fewer checkpoints are often a risk signal, not a benefit**"——把"宣传少人工介入"定义为 red flag；主张 oversight 是能力而非负担。
- **Luminance**（[human-in-the-loop-wont-save-you](https://www.luminance.com/resources/insights/human-in-the-loop-wont-save-you-systems-designed-for-accuracy-and-transparency-will/)）："**Human-in-the-Loop Won't Save You**"——把"依赖人工兜底"定义为设计失败；口号 "**Autonomous by default. Human by choice.**"，并把 "**minimal manual checkpoints**" 写成卖点。
- Robin 居中：强调 "amplify rather than replace legal judgement"，并设计了"AI 与律师并排编辑、不覆盖你的判断"的交互。

## 4.5 公开数字的可得性对比

| | 准确率类 | 幻觉类 | 时间节省 | 自动化率（auto-clear） |
|---|---|---|---|---|
| Harvey | ✅ 丰富（59→77%、53→87%、≥5%、>95%、65–70%） | ✅ 0.2%，含基线对照与方法学 | ✅ | ❌ **未公开** |
| Robin | ⚠️ 仅有相对提升（+11% IAA、LeMAJ 省 80%/50% 时间） | ⚠️ 仅监控项列举，无数值 | ✅ | ❌ **未公开** |
| Luminance | ✅ 189k 标注点、+5%，但无绝对分 | ❌ 无数值 | ✅ 90%/98%/500+ | ❌ **未公开** |

**结论：三家中没有任何一家公开 auto-approval / auto-clear / 人工复核比例。** 公开数字全部集中在"准确率、时间节省、成本节省"，回避了"多少比例完全不需要人"这一最关键的自动化边界问题。

---

# 五、未能取证的清单（诚实披露）

1. `docs.harvey.ai` —— **DNS 不可解析**，Harvey 无可公开访问的产品文档站。
2. `www.robinai.com` 全站 —— **连接失败**；官方规范域名为 `robinai.com`。
3. `docs.robinai.com` / `support.robinai.com` —— 不存在。
4. Luminance 三份白皮书 + Robin 两份白皮书 **PDF 正文** —— 已下载但**文本提取失败**（图片型 PDF + 子集化自定义字体编码；本机无 pdftotext / PyPDF2 / Quartz）。落地页已读，PDF 内容视为未读。
5. `robinai.com/first-pass` —— JS 骨架，Wayback 亦无正文，**未读**。
6. `robinai.com/news-and-resources/robin-university/how-robin-ai-handles-uncertainty-with-n-a-answers` —— 存在但**本轮未打开正文**（已从 help sitemap 确认存在）。
7. Robin 论文 `https://arxiv.org/html/2510.07243v1`（LeMAJ，NLLP @ EMNLP）—— **未打开**。
8. Luminance `The Hidden Network...` 仅读到前半（Robin 的同名主题文章）；Harvey `/blog/a-framework-for-domain-specific-evaluations`、`/blog/evaluate-law-firm-agent-governance`、`/blog/memory-in-harvey`、`/blog/governance-iso-42001` —— 存在于 sitemap，**未读正文**。
9. **三家均未公开**：数值风险阈值、置信度阈值、误报率、申诉入口、复核 SLA、翻案回流流程、auto-approval 比例。

**本报告所有 URL 均为本轮实际取回内容者**；未取回者一律在上表中列出，未混入正文引用。
