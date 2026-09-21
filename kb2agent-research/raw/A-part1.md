### 2.0 六家产品的分层对照总表

> 以下所有术语均为**产品官方原文术语**，逐条可追到 URL（详见 `raw/A-企业知识助手案例.md` 的逐条出处）。

| | **连接器/语料层** | **索引/图谱层** | **取数模式层** | **权限层** | **行为层** | **评测层** |
|---|---|---|---|---|---|---|
| **Glean** | Connectors：Native / Web history / Push API / Partner | search index + **Knowledge Graph**（Content / People / Activity）+ **personal graph**＝**system of context** | **Indexed / Live / Hybrid**（三分法） | **mirror permissions**：抓取每个源的 **permissions map**；indexed 模式用爬取时镜像的 **permission snapshot** | Assistant / Agents / Tools / **Skills** | **AI Evaluator**（租户内跑） |
| **Microsoft 365 Copilot** | Copilot connectors：**Synced**（入 Graph 并索引）vs **Federated（MCP）**（**不索引**） | **Semantic index**：tenant-level（SharePoint 文本文件）+ user-level（邮箱/工作集），**物理分置** | 无显式三档；由 Synced/Federated 承担同样的取舍 | item 级 **ACL** 随索引项存储；检索期"honor the user identity-based access boundary" | declarative agents / Copilot Studio agents | 无公开评测方法；只有 **Index browser** 运维校验 |
| **Atlassian Rovo** | Teamwork Graph Connectors（100+ 开箱；Forge 自建）；**Smart Link 型 vs 内容索引型两档** | **Teamwork Graph**（"Atlassian Cloud Platform's data intelligence layer"，1500 亿对象与关系） | 无显式分档；以"at the speed of change"表述 | **"last-mile checks"**（交付前最终校验）；"Data enters the graph with its **access controls intact**" | Rovo Search / Chat / Agents / Studio；**CLI + MCP（可写回）** | 只有数字（44% 更准/48% 更少 token、60%），**方法未公开** |
| **Notion AI** | **AI Connectors**（Slack/Drive/Jira/Gmail/Teams/SharePoint/GitHub/Linear…） | 托管向量库（官方点名 **Turbopuffer**）+ Agent 的 memory system（**用 Notion pages 与 databases 承载**） | 无显式分档 | "honor existing permissions"；第三方内容按 **permissions mapping between each connected app and Notion** 摄入；Agent **"acts as you"** | Enterprise Search / Agents / Custom Agents / MCP（可写回） | 无公开方法；只有能力边界声明 |
| **Sana** | integrations / connectors（100+）+ direct upload | "unifies your company's data"、real-time indexing；**无图谱层术语** | 无显式分档 | 三种入法决定权限语义：**direct upload / private integration（每用户自认证）/ shared integration（admin 定）** | Sana Agents + Enterprise search | 排序模型用**内部专用训练集**；有用户反馈与 Knowledge verification 设置，**无公开指标** |
| **Dust.tt** | Data sources：**Connections / Folders / Websites**；对象为 **Documents / Chunks** | 无图谱层 | 把检索拆成**四个工具**：**Search（语义 RAG）/ Include data（倒序填窗）/ Table queries（转 SQL）/ Extract data（单次 ≤500k tokens）** | **Spaces** 承载权限；"Discover Knowledge **follows the user's permissions** and the spaces available to the agent" | Discover Knowledge / Discover Skills / Discover Tools；**Agent Memory / Skills / Pods / Context Compaction** | 只有 thumbs up/down 反馈 API；官方建议自行 A/B |

**这张表本身就给出结论**：六家的**连接器层、索引层、权限层、行为层**几乎人人都有；**取数模式层（Indexed/Live/Hybrid）只有 Glean 显式命名**；**评测层只有 Glean 公开到指标级**。`[推断]` 这两个"少数派"恰好都是最贵的部分——前者要维护多套并发取数管线，后者要在客户私有语料上建评测。

---

### 2.1 Glean：三档取数模式 + 唯一公开到指标级的评测体系

**它解决什么**：把企业内 100+ 系统的语料统一成"权限感知的一份上下文"，搜索 / Chat / Assistant / Agents 共用同一底座。

