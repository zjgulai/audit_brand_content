# R8-W2 规则萃取方法学

> 分片：R8-W2（规则萃取方法学的具体操作层）
> 上游依赖：R3-rule-engineering.md §9/§11（Better Rules / LegalRuleML / DPV 标准建模）、R4-trust-and-safety-ops.md §2/§3（policy-to-enforcement、标注手册解剖、错题本）
> 本分片**只补萃取步骤细节与产出物模板**，不重复标准建模
> 撰写日期：2026-09-15
> 工作目录：`/Users/lute/Project/audit_multi_content`

---

## 0. 本部分结论

1. **Better Rules 的唯一一手操作手册已取得，但它是 Draft-02，且六项资源中四项仍标 TODO——它是草稿态材料，不是成熟标准。** 依据：`_evidence/R8/brnz-workshop-manual.md` L8 `Version: Draft-02` + 三处 `#Todo`（L280/286/292）+ `_evidence/R8/w2/betterrules-index.raw` 六项资源四项 TODO 两项 DRAFT。

2. **Better Rules 的输入是"政策+法律+业务规则+服务设计+编码环境"五路并置，客户当前约只到 2/5。** 依据：手册 L86–106 六角色准备清单 vs `01-内部证据-规则表现状审计.md` §1.1（客户只有规则条文，无法律语境映射、无测试套件、`依据来源` 无一条追溯到外部法规）。

3. **Better Rules 的角色分配里，"写规则的人"与"写测试的人"完全不重叠（L248 Business Rules Specialist+Legal Advisor vs L269 Subject Matter+Policy Advisor+Rules-as-code）——这是防止按实现反推需求的结构性保障，客户目前把两者压在同一个人的同一张表里。** 依据：手册 L237/L248/L269 的 Suggested Roles 对照表。

4. **"isomorphic" 是 Better Rules 的核心质量判据：代码不得比规则多出任何逻辑**（手册 L258），而 §1.2.7 的 LRI 论文实证指出 LLM 的头号失败恰是 `over-generalization and hallucination`——**两个独立来源从正反两面指向同一风险面：规则库最容易因"多出逻辑"而失真。** 依据：手册 L258 + arXiv:2505.14104 摘要。

5. **LLM 辅助规则萃取的头号失败模式不是幻觉，而是"产出正确但不回答本条政策的问题"**：原文 `it may produce correct text, but outside the scope of the problem in question`——这类错误没有任何格式信号可检出，因此**必须先有一个已验证的规则格式作为落点，才谈得上上 LLM**。依据：`_evidence/R8/ke-llm-drops.txt` §4.1（⚠️ 该文件实为 ICPEC 2023 编程练习题生成论文，非任务书所称的 knowledge-engineering 论文，见 §1.2 更正说明）。

6. **Mozilla AMO 的 policy-to-enforcement 管道是本分片找到的唯一三段齐全的公开实物，其关键设计是"政策自述为 guiding principles 而非判定规则"，并把执行机制本身编号为第 8 章。** 依据：`_evidence/R7/amo-addon-policies.txt` L2165 `these policies act as guiding principles for those reviews` + 八段编号表（L2185–2385）。

7. **客户"判断方式 21/21 = 自动可检测"与实测 13.8% 复现率不可能同时为真，这是整条改进管道的单点故障。** 依据：审计 §1.1（21/21 填 `自动可检测`）+ §结论先行（正则只能复现 13.8%，72.3% 一条都复现不出来，且从不多报一条）+ AMO 的 `guiding principles` 立场对照。

8. **RuleFit 类数据驱动方法在客户当前阶段不适用，因为其输入前提（已有标注数据 + 有方差的输入变量）客户两条都不满足。** 依据：arXiv:0811.1679 摘要 `linear combinations of simple rules **derived from the data**` + 审计 §1.1（`适用产品`、`判断方式` 等字段 21/21 为常量）+ §1.5.7。

9. **统计学习路径的规模门槛有实证参照：LRI 用了 5,121 个案例组（38,088 份案例）+ 216 组专家金标，客户 291 条记录差两个数量级。** 依据：arXiv:2505.14104 摘要 + 审计 §二。

10. **Feigenbaum 的「knowledge acquisition bottleneck」原始表述与 CommonKADS 建模方法，本分片未找到可核实原文（Springer 书 404、UvA 记录不存在），故本节不写其引文与步骤；但"瓶颈"现象本身有 Better Rules 手册的一手旁证。** 依据：`_evidence/R8/commonkads-book.txt`（HTTP 404）、`_evidence/R8/ck-thesis-uva.txt`（HTTP 200 但正文 `Record not found`）+ 手册 L49 `Policy and rule development has generally been isolated from implementation`。

---

## 1. 方法逐个剖析

### 1.1 Better Rules 转换流程

**本节证据基础**：`_evidence/R8/brnz-workshop-manual.md`（18,728 字节，Hamish Fraser《The Practical Better Rules Workshop Manual》Draft-02，来源仓库 `ServiceInnovationLab/betterrules.nz` 的 `workshop-manual.md`；`_evidence/R8/brnz-tree.json` 用 GitHub Trees API 确认了该 blob 的精确大小 18728 与路径）。这是本分片能找到的 Better Rules **唯一一手操作手册**——不是政策白皮书，是给人照着开工作坊用的流程册。

注意 R3-rule-engineering.md §9/§11 已经从政策层覆盖了 Better Rules 的定位与标准建模对照。**本节只写操作步骤与产出物模板**，不重复。

#### 1.1.1 输入

Better Rules 的输入不是一个文件，而是一组**人和一组域内既有材料**。手册把它们拆成"工作坊准备（Workshop Preparation）"里六个角色各自的预习任务：

| 角色 | 必须带进工作坊的输入 |
|---|---|
| Subject Matter Expert | 一份自己准备的领域初始演讲，目标是让其他成员对该领域的历史与挑战有广泛理解 |
| Policy Advisor | 现行与历史政策立场 |
| Legal Advisor | 现行与历史的**法律语境** |
| Rules-as-code Specialist | 已就绪的编码环境（**含测试套件框架**）+ 一套"非程序员也能用来创建和存放测试"的方法 |
| Service Designer | 一份关于该领域当前服务设计困境的简单报告，写清什么行得通、什么行不通 |
| Business Rules Specialist | 既有的业务流程与规则知识 |

【原文】`_evidence/R8/brnz-workshop-manual.md` L86–106

> ### Subject Matter Expert.
> Prepare an initial presentation on the domain for the team with the goal of giving the other team members a broad understanding of the history and challenges in the space.
>
> ### Policy Advisor.
> Ensure a good understanding of the current and historic policy positions as they relate to the domain is on-hand for them to supply the team
>
> ### Legal Advisor.
> Ensure a good understanding of the current and historic legal context to the subject matter are available to the team.
>
> ### Rules-as-code Specialist.
> Have previous to the project ensured they have a suitable coding environment (with test suite) setup ready to go and an understanding/experience in the process of coding rules. They will also need to have a methodology that non coders can utilise to create and store the tests.
>
> ### Service Designer.
> Establish a good understanding of the service design implications currently faced in the scope of the domain and prepare a simple report outlining what works and doesn't work.
>
> ### Business Rules Specialist.
> Bring existing knowledge of business processes and rules and be prepared to present this perspective to the workshop.

【判断】注意这里有一条对客户极重要的隐含前提：**"政策原文"不被当作输入的全部**。Better Rules 的输入是"政策+法律+业务规则+服务设计+编码环境"五路并置。真正驱动萃取的不是文本，而是这五路之间的**缺口**。对照 `01-内部证据-规则表现状审计.md` 的客户现状（只有规则条文、没有法律语境映射、没有测试套件），客户的输入完整度大约只到 2/5。——依据：上表 vs `01-内部证据-规则表现状审计.md`。

**补充：Better Rules 的官方四项目标（站点首页定义）**

来源：`_evidence/R8/w2/betterrules-index.raw`（1,262 字节，HTTP 200，抓取自 `https://raw.githubusercontent.com/ServiceInnovationLab/betterrules.nz/master/index.html`）。该文件是 betterrules.nz 站点的首页源文件，其正文给出了 Better Rules 的**权威四要素定义**：

【原文】逐字

> **Better Rules is a multidisciplinary approach that seeks to simultaneously address a number of facets in the developing of policy and rules.**
> They are:
> * creating rules and policy that are both **implementable, comprehendable and meet the policy intent**,
> * **comprehending the complexity of the existing legislative space**,
> * intentionally ensuring rules are **implementable on computers where appropriate**,
> * making rules the **digitally consumable component** that is required by the concept of Government as a platform
>
> This resource is focused on documenting the Better Rules practice as it's been developed to date.

【判断】**第二条 `comprehending the complexity of the existing legislative space` 是客户最缺的一环。** 客户 21 条规则的 `依据来源` 只写到「W1卖点表达边界（品线反馈2026-09-10 T4）」或「红绿灯.xlsx 规则库」这类内部出处（审计 §三），**没有任何一条追溯到外部法规**。Better Rules 把"理解既存立法空间的复杂度"列为四个 facet 之一，说明这一步在方法学里是**必需项而非可选项**。——依据：上引原文 + `01-内部证据-规则表现状审计.md` §三。

【判断】**第四条 `digitally consumable component` 与第三条 `implementable on computers where appropriate` 合起来给出了"Do Not Automate Everything"的立场**——注意 `where appropriate`（在适当的地方）这个限定语：**Better Rules 从不主张所有规则都应可被计算机执行**。这与客户 `判断方式` 21/21 全部填 `自动可检测`（审计 §1.1）形成直接对照，也是 §3.0 二分的规范依据。——依据：上引原文。

⚠️ **站点自身的完成度记录**（同一文件逐字）：`The Better Rules Manifesto (TODO)` / `The Practical Better Rules Workshop Manual (DRAFT)` / `The Better Rules Workshop Example (DRAFT)` / `A Better Rules introduction to rules-as-code (TODO)` / `A Better Rules introduction to test suites (TODO)` / `Contributing guide (TODO)`。**六项资源中四项标 TODO、两项标 DRAFT。** 引用时须保留此状态。

#### 1.1.2 步骤（含逐字引用）

手册把流程定为两段：**先概念建模，后并行产出**。

**步骤 1｜目标确认（Objectives）**。手册要求先明确本次是三类目标中的哪一个或哪几个组合：

【原文】L180–183

> Be clear with respect to the objectives of the group. This will be one or a combination of the following.
> * Understanding, mapping and coding the existing rule space
> * Clarifying and clearly stating the policy intent
> * Modifying or adding to the existing rule space to match the policy intent.

**步骤 2｜团队动力学（Team Dynamics）**，这是一个独立步骤而不是软性建议：

【原文】L187–191

> Ensure each member of the group is comfortable in sharing their perspective and confident in disagreeing/questioning the rest of the group; this team dynamic is important for ensuring success. If the team are new to each other it's advisable to set aside time to foster a sense of trust and undertake some team-building/ice-breaking activities.
>
> Once this has been achieved the team is ready to start.
>
> **The Subject Matter Expert** should open with their pre-prepared presentation on the topic. This introduction is a good time to set the scene and declare the objectives of the exercise so the Policy roles will likely co-present.

**步骤 3｜概念建模（How to Concept Model）**——这一步在工作坊的**第一场演讲期间就开始**，不等演讲结束：

【原文】L195–207

> Work should start immediately (during the initial presentation) on developing the Concept Model and can be facilitated by other team members.
>
> The Concept Model is initially a messy process and one should keep in mind its purpose. The overriding role of the concept model is to provide a focal point that allows the group to form a shared consistent view of the domain.
>
> Expect it to be redrawn multiple times and plan accordingly. Post-it notes directly to whiteboard is not a bad starting approach for this reason. Utilise the whiteboard to draw connections. Connections can be labelled. Do not get distracted by logic flows, that comes later.
> As the above example shows: beard and "beard tax" are identified as concepts - they are then linked with the concept "person" - the word used in the current rule set. Age is also identified and posted close to "claimant" as it applies to that concept.
>
> Expect a sense of agreement to develop within the group and for that  to be suddenly interrupted by disagreement, repeatedly. The concept model provides a focal point to work out disagreements in how the model is perceived and will be modified often as part of this process. This is the concept model fulfilling its purpose.
>
> Creating an _"out of scope"_ section can help keep the group in agreement on the scope of the project and remind people of what has been previously discussed and ruled _"out of scope"_.

【判断】"Do not get distracted by logic flows, that comes later" 是一条可执行的**阶段禁令**：概念建模阶段不许画 if-then。这与客户现状中"规则与概念混在一张表里"直接冲突。——依据：L202 vs `01-内部证据-规则表现状审计.md`。

**步骤 4｜切换到并行产出（The Process）**。这一步的机制是**按单条规则迭代，而不是按产出物批处理**：

【原文】L211–215

> Once the concept model is underway and team members believe it's reached a level of maturity and clarity which they're comfortable with - a number of other activities which contribute to the output of the workshop (described below) can be added to the group's work flow.
>
> Focus the individual team members as outlined below on their appropriate tasks but to try and work through the process as a collective, sharing into the wider group the questions inspired by their respective tasks. Each of the tasks is likely to throw up new insights and changes to the concept model - and these will need to be absorbed and discussed by the whole team. Iterative over each of the rules individually so each task has an opportunity to interrupt and inform the other parts of the team while they are looking at the same components. While this feels somewhat slower, it allows the group to be giving full consideration to each point as they move through the processing of the tests, rules and service modelling impacts which will often result in a more thorough and ultimately more efficient process.

【判断】这是一条反直觉但明确的耗时取向：**"While this feels somewhat slower"**——手册自己承认单条迭代看起来更慢，并主张它最终更高效。任何"先批量把 21 条规则都过一遍再统一写测试"的计划，都与手册的流程相悖。——依据：L213。

**步骤 5｜开发规则（Developing the Rules）**，含 what-if 扰动法：

【原文】L220–232

> Note this activity can differ a little depending if existing rules are being unpacked or new rules being written or both. Regardless, it's important to keep the rules tied directly to the concept model which is the group's shared understanding of the domain. This is best done by ensuring the terminology used is kept consistent.
>
> The process for new rules starts with the Policy Advisor giving an outline of the proposed new rules from their research in the domain. Each of the team will likely have perspectives to share on what's proposed.
>
> Each of the outputs of the workshop are designed to highlight gaps and inconsistencies in the rules. It's often helpful in analysis of the rules to play with "what-if" statements that focused on changing variables that are often assumed.
>
> For example, what if the:
> * location (i.e. not in the country)
> * timing (change the order of events)
> * role (the caregiver is a child)
> * classification (they are not citizens)
>
> is X and does our ruleset account for that. This is a useful practice to apply during the development of the test suites which we will detail shortly.

【判断】**这是本节最可迁移的单条技术。** 四个扰动轴（location / timing / role / classification）是现成的、可立即套用到客户 21 条规则上的边界用例生成器。手册明确说它"在测试套件开发期间使用"。——依据：L226–232。§1.1.6 与 §3 会复用这条。

**步骤 6｜各产出物的并行开发**，手册给每个产出物标注了建议角色：

- 决策树（Developing Decision Trees）：`**Suggested Roles:** [Legal Advisor, Business Rules Specialist, Service Designer, Rules-as-code Specialist]`（L237）
- 业务规则陈述（Developing Business Rule Statements）：`**Suggested Roles:** [Business Rules Specialist, Legal Advisor]`（L248）
- 规则即代码（Developing Rules-as-Code）：`**Suggested Roles:** [Rules-as-code Specialist, Legal Advisor]`（L256）
- 测试套件（Test Suites）：`**Suggested Roles:** [Subject Matter Specialist, Policy Advisor, Rules-as-code Specialist]`（L269）
- 问题与问题流（Questions & Question Flows）：`**Suggested Roles:** [Service Designer, Business Rules Specialist, Rules-as-Code Specialist]`（L278）
- 服务设计研究（Service Design Research）：`**Suggested Roles:** [Service Designer, Subject Matter Expert]`（L284）
- 流程流（Process Flows）：`**Suggested Roles:** [Business Rules Specialist, Service Designer]`（L290）

【判断】角色分配揭示了一条**职责分离规律**：写规则陈述的是 Business Rules Specialist + Legal Advisor；写测试的是 Subject Matter + Policy Advisor + Rules-as-code。**写规则的人和写测试的人不是同一组**。这是防止"按实现反推需求"的结构性保障。——依据：L248 vs L269。

#### 1.1.3 产出物

手册对一个产出物的成熟度做了明确分级：**base requirement（基线必需）** 与 **optional output（可选产出）**，并声明选哪些"取决于工作坊的语境与目的"。

