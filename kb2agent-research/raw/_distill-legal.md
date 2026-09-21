# 【可插入正文】法律 AI 三强：规则库的三种范式、以及全行业一致的「申诉空白」

> **本文件的定位**：不是独立报告，而是主报告《企业Agent知识库体系调研报告》的**可直接插入段落**。
> **一手证据底稿**：`raw/_sub_legal.md`（484 行；Harvey 714 / Luminance 323 / Robin 243 条 sitemap 全量枚举定位 canonical slug）。
> **证据分级沿用主报告约定**：【一手】= **底稿 `_sub_legal.md` 中标记为「已打开原文」的引文**（该轮由 `curl`/Wayback 取回正文并阅读），我未逐条重取；【一手·已复验】= 除底稿外，**本轮定稿前又独立重取一次并逐字比对过原句**；`[推断]` = 研究者推理；【未找到公开资料】= 官方渠道（含 sitemap 全量）确实没有。
> **换言之：只有 6 处【一手·已复验】是本轮二次验证的，其余【一手】是单轮取回的证据。** 对外引用前建议按 §8 第 1 条逐条复取。
> **定稿前独立复验（4 个 URL，均 HTTP 200 + 原句逐字命中）**：Harvey「Fewer checkpoints…」「Playbook rules… five elements」「over-redline, miss flags…」；Luminance「human oversight is a reliable safety net」「the more routine verification becomes」「minimal setup or manual checkpoints」。

---

## 插入位置建议

| 本文件章节 | 插入到主报告 | 替换/新增 |
|---|---|---|
| §1 | §4 案例族 C 开头（C3.3 之前） | 新增 C3.0，交代"为什么法律垂直要单列三家" |
| §2 | 紧跟既有 `#### C3.3 Harvey`（第 603–651 行）之后 | **新增 C3.4 Robin / C3.5 Luminance**；既有 C3.3 不必改，只把 §0 的引语口径修正见 §7 |
| §3 | 同上（与 §2 同批） | 新增 |
| §4 | §4 案例族 C 末尾，作为 C4 | 新增：这是本案例族**最重要的一条结构性发现** |
| §5 | 紧跟 §4 之后 | 新增：**唯一一组"两家一手立场正面对立"的证据** |
| §6 | 分发到 §6.0 共识度速查表 / §6.1 八层 / 附录缺口清单 G1–G5 | **不新增章节**，按下表逐行并入 |
| §7 | 第 456 行的引语 | **口径修正**（不改结论，只改引文的严格程度） |

---

## 1. 为什么法律垂直要单列三家（C3.0）

客服垂直（Sierra / Decagon）解决的是"**对话中该说什么**"，法律合同审查解决的是"**这份文本按我方立场该改成什么、以及为什么**"。后者与本项目「守衡」的形态更同构：

- 都是**规则驱动的判定**，而不是知识问答；
- 都有**明确的"我方立场"**（守衡 = 合规口径与品线规则；法律 = playbook）；
- 判定结论都**对外产生后果**，所以"误判怎么被纠正"是产品的一部分，不是售后。

三家的定位差异也决定了它们的知识库形态不同：Harvey 服务律所与企业法务（60+ AmLaw 100 律所 / 1,500+ 法务团队 / 142,000+ 法律专业人士）；Robin AI 偏企业法务与私募资管；Luminance 明确**跨出法务**，把采购、财务、销售、HR、市场、合规、高管都列为使用方（1,000+ 客户，2025 年 $75M Series C）。`[推断]` Luminance 的"全员使用"定位，正是它敢把"少人工检查点"写成卖点的商业原因——非法律用户本来就不会做法律复核。

---

## 2. 规则库：三种截然不同的范式（C3.4 / C3.5）

### 2.1 三家对照