**知识库分层的官方术语**（均已打开原文）：
- **连接器层**：`Connectors` 分 **Native / Web history / Push API / Partner** 四类（<https://docs.glean.com/connectors/about>）。无 connector 时用浏览器扩展的 **web history connector**——**结果仅对该用户可见、组织不可见**（这是个很聪明的"个人语料"设计）。
- **索引层**：`search index`（承担 fast retrieval / faceting / ranking）。
- **图谱层**：**Knowledge Graph**，三根支柱原文为 **Content / People / Activity**；另有 **personal graph**，与前者合称 **system of context**（<https://docs.glean.com/security/knowledge-graph>、<https://www.glean.com/blog/knowledge-graph-agentic-engine>）。
- **取数模式层（本报告认为最有借鉴价值的一个设计）**：**Indexed access / Live access / Hybrid access** 三档（<https://docs.glean.com/connectors/connectors-power-glean>）。
- **行为层**：Assistant / Agents / Tools，2026 年新增 **Skills**。

**语料治理**：爬取类型官方列五种——**Full content crawl / Incremental content crawl / Activity crawl / Identity crawl / People data**；其中 **Activity crawl 明确覆盖 "permission modifications"**（<https://docs.glean.com/connectors/crawling-types>）。**逐连接器公布默认刷新频率**，例如 GitHub/GitLab webhook 变更 5 分钟内、Salesforce 增量 10 分钟、Website 默认 28 天（<https://docs.glean.com/connectors/crawling-refresh-rates>）。数据落在**租户隔离**环境中，支持 **customer-hosted deployment**。

**权限/ACL 进检索**：官方原文是 **"mirror permissions"** ——"They also fetch the **permissions map** from each source, ensuring search results strictly adhere to the access permissions set in the source application"；indexed 模式下检索使用的是 **"the permission snapshot that was mirrored during crawling and incremental updates"**。图谱侧："The entire graph in Glean is designed with fine-grain access controls so employees can only see the data that is already shared with them in the source system"。返回体带 `"visibility": "SPECIFIC_PEOPLE_AND_GROUPS"`。**未找到**官方对"检索期是否再对上游做一次校验"的明确描述——`[待确认]`。

**评测（八家中公开度最高，且这是本报告认为最值得守衡逐条抄的一节）**：
- 载体：**AI Evaluator**（LLM-as-judge），**在每一个客户租户内**评测，数据不外泄（<https://www.glean.com/blog/glean-ai-evaluator>）。
- **检索侧指标**：**Context relevance rate**、**Context recall rate**——后者的定义是 **canonical document**（"the most authoritative and comprehensive source of information"）**被召回的比例**。
- **生成侧指标**：**Answer relevance**（二分类）、**Answer completeness**（complete / incomplete / no-answer 三档）、**Groundedness**（**先拆 claims，再逐条标 inferable / generic / ungrounded**，得分 = 有据 claims / 总 claims）。
- **方法学细节**：单答案评分（避免位置偏见）、**分类标签优先于数值**、Chain-of-Thought + few-shot、**模型集成（"LLM jury"）以抑制自我增强偏见**；对标 **RAGAS**。
- **量化结果（罕见的公开数字）**：内部数据集上**人类标注者彼此一致率仅 79%**（被当作自动评测的**上限**）；**AI Evaluator 与人类一致率 74%**；把 Evaluator 信号加入用户留存模型使预测准确率 **+18.8%**，其中 **"No Answers" 与低 groundedness 是流失的强预测因子**。
- **评测集怎么造**：① 用户不满意后**转去搜索并改写 query** 的 session；② 从语料**离线挖掘 QA 对**；并据此构造 **"hard" evaluation sets**。
- 检索传统指标：**NDCG@10**、**R@100**（<https://www.glean.com/blog/unlocking-the-power-of-vector-search-in-enterprise>）。

**关键设计决策**：
1. 把"权限快照 + 新鲜度"**显式做成可配置的三档取数模式**，而不是承诺统一实时语义——把一致性成本外化为策略。
2. **Activity crawl 单独成类并显式覆盖权限变更**——ACL 变更被当作与内容变更同级的被追踪事件。
3. **逐连接器公布刷新频率**，把"新鲜度"变成管理员可审计的数字（同时承认是默认值而非保证）。
4. **评测在客户租户内进行**，用"不外泄"换取"能在真实私有语料上评测"——这是企业 RAG 评测最难的一步。
5. `[推断]` 用 **"hard" eval sets** 反向驱动迭代，等于把 eval 当**缺陷定位工具**而非仅打分工具。

