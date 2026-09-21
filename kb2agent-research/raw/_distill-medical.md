# 【可插入正文】医疗临床文档 AI：人审的强制程度、审计轨迹的法定规格、以及变更控制的 PCCP 模板

> **本文件的定位**：主报告《企业Agent知识库体系调研报告》的**可直接插入段落**。
> **一手证据底稿**：`raw/_sub_medical.md`（511 行；Abridge 16 页 + Microsoft/Nuance 8 页 + FDA 13 个来源含 **4 份 PDF 全文抽取**；标记 107×「已打开原文」/ 13×「未找到公开资料」/ 9×`[推断]`）。
> **证据分级**：【一手】= 底稿标记「已打开原文」；【一手·已复验】= **本轮定稿前我又独立重取一次并逐字比对**；`[推断]` = 研究者推理；【未找到公开资料】= 官方渠道确实没有。
> **本轮独立复验（3 项，均 200 + 原句逐字命中）**：① eCFR 21 CFR Part 11 §11.10(e)/§11.50/§11.70 全文；② Abridge 强制人审两句；③ Microsoft 护士侧「quick nurse review and approval」。
> **⚠️ 本轮复验失败 1 项，已降级**：底稿引用的 Microsoft 发布博文原句「orders are **directly entered into the EHR order module**」**本轮未能复现**（`news.microsoft.com` 该 URL 现 404、Wayback 本轮连接失败、Microsoft 三个现行产品/文档页均无该句）。**该句在本次定稿中不得作为一手引文使用**，§3.2 已按此处理。

---

## 插入位置建议

| 本文件章节 | 插入到主报告 | 性质 |
|---|---|---|
| §1 | §4 案例族 C，作为 **C3.0** | 新增：交代为什么医疗垂直要单列（它是唯一有**法定**人审边界与审计规格的行业） |
| §2 | §4 案例族 C 末尾，作为 **C3.4** | 新增：Abridge 的**两轴误判分级**（补 L4/L5） |
| §3 | 紧跟 §2，作为 **C3.5** | 新增：Microsoft Dragon Copilot（人审表述最弱的一家） |
| §4 | §4 案例族 C 末尾，作为 **C4**（独立小节） | 新增：**FDA/21 CFR Part 11 的法定审计轨迹规格**——本报告此前完全没有监管法定规格来源 |
| §5 | **§6.0 共识度速查表新增 3 行** + **§6.1 L4/L5 补注** + 附录 G4 补强 | 并入，不新增章节 |
| §6 | §5.5（未能取得一手出处的常见说法）与 §5.4 附近 | 新增：`nuance.com` 已成空壳这一事实，防止后续再被当作一手源 |
| §7 | — | 诚实边界 |

**一句话说明这批证据的独特价值**：本报告其余十二家案例的产品，**"人审该多强"是各家自己声明的商业选择**；只有医疗这一支，**"自动化到什么程度需要人审、审计轨迹必须记什么"是有法定文本的**。因此这一支不是"又多三家案例"，而是给 L4/L5/L8 三层提供**外部强制标准**。

---

## 1. 为什么医疗垂直要单列（C3.0）

三个理由，都是别的垂直给不了的：

1. **人审边界有法律文本**。FDA 的 PCCP 终版指南对"自动实施 vs 人工实施"给出了**可引用的定义**（§4.3），Non-Device CDS 的四要件则给出**"什么情况下可以不按器械管"的判据**（§4.2）。这两条比任何厂商的自我声明都硬。
2. **审计轨迹有法定字段清单**。**21 CFR Part 11 §11.10(e)** 逐条规定了审计轨迹必须是什么形态（§4.4）。本报告此前在 L4「规则版本」与 G4「只有内容指纹、没有生效时间与批准人」上的建议，**在这一支里能找到直接的法定对应物**。
3. **有两家产品给出了"人审强制程度"的完整对照**：Abridge 用**强制语**（"required to review and verify"），Microsoft 最高只到"供审阅与编辑"。`[推断]` 同一行业、同一产品形态、同一监管环境下出现这个差别，说明**人审边界的强弱是可设计、可选择的**——而不是由技术能力决定的。

---

