# R4 — 内容审核运营（Trust & Safety）与规则自迭代

> 分片作者：R4。写作日期：2026-09-15。抓取日期统一标注为 `2026-09-15`（CST），个别来源标注 UTC。
> 本文件遵守 `00-调研任务书.md` 的证据标准：一手来源优先、逐字引用、标注 URL 与抓取日期、拿不到就写「未核实」。
> 原始证据保存在 `research/governance/_evidence/R4/`。

---

## 0. 结论先行

委托方的问题分成两半：**「规则怎么萃取」**与**「没有规则怎么办」**。调研后，这两个问题在全球内容审核行业和机器学习工程里都有成熟答案，而且答案比我预想的更"可抄"。

**十二条结论（每条后附本文件中的证据位置）：**

1. **规则不是"写出来的"，是"迭代出来的"。** YouTube 官方公开了完整流水线：识别缺口 → 看几十到几百个样本 → 出多个划线方案（每个方案必须附"会被删/会被留"的样例）→ 高管签字 → **给最有经验的审核员写 enforcement guidelines 做准确率测试** → 扩到几百人 → **"修订指南，这个过程可能要几个月"** → 才训练机器。（§1.1）

2. **政策文本（policy）与标注指南（annotation guideline / enforcement guideline）是两种不同物种。** 前者给人读，后者给执行者读。YouTube 官方对后者的定义是逐字的：`enforcement guidelines (detailed explanation of what makes content violative)`。（§2.1）

3. **从案例反推规则有显式机制，而且 Meta 把它做成了公开的"承诺等级"表格。** Oversight Board 的每一个 recommendation，Meta 都必须逐条回复，并归入四个处置码之一：`Implementing fully / Implementing in part / Assessing feasibility / No further action`。这就是「错题本 → 规则」最清晰的公开样本。（§1.2、§4.4）

4. **案例回写规则时会显式声明"泛化范围"**。Meta 原文：`These actions will affect not only content previously posted on Facebook and Instagram but also future content.` —— 一条案例判决如何变成一条规则，这句话就是机制本身。（§1.2）

5. **标注员之间的不一致，主要不是标注员的问题，是规则的问题。** YouTube 官方承认指南要"修订几个月"才能被更大范围的人一致解读；学术侧有硬数字：仇恨言论标注在"隐式/显式修辞"维度上 Fleiss κ = **0.03**；HateXplain 三分类 Krippendorff α = **0.46** 且 4.6% 样本三人完全无共识。（§2.5、§5.2）

6. **"错题本"在工程上的正式名字是 error analysis，其原始定义来自 Andrew Ng 的 Stanford CS229 讲义**：`Error analysis tries to explain the difference between current performance and perfect performance.` 与之配套的还有 `ablative analysis` 与"把 ground truth 逐组件注入，看准确率怎么变"的诊断法。（§3.1）

7. **标注预算有限时该标哪些样本，有标准答案**：uncertainty sampling（挑模型最不确定的）、query-by-committee（挑委员会分歧最大的）、density-weighted（分歧 × 代表性）。这是 Settles 2009 的 Active Learning Literature Survey，本文件给出逐字定义与适用条件。（§3.4）

8. **平均指标会掩盖子群失败**。Hidden Stratification、Model Cards、Datasheets 三篇一手论文给出了切片评估的标准做法：按子群（语言/地区/平台/品类）分别算指标，而不是只算总分。对 Momcozy 而言，"其他地区 216 条"这种粗切片本身就是风险。（§3.5）

9. **规则变更前必须跑回归**，工程侧的标准范式是 OPA 的 `opa test`：每条规则配正例与反例测试，改规则先改测试再跑一遍。NIST AI 600-1 则把对抗测试（AI red-teaming）写成结构化行动项，并明确要求 `Document the instructions given to data annotators or AI red-teamers`（MS-2.8-002）。（§4.2、§4.3）

10. **度量上，内容审核行业真正在用的不是 F1，而是 prevalence（违规内容占比）、主动发现率、申诉率与恢复率、"违规观看率"**。YouTube 官方博客给出了一组完整数字：某季度移除 560 万+ 视频、收到约 27.1 万次申诉、恢复约 2.9 万条；违规观看率 0.10%–0.11%。（§5.3）

11. **「没有规则怎么办」的官方答案不是"先拦着"，而是"先做上下文与风险映射，然后做一次 go/no-go 决策"**。NIST AI RMF 1.0 原文：`After completing the MAP function, Framework users should have sufficient contextual knowledge about AI system impacts to inform an initial go/no-go decision about whether to design, develop, or deploy an AI system.` 配合 EU AI Act Art. 9（全生命周期的风险管理系统）与 DSA Art. 34（部署前风险评估），构成了"规则不存在时的合法动作顺序"。（§6）

12. **承接上一条：平台自己也留了兜底。所有主流平台政策里都有"兜底条款"**——一条不写在规则清单里、但允许平台在规则未覆盖时采取行动的保留条款。规则库的正确设计是：**主体是清单，尾部留一个显式的兜底条目**，并规定它的处置路径（默认转人工、不计入自动拦截）。（§6.1）

---

## 1. 规则（政策）的生命周期：规则是怎么被生产出来的

### 1.1 YouTube：唯一公开了完整政策开发流水线的平台

**来源**：YouTube 官方博客 `On policy development at YouTube`，<https://blog.youtube/inside-youtube/policy-development-at-youtube/>，抓取 2026-09-15，本地证据 `_evidence/R4/youtube-policy-development.html`（150,632 字节）与 `youtube-policy-development.txt`。

该页标题为「Answering commonly asked questions about how we develop our Community Guidelines.」，全文按七个问题组织。以下逐字引用（英文原文）+ 中文要点。

**(1) 政策更新的触发：找缺口 + 找新兴风险**

> "The world moves quickly and our policies need to keep up. That's why we regularly review our policies to make sure that — similar to the laws that govern civil society — they reflect the changes that occur both on and off our platform. To be clear: the vast majority of content on YouTube does not violate our guidelines. But we still check for gaps that may have opened up or hunt for emerging risks that test our policies in new ways."

> "As we work to keep our policies evolving with the current landscape, our guiding focus is around one major goal: **preventing egregious real-world harm**."

**要点**：YouTube 的政策目标函数是单一且显式的——"防止严重现实伤害"。这不是"合规率最大化"，也不是"违规内容最少化"。这一点对 Momcozy 很重要：**规则库必须有一个显式的目标函数，否则规则之间无法排序。**

**(2) 输入源：NGO / 学者 / 各国专家 / 政府机构 / 内部情报台**

> "We also work closely with **NGOs, academics, and relevant experts from all sides and different countries** to inform this policy review. They help flag new concerns, or bring a deep understanding to complex topics that are prone to consistent change. For example, we established our COVID-19 misinformation policy at the start of the pandemic alongside health authorities like the Center for Disease Control and World Health Organization."

> "Throughout the policy development process, we partner closely with a range of **established third-party experts** on topics like hate speech or harassment. We also work with various **government authorities** on other important issues like violent extremism and child safety."

**(3) 专设的"前瞻"职能：Intelligence Desk（情报台）**

> "That valuable visibility is driven by our **Intelligence Desk**, a team within YouTube's Trust & Safety organization. These specialized analysts identify potentially violative trends — whether new vectors of misinformation or dangerous internet challenges — and the risks they pose. They're also regularly monitoring ongoing threats like extremist conspiracy theories, both tracking their prevalence across media and evaluating how they morph over time."

> "These insights then feed into thinking through how current or future policies would manage these new threats. For example, based on evidence gathered by the Intelligence Desk, we updated our hate and harassment policies to better combat harmful conspiracy theories on our platform."

**要点**：**这是一个独立的、专职的"外部风险扫描"岗位**，其产出直接进政策流程。Momcozy 的对应物是：谁负责盯平台广告政策更新、目标国法规更新、竞品被处罚案例？现在这个职能没有归属。

**(4) 划线方法：看样本 → 出多个方案 → 每个方案必须附样例**

> "Once we've identified an area where a policy update is needed, that's where our **Trust & Safety team** comes in to develop a tailored solution. We start by assessing a few things. How commonly found is this specific type of harmful content on YouTube (and what's its potential to grow)? And how is it managed under our current Community Guidelines?"

> "Then we **watch dozens or even hundreds of videos** to understand the implications of drawing different policy lines. **Drawing a policy line is never about a single video; it's about thinking through the impact on all videos**, which would be removed and which could stay up under the new guideline. Following this comprehensive review, the team shares **various options for policy lines, making sure to detail examples of videos that would be removed or approved for each** (as well as different enforcement actions, like removal vs. age-restriction)."

**要点**：这是**本分片最重要的一条方法学证据**。划线不是拍脑袋，而是：① 先估发生率与增长潜力；② 看几十到几百个真实样本；③ 产出**多个候选线**；④ 每条候选线必须附"会被删的样例"和"会被留的样例"。

第 ④ 步正是 Momcozy 现在缺的：21 条规则里，有多少条能给出"命中它"和"不命中它"的两组对照样例？从 PRD 看，只有 `H07` 这类有明确关键词族的规则勉强能做到，`U01`（含泌乳顾问头衔需核实）根本无法用样例界定。

**(5) 验收标准与签字链**

> "A top choice is selected from those draft options and then goes through further rounds of assessment. At this stage, we're looking to understand whether the proposal can meaningfully achieve a few key goals:
> - **Mitigate egregious real-world harm while balancing a desire for freedom of expression.**
> - **Allow for consistent enforcement by thousands of content moderators across the globe.**
> If we're satisfied that we're hitting these targets, an **executive group** made up of leads across the company reviews the proposal. **Final sign-off comes from the highest levels of leadership, including YouTube's Chief Product Officer and CEO.** If at any point there is **consistent disagreement between teams about where we've drawn the line, the policy is sent back to the drawing board.**"

**要点**：两条验收标准，缺一不可——**① 伤害能被实质降低；② 能被成千上万名分散的审核员一致执行**。第 ② 条是关键：一条规则如果无法被一致执行，即使"正确"也不能上线。

"如果团队之间持续无法达成一致，政策退回重画"——这是**分歧作为阻断信号**的制度化。

### 1.2 Meta：流程文档不公开，但 Oversight Board 的回写机制公开了完整链路

Meta 的 `transparency.meta.com` 与 `facebook.com` 在本调研的网络环境下**不可达**（DNS 污染，详见附录 B）。因此本节的 Meta 一手证据来自 `about.fb.com`（Meta Newsroom，可达）与 Meta 官方发布的 PDF 附件。

#### 1.2.1 「政策 → 执行指南」的翻译过程（Meta 在 Oversight Board 文件中的自述）

Meta 在回应 Oversight Board 的官方 PDF 中，说明了它如何把"一篇政策"变成"可执行的操作"：

> "**We also document our policies in enforcement guidelines** ... our policies are applied uniformly across Facebook and Instagram..."

> （关于 newsworthiness allowance）"We allow certain content that is newsworthy or important to the public interest to remain on our platform — **even if it might otherwise violate our Community Standards**. We may also limit other enforcement consequences, such as demotions, when it is in the public interest to do so. When making these determinations, however, we will remove content if the risk of harm outweighs the public interest."

> （关于 cross check）"**Cross check simply means that we give some content from certain Pages or Profiles additional review.** We often apply this process to ensure our policies are applied correctly for public figures and content on Facebook that will be seen by many people."

**来源**：`meta-ob-response-trump.html` / `.txt`（本地证据），<https://about.fb.com/news/2021/06/facebook-response-to-oversight-board-recommendations-trump/>，抓取 2026-09-15。

**要点（对 Momcozy 极重要）**：Meta 明确承认存在**规则外的例外通道**（newsworthiness allowance），并且这个通道是**成文的、有解释的、有公开数字的**。规则库不是"命中即拦"的封闭系统，它必须显式包含例外通道，否则规则会被绕过或被滥用。

#### 1.2.2 「案例 → 规则」的完整链路：Oversight Board 回写

这是本分片要交付的**最清晰公开样本**。链路共四步：

**第 1 步：个案裁决。** Oversight Board 对具体内容做 binding decision。Meta 必须执行。

**第 2 步：案例级泛化（"同一内容、平行语境"）。** Meta 官方原文：

> "**Implementing the Board's Decisions At Scale**
> We've also started the process of reinstating identical content with parallel context in the following cases: **Uyghur Muslims**, **Hydroxychloroquine, Azithromycin and COVID-19**, and **a Nazi Quote**. **These actions will affect not only content previously posted on Facebook and Instagram but also future content.**
> For cases where the board upholds our final judgment, we will continue to ensure identical content with parallel context remains either up or down in line with the board's decision."

**来源**：<https://about.fb.com/news/2021/02/facebook-response-to-the-oversight-boards-first-set-of-recommendations/>，抓取 2026-09-15，本地证据 `meta-ob-response-first-recommendations.html` / `.txt`。

**这是「错题本 → 规则」的机制原句**：一个案例判决的效力范围被显式声明为"过去 + 未来 + 平行语境"。

**第 3 步：把案例拆成"建议条目"，逐条处置。** Meta 在 Trump 案中把它收到的意见拆成 **19 条 distinct recommendations**，并公开了每一条的处置结果：

> "We identified **19 distinct recommendations** and have responded to each of them below. We carefully considered these recommendations and today are committing to **fully implement 15 of them**. We are also **implementing one recommendation in part**, **still assessing two** of them, and **taking no further action on one** of them. In determining how to respond to these recommendations, we consider **the feasibility of implementation and the impact to our users**."

四个处置码的逐字定义（这是可以直接抄的枚举值）：

> "We categorize our response to the board's recommendations in the following areas:
> - **Implementing fully**: Facebook agrees with the recommendation and has or will implement it in full.
> - **Implementing in part**: Facebook agrees with the overall aim of the recommendation and has or will implement work related to the board's guidance.
> - **Assessing feasibility**: Facebook is assessing the feasibility and impact of the recommendation and will provide further updates in the future.
> - **No further action**: Facebook will not implement the recommendation, either due to a lack of feasibility or disagreement about how to reach the desired outcome."

**来源**：Meta 官方 PDF `Facebook Responses to Oversight Board Recommendations in Trump Case`，本地证据 `meta-ob-trump-recommendations-detailed.pdf`（20 页）/ `.txt`，下载自 <https://about.fb.com/wp-content/uploads/2021/06/Facebook-Responses-to-Oversight-Board-Recommendations-in-Trump-Case.pdf>，抓取 2026-09-15。

**第 4 步：规则/流程实际变更。** 举三个可验证的落点：

- **新增"高危人物升级处罚"协议**（严重等级分层的制度来源）：Meta 原文列了三个判定因子与处罚梯度：
  > "when determining the appropriate restriction for a public figure who has violated our Community Standards or Community Guidelines in ways that incite or celebrate ongoing violent disorder or civil unrest, we may consider: **(1) the severity of the violation and the person's history on the platform, including current and past violations, (2) the public figure's potential influence over and relationship to the individuals engaged in violence, and (3) the severity of the violence and any related physical harm.** During times of civil unrest and ongoing violence, we use these factors to determine the appropriate restriction length, **ranging from one month to two years**."

- **公布 strike 系统**：`Today we are publishing detailed information in our Transparency Center about our strikes and penalties.`（对应 recommendation 16）

- **上线 Account Status**（用户可见的违规历史）：`Earlier this year, we launched "Account Status" on Facebook, an in-product experience to help every user understand the penalties Facebook applied to their accounts.`（对应 recommendation 17）

**反面样本（同样重要）：Meta 拒绝了一条，理由是"我们没有能力测"**

> Recommendation 13: "Facebook should **report on the relative error rates and thematic consistency** of determinations made through the cross check process compared with ordinary enforcement procedures."
> **Commitment Level: No further action**
> "We will take no further action on this recommendation **because it is not feasible to track this information**. ... While the board has requested details about the relative error rates of enforcement decisions made through cross check, **we do not have systems in place to make this comparison. Our measurement accuracy systems are not designed to review the small number of decisions made through the cross check process.**"

**要点**：**连 Meta 都承认，它无法计算"特殊通道 vs 常规通道"的对比错误率**，因为它的事后质量测量系统不是按这个维度建的。这对委托方是一个重要提醒：**错题本要能算出 FP/FN，必须在数据模型设计阶段就把"判定路径"和"最终真值"两个字段留出来**，事后补是补不上的。这正是 291 条记录现在最大的缺口（见 §7.2）。

还有一条拒绝，透露出"公开规则"与"防规避"的张力：

> "In providing this additional transparency, we want our global users to better understand the details of our strikes and penalties processes **while avoiding including certain information that malicious actors could use to circumvent our enforcement systems.**"

**要点**：规则库对内的完整版本与对外的脱敏版本，必须分开。Momcozy 当前把 `检测关键词` 与 `正则表达式` 写在同一张表里——这张表一旦外流，等于把规避手册交出去。

### 1.3 TikTok：Community Principles（可达部分）

`www.tiktok.com` 在本调研环境不可达（见附录 B）。通过可达的搜索快照，TikTok 官方 `Community Principles` 页面（<https://www.tiktok.com/safety/en/policies-and-engagement/community-principles>）列出**八条核心原则**，用于"指导我们如何制定规则以及如何做复杂的执行决定"。其中与规则生产直接相关的第 7 条，搜索快照返回的文字为：

> "**Be Transparent and Consistent**: We want everyone to know what our rules and standards are, and how we apply them. We seek to provide clear notice of our policies and practices, to apply them consistently, and to share our enforcement efforts at our Transparency Center."

**⚠️ 证据等级说明**：本条**未取得 TikTok 官网原文**（域名不可达）。上述文字来自搜索服务的页面快照，**属于未完成核实的引用**，不得作为论据使用。TikTok 的透明度报告指标由 R4 的另一条取证线单独处理（见 §5.3 与附录 A）。

### 1.4 规则从哪来：输入源清单（对照表）

把 §1.1（YouTube 官方流程）与 §1.2（Meta Oversight Board 回写）里出现的输入源抽出来，得到一个可直接用于 Momcozy 的清单：

| 输入源 | YouTube 官方表述（逐字） | Meta 官方表述（逐字） | Momcozy 的对应物 | 现在有吗 |
|---|---|---|---|---|
| **用户/买家举报** | "flagged by our systems or people" | "before people report it to us" | 客服工单、差评、评论区投诉 | ⚠️ 未接入 |
| **NGO / 公益组织** | "We also work closely with NGOs, academics, and relevant experts from all sides and different countries" | — | 母婴权益组织、哺乳顾问协会 | ❌ 无 |
| **学术研究** | 同上（academics） | — | 泌乳医学文献、广告法研究 | ⚠️ 仅引用为"依据来源"，无常态渠道 |
| **政府/监管机构** | "We also work with various government authorities on other important issues like violent extremism and child safety" | — | FDA / FTC / 各国广告监管 | ⚠️ 无常态渠道 |
| **专业机构（卫生权威）** | "alongside health authorities like the Center for Disease Control and World Health Organization" | — | IBCLC、泌乳医学会 | ⚠️ 有 U01 规则，但无证据链 |
| **内部情报/前瞻扫描** | "our **Intelligence Desk** ... identify potentially violative trends ... track their prevalence across media" | — | 谁盯平台政策与法规更新？ | ❌ 无 |
| **平台自身的执行数据** | "How commonly found is this specific type of harmful content on YouTube (and what's its potential to grow)?" | "Our measurement accuracy systems..." | 291 条广告记录 | ⚠️ 有数据，无闭环 |
| **独立审查机构的裁决与建议** | — | Oversight Board：19 条 recommendations，逐条处置 | 无对应机构 | ❌ 无 |
| **外部专家委员会** | "we partner closely with a range of established third-party experts" | 咨询专家（rec. 3、rec. 11 均提到 consultation with experts） | 无 | ❌ 无 |
| **举报/申诉** | "we removed more than 5.6 million videos ... and received roughly 271,000 removal appeals" | "Account Status"、appeals | 无申诉机制（Agent 说了算） | ❌ 无 |

**关键观察**：Momcozy 目前的规则来源只有两类——`品线反馈` 与 `一份历史审计 Excel`（见任务书 §二.A 的 `依据来源` 字段）。**上面 10 类输入源里，只有"内部数据"这一类是勉强接通的，而且是单向的（只用于统计，不回写规则）。**

### 1.5 「从案例反推规则」到底有没有显式机制？——有三种

委托方问"需不需要错题本"。答案是：**需要，而且行业里有三种显式的"案例反推规则"机制，分别对应不同的制度化程度：**

| 机制 | 谁在用 | 触发物 | 产出物 | 制度化程度 | 本文件证据 |
|---|---|---|---|---|---|
| **A. 独立裁决机构的 recommendation 回写** | Meta × Oversight Board | 个案裁决 + 政策建议 | 逐条处置表（4 个处置码）+ 政策/流程变更 | **最高**：有强制回复义务、有公开台账 | §1.2.2 |
| **B. 内部 QA 例会驱动的指南微调** | YouTube | 每周 QA 会上的"棘手决定" | enforcement guideline 的增补句 | **高**：有固定节奏、有明确触发词 | §1.4、§4.4 |
| **C. 标注手册的"疑难案例"收集列** | 学术标注项目（Gab Hate Corpus） | 标注员遇到的难例 | 下一版手册 | **中**：有字段、有流程，但靠人自觉 | §2.2、§3.6 |

**YouTube 的"每周例会"原文**（这是最接近 Momcozy 可执行规模的一种）：

> "**Every week, our Trust & Safety leadership meet with quality assurance leads from across the globe** (those responsible for overseeing content moderation teams) to **discuss particularly thorny decisions and review the quality of our enforcement**. If needed, **guideline tweaks are then drafted to address gaps or to provide clarity for edge cases.**"

**来源**：同 §1.1。

**要点**：注意这里的粒度——**不是"改政策"，而是"改指南"**。政策一年动几次，指南每周动。Momcozy 现在把两者混在 21 条规则的一张表里，结果是：一条只是"措辞不清"的规则，和一条"法律红线"的规则，用的是同一套变更流程（都是改表格）。这是 §7.1 要拆开的第一个问题。

---

## 2. 政策文本 → 可执行规则的翻译（标注指南 / annotation guideline）

### 2.1 平台官方承认：这个翻译过程要花几个月

**来源**：YouTube 官方博客（同 §1.1），逐字引用：

> "How do we make sure policies are enforced consistently?
> The implementation of a new policy is a joint effort between people and machine learning technology. In practice, that means in order for a policy to be successfully launched and enforced, **people and machines need to work together to achieve consistently high levels of accuracy when reviewing content**.
>
> We start by giving our most experienced team of content moderators **enforcement guidelines (detailed explanation of what makes content violative)**, and ask them to differentiate between violative and non-violative material. **If the new guidelines allow them to achieve a very high level of accuracy**, we expand the testing group to include **hundreds of moderators across different backgrounds, languages and experience levels**.
>
> **At this point, we begin revising the guidelines so that they can be accurately interpreted across the larger, more diverse set of moderators. This process can take a few months**, and is only complete once the group reaches a similarly high degree of accuracy. **These findings then help train our machine learning technology** to detect potentially violative content at scale."

这段是**本分片最有价值的一段工程证据**。把它拆成可执行的步骤：

1. **先写 enforcement guideline**（不是政策原文，是"什么让内容构成违规"的详细解释）。
2. **先用最资深的审核员测**，看指南能不能让他们达到"非常高的准确率"。**达不到就说明指南本身有问题，不是审核员有问题。**
3. **扩大测试组到几百人**（不同背景、语言、经验）。
4. **修订指南**，直到更大、更多样的人群也能达到同样准确率。**这个过程要几个月。**
5. **只有在人被指南对齐之后，才用它去训练机器。**

**对 Momcozy 的直接含义**：他们现在是**反过来做的**——先让 Agent 去判 291 条，人工只在 `检查人` 栏（从 PRD 看，291 条里该列基本为空）被动兜底，**从未做过"规则 × 多个判定者"的一致性测试**。这意味着：**目前的 291 条记录无法区分"规则不清楚"和"执行者判错了"**。

第 5 步的顺序也值得注意：**先对齐人，再对齐机器**。因为机器的"对齐"完全依赖人给出的标签质量；如果指南本身含糊，人被勉强对齐了，机器学到的是"人怎么猜"，而不是"规则说什么"（对应 §2.5 的 annotation artifacts）。

### 2.2 公开的标注手册长什么样：Gab Hate Corpus 训练手册实物解剖

这是本分片找到的**最接近委托方要的"规则库运营形态"的公开实物**。

**来源**：`A Typology and Coding Manual for the Study of Hate-based Rhetoric`，Kennedy, Kogon, Coombs, Hoover, Park, Portillo-Wightman, Mostafazadeh, Atari, Dehghani（University of Southern California），2018-07-18，20 页。
**获取**：OSF 项目 <https://osf.io/edua3>（DOI `10.17605/osf.io/edua3`），文件 `Documentation/` 目录，guid `nqt6h`，直链 <https://osf.io/nqt6h/download>。本地证据 `_evidence/R4/gab-hate-corpus-trainingmanual.pdf`（234,977 字节）+ `.txt`。抓取 2026-09-15。

#### 2.2.1 手册的目录结构（逐字）

```
1 Introduction (p.1)
2 Background (p.3)
     Legal Definitions and Perspectives on Hate Speech
     Hate Speech Studies in Natural Language Processing
3 Hate-based Rhetoric (p.7)
     3.1 Definition (p.7)
     3.2 Typology (p.8)
4 Coding Manual/Procedure (p.11)      ← 这是"可执行规则"的部分
     Hate-based Rhetoric
     Calls for violence (CV) (p.11)
     Assaults on human dignity (HD) (p.12)
     HB derogatory: Vulgarity/Offensive Language directed at an individual (VO) (p.13)
     Targeted Populations (p.14)
     Framing: Implicit or Explicit (p.14)
     Notes (p.15)                      ← 这是"错题本"字段
5 Examples (p.15)
     Gab examples (p.16-17)
     Examples from Alt-right YouTube Comments (p.18)
6 Future work (p.18)
References (p.19-20)
```

**这个结构就是委托方要的六段式的完整实现**：定义（§3.1）→ 判定标准（§4）→ 边界案例（§4 各小节内）→ 反例/不算违规的论证（§4 内专节）→ 判定树（论文 Figure 1）→ 常见误判兜底（§4 Notes）+ **已知缺陷自陈**（§6）。

#### 2.2.2 逐字证据：六个结构件分别长什么样

**(a) 定义（p.8）**

> "**Language that intends to** — through rhetorical devices and contextual references – **attack the dignity of a group of people, either through an incitement to violence, encouragement of the incitement to violence, or the incitement to hatred.**"

注意：定义里带 `intends to`（意图）。**这就是后面 κ=0.03 的根源**——意图是最难被一致判定的属性。

**(b) 判定标准 + 显式反例论证（p.11）**

> "**Calls for violence include any verbalization or promotion of messages which advocate or endorse aggression towards a given person or group on account of their status as member of a given sub-population.** This aggression can take the form of violence, genocide, exclusion, and segregation.
>
> **Threats which do not name the target's group membership as cause for the threat are not hate speech under our definition.** Such instances include individual attacks (insults or threats) and group attacks which do not leverage some form of hatred. The below text is such an example of the former:
> *paul ryan is a traitor and its too bad we do not hang traitors anymore because he would be just one in a long line*
> **This would be coded as NH and VO, as it contains a threat which does not target group identity.**"

