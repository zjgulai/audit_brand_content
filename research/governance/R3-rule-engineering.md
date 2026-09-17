# R3 — 规则工程与 Rules-as-Code：规则 schema / 作用域 / 版本 / 冲突

> 分片：R3（见 `00-调研任务书.md` 第三节）
> 写作日期：2026-09-15
> 抓取日期：所有 URL 的抓取日期均为 **2026-09-15**（除个别标注外）
> 原始证据保存在 `research/governance/_evidence/R3/`
> 本分片**不涉及**平台政策结构（R1）、裁决案例机制（R2）、T&S 运营度量（R4）、母婴品类监管（R5）

---

## 结论先行

委托方问「审核规则库应该按 国家 × 品类 × 平台 × 内容类型 定义吗」。把这个问题放到规则工程（rule engineering）三十年的方法论里看，答案是清楚的：

1. **四维笛卡尔积是错的**——不是因为它维度太多，而是因为**它把「作用域」和「规则本体」混在一张表里**。所有成熟体系（LegalRuleML、ODRL、XACML、Cedar、DMN、OpenFisca、DPV、DAPRECO）都把「这条规则说什么」与「这条规则在哪些情形下适用」**分开建模**，再用一个显式的关联机制把它们连起来。合并建模导致的必然结果是：每改一次适用范围就要复制一遍规则体，规则条数按维度乘积膨胀，同一逻辑出现 N 个副本，副本之间必然漂移。**最锐利的一条反证来自 DPV（W3C 社区组最终报告）：它处理「同一概念在 N 个国家有 N 套规定」的做法，是给每个辖区一个独立的命名空间（ISO 3166-2），法律在各自命名空间内定义——而不是给概念加一个 `jurisdiction` 字段。** 更强的两条：DPV 在术语层面把规则本体定义为**不含任何上下文的概念**（`Rule` 的定义里没有辖区/平台/品类，§9.2.7）；DAPRECO 把整部 GDPR 转写成 **966 条规则却只用了 4 个作用域容器**（§9.2.9）——作用域是**可复用的引用集合**，不是逐行重复的列。

2. **一条规则的规范构成是四层，不是一张宽表**：

   | 层 | 内容 | 标准里的对应 |
   |---|---|---|
   | L1 本体（rule body） | 模ality（义务/禁止/许可）+ 判定逻辑 + 结论 | LegalRuleML `PrescriptiveStatement` + deontic operator；Cedar `effect` + `scope` + `condition` |
   | L2 作用域（applicability / scope） | 主体、客体、行为、辖区、时间 | LegalRuleML `Jurisdiction` / `Authority` / `TemporalCharacteristic`；Cedar `principal/action/resource`；ODRL `assigner/assignee/target/action` |
   | L3 约束（constraint） | 阈值、正则、枚举、豁免条件 | ODRL `Constraint`（`leftOperand` + `operator` + `rightOperand`）；DMN input entry |
   | L4 治理元数据（governance metadata） | 稳定 ID、版本、来源、强度、优先级、状态、责任人 | Akoma Ntoso `eId`/`wId` + FRBR；LegalRuleML `hasStrength`/`Override`；DMN `hitPolicy`；Drools `salience`/`date-effective` |

   「国家 × 品类 × 平台 × 内容类型」**全部属于 L2**。它们不是规则的分类轴，而是作用域声明的四个字段值。

3. **兜底必须显式声明，几乎是所有体系的硬性要求**。Cedar：没有任何 `permit` 命中时默认 `Deny`，且这个 `Deny` 必须在文档里写明叫 *implicit deny*（Cedar docs, Authorization 节）。OPA：`default allow := false` 必须写出来，不写则 `allow` 是 `undefined` 而不是 `false`（OPA Policy Reference "Default Keyword" 节）。DMN：`hitPolicy` 有默认值 `UNIQUE`，但**只要规则可能重叠，hit policy 指示符就是强制的**（DMN 1.5 §8.2.11）。ODRL：不写 `conflict` 属性时的默认策略是 `invalid`——**整条 Policy 作废**，而不是随便挑一条（ODRL IM §2.10）。**DPV：明确声明「不定义规则的默认解释」，并说明理由——默认值会迫使表达差异时复制实例、摧毁模块化（DPV Modules → Rules §3.1，逐字见 §9.2.8）**。**DAPRECO：962 条带作用域的规则，每一条都被显式指派到四个 context 之一，没有一条是「不写就默认」（§9.2.9）**。SPECIAL：连「用户没勾选时算 opt-in 还是 opt-out」都不肯默认，而是显式列为推迟议题（§9.2.10）。理由是一致的：隐式默认让「没命中任何规则」和「命中了但结论为通过」不可区分，而这两件事的责任归属完全不同。

4. **规则唯一标识要同时满足两个互相拉扯的性质**。Akoma Ntoso 的命名约定给出三条原则：`MEANINGFULNESS`（有意义）、`PERMANENCE`（永久）、`INVARIANCE`（从资源的不变属性导出）。实操答案是**双 ID**：一个面向人的可读编码（work 层，永不变，如 `H01`、`akn/nz/act/2003/12/!main`）+ 一个面向机器的版本化 ID（expression 层，随版本变化，如 `wId`/`eId`/内容哈希）。Cedar 和 OPA 都不要求 ID 语义化，反而强调「用 UUID，永不复用」——因为它们的 ID 只用于**引用与审计**，不承担可读性职责。可读性由 `annotation` / `@id` 注释承担。

5. **冲突消解不是「谁优先」一个问题，而是三种不同策略，必须在规则集层面显式声明**：`deny-overrides`（禁止优先，Cedar/XACML/ODRL `prohibit`）、`permit-overrides`（许可优先，XACML/ODRL `perm`）、`void`（冲突即整个规则集作废，ODRL 默认）。DMN 把同一件事叫 hit policy（`U`/`A`/`P`/`F`/`C`）。古典法律解释三原则（lex specialis / lex superior / lex posterior）是**这三种策略在选择时的判据**，不是替代品。**ILC（联合国国际法委员会）结论 (6) 明确说「哪个考虑因素占主导应当依情境决定」，结论 (4) 说「首先应当调和」**——所以三条原则**不能**被硬编码成规则引擎的自动优先级，只能作为规则库里的显式声明字段 + 人工评审时的论证依据。

6. **规则的版本治理要沿三条时间轴做，只做一条会出错**。LegalRuleML 明确区分 `entry`（生效）、`efficacy`（产生效果）、`applicability`（适用）三条轴（§4.3.5）。OpenFisca 的做法是工程化的标准答案：参数用**日期键**（`values: {2016-01-01: {...}, 2017-01-01: {...}}`），公式用**日期后缀**（`formula_2017`），废止用 `end = 'YYYY-MM-DD'` 或 `value: null`。历史判定复现 = 用同一个 `period` 参数重跑同一份带日期的规则集。

7. **「开放概念」（reasonable、足够、显著）在所有体系里都不是靠规则解决，而是靠「显式降级」解决**：OpenFisca 直接声明不做（"any process that includes human judgement can not be completely automated. Human decisions can be modelled as input variables"）；LegalRuleML 提供 `DefeasibleStrength`（可被推翻）与 `<lrml:Paraphrase>`（自然语言复述）；DMN 提供 `RuleAnnotationClause`（不参与判定、只供审计）；Cedar 提供 `error` + `skip on error`（求值出错则该 policy 不参与，而不是崩掉整个决策）。共同点：**「这条规则无法自动判定」本身是一个取值，必须能表达出来**。

8. 对 Momcozy 的 12 字段 schema：**多的是 `检测关键词`/`正则表达式`/`豁免词` 三个实现细节字段**（它们属于 L3，且应当拆出去以「检测器」为单位管理，而不是挂在规则行上）；**缺的是** modality（规则类型）、稳定 ID 与版本、作用域声明（jurisdiction/platform/content_type/effective_from/effective_to）、强度与优先级、兜底声明、责任人/审批人、以及「无法自动判定」这一取值。详见第 11 节。

---

## 0. 本文的证据方法、范围与已知局限

### 0.1 证据标准

本文所有引用分为三类，用不同标记区分：

- **[原文]** — 直接抓取的一手来源原文，逐字引用，给出 URL + 定位（章节号 / 元素名 / 行号）。
- **[本地]** — 抓取物在 `research/governance/_evidence/R3/` 下的路径。
- **[判断]** — 作者基于原文的分析，不是原文内容。

**关于 PDF 来源的逐字引用精度**：ILC 报告（A/CN.4/L.702）、VCLT、DMN 1.5、Cedar 论文这几份是 PDF。本环境没有 `pdftotext` 等工具，正文由自写的 zlib 流 + 文本算子提取脚本产出，**存在字间被插入空格的现象**（例如原文的 "specific" 在提取结果里可能是 "sp ecific"）。本文引用时**已把这类提取伪影还原为正常拼写**，但读者若需逐字符比对，应以 URL 指向的原始 PDF 为准。HTML 来源（LegalRuleML、Akoma Ntoso、XACML、ODRL、OPA、Cedar docs、OpenFisca、Workshop Manual、DPV）不受此影响。

**关于第二代提取器（本轮新增，R1–R5 均可复用）**：上述第一代脚本对嵌入字体 / 对象流的 PDF 会产出 0 字符。本轮由子代理写出的第二代纯 Python 提取器解决了该问题（处理 FlateDecode、对象流中的嵌套流、Form XObject、逐页字体资源、ToUnicode CMap、`/Differences` 字形名与连字），**由此解锁了 DAPRECO 论文全文与 SPECIAL D2.1–D2.4 全文**。脚本已存入 [本地] `_evidence/R3/tools/pdftext5.py`，用法 `python3 pdftext5.py in.pdf out.txt`。

**关于「二手转述 vs 一手工件」的一条实操教训**：本轮有一处二手转述（「DAPRECO 所有公式都带 t ≥ 2018-05-25」）在**一手工件上不成立**——该日期在 5.6 MB 的知识库里只出现 1 次，且只是被形式化文本的版本标识符（§9.2.9 有完整更正记录）。**凡有工件可读，就不要采信对工件的叙述**；且计数时要写明口径（开标签 / 剥离注释后的出现次数）。

### 0.2 抓取失败与不可达来源（重要）

本次抓取环境存在明确的网络限制，以下来源**不可达**，必须在阅读本文时心里有数：

| 来源 | 状态 | 尝试过的方式 |
|---|---|---|
| `www.digital.govt.nz/dmsdocument/95-better-rules-for-government-discovery-report/html` | **被 Imperva/Incapsula JS 挑战拦截**（返回 212 字节壳页） | curl 直接请求、Googlebot UA、三种浏览器 UA、cookie jar 两段式、http/https、www/非 www、`read_page` 工具 |
| `www.digital.govt.nz/dmsdocument/116-better-rules-handbook/html` | 同上 | 同上 |
| `www.betterrules.govt.nz/`（Better Rules 官方站） | 同上（212 字节壳页） | curl |
| `web.archive.org` / `archive.org` | **DNS 被污染**（`web.archive.org` 解析到 `108.160.167.165`，属 Dropbox 段），连接超时 | curl（rc=28 超时） |
| `r.jina.ai`（代理） | 连接超时 | curl |
| `www.oecd.org` / `oecd-ilibrary.org` / `oecd-opsi.org`（OECD《Cracking the Code》报告） | HTTP 403 | curl，多路径 |
| `exa_search` / `web_search` / `read_page` 工具 | 本次会话中限流或引擎失败 | — |
| `duckduckgo.com` / `google.com` / `search.brave.com` | 不可达 | curl |
| `www.mojeek.com` | HTTP 200 但返回 JS 挑战页 | curl |

**后果**：新西兰《Better Rules for Government Discovery Report》与《Better Rules Handbook》的**正文我未能逐字读到**。本文关于 Better Rules 的论述建立在三份**可达的一手来源**上，都是同一个机构（新西兰 Service Innovation Lab）的产物：

1. `betterrules.nz/workshop-manual.html` —《The Practical Better Rules Workshop Manual》，作者 Hamish Fraser（Service Innovation Lab），Version: Draft-02。这是该 Lab 自己发布的方法论文档。
2. `serviceinnovationlab.github.io/projects/legislation-as-code/` — Lab 的项目页。
3. GitHub 组织 `BetterRules` 与 `ServiceInnovationLab` 下的**源代码与测试数据**（`example-rules-as-code`、`Piccolo`、`openfisca-aotearoa`），这是把方法论落地的直接产物。

Discovery Report / Handbook 的缺口已记入附录 B。

### 0.3 分片边界

本文只写规则工程本身。以下**有意不写**：平台政策的具体条款（R1）、广告裁决案例（R2）、审核队列运营指标（R4）、母婴品类法规（R5）。凡涉及这些的交叉点，只标注「见 R1/R2/R4/R5」，不展开。

---

## 1. 分析框架：一条规则由哪四层构成

在进入各个体系之前，先建立一个统一的观察框架。[判断，但每一层都能在原文里找到直接对应]

| 层 | 回答的问题 | 典型字段 | 变动频率 |
|---|---|---|---|
| **L1 规则本体** | 这条规则**说什么**？ | modality（禁止/义务/许可）、判定逻辑、结论类型 | 低（业务本质变化才改） |
| **L2 作用域** | 这条规则**在什么情形下适用**？ | 主体、行为、客体、辖区、时间窗 | 高（进新市场就要改） |
| **L3 约束/检测器** | 这条规则**怎么被判定**？ | 关键词、正则、阈值、比较算子、豁免条件 | 最高（调参、修 bug） |
| **L4 治理元数据** | 这条规则**凭什么有效、谁负责、优先级多少**？ | 稳定 ID、版本、来源出处、强度、优先级、状态、审批人 | 中 |

**[判断]** 判断「一个国家 × 品类 × 平台 × 内容类型的四维表该不该做」的关键，是看这四个维度落在哪一层。它们**全部落在 L2**。而 L2 在所有成熟体系里都是**独立于 L1 存储、通过声明关联到 L1** 的。下面逐个体系给出直接证据。

---

## 2. 新西兰 Better Rules / Rules as Code

### 2.1 组织背景与一句话定义

**[原文]** Service Innovation Lab 项目页：

> "This important work started when looking at Rules as Code as part of the Lab's reusable components workstream. The team soon realised there was a systemic issue that other agencies were interested in exploring how to ensure government rules could be accurately delivered as Rules as Code without creating yet another siloed version of the rules (which is essentially what happened with the coded legislation behind the SmartStart financial help tool)."
> — `https://serviceinnovationlab.github.io/projects/legislation-as-code/` [本地] `raw/sil-legislation-as-code.txt`

**这句话就是 Momcozy 场景的同构命题**：如果一个组织允许「编码版本的规则」与「人读版本的规则」并排存在，就一定会出现孤岛化的多版本。[判断]

**[原文]** 同一页面对 Rules as Code 与 Better Rules 的分野：

> "This approach can be thought of as Rules as Code. This is usually done after the rules have already been written and requires a reinterpretation of the rules by service delivery people and software developers. This has proved a risky approach where implementation by government and non-government organisations are out-of-step with either the intent or the actual rules.

> What is new is testing the implementation logic and service design impacts alongside the policy development process, utilising approaches from other disciplines such as human centred design and test-driven software development. This opening up of the drafting process to include other ways of thinking and testing the rules has been coined 'Better Rules'."
> — 同上

**[判断]** 对 Momcozy 的映射：他们的 21 条规则库 + 19 条 W1 卖点边界 + 52 条改写建议库，正是「规则已经写完之后再做编码」的 Rules-as-Code 路径。风险不在于路径本身，而在于**没有把三个库对齐到一个 L1 上**（见第 11 节）。

### 2.2 转换流程：五个输出物，四个是必需项

Better Rules 方法论的核心是一组**具名的中间产物（outputs）**。Workshop Manual 明确给每一项标了 `[base requirement]` 或 `[optional output]`：

| 输出物 | 标记 | 原文定义（逐字） |
|---|---|---|
| Concept Models | **base requirement** | "Concept models form a working map of the concepts that make up the domain the team is focusing on and are the essential central component to the workshop's process. They allow the team to create a visual shared understanding of the domain and its scope, and it becomes a reference point that allows all the other expected outputs to achieve a high level of consistency." |
| Decision Trees | optional output | "Decision trees map the logic and ways people and systems practically navigate the concept models." |
| Business Rule Statements | **base requirement** | "Business rule statements are precisely written statements of logic describing each rule in a set of rules succinctly." |
| Rules-as-Code | **base requirement** | "Rules-as-code are best thought of as an opportunity to test the policy by trying to explain it to a computer." |
| Test Suites (aka Policy Intent) | **base requirement** | "Test suites are an adoption from the world of software development. Think of them as capturing and preserving policy intent. A test is a description of a scenario with given inputs and what the expected output(s) should be." |
| Questions & Question Flows | optional output | "Question flows inform the impact rules will have on the types of problems Service Designers focus on." |
| Service Design Research | optional output | "An extension to the question flows is the consideration of the impact the ruleset has on delivery of services that might be attached to the ruleset." |
| Process Flows | optional output | "Process flows are detailed flow charts of the process(es) that will be required to support the rules." |

> 全部引自 `https://betterrules.nz/workshop-manual.html`（[本地] `repos/betterrules.nz/workshop-manual.md` 第 115–168 行）

**[原文]** 所以**转换流程的骨架是**（顺序即 Manual 的章节顺序，第 193–273 行）：

```
Concept Model（概念模型，贯穿全程、反复重画）
    ↓
Decision Trees（决策树：决定顺序与逻辑依赖）
    ↓
Business Rule Statements（业务规则陈述：每条规则一句精确的逻辑陈述）
    ↓
Rules-as-Code（规则即代码：isomorphic 映射）
    ↓
Test Suites（测试集：把"政策意图"固化成输入→期望输出的场景表）
```

Manual 对 Business Rule Statements 给了一个逐字的例子：

> "A person is eligible to vote if:
> * their age is 18 years or more, and
> * they have lived in the district for 6 months"
> — 同上，第 132–134 行

**[判断]** 注意这个例子的结构：**主语（person）+ 条件列表 + 结论（eligible to vote）**。它没有出现「国家」「渠道」这类限定词——那些属于作用域，另处声明。这正是「规则本体与适用范围分离」的最朴素体现。

### 2.3 规则表示结构：`isomorphic`（同构）是硬要求

**[原文]** Manual 在 "Developing Rules-as-Code" 一节，对「代码与规则原文的关系」给了全文最强的一条约束：

> "While coding the rules, it's expected that the rules-as-code specialist keeps an eye on the underlying concept model and any assumptions they may find themselves making while developing the code should be raised. The art of coding rules is to be very careful to not include any assumptions or extensions of logic accidentally into the code but faithfully mirror the rules in an isomorphic fashion."
> — 同上，第 258 行

**[判断]** 「isomorphic」这个词是整套方法论的价值观锚点：规则代码**不允许**比规则原文更聪明。任何「代码里补了一个原文没有的判断」都是缺陷，不是优化。这对 Momcozy 有直接含义——他们的 `判断方式` 字段 21/21 全填「自动可检测」，这本身就是一次未经原文授权的假设（见 §11.5）。

### 2.4 授权与批准

**[原文]** Manual 里关于「谁批准一条规则从草稿变为生效」的直接表述**很少**。它给的是**团队构成**与**角色分工**，而不是审批流：

> "_(Aim for approximately nine people)_
> * 1-2x Subject Matter Specialist
> * 1-2x Policy Advisor
> * 1-2x Legal Advisor &/or Legal Drafter/Parliamentary Counsel Representative
> * 1-2x Rules-as-Code Specialist
> * 1-2x Service Designer
> * 1-2x Business Rules Specialist"
> — 同上，第 56–62 行

以及对每个输出物标注 `**Suggested Roles:**`，例如：

> "**Suggested Roles:** [Legal Advisor, Business Rules Specialist, Service Designer, Rules-as-code Specialist]"（Developing Decision Trees）
> "**Suggested Roles:** [Business Rules Specialist, Legal Advisor]"（Developing Business Rule Statements）
> "**Suggested Roles:** [Rules-as-code Specialist, Legal Advisor]"（Developing Rules-as-Code）
> "**Suggested Roles:** [Subject Matter Specialist, Policy Advisor, Rules-as-code Specialist]"（Test Suites）
> — 同上，第 237、248、256、269 行

**[原文]** 整份文档的口径是「共识」而非「审批」：

> "Expect a sense of agreement to develop within the group and for that to be suddenly interrupted by disagreement, repeatedly. The concept model provides a focal point to work out disagreements in how the model is perceived and will be modified often as part of this process. This is the concept model fulfilling its purpose."
> — 同上，第 205 行

**[判断]** **这是一个真实的缺口**：Better Rules 的公开方法论输出物里，没有「规则批准人 / 生效签核」这一层。它假设「多学科团队达成一致」就等于授权。对政府政策制定场景，授权由外部的立法程序承担；**对 Momcozy 这种没有外部立法程序的企业场景，这一层必须自己补上**——不能照搬。本文在第 11 节的建议 schema 里显式补了 `approver` / `approved_at` / `status` 三个字段，来源不是 Better Rules，而是 LegalRuleML 的 `Authority` 概念 + Akoma Ntoso 的版本层（见 §4、§7）。

Counter-evidence（反证）：the Manual 明确声明自己不是权威：

> "Consider this document a starting guide. It's a methodology we've developed based on experiments that were conducted in the Service Innovation Lab in New Zealand. Do not treat this document as authoritative; instead use it to get your team and workshop started and then adapt to suit."
> — 同上，第 48 行

### 2.5 开放概念（"reasonable" 这类）怎么处理

**这是本分片最关键的问题之一，而 Better Rules 的答案是「用测试集把它逼出来」，而不是「用规则解决它」。**

**[原文]** 处理手法一：**what-if 逼问**。Manual 明确列出四类「常常被默认掉」的变量：

> "It's often helpful in analysis of the rules to play with "what-if" statements that focused on changing variables that are often assumed.
>
> For example, what if the:
> * location (i.e. not in the country)
> * timing (change the order of events)
> * role (the caregiver is a child)
> * classification (they are not citizens)
>
> is X and does our ruleset account for that. This is a useful practice to apply during the development of the test suites which we will detail shortly."
> — 同上，第 224–232 行

**[判断]** 注意这四类里，`location` 和 `classification` 正是「作用域」变量。也就是说：Better Rules 把「作用域边界的穷举」放在**测试集**里做，而不是在规则表里做。

**[原文]** 处理手法二：**测试集承载「政策意图」**。

> "Test suites are an adoption from the world of software development. Think of them as capturing and preserving policy intent."
> "Writing tests is initially an exercise in expressing the policy intent but then switches to an exhaustive analysis of possible scenarios. If the rules-as-code specialist is not yet sure of the format of the tests, the scenarios can be described in spreadsheets ready for importing alongside the code."
> — 同上，第 150、273 行

**[判断]** 「无法自动判定的开放概念」在 Better Rules 体系里的归宿是：**它变成测试集里一组必须人工标注的边界场景**，以及规则代码里一个必须显式 raise 的异常/未定义值。这与 OpenFisca 的官方立场完全一致（§3.5），与 OPA 的 `undefined` 语义也一致（§5.1）。

### 2.6 测试方法：共享测试数据 + 多语言实现对照

`BetterRules/example-rules-as-code` 这个仓库是整套测试方法论的**可执行证据**。它的设计是：一部虚构法条 + 一棵决策树 + **一份共享测试数据** + 多个语言/格式的实现，全部必须通过同一份测试数据。

**[原文]** README：

> "This repo is for implementations of the made-up [Australian Beard Tax (Promotion of Enlightenment Values) Act 1934](legislation.pdf).
>
> Its purpose is to show the breadth of options in writing legislation as code, explore some of the pros and cons of different options, and to give you a starting point for encoding real legislation."
> — `https://github.com/BetterRules/example-rules-as-code` [本地] `repos/example-rules-as-code/README.md`

**[原文]** 法条原文（注意它是**自然语言中带精确定义**的条款）：

> "In this Act, beard means any facial hair no shorter than 5 millimetres in length that:
> a. occurs on or below the chin, or
> b. exists in an uninterrupted line from the front of one ear to the front of the other ear below the nose."
> — 同上

**[原文]** 共享测试数据 `shared/example_beards.yml`（完整逐字）：

```yaml
---
beards:
  - length_in_mm: 3
    outcome: false
  - length_in_mm: 2
    on_or_below_chin: false
    uninterrupted_below_nose: true
    outcome: false
  - length_in_mm: 4
    on_or_below_chin: true
    uninterrupted_below_nose: true
    outcome: false
  - length_in_mm: 5
    on_or_below_chin: true
    uninterrupted_below_nose: false
    outcome: true
  - length_in_mm: 10
    uninterrupted_below_nose: true
    outcome: true
  - length_in_mm: 20
    on_or_below_chin: true
    outcome: true
  - length_in_mm: 6
    on_or_below_chin: false
    uninterrupted_below_nose: true
    outcome: true
  - length_in_mm: 200
    on_or_below_chin: false
    uninterrupted_below_nose: false
    outcome: false
```
> — [本地] `repos/example-rules-as-code/shared/example_beards.yml`

**[判断]** 这份测试数据有三处值得 Momcozy 直接抄的设计：

1. **每条用例只给相关字段**（第 1 条只给 `length_in_mm`，第 5 条只给 `uninterrupted_below_nose`）。缺省字段代表「不适用 / 未指定」，而**不是默认 false**。这逼着实现必须区分「条件不满足」与「条件缺失」。
2. **边界值被显式覆盖**：`3/4/5/6` 全在（阈值 5 的两侧），`200` 也在（远超标）。这就是 OpenFisca 说的 `textual comparisons` 缺失的补法——用用例把阈值钉死。
3. **`outcome` 是布尔，不是等级**。原始法条只有「是不是 beard」这一个二值结论；等级（罚多少）在另一处。**判定与定级分离**。

同一份测试数据被至少 5 种实现形式消费（[本地] `repos/example-rules-as-code/`）：

| 目录 | 形式 | 关键文件 |
|---|---|---|
| `json-logic/` | JSON 表达式树 | `beard_definition.json` |
| `blawx/` | 可视化块语言（Blockly）导出的规则+测试 | `beard.blawx` |
| `python/` | 面向对象 Python | `run.py` |
| `python-authorityspoke/` | 法条 XML + 规则 JSON + Jupyter | `example_data/codes/beard_tax_act.xml` |
| `ruby/` | Ruby | `beard_checker.rb` |

**[原文]** JSON Logic 版本（完整逐字）：

```json
{
  "and" : [
    {"==" : [ { "var" : "facial_hair_over_limit" }, "true" ]},
    { "or": [
        {"==" : [ { "var" : "on_or_below_chin" }, "true" ] },
        {"==" : [ { "var" : "uninterrupted_below_nose" }, "true" ] }
      ]
    }
  ]
}
```
> — [本地] `repos/example-rules-as-code/json-logic/beard_definition.json`

**[判断]** 这份 JSON 里**没有一个字段是「管辖区」「平台」「品类」**。作用域完全不在这棵表达式树里。这是「L1 与 L2 分离」最干净的一个样本——而且它来自「首要目标」的那个政府实验室。

### 2.7 两份关键引语的准确出处

关于「规则即代码的价值在于暴露假设」，Manual 的原句是：

> "The underlying explanation as to what happens in this process is the machine acts as an utterly unassuming context-free entity that by its nature aids in the discovery of assumptions that we miss much more easily as humans."
> "A phrase coined in response to this practice is: 'You haven't really understood your policy until you've successfully explained it to a machine'."
> — `https://betterrules.nz/workshop-manual.html`，第 142–143 行

关于概念模型是「知识资产」，另一份**独立的、由新西兰研究者撰写的评估报告**（Hamish Fraser 等，新西兰法律基金会资助项目）说：

> "A core 'knowledge asset' in the process is the 'concept model'. Within computer science, a conceptual model is also known as a domain model. It represents the core concepts in a problem domain and the relationships between them"
> — `https://hamish.dev/research/lac/part-two` [本地] `raw/hamish-lac-part-two.txt`

同一份报告对 Better Rules 与 Rules as Code 的区分给出了一个对 Momcozy 极有用的观察：

> "Importantly, a regulatory system is wider than just the legislation or legal rules that may form the legal bedrock of that wider system. Frequently, we have found that rules as code advocates are really talking about modelling a wider regulatory system, not just the law (legislation) itself."
> — 同上

**[判断]** 映射到 Momcozy：他们的规则库混合了三种不同性质的东西——**平台政策**（Google/Meta 广告政策）、**法规**（如健康声明、保险报销）、**品牌调性**（卖点表达边界）。这三类不是同一个 regulatory system，其授权来源、变更频率、责任人都不同。把它们塞进同一张 12 列表，是 §11.2 要解决的核心问题。

---

## 3. 法国 Etalab / OpenFisca

OpenFisca 是把税法与社会福利法规写成可执行代码的开源框架，由法国政府 Etalab 孵化，现由多国政府与社区共同维护。它的价值在于：**它是把「法规的时间轴」工程化得最彻底的一个体系**，而时间恰恰是 Momcozy 现有 schema 完全缺失的一维。

### 3.1 数据模型：四类对象

| 对象 | 作用 | 原文出处 |
|---|---|---|
| **Variable**（变量） | 有 `value_type` / `entity` / `label` / `definition_period` 的实体，配一个或多个 `formula` | `https://openfisca.org/doc/coding-the-legislation/` |
| **Parameter**（参数） | 法规里的数值/枚举常量，YAML 文件树 | `https://openfisca.org/doc/coding-the-legislation/legislation_parameters.html` |
| **Entity / Role**（实体/角色） | 主体建模（Person / Household / …） | `https://openfisca.org/doc/key-concepts/index.html` |
| **Period**（期间） | 计算的时间切片，是 `parameters(period)` 与 `person('salary', period)` 的入参 | 同上 |
| **Tax and Benefit System** | 上述全部的集合，即「一个版本的法规」 | 同上 |

**[原文]** Key concepts 页面把结构定义为：

> "The first entries are dedicated to the definitions of the structure of OpenFisca:
> * Tax and Benefit System as the matrix of the software
> * Variables
> * Parameters
> * Person, entities, role
> * Periods, Instants"
> — `https://openfisca.org/doc/key-concepts/index.html`

### 3.2 Parameters：日期键 + 立法引用

**[原文]** 参数的 YAML 结构（逐字）：

> "A legislative parameter is defined by a YAML file of the same name. Possible attributes are:
> * `description` (optional) Description;
> * `metadata` (optional) Can be:
>   * `reference` (optional) Legislative reference;
>   * `unit` (optional) Can be:
>     * `year`: The values are years;
>     * `currency`: The values are in the unit of currency of the country;
>     * `/1`: The values are percentages, with 1.0=100%;
> * `values`: Value of the parameter for several dates."
> — `https://openfisca.org/doc/coding-the-legislation/legislation_parameters.html`

**[原文]** 样例（逐字）：

```yaml
description: Universal income
metadata:
  unit: currency
values:
  1993-01-01:
    value: 1000
  2010-01-01:
    value: 1500
    metadata:
      reference: http://law.reference.org/universal_income
  2020-01-01:
    expected: 1700
```

**[判断]** 这个结构对 Momcozy 的意义是**三重的**：

1. **`metadata.reference` 挂在「每一个值」上，而不是挂在参数上**。也就是说：2010 年那个 1500 的法源，与 2016 年那个 0.25 的法源，可以分别记录。Momcozy 现在的 `依据来源` 是**规则级**的（21 条规则只有 2 个来源），粒度太粗。
2. **`values` 是日期→值的映射**，读值必须传 `period`。这使得「同样是 H01，在 2026-08 判为高危、在 2026-11 判为审慎」可以精确表达。
3. **`expected` 是一个独立的键**——「已知将来会变但还没变」也是数据模型里的一等公民。

### 3.3 版本化：公式的日期后缀，是 OpenFisca 最值得抄的一招

**[原文]**：

> "Some fiscal or benefit mechanism significantly evolve over time and call for a change in the formula that computes them. In this case, a simple parameter adjustment is not enough."
> — `https://openfisca.org/doc/coding-the-legislation/40_legislation_evolutions.html`

> "**Formula naming rules:**
> * A formula name must always start with `formula`.
> * To define a starting date for a formula, we add to its name a suffix made of an underscore followed by a date.
> * For instance, `formula_2017_01_01` is active from the 1st of Jan. 2017.
> * When defining a date, the month is given before the day.
> * When no month or day is specified, OpenFisca uses '01' as default value.
> * For instance, `formula_2017` is equivalent to `formula_2017_01_01`.
> * If no date is specified for a formula, OpenFisca will consider that this formula has been active since the dawn of time (or more precisely, since 0001-01-01, as Python does not handle B.C. dates)."
> — 同上

> "A formula is active until another formula, starting later, becomes active and replaces it (or until the variable end date is reached)."
> — 同上

