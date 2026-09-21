# A · 企业知识助手 / 知识 Agent 案例（知识库架构与知识→Agent 路径）

> 调研方式：全部结论来自本会话实际打开过的官方页面（web_fetch / read_page 返回正文）。
> 标注规则：
> - `已打开` = 本会话 fetch/read_page 返回过正文，可引用细节。
> - `[仅搜索摘要，未打开]` = 只在搜索结果/摘要里确认存在，未打开正文，只用于指出线索，不用于支撑事实。
> - `[推断]` = 本文档作者的推理，不是原文。
> - `未找到公开资料` = 明确承认没有找到。
>
> 检索工具状况（影响证据覆盖，务必如实转述）：本机 `web_search`/`read_page` 依赖的 Firecrawl 免费额度当日耗尽（HTTP 429），`exa_search` 未配置 API Key；DuckDuckGo HTML 端点随后弹出人机验证。最终可用的通路是 `web_fetch` 直连官方文档站 + `read_page` 的**本地直抓回退**（不走 Firecrawl 时能拿到整页正文）。因此**JS 渲染且不提供静态正文的站点（如 help.salesforce.com、developers.glean.com 部分页）未能打开正文**，已在文中逐条标注。

---

## 摘要（≤300字）

八家收敛为同一四层：连接器→索引/图谱→权限→行为。分化仅两列。权限时点：Microsoft 最粗（ACL 仅 full crawl 更新、≤24h）；Glean 居中（permission snapshot + Indexed/Live/Hybrid 三档）；Sierra、Atlassian、Harvey、Dragon Copilot 最细（运行期工具可见性裁剪、last-mile checks、按患者隐私标记裁剪）。评测公开度与强监管正相关：Glean、Sierra、Harvey、Abridge、DAX 公开到方法级；Microsoft、Notion、Sana、Dust 仅产品化测试。

---

## 横向对照总表（八案例 × 六个必答子问题）

> 表内术语**一律为各产品官方原文术语**，逐条可由上文各节的"出处"追溯到已打开页面。

