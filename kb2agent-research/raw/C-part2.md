### C3. 客服与法律垂直 Agent 三强：Sierra · Decagon · Harvey

> 本节一手材料的完整版见 `raw/_sub-cx-vertical.md`（624 行，逐条列出打开过的 URL）。这里只保留对「规则库 + 案例库 + 误判申诉」三件套与权限设计最有迁移价值的部分。

#### C3.1 Sierra：把「知识」拆成 8 类 context block，其中「规则」是独立一类

**它解决什么**：Sierra 公开把自己的路线定义为客服 Agent 的第三代演进——"**Era 1: IVR / Era 2: Flow / Era 3: Context engineering**"，并明确批评流程图式做法："Journeys go beyond sequential workflows and lists of standard operating procedures, which **demo well but tend to degrade as they scale**"（<https://sierra.ai/blog/context-engineering-the-key-to-great-agents>【一手】）。

**知识库分层（官方 8 类 context block，原文摘录）**：

| Block | 官方 Purpose |
|---|---|
| **Journey** | "A **goal** the agent knows how to pursue: dispute a charge, file a claim, book a flight. Each journey has a trigger and an outcome." |
| **Tool** | "A way for the agent to interact with external systems: pull an itinerary, check coverage, process a refund." |
| **Rule / Policy** | "**Guardrails and business logic** expressed in natural language (e.g., 'Premium cardholders waive foreign transaction fees.')." |
| **Workflow** | "Step-by-step guidance for situations that require **a specific sequence**, like regulated intake or multi-step verification." |
| **Knowledge** | "Help center articles, product docs, FAQs, and **internal policies** the agent can access on demand." |
| **Memory** | "The customer's history: past conversations, preferences, and prior issues." |
| **Glossary** | "The terminology your business uses: product names, plan tiers, and internal jargon." |
| **Response phrasing** | "Brand voice and tone." |

**本报告认为这张表的价值在于**：它把「规则/策略」与「知识」**明确分成两类 context**。`[推断]` 这正是合规审核类产品与企业知识助手类产品最重要的结构差异——前者必须有独立的规则类，后者常把规则混在文档里。

**两个可直接借用的机制（官方原文）**：
- **Conditions 作为粘合剂**：每块 context 都要回答"**under what circumstances does this piece of information become relevant?**"。条件分两类——基于 **state**（工具返回特定数据、客户已认证）与基于 **observation**（客户提到某话题、表达取消意愿）。原文强调："Once the customer is authenticated, **account-specific tools and policies become available**."
- **Workflow 的降格**："a workflow becomes **just another piece of context** made available when conditions are met, **rather than the organizing paradigm** for the entire system."

**权限：runtime 四层（官方原文，<https://sierra.ai/blog/defense-in-depth-in-the-age-of-agents>【一手】）**：
1. **Content**——"the help center articles, product documentation, and policies that the agent retrieves and grounds its responses in"；
2. **Rules and policies**——自然语言指令；
3. **Supervisors**——"**Separate models that audit the conversation in real time, blocking, rewriting, or nudging the agent** when content or behavior crosses the line"；
4. **Deterministic guards**——"**Non-model checks that can't be talked out of doing their job** — like **preventing account-modification tools from even being available to the agent until the customer has been authenticated**."
   并给出时序量级："A single message can trigger **half a dozen** of these checks before any reply goes back."

`[推断]` 第 4 层是最值得守衡抄的一条：**权限的实现方式可以不是"过滤结果"，而是"工具根本不出现"**。未认证 → 工具不可见。这是一种"物理上做不到"而非"被要求不要做"的权限，可靠性等级不同。

**评测（三家最系统）**：开源 benchmark 谱系 **τ-bench → τ²-bench → τ³-Bench（τ-Knowledge + τ-Voice） → hyper-τ-bench**。其中 **τ-Knowledge** 的构造公开得很具体：域为 τ-Banking（fintech 客服），语料 **698 篇文档 / 21 个产品类目 / 约 195K tokens**，任务要求在语料中检索 + 推理 + 多步 tool call，且"often identifying tools referenced **only in documentation** rather than explicitly listed"（<https://sierra.ai/blog/bench-advancing-agent-benchmarking-to-knowledge-and-voice>【一手】）。另有平台内 **Simulations**（agent / user / **judge** 三段，从 SOP + 知识库 + coaching transcript + conversation flow 自动生成，可接 CI/CD）、**daily golden articles** 配合 recall/precision/nDCG。