**[判断]** 这条规则同时给出了「版本化规则」的**机制**与**兜底**：不写日期 = 从无穷早生效（catch-all）。这和 OPA 的 `default`、Cedar 的 implicit deny 是同一类设计——**兜底必须是一个可以写在规则里的东西**。

### 3.4 废止与追溯

**[原文]** 变量级废止（逐字）：

```python
class progressive_income_tax(Variable):
    value_type = float
    entity = Person
    label = u"Former tax replaced by the flat tax on the 1st of June 2005"
    definition_period = MONTH
    end = '2005-05-31'
```

> "The end day is inclusive: it is the last day a variable and its formulas are active (and not the first day it is not active anymore)."
> — 同上

**[原文]** 参数级废止（`null`，逐字）：

```yaml
description: Housing allowance amount (as a fraction of the rent)
# in parameters/housing_allowance.yaml
metadata:
  unit: /1
values:
  # This parameter is only defined from the 1st of Jan 2010 to the 1st of Jan 2017 (excluded).
  2010-01-01:
    value: 0.25
  2017-01-01:
    value: null
```

> "However, trying to obtain the parameter after 2017-01-01(included) will raise an error"
> — 同上

**[判断]** `null` 与「没写这个键」语义不同：`null` = **这条规则在该日期后不存在**（查询报错），「没写」= 沿用上一个值。这个区分极其重要，因为 Momcozy 的 U02（保险报销类）已经**停用**——在标准做法下，它应该是 `end = <停用日期>` 或 `value: null`，而不是一个 `启用状态 = 停用` 的布尔位。布尔位无法回答「停用之前的历史判定长什么样」。

**[原文]** 关于「追溯适用」（retroactive application），OpenFisca 的官方立场是**明确不做行为反馈**：

> "OpenFisca is a static micro-simulation model, so it will provide you with results 'as of tomorrow', without taking retroactive effects or 'elasticity' into account (e.g. new taxes will not impact purchasing behaviour)."
> — `https://openfisca.org/doc/index.html`

**[判断]** 注意这里 "retroactive effects" 指的是**经济主体的行为反馈**（人会不会因为新税改行为），不是「法规溯及既往」。法规溯及既往在 OpenFisca 里是靠**给历史 period 传历史参数值**天然支持的。**历史判定复现的机制 = 规则集与参数集都带日期，查询时显式传入日期。** Momcozy 应当照做：审查记录必须存「判定时所用的规则集版本 ID」，而不是只存命中规则编号。

### 3.5 「开放概念」：OpenFisca 的官方拒绝清单

这是全篇最诚实的一段官方声明，逐字：

> "**Human decisions**
> This might seem obvious, but it is worth reiterating: any process that includes human judgement can not be completely automated. Human decisions can be modelled as input variables, but OpenFisca does not aim at doing machine learning on past decisions for probabilistic results, for example."
>
> "**Zero effort modelling**
> While our community is strong and you can often benefit from its shared efforts, OpenFisca is contributive: if the legislation you need is not described yet, you're the best person to add it (take a look at our contribution guidelines first)."
>
> "**Magical legislation parsing**
> OpenFisca is a framework for humans to collaborate on translating rules into code. It does not ingest lawyer speak and automatically produce developer speak. Regulations are ambiguous and need human interpretation before they can be codified."
>
> "**Textual comparisons**
> OpenFisca shines in dealing with numbers: enumerated values are a later addition, and support for string values is not built-in."
> — `https://openfisca.org/doc/index.html`

**[判断]** 最后一条对 Momcozy 是**当头一棒**：OpenFisca——一个由法国政府支持、专门做法规编码的框架——公开承认**它不擅长文本比较**。而 Momcozy 的 21 条规则里，检测手段几乎全是关键词与正则，即纯粹的文本比较。这意味着：**把 Momcozy 的规则库往「法规文本形式化」方向做，会和工具能力正面冲突**。更合适的路线是 DMN/决策表 + ODRL 式 constraint 建模（§5.5、§9.3），这两者对枚举/文本的建模能力更强。[判断]

### 3.6 Reforms：把「规则集」当成可以被整体替换的对象

**[原文]**：

> "Within OpenFisca these are known as reforms. A reform is a set of modifications to be applied to a reference tax and benefit system. It generates a reformed tax and benefit system that differs from the original one. Calculations can be run on both of them and the results compared."
>
> "**Differences between reforms and extensions**
> Reforms are sometimes confused with another mechanism: extensions. These two mechanisms do not have the same purpose:
> * Use a reform to modify a tax and benefit system in order to study the impact of a legislation change.
> * Use an extension to write formulas that are based on a main tax and benefit system, while keeping the code separated from the main country package (e.g. for local benefits)."
> — `https://openfisca.org/doc/key-concepts/reforms.html`

**[判断]** `reform` 这个概念对 Momcozy 的「规则库自迭代」是直接可用的：**每一次规则库调整 = 一个 reform 对象**（基线规则集 + 一组修改），可以对同一批历史内容跑「改革前 vs 改革后」，量化「这条新规则会把多少条历史内容从通过改判为不通过」。这就是规则库变更的影响评估（impact assessment），也是 R4 分片要的度量输入的天然来源。

### 3.7 测试：YAML 测试 + 与代码分离

**[原文]** OpenFisca 提供 `writing_yaml_tests.html`，测试用例写在 YAML 里而不是 Python 里。这里不逐字引用细节（见 [本地] `raw/of-yaml-tests.txt`），但设计取向与 Better Rules 的 `shared/example_beards.yml` 完全一致：**测试数据是非程序员可读、可编辑的独立文件**。[判断]

---

## 4. 法律规则标记语言

### 4.1 LegalRuleML（OASIS 标准）：deontic 算子的完整清单

规范：`LegalRuleML Core Specification Version 1.0`（OASIS Standard, 2021）
URL：`http://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.html`
[本地] `raw/legalruleml-core-spec.html`（774 KB）、`raw/legalruleml-core-spec.txt`（7,391 行）

#### 4.1.1 基本算子：OBL / PER / FOR

**[原文]**（§4.2.3.1 "Modal and Deontic Operators"）：

> "In the context of normative reasoning and representation of norms the focus is on the concepts of deontic necessity and deontic possibility. These two correspond to the notions of Obligation (see also the glossary) and Permission (see also the glossary). In addition, we consider the notion of Prohibition (see also the glossary), which corresponds to the operator of deontic impossibility. For something to be \"deontically necessary\" means that it holds in all situations deemed legal; similarly, something is \"deontically possible\" if there is at least one legal state where it holds. Finally, \"deontically impossible\" indicates that something does not hold in any legal state.
>
> We will use `[OBL]` for the modal/deontic operator of Obligation, `[PER]` for Permission, and `[FOR]` for Prohibition (or Forbidden)."

**[原文]** 标准 deontic logic 的三条关系（同节）：

> "Standard deontic logic assumes the following relationships between the operators:
>
> `[OBL]p equiv -[PER]-p`
> If p is obligatory, then its opposite, -p, is not permitted.
>
> `[FOR]p equiv [OBL]-p`
> If p is forbidden, then its opposite is Obligatory. Alternatively, a Prohibition can be understood as Obligation of the negation."

**[原文]** 一般形式的规则（同节）：

> "Accordingly, the following is an example of mathematical statement of a Prescriptive Rule (see also the glossary):
>
> `p_1, ..., p_n, [DEON_1]p_n+1, ..., [DEON_m]p_n+m => [DEON] q`
>
> The antecedent, `p_1, ..., p_n, [DEON_1]p_n+1, ..., [DEON_m]p_n+m`, conditions the applicability of the norm in the consequent `[DEON] q`; that is, when the antecedent conditions are met, then the consequent is the deontic effect of them. Thus, given the antecedent, the rule implies `[DEON] q`."

**[判断]** 注意这句话的措辞：**「antecedent ... conditions the applicability of the norm in the consequent」**——LegalRuleML 用的是「前件条件决定规范的适用性（applicability）」这个说法。也就是说，**适用性（applicability）在 deontic 体系里是一个独立于 deontic 算子的概念**：算子说「这条规则是义务/禁止/许可」，前件说「在什么条件下它才适用」。这直接支持「L1 与 L2 分离」的框架。[判断，基于 §4.1.1 原文]

#### 4.1.2 强弱之分：weak / strong permission，achievement / maintenance obligation

**[原文]**（同节）：

> "The operators of Obligation, Prohibition and Permission are typically considered the basic ones, but further refinements are possible, for example, two types of permissions have been discussed in the literature on deontic logic: **weak permission** (or negative permission) and **strong permission** (or positive permission). Weak permission corresponds to the idea that some A is permitted if -A is not provable as mandatory. In other words, something is allowed by a code only when it is not prohibited by that code [41]. The concept of strong permission is more complicated, as it amounts to the idea that some A is permitted by a code if and only if such a code explicitly states that A is permitted, typically as an exception to the prohibition of A or the obligation of its contrary, i.e., -A. It follows that a strong permission is not derived from the absence of a prohibition, but is explicitly formulated in a permissive (prescriptive) norm [1]."
>
> "Refinements of the concept of obligation have been proposed as well. For example it possible to distinguish between **achievement** and **maintenance** obligations, where an achievement obligation is an obligation that is fulfilled if what the obligation prescribes holds at least once in the period when the obligation holds, while a maintenance obligation must be obeyed for all the instants when it holds"

**[原文]** LegalRuleML 对「子类语义」保持中立，用两个机制挂钩外部语义（同节）：

> "LegalRuleML is neutral about the different subclasses of the deontic operators; to this end, LegalRuleML is equipped with two mechanisms to point to the semantics of various Deontic Specifications (see also the glossary) in a document. The first mechanism is provided by the `iri` attribute of a Deontic Specification"

```xml
<lrml:Obligation
    key="oblig1"
    iri="ex:achievementObligation">
    ...
</lrml:Obligation>
```

> "The second mechanism is to use an Association to link a Deontic Specification to its meaning using the `<lrml:applyModality>` element"

**[判断]** **「weak permission vs strong permission」是 Momcozy「安全词白名单」的理论定位**。他们的白名单规则族（`安全词`）目前是「命中即合规」，属于 strong permission（显式许可）。但他们的 **豁免词（exemption）**语义模糊：是「该检测器对本条内容不适用」（属于作用域）还是「虽然命中但显式许可」（属于 modality）？这两者在 LegalRuleML 里是不同的东西。**建议把豁免词归入作用域/前件条件，而不是归入许可。** [判断]

#### 4.1.3 有向算子与 Bearer：规则必须说清「对谁」

**[原文]**（同节）：

> "Furthermore, Obligations, Prohibitions and Permissions in LegalRuleML are **directed operators** [28], thus they have parties (e.g. **Bearer** — see also the glossary), specifying, for example, who is the subject of an Obligation or who is the beneficiary of a Permission."

```xml
<lrml:Obligation iri="ex:obl1">
  <ruleml:slot>
    <lrml:Bearer iri="ex:oblBearer"/>
    <ruleml:Ind>Y</ruleml:Ind>
  </ruleml:slot>
  <ruleml:Atom key="ex:atom2">
    <ruleml:Rel iri="ex:rel2"/>
    <ruleml:Ind>X</ruleml:Ind>
  </ruleml:Atom>
</lrml:Obligation>
```

**[原文]** 术语表对 Bearer 与 AuxiliaryParty 的定义（§3.4 Node Elements）：

> "**Bearer** +: a role in a Deontic Specification to which the Deontic Specification is primarily directed."
> "**AuxiliaryParty** +: a role in a Deontic Specification to which the Deontic Specification is related."
> "**Authority(ies)** +: a person or organization with the power to create, endorse, or enforce Legal Norms."
> "**Jurisdiction(s)** +: a geographic area or subject-matter over which an Authority applies its legal power."

#### 4.1.4 违背、罚则与「次级义务」：SuborderList

**[原文]**（§4.2.3.2 "Violation, Suborder, Penalty and Reparation"）：

> "Obligations can be violated; according to some legal scholars, the possibility of being violated can be used to define an obligation. A violation means that the content of the obligation has not been met. It is important to notice that a violation does not result in an inconsistency. A violation is, basically, a situation where we have
>
> `([OBL]p) and -p`"

> "One of the characteristics of norms is that having violated them, a penalty can be introduced to compensate for the violation, where a penalty is understood to also be a deontic formula. To model this feature of norms and legal reasoning, Governatori and Rotolo [25] introduced what is called here a **suborder list**"

**[原文]** 术语表定义（§3.4）：

> "**SuborderList**: A Deontic Specification consisting of a sequence of Deontic Specifications other than SuborderLists (at any depth). When a SuborderList holds, a Deontic Specification in the SuborderList holds if all Deontic Specifications that precede it in the SuborderList have been violated."
> "**PenaltyStatement** +: a Legal Statement of a sanction (e.g. a punishment or a correction)."
> "**Reparation** +: an indication that a PenaltyStatement is linked with a PrescriptiveStatement. It indicates that a sanction may apply where the PrescriptiveStatement entails a Deontic Specification and when there is a Violation of the Deontic Specification."
> "**Compliance** +: an indication that an Obligation has been fulfilled or a Prohibition has not been violated."
> "**Violation** +: an indication that an Obligation or Prohibition has been violated."

**[判断]** SuborderList 是「阶梯式救济」的标准模型：**要求 A 做 X；若不满足，则要求 A 做 Y；若再不满足，则罚 Z**。这正是内容审核里「自动判 REJECT → 转人工 → 升级处置」链条的形式化。Momcozy 目前的 `风险等级` 是**静态四档**，与结论一对一并列，没有表达「条件不满足时降级到下一档」的机制。这是一个可补强的方向。[判断]

#### 4.1.5 强度（Strength）与推翻（Override）：冲突消解的形式化

**[原文]** 术语表（§3.4）：

> "**DefeasibleStrength** +: an indication that, in the absence of information to the contrary and where the antecedent of a Legal Rule holds, the conclusion of the Legal Rule holds."
> "**StrictStrength** +: an indication that where the antecedent of a Legal Rule is indisputable, the conclusion of the Legal Rule is indisputable."
> "**Defeater** +: an indication that, in the absence of information to the contrary and where the antecedent of a Legal Rule holds, the opposite of the conclusion of the Legal Rule does not hold."
> "**Strength**: the quality of a Legal Rule to resist or not to resist a rebuttal."
> "**Override** +: an indication that a Legal Rule takes precedence over another Legal Rule. The ordered pair of Legal Rules is an instance in a defeasible priority relation."
> "**OverrideStatement** +: a Legal Statement of an Override."

**[原文]** §4.2.1 Defeasibility 给出了**三种冲突消解方法的完整分类与法律原则的映射**（这是全规范里最直接回答「冲突怎么办」的一段）：

> "It is possible to have conflicting rules, i.e., rules with opposite or contradictory heads, for example
>
> `body1 => head`
> `body2 => -head`
>
> Systems for defeasible reasoning include mechanisms to solve such conflicts. Different methods to solve conflicts have been proposed: **specificity**, **salience**, and **preference relation**. According to specificity, in case of a conflict between two rules, the most specific rule prevails over the less specific one, where a rule is more specific if its body subsumes the body of the other rule. For salience, each rule has an attached salience or weight, where in case of a conflict between two rules, the one with the greatest salience or weight prevails over the other. Finally, a preference relation (also known as superiority relation) defines a binary relation over rules, where an element of the relation states the relative strength between two rules. Thus, in case of a conflict between two rules, if the preference relation is defined order such rules, the strongest of the two rules wins over the other.
>
> Various researchers have taken different views on such methods. **Specificity corresponds to the well know legal principle of lex specialis.** Prakken and Sartor [34] argue that specificity is not always appropriate for legal reasoning and that there are other well understood legal principles such as **lex superior** and **lex posterior** apply instead. Prakken and Sartor [34] cite cases in which the lex specialis principle might not be the one used to solve the conflict, for example, a more specific article from a local council regulation might not override a less specific constitutional norm."

**[原文]** Override 的 XML 形式（同节）：

```xml
<lrml:OverrideStatement>
  <lrml:Override over="#cs2" under="#cs1"/>
</lrml:OverrideStatement>
```

> "For the representation of the strength of rules, LegalRuleML offers two options. The first is to include it in a `<lrml:Context>` block, where a `<lrml:Context>` specifies a context in which the rule is applied."
> "The second (and optional) way to express the qualification of the rule is directly inside of the rule with an `<lrml:hasStrength>` block. The difference is that `<lrml:Context>` localizes the strength of a rule, while the `<lrml:hasStrength>` block in effect relates the strength to the rule in all contexts."

**[判断]** 这段解决了「优先级应该写在哪里」的问题，答案很精妙：**同一个强度可以有两种作用域**——`Context` 里的强度只在该上下文中生效（例如「在这条平台政策下，平台规则压过品牌规则」），规则内的强度在所有上下文中生效（「红线永远是红线」）。Momcozy 只有一档全局优先级（`风险等级`），无法表达「在美国站，法规规则优先；在德国站，平台规则优先」这种情形。[判断]

### 4.2 LegalRuleML 的作用域元数据：五类，全部通过 Association 挂接

这是本分片最重要的证据之一。LegalRuleML **没有**把辖区、机关、时间写进规则体，而是设计了**独立的元数据概念 + 一个关联机制**。

#### 4.2.1 目录结构证明确实是分开的

§4 的目录（[本地] `raw/legalruleml-core-spec.txt` 第 270–299 行）：

```
4.2 Modeling Legal Norms
    4.2.1 Defeasibility
    4.2.2 Constitutive and Prescriptive Norms
    4.2.3 Deontic
        4.2.3.1 Modal and Deontic Operators
        4.2.3.2 Violation, Suborder, Penalty and Reparation
    4.2.4 Alternatives
4.3 Metadata of the LegalRuleML Specifications
    4.3.1 Sources and Isomorphism
    4.3.2 Agent, Figure, Role
    4.3.3 Jurisdiction
    4.3.4 Authority
    4.3.5 Time and Events
```

**「规则本体」在 4.2，「元数据」在 4.3。** 两个独立章节。

#### 4.2.2 关联机制：Context + Association

**[原文]** §3.4 / §3.6 的边元素（edge elements）：

> "**Context** +: an application of Associations to their target entities within a Scope."
> "`applies<Node>`: a `<Node>` applied by the Context or Association (e.g. appliesAuthority — an Authority applied by the Context or Association)."
> "`appliesAuthority`: an Authority applied by the Context or Association."
> "`appliesJurisdiction`: a Jurisdiction applied by the Context or Association."
> "`appliesStrength`: a Strength applied by the Context or Association."
> "`appliesTemporalCharacteristics`: a collection of TemporalCharacteristics applied by the Context or Association."
> "`appliesTemporalCharacteristic`: a TemporalCharacteristic applied by the Context or Association."
> "`appliesModality`: the deontic mode that applies to a Deontic Specification in a Context or Association."
> "`appliesSource`: a LegalSource or Reference applied by the Context or Association."

**[判断]** 这张表就是「作用域与规则本体分离」的标准答案的**枚举形式**：Authority（谁定的）、Jurisdiction（在哪个辖区/主题域有效）、TemporalCharacteristic（何时有效）、Strength（多强）、Source（依据哪条原文）、Modality（义务/禁止/许可）——**六种作用域维度，全部是 `applies*` 边，全部通过 Context/Association 挂到规则上**，而不是规则上的列。[判断]

#### 4.2.3 Sources and Isomorphism：`依据来源` 该怎么建模

**[原文]**（§4.3.1，逐字）：

> "For legal rule modeling, it is important for several reasons to maintain the connection between the formal norms and the legally binding textual statements that express the norms. Legal knowledge engineers and end users should know and be able to track the textual source of the formal representation. Furthermore, because the legal text is the only legally binding element, the connection between text and the rule(s) (or fragment of rule) guarantees the provenance, authoritativeness, and authenticity of the rules modelled by the legal knowledge engineer. In addition, legal experts (judges, lawyers, legal operators) request a mechanism to connect text and rules for legibility and validation of the rules. Finally, because the legal sources of rules change over time, the formal rules need to be updated according to the textual changes; as there is usually no automatic mechanism to correlate and track modifications to rules, the connection between text and rules helps to do so. For these reasons LegalRuleML includes a mechanism for managing this connection, which is called **\"isomorphism\"** in the AI & Law community."

> "The mechanism must support a **fine granularity** (rules, fragments of rules, atoms, fragments of atoms connected with provisions, fragments of provisions, letters, numbers, paragraphs, sentences, and word) as well as represent temporal modifications."

> "LegalRuleML dedicates two elements (`<lrml:References>`, `<lrml:LegalSources>`) to annotate the original legal sources and to connect them to rules, so permitting an **N:M relationship** (e.g. many rules in relation to one textual provision; many textual provisions for one rule)."

**[原文]** 术语表定义：

> "**Isomorphism**: a relationship between a set of Legal Rules with a set of Legal Sources such that the origin of the Legal Rules is tied to the Legal Sources."
> "**LegalSource(s)** +: a source of one or more Legal Norms formulated in any format and endorsed by an Authority."
> "**Reference(s)** +: a pair consisting of an internal ID and an enriched non-IRI identifier, where the non-IRI is paired with some additional information that is sufficient to disambiguate the non-IRI to a unique LegalSource."

**[判断]** 这直接判定了 Momcozy 的 `依据来源` 字段的设计缺陷：它是一个**自由文本单值**（"W1卖点表达边界（品线反馈2026-09-10 T4）"），而标准要求的是 **N:M 关系 + 细粒度定位 + 命名约定声明**。标准里连命名约定本身都要声明（`refIDSystemName="AkomaNtoso3.0-2016-03"`），这样引用才可机器解析。[判断]

#### 4.2.4 Jurisdiction 与 Authority

**[原文]** §4.3.3 Jurisdiction 的术语表定义（§3.4）：

> "**Jurisdiction(s)** +: a geographic area or **subject-matter** over which an Authority applies its legal power."

**[判断]** 注意 "**or subject-matter**"。辖区不一定是地理的——**「母婴品类」本身可以是一个 jurisdiction（主题域）**。这个措辞给「品类 × 国家」的建模提供了标准依据：它们不是两个不同性质的维度，而是同一个维度（jurisdiction）的两种取值域。这一点在 §11.2 会用到。[判断]

**[原文]** §4.3.4 Authority 节与术语表：

> "**Authority(ies)** +: a person or organization with the power to create, endorse, or enforce Legal Norms."
> "`hasAuthority`: an Authority in the collection."
> "`hasJurisdiction`: a Jurisdiction in the collection."

#### 4.2.5 Time and Events：三条时间轴

**[原文]**（§4.3.5，逐字）：

> "Legal texts are often amended as a society or judicial system evolves. Norms and rules are valid in a particular interval of time and with respect to **three main legal axes**: when they come into force (**entry**), when they effect the intended or desired result (**efficacy**), and when they apply (**applicability**). In this section, we model the external temporal dimensions of the norms (e.g., when the norm is valid) and not the temporal dimensions of the complex events that are the content of the textual provision (e.g., when a person is to present a tax application). Therefore, we only model the intervals and temporal parameters that define the period of validity of the rules. Moreover, in keeping with the sources, it is important to link the temporal parameters to **any part of a rule** (e.g. atom, rel, ind, if, then, etc.) with a **very fine granularity**."

**[原文]** 时间特征的结构（逐字）：

```xml
<lrml:TemporalCharacteristics key="tblock1">
  <lrml:TemporalCharacteristic key="nev1">
    <lrml:forStatus iri="http://docs.oasis-open.org/legalruleml/ns/v1.0/vocab#Efficacious"/>
    <lrml:hasStatusDevelopment iri="http://docs.oasis-open.org/legalruleml/ns/v1.0/vocab#Starts"/>
    <lrml:atTime keyref="#t1"/>
  </lrml:TemporalCharacteristic>
  <lrml:TemporalCharacteristic key="nev2">
    <lrml:forStatus iri="http://docs.oasis-open.org/legalruleml/ns/v1.0/vocab#InForce"/>
    <lrml:hasStatusDevelopment iri="http://docs.oasis-open.org/legalruleml/ns/v1.0/vocab#Starts"/>
    <lrml:atTime keyref="#t2"/>
  </lrml:TemporalCharacteristic>
</lrml:TemporalCharacteristics>
```

**[原文]** 术语表：

> "**Legal Status**: a standing that can apply to a Legal Norm at a Time, e.g., \"is applicable\", \"is in force\", \"has efficacy\", \"is valid\". **Status Development**: a kind of event (e.g., start, end) that changes the Legal Status of a Legal Norm, e.g. making a Legal Norm come into force."
> "**TemporalCharacteristic(s)** +: a pair of Time with a qualification, which consists of a Legal Status and a Status Development, such that the qualification holds at the Time."

**[判断]** LegalRuleML 把时间建模为 **(时刻, 法律状态, 状态变化事件)** 三元组，而不是简单的 `生效日 / 失效日` 两个日期列。原因是状态是**多值的**：一条规则可以「已经公布（entry）但尚未适用（not applicable）」，或「已生效但已被中止（suspended）」。Momcozy 的 `启用状态` 是二值的（启用/停用），无法表达这种中间状态。[判断]

### 4.3 Akoma Ntoso（OASIS 法律文档标准）：层级与标识

规范：`Akoma Ntoso Version 1.0. Part 1: XML Vocabulary`（OASIS Standard）
URL：`http://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part1-vocabulary/akn-core-v1.0-os-part1-vocabulary.html`
[本地] `raw/akn-core-part1-vocab.html`（808 KB）、`raw/akn-core-part1-vocab.txt`（9,561 行）

#### 4.3.1 FRBR 四层：这是「规则编号稳定性」的核心答案

**[原文]**（§4.1.3 FRBR，逐字）：

> "The most important concepts of the Akoma Ntoso informal ontology are related to documents that have legal status. All discourse and all description of legal sources can be characterized as referring to one of the four levels of a document as introduced by IFLA FRBR (International Federation of Library Associations (IFLA) - Functional Requirements for Bibliographic Records (FRBR) http://www.ifla.org/VII/s13/frbr/frbr.pdf):
>
> * **WORK**: the abstract concept of the legal resource (e.g., act 3 of 2005).
> * **EXPRESSION**: any version of the WORK whose content is specified and different from others for any reason: language, versions, etc. (e.g., act 3 of 2005 as in the version following the amendments entered into force on July 3rd, 2006).
> * **MANIFESTATION** - any electronic or physical format of the EXPRESSION: MS Word, Open Office, XML, TIFF, PDF, etc (e.g., PDF representation of act 3 of 2005 as in the version following the amendments entered into force on July 3rd, 2006).
> * **ITEM**: the physical copy of any manifestation in the form of a file stored somewhere in some computer on the net or disconnected (e.g., the file called act32005.pdf on my computer containing a PDF representation of act 3, 2005)."

**[判断]** 把这个四层结构套到 Momcozy 的规则库上，会立刻暴露一个结构缺陷：

| FRBR 层 | Akoma Ntoso | Momcozy 对应物（现状） | Momcozy 应有对应物 |
|---|---|---|---|
| WORK | act 3 of 2005 | —（不存在） | 「W1 功效宣称不得越界」这条**抽象规则** |
| EXPRESSION | 某次修订后的版本 | —（不存在） | 该规则在规则集 v3 里的具体表述 |
| MANIFESTATION | PDF/XML | 飞书多维表格的一行 | 表格行 / YAML / JSON 实例 |
| ITEM | 本地文件 | 某次导出的 xlsx | 审查记录引用的规则快照 |

**现状是：MANIFESTATION 与 WORK 被合并了。** 表格里的「规则编号 H01」同时承担了 work 标识与 expression 标识两种职责。一旦 H01 的表述被修改，历史审查记录就无法回答「当时 H01 说的是什么」。[判断]

#### 4.3.2 eId / wId / GUID：三种标识的分工

**[原文]**（术语与用法散见全文；下列引文逐字）：

> "history concerning the original wId and the current eId."（[本地] 第 4113 行）
> "the modifications of the original wId over time. `<mappings>` supplies a ... expression of the document, i.e., whenever eIds and wIds diverge. The attribute `@original` stores the first wId, that never evolves, `@current` stores the ..."（第 4836–4840 行）

**[原文]** Conformance Level 2（[本地] 第 9010–9025 行，逐字）：

> "an XML source is compliant with the Akoma Ntoso specifications in level 2 if it is compliant at level 1 and if
> 1. The values of the **eId and wId attributes follows the Akoma Ntoso naming convention** as formulated in chapters 4 and 5 of this document;
> 2. The values of the **FRBRuri and FBRRthis** elements follows the specification detailed in chapter 4 of the Akoma Ntoso Naming Convention Version 1.0 ...
> 3. The values of the **href and src** attributes in ALL elements (except `<a>`) follows the specifications detailed in chapter 4 and 5 of the Akoma Ntoso Naming Convention Version 1.0 ..."

**[原文]** 命名约定的三条原则（§5.9.1 Identification，逐字）：

> "The scope of the naming convention is to identify in a unique way all Akoma Ntoso concepts and resources on the network and in general all collections thereof. Some principles and characteristics should be respected in the naming convention:
>
> * **MEANINGFULNESS**: the name is a meaningful and logical description of the resource and not of its physical path
> * **PERMANENCE**: the name must be permanent and stable over time
> * **INVARIANCE**: the name must derive from invariant properties of the resource so as to provide some degree of certainty in obtaining the same name for the same resource regardless of process, tool and person."

**[原文]** FRBR 各层的 URI 使用规则（同节，逐字）：

> "1. Legislative references will most probably refer to **WORKs**: acts referring to other acts do so regardless of the actual version, and references must be to something independent of all possible expressions, e.g., to the work.
> 2. The list of attachments and schedules belong to a specific EXPRESSION, so references to ExpressionComponents is specific of the expression level."

**[判断]** **这三条原则 + 引用的 WORK/EXPRESSION 分工，是「规则编号如何既稳定又可读」的标准答案**：

- **引用一律指向 WORK**（`H01`），因为引用方（一条审查记录、另一条规则）不关心版本。
- **快照与审计一律记录 EXPRESSION**（`H01@2026-09-15T12:00Z` 或 `H01#rev7`）。
- **`GUID` 承担「永不复用且无语义」的职责**。Akoma Ntoso 里 `GUID` 与 `eId` 并存（[本地] 第 8539 行：`<section GUID="idd1d2d52a-f639-11e2-8470-abc29ba29c4d" eId="sec_302">`）——**同一元素同时有 UUID 和可读 ID**。这是双 ID 设计的直接证据。

#### 4.3.3 层级（hierarchy）与自定义容器 `hcontainer`

**[原文]**（§4.1.5.1，逐字）：

> "**The hierarchy**: a hierarchy is a set of sections nested to an arbitrary depth, usually provided with title and numbering. Each level of the nesting can contain either more nested sections or a container. No text is allowed directly inside the hierarchy, but only within a block element that is contained within a container element (not considering, of course, titles and numbering). Akoma Ntoso uses **only one hierarchy**, with predefined names and no constraints on their order or systematic layering."

**[原文]** 通用层级容器（[本地] 第 1843 行、第 2160 行，逐字）：

> "for such use cases a generic container called an **hcontainer** (i.e. hierarchical container) is provided which can be identified with a name and supports the same hierarchical structures provided by the named parts."
> "The hcontainer element is a generic element for a hierarchical container. It can be placed in a hierarchy instead of any of the other hierarchical containers. The attribute **name is required** and gives a name to the element."

**[判断]** 这一段对 Momcozy 的四维问题是**结构性启示**：Akoma Ntoso 有一组**预定义的具名层级**（part / chapter / section / article / paragraph / point …）**外加一个任意命名的通用容器 `hcontainer`**。也就是：**既能用标准层级，也能定义自己的层级，且两者可混用**。

正确的做法不是「四个维度做笛卡尔积」，而是：**用 `hcontainer` 式的自定义层级，定义一条作用域继承链**（例如 `国家 → 平台 → 品类 → 内容类型`），规则挂到链上的**某一层**，命中时**沿链向下继承 + 最具体者优先（lex specialis）**。这样规则条数从「维度值乘积」降为「实际有差异的层数之和」。[判断，详见 §11.2]

### 4.4 LegalRuleML 与 Akoma Ntoso 的关系

**[原文]** LegalRuleML 规范中直接出现的 Akoma Ntoso 引用（[本地] `raw/legalruleml-core-spec.txt`）：

> 第 2394 行："naming convention 'AkomaNtoso2.0-2011-10' and an example."
> 第 2403 行：`refIDSystemName="AkomaNtoso3.0-2016-03"/>`
> 第 4167 行："for identifiers of Akoma Ntoso."
> 第 5463 行："for testing LegalRuleML jointly with Akoma Ntoso."

**[判断]** 两个标准的分工是**清晰的、不重叠的**：

| | Akoma Ntoso | LegalRuleML |
|---|---|---|
| 管什么 | **文本**的结构与标识（层级、引用、版本） | **规范**的逻辑与元数据（deontic 算子、强度、冲突） |
| 核心机制 | FRBR 四层 + `eId`/`wId` + `hierarchy` | deontic operator + `hasStrength` + `Override` + `applies*` |
| 稳定性职责 | 保证「同一段文本的 ID 永不变」 | 保证「规则与文本的 N:M 连接可追溯」 |

