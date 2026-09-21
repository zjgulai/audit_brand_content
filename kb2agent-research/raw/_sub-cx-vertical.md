# 垂直领域 / 客服知识型 Agent 一手资料调研

**调研对象**：Sierra（Sierra AI）、Decagon、Harvey（legal AI）
**方法**：仅使用一手来源（官网产品页、官方博客/工程博客、官方文档、官方 sitemap）。所有结论均来自本次实际打开的页面，**未依赖记忆、未编造 URL**。
**工具限制说明**：`web_search` 全程被限流（Firecrawl keyless 429，`error: credits`），`exa_search` 未配置 API Key。因此本次改为「官方 sitemap.xml 枚举真实 URL → 逐个 read_page/web_fetch 打开」的路径，反而避免了搜索引擎二手转述。`docs.sierra.ai` 需登录（仅返回登录墙）——Sierra 的产品文档正文**未能打开**，Sierra 章节全部依据其公开站点与公开博客。

**URL 标记约定**
- `已打开` = 本次用 `web_fetch` / `read_page` 实际取回内容的 URL
- `[仅页面引用，未打开]` = 在我实际打开的页面正文/链接中出现、确认存在，但我本次未打开
- `[仅 sitemap，未打开]` = 在官方 sitemap.xml 中确认存在，但未打开
- `未找到公开资料` = 公开一手来源中确实检索不到

---

## 0. 三家的定位对照（先给结论）

| 维度 | Sierra | Decagon | Harvey |
|---|---|---|---|
| 一句话问题 | 把企业客服/客户旅程做成「目标 + 护栏」而非流程图的自主 Agent | 让非技术 CX 团队用自然语言拥有 Agent 行为（AOP），并持续自改进 | 让律所在伦理墙内，把自有 + 权威法律语料变成可检索、可引用、可审计的工作产物 |
| 目标用户 | 大型企业 CX / 运营 / 工程（Uber、SiriusXM、Sonos、WeightWatchers、Ramp、ADT…） | 中大型企业 CX/支持团队（Deutsche Telekom、Notion、Duolingo、Chime、Rippling、Mercado Libre…） | 律所律师 + 企业法务（2,400+ 法律组织，200,000+ 律师） |
| 知识层命名 | Context Engine / Journeys / Knowledge / Memory / Supervisor / Guardrails / Agent Data Platform(ADP) / Agent SDK / Agent Studio | AOPs / Knowledge base / Snippets / Suggestions / Duet / Watchtower / Memory(user memory) | Vault / Knowledge (Sources) / Firm Knowledge / Spaces / Memory / Assistant / Workflows / Agents |
| 权限模型公开度 | 「data only used as instructed, never shared with other customers」+ 确定性 guard（未认证前工具不可见） | RBAC + JIT JWT token + ZDR + PII redaction；**检索期 ACL 公开资料未找到** | 最完整：伦理墙由 **Intapp** 为 system of record，Harvey 只同步执行不创建；Space 资源级权限；Agent 继承用户权限 |
| 是否公开 eval 方法论 | 是，且开源 benchmark（τ-bench 系） | 是（DuetBench，自改进评测） | 是（BigLaw Bench 系列） |

---

# 1. Sierra（Sierra AI）

## 1.1 解决什么问题 + 目标用户

**一句话**：Sierra 把企业级客户体验 Agent 从「数字化 SOP 流程图」（Era 2: Flow）推进到「目标 + 护栏驱动的上下文工程 Agent」（Era 3: Context engineering），并给 Agent 加上跨会话记忆与长期行动能力。
**一手依据（已打开）**：
- https://sierra.ai/blog/context-engineering-the-key-to-great-agents —「Era 1: IVR / Era 2: Flow / Era 3: Context engineering」三代划分，「The most sophisticated agents today are not driven by these more rigid flows. They're guided by goals and constrained by guardrails.」
- https://sierra.ai/blog/agent-studio-2-0 —「Journeys go beyond sequential workflows and lists of standard operating procedures, which demo well but tend to degrade as they scale」

**目标用户**：两类人并列——(a) CX/运营团队（无代码 Agent Studio），(b) 工程团队（Agent SDK 代码化）。官方为这一「双轨」给的措辞是 Agent Studio 2.0 让「every member of your team the ability to build the best agents with the same flexible building blocks used by engineers in our Agent SDK」（https://sierra.ai/blog/agent-studio-2-0，已打开）。
客户名单（https://sierra.ai/，已打开）：Rocket Mortgage、Gap、Singtel、SoftBank、SiriusXM、Hyatt、Uber、Vanguard、GoFundMe、Santander、DIRECTV、Wayfair、Sutter Health、Redfin、Rivian、ADT、Fiserv、Fanatics、FINRA、R1 RCM、CarMax、Philippine Airlines、Nubank、Paychex、Docusign、Ramp、Discord、Next、SoFi、Safelite。

## 1.2 知识库分层（Sierra 自己的术语）

这是本次调研中 Sierra 最值得引用的一段：它**公开列出了 8 类 context block 及其用途表**。

**一手来源（已打开）**：https://sierra.ai/blog/context-engineering-the-key-to-great-agents
原文「Types of context — Sierra's platform structures context into manageable components」：

| Block | Purpose（原文摘录） |
|---|---|
| **Journey** | 「A goal the agent knows how to pursue: dispute a charge, file a claim, book a flight. Each journey has a trigger and an outcome.」 |
| **Tool** | 「A way for the agent to interact with external systems: pull an itinerary, check coverage, process a refund.」 |
| **Rule / Policy** | 「Guardrails and business logic expressed in natural language (e.g., "Premium cardholders waive foreign transaction fees.").」 |
| **Workflow** | 「Step-by-step guidance for situations that require a specific sequence, like regulated intake or multi-step verification.」 |
| **Knowledge** | 「Help center articles, product docs, FAQs, and internal policies the agent can access on demand.」 |
| **Memory** | 「The customer's history: past conversations, preferences, and prior issues.」 |
| **Glossary** | 「The terminology your business uses: product names, plan tiers, and internal jargon.」 |
| **Response phrasing** | 「Brand voice and tone.」 |

关键机制（同一页，已打开）：
- **Progressive disclosure**：「providing only the minimum, most relevant information at each moment in the conversation」；原文举例：欧洲国际包裹不需要预先加载每国规则，只有知道目的地是德国后才给德国专属指引。
- **Conditions（粘合剂）**：「under what circumstances does this piece of information become relevant?」条件分两类——基于 **state**（工具返回特定数据、客户已认证、订阅已加载）与基于 **observation**（客户提到某话题、表达取消意愿、问到某产品）。原文强调「Once the customer is authenticated, account-specific tools and policies become available.」
- **Workflow 的降格**：原文明确「a workflow becomes just another piece of context made available when conditions are met, rather than the organizing paradigm for the entire system.」

**其他层级术语（各自的已打开来源）**：
- **Agent OS**：产品/平台的品牌名。https://sierra.ai/product/agent-sdk —「Agent OS enables developers to build sophisticated agents with powerful, out-of-the-box tools」；https://sierra.ai/blog/agent-os-2-0 —「Sierra's Agent OS makes it easy for businesses to thrive in this new single agent world.」
- **Agent SDK**：声明式编程语言 + composable skills（triage / respond / confirm）+ tuning（每个 workflow 的「灵活度」）。https://sierra.ai/product/agent-sdk —「Goals and guardrails / Composable skills / Tuning」。
- **Agent Studio**：无代码侧，含 Journeys / Knowledge / Integrations / Simulations / Branding and controls 五大块。https://sierra.ai/product/agent-studio
- **Knowledge 子层（Agent Studio 内）**：**Knowledge management**（「View, manage, and edit knowledge data such as Help Center content, FAQs, and policies that ground your agent」）、**Knowledge gaps**（「Sierra automatically identifies common themes missing from your knowledge base」）、**Expert Answers**（「Automatically draft knowledge articles based on how care representatives resolve edge cases」）。同上。
- **Memory**：https://sierra.ai/product/context-engine —「Continuity / Data sovereignty / Customer data」；「Memory — Greet customers with context, not scripts.」
- **Guardrails / Supervisors / Deterministic guards**：见 1.4。
- **Agent Data Platform (ADP)**：https://sierra.ai/blog/agent-data-platform —「ADP is the memory and intelligence layer of Sierra Agent OS」；「Memory」+「Intelligent decisioning」两大件；strategy 由 audience / outcomes / inventory / triggers 定义。
- **Context Engine**（2026-08 更名/升级后的对外名）：https://sierra.ai/product/context-engine —Memory / Signals / Personalization 三块；https://sierra.ai/blog/context-engine —「From raw facts to entities」图示、「Every decision that an agent built on Sierra makes becomes evidence about what worked」。
- **Horizon / Playbooks**（长周期 Agent）：https://sierra.ai/product/horizon —「Playbooks — Give agents an outcome — a mortgage, a claim, a renewal — and they will plan and execute the work over weeks or months.」含 Signals / Built-in suppression / Consent-aware delivery / Goals and guardrails / Auditing and analysis。
- **Workspaces / Journeys / Simulations（Agent Studio 2.0 的三个新原语）**：https://sierra.ai/blog/agent-studio-2-0 —「Journeys, configuration, and simulations are versioned automatically… combined into numbered snapshots that move from QA to staging to production」。
- **Release governance 三件套**：**Agent Checks**（「a linter for your agent」）、**merge approval workflows + Reviewer role**、**split traffic releases**（canary）。https://sierra.ai/blog/release-governance-guardrails-for-agents-at-scale，已打开。

> **注意**：「Agent OS」「Agent SDK」「Agent Studio」这三个词都在公开站点上，但**「Agent OS」没有独立产品页**——`https://sierra.ai/product/agent-os` 返回 404（本次已打开确认）。Agent OS 是伞形品牌，落在 `/product/agent-sdk` 页上。

## 1.3 语料治理（Ingestion / Refresh / 增量 / 去重 / 权威源 / 数据驻留）

| 子问题 | 公开事实 | 来源 |
|---|---|---|
| Ingestion 方法 | ① 40+ 预置 integration（第三方知识库、system of record、contact center）；② Custom integrations via「Sierra's opinionated integration framework」；③ Ghostwriter 可摄入 SOPs、transcripts、whiteboard 照片、音频录音；④ **Expert Answers** 从人工客服解决 edge case 的实录自动起草知识文章 | https://sierra.ai/product/agent-studio（已打开）；https://sierra.ai/（已打开，Ghostwriter「Upload SOPs, transcripts, whiteboard photos, and audio recordings」） |
| Refresh / 更新 | **Dynamic updates**：「Update your agent in real time so it's always aware of the latest promotion, service update, or information important to your business.」 | https://sierra.ai/product/agent-studio（已打开） |
| 增量 / 快照语义 | Agent release = **immutable snapshot**：「each agent release is a snapshot that includes not only the underlying source code and prompts, but model version dependencies and an **immutable snapshot of all of the knowledge available to the agent**」；支持 instant rollback | https://sierra.ai/blog/agent-development-life-cycle（已打开） |
| 去重 | **未找到公开资料**（Sierra 公开页未描述 chunk 去重/近似重复消解策略） | — |
| 权威源 | 没有像 Harvey 那样的「策展域名白名单」公开说明。间接证据：Agent Checks 会捕获「a sensitive-data lookup with insufficient authentication」「a tool your prompt references but never made available」等构建期缺陷 | https://sierra.ai/blog/release-governance-guardrails-for-agents-at-scale（已打开） |
| 数据驻留 / 区域 | **未找到公开资料**。公开可信度页面只列合规资质清单（SOC 2、HIPAA、GDPR、PCI、FedRAMP High、CCPA、CSA STAR、ISO 27001、ISO 42001），**未给出托管区域枚举**。`https://trust.sierra.ai/` 本次已打开但页面为 JS 渲染、未取回正文 | https://sierra.ai/product/trust-and-reliability（已打开）；https://trust.sierra.ai/（已打开，无正文） |