---

### 2.2 Microsoft 365 Copilot：ACL 是"索引期快照"，且有公开的 24 小时缺口

> 除 `semantic-index-for-copilot` 外，本节引用的 ACL 细节来自 <https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/indexed-content>（由子调研线打开并摘录原句）。

**知识库分层**（官方术语）：
- **Semantic index**："a semantic index is created for every subscription at the **tenant and user level**"。**tenant-level index** 来自文本型 SharePoint Online 文件；**user-level index** 覆盖邮箱与用户工作集。二者**存储位置不同**：user-level 存在**用户邮箱所在处**，tenant-level 存在 **"isolated and protected customer's tenant container"**。
- **Copilot connectors 两类**：**Synced connectors**（ingest 并索引进 Microsoft Graph）与 **Federated connectors（基于 MCP）**——后者官方明确 **"Semantic indexing: Not applicable"**，专用于 **"regulated content that must remain in source"**。Synced 又分 **Tenant configuration / Self-serve configuration**（后者按用户维度、用户自认证、断连即删除）。
- 行为层：declarative agents / Copilot Studio agents。

**语料治理**：
- 索引项结构原文：**"Each item includes content, metadata (like title and URL), and an access control list (ACL) that enforces permissions."**
- 更新节奏：用户邮箱中文档近实时；**新增到 SharePoint 且经站点继承被 ≥2 人访问的文档按天索引**；已索引文档**更新即时索引**。
- 排除：管理员可对敏感站点关闭 "Allow this site to appear in search results"，**同时**排除出 Microsoft Search 与语义索引；官方明确**没有"只排除语义索引"的选项**。
- 驻留：EUDB 客户索引存放于 EU/EFTA 数据中心；支持 **BYOK（Purview Customer Key）**。
- 训练：**"Prompts, responses, and data accessed through semantic indexing aren't used to train foundation LLMs."**

**权限/ACL 进检索（本报告最重要的"反面参照"）**：
> **"Changes to user or group permissions (ACLs) might take up to 24 hours to reflect."**
> **"Permissions updates occur during a full crawl, not an incremental crawl."**
> ——即：源系统权限变化后，**必须手动触发一次新的 full crawl** 才能更新索引（<https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/indexed-content>）。

其他相关事实：连接器**默认 tenant-wide**（"unless external item security is restricted"）；提供 **Index browser** 可按 item 查 Properties / Permissions（allow/deny、Allow everyone vs Only people with access）与 **Check user access**（按用户验证可见性，含"用户属于 deny 组则整体被拒"的判定）。官方在 "reduce oversharing" 建议里承认需要 **"performing access control checks in real time"** 作为补充。

**评测**：**未找到公开方法**。可用的只有运维手段（Index browser 的 item 级状态校验，含 Partially indexed / Deny all 等诊断）与**官方自陈的能力边界**——语义索引页面明确列出它不擅长的查询类型（无主题关键词的查询、多参数查询、计数类查询）。`[推断]` 这份"已知失效清单"可以直接当"已知失效集"用来设计回归用例，虽然它不是 eval 方法。

**关键设计决策**：
1. **ACL 变更只在 full crawl 生效且最长 24h**——用"索引期快照 + 明确的 SLO 缺口"换索引规模与成本可控。
2. **提供 MCP 联邦连接器作为"不落索引"通道**——把强合规数据整体移出索引治理（代价：**没有语义索引**，检索退化为工具调用）。这是"用放弃检索能力换合规"的显式取舍。
3. **排除索引与排除搜索绑成同一个开关**——减小管理员误配置面，并坦诚说明无法只排除其一。
4. **为每个 item 保留可查询的 ACL 视图 + Check user access**——把权限正确性从"信任"变成"可抽查"。

---

### 2.3 Atlassian Rovo：与 Microsoft 正面对照的 "last-mile checks"