【原文】L111–112

> A brief introduction to each of the outputs. Outputs are marked as either **base requirements** or **optional outputs**. Choosing which outputs are focused on will be dependant on the context and purpose of the workshop.
> The outputs could be incorporated into the enveloping institution's documentation and kept as foundational reference material for the rules that have been brought into effect.

逐项产出物定义（含手册原文）：

**① 概念模型 Concept Models｜`[base requirement]`**

【原文】L118

> Concept models form a working map of the concepts that make up the domain the team is focusing on and are the essential central component to the workshop's process. They allow the team to create a visual shared understanding of the domain and its scope, and it becomes a reference point that allows all the other expected outputs to achieve a high level of consistency. It is also the central mechanism for quantifying and resolving disagreements and differences in perspective and as such is constantly evolving and improving over the lifetime of the workshop.

【判断】"the central mechanism for **quantifying** and resolving disagreements" 是一个强主张：概念模型是**分歧的计数器**，不只是共识的可视化。手册紧接着写 "Expect a sense of agreement to develop within the group and for that to be suddenly interrupted by disagreement, repeatedly... This is the concept model fulfilling its purpose."（L205）——**分歧的反复出现被定义为方法在正常工作**，不是方法失败。——依据：L118 + L205。

**② 决策树 Decision Trees｜`[optional output]`**

【原文】L124

> Decision trees map the logic and ways people and systems practically navigate the concept models. Experience suggests these maps can take anywhere from a few minutes to several days depending on the complexity of the concept model and the more complex ones will be revisited often in the same manner as the concept model. Their development will often result in changes to the concept model.

以及 L242：

> A decision tree is created by taking the elements of the concept model and organising them in an order that represents the sequence (if there is one) that people and systems would use to navigate the process. They provide the opportunity to look at the logic dependencies that exist in the domain. It provides another way to describe the domain and will often highlight inefficiencies in the approach and inaccuracies in the concept model.

**③ 业务规则陈述 Business Rule Statements｜`[base requirement]`**

手册给了一个**完整的格式样例**（这是本分片能拿到的最具体的规则陈述模板）：

【原文】L130–136

> Business rule statements are precisely written statements of logic describing each rule in a set of rules succinctly. An example might look like:
>
> "A person is eligible to vote if:
> * their age is 18 years or more, and
> * they have lived in the district for 6 months"
>
> Business rule statements are useful for both drafters and coders in establishing statements of logic. Note their dependency on the terms used and how they map to the concept model.

L250 补充了写法约束：

> The business rules specialist keeping the concept model in mind, starts the process of crafting the statements that make up the individual components of logic within the domain. Keep in mind the order of these is often related to the decision trees. It's important to try and keep each line or statement precise and describing a single point.

【判断】模板的形态学要点（可抽出四个槽位）：`<主体 concept> is <谓词> if: <条件列表，用 and 连接>`。且手册明确要求**一条件一行、每行只描述单一要点**（"keep each line or statement precise and describing a single point"）。这直接对应客户"把复合条件挤在一格里"的典型缺陷。——依据：L132–134 + L250。

**④ 规则即代码 Rules-as-Code｜`[base requirement]`**——手册对它的定位不是"实现"，而是**测试政策的手段**：

【原文】L141–144

> Rules-as-code are best thought of as an opportunity to test the policy by trying to explain it to a computer. A phrase coined in response to this practice is:
> "You haven't really understood your policy until you've successfully explained it to a machine".
> The underlying explanation as to what happens in this process is the machine acts as an utterly unassuming context-free entity that by its nature aids in the discovery of assumptions that we miss much more easily as humans. This process on it's own is enough to warrant undertaking the creation of this output however once the rules are written there are many other uses for them.

以及 L258 的**同构性（isomorphism）**要求：

> While coding the rules, it's expected that the rules-as-code specialist keeps an eye on the underlying concept model and any assumptions they may find themselves making while developing the code should be raised. The art of coding rules is to be very careful to not include any assumptions or extensions of logic accidentally into the code but faithfully mirror the rules in an isomorphic fashion.

【判断】"isomorphic" 是本方法学的**核心质量判据**：代码不得比规则多出任何逻辑。可操作化为一条验收测试——把 rules-as-code 里每一个判断条件回溯到业务规则陈述的某一行，回溯不到的即为"偷偷引入的假设"，必须显式化或删除。——依据：L258。

手册列出的 rules-as-code 用途（L260–264）：启用测试套件 / 提供可运行的实现模型 / 允许像发布法条文本一样发布代码（并以新西兰为例）/ 与既有数据集结合做规则集效果建模（建立在 "digital twin" 这类概念之上）。

**⑤ 测试套件 Test Suites（aka Policy Intent）｜`[base requirement]`**——手册把它定义为**政策意图的载体**：

【原文】L150

> Test suites are an adoption from the world of software development. Think of them as capturing and preserving policy intent. A test is a description of a scenario with given inputs and what the expected output(s) should be. Couple this concept with rules-as-code and it's possible to write thousands of tests for all conceivable scenarios and leverage computers to run those tests in an automated fashion. They provide an easy bridge for non programmers to engage with the coding aspect of rules-as-code by being involved in the writing of the tests and studying the results.

L271–273 给出执行细节与**低技术兜底方案**：

> The rules-as-code specialist will need to advise on the format for the tests (a spreadsheet can be a low tech solution) so they can later be converted into code and run against the rules-as-code output. They should also be relied upon to give an introduction to test writing, documentation requirements and good practice.
>
> Writing tests is initially an exercise in expressing the policy intent but then switches to an exhaustive analysis of possible scenarios. If the rules-as-code specialist is not yet sure of the format of the tests, the scenarios can be described in spreadsheets ready for importing alongside the code.

【判断】"a spreadsheet can be a low tech solution" 是**给客户的降级路径**：不需要先建规则引擎，用表格写"输入列 + 期望输出列"即可开始。且手册给出了测试写作的**两阶段性质**：先"表达政策意图"，后"穷举可能场景"——这两个阶段的目标函数不同（前者求忠实，后者求覆盖）。——依据：L271–273 + L150。

**⑥–⑧ 三个可选产出**：Questions & Question Flows（L156 定义，规则反推问题：如"the height of the building cannot exceed 10 metres" 推出问题 "What is the height of the building?"；问题常是层级式的，是否需要问取决于前序答案）、Service Design Research（L162，分析规则对服务交付与人们获取服务的影响）、Process Flows（L168，支持规则所需的流程的详细流程图，"especially useful in questioning how implementable a ruleset is"，常因角色视角不同而有多张）。

⚠️ **重要缺口记录**：手册中 Questions & Question Flows（L280）、Service Design Research（L286）、Process Flows（L292）三节正文均为 `#Todo`，**只有角色分配没有步骤**。故这三项产出的操作步骤在本分片中列为"未找到"。

#### 1.1.4 谁执行

【原文】L56–62（团队编制）

> _(Aim for approximately nine people)_
> * 1-2x Subject Matter Specialist
> * 1-2x Policy Advisor
> * 1-2x Legal Advisor &/or Legal Drafter/Parliamentary Counsel Representative
> * 1-2x Rules-as-Code Specialist
> * 1-2x Service Designer
> * 1-2x Business Rules Specialist

**建议人数约 9 人，六种角色各 1–2 人。** 注意 Legal 那一格写作 "Legal Advisor &/or Legal Drafter/**Parliamentary Counsel** Representative"——手册预期立法起草人本人可能到场。

【原文】L49（为什么必须是多学科）

> The key component is the multidisciplinary team. Policy and rule development has generally been isolated from implementation and this idea of getting everyone in the room is at the heart of "Better Rules".

【原文】L68–76（场地与道具清单，直接可执行的采购/预约单）

> * Comfortably sized room
> _(This could be tackled by a remote team however fluid communication is essential so internet connections would need to be up to the task.)_
> * 2-3x Whiteboards
> * Post It Notes
> * Coding environment for rules-as-code specialist
> * 2x Large screens
> * 2x Computers (for business rules and rules-as-code specialists)
> * Camera (for photographing whiteboards)
> * A clear understanding of what "the domain" is the group will be focusing on.

【判断】道具清单里 **"Camera (for photographing whiteboards)"** 是一个被低估的关键项：手册明确说概念模型会"be redrawn multiple times"（L202），所以概念模型的**版本序列**（照片）本身就是产出物的一部分，最终版反而信息量最小。——依据：L76 + L202 + L118（"constantly evolving"）。

#### 1.1.5 需要多久

⚠️ **本分片的证据中，手册没有给出总时长。** 唯一出现的量化时长是关于决策树的：

【原文】L124

> Experience suggests these maps can take anywhere from a few minutes to several days depending on the complexity of the concept model and the more complex ones will be revisited often in the same manner as the concept model.

【判断】可核实的只有"决策树：几分钟到几天，取决于概念模型复杂度"。**总工作坊时长、各产出物的工时占比，在现有证据中均未找到。** 任何"Better Rules 需要 X 天"的说法在本分片证据下不可采信。

一条间接的耗时取向证据（L213）："While this feels somewhat slower, it allows the group to be giving full consideration to each point"——手册预期单条迭代路径**主观上更慢**，并认为这是正确的取舍。

#### 1.1.6 失败模式

手册没有独立的"失败模式"章节，但正文中散布了多处**显式的禁令与预期困难**。逐条提取（这些都是原文字面，不是我的归纳）：

| # | 失败模式 | 手册原文 | 位置 |
|---|---|---|---|
| F1 | **在概念建模阶段就跑去做逻辑流** | "Do not get distracted by logic flows, that comes later." | L202 |
| F2 | **概念模型被当成一次成型的交付物** | "Expect it to be redrawn multiple times and plan accordingly." / "constantly evolving and improving over the lifetime of the workshop" | L202 / L118 |
| F3 | **团队不敢互相反驳** | "Ensure each member of the group is comfortable in sharing their perspective and confident in disagreeing/questioning the rest of the group; this team dynamic is important for ensuring success. If the team are new to each other it's advisable to set aside time to foster a sense of trust" | L187 |
| F4 | **规则用词与概念模型脱钩** | "it's important to keep the rules tied directly to the concept model... This is best done by ensuring the terminology used is kept consistent." | L220 |
| F5 | **代码偷偷引入规则里没有的假设** | "The art of coding rules is to be very careful to not include any assumptions or extensions of logic accidentally into the code but faithfully mirror the rules in an isomorphic fashion." | L258 |
| F6 | **范围蔓延 / 反复争论已排除项** | "Creating an _'out of scope'_ section can help keep the group in agreement on the scope of the project and remind people of what has been previously discussed and ruled _'out of scope'_." | L207 |
| F7 | **各产出物分头做、互不打断** | "try and work through the process as a collective, sharing into the wider group the questions inspired by their respective tasks. Each of the tasks is likely to throw up new insights and changes to the concept model" | L213 |
| F8 | **把方法论当权威照抄** | "Consider this document a starting guide... Do not treat this document as authoritative; instead use it to get your team and workshop started and then adapt to suit." | L48 |
| F9 | **被学科术语吓退、放弃使用产出物** | "Each of the outputs represent large academic fields with complex and intimidating terminology so use these outputs as tools and keep your focus on using them at the depth you require to achieve better rules." | L50 |

【原文】L48–50（F8/F9 合并的完整语境）

> Consider this document a starting guide. It's a methodology we've developed based on experiments that were conducted in the Service Innovation Lab in New Zealand. Do not treat this document as authoritative; instead use it to get your team and workshop started and then adapt to suit.
> The key component is the multidisciplinary team. Policy and rule development has generally been isolated from implementation and this idea of getting everyone in the room is at the heart of "Better Rules".
> Each of the outputs represent large academic fields with complex and intimidating terminology so use these outputs as tools and keep your focus on using them at the depth you require to achieve better rules. Rules for humans should be approachable and understandable and so should the methods used to develop them.

**版本状态风险（F10，来自文件元数据而非正文）**：标题页写着 `Version: Draft-02`（L8），正文含 ≥3 处 `#Todo`（L280/286/292），`workshop-example.md` 全文只有 `#TODO`（53 字节），站点根 `betterrules.govt.nz` 对应仓库 `betterrules.nz` 已迁至 `www.digital.govt.nz` 之下且**该路径返回 404**（见 §4）。故本手册应被引用为**草稿态一手材料**，引用时须保留 Draft-02 版本号。

---

### 1.2 法规文本 → 规则的 NLP 自动化

> ⚠️ **证据标签更正（必读）**：本分片任务书把 `_evidence/R8/ke-llm-drops.txt` 描述为"一篇 knowledge-engineering-with-LLM 的论文"。**经逐字核验，该描述不成立。** 该文件实际是 DROPS/Dagstuhl 的 ICPEC 2023 会议论文《NLP/AI Based Techniques for Programming Exercises Generation》（Tiago Carvalho Freitas、Alvaro Costa Neto、Maria João Varanda Pereira、Pedro Rangel Henriques），讲的是**用 NLP/LLM 半自动生成编程练习题**。文件头 `SOURCE_URL: https://drops.dagstuhl.de/storage/01oasics/oasics-vol112-icpec2023/OASIcs.ICPEC.2023.9/OASIcs.ICPEC.2023.9.pdf`，`HTTP: 200`，`BYTES: 622938`。
> **它不是法律领域文献。** 本节把它当作**方法骨架的类比证据**使用（NL 规格 → LLM 生成候选 → 结构化产物 → 可自动执行的校验），并在每处明确标注。"法规条文专用的萃取论文"见 §1.2.7。

#### 1.2.1 输入

**两类输入，性质完全不同：**

**（A）真实法规文本的形态。** 本分片手上有两份 EUR-Lex 全文（`_evidence/R8/dsa-art34-eurlex.txt` 419KB、`_evidence/R8/eu-aiact-art6-eurlex.txt` 589KB）。以 DSA 第 34 条为例，法规文本的**结构特征**是高度规律的——这恰恰是它可被自动化的原因：

【原文】`_evidence/R8/dsa-art34-eurlex.txt` L1713–1735

> Article 34
>
> Risk assessment
>
> 1. Providers of very large online platforms and of very large online search engines shall diligently identify, analyse and assess any systemic risks in the Union stemming from the design or functioning of their service and its related systems, including algorithmic systems, or from the use made of their services.
>
> They shall carry out the risk assessments by the date of application referred to in Article 33(6), second subparagraph, and at least once every year thereafter, and in any event prior to deploying functionalities that are likely to have a critical impact on the risks identified pursuant to this Article. This risk assessment shall be specific to their services and proportionate to the systemic risks, taking into consideration their severity and probability, and shall include the following systemic risks:
>
> (a)
>
> the dissemination of illegal content through their services;
>
> (b)
>
> any actual or foreseeable negative effects for the exercise of fundamental rights, in particular the fundamental rights to human dignity enshrined in Article 1 of the Charter, to respect for private and family life enshrined in Article 7 of the Charter, to the protection of personal data enshrined in Article 8 of the Charter, to freedom of expression and information, including the freedom and pluralism of the media, enshrined in Article 11 of the Charter, to non-discrimination enshrined in Article 21 of the Charter, to respect for the rights of the child enshrined in Article 24 of the Charter and to a high-level of consumer protection enshrined in Article 38 of the Charter;
>
> (c)
>
> any actual or foreseeable negative effects on civic discourse and electoral processes, and public security;
>
> (d)
>
> any actual or foreseeable negative effects in relation to gender-based violence, the protection of public health and minors and serious negative consequences to the person's physical and mental well-being.

【判断】**法规文本可自动化的四个结构特征**（均可从上文直接读出，不是我的推测）：
1. **编号层级稳定**：`Article N` → 段落号 `1.` `2.` → 字母项 `(a)` `(b)`。这是天然的 AST 结构。
2. **道义模态词固定且少**：上段出现 `shall diligently identify, analyse and assess`、`shall carry out`、`shall be specific`、`shall include`；第 35 条（L1769）出现 `shall put in place`、`may include`。**`shall`（义务）/ `may`（许可）/ `shall not`（禁止）** 是道义算子，可直接映射到规则的 effect 类型。
3. **交叉引用密集**：`Article 33(6), second subparagraph`、`Article 1 of the Charter`、`Article 34(1)`。**交叉引用是自动化最大的工程负担，也是最大的价值点**——人工手工解析这些引用正是客户最花时间的部分。
4. **条件与后果常不在同一句**：第 34(1) 段的条件（"Providers of very large online platforms..."= 适用主体）在段首，义务在段中，期限（"by the date of application referred to in Article 33(6)"）在下一段。**规则边界 ≠ 句子边界**，这是分句策略必须先解决的问题。

