# R8-W3 错题本建模、严重等级定档与空白处理

> 调研分片第三部分。范围：客户原话「我们如何去萃取这个规则库？是否需要给我们提供『错题本』？还是规则库？严重等级？要是没有呢？怎么处理？」中的三个问题。
> 工作目录 `/Users/lute/Project/audit_multi_content`，日期 2026-09-15。
> 边界：不重复 R3 的技术侧空白立场（OPA default / XACML Deny-unless-permit / Cedar skip-on-error），不重复 R6 的 GARM 序数档映射，不重复 R4 §3 的 error analysis 定义。

## 0. 本部分结论（6-10 条，每条一句话，带证据指向）

**Q3 —— 错题本 vs 规则库**

1. **错题本不是规则库的视图，也不是一张独立表，而是一条「采集 → 分诊 → 回归」的流水线，它的产物才是一张表** —— 因为它含规则库根本不存在的字段（判定路径、人工复判、处置码），不是投影（§1.1.1、§1.1.3）。
2. **错题的存储对象是「判定偏差」（判定快照 ⊕ 真相来源），不是案例、不是判定、也不是修订建议** —— 「同一条内容先判红后改判绿」在「存内容」的主键下无法存储，而委托方 `风险等级 × 处理状态` 完全对角正是这个建模后果（§1.2.1、§1.2.4）。
3. **「双库结构」有一个正在 PROD 运行的官方实例：欧盟 Cellar 的「法规 ← 判例」引用网络 —— 4,966 条三元组、6,465 条引用边、224 个判例 CELEX、693 个被引条款片段，引用精度到「句」（`A82P2SNT1`），且判例元数据有独立工作流 `CASELAW_METADATA_UPDATE`**（§1.3.1）。
4. **回流闭环的关键不在「改规则」，而在「不许未经回归就改规则」：每条错题必须有四个字段（处置码 + 关联规则编号 + 处置人 + 处置日期）才算有终态，且错题样本进 golden set 后只增不减**（§1.4、§1.5.3）。
5. **bug tracker 的类比只成立到「结构」为止；多出来的一层是错题本的「真值」必须先被证明稳定（α 达标）才能当回归期望值** —— 否则是用一组本身不一致的判断去测规则（§1.5.2）。

**Q4 —— 严重等级从哪来**

6. **没有外部等级可找，也不需要找：NIST SP 800-30 Rev.1 明确授权组织自定义标度，并给出「流程 + 风险模型 + 评估方法 + 分析取向」四件套与五档半定量尺（96-100 / 80-95 / 21-79 / 5-20 / 0-4）**（§2.1.1、§2.1.2、§2.1.3）。
7. **★ 主交付物 §4.3 的 `risk_score = severity × exposure`（乘法）应改为查表** —— NIST 官方矩阵 TABLE I-2 里 `High likelihood × Moderate impact = Moderate` 而 `Moderate likelihood × High impact = High`，两者不等；且 Low / Very Low likelihood 行会**封顶**风险等级（§2.1.5、§2.5 步骤 7）。
8. **★ 主交付物的 `exposure` 只覆盖了 severity 三子维度的一维** —— DSA Recital (79) 逐字要求「触达人数 / 不可逆性 / 补救难度」三维，后两维是「平台封号 ≠ 某国罚款」的技术答案，而委托方两维都没有字段（§2.2.1(b)、§2.3）。
9. **监管后果与商业后果不应合并成一个标量，而应输出「后果向量 + 取最差」** —— 依据是 NIST Table H-4 的第四列就叫 `Maximum Impact`；而两者在「对象 / 层级 / 时间常数」三个维度上不可通约（§2.3.4）。
10. **★ 规则库本身是一份可从轻处置的合规资产** —— AWS AUP 逐字：`we may consider your ability and willingness to comply with this Policy, including the policies and processes you have in place to prevent or identify and remove any prohibited content or activity.`（§2.3.3(b)）。

**Q5 —— 空白处理**

11. **★ 「空白走 fail-open 还是 fail-closed」不是技术默认值，而是组织层签署的风险容忍度声明** —— NIST SP 800-30 §3.1 把两个极端（`assuming the worst-case likelihood` 与 `assuming that if an event has not been observed, it is unlikely to happen`）并列为合法选项，且 TABLE G-1 把标度定义权明确放在 Tier 1（§3.2.1、§3.2.2）。
12. **「不确定」不能寄生在等级字段里** —— NIST CAUTIONARY NOTE 逐字要求边界样本 `must ultimately be assigned to one bin`；因此 `L0 未覆盖` 应从 `severity` 枚举中拆出为独立的 `coverage_state` 字段（§3.4.1，这是对主交付物 §5.5 的一处修正）。
13. **`判定路径`（自动 / 人工）是欧盟法定字段，且是 291 条记录里唯一「数据还在但信息已永久丢失」的字段** —— DSA Art 17(3)(c) 逐字：`information on the use made of automated means in taking the decision`；Meta 拒绝 rec.13 时承认 `it is not feasible to track this information`（§3.4.3、§1.4.5）。
14. **13.8% 不是覆盖率，是「规则表和判定能力分家」的证据** —— 正则层 `多余命中 = 0` 说明它是定位器而非判定器，而真正的判定能力在 `命中片段` 的 270 对自由文本里、在 5 个语种中，规则表带变音符拉丁字符数为 **0**（§3.5.1）。

**对主交付物的四处修正（汇总）**

| # | 位置 | 现状 | 建议 | 依据 |
|---|---|---|---|---|
| 1 | §4.3 | `risk_score = severity × exposure`（乘法） | **改为查 NIST TABLE I-2 矩阵**（乘法会高估低曝光内容） | §2.1.5 |
| 2 | §4.3 | `exposure = f(展示, 点击, 费用)` | **补 `irreversibility` 与 `remediability` 两维** | §2.2.1(b) |
| 3 | §5.5 | `Agent判定等级 = L0 未覆盖`（不确定寄生在等级字段） | **拆出独立 `coverage_state` 字段** | §3.4.1 |
| 4 | §3.2.1 | `LegalRuleML \| Case（有 CaseLaw 概念）` | **改为 `ConstitutiveStatement` 或标注未核实** —— 本分片在 R3 的证据（`legalruleml-core-spec.txt`，7,391 行）中检索 `CaseLaw` / `isCase` 未命中 | §1.3.3 |

## 1. 错题本与规则库的关系建模

### 1.1 三种候选建模（视图 / 独立表 / 流程）的取舍

**【判断】** 委托方给的三个候选（视图 / 独立表 / 流程）里，只有第三个是对的，但需要精确化。正确答案是：错题本是「一个流程」，它每次运行产生「一张只增不改的独立表」。它不是规则库的视图。**

#### 1.1.1 为什么不是「视图」

**【判断】** 「视图」的定义特征是：它不包含基表里没有的信息，只是基表的一个投影。错题本不满足这个条件 —— 它包含规则库里根本没有的三类信息：**

| 错题本包含的信息 | 规则库里有吗 |
|---|---|
| **判定与真相的偏差**（FP / FN） | **没有** —— 规则库只有规则，没有「规则判错了」这件事 |
| **判定路径**（auto / human / auto_then_human） | **没有** —— 规则库描述规则，不描述某一条内容的判定怎么发生的 |
| **人工复判结论与复判人** | **没有** —— 规则库的字段里没有任何人是「复核者」 |
| **处置码**（这条错题怎么处理了） | **没有** |

**【判断】** 只要错题本含有一个规则库里不存在的字段，它就不是视图。** 而按 R4 §7.2 的缺口清单，错题本至少需要补 12 个规则库里没有的字段。

#### 1.1.2 为什么「独立表」是必要但不充分的

**【判断】** 「独立表」这个说法抓住了存储形态，漏掉了最关键的部分：错题必须能改变规则。** 依据是 R4 §7.2 的最后一段（Gab Hate Corpus 手册的 `Notes` 列）：

> **【原文】**（R4 §3.2 引 Gab Hate Corpus 训练手册，主交付物 §3.2.1 亦引）
> `make notes about difficult cases and difficulties you had in coding, as we will use these contributions to refine and improve later versions of this manual.`

**【判断】** `we will use these contributions to refine and improve later versions of this manual` 是一句承诺** —— 它声明了收集的目的是**改下一版手册**。**如果错题本只是一张表而没有任何机制读它、改规则，那么它就退化成一个归档。**

**【判断】** R4 §7.2 给出的四个字段（`处置码` + `关联规则编号` + `处置人` + `处置日期`）就是把「表」变成「流程产物」的四个字段。** 它们的作用是：**每一条错题都必须有一个终态**，且这个终态指向一个具体的规则修订（或明确写「不改 + 理由」）。

#### 1.1.3 为什么「流程」是对的：三个已完成环节

**【判断】** 错题本的正确建模是三个环节，缺一不可：**

```
① 采集环节   内容 →（自动判定 + 抽样人工复判）→ 错题记录
② 分诊环节   错题记录 →（分桶 + 处置码）→ 规则修订建议（或明确不改）
③ 回归环节   规则修订 →（golden set 跑通）→ 发布；错题样本进入 golden set 永久保留
```

**每一个环节都有一手证据：**

| 环节 | 一手证据 | 出处 |
|---|---|---|
| **① 采集：必须有「判定路径」字段** | **DSA Art 17(3)(c) 法定要求**：`where applicable, information on the use made of automated means in taking the decision, including information on whether the decision was taken in respect of content detected or identified using automated means` | `_evidence/R8/dsa-art34-eurlex.txt` L1233-1235 |
| **① 采集：必须有第三态** | Gab Hate Corpus `Notes` 列收的是「编码困难」；NIST `The inability to appropriately measure AI risks does not imply that an AI system necessarily poses either a high or low risk` | R4 §3.2 / R4 §6.2 |
| **② 分诊：必须有四个处置码** | Meta 的四个处置码逐字定义（`Implementing fully` / `Implementing in part` / `Assessing feasibility` / `No further action`），且给了每条的处置结果（19 条中 `fully implement 15`） | R4 §1.2.2 |
| **③ 回归：必须进 golden set，且只增不减** | R4 §4.1 原则 3：`黄金集必须包含"已知 bug 对应的测试用例"，且每条 bug 只增不减` | R4 §4.1 |

#### 1.1.4 ★ 一个决定性证据：欧盟法把这套东西定成了**四条法定后果层级 + 六个法定字段**

**【判断】** 这是本节最强的证据 —— DSA 第 17 条不是「最佳实践建议」，是**对平台的法定义务**。它证明「错题本」不是内部管理工具，而是监管要求的结构化记录。**

> **【原文】**（`_evidence/R8/dsa-art34-eurlex.txt` L1201-1217，Article 17 Statement of reasons, 第 1 款）
> `Providers of hosting services shall provide a clear and specific statement of reasons to any affected recipients of the service for any of the following restrictions imposed on the ground that the information provided by the recipient of the service is illegal content or incompatible with their terms and conditions:`
> `(a) any restrictions of the visibility of specific items of information provided by the recipient of the service, including removal of content, disabling access to content, or demoting content;`
> `(b) suspension, termination or other restriction of monetary payments;`
> `(c) suspension or termination of the provision of the service in whole or in part;`
> `(d) suspension or termination of the recipient of the service's account.`

**【判断】** ★★★ 这四层与 §2.3.3(a) 的 GitHub 三级阶梯高度重合，但**DSA 是法条，且多了一层「金钱支付」**：**

```
DSA Art 17(1)(a)  可见性级    removal / disabling access / demoting     ← 对应 GitHub 的第 1、2 级
DSA Art 17(1)(b)  金钱级      suspension / termination of monetary payments   ← GitHub 阶梯里没有
DSA Art 17(1)(c)  服务级      suspension / termination of the service
DSA Art 17(1)(d)  账号级      suspension / termination of the account   ← 对应 GitHub 的第 3 级
```

**【判断】** 对 Momcozy 的含义**：`impact_type` 的枚举（§2.3.4）应当直接采用这四层作为 `platform_*` 的取值，而不要自己发明。**理由：它是法定的，且它是「平台会怎么处置你」的官方分类。**

**【判断】** 而且 Art 17(3) 给出了六个必填字段 —— 这就是「错题本最小 schema」的法定版本：**

> **【原文】**（同文件 L1223-1247，Art 17(3)，逐项）
> `(a) information on whether the decision entails either the removal of, the disabling of access to, the demotion of or the restriction of the visibility of the information, or the suspension or termination of monetary payments related to that information, or imposes other measures referred to in paragraph 1 with regard to the information, and, where relevant, the territorial scope of the decision and its duration;`
> `(b) the facts and circumstances relied on in taking the decision, including, where relevant, information on whether the decision was taken pursuant to a notice submitted in accordance with Article 16 or based on voluntary own-initiative investigations and, where strictly necessary, the identity of the notifier;`
> `(c) where applicable, information on the use made of automated means in taking the decision, including information on whether the decision was taken in respect of content detected or identified using automated means;`
> `(d) where the decision concerns allegedly illegal content, a reference to the legal ground relied on and explanations as to why the information is considered to be illegal content on that ground;`
> `(e) where the decision is based on the alleged incompatibility of the information with the terms and conditions of the provider of hosting services, a reference to the contractual ground relied on and explanations as to why the information is considered to be incompatible with that ground;`
> `(f) clear and user-friendly information on the possibilities for redress available to the recipient of the service in respect of the decision, in particular, where applicable through internal complaint-handling mechanisms, out-of-court dispute settlement and judicial redress.`

**【判断】** 六个字段对委托方的直接映射：**

| DSA Art 17(3) 字段 | Momcozy 落地 | 现状 |
|---|---|---|
| (a) 处置类型 + **地域范围 + 时长** | `impact_type` + `territorial_scope` + `duration` | **三个都没有**（`处理状态` 只有「无需处理/待人工复核」） |
| (b) 所依据的事实与情形 + 是否主动调查 | `命中片段` + `依据来源` + `detection_origin` | `命中片段`/`依据来源` **有**；`detection_origin` **无** |
| **(c) 是否使用自动化手段** | **`判定路径`** | **★ 无** —— 而 R4 §7.2 把它列为「做度量必需」的第 8 项 |
| (d) 违法内容的法律依据 + 理由 | `依据来源` 里的法规引用 + `边界内容` | **有字段但没填法规条款级引用** |
| (e) 违反平台条款的合同依据 + 理由 | `依据来源` 里的平台政策引用 | **有字段但没到条款级** |
| (f) 救济途径 | **申诉通道** | **完全不存在**（R4 §1.4 已列「无申诉机制」） |

**【判断】** ★★ 这一节的结论可以一句话总结**：
> **委托方问「是否需要错题本」——欧盟法已经替它回答了：只要你判定任何一条内容，你就必须能说出「依据什么、是不是机器判的、处置到哪一级、影响了哪个地区多久、用户怎么申诉」。这六件事构成的记录，就是错题本。** 委托方现在这六件事里只填得出两件（`命中片段` 与 `依据来源`，且后者未到条款级）。

#### 1.1.5 三个候选的最终裁决

| 候选 | 裁决 | 理由 |
|---|---|---|
| **视图** | **✗ 否** | 错题本含规则库不存在的字段（判定路径、复判结论、处置码），不是投影（§1.1.1） |
| **独立表** | **△ 必要不充分** | 存储形态对，但没有「每条错题必须有终态」的机制就退化为归档（§1.1.2） |
| **流程** | **✓ 是** | 采集 → 分诊 → 回归 三环节，每环节有独立证据（§1.1.3）；且采集环节的字段由 DSA Art 17(3) 法定（§1.1.4） |

**【判断】** 一句话回答委托方**：
> **错题本是一条流水线，它的输出是一张只增不改的表。表是产物，不是本体。** 只买一张表（或一个 CSV 模板）而不建流水线，等于买了一个永远不会被读的档案柜。

### 1.2 错题的存储对象是什么

**【判断】** 委托方给了三个候选：案例（case）、判定（decision）、规则修订建议（rule change proposal）。正确答案是「第四个」：存的是**判定偏差（decision deviation）**，而不是三者中任何一个。**

#### 1.2.1 为什么不是「案例」

**【判断】** 「案例」是内容本身。而一条内容可以在不同时间被判定多次，每次结论可能不同。** 如果错题本的主键是内容，那么「同一条内容先被判红、后被改判绿」这件事**无法存储** —— 表里只有一行。

**证据**：委托方现有的 291 条记录主键是内容（`广告名称 | 平台 | 外部广告ID`），实测结果是：

> **【原文】**（`01-内部证据-规则表现状审计.md` §五，主交付物 §4.5 亦引）
> `风险等级 × 处理状态` 交叉表**完全对角**，291 条里**没有任何一条**呈现「机器判红 → 人工改判绿」或「机器判绿 → 人工发现红」。

**【判断】** 「完全对角」不是分类整齐，而是**表结构不允许记录第二次判定**。** 主键是内容，所以一次内容只能有一个结论。**这就是「存内容」这个建模选择的直接后果。**

#### 1.2.2 为什么不是「判定」

**【判断】** 「判定」比「案例」进一步，但还不够 —— 因为一条判定本身可能是**正确**的。** 错题本只应该收「有问题」的判定。如果错题本存所有判定，它就等于判定日志，而不是错题本。

**证据**：`errorbook.csv` 的现有 schema 已经把这一点做对了 —— 它有 `Agent判定等级` **和** `人工复判结论` 两个字段，**两者之差才是错题**：

```
错题 = Agent判定等级 ⊕ 人工复判结论      （⊕ = 不一致）
```

**实测**：`_shards` 同级目录 `errorbook/errorbook.csv` 现有 132 条 A 类错题，其中 `人工复判结论` 列**全部为空** —— 也就是说，**目前这 132 条是「待判定的候选错题」，不是「已确认的错题」**。这是正确的初始状态，但必须有人在上面填写。

#### 1.2.3 为什么不是「规则修订建议」

**【判断】** 建议是**分诊环节的产出**，不是采集环节的对象。** 一条错题可能产生零条建议（判错了但规则没问题），也可能产生多条建议（一条错题暴露多处规则缺陷）。

**证据**：Meta 的 19 条 recommendation 里，**有一条是 `No further action`**（R4 §1.2.2）：

> **【原文】**（R4 §1.2.2 引 Meta 官方 PDF）
> `**No further action**: Facebook will not implement the recommendation, either due to a lack of feasibility or disagreement about how to reach the desired outcome.`

**【判断】** `No further action` 这个处置码的存在，证明「建议」与「错题」必须是两张表（或至少是两个实体）** —— 因为一条错题可以以「不改」结案，而「不改」也是一个必须被记录的终态。

#### 1.2.4 ★ 正确答案：存「判定偏差」，且它必须携带一个可追溯的别名