**知识库分层**：**Teamwork Graph** 官方定义为 **"Atlassian Cloud Platform's data intelligence layer"**，四个动词 **Unifying → Learning → Enriching → Growing**；实体包括 People / Projects / Issues / Goals / Work Item / Video / Sprint / Roadmap / Focus Area；规模原文 **"over 150 billion objects and relationship"**（<https://www.atlassian.com/platform/teamwork-graph>）。连接器 **100 out-of-the-box**，可用 **Forge** 自建。

**连接器的两档设计（值得借鉴）**：连接器目录区分 **Smart Link 型（仅链接跳转，不索引内容）** 与**内容索引型**（<https://www.atlassian.com/software/rovo/connectors>）。`[推断]` 这为"不愿让内容离开源系统的应用"提供了一个低谈判成本的接入档位。

**权威源认定（少见的明确表述）**：
> **"Authoritative retrieval: Assistants navigate relationships across Confluence and Jira to surface the single sources of truth, rather than just relevant pages."**

**权限/ACL 进检索**：
> **"Teamwork Graph runs last-mile checks, so users and apps only get access to the data they're entitled to."**
> "Preserve permissions: Data enters the graph with its **access controls intact**, so AI respects who can see what."

`[推断，但为对原文措辞的直读]` "last-mile checks" 指向**交付前的最终校验**，与 Microsoft 的"仅 full crawl 更新 ACL（≤24h）"构成方法论对立。**未找到** ACL 变更生效时延的公开数字。

**评测**：官方公布 **"grounding responses in Teamwork Graph data delivered 44% more accurate results while using 48% fewer tokens"** 与 **"Users are 60% more successful with Rovo Search than the leading open-source enterprise search apps"**。**方法学未公开**（无指标定义、无黄金集、无评审流程）→ **数字可引用，结论不可复现**。本报告将其标注为**厂商宣称口径**。

**其他设计决策**：把图谱开放成 **Teamwork Graph CLI（300+ commands）与 Rovo MCP Server**，且**不是只读**——"Developers can use it to write and update the graph too"。`[推断]` 图谱由此从"检索后端"升级为"可被外部 agent 读写的工作状态层"。

---

### 2.4 Notion AI：公开硬性时间预算 + 权限映射即连接器契约

**知识库分层**：**AI Connectors**（Slack / Drive / Jira / Gmail / Teams / SharePoint & OneDrive / GitHub / Linear / Notion Mail / Calendar）→ **Enterprise Search**（检索面 = workspace + connected apps + web，**可逐源收窄**）→ **Agent（3.0）**：官方原文称其记忆系统 **"using Notion pages and databases"**，配合 **instructions page** 做个性化，**Custom Agents** 可按 schedule/trigger 运行 → **MCP**（第一方，可读 workspace + 已连接应用，**并可写回 Notion**）。

**语料治理（公开了罕见的硬性时间预算）**：
- **回溯窗口**：一般只能访问 **setup date 往前一年**（例：2024-06-01 连接 → 可访问 2023-06-01 起）。
- **首次摄取最长 72 小时**；**新内容最长 3 小时**才可被搜到。
- **断连后**：内容变为不可搜（部分连接器最长 1 小时），**数据在 1 天内删除**。
- 连接器**安装在 workspace 级**，"unrelated to the workspace owner that installed it"，owner 离职不影响（Google Drive 例外，会自动找另一位有权限的 owner 重建）。
- 训练：不用于训练 Notion 模型，也不允许子处理商用客户数据训练其模型。

**权限/ACL 进检索**：
- **"Notion AI will honor existing permissions… Users will not be able to generate content or receive responses based on resources they do not have access to."**
- 第三方内容：**"only ingesting content according to the permissions mapping between each connected app and Notion."**
- Agent 行为：**"It acts as you, so it can only access what you can already see."**——把权限模型统一到**用户身份**而非 agent 身份。
- 实现细节（少见的公开度）：**"we store and create embeddings in a vector database hosted by Turbopuffer"**，Turbopuffer 通过 **SOC2 Type II**。
- Notion 3.0 同期上线 **database row/page-level access**，作为 AI 权限的配套能力一起发布。

**评测**：**未找到公开方法**。官方只给能力边界声明："best for finding and summarizing information. They're not meant to run complex calculations or perform data analysis."；"might have a more difficult time with aggregating lots of information from an app or multiple apps."