**（B）NL 规格文本（类比证据）。** ICPEC 那篇论文的输入是"出题意图的自然语言描述"，其形态学与"政策意图描述"同构。它把目标产物拆成三个固定部件——**这三个部件恰好可以一一映射到规则萃取的三件套**：

【原文】`_evidence/R8/ke-llm-drops.txt` L182–208（§2.2 Exercise Components）

> It is important to understand the components that make up a programming exercise in order to effectively design and create them. There are usually three main components that need to be considered:
> Problem Statement:Initial component containing text that is presented to the student. It explains the context and parameters of the problem, and the type of answer they must provide. It can be lengthy if the topic needs an introduction or concise and objective if it only requires the essential instructions for solving the problem. It is important to provide enough information to solve the problem, specially when the domain is unknown to the student.
> Code: Most programming exercises contain a section dedicated to code snippets...
> Answer field or options:There are two usual possibilities for the answer section, either a designated space or an area embedded in another component...
>
> While not a component in itself, the evaluation of the students' answers must be taken into account. Its complexity may vary depending on the type of the exercise, ranging from a direct verification of the correct option, to more sophisticated mechanisms, such as a set of tests performed on the code that the student has written. Although, some characteristics of the answers present a qualitative nature that prevents its automatic evaluation, such as code sophistication and legibility.

【判断】三部件 → 三件套的映射：`Problem Statement` ≈ **规则的适用场景描述**；`Code` ≈ **可执行的规则本体（rules-as-code）**；`Answer field or options` ≈ **判定结论**；而 "evaluation ... ranging from a direct verification of the correct option, to ... **a set of tests performed on the code**" ≈ **测试套件**。这与 §1.1.3 中 Better Rules 的 `概念模型 / 规则陈述 / 规则即代码 / 测试套件` 四件套在结构上收敛，且**相互独立地**都指向"必须有可自动执行的校验层"。——依据：本段 vs §1.1.3。

最后一句对规则萃取的直接含义：**"some characteristics of the answers present a qualitative nature that prevents its automatic evaluation"**——作者明确承认有一类产物**无法自动评估**（在他那里是代码优雅度与可读性）。对应到规则领域，就是 R4 §2 反复出现的那类"依赖意图/语境"的条款。

#### 1.2.2 步骤

把 ICPEC 论文的生成管线**逐级对齐**到规则萃取：

**步骤 1｜确定内容（Content Determination）**——哪些信息要进入产物。

【原文】`_evidence/R8/ke-llm-drops.txt`；Reiter & Dale 的六项 NLG 任务，论文逐字列出（§3 Text Generation）

> This process involves taking input data, such as keywords or a set of facts, and transforming them into meaningful output text. Reiter and Dale [25] identified six tasks that are essential for NLG, still present in current models:
> 1. Content Determination:Deciding what information should be included in the text under construction;
> 2. Discourse Planning or Text Structuring:Defining in which order information will be presented and the structure of such presentation;
> 3. Sentence Aggregation:Grouping information into sentences;
> 4. Lexicalization: Deciding which words and phrases should be chosen to express the required information;
> 5. Referring Expression Generation:According to Reiter and Dale [25], it consists of "selecting the words and phrases to identify domain objects";
> 6. Linguistic Realisation: Combining all words and phrases by applying grammatical rules to produce a text which is syntactically and orthographically correct.

同处给出三阶段管线：

> This type of system can be built using different architectures, being the most common the three-stage pipeline, also proposed by Reiter and Dale [24]. The pipeline includes text planning, sentence planning, and linguistic realisation. In text planning, content determination and discourse planning are combined to decide what information to include and how to structure it. In sentence planning, sentence aggregation, lexicalization, and referring expression generation are combined to select words and phrases and group them into sentences. Finally, in linguistic realisation, grammatical rules are applied to produce a syntactically and orthographically correct text.

【判断】**反向使用这六项任务，就得到条文→规则的分句算法。** 六项里第 3 项（Sentence Aggregation，把信息分组成句）的反操作就是**拆句**；第 4 项（Lexicalization，选词）的反操作就是**术语归一**（把 "very large online platform" 在所有条款中的变体归到一个 concept，这正是 §1.1 概念模型的自动化版本）；第 5 项（Referring Expression Generation，指代消解）的反操作就是**交叉引用解析**（把 "Article 34(1)" 展开回它指向的条件集合）。——依据：本段 + §1.2.1 第 3/4 条结构特征。

**步骤 2｜LLM 生成候选。** 论文的第 4 节用四个不同的生成机制做了对照实验（OpenAI API / Finetuning GPT-2 / Key-to-Text / CodeT5），并给出可复现的调用参数：

【原文】L333–338 附近（§4.1）

> OpenAI has made available APIs to GPT-3 and GPT-3.5 models. Using an access token it is possible to make requests by sending a prompt with a certain maximum number of tokens, which will be answered with the generated text. Each of these models has some variations: some are applied to simpler and faster tasks while others are used for more complex text generation.

以及 L341 的成本数字（**这是本分片唯一的、可核实的 LLM 单位成本数字**）：

> Despite its technical capacity and current popularity, there is an important tangential disadvantage: the API is not completely free. After a gracing period of three months, there are monetary usage fees for the different OpenAI models, which despite appearing minimal (GPT-3.5 is 0.002$ per 1K tokens) may become a problem in an academic context with a lot of tests.

【判断】`GPT-3.5 is 0.002$ per 1K tokens` 是 2023 年的价格，**不可直接用于 2026 年的预算测算**，但它给出了一个量级锚点：**批量规则萃取的主要成本约束不是单次调用，而是"a lot of tests"带来的重复调用次数**。论文自己把这个成本命名为 "a problem in an academic context with a lot of tests"。——依据：L341。

论文给出了一个**完整的 prompt 模板与输出样例**（Figure 2），这是可直接改造的模板：

【原文】L362–375 附近

> Source:
> prompt = """ E x e r c i s e
> I n s t r u c t i o n s :
> Write a P y t h o n p r o g r a m to r e v e r s e a s t r i n g .
> Code : """
> model . g ene ra te ( prompt = prompt , m a x _ l e n g t h =500 , t e m p e r a t u r e =0.3 , top_p =0.9)

【判断】**模板的形态是可迁移的**：一个极短的结构化 prompt（角色标签 `E x e r c i s e` / `I n s t r u c t i o n s :` / 输出槽 `Code :`）+ 低温度（`temperature=0.3`）。对应到规则萃取：`【条文】… 【道义算子】… 【条件】… 【后果】…` 的四槽 prompt。注意论文用的是 **低温度**——萃取任务要的是可复现，不是多样性。——依据：上引参数 + §1.2.6 的"scope 漂移"失败模式。

**步骤 3｜用测试做校验（而不是用人工逐个读）。** 见 §1.2.1 已引的 §2.2 末段：评估手段"ranging from a direct verification of the correct option, to more sophisticated mechanisms, such as **a set of tests performed on the code**"。

【判断】这条与 Better Rules 的 Test Suites 是**同一设计**（§1.1.3 ⑤："Think of them as capturing and preserving policy intent"），且 **ICPEC 论文与 Better Rules 手册互不引用**。两处独立收敛到同一形态，是本分片最强的交叉验证之一。——依据：本节 vs §1.1.3。

**步骤 4｜人工校验并回流。** 论文的 4.5 Summary 与 5 Conclusion 给出的结论是"当前模型可作为助手而非替代"：

【原文】L499 起（§5 Conclusion，摘要句）

> This paper focuses on the enhancement of computer programming exercises generation to the benefit of both students and teachers. By exploring Natural Language Processing (NLP) and Machine Learning (ML) methods for automatic generation of text and source code, it is possible to semi-automatically construct programming exercises, aiding teachers to reduce redundant work and more easily apply active learning methodologies.

【判断】关键词是 **"semi-automatically"** 与 **"aiding teachers"**。论文从未主张全自动；它把人的角色定为"减少重复劳动"，而非"退出环节"。——依据：上引摘要。

#### 1.2.3 产出物

| 产出物 | 对应 ICPEC 部件 | 对应 Better Rules |
|---|---|---|
| 归一化条文 AST（Article → 段 → 项） | Problem Statement 的结构部分 | 概念模型的自动化前置 |
| 道义算子标注（shall/may/shall not → 义务/许可/禁止） | —（无对应） | 规则陈述的模态 |
| 消解后的交叉引用图 | —（无对应） | 概念模型的连接边 |
| 候选规则陈述（待人工确认） | Code | Business Rule Statements |
| 可执行规则（rules-as-code） | Code | Rules-as-Code |
| 自动测试集 | "a set of tests performed on the code" | Test Suites |

【判断】ICPEC 论文**没有**道义算子标注与交叉引用图这两个产出物——因为编程练习题不需要。**这两项是法规文本特有的增量**，其方法学证据见 §1.2.7。不要从 ICPEC 论文里给这两项找依据。——依据：本表缺列 + §1.2.7。

#### 1.2.4 谁执行

论文的实验主体是**教师**（"aiding teachers to reduce redundant work"），人机分工是"机器生成候选、人筛选用"。——依据：L20 摘要。

【判断】迁移到规则萃取：**条文解析（步骤 1）与交叉引用消解可完全交给工程/自动化；道义算子标注可由 LLM 初标 + 法务复核；候选规则陈述必须由人确认（§1.1.1 已证明 Better Rules 把这一步分配给 Business Rules Specialist + Legal Advisor 双人）。**——依据：本节 + §1.1.2 步骤 6 的角色表。

#### 1.2.5 需要多久

⚠️ **本分片未找到任何关于"法规→规则 NLP 管线"的耗时实证。** 论文未报告其四组实验的耗时（只报告了 API 价格）。Better Rules 手册亦未报告耗时（§1.1.5）。**两者都属"未找到"。**

唯一可用的量级锚点是 §1.1.5 与 R4 §2.1 的两条：决策树几分钟到几天（Better Rules 手册 L124）；平台侧 enforcement guideline 迭代 **"can take a few months"**（R4 §2.1 逐字引 YouTube 官方博客）。

#### 1.2.6 失败模式

**【最重要的失败模式——原文直给】**

【原文】`_evidence/R8/ke-llm-drops.txt`（§4.1，OpenAI API 小节）

> The only disadvantage that was realised about the quality and effectiveness of the results is the possible incoherence derived from the lack of context of the model, that is, **it may produce correct text, but outside the scope of the problem in question**. To improve this, OpenAI also provides the option of fine-tuning, in which the model is further trained with a shorter dataset to perform a specific task. By fine-tuning GPT, it would be possible to obtain faster and more adequate results, in the sense that the exercises and their parts would be in accordance with a pre-defined structure and better contextualised with the domain in question.

【判断】**"it may produce correct text, but outside the scope of the problem in question" 是 LLM 辅助规则萃取的头号失败模式，而且它比"幻觉"更隐蔽。** 幻觉是无中生有，容易被察觉；这一条是**生成了一段完全合法、清晰、格式正确的规则，但它回答的不是这条政策要管的事**。在规则库里它表现为"多出来的第 22 条规则"，没有任何语法或格式信号能提示它是错的。论文给出的缓解手段是 **fine-tuning**（用较短的数据集进一步训练以获得"a pre-defined structure"和"better contextualised with the domain"）。——依据：上引原文。

迁移到客户的 21 条规则场景：**缓解手段不是微调，而是"范围锁"——要求每个候选规则必须能回溯到原文的某一具体条款与某一句。** 这与 Better Rules 的 isomorphic 要求（§1.1.3 ④）是同一条防线。

**其他失败模式：**

| # | 失败模式 | 证据 |
|---|---|---|
| N1 | **范围漂移**：产出正确但答非所问的规则 | 上引原文（§4.1） |
| N2 | **有一类产物天然无法自动评估** | §2.2 末段：`some characteristics of the answers present a qualitative nature that prevents its automatic evaluation` |
| N3 | **上下文不足导致模型不知领域** | §2.2：`It is important to provide enough information to solve the problem, specially when the domain is unknown to the student.` |
| N4 | **成本随测试次数线性放大** | §4.1：`may become a problem in an academic context with a lot of tests` |
| N5 | **法规特有的失败**：交叉引用未消解 → 规则条件不完整；条件与后果跨句 → 规则边界切错 | §1.2.1 结构特征 3、4 |

#### 1.2.7 法规专用一手文献（已取得）

**取证路径记录**：arXiv 官方 API（`export.arxiv.org/api/query`）对本环境持续返回 `429 Rate exceeded.`——证据：`_evidence/R8/arx-deontic.xml` 全文即 `Rate exceeded.`（14 字节）；本分片重试的 `w2/arx-*.txt` 亦为 `PARSE FAIL ... len= 14`。**改用 `https://arxiv.org/search/?query=...&searchtype=all` HTML 端点后取得成功**（HTTP 200）。此路径可复用。

---

##### （1）法条规范单元切分：ANNOTARES

**来源**：arXiv:2608.03898，`https://arxiv.org/abs/2608.03898`，抓取 2026-09-15，HTTP 200，40,756 字节（本地：`_evidence/R8/w2/abs-2608.03898.raw`）。

【原文】标题与摘要（逐字）

> **ANNOTARES: A Dataset for Extracting Logical Structures from German Statutory Texts**
> Authors: Ronja Schwarz, Jannik Strötgen
> Submitted: 4 Aug 2026
>
> The automatic structural analysis of legal texts is a cornerstone of legal technology, yet the extraction of their logical components remains a significant challenge. In this paper, we introduce the task of identifying and segmenting legal conditions (**Tatbestand**) and legal consequences (**Rechtsfolge**) within German statutory texts. To support this task, we present ANNOTARES (Annotations of Tatbestand-Rechtsfolge Sequences), a novel dataset comprising German law texts with span-level annotations. Spanning three distinct legal codes, the dataset is designed to evaluate both domain-specific performance and cross-statute generalizability. We benchmark diverse architectural approaches: a rule-based baseline, CRFs, BiLSTMs, BiLSTM-CRF, and modern Transformer-based models, including BERT variants and LLM-based methods. Our results demonstrate that BERT and LLM-based models achieve superior performance in capturing the complex syntactic structures of legal language. We release our dataset to facilitate further research in automated legal reasoning.

【判断】**这篇论文的存在本身就回答了 §1.2.1 结构特征 4 的问题**：法条切分的正确单位不是"句子"，而是 **Tatbestand（构成要件 / 条件）→ Rechtsfolge（法律后果）** 的配对。ANNOTARES 的标注粒度是 **span-level**（片段级），而不是句级——即一条法条的规范单元可以跨句、可以嵌套。这正是"条件与后果常不在同一句"（§1.2.1）的解法。——依据：上引摘要 + §1.2.1。

【判断】**方法选型的可核实结论**：论文横向比较了 `rule-based baseline / CRFs / BiLSTMs / BiLSTM-CRF / BERT variants / LLM-based methods` 六类架构，结论是 **"BERT and LLM-based models achieve superior performance"**。注意它并未声称传统序列标注无效——而是说在"capturing the complex syntactic structures of legal language"上 BERT/LLM 更优。**对客户的含义：不需要自研模型，直接用现成 LLM 做条件/后果切分，是当前证据支持的首选。**——依据：上引摘要。

【判断】**跨法域泛化是显式设计目标而非事后检验**：数据集"Spanning **three distinct legal codes**"且"designed to evaluate both domain-specific performance and **cross-statute generalizability**"。对客户的含义：**在一部法规上调好的切分 prompt，换一部法规必须重测**，不能假定迁移。——依据：上引摘要。

⚠️ 论文所属数据集为**德语法条**。对客户的中/英文政策文本属跨语言迁移，**ANNOTARES 的性能数字不可直接引用为客户场景的预期值**。本分片未取得其具体指标数字。

---

##### （2）从判例反推规则：Legal Rule Induction (LRI)

**来源**：arXiv:2505.14104，`https://arxiv.org/abs/2505.14104`，抓取 2026-09-15，HTTP 200，42,972 字节（本地：`_evidence/R8/w2/abs-2505.14104.raw`）。

【原文】标题与摘要（逐字）