| 维度 | Harvey | Robin AI | Luminance |
|---|---|---|---|
| 规则的载体 | **显式结构化 schema（5 字段）**【一手·已复验】 | **自然语言文档**（客户上传 .docx/.pdf）【一手】 | **Checklist / position**（红黄标注 + preferred/fallback）【一手】 |
| 政策层级 | standard / acceptable deviations / unacceptable deviations / guidance / optional | standard → pre-approved compromise → further fallback（**文内语义，非字段**） | preferred / fallback + **与"过去类似谈判已接受/未接受"的对比** |
| 状态分类 | `Aligned` / `Needs review` / `Deviates` | **Red / Amber / Green**（可配置的 `Select` 输出枚举） | `unacceptable` / `non-standard` / `missing`；视觉上 Red=high-risk、Yellow=non-standard |
| 数值阈值 | **未找到公开资料** | **客户自行定义，无内置默认值** | **未找到公开资料** |
| 规则粒度 | 单条 rule 交给一个 subagent | prompt 级（Template / Prompt Set） | **position 级（跨条款聚合，非 clause-by-clause）** |
| 规则创建 | Playbook Builder：既有 playbook / 已标注合同 / 预置模板 / 对话四种来源 + **主动提问澄清** | 客户自撰文档 | self-serve playbook setup，checklist 自动套用于所有 incoming contracts |

### 2.2 Harvey 的字段级 schema（三家唯一公开者）【一手·已复验】

原句："Playbook rules are conceptually simple, and include the following elements" ——

| 字段 | 官方定义（逐字） |
|---|---|
| **Standard position** | "the ideal term a company wants to see in their contracts" |
| **Acceptable deviations** | "fallback provisions a company is willing to negotiate" |
| **Unacceptable deviations** | "dealbreakers for the contract" |
| **Guidance** | "how to interpret and apply the rule given specific deal context" |
| **Optional** | "whether or not it is ok for a clause to be absent in a contract" |

**四个工程细节值得单独记下**（均【一手】）：
1. 规则可编码 **positions / fallback language / guidance / actions / conditions / escalation paths**。官方举例：一条数据处理规则可以要求把非标 breach notification 条款 **flag 给 privacy counsel，而不是自动 redline**——即**"升级路径"是规则的一等字段，不是兜底行为**。
2. 规则来源分析时，Harvey 会**主动提问澄清**，并把 outlier 条款 "**surface for confirmation**" 而不是自动写入规则库。
3. 每条规则带 **summary + explanation + 指向源文档的 citations**，供 playbook owner 审批。
4. 方法论出处被明确交代：内部法律工程师与产品律师在**构建 300+ 客户 playbook** 过程中沉淀的"how to weigh different inputs, reconcile conflicting precedents, and translate them into rules"。

### 2.3 Robin：playbook 是"给 AI 读的谈判立场文档"，不是 schema【一手】

官方 Help 原文："Your playbook, **which can be in either .docx or .pdf format and contains your negotiation positions or instructions**."

同页有两条**官方自陈的限制**（对理解"规则库成熟度"很重要）：
- "**At this time, Robin applies only first round playbook positions. Additional fallback or escalation positions are not yet supported.**"（该页版权年 2019–2025）
- "Robin Review works best with clean (non-redlined) documents."

但 2025-09 的能力扩展把层级语义**从字段移到了文档自然语言里**，官方举例给出完整阶梯：责任上限 **1x 年费（standard）→ 对方改 3x → Robin 提 2x（"a compromise you've pre-approved"）→ 对方再提数据泄露无限责任 → Robin 直接 redline 成 "capped at 3x annual fees"，"preserving your further fallback position"**。

`[推断]` 这是本报告里**"最弱的规则库形态"与"够用的规则库形态"之间的一条现实路径**：如果团队暂时写不出结构化 schema，**把 fallback 阶梯写进自然语言规则文本，模型仍能执行**——代价是**无法被程序校验、无法统计覆盖率、无法自动检测冲突**。结构化 schema 的价值不在"模型看得懂"，而在"人能不能对它做质量门"。

Robin 的风险三色分级实现方式也值得记：它**不是内置模型能力，而是一个可配置的输出枚举**——官方教程要求用户 "Choose the `Select` answer type and assign Red, Amber, and Green options. **Define clear criteria for each rating**"，也可以退化成 compliant / not compliant 二值。**阈值归客户。**

### 2.4 Luminance：按"立场"而非按"条款"组织【一手】