**关键设计决策**：
1. **把"第三方语料的权限映射"当作连接器的一等契约**，而不是先全量灌入再过滤。
2. **公开硬性时间预算**（72h / 3h / 1 年 / 1 天），把"最近一年"作为默认知识边界，**明确牺牲长期归档检索**。
3. **检索面可逐源逐空间收窄**，让"搜什么"成为用户可操作的控件。
4. **Agent 以调用者身份行动**，避免"agent 是超级用户"的权限放大。

---

### 2.5 Sana / Dust.tt：两条不同的取舍路线

**Sana**：能力分为 **Sana Agents** 与 **Enterprise search** 两条线；接入称 **integrations / connectors**，强调 "unifies your company's data" 与 **real-time indexing**。
- **权限的最独特设计**：用**接入路径**决定权限语义，官方 FAQ 给三分法——**(i) direct upload**（在 Sana 内逐文档管理或 collections）、**(ii) private integration**（**每个用户自行认证，"can see results only from the scope they have access to"**）、**(iii) shared integration**（admin 决定哪些文档对所有 collection/workspace 用户可见）。
- 治理：**single tenant architecture**（租户间不共享数据库）、静态 AES-256、传输 TLS 1.2+、可部署在客户自有云、支持 **Regional deploys**；**排序算法只用内部专用训练集**训练，客户数据不用于训练第三方 LLM。
- **缺失**：图谱层命名、去重、权威源认定、逐连接器刷新频率、评测方法——**全部未找到公开资料**。

**Dust.tt**：分层最清晰的一个。
- **Data sources 三类**：**Connections / Folders / Websites**；对象分 **Documents / Chunks**。
- **把"知识访问"显式拆成四个工具**：**Search（语义 RAG）/ Include data（倒序填充上下文窗口）/ Table queries（转 SQL）/ Extract data（单次最多处理 500k tokens 抽结构化）**；另有 **Advanced search mode** 给 agent 文件系统级能力（列目录、按路径读文件），并**如实承认**"generally requires more tool calls, hence more induced latency"。
- **分层过滤的亮点**：文档 label 支持 **must-have / must-not-have** 双向语义——"Documents must have at least one of the must-have labels to be included… Documents with any must-not-have labels will be excluded"，并支持**in-conversation filtering**（按会话上下文动态过滤）。`[推断]` 这把"排除废弃内容（如 `deprecated`）"做成了**检索时的一等机制**，而不是依赖源系统目录结构。
- **官方警告**：不要把全部数据源挂到一个 agent——"agents that are plugged to a **constrained number of data** will usually perform better"，**把召回范围当超参调**。
- 权限：**Spaces** 承载；"Discover Knowledge follows the user's permissions and the spaces available to the agent."**（未到机制级）**
- 评测：只有 thumbs up/down 反馈 API 与官方"自行 A/B"的建议，**无公开方法**。

---

### 2.6 证据不足但必须点名的两家：Salesforce Agentforce 与垂直 Agent

**Salesforce Agentforce + Data Cloud**：本次调研**未能打开 `help.salesforce.com` 与 `developer.salesforce.com` 的关键正文**（JS 渲染只回 "Loading"；另一路径 404）。可确证的只有官方产品页术语：**"Data. Reasoning. Actions."**；推理侧 **Atlas Reasoning Engine**（"breaks down the initial prompt into smaller tasks, evaluating at each step and proposing a plan"）；数据侧 **Data 360 / Customer 360**；构建侧 **Agent Builder / Subagents / Actions / Instructions**；可信层 **Einstein Trust Layer**（能力清单：**dynamic grounding、zero data retention、toxicity detection、secure data retrieval、Audit Trail**）；**Agentforce Guardrails**；**Agentforce Observability**。
- **权限/ACL 如何进检索：未找到公开资料。** 唯一可用的是泛化表述"least privileged access, and core access controls"——**本报告不以此支撑任何结论**。
- **评测：只找到产品化能力**（生成测试用例、检查护栏遵守情况、Observability、Audit Trail），**无方法学**。
- **本报告立场**：Agentforce 是市场上最重要的企业 Agent 产品之一，但**本节证据不足以支撑架构性结论**，故只做术语登记，不做比较。

**客服/垂直 Agent（Sierra、Decagon、Harvey、Abridge、Nuance DAX）**：见 `raw/` 下子调研产出；本报告在第 5 节只采纳其中有硬出处的部分。

---