> **Legal Rule Induction: Towards Generalizable Principle Discovery from Analogous Judicial Precedents**
> Authors: Wei Fan, Tianshi Zheng, Yiran Hu, Zheye Deng, Weiqi Wang, Baixuan Xu, Chunyang Li, Haoran Li, Weixing Shen, Yangqiu Song
> Submitted: 20 May 2025 (v1), last revised 27 Aug 2026 (this version, v2)
>
> Legal rules encompass not only codified statutes but also implicit adjudicatory principles derived from precedents that contain discretionary norms, social morality, and policy. While computational legal research has advanced in applying established rules to cases, **inducing legal rules from judicial decisions remains understudied across jurisdictions**. The advent of Large Language Models (LLMs) offers unprecedented potential to automate the extraction of such latent principles, yet progress is stymied by **the absence of formal task definitions and benchmarks**. To address this gap, we formalize **Legal Rule Induction (LRI)** as the task of deriving concise, generalizable doctrinal rules from analogous precedents, **distilling their shared preconditions, normative behaviors, and legal consequences**. We further propose a reproducible pipeline for LRI dataset construction and, instantiating it on Chinese law as a representative jurisdiction, introduce the first LRI benchmark comprising **5,121 case sets (38,088 court cases)** for model tuning and **216 expert-annotated gold test sets**. Experimental results reveal that: 1) **State-of-the-art LLMs struggle with over-generalization and hallucination**; 2) Training on our dataset markedly enhances LLMs capabilities in capturing nuanced rule patterns across similar cases.

【判断】**这是本分片对 §1.3「从历史案例反推规则」最直接的一手证据。** 三条可操作结论：
1. **任务定义**：LRI = 从**类比判例**中导出"concise, generalizable doctrinal rules"，其内部结构被明确拆成 **shared preconditions（共同前提条件）+ normative behaviors（规范行为）+ legal consequences（法律后果）** 三元组。**这个三元组可直接作为客户规则的字段模板**：条件 / 行为 / 后果。
2. **数据集规模锚点**：`5,121 case sets (38,088 court cases)` + `216 expert-annotated gold test sets`。即：**训练/调优集 ≈ 5 千组，专家金标测试集 ≈ 2 百组**。这是本分片唯一的"案例→规则"数据规模实证。⚠️ 应注意这是**判例法域**（中国法）的数字，且语境是模型训练而非人工萃取。
3. **⚠️ 头号失败模式（原文）**：**"State-of-the-art LLMs struggle with over-generalization and hallucination"** ——**过度泛化**与**幻觉**并列。过度泛化排在幻觉之前，意味着**把特例当成通则**是比编造更常见的错误。这与 §1.1.3 ④ 的 isomorphic 要求（代码不得比规则多出逻辑）指向同一风险面。——依据：上引摘要。

---

##### （3）把法条形式化为可执行约束 + 求解器验证：LexGuard

**来源**：arXiv:2605.26530，`https://arxiv.org/abs/2605.26530`，抓取 2026-09-15，HTTP 200，42,320 字节（本地：`_evidence/R8/w2/abs-2605.26530.raw`）。

【原文】标题与摘要（逐字）

> **Which Changes Matter? Towards Trustworthy Legal AI via Relevance-Sensitive Evaluation and Solver-Grounded Reasoning**
> Authors: Chen Linze, Cai Yufan, Hou Zhe, Dong Jin Song
> Submitted: 26 May 2026
>
> Legal reasoning requires distinguishing changes that matter from those that do not. Legal AI should remain stable under legally irrelevant perturbations, but should change when perturbations alter legally material points. We formulate this requirement as a **legal-relevance-sensitive evaluation problem**: LLMs should only be sensitive to the legally relevant change. We introduce a unified evaluation suite covering **should-change and should-not-change evaluation** across judicial fairness, robustness, and statute-confusion scenarios. Our evaluation shows that **existing legal LLMs are systematically sensitive to legally irrelevant variations and often fail to distinguish related legal elements and statutory rules**. To mitigate these failures, we present **LexGuard, an adversarial multi-agent framework grounded in formal reasoning**. LexGuard **formalizes statutes into executable constraints**, uses **adversarial agents to extract competing fact-statute arguments**, and invokes **SMT solvers to verify legal satisfaction and logical consistency**. Experiments show that LexGuard improves legal reasoning reliability by reducing vulnerability to manipulative framing, improving disambiguation among similar statutes, limiting the influence of legally irrelevant attributes, and increasing consistency under benign reformulations. We show that legal trustworthiness requires not only accuracy, but **calibrated sensitivity to legally material changes**.

【判断】**这篇给了本分片唯一一个完整的"学术版法规→可执行规则"管线，且三段式极为清晰**：
`① formalizes statutes into executable constraints` → `② adversarial agents extract competing fact-statute arguments` → `③ SMT solvers verify legal satisfaction and logical consistency`。
即：**形式化 → 对抗式多角度抽取 → 求解器验证**。第 ③ 步用 **SMT solver** 而非人工复核来判"逻辑一致性"，这是它与 §1.1 Better Rules（用 test suites + 人）的关键差异。——依据：上引摘要。

【判断】**should-change / should-not-change 这一对评估维度可直接移植为客户规则库的验收测试**：对一条规则施加**法律上无关**的扰动（改品牌名、改措辞、换同义表达），判定结果**必须不变**；施加**法律上有关**的扰动（改功效声明、改目标人群），判定结果**必须变**。这两条比"准确率"更能暴露规则库的真实缺陷——摘要原文即指出"existing legal LLMs are **systematically** sensitive to legally irrelevant variations"。**对照 §1.1.6 F5（代码偷偷引入规则里没有的假设）：这两个测试正是 F5 的自动化检测手段。**——依据：上引摘要 + §1.1.6。

【原文】本分片对客户的直接映射（摘要末句）

> We show that legal trustworthiness requires not only accuracy, but **calibrated sensitivity to legally material changes**.

---

##### （4）未找到可核实原文的部分

⚠️ **`deontic modality classification`（道义模态分类）未取得一手文献。** arXiv 搜索 `all: deontic modality classification legal text` 返回 **0 结果**（`_evidence/R8/w2/s-deontic.html`，HTTP 200，16,498 字节）。因此本节**不给出道义模态分类的具体方法学**，仅保留 §1.2.1 结构特征 2 中对 DSA 原文模态词的**观察**（`shall` / `may` / `shall not`），不引申为标准体系。

⚠️ **`decision table mining` 的学术检索同样返回 0 结果**（见 §1.3）。

⚠️ 本分片**未取得任何一篇论文的正文指标数字**（F1、κ 等）——仅有摘要级证据。所有性能表述均已限定在摘要原文的措辞范围内。


---

### 1.3 决策表挖掘（decision table mining）

> **取证状态**：任务书指定的 Vanthienen / Wets（鲁汶大学，决策表方法学的源头）**本分片未取得任何一手文献**。arXiv 搜索 `all: decision table mining Vanthienen` 返回 **0 结果**（`_evidence/R8/w2/s-dectable.html`，HTTP 200，16,468 字节）。故本节**不写 Vanthienen 方法学的步骤细节**，改为（a）用已取得的 LRI 论文覆盖"从案例反推规则"这一实质，（b）用 Better Rules 手册的决策树覆盖表格化形态。**凡本应来自 Vanthienen 的内容，一律留白并标记「未找到可核实原文」。**

#### 1.3.1 输入

两大类，性质不同：

**（A）历史判定案例**（"上次这种情况我们是怎么判的"）。这是 decision table mining 与 LRI 共同的前提。

【原文】arXiv:2505.14104（`_evidence/R8/w2/abs-2505.14104.raw`，抓取 2026-09-15，HTTP 200）

> Legal rules encompass not only codified statutes but also **implicit adjudicatory principles derived from precedents** that contain discretionary norms, social morality, and policy. While computational legal research has advanced in applying established rules to cases, **inducing legal rules from judicial decisions remains understudied across jurisdictions**.

**（B）概念模型 + 逻辑依赖**（Better Rules 路径，不要求已有案例）。决策树的输入不是案例，而是概念模型的元素。

【原文】`_evidence/R8/brnz-workshop-manual.md` L242

> A decision tree is created by taking **the elements of the concept model** and organising them in an **order that represents the sequence (if there is any)** that people and systems would use to navigate the process. They provide the opportunity to look at **the logic dependencies that exist in the domain**.

【判断】两条输入路径对应客户处境的两种可能：**有历史判定记录 → 走 (A)；只有政策文本 → 走 (B)。** 客户 291 条记录中仅 21 条有规则、`检查人` 列基本为空（`01-内部证据-规则表现状审计.md`），即**(A) 的输入量不足，只能走 (B)**。这是 §2 矩阵中一条关键判据。——依据：上引两段 + `01-内部证据-规则表现状审计.md`。

#### 1.3.2 步骤

**路径 B（Better Rules 决策树）——有步骤原文：**

1. 从概念模型取元素（L242）。
2. 按"人或系统实际导航流程的顺序"排列（L242）。手册明示**顺序不一定存在**："the sequence (**if there is any**)"。
3. 检查逻辑依赖，并预期它会**反向修正概念模型**："It provides another way to describe the domain and will **often highlight inefficiencies in the approach and inaccuracies in the concept model**."（L242）
4. 复杂度高的树会被反复重访："the more complex ones will be revisited often in the same manner as the concept model."（L124）

**路径 A（从案例导出规则）——LRI 的三元组结构：**

【原文】arXiv:2505.14104

> To address this gap, we formalize **Legal Rule Induction (LRI)** as the task of deriving **concise, generalizable doctrinal rules** from analogous precedents, **distilling their shared preconditions, normative behaviors, and legal consequences**. We further propose **a reproducible pipeline for LRI dataset construction** and, instantiating it on Chinese law as a representative jurisdiction, introduce the first LRI benchmark comprising **5,121 case sets (38,088 court cases)** for model tuning and **216 expert-annotated gold test sets**.

【判断】**可迁移的三步骨架**：① 归拢"analogous precedents"（类比判例组）；② 从中抽出三者：**shared preconditions（共同前提条件）/ normative behaviors（规范行为）/ legal consequences（法律后果）**；③ 输出"concise, generalizable"的规则陈述。注意 ② 的三个槽位与 §1.1.3 ③ 的 Better Rules 陈述模板（`<主体> is <谓词> if: <条件>`）**结构一致**：条件 + 行为 + 后果。两处独立收敛。——依据：上引摘要 + §1.1.3。

【判断】**"shared" 一词是关键的操作定义。** 一条规则之所以成立，是因为它在**多个类比案例中共同出现**。这给出了一条可执行的反幻觉判据：**只出现一次的判定不构成规则，只是案例。** 这与 LRI 摘要中"LLMs struggle with over-generalization"正好构成互补——过泛化是把单例当通则，而 `shared` 要求是防它的机制。——依据：上引摘要。

⚠️ **LRI 论文的"reproducible pipeline for LRI dataset construction"的具体步骤，本分片只有摘要级证据，未取得正文，故步骤细节标记「未找到」。** 数据集构造 ≠ 规则萃取，不可混同。

#### 1.3.3 产出物

| 产出物 | 证据来源 | 形态 |
|---|---|---|
| 决策树图 | Better Rules 手册 L240（`assets/beard-decision-tree.jpg`，450,862 字节，见 `_evidence/R8/brnz-tree.json`） | 白板照片 / 图 |
| 三元组规则：前提条件 / 规范行为 / 法律后果 | LRI 摘要 | 文本三元组 |
| 修订后的概念模型 | Better Rules 手册 L242（决策树开发"will often result in changes to the concept model"） | 概念模型新版本 |

**注意**：Better Rules 手册把决策树定为 **`[optional output]`**（L123），不是基线必需。L117/L129/L140/L149 定为 base 的是概念模型、业务规则陈述、规则即代码、测试套件。

#### 1.3.4 谁执行

【原文】`_evidence/R8/brnz-workshop-manual.md` L237

> **Suggested Roles:** [Legal Advisor, Business Rules Specialist, Service Designer, Rules-as-code Specialist]

四角色，**含 Service Designer**——因为决策树的排序依据是"人或系统实际如何走这个流程"，不是逻辑上的依赖顺序。

#### 1.3.5 需要多久

【原文】L124

> Experience suggests these maps can take **anywhere from a few minutes to several days** depending on the complexity of the concept model and the more complex ones will be revisited often in the same manner as the concept model.

**"几分钟到几天"**，且复杂树需要反复重访。这是本分片全部证据中**唯一一条带时间单位的萃取活动耗时**。

#### 1.3.6 失败模式

| # | 失败模式 | 证据 |
|---|---|---|
| D1 | **过度泛化**（把特例当通则）— 与幻觉并列，且排在前面 | LRI 摘要：`State-of-the-art LLMs struggle with over-generalization and hallucination` |
| D2 | **幻觉**（编造不存在的规则） | 同上 |
| D3 | **把"顺序"当必然存在** — 有些领域根本没有天然的导航顺序 | Better Rules 手册 L242：`the sequence (if there is any)` |
| D4 | **决策树与概念模型脱钩** — 树开发中发现的模型错误没有被回写 | 手册 L242：树开发 `will often result in changes to the concept model`（反过来说：不回写就是失败） |
| D5 | **用单例当规则依据** — 只在一个案例中出现过的判定被升格为规则 | 【判断】依据 LRI 的 `shared preconditions` 定义 |

⚠️ **Vanthienen / Wets 学派关于决策表完备性、一致性、冗余性的经典失败模式（如 rule overlap / gap 检测），本分片「未找到可核实原文」，不列。**

---

### 1.4 知识获取瓶颈与 CommonKADS

> **取证状态（先说结论）**：**Feigenbaum 的「knowledge acquisition bottleneck」原始表述，本分片未找到可核实原文。** 任务书指出的三条路径全部确认不可达：`link.springer.com/book/10.1007/978-1-4471-0031-2`（CommonKADS 书）返回 **HTTP 404**（`_evidence/R8/commonkads-book.txt`，22,816 字节，正文为 `Page Not Found`）；`dare.uva.nl` 记录 **HTTP 200 但内容为 `Record not found`**（`_evidence/R8/ck-thesis-uva.txt`，6,976 字节，原文 `The record with id: 8e5e0d75-a6f6-4c4e-a6b1-4b2a5d0f0d40 does not exist.`）——**HTTP 200 不等于内容存在，这是本分片踩到的一个取证陷阱**；`commonkads.com` 未尝试。
> **因此本节不写 Feigenbaum 的引文，不写 CommonKADS 的建模步骤（组织模型/任务模型/代理模型/知识模型/沟通模型/设计模型六件套的具体内容），不写任何年份、书名、页码。** 改写为：**用本分片已取得的一手证据，从旁证角度论证"知识获取瓶颈"这一现象在 Better Rules 与法规 NLP 两个方向上如何具体显现。**

#### 1.4.1 输入

瓶颈的输入形态是**分散在多个互不通话的角色头脑中的知识**，而不是任何一份文件。

【原文】`_evidence/R8/brnz-workshop-manual.md` L49（Better Rules 手册序言，逐字）

> The key component is the multidisciplinary team. **Policy and rule development has generally been isolated from implementation** and this idea of getting everyone in the room is at the heart of "Better Rules".

【判断】**这句话是"知识获取瓶颈"的现象学描述，且它是一手原文。** "Policy and rule development has generally been isolated from implementation" 说的正是：制定规则的人与实现规则的人之间没有通道，**规则的知识在传递过程中丢失**。Better Rules 的整个方法学（9 人同屋工作坊）就是对这一瓶颈的制度性回应。——依据：上引原文。

#### 1.4.2 步骤（Better Rules 的"反瓶颈"流程，代替 CommonKADS 建模步骤）

Better Rules 手册**没有把它命名为知识获取**，但六个角色的准备任务与七项产出物实质上就是一套知识获取协议：

1. **并要求每人把隐知识显式化**：SME 准备领域演讲；Policy Advisor 备齐现行与历史政策立场；Legal Advisor 备齐法律语境；Service Designer 出"什么行得通/什么行不通"的报告；Business Rules Specialist 带来既有业务流程与规则知识（L86–106，详见 §1.1.1）。
2. **用一个共享工件承载全部知识**：概念模型被明确定义为"a visual shared understanding of the domain"（L118），且被声明为"**the central mechanism for quantifying and resolving disagreements**"（L118）。
3. **把冲突显式化而不是回避**：手册预期"a sense of agreement to develop within the group and for that to be suddenly interrupted by disagreement, **repeatedly**"（L205）。
4. **按单条规则迭代，让每个任务打断其他任务**（L213，详见 §1.1.2 步骤 4）。

【判断】**第 2 条是瓶颈的度量装置。** 如果知识获取顺利，概念模型的版本数应该收敛；手册反过来说"Expect it to be redrawn multiple times and plan accordingly"（L202）与"constantly evolving"（L118）——**即手册预期这个概念模型在整场工作坊中不收敛**。这就是瓶颈的量化形态。——依据：L118 + L202。

#### 1.4.3 产出物

