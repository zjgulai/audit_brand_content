# R6 — 跨境电商标杆企业的内容治理公开证据，以及广告业的内容分级标准

> 分片作者：R6。写作日期：2026-09-15。
> 所有 URL 抓取日期均为 **2026-09-15**（除个别标注）。原始证据存于 `research/governance/_evidence/R6/`。
> 遵循 `00-调研任务书.md`：一手来源优先；逐字引用 + URL；拿不到写「未核实」；附录列失败来源。

---

## 0. 结论先行（12 条）

**关于行业标准（第一、二问的行业答案）**

1. **广告业的内容分级标准有两层：IAB Tech Lab Content Taxonomy 负责「这是什么内容」，GARM Brand Safety Floor + Suitability Framework 负责「这内容有多危险」。** 两者在 IAB Content Taxonomy 2.2（2020-10-28 发布征求意见）起被正式拼接：GARM 的 11 个风险类别被原样放成 Content Taxonomy 里 `Sensitive Topics`（ID `v9i3On`）的 11 个子类，GARM 的 4 个风险级被做成一个**正交向量** `Brand Suitability and Risk`（ID `MRkz4Q`，子项 `bsr001 Floor` / `bsr002 High Risk` / `bsr003 Medium Risk` / `bsr004 Low Risk`）。

2. **行业标准的维度模型不是笛卡尔积。** IAB Content Taxonomy 3.x = 「一套 aboutness 主题分类（4 层、704 个节点、37 个顶层）」+ 「6 个正交向量/扩展」。Momcozy 假设的「国家 × 品类 × 平台 × 内容类型」四个轴，在行业标准里**四个都存在，但都不相乘**：平台 = `Content Environment` 向量；内容类型 = `Content Form Factor` 向量；国家 = `Content Source Geo Extension`（指向 ISO-3166-1-alpha-3）；语种 = `Content Language Extension`（指向 ISO-639-1-alpha-2）；品类 = aboutness 树里的 `Shopping` 等分支。IAB 自己的原话是风险级「encoded in an orthogonal vector accordingly, allowing "risk" to be associated with a "topic" **dynamically**」——**风险是挂在主题上的动态属性，不是矩阵里的格子。**

3. **GARM 的层级是 4 档（Floor / High Risk / Medium Risk / Low Risk），不是 3 档。** 已通过三个独立一手来源交叉核实（IAB Tech Lab 官方新闻稿 2020-10-28、IAB Tech Lab `implementation.md`、IAB Tech Lab 官网 Zefr 署名文章）。实际标注数据集里还多出一个 `minimal` 档，共 **5 档序数刻度**。

4. **Floor 的语义是「所有人都不能碰」，且它是「可货币化」的反面。** 最直接的原文证据来自 IAB Tech Lab 产品高级总监 Amit Shetty 在 2020-10-28 新闻稿里的引语：「publishers can monetize more content that is **not in the 'floor' category** and the entire ecosystem can identify content that could potentially be harmful.」——**Floor 以上才有「按风险偏好买/不买」的空间；Floor 本身没有议价空间。** 这就是「地板」和普通风险等级的本质区别：普通等级是「你愿不愿意」，Floor 是「允不允许」。

5. **GARM 已于 2024-08-09 停止运营，但其标准仍在被内嵌使用。** WFA 官网保留的原文声明：「Today we announce that GARM will discontinue its activities.」以及「GARM's toolset includes the Brand Safety Floor and the Adjacency Standards Framework, which have supported brand owners in their **independent development of their own bespoke, brand-specific safety frameworks**」。**含义：GARM 的产物不是一份要照着抄的 SOP，而是一套要被每家公司「本地化成自己的框架」的骨架。**

6. **行业标准自带一个「错题本」原型，而且是可运行的。** IAB Tech Lab 官方 GitHub 仓库 `IABTechLab/Brand-Suitability-Test-Benchmarks`（Zefr 捐赠，Apache-2.0）里是 **5,330 条人工标注的 YouTube 视频**（字段只有 `label,url,title`），标签值取自 `minimal/low/medium/high/floor`，聚合规则是「11 类中取最高档」。仓库自带 `evaluation.py`：把 5 档序数标签在指定层级上二值化成「高/非高」，然后算 **Average Precision**（预测是 0–1 分数时）或 **Balanced Accuracy**（预测是标签时）。**这是「严重等级」如何变成可度量指标的完整答案。**

**关于中国跨境电商上市公司（第三问的公开证据面）**

7. **四家 A 股跨境电商上市公司（安克创新、致欧科技、赛维时代、华凯易佰）2025 年报中，「内容审核」出现 0 次。** 安克创新 2023 / 2024 / 2025 三份年报中「广告」出现 **0 / 0 / 0 次**。**「都查不到」本身是结论，不是调研失败**——原因见第 10 条。

8. **唯一一条真正接近 Momcozy 规则库的同行公开披露，在赛维时代 2025 年报第 24 页**（研发项目「基于大模型的侵权检测平台」）：「**建立侵权风险知识库与预警机制**，实现新品上架前的侵权风险前置筛查及在售商品的持续监控」、「构建覆盖主要跨境电商平台的**侵权案例知识库**，实现侵权风险的**自动评级**与智能预警；目标实现侵权的高检出率与**低误报率**」。这条披露同时给出了**知识库 + 案例库 + 自动评级 + 前置 + 在售持续监控 + 检出率/误报率双指标**——正是 Momcozy 想要的骨架，只不过赛道是知识产权而非广告合规。

9. **同行公开披露的是「AI 生成内容」，不是「AI 审核内容」。** 致欧科技 2025 年报 P17：「升级 AIGC2.0 智能图库平台，集成多模态大模型实现批量自动化出图……实现电商文案自动化生成，单环节提效达 70%」；华凯易佰 2025 年报 P12：「支持深度接入 AI 工具，辅助生成优质关键词、品牌广告创意文案、创意图片等」；赛维时代 2025 年报 P13/P24：「应用 AIGC 技术高效生成商品图片、视频等多元化营销素材」。**三家都在规模化生成内容，没有一家披露生成后的合规审核环节。**

10. **为什么「查不到」是可解释的：广告合规只有在「广告是收入项」时才进年报风险因素。** PDD Holdings 2025 年 20-F（FY2025，2026-04-29 提交，accession `0001104659-26-050727`）在 Item 3.D 有整段广告法风险披露：「The online marketing services provided by us are subject to complex and evolving advertising laws and regulations across multiple jurisdictions...」；而安克/致欧/赛维/华凯是**广告的买方**（成本侧），广告投坏了是费用问题，不是披露义务。**结论：拿「上市公司年报里没有」推断「同行没有做内容治理」是错误推理。年报只能证明「这不是他们对外披露的重大风险」，不能证明「他们内部没有流程」。**

11. **同行确实披露了「平台规则突变风险」，且措辞值得直接引用。** 赛维时代 2025 年报 P33「（3）店铺关闭风险」：「公司不能完全排除未来 Amazon 平台以及其他第三方电商平台可能会**在未事先与平台卖家进行必要和充分的沟通的情况下，突然改变平台规则**或对公司多账号经营模式合规性提出质疑甚至否定……的风险」；并逐字披露了「报告期内公司并未因该多账号经营模式受到 Amazon 平台关闭店铺的处罚」。**这是「平台政策是外部变量、且变动不可预期」的一手公司披露。**

**关于岗位、服务商与平台侧**

12. **岗位 JD 与平台侧卖家帮助文档在本环境无法抓取（全部为 JS 单页应用或被反爬拦截），已在缺口清单逐项列明。** 可替代的一手证据：Amazon Ads 官方《品牌安全》指南（区分 brand safety 与 brand suitability）、Amazon Brand Registry / Transparency 公开产品页、BrandShield 公开方法论（明确写了严重度、误报、人机分工、度量指标）。

---

## 1. 广告业的内容分级与品牌安全标准

### 1.1 IAB Tech Lab Content Taxonomy —— 「这是什么内容」的标准本体

#### 1.1.1 版本与发布节奏（逐字）

来源：<https://iabtechlab.com/standards/content-taxonomy/>
页面顶部标注：`Last updated: February 11, 2026`
本地证据：`_evidence/R6/iab-content-taxonomy-page.html` / `.txt`

原文（版本表）：

> | Version | Release Date | Additional Notes |
> | Content Taxonomy 3.1 | December 2024 | |
> | Content Taxonomy 3.0 | June 2022 | ... This update includes some deletions which make this version of the taxonomy **non-backwards compatible** with previous releases. |
> | Content Taxonomy 2.2 | December 2020 | |
> | Content Taxonomy 2.1 | October 2020 | |
> | Content Taxonomy 2.0 | November 2017 | |
> | Content Taxonomy 1.0 | | Deprecated and should NOT be used for content categorization in the absence of SCD flags. |

原文（3.1 与 3.0 的差别）：

> The 3.1 version of the content taxonomy was open for public comment until Jan 24, 2025. This latest version contains an update to the 'genre' category to include Thriller.

**实测确认**：把 3.0 与 3.1 的 TSV 做 diff，两个文件都是 704 条数据行；差异仅为：顶层标题里的版本号、`Outdoor Attractions/Parks` 改名为 `Outdoor Activities/Parks & Nature`、`Musicals`→`Musical`、`Public Radio` 的父节点从 `371` 改为 `SPSHQ5`、新增 `700 SPSHQ5 Thriller`、`Maps & Navigation` 从 `602` 下移到 `Computing` 下。**即 3.1 是一次极小的修订，3.0 才是结构性版本。**

本地证据：`_evidence/R6/iab-content-taxonomy-3.0.tsv`、`iab-content-taxonomy-3.1.tsv`（通过 `diff` 验证）。

#### 1.1.2 顶层分类与分层深度（实测）

来源：<https://github.com/InteractiveAdvertisingBureau/Taxonomies/blob/develop/Content%20Taxonomies/Content%20Taxonomy%203.1.tsv>
本地证据：`_evidence/R6/iab-content-taxonomy-3.1.tsv`（706 行；表头在第 2 行，列为 `Unique ID | Parent | Name | Tier 1 | Tier 2 | Tier 3 | Tier 4 | Extension`）

实测：**37 个顶层类别，层级分布 T1=37 / T2=323 / T3=275 / T4=69，最多 4 层。**

37 个顶层（按文件顺序逐字抄录）：

```
Attractions / Automotive / Books and Literature / Business and Finance / Careers /
Communication / Crime / Disasters / Education / Entertainment / Events /
Family and Relationships / Fine Art / Food & Drink / Genres / Healthy Living /
Hobbies & Interests / Holidays / Home & Garden / Law / Medical Health /
Personal Celebrations & Life Events / Personal Finance / Pets / Politics /
Pop Culture / Real Estate / Religion & Spirituality / Science / Sensitive Topics /
Shopping / Sports / Style & Fashion / Technology & Computing / Travel /
Video Gaming / War and Conflicts
```

**每一层怎么切？** 从数据结构本身可以看出：`Tier 1..Tier 4` 四列是**同一棵树展开成扁平列**（`Unique ID` + `Parent` 定义树形，`Tier N` 是便于查询的冗余展开）。**它不是「按敏感度」分层的，而是按「主题/体裁」这一条轴分层**——敏感度被彻底剥离出去，单独做成了一个向量（见 1.1.4）。这是本分片最重要的结构性结论。

关键观察：`Sensitive Topics`（ID `v9i3On`）**只是 37 个顶层之一，和其他 36 个平级**。也就是说，在 IAB 的模型里，「敏感内容」不是一个更高的层级，而只是主题树上的一个分支；它之所以特殊，是因为**只有它的子节点会被打上风险级标签**（见 1.1.4 的 Note 1）。

#### 1.1.3 一套分类如何同时服务「投放定向」与「品牌安全」

IAB 的答案写在实现指南里。来源：<https://github.com/InteractiveAdvertisingBureau/Taxonomies/blob/develop/implementation.md>（本地：`_evidence/R6/iab-taxonomies-implementation.md`）

第 295 行逐字：

> The IAB Tech Lab Content Taxonomy provides a "common language" that all parties—publishers, Server-Side Providers (SSPs), Demand-Side Providers (DSPs), verification vendors, and advertisers—can use and understand when describing the content of a page, app, or other user environment. **The content taxonomy is useful in two main use cases—addressability (or contextual targeting) and brand safety/suitability (introduced in 2.2).**

第 303 行逐字（**这是维度模型的关键原句**）：

> The 2.x & 3.x content taxonomy includes two parts – **a set of categories that describe the topic context or "aboutness", and an additional set of orthogonal content attributes / "vectors"** such as content language, format, language, source, media type, etc. These are all associated with IDs that are used when communicating information about a piece of content.

第 305–307 行逐字（**传输协议，说明这是真在跑的编码而不是纸面文件**）：

> The IDs within the Taxonomy specs should be used when tagging content. ... the most common usage is to associate a piece of content with an **array of IDs**.
> With OpenRTB / AdCOM (Advertising Common Object Model), the "cat" attribute should be used to transmit a list of categories associated with the content and the "cattax" attribute should be set to 2 (for Content Taxonomy version 2.x and higher).

**机制解读（我的判断，非原文）**：同一套 ID 数组，投放定向时被读作「我要投 Shopping > ...」，品牌安全时被读作「我要排除 Sensitive Topics > ... 且风险级 ≥ High」。**一个分类体系、两种消费方式，靠的是消费端而不是分类端**——分类本身不做「用途」区分。

#### 1.1.4 ★ 维度模型的行业答案：正交向量（Descriptive Vectors）

来源：<https://github.com/InteractiveAdvertisingBureau/Taxonomies/blob/develop/Content%20Taxonomies/Content%20Taxonomy%203.0%20Descriptive%20Vectors.tsv>
本地证据：`_evidence/R6/iab-content-taxonomy-3.0-descriptive-vectors.tsv`（49 行）

完整结构（逐字抄录全部行，列序为 `Unique ID | Parent | Name | Tier 1 | Tier 2 | Tier 3 | Tier 4`）：

```
1000  |        | Content Environment                        | Content Environment
1002  | 1000   | Email                                      | Content Environment | Email
1003  | 1000   | Forum/Community                            | Content Environment | Forum/Community
1005  | 1000   | Marketplace/eCommerce                      | Content Environment | Marketplace/eCommerce
1006  | 1000   | Search Engine/Listings                     | Content Environment | Search Engine/Listings
1007  | 1000   | Social                                     | Content Environment | Social
1008  | 1000   | Utility/Online Tool                        | Content Environment | Utility/Online Tool
1009  | 1000   | Voice Activated Channels                   | Content Environment | Voice Activated Channels
092QD4| 1000   | General                                    | Content Environment | General
1010  |        | Content Purpose                            | Content Purpose
1012  | 1010   | Conversational                             | Content Purpose | Conversational
1014  | 1010   | Entertainment Content                      | Content Purpose | Entertainment Content
5S2VRK| 1010   | Informational                              | Content Purpose | Informational
1011  | 5S2VRK | Academic/Research Content                  | Content Purpose | Informational | Academic/ResearchConent
1013  | 5S2VRK | Educational Content                        | Content Purpose | Informational | Educational Content
1017  | 5S2VRK | Instructional Content                      | Content Purpose | Informational | Instructional Content
1020  | 5S2VRK | News                                       | Content Purpose | Informational | News
BEZLLC| 5S2VRK | Opinion & Op-Ed                            | Content Purpose | Informational | Opinions & Op-Eds
1021  | 5S2VRK | Review                                     | Content Purpose | Informational | Review
1019  | 1010   | Commerce                                   | Content Purpose | Commerce
1215  |        | Content Source                             | Content Source
1216  | 1215   | Professionally Produced                    | Content Source | Professionally Produced
1217  | 1215   | User Generated                             | Content Source | User Generated
1218  | 1215   | Aggregated/Curated                         | Content Source | Aggregated/Curated
1022  |        | Content Form Factor                        | Content Form Factor
1023  | 1022   | Audio                                      | Content Form Factor | Audio
REJJOG| 1023   | Podcast                                    | Content Form Factor | Audio | Podcast
7OCXIZ| 1023   | Radio                                      | Content Form Factor | Audio | Radio
MJDJZY| 1023   | Event                                      | Content Form Factor | Audio | Event
1024  | 1022   | Images/Galleries                           | Content Form Factor | Images/Galleries
1026  | 1022   | Mixed                                      | Content Form Factor | Mixed
1027  | 1022   | Textual                                    | Content Form Factor | Textual
1028  | 1022   | Video                                      | Content Form Factor | Video
C2UKBG| 1028   | Show                                       | Content Form Factor | Video | Show
3927X6| C2UKBG | Episodic Show                              | Content Form Factor | Video | Show | Episodic Show
Y2MK22| 1028   | Event                                      | Content Form Factor | Video | Event
O3EQZQ| 1028   | Clip                                       | Content Form Factor | Video | Clip
20L2OV| 1028   | Movie                                      | Content Form Factor | Video | Movie
1004  | 1022   | Game                                       | Content Form Factor | Game
1029  | 1022   | VR/AR                                      | Content Form Factor | VR/AR
MRkz4Q|        | Brand Suitability and Risk                 | Brand Suitability and Risk
bsr001| MRkz4Q | Floor                                      | Brand Suitability and Risk
bsr002| MRkz4Q | High Risk                                  | Brand Suitability and Risk
bsr003| MRkz4Q | Medium Risk                                | Brand Suitability and Risk
bsr004| MRkz4Q | Low Risk                                   | Brand Suitability and Risk
1030  |        | *Content Language Extension                | *Content Language Extension   (Extension列: See ISO-639-1-alpha-2)
1219  |        | *Content Source Geo Extension              | *Content Source Geo Extension (Extension列: See ISO-3166-1-alpha-3)
```

**逐个回答任务书里点名要问的问题：**

