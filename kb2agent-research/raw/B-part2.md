### B4. 记忆分层：MemGPT、Mem0（以及它们对"知识库"概念的改写）

**MemGPT: Towards LLMs as Operating Systems**（arXiv:2310.08560，2023-10 提交 / 2024-02 修订）
出处：<https://arxiv.org/abs/2310.08560>【一手/摘要】

- **核心机制**：提出 **virtual context management**——"a technique drawing inspiration from **hierarchical memory systems in traditional operating systems** that provide the appearance of large memory resources through **data movement between fast and slow memory**"。
- 系统"s intelligently manages **different memory tiers**"，并用 **interrupts** 管理自身与用户之间的控制流。
- 两个验证域：**document analysis**（分析远超上下文窗口的大文档）与 **multi-session chat**（跨会话记住、反思、演化）。
- **对知识库的含义**：MemGPT 把"知识库"从"一个静态语料库"改写为"**一个由 agent 自己管理换入换出的分层记忆**"。`[推断]` 这与 RAG 的关键差别在于**谁决定载入什么**：RAG 由检索器决定，MemGPT 由 agent 决定。

**Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory**（arXiv:2504.19413，2025-04-28）
出处：<https://arxiv.org/abs/2504.19413>【一手/摘要】

- 架构："a scalable memory-centric architecture that addresses this issue by **dynamically extracting, consolidating, and retrieving salient information** from ongoing conversations."
- 变体："an enhanced variant that leverages **graph-based memory representations** to capture complex relational structures"。
- **量化收益（这是少见的公开数字，值得引用）**：在 LOCOMO benchmark 上，Mem0 "achieves **26% relative improvements in the LLM-as-a-Judge metric over OpenAI**"；带图记忆的版本"achieves around **2% higher overall score** than the base configuration"；相对 full-context 方法，"**91% lower p95 latency** and saves more than **90% token cost**"。
- 评测对照了六类基线：既有记忆增强系统、不同 chunk/k 的 RAG、full-context、开源记忆方案、专有模型系统、专用记忆管理平台。

`[推断]` **对本项目的两条启示**：
1. **图记忆的边际收益远小于"有没有记忆层"本身**（26% vs 2%）。在守衡这种规则显式的系统里，先做"结构化裁决记录"比先做"知识图谱"划算得多。
2. **Mem0 用 LLM-as-a-Judge 作为主指标**。合规审核场景的对错更接近**分类问题**，因此守衡的评测不应只做"生成质量打分"，必须做**混淆矩阵**（漏判/误判分开统计）。`[推断]`

---

### B5. GraphRAG 与 LightRAG：结构化检索索引的两种取舍

**GraphRAG**（Microsoft，arXiv:2404.16130，2024-04 / 2025-02 修订）
出处：<https://arxiv.org/abs/2404.16130>【一手/摘要】

- **它要解决的问题（原文）**："RAG fails on **global questions** directed at an entire text corpus, such as 'What are the main themes in the dataset?', since this is inherently a **query-focused summarization (QFS)** task, rather than an explicit retrieval task."
- **索引结构（两阶段，原文）**："uses an LLM to build a graph index in **two stages**: first, to derive an **entity knowledge graph** from the source documents, then to **pregenerate community summaries** for all groups of closely related entities."
- **问答流程**："each community summary is used to generate a **partial response**, before all partial responses are again **summarized in a final response**."
- **适用边界（原文自陈）**："For a class of global sensemaking questions over datasets in the **1 million token range**"，对**comprehensiveness** 与 **diversity** 有显著提升。

**LightRAG**（arXiv:2410.05779，2024-10 / 2025-04 修订）
出处：<https://arxiv.org/abs/2410.05779>【一手/摘要】

- **批判对象**："existing RAG systems have significant limitations, including reliance on **flat data representations** and **inadequate contextual awareness**, which can lead to fragmented answers."
- **两个关键设计**：① **dual-level retrieval**——"enhances comprehensive information retrieval from both **low-level and high-level** knowledge discovery"；② **增量更新算法**——"an **incremental update algorithm** that ensures the timely integration of new data"。

