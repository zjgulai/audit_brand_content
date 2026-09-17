# R7-W3 母婴品类参照与冷启动路径

> 撰写：品类合规参照与冷启动路径研究员
> 日期：2026-09-15
> 范围：母婴/健康类目真实规则**结构**参照（Q3）+ 无规则库团队的冷启动路径（Q4）
> 证据根目录：`/Users/lute/Project/audit_multi_content/research/governance/_evidence/`

---

## 0. 本部分结论

1. **跨市场卖点差异的真实结构是「页面内嵌的国别覆写表」，不是分国别文档**——Amazon Ads 政策页用 `Country-specific restrictions` 节处理，默认值是 "the worldwide policy outlined above"，EU-27 合并为一条，UK 单独一条。（§2.2.3，`_evidence/R1/amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.html`）
2. **国别覆写可以是「放松」，不只是「加严」**——Amazon 英国条目逐字："advertisers have the option of either conforming to the worldwide policy outlined above, or, instead of providing a study and date, they can provide a PO box mailing address or manufacturer email address for consumers to have a means of contacting the advertiser."。**这是举证强度降档**，因此国别字段必须支持「替换证据要求」，而非只支持禁止/允许。（§2.2.3）
   > **复核提示**：该文本**不在**文本层抽取件 `.md` 中（Amazon 用客户端折叠组件承载国别正文，`read_page`/`web_fetch` 只取到国名标题），且位于原始 `.html` 的**第 1336 行（11,371 字符超长行）**，部分 grep 封装会跳过。**复核须用字节级计数或 §5.1b 的解码抽取件** `_evidence/R1/amazon-ads-claims-substantiation-country-restrictions.md`。字节级计数：`mailing address`→1、`study and date`→1、`PO box`→1、`email address`→1。
3. **Amazon 把「哪些国家有覆写」做成了机器可读字段**——同一政策页内嵌元数据含 `"country_reqs"` 数组，30 个元素（EU-27 全名 + Brazil + Singapore + United Kingdom）；另有 `"lastModified":"2026-01-28T19:49:38.706Z"`、`"content_status":["Active"]`、`"vertical":["Claims and Substantiation"]`、`"role":[..., "Moderation", "AT Policy"]`。**国别覆写不是散文，是结构化列表**。（§2.2.3）
4. **Amazon 的 claim 政策第一条规则是「举证责任分配」，不是内容红线**——"Advertisers are required to ensure the accuracy of claims and provide factual substantiation if requested by Amazon."；FTC 的两原则第一条是「真实不误导」，NAD 三步的第一步是「先归类产品」。四个体系收敛为：**第一条规则是路由 + 兜底，不是红线**。（§2.1）
5. **FTC HPCG 是本次找到的唯一完整可用的健康品类规则库范本**，且它是**按判定动作组织（4 层 14 末级节），不按法源编号组织**；它明确拒绝按品类分档——"FTC law makes no bright-line distinctions between categories of health-related products or claims"。（§1.3.2）
6. **`FDA cleared` / `hospital grade` 类监管状态词的违规点不在词本身，而在「与其他宣称的并置 + 用途范围是否匹配」**——FTC HPCG Example 49 的 ab belt 案为此提供了可枚举的判定结构（clearance 的 intended purpose vs 广告宣称）。（§1.3.6）
7. **「限定词内嵌」是跨市场差异最轻量、最可机器化的解法**——用 `most` / `up to` / `95%` 替代 `all` / `every` / `universal`，把不可证伪的全称命题降级为可证伪的比例命题，从而**一套文案在多数法域同时成立**，无需准备两套。（§1.1.1）
8. **竞品的 claim 规则与审查流程全部未找到，这是一个重要的负面发现**——七个品牌 legal/claims 页本次逐一补抓（Elvie 404 ×2、Willow 403、Medela 404、Lansinoh 404、Spectra 404；Legendairy/Freemie 首页零命中）。**claim 合规在该品类是暗能力，规则库骨架必须自建。**（§1.4.2）
9. **CRN 的公开规则库按「成分/剂型/渠道」组织，FTC 按「判定动作」组织——两者是流水线的两段，客户必须同时建两个索引**（对象索引用于找规则，判定索引用于执行规则）。（§1.2.5）
10. **客户 21 条规则的真实缺陷不是「条数不够」，而是「判定层与定位层被写在了一起」**——正则层从不多报一条（零假阳性）证明它只做定位不做判定；H07 命中最多（51 次）而正则覆盖率最低（7%）证明命中量与规则可执行性无关。（§2.3.2、§3.1）
11. **「多少条规则够用」无公开一手数据（且本次搜索工具不可用），但客户自有数据已证伪「越多越好」**——21 条中 9 条无正则、2 条覆盖率为 0%，实际生效不足 10 条。建议改用可判定验收线：**可穷尽来源层（法源 + 平台政策）逐条对账完毕 + 每条规则能给出正反样例对**。（§2.3、§3.4）
12. **known gaps register 有三种真实形态，Amazon AHR 的「范围内清单 + 明示排除声明」最可直接抄**——"This page lists all policies included in the AHR" + "**not all of Amazon's policies are currently included in AHR**" + "will be updated as new policies are added in the future"，15 条政策可枚举。（§2.4.1）
13. **客户现状已有 8 条现成缺口条目可直接入册，且必须分「执行缺口」与「覆盖面缺口」两类记账**——前者可随规则改写消除，后者需排期，混记会让「未覆盖」永远算不清。（§2.4.4、§3.5）

---

## 1. 母婴/健康品类的规则结构参照

> **本节的组织逻辑**：Q3 问的是规则**结构**，不是规则**内容**。因此每个小节都尽量把「某个机构写了什么」翻译成「**这个结构可以被客户怎么复用**」。四个小节的顺序是：跨市场差异（1.1）→ 证据规则库（1.2）→ 单一文件的结构解剖（1.3）→ 竞品实际做法（1.4）。
>
> **本节的核心结论**：品类规则库存在**两种正交的组织范式**——FTC 的「按判定动作组织」（1.3.1）与 CRN 的「按对象组织」（1.2.5）。客户必须**同时建两个索引**，只建一个都会失败。

### 1.1 跨市场卖点差异的结构化表达

Q3.1 问的是：真实存在的品牌/平台，如何**结构化**处理「同一卖点在 A 国可说、B 国不可说」——是分国别文档？表格？限定词？

**本节的核心答案（三个机制，按可复用性排序）：**

| 机制 | 形态 | 真实案例 | 可机器化程度 |
|---|---|---|---|
| **M1 限定词内嵌** | 把国别边界写进句子本身（`most` / `up to` / `95%` 替代 `all`） | Medela "fit seamlessly in **most** nursing bras" | **高**——可正则 + 白名单改写库 |
| **M2 数值锚定** | 把无定义的营销词锚定到可复核的物理量 | Willow "hospital-strength … (up to **295 mmHG** per side)" | **高**——可抽参数比对 |
| **M3 术语表 / 术语裁决** | 品牌自建术语定义页，把词性差异显式化 | Momcozy 官网 Q&A 区分 hospital grade vs hospital strength | **中**——需人工维护，但可作规则的 `依据来源` |

**没有找到的机制**：**没有任何一个母婴/健康品牌公开了「分国别文档」形态的规则结构。** 竞品官网的 `legal` / `terms` 页面是**通用商业条款**（退换货、知识产权、争议解决），**不是** claim 规则。见 §1.4。

#### 1.1.1 机制 M1：限定词内嵌——最轻量、最可复用的跨市场手法

【原文】
> **Medela**："three additional inserts to cater to **over 95% of nipples sizes**"
> **Medela**："The anatomically shaped collection cups fit seamlessly in **most** nursing bras"

来源：`research/governance/R5-category-and-competitors.md` §7.2 卖点 E（逐字对照表）
底层证据：`_evidence/R5/competitors/medela-*.txt`（Medela 产品页抓取，2026-09-15）
R5 对此的判断（逐字）：
> "**Medela 的 "most nursing bras" 是最值得学的一条。** 用**限定词**（most / up to / 95%）替代**全称**（all / every / universal），把一个不可核查的全称声称变成一个可核查的比例声称。**这是一条可以直接做成改写建议库模板的规则。**"

【判断】M1 的本质是**「把不可证伪的全称命题降级为可证伪的比例命题」**。它的跨市场优势在于：全称命题（`fits all breast shapes`）在几乎所有法域都是高风险（不可 substantiate），而比例命题只要数据支撑即在多数法域可保留。**因此同一卖点不需要两套文案，只需要一套「可核验化改写」**。这是 Q3.1 的一个反直觉答案：**跨市场差异的最优解常常不是「准备两套文案」，而是「把文案改写到在所有市场都成立的形态」**。这与 FTC HPCG 的 substantiation 逻辑（§1.3.4）完全一致。

#### 1.1.2 机制 M2：数值锚定——把营销词从「不可核查」搬到「可核查」

【原文】
> **Willow**："15 levels of customizable, hospital-strength, tug-and-release suction (**up to 295 mmHG per side**) mimics baby's natural feeding pattern"
> **Willow**："Willow 360 has a suction range and strength (up to ~245mmHG) that is **comparable with** traditional double electric and **hospital-grade pumps**"

来源：`_evidence/R5/competitors/KEYWORD-HITS-raw.txt` 行 1570–1572（逐字，含原文中的 `mmHG` 大小写）
URL：willowpump.com 产品页，抓取 2026-09-15

【原文】
> **Lansinoh**：在 6 个页面混用 hospital **GRADE** / **STRENGTH** / **-GRADE**，锚定在一个 **280 mmHg** 数值上

来源：`research/governance/R5-category-and-competitors.md` §7.2 卖点 F
底层证据：`_evidence/R5/competitors/lansinoh-*.txt`（11 个产品页）

【判断】R5 给出的分类判据可直接转化为规则：
> （R5 §7.2 逐字）"**可核查用法**：`hospital-strength suction (up to 295 mmHG per side)` —— 锚定在物理量上，可验证。**Willow 与 Lansinoh 用这一种。** / **不可核查用法**：`Hospital-Grade Suction Breast Pump` 写进产品名 —— 无法验证"hospital grade"是什么意思。**Elvie、Spectra、Momcozy 用这一种。** / **Medela 用第三种：主动否认。** 这是最保守也最安全的做法。"

【判断】M2 的规则形态是**「裸词 → 审慎；裸词 + 可复核数值 → 合规；裸词进入产品身份（品名/URL handle/结构化属性）→ 高危」**。这是一个**三元判定**，而不是二元的「可用/不可用」。第三条（进入产品身份）的法源依据是 UCPD Art. 6(1)(b) 的 "main characteristics of the product"，R5 §7.7 已给出完整论证。

#### 1.1.3 机制 M3：术语表——真实存在的、品类内唯一的显式结构

**这是本次调研找到的最接近「跨市场卖点差异的结构化表达」的一手样本，而且它来自客户自己。**

【原文】（Momcozy 官网集合页 Q&A）
> **Q: Is hospital strength the same as hospital grade for breast pumps?**
> "Hospital strength and hospital grade are related but distinct terms. A hospital-grade pump is a multi-user rental device built for clinical settings, with specialized motor technology and programming designed to support mothers with medical necessity. '**Hospital strength**' is a manufacturer-used term describing powerful suction performance in a single-user personal pump — **it does not mean hospital grade.**"
> "While some brands use these terms loosely, they are not interchangeable. Hospital-grade pumps are generally recognized for delivering strong, consistent suction in clinical settings, **though there is no official regulatory standard defining a specific mmHg threshold for either term.**"

来源：`research/governance/R5-category-and-competitors.md` §7.7 立场 (a)，抓取日 2026-09-15
URL：https://momcozy.com/collections/hospital-grade-breast-pump

【判断】**这段文字的结构价值远大于它的营销价值**。它做了一件规则库设计上很关键的事：**显式声明「一个词没有法定定义」**。R5 对此的判断（逐字）：
> "**立场 (a) 的内容实际上是委托方最有价值的合规资产。** 它准确地说明了「hospital grade」与「hospital strength」的区别，并且**明确承认这两个词都没有官方法定定义**。这段文字本身就是对 M05 的正确答案，而且是**品类内唯一一家把这件事讲清楚的品牌**。"

#### 1.1.4 反面案例：同一品牌跨渠道三种立场——「跨市场一致性」是一个被忽略的维度

R5 §7.7 记录的三个立场（同一品牌、同一天、三个渠道）：

| 立场 | 渠道 | 逐字表述 |
|---|---|---|
| (a) **否认** | momcozy.com 集合页 Q&A | "it does not mean hospital grade" |
| (b) **主张** | momcozy.com 电动吸奶器集合页 | "**V Series** — Separated-motor design with **hospital grade suction**" |
| (c) **在亚马逊主张** | ASIN `B0CZNQ7VH7`（US） | 标题含 "**Hospital-Grade** Pocket Primary Pump"；结构化属性 `Product Style: hospital grade` |

来源：`research/governance/R5-category-and-competitors.md` §7.7，三渠道均 2026-09-15 实时在线