**对 Momcozy 的合并启示**：他们缺的正是这两件事的**分工**。`规则编号` 目前被迫同时承担 Akoma Ntoso 的职责（文本/条目定位）和 LegalRuleML 的职责（规则逻辑标识）。建议拆成 `rule_id`（WORK，稳定）+ `revision_id`（EXPRESSION，可变）+ `source_ref`（指向法规/政策原文的细粒度定位）。

### 4.5 LKIF 与其他

- **LKIF（Legal Knowledge Interchange Format）**：**本次未取得一手规范文档**。LKIF 是 EU ESTRELLA 项目（2004–2008）的成果，规范以项目 deliverable PDF 形式发布，我尝试的路径均不可达（见附录 B）。本文**不对 LKIF 的具体元素做任何断言**。
- **[判断]** 从二手转述可知 LKIF 与 LegalRuleML 有承继关系（LegalRuleML 的参考文献中引用了 LKIF 相关工作），但**我没有一手证据，故不作为论断**。

---

## 5. 规则引擎与策略引擎的规则建模

### 5.1 OPA / Rego（Open Policy Agent）

文档：`https://www.openpolicyagent.org/docs/latest/policy-language/`、`https://www.openpolicyagent.org/docs/latest/policy-reference/`、`https://www.openpolicyagent.org/docs/latest/style-guide/`、`https://www.openpolicyagent.org/docs/latest/policy-testing/`
[本地] `raw/opa-policy-language.txt`（4,537 行）、`raw/opa-docs-policy-ref.txt`、`raw/opa-style-guide.txt`、`raw/opa-policy-testing.txt`、`raw/opa-philosophy.txt`

#### 5.1.1 文档结构：package / rule / document

Rego 的组织单位是 `package`（命名空间）→ `rule`（规则）→ 合并成 `document`（虚拟文档）。规则分两类：

- **complete definition**（完整定义）：规则头没有 key，一个 document 只能有一个值。
- **partial definition**（部分定义）：规则头有 key，累积成 set 或 object。

**[原文]**（Policy Reference，Complete Definitions 节）：

> "In addition to rules that partially define sets and objects, Rego also supports so-called **complete definitions** of any type of document. Rules provide a complete definition by omitting the key in the head. Complete definitions are commonly used for constants:"
>
> "Documents produced by rules with complete definitions can only have one value at a time. If evaluation produces multiple values for the same document, **an error will be returned**."

**[判断]** 这是一条很强的约束：**「完整定义」的规则集一旦出现两个互相矛盾的结论，不是「后者覆盖前者」，而是直接报错。** 这与 Momcozy 关心的「两条规则对同一输入给出相反结论」直接对应——OPA 的选择是**让冲突爆炸**，而不是静默选择。

`partial set rule` 是「多条规则各自追加一条违规」的标准形式：

```rego
deny contains "User is anonymous" if input.user_id == "anonymous"
```

#### 5.1.2 `default`：兜底必须显式写出

**[原文]**（Policy Language → "Default Keyword" 节，逐字。注：OPA 的 "Policy Reference" 页把 Policy Language 全文一并呈现，该段落在两处均可查到；本文以 Policy Language 页为准）：

> "The `default` keyword allows policies to define a default value for documents produced by rules with complete definitions. **The default value is used when all the rules sharing the same name are undefined.**
>
> For example:
>
> ```rego
> package example
>
> default allow := false
>
> allow if {
>     input.user == "bob"
>     input.method == "GET"
> }
> ```
>
> **Without the default definition, the `allow` document would be undefined for the same input.**
>
> When the `default` keyword is used, the rule syntax is restricted to:
>
> `default <name> := <term>`
>
> The term may be any scalar, composite, or comprehension value but it may not be a variable or reference. If the value is a composite then it may not contain variables or references. Comprehensions however may, as the result of a comprehension is never undefined."

**[判断]** 关键在最后加粗那句：**不写 `default`，结论不是 `false`，而是 `undefined`。** 这是一个**第三态**。这个设计是刻意的——它让「没有规则命中」与「规则命中且结论为假」在语义上可区分。Cedar 和 DMN 用不同方式表达了同一件事（§5.2、§5.5）。

#### 5.1.3 反面教材：`deny` 式反向规则会 fail-open

**[原文]**（Style Guide，"Use negation to handle undefined" 节，逐字。这是 OPA 官方文档里最直接的一段安全警告）：

> "When encountering undefined references inside of rules, evaluation of the rule halts and the rule itself evaluates to undefined, unless of course, a default value has been provided. While saying `allow` is undefined or `allow` is false if encountering undefined in a rule is likely desirable, this doesn't hold true when working with \"inverted\" rules — i.e. rules like `deny` (as opposed to `allow`). Saying `deny` is undefined or `deny` is false if undefined is encountered, essentially means that **any occurrence of undefined (such as when attributes are missing in the input document) would lead to the deny rule not getting enforced.** This is particularly common writing partial rules (i.e. rules that build sets or objects).
>
> Consider for example this simple rule:
>
> **Avoid**
> ```rego
> authorized := count(deny) == 0
>
> deny contains "User is anonymous" if input.user_id == "anonymous"
> ```
>
> At first glance, it might seem obvious that evaluating the rule should add a violation to the set of messages if the `user_id` provided in input is equal to \"anonymous\". But what happens if there is no `user_id` provided at all? Evaluation will stop when encountering undefined, and the comparison will never be invoked, leading to nothing being added to the deny set — **the rule allows someone without a `user_id`**. One option is to add another rule, checking only for its presence:
>
> ```rego
> deny contains "User ID missing from input" if not input.user_id
> ```
>
> This provides an even more granular message returned to the caller, but quickly becomes tedious when working with a large set of input data. To deal with this, a helper rule using negation may be used.
>
> **Prefer**
> ```rego
> authorized := count(deny) == 0
>
> deny contains "User is anonymous" if not authenticated_user
>
> authenticated_user if input.user_id != "anonymous"
> ```
>
> In the above case, the `authenticated_user` rule will fail both in the undefined case, and if defined but equal to \"anonymous\". Since the result of the helper rule is negated in the `deny` rule, both cases are covered."

**[判断]** 这段与 `research/distill/cross-cutting-findings.md` 里的反模式「**兜底路径比主路径更宽松**」是同一个现象在工业界的官方命名版。OPA 给的解法非常具体：**反向规则（deny/禁止类）必须显式覆盖「输入缺失」这一情形，否则就是 fail-open。** 对 Momcozy：他们的 H 类红线规则如果依赖 `检测关键词` 命中，那么**输入里没有关键词 ≠ 内容合规**——必须有一条显式的「未检出/无法判定」兜底，指向人工复核而不是通过。[判断]

#### 5.1.4 测试：`opa test` + 命名约定

**[原文]**（Policy Testing 节，逐字）：

> "OPA gives you a high-level declarative language (Rego) to author fine-grained policies that codify important requirements in your system. To help you verify the correctness of your policies, OPA also gives you a framework that you can use to write tests for your policies. By writing tests for your policies you can speed up the development process of new rules and reduce the amount of time it takes to modify rules as requirements evolve."

> "To test this policy, create a separate Rego file that contains test cases."
> "To exercise the policy, run the `opa test` command in the directory containing the files."
> "`$ opa test . -v`"

**[判断]** 三个可抄的约定：①**测试文件与策略文件分离**（`example.rego` vs `example_test.rego`）；②**测试函数命名前缀 `test_`**，一行一条断言，`PASS/FAIL` 逐条列出；③测试用例**既要覆盖正例也要覆盖反例**（官方示例里四个用例是两个 allow 两个 deny）。

#### 5.1.5 Rego 的 12 个「坑」清单（官方 Errors / 语义）

不逐条展开，但记录与规则工程相关的两条：

- **Existential quantification**："Variables in Rego are existentially quantified by default"（[本地] 第 1677 行）——即写 `some` 是默认行为，容易误读。
- **Undefined 传播**：见 5.1.3。

---

### 5.2 Cedar（AWS）

文档：`https://docs.cedarpolicy.com/auth/authorization.html`、`https://docs.cedarpolicy.com/policies/syntax-policy.html`
论文：Cutler et al., *Cedar: A New Language for Expressive, Fast, Safe, and Analyzable Authorization (Extended Version)*, arXiv:2403.04651（OOPSLA 2024）
[本地] `raw/cedar-authorization.txt`、`raw/cedar-syntax-policy.txt`、`raw/cedar-oopsla.pdftxt`

#### 5.2.1 策略结构：effect / scope / conditions / annotations

**[原文]**（Syntax → Basic policy construction，逐字）：

> "A policy is a text document that includes the following elements:
>
> * **Effect** – The effect specifies the intent of the policy, to either `permit` or `forbid` any request that matches the scope and conditions specified in the policy.
> * **Scope** – The scope specifies the combination of principals, actions, and resources to which the policy applies. **Inclusion of these elements is mandatory.** A policy that has only a scope without additional conditions can be part of a role-based access control strategy.
> * **Conditions** – (Optional) You can optionally provide additional conditions. These conditions must be satisfied for the policy to affect the evaluation of the authorization request. These conditions are expressed as `when` and `unless` clauses. ...
> * **Annotations** – (Optional) An annotation is an arbitrary key-value pair that can be used by other services that read and process Cedar policies. **An annotation has no impact on policy evaluation.**"

**[原文]** 匹配判定（同节）：

> "When the request exactly matches the scope, all of the `when` clauses evaluate to true, and all of the `unless` clauses evaluate to false, then that policy evaluates to true."

**[原文]** Scope 三要素（同节）：

> "A request always includes information that Cedar uses to answer the following three questions:
> * **Principal** – Who is making the request?
> * **Action** – What operation does the principal want to perform?
> * **Resource** – What does the principal want to perform the action on?
>
> The scope section of a Cedar policy statement defines which values match the request."

**[判断]** Cedar 的 `scope` 是**强制必填**的，`conditions` 是可选的。这是一个明确的架构判断：**「这条规则管哪些情形」是规则的身份，不是它的可选属性。** 对照 Momcozy：他们的规则表里**没有作用域字段的位置**（`适用产品` 是唯一一个，且全部写死），这在 Cedar 的结构下等于**策略无法被定位**。[判断]

#### 5.2.2 决策算法与「禁止优先」的设计理由（本分片最重要的单条证据）

**[原文]**（Authorization 节，逐字）：

> "After evaluating each policy, the authorizer combines the results to make an authorization decision. It makes its decision by applying the following rules:
>
> 1. If any `forbid` policy evaluates to true, then the final result is `Deny`.
> 2. Else, if any `permit` policy evaluates to true, then the final result is `Allow`.
> 3. Otherwise (i.e., no policy is satisfied), the final result is `Deny`."

> "**Discussion**
> Cedar's authorization algorithm has three useful properties:
>
> * **default deny**: no request is authorized (decision `Allow`) unless there is a specific `permit` policy that grants it; by default, the decision is `Deny`.
> * **forbid overrides permit**: even if a `permit` policy is satisfied, any satisfied `forbid` policy overrides it, producing a `Deny` decision.
> * **skip on error**: if a policy's evaluation returns error, the policy does not factor into the authorization response; it is skipped."

**[原文]** **为什么选择「禁止优先」——设计理由原文（逐字，这是委托方最需要的一段）**：

> "**Why was Cedar's authorization algorithm designed to satisfy these properties?** The first two properties make Cedar policies easier to understand. Since `permit` policies are the only way access is granted, readers just have to understand what each policy says, not what it doesn't. Because `forbid` policies always deny access, readers can understand them independently of any `permit` policies created now or in the future; `forbid` policies effectively define permission **\"guardrails\"** that `permit` policies cannot cross.
>
> The reasoning for the skip-on-error property is more involved. An alternative authorization algorithm we considered would be to Deny a request when any policy evaluation exhibits an error. While this might sound good at first, **deny-on-error raises concerns of safety. An application that was working fine with 100 policies might suddenly start denying all requests if the 101st policy has an error. Skip-on-error avoids this dramatic failure mode**, and is more flexible: applications can always choose to look at the authorization response's diagnostics and take a different decision if an evaluated policy produces errors."

**[原文]** 论文版本（§2.4 Safety，逐字）：

> "Cedar has a design goal of creating a safe foundation for writing policies. One aspect of this goal is that **Cedar's authorizer denies by default**: If no permit policy exists that authorizes a request, the request will be denied. Another aspect is that **forbid policies always override permit policies** when making the final decision. For example, Policy4 expresses that no intern is allowed to create a new task list (Action::\"CreateList\"). With this policy, if aaron tries to create a list, his request will be approved by Policy0, but denied by Policy4, with the final decision that the request is denied. **This behavior allows forbid policies to act like guardrails that enforce universal non-access rules.** The third aspect of safety is that Cedar's authorizer is **deterministic**: It is guaranteed to terminate and always produce the same authorization decision for a given request, hierarchy, and set of policies. Because Cedar policies are free of side effects and general loops, **policy evaluation order doesn't matter.**"

**[原文]** 形式化验证（摘要，逐字）：

> "Cedar's design has been finely balanced to allow for a sound and complete logical encoding, which enables precise policy analysis, e.g., to ensure that when refactoring a set of policies, the authorized permissions do not change. We have modeled Cedar in the Lean programming language, and used Lean's proof assistant to prove important properties of Cedar's design."

**[判断]** 三条可以直接搬到 Momcozy 的设计原则：

1. **只有一种方式能让内容通过**（类似 `permit` 只有显式许可才放行）。任何「没命中红线就当合规」的默认路径都必须显式写出来。
2. **红线（`forbid`）独立可理解**：「读者不需要知道现在或将来有哪些许可规则，就能理解一条禁止规则的含义」。这对 Momcozy 意味着：**H 类红线不应该依赖 M/U 类规则的存在来解释自己**。目前 H/M/U 的三族划分是「严重度」划分，不是「modality」划分——这是一个结构性混淆。[判断]
3. **不是每个错误都要变成拒绝**（skip on error）。Cedar 明确论证了 deny-on-error 会导致「加第 101 条策略时全站拒绝」。对 Momcozy：**检测器异常不应等于判定为高危**，而应进入一个独立的「引擎异常」通道。

---

### 5.3 XACML 3.0（OASIS）：合并算法（combining algorithms）的完整清单

规范：`eXtensible Access Control Markup Language (XACML) Version 3.0`（OASIS Standard, 2013-01-17）
URL：`https://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-os-en.html`
[本地] `raw/xacml30-core.html`（1.24 MB）、`raw/xacml30-core.txt`（16,508 行）

#### 5.3.1 §2.3 Combining algorithms（逐字）

> "XACML defines a number of combining algorithms that can be identified by a `RuleCombiningAlgId` or `PolicyCombiningAlgId` attribute of the `<Policy>` or `<PolicySet>` elements, respectively. The **rule-combining algorithm** defines a procedure for arriving at an authorization decision given the individual results of evaluation of a set of rules. Similarly, the **policy-combining algorithm** defines a procedure for arriving at an authorization decision given the individual results of evaluation of a set of policies. Some examples of standard combining algorithms are (see Appendix C for a full list of standard combining algorithms):
>
> * Deny-overrides (Ordered and Unordered),
> * Permit-overrides (Ordered and Unordered),
> * First-applicable and
> * Only-one-applicable.
>
> In the case of the **Deny-overrides** algorithm, if a single `<Rule>` or `<Policy>` element is encountered that evaluates to \"Deny\", then, **regardless of the evaluation result of the other `<Rule>` or `<Policy>` elements in the applicable policy, the combined result is \"Deny\"**.
>
> Likewise, in the case of the **Permit-overrides** algorithm, if a single \"Permit\" result is encountered, then the combined result is \"Permit\".
>
> In the case of the **\"First-applicable\"** combining algorithm, the combined result is the same as the result of evaluating the first `<Rule>`, `<Policy>` or `<PolicySet>` element in the list of rules whose target and condition is applicable to the decision request.
>
> The **\"Only-one-applicable\"** policy-combining algorithm only applies to policies. The result of this combining algorithm ensures that one and only one policy or policy set is applicable by virtue of their targets. If no policy or policy set applies, then the result is \"NotApplicable\", but **if more than one policy or policy set is applicable, then the result is \"Indeterminate\"**. When exactly one policy or policy set is applicable, the result of the combining algorithm is the result of evaluating the single applicable policy or policy set.
>
> Policies and policy sets may take parameters that modify the behavior of the combining algorithms. However, none of the standard combining algorithms is affected by parameters.
>
> Users of this specification may, if necessary, **define their own combining algorithms**."

#### 5.3.2 Appendix C 的完整清单

[本地] `raw/xacml30-core.txt` 第 776–812 行与第 14489–15100 行：

| 编号 | 算法 | 备注 |
|---|---|---|
| C.1 | Extended Indeterminate values | 引入 `Indeterminate{D,P}` 等扩展态 |
| C.2 | Deny-overrides | |
| C.3 | Ordered-deny-overrides | |
| C.4 | Permit-overrides | |
| C.5 | Ordered-permit-overrides | |
| C.6 | **Deny-unless-permit** | 只有显式 permit 才放行，其余一律 deny |
| C.7 | **Permit-unless-deny** | 只有显式 deny 才拦截，其余一律 permit |
| C.8–C.13 | First-applicable、Only-one-applicable、Legacy 系列 | |

**[判断]** `Deny-unless-permit` 与 `Permit-unless-deny` 是一对**语义上等价于「兜底值」的合并算法**：前者等价于「默认拒绝」，后者等价于「默认放行」。XACML 把它们做成**可选项**而不是硬编码默认，这是一个明确的设计立场：**兜底方向必须由规则集作者显式选择。** Cedar 选择了 `Deny-unless-permit`（硬编码），ODRL 选择了「不选就作废」，DMN 选择了 `UNIQUE` 并**禁止重叠**。三种不同的默认，但**都必须显式**。[判断]

---

### 5.4 Drools / KIE：规则属性（优先级与生命周期）

文档：`https://docs.drools.org/latest/drools-docs/drools/language-reference/index.html`
[本地] `raw/drools-language-reference.txt`（Drools User Guide 8.44.0.Final）

**[原文]** Table 1. Rule attributes（逐字，摘录与本分片相关的 6 条）：

> | Attribute | Value |
> |---|---|
> | `salience` | "An integer defining the priority of the rule. **Rules with a higher salience value are given higher priority when ordered in the internalMatch queue.** Example: `salience 10`" |
> | `enabled` | "A Boolean value. When the option is selected, the rule is enabled. When the option is not selected, the rule is disabled. Example: `enabled true`" |
> | `date-effective` | "A string containing a date and time definition. **The rule can be activated only if the current date and time is after a `date-effective` attribute.** Example: `date-effective \"4-Sep-2018\"`" |
> | `date-expires` | "A string containing a date and time definition. **The rule cannot be activated if the current date and time is after the `date-expires` attribute.** Example: `date-expires \"4-Oct-2018\"`" |
> | `no-loop` | "A Boolean value. When the option is selected, the rule cannot be reactivated (looped) if a consequence of the rule re-triggers a previously met condition." |
> | `activation-group` | "A string identifying an internalMatch (or XOR) group to which you want to assign the rule. **In internalMatch groups, only one rule can be activated. The first rule to fire will cancel all pending internalMatches of all rules in the internalMatch group.** Example: `activation-group \"GroupName\"`" |

**[原文]** Table 3. Legacy rule attributes（逐字）：

> | Attribute | Value |
> |---|---|
> | `agenda-group` | "A string identifying an agenda group to which you want to assign the rule. **Agenda groups allow you to partition the agenda to provide more execution control over groups of rules. Only rules in an agenda group that has acquired a focus are able to be activated.** Example: `agenda-group \"GroupName\"`" |
> | `ruleflow-group` | "A string identifying a rule flow group. In rule flow groups, rules can fire only when the group is activated by the associated rule flow." |

**[判断]** Drools 提供的是**三个正交的控制轴**，这在所有体系里是最细的：

| 轴 | 属性 | 回答的问题 | 标准对应 |
|---|---|---|---|
| 优先级 | `salience` | 谁先算？ | LegalRuleML 的 `salience`；DMN 的 `P`（Priority） |
| 互斥 | `activation-group` | 同一个组里**只能出一条** | DMN 的 `U`（Unique）+ Cedar 的 veto |
| 分组聚焦 | `agenda-group` | 哪些规则**有资格参与本轮判定** | LegalRuleML 的 `Context`；ODRL 的 `Policy` 组合 |
| 时间 | `date-effective` / `date-expires` | 何时生效/失效 | LegalRuleML 的 `TemporalCharacteristic`；OpenFisca 的 `formula_YYYY` / `end` |
| 开关 | `enabled` | 临时停用 | Momcozy 的 `启用状态` |

**[判断]** **Momcozy 的 `启用状态` 只对应 Drools 五个轴里最弱的那个（`enabled`）。** 缺优先级、缺互斥、缺分组、缺时间。[判断]

---

### 5.5 DMN（Decision Model and Notation，OMG 标准）：决策表与 hit policy

规范：`Decision Model and Notation, Version 1.5`（OMG）
URL：`https://www.omg.org/spec/DMN/1.5/PDF`（15.0 MB PDF）
[本地] `raw/dmn-15.pdf`、`raw/dmn-15.pdftxt`、`raw/dmn-hitpolicy-excerpt.txt`

#### 5.5.1 决策表的结构

**[原文]**（§8.2 引言，逐字）：

> "The list of rules expresses the logic of the decision. For a given set of input values, the matching rule (or rules) indicate the resulting value for the output name. **If rules overlap, multiple rules can match, and a hit policy indicates how to handle the multiple matches.**
>
> If two input entries of the same input expression share no values, the entries (cells) are called **disjoint**. If there is an intersection, the entries are called **overlapping** (or even equal). '**Irrelevant**' ('-') overlaps with any input entry of the input expression.
>
> Two rules are **overlapping** if all corresponding input entries are overlapping. A specific configuration of input data may then match the two rules.
>
> Two rules are **disjoint** (non-overlapping) if at least one pair of corresponding input expressions is disjoint. No specific configuration of input data will match the two rules.
>
> If tables are allowed to contain overlapping rules, the table hit policy indicates how overlapping rules have to be handled and which is the resulting value(s) for the output name, **in order to avoid inconsistency**."

**[原文]** §8.2.8 Input entries（逐字）：

> "Rule input entries are unary tests (grammar rule 15).
>
> A dash symbol ('-') can be used to mean any input value, i.e., **the input is irrelevant for the containing rule**. ... Tables containing at least one '-' input entry are called **contracted** tables."

**[原文]** §8.2.11.1（逐字，Rule Annotation 的定义）：

> "Regardless of whether a single or multiple hit policy is used, some columns in a decision table may be designated as **rule annotations**. Rule Annotations contain text that is not returned as part of the expression results, and they are **ignored for purposes of the hit policy validations** described below. Although there is no standard mechanism to access the annotations of the matched rules in a decision table at execution time, implementations may use the annotations for **auditing, debugging, logging, documentation, analytics, consumption by down-stream systems**, or for other purposes."

**[判断]** Rule Annotation 是「说明性字段」的标准位置。Momcozy 的 `边界内容`、`触发原因`、`依据来源` 都属于**不参与判定、只供审计**的 annotation 类字段——DMN 明确把它们放在**输出列之外**，且强调它们**不参与 hit policy 校验**。这直接支持把这类字段从规则行里拆出去（§11.5）。[判断]

#### 5.5.2 hit policy 完整清单（官方定义，逐字）

**[原文]** §8.2.11（逐字）：

> "A decision table normally has several rules. **As a default, rules do not overlap.** If rules overlap, meaning that more than one rule may match a given set of input values, **the hit policy indicator is required** in order to recognize the table type and unambiguously understand the decision logic. The hit policy can be used to **check correctness at design-time**.
>
> The hit policy specifies what the result of the decision table is in cases of overlapping rules, i.e., when more than one rule matches the input data. For clarity, the hit policy is summarized using a single character in a particular decision table cell. ...
>
> The character is the initial letter of the defined hit policy (**U**nique, **A**ny, **P**riority, **F**irst, **C**ollect, **O**utput order or **R**ule order). Crosstab tables are always Unique and need no indicator.
>
> **The hit policy SHALL default to Unique**, in which case the hit indicator is optional. **Decision tables with the Unique hit policy SHALL NOT contain overlapping rules.**
>
> Tools may support only a nonempty subset of hit policies, but the table type SHALL be clear and therefore **the hit policy indication is mandatory**, except for the default unique tables. Unique tables SHALL always be supported."

**Single hit policies**（单命中，逐字）：

> "1. **Unique**: no overlap is possible, and all rules are disjoint. Only a single rule can be matched. This is the default.
> 2. **Any**: there may be overlap, but all the matching rules show equal output entries for each output (ignoring rule annotations), so any match can be used. **If the output entries are non-equal (ignoring rule annotations), the hit policy is incorrect, and the result is undefined.**
> 3. **Priority**: multiple rules can match, with different output entries. This policy returns the matching rule with the highest output priority. **Output priorities are specified in the ordered list of output values, in decreasing order of priority. Note that priorities are independent from rule sequence.**
> 4. **First**: multiple (overlapping) rules can match, with different output entries. The first hit by rule order is returned (and evaluation can halt). This is still a common usage because it resolves inconsistencies by forcing the first hit. However, **first hit tables are not considered good practice because they do not offer a clear overview of the decision logic.** It is important to distinguish this type of table from others because the meaning depends on the order of the rules. **The last rule is often the catch-remainder.** Because of this order, the table is hard to validate manually and therefore has to be used with care."

**Multiple hit policies**（多命中，逐字）：

> "5. **Output order**: returns all hits in decreasing output priority order. Output priorities are specified in the ordered list of output values in decreasing order of priority.
> 6. **Rule order**: returns all hits in rule order. Note: the meaning may depend on the sequence of the rules.
> 7. **Collect**: returns all hits in arbitrary order. An operator ('+', '<', '>', '#') can be added to apply a simple function to the outputs. If no operator is present, the result is the list of all the output entries. Collect operators are:
>    a) `+` (sum): the result of the decision table is the sum of all the outputs.
>    b) `<` (min): the result of the decision table is the smallest value of all the outputs.
>    c) `>` (max): the result of the decision table is the largest value of all the outputs.
>    d) `#` (count): the result of the decision table is the number of outputs."

**[原文]** 两条 Note（逐字）：

> "**Note 1** Crosstab tables are unique and complete by definition and therefore do not need a hit policy.
> **Note 2** The sequence of the rules in a decision table does not influence the meaning, **except in First tables (single hit) and Rule order tables (multiple hit)**. These tables should be used with care."

**[原文]** §8.2.12 Default output values（逐字）：

> "Tables may specify a default output. The default value is **underlined** in the list of output values."

#### 5.5.3 元模型：hit policy 是 DecisionTable 的必填属性

**[原文]** §8.3.1（逐字）：

> "An instance of `DecisionTable` has an associated `hitPolicy`, which SHALL be one of the enumerated `HitPolicy`: **UNIQUE, FIRST, PRIORITY, ANY, COLLECT, RULE ORDER, OUTPUT ORDER**. **The default value for the `hitPolicy` attribute is: UNIQUE.** ...
>
> If the `hitPolicy` associated with an instance of `DecisionTable` is **FIRST or RULE ORDER**, the rules that are associated with the `DecisionTable` **SHALL be ordered**. The ordering is represented by the explicit numbering of the rules ...
>
> If the `hitPolicy` associated with an instance of `DecisionTable` is **PRIORITY or OUTPUT ORDER**, the `outputValues` determine the result as specified in clause 8.2.11.
>
> If the `hitPolicy` that is associated with an instance of `DecisionTable` is **COLLECT**, the `DecisionTable` MAY have an associated `aggregation`, which is one of the enumerated `BuiltinAggregator`"

**[原文]** Table 32（逐字摘录）：

> | Attribute | Description |
> |---|---|
> | `input: InputClause` | "This attributes lists the instances of InputClause that compose this DecisionTable." |
> | `output: OutputClause` | "This attributes lists the instances of OutputClause that compose this DecisionTable." |
> | `annotation: RuleAnnotationClause` | "This attribute lists the instances of RuleAnnotationClause that compose this DecisionTable." |
> | `rule: DecisionRule` | "This attributes lists the instances of DecisionRule that compose this DecisionTable." |
> | `hitPolicy: HitPolicy` | "The hit policy that determines the semantics of this DecisionTable. Default is: UNIQUE." |
> | `aggregation: BuiltinAggregator` | "If present, this attribute specifies the aggregation function to be applied to the unordered set of values of the applicable rules to determine the value of this DecisionTable when the hitPolicy is COLLECT." |

**[判断]** DMN 对 Momcozy 的直接含义，见 §11.3 与 §11.6。核心是三条：

1. **「多条规则同时命中怎么办」是一个必须在规则集层面回答的问题**，而且答案是**七选一 + 三种聚合算子**，不是「就高不就低」这类口头约定。
2. **`Unique`（不允许重叠）是默认值**。也就是说，**如果你没有明确声明允许重叠，标准就假设你的规则集是互斥的**。Momcozy 的 21 条规则里 H/M/U 三族天然会重叠（同一条文案可能同时命中 H03 和 M05），但没有任何地方声明命中的合并策略。
3. **`First` 是标准明确不推荐的**（"not considered good practice ... hard to validate manually"）。Momcozy 如果按「规则编号顺序取第一条命中」实现，就落在这个不推荐档位上。

---

### 5.6 表达式层：CEL 与 JSON Logic

#### 5.6.1 CEL（Common Expression Language）

规范：`https://github.com/google/cel-spec`（`doc/langdef.md`、`doc/intro.md`）
[本地] `raw/cel-langdef.txt`、`raw/cel-intro.txt`

**[原文]** langdef §Overview（逐字，这是 CEL 被选作策略表达式语言的**设计理由**）：

> "In the taxonomy of programming languages, CEL is:
>
> * **memory-safe:** programs cannot access unrelated memory, such as out-of-bounds array indexes or use-after-free pointer dereferences;
> * **side-effect-free:** a CEL program only computes an output from its inputs;
> * **terminating:** CEL programs **cannot loop forever**;
> * **strongly-typed:** values have a well-defined type, and operators and functions check that their arguments have the expected types;
> * **dynamically-typed:** types are associated with values, not with variables or expressions, and type safety is enforced at runtime;
> * **gradually-typed:** an optional type-checking phase before runtime can detect and reject some programs which would violate type constraints."

**[原文]** intro（逐字，给出 CEL 的基本形态）：

> "CEL allows for simple computations to be defined on types like this one. For example, given an instance of the `Account` type assigned to the variable `account`:
>
> ```
> has(account.user_id) || has(account.gaia_id)  // true if either one is set
> size(account.emails) > 0                       // true if emails is non-empty
> matches(account.phone_number, "[0-9-]+")       // true if number matches regexp
> ```"

**[判断]** 三个对本项目有用的点：①**`terminating` 是明确的设计目标**——策略表达式不能有循环，因此可以静态分析、可以在请求路径上同步执行；②**`has()` 原语**——「字段是否存在」是一等公民，正好对应 §5.1.3 的 undefined 问题；③**`matches()` 内建正则**——Momcozy 的正则字段可以是一个 CEL 表达式的一部分，而不是一个孤立的字符串列。[判断]

**注意**：本次未能取得 Google 官方「为什么用 CEL 做 IAM Conditions」的设计文档（`cloud.google.com` 不可达）。CEL 的官方设计目标来自 `cel-spec` 本身，**不宣称有更权威的 Google 政策设计文档**。

#### 5.6.2 JSON Logic

文档：`https://jsonlogic.com/`
[本地] `raw/jsonlogic.html`

**[原文]** 首页标语（逐字）：

> "JsonLogic — **Build complex rules, serialize them as JSON, share them between front-end and back-end**"

**[判断]** JSON Logic 的定位是**可序列化的表达式树**，它解决的问题是：规则要能在前后端之间传输、能被存储、能被 diff。Better Rules 的 `example-rules-as-code` 里有一份 JSON Logic 实现（§2.6），说明这两条线索是交汇的。对 Momcozy：**如果规则要被多个系统（广告投放系统、内容审核系统、Listing 工具）共享，表达式必须可序列化**；正则字符串 + 关键词列表的组合恰好是可序列化的，这也解释了为什么他们现在的字段选择不算错——只是**位置放错了**。[判断]

---

## 6. 冲突消解：从古典法律解释原则到规则引擎的优先级设计

> 本节的法律史部分依赖独立证据搜集（见 `_evidence/R3/raw/conflict-*`），引擎部分为本分片自查。

### 6.1 三种冲突消解手段的形式化定义（LegalRuleML 原话）

已在 §4.1.5 逐字引用，这里只重述关键映射：