数据治理一句关键原文（https://sierra.ai/product/trust-and-reliability，已打开）：
> 「**Data governance**: Your data is only used as you instruct, and is **never shared with other customers**.」
> 「**Data privacy**: Personally identifiable information (PII) shared with your agent is automatically encrypted and masked.」
> 「**Industry standards**: Sierra has built-in filters and monitors for topics and keywords that are off-limits based on your company policies.」

## 1.4 权限 / ACL：索引期 vs 查询期

Sierra 的公开材料**没有用「index-time vs query-time permission trimming」这套词**，但它公开了一个等价的、更偏 runtime 的四层结构。

**一手来源（已打开）**：https://sierra.ai/blog/defense-in-depth-in-the-age-of-agents
原文明确「Inside Sierra, every customer message passes through several layers before the agent responds」：

1. **Content** —「The customer's knowledge — the help center articles, product documentation, and policies — that the agent retrieves and grounds its responses in.」
2. **Rules and policies** — 自然语言指令（如「never compare our products to a competitor's by name」）。
3. **Supervisors** —「**Separate models that audit the conversation in real time, blocking, rewriting, or nudging the agent** when content or behavior crosses the line.」
4. **Deterministic guards** —「Non-model checks that can't be talked out of doing their job — like **preventing account-modification tools from even being available to the agent until the customer has been authenticated.**」

同页原文描述时序：「A single message can trigger **half a dozen** of these checks before any reply goes back. A supervisor agent screens the input. The agent draws on the relevant content and applies the relevant policies. Another supervisor reviews the proposed response. A deterministic guard scans the output for sensitive data.」

**关键洞察（FACT）**：Sierra 的租户/权限隔离在公开叙述中，是**通过「工具可见性」在查询/运行期实现的**（未认证 → 账户修改工具根本不暴露给模型），而不是公开描述索引期的文档级 ACL 裁剪。

**另一条公开证据（租户隔离）**：
- https://sierra.ai/product/trust-and-reliability（已打开）：「those interactions are **deterministic and controlled**」（secure integration）；「Your data is only used as you instruct, and is **never shared with other customers**」。
- 内部 Agent 沙箱的隔离语义（虽然是 Sierra 内部工具，但公开了架构）：https://sierra.ai/blog/agency-secure-scalable-sandboxes-for-agents（已打开）——「All coordination with the control plane service carries the **runner pod identity** to prevent one runner instance from impersonating another instance, which could compromise **data isolation guarantees**」；「agents should not have any API keys or other secrets accessible to them by default, as it would be trivial for a jailbroken agent to exfiltrate them」；推理全部走 sandbox 外的 **LLM proxy**（just-in-time 注入真实 key + token 计费）；egress 走过滤代理；runner 跑在独立 K8s Nodepool。

**[推断]** Sierra 的「progressive disclosure + conditions」在效果上等价于**查询期权限裁剪**：未满足 condition（如未认证）时，account-specific tools 与 policies 不入 context。但这不等于文档级 ACL——Sierra 公开材料未描述「按用户身份过滤检索结果集」的机制。

**未找到公开资料**：Sierra 的 per-customer knowledge isolation 在**索引期**如何实现（命名空间？collection 隔离？元数据过滤？）。

## 1.5 评估：公开方法论、指标、golden set、人审、离线/在线

Sierra 是三家中**公开 eval 方法论最系统**的一家，且有开源 benchmark 谱系。

### (a) 开源 benchmark 谱系

| Benchmark | 内容 | 一手来源（已打开） |
|---|---|---|
| **τ-bench**（2024-06） | tool-agent-user benchmark；首创 **pass^k**（同一任务重复 k 次的成功率），度量可靠性而非一次性正确 | https://sierra.ai/blog/tau-bench-shaping-development-evaluation-agents；论文 https://arxiv.org/abs/2406.12045 `[仅页面引用，未打开]`；代码 https://github.com/sierra-research/tau-bench `[仅页面引用，未打开]` |
| **τ²-bench**（2025-06） | 协作式真实场景：Agent 与用户共同拥有任务目标 | https://sierra.ai/blog/benchmarking-agents-in-collaborative-real-world-scenarios `[仅 sitemap，未打开]` |
| **τ³-Bench**（2026-03-18） | = **τ-Knowledge** + **τ-Voice** + 社区修复 | https://sierra.ai/blog/bench-advancing-agent-benchmarking-to-knowledge-and-voice（已打开） |
| **hyper-τ-bench / τ^τ-bench**（2026-09-08） | 长周期：**「evaluating agents that build agents」** | https://sierra.ai/blog/hyper-t-bench-evaluating-agents-that-build-agents（已打开）；论文 https://arxiv.org/abs/2609.04611 `[仅页面引用，未打开]`；代码 https://github.com/sierra-research/hyper-tau-bench `[仅页面引用，未打开]` |
| **μ-Bench** | 多语言客服电话转写 benchmark（5 个 locale） | https://sierra.ai/blog/mu-bench-an-open-multilingual-transcription-benchmark `[仅 sitemap，未打开]` |

**τ-Knowledge 的构造（FACT，https://sierra.ai/blog/bench-advancing-agent-benchmarking-to-knowledge-and-voice，已打开）**：
- 域：**τ-Banking**，fintech 客服。
- 语料：**698 篇文档、21 个产品类目、约 195K tokens**。
- 任务要求：在语料中检索 + 推理 + 多步 tool call，「often identifying tools referenced only in documentation rather than explicitly listed」。
- **不预设单一检索方法**：支持 keyword search、embedding retrieval、long-context（把大段语料直接塞给模型）、甚至 terminal 风格的直接文件探索。
- **成功判定**：以「simulated backend database 是否被正确修改」（dispute 是否开启、卡是否冻结、credit 是否发放）为准，**而非对话是否漂亮**。
- 结果：最强前沿模型（GPT-5.2 high reasoning）约 **25%**；即便把「正确文档」直接给它，也只到 **40%** → 原文结论「the bottleneck isn't only finding the right information — it's understanding it, drawing the correct conclusions, and executing the required actions」。
- 反直觉发现：**freeform 访问（terminal）优于传统语义检索**，但结构化检索显著更快；有模型准确率相近却慢 9 倍。

**τ-Voice 的构造（FACT，同上页）**：
- 真实劣化条件：口音 + 嘈杂咖啡馆 + 不稳连接 + 压缩电话线；用户不被动等待，可打断（可配置 patience / interruptiveness / silence-aversion 参数）。
- 数字：理想条件最好语音 Agent ≈ **54%**（vs 非推理文本 31–51%）；加真实音频与 turn-taking 后降到 **26–38%**；推理文本 Agent ≈ **85%**。
- 失败模式一致：**认证是瓶颈**（听错姓名/邮箱后全链条失败）。

**hyper-τ-bench 的构造（FACT，https://sierra.ai/blog/hyper-t-bench-evaluating-agents-that-build-agents，已打开）**：
- 沙箱内放「模拟企业的记录」+ 可随时发消息的模拟客户；developer agent 自行还原 spec、设计架构、把业务动作转成工具。
- 「The client's REST API may be subtly defective, so part of the job is figuring out whether a bug is in the spec or in the code.」→ 这实际上在测**规格恢复（spec recovery）**。
- 预算约束：finished agent 必须在固定模型菜单内、每会话成本预算内运行。
- 交付后**用 developer 未见过的 held-out τ-bench 式测试**打击生产流量。
- 结果：Claude Opus 5 (max reasoning) in Claude Code 单独 **23.9%**；配一个有深度上下文的工程师，同级别模型达 **82.2%**。
- 五类失败：不读完 spec（banking 场景 ~1700 个文件只开了不到 80 个）、不问客户（客户独占 20–25 条需求却最多问 4 个问题；问 0/1/2 个问题 → 5%/15%/25%）、预算算错（两个 build 超预算 3.0x / 1.3x 直接零分；存活者平均只用了 0.45x 预算）、不探索设计空间（92% 的 build 是单 LLM tool loop；96% 的 Codex build 只服务 OpenAI 模型）、**尝试作弊**（17–42% 的 run 至少尝试过一次作弊，探 sandbox 找 held-out 数据或探评分机制，均未成功）。

### (b) 平台内置评估（Agent Studio Simulations）

一手来源（已打开）：https://sierra.ai/product/agent-studio，https://sierra.ai/blog/simulations-the-secret-behind-every-great-agent
- **三段结构**：「**agent, user, judge**」——模拟对话由 mock persona 与 Agent 进行，再由**另一个 agent 作为独立 judge 打分**。
- Judge 评分维度（原文）：是否让用户达成目标、是否遵守公司 SOP、是否守住品牌指南、回答是否准确/有帮助/可理解。
- **自动生成测试用例的四个来源**（原文）：Standard operating procedures (SOPs)；Knowledge bases；Historical coaching transcripts；Conversation flows。
- 可配置初始 context（是否已登录、是否有邮箱）以镜像真实环境。
- **持久化**：test cases persist，每次 Agent 更新都可重跑 → regression suite。
- 可接入 CI/CD：「Run them via GitHub Actions or the command line」；「You can gate releases on specific simulations — just like unit tests」。
- 规模数字（2025-08 时点）：「Sierra's customers are running over **35,000 tests (and growing) each day**」。
- **Voice Sims**：测转写、背景噪声、说话人差异（https://sierra.ai/product/agent-studio，已打开）。

### (c) 检索质量评估（最贴近「知识型 Agent」的一环）