【判断】这揭示了一个 **Q3.1 原问题没有覆盖的维度**：「A 国可说、B 国不可说」的常见提法是**地理维度**，但真实的高频冲突是**渠道维度**（官网 vs 亚马逊 vs 广告）。而且：
- **跨渠道的净印象也算数**——R5 引用 FTC Deception Policy 1983 的 "the entire mosaic" 标准：消费者在亚马逊看到 "Hospital-Grade"、在官网读到「我们的单用户泵不是 hospital grade」，构成净印象冲突。
- **结构化属性字段是最危险的位置**：R5 §7.7 逐字指出 "**结构化属性 `Product Style: hospital grade` 是品牌自己填的字段，属于最典型的 "specification"**"（对应 UCPD Art. 6(1)(b)）。
- **客户现状的直接含义**：M05 现行判定「审慎关注，需核实是否有对应认证」的**前提是错的**——因为**不存在**这样的认证（Momcozy 自己都承认）。正确判定是「查跨渠道一致性」。

#### 1.1.5 平台侧的「国别差异」：明确的联合键结构

真实平台把「国别」做成**「平台 × 国家」联合键**，而不是独立的国别文档：

【原文】（R5 §8.4 对 Amazon 的核验结论）
> "(4) 国别条款：**澳大利亚禁止在 Amazon 上作疾病/不适相关声称**（与 §7.6 的风险叠加）"

【原文】（R5 §8.5 对 TikTok 的核验结论）
> "(2) 但**特定市场**对医疗器械一刀切禁止前后对比 —— 这是 `平台 × 国家` 联合键的又一实证"

来源：`research/governance/R5-category-and-competitors.md` §8.4(4)、§8.5(2)

【判断】平台侧的结构是 `（平台，国家）→ 附加限制集`，**继承关系为：法源约束 ⊂ 平台约束**，且平台可以在特定国家**加严**（如澳大利亚）。因此客户规则库的**作用域键至少需要三元组**：`规则 × 市场 × 渠道/平台`。R5 §9.1 把品类维度的本质定义为「**一张法规映射表，不是一堆经验**」，与此一致。

【本节未找到】任何母婴/健康品牌公开的**分国别 claim 规则文档**。竞品官网的 legal/terms 页为通用条款。见 §1.4 与 §4。

### 1.2 Claim substantiation 规则库

**结论先行**：公开的 substantiation 规则库**存在且是一手的**，但不是以「规则条目数据库」的形态存在，而是以 **「判定步骤 + 因素清单 + 案例库」三层**存在。本分片找到三套可交叉验证的一手体系：FTC（政府，成文法基础）、NAD/NARB（行业自律，案例驱动）、ASA/CAP（英国，成文准则）。三者**结构高度同构**，差异在于「谁执行」。

#### 1.2.1 NAD 的三步清单——最接近「规则库首版」的公开范本

NAD（BBB National Programs 的 National Advertising Division）与 NARB 是**美国广告自律体系**的裁决机构。其公开的从业人员指南是一份三步骤清单：

【原文】
> "The goal of advertising substantiation is threefold:
> - Assure that advertising is truthful
> - Prevent consumers from being misled
> - Level the playing field for competitors"

> "What follows is not legal advice but a basic one-two-three checklist for advertisers concerned about substantiating their advertising claims."

> "## Step One: Consider the Product
> Certain products are subject to specific regulations and guidance. If the product is a food, dietary supplement, drug, medical device, or cosmetic, Food and Drug Administration (FDA) regulations apply. Compliance with regulations is not the end of the story, though, because all advertising claims, whether for a regulated product or not, must be truthful and not misleading."

> "## Step Two: Examine All that the Advertising Conveys
> Advertisers are responsible for all express and implied claims that reasonable consumers take away from their ads and must have substantiation for all claims before they begin advertising the product. Express claims include the words in the ad itself. Implied claims include claims reasonably inferred from express claims as well as from depictions and from what is omitted."

> "## Step Three: Determine the Appropriate Level of Substantiation
> There is no "one size fits all" when it comes to advertising but there are a few important rules of the road. In substantiating an ad claim, the support should be a good fit for the claim."

来源：`_evidence/R2/nad-guidance-substantiation-checklist.txt`（行 288–305, 306–312, 313–326, 327 起）
URL：https://bbbprograms.org/media/insights/blog/checklist-for-substantiating-advertising-claims
FETCH_METHOD: microlink.io cloud renderer，FETCH_DATE: 2026-09-15（文件头自述）

【判断】**三步清单本身就是一条「冷启动规则」的现成答案**（回应 Q4「第一条规则应该是什么」）：这条清单的**第一步不是「合规检查」，而是「先确定产品落在哪个监管制度下」**。即：第一个动作是**分类（route the product），不是判定（judge the claim）**。三步的顺序——产品 → 声明（含隐含） → 证据等级——在 FTC HPCG 里是同一顺序的展开版（HPCG 用 III.A/III.B 两大节），在 NAD 这里压缩成三句话。**跨三个体系顺序一致**，说明这是该领域真正的「第一性结构」，而非某家机构的偏好。

#### 1.2.2 NAD 的深层规则：隐含声明与「你没打算做的声称」

【原文】
> "Advertisers must have substantiation for all messages consumers reasonably take away from the ad, even if the advertiser did not intend to make the claims."

> "In addition, ads that expressly or impliedly compare one product to another, including superiority claims, such as that the Wonder Widget performs better than competitors (named or unnamed), require substantiation as well."

> "A claim that specifies a level of substantiation must be supported by at least that level of substantiation. For example, if the Wonder Widget ad indicated that "studies show that the Wonder Widget could pull an elephant," then the advertiser must have reliable studies that show the Wonder Widget can indeed pull the weight of an elephant."

> "Note that testing a product with different ingredients, properties, or composition from the advertised product is generally insufficient substantiation unless there is additional reliable evidence demonstrating that testing on a different product can substitute for testing on the advertised product. It may seem obvious, but it is worth a reminder that reviews from satisfied customers are not considered reliable evidence."

来源：`_evidence/R2/nad-guidance-substantiation-checklist.txt`（同上文件，Step Two / Step Three 段）
URL：https://bbbprograms.org/media/insights/blog/checklist-for-substantiating-advertising-claims

【判断】**最容易被漏掉、也最值钱的两条 NAD 规则**：
1. **「未打算声称」也是声称**（"even if the advertiser did not intend to make the claims"）。这条意味着规则库不能用「意图」作为任何规则的前置条件；判定对象只能是**文本 + 图像 + 省略**对合理消费者的实际传达。
2. **测试对象 ≠ 广告对象 → 不构成 substantiation**（"testing a product with different ingredients, properties, or composition from the advertised product is generally insufficient"）。这是**「成分迁移」规则**，在母婴品类极常见（用某成分的文献支持含该成分的整机/复合产品）。客户母婴品类若做成分宣称（如某益生菌菌株、某材质），这条规则直接适用。

#### 1.2.3 FTC 1984 substantiation 政策声明：规则的「法源层」

【原文】
> "First, we reaffirm our commitment to the underlying legal requirement of advertising substantiation-that advertisers and ad agencies have a reasonable basis for advertising claims before they are disseminated."

> "Objective claims for products or services represent explicitly or by implication that the advertiser has a reasonable basis supporting these claims. These representations of substantiation are material to consumers. ... Therefore, a firm's failure to possess and rely upon a reasonable basis for objective claims constitutes an unfair and deceptive act or practice in violation of Section 5 of the Federal Trade Commission Act."

> "When the substantiation claim is express (e.g., "tests prove", "doctors recommend", and "studies show"), the Commission expects the firm to have at least the advertised level of substantiation. Of course, an ad may imply more substantiation than it expressly claims or may imply to consumers that the firm has a certain type of support; in such cases, the advertiser must possess the amount and type of substantiation the ad actually communicates to consumers."

> "Absent an express or implied reference to a certain level of support, and absent other evidence indicating what consumer expectations would be, the Commission assumes that consumers expect a "reasonable basis" for claims. The Commission's determination of what constitutes a reasonable basis depends ... on a number of factors relevant to the benefits and costs of substantiating a particular claim. These factors include: the type of claim, the product, the consequences of a false claim, the benefits of a truthful claim, the cost of developing substantiation for the claim, and the amount of substantiation experts in the field believe is reasonable."

> "One issue the Commission examined was substantiation for implied claims. Although firms are unlikely to possess substantiation for implied claims they do not believe the ad makes, they should generally be aware of reasonable interpretations and will be expected to have prior substantiation for such claims. The Commission will take care to assure that it only challenges reasonable interpretations of advertising claims."

来源：`_evidence/R5/ftc/ftc-policy-statement-advertising-substantiation-1984.CLEAN.txt`（"The Reasonable Basis Requirement" / "Standards for Prior Substantiation" 段）
URL：https://www.ftc.gov/legal-library/browse/ftc-policy-statement-regarding-advertising-substantiation
（同文另存：`_evidence/R2/ftc-advertising-substantiation-policy-statement-1984.txt`，含页头 "Date November 23, 1984"，标题 "FTC Policy Statement Regarding Advertising Substantiation"）

【判断】六个因素的**可枚举性**是这份 1984 文件对规则库设计的最大贡献。它们构成一个**「需要多少证据」的权重向量**：
`[type of claim, product, consequences of false claim, benefits of truthful claim, cost of developing substantiation, expert-accepted amount]`
注意其中两个是**反向权重**（truthful claim 的收益、举证成本会**降低**要求）。规则库若把「证据要求」写死为单一阈值，会与这条法源冲突——正确形态是**分级 + 可援引的减档理由**。

另注意「implied claims they do not believe the ad makes」这一句：FTC 自己承认这是**规则库在信息上不可能完备**的地方，并主动承诺「only challenges reasonable interpretations」。这是 Q4「规则写不完」问题在**法源层的官方承认**——见 §2.4。

#### 1.2.4 可用的一手规则库清单（本节已核验存在）

| 体系 | 文件/入口 | 形态 | 本地证据路径 |
|---|---|---|---|
| FTC（美，政府） | Health Products Compliance Guidance (2022-12) | 指南：4 层 14 末级节 | `R5/ftc/ftc-health-products-compliance-guidance-2022-12.PDFTEXT.txt` |
| FTC（美，政府） | Advertising Substantiation Policy Statement (1984) | 政策声明：6 因素 | `R5/ftc/ftc-policy-statement-advertising-substantiation-1984.CLEAN.txt` |
| FTC（美，政府） | Deception Policy Statement (1983) | 政策声明：欺骗三要件 | `R5/ftc/ftc-deception-policy-statement-1983.PDFTEXT.txt` |
| FTC（美，政府） | 16 CFR Part 255 Endorsement Guides | 成文规则 | `R5/ftc/ecfr-16cfr255-endorsement-guides.TEXT.txt` |
| NAD/NARB（美，自律） | Substantiating Advertising Claims: How-To Checklist | 3 步清单 | `R2/nad-guidance-substantiation-checklist.txt` |
| NAD（美，自律） | NAD 程序 / filing tracks / NARB procedures | 流程规则 | `R2/nad-process.txt`、`R2/nad-filing-tracks.txt`、`R2/nad-narb-procedures.txt` |
| NAD（美，自律） | NAD 案例库 + 年度报告 | 判例 + 统计 | `R2/nad-case-library.txt`、`R2/nad-annual-report-2025.txt` |
| ASA/CAP（英，自律） | The CAP Code + 健康 substantiation 建议 | 成文准则 + 专项建议 | `R2/The-CAP-Code.txt`、`R2/asa-ao-substantiation-health.html` |

【判断】注意这些体系的**组织形态差异**：FTC 是「按判定动作组织」（见 1.3.1），NAD 是「按流程步骤组织」（challenge → review → decision → referral），CAP 是「按编号条款组织」（rule-numbered code）。**客户规则库若要兼顾客服/运营可用性，应取 FTC 式（按判定动作）而非 CAP 式（按编号）**——因为编号式规则在跨市场复用时会因编号体系不同而无法对齐，而判定动作是跨体系同构的（1.2.1 已证三步顺序一致）。

#### 1.2.5 CRN：**公开的、按成分组织的规则库**（本次补抓，Q3.2 的直接命中）

Q3.2 点名要 CRN（Council for Responsible Nutrition）。**找到了，且它的形态回答了一个关键设计问题：真实的公开规则库按什么分支？**

【原文】（CRN Voluntary Guidelines/Best Practices 页面正文，逐字）
> "Voluntary guidelines and best practices are one of the hallmarks of CRN's self-regulatory efforts. Member companies are expected to follow government regulations and voluntarily adhere to a strong Code of Ethics."

> CRN Recommended Guidelines for Caffeine-Containing Dietary Supplements
> Voluntary Guidelines for Marketing and Labeling DHEA dietary supplements
> Best Practices Guide for Enzyme Dietary Supplement Products
> CRN Recommended Guidelines for Providing Product Information to Consumers Purchasing Dietary Supplements and Functional Food via E-commerce
> CRN Recommended Guidelines for Iodine Quantity in Multivitamin/Mineral Supplements for Pregnancy and Lactation
> Voluntary Guidelines for Marketing and Labeling Kava Dietary Supplements
> Recommended Guidelines for Formulation, Labeling, and Packaging of Melatonin-Containing Dietary Supplements for Sleep Support
> Best Practices for Probiotics
> Regulatory Responsibilities and Best Practices for Manufacturing and Marketing Dietary Supplements Containing Proprietary Blends
> CRN Guidelines for Labeling of Protein in Dietary Supplements and Functional Foods
> CRN Recommended Guidelines for SARMs‐Containing Dietary Supplements
> Recommended Guidelines for Labeling Gummy Dietary Supplements