**【判断】** 存储对象的完整定义：**

```
存储对象 = 判定偏差记录 (DecisionDeviation)
        = 三元组 ⟨ 判定快照, 真相来源, 二者之差 ⟩
```

| 分量 | 内容 | 现有 291 条里有吗 |
|---|---|---|
| **判定快照** | `Agent判定等级` + `Agent判定规则` + `规则版本号` + `Agent判定依据类型` + **`判定路径`** | 前三项有，后两项**无** |
| **真相来源** | `人工复判结论` + `复判人` + `复判时间` + **`复判依据`** | **全部无**（`检查人` 非空率 0.0%） |
| **二者之差** | `错误类型`（FP / FN / 未覆盖）+ `是否对抗样本` + `对抗手法` | **全部无** |

**【判断】** 三条设计约束，每条有证据：**

1. **必须存「判定快照」，不是「内容」。** 依据：DSA Art 17(3)(c) 法定要求记录 `information on the use made of automated means in taking the decision`（`_evidence/R8/dsa-art34-eurlex.txt` L1233-1235）；R4 §7.2 第 7 项 `规则版本号` —— **没有版本号就无法回溯「这条是哪个版本的规则判的」**。
2. **必须存「真相来源」及其独立性。** 依据：主交付物 §3.3 硬约束 1 `环 1 与环 4 负责人不能同一人`，以及 R4 §7.2 第 3 项 `复判人`（`必须能证明"复判者未参与初判"`）。
3. **必须存「差」的分类，而不只是一个布尔值。** 依据：R4 §7.2 第 1 项给出的五态 `命中且正确(TP) / 误拦(FP) / 漏放(FN) / 正确放行(TN) / 未覆盖(UNCOVERED)`。

#### 1.2.5 ★ 关键修正：「规则修订建议」应当是错题本表的**外键目标**，不是它的行

**【判断】** 这是对主交付物 §3.2.2 的两类记录（A 类内容错题 `EB-NNNN` / B 类规则错题 `EB-RNNN`）的一处补强建议：**

**主交付物把两类错题放在同一个 `EB-` 命名空间下。但这两类的生命周期完全不同：**

| | A 类：内容错题 | B 类：规则错题 |
|---|---|---|
| 触发者 | 某一条内容的判定偏差 | 静态检查（不需要内容） |
| 需要人工 | **需要**（填 `人工复判结论`） | 不需要 |
| 有一个「验证」动作吗 | **有** —— 复判 | **没有** —— 它本身就是结论 |
| 终态 | `处置码` 指向一个规则修订 | `处置码` 指向一个规则修订（**同一张表**） |
| 是否进 golden set | **是**（这条内容成为回归用例） | **否**（它没有内容样本可入集） |

**【判断】** 两类可以共表，但必须共用一个 `关联规则编号` 外键，并且必须能产生同一张「规则修订建议表」的行。**

**建议的第三张表：**

```
rule_change_proposal
  proposal_id           # RCP-NNNN
  source_errorbook_ids  # N:M → errorbook（一条建议可由多条错题共同支撑）
  target_rule_key       # → rule.rule_key
  change_type           # 参照 Meta 四处置码
  rationale             # 必填
  status                # 参照 Meta 四处置码的终态：fully / in_part / assessing / no_action
  decided_by / decided_at
  regression_passed     # 布尔 —— 未 PASS 不许发布（R4 §4.1 原则）
  released_in_revision  # → rule.revision_id
```

**【判断】** 为什么必须有 `source_errorbook_ids` 这个 N:M 外键：** 因为**单条错题不足以支撑规则变更，重复模式才可以**。依据是 DSA Art 17 之后的机制 —— R4 §5.3.3 记录的 DSA Art 17 自由文本字段实践：`平台发现现有分类描述不了判定理由时可自由文本提交，监管方定期看，出现重复模式就升级为正式分类`。

**【判断】** 「重复模式才升级」是一条重要的约束**：**它防止为了单条错题改规则，从而造成规则库抖动。** 对委托方的直接含义：**规则修订建议的准入门槛应当是「同一模式 ≥N 条错题」，N 由风险容忍度决定（§2.4.1）。**

### 1.3 双库结构的标准出处（判例法 vs 成文法的工程对应物）

**【判断】** 委托方问「双库结构在哪出现过」。答案是：出现过，而且有一个**正在运行、官方、可逐条核查**的实例 —— 欧盟出版办公室的 Cellar 系统。它不是学术提议，是欧盟法律文档的官方基础设施。**

#### 1.3.1 ★★★ 一手证据：欧盟 Cellar 的「法规 ← 判例」片段级引用网络

**【判断】** 本分片在既有证据中发现了一份此前未被引用的关键文件**：`research/governance/_evidence/R3/raw/gdpr-cellar-gdpr-subset.rdf`（欧盟 Publications Office **Cellar** 系统导出的 GDPR 引用关系子集，RDF/CDM 本体）。

**实测统计（本分片直接跑出的数字）：**

| 指标 | 数量 |
|---|---|
| 引用关系三元组（`owl:Axiom`） | **4,966** |
| 引用链接（`cdm:work_cited_by_work`） | **6,465** |
| **独立判例 CELEX 标识** | **224** |
| **独立被引条款片段** | **693** |

**逐字样本（一条完整记录的四个字段）：**

> **【原文】**（`_evidence/R3/raw/gdpr-cellar-gdpr-subset.rdf` L13-18，`rdf:nodeID="A2"`）
> `<owl:annotatedSource rdf:resource="http://publications.europa.eu/resource/celex/32016R0679"/>`
> `<j.2:fragment_citing_source rdf:datatype="http://www.w3.org/2001/XMLSchema#string">N 159</j.2:fragment_citing_source>`
> `<j.2:fragment_cited_target rdf:datatype="http://www.w3.org/2001/XMLSchema#string">A82P2SNT1</j.2:fragment_cited_target>`
> `<owl:annotatedTarget rdf:resource="http://publications.europa.eu/resource/celex/62023CJ0200"/>`
> `<owl:annotatedProperty rdf:resource="http://publications.europa.eu/ontology/cdm#work_cited_by_work"/>`

> **【原文】**（同文件 L14，`build_info` 字段，逐字）
> `reception-ID: PO-20251023-5654; environment: PROD; CERES: 4.29.5; IMMC2CDM: 3.2.3; workflow: CASELAW_METADATA_UPDATE; rules: caselaw-legacy-20250930-0; builddate: 2025-10-24T03:47:46.722;`

**【判断】** ★★★ 这段元数据是「双库结构」最硬的工程证据，它一次性证明了五件事：**

| 证据元素 | 逐字 | 它证明什么 |
|---|---|---|
| `celex/32016R0679` | 成文法标识 | **规则库的键**（GDPR 本体） |
| `celex/62023CJ0200` | 判例标识（CELEX 前缀 `6` = 判例） | **案例库的键**，与成文法**同一命名空间下的不同前缀** |
| `cdm:work_cited_by_work` | 引用关系 | **两库之间是有类型的边，不是一个自由文本备注** |
| `fragment_citing_source = N 159` / `fragment_cited_target = A82P2SNT1` | **片段级**（判例第 159 段 → GDPR 第 82 条第 2 款第 1 句） | **★ 引用精确到「句」，不是精确到「文件」** |
| `workflow: CASELAW_METADATA_UPDATE` + `rules: caselaw-legacy-20250930-0` | **判例元数据有独立的更新工作流，且工作流本身带版本号** | **★ 案例库有独立于规则库的维护流水线** |

**【判断】** 这五件事合起来就是委托方问的「双库结构的工程对应物」，且它比任何学术提案都强，因为它是 PROD 环境的真实运行记录（`environment: PROD`）。**

#### 1.3.2 判例法 vs 成文法的三个工程差异（从这个实例直接读出）

| 维度 | 成文法侧（`32016R0679`） | 判例侧（`62023CJ0200`） | 对 Momcozy 的映射 |
|---|---|---|---|
| **标识前缀不同** | `3` = 立法 | `6` = 判例 | **规则 ID 与错题 ID 必须有可区分的命名空间**（现有 `EB-` / `rule_key` 已做到） |
| **更新工作流不同** | 立法流程 | `CASELAW_METADATA_UPDATE` | **规则变更流程 ≠ 错题录入流程**（对应主交付物 §3.3 的环 1 与环 4 必须分人） |
| **引用粒度不同** | — | **片段级（`A82P2SNT1`）** | **★ 错题必须引用到「规则的哪一条哪一款」，不能只引用到「H07」** |

**【判断】** 第三条是最容易被忽略、但对委托方最有价值的一条。** 委托方现在的 `命中规则` 字段值是 `H07` 或 `H02,H07` —— **这是文件级引用**。按 Cellar 的做法，应当是 `H07#kw-relieve-pain` 这样的片段级引用。

**而且这正好能解释主交付物 §3.2.2 发现的一条真实错题：**

> **【原文】**（主交付物 §3.2.2，EB-R010）
> `EB-R010 | 规则冲突 | H02, M07 | 共享 improve pumping efficiency，严重度不同，需 hit_policy 裁决`

**【判断】** `H02 与 M07 共享同一个关键词但严重度不同` 这个冲突，**只有在片段级引用下才能被表达为「冲突」**。** 因为从文件级看，H02 与 M07 是两条不同规则、没有冲突；从片段级看，`improve pumping efficiency` 这个**触发条件片段**同时属于两条规则且映射到两个不同等级 —— 这才是冲突。**Cellar 的 `fragment_cited_target` 就是这个「片段」的工程实现。**

#### 1.3.3 其他标准里的双库痕迹（逐项核实）

| 体系 | 规则本体 | 案例侧的表示 | 二者关系 | 一手性 |
|---|---|---|---|---|
| **欧盟 Cellar / CDM** | `celex/3*`（立法） | `celex/6*`（判例） | `cdm:work_cited_by_work`，**片段级** | ★★★ **一手，本分片实测** |
| **DSA 透明度数据库** | 平台政策 | **法定结构化判定记录**（Art 17(3) 六字段 + Art 24(5) 机器可读数据库） | 平台提交判定，**监管方与公众可读** | ★★★ **一手，`dsa-art34-eurlex.txt` L1499 与 L1199-1252** |
| **Meta × Oversight Board** | Community Standards | 个案裁决 + **四个处置码** | **案例回写规则**，且有逐条处置台账 | ★★ 一手（via R4 §1.2.2，`about.fb.com` 官方 PDF） |
| **LegalRuleML（OASIS）** | `PrescriptiveStatement`（deontic） | `ConstitutiveStatement`（构成性陈述） | 分开建模 | ★★ R3 §4.1（`raw/legalruleml-core-spec.txt`）**—— 注意：本分片核实 R3 只引用了 `PrescriptiveStatement` 与 `ConstitutiveStatement` 两类；「LegalRuleML 有 `Case`/`CaseLaw` 概念」这一说法本分片未在 R3 证据中检索到直接原文，故不改称其为已核实** |
| **软件工程** | 源码 | issue + regression test | 缺陷**转化为**回归用例 | ★★ 通用工程实践（见 §1.5） |

> **【判断】** 一处必须更正的引用**：主交付物 §3.2.1 的表格里写 `LegalRuleML | PrescriptiveStatement | Case（有 CaseLaw 概念） | 分开建模`。**本分片在 R3 的全部证据（`_evidence/R3/raw/legalruleml-core-spec.txt`，7,391 行）中检索 `CaseLaw` / `isCase` 未命中。** 建议把该行的「案例库」列改为 `ConstitutiveStatement`（R3 §4.1 已核实其在规范中出现 962 次 `<lrml:ConstitutiveStatement` 开标签），或标注为未核实。**这是对主交付物的一处更正建议。**

#### 1.3.4 一个必须说清的边界：双库结构**不等于**「先例约束」

**【判断】** 委托方可能担心「错题本会不会让一条个案绑架全局规则」。这个担心是对的，而且有一手证据支持正确的做法。**

> **【原文】**（R4 §1.2.2 引 Meta 官方，关于 Oversight Board 裁决的执行方式）
> `**Implementing the Board's Decisions At Scale**  We've also started the process of reinstating identical content with parallel context in the following cases: **Uyghur Muslims**, **Hydroxychloroquine, Azithromycin and COVID-19**, and **a Nazi Quote**. **These actions will affect not only content previously posted on Facebook and Instagram but also future content.**`
> `For cases where the board upholds our final judgment, we will continue to ensure identical content with parallel context remains either up or down in line with the board's decision.`

**【判断】** 关键词是 `identical content with parallel context`（相同内容 + 平行语境）。** 这给出了**先例的适用边界**：

```
个案裁决的效力范围 = 相同内容 + 平行语境，且显式声明影响「过去 + 未来」
```

**【判断】** 对委托方的落地方式：错题不自动变成规则，它变成规则的**适用条件**。** 一条错题 `X 在语境 A 下应判违规` 的泛化形式是 `X 在语境 A 下 → 违规`，**而不是** `X → 违规`。**这个区别就是「个例绑架全局」与「案例沉淀为规则」的分界线。**

### 1.4 从错题到规则变更的回流闭环（谁提议/谁审批/多久/防回归）

**【判断】** 委托方问了四个具体问题：谁提议、谁审批、多久一次、如何防回归。四个问题各有一手证据，且四个答案都指向同一个结论：**闭环的关键不在「改规则」，而在「不许未经回归就改规则」。**

#### 1.4.1 谁提议 —— 提议者是「分诊环节」，不是发现错题的人

**【判断】** 关键证据：Meta 的机制里，**提案的产生者是独立的裁决机构（Oversight Board），执行者才是 Meta**。** 这不是组织冗余，是职责分离。

> **【原文】**（R4 §1.2.2 引 Meta 官方 PDF，逐字）
> `We identified **19 distinct recommendations** and have responded to each of them below. We carefully considered these recommendations and today are committing to **fully implement 15 of them**. We are also **implementing one recommendation in part**, **still assessing two** of them, and **taking no further action on one** of them. In determining how to respond to these recommendations, we consider **the feasibility of implementation and the impact to our users**.`

**【判断】** 映射到委托方（对照主交付物 §3.3 的五个环）：**

| 角色 | Meta 的对应者 | Momcozy 的对应者 | 主交付物 §3.3 的说法 |
|---|---|---|---|
| **谁发现错题** | 内容审核 + 举报 | 环 3 运行取证（系统） | `环 3` |
| **谁提议改规则** | **Oversight Board（独立机构）** | **环 4 误差分析与回写（合规负责人）** | `环 4` |
| **谁审批** | **Meta 政策团队**（`we are committing to fully implement`） | **规则库负责人（环 1）** | `环 1` |
| **谁不能是同一人** | Board ≠ Meta | **环 4 ≠ 环 1** | 主交付物 §3.3 硬约束 1 |

**【判断】** 主交付物 §3.3 的硬约束 1（`环 1 与环 4 负责人不能同一人`）在本分片找到一条更强的法源：** 不是「最佳实践」，而是 AI Act Recital 62 要求的 `justification and documentation of any significant decisions and actions taken`（§2.2.2(d)）—— **「谁提议」与「谁批准」必须可分辨，否则「justification」在纸上无法成立。**

#### 1.4.2 谁审批 —— 审批者必须能说「不做」，且有四个明确终态

**【判断】** Meta 的四个处置码是**审批结果的标准枚举**，可直接抄：**

> **【原文】**（R4 §1.2.2 引 Meta 官方 PDF，逐字，四值定义）
> `- **Implementing fully**: Facebook agrees with the recommendation and has or will implement it in full.`
> `- **Implementing in part**: Facebook agrees with the overall aim of the recommendation and has or will implement work related to the board's guidance.`
> `- **Assessing feasibility**: Facebook is assessing the feasibility and impact of the recommendation and will provide further updates in the future.`
> `- **No further action**: Facebook will not implement the recommendation, either due to a lack of feasibility or disagreement about how to reach the desired outcome.`

**【判断】** 四个处置码里最重要的是第三个 `Assessing feasibility` —— 它给「我暂时决定不了」一个正式位置。** 这与 §3.4「不确定如何成为可存储状态」是同一个设计原则在**规则变更流程**上的应用：**如果处置码里没有「评估中」，那么所有悬而未决的建议都会被强行压成「改」或「不改」，而后者会静默丢弃信号。**

**【判断】** Meta 在 19 条里的实际分布：`15 fully` + `1 in part` + `2 assessing` + `1 no action`** —— **即 3/19 = 15.8% 的建议没有被完全采纳。** 这个比例说明：**审批环节是一个真实的过滤环节，不是橡皮图章。** 如果委托方的错题本 100% 转化成规则修订，那说明审批环节不存在。

#### 1.4.3 多久一次 —— 三层节奏，各有证据

| 层 | 节奏 | 逐字证据 | 谁做 |
|---|---|---|---|
| **指南微调** | **每周** | YouTube：`**Every week, our Trust & Safety leadership meet with quality assurance leads from across the globe** … to **discuss particularly thorny decisions and review the quality of our enforcement**. If needed, **guideline tweaks are then drafted to address gaps or to provide clarity for edge cases.**`（R4 §1.5） | 质量保证负责人 + 领导层 |
| **政策变更** | 事件驱动（个案裁决触发） | Meta：`19 distinct recommendations and have responded to each of them below`（一次性回应一批） | 政策团队 |
| **风险评估重做** | **至少每年一次 + 重大变更前** | DSA Art 34(1)：`at least once every year thereafter, and in any event prior to deploying functionalities that are likely to have a critical impact` | 合规职能部门 |

**【判断】** ★ 这三层的粒度差异是本节最重要的一条可操作结论：**

```
每周   → 改「指南」（guideline）—— 措辞、边界例、豁免词
每案   → 改「政策/规则」（policy/rule）—— 新增或删除一条规则
每年   → 重做「风险评估」（risk assessment）—— 等级与边界重新校准
```

**【判断】** 主交付物 §3.4 已经指出了这个粒度问题（`政策一年动几次，指南每周动`），但它把两者都放在「环 1 月度」。本分片的补强是：**YouTube 给出的节奏是「周」而不是「月」**，而 DSA 给出的上限是「年」。** 因此建议主交付物 §3.3 的环 1 拆成两个子节奏：

| 环 | 主交付物现说法 | 建议修正 |
|---|---|---|
| 环 1 规则生产 | 月度 | **拆成：环 1a 指南微调（周）+ 环 1b 规则增删（月/事件驱动）** |
| 环 4 误差分析与回写 | 周会 + 月报 + 季盘点 | 保留，但明确「周会」产出的是**指南微调建议**，不是规则修订 |

#### 1.4.4 防回归 —— 三个硬机制，缺一不可

**【判断】** 「防回归」是这四个问题里唯一有**不可绕过的机制**的一个。R4 §4.1 给了四条原则，本节补上它们的出处与委托方的落地形态。**