| 形式化手段 | 定义（LegalRuleML §4.2.1） | 对应的法律解释原则（LegalRuleML 原话） |
|---|---|---|
| **specificity** | "the most specific rule prevails over the less specific one, where a rule is more specific if its body subsumes the body of the other rule" | "Specificity corresponds to the well know legal principle of **lex specialis**." |
| **salience** | "each rule has an attached salience or weight, where in case of a conflict between two rules, the one with the greatest salience or weight prevails over the other" | （无直接映射，属工程手段） |
| **preference relation**（= superiority relation） | "defines a binary relation over rules, where an element of the relation states the relative strength between two rules" | 由作者用 `Override` 显式声明 |

**[原文]** LegalRuleML 对 specificity 的**限度**给了明确警告（逐字）：

> "Prakken and Sartor [34] argue that specificity is not always appropriate for legal reasoning and that there are other well understood legal principles such as **lex superior** and **lex posterior** apply instead. Prakken and Sartor [34] cite cases in which the lex specialis principle might not be the one used to solve the conflict, for example, a more specific article from a local council regulation might not override a less specific constitutional norm."

**[判断]** 这句话对 Momcozy 极其重要：**「平台规则比品牌规则更具体，所以平台规则优先」是一个 lex specialis 论证；但「国家法规比平台规则更上位，所以法规优先」是一个 lex superior 论证。二者会冲突。** 所以四维作用域**不能**简单地做成「越具体越优先」的一条规则，必须允许**逐维指定优先级方向**。[判断，详见 §11.2]

### 6.2 三条古典原则的一手出处

#### lex specialis derogat legi generali

**[原文]** 联合国国际法委员会（ILC）《Fragmentation of International Law》研究组结论，UN Doc **A/CN.4/L.702**（2006），结论 (5)：

> "**2. The maxim lex specialis derogat legi generali**
>
> **(5) General principle.** The maxim *lex specialis derogat legi generali* is a generally accepted technique of interpretation and conflict resolution in international law. It suggests that whenever two or more norms deal with the same subject matter, **priority should be given to the norm that is more specific**. The principle may be applicable in several contexts: between provisions within a single treaty, between provisions within two or more treaties, between a treaty and a non-treaty standard, as well as between two non-treaty standards. The source of the norm (whether treaty, custom or general principle of law) is not decisive for the determination of the more specific standard."
> — [本地] `raw/conflict-ilc-a_cn4_l702.txt` 第 438–452 行；URL `https://legal.un.org/ilc/documentation/english/a_cn4_l702.pdf`

**[原文]** 同结论 **(6) Contextual appreciation**（这一条是本分片引用它的主要理由）：

> "**(6) Contextual appreciation.** The relationship between the *lex specialis* maxim and other norms of interpretation or conflict solution **cannot be determined in a general way**. Which consideration should be predominant — i.e. whether it is the speciality or the time of emergence of the norm — **should be decided contextually**."

**[原文]** 同结论 **(7) Rationale of the principle**：

> "**(7) Rationale of the principle.** That special law has priority over general law is justified by the fact that such special law, being more concrete, often takes better account of the particular features of the context in which it is to be applied than any applicable general law. Its application may also often create a more equitable result and it may often better reflect the intent of the legal subjects."

**[原文]** 同结论 **(9) The effect of lex specialis on general law**（重要：特别法**不消灭**一般法）：

> "**(9) The effect of lex specialis on general law.** The application of the special law does not normally extinguish the relevant general law. That general law will remain valid and applicable and will, in accordance with the principle of harmonization under conclusion (4) above, continue to give direction for the interpretation and application of the relevant special law and will become fully applicable in situations not provided for by the latter."

**[原文]** 同结论 **(10) Particular types of general law**（**上位法不被特别法推翻**的出口）：

> "**(10) Particular types of general law.** Certain types of general law may not, however, be derogated from by special law. *Jus cogens* is expressly non-derogable as set out in conclusions (32), (33), (40) and (41), below. Moreover, there are other considerations that may provide a reason for concluding that a general law would prevail in which case the *lex specialis* presumption may not apply. These include the following:
> * Whether such prevalence may be inferred from the form or the nature of the general law or intent of the parties, wherever applicable;
> * Whether the application of the special law might frustrate the purpose of the general law;"

**[原文]** 同结论 **(4) The principle of harmonization**：

> "**(4) The principle of harmonization.** It is a generally accepted principle that when several norms bear on a single issue they should, to the extent possible, be interpreted so as to give rise to a single set of compatible obligations."

**[判断]** **结论 (4) 是本分片最想推荐给 Momcozy 的一条原则**：处理规则冲突的第一动作**不是**选一条赢，而是**先试图让它们不冲突**（改成兼容的表述）。只有在无法调和时才进入优先级判定。

#### lex posterior derogat legi priori

**[原文]** ILC A/CN.4/L.702 结论 **(24)**：

> "**5. Conflicts between successive norms**
>
> **(24) *Lex posterior derogat legi priori*.** According to article 30 VCLT, when all the parties to a treaty are also parties to an earlier treaty on the same subject, and the earlier treaty is not suspended or terminated, then it applies only to the extent its provisions are compatible with those of the later treaty. **This is an expression of the principle according to which \"later law supersedes earlier law\".**"

**[原文]** 同结论 **(25) Limits of the "*lex posterior*" principle**：

> "**(25) Limits of the *lex posterior* principle.** The applicability of the *lex posterior* principle is, however, **limited**. It cannot, for example, be automatically extended to the case where the parties to the subsequent treaty are not identical to the parties of the earlier treaty."

**[原文]** 同结论 **(26) The distinction between treaty provisions that belong to the same "regime" and provisions in different "regimes"**（对 Momcozy 有直接映射）：

> "**(26)** ... The *lex posterior* principle is at its strongest in regard to conflicting or overlapping provisions that are part of treaties that are **institutionally linked or otherwise intended to advance similar objectives (i.e. form part of the same regime)**. In case of conflicts or overlaps between treaties in **different regimes**, the question of which of them is later in time would **not necessarily express any presumption of priority** between them. Instead, States bound by the treaty obligations should try to implement them as far as possible with the view of **mutual accommodation** and in accordance with the principle of harmonization."

**[判断]** 「同一 regime 内 lex posterior 最强；跨 regime 则没有优先推定」——这正是 §11.2 需要的那条判据：**Google 广告政策的新旧两版属于同一 regime，适用 lex posterior；Google 政策与 EU 法规之间属于跨 regime，不能靠「谁更新」来定优先级。** [判断]

**[原文]** 条约法上的直接依据：**《维也纳条约法公约》1969，第 30 条**（逐字）：

> "**Article 30 — Application of successive treaties relating to the same subject matter**
>
> 1. Subject to Article 103 of the Charter of the United Nations, the rights and obligations of States Parties to successive treaties relating to the same subject matter shall be determined in accordance with the following paragraphs.
> 2. When a treaty specifies that it is subject to, or that it is not to be considered as incompatible with, an earlier or later treaty, the provisions of that other treaty prevail.
> 3. When all the parties to the earlier treaty are parties also to the later treaty but the earlier treaty is not terminated or suspended in operation under article 59, **the earlier treaty applies only to the extent that its provisions are compatible with those of the later treaty.**
> 4. When the parties to the later treaty do not include all the parties to the earlier one:
>    (a) as between States Parties to both treaties the same rule applies as in paragraph 3;
>    (b) as between a State party to both treaties and a State party to only one of the treaties, the treaty to which both States are parties governs their mutual rights and obligations."
> — [本地] `raw/conflict-vclt-1969.txt` 第 510–539 行；URL `https://legal.un.org/ilc/texts/instruments/english/conventions/1_1_1969.pdf`

#### lex superior derogat legi inferiori

**[原文]** 完整的拉丁法谚出现在**欧盟法院总法务官意见，Case C-449/21（Towercast）**，CELEX `62021CC0449`，第 30 点：

> "30. Moreover, it follows from the principle of the **hierarchy of norms** and the principle ***lex superior derogat legi inferiori*** deriving therefrom, that **a provision of secondary law is not capable of restricting the scope or direct applicability of a provision of primary law**, but rather must comply with its requirements and must in turn be interpreted restrictively in the light of them, where necessary."
> — [本地] `raw/conflict-eu-ag-opinion-C449-21-towercast.txt`；URL `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62021CC0449`

**[原文]** 同案第 59 点也用到 lex specialis：

> "In my view, therefore, there remains room for the application of the principle *lex specialis derogat legi generali*, notwithstanding the fact that Article 102 TFEU has ..."

**[原文]** 补充佐证（反向使用，证明该原则是 EU 法实践中的公认分析范畴）：
- AG Opinion, Case **C-582/08**，第 57–58 点："The Sixth and Thirteenth VAT Directives as well as the VAT Directive are, of course, **equal in the hierarchy of norms** ... Thus **the application of the lex superior principle between them is precluded.**"（[本地] `raw/conflict-eu-ag-opinion-C582-08-vat-lex-superior.txt` 第 785–786 行）
- AG Opinion, Case **C-507/13**，第 59 点："... neither of the provisions is *lex superior* in relation to the other."（[本地] `raw/conflict-eu-ag-opinion-C507-13-crd4-lex-posterior.txt` 第 845–846 行）

**[原文]** 国际法上的等价物（无拉丁法谚，但有成文层级规则）：
- ILC A/CN.4/L.702 结论 **(32)**（*jus cogens*）与结论 **(34)**（《联合国宪章》第 103 条）："**A rule of international law may be superior to other rules** ..."
- ILC 2022 年 *jus cogens* 条款草案："hierarchically superior to other rules of international law"
> — [本地] `raw/conflict-ilc-a_cn4_l936-jus-cogens-conclusions.txt`、`raw/conflict-ilc-jus-cogens-draft-articles-2022.txt`

#### 三条法谚的罗马法源头

**[原文]** ILC 报告 **A/CN.4/L.682** 第 56 段给出 lex specialis 的**操作定义**：

> "The principle that special law derogates from general law is a **widely accepted maxim of legal interpretation and technique for the resolution of normative conflicts**. It suggests that, if a matter is regulated by a general standard as well as by a more specific rule, then the latter should take precedence over the former."

**[原文]** 同报告第 56 段**脚注 58**给出该法谚的罗马法出处：

> "The principle *lex specialis derogat legi generali* has a long history; the principle was included in the **Corpus Iuris Civilis**. See Papinian, **Dig. 48, 19, 41** and **Dig. 50, 17, 80**. The latter states: \"**In toto iure generi per speciem derogatur et illud potissimum habetur, quod ad speciem derectum est**\" (\"In the whole of law, species takes precedence over genus, and any ...\"). Some of its alternative formulations are \"generalibus specialia derogant\", \"generi per speciem derogatur\" and \"specialia generalibus, non generalia specialibus\"."
> — [本地] `raw/conflict-ilc-a_cn4_l682.pdf` / `raw/conflict-ilc-a_cn4_l682_add1.txt`

**[原文]** 同报告第 18 段**同时点名三条法谚，并给出它们的方法论定位**（这是本分片最想引用的一段）：

> "Here, interpretative maxims and conflict resolution techniques such as **lex specialis, lex posterior or lex superior** become useful. They enable a systemic relationship to be seen between two or more rules and may thus justify a particular choice of applicable standard and a particular conclusion. **They do not do this mechanically, however, but rather as \"guidelines\"** ..."

**[判断]** **"They do not do this mechanically, however, but rather as 'guidelines'"** —— 这是 ILC 自己说的。它与我下面 §6.3 的结论完全一致：**三条法谚是判据，不是算法。**

**[原文]** 一条补充证据，说明 lex specialis **不能**被用来「解释自己造出来的冲突」——CJEU 在 C-48/14 中记录了欧洲议会的论点：

> "Moreover, according to the Parliament, **the drafter of a measure is not permitted to use the principle of lex specialis derogat legi generali to explain a conflict between two measures which it created.**"
> — [本地] `raw/conflict-eu-cjeu-C48-14-radioactive-water.txt` 第 1071 行

同案法院的立场：

> "Finally, it should be noted that, in relation to Directive 98/83 which concerns, in general, the quality of water intended for human consumption, the contested Directive is a *lex specialis* with regard to the protection of human health against the dangers of radioactive substances in such waters. **Contrary to the Parliament's claims, the principle of lex specialis derogat legi generali is applicable even if the lex generalis and the lex specialis emanate from the same institution.**"
> — 同上，第 1115 行

**[判断]** 这场争论对 Momcozy 有直接映射：**同一个团队（法务/品牌）制定的两条规则之间发生冲突时，能不能用 lex specialis 解决？** 议会主张不能，法院主张能。**采用法院的立场更实用**——否则同一份规则库内部的冲突将无法消解。但**必须在规则库层面显式声明这个立场**（即 §11.6 的 `conflict_strategy` 字段），不能默认。[判断]

#### 三原则小结

| 原则 | 拉丁文 | 一手出处 | 判据 |
|---|---|---|---|
| 特别法优于一般法 | *lex specialis derogat legi generali* | ILC A/CN.4/L.702 结论 (5) | 「更具体的规范」——但**具体性 vs 时间性何者优先须contextually 决定**（结论 (6)） |
| 后法优于前法 | *lex posterior derogat legi priori* | ILC A/CN.4/L.702 结论 (24)；VCLT Art. 30(3) | 「同一 regime 内」最强；**跨 regime 无优先推定**（结论 (26)） |
| 上位法优于下位法 | *lex superior derogat legi inferiori* | **未取得成文定义**；EU AG Opinions C-582/08 §57、C-507/13 中作为分析范畴出现 | 规范层级 |

**[判断]** **最重要的一条元结论**：ILC 结论 (6) 明确说「哪个考虑因素占主导，应当**依情境决定**」，结论 (4) 说「首先应当**调和**」。也就是说：**三条原则不是一张可以自动执行的优先级表，而是一组需要在每个具体冲突上被援引和论证的论据。** 因此，把它们**硬编码进规则引擎的自动优先级**是对它们的误用；正确用法是**把它们变成规则库里的显式声明字段（`priority_direction` / `overrides`），并在规则评审时由人援引论证**。[判断]

### 6.3 三条原则到规则引擎的映射（跨体系对照表）

| 体系 | lex specialis 的实现 | lex superior 的实现 | lex posterior 的实现 |
|---|---|---|---|
| **LegalRuleML** | `DefeasibleStrength` + body subsumption；`Override` | `Override` + `Authority` 层级（人工声明） | `TemporalCharacteristic`（`InForce` / `Starts`） |
| **DMN** | "两条规则同时命中"→ hit policy `P`（按 outputValues 排序）/ `F`（按规则序） | 无内建；靠把上位规则放在外层决策 | 无内建；靠时间窗输入列 |
| **OPA/Rego** | 规则体里的布尔条件自然实现「更具体者命中」 | `default`（最上位兜底总是最后生效） | 靠 `input.now` / 数据里的日期字段 |
| **Cedar** | scope 约束越具体 → 命中越窄；但**结论由 forbid 全权否决** | forbid 天然是上位（guardrail） | 靠 `context` 里的时间属性 |
| **XACML** | 无内建；`Only-one-applicable` 会在多 policy 适用时返回 `Indeterminate` | 用 `PolicySet` 嵌套 + combining algorithm | `First-applicable` + 顺序 |
| **Drools** | `activation-group`（组内只出一条）+ 规则体条件 | `salience` | `date-effective` / `date-expires` |
| **ODRL** | `refinement`（对 Action / AssetCollection / PartyCollection 收窄） | `conflict` 策略 + Profile 定义 | `Constraint` 的 `dateTime` leftOperand |
| **OpenFisca** | 公式日期后缀的覆盖关系 | 无（单一税制层级） | `formula_YYYY` 后来者覆盖前者 |

**[判断]** 三条原则在工程体系里**没有一条被内建为「引擎自动推导」**。它们全部退化为**作者显式声明的优先级关系**。这是一个重要的负面发现：**不要指望规则引擎自动解决冲突；引擎只提供表达优先级的手段，判断「谁优先」永远是人（或批准流程）的责任。** [判断]

---

## 7. 规则库的版本治理与历史判定复现

### 7.1 三条时间轴，而不是两个日期

见 §4.2.5。LegalRuleML 区分 `entry` / `efficacy` / `applicability`。**[判断]** 映射到 Momcozy：

| LegalRuleML 轴 | 内容审核场景的例子 |
|---|---|
| **entry**（生效） | 规则在飞书表格里被标记为「已批准」的日期 |
| **efficacy**（产生效果） | 规则第一次实际拦下内容、进入审查记录的日期 |
| **applicability**（适用） | 规则对某一批内容（某个市场、某个平台、某个时间段投放的素材）有效的日期区间 |

**现状**：Momcozy 只有 `启用状态`（一个布尔位），三条轴都没有。这导致的直接后果是：**一条规则被停用后，无法回答「它在停用前对哪些内容适用过」。**

### 7.2 历史判定复现：四个必需件

**[判断]** 综合 OpenFisca（§3.3–3.4）、Akoma Ntoso（§4.3.2）、LegalRuleML（§4.2.5）的做法，历史判定的可复现性要求审查记录里保存四件东西：

1. **规则集版本 ID**（挂在 EXPRESSION 层）。不是「命中规则编号」，而是「当时的整份规则集快照」。
2. **被判定内容的版本 ID**。同一份广告文案被改过之后，旧的判定对应旧版本的文案。
3. **判定时刻**（用于解析所有带日期键的规则）`decided_at`。
4. **引擎版本 + 检测器版本**。同一条规则换了正则，判定结果会变。

Akoma Ntoso 的做法是把前三件编码进 ID 体系（FRBRthis / FRBRdate / eId / wId）；OpenFisca 的做法是让所有查询都显式带 `period`。**两种做法是等价的：让「时刻」成为查询的必填入参，而不是隐含的「当前时间」。**

### 7.3 规则快照的浅拷贝陷阱

`research/distill/cross-cutting-findings.md` 的反模式清单里有一条「**规则快照浅拷贝**」。**[判断]** 标准做法给出的解法是**内容寻址（content addressing）**：给规则集算一个内容哈希（如 `sha256`），快照文件以哈希命名，只读。这样：①快照不可被追改；②相同内容自然去重；③可以从哈希反查「当时到底跑了什么」。

**[原文]** 一个佐证：Akoma Ntoso 的 `GUID` 与 `eId` 并存（§4.3.2），其中 `eId` 依赖命名约定（可读但需人工维护），`GUID` 是 UUID（不可读但不依赖人工）。内容哈希在这两者之间提供了第三种选择。[判断]

### 7.4 版本对比与影响评估

**[判断]** 把 OpenFisca 的 `reform`（§3.6）与 `research/distill/shards/S4-14`（「版本比对：按规则编码计算风险增量」）结合，规则集变更的最小影响评估是：

```
对同一批历史内容（例如 291 条在跑广告，或一个更大的历史样本）：
  用 规则集_vN   跑一遍 → 结果 A
  用 规则集_vN+1 跑一遍 → 结果 B
  报告 = diff(A, B)，按规则编号归因
```

输出三个数：**新增命中数（新规则捕获的）、失去命中数（被放宽或被抵消的）、翻转数（从通过变不通过 / 反之）**。这三个数就是规则库自迭代的核心度量（详见 R4）。

---

## 8. 规则集的完备性与一致性检查

### 8.1 四个可检查属性

综合 DMN（§5.5.1 的 overlapping / disjoint 定义）与 XACML（§5.3 的 `Only-one-applicable`），一份规则集可以被静态检查的属性有四个：

| 属性 | 定义 | 标准依据 |
|---|---|---|
| **一致性（consistency）** | 不存在两条规则对同一输入给出**相反**结论 | DMN `Unique` 禁止重叠；OPA `complete definition` 多值即报错 |
| **完备性（completeness）** | 每个可能的输入至少被一条规则覆盖（无缺口） | DMN "Crosstab tables are unique and complete by definition"；XACML `Deny-unless-permit` 提供兜底 |
| **冗余（redundancy）** | 不存在永远不可能命中的规则，或结论永远相同的重复规则 | DMN `Unique`；Drools 静态分析 |
| **可判定性（decidability）** | 每条规则都能在有限步骤内给出结论 | CEL "terminating" 设计目标 |

**[判断]** **「覆盖缺口」对 Momcozy 是最重要的一条**。他们的 `判断方式` 21/21 全填「自动可检测」意味着：**规则集声明自己是完备的**。但「自动可检测」是一个关于实现的断言，不是关于覆盖的断言。真正需要回答的是：「一份包含 N 种特征的文案，有多少种特征组合是 21 条规则都没覆盖的？」——按 DMN 的术语，这叫**未覆盖的输入组合**；按 XACML 的术语，这会落到 `NotApplicable`，然后由 `Deny-unless-permit` 兜底成 Deny 或由 `Permit-unless-deny` 兜底成 Permit。

**[判断]** 建议 Momcozy 采用 `Deny-unless-permit` 语义的**审核版本**：

```
默认结论 = 人工复核（不是通过，也不是拒绝）
只有显式命中「安全词白名单」规则 → 通过
只有显式命中「严格限制红线」（H 族）→ 拒绝
其余一切情况（包括未命中、检测器异常、输入缺失）→ 人工复核
```

理由：Cedar 的 `default deny` 论证（§5.2.2）保证了「只有显式许可才放行」；OPA 的 undefined 论证（§5.1.3）保证了「输入缺失不会被静默放过」；而 Momcozy 的治理约束（`00-调研任务书.md` §2.E：无法强制卡死上线节点）意味着**拒绝必须有把握**，否则会被绕过。所以兜底落到「人工复核」而不是「拒绝」是当前治理条件下的正确选择。[判断]

**[原文]** 一条来自**立法起草规范**的「冗余」硬规则，可以直接借用到规则库治理上。新西兰 **LDAC《Legislation Guidelines》2021 版**（由新西兰内阁认可为政府评估立法草案的关键参考文件）**Guideline 3.3**：

> "**Are any matters addressed by the new legislation covered by existing legislation?**
>
> **New legislation should not restate matters already addressed in existing legislation.**
>
> Where a provision in existing legislation satisfactorily addresses an issue, it is preferable not to repeat that provision in new legislation. **This kind of duplication often results in unintended differences, especially where legislation is amended over time** or where the legislation is intended to address a different policy objective."
> — [本地] `raw/conflict-nz-ldac-legislation-guidelines-2021.txt`；URL（PDF）`https://assets.ctfassets.net/6i3jqfgtuxyj/6aiZYGGoVQ4Kym4HcsdhaZ/0c429e6e0446174552aff55a36c073d9/LDAC-Legislation-Guidelines-2021-edition.pdf`

同 **Guideline 3.2**：

> "**Are any conflicts or interactions between new legislation and existing legislation addressed?**
>
> Any conflict or interactions between new and existing legislation should be **explicitly addressed** in the new legislation.
>
> If there is an unavoidable or intentional conflict between new legislation and existing legislation, or where there is any interaction between two or more provisions in different legislation, **the new legislation should make clear which provision shall prevail** or how it is intended that the two provisions should operate together."

**[判断]** 这两条直击 Momcozy 的现状：`research/distill/cross-cutting-findings.md` 的反模式「同一维度多套实现」正是 LDAC 3.3 说的 "this kind of duplication often results in unintended differences, especially where legislation is amended over time"。而 Momcozy 现在有三套并存的规则资产（21 条规则库 / 19 条 W1 卖点边界 / 52 条改写建议库），**它们之间是「重复」还是「层次」，没有任何地方声明过**。LDAC 3.2 要求的「明确哪一条优先」正是 §11.6 里 `overrides` 与 `conflict_strategy` 两个字段要解决的问题。

**[负面结果]** 必须说明：**LDAC Guidelines 2021 全文中，`lex specialis` / `lex posterior` / `lex superior` / `derogat` / `implied repeal` 的出现次数均为 0**；英国 OPC《Drafting Guidance》2024 同样为 0。**这两份文件不能用来引证拉丁法谚**，只能用来引证「不要在立法里重复既有事项」这条**实质规则**。

### 8.2 内建静态检查（已核实）

| 工具 / 方法 | 证据 |
|---|---|
| **OPA** | `opa check` / `opa test` / 渐进类型系统；**`complete definition` 出现多值直接报错**（Policy Reference "Complete Definitions" 节："If evaluation produces multiple values for the same document, an error will be returned."） |
| **XACML `Only-one-applicable`** | 多 policy 适用 → `Indeterminate`（XACML 3.0 §2.3、Appendix C.10） |
| **DMN hit policy 设计期校验** | [原文] "The hit policy can be used to check correctness at design-time."（DMN 1.5 §8.2.11）；`Unique` 表若含重叠规则即为设计错误 |

### 8.3 其他形式化方法与静态分析工具（证据情况）

| 工具 / 方法 | 状态 | 证据 |
|---|---|---|
| **OPA 内建检查** | ✔ 已核实 | `opa check` / `opa test` / 渐进类型系统；**`complete definition` 出现多值直接报错**（Policy Reference "Complete Definitions" 节："If evaluation produces multiple values for the same document, an error will be returned."） |
| **XACML `Only-one-applicable`** | ✔ 已核实 | 规范原文（Appendix C.9）："In the entire set of policies in the policy set, if no policy is considered applicable by virtue of its target, then the result of the policy-combination algorithm SHALL be \"NotApplicable\". **If more than one policy is considered applicable by virtue of its target, then the result of the policy-combination algorithm SHALL be \"Indeterminate\".**" —— **这就是标准自带的冲突检测器** |
| **DMN hit policy 设计期校验** | ✔ 已核实 | [原文] "The hit policy can be used to check correctness at design-time."（DMN 1.5 §8.2.11）；`Unique` 表若含重叠规则即为设计错误 |
| **Drools DMN 静态分析** | ✔ 已核实 —— **本条是「冲突 + 冗余 + 覆盖缺口」三元组在已发布引擎中的最佳单一引文** | Drools/KIE DMN 文档 "Configurable DMN validation" 节：**"`ANALYZE_DECISION_TABLE`: DMN decision tables are statically analyzed for gaps or overlaps and to ensure that the semantic of the decision table follows best practices."** [本地] `raw/conflict-drools-DMN-index.html.txt` 第 379–391 行。可单独启用：`<validateDMN>ANALYZE_DECISION_TABLE</validateDMN>` |
| **Drools 规则引擎的 agenda 冲突消解** | ✔ 已核实 | [原文] "The agenda controls the execution order of these rule internalMatches using a **conflict resolution strategy**." 与 "Truth maintenance also helps to identify inconsistencies and to handle contradictions."（[本地] `raw/conflict-drools-rule-engine-index.html.txt`） |
| **DMN 覆盖缺口的建模原语** | ✔ 已核实（**这是「未覆盖时返回什么」的标准答案**） | DMN 1.4/1.5 元模型 `DecisionTable` 的 `defaultOutputEntry` 属性：**"defaultOutputEntry: Expression — In an Incomplete table, this attribute lists an instance of Expression that is selected when no rules match for the decision table."** 另，DMN 1.4 §8.2.4 对输入值的完备性要求：**"input values SHOULD be exclusive and complete. Exclusive means that input values are disjoint. Complete means that all relevant input values from the domain are present."** 并给出反例："the following two input value ranges overlap: `<5, <10`. The following two ranges are incomplete: `<5, >5`." |
| **Alloy 6** | △ 部分 | 官方文档：[本地] `raw/conflict-alloy-docs.txt` — "Alloy 6 is a self-contained executable, which includes the Pardinus/Kodkod model finder and a variety of SAT solvers ... Since Alloy 6, the tool can also perform temporal model-checking." Alloy 语言规范（`https://alloytools.org/spec.html`）：<br>"A `run` command causes the analyzer to **search for an example that witnesses the consistency** of a function or a predicate. A `check` command causes it to **search for a counterexample showing that an assertion does not hold**."<br>"A model without any core instances is **inconsistent**, and almost certainly erroneous."<br>"An assertion is expected not to have any instances: the instances are **counterexamples**, which indicate that the assertion does not follow from the facts."<br>**局限（必须说明）**："The Alloy Analyzer finds instances of a model automatically by **search within finite bounds** for variables (specified by the user as a scope)" —— **有界分析，不是完全证明**。**且未找到官方文档中直接针对「规则集」的用法示例** |
| **SMT-based 规则分析** | ✔ 工业级实证 | Cedar 论文："One such question is **policy equivalence** — do two (sets of) policies evaluate to true on the same set of requests? For that, we turn to Cedar's **symbolic compiler, which works by reducing policies to SMT formulas**, and discharging questions about their behavior using an SMT solver." [本地] `raw/cedar-oopsla.pdftxt` |
| **Lean 形式化证明** | ✔ | Cedar 论文摘要："We have modeled Cedar in the Lean programming language, and used Lean's proof assistant to prove important properties of Cedar's design." |
| **知识库异常检测的经典文献** | △ 仅二手（OpenAlex 摘要） | 经 OpenAlex 检索确认存在以下经典工作（**仅摘要，未读原文，不作为论断依据**）：1987 年决策表完备性/一致性处理（DOI `10.1016/s0020-7373(87)80076-7`）；Preece 1992 的四类异常 = **redundancy, ambivalence, circularity, deficiency**（DOI `10.1017/s026988890000624x`）；1993 "detecting missing knowledge"（DOI `10.1006/imms.1993.1031`）；1994 KB verification（DOI `10.1002/int.4550090804`） |
| **Drools Verifier（独立产品）** | ✘ **负面结果** | Drools 8.44.0.Final 官方文档中**没有**独立的 "Drools Verifier" 章节；历史上的 Drools Verifier 产品不在当前文档树中，只有 DMN 的 `ANALYZE_DECISION_TABLE` 路径保留了下来 |
| **XACML 中的「policy conflict」字样** | ✘ **负面结果** | XACML 3.0 OS 规范全文中字面短语 "policy conflict" 出现 **0 次**。该规范用 combining algorithm 与 `Indeterminate` 表达冲突，而不用 "conflict" 这个词 |

**[判断]** **最有价值的可迁移做法是 Drools 的 `ANALYZE_DECISION_TABLE`**：它是唯一一个把「gaps（覆盖缺口）+ overlaps（冲突/冗余）」写进**一句产品文档**的已发布引擎。对 Momcozy 这意味着：「21 条规则之间有没有重叠、有没有覆盖缺口」**不是学术问题，而是决策表引擎的标准检查项**——但他们现在用的是飞书多维表格，没有这个检查。建议把「用 DMN 决策表重新表达规则集并跑静态分析」列入 §11.7 的 P2。

**[判断]** 第二有价值的是 Cedar 的**策略等价性检查**：它回答的问题恰好是 Momcozy 在规则库迭代时最需要的那一个——「规则集从 v3 改到 v4 之后，实际允许/拒绝的集合变了吗？变了哪些？」Cedar 把策略编译成 SMT 公式，用求解器判定两个策略集是否等价；不等价时给出**反例**（一个具体请求，在 v3 通过、在 v4 被拒）。对 Momcozy，这个能力可以用「历史内容回归」近似实现（§7.4 的 diff 方法），成本远低于引入 SMT 求解器，且能直接给出业务可读的反例。见 R4 的 Golden Dataset 设计。


## 9. 合规自动化中的「作用域」建模

### 9.1 法规知识图谱（建模方式）

**[判断]** 从 LegalRuleML 的做法（§4.2）可以归纳出法规知识图谱的**最小建模方式**：

```
Rule ──appliesJurisdiction──→ Jurisdiction
     ──appliesAuthority────→ Authority ──hasJurisdiction──→ Jurisdiction
     ──appliesSource───────→ LegalSource（可细到 word / sentence / paragraph / letter）
     ──appliesStrength─────→ Strength（StrictStrength / DefeasibleStrength / Defeater）
     ──appliesTemporalCharacteristics──→ TemporalCharacteristic ──atTime──→ Time
     ──appliesModality─────→ Deontic（OBL / PER / FOR）
     ──appliesPenalty──────→ PenaltyStatement（通过 Reparation）
```

**[判断]** 这张图的关键性质是：**所有作用域信息都是「边」，不是「列」**。边可以有独立的生命周期、可以被单独审计、可以被覆盖（同一个 `Rule` 在不同的 `Context` 下有不同的 `appliesStrength`）。列做不到这些。

### 9.2 GDPR 的形式化：DPV —— 「辖区是命名空间，不是字段」

#### 9.2.0 证据状态：四份来源中三份已可全文核对

**[更正记录]** 本节早先的版本写的是「SPECIAL 与 DAPRECO 的 PDF 抓到了但无法提取全文，因此以 DPV 为主证据」。**该判断已作废**：子代理自写的纯 Python PDF 提取器（处理 FlateDecode、对象流中的嵌套流、Form XObject、逐页字体资源、ToUnicode CMap、`/Differences` 字形名与连字）已成功产出 DAPRECO 论文与 SPECIAL D2.1–D2.4 的正文。提取器已存入 `_evidence/R3/tools/pdftext5.py`，**R1 / R2 / R4 / R5 可直接复用**（用法 `python3 pdftext5.py in.pdf out.txt`）。

本节现在**同时**核对四份来源，标准是「有没有一手工件」而不是「有没有论文」：

