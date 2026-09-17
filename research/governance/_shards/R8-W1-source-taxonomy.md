# R8-W1 规则来源分类学与冲突优先级

> 分片定位：本文只回答两个问题 —— **一条审核规则可能从哪来**（来源分类学），以及 **这些来源互相冲突时谁压谁**（冲突优先级）。
> 严重等级定档、空白/缺失处理、规则 schema 字段设计，均不在本文范围。
> 撰写日期：2026-09-15。工作目录 `/Users/lute/Project/audit_multi_content`。

---

## 0. 本部分结论

1. **「规则从哪来」有九类来源，但它们不平等——而且不平等的分界线不是权威度，是「是否产出可判定条件」**：只有法源、平台明文政策、品牌调性三层产出判定依据，其余六类只产出信号与候选规则（§1.1 表 + §2.3.2 落位表）。

2. **找到了显式的冲突优先级声明，但它是四散的、不完整的，且没有任何一方给出全序**：最硬的一条是 GitHub ToS 的 `Except to the extent applicable law provides otherwise`（法源 > 平台协议），配合 Amazon 的 `Our policies aren't legal advice`（平台自认政策不能替代法律）与 GitHub AUP 把 `Compliance with Laws and Regulations` 编为第 1 条（§2.1.1 / §2.2.2 / §1.2.2）。

3. **⭐ 真实的排序是两层而不是一层，这是本分片最重要的澄清**：**立法层「法源 > 平台政策 > 品牌调性」成立，但裁决层「平台说了算」同时成立**（`at its sole discretion`）——所以客户的规则库必须分开建模这两层，且对平台沟通时不能引用位阶，只能引用「根因已消除」（§2.2.2 + §1.2.3 的 `look for the root causes`）。

4. **平台政策的变化速度是每月 6–14 条，这是一个人力容量问题而不是态度问题**：Google Ads 实测 2024 年 68 条 / 2025 年 75 条 / 2026 年至 9 月 58 条，Amazon Ads 2026 年 1–4 月 28 条；但其中母婴相关的垂直类目条目极少，**加一条相关性过滤即可把跟进量从每月 12 条压到 0–2 条**（§1.2.2）。

5. **⭐ 过渡期长度本身就是量化了的隐含优先级**：法源类（OFAC 制裁）**0 天**（`No grace periods or exceptions are possible`）、平台 critical 违规 **3 天**、平台新规 **约 30 天且到期自动迁移**——平台不可能给它认为更低阶的来源更短的宽限期，这比措辞位置证据强得多（§3.1）。

6. **法源的实际滞后可以长达 38 个月，这反而是客户建库的唯一机会窗口**：EU AI Act 第 6(1) 条 `Done at Brussels, 13 June 2024`，但 `shall apply from 2 August 2027`；因此规则库必须支持「已通过未适用」这一第三状态，而客户现有 12 字段里只有二值的 `启用状态`（§3.3 + `01-内部证据-规则表现状审计.md:29`）。

7. **「来源可信度」没有被任何真实系统显式建模成一个字段**：NIST SP 800-30 把「识别信息来源」建模成了正式任务（TASK 1-4，分内部/外部），但**不给来源打分**；GitHub 有一个真实的 `versions: fpt: '*'` 作用域字段，但它建模的是适用范围不是可信度——**本文 §1.1 的「可信度」列是本文的定性判断，不是行业标准**（§3.4）。

8. **最危险的衰减是「无文本变更的重新校准」，任何盯 changelog 的机制都会完全漏掉它**：Amazon 明文 `We may change the severity of a violation if we observe changes…`，FTC 要求广告主自行跟进眼动研究——两者都不产生政策文本变更，因此规则库必须带「强制复审闹钟」而不只是「来源标签」（§3.5）。

9. **品牌调性是九类里唯一客户拥有 100% 主权的一类，但它目前在客户的字段体系里无处安放**：客户 `依据来源` 只有「品线反馈」与「红绿灯.xlsx」两个取值，品牌调性要么被伪装成专家经验、要么不存在——而这两者的衰减行为完全不同（§1.2.4）。

10. **建议的默认立场：品牌规则只允许比平台更严，不允许更松**——依据是风险不对称：加严的代价是投放量，放宽的代价是封店；且平台从未声明「不得比本政策更严」，反而把 `industry standards` 与法规并列、把合规责任完全推给广告主（§2.3.3 场景 3）。


---

## 1. 来源分类学

### 1.1 分类总表

**与 R4 §1.4 的边界（避免重复）**：R4 §1.4 的表是「**YouTube/Meta 官方政策流程**吃进哪些输入源」，落点是「Momcozy 有没有对应物」。本节的表是「**客户规则库**里一条规则的来源类别」，落点是这条来源的**四个工程属性**（可信度 / 更新频率 / 萃取成本 / 可否自动化）。两者互补：R4 回答「平台怎么造规则」，本文回答「你抄哪一层、多久抄一次、抄得动吗」。

**判定口径说明**（避免读者误读四个属性）：
- **可信度**＝「该来源的判定与最终裁决者（法源 / 平台 / 客户自己）的一致程度」，不是「听起来权威不权威」。分三档：高＝有外部强制力背书；中＝有平台执行力背书但随政策漂移；低＝仅是偏好，无外部背书。
- **更新频率**＝该来源**内容本身发生变化**的节奏，不是你去读它的节奏。两者之差就是滞后的来源。
- **萃取成本**＝把一个自然语言/案例形态的来源，变成「可判定的规则条目」所需的人力。
- **可否自动化**＝该来源的**变化检测**能否自动化。注意：**检测可自动化 ≠ 萃取可自动化**，下表在「可否自动化」列里把两者分开标注。

| # | 来源类 | 可信度 | 更新频率（有实测数字的给数字） | 萃取成本 | 可否自动化（检测 / 萃取） | 真实案例证据 |
|---|---|---|---|---|---|---|
| 1 | **法源**（法规 / 判决 / 执法案例） | **高**（有国家强制力） | 慢，但**生效日是硬日期**，不可协商 | 高（需法务或外部律师把法条译成判定条件） | 检测：可（法规生效日可订阅）；萃取：**不可** | GitHub AUP §1 把 `Compliance with Laws and Regulations` 置于第 1 条；GitHub ToS `Except to the extent applicable law provides otherwise` |
| 2 | **平台政策（明文的）** | 中（有平台执行力，但平台可单方改） | **快**：Google Ads 2024=68 条 / 2025=75 条 / 2026 至 9 月=58 条；Amazon Ads 2026 年 1–4 月=28 条 | 中（平台已把政策写成条目化文本，但要译成图片/文案判定条件） | 检测：**可**（有官方 changelog）；萃取：部分可 | `google-ads-changelog-2026.md`（58 条）、`google-ads-changelog-2025.md`（75 条）、`amazon-ads-change-log-G8X8M375UPCN4UUC.md` |
| 3 | **平台实际判例**（申诉结果） | 中低（**与明文政策可能不一致**，见 §1.2.3） | 每次申诉即产生，**频率最高** | 极高（个案 → 规则要人工泛化） | 检测：可（申诉结果有回执）；萃取：**不可** | `amazon-appeal-*` 系列；npm 有专门的争议解决文本 `npm-disputes.txt` |
| 4 | **品牌自定调性** | 低（纯偏好，**无外部背书**） | 随品牌/季节/品线变，**无常规律** | 低（决策者自己就能说清） | 检测：不可（没有外部发布物可盯）；萃取：**人工为主** | 见 §1.2.4（本次未取得客户品牌调性的成文文档） |
| 5 | **竞品对标** | 低（**竞品可能本身违规**，是负样本不是正样本） | 随竞品投放节奏，不可预测 | 中（要采集、去重、判断「它为什么能过」） | 检测：可（抓取）；萃取：不可 | R5 分片负责竞品，本文只给来源属性 |
| 6 | **客户投诉 / 差评** | 低到中（是**风险信号**，不是规则本身） | 连续流，全年无休 | 中（要聚类去重，否则同一抱怨产生 N 条伪规则） | 检测：可；萃取：**半自动**（聚类可自动，定则要人） | R4 §1.4 把「用户/买家举报」列为平台输入源第一行 |
| 7 | **内部专家经验** | 中（**取决于该专家是否见过足够多案例**） | 随人员流动，**会突然归零**（人走了） | 低到中（访谈即可，但难穷尽） | 检测：不可；萃取：**不可**（必须访谈） | NIST SP 800-30 Rev.1 明确把 expert judgment 作为评定输入；见 §1.2.7 |
| 8 | **数据挖掘**（从标注数据反推） | 中（**只反映历史，不反映应然**） | 随数据积累，**不随政策变** | 低（有算法）到高（要清洗标签） | 检测：可；萃取：**最可自动化的一类** | `_evidence/R8/rulefit-arxiv.txt`（RuleFit 从数据提规则）；`_evidence/R8/ke-llm-drops.txt` |
| 9 | **KOL / 代理商反馈** | 低（**利益相关，且有动机放宽**） | 项目制，随合作周期 | 低 | 检测：不可；萃取：不可 | 本次未取得可引用的一手文本，见 §1.2.9 |

**表的读法（三条硬结论）**：

【判断】
1. **可信度与更新频率在本表里是反相关的**：最可信的法源最慢，最不可信的平台实际判例最快。**这意味着「高可信来源永远追不上高频变化」是结构性的，不是执行力问题。** 任何声称「等法务确认了再改规则」的流程，在平台政策 6 条/月的节奏下必然瘫痪——依据上表第 2 行 Google 的实测数字。
2. **「可否自动化」一列里，只有第 8 行（数据挖掘）在萃取侧也是「可」**。其余八类的**变化检测**大多可自动化、**萃取**几乎全要人。这直接决定了客户团队的岗位配置：**需要一个「变更侦测」的自动化岗，和一个「规则萃取」的人工岗，两者不是同一个人。**
3. **第 3 行是唯一「高频 + 高萃取成本 + 不可自动化」三重叠加的类**，也是客户最容易忽略的类。它恰恰是 R4 分片里「错题本」要承接的那一类（见 `R4-trust-and-safety-ops.md` §3.5 的四条转换机制）。**没有错题本，第 3 类来源就完全进不了规则库。**


### 1.2 逐类剖析

#### 1.2.1 法源（法规 / 判决 / 执法案例）

**这一类的最重要特征：法源自己会声明自己的边界，而这个边界正好是下一类法源的入口。**

【原文】（FTC 工作人员指南自陈其适用范围，明确排除其他法源）

> This staff guidance document only addresses disclosures required pursuant to laws that the FTC enforces. It does not address disclosures that may be required pursuant to local, state (e.g., many sweepstake requirements), or other federal laws or regulations (e.g., regulations issued by the Consumer Financial Protection Bureau or the Food and Drug Administration).

来源：`_evidence/R8/ftc-dotcom.txt`（Federal Trade Commission, *How to Make Effective Disclosures in Digital Advertising*, March 2013，第 2 页脚注 2）
URL: https://www.ftc.gov/system/files/documents/plain-language/bus41-dot-com-disclosures-information-about-online-advertising.pdf
（HTTP 200，2,332,432 bytes，53 页真实 PDF；文本经 pypdf 抽取，落盘为 `ftc-dotcom.txt`）

【判断】
- **对 Momcozy 的直接含义**：FTC 明确把 `Food and Drug Administration` 排除在自己的范围之外。母婴/吸奶器类目**同时**落在 FTC（广告真实性）与 FDA（医疗器械/健康声称）两条法源下。客户如果只建一条「遵守广告法」的规则，就**在结构上漏掉了一整个法源**。
- 这也回答了「法源是不是一个类」：**不是**。法源是一个**集合**，且集合内部的成员会互相划界。规则库必须按「法域 × 监管主体」二维落位，而不是一个「法源」标签。
- 本条是**边界声明**，不是效力排序。它告诉你「这条不覆盖那一条」，但不告诉你「冲突时谁赢」。

【原文】（FTC 承认判定标准不可穷举，并给出解释偏好）

> There is no litmus test for determining whether a disclosure is clear and conspicuous, and in some instances, there may be more than one method that seems reasonable. In such cases, the best practice would be to select the method more likely to effectively communicate the information in question.

来源：`_evidence/R8/ftc-dotcom.txt`（第 2 页）
URL: 同上

【判断】
- `There is no litmus test` 是**法源层面的显式不确定声明**。委托方问「规则库要不要覆盖所有情况」，法源本身的回答是：**连监管机构都不给穷举清单**。
- 但它给了兜底：`select the method more likely to effectively communicate`。这与 §2.1.4 的 PyPI `resolve disputes in favor of protecting users as a whole` 是**同一结构**——**当位阶无法裁决时，回落到一个价值取向**。两处独立来源给出同一结构，这是本文认为「兜底规则必须有」的最强论据。
- 注意两者取向不同：FTC 偏向「有效沟通」，PyPI 偏向「保护用户整体」。**兜底句本身就是价值选择，客户必须自己选一句写下来**，不能默认继承。