来源：`_evidence/R7/w3/crn-voluntary-guidelines.txt`（行 151–164）
URL：https://www.crnusa.org/self-regulation/voluntary-guidelines-best-practices
FETCHED: 2026-09-15，HTTP: 200，BYTES: 90759
原始记录：`_evidence/R7/w3/fetchlog.tsv`

**CRN 的规则库结构（可枚举，共 12 份文档）：**

| 组织轴 | 实例 |
|---|---|
| **按成分** | Caffeine、DHEA、Enzyme、Iodine、Kava、Melatonin、Probiotics、Protein、SARMs |
| **按剂型** | Gummy Dietary Supplements |
| **按渠道** | E-commerce product information |
| **按配方形态** | Proprietary Blends |

【判断】**这是本分片对 Q3.1/Q3.2 最重要的结构发现之一**：CRN 的公开规则库**以「成分/剂型/渠道」为组织轴，而不是以「声明类型」为组织轴**。这与 FTC HPCG 的「按判定动作组织」（§1.3.1）形成**两种正交的规则库组织范式**：
- **FTC 范式（判定轴）**：`识别声明 → 需要什么证据 → 如何披露` —— 适用于**判定器**（做判断）。
- **CRN 范式（对象轴）**：`这是咖啡因 → 适用这份指南` —— 适用于**路由器**（找规则）。
- **两者不冲突，是流水线的两段**：先按对象路由（CRN 式）拿到适用文档集，再按判定动作逐条判（FTC 式）。
- 对客户的直接含义：**21 条规则若要扩到 100 条，必须同时建两个索引**——一个对象索引（成分/材质/功能/渠道），一个判定索引（声称类型/证据等级/披露要求）。只有判定索引会让运营找不到规则；只有对象索引会让规则无法执行。

【原文】（CRN Product Claims 页与 Supplement OWL）
> CRN 站点导航中含 "Product Claims" 项（路径 `/regulation-legislation/fda-ftc-regulations/product-claims`），归类于 "FDA/FTC Regulations" 之下。
> 另有 The Supplement OWL（Online Wellness Library）——一个产品标签登记库，路径 `/self-regulation/supplement-owl`。

来源：`_evidence/R7/w3/crn-product-claims.txt`（HTTP 200, 88605 bytes）、`_evidence/R7/w3/crn-about-substantiation.txt`（HTTP 200, 107678 bytes）、`_evidence/R7/w3/crn-supplement-owl.txt`（HTTP 200, 92713 bytes）
URL：https://www.crnusa.org/regulation-legislation/fda-ftc-regulations/product-claims
FETCHED: 2026-09-15

【判断 / 未完全核验】CRN 把 claim 规则放在「FDA/FTC Regulations」分支下，说明**CRN 自身也把 claim 规则的来源归为法源，而非自创标准**。CRN 的自创部分集中在**成分级 voluntary guidelines**。这一分工值得客户借鉴：**法源类规则（FDA cleared / medical device 等）走「法源引用」，自有类规则（品牌术语、安全词）走「成分/对象级指南」**。两条线不要混在同一个编号体系里。

【未逐字核验的项】`crn-product-claims.txt` 抓取成功（200）但正文抽取受该站 JS 导航结构干扰，本次**未取得该页的 claim 规则正文逐字引用**，仅确认其存在与归属分支。**不得**据此声称 CRN 公开了具体 claim 条目。这是一个明确的取证缺口，记入 §5。

#### 1.2.6 未能取得的一手体系（Q3.2 点名但未覆盖）

| 目标 | 状态 | 说明 |
|---|---|---|
| **BBB National Programs / NAD 主站** | **HTTP 403** | `https://bbbprograms.org/programs/all-programs/nad` 被拒（2026-09-15，本次补抓）。**但 NAD 的实质材料已在本地**：`_evidence/R2/` 有 40+ 个 NAD/NARB 文件（案例、程序、年度报告、digest），**不依赖主站可达**。见 §1.2.4 表。 |
| **NHC（National Health Council）** | **抓取 200，但无 claim substantiation 内容** | `https://nationalhealthcouncil.org/` 抓取成功（144852 bytes）。grep `substantiat` / `claim` 仅命中 "Real-World Evidence" 相关栏目（证据方法学教育，**不是** claim 规则库）。见 `_evidence/R7/w3/nhc-about.md`。**判定：NHC 不是 claim substantiation 规则库的来源。** |
| **CRN** | **部分取得** | 见 §1.2.5。指南**列表**取得（12 份），指南**正文**未取得。 |
| 竞品 claim 审查流程 | **未找到** | 见 §1.4.2。 |

【判断】Q3.2 点名的四个来源里，**FTC 是唯一完全可用的一手来源**（指南正文 + 政策声明 + 成文规则，全部本地可得）；NAD 可用（本地已有，仅主站被墙）；CRN 部分可用（有清单无正文）；NHC 经核验**不含** claim 规则库。这个排序本身就是对客户的一个交付结论：**不要指望「行业协会有现成的 claim 规则库可直接抄」——行业自律组织提供的是「成分级最佳实践」和「案例裁决」，骨架仍需自建。**

### 1.3 FTC 健康产品合规指南的结构解剖

**为什么解剖这份文件**：`Health Products Compliance Guidance`（2022-12，FTC staff 出品）是本调研范围内能找到的、**结构最完整**的健康品类规则库范本。它不是法条清单，而是一份**「判定器说明书」**：把「什么算声明」「声明需要什么等级的支撑」「什么限定词必须出现」拆成可枚举的维度。客户要从 21 条规则走向规则库，这份文件是结构参照的第一顺位。

#### 1.3.1 顶层骨架：四层 + 逐层可枚举

【原文】
```
I. Preface
II. Overview of Regulatory Framework
    A. FTC Authority over Advertising of Health-Related Products
    B. Coordination with FDA
    C. Key Differences Between FTC and FDA Law
III. Application of FTC Law to Advertising of Dietary Supplements and Other Health-Related Products
    A. Identifying Claims and Interpreting Ad Meaning
        1. IDENTIFYING EXPRESS AND IMPLIED CLAIMS
        2. WHEN TO DISCLOSE QUALIFYING INFORMATION
        3. CLEAR AND CONSPICUOUS DISCLOSURE
    B. Substantiating Claims
        1. ADS THAT REFER TO A SPECIFIC LEVEL OF SUPPORT
        2. THE AMOUNT AND TYPE OF EVIDENCE
        3. THE QUALITY OF THE EVIDENCE
        4. THE TOTALITY OF THE EVIDENCE
        5. THE RELEVANCE OF THE EVIDENCE TO THE SPECIFIC PRODUCT AND CLAIM
    C. Other Advertising Issues
        1. CLAIMS BASED ON CONSUMER TESTIMONIALS OR EXPERT ENDORSEMENTS
        2. CLAIMS BASED ON TRADITIONAL USE
        3. USE OF THE DSHEA DISCLAIMER IN ADVERTISING
        4. MISCHARACTERIZATIONS OF FDA APPROVAL
        5. THIRD-PARTY LITERATURE
IV. Conclusion
```
来源：`_evidence/R5/ftc/ftc-health-products-compliance-guidance-2022-12.PDFTEXT.txt`（行 11–1150）
URL：https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance

【判断】这份目录本身就是一份**规则库的轴设计**，可直接映射为客户规则的四个字段族：
- III.A = **判定轴**（这条文案到底在声称什么）：express / implied / qualifying-info-required / clear-and-conspicuous —— 四个可独立取值的子维度。
- III.B = **证据轴**（这个声称需要什么等级的证据）：level-of-support-claimed / amount / quality / totality / relevance —— 五个正交子维度。
- III.C = **特殊机制轴**（不走常规证据链的例外通道）：testimonial / traditional-use / disclaimer / FDA-approval / third-party-literature。
- 全部 14 个末级小节标题**都是问句的答案形式**，没有一个末级节点是「某国某法第 X 条」。这是「按判定动作组织，不按法源组织」的范本。

#### 1.3.2 结构性关键：FTC 明确拒绝「按品类分档」

这正是 Q3.1「同一卖点在 A 国可说、B 国不可说」问题的**上游答案**——FTC 在自己的框架里**主动取消了品类分档**：

【原文】
> "FTC advertising law applies to all products and claims.  Unlike FDA law, FTC law makes no bright-line distinctions between categories of health-related products or claims.  For example, provisions in the Dietary Supplement Health and Education Act of 1994 (DSHEA) regarding 'structure/function' claims in labeling don't govern the FTC's assessment of those claims in advertising.  The FTC follows the same basic steps when evaluating any health-related claim regardless of whether, under FDA law, the claim would be considered a health claim, a structure/function claim, or a drug claim.  Similarly, the FTC's approach to advertising of health-related products is the same regardless of whether, under FDA law, the product is considered a food, a supplement, or a drug."

来源：`_evidence/R5/ftc/ftc-health-products-compliance-guidance-2022-12.PDFTEXT.txt`（行 105–113）
URL：https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance

【判断】这一条对客户规则库的设计取向有直接后果：**成熟的健康品类规则库不按「产品品类」分支，而按「声明类型 + 证据等级」分支**。品类差异只在两处进入规则库——(a) 该品类是否被允许做某类声明（合法性前置门槛，见 1.3.3 的 FDA 协调段），(b) 专家对该品类的证据规范要求（见下）。这解释了为什么客户的 12 字段里如果以「品类」为强分支维度，会得到一个极稀疏且不可维护的矩阵。

#### 1.3.3 「限定词」是一等公民，且有明确触发条件

Q3.1 问「分国别文档？表格？限定词？」——FTC 给出的答案是**限定词（qualifying information）+ 明示触发条件 + 明示呈现标准**，三层齐全：

【原文】
> "An ad also can be deceptive because of what it fails to say.  Under Section 15 of the FTC Act, an ad is misleading if it fails to disclose information that is material in light of the claims in the ad or with respect to how consumers would customarily use the product.  Thus, if the ad would be misleading without certain key qualifying information, that information must be disclosed.  For example, advertisers should disclose any significant limitations on an advertised health benefit.  Similarly, advertising that makes either an express or implied safety representation should include information about any significant safety risks.  Even absent affirmative safety representations, advertisers may need to inform consumers of significant safety concerns related to the customary use of a product."

来源：`_evidence/R5/ftc/ftc-health-products-compliance-guidance-2022-12.PDFTEXT.txt`（行 215–224）
URL：https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance

【原文】
> "When the disclosure of qualifying information is necessary to prevent an ad from being deceptive, advertisers should present the information clearly and conspicuously, so it is difficult to miss (i.e., easily noticeable) and easily understandable by ordinary consumers.  If the claim requiring a disclosure is made both visually and audibly, the disclosure should be made both visually and audibly; if the claim is made just visually or just audibly, the disclosure should at least appear the same way the claim is made, but a simultaneous visual and audible disclosure is more likely to be clear and conspicuous.  A visual disclosure should stand out and, based on its size, contrast, location, the length of time it appears, and other characteristics, it should be easily noticed, read, and understood.  An audible disclosure should be delivered in a volume, speed, and cadence so that it can be easily heard and understood.  In social media, the internet, and other interactive media, the disclosure should be unavoidable; disclosures made through [hyperlinks are inadequate]."

来源：`_evidence/R5/ftc/ftc-health-products-compliance-guidance-2022-12.PDFTEXT.txt`（行 262–273）
URL：https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance
（注：末句方括号处原文在 PDF 文本抽取中被分页截断于 "[PAGE 10]"，方括号内为**跨页续读标注**，非原文引用，勿直接转引。）

【判断】可操作结构：一条「限定词规则」在 FTC 范式下至少含 4 个槽位——①**触发条件**（什么声明出现时必须披露）、②**披露内容**（什么限制/风险）、③**呈现要求**（size / contrast / location / duration / unavoidable）、④**通道一致性**（visual claim→visual disclosure）。客户现有 12 字段中若只有「规则文本 + 严重度」而无这 4 槽位，则限定词类规则**无法被机器执行**，只能做人审提示。这是 §3 处方的一个具体输入。

#### 1.3.4 证据等级：一张可枚举的「证据强度阶梯」

FTC 没有给数字阈值，但给了一个**次序明确的阶梯**，这是「规则库如何表达强度」的范例：

【原文】
> "Randomized, controlled human clinical trials (RCTs) are the most reliable form of evidence and are generally the type of substantiation that experts would require for health benefit claims.  Although there is no requirement for a specific number of RCTs, the replication of research in an independently-conducted study adds to the weight of the evidence."

> "Epidemiological or observational studies can be valuable to show an association between a product or ingredient, but they don't prove a causal link.  Methodologically sound human clinical testing is necessary to prove causation, although there may be limited situations where such testing may not be feasible."

