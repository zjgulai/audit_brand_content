# 企业级 / 垂直领域 Agent 产品的知识库架构与「知识 → Agent」路径

> **调研目的**：为跨境电商/母婴品牌（Momcozy）的飞书内容合规审查 Agent「**守衡**」提供知识库分类、建设与演进的外部参照。
> **调研方法**：所有外部事实均来自实际检索并打开的一手页面（官方文档、官方工程博客、arXiv 论文、监管/司法文书）。每条事实标注证据强度；凡属研究者推断，一律以 `[推断]` 标注，不与事实混排。
> **调研日期**：2026 年（本机系统时间），报告即成于当次检索。
> **工具限制声明（重要，影响证据强度）**：本次调研期间，本机检索工具链出现故障——`web_search` / `read_page` 依赖的 Firecrawl 免费额度当日耗尽（HTTP 429），`exa_search` 未配置 API Key，故检索改由 `web_fetch` 直连 Brave Search / DuckDuckGo HTML 端点完成。部分官方文档站（`developers.perspectiveapi.com`、`help.salesforce.com`、`platform.openai.com` 等）为 JS 渲染或对自动化访问返回 403，**这些来源只能读到搜索引擎摘要，已在正文逐条标注为「仅搜索摘要，未打开原文」**。凡标注此字样的结论，请勿当作一手证据使用。
>
> **后来找到的三条可用通路，已用于补证，并在此记录以备复核者复用**：① `read_page` 的**本地直抓回退**可绕开 Firecrawl 取到整页正文；② 用官方 **`sitemap.xml` 枚举 URL** 绕开搜索引擎定位文档；③ 微软自家的文档搜索 API（`https://learn.microsoft.com/api/search?search=<关键词>&locale=en-us`）+ **NCBI E-utilities**（文献 PMID）+ **openFDA API**（器械 510(k) 查证）。**其中第 1 条直接改变了两个案例的结论**——见下方两条更正。
>
> **两条由「工具失败被误读为事实缺失」导致的更正（本报告主动撤销初稿判断）**：
> 1. **Nuance DAX 并非"官方页全部打不开"**。真因是**命名与路径已过时**：`nuance.com/healthcare/*` 全部 **301 → `microsoft.com/en-us/health-solutions`**，**DAX Copilot 已于 2025-03-03 并入「Microsoft Dragon Copilot」**，正确文档前缀是 `learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/`。撤销后，DAX/Dragon Copilot 从"证据最薄"变成**评测方法学公开度与 Glean 同级**（见第 3 节）。
> 2. **Abridge 的 "Contextual Reasoning Engine" 确实存在**，且是其最核心的命名层。初稿判为"不存在"，实为检索词少了 `abridge-` 前缀（正确 slug：`abridge.com/abridge-contextual-reasoning-engine`）。
>
> **这两条更正的方法论意义大于内容本身**：它们共有的失败模式是**把"我没检索到"当成了"它不存在"**。这正是守衡这类判定系统最容易犯的错（"未命中规则"≠"不违规"），也是本报告给每条结论都标证据等级的原因。

---

## 0. 一页纸结论（TL;DR）

1. **企业 Agent 的知识库不是"一个库"，而是四种物理形态不同的东西**：①**权限内的语料索引**（检索层）；②**结构化判定资产**（规则/分类法/阈值）；③**先例与裁决资产**（案例库、申诉记录）；④**程序性知识**（Skill / Playbook / 工具契约）。前两者是"事实"，第三者是"判断"，第四者是"动作"。[推断：这是本报告跨案例归纳的结论，非任一厂商的官方表述]
2. **权限不是检索的后置过滤器，而是索引的第一等维度**。Microsoft 的语义索引在检索期继续沿用用户身份访问边界（官方原话："we continue to honor the user identity-based access boundary so that the grounding process only accesses content that the current user is authorized to access"），并明确"索引不改变内容的访问权限"。**对守衡的含义**：飞书多维表格作为知识库载体时，表的可读范围本身即是一层权限语义，必须在设计期显式化，而非事后加过滤。
3. **规则与先例必须分开存，且都要带版本与生效时间**。Google Perspective API 的官方 FAQ 明确提示：模型更新后需要重新校准阈值，且"我们无法在每次更新时通知用户"——**阈值会随模型漂移**，这是合规审核类系统必须内置的假设。
4. **权威源认定（authoritative source）是知识库的第一性设计问题，而不是数据清洗问题**。公开失败案例中，最贵的错误几乎都不是"检索不到"，而是"检索到了过期/错误/非权威的那一份，然后系统照答"。
5. **评测必须早于知识库规模化**。Anthropic 给出的 Skill 开发建议第一条就是 "**Start with evaluation**"：先在代表性任务上跑出能力缺口，再针对缺口增量建设。这条对本项目直接适用。
6. **知识 → Agent 的路径不是"把知识喂给模型"，而是"把知识编译成可发现、可按需加载、可执行、可审计的资产"**——这就是 Agent Skills 的 progressive disclosure（三级渐进披露）与 Anthropic 的 "just in time context" 策略所共同指向的形态。
7. **权限的"时点"必须是一个显式工程参数，而不是默认行为。** 十二家案例全部收敛到"权限是一等维度"，但**生效时刻**从"仅 full crawl 更新、最长 24 小时"（Microsoft 官方原文）到"交付前 last-mile checks"（Atlassian 官方原文）横跨三个数量级。**守衡必须声明自己属于哪一档**：飞书多维表格的"表可读范围"是同步时求值一次（索引期快照），还是每次判定向飞书现问（交付前校验）。**完整光谱见 §2.0.1（六家）与 §3.6.1（含垂直五家）。**
8. **评测是本行业最公开的缺口，也是守衡最可能形成复利的一层。** 十二家里只有 Glean 公开到指标级，且它的数字极具信息量：**人类标注者彼此一致率仅 79%（Glean 自己把它当作自动评测的上限）、AI Evaluator 与人类一致率 74%**。`[推断]` 因此任何声称显著高于 ~80% 的自动判定准确率，都必须先解释它的 golden set 是怎么造的。
9. **可引用的"最小公约数"已经出现：Glean 与 Dragon Copilot 独立收敛到同一组三指标**——**Context relevance / Answer relevance / Groundedness**（Dragon Copilot 的措辞是 Groundedness and fabrications / Answer relevance / Evidence relevance）。两家一个来自企业搜索、一个来自受监管的临床文档，来源路径完全不同。**建议守衡的评测表直接采用这组三分法，各自挂自己的阈值与 golden set。** 另有一条同等重要的衍生结论：**四家的黄金集都不是凭空设计的，而是从业务痕迹里派生的**（Harvey 从计费工时、Sierra 从前一日对话、Abridge 从医生编辑动作、Dragon Copilot 从匿名临床文档）——见 §3.6.2。
10. **"关键分支不交给 LLM 解释"是大厂在官方文档里写下来的结论，不是本报告的推断。** Salesforce Agent Script 原文：workflows "**that don't rely on interpretation by an LLM**"；OpenAI guardrails 手册原文：把 guardrails "**combine with rules-based or more traditional machine learning models**"。两家独立来源、同一结论——**守衡把"确定性检查"与"模型判定"分开是对的方向，需要的只是把这条边界写进契约并让它可验证。**
11. **评测集不必凭空设计，可以从"业务里已经完整记录的东西"里派生。** Harvey 的 **BigLaw Bench** 直接源自法律行业的 **time entry**（"Because **all work is billed**…"）。`[推断]` **守衡的等价物是"每一次人工改判"**——它天然带上下文、天然有标签、天然在增长，这也是缺口 G1/G2 之所以是最严重缺口的原因。
12. **本报告在三处主动撤销了自己初稿的判断**（见 §1.1）：①Nuance DAX 并非"官方页打不开"，而是**命名与路径已过时**（DAX Copilot 于 2025-03-03 并入 **Microsoft Dragon Copilot**）；②Abridge 的 "Contextual Reasoning Engine" 确实存在，是初稿检索词少了 `abridge-` 前缀；③**Meta 广告审核与申诉原文"无法取得"是错的——项目自己的 `_evidence/R1/` 里早已存有该批页面**。**一并记录在案，因为它们共有的失败模式是"把检索失败误判为事实缺失"**——这正是守衡这类系统最容易犯的错误，也是本报告主张所有结论都要带证据等级的原因。

13. **"申诉翻案率无人公开"这个结论只在厂商侧成立，平台侧早已是成熟惯例。** 本报告初稿在 §3.6.3 把它写成"全行业空白"，**这是本报告的第二次自我证伪**：Meta 按季度公开 `Content Actioned` / `Content Appealed` / `Content Restored with appeal` / `Content Restored without appeal` **四个并列指标**，翻案率可直接算出（**研究者本人在项目内 CSV 上独立复算：Facebook 逐季 23–29%，Instagram 2026Q2 为 22.60%**），并同时公开**精度区间与假阳性绝对数**；TikTok 公开 `Videos restored`（2026Q1 为 8,838,710 条，占 4.80%）与 `Removal rate within 24 hours`（94.4%）。**分层表述应为「厂商侧空白、平台侧已成惯例」，成因是问责对象不同**——平台对内容决定负法定透明度义务，企业软件只需对采购方负责。**真正的空白是"裁决回流到规则"这一环（§5 · C4）。**

14. **申诉台账的字段应当直接照 Meta 的四指标设，并必须把"平台自撤"与"申诉翻案"分开计。** `Restored without appeal` 是"我们主动纠错"的唯一度量，与"用户推着我们纠错"的改进含义完全不同。另有一条同等重要的纪律：**精度必须以「区间 + 假阳性绝对数」发布**（Meta：Precision 90.80–91.85%，False Positive 3,020–3,080 万）——单点精度（"准确率 9x%"）无法被反向引用，因此不构成可问责的披露。

---

## 1. 元信息：本次调研的证据分级约定

| 标记 | 含义 |
|---|---|
| 【一手】 | 研究者本人 `web_fetch` 打开并读到正文的页面 |
| 【一手/PDF或摘要】 | 打开的是论文摘要页（arXiv abs）而非全文 |
| 【官方·仅搜索摘要】 | 官方页面存在且搜索引擎返回其原句，但正文因 JS 渲染/403 未打开 |
| 【二手】 | 第三方媒体或分析文章 |
| `[推断]` | 研究者的推理，不构成事实 |
| `[待确认]` | 信息不足，不能下结论 |

### 1.1 三次同类失败：把「我没检索到」当成了「它不存在」

本报告在成稿过程中**三次**把检索失败误判为事实缺失，全部已撤销并改写。**这三条记录留在报告里，因为它们指向的正是守衡最容易犯的错（"未命中规则" ≠ "不违规"）：**

| # | 初稿误判 | 真相 | 成因 |
|---|---|---|---|
| 1 | Nuance DAX「官方页打不开」 | 命名与路径已过时：DAX Copilot 于 2025-03-03 并入 **Microsoft Dragon Copilot** | 按旧名检索（见 §3.5） |
| 2 | Abridge「Contextual Reasoning Engine 不存在」 | 确实存在，页面 slug 为 `abridge-contextual-reasoning-engine` | 初稿检索词少了 `abridge-` 前缀（见 §3.4） |
| 3 | Meta 广告审核与申诉原文「无法取得」 | **项目内 `_evidence/R1/` 早已存有该批页面**（`meta-ad-bhc-ad-review.md` 等，抓取日期 2026-09-15，含 "review process starts automatically after you create or edit an ad"、"relies primarily on automated technology"、"in some cases, to manually review ads"） | **渠道差异**：项目 R4 走本机代理 `127.0.0.1:7890` + 完整浏览器头，本轮裸 `curl` 被 400/403 拦下 |

`[推断]` **第三条最值得警惕**：它所谓的"事实缺失"并不在外部世界的某处，而**就在本项目自己的证据目录里**。因此在写下任何"未找到公开资料"之前，应当先检索本项目已存证据（`research/*/_evidence/`）。

### 1.2 两条可复用的取证手段（本轮新增，供后续复核者复用）

当目标页面 404 / 403 / JS 渲染失败时，本轮实际奏效的路径不是换搜索引擎，而是**换发现渠道**：

1. **Wayback CDX 索引 API** —— 按域名批量列出历史快照 URL，把"猜测的 404"换成"真实存在过的路径"。
2. **`robots.txt` → `sitemap`** —— 从站点自述的 sitemap 取得真实 URL 全集，再定向抓取。

`[推断]` 两条的共同点是：**不去猜 URL，而是让站点自己交出 URL**。它们与 §1.1 属于同一类纪律 —— **在断言"没有"之前，先把"找"这件事做穷尽**。

---

## 2. 案例族 A：企业知识助手类产品（含逐案证据卡）

> 子调研的详细卡片见 `kb2agent-research/raw/A-企业知识助手案例.md`。本节收录可核验的核心结论。

### A1. Microsoft 365 Copilot + Microsoft Graph 语义索引（本报告证据最扎实的案例）

**它解决什么**：把租户内的组织数据（SharePoint/OneDrive/邮箱/Teams）变成可被 LLM grounding 的检索基底，让 Copilot 在企业既有的安全合规边界内作答。