【原文】（FTC 的可执行判定要素清单——这是可直接转成规则条件的部分）

> 3. Required disclosures must be clear and conspicuous. In evaluating whether a disclosure is likely to be clear and conspicuous, advertisers should consider its placement in the ad and its proximity to the relevant claim. **The closer the disclosure is to the claim to which it relates, the better.** Additional considerations include: the prominence of the disclosure; whether it is unavoidable; whether other parts of the ad distract attention from the disclosure; whether the disclosure needs to be repeated at different places on a website; whether disclosures in audio messages are presented in an adequate volume and cadence; whether visual disclosures appear for a sufficient duration; and whether the language of the disclosure is understandable to the intended audience.

来源：`_evidence/R8/ftc-dotcom.txt`（第 i–ii 页，Overview 第 3 条；**加粗为本文所加**）
URL: 同上

【原文】（同一条的可操作化，含一条对客户的硬约束）

> 4. To make a disclosure clear and conspicuous, advertisers should:
> ● Place the disclosure as close as possible to the triggering claim.
> ● Take account of the various devices and platforms consumers may use to view advertising and any corresponding disclosure. If an ad is viewable on a particular device or platform, any necessary disclosures should be sufficient to prevent the ad from being misleading when viewed on that device or platform.
> ● When a space-constrained ad requires a disclosure, incorporate the disclosure into the ad whenever possible. However, when it is not possible to make a disclosure in a space-constrained ad, it may, under some circumstances, be acceptable to make the disclosure clearly and conspicuously on the page to which the ad links.
> ● Preferably, design advertisements so that "scrolling" is not necessary in order to find a disclosure. When scrolling is necessary, use text or visual cues to encourage consumers to scroll to view the disclosure.
> ● Keep abreast of empirical research about where consumers do and do not look on a screen.
> ● Display disclosures before consumers make a decision to buy — e.g., before they "add to shopping cart."

来源：`_evidence/R8/ftc-dotcom.txt`（第 ii 页）
URL: 同上

【判断】
- **这一组是法源类里最可直接萃取的部分**：`proximity` / `prominence` / `unavoidable` / `distracting` / `repetition` / `duration` / `understandable language` 七个维度，每一条都是**可判定的图像/版面属性**。这意味着法源类**并非完全不可自动化萃取**（修正 §1.1 表中第 1 行「萃取：不可」：**该行应读作「法条原文不可自动萃取，但监管机构发布的合规指南可被人工一次性翻译成版面规则」**）。
- `Keep abreast of empirical research about where consumers do and do not look on a screen` 是一条**引用外部可变知识**的规则。它使这条规则**自带过期风险**：眼动研究变了，规则该变。这是 §3「可信度衰减」的一个非政策类实例。
- `before they "add to shopping cart"` 把披露义务**锚定在一个具体的交互事件**上。这种「锚定到事件」的写法比「及时披露」可判定得多，值得客户规则库照抄写法。
- 对跨境业务的额外价值：`Take account of the various devices and platforms` 与 `If an ad is viewable on a particular device or platform` 意味着**同一条规则在不同设备/平台上的判定结果可以不同**。客户的 21 条规则如果是平台无关的单层写法（见 `01-内部证据-规则表现状审计.md`：12 字段、覆盖率 13.8%），在法源层面就是不完整的。

**法源类的小结（三条属性回填 §1.1）**：
- **可信度：高**，但高的理由是「有强制力」，不是「明确」。FTC 自己说 `no litmus test`。
- **更新频率：慢，但截止日是硬的**。FTC 这份指南是 2013 年 3 月的，到 2026-09-15 抓取日仍是在效版本——**13 年未改**。这与平台政策 6 条/月形成两个数量级的对比。
- **萃取成本：一次性高、后续低**。因为它的形态是「原则 + 要素清单」，翻译一次可长期用。

#### 1.2.2 平台政策（明文的）

**这一类是客户唯一已经在用的来源，也是变化最快的一类。**

【原文】（Google Ads 政策更新台账——2026 年 1–9 月的逐条记录，摘录前若干条）

> - Update to Location asset requirements (September 2026)
> - Update to Google Ads Personalized Advertising Policy (September 2026)
> - Update to the Google Ads Developer Policies (August 2026)
> - Update to the Alcohol Advertising Policy (August 2026)
> - Update to Misleading ad design policy article (August 2026)
> - Update to Limited Ad Serving Policy (August 2026)
> - Update to Other restricted businesses: Government documents and services policy (October 2026)
> - Update to Masthead format requirements (September 2026)
> - Updates to the YouTube and Discover Feed ad requirements (August 2026)
> - Update to Gambling and Games Policy: Global (August 2026)
> - Update to Appeals Limits (July 2026)
> - Update to Cryptocurrencies and related products policy (August 2026)
> - Updates to AI labeling requirements (July 2026)
> …

来源：`_evidence/R1/google-ads-changelog-2026.md`
URL: https://support.google.com/adspolicy/topic/16794025?hl=en

**实测计数（本次用 `grep -c '^\- <http'` 直接数出）**：

| 年份 | Google Ads 政策更新条目数 | 来源文件 |
|---|---|---|
| 2024 | 68 | `_evidence/R1/google-ads-changelog-2024.md` |
| 2025 | 75 | `_evidence/R1/google-ads-changelog-2025.md` |
| 2026（截至抓取日 2026-09-15） | 58 | `_evidence/R1/google-ads-changelog-2026.md` |

【原文】（Amazon Ads 的政策变更台账，带「变更月份」列）

> Ad policy change log
> Updated on Apr 27, 2026
> All policies can be accessed from the Rules and policies page.
> Change title | Change summary | Link to policy page | Month of the change
> Clarification about review times being extended due to high submission volume. … This change updates the guidance about review times during periods of high submission volume including simultaneous submissions. … Amazon Ads policies and Ads content moderation … April 2026

来源：`_evidence/R1/amazon-ads-change-log-G8X8M375UPCN4UUC.md`
URL: https://advertising.amazon.com/help/G8X8M375UPCN4UUC

Amazon 台账的**逐月分布**（本次实测，`grep -o -E '(January|…) 20[0-9][0-9]' | sort | uniq -c`）：

| 月份 | 条目数 |
|---|---|
| January 2026 | 4 |
| February 2026 | 6 |
| March 2026 | 10 |
| April 2026 | 7 |
| October 2025 | 1 |

【判断】
- **量化结论**：Google Ads 年均 68–75 条政策变更，即 **约 5.7–6.3 条/月**；Amazon Ads 在 2026 年 1–4 月共 28 条，即 **7 条/月**。两条独立产线给出同一量级：**平台政策层的变更节奏是「每周 1–2 条」**。
- **这是本分片最重要的一个数字**，因为它把「规则库怎么维护」从一个态度问题变成一个容量问题：客户若要把主要平台的明文政策全部纳入，**每月需处理约 6–14 条变更**（按 Google + Amazon 两平台计）。对照客户现状（`01-内部证据-规则表现状审计.md`：21 条规则、12 字段、覆盖率 13.8%），**仅维持不落后就需要一个人近乎全职做变更侦测**。
- **一个诚实的观察（对客户有利）**：上表里绝大多数变更是**垂直类目政策**（Gambling 出现 4 次、Alcohol 2 次、Cryptocurrency 2 次、Healthcare and Medicines 多次）或**格式要求**（Masthead、Location asset、Message assets）。**母婴品线真正相关的条目占比很低。** 因此客户不需要「全量跟进」，需要的是一条**相关性过滤规则**。这把第 2 行的成本从「每月 12 条」压到「每月 0–2 条」。**这是本文给客户最省钱的单条建议。**
- **Amazon 台账本身可能是过期的**：该页标注 `Updated on Apr 27, 2026`，最后一条变更是 April 2026，而抓取日是 2026-09-15——**中间空了约 5 个月**。可能含义有二：(a) Amazon 确实暂停了公开台账更新；(b) 抓取到的页面是缓存/旧版本。**本次无法区分两者，故标注为不确定。** 但无论哪种，结论都成立：**「平台有 changelog」不等于「changelog 是活的」**——依赖 changelog 做变更侦测，必须先验证 changelog 自身的活跃度。这是 §3 的一个具体衰减案例。

【原文】（平台政策内部也有位阶：GitHub 用「第 1 条」的位置给法源让位）

> ## 1. Compliance with Laws and Regulations
>
> You are responsible for using the Service in compliance with all applicable laws, regulations, and all of our Acceptable Use Policies. These policies may be updated from time to time and are provided below.
>
> ## 2. User Safety
>
> We do not allow content or activity on GitHub that:
> * is unlawful or promotes unlawful activities;
> * is sexually obscene or relates to sexual exploitation or abuse, including of minors;
> * is libelous, defamatory, or fraudulent;
> * is discriminatory or abusive toward any individual or group;
> * is false, inaccurate, or intentionally deceptive information and likely to adversely affect the public interest (including health, safety, election integrity, and civic participation);
> …

来源：`_evidence/R7/github-docs-aup-src.md`（GitHub Acceptable Use Policies §1–§2）
URL: https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【判断】
- **位置即排序**：`Compliance with Laws and Regulations` 是**编号第 1 条**，在 User Safety（§2）、IP/Authenticity（§3）、Spam（§4）之前。而 §2 的第一项又是 `is unlawful or promotes unlawful activities`——**法源在 AUP 里出现了两次：一次作为独立条首，一次作为内容禁令的首项**。
- 这个双出现不是冗余，而是**两个不同功能**：§1 是**义务条款**（你的责任），§2 首项是**禁令条款**（我们禁止什么）。**规则库设计可直接照抄这个分工**：法源既要成为「你必须遵守」的元规则，也要成为「命中即拒」的判定条件。客户现有 21 条规则如果只有后者没有前者，就没有法律依据层。
- **对 §2.2「隐含排序」的意义**：这是本次找到的**最强的位置信号**——一个平台把法源放在自己全部内容政策之前，且它在 §1 里承认法源与政策并列。**这与 §2.1.1 的 `Except to the extent applicable law provides otherwise` 指向同一结论：法源在平台自己的文本结构里是被置于政策之上的。** 两处独立证据同向。

#### 1.2.3 平台实际判例（申诉结果）

**这是委托方最需要、也最容易被误解的一类。核心事实：写明文的政策，与平台实际执行的尺度，是两回事。**

**（a）机制上确实是两回事——平台公开承认申诉结果会推翻/修正判定**

Amazon 把申诉做成了一条独立产品链路，且**申诉的必填内容不是「我没有违反 X 条」，而是「根本原因 + 整改证据」**：

【原文】

> You can use the following guidelines to create your appeal:
>
> Be clear and concise. Be factual and direct. Focus on the facts and events that lead to the issue rather than introducing your product, business, or customer. Remove other questions or references to ongoing support cases from your submission. Avoid using emotive language.
>
> **Provide an explanation for all issues.** Some deactivations can be the result of a combination of issues; however, look for the root causes that led to the violations. For example, if there were unverifiable suppliers, inventory management issues, or quality control issues. Provide specific actions that you have taken to address the root causes, making sure to include specific actions, dates of changes, or documentation.
>
> **Include supporting evidence for all items.** Make sure you submit supporting evidence for all of the products or ASINs that are under review. You can find the list of products at the bottom of your original notification. Make sure to check the timeframe requested for the documents. Some products require invoices from the last 365 days.
>
> **Highlight areas in your supporting documents.** You can make your response more relevant by circling or highlighting the area within your documents that is most important. For example, you can highlight ASINs, supplier name, or supplier clauses with your terms and conditions.

来源：`_evidence/R1/amazon-appeal-questionnaire-reinstate-G201623610.md`
URL: https://sellercentral.amazon.com/help/hub/reference/external/G201623610

【原文】（申诉链路的入口与时限）

> To sell on Amazon, you must adhere to our performance metrics and policies. Failure to do so may lead to the temporary deactivation of your account, removal of listings, or limitations on your use of the Merchant Fulfilled Network.
> If your account has been deactivated or your listings have been removed, you can appeal for their reinstatement by following the steps below. If you believe the deactivation was an error, follow the instructions on the Account Health page for providing an explanation.
> …
> You may be asked to submit a questionnaire, acknowledge a violation, complete a quiz, or provide supporting documents.
> …
> After submitting your appeal, monitor your email for a decision from Amazon. If you have received a response from Amazon for more information, click View Appeal from Account Health to submit additional documentation and information required in your next submission. **Please expect a reply to your appeal within two days.**

来源：`_evidence/R1/amazon-appeal-restriction-removal-G200370560.md`
URL: https://sellercentral.amazon.com/help/hub/reference/external/G200370560