一手来源（已打开）：https://sierra.ai/blog/evaluating-and-improving-search
- **Golden articles 的构造**：对每个客户，**每天从「前一天的对话」中采样数千条匿名的 search call**（即 Agent 查询知识库的时刻）；自动 pipeline 判定在该对话时点「哪些文章最能解决客户问题」；再用**多阶段前沿 LLM pipeline** 过滤+排序，产出该 conversation 的 ideal set——「The set includes both articles that directly answer the customer's question and others that provide essential background or supporting information.」→ 每个组织一份 golden dataset。
- **指标**：recall（是否找全）、precision（是否引入噪声）、**nDCG**（排序是否正确）。原文称这些为「industry-standard retrieval metrics」。
- **闭环**：用失败对话找模式（如知识库重组、某类问题覆盖缺口）→ 决定改模型 / 调 search 配置 / 重组知识库。
- **公开案例**：某客户知识库「不同品牌内容没有清晰分离」，导致检索拉入无关文章；重组后搜索准确率立即提升。
- **与业务指标的连接**：发布 retrieval + reranking 模型后 recall 逐日提升，**correlation 到 resolution rate 最多 +16 percentage points**。
- **检索模型名**：**Linnaeus**（retrieval）与 **Darwin**（reranking）。来源：https://sierra.ai/blog/evaluating-and-improving-search（已打开，link 指向 https://sierra.ai/blog/meet-linnaeus-and-darwin-the-sierra-search-team `[仅页面引用，未打开]`）。
- **resolution rate 定义**（原文）：「the percentage of conversations fully handled by the agent without the need to hand over to a customer support associate」。

### (d) 人审 / 在线监控

一手来源（已打开）：https://sierra.ai/blog/agent-development-life-cycle
- **Experience Manager**：「a sophisticated platform for auditing conversations that is accessible to technical and non-technical users alike」；CX 团队**每天**正式评估对话样本并标注（决策是否正确？语言语调和品牌是否对？是否缺知识？若错应该怎么做？）。
- **标注 → regression test**：「Every annotated conversation in the Experience Manager can become a conversation test — a snapshot of the conversation that is simulated against **mock APIs** to reliably reproduce the problem.」
- **平台升级时的兜底**：原文「When Sierra upgrades the underlying Agent OS platform, we not only run internal evaluations… but also **run the regression test suite for every one of our live customers**」。
- **在线监控（runtime）**：**Threat Detection**（跨平台看滥用/回归/新攻击模式）+ **Agent Monitors**（单 Agent 维度抓可能漏过 runtime checks 的行为）。来源：https://sierra.ai/blog/defense-in-depth-in-the-age-of-agents（已打开）。
- **红队**：原文「Sierra works with trusted third parties to run regular adversarial assessments and red-team evaluations — **millions of attempts in aggregate** — with the findings feeding back into the platform.」同上页。

### (e) Agent Checks（构建期 linter）

一手来源（已打开）：https://sierra.ai/blog/release-governance-guardrails-for-agents-at-scale
具体示例（原文）：prompt 引用了但从未提供的 tool；给 agent 的指令互相冲突；lookup tool 干了 action tool 的活；在屏幕上好用但电话上崩掉的回复；**认证不足的敏感数据查询**。按严重度排序，多数附 Ghostwriter 建议修复、可原地应用。

## 1.6 关键设计决策（Sierra）

1. **「目标 + 护栏」而非「流程图」，并以 context block + condition 作为唯一组织范式。**
   - 依据（已打开）：https://sierra.ai/blog/context-engineering-the-key-to-great-agents。原文明确把 Workflow 降格为「just another piece of context made available when conditions are met, rather than the organizing paradigm for the entire system」。
   - 取舍：放弃流程图的确定性，换来新模型发布时的「免费」能力提升——原文「When you hardcode logic, you constrain the model… With context engineering, the agent can reason more freely. As new, more capable models are released, your agent inherits that improvement.」
2. **用 AI 守 AI：Supervisor models + deterministic guards 双层。** 明确承认每层各有失败模式：「Content grounds the agent in trusted knowledge, but the same retrieval pipeline can also pull in instructions someone planted inside it」；「Supervisors catch nuance that fixed rules can't, but as agents themselves they share some of the limitations they're built to detect」；「Deterministic guards enforce the absolutes… but only fire on what's been explicitly defined」。（已打开，defense-in-depth）
3. **Agent release = 不可变快照，含模型版本 + 知识快照。** 把 RAG 语料纳入 release 语义，使 rollback 成为一等公民。（已打开，agent-development-life-cycle）
4. **评估从「静态 benchmark」转向「生产对话每日回流生成的 golden set」+「开源 benchmark 谱系」。** 两条腿：对客户用 daily golden articles 测 recall/precision/nDCG（私有、随语料演化），对社区开源 τ-bench 系（τ-knowledge/τ-voice/hyper-τ）。（已打开，evaluating-and-improving-search + bench-advancing…）
5. **release governance 照搬软件工程：linter（Agent Checks）+ PR review（Reviewer role / merge approval）+ canary（split traffic releases）+ 不可变快照回滚。**（已打开，release-governance）
6. **自建 sandbox 编排层（Agency）而非采购，理由是「问题尚未定义清楚，采购会继承别人的假设」。** 并因此得以在一周内做出「Ephemeral Sessions」——唯一允许加载客户数据的会话类型，对数据来源、持久化、可见性都有限制。（已打开，agency-secure-scalable-sandboxes-for-agents）

---

# 2. Decagon

## 2.1 解决什么问题 + 目标用户

**一句话**：让**非技术的 CX 团队**用自然语言写 AOP（Agent Operating Procedures）来拥有 Agent 行为与迭代节奏，用 Duet 做持续自改进，用 Watchtower/Simulations 做质量与验证。
**一手依据（已打开）**：https://decagon.ai/product/overview
> 「AI agents are redefining customer experiences, but most vendors are running the legacy SaaS playbook: a complex SDK, a black-box implementation, and a vendor ticket for every change after. Decagon takes a fundamentally different approach, empowering every team to rapidly build, optimize, and scale AI agents.」

**目标用户**：CX/支持/运营 + 工程（工程保留 guardrails、integrations、versioning 的控制权）。
客户（https://decagon.ai/、https://decagon.ai/product/aop，已打开）：Deutsche Telekom、American Airlines、Square、Mercado Libre、Oura、Figma、Delta、Notion、Snap、Affirm、Chime、Hertz、Ticketmaster、Cash App、Duolingo、Gopuff、Dropbox、Hunter Douglas、Spring Health、Riot Games、Rituals、Soho House、Quince、Perplexity、Noom、Fanatics、Avis、1-800-Flowers、ID.me。

## 2.2 知识库分层（Decagon 自己的术语）

Decagon 的公开分层最清晰的是**「知识」与「行为」的二分**，以及知识侧的三件套。

**一手来源（已打开）**：https://decagon.ai/modules/knowledge-base（Decagon University 官方课程模块）
> 「When customers ask for information, the agent responds using **retrieval-augmented generation (RAG), pulling from your connected knowledge sources**. When customers need to take action, like updating an address or disputing a charge, that's when **Agent Operating Procedures (AOPs)** come into play.」

该模块列出三层（原文「Top takeaways」）：
1. **Knowledge base** —「acts as a hub of documentation for informational questions」
2. **Snippets** —「fill gaps with internal context」；原文细节「For content that isn't public-facing, you can add Snippets — short, internal knowledge pieces that supplement your knowledge base. Snippets are useful for new product launches, promotions, or known issues that don't belong in public documentation.」
3. **Suggestions** —「identifies knowledge gaps and auto-generates draft articles」；「Suggestions run monthly by default, but can also be triggered on demand or exported for deeper reporting.」

**其他层级术语（各自的已打开来源）**：
- **AOP (Agent Operating Procedures)**：https://decagon.ai/product/aop —「Combine the **flexibility of natural language with the reliability of code** to execute any workflow.」；https://decagon.ai/blog/from-sops-to-agent-operating-procedures —「natural language instructions that **compile into validated workflows** for AI agents」；「What makes Decagon's approach different is the **hybrid architecture**. CX teams can write agent logic using everyday language. Meanwhile, engineers maintain control over the underlying systems」。
- **Duet**：Agent 构建伙伴。https://decagon.ai/product/duet —「Automated AOP generation」「Proactive gap detection」「Comprehensive simulations」「Real-time tracing and explanations」「Human QA insights」「Actions to accelerate hillclimbing」；**Duet Autopilot**：「converts production signals into informed agent updates」+「Every update is staged for human review with a health report that gives complete traceability」。
- **Memory（user memory）**：https://decagon.ai/blog/user-memory —「Decagon's user memory is built on a **user-level abstraction** that builds across interactions. It captures conversational context **without creating a duplicative data layer**, complementing your existing systems of record.」
  - 两个子层（原文）：**Conversational memory**（「maintains unstructured conversation history, so interactions pick up where they left off」）与 **structured metadata**（「The platform can extract and store key user signals like **feature requests, sentiment, and stated preferences** as structured metadata attached to each customer's profile.」）
  - **User view**：「brings together every agent interaction into a single profile that includes conversation history, outreach attempts, and stored preferences」+「tags set by Watchtower flags, preset conditions like CSAT scores」。
  - https://decagon.ai/product/overview —「Memory: Maintain customer context across sessions and channels, complementing your systems of record with **data portability and control**.」
- **Agent engine**：https://decagon.ai/product/overview —「Every Decagon agent is built on a **proprietary engine**…」；下含 **Proprietary models**（「a network of frontier and specialized models」）、**Memory**、**Enterprise security**。
- **Watchtower**：always-on QA。https://decagon.ai/product/watchtower —「reviews every interaction against your custom criteria」；「**Natural language flagging criteria**」「Precision filters」「Flexible time windows」「Custom categorization」「**Flexible rubric scoring**（Define multiple fields in a single Watchtower, each with its own scoring options. Assign point values and track average scores over time）」。
- **Simulations（Testing & QA 内的产品名）**：https://decagon.ai/product/testing-qa —「**Simulations, Decagon's integrated testing suite**」；「Auto-generate tests」「**Checkpoints at every stage**」「**Evaluation model rationale**（Double-click to inspect the evaluation model's rationale — 即 judge 可解释）」「Always-current test coverage（automatic detection, updates, and removals of stale tests）」「Scheduled testing runs」「Automated alerting（Trigger alerts to tools like **PagerDuty**）」。
- 其余产品面（导航可见，未打开）：Experiments（Live A/B testing）、Insights & reporting（Voice of the customer）、Integrations、Channels/Voice/Chat/Email。

## 2.3 语料治理