| 产出物 | 位置 |
|---|---|
| 概念模型（多版本，含白板照片） | §1.1.3 ① |
| 六角色各自的准备材料（领域演讲、政策立场清单、法律语境、服务设计报告、业务流程知识） | §1.1.1 |
| "out of scope" 清单 | L207 |

⚠️ **CommonKADS 的六类模型（组织/任务/代理/知识/沟通/设计）产出物清单本分片「未找到可核实原文」，不列。**

#### 1.4.4 谁执行

**九人六角色**（L56–62）。见 §1.1.4 完整清单。

【判断】**人数本身就是瓶颈的代价证据**：如果知识获取不难，不需要六种角色同屋。且手册强调"Each of the outputs represent large academic fields with complex and intimidating terminology so use these outputs as tools"（L50）——**手册作者明确意识到这些方法学的门槛会阻碍采用**，这本身是知识获取方法落地时的次级瓶颈。——依据：L50 + L56–62。

#### 1.4.5 需要多久

⚠️ **未找到。** Better Rules 手册未给出工作坊总时长（§1.1.5 已记录）。唯一带时间单位的证据仍是决策树的"几分钟到几天"（L124）与平台侧 enforcement guideline 的"a few months"（R4 §2.1）。

#### 1.4.6 失败模式

| # | 失败模式 | 证据 |
|---|---|---|
| K1 | **政策开发与实现长期隔离**（瓶颈的成因，且被描述为行业常态） | L49：`Policy and rule development has generally been isolated from implementation` |
| K2 | **概念模型被当成一次成型的交付物** | L202 / L118 |
| K3 | **团队不敢反驳** → 分歧被压掉而不是被解决 | L187：`confident in disagreeing/questioning the rest of the group; this team dynamic is important for ensuring success` |
| K4 | **方法学术语门槛导致放弃使用** | L50：`large academic fields with complex and intimidating terminology` |
| K5 | **把方法论当权威** → 不做本地适配 | L48：`Do not treat this document as authoritative` |

【判断】K1–K5 五条共同指向一个结论：**知识获取瓶颈不是"知识藏得很深"，而是"没有机制让持有知识的各方在同一条规则上同时表态"。** Better Rules 的解法是物理性的（同一房间、同一块白板、同一条规则），不是文档性的。——依据：L49 + L187 + L213。

---

### 1.5 RuleFit 与关联规则挖掘（从标注数据发现规则）

> **取证状态（含一次更正）**：`_evidence/R8/rulefit-arxiv.txt` 的 `SOURCE_URL` 标注为 `https://arxiv.org/abs/0811.3652` 且 `HTTP: 200`（38,937 字节），但**抓回的内容不是 RuleFit**——它是 **arXiv:0811.3652 "Polynomial Coefficient Enumeration"**（Tewodros Amdeberhan, Richard P. Stanley，math.CO，36 页，Submitted on 21 Nov 2008），一篇**组合数学**论文。**该证据文件的文件名与 SOURCE_URL 均与内容不符，不可引用。**
> **本分片随后定位到正确的 arXiv ID 并抓取成功**：**arXiv:0811.1679**，`https://arxiv.org/abs/0811.1679`，抓取 2026-09-15，**HTTP 200，42,320 字节**（本地：`_evidence/R8/w2/rulefit-abs.raw`）。以下引用均出自该文件。
> ⚠️ 未能取得的路径：arXiv 官方 API（`export.arxiv.org/api/query`）持续返回 `429 Rate exceeded.`（证据：`_evidence/R8/arx-deontic.xml` 全文 14 字节即 `Rate exceeded.`；本分片重试的 `w2/arx-*.txt` 共 7 个文件均为 `PARSE FAIL ... len= 14`）；arXiv HTML 搜索 `all: decision table mining Vanthienen` 返回 **0 结果**。
> ⚠️ 本分片**只取得该论文的摘要与元数据，未取得正文**，故不引用其算法公式、参数或性能数字。

#### 1.5.0 【原文】RuleFit 的原始定义（arXiv:0811.1679 摘要，逐字）

> Title: **Predictive learning via rule ensembles**
> Authors: Jerome H. Friedman, Bogdan E. Popescu
> Submitted on 11 Nov 2008
>
> General regression and classification models are constructed as **linear combinations of simple rules derived from the data**. Each rule consists of **a conjunction of a small number of simple statements concerning the values of individual input variables**. These rule ensembles are shown to produce predictive accuracy comparable to the best methods. However, **their principal advantage lies in interpretation**. Because of its simple form, **each rule is easy to understand, as is its influence on individual predictions**, selected subsets of predictions, or globally over the entire space of joint input variable values. Similarly, the degree of relevance of the respective input variables can be assessed globally, locally in different regions of the input space, or at individual prediction points. Techniques are presented for **automatically identifying those variables that are involved in interactions with other variables**, the strength and degree of those interactions, as well as the identities of the other variables with which they interact. Graphical representations are used to visualize both main and interaction effects.

【判断】**摘要本身就把方法的输入前提写死了**：`simple rules **derived from the data**`、`statements concerning **the values of individual input variables**`。即：**必须有数据，且必须有"输入变量的取值"**。这直接支撑 §1.5.7 的判定——客户 12 字段中 `适用产品` 21/21 为常量、`判断方式` 21/21 为常量（审计 §1.1），**不是可变化的 input variable**，无法构成规则集成所需的自变量空间。——依据：上引原文 + 审计 §1.1。

【判断】注意论文声明的主要卖点是 **interpretation（可解释性）**，而不是精度——`produce predictive accuracy comparable to the best methods. However, their principal advantage lies in interpretation`。**这一点对客户的意义是：RuleFit 解决的是"已有强预测模型但看不懂"的问题，不是"没有模型"的问题。客户属于后者。**——依据：上引原文。

#### 1.5.1 输入

【判断】**RuleFit 与关联规则挖掘（Apriori / 频繁项集）的共同前提是：必须已经有一个"标注数据"或"特征空间"。** 具体来说：
- **规则集成（rule ensembles）**：从**已标注的样本**里，用树模型生成候选规则、再用正则化回归筛选并赋权。没有标签，无法定义损失函数。
- **关联规则挖掘**：从**事务数据**中统计项集共现频率。没有历史的"项—事务"结构，无法计算支持度与置信度。

**这两类方法的输入不是政策文本，而是"已经被人判过的历史案例"。** 这在证据上有一个直接对照：本分片取得的 LRI 论文（arXiv:2505.14104）之所以能从判例导出规则，前提是它有 **"5,121 case sets (38,088 court cases) for model tuning and 216 expert-annotated gold test sets"**——即**先有 3.8 万份已裁决案例 + 216 组专家金标**。**没有这个量级的已标注语料，统计学习路径不成立。**——依据：arXiv:2505.14104 摘要（§1.2.7）+ §1.3.1。

#### 1.5.2 步骤

⚠️ **未找到可核实原文，不写步骤。** 本分片不掌握 RuleFit 的算法步骤，也不掌握关联规则挖掘的具体挖掘流程，**不以教科书常识填充**。

**可写的只有替代路径**：若客户确实要走"从数据发现规则"，本分片证据支持的流程是 LRI 的三元组抽取（§1.3.2），而**不是** RuleFit。

#### 1.5.3 产出物

⚠️ 依上，本节不列 RuleFit 的产出物形态（如"rule ensemble 中的加权规则列表"），因**未找到可核实原文**。

#### 1.5.4 谁执行

【判断】此类方法要求执行者具备统计学习/数据挖掘能力，且**必须同时有标注体系的设计者**（否则标签本身的定义就不可靠）。这与 Better Rules 的"九人六角色"（§1.1.4）是完全不同的人力结构——**前者是少数技术专家 + 大量廉价标注，后者是少数领域专家 + 密集协作**。——依据：§1.1.4 + 本节 1.5.1。

#### 1.5.5 需要多久

【判断】**未找到可核实的耗时数据。** 但可给出一个下界推断：LRI 论文构建 **38,088 份案例 + 216 组专家金标** 作为数据集，**仅"专家金标"一项就必然以人月计**。——依据：arXiv:2505.14104 摘要。⚠️ 该推断基于数据规模，**不是论文报告的实际工时**。

#### 1.5.6 失败模式

| # | 失败模式 | 依据 |
|---|---|---|
| R1 | **没有标注数据时方法根本无法启动** | 【判断】§1.5.1 |
| R2 | **标签定义不可靠时，学到的是标注者的猜测而非规则** | R4 §2.4 引 Plank, Hovy & Søgaard 2014：分歧绝大部分是语言歧义而非标注员马虎 |
| R3 | **指南中的示范样例被模型学成捷径**（annotation artifacts） | R4 §2.4 引 Gururangan et al. 2018 NAACL-HLT |
| R4 | **过泛化**（统计学习的高频失败模式，与 LRI 的实证一致） | arXiv:2505.14104：`State-of-the-art LLMs struggle with over-generalization and hallucination` |

#### 1.5.7 【判断】结论：此类方法在客户当前阶段不适用

**客户现实**（依据 `01-内部证据-规则表现状审计.md`）：**291 条记录 / 21 条规则 / 覆盖率 13.8% / 12 字段**。

**判定：RuleFit 与关联规则挖掘应排在「来源分类学」与「人工萃取」之后，当前不建议采用。**

**四条理由：**

1. **没有标签。** RuleFit 需要已标注样本。客户的 21 条规则是**规则**，不是**标注**——它们没有回答"这 291 条记录里，其余 270 条各自命中了哪条规则、为什么"。没有这个对应关系，就没有监督信号。
2. **没有特征空间。** 关联规则挖掘需要"项—事务"结构。客户的 12 字段是否可枚举、是否稳定，尚未确定（`来源分类学` 是另一分片的工作）。**在字段定义稳定之前做项集挖掘，得到的是字段噪声。**
3. **样本量低于可用门槛。** 291 条记录即使 100% 标注，也无法支撑规则集成的统计筛选；对照 LRI 的 38,088 份案例规模，差两个数量级。
4. **顺序颠倒会产生错误依赖。** 如果先跑挖掘得到一批"统计规则"，再让业务方去解释它们，得到的是**事后合理化**的规则，而不是政策意图。这与 §1.1.3 ④ 的 isomorphic 要求（代码不得比规则多出逻辑）方向相反——**挖掘出的规则天然会比政策多出逻辑**。

**正确的顺序**：先用 §1.1 的 Better Rules 路径（或 §1.2 的条文 NLP 路径）把**规则本身**建起来，同时按 R4 §2.1 的 YouTube 五步法把**标注指南**对齐到多人一致；等到标注数据积累到可统计的量级，**再**评估是否引入数据驱动的规则发现。

---

### 1.6 人机协同标注（HITL）：从"模型与人工分歧"反推规则

#### 1.6.1 输入

**输入不是政策文本，而是三样东西：** ① 一批**已判定的样本**（模型判过、人判过）；② 两者的**分歧清单**；③ 一份**可被修改的规则文本**（分歧最终要回到这里改）。

【判断】关键在 ③。**没有可修改的规则文本，分歧只能被"压掉"（改标签迁就规则，或改模型迁就标签），无法被"用掉"。** 这也是 §1.1.6 F2（概念模型被当成一次成型）在 HITL 语境下的同一条约束。——依据：§1.1.6 + 本节 1.6.6。

#### 1.6.2 步骤

**步骤骨架（Better Rules 的测试套件路径）——把非程序员放进循环：**

【原文】`_evidence/R8/brnz-workshop-manual.md` L150

> Test suites are an adoption from the world of software development. Think of them as capturing and preserving policy intent. A test is a description of a scenario with given inputs and what the expected output(s) should be. Couple this concept with rules-as-code and it's possible to write thousands of tests for all conceivable scenarios and leverage computers to run those tests in an automated fashion. **They provide an easy bridge for non programmers to engage with the coding aspect of rules-as-code by being involved in the writing of the tests and studying the results.**

【判断】**"studying the results" 这四个词就是 HITL 的接口定义。** 非程序员（SME/Policy Advisor）**写测试、看结果**；程序员**写代码**。人在循环中的位置是**期望输出的定义者**，不是代码的审查者。这条接口比"让人审核模型输出"更可操作——因为人审核的是**自己写下的期望**，而不是模型产出的陌生结论。——依据：上引原文。

**步骤骨架（YouTube 的五步法）——先对齐人，再对齐机器：**

R4 §2.1 已逐字引用 YouTube 官方博客的完整流程，此处只提炼其**顺序约束**（避免重复，详见 R4 §2.1）：

1. 先写 enforcement guideline（不是政策原文）。
2. **先用最资深的审核员测**——达不到高准确率则说明**指南有问题，不是审核员有问题**。
3. 扩大测试组到几百人（不同背景、语言、经验）。
4. 修订指南，直到多样人群也能达到同样准确率——**"This process can take a few months"**。
5. **只有在人被指南对齐之后，才用它去训练机器。**

【判断】**第 2 步是 HITL 中最重要的诊断规则："达不到准确率 → 先怪规则，别怪人。"** 这条把分歧的归因方向固定下来。客户当前 `判断方式` 字段 21/21 全部填 `自动可检测`（R4 §2.4），却从未做过"规则 × 多个判定者"的一致性测试，**因此目前无法区分"规则不清楚"与"执行者判错了"**（R4 §2.1 已指出）。——依据：R4 §2.1 + R4 §2.4。

**步骤骨架（对抗式抽取，学术版）：**

【原文】arXiv:2605.26530（`_evidence/R8/w2/abs-2605.26530.raw`）

> LexGuard **formalizes statutes into executable constraints**, uses **adversarial agents to extract competing fact-statute arguments**, and invokes **SMT solvers to verify legal satisfaction and logical consistency**. Experiments show that LexGuard improves legal reasoning reliability by reducing vulnerability to manipulative framing, improving disambiguation among similar statutes, limiting the influence of legally irrelevant attributes, and increasing consistency under benign reformulations.

【判断】**"competing fact-statute arguments"（相互竞争的事实—法条论证）是 HITL 的一个高阶形态**：不由一个人判一次，而是让**多个对抗性智能体各自为同一事实主张不同的法条适用**，再由求解器判逻辑一致性。人的角色转移到**裁定哪个论证成立**。对客户的含义：当一条广告是否违规存在两种合理解读时（如 R4 §2.4 记录的 `pumping doesn't have to hurt` 被判绿、而 `painless pumping` 被判红），**正确动作不是二选一，而是把这两个论证都记下来并回写规则文本**。——依据：上引原文 + R4 §2.4。

**步骤骨架（错题本 → 规则的四种制度化机制）**：R4 §3.5 已整理为 A（案例→泛化范围声明）/ B（建议→处置码→台账）/ C（难例→指南微调）/ D（难例→手册下一版）四类，此处不重复。**本节补充其共同的操作前提**：

【判断】A/B/C/D 四类机制的每一次运转，都需要一份**同时记录"规则原文 + 判定 + 分歧理由"的载体**。仅有"判错的截图"无法驱动任何一类。**HITL 的最小可用记录是"一条分歧 = 一行结构化记录 + 一个处置码 + 一句规则修订建议"。**——依据：R4 §3.5。

#### 1.6.3 产出物

| 产出物 | 证据 |
|---|---|
| 测试套件（每行 = 输入场景 + 期望输出） | Better Rules L150、L273 |
| 修订后的 enforcement guideline | R4 §2.1（YouTube 第 4 步） |
| 分歧记录（含处置码） | R4 §3.5（机制 B） |
| 形式化的可执行约束 / 求解器验证结果 | LexGuard 摘要 |
| "法律上无关"与"法律上有关"两组扰动测试 | LexGuard 摘要的 should-change / should-not-change 设计 |

#### 1.6.4 谁执行

**Better Rules 的测试套件角色表**：

【原文】`_evidence/R8/brnz-workshop-manual.md` L269

> **Suggested Roles:** [Subject Matter Specialist, Policy Advisor, Rules-as-code Specialist]

三个角色，**不含 Legal Advisor，也不含 Business Rules Specialist**——与业务规则陈述（L248：Business Rules Specialist + Legal Advisor）**完全不重叠**。见 §1.1.2 步骤 6 的判断。

#### 1.6.5 需要多久

| 环节 | 耗时 | 证据 |
|---|---|---|
| 平台侧指南对齐（人到多人一致） | **几个月** | R4 §2.1 引 YouTube：`This process can take a few months` |
| 写"几千个测试" | 未找到 | Better Rules L150 只说明**可以写** `thousands of tests`，未给工时 |

⚠️ 客户场景下的 HITL 周期**未找到可核实数据**。

#### 1.6.6 失败模式