【判断】
- **申诉的判定标准不是「这条规则的字面」，而是「根本原因是否被消除」**。`look for the root causes that led to the violations` 与 `specific actions that you have taken to address the root causes` 说明：**平台实际执行的是一套「归因 + 整改」标准，而明文政策是一套「行为清单」标准。这两套标准不是同一套。**
- 这**正是**委托方问的「平台政策明文的 vs 平台实际执行的」不一致的机制性证据：**解释权归平台（`in our sole discretion`，见 §2.1.7），且解释的框架与政策文本的框架不同。** 一条商业规则「明文写了不能被拒」，实际仍可能被拒，因为判定者问的是「你的根因消除了没有」。
- `Please expect a reply to your appeal within two days` 给出了**判例产出的延迟下界 ≈ 2 天**。这意味着第 3 类来源在理论上是**日更**的——远快于平台政策的月更。**但它的萃取成本最高（§1.1 第 3 行），所以实际可用频率取决于客户有多少人力把申诉结果转成条目。**
- `You may be asked to … complete a quiz` 是一个值得注意的执行形态：**平台用测验来验证卖家是否真的理解了规则**。这与 R4 §2.2 里 GHC 标注手册的「30 题上岗考试」是同一机制——**「理解检查」被制度化了**。客户若要在内部推行规则库，可以照抄：让运营/设计过一遍规则测验，而不是发一份文档。

**（b）明文与实际执行不一致的第二个证据面：平台为「争议」单独立法**

npm 有一份**独立的争议解决文本**，与 ToS 分开：

【原文】（文件存在性证据）

> SOURCE_URL …

来源：`_evidence/R7/npm-disputes.txt`（file: npm Dispute Resolution Policy / npm disputes，15,756 bytes）
URL: npm 官方政策站点

【判断】
- 平台愿意为「争议」单独出一份政策，本身就说明**判定结果不能由主政策唯一确定**——否则不需要争议层。**「有争议层」＝「明文政策不足以决定个案结果」的制度化承认。**
- 本次未逐字抽取该文件正文（预算原因），**故本文不引用其具体条款**，只把它作为「机制存在」的指认，并在 §5 标注为待补。这是一个有意的**证据边界声明**，不是遗漏。

**（c）一个必须写明的限制**

本次调研中，**未能取得任何平台公开的、逐条的申诉结果台账**（即「某条广告因 X 被拒、申诉后改判」的结构化记录）。平台公开的是**申诉流程**（怎么申），不是**申诉统计**（申成了多少、依据是什么）。因此：

【判断】
- 第 3 类来源（平台实际判例）在客户侧**只能自建**，无法从平台获取。**「错题本」就是这项自建工作的产物**——这从来源分类的角度解释了 R4 为什么必须做错题本，而不只是「做了更好」。
- 可用的替代观测点：客户自己的**申诉记录与结果**（成功/失败 + 平台给的措辞）。这批数据是**唯一能反推平台实际尺度的私有资产**。若客户连这批数据都没有沉淀，第 3 类来源的萃取成本将从「高」变成「不可能」。


#### 1.2.4 品牌自定调性

**这一类在本次调研中有一个尴尬但重要的事实：客户当前的「品牌调性」并不是独立来源，它被混进了「专家经验」里。**

【原文】（客户现状：`依据来源` 字段只有两个取值）

> 现在 `依据来源` 只写「W1卖点表达边界（品线反馈2026-09-10 T4）」或「红绿灯.xlsx 规则库」。**没有一条规则能追到具体的错题。**

来源：`01-内部证据-规则表现状审计.md:306`（引用方为 R8-W1；该文件为委托方现状材料）
（同时见 `01-内部证据-规则表现状审计.md:29` 的 12 字段清单：`规则编号 | 边界类型 | 适用产品 | 风险等级 | 检测关键词 | 边界内容 | 判断方式 | 依据来源 | 启用状态 | 正则表达式 | 豁免词 | 触发原因`）

【判断】
- `品线反馈` 是**内部专家经验**（§1.2.7），`红绿灯.xlsx` 是**历史审计产物**。**品牌调性作为一个独立来源，在客户的字段体系里根本无处安放**——它要么被伪装成「品线反馈」，要么不存在。
- 这不是文案问题。品牌调性与专家经验的**衰减行为完全不同**：调性随品牌战略变（可预测、可版本化），专家经验随人员流动变（不可预测、会突然归零，见 §1.2.7）。**把两者塞进同一个字段值，等于放弃了分别追踪衰减的能力**，这正是 §3 要处理的问题。
- 本文的立场：**品牌调性是九类里唯一「客户自己 100% 拥有主权」的一类**。法源要服从、平台政策要跟、判例要猜、竞品不可信、投诉是信号、专家会走、数据只反映历史、KOL 有利益——只有品牌调性，客户说了算。**因此它应当承担「冲突时的最终裁判」角色之一**（见 §2.3），而不是被折叠进别的来源里。

**未找到**：本次未取得 Momcozy（或任何母婴品牌）成文的「品牌调性规范/内容手册」类文档。因此本类**无逐字原文可引**，以上均为基于客户现状字段的判断。这是一个**真实的证据缺口**，不是省略。

#### 1.2.5 竞品对标

**本文只写本类作为「规则来源」的属性，竞品的具体分析由 R5 分片负责（`R5-category-and-competitors.md`）。**

【判断】（本类的结构性缺陷，两条）
1. **竞品是负样本，不是正样本。** 竞品的广告能上线，只说明它**尚未被平台抓到**，不说明它**合规**。把它当规则来源，等于把「未被执法的违规」写进规则库。这是本类可信度被标为「低」的唯一理由，且这个理由**不可通过增加采样量修正**——采样再多也只测出「未被抓率」。
2. **竞品对标的正确用法是「反例库」而非「规则库」**。即：记录「竞品写了 X 且存活了 N 个月」，把它作为**风险偏好参数**的输入，而不是作为「允许 X」的依据。这与 R4 §4.1 的「反例必须是看起来像正例的」原则同构。

**未找到**：本次未取得任何平台或行业文档，说明「竞品实践可作为合规依据」。平台政策一律以「自方判定」为准，**没有任何一家平台承认「别人也这么做」是抗辩理由**。这是一个**有意的反向证据**：找不到支持，本身就是结论。

#### 1.2.6 客户投诉 / 差评

**本类是「风险信号」，不是「规则」。这个区分决定了它的萃取成本。**

【原文】（平台官方把用户举报列为第一位的规则输入源；此处引用 R4 已建立的对照表）

> | 输入源 | YouTube 官方表述（逐字） | Meta 官方表述（逐字） |
> | **用户/买家举报** | "flagged by our systems or people" | "before people report it to us" |

来源：`R4-trust-and-safety-ops.md` §1.4（原始逐字引文见该分片 §1.1 与 §1.2；**本文不重复其一手 URL**，以避免与 R4 的证据清单冲突）

【判断】
- 平台把「用户举报」放在输入源第一位，说明**它被当作探测手段而非判定标准**——`flagged by our systems or people` 的 `flagged`（被标记）与 `enforced`（被处置）是两个动作。
- **对萃取成本的含义**：一条差评不能直接变成一条规则，因为差评描述的是**症状**（「奶嘴有味道」），规则需要的是**可检测条件**（「文案中出现『无异味』的绝对化声称」）。**症状→条件的转换需要人**，这正是本类「萃取：半自动」的依据。
- **落地风险（必须写明）**：如果不做聚类去重，同一批用户对同一件事的抱怨会产生 N 条**互为重复**的规则。R4 §3.4「数据切片与隐藏分层」已给出同一警告的另一面：**未经分层的聚合会掩盖真实结构**。客户现有 21 条规则的规模还看不出这个问题，一旦接入投诉流就会立刻暴露。

#### 1.2.7 内部专家经验

**这一类是客户当前实际唯一在用的来源（见 §1.2.4 的 `品线反馈`），也是九类里衰减最不可预测的一类。**

【原文】（NIST 明确把「经验与专家判断」列为评分的合法依据）

> The term likelihood, as discussed in this guideline, is not likelihood in the strict sense of the term; rather, it is a likelihood score. Risk assessors do not define a likelihood function in the statistical sense. Instead, risk assessors assign a score (or likelihood assessment) based on **available evidence, experience, and expert judgment**.

来源：`_evidence/R8/nist-sp800-30r1.txt:4589-4591`（NIST SP 800-30 Rev.1，脚注 55；**加粗为本文所加**）
URL: https://csrc.nist.gov/pubs/sp/800/30/r1/final

【原文】（NIST 把「咨询领域专家」写成了流程中的一个正式步骤）

> Mission/business owners and mission/business subject matter experts can be consulted to obtain the most complete and up-to-date information on mission/business impacts. Other subject matter experts or stakeholder representatives can be consulted to obtain information on immediate versus future impacts (e.g., consulting the Privacy Office for impacts to individuals).

来源：`_evidence/R8/nist-sp800-30r1.txt:5102-5105`
URL: 同上

【原文】（⚠️ 但 NIST 同时给出了本类最严厉的警告）

> As in a quantitative approach, **rigor is significantly lessened when subjective determinations are buried within assessments**, or when significant uncertainty surrounds a determination of value.

来源：`_evidence/R8/nist-sp800-30r1.txt:1175-1177`
URL: 同上

【判断】
- **三句合起来给出本类的使用规则**：专家经验**合法**（第 1 句）、应当**被制度化地咨询而不是随手问**（第 2 句）、但**必须显式标注为「主观判断」而不能混进客观结论里**（第 3 句）。
- **对客户规则库的直接设计含义（不越界到 schema 设计，只说来源侧要求）**：`依据来源` 字段如果写「品线反馈」（见 §1.2.4），它**必须能区分出这是主观判断**。NIST 的警告说明：一旦主观判断被埋进看起来客观的条目里，整个评估的严谨性会显著下降。客户现在 `依据来源` 只写一个来源名、不写判断性质，**恰好是 NIST 警告的那种形态**。
- **本类的衰减特性（回填 §1.1「更新频率」列）**：专家经验**不随时间平滑衰减，而是在人员离职时阶跃归零**。这不来自任何引文，而是本文对该类结构的判断：因为经验**没有外部发布物**，所以它唯一的载体是人。§3 会给出对应的迁移建议。

#### 1.2.8 数据挖掘（从标注数据反推）

**这是九类里理论上最可自动化的一类——但本次调研未能取得可引用的算法一手证据。**

**证据状态声明（必须写明，否则会变成伪造引证）**：

- `_evidence/R8/rulefit-arxiv.txt`（文件头 `SOURCE_URL: https://arxiv.org/abs/0811.3652`，HTTP 200，38,937 bytes）**名实不符**：arXiv:0811.3652 的实际标题是 **"Polynomial Coefficient Enumeration"**（作者 Tewodros Amdeberhan、Richard P. Stanley，分类 `Mathematics > Combinatorics`，36 页）。全文 grep `rulefit|rule fit` 在 `.raw` 与 `.txt` 中**均为 0 命中**。
- 备用尝试 `arXiv:0811.3628` 亦非 RuleFit（实为 Ravikumar 等关于 ℓ1 惩罚对数行列式 / 图形模型的论文）。
- 真实来源（Friedman & Popescu, *Predictive Learning via Rule Ensembles*）两次抓取均失败：`https://statweb.stanford.edu/~jhf/ftp/RuleFit.pdf` → **HTTP 000**；`https://jerryfriedman.su.domains/ftp/RuleFit.pdf` → **60 秒超时被杀**。

**因此：本文不引用 RuleFit，也不引用任何具体算法。** 本类的属性判定只基于其**结构**，并明确标注为判断：

【判断】
- **可信度：中，且这个「中」有一个致命限定——它只反映历史，不反映应然。** 从标注数据反推出的规则，描述的是「过去被怎样判过」，不是「应该怎样判」。当平台政策或法源已经改变而标注数据尚未覆盖新政策时，**数据挖掘会稳定地给出过期的正确答案**。这是本类与第 1、2 类的根本冲突面（见 §2.3）。
- **这是九类中唯一「萃取可自动化」的一类**（§1.1 表第 8 行）。但自动化产出的不是规则，是**候选规则**。理由同上：算法无法区分「历史一致」与「规范正确」。
- **本类的真正价值在冷启动**：当客户没有专家、没有案例、没有成文调性时（这正是客户现状），历史记录是**唯一存在的数据**。它能给出「我们过去实际在管什么」的基线，这个基线可以用来**校准**其他来源，而不是替代它们。
- 客户现有的 `291 条广告记录`（见 R4 §1.4 表格末行）与 `红绿灯.xlsx` 是这条路径**唯一可用的原料**。R4 §3 全域（误差分析、主动学习、数据切片）讲的就是怎么把这份原料变成条目。**本文不重复。**

#### 1.2.9 KOL / 代理商反馈