## 2. Abridge：两轴误判分级 + 四条互不相同的纠错通道（C3.4）

**它解决什么**：面向**企业级医院系统**（而非单体诊所）的临床文档生成——150+ → 300+ 家系统、2.5 亿患者。定位差异很重要：`[推断]` **面向医院系统意味着采购方有合规部门**，这解释了为什么 Abridge 是这一支里公开表述最严谨的一家。

### 2.1 规则库：拆成"事实性护栏层"与"外部权威内容层"

**(a) 事实性护栏层**——目标**不是**"审核医学正确性"，而是**逐条 claim 的"是否有原文支撑"**：

> "The Abridge system for ensuring accuracy in AI-drafted documentation has two components: 01 A proprietary, task-specific AI model for detecting unsupported claims in draft documentation 02 An automated system for correcting unsupported claims, leveraging the conversation transcript and EHR context"

检测模型规模：**"over 50,000 training examples"**，由开源通用幻觉检测数据 + 领域样本（转写、EHR 上下文、示例笔记）混合构成。

**★ 两轴分类学——这是本报告见到的"误判分级规则库"最完整的公开字段设计**【一手】：

| 轴 | 取值 | 判据的性质 |
|---|---|---|
| **Support（支撑度）** | Supported / Not supported / **Contradiction** | "classified as a 'contradiction' if it **directly conflicts** with statements made in the transcript" |
| **Severity（严重度）** | **Major / Moderate / Minimal** | 定义**全部用"most clinicians would agree"起头**——即**以临床医生共识为判据，而不是固定数值阈值** |

原文（Severity 三级）：
> "An unsupported claim should be classified as '**major**' if **most clinicians would agree** that, if left uncorrected, the claim would most likely have a **negative impact on clinical care** and/or has a non-trivial chance of leading to **substantial harm**."
> "**Any inaccurate claim that could plausibly impact patient care should be rated at least 'moderate'.**"
> "An inaccurate claim is classified as '**minimal severity**' if most clinicians would agree that it has **little to no impact** on clinical care, either in the short or long term, even if left uncorrected."

`[推断]` **这两轴合起来给出一个可以直接搬到守衡的结构**：**"是否与原文冲突"**（客观、可校验）与**"影响有多大"**（需人判、需共识）**是两个正交维度**。守衡今天的判定只有"合规/不合规"，缺的正是第二轴——而第二轴恰恰是"哪些必须拦、哪些可以放过"的唯一依据。注意 Abridge **没有给第二轴任何数值线**，而是给了**共识式定义**——这比给一个拍脑袋的阈值更可辩护。

**(b) 外部权威内容层**——**不自建指南库**，走授权路线：UpToDate、NEJM、JAMA、AHA（"American Heart Association licenses selected scientific content to Abridge"）。**证据排序规则由临床医生手工制定**，官方原话：
> "Is the right source a specialty society guideline? The primary literature? A review article? An opinion piece? Those carry very different weight at the point of care, and knowing how to rank them, and when, **is not a question an algorithm can settle on its own.**"

`[推断]` 这句话与主报告 §5.2（Air Canada 案）是同一个问题的两种表述：**"哪一份是权威源"不能交给模型决定**。

### 2.2 案例库：Abridge 没有"案例库"，它有的是**评测数据集 + 三条从真实反馈反推测试用例的路径**

数据集（**10,000+ 小时**医学对话、内部非公开问诊集、"challenge datasets"、Librispeech、**FLEURS 102 语言**）之外，更有迁移价值的是**回归用例是怎么长出来的**——由**医生自由文本反馈**反推出新的测试维度【一手】：
> "**New medications are continuously being released** — Does the documentation correctly spell medications that the models have not encountered previously?"
> "**Many visits include multiple speakers** — Given an infant patient, a parent, and a clinician, does the documentation appropriately distinguish between the parent and the (non-speaking) patient?"
> "**Clinicians and patients do not always agree** — If a patient misstates their own diagnosis, and a clinician corrects them, is the conclusion appropriately reflected in the final note?"

`[推断]` **守衡错题本的等价物就在这三条里**：不要问"哪条规则判错了"，要问"**哪一类输入我们从来没测过**"。Abridge 的三条全部是**输入分布的缺口**（新药名 = 新词、多人对话 = 说话人归属、患者自述与医生纠正冲突 = 信号优先级），而不是规则逻辑的缺口。