| 问题 | 行业标准答案 | 证据 |
|---|---|---|
| 有没有把「内容类型」作为分类轴？ | **有，但不在主题树里**，在 `Content Form Factor` 向量（Textual / Images-Galleries / Video / Audio / Mixed / Game / VR-AR，各有下级） | 上表 |
| 有没有把「平台」作为分类轴？ | **有，但不在主题树里**，在 `Content Environment` 向量（Email / Forum-Community / Marketplace-eCommerce / Search Engine-Listings / Social / Utility-Online Tool / Voice Activated Channels / General） | 上表 + implementation.md 第 320 行「Describes the surrounding platform (distinct from device)」 |
| 有没有把「地区/国家」作为分类轴？ | **有，但是扩展向量**，`*Content Source Geo Extension` → **ISO-3166-1-alpha-3**（用现成国际标准，不自造） | 上表 Extension 列 |
| 有没有把「语种」作为分类轴？ | **有，但是扩展向量**，`*Content Language Extension` → **ISO-639-1-alpha-2**（同样外挂国际标准） | 上表 Extension 列 |
| 如果没有，它用什么替代？ | 不是「替代」，而是**结构性选择：把「主题」和「属性」分成两层，属性之间互不相乘**。风险级是属性之一，不是格子之一 | implementation.md 第 303、384 行 |

**为什么这个区分重要**：如果是笛卡尔积，「法国 × 吸奶器 × Meta × 短视频」会是一个独立规则集合；正交向量下，它是「同一个主题标签 + 一组属性标签 + 一个风险级」，**规则的组合爆炸被消灭**。Momcozy 现在的 21 条规则里有 8 条带正则、`适用产品` 全部写死为五个吸奶器型号——这正是「用笛卡尔积思维写规则」的症状（见第 6 节）。

---

### 1.2 GARM —— Brand Safety Floor + Suitability Framework

#### 1.2.1 GARM 是什么、为什么出现（WFA 官方叙述，逐字）

来源：<https://wfanet.org/leadership/garm>（WFA 官网，抓取 2026-09-15）
本地证据：`_evidence/R6/garm-wfa-statement-2024-08-09.html`

逐字原文：

> The Global Alliance for Responsible Media (GARM) was a voluntary cross-industry initiative **created in 2019** to address digital safety. GARM was set up in the wake of the Christchurch New Zealand Mosque shootings during which the killer livestreamed the attack on Facebook. This followed a slew of high-profile cases where brands' ads appeared next to illegal or harmful content, such as promoting terrorism or child pornography – creating both consumer and reputational issues for brands.
>
> Since its launch, GARM has enhanced transparency in ad placements on digital social media by providing voluntary and pro-competitive tools for the advertising industry. These tools provide information to help advertisers avoid inadvertently supporting harmful and illegal content, **reducing such ads from 6.1% in 2020 to 1.7% in 2023**. GARM's toolset includes the **Brand Safety Floor** and the **Adjacency Standards Framework**, which have supported brand owners in their **independent development of their own bespoke, brand-specific safety frameworks** to ensure that their advertising dollars do not inadvertently support illegal or harmful content that damages their brands.

**注意措辞**：「have supported brand owners in their independent development of their own bespoke, brand-specific safety frameworks」——**GARM 从来没有打算提供一份可以直接抄的 SOP，它的定位是让每家公司自己长出一套框架。** 这对 Momcozy「规则库该自己建还是抄行业标准」是一个直接回答：**抄骨架，自己填肉**。

#### 1.2.2 11 个风险类别（三个来源交叉核实，逐字）

**来源 A：IAB Tech Lab 官方新闻稿，2020-10-28**
URL：<https://iabtechlab.com/press-releases/tech-lab-releases-for-comment-content-taxonomy-to-improve-brand-safety-support-brand-suitability/>
本地证据：`_evidence/R6/iab-pr-ct22-2020-10-28.html` / `.txt`

逐字：

> **Full List of Sensitive Topic Categories include:**
> 1. Adult & Explicit Sexual Content
> 2. Arms & Ammunition
> 3. Crime & Harmful Acts to Individuals and Society and Human Right Violations
> 4. Death Injury, or Military Conflict
> 5. Online Piracy
> 6. Hate Speech & Acts of Aggression
> 7. Obscenity and Profanity
> 8. Illegal Drugs/Tobacco/E-Cigarettes/ Vaping/Alcohol
> 9. Spam or Harmful Content
> 10. Terrorism
> 11. Sensitive Social Issues

**来源 B：IAB Tech Lab 实现指南 `implementation.md` 第 370–382 行**
URL：<https://github.com/InteractiveAdvertisingBureau/Taxonomies/blob/develop/implementation.md>

逐字：

> The 11 Brand Safety categories identified in the framework are introduced in v2.2 of the Content Taxonomy as topic categories under the parent category "Sensitive Topics" (id "v9i3On" in the Content Taxonomy 2.2 spreadsheet). The 11 categories are:
> 1. Adult & Explicit Sexual Content
> 2. Arms & Ammunition
> 3. Crime & Harmful acts to individuals and Society and Human Right Violations
> 4. Death Injury, or Military Conflict
> 5. Online piracy
> 6. Hate speech & acts of aggression
> 7. Obscenity and Profanity
> 8. Illegal Drugs/Tobacco/eCigarettes/ Vaping/Alcohol
> 9. Spam or Harmful Content
> 10. Terrorism
> 11. Sensitive Social Issues

**来源 C：我实测的 3.1 TSV 里 `Sensitive Topics`（`v9i3On`）的 11 个子节点**（注意第 3、4、5、11 项的字面与上面两处略有出入，以 TSV 为准）：

```
Rm3SiT  Adult & Explicit Sexual Content
avbNf2  Arms & Ammunition
XtODT3  Crime & Harmful Acts to Individuals, Society & Human Right Violations
I4GWl6  Death, Injury, or Military Conflict
Z7rJBM  Debated Sensitive Social Issues          ← 对应 "Sensitive Social Issues"
HxqYV1  Hate Speech and Acts of Aggression
pg0WhF  Illegal Drugs, Tobacco, eCigarettes, Vaping, Alcohol
j9PaO9  Obscenity and Profanity
mm3UXx  Online Piracy
6i4dB6  Spam or Harmful Content
8FD8nI  Terrorism
```

**结论：任务书提示的「通常说 11 类」得到核实，且 11 类在 IAB 的机器可读分类表里就是 `Sensitive Topics` 的全部子节点。**「Debated Sensitive Social Issues」是 `Sensitive Social Issues` 的后续改名版本。

#### 1.2.3 层级：4 档（Floor / High / Medium / Low）

**来源 A：IAB Tech Lab 新闻稿 2020-10-28，逐字**

> - Risk levels were created to identify a range of suitability and are treated as **additional attributes of the content**. The four levels of risk are **"Floor," "High Risk," "Medium Risk," and "Low Risk."**
> - **Both topics and risk levels work together, dynamically.**

**来源 B：IAB Tech Lab `implementation.md` 第 384–389 行，逐字**

> The risk levels in the Framework that identify the levels of suitability are treated as additional attributes of the content. **They are encoded in an orthogonal vector accordingly, allowing "risk" to be associated with a "topic" dynamically.** The levels are:
> 1. Floor
> 2. High Risk
> 3. Medium Risk
> 4. Low Risk

**来源 C：IAB Tech Lab 官网 Zefr 署名文章**（「GARM Brand Suitability: Developing a Collaborative Interpretation of the Standard」，作者 Jon Morra, PhD, Chief Data Scientist, Zefr）
URL：<https://iabtechlab.com/garm-brand-suitability-developing-a-collaborative-interpretation-of-the-standard/>
本地证据：`_evidence/R6/iab-zefr-garm-interpretation.html` / `.txt`

逐字：

> In 2019, the Global Alliance for Responsible Media, GARM, released the brand safety and suitability standard. **This standard, spreads out 11 categories of content against 4 risk levels (low, medium, high, and floor)** and was created to allow brands to have a clear and concise vocabulary to define their particular brand suitability needs.

**→ 11 × 4 = 44 格。这就是「严重等级 × 类别」的行业标准形状。**

#### 1.2.4 ★ 「Floor」（地板）的精确定义

**IAB 实现指南并没有给出逐格指导原文**——它把定义明确甩给了 GARM 原文档。第 368 行逐字：

> For the purposes of the Content Taxonomy v2.2, **the descriptions for each category at each risk level, including the Floor, are described in the framework.**

以及第 360–364 行的向量描述表里，四行描述全部只写：

> | Brand Suitability and Risk | Defined in the GARM / 4As/APB specs |
> | Floor | Defined in the GARM / 4As/APB specs |
> | High Risk | Defined in the GARM / 4As/APB specs |
> | Medium Risk | Defined in the GARM / 4As/APB specs |
> | Low Risk | Defined in the GARM / 4As/APB specs |

**这是本分片最大的证据缺口：GARM 原 PDF 现被 WFA 登录墙拦截，我没能取到「每个类别 × 每个层级」的逐格指导原文。** 详见第 8 节缺口清单。以下是**从可取到的一手材料中能确证的 Floor 语义**：

**证据 1（最直接）——IAB Tech Lab 产品高级总监 Amit Shetty 的引语，2020-10-28 新闻稿逐字：**

> "While Tech Lab had always planned to update the Content Taxonomy, COVID-19 has accelerated the need as many advertisers blocklisted critical and educational topics about the pandemic," said Amit Shetty, Sr. Director, Product, IAB Tech Lab. "With the updated framework, advertisers have more control and can be nuanced about what topics they advertise on. **At the same time, publishers can monetize more content that is not in the 'floor' category** and the entire ecosystem can identify content that could potentially be harmful."

**证据 2——GARM 负责人 Rob Rakowitz 的引语，同一新闻稿逐字：**

> "IAB Tech Lab's Content Taxonomy 2.2 provides the means to operationalize the work we have done at GARM to define sensitive categories across the entire digital ecosystem, including programmatic," said Rob Rakowitz, Initiative Lead, GARM. "We believe this update dramatically helps to increase brand safety and provide a **baseline level of understanding** for brands and publishers to clearly communicate the nature of the content that is being distributed."

**证据 3——IAB 实现指南第 368 行「双重目标」原文：**

> The goal of including these categories are twofold. First, to provide a mechanism to **mark content that might not be suitable for certain brands**, but equally important, to **allow content that might otherwise have been blanket marked as unsafe to be monetized by allowing brands with the right risk tolerance to buy such inventory.**

**综合解读（我的判断，明确标注为判断）**：
- **普通风险等级（Low/Medium/High）解决的问题是「同一个主题，不同品牌的容忍度不同」** → 输出是「买 / 不买」的商业决策。
- **Floor 解决的问题是「不管什么品牌，都不该买」** → 输出是「全行业统一下架」的准入决策。
- 因此 Floor 和其他三档**不是同一个量纲上的四档**。三档是「偏好」，Floor 是「底线」。证据 3 里 "blanket marked as unsafe" 与 "monetized" 的对立，正是这条分界线。
- 一个可验证的旁证：IAB 官方标注集 `Brand-Suitability-Test-Benchmarks` 的 README 把 5 个合法标签列为 `minimal, low, medium, high, floor`，但**实际 5,330 条样本里 floor 出现 0 次**（分布见 1.4.2）。**Floor 在实践中是稀有事件——这正符合「底线」的语义：它不该是常态档位。**

**为什么要有地板——对 Momcozy 的直接启发（预告第 6 节）**：Momcozy 的 H 族（严格限制红线）自称「红线」，但字段上它和 M/U 族是同构的（同一张表、同一个 `风险等级` 四档枚举、同样 21/21 全部「自动可检测」）。**行业标准的做法是让 Floor 在结构上就与其他档不同**：Floor 不需要「品牌偏好」参数、没有申诉/议价路径、它的判定结果直接是 exclude。这一点在第 6 节展开。

#### 1.2.5 「这份框架如何被实际使用」——采用者证据

**采用者 A：IAB Tech Lab（标准化方）。** 全文见 1.1、1.2.2–1.2.4。要点：GARM 的 11 类被做成 `Sensitive Topics` 的 11 个子节点；4 个风险级被做成 `Brand Suitability and Risk` 正交向量（`bsr001`–`bsr004`）。**这是「被内嵌」的最硬证据——不是引用，是编码进了 OpenRTB/AdCOM 实际传输的 ID 数组。**

**采用者 B：Zefr（品牌适用性技术方）。** 同一 IAB 官网文章逐字：

> In July 2021, Tech Lab announced a new initiative: the Open Source Repository for the industry. **Zefr has contributed to this initiative by providing rich data-sets based human reviews of video content against the GARM standards**, to in turn help both the buy-side and the sell-side have a common source when "brand suitability" is being referred to in video environments. After extensive testing, we know that this data set is an effective tool **when used as training data to build strong and robust machine learning systems** to evaluate data signals for video content.

**采用者 C：Amazon Ads（需求侧/平台侧）。** Amazon Ads 官方指南《什么是品牌安全？定义、示例及其运作方式》
URL：<https://advertising.amazon.com/library/guides/brand-safety>
本地证据：`_evidence/R6/amazon-ads-brand-safety.html` / `.txt`
注意：该页面按浏览器语言返回了中文版，以下为中文原文逐字（**这也是本分片唯一一处中文的官方「品牌安全」定义**）：

> **品牌安全与品牌适用性有什么区别？**
> 品牌适用性的概念与品牌安全性有关。**品牌安全性是指避免不当内容，而对于哪些内容属于不当内容，所有受众通常都有一致的看法。另一方面，品牌适用性对于单个品牌而言是与众不同的。** 品牌适用性是指将您的广告与符合您的特定价值观、身份、风格和其他主观特征的内容相匹配。
> 例如，素食品牌可能不会将有关狩猎和钓鱼的应用视为适合其广告的广告位，**尽管狩猎和钓鱼并不是每个人都反感的话题**。语气非常随意和幽默的网站可能不适合品牌声音比较严肃的公司。

**这段话是对 Floor / 其余三档分工的一句话解释**：「所有受众都有一致看法」= Floor；「对于单个品牌而言是与众不同的」= High/Medium/Low。**Amazon 作为采用者，用自己的语言复述了同一结构。**

同一页面还给出可操作流程（逐字）：

> 2. 选择成熟的程序化提供商
> 3. 利用"包含"列表和"排除"列表：使用可用的投放选项来确定要包含以及要排除的广告资源。
> 4. 把品牌安全性放在首位：保护品牌安全性不是一件一劳永逸的事情，而是一个**持续的过程**。品牌必须**定期评估**可能威胁其品牌安全性的因素。……请**不断更新"包含"列表和"排除"列表**。

**本环境未取到采用者声明：** Meta、Google、GroupM、Unilever 的公开声明页在本环境均无法抓取（`support.google.com` 连接超时、`transparency.meta.com` 连接超时、`unilever.com` 403、`groupm.com` 200 但未找到 GARM 专页）。见第 8 节缺口清单。

---

### 1.3 GARM 停止运营的核实（任务书点名的核实项）

**谁在 2024 年 8 月宣布了什么，原文出处：**

- **宣布者**：WFA（World Federation of Advertisers，世界广告主联合会）——GARM 的托管方。
- **宣布日期**：声明末尾署 **`9 August 2024`**。
- **原始出处 URL**：<https://wfanet.org/leadership/garm>（该页标题为 `GARM`，正文标题为 `Statement on the Global Alliance for Responsible Media (GARM)`）
- **本地证据**：`_evidence/R6/garm-wfa-statement-2024-08-09.html`
- **抓取日期**：2026-09-15（**截至抓取时该声明仍在 WFA 官网原址可访问，未被删除**）

**逐字原文（第一节）：**

> ## Statement on the Global Alliance for Responsible Media (GARM)
>
> **Today we announce that GARM will discontinue its activities.**

**逐字原文（原因段）：**

> GARM is a small, not-for-profit initiative, and **recent allegations that unfortunately misconstrue its purpose and activities have caused a distraction and significantly drained its resources and finances**. WFA therefore is making the difficult decision to discontinue GARM activities.

**逐字原文（收尾与联系方式）：**

> For further enquiries, please contact Will Gilroy at w.gilroy@wfanet.org.
> _9 August 2024_

**核实结论：**

1. ✅ **GARM 确实于 2024-08-09 由 WFA 宣布停止活动**，且原文可在 wfanet.org 原址取到。
2. ✅ **其标准文档「仍被行业广泛内嵌」得到证实**——最硬的证据不是谁在引用它，而是 **IAB Content Taxonomy 3.1（2024-12 发布，晚于 GARM 解散）里 `bsr001 Floor / bsr002 High Risk / bsr003 Medium Risk / bsr004 Low Risk` 四个节点依然存在**（我实测的 TSV）。**GARM 死了，GARM 的枚举值还活在行业标准的传输格式里。**
3. ⚠️ **其标准文档「仍可公开查」这一点只部分成立**：WFA 图书馆里那份原 PDF 的下载链接现在是**登录墙**（见缺口清单），但 IAB Tech Lab 的实现指南与新闻稿完整保留并逐条复述了它的结构。

**这个「标准比组织活得久」的现象，对 Momcozy 有一个直接教训**：把规则库的**枚举值（ID + 名称 + 顺序）**和**填充内容（每个格子的指导文本）**分开存。组织/供应商会死，枚举值要设计成能活十年。

---

### 1.4 落地形态：GARM 标准的两件真实产物

#### 1.4.1 产物一：机器可读的 ID 编码

已在 1.1.4 给出。要点复述：`MRkz4Q`（Brand Suitability and Risk）下有 `bsr001`–`bsr004`；`v9i3On`（Sensitive Topics）下有 11 个子节点，每个都有**稳定的字母数字 ID**（不是自增数字，如 `bsr001`、`Rm3SiT`、`XtODT3`）。IAB 明确说明这些 ID 用于 OpenRTB/AdCOM 的 `cat` 数组传输。

**这是「规则编号」的行业标准做法：稳定 ID + 名称 + 顺序，且 ID 一旦发布不改。** 对照 Momcozy：`H01`–`H09` / `M01`–`M07` / `U01`–`U04` 已经是稳定 ID，这一点他们做对了。

#### 1.4.2 产物二：★ 官方「错题本」——IAB Brand Suitability Test Benchmarks