> "Animal and in vitro studies may provide useful supporting or background information, but, without confirmation by human RCTs, they aren't sufficient to substantiate health-related claims."

> "Anecdotal evidence about the individual experiences of consumers, including surveys of consumer experiences, are never sufficient to substantiate claims about the effects of a health [product]."

来源：`_evidence/R5/ftc/ftc-health-products-compliance-guidance-2022-12.PDFTEXT.txt`（行 438–444, 449–453, 456–458, 465–466）
URL：https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance

【判断】阶梯次序：`RCT（+独立重复） > 高质量流行病学（仅在 RCT 不可行且领域接受时可替代） > 动物/体外（仅支撑，不构成 substantiation） > 消费者轶事/问卷（"never sufficient"）`。注意最后一档用的词是 **never**——这是**绝对禁止档**。规则库中「绝对禁止」与「需要更高证据」是两种不同的动作（reject vs. require-evidence），FTC 用词明确区分了二者。

#### 1.3.5 「声称自己有证据」本身是一条独立规则

这是最容易被客户规则库漏掉、但结构上极干净的一类：

【原文】
> "As a starting point, marketers of health-related products must have at least the level of support that they claim to have.  In other words, in addition to meeting the basic requirement that any objective claim about safety or efficacy must be substantiated, the marketer also must ensure that any assertion about the amount, type, or strength of evidence is accurate."

来源：`_evidence/R5/ftc/ftc-health-products-compliance-guidance-2022-12.PDFTEXT.txt`（行 402–405）
URL：https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance

【判断】此规则触发词族包括 `clinically proven`、`studies show`、`scientifically tested`、`doctor recommended` 等**元声明（meta-claim）**。它的判定不依赖产品是否真的有效，只依赖「所声称的证据等级 ≤ 实际持有的证据等级」。对客户而言这是一条**低成本高收益**的规则：字段需求仅「证据持有等级」+「文案声称等级」，比较即可判，无需理解医学。

#### 1.3.6 `FDA cleared` 类声明的处理结构（直接命中 Q3.1 的举例）

FTC 把「监管状态词」单列一节，并给出**「监管状态词 + 邻近功效宣称」= 欺骗**的结构：

【原文】
> "Advertisers should be careful not to mischaracterize the extent to which a product or claim has been reviewed, authorized, or approved by the FDA.  For instance, compliance with the DSHEA notification and disclaimer provisions doesn't constitute FDA authorization, and advertisers shouldn't imply that the FDA has specifically approved any claim on that basis.  Nor should advertisers mischaracterize or overstate any FDA assessment of the science supporting a particular claim."

> "Example 49: The marketer of an electronic 'ab sculpting' belt receives clearance from the FDA to sell the product as a Class II medical device for the intended purpose of stimulating and strengthening healthy muscle.  The marketer airs an infomercial for the device with repeated references to the fact that the product is 'FDA Approved,' alongside claims that 'in just 10 minutes a day for 30 days, you can effortlessly lose two or more inches and 10 pounds from your waist.'  The infomercial is deceptive because the juxtaposition of the 'FDA Approved' reference and claims about weight loss and reduction in waist circumference gives the impression that the FDA has found the product to be effective for such dramatic effects."

> "Example 48: ... Ads for the shake feature a prominent banner stating, 'Meets FDA Qualified Health Claim.'  By using a technical regulatory term unfamiliar to most consumers, the banner mischaracterizes the FDA's action and likely communicates both FDA approval of the product for heart disease and a high level of supporting evidence.  Use of the banner in advertising is deceptive."

来源：`_evidence/R5/ftc/ftc-health-products-compliance-guidance-2022-12.PDFTEXT.txt`（行 1065–1071, 1079–1088, 1072–1078）
URL：https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance

【判断】这是**跨市场卖点差异的机器可判形式**，也是本分片最重要的结构发现之一：
- 违规点**不在** `FDA cleared` 这个词本身，而在**它与其他宣称的「并置（juxtaposition）」**。
- 因此规则不能写成「禁止出现 X 词」的黑名单条目（那会漏掉合法用法、又把非法用法当成词表问题），必须写成 **①监管状态声明 × ②邻近功效宣称 的配对规则 + ③适用范围一致性检查**（clearance 的 intended purpose 是否覆盖被宣称的用途）。
- Example 49 的结构即：`clearance 的 intended purpose = stimulate/strengthen healthy muscle`，`广告宣称 = lose inches and 10 pounds` → 用途不匹配 + 并置暗示 → 欺骗。
- 客户母婴品类中的 `hospital grade`、`medical device`、`FDA cleared`、`FDA registered` 全部属于这一类「监管状态词」。它们的规则形态应当是**配对 + 范围检查**，而非关键词拦截。

#### 1.3.7 「第三方文献」与「免责声明」各有独立机制

【原文】
> "The FTC doesn't regulate the content or accuracy of statements made in independently written and published books, articles, or other non-commercial literature.  The FTC does, however, prohibit the deceptive use of such materials in the marketing of products."

来源：`_evidence/R5/ftc/ftc-health-products-compliance-guidance-2022-12.PDFTEXT.txt`（行 1095–1098）
URL：https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance

【判断】「不监管内容、但监管其在营销中的使用」是**引用类内容**的通用规则骨架：规则判定对象从「文本本身」转移到「文本在商业语境中的放置方式」。对客户的直接含义：KOL 引用、媒体报道截图、论文摘要截图，需要独立的规则族（放置语境规则），不能复用普通文案规则。

【本节未逐字核验的两节】FTC HPCG 的 `III.C.2 CLAIMS BASED ON TRADITIONAL USE`（行 965）与 `III.C.3 USE OF THE DSHEA DISCLAIMER IN ADVERTISING`（行 1043）两节的正文**本次未逐字引用**（预算约束）。它们对应「传统使用」与「免责声明」两条独立机制。**R5 §6.3 已就免责声明给出更强的结论，可直接引用而不必回读 HPCG**：
> （R5 §6.3 标题逐字）"免责声明不能治愈欺骗：豁免词字段的法源问题"
即：**免责声明不是许可证**。这解释了为什么 HPCG 把 DSHEA disclaimer 单列一节而不是并入 substantiation——免责声明本身也是一条需要被审的声称，而不是豁免。

### 1.4 竞品公开合规声明

**本节结论：竞品的「claim 行为」有大量一手证据；竞品的「claim 审查流程 / 合规规则」——未找到。**

Q3.3 要求：找不到就明写「未找到」，不要编造。以下逐项记录取证动作与结果。

#### 1.4.1 claim 表述行为：**找到**（证据充分）

七个品牌（Elvie / Willow / Medela / Lansinoh / Spectra / BabyBuddha / Momcozy）在 2026-09-15 的官网产品页文案，R5 已建立逐字对照表，覆盖 6 个卖点（奶量、舒适/疼痛、效率/排空/漏奶、静音、贴合/尺寸、医院级）。证据在 `_evidence/R5/competitors/`（含 `/products.json` 目录级 dump：Spectra 47 / BabyBuddha 43 / Momcozy 405 个产品）。

R5 §7.1「样本与方法」给出七行逐品牌取证表（品牌 / 抓取页面数 / 抓取方式 / 抓取日，抓取日均为 2026-09-15）。其取证完整性自检逐字如下：

【原文】
> "**取证完整性说明（来自抓取方的自检）**：Medela + Lansinoh 的 19 页共 334 个页面文本片段，机械复核 **325/334 逐字命中**，其余 9 条为标注/分隔符。抓取方在自检中**纠正了自己草稿里的两处真实错误**（一处是给 `<title>` 错误追加了 "| Medela"，一处是脚注 `®` 前后空格）。**未发现捏造**。"

> "**未取到的来源**：Medela 没有独立的 "Swing" 产品页（只有 Swing Maxi）；`increase milk`、`pediatrician recommended`、`natural let-down`、`recommended by` 四个字符串在 Medela+Lansinoh 的 19 页里**出现次数为 0**；Lansinoh 全部 10 页**没有任何临床引用**。"

来源：`research/governance/R5-category-and-competitors.md` §7.1（该节含七行逐品牌抓取表）

来源：`research/governance/R5-category-and-competitors.md` §7.1、`_evidence/R5/competitors/FETCH-LOG.txt`

#### 1.4.2 legal / terms / claims / compliance 页面：**未找到**（本次主动补抓，全部失败）

**本条是本分片新做的取证动作**（R5 的 FETCH-LOG 中**没有**任何 legal/terms 页抓取记录，grep 命中 0，见 `_evidence/R5/competitors/FETCH-LOG.txt`）。本次以 Safari 17 UA 补抓：

| 目标 | URL | HTTP | 结果 |
|---|---|---|---|
| Elvie legal | `https://www.elvie.com/pages/terms-conditions` | **404** | 无此页 |
| Elvie claims | `https://www.elvie.com/pages/legal` | **404** | 无此页 |
| Willow legal | `https://www.willowpump.com/pages/terms-of-service` | **403** | 拒绝 |
| Medela legal | `https://www.medela.us/terms-of-use` | **404** | 无此页 |
| Lansinoh legal | `https://www.lansinoh.com/pages/terms-of-use` | **404** | 无此页 |
| Spectra legal | `https://www.spectrababyusa.com/pages/terms-of-service` | **404** | 无此页 |
| Legendairy Milk 首页 | `https://legendairymilk.com/` | 200 | **无** compliance / claims / legal 段落 |
| Freemie 首页 | `https://freemie.com/` | 200 | **无** compliance / claims / legal 段落 |

抓取日期：2026-09-15。原始记录：`_evidence/R7/w3/fetchlog.tsv`（本分片产出，一源一行：name / HTTP code / bytes / URL）
文件：`_evidence/R7/w3/elvie-legal.md`、`elvie-claims.md`、`willow-legal.md`、`medela-legal.md`、`lansinoh-legal.md`、`spectra-legal.md`、`legendairy-home.md`、`freemie-home.md`

**【判断 / 未找到】**：
1. **七个品牌中，没有一家在公开站点上提供「claim 规则」「合规规则」「substantiation 政策」页面。** 抓到的 404 说明这些品牌**没有**按 `legal` / `terms` 路径发布合规规则文档；403 的 Willow 无法判定（需登录或 UA 策略拒绝），但即使用户可见，其 `/pages/terms-of-service` 按该路径命名惯例是**通用服务条款**，而 R4/R5 已多次证实通用条款不构成 claim 规则。
2. **未找到任何竞品的「索赔审查流程」**（claim review workflow）：没有 SOP、没有审查清单、没有审批层级、没有 reviewer role 描述。
3. **未找到任何竞品的「分国别 claim 规则文档」**（见 §1.1 开头结论）。
4. **未找到 Legendairy Milk 与 Freemie 的任何合规表述**：两者的抓取结果（Legendairy 16,217 字节、Freemie 5,274 字节正文）中 `hospital`、`compliance`、`disclaimer`、`legal` 命中 **0**。

【判断】这是一个**重要的负面发现**，且具有直接设计含义：**claim 合规在这个品类里是「不公开的竞争暗能力」，不是「公开的行业标准」。** 因此：
- **不能靠「抄竞品的合规做法」来建规则库**——竞品公开的信息只有「文案结果」，没有「判定依据」。可抄的是 §1.1 的三个**表达机制**（限定词内嵌、数值锚定、术语表），不是规则本身。
- **客户若建立规则库并公开其结构（哪怕只公开术语表），在品类内是领先位置。** 这与 R5 §7.7 的判断一致——Momcozy 官网那段 hospital grade Q&A 被 R5 评为「**品类内唯一一家把这件事讲清楚的品牌**」。

#### 1.4.3 竞品的合规「行为证据」：可从法源侧反推

虽然竞品不公开规则，但**它们的合规状态可由外部裁决记录反推**。R2 目录中已有三份**营养/母婴相邻品类**的 NAD 案例：

| 案例文件 | 品类 | 说明 |
|---|---|---|
| `_evidence/R2/nad-case-1-kendamil.txt` | **婴幼儿配方奶粉**（Kendamil） | 与母婴品类直接相邻 |
| `_evidence/R2/nad-case-2-nanit.txt` | 婴儿监视器（Nanit） | **母婴硬件** |
| `_evidence/R2/nad-case-3-hims-hers.txt` | 女性健康/DTC（Hims & Hers） | 女性健康品类 |

来源：`_evidence/R2/nad-case-*.txt`，URL 前缀 `https://bbbprograms.org/`（具体案例页 URL 见各文件头 `SOURCE_URL`）
另存有 NARB 决定：`_evidence/R2/narb-decision-1-kendal.html`、`narb-decision-2-tmobile-compliance.html`

【判断】这三个案例的存在本身就是 Q3.3 的一个间接答案：**竞品的 claim 审查流程不公开，但竞品的 claim 争议是公开裁决的。** 对客户规则库而言，**NAD 案例库是比竞品官网更有价值的规则来源**——因为案例同时给出「被挑战的文案原文」+「裁决理由」+「要求采取的整改动作」，这三个恰好是规则库的三要素（触发文本、判定依据、处置动作）。详见 §2.2 的来源排序。