### 2.3 误判与复核：**四条互不相同的通道**（本报告里机制最全的一家）

| # | 通道 | 官方原文要点 |
|---|---|---|
| 1 | **上线前盲评 + anytime-valid 序贯检验** | "Before we release any major model updates, we perform **blinded head-to-head evaluations with our own clinical staff**"；"To allow for early stopping when the results are conclusive, we use **anytime-valid sequential hypothesis testing**, providing guarantees on the **false positive rate** that hold regardless of how long we run the trial" |
| 2 | **alpha → beta → GA 分阶段放行** | "The first stage is an '**alpha**' release with **limited rollouts to specially trained early adopters**… trained to be especially vigilant about editing and comprehensive in their feedback" |
| 3 | **被动信号 = 医生改了多少** | "we capture **edits made to the AI-generated note before they are finalized**… Clinician-generated edits are **inherently scalable as a feedback mechanism, as editing is already a natural workflow**" |
| 4 | **专用审计工具 Linked Evidence** | "we outfit all of our note viewers with a tool for **pinpointing the relevant transcript excerpt**… **This same feature is available to our clinician users**" |

`[推断]` **第 3 条是这一整份调研里唯一一条"零额外人力成本"的质量信号**：医生本来就要改，改动量天然就是质量度量。**守衡的等价物是运营/法务对判定结论的实际修改率**——它不是新建流程，而是**把已有动作记录下来**。

`[推断]` **第 4 条的设计取向值得单独注意**：**同一个回溯工具同时给内部审计员和终端用户**。这意味着"可审计"不是给合规部门看的报告，而是**使用者日常操作的一部分**。

### 2.4 人机分工：**强制语，且责任在医生**（本报告措辞最强的一家）【一手·已复验】

> "**All clinician notes generated by Abridge are reviewed and edited (if necessary) by the clinicians who conducted the patient encounter before being entered into the EHR.** No guardrail is perfect, and clinical conversations can contain legitimate sources of ambiguity…"
> "we stress that even amidst this progress, **clinician review of AI-generated notes remains essential. Clinicians are required to review and verify their own notes before filing in the electronic health record (EHR).**"

**责任归属的设计语言**：
> "Transparency Builds Trust: … requires designing systems that are **easily auditable**. **With Linked Evidence, Abridge-generated draft clinical documentation is traceable to the source conversation.**"
> "Our design approach envisions **assistance as a fundamentally humble feature**, which respects the role of clinician judgment."

条款侧：Terms §11 写 "**AS IS**"、"**ABRIDGE DOES NOT ENGAGE IN THE PRACTICE OF MEDICINE**"，责任归于医生，**责任上限为 "the greater of $1,000 or the amount paid… in the previous twelve (12) months"**。BAA 另给：部长账簿查阅权、披露会计 30 天内、PHI 访问 15 个工作日内、违约通知 10 个工作日。

**【未找到公开资料】**：Abridge 的**审计日志具体字段、保留期限、谁可查阅**（sitemap 确认**不存在 security/trust 页面**，也没有 SOC 2 / HITRUST / ISO 声明）。

---

## 3. Microsoft Dragon Copilot（原 Nuance DAX）：人审表述最弱的一家（C3.5）

### 3.1 先更正一个事实：`nuance.com` 已经是空壳

三个不同的 `nuance.com/healthcare/*` URL **返回字节完全相同**的 166,321 字节 Microsoft 模板（**302 跳转**）。真正的 Nuance DAX Copilot 页面（带全部统计数字的那个）**只能通过 Wayback 2024 快照取到**。产品已于 **2025-03-03 并入「Microsoft Dragon Copilot」**。

`[推断]` **这条要写进主报告的理由不是"八卦"，而是防止后续复核者把 `nuance.com` 当一手源**——主报告在 §1 已经记录过一次同类教训（"把检索失败误判为事实缺失"），这是它的镜像：**把重定向后的空壳误判为有效来源**。

### 3.2 人审边界：最高只到"供审阅与编辑"

**措辞强度对照**（这就是本节的全部价值）：