**本类在本次调研中完全没有取得可引用的一手文本。如实记录。**

**未找到**：
- 未找到任何平台或标准文档，把「KOL / 代理商反馈」列为规则来源类。
- 未找到任何关于代理商反馈如何进入规则库的流程描述。
- 未取得任何 KOL/代理商合同、简报或反馈模板。

【判断】（在无证据情况下，只写结构性的、可自证的推理，并标注为判断）
- **利益方向是明确的**：代理商的收入与「投放通过率」正相关，KOL 的收入与「内容自由度」正相关。因此本类在冲突中的**系统性偏置方向是放宽**。这不是道德判断，是激励结构判断。
- **同类结构在证据中的对应物**：`R4-trust-and-safety-ops.md` §1.4 把「NGO / 公益组织」「政府/监管机构」「专业机构（卫生权威）」「外部专家委员会」列为平台的独立输入源。**注意平台为这些来源单列了渠道，而没有为「代理商」单列。** 这是一个**位置性的负面信号**：平台承认外部输入，但承认的是**无利益冲突的那几类**。
- **对客户的建议落点**：如果客户要用这一类，它应当被归入「§1.2.6 客户投诉」同一处理层（**信号，不是规则**），而不是与法源/平台政策并列为规则来源。原因是：它的价值在于**提前知道市场会怎么反应**，不在于**决定什么是对的**。

**与 §2.3 的衔接**：正因为本类无证据且激励方向明确，它在 §2.3 推荐的优先级里被放在**最底层且只作为「触发复审」的信号**，不参与规则判定。


---

## 2. 冲突优先级

### 2.1 显式优先级声明（原文证据）

**结论先行：找到了。** 下面四类显式声明都是真实存在于证据文件里的字符串，不是推论。

#### 2.1.1 声明 A：法源 > 平台政策（「合同让位于法律」条款）

这是最强的一条。GitHub ToS 的准据法条款里有一个让步从句，它把「法律」放在「本协议」之上：

【原文】

> Except to the extent applicable law provides otherwise, this Agreement between you and GitHub and any access to or use of the Website or the Service are governed by the federal laws of the United States of America and the laws of the State of California, without regard to conflict of law provisions. You and GitHub agree to submit to the exclusive jurisdiction and venue of the courts located in the City and County of San Francisco, California. However, any claim for injunctive relief with respect to a violation of section D.9 may be brought in any jurisdiction.

来源：`_evidence/R7/github-terms-of-service.txt:773`
URL: https://docs.github.com/en/site-policy/github-terms/github-terms-of-service

【判断】
- `Except to the extent applicable law provides otherwise` 是一个**显式的效力位阶让步**：平台自己的协议承认，当法律另有规定时，协议不适用。这就是「法源 > 平台政策」的最干净的一手表述。
- 注意它同时暴露了另一层：同一句里的 `without regard to conflict of law provisions` 说明平台**不打算**为客户所在司法辖区的法律冲突买单 —— 平台选择的是「美国联邦法 + 加州法」单一锚点。对客户的实践含义是：**平台政策层永远只锚定一个法域，而客户品牌的法源义务可能横跨多法域**，两者的冲突不会由平台帮你解决（详见 §2.3 的「法域错配」问题）。
- 本条只解决「协议 vs 法律」，**没有**解决「法律 vs 法律之间」「平台政策 vs 品牌调性」的排序。不要把这一条过度外推。

#### 2.1.2 声明 B：法源与平台政策并列，且法源写在前面（共享句式）

GitHub AUP 与 PyPI AUP 出现了**几乎逐字相同的一句话**，而且都是各自 AUP 的第一条实质内容：

【原文】（GitHub）

> ## 1. Compliance with Laws and Regulations
>
> You are responsible for using the Service in compliance with all applicable laws, regulations, and all of our Acceptable Use Policies. These policies may be updated from time to time and are provided below.

来源：`_evidence/R7/github-docs-aup-src.md`（GitHub AUP §1），另见 `_evidence/R7/github-acceptable-use.txt`
URL: https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【原文】（PyPI）

> You are responsible for using PyPI in compliance with all applicable laws,
> regulations, and all of our Acceptable Use Policies. These policies may be
> updated from time to time and are provided below, as well as in our
> [Terms of Use](../Terms-of-Use/). You must not engage in activity
> that significantly harms other users. We will interpret our policies and
> resolve disputes in favor of protecting users as a whole.

来源：`_evidence/R7/pypi-aup.txt:225-231`
URL: https://pypi.org/policy/acceptable-use-policy/

【判断】
- **两个互不相关的平台用了同一句式**，说明这不是某一家法务的偶然措辞，而是一个在平台治理圈里流通的模板句。这一点对客户很重要：**客户的规则库如果以「平台政策」为唯一来源，它在结构上就是「二手转述的法源」**——平台自己都在 §1 承认法源是第一性的，平台政策只是把它转译了一遍。转译会丢失细节，这就是 §2.3 推荐「法源直达」的依据。
- 两者都把法源与政策**并列在同一个列表**（`applicable laws, regulations, and all of our Acceptable Use Policies`），而不是分层。句法上的并列**不等于**效力上的平等——因为 §2.1.1 的让步条款已经把法律抬到协议之上了。**读者必须靠跨条款拼合才能得到真实位阶，单看本条会误判为「三层平权」。**

#### 2.1.3 声明 C：冲突时「更具体者优先」（特异性原则）

这是全部证据里**唯一一条明确写出的、用于解决条款之间冲突的规则**：

【原文】

> Occasionally, websites owned by GitHub may provide different or additional terms of service. If those additional terms conflict with this Agreement, the more specific terms apply to the relevant page or service.

来源：`_evidence/R7/github-terms-of-service.txt:343`
URL: https://docs.github.com/en/site-policy/github-terms/github-terms-of-service

【判断】
- `the more specific terms apply` 是**特异性优先（lex specialis）**的显式声明。它解决的是「总则 vs 分则」，不是「法源 vs 平台政策」。
- **但它仍然是本次调研里最可迁移的一条规则**：客户要建的是一套跨来源的规则库，而跨来源冲突的本质恰恰是「谁的适用范围更具体」。GitHub 给出的答案是可用的落点——**当两条规则冲突且都不是绝对上位来源时，比较适用范围的具体度，具体者胜**。
- 边界：这条只出现在 GitHub 的 ToS 里，**没有**在 AWS AUP、npm ToS、PyPI AUP、AMO 政策中找到对应表述（见 §4 grep 记录）。因此它是「一家之言」，不是行业普遍声明。

#### 2.1.4 声明 D：模糊时的价值取向兜底（解释规则，非位阶规则）

PyPI 在同一段里给了一条**冲突无法靠位阶解决时**的兜底：

【原文】

> We will interpret our policies and resolve disputes in favor of protecting users as a whole.

来源：`_evidence/R7/pypi-aup.txt:230-231`
URL: https://pypi.org/policy/acceptable-use-policy/

【判断】
- 这是**解释规则（rule of construction）**而非效力位阶：它不说谁压谁，它说**当条文可两解时，往保护用户整体的方向解**。
- 对客户规则库的直接价值：客户抱怨「新场景没有规则」（见 `01-内部证据-规则表现状审计.md` 覆盖率 13.8%）时，需要的正是这种兜底句。有了它，「没规则」就不再等于「无法裁决」——**可以从一条默认价值取向推出临时判定**，然后把该判定作为候选规则入队。这为另一 agent 负责的「空白处理」提供了一条有出处的依据（本文不展开）。
- 注意 PyPI 用的是 `our policies`——**它只承诺对自己的政策如此解释**，不承诺对法源如此解释。

#### 2.1.5 声明 E：合规意图作为减轻情节（执行层的软排序）

AWS AUP 在执行段写了一条**不改变位阶、但改变后果**的规则：

【原文】

> When determining whether there has been a violation of this Policy, we may consider your ability and willingness to comply with this Policy, including the policies and processes you have in place to prevent or identify and remove any prohibited content or activity.

来源：`_evidence/R7/aws-aup.txt:285`
URL: https://aws.amazon.com/aup/

【判断】
- 这条把「你有没有流程」变成了**判定输入**。它不排序来源，但它排序**后果**：同样违规，有预防/识别/移除流程的一方，被从轻认定的概率更高。
- 对客户的含义：规则库不只是「判什么违规」，还需要能**举证自己有一套流程**。这与 R4 分片里错题本/规则生命周期的作用互相咬合（`R4-trust-and-safety-ops.md` §1-§3）。

#### 2.1.6 未找到的显式声明（边界，必须写明）

**未找到**任何一家平台或品牌，用一句话显式写出完整的多来源优先级全序，例如「法源 > 平台政策 > 品牌调性 > 竞品 > 投诉 > 专家经验」。具体 grep 记录：

- 在 `R7/amo-addon-policies.txt` 中检索 `priorit|precede|precedence|take priority|supersede|in the event of|conflict|applicable law` → **0 命中**。
- 在 `R7/aws-aup.txt` 中检索同一组词 → **0 命中**。
- 在 `R7/npm-terms-of-use.txt` 中检索 `conflict|precedence|order of|supersede` → 仅 1 条无关命中（`Use of npm's trademarks is governed by our`）。
- 在 `R7/shopify-legal-index.txt`、`R7/npm-disputes.txt` 中检索同一组词 → **0 命中**。

【判断】
- 平台不写全序是**理性策略**而非疏漏：一旦写出全序，就等于把自己锁死在无法覆盖未来情形的位阶表上；保留「更具体者优先」+「法律优先」+「按用户整体利益解释」三条**局部规则**，成本更低、适应性更强。
- 因此客户的调研问题「冲突时谁压谁」**不可能靠抄平台政策回答**，必须自己立法。§2.3 给出建议。

#### 2.1.7 一条跨系统的法源指名（把 FTC 直接写进平台政策）

PyPI 在促销条款里**直接指名了一个具体法源**，而不是笼统说「遵守法律」：

【原文】

> If you decide to post any promotional materials in your Account, you are solely responsible for complying with all applicable laws and regulations, including without limitation the U.S. Federal Trade Commission's Guidelines on Endorsements and Testimonials. We reserve the right to remove any promotional materials or advertisements that, in our sole discretion, violate any PyPI terms or policies.

来源：`_evidence/R7/pypi-aup.txt:267-272`
URL: https://pypi.org/policy/acceptable-use-policy/

【判断】
- 这是一个**平台把法源具体化为可执行条款**的实例：它没有停在「遵守法律」，而是点名 `FTC's Guidelines on Endorsements and Testimonials`。本文证据中同一份 FTC 指南的一手文本就在 `_evidence/R8/ftc-com-disclosures.txt` —— **平台政策层与法源层在这里是对齐的，不是冲突的**。
- 反向读：`in our sole discretion` 表明即便引用了法源，**最终判定权仍归平台**。所以「法源 > 平台政策」在**立法**层面成立（§2.1.1/§2.1.2），在**裁决权**层面并不成立。这是本次调研最重要的区分之一，也是 §2.3 推荐规则的核心。
- 该指南相关的更多一手内容见 `_evidence/R8/ftc-com-disclosures.txt`（FTC 广告披露指南）。


### 2.2 从系统行为反推的隐含排序

§2.1.6 已确认：**没有一家平台公布完整的多来源优先级全序。** 但系统的**行为**会泄露它的排序。下面四条是从「条款位置」「措辞顺序」「严重等级算法」「管辖权让渡」四种不同机制反推出的同一结论。

#### 2.2.1 证据面 A：位置与措辞顺序（法源在平台文本里被放在最前）

已见 §1.2.2 的 GitHub AUP 结构。补充一条**措辞内部的顺序**：

【原文】（GitHub）

> You are responsible for using the Service in compliance with all applicable **laws, regulations, and all of our Acceptable Use Policies.**

【原文】（PyPI）

> You are responsible for using PyPI in compliance with all applicable **laws, regulations, and all of our Acceptable Use Policies.**

（来源同 §2.1.2）

【判断】
- 两处独立来源，均为 `laws, regulations, and [policies]`。**法源永远在并列结构的前项，平台政策在末项。** 在英文法律起草惯例中，并列项的排序承载效力暗示（同类条款中越靠前越基础）。
- 叠加 GitHub AUP 的 **§1 编号位置**（见 §1.2.2），形成**双重同向信号**：既排在最前，又是第 1 条。
- **可信度评估**：这是**弱证据**（措辞顺序不具法律效力），但它是**四个证据面中唯一在两个独立平台上重复出现的**。因此本文不把它当决定性证据，只当**佐证**。

#### 2.2.2 证据面 B：平台自认「政策不是法律的替代品」（最强的一条）

这一条比位置证据强得多，因为它是**平台主动声明自己低一档**：

【原文】