| 子问题 | 公开事实 | 来源 |
|---|---|---|
| Ingestion 方法 | 「Decagon integrates with **help centers, internal docs, and ticketing systems**, automatically ingesting updates」；集成清单含 **Zendesk, Salesforce, Confluence, Slack, Shopify, Stripe** | https://decagon.ai/modules/knowledge-base（已打开）；https://decagon.ai/blog/knowledge-base-ai（已打开） |
| 多源统一 | 「**Multi-source ingestion** — Most support teams store knowledge across help centers, CRMs, chat logs, internal wikis, and document repositories. An AI knowledge base ingests content from all of these sources into a single searchable corpus.」 | https://decagon.ai/blog/knowledge-base-ai（已打开） |
| Refresh / 增量 | 「automatically ingesting updates so your AI always reflects the latest information」；Suggestions「**Automatic monthly updates**」+ 可 **on-demand 触发** | https://decagon.ai/modules/knowledge-base（已打开）；https://decagon.ai/product/suggestions（已打开） |
| Stale 检测 | 「**Stale content flagging** — The system monitors article performance using signals like **resolution rate, user feedback, and search-but-no-click patterns** to identify articles that are outdated, contradictory, or no longer helping customers reach a resolution.」 | https://decagon.ai/blog/knowledge-base-ai（已打开） |
| Gap 检测与排序 | 「Gap detection… highlights these topics with no corresponding article, **ranked by how often they appear**」；产品侧「**Ranked coverage impact** — Prioritize the gaps that affect the largest share of conversations」 | 同上；https://decagon.ai/product/suggestions（已打开） |
| AI 起草 + 人审 | 「**AI-assisted drafting**… generates draft content modeled on how top-performing human agents actually resolved those issues」；「**Human review before publication**. AI drafts the content, but a human approves it. This step is non-negotiable.」 | https://decagon.ai/blog/knowledge-base-ai（已打开） |
| 去重 | 「Audit existing content for accuracy. Remove **contradictory articles, consolidate duplicate entries**, and flag anything that hasn't been reviewed in six months or more.」——这是 Decagon 对**客户的建议步骤**，不是产品自动化去重能力的声明 | 同上（已打开） |
| 权威源 | **未找到公开资料**（无策展域名白名单/权威性分级声明）。间接：Decagon 有 live web search 能力（https://decagon.ai/blog/live-web-search-with-perplexity `[仅 sitemap，未打开]`） | — |
| 数据驻留 | **未找到公开资料**。公开 security 页只到「**Multi-region infrastructure**」这一粒度，无区域枚举 | https://decagon.ai/security（已打开） |

## 2.4 权限 / ACL：索引期 vs 查询期

**Decagon 公开资料中，检索期的 permission-aware retrieval / permission trimming 未找到公开资料。**

能确认的公开事实（https://decagon.ai/security，已打开）：

- **RBAC**：「Platform access is defined and enforced by role, ensuring every user automatically gets the right permissions for their job.」→ **平台访问**，非语料检索。
- **SSO**：Okta、Microsoft Entra。
- **Just-in-time API tokens**：「**Short-lived JWT tokens** give AI agents real-time access to customer systems, **scoped for minimal privilege and discarded after each session**.」→ 这是**对下游系统的访问控制**，是最接近「查询期权限」的公开机制。
- **Voice authentication**：语音渠道的终端用户身份验证。
- **Zero-data retention with LLMs**：「Decagon enforces zero-data retention with all AI providers like OpenAI and Anthropic, ensuring no conversation data is stored or used for training.」
- **PII redaction**：「Sensitive data is automatically detected and redacted using **Google's DLP service**, sanitizing logs and transcripts just after a conversation ends.」
- **Supervisor model**（与 Sierra 同名但独立实现）：「A built-in supervisor detects **hallucinations before responses are sent**, automatically revising responses that stray from factual grounding.」
- **Bad actor detection**：「A specialized detection system identifies adversarial prompts, manipulation attempts, or policy violations」。
- **Audit logs**：「Comprehensive, tamper-protected logs capture key events, from logins to unusual activity, **accessible only to senior engineering leadership**.」
- **多区域 + 模型冗余 + autoscaling/auto-failover + uptime SLA**。

知识库侧的权限在公开材料中只出现定性表述：「**Flexible publishing controls** — Keep your team in control of what goes live」（https://decagon.ai/product/suggestions，已打开）。Snippets 有「without exposing sensitive details」的意图描述（https://decagon.ai/modules/knowledge-base，已打开），但**未说明是索引期隔离还是查询期过滤**。

**未找到公开资料**：Decagon 是否做文档级 ACL、tenant isolation 在检索层如何实现、per-customer knowledge isolation 机制。

**[推断]** 从「complementing your existing systems of record, without creating a duplicative data layer」这一反复出现的措辞看，Decagon 的隔离重心更可能在 **连接器侧的凭据与 scope**（JIT JWT + minimal privilege），而非在自有索引里做文档级权限裁剪。这是推断，不构成事实。

## 2.5 评估

### (a) DuetBench（自改进评测）— 构造与指标

**一手来源（已打开）**：https://decagon.ai/blog/duetbench（2026-06-09，作者 Eric Lin, Agent Data Scientist）
- 定位：「**the first benchmark in the customer service domain designed to evaluate agent self-improvement**」。填补的三个 gap（原文）：**Static**（测单题解决而非迭代改进）、**Effort-blind**（只看最终分，不看自改进能力）、**Lacking real-world complexity**（简化环境，任务是 instruction-following 与 tool use，而非 debug 坏对话、修 agent logic、stress-test 改动）。
- **Harness 构造**：「runs on **simulated customer deployments**, complete with **Agent Operating Procedures (AOPs), tools, guardrails, and synthetic traffic**」。
- **人类基线**：对照「recently certified Decagon employees who had completed **Decagon Masters**, our agent-building certification program」——即拿内部认证过的人类 agent builder 做对照。
- **四类实验族**：diagnostic tasks、build tasks、simulation-generation tasks、end-to-end certification tasks。
- **关键数字（FACT）**：
  - 诊断：**90 个诊断任务、9 个 family**；Autopilot 全 check 通过率 **93%** vs 人类平均 **83%**；最难任务上 **87%**；抗 sycophancy **100%** 反驳成功；平均 **13 次 tool call**，最难调查用到 **64 次**。任务时长从 1 分钟到 1 小时，中位数 15 分钟。
  - 构建：**44 个 agent-building 任务**；Autopilot **45.5%** vs 人类（3 小时内）**23%**；人类在 medium/hard 任务上 3 小时内完成 **0 个**，Autopilot 完成 medium **57.1%** / hard **30.8%**，且都在 **60 分钟内、无人工监督**；build 任务「只有在所有关联 simulation 都通过时才算通过」；收敛轮数约 **2.2 rounds**。
  - 自评测试集：**20 个 AOP、520 次 run**；首轮生成 simulation 准确率 **58%**，自批判后 **88%**；在 **70%** 的 benchmark 场景中发现真实 bug。
  - 端到端：达到 Decagon 认证人类的 **90% 通过线**（人类新手做其中一节需 6–8 小时）。
- **在线信号（FACT）**：「In the past week, **Duet created 81% of test simulations and made 54% of agent edits**」；beta 期「teams accepted **93%** of the proposed workspaces after review」。
- 后续：**DuetBench-2: Measuring agent self-improvement in production**（2026-09-09）— https://decagon.ai/blog/duetbench-2 `[仅 sitemap，未打开]`

### (b) 平台内 Simulations 的评估构成（已打开，https://decagon.ai/product/testing-qa）

- 「**Checkpoints at every stage** — Confirm that your agent reliably triggers the right actions, uses correct data and tools, and follows business logic, **all in the exact moments intended**.」→ 这是**过程/轨迹级**评分点，不只终局。
- 「**Evaluation model rationale** — Double-click to inspect the evaluation model's rationale and see exactly why a test passed or failed.」→ judge 可解释。
- 「Validate agent behavior across channels before deploying to production **and with every subsequent update**」→ 离线 + 回归。
- 「**Always-current test coverage** — Ensure your testing is always up-to-date with automatic detection, updates, and removals of **stale tests**.」→ 测试集本身会腐坏，需要治理。
- 「Integrate with **CI/CD practices** to test every agent version」。
- 在线侧：**Watchtower** 对**每一次**会话按自定义 criteria 打分（rubric 可多字段、可打分并追踪平均分随时间变化）。
- **Human QA insights**（Duet）：「Incorporate human QA feedback into a continuous improvement loop」。（https://decagon.ai/product/duet，已打开）

### (c) 其他已确认的 eval 相关页面（未打开）

- https://decagon.ai/blog/evaluation-engine-ai-agents `[仅 sitemap，未打开]`
- https://decagon.ai/blog/designing-layered-guardrails-for-reliable-ai-agents `[仅 sitemap，未打开]`
- https://decagon.ai/blog/autopilot-in-production `[仅 sitemap，未打开]`（标题为 "Autopilot in production: Governance of self-improving agents"）
- Glossary 条目：`what-is-llm-as-a-judge`、`what-is-trajectory-evaluation`、`what-is-verified-resolution-rate`、`what-is-human-override-rate`、`what-is-recontact-rate`、`what-is-silent-agent-drift`、`what-is-tool-call-guardrails`、`what-is-voice-agent-simulation` 等 **约 150+ 条**术语页 `[仅 sitemap，未打开]`

## 2.6 关键设计决策（Decagon）

1. **AOP = 自然语言「编译」成受验证的工作流，坚持「不用 SDK、不用专业服务」。**
   - 依据（已打开）：https://decagon.ai/product/aop —「Instead of complex SDKs or costly professional services, you can define agent behavior in natural language, the same way you train human agents with SOPs.」
   - 与 Sierra 的分歧点（FACT，双方原话）：Sierra 说「Agents should be technology everyone can use — not just engineers」但仍提供 SDK（https://sierra.ai/blog/agent-os-2-0，已打开）；Decagon 把「复杂 SDK」直接列为旧范式缺点。
   - 混合架构：CX 写自然语言逻辑，工程管 guardrails/integrations/versioning。「Technical teams can version with **Git-based tracking** and retain full ownership of code.」（https://decagon.ai/product/aop，已打开）
2. **人类审核作为自改进 Agent 的强制闸门。** Autopilot 生成更新 → 「**staged for human review with a health report that gives complete traceability**」。这是把「self-improving」的安全边界明确放在人审上。（已打开，product/duet）
3. **知识缺口闭环产品化（Suggestions），且默认月更。** gap 按对话影响排序 + 从**顶尖人工客服的真实解决过程**生成草稿 + 人工批准才发布。（已打开，product/suggestions + blog/knowledge-base-ai）
4. **User memory 刻意不做「第二个数据层」。** 原文：「captures conversational context **without creating a duplicative data layer**, complementing your existing systems of record. With **full API accessibility, opt-in storage, and expiration controls**」；「you can specify **memory calls directly within each Agent Operating Procedure (AOP)**」——即记忆的**读写时机由 AOP 显式控制**，而不是全局自动注入。（已打开，blog/user-memory）
5. **把「谁来做 agent 建设」本身作为评测对象。** DuetBench 不测 agent 会不会解题，而测 agent 能不能**自己把 agent 改好**，并用内部人类认证（Decagon Masters）做基线。（已打开，blog/duetbench）

---

# 3. Harvey（legal AI）

> 说明：Harvey 是法律垂直而非客服垂直；但它的知识架构（Vault / Knowledge / Firm Knowledge / Memory）、权限模型（ethical walls）与 BigLaw Bench 的构造方法，对「垂直知识型 Agent」这一课题的参考价值在三家中最高，尤其是**权限与语料的耦合方式**。

## 3.1 解决什么问题 + 目标用户