**仓库**：<https://github.com/IABTechLab/Brand-Suitability-Test-Benchmarks>
**描述字段（GitHub API 逐字）**：`Media content that has been human labeled according to the GARM standard.`
**创建时间**：2021-04-20；**最后更新**：2023-09-05；**许可证**：Apache-2.0
**仓库 homepage 字段（逐字）**：`https://wfanet.org/l/library/download/urn:uuid:7d484745-41cd-4cce-a1b9-a1b4e30928ea/garm+brand+safety+floor+suitability+framework+23+sept.pdf`
→ **这独立佐证了 GARM 框架文档的权威 URL，即使该 URL 现在被登录墙挡住。**

**README 逐字（本地：`_evidence/R6/iab-brand-suitability-test-benchmarks-README.md`）：**

> This repository contains a list of human reviewed content and the labels assigned by those people **according to the GARM standard**.

**数据格式逐字：**

> 1. `label` - **Of the 11 GARM categories, the highest label applicable.** The label values are one of `minimal`, `low`, `medium`, `high`, or `floor`. For example **if a video is medium for adult content, high for weapons, minimal for everything else then the label would be high.**
> 2. `url` - The URL where the video can be found.
> 3. `title` - The user supplied title of the video

**★ 三个关键设计决策（这是本分片对 Momcozy 最有价值的单条发现）：**

1. **粒度：一条内容一个总标签，取 11 类中的最高档（max 聚合）。** 不是「11 个标签各存一个」，而是**先按类判定、再取最大值**。这解决了「一条内容同时命中多个风险类别时怎么定级」的问题，而且答案简洁到可以直接实现。
2. **档位是 5 档序数（minimal < low < medium < high < floor），不是 4 档。** 4 档是 GARM 的公开层；实践里必须补一个 `minimal`（= 无风险），否则「没命中任何类」没有取值。**Momcozy 的四档 `高危/审慎/待复核/合规` 结构上是对的，但他们把「合规」和风险档混在同一个枚举里——行业做法是把「无风险」作为最底档显式纳入刻度，而不是当成「没命中规则」的默认值。**
3. **数据集只存三个字段：`label, url, title`。** 没有「命中规则编号」、没有「判定人」、没有「理由」。**行业官方错题本的最小字段集比 Momcozy 现在字段少得多**——他们现有字段是 12 个（规则编号 | 边界类型 | 适用产品 | 风险等级 | 检测关键词 | 边界内容 | 判断方式 | 依据来源 | 启用状态 | 正则表达式 | 豁免词 | 触发原因）。见第 6 节。

**★ 实测数据（我下载并统计，本地：`_evidence/R6/iab-bsb-youtube.csv`）：**

- 文件：`video/data/youtube.csv`，**5,330 行**，表头 `label,url,title`
- 标签分布（实测）：

| label | 条数 | 占比 |
|---|---:|---:|
| minimal | 3,285 | 61.6% |
| medium | 1,285 | 24.1% |
| high | 599 | 11.2% |
| low | 161 | 3.0% |
| **floor** | **0** | **0%** |

- README 对此有明确免责逐字：

> Note that at least for the YouTube file, **the distribution of labels is *not* indicative of the distribution of labels on the platform as a whole. The distribution was chosen to give a more uniform set of labels.**

**→ 这是「错题本应该长什么样」的一条硬约束：官方错题本是刻意做过类别平衡的，不是自然分布的流水账。** 自然分布下 minimal 会占 99%+，那样的数据集训不出东西。

**★ 度量方式（`evaluation.py`，本地：`_evidence/R6/iab-bsb-evaluation.py`，逐字）：**

```python
def convert_labels_to_booleans(df: pd.DataFrame, higher_level: Optional[str] = None) -> pd.DataFrame:
    high_labels: Set[str] = set()
    if higher_level == 'floor':
        high_labels = {'floor'}
    elif higher_level == 'high':
        high_labels = {'floor', 'high'}
    elif higher_level == 'medium':
        high_labels = {'floor', 'high', 'medium'}
    elif higher_level == 'minimal':
        high_labels = {'floor', 'high', 'medium', 'low'}
    df['is_high'] = df.label.isin(high_labels)
    return df
```

```python
def calc_error_metrics(labels, predictions, higher_level=None):
    joined = labels.merge(predictions, on='url', how='inner')
    if labels.shape[0] != predictions.shape[0] or labels.shape[0] != joined.shape[0]:
        print(f'Supplied {labels.shape[0]} labels and {predictions.shape[0]} predictions, '
              f'but only {joined.shape[0]} items are in the inner join.')
    if joined.dtypes['prediction'] == 'float':
        joined = convert_labels_to_booleans(joined, higher_level)
        ap = average_precision_score(y_true=joined.is_high, y_score=joined.prediction)
        return 'Average Precision', ap
    else:
        ba = balanced_accuracy_score(y_true=joined.label, y_pred=joined.prediction)
        return 'Balanced Accuracy', ba
```

命令行帮助逐字：

> The predictions may be either labels with the words "minimal", "low", "medium", "high", or "floor" **or floating point numbers between 0 and 1**. If the predictions are numeric then an additional argument called level must be supplied to indicate **which two levels are being differentiated against**.

**→ 「严重等级」如何变成可度量指标的完整答案：**

1. **5 档序数刻度先被二值化**：选一个操作点（`--level floor|high|medium|low`），把刻度切成「≥该档」与「<该档」两桶。
2. **预测是标签 → 报 Balanced Accuracy**（因为类别不平衡，用平衡准确率而不是准确率）。
3. **预测是 0–1 分数 → 报 Average Precision**（阈值可滑动，所以用 PR 曲线下面积，而不是固定阈值的 F1）。
4. **只在 url 内连接（inner join）后计算**，且当标注数与预测数不一致时**打印告警而不是静默通过**。

**这四条，一条不改地适用于 Momcozy 的 21 条规则 + 291 条在跑记录。**

#### 1.4.3 产物三：★ 争议处理流程（「错题本」的迭代回路）

README「Challenges」节逐字：

> Should someone wish to challenge a particular [label] please submit a pull request and mention the piece of content by **both file, URL, and desired new label**. Please also submit a **reason** for why the label should change. The uploader of the file will respond in kind and the following flow will commence.
> 1. An agreement that the label is wrong. In this case the pull request is accepted with no further conversation is needed.
> 2. A disagreement, instead stating that the uploader thinks label is correct.
>    1. The uploader will provide a reason why it is correct.
>    2. If the challenger agrees, then the pull request is rejected and no change is made.
>    3. If the challenger disagrees then the pull request remains open.
>        1. The community at large will now be able to comment to convince either the challenger or uploader to change their mind.
>        2. If this is successful then the pull request will be closed as desired
>        3. If this is unsuccessful then the particular piece of content will be brought to the **GARM committee for resolution**.
>        4. **GARM will then either update their definitions to resolve the dispute or issue a ruling**, in either fashion stating how to close the pull request.

**→ 这是「规则库自迭代」的一个可运行模板，而且它把三种结局显式区分开了：**

| 结局 | 触发条件 | 系统动作 |
|---|---|---|
| 标注错 | 双方同意 | 直接改标注 |
| 标注对 | 挑战者被说服 | 关闭，不改 |
| **定义不清** | 双方各执一词 | **升级为「规则定义需要修改」，而不只是改这一条标注** |

**第三种结局是 Momcozy 现在完全没有的。** 他们的规则表里 `依据来源` 只指向两份内部文档，没有任何「这条规则本身被质疑 → 修改规则定义」的入口和记录位。

---

### 1.5 其他相关标准（IAB Brand Safety & Suitability / MRC / WFA）

| 标准/机构 | 核实到的一手证据 | 状态 |
|---|---|---|
| **IAB Tech Lab Brand Safety & Suitability** | 即 `Brand Suitability and Risk` 向量（`MRkz4Q`）+ `Sensitive Topics`（`v9i3On`）。定义权威仍在 GARM/4As APB 文档 | ✅ 已核实结构；逐格文本见缺口 |
| **4A's APB（Advertiser Protection Bureau）** | IAB 实现指南第 368 行逐字：「based on the Brand Safety & Suitability Framework released in September 2020 by the Global Alliance for Responsible Media (GARM) **in collaboration with the American Association of Advertising Agencies' (4As) Advertiser Protection Bureau (APB)**」——即框架是 GARM 与 4A's APB 联合产物 | ✅ 已核实存在与角色；4A's 站点本环境 403，未取到其自有文档 |
| **WFA** | WFA 是 GARM 的托管方并发布了停止声明（1.3）。WFA 另有 Global Media Charter、Policy Heatmaps（Alcohol / Green Claims / Influencer Marketing / Food Marketing and Children / Privacy）等工具，但**未发现 WFA 发布独立于 GARM 的内容分级标准** | ✅ 已核实 WFA 角色；❌ 未找到 WFA 独立内容分级标准 |
| **MRC (Media Rating Council)** | `https://www.mediaratingcouncil.org/` 可访问（HTTP 200），但**未在其站点定位到 Brand Safety 专属标准文档**；MRC 的主要标准集中在 audience measurement / viewability / invalid traffic | ⚠️ 域名可达，**内容级 Brand Safety 标准未核实到** |

**结论：广告业的内容分级标准事实上只有一条主干——GARM 框架 → 被 IAB Tech Lab 编码进 Content Taxonomy → 由验证厂商（Zefr 等）和平台（Amazon Ads 等）落地。** MRC、WFA 都不提供与 GARM 并列的第二套内容分级标准。这解释了为什么 GARM 解散后行业没有「换个标准」，而是**继续用已经渗进传输格式里的那套枚举值**。

---
## 2. 中国跨境电商上市公司的合规披露（核心证据）

### 2.0 取证方法与渠道核实

**任务书指定的三个官方渠道，在本环境的可达性实测（2026-09-15）：**

| 渠道 | 域名 | 实测结果 | 处置 |
|---|---|---|---|
| 巨潮资讯网 | `www.cninfo.com.cn` / `static.cninfo.com.cn` | **HTTP 403**（阿里云 WAF 反爬页，带指纹 `PS-DGM-01Oqz93`）；POST 到 `/new/hisAnnouncement/query` 同样 403 | ❌ 改用交易所原始渠道 |
| 深交所 | `www.szse.cn` + `disc.szse.cn` | ✅ **HTTP 200，且公开 JSON API 可用** | ✅ 主渠道 |
| 港交所披露易 | `www1.hkexnews.hk` | 页面 ✅ 200；`titleSearchServlet.do` 返回空集（参数契约未攻克） | ⚠️ 未取到 |
| SEC EDGAR | `data.sec.gov` / `efts.sec.gov` / `www.sec.gov/Archives` | ✅ 200（**必须带含联系方式的 User-Agent**，否则 403） | ✅ 主渠道 |

**深交所取数方法（可复现）**：

```
POST https://www.szse.cn/api/disc/announcement/annList?random=0.1
Headers: Content-Type: application/json; Referer: https://www.szse.cn/disclosure/listed/fixed/index.html
         X-Request-Type: ajax
Body: {"seDate":["2024-01-01","2026-09-15"],"stock":["300866"],
       "channelCode":["fixed_disc"],"pageSize":30,"pageNum":1}
返回: data[].attachPath 形如 /disc/disk03/finalpage/2026-04-10/<uuid>.PDF
下载: https://disc.szse.cn/download{attachPath}       ← 注意必须带 /download 前缀
```

**实际抓取并全文解析的正式年报（PDF → 文本，页码已在正文标注）：**

| 公司 | 代码 | 报告 | 披露日期 | 页数 | 本地文件 |
|---|---|---|---|---|---|
| 安克创新 | 300866.SZ | 2025 年年度报告 | 2026-04-10 | 238 | `listed-co-reports/anker-300866-annual-2025.pdf` / `.txt` |
| 安克创新 | 300866.SZ | 2024 年年度报告 | 2025-04-29 | — | `anker-300866-annual-2024.pdf` / `.txt` |
| 安克创新 | 300866.SZ | 2023 年年度报告 | 2024-04-25 | — | `anker-300866-annual-2023.pdf` / `.txt` |
| 致欧科技 | 301376.SZ | 2025 年年度报告 | 2026-04-29 | 235 | `ouke-301376-annual-2025.pdf` / `.txt` |
| 赛维时代 | 301381.SZ | 2025 年年度报告 | 2026-04-28 | 186 | `sailvan-301381-annual-2025.pdf` / `.txt` |
| 华凯易佰 | 300592.SZ | 2025 年年度报告 | 2026-04-25 | 247 | `huakai-yibai-300592-annual-2025.pdf` / `.txt` |
| PDD Holdings（Temu 母公司） | PDD.O | FY2025 Form 20-F | 2026-04-29（accession `0001104659-26-050727`） | — | `pdd-20f-2025.htm` / `.txt` |

**关键词计数（对去除所有空白后的全文计数，避免 PDF 换行把词切断）**：

| 关键词 | 安克2025 | 安克2024 | 安克2023 | 致欧2025 | 赛维2025 | 华凯2025 |
|---|---:|---:|---:|---:|---:|---:|
| **广告** | **0** | **0** | **0** | 8 | 18 | 12 |
| **内容审核** | **0** | **0** | **0** | **0** | **0** | **0** |
| 宣传 | 1 | 5 | 4 | 0 | 1 | 0 |
| 审核 | 9 | 6 | 6 | 0 | 2 | 4 |
| 合规 | 11 | 8 | 6 | 17 | 20 | 14 |
| 知识产权 | 1 | 2 | 2 | 0 | 4 | 1 |
| 处罚 | 4 | 7 | 7 | 6 | 5 | 24 |
| 虚假 | 3 | 3 | 3 | 14 | 25 | 40 |
| 平台规则 | 1 | 1 | 1 | 1 | 1 | 0 |

> ⚠️ 口径说明：`虚假` 的高计数几乎全部来自年报固定声明句「不存在虚假记载、误导性陈述或者重大遗漏」，**不是**内容合规风险披露；`审核` 的计数在安克全部指向董事薪酬审核、供应商 ESG 审核等，**不在内容方向上**。逐条人工核对结果见下文各公司小节。

---

### 2.1 安克创新（300866.SZ）—— 三年年报，「广告」零次

**年报「第三节 管理层讨论与分析 → 3、公司可能面临的风险」（P39–P40）完整枚举，共 4 项：**

1. （1）全球关税政策变化与贸易摩擦加剧风险
2. （2）汇率波动风险
3. （3）经营与竞争风险
4. （4）管理风险

**逐字（P39，开篇）：**

> 3、公司可能面临的风险
> （1）全球关税政策变化与贸易摩擦加剧风险
> 公司海外销售收入占比较高，业务覆盖北美、欧洲及亚太等主要市场，并通过多区域布局构建全球化销售网络。2025年以来，全球关税政策持续调整，贸易摩擦进一步加剧……

**逐字（P40，「（3）经营与竞争风险」中与品牌相关的一句）：**

> 三是持续深耕自有品牌，提升全球渠道和营销能力，通过品牌影响力、用户口碑及渠道布局构建差异化竞争优势，以应对行业竞争加剧带来的挑战。

**→ 判定：安克创新 2025 年报的风险因素章节中，完全没有「广告宣传合规」「产品描述/宣称合规」「内容审核」「知识产权侵权」「平台规则处置」这五类风险。** 2023、2024 年报同样如此（「广告」计数 0 / 0）。

**安克年报中唯一一处「规则库 + 分级 + 量化评分」的公开描述，在供应链 ESG 侧（P61）：**

逐字（P61）：

> 在可持续发展专项评估方面，公司建立标准化的供应商可持续发展评估机制，评估涵盖**人权与劳工、职业健康安全、环境保护、商业道德、管理体系五大领域共128个检查项，采用量化扣分制**。2025年运用 **AI智能体监控法规变化并升级法规数据库**，保障评估科学合规。2025年，公司共开展供应商环境与社会影响现场评估51次，覆盖各业务线，供应商ESG审核通过率达100%。公司建立**供应商风险分级标准，结合社会负面事件、自查能力、现场评估结果等因素，将供应商划分为标杆、低风险、中风险、高风险等级并实施差异化管理**。对存在不合规行为的供应商，公司**按照风险等级采取要求整改、跟进审核、暂停合作直至终止合作等处置措施**，并依据《供应链社会责任事件补救程序》为供应商提供整改支持与专项培训。

**★ 这一段是安克全部披露里对 Momcozy 最有价值的内容，且它的形状与内容审核规则库完全同构：**

| 安克供应链 ESG 的做法（逐字可引） | 对 Momcozy 内容规则库的映射 |
|---|---|
| 「五大领域共 **128 个检查项**」 | 规则库的规则条目总数与分组 |
| 「采用**量化扣分制**」 | 风险等级不是主观标注，而是**累加扣分后落档** |
| 「**AI 智能体监控法规变化并升级法规数据库**」 | 规则库的上游变更侦测（法规/平台政策变动 → 规则库更新） |
| 「供应商**风险分级标准**……标杆/低风险/中风险/高风险」 | 与 GARM 的四档/GARM+minimal 的五档同构 |
| 「按照**风险等级**采取要求整改、跟进审核、暂停合作直至终止合作」 | **等级 → 处置动作**的显式映射（不是等级单独存在） |
| 「《供应链社会责任事件补救程序》」「整改支持与专项培训」 | 命中后的补救链路，而不只是「打标」 |

**注意：这是供应链，不是内容。** 安克没有披露任何内容侧的等价机制。**但「同一家公司对供应商已经有量化扣分 + 风险分级 + 分级处置，却没有对内容建立同类机制」本身是一个强有力的论证素材**——说明这套方法论在公司内部是被承认有效的，只是还没有被搬到内容侧。

**处罚披露：** 安克 2025 年报 `处罚` 出现 4 次，逐条核对后全部是「报告期内公司现任及报告期内离任董事和高级管理人员近三年证券监管机构处罚的情况 □适用 ☑不适用」及其配套表述，**不涉及广告/内容处罚**。

---

### 2.2 致欧科技（301376.SZ）—— 披露了 AIGC 规模化生产，未披露审核

**年报「（二）公司可能面对的风险及应对措施」（P41–P42）完整枚举，共 4 项：**