官方（VP of Product）原文："Luminance now focuses any negotiation around a business's core positions, instantly directing attention to the clauses you care about, whether they're **unacceptable, non-standard or missing altogether**. Displayed in a clear **step-by-step Checklist**, users can simply tick off each position as they review."

**每个 position 输出三元组**：**Summary**（对方提了什么）/ **Reason**（"why it's not standard against internal benchmarks"）/ **Mark-Up**（一键插入的替代措辞）。

**"position 级而非 clause 级"是其核心技术主张**，原文举例：责任限制在第 3 页，而第 5 页 IP 条款又引用了责任限制——"**all of this will be considered**"，而不是逐条款孤立评估。

`[推断]` **这一条对守衡的迁移价值最高。** 守衡的判定对象是"一条内容是否合规"，但同一条内容在不同语境（品线、平台、达人类型、投放场景）下结论不同；如果规则库按"条款/词表"组织，就会反复出现"单看这句没问题、连起来看有问题"的漏判。**按"立场（position）"组织规则、让一次判定聚合跨字段证据，是解法方向。**

---

## 3. 案例库与黄金样本（C3.4 / C3.5 续）

| | Harvey | Robin AI | Luminance |
|---|---|---|---|
| 黄金样本 | workflow 支持客户自带 "**golden examples**"（25,000+ custom workflows）；评测侧有专家共建的 **"golden" query sets**（precision / recall / NDCG） | **8,500+ 样本** gold-standard 数据集，**four-eye 双人复核**；Q&A 标注出"回答所需的精确文本段落" | **ContractIQ Bench：189,000 人工标注并复核的数据点**（三家唯一公开人工标注黄金集规模者），held-out 文档 + 法律专家盲评 |
| 客户历史数据 | **Precedent bank**：可搜索，每条 redline 旁按 **clause 粒度**并列展示"对方提案 vs 我方已签合同中被接受的立场"，可点击跳回源文档 | 不预制黄金样本，让客户**用多维过滤构造 precedent set**（文档类型 / 交易对手特征 / 时间 / 法域 / 交易规模与风险画像） | 客户既有合同与 past decision-making："**Every negotiation is preserved and searchable**" |
| 正负例 / 拒答 | 幻觉的**形式化定义**（见 §3.1） | **N/A answers** 处理不确定性（存在专门 help 文档，底稿未打开正文） | 把"缺失"作为**一等输出类别**训练："When information is not present, it is designed to **identify that absence rather than invent an answer**" |
| 数据集治理 | published 评测集 **lock 不可变**；行级 RBAC 分 public / confidential / restricted | Permission Groups：Personal / Private(invite-only) / Public | 自建 AWS 环境部署 Luna，减少对外部模型供应商的数据暴露 |

### 3.1 Harvey 的幻觉定义（可直接引用的一句话）【一手】

> "a factual claim made by an LLM that can be **demonstrably disproven by reference to a source of truth**"

并且**明确不把理解/推理错误计入幻觉**——这条边界很重要，否则"幻觉率"会变成一个谁都能定义的营销数字。检测方法：先把答案拆成 factual claims，再逐条对照 source of truth，**并对全部模型判断做人工复核**。

### 3.2 两个"把历史裁决回流进规则库"的具体机制【一手】

1. **Harvey 的 pattern 建议**：当最近 5 份 NDA 都接受了某条款而 agent 仍在 flag 时，Harvey 识别该 pattern 并**主动建议新 standard**；同时会 flag "agent 立场已落后于最近谈判"，surface 团队实际签署结果与写定标准的不一致。
2. **Robin 的 "Have we ever?" 框架**：用**接受史**而非**声称立场**还原真实边界——官方示例 prompt："*Have we ever accepted unlimited liability for breach of confidentiality in a vendor agreement? If so, what were the specific circumstances...*"。配套还有 **Request precedent hierarchies**（按有利程度排序并标出 outlier）与 **precedent + playbook validation**（把 playbook 文档一并放进文档集做一致性比对）。

`[推断]` 这两条合起来给出了一个**不依赖模型自动学习**的轻量回流路径：**规则库旁边挂一份"接受史"，用固定 prompt 周期性回答"我们实际上接受过什么"，再把差异变成规则修订提案。** 它的成本是几次人工审阅，而不是一套训练管线。