| 家 | 最高措辞 | 强度 |
|---|---|---|
| **Abridge** | "Clinicians are **required to** review and verify their own notes **before filing** in the EHR" | **强制 + 时点** |
| **Microsoft**（医生侧） | "delivers the summary… **for clinician review and editing**" | 描述性 |
| **Microsoft**（护士侧）【一手·已复验】 | "converting them into structured flowsheet documentation for **quick nurse review and approval** and seamless EHR transfer" | 描述性 |
| **Microsoft**（定稿前） | "makes it easy to get **a quick refresher on the patient before finalizing a note**" | 描述性 |

**在本次抓取的全部 Microsoft 与 Nuance 页面中，未找到任何 "clinician remains responsible" 或等同的责任归属语句**【未找到公开资料】。`[推断]` 此类条款很可能存在于产品条款/DPA/客户合同中，但**不应据现有公开证据推断其内容**。

**⚠️ 一条已降级的对比（本轮复验失败）**：底稿引用了 Microsoft 发布博文的一句"**orders are directly entered into the EHR order module**"，并据此论证"自动写入 EHR 与人审边界存在张力"。**本轮该句未能复现**（原 URL 404、Wayback 连接失败、三个现行页均无）。**因此本文件不把它作为一手引证。** `[推断]` 若该表述确曾存在，其张力仍然成立；但在拿到可打开的存档链接前，**它只能作为待核项列入附录，不能进正文**。

### 3.3 合规与评测

- **合规是平台级而非产品级**：HIPAA/HITECH 经 BAA、ISO 27001、**HITRUST CSF**（由**认可的外部独立审计师**执行）、SOC 1/2/3、ISO 42001、FedRAMP，Trust Center 称 **"more than 90 offerings"**。**Dragon Copilot 专属认证：未找到公开资料。**
- Microsoft 自己写明了责任划分："using Microsoft services **doesn't on its own achieve HIPAA compliance**. Your organization is responsible for ensuring that you have an adequate compliance program and internal processes in place"。
- **数字**（均【一手】）：每次问诊省 **5 分钟** → 每位医生每月多 **13 个**预约档期；**70%** 自述工作生活平衡改善；**77%** 文档质量提升；**93%** 患者称医生更亲切；训练量 **15M+** 问诊；**200+** EHR；UMHW 每月 +12 患者 / +20 wRVU / **80% ROI**；Intermountain 笔记耗时 **-27%** / 2,500+ 用户 / 24+ agents；Mercy 护士 12 小时班次省约 **2 小时**；VA AI Tech Sprint 在 150+ 参赛者中胜出。**调查样本有脚注**：879 名临床医生 / 340 家机构（2024-07）；413 名患者（2024-06）——**这一点值得肯定，本报告其它案例的"百分比"多数没有样本脚注**。
- **评测**：与 **Glean 独立收敛到同一组三指标**——Groundedness and fabrications / Answer relevance / Evidence relevance（见主报告 §2.1 与 §6.0 第 9 条）。
- **【未找到公开资料】**：产品级认证、审计日志规格、**任何准确率指标**、申诉流程、责任/免责语言。

`[推断]` **对本报告的直接含义**：主报告 §6.0 第 21 条说"公开的评测方法学与是否面向强监管行业正相关"，Dragon Copilot 是一个**反例边界**——它面向强监管行业，但公开的是**平台级认证**与**客户案例数字**，而不是自己的准确率。**认证可以替代 benchmark 取信**，这是采购路径差异，不是能力差异。

---

## 4. 【本节最重要】FDA：给 L4/L5/L8 三层提供法定规格（C4）

> **这一节是本报告此前完全缺失的一类证据**：前面十二家案例里，"规则该怎么版本化""审计该记什么""变更该谁批"全部是**厂商的做法**；这里第一次出现**监管机构的法定/指南要求**。

### 4.1 完整政策时间线（已确认）

**2019-04-02 讨论稿 → 2021-01 AI/ML SaMD Action Plan → 2021-10 Good Machine Learning Practice → 2023-04 PCCP 草案 → 2023-10 PCCP Guiding Principles → 2024-06 Transparency Guiding Principles → 2024-12-04 PCCP 终版（2025-08-18 重新发布，Docket FDA-2022-D-2628，49 页）**