> Our policies are designed to help advertisers connect with their audiences, while providing customers with high quality, trustworthy ads. **It's your responsibility as an advertiser to make sure that your ads comply with all applicable laws, rules, regulations, and industry standards in the geographical areas where your advertisements appear. Our policies aren't legal advice.** It's your responsibility to consult with legal counsel if you have questions about the laws and regulations concerning your ads.

来源：`_evidence/R1/amazon-ads-policies-G5RLASA28TP9TFXZ.md:38`（**加粗为本文所加**）
URL: https://advertising.amazon.com/help/G5RLASA28TP9TFXZ
（页面自标 `Updated on Sep 2, 2026`）

【判断】
- `Our policies aren't legal advice` 是**平台明确否认自己的政策可以替代法源**。这是本次调研中**支持「法源 > 平台政策」的最强单句**——它不需要读者从位置去推测，平台自己说了。
- **注意这里列了四层，不是三层**：`laws, rules, regulations, and industry standards`。**`industry standards`（行业标准）被平台与法规并列**。这对客户的直接含义：客户所属行业（母婴/泌乳/医疗器械）的专业标准，**在平台上是被与法规同级提及的**，不是软性参考。这与 §1.2.7 的「咨询专业机构（IBCLC、泌乳医学会）」形成闭环——R4 §1.4 表格里 Momcozy 的「专业机构」一行标注为「⚠️ 有 U01 规则，但无证据链」，本句给出了它应有的位置：**不是可选加分项，是被平台点名的一层**。
- `in the geographical areas where your advertisements appear` 是**显式的地域作用域声明**。与 §2.1.1 的 `governed by the federal laws of the United States` 指向同一事实：**平台政策是全局单一版，法源义务是逐法域分裂的**。这个错配是 §2.3 要处理的核心问题之一。
- **但紧接着的一句必须同时读**（同一页，同一天更新）：

【原文】（同页，判定权归属）

> Amazon reserves the right to reject, remove, or require modifications to ads that don't meet its policies, **at its sole discretion**.

来源：`_evidence/R1/amazon-ads-policies-G5RLASA28TP9TFXZ.md:42`
URL: 同上

【判断（本节最关键的一条推论）】
- **把两句合起来读，得到本分片最重要的结构性结论：**
  - **立法层（谁定对错的标准）：法源 > 平台政策。** 依据：`Our policies aren't legal advice` + `applicable laws, rules, regulations, and industry standards` + §2.1.1 的 `Except to the extent applicable law provides otherwise`。
  - **裁决层（谁说了算）：平台 > 一切。** 依据：`at its sole discretion` + §2.1.7 的 PyPI `in our sole discretion`。
- **这两层不矛盾，且必须分开建模。** 客户的规则库如果把两层混在一起（比如写成「依法判定」），就会在申诉时用错语言——**申诉时你不能说「按法律我不违规」，你得说「我的根因已消除」**（依据 §1.2.3 的 Amazon 申诉指南 `look for the root causes`）。
- **这解释了委托方困惑的根源**：他们问「冲突时谁压谁」，隐含假设是**一个**排序。真实答案是**两个排序，分属立法层与裁决层**。这是本文对客户最有价值的一条澄清。

#### 2.2.3 证据面 C：严重等级算法把「是否违法」当作独立的加重轴

这是**行为证据**——不是措辞，是算法的实际输入。

【原文】（Amazon Account Health Rating 的 severity 判定因子）

> To calculate your AHR, we assign a certain number of points to each policy violation based on the severity of the violation. There are four severity levels: critical, high, medium, and low. Critical violations are the most serious violations, which can lead to immediate account enforcement. **When determining the severity, we consider factors including the degree to which the violation negatively impacts the customer experience and whether the policy violation contravenes applicable laws and regulations.**

来源：`_evidence/R1/amazon-ahr.md:52`（**加粗为本文所加**）
URL: https://sellercentral.amazon.com/help/hub/reference/external/G200205250（文件头 `source:` 字段标注）

【原文】（同制度的 FAQ，逐级定义）

> Critical: Violations of this severity have a serious and unacceptable impact on customers, **or violate certain laws, regulations, or the rights of others**. Any single violation with this severity immediately qualifies your account for deactivation.
> High: Given the negative impact these violations have on customers, **or the degree to which they may also violate applicable laws or regulations**, our tolerances for high severity violations are minimal.
> Medium: Violations of this severity may significantly undermine customer and sellers trust if they continue to occur over time.
> Low: We tolerate infrequent low severity violations because we understand that mistakes happen in the course of doing business.

来源：`_evidence/R1/amazon-ahr-faq-GR786P4BPEVKTBAG.md:84`
URL: https://sellercentral.amazon.com/help/hub/reference/external/GR786P4BPEVKTBAG

【判断】
- **Amazon 的 severity 有两个独立轴：(1) 对客户体验的损害，(2) 是否违反法律法规。** 两个 `or` 说明**任一轴单独成立即可升级**。
- **这就是隐含排序的行为证据**：如果平台认为自己的政策与法源平权，就不需要把「是否违法」单列为一个**独立的加重因子**。**把它单列，等于承认法源是比自身政策更高一档的严重性来源。**
- **⭐ 对客户规则库的可迁移结论（本文范围内，不涉及定档）**：一条规则的**来源类决定了它能沿哪个轴升级**——
  - 来自**法源**的规则 → 可同时沿「客户体验」与「违法」两轴升级；
  - 来自**平台政策**的规则 → 主要沿「客户体验」轴升级；
  - 来自**品牌调性**的规则 → **只能沿「客户体验」轴**，且客户体验的定义权在平台手里。
  - 因此：**同样是「严重」，来自法源的严重与来自品牌调性的严重不是同一种严重。** 这一条直接交给负责「严重等级定档」的分片使用（本文不展开定档逻辑，按边界要求）。
- **一条必须同时记录的动态性**（对 §3 直接相关）：

【原文】

> We may change the severity of a violation if we observe changes in the degree to which that violation affects customers or other sellers.

来源：`_evidence/R1/amazon-ahr-faq-GR786P4BPEVKTBAG.md:90`
URL: 同上

【判断】→ **严重等级本身是可被平台单方重新校准的。** 这意味着客户规则库里任何硬编码的等级都会过期，且**过期不来自政策文本变更，而来自等级校准**——后者通常不发 changelog。这是 §3 讨论的一种隐蔽衰减。

#### 2.2.4 证据面 D：平台对知识产权类主动让渡管辖权（法源接管）

【原文】

> npm does not resolve squatting claims on demand. We do not transfer package, organization, or username ownership simply because another user wants the name. If you believe a name infringes a trademark or other intellectual property right you own, please follow the formal name dispute process on GitHub - **that is the only path we act on.**

来源：`_evidence/R7/npm-disputes.txt:505-507`（**加粗为本文所加**）
URL: https://docs.npmjs.com/policies/disputes
（HTTP 200 已核，见 `_evidence/R7/_fetchlog.tsv`：`2026-09-14T18:28:20Z npm-disputes ... 200 502762 try1`）

【判断】
- `that is the only path we act on`（**这是我们唯一受理的路径**）是**平台显式放弃自行裁决、把该来源类整体路由到正式法律程序**。这是本次找到的**唯一一条「平台承认某来源类的判定权不在自己手上」的原文**。
- 与 §2.2.2 的 `at its sole discretion` 形成**有意义的例外**：平台并非对所有类都主张专属裁量权。**它按来源类分别声明裁量权**——这是「来源分类学」在平台侧真实存在的证据。
- **反推的隐含排序（本条的落点）**：`法源（IP/商标）> 平台政策`，且这个让渡是**强制且排他**的（`only path`）。对比 §2.2.3，法源在 Amazon 那里是**加重因子**，在 npm 这里是**排他路径**。**两种机制不同，方向一致。**
- **对客户的操作含义**：客户的规则库里应当有一类规则是**「不在平台申诉，直接走法律/知识产权渠道」**。这类规则不能混进普通审核队列——因为对它们而言，平台审核根本不是裁决者。

#### 2.2.5 反推出的隐含排序（汇总）

【判断】综合 A–D 四个证据面，本文反推的隐含排序如下。**标注「强度」是为了让读者知道哪一条可以拿去跟法务讲、哪一条只能内部用。**

| 层 | 排序 | 证据面 | 强度 | 依据 |
|---|---|---|---|---|
| **立法层** | **法源 > 平台政策** | B（平台自认政策非法律建议） | **强**：平台主动声明 | `Our policies aren't legal advice`；`Except to the extent applicable law provides otherwise` |
| 立法层 | **法源 > 平台政策** | D（IP 类管辖权让渡） | **强**：`only path we act on` | 同上 |
| 立法层 | **法源 > 平台政策** | C（违法作为独立加重轴） | **中**：算法行为证据 | AHR severity 双轴 |
| 立法层 | **法源 > 平台政策** | A（位置与措辞顺序） | **弱**：起草惯例 | `laws, regulations, and [policies]`；AUP §1 |
| **裁决层** | **平台 > 一切（除让渡类）** | B + D | **强** | `at its sole discretion`；`in our sole discretion`；但 IP 类例外 |
| **执行层** | **「有流程」> 「无流程」** | §2.1.5 | **中** | AWS `we may consider your ability and willingness to comply … including the policies and processes you have in place` |
| 同层内 | **具体者 > 一般者** | §2.1.3 | **弱**：仅 GitHub 一家 | `the more specific terms apply` |
| 无法裁决时 | **回落价值取向** | §2.1.4、§1.2.1 | **中**：两处独立来源同构 | PyPI `in favor of protecting users as a whole`；FTC `select the method more likely to effectively communicate` |

### 2.3 推荐的优先级规则 + 依据

**本节是本文对委托方问题的正面回答。每条规则后面标注它引用的证据；凡无证据支撑的设计选择，明确标注为「本文建议」。**

#### 2.3.1 核心设计：把「一个排序」拆成「三层 + 一个兜底」

§2.2.5 已证明真实系统里存在**两个不同性质的排序**（立法层、裁决层）。因此推荐的不是一条全序，而是**三条各自独立、可分别执行的规则**：

**规则 1（立法层，效力位阶）**

> **法源 > 平台政策 > 品牌调性 > 其他所有来源。**
>
> 且：**当法源与平台政策冲突时，以法源为准，但必须以平台可接受的形态呈现。**

- 依据：§2.2.2（`Our policies aren't legal advice`）、§2.1.1（`Except to the extent applicable law provides otherwise`）、§2.2.3（违法为独立加重轴）。
- **第二条限定语是本文的关键补充，且它是从证据里推出来的，不是发明**：§1.2.3 的 Amazon 申诉指南要求 `look for the root causes`，§2.1.7 的 `in our sole discretion` 说明判定权归平台。**所以「以法源为准」是内部判定标准，对平台沟通时必须翻译成「根因已消除」。** 直接对平台讲法条，不构成有效的申诉语言。
- **规范化的理由（为什么不是品牌调性排第二）**：品牌调性若高于平台政策，会导致规则库指导业务去违反平台政策，而平台**有能力单方封店**（`at its sole discretion`）。品牌调性只在自己拥有裁决权的范围内（自有站点、自有物料）可以高于平台政策。**因此规则 1 的全序需要加一条例外，见规则 1b。**

**规则 1b（位阶的例外：裁决权属地原则 —— 本文建议，无直接引文）**

> **排序只在「谁拥有最终裁决权」的范围内有效。**
> - 平台店铺 / 平台广告 / 平台素材 → 裁决者是平台 → **平台政策 > 品牌调性**（且平台的 `sole discretion` 高于一切）。
> - 自有站点 / 自有私域 / 线下物料 → 裁决者是客户自己 → **法源 > 品牌调性 > 平台政策**（平台政策在此降为参考）。
>
> 依据：`at its sole discretion`（§2.2.2）与 npm 的 `only path we act on`（§2.2.4）共同证明「平台按场景声明裁量权」；本规则的**具体切分方式**是本文建议。
> **这条解决委托方最实际的痛点**：同一个素材，发在 Amazon 详情页和发在自有 DTC 站点，适用的是**不同的排序**。用一条规则覆盖两个场景必然出错。

**规则 2（裁决层，沟通与举证）**

> **申诉/沟通时，不引用位阶，只引用「根因 + 整改 + 举证」。**
>
> 依据：§1.2.3 的 Amazon 申诉指南原文（`look for the root causes` / `specific actions` / `dates of changes, or documentation` / `Highlight areas in your supporting documents`），以及 §2.1.5 的 AWS `we may consider your ability and willingness to comply … including the policies and processes you have in place`。
> **推论**：规则库**必须能输出「根因」和「流程证据」**，不只是输出「违规/不违规」。这决定了错题本不能只存案例，还要存**根因分类与整改动作**——与 R4 §3.5「一条错误 = 一行结构化记录 + 一个处置码」的要求一致。

**规则 3（兜底，无法裁决时）**