1. 汇率波动风险
2. 地缘政治、贸易摩擦风险
3. 海运价格波动风险
4. 市场竞争加剧风险

**→ 判定：致欧 2025 年报风险因素章节中没有内容/广告合规风险。**

**致欧对「合规」的 AI 投入全部落在供应链与清关侧（P17）：**

逐字（P17）：

> 在供应链环节公司将AI技术深度嵌入履约与质检环节，有效优化合规性与管控精度。**利用AI自动生成海关编码，优化了跨境物流清关与合规体系；同时引入AI视觉识别技术，高效检测质检图片**，大幅提升了批量产品的品控准确率与检验效率。

**→ 注意：致欧确实用了 AI 视觉识别做「检测」，但检测对象是**质检图片（实物质量）**，不是**营销素材（内容合规）**。**

**★ 致欧公开披露的 AIGC 内容生产规模（P17，逐字）：**

> 报告期内，公司积极推进营销AI全流程化。在内容生产上，**升级AIGC2.0智能图库平台，集成多模态大模型实现批量自动化出图，实现高质量商品图片输出，降低了人工拍摄成本；实现电商文案自动化生成，单环节提效达70%**，大幅缩短新品上市周期。营销投放环节，实现了**广告竞价和投放的自动化托管**，有效提升了广告投放效率与ROAS（投资回报率）；售后环节部署AI邮件回复系统，其中已有30%实现AI自动回复……

**★ 2026 年计划（P41，逐字）：**

> 营销前台将全面落地全球多语言、多平台智能营销系统。深度集成智能价格监控、库存预警、**广告自动投放以及涵盖文、图、视频的全链路AIGC生成流程**，实现一站式智能营销管理。

**→ 这是本分片最直接的一条「同行现状」证据：一家跨境家居上市公司正在把「文、图、视频的全链路 AIGC 生成」铺到全球多语言多平台，而年报里没有任何一句提到生成内容的合规审核。** 对 Momcozy 而言，这既说明**需求真实存在且正在放大**（AI 生成量越大，审核缺口越大），也说明**同行还没公开解决它**。

---

### 2.3 赛维时代（301381.SZ）—— ★ 同行里最接近 Momcozy 规则库的公开披露

**年报「2、公司可能面对的风险及应对措施」（P33–P34）完整枚举，共 7 项：**

1. （1）信息化系统无法及时应对跨境电商行业快速变化的风险
2. （2）未来品牌影响力下降的风险
3. （3）**店铺关闭风险**
4. （4）存货管理风险
5. （5）汇率波动风险
6. （6）信息安全风险
7. （7）全球经济、政治环境变化和贸易摩擦的风险

#### 2.3.1 ★ 平台规则突变风险：逐字原文（P33）

> **（3）店铺关闭风险**
> 公司是一家技术驱动的出口跨境品牌电商，主要产品涵盖服饰配饰品类、非服饰配饰品类两大类，拥有 Coofandy、Ekouaer、Avidlove 等多个品牌。基于构建品牌矩阵及发展多品类业务的战略考虑，公司采用了跨境电商行业较为常见的多账号开店经营模式，在 Amazon、Walmart 等第三方电商平台经营多个店铺。**虽然公司目前采用的多账号经营模式并不违反 Amazon 平台现行有效的禁止性规定且报告期内公司并未因该多账号经营模式受到 Amazon 平台关闭店铺的处罚，但是，公司不能完全排除未来 Amazon 平台以及其他第三方电商平台可能会在未事先与平台卖家进行必要和充分的沟通的情况下，突然改变平台规则或对公司多账号经营模式合规性提出质疑甚至否定公司多账号经营模式的风险**，对多账号开店经营模式进行限制，进而导致公司出现大量第三方电商平台店铺被关闭的情形，则公司可能面临营业收入和利润规模大幅下滑的风险，从而对公司整体经营业绩造成重大不利影响。
> 公司采用多账户经营模式系基于打造品牌矩阵的目的的合理商业需求。未来，公司在实际经营过程中将继续保持遵守诚信经营的基本原则以及亚马逊等第三方平台的平台运营规则，同时**与平台方保持密切沟通，及时与平台方确认对规则及规则变更的理解**。同时，公司将利用品牌在主力线上平台上的市场影响力，进一步深化多平台运营及大力开拓线下市场，以缓解单一平台店铺运营风险。

**可提取的三条事实：**
1. **平台规则是外部变量，且公司明确披露其变动「可能未事先沟通」。** → 规则库必须内置「外部政策变更侦测」而不是假设规则稳定。
2. **公司披露了「报告期内未受处罚」这一具体事实**——这是「未受处罚」的正面陈述，而不是「我们不会被处罚」的保证。
3. **公司的应对是「与平台方保持密切沟通，及时确认对规则及规则变更的理解」**——即**规则解释权在平台，品牌方只能跟进**。

#### 2.3.2 ★★ 「基于大模型的侵权检测平台」：逐字原文（P24）

在「4、研发投入 → 主要研发项目名称」表中，赛维时代列出了一个项目，**这是全部四家公司里唯一一个内容侧自动化审核的公开披露**。逐字：

> **基于大模型的侵权检测平台**
> **项目目的**：旨在利用多模态大模型与计算机视觉技术，构建覆盖**图像、文本、设计元素**的智能侵权检测平台。通过深度学习模型对**产品图片、Listing文案、品牌标识**进行自动化比对与风险识别，**建立侵权风险知识库与预警机制**，实现**新品上架前的侵权风险前置筛查及在售商品的持续监控**，有效降低因知识产权纠纷导致的经营风险与合规成本。
> **项目进展**：已完成
> **拟达到的目标**：建成多模态侵权检测引擎，支持图像相似度比对、文本语义侵权分析、商标与外观专利智能匹配；**构建覆盖主要跨境电商平台的侵权案例知识库，实现侵权风险的自动评级与智能预警**；目标实现**侵权的高检出率与低误报率**，大幅降低侵权事件发生概率。
> **预计对公司未来发展的影响**：该平台将从源头上构建公司知识产权合规的技术护城河，有效防范因侵权导致的**产品下架、店铺封禁**等重大经营风险；在行业层面，基于大模型的侵权检测能力将成为跨境电商企业的核心合规基础设施，助力公司品牌化战略的稳步推进；同时，平台积累的侵权检测数据与模型能力可支撑公司在产品设计环节的合规前置审查，降低研发试错成本，提升新品上市效率。

**★ 把这段话拆成 Momcozy 能直接抄的字段与流程：**

| 赛维原文要素 | 对应的规则库设计要素 |
|---|---|
| 「覆盖**图像、文本、设计元素**」 | **内容类型维度**：三种模态各有独立的检测引擎 |
| 「**产品图片、Listing文案、品牌标识**」 | 检测对象清单（与内容类型正交，是「被检对象」而不是「内容格式」） |
| 「建立**侵权风险知识库**与预警机制」 | 规则库（知识库）+ 预警（触发链路） |
| 「**构建覆盖主要跨境电商平台的侵权案例知识库**」 | **案例库（=错题本）**，且**按平台分区** |
| 「实现侵权风险的**自动评级**与智能预警」 | **严重等级由系统自动判定**，不是人工逐条打标 |
| 「**新品上架前的侵权风险前置筛查**及**在售商品的持续监控**」 | **两个生命周期节点**：上架前（gate）+ 在售中（monitor） |
| 「目标实现侵权的**高检出率与低误报率**」 | **两个度量指标同时约束**（recall 与 precision 并列，不允许用一方换另一方） |
| 「有效防范因侵权导致的**产品下架、店铺封禁**」 | **规则的最终下游后果**被显式写出来（这决定了等级怎么定） |
| 「支撑公司在**产品设计环节**的合规前置审查」 | 规则库的作用点被**前移到设计阶段**，不只在发布前 |

**★ 最重要的一点：「构建覆盖主要跨境电商平台的侵权案例知识库」= 同行已经公开承认「案例库」是合规基础设施，而且是按平台组织的。** 这正是委托方问的「错题本还是规则库」的答案：**两个都要，案例库是知识库的组成部分。**

#### 2.3.3 赛维披露的 AIGC 生产规模（P13、P24）

逐字（P13）：

> 在商品运营环节，公司**应用AIGC技术高效生成商品图片、视频等多元化营销素材**，加快产品全球上新节奏，同时搭建智能营销系统，通过AI实现**广告全链路托管与策略动态优化**，有效提升投放效率与转化效果。

逐字（P13 行业趋势节）：

> 2025年以来，人工智能技术的深度应用有效破解上述困境，其中**AI生成内容（AIGC）在行业内加速普及，AI商品图片生成、AI模特试穿、AI视频广告制作等技术进入规模化应用阶段**，显著降低内容创作成本并缩短制作周期……

逐字（P24 研发项目「Amazon广告投放智能体项目」）：

> 基于大语言模型与强化学习技术，构建面向Amazon平台的广告投放智能体。通过自主决策引擎实现广告竞价策略的动态优化、关键词智能拓展与受众精准定向，**替代传统人工投放模式**，实现从投放计划生成、预算分配、出价调整到效果归因的全流程自动化闭环，大幅降低广告运营的人工依赖，提升投放效率与ROI。

**→ 赛维同时在做「AI 生成素材」和「AI 投放」，且明确说「替代传统人工投放模式」。而它的合规侧只有侵权检测平台。广告文案/素材本身的合规（宣称、功效、绝对化用语等）在年报中没有任何披露。**

#### 2.3.4 赛维对行业合规环境的判断（P18 附近，逐字）

> 与此同时，国内针对跨境电商的财税、外汇、海关等监管体系日趋完善，政策环境更加规范透明；**全球主要消费市场亦不断强化知识产权、产品安全、数据合规、环保标准等方面的监管要求，合规经营已成为企业出海的底线要求与核心竞争力**。行业规范化发展持续挤压不合规经营空间，具备**完善合规体系**、资金实力与品牌运营能力的优质企业竞争优势进一步凸显。

**→ 「合规经营已成为企业出海的底线要求与核心竞争力」是一句可以在内部立项材料里直接引用的行业判断，出自同行年报。**

---

### 2.4 华凯易佰（300592.SZ）—— AI 生成广告创意，未提审核

**★ 推广模式的完整描述（P12，逐字）：**

> （6）推广模式
> 公司构建了以数据驱动为核心、多渠道协同、精准营销的立体化推广体系，在深耕 Amazon、WalMart 等主流平台的站内流量资源的同时，**积极拓展 TikTok 等新兴社交媒体营销渠道**，实现站内站外流量协同，提升品牌曝光度。公司充分利用平台提供的营销工具，包括自动广告、关键词广告、成交型广告、展示型广告等，精准触达目标用户。同时，结合自主研发的广告投放管理系统，对SKU的广告优化进行精细化全自动运营。该系统支持报表获取、关键词选择、竞价优化、预算调控等基础功能；**支持深度接入AI工具，辅助生成优质关键词、品牌广告创意文案、创意图片等**；可根据不同的业务场景和时间阶段（如大促活动、新品上市等），灵活切换流量优先、销量优先、利润优先等投放策略，实现广告投放的智能化决策。

**→ 「辅助生成优质关键词、品牌广告创意文案、创意图片」——AI 生成的三类输出，全是 Momcozy 审查对象的同类物（关键词/文案/图片）。而这句话后面直接接的是「投放策略」，中间没有合规审核环节。**

**华凯易佰的「业务审核」出现在产品与物流侧（P25 与 P26 附近，逐字）：**

> 应用于公司产品系统商品创建通过采样链接，通过接口群一键采集1688平台供应商产品数据。**业务审核后，产品进入样品跟单**，通过接口群，实现样品自动下采购单、批量推送财务系统支付……

> 易佰云物流系统主要功能包括优选服务、轨迹服务、**产品审核**、运费计算工具、物流核销、海外仓进销存、物流方式报价防呆、SU渠道管理、头程订单分摊运费功能计算等……

**→ 「业务审核」和「产品审核」都是**商品与物流**的审核（选品审核、报关要素审核），不是内容审核。**

**华凯易佰的 `处罚` 计数最高（24 次），逐条核对后的构成：**

- 大量来自重组承诺条款，例如（P69 附近，逐字）：
  > 报告期内易佰网络及其子公司**不存在因销售侵犯其他商标、著作权、专利等知识产权的商品而受到第三方电商平台重大处罚的情况**；若易佰网络及其子公司未来因前述情况受到第三方电商平台重大处罚的，其将承担易佰网络及其子公司因此受到的损失。报告期内，易佰网络**不存在因数据泄露或侵犯个人隐私而被平台处罚的情形**……

  > 1、截至本承诺函出具日，易佰网络及其子公司**未曾因通过子公司或以信息授权形式在 eBay、Amazon、AliExpress、Wish 等第三方电商平台开设网店而被第三方电商平台强制关店或处罚的情况**……

- **→ 这些是「未受处罚」的否定式披露 + 兜底承诺，不是处罚记录。** 但值得注意的是：**承诺条款把「知识产权侵权」和「数据/隐私」列为需要单独兜底的平台处罚事由，而「广告/内容」不在其中。** 这与赛维的侵权检测平台形成了互补证据：**跨境电商行业的合规风险认知集中在 IP 和数据，不在内容宣称。**

---

### 2.5 SHEIN / PatPat / Temu(PDD) / 子不语 —— 逐一核实结果

#### 2.5.1 SHEIN —— ★ 任务书假设的「2023 年递交的 F-1 招股书」在公开渠道不存在

**核实方法**：SEC EDGAR 公司名检索 + `data.sec.gov/submissions/CIK0002152230.json`

**实测结果（2026-09-15）：**

- EDGAR 公司名检索 `company=shein`，返回 16 条，**其中唯一的发行人是 `SHEIN Global Holdings Limited/ADR`，CIK `0002152230`，州/国家 `NY`**。
- 该 CIK 的 submissions JSON 中，**`filings.recent.form` 集合 = `{'F-6EF'}`，仅 3 份 F-6EF（2026-09-01、2026-08-31、2026-09-08），无 F-1、无 20-F、无 6-K。**
- `filings.files` 为空数组，说明没有更早的历史分卷。

**判定：❌ 未找到 SHEIN 的公开 F-1 招股说明书。** 合理推断（**标注为推断**）：SHEIN 走的是美国 JOBS Act 允许的**保密递交（confidential submission / draft registration statement）**路径，保密递交的文件在注册生效前不进入 EDGAR 公开检索。**因此任务书里「SHEIN F-1 有大量合规与内容相关披露」这一前提，在本环境无法用一手来源核实。**

**替代尝试与结果**：`www.sheingroup.com` 未测试；`hkexnews.hk` 搜索接口未攻克（见 2.5.4）。**SHEIN 部分按任务书要求写「未找到」，不用行业常识补。**

#### 2.5.2 PatPat —— 未找到

PatPat（深圳盈立科技/Interfocus）**未在任何主要交易所上市**，无年报、无招股书、无 20-F。**❌ 未找到任何公开披露文件。**（本轮未做进一步尝试，因为不存在披露义务就不存在披露文件。）

#### 2.5.3 Temu / 拼多多（PDD Holdings, PDD.O）—— ★ 有，而且是最丰富的广告合规披露

**文件**：FY2025 Form 20-F，2026-04-29 提交，accession `0001104659-26-050727`，primary document `pdd-20251231x20f.htm`
**本地证据**：`_evidence/R6/pdd-20f-2025.htm`（4.33 MB）/ `.txt`（873 KB，已去标签）

**★ 在 Item 3.D 风险因素中，有一条完整的广告法风险。逐字（原文为英文）：**

> **The online marketing services provided by us are subject to complex and evolving advertising laws and regulations across multiple jurisdictions, and any failure to comply with such laws and regulations could materially and adversely affect our business, financial condition and results of operations.**
> We generate a significant amount of our revenues from online marketing services and other related services. Such commercial advertising activities are, or may in the future be, subject to online advertising and other applicable laws and regulations across the jurisdictions in which we operate... See "Item 4. Information on the Company—B. Business Overview—Regulations in the PRC—Regulations Relating to Internet Advertising Business." Under the Administrative Measures on Internet Advertising, our online marketing services and other related services fall within the purview of the PRC Advertising Law. **PRC advertising laws and regulations require advertisers, advertising operators and advertising distributors to ensure that the content of the advertisements they prepare or distribute is fair and accurate and is in full compliance with applicable laws.** The Pinduoduo platform currently generates revenues primarily from online marketing services. **Violation of these laws, rules or regulations may result in penalties, including fines, confiscation of advertising fees and orders to cease dissemination of the advertisements.** In circumstances involving serious violations, the PRC government may **suspend or revoke a violator's business license or license for operating advertising business**.

**★ 逐字（同段，关于广告内容需事先审批）：**

> In addition, **for advertising content related to specific types of products and services, advertisers, advertising operators and advertising distributors must confirm that the advertisers have obtained requisite government approvals**, including the advertiser's operating qualifications, proof of quality inspection of the advertised products, and, **with respect to certain industries, government approval of the content of the advertisement and filing with the local authorities**.

**★ ★ 逐字（同段，平台的内容审核义务）：**

> Pursuant to the Administrative Measures on Internet Advertising, **the Pinduoduo platform is required to take steps to monitor the content of advertisements displayed on the platform.** Complying with PRC requirements on online advertising requires considerable resources and time, and could significantly affect the operation of the Pinduoduo platform, while exposing the Pinduoduo platform...

**★ Item 4.B「Regulations Relating to Internet Advertising Business」逐字（这是对 2023 年《互联网广告管理办法》的英文转述，包含审核制度的法定要求）：**

> On February 25, 2023, the SAMR promulgated the **Administrative Measures for Online Advertising**, which became effective on May 1, 2023. The Interim Measures for the Administration of Internet Advertising were abolished simultaneously. Pursuant to the Administrative Measures for Online Advertising, commercial advertising activities conducted within the territory of the PRC to directly or indirectly promote a product or service **through text, images, audio, video, or any other form**, using any website, web page, web application, or other online media, will be governed by such measures and the Advertising Law. **An advertising agent or advertising publisher must establish, improve and implement systems for the receipt and registration, moderation, file management of their online advertising business.** Also, advertising agents and advertising publishers must cooperate, in accordance with the law, with any investigations of the online advertising industry conducted by the market regulatory authority, and provide truthful, accurate, and complete information in a timely manner if requested to do so.