| # | 失败模式 | 证据 |
|---|---|---|
| H1 | **归因错误：把规则缺陷当成执行者失职** | YouTube 第 2 步的反向诊断规则（R4 §2.1） |
| H2 | **顺序颠倒：先训机器再对齐人** | YouTube 五步法的第 5 步顺序（R4 §2.1） |
| H3 | **分歧被压掉而非回写规则** | 【判断】§1.6.1 ③ |
| H4 | **过度泛化** | arXiv:2505.14104：`State-of-the-art LLMs struggle with over-generalization and hallucination` |
| H5 | **幻觉** | 同上 |
| H6 | **对法律上无关的改动过敏**（改了品牌名/措辞，判定就变） | arXiv:2605.26530：`existing legal LLMs are systematically sensitive to legally irrelevant variations` |
| H7 | **无法区分相近法条/相近规则** | 同上：`often fail to distinguish related legal elements and statutory rules` |
| H8 | **示范样例被学成捷径（annotation artifacts）** | R4 §2.4 引 Gururangan et al. 2018 |
| H9 | **多数投票不提高可靠性** | R4 §5.2.4 |

---

### 1.7 T&S 行业的 policy-to-enforcement 翻译流程（含具体模板）

> **证据说明**：R4 §2 与 §3 已覆盖 YouTube/Meta 的流程与标注手册解剖。**本节不重复**，改用 R7 分片取得的 **Mozilla Add-on Policies 管道**——它是本分片找到的**唯一一份"政策原文 → 审核员判定 → 拒绝后果"三段齐全的公开实物**。
> 三份证据（均 HTTP 200，抓取 2026-09-15）：
> - `_evidence/R7/amo-addon-policies.txt`（83KB）——**政策原文**，页面标注 `Last update: Apr 30, 2026`
> - `_evidence/R7/amo-review-rejection.txt`（68KB）——**拒绝意味着什么**
> - `_evidence/R7/amo-source-code-submission.txt`（75KB）——**证据提交要求**
> ⚠️ 取证提醒：这三份是网页转文本，正文被重复渲染了三次（导航区 ×3）。引用前本分片已核对行号唯一性。

#### 1.7.1 输入

**政策文本 + 待审对象 + 审核员。** 政策本身是唯一的规范来源，且**明确声明它不是法律意见**：

【原文】`_evidence/R7/amo-addon-policies.txt` L2163–2165

> All add-ons are subject to these policies, regardless of how they are distributed.
>
> When an add-on is given human review or otherwise assessed by Mozilla, these policies act as **guiding principles** for those reviews. Add-ons that do not comply with these policies may be **rejected or disabled** by Mozilla.

以及 L2161（免责声明，逐字）：

> These policies are not intended to serve as legal advice: depending on where you are located, additional requirements may apply.

【判断】**"guiding principles" 这个词是整份文档最重要的一处**。政策**故意不写成判定规则**——它把自己定位为审核员的**指导原则**，把具体判定权留给审核员。这与客户当前把 21 条规则全部标为 `自动可检测`（R4 §2.4）形成直接冲突：**平台自己都不敢把政策写成自动可检测的规则，而是写成原则 + 人工审核。**——依据：L2165 + R4 §2.4。

#### 1.7.2 步骤与模板

**模板 A｜政策的顶层骨架（可直接照搬的八段式）**

AMO 政策的编号结构（`_evidence/R7/amo-addon-policies.txt` 逐字标题，行号）：

```
1. No Surprises                                   (L2185)
   1.1. Unexpected features                      (L2191)
2. Content                                        (L2203)
3. Submission Guidelines                          (L2225)
   3.1. Source Code Submission                    (L2231)
4. Development Practices                          (L2245)
5. User Scripts                                   (L2269)
6. Data Collection and Transmission Disclosure and Control (L2277)
   6.1. Prohibited Data Collection and Transmission (L2283)
   6.2. User Consent and Control                  (L2291)
   6.3. Additional Privacy Protocols              (L2367)
7. Monetization                                   (L2373)
8. Security, Compliance and Blocking              (L2381)
   8.1. Policy Enforcement                        (L2385)
```

【判断】**编号规律**：`N` = 主题域；`N.M` = 该域下的**可判定子条款**。**注意"审核后果"被显式编号为第 8 章（Security, Compliance and Blocking）而不是散落各处**——即政策的**执行机制本身是政策的一部分**。客户现状中未见任何"违反之后怎么办"的成文章节，这是可直接补齐的结构缺口。——依据：上表。

**模板 B｜一条政策的可判定写法（逐字实例：数据同意界面的六项强制条件）**

这是全份文档中**最接近"规则陈述"的一段**——一条政策原则被展开成一串可逐项核验的条件：

【原文】`_evidence/R7/amo-addon-policies.txt` §6.2.2 附近，逐字

> The data transmission consent and control must be contained within the add-on. **The consent experience must:**
> - **Be unmissable.** It is recommended to present it in a new focused tab in the current window. **Other ways that could be missed or accidentally hidden, like a popup window, will result in a rejection.**
> - **Be presented on a single page**, including all choices and decision options.
> - **Present users with a clear, readable data transmission consent.** Information explaining the data transmitted must be prominently stated and not buried or hidden.
> - **Avoid deceptive design patterns** that make it harder to understand your data transmission policy, including, but not limited to, illegible font sizes, reduced color contrast, hidden options, multi-step consent decline flows, and similar techniques indicative of deceptive design.
> - **Clearly state what type of data is being transmitted.**
> - **Inform about the impact of accepting or declining the data transmission**

【判断】**这六条的写法是"政策 → 判定项"的教科书级模板，含四个可抽取的工程特征**：
1. **每项一个动词开头**（Be / Be presented / Present / Avoid / Clearly state / Inform）——**每项只描述一个可观察的属性**，与 Better Rules 的 "keep each line or statement precise and describing a single point"（§1.1.3 ③）是同一条纪律。
2. **其中一条直接绑定了后果**：`like a popup window, **will result in a rejection**`——**判定项与处置结论在同一句内闭合**，审核员不需要二次推断。客户规则库目前缺少这种"命中即处置"的绑定。
3. **给了反例枚举而不是只给正例**：`illegible font sizes, reduced color contrast, hidden options, multi-step consent decline flows`——这正好对冲 R4 §2.4 记录的 annotation artifacts 风险（只给一个示范样例会被学成捷径）。**用反例枚举代替单一示范，是这条模板最值得抄的一点。**
4. **保留了"including, but not limited to"**——显式声明枚举不完备，把未列举情形留给人工判断。

**模板 C｜审核需要的证据包（提交方能提供什么）**

【原文】`_evidence/R7/amo-addon-policies.txt` L2231–2237（§3.1 Source Code Submission，逐字）

> Code must be provided in a way that is reviewable. Add-ons may contain transpiled, minified or otherwise machine-generated code, but Mozilla needs to review a copy of the source code before any of these steps have been applied.
>
> The author must provide this information to Mozilla during submission **along with instructions on how to reproduce the build**. All dependencies must either be included in the source code package directly or downloaded only through the respective official package managers during the build process. Build tools or environments that no longer appear to be supported by their maintainers are not accepted. **Reviewers may ask you to refactor parts of the code if it is not reviewable.**
>
> The provided source code is reviewed by an administrator and is not redistributed in any way. The code is only used for the purpose of reviewing the add-on. **Failure to provide this information results in rejection or blocking.**

【判断】**"instructions on how to reproduce the build"（如何复现构建的说明）是一条可直接移植的要求**。对应到客户场景：**任何被判定的记录，必须附带"如何复现这个判定"的说明**（命中了哪条规则、依据哪个证据字段、当时的输入是什么）。没有复现说明的判定，事后无法审计，也无法沉淀为错题。这是客户 12 字段中目前缺失的一项（R4 已指出 291 条记录的 `检查人` 列基本为空）。——依据：L2235 + R4 §2.1。

**模板 D｜审核结论的两种形态与分级处置**

【原文】`_evidence/R7/amo-review-rejection.txt` L2167、L2177（逐字）

> The **machine validation** tells you immediately if anything needs to be fixed to enable the publication of your extension. **In some cases, a human review may be necessary for publication.** When this review starts, the reviewer may ask for clarification about your extension. The outcome of the review could be **the rejection of your extension's latest version and the rejection of earlier unreviewed versions if they also contain issues**.

【原文】`_evidence/R7/amo-review-rejection.txt` L2187–2195（逐字）

> Impact of review rejection
>
> Should your extension be rejected by the human review:
>
> You receive an email that explains **the reason for the rejection and what action you need to take to correct the issues identified**.
>
> People who have installed your extension **will not notice any change** as a result of the review rejection; they will be able to continue using your extension as usual.

【判断】**这段给出了"机器初筛 + 人工复核"的两级结构，且两级的结论形态不同**：
- **machine validation**：即时、二元（"anything needs to be fixed"）。
- **human review**：可向提交方**索取澄清**（`may ask for clarification`），结论可以是**拒绝**，且**拒绝范围可回溯**（`earlier unreviewed versions if they also contain issues`）。

**最后一句（拒绝不影响已安装用户）对客户是一条重要的分级设计原则**：**判定结论的"生效范围"是可裁剪的**——不是"违规即下架"，而是"拒绝本次提交，存量不动"。客户目前没有这种分级，只有红/黄/绿三档静态等级。——依据：L2177 + L2195。

**模板 E｜执行的分级响应（第 8.1 章，逐字）**

【原文】`_evidence/R7/amo-addon-policies.txt` §8.1 Policy Enforcement 附近，逐字

> Mozilla may reject or block affected versions or entire add-ons that don't comply with the above policies, **depending on the extent of their non-compliance**.
>
> Mozilla may attempt to contact the add-on's developer(s) and **provide a reasonable time frame for the problems to be corrected before a block is deployed**. If an add-on appears to **intentionally or repeatedly** violate the policies, or its developers have proven **unreachable, unresponsive, or uncooperative**, blocking may be immediate.
>
> Mozilla reserves the right to block or delete any developer's account on addons.mozilla.org, thereby preventing further use of the service, for certain violations of Mozilla's policies.

【判断】**平台的政策→执行映射里有三个正交的升级轴**，客户可直接抄：
1. **范围**：`affected versions` → `entire add-ons` → `developer's account`（版本 → 整体 → 主体）。
2. **速度**：默认给 `a reasonable time frame` 先整改；**四类情形可立即封禁**：`intentionally`（故意）/ `repeatedly`（反复）/ `unreachable` / `unresponsive` / `uncooperative`（失联、不回应、不配合）。
3. **触发条件**：`depending on the extent of their non-compliance`——**处置力度与违规程度成正比**，是显式成文的。

**注意第 2 条里"失联/不回应/不配合"被列为与"故意违规"同一档的立即封禁理由。** 即**配合度本身是升级判据**，不只是违规事实。这是客户规则库完全没有的维度（客户按内容定档，没有"处置阻力"维度）。——依据：§8.1 原文。

#### 1.7.3 产出物

| 产出物 | AMO 对应物 | 客户可落地形态 |
|---|---|---|
| 政策文件（N + N.M 编号，含独立的"执行"章） | `amo-addon-policies.txt` 八章 + 8.1 | 规则库总纲 + 处置章 |
| 可判定条件清单（一条原则 → 六个条件句） | §6.2.2 六条 | 每条规则的判定项 |
| 反例枚举 | §6.2.2 `illegible font sizes, ...` | 每条规则的"典型错误写法" |
| 证据包要求（含复现说明） | §3.1 `instructions on how to reproduce the build` | 每条判定的复现说明字段 |
| 两级结论（机器初筛 / 人审） | review-rejection L2177 | 自动命中 + 人工复核 |
| 分级执行表（范围 × 速度 × 触发） | §8.1 | 处置矩阵 |

#### 1.7.4 谁执行

| 角色 | AMO 证据 |
|---|---|
| 政策作者 | 页面 Contributors 列表（逐字）：`kewisch / rebloor / wagnerand / atsay / jvillalobos / wbamberg / kmaglione / dotproto / bacharakis`（`amo-addon-policies.txt` L2408–2424 附近） |
| 机器校验 | `The machine validation tells you immediately...`（rejection L2167） |
| 人工审核员 | `the reviewer may ask for clarification about your extension`（rejection L2177） |
| 管理员 | `The provided source code is reviewed by an administrator`（policies L2237） |

【判断】**九个具名贡献者 + 页面标注最后更新日 `Apr 30, 2026`**，说明这份政策本身在持续维护。**政策的维护者名单是公开的**——这是客户目前不具备的治理透明度。——依据：上表。

#### 1.7.5 需要多久

⚠️ **AMO 三份文档均未给出审核时长或翻译耗时。** 本分片「未找到」。
参照：R4 §2.1 引 YouTube 官方博客的 `This process can take a few months`（指南对齐耗时）。

#### 1.7.6 失败模式

| # | 失败模式 | 证据 |
|---|---|---|
| P1 | **把政策当法律意见** | L2161：`These policies are not intended to serve as legal advice` |
| P2 | **把指导原则当成可自动判定的规则** | L2165 `guiding principles` vs 客户 21/21 `自动可检测` |
| P3 | **没有配套的复现说明 → 判定不可审计** | L2235 `instructions on how to reproduce the build`；L2237 `Failure to provide this information results in rejection or blocking` |
| P4 | **处置只有一档** | §8.1 显示真实平台有 3 类范围 × 2 类速度 |
| P5 | **只看违规事实，不看处置阻力** | §8.1 把 `unreachable, unresponsive, or uncooperative` 列入立即封禁 |
| P6 | **单点示范被学成捷径** | R4 §2.4 引 Gururangan 2018；AMO 的对策是反例枚举（§6.2.2） |
| P7 | **政策无版本/无维护者记录** | AMO 有 `Last update: Apr 30, 2026` + 九人贡献者名单 |

---

### 1.8 标注规范与分类法编写模板

> **证据说明**：R4 §2.2 已对 Gab Hate Corpus 训练手册（20 页）做过实物解剖，含目录结构与六个结构件的逐字证据，**本节不重复**。本节补的是**两个 R4 未覆盖的实物**：① GitHub 政策仓库的**元数据字段**（一条政策实际存了哪些字段）；② 分类法的**分面写法**。

#### 1.8.1 输入

三样：① 政策原文；② 已有的分类法/术语表（若有）；③ **一份要被复用的字段清单**（这是本节的核心）。

【判断】编写标注规范最常见的错误起点是直接从"条款"开始写。**正确起点是字段清单**——因为字段决定了后续所有标注的可统计性。下节的 GitHub 样本给出了一个真实的字段清单。——依据：§1.8.2。

#### 1.8.2 步骤与产出物模板

**模板 ①｜政策的元数据头（YAML front-matter，逐字）**

来源：`_evidence/R7/github-docs-aup-src.md`（GitHub 官方仓库的 Markdown 源码，129 行）。文件开头逐字：

```
---
title: GitHub Acceptable Use Policies
redirect_from:
  - /articles/github-acceptable-use-policies
  - /github/site-policy/github-acceptable-use-policies
versions:
  fpt: '*'
category:
  - Follow acceptable use policies
---
```

【判断】**这是本分片找到的"一条政策实际存了哪些字段"最干净的一手样本。** 四个字段各有明确职能，客户可直接映射：

| GitHub 字段 | 职能 | 客户对应 |
|---|---|---|
| `title` | 政策标题 | 规则条目名 |
| `redirect_from` | **历史 URL 列表**——政策改名/搬家后，旧链接仍然有效 | **规则的版本沿革**：一条规则改过几次、旧编号是什么 |
| `versions: fpt: '*'` | **适用版本范围**（`fpt` = free/pro/team；`'*'` = 全部） | **规则的适用范围**（哪个平台/哪个品类/哪个市场） |
| `category` | **分类法归属**（此处为 `Follow acceptable use policies`） | **规则的一级分类** |

【判断】**`redirect_from` 是客户最缺也最容易补的字段。** 它把"规则条目的身份"与"规则条目的位置"解耦——规则可以改名、可以搬到别的分类下，而引用它的地方不会断链。客户 21 条规则如果做过任何一次重编号或合并，没有这个字段就意味着**历史判定记录无法回溯到当前规则**。——依据：上引 front-matter + R4 §2.1（记录无法区分规则缺陷与执行错误）。

**模板 ②｜政策的"短版本"摘要写法（逐字）**

同文件紧接着 front-matter 之后：

【原文】`_evidence/R7/github-docs-aup-src.md` 第 12 行附近

> **Short version:** _We host a wide variety of collaborative projects from all over the world, and that collaboration only works when our users are able to work together in good faith. While using the Service, you must comply with our Acceptable Use Policies, which include some restrictions on content and conduct on GitHub related to user safety, intellectual property, privacy, authenticity, and other limitations. In short, be excellent to each other._