**（a）每条修订必须配 ≥1 正例 + ≥1 反例 + ≥1 对抗样本**

> **【原文】**（R4 §7.1 环 2 输入，引 Gab Hate Corpus）
> `passing a test of about thirty messages that had been previously annotated and agreed upon by the authors`

> **【原文】**（R4 §7.1 环 2 准入要求，引 NIST AI 600-1）
> `MP-2.3-005 … regular adversarial testing`

**（b）错题样本只增不减，永久留在 golden set**

R4 §4.1 原则 3：`黄金集必须包含"已知 bug 对应的测试用例"，且每条 bug 只增不减`。

**【判断】** 这是把错题本与回归测试连起来的那颗螺丝。** 没有它，错题本修完一条就丢掉，同样的错会以完全一样的形式再次发生。

**（c）回归门不可特批绕过**

主交付物 §3.3 硬约束 2：`环 2 不可特批绕过`。

**【判断】** 本分片为这条补一条法源：** 见 §2.4.4 引用的 NIST CAUTIONARY NOTE —— `Risks that are on the borderline between bins … must ultimately be assigned to one bin. This determination could have a significant effect on the risk prioritization process.` **归箱决定对优先级有实质影响，因此它不能由「特批」绕过。**

#### 1.4.5 ★ 一处必须指出的缺口：委托方的环 4 没有「拒绝入口」

**【判断】** 现有设计的环 4 输入是「四格 + 抽样人审」。但 Meta 的教训指出：**最贵的错题来自外部，不是内部抽查。****

> **【原文】**（R4 §1.2.2，Meta 拒绝 recommendation 13 的理由）
> `We will take no further action on this recommendation **because it is not feasible to track this information**. … While the board has requested details about the relative error rates of enforcement decisions made through cross check, **we do not have systems in place to make this comparison. Our measurement accuracy systems are not designed to review the small number of decisions made through the cross check process.**`

**【判断】** Meta 承认「事后补不上」。** 委托方现在**完全没有采平台侧的判定**（拒登、下架、限制投放）—— 见 §2.4.2 的缺口表。**这意味着委托方会重复 Meta 的错误，而且是在更容易避免的地方：因为平台的判定结果通常会通过广告后台的通知给出，它是可采的。**

**【判断】** 建议在环 4 的输入里增加第四个入口：`平台反馈`**（对应 R4 §7.2.2 的 `外部反馈入口`：`把客服/平台拒登通知/AI 平台的政策警告回填成 FN 候选`）。

### 1.5 与 bug tracker → regression test 的类比是否成立

**【判断】** 成立，但只成立一半。这是本节要给出的明确答案：类比在「结构」上成立，在「真值来源」上不成立 —— 而这个差别恰好决定了委托方该怎么建。**

#### 1.5.1 结构上成立的部分（四条对应关系）

| bug tracker 机制 | 错题本对应物 | 证据 |
|---|---|---|
| issue 有唯一 ID + 状态机 | `EB-NNNN` + `处置码` 四值 | R4 §7.2 第 5 项；Meta 四处置码 |
| issue 指派给负责人 + 时间戳 | `处置人` + `处置日期` | R4 §7.2 末尾四字段 |
| 修复必须附一个失败的测试 | 规则修订必须附 ≥1 正例 + ≥1 反例 + 对抗样本 | R4 §4.1 原则 3；GHC `thirty messages` |
| 测试永久保留，防同一 bug 复发 | 错题样本永久留在 golden set，**只增不减** | R4 §4.1 原则 3 |

**【判断】** 四条对应关系全部有证据，所以「结构类比成立」是有据的。**

#### 1.5.2 ★ 结构上不成立的部分：真值来源不同，且这一点决定了设计

**【判断】** 这是本节的核心发现：**

| | **bug tracker** | **错题本** |
|---|---|---|
| **真值从哪来** | **可执行规格 / 测试期望** —— 是**外部给定的**，不依赖人的判断 | **人工复判** —— 是**人给的**，且人之间可能不一致 |
| **一个 bug 是不是 bug，有争议吗** | **原则上没有**（规格说应该输出 5，程序输出 4 → 是 bug） | **★ 有** —— 「这条文案算不算功效承诺」本身就是争议对象 |
| **因此需要什么额外的度量** | 不需要 —— 通过/失败是二值的 | **需要一致性系数 α** —— 因为「真相」本身需要先被证明是稳定的 |

**【判断】** 这个差别有直接的一手证据支撑：**

> **【原文】**（R4 §4.1 原则 1 所引，YouTube 官方对 enforcement guidelines 修订目的的说明）
> `we begin revising the guidelines so that they can be accurately interpreted across the larger, more diverse set of moderators. **This process can take a few months.**`

**【判断】** YouTube 花「几个月」改指南，目的不是让机器判得准，是让**人**判得一致。** bug tracker 里没有对应动作 —— 因为规格不需要「被更多人一致地解释」。

> **【原文】**（Krippendorff 2004，R4 / 主交付物 §4.4.1 已引）
> `the reliability of each variable should be measured and **the smallest among them should be taken as the reliability of the whole system**`
> `An acceptable level of agreement … must be chosen depending on the costs of drawing invalid conclusions`

**【判断】** 结论：**
> **bug tracker 的类比成立到「结构」为止。多出来的一层是：错题本的「真值」必须先被证明是稳定的（α 达标），才能作为回归测试的期望值。**
> **否则就是在用一组本身不一致的期望去测规则 —— 这正是主交付物 §4.4.1 说的「机器拟合了一组本身就不一致的判断」。**

#### 1.5.3 一个具体的推论：错题本有两种「门」，顺序不能颠倒

**【判断】** 由 §1.5.2 直接推出：**

```
第一道门（α 门）：这条错题的「人工复判结论」可信吗？
                → 需要 ≥2 名复判者，且计算一致性
                → α < .667  → 这条错题的结论不可用，转入「规则边界不清」类
第二道门（回归门）：规则修订后 golden set 是否 PASS？
                → FAIL 不许发布
```

**【判断】** 委托方现在**两道门都不存在**：`检查人` 非空率 0.0%（第一道门无人执行），`golden set` 未建（第二道门不存在）。**

**【判断】** 这不是一个「工程成熟度」问题，而是一个**证据链断裂**问题**：主交付物 §3.3 的环 2 与环 4 都依赖人工复判的产出，而人工复判从未发生（`风险等级 × 处理状态` 完全对角，见主交付物 §4.5）。**因此 P0 的第一件事不是建回归门，是把第一道门开起来。**

## 2. 严重等级的自主定档

### 2.1 likelihood × impact 的标准出处

**【判断】** 委托方问「严重等级从哪来」时，隐含假设是「等级是外部给定的」。这个假设在跨境内容治理里不成立 —— 没有任何一个外部机构给过 Momcozy 一套等级。所以唯一可用的答案就是「自己定档」，而自己定档有一个权威的标准做法，出处是 NIST SP 800-30 Rev.1。**

#### 2.1.1 第一手定义（逐字，NIST SP 800-30 Rev.1 §2.3）

> **【原文】**（`_evidence/R8/nist-sp800-30r1.txt` L675-678，Appendix/§2.3 KEY RISK CONCEPTS；SOURCE_URL: https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-30r1.pdf，HTTP 200，334KB）
> `Risk is a measure of the extent to which an entity is threatened by a potential circumstance or event, and is typically a function of: (i) the adverse impacts that would arise if the circumstance or event occurs; and (ii) the likelihood of occurrence.`

> **【原文】**（同文件 L685-693）
> `A risk assessment methodology typically includes: (i) a risk assessment process (as described in Chapter Three); (ii) an explicit risk model, defining key terms and assessable risk factors and the relationships among the factors; (iii) an assessment approach (e.g., quantitative, qualitative, or semi-qualitative), specifying the range of values those risk factors can assume during the risk assessment and how combinations of risk factors are identified/analyzed so that values of those factors can be functionally combined to evaluate risk; and (iv) an analysis approach (e.g., threat-oriented, asset/impact-oriented, or vulnerability-oriented), describing how combinations of risk factors are identified/analyzed to ensure adequate coverage of the problem space at a consistent level of detail.`

**【判断】** 这四件套就是「一个团队如何自己定档」的完整骨架，而且它明确允许组织自定义：**

| SP 800-30 要求的四件 | Momcozy 对应的产物 | 现状 |
|---|---|---|
| (i) 风险评估流程 | §2.5 的定档步骤 | **不存在** |
| (ii) 显式风险模型（关键术语 + 可评估风险因子 + 因子间关系） | `severity` / `exposure` / `disposition` 三字段的关系 | **不存在**（四档是枚举，无模型） |
| (iii) 评估方法（quantitative / qualitative / semi-qualitative）+ 取值范围 | 现有四档 = 一个 qualitative 序数尺，**但从未声明它是哪一种** | **未声明** |
| (iv) 分析取向（threat-oriented / asset-impact-oriented / vulnerability-oriented） | — | **未选择** |

#### 2.1.2 ★ 关键授权：尺度是「组织自定义」的，标准只给模板

**【判断】** 这是本节最重要的一句话 —— NIST 明确说标度可以改。**

> **【原文】**（同文件 L4813-4820，TABLE H-4 TEMPLATE – IDENTIFICATION OF ADVERSE IMPACTS，列头三处均写）
> `Table H-2 or Organization-defined` / `Table H-2 or Organization-defined` / `Table H-3 or Organization-defined`

> **【原文】**（同文件 L4527-4529，Appendix G 引言）
> `The assessment scales in this appendix can be used by organizations as a starting point with appropriate tailoring to adjust for any organization-specific conditions.`

**【判断】** 结论：委托方不需要「找到」一个等级标准，需要的是「声明一个」等级标准，并留下它是怎么来的。** 这与 R6 已核实的 GARM 现状是同一个逻辑 —— GARM 组织 2024-08-09 已解散，其框架仍在被 IAB Tech Lab 承载，但它不处理「跨法域 × 跨平台」的后果合成（见 §2.3）。

#### 2.1.3 官方给的五档标度（可直接裁剪为 Momcozy 的 severity 尺）

> **【原文】**（同文件 L4775-4792，TABLE H-3: ASSESSMENT SCALE – IMPACT OF THREAT EVENTS，逐档摘录）
> `Very High 96-100 10` — `The threat event could be expected to have multiple severe or catastrophic adverse effects on organizational operations, organizational assets, individuals, other organizations, or the Nation.`
> `High 80-95 8` — `The threat event could be expected to have a severe or catastrophic adverse effect … (iii) result in major financial loss; or (iv) result in severe or catastrophic harm to individuals involving loss of life or serious life-threatening injuries.`
> `Moderate 21-79 5` — `… (iii) result in significant financial loss; or (iv) result in significant harm to individuals that does not involve loss of life or serious life-threatening injuries.`
> `Low 5-20 2` — `… (iii) result in minor financial loss; or (iv) result in minor harm to individuals.`
> `Very Low 0-4 0` — `The threat event could be expected to have a negligible adverse effect …`

**【判断】** 三点可以直接搬：**

1. **五档，不是四档** —— 委托方现有四档（高危/审慎/待复核/合规）在档数上就少一档，这与主交付物 §4.2 的诊断一致（缺 L0 未覆盖、L5 例外/降级）。
2. **每档有「定性名 + 半定量区间 + 整数分」三重表示** —— 委托方现在只有定性名，**没有任何可计算的表示**，所以 §4.3 的 `severity × exposure` 无法执行。
3. **★ 影响描述里枚举了「后果的种类」**，且影响的对象是复数：`organizational operations, organizational assets, individuals, other organizations, or the Nation`。**这正是 §2.3「监管后果与商业后果如何合成」的原始模板** —— 一个 threat event 同时对五类对象产生后果，等级取这些后果的最大者。

#### 2.1.4 likelihood 的两段分解（被现有设计忽略的一处）

> **【原文】**（同文件 L898-905）
> `The likelihood of occurrence is a weighted risk factor based on an analysis of the probability that a given threat is capable of exploiting a given vulnerability (or set of vulnerabilities). The likelihood risk factor combines an estimate of the likelihood that the threat event will be initiated with an estimate of the likelihood of impact (i.e., the likelihood that the threat event results in adverse impacts). For adversarial threats, an assessment of likelihood of occurrence is typically based on: (i) adversary intent; (ii) adversary capability; and (iii) adversary targeting.`

> **【原文】**（同文件 L4586-4594，Appendix G 脚注 55）
> `The term likelihood, as discussed in this guideline, is not likelihood in the strict sense of the term; rather, it is a likelihood score. Risk assessors do not define a likelihood function in the statistical sense. Instead, risk assessors assign a score (or likelihood assessment) based on available evidence, experience, and expert judgment.`

**【判断】** 这条脚注是**对委托方最有用的一句免责**：委托方不必为 `exposure` 找一个统计意义上的概率函数。**「基于可得证据、经验与专家判断的分数」就是标准做法。** 现有三个字段（`近7天展示` / `近7天点击` / `近7天费用USD`）作为 `exposure` 的代理是**合规于标准的**，不需要额外采集。

**【判断】** 而且 likelihood 是两段乘积，不是一段**：
```
likelihood = P(事件被发起) × P(发起后造成影响)
```
对委托方直接映射：
- `P(内容被平台发现)` ← 展示量 / 投放地区数 / 是否在平台重点巡查品类
- `P(发现后被判定违规)` ← 规则在该平台的确定性（H 族红线 vs U 族灰规则）

**现有四档完全没有第二段** —— 「这条内容会不会被平台看到」和「平台看到会不会判违规」是两个正交的问题，现在被压成了一个 `高危`。

#### 2.1.5 风险等级的合成矩阵（NIST 官方表，逐字）

> **【原文】**（同文件 L4883-4896，TABLE I-2: ASSESSMENT SCALE – LEVEL OF RISK (COMBINATION OF LIKELIHOOD AND IMPACT)）

| Likelihood ↓ ＼ Level of Impact → | Very Low | Low | Moderate | High | Very High |
|---|---|---|---|---|---|
| **Very High** | Very Low | Low | Moderate | High | **Very High** |
| **High** | Very Low | Low | Moderate | High | **High** |
| **Moderate** | Very Low | Low | Moderate | **Moderate** | **High** |
| **Low** | Very Low | Low | **Low** | **Low** | **Moderate** |
| **Very Low** | Very Low | **Very Low** | **Very Low** | **Low** | **Low** |

**【判断】** ★ 这张表有两个极易被忽略的结构特征，而它们恰好是委托方最需要的：**

1. **不是乘法表。** 如果它是 `likelihood × impact` 的乘积，`High × Moderate` 与 `Moderate × High` 应当相等。看表：`High likelihood × Moderate impact = Moderate`，`Moderate likelihood × High impact = High`。**两者不等 —— impact 的权重高于 likelihood。**
2. **底部三行被「削平」了。** `Low` 与 `Very Low` likelihood 行里，即使 impact 是 `Very High`，风险也只到 `Low`/`Moderate`。**即：极低发生概率会封顶风险等级。**

**【判断】** 这两点对委托方是可直接落地的规则**：一条「极高危但零曝光」的规则（如某小语种市场的红线表达）**不应与「高危且 20 万次展示」同档处置**。主交付物 §4.3 提出的 `severity × exposure` 是**乘法**，按 NIST 官方表这会**高估低曝光内容的等级**。**建议改为查表（matrix）而不是相乘** —— 这是对主交付物 §4.3 的一处修正。

#### 2.1.6 FMEA / risk matrix 的原始出处：本轮未取得一手

**【判断】** 任务书点名要 `MIL-STD-1629` / `MIL-P-1629` 作为 FMEA 的原始出处。本轮**未取得**这两个标准的正文**（详见 §4 不可达来源）。**因此本分片不从 FMEA 推导任何设计建议**，只记录一条可核实的替代路径：

- **NIST SP 800-30 Rev.1 §2.3 明确把 `quantitative / qualitative / semi-qualitative` 三选一作为「评估方法」的必填项**，并给出五档半定量标度（96-100 / 80-95 / 21-79 / 5-20 / 0-4 + 整数分 10/8/5/2/0）。**这套标度本身就是 FMEA 家族「序数 + 半定量分数」的做法**，且是可直接引用的政府标准正文。
- **FMEA 的两个标志性构件**（Severity / Occurrence / Detection 三因子与 RPN 乘积）**在本轮证据中没有一手出处**，故不做断言。**未找到。**

**【判断】** 对委托方的操作含义**：**不要引用 FMEA 作为方法论依据，引用 NIST SP 800-30 Rev.1。** 前者本轮无源，后者有 334KB 全文且有明确的组织自定义授权。

### 2.2 内容治理领域的实际风险分级（DSA / EU AI Act / 其他）

**【判断】** 委托方要的不是「学界方法」，而是「真实在跑的内容治理系统怎么定档」。这一节给两套法定制度和一个负结论。**

#### 2.2.1 DSA 第 34 条：系统性风险评估 —— 唯一「内容治理领域」的法定风险分级

**【判断】** 这是本节最强的一条证据，因为它把「内容治理 + 风险分级 + 跨法域」三件事同时落在一条法条里。**

**（a）法条正文的结构：四个必评风险类别 + 「severity and probability」双因子**

> **【原文】**（`_evidence/R8/dsa-art34-eurlex.txt` L1717-1734；SOURCE_URL: https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32022R2065，HTTP 200，419KB）
> `Providers of very large online platforms and of very large online search engines shall diligently identify, analyse and assess any systemic risks in the Union stemming from the design or functioning of their service and its related systems, including algorithmic systems, or from the use made of their services.`
> `They shall carry out the risk assessments by the date of application referred to in Article 33(6), second subparagraph, and at least once every year thereafter, and in any event prior to deploying functionalities that are likely to have a critical impact on the risks identified pursuant to this Article. This risk assessment shall be specific to their services and proportionate to the systemic risks, taking into consideration their severity and probability, and shall include the following systemic risks:`
> `(a) the dissemination of illegal content through their services;`
> `(b) any actual or foreseeable negative effects for the exercise of fundamental rights, in particular the fundamental rights to human dignity enshrined in Article 1 of the Charter, to respect for private and family life enshrined in Article 7 of the Charter, to the protection of personal data enshrined in Article 8 of the Charter, to freedom of expression and information, including the freedom and pluralism of the media, enshrined in Article 11 of the Charter, to non-discrimination enshrined in Article 21 of the Charter, to respect for the rights of the child enshrined in Article 24 of the Charter and to a high-level of consumer protection enshrined in Article 38 of the Charter;`
> `(c) any actual or foreseeable negative effects on civic discourse and electoral processes, and public security;`
> `(d) any actual or foreseeable negative effects in relation to gender-based violence, the protection of public health and minors and serious negative consequences to the person's physical and mental well-being.`

