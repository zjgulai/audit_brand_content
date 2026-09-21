## 3. 案例族 B：「知识库 → Agent」的公开方法论

> 本节所有引用均来自**研究者本人打开并读到正文**的页面，证据强度为【一手】。

### B1. Anthropic《Building effective agents》（2024-12-19）

**出处**：<https://www.anthropic.com/engineering/building-effective-agents>【一手】

**核心论点（原文摘录）**：
- Anthropic 把所有变体统称 **agentic systems**，但在架构上划出一条关键界线：
  - **Workflows**："systems where LLMs and tools are orchestrated through **predefined code paths**."
  - **Agents**："systems where LLMs **dynamically direct their own processes and tool usage**, maintaining control over how they accomplish tasks."
- 选型原则："**find the simplest solution possible, and only increasing complexity when needed**."并明确："For many applications, however, **optimizing single LLM calls with retrieval and in-context examples is usually enough**."
- 复杂度代价："Agentic systems often trade **latency and cost** for better task performance."
- **基础构件是 augmented LLM**："The basic building block of agentic systems is an LLM enhanced with augmentations such as **retrieval, tools, and memory**."
- 五种 workflow 模式：**prompt chaining / routing / parallelization（sectioning + voting）/ orchestrator-workers / evaluator-optimizer**。
- 关于**并行化的两种用法**中，**voting** 的官方示例直接点名审核场景："Evaluating whether a given piece of content is **inappropriate**, with multiple prompts evaluating different aspects or **requiring different vote thresholds to balance false positives and negatives**."
- 关于**护栏**，官方给出的做法是并行分工而非单次调用兼任："Implementing guardrails where **one model instance processes user queries while another screens them** for inappropriate content or requests. This tends to perform better than having the same LLM call handle both."
- Agent 的定义性描述："They are typically just **LLMs using tools based on environmental feedback in a loop**."并要求"gain **ground truth** from the environment at each step"、"**pause for human feedback at checkpoints**"、设置"**stopping conditions**（如最大迭代数）"。
- 三条原则：**simplicity** / **transparency（显式展示规划步骤）** / 精心设计 **ACI（agent-computer interface）**，且"**invest just as much effort** [in ACI] as [in] human-computer interfaces"。
- 工具设计的具体手法：把模型**当作初级开发者写 docstring**；**Poka-yoke**（把参数改成难以犯错的形状）。实例：SWE-bench agent 因为相对路径出错，改成**强制绝对路径**后"the model used this method flawlessly"，且"we actually **spent more time optimizing our tools than the overall prompt**"。

**对守衡的可迁移结论** `[推断]`：
1. 「规则表 + 白名单 + 语境守卫」是典型的 **routing + parallelization** 架构，属于 Anthropic 定义的 **workflow**，**不是 agent**。这是好事：workflow 可预测、可回归测试。不要为了"叫 Agent"而把它改成自主循环。
2. **voting + 不同阈值**正是误报/漏报权衡的官方手法，可直接映射到守衡的"多规则投票 + 分级处置"。
3. **护栏独立进程**：语境守卫适合作为独立的一次模型调用，而不是塞进主判定的同一个 prompt。

---

### B2. Anthropic《Effective context engineering for AI agents》（2025-09-29）

**出处**：<https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents>【一手】

**核心论点（原文摘录）**：
- 定义："**Context engineering** refers to the set of strategies for **curating and maintaining the optimal set of tokens** (information) during LLM inference."
- 上下文是**有限资源且有边际递减**：引用 Chroma 的 **context rot** 研究——"as the number of tokens in the context window increases, the model's ability to **accurately recall** information from that context **decreases**"；并把它类比为人类的 **attention budget**。
- 目标函数："finding the **smallest possible set of high-signal tokens** that maximize the likelihood of some desired outcome."
- **系统提示的 "right altitude"**：一端是"hardcoding complex, brittle logic in their prompts"，另一端是"vague, high-level guidance that fails to give the LLM concrete signals"。
- **工具是上下文的一种**，且最常见的失败模式是"**bloated tool sets** that cover too much functionality or lead to ambiguous decision points about which tool to use"；判据是："**If a human engineer can't definitively say which tool should be used in a given situation, an AI agent can't be expected to do better.**"
- **few-shot 的正确用法**：反对把"a laundry list of edge cases"塞进 prompt，主张"curate a set of **diverse, canonical examples**"。原文："For an LLM, examples are the '**pictures**' worth a thousand words."
- **检索范式的迁移**：从 pre-inference 的 embedding 检索，转向 **"just in time" context**——agent 只持有**轻量标识符**（file paths、stored queries、web links），在运行时用工具把数据动态载入上下文。
- **元数据即信号**："the **metadata of these references** provides a mechanism to efficiently refine behavior"；并给出具体例子：`tests/test_utils.py` 与 `src/core_logic/test_utils.py` 同名不同义；"**Folder hierarchies, naming conventions, and timestamps** all provide important signals"。
- **progressive disclosure**："allows agents to incrementally discover relevant context through exploration."
- **混合策略是被官方推荐的**："the most effective agents might employ a **hybrid strategy**, retrieving some data up front for speed, and pursuing further autonomous exploration at its discretion."并**点名法律与金融**这类内容变化慢的领域更适合混合策略："The hybrid strategy might be better suited for contexts with **less dynamic content, such as legal or finance work**."
- **长任务的三种手法**：**compaction**（压缩历史，Claude Code 会保留"architectural decisions, unresolved bugs, and implementation details"并丢弃冗余工具输出，连续时保留"the five most recently accessed files"）、**structured note-taking / agentic memory**（如 `NOTES.md`）、**sub-agent architectures**（子 agent 可消耗数万 token，只回传 1,000–2,000 token 的蒸馏摘要）。官方调参建议：压缩提示词"**start by maximizing recall** ..., then iterate to improve precision"。
- 反模式提醒：压缩过猛会"result in the loss of subtle but critical context whose importance only becomes apparent later"。
- 结尾原则："**find the smallest set of high-signal tokens**"，以及"**do the simplest thing that works**"。