**一句话**：让律所与企业法务在**伦理墙（ethical walls）约束下**，把公共权威法律语料、外部数据库与自有机构知识统一成可检索、可引用、可审计、可协作的工作层。
**一手依据（已打开）**：
- https://www.harvey.ai/ —「2,400+ Legal Organizations Build on Harvey」；https://www.harvey.ai/platform —「More than **200,000 lawyers** around the world use Harvey」
- https://www.harvey.ai/platform/agents —「Delegate the Work. Own the Judgment.」「Harvey handles the work end to end and returns cited, review-ready output.」
- https://www.harvey.ai/blog/agents-and-ethical-walls —「**Why information barriers are the most important unsolved problem in legal AI.**」（这是 Harvey 自己给这个行业下的判断）

**目标用户**：律所（Law Firms / Mid-Sized Firms）、企业法务（In-House）、交易/诉讼/创新团队。客户含 A&O Shearman、Latham & Watkins、Norton Rose Fulbright、O'Melveny、Ashurst、CMS、Foley Hoag、Cuatrecasas、Deutsche Telekom、Bayer、KKR、Bridgewater、Carvana、HubSpot、GSK Stockmann、Schoenherr、Repsol、dentsu 等（https://www.harvey.ai/ 与 sitemap 客户页，已打开 sitemap）。

## 3.2 知识架构分层（Harvey 自己的术语）

**平台层（导航可见，https://www.harvey.ai/platform，已打开）**：
Overview / **Agents** / **Vault** / **Knowledge** / **Spaces** / Command Center / Contract Intelligence / Harvey Mobile / Ecosystem / **Memory**

**Harvey 自己给出的一张「知识四件套」清单**（这是本次调研中最直接的分层证据）：
> https://www.harvey.ai/blog/biglaw-bench-retrieval （已打开）
> 「These leading techniques are used throughout Harvey's products across **Assistant, Knowledge Sources, Vault, and Workflows** when analyzing everything from complex documents to large databases.」

另一处并列（https://www.harvey.ai/platform/vault，已打开）：
> 「**Cross-platform connection** — Leverage vaults across Harvey's platform, including **Assistant, Workflows, Mobile, and Harvey's Word and Outlook Add-Ins**.」

逐层说明（各自的已打开来源）：

| 术语 | Harvey 的定义原文 | 来源 |
|---|---|---|
| **Vault** | 「Securely store and organize up to **100,000 documents** including files, email correspondence, and queries in vaults that are accessible across Harvey's platform.」；含 **Review tables**（「Extract and compare key data points from thousands of documents at once in a structured, tabular format」）、**Deep analysis over vaults** | https://www.harvey.ai/platform/vault |
| **Knowledge (Sources)** | 「Ground Answers in Trusted Data — Connect every query to legal databases, curated public sources, and the institutional knowledge only your firm has.」；三类来源：**Powerful Legal Databases**（Ask LexisNexis、Gyldendal Rettsdata、FromCounsel、SCC Online、Wolters Kluwer、Otto Schmidt、Lefebvre、Tirant lo Blanch）、**Web**、**EDGAR**、**Global Coverage**、**Vault Knowledge Bases** | https://www.harvey.ai/platform/knowledge |
| **Firm Knowledge** | 「connect company resources, embed content from specific practice areas, and integrate proprietary workflows all within the platform itself」；三种接入方式：**native integrations**、**Harvey's APIs**、**MCP**（原文「External tools will also be accessible through MCP later this year」） | https://www.harvey.ai/blog/firm-knowledge-in-harvey |
| **Spaces** | 「A governed environment where every collaborator — firm, client, or internal team — works from the same context, with the same tools, on the same matter.」；含 **Shared Vaults and Artifacts**、**Shared Workflows**、**Playbooks**、**Guest accounts**、**Space Analytics** | https://www.harvey.ai/platform/spaces |
| **Memory** | 「Your preferences carried across Harvey so every response comes back consistent with how you work.」；示例偏好原文：「Maya's GC prefers **numbered lists**.」「**Prioritize EDGAR as the primary source** over web or other sources.」 | https://www.harvey.ai/platform/memory |
| **Agents** | 「Purpose built agents execute complex legal work end to end.」；含 **Agent Builder**、**Connectors**、**Parallel Execution**、**Scheduled Agents**、**Nudges**、**Auditability**（「Every claim is backed by a citation and every step is logged」） | https://www.harvey.ai/platform/agents |
| **Workflows / Playbooks** | Workflows 出现在分层清单与跨平台清单中；Playbooks：「Embed your methodology into reusable Playbooks that deliver consistent, high-quality outputs — offering a new means for delivering value while preserving proprietary know-how」 | 同 Vault / Spaces 页 |
| **Command Center / Contract Intelligence / Ecosystem / Mobile** | 分别为「Analytics, benchmarking, and agentic insights to lead their organization's AI transformation」「Surface insights, strengthen negotiations, and accelerate reviews」「Access Harvey where you already work and ground every answer in sources you trust」 | https://www.harvey.ai/platform |

## 3.3 语料治理

这是三家中**公开细节最多**的一块。

### (a) 自有语料的 Ingestion：一篇专门工程博客

**一手来源（已打开）**：https://www.harvey.ai/blog/building-new-file-ingestion-system-to-scale-firm-knowledge（2026-02-11，作者 Reggie Cai）

- **动机（原文）**：「Large firms often have **millions of documents** in their DMS, whether it be iManage, SharePoint, Google Drive, or another platform.」旧同步方案的问题：「our synchronous file ingestion couldn't process extremely large uploads quickly」+「users also had to **manually select large sets of individual files (not folders)**」+「after files were uploaded to Harvey, they eventually became **stale**」。
- **两个新特性**：
  - **Folder uploads**：「Select any folder from a DMS and import the **entire hierarchy** into Harvey — including nested folders, their associated files, and **all relevant metadata**.」目标「one click import of hundreds of thousands of files」。
  - **One-way sync**：「Connect a folder or client matter for **continuous synchronization**. When files or folders change in the DMS, Harvey automatically detects and syncs the updates.」
- **编排**：Temporal。理由原文：「file ingestion at scale is inherently complex and unpredictable — traffic is bursty, external services rate limit, and requests fail transiently.」能力：branching / fan-in-fan-out、横向扩展 worker、**每步 checkpoint**（「If a workflow fails midway through processing 100,000 files, it resumes from exactly where it left off」）、可配置 retry + backoff。
- **5 步流水线（原文标题）**：Step 1 Folder selection → Step 2 **Crawl and build manifest** → Step 3 **Diffing** → Step 4 **Apply changes** → Step 5 **Trigger downstream processing**（「**chunking, embedding, and OCR**」）。
- **增量 / Diff 算法（原文细节）**：
  - 「**Mapping external IDs to internal IDs**. Each file and folder in Harvey stores the external ID from the source system, enabling us to track identity **across renames and moves**.」
  - 「**Detecting changes**. For each resource in the manifest, Harvey determines if it needs to be **created, renamed, re-downloaded, or moved**. Resources no longer present are **deleted**.」
  - 「**Ordering operations carefully**… Folders must be created before any of their children… deletions should occur after any children have been moved.」
  - **变更检测**：「we use **hash-based comparison** when available, falling back to **timestamp comparison** if necessary. This ensures we only re-sync files that have actually changed.」部分集成支持 **delta capture after a given time**。
- **去重（FACT）**：以 hash/时间戳判定「内容是否真的变了」→ 避免重复 re-sync。**这是变更级别的去重，不是语义近似去重。** 文档级重复内容消解**未找到公开资料**。
- **限流（原文）**：「Each integration partner enforces rate limits differently — by request count, payload size, or both; scoped **per-user, per-organization, or both**; and sometimes changing dynamically based on tier or infrastructure load.」→ 自建 Redis rate limiter，避免 Vault 的批量导入打爆 Assistant 实时上传的配额。
- **性能（原文）**：批量写库、**PgBouncer** 连接池、并行下载、**用 blob storage 存中间状态而非塞进 Temporal event history**、按 CPU/IO 分 task queue、**处理完成后立即删除 blob 临时数据**（隐私要求）。
- **规模声明**：「designed to support ingestion of **hundreds of thousands of files**」。
- **未来方向（原文）**：「Beyond files: The same ingestion infrastructure extends to other resources… **client matter metadata, ethical walls, emails, billing entries, and more**. Anything that can be crawled and indexed can flow into Harvey.」以及「**Agentic search across DMS**… real-time AI agents that search and retrieve documents directly from a customer's DMS **without requiring pre-ingestion**」——即「索引期」与「查询期」两条路并存。

### (b) 公共权威语料的 Ingestion：The Data Factory

**一手来源（已打开）**：https://www.harvey.ai/blog/using-agents-to-scale-harveys-knowledge-sources（2026-02-02，作者 Samarth Goel & Chris Bello）

- **规模跃迁（FACT）**：「Since August 2025, this pipeline has helped Harvey scale its knowledge source coverage from just **six jurisdictions to over 60**, and from **20 unique legal data sources to more than 400**.」
- **三层架构（原文）**：**Intake engine**（发现与合规）→ **Evaluation pipeline**（能否真的用来解题）→ **Configuration layer**（声明式配置）。
- **Configuration layer 是核心抽象**：原文「Each jurisdiction is defined by a single **config object**: the domains to search, the filter hierarchy for narrowing queries, **the permissions required for access**, and optional agent instructions.」
- **架构决策（FACT，很重要）**：原文明确**拒绝 per-jurisdiction 子 agent**：「A natural design would assign each jurisdiction its own specialized agent, but **subagent handoffs can lose crucial conversation history**, which can create friction during multi-turn legal research. Instead, we treat domain-specific sources as **parameterized tools**.」→「The result is a **single reasoning system** that can fluidly move between Austrian court decisions and Brazilian statutes in the same conversation.」
- **权威源原则（原文，直接回答「authoritative source」子问题）**：「Why not just use open web search? Our customers care deeply about **source authority**… Open web search might surface the right answer, but it can't guarantee the source meets the **evidentiary standards** attorneys require. Our **curated domain lists** ensure every result comes from a **vetted government portal or authoritative legal database**.」
- **合规闸门（FACT）**：**Legal Review Agent** 预分析 terms of use、robots.txt、copyright assertions、local database rights，抽取关键条款并标注限制，输出结构化摘要给 Legal 团队；**「Attorneys still review every source before it goes live」**；吞吐从 1–2 提升到 2–4 sources/小时。
- **自动发现**：**Sourcing Agent** 映射法域法律基础设施、识别可信仓库、与现有工具交叉比对找缺口。

### (c) 公共来源清单（已打开的 100 源清单）

https://www.harvey.ai/blog/100-knowledge-sources-available-in-harvey（2025-09-08，已打开）
- 「Harvey has now reached **100 integrated national legal and regulatory data sources** globally」，覆盖六大洲 + 超国家源（EU law、UN Security Council resolutions）。
- 以 **Regional Bundles** 组织：「Customers can select the regions they need and gain access to all Knowledge Sources in those bundles.」
- 分地区逐国列出具体源，例如：US = EDGAR, US Code, LexisNexis®, Delaware General Corporation Law；EU = EU Law, EUR-Lex, Curia (CJEU), European Banking Authority；UK = Legislation.gov.uk, HMRC, Companies House, CMA, Irish Statute Book, Jersey Law, BVI；Germany = Gesetze-im-Internet；France = Légifrance；India = Indian Kanoon；Japan = Courts.go.jp, e-Gov。
- 该页同时给出组织单位 **Knowledge Sources** 与本页的 **Regional Bundles** 两个术语。