> **当所有来源都无明文、或两条同层来源冲突时，回落到一条书面的价值取向句，而不是「暂不判定」。**
>
> 依据：§2.1.4 PyPI `We will interpret our policies and resolve disputes in favor of protecting users as a whole`；§1.2.1 FTC `There is no litmus test … the best practice would be to select the method more likely to effectively communicate the information in question`。**两处独立来源给出同一结构（位阶失效 → 回落取向），这是本文认为兜底句必须存在的论据。**
> **客户必须自己做的一件事**：写一句自己的兜底句。本文**不建议直接抄 PyPI 或 FTC 的**——理由见 §1.2.1 的判断：这两句取向不同（保护用户 vs 有效沟通），**兜底句是价值选择，抄错了会把别人的价值观变成自己的默认判定。**
> 对母婴品类的**建议取向（本文建议，无引文）**：偏向「保护使用者（婴幼儿与哺乳期母亲）」，而不是偏向「有效沟通」或「保护消费者整体」。理由是 FDA 与 FTC 在母婴/健康类目上的监管取向更接近前者，且与 §1.2.1 指出的 FDA 缺口同向。

#### 2.3.2 九类来源在推荐排序中的落位（与 §1.1 表逐行对应）

【判断】下表的落位均为本文根据 §2.1/§2.2 证据的推论，**除标注外无直接引文**。

| 层 | 来源类 | 可否作为判定依据 | 可否作为严重性加重 | 说明 |
|---|---|---|---|---|
| **第 1 层：法定** | 1 法源 | ✅ 是（最高） | ✅ 可（§2.2.3 独立轴） | 冲突时以此为准 |
| **第 2 层：平台强制** | 2 平台政策（明文） | ✅ 是 | ✅ 可（客户体验轴） | 裁决权在平台 |
| **第 2 层：平台强制** | 3 平台实际判例 | ⚠️ **仅作校准，不作依据** | ⚠️ 间接 | 只反映实然，不反映应然；用于修正对政策的理解 |
| **第 3 层：自主** | 4 品牌调性 | ✅ 是（自有渠道内最高） | ✅ 可（自有渠道内） | 唯一客户拥有主权的一类（§1.2.4） |
| **第 4 层：信号** | 6 客户投诉 / 差评 | ❌ **不作依据** | ✅ 可（升级触发） | 症状非条件（§1.2.6） |
| **第 4 层：信号** | 9 KOL / 代理商 | ❌ 不作依据 | ❌ 否 | 激励方向系统偏宽松（§1.2.9） |
| **第 5 层：校准** | 7 内部专家经验 | ⚠️ 可，但**必须标注为主观判断** | ⚠️ 可 | 依据 NIST 警告（§1.2.7） |
| **第 5 层：校准** | 8 数据挖掘 | ⚠️ 仅产出**候选**规则 | ❌ 否 | 只反映历史（§1.2.8） |
| **不入层：反例** | 5 竞品对标 | ❌ 不作依据 | ❌ 否 | 负样本，入反例库（§1.2.5） |

**三条读表要点**：

1. **只有第 1、2、3 层产出「判定依据」**；第 4、5 层产出的是**信号与候选**。这个区分是本文对「九个来源要不要平等对待」的明确回答：**不平等，而且不是按权威度不平等，是按「是否产出可判定条件」不平等。**
2. **第 3 类（平台实际判例）被放在第 2 层却不是依据**，这是本表最反直觉的一格。理由：它对**理解**平台尺度极有价值，对**立法**没有价值——因为它永远是特定个案的、且平台保留改判权（`We may change the severity`，§2.2.3）。**它是校准器，不是标准。**
3. **第 7、8 类的「校准」含义不同**：第 7 类校准**判定边界的松紧**（专家说这条太严了），第 8 类校准**覆盖面的盲区**（数据显示某类内容从未被审过）。两者都不应直接产生规则。

#### 2.3.3 三个必须回答的冲突场景（推演）

【判断】以下三条均为本文基于上述证据的推演，用于让规则可执行。

**场景 1：法源允许，平台政策禁止。**
→ 以平台政策为准（因为裁决者是平台，`at its sole discretion`）。**但在规则库中同时标注「法源允许」，以便在自有渠道放行、并在申诉时准备法律依据。**
→ 依据：规则 1b + §2.2.2。
→ 典型实例：同一句功效声称在某些法域合法，但平台政策全面禁止（参见 `_evidence/R1/amazon-prohibited-product-claims-G202024200.md` 与 `amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.md` 所列的声称substantiation 要求——**本文未逐字核这两份文件，仅作定位提示，不作为引证**）。

**场景 2：平台政策允许，法源禁止。**
→ 以法源为准，**不上**。这是唯一一个「平台允许也不能做」的场景。
→ 依据：§2.1.1 `Except to the extent applicable law provides otherwise`；§2.2.2 `Our policies aren't legal advice`。
→ **这是客户最需要提防的场景**，因为平台不会替他们拦——平台已明说政策不是法律建议。

**场景 3：品牌调性比平台政策更严（品牌自愿加严）。**
→ **允许，且推荐。** 平台政策是**地板不是天花板**。
→ 依据：本次**未找到**任何平台的「地板非天花板」明文表述（已在 §2.1.6 记录 grep 结果 0 命中）。**但反证成立**：平台从未声明「不得比本政策更严」，且 §2.2.2 明确把 `industry standards` 与法规并列、把合规责任完全推给广告主。**因此加严在结构上无风险，放宽才有风险。**
→ **本文建议的默认立场**：品牌规则**只允许比平台更严，不允许更松**。这条建议的依据是**风险不对称**：加严的代价是投放量，放宽的代价是封店。两者不可比。

#### 2.3.4 一句话回答委托方

> **规则库不需要「一个」优先级，需要「三层位阶 + 一条兜底」：法源 > 平台政策 > 品牌调性；同层冲突比适用范围具体度；无法裁决时回落一句自己写的价值取向。**
> **且必须知道：位阶只用于内部判定，对平台的唯一有效语言是「根因已消除」。**


---

## 3. 来源可信度衰减与版本迁移

本章回答委托方最实际的一组问题：**规则写下来之后会过期吗？过期了怎么办？旧的怎么迁？**

**核心结论（一句话）**：**衰减速度由来源类决定，且各类的「过渡期」长短本身就是平台/法源给出的隐含优先级。法源类过渡期可达 0 天，平台政策类约 30 天，法源自身的生效期最长可达 38 个月。**

### 3.1 过渡期是分级的——这是本章最强的量化证据

【原文】（法源类：零过渡期）

> If you're based in a location that's recently become subject to OFAC sanctions, your Google Ads account will be suspended. Manager accounts based in embargoed countries or territories will be suspended, and their managed accounts may also be suspended.
>
> If your account is affected by OFAC sanctions, we'll notify you by email when we suspend your account. **No grace periods or exceptions are possible.**

来源：`_evidence/R1/google-ads-country-restrictions-6163740.md:27`（**加粗为本文所加**）
URL: https://support.google.com/google-ads/answer/6163740

【原文】（平台政策类·高危：3 天）

> What happens if I incur a critical violation?
>
> When we detect a critical violation, we will notify you of the violation via your Account Health page and email. Your AHR will turn red and reflect a numeric score of zero. **You will have a three-day grace period to address the violation before account deactivation.**

来源：`_evidence/R1/amazon-ahr-faq-GR786P4BPEVKTBAG.md:121`（**加粗为本文所加**）
URL: https://sellercentral.amazon.com/help/hub/reference/external/GR786P4BPEVKTBAG

【原文】（平台政策类·新规上线：约 30 天，且到期自动迁移）

> **[April 2025] Updates to Course requirements**: Starting April 30, 2025, our new Courses Policy requires that content featured in a YouTube Course must have 1) an intent to teach, 2) consist of at least three non-repeating videos from the Course owner's channel, and 3) contain no [age-restricted content]. **Courses that don't meet these criteria may be automatically converted to standard playlists within 30 days of this policy update.**

来源：`_evidence/R1/youtube-policy-updates.md:275`（**加粗为本文所加**）
URL: https://support.google.com/youtube/answer/10008196

【原文】（平台政策类·另一例：提前约 1 个月公告生效日）

> **[May 2023] Updates to YouTube Partner Program reapplication policy:** Starting June 5, 2023, we're extending our policy on reapplications to the YouTube Partner Program (YPP) from 30 days to 90 days. This means that channels that have been suspended or rejected more than once from YPP must now wait 90 days before reapplying to the program. If it's your first time being rejected from YPP, you can still reapply after 30 days, but if you're rejected again you need to wait 90 days before reapplying. This change doesn't affect our appeal policy and channels will still have 21 days to appeal rejection and suspension decisions.

来源：`_evidence/R1/youtube-policy-updates.md:191`
URL: 同上

【原文】（平台政策类·下架类：约 1 个月公告期）

> **[March, 2023] Overlay ad format update**: To improve the viewer experience and optimize for higher performing ad formats across devices, **legacy desktop overlay ads will stop appearing on YouTube videos starting April 6, 2023.**

来源：`_evidence/R1/youtube-policy-updates.md:193`（**加粗为本文所加**）
URL: 同上

**过渡期分级汇总（本次实测）**：

| 来源类 | 过渡期 | 触发条件 | 证据 |
|---|---|---|---|
| **法源（制裁/禁运）** | **0 天** | 账户被列入 OFAC 制裁辖区 | `No grace periods or exceptions are possible.` |
| 平台政策（critical 违规） | **3 天** | 检测到 critical 级违规 | `three-day grace period` |
| 平台政策（新规上线） | **约 30 天**，到期自动迁移 | 新政策生效 | `automatically converted … within 30 days` |
| 平台政策（规则参数变更） | **约 1 个月**（公告日→生效日） | 政策修订公告 | `May 2023` → `Starting June 5, 2023` |

【判断】
- **⭐ 这张表本身就是「隐含优先级排序」的第五个证据面，而且是量化的。** 平台给法源类 **0 天**、给自己的政策 **3–30 天**。**你不可能对一个你认为排在后面的东西给出更短的宽限期。** 过渡期长度是「不可协商程度」的直接度量，因此它比 §2.1 的措辞位置证据（弱）强得多。
- **法源类的规则必须走「实时同步」架构，平台政策类可以走「月度批次」架构。** 这是本文对客户规则库运维节奏最具体的一条建议：**不要用一套节奏处理两类来源。** 现有 21 条规则用的是同一套表格变更流程（见 R4 §1.5 的「政策一年动几次，指南每周动」对照），这在来源分类学上是不成立的。
- **`No grace periods or exceptions are possible` 里的 `exceptions are possible` 值得单独注意**：它连「例外申请」这个通道都关闭了。这意味着**该类规则的唯一正确架构是「事前拦截」而非「事后申诉」**。对客户的直接含义：**制裁类/禁运类规则不能放进「审核后可申诉」的队列，必须在投放前硬阻断。**

### 3.2 平台政策改版后，按旧版写的规则怎么办——真实的迁移实践

**找到真实实践三例，机制各不相同：**

**（a）YouTube：公告 → 生效日 → 到期自动迁移（Grace + auto-migrate）**
见 §3.1 的 Courses Policy 与 Overlay ads 两例。机制是：**给出明确生效日 + 到期后旧形态被自动转换/下架**。迁移动作由平台执行，不由发布者执行。

**（b）GitHub：政策文档带 `Effective date` 字段 + 产品线作用域字段**
【原文】（GitHub ToS 的生效日字段）
> Effective date: April 27, 2026

来源：`_evidence/R7/github-terms-of-service.txt:297`
URL: https://docs.github.com/en/site-policy/github-terms/github-terms-of-service

【原文】（GitHub 政策文档源文件的 YAML front-matter，含版本作用域字段）
> ---
> title: GitHub Acceptable Use Policies
> redirect_from:
>   - /articles/github-acceptable-use-policies
>   - /github/site-policy/github-acceptable-use-policies
> versions:
>   fpt: '*'
> category:
>   - Follow acceptable use policies
> ---

来源：`_evidence/R7/github-docs-aup-src.md:1-10`（同样结构见 `github-docs-cg-src.md:8-11`、`github-docs-tos-src.md:10-13`）
URL: https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【判断】
- **`versions: fpt: '*'` 是一个真实存在的、机器可读的政策作用域字段。** `fpt` 指 Free/Pro/Team 产品线，`'*'` 表示全版本适用。**这是本次找到的唯一一个「平台把政策的适用范围建模成结构化字段」的实例。**
- **它的意义**：GitHub 用同一个字段控制「这条政策对哪些产品线生效」。客户规则库如果需要表达「这条规则只对某平台/某品线生效」，**GitHub 的 `versions` 字段是可抄的形态**（引用形态，不涉及 schema 设计，按边界要求不展开）。
- **但注意它建模的是「作用域」不是「可信度」**——见 §3.4。