`[推断]` **对本项目的取舍建议**：
- GraphRAG 的**索引构建成本是 LLM 全量跑语料**，且论文只在"1M token 量级 + 全局性总结问题"上验证。守衡的核心问题是**逐条内容判定**（local，而非 global），**因此 GraphRAG 的主战场不是守衡的判定路径**。
- 但 GraphRAG 的"**社区摘要**"思路对守衡有一个精准的用法：**把散落的先例/申诉记录聚合成"同类问题的处置共识摘要"**，供规则维护者（而非判定引擎）复盘。这是"人类决策支持"而非"在线判定"。[推断]
- LightRAG 的**增量更新**才是守衡更需要的属性：平台政策频繁变更，索引必须能增量吸收新规则与新先例，而不是全量重建。

---

### B6. 检索的自我修正：Self-RAG / CRAG / LangGraph 的"flow engineering"

**出处**：LangChain 官方博客 *Self-Reflective RAG with LangGraph*（Ankush Gola，2024-02-07）<https://www.langchain.com/blog/agentic-rag-with-langgraph>【一手】

- **承认的工程现实**："In practice, many have found that implementing RAG requires **logical reasoning around these steps**: for example, we can ask **when to retrieve** ..., **when to re-write the question** for better retrieval, or **when to discard irrelevant retrieved documents and re-try retrieval**?"
- **三种认知架构（原文）**：**chain**（基础 RAG 流程）、**routing**（LLM 在不同 retriever 间选择）、**state machines**（支持循环与显式转移，适合自反思 RAG）。
- **CRAG 的三个可迁移机制**：① 用**轻量级 retrieval evaluator** 给每篇检索结果打置信分；② 当向量检索被判定为 ambiguous/irrelevant 时，**补充 web 检索**；③ **knowledge refinement**——把文档切成 "knowledge strips" 逐条打分过滤。
- **Self-RAG 的四个反思 token（可直接借用为审核提示词结构）**：
  - `Retrieve`：要不要检索（yes / no / continue）
  - `ISREL`：检索到的段落是否**相关**（relevant / irrelevant）
  - `ISSUP`：生成内容是否**被该段落支持**（fully supported / partially supported / no support）——**这是抗幻觉的关键一环**
  - `ISUSE`：生成内容对问题是否**有用**（5→1 分）
- LangChain 在实现中做了取舍以降低时延："Instead, we perform a **single generation from all relevant documents**. The generation is then **graded relative to the documents (e.g., to guard against hallucinations)** and relative to the answer."

`[推断]` **对本项目最强的一条映射**：`ISSUP`（"这句话是否被这份材料支持"）几乎就是守衡"**每条判定结论必须能指回它所引用的规则/先例**"的形式化版本。把 `ISSUP` 作为判定的**自检步骤**（而非事后审计），可以在生成阶段就拦掉"规则没写但模型说了"的越界结论。这与本项目"任何新声明都必须配反向对照"的纪律是同一种工程气质。

---

### B7. 「知识 → Agent」的阶段表（本报告提炼，标注资料支撑）

> **性质声明**：下表的**阶段划分与验收标准是本报告的提炼与设计**，不是任何单一来源的官方阶段模型。每一行右列注明了支撑该阶段的公开资料。凡我加的判断均标 `[推断]`。