**★ 同段继续（可识别性、可关闭、禁止欺骗性诱导点击，逐字）：**

> The Administrative Measures for Online Advertising further provides that **an online advertisement must be clearly identifiable as an advertisement**. Any **paid search advertisement** for a product or service must be **prominently labeled as an advertisement** by the publisher of that advertisement to distinguish it from non-paid search results. When publishing an online advertisement as a "pop-up" advertisement or other similar forms, the advertiser and the publisher of the advertisement must **prominently display a "close" button so that the pop-up can be closed in one click**. It is **prohibited to deceive or mislead users into clicking on or browsing an advertisement by using deceptive prompts about system or software updates, fake media control symbols, fake promises of rewards, or any other method** that misleads users into clicking on or browsing advertisements.

**★ 英国 DMCCA 2024（Temu 侧，逐字）：**

> In the United Kingdom, our activities may also be subject to the **Digital Markets, Competition and Consumers Act 2024 ("DMCCA")**, which enhances the enforcement powers of the Competition and Markets Authority ("CMA") in relation to consumer protection and unfair commercial practices, including in the context of online advertising. **The CMA has the authority to directly impose significant fines for breaches, including for misleading advertising, inadequate disclosures, or non-compliant online practices, without the need for court proceedings.**

**★ 第三方商家违规传导至平台（逐字）：**

> ... if the **third-party merchants or vendors whom we work with violate applicable laws and regulations, those violations could also result in liabilities for us and harm our brands**, reputation and business.

**★ 平台被调查的事由清单（逐字，说明「内容/listing/商家行为」已被列为监管关注面）：**

> We may continue to face similar investigations or enforcement actions, or claims and legal proceedings (including putative class actions) in jurisdictions where we operate concerning various aspects of our business, such as user acquisition and retention strategies, pricing and discounting practices, **product listings, third-party merchant conduct**, or the collection or use of consumer data.

#### 2.5.4 子不语（2420.HK）—— 未取到

**已完成的尝试（逐字记录，供后续接手）：**

1. `https://www1.hkexnews.hk/search/prefix.do?callback=cb&lang=EN&type=A&name=2420&market=SEHK` → ✅ 返回 `{"stockId":1000172163,"code":"02420","name":"ZIBUYU"}`
2. `https://www1.hkexnews.hk/search/titleSearchServlet.do?...&stockId=1000172163&fromDate=20230101&toDate=20260915&searchType=1&t1code=-1&t2Gcode=-1&t2code=-1&rowRange=100&lang=EN` → ❌ `{"result":"[]","recordCnt":0}`
3. 换日期格式 `01/01/2023`、`2023-01-01`、`zh` 语言、`searchType=0`、`t1code=40000` → ❌ 全部返回 `result:"[]"` 或 `result:"null"`
4. POST 到 `titleSearchServlet.do` → ❌ HTTP 405 `HTTP method POST is not supported by this URL`
5. `https://www1.hkexnews.hk/listedco/listconews/advancedsearch/search_active_main.aspx` → 返回 9,166 字节，**正文中无任何 `<input name=...>` 表单字段**（疑为框架页，真实表单在 iframe 中）

**判定：❌ 未取到子不语年报。原因：港交所披露易检索接口的参数契约未攻克（缺 `t1code`/`t2Gcode`/`t2code` 的合法枚举值或缺少会话态参数）。** 这是本分片可以明确交给后续接手的一项。

---

### 2.6 横向对比表：四家 A 股公司披露了什么 / 没披露什么

| 项目 | 安克创新 | 致欧科技 | 赛维时代 | 华凯易佰 |
|---|---|---|---|---|
| 风险因素条数 | 4 | 4 | 7 | （含重组承诺，未逐条枚举） |
| 是否有「内容/广告合规」风险条目 | ❌ | ❌ | ❌ | ❌ |
| 是否有「平台规则突变」风险条目 | ❌ | ❌ | ✅ P33 店铺关闭风险 | ❌ |
| 是否披露受平台处罚（广告/内容事由） | ❌ | ❌ | ❌（仅披露「未受处罚」） | ❌（仅承诺兜底） |
| 是否披露 AI 生成营销素材 | 未查到 | ✅ P17 AIGC2.0 图库 + 文案 | ✅ P13 AIGC 图片/视频 | ✅ P12 关键词/创意文案/创意图片 |
| 是否披露 AI 内容审核 | ❌ | ❌（AI 视觉只用于质检图片） | ✅ **P24 侵权检测平台** | ❌ |
| 是否披露案例/知识库 | ❌ | ❌ | ✅ **P24 侵权案例知识库 + 风险知识库** | ❌ |
| 是否披露自动评级 | 供应链侧 ✅ P61（供应商风险分级） | ❌ | ✅ **P24 侵权风险自动评级** | ❌ |
| 是否披露量化扣分制 | ✅ **P61 供应商 128 项检查 + 量化扣分** | ❌ | ❌ | ❌ |
| 是否披露等级→处置映射 | ✅ **P61 整改/跟进审核/暂停/终止** | ❌ | ❌ | ❌ |
| 是否披露度量指标 | ❌ | ❌ | ✅ **P24 高检出率 + 低误报率** | ❌ |

### 2.7 ★ 「都查不到」这个结论本身，以及为什么

**事实陈述：**

1. 四家 A 股跨境电商上市公司 2025 年报中，**「内容审核」出现 0 次**。
2. 安克创新 2023 / 2024 / 2025 三份年报中，**「广告」出现 0 次**。
3. 四家的风险因素章节中，**没有任何一家把「广告宣传合规」列为风险**。

**为什么这不是「调研没找到」，而是三条可解释的结构性原因（我的判断，明确标注为判断）：**

**原因一：披露义务由「重大性」触发，而广告合规对品牌方不是重大风险。**
A 股年报「风险因素」章节的编写标准是「可能对经营业绩产生重大不利影响」。对安克/致欧/赛维/华凯这类公司：
- 广告费是**销售费用**科目（赛维 2025 年报显示销售费用含「销售平台费用、销售宣传推广费用」；致欧 2025 年报「广告费」科目期末 4.46 亿元，同比从 3.13 亿元增长）
- 一条广告文案违规的后果是**罚款或平台下架**，金额相对于营收不构成「重大」
- 所以**理性披露策略就是不写**。这不代表没做，代表不值得写。

**原因二：广告合规只有在下述两种情况下才会进年报：**
- **(a) 广告是收入项** → PDD 就是这种情况。它卖广告位，所以要审别人的广告，所以《互联网广告管理办法》对它施加了法定审核义务，所以它必须在 20-F 里披露整段。**逐字证据见 2.5.3。**
- **(b) 平台是内容审核的义务主体** → 同样是 PDD。
- **Momcozy 两条都不满足**：它是广告主（买方）+ 内容生产方。**所以「照同行年报找内容治理 SOP」这条路在方法论上就是错的。**

**原因三：真正在做内容治理的公司，把这件事藏在「研发投入」而不是「风险因素」里。**
赛维时代的侵权检测平台披露在**「4、研发投入 → 主要研发项目名称」表**里——这是一个**技术能力披露位**，不是风险披露位。**这给出了找同行做法的正确检索路径：不看「风险因素」章节，要看「研发投入」「管理层讨论与分析 → 经营模式/技术能力」章节。**

**→ 「都查不到」的正确解读：**
> 公开披露渠道能证明的是「内容合规不是这几家公司的重大风险」；它**不能**证明「这几家公司没有内容审核流程」。想获得流程证据，必须换渠道（岗位 JD、供应商/客户尽调材料、平台侧卖家评级、行业标准采用声明），而**岗位 JD 与平台侧文档恰好是本环境抓不到的**（见第 3、5 节与缺口清单）。**这个证据缺口是本次调研真实存在的边界，应当如实报告给委托方，而不是用行业常识填空。**

---

## 3. 岗位定义：流程的化石

### 3.1 采集尝试与结果（全部失败，逐项记录）

| 渠道 | 尝试的 URL | 实测结果 |
|---|---|---|
| LinkedIn Jobs | `https://www.linkedin.com/jobs/search?keywords=Content%20Reviewer` | **HTTP 451**（Unavailable For Legal Reasons），返回 0 字节 |
| Boss 直聘 | `https://www.zhipin.com/web/geek/job?query=内容审核&city=100010000` | HTTP 200 但仅 **9,204 字节**，为 JS 壳；正文无「内容审核」「岗位职责」 |
| 猎聘 | `https://www.liepin.com/zhaopin/?key=内容审核` | HTTP 200 但仅 **35,483 字节**，为 JS 壳；正文无「岗位职责」 |

**判定：❌ 本环境无法取得任何跨境电商公司的内容审核/合规岗位 JD 原文。**
原因：三个平台都是客户端渲染（CSR）单页应用，且都有反爬；本环境**没有可用的 JS 渲染能力**（浏览器桥接工具返回 `The controlled tab was closed. Select the current page in the side panel before retrying.`，`r.jina.ai` 等渲染代理在 `000` 不可达）。**按任务书要求，此项写「未找到」，不用行业常识补。**

### 3.2 替代证据：从年报里能提取的「职能定义碎片」

虽然没有 JD，年报里仍有三类可用的职能证据：

**（a）岗位类型的间接证据 —— 广告投放岗已在被 AI 替代**
赛维时代 2025 年报 P24 逐字：

> ……**替代传统人工投放模式**，实现从投放计划生成、预算分配、出价调整到效果归因的全流程自动化闭环，**大幅降低广告运营的人工依赖**……在效率层面，**可大规模缩减广告运营人力投入**，支撑更多 SKU 和站点的精细化投放

**→ 含义：投放执行岗在缩编，但合规审查岗的披露为零。** 这是一个组织信号：**AI 把「生成」和「投放」自动化了，但「审查」这一环没有被自动化，也没有被显式补人。**

**（b）职能分工的间接证据 —— 审核职能挂在哪个部门**
华凯易佰 P25/P26 逐字：审核出现在「产品系统」（业务审核）、「易佰云物流系统」（产品审核）、「质控」。**→ 在这些公司里，「审核」是业务/供应链职能，不是独立的合规职能。**

**（c）组织结构的间接证据 —— 治理架构里没有内容合规位**
四家年报的「公司治理」章节逐条列出：股东会、董事会（下设战略/薪酬与考核/审计/提名委员会）、独立董事、监事会（2025 年安克按新《公司法》取消监事会，职权由审计委员会承接）、信息披露、利益相关者。**没有任何一家设置「合规委员会」或在董事会层面设内容/广告合规职责。** 安克 2025 年报 P43 逐字：

> 报告期内，公司董事会下设的**审计、提名、薪酬与考核、战略**四个专门委员会均按照既定职责规范运作

### 3.3 可用的职能定义（来自行业标准方，而非 JD）

替代 JD 的最强一手材料是 **IAB Tech Lab 实现指南里对「谁负责什么」的分工定义**。来源：`implementation.md` 第 396–415 行，本地 `_evidence/R6/iab-taxonomies-implementation.md`

**买方（品牌方）的职责，逐字（第 396–402 行）：**

> **Content Taxonomy Usage Guidance for Buyers**
> **_Brand safety:_**
> Buyers should **familiarize themselves with the GARM/4A's APB Brand Safety & Suitability Framework** and the Tech Lab Content Taxonomy. They should also **understand the risk/tolerance levels they are comfortable with by looking at examples of the various suitability examples**. They should then **work with their DSPs and ad verification vendors to ensure that their goals are met by specifying the risk tolerance goals using the Content Taxonomy**.

**→ 这就是「品牌方内容合规岗」的行业标准职责定义，共三个动作：**
1. **读框架**（GARM + Content Taxonomy）
2. **定自己的风险容忍度**（by looking at examples——**从案例反推容忍度，而不是从原则推导**）
3. **把容忍度以标准 ID 的形式写进采购/投放配置**（specifying the risk tolerance goals using the Content Taxonomy）

**验证方（技术执行方）的职责，逐字（第 404–415 行）：**

> **Implementation Guidance for Ad Verification Vendors**
> Ad verification vendors are likely to be the main implementers of the brand safety floor and suitability. As such, the recommendations provided here would also apply to any other audience implementing brand safety checks.
> Recommendations:
> - Ad verification vendors should **apply any relevant Content Taxonomy categories** to a given piece of content, and/or any of the 11 brand safety categories
> - Ad Verification vendors should **apply a risk level whenever any of the 11 core brand safety category labels are applied** to a piece of content.
> - **It is possible to have multiple brand safety category labels (and appropriate risk levels with each brand safety category label) associated with a given piece of content.**
> - As of v2.2, ad verification vendors **are not required to apply risk levels to topic categories other than the 11 core Brand Safety categories** in the Content Taxonomy.

**→ 这里有一条极其重要的边界规则（第 3 条）：同一条内容可以有多个类别标签，每个标签各带自己的风险等级。** 这与 1.4.2 的「取最高档」聚合并不矛盾——**存储是多标签多等级，对外输出的单一等级是 max 聚合的结果**。**Momcozy 的规则表现在只存一个 `风险等级` 字段（一条规则一个等级），这是存储层与聚合层的混淆。** 见第 6 节。

**职责分工的第三块证据：Zefr 文章里对「top down / bottom up」的分工描述，逐字：**

> ...**the existing GARM standard takes an initial top down approach by working with the buy-side to create brand suitability definitions; and while this is an important first step it is equally important to support the sell-side by providing content examples that match these definitions.**

---

## 4. 品牌保护与内容合规服务商的公开方法论

### 4.1 可达性实测

| 服务商 | 域名 | 结果 |
|---|---|---|
| BrandShield | `brandshield.com` | ✅ 200，且 SSR 可见正文 |
| Red Points | `redpoints.com` | ❌ 403 |
| CounterFind | `counterfind.com` | ✅ 200（仅博客与产品页，未含方法论长文） |
| MarkMonitor | `markmonitor.com` | ✅ 200（未定位到方法论文档） |
| Deloitte / PwC / Accenture | — | ✅ 域名可达（未定位到内容/广告合规白皮书） |
| McKinsey | `mckinsey.com` | ❌ 连接失败（exit 92） |

### 4.2 BrandShield 的公开方法论（逐字提取）

**来源**：《Online Brand Protection: The Complete 2026 Guide》，作者 Oren Todoros（BrandShield），发布日期 **August 24, 2026**
**URL**：<https://www.brandshield.com/blog/online-brand-protection-the-complete-2026-guide/>
**本地证据**：`_evidence/R6/brandshield-guide.html` / `.txt`
**⚠️ 来源性质声明**：这是**供应商自发布的营销内容**，文中明确承认其平台对比「**are not based on controlled head-to-head testing**」。以下只提取其**流程描述**部分，不采信其产品对比结论。

**★ 完整生命周期定义（逐字）：**

> Online brand protection is the discipline of **detecting, prioritizing, and removing** digital threats that misuse a company's identity, intellectual property, products, or customer trust. It combines **monitoring with investigation and enforcement** across websites, marketplaces, social media, domains, ads, apps, and other external channels.

**★ 三个概念的区分（逐字，这段对「规则库 vs 错题本」的边界很有用）：**

> The key word is **protection**. **Brand monitoring and brand protection are related, but they are not the same thing. Brand monitoring focuses on visibility.** It identifies mentions, listings, domains, accounts, or other digital assets that may relate to your company. **Online brand protection goes further. It assesses whether a finding is harmful, gathers evidence, prioritizes the risk, and takes action when enforcement is justified.** Trademark registration is different again...

**→ 这意味着「监控（发现）」与「保护（判定+取证+定级+处置）」是两个产品层。Momcozy 现在做的「审查 Agent」如果只做「命中关键词」，就在第一层；要进第二层必须补「是否真的有害」「取证」「定级」「处置」。**

**★ 规则库的组织方式（逐字）：**

> Good detection should find more than exact matches. For example, criminals may **distort a logo, alter a product image, misspell a domain, or use a related phrase** rather than the exact trademark.

**★ 误报的处理（逐字，这是直接回答任务书问题的一段）：**

> **However, more findings do not automatically mean better protection. False positives and low-value alerts create work for legal, security, and brand teams.**

**★ 威胁聚类（逐字）：**

> **Threat clustering links apparently separate assets so teams can identify the campaign or operator behind them. Instead of treating ten seller accounts and five domains as fifteen unrelated incidents, clustering looks for shared images, infrastructure, contact details, account...**

**★ 人机分工（逐字，这是最直接的一段）：**

> **Automation can speed up repetitive actions. However, experienced analysts remain useful when cases involve unclear rights, regional differences, evasive operators, or repeated escalation.**

→ **四条「必须给人」的条件：权属不清 / 地区差异 / 规避型对手 / 反复升级。** 这是一份可直接写进 SOP 的人工介入判据，比「模糊的给人工」具体得多。

**★ 定级与处置（逐字）：**

> Detection without remediation leaves the burden on your internal team. Look for clear **enforcement workflows, evidence capture, status tracking, escalation paths, and human assistance for harder cases**.

> Evidence matters. Strong cases usually include the **relevant URL, screenshots, timestamps, account information, proof of rights, and a clear explanation of the violation**.

→ **「举证包」的六个字段：URL / 截图 / 时间戳 / 账号信息 / 权属证明 / 违规说明。** 这是一条可以直接抄的字段清单。

**★ ★ 度量什么（逐字，这是任务书第四问「度量什么」的行业答案）：**

> **4. What should reporting measure?**
> Reporting should show whether the company is **reducing meaningful risk, not simply generating more alerts**. Useful measures include:
> - **Validated threats**
> - **Threats by type and channel**
> - **Severity and customer exposure**
> - **Takedown requests submitted**
> - **Takedown or enforcement success**
> - **Time to action**
> - **Time to removal**
> - **Repeat offenders**
> - **Recurring assets after enforcement**
> - **Connected threats removed as part of one campaign**

