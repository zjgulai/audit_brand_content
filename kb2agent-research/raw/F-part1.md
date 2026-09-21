## 6. 跨案例共识清单与企业 Agent 知识库分层候选方案

> **本节性质声明**：这是本报告的**归纳与设计**部分，不是任何单一来源的官方结论。每一条都标注了它由哪些案例/资料支撑，以及它属于「多案例共有」还是「少数派做法」。凡属我个人的设计判断，标 `[推断]`。

### 6.0 共识度速查表

| # | 命题 | 共识度 | 支撑案例/资料 |
|---|---|---|---|
| 1 | 必须有**独立的连接器/语料接入层**，且它是可枚举、可审计的资产清单 | **几乎全体** | Glean Connectors 四类；M365 Synced/Federated；Rovo Connectors；Notion AI Connectors；Sana integrations；Dust Data sources |
| 2 | 必须有**租户内索引/语义层**，而不是每次查询都直连源系统 | **几乎全体** | 六家全部；M365 明确"semantic index is created for every subscription" |
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

---

### 6.1 分层候选方案：企业 Agent 知识库的八层

> 下图是**本报告提出的候选方案**，不是某厂商的官方架构。每层标注了"多数案例共有"或"少数派做法"。`[推断]` 全部为归纳性判断。

```
L0  源与权威层        Source & Authority
    └ 谁拥有这条知识 / 哪一份是准的 / 何时生效 / 何时失效
L1  接入层            Connectors
    └ 同步型（入索引） vs 联邦型（不入索引）/ 推 vs 拉 / Smart Link vs 全内容
L2  索索引层          Index
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
| **L3 权限层** | **全体共有，但一致性等级差异巨大** | Microsoft：**ACL 更新仅 full crawl 生效，最长 24h**（反面参照）。Rovo：**last-mile checks**（正面参照）。Glean：三档模式（折中参照）。Notion：**permissions mapping 作为连接器契约**（设计参照） |
| **L4 规则与阈值层** | **审核类产品必有，但企业知识助手普遍不显式建模** | OpenAI 的 `parameters` 随判定落库；Perspective 的"属性定义 + 部署方阈值"分离；Microsoft 的 sensitivity label 参与 trimming。`[推断]` 这是**企业知识助手类产品与合规审核类产品的最大结构差异**：前者把规则隐含在 prompt 与排序里，后者必须把规则变成可 diff 的资产 |
| **L5 先例与申诉层** | **最少被显式建模，但合规场景最不可缺** | `[推断]` 依据：Anthropic 的 few-shot 原则要求"curate **diverse, canonical examples**"；Self-RAG 的 `ISREL`/`ISSUP`/`ISUSE` 三问实质就是在做"这条先例是否相关、结论是否有据、是否有用"；OpenAI 用混淆矩阵定阈意味着**必须有标注好的误判样本**——而误判样本的来源就是申诉。**本次调研未在任何厂商的公开架构里找到"申诉库"作为一等层的命名**，这是行业的空白点，也是守衡可以领先的地方 |
| **L6 程序与工具层** | **正在从少数派变主流** | Agent Skills 已成开放标准（agentskills.io）；Dust 的 Skills 与 Glean 的 Skills 是三家的独立收敛。`[推断]` 收敛原因很清楚：**知识不解决"怎么做事"，必须另有一层承载程序** |
| **L7 记忆与状态层** | **全体共有，但多数不叫这个名字** | Notion 的 memory system 用 pages/databases 承载；Anthropic 用 compaction + notes 文件；MemGPT 用 OS 式分层。`[推断]` 对合规审核，这一层的正确形态不是"记住用户偏好"，而是"**记住这个项目/这个店铺/这个 SKU 的未决事项与既往处置**" |
| **L8 评测与回归层** | **共识最弱、缺口最大** | 六家里只有 Glean 公开到指标级；Microsoft/Notion/Sana/Dust/Salesforce 均**未找到公开评测方法**。`[推断]` 这不是偶然：**评测需要标注，标注需要业务专家，而业务专家的时间是最稀缺资源**。因此"评测做不起来"几乎是行业默认状态——**也正因如此，谁先建起来谁就有复利** |

---

### 6.2 「从知识库走到 Agent」的三道关（本报告提炼）

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
- 验收：**抽掉任意一条引用，结论必须变成"无法支撑"而不是"照旧输出"。**

---

### 6.3 知识库建设的失败模式清单（机制级描述）

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
| **F8** | **评测被跳过，或评测覆盖大于实际覆盖**：检查恒真、指标算不出来，却对外宣称已评测 | 评测需要标注，标注需要业务专家 | **事实**：六家中只有 Glean 公开到指标级，Microsoft/Notion/Sana/Dust/Salesforce **均未找到公开评测方法**（见 `raw/A-企业知识助手案例.md` 未找到清单）。另注：本项目自身纪律明确"**检查不得断言固定措辞或固定数量**，废检查（恒真）比没有检查更坏" | 建黄金集 + 混淆矩阵；**每条检查必须配反向对照（抽掉配置要变红）** |
| **F9** | **图谱/结构化被当银弹**：为了"更准"上知识图谱，成本翻倍收益有限 | 把 GraphRAG 的适用场景误当通用场景 | **事实**：GraphRAG 论文自陈适用"**global sensemaking questions over datasets in the 1 million token range**"，提升的是 comprehensiveness 与 diversity；GraphRAG 索引"uses an LLM to build a graph index in two stages"，成本高。Mem0 论文显示图记忆相对非图版本只"around **2% higher overall score**"，而"有没有记忆层"带来的是"**26% relative improvements**" | 先问"我的问题是 local 还是 global"；逐条判定问题不需要图谱 |
| **F10** | **连接器内容不是"文本富集"就接入**：接进来但检索质量差 | 接入方按"能连上"而非"能检索好"验收 | **事实**：M365 官方——connector 方式"works best when the connector content is **text rich**" | 接入验收标准里加一条"可被检索到且语义可分辨"的反向测试 |
| **F11** | **把工具/知识全塞给一个 agent，触发模糊** | 以为"给得多=能力强" | **事实**：Anthropic 指出最常见失败模式是 "**bloated tool sets**... ambiguous decision points"，判据是"if a human engineer can't definitively say which tool should be used, an AI agent can't be expected to do better"；Dust 官方警告"agents that are plugged to a **constrained number of data** will usually perform better" | 按域切分 agent/知识源；把召回范围当超参 |
| **F12** | **Skill/知识包成为供应链攻击面** | 第三方 skill 可带脚本与外部网络访问 | **事实**：Anthropic 官方安全提示——"malicious skills may introduce vulnerabilities... or **direct Claude to exfiltrate data**"；建议"installing skills only from **trusted sources**"，并审计 code dependencies 与"instructions or code within the skill that instruct Claude to connect to potentially **untrusted external network sources**" | 知识库/技能目录要有准入与审计流程 |

---