| 阶段 | 目标 | 关键动作 | 产出物（artifact） | 验收标准 | 资料支撑 |
|---|---|---|---|---|---|
| **S0 评测先立** | 先能量化"现在差在哪" | 抽代表性任务集；先跑最简方案（单次调用 + 检索 + few-shot）记录失败模式 | 失败模式清单 + 基线指标 | 能说出**具体**失败样例与频次，而不是"效果一般" | Anthropic Agent Skills："**Start with evaluation**"；Building effective agents："optimizing single LLM calls with retrieval and in-context examples is usually enough" |
| **S1 语料盘点与权威源认定** | 每一条知识都有**唯一的权威版本** | 建立源清单：谁拥有、生效时间、替代关系、谁可读；标出互相冲突的文档 | 源登记表（含 owner / effective_from / supersedes / ACL） | 任意一条规则问"以哪份为准"，答案唯一且可追溯 | 本项目证据：Microsoft 用 overtification/oversharing 治理与 sensitivity label 做收敛；`[推断]` 冲突源是最高频失败模式 |
| **S2 检索层（权限内索引）** | 让"能被检索到"与"有权限看到"等价 | 索引期保留权限维度；检索期按调用者身份收敛；文本富集优先 | 索引 + 连接器 + 权限映射 | 抽检：不存在"越权命中"与"有权却查不到"两个方向的错误 | Microsoft 语义索引原文（身份边界、RBAC、connector 保持访问控制） |
| **S3 结构化知识层（规则/分类法/图谱）** | 把"可判定的东西"从自然语言里提出来 | 规则表 + 分类法 + 阈值 + 优先级；必要时建实体关系 | 规则表（带版本/生效/失效）、分类法、阈值表 | 规则可**机械执行**、可 diff、可回归；阈值有明确 owner | Perspective API 官方 FAQ（阈值需随模型更新重校准）；GraphRAG / LightRAG（何时该上图谱） |
| **S4 先例层（案例库）** | 让"判断"可复用、可被质疑 | 存正例/负例/边界例 + 裁决理由 + 引用链 | 案例库（含 result / reason / cited_rules / reviewer） | 同类新问题能检出"历史上同类怎么判的"，且答案不含未复核结论 | Self-RAG 的 `ISREL`/`ISSUP`/`ISUSE`；Anthropic"curate **diverse, canonical examples**" |
| **S5 工具化与 Skill 封装** | 让知识**可被发现、可按需加载、可执行** | 把流程写成 SKILL.md；确定性部分写脚本；工具描述做 poka-yoke | Skill 目录（SKILL.md + scripts/ + references/ + assets/） | 触发器描述能区分近邻技能；确定性步骤不经过模型生成 | Agent Skills 规范（三级渐进披露）；Building effective agents（ACI、poka-yoke） |
| **S6 记忆与状态** | 跨会话保持连续性与项目状态 | 会话内：compaction / notes 文件；跨会话：结构化裁决记录 | NOTES/记忆文件 + 裁决流水 | 长任务不丢关键决策；压缩后仍保留未决项 | Anthropic context engineering（compaction / structured note-taking / sub-agents）；MemGPT；Mem0（26% vs 2% 的边际收益对比） |
| **S7 编排与护栏** | 把判定做成可预测的工作流，而非自主循环 | routing 分流 + 并行投票 + 独立护栏调用 + 人工检查点 + 停止条件 | 编排图（显式状态机）+ 处置分级规则 | 每步可观测；护栏与主判定不共享同一次调用 | Anthropic voting/sectioning 与 guardrail 建议；LangGraph 的 state machine 论述 |
| **S8 评测与回归（闭环）** | 让知识的每次变更都可被证伪 | 建黄金集；规则变更触发回归；误判申诉回流为新案例 | 回归套件 + 申诉回流流水 | **抽掉任一配置后检查必须真的变红**（本项目纪律） | Anthropic"Start with evaluation"；`[推断]` 申诉回流是合规审核类系统的必需品 |

**阶段之间的顺序约束（`[推断]`，但理由明确）**：
- **S1 必须先于 S2**：如果权威源没定，索引只是把冲突放大了。
- **S0 必须先于 S3**：规则表该长什么样，取决于失败模式清单，而不是取决于架构美观。
- **S5 可以滞后**：Skill 封装是"最后一公里"，前面的层没做扎实时，Skill 只会把混乱固化。
- **S8 不是终点而是横切**：它从 S0 就开始，贯穿到 S7。

---