**对守衡的可迁移结论** `[推断]`：
1. 守衡属于官方点名的"**less dynamic content**"（合规规则/平台政策）场景，因此**混合策略**（规则表全量前置 + 长尾语境按需检索）优于纯 RAG。
2. **规则表的命名与目录结构本身是信号**：规则 ID 的编号体系、`enabled/effective_from` 之类的元数据，会实际影响模型与人的判断质量。这为"规则表要带版本与生效时间"提供了模型侧的动机，而不只是审计动机。
3. **证据包应当是"轻量标识符"而非全文**：判定结论里引用的规则/先例，应以 ID + 定位符落库，全文按需加载。

---

### B3. Anthropic Agent Skills：把知识编译成"可发现 / 可按需加载 / 可执行"的资产

**出处**：<https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills>（2025-10-16）【一手】；开放标准规范 <https://agentskills.io/>【一手】

**Skill 的物理形态（可执行的最小结构）**【一手，agentskills.io】：
```
my-skill/
├── SKILL.md          # 必需：metadata（name/description）+ 指令
├── scripts/          # 可选：可执行代码
├── references/       # 可选：文档
├── assets/           # 可选：模板与资源
```
**三级渐进披露（progressive disclosure）**【一手，agentskills.io 原文】：
1. **Discovery**："At startup, agents load **only the name and description** of each available skill, just enough to know when it might be relevant."
2. **Activation**："When a task matches a skill's description, the agent reads the **full `SKILL.md`** instructions into context."
3. **Execution**："The agent follows the instructions, optionally **executing bundled code or loading referenced files** as needed."

Anthropic 工程博客补充了关键机制细节：
- 启动时把每个 skill 的 `name` 与 `description` **预加载进 system prompt**；"This metadata is the **first level** of progressive disclosure"。
- 正文是**第二级**；skill 目录内的附加文件（如 PDF skill 的 `reference.md`、`forms.md`）是**第三级及以后**，"Claude can choose to navigate and discover only as needed"。
- **代码作为工具**："skills can also include code for Claude to execute as tools at its discretion"，且因为"code is **deterministic**"，这类工作流"consistent and repeatable"。Codex 提示词里也点明动机："sorting a list via token generation is far more expensive than simply running a sorting algorithm"。
- **开发方法论（四条，原文标题）**：
  1. **Start with evaluation**："Identify specific gaps in your agents' capabilities by running them on **representative tasks** ... Then build skills incrementally to address these shortcomings."
  2. **Structure for scale**：`SKILL.md` 变臃肿就拆分；"If certain contexts are **mutually exclusive or rarely used together**, keeping the paths separate will reduce the token usage."并明确代码的**双重身份**："code can serve as both executable tools and as documentation. It should be **clear whether Claude should run scripts directly or read them into context as reference**."
  3. **Think from Claude's perspective**："Pay special attention to the `name` and `description` ... Claude will use these when deciding whether to trigger the skill."
  4. **Iterate with Claude**："ask Claude to **capture its successful approaches and common mistakes** into reusable context and code within a skill."
- **安全边界（官方明示）**：skill 能引入漏洞或诱导数据外泄，因此"installing skills only from **trusted sources**"，并对"code dependencies and bundled resources like images or scripts"做审计——**skill 是供应链攻击面**。

**对守衡的可迁移结论** `[推断]`：
1. **规则库 ≠ Skill**。规则是"事实/约束"（第一、二层知识），Skill 是"程序"（怎么做一次审查、产出什么、边界在哪）。守衡应把"判定引擎的调用契约"沉淀为一个 Skill，把"规则条目"留在表里。
2. **`description` 是触发器，不是文档标题**。若未来要给守衡加"竞品文案比对""直播话术预审"等技能，`description` 的写法直接决定误触发率。
3. **确定性优先**：能用脚本判定的（如关键词命中、白名单匹配、格式校验）就写进 `scripts/`，不要交给模型"生成判断"。这与本项目"检查必须配反向对照"的纪律同向。
4. **`references/` 是理想的先例库落点**：先例摘要放 `references/`，全文留在多维表格，SKILL.md 只保留"何时读哪一份"的导航。

---