**这一段的写法值得逐字抄**：`标准 → 排除条件（not X under our definition）→ 一条真实反例 → 这条反例的完整编码结果（NH + VO）`。**反例不只是一个"不算违规"的标注，而是一个"算另一个类别"的完整判定**。

**(c) 判定者测试（p.11，引 Benesch 2012）**

> "**Was the speech understood by the audience as a call to violence?** Inflammatory speech is often expressed in elliptical, indirect language, which can be variously interpreted. For this analysis, **the only relevant meaning is the way in which the speech was understood by the audience most likely to react, at the time when it was made or dessiminated** (p. 4)."

**要点**：把"谁的理解算数"写死在规则里。Momcozy 的等效问题：`H07 疼痛功效承诺` 里的 `comfort/gentle` 与 `pain relief` 的界线，到底是"普通消费者怎么理解"还是"监管机构怎么认定"？规则里没写。

**(d) 同一词看用法：显式排除"口语化用法"（p.12）**

> "In the evaluation of slurs against group identity ... we define such instances as "hate-based" **if they are used in a manner intended to wound; this naturally excludes the casual or colloquial use of hate slurs.** As an example, the adaptation of the N-slur (replacing the "-er" with "-a") often implies colloquial usage. Words such as "bitch" and "dick" are to be considered hateful **if they are used in a way which dehumanizes the respective, targeted populations.**"

**要点**：这就是 Momcozy 需要的 `豁免词` 字段的**正确写法**——不是"这些词豁免"，而是"这些词在什么用法下豁免"。他们目前 5 条规则带 `豁免词`，PRD 显示是裸词形式，**这在工程上是危险的**（对应任务书提到的反模式："兜底路径比主路径更宽松"）。

**(e) 「不算违规」专节（p.13）**

标题逐字：`Examples of vulgarity that are not hate (NH):`，下面附 3 条真实原文（例：`And it's gotta be some ghetto fool :/`）。

**(f) 常见误判兜底（p.14）**

> "**If you are unsure that a word is being used as a derogatory slur directed in a hateful, degrading way towards a segment of the population, feel free to consult hatebase.org or urbandictionary.com.**"

**要点**：给出**可查的外部权威**作为兜底，而不是"自行判断"。

**(g) ★ 把「规则本身有问题」制度化：Notes 列（p.15）—— 「错题本」在规则手册里的原形**

> "**Notes** — Is there anything important to note about the document? Is it in a different language? **Does it seem in any way like it should be excluded (e.g. because it is fake, because it has been repeated multiple times, etc.)** If so, **add a note describing these issues in the 'note' column.** In addition, **make notes about difficult cases and difficulties you had in coding, as we will use these contributions to refine and improve later versions of this manual.**"

这一段只占半页，但它**完整定义了一个"错题本"字段的全部要素**，可以直接抄成字段规格：

| 要素 | 手册原文 | 对应字段设计 |
|---|---|---|
| **字段名** | `'note' column` | `难例备注` |
| **收集动作** | `make notes about difficult cases` | 判定者必须填写 |
| **收集什么（一）** | `difficulties you had in coding` | **判定者遇到的困难**（不只是"判错的案例"——这是关键区别） |
| **收集什么（二）** | `Does it seem in any way like it should be excluded (e.g. because it is fake, because it has been repeated multiple times, etc.)` | **"似乎应该被排除"的直觉**（例如内容看起来像假的、像重复投放的） |
| **收集什么（三）** | `Is it in a different language?` | **语种异常标记** |
| **用途声明** | `we will use these contributions to refine and improve later versions of this manual` | 明确写进字段说明：**该字段用于修订规则，不是归档** |

**Momcozy 的 291 条记录里，完全没有这一列。**

**(h) 已知缺陷自陈（p.18，§6 Future work）**

> "**The most significant short-coming of our typology and coding procedure is the lack of a theory of speech acts**... Another limitation of our typology is the accounting for the various ways in which slurs are employed: as insults, as means of dehumanization, as benign discussions of the slurs themselves, etc."

**要点**：手册自己写了"我们知道它哪里不够"。**规则库必须有"已知缺陷"字段**，否则使用者会误以为未覆盖的地方是"合规"。

#### 2.2.3 判定树（GHC 论文 Figure 1）

**来源**：`r4-ghc-paper-osf-hqjxn.pdf`（48 页），<https://osf.io/hqjxn/download>，DOI `10.31234/osf.io/hqjxn`，本地证据 `_evidence/R4/r4-ghc-paper-osf-hqjxn.pdf` / `.txt`，抓取 2026-09-15。

图注逐字：`Figure 1. Workflow of annotating a document for hate-based rhetoric.`

图中的判定节点（按 PDF 文本流顺序逐字）：

```
Does the text...
  ...express hatred towards a group/person?
  ...express aggression, insult, or use profanity?
Consider the type of the identified rhetoric. Does it...
  ...degrade, dehumanize, or imply inferiority of the targeted group/person?   → Label HD
  ...endorse or express aggression or violence toward the targeted group/person? → Label CV
  ...express aggression, insult, or use profanity?                             → Label VO
Consider the subcomponents of the identified rhetoric. Does it...
  ...Function through sarcasm, irony, or metaphor?   → Label IM
  ...(otherwise)                                     → Label EX
Label the type of group being targeted by text
  ...empower hate groups or reinforce the marginalization of the targeted group/person?
  ...contain profanity or insulting language?  → Label VO
YES / NO
  → Label NH
```

论文正文（p.12）说明手册与判定树的关系：

> "The full version of the typology used to train annotators, **which includes our definitions, explanations of categories, and examples**, has previously been made public via online preprint, and is provided in its entirety as part of the Supplemental Materials. **The essential components of the typology and the associated process followed by annotators are shown in Figure 1.**"

**训练协议（p.19）——这是"规则库的上岗考试"，可直接抄**：

> "Annotators were undergraduate research assistants (RAs) trained by first reading the typology and coding manual and then **passing a test of about thirty messages that had been previously annotated and agreed upon by the authors.**"

**要点**：**用 30 条"作者之间已经达成一致的样本"做上岗考试**。Momcozy 要做的是同一件事，只是对象从"新标注员"换成"新规则"或"Agent 的新版本"：**每条规则上线前，用一组已达成共识的正例/反例跑一次，不过不发布**。这就是 §4 的黄金集。

### 2.3 工业界的 category 定义写法（对照）

学术手册之外，工业界把规则写成机器可调用形式时，采用更短的"定义 + 显式边界 + 免责"三件套。三份官方来源对照：

| 来源 | 结构 | 逐字样例 | 显式边界处理 |
|---|---|---|---|
| **OpenAI Moderation**（官方 `openai-cookbook` 仓库内 vendored 文档） | 11 个 category，扁平 + 斜杠子类 | `hate` — "Content that expresses, incites, or promotes hate based on race, gender, ethnicity, religion, nationality, sexual orientation, disability status, or caste." | **`Hateful content aimed at non-protected groups (e.g., chess players) is harassment.`** ← 用一句话把"命中 A 类但不满足 A 类前提"的样本明确改判到 B 类 |
| 同上 | — | `sexual` — "Content meant to arouse sexual excitement... (**excluding sex education and wellness**)" | 括号内显式豁免（**对 Momcozy 直接适用：健康/教育语境的豁免写法**） |
| 同上（口径免责） | — | "`category_scores`: ...denoting the model's confidence that the input violates the OpenAI's policy for the category. The value is between 0 and 1... **The scores should not be interpreted as probabilities.**" / "**custom policies that rely on `category_scores` may need recalibration over time.**" | 明确禁止把分数当概率；明确预告**分数会漂移、需要重校准** |
| **AWS Bedrock Guardrails**（<https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-content-filters.html>） | 5 类 + **每类 4 档强度** | `Hate` — "Describes input prompts and model responses that discriminate, criticize, insult, denounce, or dehumanize a person or group on the basis of an identity (such as race, ethnicity, gender, religion, sexual orientation, ability, and national origin)."；`Insults` — "...demeaning, humiliating, mocking, insulting, or belittling language. This type of language is also labeled as bullying." | **强度被显式参数化**："Select **None, Low, Medium, or High** for the level of filtration you want to apply to each category. **You can choose to have different filter levels for prompts and responses.**" |
| **Perspective API TOXICITY**（Google Jigsaw，官方 model card） | 单属性，定义 + 用途禁令 | "The toxicity model classifies whether a comment is a rude, disrespectful, or unreasonable comment that is likely to make people leave a discussion." | **用途禁令**："**Fully automated moderation — Perspective is not intended to be used for fully automated moderation. Machine learning models will always make some mistakes, so it is essential to build in systems for humans to catch and correct those mistakes.**" |

**本地证据**：`_evidence/R4/openai-moderation-docs.txt`、`_evidence/R4/r4-aws-guardrails-content-filters.html` / `.txt`、`_evidence/R4/perspective-toxicity-modelcard.md`。均抓取 2026-09-15。

**三条可直接抄的设计原则**：

1. **"改判规则"要写进定义里**（OpenAI 的 `chess players → harassment`）。规则之间必须有**冲突消解**，且写在定义层，不留给执行者现场判断。
2. **强度是规则的一等属性，不是附属说明**（AWS 的 None/Low/Medium/High）。Momcozy 的 `风险等级` 四档目前是**结果标签**；AWS 的做法是**阈值参数**——同一个类别，可以按场景（prompt vs response；对 Momcozy 就是"广告文案 vs 落地页/详情页"）设不同档位。
3. **规则库必须自带"不要这样用"的声明**（Perspective 的 fully automated moderation 禁令）。**在委托方目前的治理约束下（无法强制卡死上线节点），这一条尤其重要**：规则库必须显式声明"哪些条目禁止自动拦截、只能转人工"。

### 2.4 翻译成本在哪里：四条一手证据

委托方问「政策文本与判定规则之间的翻译成本在哪」。四条独立一手证据指向同一个答案：**成本集中在"依赖意图/语境/隐式"的条款上，而且成本有硬上限。**

**(1) 平台侧自陈：数月迭代（YouTube，§2.1）** —— `This process can take a few months`。

**(2) 学术侧数字：隐式修辞维度上人类自己都无法一致。** GHC 论文 Table 3（p.35）报告的各维度 Fleiss κ（括号内为 PABAK）：

| 维度 | Fleiss κ | PABAK |
|---|---|---|
| Assaults on human dignity (HD) | 0.23 | 0.67 |
| Calls for violence (CV) | 0.28 | 0.97 |
| Vulgarity/Offensive (VO) | 0.30 | 0.79 |
| Identity-based targeting（IDL / NAT / POL / MPH 等） | 0.18–0.29 | 0.61–0.92 |
| **Framing: Implicit or Explicit (IM)** | **0.03** | **0.38** |

作者对该维度的逐字结论（p.22）：

> "**the low agreement for Implicit/Explicit rhetoric casts doubts on their usefulness and informativeness**"

**(3) 指南里的示范例子本身会变成模型学到的捷径。** Gururangan et al., "Annotation Artifacts in Natural Language Inference Data", NAACL-HLT 2018, pp.107–112（<https://aclanthology.org/N18-2017.pdf>）：

> "We conjecture that the framing of the annotation task has a significant effect on the language generation choices that crowd workers make when authoring hypotheses, producing certain patterns in the data. **We call these patterns annotation artifacts.**" (p.107)

> "Interestingly, **the example from the SNLI annotation guidelines (Table 3)** contains both *animals* and *outdoors*, and also removes the number. **This example likely primed the annotators, inducing the specific heuristics** of replacing *dog* with *animal* and mentions of scenery with *outdoors*." (p.109)

> "This raises an important question about state-of-the-art NLI models: **to what extent are they "gaming" the task by learning to detect annotation artifacts?**" (p.110)

**要点**：**指南里写的那条示范样例，会被执行者（人）和机器同时当成捷径。** 对 Momcozy 的直接含义：`H07` 的正则 `sans douleur|schmerzfrei|sin dolor` 一旦成为唯一的示范，Agent 就会把"多语言疼痛词匹配"当成 H07 的全部，而漏掉没有直接关键词、但语义上仍构成"疼痛功效承诺"的表述（例如 `pumping shouldn't hurt`——**这条恰好出现在 PRD 第 84 行的合规样本里，被评为「合规·绿」**）。

> 引一条 PRD 里的实例（`PRD/内容治理需求文档.md:84`）：
> `Why pumping doesn't have to hurt | Expert answers on pumping` —— `风险等级：合规·绿`，`命中规则：（空）`。
> 但同一份 PRD 里 `M5 Smart's 105° flange + micro-vibration = painless pumping` 被判 `高危·红 / H07`（`:111`）。**"doesn't have to hurt" 与 "painless" 在消费者理解层面高度接近，却落在红绿两端，且记录里没有任何字段解释这个差异。** 这就是 §2.4 说的"翻译成本"在 Momcozy 数据里的具体形态。

**(4) 标注者的分歧是系统性的，不是随机噪声。** Plank, Hovy & Søgaard 2014（ACL，pp.507–511，<https://aclanthology.org/P14-2083.pdf>）：

> "**even in the absence of annotation guidelines only 2% of annotator choices are linguistically unmotivated**"

**要点**：这条常被误读。它不是说"没有指南也行"，而是说：**分歧中的绝大部分是"语言本身有歧义"，而不是"标注员马虎"**。因此，治理动作应该指向**规则文本的消歧**，而不是"加强培训/加强考核"。

**(5) 分歧有三类来源，且不能都用同一个指标压掉。** Basile et al. 2021, "We Need to Consider Disagreement in Evaluation"（ACL BPPF workshop，<https://aclanthology.org/2021.bppf-1.3.pdf>）：

> "However, this assumption is flawed for two reasons. 1) In many cases, more than one answer is correct. 2) Even where there is a single answer, **disagreement among annotators is ubiquitous, making it difficult to decide on a gold standard. We discuss three sources of disagreement: from the annotator, the data, and the context**, and show how this affects even seemingly objective tasks. **Current methods of adjudication, agreement, and evaluation ought to be reconsidered** at the light of this evidence." (p.1)

*(注：`disagreement` 原文在 PDF 中拼作 `disagreement`/`disagreemnet` 混排，上引以 PDF 文本层为准。)*

**本节小结（可直接放进交付的一句话）**：政策文本 → 可执行规则的翻译成本，等于「把每一条规则里所有依赖**意图**、**语境**、**隐式修辞**的成分，替换成**可观察的证据条件**」的成本。凡是替换不掉的，就必须显式降级为"人工复核类"，而不是留在"自动可检测"里。

**而 Momcozy 当前的 `判断方式` 字段是 21/21 全部填 `自动可检测`**（任务书 §二.A）——**这是他们目前最大的单点问题。**

---

## 3. 误差分析与规则挖掘：「错题本」的科学形态

委托方直觉上说的「错题本」，在机器学习工程里的正式名字是 **error analysis**。本节给出它的原始出处、定义、配套方法，以及"从错误到规则"的转换机制。

### 3.1 Andrew Ng：「error analysis」的原始定义与诊断法

**来源**：`Machine Learning Advice`（Stanford CS229 课程讲义，Andrew Y. Ng），30 页 PDF，<https://cs229.stanford.edu/materials/ML-advice.pdf>，本地证据 `_evidence/R4/cs229-ml-advice-ng.pdf`（320,993 字节）/ `.txt`，抓取 2026-09-15。

这份讲义是 error analysis 作为**方法论术语**的最早期权威出处之一。逐字证据：

**(a) 它被明确定位为"好的机器学习实践"（p.19）**

> "• **Good machine learning practice: Error analysis. Try to understand what your sources of error are.**"

**(b) 原始定义（p.23）——一句话，但极精确**

> "**Error analysis tries to explain the difference between current performance and perfect performance.**
> **Ablative analysis tries to explain the difference between some baseline (much poorer) performance and current performance.**"

**(c) 具体做法：逐组件注入 ground truth（p.22）**

> "**Error analysis** — How much error is attributable to each of the components? **Plug in ground-truth for each component, and see how accuracy changes.**
> Conclusion: Most room for improvement in face detection and eyes segmentation."

附带的对照表（讲义 p.22 原表）：

| Component | Accuracy |
|---|---|
| Overall system | 85% |
| Preprocess (remove background) | 85.1% |
| Face detection | 91% |
| Eyes segmentation | 95% |
| Nose segmentation | 96% |
| Mouth segmentation | 97% |
| Logistic regression | 100% |

**(d) 消融分析（ablative analysis）的具体做法（p.24）**

> "Simple logistic regression without any clever features get 94% performance. Just what accounts for your improvement from 94 to 99.9%? **Ablative analysis: Remove components from your system one at a time, to see how it breaks.**"

| Component | Accuracy |
|---|---|
| Overall system | 99.9% |
| Spelling correction | 99.0% |
| Sender host features | 98.9% |
| Email header features | 98.9% |
| Email text parser features | 95% |
| Javascript parser | 94.5% |
| Features from images | 94.0% [baseline] |

**(e) 诊断的三个层次（直升机 RL 例，p.18）——"先排除，再定位"**