原始概念是**两个**：**SaMD Pre-Specifications (SPS)**（要改**什么**）+ **Algorithm Change Protocol (ACP)**（**如何**改而保持安全有效），后合并为 **PCCP（Predetermined Change Control Plan）**。

### 4.2 「什么时候不用按医疗器械管」——Non-Device CDS 四要件（**人审边界在监管上的定义**）【一手】

> "Your software function must meet **all four criteria** to be considered Non-Device CDS."
> 1. "Your software function does **NOT** acquire, process, or analyze medical images, signals, or patterns."
> 2. "Your software function displays, analyzes, or prints **medical information normally communicated between health care professionals (HCPs)**."
> 3. "Your software function provides **recommendations (information/options) to a HCP rather than provide a specific output or directive**."
> 4. "Your software function **provides the basis of the recommendations so that the HCP does not rely primarily on any recommendations** to make a decision."

**第 3、4 条就是"人审边界"的法定版本**，而且第 4 条尤其锋利：**你必须把"依据"给出来，以至于人不会主要依赖结论**——这不是"加一句免责声明"，而是**产品功能要求**。

**时敏场景被明确排除**：
> "Software that is meant to support **time-critical** decision making do not meet the definition of Non-Device CDS… In such situations, **it is difficult to support that a clinician is not meant to solely rely on a provided recommendation** or that the clinician will spend time to understand its specific basis."

`[推断]` **这一条对守衡的映射非常直接**：守衡的判定发生在**内容发布前的窗口期**，运营方通常有"急着发"的时间压力。`[推断]` 按 FDA 的逻辑，**时间压力本身就是"人不会真的去看依据"的证明**——因此"给出依据"在设计上必须是**低摩擦的**（一句话结论 + 可点开的证据），而不是要求人读完一份报告。**如果人不可能读，那么"提供了依据"在法律意义上等于没提供。**

### 4.3 「变更要不要人审」——PCCP 对"自动 vs 人工"的法定区分【一手】

> "The Description of Modifications should clearly state if the planned modifications are proposed to be implemented **automatically** (i.e., whether the modifications are implemented automatically by software), whether modifications are implemented **manually (i.e., involving steps that require human input, action, review, and/or decision-making, and therefore are not implemented automatically)**, or a combination of both."

**PCCP 三部分结构**：

| 部分 | 强制内容 |
|---|---|
| **Description of Modifications** | 必须**具体、可验证、可验证性可评估**；**必须声明自动 / 人工 / 两者** |
| **Modification Protocol** | **4 个强制组件**：data management practices、re-training practices、performance evaluation、update procedures |
| **Impact Assessment** | **5 个强制项**，含：每次修改各自的 benefit/risk、**修改之间的相互作用**、**累积影响** |

另必须**预先指定**：研究设计、性能指标、**pre-defined acceptance criteria（预先定义的接受标准）**、统计检验；且**必须同时对照"原版本"与"上一次修改后的版本"**。可追溯性由**traceability table**承担；版本控制靠 **PCCP 标题 + 版本号写进器械授权函**（"the PCCP will be **referenced in the device's letter of authorization, including the PCCP title and version number**"）。

**自动实施会被额外审慎看待**：
> "FDA will consider PCCPs for AI-DSFs for modifications that are implemented automatically. The Agency recognizes that **this subset of AI-DSFs has an additional degree of complexity**…"

**上市前审查是交互式的**，且有一条退路：
> "FDA should work with the manufacturer to revise the PCCP, and will do so using FDA's existing processes to request additional information **through interactive review or through a deficiency letter**. If deficiencies with the PCCP remain unresolved, **FDA may authorize the device upon withdrawal of the PCCP.**"

`[推断]` **PCCP 是本次调研里对本项目 G4 最直接的解法模板**。守衡今天的问题（G4）是"规则只有内容指纹，没有生效时间与批准人"。PCCP 给出的结构是：
- **改什么**（Description）→ 规则 diff
- **怎么改**（Modification Protocol）→ 谁改、怎么验证、什么数据、什么步骤
- **改了有什么影响**（Impact Assessment）→ **含"多条修改之间的相互作用"与"累积影响"**