**【判断】** 三条可直接搬进 Momcozy 设计的东西：**

1. **分级因子与 NIST SP 800-30 §2.3 完全同构** —— DSA 用的是 `severity and probability`，NIST 用的是 `adverse impacts` 与 `likelihood of occurrence`。**两个独立法域、两个独立领域（平台治理 / 信息安全）在同一结构上收敛**，这是「likelihood × impact 是这个问题的正确答案」的跨域旁证。
2. **风险类别是「后果的对象」分类，不是「内容的主题」分类** —— (a) 违法内容 / (b) 基本权利 / (c) 公民 discourse 与选举 / (d) 性别暴力、公共卫生、未成年人。**注意这与委托方现在的 `主题分类`（T1 医疗功效 / T3 权威背书…）是两个完全不同的切分轴**：一个是「内容长什么样」，一个是「伤害到谁」。**这两个轴必须都建，不能互相替代**（详见 §2.3）。
3. **`at least once every year thereafter` —— 法定校准周期是一年**，且**在部署重大新功能前必须重评**。

**（b）可操作化：DSA 给了「怎么估 severity」的具体分解（Recital 79）**

> **【原文】**（同文件 L373，Recital (79)）
> `In determining the significance of potential negative effects and impacts, providers should consider the severity of the potential impact and the probability of all such systemic risks. For example, they could assess whether the potential negative impact can affect a large number of persons, its potential irreversibility, or how difficult it is to remedy and restore the situation prevailing prior to the potential impact.`

**【判断】** ★★ 这段是本分片对 §2.3 最有用的一句。它把 `severity` 拆成三个可独立判断的子维度：**

| DSA Recital 79 的 severity 子维度 | 逐字 | 对 Momcozy 的映射 |
|---|---|---|
| **触及人数** | `can affect a large number of persons` | `近7天展示` / `近7天点击`（**主交付物 §4.3 的 exposure 已覆盖这一维**） |
| **不可逆性** | `its potential irreversibility` | **完全没建** —— 「平台已下架/已封号」不可逆，「要求改写」可逆 |
| **补救难度** | `how difficult it is to remedy and restore the situation prevailing prior to the potential impact` | **完全没建** —— 「删一条 listing」vs「恢复一个被封的店铺」差几个数量级 |

**【判断】** 这是一条对主交付物 §4.3 的实质补强。** 主交付物把 `exposure` 定义为 `f(近7天展示, 近7天点击, 费用)` —— **这只是 DSA 三子维度里的第一维（触及人数）**。DSA 明确要求另外两维（不可逆性、补救难度）也参与 severity 判断，而这两维**恰好是「平台封号风险」与「罚款风险」的差别所在**（见 §2.3）。

**（c）区域与语言必须进入评估 —— 这一句直接命中委托方的空白**

> **【原文】**（同文件 L1761，Art 34(2) 末段）
> `The assessment shall take into account specific regional or linguistic aspects, including when specific to a Member State.`

> **【原文】**（同文件 L393，Recital (81)）
> `Where risks are localised or there are linguistic differences, those providers should also account for this in their risk assessments.`

**【判断】** 「区域与语言差异必须进评估」是法定义务。** 委托方现状是「小语种覆盖 0%」（主交付物 §2.5.4 实测）—— 按 DSA 的结构，**这不是「还没做」，而是「评估本身不成立」**。这给 §3.5 的处方提供了法源：**空白必须被显式评估，不能默认通过。**

**（d）每年至少一次 + 重大变更前 —— 校准周期的法源**

**【判断】** 与 NIST SP 800-30 的 `the validity and usefulness of any risk assessment is bounded in time`（同文件 L673-674）合起来看，两套体系都认为风险等级有保质期。** 委托方现有等级从未校准（主交付物 §4.5 实测：`风险等级 × 处理状态` 完全对角，`检查人` 非空率 0.0%），**已经超出任何一套体系的保质期。**

#### 2.2.2 EU AI Act 第 6 条：高风险分级的三个可搬构件

**【判断】** AI Act 的分级不是「给内容定档」，是「给系统定档」。但它有两个构件对「没有外部等级时怎么自己定档」极有价值，而且都出自 Recital。**

**（a）风险分级的总原则：按 intensity 与 scope 定制规则**

> **【原文】**（`_evidence/R8/eu-aiact-art6-eurlex.txt` L148，Recital (26)；SOURCE_URL: https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689，HTTP 200，588KB）
> `In order to introduce a proportionate and effective set of binding rules for AI systems, a clearly defined risk-based approach should be followed. That approach should tailor the type and content of such rules to the intensity and scope of the risks that AI systems can generate. It is therefore necessary to prohibit certain unacceptable AI practices, to lay down requirements for high-risk AI systems and obligations for the relevant operators, and to lay down transparency obligations for certain AI systems.`

**【判断】** `intensity`（强度）× `scope`（范围）又是 likelihood × impact 的第三次跨域复现** —— 而且这一句明确说「规则的类型与内容应当按风险定制」。**对委托方的含义：21 条规则不应该有同一种处置强度。现有四档确实是分层的，但处置权限、时效、复核要求没有跟着档位走。**

**（b）★★ 定档公式（逐字）：severity + probability + 预设领域，三者同时满足**

> **【原文】**（同文件 L252，Recital (52)）
> `it is appropriate to classify them as high-risk if, in light of their intended purpose, they pose a high risk of harm to the health and safety or the fundamental rights of persons, taking into account both the severity of the possible harm and its probability of occurrence and they are used in a number of specifically pre-defined areas specified in this Regulation.`

**【判断】** 这是三个因子，不是两个：**

```
高风险 = f( severity, probability ) AND ( 用途落在预设领域清单内 )
```

**换句话说：AI Act 认为「severity × probability 算出来高」还不够，还要「落在预设的敏感领域清单里」才算高风险。** 这与 NIST 的纯矩阵法不同 —— **AI Act 用的是「矩阵 + 领域清单」双闸门**。

**【判断】** 对 Momcozy 的直接含义：这正好是「国家 × 品类 × 平台 × 内容类型」四维笛卡尔积的正确用法。** 委托方现在把四维当成**规则的作用域**（主交付物 §2.3），但 AI Act 的用法是：**四维组合本身可以是一个「敏感领域清单」的判定条件** —— 例如「美国 × 母婴 × Amazon × 医疗功效」是一个敏感组合，「日本 × 母婴 × 官网 × 一般描述」不是。**两者相加才定档，而不是让 severity 单独定档。**

**（c）★★★ 「列入清单但可论证为非高风险」—— 一份可复用的空白处理范式**

> **【原文】**（同文件 L256，Recital (53)，节选）
> `It is also important to clarify that there may be specific cases in which AI systems referred to in pre-defined areas specified in this Regulation do not lead to a significant risk of harm to the legal interests protected under those areas because they do not materially influence the decision-making or do not harm those interests substantially.`
> `… To ensure traceability and transparency, a provider who considers that an AI system is not high-risk on the basis of the conditions referred to above should draw up documentation of the assessment before that system is placed on the market or put into service and should provide that documentation to national competent authorities upon request. Such a provider should be obliged to register the AI system in the EU database established under this Regulation.`

**【判断】** ★ 这个机制值得整段抄，因为它是「有规则但结论是没有风险」这件事被正式建模的唯一一手范例。** 它的四个要件是：

| AI Act Recital 53 的机制 | 对 Momcozy 的翻译 |
|---|---|
| 系统落在高风险预设领域内 | 内容落在「国家 × 品类 × 平台 × 类型」的敏感组合内 |
| 但**可以论证**它不实质影响决策 / 不实质伤害 | **但可以论证这条内容没有实质风险** |
| **必须在上线前**书面记录该论证 | **必须在放行前**留下「为什么判它合规」的记录 |
| **必须登记进数据库**，监管方可索取 | **必须落库**，合规负责人可抽查 |

**【判断】** 这就是 §3.4「『不确定』如何成为可存储状态」的另一半答案** —— 不只是「不确定」要存，**「我确认它没问题」也要存，而且要存论证**。委托方现在的 `合规·绿` 是一个**零论证的结论**：291 条里 157 条标绿，没有任何一条记录了「为什么」。

**（d）风险管理制度必须是全生命周期、定期复审的**

> **【原文】**（同文件 L304，Recital (62)）
> `The risk-management system should consist of a continuous, iterative process that is planned and run throughout the entire lifecycle of a high-risk AI system. … The risk-management system should be regularly reviewed and updated to ensure its continuing effectiveness, as well as justification and documentation of any significant decisions and actions taken subject to this Regulation.`

**【判断】** `justification and documentation of any significant decisions` —— 「重大决定必须留理由」是法定要求。** 委托方的 `检查人` 列非空率 0.0%，**这条在法务意义上不是「流程不完善」，是「无记录」。**

#### 2.2.3 Ofcom 的 risk assessment guidance：本轮未取得正文（一次尝试后放弃）

**【判断】** 任务书点名 Ofcom，并要求「试一次就放弃」。实测：`https://www.ofcom.org.uk/online-safety/illegal-and-harmful-content/` 返回 HTTP 403（Cloudflare），尝试一次即停止。**

- 本地已存的抓取产物：`_evidence/R8/ofcom-risk-assessment-guidance.txt`（182 字节）、`_evidence/R8/ofcom-rsm-guidance.txt`（229 字节）—— **均为 403 拦截页，无正文**。
- Ofcom 的两条引文（`Identify whether there are any additional characteristics or functionalities … not in the … Profiles, which could increase the risk` 与 Step 3 的 `the alternative measures that have been or are planned to be implemented instead …`）**来自 R4 §6.2/§6.7 的既有抓取**，本分片**只引用 R4，不重新声称已取得 Ofcom 原文**。
- **未取得 Ofcom risk assessment guidance 正文。未找到。**

#### 2.2.4 一个必须说清的负结论

**【判断】** 本轮穷尽检索后未找到任何「跨境卖家自建内容规则库严重等级」的外部标准。** 已核实的三类来源分别是：

| 来源类型 | 代表 | 为什么不能直接用 |
|---|---|---|
| **平台政策等级** | Meta / YouTube / TikTok / Google Ads | **R1 §5 已覆盖**，且它是平台对**平台自己**的分级，不是卖家对**自己投放**的分级 |
| **广告业内容分级** | GARM / IAB Tech Lab | **R6 §1.2 已覆盖**，且 GARM 组织 2024-08-09 已解散 |
| **法定风险评估** | DSA Art 34 / AI Act Art 6 | **管的是「平台」和「AI 系统」，不是「一条广告文案」** |

**【判断】** 结论：委托方不可能「找到」一个现成的等级表。** 正确做法是**用 NIST SP 800-30 的四件套骨架 + DSA Recital 79 的三子维度 + AI Act Recital 53 的论证留痕机制，自己造一个并声明它**。§2.5 给出分步做法。

### 2.3 监管后果与商业后果的合成

**【判断】** 任务书里这一问的措辞很精确：「平台封号风险」与「某国罚款风险」不是同一种严重。这一节要回答的是：两个不同量纲的后果，怎么合成一个等级。**

#### 2.3.1 第一步：承认「后果的对象」是复数，不是单一维度

> **【原文】**（`_evidence/R8/nist-sp800-30r1.txt` L4775-4792，TABLE H-3，五档描述均重复同一串对象）
> `… adverse effects on organizational operations, organizational assets, individuals, other organizations, or the Nation.`

**【判断】** NIST 明确列了五种后果承受者。** 委托方当前的四档只编码了「内容有多危险」，**没有编码「危险落到谁头上」**：

| NIST 的后果对象 | Momcozy 对应的具体对象 | 现有字段能否表达 |
|---|---|---|
| `organizational operations` | 店铺运营被中断（listing 下架、账号限制） | **不能** |
| `organizational assets` | 品牌资产、广告账户余额、店铺权重 | **不能** |
| `individuals` | 消费者（虚假医疗功效伤害） | 部分（H 族红线隐含） |
| `other organizations` | 平台（Amazon/Meta/TikTok）、经销商 | **不能** |
| `the Nation` | **各国监管机关**（FTC / 各国广告法 / DSA） | **不能** |

#### 2.3.2 第二步：监管后果（法域侧）—— DSA 给了四条法定分类

**【判断】** DSA Art 34(1)(a)-(d) 的四类系统性风险，正是「监管后果」的权威四分法**（原文见 §2.2.1）：

| DSA 类别 | 后果承受者 | 对 Momcozy 的典型触发 |
|---|---|---|
| **(a) 违法内容传播** | 国家 / 消费者 | 虚假医疗功效（FTC / 各国广告法 / 药监） |
| **(b) 基本权利负面影响** | 个人 | 歧视性表述；不尊重儿童权利（母婴品类的特殊风险） |
| **(c) 公民 discourse 与公共安全** | 国家 | 低频，但一旦触发量级最高 |
| **(d) 性别暴力 / 公共卫生 / 未成年人 / 身心健康** | 个人 + 国家 | **★ 母婴品类的主战场** —— 「堵奶」「乳腺炎」类表述同时命中 (d) |

**【判断】** ★ 对 Momcozy，(d) 是最重要的一类，而它现在完全没有独立位置。** 委托方的 H 族红线是「严格限制」的笼统集合，没有区分「违法」（监管罚款）与「伤害个体」（消费者伤害 + 舆情）。

#### 2.3.3 第三步：商业后果（平台侧）—— 一手证据显示是**三级阶梯**，不是单一「封号」

**【判断】** 这一节用 R7 的四个平台一手条款，证明商业后果是一条从「内容」到「账号」的阶梯。这是「平台封号风险」的真实结构。**

**（a）GitHub：五级阶梯，逐字**

> **【原文】**（`_evidence/R7/github-community-guidelines.txt` L265-275）
> `Where we have decided that moderation action is warranted, these are some of the ways we may respond:`
> `Removing the offending content`
> `Blocking or disabling the offending content`
> `Downgrading the visibility of the offending content`
> `Hiding a user account or organization from public view`
> `Suspending a user account or organization`

> **【原文】**（`_evidence/R7/github-acceptable-use.txt` L350-356）
> **（逐行原样，含 Markdown 链接语法，`/en/site-policy/...` 为链接目标）**
> `Enforcement. GitHub retains full discretion to`
> `[take action](/en/site-policy/github-terms/github-community-guidelines#what-happens-if-someone-violates-githubs-policies)`
> `in response to a violation of these policies, including account suspension, account`
> `[termination](/en/site-policy/github-terms/github-terms-of-service#3-github-may-terminate)`
> `, or`
> `[removal](/en/site-policy/github-terms/github-terms-of-service#2-github-may-remove-content)`
> `of content.`
>
> **去链接后的连续文本**（供直接引用，本分片实际使用的形态）：`Enforcement. GitHub retains full discretion to take action in response to a violation of these policies, including account suspension, account termination, or removal of content.`
> **⚠️ 引用提示**：上句为**去除 Markdown 链接标记后的渲染文本**，非源文件逐字连续串。**逐字引用时应使用上面的分行原样版本。**

**【判断】** ★★ 这个阶梯是本分片对 §2.3 的核心发现。它有三个层级，而这三个层级的经济后果量级完全不同：**

```
第 1 级  内容级   Removing / Blocking / Disabling the content      → 损失 = 这一条内容的投放
第 2 级  可见性级 Downgrading the visibility of the content         → 损失 = 这条内容的自然流量（可能远超广告花费）
第 3 级  账号级   Hiding the account / Suspending the account       → 损失 = 整个店铺的历史与未来
```

**【判断】** 委托方的四档风险等级只描述「内容有多危险」，完全没有指出「危险会在哪一级落地」。** 这是「平台封号风险 ≠ 某国罚款风险」这个问题的技术答案：**两者不仅后果对象不同，落地层级也不同 —— 封号是账号级（不可逆，见 DSA Recital 79 的 `irreversibility`），罚款是法人级。**

**（b）AWS：★ 「你有没有流程」本身就是减轻情节**

> **【原文】**（`_evidence/R7/aws-aup.txt` L283-285，Investigation and Enforcement）
> `We may investigate any suspected violation of this Policy, and remove or disable access to any content or resource that violates this Policy. You agree to cooperate with us to remedy any violation.`

> **【原文】**（同文件 L285）
> `When determining whether there has been a violation of this Policy, we may consider your ability and willingness to comply with this Policy, including the policies and processes you have in place to prevent or identify and remove any prohibited content or activity.`

**【判断】** ★★★ 这一句是本分片对「规则库值多少钱」最有力的一手论据。**

**平台在判断「是否构成违规」时，会考虑「你有哪些流程来防止/发现/移除违规内容」。** 也就是说：

> **规则库不只是「防漏放的内部工具」，它本身是一份可以让平台从轻处置的合规资产。**

**【判断】** 这直接改变了 §3.5 处方的论证方式。** 「建规则库」的商业理由不是「降低误拦率」，而是**在平台处置你时，你有一份可出示的流程证据**。这与 AI Act Recital 53 的「论证必须书面留痕」是同一个机制在商业侧与监管侧的两处体现。

**（c）Mozilla AMO：比例原则 + 整改期 + 故意/重复/失联三个升级触发器**

> **【原文】**（`_evidence/R7/amo-addon-policies.txt` L2387-2391，§8.1 Policy Enforcement）
> `Mozilla may reject or block affected versions or entire add-ons that don't comply with the above policies, depending on the extent of their non-compliance.`
> `Mozilla may attempt to contact the add-on's developer(s) and provide a reasonable time frame for the problems to be corrected before a block is deployed. If an add-on appears to intentionally or repeatedly violate the policies, or its developers have proven unreachable, unresponsive, or uncooperative, blocking may be immediate.`
> `Mozilla reserves the right to block or delete any developer's account on addons.mozilla.org, thereby preventing further use of the service, for certain violations of Mozilla's policies.`

**【判断】** 三个可搬的机制：**

| AMO 机制 | 逐字锚点 | 对 Momcozy 的映射 |
|---|---|---|
| **处置强度按违规范围定** | `depending on the extent of their non-compliance` | 等级不只看单条内容的严重度，还看**同一违规在账号内的扩散范围** |
| **默认给整改期，不直接封** | `provide a reasonable time frame for the problems to be corrected before a block is deployed` | **「发现 → 通知 → 限期整改 → 未改才封」是本阶梯的标准节奏**，委托方应假设平台会给窗口 |
| **★ 三个升级触发器：故意 / 重复 / 失联** | `intentionally or repeatedly violate the policies, or its developers have proven unreachable, unresponsive, or uncooperative` | **「重复违规」是升级到账号级的关键因子** —— 而这需要**跨时间累计违规次数**，委托方现有字段里没有 |