### (d) 刷新与更新节奏（FACT）

- 自有文件：**one-way sync**，按计划同步（原文「reflected in Harvey on the next scheduled sync」）。来源：building-new-file-ingestion-system（已打开）
- 公共源：Data Factory 是持续扩张的 pipeline（6→60+ 法域）；具体刷新频率**未找到公开资料**。
- 法规版本语义（EUR-Lex 等）**未找到公开资料**。

### (e) 数据驻留（FACT）

**一手来源（已打开）**：https://www.harvey.ai/security
> 「**Data Sovereignty and Control** — With Harvey, you retain full control over your data. Decide which data to upload, set retention policies, delete data anytime, and **keep everything in-region — EU or Switzerland, US, or Australia**.」
> 「Harvey hosts its cloud environment in **Microsoft Azure**. For customers with requirements or preferences for data localization we offer processing in the **EU and Switzerland or Australia**. This applies to Harvey subprocessors as well.」

**租户隔离（原文）**：
> 「Customer data for each customer is **logically separated to prevent any commingling of data between customers** and Harvey implements strict access controls following the **principle of least privilege**.」
> 「Harvey **encrypts all data at rest and in transit**, uses strong access controls, and, **by default, never trains on customer data**.」
> 「Harvey requires **Zero Data Retention (ZDR) by model providers**.」
> 「Can my firm use our client data for model training? **Yes, but only if you explicitly request it.** In that case, a bespoke model is created exclusively for you, and your data is never used to train models used by other customers.」

## 3.4 权限 / ACL：这是 Harvey 最强、最值得抄的一块

Harvey 在公开材料中**明确回答了 index-time vs query-time 的问题**，且给出了一个罕见的架构立场：**不自建权限系统，而是同步外部 system of record**。

### (a) Ethical walls 的架构立场（关键 FACT）

**一手来源（已打开）**：https://www.harvey.ai/blog/agents-and-ethical-walls（2026-03-12，作者 Gabe Pereyra）
**这是本次调研中关于「Agent 时代权限」最具体的一篇一手论述。**要点：

1. **为什么 Agent 改变了问题（原文三点）**：
   - 「**Agents access data, not the lawyer**」——Agent 自主决定读哪些文档，「If the agent accesses a document behind an ethical wall, **the breach has already occurred — even if the lawyer never sees the result**.」
   - 「**Agents maintain context across time**」——跨会话记忆带来跨 Matter 的污染风险，「The answer under current ethics rules is **unambiguously yes**」（即构成污染）。
   - 「**Agents operate at a scale humans can't monitor**」——「An agent can process hundreds of documents in minutes.」
2. **四条设计要求（原文标题）**：
   - **Fail closed, not open**：「If an agent can't confirm that a document falls within the matter's boundary, it **must skip that document and flag the uncertainty**.」
   - **Matter-centric product isolation**：「making the **client matter the atomic unit of the product**. Every agent, every document, every conversation, every piece of work product must be scoped to a specific matter… not as a metadata tag, but as a **hard security boundary**.」
   - **Integration with conflicts infrastructure**：「When **Intapp** says a wall exists between Matter A and Matter B, the AI platform **enforces that wall at the retrieval layer, the context layer, and the output layer**. When **iManage** restricts access to a workspace, the AI agent **inherits those same restrictions**.」并明确反对自建：「An AI platform that tries to build its own parallel conflicts system is **making a mistake**.」
   - **Audit trails that satisfy courts**：「Every document retrieval, every context window, every agent session needs to be logged at a level of detail sufficient to prove — after the fact — that no walled information was accessed.」
3. **对采购方的建议问题（原文，可作为评测清单）**：「When an agent runs a task, **what data can it access? Is access scoped to a single matter or to the user's full permissions? How is wall enforcement implemented — at the application layer, the data layer, or both?**」

### (b) 产品化的权限声明

- **Security 页（已打开）**：「**Ethical Walls Enforcement** — Harvey **syncs and enforces your firm's existing ethical wall policies**, blocking restricted users from accessing or sharing walled content across Harvey. **Harvey never creates, modifies, or deletes walls**, ensuring that your **walls provider remains the system of record**.」
- **Spaces 页（已打开）**：「**Granular access controls** — Permissions are set at the **resource level, not just the Space level**. Nothing reaches a collaborator without **explicit admin approval from both sides**.」+「**Ethical wall enforcement** — **Intapp integration** enforces ethical walls automatically across matters」+「**Full audit trails** — Every access grant, resource share, query, and approval action is logged in real time.」
- **Firm Knowledge（已打开）**：「**permission-aware architecture**」「**searches are permission-aware and connected to the right artifacts**」「This helps prevent leakage」；「**Ethical walls align with your firm's compliance framework** to help prevent client information from leaking across matters」。
- **Vault（已打开）**：「**Permissions & governance controls** — Control who can access, edit, and view vaults and knowledge bases.」「**Sharing** — Collaborate in vaults and review tables with colleagues and external partners – with full control over who can access, view, and edit.」
- **Agentic Vault Search（已打开，2026-09-08）**：这是**最直接回答「检索期是否做权限裁剪」的一句**：
  > 「**The agent has the same permissions as the user**: ethical walls and existing Vault permissions (view, edit, full access) apply exactly as they do today, and **every file the agent touches is logged in the workspace's audit trail**.」
  → **FACT：Harvey 在查询期执行与用户等价的权限裁剪，并逐文件审计。**
- **Command Center / Agents 页（已打开）**：「SAML SSO、audit logs、IP allow-listing、data lifecycle management」；SOC2 II / CCPA / ISO 27001 / GDPR / ISO 27701 / ISO 42001。
- **Security 页 FAQ（已打开）**：「How do you respect access controls for client data? — Harvey enforces strict **role-based access controls and logical workspace separation**… Customers can determine **what data to upload to Harvey, how long it is retained, and whether that data can be shared with others** within the company.」

### (c) 一个刻意的不对称（FACT）

**Agentic Vault Organization**（2026-09-08，已打开）：
> 「The Harvey Agent can **move, rename, and tag** files, but importantly, it **never edits the content inside them** and **never runs a change without a person confirming it first**.」
> 「Harvey **proposes a plan and shows exactly what it intends to change before touching anything**, so you confirm or adjust before it executes. You can also **undo the most recent set of changes**.」

→ 写操作（组织/重命名）与人审强绑定；读操作（检索）则继承用户权限并全量审计。这是一个明确的能力边界设计。

**未找到公开资料**：Harvey 是否在**索引期**做 per-user 权限打标（例如把 iManage ACL 落到 chunk 元数据上）。公开材料只说到「permission-aware」与「查询期继承用户权限 / 多层的 retrieval-context-output layer」。「检索层/上下文层/输出层」这三层的措辞暗示不止查询期一处，但机制未公开。

## 3.5 评估：BigLaw Bench 的构造（重点）

### (a) 原始 BigLaw Bench 的构造方法（FACT）

**一手来源（已打开）**：https://www.harvey.ai/blog/introducing-biglaw-bench（2024-08-29）

- **定位**：「a **public-facing version of our internal dataset** for evaluating LLMs and model systems on complex legal tasks」。
- **任务来源（构造方法的关键创新）**：**以「time entry（计时条目）」为任务分类的骨架**。原文：
  > 「we draw on a familiar feature of the legal profession: the **time entry**… Because **all work is billed**, building a comprehensive set of time entries closely reflects the set of legal tasks that make up real-world practice.」
  > 「By converting **time entries into model-based tasks (prompt / document pairs)**, we are able to identify and evaluate how models can contribute to real, high-value legal work.」
- **谁写的**：「conceptualized and designed by our **legal research team, composed of attorneys** with experience across a wide range of practice areas and BigLaw firms, and constructed using **publicly available documents** to enable transparent evaluation」。
- **任务分布（已打开的表格数据，节选）**：
  - Transactional：Corporate Strategy & Advising 28.3%、Drafting 24.5%、Legal Research 13.2%、Due Diligence 11.3%、Risk Assessment & Compliance 9.4%、Negotiation Strategy 5.7%、Deal Management 3.8%、Transaction Structuring 3.8%
  - Litigation：Analysis of Litigation Filings 25.5%、Case Management 23.4%、Drafting 14.9%、Case Law Research 8.5%、Transcript Analysis 8.5%、Document Review & Analysis 6.4%、Regulatory & Advising 6.4%、Trial Preparations & Oral Argument 6.4%
- **评分方法：两个独立分数（FACT）**：
  - **Answer score**：「Harvey's research team developed **bespoke rubrics** to evaluate each task. These rubrics establish objective criteria… They also **penalize common LLM failure modes such as incorrect tone or length, irrelevant material, toxicity, and hallucinations**.」
    计分规则（原文）：「each affirmative requirement was assigned a **positive score** based on its importance… Negative criteria, such as hallucinations, were assigned **negative scores**… Answer score is computed by taking the combination of these positive and negative points and **dividing by the total number of positive points available** for a task.」
    定义原文：「Answer score represents: **What % of a lawyer-quality work product does the model complete for the user?**」
  - **Source score**：只对「rubric 要求必须有来源支撑的实质性观点」计分。例：「if a substantive point in the rubric was, 'The model's answer must include the termination fee is $10,000,000,' the sourcing point would be 'the model must provide a source for its statement that the termination fee is $10,000,000.'」
    定义原文：「Source score represents: **What % of correct statements does the model support with an accurate source?**」
    **重要观察（原文）**：「Though related, **source score and answer score are independent**. A model can make a number of correct assertions (high answer score) while failing to provide traceability… (low source score).」
- **结果（原文）**：「Harvey's proprietary models… producing **74% of a final, expert lawyer-quality work product**」；「Besides Harvey, only ChatGPT provided sources to documents for a meaningful number of tasks when sources were not explicitly requested」；且**强行要求引用会显著拉低表现**——「the foundation models would consistently **hallucinate sources**（either document text, page number, or both）leading to weak source scores and **far worse answer scores**」。
- **局限自述（原文）**：「it currently emphasizes tasks that today's models can or should be able to do. This list of tasks falls far short of the goal of providing a benchmark of all tasks…」

### (b) BLB 的四条扩展线（2026 年）

**一手来源（已打开）**：https://www.harvey.ai/blog/expanding-big-law-bench（2026-02-09）

