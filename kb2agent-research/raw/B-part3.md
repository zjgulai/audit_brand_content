### B8. Microsoft《AI agent orchestration patterns》：复杂度阶梯与 maker-checker 环

**出处**：<https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns>（Azure Architecture Center，最后更新 2026-02-12）【一手】

**复杂度阶梯（三级，官方明确要求"用最低够用的复杂度"）**：

| 级别 | 官方描述 | 何时用 | 官方注意事项 |
|---|---|---|---|
| **Direct model call** | 单次模型调用 + 精心设计的 prompt，**无 agent 逻辑、无工具** | 分类、摘要、翻译等单步任务 | "**If prompt engineering can solve the problem, you don't need an agent.**" |
| **Single agent with tools** | 一个 agent 推理并从工具/知识源/API 中选择，可多轮循环 | 单领域的多样化查询 | "**Often the right default for enterprise use cases.**"；**必须设迭代上限**以防工具调用死循环 |
| **Multiagent orchestration** | 多个专门化 agent 协作，由 orchestrator 或对等协议协调 | 跨职能/跨领域、需要**不同安全边界**、可并行专门化 | "Adds coordination overhead, latency, and failure modes" |

**五种编排模式（官方命名与适用）**：**Sequential**（pipeline / prompt chaining）、**Concurrent**（fan-out/fan-in / scatter-gather）、**Group chat**（roundtable / multiagent debate / council）、**Handoff**（dynamic delegation）、**Magentic**（task-ledger-based / adaptive planning）。

**对本项目最直接相关的是 maker-checker loop（官方定义，属 group chat 的特例）**：
> "one agent, the **maker**, creates or proposes something, and another agent, the **checker**, evaluates the result against **defined criteria**. If the checker identifies gaps or quality problems, it **pushes the conversation back to the maker with specific feedback**."循环直到 checker 通过或达到最大迭代上限。

官方对该模式的硬要求：
- "This pattern requires **clear acceptance criteria** for the checker agent so that it can make **consistent** pass or fail decisions."
- "**Set an iteration cap** to prevent infinite refinement loops, and **define fallback behavior for when the cap is reached**. The failover behavior might include **escalation to a human reviewer** or a quality warning alongside the best possible result."
- 官方点名的适用场景包括 **"Compliance and regulatory validation that requires multiple expert perspectives"** 与 **"Content creation workflows that require editorial review with a clear separation of concerns between creation and validation"**——**与本项目的合规审查定位高度吻合**。

**必须逐条抄下来的三条"安全与权限"要求（官方原文）**：
1. **"Security trimming must be implemented in every agent in the pattern."**——并解释了矛盾点："Agents must have broad access to knowledge stores to handle requests from all users, but they **must not return data that's inaccessible to the user**."
2. **"Apply content safety guardrails at multiple points in the orchestration, including user input, tool calls, tool responses, and final output. Intermediate agents might introduce or propagate harmful content."**——注意四个点位，尤其是**工具响应**这一环，常被忽略。
3. **"Design agents and their orchestrators to follow the principle of least privilege."** + 设计审计轨迹以满足合规要求。

**其余可迁移的工程要求**：
- **上下文与状态**：多 agent 编排下上下文膨胀快，"Monitor accumulated context size and use **compaction** techniques, such as summarization or **selective pruning**, **between agents**"；跨会话/长任务要"**persist shared state externally**"，并把持久化状态**限定到最小必要信息**（"To reduce token overhead and **privacy risks**, scope persisted state to the minimum necessary information."）。
- **可靠性**：timeout/retry、优雅降级、**错误必须外显而非隐藏**、**把输出传给下一个 agent 前先校验**（"Low-confidence, malformed, or off-topic responses **can cascade** through a pipeline"）、断路器、checkpoint。
- **评测与可观测性（原文）**："Agent outputs are **nondeterministic**, so use **scoring rubrics or language-model-as-judge evaluations rather than exact-match assertions**." + "**Instrument all agent operations and handoffs**" + 为每个 agent 建立性能与资源基线。
- **成本**：按任务复杂度给每个 agent 配不同档模型；"Agents that perform **classification, extraction, or formatting** can often use smaller, less expensive models"；监控 per-agent token 消耗。
- **HITL**：明确"哪些点需要人工、是可选还是强制、人的回复是**批准**还是**反馈**"；强制门是同步的，因此**在门处持久化状态**；并给出一个很好用的细化手段——"You can also **scope HITL gates to specific tool invocations rather than full agent outputs** so that the orchestration can proceed autonomously for low-risk actions."
- **反模式清单（节选）**：为了协调而协调、加入没有实质专门化的 agent、忽视多跳延迟、并发 agent 之间共享可变状态、**对本质不确定的流程使用确定性模式（以及反过来）**、忽视资源约束。

**对守衡的映射** `[推断]`：
- 守衡的判定引擎是**单个 agent with tools + 确定性规则**，按官方阶梯应停在第二级，**不应上多 agent**。
- 但"误判申诉 → 复核 → 回流"这条线，形状就是一个 **maker-checker loop**：maker 给出处置建议，checker 按**明确的验收标准**复核，不通过则带具体反馈回退，且**必须有迭代上限与到达上限后的兜底（升级人工）**。
- 官方那句 **"security trimming must be implemented in every agent"** 提醒：如果守衡未来拆出多个子判定（文本/图片/直播话术），**每个子判定都要独立做权限收敛**，不能只在外层做一次。

---

### B9. 未能补齐的方法论缺口（诚实声明）

按任务要求本应覆盖但**本次未能取得可靠一手证据**的部分，逐条列出，不做推断填补：

| 缺口 | 状态 | 原因 |
|---|---|---|
| **OpenAI《A practical guide to building agents》** | **未取得** | `openai.com` 相关页返回 403；`cdn.openai.com` 域名不可解析；`developers.openai.com` 返回 403。**替代证据**：本报告改用 OpenAI 官方 Cookbook（`How_to_use_moderation` / `How_to_use_guardrails`），已取得完整正文（见 C1）。 |
| **Google《Agents》白皮书（Kaggle / Google Cloud）** | **未取得正文** | `kaggle.com/whitepaper-agents` 返回 200 但正文为 JS 渲染，只得到标题 "Agents"。**未做任何内容引用。** |
| **LangChain / LlamaIndex 的 RAG→Agent 官方叙事长文** | **部分取得** | LangChain 官方博客 *Self-Reflective RAG with LangGraph* 已取得完整正文（见 B6）；`blog.langchain.com/agentic-rag` 路径 404，未找到正确 slug。**OpenAI Agents SDK / LlamaIndex 的 agentic strategies 文档未取得。** |
| **Google ADK / Vertex AI RAG Engine / grounding 文档** | **未取得** | 未在本次窗口内定位到可直连的官方页。 |
| **Semantic Kernel 的 memory/planner 设计** | **未取得** | 未定位到可直连页；Azure 架构中心已改用 Agent Framework，Semantic Kernel 文档标注为迁移中（这一"迁移"事实本身来自 B8 引用页，【一手】）。 |

`[推断]` 这五个缺口**不影响本报告的主结论**：B1–B8 已覆盖 Anthropic（agent 选型 + 上下文工程 + Skill 封装）、Microsoft（编排模式与复杂度阶梯）、记忆分层（MemGPT / Mem0）、结构化索引（GraphRAG / LightRAG）、检索自修正（Self-RAG / CRAG），**阶段表所依赖的每一环都有已打开的一手出处**。

---