**【判断】** `repeatedly` 这个词把「历史」变成了一等公民。** 与 R4 §7.5.1 已记录的 Meta 梯度（`one month` → `2-year restriction` → `permanently disable`）方向一致：**平台侧后果是「单次严重度 × 累计次数」的函数，不是单次严重度的函数。**

#### 2.3.4 合成方法：不合并成一个数，而是输出一个「后果向量 + 取最差」

**【判断】** 这一节给出明确答案：监管后果与商业后果不应该合并成一个标量。理由有三条，每条有证据：**

1. **两者的「对象」不同** —— NIST Table H-3 的五类后果对象（§2.3.1）说明后果天然是复数的；把它们加权平均会掩盖最严重的那一类，**违反 Krippendorff 的元规则「取最小不取平均」**（R4 §5.2 / 主交付物 §4.4.2）。
2. **两者的「层级」不同** —— GitHub 的三级阶梯说明商业后果从内容级一路到账号级；**监管后果没有「账号级」这一层，它有「法人级」这一层。两者不可通约。**
3. **两者的「时间常数」不同** —— AMO 的整改期是「reasonable time frame」；DSA Art 34(3) 要求风险支持文件保留 **`at least three years`**（`_evidence/R8/dsa-art34-eurlex.txt` L1763）。**一个以天计，一个以年计。**

**建议的存储结构（与 NIST Table H-4 模板同构）：**

> **【原文】**（`_evidence/R8/nist-sp800-30r1.txt` L4808-4820，TABLE H-4: TEMPLATE – IDENTIFICATION OF ADVERSE IMPACTS，列头逐字）
> `Type of Impact` / `Impact` / `Affected Asset` / `Maximum Impact`
> （三个取值列均写：`Table H-2 or Organization-defined` / `Table H-3 or Organization-defined`）

**【判断】** NIST 官方的模板是四列：影响类型 / 影响 / 受影响资产 / 最大影响。** 直接映射为委托方的表：

| NIST Table H-4 列 | Momcozy 落地列 | 说明 |
|---|---|---|
| `Type of Impact` | `impact_type` | 枚举：`platform_content` / `platform_visibility` / `platform_account` / `regulatory_fine` / `consumer_harm` / `brand_reputation` |
| `Impact` | `impact_severity` | 按 §2.1.3 的 H-3 五档 |
| `Affected Asset` | `affected_asset` | listing / 店铺 / 广告账户 / 法人主体 / 品牌 |
| **`Maximum Impact`** | **`overall_severity`** | **★ 取所有行里的最大档** |

```
overall_severity = max(impact_severity over all impact rows)
```

**【判断】** 三条必须写进设计文档的约束：**

1. **`overall_severity` 是取 max，不是加权和** —— 依据 NIST Table H-4 的列名就是 `Maximum Impact`，且与 IAB `evaluation.py` 的 `overall_severity = max(per_category_severity)`（R6 §4.2.2 已核实）方向一致。
2. **`impact_type` 必须区分 `platform_*` 与 `regulatory_*`，不能合并成一个「严重度」** —— 这正是委托方问题里「不是同一种严重」的落地方式。
3. **`affected_asset` 必须显式** —— 因为 GitHub 的阶梯证明「哪一级资产受损」决定了损失量级。

**【判断】** 回归到 §2.1.5 的 NIST Table I-2**：合成后的 `overall_severity` 才是进 `likelihood × impact` 矩阵的那个 `impact`，而**不是单条内容的主题严重度**。这是本节对主交付物 §4.3 的第二处实质修正 —— 主交付物把 `severity` 当作规则的固有属性（`severity ∈ {L0..L5}`，规则的属性），**但按 NIST 的结构，`impact` 是「后果」的属性，同一条规则命中的内容可以产生不同的后果对象与不同的受影响资产。**

### 2.4 校准机制

**【判断】** 「多久重新校准一次」和「用什么数据校准」这两个问题，NIST SP 800-30 给了比 DSA 更细的答案，因为它在「风险容忍度」这个概念上给了完整的操作定义。而 DSA 给的是法定的最低频率。**

#### 2.4.1 校准的锚点不是「数据」，是「风险容忍度」—— 而它是组织自己声明的

> **【原文】**（`_evidence/R8/nist-sp800-30r1.txt` L1848-1852，§3.1 Risk Framing，Risk Tolerance and Uncertainty）
> `Organizations determine the levels and types of risk that are acceptable. Risk tolerance is determined as part of the organizational risk management strategy to ensure consistency across the organization. Organizations also provide guidance on how to identify reasons for uncertainty when risk factors are assessed, since uncertainty in one or more factors will propagate to the resulting evaluation of level of risk, and how to compensate for incomplete, imperfect, or assumption-dependent estimates.`

> **【原文】**（同文件 L1856-1858）
> `To compensate, organizations can take a variety of approaches to determine likelihood, ranging from assuming the worst-case likelihood (certain to happen sometime in the foreseeable future) to assuming that if an event has not been observed, it is unlikely to happen. Organizations also determine what levels of risk (combination of likelihood and impact) indicate that no further analysis of any risk factors is needed.`

**【判断】** ★★★ 这段是全文最重要的一处，它同时回答了 Q4 的校准问题和 Q5 的空白问题。**

**「假设最坏情况」与「假设没观察到就不会发生」是同一个量尺的两个极端** —— 这正是 **fail-closed 与 fail-open 的原始表述**，而且 NIST 明确说：**选哪一端是组织的风险容忍度决定的风险框架决策，不是技术决策。**

> **【判断】** 这句话把 §3.2 的问题重新定义了**：委托方问「空白走哪条路」，正确的问题不是「技术上哪个默认值对」，而是 **「谁有权声明本组织的风险容忍度」**。答案在 NIST 的组织结构里是 **Tier 1（组织层）** —— 见 §2.1.3 引用的 TABLE G-1：`Likelihood information and guidance specific to Tier 1` 由 Tier 1 提供给 Tier 2/Tier 3。

#### 2.4.2 用什么数据校准：NIST 的输入清单是「跨层级的」

> **【原文】**（同文件 L4694-4700，TABLE H-1 / TABLE G-1 中 Tier 3 层提供的输入，逐条）
> `Historical data on successful and unsuccessful cyber attacks; attack detection rates.`
> `Security assessment reports (i.e., deficiencies in assessed controls identified as vulnerabilities).`
> `Results of monitoring activities (e.g., automated and nonautomated data feeds).`
> `Vulnerability assessments, Red Team reports, or other reports from analyses of information systems, subsystems, information technology products, devices, networks, or applications.`
> `Contingency Plans, Disaster Recovery Plans, Incident Reports.`
> `Vendor/manufacturer vulnerability reports.`

**【判断】** 这对委托方是一个「校准数据从哪来」的清单，翻译过来：**

| NIST 的输入 | Momcozy 的对应数据源 | 现状 |
|---|---|---|
| `Historical data on successful and unsuccessful … attacks; detection rates` | 291 条判定记录的 `命中规则 × 人工复判` 四格表 | **数据在，但从未做过四格分析**（主交付物 §4.5：表完全对角，说明没有人工复判） |
| `Security assessment reports (deficiencies … identified as vulnerabilities)` | **§1.2 的 B 类规则错题**（EB-R001–R011，11 条规则自身缺陷） | **已生成 11 条，未进入维护流程** |
| `Results of monitoring activities` | 平台政策变更监控 | **环 5 完全空缺**（主交付物 §3.3） |
| `Red Team reports` | 对抗样本测试（golden set 的对抗用例） | **未建** |
| `Incident Reports` | **平台通知 / 下架 / 拒登记录** | **★ 完全没采** |

**【判断】** ★ `Incident Reports` 这一条是委托方最大的数据缺口。** 规则表现状审计有 291 条**自己判的**记录，但没有一条**平台判的**记录（被拒登、被下架、被限制投放）。**这意味着一半的校准信号从未被采集** —— 依据是 §2.3 的 AWS 条款：平台在判断违规时会看你的流程，**而你甚至不知道平台判过你什么。**

#### 2.4.3 校准频率：四个来源给出三个不同的周期

| 来源 | 逐字锚点 | 周期 |
|---|---|---|
| **DSA Art 34(1)** | `at least once every year thereafter, and in any event prior to deploying functionalities that are likely to have a critical impact on the risks identified` | **至少每年一次 + 重大变更前** |
| **DSA Art 34(3)** | `shall preserve the supporting documents of the risk assessments for at least three years` | **支持文档留存 ≥3 年** |
| **EU AI Act Recital 62** | `The risk-management system should be regularly reviewed and updated to ensure its continuing effectiveness` | **定期复审**（未定周期） |
| **NIST SP 800-30 Step 4** | `Information derived from the ongoing monitoring of risk factors can be used to refresh risk assessments at whatever frequency deemed appropriate.` | **组织自定** |
| **NIST SP 800-30 Step 4** | `Organizations use the risk management strategy to convey key requirements for maintaining risk assessments including, for example, risk factors to monitor and the frequency of such monitoring.` | **组织必须在策略里写明** |
| **COM(2000)1 §6.3.5**（R4 §6.6.3 已核实） | `The measures may have to be modified or abolished by a particular deadline, in the light of new scientific findings` + `regular scientific monitoring` | **可复审 + 定期监测** |

**【判断】** 四个来源的公约数是：**
1. **有一个法定下限（1 年）**；
2. **有一个事件触发的立即重评（重大变更前）**；
3. **频率本身必须被书面声明**（NIST：`Organizations use the risk management strategy to convey … the frequency of such monitoring`）。

**【判断】** 对委托方的具体建议**：主交付物 §4.4.3 提的「周 / 月 / 季」三档是合理的，但**缺一条事件触发**。建议改为：

```
周  → 环 4 误差分析与回写（数据校准）
月  → 逐规则 α + 标出最差那条
季  → 重新校准 L3/L4 的划分（等级校准）
年  → 全量重评（对齐 DSA Art 34(1) 法定下限）
事件触发 → 平台政策变更 / 新法域上线 / 新品上市 / 平台通知违规 / 法规生效
留存 → 每次校准的支持文件留 ≥3 年（对齐 DSA Art 34(3)）
```

#### 2.4.4 ★ 一条必须写进设计文档的诚实声明：等级是粗尺，边界样本必须硬性归箱

> **【原文】**（`_evidence/R8/nist-sp800-30r1.txt` L5146-5157，Appendix J 之后的 CAUTIONARY NOTE）
> `Organizations are cautioned that risk assessments are often not precise instruments of measurement and reflect the limitations of the specific assessment methodologies, tools, and techniques employed—as well as the subjectivity, quality, and trustworthiness of the data used. Risk determinations may be very coarse due to the assessment approach selected, the uncertainty in the likelihood of occurrence and impact values, and the potential mischaracterization of threats. Risks that are on the borderline between bins using the organization-defined binning scales, must ultimately be assigned to one bin. This determination could have a significant effect on the risk prioritization process. Thus, organizations should incorporate as much information as practical on particular risks during the prioritization process to ensure that the values for risks are appropriately determined (e.g., very low, low, moderate, high, very high).`

**【判断】** 这段话的价值在于它是官方对「这套方法有多准」的自我限制声明。三处可直接引用：**

1. **`risk assessments are often not precise instruments of measurement`** —— **不要声称等级是「算出来的精确值」**。主交付物 §4.3 的标题「等级是算出来的」应当在此加一条限定。
2. **`Risks that are on the borderline between bins … must ultimately be assigned to one bin`** —— **边界样本必须硬性归箱，不能悬置**。这意味着 §3.4 的「不确定状态」必须是**归箱之外的独立字段**，不能靠「等级 = 待定」来表达。
3. **`This determination could have a significant effect on the risk prioritization process`** —— **归箱决定本身要留痕**，因为它对优先级有实质影响。

**【判断】** 与 §2.4.1 的「风险容忍度」合起来，校准的完整定义是：**
> **校准 = 定期检验「分箱边界」是否仍与组织声明的风险容忍度一致，并用真实后果数据（尤其是平台的 Incident 数据）修正边界。**
> **它校准的是边界，不是分数。**

### 2.5 可操作定档步骤（分步 + 每步证据来源）

**【判断】** 以下九步是「没有外部等级时，一个团队如何自己定档」的完整可执行流程。每一步都给出证据来源与产出物。九步的顺序不可调换 —— 因为每一步的输入是上一步的产出。**

#### 步骤 1：声明风险框架（Risk Framing）—— 谁承担什么后果

| 项 | 内容 |
|---|---|
| **动作** | 由**组织层**（不是执行层）书面声明：本组织接受哪些后果、不接受哪些后果 |
| **产出** | 一份《风险容忍度声明》，写明：① 5 类后果对象各自的可接受程度；② 采用哪种评估方法（quantitative / qualitative / semi-qualitative）；③ 分析取向（threat-oriented / asset-impact-oriented / vulnerability-oriented） |
| **证据来源** | NIST SP 800-30 §2.3 `A risk assessment methodology typically includes: (i) a risk assessment process …; (ii) an explicit risk model …; (iii) an assessment approach (e.g., quantitative, qualitative, or semi-qualitative) …; and (iv) an analysis approach …`；同文件 §3.1 `Organizations determine the levels and types of risk that are acceptable.` |
| **委托方的直接含义** | **这一步的回答者是法人/管理层，不是内容运营。** 因为它决定了「合规成本」与「平台风险」哪个优先 —— 这是商业决策。（§2.4.1） |

#### 步骤 2：选边 —— 声明不确定时的默认方向

| 项 | 内容 |
|---|---|
| **动作** | 声明：在信息不足时，假设最坏情况，还是假设未观察到即不发生 |
| **产出** | 一句话写进《风险容忍度声明》，并**说明它适用于哪一档**（不是全局一个默认） |
| **证据来源** | NIST SP 800-30 §3.1 `To compensate, organizations can take a variety of approaches to determine likelihood, ranging from assuming the worst-case likelihood (certain to happen sometime in the foreseeable future) to assuming that if an event has not been observed, it is unlikely to happen.`（§2.4.1 已引）；同文件 `The more risk averse, the greater the range of values considered. Organizations accepting greater risk or having a greater risk tolerance are more likely to require substantive evidence before giving serious consideration to threat events.`（L2077-2078） |
| **委托方的直接含义** | **这是 Q5「谁有权决定空白走哪条路」的答案**：决策者是组织层，依据是风险容忍度，不是技术团队。详见 §3.2。 |

#### 步骤 3：建「后果对象表」—— 把「谁受损」显式化

| 项 | 内容 |
|---|---|
| **动作** | 对每类可能的风险情形，填 NIST Table H-4 的四列 |
| **产出** | `impact_type` / `impact_severity` / `affected_asset` / `maximum_impact` 四列（见 §2.3.4） |
| **证据来源** | NIST SP 800-30 TABLE H-4 `Type of Impact` / `Impact` / `Affected Asset` / `Maximum Impact`（L4808-4820）；后果对象清单见 TABLE H-3 五档描述中重复出现的 `organizational operations, organizational assets, individuals, other organizations, or the Nation` |
| **委托方的直接含义** | **这一步把「平台封号」与「某国罚款」分成了两行，而不是两档。** 它们量纲不同、层级不同、时间常数不同（§2.3.4）。 |

#### 步骤 4：抄 DSA Recital 79 的三子维度，把 severity 拆开

| 项 | 内容 |
|---|---|
| **动作** | 对每一行后果，问三个问题：① 影响多少人？② 可逆吗？③ 补救有多难？ |
| **产出** | `reach` / `irreversibility` / `remediability` 三个子字段 |
| **证据来源** | DSA Recital (79) `they could assess whether the potential negative impact can affect a large number of persons, its potential irreversibility, or how difficult it is to remedy and restore the situation prevailing prior to the potential impact.`（`_evidence/R8/dsa-art34-eurlex.txt` L373） |
| **委托方的直接含义** | **这是对主交付物 §4.3 的第一处实质修正。** 主交付物的 `exposure = f(近7天展示, 近7天点击, 费用)` 只覆盖了第①维。**第②③维是「封号 vs 罚款」的真正区别所在，而它们现在完全没有字段。** |

#### 步骤 5：定标度 —— 用五档，不用四档，且每档要有分数

| 项 | 内容 |
|---|---|
| **动作** | 采用「定性名 + 半定量区间 + 整数分」三重表示 |
| **产出** | severity 尺：`Very Low 0-4 (0)` / `Low 5-20 (2)` / `Moderate 21-79 (5)` / `High 80-95 (8)` / `Very High 96-100 (10)` |
| **证据来源** | NIST SP 800-30 TABLE H-3（L4775-4792，逐档见 §2.1.3）；授权自定义见 TABLE H-4 的 `Table H-3 or Organization-defined` 与 Appendix G 引言 `with appropriate tailoring to adjust for any organization-specific conditions` |
| **委托方的直接含义** | **现有四档没有任何可计算的表示**，所以 §2.4 的校准和 §4.3 的矩阵都无法执行。**加分数是零成本的。** |

#### 步骤 6：建 likelihood 尺，并把 likelihood 拆成两段

| 项 | 内容 |
|---|---|
| **动作** | 分别估计 P(被平台发现) 与 P(发现后被判定违规)，再合成 |
| **产出** | `p_detected` / `p_upheld` / `likelihood` 三字段 |
| **证据来源** | NIST SP 800-30 §2.3 `The likelihood risk factor combines an estimate of the likelihood that the threat event will be initiated with an estimate of the likelihood of impact`（L900-902） |
| **委托方的直接含义** | **现有四档把两段压成了一段。** 一条「零曝光的高危表达」与「高曝光的高危表达」在 `p_detected` 上差别巨大，而它们的 `p_upheld` 可能相同。 |

#### 步骤 7：用官方矩阵合成，不要相乘

| 项 | 内容 |
|---|---|
| **动作** | 用 NIST TABLE I-2 的查表法，而不是 `severity × likelihood` 的乘法 |
| **产出** | `level_of_risk ∈ {Very Low, Low, Moderate, High, Very High}` |
| **证据来源** | NIST SP 800-30 TABLE I-2（L4883-4896，完整表见 §2.1.5）。**关键：`High likelihood × Moderate impact = Moderate`，而 `Moderate likelihood × High impact = High` —— 两者不等，impact 权重大于 likelihood；且 Very Low / Low likelihood 行会封顶风险等级。** |
| **委托方的直接含义** | **这是对主交付物 §4.3 的第二处实质修正。** 主交付物写 `risk_score = severity × exposure`（乘法）。按 NIST 官方表，**乘法会高估低曝光内容的等级**，而「封顶」机制是官方设计的一部分。 |

#### 步骤 8：等级 → 处置权限 → 一致性门槛 的三联绑定