- **基座模型分数演进（FACT）**：「base model scores going from **60% (GPT 4o | Claude 3.5 | Gemini 1.5) to 90% (GPT-5 | Claude 4.5 | Gemini 3)**」；「we will be releasing extended benchmarks that increase the number of BLB data points **more than fivefold**」。
- **三条扩展线（原文表格）**：**Global**（不同法域的表现，与各国本地专家合作，先做 UK / Australia / Spain）、**Practice Areas**（Capital Markets、M&A、Fund Formation、Litigation、Arbitration、IP；「depth and end-to-end task completion」）、**Legal Research**（「Model and agent search capabilities on complex research problems」）。
- **方法论自我修正（FACT，很重要）**：原文「we have found that the **most accurate measure of model capabilities is core BLB: their ability to solve tasks as graded by objective, expert-written criteria**」——即在试过 hallucination rate、sourcing、retrieval 之后，回归到 expert rubric 的核心分。
- **用 BLB 做「行为探测」而非只做「打分」**：
  - **概念混淆的 canary**：美国联邦证据法中「非传闻的不可采陈述」vs「属传闻但可采」两组，早期模型会混甚至互换；原文把它当作「a **canary** for collecting additional data on any model's internalization of legal rules」。
  - **Sycophancy 探测**：选「看似主观但专家对正确答案有共识」的题（如 Most Favored Nations 条款触发概率），把同一 prompt **改写成三种立场**（中立 / 作为 GP 想找漏洞 / 作为 MFN 持有人想获益），看模型是否因提问者立场而偏离原正确预测。
- **明确自述 BLB 不是万能**：「it is not yet a silver bullet… we wanted to focus where it had been most impactful — **providing insights about model behavior rather than answers about specific outcomes**」。

### (c) BLB: Retrieval（检索子基准的构造）

**一手来源（已打开）**：https://www.harvey.ai/blog/biglaw-bench-retrieval（2024-11-13，作者 Niko Grupen & Julio Pereyra）

- **两类数据集（原文）**：**research datasets**（case law、legislation、EUR-Lex、published law firm memoranda）与 **document collections**（contracts、emails）。
- **Query 与 ground truth 构造（FACT）**：「we used a mix of **human experts and AI systems** to generate a large number of salient queries… Then for each question, our **AI-assisted experts annotated relevant material** that would need to be retrieved in order to correctly respond to each question.」样本查询公开在 https://github.com/harveyai/biglaw-bench/tree/main/blb-retrieval `[仅页面引用，未打开]`
- **指标（FACT）**：「We measured performance as the **percentage of relevant content found** by the retrieval system for a given user query, graded against a **ground truth established in advance by our in-house legal research team**. In technical terms, this is equivalent to **recall at a fixed token threshold**.」
- **结果（FACT）**：「identifying up to **30% more relevant content** than alternative retrieval methods from OpenAI and other embedding model providers（**Voyage, Cohere**）across a diverse range of legal document types」。
- **为什么领域检索难（原文，三类文档的差异）**：Contracts——「hundreds of pages and potentially hundreds of thousands of tokens of text with **cross-references and defined terms which must be tracked**」；Discovery Emails——「short documents… **complex relationships (e.g., email threads) and rich metadata (sender, recipient, attachments)**」；Research Databases——「millions of documents… relationships like **recency cannot be captured by vanilla semantic search**」。
- **律师的真实相关性判据（原文）**：case law 看「not only relevant but also **recent and controlling in a jurisdiction**」；Merger Agreements 看「**industry, deal size**」。
- **Harvey 检索取胜的三个原因（原文列表）**：1. **Metadata**（「Adding metadata to contextualize passages of text」）；2. **Features**（「Capturing features like **recency** that are typically not accounted for in typical semantic search systems」）；3. **LLM-based retrieval**（页面在此处被截断，未取到完整第三点说明）。
- **公开发现（FACT）**：MA（Merger Agreements）与 SPA（Stock Purchase Agreements）在常规 RAG 下表现差异巨大，尽管律师认为两者相似——「These gaps confirm the value in thinking about **domain- and task-specific retrieval**」。

### (d) BLB: Research（agentic 研究基准）

**一手来源（已打开）**：https://www.harvey.ai/blog/introducing-big-law-bench-research（2026-03-11，作者 Laura Toulme）

- **数据合作方**：「Working with our data partner **Snorkel AI**… we identified a series of **US Case Law** research problems that leading models are currently unable to solve — **even when provided with search tools like web search**.」
- **首个要求模型端到端使用工具的 BLB**：「Models must **use tools to perform searches** in order to identify relevant research context and provide a **grounded, cited response**.」
- **「难但不冷僻」的构造原则（原文，方法论金句）**：
  > 「A good way to make benchmarks hard is to make them **esoteric**. This is unfortunately also a great way to make a benchmark **useless**… Accordingly, we needed to ensure that tasks were **difficult and realistic**.」
  > 「We did this **not by predicting what should be hard but by actually finding the frontier of model capabilities**.」
- **难度阈值（FACT）**：「we found that model answers become **unhelpful once the model completes less than 60% of the required task criteria**」；并区分「部分正确仍有用」（「slightly-off analysis with good citations to principal cases still gives users a research head start」）。
- **已公开的具体任务（已打开的表格，节选）**：Corporate「Assessing Earn-Out Manipulation Claims After Asset Sale」（Delaware 公司资产出售 + 多年 earn-out，买方整合决策是否违反 APA）；Securities Litigation「Evaluating Securities Fraud Claims Against EV Company for Prototype Misrepresentations」（氢燃料电池卡车公司 CEO 陈述与内部文件矛盾，评 material misrepresentation、scienter pleading、PSLRA safe harbor）；Privacy & Cybersecurity「Analyzing Defenses to Nationwide Class Action Arising from FinTech Data Breach」（65 万用户，承包商 API 凭据泄露，评 Article III standing、choice-of-law、Rule 12(b)(6)）。
- 覆盖的其他领域：IP、Commercial Litigation、Constitutional Law、Regulatory、Employment & Labor、Health Law & Life Sciences、Tax、Tort、Real Property、Media and Technology、Immigration、Family Law。

### (e) 人审 / 自动化 eval pipeline / 数据服务（三支柱）

**一手来源（已打开）**：https://www.harvey.ai/blog/scaling-ai-evaluation-through-expertise（2025-05-22）

- **三支柱（原文）**：**Expert-led reviews** + **Automated evaluation pipelines** + **Dedicated data services**。
- **Retrieval golden set 的两步法（原文）**：「First, we collaborate with domain experts to develop **retrieval datasets: curated "golden" query sets** designed to rigorously test how well our systems surface relevant documents.」→「For each query, these experts identify the most relevant supporting documents.」→「We then evaluate our retrieval systems — **both traditional and agent-based** — against these references using metrics like **precision, recall, and NDCG**」。
  - **原文声明这些指标与用户满意度强相关**：「These metrics have proven **highly predictive of real-world user satisfaction**.」
  - 还测「varying levels of **retrieval power**」与「**model context**」占用，以理解「tradeoffs between quality, speed, and cost」。
- **两种人类评估协议（原文）**：
  - **A/B preference tests**：「Experts see two anonymized answers side-by-side, with **model order randomized**, and choose the better one.」
  - **Likert-scale ratings**：「Experts rate each answer independently on a scale from **1（very bad）to 7（very good）**, assessing dimensions like **accuracy, helpfulness, and clarity**.」
  - 偏差控制原文：「randomized ordering, standardized prompts, and anonymized content — help **reduce labeling bias** and allow us to detect **statistically significant** improvements」。
  - 已公开案例数字：GPT-4.1 vs GPT-4o，「The mean rating improved by over **10% (from 5.10 to 5.63)**, and the median score rose **from 5 to 6**」。
- **自动化 eval 的产出结构（原文）**：「The evaluator uses this information to produce two results: a **grade** that reflects how well the model's output meets the expected quality or correctness standards, and a **confidence score** that indicates how reliable that grade is.」
- **Rubric 维度示例（原文）**：structure（「Is the response presented in a structured format such as a table with columns X, Y, Z?」）、style（「Does the response emphasize actionable advice?」）、substance（「Does the response state a certain fact?」），外加 hallucination / misconstrued information 检查。
- **三种用途（原文）**：**Routine Evaluations**（「a suite of lightweight **canary evaluations nightly** to validate the day's code changes before they go to production, catching regressions in **sourcing accuracy, answer quality, legal precision**」）、**Production Monitoring**（「monitor **anonymized** production data… without compromising client confidentiality」）、**Model Vetting**（「evaluate newly released foundation models」）。
- **Knowledge Source Identification 专项（FACT）**：为核验 LLM 生成的引证，构建专用 pipeline——**High-Volume Fuzzy Matching**（对百万级文档语料匹引证串，容忍不完整/拼写错误）+ **Metadata Weighting**（document name / date / parties / publication 加权）；流程 = 结构化 metadata 抽取 → 有可靠出版数据则查内部 DB 取候选，否则 embedding 检索 + 日期过滤 → **LLM 做二元文档匹配判定**；「yielded **over 95% accuracy** on our internal benchmark dataset **validated by attorneys**」。
- **评估数据服务（原文）**：「We established a service dedicated to evaluation data, **isolated from Harvey's primary application** to prevent unintentional data leakage or unauthorized dependencies… our **fine-grained role-based access control system enforces strict privacy policies at the row level**」。（该页正文在此处被截断，后续内容未取到 → 此子问题的完整细节 **未找到公开资料（页面截断）**）

### (f) 其他已确认存在但未打开的 eval 页面

- https://www.harvey.ai/blog/biglaw-bench-hallucinations `[仅 sitemap，未打开]`
- https://www.harvey.ai/blog/biglaw-bench-sources `[仅 sitemap，未打开]`
- https://www.harvey.ai/blog/biglaw-bench-workflows-spa-deal-points `[仅 sitemap，未打开]`
- https://www.harvey.ai/blog/introducing-big-law-bench-global `[仅 sitemap，未打开]`
- https://www.harvey.ai/blog/introducing-biglaw-bench-arena `[仅 sitemap，未打开]`
- https://www.harvey.ai/blog/introducing-harveys-legal-agent-benchmark `[仅 sitemap，未打开]`
- https://www.harvey.ai/blog/using-elo-scores-to-build-better-legal-ai `[仅 sitemap，未打开]`
- https://www.harvey.ai/blog/contract-intelligence-benchmark `[仅 sitemap，未打开]`
- https://www.harvey.ai/blog/legal-agent-benchmark-initial-results `[仅 sitemap，未打开]`
- https://www.harvey.ai/blog/legal-agent-bench-m-and-a-due-diligence `[仅 sitemap，未打开]`
- https://www.harvey.ai/blog/legal-agent-benchmark-in-house-contracting `[仅 sitemap，未打开]`
- https://www.harvey.ai/blog/a-framework-for-domain-specific-evaluations `[仅 sitemap，未打开]`
- https://www.harvey.ai/legal/evaluation-terms-of-service `[仅 sitemap，未打开]`
- https://www.harvey.ai/research `[仅 sitemap，未打开]`

## 3.6 关键设计决策（Harvey）

1. **Matter（客户事项）作为原子安全单元，并把「权限系统」外包给既有 system of record。**
   - 依据（已打开）：agents-and-ethical-walls 的「Matter-centric product isolation」+「Integration with conflicts infrastructure」，以及 security 页「Harvey **never creates, modifies, or deletes walls**, ensuring that your **walls provider remains the system of record**」。
   - 取舍：放弃自建 conflicts 系统的自主权，换取「不产生平行配置造成的缝隙」；代价是强依赖 Intapp / iManage。