**发布治理三件套**（<https://sierra.ai/blog/release-governance-guardrails-for-agents-at-scale>【一手】）：**Agent Checks**（"a **linter** for your agent"）、**merge approval workflows + Reviewer role**、**split traffic releases**（金丝雀）。`[推断]` "把 agent 配置当代码来 lint 与灰度"这个做法，与守衡"217 项契约检查 + 反向对照"的思路同源。

#### C3.2 Decagon：AOP + DuetBench（**评"自改进"本身**）

**知识层术语**：**Knowledge base / Snippets / Suggestions** + **AOP**（Agent Operating Procedures，行为层）+ **Duet**（构建侧）+ **Memory**（user memory）。

**最独特的评估设计：DuetBench**——据其公开材料，这是**首个评测"客服 Agent 自我改进能力"的 benchmark**，做法是四类实验族，对照 **Decagon Masters（人类认证）**，规模含 90 诊断 / 44 构建 / 20 AOP × 520 run。平台内 Simulations 支持 checkpoints、可查 judge rationale、**stale test 自动清理**、CI/CD 与告警；**Watchtower** 做全量在线 QA + rubric 打分。

**人审的硬约束（FACT）**：Autopilot 的更新**必须 staged for human review**；知识草稿必须人工批准。

`[推断]` **对守衡最有价值的一点**：Decagon 把"**Agent 能不能自己变好**"当成一个可评测的对象，而不是当成宣传语。如果守衡未来要让规则库自动从错题本里学习，那么"自改进是否真的改进了"就必须是可评测的——否则就是又一个"声明了没实现"。

#### C3.3 Harvey（法律）：**伦理墙（ethical walls）——本次调研中对「权限」最有价值的一手论述**

**为什么单列它**：Harvey 公开回答了"Agent 时代权限问题为什么变了"，并且给出了四条设计要求。**这与守衡的处境高度同构**——守衡的判定结论会影响外部（达人、运营、平台），一旦读到了不该读的语料，**判断本身就已经被污染了**。

**Agent 改变问题的三点（官方原文，<https://www.harvey.ai/blog/agents-and-ethical-walls>，2026-03-12【一手】）**：
1. **"Agents access data, not the lawyer"**："If the agent accesses a document behind an ethical wall, **the breach has already occurred — even if the lawyer never sees the result**."
2. **"Agents maintain context across time"**：跨会话记忆带来跨 Matter 的污染风险，而"under current ethics rules the answer is **unambiguously yes**"（即构成污染）。
3. **"Agents operate at a scale humans can't monitor"**："An agent can process **hundreds of documents in minutes**."

**四条设计要求（官方原文标题 + 关键句）**：
1. **Fail closed, not open**——"If an agent can't confirm that a document falls within the matter's boundary, it **must skip that document and flag the uncertainty**."
2. **Matter-centric product isolation**——"making the **client matter the atomic unit of the product**. Every agent, every document, every conversation, every piece of work product must be scoped to a specific matter… **not as a metadata tag, but as a hard security boundary**."
3. **Integration with conflicts infrastructure**——"When **Intapp** says a wall exists between Matter A and Matter B, the AI platform **enforces that wall at the retrieval layer, the context layer, and the output layer**."并明确反对自建："An AI platform that tries to build its **own parallel conflicts system is making a mistake**."
4. **Audit trails that satisfy courts**——"Every document retrieval, every context window, every agent session needs to be logged at a level of detail **sufficient to prove — after the fact — that no walled information was accessed**."

**官方给采购方的问题清单（可直接当守衡的自检表，原文）**：
> "When an agent runs a task, **what data can it access? Is access scoped to a single matter or to the user's full permissions? How is wall enforcement implemented — at the application layer, the data layer, or both?**"

**产品化描述（官方原文）**：
- **"Harvey syncs and enforces your firm's existing ethical wall policies**… **Harvey never creates, modifies, or deletes walls**, ensuring that your **walls provider remains the system of record**."
- **检索期裁剪的最明确一句**（Agentic Vault Search）："**The agent has the same permissions as the user**: ethical walls and existing Vault permissions (view, edit, full access) apply exactly as they do today, and **every file the agent touches is logged in the workspace's audit trail**."
- **写读不对称（刻意的设计）**："The Harvey Agent can **move, rename, and tag** files, but importantly, it **never edits the content inside them** and **never runs a change without a person confirming it first**."——"Harvey **proposes a plan and shows exactly what it intends to change before touching anything**… You can also **undo the most recent set of changes**."