| 项 | 内容 |
|---|---|
| **动作** | 每个等级同时绑定三件事：谁批准、要求多高的一致性、响应多快 |
| **产出** | `disposition` / `approval_authority` / `min_alpha` / `sla` 四列 |
| **证据来源** | ① 一致性门槛按代价分档：Krippendorff `An acceptable level of agreement … must be chosen depending on the costs of drawing invalid conclusions`（R4 / 主交付物 §4.4.1 已引）；② 处置权限见主交付物 §4.2.1；③ **法定留痕要求**：AI Act Recital 62 `justification and documentation of any significant decisions and actions taken`（`_evidence/R8/eu-aiact-art6-eurlex.txt` L304）；④ NIST `Organizations also determine what levels of risk (combination of likelihood and impact) indicate that no further analysis of any risk factors is needed.`（L1858） |
| **委托方的直接含义** | **现状是「等级 = 处理状态」的一一映射**（主交付物 §4.5：`风险等级 × 处理状态` 完全对角）。**等级必须至少绑定四件事，才有信息量。** |

#### 步骤 9：把校准节奏与留存期写成制度

| 项 | 内容 |
|---|---|
| **动作** | 写明频率（周/月/季/年 + 事件触发）、数据源、留存期、谁签字 |
| **产出** | 一段写进规则库治理文档的制度文本 |
| **证据来源** | DSA Art 34(1) `at least once every year thereafter, and in any event prior to deploying functionalities … critical impact`；DSA Art 34(3) `at least three years`；NIST Step 4 `Organizations use the risk management strategy to convey key requirements for maintaining risk assessments including, for example, risk factors to monitor and the frequency of such monitoring.`（L2485-2486） |
| **委托方的直接含义** | **现状是零校准**（`检查人` 非空率 0.0%）。留存期 ≥3 年是法定的，即使委托方不是 VLOP —— **它是「你能证明自己尽到注意义务」的唯一方式**，见 §2.3.3(b) 的 AWS 条款。 |

#### 2.5.1 一张自检表：九步里哪几步委托方已有数据

| 步骤 | 需要的数据 | 委托方是否已有 |
|---|---|---|
| 1 风险框架 | 无（是决策，不是数据） | **无（从未做过）** |
| 2 选边 | 无（是决策） | **无（现状是静默 fail-open，见 §3.1）** |
| 3 后果对象表 | 后果类型清单 | **无** |
| 4 severity 三子维度 | reach / irreversibility / remediability | reach **有**（展示/点击/费用），另两维**无** |
| 5 五档标度 | 无 | **无（现有四档且无分数）** |
| 6 likelihood 两段 | p_detected / p_upheld | **均无** |
| 7 矩阵合成 | 上两步的产出 | **无** |
| 8 三联绑定 | 处置权限 / α / SLA | **无**（α 从未算过） |
| 9 校准制度 | 频率 / 数据源 / 留存 | **无**（法定 3 年留存不存在） |

**【判断】** 九步里委托方只在第 4 步有一维数据。这张表本身就是「严重等级从哪来」的答案：不是找不到，是从来没建过。**

## 3. 空白处理

### 3.1 真实系统的空白立场

**【判断】** 委托方问「某个（国家 × 品类 × 平台 × 内容类型）组合没有规则时，真实的系统怎么处理」。答案是：没有一个真实系统会因为「没规则」而自动放行。但也没有一个真实系统会因为「没规则」而自动拦截 —— 它们全部走第三条路：显式转人工 + 强制记录。**

#### 3.1.1 平台政策侧：兜底全部是「条件式」的，没有无条件宽容

**【判断】** R4 §6.1 已逐字核实五家平台的兜底条款。本节只做一件事：**把它抽象成三种形态**，因为委托方需要的是形态，不是逐条对照。**

| 形态 | 定义 | 一手样本（逐字） | 对空白的处置 |
|---|---|---|---|
| **① 例外型** | 空白处不自动放行，但**具名例外**可以放行 | TikTok：`We recognize that **some content that would otherwise violate our rules may be in the public interest to view.** … We may allow content to remain on TikTok under public interest exceptions, including: **Documentary / Educational / Medical or Scientific / Counterspeech / Satirical / Artistic**`；且 `**We won't make exceptions for content that could cause extreme harm**` | **放行需要具名理由 + 有不可例外的上限档** |
| **② 覆盖宣告型** | 政策清单**声明自己非穷尽**，未列举 ≠ 允许 | YouTube：`These policies apply to all types of content on our platform … **This list isn't complete.**`；Google Ads：`Examples … (**non-exhaustive**)`；TikTok：`These examples are meant to guide you, but **they don't cover every situation.**` | **未列举时规则仍适用，责任在广告主** |
| **③ 义务转移型** | 平台不处理空白，**把空白处的合规义务整体转移给广告主** | Amazon：`**It is the Vendor and Seller's responsibility to comply with all applicable laws and rules and regulations** that apply to the Vendor or Seller, the content of the Store, and any location where the Store appears.` | **空白 = 广告主自担** |

**【判断】** ★ 三种形态都指向同一个结论：**
> **「没有规则」不等于「允许」。它等于「责任未分配」—— 而在三种形态里，责任最终都落在广告主（委托方）身上。**

**【判断】** 第三种形态（Amazon）对委托方最重要，因为委托方的主战场是 Amazon 系。** Amazon 用一句 `It is the Vendor and Seller's responsibility to comply with all applicable laws and rules and regulations` **把「平台政策没写」的全部情形转给了卖家**。这意味着：

> **对委托方，空白不是「平台的盲区」，而是「自己的风险敞口」。** 这直接否定了「平台没规定所以可以投」这个隐含假设。

#### 3.1.2 法定侧：没有任何一条法域允许「没规则所以不管」

**【判断】** 本分片已核实的四份法定文本，对「测不出来怎么办」的立场完全一致：**

> **【原文】**（NIST AI RMF 1.0 §1.2.1，R4 §6.2 已核实）
> `The inability to appropriately measure AI risks does not imply that an AI system necessarily poses either a high or low risk`

> **【原文】**（COM(2000)1 §6.2，R4 §6.6.1 已逐字核实）
> `The absence of scientific proof of the existence of a cause-effect relationship, a quantifiable dose/response relationship or a quantitative evaluation of the probability of the emergence of adverse effects following exposure should not be used to justify inaction.`

> **【原文】**（NIST AI 600-1 生成式 AI Profile，MEASURE 3.2 原文；⚠️ 本地文件名 `nist-ai-rmf-playbook.txt` 与其真实来源不符，真实 SOURCE_URL 为 `https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf`）
> `MEASURE 3.2: Risk tracking approaches are considered for settings where AI risks are difficult to assess using currently available measurement techniques or where metrics are not yet available.`

> **【原文】**（同文件，MANAGE 2.3 原文）
> `MANAGE 2.3: Procedures are followed to respond to and recover from a previously unknown risk when it is identified.`

**【判断】** ★ MEASURE 3.2 与 MANAGE 2.3 是两条**专门描述「空白」的官方条文**，而且它们是配对的：**

```
MEASURE 3.2  = 当度量手段不存在时，转为「风险追踪」   ← 空白期间的常态动作
MANAGE 2.3   = 当未知风险被发现时，按程序响应与恢复    ← 空白被填补时的动作
```

**【判断】** 这两条合起来就是「已知未覆盖清单」的官方定义：**
> **它不是一份「我们还没做」的清单，而是一条**运行中的流程**：未覆盖项被追踪（MEASURE 3.2），一旦显形就按程序处理（MANAGE 2.3）。**

#### 3.1.3 ★ 一条对委托方最实用的法条：AI Act 的「先评估、后判定」顺序

> **【原文】**（NIST AI RMF 1.0 §5.2，R4 §6.2 已核实）
> `After completing the MAP function, Framework users should have sufficient contextual knowledge about AI system impacts to inform an initial go/no-go decision`

**【判断】** 顺序是：先 MAP（摸清影响面），再做 go/no-go。** 空白处的正确动作不是「默认放行」也不是「默认拦截」，而是**先摸清这个组合里有什么风险，然后做一次显式决策**。

**委托方的现状是**：21 条规则的作用域写死「W1、M5、M6、M9、Air1」，而同一份 PRD 的改写建议库里出现了 **S12 Pro（5 次）与 V1 Pro（1 次）** 两个不在适用范围内的型号（`01-内部证据-规则表现状审计.md` §1.5）。

> **【原文】**（`01-内部证据-规则表现状审计.md` §1.5）
> `**S12 Pro 与 V1 Pro 有改写建议、却没有规则覆盖。**`

**【判断】** 这是一个**已经被指出、但还没有被处置**的空白。按 §3.1.3 的顺序，正确动作是：**

```
1. MAP：列出「S12 Pro × 各平台 × 各内容类型」这个组合可能涉及哪些风险
2. 决策：显式记录「本季度选择不覆盖 / 覆盖 / 临时人工全量」
3. 留痕：把决策写进「已知未覆盖清单」，而不是让它们静默通过
```

**【判断】** 委托方现在的实际状态是第 3 步的缺失：S12 Pro 的内容会**静默通过全部 21 条规则**，并显示为 `合规·绿`。**

### 3.2 治理侧：谁有权决定空白走 fail-open 还是 fail-closed

**【判断】** 这是委托方问题里最尖的一问，也是本分片能给出最明确答案的一问。答案是：**决策者是组织层（法人/管理层），依据是「风险容忍度」，不是技术团队，也不是内容运营。而 NIST 把这件事写成了标准动作。**

#### 3.2.1 ★★ 决定性证据：fail-open / fail-closed 在 NIST 里是「风险容忍度」的一个取值

> **【原文】**（`_evidence/R8/nist-sp800-30r1.txt` L1848-1852，§3.1 Risk Framing，Risk Tolerance and Uncertainty）
> `Organizations determine the levels and types of risk that are acceptable. Risk tolerance is determined as part of the organizational risk management strategy to ensure consistency across the organization. Organizations also provide guidance on how to identify reasons for uncertainty when risk factors are assessed, since uncertainty in one or more factors will propagate to the resulting evaluation of level of risk, and how to compensate for incomplete, imperfect, or assumption-dependent estimates.`

> **【原文】**（同文件 L1856-1858）
> `To compensate, organizations can take a variety of approaches to determine likelihood, ranging from **assuming the worst-case likelihood (certain to happen sometime in the foreseeable future)** to **assuming that if an event has not been observed, it is unlikely to happen**.`

**【判断】** ★★★ 这两句话把委托方的问题彻底重新定义了：**

| 委托方的问法 | 正确的问法 |
|---|---|
| 「空白走 fail-open 还是 fail-closed？」 | **「本组织的风险容忍度是多少？」** |
| 「技术上哪个默认值对？」 | **「谁有权声明本组织接受哪些后果？」** |
| 「内容运营团队该怎么设？」 | **「组织层（Tier 1）在风险框架里怎么规定？」** |

**【判断】** 因为 NIST 明确把两个极端都列为**合法选项**：**
- **fail-closed 极端** = `assuming the worst-case likelihood (certain to happen sometime in the foreseeable future)`
- **fail-open 极端** = `assuming that if an event has not been observed, it is unlikely to happen`

**两者都是标准认可的做法。选哪一个不是对错问题，是风险容忍度问题。**

#### 3.2.2 决策权的层级归属（NIST 三层结构）

> **【原文】**（`_evidence/R8/nist-sp800-30r1.txt` L4531-4548，TABLE G-1: INPUTS – DETERMINATION OF LIKELIHOOD，逐条）
> `From Tier 1 (Organization level)`
> `- Likelihood information and guidance specific to Tier 1 (e.g., likelihood information related to organizational governance, core missions/business functions, management/operational policies, procedures, and structures, external mission/business relationships).`
> `- Guidance on organization-wide levels of likelihood needing no further consideration.`
> `- Assessment scale for assessing the likelihood of threat event initiation … (Table G-2)`
> `… annotated by the organization, if necessary.`
> （该组三行 `Provided To` 均为 `No | Yes | Yes`）

**【判断】** ★★★ TABLE G-1 给出了决策权的**精确归属与流向**，这是本节最硬的一条证据：**

```
Tier 1（组织层）→ 提供：风险容忍度、标度（Table G-2至G-5）
Tier 1 → Tier 2 : "Yes"
Tier 1 → Tier 3 : "Yes"  ← 但标注 "If not provided by Tier 2"
Tier 3（系统层）→ 不得自行决定，只能使用上级给的标度
```

**【判断】** 三处可直接落地的结论：**

| NIST 的结构 | 对 Momcozy 的含义 |
|---|---|
| **标度的定义权在 Tier 1** | **`severity` 与 `likelihood` 的分档边界必须由管理层定，不能由内容团队定** |
| **`Guidance on organization-wide levels of likelihood needing no further consideration`** | **★ 组织层必须明确声明「哪些低风险等级不需要进一步分析」—— 这是 fail-open 的合法形式：不是「静默放行」，是「按声明放行」** |
| **Tier 3 只能使用上级标度** | **内容运营不能自行决定空白走哪条路** |

#### 3.2.3 ★ 谁签字：「能指定举证责任人」是一条法定约束

> **【原文】**（COM(2000)1 §6，R4 §6.6.3 已逐字核实）
> `• **capable of assigning responsibility for producing the scientific evidence necessary for a more comprehensive risk assessment.**`

**【判断】** ★ 这是「谁有权决定空白走哪条路」的法务答案：**
> **决定空白处置的人，必须同时能指定「谁负责把这块空白补上」。**

**【判断】** 委托方现状**：既没有人宣布空白怎么处置，也没有人被指定去补空白。**两者必须是同一个决定** —— 因为按 COM(2000)1 的六条约束，临时措施的正确形态是「相称 + 临时 + 可复审 + **有举证责任人**」：

> **【原文】**（COM(2000)1 §6.3.5，R4 §6.6.3 已逐字核实）
> `**The measures should be maintained as long as the scientific data are inadequate, imprecise or inconclusive and as long as the risk is considered too high to be imposed on society. The measures may have to be modified or abolished by a particular deadline, in the light of new scientific findings.**`

**【判断】** `by a particular deadline` —— 「空白期的临时处置必须带截止日期」。** 委托方的空白期没有截止日期，也就永远不会有终点。

#### 3.2.4 四层权限的建议分配（综合以上证据）

**【判断】** 综合 NIST Tier 结构 + COM(2000)1 的举证责任 + 主交付物 §4.2.1 的处置权限，建议如下四层分工：**

| 决策 | 谁定 | 依据 | 是否可委托 |
|---|---|---|---|
| **① 风险容忍度声明**（哪些后果不接受） | **法人/管理层（Tier 1）** | NIST §3.1 `Organizations determine the levels and types of risk that are acceptable.` | **不可委托** |
| **② 分档标度与边界**（L0–L5 的定义） | **管理层 + 合规负责人** | NIST TABLE G-1：标度由 Tier 1 提供 | 不可委托给执行层 |
| **③ 单条内容的空白处置**（这条怎么判） | **一线 + 合规负责人** | 主交付物 §4.2.1 处置权限列 | **可委托** |
| **④ 空白清单的复审与升级**（这块要不要建规则） | **合规负责人（环 4）** | NIST MEASURE 3.2 + MANAGE 2.3 | 可委托，但**必须与环 1（规则生产）分人** |
| **⑤ 临时处置的截止日期与举证责任人** | **与管理层共同签署** | COM(2000)1 §6 `capable of assigning responsibility for producing the scientific evidence` | **不可委托** |

**【判断】** 核心结论一句话：**
> **空白走 fail-open 还是 fail-closed，不是一个技术默认值，是一份由管理层签署的风险容忍度声明。技术团队能做的只有一件事：把「本组织的声明是什么」变成一个可执行、可审计的规则（如第 22 条兜底规则）。**

### 3.3 known-gaps register 的真实形态

**【判断】** 委托方问「known-gaps register 有没有真实实践」。答案是：有，而且有**四种不同制度层级的真实形态**，从法定义务一直到学术标注手册的备注列。**

#### 3.3.1 四种真实形态（按制度化程度排序）

| # | 形态 | 载体 | 制度化程度 | 一手性 |
|---|---|---|---|---|
| **1** | **法定机器可读数据库中的自由文本字段** | DSA Art 17 判定理由 + Art 24(5) 公开数据库 | **法定强制** | ★★★ 一手（`dsa-art34-eurlex.txt` L1499、L1199-1252） |
| **2** | **风险评估中的「未被 Profile 覆盖」显式核查** | Ofcom Children's Risk Profiles 的 Step 2 | 法定指引 | ★★ 经 R4 §6.2 转述（**本分片未取得 Ofcom 原文，见 §4**） |
| **3** | **「度量手段尚不存在」的正式条文** | NIST AI 600-1（生成式 AI Profile）MEASURE 3.2 | 框架级（自愿采用） | ★★★ 一手（`nist-ai-rmf-playbook.txt` L1805） |
| **4** | **标注手册的「编码困难」备注列** | Gab Hate Corpus 训练手册的 `Notes` 列 | 学术惯例 | ★★ 经 R4 §3.2 引（GHC 手册） |

#### 3.3.2 ★ 形态 1 的逐字证据：法定「自由文本 + 定期审视 + 重复模式升级」

> **【原文】**（DSA Art 24(5)，`_evidence/R8/dsa-art34-eurlex.txt` L1499）
> `Providers of online platforms shall, without undue delay, submit to the Commission the decisions and the statements of reasons referred to in Article 17(1) for the inclusion in a publicly accessible machine-readable database managed by the Commission. Providers of online platforms shall ensure that the information submitted does not contain personal data.`

**【判断】** 这条给出了「已知未覆盖清单」的**完整制度设计**，而且每一环都有一手依据：**

```
① 每条判定必须提交结构化理由        ← DSA Art 17(3) 六字段（§1.1.4）
② 汇入一个公开的机器可读数据库      ← DSA Art 24(5)
③ 监管方定期审视，出现重复模式就升级为新分类  ← R4 §5.3.3 记录的 Art 17 实践
```

**【判断】** 第 ③ 步「重复模式升级」是整份清单存在的**唯一目的**。** 一个只收集不升级的清单，就是 §1.1.2 说的「归档」。

#### 3.3.3 ★ 形态 3 的逐字证据 + 它的配对条文

> **【原文】**（`_evidence/R8/nist-ai-rmf-playbook.txt` L1805-1806）
> `MEASURE 3.2: Risk tracking approaches are considered for settings where AI risks are difficult to assess using currently available measurement techniques or where metrics are not yet available.`

> **【原文】**（同文件 L1807-1811，MEASURE 3.2 的 Suggested Action）
> `MS-3.2-001 Establish processes for identifying emergent GAI system risks including consulting with external AI Actors.`

> **【原文】**（同文件 L1965-1966）
> `MANAGE 2.3: Procedures are followed to respond to and recover from a previously unknown risk when it is identified.`