**→ 十个指标里，与 Momcozy 内容审查直接对应的是前六个：**
`Validated threats`（经核实为真的命中数，不是命中总数）→ `Threats by type and channel`（按类型×渠道拆分）→ `Severity and customer exposure`（严重度 × 受众暴露）→ `Time to action`（从发现到动作的时长）→ `Time to removal`（从动作到下线的时长）→ `Repeat offenders`（重复违规者）。

**注意第一个指标：`Validated threats`。** 这是一个**把「命中」与「确认」分开**的指标设计——**直接对应 Momcozy 现在最大的口径问题：21/21 条规则全部声明「自动可检测」，没有「经人工确认为真」这一层计数。** 见第 6 节。

**★ 平台评估的七维度（逐字，可作为 Momcozy 选型工具时的对照表）：**

> - **Coverage breadth**: How many relevant channel types the platform protects.
> - **Detection accuracy**: Evidence of AI, visual detection, analyst validation, or other methods designed to reduce noise.
> - **Takedown speed & success**
> - **Automation**: Ability to automate detection, prioritization, enforcement, and recurring workflows.
> - **Integrations**: APIs and connections with enterprise security, workflow, or platform ecosystem
> - **Reporting**: Dashboards, case history, analytics, exports, and outcome measurement.
> - **Support**: Availability of managed services, analysts, IP specialists, or disruption teams.

**★ 验收方法（逐字，可抄）：**

> A **pilot or proof of concept** can be more useful than a polished demonstration. **Give each shortlisted provider the same brands, trademarks, products, and known threats. Then compare discovery quality, false positives, prioritization, usability, and enforcement outcomes.**

**→ 这就是 Golden Dataset / 对照评测的思想，而且给出了「同一批已知样本喂给所有候选方案再比」的具体做法。与 IAB 官方标注集的用法（1.4.2）完全一致。**

---

## 5. 跨境平台侧的合规运营实践

### 5.1 可达性实测（这是本分片最大的证据缺口）

| 目标 | URL | 结果 |
|---|---|---|
| Amazon Seller Central Account Health 帮助页 | `sellercentral.amazon.com/help/hub/reference/external/G200370560` | ⚠️ HTTP 200 但**纯 SPA**：169,425 字节 HTML 中，正文区域无服务端渲染内容；`violation` 仅在反爬脚本里出现 2 次；无 `__NEXT_DATA__` / `INITIAL_DATA` 等注水载荷 |
| Amazon 帮助页 API 猜测 | `/help/hub/api/reference/external/G200370560` 等 3 条 | ❌ 全部返回同一个 SPA 外壳（135,9xx 字节），不是 JSON API |
| Amazon Brand Registry 公开页 | `brandservices.amazon.com/protection` | ⚠️ HTTP 200，但正文同样 JS 渲染（仅导航 SSR） |
| Amazon Transparency 公开页 | `brandservices.amazon.com/transparency` | ⚠️ 同上 |
| Amazon 举报违规页 | `brandservices.amazon.com/reportviolation` | ⚠️ 同上 |
| **Amazon Ads 品牌安全指南** | `advertising.amazon.com/library/guides/brand-safety` | ✅ **SSR 可用，已取得全文** |
| Amazon Ads 广告库存指南 | `advertising.amazon.com/library/guides/ad-inventory` | ✅ SSR 可用（内容为广告库存类型学，非内容政策） |
| TikTok Shop 美国卖家中心 | `seller-us.tiktok.com/` | ❌ 连接失败（000） |
| TikTok Shop 全球卖家中心 | `seller.tiktokglobalshop.com/` | ⚠️ HTTP 200 但正文中无 `polic`/`rule`/`violat` 类链接 |
| TikTok Shop 合作方门户 | `partner.tiktokshop.com/` | ⚠️ HTTP 200，正文中无相关政策文档链接 |
| TikTok 主站（社区准则） | `www.tiktok.com/` | ❌ 连接失败（000） |
| Temu 卖家中心 | `seller.temu.com/` | ⚠️ HTTP 200（176 KB）但为 SPA，未取到违规处罚阶梯 |
| Temu 主站 | `www.temu.com/` | ⚠️ HTTP 200 但仅 2,889 字节（跳转壳） |

**判定：❌ 任务书第五项要求的「Amazon Account Health 机制官方文档原文」「TikTok Shop / Temu 违规处罚阶梯原文表格」，在本环境无法取得。** 原因是这三家平台的全部卖家帮助内容都是客户端渲染，而本环境的浏览器桥接不可用（`The controlled tab was closed`）。**按任务书要求写「未核实」，不用行业常识补。**

### 5.2 可取到的一手证据：Amazon Ads 对 Brand Safety 的官方定义与操作流程

**来源**：Amazon Ads 官方指南《什么是品牌安全？定义、示例及其运作方式》
**URL**：<https://advertising.amazon.com/library/guides/brand-safety>
**本地证据**：`_evidence/R6/amazon-ads-brand-safety.html` / `.txt`（页面按语言返回中文版；抓取 2026-09-15）

**★ 官方定义（逐字）：**

> 品牌安全措施可以降低与不符合品牌安全的内容相关的风险，有助于保护品牌的声誉。
> **品牌安全性是指避免不当内容，而对于哪些内容属于不当内容，所有受众通常都有一致的看法。另一方面，品牌适用性对于单个品牌而言是与众不同的。** 品牌适用性是指将您的广告与符合您的特定价值观、身份、风格和其他主观特征的内容相匹配。
> 例如，**素食品牌可能不会将有关狩猎和钓鱼的应用视为适合其广告的广告位，尽管狩猎和钓鱼并不是每个人都反感的话题。** 语气非常随意和幽默的网站可能不适合品牌声音比较严肃的公司。
> **品牌安全是指保护您的品牌免受损害。品牌适用性是指通过了解哪些类型的内容适合您的品牌来支持并树立您的特定品牌形象，同时避免与不符合您的品牌的内容产生关联。**

**★ 官方四步操作流程（逐字）：**

> 1. **确定您的品牌故事和价值观**：要在投放广告时保护您的品牌，首先要明确什么样的内容适合或不适合自己的品牌，这一点很重要。例如，与酒相关的内容可能不适合某些品牌，但酒类品牌在推广商品时可能会使用这类内容。**确定自己关注的重点有助于将精力集中在对品牌最重要的事务上。**
> 2. **选择成熟的程序化提供商**：要降低程序化广告带来的风险，关键是要选择成熟的需求方平台 (DSP)。……您的广告科技 (Adtech) 提供商可以帮助您保护您的品牌，您可以**咨询他们具体采取哪些措施来确保品牌安全性**。
> 3. **利用"包含"列表和"排除"列表**：使用可用的投放选项来确定要包含以及要排除的广告资源。"包含"列表中可以包含受信任的应用和网站，或者与您的品牌相关的特定主题和关键词。使用"排除"列表可以防止您的广告在用户搜索不可信的域名或不当关键词时展示。
> 4. **把品牌安全性放在首位**：保护品牌安全性不是一件一劳永逸的事情，而是一个**持续的过程**。品牌必须**定期评估**可能威胁其品牌安全性的因素。寻找能够提供透明度和严格质量标准的技术提供商，因为他们会自动阻止对品牌安全性不利的内容。请**不断更新"包含"列表和"排除"列表**。**监控您的品牌认知度并分析受众**，以便确保您了解受众对您的品牌声誉和品牌价值观的看法。在品牌安全方面，应时常保持警惕。

**★ 这一步里藏着 Momcozy 可以直接抄的两条：**
- **第 1 步的产出物是「品牌关注重点清单」**，而不是规则条目。→ 说明规则库的上游应该是「品牌价值主张」，不是「违禁词表」。
- **第 3 步的产出物是两份清单：包含列表 + 排除列表。** → 这是一个**双名单结构**。Momcozy 现在只有「规则（黑）」+「安全词白名单」，等价于「排除列表 + 少量包含」。**但他们没有一份「包含列表」（授权可用的话术库 / 可信表达模板）**，而赛维的年报里反过来也有这个问题。

同一页面还指向两份 Amazon DSP 政策文档（正文只给了名称与链接文案，未展开）：
- 「亚马逊 DSP 广告库存政策」——原文引用文案：`亚马逊广告致力于通过亚马逊 DSP 为客户提供优质广告库存。阅读完整的亚马逊 DSP 广告库存政策。`
- 「亚马逊 DSP 内容邻接政策」——原文引用文案：`亚马逊采取各种措施来防止您的广告出现在包含敏感内容、商品和服务的网页、应用程序、流媒体电视以及播客中。阅读完整的亚马逊 DSP 内容邻接政策。`

**→ 「内容邻接政策（Content Adjacency Policy）」这个命名本身有价值：它把「广告旁边是什么内容」显式命名为一类政策对象，与「广告自身内容是否合规」并列。** Momcozy 现在只有「广告自身内容」一条轴，没有「内容邻接（我的内容出现在什么语境中）」这条轴。

### 5.3 「违规类型 → 处罚等级」显式化：本环境能确证的只有法定侧

平台侧的处罚阶梯表未取到。但 **PDD 20-F 提供了中国法定侧的「违规 → 处罚」阶梯**（逐字见 2.5.3），可整理为：

| 违规情形 | 法定后果（PDD 20-F 转述原文） |
|---|---|
| 广告内容不真实、不准确、不符合法律 | `penalties, including fines, confiscation of advertising fees and orders to cease dissemination of the advertisements` |
| 严重违规（serious violations） | `the PRC government may suspend or revoke a violator's business license or license for operating advertising business` |
| 未建立/未落实广告业务的承接登记、审核、档案管理制度 | （法定要求本身）`An advertising agent or advertising publisher must establish, improve and implement systems for the receipt and registration, **moderation**, file management of their online advertising business.` |
| 广告不可识别 / 付费搜索广告未标注 | `an online advertisement must be clearly identifiable as an advertisement`；`Any paid search advertisement ... must be prominently labeled as an advertisement` |
| 弹窗无一键关闭 | `must prominently display a "close" button so that the pop-up can be closed in one click` |
| 欺骗性诱导点击 | `It is prohibited to deceive or mislead users into clicking on or browsing an advertisement by using deceptive prompts about system or software updates, fake media control symbols, fake promises of rewards, or any other method` |
| 英国：误导性广告 / 披露不充分 / 不合规在线做法 | `The CMA has the authority to directly impose significant fines for breaches ... without the need for court proceedings` |

**→ 这张表的价值：它是「等级 → 后果」的**法定**参照，可以用于给 Momcozy 的 H/M/U 三族标定「后果严重性」，而不是凭内部感觉分档。**

---
## 6. 对 Momcozy 的直接含义

> 本节把前面五节的发现翻译成对 Momcozy 规则库的**具体字段与流程建议**。
> 凡是「我想的建议」都明确标为【建议】；凡是「有证据支撑的结论」标为【证据】。

### 6.1 维度模型：Momcozy 的「国家 × 品类 × 平台 × 内容类型」不是行业答案

**【证据】IAB Content Taxonomy 用什么维度组织？**

| 层 | 内容 | 证据 |
|---|---|---|
| 第一层：主题（aboutness） | 一棵 4 层树，37 个顶层、704 个节点，**只有一条轴：主题/体裁** | 3.1 TSV 实测 |
| 第二层：正交属性（vectors） | `Content Environment`（平台，8 值）/ `Content Purpose` / `Content Source` / `Content Form Factor`（内容类型，7+ 值）/ `Brand Suitability and Risk`（风险级，4 值）/ `*Content Language Extension` → ISO-639-1 / `*Content Source Geo Extension` → ISO-3166-1 | 3.0 Descriptive Vectors TSV 实测 |
| 组合规则 | 主题标签数组 + 属性标签数组；**风险级动态挂在主题上**（"allowing 'risk' to be associated with a 'topic' dynamically"） | implementation.md 第 303、384 行 |

**【证据】GARM 框架用什么维度组织？**

| 层 | 内容 |
|---|---|
| 类别轴 | **11 个固定大类**（Adult & Explicit Sexual Content … Terrorism） |
| 严重度轴 | **4 档**（Floor / High / Medium / Low），实践再加 `minimal` = 5 档序数刻度 |
| 组合方式 | 11 × 4 的**指导矩阵**（每格一段指导文本），但**对外输出时聚合成单一等级**：`Of the 11 GARM categories, the highest label applicable` |

**与 Momcozy 假设的「国家 × 品类 × 平台 × 内容类型」逐项对比：**

| Momcozy 的轴 | 行业标准里有吗 | 行业标准放在哪 | 关键差别 |
|---|---|---|---|
| **国家** | ✅ 有 | `*Content Source Geo Extension` → **外挂 ISO-3166-1-alpha-3**，不自造枚举 | **不自建国家字典**，直接引用国际标准码 |
| **品类** | ✅ 有（但形状不同） | aboutness 树里的 `Shopping` 等分支；**不是顶层轴** | 品类是**主题树的一个分支**，不是与主题并列的轴 |
| **平台** | ✅ 有 | `Content Environment` 向量（Email/Forum-Community/Marketplace-eCommerce/Search Engine-Listings/Social/Utility/Voice/General） | **平台的枚举是「内容所处的环境类型」，不是「品牌名」**——不是 "Amazon/Meta/Google"，而是 "Marketplace/eCommerce/Social/Search Engine" |
| **内容类型** | ✅ 有 | `Content Form Factor` 向量（Textual/Images-Galleries/Video/Audio/Mixed/Game/VR-AR） | 同样是**格式类型**，不是「主图/A+/短视频/帖子」这类业务名 |
| **（行业标准多出来的）** | ✅ | **`Content Source`（谁生产的：Professionally Produced / User Generated / Aggregated-Curated）** | ★ Momcozy **完全没有这条轴**。而 AI 生成内容（AIGC）在这条轴上恰恰是**最危险的新取值**——赛维、致欧、华凯三家都在规模化 AIGC（第 2 节），行业标准却还没有官方取值给它 |
| **（行业标准多出来的）** | ✅ | **`Content Purpose`（内容目的：Conversational / Entertainment / Informational→News-Opinion-Review / Commerce）** | ★ Momcozy **没有这条轴**。同一条文案，出现在「商品详情页（Commerce）」与「社媒知识科普（Informational）」里，合规判定应该不同 |
| **（行业标准多出来的）** | ✅ | **`Brand Suitability and Risk` 独立成向量**，而不是当成规则的一个字段 | ★ 这是最根本的差别，见 6.1.1 |
| **（行业标准少了的）** | ❌ | 行业标准**没有**独立的法律辖区轴（国家 ≠ 法律辖区）、**没有**品牌自身价值观轴（那被明确划给「品牌自己定义」） | GARM 明说框架是让品牌「independent development of their own bespoke, brand-specific safety frameworks」——**品牌自身调性这一层，行业标准故意不做，留给你自己做** |

**★ 6.1.1 结论：正确分层不是「四维笛卡尔积」，而是三层**

```
第 1 层｜主题分类（aboutness）—— 一条轴，一棵树
        内容在讲什么：品类 / 场景 / 话题
        （Momcozy 对应物：吸奶器、母乳喂养、育儿、产后恢复…）

第 2 层｜正交属性（vectors）—— 多条轴，互不相乘
        内容所处的环境：平台类型（Content Environment）
        内容的格式：Content Form Factor
        内容的来源：Content Source（含 AIGC）
        内容的目的：Content Purpose
        语种：ISO-639-1
        国家/地区：ISO-3166-1
        （Momcozy 对应物：Meta/Google/TikTok 渠道 + 图文/视频 + 自产/UGC/达人生成 + 详情页/社媒/广告 + 5 个语种 + 6 个投放地区）

第 3 层｜风险级 —— 一个动态属性，挂在第 1 层节点上
        Floor / High / Medium / Low (+ minimal)
        （Momcozy 对应物：H / M / U / 合规 四档）
```

**【建议】具体改法（字段级）：**

1. **不要把「国家 × 品类 × 平台 × 内容类型」做成规则编号的前缀空间。** 如果每条规则都要声明自己适用于哪个国家×品类×平台×内容类型的组合，21 条规则会很快膨胀到几百条，而且必然出现「同一条规则被复制成 12 份只在平台上不同」的情况——**这正是 `research/distill/cross-cutting-findings.md` 反模式清单里「同一维度多套实现」的成因。**
2. **把现有 21 条规则拆成两半**：
   - **主题侧**（讲什么）：如「吸奶器功效宣称」「母乳替代/喂养方式比较」→ 归入主题树
   - **属性侧**（在哪讲、怎么讲）：如「绝对化用语」「医疗功效暗示」「比较广告」→ 归入向量，**与主题解耦**
3. **`适用产品` 字段全部写死为五个型号的做法应当废止（现有 21/21 条如此）。** 换成：
   - `applies_to_category`（主题节点 ID，可多值）
   - `applies_to_environment`（平台类型枚举）
   - `applies_to_form_factor`（内容格式枚举）
   - `applies_to_language` / `applies_to_geo`（**用 ISO 码，不自建**）
4. **新增 `content_source` 字段，取值至少包含 `AIGC-generated`。** 这是本分片发现的最大的模型缺口：**三家同行在规模化 AIGC 生产，行业标准里还没有对应的风险取值，Momcozy 如果要建规则库，这一格是空白市场。**
5. **风险级不要存成规则的一个属性字段，要存成「判定结果的属性」。** 见 6.2。

### 6.2 「地板」概念对 H 类红线规则的启发

**【证据】Floor 与其他三档在结构上不是同一量纲：**

- 三档（Low/Medium/High）解决「**同一个主题，不同品牌的容忍度不同**」。IAB 原文的目标之一是 "to **allow content that might otherwise have been blanket marked as unsafe to be monetized by allowing brands with the right risk tolerance to buy such inventory**."
- Floor 解决「**不管什么品牌，都不该出现**」。Amit Shetty 原文："publishers can monetize more content that is **not in the 'floor' category**"。
- Amazon Ads 的官方转述更直白：「**品牌安全性是指避免不当内容，而对于哪些内容属于不当内容，所有受众通常都有一致的看法**；另一方面，品牌适用性对于单个品牌而言是与众不同的。」

**→ 判据：如果一个判断结论会因为「不同品牌的容忍度不同」而改变，它就不属于 Floor；如果它不因品牌而改变，它就不该和三档混在同一张表里。**