---

## 4. 【本节最重要】三家一致回避的东西：申诉入口、复核 SLA、翻案回流、自动化率

这是本次子调研**最一致、也最可复现的空白**。三家官方渠道（含 sitemap 全量枚举）中：

| 项 | Harvey | Robin AI | Luminance |
|---|---|---|---|
| 面向终端用户的"AI 判错了 → 申诉"入口 | 【未找到公开资料】 | 【未找到公开资料】 | 【未找到公开资料】 |
| 复核 SLA / 时限承诺 | 【未找到公开资料】 | 【未找到公开资料】 | 【未找到公开资料】 |
| 翻案后如何回流到规则/模型 | 【未找到公开资料】 | 【未找到公开资料】 | 【未找到公开资料】 |
| 误报率（false positive rate） | 【未找到公开资料】 | 【未找到公开资料】 | 【未找到公开资料】 |
| **auto-approval / auto-clear / 人工复核比例** | 【未找到公开资料】 | 【未找到公开资料】 | 【未找到公开资料】 |

**三家公开的数字全部集中在"准确率、时间节省、成本节省"三类**：Harvey 59%→77%（风险分类）、53%→87%（redline rubric）、幻觉 0.2%、引用识别 >95%、≥5%（律师+Review tables 优于纯律师或纯 LLM）；Robin 80% faster review、98% 时间节省、LeMAJ 省 80%/50% 评测人力、IAA +11%；Luminance 90%/98%/500+ 小时、Staples 50%、Hitachi NDA <5 分钟、Luna +5%、189,000 标注点。

**但没有一家回答"多少比例的合同可以完全不需要人"。** 包括以 **Autopilot「AI 对 AI 自动谈判、until human signature」**为卖点的 Luminance，也没有给出"多少比例能自动走完"的数字。

`[推断]` 这不是疏漏，是**共同的行业默契**：自动化率的数字一旦公开，就等于把"人工兜底还剩多少"暴露给采购方与监管方，而这正好是**最难辩护、最容易在法律与合规场景里被追责**的那一项。`[推断]` 对本项目的含义是：**守衡若要公开自己的判定质量，可以选择填上这个行业空白——但要先确保这个数字口径上站得住（分子分母、是否含人工改判、是否含未判定）。**

---

## 5. 人机分工：唯一一组"两家一手立场正面对立"的证据

**这是本子调研里最有对比价值的发现**，因为两句话都是厂商自己写的、且都在**劝采购方不要相信对方那一套**。

### Harvey 立场【一手·已复验，逐字】
> "**Fewer checkpoints are often a risk signal, not a benefit**: Legal teams should be cautious of solutions that emphasize speed and efficiency **without extensive oversight controls**, because it often means less governance and more risk shifted to your team (resulting in more manual work)."

同文另一句（同段）：
> "It's important to recognize that some legal AI tools emphasize speed and efficiency above all else for faster review, fewer checkpoints, and more autonomous outputs. While this sounds convenient, legal work is too high-stakes to prioritize convenience over trust and accuracy."

### Luminance 立场【一手·已复验，逐字】
> "This wasn't just a failure of AI. And it wasn't simply a failure of process. It was a failure of an assumption that **human oversight is a reliable safety net**."
> "Verification doesn't happen in ideal conditions, it happens at the tail end of long workflows, across stacks of documents, against hard deadlines. And **the more routine verification becomes, the less reliable it gets**."
> "**accuracy cannot be enforced through policy alone**… policy and process are **no substitutes for system design**."

并在产品页把"少检查点"直接写成卖点（同页【一手·已复验】："increased levels of efficiency and precision and **minimal setup or manual checkpoints**"），口号为 "**Autonomous by default. Human by choice.**"

### Robin 居中【一手】
> "Robin's precedent research capabilities **amplify rather than replace legal judgement**… it **will not have full context of a deal which may create precedent with unusual concessions**."

并在交互上做了差异化设计：能**区分"你的改动"与"对方的改动"**，只对应当响应的部分作答，"**supporting you without overriding your judgment**"【一手】。

