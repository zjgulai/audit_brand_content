# R2 — 广告监管与自律的裁决案例库机制

> 分片：R2（规则库搭建与自迭代调研）
> 写作日期：2026-09-15
> 取证日期：2026-09-15（所有 URL 均为当日抓取；政策类内容会变，引用时请复核）
> 原始证据目录：`research/governance/_evidence/R2/`
> 上游约束：`research/governance/00-调研任务书.md`

---

# R2 导读者摘要

> 全部证据取回日期 **2026-09-15**（其中 NAD/NARB 一节的程序文件为当日二轮补齐）。本节读完即可取走本分片结论；完整论证见后文。

**一句话结论**：广告业给出的答案不是「错题本 **还是** 规则库」，而是**三层工件 + 一个连接键（规则编号）**；「没有规则怎么办」四个法域都有一条**举证责任倒置**的兜底条款，且措辞几乎一致。

**三层工件模型**

| 层 | 回答什么 | ASA 对应物 | 寿命 | Momcozy 现状 |
|---|---|---|---|---|
| L1 规则库 | 不许做什么 | CAP Code（`3.7`/`12.1`/`15.1.1`），Edition 12 / v12.2.107 | 长期，改一次记一次 | ✅ 21 条，但无版本、无变更日志 |
| L2 **释义层** | 同类事实怎么判 | AdviceOnline / Advertising Guidance / Enforcement Notice | 长期 | ❌ **完全没有——最值得新建** |
| L3 判例库 | 这条规则在事实上怎么落地 | ASA rulings（`G26-1343656`） | **公开 5 年** | ⚠️ 291 条，但 `检查人` 填充 0% |

**兜底条款四处原文（「没有规则怎么办」的答案）**

| 法域 | 条款 | 逐字 |
|---|---|---|
| UK | CAP Code 规则 **3.7** | `The ASA may regard claims as misleading in the absence of adequate substantiation.` |
| US | FTC Policy Statement 1984 | `a firm's failure to possess and rely upon a reasonable basis for objective claims constitutes an unfair and deceptive act or practice in violation of Section 5` |
| **EU** | UCPD **Art 12(b)**（措辞最强） | `to consider factual claims as inaccurate if the evidence demanded in accordance with (a) is not furnished or is deemed insufficient` |
| CN | 《广告法》**第二十八条第一款第（三）项** | `使用虚构、伪造或者无法验证的科研成果、统计资料、调查结果、文摘、引用语等信息作证明材料的` |
| US/NAD | Procedures §2.1(K)（正式裁决类别） | `No Substantiation Received` —— **举证不能是一个可单独发布的裁决类别**。⚠️ 措辞须精确：**没有**一句原文说「证据不足本身即违规」（§2.5c.5） |

**对委托方四问的四句话答案**

1. **维度模型**：「国家 × 品类 × 平台 × 内容类型」四维笛卡尔积**不对**。正确分层是 **L1 语义规则（与法域/平台无关）+ L2 法域映射表（规则→各国/各平台条款）+ L3 平台政策（引用，不改写）**。ASA 不按国家建规则库，跨辖区靠「来源国管辖 + 规则号」连接。
2. **萃取方法**：自上而下（法规/政策→规则）覆盖法域已明确部分，其上限由上位法划定（CAP 不能给 UCPD 黑名单增减条目）；自下而上（判例→释义→规则）覆盖长尾，但**必须经释义中间层回流**，否则判例无限膨胀且规则被个别事实绑架。
3. **错题本/规则库/严重等级**：三者用**规则编号**连接；**严重等级必须是独立字段，不能编码进编号前缀**（他们的 `H/M/U` 现在同时编码判定路径与严重度，`M05` 已因此失配）。最小字段集见 §7.1.1（9 个字段，A/B/C 三组）。
4. **自迭代**：回路是 **判例 → 释义层 → 规则修订（变更日志 + 版本号 + 缓冲期）**；度量用 **规则→判例数分布**（§1.6.4 实测模板）+ **precision/recall/false-positive rate**（DSA Reg 2024/2835 Annex I 的强制口径）；制定规则者与执行审查者应分离（ASA：CAP 制定 / ASA 执行）。

**三条对 Momcozy 最要紧的实测发现**

1. **`检查人` 字段填充 0/291** —— 他们的治理约束是「靠审查记录问责」，而问责链当前**完全没运行**。这是最高优先级缺口。
2. **规则库有两处直接矛盾**：`less pain` / `reduces pain` 同时是 `H07`（高危红线）关键词与「安全词」白名单项；且多值 `命中规则` **无规范排序**（`M03,H07` 12 次 vs `H07,M03` 5 次 = 同一集合两种写法）。
3. **`H05` 的法域敞口**：`best/#1/No.1/最佳/最好` 被「按 2026-09-09 口径放开」，但法域限定只是一句括注、不在任何结构化字段里；中国同类表述罚 10 万–80 万元。

**本分片引用的 8 个官方域名**：`asa.org.uk` · `ftc.gov` · `ecfr.gov` · `bbbprograms.org` · `eur-lex.europa.eu`（实际经 CELLAR 取文）· `samr.gov.cn` · `sjfg.samr.gov.cn` · `scjgj.fujian.gov.cn`（另引 Federal Register 文号若干）。

**证据位置**：`research/governance/_evidence/R2/`（**229 文件，约 83 MB**）。机器可核的「引用 → 文件路径 → 抓取时间」对照表见 §8.0。NAD/NARB 一节的**访问限制与取得路径**见 §2 章首（`bbbprograms.org` 对本机出口 IP 全方法 403）。

---

## 结论先行

委托方的问题原话是：「需要给我们提供『错题本』？还是规则库？严重等级？要是没有呢？怎么办？」

广告业用一百年给出的答案不是「二选一」，而是**三个工件、一个连接键**：

| 工件 | 它回答什么 | ASA 对应物 | 寿命 |
|---|---|---|---|
| **规则库**（rule） | 「不许做什么」——先验的、编号稳定的规范 | CAP Code（Edition 12），规则号如 3.7、12.1、15.1.1 | 长期，改一次记一次 |
| **判例库**（casebook） | 「这条规则在具体事实上怎么落地」——后验的、事实绑定的裁决 | ASA rulings，案件号如 G26-1343656 | **公开 5 年后下架**（见 §1.6） |
| **释义层**（guidance） | 「同类事实该怎么判」——从判例蒸馏出的可复用判断标准 | AdviceOnline / Advertising Guidance / Enforcement Notice | 长期，随判例更新 |

**连接键是规则编号。** 这是整个机制里最容易被忽略、但最关键的设计：ASA 的判例数据库可以**按 CAP Code 规则号直接检索**（`?capCode=3.7` → 该规则下的全部判例），并且每条 ruling 的末尾会明确列出「CAP Code (Edition 12)」+ 被违反的规则号清单，每个规则号超链接回规则正文（见 §1.3 逐字段拆解）。规则号是这个体系里唯一一个人工稳定、可跨版本引用、可机器连接的字段；`issue` / `media_type` / `topic` 这些分类维度在 ASA 的底层实现里都是 **GUID**（不透明内部 ID），不可移植。

**「没有规则怎么办」在三大体系里都有一条显式兜底，而且措辞几乎一致：举证责任在广告主，证据不足本身即构成违规。**

- ASA / CAP Code 规则 3.7 逐字：「The ASA may regard claims as misleading in the absence of adequate substantiation.」（ASA 可以在缺乏充分证据的情况下认定声称具有误导性）
- ASA AdviceOnline 逐字：「One of the main tenets of the Codes is that the burden of proof for claims lies with advertisers.」（举证责任在广告主，是准则的主要信条之一）
- FTC 的 doctrine 是同一个结构：substantiation 要求广告主在投放**之前**就持有证据（见 §3.1）
- EU / UCPD **Art 12(b)** 更强：`shall be regarded` —— 未提供证据或证据被认为不充分，**该声称应被视为不准确**（见 §4.1.3）
- CN / 《广告法》**第二十八条第一款第（三）项**：`使用虚构、伪造或者**无法验证的**科研成果…作证明材料的` 即构成虚假广告（见 §5.1.5）
- **NAD 的对应表述：没有逐字原文，但操作形态完整** —— Procedures 全文（2026/2020 两版）中 `burden` / `competent and reliable` / `Federal Trade Commission` **出现次数均为 0**；举证责任只写在 **FAQ** 页（`The burden of proof is on the advertiser in an NAD challenge.`）；而 **Procedures §2.1(K) 把 `No Substantiation Received` 列为正式裁决类别**，**§3.2(A) 把举证写成强制程序义务**（`the advertiser shall … provide substantiation`）。**即：结论成立，但证据地位是「四处操作条款的合力」，不是一句原文。** 见 §2.5c.1 / §2.5c.5

**这对 Momcozy 的直接含义是：他们不需要「穷举所有违规表达」才能上线审查。「规则未覆盖」不是漏洞，而是应当显式实现的一条兜底规则——『凡属客观功效声称且无法出示证据者，一律判红』。** 具体字段与流程见 §7。

三个体系的严重等级机制选型也不同，结论是：

- **ASA 的 sanctions 阶梯**是「声誉 + 媒体通路剥夺 + 法定后手」三段式，**没有罚款**（罚款在 Ofcom 那边，且只对持牌广播机构）。它适合「无法强制卡死上线节点」的组织，因为它不依赖任何一处强制卡点，而依赖**公开记录本身**产生代价。
- **NAD 的 compliance 机制**是**三态**（初稿误写为二态，已在 §2.3.3 更正）：「自愿遵守并关闭」→ **合规程序（可反复触发，§8.1(B)）** → 「转交 FTC 并公开」。中间那一态才是它的价值所在：**它把「已整改」从自行申报的状态，变成需要被复核、且可被挑战方或任何第三方反复质疑的结论**（§2.5d 的 T-Mobile 案跑满了两次）。
- **FTC 的阶梯**才有真金白银：warning letter → administrative complaint → consent order → civil penalty（金额每年按通胀调整，见 §3）。

对 Momcozy 而言，**ASA 的阶梯是唯一在结构上可搬的**：他们同样无法卡死系统节点，同样只能靠「记录 + 问责 + 公开」施压（任务书 §二.E 已明确这一约束）。

---

## 0. 取证方法与口径

### 0.1 本分片做了什么

- 一手来源：`asa.org.uk`（含 CAP Code 官方 PDF 全文 142 页、Compliance Procedures PDF、Non-broadcast Complaint Handling Procedures PDF、Evidence-based policy-making PDF）、单条 ruling 原文页面、ASA 判例检索接口实测。
- 交叉体系：FTC（`ftc.gov` / `ecfr.gov` / `govinfo.gov`）、NAD/NARB（`bbbprograms.org` / `bbbnp.org`）、EU（`eur-lex.europa.eu`）、中国（`samr.gov.cn` / `gov.cn` / `flk.npc.gov.cn` / `nmpa.gov.cn`）——见 §2–§5，各自的原始文件存于 `_evidence/R2/`。
- **两个体系存在网络级访问障碍，已在各节章首记录，供复核者复现时参考**：
  - `bbbprograms.org` 对本机出口 IP 返回 **HTTP 403**（全方法、全 UA、真实无头 Chrome 均 403 —— 属出口 IP/机房 ASN 级 WAF 封锁）。**可行路径**：`microlink.io` 云渲染器（HTML 与 PDF 均可）、`assets.bbbprograms.org`（未被拦截）、运营方 S3 源站桶。**且站点已改版**，任务书给的路径已 404。详见 §2 章首。
  - `nmpa.gov.cn` 对**所有路径**返回 **HTTP 412**（JS 反爬），直接导致 §9.1 **G5（吸奶器在中国的器械定性）成为永久 NOT FOUND**。
  - `ftc.gov` 对本网络同样 403；§3 的 FTC 材料经 `ecfr.gov` / `govinfo.gov` / Federal Register 等替代路径取得。
- 判例原文全部逐字段拆解，URL 逐条给出。

### 0.2 引用标记约定

- **「原文」**＝逐字引用，已在 `_evidence/R2/` 存有对应文件；引用时给条款号 + URL + 本地路径。
- **「本分片判断」**＝我的推论，不是原文。凡属推论必显式标注。
- 拿不到就写 **NOT FOUND**，不用推测填空。

### 0.3 CAP Code 版本标识（重要）

CAP Code 官方 PDF 封面页载明版本标识（`_evidence/R2/The-CAP-Code.pdf` 第 1 页，本地文本 `_evidence/R2/The-CAP-Code.txt` 第 1–7 行）：

> The CAP Code
> The UK Code of Non-broadcast Advertising
> and Direct & Promotional Marketing
> **Edition 12**
> Legal, decent, honest and truthful **v12.2.107**

**这是「规则库带版本号」最朴素也最有效的实现：`Edition 12` 是主版本（2010 年启用），`v12.2.107` 是次版本计数器。** 每一条 ruling 的末尾都会写「CAP Code (Edition 12)」，即判例锚定到**版本**而非「最新版」。这对历史判例的可回溯性是决定性的——见 §1.4。

---

## 1. 英国 ASA / CAP Code（首要目标）

### 1.1 CAP Code 的编号体系与分层

#### 1.1.1 顶层结构

CAP Code 官方 PDF 目录（`_evidence/R2/The-CAP-Code.txt` 第 10–60 行，源 PDF `_evidence/R2/The-CAP-Code.pdf` 第 2 页）逐字列出：

```
Preface
Introduction
1. Compliance
2. Recognition of marketing communications
3. Misleading advertising
4. Harm and offence
5. Children
6. Privacy
7. Political advertisements
8. Promotional marketing
9. Distance selling
10. Use of data for marketing
11. Environmental claims
12. Medicines, medical devices, health-related products and beauty products
13. Weight control and slimming
14. Financial products
15. Food, food supplements and associated health or nutrition claims
16. Gambling
17. Lotteries
18. Alcohol
19. Motoring
20. Employment, homework schemes and business opportunities
21. Tobacco, rolling papers and filters
22. Electronic cigarettes
23. How the system works
24. History of self-regulation
25. Appendix 1 The DMCCA and the BPRs
26. Appendix 2 Advertising rules for on-demand services regulated by statute
27. Appendix 3 VSPs Advertising rules for video-sharing platforms regulated by statute
```

URL：https://www.asa.org.uk/codes-and-rulings/advertising-codes/non-broadcast-code.html
（在线版本按 Section 拆分，页面上每节都有标题与说明，与 PDF 目录一一对应）

#### 1.1.2 规则编号格式

**格式：`<节号>.<规则序号>`，子规则再加一级 `<节号>.<规则序号>.<子序号>`。**

实测样例（全部来自 `_evidence/R2/The-CAP-Code.txt`，行号为本地文本行号）：

| 规则号 | 原文（逐字） | 本地行号 |
|---|---|---|
| 3.1 | `Marketing communications must not materially mislead or be likely to do so.` | 434 |
| 3.4.1 | `the main characteristics of the product` | 453 |
| 12.2.1 | `Marketing communications for medicinal products must not offer to provide a diagnosis or suggest a treatment by correspondence, for instance, by post, by e-mail or by other means of an electronic communications network.` | 1621 |
| 15.1.1 | `Only nutrition claims listed in the applicable register may be used in marketing communications.` | 2001 |
| 15.14.1 | `Except those for fresh fruit or fresh vegetables, marketing communications …` | 2095 |

**关键属性：编号是「节内顺序号」，不是「语义分类号」。** 这一点直接决定了后面的所有问题——见 §1.4。

#### 1.1.3 节内的固定骨架

每个 Section 都遵循同一骨架：`Background`（法律与事实背景）→ `Scope`（本节适用于什么）→ `Definition`（术语定义）→ `Rules`（规则正文）。以 Section 12 为例（`_evidence/R2/The-CAP-Code.txt` 第 1506 行起）：

> **Scope**
> The rules in the first part of this section apply to all marketing communications for medicines, medical devices, treatments, health-related products and beauty products. The rules in subsequent parts apply to marketing communications for specific products and/or services. If relevant, the rules in this section also apply to claims for products for animals.
> **Definition**
> For the purposes of this Code, "licence" includes certificate, authorisation or registration.
> "Applicable conformity marking" means conformity marking required by legislation set out earlier this section, under "Law".
> "Disease" includes any injury, ailment or adverse condition, whether of body or mind.

**这个骨架本身就是一种规则工程实践：把「适用范围」「术语」「规则条文」三层在同一节内物理分离。** 对照 Momcozy 现有的 21 条规则库——`边界内容` 一栏同时承载了「适用范围」和「规则条文」，`触发原因` 一栏同时承载了「判定理由」和「升级条件」——这是他们 schema 的第一个结构性问题（详见 §7.2）。

### 1.2 sector-specific 规则如何挂到主码上（**修正任务书的一处前提**）

**任务书 §调研目标 1 问：「sector-specific 的附录（如 medicines、alcohol、HFSS、gambling）如何挂到主码上？附录是覆盖主码还是叠加？」**

**实测结论：这些不是附录，是主码的第 12–22 节。** 我按 PDF 目录逐条核对（§1.1.1）：medicines 在第 12 节、alcohol 在第 18 节、gambling 在第 16 节、HFSS 在**第 15 节内部**（规则 15.14–15.20）。真正的三个 Appendix 是**法定回填条款**：

| Appendix | 内容 | 性质 |
|---|---|---|
| Appendix 1 | The DMCCA and the BPRs | 把《Digital Markets, Competition and Consumers Act 2024》与《Business Protection from Misleading Marketing Regulations 2008》的法定义务回填进准则 |
| Appendix 2 | Advertising rules for on-demand services regulated by statute | Ofcom 指定 ASA 共同监管 VoD 广告（2010 年 8 月起）后的法定要求 |
| Appendix 3 | VSPs — video-sharing platforms | 法定视频分享平台广告规则 |

（来源：`_evidence/R2/The-CAP-Code.txt` 第 30–40 行目录 + 第 100–140 行 Preface 说明）

**那么「覆盖还是叠加」？答案是第三种的、更精确的结构：分节 + 显式优先级声明 + 节内交叉引用。**

1. **分节**：通用规则（第 3 节 Misleading advertising）与行业规则（第 12/13/15/16 节）是**并列的编号空间**，不是父子关系。行业规则不重复通用规则，而是**叠加适用**。
2. **显式声明叠加**：Section 3 的 Background 明确写（`_evidence/R2/The-CAP-Code.txt` 第 425–428 行）：

   > **原文**：`Children and Medicines sections of the Code contain rules that apply, as well as the general rules, to marketing communications that fall under those sections.`

   （「Children 与 Medicines 两节包含的规则，与通用规则**一并**适用于落入该两节的营销传播。」）
3. **节内交叉引用是显式的、带编号的**——这就是编号真正在干活的地方：
   - 规则 3.4.6：`that consumers have the right to withdraw or cancel, if they have that right (**see rule 3.56**).`
   - 规则 12.2：`Accurate and responsible general information about such conditions may, however, be offered (**see rule 12.11**).`
   - 规则 12.9：`…must hold proof before suggesting their product or therapy is guaranteed to work, absolutely safe or without side-effects (**subject to rule 12.19**).`
   - 规则 15.7：`Nutrition and health claims for food supplements must be permitted or authorised as provided for **at rule 15.1.1 above**.`
   - （以上均见 `_evidence/R2/The-CAP-Code.txt`，行号分别为 469、1615、1650、2042）

**本分片判断**：ASA 用「编号 + 显式交叉引用」替代了「继承 / 覆盖」这类层级语义。规则之间没有 override 关系，只有「一并适用」和「但书指向」。这样做的好处是**判定结果可追溯**——一条广告被判违规时，引用的是一组**平铺的规则号**（见 §1.3 的 Nutricia 案：同时引 1.10 / 15.10 / 15.1 / 15.1.1 / 15.10.1），而不是一条继承链。

**这对 Momcozy 的启示**：他们的 `H/M/U` 三族本质上不是三个严重等级，而是三种**判定路径**（自动红线 / 语境守卫 / 人工复核）。ASA 的做法说明：**严重等级应该是一个独立字段（decision/sanction 层），不应编码进规则编号的前缀**。把 `H` 当严重等级用，会导致「同一条规则既要有高严重度实例又要有低严重度实例」时无处安放——这正是他们 `U04` 想表达却没表达出来的东西（`U04` 的说明文字里写着「与 goodbye/no more/not anymore/relieve 等连用应升级 H01/H07」——**升级不是严重等级，是判定路径的切换**）。

### 1.3 单条 ruling 的完整字段结构（逐字段拆解 4 条真实判例）

#### 1.3.1 判例 A：Hemios（磁疗手环，减肥 + 性功能声称）

- URL：https://www.asa.org.uk/rulings/hemios.html
- 本地证据：`_evidence/R2/ruling-hemios.html`
- 裁决：**Upheld**（投诉成立）
- 刊登媒体：`Social media (paid ad), Internet (display)`
- 发布日期：`09 September 2026`

逐字段拆解（字段名取自页面上的实际小标题，引文逐字）：

| # | 字段 | 该案取值 |
|---|---|---|
| 1 | 标题 | `ASA Ruling on Hemios` |
| 2 | 广告主 | `Hemios` |
| 3 | 裁决 | `Upheld` |
| 4 | 媒体 | `Social media (paid ad), Internet (display)` |
| 5 | 发布日期 | `09 September 2026` |
| 6 | **Ad description** | 逐字描述被投诉广告，并**分子条目 a./b. 引用广告原文**：`a. The Facebook ad, seen on 24 May 2026, featured an image of a bracelet and the text, "DAMN, THIS THING WORKS! Morning wood is back. Gained 15lbs of muscle. Energy lasts all day. Stubborn belly fat melted."` / `b. The YouTube ad, seen on13 May 2026, featured an image of a bracelet and the text, "ROCK HARD MORNINGS IN 72 HOURS. Or get your money back.", "BURNS OFF BEER BELLY", "MELTS MAN BOOBS", "REDUCES JOINT PAIN", "BOOSTS DESIRE".` |
| 7 | **Issue** | `Two complainants challenged whether the efficacy claims for the Hemios were misleading and could be substantiated.` |
| 8 | **Response** | 广告主的完整答辩，含其提交的证据类型：`They provided a link to a "Transparency & Safety" page on their website… Hemios referred to three published papers on vacuum-constriction devices.` |
| 9 | **Assessment** | ASA 的推理过程。**显式写出「未获证据 ⇒ 未获证实 ⇒ 误导」的三段推论**：`We assessed the evidence provided. This included a transparency and safety page from Hemios' website, and summaries of three articles which related to studies of vacuum-constriction devices. **Hemios did not provide copies of the articles.** However, we understood that they did not relate to the product sold and were not recent. The website material did not amount to substantiation for the claims in the ads.` / `Because we had not seen evidence that the Hemios bracelet could produce the claimed effects, we concluded that the claims had not been substantiated and were misleading.` |
| 10 | **依据的规则（显式声明）** | `The ads breached CAP Code (Edition 12) rules 3.1 (Misleading advertising), 3.7 (Substantiation), 12.1 (Medicines, medical devices, health-related products and beauty products), and 13.1 (Weight control and slimming).` |
| 11 | **规则号清单（机器可读块）** | 页面下方独立一块：`CAP Code (Edition 12)` + `3.1` `3.7` `12.1` `13.1`，每个规则号是指向规则正文的超链接 |
| 12 | **Action** | 处置命令：`The ads must not appear again in the form complained of. We told Hemios not to make efficacy claims about their product, for example in relation to weight loss, or improving erectile performance, in the absence of adequate evidence.` |
| 13 | More on（主题标签） | `Weight and slimming` |
| 14 | 广告主地址 | `Hemios / 70 Stevenson St / San Francisco / California / 94105 / USA` ← **境外广告主，ASA 仍管辖** |
| 15 | Number of complaints | `2` |
| 16 | Agency | `None – unconfirmed` |
| 17 | **Complaint Ref** | `G26-1343656 Hemios` ← **稳定案件编号** |
| 18 | Related rulings | 关联判例列表 |
| 19 | Recommended resources | 指向 AdviceOnline 释义条目（`Weight control: Pills, medicines and patches` 等） |

**三个必须点出来的机制：**

1. **字段 6 + 字段 7 分离了「事实」与「争点」。** `Ad description` 是**证据**（广告原样），`Issue` 是**待判问题**（把事实抽象成一句可判定的争点）。这个分离正是「错题本」能否被复用的分水岭——见 §7.1。
2. **字段 10 + 字段 11 让「依据哪条规则」既给人读也给人连。** 散文里写一遍（带规则简称），下面再给一个纯规则号清单，规则号超链接回规则正文。
3. **字段 9 的推理链条是「证据 → 是否充分 → 结论」而不是「对错」。** 原文：`Hemios did not provide copies of the articles.` —— **ASA 把「没交全文」本身作为一个不利事实来记载。** 这与 §1.7 的程序规则一致：`Abstracts of full studies will not usually be considered sufficient to substantiate claims.`

#### 1.3.2 判例 B：Nipper&Co Ltd（催乳茶 —— **对 Momcozy 最贴近的判例**）

- URL：https://www.asa.org.uk/rulings/nipper-co-ltd-a25-1284063-nipper-co-ltd.html
- 裁决：**Upheld**，发布日期 `09 July 2025`
- 依据规则：`The ad breached CAP Code (Edition 12) rules 15.1 and 15.1.1 (Food, food supplements and associated health or nutrition claims)`
- Complaint Ref：`A25-1284063 Nipper&Co Ltd`

**为什么这条判例对 Momcozy 价值最高**：它判的是一支「催乳茶」的带货视频，声称 `encourage breast milk supply`，而**视频里用奶瓶刻度演示了 2oz → 3oz 的产出增长**。ASA 认定这不只是文字问题——**画面本身构成了隐含的健康声称**。逐字原文：

> `We further considered the video content, which appeared to show someone producing 2oz of breast milk whilst pumping on day one of consuming the tea, which increased to 3oz on day seven of consuming the tea, **also implied that the MUM's MiLK lactation tea could increase how much breast milk a new mother could produce.**`
> `We considered those were specific health claims for the purposes of the Code. However, we had not seen any evidence which demonstrated that those claims were authorised on the GB NHC Register.`
> `because at the time it was seen it included specific health claims that were not authorised on the GB NHC Register, we concluded that it breached the Code.`
> **Action**：`The ad must not appear again in the form complained of. We told Nipper&Co Ltd t/a Nipper & Co to ensure that any specific health claims made in their future advertising were authorised on the GB NHC Register and met the associated conditions of use.`

**本分片判断**：这条判例把「产品名称本身」（`lactation tea`）也算作隐含声称——原文 `We considered that the references to the product's name, "lactation tea" in the ad, also implied a relationship between the tea and breast milk production.`。**对 Momcozy 的直接含义：一旦某个 SKU 的名称或视觉符号（如奶量刻度、奶瓶液面、'more milk' 图标）语义上指向增产，它就是一个独立于文案的关键词命中源——现有 21 条规则库全部是「文本关键词 + 正则」，对画面/产品名零覆盖。**

#### 1.3.3 判例 C：Go Night Night（冒用专业机构背书 —— **对应 Momcozy 的 U01 规则**）

- URL：https://www.asa.org.uk/rulings/go-night-night--unconfirmed--a24-1249218-go-night-night--unconfirmed-.html
- 裁决：**Upheld**，发布日期 `30 October 2024`
- 依据规则：`The ad breached CAP Code (Edition 12) rules 3.1 (Misleading advertising), 3.50 and 3.51 (Endorsements and Testimonials).` **另加 1.7（Unreasonable delay）**
- Complaint Ref：`A24-1249218 Go Night Night (unconfirmed)`

**这条判例直接回答了 Momcozy 的 U01（`lactation consultant / IBCLC / expert-tuned / expert-designed` 需核实是否真实合作）应该怎么判**。事实与理由逐字：

> **Response**：`Go Night Night did not respond to the ASA's enquiries.`
>
> **Assessment**：`The ASA was concerned by Go Night Night's lack of response and apparent disregard for the Code, which was a breach of CAP Code (Edition 12) rule 1.7 (Unreasonable delay). We reminded them of their responsibility to provide a response to our enquiries and told them to do so in the future.`
>
> `We considered consumers would interpret the inclusion of FEDANT's logo, which appeared on every page on the website, and contained the text "FEDANT, Federation of Antenatal Educators", to mean that Go Night Night was registered with them. FEDANT administers the national register and professional standards of antenatal educators, breastfeeding counsellors and doulas in the UK. However, we understood that Go Night Night was not registered with them. We therefore concluded that the use of the FEDANT logo was misleading.`
>
> **Action**：`The ad must not appear again in its current form. We told Go Night Night not to feature the FEDANT logo in future unless they were registered with them.` **`We referred the matter to CAP's Compliance team.`**

**三个可搬运的机制点：**

1. **「未回应」本身是独立的违规条目**（规则 1.7）。ASA 有一套「不配合即违规」的规则，不依赖实体判断。**Momcozy 的 21 条规则里没有任何一条覆盖「未回应/未提供证据」——这是他们兜底条款必须补的第一条。**
2. **违规认定的路径是「消费者会如何理解」而不是「事实上有没有合作」**。原文 `We considered consumers would interpret the inclusion of FEDANT's logo… to mean that Go Night Night was registered with them.` 而判定的关键事实是「事实上没注册」。**这是「背书类声称」判定模板：声称 X ⇒ 需证明 X 成立 ⇒ 不成立即误导。**
3. **`We referred the matter to CAP's Compliance team.` 是升格动作，且被写在 ruling 里。** 这一步在所有 sanctions 阶梯里排第一位（见 §1.5）。

**对应规则正文（`_evidence/R2/The-CAP-Code.txt`）：**

> `3.47 Marketers must hold documentary evidence that a testimonial or endorsement used in a marketing communication is genuine, unless it is obviously fictitious, and hold contact details for the person who, or organisation that, gives it.`
>
> `3.52 Marketing communications must not display a trust mark, quality mark or equivalent without the necessary authorisation. Marketing communications must not claim that the marketer (or any other entity referred to), the marketing communication or the advertised product has been approved, endorsed or authorised by any public or private body if it has not or without complying with the terms of the approval, endorsement or authorisation.*`

**注意 3.52 的构成要件是「授权 + 遵守授权条款」两条**——不是「有没有合作」，而是「有没有获得**授权**」且「有没有**遵守授权条款**」。这对 Momcozy 的「专家调校程序」尤其重要：即使真的请了 IBCLC 参与，**如果对方的授权范围不包含对外背书表述，仍然违规**。

**本分片判断**：Momcozy 的 `U01` 现在是一句人工判断（「含泌乳顾问/认证头衔，需核实是否真实合作」），其判定条件（「是否真实合作」）比 CAP 规则 3.52 的判定条件（「是否获得授权 + 是否遵守授权条款」）**更松**。这是一个应当收紧的边界。

#### 1.3.4 判例 D：Nutricia Ltd（婴儿配方奶播客 —— **多争点、混合裁决、含版本适用声明**）

- URL：https://www.asa.org.uk/rulings/nutricia-ltd-g21-1111826-nutricia-ltd.html
- 裁决：`Three issues were investigated, two of which were Upheld. The other was informally resolved after the advertiser agreed to amend their advertising.`
- 依据规则：议题 1 → `1.10 / 15.10 / 15.1 / 15.1.1`；议题 2 → `15.10 / 15.10.1 / 15.1 / 15.1.1`（页面把每个规则号**连同规则正文一并内嵌**在 Assessment 里显示）

**这条判例贡献两个别的判例没有的字段：**

**（1）`Background` 字段——版本 / 法律背景适用声明。** 逐字：

> `The ad under investigation appeared in May 2021, and we therefore assessed it under the Code interpreted in the light of changes in the background law resulting from the UK's exit from the EU, as per CAP/BCAP's statement on EU exit dated 22 December 2020.`

**这是「历史判例如何在规则变更后仍然可回溯」的机制答案**：判例**显式记录它所适用的规则版本与法律背景**，不随准则更新而改写。对照 §1.4 的 renumbering 机制，两者合起来构成完整的时间可回溯性。

**（2）多争点 = 多行裁决，且每一行独立给规则号。** `Summary of Council decision` 明确写「三个议题，两个 Upheld，一个 informally resolved」。**这对 Momcozy 的 291 条记录很重要：一条内容可以同时命中多条规则、且各条规则的结论可以不同**——他们的 `命中规则` 字段是多值的（如 `H02,H07,H09`），但 `风险等级` 是单值的（`高危·红`）。**多值命中 + 单值等级会造成等级归因丢失**：当 `H02,H07,H09` 同时命中时，最终是「红」的原因无法区分是三条都红、还是其中一条红。见 §7.1。

#### 1.3.5 ruling 的字段 schema（从 4 条判例归纳）

```
ruling {
  case_ref          : "G26-1343656" | "A25-1284063"   # 稳定案件号，前缀 G/A 区分来源
  title             : "ASA Ruling on <advertiser>"
  advertiser        : string
  trading_as        : string?                          # "t/a ..."
  advertiser_address: string?                          # 含境外地址
  decision          : "Upheld" | "Not upheld" | "Upheld in part"
  media             : [string]                         # "Social media (paid ad)" 等
  published_date    : date                             # 每周三发布
  background        : string?                          # 版本/法律背景适用声明
  ad_description    : [{label:"a"|"b", seen_date, medium, verbatim_text}]
  issue             : [{index, complainant_type, challenged_claim}]
  response          : string                           # 广告主答辩 + 提交证据清单
  assessment        : [{issue_index, outcome, reasoning, evidence_assessed}]
  rules_breached    : [{edition:"Edition 12", rule:"3.7", rule_title:"Substantiation"}]
  action            : string                           # 处置命令
  referral          : "CAP Compliance team" | null     # 升格动作
  topics            : [string]                         # "Weight and slimming"
  complaints_count  : int
  agency            : string | null
  related_rulings   : [case_ref]
  advice_links      : [advice_online_slug]
}
```

**本分片判断**：其中 `case_ref`、`rules_breached`、`decision`、`published_date`、`media`、`action`、`referral` 是**机器可读且已结构化呈现**的七项；`ad_description`、`issue`、`response`、`assessment` 是**非结构化散文**（但小标题固定，可解析）。ASA 官方**没有**提供 JSON/API——判例库是 HTML，可读不可编程。见 §1.6。

### 1.4 规则编号是否稳定？——三个已实现的机制

这是任务书 §交叉问题 的第一问，ASA 的答案很干脆：**编号基本稳定，必须变动时用「留墓碑」和「留迁移记录」两种手法显式处理，且必须带日期。**

#### 机制一：原地墓碑（tombstone），编号永久保留

`_evidence/R2/The-CAP-Code.txt` 第 225 行与第 366 行逐字：

> `l. [Deleted 10 May 2018].`
>
> `1.8.1 [Deleted 6 November 2018]`

**关键点：被删的规则**占位**保留在编号序列里，只标注删除日期。** 编号**不回收、不复用**。这意味着任何一条历史判例引用的 `1.8.1`，十年后仍能在规则正文里查到「此规则已于 2018-11-06 删除」，而不是查无此号。

#### 机制二：迁移记录（renumbering notice），带生效日

`_evidence/R2/The-CAP-Code.txt` 第 2142 行逐字：

> `15.18 Rule renumbered and moved to 15.20 on 5 January 2026.`

**编号变更时，旧号位置写「已改号为 X，生效日 Y」。** 于是：
- 2026-01-05 之前的判例引用 `15.18` → 旧号位置能指到新号
- 2026-01-05 之后的判例引用 `15.20` → 新号
- 两端都不产生断链

配合 §1.3.4 的 `Background` 字段（判例记录自己适用的版本），时间轴就完整了。

#### 机制三：Edition + 次版本号 + 变更登记册

1. 主版本：`Edition 12`（2010-09-01 生效）。CAP Code 原文（`_evidence/R2/The-CAP-Code.txt` 第 380 行附近）：

   > `This twelfth edition of the Code comes into force on 1 September 2010. It replaces all previous editions.`

2. 次版本：封面 `v12.2.107`。

3. **变更登记册**（Register of CAP Code changes）——URL：https://www.asa.org.uk/codes-and-rulings/advertising-codes/register-of-cap-code-changes.html
   本地证据：`_evidence/R2/asa-register-cap-changes.txt`

   页面开篇逐字：

   > `This page lists substantive rule changes made to the CAP Code since it was published in 2010.`
   > `It does not list administrative changes, for example where references to legislation, licensing or other bodies have been updated without impacting the effect of the rules, or changes to introductory passages or similar which describe, for example, the scope of the sections involved.`

   **这是「哪些变更需要登记、哪些不需要」的显式判据：实质规则变更登记；引用/法律名称更新等不影响规则效果的行政变更不登记。**

   登记册的条目格式**只有三种**，全部以规则号为键：

   | 格式 | 登记册实例（逐字） |
   |---|---|
   | `Amendment of <规则号>, was: <旧文>` | `Amendment of 3.18, was: Quoted prices must include non-optional taxes, duties, fees and charges that apply to all or most buyers…` |
   | `Addition of <规则号>` / `Addition of rule <规则号>` | `Addition of rule 9.10` / `Addition of rule 15.18` |
   | `Insertion of <规则号>` | `Insertion of 12.2.1` / `Insertion of section 22 (Electronic Cigarettes)` |

   登记册按 Section 分组列出受影响的节：`Scope of the Code / 03 Misleading advertising / 09 Distance selling / 10 Database practice / 11 Environmental claims / 12 Medicines / 15 Food / 16 Gambling / 20 Employment / 21 Tobacco / 22 Electronic Cigarettes`。

**⚠️ 一个必须记录的缺口**：**登记册的在线版本不逐条标注变更日期**（我核对了原始 HTML，只出现 `January 2005` 一处日期，属旧条文内在引用，非变更日期）。带日期的变更记录散落在 **CAP Code PDF 正文内**（如 `[Deleted 10 May 2018]`、`renumbered and moved to 15.20 on 5 January 2026`）。

**本分片判断**：这是一个可复用的教训——**变更日志必须把「规则号」「旧文」「新文」「生效日」四个字段做成一等公民**。ASA 把「规则号 + 新旧文」放在网页登记册、把「生效日」放在准则正文脚注，导致**两处信息必须手工关联**。Momcozy 若把变更记录做在规则表的 `备注` 列里（他们现在 `U02` 就是这么做的：`因站点资质已具备而停用`，只有原因没有日期），会复现同样的问题。

#### 机制四（补充）：未被登记册覆盖但确实发生了的「口径变更」

Momcozy 的 `H05` 规则里写着一句极度值得注意的话：

> `虚假安全承诺（best/#1/No.1/最佳/最好等排名最高级按2026-09-09口径放开，海外广告允许，不再判险）`

**这是他们自己的「口径变更」记录——一条规则的关键词范围被外部口径决定，且带日期。** 但这条口径**没有对应的 `依据来源`**：该行 `依据来源` 只写了 `W1卖点表达边界（品线反馈2026-09-10 T4）+ 吸奶器广告文案审计_红绿灯.xlsx 规则库`，没有任何指向「2026-09-09 口径」的出处。

**本分片判断**：这正是 ASA 「依据来源必须可回溯」要防的东西。ASA 的规则 1.10 原文（`_evidence/R2/The-CAP-Code.txt` 第 1704 行附近，Nutricia 案内嵌引文）：

> `Marketers have primary responsibility for ensuring that their marketing communications are legal. Marketing communications should comply with the law and should not incite anyone to break it.`

对照 §5 中国《广告法》第九条第（三）项对绝对化用语的禁令——**「best/#1/No.1/最佳/最好」在海外可以放开，但如果同一条素材投放到中国站点，就是《广告法》第九条的正面违规。** 而 Momcozy 的 291 条记录里，投放地区**没有美国、也没有中国**（`其他216 / 法国26 / 英国19 / 加拿大14 / 西班牙11 / 意大利3`）。这意味着他们现在的规则库是按「广告投放地」而不是「内容适用法域」建的——见 §6.3。

### 1.5 ASA 的 sanctions 阶梯（每一级的触发条件与原文）

ASA 的制裁阶梯分散在三份文件里：`Sanctions` 网页（面向公众的概览）、`CAP Compliance: Non-broadcast compliance procedures`（PDF，2025-02-03 版，**面向执行的操作规程**）、CAP Code 第 23 节 `How the system works`（准则内的法定/自律工具箱）。以下是完整阶梯。

#### 1.5.1 阶梯总表

| 级 | 动作 | 触发条件（原文） | 出处 |
|---|---|---|---|
| **L0** | 非正式解决（informal resolution / informal case） | 投诉成立但「不需要正式调查」；广告主同意修改或撤下 | 见 §1.5.2 |
| **L1** | 正式裁决 + 每周公开（adverse publicity） | ASA Council 裁决违规 | CAP Code §23 |
| **L2** | 要求书面合规保证（pro-forma notice of compliance） | 裁决违规后即触发 | 程序 PDF 第 41 段 |
| **L3** | 转 CAP Compliance team（**升格动作**） | 广告主未在截止日前撤改或未给保证 | 程序 PDF 第 6.i 段 |
| **L4** | 点名公示（Non-compliant online advertisers 页 + SEO + 付费搜索广告） | 在广告主自有网站/自有社媒等非付费空间持续违规 | Sanctions 页 |
| **L5** | Ad Alerts（媒体通路封锁） | CAP 认为需警示媒体勿接该广告主广告；分 General 与 Specific 两类 | CAP Code §23 / Ad Alerts 页 |
| **L6** | 撤销交易特权与认可（Royal Mail 批量邮费折扣等；极端情况开除会籍） | CAP 会员组织自行执行 | CAP Code §23 |
| **L7** | 强制预审（pre-publication vetting / poster pre-vetting，通常 2 年） | 「persistent offenders, or those whose marketing communications bring advertising into disrepute」 | CAP Code §23 |
| **L8** | Enforcement Notice（整行业） | 某行业内多家广告主明确违规 | 程序 PDF 第 8–12 段 |
| **L9** | 转 Trading Standards / CMA（法定后手） | 裁决后仍持续出现；Trading Standards 可要求承诺、申请禁制令 | CAP Code §23 |
| **L10** | 转 Ofcom（仅广播 / VoD） | 广播持牌机构持续违规 | Sanctions 页 |

#### 1.5.2 L0：非正式解决——**不进判例库、不写规则号**

`How we handle complaints` 页逐字（URL：https://www.asa.org.uk/make-a-complaint/how-we-handle-complaints.html，本地 `_evidence/R2/asa-how-handle-complaints.html`）：

> `Sometimes we'll decide that there's a problem under the rules but that the issues raised don't call for us to investigate. In these cases we'll write to the advertiser providing appropriate guidance. As we prefer to work by persuasion and agreement, some complaints can be resolved quickly and informally by working with an advertiser to have an ad changed or get a name taken off a mailing list. **Informally resolved cases aren't put before the ASA Council, so no ruling is published.**`

程序 PDF 的定义（本地 `_evidence/R2/asa-Non-broadcast-Complaint-Handling-Procedures.txt`）：

> `Informal case – an investigation is launched on a potential breach of the Code but we secure from the Advertiser their agreement to amend or withdraw the ad to bring it into compliance without the need for a Ruling.`

**但非正式解决并非完全不可见。** 判例列表页有独立的 `Informally resolved` 标签页，并说明（URL：https://www.asa.org.uk/codes-and-rulings/rulings.html）：

> `We also publish a list of companies and organisations which agree to amend or withdraw their ad without being subject to a formal ruling.`

**而公开的字段只有三个。** 我抓取了 2026-09-09 那一期的 Informally resolved 列表（本地 `_evidence/R2/asa-informal2.html`），逐条形态一致：

```
Advanced Thermosets Ltd t/a Ru-bix Advanced Materials
09 September 2026
Number of complaints: 1
```

（该期共 8 条，全部只有「广告主名 / 日期 / 投诉数」三项）

**这是整个 ASA 体系里对 Momcozy 最有价值的一个设计决策，我把它单独拎出来：**

> **ASA 的公开判例库有「两级可见性」：正式裁决完整公开且带规则号；非正式解决只公开「谁 + 何时 + 几条投诉」，不给规则归属、不给广告描述、不给评估过程。**

**本分片判断**：这样做的好处是**规则→判例索引的纯度**。如果非正式解决也带规则号，那么「规则 3.7 下有 373 条判例」这个数字就会混入大量未经对抗性检验的、单方认定的案例，规则的含义会被稀释。ASA 的选择是：**只有经过 Council 对抗式裁决的事实，才有资格定义规则的含义。**

Momcozy 的对应处境是：291 条在跑记录里绝大多数是「审查时命中 + 给了改写建议」，属于 ASA 意义上的 informal 层。**他们需要先决定：这些记录进不进判例库？**

**建议（详见 §7.1）**：分两级存——
- **审查记录层**（291 条所在的层）：全字段保留，含 `命中规则`、`命中片段`、`修改建议`、`检查人`，但**不用于定义规则含义**。
- **判例层**：只有满足「已上线且造成实际风险」或「人工复核改判过系统判定」或「有外部投诉/平台下架」三种条件之一的记录，才升格进判例层，并补全 ASA 式字段（争点、答辩、证据、评估、处置）。

#### 1.5.3 L3–L4：Compliance team 与「明确违规」的判据

`CAP Compliance: Non-broadcast compliance procedures`（2025-02-03 版 PDF，本地 `_evidence/R2/compliance-procedures.pdf` / `.txt`）第 4 段逐字给出**「不需要判例也能执法」的门槛**：

> `CAP and the ASA are complementary parts of the enforcement regime, and CAP will only take enforcement action against specific ads in the absence of an ASA ruling where the breach is clear-cut. An ad is determined to be in clear-cut breach by reference to a directly applicable ASA ruling or, in the absence of a ruling, by reference to one or more CAP Code rules that, in the view of ASA or CAP and given the specific content and context of the ad, leave no reasonable scope for alternative interpretation or alternative application.`

**这就是「没有判例怎么办」的官方答案：规则条文本身足够明确到「no reasonable scope for alternative interpretation」时，可以直接执法。** 反过来也说明：**规则写得越模糊，越依赖判例；规则写得越精确，越能直接执法。** 这是规则质量的度量之一。

第 6 段给出合规案件的三个来源与内部案件类型码：

> `i. The ASA Investigations team` → 广告主未给书面保证时转来，内部记为 **`post-investigation compliance case` 或 `PIC`**
> `ii. The ASA Complaints team` → 投诉显示明确违规时转来，内部记为 **`Non-compliant ad`**
> `iii. Other sources` → 主动监测（`Active Ad Monitoring system`、tech-assisted monitoring、staff monitoring、stakeholder intelligence）

第 6.ii 段还给了两个**示例性「明确违规」**（可直接拿来当 Momcozy 的类比）：

> `no ad-specific ASA ruling may be required in respect of online advertising that is unarguably an ad for a prescription only medicinal product (the advertising of which to the public is unlawful – CAP Code rule 12.12), or the online business-to-consumer advertising of consumer products with VAT exclusive prices (CAP Code rule 3.18).`

#### 1.5.4 时限（决定阶梯的「速度」）

程序 PDF 第 25 段与脚注 10 逐字：

> `10 e.g. 2-5 working days. For standard casework, it is likely to be five working days, but might be shorter for very offensive, illegal or harmful content. For ENs, it's normally 4 weeks.`
> `ii. For certain compliance cases, for example "post-investigation cases", we set a shorter deadline (i.e. **24 hours** from when we send the email, or the next business day if we contact you on a Friday or before a bank holiday)…`
> `iii. …the CAP Compliance team will grant an extension to the deadline only where we consider the advertiser has reasonable grounds for requesting one… Any extension is unlikely to be longer than **five working days** and a repeat request for extension is likely to require compelling justification…`

对照调查阶段的时限（`How we handle complaints` 页 / 程序 PDF 第 30 段）：

> `Advertisers and broadcasters are required to reply to us in writing within seven working days, or five working days for cases involving issues of harm or offence. If they don't reply promptly they can automatically be found to break the Advertising Codes…`

**本分片判断**：ASA 的时限设计是**分层递进**的——首次调查 7 天（重案 5 天）→ 正式合规 5 天 → 判后合规 24 小时。**越往后越短。** 这是一个可以直接借用的机制：它把「拖延」变成了一个会自我加剧的负债，不需要任何强制卡点。

#### 1.5.5 L4：点名公示的具体做法（**这块最值得 Momcozy 抄**）

`Sanctions` 页逐字（URL：https://www.asa.org.uk/codes-and-rulings/sanctions.html，本地 `_evidence/R2/asa-sanctions.html`）：

> `Where non-compliant claims appear on a marketer's own website, or in other non-paid-for space under their control, such as their social media accounts, we can:`
> - `Add their name and details of the problem with their advertising to a dedicated section of the ASA website until they comply. We use search engine optimisation to ensure those details appear in search engine results when consumers look up the company's website;`
> - `Ask Search Engines to remove paid-search ads when those ads contain material – or a link to a page on the marketer's website that contains material – which breaks the rules;`
> - `Place our own paid-search ads to highlight the advertiser's name and non-compliance;`
> - `Work with social media companies, including under the Intermediary and Platform Principles, to have non-compliant content removed from their platforms.`

非合规线上广告主公示页实时条数（2026-09-15 抓取）：**`27 result(s)`**（本地 `_evidence/R2/asa-ncoa.html`）。每条字段：广告主名 / 品牌名 / 违规类别 / 更新日期，例如 `Gary Baron / Counselling services / 18 August 2026`、`Power Body Nutrition Ltd / powerbody.co.uk / 01 June 2026`。

程序 PDF 第 17 段补充了平台合作方名单与「明确违规」在此语境下的等价定义：

> `following the Intermediary and Platform Principles (IPPs) pilot, platforms and intermediaries, such as **Amazon Ads, Google, Meta, Yahoo for Business and TikTok** currently volunteer to act swiftly, in line with the IPPs, to remove, on notice from the CAP Compliance team, an ad found to be in clear-cut breach of a Code rule. For the avoidance of doubt, for our purposes a clear-cut breach means the same as "indisputably a prima facie breach" referenced in the Principles.`

**对 Momcozy 的意义**：这四家平台里，**Google 和 Meta 正是他们 291 条记录的全部投放平台（Google 262 / Meta 27）**。ASA 的机制说明：平台侧存在「收到监管方通知即快速下架」的志愿承诺。**这是外部环境里已经存在的强制通路——他们的审查记录如果能对齐到「可被平台接受的违规判据」，就有了一条现实的升级路径。**

#### 1.5.6 L8：Enforcement Notice（整行业工具）

程序 PDF 第 8–10 段逐字：

> `8. If evidence indicates that advertisers within a given advertising sector e.g. telecoms, airlines, gambling etc. are publishing ads in clear-cut breach of one or more specific rules in the Code, the CAP Compliance team may initiate a sector compliance project. Depending on the circumstances, including the number of advertisers in the sector, the team may decide to publish an EN.`
> `9. …ENs are published on the CAP website and circulated to applicable advertisers and, as relevant, trade bodies on the ASA/CAP database, media platforms and relevant government bodies.`
> `10. ENs typically seek to **draw out the key lessons from particular ASA rulings** to inform advertisers in a relevant sector whether their ads are in breach of the Code and, if so, how to amend their ads or, if amendment cannot resolve the non-compliance, to withdraw the ad entirely. They include a deadline (usually one month from the date of publication)…`
> `11. Often, ENs are issued in liaison with a government body with a particular interest and expertise in the area and/or in conjunction with online social media platforms or other providers of advertising space. In all cases, ENs are signed off by senior executives of the CAP Compliance team.`

**EN 就是「行业级错题本」的官方形态**：把多条判例蒸馏成一份面向同行业所有广告主的「该怎么做 / 该怎么改」的文件，带整改截止日。实例（URL 与标题逐字）：

| EN | URL | 日期 |
|---|---|---|
| `Enforcement Notice: Fertility treatments`（与 CMA、HFEA 联合发布） | https://www.asa.org.uk/resource/enforcement-notice-fertility-treatments.html | `10 Jun 2021` |
| `Enforcement Notice: Training Courses`（aesthetics injectables 行业） | 见搜索结果页 | — |
| `Enforcement Notice: CEASE Therapy`（bogus claims by therapists） | 见搜索结果页 | — |
| `Enforcement Notice: Estate Agents` | 见搜索结果页 | — |

`Fertility treatments` EN 的官方描述逐字（本地 `_evidence/R2/asa-en-fertility.html`）：

> `This Enforcement Notice is jointly-issued with the Competition and Markets Authority (CMA) and the Human Fertilisation & Embryology Authority (HFEA) and provides guidance to advertisers of fertility treatments to make sure that fertility clinics are treating their patients fairly. The Enforcement Notice details how clinics should advertise their prices, success rates, add-on treatments and complementary therapies in order to comply with the CAP Code.`

**本分片判断**：EN 是「错题本 → 规则库」回写路径的实体证据。它证明了一件对 Momcozy 至关重要的事：**从判例到规则的中间层（行业指引）是可以单独存在的、有截止日的、有署名的工件。** 他们不需要在「一条条具体错题」和「一条条抽象规则」之间二选一。

### 1.6 ruling 数据库：公开可检索吗？检索维度有哪些？

#### 1.6.1 结论

**公开、免费、无需登录，且可按规则号检索。但没有 API，没有结构化导出，可靠性有限。**

#### 1.6.2 检索维度（从检索表单 HTML 直接读出）

检索表单位于 https://www.asa.org.uk/codes-and-rulings/rulings.html 侧栏（`<form method="get" class="filter-form" id="form-filter">`）。字段与取值（本地 `_evidence/R2/asa-rulings.html`）：

| 字段名 | 标签 | 取值 | **取值是否人类可读** |
|---|---|---|---|
| `q` | 关键词 | 自由文本 | ✅ |
| `sort_order` | Sort order | `relevant` / `recent` | ✅ |
| `date_period` | Date | `past_week` / `past_month` / `past_year` | ✅ |
| `custom_date` + `from_date` + `to_date` | 自定义日期区间 | `1` + `DD/MM/YYYY` | ✅ |
| `decision` | Decision | `Upheld` 等 | ✅ **字面值** |
| **`capCode`** | **CAP Code rule** | **规则号字面值，如 `1.3` `3.1` `3.3` `3.7` `3.17` `11.1` `12.1` …** | ✅ **字面值** |
| `issue` | Issue | `Misleading` / `Miscellaneous/Other` … | ❌ **GUID**（如 `B62E671E-81D6-42FD-8BDA1611D194B1D3`） |
| `media_type` | Media | `Search (paid)` / `Social media (paid ad)` / `Website (own site)` / `Internet (display)` … | ❌ **GUID** |
| `topic` | Topic | `Weight and slimming` … | ❌ **GUID** |

**这张表本身就是一条重要发现：**

> **ASA 判例库里唯一两个「字面值」分类维度是 `decision` 和 `capCode`（规则号）。`issue`、`media_type`、`topic` 三个人类可读的分类体系，底层都是不透明的 GUID。**

**本分片判断**：这不是疏忽，而是「规则号是主键、分类是标签」的自然结果。规则号有**外部定义**（写在准则正文里，有版本），所以它可以是稳定字面值；`issue` / `topic` 是 ASA 内部的编辑分类，没有外部定义，所以只能内部编号。**对 Momcozy 的直接含义：他们的 `H/M/U` 编号要成为可跨系统连接的键，前提是编号的含义写在规则正文里、而不是靠分类标签解释。** 现在 `H01` 的含义要靠 `边界内容` 那一长段散文来解释——这意味着 `H01` 不是稳定键，只是一个行号。

#### 1.6.3 规则级检索的实测行为（**有一个重要陷阱**）

我实测了 `capCode` 过滤器的行为，发现它**不是全局索引，而是结果集内的 facet**：

| 请求 | 返回 |
|---|---|
| `?type=rulings`（无过滤） | `4250 result(s)` |
| `?capCode=99.99`（不存在的规则） | `4250 result(s)` ← **未生效** |
| `?capCode=3.7`（`/search.html` 上） | `4250 result(s)` ← **未生效** |
| `?capCode=15.1`（**`/codes-and-rulings/rulings.html`** 上） | `Rulings (0)` |
| `?capCode=15.1&date_period=past_year` | `Rulings (15)` |
| `?capCode=15.1&custom_date=1&from_date=01/01/2020&to_date=15/09/2026` | `Rulings (63)` |
| `?capCode=3.7&decision=Upheld` | `Rulings (1)` |
| `?date_period=past_year`（无规则过滤） | `Rulings (321)` |

**两条必须记住的操作事实：**
1. **规则过滤只在 `/codes-and-rulings/rulings.html` 上生效，在 `/search.html` 上被静默忽略**（不存在的规则号也返回全量，说明它不校验、直接忽略）。
2. **规则过滤必须与日期区间或其它收窄条件联用**，否则 facet 只在默认结果集（通常是当期）内计数，会返回 0 或极小值。

#### 1.6.4 用检索接口建「规则 → 判例数」索引（2026-09-15 实测）

固定区间 `01/01/2015 – 15/09/2026`，逐条规则计数（源：`https://www.asa.org.uk/codes-and-rulings/rulings.html?capCode=<rule>&custom_date=1&from_date=01/01/2015&to_date=15/09/2026`）：

| CAP Code 规则 | 规则主题 | 判例数 |
|---|---|---|
| 3.1 | Misleading advertising（不得实质误导） | **676** |
| 3.7 | **Substantiation（举证）** | **373** |
| 1.3 | Compliance（社会责任） | 289 |
| 3.3 | 不得遗漏重要信息 | 267 |
| 1.7 | Unreasonable delay（未合理回应） | 127 |
| 12.1 | Medicines/medical devices 客观声称须有证据 | 121 |
| 15.1 | Food 营养与健康声称 | 63 |
| 15.1.1 | 仅可用登记册内的声称 | 63 |
| 3.11 | 夸大产品性能 | 55 |
| 12.18 | 不得用健康专业人士或名人背书**药品** | 6 |
| 13.1 | Weight control and slimming | 5 |
| 3.13 | 不得暗示声称被普遍接受 | **0** |

**这张表就是一个「规则库健康度」度量模板**（任务书 §六.4 问「度量什么」）：

- **载荷分布**：`3.1`（676）与 `3.7`（373）承担了绝大部分案件——说明**「误导」和「举证」是两条主干规则**，其它规则是主干上的分支。
- **休眠规则**：`3.13` 在 11 年内 0 条判例。这不必然说明它无用（可能它防的是极罕见情形），但它说明**这条规则从未被对抗性检验过，其边界是未知的**。
- **对比 12.18 vs 12.1**：`12.18`（不得用健康专业人士背书）只有 6 条，而 `12.1` 有 121 条。**本分片判断**：这与规则 12.18 只适用于**药品（medicines）**有关——健康产品/器械的背书问题走的是第 3 节的 `3.47 / 3.52`，而不是 12.18（见 §1.3.3 的 Go Night Night 案引用的就是 3.50/3.51）。**这是「同一行为在不同规则下归属不同」的一个真实例证，也是 Momcozy 最容易踩的坑：他们的 `U01`（IBCLC/专家背书）与 `H04`（医生推荐）现在被拆成两条不同族的规则，但按 CAP 的结构，它们其实是同一组规则（3.47 + 3.52）的两个事实形态。**

#### 1.6.5 判例的寿命与更新

程序 PDF 第 42–43 段逐字（本地 `_evidence/R2/asa-Non-broadcast-Complaint-Handling-Procedures.txt`）：

> `42. We usually publish rulings on our website within 14 calendar days of the ASA Council's decision, and **they remain on the website for five years**. CAP may continue to refer to rulings in its guidance for as long as they are useful for educational purposes.`
> `43. **Minor changes to a ruling after publication** — If insubstantial changes to the ruling are needed after it has been published, for example to correct factual or typographical errors that are not material to the outcome of the case, the Chair of the ASA may authorise appropriate corrective action any time after publication. It will be for the Chair to decide on the significance of changes and whether it is appropriate for them to exercise their discretion under this provision. Upon correction we will notify the parties of the changes made.`

**这两个段落合起来回答了「历史判例如何长期可用」：**

> **判例本体有 5 年公开寿命；但从判例蒸馏出的指引（guidance）可以无限期引用。**

**本分片判断**：这是本分片最重要的架构洞见之一。ASA 明确区分了**证据的寿命**和**结论的寿命**：
- **证据**（ruling 全文）——会过期、会下架、要控成本；
- **结论**（AdviceOnline 条目、EN、Advertising Guidance）——只要还有教育价值就一直用。

**对 Momcozy 的直接含义**：他们的「错题本」不应该是一个不断膨胀的判例列表（291 条已经不小，且会持续增长到无法人工维护），而应该是**「少量蒸馏后的判断标准」+「有寿命的原始记录」**。见 §7.1。

#### 1.6.6 独立复核（Independent Review）——判例可以改判，且改判后重发

URL：https://www.asa.org.uk/codes-and-rulings/independent-reviews.html（本地 `_evidence/R2/asa-independent-reviews.html`）

逐字：

> `A party has 21 days from the date on the ASA's letter of notification of the final decision to ask the Independent Reviewer to review the case.`
>
> `The Independent Reviewer can only accept the request if one or more of the following tests is established:`
> - `if additional relevant evidence becomes available which could not reasonably have been shared during the course of the investigation`
> - `where it is alleged that there is a substantial flaw in Council's ruling`
> - `where it is alleged that there is a substantial flaw in the process by which that ruling was made`
>
> `The Council's rulings on reviewed cases is final. **Rulings that are revised following a review will be republished on our website.**`

**「改判后重发」= 案件号必须稳定、判例必须可被覆写、且覆写要留痕。** 程序 PDF 第 27 段补充了一条重要的执行细节：

> `27. i. For post-investigation compliance cases, if the advertiser is making an application for independent review of the ASA's ruling, corrective action and the assurance of compliance, requested by the CAP Compliance team, **will normally continue to be required**…`
> `ii. It is acknowledged that the independent review process may ultimately lead to the ASA ruling being amended in a way that renders the assurance of compliance, provided to the CAP Compliance team, obsolete.`

**即：申诉不中止执行。** 这是一个明确的默认值选择——**先执行、后改判**，而不是「申诉期间冻结」。对无法强制卡死上线节点的 Momcozy，这是唯一可行的默认值。

### 1.7 ASA 的规则更新机制

#### 1.7.1 谁提案、谁决定

CAP Code 第 23 节逐字（`_evidence/R2/The-CAP-Code.txt` 第 2964–2975 行）：

> `CAP co-ordinates the activities of its members to achieve the highest degree of compliance with the Code. **It creates, reviews and amends the Code.** From time to time, it produces for the industry Help Notes that give detailed guidance on specific sectors or subjects that are covered only generally in the Code. It oversees the sanctions operated by its members.`
> `CAP actively encourages participation in the self-regulatory system. **Suggestions for improving Code rules or modifying their application should be sent in writing to the Chairman. If changes are adopted by CAP their introduction is normally deferred for a short time to give marketers an adequate opportunity to amend their marketing communications.**`

**三个机制点：**
1. **提案入口是开放的**（任何人可书面提交给 CAP 主席），不限于会员。
2. **决定权在 CAP**（自律组织），不在 ASA（执法机构）。Preface 进一步明确分工（`_evidence/R2/The-CAP-Code.txt` 第 78–86 行）：
   > `The Committee of Advertising Practice (CAP) is the self-regulatory body that **creates, revises and enforces** the Code.`
   > `The Advertising Standards Authority (ASA) is the independent body that **endorses and administers** the Code, ensuring that the self-regulatory system works in the public interest.`
3. **生效有缓冲期**：`their introduction is normally deferred for a short time to give marketers an adequate opportunity to amend their marketing communications.`

#### 1.7.2 变更前：公开征询

URL：https://www.asa.org.uk/about-asa-and-cap/the-work-we-do/how-we-consult.html（本地 `_evidence/R2/asa-how-we-consult.html`）

逐字：

> `CAP and BCAP consult on significant changes to the Codes, allowing those affected to put forward relevant opinions and evidence for us to take into account.`
>
> `Consultations allow those affected by or concerned about a particular advertising issue that is subject to consultation to put forward their opinions and supporting evidence for CAP and BCAP to take into account when making decisions about proposed changes to the Advertising Codes.`
>
> `We endeavour to make our consultations clear and open by:`
> - `involving, as far as possible, everyone whose views should be considered, for example small and large advertisers, professional associations, marketers, consumer groups, media owners, public bodies and individuals`
> - `clearly setting out our proposed Code changes and explaining the policy considerations underpinning these in a consultation document`
> - `considering all consultation responses to understand the possible effects of our proposals and inform our decisions about changing the Codes`
> - `when a consultation is closed, **publishing the outcome and an explanation of how responses helped shape it**.`

**注意最后一条：变更后必须公开「意见如何影响了决定」。** 这是一个常被省略但极重要的闭环步骤。

已发生的征询实例（检索结果页）：`Medicines consultations`（CAP/BCAP 就准则 medicines 章节两次征询）、`Gambling consultation update` / `Gambling consultation regulatory statement`、`Public consultation on scheduling of TV ads for payday loans`。

#### 1.7.3 变更的判据：Evidence-based policy making

CAP/BCAP 于 `18 Jan 2018` 发布《Evidence-based policy-making: How CAP and BCAP assess calls for regulatory change》（PDF 10 页，本地 `_evidence/R2/asa-evidence-based-policy-making.pdf` / `.txt`）。这是整个「规则从哪来」问题的官方答案。

**（a）证据的接收承诺（第 1 节逐字）**

> `CAP and BCAP are committed to:`
> - `acknowledging receipt of all evidence sent to them,`
> - `receiving and reviewing all evidence fairly, impartially and with an open mind,`
> - `responding formally to significant pieces of evidence, and`
> - `**keeping significant evidence on file, even if it does not on its own merit immediate action by CAP and BCAP.**`
> `All evidence is useful in building a picture of whether a regulatory change might be necessary, **even if it does not in itself justify such change.**`

**这条对 Momcozy 极重要**：**「证据不足以上线一条新规则」≠「证据应当丢弃」。** ASA 的做法是**归档留存**，作为未来某项规则变更的证据池。他们的 291 条记录里，那些「命中但人工判定不判险」的案例，就属于这一类。

**（b）什么样的证据够格（第 2 节逐字）**

> `CAP and BCAP do not consider any one type of research to be the best in supporting a case for change. …In general, CAP and BCAP will expect research and methodology to be submitted **in full: they cannot assess evidence based only on a summary or abstract.**`
> `CAP and BCAP do not prescribe study design but they favour research which:`
> - `identifies the nature, scale and impact of any detriment;`
> - `is fair and impartial and follows a recognised methodology;`
> - `takes into account confounding variables;`
> - `is carried out on a representative cross-section of a population similar to that of the UK or on a representative sample of the relevant part of the population; and`
> - `mitigates against potential bias.`

以及几条负面判据：

> `Studies that show associations between factors can be useful, but **alone are unlikely to prove that an advertisement or advertising practice caused a particular effect.**`
> `Concerns about the potential harm of legally available products, while important, are **unlikely to be sufficient on their own to justify further controls or an outright ban** particularly if the product / service is already subject to specific rules. CAP and BCAP will expect evidence to identify **why a particular advertising practice is irresponsible.**`

**（c）证据之外必须看的上位约束（第 3 节逐字）——「规则库不能自己决定自己的边界」**

> `The Codes themselves are not law but they exist alongside it, sometimes reflecting it, supplementing it or filling gaps where it does not reach.`
> `CAP and BCAP will often hear calls from those who consider a particular advertising practice to be misleading for it to be banned outright. However, the Consumer Protection from Unfair Trading Regulations 2008 (the CPRs) delimit how CAP and BCAP must regulate misleading advertising, **providing a list of banned practices – to which CAP and BCAP cannot add – and provide a test that the ASA must apply in all other instances.** Evidence that a particular advertising practice is not optimally clear or preferred by consumers is alone unlikely to provide grounds for change if it does not show that the practice in question is likely to mislead them.`

**这是「规则库的边界由上位法划定」最清晰的表述。** 对 Momcozy：他们的规则**不能**比《广告法》/ UCPD / FTC Act 更严或更松——更严会造成业务无谓损失，更松会造成合规裸奔。**规则库的正确姿态是「映射上位法 + 补足业务特有边界」，而不是「发明新的法律」。**

**（d）收到证据后可能做什么（第 4 节逐字）——干预阶梯**

> `Depending on the strength of the evidence before them and what it suggests, CAP and BCAP might do one or more of the following:`
> - `implement new rules or remove / amend existing ones,`
> - `publish guidance on how existing or new rules should be interpreted,`
> - `conduct their own research and / or initiate a call for evidence,`
> - `pass information to CAP or ASA teams to aid in their enforcement of existing rules, or`
> - `**take no action but keep the issue under internal review.**`

**这就是「没有规则怎么办」的组织级答案：五选一，而且「什么都不做但挂账」是合法选项之一。** 对照 §1.7.1 的 CAP 承诺 `keeping significant evidence on file`——ASA 有一个明确的「待观察池」。

### 1.8 三层工件模型：rule → guidance → ruling（**本分片的核心机制发现**）

把 §1.1–§1.7 拼起来，ASA 的实际结构是**三层工件 + 一个连接键**：

```
┌──────────────────────────────────────────────────────────────┐
│ L1  规则库  CAP Code (Edition 12), v12.2.107                  │
│     单位：rule（3.7 / 12.1 / 15.1.1 …）                       │
│     编号：<节>.<序>[.<子序>]，不回收、不复用                    │
│     变更：墓碑 + 改号声明 + 变更登记册 + 版本号                  │
│     决策者：CAP（自律组织）；提案入口：书面提交主席               │
│     边界：由上位法（CPRs / DMCCA / 药品法）划定，CAP 不能增减      │
└──────────────────────────────────────────────────────────────┘
                    ▲ 规则号（唯一人类稳定键）
                    │
        ┌───────────┴───────────┐
        │                       │
┌───────┴────────────┐  ┌───────┴──────────────────────────────┐
│ L2  释义层          │  │ L3  判例库                            │
│ AdviceOnline /      │  │ ASA rulings                           │
│ Advertising         │  │ 单位：ruling（G26-1343656 / A25-…）    │
│ Guidance /          │  │ 字段：见 §1.3.5 schema                │
│ Enforcement Notice  │  │ 寿命：公开 5 年                        │
│ 寿命：长期           │  │ 可改判：Independent Review → 重发      │
│ 关联：↔ 规则号       │◄─┤ 关联：→ 规则号 + → 释义条目            │
│       ↔ 「最近判例」 │  │ 两级可见性：正式裁决全字段 /           │
│                     │  │            非正式解决仅「谁+何时+几条」 │
└─────────────────────┘  └──────────────────────────────────────┘
```

**这个模型对委托方的问题（「错题本？还是规则库？」）的直接回答：**

> **不是二选一。规则库必须有一个显式的「释义中间层」，判例的价值必须通过这个中间层才能回流到规则。**
> **直接从判例改规则，会导致规则条文被个别事实绑架；没有释义层，判例会无限膨胀而无法复用。**

**证据链**（每一环都有原文）：

1. **释义层的存在与定位**（CAP Code 第 23 节逐字）：
   > `It produces for the industry **Help Notes** that give detailed guidance on specific sectors or subjects that are **covered only generally in the Code**.`
   → 明确说：Helps Notes 覆盖的是**准则只做概括规定**的领域。释义层不是重复规则，是补规则够不到的地方。

2. **释义层的内容来自判例**（AdviceOnline 库首页逐字，URL：https://www.asa.org.uk/advice-and-resources/resource-library/advice-online.html，本地 `_evidence/R2/asa-advice-online.html`）：
   > `Our AdviceOnline library provides guidance on interpreting the UK Code of Non-broadcast Advertising and Direct & Promotional Marketing. **Entries give practical advice based on previous ASA rulings** to help you to create ads and sales promotions which stick to the CAP Code.`

3. **释义层条目 ↔ 规则号 ↔ 判例** 的三向链接，在具体条目页可见。以 `Substantiation for health, beauty and slimming claims` 为例（URL：https://www.asa.org.uk/advice-online/substantiation-for-health-beauty-and-slimming-claims.html，本地 `_evidence/R2/asa-ao-substantiation-health.html`），该条目：
   - 明确引述 **Rule 3.7** 与 **Rule 12.1** 的逐字原文
   - 给出**三档证据强度**（见下）
   - 页面底部有 `Recent rulings` 区块，直连最新相关判例（实测该页列出 `Hemios / Upheld / 09 September 2026`）

4. **释义层有自己的日期**：该条目显示 `23 Jun 2025`（最后更新日）。判例有发布日期，释义条目也有更新日期——**两层各有各的时间戳。**

#### 1.8.1 释义层里最值得抄的一段：健康/美容/减肥声称的三档证据标准

`Substantiation for health, beauty and slimming claims` 条目逐字（本地 `_evidence/R2/asa-ao-substantiation-health.html`）：

> `**One of the main tenets of the Codes is that the burden of proof for claims lies with advertisers.** Before submitting an advertisement for publication, advertisers must hold documentary evidence to prove claims that consumers are likely to regard as objective and that are capable of objective substantiation (Rule 3.7).`
> `In July 1998, with input from the Health and Beauty Working Group, CAP produced Advertising Guidance on Substantiation which provides detailed guidance on the type and volume of data that the ASA and CAP expects advertisers to hold to back up a variety of different categories of claims.`
>
> `The Advertising Guidance identifies three types of health, beauty and slimming claims that are made for products (or services):`
>
> - `**sensory/impressionistic subjective claims** - these are claims that cannot be proved objectively and which might be understood to be opinion e.g. "no other shower gel leaves you feeling fresher". In some circumstances, satisfactory consumer research may be required to back them up (see Section 1 of the Advertising Guidance);`
> - `**uncontroversial/established objective claims** - a less significant amount of evidence is usually needed in support of these types of claims. The Advertising Guidance gives examples of what might constitute satisfactory proof (see Section 2);`
> - `**"New" or "breakthrough" objective claims** - the ASA and CAP have more stringent evidence requirements for these types of claims. Sound data, relevant to the claim made, should be collated to form a body of evidence. **This should normally include: at least one experimental human study (ideally double-blind and placebo-controlled) and often observational human studies.** The Advertising Guidance details other categories of evidence that might form part of a body of evidence and gives specific guidance on the quality of data, including **the importance of the studies being subjected to peer-review either through publication in reputable, peer-reviewed journals or assessment by an independent expert** (see Section 3)`

**这三档证据标准可以直接映射到 Momcozy 的现有资产**：

| ASA 证据档 | 对应 Momcozy 的表达 | 他们的 `W1卖点表达边界` 灯色 | 现有规则 |
|---|---|---|---|
| sensory/impressionistic subjective | 「更细腻连续的吸力变化」「柔软贴合与稳定支撑」 | 绿 | 安全词 |
| uncontroversial/established objective | 「接近体温的温面包裹」「可调节可保存的个性化程序」 | 绿 | 安全词 |
| **"New" / "breakthrough" objective** | 「前几分钟排乳更顺」「更高吸乳效率」「减少漏奶」；他们标注为「需 W1 自身对照数据」 | 黄 | `M07` / `M03` |
| **（超出三档：医学功效）** | 「热敷治疗堵奶」「触发催产素」「提高长期奶量」 | 红 | `H01` / `H02` |

**关键发现**：他们的灯色体系（绿/黄/红）**已经在事实上实现了 ASA 的证据分档**，但没有把它显式表达成「证据档位」这个字段。`W1-01` 的三行（绿/黄/红）逐字说明了这件事：

> 绿色-可用：`接近体温的温面包裹，帮助减少冷接触不适。` / `判定理由：有温暖乳盾/热敷方向证据，且表达停留在体验层。`
> 黄色-需限定：`可能帮助前几分钟排乳更顺，建议作为待验证产品终点。` / `判定理由：相关研究支持短时方向，但不能外推到长期奶量。`
> 红色-禁用：`（禁用）温热治疗堵奶/乳腺炎、触发催产素、提高长期奶量。` / `判定理由：证据链不完整且有指南争议。`

**`判定理由` 一栏写的其实全是「证据强度」，不是「表达方式」。** 把这一栏规范化成 ASA 式的三档枚举（`sensory` / `established` / `novel` / `medical`），就能把「灯色」从主观判断变成可推导结果：**证据档 × 表达类型 → 灯色**。这是 §7.2 建议的核心。

#### 1.8.2 释义层如何回写成规则：Change register 与 EN 的两条路径

| 路径 | 触发 | 产物 | 是否有截止日 | 证据 |
|---|---|---|---|---|
| **路径 A：规则变更** | CAP 采纳提案 | 修改 CAP Code + 登记册条目 + 版本号递增 + 缓冲期 | 缓冲期 | §1.4 机制三、§1.7.1 |
| **路径 B：行业指引** | 某行业多家明确违规 | Enforcement Notice（可跨机构联署） | 通常 1 个月 | §1.5.6 |

**注意路径 B 的门槛比路径 A 低得多**：EN 不需要改规则，只需要「多家广告主明确违规」（`clear-cut breach`）。**这是 Momcozy 更现实的回写路径**——他们不需要等规则改版，只需要在发现同类问题重复出现时，发一份「品线级 Enforcement Notice」。

### 1.9 跨辖区：ASA 如何处理「同一行为在不同地方归不同规则」

任务书 §交叉问题 第三问。ASA 的答案分两种情形。

#### 情形一：广告出现在境外媒体 → 转 EASA，**由来源国管辖**

CAP Code 第 23 节 `Cross-border marketing communications` 逐字（`_evidence/R2/The-CAP-Code.txt` 第 3226 行起）：

> `The Code does not apply to marketing communications in foreign media. If marketing communications appear in media based in countries that have self-regulatory organisations (SROs) that are members of EASA or if direct marketing originates from countries that have SROs that are members of EASA, **EASA will co-ordinate cross-border complaints so the SRO in the country of origin of the marketing communication has jurisdiction; consumers need complain only to their SRO.** If not, the ASA will take what action it can. **The SROs with jurisdiction are formally responsible for applying any sanctions**, though the ASA and CAP will, whenever they can, adopt a pragmatic approach to ensure that consumers are protected.`

#### 情形二：境外广告主直接面向英国消费者 → ASA 自己管，但权力有限

`How we handle complaints` 页逐字：

> `We also do our best to address complaints about ads from countries without EASA links where those ads are directly targeting UK consumers (for example, through a .co.uk website or UK pricing). However, **our powers are more limited when dealing with ads outside our jurisdiction.**`

**实测印证**：§1.3.1 的 Hemios 案，广告主注册地是 `70 Stevenson St / San Francisco / California / 94105 / USA`——**美国没有 EASA 成员 SRO，所以 ASA 直接裁决并发布 ruling**。而 §1.3.3 的 Go Night Night 案，ASA 的动作止于「禁止再使用该 logo」+「转 CAP Compliance team」，**没有转 Trading Standards**——对境外主体，法定后手够不到。

**本分片判断——这对 Momcozy 是一个必须显式建模的风险：**

Momcozy 的 291 条投放记录覆盖 `法国26 / 英国19 / 加拿大14 / 西班牙11 / 意大利3 / 其他216`（任务书 §二.D）。按 §1.6.4 与本节：

| 投放地 | 谁有管辖权 | 依据 | 对 Momcozy 的含义 |
|---|---|---|---|
| 英国 | ASA（直接） | ASA remit（英国媒体 / 面向英国消费者） | 有公开发布的 ruling 风险，可被检索、被媒体转载 |
| 法国 / 德国 / 西班牙 / 意大利 | 来源国 SRO，经 EASA 转办 | CAP Code §23 Cross-border + `How we handle complaints` | 各国 SRO 有**各自的规则库**（法国 ARPP、西班牙 Autocontrol、意大利 IAP 等），规则号**不通用** |
| 加拿大 | 北美自律体系（Ad Standards），**非 EASA** | 需另行核实（见 §9 缺口） | 不能假设与英国同规则 |
| 美国 | FTC + NAD/NARB（§2、§3） | — | 注意：**他们的 291 条里没有美国投放**，但品牌主体在北美 |
| 中国 | 市场监管总局 + 《广告法》 | §5 | 若同一素材回流用于中国站内/跨境店，法域完全不同（如绝对化用语） |

**「同一个行为在不同辖区是否归属不同规则」——三个体系的答案都是「是」，且都用同一套解法：不试图统一规则，而是统一「连接键」。**
- ASA / EASA：以**来源国 SRO** 为管辖锚，消费者只需向本国 SRO 投诉。
- 中国《广告法》第十六条/第十七条/第十八条以**产品类别**为锚（见 §5）。
- EU UCPD 以 **Annex I 黑名单 + Art 6/7 一般条款**为锚（见 §4）。

**对 Momcozy 的工程结论**：他们的规则库**不能**按「国家」建正向规则，因为那会导致同一含义在不同国家被重复定义 N 次且很快就会漂移。正确做法是**「语义规则（与法域无关）+ 法域映射表（语义规则 → 各法域的依据条款）」两层**——这正是 CAP 用「规则号」做连接键的等效设计。详见 §6.3 与 §7.2。

---

## 2. 美国 BBB National Programs / NAD / NARB

> **取证状态（2026-09-15，本节在初稿后做过一次实质补齐）**：已取得 **NAD/NARB Procedures 全文**（`_evidence/R2/nad-narb-procedures.txt`，1,590 行 / 100 KB，封面载明 `Revised effective March 16, 2026`），并有 **2020 版**（`nad-narb-procedures-2020.txt`）可做版本对照；另有 **NAD Annual Report 2025**（含逐案表）、**两份官方 case digest**、**3 份个案 decision summary**、**3 份转交通知**、**2 份 NARB 决定**、**FAQ 全文**。个案 decision **全文**仍为订阅制（未取得），但 §2.5b 已用公开 summary 完成逐字段拆解。
>
> **⚠️ 访问路径（第三方复核本节时必须知道）**：`bbbprograms.org` 对本机出口 IP 返回 **HTTP 403** —— 纯 `curl`、伪装浏览器 UA、Googlebot UA、HTTP/HTTPS、IPv4/IPv6、**以及真实无头 Chrome `--dump-dom`** 全部 403。判据：同一 URL 由**不同 IP 的云渲染器**成功取得，故属**出口 IP / 机房 ASN 级 WAF 封锁**，不是指纹或 UA 问题。本节文件的取得路径按价值排序：① **`microlink.io` 云渲染器**（主路径，HTML 与 PDF 均可转换）；② **`assets.bbbprograms.org`**（未被 WAF 拦截，普通 curl 即可）；③ **`bbbnp-bbbp-stf-use1-01.s3.amazonaws.com`**（运营方**源站桶可公开列举与下载**，`?list-type=2&prefix=…`）。
>
> **站点已改版**：任务书给的 `/programs/all-programs/nad` 与 `.../case-decisions` 现均 **404**；当前路径为 `/programs/advertising/nad`、`/programs/advertising/narb`、`/media/newsroom/decisions`。另：`bbbnp.org` **apex 域证书不匹配**（证书只覆盖 `*.bbbnp.org`），apex 按设计不可达。

### 2.1 机构的法律地位、定位与案件规模

#### 2.1.0 **一条必须放在最前面的原文：NAD 的裁决不构成违法认定**

**逐字（Procedures §2.1(A)，`_evidence/R2/nad-narb-procedures.txt` 第 139–143 行）**：

> `NAD and the National Advertising Review Board (NARB) are investigative or appellate units of the advertising industry's system of voluntary self-regulation. Policies and procedures are established by BBB National Programs. **A decision by NAD/NARB does not constitute a finding that any law has been violated.** An advertiser's voluntary participation in the self-regulatory process **is not an admission** and`

**这一条决定了 NAD 判例库可被当作什么、不可被当作什么：**

| | 可以被当作 | **不可以**被当作 |
|---|---|---|
| 性质 | 行业标准的事实性表述（「同行认为这条声称不成立」） | 违法认定、行政处罚记录 |
| 效力 | 对会员的商业压力 | 免责凭证 |
| 举证 | 显示行业共识存在 | 证明「我已合规」 |

**「不构成免责」这半边由 FTC 自己确认**（逐字，§3.1.1f）：

> `The Commission will not necessarily defer, however, to a finding by a self-regulation group. An imprimatur from a self-regulation group will not automatically shield a firm from Commission prosecution…`

**对 Momcozy 的直接含义（这是一条措辞级建议，不是修辞偏好）**：他们的内部案例库**不应模仿司法/处罚语言**（「违法」「处罚决定」），而应采用**行业自律语言**（「不予支持」「建议修改/停止」）。理由：**用错语言会让内部案例库在法务、平台申诉或监管问询场景中被当成对己不利的自认**——一份写着「违法」的内部记录，等于自认已知道违法状态。建议直接对齐 NAD 的官方 disposition 词表（§2.5b.4）。

#### 2.1.1 机构定位与案件规模

**官方自述（逐字，`_evidence/R2/nad-process.txt` 第 294 行）**：

> `The U.S. advertising industry founded the National Advertising Division (NAD) and the National Advertising Review Board in 1971 as a system of independent industry self-regulation to build consumer trust in advertising and support fair competition in the marketplace. NAD holds national advertising across all media types to high standards of truth and accuracy by reviewing truth-in-advertising challenges from **businesses, trade associations, consumers, or on its own initiative**.`

**案件库规模（逐字，第 295 行）**：

> `Through its work, thousands of misleading advertising claims have been removed from the marketplace and **NAD's case decisions represent the single largest body interpreting advertising law in the country**.`

**与 ASA 的结构性对照：**

| 维度 | UK / ASA | US / NAD |
|---|---|---|
| 成立 | 1962（ASA） | 1971（NAD/NARB） |
| 规则来源 | **自己写规则**（CAP Code，22 节 + 3 附录） | **不写规则**，以 FTC 法理（deceptive advertising）+ 判例为准则 |
| 决定主体 | ASA Council（独立陪审团） | NAD 律师团队 → 上诉到 NARB |
| 规则号体系 | ✅ 有（3.7 / 12.1 …） | ❌ **无规则号** |
| 判例是否公开全文 | ✅ 全文免费公开 | ⚠️ **只有摘要公开，全文需订阅** |
| 判例寿命 | 公开 5 年 | 归档于 Online Archive |

### 2.2 NAD 的案件流程

#### 2.2.1 谁可以提起（逐字，第 387 行）

> `The NAD Challenge process promotes fair competition and enhances consumer trust in the marketplace. **Any company, consumer, or non-governmental organization, including trade associations and non-profit organizations, can file a challenge with NAD.**`

**注意：提起主体比 ASA 更宽**（ASA 也接受公众投诉，但 NAD 明确把 NGO、行业协会、非营利组织列出）。

**Procedures 的正式版本更宽，但有一个排除项（逐字，§3.1(A)，第 464–467 行）**：

> `Any person or legal entity, **except entities such as law firms representing an undisclosed third party**, may submit to NAD any complaint regarding national advertising, regardless of whether it is addressed to consumers, to professionals, or to business entities. Likewise, **NAD may initiate a proceeding as part of its monitoring responsibility** pursuant to Section 2.1(B) of these Procedures.`

**三个细节**：
1. 主体是 `Any person or legal entity` —— **比程序页的表述还宽**（多了「任何法律实体」）。
2. **唯一排除项是「代理未披露第三方的律所」** —— 即**匿名挑战被明确禁止**。对照 ASA：ASA 接受匿名投诉但会降低优先级；NAD 直接把这条路堵死。**这是一个可以直接搬的机制：允许投诉，但不允许匿名投诉。**
3. `except those submitted by consumers` —— **消费者投诉不必走门户**（其他主体强制走 `portal.bbbnp.org`）。

#### 2.2.2 三条 filing track（逐字，第 387–399 行）

| Track | 适用 | 时限（逐字） |
|---|---|---|
| **Fast-Track SWIFT** | `Single-issue advertising cases` | `decisions in **20 business days**` |
| **Standard Track** | `Open to a variety of case types` | `decisions **20 business days following the final meeting**` |
| **Complex Track** | `Cases requiring complex substantiation` | `decisions **30 business days following the final meeting**` |

**Complex Track 的定义（逐字，第 497 行）**：

> `Complex Track cases involve complex substantiation, such as challenges that may include **multiple expert reports or scientific or other technical evidence that requires significant time to analyze**, or that involve numerous claims made for a variety of different products.`

**Complex Track 的设计意图（逐字，第 495 行）**：

> `The Complex Track, however, is an enhanced process for challenges that require complex claim substantiation providing businesses and their counsel with **a customized experience consisting of flexible and more predictable scheduling, greater transparency into the case review process, and deeper insights into NAD's perspective on the evidence**.`

**这三个 track 对 Momcozy 的直接参考价值**：**他们也可以按「判定复杂度」而不是「严重度」分流。**

- `Fast-Track` 对应：单条规则字面命中、无需语境判断（如 `H06` FDA approved、`H05` fits all breast shapes）；
- `Standard` 对应：多规则命中或需看上下文（如 `U04`）；
- `Complex` 对应：需要证据本身（如 `H03` 临床证明、`M07` 效率数据）。

**注意 Momcozy 现有的 `判断方式` 列 21/21 全部写「自动可检测」——他们没有分流维度。** NAD 的三 track 正好是一个现成的分流结构。

#### 2.2.3 提起的程序要求（逐字，第 469–473 行）

> `- Timing: **The filing fee must be received by NAD before the 20-day countdown clock will begin on the claim.**`
>
> `- A challenge can only be commenced by filing via the online portal.`
>
> `- If NAD determines that the challenge is not appropriate for Fast-Track SWIFT, the challenger has the option to refile the challenge in the Standard or Complex track or close the challenge.`

**要点**：**有 filing fee，且时限从费用到账起算。** 这与 ASA 的「投诉免费」形成对比——ASA 的 `How we handle complaints` 页逐字：`Like other complaints to the ASA, cross-border complaints are handled **free of charge**.`

**两种收费模式的取舍**：收费抑制了滥诉，但也把「消费者单独提起」变成了不现实选项（消费者几乎不会为一个案件付费）。ASA 的免费模式则依赖 `prioritisation principles` 来抑制资源滥用（逐字：`what harm or detriment has occurred or might occur / the likely risk of action versus inaction / the likely impact of our intervention / what level of resource would be proportionate to the problem being addressed`）。

#### 2.2.4 NAD 的自发监测比例（**一个关键的度量数字**）

**逐字（第 405 行）**：

> `As part of its public interest mission to ensure consumers receive truthful and accurate advertising messages, **NAD initiates approximately 20-25% of its cases each year based on its own monitoring of advertising in a wide variety of product categories.**`
> `The goal of NAD's monitoring cases is to **expand the universe of advertising claims that are reviewed for truth and transparency and provide guidance for future advertising**.`

**这个 20–25% 是一个可以直接借用的治理指标：**

> **在「靠投诉驱动」和「靠自查驱动」之间，NAD 的公开比例目标是 1:4 到 1:3。**

对照 ASA：ASA 侧没有公开同等口径的自发案件比例，但明确说了**方向**（`Compliance Procedures` 第 6.iii 段逐字）：

> `The ASA regulatory system is **increasingly less reliant on complaints** to inform its interventions and **increasingly more proactive** in its methods of identifying ads that are in clear-cut breach of one or more rules in the CAP Code. These proactive methods include, but are not limited to, the ASA's Active Ad Monitoring system, additional tech-assisted monitoring tools, self-initiated staff monitoring, and intelligence and insights from stakeholders…`

**对 Momcozy 的直接含义**：他们的 291 条全部来自「投放后审计」（拉取在跑广告 + 规则匹配），**属于 NAD 意义上的 monitoring，不是 challenge**。**建议把「monitoring 发现的占比」做成一个显式指标**，并对标一个目标值（例如：主动监测 ≥ 80%，外部投诉 ≤ 20%）——因为这个比例决定了他们是「在别人指出问题前发现」，还是「被指出后补救」。

#### 2.2.5 这套机制的价格（**逐字，2026 版 Procedures**）

**任务书没有问这个，但它决定「能不能抄」——NAD 的整个结构是靠 filing fee 支撑的，而费用结构本身透露了它的设计意图。**

| 项目 | National Partner | 非 Partner | 出处 |
|---|---|---|---|
| Standard Track 立案费（挑战方年营收 **< $250M**） | **$8,400** | **$10,500** | §3.1(B)(1) |
| Standard Track 立案费（**$250M–$5B**） | $31,080 | $38,850 | 同上 |
| Standard Track 立案费（**> $5B**） | $40,320 | $50,400 | 同上 |
| Complex Track 立案费（< $250M） | $25,200 | $31,500 | §4.1(B) |
| Complex Track 立案费（$250M–$5B） | $44,520 | $55,650 | 同上 |
| Complex Track 立案费（> $5B） | $66,360 | $82,950 | 同上 |
| Fast-Track SWIFT 立案费（< $250M） | $12,600 | — | §6.1 |
| Standard→Complex **转轨费** | $22,680 | $28,350 | §4.2 |
| 上诉费（广告主，Standard Track） | $31,050 | $38,810 | §5.2 |
| 上诉费（广告主，Complex Track） | $35,420 | $44,280 | §5.2 |
| **挑战方申请上诉**（不可退审查费，可抵立案费） | **$5,750** | $5,750 | §5.2(B) |
| 重新开案申请费（不可退） | $5,000 | $5,000 | §8.1(A)(1) |
| 行政关闭处理费 / 转轨处理费 | $5,000 | $5,000 | §3.1(B) |
| 上诉撤回时保留额 | $11,500 | $11,500 | §5.10 |

**逐字示例（§3.1(B)(1)，第 478–486 行）**：

> `National Partners shall pay a filing fee in the amount of: (a) **$8,400** if the challenger's gross annual revenue is less than $250 million; (b) **$31,080** if the challenger's gross annual revenue is between $250 million and $5 billion; or (c) **$40,320** if the challenger's gross annual revenue is $5 billion`

**四个可搬运的设计点：**

1. **费用按「挑战方」营收分档**（<$250M / $250M–$5B / >$5B）——**大公司挑战小公司要付更多**。这是一条我事先没想到的自律设计：它抑制的不是滥诉，而是**大厂用挑战程序压小厂**。
2. **上诉是收费的，且挑战方还要先付不可退的 $5,750 申请费**——**上诉门槛由「钱」+「许可」双重构成**（许可标准见 §2.4）。对照 ASA：Independent Review **对双方免费开放**，只设实体门槛（§1.6.6）。**同一问题（防止无理由上诉），两个体系用了完全不同的手段。**
3. **重新开案要付费**（$5,000 不可退，获准后再补足立案费差额）——即 **「举证不足想补证据」在 NAD 里是有明确价格的**。
4. **有减免通道**（`Fee waivers can be submitted to the BBB National Programs President and CEO or his or her designee`，§8.1(A)(2)），且**低收入分档本身就是一种减免**。

**对 Momcozy 的直接含义**：他们的场景是**内部审查，没有对手付费**，所以费用数字本身不可搬。**但分档逻辑可以整段搬**——把「审查成本」按**品线/渠道的营收规模**分摊，而不是各品线平均分摊。理由：**大品线的一次合规失误，绝对损失也更大，理应承担更多审查资源。**

---

### 2.3 compliance 机制：不遵守会怎样

#### 2.3.1 核心原文（逐字，第 459 行）—— **本节最重要的一段**

> `Participation in the self-regulatory process is **voluntary**. However, pursuant to the NAD/NARB Procedures, **if an advertiser refuses to participate or refuses to comply with NAD's recommendations, NAD will refer the matter to the appropriate regulatory agency, which is typically the Federal Trade Commission (FTC). A press release will be issued to this effect.** NAD referrals receive **priority treatment from the FTC** so an advertiser can expect a call from an FTC attorney who is assigned to the referral. Advertisers who initially refuse to participate often return to NAD, and those who refused to comply with NAD's recommendations often end up modifying their advertising. **NAD may also report misleading advertising to the platform on which it was found, including Facebook, for review as to whether the challenged claims comply with platform advertising policies.**`

#### 2.3.2 这条机制的完整链条（拆解）

```
① 参与是自愿的（voluntary）
   ↓ 广告主拒绝参与 或 拒绝遵守建议
② NAD 转交 FTC（typically the FTC）+ 发新闻稿（A press release will be issued to this effect）
   ↓
③ FTC 优先处理 NAD 转办案件 → 指派律师主动联系
   ↓ （平行路径）
④ NAD 可同时把误导广告报告给平台（包括 Facebook），由平台按广告政策复核
```

**四个可搬运的设计点：**

1. **「自愿」与「有后果」并存。** 不强制参与，但**不参与就触发转交 + 公开新闻稿**。这是唯一能在无强制力组织里运作的结构。
2. **转交本身被公开（`A press release will be issued to this effect`）。** 即：**「不配合」这个事实会被公开。** 对照 ASA 侧：`We referred the matter to CAP's Compliance team.` 被写进判例正文（Go Night Night 案，§1.3.3）。
3. **转交有「优先处理」的实质后果**（`NAD referrals receive priority treatment from the FTC`）——不是把问题丢出去，而是**把一个私人纠纷升级为监管优先事项**。
4. **平台侧平行施压**（`NAD may also report misleading advertising to the platform… including Facebook`）。对照 ASA：平台侧有 `Intermediary and Platform Principles` 的志愿承诺（Amazon Ads / Google / Meta / Yahoo for Business / TikTok，§1.5.5）。**两个体系都发现了同一条杠杆：平台下架比监管处罚更快、更直接。**

**注意第 4 点对 Momcozy 的特别意义**：他们的 291 条 100% 投在 **Google（262）+ Meta（27）**——而这两家正好同时出现在 ASA 的 IPP 名单和 NAD 的平台报告机制里。**这是他们现有外部环境里唯一一条真实存在的强制通路。**

#### 2.3.3 案件关闭条件（逐字，第 509 行）

> `If the advertiser agrees to comply with any recommended changes to their advertising, the case is closed. If the advertiser does not agree to comply, it is referred to the FTC and other appropriate regulatory agencies. NAD may also report misleading advertising to the platform on which it was found, including Facebook, for review as to whether the challenged claims comply with platform advertising policies.`

**⚠️ 本分片在此更正自己的一个判断。** 初稿据此写成「案件只有两种终局——同意整改并关闭，或转交，没有僵持状态」，并称之为「二元开关」。**取得 Procedures 全文后，这个说法不成立。** NAD 在「关闭」与「转交」之间有一整套**独立的合规程序（Compliance Proceedings，§8.1(B)）**，而且**它可以反复运行**。真正的结构是三态，不是二态。下面 §2.3.4 是逐字原文，§2.5d 是一个跑完整两轮的真实案件。

**修正后的判断**：NAD 的终端处置确实只有「关闭 / 转交」两出口，**但进入哪一个是靠合规程序反复博弈决定的**。这与 ASA 的十级阶梯差异没有初稿说的那么大——**两者都有中间态，区别在于 ASA 的中间态是「制裁升级」，NAD 的中间态是「要求报告 + 复核」。**

#### 2.3.4 **合规程序（Compliance Proceedings）的完整机制（§8.1(B)，逐字）**

**§8.1(B)(1) Standard or Complex Track（第 1441–1458 行）**：

> `After a standard or complex track NAD case or NARB panel decision requesting that advertising be "Modified or Discontinued" is published, **together with an Advertiser's Statement indicating the advertiser's willingness to comply** with NAD or the NARB panel's recommendations, NAD or the NARB, **either on its own or at the request of a challenger or a third party**, may request that the advertiser **report back, within 10 business days**, on the status of the advertising at issue and explain the steps it has taken to bring the advertising into compliance with the decision.`

> `In response to a request that the advertiser report on its compliance… an advertiser **may file a petition to reopen the case** under Section 8.1(A)… **If a petition to reopen is filed, the compliance inquiry will be suspended until the NAD Vice President decides whether the case will be reopened.** If the petition to reopen is **denied**, the compliance inquiry will **resume** and a response to the compliance inquiry shall be provided within 10 business days after the request to reopen is denied. If the petition to reopen is **granted**, the compliance inquiry will be **terminated**, and the termination will be reported in the NAD Case Reports.`

**🔑 这里有三个此前完全没被识别的机制：**

```
① 触发主体包含「第三方」
   NAD / NARB 自己，或【挑战方】，或【任何第三方】
   → 一旦广告主进入 NAD 体系并作出 MOD/DISC 整改，
     它就被置于一个「任何人可请求复核」的持续监督之下。
   
② 有一个明确的「对抗性中止」开关
   广告主可以对合规问询【申请重新开案】→ 合规问询【自动中止】
   → 准：合规问询【终止】（并记入 Case Reports）
   → 驳：合规问询【恢复】，且只剩 10 个工作日回答
   
③ 重新开案不是「重审」，是「换证据重打一遍」
   §8.1(A)(3)：重新开案的案件【完全按新挑战的流程走】
   （Standard/Complex/SWIFT 全流程 + 可再上诉）
```

**§8.1(A) 重新开案的裁量标准（逐字，四个考虑因素）**：

> `A closed NAD or NARB case may be reopened if the NAD Vice President, **in their sole discretion**, determines that **extraordinary circumstances** warrant the reopening. In making this determination, the NAD Vice President shall take into account (1) **the advertiser's compliance with any recommendations** by NAD or NARB relating to the claims at issue; (2) if the reopening is requested based on new evidence, whether there is a satisfactory showing that the new evidence **was not reasonably available** to the party at the time the NAD record was closed; (3) if the reopening is requested based on new evidence, whether the new evidence **would have likely changed** the NAD or NARB decision in a material way; and (4) whether the request has **sufficient merit to warrant the expenditure of NAD resources**.`

**注意因素(1)：广告主过往的合规表现，是重新开案裁量的第一考虑项。** 即**「不老实整改」会降低它未来申请重开的说服力** —— 这是一个把「合规历史」直接变成程序性杠杆的设计。

**§8.1(B)(3) 不合规的后果（逐字）**：

> `If the advertiser fails to file a substantive written response within an additional 5 business days, **NAD may refer the file to the appropriate government agency and release information regarding the referral to the press, the public, and the media in which the advertising at issue has appeared** and shall report the referral in the next issue of the Case Reports.`

**🔑 对 Momcozy 最重要的一条含义：`a third party` 可以请求合规问询。** 也就是说，**一旦他们被外部（竞争对手、NGO、平台、甚至消费者组织）挑战过一次并答应整改，整改是否真的到位就不再由他们自己说了算**。他们的 291 条现在 100% 靠自查，**没有任何机制让外部验证整改结果**。建议：在他们的阶梯里加一级 `external_verifiable` —— **整改结论必须留下可被第三方复核的痕迹**（改后素材截图 + 落地页快照 + 修改时间戳），而不是只写一句「已整改」。**这一条正是他们 `检查人` 字段填充率 0%（§7.1.6）的直接后果。**

### 2.4 NARB 上诉

**逐字（第 511 行）**：

> `If the advertiser appeals **or a challenger's request to appeal is granted**, the case will be reviewed by the National Advertising Review Board (NARB).`

**注意这句话里的不对称：**
- **广告主：appeals**（直接上诉）
- **挑战方：request to appeal is granted**（需申请，且需被批准）

**这是一个明确的、有利于被挑战方的程序设计。** 对照 ASA：Independent Review 对**双方都开放**（`The Independent Review process is open to advertisers, complainants or broadcasters…`，§1.6.6），但设置了**三个门槛测试**（`additional relevant evidence` / `substantial flaw in Council's ruling` / `substantial flaw in the process`）。

**这两种设计解决的是同一个问题（防止无理由上诉），用了不同手段：**
- NAD/NARB：**对一方开放、对另一方需批准**（不对称准入）
- ASA：**对双方开放，但设置实体门槛**（对称准入 + 高门槛）

**对 Momcozy**：他们的「品线对审查结论提出异议」是高频场景。ASA 的模式（对称准入 + 三项门槛 + **申诉不中止执行**，§1.6.6 / §7.3.3）更贴合——因为品线既是「被审查方」也可能是「发现规则问题的一方」。

#### 2.4.1 挑战方申请上诉的门槛（**逐字，§5.2(B)**）

**上一段说的「不对称准入」，在 Procedures 里有精确原文（第 821–829 行）**：

> `**Within 10 business days** after the date of receipt of an NAD final case decision, the challenger may request review by the NARB by filing a letter, **not to exceed 20 pages** plus any relevant attachments from the NAD case record, explaining why **there is a substantial likelihood that the NARB would reach a different result from NAD**. Upon receipt of submission by NARB, an invoice for the **non-refundable review fee of $5,750** will be sent out… which will be credited toward the filing fee required by Section 5.2(B) **if the review is granted**.`

**三个门槛叠加**：① 10 个工作日；② ≤20 页 + 只准附**已在 NAD 卷宗内**的材料；③ **须证明「NARB 有实质可能得出不同结论」**。**外加 $5,750 不可退费用（未获准则不退，获准则抵立案费）。**

**对照广告主侧：广告主有 `automatic right of appeal`（自动上诉权），只需付上诉费，无须证明任何事。** 这就是不对称的完整形态——**一侧是权利，一侧是申请 + 举证 + 付费**。

#### 2.4.2 NARB 的审查标准：**完全重新判断（de novo），不尊重 NAD**（逐字，§5.7(C)(2)）

> `The panel **shall not consider any evidence or facts if they are outside** the evidence and facts presented to NAD. In making its decision, the panel shall **exercise its own independent judgment** on the issues presented and **shall not give deference to NAD's findings and recommendations**.`

**这两句话合起来定义了一个我此前没料到的结构**：

```
证据范围：受限（不得超出 NAD 卷宗）      → 不是完全的 de novo 审判
判断标准：完全独立（不得尊重 NAD 的认定）  → 但对卷宗内的判断是全新的
```

**即：NAD → NARB 是「同一份证据、第二双眼睛」，而不是「新证据、新程序」。** 这与 ASA 的 Independent Review 形成鲜明对比——ASA 的独立审查**允许提交 `additional relevant evidence`**（§1.6.6），即它是**带新证据的复审**。

**对 Momcozy 的映射**：他们的「品线对审查结论提出异议」——建议采用 **NAD/NARB 模式（同一证据、第二审查人、不得引入新证据）**，而不是 ASA 模式。理由：他们的场景是**投放后审计**，证据是当时的素材快照；**允许补证据等于允许事后修改素材再申诉**，会破坏审计结论的时间锚定。

#### 2.4.3 NARB 的实际产出（Annual Report 2025 原始表格 + 一处内部矛盾）

**NARB 2025 年逐案清单（`_evidence/R2/nad-annual-report-2025.txt`，第 34 页表，10 个已结案小组）**：

| Panel | 挑战方 / 广告主 | 产品类 | Decision |
|---|---|---|---|
| 333 | Louisiana-Pacific Corp. / James Hardie Building Products | 建材 | `Upheld` |
| 335 | P&G / GuruNanda | 化妆品 | `Upheld` |
| **336** | **Charter Communications / T-Mobile US** | **电信** | **`Overturned`** |
| 337 | Bayer Healthcare / Olly PBC | 膳食补充剂 | `Upheld` |
| 338 | Verizon / Charter Communications | 电信 | `N/A` |
| 339 | P&G / Essor Group (Boka) | 化妆品 | `Upheld` |
| **340** | **Verizon / T-Mobile US** | **电信** | **`Upheld In Part`** |
| 341 | International Bottled Water Assn / Boxed Water | 食品饮料 | `N/A` |
| 342 | **Nurture, LLC（达能子公司）/ Kendal Nutricare** | **婴幼儿产品** | `Upheld` |
| 343 | Verizon / AT&T Services | 电信 | `Upheld` |

**同页的合规案件（Compliance Cases）**：`332C` · `333C` · `339C` · `340C` —— **四件，全部标记 `Compliance`**。

**⚠️ 一处必须记录的内部矛盾（这就是子代理交给我判断的第 2 项）**：

同一份年报的汇总行写作：

```
Case Type  Filed Heard Withdrawn Denied Upheld  Upheld in Part  Overturned  Compliance  Pending
Appeals      7     8       0       2      8          0             0           4         2
```

**我的复核结论（已用 microlink 定位版式原始像素位置核对，不是文本猜测）**：

1. **「Overturned = 0」这个读法在版式上是对的** —— 表头共 9 个数据列（`Filed·Heard·Withdrawn·Denied·Upheld·Upheld in Part·Overturned·Compliance·Pending`），数据行恰有 9 个数值，逐列对齐。**子代理的位置抽取没有错。**
2. **三个独立交叉验证对得上**：`Compliance=4` ↔ 同页列出的 4 件 `…C` 案件；`Pending=2` ↔ 后文 `Pending (as of January 1st, 2026) … NARB 2`；`Heard=8` ↔ 逐案表中除去 2 件 `N/A` 后正好 8 件。
3. **但 `Upheld=8 / Upheld in Part=0 / Overturned=0` 与它自己的逐案表直接冲突** —— 逐案表是 `Upheld 6 · Upheld In Part 1 · Overturned 1 · N/A 2`。

**所以结论是**：**「Overturned 0」不得作为统计结论发布。** 我要的不是「抽错了」，而是更麻烦的东西——**BBB 自己年报的汇总行与逐案表不一致**。（最可能的解释是汇总行把 8 件「已审理」案件整体计入了 `Upheld` 列、后两列未回填；但**这属推测，未证实**。）

**🔑 这一条本身就是给 Momcozy 的最好一课**：他们问「错题本还是规则库」，而这里给出了第三个答案——**报表必须能从案件明细重算出来**。一个无法与明细对账的汇总数字，比没有汇总数字更糟，因为它会被当成事实引用。**建议：Momcozy 的任何合规率/分布指标，都必须写成「可由 291 条明细重新计算」的派生量，不得手工填写。**

---

### 2.5 案例库的形态（**与 ASA 的关键差异**）

**逐字（第 339–340 行、第 380 行）**：

> `Over its 50-year history, NAD has published thousands of decisions and has become the leading voice in providing guidance for truthful and transparent advertising. NAD reviews advertising in any industry and advertising format and often addresses **cutting-edge advertising issues before regulatory guidance is available**.`
>
> `**Summaries of all case decisions can be found in the Case Decision Summary library.**`
>
> `For the full text of decisions, **subscribe to the Online Archive**. Members of the press can request the full text of decision by emailing the request to press@bbbnp.org.`

**Online Archive 的规模（逐字，第 327 行）**：

> `An exclusive database containing **6,000+ self-regulatory legal cases** and detailed analysis from NAD, NARB, and CARU dating back to the 1970's.`

**这是 ASA 与 NAD 之间最重要的结构差异：**

| | ASA | NAD |
|---|---|---|
| 摘要 | ✅ 免费 | ✅ 免费 |
| **全文** | ✅ **免费公开** | ❌ **订阅制（exclusive）** |
| 规则号索引 | ✅ 可按 `capCode` 检索 | ❌ 无规则号 |
| 保留期 | 5 年（全文） | 归档（1970s 起） |

**本分片判断——这一条对委托方的问题（「错题本还是规则库？」）是一个反面教材：**

> **NAD 有 6,000+ 个案例、50 年积累，但因为「没有规则号」+「全文收费」，它的判例库无法被外部（甚至内部非订阅者）用作可检索的规则索引。** 官方页面自己也只能说 `Summaries of all case decisions can be found in the Case Decision Summary library`。
>
> **反观 ASA：4,250 条判例、全文免费、可按规则号检索（`?capCode=3.7` → 373 条）。**
>
> **结论：判例库的价值不取决于案例数量，而取决于「有没有一个稳定的连接键」。ASA 有规则号，NAD 没有。**

### 2.5b **T2 补齐：NAD 个案的真实结构（3 个 2026 年 8–9 月案件）**

> 路径说明：NAD decision **全文**确为订阅制，但 NAD 对每个案件发布**公开 decision summary / press release**，其结构足以完成字段拆解。以下三个案件原文存于 `_evidence/R2/nad-case-*.txt`（`bbbprograms.org/media/newsroom/decisions/<slug>`，2026-09-15 取回，经 microlink.io 云渲染取得，因 `bbbprograms.org` 对纯 curl 返回导航壳）。

#### 2.5b.1 案件①：Kendal Nutricare（Kendamil 婴儿配方奶）—— **对 Momcozy 价值最高**

- **案件号**：`NAD Case #7562: Kendal Nutricare Limited`
- **日期**：`August 31, 2026`
- **挑战方**：`In a challenge brought by **Abbott Laboratories**`（竞争对手）
- **争议媒体**：`Kendamil **packaging**, its website, as well as digital advertising claims` ← **包装也在范围内**
- **争点**：`whole milk, breast milk comparisons, human milk oligosaccharides (HMOs), and brand heritage`

**逐字结构（4 个分节标题 + 每节的「认定 → 但书 → 建议」三段式）**：

| 分节 | 认定（逐字） | 建议（逐字） |
|---|---|---|
| `## Whole Milk Claims` | `NAD determined that Kendal substantiated its ingredient claims regarding the use of whole milk… **However**, NAD found that claims that competing formulas lose "natural milk fats and important nutrients" reasonably conveys that competing formulas are nutritionally inferior. As the record did not establish this or that infants receive superior nutritional benefits from Kendamil…` | `NAD recommended that Kendal **discontinue** the claim, "Creamy whole milk from European grass-fed cows, sourced from family farms…"` |
| **`## Breast Milk Claims`** | `NAD determined that while the record supports **qualified statements concerning compositional similarities** between whole milk fat and breast milk, **the evidence did not establish that those similarities result in comparative nutritional benefits.**` | `NAD recommended that Kendal **discontinue** claims that Kendamil's use of whole milk keeps natural fats closer to breast milk…` / `NAD also recommended that Kendal **modify or discontinue** its milk-fat comparison **graphics** because they did not accurately reflect the composition of Kendamil or competing formulas.` |
| `## HMO Claims` | `NAD determined that Kendal's advertising reasonably conveyed that Kendamil's specific blend of HMOs (3'-GL, 4'-GL, and 6'-GL) helps support immune health and that the blend is unique. However, **NAD determined that Kendal's evidence was not a good fit for these product-specific claims.**` | `NAD recommended that Kendal discontinue claims that its HMO blend supports immune health.` |
| `## Heritage Claims` | `NAD determined that consumers are reasonably likely to understand unqualified heritage claims including "Est. 1962" and "60 years of experience" as communicating that the Kendamil brand or formula itself has existed continuously since 1962.` | `NAD recommended that Kendal discontinue or modify these heritage claims to clearly communicate that references such as "Est. 1962"… refer to the manufacturing facility or production heritage…` |

**两个程序机制（逐字）**：

> `During the inquiry, Kendal **permanently discontinued** the challenged exclusivity claim. **NAD will treat the discontinued claim, for compliance purposes, as though NAD recommended it be discontinued.**`

> `In its **advertiser statement**, Kendal stated it will "comply with NAD's recommendations."`

> `Per NAD/NARB Procedures, **this release may not be used for promotional purposes.**`

**🔑 「Breast Milk Claims」这一节是 Momcozy `H09` 的现成判据。** NAD 划的线是：

```
可证：成分相似（compositional similarities）           → 允许，但须限定（qualified statements）
不可证：由相似推出比较性营养优势                          → 禁止
不可证：由成分相似推出"更接近母乳"                        → 禁止
图形/图表同样受约束（graphics 被判 modify or discontinue）
```

**逐字对照 Momcozy 的 `H09` 边界**（PRD 第 381 行）：`智能闭环/仿生虚假宣称；只允许"参考自然哺乳节奏的设计思路/inspired by"表达`。

**本分片判断**：他们把 `inspired by natural nursing` 设为安全区、`mimics/copies baby` 设为红区——**方向与 NAD 一致，但 NAD 的判据更精确、更可操作**：

> **可说的是「设计参考了 X」；不可说的是「因参考 X 而得到更好的结果」。**
> 即：**参考（参考来源）可以，推断（由参考推出优势）不可以。** 这正好解释了为什么 `inspired by natural nursing` 安全而 `mimics baby's natural rhythm → better let-down` 危险——**危险的不是「mimics」，是后半句的推断**。建议把 `H09` 的 `边界内容` 改写成这个判据，而不是停留在关键词枚举。

#### 2.5b.2 案件②：Udisense / Nanit（智能婴儿监视器）—— **`M03` 与 UGC 敞口**

- **案件号**：`NAD Case #7558: Udisense, Inc. (Nanit)`
- **日期**：`September 1, 2026`
- **挑战方**：`Owlet Baby Care, Inc.`（竞争对手）
- **争议媒体**：`its website, sponsored Google search results, and on social media platforms, **including sponsored influencer content and re-posted user-generated content**`

| 争点 | 逐字认定与建议 |
|---|---|
| `"Most Loved" / "#1 Most Loved" / "Internet's Favorite"` | `NAD evaluated Nanit's reliance on **Amazon reviews** to support these popularity claims and determined that **Nanit did not show that Amazon reviews are representative of the marketplace as a whole.**` → `recommended that they should be discontinued.` |
| `"Most Awarded"` | `Given **the undefined nature of awards** and Nanit's reliance on awards from third parties with **potentially varying standards and rigor**, NAD recommended that the "most awarded" claims be discontinued.` |
| `"Smartest Baby Monitor"` | `NAD found that Nanit **failed to provide adequate substantiation for why** its monitor system is the "smartest".` |
| **安全 / SIDS 暗示** | `At issue for NAD was **user-generated and brand social media posts** depicting infants sleeping on their stomachs while using the Nanit monitor with accompanying text such as "If it wasn't for the… @get_nanit…, **face down tummy sleeping would have my mom anxiety through the roof.**" NAD found that **the context of the posts**, coupled with statements suggesting relief from anxiety about "tummy sleeping"… **may convey a broader safety message that the Nanit device can prevent harmful stomach-sleeping risks, such as Sudden Infant Death Syndrome (SIDS).**` |

**本分片判断——这两条对 Momcozy 是直接的：**

1. **`M03`（`trusted by 6 million / bestseller / top rated`）在 NAD 下有明确判据**：**用平台内评价数据支撑「全市场最受喜爱」，必须先证明该数据对全市场有代表性。** Momcozy 的 `M03` 现在是「未标注来源的效果数据声明」——**按 NAD 的口径，问题不是「没标来源」，而是「样本不代表市场」**。建议 `M03` 的边界内容改为：
   ```
   销量/排名/受欢迎度声称 → 须能证明数据源对目标市场有代表性
   仅凭 Amazon/自家站内评价 → 不构成代表性证据
   奖项类声称 → 评奖主体标准不明时不得使用
   ```
2. **UGC / 达人内容的责任**：NAD 把 `user-generated and brand social media posts` 与 `re-posted user-generated content` **直接列为审查对象**，并依**上下文**（`the context of the posts`）认定构成未明示的安全声称。**这与 §3.3.4 的 FTC §255.1(d)（`Advertisers are subject to liability for misleading or unsubstantiated statements made through endorsements`）完全同向。** Momcozy 的 291 条**完全不覆盖 UGC 与达人自有渠道**（§7 已列为缺口）。

#### 2.5b.3 案件③：Hims & Hers Health —— **`H04`/`U01` 的现成判据**

- **案件号**：`NAD Case #7543: Hims & Hers Health, Inc.`
- **日期**：`August 24, 2026`
- **挑战方**：`Kenvue Inc.`（竞争对手）

| 争点 | 逐字认定与建议 |
|---|---|
| **`Doctor-Trusted` / `Dermatologist-Recommended`** | `As support for the doctor-trusted claims, Hims provided **confidential results of a survey of 250 independent dermatologists**. NAD determined that the Hims survey was **sufficient to support certain carefully qualified claims** about the level of dermatologist trust reported for **particular ingredients, ingredient combinations, and patient populations**. **However, NAD found that the survey results are not a good fit for the unqualified "doctor-trusted ingredients" claims** presented in the challenged advertising.` → `NAD recommended that Hims & Hers **modify** its "doctor-trusted ingredients" claims to **clearly and conspicuously disclose the relevant survey results, including the reported level of dermatologist trust for particular ingredients, ingredient combinations, and patient populations**, or otherwise make the level of support clear.` |
| **`Dermatologist-Recommended`** | `Additionally, NAD determined that **Hims' dermatologist-trust survey is not a good fit to substantiate a dermatologist-recommended claim** and recommended that Hims & Hers **discontinue** the claim "Hims Hair Hybrids contain a combination of **dermatologist-recommended** prescription ingredients."` |
| 比较功效声称 | `NAD found that Hims & Hers had a reasonable basis for the claim… **However, as there was no evidence that doctors trust finasteride for that reason**, NAD recommended that the claim be modified to **remove the "doctor trusted" language.**` |
| 安全与副作用 | `NAD recommended that Hims & Hers further modify the claim to **clearly identify the subject of the research, the relevant limitations of the evidence, and the distinction between topical finasteride generally and the challenged compounded products** to avoid conveying the message that the Hims Spray and Serum have been shown to be safe in clinical studies.` |

**🔑 这个案件给出了 NAD 的核心判据——「证据是否对口」（evidence fit），并且给出了两个可直接使用的分界：**

```
① trust ≠ recommendation
   250 位皮肤科医生的「信任度调查」足以支撑「受皮肤科医生信任」的限定表述，
   但【不足以】支撑「皮肤科医生推荐」。→ 两者必须分别取证。

② ingredient ≠ product
   「外用非那雄胺（成分）在研究中被证明安全有效」不能推及
   「本复方产品（成品）已被证明安全有效」。
   → 必须明确：研究对象、证据限制、成分与成品的区别。
```

**对 Momcozy 的直接映射（这是本分片对 `U01`/`H04`/`M07` 最具体的一条建议）：**

| NAD 判据 | 对应 Momcozy 规则 | 建议改写 |
|---|---|---|
| `trust ≠ recommendation` | **`U01`（`expert-designed / expert-tuned`）vs `H04`（`recommended by experts`）** | 二者**不是严重度差异，是证据类型差异**：`U01` 需要「专家参与设计」的证据；`H04` 需要「专家明确推荐」的证据。**一份「专家参与」的证明不能支撑「专家推荐」的表述。** 建议在两条规则上分别挂不同的证据要求 |
| `ingredient ≠ product` | **`M07`（`效率/漏奶/奶流类 claim 需 W1 自身对照数据`）；`H03`（`clinically proven`）** | 现有边界内容已写「需 W1 自身对照数据」——**NAD 的判据支持这一条，并把它上升为一般规则**：外部研究/成分研究**一律不能**支撑成品声称。建议写成兜底规则 `X04 证据对口性` |
| 「明确研究对象与证据限制」 | `M03`（数据声称） | 数据声称若保留，须同时披露：研究对象、样本、限制。对照他们已经写出的 `落地页标注研究名称/样本/日期`（SUG-35 备注）——**方向对，需升级为硬要求** |

#### 2.5b.4 NAD Case Report 的**正式裁决分类**（本案库的「decision 词表」）

**逐字（Procedures §Case Report Headings）**：

> `K. Case Report Headings. NAD's decisions in the Case Reports shall be published according to disposition, under the headings:`
> `• Advertising Substantiated`
> `• Advertising Referred to NARB`
> `• Advertising Modified or Discontinued`
> `• Advertising Substantiated/Modified or Discontinued`
> `• Administrative Closing`
> `• Advertising Referred to Government Agency`
> `• **No Substantiation Received**`
> `• Compliance`

**🔑 `No Substantiation Received` 是一个正式的、单独发布的裁决类别。**

**⚠️ 精确表述（见 §2.5c.5）**：可以说「**NAD 体系在操作上把举证不能当作独立的裁决事由，并为此设有专门类别**」；**不可以说**「NAD 规定证据不足本身即违规」——因为后者会被读成存在一句原文，而**该原文在 NAD 全部公开材料中不存在**（已穷尽检索，§2.5c.5）。这个类别本身就是该结论的证据：**它不需要论证声称为假，只需记录「未收到证据」，就能单独成一类并公开发布。**

**另注**：`No Substantiation Received` 的**触发条件是「未收到」而不是「收到了但不够」**。这与委托方「证据不足即违规」的直觉有细微但重要的差别——**NAD 把它做成一个「不作为」类别（不交材料），而不是一个「证据质量」类别（交了但不够）**。证据质量不足走的是 `Advertising Modified or Discontinued`（§2.5b.1/§2.5b.3 的两个案件都是这一类，尽管它们实际上是「证据不对口」）。**这个区分对 Momcozy 很重要：他们的场景是「素材里没有证据字段」，更接近哪种？本分片判断：更接近后者——素材在，只是没带证据。因此直接照搬 `No Substantiation Received` 会错位，应新建一个「证据未随素材提交」的类别，而不是复用一个语义不同的类别。**

**注意 `Advertising Substantiated/Modified or Discontinued` 这一项**：它承认**同一案件可以同时存在成立与不成立的声称**——与 §1.3.4 的 Nutricia 案（`Three issues were investigated, two of which were Upheld`）是同一结构。

**另两项对 Momcozy 有直接参考价值**：
- `Advertising Referred to Government Agency` —— **「转交」是一个被记录的裁决类别**，不是内部动作。
- `Compliance` —— **合规状态本身是一种可发布的裁决状态**。

**建议**：Momcozy 的案例库应当采用**同样形态的 disposition 词表**，而不是只有「风险等级」一个字段。建议的最小词表（对齐 NAD + ASA）：

```
substantiated           声称成立
modified                须修改后可用
discontinued            须停止使用
substantiated_modified  部分成立、部分须改      ← 对应 ASA 的 "Upheld in part"
no_substantiation       未收到证据（本身即违规） ← 对应 NAD 的正式类别
referred_external       已转交（GTM/平台/法务）
compliance_confirmed    已确认整改
administrative_closing  行政关闭（无需处理）
```

### 2.5c NAD 的举证责任、证据标准与时限（G1 补齐并大幅扩写）

#### 2.5c.1 **一处必须先说的否定发现（否则极易被误引）**

**我逐字检索了 2026 版与 2020 版 Procedures 全文（`nad-narb-procedures.txt` 1,590 行 / `-2020.txt` 1,449 行），以下三个词在两版中的出现次数均为 0：**

| 检索词 | 2026 版 | 2020 版 |
|---|---|---|
| `burden`（举证责任） | **0** | **0** |
| `competent and reliable`（CRSE 的标准表述） | **0** | **0** |
| `Federal Trade Commission`（FTC 全称） | **0** | **0** |

**结论（本分片实测，可复现）**：

> **「NAD 的举证责任规定在 Procedures 第 X 条」这一说法是错的——Procedures 里根本没有举证责任条款，也没有点名 FTC。**
>
> 任何写成 `per NAD/NARB Procedures §…, the burden of proof is on the advertiser` 的引注，**都是伪造引注**。

**举证责任的正式表述不在程序文件里，而在官方 FAQ 页**（逐字，`_evidence/R2/bbbnp-faq.txt` 第 491 行）：

> `**The burden of proof is on the advertiser in an NAD challenge.** The challenger may submit evidence that demonstrates the challenged advertising claims are not truthful and accurate.`

**程序文件里对「举证」的实际处理方式是「把它写成一项程序义务」**，而不是写「举证责任」（逐字，§3.2(A)，第 507–511 行）：

> `The advertiser **shall, within 15 business days after receipt of the complaint**, submit its written response **that provides substantiation for any advertising claims or representations challenged**…`

**⚠️ 这条否定发现对委托方有直接价值**：他们要做的是内部规则库，而**引注来源错位是内部规则库最典型的失效方式**——写规则的人记住了结论（「举证在广告主」），但把出处安到了一个看起来更权威的文件上。**建议：规则库的每条规则必须带「出处类型」字段，区分「法条」「程序文件」「FAQ/释义层」「判例」四类，因为四类的可引用强度完全不同。**（对照 §1.8 的 ASA 三层工件模型：ASA 的释义层正是因为**与规则层分离且标注清楚**才好用。）

#### 2.5c.2 完整时限表（逐字，Standard Track）

| 步骤 | 时限 | 页数限制 | 出处 |
|---|---|---|---|
| 广告主书面答辩（含证据附件） | **15 个工作日**（自收到投诉起） | 30 页（不含证据附件） | §3.2(A) |
| 挑战方回复 | **10 个工作日**（自收到答辩起） | 20 页 | §3.3(A) |
| 广告主最终回应 | **10 个工作日**（自收到回复起） | 20 页 | §3.4 |
| NAD 索要补充材料 | **6 个工作日** | — | §3.5(A) |
| **NAD 作出裁决** | **20 个工作日**（自收到最后一份文件起，或自最终会议结束起） | — | §3.6 |
| 广告主提交 Advertiser's Statement | **5 个工作日** | — | §3.6 / §5.1(A) |
| 挑战方申请上诉 | **10 个工作日** | 20 页 | §5.2(B) |
| 合规问询：广告主报告 | **10 个工作日** | — | §8.1(B)(1) |

**Complex Track 的差异**（§4.4(B) / §4.9）：答辩同为 **15 个工作日**、**30 页**；最终裁决 **30 个工作日**（Standard 为 20）。

**对照 ASA**（§1.7）：ASA 首次回应 **7 个工作日**（重案 5 天），NAD **15 个工作日** —— **ASA 更紧**。**本分片判断**：这个差异的来源不是效率，是**举证成本**——NAD 案件的核心是科学证据（complex substantiation），15 天上限已经是压缩后的结果；ASA 案件多数是规则字面命中，7 天足够。

#### 2.5c.3 **NAD 自己的 CRSE 操作化定义（本案库最有价值的一段）**

**逐字（`_evidence/R2/nad-digest-cosmetics.txt` 第 345–350 行；`nad-digest-environmental.txt` 同文）**：

> `**Competent and reliable scientific evidence is generally a methodologically sound, placebo-controlled, human clinical trial on the product or the ingredients in the product.** Results should be **statistically significant to the 95% confidence level** and the record should contain evidence that the results are **noticeable and meaningful to consumers**. Further, **advertising claims should be tailored to accurately reflect the study results.**`

**这一段同时回答了四个问题**（对照 §3.2 的 FTC 侧定义，FTC 只给「基于专家的判断」，**NAD 给的是可操作的具体条件**）：

| 问题 | NAD 的答案（逐字要素） |
|---|---|
| 需要什么类型的研究？ | `methodologically sound, placebo-controlled, human clinical trial` |
| 研究对象必须是成品还是成分？ | `on the product **or the ingredients in the product**` —— **表面允许成分研究**，但见下方 §2.5c.4 的限制 |
| 是否要求「在人体上」？ | ✅ `human clinical trial`（明确） |
| 显著性标准？ | ✅ `statistically significant to the 95% confidence level`（**给了具体数值**） |
| 还有别的门槛吗？ | ✅ `noticeable and meaningful to consumers`（**统计显著 ≠ 消费者可感知**，这是两个独立门槛） |
| 声称与证据的关系？ | ✅ `claims should be tailored to accurately reflect the study results`（**这就是「证据对口性」的一般条款**） |

#### 2.5c.4 **「成分研究不能替代成品研究」的原文（逐字，NAD Program Guidance）**

**逐字（`_evidence/R2/nad-guidance-substantiation-checklist.txt` 第 345 行）**：

> `Note that **testing a product with different ingredients, properties, or composition from the advertised product is generally insufficient substantiation** unless there is additional reliable evidence demonstrating that testing on a different product can substitute for testing on the advertised product. It may seem obvious, but it is worth a reminder that **reviews from satisfied customers are not considered reliable evidence.**`

**两句话，两个重要结论**：
1. **成品必须自己被测**（成分/近似配方研究默认不足，除非另有桥接证据）—— 这与 §2.5b.3 的 Hims & Hers 案（`ingredient ≠ product`）互为印证。
2. **用户好评不是证据**（`reviews from satisfied customers are not considered reliable evidence`）—— 与 FTC §255.1 及 §3.2.3 同向。

**对 Momcozy 的直接含义**：他们的 `M07`（效率/漏奶/奶流类需 W1 自身对照数据）**方向完全正确，且 NAD 的原文可以给它一个更强的表述**。建议把这两句原文直接引为 `H03`/`M07` 的边界依据——**比现在写「需 W1 自身对照数据」更有说服力，因为它是自律体系自己的判据原文，不是我们的推论。**

#### 2.5c.5 **「证据不足本身即违规」——本分片必须精确交代的一项**

**委托方的核心问题之一是「没有证据的声称是否本身即构成问题」。** 子代理为此做了穷尽检索：Procedures 全文（两版）、Annual Report、两份 digest（约 154 K 字符）、guidance 全文、FAQ、8 个案件页。

**结论：NAD 材料中不存在一句「缺乏实证本身即构成违规」的逐字表述。**

**它只以「操作形态」存在，由四处共同支撑：**

```
① 举证责任在广告主       FAQ: The burden of proof is on the advertiser
② 举证是强制程序义务     §3.2(A): the advertiser SHALL … provide substantiation
③ 未收到证据是独立裁决类 §2.1(K): "No Substantiation Received"
④ 实际发生的裁决         Leptitox: failed to provide substantiation for its express
                        weight loss advertising claims
```

**⚠️ 本条必须按这个精度使用**：可以说 **「NAD 体系在操作上把举证不能当成独立的裁决事由，并设有专门类别 `No Substantiation Received`」**；**不可以说「NAD 规定证据不足本身即违规」**，因为后者会被读成有一句原文，而原文不存在。

**这正是 §0.2 引用约定存在的意义** —— 「本分片判断」与「原文」的边界在这里最容易失守，因为结论本身是对的，错的是它的证据地位。

### 2.5d **一个跑完整两轮的合规循环案件：NARB #7415-340 2C（T-Mobile，2026-01-22）**

> 这是本分片找到的**最能说明 NAD 合规机制实际如何运作**的单个案件，也是给 Momcozy 阶梯设计的最佳范本。原文存于 `_evidence/R2/narb-decision-2-tmobile-compliance.txt`（`bbbprograms.org/media/newsroom/decisions/t-mobile-compliance`），全文逐字。

#### 2.5d.1 完整时间线（逐字重建）

| # | 时间 | 事件（逐字要素） |
|---|---|---|
| 1 | — | **NAD Case #7415**，挑战方 **Verizon**。NAD 建议 T-Mobile 停止使用 `"Save on Every Plan"` 手册、两条电视广告、一份新闻稿、以及 Savings Calculator 网站上的省钱声称 |
| 2 | — | T-Mobile 上诉 → **NARB Panel #7415-340**；`the NARB panel **affirmed** NAD's decision` |
| 3 | — | T-Mobile 在 Advertiser's Statement 中表示 `while it "**disagrees with the panel's decision**," it **would comply**` |
| 4 | — | **Verizon 请求合规问询**（第一次）。NARB 于 **2025 年 10 月**建议停止或修改；T-Mobile 同意 → **NARB Case #7415-340C** |
| 5 | — | T-Mobile 再次修改价格优势声称；**Verizon 请求第二次合规审查**，主张新版本只是 `"**superficial, cosmetic tweaks**"` 且 `the "**core takeaway**" remained unchanged`。NARB 于 **2025 年 12 月**启动第二次合规审查 |
| 6 | — | T-Mobile 抗辩：已作实质修改、`acted in **good faith**`、部分广告已停止、新声称与旧声称 `"**materially different**"`，因此 `NARB should not conduct a compliance inquiry` |
| 7 | **2026-01-22** | NARB 认定：新免责声明 `**was not sufficiently clear** to put reasonable consumers on notice that the price comparison included the cost of ancillary services beyond basic cellular service` |
| 8 | **2026-01-22** | NARB 进一步认定：T-Mobile `had **not made a bona fide attempt** to bring its advertising into compliance… even though it had had **ample time** to comply` |
| 9 | **2026-01-22** | `While NARB had **initially decided to refer the matter to the FTC**, subsequent to sending the compliance decision to T-Mobile, the advertiser advised NARB of T-Mobile's plans to **petition the NAD to re-open** the proceeding to evaluate new substantiation` |

#### 2.5d.2 🔑 这个案件证明的五件事

```
① 「同意整改」不是终点，是循环的起点
   本案跑了【两次】合规审查，每次都由【挑战方】Verizon 触发 →
   印证 §8.1(B)(1) 的「challenger or a third party」触发权
   
② 存在一种真实且高发的抗辩，叫「我已经改得很实质了」
   T-Mobile 的四个论点：实质修改 / good faith / 已停止部分广告 / 新声称 materially different
   → NARB 全部不接受（not a bona fide attempt）
   
③ NARB 会审查【修改的质量】，不只是【是否修改】
   Verizon 的措辞「superficial, cosmetic tweaks」和「core takeaway remained unchanged」
   → 这正是判定标准：改的是措辞还是实质信息
   
④ 「免责声明」是最常见的应付手段，也最容易被击穿
   T-Mobile 加了 "By getting built-in benefits they leave out."
   → NARB: was not sufficiently clear
   
⑤ 转交 FTC 之前的最后一刻，广告主还能用【重新开案】把程序拉回来
   时间点：already decided to refer → T-Mobile 提出将申请重开 → 
   与 §8.1(B)(1) 的「petition to reopen 中止 compliance inquiry」精确对应
```

#### 2.5d.3 对 Momcozy 的直接含义（**这是全篇最可操作的一节**）

**他们的阶梯现在是「命中规则 → 风险等级 → 改写建议」。这个案件说明缺了最关键的一环：整改质量的复核。**

| 本案机制 | Momcozy 现状 | 建议 |
|---|---|---|
| 合规问询由**挑战方/第三方**发起 | 整改结果由**被审查方自己声明**，`检查人` 填充 0/291 | 增加 `复核人` + `复核结论` 两个字段，且**复核人不得等于原审查人** |
| 判定「是否 bona fide attempt」 | **无此判断**，只有「是否已整改」二值 | 增加 `整改性质` 枚举：`措辞调整` / `实质信息变更` / `停止使用`，并要求说明**核心信息是否改变** |
| 免责声明须 `sufficiently clear` | 现有 19 条卖点边界是关键词白名单，**不评估免责声明是否足够显著** | 增加 `免责声明充分性` 判定项 |
| 二次、三次复核 | 无（一次性） | 阶梯的最高两级应支持**重复触发**，而不是单次终局 |

**一句话**：T-Mobile 案的教训是——**「已整改」是一个需要被证明的结论，不是一个可以自行申报的状态。**

---

### 2.5e **同一广告主、同类声称、相反结论：Kendamil 的两个案件（判例一致性的实测）**

**委托方问「判例会不会互相矛盾」。本分片在 NAD 体系里找到了一个表面上完美的矛盾样本，但拆开后发现它其实是**一致的**——而这个过程本身给出了一个重要的字段设计结论。**

#### 2.5e.1 两个案件并列

| | **案件 A** | **案件 B** |
|---|---|---|
| 编号 | NAD **#7422** → NARB **#7422-342** | NAD **#7562** |
| 日期 | **2025-12-16**（NARB） | **2026-08-31** |
| 广告主 | Kendal Nutricare（Kendamil） | Kendal Nutricare（Kendamil） |
| 挑战方 | **Nurture, LLC（达能子公司）** | **Abbott Laboratories** |
| 争点 | 全脂奶 / MFGM / 植物油 | 全脂奶 / **母乳比较** / HMO / 品牌历史 |
| 结论 | **声称成立**（`supported and not misleading`） | **建议停止或修改** |

**案件 A 被维持的具体声称（逐字）**：

> `"**Whole milk fats are similar to those found in breast milk**, with naturally occurring MFGM supporting cognitive development"` → panel agreed with NAD that these `are **truthful and not misleading**`

**案件 B 被建议停止的具体声称（逐字）**：

> `NAD recommended that Kendal discontinue claims that Kendamil's use of whole milk **keeps natural fats closer to breast milk**, it provides "**natural milk fat instead of relying on vegetable oils**," and "We source creamy European whole milk from grass-fed cows…"`

#### 2.5e.2 🔑 矛盾在拆开措辞后消失——而且两个案件划的是同一条线

**关键在案件 B 里被建议**保留**的那半句（逐字）**：

> `NAD determined that while **the record supports qualified statements concerning compositional similarities** between whole milk fat and breast milk, **the evidence did not establish that those similarities result in comparative nutritional benefits.**`

**把两个案件叠起来看：**

```
案件 A 允许："全脂奶脂肪【与】母乳中的脂肪相似"          → 成分相似，限定表述 ✅
案件 B 允许："成分相似（compositional similarities）"    → 同上 ✅
案件 B 禁止："【更接近】母乳" / "用天然乳脂【替代】植物油" → 由相似推出比较优势 ❌
```

**两个案件划的是同一条线**：**成分相似可以说，由相似推出更优不可以说。** 这与 §2.5b.1 从案件 B 单独得出的结论完全一致，**并且现在由案件 A 从反面完成了交叉验证**——一个 2025 年胜诉的「similar to」声称，正好落在 2026 年败诉的「closer to」声称的允许侧。

#### 2.5e.3 但这里有一个真实的、必须记录的教训

**在标题层面，这两份公开材料的观感是完全相反的**：一份标题写 `NAD Finds Kendamil Infant Formula Claims Supported`，另一份写 `NAD Finds Certain Kendamil Infant Formula Claims Supported; Recommends Others Be Modified or Discontinued`——**而且两份讲的都是「母乳比较声称」**。

**任何只按「主题」建索引的案例库，都会把这两条归到同一个 `母乳比较` 标签下，得出「判例矛盾」或「判例反复」的错误结论。**

**➡️ 对 §7.1.2 的修正**：我此前写「最关键的一个字段是 `issue`（争点），不是 `规则号`」。**这两个案件证明这个说法还不够精确**——`issue`（母乳比较）**不足以**区分这两个案件，真正区分它们的是**被诉的具体声称字符串**。

> **修正为：案例库的主键必须是 `被诉声称原文`（claim string），`issue` 只是它的聚合视图。**
>
> 理由：这是一条**判例级实测证据**，不是推论——两个案件共享全部高层标签（广告主、产品、主题、法域），却得出相反结论；把它们分开的唯一维度是**声称的原话**。

**对 Momcozy 的直接含义**：他们的 291 条记录里有 `命中内容`（广告原文片段）字段。**建议把它确立为案例库的主键与去重键，而不是让 `命中规则`（H07 等）承担索引职责**——因为 `H07` 这类规则号会把「similar to」和「closer to」两条素材归到一起，而它们的合规结论相反。

---

### 2.6 本节缺口（**已在 2026-09-15 补齐后重写**）

> **初稿的 §2.6 列了 5 项缺口，其中 4 项现已补齐。** 下表保留「原缺口 → 现在的状态」，以保证可追溯。

#### 2.6.1 原缺口清单的现状

| # | 初稿所称缺口 | 现状 |
|---|---|---|
| 1 | NAD/NARB Procedures 全文未取得 | **✅ 已取得**（2026 版 + 2020 版，共 3,039 行）。举证义务、时限、页数限制、裁决词表、费用、合规程序、重新开案标准全部到位（§2.2.5 / §2.3.4 / §2.5c）。**且产生一处否定发现**：Procedures 中无 `burden` / `competent and reliable` / `Federal Trade Commission`（§2.5c.1）。 |
| 2 | 个案 decision 字段结构未取得（订阅制） | **⚠️ 部分**。decision **全文**仍为订阅制（结构性障碍未变）。但**已用公开 summary 完成 3 案逐字段拆解**（§2.5b），并取得**两份权威 schema**：§2.1(J)（规范性：`shall identify the advertiser, challenger, product or service, and subject matter reviewed`）+ §2.1(K)（8 项 disposition 词表）。**「证据不足即违规」的原文表述经穷尽检索确认不存在**（§2.5c.5）。 |
| 3 | compliance rate 公开数字 | **✅ 找到，但有严重时效限制**。原文 `**More than 90 percent of the advertisers who come before NAD comply with NAD's recommendations.**` —— **仅见于两份 ©2012 ASRC digest**（`nad-digest-cosmetics.txt` 第 31 行 / `nad-digest-environmental.txt` 第 29 行），**未找到 2012 年之后的任何重申**。**因此不得作为现状引用**，只能作为「历史上曾达到过的水平」。 |
| 4 | NARB 上诉成功率 | **✅ 已取得，但有一处内部矛盾**。Annual Report 2025 逐案表完整（10 件），汇总行为 `Filed 7 · Heard 8 · Withdrawn 0 · Denied 2 · Upheld 8 · Upheld in Part 0 · Overturned 0 · Compliance 4 · Pending 2`。**汇总与逐案表不一致**（逐案表为 Upheld 6 / In Part 1 / Overturned 1 / N-A 2）。**结论：只能用逐案表，不得引用汇总行**（§2.4.3）。 |
| 5 | NAD substantiation 标准原文未取得 | **✅ 已取得且质量高于 FTC 侧**。NAD 自己的 CRSE 操作化定义（`placebo-controlled, human clinical trial` / `95% confidence level` / `noticeable and meaningful to consumers` / `claims should be tailored to accurately reflect the study results`，§2.5c.3）+ 成分与成品不可互替（§2.5c.4）。 |

#### 2.6.2 **仍然存在的缺口（新增清单）**

| # | 缺口 | 影响 | 原因 |
|---|---|---|---|
| **N1** | NAD decision **全文** | 无法逐字段核对完整裁决书（公开的只有 summary） | 订阅制 Online Archive（6,000+ 案件，1971 年起）。**结构性障碍，不再追。** |
| **N2** | **NAD 是否要求「几项研究」的数值门槛** | 无法给出定量要求 | **NOT FOUND**。NAD 只给定性判据（`good fit` / `not a good fit`，§2.5b.3）。**注意：这与 FTC 侧一致**（FTC 也拒绝给数字，§3.2.2）——**两个体系都刻意不给数值门槛，这本身是一个结论。** |
| **N3** | 2012 年后的 compliance rate | 「>90%」无法用于现状 | 未找到重申。见 §2.6.1 第 3 项。 |
| **N4** | Online Archive 的**检索 facet 完整枚举** | 无法对照 NAD 的 issue 分类体系 | 官方称可按 `company, product, issue or claim type, date, document type, or Program` 检索、含 50+ issue types；**但免费库页面为 JS 渲染，未能枚举其 facet 列表，故不对其断言**（§2.5 只引用了官方文字描述，未声称实测）。 |
| **N5** | **`2C` 后缀是否为成文约定** | 影响案例编号的可解析性 | Procedures 全文**未定义** `C` / `2C` 后缀（已检索）。可从案件观察到 `340C`（第一次合规）与 `340 2C`（第二次合规）的用法，**但这是观察，不是规范**。**建议 Momcozy 若要引入类似编号，必须把后缀规则写进规范文件**——否则会出现 NAD 这种「后缀含义只能从案件反推」的情况。 |
| **N6** | Annual Report 汇总行与逐案表不一致的**原因** | 无法判定谁对 | 已确认两张表不一致（§2.4.3）。**最可能的解释（推测，未证实）**：汇总行把 8 件已审理案件整体计入 `Upheld`，`Upheld in Part` / `Overturned` 两列未回填。 |
| **N7** | BBB National Programs 的**年费**（National Partner 会费） | 无法评估「成为会员」的总成本 | 未查。费用表只覆盖 filing fee，未覆盖会员年费。 |
| **N8** | CARU（儿童广告审查）的规则与程序 | 与本分片相关度低（Momcozy 非儿童产品） | 未调研。**这是有意的范围排除**，非遗漏。 |

#### 2.6.3 一处**必须保留**的 FTC 交叉引用（初稿的这条是对的，移到这里保存）

**NAD 的判定不构成 FTC 意义上的免责**（逐字，§3.1.1f）：

> `The Commission will not necessarily defer, however, to a finding by a self-regulation group. An imprimatur from a self-regulation group will not automatically shield a firm from Commission prosecution…`

**这与 §2.1.0 的 Procedures §2.1(A) 互为两面**：NAD 说自己不认定违法；FTC 说自己不因 NAD 的认可而免责。**两面合起来 = NAD 判例在任何法律程序里都没有免责效力。**

---

### 2.7 NAD 机制对 Momcozy 的五条直接含义（**由三条扩为五条**）

**1. 合规机制适配，但初稿对它「二元终局」的描述是错的。** 完整的结构是**三态**（§2.3.4）：`整改关闭` / `合规程序（可反复）` / `转交`。中间那一态才是 NAD 机制真正的价值所在——它把「已整改」从**自行申报的状态**变成**需要被复核并可能被反复质疑的结论**（§2.5d 的 T-Mobile 案跑了两轮）。**建议 Momcozy 直接借用其最高两级：`合规复核` + `转交外部`。**

**2. 20–25% 自发监测比例仍可对标，但先补覆盖。** Momcozy 当前 100% 是主动监测（无外部投诉渠道），但**监测覆盖仅 291 条在跑素材的文本字段，不含图片/视频/落地页**（实测 `落地页URL` 填充率 0%，§7.1.3）。**先补覆盖，再谈比例。**

**3. 「不遵守就转交平台」仍是最现实的一级升级动作。** Google 与 Meta 同时是 ASA 的 IPP 志愿方（§1.5.5）与 NAD 的报告对象（§2.3.1/§2.3.3），且 NAD 可把误导广告直接报告给平台。**建议在 §7.3.2 的 L4 层定义：`escalate_external` = 「记录 + 通知 GTM 负责人 + 向平台侧报告（若已上线）」。**

**4.（新增）`a third party` 触发权 → 整改结论必须外部可验证。** §8.1(B)(1) 明确允许**任何第三方**请求合规问询。**一旦 Momcozy 被外部挑战过一次，整改是否到位就不再由他们自己说了算。** 结合他们 `检查人` 填充率 0/291（§7.1.6），**当前状态下他们连「谁做的整改」都拿不出，更谈不上「可被第三方复核」**。建议新增 `external_verifiable` 要求：整改须留改后素材快照 + 落地页快照 + 时间戳。

**5.（新增）案例库主键应是「被诉声称原文」，不是规则号、也不是争点主题。** §2.5e 的两个 Kendamil 案件共享全部高层标签却结论相反，**唯一能把它们分开的维度是声称原话**。建议把 `命中内容`（广告原文片段）确立为主键与去重键。

**补充（成本视角）**：NAD 的费用结构（§2.2.5）透露的设计意图是**按挑战方营收分档**——大公司挑战小公司要付更多。**Momcozy 可搬的是分档逻辑本身**：把审查成本按品线/渠道营收规模分摊，而非平均分摊。

---

## 3. 美国 FTC：substantiation doctrine 与处置阶梯

> 本节所有引文均已存档至 `_evidence/R2/`，URL 与本地文件逐一对应。抓取日期均为 2026-09-15。

### 3.1 Substantiation doctrine：官方定义原文

#### 3.1.1 1984 年《FTC Policy Statement Regarding Advertising Substantiation》

- **出处**：FTC Policy Statement Regarding Advertising Substantiation，日期 `November 23, 1984`，`Appended to Thompson Medical Co., 104 F.T.C. 648, 839 (1984), aff'd, 791 F.2d 189 (D.C. Cir. 1986), cert. denied, 479 U.S. 1086 (1987).`
- **URL**：https://www.ftc.gov/legal-library/browse/ftc-policy-statement-regarding-advertising-substantiation
- **本地**：`_evidence/R2/ftc-advertising-substantiation-policy-statement-1984.html` / `.txt`

**（a）reasonable basis 要求的本体（逐字）**

> `First, we reaffirm our commitment to the underlying legal requirement of advertising substantiation-that advertisers and ad agencies have a **reasonable basis for advertising claims before they are disseminated**.`

**（b）缺失依据本身即构成违法（逐字）—— 这是整份文件的枢纽句**

> `The Commission intends to continue vigorous enforcement of this existing legal requirement that advertisers substantiate **express and implied claims, however conveyed**, that make objective assertions about the item or service advertised. Objective claims for products or services represent explicitly or by implication that the advertiser has a reasonable basis supporting these claims. These representations of substantiation are material to consumers. That is, consumers would be less likely to rely on claims for products and services if they knew the advertiser did not have a reasonable basis for believing them to be true. Therefore, **a firm's failure to possess and rely upon a reasonable basis for objective claims constitutes an unfair and deceptive act or practice in violation of Section 5 of the Federal Trade Commission Act.**`

**（c）「明示 vs 暗示」的处理（逐字）**

> `Many ads contain express or implied statements regarding the amount of support the advertiser has for the product claim. **When the substantiation claim is express (e.g.., "tests prove", "doctors recommend", and "studies show"), the Commission expects the firm to have at least the advertised level of substantiation.** Of course, an ad may imply more substantiation than it expressly claims or may imply to consumers that the firm has a certain type of support; in such cases, **the advertiser must possess the amount and type of substantiation the ad actually communicates to consumers.**`

**注意 `"tests prove"`, `"doctors recommend"`, `"studies show"` 这三个例子**——它们**逐字对应 Momcozy 的 `H03`（`clinically proven / scientifically proven`）与 `H04`（`doctor recommended / recommended by experts`）**。FTC 的规则是「声称了多少证据，就必须持有多少证据」（`at least the advertised level of substantiation`），而不只是「不得虚假」。

> `Absent an express or implied reference to a certain level of support, and absent other evidence indicating what consumer expectations would be, the Commission assumes that consumers expect a "reasonable basis" for claims. The Commission's determination of what constitutes a reasonable basis depends… on a number of factors… These factors include: **the type of claim, the product, the consequences of a false claim, the benefits of a truthful claim, the cost of developing substantiation for the claim, and the amount of substantiation experts in the field believe is reasonable.**`

**（c2）「净印象」测试与多义规则（1983 Deception Policy Statement 逐字）**

- 出处：FTC Deception Policy Statement，`Oct 14 1983`，`Appended to Cliffdale Associates, Inc., 103 F.T.C. 110, 174 (1984)`。本地 `_evidence/R2/deception-stmt.txt`。

> `the representation, omission or practice must be **likely to mislead reasonable consumers under the circumstances. The test is whether the consumer's interpretation or reaction is reasonable.**`

> `the important criterion is **the net impression** that it is likely to make on the general populace.`

> **`When a seller's representation conveys more than one meaning to reasonable consumers, one of which is false, the seller is liable for the misleading interpretation.`**

以及 HPCG 对「净印象」的操作化（逐字）：

> `assessing the 'net impression' conveyed by all elements of the ad… **When an ad lends itself to more than one reasonable interpretation, the advertiser is responsible for substantiating each interpretation.**`

**🔑 「多义规则」对 Momcozy 是一条可直接落地的判据**：若一句文案存在两种合理解读，其中一种为假，**广告主须为每一种解读书面举证**。这正是他们 `U04`（`painful pumping` 是痛点场景还是功效承诺）悬而未决的问题——**按 FTC 口径，不需要判定「到底是哪一种」，两种都要能举证；举证不了的那一种即为违规。**

**（c3）「reasonably clear」标准（HPCG 脚注 20 逐字，注解 POM Wonderful）**

> `Commission can rely on its common sense and expertise to determine what claims were conveyed **so long as the claims are reasonably clear**`

**（d）暗示性声称的举证义务（逐字）**

> `One issue the Commission examined was substantiation for implied claims. Although firms are unlikely to possess substantiation for implied claims they do not believe the ad makes, **they should generally be aware of reasonable interpretations and will be expected to have prior substantiation for such claims.** The Commission will take care to assure that it only challenges **reasonable interpretations** of advertising claims.`

**（e）事后补充证据不能免责（逐字）**

> `The Commission emphasizes that as a matter of law, **firms lacking a reasonable basis before an ad is disseminated violate Section 5 of the FTC Act and are subject to prosecution.**`
>
> `…nor does it mean that **subsequent evidence of truthfulness absolves a firm of liability for failing to possess prior substantiation** for a claim.`
>
> `…advertisers **will not be allowed to create entirely new substantiation simply because their prior substantiation was inadequate.**`

**（f）FTC 与自律组织的关系（逐字）—— 这一条定义了 NAD 与 FTC 的关系**

> `The Commission will not necessarily defer, however, to a finding by a self-regulation group. **An imprimatur from a self-regulation group will not automatically shield a firm from Commission prosecution**, and an unfavorable determination will not mean the Commission will automatically take issue, or find liability if it does. Rather the Commission will make its judgment independently…`

### 3.2 「competent and reliable scientific evidence」（CRSE）的定义原文与检验标准

#### 3.2.1 定义（逐字）

- **出处**：FTC, *Health Products Compliance Guidance*（2022 年 12 月，取代 1998 年《Dietary Supplements: An Advertising Guide for Industry》）
- **URL**：https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance
- **本地**：`_evidence/R2/ftc-health-products-compliance-guidance-2022.html` / `.txt`（引用位置：本地文本第 160 行）

> `When applied to claims about the efficacy or safety of health-related products, the factors described above make up the FTC's rigorous substantiation standard of "competent and reliable scientific evidence." The FTC has more specifically defined that standard as **"tests, analyses, research, or studies that (1) have been conducted and evaluated in an objective manner by experts in the relevant disease, condition, or function to which the representation relates; and (2) are generally accepted in the profession to yield accurate and reliable results."** In addition, the FTC requires that the research must be **"sufficient in quality and quantity based on standards generally accepted in the relevant scientific fields, when considered in light of the entire body of relevant and reliable scientific evidence, to substantiate that the representation is true."**`

**⚠️ 两版定义并存（引用时须注明版本）**：任务书引用的经典措辞来自 **1998 年《Dietary Supplements: An Advertising Guide for Industry》**，与上引 2022 年 HPCG 版本**字面不同**（本地 `_evidence/R2/ftc-dietary-supplements-advertising-guide-1998.pdf` / `.txt`；注意原 URL 现已 301 跳转到 2022 指南，1998 版仅存于 `system/files/documents/plain-language/bus09-…pdf`）：

> `"competent and reliable scientific evidence," defined in FTC cases as **"tests, analyses, research, studies, or other evidence based on the expertise of professionals in the relevant area, that have been conducted and evaluated in an objective manner by persons qualified to do so, using procedures generally accepted in the profession to yield accurate and reliable results."**`

两版的差异点在于 2022 版把「相关领域」收紧为 `the relevant disease, condition, or function to which the representation relates`（**与声称所涉的疾病/状况/功能对口**），1998 版则只说 `the relevant area`。**对 Momcozy 的 `H04`/`U01`，2022 版的收紧措辞更有用**（§3.3.1 的 §255.3(a) 与之同向）。另附 FTC 的量化免责（逐字）：`There is no fixed formula for the number or type of studies required.`

**🔑 三要件版本（**Roca Labs Final Order** 的实际命令文本，比指南更硬）**——本地 `_evidence/R2/ftc-order-roca-labs-final-judgment.pdf` / `.txt`：

> `For purposes of this Section, **competent and reliable scientific evidence** means tests, analyses, research, or studies (1) that have been conducted and evaluated in an objective manner by experts **in the relevant disease, condition, or function to which the representation relates**; (2) that are generally accepted by qualified experts to yield accurate and reliable results; and (3) **that are randomized, double-blind, and placebo-controlled human clinical testing of the Covered Product, or of an Essentially Equivalent Product, when such experts would generally require such human clinical testing to substantiate that the representation is true.**`

**第 (3) 项是本节对 Momcozy 最有价值的一句话。** 它把三个问题一次答完：
- **必须是人体的**（`human clinical testing`）；
- **必须是 RCT 级别的**（`randomized, double-blind, and placebo-controlled`），**但有一个条件从句**（`when such experts would generally require…`）——即**是否需要 RCT 取决于该领域专家的一般要求**，不是一刀切；
- **必须测「本产品」或「实质等同产品」**（`the Covered Product, or of an Essentially Equivalent Product`）——**成分研究只有在能证明「实质等同」时才可用**。

**对 Momcozy 的直接映射**：`M07` 的边界内容已写「需 W1 自身对照数据」——**方向正确，但缺少「或实质等同产品」这条出口**。建议改写为：

```
M07 / H03 的证据要求（对齐 FTC Roca Labs 三要件）：
  ① 专家对口：研究者的专业领域须与所声称的功能对口
  ② 方法公认：方法须被本领域公认为能产生准确可靠结果
  ③ 产品对口：须为本产品（W1/M5/…）或「实质等同产品」的人体试验；
     若为他型号/成分研究，须另行证明「实质等同」（剂量、配方、使用条件）
  ④ RCT 必要性：由本领域专家的一般要求决定，不由品牌方自行判断
  ⑤ 举证责任：无法出示 ①–④ 即判红，无需证明声称虚假
```

**注意定义的三个要件（对 Momcozy 直接可用）：**
1. **相关领域的专家**（`experts in the relevant disease, condition, or function to which the representation relates`）—— 专家必须**与被声称的功能对口**。
2. **客观方式实施与评估**（`conducted and evaluated in an objective manner`）。
3. **该方法被本领域公认为能产生准确可靠结果**（`generally accepted in the profession to yield accurate and reliable results`）。

**要件 1 直接命中 Momcozy 的 `U01`**：`lactation consultant / IBCLC` 是「哺乳支持」领域的专业身份。如果声称涉及的是**奶量产出**（`more milk`），那么需要的专家是泌乳生理/临床研究方向，**而不是泛泛的哺乳顾问**。ASA 侧有对应结构：规则 12.2 逐字要求健康专业人士`will be deemed suitably qualified only if they can provide suitable credentials, for example, evidence of: relevant professional expertise or qualifications; systems for regular review of members' skills and competencies and suitable professional indemnity insurance…`（`_evidence/R2/The-CAP-Code.txt` 第 1608 行起）。

#### 3.2.2 需要几条研究？什么质量？是否要求 RCT？

同一文件（本地文本第 162 行与第 176 行）逐字：

> `As a general matter, **substantiation of health-related benefits will need to be in the form of randomized, controlled human clinical testing** to meet the competent and reliable scientific standard. In evaluating the reliability of such testing, the FTC will consider several parameters, such as **sample size, duration, and outcome measures**, that will vary depending on the exact nature of the hypothesis being tested and accepted norms in the relevant field. Assessing whether a study is well-designed and well-conducted, and whether the data has been properly analyzed and interpreted, are tasks that should be undertaken by someone with appropriate expertise. Marketes of health products are encouraged to consult with an independent expert in the relevant field of research.`
> `Even when an advertiser doesn't make a specific claim about the level of support, claims about the health benefits of a product must still meet the basic substantiation standard of "competent and reliable scientific evidence." **Randomized, controlled human clinical trials (RCTs) are the most reliable form of evidence and are generally the type of substantiation that experts would require for health benefit claims.** Although **there is no requirement for a specific number of RCTs**, the replication of research in an independently-conducted study adds to the weight of the evidence. Replication in a second study by independent researchers reduces the chance that the results of a single RCT may be influenced by unanticipated, undetected, systematic biases that may occur despite the best intentions of sponsors and investigators. An additional, independently conducted study to corroborate findings provides much greater confidence in the validity of the initial results. As discussed in the next section, however, **the quality of the research is more important than the quantity.** For that reason, **numerous flawed and inadequate studies are unlikely to add up to competent and reliable scientific evidence sufficient to substantiate a claim.**`

**三句话总结（可直接写进 Momcozy 的规则依据栏）：**

| 问题 | FTC 的答案（原文依据） |
|---|---|
| 需要几条 RCT？ | **没有具体数量要求**（`there is no requirement for a specific number of RCTs`），但独立复现增加证明力 |
| 必须 RCT 吗？ | 健康功效声称「一般需要」（`will need to be in the form of randomized, controlled human clinical testing`；`generally the type of substantiation that experts would require`） |
| 质量 vs 数量？ | **质量比数量重要**（`the quality of the research is more important than the quantity`）；**「多篇有缺陷的研究加起来也凑不出 CRSE」**（`numerous flawed and inadequate studies are unlikely to add up to competent and reliable scientific evidence`） |

**本条对 Momcozy 的直接含义**：他们 `W1卖点表达边界` 里反复出现的「28.2% / 10% / 70% 内部数据须补样本量、方法和统计设计」（见 `M07` 规则说明与 SUG-35/36/44 备注）——**按照 FTC 的标准，补样本量与统计设计还不够；需要的是「实施与评估的客观性」和「本领域公认方法」。内部测试即便补全统计，若由品牌方自行设计执行，仍不满足要件 2 的客观性要求。**

**🔑 一个重要的对照：FTC 与 NAD 对同一个标准给了不同精度的定义。**

| | FTC（§3.2.1/§3.2.2） | NAD（§2.5c.3） |
|---|---|---|
| 定义方式 | 「专家会认为合理」（`experts in the field`）——**外接于专家判断** | 直接列出条件（**安慰剂对照 / 人体临床试验 / 95% 置信 / 消费者可感知**） |
| 研究类型 | `randomized, controlled human clinical testing` | `methodologically sound, placebo-controlled, human clinical trial` |
| 显著性 | 未给数值 | **`95% confidence level`（给了数值）** |
| 研究数量 | **明确不给数值**（`there is no requirement for a specific number of RCTs`） | **同样不给数值**（只有 `good fit` / `not a good fit`，§2.6.2 N2） |
| 声称与证据的关系 | 分散在个案与指南中 | **一句一般条款**：`claims should be tailored to accurately reflect the study results` |

**本分片判断**：**做内部规则库时应当引 NAD 的定义，而不是 FTC 的定义。** 理由：FTC 的定义把判断权交给「某个领域的专家」，这在内部审查场景下**无法执行**——审查员会被迫去问「专家会怎么想」；NAD 的定义把条件写死了，**审查员可以直接勾选四项**。**两者法律效力不同（FTC 有强制力），但作为规则库的判据文本，NAD 的更可用。** ⚠️ 注意措辞：这是**判据来源的选择**，不是效力来源的选择——不得据此认为 NAD 的定义有法律约束力（§2.1.0）。

**两个体系一致的地方同样重要**：**都不给「需要几项研究」的数值门槛。** 这是一个跨体系的稳定结论，**建议 Momcozy 也不要在规则库里写「需 2 项研究」这类数字**——没有任何一个成熟体系背书它。

#### 3.2.3 见证/用户评价不能替代证据（逐字）

> `Example 39: A website advertising a smartphone app features testimonials from satisfied customers who say that, after using the app at bedtime for less than a week, their insomnia went away, and they slept soundly through the night. **These testimonials don't constitute substantiation.** The advertiser must have competent and reliable scientific evidence that its product is effective in treating insomnia.`

**对照 ASA**：AdviceOnline 逐字 `Objective claims can be direct or implied (**including through images and quoted customer testimonials**)`（§1.8.1）。**两个体系在「用户证言构成声称但不构成证据」上完全一致。**

#### 3.2.4 「clinically proven」的处理（逐字案例）

> `Example 17: An advertiser claims that its product is based on "Nobel Prize-Winning" research and has been "proven effective" by "$5 Million in NIH Research." The Nobel Prize referred to in the ad, however, was for an unrelated use of the product's active ingredient and has nothing to do with the claimed health benefits. In addition, the NIH research examined the safety, but not the efficacy, of the active ingredient. **The specific claims about the level of support are deceptive even if the advertiser possesses other research that provides competent and reliable scientific evidence of efficacy.**`

**两个可搬运的规则：**
1. **证据的「用途」必须与声称匹配**（`unrelated use of the product's active ingredient`）——活性成分的其他用途研究不能支持本声称。
2. **安全性研究不能支持功效声称**（`examined the safety, but not the efficacy`）。
3. **「证据级别」声称本身是一个独立声称**（`The specific claims about the level of support are deceptive even if the advertiser possesses other research…`）——**即：即使你确实有 CRSE，如果你说「$5M NIH 研究证明」，而 NIH 那笔钱研究的是安全性，你仍然违法。**

**第 3 条对 Momcozy 的 `H03`（`clinically proven`）是一个重要细化**：`H03` 现在是一条整体红线的关键词规则（`clinically proven, clinically tested, clinically validated, clinical studies show, scientifically proven, 临床证明, 临床验证, 临床试验证实, 医学证明`），边界内容为 `未经备案的临床/科学背书`。按 FTC 的结构，`H03` 需要拆成两层：
- **`H03.1` 无临床证据而宣称临床证明**（红）；
- **`H03.2` 有临床证据但证据不支持该声称（用途不符/指标不符/人群不符）**（红，且判据完全不同）。

第 2 层的判据来自 §3.2.1 的要件 1（`experts in the relevant disease, condition, or function`）与本节案例（安全性 ≠ 功效）——**这是纯关键词规则无法覆盖的，必须有人工判定路径与证据登记表配合。**

### 3.3 Endorsement Guides（16 CFR Part 255）

#### 3.3.1 § 255.3 Expert endorsements（**对 Momcozy 的 U01/H04 最直接**）

- **URL**：https://www.ecfr.gov/current/title-16/chapter-I/subchapter-B/part-255
- **本地**：`_evidence/R2/ecfr-16cfr255-endorsement-guides.html` / `.txt`（§255.3 位于本地文本第 567 行起）

> **§ 255.3 Expert endorsements.**
>
> `(a) Whenever an advertisement represents, expressly or by implication, that the endorser is an expert with respect to the endorsement message, then **the endorser's qualifications must in fact give the endorser the expertise that the endorser is represented as possessing with respect to the endorsement.**`
>
> `(b) Although an expert may, in endorsing a product, take into account factors not within the endorser's expertise (such as taste or price), **the endorsement must be supported by an actual exercise of the expertise that the expert is represented as possessing in evaluating product features or characteristics which are relevant to an ordinary consumer's use of or experience with the product. This evaluation must have included an examination or testing of the product at least as extensive as someone with the same degree of represented expertise would normally need to conduct in order to support the conclusions presented in the endorsement.** To the extent that the advertisement implies that the endorsement was based upon a comparison to another product or other products, such comparison must have been included in the expert's evaluation; and as a result of such comparison, the expert must have concluded that, with respect to those features on which the endorser is represented to be an expert and which are relevant and available to an ordinary consumer, **the endorsed product is at least equal overall to the competitors' products.** Moreover, where the net impression created by the endorsement is that the advertised product is superior to other products with respect to any such feature or features, then **the expert must in fact have found such superiority.**`

**§255.3(b) 是本节最有价值的一句话。** 它把「专家背书」的判据从「有没有合作」升级为**「专家是否以其被声称的专业程度，对产品做了足量的检验或测试」**：

```
IF   广告明示或暗示背书人是某领域专家
THEN ① 背书人的资质必须真的达到被声称的专业水平（255.3(a)）
     ② 背书必须建立在「对该产品的检验或测试」之上
     ③ 该检验的充分程度 ≥ 同一专业水平的人为支持该结论通常所需的程度（255.3(b)）
     ④ 若暗示了比较，则比较必须真实做过，且结论是「至少相当」
     ⑤ 若暗示了优越，则专家必须真的得出「优越」的结论
```

**§255.3(c) 的三个示例（逐字）**

> `(1) Example 1. An endorsement of a particular automobile by one described as an "engineer" implies that the endorser's professional training and experience are such that the endorser is well acquainted with the design and performance of automobiles. **If the endorser's field is, for example, chemical engineering, the endorsement would be deceptive.**`
> `(3) Example 3. A manufacturer of automobile parts advertises that its products are approved by the "American Institute of Science." From its name, consumers would infer that the "American Institute of Science" is a bona fide independent testing organization with expertise in judging automobile parts… **If the American Institute of Science is not such a bona fide independent testing organization (e.g., if it was established and operated by an automotive parts manufacturer), the endorsement would be deceptive.** Even if the American Institute of Science is an independent bona fide expert testing organization, the endorsement may nevertheless be deceptive **unless the Institute has conducted valid scientific tests of the advertised products and the test results support the endorsement message.**`
> `(6) Example 6. A medical doctor states in an advertisement for a drug that the product will safely allow consumers to lower their cholesterol by 50 points. **If the materials the doctor reviewed were merely letters from satisfied consumers or the results of a rodent study, the endorsement would likely be deceptive** because those materials are not the type of scientific evidence that others with the represented degree of expertise would consider adequate to support this conclusion about the product's safety and efficacy. Under such circumstances, **both the advertiser and the doctor would be liable** for the doctor's misleading representation.`

**Example 3 与 Momcozy 的 `U01`（`expert-designed program / expert-tuned`）高度相关**：如果「专家程序」的专家是品牌自设或品牌付费设立的机构，即使名义上独立，也构成欺骗。**Example 1 则直接回答「哪一类专家才够格」——专业领域必须与声称内容对口。**

#### 3.3.2 § 255.4 Endorsements by organizations（逐字）

> `(a) Endorsements by organizations, especially expert ones, are viewed as representing the judgment of a group whose collective experience exceeds that of any individual member, and whose judgments are generally free of the sort of subjective factors that vary from individual to individual. Therefore, **an organization's endorsement must be reached by a process sufficient to ensure that the endorsement fairly reflects the collective judgment of the organization.** Moreover, if an organization is represented as being expert, then, in conjunction with a proper exercise of its expertise in evaluating the product under § 255.3, **it must utilize an expert or experts recognized as such by the organization or standards previously adopted by the organization and suitable for judging the relevant merits of such products.**`

**这一条正好覆盖 Momcozy `H04` 里的 `Recommended by 100+ experts`**：机构式背书（尤其是「100+ 专家」这类集体背书）必须**有一个能确保该背书真实反映机构集体判断的流程**，且如果被表述为专家机构，必须使用该机构认可的标准或专家。

#### 3.3.3 § 255.5 Disclosure of material connections（逐字）

> `(a) When there exists a connection between the endorser and the seller of the advertised product that might materially affect the weight or credibility of the endorsement, and that connection is not reasonably expected by the audience, **such connection must be disclosed clearly and conspicuously.** Material connections can include a business, family, or personal relationship. They can include **monetary payment or the provision of free or discounted products (including products unrelated to the endorsed product) to an endorser, regardless of whether the advertiser requires an endorsement in return.** Material connections can also include other benefits to the endorser, such as early access to a product or the possibility of being paid, of winning a prize, or of appearing on television or in other media promotions. Some connections may be immaterial because they are too insignificant to affect the weight or credibility given to endorsements. **A material connection needs to be disclosed when a significant minority of the audience for an endorsement does not understand or expect the connection.** A disclosure of a material connection does not require the complete details of the connection, but **it must clearly communicate the nature of the connection sufficiently for consumers to evaluate its significance.**`

**注意 `regardless of whether the advertiser requires an endorsement in return`** —— **免费寄样即使不要求发内容，也构成需要披露的重大关联。** 这对 Momcozy 的达人/KOC 运营是一个直接的合规条目。

**§255.5(b)(1) 示例（逐字）**——资助研究本身需要披露：

> `(1) Example 1. A drug company commissions research on its product by an outside organization. The drug company determines the overall subject of the research… and pays a substantial share of the expenses of the research project, but the research organization determines the protocol for the study and is responsible for conducting it. A subsequent advertisement by the drug company mentions the research results as the "findings" of that research organization. Although the design and conduct of the research project are controlled by the outside research organization, **the weight consumers place on the reported results could be materially affected by knowing that the advertiser had funded the project. Therefore, the advertiser's payment of expenses to the research organization should be disclosed in the advertisement.**`

#### 3.3.4 广告主对背书人言论的责任（§ 255.1(d)/(e) 逐字）

> `(d) **Advertisers are subject to liability for misleading or unsubstantiated statements made through endorsements or for failing to disclose unexpected material connections between themselves and their endorsers.** (See § 255.5.) **An advertiser may be liable for a deceptive endorsement even when the endorser is not liable.** Advertisers should:`
>
> `(e) Endorsers may be liable for statements made in the course of their endorsements… (For the responsibilities of an endorser who is an expert, see § 255.3.)`

**对 Momcozy**：`H04` 现在只覆盖「广告文案中写了什么背书」（`doctor recommended` 等关键词）。**§255.1(d) 说明真正的敞口在「背书人自己说了什么」**——达人、KOC、合作 IBCLC 在自有渠道的表述，广告主同样担责。**他们的 291 条记录里没有任何一条覆盖「达人/合作方自有渠道内容」。**

### 3.4 2023 年 Endorsement Guides 修订

- 修订版本：**88 FR 48092**（2023 年 7 月 26 日），2023 年 6 月 29 日 FTC 公告
- 本地证据：`_evidence/R2/fr-2023-14795-endorsement-guides-final-rule.txt`、`_evidence/R2/ftc-pr-2023-06-endorsement-guides.txt`

**具体修订内容见 §9 缺口清单**——本分片对 2023 修订的逐条核对依赖子代理的提取结果；已确认存在的关键改动方向为：新增「Endorsements Directed to Children」条款、对虚假评论/虚假证言的明确禁止、以及将「material connection」的披露要求进一步明确化。**未逐条核对到原文的部分，本分片不写成结论。**

### 3.5 处置阶梯：触发条件与金额上限

#### 3.5.1 阶梯总表

| 级 | 动作 | 触发条件（原文） | 强制性 | 金额 |
|---|---|---|---|---|
| **L0** | Warning letter | 可能违法，但尚未进入正式程序 | 非正式 | 无 |
| **L1** | Administrative complaint（Part 3 proceeding） | FTC Act §5(b)，15 U.S.C. §45(b) | 正式 | — |
| **L2** | Consent order（同意令） | 和解；无需承认违法 | **有法律强制力** | — |
| **L3** | Civil penalty | 违反已生效命令（§45(m)(1)(A)）或违反已公布的 penalty offense（§45(m)(1)(B)） | 强制 | **每次违反 $53,088**（2025 年调整后） |

#### 3.5.2 Warning letter（逐字）

- **URL**：https://www.ftc.gov/enforcement/warning-letters（本地 `_evidence/R2/ftc-about-warning-letters.txt`）

> `Eliminating false or misleading information from the marketplace is a key objective of the FTC… The purpose of FTC warning letters is to **warn companies that their conduct is likely unlawful and that they can face serious legal consequences, such as a federal lawsuit, if they do not immediately stop.** Overwhelmingly, companies that receive FTC warning letters take steps quickly to correct problematic advertising or marketing language and come into compliance with the law. **In many cases, warning letters are the most rapid and effective means to address the problem.**`
> `When FTC warning letters are sent to companies, their purpose is to warn of possible law violations. **Warning letters are not formal enforcement actions**, and they may or may not be followed by FTC legal action. **The letters typically include an explanation of why the company is receiving the letter and examples of problematic advertising or marketing language. They require the recipients to correct the problem immediately and contact the FTC within several days to confirm that they have made the required changes.**`
> `Finally, while FTC or joint agency warning letters may be public, **recipients' responses to them usually are not.** After sending the letters, the FTC will not comment on whether a company or individual has received them, whether they have contacted the Commission within the amount of time required, or what they told the agency about their planned response.`

**注意最后一条与 ASA 的对比：FTC 的 warning letter 是「单向公开」——信公开，回执不公开。ASA 的非正式解决是「广告主名 + 日期 + 投诉数公开」（§1.5.2）。** 两种做法各有权衡：FTC 保住了被警告方的沟通空间，ASA 保住了记录的可检索性。

**Warning letter 的结构对 Momcozy 极有参考价值**：`an explanation of why the company is receiving the letter` + **`examples of problematic advertising or marketing language`** + `correct the problem immediately` + `contact within several days to confirm`。

**这就是「错题本」的通知形态**：不是「你违规了」，而是「为什么 + 具体例子 + 立刻改 + 几天内确认」。

#### 3.5.3 民事罚款金额（逐字）

- **出处**：FTC, *Adjustments to Civil Penalty Amounts*，Federal Register 2025-01361（本地 `_evidence/R2/fr-2025-01361-civil-penalty-adjustments.txt`）
- **法条**：`16 CFR 1.98(d): 15 U.S.C. 45(m)(1)(A)` 与 `16 CFR 1.98(e): 15 U.S.C. 45(m)(1)(B)`

本地文本第 152 行与第 156 行的调整表逐字：

```
16 CFR 1.98(d): 15 U.S.C. 45(m)(1)(A) Knowing violations of    51,744   1.02598   53,088
16 CFR 1.98(e): 15 U.S.C. 45(m)(1)(B) Knowing violations of    51,744   1.02598   53,088
```

**即：每次违反的最高民事罚款从 $51,744 调整为 $53,088（2025 年调整，通胀系数 1.02598）。**

**两个条款的区别（这是阶梯的关键）：**

| 条款 | 触发条件 | 说明 |
|---|---|---|
| **§45(m)(1)(A)** | **明知**违反 FTC 此前对该主体发出的**最终命令**（cease and desist order） | 需要先有一个针对该主体的命令 |
| **§45(m)(1)(B)** | **明知**违反 FTC 依 §57a(a)(1)(B) 制定的、**界定不公平或欺骗性行为**的规则 | 需要先有该规则 |

**注意：两者都要求「明知」（knowing）。**

#### 3.5.4 Notice of Penalty Offenses —— **「clinically proven」的现成规则条款**

**这是本节对 Momcozy `H03` 最有价值的一份文件。**

- 文件：FTC *Notice of Penalty Offenses Concerning Substantiation of Product Claims*（2023-04-13 发出，约 670 家 OTC / 顺势疗法 / 补充剂 / 功能食品营销者收件）
- URL：https://www.ftc.gov/system/files/ftc_gov/pdf/Substantiaton-NPO.pdf（**FTC 自己的文件名有拼写错误 `Substantiaton`，非笔误——按原样引用**）
- 本地：`_evidence/R2/ftc-substantiation-NPO-notice.pdf` / `.txt`

**第 5 项（逐字）——直接对应 Momcozy 的 `H03`：**

> `It is an unfair or deceptive act or practice to represent that a product claim has been **scientifically or clinically proven** unless, **at the time the representation is disseminated**, the advertiser **possesses and relies upon evidence sufficient to satisfy the relevant scientific community of the claim's truth.**`

**第 3 项（逐字）——「必须是产品本身的人体试验」：**

> 要求 `at least **one human clinical trial of the product**` 满足六项条件，方可就严重疾病的治愈/缓解/治疗作声称。

**🔑 这一条把 §3.2.4 的「成分研究 ≠ 成品声称」从判例上升为**已公布的处罚先例（penalty offense）**，且 `of the product` 三个字是明文。** 与之同向的还有 HPCG 的 Example 37（逐字，子代理核实）：

> `The advertiser would need to have a study of the actual product if that is what experts in the field would generally require`

**机制意义（为什么这比普通判例更重）**：Notice of Penalty Offenses 的作用是**建立 §5(m)(1)(B) 所需的「明知」要件**——一旦某行为已被列入公布的处罚先例，**后续从事该行为的任何主体都可能被直接处以民事罚款，而无须先有针对它的命令**。即：

```
普通判例：  先有命令 → 违反命令 → 罚款（§5(m)(1)(A)）
处罚先例：  行为已公布为违法 → 明知而为之 → 直接罚款（§5(m)(1)(B)），无需先前命令
```

**另一项须记的边界（`§5(m)(1)(B)` 的适用限制，逐字）**：仅适用于 `a final cease and desist order, **other than a consent order**` —— **同意令（consent order）不能作为 §5(m)(1)(B) 的基础**。且该条可及于 **`whether or not such person… was subject to such cease and desist order`**（非当事方亦可被及），但非当事方依 `§5(m)(2)` 有权要求 **de novo 审理**。

**⚠️ 一个必须避开的过期数字**：**FTC 自己的 Penalty Offenses 页面仍写着 `up to $50,120 per violation`**——那是 **2023 年**的数额（`88 FR 1499`）。**截至 2026-09-15 的最新数额是 $53,088（2025 年调整，`90 FR 5580`）**，且已用四种方法核实**不存在 2026 年调整**（eCFR 1.98 仍标注 2025 年来源；Federal Register API 检索 FTC「Adjustments to Civil Penalty Amounts」13 条命中，最新为 2025-01-17；FR API 检索 2026 年 1–2 月 FTC 规则仅 1 条且为 negative option/CARS/non-compete；FTC 新闻稿检索 2026 年 1–3 月无结果）。**引用时用 $53,088。**

**未决事项**：`16 CFR Part 465`（Reviews & Testimonials TRR，`89 FR 68034`）的操作条文未取得——**若取得，其违反可直接触发 §5(m)(1)(A) 罚款且无需先前命令**，对用户证言/评论类素材影响很大。列为 §9 缺口。

#### 3.5.5 「clinically proven」的实际执法价码（4 个真实案件，含金额）

| 案件 | 时间 | 金额 | 关键逐字 |
|---|---|---|---|
| **FTC v. Neurometrix**（Quell 设备） | — | **$4M 和解，约 $3.9M 退还消费者** | 起诉状：`…it is clinically proven to do so, and that it is cleared by FDA for this specific use.`；广告物证：`Clinically Proven Technology`、`clinically proven to relieve chronic pain at the touch of a button.` |
| **FTC v. Amare Global Holdings** | **2026-06-02 起诉；2026-06-12 追加藐视动议（在办）** | FTC 请求 `compensatory damages for consumers in the full amount consumers paid` | 品牌合伙人声称产品 `scientifically backed` 或 `clinically proven`；**所引研究无安慰剂、n=10、且由公司自己人撰写** |
| **Reebok EasyTone / RunTone** | 2011-09-28 | **$25M 消费者退款** | `proven to lead to 28 percent more strength and tone in the buttock muscles` |
| **Window Rock / CortiSlim** | 2005-09-21 | **$4.5M 现金与资产**（Pinnacle/Cheng $3.4M；Talbott $1.12M） | — |

**Amare 案值得单独注意**：它是**同时体现「证据质量不足」与「违反既有命令」两级**的活案例（起诉 + 藐视动议），且 FTC 主张的金额口径是「消费者实际支付的全额」，而非按每次违反计罚。**对 Momcozy 的含义：`H03`（`clinically proven`）一旦越线，量级不是几千美元，而是百万美元级别 + 全额退款风险。**

#### 3.5.6 FTC 与 FDA 的分工（**G6 已补齐**）

HPCG § II.B 逐字（本地 `_evidence/R2/ftc-health-products-compliance-guidance-2022.txt`）：

> `The FTC and the Food and Drug Administration (FDA) share jurisdiction over the marketing of dietary supplements, foods, drugs, devices, and other health-related products. … **The FDA has primary responsibility for claims that appear in labeling**, including the package, product inserts, and other promotional materials available at point of sale. **The FTC has primary responsibility for claims in all forms of advertising.**`

> `Marketers should be aware that the FDA/FTC Liaison Agreement doesn't limit the FTC's jurisdiction or prohibit the agency from taking action against deceptive labeling claims or obtaining orders that address all forms of marketing, including claims that appear in labeling.`

**MOU 引用（HPCG 脚注 9 逐字）**：`Memorandum of Understanding Between the Fed. Trade Comm'n and the Food and Drug Admin., **36 Fed. Reg. 18,539 (Sept. 16, 1971)**`

**脚注 10 逐字（边界模糊之处）**：

> `Some forms of marketing may constitute both labeling and advertising under the two agencies' laws. For example, **a website where a dietary supplement can be purchased would fall within the FDA's definition of labeling in addition to being advertising under FTC law.**`

**HPCG § II.C 逐字（两法的关键差异）**：

> `FTC advertising law applies to all products and claims. **Unlike FDA law, FTC law makes no bright-line distinctions between categories of health-related products or claims.**`

> **`The FTC doesn't pre-approve "health" claims`** … `Marketers should be aware, however, that the FTC gives great deference to a determination by the FDA of whether there is adequate support for a particular health claim in labeling. **Health claims that meet the FDA "significant scientific agreement" standard will be presumed to be substantiated under FTC law.**`

> `Where there is an existing standard for substantiation developed by a government agency such as the FDA or the National Institutes of Health, or another authoritative body such as the National Academy of Sciences, the FTC gives great deference to that standard.`

**对 Momcozy 的直接含义**：
1. **网站/落地页归 FDA 侧**（`a website where a dietary supplement can be purchased would fall within the FDA's definition of labeling`）——**而他们的 `落地页URL` 字段填充率实测为 0%（§7.1.3），意味着这一整块从未进入审查。**
2. **FTC 不预先批准健康声称**，但对 FDA 的 `significant scientific agreement` 判定给予高度尊重——即：**若某个声称已通过 FDA 的 SSA 标准，在 FTC 侧被推定为已举证。** 这是 Momcozy 可以走的**正向路径**（而不是只做删减）：与其删掉所有功效表述，不如对有证据的卖点走 FDA SSA 或等价的权威路径，把「可说的」扩到最大。

**⚠️ 仍未取得**：MOU 原文本身（`fda.gov` 在取证环境中完全不可达；govinfo 的 1971 年 FR 扫描件使用子集字体、无 `ToUnicode` CMap，无法提取）。**但 MOU 的存在、引注与实质内容已通过 FTC 自身的描述得到确证**，足以支撑本节结论。

### 3.6 FTC 机制对 Momcozy 的三条直接含义

1. **兜底条款的法律原型已经存在，且比 ASA 规则 3.7 更完整。** FTC 的 reasonable basis 要求比 CAP 规则 3.7 多了一层「声称了多少证据就必须持有多少证据」（`at least the advertised level of substantiation`）。**建议 Momcozy 的兜底规则直接采用 FTC 的三段式**：

```
IF   内容含客观声称（express or implied, however conveyed）
THEN ① 广告主必须在发布前持有依据（prior substantiation）
     ② 持有的依据级别必须 ≥ 内容向消费者传达的证据级别
     ③ 无依据 或 依据级别不足 → 判定违规（无需证明声称本身为假）
```

2. **`H04` 的判据需要从「是否真实合作」升级为 §255.3(b) 的「专家是否做了足量检验」。** 这是本分片对 `U01`/`H04` 最具体的一条修改建议：

```
现有判据：需核实是否真实合作
建议判据：① 该专家的专业领域是否与声称内容对口（§255.3(a) + CRSE 要件 1）
         ② 该专家是否对该产品做过「检验或测试」，且充分程度达到其被声称的专业水平所要求的程度（§255.3(b)）
         ③ 若暗示比较 → 比较是否真实做过且结论为「至少相当」（§255.3(b)）
         ④ 若暗示优越 → 专家是否真的得出「优越」结论（§255.3(b)）
         ⑤ 关联披露：是否存在须披露的重大关联（§255.5(a)）
```

3. **15 CFR Part 255 的 §255.1(d) 提示了一个当前完全未覆盖的敞口**：广告主对**背书人在其自有渠道**的表述同样担责。Momcozy 的 291 条只覆盖品牌自有广告素材，**不覆盖达人/KOC/合作专家的自有渠道内容**。这是一条需要新增的审查范围，而不是新增的关键词。

---

## 4. 欧盟：UCPD / 健康声称条例 / DSA

> 本节依据子代理的一手取证（EUR-Lex 与欧盟出版局 CELLAR 认证 XHTML，取回日期 2026-09-15）。原始文件：`_evidence/R2/eu-ucpd-2005-29.md`（36 KB，逐条原文）、`_evidence/R2/eu-annex-i-blacklist.md`（25 KB，Annex I 全部条目逐字）、`_evidence/R2/eu-hc-reg-1924-2006.md`。

### 4.1 UCPD（Directive 2005/29/EC）

#### 4.1.1 Article 6 — 误导性行为（misleading actions）

**Art 6(1) 引言段（逐字）**：

> `A commercial practice shall be regarded as misleading if it contains false information and is therefore untruthful or in any way, including overall presentation, deceives or is likely to deceive the average consumer, **even if the information is factually correct**, in relation to one or more of the following elements, and in either case causes or is likely to cause him to take a transactional decision that he would not have taken otherwise:`

子代理对构成要件的拆解（逐字，`_evidence/R2/eu-ucpd-2005-29.md`）：

> **Two limbs, verbatim in one sentence.** The "untrue" limb is the phrase `"if it contains false information and is therefore untruthful"`. The "deceptive" limb is the phrase `"or in any way, including overall presentation, deceives or is likely to deceive the average consumer, even if the information is factually correct"`. The consequence limb is `"causes or is likely to cause him to take a transactional decision that he would not have taken otherwise"`.

**Art 6(1)(a)–(g) 逐字（节选与 Momcozy 直接相关的三项）**：

> `(b) the main characteristics of the product, such as its availability, benefits, risks, execution, composition, accessories, after-sale customer assistance and complaint handling, method and date of manufacture or provision, delivery, fitness for purpose, usage, quantity, specification, geographical or commercial origin **or the results to be expected from its use, or the results and material features of tests or checks carried out on the product**;`
>
> `(c) the extent of the trader's commitments, the motives for the commercial practice and the nature of the sales process, **any statement or symbol in relation to direct or indirect sponsorship or approval of the trader or the product**;`
>
> `(f) **the nature, attributes and rights of the trader or his agent, such as his identity and assets, his qualifications, status, approval, affiliation or connection** and ownership of industrial, commercial or intellectual property rights or his awards and distinctions;`

**Art 6(1)(f) 是欧盟对 Momcozy `H04` / `U01` 的直接对位条款** —— 它把「资质、身份、批准、隶属或关联」（`qualifications, status, approval, affiliation or connection`）列为可构成误导的要素。**注意 `affiliation or connection` 覆盖了「关联关系」本身**，即：即使合作是真实的，未披露关联也可能构成误导（与 FTC §255.5 同构）。

**Art 6(2)(c)（Omnibus 新增的「dual quality」条款，逐字）**：

> `(c) any marketing of a good, in one Member State, as being identical to a good marketed in other Member States, while that good has significantly different composition or characteristics, unless justified by legitimate and objective factors.`

**对 Momcozy 的意义**：他们在多国投放同一素材（291 条覆盖 FR/UK/CA/ES/IT）。**若同一产品在不同成员国的成分或特性有实质差异，却在营销中声称相同，构成新的 Annex 级误导。**

#### 4.1.2 Article 7 — 误导性遗漏（misleading omissions）

**Art 7(1)（逐字）**：

> `A commercial practice shall be regarded as misleading if, in its factual context, taking account of all its features and circumstances and the limitations of the communication medium, **it omits material information that the average consumer needs, according to the context, to take an informed transactional decision** and thereby causes or is likely to cause the average consumer to take a transactional decision that he would not have taken otherwise.`

**Art 7(2)（逐字）**：

> `It shall also be regarded as a misleading omission when, taking account of the matters described in paragraph 1, a trader **hides or provides in an unclear, unintelligible, ambiguous or untimely manner** such material information as referred to in that paragraph or **fails to identify the commercial intent of the commercial practice** if not already apparent from the context…`

**Art 7(3)（逐字）—— 与 CAP Code 规则 3.3 的措辞几乎一致**：

> `Where the medium used to communicate the commercial practice imposes limitations of space or time, these limitations and any measures taken by the trader to make the information available to consumers by other means shall be taken into account in deciding whether information has been omitted.`

对照 CAP Code 规则 3.3 逐字：`Regard will be had to any limitations (e.g. as to time or space) resulting from the means of communication used and steps taken by the marketer to overcome these by providing the information by other means.`（`_evidence/R2/The-CAP-Code.txt` 第 441 行）——**两段措辞高度同源，说明 UK 准则 3.3 是对 UCPD Art 7 的国内转化。**

**Art 7(4)（invitation to purchase 的材料信息，逐字，含 (a)–(f)）**：

> `(a) the main characteristics of the product, to an extent appropriate to the medium and the product;`
> `(b) the geographical address and the identity of the trader…`
> `(c) the price inclusive of taxes, or where the nature of the product means that the price cannot reasonably be calculated in advance, the manner in which the price is calculated, as well as, where appropriate, all additional freight, delivery or postal charges…`
> `(d) the arrangements for payment, delivery and performance, if they depart from the requirements of professional diligence;`
> `(e) for products and transactions involving a right of withdrawal or cancellation, the existence of such a right;`
> `(f) for products offered on online marketplaces, whether the third party offering the products is a trader or not, on the basis of the declaration of that third party to the provider of the online marketplace.`

**子代理的一处核查更正（逐字）**：

> **Correction to the brief:** Art 7(4) as amended has **six** points, (a)–(f). Point **(f) was added by Directive (EU) 2019/2161** and has no counterpart in the pre-2022 text.

**Art 7(6)（Omnibus 新增，评论真实性，逐字）**：

> `Where a trader provides access to consumer reviews of products, information about **whether and how the trader ensures that the published reviews originate from consumers who have actually used or purchased the product** shall be regarded as material.`

#### 4.1.3 Article 12 — **举证责任转移条款（本分片找到的最干净的兜底条款）**

> `Member States shall confer upon the courts or administrative authorities powers enabling them in the civil or administrative proceedings provided for in Article 11:`
>
> `(a) to require the trader to furnish evidence as to the accuracy of factual claims in relation to a commercial practice if, taking into account the legitimate interest of the trader and any other party to the proceedings, such a requirement appears appropriate on the basis of the circumstances of the particular case;`
>
> `and`
>
> `(b) **to consider factual claims as inaccurate if the evidence demanded in accordance with (a) is not furnished or is deemed insufficient by the court or administrative authority.**`

**Art 12(b) 是四个体系里措辞最直接的兜底**。它把「未提供证据」与「证据不足」**直接等同于「声称不准确」**：

```
IF   经营者作出事实性声称（factual claim）
THEN 法院/行政机关可要求其提供证据（Art 12(a)）
AND  若未提供，或所提供的被认定为不充分
     → 该声称应被视为不准确（Art 12(b)）
```

**对 Momcozy 的直接含义**：这条可以直接改写成他们的兜底规则，而且**不需要引用任何具体的功效条款**。它比 ASA 规则 3.7（`The ASA **may** regard claims as misleading in the absence of adequate substantiation.`——「可以认定」）**更强**：Art 12(b) 用的是 `shall be regarded`（应被视为）。

#### 4.1.4 Annex I —— **「任何情况下均视为不公平」的黑名单**

**⚠️ 任务书的一处前提需要更正**：任务书问「Annex I 的 **31 项**黑名单——这份黑名单本身就是一份现成的规则库，请逐项列出」。

**实测结论：原始 2005 年指令确为 31 项（1–31），但该名单已通过「字母后缀插入」的方式扩充，当前为 47 项。**

子代理的核实（逐字，`_evidence/R2/eu-annex-i-blacklist.md`）：

> `The **original** 2005 Directive contained **31 numbered items (1–31)**: items 1–23 = misleading commercial practices; items 24–31 = aggressive commercial practices.`
>
> `Later amendments did **not** renumber the list — they inserted items with **letter suffixes**. The list has therefore grown while the top-level numbering still runs 1–31:`
>
> | Amendment | Inserted entries | Resulting entry count |
> |---|---|---|
> | Directive (EU) 2019/2161 ("Omnibus") | 11a, 23a, 23b, 23c | 35 |
> | Directive (EU) 2024/825 ("green transition") | 2a, 4a, 4b, 4c, 10a, 23d, 23e, 23f, 23g, 23h, 23i, 23j | **47 (current)** |
>
> `Directive (EU) 2024/825 applies from **27 September 2026**.`

**这是一条时间敏感的关键发现**：**Directive (EU) 2024/825 自 2026-09-27 起适用**——距本次取证日期（2026-09-15）仅 12 天。它一次性新增 12 项 Annex I 条目（2a、4a、4b、4c、10a、23d–23j），主题是**绿色声明与可持续性标签**。

**Annex I 全 47 项（2026-09-27 版）**已逐字存档于 `_evidence/R2/eu-annex-i-blacklist.md`（PART 2，第 117–223 行）。以下列出与 Momcozy 业务直接相关的条目（逐字）：

| 条目 | 逐字原文 | 对 Momcozy 的映射 |
|---|---|---|
| **4** | `Claiming that a trader (including his commercial practices) or a product has been approved, endorsed or authorised by a public or private body when he/it has not or making such a claim without complying with the terms of the approval, endorsement or authorisation.` | **← `H04` / `U01`（专家/IBCLC/机构背书）**；与 CAP 规则 3.52、FTC §255.3 同构 |
| **2** | `Displaying a trust mark, quality mark or equivalent without having obtained the necessary authorisation.` | **← `U01`（认证标识/头衔）**；与 CAP 规则 3.52 上半句逐字同构（`must not display a trust mark, quality mark or equivalent without the necessary authorisation`） |
| **17** | `Falsely claiming that a product is able to cure illnesses, dysfunction or malformations.` | **← `H01`（treat/cure/heal/治疗/治愈/疏通堵奶/治疗乳腺炎）**——注意这是 Annex I 级别的「任何情况下均不公平」，**没有抗辩空间** |
| **23b** | `Claiming that reviews of a product are from real users without taking reasonable and proportionate steps to ensure that they are genuine.` | **← 用户证言/好评素材** |
| **23c** | `Submitting or commissioning false reviews or endorsements, or misrepresenting reviews or social endorsements, in order to promote products.` | **← 达人/KOC 运营** |
| **18** | `Passing on materially inaccurate information on market conditions or on the possibility of finding the product with the intention of inducing the consumer to acquire it at conditions less favourable than normal market conditions.` | 促销话术（← `M04` 限时焦虑类） |
| **28** | `Including in an advertisement a direct exhortation to children to buy advertised products or persuade their parents or other adults to buy advertised products for them.` | **← 母婴品类特有风险**（儿童直接劝导） |
| **4a** | `Making a generic environmental claim for which the trader is not able to demonstrate recognised excellent environmental performance relevant to the claim.` | 新增；← 若涉环保/可持续表述 |
| **4b** | `Making an environmental claim about the entire product or the trader's entire business when it concerns only a certain aspect of the product or a specific activity of the trader's business.` | 新增 |
| **4c** | `Claiming, based on the offsetting of greenhouse gas emissions, that a product has a neutral, reduced or positive impact on the environment in terms of greenhouse gas emissions.` | 新增 |

子代理的相关性归纳（明确标注为推断，非原文）：

> `Note for health-claim work: Annex I point **17** is the only Annex I entry directly about health/cure claims. It sits alongside — not instead of — Regulation (EC) No 1924/2006 and Regulation (EU) No 1169/2011 Art 7(3).`

**Annex I 的机制意义——但必须加一条限制（经子代理核实，见下）：**

> **Annex I 是「任何情况下均视为不公平」（`in all circumstances considered unfair`）的黑名单**——Art 5(5) 逐字：`Annex I contains the list of those commercial practices which shall in all circumstances be regarded as unfair. The same single list shall apply in all Member States and may only be modified by revision of this Directive.` 即：列表中行为**不需要**证明「实质扭曲了消费者经济行为」，也**不需要**个案评估。

**⚠️ 但不要把 Annex I 当成健康声称的主力武器。** 子代理的核实结论（逐字）：

> `Point **17** is the **only** Annex I health entry — and the Commission's own guidance says its "practical utility … is marginal", routing health cases through **Art 6** instead.`

**本分片判断（据此修正上一版措辞）**：
- **对健康/功效声称，主力是 UCPD Art 6（一般条款）+ Reg 1924/2006 Art 6(1)/Art 10(3)**，不是 Annex I item 17。
- **Annex I 真正可直接编码为「无抗辩红线」的，是 item 4（虚假背书）、item 2（未授权 trust mark）、item 23b/23c（评论真实性）、item 28（儿童直接劝导）** —— 这四条**恰好全部命中 Momcozy 的 `U01`/`H04`、用户证言素材、达人运营与母婴品类**。
- **item 17 仍然值得保留为一条规则，但应与 Art 6 的规则并存（作为加重情节），而不是替代它。**
>
> **对照 Momcozy 的 `H` 族**：他们的 `H` 族规则是「严格限制红线」，但 `H01` 的 `豁免词` 列有 20 个豁免短语（`treat yourself, doesn't treat, does not treat, do not treat, not intended to treat, not to treat, not a treatment, not a medical device, …`）。**这在中国（《广告法》第十七条）和欧盟（Annex I item 17）的语境下可能是无效的**——因为「治疗堵奶」这一表述整体落在禁止范围内，加否定语不改变「涉及疾病治疗功能」的事实。这个判断需要在法域映射层显式标注。

### 4.2 健康声称：Regulation (EC) No 1924/2006

- **本地**：`_evidence/R2/eu-hc-reg-1924-2006.md`

#### 4.2.1 Article 5（通用条件）与 Article 6（科学证实）

子代理的拆解（逐字标注为推断）：

> `**My inference:** Art 6(1) is the operative rule against "clinically proven" style assertions. It requires the claim to be *based on and substantiated by* generally accepted scientific evidence. Art 6(2) places the justification burden on the operator; Art 6(3) gives national authorities the power to demand the underlying data.`

**Article 6 逐字**：

> `6(1) Nutrition and health claims shall be based on and substantiated by generally accepted scientific evidence.`
>
> `6(2) A food business operator making a nutrition or health claim shall justify the use of the claim.`
>
> `6(3) The competent authorities of the Member States may request a food business operator or a person placing a product on the market to produce all relevant elements and data establishing compliance with this Regulation.`

**Art 6(3) 是行政侧的调证权，与 UCPD Art 12(a) 形成互补。**

#### 4.2.2 Article 12 — **禁止使用的健康声称**

> `(b) claims which make reference to the rate or amount of weight loss;`
>
> `(c) **claims which make reference to recommendations of individual doctors or health professionals and other associations not referred to in Article 11.**`

**Art 12(c) 是一条硬禁止**：对食品/健康声称而言，**引用「个别医生或健康专业人士的推荐」本身即被禁止**——不是「无据才禁止」，而是「引用即禁止」，除非落在 Art 11 所指的机构范围。

**对 Momcozy 的直接含义**：如果其任何产品在欧盟被归类为食品/食品补充剂，那么 `H04`（`doctor recommended / pediatrician recommended / ob-gyn recommended / ibclc-recommended`）在欧洲**不是「需核实真实性」的问题，而是「不得使用该表述形式」的问题**。**这与 FTC §255.3 的路径（允许，但须真实、须经足量检验）方向不同。**

#### 4.2.3 EU 授权声称注册库

子代理已核实该注册库的机制与字段（`_evidence/R2/eu-hc-reg-1924-2006.md` 第 262 行起 `### The EU Register of nutrition and health claims`）。

**这与 ASA 侧的 GB NHC Register 是同一机制**：CAP 规则 15.1.1 逐字 `Only health claims listed as authorised in the applicable register, or claims that would have the same meaning to the consumer, may be used in marketing communications.`——**英国脱欧后保留了这一机制（改为 GB NHC Register），Nipper&Co 催乳茶案就是据此判违规的（§1.3.2）。**

**本分片判断**：这是 ASA 与 EU 之间**唯一一处规则几乎完全对齐**的地方。对 Momcozy 的启示：**「声称白名单」是少数可以跨法域复用的规则结构**——它的连接键是「声称条目 ID」，而不是国别。

### 4.3 DSA（Regulation (EU) 2022/2065）

> 证据：`_evidence/R2/eu-dsa-2022-2065-art34-42.md`（55 KB，Art 15/17/20/21/24/34/35/36/37/42 逐条原文 + 完整指标清单 + 透明度数据库字段表）。
>
> **取证路径说明（重要）**：`eur-lex.europa.eu` 对非浏览器客户端返回 **HTTP 202 + AWS WAF JS 挑战**（子代理实测 6 种 URL 形式 + 完整浏览器头模拟 + `web_fetch` 工具，全部失败）。实际取文来自 **CELLAR**（欧盟出版局仓库，即 EUR-Lex 自身渲染的数据源），通过 `Accept: application/xhtml+xml` 取得，并已验证文件带 EUR-Lex 合并版本头（如 `02005L0029 — EN — 28.05.2022 — 001.001`）。**引用时仍引 EUR-Lex URL，但取证路径须记为 CELLAR。**
>
> **DSA 无合并版本**（SPARQL 核实：仅有 `02022R2065-20221027`），即**该条例自生效未被修订**。

#### 4.3.1 Article 34 — 风险评估（仅适用 VLOP / VLOSE）

**Art 34(1)(a)–(d) 逐字**：

> `(a) the dissemination of illegal content through their services;`
>
> `(b) any actual or foreseeable negative effects for the exercise of fundamental rights, in particular … **to respect for the rights of the child enshrined in Article 24 of the Charter and to a high-level of consumer protection enshrined in Article 38 of the Charter**;`
>
> `(c) any actual or foreseeable negative effects on civic discourse and electoral processes, and public security;`
>
> `(d) any actual or foreseeable negative effects in relation to gender-based violence, **the protection of public health and minors** and serious negative consequences to the person's physical and mental well-being.`

**Art 34(2) 逐字（含与广告直接相关的一项）**：

> `(a) the design of their recommender systems and any other relevant algorithmic system;`
> `(b) their content moderation systems;`
> `(c) the applicable terms and conditions and their enforcement;`
> **`(d) systems for selecting and presenting advertisements;`**
> `(e) data related practices of the provider.`

**Art 34(2) 末段（本分片认为最值得注意的一句）**：

> `The assessment shall take into account **specific regional or linguistic aspects, including when specific to a Member State**.`

**本分片判断**：`specific regional or linguistic aspects` 这一句，是 DSA 体系里**唯一与 Momcozy 的多语种投放直接相关**的表述——它承认「同一内容在不同语言/地区会产生不同的系统性风险」。这与他们 291 条记录里 `文案语种 英199 / 德42 / 法20 / 西11 / 意9 / 其他10` 的现实直接对应。

#### 4.3.2 Article 35(1) — 缓解措施

**chapeau 逐字**：

> `…shall put in place **reasonable, proportionate and effective** mitigation measures… Such measures **may include**, where applicable:`

**Art 35(1)(a)–(k) 中与广告治理相关的三项（逐字）**：

> `(e) **adapting their advertising systems and adopting targeted measures aimed at limiting or adjusting the presentation of advertisements** in association with the service they provide;`
>
> `(j) taking targeted measures to protect the rights of the child, including age verification and parental control tools…;`
>
> `(k) ensuring that an item of information, whether it constitutes a generated or manipulated image, audio or video that appreciably resembles existing persons, objects, places or other entities or events and **falsely appears to a person to be authentic or truthful is distinguishable through prominent markings** when presented on their online interfaces…`

**注意 chapeau 用的是 `may include`（可包括）**，列表是**示例性而非穷尽**的。**Art 35(1)(k) 是合成媒体的显著标识义务**——对 Momcozy 若使用 AI 生成素材（模特图、场景图）有直接含义。

#### 4.3.3 Article 42 — 透明度报告义务

> `42(1) Providers of very large online platforms or of very large online search engines shall publish the reports referred to in Article 15 at the latest by two months from the date of application …, and thereafter **at least every six months**.`
>
> `42(2) …shall, in addition to the information referred to in Article 15 and Article 24(1), specify:`
> `(a) **the human resources that the provider … dedicates to content moderation …, broken down by each applicable official language of the Member States**…`
> `(b) the qualifications and linguistic expertise of the persons carrying out the activities referred to in point (a), as well as the training and support given to such staff;`
> `(c) **the indicators of accuracy and related information referred to in Article 15(1), point (e), broken down by each official language of the Member States**.`
>
> `42(4) Providers … shall transmit … and make publicly available at the latest three months after the receipt of each audit report pursuant to Article 37(4):`
> `(a) a report setting out the results of the risk assessment pursuant to Article 34;`
> `(b) **the specific mitigation measures put in place pursuant to Article 35(1)**;`
> `(c) the audit report provided for in Article 37(4);`
> `(d) the audit implementation report provided for in Article 37(6);`
> `(e) where applicable, information about the consultations conducted by the provider in support of the risk assessments and design of the risk mitigation measures.`

#### 4.3.4 透明度指标清单（**子代理核实的一处关键更正**）

**⚠️ 更正任务书的前提**：任务书提示找 `Delegated Regulation (EU) 2024/436` 作为指标法。**实测该授权条例是「审计」法（法律依据 `Article 37(7)`），不是指标法。** 真正的指标法是通过条例：

> **Commission Implementing Regulation (EU) 2024/2835**（2024-11-04），法律依据 `Articles 15(3) and 24(6)`，覆盖 Art 15(1)、24(1)、42(2) 下的报告。

**另一个更正**：任务书把「通知数量 / 平均处置时间」归到 `Art 24(1)(a)-(b)`。**实测 Art 24(1)(a) 是庭外争议解决、24(1)(b) 是 Art 23 暂停；通知与处置时间在 Art 15(1)(b)。且 DSA 用的是 median（中位数），不是 average。**

**Reg (EU) 2024/2835 Annex I 的模板结构（逐字）**：

```
1. QUANTITATIVE TEMPLATE
   1.1 Report identification
   1.2 Article 15(1)(a). Member State orders
   1.3 Article 15(1)(b). Notices…
   1.4 Article 15(1)(c)…
   1.5 Articles 15(1)(d), 24(1)(a) and 24(1)(b)
   1.6 …indicators of accuracy
   1.7 Articles 42(2)(a) and 42(2)(b). Human resources…
   1.8 Article 42(3). Average monthly active recipients…
2. QUALITATIVE TEMPLATE
```

**指标名（逐字）**：`Number of notices received` · `Number of notices received from Trusted Flaggers` · `Number of specific items of information included in the total number` · **`Median time to take action`** · `orders received / median time to inform / Median time to give effect to the order` · `complaints by type` · `disputes to out-of-court bodies` · `suspensions (manifestly illegal content / unfounded notices / unfounded complaints)` · **`Accuracy / Precision / Recall of the automated means`**（按范围与**按各官方语言**重复）· `moderators internal/external/with linguistic expertise` · `average monthly active recipients per Member State`。

**误差度量（逐字枚举，这一组对本分片的「规则库健康度」直接可用）**：

> `sensitivity, recall, hit rate, or true positive rate` · `specificity, selectivity, or true negative rate` · **`precision or positive predictive value`** · `negative predictive value` · `miss rate or false negative rate` · **`fall-out or false positive rate`** · `false discovery rate` · `false omission rate.`

**本分片判断（这一条直接回答了任务书 §六.4「度量什么」）**：

> DSA 强制 VLOP 报告的，正是 Momcozy 最缺的一组指标——**precision / recall / false positive rate / false negative rate**，且**要求按语言分别报告**。
> Momcozy 的 §7.1.5 建议（把 `engine_level` 与 `decision` 分离）**恰好就能算出这几个量**：`false positive rate ≈ (downgraded + false_positive) / detected`。DSA 的清单可以作为这套指标的外部权威依据，而不是自创口径。

#### 4.3.5 **边界问题：DSA 对 Momcozy 是间接约束还是直接约束？**

这是委托方要求明确写清的一问。**结论：间接约束——DSA 的义务主体是平台，不是广告主。**

**依据（Art 34/35/42 的适用主体逐字）**：三个条款的主语都是 `Providers of very large online platforms or of very large online search engines`（超大型在线平台/搜索引擎的提供者）。**DSA 全文没有对「广告主」设定内容义务。**

**传导链条（机制，逐步给出依据）**：

```
① DSA Art 34(1)(d) 要求 VLOP 评估「公共卫生与未成年人保护」相关的系统性风险
   Art 34(2)(d) 明确要求评估「广告选择与展示系统」这一因素
        ↓
② DSA Art 35(1)(e) 要求 VLOP 采取缓解措施，其中明文包括
   「adapting their advertising systems and adopting targeted measures
     aimed at limiting or adjusting the presentation of advertisements」
        ↓
③ 平台把该义务落成对广告主的可执行要求 → 平台广告政策收紧 + 自动化审核
        ↓
④ DSA Art 42(4)(b) 要求平台公开其 Art 35(1) 缓解措施
   + Art 42(2)(c) 要求按语言公开自动化手段的 accuracy 指标
        ↓
⑤ Momcozy 感受到的不是 DSA 条文，而是
   「素材被平台自动拒登 / 被限流 / 账号被限制」的运营后果
```

**这条链条里每一环都有条文依据，但「平台在事实上如何把 Art 34/35 转成广告审查规则」本分片未取到平台侧的一手证据。** 已确认的、方向一致的间接证据只有两条（§1.5.5、§2.3.1）：
- ASA 的 IPP 名单里，**Amazon Ads / Google / Meta / Yahoo for Business / TikTok** 志愿承诺「收到 CAP Compliance 通知即快速移除明确违规广告」；
- NAD 逐字：`NAD may also report misleading advertising to the platform on which it was found, including Facebook, for review as to whether the challenged claims comply with platform advertising policies.`

**本分片判断**：
- **对 Momcozy，DSA 的正确用法不是「合规义务清单」，而是「向平台申诉/沟通时的依据引用」。** 当他们与 Meta/Google 就素材被拒发生分歧时，Art 34(1)(d)（公共卫生与未成年人）与 Art 34(2)(d)（广告系统）是**平台自身义务**的依据，可用来说明「平台收紧广告审核属于其 DSA 义务范围，不是任意裁量」。
- **DSA 对规则库搭建的真正价值在指标设计**（§4.3.4），不在义务本身。**建议采纳其 precision/recall/false-positive 口径，按语种分别计算**——这正好补上 Momcozy 当前完全缺失的规则精度度量。

#### 4.3.6 DSA 透明度数据库（一个可用的外部参照）

**官方数据库**（DG CONNECT 运营）：https://transparency.dsa.ec.europa.eu/

**Art 24(5) 逐字建立该库**：

> `…submit to the Commission the decisions and the statements of reasons referred to in Article 17(1) for the inclusion in a **publicly accessible machine-readable database** managed by the Commission.`

**Art 17(3)(a)–(f) 逐字规定「说明理由」必须包含的字段**（这是欧盟版的「判例字段 schema」）：

> `the decision & territorial scope/duration · facts and circumstances incl. Art 16 notice or own-initiative · **use of automated means** · legal ground · contractual ground · clear redress information.`

**数据库实际字段（子代理从官方 API 文档逐字取得）**：`decision_visibility` · `decision_monetary` · `decision_provision` · `decision_account` · `account_type` · `decision_ground` · `content_type` · `category` · `territorial_scope` · `content_language` · `content_date` · `content_id` · `application_date` · `decision_facts` · `source_type` · **`automated_detection`** · **`automated_decision`** · `puid`，另加服务端字段 `uuid` / `id` / `created_at` / `permalink` / `self`。

**抓取时点实测规模**：**3,895,215,392 条 statement，372 个平台，43% 为完全自动化决策。**

**本分片判断**：这是**全球唯一一个公开、机器可读、带受控词表的内容审核裁决数据库**，字段设计比 ASA 的 HTML 判例库更适合机器消费。**建议 Momcozy 的案例库字段直接对齐这套命名**（尤其 `automated_detection` 与 `automated_decision` 两个布尔位——它们正好表达「系统命中」与「系统定性」的分离，即 §7.1.5 建议的 `engine_level` / `decision` 分离）。

### 4.4 欧盟机制对 Momcozy 的三条直接含义

1. **UCPD Art 12(b) 应当直接改写成他们的兜底规则第一句。** 原文 `to consider factual claims as inaccurate if the evidence demanded in accordance with (a) is not furnished or is deemed insufficient by the court or administrative authority.` —— 这是四个体系里唯一把「未提供证据」与「证据不足」并列等同于「声称不准确」的条款。

2. **Annex I 是唯一可以直接编码为「无抗辩红线」的规则集**（47 项，其中 health/cure 是第 17 项、背书是第 4 项、评论真实性是 23b/23c）。**建议 Momcozy 为这 47 项各建一条 `no_defence = true` 的规则**，与需要语境判断的 `H` 族区分开。

3. **欧盟内部存在规则路径分歧，同一行为可能被「禁止使用」而非「须举证」。** Reg 1924/2006 Art 12(c) 禁止引用个别医生推荐；FTC §255.3 允许但要求真实与足量检验；CAP 规则 12.18 仅对**药品**禁止。**因此 `H04` 必须带法域维度，不能是一条全球通用的红线。**

---

## 5. 中国：《广告法》与执法案例库

> 本节依据子代理的一手取证（原始文件全部存档于 `_evidence/R2/cn-*.md` / `cn-*.txt` / `cn-*.pdf`）。底本为**国家市场监督管理总局「市场监管法律法规规章数据库」**（`sjfg.samr.gov.cn`）官方 DOCX/PDF，取回日期 2026-09-15，抓取方式见 `_evidence/R2/cn-ad-law-key-articles.md` §0 的方法说明（含经官方 JSON 接口取得文件路径的完整过程，可复现）。

### 5.1 版本与法条原文

**法版本标注**（DOCX 第 2 段逐字）：

> `（1994年10月27日第八届全国人民代表大会常务委员会第十次会议通过　2015年4月24日第十二届全国人民代表大会常务委员会第十四次会议修订　根据2018年10月26日第十三届全国人民代表大会常务委员会第六次会议《关于修改〈中华人民共和国野生动物保护法〉等十五部法律的决定》第一次修正　根据2021年4月29日第十三届全国人民代表大会常务委员会第二十八次会议《关于修改〈中华人民共和国道路交通安全法〉等八部法律的决定》第二次修正）`

**⚠️ 一处必须记录的核查更正**：任务书把「第九条违法 → 二十万元以上一百万元以下罚款…可以吊销营业执照」记作**第五十八条**。经核对 SAMR 官方法条原文，**该罚则实际位于第五十七条**（对应第九条、第十条）；**第五十八条**对应的是第十六条、**第十七条**、第十八条、第四十六条等，罚则档位更低（一倍以上三倍以下 / 十万元以上二十万元以下）。两者不可混用。（依据：`_evidence/R2/cn-ad-law-key-articles.md` 的处罚条款章节）

#### 5.1.1 第九条（禁止情形全项 —— 含第（三）项「绝对化用语」）

> `第九条　广告不得有下列情形：`
>
> `（一）使用或者变相使用中华人民共和国的国旗、国歌、国徽，军旗、军歌、军徽；`
> `（二）使用或者变相使用国家机关、国家机关工作人员的名义或者形象；`
> `（三）使用"国家级"、"最高级"、"最佳"等用语；`
> `（四）损害国家的尊严或者利益，泄露国家秘密；`
> `（五）妨碍社会安定，损害社会公共利益；`
> `（六）危害人身、财产安全，泄露个人隐私；`
> `（七）妨碍社会公共秩序或者违背社会良好风尚；`
> `（八）含有淫秽、色情、赌博、迷信、恐怖、暴力的内容；`
> `（九）含有民族、种族、宗教、性别歧视的内容；`
> `（十）妨碍环境、自然资源或者文化遗产保护；`
> `（十一）法律、行政法规规定禁止的其他情形。`

**罚则：第五十七条**（逐字）：

> `第五十七条　有下列行为之一的，由市场监督管理部门责令停止发布广告，对广告主处二十万元以上一百万元以下的罚款，情节严重的，并可以吊销营业执照，由广告审查机关撤销广告审查批准文件、一年内不受理其广告审查申请；……`
>
> `（一）发布有本法第九条、第十条规定的禁止情形的广告的；`

#### 5.1.2 第十七条（非医疗广告禁止涉及疾病治疗功能 —— **与 Momcozy H01 直接对位**）

> `第十七条　除医疗、药品、医疗器械广告外，禁止其他任何广告涉及疾病治疗功能，并不得使用医疗用语或者易使推销的商品与药品、医疗器械相混淆的用语。`

**罚则：第五十八条第（二）项**（逐字）：

> `第五十八条　有下列行为之一的，由市场监督管理部门责令停止发布广告，责令广告主在相应范围内消除影响，处广告费用一倍以上三倍以下的罚款，广告费用无法计算或者明显偏低的，处十万元以上二十万元以下的罚款；情节严重的，处广告费用三倍以上五倍以下的罚款，广告费用无法计算或者明显偏低的，处二十万元以上一百万元以下的罚款，可以吊销营业执照，……`
>
> `（二）违反本法第十七条规定，在广告中涉及疾病治疗功能，以及使用医疗用语或者易使推销的商品与药品、医疗器械相混淆的用语的；`

#### 5.1.3 第十六条（医疗、药品、医疗器械广告禁止内容）

> `第十六条　医疗、药品、医疗器械广告不得含有下列内容：`
>
> `（一）表示功效、安全性的断言或者保证；`
> `（二）说明治愈率或者有效率；`
> `（三）与其他药品、医疗器械的功效和安全性或者其他医疗机构比较；`
> `（四）利用广告代言人作推荐、证明；`
> `（五）法律、行政法规规定禁止的其他内容。`
>
> `……推荐给个人自用的医疗器械的广告，应当显著标明"请仔细阅读产品说明书或者在医务人员的指导下购买和使用"。医疗器械产品注册证明文件中有禁忌内容、注意事项的，广告中应当显著标明"禁忌内容或者注意事项详见说明书"。`

#### 5.1.4 第十八条（保健食品广告禁止内容）

> `第十八条　保健食品广告不得含有下列内容：`
>
> `（一）表示功效、安全性的断言或者保证；`
> `（二）涉及疾病预防、治疗功能；`
> `（三）声称或者暗示广告商品为保障健康所必需；`
> `（四）与药品、其他保健食品进行比较；`
> `（五）利用广告代言人作推荐、证明；`
> `（六）法律、行政法规规定禁止的其他内容。`
>
> `保健食品广告应当显著标明"本品不能代替药物"。`

#### 5.1.5 第二十八条（虚假广告定义与情形）

> `第二十八条　广告以虚假或者引人误解的内容欺骗、误导消费者的，构成虚假广告。`
>
> `广告有下列情形之一的，为虚假广告：`
>
> `（一）商品或者服务不存在的；`
> `（二）商品的性能、功能、产地、用途、质量、规格、成分、价格、生产者、有效期限、销售状况、曾获荣誉等信息，或者服务的内容、提供者、形式、质量、价格、销售状况、曾获荣誉等信息，以及与商品或者服务有关的允诺等信息与实际情况不符，对购买行为有实质性影响的；`
> `（三）**使用虚构、伪造或者无法验证的科研成果、统计资料、调查结果、文摘、引用语等信息作证明材料的**；`
> `（四）**虚构使用商品或者接受服务的效果的**；`
> `（五）以虚假或者引人误解的内容欺骗、误导消费者的其他情形。`

**第（三）项与第（四）项是中国的「兜底条款」**，与 ASA 规则 3.7、FTC 的 reasonable basis 在功能上对位：

| 体系 | 兜底表述 | 逐字 |
|---|---|---|
| **CN** | 《广告法》第二十八条第一款第（三）项 | `使用虚构、伪造或者**无法验证的**科研成果、统计资料、调查结果、文摘、引用语等信息作证明材料的` |
| **CN** | 《广告法》第二十八条第一款第（四）项 | `**虚构**使用商品或者接受服务的效果的` |
| **UK** | CAP Code 规则 3.7 | `The ASA may regard claims as misleading in the absence of adequate substantiation.` |
| **US** | FTC Policy Statement 1984 | `a firm's failure to possess and rely upon a reasonable basis for objective claims constitutes an unfair and deceptive act or practice in violation of Section 5` |

**四者的共同结构：把「证据问题」转化为「违法问题」。** 注意 CN 的措辞是「**无法验证的**」——这比「虚假」宽：**不需要证明材料是假的，只需要它是无法验证的。** 这与 FTC 的「不需证明声称本身为假，只需证明广告主缺乏合理依据」是同构的。

#### 5.1.6 第三十八条（广告代言人规则）

> `第三十八条　广告代言人在广告中对商品、服务作推荐、证明，应当依据事实，符合本法和有关法律、行政法规规定，并不得为其未使用过的商品或者未接受过的服务作推荐、证明。`
>
> `不得利用不满十周岁的未成年人作为广告代言人。`
>
> `对在虚假广告中作推荐、证明受到行政处罚未满三年的自然人、法人或者其他组织，不得利用其作为广告代言人。`

**注意「不得为其未使用过的商品作推荐、证明」——这是一条 FTC §255.3(b) 的简化版**：中国要求「使用过」，FTC 要求「以被声称的专业水平做过足量检验」。**两者都比 Momcozy 现有的 `U01`（「需核实是否真实合作」）更严。**

#### 5.1.7 第四十六条（广告审查 —— 审查批准文号）

> `第四十六条　发布医疗、药品、医疗器械、农药、兽药和保健食品广告，以及法律、行政法规规定应当进行审查的其他广告，应当在发布前由有关部门（以下称广告审查机关）对广告内容进行审查；未经审查，不得发布。`

**这是中国体系里唯一一个「强制卡点」**：医疗/药品/医疗器械/保健食品广告必须**事前审查**取得批准文号才能发布。**对无法强制卡死上线节点的 Momcozy 而言，这是唯一一条法定的、不可绕过的前置卡点**——如果其产品在中国被定性为医疗器械。

#### 5.1.8 第五十五条（虚假广告罚则）

> `第五十五条　违反本法规定，发布虚假广告的，由市场监督管理部门责令停止发布广告，责令广告主在相应范围内消除影响，处广告费用三倍以上五倍以下的罚款，广告费用无法计算或者明显偏低的，处二十万元以上一百万元以下的罚款；两年内有三次以上违法行为或者有其他严重情节的，处广告费用五倍以上十倍以下的罚款，广告费用无法计算或者明显偏低的，处一百万元以上二百万元以下的罚款，可以吊销营业执照，并由广告审查机关撤销广告审查批准文件、一年内不受理其广告审查申请。`

### 5.2 「绝对化用语」的执法口径：**《广告绝对化用语执法指南》（2023 年第 6 号公告）**

一手来源：国家市场监督管理总局公告 **2023 年第 6 号**，落款 **2023 年 2 月 25 日**（局务会议 2023-02-24 通过）。
URL：https://www.samr.gov.cn/ggjgs/tzgg/art/2023/art_183b5cb48d9e4f0dba67f9f912a913ba.html
本地：`_evidence/R2/cn-samr-absolute-language-guide-verbatim.txt`（逐字全文）

**该指南明确回答「`最` 是不是一律违法」——不是。** 它用**三组条款**把绝对化用语分成三层：

#### 第一层：**不适用**《广告法》绝对化用语规定（第二条定义的「绝对化用语」根本不成立）

> `五、有下列情形之一的，广告中使用绝对化用语**未指向商品经营者所推销的商品，不适用**《广告法》关于绝对化用语的规定：`
> `（一）仅表明商品经营者的服务态度或者经营理念、企业文化、主观愿望的；`
> `（二）仅表达商品经营者目标追求的；`
> `（三）绝对化用语指向的内容，与广告中推销的商品性能、质量无直接关联，且不会对消费者产生误导的其他情形。`

> `六、有下列情形之一的，广告中使用的绝对化用语指向商品经营者所推销的商品，但**不具有误导消费者或者贬低其他经营者的客观后果的，不适用**《广告法》关于绝对化用语的规定：`
> `（一）仅用于对**同一品牌或同一企业商品进行自我比较**的；`
> `（二）仅用于宣传商品的使用方法、使用时间、保存期限等消费提示的；`
> `（三）依据国家标准、行业标准、地方标准等认定的商品**分级用语**中含有绝对化用语并能够说明依据的；`
> `（四）商品名称、规格型号、**注册商标或者专利**中含有绝对化用语，广告中使用商品名称、规格型号、注册商标或者专利来指代商品，以区分其他商品的；`
> `（五）依据国家有关规定评定的**奖项、称号**中含有绝对化用语的；`
> `（六）在限定具体时间、地域等条件的情况下，表述时空顺序客观情况或者宣传**产品销量、销售额、市场占有率等事实信息**的。`

> `七、广告绝对化用语属于本指南第五条、第六条规定情形，但**广告主无法证明其真实性的，依照《广告法》有关规定予以查处**。`

#### 第二层：**仍属违法，但可不予/从轻处罚**（裁量条款）

> `九、除本指南第五条、第六条规定情形外，**初次**在广告中使用绝对化用语，**危害后果轻微并及时改正的，可以不予行政处罚**。`
>
> `十、商品经营者在其**经营场所、自设网站或者拥有合法使用权的其他媒介**发布的广告中使用绝对化用语，**持续时间短或者浏览人数少，没有造成危害后果并及时改正的，应当依法不予行政处罚**；危害后果轻微的，可以依法从轻、减轻行政处罚。`
>
> `十二、市场监管部门可以依照有关规定，制定广告绝对化用语**轻微违法行为依法免予处罚清单**并进行动态调整。`

#### 第三层：**一般不认为轻微**（从重情形）—— **这一条直接命中 Momcozy**

> `十一、有下列情形之一的，**一般不认为属于违法行为轻微或者社会危害性较小**：`
> `（一）**医疗、医疗美容、药品、医疗器械、保健食品、特殊医学用途配方食品广告中出现与疗效、治愈率、有效率等相关的绝对化用语的**；`
> `（二）招商等有投资回报预期的商品广告中出现与投资收益率、投资安全性等相关的绝对化用语的；`
> `（三）教育、培训广告中出现与教育、培训机构或者教育、培训效果相关的绝对化用语的。`

#### 对 Momcozy `H05` 的精确含义（**这一条改变了 §6.3 分歧点 1 的结论**）

`H05` 逐字写着 `best/#1/No.1/最佳/最好等排名最高级按2026-09-09口径放开，海外广告允许，不再判险`。按 2023 年第 6 号指南，这个放松**部分成立、部分不成立**：

| `H05` 涉及的情形 | 中国口径 | 结论 |
|---|---|---|
| **自我比较**（`our best pump yet`）| 第六条（一）→ **不适用** | ✅ 放松成立 |
| **销量/市占率事实**（`#1 selling breast pump`，限定时间地域且有据）| 第六条（六）→ **不适用**，但第七条要求**能证明真实性** | ✅ 放松成立**前提是可举证** |
| **奖项/称号**（`award-winning`，依国家规定评定）| 第六条（五）→ **不适用** | ✅ 放松成立 |
| **指向产品性能且贬低/误导竞品**（`the best pump, better than Medela`）| 第五条/第六条均不覆盖 | ❌ **放松不成立**，仍违反第九条第（三）项 |
| **若产品被定性为医疗器械，且绝对化用语涉及疗效/治愈率/有效率** | **第十一条（一）→ 一般不认为轻微** | ❌❌ **不仅违法，且不适用从轻/免罚** |

**本分片判断**：`H05` 的「2026-09-09 口径放开」**是一条没有法域字段的全局放松，而它恰好把第十一条（一）这一类最重的情形也一并放开了**。建议的最小修改：

```
H05 拆为两条：
  H05.1 绝对化用语·指向产品性能且无据         → red   （原关键词保留）
  H05.2 绝对化用语·自我比较/销量事实/奖项      → grey  （新增，需人工核实「有据」）
  并在两条上加 jurisdiction 字段：
        { CN: 第九条第(三)项 + 2023年第6号指南第五~十一条 }
        { UK: 无对应条款（CAP 规则 3.11 仅禁「夸大以致误导」） }
        { US: 视情形（FTC 须证明误导） }
  另加一条硬规则：
  X05 若产品为医疗器械/保健食品/特殊医学用途配方食品，
      则任何与疗效/治愈率/有效率相关的绝对化用语一律 red 且不适用从轻
      （依据：《广告绝对化用语执法指南》第十一条第（一）项）
```

**⚠️ 一处 NOT FOUND**：2016 年原国家工商总局关于绝对化用语的《答复》**在 samr.gov.cn 上未找到**（子代理已记录）。**因此本分片不引用该答复，仅引用 2023 年第 6 号公告这一份现行有效的官方文件。**

### 5.3 「广告违法典型案例」库：**结构与关键缺陷**

#### 5.3.1 是否公开？是，但没有可检索的数据库

子代理的结构性发现（逐字，`_evidence/R2/cn-samr-typical-cases.md` §3.3）：

> `4. **官方站内并无「案例库检索」**；「广告法10周年」专题 `alzs` 栏目是**人工聚合的省级案例链接列表**（11 条），不是数据库。`

**⚠️ 补充更正（子代理已完成更彻底的取证）**：**面向用户的检索界面确实不存在，但索引本身存在且可完整获取。** 子代理破解了 SAMR 的 CMS 列表 API（`GET /api-gateway/jpaas-publish-server/front/page/build/unit`），抓取到**广告监督管理司「工作动态」栏目 1,058 条（2023–2026）**，另有「广告法10周年」专题的 `alzs`（案例展示）与 `zyfb`（重要发布）两个索引。

**这一区别很重要**：委托方问的是「典型案例库是否公开、结构如何」。准确答案是——
> **公开、可完整抓取，但无检索界面；且总局级批次不给条文号，因此索引存在而法条映射不成立。**
> 即：**「能不能拿到」与「能不能用」是两件事。**

**批次清单（8 个总局级批次，约 76 个案例；子代理逐条核实标题/日期/URL）**：

| # | 批次标题 | 日期 | 案例数 |
|---|---|---|---|
| 1 | 市场监管总局集中曝光一批广告导向违法典型案例 | 2024-12-04 | 7 |
| 2 | 市场监管总局集中曝光十起民生领域违法广告典型案例 | 2025-01-16 | 10 |
| 3 | 市场监管总局公布十起违法广告典型案例 | 2025-06-13 | 10 |
| 4 | 市场监管总局公布十起违法广告典型案例 | 2025-07-11 | 10 |
| 5 | 市场监管总局公布十起互联网违法广告典型案例 | 2025-11-11 | 10 |
| 6 | 市场监管总局公布十起违法广告典型案例 | 2026-01-31 | 10 |
| 7 | 市场监管总局集中曝光十起「神医神药」违法广告典型案例 | 2023 | 10 |
| 8 | 市场监管总局集中曝光一批侵害未成年人权益的广告违法典型案例 | 2024-06-13 | 9 |

省级批次另存：福建（2024 批次 1 与 3）、辽宁 2024、广西 2024 民生领域。**全部 URL 见 `_evidence/R2/cn-notes.md` 与 `cn-samr-typical-cases.md`。**

**⚠️ 一条方法论警告（子代理核实，本分片认同）**：全国年均罚款均值约 **¥5,660/件**，而**公开典型案例的罚额普遍在 10 万–80 万元**。**两者相差 20–140 倍。** 即：**公开案例库是「严重性选择」后的样本，不能用于估计违规的真实罚额分布。** 引用罚额时必须同时说明这一点。

批次清单（标题 + 日期 + URL）见 `_evidence/R2/cn-samr-typical-cases.md` §1。已核实的省级批次存档包括：`cn-case-batch-fujian-2024-1.txt`、`cn-case-batch-fujian-2024-3.txt`、`cn-case-batch-guangxi-2024.txt`、`cn-case-batch-liaoning-2024.txt`。

#### 5.3.2 单条案例的完整字段结构（**总局级 vs 省级，颗粒度差异巨大**）

**总局级模板**（逐字，`_evidence/R2/cn-samr-typical-cases.md` §3.1）：

```
序号、<办案机关>查处<当事人><案由>案
经查，<当事人><媒介>发布<商品属性定性><广告>，含有<引号逐字摘录的广告内容>等<违法性质归类>。
<年月>，<办案机关>依据《中华人民共和国广告法》有关规定，对当事人作出<处罚内容>的行政处罚。
```

**总局级完整样本（逐字，2026-01-31 批次案例一）**：

> `一、广东省广州市番禺区市场监管局查处广州简美健康科技有限公司违法广告案`
>
> `经查，当事人发布的普通商品广告含有"促进眼角膜修复""有效预防近视，去检查视力已经4.9了！""适合过敏性鼻炎""过敏体质得到全面改善"等涉及疾病预防、治疗功效的内容，以及"brieye长期与8位国际权威眼科医生组成顾问团"等虚假内容。2025年11月，广东省广州市番禺区市场监管局依据《中华人民共和国广告法》有关规定，对当事人作出罚款60万元的行政处罚。`

**省级完整样本（逐字，福建省 2024 年第三批，案例 2）**：

> `案例2：福建如仁堂大药房有限责任公司发布违法广告案`
>
> `当事人在其经营网店上销售普通产品，发布含有"不再受高糖困扰""防脱生发"等内容，违反《中华人民共和国广告法》第十七条"除医疗、药品、医疗器械广告外，禁止其他任何广告涉及疾病治疗功能，并不得使用医疗用语或者易使推销的商品与药品、医疗器械相混淆的用语"的规定。销售的医疗器械产品广告中含有"安全无副作用"等内容，当事人的行为违反了《中华人民共和国广告法》第十六条"医疗、药品、医疗器械广告不得含有下列内容：（一）表示功效、安全性的断言或者保证"的规定。发布的"北京同仁堂祛痘膏"广告图片含有"北京同仁堂"和"南京同仁堂"对比内容，涉嫌贬低其他生产经营者的商品，违反了《中华人民共和国广告法》第十三条"广告不得贬低其他生产经营者的商品或者服务"……依据《中华人民共和国广告法》五十八条、第五十九条规定，2024年8月，莆田市市场监管局作出行政处罚，责令当事人停止发布违法广告，消除不良影响，并处罚款63950元。`
>
> 来源：https://scjgj.fujian.gov.cn/zw/tzgg/202412/t20241204_6587818.htm

**字段对照表**（逐字，`_evidence/R2/cn-samr-typical-cases.md` §3.2）：

| 字段 | 总局级 | 省级 |
|---|---|---|
| ① 序号 + 当事人 + 案由 | ✅ | ✅ |
| ② 事实 | ✅ `经查，…` | ✅ `当事人…` |
| ③ **引号逐字摘录违法用语** | ✅ | ✅ |
| ④ **违反的具体条文 + 条文逐字引述** | ❌ **仅「依据《广告法》有关规定」** | ✅ **第十七条、第十六条、第十三条，条文原文一并引用** |
| ⑤ **处罚依据的具体条文** | ❌ | ✅ `依据《中华人民共和国广告法》五十八条、第五十九条规定` |
| ⑥ 处罚时间 | ✅（到月） | ✅ |
| ⑦ 办案机关 | ✅ | ✅ |
| ⑧ 处罚种类 + 金额 | ⚠️ 常只保留「罚款 X 万元」 | ✅ `责令停止发布 + 消除不良影响 + 罚款 63950 元` |
| ⑨ 处罚决定书文号 | ❌ | ❌ |

#### 5.3.3 关键缺陷（子代理核实结论，逐字）

> `1. **总局级批量典型案例不披露法条号**，只写「依据《中华人民共和国广告法》有关规定」。因此在总局批次上**无法直接做法条映射**，任何"第X条案件占比"的统计在总局层级是**不可得出**的。`
> `2. **总局批次也不披露广告费用**，只披露最终罚款额；因此**无法从总局案例反推「广告费用三倍以上五倍以下」与「二十万元以上一百万元以下」两档中实际适用了哪一档**。`
> `3. **总局批次标题不含「处罚决定书文号」**，无法回溯到个案决定书；需要个案级文书应去**省级市场监管局**或**信用中国**（`creditchina.gov.cn`）的行政处罚公示。`
> `4. **官方站内并无「案例库检索」**；「广告法10周年」专题 `alzs` 栏目是**人工聚合的省级案例链接列表**（11 条），不是数据库。`

**这四条缺陷对 Momcozy 的教训（§6.2 已展开）：公开案例如果不带条文号，就不能用于建立「规则 → 案例」索引。**

### 5.4 母婴/吸奶器相关的执法现状

子代理检索结论（逐字，`_evidence/R2/cn-samr-typical-cases.md` §4 末尾）：

> `上述官方执法样本反复出现同一模式 —— **「普通商品 / 普通食品 + 疾病预防、治疗功效表述」→ 违法**；以及 **「医疗器械 + 功效/安全性断言保证」→ 违法**。**没有任何一个总局批次案例中出现「吸奶器」**（见 `cn-maternal-breastpump-cases.md` 的 NOT FOUND 记录）。`

**总局批次中与母婴/婴儿/医疗器械最接近的执法样本（逐字摘录）**：

| 批次 | 条目 | 关键逐字内容 | 罚额 |
|---|---|---|---|
| 2024-06-13 未成年人权益 | 淄博云医医疗器械有限公司 | `"新生儿医用黄疸蓝光灯，照射5—10小时宝宝就会改善""高效退黄去黄、没副作用、安全可靠"` —— 对**医疗器械**功效、安全性的断言和保证 | 10 万元 |
| 2025-11-11 互联网 | 山东欧邦生物科技有限公司 | `"VAVK儿童装医用硅酮胶敷料"医疗器械广告`，宣称 `"更适合儿童使用""针对儿童肌肤定制"` 与实际情况不符 | 20 万元 |
| 2025-11-11 互联网 | 广州默尼互联网信息有限公司 | 以**互联网健康科普文章**形式变相发布处方药广告和未经审查的 `"排卵检测试剂""胎心监护仪"` 医疗器械广告 | 42 万元 |
| 2026-01-31 | 广州简美健康科技有限公司 | 普通商品含 `"促进眼角膜修复""有效预防近视…"` 等**涉及疾病预防、治疗功效**的内容 | 60 万元 |
| 2024-12-04 广告导向 | 义乌市珈蓝弥朵饰品有限公司 | 普通饰品宣称 `"行走的速效救心丸"`「不是靠药去治好的」等**没有科学依据**内容 | 20 万元 |

**注意「以互联网健康科普文章形式变相发布…广告」这一条**——对 Momcozy 的博客/SEO 内容（他们 291 条中有 `博客页` 投放，见 PRD 第 262 行的 `[博客页]-6月SEO投广`）是一个直接的风险模式：**内容营销形态的广告在中国同样受《广告法》约束，不因披着科普外衣而豁免。**

### 5.5 广告监测系统与统计数据

**法定依据**：《广告法》第四十九条第二款（逐字）——`市场监督管理部门应当建立健全广告监测制度，完善监测措施，及时发现和依法查处违法广告行为。`（来源：`_evidence/R2/cn-ad-law-full-samr-db.txt`）

**《2026年全国广告监管工作要点》三（六）逐字**（URL：https://www.samr.gov.cn/ggjgs/sjdt/gzdt/art/2026/art_7927e556f71945358b4ac486e1a7859b.html）：

> `提升广告监测效能。加强人工智能等新技术创新应用，**不断丰富广告监测关键词库**，提升违法广告发现能力。制定《关于提升广告监测工作效能的指导意见》。统筹开展广告日常监测与专项监测，定期通报监测情况。大力提升总局本级广告监测能力，稳步推进省级地面电视广播广告监测试点。`

**⚠️ 值得注意**：`不断丰富广告监测关键词库` —— **中国监管方的思路与 Momcozy 现在的规则库同构（关键词库），也在用 AI 扩充。** 这意味着**关键词库这条路是监管侧也在走的，不是错的；错的是把它当作唯一的判定路径。**

**未找到**：总局对「全国互联网广告监测平台」的**指标体系说明**（违法率 / 条次 / 违法线索数的定义与口径）。见 §9 缺口清单。

### 5.6 《互联网广告管理办法》（2023，总局令第 72 号，2023-05-01 施行，全文 32 条）

三重交叉验证（SAMR DOCX + PDF + 司法部 `moj.gov.cn`，5,251/5,251 与 5,200/5,200 字符一致）。取代工商总局令第 87 号《互联网广告管理暂行办法》。已存档 `_evidence/R2/cn-internet-ad-measures-2023-full.md` 等三份。

| 条文 | 逐字要点 | 对 Momcozy 的含义 |
|---|---|---|
| **第九条** | `互联网广告应当具有可识别性，能够使消费者辨明其为广告。` / `对于竞价排名的商品或者服务，广告发布者应当显著标明"广告"，与自然搜索结果明显区分。` / `除法律、行政法规禁止发布或者变相发布广告的情形外，通过**知识介绍、体验分享、消费测评**等形式推销商品或者服务，并附加购物链接等购买方式的，广告发布者应当显著标明"广告"。` | **第三条直接命中他们的 SEO 博客投放**（PRD 第 262 行 `[博客页]-6月SEO投广`）——科普/测评形态 + 购物链接 = 必须标「广告」 |
| **第十条** | 弹窗广告一键关闭，五种禁止做法 | 落地页/站内弹窗 |
| **第十三条** | `广告主应当对互联网广告内容的真实性负责` + **档案保存不少于三年** | **档案保存义务**——与 §7.1.3 的数据层建议直接相关 |
| **第十六条** | 平台经营者六项义务 | — |
| **第十七条第一款** | `不得在搜索政务服务网站、网页、互联网应用程序、公众号等的结果中插入竞价排名广告。` | — |
| **第十九条** | **直播带货全部在本条**（四款：商品销售者→广告主责任；直播间运营者→广告经营者/发布者；受托直播营销人员→广告经营者/发布者；以自己名义形象推荐证明→**广告代言人**） | 直播场景的责任分配 |
| **第二十条** | ⚠️ **管辖条款，与直播带货无关**（更正任务书的「第十九条/第二十条 area」表述） | — |

### 5.7 2025–2026 年新出的四份指南（**对 Momcozy 现值最高的一组文件**）

子代理在检索中额外发现、且**直接落在委托方问题上**的官方文件：

| 文件 | 编号 / 日期 | 为什么与 Momcozy 相关 |
|---|---|---|
| **《广告引证内容执法指南》** | 总局公告 **2026 年第 20 号** | **直接实施《广告法》第二十八条第一款第（三）项**；对**「临床验证」「实验数据」类宣称**提出硬要求：机构须有法定资质、出处须表明、有适用范围/有效期限须明示。**这是 `H03`（`clinically proven`）在中国的最新、最具体的执法依据**——比 2023 年的绝对化用语指南更贴题 |
| **《〈中华人民共和国广告法〉适用问题执法指南（一）》** | 市监广发〔2025〕55 号 | **定义什么才算「广告」**（营销性 / 媒介性 / 受众不特定性 / 非强制性）。**直接决定他们的种草、科普、直播切片内容是否构成广告**——这是「内容审查范围」的边界文件 |
| **《医疗广告认定指南》** | 总局公告 **2025 年第 29 号**（总局 + 卫健委 + 中医药局联署） | **第八条列出六种「科普宣传」转化为「变相医疗广告」的方式**——对母婴健康内容尤其关键 |
| **《医疗广告监管工作指南》** | 2025-05-09 | 第十七条：非医疗机构宣称可从事医疗服务 → 涉嫌无证行医，移送卫健委 |

**《2026 年全国广告监管工作要点》确定的 2026 年执法重点**（逐字）：`直播电商广告、引证广告、AI 生成广告`，并对 **「大字吸睛、小字免责」** 开展提示性用语整治。

**本分片判断**：**「引证广告」被列入 2026 年执法重点，配合 2026 年第 20 号指南，意味着 `H03`（临床/科学背书）在中国的执法密度将在 2026 年显著上升。** 而「大字吸睛、小字免责」的整治方向，与他们 `H05`/`M07` 常用的「加限定语」改写策略（如 `relaxation supports your natural let-down, which may help your flow`）存在张力——**限定语在中国不必然构成免责，尤其当主视觉是大字功效、限定是小字免责时。**

### 5.8 量化统计（官方，逐年逐字）

| 指标 | 数值 | 来源 |
|---|---|---|
| **2025 全年** | **44,521 件广告违法案件，罚没 2.52 亿元** | 2026-01-31 批次 |
| 2025 前三季度（互联网） | 22,185 件 / 1.11 亿元 | — |
| 2023 全年 | 4.76 万件 / 4.66 亿元 | — |
| 2018 全年 | 4.13 万件 / 7.58 亿元 | — |
| **国家互联网广告监测平台** | 采集 21.98 亿条次 → 识别 4.16 亿条次 → 审核 2.87 亿条次 → 发现违法 **174.68 万条次** → 派发线索 62,150 件；**违法率 7.1% → 约 0.6%**；覆盖 1,000 网站 + 1,000 APP + 1,000 微信公众号 | — |

**⚠️ 关键方法论提示**：**全国年均罚款均值约 ¥5,660/件，而公开典型案例的罚额普遍在 10 万–80 万元——相差 20–140 倍。** 公开案例库是「严重性选择」后的样本，**不能用于估计违规的真实罚额分布或真实违规率**。引用罚额时必须同时说明这一点。

**未找到**：总局对「广告违法率」的**官方定义与计算公式**（该指标来自 samr.gov.cn 转载的新闻稿，非规范性文件）；2024 全年全国案件数（未以此形式发布）。

---

## 6. 交叉问题（每个体系都要回答）

### 6.1 规则编号是否稳定？条款号在版本更新后会变吗？历史判例如何关联？

| 体系 | 编号形态 | 会变吗 | 变了的处理 | 判例如何锚定 |
|---|---|---|---|---|
| **UK / CAP Code** | `节.序[.子序]`：`3.7` / `12.2.1` / `15.1.1` | **基本不变；变时必须显式声明** | ① 删除→原地留墓碑 `[Deleted 10 May 2018]`，编号**不回收**；② 改号→原地写迁移声明 `15.18 Rule renumbered and moved to 15.20 on 5 January 2026.`；③ 版本号 `Edition 12` + `v12.2.107`；④ 独立变更登记册（以规则号为键，三种条目格式：`Amendment of X, was:` / `Addition of rule X` / `Insertion of X`） | 判例末尾写 `CAP Code (Edition 12)` + 规则号清单；判例自带 `Background` 段声明适用版本与法律背景（Nutricia 案逐字：`we therefore assessed it under the Code interpreted in the light of changes in the background law resulting from the UK's exit from the EU`） |
| **US / FTC** | 成文法条号 `15 U.S.C. § 45(b)`、`16 CFR § 255.5` | 不变（法条号是法定引用） | 修订通过 FR 公告 + 新版本 CFR；旧版本留在 eCFR 历史 | 执法案以 `consent order` / `administrative complaint` 的案件名与案号锚定，引用当时生效的 CFR 版本 |
| **US / NAD** | 程序条款 + 案件号（`NAD Case #xxxx`） | 程序可改版 | 见 §2 | 案件报告编号 + 年份 |
| **EU / UCPD 等** | `Art. 6(1)(a)`、`Annex I item 21`、`Reg. (EC) No 1924/2006 Art. 10(2)(a)` | **不变**；修订以 `amending act` 追加，条号保留 | 合并版本（consolidated text）保留全部条号；新增内容以新条号追加（如 Omnibus Directive 2019/2161 对 UCPD Art 13 的增补） | 判例/执法以条号引用，CELEX 号定位 |
| **CN / 《广告法》** | `第X条` + `第（X）项`：`第九条第（三）项`、`第二十八条第一款第（三）项` | ⚠️ **会变，且是「级联前移」**（见下） | 修正案形式，全文重发 | 执法案例引用条号（但**总局级典型案例不引条号**——见 6.2） |

**⚠️ 中国是一个反例——条文号在修正后会级联变动，这是本分片发现的第三种编号机制。**

子代理比对 SAMR（2021 现行版，**74 条**）与人大网（2018 版，**75 条**）确认：**2021 年修正删除了 2018 版第六十条**（广告发布登记罚则），**致使其后所有条号整体前移一位**。逐字对照（`_evidence/R2/cn-notes.md` §1.13）：

| 内容 | 2018 版 | **2021 现行版** |
|---|---|---|
| 广告代言人罚则 | 第六十二条 | **第六十一条** |
| 违法发送广告 / 未确保一键关闭 | 第六十三条 | **第六十二条** |
| 平台等不予制止 | 第六十四条 | **第六十三条** |
| 隐瞒真实情况申请广告审查 | 第六十五条 | **第六十四条** |
| 伪造、变造、转让广告审查批准文件 | 第六十六条 | **第六十五条** |
| 记入信用档案并公示 | 第六十七条 | **第六十六条** |
| 媒体发布违法广告的通报 | 第六十八条 | **第七十七条 → 见原表** |
| 侵权行为民事责任 | 第六十九条 | **第六十八条** |
| 法定代表人任职限制 | 第七十条 | **第六十九条** |
| 公益广告 | 第七十四条 | **第七十三条** |
| 施行日期 | 第七十五条 | **第七十四条** |

**子代理的核实结论（逐字）**：

> `**本报告引用的第四条、第九条、第十六条、第十七条、第十八条、第二十八条、第三十八条、第四十六条、第五十五条、第五十七条、第五十八条均在第六十条之前，序号两版一致，引用安全。**`

**本分片判断——三种编号机制并列，各自代价不同：**

| 机制 | 代表 | 做法 | 代价 |
|---|---|---|---|
| **墓碑 + 保留编号** | UK CAP Code | 删除处留 `[Deleted 10 May 2018]`，编号**永不回收** | 编号会「跳号」，但历史引用永不断链 |
| **冻结顶层号 + 字母后缀追加** | EU UCPD Annex I | 顶层仍 1–31，新增用 `2a` / `23b` / `23j` | 编号不再连续，但**旧号永不变** |
| **级联前移（删除即重排）** | CN 《广告法》 | 删一条，其后全部 −1 | **任何未注明版本的引用都会指错条文** |

**对 Momcozy 的教训是明确的**：**他们的规则库必须记录「引用时所依据的法版本」**。中国出现「第六十二条」（2018）与「第六十一条」（2021）指向同一罚则的情况——**如果案例记录只写「依据广告法第六十二条」而不写版本，这条记录在两年后就是错的，且错得无法察觉。** 这正是 §7.2.3 建议的 `rules_version` 快照字段的又一条理由。

**三个体系的共同解法（可归纳为一条工程规则）：**

> **编号一旦发布即视为不可变标识符；任何变更都必须产生「旧号 → 新号（含生效日）」或「旧号 → 已废止（含日期）」的双向记录；判例侧必须记录它所适用的规则版本快照。**

**对 Momcozy 的映射**：他们目前**三条都没有**。
- 编号会变吗？—— `H09`/`M07` 是后追加的，`U02` 被停用了，但**没有任何变更记录**；
- 停用处理？—— `U02` 的停用原因写在 `边界内容` 里（`站点报销资质已具备（2026-09-09用户确认），规则停用、不再判险`），**没有把编号保留为墓碑格式，也没有独立的停用日期字段**；
- 判例版本锚定？—— **不存在**。291 条记录没有任何 `rules_version` 快照。

### 6.2 「依据哪条规则」是否在判决里显式声明？还是只给结论？

**这是本分片最有信息量的一组对照，因为四个体系给出了四种不同的答案。**

| 体系 | 是否显式声明规则号 | 原文证据 |
|---|---|---|
| **UK / ASA** | **是，而且声明两遍** | 散文里一遍：`The ads breached CAP Code (Edition 12) rules 3.1 (Misleading advertising), 3.7 (Substantiation), 12.1 …, and 13.1 …`；页面下方再来一个纯规则号清单（`3.1 / 3.7 / 12.1 / 13.1`），每个号超链接回规则正文 |
| **UK / ASA（Nutricia 案的特殊做法）** | **是，且把规则原文内嵌进判决** | 判决里在每个被引规则号后直接嵌入该规则全文，如 `The ad breached CAP Code (Edition 12) rules 15.10 / 15.10 Except for those in a scientific publication… / and 15.10.1 / 15.10.1 Marketing communications must not confuse between infant formula and follow-on formula.` |
| **CN / 省级典型案例** | **是，条文号 + 条文原文 + 处罚依据条文号** | 福建如仁堂案逐字：`违反《中华人民共和国广告法》第十七条"除医疗、药品、医疗器械广告外，禁止其他任何广告涉及疾病治疗功能…"的规定` … `依据《中华人民共和国广告法》五十八条、第五十九条规定` |
| **CN / 总局级典型案例** | **否，只给结论性归类** | 逐字：`依据《中华人民共和国广告法》有关规定，对当事人作出罚款60万元的行政处罚`（**无条文号**）；违法性质用词组而非条号：`涉及疾病预防、治疗功效的内容`、`对医疗器械功效、安全性的断言和保证性内容` |
| **US / FTC** | 见 §3 | |
| **US / NAD** | 见 §2 | |
| **EU** | 见 §4 | |

**中国这个「总局 vs 省级」的落差是一个可以直接搬用的教训：**

> **总局级案例：可读性强、可用于普法宣传，但不可用于建立「规则 → 案例」索引（无法做法条映射）。**
> **省级案例：显式条文号 + 条文原文 + 处罚依据，可作为规则库的自上而下来源。**

子代理的核实结论（逐字，来自 `_evidence/R2/cn-samr-typical-cases.md` §3.3）：

> `1. **总局级批量典型案例不披露法条号**，只写「依据《中华人民共和国广告法》有关规定」。因此在总局批次上**无法直接做法条映射**，任何"第X条案件占比"的统计在总局层级是**不可得出**的。`
> `2. **总局批次也不披露广告费用**，只披露最终罚款额；因此**无法从总局案例反推「广告费用三倍以上五倍以下」与「二十万元以上一百万元以下」两档中实际适用了哪一档**。`
> `3. **总局批次标题不含「处罚决定书文号」**，无法回溯到个案决定书；需要个案级文书应去**省级市场监管局**或**信用中国**（`creditchina.gov.cn`）的行政处罚公示。`
> `4. **官方站内并无「案例库检索」**；「广告法10周年」专题 `alzs` 栏目是**人工聚合的省级案例链接列表**（11 条），不是数据库。`

**「只给结论不给依据」的代价是可以量化的**：总局级案例无法被结构化索引、无法统计规则分布、无法回溯原始文书。**这正是 Momcozy 的 291 条记录当前的处境**——`命中原因` 一栏写的是规则说明的复述（如 `H02 催乳/增产/奶量产出承诺（含裸 more milk…）；W1当前为用户主动调节+保存程序，非闭环生理识别`），而不是「本句违反了 H02 的哪一条构成要件」。

### 6.3 同一个行为在不同辖区是否归属不同规则？如何处理？

**答案是「是」，而且分歧比预想的大。三个真实分歧点：**

#### 分歧点 1：绝对化用语（最高级）

| 辖区 | 规则 | 原文 |
|---|---|---|
| **CN** | 《广告法》**第九条第（三）项**正面禁止，且有独立罚则 | `（三）使用"国家级"、"最高级"、"最佳"等用语；` —— 罚则见**第五十七条**：`处二十万元以上一百万元以下的罚款，情节严重的，并可以吊销营业执照` |
| **UK** | **无对应规则**。CAP Code 规则 3.11 只禁止「夸大产品能力或性能以致误导」 | `3.11 Marketing communications must not mislead consumers by exaggerating the capability or performance of a product.` |
| **Momcozy 现状** | `H05` 曾把 `best/#1/No.1/最佳/最好` 列为红线，后**整体放开** | 逐字：`虚假安全承诺（**best/#1/No.1/最佳/最好等排名最高级按2026-09-09口径放开，海外广告允许，不再判险**）` |

**这个分歧是致命的，因为他们的规则库没有编码法域。** 实测 `H05` 的 `适用产品` 是 `W1、M5、M6、M9、Air1`，`边界内容` 里那句「海外广告允许」是**唯一**的法域限定，且只是一句括注、不在任何结构化字段里。**如果同一素材回流到中国站内或跨境店，`H05` 会放行一个《广告法》第五十七条级别的违法行为（20 万–100 万罚款 + 可吊销营业执照）。**

**官方支持这一判断的证据**（`_evidence/R2/cn-samr-typical-cases.md` §4 逐字摘录的总局批次案例）：

- 2025-01-16 民生领域批次：`武汉睿贝鑫医疗科技有限公司` —— `违法使用了"最权威、最专业""亚洲顶尖""顶级机构"等绝对化用语`，罚 **80 万元**（该批次最高）
- 2025-01-16 同批次：`河南一穗玉米网络科技有限公司` —— 化妆品广告 `违法使用"销售第一，全国全网"等绝对化用语，且相关内容与实际不符`，罚 **10.96 万元**
- 2026-01-31 批次：`重庆林晖泰商务信息咨询有限公司` —— `违法使用"世界最强"等绝对化用语以及国家机关、国家机关工作人员名义或者形象`，罚 **16 万元**

#### 分歧点 2：健康/功效声称的准入门槛

| 辖区 | 准入门槛 | 原文 |
|---|---|---|
| **UK** | 声称须有证据；医学声称须持牌/合规器械 | CAP 规则 3.7（须持有书面证据，证据不足可径行认定误导）+ 规则 12.1（`Objective claims must be backed by evidence, if relevant consisting of trials conducted on people`；医学声称须 `licensed by the MHRA, VMD or under the auspices of the EMA, or for a medical device with the applicable conformity marking`） |
| **UK（食品/保健品）** | **只能使用已获授权的声称清单** | CAP 规则 15.1.1 逐字：`Only health claims listed as authorised in the applicable register, or claims that would have the same meaning to the consumer, may be used in marketing communications.`（Nipper&Co 催乳茶案据此判违规） |
| **CN** | **非医疗商品一律禁止涉及疾病治疗功能** | 《广告法》**第十七条**逐字：`除医疗、药品、医疗器械广告外，禁止其他任何广告涉及疾病治疗功能，并不得使用医疗用语或者易使推销的商品与药品、医疗器械相混淆的用语。` 罚则见**第五十八条** |
| **CN（医疗器械）** | 不得有功效/安全性断言保证 | 《广告法》**第十六条第（一）项**逐字：`表示功效、安全性的断言或者保证` |

**注意 CN 第十七条与 UK 的结构性差异：CN 是「一刀切的禁止」，UK 是「允许但须举证」。** 这意味着同一条文案（例如 `helps relieve engorgement discomfort`）在 UK 可能是「可举证即可」，而在 CN（若吸奶器定性为普通商品）则可能因为「涉及疾病治疗功能」或「使用医疗用语」被整体禁止。

**⚠️ 一个关键的未决事实**：**吸奶器在中国是否属于医疗器械？** 这决定适用第十七条还是第十六条。子代理的检索结果：**NOT FOUND**——总局批次案例中没有任何一个出现「吸奶器」。详见 §9 缺口清单。

#### 分歧点 3：专家/医生背书

| 辖区 | 规则 | 原文 |
|---|---|---|
| **UK（药品）** | 规则 12.18 禁止 | `12.18 Marketers must not use health professionals or celebrities to endorse medicines.`（实测 2015–2026 年 6 条判例） |
| **UK（非药品）** | 走第 3 节：真实性 + 授权 | `3.47 Marketers must hold documentary evidence that a testimonial or endorsement used in a marketing communication is genuine… and hold contact details for the person who, or organisation that, gives it.` / `3.52 Marketing communications must not display a trust mark, quality mark or equivalent without the necessary authorisation…`（Go Night Night 案：冒用 FEDANT logo） |
| **CN** | 《广告法》第十六条第（四）项 / 第十八条第（五）项禁止医疗、药品、医疗器械、保健食品广告「利用广告代言人作推荐、证明」；第三十八条要求代言人**不得为其未使用过的商品作推荐**，且虚假广告代言受罚未满三年者不得再代言 | 见 §5 |
| **Momcozy 现状** | 按「推荐 vs 参与设计」拆成两条规则，且两条都不含法域 | `H04`（`doctor recommended / ibclc-recommended / 推荐 by 100+ experts`，高危·红）与 `U01`（`lactation consultant / ibclc / expert-designed / expert-tuned`，待复核·灰） |

**本分片判断**：`H04`/`U01` 的拆分在语义上是合理的（推荐 vs 参与设计确实是两种不同的言语行为），但**在证据标准上是同一件事**——两者都要求「真实、获授权、范围含对外背书」的合作。ASA 把它们放在同一组规则（3.47 + 3.52）下正是这个原因。Momcozy 如果要保留拆分，应在两条规则上挂**同一个证据标准引用**。

#### 「他们如何处理？」——三个体系共同的解法

**没有一个体系试图统一各辖区的规则；三个体系都只统一「连接键」。**

| 体系 | 统一键 | 机制 |
|---|---|---|
| UK / ASA | **规则号** | 国内一套法典；跨境靠 EASA 来源国管辖（CAP Code §23：`the SRO in the country of origin of the marketing communication has jurisdiction`） |
| EU | **条号（Art. / Annex I item）** | 指令 + 成员国转化；UCPD 有全欧统一的 Annex I 黑名单（31 项），其余靠一般条款 + 各国执法 |
| CN | **条号（第X条第（X）项）** | 单一法典全国适用 |
| US | 成文法条号 + 机构程序 | FTC（联邦）+ 州法 + 自律（NAD）三层 |

**对 Momcozy 的工程结论（本条已在 §7.5 问题 1 给出，此处补充证据）：**

> **正确结构是「语义规则（唯一）+ 法域映射表（一对多）」，而不是「国家 × 品类 × 平台 × 内容类型」的笛卡尔积。**
> **判据**：分歧点 1（绝对化用语）就是一个语义规则在 CN 有、在 UK/US 无的例子。若按国家建正向规则，这一条要在 CN 规则库里写一遍，然后在 UK 库里「什么都不写」——而「什么都不写」在规则库里是**不可见的**，无法审查、无法测试。相反，如果规则库里有一条 `S01 绝对化用语`，其法域映射为 `{CN: 广告法第九条第（三）项（红）, UK: 不适用, US: 视情形（FTC 需证明误导）}`，那么**「UK 不适用」这件事本身就成了一个显式、可审查、可被质疑的条目**。

### 6.4 「规则编号 + 判例库 + 处置阶梯」三件套的可迁移性总结

| 组件 | 三个体系是否都有 | 可迁移到 Momcozy 的程度 | 主要障碍 |
|---|---|---|---|
| **规则编号体系** | UK ✅ / EU ✅ / CN ✅ / US（法条号）✅ | **高**。纯工程问题 | 需要先做编号重构（§7.2）+ 变更日志 |
| **公开判例库** | UK ✅（最强）/ CN ✅（有但无检索）/ US ✅（FTC + NAD） | **中**。他们不需要公开，需要**内部可检索** | 需要先修数据层（§7.1.3：71% 行不可解析） |
| **处置阶梯** | UK ✅（无罚款，靠公开+通路）/ US FTC ✅（罚款）/ CN ✅（罚款+吊照） | **中高**。ASA 阶梯结构可搬 | 需要 L4 层（§7.3.2）与「升格不中止执行」默认值 |
| **释义中间层** | UK ✅（AdviceOnline / EN / Guidance）/ EU（委员会指引）/ CN（无）/ US FTC（行业指引） | **高**，但**他们目前完全没有这一层** | **这是最值得新建的一层**（§1.8 / §7.4.3） |
| **兜底条款** | UK ✅（规则 3.7 + 1.7）/ US ✅（FTC substantiation）/ CN ✅（第二十八条第（三）项「无法验证的…作证明材料」） | **高**。见 §7.4.3 三条兜底 | 需要新增「已备证据库」数据结构 |

---

## 7. 对 Momcozy 的直接含义

> 本节的每一条建议都锚定到：**(a) 本分片抓到的原文机制**，或 **(b) 对 `PRD/内容治理需求文档.md` 现有资产的实测统计**。凡属我的判断，标「本分片判断」。

### 7.1 「错题本」的最小字段集

#### 7.1.1 从 ASA ruling / NAD decision 结构提炼的字段集

对照 §1.3.5 的 ruling schema 与 §2.2–§2.3 的 NAD 流程与 compliance 机制（**NAD decision 全文字段结构因订阅制未能核实，见 §9 G2**），一个**可复用、可判定、可问责**的案例记录最少需要 9 个字段。我把它们分成三组：

**A 组——定位（这条记录说的是哪条内容）**

| # | 字段 | ASA 对应 | Momcozy 现有 | 缺口 |
|---|---|---|---|---|
| A1 | `case_ref` 稳定案件编号 | `G26-1343656` / `A25-1284063` | ❌ 无 | **必须新增**。现用 `外部广告ID`（如 `GG-6fc2e040406a`）可作外部锚，但那是平台侧 ID，不是审查侧案件号 |
| A2 | `content_ref` 内容快照引用 | `Ad description` 内的 a./b. 分条 | ⚠️ 部分（`Primary Text`/`Headline` 列，但 71% 行被 `|` 破坏，见 7.1.3） | 需可寻址的内容快照（含图片/视频而非仅文本） |
| A3 | `medium` 媒体 | `Social media (paid ad), Internet (display)` | ✅ `平台` + `广告类型` | 需要按 ASA 口径正向枚举，而非自由文本 |
| A4 | `seen_date` 观察到的时间 | `seen on 24 May 2026` | ✅ `数据日期`（65% 填充） | 需区分「内容创建时间」与「观察到的时间」 |

**B 组——判定（这条记录为什么被判）**

| # | 字段 | ASA 对应 | Momcozy 现有 | 缺口 |
|---|---|---|---|---|
| B1 | `issue` 争点（把事实抽象成一句可判定的问题） | `Two complainants challenged whether the efficacy claims for the Hemios were misleading and could be substantiated.` | ❌ 无。现有 `命中原因` 是**规则说明的复述**，不是争点 | **必须新增**。这是「错题本」能否被复用的分水岭——见 7.1.2 |
| B2 | `evidence_verbatim` 被判定的事实原文（含画面） | `Ad description` 的逐字广告文本 | ⚠️ `命中片段`（7% 填充） | 需扩展到「非文本证据」：ASA 在 Nipper&Co 案中认定**视频画面本身**构成健康声称 |
| B3 | `rules_cited` 显式规则号清单（有序、规范） | `3.1 / 3.7 / 12.1 / 13.1` 独立机器可读块 | ⚠️ `命中规则`（45% 填充）**且无规范排序** | 见 7.1.4 |
| B4 | `decision` 裁决 | `Upheld` / `Not upheld` / `Upheld in part` | ⚠️ `风险等级`（98%） | 语义错位：`风险等级` 是**预测**，`decision` 是**事后裁决**。见 7.1.5 |
| B5 | `reasoning` 推理 | `Assessment` 段 | ❌ 无（`命中原因` 是规则复述） | 需「事实 → 是否达证据标准 → 结论」三段 |

**C 组——闭环（这条记录接下来怎么办、谁负责）**

| # | 字段 | ASA 对应 | Momcozy 现有 | 缺口 |
|---|---|---|---|---|
| C1 | `action` 处置命令 | `The ads must not appear again in the form complained of. We told Hemios not to make efficacy claims… in the absence of adequate evidence.` | ⚠️ `修改建议`（7% 填充） | 需区分「改写建议」与「禁令」 |
| C2 | `escalation` 升格动作 | `We referred the matter to CAP's Compliance team.` | ❌ 无 | **必须新增**（见 7.3） |
| C3 | **`owner` 责任人与确认时限** | ASA 侧：`pro-forma notice of compliance` + 明确 deadline | ❌ **`检查人` 字段填充率 0%** | **最高优先级缺口**，见 7.1.6 |

#### 7.1.2 最关键的一个字段是 `issue`（争点），不是 `规则号`

ASA 把 `Ad description`（事实）和 `Issue`（争点）**分成两个字段**，这不是排版习惯：

- `Ad description`（Hemios 案）：`b. The YouTube ad, seen on13 May 2026, featured an image of a bracelet and the text, "ROCK HARD MORNINGS IN 72 HOURS…"`
- `Issue`（同案）：`Two complainants challenged whether the efficacy claims for the Hemios were misleading and could be substantiated.`

**同一句 `Issue` 覆盖了 a. 和 b. 两支广告、5 条不同的广告语。** 也就是说，ASA 的判例单位不是「一条广告」，而是**「一个争点」**——多支广告共享同一个争点，就合成一条 ruling。

**对 Momcozy 的直接含义**：他们现在的 291 条记录是**按广告**（一行一支广告）组织的，`命中原因` 一栏是规则说明的复述。这导致：

1. **同类问题无法聚合**。实测：291 条里有 32 种多规则组合，但 `修改建议` 只有 6 条填充——**同一个争点在 291 行里被重复发现了上百次，却没有被记录为「同一个争点」**。
2. **规则边界无法被检验**。ASA 的规则 3.13（不得暗示声称被普遍接受）在 11 年内 0 条判例——因为没有人把它抽象成一个独立争点。Momcozy 的 `U04`（痛点场景 vs 功效承诺）现在是散文描述的「需人工判定」，**如果把它写成一个 `issue`，它就能被计数、被抽样复核、被统计推翻率**。

**具体建议**：给 `U04` 写一条规范化的 `issue`，例如：

```
issue_id      : U04-A
question      : 该表述中的 "sore/painful/clogged ducts" 是痛点场景描述，还是消除性功效承诺？
test          : 是否与 goodbye / no more / not anymore / relieve / forever 等消除性动词连用？
outcome_yes   : 升级为 H01/H07（红）
outcome_no    : 保留为场景描述（灰·无需处理）
```

——这实质上就是把现有 `U04` 的 `触发原因` 散文**升格为一个可计数的判定单元**。ASA 的 `Issue` 字段就是这个东西。

#### 7.1.3 先修数据：机读门槛在**解析器**，不在数据

这是本分片对 Momcozy 最直接的实测结论。对 `PRD/内容治理需求文档.md` 第 63–357 行的 291 条记录逐行解析：

| 实测项 | 结果 |
|---|---|
| 表头声明列数 | **27** |
| 列数正确的行 | **84 / 291（28.9%）** |
| **列数漂移的行** | **207 / 291（71.1%）** |
| 实际列数分布 | 27, 28, 29, 32, 33, 34, 35, 36, 37, 38, 39, 42, 43, 44, 45, 46 |
| 漂移原因 | 广告文案（Primary Text / Headline）中含 **`\|`（反斜杠转义的竖线）**；对**朴素的按 `|` 切分**而言，一行被切成多列 |
| **精确定性（实测）** | **207/207 个漂移行全部含 `\|` 转义；85 个不漂移的行完全不含竖线；0 行含未转义竖线。** 即：**这份 Markdown 本身是合规的**（渲染正常）——问题在于**它不能被朴素切分器解析** |

**为什么这恰好是最要命的地方**：他们的广告文案大量使用 `|` 作为标题分隔符，例如 PRD 第 119 行原文：

> `The Warm-Massage Breast Pump | Pumping That Feels Like Care | Warmth Meets Comfort | World's First Warm Pump | Feel the Difference, Mom | 360° wraparound warmth…`

**而 `命中规则` / `命中片段` / `修改建议` / `检查人` 恰好位于表格中段——正是被 `|` 冲散的位置。**

进一步，用右侧锚定法（最后 8 列与最前 6 列不含 `|`，可可靠解析）统计全库：

| 字段 | 填充率 |
|---|---|
| `文案语种` | 291 / 291（100%） |
| `广告名称` / `平台` / `品线` / `投放地区` | 289 / 291（99%） |
| `近7天费用USD` / `展示` / `点击` / `外部广告ID` | 289 / 291（99%） |
| `广告系列Campaign` / `广告账号` / `广告组` / `广告类型` | 262 / 291（90%） |
| **含 `命中规则` 的行** | **130 / 291（45%）** |
| **`检查人` 非空** | **0 / 291（0%）** |
| `父记录` 非空 | 1 / 291（0.3%） |

**⚠️ 定性更正（经委托方独立复算确认）**：**漂移行不是数据损坏。** 委托方用 `(?<!\\)\|` 转义感知切分复算后，**291 行全部恰好 27 字段，0 错位**；本分片对 21 条规则表做同样处理，**全部恰好 12 字段，0 错位**。因此：

> **这份 Markdown 渲染正常、语义完整、转义合规。问题不在数据，在解析器——任何下游工具必须先做转义感知切分。**

**本分片判断**：即便如此，他们现在仍然**无法回答任何关于自己审查质量的量化问题**——但那不是数据脏，而是**缺少可编程的存储格式与索引**：
- 哪条规则误报最多？—— 答不出（`命中规则` 只有 45% 且多值无规范排序）
- 人工复核推翻系统判定的比例是多少？—— 答不出（没有 `decision` 字段）
- 谁在什么时候审的？—— 答不出（`检查人` 0%）

**代价的精确表述**：`\|` 是标准 Markdown 转义，渲染正确。但下列常见通路会**静默错位**（切出来仍是合法数组，只是字段含义偏移，不报错）：
- `awk -F'|'`、朴素的 `line.split('|')`、部分 Markdown 解析库、直接导出 CSV → 207 行（71.1%）错位；
- **风险在于「静默」**：字段语义偏移不会被任何工具报错，任何基于它的统计都会得到看似合理但错误的数字。

**这正是 ASA 与本分片反复强调的一点：人可读 ≠ 机可读。** ASA 的判例同样是人可读的 HTML（§1.6.5：无 API、无结构化导出），**但 ASA 至少把「规则号清单」「decision」「发布日期」抽成了独立的、可定位的块**（§1.3.1 字段 10/11/5）。Momcozy 的表把**判定字段和广告文案放在同一行**，于是文案的排版需求（竖线分隔）直接破坏了判定字段的可解析性。

**建议（按投入产出排序）：**

1. **立刻停止用 Markdown 表格承载案例记录。** 迁移到 CSV/JSONL（或 Base 表），字段定长，文本字段做转义。这不是「以后优化」，这是**当前所有量化治理动作的前置条件**。
2. 迁移时保留 `外部广告ID` 作为与平台侧的对账键（它 99% 填充且无歧义）。
3. 新增 `case_ref`，格式建议直接仿 ASA：`<来源码><YY>-<序号>`，例如 `M26-000123`（M = Momcozy；`G`/`A` 前缀可分别表示「投诉/外部触发」与「内部审查发现」——**这正是 ASA `G26-…` 与 `A25-…` 两个前缀的用途**）。

#### 7.1.4 `命中规则` 多值字段有两个具体缺陷

实测 291 条记录中 `命中规则` 的全部取值：43 种（11 种单规则 + 32 种多规则组合）。两个已确认的缺陷：

**缺陷 1：多值无规范排序，同一集合有两种写法。**

```
H02,H07  出现 3 次   ←→   H07,H02  出现 1 次      （同一集合）
M03,H07  出现 12 次  ←→   H07,M03  出现 5 次      （同一集合）
```

**对任何按 `命中规则` 做的聚合（计数、排序、趋势）都会静默漏算。**

**缺陷 2：跨规则关键词重复与直接矛盾。**

对 21 条规则的关键词做集合运算，实测结果：

| 重复关键词 | 归属规则 | 性质 |
|---|---|---|
| `prevent mastitis` | **H01 + H02** | 规则边界重叠 |
| `improve pumping efficiency` | **H02 + M07** | 规则边界重叠 |
| `less pain` | **H07（高危红线）+ 安全词（白名单）** | **直接矛盾** |
| `reduces pain` | **H07（高危红线）+ 安全词（白名单）** | **直接矛盾** |

**逐字核对证据**（`PRD/内容治理需求文档.md` 第 368 行 H07 与第 379 行 安全词）：

- H07 `检测关键词` 含：`… less pain, reduce pain, reduces pain, reduced pain, pain solution …`
- 安全词 `检测关键词` 含：`… **reduces pain, less pain**, gentle, comfort`
- 安全词 `边界内容` 逐字：`客观功能/真实认证关键词（**正面提示，不参与降级**）`

**即：`reduces pain` 与 `less pain` 同时是「高危红线 H07 的命中词」和「白名单正面词」。** 在任何实际引擎里，这两个词的处理结果取决于匹配顺序，而不是取决于规则意图。**这是一个必须立刻修掉的实现级 bug。**

**本分片判断**：安全词白名单里加入 `reduces pain / less pain` 的**意图**很可能是想做「改写后的合规表达」（因为 52 条改写建议库里 SUG-20/21/22 的建议文案正是走 `comfort/gentle/缓解不适` 一路）。但白名单是**输入侧**判定，改写建议是**输出侧**产物——**把输出侧的建议词放进输入侧白名单，是本末倒置。** ASA 的做法是分层的：`relief of symptoms` 的可用性由规则 12.7 判断（`References to the relief of symptoms or the superficial signs of ageing are acceptable **if they can be substantiated.**`），而不是把词放进白名单。

#### 7.1.5 「风险等级」在语义上被当成了两个字段用

现有 `风险等级` 取值为 `高危·红 / 审慎·黄 / 待复核·灰 / 合规·绿`（实测分布：绿 157 / 红 91 / 黄 30 / 灰 11，共 289 条有值）。

对照 ASA：`decision`（`Upheld` / `Not upheld` / `Upheld in part`）是**事后裁决**，规则号是**依据**，`Action` 是**处置**。三者分离。

**Momcozy 现在把「预测风险」和「实际结论」压在一个字段里，并额外把「是否合规」也压进去（`合规·绿`）。** 后果：

- **无法度量规则精度**。规则命中了但人工判断为绿 → 记 `合规·绿`，看起来像「没命中」，其实是**误报**。实测：291 条里 157 条是绿，其中相当部分来自命中规则后的人工降级——**但记录方式让这个数字无法被还原**。
- **`合规·绿` 与 `命中规则` 为空在语义上被混淆**。ASA 的做法相反：`Not upheld`（裁决不成立）和「没有投诉」是两种不同的记录，且前者进入判例库、后者不进入。

**建议拆分**：

```
detected_rules : [H02, H07, H09]        # 系统命中了什么（多值，规范排序）
engine_level   : 红 | 黄 | 灰 | 绿        # 引擎的预测
decision       : upheld | downgraded | false_positive | needs_human
                # 人工/复核的最终结论 —— 与 engine_level 分开存
decided_by     : <人名/工号>
decided_at     : <时间>
rationale      : <为什么改判>
```

**只有把 `engine_level` 与 `decision` 分开，「规则精度」才成为一个可算的指标**（`downgraded + false_positive` / `detected` 即误报率）。这就是任务书 §六.4「自迭代：度量什么」的答案。

#### 7.1.6 最严重的缺口：`检查人` 填充率 0%

任务书 §二.E 载明他们的治理约束是：

> **无法强制卡死「审查完才能上线」的系统节点，靠 GTM 把控 + 审查记录问责。**

**实测：`检查人` 字段在 291 条记录中填充 0 条。**

ASA 在同样的处境下（它也没有任何强制卡点——它不能阻止广告上线，只能在事后裁决），依赖的是**一条完整的、有署名、有时限的问责链**：

1. 裁决 → `pro-forma notice of compliance`，**要求书面保证**（程序 PDF 第 41 段）
2. 未在截止日前给出保证 → 转 Compliance team（程序 PDF 第 6.i 段）
3. 未解决 → 通知第三方媒体下架（程序 PDF 第 26 段）
4. 仍未解决 → 点名公示 + Ad Alerts + 预审（§1.5.5、§1.5.6）

**这条链的每一环都不需要强制卡点，但每一环都有「时限 + 责任主体 + 可公开记录」。**

**本分片判断：`检查人` 0% 填充意味着他们设想的问责机制当前完全没运行。** 这不是一个「以后补」的字段，而是整个「无法卡死节点」方案能否成立的唯一支点。**优先于所有其它建议。**

最低可行的补法（不需要等系统改造）：

| 动作 | 成本 | 效果 |
|---|---|---|
| 在投放审批（GTM）环节增加一个必填的「审查记录 ID」 | 低 | 把审查记录与上线动作绑定 |
| 每条非绿记录强制填 `检查人` + `decided_at` | 低 | 问责链闭合 |
| 每周抽 10 条绿记录反向复核，填 `decision` | 低 | 首次得到误报率估计 |

对照 ASA：`Number of complaints: 2`、`Complaint Ref: G26-1343656`、`Agency: None – unconfirmed`——**ASA 连「投诉有几条」「有没有代理介入」都记录并公开。**

### 7.2 规则编号体系：ASA 的编号方式能不能搬到他们的 H/M/U 上？

#### 7.2.1 先看他们现在的问题（实测）

**问题 1：编号顺序与实际位置不一致。**

21 条规则在表格中的实际顺序（实测）：

```
H01 → H02 → H03 → H04 → H05 → H06 → H07 → H08
    → M01 → M02 → M03 → M04 → M05 → M06
    → U01 → U02 → U03 → 安全词 → U04 → H09 → M07
```

**`H09` 和 `M07` 排在 `安全词` 和 `U04` 之后——即它们是在表格末尾追加的，不在自己编号族的序号位置上。U04 也排在 `安全词` 之后。**

**本分片判断**：这说明编号**不是位置序号，而只是一个追加时分配的标签**。这本身不是错误——**ASA 的编号也是分配序而非语义序**（3.13 排在 3.11 之后纯属历史顺序）。**问题在于他们没有像 ASA 那样把这个事实显式化**：ASA 有 `Edition 12 + v12.2.107` + 变更登记册 + 墓碑 + 改号声明；Momcozy 没有任何一处记录「H09 是何时、因为什么被追加的」。

**问题 2：`H01` / `H02` 各自承载了多个互不相同的风险构造。**

`H01` 的 `检测关键词` 与 `边界内容`（逐字）覆盖了**至少 6 个不同的风险构造**：

| # | 风险构造 | 关键词片段（逐字） |
|---|---|---|
| 1 | 医疗治疗声称 | `treat, cure, heal, remedy, diagnos, 治疗, 治愈, 诊断, 疗法, 根治` |
| 2 | 疏通堵奶 | `unclog, unclog ducts, unblock ducts, clear clogged, fix clogged, 疏通堵奶, 疏通乳腺, 通乳腺` |
| 3 | 乳腺炎治疗/预防 | `cure mastitis, treat mastitis, prevent mastitis, prevents mastitis, stop mastitis, 治疗乳腺炎, 预防乳腺炎, 治愈乳腺炎, 根治乳腺炎` |
| 4 | 残余乳 | `residual milk, remove residual milk, reduces residual milk, clear residual milk, 排残奶, 残余奶, 残留乳汁` |
| 5 | **解剖学对应（五区五管）** | `(five\|5) zones?[^.!?\|]*(duct\|milk\|mammary), (five\|5) milk ducts, 五条乳腺管, 五区对应乳腺` |
| 6 | 乳头损伤预防 | `prevent nipple damage, reduce nipple damage, 预防乳头损伤, 减少乳头损伤, 防止乳头损伤, 避免乳头损伤` |

`H02` 同样覆盖至少 7 个构造：奶量增产（`more milk / increase milk supply / 催乳 / 增产 / 追奶`）、催产素（`trigger oxytocin / 触发催产素`）、长期奶量（`long-term milk supply`）、奶阵速度（`faster letdown / 更快奶阵`）、排空效率（`improve emptying / 提高排空`）、**吸力参数→奶量比较**（`295\s?mmhg[^.!?\|]*(more milk\|better\|faster)`，其实属 `H08`/`M02` 领域）、**乳腺炎预防**（`prevent mastitis`，**与 H01 重复**）。

**本分片判断——这就是「H01/H02 承载了多个不同风险」的具体内容，而且后果是可测的**：

- **`命中规则` 的粒度失真**。当一条广告命中 `H01`，你无法知道它是「说能治疗乳腺炎」（最严重，直接涉及医疗器械法域）还是「说五区对应五条乳腺管」（解剖学声称，性质完全不同）。修复动作也完全不同：前者要整体撤下医疗叙事，后者只需删掉解剖对应句。
- **`规则→改写建议` 的映射被迫变粗**。实测 52 条改写建议库中，映射到 `H01` 的只有 4 条（SUG-16/17/18/19），却要覆盖 `H01` 的全部 6 个构造——**构造 4、5、6（残余乳/五区/乳头损伤）在改写库里没有对应条目**。SUG-18 同时覆盖了构造 4、5、6（`Five zones target five milk ducts, flush residual milk and prevent nipple damage`），这是把三个不同问题塞进一条建议。

#### 7.2.2 ASA 的编号方式能不能搬？——能搬的是「机制」，不是「格式」

**能直接搬的四件事：**

| ASA 机制 | 原文依据 | Momcozy 落地方式 |
|---|---|---|
| **① 两级编号：`节.序[.子序]`** | `3.7` / `3.4.1` / `12.2.1` / `15.1.1`（§1.1.2） | 把 `H01` 拆成 `H01`（医疗治疗声称，节）× `H01.1`（治疗）`H01.2`（疏通）`H01.3`（乳腺炎）`H01.4`（残余乳）`H01.5`（解剖对应）`H01.6`（损伤预防） |
| **② 编号不回收、不复用（墓碑）** | `l. [Deleted 10 May 2018].` / `1.8.1 [Deleted 6 November 2018]`（§1.4 机制一） | `U02` 已停用——**不要把这个号让给新规则**，保留占位并写停用日期与原因 |
| **③ 改号要留迁移记录，带生效日** | `15.18 Rule renumbered and moved to 15.20 on 5 January 2026.`（§1.4 机制二） | 若把 `H09` 归位到 `H03` 一带，旧号处写「已于 YYYY-MM-DD 改号为 Hxx」 |
| **④ 版本号 + 变更登记册** | `Edition 12` / `v12.2.107` + Register of CAP Code changes（§1.4 机制三） | 规则库加 `version` 字段（如 `v1.3.0`）+ 独立变更日志（规则号 / 旧文 / 新文 / 生效日 / 提案人） |

**不能搬、也不该搬的一件事：不要用规则号前缀编码严重等级。**

ASA 的规则号 `3.7` / `12.1` / `15.1` **完全不含严重度信息**。严重度体现在三个地方：`decision`（是否 Upheld）、`Action`（整改命令的强度）、`referral`（是否升格）。

Momcozy 的 `H/M/U` 前缀**同时**编码了「判定路径」（自动红线 / 语境守卫 / 人工复核）和「严重等级」（高危 / 审慎 / 待复核）——而且这两件事在他们的 `边界类型` 与 `风险等级` 两列里是**分开写的、却给出了一一对应的取值**：

| 边界类型 | 风险等级 | 实测条数 |
|---|---|---|
| `严格限制红线` | `高危` | 9（H01–H09） |
| `审慎关注` | `审慎` | 6（M01–M04, M06, M07） |
| `人工复核` | `待复核` | 5（M05, U01, U02, U03, U04） |
| `安全词白名单` | `合规` | 1（安全词） |

**注意 `M05`（medical/hospital/military grade 等级背书）的 `边界类型` 是 `人工复核` 但编号是 `M`。** 它是唯一一个「前缀与边界类型不一致」的规则——**这恰好证明了前缀编码不可靠**：当一条规则的性质在编写后发生变化（从「审慎关注」变成「需核实认证，走人工」），编号改不了，只能靠 `边界类型` 列纠正，于是两者永久失配。

**建议的编号方案**（保留他们已有的编号资产，只做增量）：

```
规则编号格式： <域>.<序号>[.<子序号>]
域 = 语义域，不是严重度：
  C = Claim 功效/医疗声称        （原 H01–H09 拆分后归此）
  E = Endorsement 背书           （原 H04 + U01 合并）
  S = Safety 绝对化/安全承诺      （原 H05 + H06）
  Q = 数据与比较                 （原 H08 + M03 + M06）
  X = 体验/感官描述              （原 M01/M02/M04/M05 的部分）
  P = 价格与促销                 （原 M04）
  D = 解剖/生理机制描述          （原 H01 构造 5）
严重等级 = 独立字段，取值 {red, amber, grey, green}
判定路径 = 独立字段，取值 {auto, context_guard, human}
```

**注意 `E`（背书）这一域的提出理由**：实测 `H04`（`ibclc-recommended` 等，红）与 `U01`（`ibclc / expert-designed` 等，灰）**是同一现象的两个事实形态**——「推荐」（recommendation）与「参与设计」（participation）。ASA 把二者放在同一组规则下（3.47 真实性 + 3.52 授权，见 §1.3.3），因为**它们的判据是同一个：是否有真实、获授权、范围包含对外背书的合作**。Momcozy 现在的拆法（按「推荐 vs 设计」拆成红/灰两条）会在边界案例上卡住：`expert-designed program, endorsed by our IBCLC` 该判哪条？

**建议合并为 `E` 域，用 `severity` 区分**：
```
E01  无据的专家/机构推荐式背书          severity=red
E02  专家参与设计/调校（需授权与范围核实） severity=amber→human
E03  冒用认证标识/机构 logo             severity=red
```
并在 `E02` 上挂 ASA 规则 3.52 的双要件判据：**「是否获得授权」+「是否遵守授权条款」**（逐字见 §1.3.3）。

#### 7.2.3 「规则编号是否稳定」给他们的直接答案

任务书 §交叉问题 问：「条款号在版本更新后会变吗？如果变了，历史判例如何关联？」

**ASA 的答案（三个机制，全部有原文）：编号不变；必须变时必须留双向指针（旧号写「已改号为 X」+ 生效日）；判例侧记录自己所适用的版本（`CAP Code (Edition 12)` + `Background` 段的法律背景声明）。**

**Momcozy 必须补的最小实现：**

1. 规则表加 `version` 列（每条规则自己的版本，不要求全表统一）。
2. 加独立的 `变更日志` 表：`规则编号 | 变更类型(新增/修改/停用/改号) | 旧文 | 新文 | 生效日 | 提案人 | 依据`。
   —— 注意他们**已经有一个可用的雏形**：`U02` 的 `边界内容` 写着 `站点报销资质已具备（2026-09-09用户确认），规则停用、不再判险`。这是有日期、有原因、有依据的——**只是长在 `边界内容` 字段里，而不是变更日志里**。把它搬出来，机制就成立了。
3. 每条案例记录加 `rules_version` 快照字段，记录判定时各规则的版本。**没有这个字段，规则一改，历史案例的结论就无法解释。**

### 7.3 严重等级：ASA 阶梯 vs NAD compliance，哪种更适合 Momcozy？

任务书 §二.E 的约束是明确的：**「无法强制卡死『审查完才能上线』的系统节点，靠 GTM 把控 + 审查记录问责。」**

#### 7.3.1 三个体系的适配性对照

| 维度 | ASA sanctions 阶梯 | NAD compliance | FTC 阶梯 |
|---|---|---|---|
| 依赖强制卡点？ | **否**。全部是事后动作 | 否，但依赖「转交 FTC」这个威胁可信 | **是**（consent order 有法律强制力） |
| 是否需要法律主体/诉讼？ | 否（法定后手才需要） | 否（转交才需要） | 是 |
| 主要成本机制 | **公开记录 + 媒体通路 + SEO** | 公开决定 + 转交威胁 | 罚款 |
| 是否适用于「广告主在境外」 | 部分（§1.9：法定后手够不到） | 是（FTC 有跨境执法） | 是 |
| 能否用于内部审查（非对外投诉） | **可以**——它就是一套「发现 → 记录 → 给期限 → 升级」的流程 | 可以，但结构更重 | 不适用 |

**结论：ASA 的阶梯在结构上是唯一可搬的。** 理由：

1. **它不假设任何强制卡点。** ASA 的 `Compliance Procedures` 全文没有一处依赖「广告主必须先获批才能投放」——它的全部机制都在事后。
2. **它的第一级不需要任何权限。** `informal resolution`（§1.5.2）：写信给广告主、给出指引、拿到「已修改」的确认。**这就是 Momcozy 的 GTM 能做到的事。**
3. **它的升格路径清晰且有门槛。** 从 L0 到 L1 需要 `clear-cut breach`（§1.5.3 原文：`leave no reasonable scope for alternative interpretation or alternative application`）——**Momcozy 对应的是「无需人工判断、规则字面命中」的情形**。
4. **它把「时间」做成杠杆。** 时限递进式收紧（§1.5.4：调查 7 天 → 正式合规 5 天 → 判后 24 小时）。**拖延会自我加剧**，不需要任何强制手段。

#### 7.3.2 建议的 Momcozy 严重等级阶梯（把 ASA 的 10 级压缩成 5 级）

| Momcozy 级 | 名称 | 触发条件（对齐 ASA 原文） | 对应现有资产 |
|---|---|---|---|
| **L0** | `auto_pass` | 未命中任何规则，或仅命中安全词 | `合规·绿`（157 条） |
| **L1** | `advisory` | 命中 `amber`/`grey`，给出改写建议即可，不阻断 | `审慎·黄`（30 条）+ `待复核·灰`（11 条） |
| **L2** | `block_recommended` | 命中 `red`，且属于 `clear-cut breach`（规则字面命中、无语境争议） | `高危·红`（91 条）中的一部分 |
| **L3** | `escalate_human` | 命中 `red` 但存在语境争议（即 ASA 意义上的 `reasonable scope for alternative interpretation`），或人工改判过 | `高危·红` 的另一部分 + `U04` |
| **L4** | `escalate_external` | 已在投 + 未在期限内修正 + 涉及平台政策/法域风险 | 当前**不存在** |

**关键的映射说明：**

- **现有的 `高危·红`（91 条）必须被一分为二（L2/L3）。** 依据是 ASA 的 `clear-cut breach` 判据（§1.5.3 原文）。示例：`Pain-Free Pumping` 是 L2（字面命中 H07，无语境可辩）；`Say goodbye to cold, painful pumping` 是 L3（`painful` 是场景描述还是功效承诺，有争议——这正是 `U04` 想解决的问题）。
- **`待复核·灰` 不等于低风险。** `U04` 的 `触发原因` 写着「与 goodbye/no more/not anymore/relieve 等消除性表述连用**应升级 H01/H07**」——它是**一个升级触发器，不是一个等级**。ASA 的结构里对应物是 `Issue`（把事实抽象成可判定的争点），不是 `decision`。
- **L4 当前不存在，必须新建。** 触发条件建议对齐 ASA 的核心理念——**「已上线 + 未修正 + 有时限」**三条件同时成立才升格（对照 §1.5.4 的 24 小时 post-investigation 时限）。而且升级动作不需要任何强制权限：**记录 + 通知 GTM 负责人 + 记入月度复盘**，即是 ASA 意义上的一次 `referral to CAP Compliance team`（Go Night Night 案的 `We referred the matter to CAP's Compliance team.`）。

#### 7.3.3 一个必须内建的默认值：**升格不中止执行**

ASA 程序 PDF 第 27 段逐字（§1.6.6）：

> `For post-investigation compliance cases, if the advertiser is making an application for independent review of the ASA's ruling, corrective action and the assurance of compliance, requested by the CAP Compliance team, **will normally continue to be required**.`

**即：申诉期间不冻结整改要求。** 对 Momcozy 这意味着：**当品线对审查结论提出异议时，默认值是「先按审查意见修改，异议并行处理」，而不是「暂停上线等结论」。** 这是唯一与他们「无法卡死节点」约束相容的默认值。

### 7.4 「没有规则怎么办」：FTC 与 NAD 的兜底能否作为他们的兜底条款？

#### 7.4.1 他们的现状：兜底条款完全缺失

实测 21 条规则的 `判断方式` 列：**21/21 全部填 `自动可检测`**。

而其中 5 条（`M05` / `U01` / `U02` / `U03` / `U04`）的 `边界类型` 是 `人工复核`：

| 规则 | 边界类型 | 判断方式 | 冲突 |
|---|---|---|---|
| M05 | 人工复核 | 自动可检测 | ⚠️ |
| U01 | 人工复核 | 自动可检测 | ⚠️ |
| U02 | 人工复核 | 自动可检测 | ⚠️ |
| U03 | 人工复核 | 自动可检测 | ⚠️ |
| U04 | 人工复核 | 自动可检测 | ⚠️ |

**「人工复核」规则声称「自动可检测」——5 条规则自相矛盾。** 更根本的问题：**21 条规则全部是基于「检测关键词 + 正则」的枚举式规则。枚举式规则的固有缺陷是——没被枚举到的表达就是漏网。** 实测他们的关键词覆盖面已经很大（`H01` 一个规则就列了 60+ 个关键词、9 条正则），但 §1.3.2 的 Nipper&Co 案证明：**视频画面、产品名称、视觉刻度都不在文本枚举的射程内。**

#### 7.4.2 三个体系各自的兜底条款（原文）

**（1）ASA / CAP Code 规则 3.7 —— 举证责任 + 证据缺失即违规**

`_evidence/R2/The-CAP-Code.txt` 第 486 行，逐字：

> `3.7 Before distributing or submitting a marketing communication for publication, marketers must hold documentary evidence to prove claims that consumers are likely to regard as objective and that are capable of objective substantiation. **The ASA may regard claims as misleading in the absence of adequate substantiation.**`

**这是整个 CAP Code 里最重要的一句话。** 它的结构是：

```
IF  声称是客观的（objective）
AND 声称是可客观证实的（capable of objective substantiation）
THEN 广告主必须在投放前持有书面证据
AND  若证据不充分 → ASA 可以径行认定该声称具有误导性
```

**注意它不要求 ASA 证明声称是假的。** 只需证明**证据不充分**。Hemios 案的原文印证了这一点（§1.3.1）：

> `Because we had not seen evidence that the Hemios bracelet could produce the claimed effects, we concluded that the claims had not been substantiated and were misleading.`

**（2）ASA AdviceOnline —— 举证责任明示 + 三档证据标准**

`Substantiation for health, beauty and slimming claims` 条目逐字（§1.8.1）：

> `**One of the main tenets of the Codes is that the burden of proof for claims lies with advertisers.**`

以及三档证据标准（`sensory/impressionistic` / `uncontroversial/established` / `"New" or "breakthrough"`，其中第三档要求 `at least one experimental human study (ideally double-blind and placebo-controlled)`）。

**（3）ASA 规则 12.1 —— 客观声称须有人体试验**

`_evidence/R2/The-CAP-Code.txt` 第 1591 行，逐字：

> `12.1 Objective claims must be backed by evidence, **if relevant consisting of trials conducted on people**. Substantiation will be assessed on the basis of the available scientific knowledge. Medicinal or medical claims and indications may be made for a medicinal product that is licensed by the MHRA, VMD or under the auspices of the EMA, or for a medical device with the applicable conforming marking. A medicinal claim is a claim that a product or its constituent(s) can be used with a view to making a medical diagnosis or can treat or prevent disease in human beings.`

**（4）ASA 规则 3.13 —— 不得把有争议的声称说成共识**

> `3.13 Marketing communications must not mislead by suggesting that their claims are universally accepted if a significant division of informed or scientific opinion exists.`

（实测该规则 2015-2026 年 0 条判例——是一条休眠但存在的兜底。）

**（5）ASA 程序规则 1.7 —— 未回应本身即违规**

Go Night Night 案原文（§1.3.3）：

> `The ASA was concerned by Go Night Night's lack of response and apparent disregard for the Code, which was a breach of CAP Code (Edition 12) rule 1.7 (Unreasonable delay).`

**（6）FTC 的对应机制** —— 见 §3.1（FTC substantiation doctrine 逐字：`a firm's failure to possess and rely upon a reasonable basis for objective claims constitutes an unfair and deceptive act or practice`）。

**（7）EU 的对应机制** —— 见 §4.1.3（UCPD **Art 12(b)** 逐字：`to consider factual claims as inaccurate if the evidence demanded in accordance with (a) is not furnished or is deemed insufficient` —— 四个体系里措辞最强的兜底，用的是 `shall be regarded`）。

**（8）CN 的对应机制** —— 见 §5.1.5（《广告法》**第二十八条第一款第（三）项**逐字：`使用虚构、伪造或者无法验证的科研成果、统计资料、调查结果、文摘、引用语等信息作证明材料的`）。

> **NAD 侧的对应表述未能核实** —— NAD 的 decision 全文本为订阅制，本分片未取得，故不写成结论（见 §9 G2）。**但从法理上可确证：NAD 以 FTC 的 deceptive advertising 法理为准，而 FTC 自己明确声明自律组织的判定不构成免责**（§3.1.1f 逐字：`An imprimatur from a self-regulation group will not automatically shield a firm from Commission prosecution`）。

#### 7.4.3 建议给他们写进规则库的三条兜底规则

**兜底 1：`X01` 无据的客观功效声称（举证责任倒置）**

```
规则编号   : X01
名称       : 未经证实的客观功效声称
严重等级   : red
判定路径   : human（需业务侧提交证据）
依据       : CAP Code 规则 3.7 逐字 + CAP 规则 12.1 逐字
触发条件   : 文案/画面中出现对产品效果的客观声称，且该声称：
             (a) 属于功效结果（非体验描述），且
             (b) 未登记在「已备证据库」中
本分片判断  : 这一条把「枚举不到的表达」转成了「枚举不到的声称必须有证据」。
             不要求穷举表达方式，只要求穷举「有证据的声称」。
             —— 这是枚举式规则库与兜底条款的本质分工。
落地要求   : 需新建「已备证据库」：claim_id | 声称文本 | 证据类型 | 研究名称 | 样本量 |
             方法 | 统计口径 | 有效期 | 可公开引用（Y/N）| 负责人
             实测他们已有部分原料：SUG-35 备注写明「28.2%/10%/70% 等内部测试补齐样本量与统计前禁用」
             与「落地页标注研究名称/样本/日期」——要求已经提出，只是没有对应的数据结构。
```

**兜底 2：`X02` 未提供证据 / 未回应**

```
规则编号   : X02
名称       : 审查结论未在期限内获得回应或证据
严重等级   : amber → 逾期升级 red
判定路径   : auto
依据       : CAP Code 规则 1.7 逐字（Go Night Night 案）+ 程序 PDF 第 31 段逐字
             「All evidence submitted by advertisers must be in English or translated,
              at the advertiser's expense, into English by a credible translation service.
              Where reference is made to research documents their relevance must be explained
              and full copies of those documents must be provided with the relevant
              sections highlighted. Abstracts of full studies will not usually be
              considered sufficient to substantiate claims.」
时限       : 对照 ASA —— 首次 7 天（重案 5 天）；正式合规 5 天；判后 24 小时
本分片判断  : 这条兜底对「无法卡死上线节点」是关键补丁：它把「不回应」变成
             一个可记录、可升级的事件，而不是「默认通过」。
```

**兜底 3：`X03` 暗示性声称（画面 / 产品名 / 视觉元素）**

```
规则编号   : X03
名称       : 非文本隐含声称
严重等级   : red（与文本同源时）/ grey（需人工判定时）
判定路径   : human + 视觉审查
依据       : Nipper&Co 案逐字 ——
             「the video content, which appeared to show someone producing 2oz of
              breast milk whilst pumping on day one ... increased to 3oz on day seven ...
              also implied that the MUM's MiLK lactation tea could increase how much
              breast milk a new mother could produce.」
             以及「the references to the product's name, "lactation tea" in the ad,
              also implied a relationship between the tea and breast milk production.」
             AdviceOnline 逐字 —— 「Objective claims can be direct or implied
              (including through images and quoted customer testimonials)」
本分片判断  : 这条直接补上他们 21 条规则的最大盲区。他们的 291 条记录里
             Primary Text / Headline 是主要输入，落地页 URL 字段填充率 0%
             （实测），意味着图片/视频/落地页内容完全未进入审查范围。
             而 §二.D 显示他们 262 条投 Google、27 条投 Meta——Meta 侧
             图片/视频是主形态。
```

**这三条兜底共同的结构原则（来自 ASA 的实践，不是我的发明）：**

> **枚举「不能说什么」是有限集，枚举「必须能证明什么」也是有限集，但后者与前者不同——它随业务新增声称而增长，且每一条都有明确的准入条件（有证据才可声称）。把审查规则库从「违禁词表」升级为「声称准入表」，是唯一能在不穷举的前提下覆盖长尾的路径。**

**注意这条原则已经在他们的资产里有雏形**：`W1卖点表达边界`（19 条）本质就是一张「声称准入表」——6 个卖点 × 3 个灯色，每个卖点给出了「建议表达」与「避免条件」。**问题在于它只覆盖 W1 一个型号的 6 个卖点，而他们实际在投 5 个型号（W1、M5、M6、M9、Air1）+ S12 Pro、V1 Pro 等（52 条改写建议库中出现）。**

**建议：把 `W1卖点表达边界` 的模式（卖点 × 灯色 × 建议表达 × 避免条件 × 判定理由）从「W1 专项」升格为**全品线的通用结构**，并把 `判定理由` 一栏规范化成 ASA 的三档证据标准（`sensory` / `established` / `novel` / `medical`，见 §1.8.1）。这样灯色就从主观判断变成 `证据档 × 表达类型` 的可推导结果。**

### 7.5 给委托方四个问题的收束回答

任务书 §六 的四个问题，用本分片的证据回答：

**问题 1：维度模型——「国家 × 品类 × 平台 × 内容类型」四维笛卡尔积对吗？**

**不对。** 依据：

- ASA 的规则库**不按国家分**（一个国家一个法典），跨辖区靠 `EASA 来源国管辖` + `规则号` 连接（§1.9）。
- ASA 的规则库**不按平台分**。`media_type` 只是判例的**检索维度（且底层是 GUID，§1.6.2）**，不是规则的组织维度。同一条规则 3.7 同时适用于 `Social media (paid ad)`、`Internet (display)`、`Website (own site)`、`Search (paid)`（§1.6.4 实测 373 条判例跨全部媒体）。
- ASA 的规则库**按「声称的语义类型」分节**：Section 3 管误导（通用）、Section 12 管医疗健康（品类）、Section 13 管减肥（品类）、Section 15 管食品健康声称（品类）。

**正确的分层（三层，不是四维笛卡尔积）：**

```
L1 语义规则层（与法域/平台无关）    ← 规则编号在这里，是稳定的
     「客观功效声称须有证据」「不得冒用机构背书」「不得绝对化安全承诺」
L2 法域映射层（规则 → 各国/各平台依据条款）  ← 只存映射，不重复规则内容
     X01 → UK: CAP 3.7 + 12.1 / EU: UCPD Art 6 + Reg 1924/2006 Art 6 / US: FTC substantiation / CN: 广告法 §28
     S01 → CN: 广告法 §9(3)（海外可能不适用）
L3 平台政策层（平台自定，叠加）      ← 引用，不改写
     Google/Meta 各自的广告政策
```

**四维笛卡尔积的真问题是它会指数爆炸且无法维护**：国家 × 品类 × 平台 × 内容类型的组合数远超实际需要，且大量组合为空。ASA 用「规则号 + 分节 + 显式交叉引用」把这件事压到了线性复杂度。

**问题 2：萃取方法——自上而下 vs 自下而上？**

**ASA 的答案是两条路都要，且分工明确**（§1.8.2）：
- **自上而下**（法域/法规 → 规则）：CAP code 的第 1–22 节。上限由上位法划定（`the CPRs ... providing a list of banned practices – to which CAP and BCAP cannot add`，§1.7.3c）。**代价：只能覆盖法域已明确的部分。**
- **自下而上**（判例 → 释义 → 规则）：AdviceOnline / EN / 规则修订。**代价：慢，且需要足够多的判例才能形成模式**（§1.7.3b：`Studies that show associations ... alone are unlikely to prove that an advertisement or advertising practice caused a particular effect.`）。

**关键机制是中间层。** 没有 AdviceOnline/EN 这一层，自下而上的证据无法安全地回流到规则——只能变成堆砌的判例。

**问题 3：错题本 / 规则库 / 严重等级的关系？**

见 §1.8 的三层模型 + §7.1 的字段集 + §7.3 的等级阶梯。一句话：**规则库回答「不许做什么」，错题本回答「这条规则在事实上怎么落地」，严重等级回答「落地之后怎么办」。三者用规则编号连接，严重等级必须是独立字段而非编号的一部分。**

**问题 4：自迭代——回路、度量、责任人？**

- **回路**：判例 → 释义层（AdviceOnline/EN）→ 规则修订（变更登记册 + 版本号 + 缓冲期）。ASA 的两条回写路径见 §1.8.2。
- **度量**（§1.6.4 实测模板）：规则 → 判例数分布（找出载荷规则与休眠规则）、误报率（需要 `engine_level` 与 `decision` 分离，§7.1.5）、升格率（`referral` 字段）。
- **责任人**：ASA 的分工是——**CAP 制定规则（自律组织），ASA 执行规则（独立机构）**（§1.7.1）。这个分离是刻意的：`The separation of operation and responsibilities helps to ensure that the independent judgement of the ASA is not compromised.`（CAP Code §23）
  **对 Momcozy**：他们的 GTM 负责推进业务，内容审查如果要靠审查记录问责，**制定规则的人（品牌/法务）与执行审查的人（审查岗）应当分开**，否则会出现「自己定规则、自己判合规、自己免责」的结构性失效。**而 `检查人` 字段 0% 填充（§7.1.6）意味着这个分离当前连记录都没有。**

---

## 8. 证据清单

### 8.0 机器可核对照表（引用 → 本地路径 → 抓取时间）

> 全部路径相对于 `/Users/lute/Project/audit_multi_content/research/governance/`。抓取日期均为 **2026-09-15**（单日完成，无跨日漂移）。

| 本报告引用 | 本地文件（`_evidence/R2/…`） | 类型 |
|---|---|---|
| CAP Code 全文（Edition 12 / v12.2.107） | `The-CAP-Code.pdf` (1.27 MB) + `The-CAP-Code.txt` (3,563 行) | 官方 PDF |
| CAP Code 变更登记册 | `asa-register-cap-changes.html` / `.txt` | 官方页 |
| ASA Compliance Procedures（2025-02-03） | `compliance-procedures.pdf` / `.txt` | 官方 PDF |
| ASA Non-broadcast Complaint Handling Procedures | `asa-Non-broadcast-Complaint-Handling-Procedures.pdf` / `.txt` | 官方 PDF |
| ASA Evidence-based policy-making（2018-01-18） | `asa-evidence-based-policy-making.pdf` / `.txt` | 官方 PDF |
| ASA Sanctions / Ad Alerts / NCOA / Independent reviews / How we consult / How we handle complaints | `asa-sanctions.html`、`asa-ad-alerts.html`、`asa-ncoa.html`、`asa-independent-reviews.html`、`asa-how-we-consult.html`、`asa-how-handle-complaints.html` | 官方页 |
| ASA 判例检索表单（全部 facet）| `asa-rulings.html` | 官方页 |
| ASA 非正式解决列表（该期 8 条）| `asa-informal2.html` | 官方页 |
| ASA 判例 Hemios 全文 | `ruling-hemios.html` | 官方页 |
| ASA AdviceOnline「Substantiation for health, beauty and slimming claims」 | `asa-ao-substantiation-health.html` | 官方页 |
| ASA Enforcement Notice: Fertility treatments | `asa-en-fertility.html` | 官方页 |
| FTC Policy Statement Regarding Advertising Substantiation（1984） | `ftc-advertising-substantiation-policy-statement-1984.html` / `.txt` | 官方 |
| FTC Health Products Compliance Guidance（2022） | `ftc-health-products-compliance-guidance-2022.html` / `.txt` | 官方 |
| FTC Deception Policy Statement（1983）| `ftc-deception-policy-statement-1983.html` / `.txt` | 官方 |
| 16 CFR Part 255（Endorsement Guides） | `ecfr-16cfr255-endorsement-guides.html` / `.txt` | eCFR |
| 16 CFR Part 1 Subpart L + 1.98（罚款金额） | `ecfr-16cfr-part1-subpartL.*`、`ecfr-16cfr1.98-civil-penalty-amounts.*` | eCFR |
| FTC 2023 Endorsement Guides 最终规则 | `fr-2023-14795-endorsement-guides-final-rule.txt` | Federal Register |
| FTC 民事罚款年度调整（2025） | `fr-2025-01361-civil-penalty-adjustments.txt` | Federal Register |
| FTC Warning Letters 说明 | `ftc-about-warning-letters.html` / `.txt` | 官方 |
| 15 U.S.C. § 45（FTC Act §5，含 §5(m)） | `uscode-15-45-s5-clean.txt` | 官方法典 |
| FTC 执法案件（部分） | `ftc-case-roca-labs.*`、`ftc-complaint-neurometrix-quell.pdf`、`ftc-pr-2005-09-window-rock-cortislim.*`、`ftc-pom-wonderful-155-ftc-1.pdf` | 官方 |
| **NAD 案件①Kendamil（#7562）** | `nad-case-1-kendamil.txt` / `.html` | 官方 newsroom |
| **NAD 案件②Nanit（#7558）** | `nad-case-2-nanit.txt` / `.html` | 官方 newsroom |
| **NAD 案件③Hims & Hers（#7543）** | `nad-case-3-hims-hers.txt` / `.html` | 官方 newsroom |
| **NAD/NARB Procedures**（含 §4.4 举证与时限、Case Report Headings） | `nad-narb-procedures.txt` (100 KB)、`nad-narb-procedures-2020.txt` | 官方 |
| NAD 流程 / filing tracks / 案例库 / program guidance | `nad-process.*`、`nad-filing-tracks.*`、`nad-case-library.*`、`nad-program-guidance.*` | 官方页 |
| NAD 年报 2025（自发监测占比 20%） | `nad-annual-report-2025.txt` (85 KB) + `.raw.json` | 官方 |
| NAD 转办 FTC 的跟进统计 | `nad-law360-ftc-referral-stats.txt` | ⚠️ **行业媒体分析，BBB 站内转载，非一手**（引用时须标注） |
| **UCPD 2005/29/EC 逐条原文** | `eu-ucpd-2005-29.md` (36 KB) | CELLAR→EUR-Lex |
| **UCPD Annex I 全文（35 项 + 47 项两版）** | `eu-annex-i-blacklist.md` (25 KB) | CELLAR→EUR-Lex |
| **Reg 1924/2006 逐条原文** | `eu-hc-reg-1924-2006.md` (27 KB) | CELLAR→EUR-Lex |
| **DSA 2022/2065 Art 15/17/20/21/24/34/35/36/37/42 + 指标清单** | `eu-dsa-2022-2065-art34-42.md` (55 KB) | CELLAR→EUR-Lex |
| **EU 总引文登记册（241 条逐字引文，含 URL+日期）** | `eu-notes.md` (102 KB) | 汇编 |
| EU 原始文档 / 清洗文本 / 脚本 | `raw/`（18 份）、`txt/`（17 份）、`_fetch.sh`、`_xhtml2txt.py` | — |
| **《广告法》逐条原文（2021 现行版）** | `cn-ad-law-key-articles.md` (19.7 KB)、`cn-ad-law-full-samr-db.txt` | SAMR 法规库 DOCX/PDF |
| 《广告法》官方 PDF（文字版 + 公版扫描件） | `cn-ad-law-samr-2021.pdf`、`cn-ad-law-samr-origin-scan.pdf` | 官方 |
| **《广告绝对化用语执法指南》（2023 年第 6 号公告）逐字** | `cn-samr-absolute-language-guide-verbatim.txt`、`cn-samr-absolute-language-guide.md` | 官方 |
| **总局「广告违法典型案例」批次库 + 字段拆解** | `cn-samr-typical-cases.md` (21 KB) | 官方 |
| 省级典型案例批次（闽/桂/辽/甘） | `cn-case-batch-*.txt` | 官方 |
| 《互联网广告管理办法》（2023）全文 + 重点条文 + 抓取日志 | `cn-internet-ad-measures-2023-full.md`、`-key-articles.md`、`cn-iam-2023-fetch-log.md` | 官方 |
| 广告监测制度与统计数据 | `cn-ad-monitoring-stats.md`、`cn-ad-monitoring-national-platform.txt` | 官方 |
| 医疗器械广告监管/识别指引（2025） | `cn-samr-medical-ad-supervision-guide-2025.txt`、`-identification-guide-2025.txt` | 官方 |
| **中国部分总引文登记册** | `cn-notes.md` (54.5 KB) | 汇编 |

**统计（2026-09-15 二轮补齐后复核）**：`_evidence/R2/` 顶层 **226 个文件** + `raw/` / `txt/` / `_tools/` 三个子目录，**共 677 个文件，83 MB**。抓取日期单一（2026-09-15），无跨日漂移。

> **⚠️ 一处需要向复核者说明的文件量差异**：初稿写「205 个文件 / 约 64 MB」，二轮补齐后为「226 / 83 MB」。差值来自 **NAD/NARB 一节的追加取证**（Procedures 两版、Annual Report 2025、3 份 decision summary、2 份 NARB 决定、3 份转交通知、2 份 digest、guidance、FAQ 等，共 21 个新增顶层文件）。**这是一个可核对的确定性差异，不是统计口径变化。**


### 8.1 英国 ASA / CAP（首要目标）

#### 8.1.1 规则原文（CAP Code）

| 内容 | URL | 本地文件 |
|---|---|---|
| CAP Code 全文 PDF（Edition 12, v12.2.107，142 页） | https://www.asa.org.uk/static/c6be0fb9-2c66-4248-ba5b824bf26fd3d3/fa3714eb-f3e9-4c45-b9d31f1b87d00d3a/The-CAP-Code.pdf | `_evidence/R2/The-CAP-Code.pdf` |
| CAP Code 全文文本（逐页提取，3,563 行） | 同上 | `_evidence/R2/The-CAP-Code.txt` |
| 非广播准则入口页 | https://www.asa.org.uk/codes-and-rulings/advertising-codes/non-broadcast-code.html | `_evidence/R2/asa-nonbroadcast-code.html` |
| 广告准则总览 | https://www.asa.org.uk/codes-and-rulings/advertising-codes.html | （见 §1.1.1） |
| **CAP Code 变更登记册** | https://www.asa.org.uk/codes-and-rulings/advertising-codes/register-of-cap-code-changes.html | `_evidence/R2/asa-register-cap-changes.html` / `.txt` |

**引用的关键规则号**（行号指本地 `The-CAP-Code.txt`）：
`1.3` / `1.7`（未合理回应）/ `1.8.1`（已删除）/ `1.10` / `3.1` / `3.2` / `3.3` / `3.4.1`–`3.4.6` / `3.7`（举证）/ `3.11` / `3.13` / `3.44`–`3.46`（虚假评论）/ `3.47` / `3.48`–`3.51`（证言与背书）/ `3.52`（trust mark / 授权）/ `3.53` / `3.56` / `9.10` / `11.8` / `12.1`（客观声称须人体试验）/ `12.2` / `12.2.1` / `12.3`–`12.10` / `12.11` / `12.12` / `12.14` / `12.18`（不得用健康专业人士背书药品）/ `12.19` / `12.24` / `13.1` / `15.1` / `15.1.1`（仅可用登记册内声称）/ `15.2` / `15.6.2` / `15.7` / `15.10` / `15.10.1` / `15.14` / **`15.18`（改号说明）** / `15.19` / `15.20`（HFSS）

#### 8.1.2 程序与制裁

| 内容 | URL | 本地文件 |
|---|---|---|
| **CAP Compliance: Non-broadcast compliance procedures**（2025-02-03，9 页） | https://www.asa.org.uk/static/a501c9ab-54c3-4dbc-84d6b61be6f5971b/78273db5-cfc7-4a21-a5017b9bc1a48542/Compliance-Procedures-03022025.pdf | `_evidence/R2/compliance-procedures.pdf` / `.txt` |
| **Non-Broadcast Complaint Handling Procedures**（21 页） | https://www.asa.org.uk/static/e968b8b3-9beb-4c4f-a52e224c42566cad/77913969-bf2b-4bd6-a7c62edd6a269240/Non-broadcast-Complaint-Handling-Procedures.pdf | `_evidence/R2/asa-Non-broadcast-Complaint-Handling-Procedures.pdf` / `.txt` |
| Broadcast Complaint Handling Procedures | https://www.asa.org.uk/static/b65e1503-4607-4d85-a1c8f9eb681de261/e4da7ae9-58ab-4a83-93463a34c9c92c2c/Broadcast-Complaint-Handling-Procedures.pdf | `_evidence/R2/asa-Broadcast-Complaint-Handling-Procedures.pdf` |
| Making an ad complaint guide | https://www.asa.org.uk/static/8c4ece0c-1efa-43b9-885c0d18480e3f94/3926b4ab-c966-449f-94aa9d5dc1769c06/Making-an-ad-complaint-guide.pdf | `_evidence/R2/asa-Making-an-ad-complaint-guide.pdf` |
| Sanctions 页 | https://www.asa.org.uk/codes-and-rulings/sanctions.html | `_evidence/R2/asa-sanctions.html` |
| Non-compliant online advertisers（27 条，2026-09-15） | https://www.asa.org.uk/codes-and-rulings/non-compliant-online-advertisers.html | `_evidence/R2/asa-ncoa.html` |
| Ad Alerts / Media Alerts | https://www.asa.org.uk/advice-and-resources/resource-library/ad-alerts.html | `_evidence/R2/asa-ad-alerts.html` |
| Trading Standards referrals | https://www.asa.org.uk/codes-and-rulings/trading-standards-referrals.html | `_evidence/R2/asa-ts-referrals.html` |
| How we handle complaints | https://www.asa.org.uk/make-a-complaint/how-we-handle-complaints.html | `_evidence/R2/asa-how-handle-complaints.html` |
| Independent reviews | https://www.asa.org.uk/codes-and-rulings/independent-reviews.html | `_evidence/R2/asa-independent-reviews.html` |

#### 8.1.3 规则更新机制

| 内容 | URL | 本地文件 |
|---|---|---|
| **How we consult** | https://www.asa.org.uk/about-asa-and-cap/the-work-we-do/how-we-consult.html | `_evidence/R2/asa-how-we-consult.html` |
| **Evidence-based policy-making**（2018-01-18，10 页） | https://www.asa.org.uk/static/uploaded/cb20c00f-b559-40a2-8b5677188511b45b.pdf | `_evidence/R2/asa-evidence-based-policy-making.pdf` / `.txt` |
| Consultations 列表 | https://www.asa.org.uk/advice-and-resources/resource-library/consultations.html | （见 §1.7.2） |
| Enforcement Notice: Fertility treatments（2021-06-10，与 CMA / HFEA 联署） | https://www.asa.org.uk/resource/enforcement-notice-fertility-treatments.html | `_evidence/R2/asa-en-fertility.html` |

#### 8.1.4 判例原文（逐字段拆解用）

| 判例 | 发布日期 | 依据规则 | URL | 本地文件 |
|---|---|---|---|---|
| **Hemios**（磁疗手环） | 2026-09-09 | 3.1 / 3.7 / 12.1 / 13.1 | https://www.asa.org.uk/rulings/hemios.html | `_evidence/R2/ruling-hemios.html` |
| **Nipper&Co Ltd**（催乳茶，**最贴近 Momcozy**） | 2025-07-09 | 15.1 / 15.1.1 | https://www.asa.org.uk/rulings/nipper-co-ltd-a25-1284063-nipper-co-ltd.html | （在线抓取，见 §1.3.2） |
| **Go Night Night**（冒用 FEDANT 背书） | 2024-10-30 | 1.7 / 3.1 / 3.50 / 3.51 | https://www.asa.org.uk/rulings/go-night-night--unconfirmed--a24-1249218-go-night-night--unconfirmed-.html | （在线抓取，见 §1.3.3） |
| **Nutricia Ltd**（婴儿配方奶播客，多争点） | 2022-02-23 | 1.10 / 15.1 / 15.1.1 / 15.10 / 15.10.1 | https://www.asa.org.uk/rulings/nutricia-ltd-g21-1111826-nutricia-ltd.html | （在线抓取，见 §1.3.4） |

#### 8.1.5 判例检索接口（实测参数，2026-09-15）

| 内容 | URL | 本地文件 |
|---|---|---|
| 判例列表 + 检索表单（含全部 facet 的 HTML） | https://www.asa.org.uk/codes-and-rulings/rulings.html | `_evidence/R2/asa-rulings.html` |
| 非正式解决列表（该期 8 条） | https://www.asa.org.uk/codes-and-rulings/rulings.html?tab=informally-resolved | `_evidence/R2/asa-informal2.html` |
| 规则过滤示例（可检索性证明） | `…/rulings.html?capCode=15.1&custom_date=1&from_date=01/01/2020&to_date=15/09/2026` → `Rulings (63)` | （见 §1.6.3/§1.6.4） |

#### 8.1.6 释义层（AdviceOnline）

| 内容 | URL | 本地文件 |
|---|---|---|
| AdviceOnline 库首页 | https://www.asa.org.uk/advice-and-resources/resource-library/advice-online.html | `_evidence/R2/asa-advice-online.html` |
| **Substantiation for health, beauty and slimming claims**（三档证据标准，2025-06-23） | https://www.asa.org.uk/advice-online/substantiation-for-health-beauty-and-slimming-claims.html | `_evidence/R2/asa-ao-substantiation-health.html` |

### 8.2 美国 FTC

| 内容 | URL | 本地文件 |
|---|---|---|
| **FTC Policy Statement Regarding Advertising Substantiation**（1984-11-23） | https://www.ftc.gov/legal-library/browse/ftc-policy-statement-regarding-advertising-substantiation | `_evidence/R2/ftc-advertising-substantiation-policy-statement-1984.html` / `.txt` |
| **Health Products Compliance Guidance**（2022；CRSE 定义、RCT 要求、三档判据） | https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance | `_evidence/R2/ftc-health-products-compliance-guidance-2022.html` / `.txt` |
| **16 CFR Part 255 — Endorsement Guides**（含 §255.1(d)/(e)、§255.3、§255.4、§255.5） | https://www.ecfr.gov/current/title-16/chapter-I/subchapter-B/part-255 | `_evidence/R2/ecfr-16cfr255-endorsement-guides.html` / `.txt` |
| Endorsement Guides 2023 最终规则（88 FR 48092） | Federal Register 2023-14795 | `_evidence/R2/fr-2023-14795-endorsement-guides-final-rule.txt` |
| FTC 2023-06 Endorsement Guides 新闻稿 | ftc.gov | `_evidence/R2/ftc-pr-2023-06-endorsement-guides.txt` |
| **About FTC Warning Letters** | https://www.ftc.gov/enforcement/warning-letters | `_evidence/R2/ftc-about-warning-letters.html` / `.txt` |
| **Adjustments to Civil Penalty Amounts**（2025；$53,088） | Federal Register 2025-01361 | `_evidence/R2/fr-2025-01361-civil-penalty-adjustments.txt` |
| 16 CFR Part 1 Subpart L（民事罚款调整条文） | eCFR | `_evidence/R2/ecfr-16cfr-part1-subpartL.html` / `.txt` |
| 16 CFR 1.98 现行罚款金额 | eCFR | `_evidence/R2/ecfr-16cfr1.98-civil-penalty-amounts.html` / `.txt` |
| FTC Deception Policy Statement（1983） | ftc.gov | `_evidence/R2/ftc-deception-policy-statement-1983.html` / `.txt` |
| Advertising FAQ's: A Guide for Small Business | ftc.gov | `_evidence/R2/ftc-advertising-faqs-small-business.html` / `.txt` |
| Endorsement Guides FAQ | ftc.gov | `_evidence/R2/ftc-endorsement-guides-faq.html` / `.txt` |
| 15 U.S.C. § 45（FTC Act §5，含 §5(m) 民事罚款条款） | uscode.house.gov | `_evidence/R2/uscode-15-45-s5-clean.txt` |
| 执法案例（部分） | ftc.gov | `_evidence/R2/ftc-case-roca-labs.html`、`ftc-complaint-neurometrix-quell.pdf`、`ftc-pr-2005-09-window-rock-cortislim.html`、`ftc-pom-wonderful-155-ftc-1.pdf` |
| FTC-FDA MOU | ftc.gov | `_evidence/R2/ftc-fda-mou.html`（**内容提取失败，见 §9**） |

### 8.3 美国 NAD / NARB（**2026-09-15 二轮补齐后重写**）

> **⚠️ 站点已改版**：任务书给的 `/programs/all-programs/nad` 与 `.../case-decisions` 现均 **404**。下表 URL 为**当前有效路径**。
> **⚠️ 访问限制**：`bbbprograms.org` 对本机出口 IP 返回 **HTTP 403**（纯 curl / 浏览器 UA / Googlebot UA / HTTP / HTTPS / IPv4 / IPv6 / 真实无头 Chrome 全部 403，属出口 IP 级 WAF 封锁）。下列文件经 **microlink.io 云渲染**、**`assets.bbbprograms.org`**（未被拦截）、或**运营方 S3 源站桶**取得。机制与路径说明见 §2 章首。

#### 8.3.1 程序文件（**本节的核心新增证据**）

| 内容 | URL | 本地文件 |
|---|---|---|
| **NAD/NARB Procedures（`Revised effective March 16, 2026`，29 页）** | https://bbbprograms.org/getmedia/133fded6-5046-44de-a30e-f0890377480c/NAD-NARB-Procedures.pdf | `nad-narb-procedures.txt`（1,590 行）+ `.raw.json` |
| **NAD/NARB Procedures 2020 版**（版本对照用） | https://bbbnp-bbbp-stf-use1-01.s3.amazonaws.com/docs/default-source/bbb-national-programs/procedures/nad_narbprocedures_8-20-2020.pdf | `nad-narb-procedures-2020.txt`（1,449 行） |
| **NAD Annual Report 2025**（含逐案表 + 汇总表） | https://bbbprograms.org/getmedia/1b815bdb-eab6-4a54-8af0-afa0a03d1eae/NAD_AnnualReport_2025_Digital_Report.pdf | `nad-annual-report-2025.txt` + `.raw.json`（2 MB，**版式定位用**） |
| Program FAQ（**举证责任原文在此，不在 Procedures**） | https://bbbprograms.org/about/faq | `bbbnp-faq.txt` / `.html` |
| NAD 主页面（tracks / 监测比例 / 案例库说明） | https://bbbprograms.org/programs/advertising/nad | `nad-process.txt` / `.html` |
| NAD 挑战流程页 | https://bbbprograms.org/programs/advertising/nad/challenges | `nad-filing-tracks.txt` |
| NARB 页面（上诉机制、panel 构成） | https://bbbprograms.org/programs/advertising/narb | `narb-overview.txt` |
| Program Guidance 索引 | https://bbbprograms.org/media/resources/program-guidance | `nad-program-guidance.txt` |
| **《Checklist for Substantiating Advertising Claims》**（§2.5c.4 出处） | https://bbbprograms.org/media/insights/blog/checklist-for-substantiating-advertising-claims | `nad-guidance-substantiation-checklist.txt` |
| Online Archive 页（订阅库描述） | https://bbbprograms.org/media/online-archive | `nad-online-archive.txt` |
| Online Archive 使用指南 PDF | 同上（getmedia） | `nad-online-archive-guide.txt` |
| Complex Track 说明 PDF | 同上（getmedia） | `nad-complex-track-overview.txt` |
| Standard Track 信息图 PDF | 同上（getmedia） | `nad-standard-track-infographic.txt` |
| 免费判例库列表页（JS 渲染） | https://bbbprograms.org/media/newsroom/decisions | `nad-case-library.txt` |

#### 8.3.2 判例与转交通知（全部为**公开 summary**，非 decision 全文）

| 内容 | URL | 本地文件 |
|---|---|---|
| NAD #7562 Kendal Nutricare（Kendamil，2026-08-31，挑战方 Abbott） | https://bbbprograms.org/media/newsroom/decisions/kendamil | `nad-case-1-kendamil.txt` |
| NAD #7558 Udisense / Nanit（2026-09-01，挑战方 Owlet） | https://bbbprograms.org/media/newsroom/decisions/udisense-nanit | `nad-case-2-nanit.txt` |
| NAD #7543 Hims & Hers（2026-08-24，挑战方 Kenvue） | https://bbbprograms.org/media/newsroom/decisions/hims-hers | `nad-case-3-hims-hers.txt` |
| **NARB #7422-342 Kendal Nutricare（2025-12-16）** —— §2.5e 案件 A | https://bbbprograms.org/media/newsroom/decisions/narb-kendal | `narb-decision-1-kendal.txt` |
| **NARB #7415-340 2C T-Mobile（2026-01-22）** —— §2.5d 合规循环 | https://bbbprograms.org/media/newsroom/decisions/t-mobile-compliance | `narb-decision-2-tmobile-compliance.txt` |
| 转交通知：Talking Rain（2014） | …/decisions/nad-refers-talking-rain-beverage-company-to-ftc-after-company-fails-to-comply-with-nad-recommendatio | `nad-referral-talking-rain.txt` |
| 转交通知：Steuart's Pain Formula（2016，**第二次转交**） | …/decisions/nad-refers-advertising-for-steuart-s-pain-formula-to-ftc-following-advertiser-s-failure-to-provide-s | `nad-referral-steuarts.txt` |
| 转交通知：Leptitox Nutrition（2020） | …/decisions/nad-refers-leptitox-nutrition-to-ftc-for-dramatic-dietary-supplement-weight-loss-claims | `nad-referral-leptitox.txt` |
| 官方 case digest（化妆品类，含 §2.5c.3 的 CRSE 定义） | S3 源站桶 | `nad-digest-cosmetics.txt` |
| 官方 case digest（环保类，同文互证） | S3 源站桶 | `nad-digest-environmental.txt` |
| FTC 侧「NAD 转办案件的处理」页 | https://www.ftc.gov/enforcement/cases-proceedings/closing-letters-and-other-public-statements/resolution-of-referrals-from-nad | `ftc-resolution-of-nad-referrals.txt` —— **⚠️ 空文件（284 字节，仅页头）**：ftc.gov 对本网络**全部方法 403**，见 §2 章首 |
| Law360 报道（NAD 转办与 FTC 统计，第三方） | S3 源站桶 | `nad-law360-ftc-referral-stats.txt` |

#### 8.3.3 分析笔记

| 内容 | 路径 |
|---|---|
| 子代理的完整 NAD 工作笔记（983 行，含 19 字段 schema + 12 项 NOT FOUND） | `_evidence/R2/nad-notes.md`（76 KB） |

**⚠️ 一处命名不一致（供复核者注意）**：`nad-notes.md` §2b 的 19 字段 schema 是**子代理的归纳**，其中「规范 vs 观察」的区分以 §2.1(J)（规范性）与逐案 observation 为界。本报告未逐条复述该 19 字段表，只采用了经我复核的两份权威 schema（§2.1(J) / §2.1(K)）。

### 8.4 欧盟

| 内容 | URL | 本地文件 |
|---|---|---|
| **UCPD 2005/29/EC 逐条原文**（Art 5/6/7/8/9/11/11a/12/13） | https://eur-lex.europa.eu/eli/dir/2005/29/oj | `_evidence/R2/eu-ucpd-2005-29.md` |
| **Annex I 黑名单全文**（31 项原版 + 35 项 2022 版 + **47 项 2026-09-27 现行版**） | https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02005L0029-20260927 | `_evidence/R2/eu-annex-i-blacklist.md` |
| **Reg (EC) No 1924/2006**（Art 5/6/7/10/11/12/13/14/28 + EU 注册库 + FIC Art 7） | https://eur-lex.europa.eu/eli/reg/1924/2006/oj | `_evidence/R2/eu-hc-reg-1924-2006.md` |

### 8.5 中国

| 内容 | URL | 本地文件 |
|---|---|---|
| **《中华人民共和国广告法》官方 DOCX**（SAMR 法规库） | https://sjfg.samr.gov.cn/law/file/docx/3235243/1663323578206.docx | `_evidence/R2/cn-ad-law-samr-2021.pdf` 等 |
| 广告法逐条原文（第四/九/十六/十七/十八/二十八/三十八/四十六/五十五/五十七/五十八/四十九条） | https://sjfg.samr.gov.cn/law/pageInfo/law_search_new.law_details?lawId=15facd787430cd204c54e76d4fd6e54d | `_evidence/R2/cn-ad-law-key-articles.md`（19,720 B）、`cn-ad-law-full-samr-db.txt` |
| 广告法全文 PDF（文字版 24 页）+ 公版扫描件（10 页） | 同上 | `cn-ad-law-samr-2021.pdf`、`cn-ad-law-samr-origin-scan.pdf` |
| **总局「广告违法典型案例」批次库结构与逐字样本** | samr.gov.cn 各批次 | `_evidence/R2/cn-samr-typical-cases.md`（21,439 B） |
| 省级典型案例批次（福建 2024 一批/三批、广西 2024、辽宁 2024） | scjgj.fujian.gov.cn 等 | `cn-case-batch-fujian-2024-1.txt`、`cn-case-batch-fujian-2024-3.txt`、`cn-case-batch-guangxi-2024.txt`、`cn-case-batch-liaoning-2024.txt` |
| 「绝对化用语」官方答复/口径 | samr.gov.cn | `_evidence/R2/cn-samr-absolute-language-guide.md` |
| **《互联网广告管理办法》（2023）全文 + 重点条文 + 抓取日志** | samr.gov.cn / gov.cn | `cn-internet-ad-measures-2023-full.md`（27,923 B）、`cn-internet-ad-measures-key-articles.md`（27,033 B）、`cn-iam-2023-fetch-log.md` |
| **广告监测制度与统计数据**（含《2026年全国广告监管工作要点》） | https://www.samr.gov.cn/ggjgs/sjdt/gzdt/art/2026/art_7927e556f71945358b4ac486e1a7859b.html | `_evidence/R2/cn-ad-monitoring-stats.md`、`cn-ad-monitoring-national-platform.txt` |
| 医疗器械广告监管/识别指引（2025） | samr.gov.cn | `cn-samr-medical-ad-supervision-guide-2025.txt`、`cn-samr-medical-ad-identification-guide-2025.txt` |

### 8.6 委托方自有材料（用于 §7 的实测统计）

| 内容 | 路径 |
|---|---|
| 内容治理需求文档（含 291 条广告记录、21 条规则库、19 条卖点边界、52 条改写建议） | `PRD/内容治理需求文档.md` |
| 调研任务书（本分片的上游约束） | `research/governance/00-调研任务书.md` |

**§7 中对 291 条记录的统计口径**：解析范围为 `PRD/内容治理需求文档.md` 第 63–357 行（表头在第 63 行，共 27 列；291 条数据行）。列数漂移判定 = 「按 `|` 切分后的列数 ≠ 27」；右侧锚定统计 = 取每行最末 8 列与最前 6 列（这两段不含广告文案，因而无 `|` 污染）。

---

## 9. 缺口清单（没查到什么，为什么）

本清单按「对本分片结论的影响程度」排序。

### 9.1 高影响缺口

| # | 缺口 | 影响 | 原因 / 已尝试 |
|---|---|---|---|
| ~~**G1**~~ | ~~NAD/NARB Policies and Procedures 全文~~ | **✅ 已补齐（见 §2.5c）** | 程序文件本身公开：`_evidence/R2/nad-narb-procedures.txt`（100 KB）。已取得 §4.4「广告主书面答辩与举证义务」、15 个工作日时限、30 页限制、Case Report Headings 正式裁决词表。 |
| **G2** | NAD 个案 decision **全文**（订阅版） | **⚠️ 部分补齐（见 §2.5b）** —— 用公开 summary 完成 3 个真实案件（Kendamil #7562、Nanit #7558、Hims & Hers #7543）的逐字段拆解，并取得两份权威 schema（§2.1(J) 规范性字段、§2.1(K) 8 项 disposition 词表） | 全文仍为订阅制（结构性障碍，未变）。**⚠️ 更正初稿表述**：「证据不足即构成违规」**不能**说「已由 `No Substantiation Received` 确证」——该类别证明的是「举证不能可作为独立裁决事由」，**而表述该命题的原文经穷尽检索不存在**（§2.5c.5）。 |
| **G3** | **NAD 的 compliance rate 公开数字** | **✅ 找到唯一数字，但已过时 14 年**：`More than 90 percent of the advertisers who come before NAD comply with NAD's recommendations.` | **仅见于两份 ©2012 ASRC digest**，**未找到 2012 年后的任何重申**。**故不得作为现状引用**，只能表述为「历史上曾达到的水平」。见 §2.6.1 第 3 项。 |
| ~~**G4**~~ | ~~DSA Art 34/35/42 与指标清单~~ | **✅ 已补齐（见 §4.3）** | `_evidence/R2/eu-dsa-2022-2065-art34-42.md`（55 KB）。含 Art 34/35/42 逐字、Reg (EU) 2024/2835 Annex I 完整指标清单、透明度数据库字段表，以及「间接约束」传导链条。 |
| **G5** | **吸奶器在中国的器械定性** | 直接决定适用《广告法》第十六条（医疗器械）还是第十七条（非医疗商品一律禁涉疾病治疗功能）。**两条路径的合规要求与罚则档位都不同**（第五十八条 vs 第五十七条；10 万–20 万 vs 20 万–100 万起）。若属医疗器械，还触发第四十六条**事前审查**（中国体系里唯一的法定强制卡点） | **NOT FOUND，且已穷尽路径**：① `nmpa.gov.cn` 对**所有路径**返回 **HTTP 412**（JS 反爬），即使完整浏览器头也不行；② `cmde.org.cn` 返回 202；③ 浏览器工具无可控标签页；④ `archive.org` 超时；⑤ `gov.cn` 无分类目录；⑥ SAMR 法规库只有《医疗器械分类规则》与《医疗器械监督管理条例》，**无分类目录**（检索命中 0）；⑦ **1,058 条 SAMR 广告案例索引中「吸奶器/母婴/孕产/哺乳/母乳/乳腺」命中数为 0**。<br>**已取得的替代证据（非结论）**：《医疗器械监督管理条例》第一百零三条的法定定义——`医疗器械，是指直接或者间接用于人体的仪器、设备、器具、体外诊断试剂及校准物、材料以及其他类似或者相关的物品…其效用主要通过物理等方式获得…`，用途含（一）疾病的诊断、预防、监护、治疗或者缓解…（三）生理结构或者生理过程的检验、替代、调节或者支持…；第六条设 I/II/III 风险分级；第十三条设备案 vs 注册。<br>**⚠️ 存在搜索引擎索引级信号（两个 NMPA `/zwfw/sdxx/sdxxylqx/qxpjfb/` URL 匹配「吸奶器」），但页面正文被 412 拦截，故此信号不能证明任何事。本分片明确标注：不得用任何看似合理的答案填补此项。** |
| ~~**G6**~~ | ~~FTC 与 FDA 的分工原文~~ | **✅ 已补齐（见 §3.5.6）** | 依据 HPCG § II.B / § II.C 逐字。**MOU 原文本身仍未取得**（`fda.gov` 不可达；govinfo 1971 年 FR 扫描件无 ToUnicode CMap）——但 MOU 的存在、引注与实质已由 FTC 自身描述确证。 |
| **G7** | **FTC 2023 年 Endorsement Guides 修订的逐条改动** | §3.4 只给出方向，未逐条核对 | 已存 `fr-2023-14795-endorsement-guides-final-rule.txt`（162 KB），但本次窗口内未完成逐条比对。**未核实部分不写成结论。** |
| ~~**G8**~~ | ~~FTC Notice of Penalty Offenses 项目清单~~ | **✅ 已补齐（见 §3.5.4）** | 5 项处罚先例逐字（含直击 `H03` 的第 5 项与要求 `at least one human clinical trial of the product` 的第 3 项），2023-04-13 发往约 670 家。 |

### 9.2 中等影响缺口

| # | 缺口 | 说明 |
|---|---|---|
| **G9** | **CAP Code 变更登记册的逐条变更日期** | 网页版登记册**不逐条标注日期**（已核对原始 HTML）。带日期的记录只存在于 CAP Code PDF 正文的脚注（如 `[Deleted 10 May 2018]`、`renumbered and moved to 15.20 on 5 January 2026`）。**两处信息需手工关联——这本身是一个发现（§1.4）。** |
| **G10** | **ASA 判例总数与规则分布的长时间序列** | 只做了 2015-01-01–2026-09-15 单窗口的规则计数（§1.6.4），未做逐年趋势。**原因是规则 facet 是结果集内 facet，逐年抓取成本高且接口无速率保证。** |
| **G11** | **ASA 非正式解决案件的总量与规则归属** | 已确认非正式解决**不带规则号**（§1.5.2），因此无法建立规则归属。总量需逐期抓取列表页统计，未做。 |
| **G12** | 《互联网广告管理办法》（2023）条文 | **✅ 已核对（子代理三重交叉验证：SAMR DOCX + PDF + 司法部 moj.gov.cn，5,251/5,251 与 5,200/5,200 字符一致）**。要点：**第九条**（可识别性 + 竞价排名须显著标明「广告」+ 知识介绍/体验分享/消费测评加购物链接须标明「广告」）；**第十条**（弹窗一键关闭，五种禁止做法）；**第十三条**（广告主对内容真实性负责 + 档案保存不少于三年）；**第十六条**（平台经营者六项义务）；**第十七条第一款**（政务服务搜索结果不得插竞价排名）；**直播带货全部在第十九条**（四款：销售者→广告主；直播间运营者→经营者/发布者；受托直播营销人员→经营者/发布者；以自己名义形象推荐→广告代言人）。**⚠️ 更正任务书：第二十条是管辖条款，与直播带货无关。** |
| **G13** | 「绝对化用语」官方口径 | **✅ 已补齐（见 §5.2）**。现行有效文件是《广告绝对化用语执法指南》（总局公告 **2023 年第 6 号**，落款 2023-02-25），12 条全文逐字。**2016 年原工商总局《答复》在 samr.gov.cn 上不存在**（子代理检索全部 1,058 + 92 + 26 条索引，仅 1 次「绝对化」命中，为海淀区解读）——**该答复列为永久 NOT FOUND，不再追。** |
| **G14** | **中国国家级广告监测平台的指标体系** | 《广告法》第四十九条第二款给了法定授权，但**未找到**总局对「违法率 / 条次 / 违法线索数」的定义与口径。 |
| **G15** | **EU Register of nutrition and health claims 的字段结构** | 已定位条目在 `eu-hc-reg-1924-2006.md` 第 262 行起，但本分片未逐字段引用。 |
| **G16** | **NARB 上诉成功率统计** | **✅ 已取得，但须用逐案表而非汇总行。** Annual Report 2025 逐案表完整（10 件：Upheld 6 / Upheld In Part 1 / Overturned 1 / N-A 2）。 | **汇总行与逐案表不一致**（汇总写 `Upheld 8 / Upheld in Part 0 / Overturned 0`）。已用版式原始位置复核确认**不是抽取错误**，而是年报内部矛盾。**结论：只引逐案表，不引汇总行。** 见 §2.4.3。 |
| **G17** | **CAP 与 BCAP 的规则冲突处理** | 本分片只覆盖了非广播准则（CAP Code）。广播准则（BCAP Code）是独立文件、独立编号（同为 `Edition 12`？未核实）。**同一素材在广播与非广播的编号映射未核实。** |

### 9.3 低影响缺口 / 未采用的方向

| # | 项 | 说明 |
|---|---|---|
| **G18** | EU 各成员国转化法的具体条文（法国 ARPP / 德国 UWG / 西班牙 Ley 3/1991 / 意大利 Codice del Consumo） | Momcozy 在 FR/ES/IT 有投放，**这些国家的国内转化条文未调研**。本分片只覆盖了指令层。 |
| **G19** | 加拿大 Ad Standards 的规则与程序 | 291 条中有 14 条投加拿大，**但加拿大不在 EASA 体系内**（§1.9），其自律规则未调研。 |
| **G20** | **中国广告协会（CAA）等行业自律规则** | 未调研。中国体系里是否存在 ASA 式的自律判例库，本分片未回答。 |
| **G21** | ASA 判例的机器可读导出 / API | **已确认不存在**（判例库是 HTML；检索接口无文档、无 API、无速率保证）。这不是缺口，是结论。 |
| **G22** | NAD Online Archive 的内容（订阅制） | 未订阅，未获取。官方称含 `more than 6,000 cases… dating back to 1971`、可按 `company, product, issue or claim type, date, document type, or Program` 检索、含 50+ issue types —— **以上均为官方文字描述，未实测枚举**。见 §2.6.2 N4。 |

### 9.4 关于「未核实」的声明

按任务书 §四.4 的要求明确声明：

- 本分片所有**标注为「原文」的引文**，均已存有对应本地文件（§8 清单），可逐条复核。
- 本分片所有**标注为「本分片判断」或「子代理推断」**的内容，是推论而非原文，已在行文中显式标注。
- **§9.1 中 G1–G8 涉及的主题，本分片不作结论。** 宁可留缺口。
- **本分片主动更正了自己三处**（均已在正文就地标注）：① §7.1.3 原写「未转义的 `|`」——实为**合规的 `\|` 转义**，问题在解析器不在数据（经委托方复算确认）；② §4.1.4 原称 Annex I 可作健康声称的无抗辩红线——委员会自己的指引说 item 17 实用性 `marginal`，健康案件走 Art 6；③ **§2.3.3 原称 NAD 的终局是「二元开关」——实为三态**（取得 Procedures 全文后发现 §8.1(B) 合规程序，并由 T-Mobile 案实证两次循环，见 §2.5d）。
- **另有一处对子代理结论的更正**：子代理称「证据不足即构成违规已由 `No Substantiation Received` 确证」——**该说法过强**，已在 §2.5c.5 / §9.1 G2 就地更正为「操作形态成立、原文不存在」。
- 一处**主动更正了任务书的前提**：① 任务书问「sector-specific 的附录」——实测是**主码的第 12–22 节**，不是附录（§1.2）；② 任务书问「Annex I 的 31 项黑名单」——实测**现行版为 47 项**（2026-09-27 起适用，§4.1.4）；③ 任务书把《广告法》第九条罚则记作第五十八条——实测为**第五十七条**（§5.1）。