**Momcozy 现在的 H/M/U 三族 vs Floor/High/Medium 的层级设计，差别在五点：**

| # | 差别 | Momcozy 现状（来自 `PRD/内容治理需求文档.md`，A 节） | 行业标准做法 | 建议 |
|---|---|---|---|---|
| 1 | **H 族与 M/U 族结构同构** | 同一张表、同一套 12 字段、同一个 `风险等级` 四档枚举；H01–H09 与 M01–M07、U01–U04 只是 `边界类型` 字段取值不同 | Floor 在**语义上不是「最严的一档」，而是「没有偏好参数」的一档** | 让 H 族**减少字段**而不是增加字段：H 族不需要「豁免词」「适用产品」「语境守卫」这类议价参数 |
| 2 | **H 族的「红线」没有排除机制** | H 族与其他族一样有 `豁免词` 字段（全表 5 条带豁免词） | Floor 的判定是 exclude，无「看情况」 | 【建议】H 族**禁用 `豁免词` 字段**；若某条规则真的需要豁免，它就**不是 H**，应该降到 M |
| 3 | **21/21 全部「自动可检测」** | `判断方式` 21 条全部为 `自动可检测` | IAB 官方标注集里 `floor` 在 5,330 条样本中出现 **0 次**——**Floor 是稀有事件，不该是常态** | 【建议】H 族计入「自动检出即阻断」，不许进人工队列；M/U 族才进人工队列。**更重要的是：如果 21 条全部自动可检测，说明现在没有「需要人判断」的规则，这与 U 族（人工复核灰规则）的定义自相矛盾**——见 6.5 |
| 4 | **等级 → 处置没有显式映射** | 规则表里 `风险等级` 是一列，但**没有「该等级对应什么动作」的字段** | 安克 P61 的同行做法：「按照**风险等级**采取要求整改、跟进审核、暂停合作直至终止合作等处置措施」——**等级后面永远跟着动作** | 【建议】增加 `action_type` 字段。参照 `S1-06`/`S3-09`（9 种 `actionType` 与自动/人工分流）的已有内部资产 |
| 5 | **「合规」与三个风险档混在同一枚举** | `风险等级` 四档 = `高危` / `审慎` / `待复核` / `合规` | GARM 的刻度是 **5 档纯风险序数**：`minimal < low < medium < high < floor`，「无风险」是最底档 `minimal`，不是「没命中」的默认值 | 【建议】改成**两个字段**：`severity`（5 档序数，含 `minimal`）+ `status`（`待复核`/`已确认`/`已豁免`）。**把「等级」和「状态」分开，现在的四档是这两种东西的混合。** |

**★ 最关键的一条启发（来自 1.4.2 的聚合规则）：**

> `label` - Of the 11 GARM categories, **the highest label applicable**. For example if a video is medium for adult content, high for weapons, minimal for everything else then the label would be high.

**→ 存储层：一条内容可以同时命中多个类别，每个类别各有自己的等级（IAB 实现指南第 3 条也明确 "It is possible to have multiple brand safety category labels ... associated with a given piece of content"）。**
**→ 输出层：对外的单一等级 = max 聚合。**

**Momcozy 现在把 `风险等级` 存在规则行上（一条规则一个等级），这会导致两个问题：**
1. **无法回答「这一条内容整体有多危险」**——因为等级挂在规则上，不挂在内容上。
2. **命中多条规则时无法排序。** 他们的 291 条广告明细里有 `风险等级 | 命中规则 | 命中片段`，说明**已经有多命中现象**，但没有定义「同时命中 H03 和 M05 时算几级」。

**【建议】新增一张「判定结果表」，与规则表分离：**

```
判定结果（content_finding）
  finding_id
  content_id            # 被审的那条内容
  matched_rule_ids[]     # 命中的所有规则（多值）
  per_category_severity  # 每个类别各自的等级
  overall_severity       # = max(per_category_severity)，与 GARM 一致
  action_type            # 由 overall_severity 映射，不是人工选
  status                 # 待复核 / 已确认 / 已豁免（与 severity 分离）
  evidence               # 命中片段 + 位置（对应 BrandShield 的举证包）
  reviewer / reviewed_at # 人工介入记录
```

### 6.3 同行实际披露了什么 —— 以及「都查不到」这个结论

**【证据】直接回答：四家 A 股跨境电商上市公司，没有任何一家公开披露内容审核流程。**
- 「内容审核」在四家 2025 年报中出现 **0 次**。
- 安克创新 2023/2024/2025 三份年报中「广告」出现 **0 次**。
- 四家的风险因素章节均无「广告宣传合规」条目。

**★ 「都查不到」本身就是一个结论，而且有三条可解释的原因（我在第 2.7 节已经论证）：**

1. **披露由「重大性」触发。** 广告费对品牌方是销售费用；一条文案违规的后果（罚款/下架）相对于营收不构成「重大不利影响」，所以理性披露策略就是不写。**不写 ≠ 没做。**
2. **广告合规只在两种情况下进年报：广告是收入项，或平台是审核义务主体。** PDD 20-F 有整段广告法风险披露，正因为它是**卖广告的平台**；《互联网广告管理办法》要求的「承接登记、审核、档案管理制度」的**法律义务主体是广告经营者/发布者**，不是广告主。**Momcozy 是广告主，所以这条路在方法论上就找错地方了。**
3. **真正在做内容治理的公司把它披露在「研发投入」而不是「风险因素」里。** 赛维时代的侵权检测平台在「4、研发投入 → 主要研发项目名称」表中。

**★ 给委托方的一句话结论：**

> **拿「上市公司年报里查不到内容审核」推断「同行没有做内容治理」是错误推理。** 年报只能证明「内容合规不是这几家的重大风险披露事项」。这个「查不到」反映的是**披露制度的形状**，不是行业的形状。**委托方如果想知道同行怎么做，应该走三个替代渠道**（本分片只走通了第一个）：
> 1. **同行的研发项目/技术能力披露**（✅ 本分片走通，见 6.4）
> 2. **岗位 JD**（❌ 本环境抓不到，需真实浏览器）
> 3. **平台侧的卖家评级/申诉文档**（❌ 本环境抓不到，需登录态）

**【证据】同行真正公开披露的、可以抄的东西（按可用度排序）：**

| 序号 | 来源（可逐字引用） | 可抄什么 |
|---|---|---|
| 1 | 赛维时代 2025 年报 P24「基于大模型的侵权检测平台」 | **整条流水线**：多模态（图像/文本/设计元素）→ 风险知识库 → 案例知识库（按平台分区）→ 自动评级 → 上架前前置筛查 + 在售持续监控 → 高检出率/低误报率双指标 |
| 2 | 安克创新 2025 年报 P61 供应商 ESG 评估 | **量化扣分制**（128 检查项 → 扣分 → 落档）+ **等级→处置映射**（整改/跟进审核/暂停/终止）+ **AI 智能体监控法规变化并升级法规数据库** |
| 3 | 赛维时代 2025 年报 P33 店铺关闭风险 | **规则库必须内置「外部政策变更侦测」**；平台规则变动「可能未事先沟通」 |
| 4 | 致欧科技 2025 年报 P17 + 华凯易佰 P12 + 赛维 P13 | **同行正在规模化 AIGC 生成营销素材，但无人披露生成后审核环节** → Momcozy 的需求是真实且被放大的 |

### 6.4 关于 Amazon Account Health 作为错题本原型的诚实话

**必须明确：我未能取得 Amazon Account Health / 政策通知机制的官方文档原文。**
- `sellercentral.amazon.com/help/hub/reference/external/G200370560`（Account Health 帮助页）返回的 169 KB HTML 里**没有服务端渲染的正文**，只有 SPA 外壳；
- 我尝试的 3 个 API 端点猜测全部返回同一个外壳；
- Amazon Brand Registry / Transparency 公开页正文同样 JS 渲染；
- 本环境的浏览器桥接不可用，无法执行 JS。

**因此，下面不是「Account Health 字段级建议」，而是「用我确实拿到的三个一手产物，拼出一个等价的产品原型」。** 如果委托方要真正的 Account Health 原型，需要**在登录态的真实浏览器里补抓**以下页面（这是我能给出的最精确的补抓清单）：

- `https://sellercentral.amazon.com/help/hub/reference/external/G200370560`（Account Health 帮助）
- `https://sellercentral.amazon.com/performance/dashboard`（Account Health 面板，需登录）
- Amazon「账户状况评级（Account Health Rating）」公告页（在 Seller Central 新闻区）
- Amazon DSP「内容邻接政策」与「广告库存政策」全文（入口在 `advertising.amazon.com/library/guides/brand-safety` 页尾）

**可用的三个等价原型（全部有一手证据）：**

**原型 A —— 官方标注集 schema（IAB Brand Suitability Test Benchmarks）**
- 最小字段：`label, url, title`（**只 3 个**）
- 聚合规则：11 类取最高档
- 档位：`minimal < low < medium < high < floor`
- **可借鉴**：字段要少；档位要序数化；标签要显式包含「无风险」底档。**Momcozy 现有 12 字段 + 52 条改写建议库 + 19 条卖点边界**远超官方错题本的最小集，**但缺的恰恰是最重要的两个：`content_id`（判定挂在内容上）和 `overall_severity`（max 聚合结果）。**

**原型 B —— 官方评测脚本（`evaluation.py`）**
- 5 档序数 → 在 `--level` 指定点二值化 → `Balanced Accuracy`（标签预测）或 `Average Precision`（0–1 分数预测）
- 不一致时**打印告警**而不是静默通过
- **可借鉴**：Momcozy 的 291 条在跑记录可以直接跑这个评测。**他们现在有 `风险等级 | 命中规则 | 命中片段 | 修改建议 | 检查人` 五个字段，已经具备跑 Balanced Accuracy 的全部输入。**

**原型 C —— 官方争议处理流程（README「Challenges」节）**
- 提 PR 时必须给：**文件 + URL + 期望的新标签 + 理由**
- 三种结局分流：标注错 → 改标注；标注对 → 关闭；**定义不清 → 升级为「修改规则定义」**
- **可借鉴**：这是 Momcozy「自迭代回路」缺的那一环。**他们现在 `依据来源` 字段只指向两份内部文档（`W1卖点表达边界（品线反馈2026-09-10 T4）`、`吸奶器广告文案审计_红绿灯.xlsx 规则库`），没有任何「这条规则本身的定义被质疑 → 修改规则定义」的记录位。**

**★ 从 BrandShield 的十个指标（第 4.2 节）里挑给 Momcozy 的最小子集：**

| 指标 | Momcozy 现状能否算 | 说明 |
|---|---|---|
| `Validated threats`（经核实为真的命中数） | ❌ 不能 | 现在 291 条记录里没有「已确认为真」这一层；21/21 声明「自动可检测」 |
| `Threats by type and channel` | ⚠️ 部分 | 有 `风险等级`、`命中规则`；有 `平台`（Google 262/Meta 27）—— 可以拆，但没有按类型×渠道的报表 |
| `Severity and customer exposure` | ⚠️ 部分 | 有严重度；有 `近7天费用USD / 展示 / 点击` —— **这是极好的 exposure 代理指标，同行/服务商都没有，Momcozy 反而有** |
| `Time to action` / `Time to removal` | ❌ 不能 | 没有时间戳字段 |
| `Repeat offenders` | ❌ 不能 | 没有内容生产者/责任方维度 |

**→ 最值得说的是第 3 行：Momcozy 的 291 条记录把 `风险等级` 和 `近7天费用USD / 展示 / 点击` 并列存储，这已经是一个「严重度 × 受众暴露」矩阵的雏形，而 BrandShield 把它列为十大指标之一、同行年报里完全没有。这是 Momcozy 现有资产里的相对优势，应该在规则库设计里保住并显式化，而不是在重构时丢掉。**

### 6.5 一个必须指出的内部矛盾（写进规则库验收清单）

**【证据 + 判断】** 任务书 §二 记录：21 条规则 `判断方式` **21/21 全部填 `自动可检测`**；同时 U 族的定义是「人工复核灰规则」。
**这两件事不能同时成立。** 一条规则如果「自动可检测」，它就不需要「人工复核」这一族；如果它真的需要人工复核，它的 `判断方式` 就不该是「自动可检测」。

**行业标准的处理方式对照：**
- IAB 的评测脚本**显式接受两种预测形态**：标签（`minimal/low/medium/high/floor`）**或** 0–1 分数；并且当预测是分数时，**必须指定 `--level` 操作点**。
- Zefr 在 IAB 站点的原文逐字：「**Simply relying on keyword analysis and Natural Language Processing (NLP) without human reviews leaves room for oversights like false positives and low precision.**」
- BrandShield 原文逐字给出四条必须给人的条件：「**unclear rights, regional differences, evasive operators, or repeated escalation**」。

**→ 【建议】把 `判断方式` 拆成两个正交字段：**
```
detection_mode : rule_based | model_score | human_only
operating_point: <当 detection_mode=model_score 时必填>   # 对应 evaluation.py 的 --level
escalation_criteria: <当 detection_mode≠human_only 时，什么条件下转人工>
```
并规定：**`detection_mode = rule_based` 的规则，其 `escalation_criteria` 必须非空**——因为纯规则匹配必然产生误报（Zefr 原文），没有升级条件就等于承认误报会直接漏过去。

---

## 7. 证据清单

### 7.1 行业标准（一手，全部为行业标准组织/平台官方发布）

| # | 来源 | URL | 抓取日期 | 本地路径 |
|---|---|---|---|---|
| E1 | IAB Tech Lab Content Taxonomy 标准页 | https://iabtechlab.com/standards/content-taxonomy/ | 2026-09-15 | `_evidence/R6/iab-content-taxonomy-page.html` / `.txt` |
| E2 | IAB Content Taxonomy 3.1（机器可读） | https://github.com/InteractiveAdvertisingBureau/Taxonomies/blob/develop/Content%20Taxonomies/Content%20Taxonomy%203.1.tsv | 2026-09-15 | `_evidence/R6/iab-content-taxonomy-3.1.tsv` |
| E3 | IAB Content Taxonomy 3.0（机器可读） | https://github.com/InteractiveAdvertisingBureau/Taxonomies/blob/develop/Content%20Taxonomies/Content%20Taxonomy%203.0.tsv | 2026-09-15 | `_evidence/R6/iab-content-taxonomy-3.0.tsv` |
| E4 | **IAB Content Taxonomy 3.0 Descriptive Vectors**（正交向量定义，★核心） | https://github.com/InteractiveAdvertisingBureau/Taxonomies/blob/develop/Content%20Taxonomies/Content%20Taxonomy%203.0%20Descriptive%20Vectors.tsv | 2026-09-15 | `_evidence/R6/iab-content-taxonomy-3.0-descriptive-vectors.tsv` |
| E5 | IAB Content Taxonomy 2.2（首次引入 GARM 的版本） | https://github.com/InteractiveAdvertisingBureau/Taxonomies/blob/develop/Content%20Taxonomies/Content%20Taxonomy%202.2.tsv | 2026-09-15 | `_evidence/R6/iab-content-taxonomy-2.2.tsv` |
| E6 | **IAB Tech Lab 实现指南 implementation.md**（★ 11 类 + 4 级 + 正交向量的规范表述） | https://github.com/InteractiveAdvertisingBureau/Taxonomies/blob/develop/implementation.md | 2026-09-15 | `_evidence/R6/iab-taxonomies-implementation.md` |
| E7 | **IAB Tech Lab 新闻稿「Content Taxonomy 2.2 to Improve Brand Safety and Support Brand Suitability」（2020-10-28）**（★ 11 类全名单 + 4 级 + 双方引语） | https://iabtechlab.com/press-releases/tech-lab-releases-for-comment-content-taxonomy-to-improve-brand-safety-support-brand-suitability/ | 2026-09-15 | `_evidence/R6/iab-pr-ct22-2020-10-28.html` / `.txt` |
| E8 | **IAB Tech Lab / Zefr「GARM Brand Suitability: Developing a Collaborative Interpretation of the Standard」**（★ 11×4 表述 + 误报问题 + 上下结合） | https://iabtechlab.com/garm-brand-suitability-developing-a-collaborative-interpretation-of-the-standard/ | 2026-09-15 | `_evidence/R6/iab-zefr-garm-interpretation.html` / `.txt` |
| E9 | **IAB Tech Lab `Brand-Suitability-Test-Benchmarks` 仓库**（★ 官方 GARM 标注集） | https://github.com/IABTechLab/Brand-Suitability-Test-Benchmarks | 2026-09-15 | `_evidence/R6/iab-brand-suitability-test-benchmarks-README.md` |
| E10 | 同上，YouTube 标注数据（5,330 行） | https://raw.githubusercontent.com/IABTechLab/Brand-Suitability-Test-Benchmarks/main/video/data/youtube.csv | 2026-09-15 | `_evidence/R6/iab-bsb-youtube.csv` |
| E11 | 同上，评测脚本 evaluation.py | https://raw.githubusercontent.com/IABTechLab/Brand-Suitability-Test-Benchmarks/main/evaluation.py | 2026-09-15 | `_evidence/R6/iab-bsb-evaluation.py` |
| E12 | **WFA GARM 停止运营声明（2024-08-09）** | https://wfanet.org/leadership/garm | 2026-09-15 | `_evidence/R6/garm-wfa-statement-2024-08-09.html` |
| E13 | GARM Brand Safety Floor + Suitability Framework 原 PDF（**被登录墙拦截，未取得**） | https://wfanet.org/l/library/download/urn:uuid:7d484745-41cd-4cce-a1b9-a1b4e30928ea/garm+brand+safety+floor+suitability+framework+23+sept.pdf | 2026-09-15 | `_evidence/R6/GARM-PDF-DOWNLOAD-BLOCKED-login-wall.html`（实际返回的是 WFA 登录页） |
| E14 | **Amazon Ads 官方《品牌安全》指南**（★ brand safety vs suitability 定义 + 四步流程） | https://advertising.amazon.com/library/guides/brand-safety | 2026-09-15 | `_evidence/R6/amazon-ads-brand-safety.html` / `.txt` |
| E15 | Amazon Ads 官方《广告库存》指南 | https://advertising.amazon.com/library/guides/ad-inventory | 2026-09-15 | `_evidence/R6/amazon-ads-ad-inventory.html` / `.txt` |
| E16 | **BrandShield《Online Brand Protection: The Complete 2026 Guide》（2026-08-24）**（★ 服务商方法论；供应商自发布，非独立评测） | https://www.brandshield.com/blog/online-brand-protection-the-complete-2026-guide/ | 2026-09-15 | `_evidence/R6/brandshield-guide.html` / `.txt` |