**（c）平台用 change log 作为迁移通知渠道（并明说「去看 change log」）**
【原文】
> Amazon may suspend or terminate ad accounts for severe or repeated policy violations. **Policies are periodically updated. Review the change log for updates.**

来源：`_evidence/R1/amazon-ads-policies-G5RLASA28TP9TFXZ.md:42`
URL: https://advertising.amazon.com/help/G5RLASA28TP9TFXZ
（页面自标 `Updated on Sep 2, 2026`）

【判断】
- `Review the change log for updates` 是**把迁移通知责任转移给广告主**的明文表述。平台不承诺逐个通知，只承诺维护台账。
- **与 §1.2.2 的 Amazon 台账可能停更 5 个月的观察合起来**，得到一个实用警告：**当平台把通知责任转给你、而台账本身可能不活跃时，你的变更侦测不能只依赖该台账。** 建议（本文建议）保留**页面级哈希比对**作为兜底——这正好是 R4 §4 回归门思路在「来源侦测」上的应用。

### 3.3 法源更新到规则更新的实际滞后——可测量的证据

**这次拿到了一个非常干净的数字。**

【原文】（EU AI Act 的生效与分阶段适用条款；本文证据文件正是第 6 条）

> **Entry into force and application**
>
> This Regulation shall enter into force on the twentieth day following that of its publication in the Official Journal of the European Union.
>
> **It shall apply from 2 August 2026.**
>
> However:
>
> (a) Chapters I and II shall apply from 2 February 2025;
>
> (b) Chapter III Section 4, Chapter V, Chapter VII and Chapter XII and Article 78 shall apply from 2 August 2025, with the exception of Article 101;
>
> **(c) Article 6(1) and the corresponding obligations in this Regulation shall apply from 2 August 2027.**
>
> This Regulation shall be binding in its entirety and directly applicable in all Member States.
>
> **Done at Brussels, 13 June 2024.**

来源：`_evidence/R8/eu-aiact-art6-eurlex.txt:4395-4416`（**加粗为本文所加**）
URL: EUR-Lex，EU AI Act（Regulation (EU) 2024/1689）全文页；本证据文件为 `_evidence/R8/eu-aiact-art6-eurlex.txt`（419–588KB 级一手文本，见 §5）

【原文】（DSA 的对应条款）

> 2. This Regulation shall apply from 17 February 2024.

来源：`_evidence/R8/dsa-art34-eurlex.txt:3339`
URL: EUR-Lex，DSA（Regulation (EU) 2022/2065）全文页；证据文件 `_evidence/R8/dsa-art34-eurlex.txt`

**实测滞后数字**：

| 法源 | 通过/公布日 | 适用日 | 滞后 |
|---|---|---|---|
| **EU AI Act 第 6(1) 条**（高风险分级——本文证据文件本身） | **2024-06-13**（Done at Brussels） | **2027-08-02** | **约 38 个月** |
| EU AI Act（主体条款） | 2024-06-13 | 2026-08-02 | 约 26 个月 |
| EU AI Act（第 I、II 章） | 2024-06-13 | 2025-02-02 | 约 8 个月 |
| DSA | 2022-11-16（生效） | 2024-02-17 | 约 15 个月 |

【判断】
- **⭐ 这是本文对「法源更新到规则更新的实际滞后」的正面回答：法源在文本层面可以有长达 38 个月的「已通过但未适用」窗口。**
- **这个数字推翻了一个常见假设**：不是「法源很慢所以要等」，而是「**法源很慢，所以你有时间为它准备**」。**38 个月的窗口是客户规则库唯一可以「从容建库」的机会窗口。**
- **由此推出规则库必须支持三种状态，而不是两种**（这是本文的结论，不是引文）：
  1. **已通过未适用**（Enacted, not yet applicable）—— 依据：EU AI Act Art. 6(1) 的 2027-08-02；
  2. **已适用**（In force）；
  3. **已废止/被替代**（Superseded）。
  客户现有 12 字段（`01-内部证据-规则表现状审计.md:29`：`规则编号 | 边界类型 | 适用产品 | 风险等级 | 检测关键词 | 边界内容 | 判断方式 | 依据来源 | 启用状态 | 正则表达式 | 豁免词 | 触发原因`）里**只有 `启用状态` 一个二值字段**，**无法表达第 1 种状态**。这是本分片交给 schema 设计分片的一个具体缺口（按边界要求，本文不设计字段，只指出缺口）。
- **对「提前准备」的实操含义**：客户应当把「已通过未适用」的法源**提前翻译成规则但标记为不启用**，并设定在未来适用日自动启用。这样法源生效日不会变成一次突击。

### 3.4 「来源可信度」有没有被真实系统显式建模成一个字段？

**答案：未找到作为一个「可信度」标量字段的建模。但找到了相邻的两种真实建模，必须区分清楚。**

**（a）ISO 31010 的证据状态**
`_evidence/R8/iso31010-risk-management-official.txt` 仅 6,875 bytes，为官方预览/落地页级别文本，**未取得 ISO 31010 条文正文**（R4 §6.4 已就 ISO 标准记录同一限制：「⚠️ 仅取得官方预览页，未取得条文正文」）。**因此本文不引用 ISO 31010 的任何条款内容。**

**（b）NIST SP 800-30 把「识别信息来源」建模成了一个正式任务——但不是「可信度打分」**

【原文】（NIST 风险评定的正式任务之一）