**评测：BigLaw Bench 的构造（值得逐条抄的方法论）**（<https://www.harvey.ai/blog/introducing-biglaw-bench>【一手】）：
- **任务分类的骨架来自"time entry"**："we draw on a familiar feature of the legal profession: the **time entry**… Because **all work is billed**, building a comprehensive set of time entries closely reflects the set of legal tasks that make up real-world practice."然后"**converting time entries into model-based tasks (prompt / document pairs)**"。
  `[推断]` **这是本报告见到的最聪明的评测集构造法之一**：不去凭空设计任务，而是**从"计费工时"这种已经在业务里被完整记录的东西里派生**。守衡的等价物是"**每一次人工改判**"——它天然带业务上下文。
- **两个独立的分数**：**Answer score**（"What % of a **lawyer-quality work product** does the model complete?"）+ **Source score**（"What % of correct statements does the model **support with an accurate source**?"）。rubric 对幻觉等失败模式给**负分**。
- **关键观察**："Though related, **source score and answer score are independent**. A model can make a number of correct assertions (high answer score) while failing to provide traceability… (low source score)."
- **反向发现**：**强行要求引用会显著拉低表现**——"the foundation models would consistently **hallucinate sources**（either document text, page number, or both）leading to weak source scores and **far worse answer scores**"。
  `[推断]` **这条对守衡极其重要**：它说明"要求模型给出来源"如果只写在提示词里，会诱导模型**编造来源**。来源必须是**结构上可验证的**（指向真实存在的规则 ID / 条款 ID），而不是让模型自由书写引用。
- **BLB: Retrieval 的指标与构造**：以**专家预先标注的 ground truth** 为基准，指标是"**recall at a fixed token threshold**"（"the percentage of relevant content found… equivalent to **recall at a fixed token threshold**"）；并公开"identifying up to **30% more relevant content** than alternative retrieval methods from OpenAI and other embedding model providers（Voyage, Cohere）"。
- **为什么领域检索难（原文，三类文档差异）**：Contracts——"**cross-references and defined terms which must be tracked**"；Discovery Emails——"**complex relationships (e.g., email threads) and rich metadata**"；Research Databases——"relationships like **recency cannot be captured by vanilla semantic search**"。
- **律师的真实相关性判据（原文）**：case law 看"not only relevant but also **recent and controlling in a jurisdiction**"；Merger Agreements 看"**industry, deal size**"。→ **Harvey 检索取胜的三个原因**：**Metadata**、**Features（如 recency）**、**LLM-based retrieval**。
- **方法论自我修正（2026-02，很重要）**：在试过 hallucination rate、sourcing、retrieval 等指标后，官方回归到"**the most accurate measure of model capabilities is core BLB: their ability to solve tasks as graded by objective, expert-written criteria**"（<https://www.harvey.ai/blog/expanding-big-law-bench>【一手】）。

**对守衡的映射** `[推断]`：
| Harvey 的做法 | 守衡的对应物 |
|---|---|
| matter 作为**硬安全边界**（不是元数据标签） | 品线/店铺/平台作为判定边界——守衡已有 `product_lines` 机制但 `rules_scoped = 0`，即"声明了没生效" |
| **fail closed**：不确定就不读、并标记不确定 | 判定引擎遇到"无规则可命中"时，应当**显式标记为盲区**，而不是默认合规 |
| 权限源不自建，**同步 Intapp/iManage 为 system of record** | 飞书多维表格是权威源时，**权限判定应继承飞书表的可读范围**，不自建一套平行权限 |
| **answer score 与 source score 分开** | 判定准确率与**引用可追溯率**必须分开度量 |
| 引用必须可验证，否则模型会**编造来源** | 结论中的规则/条款引用必须是**结构化 ID 校验**，不靠模型自由书写 |
| 评测任务从 **time entry** 派生 | 评测任务从**人工改判记录**派生 |
| 写操作必须**先出计划、人确认、可撤销** | 规则库的任何自动修改都应"提议 + 人批 + 可回滚" |

---