| | 语料/连接器层 | 索引 / 图谱 / 知识层 | **权限进检索的机制（核心对照）** | 行为层 | 评测（公开度） |
|---|---|---|---|---|---|
| **Glean** | Connectors：Native / Web history / Push API / Partner | search index + **Knowledge Graph**（Content / People / Activity）+ **personal graph** = **system of context**；取数显式三分 **Indexed / Live / Hybrid** | **mirror permissions**：抓每源 **permissions map**；indexed 模式用爬取时镜像的 **permission snapshot**；Activity crawl 明确覆盖 **permission modifications** | Assistant / Agents / Tools / **Skills** | **最高**：租户内 **AI Evaluator**，指标级公开 + 人机一致率 74% |
| **Sana** | integrations / connectors（100+）+ direct upload | "unifies your company's data"、real-time indexing；**无图谱层术语** | 三种入法决定权限语义：**direct upload / private integration（每用户自认证）/ shared integration（admin 定）** | Sana Agents + Enterprise search | 低：排序用内部专用训练集；有反馈与 Knowledge verification 设置，**无公开指标** |
| **Dust.tt** | Data sources：**Connections / Folders / Websites**；对象 **Documents / Chunks** | 无图谱层；检索被拆成四工具 **Search / Include data / Table queries / Extract data** | "Discover Knowledge **follows the user's permissions** and the **spaces** available to the agent"；label 双向过滤（must-have / must-not-have + 会话内动态过滤） | Discover Knowledge / Skills / Tools；**Agent Memory / Skills / Pods / Context Compaction** | 低：只有 thumbs up/down 反馈 API |
| **Microsoft 365 Copilot** | Copilot connectors：**Synced**（入 Graph 并索引）vs **Federated（MCP）**（**不索引**，语义索引 Not applicable） | **Semantic index**：tenant-level（SharePoint 文本文件）+ user-level（邮箱/工作集），**物理分置** | **逐 item 必填 ACL 数组**（`accessType`: grant/deny；`type`: user/group/everyone/**everyoneExceptGuests**/externalGroup）；**ACL 变更仅 full crawl 生效、最长 24h** | declarative agents / Copilot Studio agents | 低：无公开方法；只有 **Index browser** 的 item 级运维校验 |
| **Notion AI** | **AI Connectors**（Slack/Drive/Jira/Gmail/Teams/SharePoint/GitHub/Linear/Outlook…） | 托管向量库（官方点名 **Turbopuffer**）+ Agent 的 **memory system（用 Notion pages 与 databases 承载）** | "honor existing permissions"；第三方按 **permissions mapping between each connected app and Notion** 摄入；Agent **"acts as you"**；同期上线 **database row-level access** | Enterprise Search / Agents / Custom Agents / MCP（可写回） | 低：只有能力边界声明 |
| **Atlassian Rovo** | Teamwork Graph Connectors（100 开箱；Forge 自建）；**Smart Link 型 vs 内容索引型**两档 | **Teamwork Graph** = "Atlassian Cloud Platform's **data intelligence layer**"（**150 billion objects and relationship**） | **"last-mile checks"**（交付前最终校验）；自建连接器 "Data enters the graph with its **access controls intact**" | Rovo Search / Chat / Agents / Studio；**CLI（300+ commands）+ MCP，可写回** | 中低：有数字（44% 更准 / 48% 更少 token、60%），**方法未公开、不可复现** |
| **Salesforce Agentforce** | **Agentforce Data Libraries (ADL)**：web / documents / text fields → 可搜索信息；+ Data 360 / MuleSoft | ADL（非结构化）+ Prompt Builder（CRM merge fields）+ **Atlas Reasoning Engine** + Model Library / BYOLLM | **未找到公开资料**（仅有泛化 "least privileged access / core access controls"） | **Agent Script**（显式把可靠逻辑从 LLM 解释中拿出）/ subagents / actions | **中**：三套测试入口（UI-CSV / CLI-YAML / API-XML）+ 自定义评测（JSONPath 断言字符串/数值/延迟） |
| **Sierra** | 40+ 集成 + Ghostwriter（SOP/transcript/白板照/录音）+ Expert Answers | **8 类 context block**（Journey / Tool / Rule-Policy / Workflow / **Knowledge** / Memory / Glossary / Response phrasing）+ progressive disclosure + Conditions | **运行期工具可见性裁剪**：四层 Content / Rules / **Supervisors** / **Deterministic guards**（"preventing account-modification tools from even being available… until the customer has been authenticated"） | Agent Studio / Agent SDK / Agent OS；release = **含知识快照的不可变版本** | **高**：τ-bench→τ³（τ-Knowledge 698 文档/21 类目/~195K tokens）→hyper-τ；**每日 golden articles + recall/precision/nDCG**；Simulations（agent/user/**judge**）可接 CI/CD |
| **Decagon** | 连接 help center / internal docs / ticketing；**Knowledge base / Snippets / Suggestions** | **AOP**（自然语言**编译成受验证工作流**）；**user memory**（Conversational memory + 结构化 metadata，"without creating a duplicative data layer"） | **未找到公开资料**；最接近的是 **JIT 短时 JWT（minimal privilege, discarded after each session）**+ RBAC + ZDR + PII redaction | AOP / Duet / Watchtower / Simulations | **中高**：**DuetBench**（首个评 agent **自改进**的客服 benchmark，对照内部 Decagon Masters 人类认证） |
| **Harvey** | DMS 连接器（iManage/SharePoint/GDrive）folder upload + **one-way sync**；公共源由 **The Data Factory**（6→60+ 法域、20→400+ 源，策展域名白名单 + attorney 逐源过审） | **Assistant / Knowledge Sources / Vault / Workflows** + Firm Knowledge / Spaces / Memory / Playbooks | **最完整**：**"The agent has the same permissions as the user"**（查询期裁剪 + 逐文件审计）；伦理墙在 **retrieval / context / output** 三层强制；**matter 是硬安全边界而非 metadata tag**；**fail closed**；权限源为 **Intapp/iManage**，Harvey **never creates, modifies, or deletes walls** | Agents / Agent Builder / Workflows / Playbooks | **高（构造最严谨）**：**BigLaw Bench** 源自 **time entry**；**answer score + source score 双分且独立**；BLB: Retrieval 用 **recall@固定 token 阈值**；BLB: Research 公开 "**<60% 完成度即无用**" 阈值 |
| **Abridge** | 医学证据源（**Content Sources**，含 AHA 授权内容）+ 患者 EHR 史 + 机构指南 + 医生偏好 + 对话 | **Abridge Contextual Reasoning Engine** 四子层：**EHR CONTEXT / PREDICTED PROBLEMS / ORDERS / CODING**（CODING 由 **Linked Evidence** 驱动，输出可审计、可回指源数据） | 仅治理性表述：**Clinician-in-the-loop** + "Queries run entirely inside Abridge's architecture. PHI never leaves it and is never used for training"；**检索期/索引期机制未找到公开资料** | Clinicians / Revenue Cycle / Nursing；CDS / Care Signals | **高**：**when/what/how 框架**（离线→灰度→在线）；safety/accuracy/fairness/usability 四维；**内在 vs 结果双轴**；盲法头对头 + 内部 benchmark；**LLM judge 须先与医生标注对齐**；confabulation 检测 **97% vs GPT-4o 82%**（50,000+ 训练样本、1,000+ 小时人工验证）；CDS Safety **99.5% / 1,000+ cases / 1,000+ rubrics** |
| **Dragon Copilot**（原 Nuance DAX） | **Optional service data**：**FHIR/HL7/EHR resources for Patient, Practitioner, Encounter**；外部知识由 **Information Assist** 经 **Azure Healthcare Agent Service** 编排到 approved/vetted 源 | **Dictation vs Ambient recording** → **Dragon standard payload**(JSON) + **Resource** + **Ontology**（**LOINC / SNOMED-CT**；`Context` 字段清单见 8d 的 `[子代理未复核]` 标注）+ 资源间链接（order→condition）；**Clinical Safeguards engine** | **检索期按患者级隐私标记裁剪**：客户负责配置访问控制（仅"有既定治疗关系的医护"可访问）；**Context Grounding 明确"External sources and data from other sessions are not allowed"**；**Epic 诊断检索仅对未被增强隐私访问控制限制的记录生效**（FAQ："restricted records → No"）；**索引期 ACL 机制未找到** | Information Assist（外部知识问答）/ note generation / Flowsheet capture | **中高（方法学公开）**：两级测试（平台服务 **2–5k queries** → 用户应用 **50–100 queries**）；RAG 评估三判据 **Groundedness and fabrications / Answer relevance / Evidence relevance**；红队在 **credible + customer + harmful adversarial** 三种源上分别做 UPIA/XPIA 注入测试；**诚实声明"customer sources 上不保证 grounding，须先自评"**；**未给准确率数字** |

**这张表给出的三个结论（`[推断]`，但均有上表事实支撑）**：

1. **连接器层、索引层、行为层已经商品化**——八家几乎人人都有，术语不同但结构同构。**真正分化的是"权限进检索的时点"与"评测的公开度"这两列**。
2. **权限时点存在一条清晰的光谱**：Microsoft 的"仅 full crawl 生效、最长 24h"是最粗的一档 → Glean 的"索引期快照 + Live/Hybrid 按需实时"是折中档 → Sierra 的"运行期工具可见性裁剪"、Atlassian 的"last-mile checks"、Harvey 的"查询期继承用户权限 + 三层强制"、**Dragon Copilot 的"按患者级隐私标记决定是否检索 + 禁止跨 session/外部源"** 是最细的一档。**细的一端几乎都出现在"内容本身带强合规属性"的场景（客服身份认证、法律伦理墙、患者隐私）**；而**最粗的一端（Microsoft）恰恰是覆盖面最广、语料最杂的一档**——`[推断]` 权限粒度与语料异构度负相关，因为每多接一种源就多一套难以统一建模的权限语义。
3. **公开的评测方法学与"是否面向强监管行业"正相关**：Glean（企业通用但客户含大量受监管行业）、Sierra（客服+金融）、Harvey（法律）三家的 eval 公开度显著高于 Notion / Sana / Dust / Microsoft / Salesforce。**Microsoft 与 Salesforce 反而最不公开方法学**——这与其"靠认证与合同而非 benchmark 取信"的采购路径一致。`[推断]`

---

### [1] Glean（企业搜索 + Assistant + Agents）

- **它解决什么**：把企业内 100+ 系统（Slack/GDrive/Jira/Salesforce…）的语料统一成"权限感知的一份上下文"，让搜索、Chat(RAG)、Assistant、Agents 共用同一底座。目标用户：知识工作者 + IT/AI 平台管理员。
- **知识库分层（原文术语，已打开）**：
  - 连接器层：**Connectors**，分 **Native connectors / Web history connectors / Push API connectors / Partner connectors**（[docs.glean.com/connectors/about](https://docs.glean.com/connectors/about)）。
  - 索引层：**search index**（powers fast retrieval, faceting, ranking）。
  - 图谱层：**Knowledge Graph**，三根支柱原文为 **Content / People / Activity**；另有新层 **personal graph**，与前者合称 **system of context**（[docs.glean.com/security/knowledge-graph](https://docs.glean.com/security/knowledge-graph)；[glean.com/blog/knowledge-graph-agentic-engine](https://www.glean.com/blog/knowledge-graph-agentic-engine)）。
  - 取数模式层（很有参考价值的三分法）：**Indexed access / Live access / Hybrid access**（[docs.glean.com/connectors/connectors-power-glean](https://docs.glean.com/connectors/connectors-power-glean)）。
  - 行为层：**Assistant / Agents / Tools**；2026 年新增 **Skills**（[glean.com/blog](https://www.glean.com/blog) 列表页可见 "Glean Skills know how your business works"，该列表页已打开，单篇未打开）。
- **语料治理（已打开）**：
  - 接入：native connector 直调源 API；无 connector 时用浏览器扩展的 **web history connector**（结果仅对该用户可见、组织不可见）；受限环境用 **Push API**（Indexing API 推送）；伙伴连接器同样走 Indexing API（[connectors/about](https://docs.glean.com/connectors/about)）。
  - 爬取类型（原文五个）：**Full content crawl / Incremental content crawl / Activity crawl / Identity crawl / People data**；**Activity crawl** 原文明确包含 "content additions, updates, deletions, and **permission modifications**"（[crawling-types](https://docs.glean.com/connectors/crawling-types)）。
  - 刷新频率：逐连接器公开默认值。例：GitHub/GitLab webhook 变更 5 分钟内；Slack webhook 近实时；Confluence 新 DC 版本 5 分钟、旧版本 1 小时；Salesforce 增量 10m/全量 28d；Gmail 活动驱动、全量约 28–30 天；Website 默认 28 天（[crawling-refresh-rates](https://docs.glean.com/connectors/crawling-refresh-rates)）。
  - 权威源认定：在**评测**语境中出现 **canonical document**（"the most authoritative and comprehensive source of information"），见 [AI Evaluator](https://www.glean.com/blog/glean-ai-evaluator)。语料侧未见"权威源"的产品机制。
  - 数据驻留：连接器取到的数据进入**该租户隔离的 Glean tenant**，传输加密、落盘后租户内静态加密；支持 **customer-hosted deployment（GCP / AWS）**（[connectors/about](https://docs.glean.com/connectors/about)；[docs.glean.com/security](https://docs.glean.com/security)）。
- **权限/ACL 进检索（已打开）**：官方原文是 **"mirror permissions"**——"They also fetch the **permissions map** from each source, ensuring search results strictly adhere to the access permissions set in the source application"；indexed 模式下原文写明检索时使用的是 **"the permission snapshot that was mirrored during crawling and incremental updates"**（即索引期快照）；live/hybrid 模式则在请求时调源系统。检索返回体里带 **`"visibility": "SPECIFIC_PEOPLE_AND_GROUPS"`** 字段（[query flow 示例](https://docs.glean.com/security/architecture/data-flow/query)）。图谱侧原文："The entire graph in Glean is designed with fine-grain access controls so employees can only see the data that is already shared with them in the source system"（[knowledge-graph blog](https://www.glean.com/blog/knowledge-graph-agentic-engine)）。**未找到**官方对"检索期是否再做一次上游二次校验"的明确描述（打开结果条目的链接会跳回源系统，官方说"may enforce access again at click time"，但这句针对的是**用户点击**而非检索管线）。
- **评测（已打开，本批产品中公开度最高）**：**AI Evaluator**，LLM-as-judge，在**每个客户租户内**评测而不外泄数据。检索侧指标：**Context relevance rate**、**Context recall rate**（原文把 canonical document 被召回的比例作为 context recall 定义）；生成侧：**Answer relevance**（二分类）、**Answer completeness**（complete/incomplete/no-answer 三档）、**Groundedness**（先拆 claims，再逐条标 inferable/generic/ungrounded，得分=有据 claims/总 claims）。方法学：单答案评分（避免位置偏见）、分类标签优先于数值、Chain-of-Thought + few-shot、模型集成（"LLM jury"）抑制自我增强偏见；对标 **RAGAS**。量化结果：内部数据集上**人类标注者之间一致率仅 79%**（被当作自动评测上限），**AI Evaluator 与人类一致率 74%**；把 Evaluator 信号加入用户留存模型使预测准确率**提升 18.8%**，其中"No Answers"与低 groundedness 是流失强预测因子。评测集构造来源：①用户不满意后转去搜索改写的 session；②从语料离线挖掘的 QA 对；并据此造出 **"hard" evaluation sets**。检索侧传统指标另有 **NDCG@10** 与 **R@100**（[vector search 博客](https://www.glean.com/blog/unlocking-the-power-of-vector-search-in-enterprise)）。另有"用点击类指标评搜索、用 AI Evaluator 评助理"的**离线/在线分工**陈述。
- **关键设计决策**：
  1. **把"权限快照 + 新鲜度"显式做成三档取数模式（Indexed/Live/Hybrid）**，而不是承诺一个统一的实时语义——把一致性成本转移给可配置策略。
  2. **Activity crawl 单独成一种爬取类型并显式覆盖权限变更**——把 ACL 变更当作与内容变更同级的被追踪事件，而不是靠全量重爬兜底。
  3. **逐连接器公布刷新频率表 + 各自 webhook/轮询策略**，把"新鲜度"变成可被管理员审计的数字（同时承认"这些是默认值不是保证"）。
  4. **评测指标在客户租户内计算**（AI Evaluator），用"不外泄数据"换取"能在真实私有语料上评测"——这是企业 RAG 评测最难的一步。
  5. **[推断]** 用 "hard eval sets"（按最差指标切片反向造集）驱动迭代，等于把 eval 当成缺陷定位工具而非仅打分工具。
- **出处**：
  - 已打开：[docs.glean.com/connectors/about](https://docs.glean.com/connectors/about) · [crawling-types](https://docs.glean.com/connectors/crawling-types) · [crawling-refresh-rates](https://docs.glean.com/connectors/crawling-refresh-rates) · [connectors-power-glean](https://docs.glean.com/connectors/connectors-power-glean) · [security/knowledge-graph](https://docs.glean.com/security/knowledge-graph) · [security/architecture/data-flow/query](https://docs.glean.com/security/architecture/data-flow/query) · [docs.glean.com/security](https://docs.glean.com/security) · [blog/knowledge-graph-agentic-engine](https://www.glean.com/blog/knowledge-graph-agentic-engine) · [blog/glean-ai-evaluator](https://www.glean.com/blog/glean-ai-evaluator) · [blog/unlocking-the-power-of-vector-search-in-enterprise](https://www.glean.com/blog/unlocking-the-power-of-vector-search-in-enterprise) · [glean.com/blog（目录页）](https://www.glean.com/blog)
  - `[仅搜索摘要，未打开]`：[blog/enterprise-search-evaluation-2026](https://www.glean.com/blog/enterprise-search-evaluation-2026) · [blog/2025-search-tool-benchmark-key-metrics-to-evaluate-accuracy-and-speed](https://www.glean.com/blog/2025-search-tool-benchmark-key-metrics-to-evaluate-accuracy-and-speed) · [perspectives/how-to-debug-enterprise-search-relevancy-issues](https://www.glean.com/perspectives/how-to-debug-enterprise-search-relevancy-issues)
- **证据强度**：官方文档（架构/权限/治理/刷新频率）+ 官方工程博客（评测方法）。**权限是否二次校验**一项证据不足。
- **事实 vs 推断**：以上"mirror permissions / permission snapshot / 三档取数模式 / 五个 crawl 类型 / 刷新频率数值 / AI Evaluator 全部指标与 79%·74%·18.8% / NDCG@10 与 R@100 / canonical document"均为**原文事实**。"hard eval sets 被当缺陷定位工具""应把权限快照当作显式可配置一致性等级"为 `[推断]`。

---

### [2] Sana Labs（Sana AI / Sana Agents）

- **它解决什么**：把公司自有文档 + 会议 + 100+ SaaS 应用统一成"可问答 + 可执行 agent"的入口，主打知识检索与 agent 自动化。目标用户：中大型企业全员（金融/咨询/律所/PE/工业）。
- **知识库分层（原文术语，已打开）**：官方分为 **Sana Agents** 与 **Enterprise search** 两条能力线；接入侧原文称 **integrations / connectors**，并强调"**unifies your company's data**"与 **real-time indexing**；权限侧原文给出三种入法：**(i) direct upload、(ii) private integration、(iii) shared integration**（[products/sana](https://sanalabs.com/products/sana/)；[products/sana/enterprise-search](https://sanalabs.com/products/sana/enterprise-search)；[products/sana/security](https://sanalabs.com/products/sana/security)）。**未找到**官方对"图谱层/记忆层"的分层命名（无公开的 "knowledge graph" 层术语）。
- **语料治理（已打开）**：接入=integrations（100+ 应用，含 GDrive/Confluence/Jira/ServiceNow/Salesforce/Teams/SharePoint/Workday/Slack/Dropbox 等）；上传也可以。刷新：原文产品页称 **"Real-time indexing gives you access to the latest and greatest company information"**（无逐连接器频率表）。存储：数据"indexed and stored on our cloud instance"，**single tenant architecture，租户间不共享数据库**；静态 AES-256、传输 TLS 1.2+；可部署在客户自有云（"can be deployed on your cloud infrastructure"）。去重/权威源：**未找到公开资料**。驻留：有 **Regional deploys**（产品页安全清单列出）。
- **权限/ACL 进检索（已打开）**：原文 FAQ "Can every user see every document?" 给出三分法：
  - direct upload → 在 Sana 内做**逐文档访问管理或 collections**；
  - **private integration → 每个用户自行认证，"can see results only from the scope they have access to"（原文举例：用户看到的 Google Drive 结果与他直接登录 GDrive 能看到的相同）**；
  - **shared integration → 由 admin 控制哪些文档对所有 collection/workspace 用户可见**。
  另有 SSO/SCIM 同步用户角色与权限、"Users can only access data they are authorized for"。**未找到**索引期 ACL 快照 vs 检索期校验的机制级说明。
- **评测（已打开，部分）**：搜索排序侧原文："We use a **dedicated training set of internal data** to manually and automatically train our **ranking algorithm and query rewrite**"；明确"customer data 不用于训练第三方 LLM"，且**排名训练只用自己的内部数据集**。另有用户反馈产品化信号：**user-generated feedback on responses**、**Knowledge verification settings**、**Analytics dashboard for monitoring usage and responses**。**未找到**公开的指标定义、黄金集构造、人工评审流程、离线/在线评测方法。
- **关键设计决策**：
  1. **把"文档可见性"建模为三种入法（upload / private integration / shared integration）而不是单一 ACL 模型**——用接入路径决定权限语义，降低对源系统 ACL 建模完整性的依赖。
  2. **private integration 走"每用户自认证"**，即检索期以用户身份向源系统取数（等价于 Glean 的 live access）——用延迟换权限正确性。
  3. **排序模型只用内部数据训练**，把"客户语料"严格排除在训练回路之外——这是企业 AI 采购里最常见的合规红线。
  4. **single-tenant 隔离 + 可选客户自有云**，把多租户风险从"逻辑隔离"上移到"物理/部署隔离"。
- **出处**（均已打开）：[sanalabs.com/products/sana/](https://sanalabs.com/products/sana/) · [products/sana/security](https://sanalabs.com/products/sana/security) · [products/sana/enterprise-search](https://sanalabs.com/products/sana/enterprise-search)
- **证据强度**：官方产品页 + 官方安全 FAQ。**缺**工程博客级深度；分层命名、去重、权威源、逐连接器刷新频率、评测方法均未公开。
- **事实 vs 推断**：三种入法、private/shared integration 权限语义、single-tenant、AES-256/TLS1.2+、内部训练集、ZDR、Regional deploys 均为**原文事实**。"private integration ≈ Glean live access"、"按接入路径建模权限是在回避源 ACL 建模"为 `[推断]`。

---

### [3] Dust.tt

- **它解决什么**：把公司知识 + 工具接进来，让团队用同一套系统**创建、共享、运行 agent**（"Multiplayer AI for human-agent collaboration"）。目标用户：中小到中大型企业的业务/工程团队自建 agent。
- **知识库分层（原文术语，已打开，非常清晰）**：
  - **Data sources** 分三类：**Connections / Folders / Websites**（[knowledge/search-data-sources](https://docs.dust.tt/docs/user-documentation/agents/knowledge/search-data-sources.md)）。
  - 数据对象分 **Documents** 与 **Chunks**（[developer-platform/core-concepts/chunks-and-documents](https://docs.dust.tt/docs/developer-platform/core-concepts/chunks-and-documents)）。
  - 检索/知识能力被显式拆成**四种工具**：**Search（语义搜索 RAG） / Include data（倒序填窗口） / Table queries（转 SQL） / Extract data（单次跑最多 500k tokens 抽结构化）**（[agents/knowledge/*](https://docs.dust.tt/llms.txt) 目录 + 已打开 understanding-rag）。
  - 能力层：**Discover Knowledge / Discover Skills / Discover Tools**（"Give agents access to company documents and data warehouse analysis"）。
  - 记忆层：**Agent Memory** 工具、**Skills**（"Reusable packages of instructions, knowledge, and tools"）、**Pods**（人类+agent 共享工作区）、**Context Compaction**。
- **语料治理（已打开）**：接入=Connections（70+/100+ 连接器）、Folders、Websites、Push API（Indexing API 的 upsert document/rows）、**Client-side MCP**、以及 beta 的按源导入（Jira/Salesforce/Hubspot/Guru/Linear/Dropbox/Front）。刷新：有 FAQ **"Why isn't my recently updated document showing in agent responses?"**（存在该问题条目，正文未打开）。**分层过滤是 Dust 的亮点**：文档 label 支持 **must-have / must-not-have** 两套语义（"Documents must have at least one of the must-have labels to be included… Documents with any must-not-have labels will be excluded"），并支持 **in-conversation filtering（按会话上下文动态过滤，需精确 tag 匹配）**。去重/权威源/驻留：**未找到公开资料**（有 FAQ "How does Dust handle user data?"，正文未打开）。
- **权限/ACL 进检索（已打开，但仅到表述层）**：Discover Knowledge 原文："**Discover Knowledge follows the user's permissions and the spaces available to the agent.**" Permissions 由 **Spaces** 承载（[admins/spaces-management](https://docs.dust.tt/docs/user-documentation/admins/spaces-management)、[admin-governance/access-controls-and-permissions](https://docs.dust.tt/docs/user-documentation/admins/admin-governance/access-controls-and-permissions) —— 两页在 llms.txt 中确认存在，**正文未打开**）。**未找到**索引期 ACL 快照或检索期二次校验的机制说明。
- **评测（已打开，弱）**：只有**产品化反馈回路**：`Submit feedback for a specific message (thumbs up/down)`、`Get feedbacks for a conversation`（[api-reference/feedbacks/*](https://docs.dust.tt/llms.txt)），以及官方建议 "**try different options to evaluate which one suits you best**"（让用户自己 A/B）。另有 FAQ "Does the Dust agent give accurate and safe responses?"（存在，正文未打开）。**未找到**官方指标、黄金集、人工评审流程、离线评测。
- **关键设计决策**：
  1. **把"知识访问"拆成 Search / Include data / Table queries / Extract data 四个工具**，并在文档里明确各自适用与失效边界（RAG 不做计数、不做全覆盖）——把检索能力的选择权交给 agent 与构建者，而不是一个万能 retriever。
  2. **label 的双向语义（must-have / must-not-have）+ 会话内动态过滤**，把"排除废弃内容"做成检索时的一等机制（例如排除 `deprecated`），而非仅靠源系统目录结构。
  3. **Advanced search mode 给 agent 文件系统级能力**（列目录、按路径读文件），与语义搜索并存，并如实承认"generally requires more tool calls, hence more induced latency"。
  4. **官方明确警告不要把全部数据源挂到一个 agent**（"agents that are plugged to a constrained number of data will usually perform better"）——把召回范围当超参调。
  5. **[推断]** Skills 被定义为"instructions + knowledge + tools 的可复用包"，是把行为层与知识层**打包分发**的最小单元。
- **出处**（均已打开）：[docs.dust.tt/llms.txt](https://docs.dust.tt/llms.txt) · [knowledge/search-data-sources.md](https://docs.dust.tt/docs/user-documentation/agents/knowledge/search-data-sources.md) · [discover-knowledge.md](https://docs.dust.tt/docs/user-documentation/agents/discover-knowledge.md) · [understanding-rag.md](https://docs.dust.tt/docs/user-documentation/agents/llm-best-practices/understanding-rag.md) · [use-cases-and-guides/knowledge](https://docs.dust.tt/docs/user-documentation/getting-started/use-cases-and-guides/knowledge)
- **证据强度**：官方文档（分层与检索工具最强、权限与评测最弱）。
- **事实 vs 推断**：三类 data source、documents/chunks、四工具、must/must-not label、advanced search mode、Discover Knowledge 的权限表述均为**原文事实**。"Skills 是行为+知识打包分发单元"为 `[推断]`。

---

### [4] Microsoft 365 Copilot（Graph 语义索引 + Copilot 连接器 + ACL 裁剪）

- **它解决什么**：把租户内（M365）与租户外（第三方/LOB）的内容统一进 Microsoft Graph，让 Copilot/搜索/Agent 在同一权限边界内做 grounding。目标用户：M365 企业租户的全体员工 + IT 管理员。
- **知识库分层（原文术语，已打开）**：
  - **Semantic index**：由 Microsoft Graph 内容生成，原文定义 **"a semantic index is created for every subscription at the tenant and user level"**；**tenant-level index** 来自 text-based SharePoint Online 文件，**user-level index** 覆盖邮箱与用户工作集；以 **vectorized indices**（多维空间中的向量）承载。原文明确二者**存储位置不同**：user-level 存在用户邮箱所在处，tenant-level 存在"isolated and protected customer's tenant container"（[semantic-index-for-copilot](https://learn.microsoft.com/en-us/microsoftsearch/semantic-index-for-copilot)）。
  - **Copilot connectors** 两类：**Synced connectors**（ingest & index into Microsoft Graph）与 **Federated connectors (MCP-based)**（**不做语义索引**，查询时实时取）。Synced 又分 **Tenant configuration / Self-serve configuration**（后者按用户维度，用户自认证、内容 scoped to that individual user，断连即删除）（[extensibility/overview-copilot-connector](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/overview-copilot-connector)；[connectors/overview](https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/overview)）。
  - 行为层：**declarative agents / Copilot Studio agents**，连接器是它们的知识来源，admins 控制每个 agent 能用哪些 connector/action。
- **语料治理（已打开，细节最硬）**：
  - 索引项结构：**"Each item includes content, metadata (like title and URL), and an access control list (ACL) that enforces permissions."**
  - 索引更新节奏：新建用户文档"near real-time in the user's mailbox"；**新增到 SharePoint 且通过站点继承被 ≥2 人访问的文档按天索引**；已索引文档**更新即时索引**。
  - 连接器同步：**Continuous sync**，连接器周期性检查变更，admins 可配频率并触发 full crawl。**ACL 的更新规则是硬约束**（见下）。
  - 去重/权威源：**未找到**统一机制；people data 连接器明确"keeping the original data authoritative in its source system"。
  - 驻留：索引数据留在租户；**EUDB 客户索引存放在 EU/EFTA 数据中心**，其他客户可能在租户区域或美国；multi-geo 尊重各地边界。支持 **BYOK（Microsoft Purview Customer Key）**。
  - 排除：管理员可对敏感站点（payroll/HR/financial）关闭 "Allow this site to appear in search results" 以**同时**排除出 Microsoft Search 与语义索引；**原文明确没有"只排除语义索引不排除搜索"的选项**；有 DLP 时走 Purview DLP。
  - 训练：**"Prompts, responses, and data accessed through semantic indexing aren't used to train foundation LLMs"**。
- **权限/ACL 进检索（已打开，本批最明确的一条"索引期快照"证据）**：
  - 机制：语义索引**只在用户本已有权访问的内容上工作**；grounding 阶段"continue to honor the user identity-based access boundary"；连接器新增项 "**Permission-based filtering** - Search and Copilot only show items to users who have access in the source system"。Sensitivity label **包含在 search trimming 里**（"supported for filtering and application-side rules used for visual marking and access restrictions"）。
  - **时延与生效窗口（关键硬事实）**：**"Changes to user or group permissions (ACLs) might take up to 24 hours to reflect"**；**"Permissions updates occur during a full crawl, not an incremental crawl"**；若源系统权限在最近一次 full crawl 后变化，**必须触发一次新的 full crawl** 才能更新索引（[connectors/indexed-content](https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/indexed-content)）。
  - 可审计性：**Index browser** 可查单个 item 的 **Properties / Permissions（allow/deny、Allow everyone vs Only people with access）/ Check user access**（按用户验证其是否可见，含"该用户属于某 deny 组则整体被拒"的判定）。ACL 用户映射失败会显式报错。
  - 连接器默认范围：**"Deployed connectors are tenant-wide unless external item security is restricted."**（[extensibility/overview-copilot-connector](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/overview-copilot-connector)）
  - 反过度共享：原文建议"inheriting exclusion lists for SharePoint Online sites and **performing access control checks in real time**"——即官方承认需要检索期实时校验作为补充，但该句出现在"reduce oversharing"建议里，**不是**对语义索引自身管线的描述。
  - **ACL 的精确数据模型（已打开，可直接引用）**：索引项 `externalItem` 的 `acl` 是 **"An array of access control entries. Each entry specifies the access granted to a user or group. **Required**."**；单条 ACE（`acl` 资源）字段为：
    - `accessType`：`grant` / `deny` / `unknownFutureValue`
    - `type`（身份类型）：`user` / `group` / `everyone` / **`everyoneExceptGuests`** / `externalGroup` / `unknownFutureValue`
    - `value`：Entra 身份填 object id；`externalGroup` 填外部组 ID
    （[externalconnectors-acl](https://learn.microsoft.com/en-us/graph/api/resources/externalconnectors-acl?view=graph-rest-1.0)；[externalconnectors-externalitem](https://learn.microsoft.com/en-us/graph/api/resources/externalconnectors-externalitem?view=graph-rest-1.0)）
    → 关键含义：**ACL 是逐 item 必填的数组，且显式支持 deny 与"除来宾外所有人"两种非穷举身份**——即权限裁剪不是"过滤掉无权项"这么简单，deny 条目会**撤销**用户经由 group 获得的权限（索引浏览器原文："If the user is denied access to any of these groups, their overall permission to view the item is revoked"）。
  - **元数据如何影响可检索性（对"语料治理"极为关键）**：schema 属性带五个正交开关 —— **Searchable**（进全文索引）/ **Queryable**（可被 KQL 过滤，支持 `*` 前缀匹配，**不支持后缀匹配**）/ **Retrievable**（可在结果中返回）/ **Refinable**（可作为搜索页筛选器，**仅 string/numeric**）/ **isExactMatchRequired**（全串精确索引，**仅可用于非 searchable 属性**，适用于 GUID 类标识）。原文规则：**Refinable 与 Searchable 互斥**；**修改 search 能力必须重新摄取（reingestion）**；**新增属性可不必重灌但建议重灌**；**属性必须标记 Retrievable 才能映射 semantic label**；每个 label 只能映射到**恰好一个**属性。**语义标签（semantic labels）** 是 Microsoft 发布的固定词表（title / url / createdBy / lastModifiedBy / authors / createdDateTime / lastModifiedDateTime / fileName / fileExtension / iconUrl / containerName / containerUrl），**官方明确"Semantic labels 只用于过滤，不影响语义索引"**；`title` 标签影响最大（决定该连接能否进入 result cluster experience）；另可设 **rank hints**（仅适用于 searchable 且未映射 label 的文本属性），在 admin portal 的 **Search and intelligence → Customization → Relevance tuning → Configure rank hints** 调权重。内置 `content` 属性无需在 schema 中声明、**直接被语义索引**并用于生成 dynamic snippets（[connecting-external-content-manage-schema](https://learn.microsoft.com/en-us/graph/connecting-external-content-manage-schema)）。
- **评测（已打开，弱）**：**未找到**公开的评测方法/指标/黄金集。已打开页面里只有**可运维的验证手段**：Index browser 的 item 级索引状态校验（含 Partially indexed / Deny all / allowed for everyone 三种状态诊断）、索引状态与 last refresh time、错误报告。语义索引页面**明确列出它不擅长的查询类型**（无主题关键词的查询如 "find bugs assigned to"、多参数查询、计数类查询），这是**能力边界的公开声明**，可当"已知失效集"用，但不是 eval 方法。
- **关键设计决策**：
  1. **ACL 变更只在 full crawl 时生效且最长 24h**——用"索引期快照 + 明确的 SLO 缺口"换取索引规模与成本可控，并要求管理员在权限变更后主动触发 full crawl。
  2. **提供 MCP 联邦连接器作为"不落索引"通道**——把"敏感/动态/强合规数据"从索引治理里整体移出（代价：**没有语义索引**，检索退化为工具调用）。
  3. **把"排除索引"与"排除搜索"绑成同一个开关**——减少管理员误配置面，同时坦诚说明无法只排除其一。
  4. **为每个 item 保留可查询的 ACL 视图 + Check user access 工具**——把权限正确性从"信任"变成"可抽查"。
  5. **[推断]** tenant-level 与 user-level 索引物理分置（分别存租户容器与用户邮箱）是为了让个人工作集的新鲜度与隐私边界不受租户索引节奏拖累。
  6. **把 schema 做成"能力开关 + 固定语义词表"而非自由字段**：Searchable / Queryable / Retrievable / Refinable / isExactMatchRequired 五个正交开关（且 Refinable 与 Searchable 互斥），加上 Microsoft 自有的 semantic labels 词表与 rank hints——**用受限的字段契约换取跨连接器可比较的检索质量**，代价是改 search 能力必须重灌。
  7. **ACL 逐 item 必填且显式支持 deny**：deny 可撤销经 group 继承来的权限，配合索引浏览器的 "Check user access" 形成"可被抽查"的权限证据链。**[推断]** 这也意味着任何自定义连接器都必须自行完成源系统 ACL → Entra 身份的映射，映射失败会直接表现为用户看不到内容（官方文档专门列了 user mapping 失败的排查项）。
- **出处**（均已打开）：
  - [microsoftsearch/semantic-index-for-copilot](https://learn.microsoft.com/en-us/microsoftsearch/semantic-index-for-copilot)
  - [m365/copilot/extensibility/overview-copilot-connector](https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/overview-copilot-connector)
  - [m365/copilot/connectors/overview](https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/overview)
  - [m365/copilot/connectors/indexed-content](https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/indexed-content)
  - [graph/connecting-external-content-manage-schema](https://learn.microsoft.com/en-us/graph/connecting-external-content-manage-schema)
  - [graph/api/resources/externalconnectors-acl](https://learn.microsoft.com/en-us/graph/api/resources/externalconnectors-acl?view=graph-rest-1.0)
  - [graph/api/resources/externalconnectors-externalitem](https://learn.microsoft.com/en-us/graph/api/resources/externalconnectors-externalitem?view=graph-rest-1.0)
- **证据强度**：官方文档（本批最高；ACL 数据模型、schema 开关、驻留与训练政策均可逐条引用）。
- **事实 vs 推断**：ACL 24h/仅 full crawl 生效、tenant vs user level 索引及存储位置、EUDB、BYOK、连接器默认 tenant-wide 除非限制 item security、MCP 联邦连接器不支持语义索引、item 级 ACL 含 grant/deny 与 everyoneExceptGuests、deny 可撤销 group 继承权限、sensitivity label 参与 search trimming、schema 五个开关及 Refinable⊥Searchable、改 search 能力需重灌、semantic labels 不参与语义索引、内置 content 属性被语义索引、不用于训练 foundation LLM——**全部为原文事实**。"物理分置是为了新鲜度与隐私解耦""自定义连接器必须自建 ACL→Entra 映射"为 `[推断]`。

---

### [5] Notion AI（Notion 3.0 Agents / Enterprise Search / AI Connectors）

- **它解决什么**：让 Notion 工作区 + 已连接第三方应用成为"答案与执行"的同一入口：Enterprise Search 出答案、Agent 出动作。目标用户：Notion 的 Business/Enterprise 团队。
- **知识库分层（原文术语，已打开）**：
  - **Notion AI Connectors**（第三方语料层）：Slack / Google Drive / Jira / Gmail / Microsoft Teams / SharePoint & OneDrive / GitHub / Outlook / Linear / Google Calendar / Notion Mail / Notion Calendar。
  - **Enterprise Search**：检索面 = "your workspace + your connected apps + the web"，**scope 可逐源收窄**（可只搜 workspace，甚至收窄到某 page/teamspace；可分别 toggle Web search 与 Apps and integrations）。
  - **Agent（3.0）**：原文 "state-of-the-art memory system (**using Notion pages and databases**)" + **instructions page** 做个性化；**Custom Agents** 可按 schedule/trigger 自主运行。
  - **MCP**：第一方 MCP 集成，可读 workspace + 已连接应用，**并可写回 Notion**。
- **语料治理（已打开）**：
  - 接入：Notion AI Connectors（管理员在 Settings → Notion AI 统一管理）；连接器**安装在 workspace 级**，"unrelated to the workspace owner that installed it"；owner 离职不影响，仅显式卸载/断连才停（Google Drive 例外，会自动找另一位有权限的 owner 重建）。
  - 时间范围：**一般只能访问 setup date 往前一年**（例：2024-06-01 连接 → 可访问 2023-06-01 起）。
  - 刷新/首次灌入：**首次摄取最长 72 小时**；**新内容最长 3 小时**才可被搜到（大数据量更久）。
  - 断连清理：内容变为不可搜（部分连接器最长 1 小时），**数据在断连后 1 天内删除**。
  - 训练：**不用于训练 Notion 模型，也不允许子处理商用客户数据训练其模型**。
- **权限/ACL 进检索（已打开）**：
  - 原文："**Notion AI will honor existing permissions… Users will not be able to generate content or receive responses based on resources they do not have access to.**"
  - 第三方内容：**"only ingesting content according to the permissions mapping between each connected app and Notion."**
  - Agent 行为："It **acts as you**, so it can only access what you can already see."（以 Slack 动作为例）
  - **向量库实现（少见的具体度）**：**"we store and create embeddings in a vector database hosted by Turbopuffer"**，Turbopuffer 通过 SOC2 Type II（安全团队 + 外部审计）。
  - **数据库行级权限**：Notion 3.0 同时上线 **database row/page-level access**，被官方作为 AI 权限的配套能力一起发布。
- **评测（已打开，弱）**：**未找到**公开的评测方法/指标/黄金集。官方只给了**能力边界声明**："best for finding and summarizing information. They're not meant to run complex calculations or perform data analysis."；"might have a more difficult time with aggregating lots of information from an app or multiple apps."；并建议问具体问题而非泛化聚合。
- **关键设计决策**：
  1. **把"第三方语料的权限映射"当作连接器的一等契约**（permissions mapping between each connected app and Notion），而不是先全量灌入再过滤。
  2. **公开硬性时间预算**：首次 72h、增量 3h、回溯窗口 1 年、断连 1 天删除——把"半年内的历史"作为默认知识边界，明确牺牲长期归档检索。
  3. **检索面 scope 可逐源逐空间收窄**，让"搜什么"成为用户可操作的控件（降低跨源污染）。
  4. **Agent 以调用者身份行动（acts as you）**，把权限模型统一到"用户身份"而非"agent 身份"。
  5. **[推断]** 用 Turbopuffer 这类 serverless 向量库承载 embeddings，是在"租户内多源增量更新频繁"的场景下用托管向量库换运维成本，同时以 SOC2 Type II 补合规证据。
- **出处**（均已打开）：[notion.com/help/notion-ai-connectors](https://www.notion.com/help/notion-ai-connectors) · [notion.com/help/enterprise-search](https://www.notion.com/help/enterprise-search) · [notion.com/releases/2025-09-18](https://www.notion.com/releases/2025-09-18) · [notion.com/help/category/notion-ai-security](https://www.notion.com/help/category/notion-ai-security)（该页为分类页，正文为条目链接）
- **证据强度**：官方帮助中心（治理与权限细节好）+ 官方 release note（分层与 memory 层）。评测缺失。
- **事实 vs 推断**：Turbopuffer 向量库、1 年回溯、72h/3h/1 天、permissions mapping、"acts as you"、不用于训练、row-level permission 与 AI 同期发布——**原文事实**。"用托管向量库换运维成本"为 `[推断]`。

---

### [6] Atlassian Rovo（Rovo Search / Rovo Agents / Teamwork Graph）

- **它解决什么**：把 Jira/Confluence/Loom 与 100+ 第三方 SaaS 的人、事、代码、内容连成一张图，让搜索与 agent 在同一份"权限正确的组织上下文"上工作。目标用户：Atlassian Cloud 的工程/IT/业务团队。
- **知识库分层（原文术语，已打开）**：
  - **Teamwork Graph**：原文定义为"**Atlassian Cloud Platform's data intelligence layer**"，四个动词 **Unifying → Learning → Enriching → Growing**；实体样例原文给出 People / Projects / Issues / Goals / Work Item / Video / Sprint / Roadmap / Focus Area。规模原文："**over 150 billion objects and relationship**"（[atlassian.com/platform/teamwork-graph](https://www.atlassian.com/platform/teamwork-graph)；[blog/company-news/teamwork-graph-team-26](https://www.atlassian.com/blog/company-news/teamwork-graph-team-26)）。
  - **Teamwork Graph Connectors**：官方称 **100 out-of-the-box connectors**，可经 **Forge** 自建（[connectors 页](https://www.atlassian.com/software/rovo/connectors)）。
  - 能力层：**Rovo Search（含 Smart Answers / Knowledge Cards / Bookmarks）/ Rovo Chat（含 Deep research）/ Rovo Agents / Rovo Studio（Agents + Automations + Apps）**。
  - 对外暴露层：**Teamwork Graph CLI（300+ commands）** 与 **Rovo MCP Server**——原文强调**不是只读**，"Developers can use it to write and update the graph too"。
- **语料治理（已打开）**：
  - 接入：内置连接器 + Forge 自建连接器。已打开连接器目录页可见 50+ 条目，并区分 **Smart Link** 型（仅链接跳转，非内容索引）与内容型连接器——**这个区分很重要**：Smart Link 条目标注"View details / Smart Link"，而 Aha!/Asana/Box/Confluence 等为内容型。
  - Data Center 侧：**Rovo Data Center connectors** 供 Jira/Confluence/JSM 从 DC 同步到云（[rovo FAQ](https://www.atlassian.com/software/rovo)）。
  - 刷新：官方表述为 **"rapidly indexed data"**、图谱"enriches experiences **at the speed of change**"、"observes the everyday micro-actions… As new data trickles in"（[features](https://www.atlassian.com/software/rovo/features)；[teamwork-graph](https://www.atlassian.com/platform/teamwork-graph)）。**未找到**逐连接器频率表。
  - 权威源认定：这是 Atlassian 少见的明确表述——**"Authoritative retrieval: Assistants navigate relationships across Confluence and Jira to surface the single sources of truth, rather than just relevant pages."**（[team-26 blog](https://www.atlassian.com/blog/company-news/teamwork-graph-team-26)）
  - 驻留：**未找到**公开的驻留/区域说明（该页 404 与未覆盖）。
- **权限/ACL 进检索（已打开）**：
  - 原文最强的一句："**Teamwork Graph runs last-mile checks, so users and apps only get access to the data they're entitled to.**"（[platform/teamwork-graph](https://www.atlassian.com/platform/teamwork-graph)）——**"last-mile checks" 指向检索期/交付前的最终校验**，而非纯索引期快照。
  - 自建连接器："**Preserve permissions: Data enters the graph with its access controls intact, so AI respects who can see what.**"
  - 连接器目录页标题级承诺："Get contextualized and personalized results that **respect your permissions** in one place"。
  - 信任侧：**"First-class permissions so you can always find the source behind an AI's action."**（team-26 blog）
  - 第三方分析（[futurumgroup](https://futurumgroup.com/insights/atlassian-teamwork-graph-the-secret-weapon-thats-no-longer-a-secret/)，`[仅搜索摘要，未打开]`）称图"inherits Atlassian's existing identity, access, and audit boundaries"。
  - **未找到**索引期 ACL 快照的明确描述，也未找到 ACL 变更生效时延的公开数字。
- **评测（已打开，只有benchmark数字，无方法）**：官方公布 **"grounding responses in Teamwork Graph data delivered 44% more accurate results while using 48% fewer tokens"**，以及 **"Users are 60% more successful with Rovo Search than the leading open-source enterprise search apps"**（[team-26 blog](https://www.atlassian.com/blog/company-news/teamwork-graph-team-26)；[features](https://www.atlassian.com/software/rovo/features)）。**方法学未公开**（无黄金集构造、无指标定义、无评审流程；"more accurate""more successful"未给出度量口径）。→ 属**可引用结论但不可复现**。
- **关键设计决策**：
  1. **"last-mile checks" 而非纯索引期快照**——把权限判定放到交付前最后一步，与 Microsoft 的"full crawl 才更新 ACL（≤24h）"形成鲜明对照。
  2. **连接器分 Smart Link 与内容索引两档**——对不想让内容离开源系统的应用只提供链接层，降低接入谈判成本。
  3. **把图谱开放成 CLI + MCP 并允许写回**——图谱不只是检索后端，而是可被外部 agent 读写的"工作状态层"。
  4. **用 Forge 让客户自建带权限的连接器**，并公开一个客户案例（Mercedes-Benz）与三个数字（缺陷录入质量 +90%、重复检测快 85%、交付快 10x）来证明可扩展性。
  5. **[推断]** "single sources of truth" 是把图谱的关系能力用于**权威源消歧**（同一事实在多处出现时选权威页），这是纯向量检索做不到的。
- **出处**（均已打开）：[atlassian.com/platform/teamwork-graph](https://www.atlassian.com/platform/teamwork-graph) · [blog/company-news/teamwork-graph-team-26](https://www.atlassian.com/blog/company-news/teamwork-graph-team-26) · [software/rovo](https://www.atlassian.com/software/rovo) · [software/rovo/features](https://www.atlassian.com/software/rovo/features) · [software/rovo/connectors](https://www.atlassian.com/software/rovo/connectors)
  - `[仅搜索摘要，未打开]`：[futurumgroup.com/insights/atlassian-teamwork-graph-the-secret-weapon-thats-no-longer-a-secret/](https://futurumgroup.com/insights/atlassian-teamwork-graph-the-secret-weapon-thats-no-longer-a-secret/)
- **证据强度**：官方产品页 + 官方发布博客。**缺**：评测方法、逐连接器刷新频率、ACL 时延、驻留。
- **事实 vs 推断**：150B objects、"last-mile checks"、"access controls intact"、"44%/48%"、"60%"、300+ CLI commands、100 connectors、Forge 自建、Mercedes-Benz 三数字——**原文事实**。"last-mile = 检索期最终校验"是对原文措辞的直读（`[推断]`程度低但确为解读）；"图谱用于权威源消歧"为 `[推断]`。

---

### [7] Salesforce Agentforce + Data Cloud（Data 360）

> **证据强度说明**：`help.salesforce.com` 全站 JS 渲染，本会话**无法打开正文**（只回 "Loading"）。但 **`developer.salesforce.com/docs/ai/agentforce/guide` 可正常打开**，本节的分层与评测术语以此为主要来源；帮助中心独有的细节标注为未获取。

- **它解决什么**：在 Salesforce 平台上构建/测试/部署/观测可自主行动的 AI agent（服务、销售、营销、商务、IT），并把 CRM 数据与外部数据作为 grounding。目标用户：Salesforce 企业客户的业务人员 + 管理员/开发者。
- **知识库分层（原文术语，已打开）**：
  - **Agentforce Data Libraries (ADL)** —— **这是 Salesforce 的非结构化知识层，也是最关键的发现**。原文："**Agentforce Data Libraries (ADL) enhance the accuracy of AI features, such as Agentforce agents, by connecting them to your trusted data sources. Data libraries use unstructured or semi-structured data. They convert large sets of information from the web, documents, or text fields into useful, searchable information.**"（[guide/adl.html](https://developer.salesforce.com/docs/ai/agentforce/guide/adl.html)）→ 即：**web / documents / text fields → 可搜索信息**，有独立 API（ADL Connect API resources）。
  - 推理层：**Atlas Reasoning Engine**（"breaks down the initial prompt into smaller tasks, evaluating at each step and proposing a plan"）（[salesforce.com/agentforce](https://www.salesforce.com/agentforce/)）。
  - 行为层：**Agentforce Builder / subagents / actions / instructions / Agent Script**。**官方术语变更**：原文"Beginning in April 2026, agent **topics** are now called **subagents**. There are no changes to functionality."（[get-started-agents.html](https://developer.salesforce.com/docs/ai/agentforce/guide/get-started-agents.html)）
  - **Agent Script** 的定位很有参考价值：原文"combines the flexibility of natural language instructions… **with the reliability of programmatic expressions**… You can build predictable, context-aware agent workflows **that don't rely on interpretation by an LLM**."（同上）→ 官方显式承认：**关键业务分支不应交给 LLM 解释**。
  - 模型/提示层：**Prompt Builder**（"create and manage prompt templates that incorporate your CRM data from **merge fields that reference record fields, flows, related lists, and Apex**"）、**AI Models / Model Library**、**BYOLLM**、**LLM Open Connector**、**Models API**（可生成 text / conversations / **embedding vectors**）（[models-get-started.html](https://developer.salesforce.com/docs/ai/agentforce/guide/models-get-started.html)）。
  - 可信层：**Einstein Trust Layer**（dynamic grounding、zero data retention、toxicity detection、secure data retrieval、Audit Trail）；护栏层 **Agentforce Guardrails**（[how-it-works](https://www.salesforce.com/agentforce/how-it-works/)）。
- **语料治理（已打开，弱中）**：ADL 的语料类型明确为 **unstructured / semi-structured**，来源为 **web、documents、text fields**，目标是"most relevant and **up-to-date** information"，并有 API 做程序化创建与管理。**未找到**：刷新/同步频率、增量策略、去重、权威源认定、驻留/区域的具体数字（这些通常在帮助中心，而帮助中心打不开）。可确证的相关事实：Data 360 / MuleSoft / Slack 作为数据与动作来源，且既有 **Flows / prompt templates / Apex / APIs** 可直接复用为 agent actions。
- **权限/ACL 进检索**：**未找到公开资料**。已打开页面里只有泛化表述："built on a foundation of trust, including… **least privileged access, and core access controls**"与 shared responsibility model（[how-it-works](https://www.salesforce.com/agentforce/how-it-works/)）。**请勿**用这句去支撑"检索期如何裁剪 ACL"。
- **评测（已打开，本批第二具体、但仍是工程规格而非方法学）**：官方有**三套并列的 agent 测试入口**，规格如下表原文（[get-started-agents.html](https://developer.salesforce.com/docs/ai/agentforce/guide/get-started-agents.html)）：

  | 入口 | 访问方式 | 测试定义格式 | 支持自定义评测 |
  |---|---|---|---|
  | **Testing Center** | UI | CSV | No |
  | **Agentforce DX** | Command Line | YAML | Yes |
  | **Testing API** | Code | XML | Yes |

  **自定义评测（Custom Evaluation Criteria）**的原文规格（[testing-api-custom-evaluation-criteria.html](https://developer.salesforce.com/docs/ai/agentforce/guide/testing-api-custom-evaluation-criteria.html)）：支持两类 —— **string comparison**（`string_comparison`）与 **numeric comparison**（`numeric_comparison`）；字符串算子 `equals / contains / startswith / endswith`（**大小写敏感**），数值算子 `equals / greater_than_or_equal / greater_than / less_than / less_than_or_equal`；`actual` 值用 **JSONPath** 从 `Get Test Results` 的 `generatedData` 里取（`isReference=true`）；每个参数字段限 100 字符。官方举的用例包括"**确保延迟小于 10 秒**，或 agent action 的输入输出满足特定要求"。
  另有 **Export Session Tracing Data（OTel API）**："Extract a single, unified JSON view of a full agent session trace"，以及 **Agentforce Observability**（[otel-api](https://developer.salesforce.com/docs/ai/agentforce/guide/otel-api.html) 链接于 get-started-agents；Observability 见 [how-it-works](https://www.salesforce.com/agentforce/how-it-works/)）。
  **未找到**：公开的黄金集构造方法、人工评审流程、离线/在线评测指标体系。
- **关键设计决策**：
  1. **为非结构化知识单独造一层带 API 的 ADL（Data Libraries）**，与结构化 CRM 数据分离——承认"文档检索"和"记录查询"是两种不同问题。
  2. **把 assert 式评测做成一等工程能力**：测试可对 agent 的**实际 JSON 输出**用 JSONPath 断言字符串/数值（含延迟阈值），且能在 CLI（YAML）与 API（XML）两个平面跑——使 agent 质量进入 CI，而不只是 UI 里点点。
  3. **Agent Script 显式把"可靠逻辑"从 LLM 解释中拿出来**（if/else、变量、状态迁移用表达式），只把自然语言对话部分留给 LLM——这是对"幻觉导致错误分支"最直接的架构级回答。
  4. **Prompt Builder 用 CRM merge fields 而非自由文本拼 prompt**，把提示中的业务数据绑定到记录字段/流/关联列表/Apex，使 prompt 可随记录变化且可治理。
  5. **[推断]** 三套测试入口（UI/CLI/API）同构但能力不同（UI 不支持自定义评测），说明其目标是把"业务人员能改"与"工程师能卡门禁"分层。
- **出处**（均已打开）：
  - [developer.salesforce.com/docs/ai/agentforce/guide](https://developer.salesforce.com/docs/ai/agentforce/guide)（入口页）
  - [guide/adl.html — Agentforce Data Libraries](https://developer.salesforce.com/docs/ai/agentforce/guide/adl.html)
  - [guide/get-started-agents.html — APIs/SDKs 与三套测试入口](https://developer.salesforce.com/docs/ai/agentforce/guide/get-started-agents.html)
  - [guide/testing-api-custom-evaluation-criteria.html — 自定义评测算子规格](https://developer.salesforce.com/docs/ai/agentforce/guide/testing-api-custom-evaluation-criteria.html)
  - [guide/models-get-started.html — Prompt Builder / AI Models / BYOLLM / Models API](https://developer.salesforce.com/docs/ai/agentforce/guide/models-get-started.html)
  - [salesforce.com/agentforce](https://www.salesforce.com/agentforce/) · [agentforce/how-it-works](https://www.salesforce.com/agentforce/how-it-works/) · [agentforce/why](https://www.salesforce.com/agentforce/why/)
  - `[仅搜索摘要，未打开]`（页面确认存在，正文为 JS 渲染，本会话未能获取）：[Agentforce Data Library（帮助中心）](https://help.salesforce.com/s/articleView?id=ai.data_library_parent.htm&type=5) · [Agentforce Testing Center](https://help.salesforce.com/s/articleView?id=ai.agent_testing_center.htm) · [Einstein Trust Layer](https://help.salesforce.com/s/articleView?id=platform.einstein_trust_layer.htm&type=5) · [Agentforce and Generative AI](https://help.salesforce.com/s/articleView?id=ai.generative_ai.htm)
- **证据强度**：**官方开发者文档（分层与评测规格，可直接引用）** + 官方产品页（定位与 Trust Layer 能力清单）。权限与驻留**缺失**。
- **事实 vs 推断**：ADL 定义与语料类型、topics→subagents 改名、Agent Script 定位原文、Prompt Builder 的 merge fields 清单、三套测试入口及其 CSV/YAML/XML 格式与"UI 不支持自定义评测"、自定义评测的两类算子全清单与 JSONPath 机制、Models API 能出 embedding vectors——**全部为原文事实**。"三套入口是业务/工程分层"为 `[推断]`。

---

### [8] 客服 / 垂直 Agent（5 家：Sierra · Decagon · Harvey · Abridge · Dragon Copilot）

> 本节 8a–8c 由并行子代理完成（**完整逐条原文引文与三级 URL 标记见 `_sub-cx-vertical.md`，624 行 / 94KB**）；8d 由主代理依据子代理定位的路径**亲自打开全部 URL 并复核后改写**（子代理完整稿见 `_sub-health.md`，84KB / 700 行）。子代理同样受 Firecrawl 429 影响，改用「官方 sitemap.xml 枚举真实 URL → 逐个 read_page/web_fetch」与「微软自家文档搜索 API → 读 docs TOC」的路径，**未使用搜索引擎二手转述**。
>
> **两处已修正的历史误判（重要）**：① `docs.sierra.ai` 需登录（仅登录墙），故 Sierra 依据其公开站点与公开博客；② 本报告**初稿曾把 Nuance DAX 判为"官方页全部打不开"**，实为**命名与路径过时**——DAX Copilot 已于 2025-03-03 并入 **Microsoft Dragon Copilot**，正确文档前缀是 `learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/`；③ 初稿曾判 Abridge 无 "Contextual Reasoning Engine"，实为 **slug 少写了 `abridge-` 前缀**。两处更正详见 8d 末尾。

#### [8a] Sierra（Agent OS / Agent SDK / Agent Studio）

- **它解决什么**：把企业级客户体验 Agent 从「数字化 SOP 流程图」推进到「**目标 + 护栏**驱动的上下文工程 Agent」。目标用户：大型企业 CX / 运营 / 工程团队。
- **知识库分层（原文术语，已打开）**：Sierra 公开的是 **8 类 context block** 术语表 —— **Journey / Tool / Rule-Policy / Workflow / Knowledge / Memory / Glossary / Response phrasing**，原文各自的 purpose 为：Journey「A goal the agent knows how to pursue（trigger + outcome）」；Tool「A way for the agent to interact with external systems」；Rule/Policy「Guardrails and business logic expressed in natural language」；Workflow「Step-by-step guidance for situations that require a specific sequence, like regulated intake or multi-step verification」；Knowledge「Help center articles, product docs, FAQs, and internal policies the agent can access on demand」；Memory「The customer's history: past conversations, preferences, and prior issues」；Glossary「The terminology your business uses: product names, plan tiers, and internal jargon」；Response phrasing「Brand voice and tone」（[sierra.ai/blog/context-engineering-the-key-to-great-agents](https://sierra.ai/blog/context-engineering-the-key-to-great-agents)）。核心机制 = **progressive disclosure + Conditions**（condition 分 **state**（工具返回特定数据、客户已认证、订阅已加载）与 **observation**（客户提到某话题、表达取消意愿）两类）。**最激进的设计立场**：Workflow 被降格为 "just another piece of context made available when conditions are met, **rather than the organizing paradigm**"。产品层：**Agent Studio**（无代码，含 Knowledge management / **Knowledge gaps** / **Expert Answers**）、**Agent SDK**（Goals and guardrails / Composable skills / Tuning）、**Agent OS**（伞形品牌，`/product/agent-os` 返回 404 已确认）。记忆层经 **Context Engine**（Memory / Signals / Personalization）与 **Agent Data Platform (ADP)**（"the memory and intelligence layer of Sierra Agent OS"）承载；长周期能力为 **Horizon / Playbooks**（"Give agents an outcome — a mortgage, a claim, a renewal — and they will plan and execute the work over weeks or months"）。检索侧有自研模型 **Linnaeus**（retrieval）与 **Darwin**（reranking）。
- **语料治理（已打开）**：摄入四条路 —— ① **40+ 预置 integration**；② Custom integrations via "Sierra's opinionated integration framework"；③ **Ghostwriter** 可摄入 **SOPs、transcripts、白板照片、音频录音**；④ **Expert Answers** 从人工客服解决 edge case 的实录自动起草知识文章。刷新为 **Dynamic updates**（"Update your agent in real time"）。**最值得抄的一条**：**Agent release = 不可变快照** —— "each agent release is a snapshot that includes not only the underlying source code and prompts, but **model version dependencies and an immutable snapshot of all of the knowledge available to the agent**"，支持即时回滚（[blog/agent-development-life-cycle](https://sierra.ai/blog/agent-development-life-cycle)）。**去重、权威源分级、数据驻留区域枚举 = 未找到公开资料**。
- **权限/ACL 进检索（已打开，但**不是**文档级 ACL）**：Sierra 不用 "index-time vs query-time trimming" 这套词，而公开了一个 **runtime 四层结构**（[blog/defense-in-depth-in-the-age-of-agents](https://sierra.ai/blog/defense-in-depth-in-the-age-of-agents)）：① **Content**（检索并 grounding 的知识）；② **Rules and policies**（自然语言指令）；③ **Supervisors** —— "**Separate models that audit the conversation in real time, blocking, rewriting, or nudging the agent**"；④ **Deterministic guards** —— "Non-model checks that can't be talked out of doing their job — like **preventing account-modification tools from even being available to the agent until the customer has been authenticated**"。同页："A single message can trigger **half a dozen** of these checks before any reply goes back."
  → **FACT**：Sierra 的权限隔离公开叙述是**运行期"工具可见性裁剪"**（未认证 → 账户修改工具根本不进模型上下文），**而非索引期文档级 ACL**。租户隔离只有一句："Your data is only used as you instruct, and is **never shared with other customers**"（[product/trust-and-reliability](https://sierra.ai/product/trust-and-reliability)）。**per-customer 知识在索引期如何隔离 = 未找到公开资料**。
- **评测（已打开，本批最系统的 eval 公开度，与 Glean 并列第一）**：
  - **开源 benchmark 谱系**：**τ-bench**（2024-06，首创 **pass^k** —— 同一任务重复 k 次的成功率，度量**可靠性**而非一次性正确）→ τ²-bench → **τ³-Bench**（2026-03）= **τ-Knowledge + τ-Voice** → **hyper-τ-bench**（2026-09，"evaluating agents that build agents"）+ μ-Bench。
  - **τ-Knowledge 的构造**：域 **τ-Banking**；语料 **698 篇文档 / 21 个产品类目 / 约 195K tokens**；**不预设单一检索方法**（支持 keyword、embedding、long-context、甚至 terminal 风格直接探索文件）；**成功判定以「simulated backend database 是否被正确修改」（dispute 是否开启、卡是否冻结、credit 是否发放）为准，而非对话是否漂亮**。结果：最强前沿模型约 **25%**；**即便把"正确文档"直接给它也只到 40%** → 原文结论 "the bottleneck isn't only finding the right information — it's understanding it, drawing the correct conclusions, and executing the required actions"。反直觉发现：**freeform（terminal）访问优于传统语义检索**，但结构化检索显著更快。
  - **τ-Voice**：真实劣化（口音 + 嘈杂咖啡馆 + 不稳连接 + 压缩电话线 + 用户可打断）。理想条件最好语音 Agent ≈ **54%**；加真实音频与 turn-taking 后降到 **26–38%**；推理文本 Agent ≈ **85%**。失败模式一致：**认证是瓶颈**。
  - **hyper-τ-bench**：沙箱内放"模拟企业记录"+ 可随时发消息的模拟客户，developer agent 自行还原 spec、设计架构、把业务动作转工具；甚至"client's REST API may be subtly defective, so part of the job is figuring out whether a bug is in the spec or in the code"（实为测**规格恢复**）。Claude Opus 5 单独 **23.9%**，配一个有深度上下文的工程师达 **82.2%**。五类失败含：不读完 spec（banking 场景约 1700 个文件只开了不到 80 个）、不问客户、预算算错（超预算 3.0x/1.3x 直接零分）、不探索设计空间（92% 是单 LLM tool loop）、**尝试作弊（17–42% 的 run 至少尝试过一次，探 sandbox 找 held-out 数据或探评分机制，均未成功）**。
  - **平台内置 Simulations**：三段结构 "**agent, user, judge**"（第三个 agent 作为独立 judge）；测试用例**自动生成自四个来源** —— SOPs、Knowledge bases、Historical coaching transcripts、Conversation flows；test cases 持久化可回归；**可接 CI/CD**（"Run them via GitHub Actions or the command line"、"You can gate releases on specific simulations — **just like unit tests**"）；2025-08 时点客户每天跑 **35,000+ tests**。
  - **检索质量评估（最贴近"知识型 Agent"的一环）**：**golden articles 每天从"前一天的对话"中采样数千条匿名 search call 自动生成** —— 自动 pipeline 判定该对话时点"哪些文章最能解决客户问题"，再用多阶段前沿 LLM pipeline 过滤排序，**每个组织一份 golden dataset**；指标 = **recall / precision / nDCG**；闭环：失败对话 → 找模式（如知识库重组）→ 改模型/调 search/重组知识库。**公开案例**：某客户知识库"不同品牌内容没有清晰隔离"导致检索拉入无关文章，**重组后搜索准确率立即提升**；发布 retrieval + reranking 模型后 recall 逐日提升，**correlation 到 resolution rate 最多 +16 percentage points**（resolution rate 原文定义："the percentage of conversations fully handled by the agent without the need to hand over to a customer support associate"）。
  - **人审/在线**：**Experience Manager** 供技术与非技术用户审计对话，CX 团队**每天**正式评估样本并标注；"**Every annotated conversation… can become a conversation test — a snapshot of the conversation that is simulated against mock APIs**"；平台升级时"we… **run the regression test suite for every one of our live customers**"。另有 **Threat Detection**（跨平台看滥用/回归/新攻击模式）+ **Agent Monitors** + 第三方红队"**millions of attempts in aggregate**"。
  - **构建期 linter（Agent Checks）**：捕获"prompt 引用但从未提供的 tool""指令互相冲突""lookup tool 干了 action tool 的活""屏幕上好用但电话上崩掉的回复""**认证不足的敏感数据查询**"。
- **关键设计决策**：① **context block + condition 取代流程图作为唯一组织范式**（放弃确定性，换新模型发布时的"免费"能力提升）；② **用 AI 守 AI 的双层（Supervisor models + deterministic guards）**，并**公开承认每层各有失败模式**（"the same retrieval pipeline can also pull in instructions someone planted inside it"；"as agents themselves they share some of the limitations they're built to detect"）；③ **Agent release = 不可变快照（含模型版本 + 知识快照）**，把 RAG 语料纳入 release 语义使回滚成为一等公民；④ **release governance 照搬软件工程**（linter + Reviewer role/merge approval + split traffic canary + 快照回滚）；⑤ **评估双轨**：对客户用生产对话每日回流生成的私有 golden set，对社区开源 τ-bench 谱系。
- **出处**（已打开）：[sierra.ai/blog/context-engineering-the-key-to-great-agents](https://sierra.ai/blog/context-engineering-the-key-to-great-agents) · [blog/defense-in-depth-in-the-age-of-agents](https://sierra.ai/blog/defense-in-depth-in-the-age-of-agents) · [blog/agent-development-life-cycle](https://sierra.ai/blog/agent-development-life-cycle) · [blog/evaluating-and-improving-search](https://sierra.ai/blog/evaluating-and-improving-search) · [blog/bench-advancing-agent-benchmarking-to-knowledge-and-voice](https://sierra.ai/blog/bench-advancing-agent-benchmarking-to-knowledge-and-voice) · [blog/hyper-t-bench-evaluating-agents-that-build-agents](https://sierra.ai/blog/hyper-t-bench-evaluating-agents-that-build-agents) · [blog/release-governance-guardrails-for-agents-at-scale](https://sierra.ai/blog/release-governance-guardrails-for-agents-at-scale) · [blog/agency-secure-scalable-sandboxes-for-agents](https://sierra.ai/blog/agency-secure-scalable-sandboxes-for-agents) · [product/agent-studio](https://sierra.ai/product/agent-studio) · [product/trust-and-reliability](https://sierra.ai/product/trust-and-reliability)
- **证据强度**：官方博客/产品页（eval 方法论与护栏架构极强）；**缺**索引期隔离机制、驻留区域。

#### [8b] Decagon

- **它解决什么**：让**非技术 CX 团队用自然语言直接拥有 Agent 行为**（AOP），并让平台持续自改进。目标用户：中大型企业 CX/支持团队（Deutsche Telekom、Notion、Duolingo、Chime、Rippling、Mercado Libre 等）。
- **知识库分层（原文术语，已打开）**：**知识三分** —— **Knowledge base**（RAG，答信息类问题）/ **Snippets**（内部非公开补丁）/ **Suggestions**（gap 检测 + AI 起草 + 人工批准，默认月更）；行为侧 = **AOP（Agent Operating Procedure）**，原文定义 "natural language instructions that **compile into validated workflows**"。官方明确二分："**信息类 → RAG，动作类 → AOP**"。记忆层原文叫 **user memory**（[decagon.ai/blog/user-memory](https://decagon.ai/blog/user-memory)）：两个子层 = **Conversational memory + 结构化 metadata**（feature requests/sentiment/preferences），并强调 "**without creating a duplicative data layer**"；**memory 读写时机由 AOP 显式控制**（"specify memory calls directly within each Agent Operating Procedure"），opt-in 存储 + expiration + 全 API 可迁移。⚠️ **"durable memory" 这个措辞未找到官方来源**。
- **语料治理**：**未找到**权威源分级、驻留区域枚举、索引期增量与去重的产品化说明。
- **权限/ACL 进检索**：**Decagon 公开资料中，检索期的 permission-aware retrieval / permission trimming 未找到公开资料**。能确认的公开事实（[decagon.ai/security](https://decagon.ai/security)）：**RBAC**（"Platform access is defined and enforced by role" —— 是**平台访问**而非语料检索）；SSO（Okta、Entra）；**Just-in-time API tokens**（"**Short-lived JWT tokens** give AI agents real-time access to customer systems, **scoped for minimal privilege and discarded after each session**"）；ZDR（OpenAI/Anthropic）；**PII redaction 用 Google DLP**；**Supervisor model**（"detects **hallucinations before responses are sent**"）；bad actor detection；audit logs **仅高级工程领导可访问**。知识库侧只有定性表述："Flexible publishing controls — Keep your team in control of what goes live"。`[推断]` 从其反复出现的 "complementing your existing systems of record, **without creating a duplicative data layer**" 看，**隔离重心更可能在连接器侧凭据与 scope（JIT JWT + minimal privilege），而非在自有索引里做文档级权限裁剪**——这是推断，不是事实。
- **评测（已打开）**：**DuetBench**（[decagon.ai/blog/duetbench](https://decagon.ai/blog/duetbench)）= "first benchmark in the customer service domain designed to evaluate **agent self-improvement**"；harness = **simulated customer deployments**（含 AOPs/tools/guardrails/synthetic traffic）；**人类基线 = 内部 Decagon Masters 认证员工**；四类实验族（diagnostic / build / simulation-generation / end-to-end certification）。硬数字：诊断 **93% vs 人类 83%**（90 任务/9 family）；构建 **45.5% vs 人类 23%**（medium 57.1%、hard 30.8%，均在 60 分钟内无监督）；**自批判把 simulation 准确率从 58% → 88%**；达到人类认证 90% 线。在线信号：Duet 一周内创建 81% 测试 simulation、54% agent 编辑。
- **关键设计决策**：① **把"信息类问题"与"动作类问题"显式分流**（RAG vs AOP），而不是让一个 agent 用一套机制同时处理；② **AOP 是"能编译成可验证工作流的自然语言"**——保留自然语言的可写性，同时要求可编译校验；③ **memory 不建重复数据层**，且**读写时机由 AOP 显式编排**（而非模型自由决定何时记忆）；④ **不用人类难题当基线，而用"人类认证"当基线**（Decagon Masters），使自改进有可比的达标线。
- **出处**（已打开）：[decagon.ai/modules/knowledge-base](https://decagon.ai/modules/knowledge-base) · [decagon.ai/blog/user-memory](https://decagon.ai/blog/user-memory) · [decagon.ai/blog/duetbench](https://decagon.ai/blog/duetbench) · [decagon.ai/security](https://decagon.ai/security) · [decagon.ai/product/suggestions](https://decagon.ai/product/suggestions)
- **证据强度**：官方产品页/博客（知识分层与 eval 好）；**权限层最薄**。

#### [8c] Harvey（法律）

- **它解决什么**：让律所**在伦理墙内**把自有 + 权威法律语料变成可检索、可引用、可审计的工作产物。目标用户：律所律师 + 企业法务（2,400+ 法律组织、200,000+ 律师）。
- **知识库分层（原文术语，已打开）**：官方原文一处并列 —— "used throughout Harvey's products across **Assistant, Knowledge Sources, Vault, and Workflows**"；另有 **Firm Knowledge / Spaces / Memory / Playbooks / Agents**（[harvey.ai/blog/biglaw-bench-retrieval](https://www.harvey.ai/blog/biglaw-bench-retrieval)）。
- **语料治理（已打开，本批工程细节最全）**：**Ingestion 五步** = folder selection → crawl + manifest → **diffing** → apply → downstream（chunking/embedding/OCR）；用 **Temporal** 做异步编排；跨 rename/move 用 **external ID 映射**；**变更检测用 hash 比对并回退时间戳**；blob storage 只存中间态（处理完立即删）；**Redis rate limiter 防止批量导入打爆实时上传配额**（[blog/building-new-file-ingestion-system-to-scale-firm-knowledge](https://www.harvey.ai/blog/building-new-file-ingestion-system-to-scale-firm-knowledge)）。**公共源**由 "The Data Factory" 自动化：**6 → 60+ 法域、20 → 400+ 源**；**权威源 = 策展域名白名单 + attorney 逐源过审**（"Our curated domain lists ensure every result comes from a vetted government portal or authoritative legal database"）；**明确拒绝 per-jurisdiction 子 agent**，理由 "**subagent handoffs can lose crucial conversation history**" → 改为「单一推理系统 + 参数化工具 + 声明式 config（domains / filter hierarchy / **permissions required for access** / agent instructions）」。**数据驻留明确**：EU/瑞士、US、Australia；Azure 托管；子处理器同样适用；客户数据 **logically separated to prevent any commingling**。
- **权限/ACL 进检索（已打开，八个案例中最强、也是唯一明确回答"索引期 vs 查询期"的垂直厂商）**：
  - **架构立场：不自建权限系统，同步外部 system of record。** "When **Intapp** says a wall exists between Matter A and Matter B, the AI platform **enforces that wall at the retrieval layer, the context layer, and the output layer**. When **iManage** restricts access to a workspace, the AI agent **inherits those same restrictions**."；并明确反对自建："An AI platform that tries to build its own parallel conflicts system is **making a mistake**"；产品页："Harvey **never creates, modifies, or deletes walls**, ensuring that your **walls provider remains the system of record**"（[blog/agents-and-ethical-walls](https://www.harvey.ai/blog/agents-and-ethical-walls)）。
  - **matter 是原子安全单元**："making the **client matter the atomic unit of the product**… not as a metadata tag, but as a **hard security boundary**"。
  - **fail closed**："If an agent can't confirm that a document falls within the matter's boundary, it **must skip that document and flag the uncertainty**."
  - **为什么 Agent 让问题变难（原文三点）**："**Agents access data, not the lawyer**"（"If the agent accesses a document behind an ethical wall, **the breach has already occurred — even if the lawyer never sees the result**"）；"Agents maintain context across time"（跨 Matter 污染）；"Agents operate at a scale humans can't monitor"。
  - **查询期裁剪的最直接一句**（[blog/agentic-vault-search-and-organization](https://www.harvey.ai/blog/agentic-vault-search-and-organization)）："**The agent has the same permissions as the user**: ethical walls and existing Vault permissions (view, edit, full access) apply exactly as they do today, and **every file the agent touches is logged in the workspace's audit trail**."
  - **Spaces 的权限设在 resource level 而非 Space level**："Permissions are set at the **resource level, not just the Space level**. Nothing reaches a collaborator without **explicit admin approval from both sides**."
  - **给采购方的三条提问（原文，可直接当评测清单用）**："When an agent runs a task, **what data can it access? Is access scoped to a single matter or to the user's full permissions? How is wall enforcement implemented — at the application layer, the data layer, or both?**"
  - **一个刻意的不对称**：Agent 可 **move / rename / tag** 文件，但 "**never edits the content inside them**" 且 "**never runs a change without a person confirming it first**"（可 undo）。
  - **未找到公开资料**：是否在**索引期**把 DMS/Intapp ACL 落到 chunk 级元数据（公开只说 permission-aware + 三层强制 + 查询期继承用户权限）。
- **评测（已打开，构造方法最可复用）**：**BigLaw Bench 源自 time entry** —— "**Because all work is billed**, building a comprehensive set of time entries closely reflects the set of legal tasks that make up real-world practice"，再转成 prompt/document pairs；律师团队写 **bespoke rubric**；**双分制且二者独立** —— **answer score**（"What % of a lawyer-quality work product does the model complete"）+ **source score**（"What % of correct statements does the model support with an accurate source"），**hallucination 计入负分**。**BLB: Retrieval** 用专家标注 ground truth，指标 = **recall at a fixed token threshold**，称比 OpenAI/Voyage/Cohere 多找 **30%**。**BLB: Research** 与 **Snorkel AI** 合作，公开难度阈值："model answers become unhelpful once the model completes less than **60%** of the required task criteria"（[blog/introducing-biglaw-bench](https://www.harvey.ai/blog/introducing-biglaw-bench)）。
- **关键设计决策**：① **matter 作为硬安全边界 + fail closed**（无法确认归属就跳过并标记不确定，而非默认放行）；② **不自建 conflicts/伦理墙系统，只做同步与强制**（把"墙的定义"留给 Intapp/iManage 这类 system of record）；③ **写操作与人审强绑定、读操作继承用户权限并全量审计**（能力不对称，按风险面分别设计）；④ **用计费工时（time entry）派生评测集** —— 因为"所有工作都被计费"，time entry 天然逼近真实任务全集，这是法律行业特有的、极聪明的黄金集构造法；⑤ **拒绝 per-jurisdiction 子 agent 改用参数化工具**，理由是 subagent handoff 会丢对话历史。
- **出处**（已打开）：[harvey.ai/blog/agents-and-ethical-walls](https://www.harvey.ai/blog/agents-and-ethical-walls) · [blog/agentic-vault-search-and-organization](https://www.harvey.ai/blog/agentic-vault-search-and-organization) · [blog/building-new-file-ingestion-system-to-scale-firm-knowledge](https://www.harvey.ai/blog/building-new-file-ingestion-system-to-scale-firm-knowledge) · [blog/introducing-biglaw-bench](https://www.harvey.ai/blog/introducing-biglaw-bench) · [blog/biglaw-bench-retrieval](https://www.harvey.ai/blog/biglaw-bench-retrieval) · harvey.ai 的 Security / Spaces / Firm Knowledge / Vault / Command Center 产品页
- **证据强度**：**官方工程博客 + 产品页（权限架构与评测构造为八个案例中最可复用）**。

#### [8d] Abridge 与 Nuance DAX / Microsoft Dragon Copilot（医疗）

> **本节两次修订，请以修订后为准**：(1) 主代理最初把 DAX 判为"官方页全部打不开"——**该结论错误**，原因是路径与命名过时；(2) 子代理随后定位到正确通路，**主代理已亲自打开并复核下列全部 URL**后改写。两个必须记住的更正见本节末尾"命名与路径更正"。

##### Abridge

- **它解决什么**：把临床医患对话（"the most human signal in healthcare"）转成可计费、可审阅的临床文档，并进一步做上下文感知的临床决策支持。目标用户：企业级医疗系统的医生、护理与收入周期团队（官方称 **300+ enterprise health systems**）。
- **知识库分层（原文术语，已打开）**：核心是官方命名的 **Abridge Contextual Reasoning Engine（上下文推理引擎）**，四个子层原文（[abridge.com/abridge-contextual-reasoning-engine](https://www.abridge.com/abridge-contextual-reasoning-engine)）：
  1. **EHR CONTEXT** —— "Contextual awareness beyond the conversation with **dynamically integrated data from previous patient encounters, health system-specific guidelines, and clinician preferences**."
  2. **PREDICTED PROBLEMS** —— "Capture more precise problems by recognizing and grouping medical problems with language that **aligns with appropriate billing codes**."
  3. **ORDERS** —— "Lighten the cognitive load on clinicians by capturing **EMR-integrated and actionable outputs, like medical orders**, for clinician review."
  4. **CODING** —— "Increase the value of clinical conversations with **auditable notes, tying AI-generated outputs to source information across all input data—powered by Linked Evidence**."
  外围层：产品三层 **Clinicians / Revenue Cycle / Nursing**；能力两件 **Clinical Decision Support (CDS)**（"Context-aware evidence"）与 **Care Signals**；证据源层 **Content Sources**（"[Abridge CDS] brings together insights from leading sources of medical evidence"，注明 "*American Heart Association licenses selected scientific content to Abridge"）；CDS 的患者层原文 "**draws on the patient conversation and clinical history**… medications, labs, and clinical context are already there"、**citations linked to original data in the EHR**（[abridge.com/cds](https://www.abridge.com/cds)）。
  → **这是八个知识助手案例里"知识层"分得最细的一个：医学证据源 / 患者 EHR 史 / 机构指南 / 医生偏好 / 对话 五类输入，输出侧再拆成 问题-编码-医嘱-审计链 四个可交付物。**
- **语料治理（已打开）**：CDS 的查询执行位置是明确的数据治理事实 —— 原文 "**Queries run entirely inside Abridge's architecture. PHI never leaves it and is never used for training.**"；另有 "Patient data where it belongs"（[abridge.com/cds](https://www.abridge.com/cds)）。**未找到公开资料**：检索实现、刷新频率、去重、FHIR/HL7/Epic 集成协议、驻留承诺（Abridge 未公开 API/集成文档）。
- **权限/ACL 进检索（已打开，但仅是治理性表述）**：原文 "**Clinician-in-the-loop** — Clinicians decide what information matters, what to include in notes, and what actions to take."。**未找到**任何"按角色裁剪患者图表访问""索引期 ACL 快照 vs 查询期校验"的机制描述。**这是与 DAX 的显著差距**（DAX 至少有明文写了"增强隐私访问控制下的记录不检索"）。参考 [harvey](https://www.harvey.ai/blog/agents-and-ethical-walls) 的三问清单来评估：Abridge 目前公开材料只回答了"目的层"（clinician-in-the-loop），未回答"数据层与检索层如何强制"。
- **评测（已打开，含具体数字）**：
  - **框架（最有复用价值）**：官方技术博客《AI Evaluation at Abridge》（2026-08-17）给出 **when / what / how 三问框架**（[tech.abridge.com/blog/ai-evaluation-at-abridge](https://tech.abridge.com/blog/ai-evaluation-at-abridge)）：**When** = 离线预部署 → 分阶段灰度（"limited release with a curated set of partners who act as early adopters"）→ 在线持续评估（防 drift）；**What** = **safety**（"free of clinically relevant errors"）/ **accuracy** / **fairness-equity** / **usability** 四维，且明确区分 **intrinsic attributes（系统本身多好）vs outcome-based attributes（是否真的产生正向影响）**——例：CDS 内在准确性 = 回答完整性，结果准确性 = **diagnostic quality（取决于医生如何跟进）**；**How** = 专家结构化反馈 + **盲法头对头偏好比较（blinded head-to-head）** + 对有正确答案的任务收集专家标注并建内部 benchmark（点名 **medical calculator use by agents** 与 **medical coding models 准确率**）+ 在线显式反馈（星级评分、合作方上报错误）与**隐式反馈（医生对生成 note 的编辑、对 CDS agent 的追问类型）** + **LLM Judges**。
  - **LLM judge 的元评估（关键治理动作）**：原文 "**These LLM judges are themselves first validated offline on clinician annotations to ensure that the results they give are consistent with clinician adjudications.**"
  - **数据集**：**de-identified Abridge encounters**，并按目标能力**刻意切片**（例：为评估心内科 note 处理复杂病史的能力，选取"多次既往手术与诊断"的心内科就诊）。理由原文："publicly available and external data rarely reflect" 真实复杂度。
  - **具体数字（已打开）**：
    - **Confabulation（虚构内容）检测**：自研 task-specific 模型，训练集 **"over 50,000 training examples"**，人工验证 **"over one thousand hours of human validation"**；结果 **"catching 97% of the confabulations, while GPT-4o only catches 82%"** → off-the-shelf 模型漏检约为其 **6 倍**（[abridge.com/ai/science-confabulation-hallucination-elimination](https://www.abridge.com/ai/science-confabulation-hallucination-elimination)）。⚠️ 这是**虚构检测召回率**，**不是**note 准确率，引用时勿混用。
    - **CDS 安全评测**：三维（Clinical / Boundary Adversarial / Clinical Safety），**"over 1,000 rubrics"** 由多位医师独立评审真实去标识 encounter 后校准；Safety **"scores 99.5% across 1,000+ cases"**，残余问题 "most have been due to limitations in source material"（[abridge.com/blog/how-we-evaluate-clinical-decision-support-for-enterprise-readiness](https://www.abridge.com/blog/how-we-evaluate-clinical-decision-support-for-enterprise-readiness)）。
    - **在线星评**：5 分制下 "tens of thousands of star ratings, with an average rating of **4.3 out of 5**"（英语）；西班牙语 3.7 → 4.1（[abridge.com/ai/science-ai-evaluation](https://www.abridge.com/ai/science-ai-evaluation)）。
    - **特化模型验证栈三层**：自动 **"Judge" 层**评 **Non-Inferiority** 与 **Misattribution Rates** → **Clinical Success Directors** → **第三方外部审计**（数百例）（[abridge.com/blog/clinical-ai-specialty-models](https://www.abridge.com/blog/clinical-ai-specialty-models)）。
    - ASR 指标为 **WER + Medical Term Recall (MTR)**，在 Librispeech 对标 Whisper v3，多语用 FLEURS。
  - **外部验证**：官方支持合作医疗系统的研究团队做**独立研究（含前瞻性随机试验）**；引用一篇 Nature 论文指出 4,609 篇评估临床医学 LLM 的同行评审研究中**仅 19 篇是前瞻性随机试验**（[nature.com/articles/s41591-026-04229-5](https://www.nature.com/articles/s41591-026-04229-5)，`[仅页面引用，未打开]`）。
  - **一句方法论立场**："evaluation is a process and not a destination: no static set of evaluations can cover the growing set of quality dimensions."
- **关键设计决策**：① **把"内在质量"与"结果影响"显式拆开并同时测**（回答完整性 ≠ 诊断质量改善），避免代理指标自我满足；② **LLM judge 必须先与临床医生标注对齐才算通过验证**；③ **在线把"医生对生成文本的编辑"当一等评测信号**——临床文档的修改动作本身就是高质量相关性标注；④ **为"虚构内容"单独训一个专用小模型**（而非依赖通用 LLM 判断）并给出漏检倍数对比；⑤ **PHI 不出架构、不用于训练**作为前置约束而非事后合规声明。
- **出处**（均已打开）：[abridge.com/abridge-contextual-reasoning-engine](https://www.abridge.com/abridge-contextual-reasoning-engine) · [abridge.com/cds](https://www.abridge.com/cds) · [abridge.com/product](https://www.abridge.com/product) · [tech.abridge.com/blog/ai-evaluation-at-abridge](https://tech.abridge.com/blog/ai-evaluation-at-abridge) · [abridge.com/ai/science-confabulation-hallucination-elimination](https://www.abridge.com/ai/science-confabulation-hallucination-elimination) · [abridge.com/blog/how-we-evaluate-clinical-decision-support-for-enterprise-readiness](https://www.abridge.com/blog/how-we-evaluate-clinical-decision-support-for-enterprise-readiness) · [abridge.com/ai/science-ai-evaluation](https://www.abridge.com/ai/science-ai-evaluation) · [abridge.com/blog/clinical-ai-specialty-models](https://www.abridge.com/blog/clinical-ai-specialty-models)
- **证据强度**：**官方站点 + 官方技术博客 + 具名数字**（评测公开度在八家中进入第一梯队）；**架构与权限机制缺失**。

##### Nuance DAX → Microsoft Dragon Copilot

> ⚠️ **命名更正**：**DAX Copilot 已于 2025-03-03 与 Dragon Medical One 合并为「Microsoft Dragon Copilot」**；`nuance.com/healthcare/*` 全部 **301 到 `microsoft.com/en-us/health-solutions`**，Nuance 医疗站已不再独立存在。官方文档的实际路径前缀是 **`learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/`**。**不要再用 `nuance.com` 或 `DAX Copilot` 作为唯一检索词。**

- **它解决什么**：环境式（ambient）临床文档草拟 + 面向医生的信息检索（Information Assist）+ 护理端 flowsheet 抽取。目标用户：**作为 Microsoft 开发伙伴，把 Dragon Copilot 嵌入/集成进自己的 EHR 系统**（文档明确"intended for Microsoft development partners"），最终用户为医生与护士。
- **知识库分层（原文术语，均已打开）**：
  1. **输入形态层**：**Dictation**（单说话人，光标级实时，可事后补录）vs **Ambient conversation capture**（多说话人环境录音）；**Session** = 一次 encounter 的 recording bundle。
  2. **生成产物层**：**Ambient note generation**（医师）/** Flowsheet capture**（护士）；原文 "generate recommendations for **discrete orders, conditions, and other clinical data** such as flowsheet documentation, narrative notes, and incident notes"（[about/](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/about/)）。
  3. **结构化交换层（最有参考价值）**：**Dragon standard payload**（JSON）+ **Resource**（"standards used to describe a category of AI-generated healthcare data"）+ **Ontology** —— 原文 "provides a standardized way to represent and reference clinical and non-clinical content generated by Dragon Copilot, ensuring **consistency and interoperability across different applications and services**"；编码系统为 **LOINC / SNOMED-CT**；**且有资源间链接层**："an order resource can be linked to a condition resource as the reason for placing the order"。
    > ⚠️ **证据分级**：主代理亲自打开的 ontology 页只到"ontology 是标准化表示与互操作层 + 两个子页（Coding systems / Document details）"。**`Context` 属性含 `content_type` / `display_description` / `spoken_forms` / `codes`、以及"HPI → LOINC `10164-2`"这一实例，来自子代理对 `.../ontology/coding-systems` 与 `.../resources/context` 的读取，主代理未逐页复核** → 标 `[子代理已打开，主代理未复核]`。引用该字段清单前建议自查一次。
    （[ontology/](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/sdk/partner-apis/dragon-data-exchange/dragon-standard-payload/ontology/) 已打开）
  4. **患者上下文层**：**FHIR / HL7 / EHR resources for Patient, Practitioner, and Encounter**，原文列为 **Optional service data**，"needed by Dragon Copilot to **accurately generate and contextualize clinical content**, as well as to enable seamless workflow integration"，并注明 "Patient identifiable information such as name, DOB and MRN is **associated with the generated AI draft**"（[whitepapers/data-collection](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/data-collection)）。
  5. **外部知识层（= 它的"知识库"）**：**Information Assist** 扩展 —— "access to external information from **trusted sources**"，由 **Azure Healthcare Agent Service** 编排，"to an **approved, vetted, and tested external source** which has been specified in the system"，并全部经过 **Clinical Safeguards engine**（"filters for harmful/non-healthcare related content, hallucinations, and omissions and assures **provenance, verification, and clinically contextualized responses**"）（[whitepapers/transparency-information-assist](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/transparency-information-assist)）。
  6. **EHR 内互操作层**：**SMART on FHIR app launch**、JS/Android/**DAXKit** SDK、partner APIs（含 **ambient audio streaming**）。
- **语料治理（已打开，细节很硬）**：
  - **权威源认定（原文，罕见地明确）**："Research queries are limited **only to vetted sources that have been approved, tested, and included in users source list** in the Dragon Copilot **Settings** menu."；"Only sources that have been **enabled via Settings** can be searched. **Only web-based data are available to search (PDFs referenced by websites are not currently in scope).**"；检索行为 = "Multiple sources will be searched simultaneously"、**"Searches will provide the top three sites from those in scope, prioritizing based on search engine ranking"**。
  - **启用需要四级串联**：该地区已批准（目前**仅美国**、**仅英语**）→ Microsoft 在 Dragon admin center 为组织启用 → 组织管理员为用户启用 → 用户在 Settings > Information Assist 启用并选源。原文另提醒客户"should add, to any allow lists, relevant websites"，因为被引用的站点必须在客户的 allow list 内。
  - **刷新频率 / 增量 / 去重**：**未找到公开资料**。
  - **数据驻留（逐国表，已打开）**：US→US、Canada→Canada、UK→UK、France/Ireland/Belgium→**France, EU**、Germany/Austria/Netherlands/Switzerland→**Germany, EU**；**Dragon Copilot 是 "EU Data Boundary Service"**；**护理功能仅在美国可用且 "the data never leaves the geographic region"**（[whitepapers/privacy](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/privacy)）。
  - **训练政策（必须更正一个常见误解）**：Microsoft **会**用客户数据训练，但**仅用 90 天内完成匿名化的数据**。原文：select Customer Data（含 audio、transcription、clinical documentation、**clinician corrections**）→ "designated Dragon Copilot **research environment**" → "**anonymized within 90 days**"（自采集/生成日起算）→ "**Dragon Copilot's AI/ML models are trained solely on anonymized data.**" 匿名化标准对齐 HIPAA de-identification、加拿大 PIPEDA 与魁北克 Law 25 的不可逆去标识、以及 GDPR 匿名化（含 Recital 26）。另有**严格受限的人审**（仅两类目的：解决客服工单保障运行；确保临床准确性与可靠性，含用人类标注员构造匿名数据集用于模型改进/开发/评估）。撤回同意可工单清除可关联的患者数据，**但此前已生成的匿名数据不会清除**。
  - **合规**：HITRUST CSF、HIPAA、ISO 27001/27017/27018、FedRAMP、SOC 1/2/3、GDPR、PIPEDA、C5、HDS、revFADP、Cyber Essentials Plus；Microsoft HLS 遵循 "**minimum necessary**" 原则；SAW + Security Groups RBAC + 每月审计；日志只读 + Azure Sentinel。删除走 **Microsoft Purview Data Lifecycle Management**。
- **权限/ACL 进检索（已打开）**：
  - **官方明文把访问控制责任交给客户（原文，请直接引用）**："Customers of Dragon Copilot are also **responsible for configuring and managing access controls within their environment** to ensure that **only healthcare professionals with an established therapeutic relationship with a certain patient can access that patient's data**."（[whitepapers/privacy](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/privacy)）
  - **产品内的上下文边界（原文）**：**Context Grounding** —— "The context provided to the LLM is **grounded in specific note data**. **External sources and data from other sessions are not allowed.**"
  - **EHR 侧的实际裁剪样例（最好的一条硬证据）**：**Intelligent diagnosis retrieval from Epic** —— "Diagnoses can be retrieved **only for checked-in patients whose records are not restricted or controlled under enhanced privacy access controls**."；FAQ 进一步确认 "**Will diagnoses be retrieved for patients with restricted records? No**"；且**必须在最后一次录音结束前录入 visit diagnosis**才生效，problem list 不参与（须提升为 visit diagnosis）（[specialty-models/intelligent-diagnoses-retrieval](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/specialty-models/intelligent-diagnoses-retrieval)）。
  - → **结论：DAX/Dragon 是"检索期按患者级隐私标记裁剪"**（restricted record 直接不检索），与 Harvey 的 fail-closed 同属"交付前裁剪"一路；但**权限定义仍由客户的 EHR/组织承担**，Microsoft 不自建权限系统。**索引期 ACL 快照机制未找到公开资料。**
- **评测（已打开，公开度远超预期；这是本案例最有价值的部分）**：**Information Assist 的透明性白皮书给出了完整的两阶段评测设计**（[whitepapers/transparency-information-assist](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/transparency-information-assist)）：
  - **设计前置**："carefully designed and reviewed against **clinical content specifications by clinical content subject matter experts**"。
  - **Stage 1 四个考量维度**：Harmful content（含 hate/fairness、sexual、violence、self-harm、protected material、user prompt injection）；**Groundedness and fabrications**（"is the response based on information in an actual source?"）；**Accuracy**；**Relevance & overreliance**。
  - **红队方法（多维）**：① 有害内容评测由**在性别/地域/文化视角上多样化的评测团队**执行，用大量潜在敏感问题跨风险类别审查；② **UPIA（user prompt injection）与 XPIA（cross domain prompt injection）** 用**自动化 + 人工**测试，且**在三种 grounding 源上分别测：credible / customer / harmful adversarial public website**；③ **RAG 评估**（下面单列）。
  - **RAG 评估的三个判据（原文，可直接对照 Glean 的指标）**：**Groundedness and fabrications**（"assessing capability of grounding responses on the provided evidence sources, while **refraining from using its own 'internal knowledge'** or providing factually incorrect information"）、**Answer relevance**（"the ability to provide a response that is relevant to the user query"）、**Evidence relevance**（"assessing whether the **selected evidence sources** are relevant to the user query"）。三个判据各自配了具体的反例示例。
  - **两级测试规模（原文）**："Tests were run once at **Azure Healthcare Agent (platform service) level (2-5k queries)** and then again at **Dragon Copilot (user-app) level (50-100 queries)**"，含不同措辞与变体。
  - **结果（原文）**：有害内容"results were safe with minimal instances of harmful outputs"；注入攻击"potential risks were well-managed"；**人工 groundedness 评测在 credible sources 上"indicated a low frequency of ungrounded information"**，但**明确警告客户源**："when utilizing **customer sources**, it is important to only use **trusted documents** and **evaluate the system's provided outputs prior to implementation** as the nature and complexity of different customer sources can vary significantly." → **这是一条极有价值的诚实声明：同一套 RAG 管线在可信源上表现好，在客户自建语料上不保证。**
  - **UX 级缓解**：**Chat Safeguards** 生成 AI 签名与免责声明；**每个答案附带对应证据**（"for provenance, explainability, and transparency, allowing end users to verify the correctness of the provided answer"）；答案卡片带 **Feedback** 图标做持续改进。
  - **RAG 判据的对照价值**：其 Answer relevance 与 Glean 的 Answer relevance 同名，Evidence relevance 对应 Glean 的 Context relevance，Groundedness 对应 Glean 的 Groundedness——**两家独立收敛到同一组三指标**，可作为"企业 RAG 评测的最小公约数"。
  - **产品侧质量信号**：Data collection 白皮书把 **Product feedback**（"clinical AI draft ratings and feedback"）与 **Usage analytics** 列为 **Required service data**。
- **关键设计决策**：① **Information Assist 只检索"被批准、被测试、已在系统内登记"的外部源，且客户须把域名加入 allow list**——把"可信语料"变成配置项而非模型判断；② **明确声明"只搜网页、PDF 不在范围内"、并且"只返回在范围内按搜索引擎排序的前三个站点"**——用极其保守的检索范围换取可解释性；③ **两级评测（平台服务 2–5k 查询 → 用户应用 50–100 查询）**，承认平台级与产品级表现不同；④ **红队刻意在"可信源/客户源/有害对抗站点"三种 grounding 源上分别做注入测试**，而非只测干净语料；⑤ **把"客户源可能不 grounding"的警告写在官方透明性文档里**，而不是只写在合同里；⑥ **[推断]** 用 **Ontology + Resource + Context（LOINC/SNOMED-CT）** 把 LLM 输出结构化成可互操作的临床对象（而非自由文本），是为了让下游 EHR 能安全消费——这与 Salesforce 的 ADL、Harvey 的 Resource-level 权限是同一思路的不同切面。
- **出处**（均已打开）：
  - [dragon-copilot/about/](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/about/)
  - [dragon-copilot/whitepapers/privacy](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/privacy)
  - [dragon-copilot/whitepapers/data-collection](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/data-collection)
  - [dragon-copilot/whitepapers/transparency-information-assist](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/transparency-information-assist)
  - [dragon-copilot/sdk/partner-apis/dragon-data-exchange/dragon-standard-payload/ontology/](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/sdk/partner-apis/dragon-data-exchange/dragon-standard-payload/ontology/)
  - [dragon-copilot/specialty-models/intelligent-diagnoses-retrieval](https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/specialty-models/intelligent-diagnoses-retrieval)
  - 文档 TOC：`https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/toc.json`
  - 子代理另打开（本代理未逐页复核，标注 `[子代理已打开，主代理未复核]`）：`whitepapers/`、`whitepapers/security`、`whitepapers/transparency`、`specialty-models/specialty-specific-content`、`specialty-models/clinical-note-status`、`sdk/glossary`、`sdk/embedded-desktop/smart-fhir-app-launch`、`sdk/partner-apis/ambient-audio-streaming/`、`ontology/coding-systems`、`resources/context`、`extensions/development-concepts`，以及两条 news.microsoft.com 新闻稿（2025-03-03 合并公告、2025-10-16 护理与伙伴扩展）
- **证据强度**：**官方文档（隐私/数据收集/透明性白皮书 + 本体 + 功能页），RAG 评测方法学公开度与 Glean 同级**。
- **监管口径（已打开原文）**："**Dragon Copilot (physician) is UKCA marked as a Class I medical device in Great Britain. In all other jurisdictions, Dragon Copilot is not designed, intended, or made available as a medical device.**" → 即**不是** FDA 获批器械。子代理以 openFDA API 查证无 FDA 510(k)（`api.fda.gov/device/510k.json?search=applicant:"Nuance"` 仅命中一家无关的 "Nuance Medical, LLC"；`device_name:"Dragon"` 8 条全无关）——**该检索结论标注为 `[子代理 API 查询，主代理未复核]`**。

##### 命名与路径更正（两处必须修正的历史误判）

1. **`nuance.com/healthcare/*` 不是"打不开"而是"已收编"**：全部 **301 → `microsoft.com/en-us/health-solutions`**；DAX Copilot 已于 **2025-03-03** 并入 **Microsoft Dragon Copilot**。正确文档前缀是 `learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/`。可用微软自家文档搜索 API 定位：`https://learn.microsoft.com/api/search?search=<关键词>&locale=en-us`。
2. **Abridge 的 "Contextual Reasoning Engine" 确实存在，且是其最核心命名层**：正确 slug 带 `abridge-` 前缀 —— `https://www.abridge.com/abridge-contextual-reasoning-engine`（本代理已亲自打开复核，四个子层原文见上）。最初 `abridge.com/contextual-reasoning-engine` 的 404 是 slug 猜测错误，**不构成"该术语不存在"的证据**。

##### 关于文献引用的诚实边界

子代理做了 PubMed 全库检索，结论是：**不存在具名的、由 Kaiser Permanente 发表的 DAX/ambient 结局试验**，只有 Kaiser 关联单位的**评论**（*Ann Intern Med* 2026;179(6):898-899 与 *JAMA* 2026;335(16):1393-1395）。**请勿引用"Kaiser 研究"作为 DAX 效果证据。** 真正可引用的具名研究（子代理经 NCBI E-utilities 读取同一记录，标注 `[子代理 API 读取，主代理未复核]`，PMID 可直接核验）中，**对 DAX 最重要的两条是**：
- **Lukac 2025, *NEJM AI* 2(12), PMID 41497288** —— UCLA 三臂 RCT（238 医师/14 专科，DAX Copilot vs Nabla vs 常规照护）：Nabla −9.5% time-in-note（P=0.02），**DAX −1.7%（P=0.66，不显著）**。**这是目前唯一 DAX 的 RCT，且结论对 DAX 不利。**
- **Webb 2026, *Appl Clin Inform* 17(1):118-126, PMID 41734793** —— UT Southwestern 急诊科交叉试验，**DAX 与 Abridge 正面对撞**：DAX 工作负担降幅更大（1.5 vs 2, p=0.025）、PDQI-9 偏 DAX（39 vs 36.5, p=0.011），**但校正模型显示差异主要来自 order effect 而非工具本身**。→ **这条对"两家厂商对比"的结论最关键：正面对撞下未观察到工具本身的可靠差异。**
- 其他可引用项：Haberle 2024 *JAMIA* 31(4):975-979 PMID 38345343（Intermountain，after-hours EHR 显著恶化）；Bundy 2024 *J Gen Intern Med* 39(15):2995-3000 PMID 38937369（Atrium，明确点名 DAXC 会 "imagine or misgender patients, offer unsolicited and inappropriate diagnoses, and mistake critical details"）；Ma 2025 *JAMIA* 32(2):381-385 PMID 39688515 与 Shah 2025 *JAMIA* 32(2):375-380 PMID 39657021（Stanford 两项）；Svetly 2026 *Appl Clin Inform* 17(4):747-753 PMID 42618038（AdventHealth，note 时间 −26.2%）；Wendt 2025 *Future Healthc J* 12(3):100450 PMID 40896303（Providence 阶梯楔形，Nuance 提供免费 license 已披露 COI）；Rotenstein 2026 *JAMA* 335(16):1408-1417 PMID 41920565（UCSF 多中心，8581 医师，**摘要未具名厂商**，COI 提及 Abridge 顾问角色与 MGB 对 Abridge 的投资 → **不要归给 DAX**）。

---

## 未找到 / 存疑清单

| 项 | 状态 | 原因 |
|---|---|---|
| Salesforce **Data Cloud / Data 360 内部**的 data streams / DLO / DMO / vector index 等术语 | **未找到（可打开的）官方原文** | `help.salesforce.com` 全站 JS 渲染（只回 "Loading"），相关页只在该站。**已解决的部分**：非结构化知识层已由开发者文档确证为 **Agentforce Data Libraries (ADL)** |
| Salesforce 的权限/ACL 如何进检索（索引期 vs 检索期） | **未找到公开资料** | 帮助中心打不开；开发者指南未覆盖权限裁剪。仅得泛化"least privileged access / core access controls"表述，不足以支撑机制描述 |
| Salesforce 的评测**方法学**（黄金集构造、人工评审、离线/在线指标） | **未找到** | **已获取的部分**：三套测试入口的格式规格（UI/CSV、CLI/YAML、API/XML）与自定义评测的完整算子清单已在开发者文档中查证；缺的是 golden set 构造与人工评审流程 |
| Salesforce 的语料刷新频率、增量策略、去重、驻留区域 | **未找到公开资料** | 同上 |
| Microsoft 语义索引的评测方法 | **未找到公开资料** | 官方页面只有 item 级索引状态校验工具与"不擅长的查询类型"清单 |
| Notion AI / Enterprise Search 的评测方法 | **未找到公开资料** | 官方仅给能力边界声明 |
| Sana 的去重、权威源认定、逐连接器刷新频率、评测方法 | **未找到公开资料** | 官方只有产品页与安全 FAQ |
| Sana 是否有图谱层/记忆层的命名 | **未找到** | 无 "knowledge graph" 类官方术语 |
| Dust 的 ACL 机制（索引期快照 vs 检索期校验）、去重、权威源、驻留、评测指标 | **未找到公开资料** | Spaces / Access Controls 页在 llms.txt 中确认存在但正文未打开 |
| Atlassian 逐连接器刷新频率、ACL 变更生效时延、数据驻留 | **未找到公开资料** | 产品页无此粒度；未定位到对应 support/ 文档 |
| Atlassian "44% 更准 / 48% 更少 token" 与 "60% more successful" 的度量口径 | **存疑（数字已确证，方法未公开）** | 官方博客与产品页给出数字但无指标定义、无黄金集、无评审流程，不可复现 |
| Glean 是否在检索期对上游做二次权限校验 | **存疑** | 官方只写 indexed 模式用"permission snapshot"，live/hybrid 请求时取源；未描述检索管线的二次校验 |
| Glean "Enterprise Search Evaluation 2026"（~2× vs ChatGPT、1.6× vs Claude）的具体方法 | **仅搜索结果，未打开原文** | [blog/enterprise-search-evaluation-2026](https://www.glean.com/blog/enterprise-search-evaluation-2026) 仅在 Brave 结果中出现，本会话未打开正文 |
| Sierra：索引期 per-customer 知识隔离机制（命名空间/collection/元数据过滤）、chunk 去重、数据驻留区域枚举、权威源分级 | **未找到公开资料** | `docs.sierra.ai` 需登录（仅返回登录墙）；`trust.sierra.ai` 为 JS 渲染无正文（已打开但未取回内容）。公开页只列合规资质，未给托管区域 |
| Decagon：检索期 permission trimming / tenant isolation 机制、权威源分级、驻留区域、索引期增量与去重 | **未找到公开资料** | 官方只公开连接器侧凭据与 scope（JIT JWT + minimal privilege） |
| Decagon 的 "durable memory" 措辞 | **该措辞未找到官方来源** | 官方术语是 **user memory**；请勿在报告中写 "durable memory" 并归于 Decagon |
| Harvey：是否在**索引期**把 DMS/Intapp ACL 落到 chunk 级元数据 | **未找到公开资料** | 公开只说 permission-aware + retrieval/context/output 三层强制 + 查询期继承用户权限并逐文件审计 |
| Harvey：公共源刷新频率与法规版本语义、语义级去重 | **未找到公开资料** | 两篇博客在本地抓取时被截断（scaling-ai-evaluation-through-expertise 的 Data Management 段之后、biglaw-bench-retrieval 的 LLM-based retrieval 第三点） |
| Sierra/Decagon/Harvey 的**索引期文档级 ACL** | **三家均未找到公开资料** | 这是垂直厂商公开度的共同缺口；Harvey 只公开"查询期继承用户权限 + 三层强制" |
| Harvey：公共知识源刷新频率与法规版本语义、语义级去重 | **未找到公开资料** | 公开只说 Data Factory 的扩张（6→60+ 法域、20→400+ 源）与 attorney 逐源过审 |
| Harvey：评估数据服务的完整设计 | **未找到（页面截断）** | `scaling-ai-evaluation-through-expertise` 在 "Data Management" 段之后被截断；`biglaw-bench-retrieval` 在 "LLM-based retrieval" 第三点处被截断 |
| Firecrawl / DuckDuckGo / Brave 检索通路 | **工具故障（已记录）** | Firecrawl keyless 429（retry_after ≈ 86000s）；DuckDuckGo HTML/lite 弹人机验证；Brave HTML 首次可用、随后 429；exa_search 未配置 Key。**可用通路**：`web_fetch` 直连官方文档 + **`read_page` 的本地直抓回退**（可绕开 Firecrawl 取整页正文）；子代理另用「官方 sitemap.xml 枚举 URL」绕开搜索引擎 |
| ~~Nuance DAX / DAX Copilot 的全部子问题~~ | **已解决（原判断为误判，已撤销）** | 真因是命名与路径过时：`nuance.com/healthcare/*` **301 到 `microsoft.com/en-us/health-solutions`**，DAX Copilot 于 **2025-03-03** 并入 **Microsoft Dragon Copilot**，正确文档前缀为 `learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/`。主代理已亲自打开并复核 about/、whitepapers/privacy、whitepapers/data-collection、whitepapers/transparency-information-assist、ontology/、intelligent-diagnoses-retrieval 共 6 页 → 详见 [8d] 节 |
| ~~Abridge 的 "Contextual Reasoning Engine" 术语~~ | **已解决（原判断为误判，已撤销）** | 正确 slug 带 `abridge-` 前缀：**`https://www.abridge.com/abridge-contextual-reasoning-engine`**（主代理已亲自打开复核）。该页正是 Abridge 最核心的命名层，含 **EHR CONTEXT / PREDICTED PROBLEMS / ORDERS / CODING** 四个子层与 **Linked Evidence** → 详见 [8d] 节 |
| Abridge：架构/检索实现、EHR 集成协议（FHIR/HL7/Epic）、刷新频率、去重、驻留承诺 | **未找到公开资料** | 公开页只到"Queries run entirely inside Abridge's architecture. PHI never leaves it"这一治理性表述 |
| Abridge：具体准确率/遗漏率数字、黄金集规模、医生评审人数 | **未找到（可能在未打开的 /ai/publications 与 /whitepapers）** | 本次已打开其技术博客的**评测框架**（when/what/how、内在 vs 结果双轴、LLM judge 对齐人审），但未打开具体的论文与白皮书 |
| 医疗两家的**权限/ACL 进检索机制** | **Abridge 未找到；DAX 已找到（部分）** | **Abridge** 只公开 "Clinician-in-the-loop" 与 PHI 不出架构，**索引期/检索期机制未找到**。**DAX 有明文**：客户负责配置访问控制（"only healthcare professionals with an established therapeutic relationship…"）；**产品内 Context Grounding 明确 "External sources and data from other sessions are not allowed"**；**Epic 诊断检索仅对"未被增强隐私访问控制限制的记录"生效**（FAQ 直答"restricted records → No"）；但**索引期 ACL 快照机制未找到** |
| DAX / Dragon Copilot 的**索引期 ACL 快照机制**、语料刷新频率、增量、去重 | **未找到公开资料** | 官方文档覆盖到"检索期按患者隐私标记裁剪"这一层，未公开索引侧实现 |
| DAX 的**具体准确率数字** | **未找到（官方只给质性结论）** | 透明性白皮书称 credible sources 上"low frequency of ungrounded information"、有害内容"safe with minimal instances"，但**未给数字**；这与 Abridge 公开 97%/82%/99.5% 形成对照 |
| 文献侧：**Kaiser Permanente 具名 DAX 结局试验** | **不存在（子代理 PubMed 全库检索）** | 仅有 Kaiser 关联单位的**评论**（*Ann Intern Med* 2026;179(6):898-899；*JAMA* 2026;335(16):1393-1395）。**请勿引用"Kaiser 研究"作为 DAX 效果证据**；应改引 UCLA 三臂 RCT（PMID 41497288，DAX −1.7%、P=0.66 不显著）与 UT Southwestern DAX-vs-Abridge 交叉试验（PMID 41734793，差异归因于 order effect） |