【判断】**"Short version:" 是一个独立的、被显式标记的字段**——**同一份政策有两个正交版本**：法律上精确的长版本，和给人读的短版本。两者并列存放，不互相替换。
注意短版本本身就完成了一次**分类法的宣告**：它把限制归纳为五个维度——**`user safety, intellectual property, privacy, authenticity, and other limitations`**。**这五个词就是 GitHub 的顶层分类轴。**——依据：上引原文。

**模板 ③｜术语定义的显式声明（逐字）**

同文件，front-matter 之后第二段：

【原文】`_evidence/R7/github-docs-aup-src.md`

> Capitalized terms used but not defined in these Acceptable Use Policies have the meanings assigned to them in your main agreement with us — the [GitHub Terms of Service](...) or GitHub Customer Agreement, or the [GitHub Corporate Terms of Service](...) or other legacy GitHub contract, or a Microsoft volume licensing agreement. For customers subject to the legacy Corporate Terms of Service, "you" and "your" refer to "Customer" or "Users". "We", "us", and "our" refer to "GitHub".

【判断】**这段确立了三条术语纪律**：① **首字母大写的词 = 已定义术语**（一个全文通用的视觉信号）；② 本文件未定义的术语**不在此处定义，而是指回主协议**（避免同一术语两处定义不一致）；③ `"you" / "your" / "We" / "us" / "our"` 这类代词被显式绑定到法律主体。**对客户的含义：`检查人`、`风险等级`、`命中规则` 这 12 个字段里的每一个，都应有一处唯一定义，且规定"本文件未定义的指回哪里"。**——依据：上引原文 + `01-内部证据-规则表现状审计.md`。

**模板 ④｜分类法的分面写法（逐字）**

GitHub AUP 正文采用"总则 + 分面 + 分面子页"三层：

【原文】`_evidence/R7/github-docs-aup-src.md`

> ## 1. Compliance with Laws and Regulations
>
> You are responsible for using the Service in compliance with all applicable laws, regulations, and all of our Acceptable Use Policies. These policies may be updated from time to time and are provided below.
>
> ## 2. User Safety
>
> We do not allow content or activity on GitHub that:
>
> <!-- markdownlint-disable GHD034 -->
>
> * is unlawful or promotes unlawful activities;
>
> * is [sexually obscene](/site-policy/acceptable-use-policies/github-sexually-obscene-content) or relates to sexual exploitation or abuse, including of minors;
>
> * is libelous, defamatory, or fraudulent;

【判断】**分面写法的四个特征**（均可从上文直接读出）：
1. **每个分面以一句统一的否定式开头**：`We do not allow content or activity on GitHub that:` ——**主语 + 否定 + 冒号**，后面跟项列表。这使"这个分面管什么"一句话可答。
2. **每个列表项是一个独立可判定的短句**，以分号结尾。
3. **列表项可链接到子政策页**（`github-sexually-obscene-content`）——**条目本身可以是一个指针**，不必在本页展开。这是规模化的关键：主政策保持可读，细节下沉到子页。
4. **`<!-- markdownlint-disable GHD034 -->`** 出现在列表之前——一个**显式的 lint 豁免**。说明该仓库对政策文档有自动检查，且允许在特定位置声明例外。**这是"规则文档也要过 CI"的实物证据。**

#### 1.8.3 产出物模板（汇总）

| 模板 | 来源 | 用途 |
|---|---|---|
| 元数据头（title / redirect_from / versions / category） | GitHub AUP front-matter | 每条规则的字段清单 |
| Short version 摘要（显式标记） | GitHub AUP | 每条规则的人读版 |
| 术语定义段（大写即定义 + 指回主协议） | GitHub AUP | 术语表 + 唯一真源 |
| 分面写法（`We do not allow ... that:` + 短句列表 + 子页链接） | GitHub AUP §2 | 分类法的结构 |
| 可判定条件清单（动词开头、每项一属性） | AMO §6.2.2 | 每条规则的判定项 |
| 反例枚举（`including, but not limited to`） | AMO §6.2.2 | 防 annotation artifacts |
| 免责声明（"not legal advice"） | AMO L2161 | 规则库的定位声明 |
| 贡献者名单 + Last update 日期 | AMO 页脚 | 维护者与版本记录 |

#### 1.8.4 谁执行 / 耗时

**执行者**：AMO 页脚的九人具名贡献者（§1.7.4）；GitHub 的政策以源码形式由工程仓库维护（`github-docs-aup-src.md` 是 `docs` 仓库的 Markdown 源文件）。

【判断】**两家的共同点：政策文档与代码文档同仓、同流程、同 lint。** 这不是巧合——它把"改政策"从一次性法律行为变成了可评审的工程变更。客户当前把规则放在表格里，**没有版本、没有评审、没有 lint**。——依据：`github-docs-aup-src.md` 的 `markdownlint-disable` 注释 + AMO 页脚。

**耗时**：⚠️ **未找到。** 本分片未取得任何"编写一份标注规范需要多久"的实证。可参照的最近距离证据仍是 R4 §2.1 引 YouTube 的 `This process can take a few months`（指南对齐而非编写）。

#### 1.8.5 失败模式

| # | 失败模式 | 证据 |
|---|---|---|
| G1 | **无版本沿革字段 → 历史判定无法回溯到当前规则** | 【判断】缺 `redirect_from` 类字段（§1.8.2） |
| G2 | **无适用范围字段 → 同一规则被套用到不该管的场景** | 【判断】缺 `versions` 类字段（§1.8.2） |
| G3 | **同一术语多处定义** | GitHub 的纪律是"本文件未定义的指回主协议"（§1.8.2 模板 ③） |
| G4 | **只给一个示范样例 → 被学成捷径** | R4 §2.4 引 Gururangan 2018；AMO 的对策是反例枚举 |
| G5 | **政策即规则，不留人工判断空间** | AMO 自述为 `guiding principles`（L2165） |
| G6 | **规则文档不过任何自动检查** | GitHub 仓库有 `markdownlint-disable GHD034`；客户无 |

---

## 2. 方法选择矩阵（团队规模 × 数据可得性 × 时间预算 → 推荐方法）

### 2.0 客户现状的三维定位（先把客户放进矩阵）

**依据**：`01-内部证据-规则表现状审计.md` §1.1、§2.7、§三。

| 维度 | 客户实测值 | 证据 |
|---|---|---|
| **团队规模** | ⚠️ **未找到**。`01-内部证据-规则表现状审计.md` 全篇未记录团队人数、职能构成或工时预算。**本分片不推测。** | grep `团队\|人力\|编制\|人数\|工时` 于该文件，**无一条给出人数** |
| **数据可得性** | **D1（低）**：291 条记录已有判定，但**27 列中没有任何一列承载 false positive / false negative / 规则出处**；规则层 12 列中 `判断方式` 21/21 填 `自动可检测`、`适用产品` 21/21 为常量、仅 8 条有正则、5 条有豁免词 | 审计 §1.1、§三 |
| **规则与判定的自洽度** | **13.8%**：规则自带的正则跑在 291 条记录上只能复现 13.8% 的人工判定，**72.3% 一条都复现不出来，且从不多报一条** | 审计 §结论先行 |
| **时间预算** | ⚠️ **未找到**。审计文件未记录任何交付期限。 | 同上 |

【判断】**"从不多报一条"是客户定位里最关键的一个数字。** 它意味着现有正则**只在高置信时命中**——没有 false positive 的历史记录。因此**任何依赖"从误报反推规则"的方法（§1.5 数据挖掘、§1.6 HITL 的 FP 方向）在客户当前数据上都没有输入**。客户必须先手工制造出第一批 FP/FN 记录，才谈得上数据驱动。——依据：审计 §结论先行 + §三。

【判断】**"判断方式 21/21 = 自动可检测" 与 §1.7 的 AMO 样板正面冲突。** 平台方（Mozilla）把自己的政策明确定位为 `guiding principles`（L2165），即**承认多数条款需要人工判断**；客户则宣称 21/21 全部可自动检测，而实测复现率 13.8%。**两者不可能同时为真。** 这是 §3 管道的第 0 步。——依据：§1.7 + 审计 §1.1。

### 2.1 矩阵

**维度取值定义：**

| 维度 | 取值 |
|---|---|
| **团队规模** | **T1** 1 人 / 无专职规则工程师 ・ **T2** 2–4 人 ・ **T3** 5–9 人跨职能（Better Rules 编制，§1.1.4） ・ **T4** ≥9 人 / 有平台级 T&S 编制 |
| **数据可得性** | **D0** 只有政策文本 ・ **D1** 有判定记录但未结构化（**客户在此**） ・ **D2** 结构化记录含 FP/FN/出处 ・ **D3** 万级已标注语料 |
| **时间预算** | **W** ≤1 周 ・ **M** ≤1 月 ・ **Q** ≤1 季度 ・ **Y** ≥1 年 |

**推荐表**（每格给出**首选方法**与**禁止方法**）：

| | **D0 只有政策** | **D1 记录未结构化** | **D2 含 FP/FN** | **D3 万级语料** |
|---|---|---|---|---|
| **T1** | **W**：只做 §1.1.3 ③ 业务规则陈述（一条件一行）+ §1.8 模板 ① 加 `redirect_from`/`versions`/`category` 三字段。**禁**：Better Rules 工作坊（需 9 人）、rules-as-code | **W**：同上 + §1.1.3 ⑤ 用**表格**写测试套件（手册明示 spreadsheet 可作低技术方案，L271）。**禁**：LLM 全自动抽取 | **M**：§1.1.3 ⑤ 测试套件 + §1.6 单人与模型分歧人工裁定。**禁**：统计学习 | **M**：§1.2.6 的 LLM 抽取 + 人工抽检。**禁**：自研模型 |
| **T2** | **M**：§1.2 条文 NLP（ANNOTARES 路径，条件/后果切分）+ §1.1.3 ③ 陈述。**禁**：跳过陈述直接写代码 | **M**：**★ 客户若团队 ≥2 人的最近路径**：§1.1.3 ③+⑤ + §1.1.2 步骤 5 四轴 what-if 扰动 | **Q**：以上 + §1.2.7 LexGuard 的 should-change/should-not-change 成对测试 | **Q**：§1.2.7 LLM/BERT 抽取 + §1.6 HITL 抽检 |
| **T3** | **M**：**完整 Better Rules 工作坊**（§1.1，九人六角色，八项产出）。**这是 D0 下唯一能产出概念模型的方法** | **M–Q**：Better Rules 工作坊 + §1.8 元数据字段 | **Q**：以上 + §1.6 四种错题机制（R4 §3.5 A/B/C/D） | **Q–Y**：以上 + §1.3/§1.5 数据驱动发现 |
| **T4** | **Q**：§1.7 的 AMO 五模板全套（政策八段式 + 可判定条件清单 + 证据包 + 两级结论 + 分级执行） | **Q**：以上 + §1.1.3 ⑤ + §1.6 YouTube 五步法（R4 §2.1） | **Q**：以上 + §1.6 全循环 | **Y**：§1.3 LRI 路径（需数千案例组）+ §1.5 |

**符号说明**：★ = 对客户 **相对最现实** 的格子。**禁** = 在该格下已被证据判定不可行的方法。

### 2.2 矩阵的依据（逐格说明为什么这样推荐）

**依据 1｜T1（单人）为何禁 Better Rules。** 工作坊的**编制下限由手册写死**：`_(Aim for approximately nine people)_`（L56），六种角色各 1–2 人，且 `1-2x Legal Advisor &/or Legal Drafter/Parliamentary Counsel Representative`（L59）——**单人团队无法同时扮演法务与业务规则专家**。手册未给出减少人数的降级方案，因此 T1 下该方法**不可用**，不是"效果差"。——依据：§1.1.4。

**依据 2｜D0 为何只能靠 T3 得到概念模型。** 概念模型的机制是"分歧的计数器"（L118），它需要**至少两个持不同视角的人**才能产生分歧。T1/T2 下可以画图，但得不到"quantifying disagreements"的功能。故 D0 下推荐 T3。——依据：§1.1.3 ①。

**依据 3｜D1 为何禁用统计方法（§1.5）。** 见 §1.5.7 四条理由，核心是：RuleFit 需要已标注样本与稳定特征空间；客户 291 条记录**从不多报一条**（审计 §结论先行），即**没有正例之外的负例标注**；且 12 字段中 `适用产品` 21/21 为常量、`判断方式` 21/21 为 `自动可检测`——**特征方差为零或近零**。零方差特征无法支撑任何统计筛选。——依据：§1.5.7 + 审计 §1.1。

**依据 4｜D1 + 表格测试套件为何可行。** Better Rules 手册明示**低技术兜底**：`a spreadsheet can be a low tech solution`（L271），且测试写作分两阶段——先表达政策意图、后穷举场景（L273）。客户已有判定记录，**第一阶段（表达意图）可以直接用 21 条规则填**，不需要任何新工具。——依据：§1.1.3 ⑤。

**依据 5｜四轴 what-if 为何在 D1 下性价比最高。** 手册给出**四个现成扰动轴**：location / timing / role / classification（L226–232），并声明这"is a useful practice to apply during the development of the test suites"。它在**没有任何外部数据**的情况下就能生成边界用例——恰好匹配客户 D1 的处境。——依据：§1.1.2 步骤 5。

**依据 6｜D3 才谈得上 LRI。** LRI 的基准规模是 `5,121 case sets (38,088 court cases)` + `216 expert-annotated gold test sets`（arXiv:2505.14104）。客户 291 条记录与此差两个数量级。——依据：§1.3.2。

**依据 7｜时间预算的下界由"人"而非"机器"决定。** 唯一带单位的耗时证据：决策树 `a few minutes to several days`（L124）；平台侧指南对齐 `can take a few months`（R4 §2.1）。**没有任何一条证据支持"一周内完成规则库重建"。****故 W 格只能推荐不依赖多人协作、不依赖一致性验证的最小动作**（陈述规范化 + 字段补齐）。——依据：§1.1.5、§1.3.5、§1.6.5。

**依据 8｜T4 为何必抄 §1.7 模板。** AMO 的八段式里**第 8 章是执行机制本身**（`8. Security, Compliance and Blocking` 及 `8.1 Policy Enforcement`），且给出**三个正交升级轴**（范围 / 速度 / 触发条件）。客户 21 条规则**没有任何一章讲违反之后怎么办**——T4 规模下这是必需件。——依据：§1.7.2 模板 E。

### 2.3 矩阵的已知局限

⚠️ **"团队规模"维度本分片无客户实测值**（§2.0）。矩阵按 T1–T4 通用分级给出，**客户落在哪一档需由主 agent 补填**。
⚠️ **"时间预算"维度同样无客户实测值。**
⚠️ 矩阵未纳入**合规/法务风险**维度（属其他分片范围：严重等级定档）。
⚠️ 所有"耗时"均为**方法自身的耗时证据**，不含客户的排期约束。

---

## 3. 方法组合的推荐管道（客户从 21 条规则出发该走哪条路）

### 3.0 路线的分岔点：先回答"规则"这个词指什么

审计 §结论先行 已经给出诊断：

【原文】`01-内部证据-规则表现状审计.md` §结论先行

> 这直接解释了团队的困惑「规则库应该如何来定义」：**他们困惑的不是分类维度选哪几个，而是「规则」这个词现在同时指两样东西——一份给人看的政策文档，和一套给机器执行的判定逻辑。这两样东西已经分家了。**

【判断】**这是整条管道的分岔点，必须先于任何方法选择解决。** Better Rules 手册对这个问题有现成的处理：它把"给人看的"和"给机器执行的"**分别列为两个独立产出物**——业务规则陈述（`[base requirement]`，给人看）与规则即代码（`[base requirement]`，给机器执行），并用**测试套件**把两者绑在一起（§1.1.3 ③④⑤）。**客户的问题不是选错了方法，而是把这两个产出物压进了同一张表的 12 列里。**——依据：§1.1.3 + 审计 §结论先行。

**因此管道的第 0 步是：把 21 条规则按"能否写成可自动执行的条件"二分，而不是给每一条都填 `自动可检测`。**

**二分的判据来自 §1.7 的 AMO 样板**：一条政策只有在其判定项能被写成"动词开头的、每次只描述一个可观察属性的条件句"时，才是可自动化的（§1.7.2 模板 B）。写不成的，**显式降级为人工复核类**，不留在这个字段里。

### 3.1 推荐管道（五阶段，按依赖顺序，不按日历顺序）

**阶段 0｜字段与身份（先做，因为它解除所有后续阻塞）**