`[推断]` 其中**"修改之间的相互作用"与"累积影响"这两项是守衡完全没有的视角**——守衡现在的规则库检查是逐条契约校验（217 项），但**没有"这批修改合在一起会不会互相抵消"的检查**。PCCP 把这件事写成了强制项。

### 4.4 审计轨迹的法定规格——21 CFR Part 11（**不是 PCCP**）

> **先记一条实测事实**：**PCCP 终版指南全文 "audit" 出现 0 次**。审计轨迹要求来自 **21 CFR Part 11**。**不要把审计要求归给 PCCP 指南。**

**核心条款 §11.10(e)**【一手·已复验，逐字】：
> "Use of **secure, computer-generated, time-stamped audit trails** to independently record the **date and time of operator entries and actions that create, modify, or delete electronic records**. **Record changes shall not obscure previously recorded information.** Such audit trail documentation shall be **retained for a period at least as long as that required for the subject electronic records** and shall be **available for agency review and copying.**"

§11.10 其余控制项中与本项目直接相关的：**(b)** 必须能生成**人类可读与电子两种形式**的完整记录副本供检查；**(c)** 记录在**整个保留期内**准确且可随时检索；**(g)** **权限检查**（仅授权个人可操作系统、电子签署、访问输入输出设备、改动记录）；**(j)** 须**建立书面政策使个人对其电子签名下发起的行为负责**，目的是 "deter record and signature falsification"；**(k)(2)** 修订与变更控制程序须维护**记录系统文档时间序列性开发与修改的审计轨迹**。

**签名相关**：§11.50(a) 签名记录须含**签署人打印姓名 + 签署日期时间 + 签名的含义**（"such as **review, approval, responsibility, or authorship**"）；§11.70 签名须与记录**绑定**，"ensure that the signatures **cannot be excised, copied, or otherwise transferred** to falsify an electronic record by ordinary means"；§11.100/§11.200 电子签名**唯一对应个人**、非生物特征签名须**至少两个不同身份要素**。开放系统（§11.30）另需**文档加密 + 数字签名标准**。

`[推断]` **§11.50(a) 的第三项——"签名的含义"——是本报告见到的最可操作的一条治理要求**。它要求系统区分：这个签字是 **review（看过）**、**approval（批准）**、**responsibility（担责）** 还是 **authorship（撰写）**。守衡今天的 `legal-decisions-v1.json` 只记"决定了什么"，**没有记"这是谁以什么身份做的什么性质的确认"**。把它补上，成本极低（一个枚举字段），但它把"批准"从一个含糊的词变成了**可追责的类型**。

### 4.5 全生命周期（TPLC）与人机协同的监管表述【一手】

> "Principle Seven discusses placing focus on '**the performance of the Human-AI Team**.' … it is important to understand the performance of the '**Human-AI team, rather than just the performance of the model in isolation**'… rely on the human to interpret the AI outputs and ultimately make clinical decisions."

`[推断]` **"Human-AI team" 是本报告里对"人审"最准确的一个概念化**：它把评测对象从"模型"改成"模型 + 人 + 流程"的组合。这对守衡有直接操作含义——**如果最终结论由运营/法务拍板，那么守衡的评测指标应当包含"人看完守衡的结论后判断的正确率"，而不只是"守衡自己判得对不对"。**

**上市后监测（含一句对本项目极其重要的警告）**：
> "The performance of AI-enabled devices deployed in a real-world environment… **may change or degrade over time, presenting a risk to patients.**"
> "When performance changes do occur, **users may be less likely to identify them** in AI-enabled devices if, for example, the devices are part of a **highly automated process with limited on-going human interaction**"

`[推断]` 这句话从监管侧确认了主报告 §5.4（Luminance「the more routine verification becomes, the less reliable it gets」）与 Harvey「Fewer checkpoints are often a risk signal」的同一个机制：**自动化程度越高，人越发现不了漂移**。三家（监管 + 两家厂商）从三个不同位置说了同一件事。

**透明度设计**（生命周期草案指南）："transparency refers to clearly communicating the **contextually relevant performance and design information**… **Including appropriate transparency information has also been shown to more than double willingness to use a device.**"