### 三家的"替代物"（在申诉机制缺失的情况下，它们各自拿什么顶上）

| | 误判的工程处理 | 人审入口 | 低置信行为 |
|---|---|---|---|
| **Harvey** | 每个 subagent 在**自己的文档分支**工作，每个 edit 是**带 rule 标签的 tracked change**；收尾像 VCS 一样 merge，**两条规则触碰同一文本的 collision 升级给 lead agent 裁决** | Review Queue / Assignment，**可按自定义规则分派**，有 `Ready for review` 状态 | 公开承认的旧失败模式："reviews could **over-redline, miss flags, insert suggestions in the wrong location, and miss whose paper the contract was on**" |
| **Robin** | 生产环境**回归测试**监控 sudden hallucinations、相对 gold standard 的 accuracy/correctness/relevance 漂移、回复一致性、context 变化 | **把 .docx 导出到 Word 自己改**（这是官方给出的修正通道）；另有支持工单（非申诉机制） | N/A answers（未读正文） |
| **Luminance** | **verifier 独立审计答案**："most systems generate an answer and trust it. **We don't.**"（claims examined / citations verified / sources cross-referenced）；多模型 "Panel of Judges" + 编排层裁决 | 可 "**review a log of all changes made by the AI**" | "**Where confidence is low, outputs are flagged rather than presented as fact.**"；信息不足时"**returns the question and outlines what's missing rather than guessing**" |

`[推断]` **Luminance 的"低置信 → 标注而非断言"是三家唯一明文写出的机制，也是守衡最该照抄的一条**：它把"不确定"从失败变成了一个**有出口的输出类别**。与之配套的是 Luminance 训练目标里的 "identify that absence rather than invent an answer"——**把"缺失"当一等输出类别训练**，而不是当错误处理。

---

## 6. 并入主报告的具体行（不新增章节）

| 主报告位置 | 并入什么 |
|---|---|
| **§6.0 共识度速查表** | 新增一行：**「规则库必须有独立的结构化载体，而不是混在文档里」**——证据强度：**方法论共识 + 3/3 法律垂直产品都有独立规则层，但只有 1/3 公开字段级 schema** |
| **§6.0 共识度速查表** | 新增一行：**「低置信输出必须被标注，而不是输出为事实」**——证据强度：**少数产品明确（Luminance 明文）；其余为工程实践**（与主报告第 453 行 Microsoft「错误必须外显而非隐藏」同源） |
| **§6.1 八层分层候选** | 在"规则层"下补注：法律垂直给出的字段模板 = **standard / acceptable / unacceptable / guidance / optional**；并强调 **escalation path 是规则的一等字段**（Harvey 原文），不是兜底逻辑 |
| **§6.1 八层分层候选** | 在"案例层"下补注：三种构造路径 —— ① 客户自带 golden examples；② 客户历史文档 + 多维过滤（Robin）；③ 平台自建人工标注黄金集（Luminance 189k）。**守衡可负担的是 ① + ②** |
| **附录 G1（人工结论回流没有落点）** | 补强证据：**三家法律 AI 全部公开了"从已签结果反推规则"的机制**（Harvey pattern 建议 / Robin "Have we ever?"），但**没有一家公开"从被推翻的 AI 判断反推规则"的机制**。→ G1 不只是"守衡缺"，而是**全行业都缺的一端** |
| **附录 G3（案例库无结构化载体）** | 补强证据：**三家都有先例层，且都强调"先例不平等"**——Robin 原文 "**Not all precedent is equal**… Legal teams must be equipped to **discern 'gold standard' precedents from outlier agreements**"。→ 先例库不能只是"历史记录集合"，必须带**质量分级维度** |
| **附录 G5（上游引用是声明不是证明）** | **最锋利的一条补强**：Harvey 在 BigLaw Bench 中公开发现——**强行要求模型给引用会显著拉低表现**，模型会 "consistently **hallucinate sources**（either document text, page number, or both）leading to weak source scores and **far worse answer scores**"；因此它把评测拆成 **answer score 与 source score 两个独立分数**（原文："Though related, source score and answer score are **independent**"）。→ **结论：引用可追溯性必须与判定准确率分开度量，且引用必须结构化可校验，不能靠模型自由书写。** |
| **附录 G6（评测入集机制）** | 补强证据（可直接抄的方法论）：Harvey 的 ground truth 由**签约律师与 Review tables 分别作答 → 比对分歧 → 内部 ALRs 裁决**，且**双方一致的样本也抽样复核**（"ensure that agreement didn't cover up misunderstanding"）；评测集 published 后 **lock 不可变**。另有 **BigLaw Bench 的任务骨架从"time entry"（计费工时）派生**——`[推断]` 守衡的等价物是"**每一次人工改判**"，它天然带业务上下文，比凭空设计任务更贴近真实分布 |
| **附录 G7（申诉只有出口没有归途）** | 补强证据：**三家法律 AI 均未公开申诉入口、复核 SLA、翻案回流**（见 §4）。→ 守衡的申诉链路设计**没有行业现成答案可抄**，只能自己定；这既是风险也是少见的差异化空间 |