| 动作 | 依据 |
|---|---|
| 给 21 条规则补三个字段：**版本沿革 / 适用范围 / 一级分类** | §1.8.2 模板 ①（GitHub `redirect_from` / `versions` / `category`） |
| 给每条规则写一句 **Short version**（人读版） | §1.8.2 模板 ② |
| 把 `判断方式` 从 21/21 `自动可检测` **改为二分**：`自动可判定` / `需人工判断` | §1.7.2 模板 B + §3.0 |
| `适用产品` 从常量改为真实取值 | 审计 §1.5（该字段已失效） |

【判断】阶段 0 之所以排第一，是因为**客户当前 27 列记录里缺 false positive / false negative / 规则出处三列**（审计 §三），而这三列的存在与否决定了后面能不能走数据驱动的路。**补字段的成本远低于事后重建。**——依据：审计 §三。

**阶段 1｜把判定逻辑从字符串里拆出来（最高性价比的单步）**

审计 §2.7 已指出现成的结构：

【原文】`01-内部证据-规则表现状审计.md` §2.7

> 它已经在编码 `（规则编号, 命中词）` 这个二元组，用的分隔符是 `/` 与 `,`。**这是一条结构化的证据记录被写成了字符串。** 拆开它就是现成的 `evidence[]` 数组，每个元素是 `{ruleId, matchedTerm, text, span}`——只缺字符位置。

**动作**：把 `命中片段` 拆成结构化 `evidence[]`。这一步**不引入任何新方法**，只是把已有数据还原成它本来的结构。

**阶段 2｜写测试套件（用表格，不写代码）**

| 动作 | 依据 |
|---|---|
| 每条规则写 N 行 `输入场景 → 期望输出`，用**电子表格** | §1.1.3 ⑤：`a spreadsheet can be a low tech solution`（L271） |
| 先"表达政策意图"，再"穷举可能场景"——两阶段分开做 | §1.1.3 ⑤：`Writing tests is initially an exercise in expressing the policy intent but then switches to an exhaustive analysis of possible scenarios`（L273） |
| 用**四轴扰动**生成边界用例：location / timing / role / classification | §1.1.2 步骤 5（L226–232） |
| 写测试的角色与写规则的角色**分开** | §1.1.2 步骤 6（L248 vs L269：两组角色不重叠） |

【判断】阶段 2 的关键不是覆盖率，而是**让非程序员进入循环**。手册原文：测试套件 `provide an easy bridge for non programmers to engage with the coding aspect of rules-as-code by being involved in the writing of the tests and studying the results`（L150）。**"studying the results" 是人在循环里的位置。**——依据：§1.6.2。

**阶段 3｜人对齐，再机器对齐**

严格照 YouTube 五步法的顺序（R4 §2.1）：

1. 写 enforcement guideline（= 客户的政策文本 + 阶段 0 的二分结果）。
2. **先用最资深的人测**——达不到高准确率则改规则，不换人。
3. 扩大测试组（至少 2–3 人，覆盖不同品类/市场）。
4. 修订规则，直到多人一致。
5. **最后**才用对齐后的判定去调 Agent。

【判断】客户目前**跳过了第 2–4 步直接做了第 5 步**（21/21 标为自动可检测，正则已上线）。这解释了为什么"正则跑在 291 条记录上只能复现 13.8%"——**规则从未经过人际一致性检验，它只是一个人的判定习惯被写成了正则。**——依据：R4 §2.1 + 审计 §结论先行。

**阶段 4｜错题本闭环（补三列，然后才谈自动化）**

审计 §三 给出的三列——**false positive / false negative / 规则出处**——必须补齐。补齐之后，§1.6.6 的 H1/H3 与 R4 §3.5 的 A/B/C/D 四种机制才具备运转前提。

**阶段 5（可选，且必须最后）｜考虑 LLM 辅助与数据驱动发现**

只有当 D 达到 **D2**（含 FP/FN 的结构化记录）时才启用 §1.2 的 LLM 抽取；只有达到 **D3** 时才考虑 §1.3/§1.5。

### 3.2 两条不推荐的路，以及为什么

**不推荐 A：先上 LLM 全自动抽取 21 条规则 → 再人工校对。**
理由：§1.2.6 的头号失败模式是 **"it may produce correct text, but outside the scope of the problem in question"**——产出看起来完全正确但不回答本条政策的问题。在客户当前**连"规则该长什么样"都没统一**（§3.0）的阶段，这种失败**无法被检出**，因为没有任何基准可对照。**LLM 抽取需要先有一个已验证的规则格式作为落点。**——依据：§1.2.6 + §3.0。

**不推荐 B：先跑 RuleFit / 关联规则挖掘找规律。**
理由见 §1.5.7 四条，核心是**零方差特征 + 无负例标注**（审计 §1.1、§结论先行）。且顺序颠倒会产出**事后合理化**的规则，与 isomorphic 要求方向相反。——依据：§1.5.7。

### 3.3 管道的最小可行子集（若时间预算 ≤ 1 月）

若客户团队规模为 **T1–T2** 且时间预算紧，**只做阶段 0 + 阶段 1 + 阶段 2 的前两行**，即：

1. 补三个字段 + `判断方式` 二分；
2. 拆 `命中片段` 为 `evidence[]`；
3. 用表格给每条规则写测试行，先只做"表达政策意图"这一阶段。

**这三步不依赖任何人际协作机制、不依赖新工具、不需要九人团队，且每一步都有手册或审计的逐字依据。** 剩余的阶段 3/4/5 随人力到位再推进。

### 3.4 管道的已知风险

| 风险 | 依据 |
|---|---|
| **阶段 0 的二分若被跳过，后面全部失效** —— `自动可检测` 21/21 是单点故障 | §3.0 + 审计 §1.1 |
| **阶段 3 的一致性检验耗时无法预估** —— 唯一参照是 YouTube 的 `a few months`，且那是平台级规模 | R4 §2.1 |
| **客户团队规模与时间预算均未取得** —— 管道排期无法落具体日历 | §2.0、§2.3 |
| **四轴 what-if 的产出量可能超出人工消化能力** —— 手册未给出用例数量的上限建议 | §1.1.2 步骤 5（无数量约束） |

---

## 4. 不可达来源

**本节记录本分片实际尝试过的全部路径与真实返回状态。** 凡标注「未找到」的内容，均指在该路径下确实未取得可核实原文，而非未检索。抓取日期均为 2026-09-15。

### 4.1 任务书预告不可达（本分片未重试或仅试一次）

| 目标 | 状态 | 说明 |
|---|---|---|
| `betterrules.govt.nz` | **被 Incapsula 阻断，未重试** | 按任务书指示直接放弃，改用 GitHub `ServiceInnovationLab` 仓库，**成功** |
| `ofcom.org.uk` | 未尝试 | 任务书预告不可达 |
| `link.springer.com/book/10.1007/978-1-4471-0031-2`（CommonKADS） | **HTTP 404** | `_evidence/R8/commonkads-book.txt`，22,816 字节，正文 `Page Not Found` |
| `dare.uva.nl/search?identifier=8e5e0d75-...` | **HTTP 200 但内容为 `Record not found`** | `_evidence/R8/ck-thesis-uva.txt`，6,976 字节。⚠️ **HTTP 200 ≠ 内容存在** |
| `commonkads.com` | 未尝试 | — |

### 4.2 本分片新尝试且失败的路径

| 目标 | 状态 | 证据 |
|---|---|---|
| `https://www.digital.govt.nz/standards-and-guidance/technology-and-architecture/better-rules` | **HTTP 404** | `_evidence/R8/test-betterrules.txt`（1,320 字节，正文为 `Page not found`） |
| `export.arxiv.org/api/query`（arXiv 官方 API，全部查询） | **HTTP 429 `Rate exceeded.`** | 单次调用亦被限流；`_evidence/R8/arx-deontic.xml` 全文 14 字节即 `Rate exceeded.`；`w2/arx-*.txt` 共 **8** 个文件均为 `PARSE FAIL ... len= 14` |
| `https://raw.githubusercontent.com/ServiceInnovationLab/betterrules.nz/master/README.md` | **HTTP 000（连接失败）** | `_fetchlog-w2.tsv` |
| arXiv 搜索 `all: deontic modality classification legal text` | **HTTP 200，0 结果** | `_evidence/R8/w2/s-deontic.html`（16,498 字节） |
| arXiv 搜索 `all: decision table mining Vanthienen` | **HTTP 200，0 结果** | `_evidence/R8/w2/s-dectable.html`（16,468 字节） |

**【判断】关于 `decision table mining` 与 `deontic modality classification` 的负面结论**：两者在 arXiv 全库检索均返回 **0 结果**。可能的解释有三种，本分片**不加以裁定**：① 这两个方向的文献不在 arXiv 上（决策表方法学主要发表在信息系统/BPM 会议与期刊，道义逻辑主要在人文与法律计算会议）；② 检索式过窄；③ 该方向本身文献稀少。**因此任务书要求的 Vanthienen/Wets 方法学的步骤细节与道义模态分类方法，本分片一律标记「未找到可核实原文」，不以常识填充。**

### 4.3 本分片新尝试且成功的路径（可复用）

| 目标 | 状态 | 产出 |
|---|---|---|
| `https://arxiv.org/search/?query=...&searchtype=all`（**HTML 端点**） | **HTTP 200，可用** | ⚠️ 注意：arXiv 已改版，`<li class="arxiv-result">` 为分块标记，旧的 `list-title` 正则会返回 0 命中造成"无结果"的假象——**本分片首次解析即因此误判** |
| `https://arxiv.org/abs/2608.03898` | **HTTP 200, 40,756 B** | ANNOTARES（法条条件/后果切分） |
| `https://arxiv.org/abs/2505.14104` | **HTTP 200, 42,972 B** | Legal Rule Induction |
| `https://arxiv.org/abs/2605.26530` | **HTTP 200, 42,320 B** | LexGuard |
| `https://arxiv.org/abs/0811.1679` | **HTTP 200, 42,320 B** | ✅ **真正的 RuleFit 原文**（Friedman & Popescu） |
| `https://raw.githubusercontent.com/ServiceInnovationLab/betterrules.nz/master/index.html` | **HTTP 200, 1,262 B** | Better Rules 官方四要素定义 |
| `https://api.github.com/repos/ServiceInnovationLab/betterrules.nz/git/trees/...` | **HTTP 200, 10,318 B** | 仓库文件树（`_evidence/R8/brnz-tree.json`） |

### 4.4 未取得的材料汇总（「未找到」清单）

1. Feigenbaum「knowledge acquisition bottleneck」原始表述 —— **未找到可核实原文**
2. CommonKADS 建模方法（六类模型）步骤 —— **未找到可核实原文**
3. Vanthienen / Wets 决策表挖掘方法学 —— **未找到可核实原文**
4. 道义模态分类（deontic modality classification）方法学 —— **未找到可核实原文**
5. Better Rules 工作坊的总时长 —— **未找到**
6. Questions & Question Flows / Service Design Research / Process Flows 三项产出的步骤（手册原文为 `#Todo`）—— **未找到**
7. 客户团队规模与时间预算 —— **未找到**（`01-内部证据-规则表现状审计.md` 未记录）
8. 各学术论文的正文指标数字（F1 / κ 等）—— **未取得正文，仅摘要级证据**

---

## 5. 证据清单

### 5.1 强证据（HTTP 200，本分片实际引用）

| 文件 | 大小 | 来源 / URL | 用于 |
|---|---|---|---|
| `_evidence/R8/brnz-workshop-manual.md` | 18,728 B | GitHub `ServiceInnovationLab/betterrules.nz` `workshop-manual.md`（经 `brnz-tree.json` 校验 blob 大小一致） | **§1.1 全部、§1.3/§1.4/§1.6 部分** |
| `_evidence/R8/w2/betterrules-index.raw` | 1,262 B | `raw.githubusercontent.com/.../master/index.html` | §1.1.1（官方四要素定义） |
| `_evidence/R8/brnz-tree.json` | 10,318 B | `api.github.com/repos/ServiceInnovationLab/betterrules.nz/git/trees/...` | 仓库结构、blob 校验 |
| `_evidence/R8/ke-llm-drops.txt` | 40,772 B | `drops.dagstuhl.de/.../OASIcs.ICPEC.2023.9.pdf` | **§1.2（⚠️ 内容与任务书标签不符，见 §1.2 更正说明）** |
| `_evidence/R8/dsa-art34-eurlex.txt` | 419,203 B | EUR-Lex（DSA 全文） | §1.2.1 法条结构 |
| `_evidence/R8/eu-aiact-art6-eurlex.txt` | 588,942 B | EUR-Lex（EU AI Act 全文） | 未直接引用 |
| `_evidence/R8/w2/abs-2608.03898.raw` | 40,756 B | `arxiv.org/abs/2608.03898` | §1.2.7（1） |
| `_evidence/R8/w2/abs-2505.14104.raw` | 42,972 B | `arxiv.org/abs/2505.14104` | §1.2.7（2）、§1.3、§1.5 |
| `_evidence/R8/w2/abs-2605.26530.raw` | 42,320 B | `arxiv.org/abs/2605.26530` | §1.2.7（3）、§1.6 |
| `_evidence/R8/w2/rulefit-abs.raw` | 42,320 B | `arxiv.org/abs/0811.1679` | **§1.5.0（真正的 RuleFit）** |
| `_evidence/R7/amo-addon-policies.txt` | 83 KB | Mozilla Extension Workshop；页面标注 `Last update: Apr 30, 2026` | **§1.7 全部** |
| `_evidence/R7/amo-review-rejection.txt` | 68 KB | 同上 | §1.7.2 模板 D |
| `_evidence/R7/amo-source-code-submission.txt` | 75 KB | 同上 | §1.7.1（备份） |
| `_evidence/R7/github-docs-aup-src.md` | 129 行 | GitHub 官方仓库 Markdown 源（带 YAML front-matter） | **§1.8 全部** |
| `_evidence/R8/nist-ai-rmf-playbook.txt` | 163,053 B | `nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf`（由父 agent 核验内容为真实 PDF 文本） | 未在本分片直接引用 |

### 5.2 弱证据 / 不可用（已记录，未引用）

| 文件 | 状态 | 原因 |
|---|---|---|
| `_evidence/R8/rulefit-arxiv.txt` | HTTP 200，38,937 B | ⚠️ **内容为 arXiv:0811.3652 组合数学论文，非 RuleFit** |
| `_evidence/R8/commonkads-book.txt` | HTTP 404 | 正文 `Page Not Found` |
| `_evidence/R8/ck-thesis-uva.txt` | HTTP 200 | 正文 `Record not found` |
| `_evidence/R8/test-betterrules.txt` | HTTP 404 | 正文 `Page not found` |
| `_evidence/R8/arx-deontic.xml` | HTTP 429 | 全文 `Rate exceeded.` |
| `_evidence/R8/w2/arx-*.txt`（7 个） | HTTP 429 | 全部 `PARSE FAIL ... len= 14` |
| `_evidence/R8/w2/s-deontic.html` / `s-dectable.html` | HTTP 200 | **0 结果**（真实搜索结果为空） |
| `_evidence/R8/brnz-workshop-example.md` | 53 B | 全文仅 `#TODO` |
| `_evidence/R8/ofcom-*` | 403 挑战页 | 任务书已预告 |

### 5.3 二手引用（引自已完成分片，本分片未独立复核原始文件）

本分片引用了以下**已由其他分片逐字取证**的内容，均已在正文标注出处分片与节号：

| 内容 | 来源分片 |
|---|---|
| YouTube enforcement guideline 五步法、`This process can take a few months` | R4 §2.1 |
| Gab Hate Corpus 训练手册解剖、Fleiss κ 表、`Implicit/Explicit` 维度结论 | R4 §2.2、§2.4 |
| Gururangan et al. 2018 annotation artifacts 三处逐字 | R4 §2.4 |
| Plank, Hovy & Søgaard 2014；Basile et al. 2021 分歧三来源 | R4 §2.4 |
| 错题本四种机制 A/B/C/D | R4 §3.5 |
| 多数投票不提高可靠性 | R4 §5.2.4 |
| 客户现状：12 列字段名、21/21 `自动可检测`、13.8% 复现率、`命中片段` 结构、错题本缺三列 | `01-内部证据-规则表现状审计.md` §1.1、§1.5、§2.7、§结论先行、§三 |

⚠️ **`_evidence/R8/brnz-workshop-manual.md` 是同内容三份副本之一**（与 `R3/repos/betterrules.nz/workshop-manual.md`、`R3/repos/brnz-org/workshop-manual.md` 同哈希，由父 agent 核验）。**本分片按一份来源引用，不构成三源交叉印证。**

---

*分片 R8-W2 完*