> **【原文】**（同文件 L1967-1973，MANAGE 2.3 的 Suggested Action，逐句）
> `MG-2.3-001 Develop and update GAI system incident response and recovery plans and procedures to address the following: Review and maintenance of policies and procedures to account for newly encountered uses; Review and maintenance of policies and procedures for detection of unanticipated uses; Verify response and recovery plans account for the GAI system value chain; Verify response and recovery plans are updated for and include necessary details to communicate with downstream GAI system Actors: Points-of-Contact (POC), Contact information, notification format.`

**【判断】** `MG-2.3-001` 的前两项就是「已知未覆盖清单」的**操作定义**，逐字翻译：**

| 逐字 | 对 Momcozy 的动作 |
|---|---|
| `Review and maintenance of policies and procedures to account for **newly encountered uses**` | **每一次遇到没见过的表达方式，都要触发一次规则复核** |
| `Review and maintenance of policies and procedures for **detection of unanticipated uses**` | **★ 不只是「处理这一次」，还要建立「下次怎么自动发现同类」的能力** |
| `Verify response and recovery plans account for the **GAI system value chain**` | 覆盖从文案生成到投放的全链路 |
| `communicate with downstream GAI system Actors: **Points-of-Contact (POC), Contact information, notification format**` | **未覆盖项要有责任人、有联系方式、有通知格式 —— 即它是一个有主的东西，不是一个统计数字** |

**【判断】** 第二条 `detection of unanticipated uses` 是委托方最缺的。** 委托方现在连「未覆盖」这个状态都没有（未命中 = `合规·绿`），所以**不可能有「发现未预期用法」的能力**。

#### 3.3.4 一份 known-gaps register 的最小 schema（综合四种形态）

**【判断】** 综合 §1.1.4（DSA Art 17(3)）、§1.2.5（重复模式门槛）、§3.3.3（MG-2.3-001 的四要件），最小可用 schema 如下：**

```
known_gap
  gap_id                # GAP-NNNN
  scope                 # 四维作用域：country × category × platform × content_type
  detected_at           # 何时被发现
  detection_source      # 枚举：
                        #   rule_missed      规则全部未命中（兜底触发）
                        #   external_feedback 平台通知/拒登/下架
                        #   manual_audit     人工抽查发现
                        #   competitor_case  竞品被处罚案例
  evidence_refs         # N:M → errorbook（支撑这个 gap 的错题）
  occurrence_count      # 累计触发次数（★ 决定是否升级为规则）
  risk_signal           # 命中的风险信号（医学词汇/比较级/绝对化用语/身份背书/数据声明）
  interim_disposition   # 枚举：human_review_all / human_review_sample / pass_with_log / reject_all
  interim_deadline      # ★ COM(2000)1 §6.3.5 的 by a particular deadline
  evidence_owner        # ★ COM(2000)1 §6 的 capable of assigning responsibility
  status                # open / rule_proposed / rule_released / accepted_risk / closed
  rule_proposal_id      # → rule_change_proposal.proposal_id
  reviewed_at / reviewed_by
```

**【判断】** 四个「必须有」的字段，各有法源：**

| 字段 | 法源 | 逐字 |
|---|---|---|
| `interim_deadline` | COM(2000)1 §6.3.5 | `The measures may have to be modified or abolished **by a particular deadline**` |
| `evidence_owner` | COM(2000)1 §6 | `capable of assigning **responsibility for producing the scientific evidence** necessary for a more comprehensive risk assessment` |
| `occurrence_count` | R4 §5.3.3（Art 17 实践） | 重复模式才升级为正式分类 |
| `status` 含 `accepted_risk` | NIST §3.1 | `Organizations determine the levels and types of risk that are acceptable.` —— **明确接受某风险是一个合法终态，但必须显式记录** |

**【判断】** 最后一个字段 `accepted_risk` 是委托方最需要、也最容易漏的。** 它的意思是：**「我们知道这块没覆盖，我们决定接受它」是一个合法的、必须留痕的终态 —— 而不是「没发现」。** 这与 AI Act Recital 53 的机制完全同构（§2.2.2(c)）：**「我知道它在高风险清单里，我论证它不高风险，我把论证存档登记」**。

### 3.4 「不确定」如何成为可存储状态

**【判断】** 委托方问的是最后一半：「这个组合我们不确定」如何被表达成一个可存储的状态，而不是一个沉默。本节给出**七种不确定，七种存法**，以及对主交付物 §5.5 的一处补强。**

#### 3.4.1 ★ 一处必须先说清的边界：不确定状态**不能**寄生在等级字段里

> **【原文】**（`_evidence/R8/nist-sp800-30r1.txt` L5146-5157，CAUTIONARY NOTE，§2.4.4 已引）
> `Risks that are on the borderline between bins using the organization-defined binning scales, **must ultimately be assigned to one bin**. This determination could have a significant effect on the risk prioritization process.`

**【判断】** ★★ NIST 明确要求：边界样本**必须最终归入某一箱**，不能悬置。**

**【判断】** 这推出一个反直觉但正确的设计约束：**
> **「不确定」必须是一个**与等级并列的独立字段**，而不是等级的一个取值。**
> **原因：如果 `severity` 允许取「待定」，那么 (a) 等级的分箱永远无法闭合；(b) 优先级排序无法进行（因为「待定」没有序数位置）；(c) 违反 NIST 的 `must ultimately be assigned to one bin`。**

**【判断】** ★ 这一条恰好验证了主交付物 §4.2.3 的一处改动是对的**：把 `待复核·灰` 从风险等级**移出**为独立的 `复核状态` 字段。**本分片为这处改动补一条法源：NIST CAUTIONARY NOTE 的 `must ultimately be assigned to one bin`。**

**【判断】** 但同时，主交付物 §5.5 的表格把「规则没覆盖」映射为 `Agent判定等级 = L0 未覆盖` —— 这是**把不确定寄生在等级字段里**，与上面那条约束冲突。**建议修正为：

```
severity       ∈ {L1..L5}  或  未评估        # 分箱值，必须归箱
coverage_state ∈ {covered, uncovered}        # ★ 独立字段：规则覆盖状态
review_state   ∈ {pending, upheld, upgraded, downgraded, passed, rule_fix}
                                              # ★ 独立字段：复核状态
```

**理由**：`L0 未覆盖` 与 `L4 高危` 不在同一个序数尺上 —— 前者是「我不知道」，后者是「我知道很严重」。**把它们放在一个枚举里，会让任何度量（如「高危占比」）的分母失去意义。**

#### 3.4.2 七种不确定，七种存法（对主交付物 §5.5 的补强）

| # | 不确定的类型 | 存法（字段 + 取值） | 证据来源 | 主交付物 §5.5 是否已有 |
|---|---|---|---|---|
| **1** | **规则没覆盖（我不知道有这回事）** | `coverage_state = uncovered` + `未覆盖原因`（枚举） | NIST MEASURE 3.2；DSA Art 17 自由文本实践 | 有（但存在等级字段里，建议拆出） |
| **2** | **规则覆盖了，但我判不出来** | `review_state = pending` + `L2 待复核` | 主交付物 §4.2.1 L2 定义 | 有 |
| **3** | **两个人判得不一样** | `复判人` 非空 + **α 计算** | Krippendorff；主交付物 §4.4.1 | 有 |
| **4** | **这条内容是新的、没见过的** | `未覆盖原因 = 新表达方式` → 进入规则生产队列 | NIST MG-2.3-001 `newly encountered uses` | 有 |
| **5** | **检测器本身出错了** | `ERROR` 独立通道 | Cedar skip-on-error（R3 §5.2.2） | 有 |
| **6** | **★ 已知有风险，但度量手段不存在** | **`measurement_gap = true`** + `risk_signal` 非空 | **NIST MEASURE 3.2** `metrics are not yet available` | **✗ 缺** |
| **7** | **★ 已知没覆盖，组织决定接受** | **`status = accepted_risk`** + `accepted_by` + `accepted_at` + `rationale` | **NIST §3.1** `Organizations determine the levels and types of risk that are acceptable.`；**AI Act Recital 53** 的论证留痕机制 | **✗ 缺** |
| **8** | **★ 边界样本，必须归箱但归哪箱有争议** | `bin_borderline = true` + `bin_decision_by` + `bin_decision_rationale` | **NIST CAUTIONARY NOTE** `must ultimately be assigned to one bin. This determination could have a significant effect` | **✗ 缺** |

**【判断】** 6、7、8 三种是主交付物 §5.5 缺失的，且三者性质不同：**
- **#6 是「我们看不见」** —— 需要的是 MEASURE 3.2 式的风险追踪流程；
- **#7 是「我们看见了但决定接受」** —— 需要的是签署与留痕；
- **#8 是「我们看见了但归箱困难」** —— 需要的是记录归箱理由，因为它影响优先级。

**【判断】** 三者共同点：它们都不能靠「等级」表达，因为它们的共同特征是「等级本身不可靠」。** 这正是 §3.4.1 那条约束的深层原因。

#### 3.4.3 ★ 一条对委托方的强论据：DSA 把「是否用自动化」定成了法定字段

> **【原文】**（`_evidence/R8/dsa-art34-eurlex.txt` L1233-1235，Art 17(3)(c)）
> `(c) where applicable, information on the use made of automated means in taking the decision, including information on whether the decision was taken in respect of content detected or identified using automated means;`

**【判断】** 这条把 R4 §7.2 的第 8 项（`判定路径`）从「工程最佳实践」升级为「欧盟法定字段」。** 委托方 291 条记录里没有这个字段，**意味着它即使作为平台也无法回答「这条判定是机器做的还是人做的」。**

**【判断】** 结合 Meta 拒绝 rec.13 的教训（§1.4.5）：**
> **`判定路径` 是「事后补不上」的字段。** 一旦判定发生时没有记录它，就永远无法重建。**这是 291 条记录里唯一一个「数据还在但信息已经永久丢失」的字段。**

### 3.5 对客户 13.8% 覆盖率的具体处方

**【判断】** 委托方的实测覆盖率是 13.8%（正则层），这是一个必须被**正确解读**的数字 —— 它不是一个「覆盖率」指标，它是一份**诊断**。本节给出五步处方。**

#### 3.5.1 先纠正一个解读：13.8% 不是覆盖率，是「规则表不是判定器」

> **【原文】**（`01-内部证据-规则表现状审计.md` §2.1）
> `**正则层从不多报一条**（多余命中 = 0）。它不是「判定规则」，它是「已经被判违规之后，用来在文本里找位置的定位器」。规则表把两件事写在了一起。`

**【判断】** `多余命中 = 0` 是本节要抓住的关键读数。** 一个真正的规则会出现误报（FP > 0）。**零误报说明它不是在做判定 —— 它是在做定位。**

**【判断】** 因此正确的问题不是「怎么把 13.8% 提高到 60%」，而是「判定能力现在存在哪里」。** 答案有实测证据：

> **【原文】**（同文件 §2.2）
> `**规则表 21 条的 `检测关键词` 里，带变音符的拉丁字符数量为 0。** 一条都没有。而人工实际在用的命中词包括：`schmerzfrei`（德，18 次）、`sans douleur`（法，8 次）、`indolore`（意，4 次）、`silenciosa`/`silencioso`（西，3 次）、`sin dolor`（西，2 次）、`cicha`（意，2 次）`
> `**结论**：运营层已经是 5 语种（英/德/法/西/意），规则表层是 2 语种（英/中）。**这张多语种词表现存于 3 位 Copywriter 的脑子里和 `命中片段` 的自由文本里，规则表里没有。** 这是规则库里价值最高、也最容易随人流失的部分。`

**【判断】** ★★ 这就是处方的第一句话：**
> **13.8% 不是「规则库覆盖得少」，是「规则库和判定能力分家了」。判定能力在 `命中片段` 的自由文本里（270 对），不在规则表里。**

**【判断】** 而这个「在自由文本里」的状态，恰好就是 known-gaps register 的雏形** —— **它已经是一份未结构化的未覆盖清单了，只是没人读它。**

#### 3.5.2 五步处方

**第 1 步：把 `命中片段` 里的 270 对逆向工程成规则（预期收益最大、成本最低）**

| 动作 | 依据 |
|---|---|
| 解析 291 条的 `命中片段` → `（规则编号, 命中词）` 对 | 实测共 **270 对** |
| 其中 **103 对（38.1%）规则表解释不了** → **这 103 对就是最直接的规则缺口清单** | `01-内部证据` §2.2 |
| 按「规则编号 + 语种」聚合，得到每条规则的多语种词表 | 5 语种已实测：英/德/法/西/意 |
| **归一化书写形态**（`hospital-grade` vs `hospital grade`） | `01-内部证据` §2.2：`连英文内部都存在书写形态的漂移，而规则表用空格分词，没有归一化层` |

**【判断】** 这一步的产出直接写进规则库，且不需要任何新采集。** 依据 §3.3.1：这是一次**从自由文本升级为正式分类**的动作，就是 DSA Art 17 实践里的「重复模式升级」。

**第 2 步：把「未命中」从「合规」里拆出来，并立刻上线第 22 条兜底规则**

| 动作 | 依据 |
|---|---|
| 新增 `coverage_state` 字段 | §3.4.1；NIST CAUTIONARY NOTE |
| 未命中 → `coverage_state = uncovered`，**禁止自动放行** | 主交付物 §5.1；Amazon 的义务转移条款（§3.1.1 形态③） |
| 上线第 22 条兜底规则（CATCH-ALL-01） | 主交付物 §5.3；R4 §6.1 尾部给出的形态 |

**【判断】** 预期后果**：291 条里 **159 条未命中（54.6%）** 会立刻从 `合规·绿` 变成 `未覆盖`。**这会显得「覆盖率很差」—— 但那个数字本来就是假的。** 依据：主交付物 §4.2.3 的诊断表。

**第 3 步：建立 `known_gap` 表，并把 159 条未命中按四维作用域聚合**

| 动作 | 依据 |
|---|---|
| 建 `known_gap` 表（schema 见 §3.3.4） | DSA Art 24(5) 的机器可读数据库；NIST MEASURE 3.2 |
| 按 `国家 × 品类 × 平台 × 内容类型` 聚合未命中的 159 条 | 主交付物 §5.7 的三维交叉表 |
| **每个 gap 必须指派 `evidence_owner` 与 `interim_deadline`** | **COM(2000)1 §6 与 §6.3.5（法定要件）** |
| **每个 gap 必须能取到终态 `accepted_risk`** | NIST §3.1；AI Act Recital 53 |

**【判断】** 这一步的关键是**不许留 `open` 状态的孤儿**。** 每一个 gap 要么升级为规则、要么被显式接受、要么被关闭并写明理由。

**第 4 步：把 `判定路径` 补上，并开始采平台侧判定**

| 动作 | 依据 |
|---|---|
| 新增 `判定路径` 字段（`auto` / `human` / `auto_then_human` / `human_then_auto`） | **DSA Art 17(3)(c) 法定要求**（§3.4.3） |
| **新建「平台反馈」入口**（拒登通知 / 下架通知 / 政策警告） | Meta rec.13 的教训（§1.4.5）；R4 §7.2.2 的 `外部反馈入口` |
| 把平台侧判定回填为 FN 候选 | 同上 |

**【判断】** 这一步的紧迫性高于其他各步，因为它是**不可追溯的** —— 已经发生的平台判定，其信息已经永久丢失。**

**第 5 步：声明风险容忍度，并给空白期的临时处置加截止日期**

| 动作 | 依据 |
|---|---|
| 管理层签署《风险容忍度声明》 | NIST §3.1 `Organizations determine the levels and types of risk that are acceptable.` |
| 声明「哪些低风险等级不需要进一步分析」 | NIST TABLE G-1 `Guidance on organization-wide levels of likelihood needing no further consideration.` |
| 声明空白期的默认方向（fail-open / fail-closed / 转人工） | NIST §3.1 的两个极端（§3.2.1） |
| **给空白期处置加截止日期与举证责任人** | COM(2000)1 §6 与 §6.3.5 |

#### 3.5.3 一处必须指出的现实约束（诚实声明）

**【判断】** 五步里有三步是**流程动作**，它们是零技术成本的；但第 1 步与第 4 步需要人。**

| 步骤 | 成本性质 | 是否需要新增预算 |
|---|---|---|
| 1 逆向工程 270 对命中片段 | **人力（约 2–3 人日）** | 否（用现有人） |
| 2 拆 `coverage_state` + 兜底规则 | **工程（字段 + 一条规则）** | 否 |
| 3 建 `known_gap` 表 | **工程 + 指派 owner** | 否 |
| 4 采平台侧判定 | **需接入平台通知渠道** | **可能需（渠道对接）** |
| 5 风险容忍度声明 | **管理层会议** | 否 |

**【判断】** 第 4 步是唯一可能有外部依赖的一步。** 但它对委托方的价值最高，因为它同时解决三件事：FN 的采集（主交付物 §4.4）、后果等级的校准（§2.4.2 的 `Incident Reports` 缺口）、以及在平台处置时的从轻证据（§2.3.3(b) 的 AWS 条款）。

**【判断】** 一个必须说清的限制：委托方 291 条记录里 20.3%（59 条）连文案都抓不到（`两者皆无`，`01-内部证据` §2.3）。** 对这 59 条，**第 1 步与第 2 步都无从执行** —— 它们既不能被规则判定，也不能被逆向工程。**它们必须先进 known_gap，作为 `detection_source = manual_audit` 的条目，而不是留在 `合规·绿` 里。**

## 4. 不可达来源

**【判断】** 本节逐项记录本分片尝试过但未取得正文的来源，以及既有证据包中已存在的失败记录（避免后续分片重复尝试）。每条都注明确切的失败形态。**

### 4.1 本分片亲自尝试的（1 项）

| # | 目标 | URL | 结果 | 尝试次数 | 影响 |
|---|---|---|---|---|---|
| 1 | **MIL-STD-1629 / MIL-P-1629（FMEA 原始出处）** | `https://quicksearch.dla.mil/qsSearch.aspx` | **HTTP 000（连接失败）** | **1 次（按任务书要求，一次即止）** | **★ 本分片因此不从 FMEA 推导任何设计建议；§2.1.6 改为以 NIST SP 800-30 Rev.1 作为 likelihood × impact 的唯一一手依据** |
| 2 | **Ofcom risk assessment guidance** | `https://www.ofcom.org.uk/online-safety/illegal-and-harmful-content/` | **HTTP 403（Cloudflare，返回 5,832 字节 `Just a moment...` 挑战页）** | **1 次（按任务书要求，一次即止）** | **★ 本分片不从 Ofcom 原文推导任何结论；§2.2.3 只引用 R4 已取得的转述，并明确标注** |