**知识库怎么分层**（均为官方术语，【一手】[Semantic indexing for Microsoft Copilot](https://learn.microsoft.com/en-us/microsoftsearch/semantic-index-for-copilot)）：

| 层 | 官方描述 | 关键事实 |
|---|---|---|
| **Lexical index（词法索引）** | 传统的关键词匹配索引 | 与语义索引并存，不是被替代 |
| **Semantic index（语义索引）** | "maps your organization's data into an advanced lexical and semantic index"；由 Microsoft Graph 内容生成，是**向量化**索引 | 用户可"search through billions of vectors" |
| **Tenant-level index（租户级）** | 组织范围索引，由**文本型 SharePoint Online 文件**生成 | 每位 Copilot 付费客户都有；**索引过程无需管理员介入，且"can't be disabled"** |
| **User-level index（用户级）** | 个人工作集索引：邮件、提及你的文档、你评论或分享过的内容 | 用户级索引信息存储在该用户邮箱所在地 |
| **Connector data（连接器层）** | 通过 Copilot connectors 把外部/第三方内容导入 Microsoft Graph 后再索引 | 官方明确"works best when the connector content is text rich" |
| **Metadata / column signals（元数据信号层）** | SharePoint 列元数据作为检索相关性信号 | 仅在查询被 scope 到某个库/文件夹时生效 |

**权限/ACL 怎么进检索**（这是最有价值的一段，官方原文）：
- "When data is indexed, we **continue to honor the user identity-based access boundary** so that the grounding process only accesses content that the current user is authorized to access."
- "it only surfaces the results to a user **if the user already has access to the content controlled by role-based access control**."
- "indexing data **doesn't change access permissions** to content"。
- 第三方连接器内容进入 Graph 后同样"**while maintaining access controls for content**"。
- 管理层面上，官方建议的治理动作是"**reduce oversharing**"与"right size user access to data"，并把 **Sensitivity labels（敏感度标签）**纳入 search trimming（过滤与应用侧规则）。

**语料治理与刷新**（官方明确的时间语义）：
- 新建于 SharePoint、且经站点继承可被 **2 人及以上**访问的文档：**按天索引**。
- 已索引文档被**更新**时：变更**立即索引**。
- 用户邮箱中用户创建的文档：**近实时索引**。
- 支持排除：可由管理员把 SharePoint 站点从租户级索引排除；**但排除动作同时作用于 Microsoft Search 与语义索引，无法只排除其一**。
- 支持的数据驻留：租户级索引存放于 SharePoint 站点所在区域；EUDB 客户存于 EU/EFTA 数据中心；multi-geo 组织遵守地理边界。
- 不支持的边界（同样是重要设计约束）：委托邮箱、共享邮箱、归档邮箱数据、归档 SharePoint 数据**均不支持**。

**关键设计决策（可迁移）**：
1. **索引期不做权限裁剪，检索期强制身份边界**——用"渲染时收敛"替代"索引时复制多份"。[推断：这是为了让权限变更即时生效，避免索引副本与 ACL 快照不一致]
2. **元数据不是装饰，是检索信号**：只在查询被 scope 时启用列元数据，兼顾相关性与成本。
3. **默认开启 + 不可关闭 + 排除粒度有限**：把"可用性"放在"可配置性"之前，代价是治理只能靠前置的 over-sharing 治理。
4. **"文本富集"作为接入门槛**：官方承认 connector 内容"text rich"时效果最好——等于承认非文本/半结构化语料的接入成本高。

**评测**：官方该页未给出公开评测方法。`[待确认]`

**对守衡的直接含义** `[推断]`：守衡的知识库载体是飞书多维表格，其权限模型（谁能读哪张表、哪个视图）在事实上承担了 Copilot 中 "item-level permission + RBAC" 的角色。因此**"哪张表谁能读"必须作为判定引擎的一等输入被记录**，而不是靠"大家都能看知识库"的隐含假设。

---

---

### 2.0 六家产品的分层对照总表

> 以下所有术语均为**产品官方原文术语**，逐条可追到 URL（详见 `raw/A-企业知识助手案例.md` 的逐条出处）。
> **★ 标记的两列是本次调研认定的真正分化点**：`权限层` 的**时点**（索引期快照 / 交付前校验 / 运行期裁剪）与 `评测层` 的**公开度**。连接器、索引、行为三层已经商品化，术语不同而结构同构。

| | **连接器/语料层** | **索引/图谱层** | **取数模式层** | **权限层** | **行为层** | **评测层** |
|---|---|---|---|---|---|---|
| **Glean** | Connectors：Native / Web history / Push API / Partner；**逐连接器公布刷新频率**（GitHub/GitLab webhook 变更 ≤5m；Slack webhook 近实时；Confluence 新版本 5m/旧版本 1h；**Salesforce 增量 10m、全量 28d**；Gmail 活动驱动、全量 28–30d；Website 默认 28d） | search index + **Knowledge Graph**（Content / People / Activity）+ **personal graph**＝**system of context** | **Indexed / Live / Hybrid**（三分法） | ★ **mirror permissions**：抓取每个源的 **permissions map**；indexed 模式用爬取时镜像的 **permission snapshot**；五个 crawl 类型中 **Activity crawl 明确覆盖 "permission modifications"**。**未描述检索管线是否二次校验**（`[待确认]`） | Assistant / Agents / Tools / **Skills** | **AI Evaluator**（租户内跑） |
| **Microsoft 365 Copilot** | Copilot connectors：**Synced**（入 Graph 并索引）vs **Federated（MCP）**（**不索引**） | **Semantic index**：tenant-level（SharePoint 文本文件）+ user-level（邮箱/工作集），**物理分置** | 无显式三档；由 Synced/Federated 承担同样的取舍 | ★ 逐 item **必填 `acl` 数组**：`accessType`(grant/**deny**) × `type`(user/group/everyone/**everyoneExceptGuests**/externalGroup)，**deny 可撤销经 group 继承的权限**；检索期"honor the user identity-based access boundary"；**但 ACL 变更仅 full crawl 生效、最长 24h** | declarative agents / Copilot Studio agents | 无公开评测方法；只有 **Index browser** 运维校验 |
| **Atlassian Rovo** | Teamwork Graph Connectors（100+ 开箱；Forge 自建）；**Smart Link 型 vs 内容索引型两档** | **Teamwork Graph**（"Atlassian Cloud Platform's data intelligence layer"，1500 亿对象与关系） | 无显式分档；以"at the speed of change"表述 | ★ **"Teamwork Graph runs last-mile checks, so users and apps only get access to the data they're entitled to"**（**交付前最终校验**，与 Microsoft 正面对照）；自建连接器 "Data enters the graph with its **access controls intact**" | Rovo Search / Chat / Agents / Studio；**CLI + MCP（可写回）** | 只有数字（44% 更准 / 48% 更少 token、60% more successful），**无指标定义、无黄金集、无评审流程 → 不可复现**，请标「厂商宣称口径」 |
| **Notion AI** | **AI Connectors**（Slack/Drive/Jira/Gmail/Teams/SharePoint/GitHub/Linear…） | 托管向量库（官方点名 **Turbopuffer**）+ Agent 的 memory system（**用 Notion pages 与 databases 承载**） | 无显式分档 | ★ "honor existing permissions"；第三方按 **permissions mapping between each connected app and Notion** 摄入；Agent **"acts as you"**；同期上线 **database row-level access** | Enterprise Search / Agents / Custom Agents / MCP（可写回） | 无公开方法；只有能力边界声明 |
| **Sana** | integrations / connectors（100+）+ direct upload | "unifies your company's data"、real-time indexing；**无图谱层术语** | 无显式分档 | 三种入法决定权限语义：**direct upload / private integration（每用户自认证）/ shared integration（admin 定）** | Sana Agents + Enterprise search | 排序模型用**内部专用训练集**；有用户反馈与 Knowledge verification 设置，**无公开指标** |
| **Dust.tt** | Data sources：**Connections / Folders / Websites**；对象为 **Documents / Chunks** | 无图谱层 | 把检索拆成**四个工具**：**Search（语义 RAG）/ Include data（倒序填窗）/ Table queries（转 SQL）/ Extract data（单次 ≤500k tokens）** | **Spaces** 承载权限；"Discover Knowledge **follows the user's permissions** and the spaces available to the agent" | Discover Knowledge / Discover Skills / Discover Tools；**Agent Memory / Skills / Pods / Context Compaction** | 只有 thumbs up/down 反馈 API；官方建议自行 A/B |

**这张表本身就给出结论**：六家的**连接器层、索引层、权限层、行为层**几乎人人都有；**取数模式层（Indexed/Live/Hybrid）只有 Glean 显式命名**；**评测层只有 Glean 公开到指标级**。`[推断]` 这两个"少数派"恰好都是最贵的部分——前者要维护多套并发取数管线，后者要在客户私有语料上建评测。

#### 2.0.1 真正分化的两列之一：权限的**时点**是一条光谱

六家官方措辞按"权限生效的时刻"排序，可以排成一条连续光谱（左粗右细）：

| 档位 | 产品 | 官方原文措辞 | 用户看到过期权限的最坏时长 |
|---|---|---|---|
| **索引期快照（最粗）** | **Microsoft 365 Copilot** | "Permissions updates occur during a **full crawl, not an incremental crawl**"；"ACL 变更最长 24h 才反映" | **≤24 小时**，且需**人工触发 full crawl** |
| **索引期快照 + 可切换** | **Glean** | indexed 模式用 "the **permission snapshot** that was mirrored during crawling"；live/hybrid 请求时取源 | 由**连接器刷新周期**决定（Salesforce 增量 10m / 全量 28d） |
| **接入方式即权限语义** | **Sana** | **private integration**：每用户自认证，只见自己有权的 scope；**shared integration** 由 admin 定 | 无明说 `[待确认]` |
| **身份代理** | **Dust.tt** | 检索 "**follows the user's permissions** and the spaces available to the agent" | 无明说 `[待确认]` |
| **身份代理 + 内容侧时限** | **Notion AI** | Agent "**acts as you**"；且给出硬性时间预算：首次摄取 **≤72h**、新内容 **≤3h**、回溯窗口 **1 年**、断连 **1 天内删除** | **≤3 小时**（内容侧，非权限侧） |
| **交付前最终校验（最细）** | **Atlassian Rovo** | "Teamwork Graph runs **last-mile checks**, so users and apps only get access to the data they're entitled to" | **请求时**（无窗口） |

`[推断]` **这张表对守衡的直接价值**：飞书多维表格既然同时是"知识库载体"和"权限实体"，那么「表的可读范围」究竟在**什么时候**被求值——是同步到本地库时求值一次（索引期快照），还是每次判定时向飞书现问（交付前校验）——**是必须显式选定的一个工程参数，而不是默认行为**。可参照 Glean 的做法，把它做成**可配置的三档**（本地快照 / 混合 / 实时），并在每条判定记录里写下本次用的是哪一档。

#### 2.0.2 真正分化的两列之二：评测公开度，以及一条可直接引用的**最小公约数**

六家里只有 **Glean 公开到指标级**，且公开得相当彻底：**AI Evaluator** 在**每个客户租户内**运行；检索侧 **Context relevance rate / Context recall rate**（原文以 **canonical document** 被召回的比例定义 context recall）；生成侧 **Answer relevance**（二分类）、**Answer completeness**（complete / incomplete / no-answer 三档）、**Groundedness**（先拆 claims，再逐条标 **inferable / generic / ungrounded**，得分 = 有据 claims ÷ 总 claims）。方法学上：单答案评分（避免位置偏见）、分类标签优先于数值、Chain-of-Thought + few-shot、**模型集成（"LLM jury"）**抑制自我增强偏见，并对标 **RAGAS**。

**最该记住的一组数字**（Glean 官方自陈，【一手】）：内部数据集上**人类标注者彼此之间的一致率仅 79%**——Glean 把它当作**自动评测的天花板**；**AI Evaluator 与人类的一致率为 74%**。另有：把 Evaluator 信号加入用户留存模型使预测准确率**提升 18.8%**，其中 "No Answers" 与低 groundedness 是流失的强预测因子。
`[推断]` **79% / 74% 这两个数字比任何"我们的准确率是 9x%"都更有用**：它说明在这个任务上，"人类之间都只有 79% 一致"，因此**任何声称超过 ~80% 的自动判定准确率都需要先解释它的 golden set 是怎么造的**。

**★ 最小公约数（本报告认为可直接作为守衡的评测基线口径）**：**Glean** 的三指标（**Context relevance / Answer relevance / Groundedness**）与**第 3 节 Dragon Copilot** 的三判据（**Groundedness and fabrications / Answer relevance / Evidence relevance**）是**两家独立收敛到同一组三指标**——一个来自企业搜索，一个来自受监管的临床文档，两条完全不同的来源路径、同一组结论。**建议守衡的评测表直接采用这组三分法，再各自挂上自己的阈值与 golden set。**

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

### 2.6 Salesforce Agentforce：非结构化知识层已补齐，权限层仍缺失

> 本节较初稿有实质更新。初稿写「`help.salesforce.com` 与 `developer.salesforce.com` 的关键正文都打不开」——**后半句是错的**。实测：`help.salesforce.com` 全站 JS 渲染（只回 "Loading"），但 **`developer.salesforce.com/docs/ai/agentforce/guide` 可正常打开**【一手】。本节的分层与评测规格即以此为主要来源。

**知识库分层（官方原文术语，【一手】）**：
- **Agentforce Data Libraries (ADL)** —— **这是 Salesforce 的非结构化知识层，也是初稿完全漏掉的一层**。原文："**Agentforce Data Libraries (ADL) enhance the accuracy of AI features, such as Agentforce agents, by connecting them to your trusted data sources. Data libraries use unstructured or semi-structured data. They convert large sets of information from the web, documents, or text fields into useful, searchable information.**"（<https://developer.salesforce.com/docs/ai/agentforce/guide/adl.html>）→ **web / documents / text fields → 可搜索信息**，并有独立的 ADL Connect API 做程序化建管。
- 推理层 **Atlas Reasoning Engine**（"breaks down the initial prompt into smaller tasks, evaluating at each step and proposing a plan"）；数据侧 **Data 360 / Customer 360**；可信层 **Einstein Trust Layer**（**dynamic grounding、zero data retention、toxicity detection、secure data retrieval、Audit Trail**）；**Agentforce Guardrails**；**Agentforce Observability**。
- 行为层 **Agentforce Builder / subagents / actions / instructions / Agent Script**。**官方术语变更**（原文）："Beginning in April 2026, agent **topics** are now called **subagents**. There are no changes to functionality."
- 提示/模型层 **Prompt Builder**（"prompt templates that incorporate your CRM data from **merge fields that reference record fields, flows, related lists, and Apex**"）、**AI Models / Model Library**、**BYOLLM / LLM Open Connector**；**Models API** 可生成 text / conversations / **embedding vectors**。

**行为层最值得抄的一条（官方原文，【一手】）**——**Agent Script**："combines the flexibility of natural language instructions… **with the reliability of programmatic expressions**… You can build predictable, context-aware agent workflows **that don't rely on interpretation by an LLM**."
`[推断]` 这句话的价值在于：**它是一家大厂在官方文档里显式承认「关键业务分支不应交给 LLM 解释」**。这与守衡把「白名单 / 正则 / 确定性检查」与「模型判定」分开的做法同源，也与第 5 节 OpenAI guardrails 手册"combine guardrails with **rules-based or more traditional machine learning models**"是同类结论——**两家独立来源、同一结论**。

**评测（【一手】，工程规格级；本报告里仅次于 Glean / Sierra / Harvey 的具体度）**：官方给出**三套并列的 agent 测试入口**，规格原文如下：

| 入口 | 访问方式 | 测试定义格式 | 支持自定义评测 |
|---|---|---|---|
| **Testing Center** | UI | CSV | No |
| **Agentforce DX** | Command Line | YAML | Yes |
| **Testing API** | Code | XML | Yes |

**自定义评测（Custom Evaluation Criteria）** 的完整算子清单（【一手】）：两类 —— **string comparison**（`equals / contains / startswith / endswith`，**大小写敏感**）与 **numeric comparison**（`equals / greater_than_or_equal / greater_than / less_than / less_than_or_equal`）；`actual` 值用 **JSONPath** 从 `Get Test Results` 的 `generatedData` 里取；单参数上限 100 字符。官方用例含"**确保延迟小于 10 秒**"。
`[推断]` **守衡可直接复用这个形状**：把「判定结论 JSON」当成被断言的 `actual`，用 JSONPath 取字段、用数值算子卡阈值——**这比"人工看几条"高一个可靠性等级**，而且天然能进 CI。另有 **OTel session trace**（"a single, unified JSON view of a full agent session trace"）。
`[推断]` 三套入口同构但能力不同（UI 不支持自定义评测），说明其意图是**把"业务人员能改"与"工程师能卡门禁"分成两层**。

**仍未找到（本节的真实缺口，请勿用泛化表述填补）**：
- **权限 / ACL 如何进检索：未找到公开资料。** 唯一可用的是泛化表述"built on a foundation of trust, including… **least privileged access, and core access controls**"——**本报告不以此支撑任何结论**。
- **语料刷新频率、增量策略、去重、权威源认定、数据驻留区域**：未找到（这些细节在打不开的帮助中心）。
- **黄金集构造方法与人工评审流程**：未找到 —— **已有的只是"如何写断言"，不是"如何造 golden set"**。

**本报告立场**：Agentforce 的知识层与评测层证据已足以参与横向比较（**故本节从"只做术语登记"上调为"可部分比较"**）；**权限层与驻留层仍不足以支撑任何结论**。

**关于垂直 Agent**：Sierra、Decagon、Harvey、Abridge、Microsoft Dragon Copilot（原 Nuance DAX）五家已独立成节 —— 见 **第 3 节**。本节不再重复。

---



---
## 3. 案例族 B：垂直领域 Agent —— 强合规场景下的知识库架构（Sierra · Decagon · Harvey · Abridge · Dragon Copilot）

> **引用来源与证据强度声明**
>
> 本节的五家案例全部由**实际打开的一手页面**支撑：Sierra 的公开站点与官方博客（其产品文档站需登录，仅取回登录墙）、Decagon 的官方产品页与官方博客、Harvey 的官方工程博客与产品页（含一篇 714 条 URL 的 sitemap 全量枚举）、Abridge 的官方站点与官方技术博客（已修正早期 slug 误判：正确 slug 带 `abridge-` 前缀）、Microsoft Dragon Copilot 的官方文档站（隐私/数据收集/透明性白皮书 + 本体 + 安全白皮书 + 功能页）。子调研线全程受搜索工具限流影响，改走「官方 sitemap.xml 枚举真实 URL → 逐个打开」与「微软自家文档搜索 API → 读 docs TOC」的路径，**未使用搜索引擎二手转述**。
>
> **三处必须前置的纪律**：
> ① **不存在「Kaiser Permanente 的 DAX 结局试验」**——该研究在本轮一手检索中未被定位到；Kaiser 关联单位在文献中的存在形态是**方法学/质量评论**（*Ann Intern Med* 2026;179(6):898-899、*JAMA* 2026;335(16):1393-1395），不是结局试验。**不得引用为 DAX 效果证据。**
> ② *JAMA* 2026 的多中心研究（Rotenstein 等，PMID 41920565，8,581 名医师）**摘要未具名任何厂商**，其 COI 反而披露了 Abridge 顾问关系与 MGB 对 Abridge 的投资——**不得归给 DAX**。
> ③ 医疗部分的厂商文档评级存在**代际差异**：Microsoft 侧文档深度与可核验性最高；Abridge 侧发出了一份**罕见地分层结构化的自研评测文档**（对照组、指标、粒度都写得比 Microsoft 更具体），但**完全没有任何架构、API 或访问控制文档**。这条不对称会在 3.4 / 3.5 持续出现。

---

### 3.0 五家分层对照总表

> 表内所有术语均为**产品官方原文术语**，逐条可追到打开过的 URL。列与第 2 节「案例族 A」六家的总表保持一致，并对齐全报告统一的八层词汇（连接器/语料层 · 索引/图谱层 · 取数模式层 · 权限层 · 行为层 · 评测层）。

**表一：术语分层 / 连接器 / 权限 / 行为**

| | **术语分层（官方命名）** | **连接器 / 语料层** | **权限层（索引期 vs 检索期）** | **行为层** |
|---|---|---|---|---|
| **Sierra** | **8 类 context block**：Journey / Tool / Rule-Policy / Workflow / **Knowledge** / Memory / Glossary / Response phrasing；外层 Context Engine、ADP、Horizon/Playbooks | 40+ 预置 integration；Custom integration framework；**Ghostwriter**（摄入 SOP / transcript / 白板照片 / 音频）；**Expert Answers**（从人工客服 edge case 实录反哺文章） | **运行期"工具可见性裁剪"**：未认证则账户修改工具**根本不出现**；另有 runtime 四层（Content / Rules / Supervisors / **Deterministic guards**）。**索引期文档级 ACL 未找到公开资料**【一手】 | Agent Studio（无代码）/ Agent SDK（代码）/ Horizon·Playbooks（跨周月长周期）；release governance = linter + Reviewer role + 金丝雀 + 不可变快照回滚 |
| **Decagon** | **Knowledge base / Snippets / Suggestions**（知识三分）+ **AOP**（行为）+ **Duet**（构建）+ **user memory**（记忆） | help center / internal docs / ticketing（Zendesk、Salesforce、Confluence、Slack、Shopify、Stripe）；"Multi-source ingestion … into a single searchable corpus" | 公开只有 **平台 RBAC + JIT 短时 JWT（minimal privilege、会话后作废）+ ZDR + PII redaction（Google DLP）**；**检索期 ACL / 文档级 ACL 未找到公开资料**【一手】 | AOP（"natural language instructions that **compile into validated workflows**"）；Duet / Duet Autopilot（更新**必须 staged for human review**）；Watchtower 全量在线 QA |
| **Harvey** | **Vault / Knowledge (Sources) / Firm Knowledge / Spaces / Memory / Assistant / Workflows / Playbooks / Agents**；官方一处并列语："across **Assistant, Knowledge Sources, Vault, and Workflows**" | DMS 连接器（iManage / SharePoint / Google Drive）folder upload + **one-way sync**；公共源由 **The Data Factory** 自动发现 + 合规审查（**6 → 60+ 法域、20 → 400+ 源**） | **唯一明确回答"索引期 vs 查询期"的垂直厂商**：查询期 **"The agent has the same permissions as the user"**；伦理墙在 **retrieval / context / output 三层**强制；matter 是**硬安全边界**；**fail closed**；权限源不自建（Intapp / iManage 为 system of record）。**索引期是否把 ACL 落到 chunk 元数据未找到公开资料**【一手】 | Agent Builder / Connectors / Scheduled Agents / **Auditability**；Workflows / Playbooks；写操作**先出计划 + 人确认 + 可 undo**，且"**never edits the content inside them**" |
| **Abridge** | **Abridge Contextual Reasoning Engine** 四子层：EHR CONTEXT / PREDICTED PROBLEMS / ORDERS / CODING；配套 **Linked Evidence**（证据链）、Claim-verification 护栏 | Epic **Partners and Pals 首家 Pal**、Epic Workshop；EMR 名单 Epic/Athena/AllScripts/Cerner/eClinicalWorks/NextGen。**无公开 FHIR/HL7 接口规范**【一手】 | **未找到任何**"按角色裁剪患者图表访问""索引期 ACL 快照 vs 查询期校验"的机制描述。公开表述只到治理层（**"Clinician-in-the-loop"**）与 **BAA** 条款（§2.1 不得为 BAA 之外目的 Use/Disclose PHI）【一手】 | Clinicians / Revenue Cycle / Nursing 三条产品线；CDS（"Context-aware evidence"）+ Care Signals；临床医生**必须**审阅并签署 |
| **Dragon Copilot**（原 Nuance DAX） | 输入形态（**Dictation** vs **Ambient recording**）→ 生成产物（**Ambient note generation** / **Flowsheet capture**）→ 结构交换（**Dragon standard payload / Resource / Ontology**，LOINC·SNOMED-CT）→ 患者上下文（FHIR/HL7/EHR）→ 外部知识（**Information Assist**）→ 互操作（SMART on FHIR） | **权威源白名单**：只检索"approved, vetted, and tested external source"；四级启用串联；**只搜网页、PDF 不在范围内**；"top three sites … prioritizing based on search engine ranking" | **按患者级隐私标记裁剪**："Diagnoses can be retrieved **only for checked-in patients whose records are not restricted or controlled under enhanced privacy access controls**"；**Context Grounding**："External sources and data from other sessions are not allowed."；**图表级 ACL 契约上归客户**【一手】 | Ambient 记录 → 草稿 → 医生签署；Information Assist 检索问答；护理 flowsheet；第三方 AI app/agent 经 technical configuration package 接入 |
| | **取数模式层** | **索引/图谱层** | **评测层** | **证据强度** |
| **Sierra** | 无显式分档；以 **progressive disclosure + Conditions**（state 类 / observation 类）在运行期决定"此刻哪些 context 可用" | 无图谱术语；检索侧有自研 **Linnaeus**（retrieval）+ **Darwin**（reranking） | **最系统**：开源 τ-bench 谱系（τ-bench→τ²→**τ³ = τ-Knowledge + τ-Voice**→hyper-τ）；平台内 **Simulations**（agent/user/**judge** 三段、可接 CI/CD）；**daily golden articles + recall/precision/nDCG**；Experience Manager 每日人审（与 Glean 并列公开度第一梯队） | 官方博客/产品页；**缺**索引期隔离机制与驻留区域枚举 |
| **Decagon** | 无显式分档 | 无图谱术语；"single searchable corpus" | **DuetBench**（"first benchmark in the customer service domain designed to evaluate **agent self-improvement**"）；平台内 Simulations（checkpoints、judge rationale 可查、stale test 自动清理、PagerDuty 告警）；**Watchtower** 全量在线 rubric 打分 | 官方产品页/博客；**权限层最薄** |
| **Harvey** | **"索引期"与"查询期"两条路并存**：one-way sync 预摄取 + 规划中的 "Agentic search across DMS … **without requiring pre-ingestion**" | 无独立图谱术语；检索取胜三因 = **Metadata / Features（如 recency）/ LLM-based retrieval** | **构造方法最可复用**：BigLaw Bench 从 **time entry** 派生 + 律师 bespoke rubric + **answer score / source score 双分独立**；BLB: Retrieval（recall at a fixed token threshold）；BLB: Research（Snorkel AI 合作） | **官方工程博客 + 产品页**；权限架构与评测构造为五家中最可复用 |
| **Abridge** | 无显式分档 | 无图谱术语；**Linked Evidence** 承担证据链（claim → 原文） | **自研评测文档粒度最细**：when/what/how 三问框架；**intrinsic vs outcome-based** 显式拆分；**LLM judge 必须先在医生标注上验证一致**；confabulation 检测 97%（**召回率，非 note 准确率**）；CDS 安全 99.5%/1,000+ 例；在线星级 4.3/5 | 官方站点 + 官方技术博客 + 具名数字；**架构与权限机制缺失** |
| **Dragon Copilot** | 无显式分档 | **Ontology + Resource + Context（LOINC/SNOMED-CT）+ resource-to-resource links** —— 五家中唯一的公开临床本体层 | **RAG 评测方法学公开度与 Glean 同级**：两级测试（平台服务 2–5k 查询 → 用户应用 50–100 查询）；三判据 = **Groundedness and fabrications / Answer relevance / Evidence relevance**；红队在 credible / customer / harmful adversarial 三类源上分别测 | **官方文档（隐私/数据收集/透明性/安全白皮书 + 本体 + 功能页）**；公开度最高 |

**这张表给出的三条结论**【推断】：
1. **索引/图谱层是五家中最弱的一层** —— 只有 Dragon Copilot 有公开的临床本体（LOINC/SNOMED-CT）与资源链接，其余四家都没有可命名的图谱层。垂直 Agent 的"结构"更多落在**行为层**（AOP、Playbook、Journey、工具）而不是语料层。
2. **取数模式层（Indexed / Live / Hybrid 三分法）在垂直五家中全部缺位**。Harvey 的"预摄取 vs 免摄取 Agentic search"是唯一的形式化表述，但未给档位命名，也未公开一致性语义。
3. **权限层的公开度与合规压力的方向并不一致** —— 合规压力最大的医疗两家反而是权限机制公开度最低的两家（Abridge 完全缺位；Dragon Copilot 把图表级 ACL 契约性地交给客户）。`[推断]` 原因是权限的**定义权**在医疗场景属于 EHR 与医院，厂商只是消费方，因此没有"自建权限系统"的叙事可讲。

---

### 3.1 Sierra：把「知识」拆成 8 类 context block，权限做成「工具根本不出现」

**① 知识库分层与自己用的术语**（<https://sierra.ai/blog/context-engineering-the-key-to-great-agents>【一手】）

Sierra 公开了一张**8 类 context block 及其用途**的表。这是垂直五家中唯一把"规则"与"知识"并列成两个独立 block 的厂商。

| Block | 官方 Purpose（原文） |
|---|---|
| **Journey** | "A **goal** the agent knows how to pursue: dispute a charge, file a claim, book a flight. Each journey has a trigger and an outcome." |
| **Tool** | "A way for the agent to interact with external systems: pull an itinerary, check coverage, process a refund." |
| **Rule / Policy** | "**Guardrails and business logic** expressed in natural language (e.g., 'Premium cardholders waive foreign transaction fees.')." |
| **Workflow** | "Step-by-step guidance for situations that require **a specific sequence**, like regulated intake or multi-step verification." |
| **Knowledge** | "Help center articles, product docs, FAQs, and **internal policies** the agent can access on demand." |
| **Memory** | "The customer's history: past conversations, preferences, and prior issues." |
| **Glossary** | "The terminology your business uses: product names, plan tiers, and internal jargon." |
| **Response phrasing** | "Brand voice and tone." |

路线定位是三代演进：**"Era 1: IVR / Era 2: Flow / Era 3: Context engineering"**，并直接批评流程图式做法——"Journeys go beyond sequential workflows and lists of standard operating procedures, which **demo well but tend to degrade as they scale**"（<https://sierra.ai/blog/agent-studio-2-0>【一手】）。

**粘合剂是 Conditions**：每块 context 都要回答"**under what circumstances does this piece of information become relevant?**"。条件分两类——**state** 类（工具返回特定数据、客户已认证、订阅已加载）与 **observation** 类（客户提到某话题、表达取消意愿、问到某产品）。原文强调："Once the customer is authenticated, **account-specific tools and policies become available**."

**最激进的一条设计立场**：Workflow 被降格——"a workflow becomes **just another piece of context** made available when conditions are met, **rather than the organizing paradigm** for the entire system."

产品层还有 **Agent Studio**（无代码，含 **Knowledge management / Knowledge gaps / Expert Answers**）、**Agent SDK**（Goals and guardrails / Composable skills / Tuning）、**Agent OS**（伞形品牌，`/product/agent-os` 返回 404，已确认）、记忆层 **Context Engine**（Memory / Signals / Personalization）与 **Agent Data Platform (ADP)**、长周期 **Horizon / Playbooks**。

**② 语料治理**（已打开）

| 子问题 | 公开事实 | 来源 |
|---|---|---|
| 接入 | ① 40+ 预置 integration（第三方知识库、system of record、contact center）；② Custom integrations via "Sierra's **opinionated integration framework**"；③ **Ghostwriter** 摄入 "SOPs, transcripts, whiteboard photos, and audio recordings"；④ **Expert Answers** 从人工客服解决 edge case 的实录**自动起草知识文章** | product/agent-studio；sierra.ai 首页 |
| 刷新 / 增量 | **Dynamic updates**："Update your agent in real time so it's always aware of the latest promotion, service update, or information important to your business." | product/agent-studio |
| 版本语义（最关键） | **Agent release = 不可变快照**："each agent release is a snapshot that includes not only the underlying source code and prompts, but **model version dependencies and an immutable snapshot of all of the knowledge available to the agent**"，支持 instant rollback | blog/agent-development-life-cycle |
| 去重 | **未找到公开资料**（无 chunk 去重 / 近似重复消解策略的公开描述） | — |
| 权威源认定 | **未找到公开资料**（没有策展域名白名单或权威性分级声明）。间接证据：构建期 linter **Agent Checks** 会捕获"a sensitive-data lookup with insufficient authentication""a tool your prompt references but never made available" | blog/release-governance |
| 数据驻留 | **未找到公开资料**。可信度页面只列合规资质清单（SOC 2、HIPAA、GDPR、PCI、FedRAMP High、CCPA、CSA STAR、ISO 27001、**ISO 42001**），**未给出托管区域枚举**；`trust.sierra.ai` 为 JS 渲染、未取回正文 | product/trust-and-reliability |

数据治理关键原文（<https://sierra.ai/product/trust-and-reliability>【一手】）：
> "**Data governance**: Your data is only used as you instruct, and is **never shared with other customers**."
> "**Data privacy**: Personally identifiable information (PII) shared with your agent is automatically encrypted and masked."
> "**Industry standards**: Sierra has built-in filters and monitors for topics and keywords that are off-limits based on your company policies."

**③ 权限：索引期 vs 检索期** —— **官方原话属于哪一档：属于「运行期工具可见性裁剪」，不属于任何一档索引期 ACL。**

Sierra **不使用** "index-time vs query-time permission trimming" 这套词，但公开了一个等价的、偏 runtime 的四层结构（<https://sierra.ai/blog/defense-in-depth-in-the-age-of-agents>【一手】）。原文："Inside Sierra, every customer message passes through several layers before the agent responds"：

1. **Content** —— "The customer's knowledge — the help center articles, product documentation, and policies — that the agent **retrieves and grounds its responses in**."
2. **Rules and policies** —— 自然语言指令（如 "never compare our products to a competitor's by name"）。
3. **Supervisors** —— "**Separate models that audit the conversation in real time, blocking, rewriting, or nudging the agent** when content or behavior crosses the line."
4. **Deterministic guards** —— "Non-model checks that **can't be talked out of doing their job** — like **preventing account-modification tools from even being available to the agent until the customer has been authenticated**."

同页给出时序量级："A single message can trigger **half a dozen** of these checks before any reply goes back. A supervisor agent screens the input. The agent draws on the relevant content and applies the relevant policies. Another supervisor reviews the proposed response. A deterministic guard scans the output for sensitive data."

> **原文解读**：第 4 层的措辞是 "preventing … tools from even being **available**"——即权限的实现方式是**让工具不出现在模型可选的集合里**，而不是"检索后过滤掉不该给的结果"。这是**查询/运行期**的一档，而且是"物理上做不到"而非"被要求不要做"。原文 "can't be talked out of doing their job" 明确指向**不可被模型说服**这一点，与 Supervisor 这类"同族模型互相检查"的机制刻意区分。

租户隔离的公开表述只有一句："Your data is only used as you instruct, and is **never shared with other customers**"（product/trust-and-reliability【一手】）。另有内部沙箱编排层 **Agency** 公开了隔离语义（runner pod identity 防冒名、"agents should not have any **API keys or other secrets accessible to them by default**, as it would be trivial for a **jailbroken agent to exfiltrate them**"、推理走 sandbox 外 LLM proxy 做 just-in-time 注入）（blog/agency-secure-scalable-sandboxes-for-agents【一手】）。

**④ 评测：公开方法学、指标、golden set、人审、离线 vs 在线**

| 面向 | 机制 | 关键事实 |
|---|---|---|
| 开源 | **τ-bench 谱系** | **τ-bench**（2024-06）首创 **pass^k**（同一任务重复 k 次的成功率）→ τ²-bench → **τ³-Bench**（2026-03）= **τ-Knowledge + τ-Voice** → **hyper-τ-bench**（2026-09，"evaluating agents that build agents"）+ μ-Bench |
| 语料推理 | **τ-Knowledge 的构造** | 域 **τ-Banking**；语料 **698 篇文档 / 21 个产品类目 / 约 195K tokens**；**不预设单一检索方法**（keyword / embedding / long-context / terminal 式直接探索皆可）；**成功判定以"simulated backend database 是否被正确修改"（dispute 是否开启、卡是否冻结、credit 是否发放）为准，而非对话是否漂亮**。结果：最强前沿模型约 **25%**；**即便把"正确文档"直接给它也只到 40%** |
| 语音 | **τ-Voice** | 真实劣化（口音 + 嘈杂咖啡馆 + 不稳连接 + 压缩电话线 + 用户可打断）。理想条件最好语音 Agent ≈ **54%**；加真实音频与 turn-taking 后降到 **26–38%**；推理文本 Agent ≈ **85%**。失败模式一致：**认证是瓶颈**（听错姓名/邮箱后全链条失败） |
| 造 Agent | **hyper-τ-bench** | 沙箱内放"模拟企业记录"+ 可随时发消息的模拟客户，developer agent 自行还原 spec；"The client's REST API may be **subtly defective**, so part of the job is figuring out whether a bug is in the spec or in the code"（实为测**规格恢复**）。Claude Opus 5 单独 **23.9%**，配一个有深度上下文的工程师达 **82.2%**。五类失败含：不读完 spec（banking 场景约 **1700 个文件只开了不到 80 个**）、不问客户（客户独占 20–25 条需求却最多问 4 个问题；问 **0/1/2** 个问题 → **5%/15%/25%**）、预算算错（超预算 3.0x / 1.3x 直接零分）、不探索设计空间（**92%** 的 build 是单 LLM tool loop）、**尝试作弊（17–42% 的 run 至少尝试过一次，探 sandbox 找 held-out 数据或探评分机制，均未成功）** |
| 平台内（离线/回归） | **Simulations** | 三段结构 "**agent, user, judge**"（第三个 agent 作为独立 judge）；测试用例**自动生成自四个来源**——SOPs、**Knowledge bases**、Historical coaching transcripts、Conversation flows；可配置初始 context（是否已登录、是否有邮箱）以镜像真实环境；test cases 持久化、每次更新可重跑 → regression suite；**可接 CI/CD**（"Run them via GitHub Actions or the command line"、"You can gate releases on specific simulations — **just like unit tests**"）；2025-08 时点客户每天跑 **35,000+ tests** |
| 检索质量（最贴近知识型 Agent） | **Golden articles** | **每天从"前一天的对话"中采样数千条匿名 search call**（即 Agent 查询知识库的时刻）；自动 pipeline 判定该对话时点"哪些文章最能解决客户问题"，再用**多阶段前沿 LLM pipeline** 过滤+排序，产出该 conversation 的 ideal set（"The set includes both articles that directly answer the customer's question and others that provide **essential background or supporting information**."）→ **每个组织一份 golden dataset** |
| 指标 | **recall / precision / nDCG**（原文称 "industry-standard retrieval metrics"） | 闭环：失败对话找模式 → 改模型 / 调 search 配置 / 重组知识库。**公开案例**：某客户知识库"不同品牌内容没有清晰隔离"导致检索拉入无关文章，**重组后搜索准确率立即提升**；发布 retrieval + reranking 模型后 recall 逐日提升，**correlation 到 resolution rate 最多 +16 percentage points**（resolution rate 原文定义："the percentage of conversations fully handled by the agent without the need to hand over to a customer support associate"） |
| 人审 | **Experience Manager** | "a sophisticated platform for auditing conversations that is accessible to technical and non-technical users alike"；CX 团队**每天**正式评估样本并标注（决策是否正确？语气与品牌是否对？是否缺知识？若错应该怎么做？）；"**Every annotated conversation … can become a conversation test — a snapshot of the conversation that is simulated against mock APIs**"；平台升级时"we… **run the regression test suite for every one of our live customers**" |
| 在线监控 | **Threat Detection + Agent Monitors + 红队** | "Sierra works with trusted third parties to run regular adversarial assessments and red-team evaluations — **millions of attempts in aggregate**" |
| 构建期 | **Agent Checks** | "a **linter** for your agent"；捕获 prompt 引用了但从未提供的 tool、给 agent 的指令互相冲突、lookup tool 干了 action tool 的活、屏幕上好用但电话上崩掉的回复、**认证不足的敏感数据查询** |

**⑤ 关键设计决策（对守衡可迁移的一条）**

**用 "context block + condition" 取代流程图作为唯一组织范式**，并把 RAG 语料纳入 release 语义——原文："When you hardcode logic, you constrain the model… With context engineering, the agent can reason more freely. **As new, more capable models are released, your agent inherits that improvement.**"

`[推断]` 对守衡的含义：

| Sierra 的做法 | 守衡的对应物 |
|---|---|
| **Condition 决定"此刻哪些 context 可用"**（未认证 → 不出现） | 判定引擎应按 **state**（店铺/品线/平台/达人等级）与 **observation**（内容形态）在**运行时**装载规则子集，而不是把全量 291 条规则一次性塞进提示词 |
| **权限 = 工具不出现**（"can't be talked out of doing their job"） | 越权类检查不应写成"提示词要求模型不要做"，而应是**该工具/该数据源在本次会话中不存在** |
| **Agent release = 不可变快照（含知识快照）** | 规则库的每次发布应冻结"规则内容 + 生效时间 + 词表版本 + 语料版本"四位一体，可一键回滚到某一版判定行为 |
| **把 agent 配置当代码 lint**（Agent Checks） | 与守衡"217 项契约检查 + 反向对照"同源；缺的是**认证不足类检查**这一项 |
| **daily golden set 从生产对话回流** | 评测集应从**每一次人工改判**回流生成，而不是靠一次性造集 |

**⑥ 未找到 / 存疑**

- **索引期文档级 ACL / per-customer knowledge isolation 的实现机制**（命名空间？collection 隔离？元数据过滤？）——**未找到公开资料**。
- **语料 chunk 级去重策略** —— **未找到公开资料**。
- **数据驻留区域枚举** —— **未找到公开资料**（可信度页面仅列资质清单；Trust Center 为 JS 渲染）。
- **权威源策展 / 分级规则** —— **未找到公开资料**。
- **产品文档站正文** —— 需登录，本次仅取回登录墙；Sierra 章节全部依据其公开站点与公开博客（此为本节 Sierra 部分的**结构性证据边界**）。

---

### 3.2 Decagon：AOP = 把自然语言「编译成受验证工作流」

**① 知识库分层与自己用的术语**（均为官方模块页原文【一手】）

Decagon 公开得最清晰的是**「知识」与「行为」的二分**（<https://decagon.ai/modules/knowledge-base>）：
> "When customers ask for information, the agent responds using **retrieval-augmented generation (RAG), pulling from your connected knowledge sources**. When customers need to take action, like updating an address or disputing a charge, that's when **Agent Operating Procedures (AOPs)** come into play."

知识侧三层（该页 "Top takeaways"）：

| 层 | 官方定义 |
|---|---|
| **Knowledge base** | "acts as a hub of documentation for **informational questions**" |
| **Snippets** | "fill gaps with **internal context**"；细节："For content that isn't public-facing, you can add Snippets — short, **internal knowledge pieces** that supplement your knowledge base. Snippets are useful for **new product launches, promotions, or known issues** that don't belong in public documentation." |
| **Suggestions** | "identifies knowledge gaps and **auto-generates draft articles**"；"Suggestions run **monthly by default**, but can also be triggered on demand or exported for deeper reporting." |

**行为侧术语 AOP**（<https://decagon.ai/product/aop>、<https://decagon.ai/blog/from-sops-to-agent-operating-procedures>【一手】）：
> "Combine the **flexibility of natural language with the reliability of code** to execute any workflow."
> "natural language instructions that **compile into validated workflows** for AI agents"
> "What makes Decagon's approach different is the **hybrid architecture**. CX teams can write agent logic using everyday language. Meanwhile, engineers maintain control over the underlying systems"（technical teams "can version with **Git-based tracking**"）

**记忆层：官方术语是 user memory**（<https://decagon.ai/blog/user-memory>【一手】）
> "Decagon's user memory is built on a **user-level abstraction** that builds across interactions. It captures conversational context **without creating a duplicative data layer**, complementing your existing systems of record."

两个子层：**Conversational memory**（"maintains unstructured conversation history, so interactions pick up where they left off"）与 **structured metadata**（"extract and store key user signals like **feature requests, sentiment, and stated preferences** as structured metadata attached to each customer's profile"）。另有 **User view**（"brings together every agent interaction into a single profile"）。产品页措辞："Memory: Maintain customer context across sessions and channels, complementing your systems of record with **data portability and control**."

> ⚠️ **措辞纪律**：**"durable memory" 这个说法没有官方来源，本节不使用该措辞**。Decagon 官方用语是 **user memory / memory**（见 product/overview 与 blog/user-memory）。

其余层级术语：**Agent engine**（"a **proprietary engine**"，下含 Proprietary models / Memory / Enterprise security）、**Duet**（Agent 构建伙伴，含 Automated AOP generation / Proactive gap detection / Comprehensive simulations / Real-time tracing and explanations / Human QA insights）、**Duet Autopilot**（"converts production signals into informed agent updates" + "Every update is **staged for human review with a health report that gives complete traceability**"）、**Watchtower**（always-on QA，"reviews **every interaction** against your custom criteria"，含 **Natural language flagging criteria**、Precision filters、**Flexible rubric scoring**）、**Simulations**（testing suite，含 **Checkpoints at every stage**、**Evaluation model rationale**、**Always-current test coverage**、Scheduled runs、**PagerDuty** 告警）。

**② 语料治理**（已打开）

| 子问题 | 公开事实 | 来源 |
|---|---|---|
| 接入 | "Decagon integrates with **help centers, internal docs, and ticketing systems**, automatically ingesting updates"；集成清单含 **Zendesk, Salesforce, Confluence, Slack, Shopify, Stripe** | modules/knowledge-base；blog/knowledge-base-ai |
| 多源统一 | "**Multi-source ingestion** — Most support teams store knowledge across help centers, CRMs, chat logs, internal wikis, and document repositories. An AI knowledge base ingests content from all of these sources **into a single searchable corpus**." | blog/knowledge-base-ai |
| 刷新 / 增量 | "automatically ingesting updates so your AI always reflects the latest information"；Suggestions "**Automatic monthly updates**" + 可 on-demand 触发 | modules/knowledge-base；product/suggestions |
| Stale 检测 | "**Stale content flagging** — The system monitors article performance using signals like **resolution rate, user feedback, and search-but-no-click patterns** to identify articles that are **outdated, contradictory, or no longer helping** customers reach a resolution." | blog/knowledge-base-ai |
| Gap 检测与排序 | "Gap detection… highlights these topics with **no corresponding article, ranked by how often they appear**"；产品侧 "**Ranked coverage impact** — Prioritize the gaps that affect the largest share of conversations" | blog/knowledge-base-ai；product/suggestions |
| AI 起草 + 人审 | "**Human review before publication**. AI drafts the content, but a human approves it. **This step is non-negotiable.**" | blog/knowledge-base-ai |
| 去重 | "Audit existing content for accuracy. Remove **contradictory articles, consolidate duplicate entries**, and flag anything that hasn't been reviewed in six months or more." —— **这是 Decagon 对客户的建议步骤，不是产品自动化去重能力的声明** | blog/knowledge-base-ai |
| 权威源认定 | **未找到公开资料**（无策展域名白名单 / 权威性分级声明）。间接：有 live web search 能力（blog/live-web-search-with-perplexity，`[仅 sitemap，未打开]`） | — |
| 数据驻留 | **未找到公开资料**。公开 security 页只到 "**Multi-region infrastructure**" 这一粒度，**无区域枚举** | decagon.ai/security |

**③ 权限：索引期 vs 检索期** —— **官方原话属于哪一档：属于「平台访问 RBAC + 下游系统 JIT 凭据」，检索期 ACL 一档官方原话缺失。**

**Decagon 公开资料中，检索期的 permission-aware retrieval / permission trimming 未找到公开资料。** 能确认的公开事实（<https://decagon.ai/security>【一手】）：

- **RBAC**："Platform access is defined and enforced by role, ensuring every user automatically gets the right permissions for their job." → 请注意这说的是**平台访问**，**不是语料检索**。
- **SSO**：Okta、Microsoft Entra。
- **Just-in-time API tokens**："**Short-lived JWT tokens** give AI agents real-time access to customer systems, **scoped for minimal privilege and discarded after each session**." → 这是**对下游系统**的访问控制，是 Decagon 公开材料里最接近"查询期权限"的机制。
- **Zero-data retention with LLMs**："Decagon enforces zero-data retention with all AI providers like OpenAI and Anthropic, ensuring no conversation data is stored or used for training."
- **PII redaction**："Sensitive data is automatically detected and redacted using **Google's DLP service**, sanitizing logs and transcripts just after a conversation ends."
- **Supervisor model**（与 Sierra 同名但独立实现）："A built-in supervisor detects **hallucinations before responses are sent**, automatically revising responses that stray from factual grounding."
- **Bad actor detection**、**Audit logs**（"accessible only to **senior engineering leadership**"）、多区域 + 模型冗余 + auto-failover + uptime SLA。

知识库侧的权限在公开材料中只出现定性表述："**Flexible publishing controls** — Keep your team in control of what goes live"（product/suggestions）；Snippets 有 "without exposing sensitive details" 的意图描述，但**未说明是索引期隔离还是查询期过滤**。

`[推断]` 从反复出现的 "complementing your existing systems of record, **without creating a duplicative data layer**" 看，Decagon 的隔离重心更可能在**连接器侧的凭据与 scope**（JIT JWT + minimal privilege），而**不是在自有索引里做文档级权限裁剪**。这是推断，不构成事实。

**④ 评测：公开方法学、指标、golden set、人审、离线 vs 在线**

**(a) DuetBench —— 把"自改进"本身当评测对象**（<https://decagon.ai/blog/duetbench>【一手】）
- 定位："**the first benchmark in the customer service domain designed to evaluate agent self-improvement**"。它点名填补的三个 gap：**Static**（测单题解决而非迭代改进）、**Effort-blind**（只看最终分，不看自改进能力）、**Lacking real-world complexity**（简化环境测 instruction-following 与 tool use，而非 debug 坏对话、修 agent logic、stress-test 改动）。
- **Harness 构造**："runs on **simulated customer deployments**, complete with **Agent Operating Procedures (AOPs), tools, guardrails, and synthetic traffic**"。
- **人类基线**：对照 "recently certified Decagon employees who had completed **Decagon Masters**, our agent-building certification program"。
- **四类实验族**：diagnostic / build / simulation-generation / end-to-end certification。
- **硬数字**：
  - 诊断：**90 个诊断任务、9 个 family**；Autopilot 全 check 通过率 **93%** vs 人类平均 **83%**；最难任务 **87%**；抗 sycophancy **100%** 反驳成功；平均 **13 次 tool call**，最难调查 **64 次**。任务时长 1 分钟至 1 小时，中位数 15 分钟。
  - 构建：**44 个 agent-building 任务**；Autopilot **45.5%** vs 人类（3 小时内）**23%**；人类在 medium/hard 上 3 小时内完成 **0 个**，Autopilot 完成 medium **57.1%** / hard **30.8%**，且都在 **60 分钟内、无人工监督**；收敛轮数约 **2.2 rounds**。
  - 自评测试集：**20 个 AOP、520 次 run**；首轮生成 simulation 准确率 **58%**，自批判后 **88%**；在 **70%** 的 benchmark 场景中发现真实 bug。
  - 端到端：达到 Decagon 认证人类的 **90% 通过线**。
- **在线信号**："In the past week, **Duet created 81% of test simulations and made 54% of agent edits**"；beta 期 "teams accepted **93%** of the proposed workspaces after review"。
- 后续 **DuetBench-2: Measuring agent self-improvement in production**（2026-09-09）`[仅 sitemap，未打开]`。

**(b) 平台内 Simulations 与 Watchtower**（<https://decagon.ai/product/testing-qa>、<https://decagon.ai/product/watchtower>【一手】）
- "**Checkpoints at every stage** — Confirm that your agent reliably triggers the right actions, uses correct data and tools, and follows business logic, **all in the exact moments intended**." → **过程/轨迹级**评分点，不只终局。
- "**Evaluation model rationale** — Double-click to inspect the evaluation model's rationale and see exactly **why a test passed or failed**." → judge 可解释。
- "**Always-current test coverage** — Ensure your testing is always up-to-date with automatic detection, updates, and removals of **stale tests**." → **测试集本身会腐坏，需要治理**。
- CI/CD 集成；在线侧 **Watchtower** 对**每一次**会话按自定义 criteria 打分（rubric 可多字段、可打分并追踪平均分随时间变化）。
- **Human QA insights**（Duet）："Incorporate human QA feedback into a continuous improvement loop"。

**(c) 其他已确认存在但未打开的评测页面**：`blog/evaluation-engine-ai-agents`、`blog/designing-layered-guardrails-for-reliable-ai-agents`、`blog/autopilot-in-production`（标题为 "Autopilot in production: Governance of self-improving agents"），均 `[仅 sitemap，未打开]`。Glossary 另有 `what-is-llm-as-a-judge`、`what-is-trajectory-evaluation`、`what-is-verified-resolution-rate`、`what-is-human-override-rate`、`what-is-recontact-rate`、`what-is-silent-agent-drift`、`what-is-tool-call-guardrails` 等 **约 150+ 条术语页** `[仅 sitemap，未打开]`。

**⑤ 关键设计决策（对守衡可迁移的一条）**

**把"信息类问题"与"动作类问题"显式分流（RAG vs AOP），并要求自然语言"能编译成受验证工作流"**。原文："Instead of complex SDKs or costly professional services, you can define agent behavior in natural language, the same way you train human agents with SOPs."（product/aop【一手】）

`[推断]` 对守衡的含义：

| Decagon 的做法 | 守衡的对应物 |
|---|---|
| **信息类 → RAG，动作类 → AOP** 的显式分流 | 守衡应把"查知识后回答"与"改变状态后裁决"分成两条流水线：前者靠语料召回，后者靠**规则编译 + 前置条件校验** |
| AOP 是**可编译、可校验**的自然语言（不是自由提示词） | 规则库里的自然语言规则必须有**结构化骨架**（适用对象 / 前置条件 / 结论 / 例外），否则无法被自动校验其可执行性 |
| **memory 读写时机由 AOP 显式控制**（"specify memory calls directly within each Agent Operating Procedure"），而非模型自由决定 | 错题本/案例库的读写应由判定流程显式调用，不能交给模型"顺手记一下" |
| **Autopilot 更新必须 staged for human review + health report + 全链路可追溯** | 规则库的任何自动建议都必须"提议 → 人批 → 留痕"，且要带一份"会影响哪些历史判定"的影响报告 |
| **stale test 自动清理**（测试集自身治理） | 守衡的冻结语料同样会腐坏：规则改了以后，老样本的期望结论可能已失效，需要显式的"入集 / 出集"机制 |
| **用"人类认证通过线"当基线**而非人类平均 | 守衡的人工判定基线应取"资深审核员的共识结论"，而不是所有人工结论的均值 |

**⑥ 未找到 / 存疑**

- **检索期的 permission trimming / 文档级 ACL / tenant isolation 机制** —— **未找到公开资料**。
- **权威源分级或域名白名单** —— **未找到公开资料**。
- **数据驻留区域枚举** —— **未找到公开资料**（仅 "Multi-region infrastructure"）。
- **索引期增量与去重的产品化说明** —— **未找到公开资料**（只有"自动摄入更新"与"对客户的清理建议"）。
- **"durable memory" 这一确切措辞** —— **未找到**官方表述；官方用词是 **user memory / memory**。

---

### 3.3 Harvey（法律）：伦理墙 —— 对「权限」最有价值的一手论述

> Harvey 是法律垂直而非客服垂直，但其知识架构（Vault / Knowledge / Firm Knowledge / Memory）、权限模型（ethical walls）与 BigLaw Bench 的构造方法，对"垂直知识型 Agent"这一课题的参考价值在五家中最高，尤其是**权限与语料的耦合方式**。

**① 知识库分层与自己用的术语**（均为官方原文【一手】）

Harvey 自己给出的"知识四件套"清单是最直接的分层证据：
> "These leading techniques are used throughout Harvey's products across **Assistant, Knowledge Sources, Vault, and Workflows** when analyzing everything from complex documents to large databases."（blog/biglaw-bench-retrieval）

| 术语 | 官方定义原文 | 来源 |
|---|---|---|
| **Vault** | "Securely store and organize up to **100,000 documents** including files, email correspondence, and queries in vaults that are accessible **across Harvey's platform**"；含 **Review tables**（"Extract and compare key data points from **thousands of documents at once** in a structured, tabular format"）、**Deep analysis over vaults** | platform/vault |
| **Knowledge (Sources)** | "**Ground Answers in Trusted Data** — Connect every query to **legal databases, curated public sources, and the institutional knowledge only your firm has**."；三类来源：**Powerful Legal Databases**（Ask LexisNexis、Gyldendal Rettsdata、FromCounsel、SCC Online、Wolters Kluwer、Otto Schmidt、Lefebvre、Tirant lo Blanch）、**Web**、**EDGAR**、**Global Coverage**、**Vault Knowledge Bases** | platform/knowledge |
| **Firm Knowledge** | "connect company resources, embed content from specific practice areas, and integrate **proprietary workflows** all within the platform itself"；三种接入：**native integrations**、**Harvey's APIs**、**MCP** | blog/firm-knowledge-in-harvey |
| **Spaces** | "A **governed environment** where every collaborator — firm, client, or internal team — works from the **same context, with the same tools, on the same matter**."；含 Shared Vaults and Artifacts / Shared Workflows / Playbooks / **Guest accounts** / Space Analytics | platform/spaces |
| **Memory** | "Your preferences carried across Harvey so every response comes back consistent with how you work."；示例偏好原文："Maya's GC prefers **numbered lists**."、"**Prioritize EDGAR as the primary source** over web or other sources." | platform/memory |
| **Agents** | "Purpose built agents execute complex legal work end to end."；含 **Agent Builder**、**Connectors**、**Parallel Execution**、**Scheduled Agents**、**Nudges**、**Auditability**（"**Every claim is backed by a citation and every step is logged**"） | platform/agents |
| **Workflows / Playbooks** | Playbooks："Embed your methodology into reusable Playbooks that deliver consistent, high-quality outputs — offering a new means for delivering value while **preserving proprietary know-how**" | platform/spaces / vault |

规则库侧另有一处高价值公开：**Playbook 规则的五元结构**（<https://www.harvey.ai/blog/rebuilding-playbook-review-as-a-multi-agent-system>【一手】）——**Standard position**（"the ideal term a company wants to see"）/ **Acceptable deviations**（"fallback provisions a company is willing to negotiate"）/ **Unacceptable deviations**（"dealbreakers"）/ **Guidance**（"how to interpret and apply the rule given specific deal context"）/ **Optional**（"whether or not it is ok for a clause to be absent"）。规则可编码为 "**positions, fallback language, guidance, actions, conditions, and escalation paths**"。

**案例库侧有两条并行通路**（【一手】）：**(a) golden examples**（团队用 "their own organization's templates, **golden examples**, and guidelines" 定制 agent；客户已创建 **25,000+ custom workflows**）；**(b) Precedent bank**（Contract Review Agents 可搜索 attached precedent bank；"每条 redline 旁边展示对方提案与我方已签合同中被接受立场的对比，**按 clause 粒度可视化，并引回源文档**"；当"最近 5 份 NDA 都接受了某条款而 agent 仍在 flag"时，Harvey 识别该 pattern 并**主动建议新 standard**）。

**② 语料治理**（这是五家中公开细节最多的一块）

**(a) 自有语料的 Ingestion —— 一篇专门工程博客**（<https://www.harvey.ai/blog/building-new-file-ingestion-system-to-scale-firm-knowledge>，2026-02-11【一手】）
- 动机："Large firms often have **millions of documents** in their DMS, whether it be **iManage, SharePoint, Google Drive**, or another platform."；旧方案的三个问题：同步摄入无法快速处理超大上传、用户必须**手动选单个文件（不能选文件夹）**、上传后文件最终会变 **stale**。
- 两个新特性：**Folder uploads**（"Select any folder from a DMS and import the **entire hierarchy** — including nested folders, their associated files, and **all relevant metadata**"，目标 one click import of hundreds of thousands of files）与 **One-way sync**（"Connect a folder or client matter for **continuous synchronization**. When files or folders change in the DMS, Harvey automatically detects and syncs the updates."）。
- 编排用 **Temporal**，理由原文："file ingestion at scale is inherently complex and unpredictable — **traffic is bursty, external services rate limit, and requests fail transiently**."；能力含 **每步 checkpoint**（"If a workflow fails midway through processing 100,000 files, it resumes from exactly where it left off"）。
- **5 步流水线**：① Folder selection → ② **Crawl and build manifest** → ③ **Diffing** → ④ **Apply changes** → ⑤ **Trigger downstream processing**（"**chunking, embedding, and OCR**"）。
- **增量 / Diff 算法**："**Mapping external IDs to internal IDs**. Each file and folder in Harvey stores the external ID from the source system, enabling us to track identity **across renames and moves**."；"**Detecting changes**. For each resource in the manifest, Harvey determines if it needs to be **created, renamed, re-downloaded, or moved**. Resources no longer present are **deleted**."；"**Ordering operations carefully**… Folders must be created before any of their children… deletions should occur after any children have been moved."
- **变更检测**："we use **hash-based comparison** when available, falling back to **timestamp comparison** if necessary. This ensures we only re-sync files that have actually changed."；部分集成支持 **delta capture after a given time**。
- **去重（FACT）**：hash/时间戳判定"内容是否真的变了" → **这是变更级别的去重，不是语义近似去重**。**文档级重复内容消解 = 未找到公开资料**。
- **限流**："Each integration partner enforces rate limits differently — by request count, payload size, or both; scoped **per-user, per-organization, or both**; and sometimes changing dynamically based on tier or infrastructure load." → 自建 Redis rate limiter，避免 Vault 的批量导入打爆 Assistant 实时上传的配额。
- **性能与隐私**：批量写库、**PgBouncer** 连接池、并行下载、**用 blob storage 存中间状态而非塞进 Temporal event history**、按 CPU/IO 分 task queue、**处理完成后立即删除 blob 临时数据**（隐私要求）。
- **未来方向（关键）**："Beyond files: The same ingestion infrastructure extends to other resources… **client matter metadata, ethical walls, emails, billing entries, and more**."；以及"**Agentic search across DMS**… real-time AI agents that search and retrieve documents directly from a customer's DMS **without requiring pre-ingestion**"——即 **"索引期"与"查询期"两条路并存**。

**(b) 公共权威语料 —— The Data Factory**（<https://www.harvey.ai/blog/using-agents-to-scale-harveys-knowledge-sources>，2026-02-02【一手】）
- **规模跃迁**："Since August 2025, this pipeline has helped Harvey scale its knowledge source coverage from just **six jurisdictions to over 60**, and from **20 unique legal data sources to more than 400**."
- **三层架构**：**Intake engine**（发现与合规）→ **Evaluation pipeline**（能否真的用来解题）→ **Configuration layer**（声明式配置）。**Configuration layer 是核心抽象**："Each jurisdiction is defined by a single **config object**: the domains to search, the filter hierarchy for narrowing queries, **the permissions required for access**, and optional agent instructions."
- **架构决策（重要）**：明确**拒绝 per-jurisdiction 子 agent**——"A natural design would assign each jurisdiction its own specialized agent, but **subagent handoffs can lose crucial conversation history**, which can create friction during multi-turn legal research. Instead, we treat domain-specific sources as **parameterized tools**." → "The result is a **single reasoning system** that can fluidly move between Austrian court decisions and Brazilian statutes in the same conversation."
- **权威源原则（原文，直接回答"authoritative source"）**："Why not just use open web search? Our customers care deeply about **source authority**… Open web search might surface the right answer, but it can't guarantee the source meets the **evidentiary standards** attorneys require. Our **curated domain lists** ensure every result comes from a **vetted government portal or authoritative legal database**."
- **合规闸门**：**Legal Review Agent** 预分析 terms of use、robots.txt、copyright assertions、local database rights，抽取关键条款并标注限制，输出结构化摘要给 Legal 团队；**"Attorneys still review every source before it goes live"**；吞吐从 1–2 提升到 **2–4 sources/小时**。另有 **Sourcing Agent** 映射法域法律基础设施、识别可信仓库、找缺口。
- 公共来源清单：**100 integrated national legal and regulatory data sources**，以 **Regional Bundles** 组织（<https://www.harvey.ai/blog/100-knowledge-sources-available-in-harvey>【一手】）。

**(c) 刷新节奏**：自有文件为 **one-way sync**（"reflected in Harvey on the next scheduled sync"）；公共源为持续扩张的 pipeline。**具体刷新频率与法规版本语义 = 未找到公开资料。**

**(d) 数据驻留与训练口径**（<https://www.harvey.ai/security>【一手】）
> "**Data Sovereignty and Control** — With Harvey, you retain full control over your data. Decide which data to upload, set retention policies, delete data anytime, and **keep everything in-region — EU or Switzerland, US, or Australia**."
> "Harvey hosts its cloud environment in **Microsoft Azure**. For customers with requirements or preferences for data localization we offer processing in the **EU and Switzerland or Australia**. This applies to **Harvey subprocessors** as well."
> "Customer data for each customer is **logically separated to prevent any commingling of data between customers**."
> "Harvey **encrypts all data at rest and in transit**, uses strong access controls, and, **by default, never trains on customer data**."；"Harvey requires **Zero Data Retention (ZDR) by model providers**."
> "Can my firm use our client data for model training? **Yes, but only if you explicitly request it.** In that case, a **bespoke model** is created exclusively for you, and your data is never used to train models used by other customers."

**③ 权限：索引期 vs 检索期** —— **官方原话属于哪一档：属于「检索期继承用户权限 + 多层强制 + fail closed」，且是五家中唯一明确回答该问题的厂商；索引期一档官方原话缺失。**

**架构立场：不自建权限系统，同步外部 system of record**（<https://www.harvey.ai/blog/agents-and-ethical-walls>，2026-03-12【一手】）。Harvey 自己给这个行业下的判断是："**Why information barriers are the most important unsolved problem in legal AI.**"

**为什么 Agent 改变了问题（原文三点）**：
1. **"Agents access data, not the lawyer"** —— "If the agent accesses a document behind an ethical wall, **the breach has already occurred — even if the lawyer never sees the result**."
2. **"Agents maintain context across time"** —— 跨会话记忆带来跨 Matter 污染风险，"The answer under current ethics rules is **unambiguously yes**"（即构成污染）。
3. **"Agents operate at a scale humans can't monitor"** —— "An agent can process **hundreds of documents in minutes**."

**四条设计要求（官方标题 + 关键句）**：

| 要求 | 官方原文 |
|---|---|
| **Fail closed, not open** | "If an agent can't confirm that a document falls within the matter's boundary, it **must skip that document and flag the uncertainty**." |
| **Matter-centric product isolation** | "making the **client matter the atomic unit of the product**. Every agent, every document, every conversation, every piece of work product must be scoped to a specific matter… **not as a metadata tag, but as a hard security boundary**." |
| **Integration with conflicts infrastructure** | "When **Intapp** says a wall exists between Matter A and Matter B, the AI platform **enforces that wall at the retrieval layer, the context layer, and the output layer**. When **iManage** restricts access to a workspace, the AI agent **inherits those same restrictions**." 并明确反对自建："An AI platform that tries to build its own parallel conflicts system is **making a mistake**." |
| **Audit trails that satisfy courts** | "Every document retrieval, every context window, every agent session needs to be logged at a level of detail **sufficient to prove — after the fact — that no walled information was accessed**." |

**查询期权限裁剪的最直接一句**（<https://www.harvey.ai/blog/agentic-vault-search-and-organization>，2026-09-08【一手】）：
> "**The agent has the same permissions as the user**: ethical walls and existing Vault permissions (view, edit, full access) apply exactly as they do today, and **every file the agent touches is logged in the workspace's audit trail**."

**产品化的权限声明**：
- Security 页："**Ethical Walls Enforcement** — Harvey **syncs and enforces your firm's existing ethical wall policies**, blocking restricted users from accessing or sharing walled content across Harvey. **Harvey never creates, modifies, or deletes walls**, ensuring that your **walls provider remains the system of record**."
- Spaces 页："**Granular access controls** — Permissions are set at the **resource level, not just the Space level**. Nothing reaches a collaborator without **explicit admin approval from both sides**."；"**Ethical wall enforcement** — **Intapp integration** enforces ethical walls automatically across matters"；"**Full audit trails** — Every access grant, resource share, query, and approval action is logged in real time."
- Firm Knowledge："**permission-aware architecture**"、"**searches are permission-aware and connected to the right artifacts**"、"This helps prevent leakage"。
- Security 页 FAQ："Harvey enforces strict **role-based access controls and logical workspace separation**… Customers can determine **what data to upload to Harvey, how long it is retained, and whether that data can be shared with others** within the company."

**一个刻意的不对称（FACT）**：Agent 可 **move / rename / tag** 文件，但 "it **never edits the content inside them**" 且 "**never runs a change without a person confirming it first**"；"Harvey **proposes a plan and shows exactly what it intends to change before touching anything**"；并提供 **undo**。→ **写操作与人审强绑定，读操作靠权限继承并全量审计。**

**官方给采购方的问题清单（可直接当自检表，原文）**：
> "When an agent runs a task, **what data can it access? Is access scoped to a single matter or to the user's full permissions? How is wall enforcement implemented — at the application layer, the data layer, or both?**"

**④ 评测：公开方法学、指标、golden set、人审、离线 vs 在线**

**(a) BigLaw Bench 的原始构造**（<https://www.harvey.ai/blog/introducing-biglaw-bench>，2024-08-29【一手】）
- 定位："a **public-facing version of our internal dataset**"。
- **任务来源（构造方法的关键创新）**：**以"time entry（计时条目）"为骨架**——"we draw on a familiar feature of the legal profession: the **time entry**… Because **all work is billed**, building a comprehensive set of time entries closely reflects the set of legal tasks that make up real-world practice."；"By converting **time entries into model-based tasks (prompt / document pairs)**, we are able to identify and evaluate how models can contribute to real, high-value legal work."
- **谁写的**："conceptualized and designed by our **legal research team, composed of attorneys**, and constructed using **publicly available documents** to enable transparent evaluation"。
- **两个独立分数**：
  - **Answer score**：定义原文 "**What % of a lawyer-quality work product does the model complete for the user?**"；计分规则："each affirmative requirement was assigned a **positive score**… Negative criteria, such as **hallucinations**, were assigned **negative scores**… Answer score is computed by … **dividing by the total number of positive points available**"。
  - **Source score**：定义原文 "**What % of correct statements does the model support with an accurate source?**"；例："The model's answer must include the termination fee is $10,000,000" 对应 "the model must provide a source for its statement…"。
  - **关键观察（原文）**："Though related, **source score and answer score are independent**. A model can make a number of correct assertions (high answer score) while failing to provide traceability… (low source score)."
- **结果与反向发现**：Harvey 自研模型 "producing **74% of a final, expert lawyer-quality work product**"；**强行要求引用会显著拉低表现**——"the foundation models would consistently **hallucinate sources**（either document text, page number, or both）leading to weak source scores and **far worse answer scores**"。
- **局限自述**："it currently emphasizes tasks that today's models can or should be able to do. This list of tasks falls far short of the goal of providing a benchmark of all tasks…"

**(b) BLB 的四条扩展线（2026）**（<https://www.harvey.ai/blog/expanding-big-law-bench>【一手】）
- 基座分数演进："base model scores going from **60% (GPT 4o | Claude 3.5 | Gemini 1.5) to 90% (GPT-5 | Claude 4.5 | Gemini 3)**"；将发布扩展基准，数据点增加 **五倍以上**。
- 三条扩展线：**Global**（先做 UK / Australia / Spain）、**Practice Areas**（Capital Markets、M&A、Fund Formation、Litigation、Arbitration、IP）、**Legal Research**。
- **方法论自我修正（重要）**："we have found that the **most accurate measure of model capabilities is core BLB: their ability to solve tasks as graded by objective, expert-written criteria**"——即在试过 hallucination rate、sourcing、retrieval 之后，**回归到 expert rubric 的核心分**。
- **用 BLB 做行为探测**：概念混淆的 canary（美国联邦证据法两组易混概念，早期模型会混甚至互换，被当作 "a **canary** for collecting additional data on any model's internalization of legal rules"）；**Sycophancy 探测**（把同一 prompt **改写成三种立场**——中立 / 作为 GP 想找漏洞 / 作为 MFN 持有人想获益，看模型是否因提问者立场而偏离原正确预测）。
- 自述："it is not yet a silver bullet… we wanted to focus where it had been most impactful — **providing insights about model behavior rather than answers about specific outcomes**"。

**(c) BLB: Retrieval**（<https://www.harvey.ai/blog/biglaw-bench-retrieval>，2024-11-13【一手】）
- 两类数据集：**research datasets**（case law、legislation、EUR-Lex、published law firm memoranda）与 **document collections**（contracts、emails）。
- Query 与 ground truth 构造："we used a mix of **human experts and AI systems** to generate a large number of salient queries… Then for each question, our **AI-assisted experts annotated relevant material** that would need to be retrieved"。样本查询公开在 GitHub `harveyai/biglaw-bench/tree/main/blb-retrieval` `[仅页面引用，未打开]`。
- **指标**："the **percentage of relevant content found** by the retrieval system for a given user query, graded against a **ground truth established in advance by our in-house legal research team**. In technical terms, this is equivalent to **recall at a fixed token threshold**."
- 结果：比 OpenAI / Voyage / Cohere 等方法 "**up to 30% more relevant content**"。
- **三类文档的差异（原文）**：Contracts——"hundreds of pages and potentially hundreds of thousands of tokens of text with **cross-references and defined terms which must be tracked**"；Discovery Emails——"short documents… **complex relationships (e.g., email threads) and rich metadata**"；Research Databases——"millions of documents… relationships like **recency cannot be captured by vanilla semantic search**"。
- **律师的真实相关性判据（原文）**：case law 看 "not only relevant but also **recent and controlling in a jurisdiction**"；Merger Agreements 看 "**industry, deal size**"。
- **Harvey 检索取胜的三个原因**：**Metadata**、**Features（如 recency）**、**LLM-based retrieval**（页面在此处被截断，第三点说明未取到）。
- **公开发现**：MA（Merger Agreements）与 SPA（Stock Purchase Agreements）在常规 RAG 下表现差异巨大，尽管律师认为两者相似——"These gaps confirm the value in thinking about **domain- and task-specific retrieval**"。

**(d) 人审 / 自动化 eval pipeline / 数据服务三支柱**（<https://www.harvey.ai/blog/scaling-ai-evaluation-through-expertise>，2025-05-22【一手】）
- 三支柱：**Expert-led reviews** + **Automated evaluation pipelines** + **Dedicated data services**。
- **Retrieval golden set 两步法**："we collaborate with domain experts to develop **retrieval datasets: curated 'golden' query sets**" → "For each query, these experts identify the most relevant supporting documents." → 用 **precision, recall, and NDCG** 评测；原文声明 "These metrics have proven **highly predictive of real-world user satisfaction**"；还测 varying levels of **retrieval power** 与 **model context** 占用，以理解 "tradeoffs between quality, speed, and cost"。
- **两种人类评估协议**：**A/B preference tests**（"Experts see two anonymized answers side-by-side, with **model order randomized**"）与 **Likert-scale ratings**（1 "very bad" 到 7 "very good"，评 accuracy / helpfulness / clarity）。偏差控制原文："randomized ordering, standardized prompts, and anonymized content — help **reduce labeling bias** and allow us to detect **statistically significant** improvements"。公开案例数字：GPT-4.1 vs GPT-4o，"The mean rating improved by over **10% (from 5.10 to 5.63)**, and the median score rose **from 5 to 6**"。
- **自动化 eval 产出**："a **grade**… and a **confidence score** that indicates how reliable that grade is."
- **三种用途**：**Routine Evaluations**（"a suite of lightweight **canary evaluations nightly**… catching regressions in **sourcing accuracy, answer quality, legal precision**"）、**Production Monitoring**（"monitor **anonymized** production data… **without compromising client confidentiality**"）、**Model Vetting**。
- **Knowledge Source Identification 专项**：High-Volume Fuzzy Matching + Metadata Weighting → **LLM 做二元文档匹配判定**；"yielded **over 95% accuracy** on our internal benchmark dataset **validated by attorneys**"。
- **评估数据服务**："We established a service dedicated to evaluation data, **isolated from Harvey's primary application** to prevent unintentional data leakage… our **fine-grained role-based access control system enforces strict privacy policies at the row level**"。（**该页正文在此处被截断 → 此子问题的完整细节未找到公开资料**）

**(e) 合同理解侧 benchmark 的 ground truth 治理**（<https://www.harvey.ai/blog/contract-intelligence-benchmark>【一手】）：**签约的 transactional attorney 与 Review tables 分别作答 → 比对分歧 → 由内部 Applied Legal Researchers (ALRs) 裁决分歧**；**双方一致的样本也会被抽样复核**（"ensure that agreement didn't cover up misunderstanding"）；此后每月新增、复核、评测数千个数据点。**published 后的评测集会被 lock（不可变）**作为可复现基线；行级 RBAC 分 **public / confidential / restricted** 三层。

**(f) 其他已确认存在但未打开的 eval 页面**（均 `[仅 sitemap，未打开]`）：`biglaw-bench-hallucinations`、`biglaw-bench-sources`、`biglaw-bench-workflows-spa-deal-points`、`introducing-big-law-bench-global`、`introducing-biglaw-bench-arena`、`introducing-harveys-legal-agent-benchmark`、`using-elo-scores-to-build-better-legal-ai`、`contract-intelligence-benchmark`、`legal-agent-benchmark-initial-results`、`legal-agent-bench-mim-and-a-due-diligence`、`legal-agent-benchmark-in-house-contracting`、`a-framework-for-domain-specific-evaluations`、`legal/evaluation-terms-of-service`、`research`。

**⑤ 关键设计决策（对守衡可迁移的一条）**

**Matter（客户事项）作为原子安全单元，并把"权限系统"外包给既有 system of record，同时 fail closed。**

`[推断]` 对守衡的含义：

| Harvey 的做法 | 守衡的对应物 |
|---|---|
| matter 作为**硬安全边界**（"**not as a metadata tag, but as a hard security boundary**"） | 品线 / 店铺 / 平台作为判定边界——守衡已有 `product_lines` 机制但 `rules_scoped = 0`，即"**声明了没生效**"，这在 Harvey 的判据里属于最危险的一类 |
| **fail closed**：不确定就不读，并标记不确定 | 判定引擎遇到"无规则可命中"时应**显式标记为盲区**，而不是默认合规 |
| 权限源不自建，**同步 Intapp / iManage 为 system of record** | 飞书多维表格作为权威源时，**权限判定应继承飞书表的可读范围**，不自建平行权限 |
| **answer score 与 source score 分开且相互独立** | 判定准确率与**引用可追溯率**必须分开度量；上游引用是"证明"而非"声明" |
| 引用必须结构可验证，否则模型**会编造来源** | 结论中的规则 / 条款引用必须是**结构化 ID 校验**（指向真实存在的规则 ID），不靠模型自由书写 |
| 评测任务从 **time entry** 派生（"all work is billed"） | 评测任务从**人工改判记录**派生——它天然带业务上下文 |
| 写操作**先出计划、人确认、可撤销** | 规则库的任何自动修改都应"提议 + 人批 + 可回滚" |
| **golden query set 由领域专家标注 + 分歧裁决 + 一致样本抽样复核** | 评测集的入集需要"双人独立判定 + 分歧裁决"流程，而不是单人写期望值 |

**⑥ 未找到 / 存疑**

- **索引期是否把 DMS / Intapp ACL 落到 chunk 级元数据** —— **未找到公开资料**（公开只说 permission-aware + retrieval/context/output 三层强制 + 查询期继承用户权限）。
- **公共知识源的刷新频率与法规版本语义** —— **未找到公开资料**。
- **语义级去重（文档级重复内容消解）** —— **未找到公开资料**（只有 hash 级变更去重）。
- **评估数据服务的完整设计** —— 官方页面正文在 "Data Management" 段落后被截断，**未找到公开资料**。
- **面向终端用户的"AI 判错了 → 申诉 → 翻案"流程、复核 SLA、翻案回流** —— **未找到公开资料**（但**误判的工程处理**有明确公开：subagent 在各自文档分支工作、带 rule 标签的 tracked change、收尾按版本控制方式 merge，两条规则触碰同一文本的 collision **escalate 给 lead agent 裁决**；失败模式定性为 "reviews could **over-redline, miss flags, insert suggestions in the wrong location, and miss whose paper the contract was on**"；人工复核走 **Review Queue & Assignment**）。

---

### 3.4 Abridge（医疗）：Contextual Reasoning Engine 的四子层与「虚构检测」

**① 知识库分层与自己用的术语**（<https://www.abridge.com/abridge-contextual-reasoning-engine>【一手】）

伞形术语是 **Abridge Contextual Reasoning Engine（上下文推理引擎）**，官方给出**四个子层**：

| 子层 | 官方原文 |
|---|---|
| **EHR CONTEXT** | "Contextual awareness beyond the conversation with **dynamically integrated data from previous patient encounters, health system-specific guidelines, and clinician preferences**." |
| **PREDICTED PROBLEMS** | "Capture more precise problems by recognizing and grouping medical problems with language that **aligns with appropriate billing codes**." |
| **ORDERS** | "Lighten the cognitive load on clinicians by capturing **EMR-integrated and actionable outputs, like medical orders**, for clinician review." |
| **CODING** | "Increase the value of clinical conversations with **auditable notes, tying AI-generated outputs to source information across all input data—powered by Linked Evidence**." |

外围层：产品三线 **Clinicians / Revenue Cycle / Nursing**；能力两件 **Clinical Decision Support (CDS)**（"Context-aware evidence"）与 **Care Signals**；证据源层 **Content Sources**（"brings together insights from leading sources of medical evidence"）；**Linked Evidence**（"enables clinicians to see evidence for each AI-generated summary"；"Abridge-generated draft clinical documentation is **traceable to the source conversation**"）；**Claim-verification 护栏层**（自研 task-specific 语言模型，检测并评估每条 claim 的支持度，再由自动化**纠正系统**处理）。

> **这是五家中"知识层"分得最细的一个**：输入侧五类（医学证据源 / 患者 EHR 史 / 机构指南 / 医生偏好 / 对话），输出侧四个可交付物（问题-编码-医嘱-审计链）。引原文："intelligently associating what's going on in this conversation with all these other pieces of information"（CEO Shivdev Rao, MD）；"We're pulling in all kinds of data, metadata, insights, information from **any number of seemingly disparate sources**"（Chief Scientist Zachary Lipton, PhD）。

**Abridge 实际运行两套不同的语料**：

| 语料 | 内容 | 官方依据 |
|---|---|---|
| **患者图表上下文语料** | 既往就诊、用药、检验、"the patient conversation and clinical history" | "Abridge draws on the patient conversation and clinical history to deliver insights specific to the patient—**medications, labs, and clinical context are already there**." |
| **授权医学知识语料** | **UpToDate**（Wolters Kluwer，"**our first high-quality data partner**"）、**NEJM Group**、**JAMA Network**、**American Heart Association**（附注 "*American Heart Association licenses selected scientific content to Abridge."）、**American Diabetes Association**、**American Academy of Family Physicians**、**EBMcalc** | abridge.com/cds；blog/building-trusted-healthcare-ai |

CDS 与文档的边界是刻意划的："this capability lives within Abridge's interface, **not the documentation itself**"。

**② 语料治理**（已打开）

| 子问题 | 公开事实 | 来源 |
|---|---|---|
| EHR 集成 | "Abridge seamlessly integrates with leading EHRs"；**Epic Partners and Pals 首家 Pal**（2023-08-16）；**Epic Workshop**（与 Mayo Clinic + Epic 的护理环境文档，2024-07-23）；EMR 名单 **Epic / Athena / AllScripts / Cerner / eClinicalWorks / NextGen / Other**（来自其自家表单枚举）；集成深度主张引 Penn 研究脚注："Deeply integrated EHR tools take up **to 75% less time** for a physician to use than an external app or web site" | press-release/epic-pals；press-release/abridge-mayo-epic；reports/adoption-scale-impact |
| 刷新 | 特化模型更新 "shipped '**quietly**,' which is to say **without build, configuration, or workflow disruption**. Health systems are **not asked to implement new versions**. Clinicians are **not prompted to update apps**."；CDS 授权内容由合作方刷新，Abridge 只说维持 "growing body of sources"。**具体刷新节奏 = 未找到公开资料** | blog/clinical-ai-specialty-models |
| 增量 / 去重 | **未找到公开资料** | — |
| 权威源认定 | **有且很强，但形式是"授权采购"而非"域名白名单"**：全部医学证据源来自具名授权方（UpToDate / NEJM / JAMA / AHA / ADA / AAFP / EBMcalc）。`[推断]` 这把幻觉面从"模型懂不懂医学"迁移到了"检索有没有取对源" | abridge.com/cds |
| 数据驻留 | **未找到公开资料**。公开页面无按地域的数据驻留表、无 EU 数据边界声明——**这是与 Dragon Copilot 的鲜明反差** | privacy |
| 保留 / 删除 | Customer Data（"may include Protected Health Information (PHI)"）"governed **exclusively** by the terms of our agreements with those customers, including our **Business Associate Agreements (BAAs)**"；一般保留"as long as needed to fulfill the purposes for which it was collected"；**声纹特例**（消费侧 Abridge Scan）："permanently destroy it … (**one year after your last use of the mobile application**)" | privacy |
| 训练口径（**必须精确引用，不要泛化**） | CDS 页原话是 "**Queries run entirely inside Abridge's architecture. PHI never leaves it and is never used for training.**"——**这句的作用域是 CDS 查询路径**。另有："Our offline evaluations rely on datasets curated from **de-identified Abridge encounters**"；"we collect annotations on **de-identified encounters**"；BAA §2.2.4 明确许可 "**Use PHI for purposes of de-identification of the PHI**"。**Abridge 从未发布过 Microsoft 式的"我们的模型只训练于 X"这句话。** | abridge.com/cds；tech.abridge.com/blog/ai-evaluation-at-abridge；terms/business-associate-agreement |
| 集成规范 | **无 FHIR / HL7 接口规范、无 SMART-on-FHIR 启动文档、无资源级集成契约**（对比 Microsoft 公开了 `Dragon standard payload`） | — |

**③ 权限：索引期 vs 检索期** —— **官方原话属于哪一档：属于「契约治理档」，两档机制性描述均缺失。**

**Abridge 在这个子问题上是五家中公开度最低的一家。** 能公开确认的只有两类东西：

**(a) 契约层：BAA 条款异常详细**（<https://www.abridge.com/terms/business-associate-agreement>【一手】，Abridge = Business Associate，客户 = Covered Entity）

| 条款 | 义务 |
|---|---|
| §2.1 | "Business Associate shall **not Use or Disclose PHI** … **except in accordance with any Underlying Agreement**, or as permitted by this BAA or Required by Law." |
| §2.2.4 | "Use PHI for purposes of **de-identification** of the PHI"——**显式许可的用途** |
| §2.3 | 遵从 "**Subpart C of 45 C.F.R. Part 164**"（HIPAA 安全规则） |
| §2.4 | 知悉后 **10 个工作日**内通知非许可使用/披露与安全事件；发现后**不晚于 30 个日历日**提交书面泄露报告 |
| §2.6 | 分包方 flow-down："reasonable assurances" 遵守实质相似的约束 |
| §2.8 | Designated Record Set 在请求后 **15 个工作日**内可供查阅/复制 |
| §2.10 | 披露清单支持 **30 天**内提供 |
| §3.4 | 客户保证其"has obtained any necessary authorizations, consents, and other permissions" 后才把 PHI 放入 Abridge 系统 |
| §4.3 / §4.4 | 终止时返还或销毁全部 PHI，"retain **no copies**"；**但双方约定返还/销毁通常不可行，BA "will need to retain such PHI"** |

**(b) 产品层：治理性表述**——"**Clinician-in-the-loop** — Clinicians decide what information matters, what to include in notes, and what actions to take."；"Insights are grounded in each patient's clinical history, with **citations linked to original data in the EHR**."；"Queries run **entirely inside Abridge's architecture**."（`[推断]` 这是**数据出境控制**，不是访问控制机制：它断言 PHI 不流向外部模型供应商。）

**未找到公开资料**：Abridge 如何强制图表级或角色级访问（是否继承 EHR 会话、SSO 如何工作、admin 控制台做什么），**完全未公开**。`[推断]` 鉴于其 Epic PALS / 嵌入形态与 Abridge 侧零访问控制文档，图表 ACL **很可能**委托给宿主 EHR——**但本轮无法验证，不得作为事实陈述**。

用 Harvey 给采购方的三问清单来评估：Abridge 目前公开材料**只回答了"目的层"（clinician-in-the-loop），未回答"数据层与检索层如何强制"**。

**④ 评测：公开方法学、指标、golden set、人审、离线 vs 在线**

**(a) 框架：when / what / how 三问**（<https://tech.abridge.com/blog/ai-evaluation-at-abridge>【一手】）
- **When** = 离线预部署 → 分阶段灰度（"limited release with a **curated set of partners who act as early adopters**"）→ 在线持续评估（防 drift）。
- **What** = **safety**（"free of clinically relevant errors"）/ **accuracy** / **fairness-equity** / **usability** 四维，且明确区分 **intrinsic attributes（系统本身多好）vs outcome-based attributes（是否真的产生正向影响）**。示例：CDS 内在准确性 = 回答完整性；**结果准确性 = diagnostic quality（取决于医生如何跟进）**。
- **How** = 专家结构化反馈 + **盲法头对头偏好比较（blinded head-to-head）** + 对有正确答案的任务收集专家标注并建内部 benchmark（点名 **medical calculator use by agents** 与 **medical coding models 准确率**）+ 在线显式反馈（星级评分、合作方上报错误）与**隐式反馈（医生对生成 note 的编辑、对 CDS agent 的追问类型）** + **LLM Judges**。
- **LLM judge 的元评估（关键治理动作）**："**These LLM judges are themselves first validated offline on clinician annotations to ensure that the results they give are consistent with clinician adjudications.**"
- **一句方法论立场**："evaluation is a process and not a destination: **no static set of evaluations can cover the growing set of quality dimensions**."

**(b) 离线基准数据集**（<https://www.abridge.com/ai/science-ai-evaluation>【一手】）
- 内部基准数据集 = "**clinical audio, gold standard transcripts, human-written reference notes, and rich metadata on patient characteristics**"。
- ASR 指标："**word error rate** and medically tailored metrics (e.g., **recall of medical terms**)"; plus "capture of newly minted medication names"。
- Note 生成指标："variants of **precision and recall (e.g., of medical concepts)**, which serve as proxies for **factuality and completeness**"。
- 分层分析 "to assess performance across diverse patient subpopulations"；ASR 对外校准用公共集 **Librispeech**（对标 Whisper v3）、多语用 **FLEURS**。
- **明确的范围限制**："Abridge is **not designed to serve as a translation service**, and it is no substitute for a trained medical interpreter."
- 数据集构造：**de-identified Abridge encounters**，并按目标能力**刻意切片**（例：为评估心内科 note 处理复杂病史的能力，选取"多次既往手术与诊断"的心内科就诊），理由原文："**publicly available and external data rarely reflect**" 真实复杂度。

**(c) 在线指标 —— 唯一公开的硬数字**
- 主端到端指标：临床医生在 note 编辑界面的 **1–5 星级评分**。
- "over the last three months (May-July), we collected **tens of thousands of star ratings, with an average rating of 4.3 out of 5** for English-language encounters."
- 西班牙语："risen from an average of **3.7 during the month of February to its current average of 4.1**."
- 被动信号："the **edits required to finalize the note**"；主动信号：评论与星级。

**(d) 虚构检测（本节最常被误引的一个数字，必须写准）**（<https://www.abridge.com/ai/science-confabulation-hallucination-elimination>【一手】）
- 方法：**in-house, task-specific language model**，训练于 "a curated set of **over 50,000 training examples**"，"designed to **detect and assess the level of support of each claim** in the note"；随后"**correct it using another automated system**"。
- 结果原文："our technology … **catching 97% of the confabulations, while GPT-4o only catches 82%**. In other words, a standard off-the-shelf model misses **six times as many** confabulations as the Abridge system."
- **⚠️ 引用纪律：这是「虚构检测的召回率」，不是 note 准确率。** Abridge **没有**发布 note 级准确率或事实性百分比。把 97% 写成"note 准确率 97%"是错误引用。
- Abridge 自陈的诚实边界："**No guardrail is perfect**, and clinical conversations can contain legitimate sources of ambiguity, for instance, where the 'correct' note may rely on clinical judgements that were **not verbalized during the encounter**."
- 明确点名的失败模式：**说话人误归因（speaker misattribution）**——"it is not entirely clear from the transcript alone if a statement is made by the patient, the clinician, or a caregiver"（如 "patient reports that their dog is sick"）。
- 人审位置：护栏"supported by **over one thousand hours of human validation**"；且临床医生审阅是强制的——"**All clinician notes generated by Abridge are reviewed and edited** (if necessary) by the clinicians who conducted the patient encounter before being entered into the EHR."

**(e) 特化模型验证栈（"the gauntlet"）**（<https://www.abridge.com/blog/clinical-ai-specialty-models>【一手】）
1. **Automated "Judge" layer** —— LLM judges 打分至少两个具名变量："**Non-Inferiority**: Strict safeguards that ensure new specialty models match or exceed the generic baseline performance" 与 "**Misattribution Rates**: Monitoring against 'hallucinations' or misattributed patient data."
2. **Clinical Success Directors** —— 用 "a predefined, data-driven baseline" 评估真实世界例子。
3. **External third-party auditors** —— 复核 "hundreds of additional examples"。
4. "**Only when a model clears every layer** do we consider deploying."
开发过程："'**clinician-in-the-loop**' process pairs product and engineering leads with Clinician Science and Clinical Success Directors in cross-functional collaborations we call '**NoteGen**' teams"，并打磨"the underlying '**recipes**' that shape how different sections of notes are generated"。

**(f) CDS 评测三维度 + 一个数值安全分**（<https://www.abridge.com/blog/how-we-evaluate-clinical-decision-support-for-enterprise-readiness>【一手】）

| 维度 | 方法 | 结果 |
|---|---|---|
| **Clinical Evaluations** | 多位医师独立评审真实去标识 encounter，校准到共同 rubric；"**over 1,000 rubrics** — a material increase over the size of existing benchmarks that use real encounters, like the **NOHARM study**" | — |
| **Boundary Adversarial Evaluations** | "directly harmful prompts, scope violations, attempts to bypass clinical judgment, discriminatory care scenarios, jailbreaks, and medicolegal edge cases" | — |
| **Clinical Safety Evaluations** | "wrong drugs, missed critical diagnoses, harmful management advice, and medical misinformation. **Flagged cases are manually reviewed by clinicians.**" | "The system currently scores **99.5% across 1,000+ cases**. In the small number of cases where potential safety issues were identified, **most have been due to limitations in source material**." |

上线纪律：内部测试 → "a small group of clinicians at **highly-engaged preview partners**" → "entire departments at designated organizations" → GA；"We maintain the ability to **tune or roll back at any stage**."
**诚实的局限**：这三项都是**厂商自设、厂商自跑**的评测，**没有一项被描述为外部审计或同行评审**，99.5% 也没有置信区间与分母拆分。

**(g) 外部验证与文献边界**
- Abridge 支持合作医疗系统的研究团队做独立研究（含前瞻性随机试验）；引用一篇 Nature 论文指出 4,609 篇评估临床医学 LLM 的同行评审研究中**仅 19 篇是前瞻性随机试验**（`[仅页面引用，未打开]`）。
- **唯一直接对撞 Abridge 与 DAX 的独立研究**：**Webb 等，*Appl Clin Inform* 2026;17(1):118-126，PMID 41734793**——UT Southwestern 急诊科、单中心前瞻性交叉试验、6 周、20 例入组/18 例完成、交替 3 周阶段。DAX 在整体感知工作负担上降幅更大（**median 1.5 vs 2; p=0.025**）；SUS 相当（**73.5 vs 73.5; p=0.94**）；UMUX-Lite 86 vs 82.5（p=0.079）；修正版 **PDQI-9 偏 DAX（39 vs 36.5; p=0.011）**；推荐意愿 **9 vs 7.5（p=0.015）**。**但原文结论是**："adjusted models suggested these differences **reflected order effects more than inherent tool differences**." → **正面对撞下未观察到工具本身的可靠差异，这是本节最重要的一条外部证据。** `[子代理 API 读取，未复核]`
- Abridge 的同行评审论文清单（官方列出 16 篇）中与架构最相关的：Krishna 等 ACL 2021《Generating SOAP Notes from Doctor-Patient Conversations Using Modular Summarization Techniques》；Ramprasad 等 ACL 2024《Analyzing LLM Behavior in Dialogue Summarization: Unveiling **Circumstantial Hallucination** Trends》；**Khosla 等 EMNLP 2020《MedFilter》**——**这是与 Abridge 关联的唯一明确点名"本体知识（ontological knowledge）"组件的论文**。

**(h) 监管状态**：openFDA 510(k) API 查询 `applicant:"Abridge"` 返回 `NOT_FOUND`；abridge.com 全部页面**无任何 FDA 清除、De Novo 或监管路径声明**。Abridge 把产品定位为**经医生审阅的辅助性文书工具**，而非受监管器械。`[推断]` **Abridge 无 FDA 510(k) 清除**；`[待确认]` 其监管路径的推理未公开。**明确未找到**：**Abridge 无任何监管申报的公开资料**。

**⑤ 关键设计决策（对守衡可迁移的一条）**

**把「内在质量」与「结果影响」显式拆开并同时测，并要求 LLM judge 先与人类专家标注对齐才算通过验证。**

`[推断]` 对守衡的含义：

| Abridge 的做法 | 守衡的对应物 |
|---|---|
| **intrinsic（回答完整性）vs outcome-based（diagnostic quality）显式拆开** | 守衡必须把"规则库自身的准确率"与"审核动作带来的业务结果"分开度量——后者依赖人怎么跟进，不能被前者冒充 |
| **LLM judge 必须先在医生标注上验证一致** | 若守衡引入模型自评，必须先测"模型判定与人工改判的一致率"，达不到阈值就不许用它做自动评测 |
| **把"医生对生成文本的编辑"当一等评测信号** | 每一次人工改判都是高质量相关性标注——这是守衡手上最被浪费的资产 |
| **为"虚构内容"单独训一个小模型**（而非依赖通用 LLM 判断） | 引用核验不应依赖通用模型自述，而应是**独立的结构化校验器**（规则 ID 是否真实存在、是否适用于本品线） |
| **护栏做"检测 + 自动纠正"两级**，并公开承认 speaker misattribution 是残余失败模式 | 判定引擎除了"发现问题"还应有"给出纠正方案"，并为已知失败模式保留显式的拒答/升级通道 |
| **CDS 刻意不进病历**（"not the documentation itself"） | 守衡的"建议"与"裁决"必须分开承载：建议可以不进权威制品，裁决必须进且可审计 |

**⑥ 未找到 / 存疑**

- **图表级 / 角色级访问控制（chart-level / role-based ACL）如何强制** —— **未找到公开资料**（无 admin console、SSO、chart-scoping 的任何描述）。
- **数据驻留承诺** —— **未找到公开资料**（无地域表、无 EU 数据边界声明）。
- **FHIR / HL7 接口规范、SMART-on-FHIR 启动文档、资源级集成契约** —— **未找到公开资料**。
- **授权 CDS 语料的具体刷新节奏** —— **未找到公开资料**。
- **监管路径的推理** —— **未找到公开资料**（无 FDA 清除，也无监管立场声明）。
- **note 级准确率 / 事实性百分比** —— **未找到**。Abridge 公布的是**虚构检测召回率（97%）**与 **CDS 安全分（99.5%）**，**不是 note 准确率**，勿混用。
- **"Abridge medical ontology" 作为具名产品层** —— **未找到**（唯一本体相邻物是 2020 年 EMNLP MedFilter 论文，以及 PREDICTED PROBLEMS / CODING 下的计费码对齐措辞）。
- **"Abridge Enterprise" 作为当前产品名** —— **未找到**（历史物是 2021 年 "launches enterprise solution" 新闻稿）。
- **子代理读取路径的部分内容**：本节中来自官方工程博客《AI Evaluation at Abridge》与部分 Abridge 评测页面的细节，由并行子调研线读取并用官方 URL 复核定位，主报告侧未逐页重跑，保留 `[子代理已打开，主代理未复核]` 标注。

---

### 3.5 Microsoft Dragon Copilot（原 Nuance DAX）：权威源白名单 + 患者级隐私标记

> **命名前置**：**DAX Copilot 已于 2025-03-03 与 Dragon Medical One 合并为「Microsoft Dragon Copilot」**；`nuance.com/healthcare/*` 全部 **301 → `microsoft.com/en-us/health-solutions`**，Nuance 医疗站不再独立存在。正确文档前缀是 `learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/`。官方合并措辞："Microsoft Dragon Copilot brings together the trusted voice dictation capabilities of **Dragon Medical One** and the ambient listening capabilities of **DAX Copilot** with fine-tuned generative AI and healthcare-adapted safeguards."

**① 知识库分层与自己用的术语**（这一家是全报告文档化程度最高的部分）

| # | 层（官方术语） | 官方原文 |
|---|---|---|
| 1 | **Capture —— `Dictation` vs `Ambient recording`** | "Dictation: Capturing audio from a **single clinician**…" / "Ambient recording: Capturing audio from **multiple speakers** during a patient visit." |
| 2 | **Session / Recording / Encounter 信封** | "`Session`: A **bundle of recordings** associated with a specific encounter."；"Multiple recordings can be generated for a single encounter." |
| 3 | **转写层（含 diarization）** | "Speech-to-text (STT) converts single or multiparty speech into text, including unspoken punctuation and **speaker role identification**."；可靠性范围："Ambient diarized speakers **≤ 2** — One speaker (the clinician) is identified as **primary**. All other speakers are **aggregated**." |
| 4 | **生成层** | "Ambient note generation (physicians): … produces a **draft clinical note**" / "Flowsheet capture (nurses): … based on audio inputs and **enabled customer flowsheet templates**." |
| 5 | **生成式 AI 层** | "Large-language-model (LLM) functionality that can create, transform, or summarize clinical content when **triggered by templates or free-form prompts**." |
| 6 | **专科模型层** | "All specialties are supported … however the following specialties have been **optimized**"——**46 个优化专科**（英文 US/CA），英文 UK 7 个、荷兰语 6 个、德语 5 个、法语 8 个 |
| 7 | **载荷层 `Dragon standard payload`** | "`Payload`: A JSON file consisting of content generated for a specific use case from a session. **Each new recording triggers the creation of a new payload.**" |
| 8 | **本体 / 资源层** | "`Resource`: **The standards used to describe a category of AI-generated healthcare data.**… a clinical document section resource (such as **HPI**) can be imported into a note template, or a **condition resource** can supplement a problem list."；content types: `document_section` / `condition` / `order.{type}` |
| 9 | **编码系统子层** | Context `codes` 为 "**LOINC or SNOMED-CT** Codes"；实例：HPI → `{"identifier":"10164-2","system":"loinc.org"}` 带 `spoken_forms` |
| 10 | **证据 / 关系链接层** | "**Resources can be linked to other resources.** For example, an **order resource can be linked to a condition resource as the reason for placing the order**." |
| 11 | **EHR 患者上下文层** | **Optional service data**："**FHIR, HL7, and/or EHR resources for Patient, Practitioner, and Encounter** … needed by Dragon Copilot to **accurately generate and contextualize clinical content**"；并注明 "Patient identifiable information such as **name, DOB and MRN is associated with the generated AI draft**" |
| 12 | **外部知识 / RAG 层 —— `Information Assist`** | "access to **external information from trusted sources**"，由 **Azure Healthcare Agent Service** 编排，"to an **approved, vetted, and tested external source**" |
| 13 | **Clinical Safeguards 引擎** | "filters for **harmful/non-healthcare related content, hallucinations, and omissions** and assures **provenance, verification, and clinically contextualized responses**" |
| 14 | **RAI 护栏栈（具名顺序）** | **Guardlist**（hate/sexual/violence/self-harm/protected material/prompt-injection 词表）→ **Azure Content Safety**（harm scores）→ **Dynamic Blocklist** → **Allow list**（"specifically created for the Dragon Copilot workflow to allow words flagged by Guardlist that are deemed necessary"）→ **Intent Classification Module**（"rejects prompts that are irrelevant … non-medical related, related to medical advice, or **clinical decision-making**"）→ **Context Grounding** → 响应后复跑同一批检查 → **Prompt Injection checks** |
| 15 | **扩展层（AI apps and agents）** | 第三方 app/agent 经 **technical configuration package** 与 **adaptive cards** 接入；伙伴含 Elsevier、OpenEvidence、Wolters Kluwer UpToDate、Atropos Health、Canary Speech、Lightbeam、Pangaea、Ensemble、Regard、RhythmX AI、Cohere Health、Humata Health、Rhyme、Press Ganey、Artisight、hellocare.ai |

> **证据分级**：第 9 层中 `Context` 属性含 `content_type` / `display_description` / `spoken_forms` / `codes`、以及 "HPI → LOINC `10164-2`" 这一实例，来自子调研线对 `.../ontology/coding-systems` 与 `.../resources/context` 的读取 → **`[子代理已打开，主代理未复核]`**。第 3、4、5、13、14 层来自 `whitepapers/transparency`、`whitepapers/transparency-information-assist`、`sdk/glossary` 等页 → **`[子代理已打开，主代理未复核]`**。第 11、12 层由主报告侧亲自打开复核。

**② 语料治理**

**(a) 语料被显式拆成 required vs optional service data**（<https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/data-collection>【一手】）

**Required service data**（"the **minimum data necessary** to deliver clinical drafts, documentation, and other AI features"）：患者健康数据（"the **encounter audio, generated transcript, and all versions of edited AI drafts and extracted data**"，含"the clinical documentation including the **clinician corrections**… and the **final, signed clinical documentation**"）、听写音频、医务人员信息（姓名/专科或执照/邮箱）、使用分析、**产品反馈**（"**clinical AI draft ratings and feedback, which is collected to continuously improve AI accuracy**"）、产品配置与设置（含 "**organization-wide templates**"）、服务诊断、桌面端诊断日志。

**Optional service data** = EHR 患者上下文层："**FHIR, HL7, and/or EHR resources for Patient, Practitioner, and Encounter** … needed by Dragon Copilot to **accurately generate and contextualize clinical content**"。

**(b) 权威源认定 —— 这是全报告最明确的一家**（<https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/transparency-information-assist>【一手】）
- **"Research queries are limited only to vetted sources that have been approved, tested, and included in users source list** in the Dragon Copilot **Settings** menu."
- **"Only sources that have been enabled via Settings can be searched. Only web-based data are available to search (PDFs referenced by websites are not currently in scope)."**
- 检索行为："Multiple sources will be searched simultaneously"；**"Searches will provide the top three sites from those in scope, prioritizing based on search engine ranking."**
- **启用需要四级串联**：① 该地区已批准（目前**仅美国**、**仅英语**）→ ② Microsoft 在 Dragon admin center 为组织启用 → ③ 组织管理员为用户启用 → ④ 用户在 Settings > Information Assist 启用并选源。原文另提醒客户 "should add, to any allow lists, relevant websites"，因为被引用的站点必须在客户的 allow list 内。

**(c) 训练口径（必须写准，这是一个被广泛误传的点）**（<https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/privacy>，最后更新 2026-08-20【一手】）

> "Microsoft **securely transmits select Customer Data** (such as **audio recordings and transcriptions, clinical documentation, and corrections or additions to generated clinical documentation**) to a **designated Dragon Copilot research environment** where it is processed and **anonymized within 90 days** (measured from the day the data was captured or generated)."
> "**Resulting anonymized data is used to provide Dragon Copilot, including to continually enhance the safety, accuracy, and capability of Dragon Copilot's core functionality and AI/ML models.**"
> "**Dragon Copilot's AI/ML models are trained solely on anonymized data.**"
> "Microsoft's anonymization process is specifically designed to meet relevant thresholds … the standard for **de-identification under HIPAA**, the PIPEDA and **Quebec Law 25** guidance on **irreversible de-identification** in Canada, and the standard for **anonymization under the GDPR (including Recital 26)**."

> **⚠️ 必须写准的一句话**：官方原文是 "trained **solely on anonymized data**"，即 **Microsoft 会用客户数据训练，但只用 90 天内完成匿名化的数据**——**不是**"不用客户数据训练"。常见的中文转述"DAX 不用客户数据训练"与官方隐私白皮书不符。另需注意：**clinician corrections 与最终签署的 note 被明确列为传输到研究环境的数据**——即最高价值的训练信号是**编辑差分**。

**人审被限定为两个目的**："**In strictly limited scenarios**, Customer Data may be subject to '**human review**' by select Microsoft employees and subprocessors"：① "To resolve customer service tickets and ensure the reliable operation of Dragon Copilot"；② "To ensure Dragon Copilot meets high standards of clinical accuracy and reliability, including through anonymizing Customer Data… This access also includes the use of **human annotators to assist with the creation of anonymized data sets** used for model improvement, development, and evaluation."

**撤回同意的处理（必须写准）**："In the case that a patient revokes previously provided consent, a customer can log a ticket with customer support to have any Customer Data **that can be linked back to the individual patient** purged from the operational and research environment systems. **Resulting anonymized data created by Microsoft prior to the patient's revocation of consent will not be purged.**" → **撤回同意只清可关联数据，已生成的匿名数据不清。**

**(d) 保留 / 删除 / 驻留 / 存储隔离 / 合规**
- 保留与删除："retained, deleted, and purged as set forth in the **DPA**. Customer Data is purged using **Microsoft Purview Data Lifecycle Management**."
- 识别音频："data acquired during an exam is used for **recognition purposes in-memory** and is **never stored in any unencrypted manner**."；客户端："**Dragon Copilot desktop and web: Do not persist data.**"；移动端：libsodium **XChaCha20 with Poly1305 MAC** 逐包加密，"**Audio data is deleted on the device after upload**"；离线时本地加密暂存、恢复连接后自动上传并删除。
- **数据驻留逐国表**（privacy 白皮书 §6）：US→US、Canada→Canada、UK→UK、France/Ireland/Belgium→**France, EU**、Germany/Austria/Netherlands/Switzerland→**Germany, EU**。原文："Dragon Copilot is an '**EU Data Boundary Service**' and stores and processes Customer Data within the **EU Data Boundary**."；"Nursing features are only available in the US and the **data never leaves the geographic region**."；安全白皮书补充：Azure "**10 such locations within the continental United States**"、"**data never leaves a geography**"、部署为 "**active/active**"。
- **存储隔离**（安全白皮书）："Dragon Copilot uses **shared compute resources and dedicated storage**. For physicians customer data is stored in a **customer-specific storage container inside a shared storage account** whereas for nurses customer data is stored in a **storage account within their customer-specific namespace**. Therefore, **each customer's data is segregated**."
- 合规：HITRUST CSF、HIPAA、**ISO 27001/27017/27018**、FedRAMP、**SOC 1 Type 1 / SOC 2 Type 2 / SOC 3 Type 3**、EU & UK GDPR、PIPEDA + 全部加拿大省级隐私法、**C5（德国）**、**HDS（法国）**、**revFADP（瑞士）**、**Cyber Essentials Plus（英国）**。
- **(e) 刷新 / 增量 / 去重** —— **未找到公开资料**。

**③ 权限：索引期 vs 检索期** —— **官方原话属于哪一档：属于「按患者级隐私标记的检索期裁剪」，图表级 ACL 契约上归客户所有。**

**(a) 官方明文把图表级访问控制交给客户**（privacy 白皮书 §2【一手】）：
> "**Customers of Dragon Copilot are also responsible for configuring and managing access controls within their environment** to ensure that **only healthcare professionals with an established therapeutic relationship with a certain patient can access that patient's data**."

→ 这是一次**契约性委托**，不是产品功能。产品内只由两件事兜底：**Context Grounding** 与单用户会话。

**(b) 产品内的上下文边界（本节最该背下来的一句原文）** —— **Context Grounding**：
> "**The context provided to the LLM is grounded in specific note data. External sources and data from other sessions are not allowed.**"

`[推断]` 这是一条**在提示词构造期强制的会话级上下文 ACL**——与基于角色的访问控制是不同的机制。它回答的是"模型能不能看到别的患者"：检索/上下文窗口被**硬性限定在当前 session 的 note 数据上**。配合限制项 "**No collaborative editing** — designed for a single authenticated user per documentation session"，构成双重封边。

**(c) 检索期按患者级隐私标记裁剪（最好的硬证据）**（<https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/specialty-models/intelligent-diagnoses-retrieval>【一手】）：
- "**Diagnoses can be retrieved only for checked-in patients whose records are not restricted or controlled under enhanced privacy access controls.**"
- FAQ 进一步确认："**Will diagnoses be retrieved for patients with restricted records? No**"
- 以及一个容易被忽略的前置条件：必须在**最后一次录音结束前**录入 visit diagnosis 才生效，**problem list 不参与**（须提升为 visit diagnosis）。

→ **结论：Dragon Copilot 是"检索期按患者级隐私标记裁剪"**（restricted record 直接不检索），与 Harvey 的 fail-closed 同属"交付前裁剪"一路；**但权限的定义仍由客户的 EHR / 组织承担**，Microsoft 不自建权限系统。

**(d) 认证与审计**
- "Dragon Copilot authenticates against the customer **Entra ID (Azure AD) tenant using the OpenID Connect protocol**."；"**All Dragon Copilot users have their own unique account.**"
- 嵌入护理流程是一处真实的 ACL 设计点："Within the embedded nursing experience users are authenticated **within the EHR mobile app**. A mapping is maintained within **Dragon admin center** between the **EHR ID and the nurse's Entra ID**."
- Microsoft 侧最小必要："Microsoft HLS follows the HIPAA requirement of '**minimum necessary**'… **Production file access in Azure is restricted**"；"two-factor authentication"、需要知需（need-to-know）、**Security Groups Role-Based Access Controls**、**Secure Admin Workstation (SAW)**、**segregation of duties and least privilege**、"**Access is audited monthly**"。
- 审计日志："date, time, user account (when applicable), event type, IP address and success or failure"；"**Logs are read-only**"；存于 Azure application insights 并摄入 **Azure Sentinel SIEM**。

**(e) 扩展治理：三/四道门**（transparency-information-assist【一手】）：① 该扩展**在使用地区已获批准**（即美国）；② **Microsoft 在 Dragon admin center 为组织启用**；③ **组织管理员为用户启用**；④ **用户在 Settings 中启用并勾选源**。

**④ 评测：公开方法学、指标、golden set、人审、离线 vs 在线**

**(a) 自有指标与流程**（`whitepapers/transparency`【子代理已打开，主代理未复核】）
> "Dragon Copilot AI performance is measured in multiple ways, including: **Word Error Rate (WER)** for STT. **Accuracy score** for ambient note generation and flowsheet capture, and engineered generative AI measured against **standard data sets**. **Latency** for AI processes. Additional standard measures apply … like **service uptime**."
> "Each system was carefully designed and built using detailed **clinical content specifications**, evaluated through batteries of **quantitative and qualitative tests**, **red-teamed** for content and security vulnerabilities, and **reviewed by clinical content subject matter experts** … New AI models are deployed in production after successful **AB tests that compare new models with baseline models**."
> 具名评测指标："**Groundedness, Completeness, Relevance, and Factuality**"，外加 "**Context-based tests using anonymized clinical documents** (notes or flowsheets) and transcripts."

**(b) Information Assist 的 RAG 评测（本节最有方法学价值的一段）**（`whitepapers/transparency-information-assist`【子代理已打开，主代理未复核】）
- **两级测试规模（原文）**："Tests were run once at **Azure Healthcare Agent (platform service) level (2-5k queries)** and then again at **Dragon Copilot (user-app) level (50-100 queries)**"，含不同措辞与变体。
- **RAG 评估的三个判据**：
  - **Groundedness and fabrications** —— "assessing capability of grounding responses on the provided evidence sources, while **refraining from using its own 'internal knowledge'** or providing factually incorrect information"
  - **Answer relevance** —— "the ability to provide a response that is **relevant to the user query**"
  - **Evidence relevance** —— "assessing whether the **selected evidence sources** are relevant to the user query"
- **红队（多维）**：有害内容评测由**在性别/地域/文化视角上多样化的评测团队**执行；**UPIA（user prompt injection）与 XPIA（cross domain prompt injection）** 用自动化 + 人工测试，且**在三种 grounding 源上分别测：credible / customer / harmful adversarial public website**。
- **结果（原文）**：有害内容 "results were **safe with minimal instances of harmful outputs**"；注入攻击 "potential risks were **well-managed**"；**人工 groundedness 评测在 credible sources 上 "indicated a low frequency of ungrounded information"**，但**明确警告客户源**："when utilizing **customer sources**, it is important to **only use trusted documents** and **evaluate the system's provided outputs prior to implementation** as the nature and complexity of different customer sources can vary significantly."
  → **这是一条极有价值的诚实声明：同一套 RAG 管线在可信源上表现好，在客户自建语料上不保证。**
- UX 级缓解：**Chat Safeguards** 生成 AI 签名与免责声明；**每个答案附带对应证据**（"for provenance, explainability, and transparency, allowing end users to **verify the correctness** of the provided answer"）；答案卡片带 **Feedback** 图标。
- 自陈局限："The evaluation results suggest a promising level of generalizability across different use cases that were **not explicitly tested**."

**(c) 官方自陈的产品级失效模式（罕见地坦率）**
> "Potential transcription errors due to background noise, overlapping speech, or **accented speech not well represented in training data**."
> "Summarization or extraction inaccuracies such as **omitted findings or hallucinated details**, especially in preview markets or languages."
> "Latency sensitivity in low-bandwidth environments (**>250 ms** may affect real-time dictation experience)."
> "**No collaborative editing** — designed for a single authenticated user per documentation session."
> 具名 RAI 关切："**over-reliance** on autogenerated text（'**automation bias**'）、privacy of voice data、以及 **fairness when models underperform on dialects or accents**"。
> 运行上限：ambient diarized speakers **≤2**；单次 ambient recording **75 分钟**；STT 网络延迟 **<200 ms**。

**(d) 厂商宣称的效果数字 —— 注意这些是问卷不是试验**（2025-03-03 合并公告【一手】）

| 宣称 | 脚注来源（原文） |
|---|---|
| "clinicians reporting **five minutes saved per encounter**" | "[1] Microsoft survey of **879 clinicians across 340 healthcare organizations** using DAX Copilot; July 2024" |
| "**70%** of clinicians reporting reduced feelings of burnout and fatigue" | "[2] … same survey; July 2024" |
| "**62%** of clinicians stating they are less likely to leave their organization" | "[3] … same survey; July 2024" |
| "**93%** of patients report a better overall experience" | "[4] Survey of **413 patients** conducted by multiple healthcare organizations whose clinicians use DAX Copilot; June 2024" |

**规模宣称**："DAX's ambient AI technology, which has assisted **over 3 million ambient patient conversations across 600 healthcare organizations in the past month alone**"。

**(e) 厂商无关的独立验证研究（必须按此清单引用）**

| 研究 | 设计 | 具名厂商 | 关键结果 |
|---|---|---|---|
| **Lukac 等，*NEJM AI* 2025;2(12)，PMID 41497288** | **UCLA Health；平行三组实用型 RCT，1:1:1 协变量约束随机化，238 名门诊医师、14 个专科**，2024-11 至 2025-01 | **Microsoft DAX Copilot vs Nabla vs 常规照护** | DAX 在 **24,696 次就诊中用了 33.5%**；Nabla 在 23,653 次中用 29.5%。主结局（log time-in-note）：**Nabla −9.5%（95% CI −17.2% 至 −1.8%；P=0.02）**；**DAX −1.7%（95% CI −9.4% 至 +5.9%；P=0.66，不显著）**。两者都改善 Mini-Z（DAX +2.83）并降低医师任务负荷。**→ 目前唯一 DAX 的 RCT，且主结局对 DAX 不利。** |
| **Webb 等，*Appl Clin Inform* 2026;17(1):118-126，PMID 41734793** | **UT Southwestern 急诊科；单中心前瞻性交叉，6 周，20 例入组/18 例完成** | **DAX vs Abridge**（唯一正面对撞） | DAX 工作负担降幅更大（median 1.5 vs 2; p=0.025）、PDQI-9 偏 DAX（39 vs 36.5; p=0.011）、推荐意愿 9 vs 7.5（p=0.015）；SUS 相当（73.5 vs 73.5; p=0.94）。**但校正模型显示差异主要来自 order effect 而非工具本身。** |
| **Haberle 等，*JAMIA* 2024;31(4):975-979，PMID 38345343** | **Intermountain Health；同行匹配对照队列**，99 名医师/12 专科 + 76 名匹配对照 | **Nuance DAX**（标题具名） | 中位使用率 **47%**；参与者在敬业度上呈正向趋势而对照组恶化；**"statistically significant worsening of after-hours EHR"**；**"no quantifiable effect on patient safety"**；**"no significant benefits to patient experience, documentation, or measures of provider productivity."** |
| **Bundy 等，*J Gen Intern Med* 2024;39(15):2995-3000，PMID 38937369** | **Atrium Health Wake Forest Baptist；半结构化访谈**，116 名初级保健医师中的 12 名 | **"DAX Copilot (DAXC)"** | 减少文书时间、缓解"记不住关键临床细节"的焦虑、问诊更有人情味。**但**："the tool would occasionally **imagine or misgender patients, offer unsolicited and inappropriate diagnoses, and mistake critical details in transcription**." |
| **Svetly 等，*Appl Clin Inform* 2026;17(4):747-753，PMID 42618038** | **AdventHealth（多州）；回顾性前后对照**，210 名医师、**Epic Signal** 数据、前后各 8 个月 | **DAX Copilot** | 活跃 note 时间 **5.54 → 4.09 分钟/次（−26.2%，p<0.001）**；**note 长度 +28.8%**；**打字 −51.7%** |
| **Ma 等，*JAMIA* 2025;32(2):381-385，PMID 39688515** / **Shah 等，*JAMIA* 2025;32(2):375-380，PMID 39657021** | **Stanford Health Care；前瞻性 QI**，45 / 48 名医师、3 个月 | 摘要未具名；Shah 2025 结论提到 "**DAX Copilot**" | Ma：使用率 **9,629/17,428（55.25%）**、显著的使用者间异质性；单份 note 中位 **−0.57 min**、每日文书 **−6.89 min**、下班后 **−5.17 min**、总 EHR **−19.95 min/天**。Shah（配对 n=38）：**任务负荷 −24.42（p<.001）**、**倦怠 −1.94（p<.001）**、**可用性 +10.9（p<.001）** |
| **Wendt 等，*Future Healthc J* 2025;12(3):100450，PMID 40896303** | **Providence；阶梯楔形随机对照** | **Nuance DAX**（标题具名） | 文书负担、挫败感与倦怠显著下降；**每周少 2.5 小时**的下班后文书。COI：Providence St. Joseph Health 从 Nuance（Microsoft 旗下）获得**有限数量的免费 license** |
| **Liu 等，*JAMA Netw Open* 2024;7(9):e2432460，PMID 39240568** | **Atrium Health；非随机临床试验** | 摘要未具名（COI 披露） | COI 原文披露 "Dr Cleveland reported serving on the **Executive Client Council (noncompensated advisory group) for Nuance/Microsoft** …（which included **DAX Copilot in February 2023**）" |
| **Rotenstein 等，*JAMA* 2026;335(16):1408-1417，PMID 41920565** | UCSF 牵头多中心，**8,581 名医师、1,809 名采用者** | **摘要未具名任何厂商** | 双重差分：**−13.4 min EHR 时间（95% CI 9.1–17.7）**、**−16.0 min 文书时间（95% CI 13.7–18.3）**、**+0.49 次/周就诊量（95% CI 0.17–0.81）**；下班后 EHR 时间无显著变化。COI 含 Yale New Haven 与 **Abridge** 的顾问关系、Mass General Brigham 对 **Abridge** 的投资。**→ 混合厂商人群，不得归给 DAX。** |

> 以上 PMID 记录均经 NCBI E-utilities 读取同一记录，统一标注 **`[子代理 API 读取，未复核]`**；PubMed 页面本身对直接抓取返回 203 反爬响应，因此页面 URL 标记为 `[已确认存在，未逐页打开]`。
>
> **厂商具名但非 DAX/Abridge 的研究（列出以防误归因）**：Palm 等，*Front Artif Intell* 2025;8:1691499，PMID 41199808 —— 这是 **Suki AI** 的 PDQI-9 环境 note 质量验证，幻觉率 **31% 的环境 note vs 20% 的 gold note（p=0.01）**；**相邻工具的数字不得归给 Abridge 或 DAX**。另有 Ghanem 等（PMID 41366572，外科住院医）、Talman 等（PMID 42114818，儿科血液肿瘤）、Shin 等（PMID 40675605，儿科亚专科快速随机）为 DAX 家族的标题级发现。

**(f) 监管状态（必须写准）**（`whitepapers/transparency`，并在 `whitepapers/transparency-information-assist` 逐字重复【子代理已打开，主代理未复核】）
> "Notwithstanding the Universal Licensing Terms for Online Services Medical Device Disclaimer, **Dragon Copilot (physician) is UK Conformity Assessed (UKCA) marked as a Class I medical device in Great Britain. In all other jurisdictions, Dragon Copilot is not designed, intended, or made available as a medical device.**"

2025-10 护理与伙伴扩展新闻稿亦重复该免责声明（【一手】）。openFDA 查询：`applicant:"Nuance"` 命中 6 条，**全部来自无关公司 "Nuance Medical, LLC"**（冷冻治疗罐）；`device_name:"Dragon"` 命中 8 条（针灸针、X 光设备、注射器等），**均无关**。**未见 DAX / Dragon 的 510(k)** → **`[子代理 API 查询，未复核]`**。
`[推断]` **DAX Copilot / Dragon Copilot 无 FDA 510(k) 清除**：Microsoft 只在一个市场（英国）做了最低风险等级（Class I）的器械声明，同时在美国明确声明**不是**器械——即**刻意避开 FDA 路径**。另注："Dragon Copilot is an 'AI clinical assistant'" 是**定位表述，不是监管表述**。

**⑤ 关键设计决策（对守衡可迁移的一条）**

**把"可信语料"做成配置项而非模型判断，并在提示词构造期强制上下文边界。**

`[推断]` 对守衡的含义：

| Dragon Copilot 的做法 | 守衡的对应物 |
|---|---|
| **只检索 approved / vetted / tested 的源**，且客户须把域名加入 allow list | 守衡的规则来源应有**白名单制**：只有被登记并测试过的规则源可参与判定，未登记的源不进上下文 |
| **非常保守的检索范围**（只搜网页、PDF 不在范围内、只返回 top three） | 宁可缩小召回面也要保证可解释性——命中率不足可以用"显式报告盲区"补偿，不能靠扩召回赌正确率 |
| **Context Grounding**："External sources and data from other sessions are not allowed." | 单次判定任务的上下文应**硬性限定在本次案例范围内**，不得携带其他店铺/其他达人的历史 |
| **按患者级隐私标记在检索期裁剪**（restricted record → 不检索） | 敏感/受限对象在**取数阶段**就被排除，而不是检索出来再过滤 |
| **两级评测**（平台服务 2–5k 查询 → 用户应用 50–100 查询），承认平台级与产品级表现不同 | 守衡也应区分"规则引擎单测"与"整条审核链路端到端"两级评测，不要把前者当后者 |
| **红队在 credible / customer / harmful adversarial 三类源上分别做注入测试** | 注入测试不能只在干净语料上做；必须包含"客户自建语料被污染"的场景 |
| **把"客户源可能不 grounding"的警告写进官方文档** | 已知的语料风险应写在系统可读到的地方（规则库/文档），而不是只写在汇报里 |
| **删除走 DPA + Purview 生命周期**，撤回同意只清可关联数据 | 守衡的案例留痕需明确"哪些会被删除、哪些（已聚合/已匿名）不随撤回而删除" |

**⑥ 未找到 / 存疑**

- **Information Assist 的刷新频率、增量与去重机制** —— **未找到公开资料**。
- **note 生成路径的量化 hallucination / omission 率** —— **未找到公开资料**：Microsoft 点名了 Groundedness / Completeness / Relevance / Factuality 四项指标，但**只对 Information Assist 的 RAG 路径给出（定性）结果，note 生成路径无任何数字**。
- **索引期 ACL 快照机制** —— **未找到公开资料**（图表级 ACL 契约上归客户）。
- **原 Nuance DAX 的架构文档** —— **未找到**：nuance.com/healthcare 已 301 至 Microsoft，任何 2022 年之前的 Nuance 工程描述都不再由一手站提供。
- **本节的证据分层**：第 3–10、13–15 层、`whitepapers/transparency`、`whitepapers/security`、`specialty-models/*`、`sdk/glossary`、`resources/context`、`ontology/coding-systems`、`extensions/development-concepts` 与两条 news.microsoft.com 新闻稿，均由并行子调研线打开 → 保留 **`[子代理已打开，主代理未复核]`** 标注；`whitepapers/privacy`、`whitepapers/data-collection`、`whitepapers/transparency-information-assist`、功能页与第三方研究结论已在主报告侧复核。

---

### 3.6 五家横向结论：权限时点光谱 与 评测指标的行业收敛

#### 3.6.1 权限时点是一条光谱，而不是一个开关

把八个案例（本节五家 + 企业知识助手类六家中的两家锚点）按"权限在哪一刻生效"排列，得到一条从最粗到最细的光谱：

| 位置 | 主体 | 权限生效时点（官方原话所属档位） | 一致性缺口（官方承认的） | 证据 |
|---|---|---|---|---|
| **最粗** | **Microsoft 365 Copilot** | **纯索引期快照**：item 级 ACL 随索引项存储，检索期"honor the user identity-based access boundary" | **"Permissions updates occur during a full crawl, not an incremental crawl"**，且 "**might take up to 24 hours to reflect**" | 【一手】 |
| **居中** | **Glean** | **索引期快照 + 可选择三档**：indexed 模式用 **"the permission snapshot that was mirrored during crawling and incremental updates"**；另有 **Live / Hybrid** 两档；图谱侧"designed with fine-grain access controls" | 官方**未明确说明**检索期是否再对上游做一次校验 → `[待确认]` | 【一手】 |
| **居中偏细** | **Decagon** | **连接器侧凭据**：JIT 短时 JWT "scoped for minimal privilege and **discarded after each session**"；平台 RBAC | **检索期 ACL 未找到公开资料** | 【一手】 |
| **细** | **Sierra** | **运行期工具可见性裁剪**：**"preventing account-modification tools from even being available to the agent until the customer has been authenticated"**；叠加 runtime 四层（Content / Rules / Supervisors / Deterministic guards） | 未见一致性缺口描述；**索引期文档级 ACL 未找到公开资料** | 【一手】 |
| **细** | **Harvey** | **查询期继承用户权限 + 三层强制 + fail closed**：**"The agent has the same permissions as the user"**；伦理墙在 **retrieval / context / output 三层**强制；matter 是 **"not as a metadata tag, but as a hard security boundary"**；无法确认归属则 **"must skip that document and flag the uncertainty"** | **索引期是否把 ACL 落到 chunk 元数据未找到公开资料** | 【一手】 |
| **最细** | **Dragon Copilot** | **按对象级隐私标记的检索期裁剪**：**"Diagnoses can be retrieved only for checked-in patients whose records are not restricted or controlled under enhanced privacy access controls"**；叠加 **"External sources and data from other sessions are not allowed."** | **图表级 ACL 契约上归客户**（"Customers … are also responsible for configuring and managing access controls within their environment"）；索引期机制未找到公开资料 | 【一手】 |

**三条横切结论**：

1. **权限时点在垂直五家中普遍比企业知识助手更靠"查询/运行期"，但实现方式各不相同**：Sierra 裁的是**工具可用性**，Harvey 裁的是**文件可达性**，Dragon Copilot 裁的是**记录的可检索性**。三者共享同一个特征——**裁剪发生在"下发给模型的内容"这一层，而不是发生在"索引里存了什么"这一层**。`[推断]` 这与它们的语料形态有关：垂直语料是**事务性、对象级、随状态变化**的（工单状态、matter、就诊记录），索引期快照天然无法承载。

2. **五家的「索引期文档级 ACL」全部未找到公开资料——这是垂直厂商公开度的共同缺口。** 需要注意这是一个**公开度**结论，不是**能力**结论：没有任何一家的一手材料能证明或证伪它在索引期做了文档级权限打标。Harvey 的"retrieval layer / context layer / output layer 三层强制"措辞**暗示不止查询期一处**，但机制未公开。

3. `[推断]` **权限粒度与语料异构度呈负相关。** 语料越异构（多部门、多系统、多租户），厂商越倾向把权限一致性**外化为连接器契约或配置项**（Glean 的三档、Notion 的 permissions mapping、Microsoft 的 24h 缺口），并允许存在时间窗；语料越同构且对象级（matter、患者记录），越倾向在**交付前做硬裁剪并 fail closed**（Harvey、Dragon Copilot）。这条推断的解释力在于：异构语料的权限变更频率高到无法用同步机制跟上，只能承认缺口并把它变成可配置的一致性等级。

**对守衡的映射** `[推断]`：

| 外部光谱位置 | 守衡的对应物 | 现状判断 |
|---|---|---|
| Microsoft 的"24 小时一致性缺口" | 飞书权威源与本地判定制品之间的同步延迟 | 守衡的制品是本地 JSON，权限语义主要落在**飞书表的可读范围**；`[推断]` 需要先把"谁能读到哪张表"显式化，否则无法定义缺口 |
| Glean 的三档取数模式 | 规则取数应分档：本地冻结制品 / 飞书实时读取 / 混合 | 当前是"本地冻结"一档，缺档位命名与切换语义 |
| Sierra 的"工具根本不出现" | 越权类能力在会话中不应存在，而非被提示词禁止 | 应把"读不到某品线规则"实现为**该品线规则不进入本次上下文** |
| Harvey 的 fail closed | 无规则命中时应标记盲区而非默认合规 | 对应守衡 G2（假阴性在源表数据模型里没有位置） |
| Harvey 的三问清单 | "本次判定能读哪些数据？范围是单品线还是全部？强制发生在应用层还是数据层？" | 可直接作为守衡权限设计的自检表 |
| Dragon Copilot 的 allow list | 规则来源白名单 | 对应的"**规则库 + 案例库 + 误判申诉**三件套"中，规则库的**权威源认定**目前是"声明"而非"证明" |

#### 3.6.2 评测指标的行业收敛 —— 企业 RAG 评测的最小公约数

**两组独立收敛，构成本节最可直接引用的一条行业结论。**

**收敛一：三家独立给出同一组三指标。**

| 厂商 | 检索侧指标 | 生成侧指标 | 事实性指标 |
|---|---|---|---|
| **Glean**（企业知识助手类） | **Context relevance rate**、**Context recall rate**（后者的定义是 **canonical document**——"the most authoritative and comprehensive source of information"——**被召回的比例**） | **Answer relevance**（二分类）、**Answer completeness**（complete / incomplete / no-answer 三档） | **Groundedness**：**先拆 claims，再逐条标 inferable / generic / ungrounded**，得分 = 有据 claims / 总 claims |
| **Dragon Copilot**（垂直·医疗） | **Evidence relevance**（"assessing whether the **selected evidence sources** are relevant to the user query"） | **Answer relevance**（"the ability to provide a response that is relevant to the user query"） | **Groundedness and fabrications**（"grounding responses on the provided evidence sources, while **refraining from using its own 'internal knowledge'**"） |
| **Sierra**（垂直·客服） | **recall / precision / nDCG**（原文称 "industry-standard retrieval metrics"），配合 **daily golden articles** | —（以 resolution rate 为业务端指标） | —（以 τ-Knowledge 的"simulated backend database 是否被正确修改"作为端到端判定） |

→ **Glean 的 Context relevance / Answer relevance / Groundedness 与 Dragon Copilot 的 Groundedness and fabrications / Answer relevance / Evidence relevance 收敛到同一组三指标**。这两家在产品形态、语料类型、客户行业上毫无交集，却独立命名出几乎同构的三件套：【一手】

> **企业 RAG 评测的最小公约数 =「检索到的东西对不对（context / evidence relevance）」+「答的东西切不切题（answer relevance）」+「答的东西有没有据（groundedness / fabrications）」。**

**收敛二：人类一致性被当成自动评测的天花板。** Glean 的硬数字：**人类标注者彼此一致率仅 79%**（并被**当作自动评测的上限**），**AI Evaluator 与人类一致率 74%**。→ `[推断]` 这条数字解释了两件事：① 任何声称 RAG 评测准确率超过 ~80% 的说法，都已经超过了人类彼此的一致上限，需要额外解释；② 引入 LLM-as-judge 时的合理目标不是"接近 100%"，而是"落在人类一致率以下的可解释区间"。

**收敛三：各家的"黄金集"构造法正在从"造题"转向"从真实业务痕迹派生"。** 这是五家中最值得逐条抄的一节：【一手】

| 厂商 | 黄金集的派生源 | 原文 |
|---|---|---|
| **Sierra** | **前一天的对话**（采样数千条匿名 search call） | "articles that **most directly solve the customer's problem** at that point in the conversation" |
| **Harvey** | **计费工时（time entry）** | "Because **all work is billed**, building a comprehensive set of time entries closely reflects the set of legal tasks that make up real-world practice." |
| **Abridge** | **去标识的真实就诊 + 医生对生成文本的编辑** | "de-identified Abridge encounters"；被动信号 = "the **edits required to finalize the note**" |
| **Dragon Copilot** | **匿名的真实临床文档与转录**（context-based tests） | "**Context-based tests using anonymized clinical documents** (notes or flowsheets) and transcripts." |
| **Decagon** | **模拟客户部署 + 合成流量**（自改进场景没有真实痕迹可派生） | "runs on **simulated customer deployments**, complete with AOPs, tools, guardrails, and **synthetic traffic**" |

`[推断]` 前三家共有的模式是：**评测集从"业务里已经被完整记录的动作"派生，而不是靠人凭空设计题目**——对话检索时刻、计费工时、医生编辑动作都是天然带上下文的标注。守衡的等价物是**每一次人工改判**：它天然携带"哪个规则错了、错在哪、正确结论是什么"。

**收敛四：拒答/失败被单列为一等信号（个别但极有价值）。**
- Glean 把 **"No Answers" 与低 groundedness** 用作流失预测因子（预测准确率 **+18.8%**）。
- Dragon Copilot 的 Answer completeness 直接设 **no-answer** 档；Sierra 的 τ-Knowledge 以**状态变更是否正确**为准，未完成即失败。
- `[推断]` 三家都把"没答出来"当成**要单独计数的结果**，而不是当成"准确率里的一条错例"。这与守衡把假阴性当作"没有位置存放"形成直接对照。

#### 3.6.3 五家在「规则库 + 案例库 + 误判申诉」三件套上的位置

| 三件套 | Sierra | Decagon | Harvey | Abridge | Dragon Copilot |
|---|---|---|---|---|---|
| **规则库** | **Rule/Policy 是独立 context block**（8 类中单独一类，自然语言表达 + Conditions 决定何时可用） | **AOP**：自然语言指令**编译成受验证工作流**；工程侧用 Git 版本管理 | **Playbook 五元结构**（Standard / Acceptable deviations / Unacceptable deviations / Guidance / Optional）+ **escalation paths 可编码** | 无独立规则库层；**临床规范（clinical content specifications）+ 专科 recipes** 承担规则职能 | **Guardlist / Dynamic Blocklist / Allow list / Intent Classification** 构成规则栈；临床内容规范作为设计前置 |
| **案例库** | Knowledge + Expert Answers（从人工实录反哺文章）；无公开的"历史裁决库" | Suggestions 从**顶尖人工客服的真实解决过程**起草文章；**无公开历史裁决库** | **两层都有且明确**：golden examples（few-shot 层，25,000+ custom workflows）+ **Precedent bank**（"我们以前到底同意过什么"、按 clause 粒度对比、**最近 5 份 NDA 都接受某条款时主动建议新 standard**） | 无公开案例库层；**医生编辑动作**事实上充当隐式案例信号 | **无公开案例库层**（"未找到"） |
| **误判申诉** | Experience Manager 每日标注 → 可转为 **regression test**（对着 mock APIs 重跑） | Duet 的 **Human QA insights** + Autopilot 更新必须人审；**无面向终端用户的申诉流程** | **无面向用户的申诉/翻案入口（未找到）**；误判的工程处理明确（多 agent 分支 merge + collision escalate 给 lead agent + 承认 over-redline / miss flags 等失败形态）+ Review Queue 人工复核 | **无申诉机制**；但有"检测 + 自动纠正"两级护栏，且临床医生审阅强制 | **未找到申诉机制**；有 Chat Safeguards 免责声明 + 答案反馈图标 + 医生强制签核 |
| **该列的行业结论** | — | — | — | — | **垂直五家中，只有 Harvey 在"案例库"这一层有明确的、可引用的产品化设计；五家在"误判申诉闭环"上全部缺位或极弱。** 唯一的替代品是三家分别给出的"回归测试 + 人审队列"（Sierra / Decagon / Harvey），本质上是**厂商侧的质量流程**，不是**用户侧的申诉归途**。**⚠️ 但"申诉翻案率无人公开"这一判断只在厂商侧成立**——平台侧早已是成熟惯例（Meta 按季度公开四个可算出翻案率的并列指标；TikTok 公开 restoration 计数与 24 小时处置率）。**完整证据与研究者复算见 §5 · C4。** |

`[推断]` **对守衡而言，这一列是外部案例给不出答案的一列，也正是守衡可以做出差异的一列。** 外部五家都是厂商侧单向治理（人审、回归、红队），没有任何一家公开了"业务方认为判错了 → 提交申诉 → 谁在什么时限内复核 → 翻案后如何回流到规则库与评测集"的完整通路。

**⚠️ 一处必须修正的初稿判断（本报告第二次自我证伪）**：初稿在这里把它写成"**一个外部也没人做完的公开空白**"，**这是错的**。正确表述是分层的：

| 分层 | 申诉闭环的公开状况 | 依据 |
|---|---|---|
| **厂商侧**（企业软件 / 法律 / 医疗 AI） | **确实缺位**——只公开准确率与节省，不公开申诉翻案率 | 本节五家；`_distill-legal.md` §4；`_distill-medical.md` §7 |
| **平台侧**（内容审核） | **早已是成熟惯例**——Meta 四指标并列并按季度发布，翻案率可算且稳定；TikTok 公开 restoration 计数与处置时效 | **§5 · C4**（含研究者独立复算） |

`[推断]` **成因不是能力差异，而是问责对象差异**：平台要对**内容决定**承担法定透明度义务，所以必须公开；企业软件只需对**采购方**负责，所以可以只公开对自己有利的指标。

**那么真正的空白是什么？** 是 **"裁决回流到规则"这一环**：Meta 公开"撤回了多少条"，但不公开"因此改了哪条规则"；Amazon 只说 AHR 分数随申诉回升，不说规则会因申诉而改。**"翻案 → 规则修订 → 生效"这条因果链，平台侧同样是空白。** 这才是本节结论中真正站得住的部分——**它比"全行业空白"更窄，但也更真，并且恰好就是 G1 / G7 要补的那一段。**

#### 3.6.4 五条可直接落到守衡的机制（按可迁移性排序）`[推断]`

| 优先级 | 可迁移机制 | 来源 | 守衡对应物 | 为什么先做这条 |
|---|---|---|---|---|
| 1 | **权限 = 工具/数据源不出现**，而非"被要求不要用" | Sierra（"can't be talked out of doing their job"） | 越权类检查改为上下文装载期裁剪 | 可靠性与"提示词禁令"不在一个等级；改动面小、收益确定 |
| 2 | **fail closed：无法确认归属就跳过并标记不确定** | Harvey | 无规则命中 → 显式标记盲区，而非默认合规 | 直接对应 G2；这是"判定系统"与"检索系统"的分野 |
| 3 | **评测任务从人工改判痕迹派生** | Harvey（time entry）/ Sierra（前一日对话）/ Abridge（医生编辑） | 每一次人工改判 → 一条评测样本候选 | 守衡已有 291 条冻结语料 + 人工判定，缺的是**入集机制**而不是数据 |
| 4 | **answer score / source score 分开且相互独立**；引用必须结构可验证 | Harvey | 判定准确率与引用可追溯率分开统计；规则引用用结构化 ID 校验 | 直接对应 G5"上游引用是声明不是证明" |
| 5 | **LLM judge 必须先与人工判定对齐才算通过验证** | Abridge；Glean 的 79%/74% 一致率数字 | 引入任何模型自评前，先测它与人工改判的一致率 | 提供了一条可量化的准入门槛，防止"评了但没真评" |

---

---
## 4. 案例族 C：「知识库 → Agent」的公开方法论

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
- GraphRAG 的**索引构建成本是 LLM 全量跑语料**，且论文只在"1M token 

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

---

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

---

## 5. 案例族 D：垂直合规 / 内容审核 Agent —— 「规则库 + 案例库 + 误判申诉」三件套

### C1. OpenAI Moderation：把「阈值」显式交给部署方，并要求用混淆矩阵定阈

**出处**：OpenAI 官方 Cookbook `examples/How_to_use_moderation.ipynb`（GitHub 原始文件，【一手】<https://github.com/openai/openai-cookbook/blob/main/examples/How_to_use_moderation.ipynb>）；配套 `examples/How_to_use_guardrails.ipynb`【一手】

**它的三层结构（官方章节标题，即"知识/规则"的三种组织方式）**：
1. **Input moderation**：在 LLM 之前/并行拦截有害输入。
2. **Output moderation**：在返回用户前校验模型输出。
3. **Custom moderation**：**不使用 Moderation API**，而是用一次额外的模型调用，按**调用方自定义的 `parameters`** 打分。官方给出的返回结构是严格的 JSON：
   ```
   { "flagged": bool, "reason": str, "parameters": { "political content": bool, "misinformation": bool } }
   ```
   ——即：**判定结论 + 理由 + 所用参数（规则）三元组**。`[推断]` 这正是"规则库驱动判定"的最小可审计形态。

**分类法（官方列出的 image moderation categories，【一手】）**：
`sexual` / `sexual-minors` / `harassment` / `harassment-threatening` / `hate` / `hate-threatening` / `illicit` / `illicit-violent` / `self-harm` / `self-harm-intent` / `self-harm-instructions` / `violence` / `violence-graphic`
注意其结构：**顶层类别 + 斜杠子类别**，且子类别是"更严重/更具体"的那一档。`[推断]` 这种"父类用于统计、子类用于处置"的两级分类法，是合规审核知识库的通用形状。

**阈值哲学（官方原文，本报告最重要的一段引用之一）**：
> "OpenAI has selected thresholds for moderation categories that **balance precision and recall for our use cases**, but **your use case or tolerance for moderation may be different**. Setting this threshold is a common area for optimization - we recommend **building an evaluation set and grading the results using a confusion matrix** to set the right tolerance for your moderation."

并明确写出代价方向：
> "More **false positives** leads to a **fractured user experience**, where customers get annoyed and the assistant seems less helpful.
> More **false negatives** can cause **lasting harm to your business**."

以及**同一模型在不同业务下阈值应不同**的例子：创意写作平台对某些敏感话题应把阈值调高以保留创作自由。

**延迟与成本的取舍（官方原文）**："send your moderations **asynchronously along with your main LLM call**. If your moderation gets triggered you send back a **placeholder response**, otherwise send back the LLM response."并提醒异步可能"lead to unnecessary costs"（因为内容若在进入 LLM 前就被拦，本可省掉生成成本）。

**Guardrails 手册补充的三条硬约束（【一手】`How_to_use_guardrails.ipynb`）**：
- Guardrail 的三方权衡是 **accuracy / latency / cost**；提升准确率的手段包括 fine-tune、few-shot，以及一句关键的表述：**"RAG can also be effective if you have a corpus of information that can help determine whether a piece of content is allowed or not."**——即：**把"允许/不允许"的判定知识本身当成检索语料**。
- **Guardrail 的已知失效模式**（官方自陈）：① "When using LLMs as a guardrail, be aware that they have **the same vulnerabilities as your base LLM call itself**"，例如 prompt injection 可能**同时**绕过 guardrail 与主调用；② "As conversations get longer, LLMs are more susceptible to **jailbreaking** as your instructions become **diluted** by the extra text"；③ 过度收紧会造成 **over-refusals**（"your guardrails reject innocuous user requests because there are similarities with prompt injection"）。
- **官方给的缓解手段（三条，直接可用）**：① "**combine guardrails with rules-based or more traditional machine learning models** for detection"；② "have guardrails that **only ever consider the latest message**, to alleviate the risks of the model being confused by a long conversation"；③ "**gradual roll-out with active monitoring of conversations**"，把新发现的行为模式"add more guardrails to cover these new types of behaviour, or **include them as training examples to your existing guardrails**"。
- **输出侧阈值举例**：官方示例用 G-Eval 式评分（domain + criteria + steps → 1–5 分），并"block anything scoring a **3 or higher**"；同时给出**按风险差异定阈**的示范——防 jailbreak 应用极低阈值，而宠物推荐场景愿接受少量漏判，因为"the worst that could happen is someone ends up with a Bichon Frise ... which though harmless will probably not cause lasting damage to our business"。

**对守衡的映射** `[推断]`：
| OpenAI 的做法 | 守衡的对应物 |
|---|---|
| Input / Output / Custom 三层 | 语境守卫（输入侧）+ 判定引擎（主体）+ 结论自检（输出侧） |
| `parameters` 随判定一起落库 | 判定结论必须记录"本次用了哪些规则/白名单版本" |
| 混淆矩阵定阈 | 守衡的评测必须分开统计**误判率（误报）**与**漏判率（漏放）**，而不是一个总分 |
| 官方缓解手段②"只看最新消息" | 语境守卫应考虑"只对当前待审内容 + 最小必要上下文"判定，避免长上下文稀释规则 |
| 官方缓解手段①"规则/传统模型混合" | 关键词/正则/白名单这类确定性检查**不应**交给模型 |

---

### C2. Google Perspective API：阈值所有权归部署方，且阈值会随模型漂移

**出处与证据强度说明**：`developers.perspectiveapi.com` 与 `support.perspectiveapi.com` 均为 JS 渲染（`web_fetch` 返回 `Loading` 骨架）。以下表述来自**搜索引擎返回的官方页面原句**与官方 GitHub 仓库，逐条标注证据强度。

- 【一手】`conversationai/perspectiveapi` 官方仓库 README（<https://github.com/conversationai/perspectiveapi>，经 `raw.githubusercontent.com` 读取）："Perspective is a free API that helps you host better conversations online. The API uses machine learning models to **score the perceived impact a comment might have on a conversation**. You can use this score to **give feedback to commenters, help moderators more easily review comments, allow readers to more easily find interesting or productive comments**"；由 **Jigsaw 与 Google Counter Abuse Technology 团队**在 Conversation-AI 研究计划下创建。
- 【官方·仅搜索摘要】官方 FAQ 页（`support.perspectiveapi.com/s/about-the-api-faqs`）原文：**"if you select a [threshold] ... need to update that threshold when the models update. However you may see that a specific score changed due to an update. Note that we are **not able to notify users each time an update is released**."**
  → **这是本报告最值得守衡记住的一条外部证据**：*阈值不是常量，模型更新会让同一个阈值的行为改变，而且厂商不会通知你*。因此阈值必须自带"校准日期 + 对应模型版本"。
- 【官方·仅搜索摘要】官方 Key Concepts 页（`.../about-the-api-key-concepts`）原文：主属性 **TOXICITY** 定义为 **"a rude, disrespectful, or unreasonable comment that is likely to make you leave a discussion"**；其他属性包括 **PROFANITY、THREAT、SEXUALLY_EXPLICIT** 等。
- 【官方·仅搜索摘要】官方 Limits 页（`.../about-the-api-limits-and-errors`）原文：默认配额为 **"an average of 1 query per second (QPS) for all Perspective projects"**，仅供测试与开发环境。
- 【搜索摘要中可见的官方描述】分数语义：`TOXICITY` 返回 **0.0–1.0** 的单个数值，且 `type` 为 **PROBABILITY**；即"模型估计约 X% 的人类评审者会认为该内容有毒"——**它衡量的是"感知影响"，不是"危害程度"**。
- 【二手，第三方分析】常见实践是把 **0.6–0.8** 区间用作"送人工复核"的阈值；但**该区间不是官方推荐值**，本报告不把它当事实使用。
- 【推断】第三方资料一致指出 Perspective **按单条评论孤立打分，不参考说话者、受众与对话上下文**，因此反讽/语境类内容误报率更高。这解释了为什么"语境守卫"这类组件在垂直审核里不可或缺。

**三件套的组织方式（从上述证据可确认的部分）**【推断 + 部分事实】：
- **规则库**：以"属性（attribute）"为规则单元，而非以"违规词"为单元；每条属性有独立定义句（如 TOXICITY 的定义）。
- **阈值库**：阈值**不属于 API，属于部署方**——API 只给概率，判定由调用方决定。这是"规则（属性定义）+ 策略（阈值）分离"的教科书式做法。
- **申诉/反馈**：官方 README 明确 score 可用于 "give feedback to commenters" 与 "help moderators review"，即**分数是给人用的输入，而非终局裁决**。

---

---

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

### C4. 平台侧执法与申诉：全篇唯一「已经做完」的一侧（Meta · TikTok · Amazon）

> **本节性质与前三节不同**：C1/C2 是模型厂商的审核 API，C3 是企业软件厂商的垂直 Agent；**本节是平台自身对内容决定的执法与申诉**。它是本报告全篇**唯一一组"申诉闭环已成惯例"的一手证据**，因此对守衡的价值不在"抄架构"，而在**抄台账字段、抄处置分级、抄可问责的披露形态**。
>
> **证据来源分两层**：运营侧措辞来自平台官方帮助文档【一手】；**量化指标来自研究者本人在项目内既存官方导出数据上的独立复算**【一手·已复验】——`research/governance/_evidence/R4/meta-cser-2026Q2.csv`（5,409 行，sha256 `540b2905…`，Meta 官方 CSER 完整导出）与 `research/governance/_evidence/R4/tiktok-cger-2026Q1/2026Q1_raw_data_cger_English.csv`（96,681 行，TikTok 官方 CGER 导出）。**这两份都不是二手转述。**

#### C4.1 Meta：四指标并列 + 精度区间 + 假阳性绝对数（本报告见到的最可问责的披露形态）

Meta 的 CSER 按季度公开**四个并列的绝对数指标**，它们合起来使"申诉翻案率"成为**可直接推导的一等指标**：

| 指标 | 含义 |
|---|---|
| `Content Actioned` | 已处置量（分母） |
| `Content Appealed` | 被申诉量 |
| `Content Restored with appeal` | **申诉后翻案量** |
| `Content Restored without appeal` | **平台主动自撤量** |

`[一手·已复验]` **研究者独立复算（2026Q2，全政策域汇总）**：

| 平台 | Content Actioned | Content Appealed | 申诉率 | Restored **with** appeal | **申诉翻案率** | Restored **without** appeal |
|---|---|---|---|---|---|---|
| **Facebook** | 975,549,000 | 3,742,100 | 0.38% | 979,400 | **26.17%** | 5,595,600（0.574%） |
| **Instagram** | 85,369,600 | 3,380,600 | 3.96% | 764,100 | **22.60%** | 434,300（0.509%） |

同一 CSV 的 `Cross-Policy Data` 行还给出**平台自报的精度区间与假阳性绝对数**：

| 平台 | Enforcement Precision | False Positive（绝对数，区间） |
|---|---|---|
| Facebook | **90.80% – 91.85%** | 30,200,000 – 30,800,000 |
| Instagram | **90.78% – 92.24%** | 9,100,000 – 9,500,000 |

**⚠️ 三条由复算发现的修正——底稿的三个数字里有两个不能用：**

| # | 底稿说法 | 复算结论 | 依据 |
|---|---|---|---|
| 1 | "Facebook 申诉率 **0.38%**，与 Instagram 的 3.96% 相差约 10 倍" | ❌ **分母被污染**。Facebook 的 `Content Actioned` 含 **Fake Accounts 822,400,000 条（占 84.3%）**，而 **Fake Accounts 在全部 35 个季度里从不报告申诉数据**（只有 `Content Actioned` 与 `Proactive rate`）。**剔除后申诉率为 2.44%**，与 Instagram 同量级（IG 逐季 2.96–3.96%，其 Actioned 与 Appealed 的政策域集合完全一致，无污染） | 逐 `policy_area` 核查：FB 2026Q2 有 Actioned 的政策域 15 个、有 Appealed 的 14 个，差集恰为 `Fake Accounts` |
| 2 | "平台主动纠错量是申诉翻案量的 **5.7 倍**" | ❌ **单季度假象**。该比值在 2025Q2–2026Q2 为 **3.84x / 4.35x / 0.81x / 0.57x / 5.71x**，波动近 10 倍，且几乎完全由一个政策域驱动：**Spam 的自撤量在 5,400,000 → 350,000 → 5,307,400 之间摆动（15 倍）** | 逐政策域拆解 `Content Restored without appeal` |
| 3 | "申诉翻案率 22–26%" | ✅ **稳健，可用**。FB 逐季 **28.64% / 29.39% / 25.42% / 23.21% / 26.17%**，5 个季度全部落在 23–29% | 同上 |

`[推断]` **修正后仍然成立的结论**（而且比底稿更干净）：**申诉翻案率是公开的、稳定的、可算的**（FB 23–29%、IG 22.60%）。**"申诉率"必须与"翻案率"成对读**——翻案率 26% 作用在个位数百分比的申诉率上，意味着**绝大多数被处置内容从未被申诉**。而**精度必须以「区间 + 假阳性绝对数」发布**：单点精度无法被反向引用，因此不构成可问责的披露。

`[推断]` **对守衡的直接映射（比数字本身更有用）**：**申诉台账字段直接照这四个指标设**，并**必须把"平台自撤"与"申诉翻案"分开计**——前者是"我们主动纠错"，后者是"用户推着我们纠错"，两者的改进含义完全不同。

#### C4.2 TikTok：唯一同时公开「时效 + 状态机 + 申诉终局性」的一家

**(a) `[一手]` 运营侧规则（逐字）**——审核 SLA、状态机与终局性：

> "While some TikTok ads might take longer than usual for the review process to complete, **most are reviewed within 24 hours**."（`advertising-on-tiktok-first-things-to-note`，Last updated Feb 2025）
> "If your Account Health status says **Attention Needed**… you'll receive **warning notifications and suggestions to improve**. If your Account Health status is **Poor**, your account **will be suspended**."
> "**Note: Some issues can lead to an immediate suspension if the violation is severe.**"
> "**Temporary suspension** — If this is your first violation, you'll have **30 days** to address the issues… or **submit an appeal**."
> "**Permanent suspension** — … **You won't be able to appeal this decision.**"（`account-suspensions`，Last updated Jun 2026）

**这是本报告全篇唯一一组同时具备四要素的一手规则**：

| 要素 | TikTok 的答案 |
|---|---|
| 状态枚举 | `Attention Needed`（警告 + 改进建议）→ `Poor`（停号） |
| **绕过分数的直通路径** | "Some issues can lead to an **immediate suspension** if the violation is **severe**" |
| **申诉时限** | **30 天** |
| **终局性** | 永久停号 **"You won't be able to appeal this decision"** |

`[推断]` **机制一：「严重度是一条旁路，而不是分数的一部分」。** 守衡目前是"累积命中"式判定，而 TikTok 的"严重度直通停号"与 Amazon 的"`single critical issue` → 立即停号"是**同一机制的两处独立实现**——**零容忍类目必须能绕过累积积分**。

`[推断]` **机制二：申诉必须有终点。** 全篇只有 TikTok 写明"30 天内解决或终局"。**"申诉次数上限"在本报告其它所有案例里都是「未找到公开资料」**——守衡 G7（申诉只有出口没有归途）缺的半个答案正在这里。

**(b) `[一手·已复验]` TikTok CGER 的季度公开指标——比其运营文档更硬的一层。** 从 CSV 严格取**全维度均为 `All` 的全局行**：

| 指标 | 最新值（Jan–Mar 2026） | 历史区间 |
|---|---|---|
| `Total videos removed` | 184,012,576 | — |
| **`Videos restored`** | **8,838,710（占 4.80%）** | **3.0% – 6.8%**（23 个季度） |
| `Proactive removal rate` | **99.3%** | 93.4% → 99.3%（持续上升） |
| **`Removal rate within 24 hours`** | **94.4%** | 89.8% – 94.8% |
| `Removal rate before any views` | （2023 年后停报） | 76.8% – 90.5% |
| **自动化处置量** | 147,864,952（**占 80.4%**） | 87.0%（Oct–Dec 2025） |

**三条要点**：

1. **TikTok 公开 restoration 计数**——**平台侧同样有可算的"翻案率"**（此处为合并口径，未区分"申诉翻案"与"主动自撤"，比 Meta 的四指标粗一档，但方向一致）。
2. **`Removal rate within 24 hours` 是一条被度量的 SLA 合规率**，比运营文档里"most are reviewed within 24 hours"这句承诺硬得多；另有**用户举报的处置时效分布**：**96.2% 在 2 小时内**处置完成，超 24 小时的仅 0.2%。
3. **自动化占比是公开的**（80.4%）。`[推断]` 人工占比为其余数（19.6%）属**推导值**——TikTok 只把 `Human moderation` 作为**政策域内的类别占比**发布，不发布全局人工处置量。

`[推断]` **一处数据陷阱（研究者复算时踩到，记此备查）**：该 CSV 的 `Policy type` / `Issue` / `Task type` / `Task` 各自都有 `All` 层级，**若只按 `Market == 'All'` 过滤而不锁定其余维度，同一指标会有多行命中**——我曾因此算出"Jan–Mar 2026 翻案率 52.97%"这一荒谬值。**正确做法是同时锁定六个维度全为 `All`。** 这与 §1.1 属同一类错误：**聚合层级选错，会稳定地产生看起来合理的错数。**

#### C4.3 Amazon：处置分级最细、申诉时限也有明文的一家

**(a) `[一手]` 申诉时限——底稿曾标"待核"，现已确认**：

> "Please expect a reply to your appeal **within two days**."（`_evidence/R1/amazon-appeal-restriction-removal-G200370560.md`）

**广告侧另有独立 SLA**：
> "You can check the status of your ads at any time in the ad console (**usually within 24 hours, but this could take up to 3 business days**)."（`_evidence/R1/amazon-ads-content-moderation-GXZXZ78UXL2AEBQ9.md`）

`[推断]` **这两条推翻了底稿"TikTok 是唯一公开 SLA 的一家"的判断**——Amazon 在**申诉**与**广告审核**两条链路上都有明文时限。**"公开时限"在平台侧是普遍做法，不是 TikTok 的孤例。**

**(b) `[一手]` 上架侧两层决策 + AHR 双因停号**：

> "**We make decisions at two levels: what products can be sold, and what requirements must be met to sell them.**"
> "When AHR suspends a seller, it happens for one of two reasons: **Poor historical performance** — … **Having a single critical issue** — Immediate zero-tolerance violations…"
> "The score **decreases** when a seller incurs policy violations and **improves through violation resolution and successful order fulfillment.**"

`[推断]` 最后一句是**平台侧最接近"翻案回流"的官方表述，但它只说了"账号分数回升"，没说"规则会因申诉而改"**。这正是 §3.6.3 修正后所指的那个真正的空白。

**(c) `[一手]` 公开数字（本轮最丰富的一组）**：主动拦截 **99.9%+** 侵权 listing、**每日**扫描 **50 亿+** 详情页改动、**2025 年查获 1,500 万+ 假货**、比品牌方自己发现**早 8 天**、新卖家 **100%** 须完成验证；2025 年新增 **agentic AI 审计**机制（"continuously scans for products that may have evaded our existing controls—**serving as an audit**"）。
`[推断]` 最后一条是"**用 AI 回头查已经进来的**"，与守衡的夹带审计同源但方向相反：不是拦入口，而是**复核存量**。

**(d) `[一手]` 买家评论侧的"一罪不再审"**：分级执法为 "Remove their content / Limit their ability to use community features / Suspend or terminate their account / **Withhold payments**"；另有一条罕见规则——"If we reject or remove your review for guidelines violation, **you won't be allowed to review that product again.**"
`[推断]` 这是"终局性"的另一种表达：**不是"不能再申诉"，而是"不能再对同一对象行使权利"**。

#### C4.4 三方横向对照

| 维度 | Meta | TikTok | Amazon |
|---|---|---|---|
| 规则库形态 | 两轴：Ad Content + Business Assets；每页 `Policy details \| Change log` 双标签 | 平铺主题清单（21 + 22 篇）；单篇「禁止 + 例外」二元式 | 按对象分体系：买家社区 / 卖家上架两层 / AHR 绩效分 |
| **处置分级** | `remove / reduce / inform` + strike system | `Attention Needed` → `Poor` → 30 天临时 → **permanent（不可再申诉）** + **严重度直通停号** | Remove content / Limit features / Suspend or terminate / **Withhold payments**；AHR **双因停号** |
| 人机边界措辞 | "where our technology **misses something or needs more input**"；**两级升级**（reviewers → subject matter experts） | "may involve **manual reviews or automated tools**"；**公开自动化占比 80.4%** | "proprietary machine learning" + "dedicated global team of compliance specialists" |
| **SLA** | 内容侧【未找到公开资料】 | ✅ "most are reviewed **within 24 hours**"，实测达成率 **94.4%** | ✅ 广告审核 **24 小时 / 最长 3 个工作日** |
| **申诉时限 / 终局性** | 五步流程含 "Option for review"，措辞为 "you **usually** can"（入口非无条件） | ✅ **30 天**；永久停号 **"You won't be able to appeal"** | ✅ **"expect a reply to your appeal within two days"** |
| **翻案率** | ✅ **可算且稳定**：FB 23–29%、IG 22.60%（§C4.1 复算） | ✅ **可算（合并口径）**：restored **3.0–6.8%** | 【未找到公开资料】 |
| 版本化 | ✅ **每页 Change log（日期 + 主题）** | 每页 `Last updated:` 月份，**无 diff** | 政策无 changelog；**Amazon Ads 另有独立 change log 页**（项目内已存） |
| **数值型触发阈值** | ❌ 只有定性词 | ❌ | ❌ |

`[推断]` **三方共性（可进 §7.0 速查表）**：**"关键分支的执行者是人还是机器"三方都不隐藏**（都明说"AI 预筛 + 人工兜底/升级"），**但"在什么数值条件下交接"三方都不公开**。这与 C1/C2 的结论一致，是该结论在**平台侧的第四次独立验证**。

#### C4.5 三条最值得守衡抄的机制 `[推断]`

1. **`reduce` 这一档：介于通过与否决之间的第三种处置。** Meta 原文："we'll often **reduce the distribution** of this content, **even when it doesn't quite meet the standard for removal**." **守衡现在是二值（合规 / 不合规），这一档会被迫二选一——要么放过、要么误杀。**
2. **版本化的三档形态**：① Meta **每页 Change log（日期 + 主题）**——可读的变更史（最强）；② TikTok `Last updated:` 月份——只知最新、不知改了什么；③ Amazon 政策无 changelog（最弱）。**对照 G4：守衡今天连"月份"这一档都没有，只有内容指纹**——能判断"变了"，不能判断"变了什么、何时生效、因为什么"。
3. **每一档处置都要有对应的"告知"动作。** Meta 的 `inform`，与 TikTok `Attention Needed` 档的"warning notifications and **suggestions to improve**"，都表明**平台把"告诉你为什么"当成处置的一部分**，而不是只给结果。

#### C4.6 本节的三条用词纪律（引用时不得越界）

1. Meta 的"**7 个一级类目**"是底稿对路径段的**归纳**，Meta 页面本身只暴露**二级路径**（100 条是真实的）。**不得写成 Meta 官方 taxonomy。**
2. TikTok 的"**prohibited / restricted / editorial 三分法**"**不是官方用词**；官方用 "In some cases… may be allowed" 表达受限。**不得当作 TikTok 官方分类引用。**
3. **Amazon POA（Plan of Action）三要素**（root cause / immediate corrective action / preventive measures）的**官方措辞本轮未取到**，底稿标 `[推断]`，**本节同样不作为事实使用**。底稿"登录墙"的结论对**卖家 listing 部分**成立，**但不适用于 Amazon 广告政策与 AHR 部分**（项目内已存 30+ 篇原文）。

---

---

## 6. 案例族 E：公开的失败与踩坑复盘

> **本节证据强度声明（请先读）**：本节最常被引用的两个数字（Gartner 的 40%、MIT NANDA 的 95%）在中文互联网上存在大量二手转述与夸大。**本报告只引用研究者亲自打开并读到原句的版本**，对未能取得一手出处的数字**明确标注"未取得一手原文"并拒绝使用**。这一点比数字本身更重要。

### 6.1 Gartner：超过 40% 的 Agentic AI 项目将在 2027 年底前被取消

**出处**：Gartner 官方新闻稿（2025-06-25），标题《Gartner Predicts Over 40% of Agentic AI Projects Will Be Canceled by End of 2027》——<https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027>
本报告读取的是**全文转载版**（标注"Originally published on Gartner, June 25, 2025"）：<https://www.predictiveanalyticsworld.com/machinelearningtimes/gartner-predicts-over-40-of-agentic-ai-projects-will-be-canceled-by-end-of-2027/13875/>【一手读取转载全文；gartner.com 原站有 Cloudflare 拦截】

**原文关键句（逐条摘录）**：
- **预测**："Over 40% of agentic AI projects will be canceled by the end of 2027, due to **escalating costs, unclear business value or inadequate risk controls**."
- **原因（分析师原话）**："Most agentic AI projects right now are **early stage experiments or proof of concepts that are mostly driven by hype and are often misapplied**... This can **blind organizations to the real cost and complexity** of deploying AI agents at scale, **stalling projects from moving into production**."——Anushree Verma, Senior Director Analyst, Gartner
- **投资分布（2025 年 1 月 Gartner 对 3,412 名 webinar 参与者的调查）**：19% 表示组织已对 agentic AI **大额投资**，42% 为**保守投资**，8% **无投资**，其余 31% **观望或不确定**。
- **"agent washing"（代理洗白）**：Gartner 指出大量厂商在参与炒作——"**the rebranding of existing products, such as AI assistants, robotic process automation (RPA) and chatbots, without substantial agentic capabilities**"。并给出一个极具冲击力的估计：**"Gartner estimates only about 130 of the thousands of agentic AI vendors are real."**

**对守衡的含义** `[推断]`：
1. Gartner 列的三条取消原因里，**"inadequate risk controls" 与知识库治理直接相关**——合规审核 Agent 恰恰是最需要"风险控制"作为卖点的品类，因此**守衡的护城河不在"能判"，而在"能证明它判得住"**。
2. "agent washing" 的教训对内部项目同样适用：守衡的判定引擎按 Anthropic 的定义属于 **workflow（预定义代码路径）而非 agent（模型自主决定流程）**。`[推断]` 这不是缺点，但**对外表述时不应把 workflow 包装成自主 agent**——一旦被追问"它自己决定什么"，叙事会崩。

---

### 6.2 Air Canada 聊天机器人案（Moffatt v. Air Canada, 2024 BCCRT 149）：知识库与现实不一致的判例

**这是一条司法判决，不是产品评论**，因此证据等级最高。

**可确证的事实**【二手（多家律所与律师协会的案情摘要），判例本身可追】：
- 案件：**Moffatt v. Air Canada, 2024 BCCRT 149**（不列颠哥伦比亚省民事解决法庭），**2024-02-14** 作出裁决。
- 事实经过：Jake Moffatt 在其亲属去世后，通过 Air Canada 官网的**聊天机器人**询问**bereavement fare（丧亲票价）**政策；机器人给出了与航空公司实际政策**不一致**的信息。
- 争点：Air Canada 主张"**cannot be held liable for the information provided by the chatbot**"，并援引其 Domestic Tariff 的合同条款；同时主张 Moffatt 未按规定程序申请。
- 裁决结果：** tribunal 认定 Air Canada 对聊天机器人提供错误信息承担 negligent misrepresentation（过失虚假陈述）责任**，判令其支付**标准票价与丧亲票价之间的差额**，另加利息与仲裁费用。
- 判决中的一句被广泛引用（多家法律分析转述）：Air Canada 关于"聊天机器人是独立法律实体"的辩解**不成立**——**公司对其网站上的所有信息负责**。
- 出处（可打开性已逐条实测，标注如下）：
  - 【二手·可引用】McCarthy Tétrault 案例分析：<https://www.mccarthy.ca/en/insights/blogs/techlex/moffatt-v-air-canada-misrepresentation-ai-chatbot>（标题与摘要已确认；**正文因 Vercel 安全校验未打开全文**）
  - 【二手·可引用】WeirFoulds 案例分析：<https://www.weirfoulds.com/moffatt-v-air-canada-bot-betrayal-and-negligent-misrepresentation>（页面已打开，正文被截断）
  - 【二手·可引用】American Bar Association Business Law Today（2024-02）：<https://www.americanbar.org/groups/business_law/resources/business-law-today/2024-february/bc-tribunal-confirms-companies-remain-liable-information-provided-ai-chatbot/>（摘要原文："the British Columbia Civil Resolution Tribunal found Air Canada liable for misinformation given to a consumer by an AI chatbot on its website and awarded damages"；**正文因 Cloudflare 未打开**）
  - 【判决全文·未打开】CanLII 与 BCCRT 官网在本次调研中均返回 403 / JS 校验，**研究者未能读到判决书原文**。凡涉及判决具体措辞的表述，本报告均以多家权威二手来源的**一致**表述为准，并已在措辞上避免超出该共识。

**这是"知识库建设"层面最有价值的一个案例** `[推断]`：
- 它的失效机制**不是检索不到**，而是**存在一个错误的、且对客户可见的知识源（聊天机器人），同时存在一个正确的、但客户查不到的知识源（内部政策文件）**。
- 用本报告的分层词汇说：**L0（权威源认定）缺失**。系统没有规定"当聊天机器人的答案与 Tariff 冲突时，以哪个为准"，于是**对外呈现的那一份自动成为了事实上的权威源**。
- **对守衡的直接含义**：守衡的判定结论会**直接对外**（发给达人/运营/可能到达平台）。因此"权威源认定"不是内部治理洁癖，而是**责任边界**。这正好解释了本项目为什么必须有 `legal-decisions-v1.json` 这种"决定与未决的唯一台账"，以及为什么规则要带生效时间。

---

### 6.3 行业结构性失败：**评测层普遍缺失**

这不是某一家的事故，而是本报告在**十二家案例**（第 2 节六家 + 第 3 节五家 + Salesforce）中**实测到的系统性缺口**，其证据是可枚举的"未找到"：

| 产品 | 公开的评测方法 | 实测结论 |
|---|---|---|
| **Glean** | **有，且到指标级**：AI Evaluator，逐指标公开（context relevance/recall、answer relevance/completeness、groundedness），并公开**人机一致率 74%、人类标注者彼此一致率 79%** | 唯一把"人类一致性上限"也公开的一家 |
| **Sierra** | **有，且到开源 benchmark 级**：τ-bench 谱系（τ-bench → τ² → **τ³ = τ-Knowledge + τ-Voice** → **hyper-τ**）；平台内 Simulations（agent / user / **judge** 三段，可门禁化）；**daily golden articles + recall / precision / nDCG** | 公开度与 Glean 并列第一梯队 |
| **Harvey** | **有，构造方法最可复用**：**BigLaw Bench 源自 time entry**（"Because **all work is billed**…"）；**answer score / source score 双分且相互独立**；BLB: Retrieval 用 **recall at a fixed token threshold**；<60% 完成度即判无用 | 唯一把"评测集怎么来的"写清楚的一家 |
| **Dragon Copilot** | **有，方法学与 Glean 同级**：两级测试（平台服务 **2–5k 查询** → 用户应用 **50–100 查询**）；三判据 **Groundedness and fabrications / Answer relevance / Evidence relevance**；红队在 credible / customer / harmful adversarial 三类源上分别做 UPIA / XPIA | **并诚实声明"客户自建语料上不保证 grounding"** |
| **Abridge** | **有**：when/what/how 框架；safety / accuracy / fairness / usability 四维；**intrinsic vs outcome-based 显式拆分**；**LLM judge 须先在医生标注上验证一致**；CDS 安全 **99.5% / 1,000+ cases / 1,000+ rubrics** | ⚠️ 均为**厂商自设自跑**，无外部审计；且**无 note 级准确率数字** |
| **Decagon** | **有，评的对象最新颖**：**DuetBench** —— 据其公开材料为**首个评测客服 Agent「自我改进能力」**的 benchmark，对照内部 **Decagon Masters** 人类认证 | 评的是"自改进"，不是"单题解决" |
| **Salesforce Agentforce** | **只有工程规格，无方法学**：三套测试入口（UI-CSV / CLI-YAML / API-XML）+ 自定义评测（**JSONPath** 断言字符串 / 数值 / 延迟） | **有"如何写断言"，没有"如何造黄金集"** |
| **Microsoft 365 Copilot** | **无公开方法** | 只有 Index browser 的 item 级运维校验与"不擅长的查询类型"清单 |
| **Atlassian Rovo** | **只有数字，无方法** | "44% more accurate / 48% fewer tokens"、"60% more successful"均无度量口径 → **不可复现** |
| **Notion AI** | **无公开方法** | 只有能力边界声明 |
| **Sana** | **无公开方法** | 只有"排序模型用内部训练集"+ 用户反馈设置 |
| **Dust.tt** | **无公开方法** | 只有 thumbs up/down 反馈 API 与"自行 A/B"建议 |

**依据**：逐条见 `raw/A-企业知识助手案例.md`、`raw/_sub-cx-vertical.md`、`raw/_sub-health.md`、`raw/_sub_legal.md` 的「未找到 / 存疑清单」。

`[推断]` **为什么会这样，以及为什么这是守衡的机会**：
- 评测需要**标注**，标注需要**业务专家**，而业务专家的时间在任何组织里都是最稀缺资源。因此"评测做不起来"是行业默认状态，不是能力问题。
- 于是行业普遍退化成两种替代品：**①厂商宣称数字**（不可复现，如 Atlassian 的 44%）；**②产品化反馈按钮**（thumbs up/down，只反映满意度不反映正确性）。
- **守衡的处境与它们不同**：它有**291 条带人工判定的冻结语料**与**V13 的混淆矩阵基线（precision 0.970 / recall 0.962 / f1 0.966）**，这在同规模项目里是罕见的资产。`[推断]` 守衡真正缺的不是"能不能评测"，而是"**评测集能不能随时间变化**"——冻结基线只能防劣化，不能改进。

**一条从上面这张表读出来的规律**（`[推断]`，但支撑事实齐全）：**公开的评测方法学与"是否面向强监管行业"正相关**。公开到方法级的是 Glean、Sierra、Harvey、Abridge、Dragon Copilot——其中四家直接服务金融、法律、医疗；而**最不公开方法学的，恰恰是覆盖面最广、客户最多的两家（Microsoft 与 Salesforce）**。这与其采购路径一致：**它们靠认证、合同与审计取信，不靠 benchmark 取信。** 对守衡的含义是：**不要指望从最大的厂商那里抄到评测方法**，可抄的方法学在第 3 节那几家强监管垂直厂商。

#### 6.3.1 与本节配套的方法论边界（写给复核者）

本报告在评测这条线上刻意划了三条边界，写在这里以免被误引：

1. **厂商宣称 ≠ 独立验证**。Abridge 的 99.5%、Dragon Copilot 的"每次就诊省 5 分钟 / 70% 医师倦怠下降"，前者是**厂商自设自跑的评测**（无外部审计），后者的脚注来源是**问卷**（Microsoft 对 340 家机构 879 名医师的调查）。两者都不是临床试验结论。
2. **不存在"Kaiser Permanente 的 DAX 结局试验"**。本轮一手检索未定位到该研究；Kaiser 关联单位在文献中的存在形态是**方法学/质量评论**（*Ann Intern Med* 2026;179(6):898-899、*JAMA* 2026;335(16):1393-1395），**不是结局试验，不得引用为 DAX 效果证据**。
3. **可引用的具名独立研究，只有两条对本报告最关键**（均标 `[子代理 API 读取，未复核]`，PMID 可直接核验）：
   - **UCLA 三臂 RCT（Lukac 等，*NEJM AI* 2025;2(12)，PMID 41497288）**：238 名医师 / 14 专科，DAX Copilot vs Nabla vs 常规照护；主结局 **DAX −1.7%（P=0.66，不显著）**，Nabla −9.5%（P=0.02）。**这是目前唯一的 DAX RCT，且主结局对 DAX 不利。**
   - **UT Southwestern 交叉试验（Webb 等，*Appl Clin Inform* 2026;17(1):118-126，PMID 41734793）**：**DAX 与 Abridge 正面对撞**，校正模型显示差异主要来自 **order effect 而非工具本身**。**这条对"两家厂商对比"最关键**：正面对撞下未观察到工具本身的可靠差异。
   - ⚠️ 另有一条常见的错误归因：*JAMA* 2026 的多中心研究（Rotenstein 等，**PMID 41920565**，8,581 名医师）**摘要未具名任何厂商**，其 COI 反而披露了 Abridge 顾问关系与 MGB 对 Abridge 的投资 —— **不得归给 DAX**。

---

### 6.4 官方文档里承认的产品级失效模式（比第三方吐槽更可信）

企业 AI 的失败复盘里，最可靠的一类证据是**厂商自己写在文档里的限制**。本报告收集到以下几条，全部为【一手】：

| 失效模式 | 官方原文 | 出处 |
|---|---|---|
| **护栏会被与主调用同一个注入绕过** | "a **prompt injection** attempt could be successful in evading **both your guardrail and your actual LLM call**" | OpenAI Cookbook `How_to_use_guardrails.ipynb` |
| **长对话导致指令稀释、更易被越狱** | "As conversations get longer, LLMs are more susceptible to **jailbreaking** as your instructions become **diluted** by the extra text" | 同上 |
| **过度收紧造成 over-refusal** | "Guardrails can harm the user experience if you make them overly restrictive... This manifests as **over-refusals**, where your guardrails reject innocuous user requests because there are similarities with prompt injection or jailbreaking attempts." | 同上 |
| **误报会撕裂用户体验** | "More **false positives** leads to a **fractured user experience**, where customers get annoyed and the assistant seems less helpful." | OpenAI Cookbook `How_to_use_moderation.ipynb` |
| **阈值会随模型更新漂移，且不通知** | "**need to update that threshold when the models update**... we are **not able to notify users each time an update is released**" | Perspective API 官方 FAQ（【官方·仅搜索摘要】） |
| **权限变更的索引生效有硬缺口** | "**Permissions updates occur during a full crawl, not an incremental crawl**"、"might take up to **24 hours** to reflect" | Microsoft Learn `connectors/indexed-content` |
| **索引与搜索无法分别排除** | "There's **no option to exclude results from Microsoft Search only or semantic indexing only**; actions apply to both at the same time." | Microsoft Learn `semantic-index-for-copilot` |
| **语义索引在特定查询类型上不擅长** | 官方列出：无主题关键词的查询、多参数查询、计数类查询 | 同上 |
| **Skill 是供应链攻击面** | "malicious skills may introduce vulnerabilities in the environment where they're used or **direct Claude to exfiltrate data and take unintended actions**" | Anthropic Agent Skills 工程博客 |
| **模型在低质量检索上会"自信地错"** | LangChain 引用 CRAG/Self-RAG 的动机："many have found that implementing RAG requires **logical reasoning around these steps**: when to retrieve, when to re-write the question, or **when to discard irrelevant retrieved documents and re-try retrieval**" | LangChain 官方博客 |
| **对本质确定的流程用不确定模式（反模式）** | "Using **deterministic patterns for workflows that are inherently nondeterministic**"、以及反向的"using nondeterministic patterns for workflows that are inherently deterministic" | Microsoft Azure Architecture Center |
| **多 agent 共享可变状态导致事务不一致** | "**Sharing mutable state between concurrent agents**, which can result in transactionally inconsistent data because of assuming synchronous updates across agent boundaries" | 同上 |
| **低质量或跑题的输出会在流水线中级联** | "Low-confidence, malformed, or off-topic responses **can cascade through a pipeline**"；建议"**surface errors instead of hiding them**" | 同上 |
| **处置分级不足会把"该限制"的中间档逼成二选一** | 平台承认存在介于通过与否决之间的第三档：Meta——"we'll often **reduce the distribution** of this content, **even when it doesn't quite meet the standard for removal**" | Meta 官方执法说明（`_evidence/R1/meta-enforcement-hub.md`） |
| **申诉若无终局性，复核会无限循环** | TikTok 把终局性写成明文规则："**You won't be able to appeal this decision.**"（永久停号）；Amazon 买家侧为 "you **won't be allowed to review that product again**" | TikTok `account-suspensions`；Amazon Community Guidelines |

**这张表的读法** `[推断]`：把厂商自陈的限制**直接当成自己的测试用例清单**。每一行都是一个可以立刻写的回归用例——例如"构造一次长对话 + 注入，检查语境守卫是否与主判定同时失守"。

---

### 6.5 未能取得一手出处的常见说法（**明确排除，不作为依据**）

以下说法在中文技术圈流传极广，但**本次调研未能取得可打开的一手原文**，因此本报告**不引用其具体数字**：

| 流传说法 | 本次核实结果 |
|---|---|
| **MIT NANDA《The GenAI Divide: State of AI in Business 2025》"95% 的生成式 AI 试点未产生可衡量回报"** | **未取得一手原文**（本机检索通路受限，未定位到可直连的原始报告 PDF）。报告中"失败原因归类"的转述版本很多且互相矛盾，**故不引用**。 |
| **S&P Global "42% 的公司在 2025 年前放弃多数 AI 计划"** | **未取得一手原文**，不引用。 |
| **"Klarna 用 AI 客服替代 700 名客服后于 2025 年回补招聘"** | **未取得一手原文**（Bloomberg 付费墙；官方声明未定位）。**细节（人数、时间、措辞）不引用。** |
| **"McDonald's 与 IBM 的 AI drive-thru 于 2024 年终止"** | **未取得一手原文**，不引用具体时间与原因。 |
| **"Cursor 支持机器人编造政策并道歉"** | **未取得一手原文**，不引用。 |
| **"Gartner 称知识图谱可把准确率提升 XX%"** | **未取得一手原文**，不引用。 |
| **RAG/Agent 在真实企业环境的命中率数字** | **未取得**任何可引用的公开基准，不引用。 |

**为什么要把这张表写出来**：本报告的第一原则是"**不确定的就不写**"。这七个说法很可能**部分为真**，但"很可能为真"不等于"可以写进决策依据"。`[推断]` 对本项目的实际启示是反向的——**如果一个数字你追不到一手出处，它就不该出现在给法务或老板看的材料里**；这条纪律与守衡自身的"声明必须可证伪"是同一条。

---

### 6.6 从失败中提炼的六条"知识库建设"教训

> 每条 = 机制 → 教训 → 对应本报告的分层。

**教训 1：失效常常不是"检索不到"，而是"检索到了不该被信任的那一份"。**
机制：多个知识源并存且无权威源认定时，**对外可见的那一份会自动成为权威**（Air Canada 案）。→ **教训**：L0 权威源认定必须先于 L2 索引建设。→ 分层：L0 / L2。

**教训 2：权限的"最终一致性"必须变成可声明的 SLO，而不是隐含假设。**
机制：Microsoft 的 ACL 变更仅 full crawl 生效、最长 24h。→ **教训**：任何"AI 能读到什么"的能力，都要同时声明"权限变更多久生效"，并在 UI 或文档里对使用者可见。→ 分层：L3。

**教训 3：阈值不是配置，是会漂移的资产。**
机制：模型更新改变同一阈值的行为，且厂商不通知（Perspective）。→ **教训**：阈值必须带"校准日期 + 对应模型版本"，模型升级触发回归。→ 分层：L4 / L8。

**教训 4：护栏必须与主判定解耦，且需要独立的失效测试。**
机制：同一注入可同时绕过护栏与主调用；长上下文稀释指令。→ **教训**：护栏独立调用 + 独立回归用例（含长对话注入场景）。→ 分层：L6 / L8。

**教训 5：评测集如果不会生长，评测就只是防劣化，不是改进。**
机制：冻结基线（如逐项等于常量）+ 无入集机制 = 新发现的错例不进评测。→ **教训**：必须有"错例 → 评测集"的入集路径，且误报与漏放**分开统计**。→ 分层：L8。

**教训 6：申诉的"归途"比"出口"更重要。**
机制：只建申诉入口、不建申诉结果回流，则撤销过的事实不会改变任何规则或任何数字。→ **教训**：申诉记录必须与判定记录**同构、可追加、不可覆盖**，并能反向驱动规则修订与误报计数。→ 分层：L5 / L8。

---

---

## 7. 跨案例共识清单与企业 Agent 知识库分层候选方案

> **本节性质声明**：这是本报告的**归纳与设计**部分，不是任何单一来源的官方结论。每一条都标注了它由哪些案例/资料支撑，以及它属于「多案例共有」还是「少数派做法」。凡属我个人的设计判断，标 `[推断]`。

### 7.0 共识度速查表

| # | 命题 | 共识度 | 支撑案例/资料 |
|---|---|---|---|
| 1 | 必须有**独立的连接器/语料接入层**，且它是可枚举、可审计的资产清单 | **几乎全体** | Glean Connectors 四类；M365 Synced/Federated；Rovo Connectors；Notion AI Connectors；Sana integrations；Dust Data sources |
| 2 | 必须有**租户内索引/语义层**，而不是每次查询都直连源系统 | **几乎全体** | 第 2 节六家全部；M365 明确"semantic index is created for every subscription"。第 3 节的反例值得注意：**Harvey 公开了"免预摄取的 Agentic search over DMS"方向**，即承认索引层可以被绕过 |
| 3 | **权限是一等维度**，且必须在检索/交付时收敛到调用者身份 | **全体** | Glean "mirror permissions"；M365 "honor the user identity-based access boundary"；Rovo "last-mile checks"；Notion "acts as you"；Sana private integration；Dust follows user's permissions |
| 4 | 权限的**一致性等级是必须显式化的工程参数**（快照 vs 实时） | **全体**（但只有 Glean 显式命名） | Glean **Indexed/Live/Hybrid**；M365 ACL ≤24h 且仅 full crawl 生效；Rovo last-mile；Sana 每用户自认证；Notion 3h/72h |
| 5 | **权威源认定**是知识层的核心问题 | **少数派明说，多数隐含** | Rovo "surface the **single sources of truth**"；Glean 用 **canonical document** 定义 context recall；M365 people connector "keeping the original data authoritative in its source system"；Notion/Atlassian 未给机制 |
| 6 | **权威源需要被"消歧机制"保障**，而不只是口号 | **少数派** | Rovo 用图谱关系做 "authoritative retrieval"；Glean 用 canonical document 作为评测锚点。**其余产品未公开机制** |
| 7 | **新鲜度必须变成公开数字**（刷新频率 / 时间预算） | **少数派但极有价值** | Glean 逐连接器刷新频率表；Notion 72h/3h/1 年/1 天；M365 按天/即时/近实时三档；Sana 只说 "real-time"；Rovo 只说 "at the speed of change" |
| 8 | **淘汰/废弃内容要有检索时的一等机制**（而非靠目录治理） | **个别** | Dust 的 **must-have / must-not-have label**；M365 的 sensitivity label 参与 search trimming |
| 9 | **行为层应可打包分发**（instructions + knowledge + tools 一体） | **少数派但正在扩散** | Anthropic **Agent Skills**（开放标准）；Dust **Skills**（"Reusable packages of instructions, knowledge, and tools"）；Glean Skills |
| 10 | **阈值/策略的所有权属于部署方**，模型只提供分数 | **审核类共识** | Perspective（API 给概率，判定权归调用方）；OpenAI（"your use case or tolerance may be different"） |
| 11 | **阈值必须随模型版本重校准**，且厂商不会通知 | **Perspective 明说；OpenAI 隐含** | Perspective FAQ 原文；OpenAI 用混淆矩阵定阈 |
| 12 | **评测应在客户私有语料上做** | **个别** | 仅 Glean 明确（AI Evaluator 在租户内跑）；其余产品只有产品化反馈或干脆没有 |
| 13 | **把"护栏"拆成独立调用**，不让同一次调用既判定又兜底 | **方法论共识** | Anthropic（parallelization/guardrails）；OpenAI（input/output 分离）；Microsoft（多点位 guardrails） |
| 14 | **人工检查点是架构组件**，要有明确的批准/反馈语义与迭代上限 | **方法论共识 + 少数产品** | Microsoft maker-checker（含 acceptance criteria 与迭代上限）；Anthropic "pause for human feedback at checkpoints"；Salesforce Guardrails |
| 15 | **失败/拒答要作为一等信号被记录与分析** | **个别** | Glean 把 "No Answers" 与低 groundedness 用作流失预测因子（+18.8% 预测准确率） |
| 16 | **权限的判断权不应由 AI 层自建**：AI 层只执行上游权威系统的结论，**从不创建/修改/删除权限规则** | **个别但极强** | Harvey 官方原文："When **Intapp** says a wall exists… the AI platform **enforces that wall**"，"**Harvey never creates, modifies, or deletes walls**, ensuring that your walls provider remains **the system of record**"；并明确反对自建——"An AI platform that tries to build its **own parallel conflicts system is making a mistake**"。`[推断]` **对守衡的直接对应**：白名单/规则的权威在法务与产品，守衡不应自己发明例外 |
| 17 | **权限判定要 fail closed**：无法确认归属就先不读、并上报不确定性，而不是先读了再说 | **个别** | Harvey 官方原文："If an agent can't confirm that a document falls within the matter's boundary, it **must skip that document and flag the uncertainty**"；Dragon Copilot 同向（"External sources and data from other sessions are **not allowed**"） |
| 18 | **读写不对称**：Agent 可以整理（移动/改名/打标），但**绝不改内容**，且**任何变更需人确认后才执行** | **个别但极有价值** | Harvey 官方原文：Agent can "move, rename, and tag files, but importantly, it **never edits the content inside them**" and "**never runs a change without a person confirming it first**"；"proposes a plan and shows exactly what it intends to change before touching anything" + 可撤销上一批变更。`[推断]` 这是"AI 不越权"最可落地的形态，比抽象原则有用 |
| 19 | **评测要在客户自己的租户/语料内跑**，而不是只看厂商 benchmark | **个别** | 仅 Glean 明确（**AI Evaluator 在每个客户租户内**运行）；Sierra 的 golden articles 从**该客户自己的对话**里每日采样生成 |
| 20 | **"关键分支不交给 LLM 解释"**应当被写进架构，而不是写在提示词里 | **两家独立来源** | Salesforce **Agent Script** 原文："workflows **that don't rely on interpretation by an LLM**"；OpenAI guardrails 手册原文："**combine guardrails with rules-based or more traditional machine learning models** for detection" |
| 21 | **公开的评测方法学与"是否面向强监管行业"正相关** | **全体观察** | 公开到方法级的是 Glean、Sierra、Harvey、Abridge、Dragon Copilot；Microsoft、Notion、Sana、Dust 只有产品化测试，Salesforce 只有断言规格。**最不公开方法学的反而是覆盖面最广的两家（Microsoft / Salesforce）**`[推断]`：与其采购路径（靠认证与合同而非 benchmark 取信）一致 |
| 22 | **申诉翻案率必须与申诉率成对发布，并同时给出精度区间与假阳性绝对数** | **个别但极强** | Meta CSER 四指标并列（`Content Actioned` / `Content Appealed` / `Content Restored with appeal` / `Content Restored without appeal`）+ `Enforcement Precision` 区间 + `False Positive` 绝对数区间。**研究者已在项目内 CSV 上复算验证其可用性（§5 · C4.1）**：FB 翻案率逐季 23–29% 稳健，而单看申诉率会因 Fake Accounts 污染得出 0.38% 的假值 |
| 23 | **处置分级应 ≥ 三档：否决 / 限制（降流量）/ 通过** | **两家独立** | Meta `remove / reduce / inform`，其中 `reduce` 明确 "**even when it doesn't quite meet the standard for removal**"；Amazon 四级含 `Withhold payments`。`[推断]` 只有二值判定的系统会把"该降流量"的中间档**被迫二选一**（§5 · C4.5） |
| 24 | **严重度应是一条旁路，而不是分数的一部分** | **两家独立** | TikTok："Some issues can lead to an **immediate suspension** if the violation is **severe**"；Amazon AHR："**Having a single critical issue** — Immediate zero-tolerance violations"。`[推断]` **零容忍类目必须能绕过累积积分**，而守衡目前是纯累积命中式（§5 · C4.2 / C4.3） |
| 25 | **申诉必须有明确的时限与终局性** | **个别** | TikTok：**30 天**窗口 + 永久停号 "**You won't be able to appeal this decision**"；Amazon："expect a reply to your appeal **within two days**"。`[推断]` **这是全篇唯一明确写出"申诉有终点"的证据，恰好补上 G7 的半个答案**——"申诉次数上限"在其余全部案例中均为「未找到公开资料」 |

---

### 7.1 分层候选方案：企业 Agent 知识库的八层

> 下图是**本报告提出的候选方案**，不是某厂商的官方架构。每层标注了"多数案例共有"或"少数派做法"。`[推断]` 全部为归纳性判断。

```
L0  源与权威层        Source & Authority
    └ 谁拥有这条知识 / 哪一份是准的 / 何时生效 / 何时失效
L1  接入层            Connectors
    └ 同步型（入索引） vs 联邦型（不入索引）/ 推 vs 拉 / Smart Link vs 全内容
L2  索引层            Index
    └ 词法 + 语义（向量）+ 元数据信号；图（可选）；增量 vs 全量
L3  权限层            Permission
    └ 索引期快照 / 检索期收敛 / last-mile 校验；一致性等级显式化
L4  规则与阈值层      Rules & Thresholds        ← 合规审核的"事实层"
    └ 分类法 + 规则条目 + 阈值 + 版本 + 生效时间 + owner
L5  先例与申诉层      Precedents & Appeals      ← 合规审核的"判断层"
    └ 正例/负例/边界例 + 裁决理由 + 引用链 + 申诉与翻案记录
L6  程序与工具层      Procedures & Tools
    └ Skill / Playbook / 工具契约（确定性部分用脚本）
L7  记忆与状态层      Memory & State
    └ 会话内 compaction / 跨会话裁决流水 / 项目状态
L8  评测与回归层      Eval & Regression         ← 横切，不是终点
    └ 黄金集 + 混淆矩阵 + 回归触发 + 申诉回流
```

**各层的共识度与关键取舍**：

| 层 | 共识度 | 关键取舍与证据 |
|---|---|---|
| **L0 源与权威层** | **少数派显式化，但失败代价最高** | Rovo 明说 "single sources of truth"，Glean 以 canonical document 定义 recall。`[推断]` 多数产品的做法是"不解决，靠排名兜底"，这在通用知识搜索里勉强可行，**在合规判定里不可行**——因为判错要担责 |
| **L1 接入层** | **全体共有** | 分歧在"是否允许不入索引"。M365 的 **Federated connector（MCP，明确不支持语义索引）**与 Rovo 的 **Smart Link** 是同一个取舍的两种实现："**用放弃检索能力换合规**" |
| **L2 索引层** | **全体共有** | 分歧在图。Rovo/Glean 有图谱，Sana/Dust/Notion 没有明确图谱层。`[推断]` 图谱的价值主要是**权威源消歧**与**关系型问答**，不是通用的检索增强 |
| **L3 权限层** | **全体共有，但一致性等级差异巨大** | Microsoft：**ACL 更新仅 full crawl 生效，最长 24h**（反面参照）。Rovo：**last-mile checks**（正面参照）。Glean：三档模式（折中参照）。Notion：**permissions mapping 作为连接器契约**（设计参照）。**垂直侧三家给出最细的实现**：Sierra 让**工具在未认证时根本不出现**、Harvey **"the agent has the same permissions as the user" + retrieval/context/output 三层强制 + fail closed**、Dragon Copilot **按患者级隐私标记在检索期裁剪**。★ 完整光谱见 **§2.0.1**（六家）与 **§3.6.1**（含垂直五家） |
| **L4 规则与阈值层** | **审核类产品必有，但企业知识助手普遍不显式建模** | OpenAI 的 `parameters` 随判定落库；Perspective 的"属性定义 + 部署方阈值"分离；Microsoft 的 sensitivity label 参与 trimming。`[推断]` 这是**企业知识助手类产品与合规审核类产品的最大结构差异**：前者把规则隐含在 prompt 与排序里，后者必须把规则变成可 diff 的资产。★ **版本化的三档形态（平台侧，见 §5 · C4.5）**：① Meta **每页 Change log（日期 + 主题）**= 可读的变更史（最强）＞ ② TikTok `Last updated:` 月份 = 只知最新、不知改了什么 ＞ ③ Amazon 政策无 changelog（最弱）。**对照 G4：守衡今天连"月份"这一档都没有，只有内容指纹**——能判断"变了"，不能判断"变了什么、何时生效、因为什么" |
| **L5 先例与申诉层** | **最少被显式建模，但合规场景最不可缺** | `[推断]` 依据：Anthropic 的 few-shot 原则要求"curate **diverse, canonical examples**"；Self-RAG 的 `ISREL`/`ISSUP`/`ISUSE` 三问实质就是在做"这条先例是否相关、结论是否有据、是否有用"；OpenAI 用混淆矩阵定阈意味着**必须有标注好的误判样本**——而误判样本的来源就是申诉。**本次调研未在任何厂商（企业软件 / 法律 / 医疗 AI）的公开架构里找到"申诉库"作为一等层的命名**——`[推断]` 这是**厂商侧**的空白点，也是守衡可以领先的地方。**⚠️ 但它不是全行业的空白（本报告第二次自我证伪，见 §3.6.3）**：**平台侧早已把申诉做成了公开台账**——Meta 按季度发布四个可算出翻案率的并列指标，TikTok 公开 restoration 计数与处置时效。★ **因此本层的正确做法不是"从零设计"，而是"照抄一份已跑通的台账 + 补上平台侧也没有的那一环"**：① 台账字段直接采用 Meta 四指标（**且"平台自撤"与"申诉翻案"必须分开计**）；② 必须有**时限与终局性**（TikTok：30 天 + 不可再申诉）；③ 处置分级 ≥ 三档（含"降流量"）；④ **平台侧同样缺位的是"裁决回流到规则"**——"翻案 → 规则修订 → 生效"这条因果链没有任何一家公开，**这才是守衡真正的差异化位置**（§5 · C4） |
| **L6 程序与工具层** | **正在从少数派变主流** | Agent Skills 已成开放标准（agentskills.io）；Dust 的 Skills 与 Glean 的 Skills 是三家的独立收敛。`[推断]` 收敛原因很清楚：**知识不解决"怎么做事"，必须另有一层承载程序** |
| **L7 记忆与状态层** | **全体共有，但多数不叫这个名字** | Notion 的 memory system 用 pages/databases 承载；Anthropic 用 compaction + notes 文件；MemGPT 用 OS 式分层。`[推断]` 对合规审核，这一层的正确形态不是"记住用户偏好"，而是"**记住这个项目/这个店铺/这个 SKU 的未决事项与既往处置**" |
| **L8 评测与回归层** | **共识最弱、缺口最大** | 十二家里只有 Glean 公开到指标级，其次是 Sierra / Harvey / Dragon Copilot / Abridge（方法级）与 Decagon（benchmark 级）；Microsoft / Notion / Sana / Dust **未找到公开评测方法**，Salesforce 只有断言规格而无 golden set 方法。★ 一条重要的横切发现：**四家的黄金集都不是凭空造的，而是从业务痕迹里派生的**（Harvey 从计费工时、Sierra 从前一日对话、Abridge 从医生编辑动作、Dragon Copilot 从匿名临床文档）——见 **§3.6.2**。**一条可用的量化锚点**：Glean 公开 **人类标注者彼此一致率仅 79%**，并把它当作自动评测的上限，**AI Evaluator 与人类 74%**。`[推断]` 这不是偶然：**评测需要标注，标注需要业务专家，而业务专家的时间是最稀缺资源**。因此"评测做不起来"几乎是行业默认状态——**也正因如此，谁先建起来谁就有复利**。`[推断]` **79% 这个数字还有一个用法**：它给出了"人类基线"，从此任何自动评测的分数都必须对照它来解读，而不是孤立地宣称"准确率 9x%"。★ **披露形态的最低要求（平台侧给出的范例，见 §5 · C4.1）**：**精度必须给区间、假阳性必须给绝对数**——Meta 公开 `Enforcement Precision` **90.80%–91.85%**（FB）与 `False Positive` **3,020–3,080 万条**。`[推断]` **单点精度不构成可问责的披露**，因为它无法被反向引用；同时给"百分比"与"错在哪、错了多少条"，才能使读者无法只挑一个方向引用 |

---

### 7.2 「从知识库走到 Agent」的三道关（本报告提炼）

`[推断]` 综合 Anthropic（Skill 三级披露 + just-in-time）、Microsoft（复杂度阶梯 + maker-checker + security trimming）、OpenAI（三层 moderation + 阈值治理），把"知识→Agent"的通过条件归为三道关：

**第一关：可发现（Discoverable）**
- 知识必须有**唯一的权威版本 + 明确的生效窗口**，否则"发现"等于"发现冲突"。
- 触发条件（skill 的 `description`、工具的描述）必须是**能区分近邻**的——Anthropic 明确："Pay special attention to the `name` and `description`... Claude will use these when deciding whether to trigger the skill."
- 验收：**同一问题问两次、换个人问，命中的权威源必须是同一个。**

**第二关：可按需加载（Loadable on demand）**
- 遵循 progressive disclosure：元数据常驻 → 正文按需 → 附件按需。
- 遵循 just-in-time：**结论里只存轻量标识符**（规则 ID、先例 ID、定位符），全文运行时取。
- 上下文是稀缺资源：目标函数是"**smallest possible set of high-signal tokens**"。
- 验收：**判定的上下文里不出现未被引用的规则全文。**

**第三关：可执行且可审计（Executable & Auditable）**
- 确定性部分用脚本，不确定部分才用模型；工具描述做 poka-yoke。
- 每个结论必须能回答"**依据哪条规则、哪条先例、哪个版本**"。
- 权限在**每个**执行单元独立收敛（"security trimming must be implemented in every agent"）。
- 失败必须外显（"surface errors instead of hiding them"）并成为评测输入。
- **权限判定 fail closed**：无法确认归属就跳过并标记，而不是先读了再说（Harvey 官方原则）；**读写不对称**：可整理、不可改内容，任何变更需人确认后才执行（Harvey 官方原则）。
- 验收：**抽掉任意一条引用，结论必须变成"无法支撑"而不是"照旧输出"。**

---

### 7.3 知识库建设的失败模式清单（机制级描述）

> 每条给出"机制"而非"症状"。带出处的为事实，纯归纳的标 `[推断]`。

| # | 失败模式（机制） | 为什么会发生 | 出处 / 依据 | 防御动作 |
|---|---|---|---|---|
| **F1** | **权限快照过期**：源系统权限已变更，索引里的 ACL 还是旧的，导致越权或该看不看到 | ACL 只在特定时机重建 | **事实**：M365 "**Permissions updates occur during a full crawl, not an incremental crawl**"，且"**might take up to 24 hours to reflect**"（<https://learn.microsoft.com/en-us/microsoft-365/copilot/connectors/indexed-content>） | 把一致性等级显式化（Glean 三档模式）；或做 last-mile 校验（Rovo）；或如 M365 一样提供 **Check user access** 抽查工具 |
| **F2** | **多源冲突且无权威源**：同一政策在 3 个文档里有 2 个版本，检索命中旧的那份，系统照答 | 没有"哪一份为准"的机制，排序把过期的排上来 | **事实（机制被官方承认）**：Rovo 把 "surface the **single sources of truth**, rather than just relevant pages" 作为独立卖点，反证问题存在；Glean 在评测里单独定义 **canonical document** 召回率，反证"召回对了权威源"是被单独度量的目标 | L0 权威源认定：每条知识必须有 owner + effective_from + supersedes |
| **F3** | **阈值随模型漂移**：换模型版本后，同一个阈值的行为改变，误报/漏报结构变化，但没人知道 | 阈值被当成常量 | **事实**：Perspective FAQ 原文——"**need to update that threshold when the models update**... Note that we are **not able to notify users each time an update is released**"（【官方·仅搜索摘要】） | 阈值自带"校准日期 + 对应模型版本"；模型升级触发回归 |
| **F4** | **护栏与主判定共享同一次调用**：护栏被同一次 prompt 里的长上下文稀释，或被同一个注入同时绕过 | 为了省一次调用而合并 | **事实**：OpenAI 官方——"a **prompt injection** attempt could be successful in evading **both your guardrail and your actual LLM call**"；"As conversations get longer, LLMs are more susceptible to **jailbreaking** as your instructions become **diluted** by the extra text"（`How_to_use_guardrails.ipynb`）；Anthropic 建议护栏独立调用 | 护栏独立调用；考虑"只看最新消息"；规则/传统模型混合 |
| **F5** | **过度收紧导致 over-refusal**：为提高安全性把护栏调紧，结果误杀正常请求，用户流失 | 只优化漏判、不度量误判 | **事实**：OpenAI 官方列出 **over-refusals** 为已知失效模式；Perspective 被第三方指出**单条孤立打分、不看语境**，因此反讽类误报高 | 用**混淆矩阵**分开度量；分级处置而非二值裁决（`[推断]`） |
| **F6** | **索引与搜索被绑成同一个开关**：想只排除 AI 检索范围，结果把人的搜索也关了 | 二者共用一套索引 | **事实**：M365 官方明确——没有"只排除 Microsoft Search **或**只排除语义索引"的选项，"actions apply to both at the same time" | 在设计期就把"谁能搜"与"AI 能读"当两个维度，而不是一个开关 |
| **F7** | **元数据缺失导致检索信号贫瘠**：只有正文没有结构化字段，检索只能靠语义近似 | 接入时把文档当纯文本 | **事实**：M365 的 SharePoint 列元数据"can be incorporated as signals during retrieval when a query is scoped to a specific library or folder"；Dust 的 label 双向过滤机制；Anthropic 指出文件名/目录/时间戳都是信号 | 把"字段"当检索一等公民：规则 ID、平台、品类、生效时间、处置等级 |
| **F8** | **评测被跳过，或评测覆盖大于实际覆盖**：检查恒真、指标算不出来，却对外宣称已评测 | 评测需要标注，标注需要业务专家 | **事实**：第 2 节六家中只有 Glean 公开到指标级，Microsoft/Notion/Sana/Dust/Salesforce **均未找到公开评测方法**；第 3 节五家里 Sierra / Harvey / Dragon Copilot / Abridge 公开到方法级，Decagon 公开到 benchmark 级（见各 `raw/` 底稿的未找到清单）。另注：本项目自身纪律明确"**检查不得断言固定措辞或固定数量**，废检查（恒真）比没有检查更坏" | 建黄金集 + 混淆矩阵；**每条检查必须配反向对照（抽掉配置要变红）** |
| **F9** | **图谱/结构化被当银弹**：为了"更准"上知识图谱，成本翻倍收益有限 | 把 GraphRAG 的适用场景误当通用场景 | **事实**：GraphRAG 论文自陈适用"**global sensemaking questions over datasets in the 1 million token range**"，提升的是 comprehensiveness 与 diversity；GraphRAG 索引"uses an LLM to build a graph index in two stages"，成本高。Mem0 论文显示图记忆相对非图版本只"around **2% higher overall score**"，而"有没有记忆层"带来的是"**26% relative improvements**" | 先问"我的问题是 local 还是 global"；逐条判定问题不需要图谱 |
| **F10** | **连接器内容不是"文本富集"就接入**：接进来但检索质量差 | 接入方按"能连上"而非"能检索好"验收 | **事实**：M365 官方——connector 方式"works best when the connector content is **text rich**" | 接入验收标准里加一条"可被检索到且语义可分辨"的反向测试 |
| **F11** | **把工具/知识全塞给一个 agent，触发模糊** | 以为"给得多=能力强" | **事实**：Anthropic 指出最常见失败模式是 "**bloated tool sets**... ambiguous decision points"，判据是"if a human engineer can't definitively say which tool should be used, an AI agent can't be expected to do better"；Dust 官方警告"agents that are plugged to a **constrained number of data** will usually perform better" | 按域切分 agent/知识源；把召回范围当超参 |
| **F12** | **Skill/知识包成为供应链攻击面** | 第三方 skill 可带脚本与外部网络访问 | **事实**：Anthropic 官方安全提示——"malicious skills may introduce vulnerabilities... or **direct Claude to exfiltrate data**"；建议"installing skills only from **trusted sources**"，并审计 code dependencies 与"instructions or code within the skill that instruct Claude to connect to potentially **untrusted external network sources**" | 知识库/技能目录要有准入与审计流程 |
| **F13** | **判定只有二值，导致中间档被"被迫二选一"**：平台承认存在"没到删、但该降流量"的处置，若系统只有合规/不合规，这一档要么被放过、要么被误杀 | 判定模型被简化成布尔值，而真实处置是分级的 | **事实**：Meta——"we'll often **reduce the distribution** of this content, **even when it doesn't quite meet the standard for removal**"；Amazon 四级处置（Remove / Limit / Suspend / **Withhold payments**）；TikTok 三态（`Attention Needed` / `Poor` / 停号）。见 §5 · C4.5 | 判定结果引入**处置等级**维度（通过 / 降权 / 否决），并让"降权"有独立的落库字段与复核口径——否则误杀与放过会被混在同一个"准确率"里互相掩盖 |
| **F14** | **申诉台账把"平台自撤"与"用户申诉翻案"合成一个数**：看不出纠错是主动的还是被推着做的 | 两者都是"翻案"，但改进含义完全不同 | **事实**：Meta 把二者**分列**为 `Content Restored with appeal` 与 `Content Restored without appeal`。`[推断]` 合并统计会掩盖"用户根本没来申诉"的真实状况——Meta 的申诉率仅为个位数百分比（§5 · C4.1） | 申诉台账分列两个字段；`Restored without appeal` 是"我们主动纠错"的唯一度量，应单独设定改进目标 |
| **F15** | **聚合层级选错，稳定地产生"看起来合理的错数"**：从多层级嵌套的官方数据集中按单一维度过滤，命中的却是不同粒度的行 | 数据集里每个维度都有自己的 `All` 汇总层 | **事实**：研究者本人在 TikTok CGER CSV 上复算时踩到——只锁 `Market=='All'` 时多行命中，算出"Jan–Mar 2026 翻案率 **52.97%**"这一荒谬值（正解为 4.80%）；Meta CSER 的 Facebook 申诉率若不剔除从不报申诉的 `Fake Accounts`，会得出 0.38% 的假值（正解 2.44%）。见 §5 · C4.1 / C4.2 | 取官方聚合数据时**逐维度断言全为 `All`**；每个派生比率都要回算分母的构成，并问一句"**这个分母里有没有根本不该出现在这里的量**" |

---

---

## 附：面向「守衡」的落地建议

> **本节的口径声明（先读这一段）**
>
> 1. 本节只写本工作区**真实存在**的文件、表、字段与数字。凡我没读到的，标 `[待确认]`；凡我提出但尚不存在的载体，一律标 **「建议·尚不存在」**。
> 2. **不编造文件名、字段名、脚本名。** 建议新建的名字是提案，不是现状，凡出现必带「建议·尚不存在」。
> 3. 本项目有一条硬纪律：**任何新声明 / 新字段 / 新工具都必须配反向对照 —— 抽掉配置后检查必须真的变红**；且检查**不得断言固定措辞或固定数量**。本节的每条建议都按这条纪律写验收，并在**本节第四节**统一说明反向对照怎么写。
> 4. 本节不重复外部调研结论，只把外部共识当作**对照标尺**使用：分层引用**本报告第 2 节**的六层词汇（连接器/语料层 · 索引/图谱层 · 取数模式层 · 权限层 · 行为层 · 评测层）与**第 3 节**垂直 Agent 的权限时点光谱（§3.6），三件套引用**本报告第 4 节**的「**规则库 + 案例库 + 误判申诉**」。本节的小节编号（一/二/三/四/五）与报告正文部分编号相互独立。

---

### 一、守衡现状的知识库分层速写

守衡的"知识库"不是一个库，而是**五组物理上分离、由 ADR 明文规定权威与方向的载体**。把它们并排摆出来，是这一节的全部目的。

#### 1.1 判定制品层 —— 引擎直读的本地 JSON（`research/governance/skeleton/`）

| 载体（真实路径） | 形态 | 扮演的角色 | 实测规模 |
|---|---|---|---|
| `skeleton/rules-v1.json` | JSON，手工维护 | **规则库主体**：判险词 + 规则 + 兜底通道，是**唯一产生命中的来源** | 26 条规则（enabled 25 / is_modifier 1 / 带 escalation 1 / catch_all 1） |
| `skeleton/whitelist-v1.json` | JSON | **放行词表**（机制分离第 1 处，ADR-0008）；豁免目标必须落 `auto_pass` 带 | 30 词（active 26 / 隔离 4） |
| `skeleton/context-guards-v1.json` | JSON | **语境守卫词表**（机制分离第 2 处，ADR-0009）；取消或弱化主张，**绝不放行** | 85 词（已接线 46 / 待法务定性 39）；与白名单重复登记 14 |
| `skeleton/disposition-layers-v1.json` | JSON，法务所有 | **处置分层映射**（DP0–DP4）：判定之后"谁必须看它" | 5 层 / 5 条映射 / 3 条升级（启用 2）；`status=ratified`，`decided_at=2026-09-16` |
| `skeleton/product-lines-v1.json` | JSON，产品所有 | **品线取值域**与规则→品线归属 | values 10 / placeholders 2 / **`rules_scoped = 0`**；`status=partially_confirmed` |
| `skeleton/topic-tree-v1.md` | Markdown | **主题树**，`Engine._validate_topics` 的校验基准 | 43 个节点 |
| `skeleton/legal-decisions-v1.json` | JSON，法务权威 | **决定与未决的唯一台账**（决定 28 条 + 决策队列 26 条），跨 engine / kb / repo 三条线 | D1 的「可申诉」拆三条义务：政策 met / 送达 met / **「已送达过」unmet** |
| `skeleton/engine-manifest.json`、`_data/manifest-history.jsonl` | JSON + JSONL | **制品版本manifest**：制品与代码的 sha256 + `engine_version`（内容哈希） | 现行 manifest 1 份；历史归档 10 条 |
| `skeleton/_data/records.json` | JSON | **冻结语料**（291 条），V13 的回归基线 | 291 条 × 33 字段，含人工 `风险等级` / `命中规则` 与派生 `_hit_rules` |
| `skeleton/_data/receipts.jsonl` + `receipts.chain.json` | JSONL + JSON | **判定回执账本**（append-only，V7e/V37 机检）＋前缀哈希链 | 现存 **1 条**（事故前 5 条，4 条不可重建，见 `receipts.LOSS.md`）；链 n=1 |
| `skeleton/_data/迁移保真度.json`、`风险等级-还原.json`、`rules_raw.json` | JSON | 迁移对账与上游 21 条现行规则的原始形态 | — |

#### 1.2 飞书权威源层 —— 人写主 Base（app 只读）

主 Base `Lk3Qb8y2QaVyZns6gprcVNE9nA0`。守衡 app 对它**读得通、写得 403 · code 91403**（实测见 `base/sync_rules.py` 文件头与 `skeleton/迁移手册-机器词表.md`）。

| 表名（真实） | table_id | 角色 | 实测条数（应用身份所见） |
|---|---|---|---|
| 广告文案明细 | `tblcbk4XiW6471YN` | **判定对象语料**与人工判定结果的落点 | 291 |
| 品线内容边界规则库 | `tblD1MiUK1v5fdjD` | **人写规则源**（21 条现行规则） | 21 |
| W1卖点表达边界 | `tblqUTAKFkWheU49` | 品线人工判断的结果：同一卖点的绿/黄/红三档 + 替换表达 + 映射规则 | 19 |
| 风险文案改写建议库 | `tblLxUfPz4Wqp2na` | 「出过的错 → 合规写法」映射 | 52 |

另有一个独立 Base `GnRZbIuXraCzf0sGr2UcmZ62nfc`「内容治理知识库」，承载业务侧定义的知识库载体：

| 表名（真实） | table_id | 角色 | 实测条数 |
|---|---|---|---|
| 内容治理知识库·材料收集 | `tblMGtPfe8ZUsEdP` | 材料登记（只记链接） | 15（其中可程序读取 4 / 不可读 11） |
| 内容治理知识库·正面和负面样本 | `tbld8qE92YaY38Yz` | **内部正负样本库**（业务侧 4 类知识库之一） | 8，其中 5 条备注写「样例」，**真实样本 0** |

#### 1.3 飞书机器词表层 —— app 自有 Base（app 可写）

机器词表 Base `B1oabL2veaFKbKs2hVAcvyKKnEe`「品线内容边界-机器词表」，含「语境守卫词」「白名单词」「词表分工说明」三张表。
权威方向与主 Base **相反**：这一侧是**本地 JSON 为准、推往飞书**，保证强度是 `policy`（纪律）而非 `physical`（权限）。参见 `base/sync_rules.py` 的 `enforcement` 字段。
`[待确认]`：`skeleton/迁移手册-机器词表.md`（2026-09-16）记「语境守卫词 89 行 / 白名单词 26 行」，而当前本地制品是 **85 / 30**（ADR-0012 的 D3 迁词所致）。飞书侧现值需实拉一次才能定；**在拉取之前，不要把 89/26 或 85/30 任一当作两侧一致的事实。**

#### 1.4 案例与错题层

| 载体（真实路径） | 形态 | 角色 | 实测状态 |
|---|---|---|---|
| `research/governance/errorbook/errorbook.csv` | CSV，25 列 | **错题本**：设计上承载 FP/FN 的唯一采集入口 | **177 行**；`人工复判结论` 0/177、`复判人` 0/177、`复判时间` 0/177、`处置码` 0/177、`处置人` 0/177、`处置日期` 0/177、`对抗手法` 0/177 |
| `research/governance/errorbook/errorbook_schema.md` | Markdown | 25 列字段定义与状态图 | 已写「`判定结果` 必须存在 `L0 未覆盖`」「`处置码` 四件套是把错题本变成规则生产原料的关键」 |
| `research/governance/errorbook/错题本.md` | Markdown | 错题本说明 | 存在 |
| `research/governance/05-内部证据-记录表分歧结构与错题本现状.md` | Markdown | 错题本现状的结构性审计 | §6.3 明确三个缺失连接：**记录表→人工结论**、**人工结论→规则修订**、**漏报的记录位置** |
| `research/kb/外部标准库-v1.json` | JSON | **条款级**外部标准（17 来源 / 62 条 / 7 个候选规则族） | `authority.ratifier = null`，62 条全部 `status=research`，**0 条经法务确认** |
| `_evidence/`（R1–R8） | 7000+ 抓取件 | 外部一手证据语料 | 附 `_KNOWN_MISLABELS.md` 已知错标索引（最后人工核对 2026-09-15） |

#### 1.5 评测、需求与运行时

| 载体 | 角色 | 实测 |
|---|---|---|
| `tools/verify_engine_contract.py` | **引擎契约验收器**，V 编号检查（V1 至 V45d 各组） | 实测 `check("V…")` 调用 **171 处**（唯一 id 数 = 调用数）；V13 断言 291 条存量语料的混淆矩阵逐项等于 `BASELINE = {precision 0.970, recall 0.962, f1 0.966}` |
| `base/verify_base.py` | **基座自证**，六个面 A–F（含 F 反向对照） | `base/README.md` 自报"41 + 26 + 20 + 26 + 19 项，含 20 条反向对照"。★ **这组数字是 README 自己的表述**，同文件另一处又写 `contract.py --selftest` 是"46 项检查 + 12 条反向对照"，两处不一致；引用具体项数前应先实跑一次 `python3 base/verify_base.py` |
| `tools/heldout_test.py` | **留出检验**（两组：改写建议库风险原句、W1 卖点建议表达）；三组对照 A 424 词 / B 60 词 / A∪B | 脚本自陈「留出集很小，只能定性，不能当统计结论」 |
| `tools/offline_replay.py` | 词表 vs 291 条人工判定的离线复现 | 自陈「是**词表 vs 人工判定**，不是机器 vs 金标准」 |
| `research/kb/知识库-v1.json` | 业务侧定义的 **4 类知识库**登记表（定义是抄的，现状是算的） | 外部标准库 / 内部正负样本库 / 措辞表达库 / 产品描述库 |
| `research/kb/缺口-v1.json` | 需求知识库线**全部缺口**登记（编号/影响哪条黄金问题/量/责任人/复算） | 16 条（D1–D16；kind 覆盖 data/access/classification/evidence/schema/process） |
| `research/kb/台账-v1.json`、`证据映射.json`、`索引-本地资产.json`、`覆盖报告.json` | 需求台账与"需求→证据"映射 | — |
| `base/contract.py`、`judge_adapter.py`、`media.py`、`text_stage.py`、`sync_rules.py` | 基座五面：进（ContentUnit）/ 判（judge(unit)）/ 供（权威源同步）/ 证（自证） | `ContentUnit` 含双指纹、H1–H14 不变量 |
| `tools/agent/tools.mjs`（守衡运行时） | 飞书内 Agent 的工具层 | **10 个工具**：`now` / `current_chat_info` / `list_chat_members` / `recent_messages` / `lookup_user` / `list_workspace` / `read_text_file` / `list_files` / `run_readonly_command` / `judge_copy`；**全文 0 处** bitable / app_token 引用 |

**一句话速写**：守衡在**判定侧**已经有一套远超同规模项目的知识工程（规则/白名单/守卫/处置分层/主题树五张表分离，双指纹版本化，append-only 回执账本，171 项契约检查 + 基座六面自证）；而在**回流侧**——案例、先例、人工结论、版本生效时间、评测集入集机制——几乎全是空壳或只有模板。**它的知识库不缺"判"，缺"记回来"。**

---

### 二、对照外部共识的缺口清单

> 记法：**每条 = 缺什么 → 会造成什么具体后果 → 建议补什么最小载体**。载体名后带「建议·尚不存在」的均为提案。
> 严重度按「后果是否静默」排序（本项目的既有判据：**一个静默的错比一个响的错坏**）。

#### G1 · 人工结论回流 **一行都没有落点**（最严重，且完全静默）

- **缺什么**：错题本 `errorbook.csv` 的 25 列 schema **设计上是对的**——`人工复判结论` 的四态含 `推翻-应判合规`（FP）与 `推翻-应判违规`（FN），并有 `处置码` + `关联规则编号` + `处置人` + `处置日期` 四件套。但实测**这 6 列填充率全部 0/177**。同时源表侧（广告文案明细）根本**没有承载人工结论的列**——`检查人` 列 0/291。
- **后果**：机器判得对不对，**在任何载体里都无法回答**。规则库的 precision/recall 只能来自 V13 冻结基线（0.970 / 0.962 / 0.966），**不能随时间积累**；一次人工改判不会改变任何数字，也不会产生任何待办。对照外部共识的"评测层"：这正是 Glean 之外多数产品只敢给"数字不给方法"的那一层，而守衡连数字都没有。
- **建议最小载体**：**不新建表**。把 `research/governance/errorbook/errorbook.csv` 的 6 个空列变成"有主人的列"，并落一份**谁填、多久填一次**的最小规程（建议落在 `research/governance/errorbook/回流规程·建议·尚不存在.md`）。
- **反向对照怎么写**：检查项不得断言"至少 N 行已填"（那是数量断言，会随语料爆炸或腐烂）。应检查**可逆性**：构造一条带 `推翻-应判合规` 的错题行 → 检查必须报出该规则的一条 FP 计数；**抽掉该行后同一个计数必须归零**。归不了零 = 检查是恒真的。

#### G2 · 假阴性在源表数据模型里**没有位置**

- **缺什么**：记录表只有"命中"，没有"应当命中但未命中"。05 号审计已把它列为"三个连接"中最严重的一个。**已发生的实例**：小语种漏检（规则表 424 个检测关键词里小语种词 0 个，而非英语文案占 28.2%）。
- **后果**：盲区率在**数学上不可观测**（错题本 schema 自己也写了这条：若"未命中"直接落到"合规"，盲区率不可观测）。守衡已有的 `catch_all` / DP0 是对的方向，但它只覆盖"引擎知道自己是兜底"的那部分；**人工在别处发现的漏放，没有任何地方可写**。
- **建议最小载体**：在 `errorbook.csv` 现有 25 列内**不加列**的前提下，用 `来源` 的既有取值 `人工复核` / `外部反馈` + `人工复判结论=推翻-应判违规` 表达 FN（schema 已支持）；真正缺的是一个**登记入口**——建议新增 `research/governance/errorbook/fn-登记·建议·尚不存在.jsonl`，每行至少含 `发现人 / 发现时间 / 原文指纹 / 应当命中的规则编号或'无规则可命中' / 是否对抗样本`。
- **反向对照**：构造一条 FN 登记 → 检查必须报出"该表达在语料中出现过但零命中"；**抽掉登记后必须回到"无此发现"**。注意不要断言"应当命中的规则编号非空"——`无规则可命中` 是合法且最有价值的取值（它指向规则生产，而不是规则修订）。

#### G3 · 案例库 / 先例库**没有结构化载体**（只有条款级）

- **缺什么**：外部标准库 `research/kb/外部标准库-v1.json` 是**条款级**条目（字段是 `条款位置` / `条款原文` / `关联规则`），62 条、**0 条 ratified**。而"上一次同类表达是怎么裁的"这一类**案例级**知识，散落在 `_evidence/` 的 7000+ 抓取件里——那是**调研证据**，不是可被工具引用的先例库，且已确知含错标（`_KNOWN_MISLABELS.md`）。
- **后果**：守衡能说"这条规则依据哪条条款"，**不能说"同类表达上次判了什么、结果如何"**。对照外部共识的"案例库"一件套，守衡有"规则库"，缺"案例库"。
- **建议最小载体**：建议新增 `research/kb/先例库-v1.json`（**建议·尚不存在**），与 `外部标准库-v1.json` **同构**（沿用其 `id` / `status` / `source_id` / `适用渠道` / `适用品线` / `关联规则` / `未确认标记` 的写法），新增最小字段集建议为：`案例来源`（平台裁定 / 内部复判 / 达人争议）、`裁定结果`、`依据条款`、`与规则的映射`、`是否可外发`。
- **反向对照**：抽掉一条先例 → 引用它的判定输出中该先例引用必须消失。**不要断言"先例库条数 ≥ N"**。

#### G4 · 规则版本**只有内容指纹，没有生效时间与批准人**

- **缺什么**：`rules-v1.json` / `whitelist-v1.json` / `context-guards-v1.json` 三个文件内**没有** `decided_at` / `effective_from` / `decided_by` 字段（对照：`disposition-layers-v1.json` 有 `decided_at`、`legal-decisions-v1.json` 有 `answered_at`）。版本以内容哈希形式存在（回执里是 `rule_version: rules@0ab7c81dbf14`），历史归档在 `_data/manifest-history.jsonl`（10 条）。
  ★ **这条缺口在本项目已被正式立案，只是还没结案**：`ADR/ADR-0002-记录级溯源与版本化.md` 状态是 **`proposed`**，其背景逐字写着「没有链接、没有版本号、没有条款号、**没有生效日期**」，并给出三条实测证据（21 条规则的 `依据来源` 取值只有 3 种且全是文件名；291 条记录里 2 条引用不存在的规则编号 `EMPTY`；`适用产品` 字段 21/21 被写死成同一常量而"**没有任何机制记录这个字段何时被谁改过**"）。所以本节不是新提法，而是**把一条已立案的 ADR 从 `proposed` 推向可验收**。
- **后果**：三类具体问题**不可答**：① "这条规则从哪天起有效"，② "6 月那次误拦当时用的是哪一版规则"（哈希能对，但**哈希→语义版本→生效区间**的映射没有），③ 平台政策更新后"我们晚了几天"的合规叙事无法举证。`manifest-history.jsonl` 是**制品指纹的采样**，带 `generated_at` 与 `$archived_at`，但**不含谁批的、何时生效、何时失效**。
- **建议最小载体**：建议新增 `skeleton/rule-changelog-v1.json`（**建议·尚不存在**），每条至少 `version_label / effective_from / effective_to(null=现行) / approved_by / approved_at / 制品 sha256 / 触发它的决定编号（指回 legal-decisions-v1.json 的 `id`）`。`approved_by` 必须能指回法务或 Owner，否则这条记录只剩装饰。
- **反向对照**：抽掉某版本区间 → 检查必须报出"该回执的 `rule_version` 落在无覆盖的时间段"。**不得断言版本条数或版本号格式**；断言的是**每个回执的 `rule_version` 都能被 changelog 覆盖**（覆盖性是关系，不是数量）。

#### G5 · 上游引用是「声明」不是「证明」

- **缺什么**：`engine-manifest.json` 的 `upstream.integrity` 值是 **`declared`**，其 note 逐字写着：whitelist / context-guards 里有 `source.snapshot` 文件名，**`rules-v1.json` 连文件名都没有**，"把它们当证明用等于把声明洗成证明"。
- **后果**：`rules-v1.json` 的真正上游是 **`PRD/内容治理需求文档.md`**（`build_rules.py` 读 PRD，不读飞书），而 PRD 是一份 L1 人工文档。于是存在一条**双向静默**路径：在飞书改规则 → PRD 不变 → 引擎用的是 PRD → **改动静默不生效**；改 PRD → 飞书不变 → **权威源与实际不符而无人知晓**。
- **建议最小载体**：不新建。把已建成的 `base/sync_rules.py --verify`（离线：本地制品 vs 最近快照）真正接进例行检查——见 **G10**。
- **反向对照**：`sync_rules.py --selftest` 已有 2 条必红；新增的接线检查须断言"**抽掉一次快照后 `--verify` 必须非零退出**"，而不是断言它输出某句固定文案。

#### G6 · 评测：**有冻结语料，没有"入集"机制与分开统计的口径**

- **缺什么**：三处资产都存在但互不连通——① `_data/records.json`（291 条冻结语料，V13 断言混淆矩阵 **完全等于** 基线）；② `tools/heldout_test.py` 的两组留出集（自陈"很小，只能定性"）；③ `errorbook.csv` 里 `来源=对抗测试` + `对抗手法` 的设计入口（填充率 0/177）。**没有任何机制把新发现的 case 送进评测集**，也**没有"误报率与漏放率分开报"的口径**（外部共识明确要求分开，而不是一个总分）。
- **后果**：V13 的"逐项等于基线"是**防劣化**的好机制，但它同时意味着：**基线一旦冻结就再也不会变好或变坏**，新发现的 100 个错例不会让它动一格。评测层于是停在"回归"这一半，"改进"那一半是空的。
- **建议最小载体**：建议新增 `skeleton/_data/eval-set-v1.json`（**建议·尚不存在**），每条含 `case_id / 输入指纹（复用 ContentUnit 的 text_sha256）/ 期望 verdict（或显式「不判」）/ 来源 / 敏感度分级 / 入集日期 / 由哪条错题转入`；并在验收器里加一组检查（可命名 V46x），**分开报** `误报数 / 漏放数 / 无规则可命中数` 三路。
- **反向对照**：每条期望值都必须能"抽掉即红"——抽掉一条期望 → 该 case 必须落回"无期望"状态且检查报出覆盖缺口。**严禁断言"评测集条数 = N"或"准确率 ≥ X%"**：前者是固定数量，后者是阈值，两者都会把"评测集没更新"伪装成"评测通过"。

#### G7 · 申诉**只有出口，没有归途**

- **缺什么**：申诉的政策与送达管道都已落地（`legal-decisions-v1.json` 的 D1-O3a / D1-O3b 均 `met`，`tools/push_receipts.py` 负责推送），但 **D1-O3c「已送达过」仍 `unmet`**；更关键的是：申诉的**结果**（撤销 / 维持）落回哪里，**没有载体**。回执账本是 append-only 的**判定**账本，`push_receipts.py` 只推不收回。
- **后果**：被误拦的人真的申诉了、也真的撤销了——**这次撤销不会变成规则修订的输入，也不会更新误报率**。这正是 ADR-0012 自己写下的那句：「**写了申诉方式 ≠ 被误拦的人能申诉**」，可以再往下推半句：**能申诉 ≠ 申诉会被记账**。
- **建议最小载体**：建议新增 `skeleton/_data/appeals-v1.json`（**建议·尚不存在**）或 `appeals-v1.jsonl`，每条 `申诉 id / 原回执 run_id / 提交人（可路由）/ 提交时间 / 结论（撤销|维持|部分）/ 结论人 / 撤销依据 / 是否已回流为错题`。同时按既有纪律，**撤销不得覆盖原判定**，只能作为一条新记录追加（与回执账本同构）。
- **反向对照**：抽掉一条已撤销的申诉 → 该规则上的"误拦已确认"计数必须归零。**不要断言"申诉条数 ≥ 1"**：`D1-O3c` 现在是 unmet，把"至少一条"写成硬检查会让检查长期是红的——那是另一种恒真。正确做法是**把 unmet 状态显式报出来**（本项目已有范式：`--status` 单独计数并打印旧回执）。

#### G8 · 品线维度**声明了但一条没填**

- **缺什么**：`product-lines-v1.json` 的 `rules_scoped = 0`；`judge_copy` 工具的描述逐字承认"**当前规则库没有品线字段，它只进回执，不改变判定**"。同时 `research/kb/知识库-v1.json` 记 `lex_lines_covered = 1 / lex_lines_total = 8`，`缺口-v1.json` 的 D6 记"七个品线族零证据"。
- **后果**：跨品线**同形异义**无法处理（`tools/measure_cross_line_homographs.py` 的存在说明这个问题已被识别），且判定的品线参数是**装饰性的**——传进去只进回执。对照外部共识的"权限层/范围层"：守衡有范围概念，没有范围生效。
- **建议最小载体**：**字段已存在**（`assignments` / `rules_scoped` / 每条规则的 `product_lines` 过滤机制已按 ADR-0012 建成），缺的是**数据录入**，不是新载体。落地动作 = 填 `assignments`，并解决 `$placeholders_excluded` 里那 2 个占位值。
- **反向对照**：V17 已经是"品线维度机制必须是活的"这一组，保留其思路——**构造一条带 `product_lines` 声明的规则 → 判定必须真的改变；抽掉声明 → 必须回到不过滤**。**不得断言"已填 N 条"**。

#### G9 · 守衡在飞书里**读不到自己的知识库**

- **缺什么**：`tools/agent/tools.mjs` 的 10 个工具全部是 `now` / 群信息 / 成员 / 最近消息 / 用户查找 / 工作区文件读取 / 只读命令 / `judge_copy`。**0 处** bitable / app_token 引用。而白名单、语境守卫、错题本、改写建议库（52 条）**都在飞书里**。
- **后果**：守衡能判，但**不能回答"这个词为什么被放行""有没有替代表达""上次这条是怎么改的"**。`风险文案改写建议库` 的 52 条在飞书源表、**本地未落盘**（`知识库-v1.json` 逐字记着），所以 `read_text_file` 也读不到它。这直接削弱了「措辞表达库」这一类知识库的可用性。
- **建议最小载体**：建议新增**只读**工具 `lookup_vocab` 与 `lookup_rewrite`（**建议·尚不存在**），沿既有 `scope: 'read'` 的写法，并遵守 `lookup_user` 那套"**来源 / 理由**"返回结构（`{ value, source, reason }`），使每个回答都能被追问出处。
- **反向对照**：**抽掉该 Base 的读取授权 → 工具必须结构化报错，而不是返回空列表**。这条是必须的：本项目已经反复踩过"静默空"（"待送 0 可能是假安静"、"自证写了 ≠ 自证被跑"）。空与读不到**必须长得不一样**。

#### G10 · 上游漂移检查**存在，但没有东西在跑它**

- **缺什么**：`base/sync_rules.py --verify`（离线：本地制品 vs 最近快照）已交付且自证全绿（20 项，含 2 条必红）。但 `base/verify_base.py` 的 A 面只调各模块的 `--selftest`——**`--verify` 不在任何自动路径上**。
- **后果**：G5 那条双向静默路径**依然敞着**。这个形状在本项目已被命名过两次：B2 修的就是"A 面原本漏了 `media.py` —— 自证写了，但没有任何东西会去跑那 20 项，而漏掉的后果是静默的"。
- **建议最小载体**：不新建。把 `sync_rules.py --verify` 接进 `base/verify_base.py` 的 A 面或新增一面，**并沿用 B2·A 那套"清单 vs 自动发现双向对照"**——只加一行调用而不加双向对照，等于把同一个洞留在原地等下一次。
- **反向对照**：**篡改一次本地制品的 sha256（或抽掉最近快照）→ 该面必须非零退出**。同时保留"清单与自动发现双向无差"这条元检查，防止将来新模块重演 media.py。

#### G11 · 业务侧 4 类知识库：**2 类实际为空**

- **缺什么**（`research/kb/知识库-v1.json`，定义是抄的、现状是算的）：外部标准库 62 条但 **ratified 0**；内部正负样本库 **真实样本 0**（8 条里 5 条写"样例"，且**落盘件自相矛盾**：抬头声明 8 / 盘上 5）；措辞表达库**只覆盖 1/8 品线**；产品描述库 5 条材料登记、**可程序读取 0 条**（权限错误）。
- **后果**：这四类里，**只有"措辞表达库"是有货的**（规则 26 + 白名单 active 26/30 + 守卫 85 已接线 46）。其余三类在飞书里看起来存在，实际贡献为零——而 `知识库-v1.json` 的 `$note` 已经点名了这个病："**把空写成「进行中」是这套知识库最容易犯、也最难被发现的错**"。
- **建议最小载体**：不新建。沿用 `缺口-v1.json` 的既有形状（编号 / kind / why / 量 / 责任人 / 复算命令），把已修好的 D7（正负样本落盘件自相矛盾）与 D8（62 条 0 ratified）**保持为红**，直到真的被填。
- **反向对照**：`tools/verify_kb.py` 的 E 组已在守"任何一类的本地现有条目都必须能在 `kb_classes.py` 的 `status_rows()` 里重算出来"。新增任何"补齐"声明时，**抽掉源数据后该类的计数必须真的变 0**——否则是把声明洗成了证明。

#### G12 · 知识来源的**权限一致性等级**从未被声明（外部调研直接产出的缺口）

- **缺什么**：守衡的知识库有两个物理位置——**本地 JSON 制品**（`research/governance/skeleton/`）与**飞书 Base**（`research/live/snapshot-*.json` 记录的 6 个源）。但**没有任何一处写明**：当**飞书表的可读范围发生变化**（换了 owner、撤了协作者、表被移出文件夹）时，本地那份是"同步时求值一次的**快照**"，还是"每次判定时向飞书**现问**"。**这个选择目前是被默认掉的，不是被决定的。**
- **为什么这是缺口（外部对照）**：本次调研发现，**十二家案例全部把权限当一等维度，但"生效时刻"横跨三个数量级**——Microsoft 官方原文是 "Permissions updates occur during a **full crawl, not an incremental crawl**"、最长 **24 小时**；Glean 把它做成可配置的 **Indexed / Live / Hybrid** 三档；Atlassian 官方原文是 **"last-mile checks"**（交付前最终校验）；Harvey 官方原文是 **"The agent has the same permissions as the user"** + **fail closed**。**没有一家是"没想过这个问题"的**；差别只在它们各自**显式声明**了自己属于哪一档。详见本报告 §2.0.1（六家对照表）与 §3.6（五家对照表）。
- **后果**：① 若上游飞书权限收紧而本地仍是旧快照，守衡会**用已经无权读到的知识去判定**，且**错误是静默的**；② 反过来，若每次都现问飞书，则**判定延迟与失败面**都会上升，而这一点同样没被度量。**两种后果都不会让任何一条现有检查变红**——这正是它属于缺口而非 bug 的原因。
- **建议最小载体**：**不新建文件**。在 `skeleton/engine-manifest.json` 的 `upstream` 段现有字段旁边，加一个显式枚举 `permission_consistency`（取值形如 `snapshot@sync` / `hybrid` / `live@query`），并在**每条判定记录**里写下本次实际生效的是哪一档 + 求值时刻（对齐 ADR-0002 的记录级溯源要求）。**建议·尚不存在**，字段名待与 ADR 对齐。
- **反向对照**：`tools/verify_engine_contract.py` 新增一条断言：**判定记录里必须出现 `permission_consistency` 与求值时刻**；然后把 manifest 里该字段**抽掉** —— 断言必须**真的变红**。若抽掉后仍然全绿，说明这条检查是恒真的废检查（比没有检查更坏）。
- **`[待确认]`**：飞书自身的权限变更是否有可订阅的事件/时间戳可用，我**没有验证**——这决定了 `live@query` 这一档是否工程可行。**这不是我能在本报告里替你决定的。**

---

### 三、一条最小演进路径

排序原则（沿用本项目既有判据）：**先做"已经建成但没被跑"的，再做"设计好了但没落点"的，最后才做"要新建载体"的**。理由很直接——前两类的边际成本接近零，而第三类每一项都要人。

#### 阶段 0 · 把已经建成的东西真的跑起来（零新建，1 人日）

| # | 动作 | 验收标准 |
|---|---|---|
| 0.1 | 把 `base/sync_rules.py --verify` 接进 `base/verify_base.py`（G10） | `python3 base/verify_base.py` 一条命令里包含上游漂移检查；**抽掉最近快照 → 必须非零退出** |
| 0.2 | 拉一次机器词表 Base 实况，与本地 85/30 对账（本节 1.3 的 `[待确认]`） | 两侧逐词差异被打印出来（"仅本地 N / 仅飞书 M / 字段不符 K"），**任一侧有差异不得静默通过** |
| 0.3 | 为 `errorbook.csv` 的 6 个空列指定**填写责任人**（不是填写内容） | 责任人必须落到**具体的自然人**，不接受团队名或角色名兜底；**"没人负责"必须与非零退出区分得开**（沿用 `push_receipts.py` 的"未映射即硬失败"） |

> 阶段 0 不做任何判断，只做**接线**。它的价值是把三条"存在但静默"的路径变成"存在且会响"。

#### 阶段 1 · 回流闭环的最小一步（G1 + G2，1–2 周）

| # | 动作 | 验收标准 |
|---|---|---|
| 1.1 | 让**第一批** 20–30 条错题真的被人复判并落库（`人工复判结论` + `复判人` + `复判时间`） | 不检查"填了多少行"；检查**抽掉这批行后该规则的 FP/FN 计数归零**（可逆性） |
| 1.2 | 建 `fn-登记·建议·尚不存在.jsonl`（G2），把已知的假阴性（如小语种漏检）先写进去 | **抽掉一条登记 → "该表达出现过但零命中"的报出必须消失**；`无规则可命中` 必须是合法取值 |
| 1.3 | `处置码` 四件套（处置码 / 关联规则编号 / 处置人 / 处置日期）打通一条**真实**链路：复判结论 → 规则修订 | 一条规则真的因为一条复判结论被改了，且 `legal-decisions-v1.json` 里能查到对应条目；**台账说改了而制品没改，或制品改了而台账没记，都必须红**（沿用 V20 的思路） |

> 阶段 1 结束后，守衡第一次拥有**能随时间变化的精度数字**。这是整条路径上唯一不可跳过的一步。

#### 阶段 2 · 版本与生效时间（G4 + G5，2–3 周）

| # | 动作 | 验收标准 |
|---|---|---|
| 2.1 | 建 `skeleton/rule-changelog-v1.json`（建议），先只补**现行版本的 `effective_from` + `approved_by`**，不追溯历史 | 检查断言的是**覆盖性**：每条回执的 `rule_version` 都能被某个区间覆盖；**不断言条数与格式** |
| 2.2 | 让 `rules-v1.json` 的上游指向**唯一权威源**（要么 PRD，要么飞书，不能两个都算） | 构造一次单侧修改 → `sync_rules.py --verify` 必须报"待同步"或"冲突"，**退出码区分方向**（pull 源报待同步 / push 源报冲突，既有设计已在） |
| 2.3 | 把 `engine-manifest.json` 的 `upstream.integrity` 从 `declared` 升到可复算，或**保持 `declared` 并在每次验收时打印它** | 无论升不升，**"声明"与"证明"必须在输出里长得不一样**；不许静默按证明处理 |

#### 阶段 3 · 评测集入集机制（G6，与阶段 1 并行即可）

| # | 动作 | 验收标准 |
|---|---|---|
| 3.1 | 建 `skeleton/_data/eval-set-v1.json`（建议），先只放**阶段 1 里那批已复判的错题** | 每条 case 的输入指纹复用 `ContentUnit` 的 `text_sha256`（**不再造第二套指纹**） |
| 3.2 | 在验收器里加一组检查，**误报 / 漏放 / 无规则可命中 三路分开报** | 三路各自可被单独抽掉并变红；**严禁断言准确率阈值** |
| 3.3 | 保留 V13 的"逐项等于基线"，但把基线**改为可从 eval-set 重算** | 基线不再是硬编码常量；**重算不出基线时必须红**，而不是自动采用新值 |

#### 阶段 4 · 案例与先例层（G3 + G7，视人力排期）

| # | 动作 | 验收标准 |
|---|---|---|
| 4.1 | 建 `research/kb/先例库-v1.json`（建议），与 `外部标准库-v1.json` 同构；**首批只放平台裁定里最贵的 5–10 个** | 先例可被判定输出引用；**抽掉一条先例 → 引用消失** |
| 4.2 | 建 `skeleton/_data/appeals-v1.json`（建议），先把 `D1-O3c` 从 `unmet` 变成"有过一次真送达" | **撤销只能追加、不能覆盖**（与回执账本同构）；`--status` 必须单独打印"仍未被送达过"的计数 |
| 4.3 | 把 `errorbook.csv` 的 `来源=外部反馈` 与 `对抗手法` 两处设计入口真正用起来 | 抽掉一条外部反馈 → 对应规则的"外部反馈计数"归零 |

#### 阶段 5 · 让守衡读到自己的知识库（G9，可早可晚）

| # | 动作 | 验收标准 |
|---|---|---|
| 5.1 | 加只读工具 `lookup_vocab` / `lookup_rewrite` | **抽掉 Base 授权 → 结构化报错，不返回空列表**；返回结构带 `source` 与 `reason`（沿用 `lookup_user` 的形状） |
| 5.2 | 把 `风险文案改写建议库` 的 52 条落一份本地投影 | 投影与飞书不一致时**必须报出**，不得静默取一边（沿用 ADR-0013 的"单向 + 指纹 + 冲突报错"） |

---

### 四、反向对照怎么写（本项目纪律的统一落地）

这一节的纪律来自项目记忆，不是我的发明：**任何新声明 / 新字段 / 新工具都必须配反向对照 —— 抽掉配置后检查必须真的变红**，且**检查不得断言固定措辞或固定数量**。落地时按这四条写：

1. **反向对照必须真的能动。** 本项目已有一次教训：某条反向对照"什么也没抽掉"，因为那一项本来就是 `False`，于是检查报了绿——**它证明的是自己没坏**。抽掉的动作若没有产生任何变化，该反向对照本身必须报红。
2. **不得断言固定数量。** 不写"错题本至少 N 行已复判""先例库 ≥ N 条""申诉 ≥ 1 条"。数量断言会随语料增长而腐烂，或在数据为空时长期假红。要断言**关系**：可逆性（抽掉即归零）、覆盖性（每条回执的版本都被 changelog 覆盖）、双向无差（清单 vs 自动发现）。
3. **不得断言固定措辞。** 不写"输出里必须含『已通过』字样"。要断言**结构差异**：能种状态与不能种状态必须在返回结构上不同（错误 vs 空），"声明"与"证明"必须在输出里长得不一样。
4. **空与读不到必须长得不一样。** 本项目反复踩过"静默空"：`待送 0 可能是假安静`、`自证写了 ≠ 自证被跑`、`batch_create 跑第二次把整张表翻倍而两次输出全是 ✅`。任何新增的读取路径都必须区分**"确实没有"**与**"我没读到"**，并对后者非零退出。

---

### 五、`[待决策]` 项（我不替你决定）

| # | 待决策 | 为什么要人来定 | 影响面向 |
|---|---|---|---|
| Q1 | 错题本的 6 个空列**由谁填、多久填一次**？ | 05 号审计的 Q1/Q4 至今未答；这决定"建流程"还是"建回流入口" | G1 / 阶段 1 全部 |
| Q2 | 内部**正负样本库**的样本**是否可外发、是否需脱敏**？ | 业务侧待收集问题里的原话；决定样本能不能进评测集 | G6 / G11 / 阶段 3 |
| Q3 | `rules-v1.json` 的**唯一权威源**是 PRD 还是飞书？ | 现在两个都能改，且改动都可能静默不生效 | G5 / 阶段 2.2 |
| Q4 | 规则版本要不要**语义版本号**，还是接受内容哈希 + changelog 区间？ | 前者要人维护、后者要工具覆盖；两种成本不同 | G4 / 阶段 2.1 |
| Q5 | `legal-decisions-v1.json` 里 **D1-O3c「已送达过」**何时转为 met？ | 它现在明确是 `unmet`，且是"申诉三件套"的最后一环 | G7 / 阶段 4.2 |
| Q6 | 机器词表 Base 与本地 JSON 的 **85/30 vs 89/26 差异**以哪侧为准？ | 我没有实拉飞书，不能替你判 | 阶段 0.2 |
| Q7 | 新增的只读工具**是否放开给全体群成员**，还是先只给审核员？ | 涉及权限，本项目规格是"一次一点给" | G9 / 阶段 5.1 |
| Q8 | 评测集里的 case **是否含敏感原文**？ | 与 ADR-0003（敏感样本分级准入）、ADR-0013（仓库三层分级）的关系需 Owner 判定：是否相容、以哪条为准 | G6 / 阶段 3.1 |

---

### 附 A · 我读过的文件清单（真实读取，非目录猜测）

**项目规则与决策**
- `ADR/README.md`（决策台账 + 决策地图，读了全文前 100 行）
- `ADR/ADR-0002-记录级溯源与版本化.md`（前 40 行；G4 的依据）
- `base/README.md`（基座五面与 ContentUnit 字段/不变量 H1–H14，读了前 100 行 + 局部 grep）

**判定引擎制品（`research/governance/skeleton/`）**
- `engine-manifest.json`（全文）
- `rules-v1.json`（顶层结构 + `$note` + 首条规则全字段）
- `whitelist-v1.json`（顶层结构）
- `context-guards-v1.json`（顶层结构 + `stats` + `source` + 首词全字段）
- `disposition-layers-v1.json`（顶层结构与关键字段）
- `product-lines-v1.json`（顶层结构与关键字段）
- `legal-decisions-v1.json`（顶层结构 + 首条决定全字段 + 前 3 条队列项 + `$note` 全文 + 全部 obligations 状态）
- `迁移手册-机器词表.md`（前 45 行）
- `_data/receipts.LOSS.md`（全文）
- `_data/receipts.jsonl`、`_data/receipts.chain.json`、`_data/manifest-history.jsonl`（结构 + 首末条）
- `_data/records.json`（条数与字段名）

**验收与自证**
- `tools/verify_engine_contract.py`（V 组标题全表、V13 全文、V38 全文、V1–V12 抽样、`BASELINE`）
- `base/verify_base.py`（`face_A` 全文、A–F 面清单）
- `base/sync_rules.py`（文件头 80 行）
- `tools/heldout_test.py`（文件头 40 行）
- `tools/offline_replay.py`（文件头 35 行）

**错题本与审计**
- `research/governance/errorbook/errorbook_schema.md`（前 120 行）
- `research/governance/errorbook/errorbook.csv`（表头 + 逐列填充率实算 + 来源分布实算）
- `research/governance/05-内部证据-记录表分歧结构与错题本现状.md`（§6 全文，第 285–389 行）
- `research/governance/_evidence/_KNOWN_MISLABELS.md`（前 50 行）
- `research/governance/_evidence/_citation_miss_attribution.md`（前 25 行）
- `research/governance/README.md`（前 60 行）

**需求知识库与飞书实况**
- `research/kb/知识库-v1.json`（全文）
- `research/kb/缺口-v1.json`（全文前 5000 字符 + 全部 D 编号与标题）
- `research/kb/外部标准库-v1.json`（顶层结构 + 首条条目全字段 + `authority` + `覆盖声明`）
- `research/live/snapshot-20260916T050845Z.json`（`note` + 6 个 source 的 label / app_token / table_id / 条数）
- `tools/kb_index.py`、`kb_query.py`、`kb_gaps.py`、`kb_facts.py`、`kb_evidence.py`、`kb_classes.py`、`kb_snapshot.py`、`kb_analyze.py`、`kb_build.py`（各自文件头 docstring）
- `tools/migrate_vocab_to_lark.py`、`migrate_whitelist_to_lark.py`、`migrate_kb_to_lark.py`（常量扫描：APP_TOKEN / TABLE / TABLE_NAME）

**运行时**
- `PMO/守衡-架构说明.md`（前 120 行）
- `tools/agent/tools.mjs`（`register()` 全表 + `judge_copy` 全文）
- `tools/push_receipts.py`（文件头 40 行）

**对照用的同批产物（只读标题，未引用其结论）**
- `kb2agent-research/Kb2Agent-方法论调研报告.md`（标题结构）
- `kb2agent-research/raw/A-part1.md`（§2.0 分层对照总表）
- `kb2agent-research/raw/B-part1.md`、`C-part1.md`（标题结构 + C1 对照表）

**外部调研的全部一手底稿（本报告第 2–5 节的每一条外部事实都出自这里）**

| 文件 | 内容 | 行数 |
|---|---|---|
| `kb2agent-research/raw/A-企业知识助手案例.md` | 企业知识助手 / 垂直 Agent 共八家的逐条证据与 URL | 469 |
| `kb2agent-research/raw/_sub-cx-vertical.md` | Sierra / Decagon / Harvey 一手调研（逐条列出打开过的 URL） | 624 |
| `kb2agent-research/raw/_sub-health.md` | Abridge / Dragon Copilot（原 Nuance DAX）一手调研 | 700 |
| `kb2agent-research/raw/_sub_legal.md` | Harvey 法律侧补充材料 | 484 |
| `kb2agent-research/raw/B-part1.md` · `kb2agent-research/raw/B-part2.md` · `kb2agent-research/raw/B-part3.md` | 「知识 → Agent」方法论（Anthropic / 记忆分层 / GraphRAG / 编排模式） | 235 |
| `kb2agent-research/raw/C-part1.md` · `kb2agent-research/raw/C-part2.md` | 合规审核三件套（OpenAI Moderation / Perspective API） | 163 |
| `kb2agent-research/raw/D-part1.md` | 失败与踩坑复盘 | 132 |
| `kb2agent-research/raw/E-守衡落地建议.md` | 本报告「附」章的底稿（缺口 G1–G11 + 演进路径） | 330 |
| `kb2agent-research/raw/F-part1.md` | 补充检索 | 111 |
| `kb2agent-research/raw/_sub_ads.md` | Meta / TikTok / Amazon 广告与上架合规一手证据 | 472 |
| `kb2agent-research/raw/_sub_legal.md` | Harvey 法律侧一手证据（与 `_sub-cx-vertical.md` 有重叠） | 484 |
| `kb2agent-research/raw/_sub_medical.md` | Abridge / Dragon Copilot 医疗侧一手证据 | — |
| `kb2agent-research/raw/_distill-legal.md` | 法律支蒸馏（插入位置映射 + 逐字引文 + 诚实边界） | 25.0KB |
| `kb2agent-research/raw/_distill-medical.md` | 医疗支蒸馏 | 34.2KB |
| `kb2agent-research/raw/_distill-ads.md` | 平台侧执法与申诉蒸馏（**含对本报告两处结论的更正**，见 §3.6.3 / §5 · C4） | 26.5KB |

> **⚠️ 引用优先级声明**：上述底稿中的若干"未找到公开资料"结论，与项目内 `research/governance/_evidence/R1/`、`R4/` 的**已存证据存在重叠**，且经复核**有数处属于"检索失败被误判为事实缺失"**（详见 §1.1 与 §5 · C4）。**凡底稿"未找到"与项目内已存证据冲突时，一律以项目内 `_evidence/` 的原文为准。**

> 这些底稿里逐条标注了 `已打开` / `[仅搜索摘要，未打开]` / `[子代理已打开，主代理未复核]` / `[推断]` / `未找到`。**本报告正文只采用其中"已打开"的部分**；凡未打开的，正文里都保留了同样的标注。**未找到的项一律如实列出，没有做任何记忆性补写。**

### 附 B · 结论来源分级

**完全基于真实文件（可直接引用）**
- 第一节 1.1–1.5 的全部条数、表名、table_id、Base token、工具名、字段名与填充率
- `errorbook.csv` 的 6 列 0/177、来源分布、等级分布（我逐列实算）
- `context-guards-v1.json` 的 85 / 46 / 39 / 14 与 `by_type`、`by_lang` 分布
- `product-lines-v1.json` 的 `rules_scoped = 0`
- `engine-manifest.json` 的 `upstream.integrity = "declared"` 及其原文说明
- `legal-decisions-v1.json` 的 28 条决定 + 26 条队列 + D1 三条义务状态
- `verify_engine_contract.py` 的 `BASELINE` 三个数值与 V13 逐项相等断言
- `tools/agent/tools.mjs` 的 10 个工具名与"0 处 bitable 引用"
- `base/verify_base.py` 的 A 面只跑 `--selftest`、不跑 `sync_rules.py --verify`

**基于真实文件 + 我的推断（引用时请保留"推断"标记）**
- G1「回流一行都没有落点」的**后果**推断：schema 正确但填充为 0 ⇒ 精度数字不能随时间积累。前半句是事实，后半句是我从"V13 基线是硬编码常量"推出的。
- G6「基线冻结 ⇒ 只会防劣化、不会改进」：这是我的推断，依据是 V13 的 `got == BASELINE` 断言形式。
- G9「守衡读不到知识库」：工具清单是事实；"因此它答不了『为什么放行』"是合理的功能推断，但我**没有实跑**守衡问它这个问题。
- G11「只有措辞表达库有货」：四类库的计数是事实；"有货/为空"的判断是我对这四个计数的解读。
- 阶段划分与工作量（1 人日 / 1–2 周 / 2–3 周）：**我的估计**，不是项目里已有的排期。

**明确标注为未读到 / 未验证**
- 飞书机器词表 Base 的**当前实际行数**（`[待确认]`，见 1.3）——我只有 `迁移手册`（2026-09-16，89/26）与本地制品（85/30）两个不一致的值，**没有实拉飞书**。
- 主 Base 各表的**真实总量**：`research/live/snapshot-*.json` 的 `note` 逐字声明"全部数字都是**应用身份**所见的数字，不是表的真实总量"。本节所有飞书条数都带这个限定。
- 内部正负样本库的**真实条数**：落盘件自相矛盾（抬头 8 / 盘上 5），`缺口-v1.json` 的 D7 明确写着"在重新拉取之前不许把 8 当成事实"。我照此处理。
- 守衡线上**是否真的有人用过申诉通道**：`D1-O3c` 记 `unmet`，我按 unmet 处理，未做独立验证。