> **IDENTIFY INFORMATION SOURCES**
>
> **TASK 1-4:** Identify the sources of descriptive, threat, vulnerability, and impact information to be used in the risk assessment.
>
> Supplemental Guidance: Descriptive information enables organizations to be able to determine the relevance of threat and vulnerability information. …
>
> Sources of information as described in Tables D-1, E-1, F-1, H-1, and I-1 **can be either internal or external to organizations. Internal sources of information that can provide insights into both threats and vulnerabilities can include, for example, risk assessment reports, incident reports, security logs, trouble tickets, and monitoring results.** … **External sources of threat information can include cross-community organizations (e.g., US Computer Emergency Readiness Team [US-CERT], sector partners …**

来源：`_evidence/R8/nist-sp800-30r1.txt:1872-1897`（**加粗为本文所加**）
URL: https://csrc.nist.gov/pubs/sp/800/30/r1/final

【判断】
- **NIST 的建模方式是「内部 vs 外部」二分 + 溯源列举，不是「可信度」评分。** 这是本次找到的最接近「来源被显式建模」的实例，且它足以支撑一件事：**把「来源」做成一个一等字段是成熟标准里的既有做法**（TASK 1-4 是编号任务）。
- **但 NIST 不给来源打可信度分。** 它要求的是**可溯源**（identify the sources），不是**分级**。
- **本文的证据边界**：在全部已抓取证据中，**未找到**任何系统把「来源可信度」实现为一个可计算的字段（例如 `source_reliability: 0.8`）。§1.1 表中的「可信度」列是**本文基于证据的定性判断**，不是对既有实现的转述。**这一点必须让读者知道，否则会把本文的构造误认为行业标准。**
- **相邻但不同的一个概念**：NIST 术语表中 `Authenticity` 定义为 `The property of being genuine and being able to be verified and trusted; confidence in the validity of a transmission, a message, or message originator.`（来源：`_evidence/R8/nist-sp800-30r1.txt:2674-2678`）。**注意这是「报文/来源身份的真实性」，不是「信息内容可信度」。** 引它时必须区分，否则会张冠李戴。

### 3.5 衰减的五种机制（汇总，含各自的可侦测性）

【判断】以下五类衰减在三章证据中均可找到对应机制；「可侦测性」一列是本文判断。

| # | 衰减机制 | 实例与证据 | 是否有变更通知 | 可侦测性 |
|---|---|---|---|---|
| 1 | **政策文本改版** | Google Ads 2026 年 58 条 / Amazon Ads 2026 年 1–4 月 28 条（§1.2.2） | ✅ 通常有 changelog | **高**（有官方台账） |
| 2 | **过渡期届满** | YouTube `within 30 days of this policy update`（§3.1） | ⚠️ 只在公告时提一次 | **中**（要记录到期日） |
| 3 | **等级/口径重新校准（无文本变更）** | `We may change the severity of a violation if we observe changes…`（§2.2.3） | ❌ **无 changelog** | **低**（只能靠结果漂移反推） |
| 4 | **法源分阶段适用** | EU AI Act Art. 6(1) 2027-08-02（§3.3） | ✅ 有法定日期 | **高**（日期是确定的） |
| 5 | **依据的外部知识过期** | FTC `Keep abreast of empirical research about where consumers do and do not look on a screen`（§1.2.1） | ❌ 无 | **低** |

【判断】
- **第 3 类是最阴险的一类**：它**不产生任何文本变更**，因此任何基于「盯 changelog」的变更侦测都会完全漏掉它。唯一的侦测方式是**结果漂移监控**——即 R4 §5 的度量体系（人机一致性、平台判定与自有判定的分歧率）。**这是本文与 R4 的一个明确接口：度量不只用于评估质量，它同时是第 3 类衰减的唯一传感器。**
- **第 5 类说明衰减不只来自监管方**：FTC 明确要求广告主自己跟进眼动研究。**这类衰减没有任何人通知你，且规则条文本身完全没变。**
- **一个可操作的兜底（本文建议）**：既然第 3、5 类不可侦测，**规则库必须带「复审周期」而不是只带「来源」**——即每条规则有一个不超过 N 个月的强制复审闹钟，到点无论是否有变更通知都重看一遍。这是唯一能覆盖「无通知衰减」的机制。**注意：这与 R4 §1.1 的 YouTube 每周 QA 例会属于同一思路（用固定节奏兜住不固定触发），但粒度不同：例会是「难例驱动」，复审闹钟是「时间驱动」，两者都需要。**


---

## 4. 不可达来源

**纪律说明**：本节每条都只试一次即放弃，并记录本次实测的状态码与失败形态。**凡列入本节的来源，本文正文一律不引用其内容。**

### 4.1 任务书预告的不可达来源（已复现，确认不可用）

| 来源 | URL | 实测状态 | 证据文件 | 文件内容 |
|---|---|---|---|---|
| **Ofcom 风险评估指南** | `https://www.ofcom.org.uk/online-safety/illegal-and-harmful-content/risk-assessment-guidance` | **HTTP 403** | `_evidence/R8/ofcom-risk-assessment-guidance.txt` | `Just a moment...`（Cloudflare 挑战页，6,053 bytes） |
| **Ofcom RSM 指南 PDF** | `https://www.ofcom.org.uk/siteassets/resources/documents/consultations/category-1-2-3/risk-assessment-guidance/risk-assessment-guidance.pdf` | **HTTP 403** | `_evidence/R8/ofcom-rsm-guidance.txt` | `Just a moment...`（Cloudflare 挑战页，6,258 bytes） |
| **Better Rules（NZ）** | `https://www.digital.govt.nz/standards-and-guidance/technology-and-architecture/better-rules` | **HTTP 404** | `_evidence/R8/test-betterrules.txt` | `Page not found \| NZ Digital government`（15,442 bytes） |
| **CommonKADS 专著（Springer）** | `https://link.springer.com/book/10.1007/978-1-4471-0031-2` | **HTTP 404** | `_evidence/R8/commonkads-book.txt` | `Page Not Found`（22,816 bytes） |
| **CK 论文（UvA DARE）** | `https://dare.uva.nl/search?identifier=8e5e0d75-a6f6-4c4e-a6b1-4b2a5d0f0d40` | **HTTP 200 但内容为错误页** | `_evidence/R8/ck-thesis-uva.txt` | `UvA DARE \| Record not found`（6,976 bytes） |

【判断】
- **Ofcom 的两条对本分片影响最大**：Ofcom 是英国《在线安全法》（Online Safety Act）下的**风险评估指南发布机构**，它本应是「监管机构如何要求平台建模风险」的最佳一手样本。**两条均为 Cloudflare 403，本文无法使用。** 这是本文在「法源 → 可执行规则」这条链上的**最大证据缺口**，如实记录。
- **`ck-thesis-uva.txt` 是一个值得单独标出的陷阱形态**：它的文件头写 `HTTP: 200`，但正文第一行是 `UvA DARE | Record not found`。**只看状态码会误判为成功抓取。** 这与本次调研中发现的 `rulefit-arxiv.txt`（HTTP 200 但内容为另一篇论文）属于同一类风险：**HTTP 200 不构成证据有效性的证明。**

### 4.2 本分片新增的不可达来源（本次实测）

| 来源 | URL | 实测状态 | 处理 |
|---|---|---|---|
| **RuleFit 论文（Friedman & Popescu, *Predictive Learning via Rule Ensembles*）** | `https://statweb.stanford.edu/~jhf/ftp/RuleFit.pdf` | **HTTP 000**（连接失败） | 放弃 |
| 同上（备用镜像） | `https://jerryfriedman.su.domains/ftp/RuleFit.pdf` | **超时，60 秒后 SIGTERM** | 放弃 |
| 同上（arXiv 猜测 ID） | `https://arxiv.org/abs/0811.3628` | HTTP 200，但内容为 Ravikumar 等关于 ℓ1 惩罚对数行列式/图形模型的论文，**非 RuleFit** | 放弃 |
| **FTC `.com Disclosures` 正文页（HTML 版）** | `https://www.ftc.gov/business-guidance/resources/com-disclosures-how-make-effective-disclosures-digital-advertising` | HTTP 200，985,748 bytes，**但文本层无正文**（纯导航壳） | **已用 PDF 替代成功**，见 §4.3 |
| **Exa 检索** | `exa_search` 工具 | 未配置 API Key，不可用 | 放弃 |
| **web_search 检索** | `web_search` 工具 | `firecrawl returned 429 Too Many Requests`（keyless 免费层限额），`retry_after_seconds: 60275` | 放弃，改用直接 curl |

### 4.3 本次成功补抓的来源（一个正面结果）

【原文】（文件头）

> SOURCE_URL: https://www.ftc.gov/system/files/documents/plain-language/bus41-dot-com-disclosures-information-about-online-advertising.pdf
> FETCHED: 2026-09-15
> METHOD: chrome124
> HTTP: 200
> BYTES: 2332432

来源：`_evidence/R8/ftc-dotcom.pdf` → 文本抽取落盘为 `_evidence/R8/ftc-dotcom.txt`（53 页，pypdf 提取）

【判断】
- **这是本次调研的关键补救**：HTML 版本（`ftc-com-disclosures.txt`）只有导航壳，`grep -i "clear and conspicuous"` **0 命中**（`.raw` 985,748 bytes 同样 0 命中）。改为直接抓 PDF 后，正文完整可取，`Clear and Conspicuous` / `no litmus test` / 七要素清单等关键内容全部到位（见 §1.2.1）。
- **教训（对后续分片可用）**：**政府/机构站点的 HTML 页面经常是 JS 渲染的导航壳，同一资源的 PDF 版本反而是一次性可取的。** 遇到 `HTTP 200 但 grep 无正文` 时，先找同页的 PDF/附件链接，不要立刻判定为不可达。

---

## 5. 证据清单

**图例**：✅ = 本文逐字引用；🟡 = 本文仅作定位提示，未逐字核（已在正文标注）；❌ = 文件存在但内容不可用，本文不引用。

### 5.1 平台政策与治理（R7，全部 HTTP 200 已核）

| 证据文件 | 原始 URL | 状态 | 本文用途 |
|---|---|---|---|
| `_evidence/R7/github-docs-aup-src.md` | https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies | ✅ | §1.2.2 §2.1.2 §2.2.1 §3.2（AUP §1 位置、YAML `versions` 字段、并列句式） |
| `_evidence/R7/github-acceptable-use.txt` | 同上 | ✅ | §2.1.2（同源 HTML 抽取版，用于交叉核验正文一致） |
| `_evidence/R7/github-terms-of-service.txt` | https://docs.github.com/en/site-policy/github-terms/github-terms-of-service | ✅ | §2.1.1（`Except to the extent applicable law provides otherwise`）、§2.1.3（`the more specific terms apply`）、§3.2（`Effective date: April 27, 2026`） |
| `_evidence/R7/pypi-aup.txt` | https://pypi.org/policy/acceptable-use-policy/ | ✅ | §2.1.2 §2.1.4 §2.1.7（并列句式、兜底句、FTC 指名） |
| `_evidence/R7/aws-aup.txt` | https://aws.amazon.com/aup/ | ✅ | §2.1.5（合规意图作为减轻情节） |
| `_evidence/R7/aws-service-terms.txt` | AWS Service Terms | ✅ | §2.1.6（grep 阴性记录） |
| `_evidence/R7/amo-addon-policies.txt` | https://extensionworkshop.com/documentation/publish/add-on-policies/ | ✅ | §1.2.1 对照 §2.1.6（`must conform to the laws of the United States`；grep 阴性记录） |
| `_evidence/R7/npm-disputes.txt` | https://docs.npmjs.com/policies/disputes | ✅ | §2.2.4（`that is the only path we act on`，IP 类管辖权让渡） |
| `_evidence/R7/npm-terms-of-use.txt` | https://docs.npmjs.com/policies/terms | ✅ | §2.1.6（grep 阴性记录） |
| `_evidence/R7/shopify-legal-index.txt` | https://www.shopify.com/legal | ✅ | §2.1.6（grep 阴性记录） |
| `_evidence/R7/_fetchlog.tsv` | —（抓取日志） | ✅ | §1.2.3 §2.2.4（用于核验上述各文件 HTTP 200 / try1） |

### 5.2 平台政策变更与迁移实践（R1，HTTP 200）

| 证据文件 | 原始 URL | 状态 | 本文用途 |
|---|---|---|---|
| `_evidence/R1/google-ads-changelog-2024.md` | https://support.google.com/adspolicy/topic/16090031?hl=en | ✅ | §1.2.2（68 条/年） |
| `_evidence/R1/google-ads-changelog-2025.md` | https://support.google.com/adspolicy/topic/16083443?hl=en | ✅ | §1.2.2（75 条/年） |
| `_evidence/R1/google-ads-changelog-2026.md` | https://support.google.com/adspolicy/topic/16794025?hl=en | ✅ | §1.2.2（58 条至 9 月） |
| `_evidence/R1/amazon-ads-change-log-G8X8M375UPCN4UUC.md` | https://advertising.amazon.com/help/G8X8M375UPCN4UUC | ✅ | §1.2.2 §3.2（逐月分布；台账可能停更） |
| `_evidence/R1/amazon-ads-policies-G5RLASA28TP9TFXZ.md` | https://advertising.amazon.com/help/G5RLASA28TP9TFXZ | ✅ | §2.2.2（`Our policies aren't legal advice`、`at its sole discretion`）、§3.2（`Review the change log`） |
| `_evidence/R1/amazon-ahr.md` | https://sellercentral.amazon.com/help/hub/reference/external/G200205250 | ✅ | §2.2.3（severity 双轴） |
| `_evidence/R1/amazon-ahr-faq-GR786P4BPEVKTBAG.md` | https://sellercentral.amazon.com/help/hub/reference/external/GR786P4BPEVKTBAG | ✅ | §2.2.3（四级定义、等级可变）、§3.1（3 天宽限期） |
| `_evidence/R1/amazon-appeal-questionnaire-reinstate-G201623610.md` | https://sellercentral.amazon.com/help/hub/reference/external/G201623610 | ✅ | §1.2.3（根因 + 整改举证要求） |
| `_evidence/R1/amazon-appeal-restriction-removal-G200370560.md` | https://sellercentral.amazon.com/help/hub/reference/external/G200370560 | ✅ | §1.2.3（申诉链路、2 天回复、quiz） |
| `_evidence/R1/google-ads-country-restrictions-6163740.md` | https://support.google.com/google-ads/answer/6163740?hl=en | ✅ | §3.1（`No grace periods or exceptions are possible`） |
| `_evidence/R1/youtube-policy-updates.md` | https://support.google.com/youtube/answer/10008196 | ✅ | §3.1 §3.2（过渡期与自动迁移；363 行 / 116 条日期条目实测） |
| `_evidence/R1/amazon-prohibited-product-claims-G202024200.md` | https://sellercentral.amazon.com/help/hub/reference/external/G202024200 | 🟡 | §2.3.3 场景 1 定位提示，**未逐字核** |
| `_evidence/R1/amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.md` | https://advertising.amazon.com/help/G6UU66YLSCUYDULQ | 🟡 | §2.3.3 场景 1 定位提示，**未逐字核** |

### 5.3 法源与标准（R8，HTTP 200）

| 证据文件 | 原始 URL | 状态 | 本文用途 |
|---|---|---|---|
| **`_evidence/R8/ftc-dotcom.txt`**（附 `ftc-dotcom.pdf`） | https://www.ftc.gov/system/files/documents/plain-language/bus41-dot-com-disclosures-information-about-online-advertising.pdf | ✅ | **§1.2.1 全部**（FTC 三大引文：适用范围排除 FDA、`no litmus test`、Clear and Conspicuous 七要素） |
| `_evidence/R8/ftc-com-disclosures.txt` | https://www.ftc.gov/business-guidance/resources/com-disclosures-how-make-effective-disclosures-digital-advertising | ❌ | **不可用**：纯导航壳，`grep -i "clear and conspicuous"` 0 命中。已由 `ftc-dotcom.txt` 替代 |
| `_evidence/R8/nist-sp800-30r1.txt` | https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-30r1.pdf | ✅ | §1.2.7（专家判断三句）、§3.4（TASK 1-4、Authenticity 术语） |
| `_evidence/R8/nist-800-30-risk-determ.txt` | https://csrc.nist.gov/pubs/sp/800/30/r1/final | ✅ | §3.4（同源落地页，用于核验） |
| `_evidence/R8/eu-aiact-art6-eurlex.txt` | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=OJ:L_202401689 | ✅ | §3.3（分阶段适用、Art. 6(1) 2027-08-02、Done at Brussels 13 June 2024） |
| `_evidence/R8/dsa-art34-eurlex.txt` | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:32022R2065 | ✅ | §3.3（`shall apply from 17 February 2024`） |
| `_evidence/R8/nist-ai-rmf-playbook.txt` | https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf | — | **已持有，本文未引用**（风险治理由 R4 §6.2 承接，本文不重复） |
| `_evidence/R8/iso31010-risk-management-official.txt` | https://www.iso.org/standard/72140.html | ❌ | **不可用**：仅 6,875 bytes 官方预览级文本，未取得条文正文。本文不引用（与 R4 §6.4 记录一致） |

### 5.4 名实不符 / 内容不可用（本文明确不引用，供后续分片避坑）

| 证据文件 | 声称的内容 | 实际内容 | 证据 |
|---|---|---|---|
| `_evidence/R8/rulefit-arxiv.txt`（.raw 同） | RuleFit 规则集成论文 | **"Polynomial Coefficient Enumeration"**（Amdeberhan & Stanley，`Mathematics > Combinatorics`，arXiv:0811.3652，36 页） | 文件头 `HTTP: 200`，38,937 bytes；全文 `grep -ci "rulefit\|rule fit"` = **0** |
| `_evidence/R8/ke-llm-drops.txt` | 知识工程 / LLM 相关 | **"NLP/AI Based Techniques for Programming Exercises Generation"**（ICPEC 2023，OASIcs Vol.112，Univ. Minho） | 文件头 `HTTP: 200`，622,938 bytes；正文标题与摘要如左 |
| `_evidence/R8/ck-thesis-uva.txt` | CK 论文 | `UvA DARE \| Record not found` | 文件头 `HTTP: 200`（**状态码具误导性**），正文为错误页 |
| `_evidence/R8/ofcom-*.txt`（2 个） | Ofcom 风险评估指南 | Cloudflare `Just a moment...` | `HTTP: 403` |
| `_evidence/R8/test-betterrules.txt` | Better Rules | `Page not found \| NZ Digital government` | `HTTP: 404` |
| `_evidence/R8/commonkads-book.txt` | CommonKADS 专著 | `Page Not Found` | `HTTP: 404` |

### 5.5 本文引用的已完成分片（只读，避免重复）

| 分片文件 | 本文引用处 | 用途 |
|---|---|---|
| `R4-trust-and-safety-ops.md` | §1.1 §1.2.6 §2.3.1 §3.5 | §1.4 输入源对照表（**边界说明**：R4 写平台流程输入源，本文写客户规则库来源属性）；§3.5 错误→规则四条机制；§6.4 ISO 限制 |
| `01-内部证据-规则表现状审计.md` | §1.2.4 §3.3 | `依据来源` 字段现状（`01-...:306`）、12 字段清单（`01-...:29`） |

【判断】（证据充分性的自我评估）
- **最强的一手证据**：FTC PDF（法源侧）、GitHub ToS/AUP 与 Amazon Ads policies（优先级与自认声明）、Amazon AHR（严重性双轴）、Google/Amazon changelog（频率）、EU AI Act 与 DSA（法源滞后）。**这六组支撑了本文 §2.2.5 与 §3 的全部量化结论。**
- **最弱的环节**：**第 9 类（KOL/代理商）与第 4 类（品牌调性）无任何一手文本**，§1.2.4 与 §1.2.9 全部为判断。第 8 类（数据挖掘）因证据文件名实不符而**算法层面无一手证据**。三处均已在正文显式标注「未找到」。
- **一个未解决的疑问**：Amazon Ads 变更台账为何停在 2026 年 4 月（抓取日 2026-09-15）。本次**无法区分**「平台停更」与「抓取到旧版页面」，已在 §1.2.2 标注为不确定。