#### 1.4.4 **补强证据：Amazon Ads 把「母婴喂养」列为与「医疗健康」并列的独立政策类目**

Q3 问「母婴品类」的规则参照是否存在。同一 Amazon Ads 政策页的 `Related topics` 清单为此提供了一个直接证据（逐字）：

【原文】（`Related topics` 部分，按原顺序）
> "Alcohol / Animal related products and services / Dating and related services / Charities / Employment and Recruitment / Entertainment and books / Financial products and services / Gambling and games / Real estate / **Healthcare products and services** / **Baby formula and feeding accessories** / Pricing and Promotions / Public service announcements / News and journalism / Sports and outdoors products / Event days"

来源：`_evidence/R1/amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.html`（及解码抽取件 `_evidence/R1/amazon-ads-claims-substantiation-country-restrictions.md` 尾部）
抓取日期：2026-09-15

【判断】**`Healthcare products and services` 与 `Baby formula and feeding accessories` 在同一个平铺列表中是两个并列条目——不是父子关系。** 这对客户的品类建模是一个直接证据：**平台侧不把母婴喂养归入医疗健康，而是与之并列。** 其含义是：客户的「母婴品类」规则**不能通过继承「健康品类」规则得到**，两者有各自独立的政策面（尽管在 claim substantiation 上共享同一页，因为该页自称 "This policy covers general claims, including books and healthcare"）。

【本节缺口】本次**未逐字引用**这三份 NAD 案例的裁决理由（受预算约束，仅确认存在与品类归属）。后续分片应补读 `nad-case-1-kendamil.txt` 与 `nad-case-2-nanit.txt`，提炼母婴品类的具体红线。

---

## 2. 冷启动路径

> **与 R4 的分工**：R4 §6 已从**平台/标准体系**角度回答「没有规则时的官方默认动作」（NIST MAP、Ofcom 四步、COM(2000)1 预防原则），R4 §7.4 给出**第一个月 SOP**。本节的 Q4 是**不同的问题**：不问「默认动作是什么」，而问「**第一条规则写哪一条**」「**0→100 的规则从哪来、按什么顺序**」「**多少条够用**」「**没覆盖的部分怎么记账**」。四问均落在**规则库内容本身**，不重复 R4。

### 2.1 第一条规则是什么（真实案例）

**结论：四个独立体系的第一条规则，收敛到同一个形态——都不是「某条内容规则」，而是「路由 + 兜底」。**

#### 2.1.1 案例 A：Amazon Ads 的 "Claims and substantiation"（最干净的一手样本）

Amazon Ads 的 claim 政策页结构（逐字，`Updated on Jan 28, 2026`）：

```
Claims and substantiation
On this page
  Policy requirements
  Prohibited content
  Restricted content
  Country-specific restrictions
Updated on Jan 28, 2026
```

而 `Policy requirements` 一节**只有一条规则，一句话**：

【原文】
> "Advertisers are required to ensure the accuracy of claims and provide factual substantiation if requested by Amazon."

来源：`_evidence/R1/amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.md`
URL：https://advertising.amazon.com/resources/ad-policy/claims-and-substantiation （页内 source 标注为 Amazon Ads support policy，抓取 2026-09-15）
原始 HTML：`_evidence/R1/amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.html`（238,994 bytes）

【判断】**第一条规则是一条「举证责任分配规则」，不是内容规则。** 它的构件只有两项：
1. **义务主体**（Advertisers）
2. **举证触发条件 + 举证动作**（"if requested by Amazon" → "provide factual substantiation"）

它**没有**规定任何具体声称是否允许——那是后面 `Prohibited content` / `Restricted content` 两节的事。**第一条规则的作用是把举证责任先钉在广告主身上，从而使后续所有内容规则都变成「可要求举证」的。** 这是冷启动顺序的一个强论据：**先有举证责任条款，后有内容条款。**

注意 `Updated on Jan 28, 2026` 这个字段：**规则库有版本日期**。这与客户现状（无版本号）对比鲜明。

#### 2.1.2 案例 B：NAD 三步清单——第一步是「确定产品落在哪个制度下」

见 §1.2.1，NAD 的 Step One 是 "Consider the Product"，先做监管归类，**再**看声明。这是同一结论的第二个独立证据。

#### 2.1.3 案例 C：FTC HPCG——两条原则，第一条是「真实不误导」，第二条才是「事前举证」

【原文】
> "Sections 5 and 12 of the FTC Act, along with the FTC's policy statements on deception and advertising substantiation, are the foundation of FTC truth-in-advertising law, and can be distilled down to two common-sense principles:
> 1. Advertising must be truthful and not misleading; and
> 2. Before disseminating an ad, advertisers must have adequate substantiation for all objective product claims conveyed, expressly or by implication, to consumers acting reasonably."

来源：`_evidence/R5/ftc/ftc-health-products-compliance-guidance-2022-12.PDFTEXT.txt`（行 38–43）
URL：https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance

【判断】原则 2 的关键词是 **"Before disseminating"**——**时点是「发布前」**。这与 Amazon 的 "if requested"（**事后**被要求时举证）**方向相反**。两者的组合给出一个可用于规则库的判据：**法源要求事前持有，平台要求事后提供**。这意味着客户的规则库应为每条「证据类规则」记两个字段：`要求持有时点` 与 `举证对象`。

#### 2.1.4 案例 D：YouTube 划线法——第一条规则必须自带「正反样例对」

【原文】
> "Then we **watch dozens or even hundreds of videos** to understand the implications of drawing different policy lines. **Drawing a policy line is never about a single video; it's about thinking through the impact on all videos**, which would be removed and which could stay up under the new guideline. Following this comprehensive review, the team shares **various options for policy lines, making sure to detail examples of videos that would be removed or approved for each**."

来源：`_evidence/R4/youtube-policy-development.html` / `.txt`（YouTube 官方博客 *On policy development at YouTube*）
URL：https://blog.youtube/inside-youtube/policy-development-at-youtube/
（转引自 `research/governance/R4-trust-and-safety-ops.md` §1.1，抓取 2026-09-15）

【判断】这是 Q4.1 的**方法学答案**：YouTube 不先写规则文本，而是先看样本、再出**多条候选线**、每条候选线**必须附「会被删的样例」与「会被留的样例」**。换算到客户的冷启动：**第一条规则的产出物不是一行规则文本，而是「一行规则文本 + 1 个正例 + 1 个反例」**。R4 §7.4 第 2 周（D6–D8）已把这个动作排进 SOP。

#### 2.1.5 第一条规则的四案例收敛

| 体系 | 第一条规则 | 形态 |
|---|---|---|
| Amazon Ads | "Advertisers are required to ensure the accuracy of claims and provide factual substantiation if requested by Amazon." | **举证责任分配** |
| NAD | "Step One: Consider the Product" | **路由/归类** |
| FTC HPCG | "Advertising must be truthful and not misleading" + "Before disseminating… substantiation" | **总则（事前）** |
| YouTube 划线法 | 先看样本 → 多候选线 → 每条附正反样例 | **方法（不可跳过）** |

【判断 / 本节结论 —— 对客户「第一条规则应该是什么」的回答】：

**第一条规则应当是「未命中即转人工」的兜底路由规则，而不是任何一条内容红线。** 理由由四个案例共同支撑：
1. 客户现状的最大问题**不是「漏了某条红线」**，而是**规则表把「判违规」与「找位置」混在一起**（内部审计：正则层 13.8% 复现率、**从不多报一条**、94/130 条零复现）。
2. 在 precision/recall 未知时，任何新增内容规则都**同时增加 FP 与 FN**，且**无法度量**（R4 §5.4：覆盖率无标准定义）。
3. 四个体系的第一个动作都是**建立「归属判定」与「举证责任」**，而非「内容对错」。
4. R4 §7.4 已独立给出同一建议：上线兜底规则 `CATCH-ALL-01`（未命中 → `未覆盖` → 转人工，不再自动判「合规」）。

**因此第一条规则的推荐文本形态**（三段式，对齐 Amazon 与 FTC 的构件）：
```
规则编号：CATCH-ALL-01
触发：所有未被其他规则命中的内容
判定：未覆盖（不得判为合规）
动作：转人工复核，并落库为「规则库缺口」记录
依据来源：Amazon Ads Claims and substantiation — Policy requirements（举证责任条款）
```
**关键点**：这条规则的价值在于**把「未覆盖」从一个隐性状态变成一个可计数的事件**。客户现状中「20.3% 记录引擎看不到」「6 条规则零命中」这类事实之所以现在才被发现，正是因为缺这条规则。

### 2.2 0 → 100 条的来源排序

#### 2.2.1 来源层级（按权威性 × 可执行性排序）

客户的规则库要从 21 条扩到 100 条，问题不是「去哪找 79 条」，而是「**按什么顺序找，才能让每一条都站得住**」。R5 §9.2/§9.3 已经为客户现有条款做过一次区分，本节把它推广为通用的四层来源模型：

| 层 | 来源 | 权威性 | 可执行性 | 客户品类实例 | 客户已有义务 |
|---|---|---|---|---|---|
| **L1 法源** | FTC HPCG / FTC 1984 substantiation / FTC Deception 1983 / 16 CFR 255 / FDA 21 CFR 884.5160 / EU MDR 2017/745 / UCPD 2005/29 / Reg 1924/2006 / MHRA / 中国广告法 | **最高** | 高（条文可引） | `FDA cleared` vs `approved`、`medical device` 分类、`BPA-free`、`LFGB` | 直接引用条款号 |
| **L2 平台政策** | Amazon Ads claims & substantiation / Amazon 品类政策 / Meta / Google Ads / TikTok | 高（**商业后果最直接**） | 高 | Amazon 禁竞品直比、Amazon 澳站禁疾病声称、TikTok 医疗器械分国禁对比 | 引用政策页 + 抓取日期 |
| **L3 裁决案例** | NAD / NARB / ASA / SAMR 处罚案例库 | 中（个案约束） | 中（需提炼） | `nad-case-1-kendamil`（婴配粉）、`nad-case-2-nanit`（婴儿监护器）、`nad-case-3-hims-hers`（女性健康） | 提炼「文案原文 + 裁决理由 + 整改要求」三元组 |
| **L4 内部错题本** | 客户 291 条记录 / 命中片段 / 人工复判分歧 | **最低** | 低（需清洗） | 3 位 Copywriter 脑中的 5 语种词表 | 先落库再成为规则 |

#### 2.2.2 各阶段的来源配比与理由

| 阶段 | 规则量 | 主来源 | 次来源 | **此阶段不要碰的来源** | 理由（带证据） |
|---|---|---|---|---|---|
| **P0 兜底** | 1 条 | L1（举证责任）/ 自建 | — | **不要碰 L4** | 见 §2.1.5。L4 是待清洗的原始数据，冷启动期用它建规则会把噪声写入规则库 |
| **P1 法源锚定** | 1 → ~15 条 | **L1** | — | **不要碰 L3/L4** | L1 条款有明确文本与编号，**可穷尽**且**不需要判例解释**。客户现有 21 条中，R5 §9.2 已确认相当一部分可直接引用法源（`依据来源` 字段填法见 R5 §9.2） |
| **P2 平台对齐** | ~15 → ~40 条 | **L2** | L1 | 仍不要碰 L4 | 平台政策**有抓取日期可考**、**有国别字段**（见 §2.2.3），且**后果最直接**（封号/拒登）。R5 §8 已为客户取得四个平台的正文 |
| **P3 案例填充** | ~40 → ~70 条 | **L3** | L2 | L4 仅作对照 | L3 提供 L1/L2 无法覆盖的**边界样例**（同一句话在什么语境下变成违规）。R5 §9.3 明确指出「哪些条款没有法源、必须靠案例积累」 |
| **P4 内部萃取** | ~70 → 100 条 | **L4** | L3 | — | 此时规则库已有 L1–L3 作为「校准锚」，L4 的多语种词表与人工判定才可被**有参照地**转成规则，而非直接把隐性知识固化 |

【判断】**这个排序的核心原则是「先可穷尽的，后可积累的」**：
- L1 与 L2 是**有限集合**（法条有编号、政策页有列表），**可以宣布「查完了」**。
- L3 与 L4 是**开放集合**，永远查不完。
- 因此冷启动的正确停止条件不是「规则够了」，而是「**可穷尽的两层已穷尽**」。见 §2.3。

#### 2.2.3 一个必须同时建的索引：来源 × 国别

**来源排序之外，客户还需要一个正交的国别索引。** 本次补抓取得了一手样本——**Amazon Ads 用「页面内的国别覆写表」处理跨市场差异，而不是分国别文档**：

【原文】（Amazon Ads "Claims and substantiation" → `Country-specific restrictions`，逐字）
> **Austria, Belgium, Bulgaria, Croatia, Cyprus, Czechia, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Poland, Portugal, Romania, Slovakia, Slovenia, Spain, and Sweden**
> "Energy-Efficiency Labels are required on large electric appliances. Advertisers are responsible for ensuring energy-efficiency labels are present in their ads and compliant with the laws in their locale; Amazon will reactively remove any noncompliant ads reactively. Amazon will ensure that ASIN-based ads have compliant labels; products may be blocked from some ads placements until auto-labeling is developed for that placement."