| 来源 | 一手工件 | 状态 |
|---|---|---|
| **DPV v2.3** | W3C CG Final Report 全文 + `dpv:core` 的 689 KB Turtle 定义文件 + Rules / Context / legal_basis 模块 | ✔ 逐字核对 |
| **SPECIAL** | D2.1《Policy Language V1》等 4 份 deliverable 正文（文本 102 KB / 53 KB / 80 KB / 81 KB） | ✔ 逐字核对 |
| **DAPRECO** | **知识库本体本身** `gdpr-dapreco-kb-rioKB_GDPR.xml`（5,633,102 字节 / 962 条规则）+ 论文全文 | ✔ 逐字核对 + 逐条计数 |
| **PrOnto** | 仅 Springer 章节摘要（付费墙） | ✘ **仍不可核对**；本文不对 PrOnto 的具体公理做断言 |

- 规范：`Data Privacy Vocabulary (DPV) version 2.3`，W3C Community Group Final Report，2026-02-25
- URL：`https://w3id.org/dpv/` / `https://www.w3.org/community/reports/dpvcg/CG-FINAL-dpv-20260225/`
- [本地] `raw/gdpr-dpv-spec.html`（1.32 MB）、`raw/gdpr-dpv-spec.txt`（267 KB）、`raw/gdpr-dpv-core.ttl`（689 KB）；`raw/gdpr-dpv-module-rules.*`、`raw/gdpr-dpv-module-context.*`

**[核对纪律]** §9.2 的所有数字都由我**直接在本地工件上重新计数**得出，不采信二手转述。每处计数都写明口径（例如区分「开标签数」与「字符串出现次数」——在 DAPRECO 上这两者恰好差 2 倍，见 §9.2.9）。二手转述与工件不符之处，**以工件为准并显式记录更正**。

#### 9.2.1 DPV 的核心设计：core concepts 相互独立

**[原文]**（DPV spec §Introduction 附近，逐字）：

> "DPV and its extensions (collectively DPV vocabularies) consists of certain **'core concepts' that are intended to be independent representations of specific information, and are distinct from other core concepts**. For example, the **Purpose** refers only to the purpose of why personal data is processed and **is independent as a concept from the other concepts (e.g. PersonalData or LegalBasis)**. The structuring of DPV is based on providing rich and comprehensive taxonomies that group concepts together based on each core concept, e.g. taxonomy of purposes, taxonomy of legal basis. **'Extensions' are a separate group of concepts that expand the 'core' vocabulary or provide concepts focused on a particular topic** e.g. [PD] for personal data categories and [RISK] for risk management. **Extensions allow modelling legally relevant but jurisdictionally applicable concepts** e.g. [EU-GDPR] for concepts from EU's GDPR."

#### 9.2.2 **辖区是一个命名空间，不是一个字段**（本节最重要的证据）

**[原文]**（DPV spec §Introduction，逐字）：

> "**Legal Jurisdiction-relevant concepts for DPV ([LEGAL])** provides concepts to represent laws, authorities, and other legal concepts in various jurisdictions. **It is structured to create a separate namespace for each country or jurisdiction by using the ISO 3166-2 code**, for example `IE` represents Ireland and `EU` represents the European Union. **Within this namespace, the specific laws and authorities for that jurisdiction are defined.**"

> "**Laws are modelled as extensions within the namespace of their respective jurisdictions.** The following are extensions part of [LEGAL-EU]: EU GDPR concepts for DPV ([EU-GDPR]), EU DGA concepts for DPV ([EU-DGA]), EU NIS2 concepts for DPV ([EU-NIS2]), EU AI Act concepts for DPV ([EU-AIAct]), EU Health Data Space (EHDS) concepts for DPV ([EU-EHDS]), EU Fundamental Rights concepts for DPV ([EU-RIGHTS])."

**[判断]** **这是对 Momcozy「国家 × … 四维笛卡尔积」问题最锐利的一个回答**：

DPV —— 目前最权威的数据保护机器可读词汇表 —— 处理「同一个概念在不同国家有不同规定」的做法**不是**给概念加一个 `jurisdiction` 字段，而是**给每个辖区一个独立的命名空间，法律在该命名空间内定义**。

对 Momcozy 的直接翻译：

```
❌ 错误做法（现状的思路）
   规则表 { 规则编号, 国家, 品类, 平台, 内容类型, ... }
   → 同一个概念在 8 个国家有 8 行

✅ 标准做法
   namespace: brand.core      ← 品牌通用概念（吸奶器、功效声称、目标人群）
   namespace: brand.us        ← 美国特有概念（FTC 健康声明、FDA 器械边界）
   namespace: brand.de        ← 德国特有概念（HWG 药品广告法）
   namespace: platform.google ← Google 广告政策概念
   namespace: platform.meta   ← Meta 广告政策概念

   规则:  brand.core.H03  「不得宣称治疗/治愈疾病」
          brand.us.H03-us 「…并引用 21 CFR / FTC 具体条款」
          brand.de.H03-de 「…并引用 HWG §3」
```

**「H03 在德国长什么样」不是 H03 的一个字段值，而是 `brand.de` 命名空间里的一条独立规则。** 它在继承自 `brand.core.H03` 的基础上**收窄或加强**——这正是 ODRL `refinement` 的语义（§9.3.3），也是 LegalRuleML `Context`（"localizes the strength of a rule"）的语义（§4.1.5）。

#### 9.2.3 Rules 模块：deontic 三分 + 与 RFC 2119 的对齐

**[原文]**（DPV Modules → Rules §1 Introduction，逐字）：

> "DPV provides the concept **Rule** to specify requirements, constraints, and other forms of 'rules' that are **associated with specific contexts (e.g., processing activities) using the relation `hasRule`**. DPV provides two categories of rules to broadly represent what is acceptable (**AcceptableRule**) and unacceptable (**UnacceptableRule**). DPV also provides concepts to indicate the outcome of assessing the rules as statuses through **RuleFulfilmentStatus** with distinction between **RuleFulfilled, RuleUnfulfilled, and RuleViolated**."

> "**DPV does not define additional semantics for rules and limits its scope and focus to provide a simple way to specify permissions, prohibitions, and obligations as common rules associated with activities** ... For a more extensive and richer set of semantics and concepts to represent rules, DPVCG suggests looking towards other languages, such as **[ODRL], [SHACL], and [RuleML]** that have been developed with the specific goal of representing and applying rules."

**[原文]** §2 Rules 的完整子类清单（逐字）：

> "dpv:AcceptableRule: A rule that is acceptable where it is either desirable if it occurs or it is not unacceptable if it does"
> "dpv:Obligation: A rule describing an obligation for performing an activity"
> "dpv:Permission: A rule describing a permission to perform an activity"
> "dpv:Recommendation: A rule describing a recommendation for performing an activity"
> "dpv:UnacceptableRule: A rule that is unacceptable where it is not desirable if it occurs"
> "dpv:Deterrence: A rule describing a deterrence for performing an activity"
> "dpv:Prohibition: A rule describing a prohibition to perform an activity"

**[原文]** §2.1 Alignment with RFC2199（逐字，**这是把「严重度」与「modality」对齐的现成方案**）：

> | Concept | RFC 2119 Keyword |
> |---|---|
> | Permission | MAY |
> | Recommendation | SHOULD |
> | Obligation | MUST |
> | Prohibition | MUST NOT |
> | Deterrence | SHOULD NOT |
> | Not Provided | MAY NOT |

**[判断]** **这张表直接对应 Momcozy 的 `边界类型` 四档**。现在的四档 `严格限制红线 / 审慎关注 / 人工复核 / 安全词白名单` 可以无歧义地映射为：

| Momcozy 现状 | DPV / RFC 2119 | modality |
|---|---|---|
| 严格限制红线 | `Prohibition` / MUST NOT | prohibition |
| 审慎关注（需限定） | `Obligation`（须附带限定语）/ MUST | obligation |
| 人工复核 | *（无直接对应 —— 这是一个「无法自动判定」的取值，见 §9.2.4）* | — |
| 安全词白名单 | `Permission` / MAY | permission |

**「人工复核」在 RFC 2119 体系里没有对应词，因为它不是一种 deontic modality，而是一种 evaluability。** 这就是 §11.1 第 7 条诊断的依据：**`边界类型` 把 modality 和 evaluability 混在了一列。** [判断]

#### 9.2.4 「无法判定」是一等公民：`NotApplicable` / `NotAvailable` / `UnknownApplicability`

这是 DPV 对「开放概念」问题给出的最干净的答案。

**[原文]**（DPV Modules → Context §5 Applicability，逐字）：

> "**5. Applicability**
>
> Applicability concepts enable expressing conditions where **the information is not available, or is not applicable, or it is unknown**. The concepts provided to represent these are: **NotApplicable, NotAvailable, and UnknownApplicability**. These concepts are useful for **'closed world' interpretations where information _must_ be provided** e.g. when filling out a form a human may write \"N/A\" in the text field instead of providing the requested information."

> "This example show how the unavailability, or non-applicability, or unknown applicability of information can be expressed using the Applicability concepts. **Note that such situations may represent risks or issues that may require additional attention e.g. where the information is unknown, further steps should be taken to determine the exact applicability.**"

```turtle
ex:PDH a dpv:Process ;
  # information about personal data is not available at the moment
  dpv:hasPersonalData dpv:NotAvailable ;
  # personal data is not involved, so we specify not applicable
  dpv:hasPersonalData dpv:NotApplicable ;
  # we don't know yet if personal data is involved - so it is unknown
  dpv:hasPersonalData dpv:UnknownApplicability ;
```

**[原文]** 三个概念的独立定义（逐字）：

> "**dpv:Applicability**: Concept provided to represent indication of cases where the information or context is not applicable (N/A) or not available or this is not known or determined yet. **If the information is applicable and available, this concept should not be used.**"
> "**dpv:NotApplicable**: Concept indicating the information or context is not applicable"
> "（DPV spec 全文索引 §8.1.74 Not Applicable / §8.2.35 is not applicable for）"

**[原文]** 一条设计注记（对「边界值」的严格性）：

> "**dpv:FeeNotRequired**: Concept indicating a fee is not required. **This is distinct from a Fee of zero** as it indicates a fee is not applicable in the context"

**[判断]** 这最后一条注记是一个绝佳的类比：**「不要求」与「要求 0」是两回事**。同理，在内容审核里：

- **`NotApplicable`** = 这条规则**不适用于**这份内容（例如：规则是关于视频的，而这是图片）
- **`NotAvailable`** = 判定所需的信息**拿不到**（例如：图片存在但 OCR 服务超时）
- **`UnknownApplicability`** = **还不知道**这条规则适不适用（例如：内容还没被分类）

**这三个值的处置路径完全不同**：`NotApplicable` → 跳过该规则（不产生结论）；`NotAvailable` → 走引擎异常通道；`UnknownApplicability` → 必须先补全前置信息。

**现状**：Momcozy 的 `判断方式 = 自动可检测`（21/21）把这三者全部折叠成了「适用且可判定」。这是本分片中我认为**风险最高的单个设计缺陷**。[判断]

#### 9.2.5 GDPR 本身的 formalization 项目（证据状态）

| 项目 | 抓到的东西 | 能否引用其模型 |
|---|---|---|
| **DPV**（W3C CG Final Report, v2.3） | ✔ 全文 + Rules / Context 模块 + 689 KB 的 `dpv:core` 定义文件 | ✔ 已在上文引用，术语级证据见 §9.2.7 |
| **SPECIAL**（H2020，SPL 政策语言） | ✔ **D2.1 / D2.2 / D2.3 / D2.4 正文已成功提取**（`raw/gdpr-SPECIAL_D2*_M1*_V10.txt`） | ✔ §9.2.6 引用其五元组授权模型，§9.2.10 引用其自我限定 |
| **DAPRECO**（GDPR → LegalRuleML 知识库） | ✔ **知识库本体 `gdpr-dapreco-kb-rioKB_GDPR.xml`（5.6 MB / 962 条规则）** + 论文全文 + GitHub 搜索 JSON + OpenAlex 元数据 | ✔ **见 §9.2.9**，含逐条计数 |
| **PrOnto**（意大利 GDPR 本体） | 抓到 `gdpr-pronto-*.html`、OpenAlex 元数据；Springer 章节全文**付费墙** | ✘ **仍未能取得正文**，本文不断言其公理 |

**[判断]** 早先版本把 **DAPRECO 记为本分片最大的缺口**；这一判断**已被推翻且方向相反**——DAPRECO 现在是本分片中**证据最硬的一份**。原因不是论文拿到了，而是**知识库本体本身拿到了**：`gdpr-dapreco-kb-rioKB_GDPR.xml` 是 DAPRECO 项目的实际交付物，我可以对它逐条计数、逐条核对，而不是转述作者对它的描述。这与 §0.1 的证据分级原则一致：**能读到工件，就不必依赖对工件的叙述**。

**PrOnto 仍是真缺口**。它只有 Springer 章节（付费墙）+ 二手描述。二手描述里有一句值得记录但不作为证据：DAPRECO 论文称「PrOnto alone is not a suitable knowledge base truly fit for automatic legal reasoning」——这是**同一批作者对另一个项目的评价**，不是 PrOnto 作者的自述，本文仅作为线索记录，不用于任何论断。已在附录 B.2 记录。

#### 9.2.6 SPECIAL：授权的五元组，以及「合规 = 集合包含」

SPECIAL（H2020 项目 "Scalable Policy-awarE Linked Data arChitecture for prIvacy, trAnsparency and complIance"）的 deliverable **D2.1《Policy Language V1》**（2017-12-26，Final）本次**成功提取了正文**（[本地] `raw/gdpr-SPECIAL_D21_M12_V10.txt`，56 页 / 102 KB）。它给出了一个与 Momcozy 问题**最接近**的建模方案。

**[原文]**（D2.1 第 1 章 "What is a Usage Policy?"，逐字）：