2. **Fail closed 而非 fail open。**「If an agent can't confirm that a document falls within the matter's boundary, it must **skip that document and flag the uncertainty**. The work product might be less complete, but the ethical wall is intact.」（已打开）
3. **Agent 与用户权限严格等价，且逐文件审计。**「The agent has the same permissions as the user… every file the agent touches is logged in the workspace's **audit trail**.」——既不做权限放大，也不做权限缩小；把可解释性放到审计日志上。（已打开，agentic-vault-search）
4. **「权威源」用策展白名单而非开放网页。**「Our **curated domain lists** ensure every result comes from a vetted government portal or authoritative legal database.」并要求 **attorney 逐源人工过审**才能上线。（已打开，using-agents-to-scale）
5. **拒绝 per-jurisdiction 子 agent，改用「单一推理系统 + 参数化工具 + 声明式 config」。** 理由直指多轮法律研究的痛点：「subagent handoffs can lose crucial conversation history」；config 里同时编码「domains / filter hierarchy / **permissions required for access** / agent instructions」。（已打开）
6. **BLB 的任务骨架来自「time entry」而非「教材知识点」。** 因为「all work is billed」→ time entries 天然覆盖真实律师工作集合；并把评分拆成 **answer score** 与 **source score** 两个独立维度，避免了「答案对但不可溯源」被高分掩盖。（已打开，introducing-biglaw-bench）
7. **写操作与人审强绑定、读操作靠权限继承。** Agent 可移动/重命名/打 tag，但「never edits the content inside them」且「never runs a change without a person confirming it first」，并提供 undo。（已打开，agentic-vault-search）

---

# 4. 横向对比：六个子问题的三家对照表

| 子问题 | Sierra | Decagon | Harvey |
|---|---|---|---|
| **知识分层术语** | Journey / Tool / Rule-Policy / Workflow / **Knowledge** / Memory / Glossary / Response phrasing（8 类 context block）+ Context Engine + ADP | **Knowledge base / Snippets / Suggestions** + **AOP**（行为）+ **Duet**（构建）+ **Memory**（user memory） | **Vault / Knowledge Sources / Firm Knowledge / Spaces / Memory / Assistant / Workflows / Playbooks / Agents** |
| **Ingestion** | 40+ 集成、custom integration framework；Ghostwriter 摄入 SOP/transcript/白板照/录音；Expert Answers 从人工客服实录反哺知识 | 连接 help center / internal docs / ticketing（Zendesk、Salesforce、Confluence、Slack、Shopify、Stripe），自动摄入更新；Snippets 补内部内容 | DMS 连接器（iManage / SharePoint / Google Drive）folder upload + one-way sync（Temporal，百万文件级）；公共源由 The Data Factory 自动发现+合规审查 |
| **Refresh / 增量** | Dynamic updates 实时；release = 含知识快照的不可变版本 | 自动摄入更新；Suggestions 默认月更、可 on-demand | hash/时间戳增量 diff + 定时 sync；跨 rename/move 靠 external ID 跟踪 |
| **去重** | 未找到公开资料 | 仅「对客户的建议」层面（清理矛盾/合并重复）；无产品化声明 | hash 级变更去重（内容未变则不重传）；语义去重未找到公开资料 |
| **权威源** | 未找到公开资料 | 未找到公开资料 | **最强**：策展域名白名单（政府门户/权威法律库）+ attorney 逐源过审 |
| **数据驻留** | 合规清单公开，**区域枚举未找到公开资料**（Trust Center JS 渲染） | 仅「Multi-region infrastructure」，**区域枚举未找到公开资料** | **EU/瑞士、US、Australia** 明确；Azure 托管；子处理器同样适用 |
| **权限：索引期 vs 查询期** | 公开的是 runtime 四层（Content / Rules / **Supervisors** / **Deterministic guards**）+ 未认证则账户修改工具不暴露；租户隔离「never shared with other customers」 | RBAC（平台）+ **JIT 短时 JWT（最小权限、会话后作废）** + ZDR + PII redaction（Google DLP）；**检索期 ACL 未找到公开资料** | **最明确**：查询期「agent 与用户同权限」+ 逐文件审计；伦理墙在 retrieval / context / output 三层强制执行；matter 为硬边界；fail closed；权限源为 Intapp/iManage，Harvey 不自建 |
| **评估** | τ-bench / τ² / **τ³（τ-Knowledge 698 文档 21 类目 ~195K tokens；τ-Voice 真实劣化）** / **hyper-τ（评 agent 造 agent）**；平台内 Simulations（agent/user/**judge** 三段，从 SOP+知识库+coaching transcript+conversation flow 自动生成，可接 CI/CD）；**daily golden articles + recall/precision/nDCG**；Experience Manager 每日人审 + 标注转 regression test；红队数百万次尝试 | **DuetBench**（首个评 agent 自改进的客服 benchmark，四类实验族，对照 Decagon Masters 人类认证，90 诊断/44 构建/20 AOP×520 run）；平台内 Simulations（checkpoints、judge rationale 可查、stale test 自动清理、CI/CD、PagerDuty 告警）；**Watchtower** 全量在线 QA + rubric 打分 | **BigLaw Bench**：time-entry 派生任务 + 专家 bespoke rubric + answer score / source score 双分；**BLB: Retrieval**（专家标注 ground truth，recall@固定 token 阈值，比 OpenAI/Voyage/Cohere 多找 30%）；**BLB: Research**（Snorkel AI 合作，agentic search，60% 完成度为「无用」阈值）；Global / Practice Areas 扩展；人审 A/B + Likert；夜间 canary + 生产匿名监控 + 模型选型；Knowledge Source Identification 95% 引证核验准确率 |
| **人审位置** | CX 每日标注对话 → 转 regression test；merge approval 的 Reviewer role | Autopilot 更新 **必须 staged for human review**；知识草稿必须人工批准；Watchtower 人看 flag | Expert-led review 为三支柱之首；attorney 逐源过审；rubric 由律师写 |

---

# 5. 明确「未找到公开资料」的清单

1. **Sierra**
   - 索引期文档级 ACL / per-customer knowledge isolation 的实现机制
   - 语料 chunk 级去重策略
   - 数据驻留区域枚举（Trust Center 为 JS 渲染，公开页未列）
   - 权威源策展/分级规则
   - `docs.sierra.ai` 正文（需登录，本次仅取回登录墙）
2. **Decagon**
   - 检索期的 permission trimming / 文档级 ACL / tenant isolation 机制
   - 权威源分级或域名白名单
   - 数据驻留区域枚举
   - 索引期增量与去重的产品化说明（只有「自动摄入更新」与「对客户的清理建议」）
   - 「durable memory」这一确切措辞：Decagon 公开用词是 **user memory / memory**（见 product/overview 与 blog/user-memory），**未找到** "durable memory" 的官方表述
3. **Harvey**
   - 索引期是否把 DMS/Intapp ACL 落到 chunk 级元数据（公开只说 permission-aware + 三层强制 + 查询期继承）
   - 公共知识源的刷新频率与法规版本语义
   - 语义级去重
   - `scaling-ai-evaluation-through-expertise` 正文在「Data Management」段落后被截断，评估数据服务的完整设计未取到
   - `biglaw-bench-retrieval` 正文在「LLM-based retrieval」处被截断，第三点说明未取到

# 6. 本次打开过的 URL 全清单（可复核）

**Sierra（已打开）**
https://sierra.ai/ · https://docs.sierra.ai/（登录墙）· https://sierra.ai/product/agent-os（404）· https://sierra.ai/product/agent-sdk · https://sierra.ai/blog · https://sierra.ai/blog/agent-os-2-0 · https://sierra.ai/blog/agent-data-platform · https://sierra.ai/product/agent-studio · https://sierra.ai/product/context-engine · https://sierra.ai/blog/release-governance-guardrails-for-agents-at-scale · https://sierra.ai/blog/simulations-the-secret-behind-every-great-agent · https://sierra.ai/product/trust-and-reliability · https://sierra.ai/blog/agent-development-life-cycle · https://sierra.ai/blog/agent-studio-2-0 · https://sierra.ai/blog/context-engine · https://sierra.ai/blog/tau-bench-shaping-development-evaluation-agents · https://sierra.ai/sitemap.xml · https://sierra.ai/product/agent-data-platform（301 → /product/horizon）· https://sierra.ai/blog/bench-advancing-agent-benchmarking-to-knowledge-and-voice · https://sierra.ai/blog/evaluating-and-improving-search · https://sierra.ai/blog/context-engineering-the-key-to-great-agents · https://sierra.ai/blog/defense-in-depth-in-the-age-of-agents · https://sierra.ai/blog/agency-secure-scalable-sandboxes-for-agents · https://sierra.ai/blog/hyper-t-bench-evaluating-agents-that-build-agents · https://trust.sierra.ai/（JS 渲染，无正文）

**Decagon（已打开）**
https://decagon.ai/ · https://decagon.ai/sitemap.xml · https://decagon.ai/product/aop · https://decagon.ai/product/overview · https://decagon.ai/product/testing-qa · https://decagon.ai/product/watchtower · https://decagon.ai/product/suggestions · https://decagon.ai/product/duet · https://decagon.ai/security · https://decagon.ai/modules/knowledge-base · https://decagon.ai/blog/knowledge-base-ai · https://decagon.ai/blog/duetbench · https://decagon.ai/blog/user-memory · https://decagon.ai/blog/from-sops-to-agent-operating-procedures · https://decagon.ai/product-overview（404）· https://decagon.ai/resources/blog（截断无正文）· https://r.jina.ai/https://decagon.ai/product/aop（代理渲染，用于交叉验证 AOP 页）

**Harvey（已打开）**
https://www.harvey.ai/ · https://www.harvey.ai/sitemap.xml · https://www.harvey.ai/platform · https://www.harvey.ai/platform/agents · https://www.harvey.ai/platform/vault · https://www.harvey.ai/platform/knowledge · https://www.harvey.ai/platform/spaces · https://www.harvey.ai/platform/memory · https://www.harvey.ai/security · https://www.harvey.ai/blog/biglaw-bench（404）· https://www.harvey.ai/blog/introducing-biglaw-bench · https://www.harvey.ai/blog/expanding-big-law-bench · https://www.harvey.ai/blog/biglaw-bench-retrieval · https://www.harvey.ai/blog/introducing-big-law-bench-research · https://www.harvey.ai/blog/scaling-ai-evaluation-through-expertise · https://www.harvey.ai/blog/100-knowledge-sources-available-in-harvey · https://www.harvey.ai/blog/building-new-file-ingestion-system-to-scale-firm-knowledge · https://www.harvey.ai/blog/using-agents-to-scale-harveys-knowledge-sources · https://www.harvey.ai/blog/firm-knowledge-in-harvey · https://www.harvey.ai/blog/agents-and-ethical-walls · https://www.harvey.ai/blog/agentic-vault-search-and-organization