> **Brazil**
> "Any products described as 'organic' must include the logo on the product packaging. Any consumable described as 'diet' 'sugar free' 'low sugar' 'light' or similar must include the same claim on the product packaging."

> **Singapore**
> "Any product described as 'organic' must include a 'certified organic' logo on the product packaging."

> **United Kingdom**
> "Energy-Efficiency Labels are required on large electric appliances. …"
> "**For substantiation of health-related efficacy claims made in the UK marketplace, advertisers have the option of either conforming to the worldwide policy outlined above, or, instead of providing a study and date, they can provide a PO box mailing address or manufacturer email address for consumers to have a means of contacting the advertiser. Example: "For verification, please email manufacturerXYZ@gmail.co.uk."**"

来源：`_evidence/R1/amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.html`（HTML 内嵌 JSON，`Country-specific restrictions` 展开段；文件内偏移约 134,167 字节处）
**解码抽取件（本次新增，供逐字复核）**：`_evidence/R1/amazon-ads-claims-substantiation-country-restrictions.md`
页面 URL：Amazon Ads 政策中心 "Claims and substantiation"
抓取日期：2026-09-15（页内 JSON 字段 `"lastModified":"2026-01-28T19:49:38.706Z"`，与页面显示的 `Updated on Jan 28, 2026` 一致）

> **⚠️ 取证方法学警告（必须随本发现一并转述）**
> Amazon 把国别正文放在**客户端折叠组件**里（页面含 `Collapse all` / `Expand all`）。这导致**文本层抽取（`read_page`/`web_fetch` 产出的 `.md`，4565 字节）只含国名，不含国别正文**——`.md` 里 `Country-specific restrictions` 下只有四个折叠标题。
> **但正文确实存在于原始 HTML 中**（作为页面内嵌内容 JSON 的转义字符串）。字节级复核（直接对 `.html` 计数）：
> `mailing address` → **1**；`study and date` → **1**；`PO box` → **1**；`email address` → **1**；`For substantiation of health-related efficacy` → **1**。
> **为什么朴素 grep 会报 0 命中**：该内容位于原始 HTML 的**第 1336 行，行长 11,371 字符**（全文件最长行 29,989 字符）。**部分 grep 封装会跳过超长行**，从而产生「不存在」的假阴性。
> **因此：本发现的复核必须针对 `.html`（或本次新增的解码抽取件），不能针对 `.md`。** 这一条同样适用于 Amazon 的**所有** Seller Central / Ads 政策页——它们的正文普遍以转义 JSON 形式内嵌。

**同一 HTML 中恢复出的结构化元数据（逐字，可直接用于规则库设计）**：
> `"lastModified":"2026-01-28T19:49:38.706Z"`
> `"content_status" : [ "Active" ]`
> `"vertical" : [ "Claims and Substantiation" ]`
> `"role" : [ "AdSu", "SP&S", "AT Policy", "Client-facing", "Moderation", "Product" ]`
> `"country_reqs" : [ "Austria", "Belgium", "Bulgaria", "Croatia", "Cyprus", "Czechia", "Denmark", "Estonia", "Finland", "France", "Germany", "Greece", "Hungary", "Ireland", "Italy", "Latvia", "Lithuania", "Luxembourg", "Malta", "Netherlands", "Poland", "Portugal", "Romania", "Slovakia", "Slovenia", "Spain", "Sweden", "Brazil", "Singapore", "United Kingdom" ]`
> `"ancestors"`：`"Restricted categories"` → `"Policies and guidelines"` → `"Support Center Homepage"`
> `"shortdesc" : "Learn how to ensure that advertising claims are accurate and provide substantiation when required."`

【判断】**`country_reqs` 是一个 30 元素的显式数组——平台自己把「哪些国家有覆写」做成了一个机器可读字段。** 这是对 §2.2.3 结论的最强佐证：**国别覆写不是散文，是一个结构化列表。** 另外 `role` 字段里有 `"Moderation"` 与 `"AT Policy"`，说明同一份政策文本同时供给**机器审核**与**政策团队**两类消费者——客户规则库若要同时服务 Agent 与人工，这个字段划分可参照。

【判断】**这是 Q3.1 最锋利的答案，而且推翻了一个常见假设**：

1. **形态是「页面内嵌的国别覆写表」，不是「分国别文档」。** 默认值 = "the worldwide policy outlined above"；国别条目 = **对默认值的覆写**。
2. **EU-27 被合并为一个条目**（27 国共用一段），而不是 27 份文档。这说明**在规则库里，国别不是最细的分支键**——`（平台 × 法域块）` 才是。
3. **★ 国别覆写可以是「放松」，不只是「加严」。** 英国条目明确给出一个**二选一的替代方案**：可以不提供 study + date，改为提供一个可供消费者联系的邮寄地址或厂商邮箱。这是一个**举证强度降档**。**天真的模型是「B 国更严所以不能说」，真实结构是「国别覆写可以在两个方向上都发生」。** 这直接改变了客户规则库的判定形态：国别字段不能只做「禁止」，必须能做「替换证据要求」。
4. **它给了规则一个「证据时效」字段，且逐声称类型取值不同。** `Restricted content` 节的实际结构是 **「首段一个笼统准许组 + 其后 3 个专项类别」**（此前草稿误写为「4 类」，现按原文更正）：

   **首段（笼统准许组，4 个并列项，但不各自单列时效）**：
   > "We permit environmental claims, origin claims, warranties or guarantees, and claims that describe health or quality ingredients on ingestible products such as gluten free or organic. These claims must be substantiated on the ad creative, product detail page, or landing page, and **environmental claims must be dated within 24 months**."

   **其后 3 个专项类别（各自单列时效）**：

   | 类别 | 逐字时效要求 |
   |---|---|
   | `Product effectiveness` | "substantiation, including source and date (**no age requirement**)" |
   | `Product endorsements` | "substantiation, including source and date (**within 24 months**)" |
   | `Comparative claims` | "substantiation, including source and date (**within 24 months**)" |

   来源：`_evidence/R1/amazon-ads-claims-substantiation-restricted-content.md`（本次新增的解码抽取件）、`_evidence/R1/amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.html`

   【判断】因此准确说法是：**时效要求共出现 3 次，取值 2 种（24 个月 / 无要求）**，另首段对环境类单独给 24 个月。**证据时效是规则的一等字段，且取值随声称类型变化**——这一点不受计数更正影响。

【判断 / 落地含义】客户的 12 字段里，要支撑上述结构，至少需要新增/明确三个字段：
- `法域块`（不是单个国家；支持 EU-27 这类合并，且允许跨国覆写）
- `覆写方向`（加严 / 放松 / 替换证据形式）
- `证据时效`（月数，或 `无时效要求`）

### 2.3 规则条数与收益的关系

#### 2.3.1 公开一手数据：**未找到**

**本节明确记录：本次调研未找到任何公开的、关于「规则库条数与收益关系」的一手量化数据。** 具体已尝试且失败的路径：
- web_search / exa_search：**本次会话搜索引擎不可用**（`modsearch failed: Every engine for the web source failed`，firecrawl 429 限流，exa 未配置 API Key）。原始报错见本节末尾。
- 本地证据库（`_evidence/R1`–`R8`）中**无** rule-count-vs-benefit 的量化研究。

**禁止**用「一般认为边际递减」这类无源表述填充本节。以下是**能找到的最接近的替代证据**：NAD 的年度案件统计（它是「裁决量」而非「规则量」，**不可直接当作规则条数证据**）。

【原文】（NAD 2025 年报，逐字）
> "NAD's monitoring matters continued to account for 20% of our decisions in 2025"
> "cases each year based on its own monitoring of" …
> "In 2025, the makeup of incoming National Advertising Division cases did evolve. For instance, we received 10% … a large number of challenges involving health claims"
> "increase in number of closed cases" / "increase in Complex Track cases"

来源：`_evidence/R2/nad-annual-report-2025.txt`（行 25–43、85、144–156）
URL：https://bbbprograms.org/getmedia/1b815bdb-eab6-4a54-8af0-afa0a03d1eae/NAD_AnnualReport_2025_Digital_Report.pdf
（本文件抓取于 R2 分片，非本次新抓；NAD 主站本次补抓为 403，见 §1.2.6）

【判断】NAD 年报提供的可用信息是**「监控自查 vs 外部挑战」的比例（20%）**，即**主动发现占比**。这是「规则库产出效率」的一个可迁移指标，但**它不是规则条数与收益的关系**。**不得**据此声称任何关于规则条数的结论。

#### 2.3.2 客户自有数据：**找到了一条真实的反例**（本节的实质内容）

虽然公开数据未找到，**客户自己的 21 条规则提供了一组可量化的一手数据**，且它直接回答了「加规则是否等于加收益」：

【原文】（内部审计，逐字）
> "现有 21 条规则表是一份「文档」，不是一份「可执行规则库」。两者的证据是：把它自带的正则跑在 291 条真实记录上，只能复现 13.8% 的人工判定，72.3% 一条都复现不出来，而且它从不多报一条。"

> "**正则层从不多报一条**（多余命中 = 0）。它不是「判定规则」，它是「已经被判违规之后，用来在文本里找位置的定位器」。规则表把两件事写在了一起。"

来源：`research/governance/01-内部证据-规则表现状审计.md` §摘要与 §2.1

**逐规则数据（内部审计 §1.2，21 条规则的关键词数 / 正则数 / 覆盖）：**

| 规则 | 关键词数 | 正则条数 | 被正则覆盖 | 覆盖率 |
|---|---:|---:|---:|---:|
| H01 | 72 | 14 | 38 | 53% |
| H02 | 59 | 11 | 29 | 49% |
| **H05** | 33 | 1 | **0** | **0%** |
| H06 | 5 | 1 | 2 | 40% |
| **H07** | 46 | 4 | **3** | **7%** |
| **H08** | 11 | 1 | **0** | **0%** |
| M01 | 8 | 1 | 3 | 38% |
| M03 | 15 | 2 | 4 | 27% |
| M05 | 6 | 1 | 3 | 50% |
| M06 | 6 | 2 | 1 | 17% |
| H09 | 30 | 6 | 19 | 63% |
| M07 | 32 | 4 | 15 | 47% |
| H03 / H04 / M02 / M04 / U01 / U02 / U03 / U04 / 安全词 | 有 | **0** | — | **无正则** |

【原文】（内部审计，逐字，关于命中量与覆盖率的关系）
> "H07 的 46 个关键词里正则只覆盖 3 个（`pain-free` / `no pain` / `without pain` / `say goodbye to ... pain`）。剩下 43 个（含 `painlessly`、`relieve pain`、`缓解疼痛`、`绝对不疼`）正则层完全看不见——**而 H07 恰恰是现网命中最多的一条规则（51 次）**。"

> "`启用状态 = 停用` 这个字段只有给人看的语义，没有执行的语义。"（U02 已停用但仍被匹配 18 次）

来源：`research/governance/01-内部证据-规则表现状审计.md` §1.2、§2.1

**【判断】三条由客户自有数据支持的结论：**

1. **规则条数与覆盖率已经解耦。** 21 条规则中，**9 条完全没有正则**（无法机器执行）；有正则的 12 条里，**2 条覆盖率为 0%**（H05、H08 抓不到自己任何一个关键词）。**即：真正在机器上起作用的规则不足 10 条，占 21 条的不到一半。**
2. **命中量与可执行性成反比。** 现网命中最多的 H07（51 次）恰恰是**正则覆盖率最低的一条（7%）**。这说明「哪里出问题」与「哪里写了规则」之间**没有正相关**。直接推论：**按「命中量」来决定优先扩哪条规则，是错的；应按「人工判定量 − 规则捕获量」的差额决定。**
3. **存在「负收益规则」。** U02 已标为 `停用` 却仍被关键词层匹配 18 次——这条规则**只产生噪声不产生信号**，且其 `启用状态` 字段在机器上无效。**这是规则库中一条真实的负收益条目，客户已有实物。**

**【判断 / 对 Q4.3 的回答】**：
> **未找到**任何公开的「规则条数 → 收益」一手数据。
> 但客户自有数据足以否定一个常见假设：**「规则越多覆盖越好」在客户当前状态下已被证伪**——21 条规则的实际生效面不足 10 条，且最高频风险对应的规则可执行性最低。
> **可用的替代判据**：不追求规则**条数**，而追求**「已穷尽来源的两层（法源 L1 + 平台 L2）覆盖率」**（§2.2.2）。可穷尽的层查完了，就可以宣布这一阶段收工——这是**可判定的停止条件**，而「多少条够用」不是。

### 2.4 已知未覆盖清单的真实形态

**Q4.4 问：其他团队怎么接受「规则写不完」？有没有公开的 known gaps register？长什么样？——有，而且找到三种真实形态。**

#### 2.4.1 形态 A：Amazon AHR 的「范围内政策清单 + 明示排除声明」★ 最接近「已知未覆盖清单」

Amazon 的 Account Health Rating（AHR）页面本身**就是一个已发布、生产环境中的范围声明**：