### 7.2 上市公司披露（一手，全部来自交易所官方渠道）

| # | 来源 | 取得方式 | 本地路径 |
|---|---|---|---|
| E17 | 安克创新（300866.SZ）2025 年年度报告 | SZSE API → `https://disc.szse.cn/download/disc/disk03/finalpage/2026-04-10/0c55621a-c49e-4915-9ba8-efe8f3f21fd1.PDF` | `_evidence/R6/listed-co-reports/anker-300866-annual-2025.pdf` / `.txt` |
| E18 | 安克创新 2024 年年度报告 | `.../2025-04-28/9bd3ae70-7998-4fbe-99ff-87b7ebd43cb8.PDF` | `anker-300866-annual-2024.pdf` / `.txt` |
| E19 | 安克创新 2023 年年度报告 | `.../2024-04-24/7bbcbd8f-9fc9-4c94-bfbd-00f902cf5f30.PDF` | `anker-300866-annual-2023.pdf` / `.txt` |
| E20 | 致欧科技（301376.SZ）2025 年年度报告 | `.../2026-04-29/a079f63f-66e8-48b3-a512-a2a32a9dc79e.PDF` | `ouke-301376-annual-2025.pdf` / `.txt` |
| E21 | 赛维时代（301381.SZ）2025 年年度报告 | `.../2026-04-28/5b874037-8418-42ed-bf51-ab2e62d55ec6.PDF` | `sailvan-301381-annual-2025.pdf` / `.txt` |
| E22 | 华凯易佰（300592.SZ）2025 年年度报告 | `.../2026-04-25/afed9d7f-bafe-4913-be76-0b8d17288fc6.PDF` | `huakai-yibai-300592-annual-2025.pdf` / `.txt` |
| E23 | **PDD Holdings Inc. FY2025 Form 20-F**（accession `0001104659-26-050727`，2026-04-29） | https://www.sec.gov/Archives/edgar/data/1737806/000110465926050727/pdd-20251231x20f.htm（需带含联系方式的 UA） | `_evidence/R6/pdd-20f-2025.htm` / `.txt` |

**引用页码对照（用于复核）：**

| 引用点 | 文件 | 页码 |
|---|---|---|
| 安克「公司可能面临的风险」4 项枚举 | `anker-300866-annual-2025.txt` | P39–P40 |
| 安克供应商 ESG「128 检查项/量化扣分/风险分级/分级处置」 | 同上 | P61 |
| 致欧「AIGC2.0 智能图库平台 + 文案自动化生成提效 70%」 | `ouke-301376-annual-2025.txt` | P17 |
| 致欧 2026 计划「文、图、视频全链路 AIGC 生成流程」 | 同上 | P41 |
| 致欧「公司可能面对的风险及应对措施」4 项 | 同上 | P41–P42 |
| 赛维「AIGC 技术高效生成商品图片、视频等多元化营销素材」 | `sailvan-301381-annual-2025.txt` | P13 |
| **赛维「基于大模型的侵权检测平台」** | 同上 | **P24** |
| 赛维「Amazon 广告投放智能体项目」 | 同上 | P24 |
| **赛维「店铺关闭风险」** | 同上 | **P33** |
| 赛维「公司可能面对的风险及应对措施」7 项 | 同上 | P33–P34 |
| 华凯易佰「推广模式 + AI 生成关键词/创意文案/创意图片」 | `huakai-yibai-300592-annual-2025.txt` | P12 |
| 华凯易佰「业务审核」「产品审核」（商品/物流侧） | 同上 | P25–P26 |

### 7.3 政策/法规条文（通过一手披露文件转述）

| # | 条文 | 来源 | 备注 |
|---|---|---|---|
| L1 | 《互联网广告管理办法》（SAMR，2023-02-25 公布，2023-05-01 施行）关于**广告经营者/发布者必须建立承接登记、审核、档案管理制度** | PDD FY2025 20-F, Item 4.B "Regulations Relating to Internet Advertising Business" | 英文转述原文见 2.5.3；**本轮未直接取到中文法规原文** |
| L2 | 同上，关于广告**可识别性**、付费搜索广告**显著标明"广告"**、弹窗**一键关闭**、禁止**欺骗性诱导点击** | 同上 | 同上 |
| L3 | 《中华人民共和国广告法》适用于互联网广告 | 同上 | 同上 |
| L4 | UK Digital Markets, Competition and Consumers Act 2024（DMCCA），CMA 可不经诉讼直接罚款 | 同上（Temu 相关段落） | 同上 |
| L5 | **16 CFR § 255.5 / Directive 2005/29/EC Art. 6 等** | — | **本分片未涉及**（属 R5/R2 边界） |

### 7.4 已抓取但正文不可用的页面（记录以免重复尝试）

| # | URL | 返回 | 说明 |
|---|---|---|---|
| F1 | https://sellercentral.amazon.com/help/hub/reference/external/G200370560 | 200 / 169 KB | 纯 SPA 外壳 |
| F2 | https://brandservices.amazon.com/protection | 200 / 434 KB | 正文 JS 渲染 |
| F3 | https://brandservices.amazon.com/transparency | 200 / 374 KB | 正文 JS 渲染 |
| F4 | https://brandservices.amazon.com/reportviolation | 200 / 434 KB | 正文 JS 渲染（与 F2 同源） |
| F5 | https://seller.temu.com/ | 200 / 176 KB | SPA |
| F6 | https://seller.tiktokglobalshop.com/ | 200 / 101 KB | SPA |
| F7 | https://partner.tiktokshop.com/ | 200 / 130 KB | SPA |
| F8 | https://www.zhipin.com/web/geek/job?query=内容审核 | 200 / 9 KB | JS 壳 |
| F9 | https://www.liepin.com/zhaopin/?key=内容审核 | 200 / 35 KB | JS 壳 |
| F10 | https://www.linkedin.com/jobs/search?keywords=Content%20Reviewer | **451** | 法律原因不可用 |

---

## 8. 缺口清单（我尝试过但没拿到的东西）

> 按任务书要求列出，让缺口可见。每条给出「尝试了什么」+「为什么失败」+「如何补上」。

### 8.1 行业标准侧

| # | 缺口 | 尝试了什么 | 失败原因 | 怎么补 |
|---|---|---|---|---|
| G1 | **GARM Brand Safety Floor + Suitability Framework 原 PDF 全文**（含「每个类别 × 每个层级」的逐格指导） | ① WFA 图书馆原始 URL（E13），带/不带 `?ext=.pdf`/`?scaleType=1`/`Referer` 共 4 种组合；② 搜索引擎（Bing 中文站、Bing RSS、Mojeek、Brave、Ecosia、Startpage、7 个 SearxNG 实例）；③ 归档（Wayback CDX + availability API、Common Crawl index 3 个 collection）；④ GitHub 检索 | ① WFA 图书馆现已要求登录（返回 WFA 登录页 HTML）；② 搜索引擎在本环境大面积不可达或只返回中文本地化结果；③ `web.archive.org` 连接超时（`Connect Timeout`），Common Crawl 对 `wfanet.org` 返回 `No Captures found`；④ 仅检索到 1 个使用 GARM 评分的第三方仓库，未含框架原文 | **需人工浏览器**：在浏览器里登录/直接打开 WFA 页面下载；或从 IAB Tech Lab 会员区获取（IAB 实现指南引用了它但没有全文复制） |
| G2 | GARM 框架「每格指导」的**语义**（是禁止/限制/允许，还是别的） | 同上；另查 IAB implementation.md 全部 789 行 | 第 368 行明确把定义**甩给 GARM 原文**：「the descriptions for each category at each risk level, including the Floor, are **described in the framework**」；第 360–364 行的向量描述表四行全部只写 `Defined in the GARM / 4As/APB specs` | 同 G1。**但注意**：从 1.4.2 可确证至少「聚合方式是 max」与「5 档序数刻度」两点，这两点已足够指导实现 |
| G3 | 4A's APB 自有文档 | `aaaa.org` → **403** | 反爬 | 人工访问 |
| G4 | MRC 的 Brand Safety 专属标准 | `mediaratingcouncil.org` 可达（200），但未在其站点定位到内容级 Brand Safety 标准文档 | 未找到入口；MRC 标准主要集中在 measurement / viewability / IVT | 人工检索 MRC 标准目录 |
| G5 | Meta / Google / GroupM / Unilever 采用 GARM 的公开声明原文 | `support.google.com` **连接失败/超时**；`transparency.meta.com` **连接失败**；`unilever.com` **403**；`groupm.com` 200 但未找到 GARM 专页 | 网络不可达 + 反爬 | 人工访问；或查 X Corp. v. GARM 诉讼文书（`courtlistener.com` 403，但 `storage.courtlistener.com` 200——可试直接构造文书 URL） |

### 8.2 上市公司披露侧

| # | 缺口 | 尝试了什么 | 失败原因 | 怎么补 |
|---|---|---|---|---|
| G6 | **子不语（2420.HK）年报** | ① `prefix.do` 查得 `stockId=1000172163`✅；② `titleSearchServlet.do` 用 6 种参数组合（日期格式 2 种、语言 2 种、`searchType` 0/1、`t1code` -1/40000）；③ POST 该 servlet（405）；④ `listconews/advancedsearch/search_active_main.aspx`（返回框架页，无表单字段） | 港交所检索接口的参数契约未攻克（疑缺会话态或 `t2Gcode` 合法枚举） | 人工在披露易按股票代号检索，或改用 HKEX 的 `Listed Company Information` 页面手动下载 |
| G7 | SHEIN 招股书 | SEC EDGAR 公司名检索 + `data.sec.gov/submissions/CIK0002152230.json` | **`SHEIN Global Holdings Limited/ADR`（CIK 0002152230）的 filings 只有 3 份 F-6EF，无 F-1**。判断为保密递交（confidential submission），保密期文件不进 EDGAR | 若 SHEIN 后续完成上市，其公开招股书会进入对应交易所披露系统；伦敦/香港上市则查 LSE/HKEX |
| G8 | PatPat 披露文件 | 未上市 | **不存在披露文件** | 无（此项为「确认不存在」，不是「没找到」） |
| G9 | 各公司**招股说明书**（IPO prospectus，风险披露远详于年报） | 只检索了年报与半年报 | 未在 SZSE API 查询中单独筛 `招股说明书` 类目（安克 2020 年上市、致欧/赛维/华凯均在 2021–2023 年上市，招股书应在 SZSE 可查） | **可低成本补上**：同一 SZSE API 加 `category` 筛选或按更早 `seDate` 区间重查。**建议补，因为招股书的风险因素章节通常逐条披露广告宣传/知识产权/平台规则风险** |
| G10 | 乐歌股份、巨星科技 | **未尝试** | 时间分配优先级 | 若需要，方法与 2.0 节相同，SZSE API 直接可用 |

### 8.3 岗位侧

| # | 缺口 | 尝试了什么 | 失败原因 | 怎么补 |
|---|---|---|---|---|
| G11 | **任何跨境电商/消费品公司的内容审核、广告合规、品牌安全岗位 JD 原文** | LinkedIn（451）、Boss 直聘（JS 壳）、猎聘（JS 壳） | 三站均为 CSR 单页应用 + 反爬；本环境**无 JS 渲染能力**（浏览器桥接不可用：`The controlled tab was closed`；`r.jina.ai` 返回 000） | **必须用真实浏览器**。建议检索词：`内容审核`、`广告合规`、`合规专员`、`品牌安全`、`Brand Safety`、`Content Reviewer`、`Ad Policy`、`Trust & Safety`；目标公司：安克、SHEIN、Temu、致欧、赛维、Babycare、好孩子、飞鹤 |
| G12 | 合规团队组织结构描述 / 行业薪酬岗位报告 | 未找到可用的公开来源 | — | 可试中国广告协会、中国跨境电商协会的公开指引（本分片提到但未抓取） |

### 8.4 平台侧

| # | 缺口 | 尝试了什么 | 失败原因 | 怎么补 |
|---|---|---|---|---|
| G13 | **Amazon Account Health 机制官方文档原文**（卖家如何知道 listing 违反了哪条规则、政策通知、申诉流程） | 帮助页原文 + 3 个 API 端点猜测 + Brand Registry 三个公开页 | 全部为 SPA，正文不在 HTML 里；浏览器桥接不可用 | **必须登录态 + JS 渲染**。补抓清单见 6.4 |
| G14 | **Amazon Brand Registry / Transparency 的规则与报告机制原文** | `brandservices.amazon.com/protection`、`/transparency`、`/reportviolation` | 正文 JS 渲染 | 同上 |
| G15 | **TikTok Shop 的违规行为定义与处罚阶梯原文**（扣分/降权/封店） | `seller-us.tiktok.com`（000）、`seller.tiktokglobalshop.com`（SPA）、`partner.tiktokshop.com`（SPA）、`tiktok.com`（000） | 连接失败 + SPA | 需真实浏览器 + 可能的卖家账号 |
| G16 | **Temu 卖家违规处罚机制原文** | `seller.temu.com`（SPA）、`temu.com`（跳转壳） | SPA | 同上 |

### 8.5 服务商方法论侧

| # | 缺口 | 尝试了什么 | 结果 |
|---|---|---|---|
| G17 | Red Points 公开方法论 | `redpoints.com` → **403** | 未取得 |
| G18 | CounterFind 方法论长文 | 站点可达，仅找到 `/blog` 与 `/brand-protection-platform` | 未取得方法论正文 |
| G19 | MarkMonitor 白皮书 | 站点可达 | 未定位到方法论文档 |
| G20 | Deloitte / PwC / Accenture / McKinsey 的内容合规白皮书 | 前三个域名可达，McKinsey 连接失败 | **未定位到任何一份内容合规/广告合规白皮书**。这一项判断为「此类白皮书要么不存在、要么需付费/留资」，不是抓取失败 |
| G21 | 中国广告协会、中国跨境电商协会的公开指引 | **未尝试** | 时间分配优先级 |

### 8.6 方法性缺口（影响结论强度，必须说明）

| # | 缺口 | 影响 |
|---|---|---|
| G22 | **四家公司年报只覆盖 A 股。** 港股（子不语）、美股中概（SHEIN）未覆盖 | 「都查不到」的结论强度限于 A 股 4 家 + PDD。**PDD 恰好是最反例（有广告合规披露），这个反例本身构成了 2.7 的核心论证** |
| G23 | **只检索了年报正文，未检索「研发投入」表的全部条目** | 除了赛维的侵权检测平台，可能还有其他公司的技术披露被漏掉。**建议对四家年报的研发项目表做一次专项人工通读** |
| G24 | **未取得任何平台的「违规 → 处罚」官方阶梯表** | 第 5.3 节的处罚阶梯是**中国法定侧**的，不能替代平台侧阶梯。**平台侧阶梯是 Momcozy「严重等级」最直接的标定依据，这个缺口优先级最高** |
| G25 | **未取得任何岗位 JD** | 第 3 节只能给出「行业标准方对买方的职责定义」（IAB），不能给出「同行实际设了什么岗、每天做什么」。**这是「流程的化石」这一诉求完全未满足的部分** |

---

## 9. 附：本分片对四个总问题的回答摘要

（供最终交付综合时直接引用；详细论证见各节）

| 总问题 | 本分片的答案 | 出处 |
|---|---|---|
| **1. 维度模型** | 「国家 × 品类 × 平台 × 内容类型」四维笛卡尔积**不是**行业答案。行业答案是**三层**：① 主题分类树（一条轴）；② 正交属性向量（平台/格式/来源/目的/语种/国家，互不相乘，语种与国家外挂 ISO 标准）；③ 风险级作为**动态挂在主题上的属性**。行业标准比 Momcozy 多两条轴（`Content Source`、`Content Purpose`），少一条轴（品牌自身调性——GARM 明确留给品牌自定义） | §1.1、§6.1 |
| **2. 萃取方法** | 行业标准走的是**自上而下定框架 + 自下而上填案例**的闭环。Zefr 原文：「the existing GARM standard takes an initial **top down** approach by working with the buy-side to create brand suitability definitions；…it is equally important to support the sell-side by **providing content examples that match these definitions**」。案例集的作用有二：「refine their verbiage and categories based on reviews of actual content」+「practitioners to have a **golden labeled set** ... to judge their own content understanding algorithms by」 | §1.4.2、§1.4.3、§3.3 |
| **3. 错题本 / 规则库 / 严重等级** | 三者关系：**规则库 = 骨架（主题树 + 向量 + 等级枚举）；错题本 = 标注样本集（官方最小字段只有 `label, url, title` 三个）；严重等级 = 规则库里的一个字母数字 ID 向量（`bsr001`–`bsr004`），实践扩成 5 档序数**。没有规则时怎么办：GARM 给了答案——**把「没有规则」当作最低档 `minimal` 显式建模**，而不是留空 | §1.1.4、§1.4.2 |
| **4. 自迭代** | 度量：官方脚本给出 `Balanced Accuracy`（标签预测）/ `Average Precision`（0–1 分数）+ **必须指定操作点 `--level`**；服务商侧给出 10 个指标，Momcozy 直接可用的是 `Validated threats` / `Time to action` / `Repeat offenders`。回路：官方 README 的争议流程给出**三种结局分流**，其中「定义不清 → 修改规则定义」是 Momcozy 完全缺失的一环。谁负责：IAB 明确买方负责「读框架 + 从案例反推容忍度 + 以标准 ID 写进投放配置」三个动作 | §1.4.2、§1.4.3、§3.3、§4.2 |

---

**（R6 分片完）**


