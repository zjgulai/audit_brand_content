## 5. 案例族 D：公开的失败与踩坑复盘

> **本节证据强度声明（请先读）**：本节最常被引用的两个数字（Gartner 的 40%、MIT NANDA 的 95%）在中文互联网上存在大量二手转述与夸大。**本报告只引用研究者亲自打开并读到原句的版本**，对未能取得一手出处的数字**明确标注"未取得一手原文"并拒绝使用**。这一点比数字本身更重要。

### 5.1 Gartner：超过 40% 的 Agentic AI 项目将在 2027 年底前被取消

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

### 5.2 Air Canada 聊天机器人案（Moffatt v. Air Canada, 2024 BCCRT 149）：知识库与现实不一致的判例

**这是一条司法判决，不是产品评论**，因此证据等级最高。

**可确证的事实**【二手（多家律所与律师协会的案情摘要），判例本身可追】：
- 案件：**Moffatt v. Air Canada, 2024 BCCRT 149**（不列颠哥伦比亚省民事解决法庭），**2024-02-14** 作出裁决。
- 事实经过：Jake Moffatt 在其亲属去世后，通过 Air Canada 官网的**聊天机器人**询问**bereavement fare（丧亲票价）**政策；机器人给出了与航空公司实际政策**不一致**的信息。
- 争点：Air Canada 主张"**cannot be held liable for the information provided by the chatbot**"，并援引其 Domestic Tariff 的合同条款；同时主张 Moffatt 未按规定程序申请。
- 裁决结果：** tribunal 认定 Air Canada 对聊天机器人提供错误信息承担 negligent misrepresentation（过失虚假陈述）责任**，判令其支付**标准票价与丧亲票价之间的差额**，另加利息与仲裁费用。
- 判决中的一句被广泛引用（多家法律分析转述）：Air Canada 关于"聊天机器人是独立法律实体"的辩解**不成立**——**公司对其网站上的所有信息负责**。
- 出处（可打开性已逐条实测，标注如下）：
  - 【二手·可引用】McCarthy Tétrault 案例分析：<https://www.mccarthy.ca/en/insights/blogs/techlex/moffatt-v-air-canada-misrepresentation-ai-chatbot>（标题与摘要已确认；**正文因 Vercel 安全校验未打开全文**）
  - 【二手·可引用】WeirFoulds 案例分析：`https://www.weirfoulds.com/moffatt-v-air-canada-bot-betrayal-and-negligent-misrepresentation`（页面已打开，正文被截断）
  - 【二手·可引用】American Bar Association Business Law Today（2024-02）：<https://www.americanbar.org/groups/business_law/resources/business-law-today/2024-february/bc-tribunal-confirms-companies-remain-liable-information-provided-ai-chatbot/>（摘要原文："the British Columbia Civil Resolution Tribunal found Air Canada liable for misinformation given to a consumer by an AI chatbot on its website and awarded damages"；**正文因 Cloudflare 未打开**）
  - 【判决全文·未打开】CanLII 与 BCCRT 官网在本次调研中均返回 403 / JS 校验，**研究者未能读到判决书原文**。凡涉及判决具体措辞的表述，本报告均以多家权威二手来源的**一致**表述为准，并已在措辞上避免超出该共识。

**这是"知识库建设"层面最有价值的一个案例** `[推断]`：
- 它的失效机制**不是检索不到**，而是**存在一个错误的、且对客户可见的知识源（聊天机器人），同时存在一个正确的、但客户查不到的知识源（内部政策文件）**。
- 用本报告的分层词汇说：**L0（权威源认定）缺失**。系统没有规定"当聊天机器人的答案与 Tariff 冲突时，以哪个为准"，于是**对外呈现的那一份自动成为了事实上的权威源**。
- **对守衡的直接含义**：守衡的判定结论会**直接对外**（发给达人/运营/可能到达平台）。因此"权威源认定"不是内部治理洁癖，而是**责任边界**。这正好解释了本项目为什么必须有 `legal-decisions-v1.json` 这种"决定与未决的唯一台账"，以及为什么规则要带生效时间。

---

### 5.3 行业结构性失败：**评测层普遍缺失**

这不是某一家的事故，而是本报告在案例族 A 中**实测到的系统性缺口**，其证据是可枚举的"未找到"：

| 产品 | 公开的评测方法 | 实测结论 |
|---|---|---|
| **Glean** | **有**：AI Evaluator，逐指标公开（context relevance/recall、answer relevance/completeness、groundedness），并公开人机一致率 74%、人类标注者一致率 79% | 唯一到指标级的 |
| **Microsoft 365 Copilot** | **无公开方法** | 只有 Index browser 的 item 级运维校验与"不擅长的查询类型"清单 |
| **Atlassian Rovo** | **只有数字，无方法** | "44% more accurate / 48% fewer tokens"、"60% more successful"均无度量口径 |
| **Notion AI** | **无公开方法** | 只有能力边界声明 |
| **Sana** | **无公开方法** | 只有"排序模型用内部训练集"+ 用户反馈设置 |
| **Dust.tt** | **无公开方法** | 只有 thumbs up/down 反馈 API 与"自行 A/B"建议 |
| **Salesforce Agentforce** | **无公开方法** | 只有产品化 Testing Center / Observability / Audit Trail |

**依据**：逐条见 `raw/A-企业知识助手案例.md` 的「未找到 / 存疑清单」。

`[推断]` **为什么会这样，以及为什么这是守衡的机会**：
- 评测需要**标注**，标注需要**业务专家**，而业务专家的时间在任何组织里都是最稀缺资源。因此"评测做不起来"是行业默认状态，不是能力问题。
- 于是行业普遍退化成两种替代品：**①厂商宣称数字**（不可复现，如 Atlassian 的 44%）；**②产品化反馈按钮**（thumbs up/down，只反映满意度不反映正确性）。
- **守衡的处境与它们不同**：它有**291 条带人工判定的冻结语料**与**V13 的混淆矩阵基线（precision 0.970 / recall 0.962 / f1 0.966）**，这在同规模项目里是罕见的资产。`[推断]` 守衡真正缺的不是"能不能评测"，而是"**评测集能不能随时间变化**"——冻结基线只能防劣化，不能改进。

---

### 5.4 官方文档里承认的产品级失效模式（比第三方吐槽更可信）

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

**这张表的读法** `[推断]`：把厂商自陈的限制**直接当成自己的测试用例清单**。每一行都是一个可以立刻写的回归用例——例如"构造一次长对话 + 注入，检查语境守卫是否与主判定同时失守"。

---

### 5.5 未能取得一手出处的常见说法（**明确排除，不作为依据**）

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

### 5.6 从失败中提炼的六条"知识库建设"教训

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