【原文】
> "This article applies to selling in: United States
> **Policies included in Account Health Rating**
> Account Health Rating (AHR) indicates your selling account's risk of deactivation due to policy non-compliance, and it displays on the seller's Account Health page for each store in which they sell worldwide. **This page lists all policies included in the AHR, and will be updated as new policies are added in the future.**"
> "**Amazon has not changed any policies as a result of AHR, and not all of Amazon's policies are currently included in AHR.** For a full list of Amazon's program policies, go to Program policies."

随后列出 **15 条**被纳入 AHR 的政策：Amazon Anti-Counterfeiting policy / Amazon Brand Name policy / Amazon Intellectual Property policy / Amazon Marketplace Fair Pricing policy / ASIN Creation policy / Communication guidelines / Customer Product Reviews Policies / INFORM Consumers Act / Product condition guidelines / Product detail page rules / Product guidelines for adult products / Product guidelines for selling software / Product safety and compliance / Restricted Products policy / Selling policies and seller code of conduct

来源：`_evidence/R1/amazon-ahr-included-policies-GQ5DSES264XVXNX7.md`（完整正文，152 行）
URL：https://sellercentral.amazon.com/help/hub/reference/external/GQ5DSES264XVXNX7
抓取日期：2026-09-15

【判断】**这是 known gaps register 的教科书形态，且它做到了四件事**：
1. **显式列出「范围内的规则」**（15 条，可枚举）——让使用者知道什么**会**影响账号。
2. **显式声明「范围外」的存在**："**not all of Amazon's policies are currently included in AHR**"——**这是一句官方承认「清单不完备」的话**。
3. **给出范围外的出口**："For a full list of Amazon's program policies, go to Program policies."——**未覆盖的部分不是消失，而是指向另一个清单**。
4. **声明清单会演进**："will be updated as new policies are added in the future"——**清单是一份有生命周期的文档，不是承诺**。

同时它还有一条**方法学声明**（对客户理解「机器审核能做什么」很关键）：
> "We use a combination of advanced machine learning techniques and automation and expert human review to identify and monitor policy non-compliance and to respond to reports of illegal products and content. Our tools use natural language processing and machine learning, which means new information is fed into them daily and they learn and get better at proactively and automatically blocking offers we suspect of policy non-compliance."

【判断】注意这句话的结构：**ML + automation + expert human review 三者并列，且不承诺覆盖率。** 亚马逊从不声称「我们的清单覆盖所有违规」。**客户的规则库应当采用同样的话术纪律：声明覆盖范围，不声明覆盖完整。**

#### 2.4.2 形态 B：Ofcom 的 essential records——把「未覆盖」变成必填记录字段

【原文】（Ofcom, *Children's Risk Assessment Guidance*，Step 1 essential records）
> "**A record of the kind(s) of non-designated content that will be assessed**, and how you have considered the risk of children encountering non-designated content"

> （Step 2）"Identify whether there are any **additional characteristics or functionalities** of the service's design or operation, **not in the Children's Risk Profiles**, which could increase the risk"

> （Step 3，偏离推荐措施时）"Any applicable measures … that are **not planned to be implemented, and the alternative measures** that have been or are planned to be implemented instead, **with information that demonstrates how these alternative measures meet the relevant duties**"

来源：`_evidence/R4/ofcom-childrens-risk-assessment-guidance.*`（85 页 PDF）
转引自 `research/governance/R4-trust-and-safety-ops.md` §6.3.3（该节保留逐字引文与文件路径）

【判断】Ofcom 给出的不是「一张清单」，而是**三个必填记录槽位**：
- **槽位 1（Step 1）**：不在既定清单内、但你判断需要评估的内容类别 —— **记录「我评估了清单外的什么」**。
- **槽位 2（Step 2）**：不在官方 Profile 内、但可能提升风险的**特性或功能** —— **记录「清单没写但我发现了什么」**。
- **槽位 3（Step 3）**：未实施的推荐措施 + 替代措施 + **论证替代措施如何满足义务** —— **记录「我没照做，理由是」**。

【判断】形态 B 与形态 A 的关键差别：**A 是「发布一份清单」，B 是「在每次判定里留三个槽位」。** 对客户而言，**B 更可落地**——因为客户的规则库正在运行中，每次人工复核都是一次产生 gap 记录的机会。R4 §7.4 的 `CATCH-ALL-01` 与 §7.2「补齐字段 #1、#2、#3、#5、#7」正是这个思路的已有版本。

#### 2.4.3 形态 C：NIST AI RMF 的「知识边界」——把未知写进文档

【原文】（转引，R4 §6.7 表）
> `the AI system's knowledge limits`（NIST AI RMF 1.0 MAP 2.2）
> `After completing the MAP function, Framework users should have sufficient contextual knowledge about AI system impacts to inform an initial go/no-go decision`（NIST AI RMF 1.0 §5.2）
> `The inability to appropriately measure AI risks does not imply that an AI system necessarily poses either a high or low risk.`（NIST AI RMF 1.0 §1.2.1）

来源：`_evidence/R4/` NIST AI RMF 1.0 相关文件
转引自 `research/governance/R4-trust-and-safety-ops.md` §6.2、§6.7

【判断】NIST 的贡献是**把「不知道」合法化**：MAP 2.2 要求显式产出「知识边界」文档，§1.2.1 明确「测不出来 ≠ 低风险」。**这解除了客户的一个心理障碍**：规则库可以带着已知的未知运行，前提是**这些未知被写下来**。

#### 2.4.4 「已知未覆盖清单」的最小可用形态（本节综合结论）

综合三种形态，客户可直接落地的 known gaps register **不需要是一份新文档**，而可以是**规则库表里的一个派生视图**。三列即可：

| 列 | 来源形态 | 客户数据的现成值 |
|---|---|---|
| `缺口类型` | A（范围内/外）+ B 槽位 1、2 | `无正则` / `正则覆盖率 0%` / `未命中` / `记录不可见` |
| `缺口描述` | B 槽位 2 | 例：20.3% 的记录引擎看不到（内容模态）；38.1% 的命中在规则表里没有词（语种） |
| `处置与理由` | B 槽位 3 | 例：暂不新增规则，因该缺口无法给出正反样例 → 转人工 |

**客户已有的现成缺口条目（来自内部审计，可直接入册）**：
1. **9 条规则无正则** → 机器不可执行。
2. **H05 / H08 正则覆盖率为 0%** → 规则存在但完全失效。
3. **H07 正则覆盖率 7%，却是命中最多（51 次）的规则** → 最高频风险可执行性最差。
4. **U02 已停用但仍被匹配 18 次** → `启用状态` 字段无执行语义。
5. **`适用产品` 字段失效**：21 条全填同一常量，而 S12 Pro / V1 Pro 有改写建议却无规则覆盖。
6. **语种缺口**：运营层 5 语种，规则表层 2 语种，**38.1% 的命中在规则表里没有词**。
7. **内容模态缺口**：**20.3% 的记录引擎看不到**。
8. **M 前缀多义**：同时编码「审慎关注」与「人工复核」两个轴，机器无法从前缀推出处置动作。

来源：`research/governance/01-内部证据-规则表现状审计.md` §1.1–§1.5、§2.1、§三

【判断】这 8 条的性质是**「规则库的内部缺口」**（规则写了但机器执行不了），与 Ofcom/Amazon 形态的**「覆盖面缺口」**（规则没写到的领域）**是两类不同的东西，清单应分开记**。混在一起会让「未覆盖」这个数永远算不清——因为前者可通过改写正则消除，后者只能通过新增规则或转人工消除。

【本节方法学记录（不可省略）】本节曾尝试用 web_search 与 exa_search 检索公开的 rule-count-vs-benefit 数据，**两个工具在本次会话中均不可用**：
> `Error: modsearch failed (exit 1): Error: Every engine for the web source failed. - firecrawl: firecrawl returned 429 Too Many Requests … - Known engines: antigravity-cli, tavily, exa, firecrawl, grok-cli, local`
> `未配置 Exa API Key：请在 设置 → 出海技能 页面的「外部工具凭据」里填写 Exa API Key 后再试`
因此**「未找到」这一结论的强度受限于工具不可用**，而非「已穷尽检索」。此限定必须随结论一并转述，**不得**在汇总层被简化为「公开数据不存在」。

---

## 3. 对客户现状（21 条规则 / 覆盖率 13.8%）的冷启动处方

**约束**：本节只写「规则库内容与结构」层面的处方；规则引擎实现（R3）、裁决制度（R2）、面向客户的最终报告均不在本分片范围。

### 3.1 先把现状说准：13.8% 不是「覆盖率低」，是「两件事被写在了一起」

内部审计的核心事实（§2.3.2 已逐字引用）：正则层复现 18/130 = **13.8%**，**72.3% 一条都不中**，且**从不多报一条**。

【判断】**「从不多报一条」这个读数比 13.8% 更重要。** 一个真正在判定的规则层必然会有假阳性（多报）；**零假阳性只有一个解释：它没有在做判定，它在做定位。** 因此客户现状的正确描述不是「规则覆盖不足」，而是：
> **规则表把「判定」（是不是违规）与「定位」（违规在文本哪一段）两件事写在同一个字段族里，而机器侧只有后者。**

这决定了处方顺序：**第一步不是加规则，是拆字段。**

### 3.2 处方一：拆开「判定层」与「定位层」（P0，最高优先）

| 拆出的层 | 输入 | 输出 | 客户现有对应物 |
|---|---|---|---|
| **判定层（decision）** | 内容 + 声明类型 + 市场 + 证据 | `合规 / 审慎 / 违规 / 未覆盖` | **缺失**——现由人工在脑内完成 |
| **定位层（locator）** | 已判违规的内容 | 命中片段的位置 | 现有 8 条正则 |

【判断】证据：H07 有 **46 个关键词**但正则只覆盖 **3 个（7%）**，而它**恰是现网命中最多的规则（51 次）**。这说明**人工判定根本没用 H07 的关键词表**——人工用的是别的判据。**判定层的真实内容目前存在于 3 位 Copywriter 的脑中（5 语种词表）**，规则表只记录了他们的定位动作。处方：把判定层的判据**显式写出来**，才可能扩到 100 条。

### 3.3 处方二：按 §2.2.2 的四阶段来源排序建库（P1→P4）

| 阶段 | 目标条数 | 主来源 | 关键动作 | 停止条件 |
|---|---|---|---|---|
| **P0** | 1 | 自建 + L1 | 落 `CATCH-ALL-01`：未命中 → `未覆盖` → 转人工，**不再自动判合规** | 盲区率可测 |
| **P1** | → ~15 | **L1 法源** | 把现有 21 条中**已有法源的**补全 `依据来源`（R5 §9.2 已给出建议填法）；**移除无法源且无法给出正反样例的条目** | **法源层穷尽**（可判定） |
| **P2** | → ~40 | **L2 平台政策** | 按 `（平台 × 法域块）` 补齐；引入 `覆写方向` 与 `证据时效` 字段（§2.2.3） | **四个平台正文已抓（R5 §8）+ 国别条目补齐** |
| **P3** | → ~70 | **L3 裁决案例** | 从 `nad-case-1-kendamil`（婴配粉）/`nad-case-2-nanit`（婴儿监护器）/`nad-case-3-hims-hers`（女性健康）提炼「文案原文 + 裁决理由 + 整改要求」三元组 | 母婴相邻品类案例库扫完 |
| **P4** | → ~100 | **L4 内部萃取** | 把 5 语种词表从 `命中片段` 自由文本迁移到受控词表字段 | 语种缺口归零 |

【判断】**P1 的停止条件是本处方最重要的设计**：法源是**可穷尽的有限集合**，因此可以宣布「查完了」。而 L3/L4 是开放集合，永远查不完——见 §3.4。

### 3.4 处方三：用「可穷尽性」替代「多少条够用」作为验收线

§2.3.1 已记录：**未找到**任何公开的「规则条数 → 收益」一手数据（且搜索引擎本次不可用）。因此**不能**用「100 条」当作目标。

【判断 / 替代验收线】用两层判据：
1. **可穷尽层已穷尽**：L1（法源）+ L2（平台政策）的清单**逐条对账完毕**，每条要么有规则、要么进 known gaps register 并写明理由。← **这是可判定的**
2. **每条规则可给出正反样例对**：对齐 YouTube 划线法（§2.1.4，R4 §1.1）与 R4 §7.4 D6–D8。**做不到的规则不能留在「自动可检测」** —— 应移入「需语境判断」或退役。

【判断】第 2 条直接命中客户现状：21 条**全部**填 `判断方式 = 自动可检测`，但内部审计显示其中 U01/U02/U03、M05、M07 本质上需要语境判断。**这是客户规则表最大的单点失真。**

### 3.5 处方四：把 8 条现成缺口入册（§2.4.4）

内部审计已产出 8 条可直接入册的缺口条目（§2.4.4 已逐条列出）。处方：**分两类记账**——
- **A 类「执行缺口」**：规则写了但机器执行不了（9 条无正则、H05/H08 覆盖率 0%、H07 仅 7%、U02 停用仍命中、M 前缀多义）。→ **可通过改写规则消除**，有明确闭合路径。
- **B 类「覆盖面缺口」**：规则没写到的领域（语种 38.1%、内容模态 20.3%、S2 Pro / V1 Pro 无覆盖）。→ **只能通过新增规则或转人工消除**，需排期。