### 4.2 既有证据包中已记录的失败（10 项，本节只汇总，不重复尝试）

| # | 目标 | URL | 结果 | 本地产物 | 影响 |
|---|---|---|---|---|---|
| 3 | **Ofcom risk assessment guidance（正文页）** | `.../risk-assessment-guidance` | **HTTP 403** | `R8/ofcom-risk-assessment-guidance.txt`（182 字节，`Just a moment...`） | 同 §4.1 #2 |
| 4 | **Ofcom risk assessment guidance（PDF）** | `.../risk-assessment-guidance.pdf` | **HTTP 403** | `R8/ofcom-rsm-guidance.txt`（229 字节） | 同 §4.1 #2 |
| 5 | **Better Rules（NZ）标准页** | `https://www.digital.govt.nz/standards-and-guidance/technology-and-architecture/better-rules` | **HTTP 404** | `R8/test-betterrules.txt`（1,320 字节，`Page not found \| NZ Digital government`） | R3 §2 的 Better Rules 内容来自其他 URL，**未受影响** |
| 6 | **CommonKADS 专著（Springer）** | `https://link.springer.com/book/10.1007/978-1-4471-0031-2` | **HTTP 404** | `R8/commonkads-book.raw`（22,816 字节，`Page not found`） | 本分片范围**不依赖** CommonKADS（属来源分类学，另有分片） |
| 7 | **CommonKADS 相关学位论文（UvA DARE）** | `https://dare.uva.nl/search?identifier=...` | **HTTP 200 但内容为 `UvA DARE \| Record not found`（软 404）** | `R8/ck-thesis-uva.txt`（510 字节） | **★ 这是一个「HTTP 200 但内容不可用」的陷阱样本** —— 提醒：不能以状态码判定可用性 |
| 8 | **Deontic logic 相关 arXiv 条目** | arXiv（条目号未落在本地文件中） | **`Rate exceeded.`** | `R8/arx-deontic.xml`（**14 字节**） | 未使用 |
| 9 | **Better Rules workshop 示例页** | 站点内页 | **正文为空（仅 front-matter + `#TODO`）** | `R8/brnz-workshop-example.md`（**53 字节**） | 未使用 —— **又一个「抓到了但页面本身是占位符」的样本** |
| 10 | **ISO 31010:2019 正文** | `https://www.iso.org/standard/72140.html` | **HTTP 200，但仅为标准落地页；正文付费墙** | `R8/iso31010-risk-management-official.txt`（6,875 字节，仅导航 + 标题 `IEC 31010:2019 Risk management — Risk assessment techniques`） | **★ 本分片不引用 ISO 31010 的任何条款内容**；风险技术方法一律以 NIST SP 800-30 Rev.1 为依据（§2.1.6） |
| 11 | **NIST SP 800-30 Rev.1 落地页** | `https://csrc.nist.gov/pubs/sp/800/30/r1/final` | HTTP 200，但为落地页 | `R8/nist-800-30-risk-determ.txt`（4,905 字节） | **未受影响** —— 全文另从 `nvlpubs.nist.gov` 的 PDF 取得（334KB，见 §5） |
| 12 | **FTC .com Disclosures 指南正文** | `https://www.ftc.gov/business-guidance/resources/com-disclosures-how-make-effective-disclosures-digital-advertising` | **HTTP 200（985KB HTML），但抽取后的文本（9,053 字节）几乎全是站点导航与菜单，无实质指南正文** | `R8/ftc-com-disclosures.txt` | **★ 本分片未把 FTC 作为任何结论的来源。** 这又是一个「HTTP 200 但正文未取得」的样本 |

### 4.3 既有分片已记录的域名级不可达（本分片未重试，直接继承）

| 域名 | 失败形态 | 记录位置 | 对本分片的影响 |
|---|---|---|---|
| `transparency.meta.com` / `facebook.com` | **DNS 污染** | R4 附录 B | **★ 影响 Q3**：Meta 的官方流程文档不可达，本分片 §1.2.2 / §1.4 的 Meta 证据**全部来自 `about.fb.com`（可达）与 R4 已下载的官方 PDF**，不来自 Meta 透明度中心 |
| `www.tiktok.com` | 站点不可达 | R4 §1.3 / 附录 B | **★ 影响 §2.3 与 §3.1**：TikTok 的公共利益例外与降级机制证据**来自 R4 §6.1 的搜索快照，R4 已明确标注「不得作为论据使用」**。**本分片同样不把它作为独立论据**，只在引用 R4 时保留其标注 |
| `ofcom.org.uk` | 403 | 本分片 §4.1 + R8 证据 | 见上 |

### 4.4 一项「检索未命中」（不是抓取失败，是内容不存在）

| 目标 | 检索范围 | 结果 |
|---|---|---|
| **LegalRuleML 的 `Case` / `CaseLaw` 概念** | `_evidence/R3/raw/legalruleml-core-spec.txt`（7,391 行，`legalruleml-core-spec.html` 774KB） | **未命中**（检索词 `CaseLaw`、`isCase`、`<lrml:Case`） |
| **影响** | — | **★ 本分片因此不改称「LegalRuleML 有 `Case`/`CaseLaw` 概念」为已核实**，并在 §1.3.3 与 §0 给出对主交付物 §3.2.1 的更正建议（改用 R3 §4.1 已核实的 `ConstitutiveStatement`） |

### 4.5 三条方法性提醒（从上面的失败样本中提炼）

**【判断】** 本节的 12 项失败里有 5 项是「HTTP 200 但正文不可用」，只有 2 项是「连不上」。这对后续分片的方法论含义是：**

1. **不能以 HTTP 状态码判定可用性。** `dare.uva.nl`（软 404）、`iso.org`（落地页）、`ftc.gov`（导航壳）、`brnz-workshop-example.md`（`#TODO` 占位）**全部返回 200**。
2. **落地页 ≠ 正文。** NIST / ISO 两级来源的落地页都存在，但**只有 NIST 指向的 `nvlpubs.nist.gov` PDF 拿到了全文** —— 即「政府标准机构的 PDF 直链」是本环境里最可靠的一类来源。
3. **对 Ofcom 这类 Cloudflare 拦截的站点，转述链必须标注。** 本分片对 Ofcom 的两条引文（Step 2 与 Step 3）**只从 R4 转述，并逐处标明「本分片未取得 Ofcom 原文」**，未提升其证据等级。

## 5. 证据清单

**【判断】** 本节列出本分片**实际用于支撑论断**的全部来源。每项给出：本地路径 / 真实 SOURCE_URL / HTTP / 体量 / 本分片用它支撑了哪一节。**

### 5.1 一手标准与法条（本分片的核心依据）

| # | 本地路径 | SOURCE_URL | HTTP | 体量 | 本分片用途 |
|---|---|---|---|---|---|
| 1 | `_evidence/R8/nist-sp800-30r1.txt` | `https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-30r1.pdf` | **200** | 334,118 B | **★ Q4 的核心依据**：§2.1 全节（risk 定义、四件套、五档标度、矩阵 TABLE I-2、likelihood 两段分解）；§2.4 全节（风险容忍度、校准数据源、CAUTIONARY NOTE）；§3.2（Tier 1 标度定义权）；§3.4.1（归箱约束） |
| 2 | `_evidence/R8/dsa-art34-eurlex.txt` | `https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32022R2065` | **200** | 419,203 B | **★ Q3 与 Q4 的核心依据**：Art 34(1)-(3)（§2.2.1）；Recital 79 三子维度（§2.2.1(b)）；Recital 81 语言差异（§2.2.1(c)）；**Art 17(1) 四层处置 + Art 17(3) 六字段（§1.1.4、§3.4.3）**；Art 24(5) 机器可读数据库（§3.3.2） |
| 3 | `_evidence/R8/eu-aiact-art6-eurlex.txt` | `https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689` | **200** | 588,942 B | **Q4 依据**：Recital 26（intensity × scope）；**Recital 52（severity + probability + 预设领域三因子）**；**Recital 53（列入清单但可论证为非高风险 + 必须留痕登记）**（§2.2.2）；Recital 62（`justification and documentation of any significant decisions`，§2.5 步骤 8） |
| 4 | `_evidence/R8/nist-ai-rmf-playbook.txt` | `https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf` | **200** | 163,053 B | **Q5 依据**：**MEASURE 3.2**（度量手段不存在时的风险追踪）与 **MANAGE 2.3 + MG-2.3-001**（未知风险的响应与恢复，四要件）—— §3.1.2、§3.3.3 |
| 5 | `_evidence/R3/raw/gdpr-cellar-gdpr-subset.rdf` | 欧盟 Publications Office **Cellar**，经 R3 取证 | 200（R3 记录） | 4,966 条 axiom / 6,465 条引用 | **★ Q3 的核心依据**：§1.3.1 的「双库结构」实证 —— 224 个判例 CELEX、693 个被引片段、`workflow: CASELAW_METADATA_UPDATE`、片段级引用 `A82P2SNT1` |
| 6 | `_evidence/R8/nist-800-30-risk-determ.txt` | `https://csrc.nist.gov/pubs/sp/800/30/r1/final` | 200（落地页） | 4,905 B | 仅用于确认 #1 的官方出处；**正文依据全部取自 #1** |
| 7 | `_evidence/R8/iso31010-risk-management-official.txt` | `https://www.iso.org/standard/72140.html` | 200（落地页，正文付费墙） | 6,875 B | **★ 未用于支撑任何论断**（见 §4.2 #10） |

### 5.2 平台与生态的一手条款（R7，本分片新用）

| # | 本地路径 | SOURCE_URL | HTTP | 本分片用途 |
|---|---|---|---|---|
| 8 | `_evidence/R7/aws-aup.txt` | `https://aws.amazon.com/aup/` | **200** | **★★ §2.3.3(b) 的核心证据**：`we may consider your ability and willingness to comply with this Policy, including the policies and processes you have in place to prevent or identify and remove any prohibited content or activity.` |
| 9 | `_evidence/R7/github-community-guidelines.txt` | `https://docs.github.com/en/site-policy/github-terms/github-community-guidelines` | **200** | **★★ §2.3.3(a) 的三级后果阶梯**：`Removing the offending content` → `Blocking or disabling` → `Downgrading the visibility` → `Hiding a user account` → `Suspending a user account` |
| 10 | `_evidence/R7/github-acceptable-use.txt` | `https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies` | **200** | §2.3.3(a)：`GitHub retains full discretion to take action … including account suspension, account termination, or removal of content.` |
| 11 | `_evidence/R7/amo-addon-policies.txt` | `https://extensionworkshop.com/documentation/publish/add-on-policies/` | **200** | **★ §2.3.3(c)**：比例原则 `depending on the extent of their non-compliance`；整改期 `a reasonable time frame`；**三个升级触发器 `intentionally or repeatedly violate …, or … unreachable, unresponsive, or uncooperative`** |

### 5.3 既有分片的二级引用（本分片明确标注为转述，未提升其证据等级）

| # | 来源分片 | 本分片引用了什么 | 本分片的标注 |
|---|---|---|---|
| 12 | `R4-trust-and-safety-ops.md` §1.2.2 | Meta Oversight Board 的 19 条 recommendation + **四个处置码逐字定义** + `fully implement 15 / in part 1 / assessing 2 / no action 1`；`identical content with parallel context` 的效力范围声明；rec.13 被拒的原文 `it is not feasible to track this information` | 转述，**原始出处为 `about.fb.com` 官方 PDF**（R4 已下载）。本分片沿用 R4 的一手性判定 |
| 13 | `R4-trust-and-safety-ops.md` §1.4 / §1.5 | YouTube 的**每周 QA 例会**原文（`Every week, our Trust & Safety leadership meet with quality assurance leads …`）与 `guideline tweaks` | 转述 |
| 14 | `R4-trust-and-safety-ops.md` §3.2 | Gab Hate Corpus 手册 `Notes` 列原文（`we will use these contributions to refine and improve later versions of this manual`） | 转述（**本分片只用它论证「收集目的必须被声明」，不重复 R4 的 error analysis 定义**） |
| 15 | `R4-trust-and-safety-ops.md` §4.1 / §6.1 / §6.2 / §6.6.3 / §7.2 / §7.5.1 | 黄金集四原则；五家平台兜底条款；NIST AI RMF `go/no-go`；COM(2000)1 §6 六条约束与 §6.3.5 临时性；291 条记录 12 项字段缺口；Meta 处罚梯度 | 转述，**逐处标注** |
| 16 | `R3-rule-engineering.md` §4.1 / §5.2.2 / §10.2 / §10.3 / §11.6 | LegalRuleML 的 `PrescriptiveStatement` 与 `ConstitutiveStatement`（962 次开标签）；Cedar `skip-on-error` 论证；六体系兜底零例外；三 ID 设计；规则 schema | 转述。**明确边界：本分片不重复 R3 的技术侧空白立场（§3.2 只写治理侧）** |
| 17 | `R6-peer-practice-and-standards.md` §4.1.1 / §6.5 | IAB `evaluation.py` 的 `overall_severity = max(...)` 与 `--level` 操作点；21/21「自动可检测」与 U 族定义的内部矛盾 | 转述。**明确边界：本分片不重做 GARM 映射** |
| 18 | `规范-审核规则库完整设计.md` §3.2 / §3.3 / §4 / §5 | 各节的现状方案（错题本两类记录、五个环、六档 L0-L5、空白三路径） | **本分片对主交付物提出 4 处修正**（见 §0 汇总表）与 6 处补强 |

### 5.4 委托方内部资产（本分片直接读取）

| # | 本地路径 | 本分片用途 |
|---|---|---|
| 19 | `01-内部证据-规则表现状审计.md` | §1.5（12 字段 21 条）；§1.5 尾部（`S12 Pro` / `V1 Pro` 无覆盖）；§2.1（**正则层 13.8%、`多余命中 = 0`**）；§2.2（**270 对命中片段、103 对解释不了、带变音符拉丁字符数为 0**、5 语种表）；§2.3（**59/291 两者皆无**） |
| 20 | `errorbook/errorbook.csv` + `errorbook/errorbook_schema.md` | §1.2（现有 `EB-NNNN` schema 的 26 列；`人工复判结论` 列在 132 条上全为空） |
| 21 | `规范-审核规则库完整设计.md` §4.5 / §5.7 | 291 条 `风险等级 × 处理状态` 完全对角；`检查人` 非空率 0.0%；159 条未命中（54.6%）；132 条待复核占用 $19,913.24（46.2%） |

### 5.5 本分片抓取但因不可用而未采用（诚实登记）

| # | 本地路径 | SOURCE_URL | HTTP | 未采用原因 |
|---|---|---|---|---|
| 22 | `_evidence/R8/ftc-com-disclosures.txt` | `https://www.ftc.gov/business-guidance/resources/com-disclosures-how-make-effective-disclosures-digital-advertising` | **200** | **抽取后 9,053 字节中几乎全为站点导航，无实质指南正文**（§4.2 #12） |
| 23 | `_evidence/R8/rulefit-arxiv.txt` | `https://arxiv.org/abs/0811.3652` | 200 | 属**萃取方法**（RuleFit），**不在本分片范围**（另有分片） |
| 24 | `_evidence/R8/ke-llm-drops.txt` | `https://drops.dagstuhl.de/storage/01oasics/oasics-vol112-icpec2023/OASIcs.ICPEC.2023.9/OASIcs.ICPEC.2023.9.pdf` | 200 | 属**教学/萃取方法**，**不在本分片范围**（另有分片） |
| 25 | `_evidence/R8/brnz-workshop-example.md` / `arx-deontic.xml` / `commonkads-book.raw` / `ck-thesis-uva.txt` / `test-betterrules.txt` | 见 §4.2 | 404 / 部分 200 | **正文不可用**（§4.2 #5-#9） |

### 5.6 本分片新增的可核查数字（全部为直接实测）

| 数字 | 含义 | 计算方法 | 出处小节 |
|---|---|---|---|
| **4,966** | 欧盟 Cellar GDPR 子集中的 `owl:Axiom` 三元组数 | `grep -c 'owl#Axiom' gdpr-cellar-gdpr-subset.rdf` | §1.3.1 |
| **6,465** | `cdm:work_cited_by_work` 引用边数 | `grep -c 'work_cited_by_work'` | §1.3.1 |
| **224** | 独立判例 CELEX 标识数 | `grep -o 'celex/6[0-9]\{4\}[A-Z]*[0-9]*' \| sort -u \| wc -l` | §1.3.1 |
| **693** | 独立被引条款片段数 | `grep -o 'fragment_cited_target …' \| sort -u \| wc -l` | §1.3.1 |
| **13.8% / 72.3% / 0** | 正则层全复现率 / 一条都不中率 / **多余命中数** | `audit_rule_table.py` + `audit_records.py`（R1 号文档） | §3.5.1 |
| **270 / 103 / 0** | `命中片段` 解析出的（规则, 命中词）对数 / 规则表解释不了的 / **带变音符拉丁字符数** | 同上 | §3.5.1 |
| **59 / 291（20.3%）** | `Primary Text` 与 `Headline` 皆无的记录数 | 同上 | §3.5.3 |

### 5.7 本分片边界（有意不写的内容）

**【判断】** 以下内容属于其他分片或已被前序分片穷尽，本分片有意不写，以免重复：**

| 不写的内容 | 归属 |
|---|---|
| 平台政策等级的逐家对照（Meta/YouTube/TikTok/Google/Amazon 的 enforcement tier） | **R1 §5 已覆盖** |
| GARM 序数档到客户规则的映射 | **R6 §1.2 / §4.2.2 已覆盖** |
| OPA `default` / XACML `Deny-unless-permit` / Cedar `skip-on-error` 的**技术侧**空白立场 | **R3 §5 / §10.2 已覆盖**（本分片 §3.2 只写**治理侧**的决策权归属） |
| Andrew Ng 的 error analysis 原始定义与诊断法 | **R4 §3.1 已覆盖**（本分片只用它作为 §1.1.3 的一格对照） |
| 规则来源分类学 | **R8-W1 分片** |
| 规则萃取方法（RuleFit / 教学法 / 词表抽取） | **R8-W2 分片** |
| 维度设计与冷启动 | **R7-W2 / R7-W3 分片** |
| 逐字段的完整 rule schema | **R3 §11.6 已覆盖**（本分片 §1.1.4 只补 DSA 法定的六字段对照） |

---

**【判断】** 全篇一句话总结**：
> **委托方问的三件事，答案是三句：错题本是流水线而不是表（Q3）；严重等级是自己定的、用 NIST 的骨架定、且必须由管理层先签风险容忍度（Q4）；空白不能静默通过，它的默认方向由风险容忍度决定，而「已知未覆盖」必须是一条有主人、有截止日期、有终态的记录，不是一个统计数字（Q5）。**