### 4.6 一个可复核的规模数字

FDA **AI 器械授权清单**快照中，本次实测**唯一 submission number 共 1,357 个**（`K######`/`DEN######`/`P######` 去重后，表格 1,358 行）。页面**自身未给总数**，且明确声明 "The list is **not a comprehensive resource**"。`[推断]` 这是**请求级计数**，不是官方总数——引用时必须连口径一起说。

---

## 5. 并入主报告的具体行（不新增章节）

| 主报告位置 | 并入什么 |
|---|---|
| **§6.0 共识度速查表** | 新增一行：**「判定应当分成两个正交轴：与源冲突与否（客观可校验）× 影响严重度（需共识判据）」**——证据强度：**个别（Abridge 两轴 taxonomy：Support{Supported/Not supported/Contradiction} × Severity{Major/Moderate/Minimal}，判据用 "most clinicians would agree"）**。`[推断]` 守衡今天只有第一轴，"哪些必须拦"没有依据 |
| **§6.0 共识度速查表** | 新增一行：**「纠错信号应当优先取"零额外成本"的那一个：使用者对 AI 输出的实际修改量」**——证据强度：**个别（Abridge "edits made to the AI-generated note before they are finalized… inherently scalable as a feedback mechanism"）**；与 Harvey「接受的 redline 反馈」同向 |
| **§6.0 共识度速查表** | 新增一行：**「审计轨迹应有法定规格意识，而非自定义」**——证据强度：**个别但强（21 CFR Part 11 §11.10(e)：secure / computer-generated / time-stamped / 不得遮蔽既往信息 / 保留期 ≥ 记录本身 / 可供审查复制）**。`[推断]` 即便守衡不受 FDA 管辖，**这组要求是"审计轨迹"这个概念的行业最严定义**，可作为自检上限 |
| **§6.0 共识度速查表** | 新增一行：**「签字必须带"含义"」**——证据强度：**个别但极强（21 CFR §11.50(a)：签名须标明 review / approval / responsibility / authorship）**；§11.10(j) 要求书面政策使个人对其电子签名下的行为负责 |
| **§6.1 · L4 规则与阈值层** | 补注：**规则层缺的第二轴与变更控制模板**。① Abridge 证明"影响严重度"必须是与"是否冲突"正交的独立维度，且可用共识式定义而非拍脑袋阈值；② **PCCP 三部分结构（Description of Modifications / Modification Protocol / Impact Assessment）可作为规则变更的模板**，其中 **Impact Assessment 的"修改之间的相互作用"与"累积影响"是守衡完全没有的检查项**；③ **Modification Protocol 的 4 个强制组件**（数据管理 / 重训 / 性能评估 / 更新程序）中，守衡已具备"更新程序"，缺前三个的**成文化** |
| **§6.1 · L4（版本化）** | 补注：PCCP 的版本控制方式——**标题 + 版本号写入授权函**（"referenced in the device's letter of authorization, including the PCCP title and version number"）。`[推断]` 守衡的等价物是：**规则的版本号应写入"上游权威源的引用处"**，而不只存在于本地文件 |
| **§6.1 · L5 先例与申诉层** | 补注：**监管侧不存在"申诉"概念，只有 deficiency letter 与召回/不良事件报告（21 CFR 803/806）**。`[推断]` 这意味着申诉/翻案机制**在强监管行业里也没有现成模板**——与法律 AI 三家的结论一致（见 `raw/_distill-legal.md` §4）。**守衡的申诉链路是自己设计，没有行业答案可抄。** |
| **§6.1 · L8 评测与回归层** | 补注：**评测对象应当从"模型"改为"Human-AI team"**（FDA 生命周期指南 Principle Seven 原文："the performance of the Human-AI team, rather than just the performance of the model in isolation"）。`[推断]` 对守衡：指标应包含"人看完守衡结论后判断的正确率"，而非只有"守衡自己判得对不对" |
| **§6.1 · L8（漂移）** | 补注：FDA 官方警告与 Luminance / Harvey 三方同源——"users **may be less likely to identify** them… if the devices are part of a **highly automated process with limited on-going human interaction**" |
| **§5.2（Air Canada 案）附近** | 补强：Abridge 的"证据排序不交给算法"（"**is not a question an algorithm can settle on its own**"）+ FDA Non-Device CDS 第 4 要件（"provides the basis… so that the HCP **does not rely primarily** on any recommendations"）——**权威源认定在医疗是监管要求，不只是工程洁癖** |
| **§5.5 / §1 工具限制** | 新增一条防伪记录：**`nuance.com/healthcare/*` 现全部 302 到同一 Microsoft 模板（三个 URL 字节完全相同）**；真 Nuance DAX 页面只剩 Wayback 快照；产品已于 2025-03-03 并入 Microsoft Dragon Copilot。**后续复核者不得把 `nuance.com` 当一手源。** |
| **附录 G4（规则版本只有内容指纹）** | **最重要的补强**：给出外部强制模板（PCCP 三部分 + 预定义接受标准 + 同时对照原版本与上次修改版本 + traceability table）。并加一句 `[推断]`：**"预先定义接受标准"是这一整套里最难但最值钱的一条**——它要求你在改之前就说清楚"改成什么样算成功" |
| **附 A · 文件清单** | **新增一行**：`kb2agent-research/raw/_sub_medical.md`（Abridge / Microsoft Dragon Copilot / FDA 监管路径，511 行）。**注意与既有的 `_sub-health.md`（700 行，无 FDA 内容）区分：两份是不同轮次的独立调研**，据此可交叉核对同一事实的两次取回是否一致 |