---

## 7. 一处引文口径修正（请改主报告第 456 行）

主报告 §4.4 现写作：

> **Harvey**："**Fewer checkpoints are often a risk signal, not a benefit**"——把"宣传少人工介入"定义为 red flag

**逐字复验后，这句话需要补回它自己的限定语，否则会读成绝对主张。** 原文完整句为：

> "**Fewer checkpoints are often a risk signal, not a benefit**: Legal teams should be cautious of solutions that emphasize speed and efficiency **without extensive oversight controls**, because it often means less governance and more risk shifted to your team…"

即 Harvey 攻击的是"**速度快但没有充分 oversight 控制**"这一类产品，而不是"检查点少"本身。**建议改为**：

> **Harvey**："**Fewer checkpoints are often a risk signal, not a benefit**"——但注意其限定条件在同句中："…solutions that emphasize speed and efficiency **without extensive oversight controls**"。Harvey 攻击的是"快而无人管"，不是"检查点少"本身。

`[推断]` 这个修正不改变结论（两家立场仍然对立），但**改变了对立的性质**：不是"要不要人"，而是"**人的位置在哪里**"——Harvey 主张人审是**能力**（要有 extensive oversight controls），Luminance 主张人审**不能当安全网**（要靠系统设计保证准确）。这个区分对企业内部项目更重要，因为守衡**不可能选择"不要人"**，只能选择"人在哪一步"。

---

## 8. 本文件的边界（它不知道的事）

1. **Robin 与 Luminance 的所有引文，来自底稿 `raw/_sub_legal.md` 的本轮 curl 取回**；本轮定稿前我**只独立复验了 Harvey 的两句 + Luminance 的两句**（见文件头）。余下引文若要用在对外材料中，建议逐条复取。
2. **未取回者不得引用**（底稿已单列，此处不重复）：`docs.harvey.ai`（DNS 不可解析）、`www.robinai.com`（连接失败，规范域名为无 www）、`docs/support.robinai.com`（不存在）、**5 份官方白皮书 PDF 正文**（图片型 PDF + 子集化字体，本机无 pdftotext/PyPDF2/Quartz，提取失败）、`robinai.com/first-pass`（JS 骨架）、Robin N/A-answers 页、arXiv `2510.07243v1`（LeMAJ 论文）、Harvey `/blog/memory-in-harvey` 等 4 篇、Robin `The Hidden Network…` 后半。
3. **Luminance 的 Legal AI Glossary 是营销站术语表**（Grounded Generation / Human-in-the-Loop / Audit Trails 等），定义偏通用，**不等于其产品实际 schema**，引用须谨慎。
4. **三家均未公开数值风险阈值与置信度阈值**——本文件所有"分级"都是**命名分类**，没有任何一家给出可比较的数值线。`[推断]` 这意味着"阈值"在法律垂直仍是**部署方自定的参数**，与主报告 §4 C1/C2（OpenAI Moderation、Perspective API）的结论一致：**阈值所有权归部署方，是行业惯例而非缺陷。**
5. 本文件**不含**对守衡的落地建议——那部分归 `raw/E-守衡落地建议.md`，此处只在 §6 标明"并到哪一行"。