> "Conceptually, a **usage policy** is meant to specify a **set of authorized operations**. In the **minimum core model** (MCM) specified in deliverable D1.3 such authorized operations are characterized by:
>
> * the **data** processed by the operation;
> * the **purpose** of the operation;
> * a description of the **operation** itself (e.g. \"query\", \"classification\", \"disclosure\", etc.);
> * a description of **where the result is stored and for how long**;
> * the **entities that can access the result** of the operation (**recipients**).
>
> That is, in abstract, mathematical terms a usage policy is just a set of tuples like
>
> `⟨data item, purpose, operation, storage, recipient⟩`
>
> that will be called **authorizations**, each of which specifies a permitted operation."

> "Example 1 — A policy `P` allows to disclose the file `John_Smith_profile.xml` to company ACME for commercial purposes iff a corresponding authorization
>
> `⟨John_Smith_profile.xml, CommercialPurpose, disclose, null, ACME⟩`
>
> belongs to `P`."

**[原文]** 合规判定 = **集合包含**（逐字）：

> "Therefore, the usage policy adopted by the data controller (call it `P_c`) **complies with** the usage policy in the data subject's consent (call it `P_s`) if and only if all the authorizations in `P_c` are also authorized by `P_s`, that is, `P_c` complies with `P_s` if and only if
>
> `P_c ⊆ P_s`. (1.1)"

> "Now we have to define a **policy language** where this kind of policies can be modelled precisely and unambiguously, possibly by representing **large sets of authorizations (tuples) in a concise way**."
> "SPECIAL's usage policies are encoded in **OWL 2**."

**[判断]** SPECIAL 是**唯一一个真的用了「多轴元组」的体系**，因此它对 Momcozy 的问题给出了最有分辨力的回答：

| | SPECIAL | Momcozy 现状 |
|---|---|---|
| 元组的每个元素是什么 | **一个独立的语义轴**（数据 / 目的 / 操作 / 存储 / 接收方），各有自己的类型与值域 | 四个**分类标签**（国家 / 品类 / 平台 / 内容类型），平铺在同一行 |
| 元组代表什么 | **一条授权**（authorization）——即「在什么条件下允许做什么」 | 一条规则的**适用范围标签** |
| 未指定的轴怎么表示 | `null`（见 Example 1 的 `storage` 位） | 无此概念（只能靠「填了所有值」） |
| 多条元组的关系 | **集合**——合规判定是 `P_c ⊆ P_s` | 无（行与行之间没有代数关系） |
| 如何压缩大集合 | **用 OWL 2 本体表示，靠推理引擎展开**（"representing large sets of authorizations (tuples) in a concise way"） | 无（只能一行一行填） |

**[判断]** **关键差异在最后两行。** SPECIAL 允许用「一个本体公理 + 推理」来表示「一大组元组」，而不是把它们**逐条物化**。这正是笛卡尔积问题的正解：**不是把乘积展开成表，而是用规则/本体去描述这个乘积，让引擎在判定时展开**。

对 Momcozy 的翻译：不需要建 5×8×3×4 = 480 行，而是写

```
scope: jurisdiction ∈ {US, DE, FR, IT, ES, GB, CA}   // 一条声明
       ∧ platform ∈ {google_ads, meta_ads}
       ∧ category = breast_pump
       ∧ content_type ∈ {copy, image, video}
```

引擎在判定时**按需求交**。这就是 SPECIAL 说的 "representing large sets of authorizations (tuples) in a concise way"。

**[判断]** DPV 已经给出了足够的答案，而且它的证据强度在四份来源里最高（W3C 最终报告）。**辖区用命名空间隔离，法律在各自命名空间内定义，判定结果的「不可判定」有三种独立的取值。** 这三条足以支撑 §11.2 与 §11.6 的建议。下面三节把 DPV 的证据下沉到**术语级**（§9.2.7），把它的两个**文档化空缺**读出来（§9.2.8），再用 **DAPRECO 的实际知识库**给「作用域与规则本体分离」补上量化证据（§9.2.9），最后回到 SPECIAL 的自我限定（§9.2.10）。

---

#### 9.2.7 DPV 的术语级证据：**规则本体不带上下文，作用域只能从外面挂上去**

§9.2.2 用的是 DPV 的散文说明（「辖区是命名空间」）。散文可能有解释空间，**机器可读的术语定义没有**。DPV 的 `dpv:core` 定义文件（`raw/gdpr-dpv-core.ttl`，689,268 字节）把这个问题回答得非常硬。

**[原文]** 规则本体 `dpv:Rule` 的定义（`dpv:core` / Rules 模块，逐字）：

> `dpv:Rule` — skos:definition: "**A rule describing a process or control that directs or determines if and how an activity should be conducted**"

**[原文]** 连接边 `dpv:hasRule`（逐字）：

> `dpv:hasRule` — skos:definition: "**Specifies applicability or inclusion of a rule within specified context**"
> `dcam:domainIncludes dpv:Context ;`
> `dcam:rangeIncludes dpv:Rule ;`

**[原文]** 作用域侧（逐字）：

> `dpv:hasScope` — skos:definition: "**Indicates the scope of specified concept or context**"；`dcam:rangeIncludes dpv:Scope`
> `dpv:Scope` — skos:definition: "**Indication of the extent or range or boundaries associated with(in) a context**"；`rdfs:subClassOf dpv:Context`
> `dpv:hasJurisdiction` — skos:definition: "**Indicates applicability of specified jurisdiction**"；`dcam:rangeIncludes dpv:Location`
> `dpv:hasApplicableLaw` — skos:definition: "**Indicates applicability of a Law**"；`dcam:rangeIncludes dpv:Law`

**[原文]** `dpv:hasRule` 的五个子属性，定义句式完全同构（逐字）：

> `dpv:hasDeterrence` — "Specifies applicability or inclusion of **a deterrence rule** within specified context"
> `dpv:hasObligation` — "Specifies applicability or inclusion of **an obligation rule** within specified context"
> `dpv:hasPermission` — "Specifies applicability or inclusion of **a permission rule** within specified context"
> `dpv:hasProhibition` — "Specifies applicability or inclusion of **a prohibition rule** within specified context"
> `dpv:hasRecommendation` — "Specifies applicability or inclusion of **a recommendation rule** within specified context"

**[判断]** 这四条定义合起来证明了 §1 的核心论断，而且是**机器可验证的**，不依赖对散文的解读。三条性质：

1. **`Rule` 的定义里没有作用域。** 它说的是「一条描述流程或控制的规则，决定某项活动**应如何**进行」——主语是活动与规则，**通篇没有出现辖区、平台、品类、时间**。规则本体是**无上下文的概念**。
2. **作用域侧独立成类，且与规则侧不同源。** `Scope` 是 `Context` 的子类，`Context` 又是 `Rule` 完全不相关的另一个类。两侧不在同一棵分类树上。
3. **两侧靠一条「边」相连，方向是 Context → Rule。** `hasRule` 的 `domain` 是 `Context`、`range` 是 `Rule`，即「**上下文拥有规则**」，而**不是**「规则携带一个上下文字段」。这是建模方向上的根本差异：前者是图的一条边，后者是表的一列。

**[判断]** 对 Momcozy 的直接翻译：现行 12 字段表把「规则说什么」和「规则在哪些情形下适用」放在**同一行**，在 DPV 的建模语言里等价于**把 `hasRule` 这条边的两个端点强行塞进同一条记录**。后果不是「更紧凑」，而是**这条边不再存在**——于是「同一逻辑在不同国家有 N 个副本」成为必然，且副本之间无法被引擎识别为同一条规则的不同适用。§11.2 给的 `hcontainer` 层级链，本质上就是把这条边补回来。

**[原文]** DPV 自己在 `LegalBasis` 上留的注记，把「适用性靠边挂」讲得更直白（逐字）：

> "**Legal basis** (plural: legal bases) are defined by legislations and regulations, whose **applicability is usually restricted to specific jurisdictions which can be represented using `dpv:hasJurisdiction` or `dpv:hasLaw`**. Legal basis **can be used without such declarations**, e.g. 'Consent', however **their interpretation will require association with a law**, e.g. 'EU GDPR'."

注意最后半句的分寸：DPV 允许你**先不写**适用辖区，但明确说**解释它时需要关联到一部法律**。这与 §1 结论 2（兜底必须显式）是同一种工程态度——**允许暂缺，但必须知道缺了什么**。

---

#### 9.2.8 DPV 明确承认两个空缺：**不定义「触发条件」，也不定义「默认解释」**

这一节是本轮新增证据里**最有价值的一条**，因为它把 §1 的结论从「我们的建议」升级为「最成熟体系的公开立场」。

先做一个**出处更正**（重要）：下面两段**不在**主规范 `CG-FINAL-dpv-20260225` 里。主规范的 §4 是「Vocabulary Index」。这两段出自 **DPV 的 Rules 模块文档**——标题 "Rules — concepts in Data Privacy Vocabulary (DPV)"，同属 2026-02-25 Final Community Group Report，规范 URL `https://w3id.org/dpv/modules/rules`（版本化 URL `https://w3id.org/dpv/2.3/modules/rules`）——的 §3.1 与 §4。引用时必须写模块文档，不能写「DPV 规范 §4」。本地工件：`raw/gdpr-dpv-module-rules.txt`（§4 正文在第 481 行）、`raw/gdpr-dpv-module-rules.clean.txt`（第 937 行）、`raw/gdpr-dpv-module-rules.html`。

**（一）§4 Triggering Rules —— 不定义「什么时候规则被触发」**

**[原文]**（DPV Modules → Rules §4，逐字）：

> "**DPV does not define how rules are 'triggered' i.e. how to specify under what conditions a rule should become applicable or is exempted from being applied.** Some common triggers for rules to be applied are provided here as examples:
>
> * **Ex-ante**: the rule is applied **before** the specified activity is carried out.
> * **Ex-post**: the rule is applied **after** the specified activity is carried out.
> * **Real-time**: the rule is applied **during** the specified activity being carried out."

**[原文]** 紧随其后的 Note（逐字，含未来工作声明）：

> "**Note**: **DPVCG is exploring providing rule trigger concepts in future versions.** The rule trigger concepts would represent **when/how the rule is to be applied** - as described above - and would further assist in **explicitly representing the intended interpretation and application of a rule within the stated context**. For example, **whether an obligation associated with a process is to be carried out before the process starts (ex-ante trigger) or after it completes (ex-post trigger)** would be interpreted through these concepts. In addition to these, further granular concepts would also assist in further expressing the intended actions - such as **a prohibition that comes in to play only on failures of a process to complete successfully**, or **an obligation that only occurs if a process is successful**."

**（二）§3.1 Default Interpretation —— 不定义「没写就是允许还是禁止」**

**[原文]**（DPV Modules → Rules §3.1，逐字）：

> "Though DPV provides concepts representing **deontic logic**, **it does not specify what should be the 'default' interpretation in relation to rules**, i.e. **it does not provide an interpretation of whether some rules apply automatically unless otherwise declared**. For example, in declaring an instance of `Process`, the assumption is that the activities are modelled for what is happening or what is intended/planned to happen. The explicit annotation using a `Permission` rule adds information about whether some activity is permitted (and its associated information). Instead, if the use-case is using DPV to only document activities that are permitted, there is no need to explicitly specify the permissions. **Similarly, just because something is happening or planned to happen, it cannot be assumed to be permitted** (e.g. pending evaluation of legal requirements)."

**[原文]** 同一节给出的**理由**，以及它**明确考虑并否决了「覆盖（override）」这条捷径**（逐字，本节最关键的一段）：

> "**This lack of default interpretation enables modularity in the use of DPV concepts.** For example, an instance of `dpv:Process` **which does not have a `dpv:hasRule` declared within it, can be made part of a rule** to specify permissions, prohibitions, or obligations regarding the process. **If instead the process had a default interpretation (e.g. permission), then it would require creating a separate instance with the same information - leading to duplicated efforts.** While an apparent solution is to **create a mechanism whereby the rule in the process is overridden with the intended 'outer' rule or context** e.g. to specify the prohibition in one process overrules permission in another process, **this prevents the combination of rules to describe situations such as a permission for a larger context within which specific parts are prohibited or obligated.**"

**[判断]** 这段的价值有三层，逐层对 Momcozy 生效：

1. **「没写」不等于「允许」，也不等于「禁止」——它等于「未定」。** DPV 是数据保护领域最成熟的机器可读词汇表，它宁可**留空**也不给一个默认值。这与 §1 结论 2（兜底必须显式声明、六个体系零例外）完全一致，并且这是**第七个独立体系、也是与商业政策最接近的一个**。
2. **默认值会摧毁模块化，代价是复制。** DPV 说得很具体：如果 `Process` 有了默认解释（比如「默认允许」），那么想表达别的意思时**就必须再造一个同信息的实例**——「leading to duplicated efforts」。**这正是 Momcozy 四维笛卡尔积的成因机制**：一旦规则行自带默认适用性，任何适用范围的差异都只能靠**再抄一行**来表达。
3. **「上层覆盖下层」这条看似显然的捷径被明确否决。** DPV 考虑过「让外层的规则覆盖内层的规则」（这正是「越具体越优先」或「越上位越优先」的机制化版本），结论是：**这会破坏规则的组合能力**——你就无法再表达「大范围允许、其中某些部分禁止」这种嵌套上下文。**这一条直接命中 §11.2 的设计选择**：作用域链**不能**只靠一条全局优先级方向来实现，必须能同时表达「上位放行 + 下位收紧」。§1 结论 1（作用域是边不是列）与 §6 的 lex specialis / lex superior 判据在此处合流：**优先级是判据，不是覆盖开关**。

**[判断]** 还有一层工程启示：**DPV 把一个缺口显式写成了缺口**，还附上未来工作计划（Ex-ante / Ex-post / Real-time 的分类已经先行给出）。也就是说，一个缺口在成熟体系里的正确记录方式是：**「本版本不定义 X，已知的取值形态是 A/B/C，未来版本将补」**——而不是「暂用 0 代替」或「默认为 false」。对照 §1 结论 2 里 OPA 的 `undefined` 第三态、ODRL 的 `invalid`、Cedar 的 default-deny，**这是同一种纪律的第四次出现**。

---

#### 9.2.9 DAPRECO：**962 条规则，只用 4 个 context** —— 作用域不是字段，是可复用的引用集合

DAPRECO 把整部 GDPR 逐条转写成形式逻辑（reified Input/Output logic，LegalRuleML 序列化）。它的交付物是知识库本体 `raw/gdpr-dapreco-kb-rioKB_GDPR.xml`，**5,633,102 字节**。下面是直接在该文件上重新计数的结果。

**（一）作用域侧：只有 4 个 `Context`，全部是顶层容器**

**[工件原文]** 四个 `Context` 开标签（逐字，`<lrml:Context>` 全文件仅此 4 个）：

```
<lrml:Context key="context_1" type="rioOnto:obligationRule">
<lrml:Context key="context_2" type="rioOnto:permissionRule">
<lrml:Context key="context_3" type="rioOnto:constitutiveRule">
<lrml:Context key="context_4" type="rioOnto:constitutiveRule4MappingWithPrOnto">
```

**[计数]** 每个 context 内的 `inScope` 引用数，以及与该 context 语义的吻合度：

| context | type | `inScope` 引用数 | 论文对应口径 |
|---|---|---|---|
| `context_1` | `rioOnto:obligationRule` | **271** | 论文「271 obligations」——**精确一致** |
| `context_2` | `rioOnto:permissionRule` | **76** | 论文「76 permissions」——**精确一致** |
| `context_3` | `rioOnto:constitutiveRule` | **491** | context_3 + context_4 合计 **615** |
| `context_4` | `rioOnto:constitutiveRule4MappingWithPrOnto` | **124** | 论文「619 constitutive rules」——**差 4 条** |
| **合计** | 4 个 context | **962** | 论文「966 formulas」——**差 4 条** |

**[原文]** 论文的权威口径（逐字）：

> "The current version of the DAPRECO knowledge base includes **966 formulas in reified Input/Output logic: 271 obligations, 76 permissions, and 619 constitutive rules.**"

**[判断]** 这里出现一个**可复现的、精确到 4 条的差异**，如实报告：论文说 966 条公式（271 + 76 + 619），而本体里带 `inScope` 引用的规则共 **962** 条（271 + 76 + 615）。**义务数与许可数与论文精确吻合**，差异全部落在 constitutive 规则上（本体 615 vs 论文 619）。合理解释是论文对本体某一版本的描述，或 4 条 constitutive 规则未被纳入任何 context。**我不为这个差异编造原因**；它的价值恰恰在于**它是一个可复算的差异**——委托方若要复核，跑一次计数即可。这也说明一件事：**连论文与其自身交付物之间都会差 4 条，任何「规则库自查」都必须以工件计数为准。**

**[计数交叉验证]** 三个独立计数指向同一个数，互为验证：

- `<lrml:ConstitutiveStatement` 开标签 = **962**
- `<ruleml:Rule closure="universal"` = **962**
- `<lrml:inScope` 引用 = **962**

**（二）规则本体侧：deontic 算子写在公式里，作用域写在容器上**

**[计数]** 机器可读的原子公式关系（`<ruleml:Rel iri="..." />`）共 **14,998** 个，涉及 **276** 种关系。deontic 与时间相关的前几位：

| 关系 | 出现次数 | 说明 |
|---|---|---|
| `rioOnto:RexistAtTime` | **1,276** | 时间存在谓词——**DAPRECO 真正的时间机制** |
| `rioOnto:not` | **543** | 经典否定，用来表达「禁止」 |
| `rioOnto:Obliged` | **319** | 义务算子 |
| `rioOnto:Permitted` | **90** | 许可算子 |

**[方法学更正，重要]** 一个容易踩的坑：字符串 `rioOnto:Obliged` 在该文件里出现 **638** 次，但**其中 319 次位于 XML 注释内**——注释是每条公式的人类可读渲染（`(rioOnto:Obliged :a2 :t1 :y) & ...`），**不是机器可读内容**。剥离注释后恰好是 **319** 次，即真实的算子使用次数。**用「字符串出现次数」计数会得到恰好 2 倍的错误结果。** 本文所有计数均已剥离注释后重算（`rioOnto:Permitted` 同理：原始 180 → 实际 90；`rioOnto:not`：原始 1,086 → 实际 543）。

**[更正]** 另一处需要驳回的二手说法：有转述称「DAPRECO 的显式时间项是强制的，**所有公式都带 t ≥ 2018-05-25**」。**该说法在本工件上不成立**：`2018-05-25` 在整个 5.6 MB 文件里**只出现 1 次**，且位于

```
<lrml:Prefix pre="GDPR" refID="/akn/eu/act/regulation/2018-05-25/eng@2018-05-25/!main#" />
```

——这是**被形式化的 GDPR 文本版本标识符**（Akoma Ntoso 的 FRBR URI），属于文档级元数据，**不是逐条公式的时间戳**。DAPRECO 的时间处理靠的是 `rioOnto:RexistAtTime` 谓词（1,276 次）把事实与规则挂在时间点上。**本文不采信「所有公式带 t ≥ 某日」的说法。**

**（三）DAPRECO 只用了 LegalRuleML 的一个子集**

**[计数]** LegalRuleML 在 §9.1 里展示的作用域边，DAPRECO **实际使用情况**：

| LegalRuleML 边 | DAPRECO 中的出现次数 | 说明 |
|---|---|---|
| `lrml:inScope` | **962** | 大量使用——作用域容器机制是核心 |
| `lrml:toTarget` | **7,344** | 大量使用——公式级引用 |
| `lrml:appliesSource` | **275** | 使用（`lrml:Association` 共 277 个） |
| `lrml:appliesStrength` | **0** | **未使用** |
| `lrml:appliesTemporalCharacteristics` | **0** | **未使用** |
| `lrml:appliesModality` | **1** | 基本未使用 |

**[判断]** 这是一个**必须如实交代的限定条件**，否则会高估证据：**DAPRECO 复用的是 LegalRuleML 的「作用域容器」机制（`Context` + `inScope`），而不是它的「规则强度 / 模态 / 时间特征」那套边。** 因此 §9.1 用 LegalRuleML 规范文本论证「作用域是边不是列」依然成立（那是规范层面的证据），但**不能说 DAPRECO 的实现验证了 `appliesStrength` 等边**——它没有用。这也从反面支持 §1 结论 1 的后半句：**这些边的价值在于「可以按需只用其中一部分」，而字段做不到这一点**——字段一旦加进表里就必须每一行都填。

**[判断]** DAPRECO 对 §1 结论 1 的贡献是**量化**的：**966 条规则（含 962 条带作用域引用），作用域侧只用了 4 个容器。** 如果作用域是「列」，那就得在 962 行上分别写入；DAPRECO 的做法是**四个可复用的引用集合**。这就是「边 vs 列」在真实法律知识库上的规模差异。

**[判断]** 还有一点与 §1 结论 2 咬合：**DAPRECO 的四个 context 本身就是一份显式的兜底声明**——每条规则被**明确指派**到某个 context；`type` 属性写明了它属于义务规则、许可规则还是构成性规则。**没有一条规则的适用性是「不写就默认」的。** 这与 §1 结论 2 的其余各例（Cedar / OPA / DMN / ODRL / DPV / SPECIAL）并列，而且是其中**唯一的法律领域**实例。

---

#### 9.2.10 SPECIAL 的自我限定：**义务与「同意请求」被显式拆出去**

§9.2.6 说 SPECIAL 的五元组「看起来最像四维笛卡尔积」。读完它自己的边界声明后，这个印象需要收紧。SPECIAL D2.1《Policy Language V1》用一整节写明**本 deliverable 不做什么**。

**[原文]**（D2.1 第 1 章 "What is not in this deliverable"，逐字）：

> "Here we **do not deal with the languages for describing business policies and processes**, that are needed to check compliance w.r.t. the GDPR. **This is the subject of another deliverable (D2.2). In particular, obligations will be dealt with there.**"
>
> "Similarly, we **do not (yet) deal with any issue related to consent requests, such as splitting the policy into mandatory and optional parts, and specifying whether the default selection modality is opt-in or opt-out.**"
>
> "In both cases (business policies and consent requests) the usage descriptions described in this deliverable will be part of the specification. Following an **incremental design strategy**, usage policies will be extended with suitable attributes to encode obligations, opt-in/out policies and any further elements needed in those contexts."

**[原文]** D2.1 §2.1「所有属性都是 functional 的」（逐字）：

> "**SPECIAL's usage policy namespace and semantics: All policy attributes are functional**, e.g. **every single authorization in a policy has one data element, one purpose element, one processing element etc.**"

**[工件原文]** 附录 1 的 OWL 2 公理（逐字，摘录）：

```
# HERE WE SAY:
# 1) THAT ALL PROPERTIES ARE FUNCTIONAL
# 2) WHICH ARE THEIR DOMAIN AND RANGE
FunctionalObjectProperty(spl:hasData)
ObjectPropertyDomain(spl:hasData spl:Authorization)
ObjectPropertyRange(spl:hasData spl:AnyData)
```

**[判断]** 三个限定条件使 SPECIAL **实际上不是**「四维笛卡尔积」，逐条对应 §1 的结论：

1. **每个轴都是 functional：一条授权在每个轴上恰好取一个值。** 所以五元组是**一条授权的坐标**，不是**一条规则的适用范围标签**。二者的区别正是 §1 结论 1 说的「规则本体 vs 作用域」：SPECIAL 的元组描述的是**被授权的那件事**（数据、目的、操作、存储、接收方），而 Momcozy 的四个标签描述的是**规则在哪些情形下生效**。**形态相似，语义不同**——这一点在 §9.2.6 的对照表里已埋下（「元组代表什么」一行）。
2. **义务被显式拆到另一个 deliverable。** 「In particular, obligations will be dealt with there.」即 SPECIAL 把「许可（usage policy）」与「义务（business policy / obligations）」**分开建模**，而不是把 deontic 类型当五元组里的第六个轴。这与 §3（ODRL 的 Permission/Prohibition/Duty 分列）和 §9.2.7（DPV 的 `hasObligation`/`hasPermission` 分开）是同一个设计。
3. **「默认选择模态是 opt-in 还是 opt-out」被显式声明为「本 deliverable 不处理」。** 这一条对本分片特别重要：**连「用户没勾选时算同意还是不同意」这种最典型的默认值问题，SPECIAL 都不肯默认，而是把它列为一个必须单独规定的、被推迟的显式议题。** 这是 §1 结论 2（兜底必须显式声明）在**同意管理**语境下的又一例，而且它给出的处置方式正是我们在 §11.6 建议的：**留成显式的、有名字的缺口，而不是悄悄填一个值。**

**[原文]** D2.2《Formal representation of the legislation V1》§1.3.1 处理时间的方式（逐字）：

> "In addition to analysing the structure of rules, our initial analysis included the **annotation of temporal references, both explicit and implicit references to other articles and paragraphs**, and terms that we deemed subjective.
>
> **1.3.1 Temporal Annotations** — In this section, we examine the different temporal conditions found in the text of the GDPR. A high level overview of the different temporal expressions is presented in Table 1.3. ... At any time, before & prior: Article 7 (Conditions for consent), paragraph 3 uses terms such as **at any time, before and prior to** (see R12)."

D2.2 用一个 `tRef` 交叉引用标注方案来记录显式与隐式的条款引用（工件中可见 `tRef Transparent` 等用法）。**[判断]** 值得注意的是 SPECIAL 把**时间**处理成**标注轴**，而不是把它塞进五元组当第六个轴——再次印证「作用域/适用性信息是独立的边或独立的标注，不是规则本体的字段」。

### 9.3 ODRL（W3C 标准）：Constraint 是「作用域与规则本体分离」的标准答案

规范：`ODRL Information Model 2.2`（W3C Recommendation, 2018-02-15）`https://www.w3.org/TR/odrl-model/`
规范：`ODRL Vocabulary & Expression 2.2`（W3C Recommendation）`https://www.w3.org/TR/odrl-vocab/`
[本地] `raw/odrl-model.html`（182 KB）、`raw/odrl-model.txt`（1,858 行）、`raw/odrl-vocab.html`（245 KB）、`raw/odrl-vocab.txt`（3,317 行）

#### 9.3.1 核心类结构

**[原文]** IM §2 目录（逐字）：

```
2. ODRL Information Model
  2.1 Policy Class (2.1.1 Set Class / 2.1.2 Offer Class / 2.1.3 Agreement Class)
  2.2 Asset Class
  2.3 Party Class
  2.4 Action Class
  2.5 Constraints (2.5.1 Constraint Class / 2.5.2 Logical Constraint Class /
       2.5.3 Constraint property with a Rule / 2.5.4 Refinement property with an Action /
       2.5.5 Refinement property with an Asset Collection / 2.5.6 Refinement property with a Party Collection)
  2.6 Rule Class (2.6.1 Permission Class / 2.6.2 Prohibition Class / 2.6.3 Duty Class /
       2.6.4 Obligation property with a Policy / 2.6.5 Duty property with a Permission /
       2.6.6 Consequence property with a Permission/Obligation Duty / 2.6.7 Remedy property with a Prohibition)
  2.7 Policy Rule Composition
  2.8 Policy Metadata
  2.9 Policy Inheritance
  2.10 Policy Conflict Strategy
```

**[原文]** §2.6 Rule Class（逐字）：

> "The Rule class is the parent of the Permission, Prohibition, and Duty classes. The Rule class represents the common characteristics of these three classes. **A Rule class MUST be disjoint with all other Rule subclasses.**
>
> The Rule class has the following properties:
>
> * A Rule MUST have one `action` property value of type Action.
> * A Rule MAY have none or one `relation` sub-property values of type Asset.
> * A Rule MAY have none, one or many `function` sub-property values of type Party.
> * A Rule MAY have none, one or many `failure` sub-property values of type Rule.
> * A Rule MAY have none, one or many `constraint` property values of type Constraint/LogicalConstraint.
> * A Rule MAY have none or one `uid` property values (of type IRI [rfc3987]) **to identify the Rule so it MAY be referenced by other Rules.**"

**[原文]** §2.6.1 Permission / §2.6.2 Prohibition（逐字）：

> "A **Permission** allows an action, with all refinements satisfied, to be exercised on an Asset if all constraints are satisfied and if all duties are fulfilled."
>
> "A **Prohibition** disallows an action, with all refinements satisfied, to be exercised on an Asset if all constraints are satisfied. **If the Prohibition has been infringed by the action being exercised, then all of the remedies MUST be fulfilled to set the state of the Prohibition to not infringed.**"

#### 9.3.2 Constraint：四元组 + 两处挂载点 + 三种 refinement

**[原文]** §2.5.1 Constraint Class（逐字）：

> "A Constraint class is used for expressions which compare two operands (which are not Constraints) by one relational operator. **If the comparison returns a match the Constraint is satisfied, otherwise it is not satisfied.** The Constraint class formulates a comparison expression, such as, the number of usages (the `leftOperand`) must be smaller than (the `operator`) the number 10 (the `rightOperand`)."

> "A Constraint MUST have one `leftOperand` property value of type LeftOperand."

> "The `leftOperand` property values are defined as instances of the `LeftOperand` class. The `leftOperand` instances MUST clearly be defined to indicate the semantics of the Constraint, and MAY declare how the value for comparison has to be retrieved or generated. The ODRL Common Vocabulary [odrl-vocab] defines `leftOperand`'s that MAY be used by **ODRL Profiles**."

> "The `rightOperand` property values are defined as instances of the `RightOperand` class, or IRIs, or Literal values. The `rightOperand` is the value of the Constraint that is to be compared to the `leftOperand`. The `rightOperandReference` represents an IRI that MUST be de-referenced first to obtain the actual value of the `rightOperand`. ... Only one of `rightOperand` or `rightOperandReference` MUST appear in the Constraint."

> "The `status` provides a value generated from the `leftOperand` action that MUST be used in the comparison expression. For example, a count constraint could have a `rightOperand` value of 10, and the `status` of 5. This means that **the action has already been exercised 5 times and the comparison must compare the current action to the status value.**"

**[判断]** **Constraint 是一个严格四元组：`leftOperand`（比什么）+ `operator`（怎么比）+ `rightOperand`（比到什么）+ `status`（已经到哪了）。** 映射到 Momcozy：

| ODRL | Momcozy 对应 |
|---|---|
| `leftOperand` | 检测目标维度（例如「文案中出现的功效声称」） |
| `operator` | 判定方式（包含 / 正则匹配 / 大于 / 属于集合） |
| `rightOperand` | 具体的关键词集合、正则、阈值 |
| `status` | 历史累计（例如「该账号本月已被警告次数」） |

**现状**：Momcozy 的 `检测关键词` / `正则表达式` / `判定方式` 三个字段，合起来正好是 `leftOperand + operator + rightOperand` 的**退化版**（`leftOperand` 隐式固定为「文本内容」）。缺 `status`（历史状态），也缺「`rightOperand` 可以是一个引用」的能力（例如「阈值放在另一处，由多国共用」）。[判断]

#### 9.3.3 两处挂载点：Rule 上的 `constraint` vs Action/Asset/Party 上的 `refinement`

**[原文]** §2.5.3（逐字）：

> "An Rule (such as a Permission, Prohibition, or Duty) MAY include the `constraint` property to indicate a condition on the Rule.
>
> To meet this condition, all of the the Constraints/Logical Constraints referenced by the `constraint` property MUST be satisfied."

**[原文]** §2.5.4 Refinement property with an Action（逐字）：

> "An Action MAY include the `refinement` property to indicate a Constraint/Logical Constraint that **narrows the semantics of the Action operation directly.**
>
> To meet this condition of narrower semantics for the Action, all of the Constraints/Logical Constraints referenced by the `refinement` property MUST be used as generating a satisfied state."

**[原文]** §2.5.5 Refinement property with an Asset Collection（逐字）：

> "An AssetCollection MAY include a `refinement` property to indicate the refinement context under which to identify individual Asset(s) of the complete collection. **The refinement property applies to the characteristics of each member of the collection (and not the resource as a whole).**"

> "Note that when using the `refinement` property, the `uid` property MUST NOT be used to identify the AssetCollection. Instead, the `source` property MUST be used to reference the AssetCollection."

**[原文]** §2.5.6 Refinement property with a Party Collection（逐字）：

> "A PartyCollection MAY include a `refinement` property to indicate the refinement context under which to identify individual Party(ies) of the complete collection. The refinement property applies to the characteristics of each member of the collection (and not the resource as a whole)."

**[判断]** 这是 ODRL 最精妙的设计：**同一个 `Constraint` 类，可以挂在四个不同的位置，且位置本身携带语义**：

| 挂载点 | 语义 | 例子 |
|---|---|---|
| **Rule 上的 `constraint`** | 「这条规则**何时**成立」 | 许可在 2018-01-01 前有效 |
| **Action 上的 `refinement`** | 「这个**行为**的更窄定义」 | 「打印」特指 ≤1200 dpi 的打印 |
| **AssetCollection 上的 `refinement`** | 「这批**客体**里的哪些成员」 | 视频目录里时长 < 60 分钟的那些 |
| **PartyCollection 上的 `refinement`** | 「这批**主体**里的哪些成员」 | 「朋友」集合里 age > 17 的那些 |

**[判断]** **这就是「作用域与规则本体分离」的标准答案。** 一条规则（Rule）说的是「许可/禁止做 Action 于 Asset」，而「谁（Party）」「什么（Action 的定义）」「何物（Asset 集合的成员）」「何时（Constraint）」全部是**独立的、可复用的、可组合的**对象。**国家 / 品类 / 平台 / 内容类型这四个维度，在 ODRL 的框架下分别落在 `PartyCollection.refinement`（主体：团队/站点）、`AssetCollection.refinement`（客体：哪个产品线）、`Action.refinement`（行为：发在哪个平台、什么形式的内容）、`Rule.constraint`（条件：何时、何地）。** 它们**不是规则的列，是四个独立对象的 refinement**。[判断]

#### 9.3.4 Constraint Operators 完整清单（ODRL Vocabulary §3.16，逐字）

| 编号 | 名称 | Definition（逐字） | Identifier |
|---|---|---|---|
| 3.16.1 | Equal to | "Indicating that a given value **equals** the right operand of the Constraint." | `odrl:eq` |
| 3.16.2 | Greater than | "Indicating that a given value is **greater than** the right operand of the Constraint." | `odrl:gt` |
| 3.16.3 | Greater than or equal to | "Indicating that a given value is **greater than or equal to** the right operand of the Constraint." | `odrl:gteq` |
| 3.16.4 | Less than | "Indicating that a given value is **less than** the right operand of the Constraint." | `odrl:lt` |
| 3.16.5 | Less than or equal to | "Indicating that a given value is **less than or equal to** the right operand of the Constraint." | `odrl:lteq` |
| 3.16.6 | Not equal to | "Indicating that a given value is **not equal to** the right operand of the Constraint." | `odrl:neq` |
| 3.16.7 | Is a | "A set-based operator indicating that a given value is an **instance of** the right operand of the Constraint." | `odrl:isA` |
| 3.16.8 | Has part | "A set-based operator indicating that a given value **contains** the right operand of the Constraint." | `odrl:hasPart` |
| 3.16.9 | Is part of | "A set-based operator indicating that a given value is **contained by** the right operand of the Constraint." | `odrl:isPartOf` |
| 3.16.10 | Is all of | "A set-based operator indicating that a given value is **all of** the right operand of the Constraint." | `odrl:isAllOf` |
| 3.16.11 | Is any of | "A set-based operator indicating that a given value is **any of** the right operand of the Constraint." | `odrl:isAnyOf` |
| 3.16.12 | Is none of | "A set-based operator indicating that a given value is **none of** the right operand of the Constraint." | `odrl:isNoneOf` |

> — `https://www.w3.org/TR/odrl-vocab/#constraintOperators`，[本地] `raw/odrl-vocab.txt` 第 1139–1235 行

#### 9.3.5 Logical Constraint Operands（ODRL Vocabulary §3.17，逐字）

| 编号 | 名称 | Definition（逐字） | Identifier |
|---|---|---|---|
| 3.17.1 | Or | "The relation is satisfied when **at least one** of the Constraints is satisfied." | `odrl:or` |
| 3.17.2 | Only One | "The relation is satisfied when **only one, and not more**, of the Constaints is satisfied" | `odrl:xone` |
| 3.17.3 | And | "The relation is satisfied when **all** of the Constraints are satisfied." | `odrl:and` |
| 3.17.4 | And Sequence | "The relation is satisfied when **each of the Constraints are satisfied in the order specified**." | `odrl:andSequence` |

**[原文]** `andSequence` 的 Note 里有一段罕见的标准级风险提示（逐字）：

> "The order of the list MUST be preserved. The andSequence operator is an example where there may be temporal conditional requirements between the operands. **This may lead to situations where the outcome is unresolvable, such as deadlock if one of the Constraints is unable to be satisfied.** ODRL Processing systems SHOULD plan for these scenarios and implement mechanisms to resolve them."

**[原文]** 所有 Logical Constraint 的 Note（逐字，适用于 or / xone / and / andSequence）：

> "This property MUST only be used for Logical Constraints, and the list of operand values MUST be Constraint instances."

**[判断]** `xone`（有且仅有一个满足）在 Momcozy 场景里有直接用途：**「同一素材只能投放在 Google 或 Meta 之一，不能同时在两处用不同话术」**这类互斥约束。更一般地，`xone` 是「多命中必须收敛到唯一结论」的形式化，与 DMN 的 `U`（Unique）语义相通。[判断]

#### 9.3.6 Policy Conflict Strategy（ODRL IM §2.10，逐字）

**[原文]**：

> "The `conflict` property is used to establish strategies to resolve conflicts that arise from the merging of Policies or conflicts between Permissions and Prohibitions in the same Policy. **Conflicts may arise when merging Policies as a result of Policy Inheritance and the resultant Rules are inconsistent.**
>
> The `conflict` property SHOULD take one of the following Conflict Strategy Preference values (instance of the ConflictTerm class):
>
> * **`perm`**: the Permissions MUST override the Prohibitions
> * **`prohibit`**: the Prohibitions MUST override the Permissions
> * **`invalid`**: **the entire Policy MUST be void if any conflict is detected**
>
> **If the `conflict` property is not explicitly set, the default of `invalid` will be used.** Additional `conflict` property values MAY be defined by ODRL Profiles.
>
> The Conflict Strategy requirements include:
>
> * If a Policy has the `conflict` property of `perm` then any conflicting Permission Rule MUST override the Prohibition Rule.
> * If a Policy has the `conflict` property of `prohibit` then any conflicting Prohibition Rule MUST override the Permission Rule.
> * If a Policy has the `conflict` property of `invalid` then any conflicting Rules MUST void the entire Policy.
> * **If a Policy has multiple `conflict` property values (for example, after a Policy merge or inheritance) and there are conflicting Rules then the entire Policy MUST be void.**"

**[原文]** vocab §3.18 的定义与 Note（逐字）：

> "**Conflict Strategy Preference** — Definition: Used to establish strategies to resolve conflicts that arise from the merging of Policies or conflicts between Permissions and Prohibitions in the same Policy. ... Note: Instances of ConflictTerm describe strategies for resolving conflicts."
> "**Handle Policy Conflicts** — Definition: The conflict-resolution strategy for a Policy. ... Note: **If no strategy is specified, the default is `invalid`.**"
> "**Prefer Permissions** — Definition: Permissions take preference over prohibitions. ... Note: Used to determine policy conflict outcomes."
> "**Prefer Prohibitions** — Definition: Prohibitions take preference over permissions. ... Note: Used to determine policy conflict outcomes."
> "**Void Policy** — Definition: The policy is void. ... Note: Used to indicate the policy is void for Conflict Strategy."

**[判断]** **ODRL 的默认值是三者中最严的：冲突即整份 Policy 作废。** 对比：

| 体系 | 冲突默认行为 |
|---|---|
| Cedar | 硬编码 `forbid overrides permit`（禁止优先） |
| XACML | 无默认，必须显式指定 combining algorithm |
| ODRL | 默认 `invalid`：**整份策略作废** |
| DMN | 默认 `UNIQUE`，且**禁止重叠**（重叠即设计错误） |
| OPA | `complete definition` 多值 → **直接报错** |
| Drools | `salience` 高者先，同 salience 时顺序不确定 |

**六个体系，零个选择「静默挑一条」。** 这是本分片最强的跨体系一致结论。[判断]

#### 9.3.7 Policy Inheritance 与合并时的冲突

**[原文]** §2.9（逐字，给出继承的复制清单）：

> "The ODRL validation requirements for ODRL Policy Inheritance includes:
>
> The child Policy MUST access the parent Policy and replicate the following in the updated child Policy:
> * All policy-level Assets, Parties, Actions from the parent Policy.
> * All `profile` identifiers.
> * Any `conflict` properties
> * All Rules from the parent Policy.
>
> Repeat the above for each identified parent Policy."

**[判断]** 「继承时 `conflict` 属性也必须被继承」是一条容易漏的规则——**如果子策略用不同方式解冲突，父策略的冲突语义就失效了**。对应到 Momcozy：如果「平台规则集」继承「品牌规则集」，那么品牌规则集声明的冲突策略（例如「法规优先」）必须一并继承，不能被平台层静默覆盖。[判断]

### 9.4 许可证的机器可读化：Creative Commons 对照

**[原文]** CC 的 RDF 命名空间（`https://creativecommons.org/ns`，[本地] `raw/cc-rights.html`）声明了 `cc:Permission` / `cc:Prohibition` / `cc:Requirement` / `cc:license` / `cc:morePermissions` / `cc:useGuidelines` 等类与属性。

**[判断]** CC 的 rights expression 与 ODRL 的关系是：**CC 是 ODRL 的一个 Profile**（即用 ODRL 的 Permission/Prohibition/Duty 表达 CC 的四种要素）。本次**未取得 W3C 或 CC 官方的「CC 作为 ODRL Profile」规范性文档**，因此**不对该关系做断言**。记为缺口。

---

## 10. 交叉问题（必须回答）

### 10.1 「规则本体」与「适用范围」是分开建模还是合并？

**结论：在我核查的 7 个体系里，7 个都是分开的；零个是合并的。** 下面给出 5 个体系的直接证据（要求是至少 3 个）。

---

#### 证据 1：LegalRuleML — 章节分开 + `applies*` 边

- **结构证据**：§4.2 是 "Modeling Legal Norms"（规则本体），§4.3 是 "Metadata of the LegalRuleML Specifications"（作用域元数据）。两个独立章节。（[本地] `raw/legalruleml-core-spec.txt` 第 270–299 行）
- **机制证据**：作用域通过 `Context` / `Association` 的 `applies*` 边挂接，边元素清单包括 `appliesAuthority`、`appliesJurisdiction`、`appliesStrength`、`appliesTemporalCharacteristics`、`appliesModality`、`appliesSource`（§3.6）。
- **动机证据**（逐字）："`<lrml:Context>` localizes the strength of a rule, while the `<lrml:hasStrength>` block in effect relates the strength to the rule in all contexts."（§4.2.1）——**同一个属性可以有两种作用域，这在「合并建模」下不可能表达。**

#### 证据 2：ODRL — Constraint 是独立类，可挂在 4 个不同位置

- **结构证据**：IM §2 把 `Policy` / `Asset` / `Party` / `Action` / `Constraint` / `Rule` 列为**并列的顶层类**（§2.1–2.6）。
- **机制证据**：同一个 `Constraint` 类型可挂为 `Rule.constraint`、`Action.refinement`、`AssetCollection.refinement`、`PartyCollection.refinement`（§2.5.3–2.5.6），**挂载位置本身携带语义**。
- **动机证据**（逐字）："The refinement property applies to the characteristics of each member of the collection (and not the resource as a whole)."（§2.5.5）
- **可复用性证据**：Constraint 有自己的 `uid`，可以被多处引用（IM Example 15 里 `xone` 引用两个具名 Constraint `http://example.com/p:88/C1` / `C2`）。

#### 证据 3：Cedar — `effect` / `scope` / `conditions` 三分，且 `scope` 强制必填

- **结构证据**（逐字）："A policy is a text document that includes the following elements: **Effect** ... **Scope** – The scope specifies the combination of principals, actions, and resources to which the policy applies. **Inclusion of these elements is mandatory.** **Conditions** – (Optional) ... **Annotations** – (Optional) ... An annotation has no impact on policy evaluation."
- **形式化证据**：Cedar 论文的语法（Fig. 5）把三者写成不同的非终结符：
  ```
  Policy ::= Effect { Scope } { Cond } ;
  Effect ::= permit | forbid
  Scope  ::= Principal · Action · Resource
  ```
  （[本地] `raw/cedar-oopsla.pdftxt`）
- **作用域可独立查询的证据**：论文 §3.3 的 `authorize` 伪码第 3 行先用 `slice(𝒫, q)` 按 scope 切出相关策略，再逐条求出 condition。**scope 是索引层，condition 是求值层。**

#### 证据 4：Akoma Ntoso — 文本层级与「元数据」分层

- **结构证据**：`<meta>` 块承载 FRBR（Work/Expression/Manifestation/Item）、`identification`、`classification`、`analysis`、`references`、`proprietary` 等，**与 `<body>` 的实际条文完全分离**。"Akoma Ntoso makes careful use of the FRBR hierarchy"（[本地] 第 3602 行）。
- **作用域层级证据**：`hierarchy` 允许 `hcontainer` 在任意深度插入自定义层级（§4.1.5.1）——**适用范围是层级结构，不是扁平列。**

#### 证据 5：OpenFisca — 参数与公式分离，且都按日期版本化

- **结构证据**：`Variable`（含 `formula`）与 `Parameter`（YAML 树）是两类不同的对象，存放在不同位置（`variables/` 与 `parameters/`）。
- **机制证据**：公式用 `parameters(period).taxes.salary.rate` 读取参数——**规则逻辑里不写数值，数值在别处**。数值改动不需要动公式（"Many legislation parameters are regularly re-evaluated while the variables using them stay the same"）。

#### 证据 6：DPV（W3C CG Final Report）—— 辖区是**命名空间**，不是字段

- **结构证据**：DPV 的 core concepts（Purpose / PersonalData / LegalBasis / …）被定义为 **"independent representations of specific information, and are distinct from other core concepts"**。
- **机制证据**（逐字）："**Legal Jurisdiction-relevant concepts for DPV ([LEGAL])** provides concepts to represent laws, authorities, and other legal concepts in various jurisdictions. **It is structured to create a separate namespace for each country or jurisdiction by using the ISO 3166-2 code** ... **Within this namespace, the specific laws and authorities for that jurisdiction are defined.**"
- **结论性证据**（逐字）："**Laws are modelled as extensions within the namespace of their respective jurisdictions.**"
- **「不可判定」独立取值的证据**：`dpv:NotApplicable` / `dpv:NotAvailable` / `dpv:UnknownApplicability` 三个独立概念（DPV Context 模块 §5）。

**[判断]** 这是 6 个体系里**最强的反笛卡尔积证据**：一个国家级标准组织在处理「同一概念在 N 个国家有 N 套规定」这个**与 Momcozy 完全相同**的问题时，选择的方案是**命名空间隔离**，而不是给概念加一个 `jurisdiction` 字段。

#### 证据 7：DMN —— 输入列是**变量**，不是维度取值

- **结构证据**：`DecisionTable` 的元模型是 `input: InputClause[]` / `output: OutputClause[]` / `rule: DecisionRule[]`（Table 32）。`InputClause` 持有的是**输入表达式**（"Input expressions are usually simple, for example, a name (e.g. CustomerStatus) or a test (e.g. Age<25)"），不是某个维度的枚举值。
- **判断证据**：`'-'` 输入项表示 "**the input is irrelevant for the containing rule**"——**「不关心这个维度」是一条规则可以显式表达的状态**。在笛卡尔积模型里，「不关心」和「关心且等于某值」无法区分。

#### 反例检查

**[判断]** 我特意找了「合并建模」的反例，找到的最接近的是 **Drools 的 DRL**：`salience`、`date-effective`、`date-expires`、`activation-group` 都是**写在规则头部的属性**，形式上确实是「规则行上的列」。但即使在这里，Drools 也区分了：
- **规则头属性**（`salience` 等）：作用域**只在本规则内**生效；
- **`agenda-group` / `ruleflow-group`**：作用域**跨规则**，是规则集层面的分组。

也就是：**即使在最「合并」的实现里，也保留了「单规则属性」与「跨规则分组」两个层级。** 这反而证明了纯合并建模是不够用的。

---

### 10.2 兜底语义（default / fallback / catch-all）在各体系里怎么表达？

| 体系 | 兜底机制 | 兜底值 | 「不写会怎样」 |
|---|---|---|---|
| **OPA/Rego** | `default <name> := <term>` | 作者指定（惯例 `false`） | 结论是 **`undefined`（第三态）** |
| **Cedar** | 硬编码 | `Deny`（implicit deny） | 无法不写（always deny by default） |
| **XACML** | combining algorithm `Deny-unless-permit` / `Permit-unless-deny` | 作者指定 | 必须显式指定算法 |
| **ODRL** | `conflict` 属性 | 默认 `invalid`（整份 Policy 作废） | 冲突即作废 |
| **DMN** | `hitPolicy` + `default output values`（下划线标注） | 默认 `UNIQUE`；默认输出值在输出值列表里**加下划线** | `UNIQUE` 下重叠即设计错误 |
| **Drools** | `<rule>` 的"最后一条兜底规则" | 无内建 | 无结论 |
| **OpenFisca** | `formula`（无日期后缀）= 从无穷早生效 | 无 | 查询报 `ParameterNotFoundError` |
| **LegalRuleML** | `DefeasibleStrength` 默认强度 | 可被推翻 | 无 |
| **CEL** | 无（表达式必求值） | 无 | `has()` 显式检查存在性 |

**[判断]** **「为什么几乎所有体系都要求兜底显式声明而不是隐式默认」——三个理由，每个都有原文支撑：**

**理由 1：隐式默认让「没命中」与「命中且为否」不可区分。**
[原文] OPA："Without the default definition, the `allow` document would be **undefined** for the same input."（§5.1.2）
这意味着不写 `default` 时，`allow` 是 `undefined`，而不是 `false`。这两个值在下游行为可能完全不同（比如 HTTP 层把 undefined 当 500，把 false 当 403）。

**理由 2：隐式默认会给「反向规则」造成 fail-open。**
[原文] OPA Style Guide："Saying `deny` is undefined or `deny` is false if undefined is encountered, essentially means that any occurrence of undefined (such as when attributes are missing in the input document) would lead to **the deny rule not getting enforced**. ... the rule allows someone without a `user_id`."（§5.1.3）

**理由 3：隐式默认会让「读者无法独立理解一条规则」。**
[原文] Cedar："Since `permit` policies are the only way access is granted, readers just have to understand what each policy says, **not what it doesn't**. Because `forbid` policies always deny access, readers can understand them independently of any `permit` policies created now or in the future."（§5.2.2）
如果兜底是隐式的（例如「默认放行」），那么要理解「这条红线规则意味着什么」，读者必须同时知道**所有其他规则的存在**——规则的局部可读性丧失。

**理由 4（补充）：兜底方向本身是一个业务决策，不该由框架替用户决定。**
[原文] XACML 把 `Deny-unless-permit` 与 `Permit-unless-deny` 都做成可选算法（§5.3.2），而不是硬编码一个。**这等于说：默认拒绝还是默认放行，是规则集作者的判断，标准不做选择。**

**[判断]** **对 Momcozy 的直接推论**：他们的 21 条规则里**没有任何一条兜底规则**，`判断方式` 全填「自动可检测」隐含了「21 条覆盖全部」。在这个前提下，实现层面对「未命中」的处理（放行？转人工？）就变成了**实现细节而非规则**。这正是 `cross-cutting-findings.md` 里「兜底路径比主路径更宽松」这条反模式的温床。

---

### 10.3 规则的唯一标识如何设计才能既稳定又可读？

**结论：需要三个 ID，不是一个。**

| ID | 稳定性 | 可读性 | 职责 | 标准依据 |
|---|---|---|---|---|
| **`rule_key`**（WORK 层） | **永不变** | 高（人可读） | 被其他规则引用、被审查记录引用、被报表聚合 | Akoma Ntoso FRBR WORK + `MEANINGFULNESS`/`PERMANENCE`/`INVARIANCE` |
| **`revision_id`**（EXPRESSION 层） | 每次实质修改都变 | 中 | 历史判定复现、快照、diff | Akoma Ntoso FRBR EXPRESSION + `eId`/`wId` |
| **`guid`** | 永不变、永不复用 | 无 | 内部主键、防重命名碰撞 | Akoma Ntoso `GUID`；Cedar "Always use identifiers that are guaranteed unique and never reused" |

**反对「只用一个可读 ID」的原文证据：**

[原文] Cedar（Syntax → Basic policy construction）：
> "This guide includes examples that use simple entity identifiers, such as `jane` or `bob` for the name of an entity of type `User`. This is done to make the examples more readable. However, **in a production system it is critical for security reasons that you use unique values that can't be reused.** We recommend that you use values like universally unique identifiers (UUIDs). For example, if user `jane` leaves the company, and you later let someone else use the name `jane`, then that new user automatically gets access to everything granted by policies that still reference `User::\"jane\"`. **Cedar can't distinguish between the new user and the old.**"

[判断] 同样的逻辑适用于规则 ID：如果 `H01` 被停用后，编号被回收给一条新规则，那么所有历史审查记录里引用 `H01` 的条目都会指向错误的规则。**「永不复用」是一条硬约束。**

**反对「只用一个 UUID」的原文证据：**

[原文] OPA Style Guide 给出的做法是**在可读编码旁边附 UUID 注释**：
> ```
> # E123: Deny non admin users.
> # Only admin users are allowed to access these resources, see https://docs.example.com/policy/rule/E123
> deny contains {
>   "code": 401,
>   "message": "Unauthorized due to policy rule (E123, https://docs.example.com/policy/rule/E123)",
> } if {
>   input.admin == false
> }
> ```
> 以及 METADATA 块：
> ```
> # METADATA
> # title: Deny non admin users
> # description: Only admin users are allowed to access these resources
> # related_resources:
> # - https://docs.example.com/policy/rule/E123
> # custom:
> #   error_id: E123
> ```

[判断] 注意 `E123` 这个编码被用在**三处**：规则注释、错误消息返回给调用方、METADATA 里作为 `error_id`。**可读编码的价值在于它能出现在面向人的输出里**（错误消息、审查报告、工单标题）。UUID 做不到这一点。

**可读编码的编制建议（综合三条原则）：**

[判断] 把 Akoma Ntoso 的三条原则落到编码设计上：

| 原则 | 编码含义 | 反例 |
|---|---|---|
| `MEANINGFULNESS` | 编码应表达**规则属于哪个族/哪个作用域**，而不是「第几条」 | ✗ `RULE-2026-09-15-001`（含创建日期，无语义） |
| `PERMANENCE` | 一旦分配**永不改变、永不复用** | ✗ 把 `H05` 改成 `H12`（历史引用断裂） |
| `INVARIANCE` | 从**不变属性**导出（规则的性质），不从事务性属性（创建时间、创建人、序号）导出 | ✗ 编号里嵌入「第几批导入」 |

**[判断]** Momcozy 现有的 `H01–H09 / M01–M07 / U01–U04 / 安全词` 编码族**基本满足前两条**（族前缀表达严重度档位，序号单调）。问题在于：

1. **族前缀表达的是「风险等级」而不是「modality」**——`H`（严格限制红线）与 `M`（审慎关注）的差别是**严重度**，不是**禁止 vs 需限定**。按 LegalRuleML/Cedar 的结构，这些应该是两组正交属性：`modality ∈ {prohibition, obligation, permission}` × `severity ∈ {1..N}`。
2. **编码里没有作用域信息**。当规则从「全球通用」变成「仅法国适用」再变成「欧盟适用」时，`H01` 的语义变了但编码不变——**违反 `INVARIANCE`**（编码不再从不变属性导出）。
3. **缺 revision 层**。

---

## 11. 对 Momcozy 的直接含义

> 现状事实取自 `00-调研任务书.md` 第二节（来自 `PRD/内容治理需求文档.md`），本文不重复调研。

### 11.1 现状 12 字段的逐字段诊断

| # | 现有字段 | 归属层 | 诊断 | 标准依据 |
|---|---|---|---|---|
| 1 | **规则编号** | L4 治理 | **半对**。承担了 WORK 层职责，但缺 EXPRESSION 层与 UUID；且族前缀混了 severity 与 modality | Akoma Ntoso FRBR；Cedar「UUID，永不复用」 |
| 2 | **边界类型** | L1 本体 | **对，但语义不纯**。四档 `严格限制红线 / 审慎关注 / 人工复核 / 安全词白名单` 混合了 **modality**（禁止 / 需限定 / 需人工 / 许可）与 **严重度**。应拆为 `modality` + `severity` + `disposition` 三个字段 | LegalRuleML `[OBL]/[PER]/[FOR]`；Cedar `effect ∈ {permit, forbid}` |
| 3 | **适用产品** | **L2 作用域** | **错的位置 + 错的值**。位置错：作用域不应是规则行的一列；值错：21 条全部写死 `W1、M5、M6、M9、Air1` | ODRL `AssetCollection.refinement`；LegalRuleML `appliesJurisdiction` |
| 4 | **风险等级** | L1/L4 | **语义重叠**。与 `边界类型` 的四档一一对应（高危/审慎/待复核/合规 ↔ 红线/审慎/人工/白名单），是同一信息的两次编码 | DMN：输出值应在 `outputValues` 列表里定义，不在输入侧 |
| 5 | **检测关键词** | **L3 约束** | **位置错**。属实现细节，应与正则合并为「检测器」对象 | ODRL `Constraint.rightOperand` |
| 6 | **边界内容** | L1 本体 | **对，但是自然语言散文**。标准做法要求本体是一个**前件→结论**的精确陈述（Business Rule Statement / PrescriptiveStatement） | Better Rules「Business Rule Statements」；LegalRuleML §4.2.2 |
| 7 | **判断方式** | L3/L4 | **错**。`自动可检测` 是一个**实现断言**，21/21 填同一个值 = 该字段零信息量。标准做法是把它变成 `evaluability ∈ {automatic, assistive, manual_only}` 的**显式取值**，并允许「无法自动判定」 | OpenFisca「Human decisions ... can not be completely automated」；Cedar `error` + skip-on-error |
| 8 | **依据来源** | L4 治理 | **粒度太粗**。自由文本、规则级单值；标准要求 N:M + 细粒度定位 + 命名约定声明 | LegalRuleML §4.3.1 Isomorphism |
| 9 | **启用状态** | L4 治理 | **太弱**。二值布尔无法表达 entry/efficacy/applicability 三轴，无法表达「已批准未生效」「暂停」 | LegalRuleML `TemporalCharacteristic`；Drools `enabled` + `date-effective` + `date-expires` |
| 10 | **正则表达式** | **L3 约束** | **位置错**，同 5 | ODRL `Constraint.operator` + `rightOperand` |
| 11 | **豁免词** | **L3/L2 混淆** | **语义歧义**：「对本条不适用」（作用域）还是「显式许可」（modality）？标准里这是两个不同的东西 | LegalRuleML：「前件条件」 vs `[PER]`（strong permission） |
| 12 | **触发原因** | L4 annotation | **对，位置对**。属 DMN 意义上的 Rule Annotation：不参与判定、只供审计 | DMN §8.2.11.1 Rule Annotation |

**[判断]** 汇总：**12 个字段里，位置正确的只有 3 个（规则编号半对、边界内容、触发原因）**；其余 9 个要么层级放错（5、10、11、3），要么语义重叠（2、4），要么粒度过粗（7、8、9）。

#### 显式的差集：多什么、缺什么

**多的字段（3 个，应当从规则行移出）：**

| 现有字段 | 为什么多 | 应当移到哪 |
|---|---|---|
| `检测关键词` | 是实现细节，属 L3，且不该一条规则一份 | `constraint` / `detector` 表，可被多条规则复用 |
| `正则表达式` | 同上；且它的变更频率远高于规则本体 | 同上，**独立版本化** |
| `豁免词` | 语义未定（作用域 vs 许可），挂在这里无法区分 | 拆成 `exceptions`（作用域）与 `permissions_granted`（许可）两个引用 |

**重复的字段（2 个，应当合并）：**

| 现有字段 | 问题 |
|---|---|
| `风险等级` | 与 `边界类型` 一一对应（高危↔红线、审慎↔审慎关注、待复核↔人工复核、合规↔白名单），是同一信息的两次编码。应保留 `severity` 一个，去掉另一个 |
| `判断方式` | 21/21 同一个值，零信息量；应改造为 `evaluability` 三值枚举 |

**缺的字段（24 个，按层分组）：**

| 层 | 缺失字段 | 为什么必须有 | 来源标准 |
|---|---|---|---|
| L1 本体 | `modality` | 现在「禁止 / 须限定 / 需人工 / 许可」混在 `边界类型` 一列 | LegalRuleML `[FOR]/[OBL]/[PER]`；Cedar `effect` |
| L1 本体 | `modality_strength` | 无法表达「可被推翻的默认」与「不可推翻的红线」 | LegalRuleML `StrictStrength` / `DefeasibleStrength` |
| L1 本体 | `bearer` | 规则没说是「对谁」成立（品牌方？代理商？KOL？） | LegalRuleML `Bearer`（有向算子） |
| L1 本体 | `disposition` | 命中后的处置与严重度不是一回事 | DMN `OutputClause`；XACML `Deny/Permit/Indeterminate` |
| L2 作用域 | `scope_id` | 唯一的作用域入口（替代 `适用产品` 这一列） | ODRL `refinement`；LegalRuleML `appliesJurisdiction` |
| L2 作用域 | `applies_to_assets` | 资产集合引用（替代型号枚举） | ODRL `AssetCollection.source` |
| L2 作用域 | `overrides` | 冲突时谁覆盖谁（现状完全没有） | LegalRuleML `<lrml:Override>` |
| L3 约束 | `constraint_id` / `left_operand` / `operator` / `right_operand` | 判定的四元组结构 | ODRL `Constraint` |
| L4 治理 | `guid` | 内部主键，防编号复用碰撞 | Akoma Ntoso `GUID` |
| L4 治理 | `revision_id` | 历史判定复现的前提 | Akoma Ntoso FRBR EXPRESSION；OpenFisca `formula_YYYY` |
| L4 治理 | `authority` | 规则凭什么有效（法规？平台政策？品牌委员会？） | LegalRuleML `Authority` |
| L4 治理 | `effective_from` / `effective_to` | 时间轴（现状只有一个布尔 `启用状态`） | LegalRuleML `TemporalCharacteristic`；OpenFisca `end=` |
| L4 治理 | `priority` | 多命中时的排序依据（现状靠规则编号顺序，即 DMN 不推荐的 `F`） | DMN `P`；Drools `salience` |
| L4 治理 | `evaluability` | **「无法自动判定」必须是一个可取值** | OpenFisca「Human decisions」；DPV `NotApplicable`/`NotAvailable`/`UnknownApplicability` |
| L4 治理 | `source_refs`（N:M） | 一规则多法源、一法源多规则的现实 | LegalRuleML §4.3.1 Isomorphism |
| L4 治理 | `approved_by` / `approved_at` | 企业场景无立法程序，授权必须自建 | **标准无对应**（见 §2.4） |
| 规则集级 | `hit_policy` / `conflict_strategy` / `fallback_disposition` | 冲突与兜底的声明位置 | DMN `HitPolicy`；ODRL `conflict`；OPA `default` |

### 11.2 「国家 × 品类 × 平台 × 内容类型」四维笛卡尔积的正确分层

#### 为什么笛卡尔积是错的

**[判断]** 三个理由，每个都有标准依据：

**理由 1：产品数 × 维度值数的乘积会爆炸，而实际差异是稀疏的。**
如果 5 个产品 × 8 个国家 × 3 个平台 × 4 种内容类型 = 480 个格子，但实际每条规则只关心其中一两个维度。**用乘积存储稀疏矩阵是经典的存储反模式。**

**理由 2：维度之间不是正交的，存在约束关系。**
「内容类型 = 视频」在「平台 = 小红书」上无意义；「国家 = 美国」与「平台 = 微信」不共存。笛卡尔积模型**无法表达「这两个维度值不共存」**。ODRL 的 `xone`（有且仅有一个满足）与 `andSequence` 正是为这类约束准备的（§9.3.5）。

**理由 3（最重要）：这四维是「作用域」，把它们做成规则的列会违反 `INVARIANCE`。**
按 Akoma Ntoso 的命名原则，规则的标识必须从**不变属性**导出（§4.3.2）。而「这条规则覆盖哪些国家」是**高度可变的**——今天只投法国，下季度投欧盟。如果作用域在规则行里，每次扩区都要复制规则、改列值、产生 `H01-FR`、`H01-EU` 这样的派生编码，**而这些派生编码会违反 `PERMANENCE`**（老的 `H01-FR` 在一段时间后必须废弃）。

#### 一个必须澄清的例外：SPECIAL 确实用了多轴元组

在否定笛卡尔积之前，必须交代一个反例：**SPECIAL（H2020 隐私合规项目）的授权模型就是一个五元组** `⟨data item, purpose, operation, storage, recipient⟩`（§9.2.6）。所以「多轴」本身不是问题。

**区别在于三点**（逐条对照 §9.2.6 的原文）：

1. **SPECIAL 的元组元素是「一条授权」的语义轴，不是「一条规则」的分类标签。** `⟨John_Smith_profile.xml, CommercialPurpose, disclose, null, ACME⟩` 读作「允许把这份数据为这个目的用这个操作…」——它**本身就是一个完整命题**。而 `国家=FR, 平台=Google, 品类=吸奶器, 内容类型=文案` 不是一个命题，它是一组**标签**，必须再配一条规则才知道要做什么。
2. **SPECIAL 允许元素为 `null`（未指定）。** Example 1 里 `storage` 位就是 `null`。笛卡尔积模型无法表达「这一维我不关心」。
3. **SPECIAL 不物化乘积，而是用 OWL 2 本体 + 推理来表达「一大组元组」。** 原文："possibly by representing **large sets of authorizations (tuples) in a concise way**"。

**[判断]** 结论：**「按多轴建模」是标准做法；「把多轴展开成笛卡尔积表」不是。** 前者是 SPECIAL 的做法，后者是 Momcozy 现在担心会掉进去的坑。正确的落地形态见本节后面的「两张表 + 一个继承函数」，或（更标准但成本更高）SPECIAL 式的本体 + 推理。

#### 正确的分层方式

**[判断]** 综合 LegalRuleML 的 `appliesJurisdiction` + `Context`（§4.2.2）、ODRL 的 `refinement`（§9.3.3）、Akoma Ntoso 的 `hierarchy` + `hcontainer`（§4.3.3）与 Cedar 的 `scope`（§5.2.1），正确结构是：

**把四维从「规则的列」提升为「一棵可继承的作用域树 + 规则挂载点」。**

```
                    ┌──────────────────────────────────┐
                    │  ScopeNode: root（全局默认）       │
                    │  applies: 无（= 全世界、全品类）    │
                    └───────────────┬──────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
   ┌────▼─────┐              ┌──────▼─────┐              ┌──────▼─────┐
   │ 国家=US   │              │ 国家=DE     │              │ 国家=FR     │   ← jurisdiction 维
   └────┬─────┘              └──────┬─────┘              └──────┬─────┘
        │                           │                           │
   ┌────▼─────┐              ┌──────▼─────┐              ┌──────▼─────┐
   │ 平台=Meta │              │ 平台=Google │              │ 平台=Google │   ← platform 维
   └────┬─────┘              └──────┬─────┘              └──────┬─────┘
        │                           │                           │
   ┌────▼─────┐              ┌──────▼─────┐              ┌──────▼─────┐
   │ 品类=吸奶器│              │ 品类=吸奶器 │              │ 品类=吸奶器 │   ← category 维
   └────┬─────┘              └──────┬─────┘              └──────┬─────┘
        │                           │                           │
   ┌────▼──────┐             ┌──────▼──────┐            ┌──────▼──────┐
   │ 内容=图片  │             │ 内容=文案    │            │ 内容=视频    │  ← content_type 维
   └───────────┘             └─────────────┘            └─────────────┘
```

规则**挂到它实际关心的最上层节点**上，命中时**沿路径向下继承**。

四条设计规则：

**(a) 规则挂载点 = 规则实际有差异的最上层。**
一条只在美国有差异的规则，挂在 `国家=US` 节点上。它在 US 下的所有平台 × 品类 × 内容类型组合里自动生效——**一次声明，不是 3×1×4=12 条规则**。
标准依据：ODRL `refinement` 的「作用于集合的每个成员，而不是整体」（§2.5.5）；Akoma Ntoso 的层级「nested to an arbitrary depth」（§4.3.3）。

**(b) 继承方向默认为「向下继承」，覆盖方向由 `Override` 显式声明。**
子节点可以覆盖父节点，但**必须显式**。LegalRuleML 提供了 `OverrideStatement`（§4.1.5）用于声明「CS2 覆盖 CS1」。
标准依据：LegalRuleML `<lrml:Override over="#cs2" under="#cs1"/>`。

**[判断]（本轮新增，重要）「让外层规则覆盖内层规则」这条看似显然的捷径，被 DPV 明确否决过，理由与本项目直接相关。** DPV 在讨论「为什么不能给规则一个默认解释」时，顺手否决了 override 机制（DPV Modules → Rules §3.1，逐字见 §9.2.8）：

> "While an apparent solution is to **create a mechanism whereby the rule in the process is overridden with the intended 'outer' rule or context** e.g. to specify the prohibition in one process overrules permission in another process, **this prevents the combination of rules to describe situations such as a permission for a larger context within which specific parts are prohibited or obligated.**"

翻译成 Momcozy 的语言：**如果作用域链只有「上层覆盖下层」这一条全局规则，你就再也表达不了「整个欧盟允许宣称 X，但德国境内禁止宣称 X 的某个具体变体」。** 而这恰恰是母婴品类跨境投放的常态（欧盟通用允许 + 德国 HWG 收紧，§6 的 lex specialis vs lex superior 冲突正是这个形态）。

**所以 (b) 与 (c) 必须成对使用**：`Override` 是**逐条声明**的（LegalRuleML），优先级方向是**逐维声明**的（(c)），**两者都不能退化成一条全局的「谁覆盖谁」。** DPV 这段话是这条设计约束在标准文本里的直接依据。

**(c) 冲突时用「逐维优先级方向」而不是「越具体越优先」。**
**这是对「越具体越优先」这个流行说法的重要修正。** LegalRuleML 明确警告 lex specialis 不一定适用（"a more specific article from a local council regulation might not override a less specific constitutional norm"，§4.1.5）。
所以正确的做法是：**在作用域树上为每个维度声明优先级方向**——
- `jurisdiction` 维：**上位优先**（国家法规 > 平台政策 > 品牌调性）→ lex superior
- `platform` 维：**具体优先**（某个平台的具体条款 > 通用政策）→ lex specialis
- `recency`：**新法优先** → lex posterior

标准依据：LegalRuleML 对三种手段与三条法律原则的映射（§4.1.5）。

**(d) 命中策略必须在规则集层面显式声明。**
不是「就高不就低」，而是从 DMN 的七个 hit policy 里选一个并写下来（§5.5.2）。
**[判断]** 对 Momcozy，最合适的是 **`P`（Priority）+ `C`（Collect）的组合**：
- 用 `P` 决定「最终处置」（拒绝 > 人工复核 > 通过）——**优先级由输出值的有序列表定义，与规则顺序无关**（DMN 原文："Note that priorities are independent from rule sequence"）；
- 用 `C`（Collect）把**所有**命中的规则作为证据累积下来（不丢弃次要命中）——审查报告需要「命中了几条、分别是什么」，而不是只留最高那条。

**[判断]** 现在 Momcozy 的做法隐含的是 `F`（First，按规则编号取第一条）。DMN 明确说这个策略 "not considered good practice because they do not offer a clear overview of the decision logic"（§5.5.2）。**这是第一个应当换掉的地方。**

#### 一个可操作的落地形态

**[判断]** 不需要一步到位建图数据库。最小可行形态是**两张表 + 一个继承函数**：

**表 A：作用域节点（scope_node）**

| 字段 | 类型 | 说明 |
|---|---|---|
| `scope_id` | string | 稳定 ID |
| `parent_scope_id` | string? | 父节点；root 为空 |
| `dimension` | enum | `jurisdiction` / `platform` / `category` / `content_type` |
| `value` | string | 该维度的取值（`US` / `Google` / `吸奶器` / `video`） |
| `label` | string | 展示名 |

**表 B：规则（rule）** —— 见 §11.5 的建议 schema，其中 `scope_id` 是一个**外键**，不是四个列。

**继承函数**：

```python
def resolve(rule, context) -> bool:
    """context = {jurisdiction: 'DE', platform: 'Google', category: '吸奶器', content_type: 'copy'}"""
    node = lookup(rule.scope_id)
    while node is not None:
        if not matches(node, context):
            return False        # 作用域链上任一节点不匹配 → 规则不适用
        node = node.parent
    return True
```

**[判断]** 这个函数的价值在于：**「规则在哪些情形适用」变成了一个可以被单元测试、可以被静态分析、可以在审查报告里被逐层打印出来的东西**，而不是分散在 21 行的 `适用产品` 列里。

### 11.3 21 条规则全部写死 `适用产品 = W1、M5、M6、M9、Air1` 该怎么改

**[判断]** 这个现象有三个层面的问题，逐个说。

#### 问题 1：它把「产品型号」当成了作用域维度，但型号是**客体（Asset）**，不是**作用域**

在 ODRL 里，「这条规则涉及哪些资产」是 `Rule.target`（指向 Asset），而「这条规则适用于资产集合里的哪些成员」是 `AssetCollection.refinement`（§2.5.5）。两者不同：
- `target` 说「管这个东西」；
- `refinement` 说「在这个东西的集合里，符合某条件的那些成员」。

**型号列表是 `target` 的取值，不是作用域的取值。** 现在混在一起了。

**改法**：
- 如果 21 条规则**确实**都作用于全部 5 个型号 → 把型号列表移到**规则集级别**（一个 `applies_to_assets` 声明），21 行不再重复。
- 如果某条规则**只**作用于某几个型号 → 那条规则单独声明，其余继承规则集级别的默认。

#### 问题 2：它用一个**硬编码列表**表达「全部产品」，会导致新产品上市时静默失效

**这是最危险的一点。** 当新产品 Air2 上市时：
- 如果没有人去改这 21 行，Air2 的内容**不会**被任何规则覆盖；
- 而由于没有兜底规则（§11.4），Air2 的内容会**静默通过**。

这正是 OPA Style Guide 描述的 fail-open（§5.1.3）的**组织版本**：不是输入字段缺失，而是**规则集的作用域没有覆盖新对象**。

**改法**（三选一，按推荐度排序）：

1. **【推荐】用「集合引用」而不是「枚举列表」**。声明 `applies_to_assets: @product_line.pump`（指向一个产品线对象），新产品加入产品线时自动被覆盖。
   标准依据：ODRL 的 `AssetCollection` + `source` 属性（§2.5.5："when using the refinement property, the `uid` property MUST NOT be used to identify the AssetCollection. Instead, the `source` property MUST be used to reference the AssetCollection."）。
2. **显式声明「未覆盖即为异常」**。加一条兜底规则：「任何不在任何规则作用域内的资产 → 人工复核」。
3. **加一个 CI 检查**：规则集的资产覆盖集与产品主数据做 diff，有新产品未被覆盖就报错。

#### 问题 3：它掩盖了「规则是否真的对所有型号都一样」这个未经验证的问题

**[判断]** 21 条规则全部写同一个值，有两种可能：(a) 确实都一样；(b) **填表时批量粘贴的**。从 `00-调研任务书.md` 描述的现状（`判断方式` 21/21 也是同一个值）看，(b) 的可能性不低。

**改法**：
- 把 `applies_to_assets` 设为**必填且不允许从别的行继承**，强制每条规则被单独回答一次；
- 对「与规则集默认值相同」的规则打一个 `inherited: true` 标记，使它**在审计时可见**——「这条规则的适用范围是继承来的，从未被单独确认过」。

### 11.4 兜底：现在缺的那一条规则

**[判断]** 现状最大的结构性缺口不是某个字段，而是**整份规则集没有兜底规则**。

按 §10.2 的四个理由与 §8.1 的 `Deny-unless-permit` 分析，建议增加一条显式的兜底规则（数值上是第 22 条）：

```
rule_key:      D00
modality:      obligation
severity:      (n/a)
disposition:   human_review
scope:         root（全局）
condition:     无（catch-all）
statement:     "凡未被 H 族规则显式判为拒绝、且未被安全词白名单显式判为通过的
                内容，一律置为『待人工复核』。"
evaluability:  automatic
```

**[判断]** 这条规则必须**显式写在规则库里**，而不是硬编码在引擎里。理由就是 §5.1.2 的 OPA 原文：不写出来，它就是 `undefined`——而 undefined 在实现层会被不同的人做不同的处理。

**[判断]（本轮新增）** DPV 为这条建议补上了一个更根本的理由（DPV Modules → Rules §3.1，逐字见 §9.2.8）：**给规则一个「默认解释」（比如默认允许或默认拒绝）的代价不是省事，而是摧毁可组合性。** DPV 的原话是：如果 `Process` 有了默认解释，想表达别的意思时「**it would require creating a separate instance with the same information - leading to duplicated efforts**」。也就是说，**兜底值一旦写进「没写就是 X」的位置，它就会变成复制行的源头**——这正是四维笛卡尔积的成因机制（§11.2 理由 3）。

**因此 D00 的正确形态是「一条显式的规则」，不是引擎里的一个 `else` 分支**：前者可审计、可改、可被 §11.2 的作用域树覆盖（例如「德国境内兜底改成 `reject`」），后者不行。DPV 把这条纪律推得更远——它连「默认解释」这个概念本身都拒绝提供（§3.1），并把「触发条件」明确列为未来工作（§4）。**一个成熟标准宁可公开挂空账，也不肯悄悄填一个默认值。**

**[判断]** 同时建议：**检测器异常（正则编译失败、上游 API 超时、字段缺失）走一个独立通道**，不并入 D00。理由见 Cedar 的 skip-on-error 论证（§5.2.2）：「an application that was working fine with 100 policies might suddenly start denying all requests if the 101st policy has an error」。如果检测器异常直接落到「高危」，那么**一次正则写错会让全量内容被拒**，而 Momcozy 没有强制卡点（`00-调研任务书.md` §2.E），后果是业务绕过审核流程。

### 11.5 正则与豁免词应该怎么分层

**[判断]** 现状是：8 条带正则、5 条带豁免词，都挂在规则行上。标准做法是**拆成三个独立对象**。

#### 三个对象的职责划分

| 对象 | 职责 | 标准依据 |
|---|---|---|
| **rule（规则）** | 说什么（modality + 前件 + 结论） | LegalRuleML `PrescriptiveStatement` |
| **constraint（约束）** | 判定的条件表达式 | ODRL `Constraint`（`leftOperand` + `operator` + `rightOperand`） |
| **detector（检测器）** | 条件在文本上如何被执行 | ODRL `Action.refinement`；CEL 表达式 |
| **exemption（豁免）** | 什么情况下该约束**不参与判定** | LegalRuleML 前件条件（否定形式） |

#### 关键判断：豁免词是「作用域」不是「许可」

**[判断]** 这是本分片给出的一个明确设计建议，依据是 LegalRuleML 对 weak/strong permission 的区分（§4.1.2）：

- 如果豁免词的语义是「出现这个词时，这条规则**不适用**」→ 它是**作用域/前件条件**，应建模为 `Constraint` 的一个**否定 refinement**（ODRL 的做法：加一个 `operator: neq` 或 `isNoneOf` 的 Constraint）。
- 如果语义是「出现这个词时，虽然命中，但**显式许可**」→ 它是 **strong permission**，应建模为一条独立的 `Permission` 规则，并且**必须被显式引用**（LegalRuleML 原文："a strong permission is not derived from the absence of a prohibition, but is explicitly formulated in a permissive (prescriptive) norm"）。

**这两种语义在实现上完全不同**：前者让规则不命中；后者让规则命中但结论被覆盖。**现状把两者混在一个 `豁免词` 字段里，无法区分。**

#### 具体分层建议

```
rule: H03「不得宣称治疗/治愈疾病」
  ├─ constraint C-H03-1
  │    leftOperand:  ！文案正文
  │    operator:     matches_regex
  │    rightOperand: "治愈|根治|cure|heal..."
  │    detector:     RE-H03-1（正则对象，可独立版本化）
  │    exemption:    [C-H03-1-EX]（否定 refinement）
  │         leftOperand:  文案正文
  │        operator:     isAnyOf
  │        rightOperand: ["非医疗语境免责声明", "clinical study 引用"]
  └─ disposition:  reject（若命中且未被豁免）
```

**四个直接收益**（[判断]）：

1. **正则可以被多个规则共享**。现状 8 条正则各自独立，如果两条规则用同一个正则，改一处要改两处。
2. **正则本身可以版本化与回归测试**。正则的修改（例如补一个绕过变体）不应该改变规则的 `revision_id`——它改的是检测器，不是规则。
3. **豁免词的两种语义可以被区分**。
4. **`检测关键词` 与 `正则表达式` 可以合并成一个 `detector` 对象**：关键词是「字面量匹配」这种最简正则的特例。

**[原文]** 一个来自标准的直接支持：ODRL 的 Constraint 有 `uid`，**可以被多处引用**（IM Example 15 里 `xone` 引用两个具名 Constraint）。也就是说，**Constraint 本来就是设计成可复用对象的，不是设计成挂在规则上的字符串。**[判断，基于 §9.3.3 的原文]

### 11.6 建议的规则 schema

**[判断]** 下面是综合本分片所有证据给出的完整 schema。**字段来源列注明每个字段来自哪个标准的哪个概念**。

#### 表 1：`scope_node`（作用域节点）

| 字段名 | 类型 | 必填 | 语义 | 来源标准 / 概念 |
|---|---|---|---|---|
| `scope_id` | string | ✔ | 稳定 ID，永不变 | Akoma Ntoso `eId`（命名约定：MEANINGFULNESS/PERMANENCE/INVARIANCE） |
| `parent_scope_id` | string? | ✔（root 为 null） | 父节点，构成继承链 | Akoma Ntoso `hierarchy` 嵌套；LegalRuleML `Context` |
| `dimension` | enum | ✔ | `jurisdiction` / `platform` / `category` / `content_type` / `channel` | ODRL `LeftOperand`（可扩展的维度枚举）；LegalRuleML `Jurisdiction` 定义含 "geographic area **or subject-matter**" |
| `value` | string | ✔ | 该维度取值（机器可读，如 `US`、`google_ads`） | ODRL `RightOperand` |
| `label` | string | ✔ | 展示名 | 工程约定 |
| `priority_direction` | enum | ✔ | `upward`（上位优先，lex superior）/ `downward`（具体优先，lex specialis）/ `recent`（新法优先，lex posterior） | LegalRuleML §4.2.1 三手段 ↔ 三原则映射 |
| `applies_from` | date | ✔ | 该作用域节点的生效日 | LegalRuleML `TemporalCharacteristic.forStatus=InForce` |
| `applies_to` | date? | | 失效日（null = 至今） | LegalRuleML `StatusDevelopment=Ends` |

#### 表 2：`rule`（规则本体 + 治理元数据）

| 字段名 | 类型 | 必填 | 语义 | 来源标准 / 概念 |
|---|---|---|---|---|
| `rule_key` | string | ✔ | **WORK 层稳定 ID**（如 `H03`），永不改变、永不复用、不回收 | Akoma Ntoso FRBR WORK + PERMANENCE；Cedar「UUID，永不复用」的反面约束 |
| `guid` | uuid | ✔ | 内部主键，无语义 | Akoma Ntoso `GUID` 属性 |
| `revision_id` | string | ✔ | **EXPRESSION 层版本 ID**（如 `H03@2026-09-15` 或内容哈希） | Akoma Ntoso FRBR EXPRESSION + `wId`/`eId`；OpenFisca `formula_YYYY` |
| `supersedes` | string? | | 被本条取代的 `revision_id` | OpenFisca：新公式取代旧公式；Akoma Ntoso `<mappings>` |
| `title` | string | ✔ | 一句话规则名（面向人） | Cedar 的 `@id` annotation；OPA METADATA `title` |
| `statement` | string | ✔ | **精确逻辑陈述**：「在〔条件〕下，〔主体〕不得/须〔行为〕于〔客体〕」 | Better Rules「Business Rule Statements」；LegalRuleML `PrescriptiveStatement` |
| `modality` | enum | ✔ | `prohibition` / `obligation` / `permission` | LegalRuleML `[FOR]` / `[OBL]` / `[PER]`；Cedar `forbid` / `permit`；ODRL `Prohibition` / `Duty` / `Permission` |
| `modality_strength` | enum | ✔ | `strict` / `defeasible` | LegalRuleML `StrictStrength` / `DefeasibleStrength` |
| `bearer` | string | ✔ | 规则**对谁**成立（如「品牌方内容团队」「投放代理商」） | LegalRuleML `Bearer` / `AuxiliaryParty`（有向算子） |
| `severity` | enum/int | ✔ | 风险严重度（**与 modality 正交**） | DMN `OutputClause` 的 `outputValues` 有序列表 |
| `disposition` | enum | ✔ | 命中后的处置：`reject` / `human_review` / `pass` / `require_edit` | DMN 输出值；XACML `Deny`/`Permit`/`Indeterminate` |
| `scope_id` | string | ✔ | **外键 → `scope_node.scope_id`**（不是四个维度列） | ODRL `refinement`；LegalRuleML `appliesJurisdiction` |
| `applies_to_assets` | ref | ✔ | 资产集合引用（不枚举型号） | ODRL `AssetCollection.source` + `refinement` |
| `exceptions` | ref[] | | 指向 `constraint` 的否定 refinement（原「豁免词」的作用域语义） | LegalRuleML 前件条件；ODRL `Constraint.operator=isNoneOf` |
| `permissions_granted` | ref[] | | 指向显式 `permission` 规则（原「豁免词」的许可语义） | LegalRuleML strong permission |
| `overrides` | string[] | | 本规则覆盖哪些 `rule_key`（优先级关系） | LegalRuleML `<lrml:Override over= under=>` |
| `priority` | int | ✔ | 数值优先级（用于 DMN `P` hit policy） | DMN `P`（"priorities are independent from rule sequence"）；Drools `salience` |
| `mutex_group` | string? | | 互斥组：同组内只允许一条命中 | Drools `activation-group`（"only one rule can be activated"）；ODRL `xone` |
| `evaluability` | enum | ✔ | `automatic` / `assistive` / `manual_only` —— **「无法自动判定」是一等取值** | OpenFisca "any process that includes human judgement can not be completely automated"；Cedar `error` + skip-on-error |
| `source_refs` | ref[] | ✔ | N:M 指向法规/政策原文的**细粒度**定位（条文号/段落/句子） | LegalRuleML `<lrml:References>` + `refIDSystemName`；§4.3.1 Isomorphism |
| `authority` | string | ✔ | 规则的权威来源（如「EU 2017/745」「Google Ads Policy」「品牌委员会」） | LegalRuleML `Authority`（"power to create, endorse, or enforce"） |
| `status` | enum | ✔ | `draft` / `approved` / `in_force` / `suspended` / `repealed` | LegalRuleML `Legal Status`（"is applicable", "is in force", "has efficacy", "is valid"）；Drools `enabled` |
| `approved_by` | string? | | 批准人 | **标准无对应**——Better Rules 假设团队共识；企业场景需自建（见 §2.4 的缺口说明） |
| `approved_at` | datetime? | | 批准时间 | 同上 |
| `effective_from` | date | ✔ | 生效日（entry） | LegalRuleML `TemporalCharacteristic.forStatus=InForce` |
| `effective_to` | date? | | 失效日（null = 至今） | LegalRuleML `StatusDevelopment=Ends`；OpenFisca `end=` |
| `trigger_rationale` | text | | 触发原因（**不参与判定，只供审计**） | DMN `RuleAnnotationClause`（"ignored for purposes of the hit policy validations"） |
| `notes` | text | | 自由笔记 | DMN `RuleAnnotationClause` |

#### 表 3：`constraint`（约束，可复用）

| 字段名 | 类型 | 必填 | 语义 | 来源标准 / 概念 |
|---|---|---|---|---|
| `constraint_id` | string | ✔ | 稳定 ID（**可被多条规则引用**） | ODRL `Constraint.uid`（IM Example 15 的 `C1`/`C2`） |
| `left_operand` | enum | ✔ | 比什么（`body_text` / `image_text` / `video_transcript` / `listing_title` / …） | ODRL `Constraint.leftOperand` |
| `operator` | enum | ✔ | 怎么比（`contains_any_of` / `matches_regex` / `gte` / `lte` / `is_none_of` / `is_all_of` / …） | ODRL §3.16 的 12 个算子（`eq/gt/gteq/lt/lteq/neq/isA/hasPart/isPartOf/isAllOf/isAnyOf/isNoneOf`） |
| `right_operand` | json | ✔ | 比到什么（词表 / 正则 / 阈值） | ODRL `Constraint.rightOperand` |
| `right_operand_ref` | ref? | | 右操作数是一个**引用**（多国共用阈值） | ODRL `rightOperandReference`（"an IRI that MUST be de-referenced first"） |
| `unit` | string? | | 单位 | ODRL `Constraint.unit`（Example 14 的 `unit: http://qudt.org/vocab/unit/MinuteTime`） |
| `status_ref` | ref? | | 历史累计状态（如「账号本月已被警告次数」） | ODRL `Constraint.status`（"the action has already been exercised 5 times"） |
| `logic_op` | enum? | | 与其他 constraint 的组合：`and` / `or` / `xone` / `andSequence` | ODRL §3.17 的 4 个逻辑操作数 |
| `detector_ref` | ref | ✔ | 指向 `detector`（实现层的正则/模型） | ODRL `Action.refinement`（"narrows the semantics of the Action operation directly"）；CEL 表达式 |
| `negated` | bool | ✔ | 是否为否定条件（原「豁免词」的作用域语义） | LegalRuleML 前件条件的否定形式 |

#### 表 4：`detector`（检测器，实现层，**变动最频繁**）

| 字段名 | 类型 | 必填 | 语义 | 来源标准 / 概念 |
|---|---|---|---|---|
| `detector_id` | string | ✔ | 稳定 ID | 工程约定；OPA 中规则可被独立查询（"each rule may be queried individually"） |
| `kind` | enum | ✔ | `keyword` / `regex` / `classifier` / `llm_judge` / `human` | OpenFisca "Human decisions ... can be modelled as input variables"（`human` 是一等 kind） |
| `pattern` | string | ✔ | 正则或关键词表 | ODRL `rightOperand`；CEL `matches()` |
| `flags` | string? | | 正则 flags（大小写、Unicode） | 工程约定 |
| `test_cases` | ref | ✔ | **该检测器的正/反例测试集** | Better Rules「Test Suites」；`example-rules-as-code/shared/example_beards.yml`；`opa test` |
| `version` | string | ✔ | 检测器版本（正则改动不改规则版本） | OpenFisca `formula_YYYY` 的思路：**实现与声明分离版本** |
| `known_bypasses` | string[] | | 已知绕过手法（拼音、拆字、emoji） | 对齐 `distill/shards/S1-10` |

#### 表 5：`rule_set`（规则集，版本化与兜底声明）

| 字段名 | 类型 | 必填 | 语义 | 来源标准 / 概念 |
|---|---|---|---|---|
| `rule_set_version` | string | ✔ | 规则集版本 ID（内容哈希优先） | Akoma Ntoso FRBR EXPRESSION；OpenFisca `reform` |
| `hit_policy` | enum | ✔ | `U` / `A` / `P` / `F` / `C` / `O` / `R`（**默认 `U`，允许重叠时必须显式声明**） | DMN `HitPolicy` 枚举（"The hit policy SHALL default to Unique"） |
| `aggregation` | enum? | | 当 `hit_policy = C` 时的聚合：`sum` / `min` / `max` / `count` | DMN `BuiltinAggregator` |
| `fallback_disposition` | enum | ✔ | **兜底结论**（建议 `human_review`） | OPA `default`；XACML `Deny-unless-permit`；Cedar implicit deny |
| `fallback_rule_id` | ref | ✔ | 兜底规则必须**显式存在**（见 §11.4 的 `D00`） | OPA："Without the default definition, the `allow` document would be undefined." |
| `conflict_strategy` | enum | ✔ | `deny_overrides` / `permit_overrides` / `void` | ODRL `conflict`（`prohibit` / `perm` / `invalid`，**默认 `invalid`**）；Cedar forbid-overrides-permit；XACML combining algorithms |
| `effective_from` / `effective_to` | date | ✔ / | 规则集生效区间 | LegalRuleML `TemporalCharacteristic` |
| `supersedes_rule_set` | ref? | | 被取代的规则集版本 | OpenFisca `reform` vs reference system |
| `approved_by` / `approved_at` | string / datetime | ✔ | 谁批准了这份规则集 | 企业自建（见 §2.4 缺口） |

#### 字段来源统计

| 来源标准 | 贡献的字段数 | 主要贡献 |
|---|---|---|
| LegalRuleML | 14 | modality、strength、bearer、authority、status、时间三轴、source_refs、overrides |
| ODRL | 15 | constraint 四元组、12 个算子、4 个逻辑操作数、refinement 挂载点、conflict |
| DMN | 7 | hit_policy、aggregation、severity 有序列表、rule annotation、default output |
| Akoma Ntoso | 5 | rule_key/revision_id/guid 三层 ID、hierarchy 继承链 |
| Cedar | 4 | modality 二值化、fallback 显式化、skip-on-error（evaluability） |
| OpenFisca | 4 | 日期版本化、end=、reform、human 判定作为一等 kind |
| Drools | 3 | priority、mutex_group、enabled 对应的 status |
| Better Rules | 2 | `statement` 的精确陈述要求、`test_cases` |
| OPA | 2 | fallback 必须显式；检测器可独立查询 |
| **企业自建（标准无对应）** | 2 | `approved_by`、`approved_at` |

### 11.7 落地顺序建议

**[判断]** 不建议一次性重构 12 字段。按「改动收益 / 改动成本」排序：

| 优先级 | 动作 | 理由 | 成本 |
|---|---|---|---|
| **P0** | 加一条**显式兜底规则 D00**（未命中 → 人工复核） | 消除 fail-open；Cedar/OPA/DMN 三方共识 | 极低（加一行 + 引擎改一处） |
| **P0** | 规则集层面**显式声明 hit_policy**（建议 `P` + 收集全部命中） | 现状是隐式 `F`，DMN 明确不推荐 | 低 |
| **P1** | 把 `适用产品` 的硬编码列表改为**集合引用** + 新增产品覆盖检查 | 消除「新产品静默失效」 | 低 |
| **P1** | 给每条规则加 **`revision_id`**，审查记录存**规则集版本** | 历史判定可复现的前提 | 中（要改审查记录结构） |
| **P1** | 把 `依据来源` 从自由文本改为 **N:M 引用 + 细粒度定位** | 法规变更时能反查受影响规则 | 中 |
| **P2** | 抽出 `scope_node` 表，`适用产品` 迁入 | 解决问题 1；为多国扩展做准备 | 中 |
| **P2** | 抽出 `constraint` + `detector` 两张表 | 正则复用、独立版本化、豁免词语义澄清 | 中高 |
| **P2** | 把 `边界类型` 拆为 `modality` + `severity` + `disposition` | 消除语义重叠 | 中 |
| **P3** | 建 `test_cases`（Golden Dataset）并与规则关联 | 规则变更的回归门禁 | 高（见 R4） |

---

## 附录 A：证据清单

### A.1 一手标准与官方文档（全部于 2026-09-15 抓取）

| 来源 | URL | 本地证据 |
|---|---|---|
| LegalRuleML Core Specification v1.0 (OASIS Standard) | `http://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/os/legalruleml-core-spec-v1.0-os.html` | `_evidence/R3/raw/legalruleml-core-spec.html`（774 KB）/ `.txt`（7,391 行） |
| Akoma Ntoso v1.0 Part 1: XML Vocabulary (OASIS Standard) | `http://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part1-vocabulary/akn-core-v1.0-os-part1-vocabulary.html` | `raw/akn-core-part1-vocab.html`（808 KB）/ `.txt`（9,561 行） |
| Akoma Ntoso v1.0 Part 2: Specifications | `http://docs.oasis-open.org/legaldocml/akn-core/v1.0/os/part2-specs/akn-core-v1.0-os-part2-specs.html` | `raw/akn-core-part2.html`（222 KB） |
| XACML 3.0 Core Specification (OASIS Standard) | `https://docs.oasis-open.org/xacml/3.0/xacml-3.0-core-spec-os-en.html` | `raw/xacml30-core.html`（1.24 MB）/ `.txt`（16,508 行） |
| ODRL Information Model 2.2 (W3C Recommendation) | `https://www.w3.org/TR/odrl-model/` | `raw/odrl-model.html`（182 KB）/ `.txt`（1,858 行） |
| ODRL Vocabulary & Expression 2.2 (W3C Recommendation) | `https://www.w3.org/TR/odrl-vocab/` | `raw/odrl-vocab.html`（245 KB）/ `.txt`（3,317 行） |
| DMN 1.5 (OMG) | `https://www.omg.org/spec/DMN/1.5/PDF` | `raw/dmn-15.pdf`（15.0 MB）/ `.pdftxt` / `raw/dmn-hitpolicy-excerpt.txt` |
| OPA Policy Language / Policy Reference | `https://www.openpolicyagent.org/docs/latest/policy-language/`、`.../policy-reference/` | `raw/opa-policy-language.txt`（4,537 行）、`raw/opa-docs-policy-ref.txt` |
| OPA Policy Testing | `https://www.openpolicyagent.org/docs/latest/policy-testing/` | `raw/opa-policy-testing.txt`（1,066 行） |
| OPA Style Guide | `https://www.openpolicyagent.org/docs/latest/style-guide/` | `raw/opa-style-guide.txt` |
| Cedar Authorization | `https://docs.cedarpolicy.com/auth/authorization.html` | `raw/cedar-authorization.txt` |
| Cedar Basic Policy Syntax | `https://docs.cedarpolicy.com/policies/syntax-policy.html` | `raw/cedar-syntax-policy.txt` |
| Cedar Policy Validation | `https://docs.cedarpolicy.com/policies/validation.html` | `raw/cedar-validation.txt` |
| Cedar 论文（OOPSLA 2024 扩展版） | `https://arxiv.org/abs/2403.04651`（PDF：`https://arxiv.org/pdf/2403.04651`） | `raw/cedar-oopsla.pdf` / `.pdftxt` |
| **DPV v2.3**（Data Privacy Vocabulary，W3C CG Final Report, 2026-02-25） | `https://w3id.org/dpv/` | `raw/gdpr-dpv-spec.html`（1.32 MB）/ `.txt`（268 KB） |
| **DPV Rules 模块** | `https://w3id.org/dpv/modules/rules` | `raw/gdpr-dpv-module-rules.txt`（59 KB） |
| **DPV Context 模块**（Applicability 概念） | `https://w3id.org/dpv/modules/context` | `raw/gdpr-dpv-module-context.txt`（181 KB） |
| **SPECIAL D2.1《Policy Language V1》**（五元组授权模型） | H2020 SPECIAL deliverable D2.1, 2017-12-26, Final | `raw/gdpr-SPECIAL_D21_M12_V10.pdf` / `.txt`（102 KB） |
| SPECIAL D2.2 / D2.3 / D2.4 | 同上 | `raw/gdpr-SPECIAL_D2{2,3,4}_M1*_V10.txt` |
| GDPRov / GDPRif / PrOnto 相关抓取物（**未纳入分析**，仅存档） | 见文件名 | `raw/gdpr-gdprov-*.html`、`raw/gdpr-gdprif-*.html`、`raw/gdpr-pronto-*` |
| ILC《Fragmentation of International Law》结论 | `https://legal.un.org/ilc/documentation/english/a_cn4_l702.pdf`（A/CN.4/L.702） | `raw/conflict-ilc-a_cn4_l702.pdf` / `.txt` |
| ILC 研究组报告（A/CN.4/L.682 及 Add.1） | `https://legal.un.org/ilc/documentation/english/a_cn4_l682.pdf`、`..._add1.pdf` | `raw/conflict-ilc-a_cn4_l682.pdf`、`raw/conflict-ilc-a_cn4_l682_add1.txt` |
| 《维也纳条约法公约》1969（VCLT） | `https://legal.un.org/ilc/texts/instruments/english/conventions/1_1_1969.pdf` | `raw/conflict-vclt-1969.pdf` / `.txt` |
| 欧盟法院总法务官意见 C-582/08（lex superior 分析） | EUR-Lex / curia.europa.eu | `raw/conflict-eu-ag-opinion-C582-08-vat-lex-superior.txt` |
| 欧盟法院总法务官意见 C-507/13（lex posterior / lex superior） | EUR-Lex / curia.europa.eu | `raw/conflict-eu-ag-opinion-C507-13-crd4-lex-posterior.txt` |
| 欧盟法院 C-48/14（lex specialis 适用性） | EUR-Lex / curia.europa.eu | `raw/conflict-eu-cjeu-C48-14-radioactive-water.txt` |
| 欧盟法院 C-96/00 Gabriel（lex specialis 实例） | EUR-Lex / curia.europa.eu | `raw/conflict-eu-cjeu-c96-00-gabriel.txt` |
| 新西兰 LDAC《Legislation Guidelines 2021》 | `https://www.ldac.org.nz/guidelines/` | `raw/conflict-nz-ldac-legislation-guidelines-2021.pdf` / `.txt`（409 KB） |
| 英国 OPC《Drafting Guidance 2024》 | `https://www.gov.uk/` | `raw/conflict-uk-opc-drafting-guidance-2024.pdf` / `.txt` |
| Alloy 6 官方文档 | `https://alloytools.org/documentation.html` | `raw/conflict-alloy-docs.txt` |
| **DPV `dpv:core` 术语定义文件（Turtle, 689 KB）** | `https://w3id.org/dpv/`（`dpv:core`） | `raw/gdpr-dpv-core.ttl`（689,268 字节）——§9.2.7 的全部术语级定义出自此文件 |
| **DPV Rules 模块 HTML + 清洗文本** | `https://w3id.org/dpv/modules/rules` | `raw/gdpr-dpv-module-rules.html`、`raw/gdpr-dpv-module-rules.clean.txt`——§9.2.8 的 §3.1 / §4 逐字原文 |
| **DPV legal/eu/gdpr 模块 + jurisdiction 词汇** | `https://w3id.org/dpv/legal/eu/gdpr` 等 | `raw/gdpr-dpv-eu-gdpr.ttl`、`raw/gdpr-dpv-legal-eu-gdpr-module.{html,txt}`、`raw/gdpr-dpv-loc-loc.ttl` |
| SPECIAL 项目 deliverable（D21–D24） | H2020 SPECIAL | `raw/gdpr-SPECIAL_D2*_M1*_V10.pdf` + **`.txt`（正文已提取：102 / 53 / 80 / 81 KB）** |
| **DAPRECO 知识库本体（GDPR → LegalRuleML）** | DAPRECO 项目交付物 | `raw/gdpr-dapreco-kb-rioKB_GDPR.xml`（**5,633,102 字节**，962 条规则）——§9.2.9 全部计数出自此文件（另有 `gdpr-dapreco-rioKB_GDPR.xml` 同尺寸副本、`gdpr-dapreco-kb-schema-excerpt.xml`） |
| DAPRECO 论文（JLLI）全文 | `raw/gdpr-dapreco-paper.pdf` → **`.txt`（144,800 字节，已提取）** | `raw/gdpr-dapreco-paper.txt`——966 条公式的权威口径出自此处 |
| PrOnto 本体（Springer 章节） | `raw/gdpr-pronto-springer-chapter.pdf`（**未提取正文，付费墙**） | 另有 `gdpr-pronto-{iospress,orbilu,unibo,springer-landing}.{html,txt}` 存档 |
| OpenAlex / GitHub 检索元数据（DAPRECO / PrOnto） | `https://api.openalex.org/`、GitHub Search API | `raw/gdpr-openalex-*.json`、`raw/gdpr-gh-search-*.json` |
| **第二代 PDF 文本提取器（R1–R5 可复用）** | — | `_evidence/R3/tools/pdftext5.py`，用法 `python3 pdftext5.py in.pdf out.txt` |
| Drools User Guide 8.44.0.Final — Rule Language Reference | `https://docs.drools.org/latest/drools-docs/drools/language-reference/index.html` | `raw/drools-language-reference.txt` |
| Drools DMN | `https://docs.drools.org/latest/drools-docs/drools/DMN/index.html` | `raw/drools-dmn.txt` |
| OpenFisca — Key concepts | `https://openfisca.org/doc/key-concepts/index.html` | `raw/of-keyconcepts.txt` |
| OpenFisca — Parameters | `https://openfisca.org/doc/coding-the-legislation/legislation_parameters.html` | `raw/of-legislation-parameters.txt` |
| OpenFisca — Legislation evolutions | `https://openfisca.org/doc/coding-the-legislation/40_legislation_evolutions.html` | `raw/of-dated-vars.txt` |
| OpenFisca — Reforms | `https://openfisca.org/doc/key-concepts/reforms.html` | `raw/of-reforms2.txt` |
| OpenFisca — 首页（能力边界声明） | `https://openfisca.org/doc/index.html` | `raw/of-index.txt` |
| CEL Language Definition | `https://raw.githubusercontent.com/google/cel-spec/master/doc/langdef.md` | `raw/cel-langdef.txt` |
| CEL Introduction | `https://raw.githubusercontent.com/google/cel-spec/master/doc/intro.md` | `raw/cel-intro.txt` |
| JSON Logic | `https://jsonlogic.com/operations.html` | `raw/jsonlogic.txt` |
| Better Rules Workshop Manual（SIL / Hamish Fraser） | `https://betterrules.nz/workshop-manual.html` | `raw/betterrules-workshop-manual.html` + `repos/betterrules.nz/workshop-manual.md` |
| SIL — Legislation as Code 项目页 | `https://serviceinnovationlab.github.io/projects/legislation-as-code/` | `raw/sil-legislation-as-code.txt` |
| BetterRules/example-rules-as-code | `https://github.com/BetterRules/example-rules-as-code` | `repos/example-rules-as-code/`（含 `shared/example_beards.yml`、`json-logic/beard_definition.json`、`blawx/beard.blawx`） |
| ServiceInnovationLab/Piccolo | `https://github.com/ServiceInnovationLab/Piccolo` | `repos/Piccolo/` |
| Creative Commons RDF namespace | `https://creativecommons.org/ns` | `raw/cc-rights.html` |
| Hamish Fraser — Legislation as Code（新西兰法律基金会项目报告） | `https://hamish.dev/research/lac/part-two` | `raw/hamish-lac-part-two.txt`（616 行） |
| DMN 1.4 规范（用于 §8.3 的 overlap/disjoint 与 defaultOutputEntry） | `https://www.omg.org/spec/DMN/1.4/PDF` | `raw/conflict-omg-dmn-1.4-specification.pdf` / `.txt` |
| EU AG Opinion, Case C-449/21（Towercast）—— **`lex superior` 完整法谚** | `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62021CC0449` | `raw/conflict-eu-ag-opinion-C449-21-towercast.txt` |
| EU CJEU Order, Case C-323/16 P（Eurallumina，法谚进入判决要旨） | `https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:62016CO0323` | `raw/conflict-eu-cjeu-order-C323-16P-eurallumina.txt` |
| ILC 2022 *jus cogens* 条款草案（"hierarchically superior"） | `https://legal.un.org/ilc/texts/instruments/english/draft_articles/1_14_2022.pdf` | `raw/conflict-ilc-jus-cogens-draft-articles-2022.txt` |
| Alloy 语言规范（counterexample 语义） | `https://alloytools.org/spec.html` | `raw/conflict-alloy-spec.html` / `.txt` |
| OpenAlex / Crossref（二手书目元数据） | `https://api.openalex.org/`、`https://api.crossref.org/` | `raw/conflict-openalex-*.json`、`raw/conflict-crossref-vv-kbs.json` |
| 子代理的证据索引起草 | — | `_evidence/R3/NOTES-conflict-resolution-and-rulebase-analysis.md` |
| 法律冲突原则与静态分析工具（子代理搜集） | 见 §6.2 / §8.3 | `raw/conflict-*`（65 个文件） |
| GDPR 形式化项目（子代理搜集） | 见 §9.2 | `raw/gdpr-*` |

### A.2 引用的项目内部资产

| 资产 | 路径 |
|---|---|
| 调研任务书 | `research/governance/00-调研任务书.md` |
| 跨仓库反模式清单 | `research/distill/cross-cutting-findings.md` |
| S1-10 对抗集规避手法 | `research/distill/shards/S1-10*` |
| S4-14 版本比对 | `research/distill/shards/S4-14*` |

---

## 附录 B：缺口清单

> 按任务书要求，明确列出「尝试过但失败/找不到的来源」与「未核实项」。

### B.1 抓取失败（有尝试记录）

| 目标 | 失败模式 | 尝试次数/方式 |
|---|---|---|
| NZ《Better Rules for Government Discovery Report》全文 | Imperva/Incapsula JS 挑战，返回 212 字节壳页 | curl（http/https、www/非 www、3 种 UA、Googlebot UA、两段式 cookie jar、`-L`）、`read_page` 工具、`web_fetch` |
| NZ《Better Rules Handbook》全文 | 同上 | 同上 |
| `www.betterrules.govt.nz/`（Better Rules 官方站） | 同上 | curl |
| OECD《Cracking the Code: Rulemaking for humans and machines》 | HTTP 403（`www.oecd.org` / `oecd-ilibrary.org` / `oecd-opsi.org`） | curl，多路径 |
| OECD OPSI Service Innovation Lab 案例页 | HTTP 403 | curl |
| `web.archive.org` / `archive.org` | DNS 解析到 `108.160.167.165`（非 Archive.org 段），连接超时 rc=28 | curl |
| `r.jina.ai` 文本代理 | 连接超时 rc=28 | curl |
| 通用搜索引擎 | `web_search`（firecrawl 429，retry_after 86400）、`exa_search`（未配置 key）、`read_page`（同 firecrawl）、`duckduckgo`/`google`/`brave`（不可达）、`mojeek`/`bing`（JS 挑战 / 结果页不可解析） | — |
| Google Cloud IAM Conditions 文档（CEL 政策用途的官方说明） | `cloud.google.com` 不可达 | curl |
| ~~SPECIAL deliverable 全文~~ | **已解决**：第二代提取器（ObjStm + ToUnicode CMap + Form XObject + `/Differences`）成功产出 D2.1–D2.4 正文 | 脚本存 `tools/pdftext5.py` |
| ~~**DAPRECO 论文（GDPR → LegalRuleML）全文**~~ | **已解决**：论文全文已提取（144,800 字节）；**且拿到了比论文更硬的工件**——知识库本体 `gdpr-dapreco-kb-rioKB_GDPR.xml`（5,633,102 字节） | 见 §9.2.9 |
| **PrOnto 本体论文（Springer 章节）全文** | **仍未解决**：`link.springer.com/content/pdf/...` 返回 HTML 付费墙；ORBilu 部分条目需登录；unibo CRIS 403 | 多路径尝试，仅得摘要 |
| **DAPRECO 论文与其本体的 4 条计数差异**（本体 615 vs 论文 619 条 constitutive 规则） | **未解释**：差异可复现，但原因未知（版本差异？未纳入 context？）。本文如实报告差异，不编造原因 | 见 §9.2.9 |
| **LKIF（Legal Knowledge Interchange Format）规范** | 未找到可达的一手规范；ESTRELLA 项目 deliverable 站点不可达 | 未做穷尽尝试 |
| ~~`lex superior` 的成文定义~~ | **已解决**：完整法谚取自 EU AG Opinion, Case C-449/21（Towercast），CELEX `62021CC0449` 第 30 点；国际法侧等价物取自 ILC A/CN.4/L.702 结论 (32)(34) | 已写入 §6.2 |
| 新西兰 LDAC《Legislation Guidelines 2021》与英国 OPC《Drafting Guidance 2024》中的拉丁法谚 | 两份文件均已取得全文（409 KB / 200 KB 文本），但 **`lex specialis` / `lex posterior` / `lex superior` / `derogat` / `implied repeal` 的出现次数均为 0** | 已 grep 全文。**结论：这两份文件不可用于引证拉丁法谚**，仅可用于引证其实质规则（LDAC 3.2 / 3.3）。另：brief 中给出的两个 gov.uk URL 均 404，正确 URL 为 `/government/publications/drafting-bills-for-parliament`；澳大利亚 OPC 站点（`www.opc.gov.au`）完全不可达（连接超时 / HTTP/2 INTERNAL_ERROR） |
| ODRL `LeftOperand` 完整 32 项定义 | 已取得清单（`raw/odrl-vocab.txt` §4.5.1–4.5.32）但**未逐项取 Definition 原文** | 有清单，缺逐项定义 |
| 「CC 作为 ODRL Profile」的规范性文档 | 未取得 | — |

### B.2 未核实事项（明确不做断言）

1. **NZ Discovery Report 与 Handbook 的原始措辞**。本文所有 Better Rules 引文来自 Workshop Manual（同一机构、同一作者）与 SIL 项目页，**不能代表 Discovery Report / Handbook 的原文**。若委托方需要这两份文档的确切内容，需在能执行 JS 的浏览器中访问 `digital.govt.nz`。
2. **LKIF 的元素体系**。本文未对 LKIF 做任何具体断言。
3. **PrOnto 的具体建模方式**。**DAPRECO 已不再是缺口**（论文全文 + 知识库本体均已取得，见 §9.2.9）。**PrOnto 仍是缺口**：只有 Springer 章节的摘要（付费墙）+ 二手描述，本文不对其公理体系做任何断言。需注意二手描述的性质：DAPRECO 论文中那句「PrOnto alone is not a suitable knowledge base truly fit for automatic legal reasoning」是**另一批作者的评价**，不能当作 PrOnto 的自我描述，本文仅作线索记录。
4. **DAPRECO 论文口径与其本体计数之间的 4 条差异**。论文称 619 条 constitutive 规则，本体内带 `inScope` 的 constitutive 规则为 615 条（491 + 124）。差异**可复现但未解释**。本文按「以工件为准、差异如实报告」处理，不推测原因。
5. **DPV 主规范与 Rules 模块文档的边界**。DPV 的「不定义默认解释」（§3.1）与「不定义触发条件」（§4）**只存在于 Rules 模块文档**，主规范 `CG-FINAL-dpv-20260225` 的 §4 是 "Vocabulary Index"。引用时务必写模块文档出处（见 §9.2.8 的出处更正）。
6. **`lex superior` 的成文定义**。**已在 §6.2 补齐**：完整拉丁法谚取自 EU AG Opinion, Case C-449/21（Towercast），CELEX `62021CC0449`，第 30 点；国际法侧的等价物取自 ILC A/CN.4/L.702 结论 (32)（*jus cogens*）与 (34)（UN Charter Art. 103）。**仍未取得的**：一条把它写成「规则」而非「解释原则」的成文条款（例如某国法律适用法中的层级条款）。
7. **Better Rules 的「授权与批准」机制**。Workshop Manual 与 SIL 项目页均未给出规则批准流程。§2.4 已说明这是真实缺口，不填补。
8. **Creative Commons 与 ODRL 的关系**。§9.4 只报告了 CC namespace 中存在的类名，未断言其与 ODRL 的 Profile 关系。
9. **OpenFisca 的「追溯适用」（retroactivity）语义**。§3.4 报告了官方对 "retroactive effects" 的用法（指经济行为反馈），但**未找到 OpenFisca 对「法规溯及既往」的专门文档**。读者不应把我的解读当作官方立场。
10. **DMN 1.5 与 1.3 的差异**。本文只读了 1.5；hit policy 相关条款在 1.3 中是否完全一致未核实。
11. **Cedar 的 `error` 与 `skip on error` 之间的完整关系**。§5.2.2 引用了官方说明，但未核验 Cedar 的 Lean 形式化模型中 error 的精确语义。
12. **Drools Verifier 的现状（负面结果，已核实）**。Drools 8.44.0.Final 官方文档树中**没有**独立的 "Drools Verifier" 章节（目录只有 introduction / Commands / DMN / KIE / experimental-features / getting-started / language-reference / migration-guide / pragmatic-ai / release-notes / rule-engine）。历史上存在的 Drools Verifier 产品未保留在现行文档中；**唯一保留的规则集静态分析入口是 DMN 的 `ANALYZE_DECISION_TABLE`**（见 §8.3）。**不要引用「Drools Verifier」作为现行能力。**

### B.3 分片边界排除（有意不写）

- 平台政策的具体条款结构（R1）
- 广告裁决案例的机制（R2）
- 审核队列运营指标与 error analysis 方法（R4）
- 母婴品类具体监管条款与竞品话术（R5）

以上内容即使与本分片相关，也未展开。

### B.4 关于篇幅

本文实际篇幅超出任务书「800–1500 行」的目标。原因是任务书同时要求「每条论断有标准条款号 / 元素名 + **逐字原文** + URL」，而本文引用的 15 份标准原文中有 9 份是英文规范文本，逐字引用本身占据了约 40% 的篇幅。**我选择保留证据完整性，未删减原文引用来压缩篇幅。** 如需精简版本，建议保留第 0、1、10、11 节与附录 B，其余章节按需查阅。

---

*本分片完成。所有引文以抓取日的原文为准；标准文本可能更新，引用时请以 URL 复查。*