> "The controller given by θRL performs poorly. Suppose that:
> 1. The helicopter simulator is accurate.
> 2. The RL algorithm correctly controls the helicopter (in simulation) so as to minimize J(θ).
> 3. Minimizing J(θ) corresponds to correct autonomous flight.
> Then: The learned parameters θRL should fly well on the actual helicopter.
> **Diagnostics:**
> 1. If θRL flies well in simulation, but not in real life, then the problem is in the simulator. Otherwise:
> 2. Let θhuman be the human control policy. If J(θhuman) < J(θRL), then the problem is in the reinforcement learning algorithm. (Failing to minimize the cost function J.)
> 3. If J(θhuman) ≥ J(θRL), then the problem is in the cost function. (Maximizing it doesn't correspond to good autonomous flight.)"

**(f) 为什么要做诊断（p.19）**

> "• Quite often, you'll need to come up with your own diagnostics to figure out what's happening in an algorithm.
> • Even if a learning algorithm is working well, you might also run diagnostics to make sure you understand what's going on. This is useful for:
> – **Understanding your application problem**: If you're working on one important ML application for months/years, it's very valuable for you personally to get a intuitive understand of what works and what doesn't work in your problem.
> – **Writing research papers**: Diagnostics and error analysis help convey insight about the problem, and justify your research claims.
> – I.e., Rather than saying "Here's an algorithm that works," it's more interesting to say "**Here's an algorithm that works because of component X, and here's my justification.**""

**要点（三条对 Momcozy 的直接含义）**：

1. **error analysis 的对象是"性能差距"，不是"错误列表"。** 定义里写的是 the difference between current performance and **perfect** performance。这意味着在动手收集错误之前，必须先定义"完美"是什么——对规则库来说就是：**每条规则的"理想判定"边界在哪**。21 条规则里没有一条写了这个。
2. **诊断的粒度是"组件"，不是"整条 pipeline"。** 对 Momcozy，组件就是 `平台 × 地区 × 语种 × 规则编号`；对 291 条记录做整体准确率是 Ng 明确反对的做法（他就是用"逐组件注入 ground truth"来避免这个）。
3. **消融分析对应"规则贡献度"**：把每条规则单独摘掉，看整体表现掉多少。**掉了 0 的规则是死规则**。Momcozy 的 21 条规则里，`命中规则` 字段的分布（从 PRD 抽样看，H07、H02、M03 命中最多，U02 已停用）可以直接算出每条的命中量，但**没有"摘掉它会有多少漏判"的数据**——因为从不做消融。

### 3.2 「先看一批样本」这条动作建议的出处与形态

`Machine Learning Yearning`（Andrew Ng 的免费书）中"error analysis"章节的具体动作建议（"手动检查约 100 个误分样本，并做成表格"）**在本调研的网络环境下未能取得原文**（见附录 B）。但这条建议的**动作形态**有可核实的等价一手证据，且更适合直接落地：

**Google PAIR Guidebook《Errors + Graceful Failure》给出了错误来源的分类加应对措施**（见 §3.2.1），而 **Meta 的 precision 度量给出了"抽样人审"的工业实现**（见 §3.2.2）。两者合起来就是"看一批样本"的完整规格。

#### 3.2.1 PAIR：错误来源分类 + 每一类的应对（逐字）

**来源**：Google PAIR (People + AI Research), *People + AI Guidebook*, 章节 `Errors + Graceful Failure`，<https://pair.withgoogle.com/chapter/errors-failing/>，抓取 2026-09-15（经本地代理），本地证据 `_evidence/R4/pair-errors-failing.html` / `.txt`。

PAIR 把 AI 系统的错误分成**三大族、七小类**，每一类都配了 Response：

**(族 1) Prediction & training data errors（预测与训练数据错误）**

| 子类 | 逐字定义 | 逐字 Response |
|---|---|---|
| **Mislabeled or misclassified results** | "When the output from the system is incorrectly labeled or classified due to poor training data. For example, inconsistently-labeled berries in the training data for a plant classification app leads to misclassification of strawberries as raspberries." | "**Allow users to give guidance or correct the data or label, which feeds back into the model to improve the dataset or alert the team to the need for additional training data.**" |
| **Poor inference or incorrect model** | "When the machine learning model isn't sufficiently precise, despite having adequate training data. For example, a plant classification app has a well-labeled dataset that includes berries, but poor model tuning returns **a large number of false positives** when identifying strawberries." | "**Allow users to give guidance, or correct the data or label, which feeds back into the AI model and helps you tune it.**" |
| **Missing or incomplete data** | "When the user reaches the edges of what the model can do based on the data it was trained on. For example, if a user tries to use a plant classification app on a dog." | "**Communicate what the system is supposed to do and how it works. Then, explain what it's missing or its limitations.** Allow users to give feedback about the needs that the system isn't meeting." |

**(族 2) Input errors（输入错误）**：`Unexpected input` / `Breaking habituation` / `Miscalibrated input`，各有 Response。
**(族 3) Relevance errors（相关性错误）**：与 context errors 相关。

**PAIR 的错误定义原则（逐字，本分片最重要的一段）**：

> "**➀ Define "errors" & "failure". What the user considers an error is deeply connected to their expectations of the AI system.** For example, a recommendations system that's useful 60% of the time could be seen as a failure or a success, depending on the user and the purpose of the system. How these interactions are handled establishes or corrects mental models and calibrates user trust."

> "**Identify user, system, and context errors**
> In non-AI systems, "user errors" are typically defined from the point of view of the system designers, and the user is blamed for "misuse" resulting in errors. "System errors" on the other hand, are typically defined from a user's point of view: users blame the system designer for a product that's not flexible enough to meet their needs. **In AI systems, users can encounter a third type of error, based on the system's assumptions about the user. These are context errors.**
> Context errors are instances in which the AI system becomes less useful through making incorrect assumptions about what the user wants to do at a certain time or place."

> "**➁ Identify error sources.** With AI systems, errors can come from many places, be harder to identify, and appear to the user and to system creators in non-intuitive ways."

> "**➂ Provide paths forward from failure.** AI capabilities can change over time. **Creating paths for users to take action in response to the errors they encounter encourages patience with the system**, keeps the user-AI relationship going, and supports a better overall experience."

**对 Momcozy 的直接映射**：把 PAIR 的七小类直接翻译成内容审查 Agent 的错误分桶：

| PAIR 子类 | Momcozy 的对应错误 | 现在能被发现吗 |
|---|---|---|
| Mislabeled or misclassified results | 规则关键词族本身写错了（如 `H07` 的 `sans douleur` 覆盖不全） | ❌ 无法发现（没有反例集） |
| Poor inference or incorrect model | Agent 判错，规则是对的 | ❌ **这正是 false positive，现在无字段记录** |
| Missing or incomplete data | 新品类/新语种/新平台的表达，21 条规则完全没覆盖 | ❌ 无法发现（**规则没命中就是"合规·绿"，没有"未覆盖"这个值**） |
| Unexpected input | 变体写法（拼音/拆字/emoji/变体拼写）绕过正则 | ⚠️ 部分可发现（未命中即绿，同样是盲区） |
| Relevance / context errors | 语境改变语义（`pumping shouldn't hurt` 是科普 vs `painless pumping` 是承诺） | ❌ 无字段 |

**这张表本身就是交付物的一部分**：它说明 **Momcozy 现在的 291 条记录只可能捕获"命中且正确"这一类结果，其余六个格子全是空的**。

#### 3.2.2 Meta：抽样人审 estimate precision 的工业实现（逐字）

Meta 公开了"看一批样本"在生产环境的标准做法。**这才是"错题本"在工业界的真实运行形态**。

**来源**：Meta Transparency Center 指标页 `Precision`（UPDATED JUL 9, 2026）与 `False Positive Volume`（UPDATED DEC 11, 2025），<https://transparency.meta.com/en-gb/...>（经本地代理抓取），本地证据 `_evidence/R4/meta-metric-precision.html` / `.txt`、`meta-metric-false-positive-volume.html` / `.txt`，抓取 2026-09-15。

**Precision 的逐字定义与算法**：

> "**What is precision** — Precision measures the accuracy of our enforcement actions on Facebook or Instagram. Specifically, **it estimates the percentage of content we actioned for violating our policies that were correctly identified as violating.**"

> "**Precision is estimated using samples of actioned content** from across Facebook or Instagram. We calculate it as: **the estimated number of actioned items that were truly violating, divided by the estimated number of total actioned items.** For example, if the precision on Facebook was 98% to 99%, that would mean of every 10,000 pieces of content actioned for this policy, 9,800 to 9,900 on average were correctly identified as violating."

> "**How we use sampling to estimate precision** — We estimate precision by sampling actioned content … **we review samples of actioned content and label them as truly violating or not violating according to our policies.** … We express this uncertainty by quoting a range of values … **This range reflects a 95% confidence window.**"

> "**Caveats** — The people who apply labels to our samples sometimes make mistakes, including labeling violations as non-violating or vice versa. … For this reason, **we may have two people review a sample to ensure accuracy in our labeling, and if there is ever a disagreement, we have a third person act as the tiebreaker.**"

> "To generate a representative measurement of global precision, **we sample and label content in the multiple languages** for Facebook and Instagram…"

**False Positive Volume 的逐字定义（★ 这是委托方「错题本」最需要的字段的工业原型）**：

> "**What is false positive volume** — **False positive volume measures the total number of non-violating content items that are incorrectly removed by our enforcement systems or human reviewers** on Facebook and Instagram. **Unlike enforcement precision, which is a percentage, false positive volume is an estimated count that quantifies the real-world impact of enforcement mistakes.**
> Another way to think about false positive volume is: **how many times did we take an action to remove content that actually complied with our Community Standards?**"

> "**How we measure false positive volume** — False positive volume is estimated by **combining the volume of actioned content with measured precision over the same period of time**. Knowing overall platform precision will most accurately reflect areas with the highest volume of actions, **we avoid using it directly to calculate false positive volume. Instead, we measure precision for a narrower subset of the platform, and then combine those precision values with the corresponding enforcement volume**… Each subset of false positive volume is then aggregated back together to produce the overall platform false positive volume.
> For example, the Community Standards Enforcement Report shows that our enforcement actions **100s of millions** of pieces of content on Facebook each quarter for spam, but **less than 10 million** pieces of content are actioned for violence and incitement. **In this case, it would not be appropriate to apply overall precision from spam enforcement to the enforcement volume for violence and incitement. Instead, we measure precision for both harms independently**…
> **In the event that a specific granularity does not have enough samples to reliably calculate precision, we leverage the precision at the next nearest level of aggregation possible.**"

> "**What Causes False Positive Volume to Change?**
> - **Changes in Enforcement Activity**: If more content is actioned overall, even a stable enforcement precision will result in higher false positive volume.
> - **Seasonal or Event-Driven Spikes**: Major events or adversarial attacks can temporarily increase enforcement actions and, consequently, false positive volume.
> - **Improvements in Detection**: Better models or reviewer training can improve enforcement precision resulting in less false positives for the same number of actions."

**这段就是本分片对委托方「错题本要怎么建」的完整技术答案**，可以直接抄成 SOP：

1. **在"命中"样本里抽样，人工标注"真的违规吗"** → 得到每条规则/每个风险类型的 **precision**。
2. **用 prevalence（在"全部内容"里抽样估违规占比）得到分母** → 见 §5.3。
3. **FP 数量 = (1 − precision) × 命中量**，**逐规则/逐风险类型单独算，不用全局数字套**。
4. **样本不够时降级到上一级聚合**（这是 Meta 明说的 fallback）。
5. **两人独立标 + 分歧时第三人裁决**（这是 IAA 的操作形式）。
6. **按语言分别抽样**（Meta 明说多语言分别抽样）。

**要点**：Meta 没有"错题本"这个产品，它有的是**一套抽样审计流程 + 六个定义清晰的指标**。委托方要的不是"一份错题清单"，而是**这个流程**。

### 3.3 主动学习（active learning）：标注预算有限时该标哪些样本

**来源**：Burr Settles, *Active Learning Literature Survey*, Computer Sciences Technical Report 1648, University of Wisconsin–Madison（Updated on: January 26, 2010），67 页，作者主页 PDF <https://burrsettles.com/pub/settles.activelearning.pdf>，本地证据 `_evidence/R4/settles-2009-active-learning-survey.pdf`（1,939,936 字节）/ `.txt`，抓取 2026-09-15。

**(a) 核心命题（Abstract 逐字）**

> "The key idea behind active learning is that **a machine learning algorithm can achieve greater accuracy with fewer training labels if it is allowed to choose the data from which it learns.** An active learner may pose queries, usually in the form of unlabeled data instances to be labeled by an oracle (e.g., a human annotator). **Active learning is well-motivated in many modern machine learning problems, where unlabeled data may be abundant or easily obtained, but labels are difficult, time-consuming, or expensive to obtain.**"

**(b) 三种查询场景（§2）**

| 场景 | Settles 的定位 | 对 Momcozy 的适配 |
|---|---|---|
| **Membership Query Synthesis**（成员查询合成） | "the learner may request labels for any unlabeled instance in the input space, including **queries the learner generates de novo**" | ⚠️ 可用来**生成对抗样本**（"如果我这样改写，规则还抓得住吗"） |
| **Stream-Based Selective Sampling**（流式选择性采样） | "each unlabeled instance is typically drawn one at a time from the data source, and the learner must decide whether to query or discard it" | ✅ **最贴合**：广告文案是持续产出的流；决定"这条要不要送人审" |
| **Pool-Based Sampling**（池式采样） | "assumes that there is a large pool of unlabeled data … and queries are selectively drawn from the pool" | ✅ **最贴合**：291 条存量 + 历史文案池 |

**(c) 不确定性采样（uncertainty sampling，§3.1）**

> "Perhaps the simplest and most commonly used query framework is **uncertainty sampling**. In this framework, **an active learner queries the instances about which it is least certain how to label.**"
> 二分类：`queries the instance whose posterior probability of being positive is nearest 0.5`
> 多分类 least confident：`x*_LC = argmax_x 1 − P_θ(ŷ|x)`
> `margin sampling`: `x*_M = argmin_x P_θ(ŷ1|x) − P_θ(ŷ2|x)`
> "**A more general uncertainty sampling strategy (and possibly the most popular) uses entropy** as an uncertainty measure: `x*_H = argmax_x −Σ_i P_θ(y_i|x) log P_θ(y_i|x)`"

**(d) 委员会查询（query-by-committee, QBC，§3.2）**

> "The QBC approach involves maintaining a **committee of models** … which are all trained on the current labeled set L, but **represent competing hypotheses**. … the learner should query the instance on which **they most disagree**."
> 分歧度量两种：`vote entropy` 与 `average KL divergence`。
> "There is **no general agreement in the literature on the appropriate committee size to use** … However, even small committee sizes (e.g., **two or three**) have been shown to work well in practice."

**(e) 密度加权（density-weighted methods，§3.6）——解决"只挑离群点"的偏置**

Settles §3.6 的动机（概括自目录与正文）：纯不确定性采样会反复挑**离群点/标注噪声**，因此把"不确定性"与"该样本在输入分布中的代表性（density）"相乘，`x*_ID = argmax_x φ_A(x) × (1/U Σ_u sim(x, x_u))^β`。

**适用条件（本节结论，供 Momcozy 选型）**：

| 方法 | 什么时候用 | 什么时候不要用 |
|---|---|---|
| **Uncertainty sampling** | Agent 输出有置信度分数时（他们的正则命中 = 高置信；语境类规则 = 低置信） | 输出只有"命中/未命中"二值时完全失效 |
| **Query-by-committee** | 有多条实现路径/多个模型可对比时（例如"纯正则版" vs "正则+LLM 语境版"） | 只有一套判定逻辑时无法用 |
| **Density-weighted** | 想避免把标注预算全花在离群样本上 | 需要优先处理高风险长尾时反而不适用（这时应该优先不确定性） |
| **随机采样（baseline）** | **永远要保留一组**，用于估计抽样偏差 | — |

**给委托方的可执行建议**：现在 291 条的抽样方式是**按投放金额倒序**（PRD 表格是按 `近7天费用USD` 降序排列的），这既不是随机采样，也不是不确定性采样，也不是密度采样——它是**"钱最多的先看"采样**。这在合规上是合理的（风险 × 暴露），但**不能用来估计任何比率**（precision、覆盖率、误判率），因为样本对"内容总体"没有代表性。**这是 §7.3 里必须补的一条。**

### 3.4 数据切片与隐藏分层：为什么"总分"会骗人

**三篇一手论文，三个层次的问题：**

**(1) Datasheets for Datasets** — Gebru et al., arXiv:1803.09010（<https://arxiv.org/abs/1803.09010>）。核心主张：数据集应附带一份"规格说明书"，记录**动机、构成、采集过程、预处理、用途、分发、维护**。

**(2) Model Cards for Model Reporting** — Mitchell et al., FAT* 2019, arXiv:1810.03993（<https://arxiv.org/abs/1810.03993>）。核心主张：模型应附一份"卡片"，**按子群（subgroup）分别披露性能**，而不是只报一个总体数字。

**(3) ★ Hidden Stratification** — Oakden-Rayner et al., "Hidden Stratification Causes Clinically Meaningful Failures in Machine Learning for Medical Imaging", arXiv:1909.12475（<https://arxiv.org/abs/1909.12475>）。这是"平均指标掩盖子群失败"最直接的一手论据：**当子群标签未被记录时，模型在子群上的系统性失败会被总体指标完全掩盖**（该文摘要原文要点：模型的整体性能看起来与基线相当，但在按疾病亚型拆分后出现显著失败）。

**对 Momcozy 的直接含义**：他们的 291 条里"投放地区"字段的分布是 `其他 216 / 法国 26 / 英国 19 / 加拿大 14 / 西班牙 11 / 意大利 3`，而平台是 `Google 262 / Meta 27`，**没有美国**。这意味着：

- **任何"我们整体合规率 XX%"的数字都是无意义的**，因为 74% 的样本落在"其他"这个桶里，而这个桶内部按语言又分成英 199 / 德 42 / 法 20 / 西 11 / 意 9 / 其他 10。
- **"其他" 是一个隐藏分层**：它同时包含了 AU / PL / EU 小国 / US（PRD 中 `投放地区 = 其他` 但落地页是 momcozy.com 美国站的样本，如 `:72`、`:74`、`:96`、`:102`）。**"没有美国"这个结论本身可能是错的**——不是没投美国，而是美国样本被归进了"其他"。

**这是任务书里"M10 之前必须解决的问题"，本分片只指出它，不负责任务书之外的数据修复。**

### 3.5 从"错误"到"规则"：四条转换机制

上面三节讲的是"怎么找错误"。委托方真正问的是"**找到之后怎么变成规则**"。四种机制，按制度化程度从高到低：

| 机制 | 操作形态 | 产出物 | 一手证据 |
|---|---|---|---|
| **A. 案例 → 泛化范围声明** | 收到一个裁决后，显式声明"同一内容 + 平行语境"的处置，且声明它**对过去与未来同时生效** | 政策条目的适用范围变更 | Meta：`These actions will affect not only content previously posted on Facebook and Instagram but also future content.`（§1.2.2） |
| **B. 建议 → 处置码 → 台账** | 把外部意见拆成 N 条 independent 条目，逐条给 4 值处置码，并公开 | 公开的处置台账 | Meta 19 条 recommendations，`Implementing fully / in part / Assessing feasibility / No further action`（§1.2.2） |
| **C. 难例 → 指南微调** | 每周 QA 例会上讨论"棘手决定"，必要时起草 guideline 增补 | enforcement guideline 的增补句 | YouTube：`guideline tweaks are then drafted to address gaps or to provide clarity for edge cases.`（§1.1） |
| **D. 难例 → 手册下一版** | 判定者记录"编码时遇到的困难"，作者据此修订手册 | 手册的新版本 | GHC 手册：`make notes about difficult cases and difficulties you had in coding, as we will use these contributions to refine and improve later versions of this manual.`（§2.2.2(g)） |

**注意 A/B/C/D 的共同点**：**它们都要求"错误"被结构化成"条目"，而不是"案例"。** 一份"错题本"如果只是把判错的广告截屏存起来，它无法驱动任何上述机制。**错题本的最小可用形态是"一条错误 = 一行结构化记录 + 一个处置码"。**

---

## 4. 回归测试与黄金集：规则不许退化

### 4.1 黄金集 / 回归门的构成原则

从 §1.1（YouTube 的划线方法）、§2.2（GHC 的 30 题上岗考试）、§2.3（OpenAI / AWS 的 category 边界写法）三处证据中，可以抽出一致的构成原则：

**原则 1：每条规则的测试集必须包含正例与反例，且反例必须是"看起来像正例"的。**
- GHC 的反例写法：`paul ryan is a traitor and its too bad we do not hang traitors anymore` → 编码为 `NH + VO`（含威胁，但不针对群体身份）。**这个反例之所以有效，是因为它含有"看起来很 hate"的介词结构。**
- OpenAI 的边界写法：`Hateful content aimed at non-protected groups (e.g., chess players) is harassment.` —— 用"看起来像 hate 但实际改判"的样例来锚定边界。

**原则 2：黄金集必须包含"对抗样本"（adversarial cases）。**
- NIST AI 600-1 的 `MP-2.3-005`（见 §4.3）要求"regular adversarial testing to identify vulnerabilities and potential manipulation or misuse"。
- Momcozy 的对抗面是明确的：拼音、拆字、emoji 替换、小语种变体拼写（`sans douleur` / `schmerzfrei` / `sin dolor` 之外还有 NL/PL/SV 的写法）、以及与 `舒适/comfort` 表述混排以规避正则。

**原则 3：黄金集必须包含"已知 bug 对应的测试用例"，且每条 bug 只增不减。**
- 这是软件工程回归测试的标准理念迁移。Momcozy 目前的等价物是"52 条风险文案改写建议库"——**但改写建议 ≠ 测试用例**：改写建议说明"应该怎么写"，测试用例说明"这样写必须被判成什么"。

**原则 4：黄金集必须冻结版本，并且与规则版本绑定。**
- OPA 的做法（见 §4.2）是测试文件与被测策略分开存放、同目录、一起进版本控制。**测试通过率是发布的必要条件。**

### 4.2 工程范式：OPA 的 `opa test`

**来源**：Open Policy Agent 官方文档 `Policy Testing`，<https://www.openpolicyagent.org/docs/policy-testing>，本地证据 `_evidence/R4/opa-policy-testing.html` / `.txt`，抓取 2026-09-15。

**(a) 官方对"为什么要给规则写测试"的表述（逐字）**

> "OPA gives you a high-level declarative language (Rego) to author fine-grained policies that **codify important requirements in your system**.
> To help you **verify the correctness of your policies**, OPA also gives you a framework that you can use to write tests for your policies. **By writing tests for your policies you can speed up the development process of new rules and reduce the amount of time it takes to modify rules as requirements evolve.**"

**(b) 官方示例的结构 —— 注意正负例成对出现**

策略文件 `example.rego`：

```rego
package authz

allow if {
    input.path == ["users"]
    input.method == "POST"
}

allow if {
    input.path == ["users", input.user_id]
    input.method == "GET"
}
```

测试文件 `example_test.rego`（**4 条测试：2 正 2 反**）：

```rego
package authz_test

import data.authz

test_post_allowed if {
    authz.allow with input as {"path": ["users"], "method": "POST"}
}

test_get_anonymous_denied if {
    not authz.allow with input as {"path": ["users"], "method": "GET"}
}

test_get_user_allowed if {
    authz.allow with input as {"path": ["users", "bob"], "method": "GET", "user_id": "bob"}
}

test_get_another_user_denied if {
    not authz.allow with input as {"path": ["users", "bob"], "method": "GET", "user_id": "alice"}
}
```

**(c) 回归门的执行**

```
$ opa test . -v
data.authz_test.test_post_allowed: PASS (1.417µs)
data.authz_test.test_get_anonymous_denied: PASS (426ns)
data.authz_test.test_get_user_allowed: PASS (367ns)
data.authz_test.test_get_another_user_denied: PASS (320ns)
--------------------------------------------------------------------------------
PASS: 4/4
```

**(d) 改坏规则会被抓住（官方原文演示）**

> "Try exercising the tests a bit more by removing the first rule in example.rego.
> ```
> $ opa test . -v
> FAILURES
> --------------------------------------------------------------------------------
> data.authz_test.test_post_allowed: FAIL (277.306µs)
> query:1     Enter data.authz_test.test_post_allowed = _
> example_test.rego:3 | Enter data.authz_test.test_post_allowed
> example_test.rego:4 | | Fail data.authz_test.allow with input as {"method": "POST", "path": …
> ```"

**要点**：这是"**规则变更前必须跑回归**"的最小可运行实现。对 Momcozy，等价形态是：**21 条规则 + 一组固定的 (内容, 期望判定) 对，任何规则改动前先跑一遍，通过率不到 100% 不许发布。**

### 4.3 对抗测试（red teaming）：NIST 的定义与要求

**来源**：NIST AI 600-1, *Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile*, July 2024, 64 页，<https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf>，本地证据 `_evidence/R4/nist-ai-600-1-genai-profile.pdf` / `.txt`，抓取 2026-09-15。

**(a) 官方定义（逐字，§A.1.5 术语表 / p.53 printed）**

> "**AI Red-teaming**: **A structured testing exercise used to probe an AI system to find flaws and vulnerabilities such as inaccurate, harmful, or discriminatory outputs**, often in a controlled environment and in collaboration with system developers."

**(b) 更完整的方法学定义（逐字，Appendix A.1.5 / p.54–55 printed）**

> "**AI Red-teaming**
> AI red-teaming is an evolving practice that references exercises often conducted in a **controlled environment and in collaboration with AI developers** building AI models **to identify potential adverse behavior or outcomes of a GAI model or system, how they could occur, and stress test safeguards**. AI red-teaming can be performed **before or after** AI models or systems are made available to the broader public; **this section focuses on red-teaming in pre-deployment contexts.**
> The quality of AI red-teaming outputs is **related to the background and expertise of the AI red team itself**. **Demographically and interdisciplinarily diverse AI red teams can be used to identify flaws in the varying contexts where GAI will be used.** For best results, AI red teams should demonstrate **domain expertise, and awareness of socio-cultural aspects within the deployment context**. **AI red-teaming results should be given additional analysis before they are incorporated into organizational governance and decision making, policy and procedural updates, and AI risk management efforts.**"

**(c) 四种红队形态（逐字）**

> "Various types of AI red-teaming may be appropriate, depending on the use case:
> - **General Public**: Performed by general users (not necessarily AI or technical experts) who are expected to use the model or interact with its outputs, and who bring their own lived experiences and perspectives… **This type of exercise can be more effective with large groups of AI red-teamers.**
> - **Expert**: Performed by specialists with expertise in the domain or specific AI red-teaming context of use (e.g., medicine, biotech, cybersecurity).
> - **Combination**: In scenarios when it is difficult to identify and recruit specialists with sufficient domain and contextual expertise, AI red-teaming exercises may leverage both expert and general public participants. For example, **expert AI red-teamers could modify or verify the prompts written by general public AI red-teamers**. These approaches may also **expand coverage of the AI risk attack surface.**
> - **Human / AI**: Performed by GAI in combination with specialist or non-specialist human teams. **GAI-led red-teaming can be more cost effective than human red-teamers alone. Human or GAI-led AI red-teaming may be better suited for eliciting different types of harms.**"

**★ 对 Momcozy 最重要的一条（逐字，`MS-2.8-002`）**：

> "**MS-2.8-002: Document the instructions given to data annotators or AI red-teamers.**"（GAI Risk 分类：Human-AI Configuration）

**要点**：**标注指南本身是必须被文档化并保存在案的受控产物。** 这条把"规则/指南文档"从"知识库里的一个文件"提升为"合规证据"。

**其他相关行动项（逐字）**：

> "**MP-2.3-005**: Implement plans for GAI systems to undergo **regular adversarial testing** to identify vulnerabilities and potential manipulation or misuse."（GAI Risk: Information Security）

> "**MP-5.1-005**: Conduct **adversarial role-playing exercises, GAI red-teaming, or chaos testing** to identify anomalous or unforeseen failure modes."（GAI Risk: Information Security）

> "**MG-2.2-001**: **Compare GAI system outputs against pre-defined organization risk tolerance, guidelines, and principles, and review and test AI-generated content against these guidelines.**"

> "**MG-2.2-005**: Engage in due diligence to analyze GAI output for **harmful content, potential misinformation**, and CBRN-related or NCII content."

> ⚠️ **条款号更正（重要）**：经全文检索，任务书提到的 **MS 2.4 与 GV-1.1-003 在 NIST AI 600-1 中不存在（0 命中）**。与红队/内容审查相关的实际条款是上列的 **MP-2.3-005、MP-5.1-005、MG-2.2-001、MG-2.2-005、MS-2.8-002**。引用时请用这些编号。

### 4.4 制度化的回归门：两种可抄的形态

**形态一：Meta 的"承诺等级"台账**（§1.2.2）。适用于**低频、高影响**的规则变更（政策级）。节奏：随案例发生；产出：公开的逐条处置表。

**形态二：YouTube 的每周 QA 例会**（§1.1）。适用于**高频、低影响**的指南微调。节奏：每周；产出：guideline 增补句。

**两种形态的对比表（给 Momcozy 的选型依据）**：

| | Meta 承诺等级台账 | YouTube 每周 QA 例会 |
|---|---|---|
| 触发物 | 外部裁决/建议 | 内部棘手判定 |
| 粒度 | 政策条目 | 指南措辞 |
| 节奏 | 事件驱动 | 每周固定 |
| 参与者 | 政策/法务/公共事务 | T&S 领导 + 全球 QA lead |
| 产出物 | 4 值处置码 + 说明 | 指南增补 |
| 可审计性 | **高**（公开存档） | 中（内部） |
| Momcozy 适配 | 平台政策更新 / 监管问询 / 重大客诉 | **周会 + 规则措辞修订** |

---

## 5. 度量：规则库的健康度怎么量化

### 5.1 先解决一个前置问题：混淆矩阵在"规则库"语境下是什么

内容审核场景的混淆矩阵与一般分类器不同，因为**"不判"也是一个动作**。把两种执行路径（自动 + 人工）都画进来，得到四格：

| | 实际违规（Ground Truth = 违规） | 实际合规（Ground Truth = 合规） |
|---|---|---|
| **Agent 判"命中"** | **TP**：正确拦截 | **FP**：误拦（**"Agent 判错但实际合规"**） |
| **Agent 判"未命中"** | **FN**：漏放（**"Agent 漏判但人工补上了"**） | **TN**：正确放行 |

**关键问题：Momcozy 现在的 291 条记录只能填出左上角（TP）与右下角（TN）两格。**

- `命中规则` 非空 + `风险等级 = 高危/审慎` → 记为 TP（**但从未验证过真的违规**，所以严格说只是"命中"，不是 TP）。
- `风险等级 = 合规·绿` + `命中规则` 为空 → 记为 TN（**但从未验证过真的合规，也可能是 FN**）。

**右上（FP）与左下（FN）两格完全为空**，因为：
- 没有"Agent 判了、人判不违规"的记录路径（`检查人` 列从 PRD 看基本为空，且 `处理状态` 只有 `无需处理` / `待人工复核` 两个值，**没有"人工推翻"这个值**）。
- 没有"Agent 没判、但人工发现了问题"的记录路径（未命中即绿，不进任何队列）。

**这就是委托方问"需不需要错题本"的技术答案：需要，而且需要的是一个能填满四格的采集结构，不是一份清单。** 具体字段设计见 §7.2。

### 5.2 人机一致性与标注者一致性：指标选择与阈值

#### 5.2.1 用哪个指标：Krippendorff 明确反对在内容分析里用 Cohen's κ

**来源**：Klaus Krippendorff, "Reliability in Content Analysis: Some Common Misconceptions and Recommendations", *Human Communication Research*, 30(3), 2004, pp.411–433，DOI `10.1093/hcr/30.3.411`。开放获取 PDF：<https://repository.upenn.edu/bitstreams/b6ea3a5b-3dee-4f27-a159-e44393eda7d4/download>，本地证据 `_evidence/R4/krippendorff-2004-reliability.pdf`（286,771 字节）/ `.txt`，抓取 2026-09-15。

**逐字（Recommendation ii）**：

> "Content analyses that assess reliability in terms of **any association coefficient, Pearson's r, for example, Benini's (1901) β, Cohen's (1960) κ, Cronbach's (1951) alpha**, Goodman and Kruscal's (1954) λr (lambda r), and %-agreement **should be rejected as these measures are incompatible with reliability concerns in content analysis.**"

**要点（重要且容易被忽略）**：**内容分析可靠性领域的权威本人明确建议不要用 Cohen's κ。** 原因是他主张可靠性必须是"多个描述之间的一致性度量"，而 κ 属于关联系数家族，且只能处理两个编码者。

**Krippendorff 推荐的替代：Krippendorff's α**，逐字（The Conservative/Liberal Continuum 一节）：

> "α can handle **multiple coders, nominal, ordinal, interval, ratio, and other metrics, missing data, and small sample sizes**."

> "For two coders and large sample sizes, α reduces not only Scott's π … but also to Spearman's ρ (rho) without ties … and to Pearson's intraclass correlation, RI…"

**⚠️ 因此本分片对委托方的建议是：主指标用 Krippendorff's α（支持多判定者、多语种、缺失值），Cohen's κ / Fleiss κ 仅作为与文献对比时的辅助指标。** 这与任务书预设（"Cohen's kappa / Krippendorff's alpha"并列）不同，属于调研后的修正。

#### 5.2.2 阈值：可接受线不是固定的，取决于"判错的代价"

**逐字（Recommendation iii）**：

> "**An acceptable level of agreement below which data are to be rejected as too unreliable must be chosen depending on the costs of drawing invalid conclusions from these data.** When human lives hang on the results of a content analysis, whether they inform a legal decision or tip the scale from peace to war, **decision criteria have to be set far higher** than when a content analysis is intended to merely support scholarly arguments. In case of the latter, to be sure that the data under consideration are at least similarly interpretable by other scholars (as represented by different coders), **I suggested elsewhere to require α ≥ .800, and where tentative conclusions are still acceptable, α ≥ .667** (Krippendorff, 2004, p. 241). **Except for perfect agreement, there are no magical numbers, however. The ones suggested here should be verified by suitable experiments.**"

**关键推论（本节最重要的结论之一）**：

> Krippendorff 明确说阈值应当**按"错误结论的代价"分档**。这意味着 Momcozy 的 `高危 / 审慎 / 待复核 / 合规` 四档**不应该共用同一个一致性阈值**：
> - `高危`（法律风险、平台封号）：需要 α ≥ .800 甚至更高
> - `审慎`：α ≥ .800
> - `待复核`（本身就是"人不确定"的类别）：α 天然低，**不应该用一致性门槛，而应该用"转人工率"和"人工处理时延"来管**
> - `合规`（放行）：需要极高的一致性与极高的 recall（因为漏放的代价在这一档最大）

**这是"严重等级"与"度量指标"之间的第一条真正的联动关系**，见 §7.5。

#### 5.2.3 Landis & Koch 的六档量表：原文不可得，但页码与内容已双重锚定

**原始文献**：

> Landis, J.R., & Koch, G.G. (1977). *The Measurement of Observer Agreement for Categorical Data*. **Biometrics 33(1):159–174**. DOI: `10.2307/2529310`. PMID: `843571`.

**⚠️ 证据等级声明**：**该文原文没有任何合法的开放副本**（Unpaywall `is_oa:false / oa_status:"closed"`；Semantic Scholar `openAccessPdf.status:"CLOSED"`；JSTOR / Wiley 付费墙）。**本报告未直接读取原文 PDF，不得声称读过。** 已核实的官方元数据（NCBI E-utilities efetch，本地 `_evidence/R4/pubmed-landis-koch-843571-abstract.txt`）：

> "1. Biometrics. 1977 Mar;33(1):159-74. The measurement of observer agreement for categorical data. Landis JR, Koch GG. … measures of interobserver agreement are developed as generalized kappa-type statistics. … PMID: 843571"

**六档量表的逐字复现 + 原始页码锚点** —— 最佳开放来源是 **Stata 官方手册**（它同时给出了原刊页码）：

**来源**：*Stata 18 Base Reference Manual*, `kappa — Interrater agreement`，"Remarks and examples → Two raters" 第 3 页，<https://www.stata.com/manuals/rkappa.pdf>，本地证据 `_evidence/R4/kappa-benchmark-scale-stata-kappa-manual.pdf`，抓取 2026-09-15。

> "The kappa-statistic measure of agreement is scaled to be 0 when the amount of agreement is what would be expected to be observed by chance and 1 when there is perfect agreement. For intermediate values, **Landis and Koch (1977a, 165)** suggest the following interpretations:
> below 0.0    Poor
> 0.00 – 0.20  Slight
> 0.21 – 0.40  Fair
> 0.41 – 0.60  Moderate
> 0.61 – 0.80  Substantial
> 0.81 – 1.00  Almost perfect"

> **★ `(1977a, 165)` 中的 `165` 就是原刊页码**（Biometrics 33(1):159–174 的第 165 页）。手册用 `1977a` 以区分 Landis & Koch 同年的另一篇 `1977b`。

**第二条独立开放复现**（同一六行，明确标注出处）：Wan Nor Arifin, *Clinical Agreement* 讲义, slide 14（<https://wnarifin.github.io/lecture/mstat/Clinical%20Agreement.pdf>）：

> "• The following guidelines by Landis and Koch (1977) is helpful for interpretation of ĸ: < 0.00 Poor / 0.00 – 0.20 Slight / 0.21 – 0.40 Fair / 0.41 – 0.60 Moderate / 0.61 – 0.80 Substantial / 0.81 – 1.00 Almost perfect"

**可以怎么引用**：正文引 `Landis & Koch (1977), Biometrics 33(1):159–174, p.165` 是安全的（**页码经 Stata 官方手册独立锚定**），但**必须注明"经 Stata 官方手册转引"**，不得暗示直接读过原文。

**⚠️ 两条必须避免的错误引用**：
1. 本目录里的 `landis-koch-1977.pdf`（4,918 字节）**是一个 Cloudflare 403 HTML 错误页，不是 PDF**，**不得引用为来源**。
2. `cohen-1960-kappa.pdf` **不是 Cohen 1960 原文**，是 University of Portland COM 425 课程讲义（其中转引了原文 Table 2）。`cohen-1960-kappa-usp.pdf` **也不是 Cohen 1960**，而是 Fleiss, Cohen & Everitt (1969), "Large Sample Standard Errors of Kappa and Weighted Kappa", *Psychological Bulletin* 72(5):323–327。**不要混用。**

**本报告的指标选择结论**：主指标仍建议用 **Krippendorff's α**（原文已取得，见 §5.2.1/§5.2.2），理由有两条：
1. α 支持**多判定者、多语种、缺失值**（Krippendorff 2004 逐字：`α can handle multiple coders, nominal, ordinal, interval, ratio, and other metrics, missing data, and small sample sizes`），而 κ 只能处理两个编码者；
2. Krippendorff 本人**明确建议在内容分析中拒绝使用 Cohen's κ**（逐字：`Content analyses that assess reliability in terms of any association coefficient … Cohen's (1960) κ … should be rejected as these measures are incompatible with reliability concerns in content analysis.`）。

**L&K 六档量表的实际用途**：仅作为**与他人结果沟通时的通用语汇**（"我们的 κ=0.23，按 L&K 量表属于 Fair"），**不作为内部质量门槛**。内部门槛用 α ≥ .800 / α ≥ .667。

#### 5.2.4 一个反直觉但很重要的补充：多数投票不提高可靠性

**逐字（Recommendation iv 末句）**：

> "**Resolving disagreements by majority among three or more coders may make researchers feel better about their data, but does not affect the measured reliability** (Krippendorff, 2004, p. 219)."

**要点**：这直接否定了"三个人投票取多数"能提升标注质量的想法。**多数投票只改变最终标签，不改变分歧本身。** 对 Momcozy：如果 Agent 与人意见不一致，**"少数服从多数"式的表决（例如 2 个 AI + 1 个人）不会提高数据可信度，只会掩盖问题**。正确的动作是把分歧**记录并分类**。

#### 5.2.5 "每条规则单独测可靠性，取最小值作为整库可靠性"

**逐字（Recommendation iv）**：

> "**All distinctions that matter should be tested for their reliability.** Where a system of several variables is intended to support a conclusion … **the reliability of each variable should be measured and the smallest among them should be taken as the reliability of the whole system.** Averaging the agreement measures of several variables, especially when they include easily coded clerical ones, **can easily mislead researchers about the reliability of variables that matter.**
> **This logic applies to individual categories as well.** … **the reliability of each distinction should be tested and the smallest one should be taken as the reliability of the whole variable.**"

**这是本分片对「规则库健康度怎么量化」的正式答案**：

> **规则库健康度 = min(每条规则的一致性/准确度)，而不是平均值。**

理由（Krippendorff 原文）：把容易的条目和困难的条目平均，会被容易的条目稀释，从而**掩盖真正危险的那几条**。这正好呼应 §3.4 的 Hidden Stratification——**平均指标会掩盖子群失败**。

### 5.3 内容审核特有的度量：三平台 + 一数据库的指标对照

#### 5.3.1 Meta：公开了 6 个可抄的指标定义

**来源**：Meta Transparency Center 指标页（经本地代理抓取），本地证据 `_evidence/R4/meta-metric-*.html` / `.txt`、`meta-cser-2026Q2.csv`（5,409 行，含 `app, policy_area, metric, period, value` 五列），抓取 2026-09-15。

| 指标 | Meta 官方定义（逐字） | 计算方式（逐字） | 更新日期 |
|---|---|---|---|
| **Prevalence**（违规内容占比） | "Prevalence considers all the views of content on Facebook or Instagram and measures **the estimated percentage of those views that were of violating content**." / "Another way to think of prevalence is **how many views of violating content we didn't prevent** — either because we haven't caught the violations early enough or we missed them altogether." | "estimated using **samples of content views** from across Facebook or Instagram. We calculate it as: **the estimated number of views that showed violating content, divided by the estimated number of total content views**." | UPDATED MAR 6, 2025 |
| **Proactive rate**（主动发现率） | "the percentage of all content or accounts acted on that **we found and actioned before users reported them to us**. We use this metric as an indicator of **how effectively we detect violations**." | 基于 actioned 内容计算；**Meta 自己指出其缺陷**："Our proactive rate **doesn't reflect how long it takes us to detect violating content or how many times it was viewed before detection.**" | UPDATED FEB 22, 2023 |
| **Precision**（判定准确率） | "it estimates **the percentage of content we actioned for violating our policies that were correctly identified as violating**." | "estimated using **samples of actioned content** … **the estimated number of actioned items that were truly violating, divided by the estimated number of total actioned items.**" 报 95% 置信区间。 | UPDATED JUL 9, 2026 |
| **False Positive Volume**（误拦量） | "**the total number of non-violating content items that are incorrectly removed** by our enforcement systems or human reviewers." / "how many times did we take an action to remove content that **actually complied** with our Community Standards?" | "**combining the volume of actioned content with measured precision over the same period of time**"；**逐 harm 分别算再求和**；样本不足时降级到上一级聚合。 | UPDATED DEC 11, 2025 |
| **Restored content**（恢复量） | "the number of pieces of content … we restored after we originally took action on them. By 'restore,' we mean **returning content that we previously removed** or removing a cover from content that we previously covered with a warning." | 分开报告"应申诉恢复"与"未申诉主动恢复"。Meta 明确警告："**It might be tempting to read this metric as an indicator of the mistakes we make … However … restoring a post doesn't necessarily mean a mistake was made.**" | UPDATED OCT 4, 2022 |
| **Appealed content / Content actioned** | 见 `meta-metric-appealed-content.txt`、`meta-metric-content-actioned.txt` | 分季度报告；Meta 明确警告季度口径不可直接相减（恢复可能对应上一季度的申诉）。 | — |

**Meta 方法论上三个可直接抄的细节**：

1. **抽样审计，不是全量核对。** `We estimate precision by sampling actioned content.`
2. **两人独立标 + 第三人裁决。** `we may have two people review a sample to ensure accuracy in our labeling, and if there is ever a disagreement, we have a third person act as the tiebreaker.`
3. **多语种分别抽样。** `we sample and label content in the multiple languages for Facebook and Instagram` —— 对 Momcozy 意味着**英/德/法/西/意 必须分别抽样，不能混算**。

#### 5.3.2 YouTube：「违规观看率」（violative view rate）与申诉/恢复数字

**来源**：YouTube 官方博客（同 §1.1），逐字：

> "To measure the effectiveness of our enforcement, we release a metric called our **violative view rate**, which looks at **how many views on YouTube come from violative material**. From July through September of this year, that number was **0.10% – 0.11%**, which means that for every 10,000 views, between 10 and 11 were of content that violated our Community Guidelines."

> "We also track the number of appeals submitted by creators in response to videos that are removed … For example, during the same time period mentioned above, **we removed more than 5.6 million videos** for violating our Community Guidelines and **received roughly 271,000 removal appeals**. Upon review, **we reinstated about 29,000 appeals**."

> "And while metrics like appeals, reinstatements, and our violative view rate **don't offer a perfect solution to understand consistency or accuracy**, they're still pivotal in benchmarking success on an ongoing basis."

**要点**：YouTube 的"违规观看率"与 Meta 的 "prevalence" 是**同一个概念**（违规内容的曝光占比），只是分母表述不同（views vs content views）。**两家独立采用同一概念，说明这是行业收敛的口径。**

**可直接算出的派生指标**：
- 申诉率 = 271,000 / 5,600,000 ≈ **4.84%**
- 申诉成功率 = 29,000 / 271,000 ≈ **10.7%**
- 即：**YouTube 的自动/人工移除里，约 0.52% 最终被恢复**。

#### 5.3.3 ★★ EU DSA Transparency Database：一份"法定的结构化错题本"schema

**这是本分片找到的、对委托方"错题本最小字段集"问题最直接、最权威的答案。**

**来源**：EU DSA Transparency Database 官方文档（European Commission, DG CNECT 运营），<https://transparency.dsa.ec.europa.eu/> 的 `Documentation → Overview` 与 `Explore Data → Download`，本地证据 `_evidence/R4/dsa-tdb-documentation.html` / `.txt`、`dsa-tdb-download-page.html` / `.txt`、`dsa-tdb-api-doc.html` / `.txt`、`dsa-tdb-additional-explanation.html` / `.txt`，抓取 2026-09-15。

**它的性质**：依据 DSA **Art 17（Statement of reasons）**，平台对每一次内容审核决定都必须向接收者发一份"理由说明"，并**同时提交到该公共数据库**。官方对该数据库的定位（逐字）：

> "The DSA Transparency Database is **structured in a way that enables transparency and scrutiny over the content moderation decisions of online platforms**. This page explains what type of information is collected, and **how the different data fields map onto Article 17 DSA**…"

**★ 16 个法定数据点的完整清单（逐字标题，这是 DSA 版"错题本行"的字段表）**：

| # | 官方字段名（逐字） |
|---|---|
| 1 | **A Platform Unique Identifier (PUID)** |
| 2 | **Specifications on the content that is affected by the statement** |
| 2.1 | Type of content affected（`app, audio, image, product, synthetic media, text and video`，**可多选**） |
| 2.2 | Specification of Content Type "Other" |
| 2.3 | Date on which the content was created on the online platform |
| 2.4 | Language of the content |
| 2.5 | Content identifier |
| 3 | **The type of restriction(s) imposed** |
| 3.1 | Decision to restrict visibility |
| 3.2 | Specification of other visibility restriction |
| 3.3 | Decision to restrict monetary payments |
| 3.4 | Specification of other monetary restriction |
| 3.5 | Decision to restrict the provisioning of the service |
| 3.6 | Decision to restrict access to the account |
| 4 | **The duration of the restriction** |
| 4.1 | Application Date |
| 4.2–4.5 | End date for visibility / monetary / service / account restrictions |
| 5 | **The territorial scope of the restriction** |
| 6 | **A description of the facts and circumstances** |
| 7 | **Information on the source of the investigation**（7.1 Information source；7.2 The identity of the notifier） |
| 8 | **Information on the account affected by the decision**（Account type：`business user` vs `private account`） |
| 9 | **Information on the use made of automated means for the detection of infringements** |
| 10 | **Information on the use made of automated means for taking decisions on infringements** |
| 11 | **The decision grounds** |
| 12 | For allegedly illegal information: the legal ground relied upon（12.1 Reference to the legal ground；12.2 Explanation of the applicability of the legal ground） |
| 13 | For allegedly infringing information: the contractual ground relied upon（13.1 Incompatible Content Grounds；13.2 Incompatible Content Explanation） |
| 14 | **Overlap between incompatibility and illegality** |
| 15 | **Reference (URL) to the legal or contractual ground** |
| 16 | **Category & Category specification**（16.1 自由文本补充字段） |

**★ 四个字段的逐字定义（对本报告 §7.2 的字段设计有直接指导意义）**：

> **9. Automated Detection** — "This attribute indicates **whether and to what extent automated means were used to identify** the specific information addressed by the decision. 'Yes' means that automated means were used to identify the specific information addressed by the decision."

> **10. Automated Decision** — "This attribute indicates **whether and to what extent automated means were used to decide on the infringing nature** of the specific information addressed by the decision. **'Fully automated' means that the entire decision-process was carried out without human intervention.** This attribute **does not refer to the identification of such content, but solely to the decision taken after the identification.** 'Not automated' means that the entire decision-process was carried out without the use of automated means. **'Partially automated' means that both automated means and human interaction were applied** in the process of taking a decision regarding the infringing nature of the information."

> **14. Overlap between TOS incompatibility and illegality** — "Some information that is incompatible with the terms and conditions of a service can simultaneously be illegal. This optional field allows to indicate whether information that was restricted on the basis of an alleged incompatibility with the terms and conditions **was also considered illegal** by the online platform. **Leaving this optional field blank does not imply that the online platform considers that the content is not illegal.**"

> **7.1 Information source** — "This attribute describes **what led to the investigation of the content**… An investigation can be based on **a notice submitted in accordance with Article 16 DSA; a notice submitted by a trusted flagger under the DSA; any other external notification; or the online platform's own voluntary initiative.**"

> **16.1 Field to add an open specification** — "For those statements of reasons where platforms feel that **no existing specification properly reflects the grounds they used**, this section allows for a **free text submission** to add specifications. **The Commission will monitor the submissions in this free text field and update the options in `category_specification` accordingly, should recurring submissions prevail.**"

**★★ 最后这一条（16.1）值得单独指出**：**监管机构自己设计了"规则库盲区的采集机制"** —— 当平台发现现有分类无法描述某个判定理由时，可以自由文本提交；**监管方定期看这个自由文本字段，出现重复的模式就把它升级为一个正式分类。** 这正是委托方要的「从案例反推规则」在法规层面的实现。

**数据可获取性（逐字，`Explore Data → Download` 页）**：

> "On this page, you can download **zipped csv files containing the daily submissions of statements of reasons**, either for **all platforms collectively or for each platform individually**. The files are provided in **full and light versions**.
> You can also download these files in **Parquet format** for the full, global version…
> **Full archive files contain all the public data points** of each individual statement of reasons submitted on a given day. That is, each file contains the **entire attribute schema of the database**. **Light archive files only contain a subset** of the attribute schema of the database, notably **no free text fields with a character limit higher than 2000 characters** (i.e. `illegal_content_explanation`, `incompatible_content_explanation` or `decision_facts`). **Light archive files also do not contain the `territorial_scope` attribute.**"

> "To download a compact, **aggregated version of the data in csv or Parquet format**, reporting the number of statements of reasons sharing the same categorical features, you can visit the `dsa-tdb` package documentation. **Two types of aggregations are provided: the basic aggregation currently feeding the Dashboard and an** [advanced one]."

**要点（三条）**：

1. **这是一份现成的、免费的、可批量下载的"平台实际执法行为"数据集。** 字段包含 `content_type` / `language` / `territorial_scope` / `decision_ground` / `category` / `automated_detection` / `automated_decision` / `source_type`。**对 Momcozy 的直接用途**：查"母婴/健康类目在 EU 各语种下，平台实际以什么理由下架了什么内容"。这是**唯一可得的、真实的"别人被罚了什么"的一手数据**（但要与 R2 分片的裁决案例库配合使用，本分片不展开）。
2. **免费全文下载（full 版）包含全部字段与自由文本解释**，即 `illegal_content_explanation` / `incompatible_content_explanation` / `decision_facts`。**这是真正的"错题本原文"**——每条记录都带"事实与情节描述"。
3. **`automated_detection` 与 `automated_decision` 被强制拆成两个字段**，且 `automated_decision` 有 `Fully automated / Partially automated / Not automated` 三值。**这是"判定路径必须落库"的法规级证据**（呼应 §7.2.1 的字段 #8：Meta 因未记录判定路径，而无法计算 Oversight Board rec.13 要求的对比错误率）。

#### 5.3.5 TikTok：两个"分母不同"的率，不可与 Meta/YouTube 同图比较

**来源**：TikTok Transparency Center `Community Guidelines Enforcement Report`（2026 Q1 正文与官方原始 CSV / 数据字典），<https://www.tiktok.com/transparency/en/cg-report>（经本地代理），本地证据 `_evidence/R4/tiktok-transparency-reports.html`、`tiktok-cg-report-2025h1.html`、`tiktok-cg-enforcement.html`，抓取 2026-09-15。

**逐字定义**：

> （图表脚注）"**Proactive removal means identifying and removing a video before it's reported.**"

> （2026Q1 正文）"Automated removals, including those by AI, now make up **more than 96% of total removals**."

> （数据字典 `CGER_README.txt`）"**Values may be omitted for privacy if they represent fewer than 1,000 users.**"

**2026 年 1–3 月（官方原始 CSV 汇总行，All/All）**：

| 指标 | 数值 |
|---|---|
| Total videos removed | **184,012,576** |
| **Proactive removal rate** | **0.993** |
| **Video: Removal rate of published** | **0.005** |
| Removal rate within 24h | 0.944 |
| Comments removed | 237,517,128 |
| Comment removal rate | 0.002 |
| LIVE sessions suspended | 50,791,858 |
| **Videos restored** | 8,838,710（÷ 总移除 ≈ **4.80%**） |
| Accounts removed（under-13 / fake / other） | 25,764,372 / 2,860,632 / 2,410,387 |

**★★ 本节最重要的一条口径警告**：**"主动发现率"不是覆盖率。**

Meta 官方对这一点的自陈最清楚（逐字，`proactive-rate` 指标页）：

> "**Our proactive rate doesn't reflect how long it takes us to detect violating content or how many times it was viewed before detection. It also doesn't reflect how many violations we failed to detect altogether** or how many times that content was viewed."

**因为它的分母是"已处置量"（acted-on content），而不是"全部内容"。** 同理，TikTok 的 `Proactive removal rate 0.993` 的分母也是已处置量。

**四个"率"的分母对照（★ 本报告要求：这四个数不能放在同一张图里比较）**：

| 度量 | 分母 | 分子 | 最新值 |
|---|---|---|---|
| Meta **Prevalence** | 全部内容**浏览量**（抽样估算） | 违规内容浏览量 | FB Hateful Conduct **0.02%**；Terrorism / Firearms / Suicide 等 4 类仅给 **`<0.05%` 上界** |
| YouTube **VVR** | 全部视频**浏览量**（5 层动态分层随机抽样，每日抽样） | 违规视频浏览量 | Q2 2026 **0.0015–0.0017** |
| TikTok **Proactive removal rate** | **已处置**视频数 | 用户举报前即被处置的视频数 | **99.3%** |
| TikTok **Video: Removal rate of published** | **已发布**视频数（全量计数） | 被移除视频数 | **0.5%** |

**只有前两个在数学上等价于"未被拦截的违规占比"（即覆盖率的可能定义之一）；后两个都不能用来推断漏检量。**

#### 5.3.6 YouTube 的 VVR 方法学（分层随机抽样，可抄的抽样设计）

**来源**：Barnett, A. (2021), *YouTube's Violative View Rate Methodology: A Statistical Assessment*（Google 委托的方法学论文，16 页），Google 公开 GCS bucket `storage.googleapis.com/transparencyreport/`，本地证据见 `_evidence/R4/_gcs-listing.txt`，抓取 2026-09-15。

> "**The VVR is the percentage of views of videos on the YouTube platform that violate its Community Guidelines.**"（p.1）
> "the population of interest is **all YouTube views**"（p.5）
> "YouTube decided that it would create **five strata**… **Random sampling would then take place among the views in each stratum, meaning that a given video's probability of selection would be proportional to the number of people who viewed it. Each sampled video would be evaluated by a trained person**…"（pp.5–6）
> "the sample sizes in the five ranges are **revised each day based on actual VVR rates in those ranges over the 90 preceding days**"（p.7）
> "**The quarterly VVR is an average of 9 daily VVR estimates, weighted by the number of views**"（p.7）

**★ 这段是"如何抽样"的完整可抄范式**，比 Meta 的说明更具体：
1. **总体 = 全部曝光**（不是内容，是 views）；
2. **分 5 层**（strata）；
3. **层内随机抽样**，样本入选概率与曝光量成正比；
4. **每条抽样内容由受过训练的人评估**；
5. **各层样本量每日根据过去 90 天的实际 VVR 动态调整**（解决"稀有类别样本不足"问题）；
6. **季度值 = 9 次日估计的加权平均**（权重为曝光量）。

**对 Momcozy 的直接映射**（`[推断]`）：他们的"内容总体"是每日在跑/待发布的广告与社媒内容；**分层变量建议用 `平台 × 风险暴露档（展示量分位）`**；**每层每日随机抽固定条数**；**稀有类别（如小语种）提高抽样率**。

#### 5.3.7 三平台指标口径对照表（★ 不得混用）

| 维度 | **Meta** | **YouTube** | **TikTok** |
|---|---|---|---|
| 违规占比指标名 | Prevalence | Violative View Rate (VVR) | Video: Removal rate of published |
| 分母 | 全部内容浏览量（抽样估算） | 全部视频浏览量（分层随机抽样） | 已发布视频数（全量计数） |
| 抽样方式 | 抽样估算（views） | 5 层动态分层随机抽样，每日重算，90 天回看 | 全量计数 |
| 最新值（2026 H1 / Q2） | Hateful Conduct **0.02%**；4 类仅 `<0.05%` 上界 | Q1 0.0017–0.0019；Q2 0.0015–0.0017 | **0.005** |
| 判定准确率指标 | **Precision**（FB 全网 **90.80–91.85%**；IG **90.78–92.24%**） | **Precision 0.874–0.896** | 未在该报告中以同期指标披露 |
| 误拦量指标 | **False positive volume**（2026Q2：**30.2–30.8M**） | 通过申诉推翻率体现（**25.1%**） | 通过 restored 数体现（8,838,710，≈4.80%） |
| 主动发现 | Proactive rate（FB Hateful Conduct **66.40%**；Spam **99.60%**） | 未单独列该指标名 | **Proactive removal rate 0.993** |
| 申诉/恢复 | Appealed / Restored（含无申诉主动恢复） | 内部申诉 365,511 → **reversed 91,810**，中位 **5 天** | Videos restored 8,838,710 |
| 官方对指标的自我限定 | "**This metric shouldn't be interpreted as an indicator of the accuracy of our decisions**"（appealed-content 页） | "**don't offer a perfect solution to understand consistency or accuracy**"（YouTube 博客） | 数值 <1,000 用户时因隐私省略 |

**这张表本身就是一条结论**：**三家平台没有任何一个指标口径是相同的**，甚至同一个名字（"主动发现率"）的分母都不同。**委托方在设计自己的看板时，必须先写清分母，再写指标名。**

#### 5.3.4 Santa Clara Principles 2.0：要求公开的数字清单（逐字）

**来源**：Santa Clara Principles on Transparency and Accountability in Content Moderation, 2.0 版，<https://santaclaraprinciples.org/>，本地证据 `_evidence/R4/santa-clara-principles.html`（31,712 字节）/ `.txt`，抓取 2026-09-15。

该文件由 14 家组织共同制定（Access Now、ACLU of Northern California、ACLU of Southern California、ARTICLE 19、Brennan Center for Justice、Center for Democracy & Technology、Electronic Frontier Foundation、Global Partners Digital、InternetLab、National Coalition Against Censorship、New America's Open Technology Institute、Ranking Digital Rights、Red en Defensa de los Derechos Digitales、WITNESS），2018 年首版（**1.0**），2020–2021 年经 50+ 组织 consultation 修订为 2.0。

**2018 年 1.0 原版三条原则（逐字要点，<https://santaclaraprinciples.org/scp1>，本地证据 `_evidence/R4/santaclara-scp1-2018.html`）**：

> **1. Numbers** — 六项拆分维度：flagged 总数 / removed 总数 / **by category of rule violated** / by format of content / **by source of flag** / by locations。并要求："This data should be provided in a regular report, **ideally quarterly, in an openly licensed, machine-readable format**."
>
> **2. Notice** — 四项最低要素：URL 或内容片段、**具体违反的条款**、检测与移除方式、申诉流程说明。
>
> **3. Appeal** — 三项最低标准：**由未参与初判的人或小组做人工复审**、可提交补充信息、告知结果与理由。

**⚠️ 一处"未核实"**：任务书及部分二手材料提到的 SCP 2.0 新增 "State of Content Moderation" 报告要求，**在 SCP 2.0 全文与 Open Consultation Report 中 grep 零命中 → 未核实，不得引用该专名。**

**结构**：`Foundational Principles`（5 条）+ `Operational Principles`（3 条：Numbers / Notice / Appeal）+ `Principles for Governments and Other State Actors`。

**五项基础原则（逐字标题 + 核心句）**：

1. **Human Rights and Due Process**：`Companies should only use automated processes to identify or remove content or suspend accounts, whether supplemented by human review or not, when there is sufficiently high confidence in the quality and accuracy of those processes.`
2. **Understandable Rules and Policies**：`Companies should publish clear and precise rules and policies … Users should be able to readily understand the following: What types of content are prohibited … **with detailed guidance and examples of permissible and impermissible content**`
3. **Cultural Competence**：`those making moderation and appeal decisions understand the language, culture, and political and social context of the posts they are moderating` / `Companies will report data that demonstrates their language, regional, and cultural competence for the users they serve, **such as numbers that demonstrate the language and geographical distribution of their content moderators.**`
4. **State Involvement in Content Moderation**
5. **Integrity and Explainability**：`Companies should actively monitor the quality of their decision-making to assure high confidence levels, and are encouraged to publicly share data about the accuracy of their systems and to open their process and algorithmic systems to periodic external auditing.`

**★ Numbers 原则要求公开的完整数字清单（逐字，这是"度量"一节最可抄的部分）**：

> "Companies should publish information about pieces of content and accounts actioned, **broken down by country or region, if available, and category of rule violated**, along each of these dimensions:
> - Total number of pieces of content actioned and accounts suspended.
> - **Number of appeals** of decisions to action content or suspend accounts.
> - **Number (or percentage) of successful appeals** that resulted in pieces of content or accounts being reinstated, and the number (or percentage) of unsuccessful appeals and;
> - **Number (or percentage) of successful or unsuccessful appeals of content initially flagged by automated detection.**
> - **Number of posts or accounts reinstated by the company proactively, without any appeal, after recognition that they had been erroneously actioned or suspended.**
> - Numbers reflecting enforcement of hate speech policies, by targeted group or characteristic, where apparent…
> - Numbers related to content removals and restrictions made during crisis periods…"

自动化相关的额外披露要求（逐字）：

> "companies should publish information relating to:
> - **When and how automated processes are used** (whether alone or with human oversight) when actioning content.
> - The categories and types of content where automated processes are used;
> - **The key criteria used by automated processes for making decisions**;
> - **The confidence/accuracy/success rates of automated processes, including changes over time and differences between languages and content categories**;
> - The extent to which there is human oversight over any automated processes, including **the ability of users to seek human review** of any automated content moderation decisions;
> - The number (or percentage) of successful and unsuccessful appeals when the content or account was first flagged by automated detection, **broken down by content format and category of violation**;
> - Participation in cross-industry hash-sharing databases…"

> "All data should be provided in a regular report, ideally quarterly, in an **openly licensed, machine-readable format**."

**Notice 原则要求的通知内容（逐字）**：

> "When providing a user with notice about why their post has been actioned, companies should ensure that notice includes:
> - URL, content excerpt, and/or other information sufficient to allow identification of the content actioned.
> - **The specific clause of the guidelines that the content was found to violate.**
> - **How the content was detected and removed** (flagged by other users, trusted flaggers, automated detection, or external legal or other complaints)."

**Appeal 原则的核心要求（逐字）**：

> "Human review by a person or panel of persons **who were not involved in the initial decision**." / "An opportunity for users to **present additional information** in support of their appeal that will be considered in the review." / "**According to the principle of proportionality, companies should prioritize providing appeal for the most severe restrictions**, such as content removal and account suspension."

**2018 → 2023（2.0）的增量（逐字证据）**：

> "This second iteration of the Santa Clara Principles is **divided into Foundational and Operational Principles**. Foundational Principles are overarching and cross-cutting … The Operational Principles set out **more granular expectations for the largest or most mature companies** with respect to specific stages and aspects of the content moderation process. **Smaller, newer, and less resourced companies may also wish to use the Operational Principles for guidance**… **In contrast to the minimum standards set out in the first iteration, this second iteration provides greater specificity regarding precisely what information is needed** to ensure meaningful transparency and accountability."

> "This second iteration of the Santa Clara Principles **expands the scope of where transparency is required** with respect to what is considered **"content"** and **"action"**… The term "content" refers to **all user-generated content, paid or unpaid, on a service, including advertising.** The terms "action" and "actioned" refer to **any form of enforcement action** … including (but not limited to) the removal of content, **algorithmic downranking of content**, and the suspension (whether temporary or permanent) of accounts."

**⚠️ 对 Momcozy 极易被忽略的一点**：2.0 版明确把 **"包括广告在内的付费与 unpaid 内容"** 纳入"content"定义，并把 **"算法降权"** 纳入 "action"。**这意味着"广告文案审查"完全是这套原则的适用对象**，而他们的 291 条全部是付费广告。

### 5.4 覆盖率（coverage）：⚠️ 已穷尽检索，**未找到标准定义**

**结论先行**：**"规则库覆盖率"在内容审核 / DSA / NIST / 平台透明度报告中，不存在标准的量化定义。**

**已穷尽的检索范围（可复现）**：DSA Art 15 / 17 / 24 / 34 / 35 / 37 / 42 全文；DSA Transparency Database 全部官方文档与 schema；European Commission 官方 FAQ；Meta / YouTube / TikTok 全部指标定义页；Meta CSER 数据字典（含 5,409 行 CSV）；TikTok CGER README 与术语表；Santa Clara Principles 1.0 与 2.0 全文；OpenAlex 三组语义检索（`coverage of content moderation policies` / `rule coverage audit content moderation` / `measuring completeness of content moderation policy taxonomies`）。**没有任何一手来源给出定义。**

**以下四条是最接近的一手材料，按贴合度排序：**

**(1) ★★ DSA 法定模板把"漏检"落到了 `Recall` 字段上——这是唯一被法规模板承接的覆盖率型指标。**

YouTube 在其 DSA 透明度报告（H1 2026）的 `8_automated_means.csv` 中，把 `Accuracy of the automated means - Recall` 这个字段填成了 **VVR（Violative View Rate）**：Q1 为 `0.0017–0.0019`、Q2 为 `0.0015–0.0017`、Comments H1 为 `0.0013–0.0018`，与同一份报告中的 `Precision 0.874–0.896` 并列申报。

> **语义**：DSA Art 15(1)(e) 要求申报"自动化手段的准确性与可能错误率"（见下），**YouTube 用 VVR 来充填其中代表"漏检"的那一侧**。这是"覆盖面"在法规模板中**唯一被量化落地的实例**。

**(2) DSA Art 15(1)(c)：法条用"三维交叉完备性"替代覆盖率概念。**

> "the information reported shall be **categorised by the type of illegal content or violation of the terms and conditions of the service provider, by the detection method and by the type of restriction applied**"

即：要求按 **（违规类型 × 检测方式 × 处置类型）三维交叉全量披露**。这是"规则库覆盖率"在法规文本中最接近的等价物——**要求"每一格都要有数"**，但法条本身**不定义覆盖率数值**。

**(3) DSA Art 15(1)(e)：唯一被点名的准确度义务。**

> "**any use made of automated means for the purpose of content moderation, including a qualitative description, a specification of the precise purposes, indicators of the accuracy and the possible rate of error of the automated means used in fulfilling those purposes, and any safeguards applied.**"

**(4) DSA Art 42(2)(c)：准确度指标必须按每种官方语言切分——语言维度的强制覆盖。**

> "the indicators of accuracy and related information referred to in Article 15(1), point (e), **broken down by each official language of the Member States**"

**(5) 反证：DSA Art 34 / 35 全篇不含任何百分比、阈值或覆盖率定义**，只有过程义务（`diligently identify, analyse and assess`）。**这从反面说明：监管也不认为"覆盖率"是一个可直接量化的合规指标。**

**(6) 四个"分母式"行业度量的口径互不相同（见 §5.3.7 的对照表）**，其中只有 Meta prevalence 与 YouTube VVR 是"分母覆盖式"度量。

---

**本报告建议的自建定义（明确标注为"本报告的构造，非引文"）**：

> **规则库覆盖率（Coverage Rate）** = 在**随机抽样的内容样本**中，被至少一条规则明确判定（命中或明确豁免）的样本占比。
>
> **规则库盲区率（Blind-spot Rate）** = 1 − Coverage Rate = 抽样样本中，**所有规则都不命中、且无任何规则对其表述过边界**的样本占比。
>
> **关键设计要求**：必须存在一个第三态的判定结果 `未覆盖`（既不是"合规"也不是"违规"）。**如果系统的输出只有"命中/未命中"，盲区率在数学上不可观测。**

**这一条对 Momcozy 是当务之急**：他们的 `风险等级` 只有四档（高危/审慎/待复核/合规），其中"合规"同时承担了"确认合规"与"规则没覆盖到"两种含义。**这是一个语义重载，必须先拆开。**（见 §7.5）

**`[推断]` 一条可直接落地的替代方案**：既然"覆盖率"没有标准定义，就**不要发明一个百分比**，而改用 DSA Art 15(1)(c) 的**三维交叉完备性**作为操作性替代——**做一张 `规则族 × 语种 × 平台` 的交叉表，空格子就是盲区。** 这比任何自造的"覆盖率 XX%"都更可审计，且直接对齐法规语言。

## 6. 冷启动：「要是没有规则呢？怎么办？」

这是委托方的直接追问。本节给出**五个法域/标准体系**的官方答案，它们收敛到同一个结论。

> **本节证据来源说明**：EU AI Act、DSA、UK OSA、Ofcom、ISO、COM(2000)1 的原文抓取由本分片的兄弟取证线完成，原始文件在 `_evidence/R4/`（`eu-ai-act-2024-1689.*`、`dsa-2022-2065.*`、`uksa-s9.html.txt`…、`ofcom-childrens-risk-assessment-guidance.*`、`iso-*-official-page.txt`、`eu-com-2000-1-precautionary.*`）。**条款号已按其核查结果修正，未沿用任务书原编号**（见各节 ⚠️ 标注）。

### 6.1 平台自己的兜底条款：五家原文对照

**先给结论：平台政策里都存在兜底条款，且全部是"条件式"的，没有无条件宽容。**

| 平台 | 兜底表述（逐字） | 触发条件 | 后果 |
|---|---|---|---|
| **Meta** | "**In other cases, we may remove content that uses ambiguous or implicit language when additional context allows us to reasonably understand that the content goes against our standards.**" | 措辞含糊/隐含 **且** 结合额外语境可判定违反标准 | **移除** |
| **Meta** | "In some cases, **we allow content – which would otherwise go against our standards – if it's newsworthy and in the public interest.**" | newsworthy + public interest，且经"公共利益价值 vs 伤害风险"权衡 | **放行**（例外） |
| **Google Ads** | "**Advertisers have a responsibility not to promote content or engage in behavior that risks harm to our users, employees, or the Ads ecosystem. If we see such content or behavior, we may take action, including but not limited to restricting or blocking your ads or suspending your account.**" | 内容**或行为**对用户/员工/广告生态构成伤害风险（**独立于内容清单**） | 限制、屏蔽广告，暂停账户 |
| **Google Ads** | "Google Ads **only allows ads, assets, and destinations that are clear, easy to interact with, and relevant to users.** Examples … (**non-exhaustive**)" | Editorial 标准不达标（如 vague phrases） | 拒登/下架 |
| **YouTube** | "Sometimes, content that would otherwise violate our Community Guidelines **may stay on YouTube when it has Educational, Documentary, Scientific, or Artistic (EDSA) context** … **This is not a pass to violate our Community Guidelines.**" | 具备 EDSA 语境或属公共利益 | **保留**，获 "EDSA exception" |
| **YouTube** | "These policies apply to all types of content on our platform … **This list isn't complete.**" | 内容类型未被列举 | 政策仍适用（**清单非穷尽**） |
| **YouTube** | "**If a YouTube creator's on- and/or off-platform behavior harms our users, community, employees or ecosystem, we may respond based on a number of factors including, but not limited to, the egregiousness of their actions and whether a pattern of harmful behavior exists.**" | **平台外**行为造成伤害 | 暂停权限 → 终止账户 |
| **TikTok** | "We recognize that **some content that would otherwise violate our rules may be in the public interest to view.** … We may allow content to remain on TikTok under public interest exceptions, including: **Documentary / Educational / Medical or Scientific / Counterspeech / Satirical / Artistic**" | 落入 6 类具名例外 | **保留但降级**：FYF 不合格 / 警告屏 / 语境标签 |
| **TikTok** | "**We won't make exceptions for content that could cause extreme harm**" | 极端伤害 | 不适用例外 |
| **TikTok** | "These examples are meant to guide you, but **they don't cover every situation.**" / "**Even with our robust moderation measures and processes, we can't guarantee that all content complies with our Community Guidelines or Terms of Service.**" | 情形未被覆盖 | 规则仍适用 / 免责声明 |
| **Amazon** | "**It is the Vendor and Seller's responsibility to comply with all applicable laws and rules and regulations** that apply to the Vendor or Seller, the content of the Store, and any location where the Store appears." | 任何未在平台政策中列明的法律/法规要求 | **义务整体转移给广告主** |
| **Amazon** | "…may not be sexually explicit or obscene, **as determined at the sole discretion of Amazon**."（限贴身衣物图像） | 平台单方判断 | 拒绝/移除素材 |

> ⚠️ **两条"任务书预期但实际不存在"的表述，不可引用**：
> 1. Google Ads 的 `"Google reserves the right to…"` ——**官方政策页 0 命中**（已用实际存在的三条兜底替代）。
> 2. TikTok 的 `"new or emerging"` 内容类型表述 ——**0 命中**（TikTok 实际用的是 "Public Interest Exceptions" + 版本更新公告）。
> 另：任务书预期的 YouTube "age-restriction" 表述**不在** Community Guidelines 主页；该页明确 EDSA 的结果是 `gets an EDSA exception`，年龄限制措辞需查各具体政策子页（本分片未抓）。

**四家对照的三条横向结论**：

1. **兜底有三种形态**：**例外型**（Meta/YouTube/TikTok 的公共利益放行）、**覆盖宣告型**（"list isn't complete"）、**义务转移型**（Amazon）。
2. **唯一给出"具名例外清单"的是 TikTok（6 类）**，且其后果是**降级而非放行**（FYF 不合格/警告屏/语境标签）——这是四家中最接近"规则外可操作中间态"的范式。
3. **Google 的兜底最宽**：以 "content **or behavior**" 与 "risks harm to our users, employees, or the Ads ecosystem" 为独立触发要件，**不依赖内容清单**。

**对 Momcozy 的直接设计含义**：规则库的尾部应该有一条**显式的兜底条目**，形态参照 TikTok：

```
规则编号：CATCH-ALL-01
边界类型：规则外兜底
风险等级：待复核（不可自动放行）
触发条件：所有其他规则均未命中，且命中以下任一"风险信号"（医学/疗效类词汇、
         比较级/最高级、绝对化用语、身份背书、数据声明、场景暗示）
判断方式：仅转人工（禁止自动判定为"合规"）
处置：进入人工队列，并强制记录"是否构成新规则"（是/否 + 理由）
```

**核心要求是"未命中 ≠ 合规"，而是"未命中 = 未覆盖，转人工并记录"。** 这是把兜底条款工程化的方式。

### 6.2 NIST AI RMF 1.0：MAP 先于 MEASURE/MANAGE，且要产出 go/no-go

**来源**：NIST AI 100-1, *Artificial Intelligence Risk Management Framework (AI RMF 1.0)*, January 2023, 48 页，<https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf>，本地证据 `_evidence/R4/nist-ai-rmf-100-1.pdf`（1,946,127 字节）/ `.txt`，抓取 2026-09-15。

#### 6.2.1 「Risk」的官方定义（§1.1，printed p.4）

> "In the context of the AI RMF, **risk refers to the composite measure of an event's probability of occurring and the magnitude or degree of the consequences of the corresponding event.** The impacts, or consequences, of AI systems can be positive, negative, or both and can result in opportunities or threats (Adapted from: ISO 31000:2018). **When considering the negative impact of a potential event, risk is a function of 1) the negative impact, or magnitude of harm**, that would arise if the circumstance or event occurs **and 2) the likelihood of occurrence** (Adapted from: OMB Circular A-130:2016)."

> "**Risk management refers to coordinated activities to direct and control an organization with regard to risk**" (Source: ISO 31000:2018).

> "**The AI RMF is designed to address new risks as they emerge. This flexibility is particularly important where impacts are not easily foreseeable and applications are evolving.**"

#### 6.2.2 ★ 「测不了 ≠ 低风险」：无规则时最重要的一句话（§1.2.1，printed p.5）

> "AI risks or failures that are not well-defined or adequately understood are difficult to measure quantitatively or qualitatively. **The inability to appropriately measure AI risks does not imply that an AI system necessarily poses either a high or low risk.**"

**要点**：这是"没有规则怎么办"的**授权性回答**。NIST 明确说：**测量能力的缺失不构成放行的理由。** 这一句应当直接进入审查 Agent 的输出话术。

#### 6.2.3 四个 Function 的关系与顺序（§5，printed p.20）

> "the Core is composed of four functions: **GOVERN, MAP, MEASURE, and MANAGE**. … **Actions do not constitute a checklist, nor are they necessarily an ordered set of steps.**"

> "**After instituting the outcomes in GOVERN, most users of the AI RMF would start with the MAP function and continue to MEASURE or MANAGE.** However users integrate the functions, the process should be iterative, with cross-referencing between functions as necessary."

**GOVERN 的定义（逐字要点）**：

> "The GOVERN function:
> • cultivates and implements **a culture of risk management** within organizations…;
> • outlines processes, documents, and organizational schemes that **anticipate, identify, and manage the risks** a system can pose…;
> • provides a structure by which AI risk management functions can **align with organizational principles, policies, and strategic priorities**;
> • **addresses full product lifecycle** and associated processes…"
>
> "GOVERN is a **cross-cutting function** that is infused throughout AI risk management and enables the other functions of the process."

#### 6.2.4 ★★ MAP 的定义与 go/no-go 判据（§5.2，printed p.24）

> "The **MAP function establishes the context to frame risks** related to an AI system."

> "**Without contextual knowledge, and awareness of risks within the identified contexts, risk management is difficult to perform. The MAP function is intended to enhance an organization's ability to identify risks and broader contributing factors.**"

> **"After completing the MAP function, Framework users should have sufficient contextual knowledge about AI system impacts to inform an initial go/no-go decision about whether to design, develop, or deploy an AI system. If a decision is made to proceed, organizations should utilize the MEASURE and MANAGE functions along with policies and procedures put into place in the GOVERN function to assist in AI risk management efforts."**

MAP 的目的（逐字列表）：

> "improving their capacity for **understanding contexts**;
> **checking their assumptions about context of use**;
> **enabling recognition of when systems are not functional within or out of their intended context**;
> identifying positive and beneficial uses of their existing AI systems;
> improving understanding of limitations in AI and ML processes;
> **identifying constraints in real-world applications that may lead to negative impacts**;
> **identifying known and foreseeable negative impacts related to intended use** of AI systems; and
> **anticipating risks of the use of AI systems beyond intended use.**"

**MAP 的子类条文（Table 2，printed pp.26–27；★ 标注为本报告认为对 Momcozy 最关键的条目）**：

| 条款 | 逐字原文 |
|---|---|
| **MAP 1.1** ★ | "Intended purposes, potentially beneficial uses, **context-specific laws, norms and expectations**, and prospective settings in which the AI system will be deployed are understood and documented. Considerations include: the specific set or types of users along with their expectations; potential positive and negative impacts of system uses to individuals, communities, organizations, society, and the planet; **assumptions and related limitations** about AI system purposes, uses, and risks across the development or product AI lifecycle; and related TEVV and system metrics." |
| **MAP 1.2** | "Interdisciplinary AI actors, competencies, skills, and capacities for establishing context reflect demographic diversity and broad domain and user experience expertise, and their participation is documented." |
| **MAP 1.3** | "The organization's mission and relevant goals for AI technology are understood and documented." |
| **MAP 1.4** | "The business value or context of business use has been clearly defined or – in the case of assessing existing AI systems – re-evaluated." |
| **MAP 1.5** ★ | "**Organizational risk tolerances are determined and documented.**" |
| **MAP 1.6** | "System requirements (e.g., 'the system shall respect the privacy of its users') are elicited from and understood by relevant AI actors." |
| **MAP 2.1** | "The specific tasks and methods used to implement the tasks that the AI system will support are defined (e.g., classifiers, generative models, recommenders)." |
| **MAP 2.2** ★ | "Information about **the AI system's knowledge limits** and how system output may be utilized and overseen by humans is documented." |
| **MAP 2.3** | "Scientific integrity and TEVV considerations are identified and documented, including those related to experimental design, data collection and selection (e.g., availability, representativeness, suitability), system trustworthiness, and construct validation." |
| **MAP 3.1** | "**Potential benefits** of intended AI system functionality and performance are examined and documented." |
| **MAP 3.2** | "**Potential costs, including non-monetary costs, which result from expected or realized AI errors** or system functionality and trustworthiness – as connected to organizational risk tolerance – are examined and documented." |
| **MAP 3.3** ★ | "**Targeted application scope is specified and documented based on the system's capability, established context, and AI system categorization.**" |
| **MAP 3.5** | "Processes for human oversight are defined, assessed, and documented in accordance with organizational policies from the GOVERN function." |
| **MAP 5.1** ★ | "**Likelihood and magnitude of each identified impact (both potentially beneficial and harmful)** based on expected use, past uses of AI systems in similar contexts, **public incident reports, feedback from those external to the team** that developed or deployed the AI system, or other data are identified and documented." |
| **MAP 5.2** | "Practices and personnel for supporting regular engagement with relevant AI actors and integrating feedback about positive, negative, and unanticipated impacts are in place and documented." |

**GOVERN 1.1**（Table 1）逐字：`Legal and regulatory requirements involving AI are understood, managed, and documented.`

#### 6.2.5 ★★ MEASURE 3.2：唯一直击"尚无度量手段"场景的规范条文

| 条款 | 逐字原文 |
|---|---|
| **MEASURE 1.1** ★ | "Approaches and metrics for measurement of AI risks enumerated during the MAP function are selected for implementation **starting with the most significant AI risks**. **The risks or trustworthiness characteristics that will not – or cannot – be measured are properly documented.**" |
| **MEASURE 1.2** ★ | "Appropriateness of AI metrics and effectiveness of existing controls are regularly assessed and updated, **including reports of errors and potential impacts on affected communities.**" |
| **MEASURE 1.3** | "**Internal experts who did not serve as front-line developers for the system and/or independent assessors are involved in regular assessments and updates.** Domain experts, users, AI actors external to the team that developed or deployed the AI system, and affected communities are consulted…" |
| **MEASURE 2.3** | "AI system performance or assurance criteria are measured qualitatively or quantitatively and **demonstrated for conditions similar to deployment setting(s)**." |
| **MEASURE 2.5** | "The AI system to be deployed is demonstrated to be **valid and reliable**. **Limitations of the generalizability beyond the conditions under which the technology was developed are documented.**" |
| **MEASURE 2.6** | "The AI system is evaluated regularly for safety risks – as identified in the MAP function. … **and it can fail safely**, particularly if made to operate beyond its knowledge limits." |
| **MEASURE 2.13** | "**Effectiveness of the employed TEVV metrics and processes in the MEASURE function are evaluated and documented.**" |
| **MEASURE 3.1** ★ | "Approaches, personnel, and documentation are in place to regularly identify and track **existing, unanticipated, and emergent AI risks** based on factors such as intended and actual performance in deployed contexts." |
| **MEASURE 3.2** ★★ | "**Risk tracking approaches are considered for settings where AI risks are difficult to assess using currently available measurement techniques or where metrics are not yet available.**" |
| **MEASURE 3.3** ★ | "**Feedback processes for end users and impacted communities to report problems and appeal system outcomes are established and integrated into AI system evaluation metrics.**" |
| **MEASURE 4.1** | "Measurement approaches for identifying AI risks are connected to deployment context(s) and informed through consultation with domain experts and other end users." |
| **MEASURE 4.3** | "**Measurable performance improvements or declines** based on consultations with relevant AI actors, including affected communities, and field data about context-relevant risks and trustworthiness characteristics are identified and documented." |

**MEASURE 3.2 是本分片找到的、唯一一条直接针对"度量手段尚不存在"的规范性要求。** 它给出的动作不是"等待规则"，而是 **"考虑风险追踪方案"（risk tracking approaches are considered）**；配合 MEASURE 1.1 的"不可测项必须被显式记录"，NIST 的立场可归纳为：

> **规则缺位时，组织义务从"测量"转为"追踪 + 记录 + 显式声明不可测"。**

#### 6.2.6 MANAGE（§5.4，printed p.31）

> "The MANAGE function entails **allocating risk resources to mapped and measured risks on a regular basis** and as defined by the GOVERN function. **Risk treatment comprises plans to respond to, recover from, and communicate about incidents or events.**"

> "**Processes for assessing emergent risks are in place, along with mechanisms for continual improvement.**"

### 6.3 三条独立法域的同一结构：「部署前评估」

三个法域，三种表述，**同一个结构**：

| 法域 | 条款 | 逐字原文 |
|---|---|---|
| **EU AI Act** | **Art. 9(8)** | "The testing of high-risk AI systems shall be performed, as appropriate, at any time throughout the development process, and, **in any event, prior to their being placed on the market or put into service**." |
| **DSA** | **Art. 34(1)** | "They shall carry out the risk assessments by the date of application referred to in Article 33(6), second subparagraph, and **at least once every year thereafter, and in any event prior to deploying functionalities that are likely to have a critical impact on the risks identified pursuant to this Article.**" |
| **UK OSA 2023** | **s.9(4)** | "**Before making any significant change to any aspect of a service's design or operation, a duty to carry out a further suitable and sufficient illegal content risk assessment relating to the impacts of that proposed change.**" |

> ⚠️ **条款号更正**：任务书写的 "34(3) 的 'at least once a year'" 有误。**"at least once every year" 在 DSA Art. 34(1)**；**Art. 34(3) 实为"风险评估支持性文件留存至少三年"**：
> "Providers … shall **preserve the supporting documents of the risk assessments for at least three years** after the performance of risk assessments, and shall, upon request, communicate them to the Commission and to the Digital Services Coordinator of establishment."

#### 6.3.1 EU AI Act Art. 9 全文要点（逐字）

> **1.** "A risk management system shall be established, implemented, documented and maintained in relation to high-risk AI systems."
> **2.** "The risk management system shall be understood as a **continuous iterative process planned and run throughout the entire lifecycle** of a high-risk AI system, requiring regular systematic review and updating. It shall comprise the following steps:
> (a) **the identification and analysis of the known and the reasonably foreseeable risks** that the high-risk AI system can pose to health, safety or fundamental rights when the high-risk AI system is used in accordance with its intended purpose;
> (b) the estimation and evaluation of the risks that may emerge when the high-risk AI system is used in accordance with its intended purpose, and under conditions of **reasonably foreseeable misuse**;
> (c) the evaluation of other risks possibly arising, based on the analysis of data gathered from the post-market monitoring system referred to in Article 72;
> (d) **the adoption of appropriate and targeted risk management measures** designed to address the risks identified pursuant to point (a)."
> **3.** "**The risks referred to in this Article shall concern only those which may be reasonably mitigated or eliminated through the development or design** of the high-risk AI system, or the provision of adequate technical information."
> **5.** "…the relevant **residual risk** associated with each hazard, as well as the overall residual risk … is judged to be acceptable. In identifying the most appropriate risk management measures, the following shall be ensured:
> (a) **elimination or reduction of risks** … in as far as technically feasible through adequate design and development;
> (b) where appropriate, **implementation of adequate mitigation and control measures** addressing risks that cannot be eliminated;
> (c) **provision of information** required pursuant to Article 13 and, where appropriate, training to deployers."
> **9.** "…providers shall give consideration to whether in view of its intended purpose the high-risk AI system is likely to have an **adverse impact on persons under the age of 18** and, as appropriate, other vulnerable groups."

> ⚠️ **条款号更正（重要）**：任务书写 `9(4) "adoption of appropriate and targeted risk management measures"` 与 `9(1) "throughout the entire lifecycle"`，**均不正确**。经核：
> - `"adoption of appropriate and targeted risk management measures"` 在 **Art. 9(2)(d)**；
> - `"throughout the entire lifecycle"` 在 **Art. 9(2)**；
> - **Art. 9(4)** 实为"本节各项要求合并适用时的相互作用与平衡"。

**★ Art. 9(3) 是一条容易被忽略的限缩条款**：风险管理义务**只覆盖**可通过设计/开发或技术信息缓解或消除的风险。**AI Act 自己承认存在义务射程之外的风险地带**——这与 DSA Art. 34 的 `diligently identify … any systemic risks` 形成对照。

#### 6.3.2 DSA Art. 34/35/37 要点（逐字）

**Art. 34(1)** 的四类系统性风险（逐字）：
> "(a) **the dissemination of illegal content** through their services;
> (b) any actual or foreseeable negative effects for the exercise of **fundamental rights**…;
> (c) any actual or foreseeable negative effects on **civic discourse and electoral processes, and public security**;
> (d) any actual or foreseeable negative effects in relation to **gender-based violence, the protection of public health and minors** and serious negative consequences to the person's physical and mental well-being."

**Art. 34(2)** 的考量因素（逐字要点）：
> "(a) the design of their **recommender systems**…; (b) their **content moderation systems**; (c) **the applicable terms and conditions and their enforcement**; (d) systems for selecting and presenting advertisements; (e) data related practices… The assessments shall also analyse whether and how the risks … are influenced by **intentional manipulation** … The assessment shall take into account specific **regional or linguistic** aspects, including when specific to a Member State."

**Art. 35(1)**（逐字要点）：`put in place **reasonable, proportionate and effective mitigation measures, tailored to the specific systemic risks identified pursuant to Article 34**`，包括 `(b) adapting their terms and conditions and their enforcement; (c) **adapting content moderation processes**, including the speed and quality of processing notices…; (d) testing and adapting their algorithmic systems`，以及 `(k)` 对深度合成内容的 `**prominent markings**` 要求。

**Art. 35(3)**（兜底设计）：
> "The Commission, in cooperation with the Digital Services Coordinators, **may issue guidelines on the application of paragraph 1 in relation to specific risks**, in particular to present best practices and recommend possible measures…"

**Art. 37**（独立审计）：
> **1.** "Providers … shall be subject, **at their own expense and at least once a year**, to independent audits…"
> **2.** "…including by **giving them access to all relevant data and premises** and by answering oral or written questions. **They shall refrain from hampering, unduly influencing or undermining the performance of the audit.**"
> **3.** Auditors shall "(a) be independent from, and do not have any conflicts of interest with, the provider…; (iii) **are not performing the audit in return for fees which are contingent on the result of the audit**; (b) have proven expertise in the area of **risk management**…"

#### 6.3.3 UK OSA s.9 + Ofcom 四步法（逐字）

**s.9(5)** 要求评估的事项（逐字要点，★ 为对 Momcozy 最相关）：
> "(a) the user base;
> (b) the level of risk of individuals who are users of the service encountering … (i) **each kind of priority illegal content (with each kind separately assessed)**…
> (c) the level of risk of the service being used for the commission or facilitation of a priority offence;
> (d) the level of risk of harm to individuals presented by illegal content of different kinds…;
> (e) **the level of risk of functionalities of the service facilitating the presence or dissemination of illegal content …, identifying and assessing those functionalities that present higher levels of risk**;
> (f) **the different ways in which the service is used**, and the impact of such use on the level of risk of harm…;
> (g) **the nature, and severity, of the harm** that might be suffered by individuals…;
> (h) **how the design and operation of the service (including the business model, governance, use of proactive technology, measures to promote users' media literacy and safe use of the service, and other systems and processes) may reduce or increase the risks identified.**"

**s.10(2)** —— "无评估即无合规缓解措施"的闭环（逐字）：
> "A duty, in relation to a service, to take or use **proportionate measures relating to the design or operation** of the service to— … (b) **effectively mitigate and manage the risk** … **as identified in the most recent illegal content risk assessment of the service**, and (c) effectively mitigate and manage the risks of harm to individuals, **as identified in the most recent illegal content risk assessment of the service**"

**★ Ofcom 的四步风险评测方法论（逐字，Ofcom, *Children's Risk Assessment Guidance*, 85 页 PDF）**：

> "This guidance recommends **the same four-step methodology as in Ofcom's Illegal Content Risk Assessment Guidance for Service Providers**…"

| 步骤 | Ofcom 逐字要点 | Essential records（逐字） |
|---|---|---|
| **Step 1: Understand content harmful to children that needs to be assessed** | "Identify the content harmful to children that needs to be **separately assessed**, including **each kind** of primary priority content, **each kind** of priority content, and **any kind(s) of non-designated content that may be relevant to your service**." / "Consult Ofcom's Children's Risk Profiles and identify the key risk factors relevant to your service" | "**A record of the kind(s) of non-designated content that will be assessed**, and how you have considered the risk of children encountering non-designated content" |
| **Step 2: Assess the risk of harm to children** | "**Separately assess the likelihood and impact** … using all relevant evidence." / "Consider **the different ways in which the service is used, including ways which are unintended**. Identify whether there are any **additional characteristics or functionalities** of the service's design or operation, **not in the Children's Risk Profiles**, which could increase the risk" / "Consider **the effectiveness of any existing control measures**" / "**Consult the Risk Level Table** to assign a risk level" | "**a list of the evidence and summary of the reasoning** that has informed the assessment of likelihood and impact of each kind" |
| **Step 3: Decide measures, implement and record** | "check which measures are recommended …, decide whether to implement applicable measures …, **or use alternative measures**. Identify any **additional measures** that may be appropriate" | "Any applicable measures … that are **not planned to be implemented, and the alternative measures** that have been or are planned to be implemented instead, **with information that demonstrates how these alternative measures meet the relevant duties**" |
| **Step 4: Report, review and update** | "Report on the risk assessment and measures through **appropriate governance and accountability channels**." / "**Monitor developing risks** and the level of risk exposure after appropriate measures are implemented (also known as **residual risk**)." / "Review and/or update the risk assessment when appropriate, including **before making any significant change**" | "**A written record of the annual review cycle** …, and **the named person responsible** who has been appointed for this process." |

**★★ Ofcom Step 2 的这句话，是"规则库没覆盖到"时的官方处置路径**：

> "Identify whether there are any **additional characteristics or functionalities** of the service's design or operation, **not in the Children's Risk Profiles**, which could increase the risk to children."

**即：不在清单里的风险，不是"不在射程内"，而是"必须被显式识别、单独评估、并记录理由"。**

**Ofcom Step 3 允许偏离推荐措施，但必须留证**：

> "Any applicable measures … that are **not planned to be implemented, and the alternative measures** that have been or are planned to be implemented instead, **with information that demonstrates how these alternative measures meet the relevant duties**"

**即：偏离规则是允许的，但"偏离"本身必须是一个有记录、有论证的动作。** 这正是 Momcozy 现在缺的：他们的 Agent 判定与人工判断之间的任何偏移，**都没有留下"为什么偏离"**。

### 6.4 ISO 标准：⚠️ 仅取得官方预览页，未取得条文正文

> **来源层级声明（必须保留）**：ISO 31000:2018、ISO/IEC 42001:2023、ISO/IEC 23894:2023 **正文均为付费标准**，且经 Cloudflare 保护。本分片**仅取得 ISO 官方标准页（metadata + 官方概述 + FAQ）**，**未获得 Clause 6.4.2 / 6.1.2 / 6.1.3 / 8.2 / 8.3 的条文原文**。以下所有引文均来自 ISO 官方页面，**不得标注为"标准正文"**。

**ISO 31000:2018 — Risk management — Guidelines**（<https://www.iso.org/standard/65694.html>，抓取 2026-09-15）：
> 官方 metadata："Edition 2, 2018. Published. This publication was last reviewed and confirmed in 2023. Therefore this version remains current. **Number of pages: 16. Technical Committee: ISO/TC 262.**"
> 官方概述："ISO 31000 is an international standard that provides **principles and guidelines for risk management**. It outlines **a comprehensive approach to identifying, analyzing, evaluating, treating, monitoring and communicating risks** across an organization."
> 官方 FAQ（★ 对本项目重要的限定）："**Does ISO 31000 lead to risk management certification?** No. ISO 31000 provides good practice guidelines but is **not a certifiable risk management standard**." / "ISO 31000 **cannot be used for certification purposes**, but does provide guidance for internal or external audit programmes."

**ISO/IEC 42001:2023 — AI management system**（<https://www.iso.org/standard/42001>，抓取 2026-09-15）：
> "Edition 1, 2023-12. **Number of pages: 51.** … Stage: International Standard published [60.60]."
> "**What is an artificial intelligence management system?** … a set of interrelated or interacting elements of an organization intended to establish policies and objectives, as well as processes to achieve those objectives, in relation to the responsible development, provision or use of AI systems."
> "**What are the objectives of ISO/IEC 42001?** … it provides an integrated approach to managing AI projects, **from risk assessment to effective treatment of these risks**."
> "Implementing this standard means putting in place policies and procedures for the sound governance of an organization in relation to AI, using the **Plan-Do-Check-Act** methodology."

**ISO/IEC 23894:2023 — AI risk management guidance**（<https://www.iso.org/standard/77304.html>）：
> "Information technology — Artificial intelligence — **Guidance on risk management**. Edition 1, 2023-02. **Number of pages: 26.**"

**可确证的只有结构关系**：31000 = 通用风险管理指南（16 页，**不可认证**）；42001 = AI 管理体系标准（51 页，可认证，PDCA 循环）；23894 = AI 风险管理专项指引（26 页）。**具体条款义务内容未能核实。**

> ⚠️ **不可代写**：任务书要求的 "ISO 31000:2018 Clause 6.4.2 Risk identification / 6.4.3 Risk analysis / 6.4.4 Risk evaluation" 与 "ISO/IEC 42001 Clause 6.1.2 / 6.1.3 / 8.2 / 8.3" 条文内容，**本报告不予提供**。任务书中"风险识别先于风险控制"这一命题在 ISO 体系中的确切条款依据，**未能核实**。

### 6.5 沙盒与试点：规则尚未定型时的官方试验场

**来源**：EU AI Act Art. 57–60（Regulation (EU) 2024/1689，经欧盟出版局 Cellar `celex/32024R1689` 获取），抓取 2026-09-15。

**Art. 57(1)**（逐字）：
> "Member States shall ensure that their competent authorities establish **at least one AI regulatory sandbox at national level, which shall be operational by 2 August 2026.** That sandbox may also be established jointly with the competent authorities of other Member States."

**Art. 57(5)** —— 沙盒的官方定义（逐字）：
> "AI regulatory sandboxes … shall provide for **a controlled environment that fosters innovation and facilitates the development, training, testing and validation of innovative AI systems for a limited time before their being placed on the market or put into service** pursuant to a specific sandbox plan agreed between the providers or prospective providers and the competent authority."

**Art. 57(6)** —— 监管者主动帮识别风险（逐字）：
> "Competent authorities shall provide, as appropriate, **guidance, supervision and support within the AI regulatory sandbox with a view to identifying risks**, in particular to fundamental rights, health and safety, testing, mitigation measures, and their effectiveness…"

**Art. 57(9)** —— 五大目标（逐字要点）：
> "(d) **contributing to evidence-based regulatory learning**;"

**★ Art. 57(12)** —— 免罚保护（对本委托方商业价值最高的一条，逐字）：
> "Providers and prospective providers participating in the AI regulatory sandbox shall remain liable under applicable Union and national liability law for any damage inflicted on third parties as a result of the experimentation taking place in the sandbox. **However, provided that the prospective providers observe the specific plan and the terms and conditions for their participation and follow in good faith the guidance given by the national competent authority, no administrative fines shall be imposed by the authorities for infringements of this Regulation.**"

**Art. 60(2)/(4)(b)** —— 真实世界测试与默示批准（逐字）：
> "Providers or prospective providers may conduct testing of high-risk AI systems referred to in Annex III in real world conditions **at any time before the placing on the market or the putting into service**…"
> "**where the market surveillance authority has not provided an answer within 30 days, the testing in real world conditions and the real-world testing plan shall be understood to have been approved**"

**要点**：**"规则尚未定型"在欧盟法上的正式出口是沙盒，不是豁免。** Art. 57(1) 的 2026-08-02 生效期限意味着**该机制现已（2026-09）进入实施期**。

> **⚠️ 适用范围提示**：沙盒面向"AI 系统的提供者或潜在提供者"，且这是**欧盟境内**的机制。Momcozy 的自用内容审查 Agent 是否落入其范围，**本报告不作判断**（需要法律意见）。此处仅陈述制度存在与条款原文。

### 6.6 没有证据时的默认动作：放行还是拦截？

**来源**：Commission of the European Communities, **COM(2000) 1 final**, *Communication from the Commission on the precautionary principle*（经 Cellar `celex/52000DC0001` 获取，28 页 PDF），抓取 2026-09-15。

#### 6.6.1 ★★ 核心判据：证据不足不能作为不作为的理由（§6.2 逐字）

> "Once the scientific evaluation has been performed as best as possible, it may provide a basis for **triggering a decision to invoke the precautionary principle**. The conclusions of this evaluation should show that the desired level of protection for the environment or a population group could be jeopardised. The conclusions should also include **an assessment of the scientific uncertainties and a description of the hypotheses used to compensate for the lack of the scientific or statistical data**. **An assessment of the potential consequences of inaction should be considered and may be used as a trigger by the decision-makers.** The decision to wait or not to wait for new scientific data before considering possible measures should be taken by the decision-makers **with a maximum of transparency**. **The absence of scientific proof of the existence of a cause-effect relationship, a quantifiable dose/response relationship or a quantitative evaluation of the probability of the emergence of adverse effects following exposure should not be used to justify inaction.** Even if scientific advice is supported only by a minority fraction of the scientific community, due account should be taken of their views, provided the credibility and reputation of this fraction are recognised."

**这是欧盟法上对"没有规则/没有证据所以先放着"这一立场的正面否定。** 同时给出了两个可操作替代动作：
1. **评估不作为的后果**（`An assessment of the potential consequences of inaction should be considered`）；
2. **记录不确定性与所用假设**（`a description of the hypotheses used to compensate for the lack of the scientific or statistical data`）。

#### 6.6.2 启用预防原则的前置条件（§5.1 逐字）

> "**The precautionary principle is relevant only in the event of a potential risk, even if this risk cannot be fully demonstrated or quantified or its effects determined because of the insufficiency or inclusive nature of the scientific data.** It should however be noted that **the precautionary principle can under no circumstances be used to justify the adoption of arbitrary decisions.**"

> **5.1.1 Identification of potentially negative effects** — "Before the precautionary principle is invoked, the scientific data relevant to the risks must first be evaluated. However, one factor logically and chronologically precedes the decision to act, namely **identification of the potentially negative effects** of a phenomenon."

> **5.1.2 Scientific evaluation** — "A scientific evaluation of the potential adverse effects **should be undertaken based on the available data** when considering whether measures are necessary… **it is not possible in all cases to complete a comprehensive assessment of risk, but all effort should be made to evaluate the available scientific information.** If necessary, it should also contain the **identification of topics for further scientific research**."

> **5.1.3 Scientific uncertainty** — "Scientific uncertainty results usually from five characteristics of the scientific method: **the variable chosen, the measurements made, the samples drawn, the models used and the causal relationship employed.**"

#### 6.6.3 措施的六条约束（§6 摘要，逐字）

> "**6. Where action is deemed necessary, measures based on the precautionary principle should be, inter alia:**
> • **proportional to the chosen level of protection,**
> • **non-discriminatory in their application,**
> • **consistent with similar measures already taken,**
> • **based on an examination of the potential benefits and costs of action or lack of action** (including, where appropriate and feasible, an economic cost/benefit analysis),
> • **subject to review, in the light of new scientific data, and**
> • **capable of assigning responsibility for producing the scientific evidence necessary for a more comprehensive risk assessment.**"

**比例原则的展开（§6.3.1 逐字，对 Momcozy 的分级设计直接适用）**：

> "**Measures based on the precautionary principle must not be disproportionate to the desired level of protection and must not aim at zero risk, something which rarely exists.** … Risk reduction measures should include **less restrictive alternatives** … such as appropriate treatment, **reduction of exposure**, tightening of controls, **adoption of provisional limits**, recommendations for populations at risk…"

**一致原则（§6.3.3 逐字）**：

> "**If the absence of certain scientific data makes it impossible to characterise the risk, taking into account the uncertainties inherent to the evaluation, the measures taken under the precautionary principle should be comparable in nature and scope with measures already taken in equivalent areas in which all the scientific data are available.**"

**★★ 临时性与复审（§6.3.5 逐字，这是"冷启动规则"的法定属性）**：

> "**The measures should be maintained as long as the scientific data are inadequate, imprecise or inconclusive and as long as the risk is considered too high to be imposed on society. The measures may have to be modified or abolished by a particular deadline, in the light of new scientific findings.** … the measures should be subjected to **regular scientific monitoring, so that they can be reevaluated** in the light of new scientific information."

**SPS Article 5(7) 三条件（官方逐字转述）**：
> "• **The measures must be of a provisional nature pending the availability of more reliable scientific data.** However this provisional nature is linked to the development of scientific knowledge rather than to a time factor.
> • **Research must be carried out to elicit the additional scientific data required for a more objective assessment of the risk.**
> • **The measures must be periodically reviewed to take account of new scientific data.**"

> ⚠️ **引用格式提醒**：**"措施必须是非歧视的、相称的、临时的、可复审的"这一组要求在 COM(2000)1 中并非集中于单段**，而是分散在 §6（六条约束）、§6.3.1（相称）、§6.3.2（非歧视）、§6.3.5（复审）与 SPS Art 5(7)（临时性）。引用时**须分别标注小节号，不要合并成一段伪引文**。

> **Case T-13/99（Pfizer Animal Health v Council, 2002）**：curia.europa.eu 为 JS 渲染且需接受 cookie，本轮未取得判决正文；Cellar `celex/62099A0013` 与 `62099TJ0013` 均返回 404（CELEX 编号不适用于该法院判决）。**未核实。**

### 6.7 冷启动的官方答案汇总（一张表）

| 问题 | 官方答案（逐字锚点） | 来源 |
|---|---|---|
| 没有规则时，默认动作是放行还是拦截？ | **都不是**——先做 MAP，然后做一次 **go/no-go 决策**：`After completing the MAP function, Framework users should have sufficient contextual knowledge about AI system impacts to inform an initial go/no-go decision` | NIST AI RMF 1.0 §5.2 |
| 测不出来怎么办？ | **不能因为测不出来就当作低风险**：`The inability to appropriately measure AI risks does not imply that an AI system necessarily poses either a high or low risk.` | NIST AI RMF 1.0 §1.2.1 |
| 度量手段还不存在怎么办？ | **转为"风险追踪 + 显式记录不可测"**：MEASURE 3.2 + MEASURE 1.1 | NIST AI RMF 1.0 Table 3 |
| 规则清单没覆盖到怎么办？ | **显式识别并单独评估，记录理由**：`Identify whether there are any additional characteristics or functionalities … not in the Children's Risk Profiles, which could increase the risk` | Ofcom Step 2 |
| 想偏离推荐措施怎么办？ | **允许，但必须留证论证**：`the alternative measures that have been or are planned to be implemented instead, with information that demonstrates how these alternative measures meet the relevant duties` | Ofcom Step 3 |
| 变更前要不要重新评估？ | **要**：`Before making any significant change to any aspect of a service's design or operation`（UK OSA s.9(4)）/ `prior to deploying functionalities that are likely to have a critical impact`（DSA Art 34(1)）/ `in any event, prior to their being placed on the market or put into service`（AI Act Art 9(8)） | 三法域 |
| 没有证据能不能先放着？ | **不能**：`The absence of scientific proof … should not be used to justify inaction.` | COM(2000)1 §6.2 |
| 那临时措施有什么要求？ | **相称 / 非歧视 / 一致 / 临时 / 可复审 / 能指定举证责任人** | COM(2000)1 §6、§6.3.5、SPS Art 5(7) |
| 规则还在形成期，有没有合法的试错空间？ | **有，是沙盒**：`a controlled environment that fosters innovation and facilitates the development, training, testing and validation of innovative AI systems for a limited time before their being placed on the market` | EU AI Act Art 57(5) |
| 平台层面规则没写，能过吗？ | **不能**。四家平台全部有兜底条款，且都是条件式的 | §6.1 |

---

## 7. 对 Momcozy 的直接含义

> 本节所有建议都建立在身份明确的前提上：**以下标 `[推断]` 的是我的判断，标 `[原文]` 的是前文逐字证据的直接推论。**

### 7.1 规则库的自迭代回路：五个环

委托方问"回路应该有几个环"。综合 §1（生命周期）、§3（误差分析）、§4（回归门）的证据，**最小可用回路是五个环**，各有不同的节奏、输入、输出与负责人。

```
                    ┌─────────────────────────────────────────────┐
                    │  环 5：外部扫描（Intelligence Desk 环）      │
                    │  节奏：双周 | 输入：平台政策/法规/竞品/客诉  │
                    └───────────────┬─────────────────────────────┘
                                    │ 新风险信号 → 建规则草案
                                    ▼
   ┌────────────────────────────────────────────────────────────┐
   │  环 1：规则生产环（Policy Line 环）                          │
   │  节奏：月度 | 输入：草案 + 抽样内容 + 划线选项               │
   │  输出：enforcement guideline（含正例/反例/判定树/豁免）      │
   └───────────────┬────────────────────────────────────────────┘
                   │ 新规则/改规则
                   ▼
   ┌────────────────────────────────────────────────────────────┐
   │  环 2：回归门环（Golden Set 环）                             │
   │  节奏：每次规则变更前（强制）                                │
   │  输入：golden set（每规则 ≥1 正例 + ≥1 反例 + 对抗样本）     │
   │  输出：PASS/FAIL；FAIL 不许发布                              │
   └───────────────┬────────────────────────────────────────────┘
                   │ 发布
                   ▼
   ┌────────────────────────────────────────────────────────────┐
   │  环 3：运行与取证环（Run & Capture 环）                      │
   │  节奏：每日 | 输入：在跑广告/内容                           │
   │  输出：四格记录（TP/FP/FN/TN）+ 未覆盖记录                   │
   └───────────────┬────────────────────────────────────────────┘
                   │ 抽样审计
                   ▼
   ┌────────────────────────────────────────────────────────────┐
   │  环 4：误差分析与回写环（Error Analysis 环）                 │
   │  节奏：每周（QA 会）+ 每月（度量报告）+ 每季（规则盘点）      │
   │  输入：四格记录 + 抽样人审                                   │
   │  输出：错误分桶表 + 处置码 + 规则修订草案                    │
   └───────────────┬────────────────────────────────────────────┘
                   │ 修订草案 → 回到环 1
                   └──────────────────────────────────────────────
```

#### 环 1：规则生产环（Policy Line 环）

| 项 | 内容 | 证据依据 |
|---|---|---|
| **输入** | ① 新风险信号（来自环 5）；② **随机抽样的真实内容**（不是"钱最多的"）；③ 现有规则的命中数据 | MAP 1.1 `context-specific laws, norms and expectations`；YouTube `watch dozens or even hundreds of videos` |
| **动作** | ① 估该类问题在内容中的发生率与增长潜力；② 看几十到几百条样本；③ **产出 ≥2 个候选"划线方案"**；④ 每个方案必须附"会被判违规的样例"与"会被判合规的样例"；⑤ 内部评审 | YouTube `the team shares various options for policy lines, making sure to detail examples of videos that would be removed or approved for each` |
| **输出** | 一条 enforcement guideline（**不是政策文句**），含：定义 / 判定标准 / 正例 / 反例 / 判定树 / 豁免条件 / 已知缺陷 / 未知边界的处置方式 | §2.2 的六段式结构 |
| **负责人** | `[推断]` 应由"内容合规负责人 + 品线市场负责人"共同签署；**单方不能定稿** | YouTube `If at any point there is consistent disagreement between teams about where we've drawn the line, the policy is sent back to the drawing board.` |
| **节奏** | 月度例会；**但紧急风险（平台政策变更/监管问询）走临时会** | `[推断]` |

#### 环 2：回归门环（Golden Set 环）

| 项 | 内容 | 证据依据 |
|---|---|---|
| **输入** | golden set 的一个版本 + 待发布的规则版本 | OPA `By writing tests for your policies you can speed up the development process of new rules` |
| **动作** | 跑 `golden_set × 新规则`，逐条比对期望判定 | OPA `opa test . -v` |
| **输出** | PASS/FAIL 报告；**FAIL 则不允许发布** | OPA `FAILURES … data.authz_test.test_post_allowed: FAIL` |
| **负责人** | `[推断]` 由规则维护人跑，合规负责人签收 | — |
| **节奏** | **每次规则变更前强制执行**（无例外） | EU AI Act Art 9(8) `in any event, prior to their being placed on the market or put into service` |
| **准入要求** | 新规则进入 golden set 时，**必须同时加入 ≥1 正例、≥1 反例、≥1 对抗样本** | GHC `passing a test of about thirty messages that had been previously annotated and agreed upon by the authors`；NIST AI 600-1 `MP-2.3-005 … regular adversarial testing` |

#### 环 3：运行与取证环（Run & Capture 环）

| 项 | 内容 | 证据依据 |
|---|---|---|
| **输入** | 每日在跑/待发布的广告文案、落地页、社媒内容 | — |
| **动作** | Agent 逐条判定，**并且把"判定路径"一并落库**（见 §7.2 字段设计） | Meta 拒绝 rec.13 的教训：`we do not have systems in place to make this comparison. Our measurement accuracy systems are not designed to review the small number of decisions made through the cross check process.` |
| **输出** | 每内容一行记录，含四态结果 + 规则版本号 + 判定路径 + 模型/规则版本 | NIST AI RMF MEASURE 3.1 `regularly identify and track existing, unanticipated, and emergent AI risks` |
| **负责人** | `[推断]` Agent 自动执行；GTM 负责"未审不得上线"的把关 | 任务书 §二.E 已有治理约束 |
| **节奏** | 每日 | — |

#### 环 4：误差分析与回写环（Error Analysis 环）

| 项 | 内容 | 证据依据 |
|---|---|---|
| **输入** | ① 四格记录；② **每周从命中样本与人审样本中各抽一批做人工复判** | Meta `We estimate precision by sampling actioned content` |
| **动作** | ① 错误分桶（按 PAIR 七类，§3.2.1）；② 逐规则算 precision/recall；③ 难例归档；④ 对每条错误给**处置码** | Meta `we measure precision for both harms independently`；GHC `make notes about difficult cases and difficulties you had in coding` |
| **输出** | ① 错误分桶表；② 每规则的 precision/recall/FP/FN；③ 处置码台账（Modified/Clarified/Escalated/No-action） | Meta 四处置码：`Implementing fully / Implementing in part / Assessing feasibility / No further action` |
| **负责人** | `[推断]` 内容合规负责人主持，需要有"未曾参与初判"的人参与 | Santa Clara `Human review by a person or panel of persons who were not involved in the initial decision`；NIST MEASURE 1.3 `Internal experts who did not serve as front-line developers` |
| **节奏** | **每周 30 分钟 QA 会**（对棘手判定）+ **每月度量报告** + **每季度规则盘点** | YouTube `Every week, our Trust & Safety leadership meet with quality assurance leads` |

#### 环 5：外部扫描环（Intelligence Desk 环）

| 项 | 内容 | 证据依据 |
|---|---|---|
| **输入** | ① 平台政策更新（Google Ads / Meta / TikTok / Amazon）；② 目标国法规更新；③ 竞品被处罚案例；④ 客诉/差评中出现的合规问题 | YouTube `Intelligence Desk … identify potentially violative trends … regularly monitoring ongoing threats` |
| **动作** | 定期扫描 + 事件驱动扫描；产出"风险信号卡" | 同上 |
| **输出** | 风险信号 → 触发环 1 建规则草案 | `These insights then feed into thinking through how current or future policies would manage these new threats` |
| **负责人** | `[推断]` **目前空缺**。建议由 GTM/合规岗兼任，工作量为每周 2 小时 | — |
| **节奏** | 双周 | — |

**五环的关键设计约束（三条）**：

1. **环 1 与环 4 的负责人不能是同一个人。** 依据：NIST MEASURE 1.3 `Internal experts who did not serve as front-line developers for the system and/or independent assessors are involved in regular assessments`；Santa Clara Appeal 原则 `who were not involved in the initial decision`。**定规则的人不能给自己判卷。**
2. **环 2 是硬门禁，不可以通过"特批"绕过。** 依据：OPA 的测试失败即构建失败；EU AI Act Art 9(8) 的部署前测试义务。
3. **环 5 必须有归属。** 目前 Momcozy 的 21 条规则 `依据来源` 只有两个内部来源，**没有任何一条来自外部平台政策或法规更新**——这说明环 5 事实上不存在。

### 7.2 「错题本」的正确形态：291 条记录缺哪些字段

**先给结论**：**他们现在缺的不是"错题本"，而是四样东西**：
① 一个**存在性**（是否有错题本）；
② 一个**第三态判定结果**（"未覆盖"）；
③ 一个 **FP/FN 的采集路径**；
④ 一个**处置码字段**（错误发现了之后怎么办）。

#### 7.2.1 291 条记录现有字段 vs 错题本所需字段

**现有字段**（`PRD/内容治理需求文档.md:64`）：
`广告名称 | 平台 | 广告系列Campaign | 品线 | 投放地区 | 文案语种 | Primary Text | Headline | 落地页URL | 风险等级 | 处理状态 | 数据日期 | 命中原因 | 命中片段 | 投放状态 | 抓取状态 | 命中规则 | 修改建议 | 检查人 | 近7天费用USD | 近7天展示 | 近7天点击 | 广告账号 | 外部广告ID | 广告组 | 广告类型 | 父记录`

**缺口清单（按优先级排序）**：

| # | 缺失字段 | 为什么必须补 | 取值/类型建议 |
|---|---|---|---|
| **1** | **`判定结果`（四态）** | 现在是 `风险等级`（高危/审慎/待复核/合规），**"合规"同时承担了"确认合规"与"规则未覆盖"两种含义**。这是语义重载，必须先拆开 | `命中且正确(TP)` / `误拦(FP)` / `漏放(FN)` / `正确放行(TN)` / **`未覆盖(UNCOVERED)`** |
| **2** | **`人工复判结论`** | 这一列是 FP 与 FN 的**唯一采集入口**。**现在 `检查人` 列为空**，意味着从未有人复核过 | 枚举：`维持原判` / `推翻-应判违规` / `推翻-应判合规` / `无法判定` |
| **3** | **`复判人`** | 必须能证明"复判者未参与初判"（Santa Clara 要求） | 人名或工号 |
| **4** | **`复判时间`** | 用于计算"人工处理时延"与"申诉窗口" | datetime |
| **5** | **`处置码`** | 错误发现了之后怎么办。**没有这个字段，错题本无法驱动规则变更** | 参照 Meta 四值：`直接改规则` / `部分改规则` / `评估中` / `不改（附理由）` |
| **6** | **`未覆盖原因`** | 当 `判定结果 = 未覆盖` 时必填。这是规则生产的原料 | 枚举：`新表达方式` / `新语种` / `新品类` / `新平台` / `规则边界不清` / `其他` |
| **7** | **`规则版本号`** | 没有版本号，无法回溯"这条是哪个版本的规则判的"，回归测试也无从比对 | 语义版本，如 `R2026.09.1` |
| **8** | **`判定路径`**（自动 / 人工 / 自动+人工） | **Meta 拒绝 rec.13 的教训**：`Our measurement accuracy systems are not designed to review the small number of decisions made through the cross check process.` **判定路径必须从第一天就落库** | `auto` / `human` / `auto_then_human` / `human_then_auto` |
| **9** | **`命中规则的置信度/依据类型`** | 区分"正则命中"（高置信）与"语境判断"（低置信）。**这是 uncertainty sampling 的必要输入**（§3.3） | `exact_match` / `regex` / `context_judgement` |
| **10** | **`是否对抗样本`** 与 **`对抗手法`** | 用于建立对抗集（§4.1 原则 2、NIST `MP-2.3-005`） | `否` / `拼音` / `拆字` / `emoji` / `变体拼写` / `同义替换` |
| **11** | **`抽样批次`** | 用于区分"随机抽样"与"风险优先抽样"。**没有这个字段，任何比率都不可计算** | 批次号 + 抽样方法枚举 |
| **12** | **`内容语种（人工核对）`** | 现有 `文案语种` 是投放设置的语种，不是内容实际语种（PRD 里已有明显错配：`:86` 加拿大样本语种填"意语"） | ISO 639-1 |

**按严重程度排序**：**#1、#2、#3、#5、#7 是"不做就无法开始"的五个字段**；#8、#9、#11 是"做度量必需"的三个字段；#4、#6、#10、#12 是"提升质量"的四个字段。

#### 7.2.2 FP 与 FN 的采集设计（具体到动作）

**这是委托方特别点出的问题。四个方向各需要一个采集路径：**

| 方向 | 含义 | 采集路径（具体动作） | 频率 | 预计样本量 |
|---|---|---|---|---|
| **FP（误拦）** | Agent 判违规，实际合规 | **对每个"高危/审慎"判定，在上线前由人工复核一次**；复核结论写入 `人工复判结论`。**如果复核者认为应放行，必须填写放行理由** | 100% 高风险；抽样 20% 中风险 | `[推断]` 按 PRD 的高危占比，初期约每周 10–30 条 |
| **FN（漏放）** | Agent 判合规，实际违规 | **① 每周从"合规·绿"样本中随机抽 30 条做人工复判；② 建立"外部反馈"入口**：把客服/平台拒登通知/AI 平台的政策警告回填成 FN 候选；③ 从竞品被处罚案例构造 FN 探针 | 每周 1 次 | 30 条/周 = 约 130 条/月 |
| **未覆盖** | 所有规则都不命中 | **把"未命中"从"合规"里拆出来**，命中兜底规则（§6.1）后进入人工队列 | 每日 | 取决于盲区大小 |
| **TN（正确放行）** | Agent 判合规，实际也合规 | 从 FN 抽样同一批样本里得到（同一次复判的两个结果） | 每周 1 次 | 与 FN 抽样同批 |

**关键设计原则（三条）**：

1. **抽查必须随机，不能按金额。** 现在 PRD 里的 291 条是按 `近7天费用USD` 降序排列的——这**用于风险排序是合理的，但用于估计比率是无效的**。必须另建一个随机抽样批次（用 `抽样批次` 字段区分）。
2. **抽样要按语种分层。** 依据 Meta：`we sample and label content in the multiple languages`。Momcozy 有 6 个语种分组（英 199 / 德 42 / 法 20 / 西 11 / 意 9 / 其他 10），**德/法/西/意 每语种每两周至少要抽 5–10 条**，否则小语种的规则效果完全不可见。
3. **FP 的成本必须被显式记账。** 依据 Meta `False Positive Volume` 指标：**FP 是"错误地阻止了合规内容"的量**。对 Momcozy，一次 FP 的代价是：文案被改（可能损失转化）+ 修改工时 + 可能错过投放窗口。**这个代价目前完全没有被计量。**

#### 7.2.3 「错题本」的最小可用模板（一行一条）

```
错题ID | 记录日期 | 来源(自动抽样/人工复核/外部反馈/对抗测试)
内容ID | 平台 | 地区 | 内容语种 | 内容类型(文本/图片/视频)
Agent判定结果 | Agent判定规则编号 | Agent判定依据类型 | 规则版本号
人工复判结论(维持/推翻-应违规/推翻-应合规/无法判定) | 复判人 | 复判时间
错误类型(PAIR七类之一) | 是否对抗样本 | 对抗手法
处置码(直接改规则/部分改规则/评估中/不改+理由) | 关联规则编号 | 处置人 | 处置日期
```

**注意最后两组字段：`处置码` + `关联规则编号` + `处置人` + `处置日期`。** 这四个字段是把"错题本"变成"规则生产原料"的关键——**没有它们，错题本只是一份归档。** 依据：GHC 手册 `we will use these contributions to refine and improve later versions of this manual`（明确声明了用途）。

### 7.3 度量：盯哪几个数

**先给一条元规则（来自 Krippendorff Recommendation iv）**：

> **规则库健康度取"最差那条规则"的分数，不取平均。** `the reliability of each variable should be measured and the smallest among them should be taken as the reliability of the whole system`

#### 7.3.1 六个必看指标

| # | 指标名 | 定义 | 计算方式 | 目标值建议 `[推断]` | 依据 |
|---|---|---|---|---|---|
| **1** | **规则命中精确率 Precision** | 被 Agent 判为违规的内容中，经人工复判确认确实违规的比例 | `precision_r = 确认违规数 / 该规则命中总数`，**逐规则计算**，抽样复核 | 高危规则 ≥ 0.95；审慎规则 ≥ 0.85 | Meta `Precision` 定义；`we measure precision for both harms independently` |
| **2** | **误拦量 False Positive Volume** | 被错误拦截的合规内容条数（不是比例，是计数） | `FPV_r = (1 − precision_r) × 该规则命中总数` | 高危规则 ≤ 2 条/月；总量月度下降 | Meta `False Positive Volume` 定义 + `combining the volume of actioned content with measured precision` |
| **3** | **漏放率 Miss Rate（FN 方向）** | 被判合规的内容中，经抽样复判发现确实违规的比例 | `miss_r = 抽样中FN数 / 该规则判定合规的抽样总数`，**逐规则、逐语种** | 高危规则 ≤ 0.01（即每 100 条合规样本最多 1 条漏放） | Meta `Prevalence` 的思路（`how many views of violating content we didn't prevent`）+ YouTube `violative view rate` |
| **4** | **盲区率 Blind-spot Rate** | 抽样内容中"所有规则都不命中且无规则描述过该情形"的比例 | `盲区率 = UNCOVERED样本数 / 抽样总数` | 首月基线 < 40%；季度降到 < 20% | **本报告自建定义**（§5.4）；依据 NIST `MEASURE 1.1 … will not – or cannot – be measured are properly documented` |
| **5** | **人机一致率 IAA** | 两名判定者（人或人机）对同一批样本判定的一致程度 | **Krippendorff's α**，逐规则计算，**报告最小值** | 高危规则 α ≥ .800；审慎 α ≥ .667 | Krippendorff 2004 Recommendation iii/iv 逐字 |
| **6** | **规则贡献度 Ablation Delta** | 摘掉某条规则后，golden set 整体表现下降的幅度 | 在 golden set 上跑 `全量规则 vs 去掉规则r`，比较指标差 | **Δ = 0 的规则应进入"待退役"评审** | Andrew Ng CS229 `Ablative analysis: Remove components from your system one at a time, to see how it breaks.` |

**★ 行业实测基准（用于校准目标值，全部来自 §5.3 的官方数字）**：

| 指标 | Meta（FB，2026Q2） | YouTube（H1 2026，DSA 申报） | TikTok（2026Q1） |
|---|---|---|---|
| Precision / 判定准确率 | **90.80–91.85%**（全网）；Hateful Conduct 单类更低 | **Precision 0.874–0.896**；Accuracy 0.998–0.999 | 未同期披露 |
| 误拦量 | **30.2–30.8 百万条/季** | 通过 reversed 数体现 | restored 8,838,710（≈4.80% of removals） |
| 申诉推翻率 | 未直接披露比率 | **91,810 / 365,511 ≈ 25.1%**，中位处理 **5 天** | 未同期披露 |
| 主动发现率 | Hateful Conduct **66.40%**；Spam **99.60%** | 未单独列 | **99.3%** |

**`[推断]` 三条校准结论**：
1. **精确率 90–92% 是这个行业的头部水平。** Momcozy 的高危规则若把目标定在 ≥95% 并不激进（因为他们的判定域窄得多）；**但如果定在 99%，以现有 21 条规则的成熟度是不可能达到的。**
2. **申诉推翻率 25% 说明"初判有相当比例会被推翻"是常态。** 因此**"人工复核推翻 Agent 判定"不应被看作异常**，而应被设计成常规路径（这正是 §7.2.2 的 FP 采集设计）。
3. **主动发现率 66%（Hateful Conduct）与 99.6%（Spam）差距极大，说明"规则可自动化程度"在违规类型之间差异巨大。** 这直接支持 §2.4 的判断：**Momcozy 现在 21/21 全填"自动可检测"是不真实的**——即使 Meta，在最难的类别上也只做到 66% 主动发现。

#### 7.3.2 两个过程指标（不衡量质量，衡量运转）

| # | 指标名 | 定义 | 目标值建议 `[推断]` |
|---|---|---|---|
| **7** | **人工处理时延 Turnaround** | 从"转人工"到"给出结论"的时间 | 高危 ≤ 4 小时；审慎 ≤ 24 小时 |
| **8** | **抽检覆盖率 Audit Coverage** | 每周实际完成人工复判的样本数 / 计划抽样数 | ≥ 95%（达不到说明人力不足，而不是流程没问题） |

#### 7.3.3 三个"不要看"的指标（及理由）

| 不要用 | 为什么 | 依据 |
|---|---|---|
| **整体准确率（Accuracy）** | 会掩盖最差规则的表现。**Krippendorff 明确说"取最小值不取平均"** | Krippendorff 2004 Rec. iv |
| **"合规率 XX%"** | 现在的 291 条里 74% 落在"其他"地区桶，无美国样本；**样本对总体无代表性，比率不可外推** | §3.4；Meta `we avoid using it directly to calculate false positive volume` |
| **"规则命中数"作为工作量指标** | 命中多可能说明规则太宽（FP 高），也可能说明问题多。**方向不明确，不能用于激励** | `[推断]`——激励"多命中"会直接推高 FP |

### 7.4 冷启动 SOP：在"规则不全也不一定对"前提下，第一个月做什么

**设计原则（三条，来自 §6）**：
1. **不是"先拦着"也不是"先放着"**，而是**先做 MAP（上下文与风险映射），然后做一次显式的 go/no-go**。（NIST AI RMF §5.2）
2. **测不出来不能当低风险**；**度量手段不存在时，转为"追踪 + 显式记录不可测"。**（NIST AI RMF §1.2.1、MEASURE 3.2/1.1）
3. **临时措施必须相称、临时、可复审、能指定举证责任人。**（COM(2000)1 §6、§6.3.5）

#### 第 0 周（启动前）：MAP —— 把"没有规则"变成一个已知量

| 动作 | 产出物 | 依据 |
|---|---|---|
| 起草 **AI 系统上下文说明**：本 Agent 的 intended purpose、用户、部署场景、**明确写出"它不做什么"** | 1 页文档 | MAP 1.1 `Intended purposes … assumptions and related limitations` |
| 声明 **风险容忍度**：哪一类错误绝对不能出（法律/平台封号），哪一类可以容忍 | 1 页文档 | MAP 1.5 `Organizational risk tolerances are determined and documented` |
| 列出 **知识边界**：21 条规则覆盖什么、不覆盖什么、哪些是"不确定" | **已知缺陷清单** | MAP 2.2 `the AI system's knowledge limits` |
| **做一次 go/no-go**：在规则不全的情况下，是"全量上线 + 人工兜底"还是"仅哨兵模式" | 明确决策 + 理由 | MAP §5.2 逐字 go/no-go 要求 |

> **`[推断]` 我的建议**：第一个月采用**哨兵模式（shadow mode）**——Agent 全量跑、结果全部落库，但**不阻断发布**，由人工决定是否采纳。理由：在 precision/recall 未知的情况下，直接拦截会同时产生大量 FP（误伤在跑的好文案）与 FN（因为规则不全而放行），而且**没有任何数据支持"拦了比不拦好"**。这与任务书 §二.E 的既有约束一致（"无法强制卡死上线节点"）。

#### 第 1 周：建基线（不急着改规则）

| 日 | 动作 | 产出 |
|---|---|---|
| D1–D2 | **冻结规则版本**：给当前 21 条规则打版本号 `R2026.09.1`；把 `判断方式 = 自动可检测` 里**实际依赖语境判断的规则**重新标注为 `context_judgement` | 带版本的规则表 |
| D2–D3 | **建随机抽样批次**：从在跑内容中**按语种分层随机抽 100 条**（不是按金额），标记 `抽样批次 = W1-BASELINE` | 100 条抽样记录 |
| D3–D5 | **基线人工复判**：由**未参与规则制定的人**对这 100 条独立判定，填 `人工复判结论`；两人独立标 30 条，算 Krippendorff's α | 基线四格分布 + α 值 |
| D4–D5 | **补齐字段**：#1、#2、#3、#5、#7（§7.2.1），先让数据能落库 | 数据表结构变更 |
| D5 | **周会 1**：只看两件事——基线四格分布 + α 值。**本周不改任何规则** | 会议记录 |

#### 第 2 周：建 golden set（为回归门做准备）

| 日 | 动作 | 产出 |
|---|---|---|
| D6–D8 | **为每条规则建正例与反例**：从第 1 周的 100 条 + PRD 的 291 条里，为 21 条规则每条找 ≥1 正例、≥1 反例；**做不到的规则记入"不可测试清单"** | golden set v0.1 |
| D8–D9 | **构造对抗样本**：对 H02/H07/M01/M02/M03 这五条关键词类规则，各造 3–5 条变体（拼音、拆字、同义替换、跨语种变体拼写） | 对抗样本集 v0.1 |
| D9–D10 | **跑第一次回归**：用 golden set 跑当前规则版本，记录通过率 | 第一次回归报告 |
| D10 | **周会 2**：议题——① 哪些规则做不到正反例？（= 规则不可执行，需要重写）② 对抗样本通过率多少？ | 会议记录 + 待重写规则清单 |

#### 第 3 周：建采集路径与首次误差分析

| 日 | 动作 | 产出 |
|---|---|---|
| D11–D12 | **上线 FP 采集**：所有高危/审慎判定进人工复核队列；复核结论强制落库 | FP 记录开始产生 |
| D12–D13 | **上线 FN 采集**：每周从"合规·绿"随机抽 30 条做复判；同时开通"外部反馈"入口（客服/平台通知） | FN 记录开始产生 |
| D13–D14 | **上线兜底规则** `CATCH-ALL-01`（§6.1）：未命中 → `未覆盖` → 转人工，**不再自动判"合规"** | 盲区率开始可测 |
| D14–D15 | **第一次误差分析会**：用 PAIR 七类给本周所有错误分桶；对每类错误给**处置码** | 错误分桶表 v1 + 处置台账 v1 |
| D15 | **周会 3**：议题——① FP/FN 的分布 ② 错误分桶结果 ③ 哪些错误要直接改规则 | 首批规则修订草案 |

#### 第 4 周：首次完整闭环 + 定节奏

| 日 | 动作 | 产出 |
|---|---|---|
| D16–D18 | **按处置码修订规则**；每条修订**必须走环 2 的回归门**（golden set 必须 PASS） | 规则版本 `R2026.10.1` |
| D18–D19 | **发布首份月度度量报告**：6 个必看指标（§7.3.1），逐规则列出，**并明确标出最差的那条** | 月度报告 v1 |
| D19–D20 | **建立环 5（外部扫描）**：指定负责人，列出监控清单（Google Ads 政策页 / Meta 政策页 / TikTok 政策页 / 目标国广告法 / 竞品处罚） | 扫描清单 + 负责人 |
| D20 | **月度复盘**：① 一个月的数据够不够支撑"解除哨兵模式"？② 哪些规则该退役？③ 抽检人力够不够？ | 决策记录 + 下月计划 |

**第一个月之后**：进入 §7.1 的五环常规节奏（环 3 每日、环 4 每周+每月+每季、环 1 每月、环 5 双周、环 2 每次变更前）。

**四条"第一个月绝对不要做"的事**（`[推断]`，基于本次调研的反面证据）：
1. **不要先扩规则数量。** 21 条规则里"自动可检测"的比例是 21/21，但其中相当一部分（U01/U02/U03、M05、M07）本质上需要语境判断。**先把这 21 条的可执行性验证清楚，再谈扩到 50 条或 100 条。**
2. **不要用整体准确率作为验收标准。** 依据 Krippendorff Rec. iv。
3. **不要用"多数投票"解决 Agent 与人的分歧。** 依据 Krippendorff：`Resolving disagreements by majority … does not affect the measured reliability`。
4. **不要在没有随机样本的情况下发布任何"合规率"数字。** 依据 Meta 的抽样口径 + §3.4 的 Hidden Stratification。

### 7.5 严重等级：从平台 enforcement tier 与 NIST 提炼的分级原则

#### 7.5.1 从一手证据里能提炼的六条分级原则

| # | 原则 | 逐字证据锚点 | 对现有四档的含义 |
|---|---|---|---|
| **1** | **分级必须同时考虑"伤害严重度"与"发生可能性/暴露量"** | NIST AI RMF：`risk is a function of 1) the negative impact, or magnitude of harm … and 2) the likelihood of occurrence` | **现有四档只编码了"严重度"，没有编码"暴露量"**。一条 `高危` 规则命中一次（低暴露）与命中 300 次（高暴露），风险完全不同。**必须先算 `风险 = 严重度 × 暴露量`，再定处置。** |
| **2** | **分级决定"谁来做决定"，不只是"怎么处理内容"** | Meta：`when determining the appropriate restriction for a public figure … we may consider: (1) the severity of the violation and the person's history …, (2) the public figure's potential influence …, (3) the severity of the violence` | 现有四档的 `处理状态` 只有 `无需处理/待人工复核`。**缺少"由谁复核"这一维度**（一线 / 合规负责人 / 法务）。 |
| **3** | **分级要能触发不同的处罚梯度，且梯度必须写死** | Meta：`restriction length, ranging from one month to two years` + `heightened penalties` + `While most new violations will trigger a one month restriction …, more serious violations will merit a 2-year restriction … In extreme cases we will permanently disable the account.` | 现有四档**没有和历史挂钩**。Meta 的梯度是"违规次数 × 严重度"共同决定的。**建议增加 `累计违规次数` 维度。** |
| **4** | **严重等级必须与"一致性阈值"绑定** | Krippendorff：`An acceptable level of agreement … must be chosen depending on the costs of drawing invalid conclusions` | **高危档需要更高的 α 门槛**（§5.2.2）。现有四档没有与任何质量门槛绑定。 |
| **5** | **例外必须显式，且例外本身有分级** | TikTok：例外内容是"降级而非放行"，且 `We won't make exceptions for content that could cause extreme harm` | **需要第五档：`例外/降级`**。现在没有"内容保留但降级"这个中间态（对 Momcozy 对应"可以投但限制渠道/受众/地区"）。 |
| **6** | **分级必须对"未覆盖"有位置** | Ofcom Step 2：`Identify whether there are any additional characteristics or functionalities … not in the … Profiles, which could increase the risk`；NIST MEASURE 3.2 | **需要第六档：`未覆盖/未知`**，其默认处置是转人工 + 记录，**绝不能默认落到 `合规`**。 |

#### 7.5.2 现有四档够不够？——**不够，缺两档，且第一档的语义需要拆**

**现有四档**（任务书 §二.A）：`高危` / `审慎` / `待复核` / `合规`。

**问题诊断**：

| 现有档位 | 问题 | 建议 |
|---|---|---|
| `高危` | ✅ 语义清晰，但**缺少"谁来决定"和"扣多少"** | 拆出 `处置权限`（一线/合规负责人/法务）与 `处罚梯度`（对应违规次数） |
| `审慎` | ✅ 语义清晰，同上 | 同上 |
| `待复核` | ⚠️ **这是"过程状态"不是"风险等级"**。它和 H/M/U 三族的分类维度重叠（`U` 族就是"人工复核灰规则"）。**把过程状态混进风险等级，会导致"待复核"的内容永远停在待复核**（因为没人定义它复核完应该变成哪一档） | 把 `待复核` 从风险等级中**移除**，改为 `复核状态` 字段（`待复核/已复核-维持/已复核-升级/已复核-降级/已复核-放行`） |
| `合规` | ⚠️ **语义重载**：同时表示"确认合规"和"规则没覆盖到" | **拆成两档**：`合规`（明确判定为合规）与 `未覆盖`（无规则命中，需人工确认） |

**建议的六档结构**（`[推断]`，但每一档都有上文的一手依据）：

| 新档位 | 含义 | 默认处置 | 一致性门槛 | 处置权限 | 依据 |
|---|---|---|---|---|---|
| **L0 未覆盖** | 无规则命中，且不能确认为合规 | **转人工 + 记录"未覆盖原因"**；禁止自动放行 | 不适用（本身即"不知道"） | 一线 + 合规负责人 | NIST MEASURE 3.2；Ofcom Step 2；§6.1 兜底条款 |
| **L1 合规** | 明确判定合规 | 自动放行 | α ≥ .667 | 自动 | Krippendorff Rec. iii |
| **L2 待复核**（原 `待复核`） | 规则命中但结论不确定 | 转人工 | 不设一致性门槛；改看**转人工率**与**处理时延** | 一线 | 原创 |
| **L3 审慎**（原 `审慎`） | 命中审慎类规则，需限定表达 | 要求改写后放行 / 限制投放 | α ≥ .667 | 一线 + 合规负责人 | Krippendorff Rec. iii |
| **L4 高危**（原 `高危`） | 命中红线规则 | 拦截 + 法务/合规确认 + 记录 | **α ≥ .800** | **合规负责人 + 法务** | Krippendorff Rec. iii（`decision criteria have to be set far higher`）；Meta 升级处罚协议 |
| **L5 例外/降级** | 内容本身可保留，但需限制 | 保留但限制渠道/受众/地区 | α ≥ .800 | 合规负责人 | TikTok `Make it ineligible for the FYF / Add a warning screen / Add a context label` |

**关键改动只有三条**：
1. `待复核` 从"风险等级"移到"复核状态"。
2. `合规` 拆成 `L0 未覆盖` 与 `L1 合规`。
3. 新增 `L5 例外/降级`，给"可以投但有限制"一个正式位置。

**为什么这三条不能省**：
- 不拆 `未覆盖`，**盲区率永远不可测**（§5.4），规则库永远看起来"很干净"。
- 不拆 `待复核`，**复核完的内容无处可去**，会形成积压。
- 不加 `L5`，**所有非黑即白的判断都会被迫二选一**，导致要么误拦（推高 FP）、要么放行（推高 FN）。

**严重度的定义应当遵循 NIST 的两因子结构，并显式落成字段**：

```
严重度 severity ∈ {L0..L5}          # 伤害的"量级"
暴露量 exposure = 近7天展示 / 近7天点击 / 投放地区数   # 伤害的"概率"代理
综合风险 risk_score = severity × exposure 分档      # 决定处置优先级
```

**`[推断]` 这一条是对现有四档最实质的改进建议**：现在的风险等级是**纯严重度**，但 PRD 里已经有 `近7天费用USD / 展示 / 点击` 三个字段——**数据已经在表里，只是没有参与定级**。把暴露量纳入定级，可以在不增加任何采集成本的前提下，把"高危但只投了 3 次"和"高危且投了 20 万次展示"区分开。

---

## 附录 A：证据清单

**抓取日期**：除特别标注外，均为 2026-09-15（CST）。**原始证据目录**：`research/governance/_evidence/R4/`。

### A.1 平台政策生命周期与回写机制

| 来源 | URL | 本地证据文件 | 字节 |
|---|---|---|---|
| YouTube 官方博客：`On policy development at YouTube` | <https://blog.youtube/inside-youtube/policy-development-at-youtube/> | `youtube-policy-development.html` / `.txt` | 150,632 |
| Meta Newsroom：Facebook's Response to the Oversight Board's First Set of Recommendations（2021-02-25） | <https://about.fb.com/news/2021/02/facebook-response-to-the-oversight-boards-first-set-of-recommendations/> | `meta-ob-response-first-recommendations.html` / `.txt` | 685,430 |
| Meta 官方 PDF：`Facebook's response to the Oversight Board's first decisions`（含 17 条 recommendation 逐条回复） | <https://about.fb.com/wp-content/uploads/2021/02/OB_First-Decision_Detailed_FINAL.pdf> | `meta-ob-first-decision-detailed.pdf` / `.txt` | 72,669 |
| Meta Newsroom：In Response to Oversight Board, Trump Suspended for Two Years（2021-06-04） | <https://about.fb.com/news/2021/06/facebook-response-to-oversight-board-recommendations-trump/> | `meta-ob-response-trump.html` / `.txt` | 339,100 |
| Meta 官方 PDF：`Facebook Responses to Oversight Board Recommendations in Trump Case`（**19 条 recommendation × 4 个处置码**，20 页） | <https://about.fb.com/wp-content/uploads/2021/06/Facebook-Responses-to-Oversight-Board-Recommendations-in-Trump-Case.pdf> | `meta-ob-trump-recommendations-detailed.pdf` / `.txt` | 128,791 |
| Meta Newsroom：Requesting Oversight Board Guidance on Our Cross-Check System（2021-09） | <https://about.fb.com/news/2021/09/requesting-oversight-board-guidance-cross-check-system/> | `meta-ob-pao-crosscheck.html` / `.txt` | 448,464 |
| Meta Newsroom：Oversight Board Selects First Policy Advisory Opinion Request（2021-06） | <https://about.fb.com/news/2021/06/oversight-board-selects-first-policy-advisory-opinion-request-to-review/> | `meta-ob-first-pao.html` / `.txt` | 410,058 |
| Meta Newsroom：Meta Asks Oversight Board to Advise on COVID-19 Misinformation Policies（2022-07） | <https://about.fb.com/news/2022/07/oversight-board-advise-covid-19-misinformation-measures/> | `meta-ob-pao-covid.html` / `.txt` | 613,448 |
| Meta Newsroom：Facebook's First Quarterly Update on the Oversight Board（2021-07） | <https://about.fb.com/news/2021/07/facebooks-first-quarterly-update-on-the-oversight-board/> | `meta-ob-quarterly-update-1.html` / `.txt` | 594,769 |

### A.2 标注指南与翻译 gap

| 来源 | URL / 定位 | 本地证据文件 |
|---|---|---|
| **Gab Hate Corpus 训练手册**（20 页，六段式结构实物） | OSF <https://osf.io/edua3>（DOI `10.17605/osf.io/edua3`），文件 guid `nqt6h`，直链 <https://osf.io/nqt6h/download> | `gab-hate-corpus-trainingmanual.pdf`（234,977 B）/ `r4-gab-hate-corpus-trainingmanual.txt` |
| **GHC 论文**（48 页，含 Figure 1 判定树、Table 3 各维度 κ）。**⚠️ 正式出处更正**：任务书若引用"LREC 2020"版本，该版本**不存在**（已核对 LREC-2020 全部 895 篇标题）。正确出处为 **Kennedy et al. (2022), *Language Resources and Evaluation* 56:79–108, DOI `10.1007/s10579-021-09569-x`**（闭源；本报告使用的是 author manuscript，即 OSF 版本） | OSF <https://osf.io/hqjxn/download>，DOI `10.31234/osf.io/hqjxn` | `r4-ghc-paper-osf-hqjxn.pdf` / `.txt` |
| OffensEval / OLID：Zampieri et al., NAACL-HLT 2019, pp.1415–1420 | <https://aclanthology.org/N19-1144.pdf> | `r4-offensEval-naacl2019.pdf` / `.txt` |
| SemEval-2019 Task 6 | <https://aclanthology.org/S19-2010.pdf> | `r4-semeval2019-task6.pdf` / `.txt` |
| HateXplain：Mathew et al., AAAI 2021（Krippendorff α=0.46；4.6% 三人零共识） | <https://arxiv.org/pdf/2012.10289> | `r4-hatexplain-paper.pdf` / `.txt` |
| **Annotation Artifacts in NLI**：Gururangan et al., NAACL-HLT 2018, pp.107–112 | <https://aclanthology.org/N18-2017.pdf> | `r4-annotation-artifacts-nli.pdf` / `.txt` |
| **Plank, Hovy & Søgaard 2014**（ACL pp.507–511，`only 2% of annotator choices are linguistically unmotivated`） | <https://aclanthology.org/P14-2083.pdf> | `r4-plank-2014-debatable.pdf` / `.txt` |
| **Basile et al. 2021**：`We Need to Consider Disagreement in Evaluation` | <https://aclanthology.org/2021.bppf-1.3.pdf> | `r4-basile-2021-disagreement.pdf` / `.txt` |
| Unhealthy Conversations（6 子属性 IAA） | <https://arxiv.org/pdf/2010.07410> | `r4-ucc-unhealthy-conversations.pdf` / `.txt`、`r4-unhealthy-conversations-readme.md` |
| Perspective API TOXICITY model card（Google Jigsaw 官方 repo） | `raw.githubusercontent.com/conversationai/perspectiveapi/main/model-cards/English/toxicity.md` | `perspective-toxicity-modelcard.md` |
| OpenAI Moderation category 定义（官方 cookbook 内 vendored 文档） | `raw.githubusercontent.com/openai/openai-cookbook/main/examples/data/oai_docs/moderation.txt` | `openai-moderation-docs.txt` |
| AWS Bedrock Guardrails content filters（5 类 + 4 档强度） | <https://docs.aws.amazon.com/bedrock/latest/userguide/guardrails-content-filters.html> | `r4-aws-guardrails-content-filters.html` / `.txt` |

### A.3 误差分析 / 回归 / 对抗测试

| 来源 | URL | 本地证据文件 |
|---|---|---|
| **Andrew Y. Ng, CS229 `Machine Learning Advice`**（30 页；error analysis 与 ablative analysis 的原始定义） | <https://cs229.stanford.edu/materials/ML-advice.pdf> | `cs229-ml-advice-ng.pdf`（320,993 B）/ `.txt` |
| **Google PAIR Guidebook — `Errors + Graceful Failure`** | <https://pair.withgoogle.com/chapter/errors-failing/>（经本地代理） | `pair-errors-failing.html` / `.txt` |
| Google PAIR Guidebook — `Mental Models` | <https://pair.withgoogle.com/chapter/mental-models/> | `pair-mental-models.html` / `.txt` |
| **Settles, Active Learning Literature Survey**（67 页，CS Tech Report 1648, UW–Madison） | <https://burrsettles.com/pub/settles.activelearning.pdf> | `settles-2009-active-learning-survey.pdf`（1,939,936 B）/ `.txt` |
| **OPA Policy Testing**（`opa test` 范式） | <https://www.openpolicyagent.org/docs/policy-testing> | `opa-policy-testing.html` / `.txt` |
| **NIST AI 600-1（Generative AI Profile）**（64 页；红队定义与行动项） | <https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf> | `nist-ai-600-1-genai-profile.pdf` / `.txt` |
| Datasheets for Datasets（Gebru et al.） | <https://arxiv.org/abs/1803.09010> | `arxiv-datasheets-abs.html` |
| Model Cards for Model Reporting（Mitchell et al.） | <https://arxiv.org/abs/1810.03993> | `arxiv-model-cards-abs.html` |
| Hidden Stratification（Oakden-Rayner et al.） | <https://arxiv.org/abs/1909.12475> | `arxiv-hidden-stratification-abs.html` |

### A.4 度量与透明度

| 来源 | URL | 本地证据文件 |
|---|---|---|
| **Meta Prevalence** 指标定义（UPDATED MAR 6, 2025） | transparency.meta.com（经本地代理） | `meta-metric-prevalence.html` / `.txt` |
| **Meta Proactive Rate**（UPDATED FEB 22, 2023） | 同上 | `meta-metric-proactive-rate.html` / `.txt` |
| **Meta Precision**（UPDATED JUL 9, 2026） | 同上 | `meta-metric-precision.html` / `.txt` |
| **Meta False Positive Volume**（UPDATED DEC 11, 2025） | 同上 | `meta-metric-false-positive-volume.html` / `.txt` |
| **Meta Restored Content**（UPDATED OCT 4, 2022） | 同上 | `meta-metric-restored-content.html` / `.txt` |
| Meta Content Actioned / Appealed Content | 同上 | `meta-metric-content-actioned.html`、`meta-metric-appealed-content.html` |
| Meta Community Standards Enforcement Report 数据（2026 Q2，5,409 行） | 同上 | `meta-cser-2026Q2.csv`（列：`app, policy_area, metric, period, value`） |
| YouTube 指标与数字（violative view rate、申诉/恢复） | 同 A.1 YouTube 博客 | `youtube-policy-development.txt` |
| **Krippendorff 2004**：`Reliability in Content Analysis`（α ≥ .800 / α ≥ .667；四条建议；反对用 Cohen's κ） | <https://repository.upenn.edu/bitstreams/b6ea3a5b-3dee-4f27-a159-e44393eda7d4/download>（DOI `10.1093/hcr/30.3.411`） | `krippendorff-2004-reliability.pdf`（286,771 B）/ `.txt` |
| Cohen 1960 kappa（仅作对比；**注意 Krippendorff 反对其在内容分析中的使用**） | 本地副本 | `cohen-1960-kappa.pdf` / `.txt` |
| **Santa Clara Principles 2.0**（Foundational 5 条 + Operational 3 条，含 Numbers 完整清单） | <https://santaclaraprinciples.org/> | `santa-clara-principles.html`（31,712 B）/ `.txt` |
| Santa Clara 1.0（2018 原版）与历史 | 同站 | `santaclara-scp1-2018.html`、`santaclara-history.html`、`santaclara-open-consultation.html` |
| TikTok 透明度报告原始页面（**本文件未引用其内容**） | tiktok.com（经本地代理） | `tiktok-transparency-reports.html`、`tiktok-cg-report-2025h1.html`、`tiktok-cg-enforcement.html` |
| **EU DSA Transparency Database — Documentation (Overview)**（Art 17 的 16 个法定数据点及其字段定义） | <https://transparency.dsa.ec.europa.eu/> → Documentation → Overview | `dsa-tdb-documentation.html` / `.txt`（约 26 KB） |
| **EU DSA Transparency Database — Download**（每日 CSV/Parquet 全量与轻量包说明） | 同站 → Explore Data → Download | `dsa-tdb-download-page.html` / `.txt` |
| EU DSA Transparency Database — API and Schema | 同站 → Documentation → API and Schema | `dsa-tdb-api-doc.html` / `.txt`（41,632 B） |
| EU DSA Transparency Database — Additional explanation | 同站 | `dsa-tdb-additional-explanation.html` / `.txt`（26,567 B） |
| **YouTube VVR 方法学论文**：Barnett, A. (2021), *YouTube's Violative View Rate Methodology: A Statistical Assessment*（16 页，5 层动态分层抽样） | Google 公开 GCS bucket `storage.googleapis.com/transparencyreport/`（可匿名列举，1,065 个 key） | `_gcs-listing.txt` 索引；PDF 见同 bucket |
| **YouTube DSA 透明度报告 H1 2026**（结构化 CSV：`8_automated_means.csv`、`7_appeals_and_recidivism.csv`、`4_notices.csv`） | 同上 GCS bucket，发布 2026-08-28，覆盖 2026-01-01 ~ 2026-06-30 | 同 bucket |
| TikTok Community Guidelines Enforcement Report（2026Q1 正文 + **官方原始数据包** + `CGER_README.txt` 数据字典） | <https://www.tiktok.com/transparency/en/cg-report>（经本地代理） | `tiktok-2026Q1-cger-data.zip`（内含 `2026Q1_raw_data_cger_English.csv`，**本报告 §5.3.5 的全部数字均逐行核对自该 CSV 的 `Quarterly / Jan-Mar 2026 / All / All` 行**）、`tiktok-2026Q1-{volume,speed,prevalence,policies}.html`、`tiktok-cg-report-2025h1.html`、`tiktok-cg-enforcement.html` |
| **Stata 18 Base Reference Manual** `kappa`（L&K 六档量表的逐字复现与页码锚点 `(1977a, 165)`） | <https://www.stata.com/manuals/rkappa.pdf> | `kappa-benchmark-scale-stata-kappa-manual.pdf` |
| Landis & Koch 1977 官方元数据（PMID 843571，经 NCBI E-utilities efetch） | `eutils.ncbi.nlm.nih.gov` | `pubmed-landis-koch-843571-abstract.txt` |
| Santa Clara Principles **1.0（2018 原版三条）** | <https://santaclaraprinciples.org/scp1> | `santaclara-scp1-2018.html` |

### A.5 冷启动 / 风险识别先于控制

| 来源 | URL / 定位 | 本地证据文件 |
|---|---|---|
| **NIST AI RMF 1.0**（NIST AI 100-1, Jan 2023，48 页） | <https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf> | `nist-ai-rmf-100-1.pdf`（1,946,127 B）/ `.txt` |
| NIST AI RMF Playbook（147 页） | <https://airc.nist.gov/docs/AI_RMF_Playbook.pdf> | `nist-ai-rmf-playbook.pdf` |
| NIST AI RMF Core（AIRC 官方 HTML 版，含 Table 1–4） | <https://airc.nist.gov/airmf-resources/airmf/5-sec-core/> | `airc-5-sec-core.html` / `.txt` |
| NIST AI RMF Framing Risk（含 risk 定义） | <https://airc.nist.gov/airmf-resources/airmf/1-sec-risk/> | `airc-1-sec-risk.html` / `.txt` |
| **Meta Community Standards — Introduction「Our commitment to voice」**（含 ambiguous/implicit 兜底原文） | transparency.meta.com（经本地代理，en-gb 与 en-us 双版本） | `meta-cs-en-gb.html`、`meta-cs-us.html` / `.txt` |
| **Google Ads Policies** 主页（含三条兜底） | <https://support.google.com/adspolicy/answer/6008942?hl=en>（经本地代理） | `google-ads-policies-home.html` / `.txt` |
| **YouTube Community Guidelines**（EDSA 完整段 + `This list isn't complete` + 平台外行为条款） | <https://support.google.com/youtube/answer/9288567?hl=en>（经本地代理） | `youtube-cg-support.html` / `.txt` |
| **TikTok Community Guidelines — Enforcement**（Public Interest Exceptions 6 类） | <https://www.tiktok.com/community-guidelines/en/enforcement/>（经本地代理） | `tiktok-enforcement.html.txt`、`tiktok-cg-rendered.html.txt` |
| **Amazon Ads — Stores creative acceptance policies**（义务转移型兜底） | <https://advertising.amazon.com/resources/ad-policy/en> | `amazon-ad-policy-index.html` / `.txt` |
| **EU AI Act**（Regulation (EU) 2024/1689，Art 9 / 27 / 57–60） | Cellar `celex/32024R1689`（`Accept-Language: eng`） | `eu-ai-act-2024-1689.xhtml` / `.pdf` / `.txt` |
| **DSA**（Regulation (EU) 2022/2065，Art 34 / 35 / 37） | Cellar `celex/32022R2065` | `dsa-2022-2065.xhtml` / `.pdf` / `.txt` |
| **COM(2000) 1 final**《预防原则通讯》（28 页） | Cellar `celex/52000DC0001` | `eu-com-2000-1-precautionary.pdf` / `.txt` |
| **UK Online Safety Act 2023** s.9 / s.10 / s.11 / s.12 | <https://www.legislation.gov.uk/ukpga/2023/50/section/{9,10,11,12}>（经 CDP 通过 AWS WAF） | `uksa-s9.html.txt`、`uksa-s10.html.txt`、`uksa-s11.html.txt`、`uksa-s12.html.txt` |
| **Ofcom** *Children's Risk Assessment Guidance*（85 页，四步法） | ofcom.org.uk | `ofcom-childrens-risk-assessment-guidance.pdf` / `.txt` |
| ISO 31000:2018 官方页（**仅预览页，无条款正文**） | <https://www.iso.org/standard/65694.html> | `iso-31000-official-page.txt` |
| ISO/IEC 42001:2023 官方页（**仅预览页**） | <https://www.iso.org/standard/42001> | `iso-42001-official-page.txt` |
| ISO/IEC 23894:2023 官方页（**仅预览页**） | <https://www.iso.org/standard/77304.html> | `iso-23894-official-page.txt` |

### A.6 委托方现状材料（本文引用处）

| 来源 | 本地路径 | 引用位置 |
|---|---|---|
| 调研任务书 | `research/governance/00-调研任务书.md` | 全文 |
| 内容治理需求文档（含 291 条广告明细与 21 条规则 schema） | `PRD/内容治理需求文档.md` | §2.4、§7.2、§7.3、§7.5 |

---

## 附录 B：缺口清单（我尝试过但没拿到的东西）

> 本分片所在环境的网络存在 **DNS 污染**（`youtube.com`→Meta IP 段、`tiktok.com`→Meta IP 段）与 **WAF 拦截**。多数缺口已通过**本地代理（127.0.0.1:7890）**或**官方替代通道（EUR-Lex → 欧盟出版局 Cellar）**解决；以下为**最终仍未取得**的项目。

### B.1 未取得的一手来源（影响论断强度）

| # | 目标 | 状态 | 原因 | 对本报告的影响 |
|---|---|---|---|---|
| **1** | **Landis & Koch (1977) 原文 PDF** | **未取得（但内容与页码已双重锚定）** | Unpaywall `is_oa:false / oa_status:"closed"`；Semantic Scholar `openAccessPdf.status:"CLOSED"`；12 个镜像全部失败（JSTOR 403、dentalage 403、stat.washington.edu 404、gwern.net 404、ResearchGate 403）；`repositorio.unal.edu.co/handle/unal/80119` 指向的是一篇**引用**该文的硕士论文，非原文 | **§5.2.3 已改为「经 Stata 18 官方手册转引」**（`(1977a, 165)` 锚定原刊页码 165）+ 第二条独立开放复现 + PubMed 官方元数据。**引用时须注明"转引"，不得声称读过原文。** 内部质量门槛仍用 Krippendorff 2004 的 α 阈值（原文已取得） |
| **2** | **Andrew Ng, *Machine Learning Yearning* 全文（特别是"手动检查约 100 个误分样本"的具体章节）** | **未取得** | `info.deeplearning.ai/hubfs/ML-Yearning.pdf` → 404；`deeplearning.ai/machine-learning-yearning/` → 404；`www.deeplearning.ai/wp-content/uploads/2020/09/ML-Yearning.pdf` → 403；GitHub 镜像不可检索 | **「先看 100 个错误样本」这条具体动作建议缺少一手出处。** 已用可取得的 CS229 `ML-advice.pdf`（error analysis 的原始定义，**原文已取得**）+ PAIR 的错误七分类 + Meta 的抽样 precision 流程作为替代证据链 |
| **3** | **Oversight Board 官网（oversightboard.com）的 case 页面原文** | **未取得** | 直连 403（Cloudflare/行政规则）；经代理仍 403；sitemap.xml 403；`web.archive.org` 直连不可达（经代理可访问首页，但未用于取 OB 页面） | **无法直接引用 OB 裁决书原文。** §1.2.2 改用 **Meta 官方发布的逐条回复 PDF**（这两个 PDF 是 Meta 对 OB 意见的正式回应，属一手来源，且信息量更大——含 4 个处置码与 19 条 recommendation 全文引述） |
| **4** | **Meta Community Standards 中的 `Commonly Reported Not Hate Speech` 段落** | **未取得** | `transparency.meta.com` Community Standards 页面经代理返回 HTTP 400 / JS 渲染；已取得 `meta-cs-en-gb.html`、`meta-cs-us.html`（7.4 KB 渲染文本），但**未包含该小节** | 影响"平台自带的边界案例说明"这一论据。已用 GHC 手册的 `Examples of vulgarity that are not hate (NH)` 专节 + `r4-ghc-paper` 的判定树作为等价替代 |
| **5** | **Amazon 的强兜底条款**（如 "reserves the right to reject or remove any ad"） | **未确认存在** | `advertising.amazon.com` 的 sponsored-ads / creative-acceptance 页为 Cloudflare + SPA 双重保护；已取得的 Stores creative acceptance 页中**仅有"义务转移型"兜底** | §6.1 的 Amazon 一栏已按实际取得的原文填写；**任务书预期的"强兜底"表述未确认，不予引用** |
| **6** | **Google Ads 的 `"Google reserves the right to…"` 表述** | **确认不存在**（0 命中） | 官方政策页全文检索 | **任务书该预期不成立。** 已替换为实际存在的三条兜底（§6.1） |
| **7** | **TikTok 的 `"new or emerging"` 内容类型表述** | **确认不存在**（0 命中） | 官方 Community Guidelines 页全文检索 | **任务书该预期不成立。** 已替换为 "Public Interest Exceptions"（§6.1） |
| **8** | **YouTube Community Guidelines 中的 age-restriction 表述** | **未找到** | 该页明确 EDSA 结果是 `gets an EDSA exception`，**未提 age-restriction** | 年龄限制措辞应在各具体政策子页（如 Nudity & sexual content policy），本轮未抓 |
| **9** | **ISO 31000:2018 Clause 6.4.2 / 6.4.3 / 6.4.4 条文正文；ISO/IEC 42001:2023 Clause 6.1.2 / 6.1.3 / 8.2 / 8.3 条文正文** | **未取得** | 付费标准（31000 为 CHF 135 / 16 页；42001 为 51 页；23894 为 CHF 155 / 26 页）；ISO 官网与 OBP 均不含条款正文，且经 Cloudflare 保护（仅有头 Chrome 可取官方页 HTML） | **§6.4 只能提供"结构关系"层面的证据**（31000 是通用指南且不可认证、42001 是可认证的 AI 管理体系并采用 PDCA、23894 是 AI 风险管理专项指引）。**"风险识别先于风险控制"在 ISO 体系中的确切条款依据未核实。** 已用 NIST AI RMF（MAP 先于 MEASURE/MANAGE）与三法域的"部署前评估"条款作为替代锚点 |
| **10** | **Case T-13/99 (Pfizer Animal Health v Council, 2002) 判决正文** | **未取得** | curia.europa.eu 为 JS 渲染且需接受 cookie（抓取返回 7 字节）；Cellar `celex/62099A0013` 与 `62099TJ0013` 均 404（CELEX 编号不适用于该法院判决） | 任务书已授权跳过。**COM(2000)1 已含预防原则判据的官方权威表述**，论断强度未受损 |
| **11** | **Chandrasekharan et al. 2018, *The Internet's Hidden Rules*（DOI 10.1145/3274301）原文 PDF** | **未取得** | OpenAlex 标记 OA: None；dl.acm.org 付费墙；arXiv 无副本 | 该文用于"规则从实践中涌现"的论据被移除，不影响主要结论 |
| **12** | ~~TikTok 透明度报告指标 / DSA schema~~ | **已补齐** ✅ | — | **§5.3.3 已补齐 DSA Transparency Database（16 个法定数据点 + 批量下载 + 字段逐字定义）；§5.3.5/§5.3.7 已补齐 TikTok 指标（两个"分母不同"的率）与三平台口径对照表。** |
| **12b** | **YouTube Community Guidelines Enforcement Report 官方"指标定义"页** | **未取得** | `support.google.com/youtube/answer/9228202` → **404**；`transparencyreport.google.com/youtube-policy/overview` 仅 7,814 字节 JS 外壳；`api/v3/youtubepolicy/*` 全部 404 | YouTube 的 removals / appeals 明细**未核实**。已用**VVR 方法学论文 + DSA 报告结构化 CSV**（官方 GCS bucket）替代 |
| **12c** | **Cohen (1960) 原文措辞** | **未核实** | Sage bot 挑战；OpenAlex `is_oa:false, any_repository_has_fulltext:false` | 目录中 `cohen-1960-kappa.pdf` 是课程讲义（转引原文 Table 2）；`cohen-1960-kappa-usp.pdf` 实为 Fleiss/Cohen/Everitt (1969), *Psych. Bulletin* 72(5):323–327。**两者都不是 Cohen 1960，不要混用。** |
| **12d** | **Krippendorff 方法书（*Content Analysis*, 3rd/4th ed.）§11.x 的 α 正文定义** | **未核实** | 无开放副本 | HCR 论文（已取得）已给出 α 的定义形式（`α = 1 – (b + c) / (2 p q)`，Figure 2），**可满足报告需要** |
| **12e** | **Santa Clara Principles 2.0 的 "State of Content Moderation" 报告要求** | **确认不存在**（grep 零命中） | SCP 2.0 全文与 Open Consultation Report 均无此专名 | **不得引用该专名。** |
| **12f** | **Jigsaw / Borkan et al. (arXiv:1903.04561) 作为 IAA 来源** | **不适用** | 该论文全文 regex 扫描 `kappa`/`agreement`/`annotator` **零命中** | **该论文不含任何 IAA 数值，不得作为标注一致性证据引用。** 已改用 Waseem 2016（`W16-5618`，**非任务书所写的 W16-5105**）、Sap et al. 2019 ACL、OffensEval NAACL 2019 |
| **13** | **Perspective API 完整属性表**（SEVERITY / IDENTITY_ATTACK / INSULT / THREAT 等） | **未取得** | `developers.perspectiveapi.com` 属性页为 GitBook 客户端渲染，抓到的是 JS 外壳、正文 0 行 | 已用官方 TOXICITY model card 替代；§2.3 的对照表仅覆盖 TOXICITY 一个属性，**不代表 Perspective 的完整 taxonomy** |
| **14** | **Wikimedia / Wikipedia 的公开内容政策**（如 Harassment、Reliable sources） | **未抓取** | `en.wikipedia.org`、`foundation.wikimedia.org` 连接失败 | `[推断]` 该来源对本文结论的边际贡献低（GHC 手册已提供更完整的判定结构实物），未列入必取项 |
| **15** | **Reddit Content Policy / GitHub AUP / TSPA Competency Framework** | **未抓取** | 主机可达但时间未及 | `[推断]` TSPA 的 Policy 与 Enforcement 分工描述对"政策→执行"的岗位设计有参考价值，**建议后续补抓** |

### B.2 条款号更正汇总（**引用时必须使用修正后的编号**）

| 任务书原编号 | 实际编号 | 逐字内容 | 来源 |
|---|---|---|---|
| EU AI Act Art 9(4) "adoption of appropriate and targeted risk management measures" | **Art 9(2)(d)** | "the adoption of appropriate and targeted risk management measures designed to address the risks identified pursuant to point (a)" | `eu-ai-act-2024-1689.txt` |
| EU AI Act Art 9(1) "throughout the entire lifecycle" | **Art 9(2)** | "a continuous iterative process planned and run throughout the entire lifecycle" | 同上 |
| EU AI Act Art 9(4)（原描述） | **Art 9(4) 实为** | 本节各项要求合并适用时的相互作用与平衡 | 同上 |
| DSA Art 34(3) "at least once a year" | **Art 34(1)** | "at least once every year thereafter, and in any event prior to deploying functionalities…" | `dsa-2022-2065.txt` |
| DSA Art 34(3)（原描述） | **Art 34(3) 实为** | "preserve the supporting documents of the risk assessments for at least three years" | 同上 |
| NIST AI 600-1 **MS 2.4** | **不存在**（0 命中） | — | `nist-ai-600-1-genai-profile.txt` |
| NIST AI 600-1 **GV-1.1-003** | **不存在**（0 命中） | — | 同上 |
| NIST AI 600-1 红队相关实际条款 | **MP-2.3-005、MP-5.1-005、MG-2.2-001、MG-2.2-005、MS-2.8-002** | 见 §4.3 | 同上 |

### B.3 方法学层面的已知局限（诚实声明）

1. **本报告的搜索结果主要依赖直连抓取而非搜索引擎。** 本次会话的搜索通道（firecrawl 免费额度）在早期即耗尽（HTTP 429），此后所有来源发现均依赖**已知 URL 直连 + 站点自有 sitemap/搜索 + OpenAlex/Unpaywall 开放获取索引**。这意味着**可能存在未被发现的更优一手来源**。
2. **§5.3.3（TikTok / DSA 透明度数据库）是明确的空白节**，本文件对该主题不作任何陈述。
3. **§6.4（ISO）的结论强度显著低于其他节**，因为只取得了官方预览页。
4. **本报告"对 Momcozy 的直接含义"一节（§7）中标 `[推断]` 的部分是我的判断**，不是引文。所有标记 `[原文]` 或附有逐字引用的论断均来自前文列出的证据文件。
5. **行数超出任务书目标（800–1500 行）。** 定稿约 1,950 行，全部为逐字证据与结构化清单，**未做任何为凑长度的展开**。若需压缩，可裁减 §2.3 的工业界 category 对照表、§5.3.3 的 DSA 字段表与 §6.1 的兜底条款对照表，但这两处是三份分片之外最可复用的部分。

---

**（R4 完）**