---

## 6. 一处必须写进报告的事实更正（防伪记录）

**`nuance.com` 已经不是 Nuance 的内容源。**

实测：三个不同的 `nuance.com/healthcare/*` URL **返回字节完全相同的 166,321 字节 Microsoft 模板**（302 跳转）。真正的 Nuance DAX Copilot 页面（承载其全部统计数字的那一版）**只存在于 Wayback 2024 快照**。产品已于 **2025-03-03 并入「Microsoft Dragon Copilot」**。

`[推断]` **这条要进正文，因为它和主报告 §1 已记录的那条教训构成一对**：
- 主报告 §1 的教训是"**把检索失败误判为事实缺失**"（Nuance DAX 初稿被判"官方页打不开"）；
- 这一条是它的镜像："**把重定向后的空壳误判为有效来源**"。

两者都是**在证据层出错，而不是在结论层出错**——这正是本报告主张所有结论都带证据等级的原因。

---

## 7. 本文件的边界（它不知道的事）

1. **只有 3 项是本轮独立复验的**（21 CFR Part 11、Abridge 强制人审两句、Microsoft 护士侧一句）；其余【一手】为底稿单轮取回证据，对外引用前建议逐条复取。
2. **1 项复验失败并已降级**：Microsoft「orders are directly entered into the EHR order module」——**原 URL 404、Wayback 本轮连接失败、现行页均无**。已从 §3.2 正文移除，仅作待核项记录。**不得引用。**
3. **FDA 内容全部经 `web.archive.org` 前缀取回**（`www.fda.gov` 直连 404/空）。**Wayback CDX API 全程 "Temporarily Offline"**，故**无法枚举站点、无法保证覆盖完整**；底稿中每条 URL 都是手工构造并逐条验证 200 的。
4. **IMDRF 风险分类原文件未取回**（只有 FDA 的转述页），因此**3×3 单元格到 I–IV 的完整映射刻意未写**，本文件亦不补。
5. **FDA 的 TPLC 独立项目页未取回**（三个候选 URL 全部 404），TPLC 内容取自**生命周期草案指南 PDF（67 页，2025-01，草案——非终版）** 与 Action Plan PDF。**引用时须注意它是草案。**
6. **三家均【未找到公开资料】**：Abridge 的审计日志字段/保留期/查阅权与 SOC 2/HITRUST/ISO 状态；Microsoft 的产品级认证、审计日志规格、准确率指标、申诉流程、责任语言；**FDA 侧没有"申诉"这个机制**（对应物是 deficiency letter 与 21 CFR 803/806 报告）。
7. 本文件**不含**对守衡的落地建议——那部分归 `raw/E-守衡落地建议.md`；本文件§5 只标明"并到哪一行"。