【判断】**两类混记会让「未覆盖」永远算不清**——A 类会随规则改写自然减少，B 类不会。分开记，A 类可作为「规则库健康度」的分子，B 类作为「待建规则」的输入。

### 3.6 处方五：给规则库加三个结构字段（来自 §1.1/§2.2.3 的一手证据）

| 字段 | 为什么必须加 | 一手依据 |
|---|---|---|
| `法域块` | 真实体系按法域块合并（EU-27 一条目），不是单国 | Amazon Ads `Country-specific restrictions`（§2.2.3） |
| `覆写方向` | 国别覆写既可能加严**也可能放松** | Amazon 英国条目：可用联系方式替代 study + date（§2.2.3） |
| `证据时效` | 同一政策内逐声称类型不同 | Amazon：环境类 24 个月 / 背书类 24 个月 / 有效性类无时效（§2.2.3） |

【判断】**这三个字段的加入会让规则数「看起来变多」**（一条规则因法域覆写分裂成多条）。这是正确的——**当前 21 条规则中的国别差异是隐性的、靠人工记忆的**，显式化后条数上升而实际判定能力也上升。**不要用「条数」作为汇报口径**，用 §3.4 的两条验收线。

### 3.7 处方六：声明覆盖范围，不声明覆盖完整（§2.4.1）

Amazon AHR 的官方话术纪律：
> "**not all of Amazon's policies are currently included in AHR.**"

【判断】客户规则库对外（对业务方）的表述应当是「**本规则库覆盖 X 类风险，未覆盖部分见 known gaps register**」，而不是「合规检测」。理由：客户现状**已证明**当前规则不足以支撑「合规」这个词——13.8% 复现率、9 条无正则。**用「合规」这个词会让业务方对绿标产生错误的信任**，而绿标恰恰是风险最高的输出（因为正则层从不多报，绿标数量必然虚高）。
## 4. 不可达来源

| 目标 | URL | 结果 | 尝试次数 | 说明 |
|---|---|---|---|---|
| BBB National Programs / NAD 主站 | `https://bbbprograms.org/programs/all-programs/nad` | **HTTP 403** | 1（2026-09-15，Safari 17 UA） | 主站拒绝。**但 NAD 实质材料本地已有 40+ 文件**（`_evidence/R2/nad-*`、`narb-*`），不依赖主站可达 |
| Elvie legal | `https://www.elvie.com/pages/terms-conditions` | **HTTP 404** | 1 | 无此页 |
| Elvie claims | `https://www.elvie.com/pages/legal` | **HTTP 404** | 1 | 无此页 |
| Willow legal | `https://www.willowpump.com/pages/terms-of-service` | **HTTP 403** | 1 | 拒绝（UA / 风控策略） |
| Medela legal | `https://www.medela.us/terms-of-use` | **HTTP 404** | 1 | 无此页 |
| Lansinoh legal | `https://www.lansinoh.com/pages/terms-of-use` | **HTTP 404** | 1 | 无此页 |
| Spectra legal | `https://www.spectrababyusa.com/pages/terms-of-service` | **HTTP 404** | 1 | 无此页 |
| web_search / exa_search（工具） | — | **工具不可用** | 多次 | `modsearch failed: Every engine for the web source failed`（firecrawl 429 限流）；exa 未配置 API Key。**这限制了 §2.3.1 的「未找到」强度** |
| CRN Product Claims 正文 | `https://www.crnusa.org/regulation-legislation/fda-ftc-regulations/product-claims` | HTTP **200 但正文未取得** | 1 | 抓取成功（88,605 bytes），但 JS 导航结构干扰正文抽取，**未取得该页 claim 规则逐字引用**，仅确认存在与归属分支 |

**任务书预先告知的不可达来源（本次未重复尝试，遵从指示）**：
- `ofcom.org.uk` —— Cloudflare 403（**注：R4 分片已成功取得 Ofcom 的 *Children's Risk Assessment Guidance* 85 页 PDF，见 `_evidence/R4/ofcom-childrens-risk-assessment-guidance.*`，本分片 §2.4.2 引用的是该 PDF**）
- `betterrules.govt.nz` —— Incapsula
- `shopify.com/legal/acceptable-use-policy` —— 404

【判断】本节记录的四条竞品 legal 页结果（404/403）**本身就是 §1.4.2 的证据**，不是单纯的取证失败——它们证明这些品牌**没有**在预期路径上发布 claim 规则文档。

---

## 5. 证据清单

### 5.1 本分片新抓的证据文件（`_evidence/R7/w3/`）

抓取日期：**2026-09-15**；UA：`Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15`；一源一文件，文件头含 `SOURCE_URL` / `FETCHED` / `HTTP` / `BYTES`；状态码总表 `fetchlog.tsv`。

| 文件 | HTTP | 字节 | URL |
|---|---|---|---|
| `crn-about-substantiation.md` (+`.raw`/`.txt`) | 200 | 107,678 | `https://www.crnusa.org/` |
| `nhc-about.md` (+`.raw`/`.txt`) | 200 | 144,852 | `https://nationalhealthcouncil.org/` |
| `nad-main.md` | **403** | 118 | `https://bbbprograms.org/programs/all-programs/nad` |
| `ftc-hpcg-landing.md` (+`.raw`/`.txt`) | 200 | 1,152,656 | `https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance` |
| `crn-product-claims.md` (+`.raw`/`.txt`) | 200 | 88,605 | `https://www.crnusa.org/regulation-legislation/fda-ftc-regulations/product-claims` |
| `crn-voluntary-guidelines.md` (+`.raw`/`.txt`) | 200 | 90,759 | `https://www.crnusa.org/self-regulation/voluntary-guidelines-best-practices` |
| `crn-probiotics.md` (+`.raw`/`.txt`) | 200 | 90,379 | `https://www.crnusa.org/regulation-legislation/self-regulation/best-practices-probiotics` |
| `crn-caffeine.md` (+`.raw`/`.txt`) | 200 | 96,242 | `https://www.crnusa.org/regulation-legislation/self-regulation/crn-recommended-guidelines-caffeine-containing-dietary` |
| `crn-supplement-owl.md` (+`.raw`/`.txt`) | 200 | 92,713 | `https://www.crnusa.org/self-regulation/supplement-owl` |
| `elvie-legal.md` | **404** | 305,223 | `https://www.elvie.com/pages/terms-conditions` |
| `elvie-claims.md` | **404** | 305,223 | `https://www.elvie.com/pages/legal` |
| `willow-legal.md` | **403** | 5,731 | `https://www.willowpump.com/pages/terms-of-service` |
| `medela-legal.md` | **404** | 29,183 | `https://www.medela.us/terms-of-use` |
| `lansinoh-legal.md` | **404** | 377,691 | `https://www.lansinoh.com/pages/terms-of-use` |
| `spectra-legal.md` | **404** | 146,328 | `https://www.spectrababyusa.com/pages/terms-of-service` |
| `legendairy-home.md` (+`.raw`/`.txt`) | 200 | 809,855 | `https://legendairymilk.com/` |
| `freemie-home.md` (+`.raw`/`.txt`) | 200 | 160,812 | `https://freemie.com/` |
| `fetchlog.tsv` | — | — | 抓取状态总表（name / HTTP / bytes / URL），21 行 |
| `fetch.sh` / `fetch2.sh` | — | — | 抓取脚本（可复现） |

**新抓证据文件数（本分片 `_evidence/R7/w3/`）：17 个 `.md` 证据文件 + 1 个状态表 + 2 个脚本。**

### 5.1b 本次新增的**解码抽取件**（对既有 R1 证据的二次提取，非新抓）

| 文件 | 来源容器 | 用途 |
|---|---|---|
| `_evidence/R1/amazon-ads-claims-substantiation-country-restrictions.md` | `_evidence/R1/amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.html` | 把内嵌 JSON 中**转义的国别正文**解码并短行化，使 §2.2.3 的国别覆写条目**可被朴素 grep 复核** |
| `_evidence/R1/amazon-ads-claims-substantiation-restricted-content.md` | 同上 | 同上，用于 §1.1.5/§2.2.3 的 `Restricted content` 时效要求逐字复核 |

> **⚠️ 必须随本分片所有 Amazon 结论一并转述的取证警告**
> Amazon Seller Central / Ads 政策页把正文以**转义 JSON** 形式内嵌在 HTML 里，且国别等小节由**客户端折叠组件**渲染：
> - **文本层抽取（`read_page`/`web_fetch` 产出的 `.md`）会丢失折叠区正文** —— 以 `amazon-ads-claims-substantiation-…md`（4565 字节）为例，`Country-specific restrictions` 下**只有四个国名标题，无正文**。
> - **正文存在于 `.html` 中**，但位于**超长行**（本页第 1336 行，11,371 字符；全文件最长行 29,989 字符）。**部分 grep 封装会跳过超长行**，因此对 `.html` 直接 grep 可能得出「不存在」的**假阴性**。
> - **正确的复核方式**：对 `.html` 做字节级计数（`python3` 读二进制后 `count`），或使用 §5.1b 的解码抽取件。
> - **本分片的全部 Amazon 国别结论均以此方式复核过**，字节级计数见 §2.2.3 的方法学警告块。

**新抓证据文件数：17 个 `.md` + 2 个解码抽取件 + 1 个状态表 + 2 个脚本。**

### 5.2 本分片引用但非本次新抓的本地证据

| 文件 | 本分片引用位置 | 抓取分片 |
|---|---|---|
| `_evidence/R5/ftc/ftc-health-products-compliance-guidance-2022-12.PDFTEXT.txt` | §1.3 全部（目录、FTC/FDA 差异、限定词、证据阶梯、FDA approval、第三方文献） | R5 |
| `_evidence/R5/ftc/ftc-policy-statement-advertising-substantiation-1984.CLEAN.txt` | §1.2.3（reasonable basis 六因素、隐含声明） | R5 |
| `_evidence/R5/ftc/ftc-deception-policy-statement-1983.PDFTEXT.txt` | §1.2.4 表（体系清单） | R5 |
| `_evidence/R5/ftc/ecfr-16cfr255-endorsement-guides.TEXT.txt` | §1.2.4 表 | R5 |
| `_evidence/R2/nad-guidance-substantiation-checklist.txt` | §1.2.1、§1.2.2（NAD 三步清单逐字） | R2 |
| `_evidence/R2/nad-annual-report-2025.txt` | §1.2.4 表、§2.3.1（20% monitoring） | R2 |
| `_evidence/R2/nad-case-1-kendamil.txt` | §1.4.3（婴配粉，仅确认存在） | R2 |
| `_evidence/R2/nad-case-2-nanit.txt` | §1.4.3（婴儿监护器，仅确认存在） | R2 |
| `_evidence/R2/nad-case-3-hims-hers.txt` | §1.4.3（女性健康，仅确认存在） | R2 |
| `_evidence/R1/amazon-ahr-included-policies-GQ5DSES264XVXNX7.md` | §2.4.1（known gaps register 主证据） | R1 |
| `_evidence/R1/amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.html` / `.md` | §2.1.1、§2.2.3（第一条规则 + 国别覆写表） | R1 |
| `_evidence/R5/competitors/KEYWORD-HITS-raw.txt` | §1.1.2（Willow 295 mmHG 逐字） | R5 |
| `_evidence/R5/competitors/FETCH-LOG.txt` | §1.4.1、§1.4.2（证明 R5 未抓 legal 页） | R5 |
| `_evidence/R4/youtube-policy-development.html` / `.txt` | §2.1.4（YouTube 划线法） | R4 |
| `_evidence/R4/ofcom-childrens-risk-assessment-guidance.*` | §2.4.2（Ofcom essential records） | R4 |

### 5.3 本分片引用的已完成分片报告

| 文件 | 引用位置 |
|---|---|
| `research/governance/R5-category-and-competitors.md` §7.1/§7.2/§7.7/§8.4/§8.5/§9.2/§9.3 | §1.1 全部、§1.4.1、§3.3 |
| `research/governance/R4-trust-and-safety-ops.md` §1.1/§6.3.3/§6.7/§7.4 | §2.1.4、§2.4.2、§2.4.3、§3.3 |
| `research/governance/01-内部证据-规则表现状审计.md` §摘要/§1.1–§1.5/§2.1 | §2.3.2、§2.4.4、§3 全部 |

### 5.4 本分片的取证缺口（须由后续分片补）

1. **`nad-case-1-kendamil.txt` / `nad-case-2-nanit.txt` 未逐字提炼** —— 母婴相邻品类的具体红线未提取（§1.4.3 已声明）。
2. **CRN 12 份成分级指南的正文未取得** —— 仅取得清单（§1.2.5 已声明）。
3. **Amazon Ads 政策页的 `Prohibited content` / `Restricted content` 未逐条编号化** —— 已取得全文，未做成规则表。
4. **§2.3.1 的「未找到」受搜索工具不可用限制** —— 若后续会话搜索工具可用，应重跑该检索。
