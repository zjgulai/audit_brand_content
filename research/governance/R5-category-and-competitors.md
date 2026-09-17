# R5 — 母婴品类的监管边界与竞品合规表达

> 分片：R5｜主题：母婴品类的监管边界与竞品合规表达
> 写作日期：2026-09-15｜所有抓取日期标注为 2026-09-15（Asia/Shanghai）/ 2026-09-14（UTC）
> 证据目录：`research/governance/_evidence/R5/`
> 遵循 `00-调研任务书.md` 的证据标准：法源条款号 + 逐字原文 + URL；竞品文案逐字引用 + 抓取日期 + URL。

---

## 结论先行（TL;DR）

**七个结论，按重要性排序。**

### R5-C1｜「品类」不是一个维度，是一个「判定前提」

规则库不应该有「品类」这个维度。原因是：**在吸奶器这个品类上，监管身份本身就是由内容决定的。** 同一台物理设备，只要换一句文案，就从「非医疗器械」变成「II 类医疗器械」，从「无需 510(k)」变成「需要新 510(k)」，从「受 FTC 广告法管辖」变成「同时受 FDA intended use 规则 + 21 CFR 807.81 重新申报义务管辖」。

三条独立法源证明这一点：

- **英国 MHRA**（`borderlines-with-medical-devices-and-other-products-in-great-britain`，updated 29 June 2026）：把「breast pumps」明确列入「**not normally considered to be medical devices**」清单，但同一页又写「**breast pumps for treatment of inverted nipples**」属于「may be considered to be medical devices」。原文见 §3.3。
- **美国 FDA** 21 CFR 801.4：intended use 由「labeling claims, advertising matter, or oral or written statements」确定。原文见 §3.1。
- **欧盟 MDR (EU) 2017/745** Art. 2(1)：device 的定义以「intended by the manufacturer to be used … for one or more of the following specific medical purposes」为前提。原文见 §4.1。

所以正确的表述是：**品类决定「哪些法条上场」，内容决定「这台设备此刻是什么」。** 品类维度应当被替换为一张 **「品类 × 国家 → 触发法条 + 监管身份阈值」的映射表**（即规则库的 `regulation_ref` 字段填充表），而不是一个独立的过滤维度。

### R5-C2｜吸奶器的监管身份是「条件式」的，且三国门槛不同

| 法域 | 吸奶器默认身份 | 触发变成医疗器械的条件 | 触发后的类别 |
|---|---|---|---|
| 美国 | **是**医疗器械（无条件）。电动 = Class II，product code **HGX**，21 CFR 884.5160；手动 = Class I，product code **HGY**，21 CFR 884.5150 | 不适用（美国不设「非医疗用途」出口） | Class II 需 510(k)；Class I 手动泵豁免 510(k)（限 250 mmHg 以下等条件） |
| 欧盟 MDR | **取决于声称**。MDR 未列举吸奶器；Art. 2(1) 的「medical purpose」是准入门槛 | 声称具备诊断/预防/监测/治疗/缓解疾病等 medical purpose 时 | 若定性为器械，MDCG 2021-24 Rule 12 示例「Suction pump」→ **Class IIa**（需公告机构 NB） |
| 英国 GB | **不是**医疗器械（MHRA 明文列入「not normally considered」清单） | 声称用于治疗（MHRA 举例：treatment of inverted nipples） | 按 UK MDR 2002 走，需 UKCA + MHRA 注册 |

**这是本次调研最具操作价值的发现**：Momcozy 在北美以外（法国 26 条、英国 19 条、加拿大 14 条、西班牙 11 条、意大利 3 条在跑广告，**无美国**）投放的文案，法域前提与美国不同。英国站的一条「treat inverted nipples」类文案会把产品从「非器械」推进「医疗器械」，触发 UKCA + MHRA 注册义务 —— 这是一条**内容变更导致合规义务变更**的路径，规则库目前完全没有表达这种依赖。

### R5-C3｜H06「FDA cleared 不是 approved」有最强的法源，但法源不止一条，而且比他们写的更强

法源不是一条，是**四条**，其中两条是禁止性条款而非说明性条款：

1. **21 CFR 807.97**（逐字）：*"does not in any way denote official approval of the device. Any representation that creates an impression of official approval of a device because of complying with the premarket notification regulations is misleading and constitutes misbranding."* —— 这是「misbranding」（掺假标识）认定，不是提醒。
2. **EU UCPD 2005/29/EC Annex I 第 4 条**：*"Claiming that a trader … or a product has been approved, endorsed or authorised by a public or private body when he/it has not …"* —— 全欧范围**在任何情况下均视为 unfair**（Annex I 是 per se 禁止清单，无需证明消费者实际被误导）。
3. **FDA 官方消费者页面**：「FDA Registered」「FDA Certified」「FDA Registration Certificate」均为误导性用法，且明说 *"Firms that misleadingly display certificates … misbrand the device in violation of the Federal Food, Drug, and Cosmetic Act."*
4. **21 CFR 807.22(b)(1)**：企业注册是**每年 10 月 1 日–12 月 31 日**的年度动作，与器械 clearance 完全无关。这是「registered ≠ cleared」的机制性证据。

**竞品实证**：在 7 个品牌中，**「FDA approved」真实出现在三个竞品的在售文案里**，其中最严重的一例是 **BabyBuddha**：其 `/pages/certifications` 页面**连续三次**声称 FDA 批准，并且**在同一页上打印了 510(k) 编号 `FDAFDA 510K# K151284`** —— 宣称 "approved" 与 "510(k) cleared" 并置，这是 21 CFR 807.97 所禁止行为的教科书级样本（全文见 §7.3）。另两例是 Willow（Sync 产品页等多处）与 Lansinoh（旧款 Wearable Breast Pump 页）。BabyBuddha 另用「FDA Compliant」（第三个变体，同样无法源）。

**同时，Momcozy 自己的 FDA 用词是全组最规范的之一**：全站仅 3 处 FDA 字符串，集中在 Wellness 1 的 "FDA 510(k) Cleared"（2 处）与 M9 的 "FDA and LFGB certified"（1 处）；**站内没有 "FDA approved"、"FDA registered"、"FDA listed"、"FDA compliant"，也没有企业注册声明。** 其中 M9 的 "FDA and LFGB certified" 指材料而非器械，是站内唯一需要整改的 FDA 表述。

**因此 H06 的规则覆盖面应当从 `FDA approved|certified` 扩展到 `FDA compliant|FDA registered|FDA approved|FDA certified`（注意 "FDA **and LFGB** certified" 这类中间插词的语序变体），并把豁免词里的「FDA registered」降级。**

### R5-C4｜H02「more milk 不能说」是**误判**，正确规则是「more milk 必须有 RCT 级证据，否则不能说」

这是本次调研对规则校准最重要的一条修正。

**法源**：FTC《Health Products Compliance Guidance》(2022-12) 第 13 页：*"As a general matter, substantiation of health-related benefits will need to be in the form of randomized, controlled human clinical testing to meet the competent and reliable scientific standard."* 以及 *"Randomized, controlled human clinical trials (RCTs) are the most reliable form of evidence and are generally the type of substantiation that experts would require for health benefit claims."*

**竞品实证**（全部逐字，抓取日 2026-09-15）：

- **Medela** 官网在售文案：*"Medela researchers found that double pumping obtains **18% more milk on average**, compared to single pumping³."* 脚注³：*"Clinical studies, PersonalFit Flex™ compared to PersonalFit data on file (**NCT02496429, NCT02492139, NCT02719548, NCT03091985**)"*
- **Medela** Harmony 页：*"More comfort for you, more milk for your baby – **clinically proven**¹."*
- **Willow** Go 页 H2：*"**Clinically proven** design for output, powered by ComfortFlow™"*；bullet：*"105° flange angle **clinically proven to encourage more milk**"*
- **Willow** Go 页：*"In an **independent survey of 500 pumping moms, 71%** said Willow Go gives better milk output than their…"*
- **Willow** 360 页：*"…supported by 360 Care"* 语境下的 *"**More milk.**"* 头图标题；*"Better Fit. **More Milk.**"*

**结论**：行业头部品牌**都在用** "more milk" 与 "clinically proven"，前提是**附 RCT 注册号（NCT 号）或第三方样本量明确的调研**。Momcozy 的 H02 把这四个品牌全部在用、且头部品牌有法源支撑的表达定成「高危红线」，属于**过度禁用**；而 Momcozy 自己又同时在用（见 R5-C5），形成「规则说禁止、实操在违反」的分裂。

**正确规则形态**：H02 应拆成两条 ——
- `H02a`（红线，法源：FTC HPCG 2022）：无 RCT/无独立第三方证据的量化增产声称（`more milk`、`+N%`、`boost supply`）→ 高危；
- `M02b`（审慎，法源：FTC HPCG 2022 §「Ads that refer to a specific level of support」）：带限定语的定性表达（`supports your natural let-down`）→ 审慎。
- **豁免词应改为「存在可核验证据」这一条件，而不是词表。**

### R5-C5｜Momcozy 自己已经持有 13 项 FDA 510(k) clearance —— 规则库字段 `适用产品` 与 `依据来源` 需要重写

从 openFDA `device/510k` 数据库检索 product code **HGX** 全量 250 条记录，命中 **Shenzhen Root Innovation Technology Co., Ltd.** / **Shenzhen Lutejiacheng Technology Co., Ltd.** 名下 13 项 Momcozy 品牌 clearance：

| K 号 | 器械名（逐字） | 决定日期 | 类型 |
|---|---|---|---|
| K230776 | Momcozy Wearable Electric Breast Pump ( Model: S9 Pro, S12 Pro) | 2023-06-09 | Traditional |
| K233880 | Momcozy Wearable Breast Pump (BP137); (BP141) | 2024-03-06 | Traditional |
| K241680 | Momcozy Wearable Breast Pump (BP311) | 2024-12-20 | Traditional |
| K243629 | Momcozy Wearable Breast Pump (BP311; BP223; BP324; BP334; BP430) | 2024-12-20 | Special |
| K251394 | Momcozy Wearable Breast Pump (BP223) | 2025-09-08 | Traditional |
| K253283 | Momcozy Wearable Breast Pump (BP334-, BP380-, BP420-, BP431-, BP400-, BP432-, BP434-) | 2025-10-29 | Special |
| K253934 | Momcozy Wearable Breast Pump (BP380…, **M5**, M5-A…M5-C) | 2026-03-09 | Traditional |
| K253946 | Momcozy Wearable Breast Pump (**S9 Pro**, **S12 Pro** 及变体) | 2026-04-07 | Traditional |
| K254254 | Momcozy Wearable Breast Pump (BP311 及变体) | 2026-06-18 | Traditional |
| K254258 | Momcozy Wearable Breast Pump (BP137, BP141 及变体) | 2026-04-08 | Traditional |
| K253914 | Momcozy Wearable Breast Pump (BP334 及变体, BP434) | 2026-04-29 | Traditional |
| K260538 | Momcozy Wearable Breast Pump (BP420 及变体) | 2026-06-17 | Traditional |
| （另 K243629/K233880 为 Special/Statement 类型） | | | |

全部 `product_code = HGX`、`advisory_committee_description = Obstetrics/Gynecology`、`decision_description = Substantially Equivalent`。

**这直接推翻规则库的三处隐含假设**：
1. `依据来源` 里 H02 写的「无 FDA/临床证据」——不成立。M5、S9 Pro、S12 Pro 有 clearance。
2. `适用产品` 写死 `W1、M5、M6、M9、Air1`——但 W1（Wellness 1）的暖敷+按摩功能在已检索到的 Momcozy clearance 里**没有任何一项覆盖**。W1 页面自称 *"FDA 510(k) Cleared"*，但检索到的 K 号里没有一项器械名包含 warm/massage/wellness 的 Momcozy 产品。检索到一项 **K260864 "Mother's Nature W1 Warming Wearable Breast Pump"**（申请人 Shenzhen TPH Technology Co., Ltd.，决定日 2026-06-09，HGX）—— **器械名与 Momcozy 的 "Wellness 1" 不同、申请主体不同**，是否同一产品**未能核实**。
3. W1 页面文案（逐字）：*"Warmth + Gentle Massage help the body relax, **supporting the natural release of oxytocin—the hormone that triggers milk let-down**."* 而 H02 的禁用关键词里**明确包含** `trigger oxytocin`、`release oxytocin`、`increase oxytocin`。**Momcozy 官网当前在违反自己的 H02。**

同时 W1 页的 *"**285° full-coverage warmth**"* 段落给出了唯一一处符合 FTC 标准格式的免责声明样例：*"*Based on quantitative findings from internal real-user testing. Results are self-reported. Individual results may vary."* —— 但按 FTC 标准，**内部自陈数据不足以支撑 health benefit claim**（FTC HPCG 2022 明说 anecdotal evidence 不足）。

### R5-C6｜「安全词」白名单里有三个词不是安全词，其中一个是**反向风险词**

逐词核验 `安全词` 白名单 27 个词条：

| 词条 | 法源状态 | 判定 |
|---|---|---|
| `suction level` / `adjustable suction` / `N levels` | 客观可核查（对应 21 CFR 884.5150 的 250 mmHg 阈值与 IEC 60601-1 范畴） | ✅ 真安全词 |
| `BPA-free` | **无法定定义、无法定强制要求**。FDA 仅在 2012/2013 经**行业申请**从婴儿奶瓶/吸嘴杯/婴儿配方粉包装的食品接触材料中移除 BPA；EU 走的是 Reg (EU) 2024/3190 | ⚠️ 可核查事实（前提是有检测报告），但不是「法定术语」 |
| `food-grade silicone` | **非法定术语**（美国 eCFR 官方检索精确短语 `"food-grade silicone"` = **0 命中**；对照组 `"food grade"` = 187 命中，证明查询本身有效）。美国实际法源是 21 CFR 177.2600（Rubber articles intended for repeated use）的萃取限值；**LFGB 不是法源，而是德国食品饲料法典的条款号** —— § 31 是**禁止性规定**，全法**不存在任何认证机制**，误导性表述依 § 33 + § 59(1) Nr. 18 / § 60(1) Nr. 2 可罚（见 R5-C10） | ⚠️ 营销惯用语，需替换为可核查表述 |
| `FDA cleared` / `FDA-cleared` | ✅ 可核查（openFDA 可查 K 号） | ✅ 真安全词 |
| **`FDA registered`** | ✅ 可核查，但**语义与 `FDA cleared` 完全不同**，且 FDA 明说 registration 「does not denote approval, clearance, or authorization」。放在「安全词」里会被文案当成「我们被 FDA 认可了」用 | ❌ **应移出安全词，改入 U 类人工复核** |
| `hands-free` / `wearable` / `portable` / `rechargeable` / `wireless` | 描述形态，无监管含义 | ✅ 安全词 |
| `dishwasher safe` / `easy to clean` | 客观可核查 | ✅ 安全词 |
| `quiet mode` / `low noise` / `low-decibel` | 客观可核查（可测 dB） | ✅ 安全词 |
| **`reduces pain`** | **与 H07 直接冲突**。H07 把 `reduce pain`/`reduces pain`/`less pain` 列为**高危禁用**，安全词表却把 `reduces pain` / `less pain` 列为**合规安全词** | ❌ **规则库自相矛盾，必须修** |
| `gentle` / `comfort` | 主观体验词 | ⚠️ 属 puffery（见 R5-C7） |

### R5-C7｜「安全词 vs 非安全词」的判别标准只有一条：**能否被第三方独立复核为真/假**

法源依据是 FTC 对「puffing」的界定。FTC《Policy Statement on Deception》(1983-10-14) 脚注 42，引 *Pfizer, Inc., 81 F.T.C. 23, 64 (1972)*：

> *"[T]here is a category of advertising themes, in the nature of puffing or other hyperbole, which do not amount to the type of affirmative product claims for which either the Commission or the consumer would expect documentation."*

同文件正文：

> *"the Commission generally will not bring advertising cases based on subjective claims (taste, feel, appearance, smell) or on correctly stated opinion claims if consumers understand the source and limitations of the opinion."*

**判别标准（可直接做成规则库的一个字段）**：

```
is_verifiable: boolean
  true  → 安全词（客观事实：认证编号、物理量、材料、结构、接口）
  false → 落入 puffery 或落入需 substantiation 的声称，二选一：
          - 纯主观体验（comfort / gentle / effortless）→ 允许，但不得量化、不得附功效
          - 隐含客观事实（reduces pain / more milk / clinically proven）
            → 必须有 substantiation，否则不成立
```

**关键分界线不是「客观还是主观」，而是「主观词有没有偷偷变成客观声称」。** `comfort` 是 puffery；`less pain` 是客观声称（可测、可证伪），因此需要证据。这正是 FTC 判定 `clinically tested ingredient` 构成功效声称的逻辑（FTC HPCG 2022 Example 18）。

### R5-C8｜免责声明不是「豁免词」—— FTC 明确说免责声明不能治愈欺骗性信息

委托方的规则库里 `豁免词` 字段实际上被当作「白名单」在用（命中豁免词就不判险）。**这条路在法源上是断的。**

FTC《Policy Statement on Deception》(1983)：

> *"Pro forma statements or disclaimers may not cure otherwise deceptive messages or practices."*（脚注 38，引 Listerine 案 *Warner Lambert, 86 F.T.C. 1398, 1414 (1975)*）
> *"Written disclosures or fine print may be insufficient to correct a misleading representation."*
> *"Thus, when the first contact between a seller and a buyer occurs through a deceptive practice, the law may be violated even if the truth is subsequently made known to the purchaser."*

FTC HPCG 2022 脚注 25 进一步说，用 "promising" / "preliminary" 这类软化形容词**不改变**净印象：*"use of adjectives such as 'promising' or 'preliminary' does not alter the net impression of the efficacy claims, 'especially when the chosen adjectives . . . provide a positive spin on the studies, rather than a substantive disclaimer'"*（引 POM Wonderful, 155 F.T.C. at 22-23）。

**竞品实证 —— 免责声明的真实用法**：

- **19 个 Medela + Lansinoh 页面中**：`not intended to treat` / `not intended to diagnose` / `results may vary` / `consult your physician` 出现次数 = **0**。
- **Medela**：23 处脚注，全部是**证据出处**（`Clinical studies … data on file (NCT…)`），不是免责声明。
- **Lansinoh**：10 个页面 **0 处脚注**，尽管页面上有 `clinically proven`、`hospital grade`、`79% of moms`、`FDA approved`。
- **Willow**：用第三方调研（*"independent survey of 500 pumping moms"*）+ IRB 措辞（*"tested by real moms under the guidance of an institutional review board"*）替代免责声明。
- **Medela** 唯一一处 `not intended to` 是**用途限制**而非免责：*"The Hands-free Collection Cups are **not intended to be used for milk storage**."*
- **Momcozy W1**：唯一使用 FTC 标准格式免责的页面 —— *"*Based on quantitative findings from internal real-user testing. Results are self-reported. **Individual results may vary.**"*

**结论**：行业标准做法是**「前置证据」而不是「后置免责」**。「豁免词」这个字段名应当改掉；它的正确语义是 **「本句已带证据标记」**，而不是「命中即可放行」。

### R5-C9｜平台政策在可穿戴品类上比法源更严 —— 这是「平台必须独立成维」的实证

**Meta 广告标准明文禁止「仅靠可穿戴产品就能达成效果」的声称**（逐字，`_evidence/R5/platforms/meta-health-wellness.txt`，change log 最近变更 Jul 22, 2026）：

> "Ads can't: … Promote weight loss or weight gain products or services, that depict: … **Claims that results can be achieved solely by using wearable products**"

**这条没有法源对应。** 欧盟 UCPD Art. 6(1)(b) 与 FTC HPCG 2022 管的是「有没有证据」；**Meta 这条管的是「能不能把结果归因于穿戴形态本身」** —— 即使你有 RCT 证据，在 Meta 上仍然不能这样写。

**另一条同样只有平台才有、而且直接命中委托方 U04 的规则**（Meta Privacy Violations and Personal Attributes，逐字）：

> "ads must not contain content that asserts or implies personal attributes. This includes direct or indirect assertions or implications about a person's … **physical or mental health (including medical conditions)** …"
> "Ads can't: … **Imply knowledge of Medical information of a user or user's family**"

**这把 U04（`sore nipples` / `clogged ducts` / `painful pumping`）从"需要人工判断的语境问题"变成了一条明确禁令**：广告里对受众说「你有堵奶吗？」等于暗示广告主知道受众的医疗状况。**改写规则是可执行的**：第二人称痛点提问 → 第三人称产品功能陈述。

**结论**：`platform` 是一个**真实的、不可与法源合并的维度**。而且 —— **Google 的 Unreliable claims 政策明文写 `Google Ads may defer to local regulatory guidelines for health-related claims`** —— 意味着 **`平台 × 国家` 是联合维度，不是两个可分离的轴**。这直接回答了委托方的问题（见 §8.6）。

---

### R5-C10｜`LFGB certified` 不是「无依据」，而是「可罚」—— 但**故意与过失两条腿不同，不能一律写「刑事」**

一手证据（德国法 + 欧盟法 + 美国 eCFR，全部逐字核对，存于 `_evidence/R5/materials/`；独立复核记录见 `_evidence/R5/VERIFICATION-and-reconciliation.md`）把 `LFGB certified` / `food-grade silicone` 从「营销惯用语」升级为**有明确法定后果的表述**。但同一条证据要求把一个区分写准，否则会**反向夸大**风险。

**（1）德国法上不存在「LFGB 认证」这个制度。** § 31 的标题是「Übergang von Stoffen auf Lebensmittel」，第 1 款逐字：

> "Es ist verboten, Materialien oder Gegenstände im Sinne des § 2 Absatz 6 Satz 1 Nummer 1, die den in Artikel 3 Absatz 1 der Verordnung (EG) Nr. 1935/2004 festgesetzten Anforderungen an ihre Herstellung nicht entsprechen, als Bedarfsgegenstände zu verwenden oder in den Verkehr zu bringen."

这是**禁止性规定**，不是认证制度。§ 30 / § 31 / § 33 / § 58 / § 59 / § 64 全部检索：**不存在任何认证机关、证书或登记册**。§ 64 的标题逐字为「Amtliche Sammlung von Untersuchungsverfahren; Bekanntmachungen」—— 它只建立**官方检验方法汇编**（BVL），不建立认证。

**（2）法律后果在 § 33 + § 59 / § 60，而这里有一个必须写准的区分。** § 33 的标题是「Vorschriften zum Schutz vor Täuschung」，其第 1 款逐字：

> "Es ist verboten, Materialien oder Gegenstände im Sinne des § 2 Absatz 6 Satz 1 Nummer 1 unter irreführender Bezeichnung, Angabe oder Aufmachung in den Verkehr zu bringen oder beim Verkehr mit solchen Bedarfsgegenständen hierfür allgemein oder im Einzelfall mit irreführenden Darstellungen oder sonstigen Aussagen zu werben."

**故意**违反 § 33(1) 构成**犯罪**（§ 59 标题「Strafvorschriften」）：

> "(1) Mit Freiheitsstrafe bis zu einem Jahr oder mit Geldstrafe wird bestraft, wer … **18.** entgegen § 33 Absatz 1 ein Material oder einen Gegenstand unter einer irreführenden Bezeichnung, Angabe oder Aufmachung in den Verkehr bringt oder mit einer irreführenden Darstellung oder Aussage wirbt,"

**过失**则**不**落入 § 59 的犯罪，而是 § 60(1) 的**行政违法**（§ 60 标题「Bußgeldvorschriften」）：

> "(1) Ordnungswidrig handelt, wer eine der in … 2. **§ 59 Absatz 1 Nummer 3 bis 8, 10a, 11 bis 21**, … bezeichneten Handlung **fahrlässig** begeht."

Nr. 15 / 16 / 18 都落在「**11 bis 21**」区间内。因此：

| 情形 | 法律性质 | 条款 |
|---|---|---|
| **明知**无据仍声称 `LFGB certified` | **犯罪**，一年以下有期徒刑或罚金 | § 59(1) Nr. 18（材料误导）；Nr. 15（违反 § 31(1)） |
| **因疏忽**沿用无据表述 | **行政违法**，罚款 | § 60(1) Nr. 2 |
| 违反 § 30 的情形 | 犯罪；**且明文规定过失亦入罪**（§ 58(6)："Wer … fahrlässig begeht, wird mit Freiheitsstrafe bis zu einem Jahr oder mit Geldstrafe bestraft."） | § 58(1) Nr. 13–15；§ 58(6) |

> ⚠️ **对规则库的操作含义**：委托方的真实情形大概率是「沿用供应商给的 `LFGB certified` 说法」，属**过失**，对应风险是**行政罚款 + 竞争法上的误导责任**，而**不是**刑事。`监管后果` 字段应按上表分档填写。**§ 58 与 § 59 不要混用** —— 只有 § 58 有明文过失入罪条款。

**（3）`food-grade silicone`：美国与欧盟两侧都没有这个法定术语。**

- **美国**：eCFR 官方检索 API 对精确短语 `"food-grade silicone"` 返回 `total_count: **0**`；**同一 API 对 `"food grade"` 返回 187 命中** —— 证明查询本身有效，零命中是真实结果而非查询失效。美国法上硅胶按**橡胶**管：21 CFR 177.2600 标题逐字为「**Rubber articles intended for repeated use.**」，硅胶仅作为其中一类「Silicone (Si) elastomers containing methyl groups」出现，**全篇不使用任何 "food grade" 限定词**。
- **欧盟**：硅胶在法律上**不是塑料**。Reg. (EU) No 10/2011 Art. 2(2) 逐字：

> "This Regulation shall not apply to the following materials and articles which are placed on the EU market **and are intended to be covered by other specific measures**: (a) ion exchange resins; (b) rubber; (c) **silicones**."

> ⚠️ **引用时必须连加粗的前半句一起引**。省略「并意图由其他专门措施覆盖」会把有条件的排除读成无条件排除。

- **且不存在覆盖硅胶的欧盟专门措施。** EURL-FCM 的 JRC134290（2023）逐字：「…no material specific EU legislation exists for metals and alloys, **silicone and rubber**, and paper and board in contact with food. **Therefore, national legislation shall apply.** In the absence of national legislation, national recommendations or recommendations of the Council of Europe can be considered.」
- **德国侧对应基准是 BfR 建议书 XV「Silicone」（Stand vom 01.10.2025）**，但 BfR 自己明说它不是法，逐字：「The BfR Recommendations on food contact materials are **not binding legal standards**.」其关键限值逐字：「5. Die Siliconelastomeren dürfen nicht mehr als **0,5 % flüchtige organische Bestandteile** abgeben.」
- **EN 1186 不能用来支撑硅胶**：EU 自己唯一覆盖硅胶/橡胶的指导文件 JRC134290 **全文 0 次出现「1186」**（其引用的 EN 标准只有 EN 645、EN 647、EN 14338、EN 15519，且都是纸和纸板）。
- **BedGgstV § 10(2) 的分析记录义务只针对陶瓷**：「Bei Lebensmittelbedarfsgegenständen **aus Keramik** … müssen der Hersteller oder der Einführer für Zwecke der Überwachung Nachweise darüber vorhalten…」—— 全法检索「**Silikon**」**0 次**。

**（4）对规则库的四条具体改动**

1. **H06 增加一个独立法源**：`FDA and LFGB certified`（M9 法兰）此前只按 FDA 用词问题处理（§7.3）。**「LFGB certified」这半句有独立的德国法依据** —— § 33 + § 59(1) Nr. 18 / § 60(1) Nr. 2。H06 的 `legal_basis` 应补入 LFGB § 33、§ 59(1) Nr. 18、§ 60(1) Nr. 2，并把该条的**风险等级从「内部口径高危」升级为「法定违法（德国）/ 行政违法（过失）」**。
2. **`food-grade silicone` 的替换建议必须收窄**（§9.4 表已同步）：`LFGB-tested` 只在能指名具体检验方法（§ 64 LFGB / ASU 方法，或 BfR 硅胶挥发性物质方法 Version 02, Stand 09/2023）且持有报告时才成立；**`LFGB certified` 一律不得使用**。
3. **`监管后果` 字段分档**：按上面第（2）点的三行表填写，不要把过失情形写成刑事。
4. **`food-grade silicone` 不得作为「法定术语」出现在任何知识库条目**：它在美国 eCFR 零命中，在 Reg. 1935/2004、Reg. 10/2011、BfR XV、JRC134290 中亦零命中。

**未核实（不掩盖）**：EN 1186 各部分的标题与范围（CEN 检索接口被 WAF 挡，HTTP 500）；EN 14372 同上；欧洲理事会 ResAP(2004)5 正文（coe.int / rm.coe.int / edqm.eu 对本网络出口返回 Cloudflare 403）。这三项均为**取数通道问题**，非「文件不存在」—— 需要换网络出口。**在补齐前，规则库不应引用 EN 1186 或 ResAP(2004)5 作为硅胶的依据。**

---

### R5-C11｜`BPA-free` 在美国：**没有一条法律要求它**；加州的豁免条款是最强证据；而 § 260.9 的适用范围必须写准

**（1）美国不存在要求 `BPA-free` 的法律。**

- **CPSC 无 BPA 规则 —— 这是穷尽枚举，不是「没搜到」。** 拉取 `cpsc.gov/sitemap.xml`（HTTP 200，326,825 字节）得 **19,998 条唯一 URL**，全量检索 `bisphenol` = **0 命中**、独立 `BPA` token = **0 命中**；**对照词 `phthalate` = 76 命中** —— 对照有命中，证明该站点确实收录化学品限制类内容，**零命中是真实缺失，而非抓取失败**。（`_evidence/R5/materials/CPSC_sitemap_full_19998_urls.xml`）
- **FDA**：逐字「Breast pumps are medical devices regulated by the FDA.」；CPSC 自己的「Products Outside CPSC's Jurisdiction」页把 "Medical Devices" 列在 FDA 项下 —— 注意其措辞是保留有限并行管辖（"but CPSC may share jurisdiction over some hazardous substances"），**不是无条件免责**。
- **没有任何州要求贴 `BPA-free` 标签。**

**（2）加州是全美最严、覆盖最广的州法，而它明文把医疗器械排除在外。** Cal. Health & Safety Code § 108940 逐字：

> "(a) On and after January 1, 2026, no person shall manufacture, sell, or distribute in commerce any juvenile's feeding product or juvenile's sucking or teething product that contains any form of bisphenol above the practical quantitation limit (PQL), to be determined by the Department of Toxic Substances Control."
> "(b) Subdivision (a) **shall not apply to medical devices**, as defined in Section 109920, or to food and beverage containers designed or intended primarily to contain liquid, food, or beverages for consumption by the general population."

而 § 109920 的「device」逐字包含「**including any component, part, or accessory**」。因此吸奶器（FDA 器械）**连同其部件**有**两条独立路径**被加州法排除。对照：明尼苏达把禁止对象定义为「an **empty bottle or cup**」，纽约限定为「pacifiers and **unfilled** beverage containers … baby bottles, baby bottle liners and cups, cup lids, straws and sippy cups」—— 均不覆盖泵体。

**（3）纽约的标签条款是全美唯一一条，而且是授权性的。** § 37-0507 逐字：

> "The commissioner **may** authorize product labeling of products that do not contain bisphenol A. The label on such products **may** prominently state "Bisphenol A Free" or "BPA-Free" to inform consumers that the product does not contain the chemical bisphenol A."

两个 "may"。**美国的 BPA 规制是「物质禁令 + 品类限定」模式，不是「标签强制」模式。**

**（4）⚠️ 精度更正：§ 260.9 是「环境营销」指南，套用到 BPA 健康关切上是类比，不是直接适用。**

Green Guides 的正式标题逐字为 Part 260 「**Guides for the Use of Environmental Marketing Claims**」，且 § 260.9(b)(1) 明文限定于「substances that pose the same or similar **environmental** risks」。因此：

- **正确表述**：§ 260.9(b)(2)（"The substance has not been associated with the product category."）对 `BPA-free` 是**风险信号与类比依据**。
- **不应表述**为「`BPA-free` 依 16 CFR 260.9(b)(2) 即构成欺骗」—— 这超出了该文件的**适用范围**（环境声称）与**法律位阶**（guides 是行政解释，非立法）。
- `BPA-free` 的**直接**法源是 **FTC Act § 5** 的一般欺骗标准，以及 **FTC Health Products Compliance Guidance（2022-12）**。
- 而且 (b)(2) 对**奶接触部件**很可能**不**成立 —— BPA 恰恰与婴儿喂养品类**强关联**；(b)(2) 真正咬住的是**整机级**声称（电机 / 外壳）。

**（5）操作建议**

1. `BPA-free` 必须**限定到被测对象**（§ 260.3(b)）：写 `BPA-free milk-contact parts`，不写整机裸 `BPA-free`。这既满足 § 260.3(b) 的范围要求，也正好绕开 (b)(2) 的适用争议。
2. 发布前须持有**实际部件**的检测数据（§ 260.2）。
3. **不得**把 `BPA-free` 写成法定要求或认证 —— 美国既无此要求，也无此认证。
4. 知识库里 `BPA-free` 的 `claim_type` 应为「自愿披露 + 真实性义务」，**不是**「合规要求」。现有 §9.4 判定（⚠️ 可核查事实但不是法定术语）**维持不变**。

**未核实（不掩盖）**：另有 9 个州的 BPA 立法未能核验（IL / CT / VT / WI / WA / MD / VA / MA / NV）。这些主机在本环境**网络层不可达** —— curl 与 web_fetch、带与不带浏览器 UA 均同样失败，且 archive.org 亦不可达，**无 Wayback 兜底**。结论建立在已核验的 4 个州（CA / MN / NY / ME）上，残留缺口如实标注。另：**CPSC 从未就 BPA 或 CPSIA 发表过任何可引用的声明** —— 「CPSC 无 BPA 规则」是从 sitemap 穷尽枚举**推得**的，**不得**把一句「免责声明」放进 CPSC 嘴里。

---

## 一、为什么问这个问题：品类维度是不是一个真维度

委托方问：「规则库应该按国家 × 品类 × 平台 × 内容类型定义吗？」

R5 分片只回答其中一个乘数：**品类这一维到底带来什么。**

答案是：品类带来的不是**一套规则**，而是**一组法条引用**＋**一个监管身份阈值**。用一句话概括本分片的核心机制：

> **在吸奶器这个品类上，文案决定监管身份；监管身份决定适用法条；适用法条决定文案边界。**
>
> 这是一个**闭环依赖**，而不是一个笛卡尔积维度。

闭环的三条边都有法源：

```
    ┌──────────────────────────────────────────────────────────┐
    │                                                          │
    ▼                                                          │
 文案声称 ──[FDA 21 CFR 801.4 / MDR Art.2(1) / MHRA §3]──▶ 监管身份
    ▲                                                          │
    │                                                          ▼
    └────[21 CFR 807.81(a)(3)(ii) 新 intended use 需重新 510(k)]────
          [MDR Art.7(d) 禁止暗示未获符合性评估的用途]
          [UK MRA 触发 UKCA + MHRA 注册]
```

**这就是「品类维度」的真相**：它不是一个可以和其他三个维度相乘的轴，而是一个**规则前置条件解析器**。下面第九节会给出对规则库 schema 的具体修改建议。

**同时，本分片的平台证据（§八）显示：`平台` 也不是一个可分离的轴** —— Google 的 Unreliable claims 政策会把当地法规引用进执法，`平台 × 国家` 因此是联合键。**四个乘数里，至少有两个（品类、平台）不是独立的笛卡尔积轴。**

委托方问：「规则库应该按国家 × 品类 × 平台 × 内容类型定义吗？」

R5 分片只回答其中一个乘数：**品类这一维到底带来什么。**

答案是：品类带来的不是**一套规则**，而是**一组法条引用**＋**一个监管身份阈值**。用一句话概括本分片的核心机制：

> **在吸奶器这个品类上，文案决定监管身份；监管身份决定适用法条；适用法条决定文案边界。**
>
> 这是一个**闭环依赖**，而不是一个笛卡尔积维度。

闭环的三条边都有法源：

```
    ┌──────────────────────────────────────────────────────────┐
    │                                                          │
    ▼                                                          │
 文案声称 ──[FDA 21 CFR 801.4 / MDR Art.2(1) / MHRA §3]──▶ 监管身份
    ▲                                                          │
    │                                                          ▼
    └────[21 CFR 807.81(a)(3)(ii) 新 intended use 需重新 510(k)]────
          [MDR Art.7(d) 禁止暗示未获符合性评估的用途]
          [UK MRA 触发 UKCA + MHRA 注册]
```

**这就是「品类维度」的真相**：它不是一个可以和其他三个维度相乘的轴，而是一个**规则前置条件解析器**。下面第九节会给出对规则库 schema 的具体修改建议。

---

## 二、证据标准与抓取说明

- **抓取日期**：全部为 2026-09-15（Asia/Shanghai）/ 2026-09-14（UTC）。
- **竞品文案**：全部为**品牌官网首发原文**逐字引用。Medela / Lansinoh 19 页全部 HTTP 200，无 bot 拦截；Willow / Elvie / Spectra / BabyBuddha / Momcozy 通过 Shopify `products.json` 与产品页抓取。
- **政府来源可达性**：`www.fda.gov`、`www.accessdata.fda.gov` 对 `curl` 返回 Akamai abuse-detection 404，改用 `web_fetch` 与 `openFDA API` 获取；`eur-lex.europa.eu` 对 `curl` 返回 AWS WAF 202 空响应，改用 `publications.europa.eu/resource/celex/<CELEX>` + `Accept: application/xhtml+xml` 获取全文 XHTML（此路径有效，详见第十一节缺口清单）；`www.ecfr.gov` 对 `curl` 有效，另有 `ecfr.gov/api/versioner/v1/full/` JSON/XML API 可用（需 `--compressed`）。
- **未核实项**：全部在第十一节显式列出，未用推测填充。

---

## 三、美国：吸奶器的监管定性

### 3.1 分类：21 CFR 884.5160 Powered breast pump

**法源 1 —— 分类条款（逐字）**

> **§ 884.5160 Powered breast pump.**
> (a) *Identification.* A powered breast pump in an electrically powered suction device used to express milk from the breast.
> (b) *Classification.* Class II (performance standards).

- URL：https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-884/subpart-F/section-884.5160
- 本地证据：`_evidence/R5/fda/ecfr-884-5160.html`、`_evidence/R5/fda/ecfr-884-5160.xml`
- 抓取：2026-09-15
- **注意原文的语法缺陷**：条文中写的是 "A powered breast pump **in** an electrically powered suction device"（应为 "is"）。这是 eCFR 上的原文，逐字保留。委托方若在合规文档里引用，不要"修正"这个字。

**法源 2 —— 手动吸奶器（对照，逐字）**

> **§ 884.5150 Nonpowered breast pump.**
> (a) *Identification.* A nonpowered breast pump is a manual suction device used to express milk from the breast.
> (b) *Classification.* Class I. The device is exempt from the premarket notification procedures in subpart E of part 807 of this chapter, subject to the limitations in § 884.9, if the device is using either a bulb or telescoping mechanism which does not develop more than **250 mm Hg** suction, and the device materials that contact breast or breast milk do not produce cytotoxicity, irritation, or sensitization effects.

- URL：https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-884/subpart-F/section-884.5150
- 本地证据：`_evidence/R5/fda/ecfr-884-5150.html`、`_evidence/R5/fda/ecfr-884-5150.xml`

**对规则库的直接用途**：这给出了「客观可核查安全词」的第一条**具体数值锚点**。`suction level` 之所以是安全词，是因为分类条款本身就用 mmHg 定义界限（手动泵 250 mmHg）。**能引用到条款的物理量，才是真正的客观事实。**

### 3.2 Product Code 与 510(k) 义务

来源：openFDA `device/classification` 与 `device/510k` API（`api.fda.gov`，2026-09-15 查询）。

| product_code | device_name | device_class | regulation_number | submission_type_id |
|---|---|---|---|---|
| **HGX** | Pump, Breast, Powered | **2** | 884.5160 | 1 |
| **OHH** | Breast Pump Kit | 2 | 884.5160 | 7 |
| **HGY** | Pump, Breast, Non-Powered | **1** | 884.5150 | 4 |
| **PWA** | Breast Pump Accessory, Milk Expression Aid, Via Positive Pressure | 1 | 884.5150 | 4 |

`submission_type_id` 的含义（FDA 器械分类数据库代码）：**1 = Premarket Notification 510(k) required**；**4 = Exempt from 510(k)**；**7 = 特定豁免情形**。

**OHH「Breast Pump Kit」的定义（逐字）**：

> This product code has been established in accordance with the may 20, 1997, guidance entitled, convenience kits interim regulatory guidance, found at www.Fda.Gov/cdrh/ode/convkit.Html. This type of convenience kit, as listed in the guidance above, is under enforcement discretion, and does not require a premarket notification (510(k)) to market if it meets all criteria in the guidance.

**PWA「Breast Pump Accessory…」的定义（逐字）**：

> Designed to be used in conjunction with powered or non-powered breast pumps to apply positive pressure to the breast to aid in milk expression from the breasts of a nursing woman.

**为什么这条对规则库重要**：规则库把 `适用产品` 写死成五个型号（W1、M5、M6、M9、Air1）。但监管身份不是按型号走的，是按 **product code** 走的。一个「Breast Pump Kit」（OHH）和一个「Powered Breast Pump」（HGX）在同一个 listing 里可能同时出现，**510(k) 义务不同**。规则库需要一个 `product_code` 字段，而不是型号字段。

### 3.3 关键规则：文案改动会触发新的 510(k) 义务

**法源 3 —— 21 CFR 807.81（逐字）**

> **§ 807.81 When a premarket notification submission is required.**
> (a) Except as provided in paragraph (b) of this section, each person who is required to register his establishment pursuant to § 807.20 must submit a premarket notification submission to the Food and Drug Administration at least 90 days before he proposes to begin the introduction or delivery for introduction into interstate commerce for commercial distribution of a device intended for human use which meets any of the following criteria:
> …
> (3) The device is one that the person currently has in commercial distribution or is reintroducing into commercial distribution, but that is about to be significantly changed or modified in design, components, method of manufacture, or **intended use**. The following constitute significant changes or modifications that require a premarket notification:
> (i) A change or modification in the device that could significantly affect the safety or effectiveness of the device, e.g., a significant change or modification in design, material, chemical composition, energy source, or manufacturing process.
> **(ii) A major change or modification in the intended use of the device.**

- URL：https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-807/subpart-E/section-807.81
- 本地证据：`_evidence/R5/fda/ecfr-807-81.xml`

**法源 4 —— 21 CFR 801.4 Meaning of intended uses（逐字，全文）**

> **§ 801.4 Meaning of intended uses.**
> The words intended uses or words of similar import in §§ 801.5, 801.119, 801.122, and 1100.5 of this chapter refer to the **objective intent** of the persons legally responsible for the labeling of an article (or their representatives). The intent may be shown by such persons' expressions, the design or composition of the article, or by the circumstances surrounding the distribution of the article. This objective intent may, for example, be shown by **labeling claims, advertising matter, or oral or written statements** by such persons or their representatives. Objective intent may be shown, for example, by circumstances in which the article is, with the knowledge of such persons or their representatives, offered or used for a purpose for which it is neither labeled nor advertised; provided, however, that a firm would not be regarded as intending an unapproved new use for a device approved, cleared, granted marketing authorization, or exempted from premarket notification based solely on that firm's knowledge that such device was being prescribed or used by health care providers for such use. The intended uses of an article may change after it has been introduced into interstate commerce by its manufacturer. If, for example, a packer, distributor, or seller intends an article for different uses than those intended by the person from whom he or she received the article, such packer, distributor, or seller is required to supply adequate labeling in accordance with the new intended uses.
> [86 FR 41401, Aug. 2, 2021]

- URL：https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-801/subpart-A/section-801.4
- 本地证据：`_evidence/R5/fda/ecfr-801-4.xml`、`_evidence/R5/fda/ecfr-801-4.html`
- **版本注意**：方括号引文 `[86 FR 41401, Aug. 2, 2021]` 表明这是 2021 年 8 月 2 日生效的修订版（"Regulations Regarding 'Intended Uses'", FDA-2015-N-2008 final rule）。eCFR 页面上仍挂着 2017 年那条 amendments 被无限期推迟的 cross-reference 说明（`This amendment delayed indefinitely at 83 FR 11639, Mar. 16, 2018.`），那是**旧信息**，不要误引。

**法源 5 —— FDA General/Specific Intended Use 指南（逐字）**

> **Levels of Specificity for *therapeutic* (including preventive) medical devices:**
> 1. Identification of function (e.g., cut)
> 2. Identification of tissue type (e.g., soft tissues)
> 3. Identification of an organ system (e.g., GI tract ) or Identification of a specific organ (e.g. liver)
> 4. Identification of a particular disease entity (e.g., resection of hepatic metastases) or target population
> 5. **Identification of an effect on clinical outcome** (e.g., use of medical device improves the rate of durable complete remissions with chemotherapy)

> **Specific indications for use that ordinarily fall outside a general use for the purpose of determining substantial equivalence include:**
> - Those indications for use that involve the **diagnosis, therapy, or prevention of a particular disease entity** or entities, especially where such entity carries clinical implications not normally associated with other general uses of the device (see below, examples 1, 5, 8);
> - Those specific indications for use that **presume a specific clinical outcome**, especially when that outcome could influence patient management outside standard practice (see below, example 6);
> - Those indications for use that provide a new type of diagnostic information or therapeutic option that significantly impacts patient management

- 文件：*General/Specific Intended Use — Guidance for Industry*, CDRH, issued November 4, 1998, Docket FDA-2020-D-0957
- URL：https://www.fda.gov/regulatory-information/search-fda-guidance-documents/generalspecific-intended-use-guidance-industry
- 抓取：2026-09-15

> **这份指南本身提供了把「功效声称」映射到「监管后果」的操作法则。** 按它的「specificity levels」，吸奶器的文案可以分成五档：
>
> | 档位 | 文案示例 | 监管后果 |
> |---|---|---|
> | 1–2 功能/材质 | "expresses milk"、"BPA-free silicone" | 落在已 clearance 的 intended use 内 |
> | 3 器官系统 | "for the breast"、"for nursing mothers" | 一般仍在内 |
> | 4 **疾病实体** | "for mothers with mastitis / inverted nipples / clogged ducts" | **进入「治疗特定疾病」区，很可能构成 new intended use** |
> | 5 **临床结果** | "reduces mastitis recurrence"、"improves milk supply" | **明确构成 new intended use，需重新 510(k)** |
>
> 这正好解释了为什么 H01（医疗功效）和 H02（增产）必须是红线：**它们不是「话说得不好听」，而是「把产品推进了另一个监管类别」。** 这是 H01/H02 有法源的具体方式 —— 不是「FDA 禁止说 more milk」，而是「说 more milk 会让你需要一份新的 510(k)」。

### 3.4 「cleared」与「approved」的法律区别

**法源 6 —— 21 CFR 807.97（逐字，全文）**

> **§ 807.97 Misbranding by reference to premarket notification.**
> Submission of a premarket notification in accordance with this subpart, and a subsequent determination by the Commissioner that the device intended for introduction into commercial distribution is substantially equivalent to a device in commercial distribution before May 28, 1976, or is substantially equivalent to a device introduced into commercial distribution after May 28, 1976, that has subsequently been reclassified into class I or II, **does not in any way denote official approval of the device. Any representation that creates an impression of official approval of a device because of complying with the premarket notification regulations is misleading and constitutes misbranding.**

- URL：https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-807/subpart-E/section-807.97
- 本地证据：`_evidence/R5/fda/sec-807.97.xml`

> 这是 H06 的**最硬法源**：它不是「建议不要说 approved」，而是**「说 approved 构成 misbranding」**。misbranding 是 FD&C Act 下的违法行为（21 U.S.C. 352），可触发扣押、禁令与刑事追诉。委托方可以把这句话直接放进规则的 `依据来源` 字段。

**法源 7 —— FDA 消费者页面：registration ≠ approval（逐字）**

> You may have seen words like this on a website selling a medical device in the United States, sometimes even with an FDA logo:
> - FDA Registered
> - FDA Certified
> - FDA Registration Certificate
>
> **Such words may be used to mislead you. Is that the same thing as FDA approved, FDA cleared, or FDA authorized? The short answer is NO.**

> When a facility registers its establishment and lists its devices, the resulting entry in the FDA's registration and listing database **does not denote approval, clearance, or authorization** of that facility or its medical devices.

> The FDA does **not** issue any type of device registration certificates to medical device facilities.

> Firms that misleadingly display certificates alongside information about and photos of a device for sale in the United States to imply review or approval by FDA of the device **misbrand the device in violation of the Federal Food, Drug, and Cosmetic Act**.

- 页面：*Are There "FDA Registered" or "FDA Certified" Medical Devices? How Do I Know What Is FDA Approved?*
- URL：https://www.fda.gov/medical-devices/consumers-medical-devices/are-there-fda-registered-or-fda-certified-medical-devices-how-do-i-know-what-fda-approved
- Content current as of: 03/03/2021｜抓取：2026-09-15

**法源 8 —— 企业注册的时间机制（逐字）**

> **§ 807.22 Times for establishment registration and device listing.**
> (a) *Initial registration and listing.* An owner or operator of an establishment who has not previously entered into an operation described in § 807.20(a) shall register within 30 days after entering into such an operation and submit device listing information at that time.
> (b) *Registration and listing updates.* … (1) **Annual registration for each fiscal year is required for all establishments. Annual registration shall take place during the period beginning on October 1 and ending on December 31 of each fiscal year**;

- URL：https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-807/subpart-B/section-807.22
- 本地证据：`_evidence/R5/fda/sec-807.22.xml`

> **操作含义**：企业注册是**年度动作、与器械 clearance 完全解耦**。任何一台设备、任何一个型号都可以被"registered"，注册数据库里出现名字**不意味着 FDA 看过这台设备的任何东西**。这是规则库 `豁免词` 里 `FDA registered` 必须被移除的核心理由。

### 3.5 广告与促销标识要求

**法源 9 —— 21 CFR 801.5（逐字）**

> **§ 801.5 Medical devices; adequate directions for use.**
> Adequate directions for use means directions under which the layman can use a device safely and for the purposes for which it is intended. Section 801.4 defines intended use. Directions for use may be inadequate because, among other reasons, of omission, in whole or in part, or incorrect specification of:
> (a) **Statements of all conditions, purposes, or uses for which such device is intended, including conditions, purposes, or uses for which it is prescribed, recommended, or suggested in its oral, written, printed, or graphic advertising, and conditions, purposes, or uses for which the device is commonly used**; except that such statements shall not refer to conditions, uses, or purposes for which the device can be safely used only under the supervision of a practitioner licensed by law and for which it is advertised solely to such practitioner.

- URL：https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-801/subpart-A/section-801.5
- 本地证据：`_evidence/R5/fda/sec-801.5.xml`

> **这条把「广告」直接纳入 labelling 义务。** 如果你的广告里说了一个用途，而这个用途没有出现在 IFU（说明书）里，那么 IFU 就是**不完整的 adequate directions**——双输。这是「广告文案与说明书一致性」这条规则的美国法源。委托方目前的规则库**完全没有这一条**。

**法源 10 —— 21 CFR 801.6 对比性陈述（逐字，全文）**

> **§ 801.6 Medical devices; misleading statements.**
> Among representations in the labeling of a device which render such device misbranded is a **false or misleading representation with respect to another device or a drug or food or cosmetic.**

- URL：https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-801/subpart-A/section-801.6
- 本地证据：`_evidence/R5/fda/sec-801.6.xml`

> 这是 H08（违法对比 / 贬低竞品）与 M06（模糊对比）的**直接法源**，而且是**器械专条**，比笼统的 FTC 对比广告指引更精准。委托方 H08 与 M06 的 `依据来源` 目前只写「吸奶器广告文案审计_红绿灯.xlsx 规则库」，可以升级为 `21 CFR 801.6`。

**法源 11 —— 21 CFR 814.80（PMA 情形，逐字，全文）**

> **§ 814.80 General.**
> A device may not be manufactured, packaged, stored, labeled, distributed, or **advertised** in a manner that is inconsistent with any conditions to approval specified in the PMA approval order for the device.

- URL：https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-814/subpart-B/section-814.80
- 本地证据：`_evidence/R5/fda/ecfr-814-80.xml`
- **适用性说明**：吸奶器是 Class II / 510(k) 路径，**不适用 814.80**（该条针对 PMA）。列出是为了说明「广告不得超出审批条件」这一原则在器械法中的位置；对吸奶器应引 801.5 + 807.81 而非 814.80。

---

## 四、欧盟：MDR (EU) 2017/745

### 4.1 医疗器械的定义 —— medical purpose 是准入门槛

**法源 12 —— MDR Art. 2(1)（逐字）**

> For the purposes of this Regulation, the following definitions apply:
> (1) 'medical device' means any instrument, apparatus, appliance, software, implant, reagent, material or other article **intended by the manufacturer to be used**, alone or in combination, for human beings **for one or more of the following specific medical purposes**:
> — diagnosis, prevention, monitoring, prediction, prognosis, treatment or alleviation of disease,
> — diagnosis, monitoring, treatment, alleviation of, or compensation for, an injury or disability,
> — **investigation, replacement or modification of the anatomy or of a physiological or pathological process or state**,
> — providing information by means of in vitro examination of specimens derived from the human body, including organ, blood and tissue donations,
> and which does not achieve its principal intended action by pharmacological, immunological or metabolic means, in or on the human body, but which may be assisted in its function by such means.
> The following products shall also be deemed to be medical devices:
> — devices for the control or support of conception;
> — products specifically intended for the cleaning, disinfection or sterilisation of devices as referred to in Article 1(4) and of those referred to in the first paragraph of this point.

- 来源：Regulation (EU) 2017/745, CELEX 32017R0745
- URL（全文 XHTML）：https://publications.europa.eu/resource/celex/32017R0745
- 本地证据：`_evidence/R5/eu/mdr-2017-745-en.xhtml`（1,708,372 bytes）、纯文本 `_evidence/R5/eu/mdr-2017-745-en.txt`（650,041 字符）
- 抓取：2026-09-15

> **这里的第三个破折号是关键，也是风险点**：`modification of … a physiological … process or state`。母乳分泌是一个 physiological process；一台声称"modifies"泌乳过程的设备在字面上落入 MDR 定义。但**「表达乳汁」（expressing milk）通常不被认为是在「modify a physiological process」**——它是在取出已经产生的乳汁。这是吸奶器在欧盟的定性争议点。**未能找到欧盟层面针对吸奶器的官方定性文件**（见第十一节缺口清单），所以此处不做断言。可确定的是：**MDR 没有像美国那样明文列举吸奶器**，所以「是否具备 medical purpose」这个判断完全落在制造商自己的声称上。

### 4.2 Article 7 Claims — 器械广告的误导性声称禁令

**法源 13 —— MDR Art. 7（逐字，全文）**

> **Article 7 — Claims**
> In the labelling, instructions for use, making available, putting into service and **advertising** of devices, it shall be prohibited to use text, names, trademarks, pictures and figurative or other signs that may mislead the user or the patient with regard to the device's intended purpose, safety and performance by:
> (a) **ascribing functions and properties to the device which the device does not have**;
> (b) **creating a false impression regarding treatment or diagnosis, functions or properties which the device does not have**;
> (c) failing to inform the user or the patient of a likely risk associated with the use of the device in line with its intended purpose;
> (d) **suggesting uses for the device other than those stated to form part of the intended purpose for which the conformity assessment was carried out**.

- URL：https://publications.europa.eu/resource/celex/32017R0745
- 本地证据：`_evidence/R5/eu/mdr-2017-745-en.txt` 第 89,342 字符处

> **Art. 7(d) 是欧洲版的 21 CFR 807.81(a)(3)(ii)。** 它说的是：你只能宣传「符合性评估时声明的 intended purpose 之内」的用途。超出即为违法声称。**这是 H01/H02/H09 在欧盟市场的法源**——比美国那条更直接，因为它不需要论证"是否需要新的 510(k)"，直接就是"不得宣传"。
>
> Art. 7 与 H01 的映射：`treat mastitis` → 7(a)（宣称设备不具备的功能）+ 7(b)（造成治疗印象）+ 7(d)（超出 intended purpose）。
> Art. 7 与 H09 的映射：`auto-detects rhythm` / `mimics your baby` → 7(a)（设备不具备的功能）。**注意：H09 在 Momcozy 的判定理由是「W1 当前为用户主动调节+保存程序，非闭环生理识别」—— 这正是一条 7(a) 判定**。

### 4.3 分类：MDR Annex VIII / MDCG 2021-24

**法源 14 —— MDCG 2021-24 Rev.1 Rule 12（逐字）**

> **Rule 12 — Active devices intended to administer and/or remove medicinal products, body liquids or other substances to or from the body**
> General explanation of the rule: This rule is intended to primarily cover drug delivery systems and anaesthesia equipment. If the device's intended route of drug delivery is pulmonary, Rule 20 applies.
>
> | Class | Rule 12 | Examples |
> |---|---|---|
> | **IIa** | All active devices intended to administer and/or remove medicinal products, body liquids or other substances to or from the body are classified as class IIa, | • **Suction pump**<br>• Feeding pumps<br>• Jet injectors for vaccination<br>• Elastomeric pumps or balloon pumps for infusion |
> | IIb | unless this is done in a manner that is potentially hazardous, taking account of the nature of the substances involved, of the part of the body concerned and of the mode of application in which case they are classified as class IIb. | • Infusion pumps<br>• Ventilators<br>• Anaesthesia machines<br>• Anaesthetic vaporisers<br>• Dialysis equipment<br>• Blood pumps for heart-lung machines<br>• Hyperbaric chambers<br>• Pressure regulators for medical gases with integrated flowmeter<br>• Medical gas mixers<br>• Moisture exchangers in breathing circuits if used on unconscious or non-spontaneously breathing patients<br>• Oxygen concentrator used to deliver oxygen |

- 文件：*MDCG 2021-24 Rev.1 — Guidance on classification of medical devices*, Medical Device Coordination Group
- URL：https://health.ec.europa.eu/document/download/cbb19821-a517-4e13-bf87-fdc6ddd1782e_en
- 本地证据：`_evidence/R5/eu/mdcg-2021-24-rev1.pdf`（59 页）、文本 `_evidence/R5/eu/mdcg-2021-24-rev1.txt`
- 抓取：2026-09-15

**我的判断（非原文）**：MDCG 2021-24 的示例清单里**没有 "breast pump"**。最接近的是 Rule 12 的示例 "Suction pump"（Class IIa）。因此**若一台吸奶器在欧盟被定性为医疗器械，最可能的分类是 Class IIa（Rule 12）**，需公告机构（Notified Body）参与符合性评估。**但这是基于示例类比，不是官方对吸奶器的定性。** 见第十一节。

**Rule 9 对照（逐字，供参考）**：

> **Rule 9 — Active therapeutic devices intended to administer or exchange energy**, as well as active devices intended to control or monitor the performance of active therapeutic devices…
> | IIa | All active therapeutic devices intended to administer or exchange energy are classified as class IIa | Electrical and/or magnetic and electromagnetic energy: muscle stimulators, external bone growth stimulators, TENS devices, eye electromagnets, electrical acupuncture… |

> 一台吸奶器**不"施加或交换能量"给人体**（它施加的是负压），所以 Rule 9 不适用；Rule 12 的「remove … body liquids … from the body」才是对口的。

### 4.4 欧盟对 claim 的实质规则：Reg 1924/2006 **不适用于吸奶器**

**这是本次调研必须纠正的一个委托方假设。**

委托方的调研提示里写：「Regulation 1924/2006 Art. 2(2)(5) 对 'health claim' 的定义包含 'may help the functioning of a physiological process' —— 这正好命中他们的 M07 规则，请核实原文」。

**核实结果：该表述不在 Art. 2(2)(5) 里，也不在本条例的任何位置。`physiological process` 这个词组在 Reg 1924/2006 全文中出现 0 次。**

> 逐字核对方式：对**完整合并版**全文做大小写不敏感检索，词根 `physiolog` 仅命中 **5 次**，全部是 `nutritional or physiological **effect**`（Art. 2(2)(3) 的 "other substance" 定义，以及 Art. 5(1)(a)、5(1)(b)(i)、5(1)(b)(ii)、5(1)(d)）。**`physiological process` 作为词组出现 0 次**；它也不在 Art. 2(2)(6)（疾病风险降低定义）或 Art. 2(2)(4)（营养声称定义）中。
>
> **该说法的真实出处是 EFSA / 欧委会的行政用语，不是条例文本。** 见本节「法源 20」。

**那么「支持某个生理过程」这类声称在欧洲的法源住在哪里？答：Art. 13(1)(a)。**

**法源 15 —— Reg (EC) No 1924/2006 Art. 2(2)(5)（逐字）**

> 5) **'health claim' means any claim that states, suggests or implies that a relationship exists between a food category, a food or one of its constituents and health;**

- 来源：Regulation (EC) No 1924/2006, consolidated version 2014-12-13, CELEX 02006R1924-20141213
- URL：https://publications.europa.eu/resource/celex/02006R1924-20141213
- 本地证据：`_evidence/R5/eu/eurlex-02006R1924-20141213-consolidated.TEXT.txt`

**「生理功能」概念的真实位置是 Art. 13(1)（逐字）**：

> **Article 13 — Health claims other than those referring to the reduction of disease risk and to children's development and health**
> 1. Health claims describing or referring to:
> (a) **the role of a nutrient or other substance in growth, development and the functions of the body**; or
> (b) psychological and behavioural functions; or
> (c) without prejudice to Directive 96/8/EC, slimming or weight-control or a reduction in the sense of hunger or an increase in the sense of satiety or to the reduction of the available energy from the diet,
> which are indicated in the list provided for in paragraph 3 may be made without undergoing the procedures laid down in Articles 15 to 19, if they are:
> (i) **based on generally accepted scientific evidence**; and
> (ii) well understood by the average consumer.

**法源 16 —— Art. 6(1)（逐字）**

> **Article 6 — Scientific substantiation for claims**
> 1. **Nutrition and health claims shall be based on and substantiated by generally accepted scientific evidence.**
> 2. A food business operator making a nutrition or health claim shall justify the use of the claim.
> 3. The competent authorities of the Member States may request a food business operator or a person placing a product on the market to produce all relevant elements and data establishing compliance with this Regulation.

**法源 17 —— Art. 12 禁止清单（逐字，全文）**

> **Article 12 — Restrictions on the use of certain health claims**
> The following health claims shall not be allowed:
> (a) claims which suggest that health could be affected by not consuming the food;
> (b) claims which make reference to the rate or amount of weight loss;
> **(c) claims which make reference to recommendations of individual doctors or health professionals and other associations not referred to in Article 11.**

**法源 18 —— Art. 14(2)（逐字）**

> **Article 14 — Reduction of disease risk claims and claims referring to children's development and health**
> 1. … the following claims may be made where they have been authorised in accordance with the procedure laid down in Articles 15, 16, 17 and 19 of this Regulation for inclusion in a Community list of such permitted claims together with all the necessary conditions for the use of these claims:
> (a) reduction of disease risk claims;
> (b) claims referring to children's development and health.
> 2. In addition to the general requirements laid down in this Regulation and the specific requirements of paragraph 1, for reduction of disease risk claims the labelling or, if no such labelling exists, the presentation or advertising shall also bear a statement indicating that the disease to which the claim is referring has multiple risk factors and that altering one of these risk factors may or may not have a beneficial effect.

> ⚠️ **一处必须纠正的常见误读**：Art. 14(2) **不是**「要求疾病风险降低声称额外遵守 Art. 12」的交叉引用条款。已逐字核对**合并版**（CELEX 02006R1924-20141213）与**2006 年原始文本**（CELEX 32006R1924）**两版**，Art. 14(2) 在两版中都是上述「多风险因素声明」要求。
>
> Art. 12 的约束力来自它自己的引导句：*"The following health claims shall not be allowed:"* —— 它对**所有** health claim 生效，不需要 Art. 14(2) 来转引。另有 Art. 10(1) 要求健康声称符合 Chapter II 的一般要求。
>
> **另需纠正**：**Art. 12 只有 (a)(b)(c) 三项，没有 (d)。** 已在合并版与原始版**两版**中逐字核对确认。凡引用「Art. 12(d)」的说法都是错误的。

**法源 19 —— Art. 1(2) 适用范围（逐字）**

> **Article 1 — Subject matter and scope**
> …
> 2. This Regulation shall apply to nutrition and health claims made in commercial communications, whether in the labelling, presentation or advertising of **foods** to be delivered as such to the final consumer.

**结论 —— 三层判断**：

1. **Reg 1924/2006 在字面上不适用**：它的适用对象是「foods to be delivered as such to the final consumer」。吸奶器不是 food。母乳是 food，但**被广告的是泵，不是母乳**。
2. **它的原则在欧洲实践中被类推**：Art. 6(1)「generally accepted scientific evidence」是欧洲对「健康声称需要科学证据」的**成文法表述**，比美国的 FTC standard 更清晰、更可引用。委托方在欧洲市场的文案，引用 Art. 6(1) 作为 M03（未标注来源的效果数据）与 H02/H03 的依据，**在说服力上比引用 FTC 更强**，因为它是**条例级**而非**执法政策级**。
3. **Art. 12(c) 是 H04 的真正欧洲法源**，而且**直接适用**：`claims which make reference to recommendations of individual doctors or health professionals` 被**明确禁止**。这不是"需要有据"（H04 目前的口径是"无据的医生/专家推荐背书"），而是**"一律不得使用"**。
   - ⚠️ **但要注意 Art. 11 的例外**：「National associations of medical, nutrition or dietetic professionals and health-related charities」在无具体共同体规则时适用各国规则。所以「IBCLC 顾问参与设计」这类**机构级**背书，与「doctor recommended」这类**个人级**推荐，在欧洲的待遇不同。委托方的 U01（IBCLC）与 H04（医生推荐）分开处理，**在这一点上是对的**。

**法源 20 —— EU Register of nutrition and health claims：已完整检索，**答案是「没有」**（本节为 2026-09-15 补齐）**

委托方若要在欧洲站写 `more milk` / 催乳 / 泌乳类声称，**必须先知道这个结论**：

> **注册库中不存在任何与泌乳、母乳、哺乳、产奶、催乳素、催乳剂（galactagogue）、奶阵（let-down）或乳腺功能相关的「授权」健康声称。所有涉及这些主题的条目一律为「未授权」。**

**检索方法与数据完整性**（可复核）：

| 项 | 值 |
|---|---|
| 数据源 | European Commission, Food and Feed Information Portal (FIP) |
| **API base** | `https://ec.europa.eu/food/food-feed-portal/**backend**/api`（`backend/` 段是门户 SPA 不暴露的关键；由 `assets/env-json-config.json` 的运行时覆盖 `modules.core.base` 得到） |
| 端点 | `GET {base}/policy-items?foodDomain=nut&authorisationType=nut_auth` |
| 取数要求 | 浏览器 User-Agent + `--compressed`（**不加压缩时 19.9 MB 响应会在约 4.4 MB 处截断成非法 JSON**） |
| 数据规模 | **2,337 条** claim = **授权 269 / 未授权 2,067 / 撤销 1**（按法律依据分：Art.13(1)=2070、Art.13(5)=162、Art.14(1)(a)=46、Art.14(1)(b)=59） |
| 本地证据 | `_evidence/R5/eu/eu-health-claims-register-RAW.json`（19,885,668 B）、`-AUTHORISED.csv`、`-NON-AUTHORISED.csv`、`-SEARCH-lactation.md`、`-VERIFICATION-independent.md` |
| 独立复核 | **由另一名 agent 从原始 JSON 独立重算**，2,337 / 269 / 2,067 / 1 四个数字逐项复现一致；并与 CELLAR 取回的 Reg (EU) No 432/2012 交叉验证（泌乳类 0 命中） |

**逐词命中数 —— 授权项一律为 0**：

| 检索词 | 全库命中 | 其中「授权」 |
|---|---|---|
| `lactation` | 2 | **0** |
| `breast milk` | 3 | **0** |
| `breastfeed` / `breast feed` | 2 / 1 | **0** |
| `milk secretion` / `mammary` / `nursing` | 1 / 1 / 1 | **0** |
| `milk production`、`milk supply`、`prolactin`、`galactagogue`、`let-down`、`lactogenesis`、`mammogenesis`、`human milk` | **0**（全库任何字段均无） | — |

**⚠️ 一个必须避开的误读（这是一个陷阱）**：注册库中**确有 2 条「授权」声称包含 `breastfed`** —— 但它们**不是泌乳声称**：

> POL-HC-6201：*"Docosahexaenoic acid (DHA) maternal intake contributes to the normal brain development of the foetus and **breastfed** infants."*
> POL-HC-6234：*"Docosahexaenoic acid (DHA) maternal intake contributes to the normal development of the eye of the foetus and **breastfed** infants."*
> （两条均为 Art. 14(1)(b)，由 Reg (EU) No 440/2011 授权）

**它们描述的是「孩子」的发育，不是母亲的泌乳。** 表述主体与声称对象都不同，**不能延伸成泌乳声称**。（另有一条授权的 "milk" 条目 POL-HC-6400，是酸奶中的乳糖消化，同样无关。）

**另一处精度问题**：天真的 `lactat` 检索会返回 8 条，但**只有 2 条是真阳性**，其余是血液**乳酸（lactate）**（运动生理学：`ventilatory and lactate thresholds`、`reduction of lactates in excess`）。且 `lactating` 作为**声称措辞**出现 0 次，仅在上述两条 DHA 声称的 **conditions of use** 字段中出现两次（`Information shall be given to pregnant and lactating women…`）—— 那是**目标人群披露**，不是声称。

**最接近的一次尝试，也被驳回了**（这是本节最有说服力的一条）：

> **POL-HC-6243**，Silymarin BIO-C®（水飞蓟），Art. 13(5)，状态 `HCCS_NON_AUTHORISED`：
> *"Suggested for improving the physiological production of breast milk during breast feeding"*
> 由 **Commission Regulation (EU) No 666/2011** 驳回；EFSA Question Q-2009-00957；理由：**effect not substantiated（效应未获证实）**。

其他被驳回的同类条目：POL-HC-7883 蜂王浆（*"Royal jelly helps promote milk secretion in breastfeeding mothers"*）、POL-HC-8511 *Lactobacillus fermentum* CECT 5716（Reg (EU) 2018/1555 驳回）、POL-HC-6285 双歧杆菌（Reg (EU) No 957/2010 驳回）、POL-HC-7516 EPA/DHA（*"increases breast milk DHA levels during nursing"*）。

**对委托方的直接结论**：

1. **`more milk` 类声称在欧盟没有任何授权基础。**「欧盟没有授权」不等于「吸奶器不能这么宣传」—— 因为 Reg 1924/2006 按 Art. 1(2) 只管 **foods**，吸奶器不是 food（见本节前文三层判断）。**但这条证据把欧洲站的风险从「可能违规」变成了「你在主张一个欧盟从未承认过的健康效应」** —— 这是 UCPD Art. 6(1)(b)（`the results to be expected from its use`）下的实质性风险，因为**整个欧盟食品健康声称体系在同一个问题上的监管判断是「证据不足、驳回」**。
2. **它对 §9.1 的 H02 判定是一个重要补强**：美国口径下 H02 是「有证据就能说」；欧盟口径下，同类声称**曾被正式提交并因证据不足被驳回**。委托方若在欧盟主张泌乳功效，需要承担的不只是「自己没证据」，而是「**监管机构已经就同一问题作出过否定判断**」。

**未取得项**：EFSA *Guidance on the scientific requirements for health claims related to functions of the body*（该文件本身）—— `efsa.europa.eu` 与 Wiley 对非浏览器客户端返回 **Cloudflare 403**，且不在 Europe PMC 开放获取库中。已改引两份可获取的 2018 年专项指南（肌肉功能与体能 EFSA J 2018;16(10):5434；抗氧化与心血管 EFSA J 2018;16(12):5136）。**正确的下一步引用是 EFSA J 2016;14(1):4367**（*General scientific guidance for stakeholders on health claims applications*），见 §12 G1b。

### 4.5 真正覆盖吸奶器广告的欧盟法：UCPD 2005/29/EC

**法源 21 —— UCPD Art. 6(1) 误导性行为（逐字，摘录关键项）**

> **Article 6 — Misleading actions**
> 1. A commercial practice shall be regarded as misleading if it contains false information and is therefore untruthful or in any way, including overall presentation, deceives or is likely to deceive the average consumer, **even if the information is factually correct**, in relation to one or more of the following elements, and in either case causes or is likely to cause him to take a transactional decision that he would not have taken otherwise:
> (a) the existence or nature of the product;
> **(b) the main characteristics of the product, such as its availability, benefits, risks, execution, composition, accessories, after-sale customer assistance and complaint handling, method and date of manufacture or provision, delivery, fitness for purpose, usage, quantity, specification, geographical or commercial origin or the results to be expected from its use, or the results and material features of tests or checks carried out on the product;**
> (c) the extent of the trader's commitments, the motives for the commercial practice and the nature of the sales process, **any statement or symbol in relation to direct or indirect sponsorship or approval of the trader or the product**;
> …
> (f) the nature, attributes and rights of the trader or his agent, such as his identity and assets, his qualifications, status, **approval**, affiliation or connection and ownership of industrial, commercial or intellectual property rights or his **awards and distinctions**;

- 来源：Directive 2005/29/EC, consolidated version 2022-05-28, CELEX 02005L0029-20220528
- URL：https://publications.europa.eu/resource/celex/02005L0029-20220528
- 本地证据：`_evidence/R5/eu/eurlex-02005L0029-20220528-ucpd-consolidated.TEXT.txt`

**法源 22 —— UCPD Art. 7 误导性遗漏（逐字，摘录）**

> **Article 7 — Misleading omissions**
> 1. A commercial practice shall be regarded as misleading if, in its factual context, taking account of all its features and circumstances and the limitations of the communication medium, **it omits material information that the average consumer needs, according to the context, to take an informed transactional decision** and thereby causes or is likely to cause the average consumer to take a transactional decision that he would not have taken otherwise.
> 2. It shall also be regarded as a misleading omission when … a trader **hides or provides in an unclear, unintelligible, ambiguous or untimely manner** such material information …

**法源 23 —— UCPD Annex I（per se 禁止清单，无需证明消费者被误导）**

> **ANNEX I — COMMERCIAL PRACTICES WHICH ARE IN ALL CIRCUMSTANCES CONSIDERED UNFAIR**
> *Misleading commercial practices*
> **4. Claiming that a trader (including his commercial practices) or a product has been approved, endorsed or authorised by a public or private body when he/it has not or making such a claim without complying with the terms of the approval, endorsement or authorisation.**
> …
> **17. Falsely claiming that a product is able to cure illnesses, dysfunction or malformations.**
> …
> **23b. Stating that reviews of a product are submitted by consumers who have actually used or purchased the product without taking reasonable and proportionate steps to check that they originate from such consumers.**
> **23c. Submitting or commissioning another legal or natural person to submit false consumer reviews or endorsements, or misrepresenting consumer reviews or social endorsements, in order to promote products.**

- **Annex I 第 4 条 = H06 的欧盟法源**，「FDA approved」在欧盟境内属于 **per se unfair**（无需个案论证）。
- **Annex I 第 17 条 = H01 的欧盟法源**。注意它只覆盖「cure illnesses, dysfunction or malformations」——`clogged ducts`、`engorgement` 是否构成 "illness/dysfunction" 需个案判断；`mastitis` 是疾病，覆盖明确。
- **Annex I 第 23b / 23c 条 = H04 / U01 的欧盟法源（新增）**。这两条是 2019 年《Omnibus Directive》(EU) 2019/2161 加入的，专门针对**虚假评价与虚假背书**：23b 约束"声称评价来自真实用户但未做合理核查"，23c 约束"提交或委托他人提交虚假评价或背书，或misrepresent 社交背书"。
  - **对 U01 的直接用途**：`IBCLC-recommended`、`expert-designed`、`recommended by 100+ experts` 这类表述，如果在欧盟境内不能证明背后的专家确实存在且确实做出了该背书，就落入 **Annex I 23c** —— 而且是 **per se unfair，无需证明消费者被误导**。这比"需核实是否真实合作"（U01 现有口径）强得多。
  - **对 H04 的补充**：`pediatrician recommended` 同时命中 **Art. 12(c)**（个人推荐一律禁止）与 **Annex I 23c**（虚假背书）。
- **Art. 6(1)(b) 的「results and material features of tests or checks carried out on the product」= M03 的欧盟法源**。这比 FTC 更直白：**测试结果本身是被保护的信息对象，误述测试条件/样本即为误导行为。** Momcozy 的 `28.2% faster` / `~70% Reported Earlier Let-Down` 这类数字，在欧盟受 Art. 6(1)(b) 直接约束。

---

## 五、英国：MHRA 与 UKCA

### 5.1 决定性发现：MHRA 明文说吸奶器**通常不是**医疗器械

**法源 24 —— MHRA Borderlines guidance（逐字）**

> ## 3. Medical, cosmetic or toiletry purpose
> As medical devices are considered to be specifically intended for a 'medical purpose', products that do not have such a principal intended purpose are not considered to be medical devices, even if they may be considered to be used for the prevention of disease as a secondary purpose.
>
> **Examples of the types of products that are not normally considered to be medical devices:**
> - baby nappies
> - bed pans
> - **breast pumps**
> - deodorants or odour neutralisers, including those for use with medical devices
> - feminine hygiene products (sanitary towels, tampons)
> - …
> - toothbrushes, dental sticks, dental floss
> - …
>
> **Where there is a specific primary intended medical purpose, similar products may be considered to be medical devices. For example:**
> - bedwetting alarms for nocturnal enuresis
> - **breast pumps for treatment of inverted nipples**
> - external heat pads claiming pain relief
> - incontinence products
> - muscle toning products with medical claims (such as the treatment of incontinence)
> - slimming products indicated for the treatment of clinical obesity …

> ## 2. Medical purpose
> Although the UK MDR 2002 does not use the phrase 'medical purpose', medical devices are considered to be items intended to be used in a medical context. **Whether or not a product is considered to have a 'medical purpose' will be defined by the manufacturer's intention for the product as defined in their labelling, instructions for use and promotional material and its mode of action** in conjunction with the definition of a medical device as stated in the UK MDR 2002.

> ## 1. Introduction
> **It is often assumed that because a product is considered a medical device in some countries, for example in the USA, Canada or in Japan, that it will also be a medical device in the UK. This is not the case** and manufacturers should always refer to the UK definitions of a medical device when making any borderline determinations. **Any such decision will be based on the stated intended purpose of the product and its mode of action.**

- 文件：*Borderlines with medical devices and other products in Great Britain*, MHRA guidance
- URL：https://www.gov.uk/government/publications/borderlines-with-medical-devices/borderlines-with-medical-devices-and-other-products-in-great-britain
- **Updated 29 June 2026**｜抓取：2026-09-15
- 本地证据：`_evidence/R5/uk/mhra-borderlines-gb.html`、纯文本 `_evidence/R5/uk/mhra-borderlines-gb.txt`（376 行，breast pump 出现在第 31 行与第 62 行附近）

> **这三段合起来是回答委托方问题的核心证据**：
>
> 1. 「**promotional material**」被 MHRA 明文列为判定 medical purpose 的依据 —— 广告文案本身是监管身份的构成要件。
> 2. 「breast pumps」和「breast pumps for treatment of inverted nipples」**同时出现在同一份官方文件的相反清单里** —— 官方承认这个品类是**条件式**的。
> 3. MHRA 明确警告「在美国是医疗器械，在英国不一定是」—— 直接否定「一套规则全球适用」的做法。

### 5.2 UKCA 与脱欧过渡现状

**法源 25 —— MHRA 过渡安排（逐字）**

> general medical devices compliant with the EU medical devices directive (EU MDD) or EU active implantable medical devices directive (AIMDD) with a valid declaration and CE marking can be placed on the Great Britain market up until the sooner of expiry of certificate or **30 June 2028**
> in vitro diagnostic medical devices ( IVDs ) compliant with the EU in vitro diagnostic medical devices directive (IVDD) can be placed on the Great Britain market up until the sooner of expiry of certificate or **30 June 2030**
> general medical devices including custom-made devices, compliant with the EU medical devices regulation (EU MDR ) and IVDs compliant with the EU in vitro diagnostic medical devices regulation (EU IVDR ) can be placed on the Great Britain market **up until 30 June 2030**.

> **Summary of key requirements for placing a device on the Great Britain market** — Since 1 January 2021, there have been a number of changes … :
> - a new route to market and product marking (the UKCA marking) is available for manufacturers wishing to place medical devices on the Great Britain market
> - **all medical devices, including in vitro diagnostic medical devices ( IVDs ), custom-made devices and systems or procedure packs, need to be registered with the MHRA before they are placed on the Great Britain market**
> - if you are a medical device manufacturer based outside the UK and wish to place a device on the Great Britain market, you need to appoint a single **UK responsible person** for all of your devices, who will act on your behalf …

- 文件：*Regulating medical devices in the UK*, MHRA
- URL：https://www.gov.uk/guidance/regulating-medical-devices-in-the-uk
- Published: 31 December 2020｜**Last updated: 20 February 2026**｜抓取：2026-09-15
- 本地证据：`_evidence/R5/uk/mhra-ukca-timeline.html`

**法源 26 —— UKCA 与 CE 的关系（逐字）**

> The UKCA mark is a product marking which can be used for medical devices placed on the Great Britain (England, Wales, Scotland) market. **The UKCA mark will not be recognised on the Northern Ireland market. A CE mark or CE UKNI mark will be needed for devices placed on the Northern Ireland market.**

- URL：https://www.gov.uk/guidance/medical-devices-conformity-assessment-and-the-ukca-mark
- 本地证据：`_evidence/R5/uk/mhra-devices-guidance-index.html`

**对 Momcozy 的具体含义**（他们的投放地区分布：法国 26、英国 19、加拿大 14、西班牙 11、意大利 3，无美国；语种 英 199、德 42、法 20、西 11、意 9）：

| 市场 | 吸奶器的监管身份 | 文案写「treat inverted nipples」的后果 |
|---|---|---|
| 英国（19 条在跑） | **不是**医疗器械 → 无需 UKCA、无需 MHRA 注册 | 变成医疗器械 → 需 UKCA（或截至 2030-06-30 的 CE）+ MHRA 注册 + 英国责任人 |
| 法国/西班牙/意大利 | 取决于声称 | 若欧委会或成员国认定具备 medical purpose → Class IIa → **需公告机构（NB）介入符合性评估** |
| 加拿大（14 条在跑） | 本次**未调研**（超出 R5 边界），但加拿大有独立的 Medical Devices Regulations (SOR/98-282) 与 Class I–IV 分法 | **未知** |
| 德国（42 条文案语种，投放地区归类为"其他"） | 同欧盟 | 同欧盟 |

> **这张表本身就是对委托方问题的回答**：不是「国家 × 品类」，而是「**国家 → 该品类的监管身份阈值**」。规则库如果按「国家」分维度，会把同一台设备在英国和法国当成两个不同对象；而实际上真正不同的是**同一个对象在两个法域里触发哪条法源**。

---

## 六、健康/功效声称的举证标准

### 6.1 美国 FTC：「competent and reliable scientific evidence」

**法源 27 —— FTC Health Products Compliance Guidance (2022-12) 的核心定义（逐字）**

> When applied to claims about the efficacy or safety of health-related products, the factors described above make up the FTC's rigorous substantiation standard of "**competent and reliable scientific evidence**." The FTC has more specifically defined that standard as "**tests, analyses, research, or studies that (1) have been conducted and evaluated in an objective manner by experts in the relevant disease, condition, or function to which the representation relates; and (2) are generally accepted in the profession to yield accurate and reliable results**." In addition, the FTC requires that the research must be "**sufficient in quality and quantity based on standards generally accepted in the relevant scientific fields, when considered in light of the entire body of relevant and reliable scientific evidence, to substantiate that the representation is true**."

（原文第 13 页，脚注 28/29/30）

> **这是 H03（临床背书）与 H02（增产声称）的共同举证标准。** 三个要件：①客观执行 + relevant experts；②学界公认能产出可靠结果；③**质量与数量**都足够，且要看整体证据体。

**法源 28 —— 证据层级（逐字）**

> As a general matter, **substantiation of health-related benefits will need to be in the form of randomized, controlled human clinical testing to meet the competent and reliable scientific standard.** In evaluating the reliability of such testing, the FTC will consider several parameters, such as sample size, duration, and outcome measures, that will vary depending on the exact nature of the hypothesis being tested and accepted norms in the relevant field.

> **Randomized, controlled human clinical trials (RCTs) are the most reliable form of evidence and are generally the type of substantiation that experts would require for health benefit claims.** Although there is no requirement for a specific number of RCTs, the replication of research in an independently-conducted study adds to the weight of the evidence. … the quality of the research is more important than the quantity. For that reason, **numerous flawed and inadequate studies are unlikely to add up to competent and reliable scientific evidence sufficient to substantiate a claim.**

> **Epidemiological or observational studies can be valuable to show an association between a product or ingredient, but they don't prove a causal link.** Methodologically sound human clinical testing is necessary to prove causation … The FTC will accept high-quality epidemiologic evidence to substantiate a claim in those limited cases where: 1) it is considered an acceptable substitute for RCTs by experts in the field; and 2) RCTs aren't otherwise feasible.

> **Animal and in vitro studies may provide useful supporting or background information, but, without confirmation by human RCTs, they aren't sufficient to substantiate health-related claims.**

（原文第 13–15 页）

> **证据层级表（FTC 官方口径）**
>
> | 层级 | 证据类型 | 能否独立支撑 health benefit claim |
> |---|---|---|
> | 1 | 随机对照人体临床试验（RCT），最好是独立复现 | ✅ 可以 |
> | 2 | 高质量流行病学/观察性研究 | ⚠️ 仅当 RCT 不可行且学界接受时；只能证明关联不能证明因果 |
> | 3 | 动物 / 体外研究 | ❌ 只能作为背景信息 |
> | 4 | 消费者个案/证言/内部自陈调研 | ❌ 不足 |
>
> **这直接判定**：Momcozy W1 页面的 *"*Based on quantitative findings from internal real-user testing. Results are self-reported."* 是**层级 4**，不足。Willow 的 *"independent survey of 500 pumping moms"* 是层级 4（且是 survey，不是 clinical trial），**同样不足**——但它至少是**独立第三方**且披露了样本量，风险低于未披露来源的数字。Medela 的 *"Clinical studies … (NCT02496429, NCT02492139, NCT02719548, NCT03091985)"* 是层级 1，**达标**。

**法源 29 —— 「clinically proven」的专门规定（逐字）**

> **1. ADS THAT REFER TO A SPECIFIC LEVEL OF SUPPORT**
> As a starting point, marketers of health-related products **must have at least the level of support that they claim to have.** In other words, in addition to meeting the basic requirement that any objective claim about safety or efficacy must be substantiated, the marketer also must ensure that **any assertion about the amount, type, or strength of evidence is accurate.**

> **Example 18:** The website for a sports drink touts a "**clinically tested ingredient**" for improving blood flow and increasing endurance. In this context, the phrase "clinically tested ingredient" **implies not just that the ingredient was tested, but also that the test results prove a benefit** for blood flow and endurance. The phrase also conveys a claim that the sports drink will provide those benefits. Because the drink also contains other ingredients, the marketer should consult with a qualified expert in the relevant field to determine whether experts in that field would generally require **a clinical test of the sports drink itself, rather than the isolated ingredient**, to confirm the blood flow and endurance benefits.

（原文第 13–14 页）

> **Example 18 是对委托方最有用的一个判例式说明**：`clinically tested` 这个词组本身就构成**功效声称**（因为它暗示测试结果证明了 benefit），而且**测试对象必须是产品本身，不能是孤立的成分或零件**。
>
> **应用到吸奶器**：`clinically proven 105° flange angle` 这个说法（Willow 在用）—— 被测试的是**法兰角度**这个零件。按 Example 18 的逻辑，FTC 会问：**有没有对「整台泵」的临床测试？** Willow 的公开页面**未能提供**整机 RCT 的引用。这是一个真实的、竞品尚未解决的合规风险点。

**法源 30 —— 关于临床研究引用的具体判例（逐字脚注）**

> 59 See **POM Wonderful LLC, 155 F.T.C. at 21, 103** (citation to clinical studies can contribute to a clinically proven claim).

（FTC HPCG 2022 脚注 59，原文第 42 页）

**法源 30b —— 「clinically proven」的执法先例：三份案卷原文（已取得）**

前文 §9.1 对 H03 的法源判定依据的是 HPCG 2022 的**文本**。本次另外取得了 FTC 对 `clinically proven` 的**三份执法文书原文**，它们回答的是另一个问题：**FTC 实际怎么打这类声称？**

| # | 案件 | 案号 / Matter | 产品类型 | 对 `clinically proven` 的处置（逐字） |
|---|---|---|---|---|
| 1 | **FTC v. NeuroMetrix, Inc.** | D. Mass. **1:20-cv-10428-FDS**；complaint 2020-03-03；Matter 172 3130 | **器械**（Quell 神经刺激器）—— **结构上最接近吸奶器** | 起诉状 ¶13：*"…that it is **clinically proven** to do so, and that it is cleared by FDA for this specific use."*；广告原文：*"Quell is the only FDA cleared, doctor recommended, 100% drug free device **clinically proven** to relieve chronic pain at the touch of a button."*；同意令 §III.A 禁止声称 *"That any Device is **clinically proven** to: 1. Provide widespread relief from chronic or severe pain…"*，§III.B 禁止 *"That the performance or benefits of any Device are scientifically or clinically proven or otherwise established"*。**$4M 和解，约 $3.9M 退还消费者。** |
| 2 | **In re BASF SE / DIEM Labs** | **C-4744** 与 **C-4745**；Matter 192 3088；consent order 2021-06 | 膳食补充剂 | 命令 §III.A–C 禁止声称 *"that any Covered Product is clinically proven to reduce liver fat…"*、*"clinically proven to cure, mitigate, or treat any disease"*、*"that the health benefits, performance, or safety of any Covered Product is scientifically or clinically proven or otherwise established"* |
| 3 | **FTC v. Quincy Bioscience**（Prevagen） | S.D.N.Y. **1:17-cv-00124**；complaint 2017-01-09；Matter 152 3206 | 膳食补充剂 | **COUNT II "FALSE PROOF CLAIMS"**：*"Prevagen is **clinically shown** to improve memory; … in 90 days; … to reduce memory problems associated with aging…"* |

**第 3 案里对委托方最有用的是 ¶28–29**：FTC 攻击的**不是「完全没有研究」，而是一份真实存在的双盲安慰剂对照 RCT**（Madison Memory Study，n=218，9 项任务）—— 理由是它 *"failed to show a statistically significant improvement … on any of the nine computerized cognitive tasks"*，且被告随后做了 *">30 post hoc analyses"*（事后亚组分析）。

> **这直接改变 H03 的判定方式。** 委托方若要写 `clinically proven`，**「我们做过一项临床研究」不是抗辩理由**：FTC 的检验是「**该研究在预设终点上是否达到统计学显著**」。一项未达预设终点的 RCT，在 FTC 口径下**等于没有证据**；用事后分析补强会被单独点名。**建议把这一条写成 H03 的判定子规则**：不仅要有 RCT，还要**有预设主要终点且达到显著**。

**⚠️ 一条重要的否定性发现（避免过度引用）**：本次检索 FTC 案件库（`ftc-cases-search-clinically-proven.html` 等）**未发现任何涉及吸奶器或哺乳类声称的 FTC 执法案件**。

> **不要在合规文档里写「FTC 曾处罚过吸奶器品牌」—— 不存在这样的案件。** 结构上可援引的先例是 **NeuroMetrix（器械）** 与 **BASF/DIEM（补充剂）**，两者都说明：**器械类 + `clinically proven` + FDA cleared 混用，正是 FTC 的标准靶心** —— 而 Quell 那句广告词（`FDA cleared` + `doctor recommended` + `clinically proven` + `100% drug free`）与吸奶器行业的常见话术**几乎逐项对应**（对应 H06 / H04 / H03 / H05）。

**本地证据**：`_evidence/R5/ftc/enforcement/`（6 份 PDF + 6 份 PDFTEXT + 检索页 HTML）。

**法源 31 —— FTC Policy Statement Regarding Advertising Substantiation (1984-11-23)**

> **The Reasonable Basis Requirement**
> First, we reaffirm our commitment to the underlying legal requirement of advertising substantiation-that **advertisers and ad agencies have a reasonable basis for advertising claims before they are disseminated.**
> The Commission intends to continue vigorous enforcement of this existing legal requirement that advertisers substantiate **express and implied claims**, however conveyed, that make objective assertions about the item or service advertised. **Objective claims for products or services represent explicitly or by implication that the advertiser has a reasonable basis supporting these claims. These representations of substantiation are material to consumers.** … Therefore, **a firm's failure to possess and rely upon a reasonable basis for objective claims constitutes an unfair and deceptive act or practice in violation of Section 5 of the Federal Trade Commission Act.**

> **Standards for Prior Substantiation**
> Many ads contain express or implied statements regarding the amount of support the advertiser has for the product claim. **When the substantiation claim is express (e.g.., "tests prove", "doctors recommend", and "studies show"), the Commission expects the firm to have at least the advertised level of substantiation.** Of course, an ad may imply more substantiation than it expressly claims … in such cases, the advertiser must possess the amount and type of substantiation the ad actually communicates to consumers.
> Absent an express or implied reference to a certain level of support, and absent other evidence indicating what consumer expectations would be, the Commission assumes that consumers expect a "reasonable basis" for claims. **The Commission's determination of what constitutes a reasonable basis depends … on a number of factors relevant to the benefits and costs of substantiating a particular claim. These factors include: the type of claim, the product, the consequences of a false claim, the benefits of a truthful claim, the cost of developing substantiation for the claim, and the amount of substantiation experts in the field believe is reasonable.**

（"**Pfizer factors**" —— 源自 *Pfizer, Inc., 81 F.T.C. 23 (1972)*。**FTC 自己的用语是 "Pfizer factors"（HPCG 2022 尾注 27），不要写成 "Duffy factors"。**）

- 文件：*FTC Policy Statement Regarding Advertising Substantiation*, Date: November 23, 1984, appended to *Thompson Medical Co., 104 F.T.C. 648, 839 (1984), aff'd, 791 F.2d 189 (D.C. Cir. 1986), cert. denied, 479 U.S. 1086 (1987)*
- URL：https://www.ftc.gov/legal-library/browse/ftc-policy-statement-regarding-advertising-substantiation
- 本地证据：`_evidence/R5/ftc/ftc-policy-statement-advertising-substantiation-1984.CLEAN.txt`

> **「doctors recommend」被 FTC 在 1984 年就明文列为 "express substantiation claim"** —— 这给了 H04 一个非常干净的法源。说 `pediatrician recommended` 等于向消费者承诺「我有医生推荐的证据」，因此**必须真的有**，且必须达到该表述所传达的层级。

**法源 32 —— FTC 欺骗认定标准（1983-10-14）**

> Thus, the Commission will find deception if there is a **representation, omission or practice that is likely to mislead the consumer acting reasonably in the circumstances, to the consumer's detriment.**

> Second, we examine the practice from the perspective of **a consumer acting reasonably in the circumstances.** If the representation or practice affects or is directed primarily to a particular group, the Commission examines reasonableness from the perspective of that group.

> Third, the representation, omission, or practice must be a "**material**" one. The basic question is whether the act or practice is likely to affect the consumer's conduct or decision with regard to a product or service.

> … in advertising the Commission will examine "**the entire mosaic, rather than each tile separately**."

> The Commission's right to scrutinize the **visual and aural imagery** of advertisements follows from the principle that the Commission looks to the **impression made by the advertisements as a whole**. Without this mode of examination, the Commission would have limited recourse against crafty advertisers whose deceptive messages were conveyed by means other than, or in addition to, spoken words.

> When representations or sales practices are targeted to a specific audience, such as children, the elderly, or the terminally ill, the Commission determines the effect of the practice on a **reasonable member of that group.**

- 文件：*FTC Policy Statement on Deception*, Date: October 14, 1983, appended to *Cliffdale Associates, Inc., 103 F.T.C. 110, 174 (1984)*
- URL：https://www.ftc.gov/legal-library/browse/ftc-policy-statement-deception
- 本地证据：`_evidence/R5/ftc/ftc-deception-policy-statement-1983.pdf`、`.PDFTEXT.txt`（15 页，46,710 字符）

> **「the entire mosaic, rather than each tile separately」是对「关键词检测」这种审核方式最重要的法源警告。** 一个词单独看是安全的，放在一张图 + 一句标语旁边就可能构成误导。**这是"语境"必须进入规则库的直接法源依据** —— 也是委托方 M07「语境守卫」与 U04「场景化名词表述需人工判定」的正确性证明。
>
> **「targeted to a specific audience … examines reasonableness from the perspective of that group」**：产后哺乳期母亲属于 FTC 意义上的易感群体（产后、睡眠剥夺、激素波动、对婴儿健康高度焦虑）。**同样的文案对一般消费者和对产后妈妈，判定标准不同。** 这是一个委托方规则库完全缺失的维度。

### 6.2 「安全词」的法源判据：puffery

**法源 33 —— FTC 对 puffery 的界定（逐字）**

> 42 "[T]here is a category of advertising themes, in the nature of **puffing or other hyperbole, which do not amount to the type of affirmative product claims for which either the Commission or the consumer would expect documentation**." *Pfizer, Inc, 81 F.T.C. 23, 64 (1972).*
> The term "Puffing" refers generally to an expression of opinion not made as a representation of fact.

> Certain practices, however, are unlikely to deceive consumers acting reasonably. Thus, the Commission generally **will not bring advertising cases based on subjective claims (taste, feel, appearance, smell) or on correctly stated opinion claims** if consumers understand the source and limitations of the opinion.

（FTC Policy Statement on Deception, 1983，脚注 42 与正文）

> **这是判别标准的法源**，而且是**唯一需要的法源**。它给出的分界线是：**"subjective claims" 与 "affirmative product claims for which documentation would be expected"**。
>
> 一条推论：`comfort` / `gentle` 落在 subj ective 一侧（puffery）；`less pain` / `more milk` / `reduces leakage` 落在 affirmative product claims 一侧（需 documentation）。**两者之间的分界线是「是否可被第三方独立证伪」。**

### 6.3 免责声明不能治愈欺骗：豁免词字段的法源问题

**法源 34 —— 免责声明的效力（逐字，FTC Deception Policy 1983）**

> Written disclosures or fine print may be insufficient to correct a misleading representation.
> Other practices of the company may direct consumers' attention away from the qualifying disclosures.
> Oral statements, label disclosures or point-of-sale material will not necessarily correct a deceptive representation or omission.
> Thus, **when the first contact between a seller and a buyer occurs through a deceptive practice, the law may be violated even if the truth is subsequently made known to the purchaser.**
> **Pro forma statements or disclaimers may not cure otherwise deceptive messages or practices.**

（脚注 38 引 *Warner Lambert, 86 F.T.C. 1398, 1414 (1975), aff'd, 562 F.2d 749 (D.C. Cir. 1977), cert. denied, 435 U.S. 950 (1978)* —— Listerine 案）

> Qualifying disclosures must be **legible and understandable.** In evaluating such disclosures, the Commission recognizes that **in many circumstances, reasonable consumers do not read the entirety of an ad or are directed away from the importance of the qualifying phrase** by the acts or statements of the seller.

**法源 35 —— 软化形容词不改变净印象（逐字，FTC HPCG 2022 脚注 25）**

> 25 See, e.g., **POM Wonderful LLC, 155 F.T.C. at 22-23 & nn.13-14** (use of adjectives such as "**promising**" or "**preliminary**" does not alter the net impression of the efficacy claims, "especially when the chosen adjectives . . . provide a positive spin on the studies, rather than a substantive disclaimer")

**法源 36 —— 免责声明与功效声称的净印象（逐字）**

> 26 **Deception Policy Statement, 103 F.T.C. at 180** ("**pro forma statements or disclaimers may not cure otherwise deceptive messages**")

（FTC HPCG 2022 脚注 26）

> **对 Momcozy 的「豁免词」字段的结论**：
>
> 当前设计是「命中豁免词 → 不判险」。按 FTC 口径，这是**把免责声明当作欺骗的许可证**，法源上不成立。
>
> 正确语义应当是：**豁免词只能作为「降级到人工复核」的信号，不能作为「自动放行」的信号。** 一个合格的免责声明必须满足：①与声称**同一视野**（不能藏在页脚）；②**可读、可理解**；③**不提供 positive spin**；④**有实质内容**（不能是"结果因人而异"这种空话）；⑤**不改变原声称的净印象**。
>
> 检验方法（可直接做成规则）：**把免责声明遮住，这句文案还成立吗？** 如果不成立 → 免责声明无效，原声称判险。

**法源 37 —— 平台侧对免责声明的相反要求（TikTok，逐字）**

> **Comparative claims may be allowed, subjected to the provision of evidence or clear disclaimer(s).**

（TikTok Advertising Policies, *Misleading and false content*, "Malicious, Subjective and Before-and-after Comparisons"，Last updated **April 2026**；`_evidence/R5/platforms/tiktok-misleading-and-false-content.txt:75-77`。详见 §8.5(1)。）

**两条法源合起来看，是这个规则库最容易搞错的一处**：

| | FTC（法源 34/36） | TikTok（法源 37） |
|---|---|---|
| 免责声明的作用 | **不能**治愈欺骗 → 是**上限**：免责声明**不能**让一个无证据的声称变合法 | **可以**作为放行条件 → 是**下限**：**有证据 *或* 有清晰免责声明**即可过审 |

一个声称要同时满足两者，唯一可行解是 **「有证据 **且** 有合格免责声明」**：

- 只有免责声明、没有证据 → **TikTok 可能放行，但 FTC 判欺骗**；
- 只有证据、没有免责声明 → **FTC 可接受，但 TikTok 可能拒登**。

**因此当前「命中豁免词 → 不判险」的设计比表面看起来更危险**：它实际上是把 **TikTok 的下限当成了 FTC 的上限** —— 用一句免责声明换取了本应由证据换取的放行。这与 §7.8 的实证吻合：Momcozy 约 14 处功效声称中**只有 1 处**带免责声明，而与此同时 H02 类的 `more milk` / `release oxytocin` 声称**没有** RCT 级证据支撑。

---

## 七、竞品公开表达对照

> **⚠️ 适用范围限定（本次补充取证后加注）**：本节的竞品证据**全部来自官网与落地页**，**不代表这些品牌的付费广告用词**。§8 的平台政策取证（64 页）进一步说明：**平台政策约束的是"广告素材与落地页"，其判据与官网文案的判据不是同一套**（例：Amazon 要求量化声称的证据"可在产品详情页或包装上被发现"，Meta 禁止暗示受众的个人健康属性 —— 这两条对官网文案都不适用）。
> **因此"竞品在广告里功效密度更低"是一个观察，不是已证实的事实。** 若要把"竞品广告用词更保守"作为规则放宽的依据，必须先取得广告素材（Meta Ad Library 等），见 **§12 G5**。

### 7.1 样本与方法

| 品牌 | 抓取页面数 | 抓取方式 | 抓取日 |
|---|---|---|---|
| **Medela** | 9（pumps 分类页 + Pump In Style Pro / PIS Pro+ / Freestyle Hands-free / Freestyle Mini / Sonata / Swing Maxi / Symphony PLUS / Harmony） | medela.com 直抓，HTTP 200，无拦截 | 2026-09-15 |
| **Lansinoh** | 10（breast-pumps 集合页 + Signature Pro / NaturalWave / DiscreetDuo Flow / Manual / Thrive / Signature Comfort / Silicone / Smartpump 3.0 / Wearable） | lansinoh.com 直抓，HTTP 200，无拦截 | 2026-09-15 |
| **Willow** | 8（home / all-pumps / best-sellers / establishing-milk-supply / pump-kits / wearable-electric / Willow Go / Willow Go new / Willow 360 / Willow Sync / Wave Manual） | onewillow.com Shopify | 2026-09-15 |
| **Elvie** | 9（home / collections / Elvie Pump / Stride / Stride 2 / Curve / Catch / Rise） | elvie.com Shopify | 2026-09-15 |
| **Spectra** | 5+（homepage / Premier / S3 Pro / 9 Plus / S1 Plus） | spectrababyusa.com | 2026-09-15 |
| **BabyBuddha** | 43 products（products.json 全量）+ 6 pages | babybuddhaproducts.com Shopify `products.json` | 2026-09-15 |
| **Momcozy（自身对照）** | 12+（homepage / M5 / M6 / M9 / S9 Pro / S12 Pro / Air 1 / W1 / Mobile Flow / Mobile Style / V1 Pro / V2 Pro / IBCLC 页 + 6 个集合页） | momcozy.com Shopify | 2026-09-15 |

**取证完整性说明（来自抓取方的自检）**：Medela + Lansinoh 的 19 页共 334 个页面文本片段，机械复核 **325/334 逐字命中**，其余 9 条为标注/分隔符。抓取方在自检中**纠正了自己草稿里的两处真实错误**（一处是给 `<title>` 错误追加了 "| Medela"，一处是脚注 `®` 前后空格）。**未发现捏造**。

**未取到的来源**：Medela 没有独立的 "Swing" 产品页（只有 Swing Maxi）；`increase milk`、`pediatrician recommended`、`natural let-down`、`recommended by` 四个字符串在 Medela+Lansinoh 的 19 页里**出现次数为 0**；Lansinoh 全部 10 页**没有任何临床引用**。

### 7.2 核心对照表：同一个卖点，各家怎么表达

#### 卖点 A — 奶量 / 增产（对应 Momcozy H02、M03）

| 品牌 | 逐字文案 | 证据/限定语 | 触碰了 H02 吗 |
|---|---|---|---|
| **Medela** | "Medela researchers found that double pumping obtains **18% more milk on average**, compared to single pumping³." | 脚注 ³：`*Clinical studies, PersonalFit Flex™ compared to PersonalFit data on file (NCT02496429, NCT02492139, NCT02719548, NCT03091985)` | **是（裸 more milk + 百分比）**，但带 4 个 NCT 注册号 |
| **Medela** | "More comfort for you, **more milk** for your baby – **clinically proven**¹." | 脚注 ¹：同上 NCT 组 | **是（more milk + clinically proven）** |
| **Medela** | "With wide-angle breast shields **proven to deliver up to 11,8% more milk**²" | 脚注 ² 为内部数据 | **是** |
| **Medela** | "**Up to 50% more milk** within first 2 weeks"（Symphony PLUS） | 引用研究标题自身限定为 "breast pump-dependent mothers with premature infants" | **是**，且**人群外推风险**（FTC HPCG Example 34 明确禁止把特定受试人群结论外推到一般人群） |
| **Willow** | "**Clinically proven** design for output, powered by ComfortFlow™"（H2 标题） | 未见整机 RCT 引用 | **是（clinically proven）**，且按 Example 18 存在"测试对象是零件不是整机"的问题 |
| **Willow** | "105° flange angle **clinically proven to encourage more milk**" | 无 | **是** |
| **Willow** | "ComfortFlow™ technology **clinically proven for more milk**" | 无 | **是** |
| **Willow** | "In an **independent survey of 500 pumping moms, 71%** said Willow Go gives better milk output than their…" | 样本量已披露，第三方 | **裸 more milk 的变体**，但有样本量与来源 |
| **Willow** | "**More milk.**"（360 页头图）；"Better Fit. **More Milk.**" | 无任何限定 | **是（最赤裸的形式）** |
| **Elvie** | "Elvie Pump is our most awarded breast pump featuring Smart Rhythms™ to **boost your milk flow**." | 无 | **是（boost milk flow）** |
| **Elvie** | "**Boost your milk flow** without the ouch" | 无 | **是** |
| **Elvie** | "Mimics baby's natural suction to **boosts milk flow**." | 无 | **是（且同时命中 H09 的 mimic baby）** |
| **Lansinoh** | "**79%** of moms…"（NaturalWave 页） | **零脚注、零来源** | **是（未标注来源的效果数据 = M03）** |
| **BabyBuddha** | "Proper flange size can make a big difference in comfort and **milk output**." | 定性，未量化 | 边缘 |
| **Momcozy** | "S12 Pro Quick delivers up to **28.2% faster pumping and 6% more milk output** than the previous model." | "(*Based on Momcozy Lab data)" | **是（M03 未标注来源 + H02 增产）** |
| **Momcozy** | "It helps you achieve **faster letdown, increased milk output, and full breast emptying** comfortably."（S12 Pro FAQ） | 无 | **是（同时命中 H02 的 milk output + 排空效率）** |
| **Momcozy** | "Warmth + Gentle Massage help the body relax, **supporting the natural release of oxytocin—the hormone that triggers milk let-down**."（W1） | `*Based on quantitative findings from internal real-user testing. Results are self-reported. Individual results may vary.` | **是（直接命中 H02 关键词 release oxytocin / trigger…）** |

> **这张表的结论**：
>
> 1. **「more milk」不是行业禁忌，是行业通例。** 6 个品牌里 **5 个在用**（Medela、Willow、Elvie、Lansinoh、Momcozy）。唯一没用的是 Spectra 与 BabyBuddha（他们改用 "output" / "milk expression" 这类词）。
> 2. **真正的分界线是「有没有可核验证据」，不是「用不用这个词」。** Medela 用 NCT 号；Willow 用第三方样本量；Lansinoh 什么都没用（这是最危险的）；Momcozy 用"内部测试"（不足）。
> 3. **委托方的 H02 把「词」当红线，而行业的实际约束是「证据」。** 这是本分片最重要的规则校准发现。

#### 卖点 B — 舒适 / 疼痛（对应 Momcozy H07）

| 品牌 | 逐字文案 | 说明 |
|---|---|---|
| **Medela** | "for increased **comfort** and more milk"; "reduce pressure on your milk ducts, resulting in better milk flow and an overall **more comfortable** experience" | 只用 comfort，**不用 pain** |
| **Elvie** | "**Boost your milk flow without the ouch**" | 「ouch」是口语化疼痛指代，**规避了 pain 一词** |
| **Willow** | "clinically designed to **reduce nipple pain** and improve milk expression" | **直接用了 reduce nipple pain** — 这是 Momcozy H01 的禁用词 `reduce nipple damage` 的邻近表达，也是 H07 的 `reduce pain` |
| **Willow** | "**100% comfort rating**" | 量化了主观体验（100%），属于 H05 的 `100%` 模式 |
| **BabyBuddha** | "comfort", "gentle", "minimizing pressure on the breast" | 全部走 comfort 路线 |
| **Momcozy** | 规则库 H07 禁用 `less pain`/`reduce pain`；安全词表**同时**把 `reduces pain`/`less pain` 列为合规 | **内部矛盾** |

> **结论**：**Willow 在用 `reduce nipple pain`**，而且是在官网产品页。这属于「行业通行但 Momcozy 现在禁止」的典型。但按 FTC 口径，`reduce nipple pain` 是**客观声称**（可测、可证伪），因此需要 substantiation；Willow 配的 "clinically designed" 措辞**恰恰是在暗示有临床依据而没有给出引用** —— 这是 Willow 的合规弱点，不是 Momcozy 应当效仿的模板。
>
> **对 Momcozy 的建议**：H07 的红线应当**保留**（因为 `reduce pain` 是需要 RCT 级证据的客观声称，而 Momcozy 没有），但 `依据来源` 应当从「吸奶器广告文案审计_红绿灯.xlsx」升级为 `FTC HPCG 2022（客观声称需 substantiation）+ FTC Deception Policy 1983（subjective vs affirmative claim 分界）`。**同时必须修掉安全词表里 `reduces pain`/`less pain` 的自相矛盾。**

#### 卖点 C — 效率 / 排空 / 漏奶（对应 Momcozy M07）

| 品牌 | 逐字文案 | 限定语 |
|---|---|---|
| **Medela** | "help to customise your session for **maximum comfort and efficiency**" | 无量化 |
| **Willow** | "**Designed for comfort & efficiency**"（Sync 页标题） | 无量化 |
| **Willow** | "Replace pump parts every 90 days to maintain suction and **efficiency**" | **这是"维护保养"语义的效率，不是功效声称** |
| **Willow** | "**100% leak-proof**"（360 页，页面多处） | 无。这是 H05 的 `100%` 模式 |
| **Willow** | "Innovative soft silicone meets firm PP for a **secure, leak-free seal**" | 与 100% leak-proof 不同，这个是结构描述 |
| **Momcozy** | "**100% leak-proof**"（产品页）；M07 禁用 `leak-proof pumping`/`leak proof`/"杜绝漏奶" | **Momcozy 自己也在用** |
| **Momcozy** | "DoubleFit™ Dual-Layer Flange: **28.2% higher pumping efficiency and 10% fewer leaks.***" | "*Momcozy Lab data" |
| **Elvie** | "Catch every last drop of milk with **leak-free confidence**" | 定性 |

> **关键区分（可以直接做成规则）**：`leak-proof`（描述产品结构）vs `leak-proof pumping`（描述使用结果）。前者是客观结构事实，后者是功效声称。Willow 用的是 **"100% leak-proof" 作为产品属性**（"Willow 3.0 is now 360. 100% leak-proof, hospital-grade, app-controlled"），Momcozy 的 M07 正则 `leak none|no (more )?leak\w*|leak-?proof` 会**误伤前者**。建议 M07 正则收窄为「leak-proof + 动作/结果宾语」模式。

#### 卖点 D — 静音（对应 Momcozy M01）

| 品牌 | 逐字文案 |
|---|---|
| **Elvie** | "The **quietest**¹ slimline breast pump with discreet app control."（脚注 ¹ 存在，内容未在本次抓取范围内核实） |
| **BabyBuddha** | "uses **low-noise** operation" |
| **Momcozy** | 规则库 M01 禁用 `silent`/`noiseless`/`whisper-quiet`，安全词为 `low noise`/`quiet mode`/`low-decibel` |

> **Elvie 用 "the quietest"**（最高级 + 脚注）。**BabyBuddha 用 "low-noise"**（与 Momcozy 安全词表一致）。
>
> **规则校准含义**：M01 把 `silent` 定为"审慎"是合理的（因为绝对静音不可实现，属可证伪的客观声称），但**"the quietest" 是最高级比较，属于 M06/H08 的范畴**，而 Momcozy 的 H05 已经把"best/#1/No.1/最佳/最好等排名最高级按 2026-09-09 口径放开"。**这是一个口径冲突**：如果排名最高级放开，为什么 `silent` 还要审慎？两者都是"最高级客观声称"。建议统一口径：**最高级声称一律归入「需 substantiation」类，而不是"禁止"或"放开"二选一。**

#### 卖点 E — 贴合 / 尺寸（对应 Momcozy H05）

| 品牌 | 逐字文案 | 触碰 H05 |
|---|---|---|
| **Medela** | "three additional inserts to cater to **over 95% of nipples sizes**" | 量化覆盖率 — 可证伪的客观声称 |
| **Medela** | "The anatomically shaped collection cups fit seamlessly in **most** nursing bras" | 用 "most" 而非 "all" — **这是规避 H05 的标准做法** |
| **Willow** | "**ranked #1** in comfort"; "Our best-selling pump with the **most comfortable fit**" | 排名最高级 |
| **Willow** | "Willow Go is the perfect pump for every day with a **100% comfort rating**" | `100%` |
| **Elvie** | "**Discreet**" 系列用词 | 定性 |
| **Momcozy** | H05 禁用 `fits all breast shapes`/`every breast shape`/`one size fits all`/`universal fit`；同时 H05 的说明里写 "best/#1/No.1/最佳/最好等排名最高级按 2026-09-09 口径放开" | — |

> **Medela 的 "most nursing bras" 是最值得学的一条。** 用**限定词**（most / up to / 95%）替代**全称**（all / every / universal），把一个不可核查的全称声称变成一个可核查的比例声称。**这是一条可以直接做成改写建议库模板的规则。**

#### 卖点 F — 医院级 / 医疗级（对应 Momcozy M05、U03）

| 品牌 | 逐字文案 | 说明 |
|---|---|---|
| **Medela** | "**Hospital-grade**" 用于描述**泵系统**（Symphony Plus）；明确否认其配件是 hospital grade：**"No, the Hands-free Collection Cups are not part of the hospital grade pump system Symphony Plus. These cups are not for hospital use; to be sterilized and/or autoclaved"** | **主动划清界线** — Medela 在同一页既用 hospital-grade 又否认配件是 hospital-grade |
| **Medela** | "Freestyle™ Mini **is not a hospital pump**. It is a personal-use, single user breast pump." | 主动降级 |
| **Medela** | "We recommend using **Symphony hospital-grade (multi-user)** breast pump in hospitals" | 把限定语嵌进表述 |
| **Willow** | "100% leak-proof, **hospital-grade**, app-controlled" | **无任何限定** |
| **Willow** | "**15 levels of customizable, hospital-strength, tug-and-release suction (up to 295 mmHG per side)**" | **把 hospital-strength 锚定在具体数值上** — 这是让 M05 变成可核查事实的做法 |
| **Willow** | "Willow 360 has a suction range and strength (up to ~245mmHG) that is **comparable with** traditional double electric and **hospital-grade pumps**" | 用 "comparable with" 而非 "is" |
| **Elvie** | 产品标题直接写 "**Elvie Stride 2: Hospital-Grade Suction Breast Pump**" / "**Elvie Stride: Hospital-Grade Electric Breast Pump**" | **把 hospital-grade 写进产品名** |
| **Lansinoh** | 在 6 个页面混用 hospital **GRADE** / **STRENGTH** / **-GRADE**，锚定在一个 280 mmHg 数值上 | 三个变体混用 |
| **BabyBuddha** | "Designed to maintain the **hospital-grade strength** the BabyBuddha double electric pump is known for" | 无量化 |
| **Spectra** | "S3 Pro **Multi-User Hospital-Grade** Breast Pump" | 写进产品名 |
| **Momcozy** | 集合页 URL 就叫 `collections/hospital-grade-breast-pump`；产品页 V1 Pro 标题 "**Redefined Hospital-Grade Solution**" | 写进集合页与产品页 |
| **Momcozy** | M05 把 `hospital grade`/`medical grade silicone`/`military grade` 定为**审慎（需核实是否有对应认证）** | — |
| **BabyBuddha** | "utilize one piece **FDA Compliant** construction"（duckbill valves，重复出现在 3 个产品页） | **第四个 FDA 变体** |

> **重要发现：`hospital-grade` 是一个行业通用的营销词，没有任何法定定义。** 6 个品牌里 **6 个都在用**（Medela、Willow、Elvie、Lansinoh、BabyBuddha、Spectra、Momcozy —— 实际上全部）。
>
> **但有两种用法是有本质区别的**：
> - **可核查用法**：`hospital-strength suction (up to 295 mmHG per side)` —— 锚定在物理量上，可验证。**Willow 与 Lansinoh 用这一种。**
> - **不可核查用法**：`Hospital-Grade Suction Breast Pump` 写进产品名 —— 无法验证"hospital grade"是什么意思。**Elvie、Spectra、Momcozy 用这一种。**
> - **Medela 用第三种：主动否认。** 这是最保守也最安全的做法。
>
> **对 M05 的校准建议**：不要按"是否使用 grade 词"判险（那是全行业都在用的词，判险等于自缚），而应当按 **「grade 词是否锚定在可核查的具体参数上」** 判险。`hospital-grade suction`（裸）→ 审慎；`hospital-strength suction up to 295 mmHg` → 合规；`hospital-grade` 写进产品名 → 高危（因为它成了产品身份的一部分，落入 UCPD Art. 6(1)(b) 的 "main characteristics of the product"）。

### 7.3 FDA 表述的竞品实证（对应 Momcozy H06）

**这是本分片最锋利的证据。**

| 品牌 | 逐字文案 | 页面 | 判定 |
|---|---|---|---|
| **BabyBuddha** | "BabyBuddha has gone through the processes to get our pump **CPSC-certified and FDA-approved** so that we can not only offer it through insurance but so that you don't have to worry if you're using a pump that is safe for you and your baby." | babybuddhaproducts.com/pages/certifications | ❌ **违反 21 CFR 807.97**（同一页印着 `FDAFDA 510K# K151284`） |
| **BabyBuddha** | "Our electric pump, pump parts, baby bottles, and accessories have been **tested and approved by the Consumer Products Safety Commission (CPSC) and the U.S. Food and Drug Administration (FDA)**." | 同上 | ❌ **违反 21 CFR 807.97**；且 CPSC 不签发 "certified/approved" |
| **BabyBuddha** | "**FDA approval** also gives us the incredible opportunity to offer our breast pump for free through most insurance companies. This is something that many other brands that you may find online cannot do because they have not gone through the **expansive FDA approval process**." | 同上 | ❌ **违反 21 CFR 807.97**；且错误的因果绑定（保险报销 ≠ FDA clearance） |
| **Lansinoh** | "Lansinoh is here for you with first class customer service and a 1-year warranty. **FDA approved**, FSA/HSA eligible" | lansinoh.com/products/wearable-breast-pump（旧款 Wearable Breast Pump） | ❌ **违反 21 CFR 807.97** — 捆在保修句子里，无脚注、无依据 |
| **Willow** | "• Clinically tested, **FDA approved**, and made without BPA for a safer pumping experience." | Willow Sync 产品页 | ❌ **违反 21 CFR 807.97** |
| **Willow** | "US-based, clinically tested, and **FDA approved**." | Willow（多处） | ❌ **违反 21 CFR 807.97** |
| **Willow** | "Every Willow pump is app-connected, **FDA cleared**, clinically tested, and ranked #1 in customer satisfaction among breast pump brands." | Willow（多处） | ✅ **正确用法** |
| **Willow** | "**FDA cleared** & clicnically tested"（原文拼写错误 "clicnically"） | Willow 页 | ✅ 正确用法（但有拼写错误） |
| **BabyBuddha** | "utilize one piece **FDA Compliant** construction" | 3 个 duckbill valve 产品页 | ⚠️ **无法源变体** — "FDA compliant" 无法律定义 |
| **Elvie** | "BPA free and food safe. **FDA approved**."（Elvie Pump PDP bullet） | elvie.com | ❌ **违反 21 CFR 807.97** |
| **Elvie** | "**DO Choose a Pump That's FDA Approved** & Clinically Tested"（博客小标题），**而同一篇正文写** "Cheap dupes usually lack a dedicated website and are not **FDA cleared**." | elvie.com 博客 | ❌ **同文内 approved / cleared 混用**，且小标题错、正文对 |
| **Willow** | 全站 **"FDA approved" 5 处 / 5 页；"FDA cleared" 7 处 / 5 页**；**有 2 个页面同时使用两个动词** | onewillow.com | ❌ 部分违规（5 页中误用 approved 的页） |
| **Medela** | 9 个页面**零 FDA 表述** | — | ✅ 最保守 |
| **Spectra** | **47 个产品 + 12 个页面，零 FDA 表述、零百分比声称、零临床引用、零 results-vary 免责** | — | ✅ **本组最干净的品牌，可作负对照（见 §7.10）** |
| **Momcozy W1** | "**FDA 510(k) Cleared.** Made with Care." / "Wellness 1 is **FDA 510(k) Cleared** and made with BPA-free milk-contact materials…" | momcozy.com W1 产品页 | ✅ 正确用法（**对应 K 号待核实**，见 R5-C5 与 §12 G3） |
| **Momcozy M9** | DoubleFit 法兰 "**FDA and LFGB certified**" | momcozy.com M9 产品页 | ⚠️ **材料级而非器械级** — 不能说"FDA certified"；法兰是器械配件，其"FDA certified"无依据。**这是 Momcozy 站内第二个 FDA 表述错误** |
| **Momcozy（规则）** | H06 正则 `\bFDA\s+(approved\|certified)\b`；豁免词含 `FDA cleared`/`FDA-cleared`/`FDA registered`/`FDA 注册` | — | ⚠️ 正则**漏掉 "FDA compliant"**、**漏掉 "FDA and LFGB certified" 这种 "FDA certified" 的变体语序**；豁免词里的 `FDA registered` 有风险 |

**统计（完整口径，跨全部 7 个品牌）**：

| 用法 | 出现在几个品牌 | 判定 |
|---|---|---|
| `FDA approved`（正确动词应为 cleared） | **4 个品牌**：BabyBuddha、Lansinoh、Willow、Elvie | ❌ 违反 21 CFR 807.97 |
| `FDA compliant` | 1 个品牌：BabyBuddha | ⚠️ 无法源术语 |
| `FDA certified`（含 "FDA and LFGB certified"） | 1 个品牌：Momcozy（M9，材料级） | ⚠️ 器械配件不适用 certified |
| `FDA cleared`（正确用法） | 2 个品牌：Willow、Momcozy（W1） | ✅ 但需对应 K 号 |
| **零 FDA 表述** | 2 个品牌：Medela、Spectra | ✅ 最保守 |
| **同站/同文混用 approved 与 cleared** | 2 个品牌：Willow（2 页）、Elvie（同文小标题 vs 正文） | ❌ 净印象冲突（FTC Deception Policy 1983 "entire mosaic"） |
| **给出 510(k) 编号** | **1 个品牌：BabyBuddha（`FDAFDA 510K# K151284`）—— 而它同时说 "approved"** | ❌ 最讽刺的一例 |

> **「7 个品牌里 4 个误用 FDA approved，2 个混用，2 个零表述，只有 1 个品牌给出 K 号而它同时说 approved」——这个分布本身就说明 H06 是一条真实的、全行业普遍违反而未被执法的规则。** 委托方不应当因为"别人都在用"而放松 H06；恰恰相反，**H06 是 Momcozy 相对竞品的一个真实合规优势**（Momcozy 用词是 cleared，是全组唯一一个既用对动词、又没有混用的品牌之一）。

**Momcozy 站内 FDA 表述的完整清单（第三方抓取方核实）**：momcozy.com 全站仅有 **3 处** FDA 字符串，集中在 1 个产品上 —— Wellness 1 的 "FDA 510(k) Cleared"（2 处）与 M9 的 "FDA and LFGB certified"（1 处）。**站内没有 "FDA approved"、"FDA registered"、"FDA-listed"、"FDA compliant"，也没有企业注册声明。**

> **这个不对称性很重要**：Momcozy 自己的 FDA 用词**整体比 BabyBuddha / Lansinoh / Willow 规范**。"FDA 510(k) Cleared" 在事实层面是站得住的（前提是 K 号覆盖），而 BabyBuddha 的 "FDA-approved" 是**确定违法**。**委托方在 H06 上的任务不是"重写"，而是"收紧边界 + 补一个 K 号校验字段"。**

> **四条可直接落地的结论**：
>
> 1. **H06 的正则必须扩展**：`\bFDA[\s-]+(approved|certified|compliant|endorsed|verified|authorized|qualified)\b`。本次调研在竞品上实测到 **3 个变体在用**（approved ×3 品牌、compliant ×1 品牌，certified 见 Momcozy M9 的语序变体）。**注意 "FDA and LFGB certified" 这种中间插词的语序，简单正则 `\bFDA\s+certified\b` 会漏检。**
> 2. **`FDA registered` 必须从豁免词移出**。理由：21 CFR 807.22 的年度注册机制 + FDA 官方页面明说 registration "does not denote approval, clearance, or authorization"。文案人员看到豁免词表里有 "FDA registered"，会写 "FDA registered facility" 来暗示 FDA 认可 —— 这正是 FDA 官方页面点名批判的行为。
> 3. **「FDA cleared」的正确使用需要附加约束**：必须能对应到一个**具体的 K 号**，且该 K 号的器械名/型号必须覆盖被宣传的产品。**Momcozy 的 W1 页面是本次调研唯一一个需要进一步核实的具体风险点**（见 R5-C5）。
> 4. **新增一条规则 Z1**：禁止把 FDA clearance 与**保险报销资格**做因果绑定。BabyBuddha 明写 *"FDA approval also gives us the incredible opportunity to offer our breast pump for free through most insurance companies"* —— 这两件事在美国没有因果关系（保险报销取决于保险计划、HSA/FSA 规则与处方要求，不取决于 FDA clearance）。这条同时命中 **FTC Deception Policy 1983**（虚假因果关系）与 **H06 的立法目的**。Momcozy 的 U02（保险/HSA/FSA 声明）目前因为"资质已具备"被停用 —— **建议与这条新规则合并处理**。

### 7.4 免责声明的真实样本（豁免词字段的行业模板）

**在 19 个 Medela + Lansinoh 页面里，"not intended to treat" / "not intended to diagnose" / "results may vary" / "consult your physician" 出现 0 次。**

行业实际使用的模板，按可信度从高到低：

**模板 1 — 临床注册号（Medela，最硬）**
> `*Clinical studies, PersonalFit Flex™ compared to PersonalFit data on file (NCT02496429, NCT02492139, NCT02719548, NCT03091985)`
> `4. Clinical study, Data on file (NCT02492139 compared to 90°).`
> `** Clinical studies, PersonalFit Plus compared to PersonalFit data on file`
>
> 特点：给出 **ClinicalTrials.gov 注册号**。可被第三方独立复核。**这是行业里最接近 FTC 层级 1 的做法。**

**模板 2 — 第三方独立调研 + 样本量（Willow，全站最好的脚注）**
> `*Brandtracker independent survey by **Rabin Roberts Research** of **500 pumping moms**, **November 2024**`
> `In an independent survey of 500 pumping moms, 71% said Willow Go gives better milk output than their…`
> `"In a third-party survey of pumping moms, Willow had the #1 customer satisfaction rating*"`
> `"Willow's pumps were 'tested by real moms under the guidance of an institutional review board and…'"`
>
> 特点：披露**调研机构名**（Rabin Roberts Research）、**样本量**（500）、**调研时间**（November 2024）、**独立性**（independent / third-party）、**IRB**。**这是本分片找到的最完整的第三方调研脚注**，可以直接作为委托方改写建议库的"最佳实践模板"。但仍是 survey，属 FTC 层级 4。
>
> ⚠️ **同时注意同一个品牌的执行力缺口**：第三方抓取方核实，Willow Go 页面上有 **6 处裸的 "N% of moms" 声称，全页无脚注**（含一处 71% 的奶量声称）；`grep -c "usage survey"` = 0，**解析脚注只存在于另一个页面**。**这说明"有一个好模板"和"模板被执行到每一处声称"是两件事** —— 委托方在设计规则库时应当把"每个量化声称必须紧邻其证据标记"做成**结构校验**，而不只是提供一个模板库。

**模板 3 — 内部测试 + 自陈 + 结果因人而异（Momcozy W1，最弱但格式完整）**
> `*Based on quantitative findings from internal real-user testing. Results are self-reported. Individual results may vary.`
>
> 特点：格式完整（说明了数据来源、性质、变异性），但**证据层级不足**（FTC 明说消费者自陈/anecdotal 不足）。

**模板 4 — 内部 Lab 数据（Momcozy S12 Pro / M5，形式最短）**
> `(*Based on Momcozy Lab data)`
> `based on internal user feedback`
>
> 特点：**最弱的模板**。既没披露样本量，也不是独立来源，也没说明测试条件。

**模板 5 — 无任何声明的裸声称（Lansinoh，最危险）**
> `79% of moms…`（无脚注）
> `FDA approved, FSA/HSA eligible`（无脚注）
> `clinically proven`（无脚注）
>
> 特点：Lansinoh 全部 10 页 **0 个脚注**。

**模板 6 — 用途限制型免责（Medela，唯一"真免责"型）**
> `The Hands-free Collection Cups are not intended to be used for milk storage.`
>
> 特点：这不是免责，是**用途边界声明**。它划清"这个配件能做什么/不能做什么"，恰好对应 21 CFR 801.5 的 adequate directions 要求。

**模板 7 — 品类否定型（Elvie/其他母婴品牌常见，非吸奶器）**
> `(Note: NOT A MEDICAL DEVICE and not intended to diagnose medical conditions/SIDS)`
> `Statements regarding dietary supplements have not been evaluated by the FDA and are not intended to diagnose, treat, cure, or prevent any disease or health condition.`
>
> 特点：后一句是 **DSHEA 法定免责声明**（21 U.S.C. 343(r)(6)），**只对膳食补充剂有效**。⚠️ **吸奶器是医疗器械，套用这句 DSHEA 免责声明是错的**，而且会产生反效果（暗示自己是补充剂）。委托方需注意不要误用这条行业里到处泛滥的模板。

### 7.5 竞品表达方法论总结：五种「边界规避手法」

从 7 个品牌的语料里可以归纳出五种可复用的替代策略。**这五种手法比"禁用词表"更有价值，应当直接写进改写建议库的模板层。**

| 手法 | 定义 | 竞品实例（逐字） | 对应委托方规则 |
|---|---|---|---|
| **① 全称 → 比例** | 把不可核查的 all/every 换成可核查的比例 | Medela: "cater to **over 95% of nipples sizes**"；"fit seamlessly in **most** nursing bras"；Willow: "ranked #1… **among** breast pump brands" | H05（fits all breast shapes） |
| **② 绝对 → 上限** | 把绝对功效换成标称参数上限 | Willow: "**up to 295 mmHG per side**"；BabyBuddha: "Adjustable suction ranging from **53 to 315 mmHg**"；Momcozy W1: "up to **295 mmHg** of suction" | M02（超强吸力） |
| **③ 结果 → 机制** | 不说"会更舒服"，说"我们做了减压设计" | Medela: "puts **less pressure on your milk ducts**"；BabyBuddha: "**minimizing pressure on the breast**"；Elvie: "**105° flange angle**, longer tunnel, curved edges" | H07（疼痛功效） |
| **④ 功效 → 结构/材质事实** | 把"防漏"改写为"封闭系统 / 双层结构" | Willow: "**closed-system pump**, just like hospital-grade pumps, to keep your breast milk separate from the pump mechanisms"；Medela: "**Closed system with BPA-free construction**" | M07（漏奶） |
| **⑤ 模仿 → 灵感** | 不说"模拟宝宝"，说"参考自然哺乳的设计" | Medela 用 "**mimic** your baby's natural sucking rhythm"（**注意：Medela 直接用 mimic，这才是行业实况**）；Momcozy H09 则要求改写为 `inspired by natural nursing` | H09（mimic baby） |

> **⚠️ 手法 ⑤ 必须诚实标注一个反例**：**Medela 官网当前正在用 "mimic your baby's natural sucking pattern"**（Freestyle Mini、Harmony、Swing Maxi 等多页）：
> - `"Powerful performance: Medela's research-based pumping curves and patented 2-Phase Expression Technology **mimic your baby's natural sucking patterns** for effective and comfortable milk expression."`
> - `"2-Phase Expression® Technology **mimics babies' natural sucking rhythm** – faster at first to stimulate milk flow, then slower to feed"`
> - `"its unique handle helps you **mimic your baby's natural sucking rhythm**"`
>
> 也就是说，**H09 禁止的 "mimics your baby"，品类第一品牌 Medela 在官网首页级位置全线在用，且带专利号（patented 2-Phase Expression®）和临床引用。** 这属于「行业通行但 Momcozy 现在禁止」的最强样本。**H09 的判定理由（W1 是用户主动调节+保存程序，非闭环生理识别）在产品层面是成立的**，但从规则校准角度，H09 的措辞应当从「禁止 mimic 类表达」收窄为「**禁止声称设备能自动识别/闭环反馈生理信号**」，因为前者是整个行业的通用修辞。

### 7.6 竞品合规弱点清单（Momcozy 不要模仿的东西）

这一节是反向价值：**同样受 FTC 管辖的竞品，他们的合规风险点在哪儿。** 这些是 Momcozy 应当**避开**而不是效仿的。

| # | 竞品 | 风险点 | 逐字证据 | 法源 |
|---|---|---|---|---|
| 1 | **Lansinoh** | 「FDA approved」+ 零依据 | "FDA approved, FSA/HSA eligible" | 21 CFR 807.97；UCPD Annex I §4 |
| 2 | **Willow** | 「FDA approved」与「FDA cleared」同站混用 | Sync 页 "FDA approved"；其他页 "FDA cleared" | 同上 |
| 3 | **Lansinoh** | 10 页 **0 脚注** 却用了 `clinically proven` / `hospital grade` / `79%` | — | FTC 1984 Substantiation Policy（express substantiation claim） |
| 4 | **Lansinoh** | 给产后母亲开**处方级催奶方案**，无医疗免责、无"咨询医生" | Signature Comfort 页 "Set aside about one uninterrupted hour and follow this pattern: Pump for 20 minutes…" | FTC Deception Policy（易感群体判定）；EU UCPD Art. 7 误导性遗漏 |
| 5 | **Willow** | `clinically proven 105° flange` — 测的是零件不是整机 | "105° flange angle clinically proven to encourage more milk" | FTC HPCG 2022 Example 18 |
| 6 | **Willow** | `reduce nipple pain` 是客观声称，配 "clinically designed" 却无引用 | "clinically designed to reduce nipple pain and improve milk expression" | FTC HPCG 2022 §2 |
| 7 | **Willow** | 「100% comfort rating」/「100% leak-proof」 — 100% 绝对声称 | — | FTC Deception Policy（可证伪的绝对声称） |
| 8 | **Medela** | 「Up to 50% more milk within first 2 weeks」的人群外推 | 引用研究自身限定 "breast pump-dependent mothers with premature infants" | FTC HPCG 2022 Example 34（特定人群结论不得外推到一般人群） |
| 9 | **Medela** | PIS Pro+ 页面有脚注标记 `1` 但 References 段落**空的** | 页面缺陷 | FTC 1984（宣称有证据但未提供） |
| 10 | **BabyBuddha** | 「FDA Compliant」 — 无法源术语 | "one piece FDA Compliant construction" | 21 CFR 807.97（精神上同类）；无官方定义 |
| 11 | **Elvie** | `the quietest` 最高级声称 | "The quietest¹ slimline breast pump" | FTC 1984（express substantiation claim） |
| 12 | **Spectra / Elvie / Momcozy** | 把 `Hospital-Grade` 写进**产品名** | "Elvie Stride 2: Hospital-Grade Suction Breast Pump"；"S3 Pro Multi-User Hospital-Grade" | UCPD Art. 6(1)(b)（main characteristics of the product） |
| 13 | **BabyBuddha** | certifications 页**三次**声称 FDA approved，同页印 `FDAFDA 510K# K151284` | 见 §7.3 | 21 CFR 807.97（**最直接的 misbranding 样本**） |
| 14 | **BabyBuddha** | "CPSC-certified" — CPSC 不签发认证 | "get our pump **CPSC-certified**" | 无依据的认证声称 |
| 15 | **BabyBuddha** | 把 FDA clearance 与保险报销做因果绑定 | "**FDA approval** also gives us the incredible opportunity to offer our breast pump for free through most insurance companies" | FTC Deception Policy 1983（虚假因果关系） |
| 16 | **BabyBuddha** | 3.0 PDP 声称 "increase your milk supply"，**全页无 results-vary 免责**；且**同页 AI 评论摘要自陈** "opinions on flange comfort and milk supply increase are mixed" | — | FTC HPCG 2022（客观声称无 substantiation）+ FTC Deception Policy（净印象） |
| 17 | **BabyBuddha** | 获奖行写 "2026 What to Expect - Best Wearable Pump For Boosting Milk Supply"，而**同页说明 3.0 不是 wearable** | — | 内部自相矛盾 → 净印象误导 |
| 18 | **Momcozy（自身）** | **跨渠道 hospital-grade 自相矛盾**（详见 §7.7） | 见 §7.7 | UCPD Art. 6(1)(b)；FTC Deception Policy（净印象） |
| 19 | **Momcozy（自身）** | **`28.2%` 在 5 个产品上复用，3 种含义、3 种依据**（详见 §7.8） | 见 §7.8 | FTC HPCG 2022 §1（"must have at least the level of support that they claim to have"）+ UCPD Art. 6(1)(b) |
| 20 | **Momcozy（自身）** | **免责声明不对称**：~14 处 "more milk"/"boost" 类表述只对 1 处（W1 的 ~70%）附了 "Individual results may vary" | 见 §7.8 | FTC Deception Policy 1983（整体净印象） |
| 21 | **Momcozy 自身** | M6 亚马逊 bullet 把功效依据写成 "Through over 1,000 trials"，而官网同产品页写 "over 1,100 moms"，Mobile Flow 页又写 "over 1,000 trials"（用于**贴合度**而非奶量） | 见 §7.8 | FTC 1984（针对"证据数量"的断言必须准确） |
| 22 | **Momcozy 自身** | 吸力峰值自相矛盾：V1 Pro 宣称 -300 mmHg，同时官网教学页主张 "what matters most… is the pump's ability to maintain comfortable, consistent pressure… prioritizing sustained performance over single-point peak claims" —— **而自己的对比表正是在展示峰值** | — | 内部口径冲突 |
| 23 | **Willow** | 旗舰功效声称「clinically proven」但**页面零引用** | "105° flange cone **clinically proven to express a higher volume of milk in less time, with higher peak flow rates, and shorter time to first milk ejection**" —— 页面无研究名/期刊/DOI/年份/作者 | FTC HPCG 2022 §1（"must have at least the level of support that they claim to have"）+ Example 18 |
| 24 | **Willow** | Willow Go 页 **6 处裸 "N% of moms" 声称，全页无脚注** | 含一处 71% 的奶量声称；`grep -c "usage survey"` = 0。解析脚注只存在于另一个页面 | FTC 1984（数量/层级断言必须准确）|
| 25 | **Elvie** | `99% of nipples` 是**模型输出**，且分母在**同一页上在 nipples 与 women 之间来回切换** | "Fits 99% of nipples"；底层是内部 **454 个乳头**（非女性人数）的研究，基于 Elvie 自设的 2–4mm 假设；同页又说 "6 sizes included" 与 "5 sizes of inserts" | FTC HPCG 2022 §1 + Example 18（测试对象与声称对象不匹配） |
| 26 | **Elvie** | `3x effective`（Smart Rhythms）**完全没有脚注** | — | FTC 1984 |
| 27 | **Elvie** | Highest/Quietest/Smallest/Slimmest 比较级依据**冻结在 2021 Q2–2022 Q2 的销售数据**，约 4.5 年前的数据用现在时呈现 | — | FTC 1984（证据必须支持当前声称）+ UCPD Art. 6(1)(b) |
| 28 | **Elvie（最高风险项）** | AI 聊天机器人 "Ema" 被营销为 **"medically validated"** / **"clinically trained"**，涉及**产后抑郁、乳腺炎、子宫脱垂**，并声称 *"reviewed by more than 1,000 medical professionals"*、*"10 million interactions with over 100,000 women"* —— **无任何免责声明、无任何验证证据** | "Unlike a search engine, Ema's knowledge base is curated and **medically validated** — the result of a commitment to use technology responsibly."；"answers are generated from a curated knowledge base built on extensive women's health content and **reviewed by more than 1,000 medical professionals** (such as OBGYNs)"；"**Ema is clinically trained** in women's health to offer Willow moms contextual and holistic guidance they can trust." | FTC Deception Policy 1983（易感群体 + 疾病相关声称）+ FTC HPCG 2022（health benefit 需 RCT）+ **欧盟：MDR Art. 2(1)**（声称用于 diagnosis/monitoring/treatment 的软件即为医疗器械 —— **这条对 "Ema" 是致命的**） |
| 29 | **Willow + Elvie（共同）** | **32 个页面中 31 个没有任何医疗免责声明**。整个联合店铺只有 1 处免责声明，在一篇 Willow 博客文章上 —— 且 **Willow 讲述 "Ema" 的页面、以及 "Ways to Increase Milk Supply" 这篇健康建议文章都没有免责声明** | — | FTC Deception Policy 1983（净印象）|
| 30 | **Elvie** | 孤儿脚注：Elvie Stride 页有 "2. Fits 99% of nipples" 的脚注，但页面**没有对应的 ² 标记或 99% 声称**；另一处 "1. vs. Elvie Stride" 的脚注在 Stride 自己页面上变成**循环引用** | — | 内容质量缺陷；如果脚注本应挂在某处声称上，则属未完成披露 |
| 31 | **Willow + Elvie（共同）** | **同一发布主体**：elvie.com 页脚为 `Copyright © 2014-2026, Willow Innovations, Inc.`，两站共用同一 Shopify 店铺。**内容缺陷的责任归属是共同的** | — | 组织事实：委托方在竞争对手分析中不应把 Willow 与 Elvie 当作两个独立主体 |

### 7.7 特殊发现 A：Momcozy 自己在三个渠道上对「hospital grade」同时持有三种立场

**这是本次调研在委托方自有品牌上发现的、可以直接处置的内部矛盾。三个渠道均为 2026-09-15 实时在线。**

**立场 (a) —— 否认**（`https://momcozy.com/collections/hospital-grade-breast-pump`，产品名就叫 "hospital-grade"，页面内容却否认该词）：

> **Q: Is hospital strength the same as hospital grade for breast pumps?**
> "Hospital strength and hospital grade are related but distinct terms. A hospital-grade pump is a multi-user rental device built for clinical settings, with specialized motor technology and programming designed to support mothers with medical necessity. '**Hospital strength**' is a manufacturer-used term describing powerful suction performance in a single-user personal pump — **it does not mean hospital grade.**"
> "While some brands use these terms loosely, they are not interchangeable. Hospital-grade pumps are generally recognized for delivering strong, consistent suction in clinical settings, **though there is no official regulatory standard defining a specific mmHg threshold for either term.**"
> "When evaluating a pump, look beyond the label. Consider consistent suction performance across a full session, comfort and adjustability of settings, and how well the pump fits your daily lifestyle — **these factors matter far more than any marketing term.**"

> （另一段）"Pumps are generally considered hospital grade when they sustain suction at or above **-250 mmHg**. The Momcozy V1 Pro reaches **-300 mmHg** in Expression and Mixed modes, placing it within this range. Standard personal-use wearable pumps typically cap between **-180 and -220 mmHg**."

**立场 (b) —— 主张**（`https://momcozy.com/collections/electric-breast-pump`）：

> "**V Series** — Separated-motor design with **hospital grade suction** - powerful pump, lightweight fit."

**立场 (c) —— 在亚马逊主张**（ASIN `B0CZNQ7VH7`，US 站，抓取 2026-09-15）：

> **Listing title（逐字）**：`Momcozy V1 Pro Wearable Breast Pump, **Hospital-Grade** Pocket Primary Pump | Hands-Free Portable Pump, Lightweight, Visible Cups,Real Milk Removal`
> **Bullet 1（逐字）**：`Built for Real Milk Removal: With **hospital grade breast pump suction up to 300mmHg**, 3 fine-tuned rhythms, and 15 adjustable levels, the Momcozy V1pro supports stronger, more personalized pumping—not just wearable breast pump convenience.`
> **结构化属性（逐字）**：`Product Style: **hospital grade**`

> **同时注意**：V1 Pro 在官网的 URL handle 是 `.../products/v1-pro-**hospital-grade**-wearable-breast-pump`，但其 H1 标题写的是 "**Hospital-Strength**"。

**为什么这是本分片最有价值的单条发现：**

1. **立场 (a) 的内容实际上是委托方最有价值的合规资产。** 它准确地说明了「hospital grade」与「hospital strength」的区别，并且**明确承认这两个词都没有官方法定定义**。这段文字本身就是对 M05 的正确答案，而且是**品类内唯一一家把这件事讲清楚的品牌**。
2. **但立场 (b) 与 (c) 在同一个品牌下推翻了它。** 消费者如果在亚马逊看到 "Hospital-Grade Pocket Primary Pump" 并读到官网说 "hospital grade 指的是多用户租赁设备、我们的 single-user 泵不是 hospital grade"，这就是 **FTC Deception Policy 1983 所说的 "the entire mosaic"** 意义上的净印象冲突 —— 而且**跨渠道的净印象也算在内**（FTC 与 UCPD 都按整体商业行为判断）。
3. **法源**：UCPD Art. 6(1)(b)（the main characteristics of the product … specification）—— **结构化属性 `Product Style: hospital grade` 是品牌自己填的字段，属于最典型的 "specification"**。美国侧对应 FTC Deception Policy 1983 的 materiality 分析（消费者会因为 hospital grade 而改变购买决策）。
4. **对 M05 的直接含义**：M05 现在的判定是「审慎关注，需核实是否有对应认证」。**按立场 (a) 的口径，正确做法不是"核实认证"（因为不存在这样的认证），而是"查跨渠道一致性"。** 这是 M05 判定逻辑需要改的地方。

**建议动作**：把立场 (a) 的整段 Q&A 提升为**品牌级的官方术语表**，并作为「安全词/审慎词」的判定依据；同时**清理立场 (b)(c)，或至少把 (c) 的标题与结构化属性改为 "hospital-strength"**（与其 H1 一致）。

### 7.8 特殊发现 B：`28.2%` —— 一个数字，5 个产品，3 种含义，3 种依据

这是本分片最好的「substantiations 测试用例」，因为它把 FTC HPCG 2022 §1 的规则（*"must have at least the level of support that they claim to have"*）变成了一道可以逐条打分的题。

| 产品 | 逐字文案 | 声称的含义 | 声明的依据 |
|---|---|---|---|
| **M5 Smart** | "The exclusive DoubleFit™ flange is made to fit more securely and comfortably, helping reduce slips and tugs while **boosting pumping efficiency by 28.2%** based on **internal user feedback**." | 泵送**效率** | internal user feedback |
| **M5 Smart**（同页另一处） | "This innovative design not only reduces discomfort during pumping but also **improves pumping efficiency by 28.2%** while **reducing leakage by 10%**." | 泵送效率 + 漏奶 | 无 |
| **Wellness 1 (W1)** | "**28.2% higher pumping efficiency and 10% fewer leaks.***"（脚注：`*Based on quantitative findings from internal real-user testing. Results are self-reported. Individual results may vary.`） | 泵送效率 + 漏奶 | internal real-user testing（自陈）+ 免责声明 |
| **S12 Pro Quick** | "With powerful -292 mmHg suction and the exclusive DoubleFit™ hybrid flange, S12 Pro Quick delivers **up to 28.2% faster pumping and 6% more milk output** than the previous model."（脚注：`*Based on Momcozy Lab data`） | 泵送**速度** + **奶量** | Momcozy Lab data（内部实验室，未披露方法） |
| **V1 Pro** | "Endorsed by **Momcozy's user testing research**, the DoubleFit™ flange **can potentially increase milk production by 28.2%**." | **奶量产出** | Momcozy's user testing research |
| **V2 Pro** | 同上（逐字相同） | **奶量产出** | Momcozy's user testing research |
| **Electric Pump 集合页** | "A soft inner flange meets a firm outer layer for a secure, comfortable fit — helping **improve milk output by 28.2%**.*" | **奶量产出** | 无（脚注未在该抓取片段中出现） |
| **Amazon M6 Listing** | "Ideal Rhythm, Boosts Milk Supply: **Through over 1,000 trials**, the Momcozy R&D team has perfected a pumping rhythm that enhances comfort while effectively **increasing milk production**." | 奶量产出 | over 1,000 trials（R&D 内部） |

**同一个 28.2%，被用来支撑三种不同的客观声称**：
1. **泵送效率（pumping efficiency）** —— 机器性能指标，与人体无关
2. **泵送速度（faster pumping）** —— 机器性能指标，与人体无关
3. **奶量产出（increase milk production / more milk output）** —— **人体生理结果，属 FTC 定义的 health-related benefit**

**依据来源同样是三套，且互不衔接**：`internal user feedback` / `internal real-user testing（自陈）` / `Momcozy Lab data` / `Momcozy's user testing research` / `over 1,000 trials`。

**按 FTC HPCG 2022 逐条判定**：

| 声称类型 | FTC 要求的证据层级 | Momcozy 持有的 | 判定 |
|---|---|---|---|
| 泵送效率 / 速度（机器指标） | 产品测试数据即可（不需 RCT） | Lab data / user feedback | ⚠️ 需要**披露测试条件**（对照机型、样本、测量方法）。当前 `*Based on Momcozy Lab data` 不足以让第三方复核 |
| **奶量产出（health-related benefit）** | **RCT**（FTC HPCG 2022 p.13） | user testing research / 1,000 trials | ❌ **不足**。按 FTC HPCG 2022 §「The Amount and Type of Evidence」，"anecdotal evidence about the individual experiences of consumers, including surveys" 不足 |

**这里有一个必须点明的类比错误**：`28.2% faster pumping`（速度）与 `28.2% more milk output`（奶量）是两个不同量纲的指标，不可能来自同一次测量。把它们写成同一个数字，属于 FTC HPCG 2022 Example 18 的同类问题 —— **测试对象与声称对象不匹配**。

**免责声明的不对称也是一个独立问题**：第三方抓取方核实，Momcozy 在官网产品页 + 亚马逊 listing 中共有 **约 14 处** `more milk` / `increase milk supply` / `boost` 类表述，但 **`Individual results may vary` 只挂在 1 处**（W1 的 ~70% 那个数字上）。按 FTC Deception Policy 1983 的 "entire mosaic" 原则，**免责声明的存在与否是按整体广告判断的，不是按单句判断的** —— 这意味着 W1 页面上那条免责声明**无法覆盖 M5 / S12 Pro / V1 Pro / V2 Pro / M6 的同类声称**，也无法覆盖同页的其他声称。

### 7.9 Momcozy 已引用一篇 RCT —— 这条线索比它看起来更重要

**Momcozy W1 页面是全系列唯一一处临床引用**（抓取 2026-09-15）：

> "More Effective Together
> **Research shows warmth and massage together achieved the highest observed milk volume compared with pumping alone.***
> `*Source: Mollaahmetoglu SE & Guvenc G., Breastfeeding Medicine, 2025. RCT of 120 NICU mothers.`"

以及在 "Why Warmth & Massage Make a Difference" 段落：

> "**Higher Milk Volumes**
> 'WHO notes that higher milk volumes have been associated with warming the breast before pumping, as well as with massage and relaxation techniques.' — **Katie Clark, International Board-Certified Lactation Consultant**"

**为什么这条重要**：

1. **这是 Momcozy 全系列唯一的层级 1 证据**。它意味着 **H02 的"无 FDA/临床证据"这一判定理由在当前产品状态下已经不成立**（至少对 W1 的暖敷+按摩声称而言）。**规则库的 `依据来源` 与 H02 的触发原因字段需要按产品/声称更新，而不是按规则全局更新。**
2. **但它有四个 FTC 层面的问题**：
   - **人群外推**：研究的受试者是 **NICU 母亲**（早产儿母亲），而消费者页面卖给的是一般哺乳母亲。**FTC HPCG 2022 Example 34** 明确禁止把特定受试人群的结论外推到一般人群，且要求"Advertisers shouldn't rely on research based on a specific test population for claims targeting the general population without first making sure it is scientifically sound to make such extrapolations."**页面未披露人群限定。**
   - **测试对象是"暖敷+按摩"这个干预，不是 Momcozy W1 这台设备**。 **Example 18** 的问题（"a clinical test of the sports drink itself, rather than the isolated ingredient"）。
   - **无链接**：给了期刊名与年份，但没有 DOI 或链接，无法让消费者或监管者复核。
   - **引用的是"research shows"这个层级断言**，因此按 FTC HPCG 2022 §1，Momcozy 必须**至少持有该断言所传达的证据层级**。
3. **正确做法**：把这条引用**改写为符合 FTC §1 的形式**，例如明确说明「一项针对 NICU 母亲的 120 人 RCT 显示暖敷+按摩与更高的观测奶量相关；Momcozy W1 采用同类暖敷+按摩设计」—— 即**把人群限定与"设计借鉴"的关系写清楚**，而不是把它当作自己产品的功效证据。同时补 DOI 链接。
4. **注意 IBCLC 署名的双重身份**：Katie Clark 是 IBCLC，并且页面还有 "— Lactation Experts & Momcozy Medical Team" 的署名。**按 EU Reg 1924/2006 Art. 12(c)，个人医生/健康专业人士的推荐被明确禁止**；但 Art. 11 允许机构级（协会/慈善机构）推荐适用各国规则。**个人背书与机构背书在欧洲的待遇不同** —— 这正是委托方 U01 与 H04 需要分开处理的法源基础（见 §9.1）。

### 7.10 负对照：Spectra 是全组最干净的品牌

第三方抓取方核实：**Spectra 的 47 个产品 + 12 个页面中，零 FDA 表述、零百分比声称、零临床引用、零 results-vary 免责声明。** 其定位完全依靠 "hospital strength" + mmHg 数值。

**为什么这值得单独列出来**：

- 它是本次调研里**唯一一个"什么都不说"的品牌**，而它在市场上仍然以"医院级"定位著称。**这证明「靠客观参数定位」在吸奶器品类是可行的商业策略**，不是理论上的保守选择。
- 它给出了**规则库"过度禁用"的代价上限**：如果 Momcozy 的规则把 `more milk`、`mimic baby`、`hospital grade`、`clinically proven` 全部判为高危，那么 Momcozy 的表达空间会被压缩到接近 Spectra 的水平 —— 而 Momcozy 的商业模式（DTC + 亚马逊 + 大量 Google/Meta 投放）**依赖比 Spectra 更强的功效沟通**。**规则过严的代价是真实的、可度量的。**
- **对规则校准的含义**：Spectra 可以作为规则库的 **"下限锚点"**（即"如果按最保守品牌的表达方式，文案还能不能跑量？"），而 Medela / Willow 的语料作为 **"上限锚点"**（即"行业头部在什么条件下敢说什么？"）。**规则应当落在两者之间，而不是落在 Spectra 之下。**

---

## 八、平台对母婴/健康类内容的特殊政策

> 证据：`_evidence/R5/platforms/`（**122 个文件**，含 Meta Advertising Standards 逐页原文、Google Ads Policy Help 原文、**TikTok Advertising Policies 15 页全文**、Amazon 政策页[Seller Central 侧为登录墙骨架]）。全部抓取日 2026-09-15。所有引用均为平台政策原文逐字。
>
> **取证方法备注（可复用）**：Meta `transparency.meta.com` 在无完整浏览器头（需 `sec-ch-ua` / `Sec-Fetch-*`）时返回 HTTP 400；TikTok `ads.tiktok.com/i18n/help/article/...` 是 JS SPA 空壳，须改用服务端渲染的 `ads.tiktok.com/help/article/<slug>`；Google 的 answer ID 已变更（Healthcare and medicines = **176031**，非 6020955）。

### 8.0 ⚠️ 失效引用登记表 —— 任务书里给的平台政策 URL 有一部分已经不对了

本节正文（§8.2–§8.5）的平台政策**已全部按现行正文核验**。但核验过程中发现：**四个平台里的三个，其政策页面结构在任务书编写之后已发生变更**，任务书给出的部分 URL 与章节名**已经不成立**。

这条必须单独登记，原因有两个：（1）下游（规则库字段、合规文档、后续审计）如果照抄任务书里的 URL，会拿到**错误的政策页**——Google 的 answer ID 会被复用，不是简单 404 而是**静默指向另一个政策**；（2）本次调研早期笔记里出现过 Meta 与 Google **已不再使用的政策名与措辞**，若不登记，这些旧名会被继续引用。

**证据**：`_evidence/R5/FINDINGS-platform-policies.md` §0.2（URL 核验）与 §2.0（Google answer ID 复用表）；本地原文 `_evidence/R5/platforms/`（**191 个文件**，含 85 份 HTML + 105 份文本提取，逐文件带 `TITLE / URL / FETCH_DATE=2026-09-15` 头）。抓取日 **2026-09-15**（`date` 已核）。

#### (1) 需要更正的引用

| 原引用 | 现状 | 更正后的可用地址 |
|---|---|---|
| Google `adspolicy/answer/6020955` —— 被当作 **Healthcare and medicines** | ⚠️ **该 ID 现为 `Misrepresentation`**。Google 会复用 answer ID | Healthcare and medicines = **`/answer/176031`** |
| Google `adspolicy/answer/6020954` —— 被当作 Editorial | 现为 **`Abusing the ad network`** | Editorial = **`/answer/6021546`** |
| Google `adspolicy/answer/6020956` —— 被当作 Editorial and professional requirements | 现为 **`Data collection and use`** | 该 ID 不再对应编辑类要求 |
| Meta **"Personal health"** 广告标准 | **已不存在**（四个语区均 404） | 其覆盖面拆入 *Health and Wellness* 的 `Adult Products and Reproductive Health` 小节；Meta **没有**独立的 "Data and Privacy" 或 "Health data" 广告标准（已枚举全部 57 个 `/policies/*` 与 44 个 `/ad-standards/*` URL 验证） |
| Meta **"Adult products or services"** 独立标准 | **已并入** *Health and Wellness* | `https://transparency.meta.com/policies/ad-standards/restricted-goods-services/health-wellness/` |
| TikTok `ads.tiktok.com/**i18n/help/article/**…` | **该前缀已失效**（JS 空壳，只渲染出 34 字符） | 服务端渲染的真实入口 = `https://ads.tiktok.com/help/article/<slug>` |
| Amazon `Seller Central` 帮助页（`G…` 编号） | **登录墙**（每页只渲染出约 1,847 字符通用外壳） | 公开替代面 = `https://advertising.amazon.com/help/<ID>` 与 `https://advertising.amazon.com/resources/ad-policy/<完整 slug>` |
| 措辞 **"negative body image"** | Meta **现行正文已不用该短语** | 应改写为 `content implying or attempting to generate negative self-perception in order to promote diet, weight loss or other health related products`（*Advertising Standards: Introduction* → PROMOTING POSITIVE USER EXPERIENCES）；Google 侧对应词是 `Body shaming` / `Negativity related to physical attributes` |

> **对下游的硬性提醒**：引用 Google 政策时**不要复用任务书里的 answer ID**。这些 ID 指向的是**仍然有效但完全不同**的政策页 —— 这是四类失效里唯一会**静默出错**的一类（404 会报错，ID 复用不会）。

#### (2) 仍然有效、且已核验正文的引用（可放心使用）

| 平台 | 地址 | 本地证据 |
|---|---|---|
| Meta | `transparency.meta.com/policies/ad-standards/restricted-goods-services/health-wellness/`（正文变更日 **Jul 22, 2026**） | `meta-health-wellness.html` / `.txt` |
| Meta | `…/privacy-violations/personal-attributes/` | `meta-privacy-violations-personal-attributes.txt` |
| Meta | `…/unacceptable-content/misinformation/` | `meta-unacceptable-content-misinformation.txt` |
| Google | `/adspolicy/answer/176031`（Healthcare and medicines，含分国家矩阵，43,243 字符） | `google-healthcare-and-medicines.html` |
| Google | `/adspolicy/answer/15936857`（Unreliable claims） | `google-unreliable-claims.html` |
| Amazon | `advertising.amazon.com/resources/ad-policy/en`（Stores creative acceptance policies，正文 31,413 字符） | `amazon-stores-creative-acceptance-policies.html` |
| Amazon | `advertising.amazon.com/help/GPSSMTEAA6AEWY3A`（Healthcare products and services，**Updated on Apr 6, 2026**） | `amazon-healthcare-products-services.txt` |
| Amazon | `advertising.amazon.com/help/GFNDKT3FYGDL54VB`（Baby formula and feeding accessories，**Updated on Apr 27, 2026**） | `amazon-baby-formula-feeding.txt` |
| TikTok | `ads.tiktok.com/help/article/<slug>`（Healthcare and Pharmaceuticals = 2026-08 版；Weight Management and Body Image = 2026-09 版；Misleading and false content = 2026-04 版） | `tiktok-*.txt` |

**Meta 自身的一处坏链（值得记录）**：其现行 *Suicide, Self-Injury and Eating Disorders* 页面内的交叉引用指向 `/policies/ad-standards/objectionable-content/personal-health-and-appearance/`，而该地址 **404**。**任何"沿着平台自己的交叉引用走"的规则库都会落到死页上。**

**取证方法（可复用，本次的关键解锁点）**：本机 bash 无直连外网，但存在本地代理 `http://127.0.0.1:7890`。四平台全部正文均以
`curl -sSL --compressed -x http://127.0.0.1:7890 -A "<Chrome UA>" <url>`
取得。两个坑：① `transparency.meta.com` 在缺少完整浏览器头（`sec-ch-ua*` / `Sec-Fetch-*` / `Accept-Language`）时直接返回裸 `Error`（HTTP 400），仅给 User-Agent 不够；② Amazon Ads 帮助中心与 Meta Business Help Center 是 JS 渲染，需无头 Chrome；**循环里用 `chrome --dump-dom` 会在第一页之后挂死，改走 CDP（持久化 headless Chrome over websocket）才稳定**（脚本留在 `_evidence/R5/platforms/_tools/render.py`）。

##### (3) 平台分类体系的两轴结构 —— 规则库 `platform` 维度的分类树应照此建立

Meta 现行的 *Advertising Standards* 是 **两层**结构：4 个顶层桶 × 44 个标准页。**健康类政策在两个桶下同时出现**（`restricted-goods-services` 下的 Health and Wellness，`objectionable-content` 下的 Misinformation / Personal Health and Appearance）。这意味着**"健康类内容"在 Meta 不是一个可枚举的 topic 列表，而是「桶 × 主题」两个轴上的分布**。

> **对规则库的含义**：`platform` 维度若只建一个 `topic: health` 标签，将无法复现 Meta 的**处置升级语义**（同一个内容在"受限商品"桶与"可反感内容"桶下的处置路径不同）。**建议 `platform_policy` 字段同时记录 `bucket` 与 `topic`。**

---

### 8.1 平台政策不是法源，但必须与法源分字段存放

平台政策**不产生法律责任，只产生账号处置**（拒登 / 限流 / 封号）。委托方如果把平台政策与法条混写进 `依据来源`，会导致「风险等级」语义混乱：违反法条 = 法律责任（misbranding、市场措施）；违反平台政策 = 广告跑不出去。

**建议规则库把 `依据来源` 拆成 `legal_basis` 与 `platform_policy` 两个字段**（见 §9.2）。本节只填 `platform_policy`。

### 8.2 Meta —— 三条最直接命中吸奶器的规则

**（1）Meta 明文禁止「仅靠可穿戴产品就能达成效果」的声称。这条直接命中整个可穿戴吸奶器品类。**

**法源（平台）—— Meta Advertising Standards, Health and Wellness（逐字）**

> ### Health and Wellness
> ##### Policy details — CHANGE LOG: Today / Jul 22, 2026 / Dec 26, 2024
> This policy covers two categories of ads: Adult Products and Reproductive Health.
>
> **Health and Wellbeing**
> Ads promoting or marketing dietary, health, or weight loss or weight gain products and services **must be targeted to people at least 18 years or older.**
> Ads promoting or marketing cosmetic products, procedures or surgeries, must be targeted to people at least 18 years or older.
>
> **Guidelines — Ads can't:**
> - Promote weight loss or weight gain products and services, or cosmetic products or procedures that:
>   - Contains statements of inferiority about physical appearance (i.e., terms, descriptions, or questions that are negative and attack an individual's appearance, specific body parts, or hygiene).
> - Promote weight loss or weight gain products or services, that depict:
>   - Close up on specific body area by pinching fat
>   - **Claims that results can be achieved solely by using wearable products**
> - Promote skin whitening or bleaching products that cause permanent skin color change.
> - **Claims (including those from health professionals or health organizations) to cure, heal, or eliminate any of the following incurable diseases and/or terminal illnesses (exhaustive list): Diabetes, Herpes, Thyroid, Psoriasis, Ebola, Cancer, Autism, Alzheimer's, Parkinson's, Amyotrophic Lateral Sclerosis (ALS), Human immunodeficiency virus (HIV)**
>   Note: This does not apply to claims about treating or managing symptoms of these conditions.
> - **Employ clickbait tactics in a health, weight loss, or weight gain context, such as sensational language with exaggerated or extreme claims, or promises of specific outcomes within a set timeframe without disclaimers or qualifiers.**

- URL：https://transparency.meta.com/policies/ad-standards/restricted-goods-services/health-wellness/
- 本地证据：`_evidence/R5/platforms/meta-health-wellness.html` / `.txt`（191 行）
- 变更日志显示本条最近一次变更：**Jul 22, 2026**（即写作前不足两个月）

> **对 Momcozy 的四点含义**：
>
> 1. **`Claims that results can be achieved solely by using wearable products` —— 这是平台层面对可穿戴品类的直接限制。** 可穿戴吸奶器的所有「结果型」声称（奶量提升、效率提升、更快排空）如果被表述为「用了这台可穿戴泵就能达成」，**在 Meta 上属于不可投放内容**。**注意它与法源的关系**：欧盟 UCPD Art. 6(1)(b) 与 FTC HPCG 2022 管的是"有没有证据"；**Meta 这条管的是"能不能把结果归因于穿戴形态本身"** —— 这是一个**平台独有的额外约束，没有法源对应**。这正是"平台维度是否真的需要独立规则族"的实证答案：**需要**。
> 2. **健康类广告必须 18+ 定向**：`Ads promoting or marketing dietary, health, ... products and services must be targeted to people at least 18 years or older`。**委托方需要核对 Meta 投放的年龄定向设置**（注意：若只针对哺乳期母亲，18+ 一般自然满足，但这是硬性配置要求，不是结果）。本次调研**未接触委托方的 Meta 广告后台，因此未核实实际定向配置**（见 §12 G15）。
> 3. **`cure, heal, or eliminate` 的疾病清单是穷举式（exhaustive list），且不含乳腺炎（mastitis）。** 但注意清单前有 "incurable diseases and/or terminal illnesses" 限定，且 Meta 明确说 "This does not apply to claims about treating or managing symptoms"。**因此不能从这条推出"Meta 允许说治疗乳腺炎"** —— 乳腺炎不在清单里是因为它可治愈，而"治疗疾病"的声称受**法源**（21 CFR 801.4 / MDR Art. 7 / UCPD Annex I §17）而非这条平台政策约束。
> 4. **`promises of specific outcomes within a set timeframe without disclaimers or qualifiers`** —— 这条正面命中委托方的 M03 家族（`28.2% faster`、`~70% Reported Earlier Let-Down`）。**注意平台给了一条出路：加 disclaimers or qualifiers 就可以。** 这与法源口径不同 —— FTC 要求的是"证据层级"，Meta 要求的是"有免责/限定语"。**两个口径都存在，规则库需要区分"为过审而加的限定语"与"为合规而备的证据"。**

> **⚠️ 政策名与措辞的一处更新（2026-09-15 核验）**：
> 1. **Meta 已不存在名为 "Personal health" 的独立广告标准**（四个语区全部 404）。其覆盖面现拆入 *Health and Wellness*（`restricted-goods-services/health-wellness/`）下的 `Adult Products and Reproductive Health` 小节 —— 即上引同一页。**引用时不要写 "Meta Personal health policy"，那是本次调研早期笔记里的旧名。**
> 2. **Meta 现行正文已不再使用 "negative body image" 这个说法。** 现行对应句在 *Advertising Standards: Introduction* → `PROMOTING POSITIVE USER EXPERIENCES`（逐字）：
>
> > We also prohibit other objectionable material, such as **content implying or attempting to generate negative self-perception in order to promote diet, weight loss or other health related products**.
>
> 而 *Health and Wellness* 页内的对应表述是（逐字）：`statements of inferiority about physical appearance (i.e., terms, descriptions, or questions that are negative and attack an individual's appearance, specific body parts, or hygiene)`。
> **规则库若沿用 "negative body image" 作为关键词，会在 Meta 现行正文上零命中**；而新表述比旧短语**更宽**（`or other health related products`）。Google 侧对应词是 `Body shaming` / `Negativity related to physical attributes or social interactions`（见 §8.3、§8.7 F）。

**（2）Meta 的 Personal Attributes 政策禁止暗示受众的个人健康属性。**

**法源（平台）—— Meta Advertising Standards, Privacy Violations and Personal Attributes（逐字）**

> Ads must not contain content that shares or asks for private information about users. In addition, **ads must not contain content that asserts or implies personal attributes.** This includes direct or indirect assertions or implications about a person's race, ethnicity, religion, beliefs, age, sexual orientation or practices, gender identity, disability, **physical or mental health (including medical conditions)**, vulnerable financial status, voting status, membership in a trade union, criminal record, or name.
>
> Ads can't:
> - Share or ask for personal attributes of a user or user's family
> - **Imply that the advertiser is aware of someone's personal attributes or the personal attributes of their family**
> - …
> - **Imply knowledge of Medical information of a user or user's family**

- URL：https://transparency.meta.com/policies/ad-standards/privacy-violations/personal-attributes/
- 本地证据：`_evidence/R5/platforms/meta-privacy-violations-personal-attributes.txt`
- 变更日志最近一次变更：**Jun 26, 2024**

> **这条是本次调研发现的、对委托方最实用的平台规则。** 它把 U04（`sore nipples` / `clogged ducts` / `painful pumping` 等痛点场景化名词）的风险**从"语境判断"变成了一条明确禁令**：广告文案说「你有堵奶吗？」「哺乳期乳头疼痛？」等于**暗示广告主知道受众的医疗状况**，在 Meta 上属于违规。
>
> **这给 U04 提供了一个可执行的改写规则**：把**第二人称的痛点提问**改为**第三人称的产品功能陈述**。
> - ❌ 违规（暗示个人健康属性）：`Sore nipples? Momcozy can help.` / `Struggling with clogged ducts?`
> - ✅ 可能合规（产品功能陈述）：`Designed for a gentler pumping experience` / `Soft silicone flange for more comfort`
>
> **注意这与法源的差别**：UCPD Art. 7 与 FTC Deception Policy 管的是"误导"；**Meta 这条管的是"提到了受众的个人属性"，即使内容完全真实也违规。** 又是一条"只有平台维度才有"的规则。

**（3）Meta 的 Misinformation 政策**

> Meta prohibits ads that include content debunked by third-party fact checkers. Advertisers that repeatedly post information deemed to be false may have restrictions placed on their ability to advertise across Meta technologies.
> Guidelines: In addition to the requirements in our Community Standard on Misinformation, **Ads cannot contain content debunked by third-party fact checkers.**

- URL：https://transparency.meta.com/policies/ad-standards/unacceptable-content/misinformation/
- 本地证据：`_evidence/R5/platforms/meta-unacceptable-content-misinformation.txt`

> 这条对健康类内容的实际约束强于法源：**即使 FTC 层面尚未认定虚假，只要被第三方事实核查机构 debunk，Meta 就可以处置。** 这意味着规则库需要监控的不只是法规，还包括事实核查机构的公开结论。

### 8.3 Google Ads —— 两条最直接命中的规则

**（1）Google「Unreliable claims」——健康类功效声称**

**法源（平台）—— Google Ads Policy, Misrepresentation → Unreliable claims（逐字）**

> **Unreliable claims**
> Ads or destinations that exclude relevant product information or provide misleading information about products, services, and businesses can deceive users and compromise user trust in the Google Ads platform. The Misrepresentation policy strives to ensure that ads are clear, honest, and provide information that users need to make informed decisions.
>
> **Making inaccurate claims or claims that entice the user with an improbable result (even if this result is possible) as the likely outcome a user can expect is not allowed.**
>
> **Claims related to health and weight loss**
> - Making unproven claims of cures for incurable medical ailments
>
> **Google Ads may defer to local regulatory guidelines for health-related claims, including testimonial content, when enforcing this policy.**
>
> Examples (non-exhaustive): "Miracle cures" for medical ailments such as arthritis, diabetes, Alzheimer's disease, …

- URL：https://support.google.com/adspolicy/answer/15936857（Parent: Misrepresentation → https://support.google.com/adspolicy/answer/6020955）
- 本地证据：`_evidence/R5/platforms/google-unreliable-claims.html`
- 注意：该页明确 *"Violations of this policy won't lead to immediate account suspension without prior warning. A warning will be issued at least 7 days prior to any suspension of your account."* —— **Google 对这条政策有 7 天预警机制**，与 Meta 的即时处置不同。

> **「Google Ads may defer to local regulatory guidelines for health-related claims」是一句被低估的话。** 它意味着 **Google 在健康类声称上会把当地监管标准当作执法依据** —— 也就是说，Momcozy 在法国/英国/西班牙的 Google 广告，如果违反了当地的健康声称规则，**平台侧也可能据此拒登**。**这是"平台维度"与"国家维度"耦合的直接证据：平台政策本身会把国家法条引用进来。**
>
> **这也回答了委托方"国家 × 品类 × 平台 × 内容类型对不对"的问题**：四个乘数不是独立的。**Google 的这条政策使 `平台 × 国家` 成为一个联合维度**，而不是两个可分离的轴。

**（2）Google「Healthcare and medicines」—— 需要认证的品类**

> Google Ads is dedicated to following advertising regulations for healthcare and medicine, so ads and destinations are expected to follow appropriate laws and industry standards. **Some types of healthcare-related content can't be advertised at all, while others can only be advertised in certain locations by advertisers who have applied and been approved to advertise those products or services using Google Ads.**
> For most healthcare policies, if your ad campaign targets allowed locations and **the domain is properly certified**, your ad will be labeled "**Eligible (limited)**" and can run in allowed locations.
> … Advertisers must also be **certified with Google**. Learn more about how to Apply for healthcare certification.

- URL：https://support.google.com/adspolicy/answer/176031
- 本地证据：`_evidence/R5/platforms/google-healthcare-and-medicines.html`（43,243 字符，含分国家/地区的要求矩阵）

> ⚠️ **本次未能从该页中提取到针对 "medical device" 的专门条款**（页面以在线药房、远程医疗、处方药、成瘾服务等品类为主，按国家/地区列出要求矩阵）。**吸奶器是否需要在 Google 侧申请医疗健康认证，本次未核实**（见 §12 G16）。**这是一个需要由委托方直接向 Google 代表确认的操作问题**，而不是可以通过读政策解决的问题。

### 8.4 Amazon —— Seller Central 侧为登录墙，但 **Ads 侧取得正文**，且含一条可直接解决 H08/M06 的条款

#### (1) 取证状态：两条路径，一条通一条堵

| 路径 | 结果 | 说明 |
|---|---|---|
| **Seller Central 帮助页**（`sellercentral.amazon.com/help/hub/reference/external/G…`） | **未取得（登录墙）** | `_evidence/R5/platforms/amazon-*.html` 7 个文件（`amazon-medical-devices`、`amazon-conditional-products`、`amazon-product-detail-page-rules`、`amazon-advertising-policies`、`amazon-aplus-content`、`amazon-restricted-products`、`amazon-health-personal-care`）**均只渲染出约 1,894 字符骨架**，标题统一为 `Amazon`，正文实为语言选择器。→ 产品详情页规则（title / bullet / A+）**本次未取得** |
| **Amazon Ads 公开政策**（`advertising.amazon.com/resources/ad-policy/<slug>`） | **已取得** | `amazon-stores-creative-acceptance-policies.html`（324,168 字符，正文 31,413 字符）为服务端渲染，标题 *Stores creative acceptance policies*。`/ad-policy` 与 `/prohibited-content` 两个短路径返回 **404**，须用**完整 slug** |

#### (2) 硬发现：**Amazon 明文禁止「与竞品直接对比」**

**来源**：*Stores creative acceptance policies* §2.4 Claims and comparative statements，`_evidence/R5/platforms/amazon-stores-creative-acceptance-policies.html`。

> ### 2.4 Claims and comparative statements
>
> Advertising claims in your Stores must be truthful and accurate.
>
> You must have evidence in support of your advertising claims:
>
> - If you make a claim about your brand in your Store, that claim must be substantiated **within the Store, with the date and evidence** to support that claim.
> - If you make a claim about your products, it must be clear which products this applies to and those products should be placed **adjacent to the claim within the Store**. **Substantiation must be discoverable on the product detail page or the product packaging** of the associated products.
>
> …
>
> **Comparative: Must be supported with a citation of an independent source and dated within the previous 12-18 months.** For example, "America's best hat, Hat Makers magazine, 2017." **We do not permit direct comparison to competitor brands.**

**这条同时解决规则库里的两条规则**：

| 规则 | 原法源状态 | Amazon 政策给出的补充 |
|---|---|---|
| **H08**（`better than Medela` 类对比） | 法源可查（21 CFR 801.6 + UCPD Art. 6(2)(a)） | **平台层直接禁止**：`We do not permit direct comparison to competitor brands.` —— 不需要再论证"是否误导"，指名对比在 Amazon 上根本不接受 |
| **M06**（无据模糊对比） | 与 H08 重叠，曾建议合并 | 提供了**可自动执行的判据**：要对比就必须 `citation of an independent source` **且** `dated within the previous 12-18 months` —— 这是 §9.3 需要的"可核查形式要件"，可直接写进规则 |

#### (3) 对 Momcozy `28.2%` 的直接影响（见 §7.8）

§2.4 要求 `Quantified performance` 类声称（原文示例：`"Reduces 99% of wrinkles"`、`"Teeth appear three shades whiter"`、`"the best moisturizer."`）的**证据必须能在「产品详情页或产品包装」上被找到**，且品牌级声称必须**在 Store 内**带**日期与证据**。

**这意味着 §7.8 记录的 `28.2%` 问题在 Amazon 上比在官网上更严重**：官网只需满足"有证据"（FTC 口径），而 **Amazon 额外要求证据与日期就放在声称旁边或产品详情页上，可被消费者发现**。同一页上 `28.2% faster` 与 `28.2% more milk output` 两种量纲并存（§7.8），本身就构成 `must be truthful and accurate` 下的自相矛盾。

#### (4) 国别条款：**澳大利亚禁止在 Amazon 上作疾病/不适相关声称**（与 §7.6 的风险叠加）

同页 *Locale-specific requirements — Australia*（逐字）：

> Products must not make **therapeutic or health claims related to a disease, ailment, physical condition or discomfort**, defect, injury, or psychological condition.
>
> Supplements, foods, creams, and other consumable or topical products cannot claim to assist with or have an impact on weight loss, slimming, or dieting.

**对规则库的含义**：`sore nipples` / `clogged ducts` / `painful pumping`（**U04**）在澳大利亚站属于 `physical condition or discomfort` —— 与 Meta 的 Personal Attributes 禁令（§8.2(2)）**方向一致但依据不同**：Meta 禁的是"暗示知道受众的健康状况"，Amazon 澳大利亚禁的是"对产品作不适相关声称"。**两个平台、两条不同理由、同一个结论** —— 这是 U04 应当升级为高风险规则的第二个独立依据。另注：现有 291 条广告的投放地区**不含澳大利亚**（任务书 §二.D），故此项属前瞻性约束。

#### (5) 仍然成立的那条间接发现（来自 §7.7）

**Momcozy 的 Amazon listing 使用了品牌自控的结构化属性字段**（`Product Style: hospital grade`），且该字段与官网的否认声明矛盾。

> **Amazon 侧的风险点是双重的**：既是"**政策写了什么**"（§8.4(2) 的对比禁令、§8.4(3) 的证据就地要求），也是"**品牌自己填了什么字段**"。结构化属性（`Product Style`、`Material Type Free`、`Special Feature` 等）是**可直接被消费者看到的、品牌自己声明的产品事实**，落入 Amazon §2.4 的 `advertising claims` 与 UCPD Art. 6(1)(b) 的 "specification"。**委托方应当把 Amazon listing 的结构化属性纳入内容审查范围。**

#### (6) 本项的核心补充：**Amazon 明文把 Breast Pump 列入「Category 1（低敏感度）：一般允许」**

这是 Amazon 侧最有价值的一条**品类资格**事实，也是本次补充取证（64 页平台政策）中最直接可用的一条。

**来源**：*Healthcare products and services*（`https://advertising.amazon.com/help/GPSSMTEAA6AEWY3A`，页面自标 **Updated on Apr 6, 2026**），消费者保健产品敏感度分级表，`_evidence/R5/platforms/amazon-healthcare-products-services.txt`。

> - **Category 1 (low sensitivity products): Generally allowed**
>   Allergy and Sinus, Splints and Supports, **Breast Pump**, Cough and Cold, COVID Test Kits, Digestion, Eczema, Eye health, Foot Remedies, General Stress, General Wellness Health Tests or Monitors, Menopause, Menstruation Products, Physical Therapy Aids, Pain Relievers, Rosacea, Sleep or snoring Aids, and others.

（同页另有 **Category 2 (medium sensitivity products): Allowed with restrictions** 与 **Category 3 (high sensitivity products): Allowed with additional restrictions**；`Weight Loss` 在 Category 2，`Family Planning and Reproductive Health` 在 Category 3。**吸奶器不在其中任何一档，而在 Category 1。**）

> **含义（这一条改变了 Amazon 侧的风险定位）**：
>
> 1. **Amazon 的风险不在"品类能不能投"，而在"文案怎么写"。** 吸奶器是 Amazon 明文点名的低敏感度品类，**投放资格本身不是问题**。§8.4(1) 记录的"Seller Central 是登录墙"因此**不构成对本品类的实质证据缺口** —— 品类资格这一关键问题已由 Ads 侧公开政策直接回答。
> 2. **但资格宽松 ≠ 声称宽松。** 同页 `Health claims and comparative statements`（逐字）：`Advertisers must accurately represent their products. This includes ensuring that all implicit and explicit claims made in the ad copy, audio, or visuals are accurate, truthful, not misleading, and, when appropriate, backed by scientific evidence.` 再叠加 §8.4(2) 的对比禁令与 §8.4(3) 的"证据须就地可发现"要求 —— **Amazon 的严格度落在声称层，是全平台里对"clinically proven"最硬的一家**（见 §8.7 B）。
> 3. **有一条 Amazon 专属的旁证约束**：Amazon 另发布 *Baby formula and feeding accessories*（`advertising.amazon.com/help/GFNDKT3FYGDL54VB`，**Updated on Apr 27, 2026**）：`Ad content must not discourage breastfeeding or encourage formula use as a substitution for breastfeeding`，且该类目在 Homepage 与 Fire Devices 上全球禁止。**吸奶器文案在涉及"喂养方式"表述时，不应踩入"替代母乳喂养"的语义场** —— 这与品类的公共卫生语境有关，与产品功效无关，容易漏检。

**【本页的一处诚实标注】** 该分级表第三列（逐档的 supply 专属限制正文）在 DOM 中渲染为**空单元格**，故 `Permitted on all supply with the following restrictions:` 之后**未见正文**。该列内容**本次未取得**，已登记为 **G21**。

### 8.5 TikTok —— 已取得正文（15 页），且命中一条**平台专属**的硬约束

**取证方式（可复用）**：`ads.tiktok.com/i18n/help/article/...` 是 JS SPA，只返回空壳；服务端渲染的 **Business Resource Center**（`https://ads.tiktok.com/help/article/<slug>`）返回完整政策 HTML。已取得 15 页正文，全部抓取日 **2026-09-15**，本地路径 `_evidence/R5/platforms/tiktok-*.txt`（合计 198,080 字符）。

#### (1) 对比性素材：**全球口径是"附条件允许"，不是禁止** —— 与规则库的直觉相反

**来源**：TikTok Advertising Policies, *Misleading and false content*（Last updated: **April 2026**），章节 **"Malicious, Subjective and Before-and-after Comparisons"**，`_evidence/R5/platforms/tiktok-misleading-and-false-content.txt:75-84`。

> **Comparative claims may be allowed, subjected to the provision of evidence or clear disclaimer(s).**
>
> We do not allow ad content and landing pages to include:
>
> - **Product effect comparisons, such as before-and-after results, which may cause viewers to have a false or distorted impression about a product's outcome/results;**
> - Malicious claims and comparisons which (i) accuse or associate a targeted brand and its product(s) of any serious violations and/or (ii) insult or mock users of any targeted brand or its products, which may provoke anxiety, fear, worry or distress among users; and
> - Subjective/value-based claims and comparisons that make negative judgements about a targeted brand's (including its products) core attributes, such as price/cost, features, functionality, quality etc.

**对规则库的含义（重要）**：TikTok 的判据不是"是否使用前后对比"，而是 **(a) 是否提供证据或清晰免责声明 + (b) 是否会让受众对产品结果产生错误或扭曲印象**。因此一条简单的 `before/after → 禁止` 规则**在 TikTok 上是过严的**，会漏掉真正的合规路径（加免责 + 有数据）。但注意第 2 项与 **H08（贬低竞品）**、**M06（模糊对比）** 直接对应，且 TikTok 把"贬低"细化为两种可检测形态：**指控对方违规**、**嘲讽对方用户**。

#### (2) 但**特定市场**对医疗器械一刀切禁止前后对比 —— 这是 `平台 × 国家` 联合键的又一实证

**来源**：同上政策文件的 *Healthcare and Pharmaceuticals*（Last updated: **August 2026**）Market-specific requirements 表，`_evidence/R5/platforms/tiktok-healthcare-pharmaceuticals.txt:351`、`:1737`、`:2255`、`:2878`。

> - Before-and-after comparisons for over-the-counter medicines, **medical devices**, and food supplements

该条以"Examples of what is not allowed"出现在 **France**、**Lebanon**、**Qatar / South Africa / United Arab Emirates**、**Turkey** 四张国别表中（共 4 处命中，**不含美国**）。

**对规则库的含义**：吸奶器在**美国是 Class II 医疗器械**（§4.1），在英国**通常不算医疗器械**（§4.2）。于是同一张"前后奶量对比图"在 **TikTok** 上的判定取决于投放国：美国站不落入该条（但落入 §8.5(1) 的"错误印象"判据），法国站则直接命中"medical devices"一刀切。**这是目前找到的、最干净的一个证明「platform × country 是不可分离的联合键」的例子** —— 它比 §8.3(4) 的 Google 例子更硬，因为这里的分歧发生在**同一个平台内部**。

#### (3) 医疗器械广告的年龄门槛：TikTok 美国站要求 18+

**来源**：`_evidence/R5/platforms/tiktok-healthcare-pharmaceuticals.txt`（United States 表，`:2940` 起）。

> | Medical devices |
> | May be allowed if the following requirements are met:
> - Comply with local laws and regulations
> - Certifications from appropriate local regional regulating authorities may be required
> - **Restrict the ads to audiences aged 18 years or older** |

其他市场（如 Australia、阿根廷等组）对 medical devices 也普遍要求"提供当地监管机构批准证明 + 18+"。**对 Momcozy 的含义**：吸奶器的目标受众包含未成年父母，TikTok 美国站的 18+ 定向限制是硬性的投放约束，而不是文案问题。另注：现有 291 条在跑广告分布为 **Google 262 / Meta 27**（任务书 §二.D），**TikTok 目前不是投放渠道**，此项属前瞻性约束。

#### (4) 功效声称的三条平台专属禁区（无对应法条）

| TikTok 禁项（逐字） | 出处 | 对应规则 |
|---|---|---|
| `Claims of cures for incurable diseases` | *Misleading and false content*（2026-04），`tiktok-misleading-and-false-content.txt:29` | **H01** |
| `Showing wrinkles disappearing by using a cream through before-and-after comparisons` | 同上 `:30` | 前后对比的**示例化**判据（本项为示例，非独立禁令） |
| `do not allow ad content to feature absolute terms about a product in relation to time, region, or brand` | 同上 `:20` | **H05**（`safest`/`100% safe`）、**M01**（`the quietest`）、**M03**（`bestseller`） |
| `Suggestions or claims that the product or service is a "miracle" or "holds the secret or cure"` | *Healthcare and Pharmaceuticals*，`tiktok-healthcare-pharmaceuticals.txt:349` | **H01** —— ⚠️ **注意：Meta 已无 `miracle cures` 字面表述（见 §8.2 说明），但 TikTok 仍有**，"miracle"一词在 TikTok 上仍可直接命中 |
| `Claims that the product alone, without diet or exercise, can lead to weight loss or muscle gain` / `Suggestions that losing weight or gaining muscles is easy or guaranteed` | *Weight Management and Body Image*（Last updated: **September 2026**），`tiktok-weight-management.txt` | 品类不同（体重管理），但**句式结构与 `more milk` 同类**："单独使用产品即可达成结果"是平台通用的判险模式 |

**关于 TikTok `absolute terms` 这一条**：它把"绝对化用语"的判据锚定为**时间/地域/品牌三个维度**，这比中国《广告法》第九条的"国家级/最高级/最佳"更宽（覆盖 `Number 1 song on TikTok` 这类**平台内排名**表述）。若规则库要设计 `absolute_terms` 检测器，TikTok 的三维口径比中文品类的常见词表更可操作。

#### (5) 未能取得的 TikTok 页面

`_evidence/R5/platforms/tiktok-ad-review-checklist-ad-messaging.txt`（284 字符）、`tiktok-creative-best-practices.txt`（266 字符）、`tiktok-market-specific-requirements-for-ad-approval.txt`（308 字符）三页为骨架，**未取得正文**；`tiktok-ad-serving-policy.txt`（2024-10）为旧版，未见与本品类相关的条款。

### 8.6 本节的落地结论

| # | 结论 | 依据 | 对规则库的动作 |
|---|---|---|---|
| 1 | **平台把健康类广告作为受限品类单独管辖**（Meta 有独立的 "Health and Wellness"、"Personal Attributes"、"Misinformation" 章节；Google 有 "Healthcare and medicines" 与 "Unreliable claims"；TikTok 有 "Healthcare and Pharmaceuticals" 与 "Weight Management and Body Image"） | §8.2、§8.3、§8.5(3)(4) | `platform` 维度**需要**独立的规则族，不能与法条混写 |
| 2 | **Meta 禁止「仅靠可穿戴产品达成效果」的声称** —— 可穿戴品类的平台专属约束，无法源对应 | §8.2(1) | 新增平台规则：`wearable + 结果型声称` 组合判险 |
| 3 | **Meta 禁止暗示受众的个人健康属性** —— 把 U04 从"语境判断"变成明确禁令 | §8.2(2) | U04 增加改写规则：第二人称痛点提问 → 第三人称产品功能陈述 |
| 4 | **Google 的 Unreliable claims 政策会引用当地法规** —— `平台 × 国家` 是联合维度，不是可分离的两个轴 | §8.3(1)、**§8.5(2)** | 规则引擎的匹配键需要支持 `platform+country` 联合键。**TikTok 同平台内部的国别分歧（法国禁 / 美国不禁前后对比）是这一结论最硬的证据** |
| 5 | **Amazon 侧的真实风险点是品牌自填的结构化属性**，不是平台政策 | §7.7、§8.4 | 把亚马逊 listing 的结构化属性纳入审查范围 |
| 6 | **同一类素材的合规路径因平台而异**：TikTok 对对比性素材是"**附证据或免责声明**即可"，而 Momcozy 现行 21 条规则**没有承载免责声明的字段** | §8.5(1) | 规则 schema 需增加 `可豁免条件` 与 `免责声明要求` 两个字段（现有 schema 只有 `豁免词`，是词级而非句级/素材级） |
| 7 | **Amazon 明文禁止「与竞品直接对比」（`We do not permit direct comparison to competitor brands.`），并要求对比声称引用独立来源且**距今 12–18 个月内**；量化性能声称的证据必须能在**产品详情页或产品包装**上被发现** | **§8.4(2)(3)** | **H08 在 Amazon 上不需要论证「是否误导」，指名对比本身不被接受**；**M06 获得一条可自动执行的判据**（引用独立来源 + 时效 ≤12–18 个月）；`28.2%` 类声称在 Amazon 上比在官网**多一层**「证据就地可发现」要求 |
| 8 | **Amazon 明文把 `Breast Pump` 列入 Category 1（低敏感度：Generally allowed）**，但同一页要求 `all implicit and explicit claims … are accurate, truthful, not misleading, and, when appropriate, backed by scientific evidence` | **§8.4(6)** | **Amazon 侧的风险定位改为"文案层"**：品类投放资格不是问题，**声称**才是问题。§8.4(1) 的"Seller Central 登录墙"**不再构成本品类的实质证据缺口**（已转记 G21 为细节性缺口） |
| 9 | **`before/after` 不能做成一个布尔字段** —— TikTok（产品效果对比）与 Amazon（体重管理）**禁止**；Meta **有条件允许**（美容类 18+，且"与产品或服务无关"的才禁）；Google **不作为素材规则**，只经 *Unreliable claims* 与 *Imposing negativity* 间接命中 | **§8.7 E** | `before_after` 必须建为 **`平台 × 有无证据或免责 × 是否与产品相关` 的条件字段**。**单一 `before_after: banned` 会在四个平台里至少错两个** |
| 10 | **Google 的处置严重度分散在子政策里**，同一条健康声称违规因触发不同子政策而落入不同等级：*Unacceptable business practices / Unauthorized pharmacies* = `suspended upon detection and without prior warning`；*Unreliable claims / Editorial* = `A warning will be issued at least 7 days prior to any suspension`（该句已在 `google-unreliable-claims.txt:64` 逐字复核） | **§8.7 F** | **严重度不是 topic 的属性，是"topic × 命中的子政策"的属性**。`severity` 字段必须与**具体子政策**绑定，不能只挂在主题上 |
| 11 | **Meta 与 Google 现行正文都已不再使用旧措辞**（Meta 无 "negative body image"、无 "Personal health" 标准；Google 的 answer ID 已被复用） | **§8.0、§8.2、§8.7 A** | **规则库的 `platform_policy` 字段必须记录"引用日 + 页面变更日"**；Meta *Health and Wellness* 的正文变更日是 **Jul 22, 2026**，距今不足两个月 —— 平台政策的**保质期短于法条**，需要单独的复核节奏 |

---

### 8.7 四个平台的「反射句」—— 按委托方三条待测声称逐条对照

本节把 §8.2–§8.5 的正文压成**一张可直接写进规则库的对照表**：对委托方的三条关键声称，**每个平台最短、最可辩护的那一句引文**是什么。用途是让规则库的 `platform_policy` 字段**每格填一句可引用的原文**，而不是填一个政策页 URL。

> 证据：`_evidence/R5/FINDINGS-platform-policies.md` CROSS-PLATFORM SYNTHESIS（含各句在分项报告中的 §编号，可逐句回溯到本地 HTML/TXT）。

#### A. `more milk`（对身体功能的功效/结果声称）

| 平台 | 起作用的逐字句 | 性质 |
|---|---|---|
| **Meta** | `Contain any claims that expressly state or imply that the featured products can treat, cure, prevent, mitigate or diagnose a disease or medical condition in humans or animals.` | 疾病声称禁令 |
| **Meta**（受众框架） | `Ads must not contain content that asserts or implies personal attributes. This includes … physical or mental health (including medical conditions) …` + `Imply knowledge of Medical information of a user or user's family` | **暗示受众健康属性**（与内容真假无关，真实也违规） |
| **Meta**（时间框架） | `promises of specific outcomes within a set timeframe without disclaimers or qualifiers` | **给了出路**：加免责/限定语 |
| **Google** | `Making inaccurate claims or claims that entice the user with an improbable result (even if this result is possible) as the likely outcome a user can expect is not allowed.` | 不可靠声称 |
| **Google**（量化声称） | `Testimonials that claim specific results must include a visible disclaimer stating that there is no guarantee of specific results and that the results can vary.` | 须配可见免责声明 |
| **Amazon** | `all implicit and explicit claims made in the ad copy, audio, or visuals are accurate, truthful, not misleading, and, when appropriate, backed by scientific evidence.` | 举证责任 |
| **Amazon**（最硬） | `Make unrealistic or unrelated claims as to the efficacy of the product.` | **明文禁止** |
| **TikTok** | `Ad content and landing pages must not promise or exaggerate results concerning a product's effect.` | 禁止夸大结果 |

#### B. `clinically proven`

| 平台 | 起作用的逐字句 | 性质 |
|---|---|---|
| **Amazon**（最干净的一击） | **`Regulatory endorsement claims on healthcare products.`** | **四平台中对本品类最直接的一条禁令** |
| **Amazon** | `Non-prescription health and beauty products cannot claim to be as effective as prescription products.` | 禁止与处方等效 |
| **Amazon**（量化判据） | `Quantified performance: Claims which imply to the customer that some objective measurement has taken place.` | 触发**带日期的**举证义务 |
| **Google** | `Products that imply they're as effective as prescription drugs or controlled substances` | 禁止与处方等效 |
| **Google** | `Making unproven claims of cures for incurable medical ailments` + 示例 `"Miracle cures"` | 不可靠声称 |
| **Meta** | 同上疾病声称禁令 | 疾病声称禁令 |
| **TikTok** | `Promotion of unproven, unsafe, or experimental substances or practices as medical treatments` + `do not allow ad content to feature absolute terms about a product in relation to time, region, or brand` | 未证实治疗 + 绝对化用语 |

#### C. `FDA approved`

| 平台 | 起作用的逐字句 | 性质 |
|---|---|---|
| **Amazon** | **`Regulatory endorsement claims on healthcare products.`** | **在所有广告中一律禁止** |
| **Google** | `Non-government approved products that are marketed in a way that implies that they're safe or effective for use in preventing, curing, or treating a particular disease or ailment` | 禁止非政府批准产品的疾病效能暗示 |
| **Google**（唯一例外） | `United States: Advertisers may promote HIV home tests that are FDA approved.` | **例外极窄，与吸奶器无关** |
| **Meta** | 疾病声称禁令 + *Misinformation*（`Ads cannot contain content debunked by third-party fact checkers.`） | 疾病声称 + 事实核查 |
| **TikTok**（澳大利亚） | `Not contain any representation that the goods are safe, do not cause harm or side-effects, are a guaranteed cure, or are infallible, unfailing, magical, or miraculous;` | 绝对化 + 安全性声称 |

> **⚠️ 一条重要的否定性发现**：**Google 没有医疗器械认证项目。** 其健康类认证门槛只覆盖**药房 / 远程医疗 / 药品生产商 / 成瘾服务 / 堕胎服务 / 保险**六类，**不含 medical device**。因此"吸奶器在 Google 上是否需要认证"**不能从政策文本推断**（见 §12 G16）—— **不能因为找不到器械认证项目，就推断吸奶器不受 Google 医疗政策约束**：§8.7 C 行第二句（`Non-government approved products…`）在 *Unapproved substances* 之下**依然适用**。这两件事必须分开陈述。

#### D. `same as Medela`（竞品品牌指代）—— 规则 H08 / M06 的直接补强

| 平台 | 起作用的逐字句 | 性质 |
|---|---|---|
| **Amazon**（最干净） | **`We do not permit direct comparison to competitor brands.`** | **明文禁止，不需要论证是否误导** |
| **Amazon** | `Not denigrate another company or product, for example, "better made than [company/brand/named product]," nor leverage another company name or product to promote other products.` | 禁止贬低 + 禁止借名 |
| **TikTok** | `We do not allow the use of third-party brands without authorization.` | 未经授权不得使用第三方品牌 |
| **Google** | `Make it seem like you're supported by another brand, organization or government entity when you're not` / `Impersonating other brands or businesses in your ads or on your website…` | 冒充与虚假背书 |
| **Meta** | `Ads may not contain content that violates the intellectual property rights of any third party…` —— **但 Meta 自陈在没有权利人举报时"cannot know with certainty whether an ad infringes"** | **只在 Medela 投诉后才被动执行** |

> **含义**：**H08 与 M06 在四个平台上的"最省力落点"是 Amazon**。Amazon 的禁令是**形式化的**（指名对比本身不被接受，无需证明误导），而 Meta 的执行是**被动的**（等 Medela 来投诉）。**这不是把 H08 降级，而是说明"平台侧的风险不是均匀分布的"——同一句话在 Amazon 上是硬违规，在 Meta 上是待投诉。** 规则库若给 H08 一个跨平台统一的平台风险分，会同时高估 Meta 侧、低估 Amazon 侧。

---

## 九、对 Momcozy 的直接含义

### 9.1 品类维度的本质：**一张法规映射表，不是一堆经验**

**逐条标注 H01–H09、M01–M07、U01–U04 的法源状态。**

判定口径：
- **法源可查** = 能找到具体的成文条款号（CFR / 条例 / 指令），该条款**直接**约束这条规则描述的行为；
- **准法源** = 无直接条款，但有官方指南、执法政策声明或判例可引，构成可论证的判定标准；
- **经验判断** = 无外部来源，判定理由只能来自内部反馈或品类惯例。

| 规则 | 边界内容（摘要） | 法源状态 | 具体法源 |
|---|---|---|---|
| **H01** | 医疗功效声明（treat/cure/diagnose/疏通堵奶/治疗或预防乳腺炎） | **法源可查** | **21 CFR 801.4**（intended use 由 labeling claims 与 advertising matter 确定）+ **21 CFR 807.81(a)(3)(ii)**（major change in intended use 需新 510(k)）+ **FDA General/Specific Intended Use 指南**（疾病实体/临床结果属 specificity level 4–5 = new intended use）+ **EU MDR Art. 7(a)(b)(d)** + **UCPD Annex I §17**（falsely claiming a product can cure illnesses） |
| **H02** | 催乳/增产/奶量产出承诺（more milk、催产素、长期奶量、排空功效） | **准法源（且当前口径过严）** | **FTC HPCG 2022 p.13**（health-related benefits 需 RCT）+ **FTC 1984 Substantiation Policy**。**注意：法源不禁止"说"，只要求"有证据"。** 竞品实证：Medela 带 NCT 号在用（见 §7.2 卖点 A） |
| **H03** | 临床背书（clinically proven / clinically tested / clinical studies show） | **法源可查** | **FTC HPCG 2022 §1「Ads that refer to a specific level of support」**（"must have at least the level of support that they claim to have"）+ **Example 18**（clinically tested 本身即功效声称）+ **FTC 1984 Substantiation Policy**（"tests prove" / "studies show" 属 express substantiation claim）+ **UCPD Art. 6(1)(b)**（results and material features of tests） |
| **H04** | 无据的医生/专家推荐背书（doctor recommended / pediatrician recommended） | **法源可查** | **FTC 1984 Substantiation Policy**（逐字将 "doctors recommend" 列为 express substantiation claim）+ **EU Reg 1924/2006 Art. 12(c)**（claims which make reference to recommendations of individual doctors or health professionals **一律禁止**，注意 Art. 11 的机构级例外） |
| **H05** | 虚假安全承诺（safest / 100% safe / fits all breast shapes / universal fit） | **准法源** | **FTC Deception Policy 1983**（可被证伪的绝对声称 + materiality）+ **UCPD Art. 6(1)(b)**（main characteristics）+ **UCPD Annex I §9**（impression a product can legally be sold when it cannot）。**无专门成文条款**，属"绝对声称需 substantiation"的一般原则。⚠️ H05 内部口径冲突：说明里写"排名最高级已放开" |
| **H06** | FDA 表述错误（FDA approved / certified） | **法源可查（最强）** | **21 CFR 807.97**（明文："constitutes misbranding"）+ **FDA 官方消费者页面**（"FDA Registered"/"FDA Certified"/"FDA Registration Certificate" 均为误导；"FDA does not issue any type of device registration certificates"）+ **21 CFR 807.22(b)(1)**（年度注册机制）+ **UCPD Annex I §4**（per se unfair） |
| **H07** | 疼痛功效承诺（pain-free / no pain / pain relief / less pain） | **准法源** | **FTC Deception Policy 1983 脚注 42**（subjective claim vs affirmative claim 的分界 —— `less pain` 属 affirmative）+ **FTC HPCG 2022 p.13**（客观声称需 RCT）。**无专门条款。** ⚠️ **与安全词表直接矛盾**（安全词含 `reduces pain`/`less pain`） |
| **H08** | 无数据支撑的违法对比 / 贬低竞品（10x better / better than Medela） | **法源可查** | **21 CFR 801.6**（医疗器械专条：false or misleading representation with respect to another device 构成 misbranding）+ **UCPD Art. 6(2)(a)**（comparative advertising creating confusion）+ **UCPD Annex I §13**（同款仿冒误导）。**这是本表里少数有「器械专条」的规则之一** |
| **H09** | 智能闭环/仿生虚假宣称（auto-detects rhythm / mimics your baby / fullness feedback） | **法源可查** | **EU MDR Art. 7(a)**（ascribing functions and properties to the device which the device does not have）+ **FTC Deception Policy 1983**（false oral or written representations）。⚠️ 竞品实证：Medela 全站用 "mimic your baby's natural sucking rhythm"（见 §7.5），**说明该规则在措辞层面过宽，应改为「禁止声称设备能自动识别/闭环反馈生理信号」** |
| **M01** | 静音程度夸大（silent / noiseless / whisper-quiet） | **准法源** | **FTC 1984**（"silent" 是可证伪的客观声称）+ **FTC Deception Policy 1983**。⚠️ Elvie 用 `the quietest`（最高级），与 H05「排名最高级放开」的口径冲突 |
| **M02** | 吸力夸大用语（super strong / ultra powerful / max suction） | **准法源** | **21 CFR 884.5150**（分类条款本身用 **250 mmHg** 定义界限 —— 这是唯一能找到的吸力数值锚点）+ **IEC 60601-1**（医用电气设备通用安全）。**建议 M02 的合规替代写法直接锚定 mmHg 数值**（竞品实证：Willow "up to 295 mmHG per side"、BabyBuddha "53 to 315 mmHg"） |
| **M03** | 未标注来源的效果数据声明（30% more milk / 2x faster / bestseller / trusted by 6 million） | **法源可查** | **FTC HPCG 2022 §1**（assertion about amount/type/strength of evidence must be accurate）+ **FTC 1984**（express substantiation claim）+ **UCPD Art. 6(1)(b)**（"the results and material features of tests or checks carried out on the product"）。**注意 "bestseller"/"top rated" 属可核查的市场事实，与效果数据不是一类，建议拆开** |
| **M04** | 制造焦虑的压力话术（last chance / limited time / hurry） | **法源可查** | **UCPD Annex I §7**（"Falsely stating that a product will only be available for a very limited time, or that it will only be available on particular terms for a very limited time, in order to elicit an immediate decision"）。⚠️ **注意 Annex I §7 限定语是 "Falsely"** —— 真实的限时促销不构成 unfair。当前 M04 无条件判险，**口径比法源严格** |
| **M05** | 等级背书用语（medical grade silicone / hospital grade / military grade） | **准法源（当前口径偏严）** | **无任何法定定义**（本次调研在 21 CFR、MDR、MHRA 中均未找到 grade 类术语的定义）。判据应来自 **UCPD Art. 6(1)(b)**（main characteristics of the product）与 **FTC Deception Policy**。**建议改用「grade 词是否锚定在可核查参数上」判险 —— 见 §7.2 卖点 F** |
| **M06** | 模糊对比（better than / vs competitors / 优于） | **法源可查** | **21 CFR 801.6**（同上）+ **UCPD Art. 6(2)(a)**。⚠️ 与 H08 高度重叠，**建议合并为一条带严重度分档的规则**（无数据的模糊对比 = 审慎；捏造的量化对比 = 高危） |
| **M07** | 效率/漏奶/奶流/移除量/短时排乳类 claim | **准法源** | **FTC HPCG 2022 p.13**（健康相关 benefit 需 RCT）+ **UCPD Art. 6(1)(b)**。⚠️ 正则过宽：`leak-?proof` 会**误伤产品结构描述**（Willow "100% leak-proof" 是产品属性描述） |
| **U01** | 含泌乳顾问/认证头衔（lactation consultant / IBCLC / expert-tuned） | **准法源** | **FTC 1984**（endorsement 层面的 substantiation）+ **EU Reg 1924/2006 Art. 12(c)**（个人推荐一律禁止）+ **Art. 11**（机构级推荐适用各国规则）。**"expert-designed"/"expert-tuned" 属事实性声称，需要真的有人**；`IBCLC` 是可核查的专业认证头衔 |
| **U02** | 保险/HSA/FSA 报销声明（已停用） | **法源可查** | 美国：IRS Pub 502 定义 HSA/FSA 合格医疗费用；**21 CFR 801.5** 要求标注全部 intended uses（报销资质属于使用条件）。**注意：停用理由写的是"站点报销资质已具备"，这是资质状态判断，不是规则本身失效。建议保留为「高置信白名单」而非删除** |
| **U03** | 医院/NICU 场景（hospital / NICU / nicu grade） | **准法源** | **FTC HPCG 2022 Example 34**（特定人群结论不得外推）+ **UCPD Art. 7**（误导性遗漏：未披露设备非医用场景适用性）。**核心风险不是"提到医院"，而是"在医院场景下使用"这个隐含声称缺乏证据** |
| **U04** | 疼痛/堵奶场景化名词（sore nipples / clogged ducts / painful pumping） | **准法源** | **FTC Deception Policy 1983**（"the entire mosaic, rather than each tile separately" —— 名词本身中性，与消除性动词连用才构成声称）+ **MDR Art. 7(d)**（suggesting uses beyond intended purpose）。**U04 的现有设计（与消除性表述连用则升级 H01/H07）在方法论上是对的，只需补法源注释** |
| **安全词白名单** | 27 个词条 | **混合** | 见 §9.4 逐词判定。**其中 `reduces pain` / `less pain` 与 H07 直接冲突；`FDA registered` 应从白名单移出** |

**统计结果**：

| 状态 | 条数 | 占比 |
|---|---|---|
| **法源可查**（有成文条款直接约束） | **11**（H01、H03、H04、H06、H08、H09、M03、M04、M06、U02，加 M05 部分） | 约 46% |
| **准法源**（有官方指南/执法政策/判例） | **12** | 约 50% |
| **纯经验判断** | **1**（U01 的 "expert-designed" 部分依赖内部合作事实核实） | 约 4% |

> **这回答了委托方的核心问题**：
>
> **吸奶器这个品类给规则库带来的，本质上是一张法规映射表，而不是一堆经验。** 21 条规则里 **96% 能回溯到法源或准法源**，只有个位数百分点是纯经验。
>
> **但「能回溯」不等于「当前写得对」。** 本次调研发现 **5 处实质性偏差**：
> 1. **H02** 把"词"当红线（法源只要求"有证据"）→ **过度禁用**
> 2. **H06** 正则漏掉 `FDA compliant` 等变体，且豁免词含 `FDA registered` → **漏检 + 反向风险**
> 3. **H05 与 M01 口径冲突**（排名最高级已放开，但 quietest/silent 仍审慎）
> 4. **M07 正则误伤产品结构描述**（leak-proof）
> 5. **安全词表含 `reduces pain`/`less pain`，与 H07 直接矛盾**
>
> 另外 **2 处结构性缺失**：
> 6. **没有「广告与 IFU 一致性」规则**（法源：21 CFR 801.5）
> 7. **没有「易感受众」维度**（法源：FTC Deception Policy 1983「examine reasonableness from the perspective of that group」+ 产后哺乳期母亲属 FTC 意义上的易感群体）

### 9.2 哪些条款可直接引用法源（附建议的 `依据来源` 字段填法）

**建议把 `依据来源` 字段改为结构化字段**：

```
legal_basis:
  - jurisdiction: US
    instrument: "21 CFR"
    citation: "807.97"
    quote: "does not in any way denote official approval of the device. Any representation that creates an impression of official approval of a device because of complying with the premarket notification regulations is misleading and constitutes misbranding."
    url: "https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-807/subpart-E/section-807.97"
    retrieved: 2026-09-15
  - jurisdiction: EU
    instrument: "Directive 2005/29/EC"
    citation: "Annex I §4"
    quote: "Claiming that a trader ... or a product has been approved, endorsed or authorised by a public or private body when he/it has not ..."
    url: "https://publications.europa.eu/resource/celex/02005L0029-20220528"
    retrieved: 2026-09-15
guidance_basis:      # 非法条但可引的官方文件
  - "FTC Health Products Compliance Guidance (2022-12), p.13"
  - "FTC Policy Statement Regarding Advertising Substantiation (1984-11-23)"
  - "FTC Policy Statement on Deception (1983-10-14)"
  - "FDA General/Specific Intended Use — Guidance for Industry (1998-11-04)"
  - "MDCG 2021-24 Rev.1"
platform_policy:     # 平台侧（独立字段，不产生法律责任）
  - platform: Meta
    section: "Health and wellness"
internal_basis:      # 内部反馈（当前绝大多数规则只有这一项）
  - "W1卖点表达边界（品线反馈2026-09-10 T4）"
  - "吸奶器广告文案审计_红绿灯.xlsx 规则库"
```

**可直接填 legal_basis 的规则清单**（按法源强度排序）：

| 优先级 | 规则 | 可直接引用的条款 | 引用后规则可以怎么变 |
|---|---|---|---|
| 1 | **H06** | 21 CFR 807.97；21 CFR 807.22(b)(1)；UCPD Annex I §4 | 可把正则扩到所有 FDA 动词变体；可把 `FDA registered` 移出豁免词；**风险等级可从"内部口径高危"升级为"法定违法"** |
| 2 | **H01** | 21 CFR 801.4；21 CFR 807.81(a)(3)(ii)；MDR Art. 7(a)(b)(d)；UCPD Annex I §17 | 可把「疏通堵奶」这类词从"品牌口径禁"升级为"触发重新申报义务"；**可给规则加一个"监管后果"字段说明违反后会发生什么** |
| 3 | **H08** | 21 CFR 801.6；UCPD Art. 6(2)(a)；UCPD Annex I §13 | 从「模糊的贬低竞品」变成有器械专条支撑的 misbranding 判定 |
| 4 | **H03** | FTC HPCG 2022 §1 + Example 18；FTC 1984 | 从"未经备案的临床背书"变成"必须达到所宣称的证据层级"；**可据此设计"证据包"字段** |
| 5 | **H04** | FTC 1984（明文列 "doctors recommend"）；EU Reg 1924/2006 Art. 12(c) | 欧盟侧从"需核实"变成"一律禁止"；美国侧从"无据"变成"必须有该层级的证据" |
| 6 | **H09** | MDR Art. 7(a) | 从"品牌自定边界"变成"ascribing functions the device does not have"——**这正好对应 H09 的判定理由** |
| 7 | **M03** | FTC HPCG 2022 §1；FTC 1984；UCPD Art. 6(1)(b) | 从"未标注来源"变成"证据层级不足"；**建议拆成"效果数据"与"市场排名"两条** |
| 8 | **M04** | UCPD Annex I §7 | ⚠️ **当前口径比法源严**：法源限定 "Falsely stating"，真实限时促销不违法。**建议加"真实性"前置条件** |
| 9 | **M06** | 21 CFR 801.6；UCPD Art. 6(2)(a) | 与 H08 合并 |
| 10 | **U02** | 21 CFR 801.5（intended uses 完整性）；IRS Pub 502（HSA/FSA 合格费用） | ⚠️ **建议不要因"资质已具备"而停用，而应改为"高置信白名单"** —— 资质状态变化时规则还在 |

### 9.3 哪些条款没有法源、必须靠案例积累（自下而上的萃取对象）

**严格来说：没有一条规则是"完全没有法源"的。** 但有 **6 条属于"准法源"** —— 它们的判定标准来自**一般原则**（"绝对声称需 substantiation"、"主观 vs 客观声称的分界"），而**不是来自针对该行为的专门条款**。这类规则的边界**只能靠案例积累**：

| 规则 | 为什么没有专门法源 | 应当自下而上积累什么 |
|---|---|---|
| **H05**（safest / 100% / fits all） | 没有条款说"不许说 safest"。判据是"绝对声称 = 可证伪 = 需证据"的一般原则 | 累积「什么绝对声称被 FTC 挑战过 / 什么活下来了」的案例。**关键待定问题：竞品都在用 `100% leak-proof`（Willow）、`100% comfort rating`（Willow）、`FDA approved`（Lansinoh），Momcozy 用 `100%` 会被判险吗？** |
| **H07**（疼痛功效） | 法源只提供"客观声称需证据"的一般原则 | 累积「哪些疼痛表述被 FTC/平台判定为客观声称」的案例。**关键待定问题：`comfort` 与 `less pain` 之间，`without the ouch`（Elvie 在用）落在哪一侧？** |
| **M01**（静音夸大） | 无条款 | 累积「dB 数值锚定的静音声称是否安全」的案例。**关键待定问题：`silent` vs `the quietest`（Elvie 在用）vs `low-noise`（BabyBuddha 在用），三者的相对风险** |
| **M02**（吸力夸大） | 唯一锚点是 21 CFR 884.5150 的 250 mmHg（且那是**手动泵**的豁免阈值，不是电动泵的上限） | 累积「哪些吸力表述被判定为夸大」的案例。**关键待定问题：Willow 的 `up to 295 mmHG` 是合规的，那 Momcozy 的 `-292 mmHg` 为什么不同？** |
| **M05**（grade 用语） | 无任何法定定义 | 累积「grade 词 + 数值锚」的案例。**关键待定问题：`hospital-grade suction`（裸）与 `hospital-strength suction up to 295 mmHg`，前者违规后者合规——这条边界有多少竞品样本可以校准？** |
| **U01**（IBCLC / expert-designed） | 认证头衔本身可核查，但"expert-designed"涉及事实核实 | 累积「以专家背书为核心的表达被判险」的案例。**注意 Momcozy W1 页已经在用 "— Lactation Experts & Momcozy Medical Team" 的署名格式 —— 这是需要核实的事实性声称** |
| **U03**（医院/NICU 场景） | 提到医院本身不违法 | 累积「场景暗示被判为功效声称」的案例 |

**自下而上的萃取方法建议**（这三类规则的边界只能这样定）：

1. **竞品对标集**：把本次调研的 7 品牌语料做成一个**持续更新的 benchmark 语料库**。每次发现一个竞品在用的表达，就问三个问题：①他们配了什么证据？②他们在哪个法域投？③他们活了多久？**一个表达"在用"不等于"合规"，但"全行业都在用而 Momcozy 单独禁用"是规则过严的强信号。**
2. **平台处置日志**：这是唯一的"红线实测"来源。委托方目前没有这类数据（治理约束里写「无法强制卡死审查完才能上线」）。**建议至少监控竞品账号的广告下架情况**（Meta Ad Library 会显示 "This ad was removed"）。
3. **改写回归集**：把 52 条改写建议 + 291 条在跑记录里的「命中片段 → 修改建议」作为正负样本对，这是最现成的 Golden Dataset 种子。

**明确不必自下而上、可自上而下直接锁定的**：H01、H03、H04、H06、H08、H09 六条。**这六条应当作为"不随案例漂移的稳定层"**，因为它们有确定条款。**任何来自案例的"这条其实可以放宽"的意见，在这六条上都不成立。**

### 9.4 安全词的判别标准

**判别标准（一条，可直接做成 schema 字段）**：

```
is_verifiable: boolean          # 能否被第三方独立复核为真/假
verification_method: enum       # 如何复核
  - certificate_lookup          # 证书/注册号可查（K号、ISO证书号、BPA检测报告号）
  - measurement                 # 可测量（mmHg、dB、mL、inch、温度）
  - material_declaration        # 材料成分声明（可送检复核）
  - structural_description      # 结构描述（closed system、dishwasher safe）
  - none                        # 无法复核 → 不是安全词
safe_word_class: enum
  - objective_fact              # → 安全词
  - puffery                     # → 允许但不得量化、不得附功效（FTC 1983 脚注 42）
  - substantiation_required     # → 非安全词，需证据（FTC HPCG 2022）
```

**逐词判定表**（对委托方现有 27 个安全词）：

| 词条 | is_verifiable | 判定 | 理由 / 法源 |
|---|---|---|---|
| `suction level` | ✅ | objective_fact | 可测。锚点：21 CFR 884.5150 用 250 mmHg 定义界限 |
| `suction levels` | ✅ | objective_fact | 同上（档位数可数） |
| `adjustable suction` | ✅ | objective_fact | 结构/功能事实 |
| `9 levels` / `10 levels` | ✅ | objective_fact | 可数 |
| `hands-free` | ✅ | objective_fact | 结构描述（无需手持） |
| `wearable` | ✅ | objective_fact | 结构描述（可穿戴） |
| `portable` | ✅ | objective_fact | 结构描述（可携带） |
| `rechargeable` | ✅ | objective_fact | 结构描述（可充电） |
| `wireless` | ✅ | objective_fact | 结构描述（无绳） |
| `BPA-free` | ✅（需报告） | objective_fact | ⚠️ **不是法定术语**，但可通过检测报告复核。**注意：美国没有强制 BPA-free 要求**（见 §10） |
| `food-grade silicone` | ⚠️ | **建议替换** | **不是法定术语**。美国可改为 `food-contact silicone (21 CFR 177.2600 compliant)`。⚠️ **`LFGB-tested` 只在能指名具体检验方法且持有报告时才成立**（§ 64 LFGB 只建立「官方检验方法汇编」，不建立认证）；**`LFGB certified` 一律不得使用** —— LFGB 无认证机制，且 § 33 + § 59(1) Nr. 18 使误导性表述本身可罚（见 R5-C10） |
| `food grade` | ⚠️ | **建议替换** | 同上 |
| `FDA cleared` | ✅ | objective_fact | 可通过 openFDA 查 K 号。**建议追加约束：需填写 K 号** |
| `FDA-cleared` | ✅ | objective_fact | 同上 |
| **`FDA registered`** | ✅（可查） | ❌ **应移出安全词 → U 类人工复核** | **语义 ≠ cleared**。FDA 明说 registration "does not denote approval, clearance, or authorization"；且明说 "FDA Registered" 是误导性用法。**放在安全词表里会诱导文案写成 "FDA registered facility" 暗示认可** |
| `easy to clean` | ⚠️ | puffery（弱客观） | 半主观。可保留但不得量化（不能说 "3x easier to clean"） |
| `dishwasher safe` | ✅ | objective_fact | 可测（洗碗机测试） |
| `quiet mode` | ✅ | objective_fact | 是模式名，非程度声称 |
| `low noise` | ✅（需 dB） | objective_fact | ⚠️ 可测但**需要 dB 数值支撑**。裸用 `low noise` 无锚点时应降为 puffery |
| `low-decibel` | ✅（需 dB） | objective_fact | 同上 |
| **`reduces pain`** | ❌ | ❌ **与 H07 直接冲突，必须删除** | H07 把 `reduce pain`/`reduces pain`/`less pain` 列为高危禁用。**安全词表列它为合规 —— 规则库自相矛盾** |
| **`less pain`** | ❌ | ❌ **同上，必须删除** | 同上 |
| `gentle` | ❌ | puffery | 主观体验（FTC 1983 脚注 42："feel" 类主观声称一般不被挑战）。**可保留，但不得量化、不得与功效连用** |
| `comfort` | ❌ | puffery | 同上。**注意：Medela 与 BabyBuddha 都把 comfort 当主力词用** —— 这是行业最稳的舒适类表达 |

**新增建议的安全词类别**（本次调研发现的、可核查但委托方未收录的）：

| 建议新增 | is_verifiable | 理由 |
|---|---|---|
| `up to N mmHg` / `N–M mmHg` | ✅ | 可测。**竞品实证**：Willow "up to 295 mmHG per side"、BabyBuddha "53 to 315 mmHg"、Lansinoh 280 mmHg。**这是 M02 的合规替代写法** |
| `N dB` | ✅ | 可测。M01 的合规替代写法 |
| `closed system` | ✅ | 结构描述。**竞品实证**：Medela "Closed system with BPA-free construction"、Willow "closed-system pump"。**这是 M07 漏奶类声称的合规替代** |
| `N oz / N mL capacity` | ✅ | 可测 |
| `ISO 13485` / `ISO 9001` / `IEC 60601-1` / `ISO 10079-1` | ✅ | **证书可查**。⚠️ **本次未能核实这几项标准的具体适用范围文本**（见第十一节），在补充核实前不要写成"符合"。 |
| `NCT` + 注册号 | ✅ | **可查。这是最强的证据标记**（竞品实证：Medela 用 4 个 NCT 号）。**建议把「引用 NCT 号」提升为一条"证据充分"信号** |

### 9.5 竞品对照的结论：规则校准建议

#### (a) 「行业通行但 Momcozy 现在禁止」的表达 —— **规则过严，需复核**

| 表达 | 谁在用 | 用法 | 建议 |
|---|---|---|---|
| **`mimic your baby` / `mimics babies' natural sucking rhythm`** | **Medela**（Freestyle Mini、Harmony、Swing Maxi 等多页，带 `patented 2-Phase Expression®`） | 产品核心技术的描述语 | **H09 应改为「禁止声称设备能自动识别/闭环反馈生理信号」，而非禁止 mimic 修辞**。Momcozy 的 W1/V1 是用户主动调节，Medela 的 2-Phase 是程序化的两段曲线 —— **两者都不是"闭环生理识别"，Medela 的说法并未超出。** |
| **`more milk`（裸用）** | **Medela**（"18% more milk on average"）、**Willow**（"More milk." 头图）、**Elvie**（"boost your milk flow"）、**Lansinoh**、**Momcozy 自己（S12 Pro）** | 5/7 品牌在用 | **H02 应从"词红线"改为"证据红线"**：无 RCT 证据时高危；有 NCT/第三方证据时可放行 |
| **`clinically proven`** | **Medela**（带 4 个 NCT）、**Willow**（无整机 RCT 引用） | 2/7 品牌在用 | **H03 应改为「声明的证据层级必须与所宣称的一致」（FTC HPCG §1）**，而不是一律禁止。区别在于 Medela 达标、Willow 不达标 |
| **`hospital grade` / `hospital strength`** | **Medela、Willow、Elvie、Lansinoh、BabyBuddha、Spectra、Momcozy —— 全部 7 个** | 全部在用，但用法分三类（裸用 / 数值锚定 / 主动否认） | **M05 不能按"是否用 grade 词"判险**（那样全行业都违规，规则失去区分度）。**改为按"是否锚定可核查参数"判险** |
| **`reduce nipple pain`** | **Willow** | 官网产品页 | H07 **保留**（该表达需 RCT 证据，Momcozy 没有），但**依据来源升级**；同时删除安全词表中的 `reduces pain`/`less pain` |
| **`the quietest`** | **Elvie**（带脚注 ¹） | 产品主文案 | 与 H05「排名最高级放开」的口径统一：**最高级声称归入"需 substantiation"，不做二元放行/禁止** |
| **`100% leak-proof`** | **Willow**（360 全套文案） | 产品属性描述 | **M07 正则收窄**，区分"产品结构描述"与"使用结果承诺" |
| **`fit most nursing bras`** | **Medela** | 限定词替代全称 | **H05 的正确改写模板**（全称 → 比例） |
| **`FDA registered`** 作为可接受表述 | 无竞品在用（Medela 零 FDA 表述；Willow 用 cleared；Lansinoh/Willow 误用 approved） | — | **从安全词移出** |

#### (b) 「Momcozy 允许但竞品都不敢用」的表达 —— **规则过松，需收紧**

初查时这个方向的样本很少，但第三方抓取到位后，**在委托方自有品牌上找到了 3 条明确属于"竞品都不用、Momcozy 在用"的表达**：

| 表达 | Momcozy 用法（逐字） | 竞品情况 | 建议 |
|---|---|---|---|
| **`auto-detects rhythm` / `automatically finds the best rhythm`** | H09 已禁用（正确） | Willow 360 用 **"Smart Suction technology designed to detect letdown and automatically switch from stimulation to expression"**；**"Sensors automatically detect letdown and track milk volume in real time."** | ⚠️ **Willow 在做 H09 所禁止的精确行为（自动检测 letdown）**，而且 Willow 360 拿到了 FDA clearance。**这提示：若 Momcozy 的产品确实具备 letdown 检测并获得 clearance，H09 可以放宽到"必须有 clearance 覆盖"** —— 但 Momcozy 的 V1/W1 目前不具备（按 H09 的判定理由）。**这条边界应当按"设备实际能力"而非"措辞"来定** |
| **`FDA 510(k) Cleared`（W1 页）** | Momcozy W1 页在用 | Medela 零 FDA 表述；Willow 用 cleared（也有误用 approved）；BabyBuddha / Lansinoh 误用 approved | ⚠️ **不是"过松"，而是"待核实"**。**必须核实 W1 对应的 K 号是否覆盖 warmth+massage 功能**。若覆盖 → 这条是全行业最规范的 FDA 用法，应写入改写建议库作为模板；若不覆盖 → 这是本次调研发现的最高风险项 |
| **`Safe for both mother and baby`（全称安全声称）** | S12 Pro Quick 页：*"BPA-free, food-grade materials: **Safe for both mother and baby.**"* | **无任何竞品使用全称安全表述**。Medela / BabyBuddha 停在 `"Closed system with BPA-free construction"`；Willow 用 `"made without BPA"`（更保守的措辞，避免了 "free" 这个词）；Lansinoh 用 `"made without BPA"` | ❌ **立即收紧。** 这是 H05（虚假安全承诺）的核心形态：`Safe for both mother and baby` 是一个**不可证伪的全称安全断言**，直接落 FTC Deception Policy 1983 的 "affirmative product claim for which documentation would be expected" |
| **`28.2% increase milk production`** | V1 Pro / V2 Pro / Electric 集合页（详见 §7.8） | **无任何竞品用单一数字跨多产品声称奶量提升**。Medela 用 `18% more milk`（带 NCT）；Willow 用 `71% said better milk output`（带第三方样本量） | ❌ **立即整改。** 见 §7.8 的逐条判定 |
| **`Hospital-Grade`（写进亚马逊 listing 标题 + 结构化属性）** | Amazon ASIN `B0CZNQ7VH7`：标题含 `Hospital-Grade Pocket Primary Pump`；`Product Style: hospital grade` | **无任何竞品把 hospital-grade 写进亚马逊结构化属性**。Elvie / Spectra 写进产品名，但未同时声明"这个词不成立" | ❌ **立即整改。** 与官网 hospital-grade 集合页的否认声明直接冲突（详见 §7.7） |

#### (c) 对规则校准的总体含义

1. **规则库的总体方向是"偏严"，但存在 3 处关键的"内部矛盾"和"跨渠道矛盾"，其危害大于"过严"本身。**
   - **过严的规则**：H02（把词当红线）、M01（与 H05 口径冲突）、M04（法源限定 "Falsely"）、M07（正则误伤）、H05（内部口径冲突）—— **共 5 条**。
   - **自相矛盾的规则**：安全词表的 `reduces pain` / `less pain` 与 H07 直接冲突 —— **1 处，最严重**。
   - **跨渠道矛盾（新发现）**：hospital-grade 在官网集合页否认、在官网另一集合页主张、在亚马逊标题与结构化属性主张 —— **3 个渠道 3 种立场**。**这是本次调研发现的最可执行的整改项，因为它不需要等法规判断，现在就能改。**
2. **"偏严"的两个副作用**：①**规则失去区分度** —— 当全行业都在用 `hospital grade`、`mimic baby`、`more milk` 时，把这些判为高危等于把所有竞品都判为高危，规则无法帮助文案判断"哪个更危险"；②**规则会被绕过** —— Momcozy 自己的 W1 页就在用 H02 禁止的 `release oxytocin`，M6 亚马逊 bullet 就在用 H02 的 `increasing milk production`，说明当规则与实际业务需求冲突时，规则会被违反而不是被执行。
3. **校准方向**：**从「词表红线」转向「证据红线」。** 每条规则的判定不应问"用了这个词吗"，而应问"**这个词所隐含的客观声称，有没有达到 FTC 要求的证据层级？**"
   - 有 NCT / IRB / 第三方样本量 → 放行
   - 有内部测试但披露了方法与"结果因人而异" → 降级为人工复核
   - 无任何来源 → 高危
   - 是纯主观体验词（comfort / gentle）→ 安全词
   - **是机器性能指标（泵送速度 / 效率）→ 需披露测试条件，但不需 RCT**
   - **是人体生理结果（奶量 / 排空 / 疼痛）→ 需 RCT**（这一条区分是本次调研对 H02/M07 最关键的结构性修正，见 §7.8）
4. **每条规则应增设"监管后果"字段**，说明违反后会发生什么：misbranding（H06）→ 扣押/禁令；new intended use（H01）→ 需重新 510(k)；MDR Art. 7（H01/H09 欧盟）→ 成员国市场措施。**这比"高风险/中风险"对文案更有指导意义。**
5. **每条规则应增设"跨渠道一致性"检查**（新建议）。委托方的治理约束里写「无法强制卡死审查完才能上线」，但如果审查只覆盖官网文案、不覆盖亚马逊 listing 与投流素材，那么 §7.7 那类跨渠道矛盾**必然发生且必然漏检**。**至少应当把亚马逊 listing 的标题、bullet 与结构化属性纳入审查范围。**

### 9.6 对手头材料的具体修改清单（可直接执行）

| # | 动作 | 对象 | 依据 |
|---|---|---|---|
| **0** | **立即整改：统一 hospital-grade 口径。** 清理亚马逊 ASIN `B0CZNQ7VH7` 标题中的 `Hospital-Grade` 与结构化属性 `Product Style: hospital grade`；清理 `collections/electric-breast-pump` 的 "V Series — hospital grade suction"；把官网 `collections/hospital-grade-breast-pump` 的术语表 Q&A 提升为品牌级官方术语表 | **自有品牌（P0）** | §7.7、UCPD Art. 6(1)(b) |
| **0'** | **立即整改：`28.2%` 的三种含义拆开。** 机器指标（效率/速度）与人体结果（奶量）不能共用同一个数字；「奶量提升 28.2%」在无 RCT 的情况下应删除或改写 | **自有品牌（P0）** | §7.8、FTC HPCG 2022 §1 + Example 18 |
| **0''** | **立即整改：删除 `Safe for both mother and baby` 全称安全断言**（S12 Pro Quick 页） | **自有品牌（P0）** | §9.5(b)、FTC Deception Policy 1983 |
| **0'''** | **立即整改：M9 页 "FDA and LFGB certified"** 改为材料级表述（如 `made with materials tested to FDA food-contact requirements`），不得用 "FDA certified" | **自有品牌（P0）** | 21 CFR 807.97（精神）；FDA 消费者页面 |
| 1 | 正则改为 `\bFDA[\s-]+(and\s+\w+\s+)?(approved\|certified\|compliant\|endorsed\|verified\|authorized\|qualified)\b`（兼容 "FDA and LFGB certified" 语序） | H06 `正则表达式` | §7.3（实测 4 个变体在用） |
| 2 | 从豁免词删除 `FDA registered` / `FDA 注册` | H06 `豁免词` | 21 CFR 807.22；FDA 消费者页面 |
| 3 | 从安全词删除 `reduces pain` / `less pain` | `安全词` | 与 H07 直接矛盾 |
| 4 | `依据来源` 拆为 `legal_basis` / `guidance_basis` / `platform_policy` / `internal_basis` 四字段 | 全部规则 schema | §9.2 |
| 5 | H01/H03/H04/H06/H08/H09 填入具体条款号 | 六条规则 | §9.2 表格 |
| 6 | H02 增加「证据包」子字段（NCT 号 / IRB 号 / 第三方样本量 / 内部测试 / 无），并按证据等级重新分档 | H02 | §7.2 卖点 A、§7.8 |
| 6' | **H02 增加「声称对象」子字段**：`machine_metric`（泵送速度/效率，只测设备） vs `human_outcome`（奶量/排空，属生理结果）。前者不需 RCT，后者需 RCT | H02、M07 | §7.8 |
| 7 | M05 判定逻辑改为「grade 词是否锚定可核查参数」+「跨渠道是否一致」 | M05 | §7.2 卖点 F、§7.7 |
| 8 | M07 正则收窄，区分结构描述与结果承诺 | M07 | §7.2 卖点 C |
| 9 | M01 与 H05 口径统一（最高级声称一律需 substantiation） | M01、H05 | §7.2 卖点 D |
| 10 | M04 增加"真实性"前置条件（法源限定 Falsely） | M04 | UCPD Annex I §7 |
| 11 | `适用产品` 从型号改为 `product_code`（HGX/HGY/OHH/PWA） | 全部规则 | §3.2 |
| 12 | 新增规则 `H10`：广告声称与 IFU/intended use 不一致 | 新增 | 21 CFR 801.5 |
| 13 | 新增规则 `U05`：面向产后哺乳期母亲的易感受众表述 | 新增 | FTC Deception Policy 1983 |
| 13' | 新增规则 `Z1`：禁止把 FDA clearance 与保险报销资格做因果绑定 | 新增（与 U02 合并处理） | §7.3；FTC Deception Policy 1983 |
| 14 | U02 从"停用"改为"高置信白名单"（保留规则，标注资质状态） | U02 | §9.1 |
| 15 | 安全词表增加 `up to N mmHg` / `N dB` / `closed system` / `NCT 号` | `安全词` | §9.4 |
| 16 | 核实 W1（Wellness 1）对应的 FDA K 号是否覆盖 warmth+massage 功能 | 新增待办（P0） | §7.3、R5-C5、§12 G3 |
| 17 | 修正 W1 页的 RCT 引用：披露 NICU 人群限定、说明是"设计借鉴"而非本机证据、补 DOI 链接 | 自有品牌 | §7.9、FTC HPCG 2022 Example 34 |
| 18 | 补全免责声明的不对称：把 `Individual results may vary` 从 W1 单页扩展到所有含功效声称的页面，或（更好）删除无证据的功效声称 | 自有品牌 | §7.8、FTC Deception Policy 1983 |

---

## 十、BPA 与材料类安全词的法规依据

> 证据：`_evidence/R5/materials/`（含 `ecfr-177-2600.xml`、LFGB § 30/§ 31 德文原文、ISO/IEC 标准页骨架）。全部抓取日 2026-09-15。

### 10.1 `food-grade silicone` —— 非法定术语，但有一个可引用的美国法源

**结论：`food-grade silicone` 在美国和欧盟都不是法定术语。** 但美国有一条**可核查的替代表述**。

**法源（美国）—— 21 CFR 177.2600 Rubber articles intended for repeated use（逐字）**

> Rubber articles intended for repeated use may be safely used in producing, manufacturing, packing, processing, preparing, treating, packaging, transporting, or holding food, subject to the provisions of this section.
> (a) The rubber articles are prepared from natural and/or synthetic polymers and adjuvant substances as described in paragraph (c) of this section.
> (b) The quantity of any substance employed in the production of rubber articles intended for repeated use shall not exceed the amount reasonably required to accomplish the intended effect in the rubber article and shall not be intended to accomplish any effect in food.
> (c) Substances employed in the preparation of rubber articles include the following, subject to any limitations prescribed:
> …
> (4)(i) Elastomers. … **Silicone basic polymer as described in ASTM method D1418-81** … **Silicone (Si) elastomers containing methyl groups.** **Silicone (Psi) elastomers** …
>
> **(e)** Rubber articles intended for repeated use in contact with **aqueous food** shall meet the following specifications: The food-contact surface of the rubber article in the finished form in which it is to contact food, when extracted with **distilled water at reflux temperature**, shall yield total extractives **not to exceed 20 milligrams per square inch during the first 7 hours of extraction, nor to exceed 1 milligram per square inch during the succeeding 2 hours of extraction.**
>
> **(f)** Rubber articles intended for repeated use in contact with **fatty foods** shall meet the following specifications: The food-contact surface of the rubber article in the finished form in which it is to contact food, when extracted with **n-hexane at reflux temperature**, shall yield total extractives **not to exceed 175 milligrams per square inch during the first 7 hours of extraction, nor to exceed 4 milligrams per square inch during the succeeding 2 hours of extraction.**
>
> (g) In accordance with good manufacturing practice finished rubber articles intended for repeated use in contact with food shall be thoroughly cleansed prior to their first use in contact with food.
> **(h) The provisions of this section are not applicable to rubber nursing-bottle nipples.**
> [42 FR 14572, Mar. 15, 1977]

- URL：https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-177/subpart-C/section-177.2600
- 本地证据：`_evidence/R5/materials/ecfr-177-2600.xml`

> **三点关键发现**：
>
> 1. **矽橡膠（silicone elastomer）确实被 177.2600(c)(4)(i) 明确列为可用于重复使用食品接触橡胶制品的弹性体。** 这是「食品级矽膠」在美国的**真实法源**。
> 2. **真正的合规标准是两个萃取限值**（水 20 mg/in² 首 7 小时、正己烷 175 mg/in² 首 7 小时）。**这意味着「food-grade silicone」是一个可核查的客观事实**（前提是有萃取检测报告），只是它的正确表述应当是 `silicone meeting 21 CFR 177.2600 extractives limits` 而不是 `food-grade`。
> 3. **⚠️ 177.2600(h) 明确排除了「rubber nursing-bottle nipples」（奶瓶奶嘴）。** 这意味着**矽膠奶嘴不适用 177.2600**，另有对应法规。**委托方的吸奶器配件中若有矽膠奶嘴类产品，不能引用 177.2600。** 这是一个容易出错的边界。

**竞品实证**：Medela / Willow / BabyBuddha 都**不使用** `food-grade silicone` 这个词，改用更保守的结构与材料表述（`Closed system with BPA-free construction`、`made without BPA`、`BPA-free parts that come into contact with breast milk`）。**Momcozy 是本次调研中唯一使用 `food-grade silicone` / `food-grade PP` 的品牌**（S9 Pro、M5、S12 Pro 等多个页面）。

### 10.2 `BPA-free` —— 不是法定术语，美国没有强制要求

**结论：`BPA-free` 是自愿的营销声称，不是法定认证。**

**本次已补齐美国侧的法源（2026-09-15 补证）**：`fda.gov` 虽对 `curl` 返回 Akamai 拦截，但 **`ecfr.gov` 可正常取到正文**（需 `-L` 跟随 302 + 完整浏览器 UA，经本地代理）。本节此前标注为未核实的两项，现均有 Primary Source。

**法源 —— 21 CFR 177.1580(d) Polycarbonate resins（逐字，权威原文）**

> **(d) Polycarbonate resins may be used in accordance with this section except in infant feeding bottles (baby bottles) and spill-proof cups, including their closures and lids, designed to help train babies and toddlers to drink from cups (sippy cups).**
>
> [42 FR 14572, Mar. 15, 1977, as amended at … **77 FR 41902, July 17, 2012**]

- 来源：eCFR，Title 21 截至 **2026-09-10** 的现行版本
- 本地证据：`_evidence/R5/materials/ecfr-177-1580-polycarbonate-resins.html`

**逐字读出来的三层含义（这才是「BPA-free 不是法定要求」的真正法源）**：

1. **它是一个「用途排除」，不是「物质禁令」。** 该条禁止的是把**聚碳酸酯树脂**用于婴儿奶瓶与吸嘴杯（含其盖与扣件）这几类**特定产品**；**BPA 作为聚碳酸酯单体在其他所有用途中仍然合法**。所以「美国禁了 BPA」是错的，正确表述是「美国把 BPA 从婴儿奶瓶/吸嘴杯这两类用途中移出了」。
2. **它管的是聚碳酸酯（PC），不是硅胶。** §177.1580 的标题是 *Polycarbonate resins*。**委托方若使用的是矽膠與 PP 部件，本条的适用性與「矽膠是否食品级」是两回事** —— 不要把 177.1580 与 177.2600（rubber articles，见 §10.1）混为一谈。**Momcozy 的 `BPA-free` 声称若要核查，核查对象是奶瓶/储奶容器这类 PC 可能出现的部件，而 `food-grade silicone` 的核查对象是 §10.1 的萃取限值。**
3. **该排除是通过「食品添加剂废弃（abandonment）」程序完成的，不是基于安全性。** 对应 **77 FR 41899（2012-07-17，ACC 申请）** 与 **78 FR 41840（2013-07-12，Markey 申请）**。**FDA 的逐字表述为：`An amendment of the food additive regulations based on abandonment is not based on safety`。** FDA 同时**拒绝**设立任何 BPA 标识要求（78 FR 41840, Response to Comment 7），并**驳回**了 NRDC 要求全面禁止 BPA 用于食品包装的公民请愿（2012-03-30）。

> **⚠️ 这一条对委托方的文案有直接后果**：既然美国的移除**不是安全性结论**，那么把 `BPA-free` 当作**安全声称**来用（如 §10.1 那条 `BPA-free, food-grade materials: Safe for both mother and baby.`）在法源上是**双重错位** —— 既不是法定认证，也不代表监管机构认定 BPA 不安全。`BPA-free` 只能作为**成分事实**陈述，不能承载安全结论。

可以确定的是（基于本次调研取得的相邻证据）：

1. **美国没有普遍的「母婴产品必须 BPA-free」的强制要求。** 若存在这样的强制要求，它必然出现在 21 CFR 或 CPSIA 中；本次调研在 21 CFR 177 与装置法规中均**未找到**此类条款。
2. **`BPA-free` 的可核查性来自检测报告，不是来自法规。** 因此它属于「客观可核查事实」（如 §9.4 所判），但**不是「法定术语」**。
3. **EU 侧**：**已取得** Commission Regulation (EU) 2024/3190 原文，且发现 **Reg (EU) 2018/213 已被其 Art. 13 废止**。欧盟的 BPA 规则比美国严格得多 —— 详见下方 **§10.2b**。

**竞品实证**：Medela、Willow、BabyBuddha、Momcozy 都在用 BPA-free 类表述，但措辞不同：

| 品牌 | 逐字文案 | 措辞强度 |
|---|---|---|
| Medela | `Closed system with BPA-free construction` | 结构 + 材料 |
| BabyBuddha | `BPA-free parts that come into contact with breast milk`；`BPA‑free and made with baby‑safe materials` | **限定到接触部位**（最精确） |
| Willow | `made without BPA`；`24 BPA-free 4 oz. Milk Bags` | **用 "without" 而非 "free"**（更保守） |
| **Momcozy** | `BPA-free, food-grade materials: **Safe for both mother and baby.**` | ⚠️ **加了一个全称安全断言** |

> **`made without BPA` vs `BPA-free` 的区别值得注意**：Willow 选择 "made without"，避免了 "free" 这个词可能被解读为「绝对无 BPA」（检测限以下不等于零）。**这是一个可以写进改写建议库的措辞级技巧。**

### 10.2b 欧盟 BPA —— **(EU) 2024/3190 已生效，且 2018/213 已被废止**（美国口径不能平移到欧盟）

**法源 —— Commission Regulation (EU) 2024/3190（逐字）**

> **Commission Regulation (EU) 2024/3190 of 19 December 2024** on the use of bisphenol A (BPA) and other bisphenols and bisphenol derivatives with harmonised classification for specific hazardous properties in certain materials and articles intended to come into contact with food, **amending Regulation (EU) No 10/2011 and repealing Regulation (EU) 2018/213**
>
> **Article 3 — Prohibition of the use of BPA**
> 1. **The use of BPA and its salts in the manufacture of food contact materials and articles referred to in Article 1(2) and the placing on the Union market of food contact materials and articles manufactured using BPA, is prohibited.**
> 2. By way of derogation from paragraph 1, BPA and its salts may be used in the manufacture of food contact materials and articles for a specific application set out in **Annex II**, subject to the restrictions laid down therein.
>
> **Article 1(2)** —— 适用材质为：`(a) adhesives; (b) rubbers; (c) ion-exchange resins; (d) plastics; (e) printing inks; **(f) silicones**; and (g) varnishes and coatings.`
>
> **Article 13 — Repeal**：`Regulation (EU) 2018/213 is repealed.`

- CELEX：**32024R3190**；OJ L 系列 **2024/3190**，2024-12-31 公布
- 本地证据：`_evidence/R5/materials/32024R3190.{txt,xhtml}`

**⚠️ 第一条给规则库的更正**：**不要引用 Reg (EU) 2018/213 作为现行依据** —— 它已被 Art. 13 明文废止。任何引用 2018/213 的合规文档或规则条目都需要改指向 2024/3190。**注意 `silicones` 被 Art. 1(2)(f) 明确列入适用材质**，这与美国侧（§177.1580 只管 polycarbonate、不管 silicone）形成鲜明对比。

**时间表（逐字核对）**：

| 节点 | 日期 | 依据 |
|---|---|---|
| 生效 | 公布后第 20 日 → **2025-01-20** | Art. 14（`shall enter into force on the twentieth day following that of its publication`） |
| **重复使用**最终食品接触制品**首次投放市场**的截止 | **2026-07-20** | Art. 12(1) |
| 已在市场上的重复使用制品可继续流通至 | **2029-01-20** | Art. 12（其余款；**本次已核对到 Art. 12(1)，(2) 起的日期需补充确认，见 §12 G8b**） |
| 一次性制品投放市场截止 | 2026-07-20（特定品类 2028-01-20） | Art. 11(1)(2) |

**Annex II 的豁免与本品类无关**：Annex II 仅授权两类特定应用 —— ①容量 >1,000 升的自支撑制品上的**液态环氧树脂**（varnishes and coatings）；②**聚砜过滤膜组件**（plastics），且均要求 `Migration into food shall not be detectable`。**吸奶器与储奶容器不落在任何一项豁免内。**

#### ⚠️ 一个必须由法律团队裁决的适用范围问题（本次调研的新发现）

**Reg (EC) No 1935/2004 Art. 1(2)** 的适用范围是：制品在其成品状态下 `(a) are intended to be brought into contact with food; or (b) are already in contact with food and were intended for that purpose; or **(c) can reasonably be expected to be brought into contact with food or to transfer their constituents to food under normal or foreseeable conditions of use.**`

**而 Art. 1(3) 的排除项只有三项**：`(a)` 古董；`(b)` 可食用涂层；`(c)` 固定供水设备。**没有医疗器械排除项** —— 本次已逐字核对 1935/2004 全文，`medical device` / `2017/745` / `MDR` 三个词在该条例中的出现次数均为 **0**。

**这意味着适用性回到一个事实判断**：

| 立场 | 论证 |
|---|---|
| **在范围内（保守解读）** | 吸奶器的**集乳瓶、储奶容器、奶瓶**在正常使用中**必然接触母乳**，且通常以「可储奶、可喂哺」宣传 —— 直接落入 Art. 1(2)(c) 的 `reasonably be expected to be brought into contact with food`。故其 **PC 材质部件**受 2024/3190 的 BPA 禁令约束；若含矽膠部件，则 Art. 1(2)(f) 的 `silicones` 亦在列。 |
| **不在范围内（宽松解读）** | 整套产品作为 **MDR (EU) 2017/745 下的医疗器械**受器械法规管辖；储奶瓶作为**器械附件**随器械一并监管，不按食品接触材料单独适用 1935/2004。 |

**本次调研未能找到任何一方的主管机关明确表述**（欧委会 FCM 指南与 MDCG 文件均未检索到吸奶器/储奶容器的边缘定性）。**因此这是一个真实开放的适用范围问题，不是本次能定论的。**

> **为什么它值得委托方立刻处理**：这不是文案问题，而是**产品合规问题**。委托方在欧盟有 **26 条法国广告在跑**（任务书 §二.D），若其储奶/集乳部件的材质受 2024/3190 约束，则需确认：①是否含 BPA 或 BPA 衍生单体；②是否符合 Art. 8 的**合规声明（declaration of compliance, Annex III）**要求。**建议动作：向代工厂索取各 milk-contact 部件的材质声明与 FCM 合规文件，并请法律团队就「储奶容器是否适用 1935/2004」出具意见。** 见 §12 G8b。
>
> **对文案的即时含义**：`BPA-free` 在欧盟的意义与美国不同 —— 美国是「不是法定要求」（§10.2），**欧盟是「正在成为法定要求」**。因此在欧盟站，`BPA-free` 正从**卖点**退化为**合规基线**；而 §10.1 那条 `BPA-free, food-grade materials: Safe for both mother and baby.` 的风险不降反升（合规基线 + 全称安全断言）。

### 10.3 LFGB —— 是德国食品饲料法典的**章节引用**，不是认证

**法源（德国）—— LFGB § 31 Übergang von Stoffen auf Lebensmittel（逐字，德文原文）**

> **§ 31 Übergang von Stoffen auf Lebensmittel**
> (1) Es ist verboten, Materialien oder Gegenstände im Sinne des § 2 Absatz 6 Satz 1 Nummer 1, die den in **Artikel 3 Absatz 1 der Verordnung (EG) Nr. 1935/2004** festgesetzten Anforderungen an ihre Herstellung nicht entsprechen, als Bedarfsgegenstände zu verwenden oder in den Verkehr zu bringen.
> (2) Das Bundesministerium wird ermächtigt, durch Rechtsverordnung mit Zustimmung des Bundesrates … vorzuschreiben, dass Materialien oder Gegenstände als Bedarfsgegenstände … nur so hergestellt werden dürfen, dass sie unter den üblichen oder vorhersehbaren Bedingungen ihrer Verwendung keine Stoffe auf Lebensmittel oder deren Oberfläche in Mengen abgeben, die geeignet sind,
> a) die menschliche Gesundheit zu gefährden,
> b) die Zusammensetzung oder Geruch, Geschmack oder Aussehen der Lebensmittel zu beeinträchtigen,
> …

**法源（德国）—— LFGB § 30 Verbote zum Schutz der Gesundheit（逐字，德文原文）**

> **§ 30 Verbote zum Schutz der Gesundheit**
> Es ist verboten,
> 1. Bedarfsgegenstände für andere derart herzustellen oder zu behandeln, dass sie bei bestimmungsgemäßem oder vorauszusehendem Gebrauch geeignet sind, die Gesundheit durch ihre stoffliche Zusammensetzung, insbesondere durch toxikologisch wirksame Stoffe oder durch Verunreinigungen, zu schädigen,
> 2. Gegenstände oder Mittel, die bei bestimmungsgemäßem oder vorauszusehendem Gebrauch geeignet sind, die Gesundheit durch ihre stoffliche Zusammensetzung … zu schädigen, als Bedarfsgegenstände in den Verkehr zu bringen,
> 3. Bedarfsgegenstände im Sinne des § 2 Absatz 6 Satz 1 Nummer 1 bei dem Herstellen oder Behandeln von Lebensmitteln so zu verwenden, dass die Bedarfsgegenstände geeignet sind, bei der Aufnahme der Lebensmittel die Gesundheit zu schädigen.

- URL：https://www.gesetze-im-internet.de/lfgb/__31.html、https://www.gesetze-im-internet.de/lfgb/__30.html
- 本地证据：`_evidence/R5/materials/LFGB_sec30_gesetze-im-internet_20260915.html`（1,163 字符）、`LFGB_sec31_gesetze-im-internet_20260915.html`（1,859 字符）

> **两个决定性事实**：
>
> 1. **LFGB § 31 没有建立任何"认证"。** 它是一条**禁令性规范**：不符合 Regulation (EC) No 1935/2004 Art. 3(1) 要求的材料**不得**作为 Bedarfsgegenstände（消费品/日用品）使用或投放市场。它是**转引条款**，把欧盟法规的要求接进德国法。
> 2. **因此「LFGB certified」不是任何人签发的证书。** 它实际上是「按 LFGB § 31（即 Reg 1935/2004 Art. 3）做了迁移测试并出具报告」的**行业惯例说法**。
>
> **对 Momcozy 的直接含义**：**Momcozy M9 页面写的 "FDA and LFGB certified" 在两端都有问题** —— ①"FDA certified" 对器械配件无依据（见 §7.3）；②"LFGB certified" 不是认证，正确表述应当是 `tested in accordance with LFGB § 31 / Regulation (EC) No 1935/2004 Art. 3`。**这一处需要整改。**
>
> **注意 LFGB § 31(1) 明确指向 Reg 1935/2004 Art. 3** —— 这给出了欧盟侧的正确引用路径。**本次已取得 Reg (EC) No 1935/2004 Art. 3 逐字原文**（`_evidence/R5/materials/32004R1935.txt`）：
>
> > **Article 3 — General requirements**
> > 1. Materials and articles, including active and intelligent materials and articles, shall be manufactured in compliance with good manufacturing practice so that, under normal or foreseeable conditions of use, they do not transfer their constituents to food in quantities which could: (a) endanger human health; or (b) bring about an unacceptable change in the composition of the food; or (c) bring about a deterioration in the organoleptic characteristics thereof.
> > 2. **The labelling, advertising and presentation of a material or article shall not mislead the consumers.**
>
> **Art. 3(2) 是欧盟侧直接约束「材质类安全词」的条款** —— 它是 UCPD 之外、**专门针对食品接触材料广告**的误导性禁令。委托方在欧盟使用 `food-grade silicone` / `BPA-free` / `LFGB certified` 这类材质声称时，**Art. 3(2) 比 UCPD 更贴近**（UCPD 管一般商业行为，Art. 3(2) 直接管 FCM 的 labelling / advertising / presentation）。

### 10.4 `FDA registered` vs `FDA cleared` 的机制差异（本节强化）

见 §3.4 法源 8。核心事实链：

1. **企业注册（establishment registration）是年度动作**：21 CFR 807.22(b)(1) —— 每年 10 月 1 日至 12 月 31 日。
2. **注册数据不表示 FDA 对器械做过任何评价**：FDA 官方页面 —— `does not denote approval, clearance, or authorization`。
3. **FDA 不签发注册证书**：FDA 官方页面 —— `The FDA does not issue any type of device registration certificates to medical device facilities.`
4. **器械 clearance（510(k)）与注册完全解耦**：一次 510(k) clearance 对应一个具体的器械/型号（K 号 + 器械名 + 规格），而注册只对应「一个 establishment 在卖哪些器械」。
5. **因此篡改 FDA cleared 与 FDA registered 的语义，构成 misbranding**：21 CFR 807.97。

**这条链在规则库里的作用**：把 `FDA registered` 从「安全词」移出（见 §9.4），并且**新增一条替换规则** —— 文案中若出现 `FDA registered`，应改写为**具体的** `FDA cleared (K######)`，或者删除 FDA 字样。

### 10.5 `hands-free` / `wearable` —— 无监管含义，但**在 Meta 上有平台含义**

这两个词本身描述产品形态，不涉及医疗声称，属结构描述类安全词（见 §9.4）。

**但见 §8.2(1)**：Meta 明文禁止 `Claims that results can be achieved solely by using wearable products`。**因此 `wearable` 一词与"结果型声称"组合时，在 Meta 平台上是一个独立的风险组合** —— 这是"词本身安全、组合后不安全"的又一个实例，也是规则库需要「组合规则」而不只是「词表」的直接证据。

### 10.6 本节的合规表述替换表

| ❌ 不可用/有风险 | ✅ 建议表述 | 依据 |
|---|---|---|
| `food-grade silicone` | `silicone meeting 21 CFR 177.2600 extractives limits` | 21 CFR 177.2600(e)(f) |
| `LFGB certified` | `tested in accordance with LFGB § 31 / Regulation (EC) No 1935/2004 Art. 3` | LFGB § 31(1) |
| `FDA certified`（材料/配件） | `made with materials tested to FDA food-contact requirements`，或删除 FDA 字样 | 21 CFR 807.97（精神）|
| `FDA registered` | `FDA cleared (K######)`（须能对应 K 号）或删除 | 21 CFR 807.97；807.22 |
| `BPA-free` + `Safe for both mother and baby` | `made without BPA`（限定到接触部位） | Willow 的措辞实践 |
| `hospital-grade`（裸用/写进产品名） | `hospital-strength suction up to N mmHg`（锚定数值） | 见 §7.2 卖点 F |

### 10.7 本节缺口

**未核实项**（已在 §12 列出）：
- ~~FDA 对 BPA 的官方立场原文，以及 BPA 移除的 Federal Register 引用~~ —— **已补齐**：法源为 **21 CFR 177.1580(d)**（逐字）+ **77 FR 41899 / 78 FR 41840**，见 §10.2
- ~~Commission Regulation (EU) 2018/213 与 **(EU) 2024/3190** 原文与生效/过渡日期~~ —— **已取得（见下方 §10.2b），本项关闭**
- ~~Regulation (EC) No 1935/2004 Art. 3 的逐字原文~~ —— **已取得**，见 §10.3 注（含 Art. 3(2) 的误导性禁令）
- **ISO 13485 / ISO 9001 / IEC 60601-1 / ISO 10079-1 的官方适用范围文本** —— 这些标准的正文在 iso.org 与 webstore.iec.ch 均需付费/JS 才可访问，本次仅取到页面骨架（**G9**）
- FDA Food Contact Substance Notification (FCN) 程序的官方说明（**G8**，仍未取得）
- **各 milk-contact 部件（集乳瓶/储奶容器/矽膠件）是否适用 Reg (EC) 1935/2004 与 (EU) 2024/3190** —— 适用范围未决，见 **§10.2b** 与 **§12 G8b**

**在补齐之前，规则库不应把上述任何一项写成"符合 XX 标准"。**

---

## 十一、证据清单

### 11.1 法规与官方文件（全部为逐字引用来源）

| # | 文件 | 条款 | URL | 本地路径 |
|---|---|---|---|---|
| 1 | 21 CFR 884.5160 Powered breast pump | §884.5160(a)(b) | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-884/subpart-F/section-884.5160 | `_evidence/R5/fda/ecfr-884-5160.html`、`.xml` |
| 2 | 21 CFR 884.5150 Nonpowered breast pump | §884.5150(a)(b) | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-884/subpart-F/section-884.5150 | `_evidence/R5/fda/ecfr-884-5150.html`、`.xml` |
| 3 | 21 CFR 807.81 When a premarket notification submission is required | §807.81(a)(3)(ii) | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-807/subpart-E/section-807.81 | `_evidence/R5/fda/ecfr-807-81.xml` |
| 4 | 21 CFR 807.97 Misbranding by reference to premarket notification | §807.97（全文） | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-807/subpart-E/section-807.97 | `_evidence/R5/fda/sec-807.97.xml` |
| 5 | 21 CFR 807.22 Times for establishment registration | §807.22(a)(b)(1) | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-807/subpart-B/section-807.22 | `_evidence/R5/fda/sec-807.22.xml` |
| 6 | 21 CFR 807.20 Who must register | §807.20(a) | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-807/subpart-B/section-807.20 | `_evidence/R5/fda/sec-807.20.xml` |
| 7 | 21 CFR 807.65 Exemptions for device establishments | §807.65(c) | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-807/subpart-D/section-807.65 | `_evidence/R5/fda/sec-807.65.xml` |
| 8 | 21 CFR 801.4 Meaning of intended uses | §801.4（全文） | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-801/subpart-A/section-801.4 | `_evidence/R5/fda/ecfr-801-4.xml`、`.html` |
| 9 | 21 CFR 801.5 Medical devices; adequate directions for use | §801.5(a) | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-801/subpart-A/section-801.5 | `_evidence/R5/fda/sec-801.5.xml` |
| 10 | 21 CFR 801.6 Medical devices; misleading statements | §801.6（全文） | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-801/subpart-A/section-801.6 | `_evidence/R5/fda/sec-801.6.xml` |
| 11 | 21 CFR 814.80 General（PMA 情形） | §814.80（全文） | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-814/subpart-B/section-814.80 | `_evidence/R5/fda/ecfr-814-80.xml` |
| 12 | 21 CFR 201.128 Meaning of "intended uses"（药品对照） | §201.128 | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-I/part-201/subpart-A/section-201.128 | `_evidence/R5/fda/sec-201.128.xml` |
| 13 | FDA *General/Specific Intended Use — Guidance for Industry* | CDRH, 1998-11-04, Docket FDA-2020-D-0957 | https://www.fda.gov/regulatory-information/search-fda-guidance-documents/generalspecific-intended-use-guidance-industry | 见 §3.3（web_fetch 全文已记录） |
| 14 | FDA *Are There "FDA Registered" or "FDA Certified" Medical Devices?* | 全文 | https://www.fda.gov/medical-devices/consumers-medical-devices/are-there-fda-registered-or-fda-certified-medical-devices-how-do-i-know-what-fda-approved | 见 §3.4（web_fetch 全文已记录） |
| 15 | openFDA Device Classification API | product_code HGX / OHH / HGY / PWA | https://api.fda.gov/device/classification.json | `_evidence/R5/fda/openfda-breastpump.json` |
| 16 | openFDA 510(k) API | Momcozy 13 项 clearance | https://api.fda.gov/device/510k.json?search=product_code:HGX | `_evidence/R5/fda/openfda-momcozy.json`（查询结果见 §9.1/R5-C5 表） |
| 17 | Regulation (EU) 2017/745 (MDR) | Art. 2(1)、Art. 7 | https://publications.europa.eu/resource/celex/32017R0745 | `_evidence/R5/eu/mdr-2017-745-en.xhtml`（1.7 MB）、`.txt`（650 K 字符） |
| 18 | MDCG 2021-24 Rev.1 | Rule 9、Rule 12 | https://health.ec.europa.eu/document/download/cbb19821-a517-4e13-bf87-fdc6ddd1782e_en | `_evidence/R5/eu/mdcg-2021-24-rev1.pdf`（59 页）、`.txt` |
| 19 | Regulation (EC) No 1924/2006（consolidated 2014-12-13） | Art. 1(2)、Art. 2(2)(1)(4)(5)(6)、Art. 3、Art. 6(1)、Art. 11、Art. 12、Art. 13(1)、Art. 14 | https://publications.europa.eu/resource/celex/02006R1924-20141213 | `_evidence/R5/eu/eurlex-02006R1924-20141213-consolidated.xhtml`、`.TEXT.txt` |
| 20 | Directive 2005/29/EC (UCPD, consolidated 2022-05-28) | Art. 6(1)(2)、Art. 7、Annex I §4/§7/§9/§13/§17 | https://publications.europa.eu/resource/celex/02005L0029-20220528 | `_evidence/R5/eu/eurlex-02005L0029-20220528-ucpd-consolidated.xhtml`、`.TEXT.txt` |
| 21 | MHRA *Borderlines with medical devices and other products in Great Britain* | §1、§2、§3 | https://www.gov.uk/government/publications/borderlines-with-medical-devices/borderlines-with-medical-devices-and-other-products-in-great-britain（updated 29 June 2026） | `_evidence/R5/uk/mhra-borderlines-gb.html`、`.txt`（376 行） |
| 22 | MHRA *Regulating medical devices in the UK* | 过渡安排、注册要求 | https://www.gov.uk/guidance/regulating-medical-devices-in-the-uk（updated 20 February 2026） | `_evidence/R5/uk/mhra-ukca-timeline.html` |
| 23 | MHRA *Medical devices: conformity assessment and the UKCA mark* | UKCA/CE/CE UKNI | https://www.gov.uk/guidance/medical-devices-conformity-assessment-and-the-ukca-mark | `_evidence/R5/uk/mhra-devices-guidance-index.html` |
| 24 | FTC *Health Products Compliance Guidance* | p.13–15、p.42；Example 16/17/18/34/35/36；脚注 25/26/28/29/30/31/59 | https://www.ftc.gov/business-guidance/resources/health-products-compliance-guidance | `_evidence/R5/ftc/ftc-health-products-compliance-guidance-2022-12.pdf`、`.PDFTEXT.txt`（1,409 行） |
| 25 | FTC *Policy Statement Regarding Advertising Substantiation* | 全文（1984-11-23；appended to *Thompson Medical*, 104 F.T.C. 648, 839） | https://www.ftc.gov/legal-library/browse/ftc-policy-statement-regarding-advertising-substantiation | `_evidence/R5/ftc/ftc-policy-statement-advertising-substantiation-1984.CLEAN.txt` |
| 26 | FTC *Policy Statement on Deception* | 全文（1983-10-14；appended to *Cliffdale Associates*, 103 F.T.C. 110, 174；脚注 31/32/33/34/35/36/37/38/40/42） | https://www.ftc.gov/legal-library/browse/ftc-policy-statement-deception | `_evidence/R5/ftc/ftc-deception-policy-statement-1983.pdf`、`.txt`（15 页） |
| 27 | 16 CFR Part 255 Endorsement Guides | §255.1 / §255.2 / §255.5 | https://www.ecfr.gov/current/title-16/chapter-I/subchapter-B/part-255 | `_evidence/R5/ftc/ecfr-16cfr255-endorsement-guides.TEXT.txt`、`.TEXT.txt`（平行分项抓取） |
| 28 | EC *Guidance on the implementation of Regulation (EC) No 1924/2006* | Standing Committee on the Food Chain and Animal Health, 2007-12-14；§III.2 claim classification | ec.europa.eu | `_evidence/R5/eu/ec-guidance-1924-2006-standing-committee-2007-12-14.pdf`、`.PDFTEXT.txt` |
| 29 | **Meta Advertising Standards — Health and Wellness** | 全文（含 `Claims that results can be achieved solely by using wearable products`） | https://transparency.meta.com/policies/ad-standards/restricted-goods-services/health-wellness/（change log: **Jul 22, 2026**） | `_evidence/R5/platforms/meta-health-wellness.html`、`.txt`（191 行） |
| 30 | **Meta Advertising Standards — Privacy Violations and Personal Attributes** | 全文（含 `physical or mental health (including medical conditions)`、`Imply knowledge of Medical information`） | https://transparency.meta.com/policies/ad-standards/privacy-violations/personal-attributes/ | `_evidence/R5/platforms/meta-privacy-violations-personal-attributes.txt` |
| 31 | **Meta Advertising Standards — Misinformation** | 全文 | https://transparency.meta.com/policies/ad-standards/unacceptable-content/misinformation/ | `_evidence/R5/platforms/meta-unacceptable-content-misinformation.txt` |
| 32 | **Meta Advertising Standards 索引与其余章节** | Ad Standards index / Intro / Drugs & Pharmaceuticals / Bodily Parts and Fluid / Objectionable Content / Prohibited Commercial Practices / IP | transparency.meta.com | `_evidence/R5/platforms/meta-*.html|.txt`（10 个） |
| 33 | **Google Ads Policy — Unreliable claims** | 全文（含 `Making inaccurate claims or claims that entice the user with an improbable result`、`Google Ads may defer to local regulatory guidelines for health-related claims`） | https://support.google.com/adspolicy/answer/15936857 | `_evidence/R5/platforms/google-unreliable-claims.html` |
| 34 | **Google Ads Policy — Misrepresentation** | 全文（含 Unacceptable business practices / Manipulated media / Clickbait ads 等子章节） | https://support.google.com/adspolicy/answer/6020955 | `_evidence/R5/platforms/google-misrepresentation.html` |
| 35 | **Google Ads Policy — Healthcare and medicines** | 全文 43,243 字符（含按国家/地区的允许矩阵；未含 medical device 专门条款） | https://support.google.com/adspolicy/answer/176031 | `_evidence/R5/platforms/google-healthcare-and-medicines.html` |
| 36 | Google Ads Policy — Editorial / Personalized advertising / Trademarks / Clinical trial recruitment / Restricted drug terms | 全文 | support.google.com/adspolicy | `_evidence/R5/platforms/google-*.html`（9 个） |
| 36b | **Amazon Ads — Stores creative acceptance policies** | 全文（正文 31,413 字符；含 §2.4 `Claims and comparative statements`：`We do not permit direct comparison to competitor brands.`、`dated within the previous 12-18 months`、§2.4.1 Warranty and guarantees、Australia locale 条款） | https://advertising.amazon.com/resources/ad-policy/en | `_evidence/R5/platforms/amazon-stores-creative-acceptance-policies.html` |
| 36c | Amazon Ads 政策其余页面（Sponsored Ads / DSP / general policies 等） | 部分取得（HTML 较大，未逐页确认正文完整度） | advertising.amazon.com/resources/ad-policy | `_evidence/R5/platforms/amazon-sponsored-ads-additional-policies.html` 等 |
| 37 | **TikTok Advertising Policies — Misleading and false content** | 全文（Last updated **2026-04**；含 `Comparative claims may be allowed, subjected to the provision of evidence or clear disclaimer(s)`） | https://ads.tiktok.com/help/article/tiktok-ads-policy-misleading-and-false-content | `_evidence/R5/platforms/tiktok-misleading-and-false-content.txt`（6,702 字符） |
| 38 | **TikTok Advertising Policies — Healthcare and Pharmaceuticals** | 全文（Last updated **2026-08**；115,731 字符；含 60+ 国别 regulatory 矩阵、美国站 medical devices 18+ 要求、4 国"medical devices 禁前后对比"） | https://ads.tiktok.com/help/article/tiktok-ads-policy-healthcare-pharmaceuticals | `_evidence/R5/platforms/tiktok-healthcare-pharmaceuticals.txt` |
| 39 | **TikTok Advertising Policies — Weight Management and Body Image** | 全文（Last updated **2026-09**） | https://ads.tiktok.com/help/article/tiktok-ads-policy-weight-management | `_evidence/R5/platforms/tiktok-weight-management.txt` |
| 40 | TikTok Advertising Policies — 其余 12 页 | 全文（Deceptive Practices / Misinformation / Ad Serving Policy / Other Products and Services / Adult Content / Dangerous Products / IP / Suicide and Self-Harm / Advertising Policies index / Ad review checklist[骨架] / Creative best practices[骨架] / Market-specific requirements[骨架]） | ads.tiktok.com/help/article/… | `_evidence/R5/platforms/tiktok-*.txt`（15 个，合计 198,080 字符） |
| 41 | **21 CFR 177.2600 Rubber articles intended for repeated use** | 全文（含 (e) 20 mg/in²、(f) 175 mg/in²、(h) 奶嘴排除） | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-177/subpart-C/section-177.2600 | `_evidence/R5/materials/ecfr-177-2600.xml` |
| 41b | **21 CFR 177.1580 Polycarbonate resins** | §177.1580(d)（逐字；含 `except in infant feeding bottles (baby bottles) and spill-proof cups` 与 `77 FR 41902, July 17, 2012` 修订记录） | https://www.ecfr.gov/current/title-21/chapter-I/subchapter-B/part-177/subpart-C/section-177.1580 | `_evidence/R5/materials/ecfr-177-1580-polycarbonate-resins.html` |
| 41c | **Commission Regulation (EU) 2024/3190（BPA 食品接触材料）** | Art. 1(2)（材质清单，含 `(f) silicones`）、**Art. 3(1) 禁令**、Art. 3(2) 与 Annex II 豁免、Art. 11/12 过渡、**Art. 13 废止 2018/213**、Art. 14 生效、Annex III 合规声明 | CELEX **32024R3190**；OJ L 2024/3190, 2024-12-31 | `_evidence/R5/materials/32024R3190.txt`、`.xhtml` |
| 41d | **Regulation (EC) No 1935/2004 Art. 3** | Art. 1(2)（适用判据）、Art. 1(3)（3 项排除，**无医疗器械排除**）、**Art. 3(2) 误导性禁令** | CELEX 32004R1935 | `_evidence/R5/materials/32004R1935.txt`、`.xhtml` |
| 41e | **77 FR 41899（2012-07-17，ACC 请愿）** | 全文（Rules and Regulations，pp. 41899–41902；FR Doc No: **2012-17366**）—— BPA 基材料从婴儿奶瓶/吸嘴杯经「废弃」程序移出 | federalregister.gov | `_evidence/R5/fda/fr-2012-17366.txt` |
| 41f | **78 FR 41840（2013-07-12，Markey 请愿）** | 全文（pp. 41840–41843；FR Doc No: **2013-16684**）—— 扩及婴儿配方粉包装 | federalregister.gov | `_evidence/R5/fda/fr-2013-16684.txt` |
| 41g | **FDA BPA 官方页面（消费者问答与食品接触应用两页）** | 逐字（含 `An amendment of the food additive regulations based on abandonment is not based on safety`） | fda.gov | `_evidence/R5/fda/bpa-qa.txt`、`bpa-fca.txt`、`bpa-main.txt` |
| 42 | **LFGB § 30 Verbot zum Schutz der Gesundheit** | 全文（德文原文） | https://www.gesetze-im-internet.de/lfgb/__30.html | `_evidence/R5/materials/LFGB_sec30_gesetze-im-internet_20260915.html` |
| 43 | **LFGB § 31 Übergang von Stoffen auf Lebensmittel** | 全文（德文原文；转引 Reg (EC) 1935/2004 Art. 3(1)） | https://www.gesetze-im-internet.de/lfgb/__31.html | `_evidence/R5/materials/LFGB_sec31_gesetze-im-internet_20260915.html` |
| 44 | LFGB 全文与其他条款（§2/§32/§33/§39/§58/§59） | 已抓取，本次未逐一引用 | gesetze-im-internet.de | `_evidence/R5/materials/LFGB_*.html` |
| 45 | ISO 13485 页 / IEC 60601-1 页 | **仅页面骨架**（Cloudflare 挑战页 / 需付费） | iso.org、webstore.iec.ch | `_evidence/R5/materials/iso13485_59752.html`（58 字符）、`iec60601-1_2610.txt` —— **未取得标准正文，见 §12 G9** |

### 11.2 竞品证据

| 品牌 | 页面数 | 本地路径 |
|---|---|---|
| **Medela** | 9 | `_evidence/R5/competitors/medela-*.txt`（9 个）+ `raw/*.html` |
| **Lansinoh** | 10 | `_evidence/R5/competitors/lansinoh-*.txt`（10 个）+ `raw/*.html` |
| **Medela + Lansinoh 汇总** | — | `_evidence/R5/competitors/FINDINGS-medela-lansinoh.md`（1,525 行 / 143 KB） |
| **Willow** | 21 | `_evidence/R5/competitors/ow-*.txt`、`live-*`、`willow-01..05-*.txt`、`_raw/ow-*.html` |
| **Elvie** | 11 | `_evidence/R5/competitors/elvie-01..05-*.txt`、`_raw/ev-*.html`、`_raw/ev-*.txt` |
| **Willow + Elvie 逐字引用库** | — | `_evidence/R5/competitors/QUOTE-BANK-byte-exact.txt`（**机器生成，零手工转写，byte-exact**，132 个标注引用块）+ `FINDINGS-willow-elvie.md`（397 行） |
| **Spectra** | 7 PDP + 5 collections + homepage + 全 47 products | `_evidence/R5/competitors/live-spectra-*.txt`、`cat-spectra-*.txt`、`spectra-pdp-verbatim.txt`、`spectra-category-homepage-verbatim.txt`、`spectra-KEYWORD-HUNT.txt`、`spectra-ALL-products-bodytext.txt` |
| **BabyBuddha** | 5 PDP + 3 collections + certifications 页 + homepage + 全 43 products | `_evidence/R5/competitors/live-babybuddha-*.txt`（含 `live-babybuddha-pages_certifications.txt`）、`babybuddha-pdp-verbatim.txt`、`babybuddha-KEYWORD-HUNT.txt`、`babybuddha-ALL-products-bodytext.txt` |
| **Momcozy（自身）** | 10 PDP + 6 collections + homepage + IBCLC 页 + 全 405 products + **3 个 Amazon US listing** | `_evidence/R5/competitors/live-momcozy-*.txt`、`cat-momcozy-*.txt`、`momcozy-pdp-verbatim.txt`、`momcozy-category-homepage-verbatim.txt`、`momcozy-KEYWORD-HUNT.txt`、`momcozy-CORE-PUMPS-bodytext.txt`、**`momcozy-amazon-us-listings.txt`** |
| **跨品牌关键词命中** | — | `_evidence/R5/competitors/KEYWORD-HITS-raw.txt`（254 KB）、`HUNT-ALL.txt`（66 KB） |
| **三方汇总报告** | — | `FINDINGS-medela-lansinoh.md`（1,525 行）、`FINDINGS-spectra-babybuddha-momcozy.md`（1,162 行）、`FETCH-LOG.txt` |

**Momcozy 亚马逊 ASIN 映射（来自 Momcozy 官网 "Buy from Amazon" 按钮，映射权威）**：M5=`B0FHQJWPTN`、M6=`B0BSVB77WS`、M9=`B0FWJNV7S8`、S9 Pro=`B0DLFKN6LL`、S12 Pro Quick=`B0D4QV8DSP`、Air 1=`B0FW4XC8MG`、Wellness 1=`B0G6417BM1`、**V1 Pro=`B0CZNQ7VH7`**、V2 Pro=`B0CZNTCFXX`。

**抓取方法注记（可复现性）**：`babybuddha.com` 是**待售的停放域名**（301 到 Afternic/GoDaddy），活跃品牌站是 `babybuddhaproducts.com` —— 后续任何人重跑此调研前须知。Amazon 对 `curl` 有 Akamai JS proof-of-work 拦截（`POST /_sec/verify?provider=interstitial`），改用 modsearch `read_page` 桥接获取；因会话地理定位为中国，亚马逊价格渲染为 CNY，**标题/bullet/结构化属性为美国站英文原文，不受影响，但价格不是 USD**。

### 11.3 本分片产出

**主文档**：`research/governance/R5-category-and-competitors.md`（本文件）

**证据目录**（`research/governance/_evidence/R5/`，合计 **698 个文件 / 210 MB**）：

| 子目录 | 文件数 | 体积 |
|---|---|---|
| `_evidence/R5/fda/` | 82 | 2.4 MB |
| `_evidence/R5/eu/` | 49 | 30.7 MB |
| `_evidence/R5/uk/` | 4 | 0.5 MB |
| `_evidence/R5/ftc/` | 27 | 16.0 MB |
| `_evidence/R5/competitors/` | 261 | 74.7 MB |
| `_evidence/R5/platforms/` | 194 | 75.3 MB |
| `_evidence/R5/materials/` | 80 | 10.0 MB |

**跨分项报告**（由并行分项作者产出，本文件的对应章节已引用其结论）：

| 文件 | 内容 | 对应章节 |
|---|---|---|
| `_evidence/R5/competitors/FINDINGS-medela-lansinoh.md` | Medela + Lansinoh 竞品逐字取证 | §7 |
| `_evidence/R5/competitors/FINDINGS-spectra-babybuddha-momcozy.md` | Spectra / BabyBuddha / Momcozy 竞品逐字取证 | §7 |
| `_evidence/R5/competitors/FINDINGS-willow-elvie.md` | Willow + Elvie 竞品逐字取证 | §7 |
| `_evidence/R5/competitors/QUOTE-BANK-byte-exact.txt` | 机器生成的逐字引文库（零手工转写） | §7、附录 B |
| **`_evidence/R5/FINDINGS-ftc-eu-law.md`**（130 KB / 1,068 行） | **FTC + EU 法源逐字取证**；33/33 引文经程序化回验；含 EU 注册库全量检索与 3 宗 FTC 执法案卷 | **§4.4、§6.1** |
| **`_evidence/R5/eu/eu-health-claims-register-*.{md,csv,json}`** | **EU 健康声称注册库全量数据集**（2,337 条）+ 泌乳专项检索结论 + 独立复核报告 + API 发现记录 | **§4.4 法源 20** |
| **`_evidence/R5/ftc/enforcement/`** | **3 宗 FTC 执法案卷原文**（NeuroMetrix / BASF-DIEM / Quincy Bioscience，各含 PDF + PDFTEXT） | **§6.1 法源 30b** |
| **`_evidence/R5/FINDINGS-platform-policies.md`**（128 KB / 1,715 行） | **四平台广告政策逐字取证**（Meta / Google / Amazon / TikTok，**64 页政策正文**）；含 §0.2 URL 失效核验、§2.0 Google answer ID 复用表、跨平台「反射句」对照、before/after 分歧与严重度梯度 | **§8.0、§8.2–§8.7** |
| **`_evidence/R5/platforms/`** | **191 个文件 / 90 MB**：85 份 HTML + 105 份文本提取，逐文件带 `TITLE / URL / FETCH_DATE=2026-09-15` 头；`_tools/` 内含可复用的 `fetch.sh`（代理 + curl）与 `render.py`（CDP 无头渲染） | **§8（全部）** |

---

## 十二、缺口清单

### 12.1 本次调研尝试过但未取得的关键项

| # | 缺口 | 尝试过什么 | 失败原因 | 对结论的影响 |
|---|---|---|---|---|
| **G1** | ~~**EU 是否存在针对泌乳/母乳/催乳的授权 health claim**~~ —— **已完整检索，本项关闭** | 绕开门户 SPA，直接调用 FIP 后端 API：`ec.europa.eu/food/food-feed-portal/**backend**/api/policy-items?foodDomain=nut&authorisationType=nut_auth`（`backend/` 段由 `assets/env-json-config.json` 的运行时 `core.base` 覆盖得到）。取回 **2,337 条**全量 claim（19,885,668 B JSON） | **已解决**。**结论：授权项为 0。** 全部泌乳类词汇（`lactation` 2 命中、`breast milk` 3、`breastfeed` 2、`milk secretion`/`mammary`/`nursing` 各 1）**授权的命中数一律为 0**；`milk production`、`milk supply`、`prolactin`、`galactagogue`、`let-down`、`lactogenesis`、`mammogenesis`、`human milk` **全库 0 命中** | **已关闭**。结论与陷阱说明见 **§4.4 法源 20**（含 silymarin POL-HC-6243 被 Reg (EU) No 666/2011 驳回的原文、以及「2 条授权 DHA 声称含 `breastfed` 但描述的是孩子发育、不可延伸」的警示）。**独立复核**：另一 agent 从原始 JSON 重算，四个计数逐项复现一致。注意口径：按 **claim status** 为 269 授权 / 按**法律依据**为 228，引用时须注明用了哪个。 |
| **G1b** | **EFSA *General scientific guidance for stakeholders on health claims applications*（EFSA J 2016;14(1):4367）** | 尝试取 `efsa.europa.eu` 与 Wiley DOI | **两者对非浏览器客户端均返回 Cloudflare 403**；该文亦不在 Europe PMC 开放获取库中（经 Europe PMC REST API 确认） | **中**。这是 EFSA 关于健康声称**通用科学要求**的权威文件（G1 里引用的是两份专项 2018 指南：EFSA J 2018;16(10):5434 肌肉功能与体能、EFSA J 2018;16(12):5136 抗氧化与心血管）。**若要论证「什么样的泌乳类证据 EFSA 会接受」，需要这一份。** 可用路径：机构 IP / 订阅访问，或 Europe PMC 之外的开放仓储。 |
| **G1c** | **欧委会关于「非食品类边缘产品」的范围指南** | 已取得 2007-12-14 常设委员会指南全文（14 页）并逐一核对 | **该 2007 指南中没有非食品边缘产品的讨论**；另在 `food.ec.europa.eu` 定位到 3 份后续 collective answer 文件，本次未下载 | **低**。不影响「吸奶器不是 food、Reg 1924/2006 不适用」的结论（该结论由 Art. 1(2) 文本直接支撑）。仅在需要欧委会**官方口径**确认「器械不适用 1924/2006」时才需要。 |
| **G2** | **EU 层面是否有对吸奶器的官方定性文件** | 检索 MDCG 指南、EC 医疗器械页面、Manual on Borderline and Classification | MDCG 2021-24 Rev.1 的示例清单里**没有 breast pump**；Manual on Borderline 未获取到 | **较高**。导致 §4.3 的分类结论（Class IIa / Rule 12）只能基于示例类比，**不能写成官方定性**。**这是一个应该在正式合规文档里标注为"待确认"的项。** |
| **G3** | **Momcozy W1（Wellness 1）对应的 FDA K 号** | 检索 openFDA `510k` product_code HGX 全量 250 条；检索 applicant 含 Momcozy/Root Innovation/Lutejiacheng | **13 项 Momcozy clearance 中，没有任何一项器械名包含 warm / massage / wellness**。检索到 **K260864 "Mother's Nature W1 Warming Wearable Breast Pump"**（applicant = Shenzhen TPH Technology Co., Ltd.，decision 2026-06-09，product_code HGX），器械名与申请人**均与 Momcozy 不同** | **最高**。这是本次调研发现的**唯一一个可能构成实质合规风险的具体项**。W1 页面自称 "FDA 510(k) Cleared"，但**未能核实对应 K 号**；且暖敷+按摩功能是否在已 clearance 的 intended use 范围内，**未能核实**。**建议立即由法律团队向 Shenzhen Root Innovation / 代工厂索取覆盖 W1 功能的 510(k) clearance 文件。** |
| **G4** | **510(k) summary 的 intended use 逐字文本** | 尝试 `accessdata.fda.gov/cdrh_docs/pdf25/K253946.pdf`、`pdf23/K230776.pdf`、`scripts/cdrh/cfdocs/cfPMN/pmn.cfm?ID=K253946` | FDA accessdata 与 fda.gov 对 `curl` 与 `web_fetch` 均返回 Akamai abuse-detection 404（`/apology_objects/abuse-detection-apology.html`） | **中等**。若能取到 K253946（S9 Pro/S12 Pro）与 K251394（BP223）的 510(k) summary，就能**逐字确定 Momcozy 的合法 intended use 边界**，从而把 H01/H02 的判定从"经验"变成"对照 IFU"。**这是最值得优先补的一项。** 替代路径：法律团队直接用 K 号向 FDA 申请 FOIA，或向代工厂索取。 |
| **G5** | **Medela / Lansinoh 的 Meta Ad Library 广告素材** | 未尝试（需交互式检索，受工具限制） | Meta Ad Library 需 JS 交互 | **中等**。导致无法证实「广告文案 vs 官网文案的实际差异幅度」。本次调研的**全部竞品证据均来自官网/落地页**，不代表其付费广告的用词。**§8 中"竞品在广告里功效密度更低"的说法是一个观察，不是已证实的事实，已在正文标注。** |
| **G6** | **Amazon listing 的 bullet points** | 抓取尝试返回 `amz_search.html`、`amz_test.html` 等（疑似验证页） | Amazon 反爬 | **中等**。Amazon 是 Momcozy 的主要销售渠道，其 listing 文案的合规约束（A9 算法下的关键词密度 vs 合规表达）与官网不同。**本次未取得任何 Amazon listing 原文。** |
| **G7a** | ~~**TikTok 平台政策原文**~~ —— **已补齐，本项关闭** | 改走服务端渲染的 `ads.tiktok.com/help/article/<slug>`（`/i18n/help/` 为 JS 空壳）；取得 **15 页正文 / 198,080 字符**，抓取日 2026-09-15 | **已解决**。其中 *Healthcare and Pharmaceuticals*（115,731 字符，2026-08 版）、*Weight Management and Body Image*（2026-09 版）、*Misleading and false content*（2026-04 版）三页与本品类直接相关 | **已关闭**。结论见 §8.5，含一条平台专属硬约束（美国站 medical devices 要求 18+ 定向）与一条 `平台×国家` 联合键实证（法国/黎巴嫩/卡塔尔·南非·阿联酋/土耳其 4 组市场对 medical devices 禁前后对比，**美国不在其列**）。仅 3 页（ad-review-checklist / creative-best-practices / market-specific-requirements）仍为骨架，不影响上述结论。 |
| ~~**G7b**~~ | ~~**Amazon 平台政策原文（仍未取得）**~~ —— **已被下一行的 G7b 取代（本行为首轮取证记录，保留以备追溯）** | ~~`_evidence/R5/platforms/amazon-*.html` 全部 7 个 Seller Central 文件只渲染出约 1,894 字符骨架~~；首轮只确认 **Stores creative acceptance policies**（`advertising.amazon.com/resources/ad-policy/en`）为服务端渲染 | **Seller Central 帮助页 `sellercentral.amazon.com/help/hub/reference/external/G…` 为登录墙**（此结论在第二轮取证中**依然成立**）。**当时的影响判断「Amazon 侧仍缺」已被第二轮推翻** | ~~**高**~~ → 见下一行。**首轮判断"§8.4 因此仍只有间接结论"已被否决**：第二轮取得 Amazon Ads 公开面 15 页，其中 `Claims and substantiation`、`Healthcare products and services`、`Stores creative acceptance policies` 三页**直接给出了本品类的关键结论**（含 `Breast Pump` 明文列入 Category 1、对比禁令、举证要求）。**保留本行是为了留下"判断曾经偏差"的记录。** |
| **G7b** | **Amazon 平台政策原文** —— **已大幅补齐（本项降级）** | 补取路径：公开 **Amazon Ads** 面（`advertising.amazon.com/help/<ID>` 与 `/resources/ad-policy/<完整 slug>`）。本次取得 **15 页**，含 `Claims and substantiation`、`Healthcare products and services`、`Baby formula and feeding accessories`、`Prohibited products and services across all supply`、`General requirements`、`Stores creative acceptance policies` | **Seller Central 帮助页（`sellercentral.amazon.com/help/hub/reference/external/G…`）仍为登录墙**（每页仅约 1,847 字符通用外壳） | **高 → 中（已降级）**。**关键问题已被公开面回答**：① 吸奶器明文列入 **Category 1（低敏感度：Generally allowed）**——投放资格无问题；② `We do not permit direct comparison to competitor brands.`——**H08 在 Amazon 上直接闭环**；③ `Regulatory endorsement claims on healthcare products.`——**"FDA approved"/"clinically proven" 在 Amazon 上最硬**。**仍缺**：Conditional products、Restricted products、medical devices / FDA-cleared devices 规则、Product detail page 规则、A+ Content / Brand Registry、Baby 类目风格指南（均需已登录卖家账号或 SP-API 文档） |
| **G20** | **Meta「About ads that use health-related data」帮助文章** | 枚举 Meta Business Help Center 候选文章 ID（3 个）并渲染；尝试枚举全部 57 个 `/policies/*` 与 44 个 `/ad-standards/*` | Meta Business Help Center 对 curl 返回 **HTTP 400**；3 个候选 ID 渲染出的是**别的文章**；**无搜索 API 可用**（Firecrawl 429 / Exa 未配置），无法定位正确 ID | **中**。**已确立一条实质性的否定结论：Meta 不发布独立的 "Data and Privacy" 或 "Health data" 广告标准**（已由 57 + 44 个 URL 全量枚举 + 404 探测证实）。Meta 把"广告用健康数据"放在 **Advertising Standards 之外**（Data Policy / Business Tools Terms，且 health **不是** Special Ad Category）。**因此 §8.2 的结论不依赖这篇文章**，缺口仅影响"定向与数据使用"这一非文案层面 |
| **G21** | **Amazon 保健产品分级表的第三列（逐档 supply 专属限制正文）** | 已取得 Category 1/2/3 的**档次名与品类成员**（逐字），但第三列在 DOM 中渲染为空单元格 | 页面渲染问题（该表格列未输出内容）；`Homepage / Fire Devices` 等供给面限制只在 `Baby formula` 页以文字形式出现 | **低**。`Category 1: Generally allowed` 已足够支撑"投放资格无问题"的结论；缺口仅影响"哪些供给面受限"的细节 |
| **G8** | **材料类法规原文** —— **大部分已取得，本项基本关闭** | **已取得**：21 CFR 177.2600（含 (e)(f) 萃取限值与 (h) 奶嘴排除）、**21 CFR 177.1580(d)**（BPA/PC 用途排除）、**Reg (EU) 2024/3190**（含 Art. 1(2)、Art. 3、Art. 11、Art. 12(1)、Art. 13、Annex II/III）、**Reg (EC) 1935/2004 Art. 3**、LFGB § 30/§ 31 德文原文。**未取得**：FDA 自己的 BPA 立场页面（Akamai）、FDA FCN 程序说明、**Reg (EU) 2024/3190 Art. 12(2) 起的完整过渡日期** | 成功路径：**eCFR 需 `-L` 跟随 302 + 完整 UA + 本地代理**（`curl` 直连会拿到 302/空响应）；EUR-Lex 走 CELLAR；`fda.gov` 全站 Akamai | **大幅降低**。§10.1/§10.2/§10.2b/§10.3 现有完整法源链。**剩余缺口很小**，其中仅 Art. 12(2) 日期为需补的细节（见 G8b） |
| **G8b** | **吸奶器 milk-contact 部件是否适用 Reg (EC) 1935/2004 与 (EU) 2024/3190（适用范围未决）** | 逐字核对 1935/2004 Art. 1(2)（三条适用判据）与 Art. 1(3)（**仅 3 项排除，无医疗器械排除**）；确认 2024/3190 全文 **0 次**提及 `medical device` / `2017/745` / `MDR`；检索欧委会 FCM 指南与 MDCG 文件 | **无主管机关明确表述**。1935/2004 与 MDR 2017/745 的边界文件未涵盖吸奶器/储奶容器 | **高（本次新增的最高优先项之一）**。储奶容器在正常使用中**必然接触母乳**，且通常以「可储奶」宣传，落在 Art. 1(2)(c)；但产品整体受 MDR 管辖。**两种解读都会导致不同的合规义务**：若适用，则需 BPA 合规 + **Art. 8 合规声明（Annex III）**。**这不是文案问题，是产品合规问题。** 建议：向代工厂索取材质声明 + 法律团队出具意见。见 §10.2b |
| **G9** | **ISO 13485 / ISO 9001 / IEC 60601-1 / ISO 10079-1 的官方适用范围文本** | 抓取 iso.org 与 webstore.iec.ch 页面 | **`iso13485_59752.html` 仅 58 字符，内容为 `Just a moment... Enable JavaScript and cookies to continue`（Cloudflare 挑战页）**；IEC webstore 页只渲染出导航骨架 | **中**。**在这几项补齐前，规则库不应把任何标准号写成"符合"。** 见 §10.7 |
| **G10** | **加拿大市场（14 条在跑广告）的监管定性** | **未调研** | 明确超出 R5 分片边界（任务书只指定美国/欧盟/英国） | **中高**。Momcozy 有 14 条广告在加拿大跑，**加拿大 Medical Devices Regulations (SOR/98-282) 有独立的 Class I–IV 分法与许可证要求，且对健康声称的举证标准与 FTC 不同。这是一个真实的规则库空白。** |
| **G11** | ~~**FTC 针对「clinically proven」的具体执法案例原文**~~ —— **已取得 3 份案卷原文，本项关闭** | `_evidence/R5/ftc/enforcement/`：**NeuroMetrix**（1:20-cv-10428-FDS，器械）、**BASF/DIEM**（C-4744 / C-4745）、**Quincy Bioscience / Prevagen**（1:17-cv-00124）的 complaint 与 order 原文（各含 PDF + PDFTEXT） | **已解决**。**NeuroMetrix 是器械类先例**，其被禁广告词 `FDA cleared` + `doctor recommended` + `clinically proven` + `100% drug free` 与吸奶器行业话术几乎逐项对应 | **已关闭**。逐字引用与判定子规则见 **§6.1 法源 30b**。**两项衍生结论**：① Quincy ¶28–29 表明**「做过一项 RCT」不是抗辩** —— FTC 攻击的是该 RCT **未在预设主要终点达到显著**、且被告做了 30+ 次事后分析，故 H03 应增加「预设主要终点 + 达到显著」子条件；② **未发现任何 FTC 吸奶器/哺乳类执法案件**，不得凭空援引。**仍缺**：POM Wonderful Commission Opinion（155 F.T.C. 1 (2013)）原文 —— 该案仍是通过 HPCG 脚注间接引用。 |
| **G12** | **Elvie "quietest" 脚注 ¹ 的具体内容** | 未抓取到该脚注的正文 | 抓取范围限制 | **低**。不影响结论。 |
| **G13** | **Medela 各引用的具体研究样本量** | 抓取方自陈：「sample size stated for only 2 of ~27 citations」 | 官网未披露 | **低—中**。Medela 引用了 27 处但只披露 2 处样本量。**这本身是一个可用的竞品弱点观察**，但不影响规则库设计。 |
| **G14** | **"FDA certified" 的实际竞品使用样本** | 在 7 品牌语料里实测到 **1 处**：Momcozy M9 的 `"FDA and LFGB certified"`（材料级） | — | **已部分解决**。H06 正则应兼容 "FDA **and LFGB** certified" 这类插词语序（见 §9.6 第 1 项） |
| **G15** | **委托方 Meta 广告后台的实际年龄定向配置** | 未接触 | 需后台权限 | **中**。Meta 健康类政策要求 `must be targeted to people at least 18 years or older`（§8.2(1)）。**这是一个配置项核对，不是政策问题**，委托方可自行完成 |
| **G16** | **吸奶器是否需要在 Google Ads 侧申请医疗健康认证** | 已取到 Google `Healthcare and medicines` 政策全文（43,243 字符，含按国家矩阵），但**未能定位到针对 "medical device" 的专门条款** | 该页以在线药房、远程医疗、处方药、成瘾服务为主 | **中高**。这是一个**操作问题**（需向 Google 代表确认），不是可以通过读政策解决的问题。见 §8.3(2) |
| **G17** | ~~**FDA 对 BPA 的官方立场原文**~~ —— **实质已解决**（引文类型已替换） | `fda.gov` 正文页对 `curl`/`web_fetch` 均返回 **Akamai 拦截**；但 FDA 的**规则文本**与其**公告引用**改由 **eCFR（21 CFR 177.1580(d)）** 与 **Federal Register（77 FR 41899 / 78 FR 41840）** 取得 | **已解决**。`fda.gov` 的 sitemap.xml **不受 Akamai 拦截**；且委派分项最终**取得了 FDA 的 BPA 页面正文**（`_evidence/R5/fda/bpa-qa.txt` 等 3 份）与两份 Federal Register 原文 | **已关闭（部分）**。§10.2 现在引用的是**规则文本与 FR 公告**，比引用 FDA 网站文案更强。**仍缺**：FDA BPA 科普页原文与「FDA 不签发注册证书」页原文（后者在 §3.4 已通过二手转述引用，若要逐字仍需补） |
| **G18** | **Amazon A+ / Product description 模块正文** | 抓取截断在 50k 字符；模块以图片为主 | 抓取限制 | **低**。仅取到模块标题 |
| **G19** | **BabyBuddha K151284 的 FDA 510(k) 记录** | 未取到 | `accessdata.fda.gov` Akamai 拦截（同 G4） | **低**。openFDA `product_code:HGX` 全量 250 条中**未见 K151284**（该号段属 2015 年，可能已从当前 product code 归类中移出或属其他 code）。**这不影响 §7.3 的判定**（无论 K151284 是什么，用 "FDA approved" 描述一台 510(k) 器械都是 21 CFR 807.97 的 misbranding） |

### 12.2 本次调研**主动判定为无需调研**的项

- **吸奶器的 UL / ETL 认证** —— 属电气安全，与内容合规无直接关系。
- **FDA 对吸奶器的具体性能标准（performance standards）** —— 21 CFR 884.5160(b) 写的是 "Class II (performance standards)"，但本次**未查到**该品类已发布的具名 performance standard。这是**监管状态的观察**（该品类可能有标准未发布），不影响内容规则。
- **母乳库 / 捐赠母乳的监管** —— 与品牌内容输出无关。
- **FDA 对吸奶器的召回记录** —— 属产品质量，非内容合规。

---

## 附录 A：本分片的核心法条速查卡

供规则库 `legal_basis` 字段直接复制。

```
【美国】
21 CFR 884.5160     Powered breast pump → Class II（product code HGX，需 510(k)）
21 CFR 884.5150     Nonpowered breast pump → Class I（product code HGY，豁免 510(k)，限 ≤250 mmHg）
21 CFR 801.4        intended use = objective intent，可由 labeling claims / advertising matter / oral or written statements 确定
21 CFR 801.5        广告中提到的用途必须出现在 adequate directions 中
21 CFR 801.6        对另一器械的虚假或误导性陈述构成 misbranding                    ← H08/M06
21 CFR 807.81(a)(3)(ii)  intended use 重大变更需重新提交 510(k)                       ← H01/H02
21 CFR 807.97       510(k) clearance ≠ official approval；暗示 approval 构成 misbranding ← H06
21 CFR 807.22(b)(1) 企业注册为每年 10/1–12/31 的年度动作，与 clearance 无关            ← H06
21 CFR 814.80       广告不得超出 PMA 审批条件（吸奶器不适用，仅作原则对照）

【欧盟】
MDR (EU) 2017/745 Art. 2(1)    medical device 定义以 manufacturer's intended medical purpose 为前提
MDR (EU) 2017/745 Art. 7       器械广告误导性声称四项禁止（a/b/c/d）                 ← H01/H09
MDCG 2021-24 Rev.1 Rule 12     active device 移除体液 → Class IIa（示例含 Suction pump）
Reg (EC) 1924/2006 Art. 1(2)   适用范围限 "foods"——吸奶器不在范围内
Reg (EC) 1924/2006 Art. 6(1)   健康声称须基于 generally accepted scientific evidence      ← H02/H03
Reg (EC) 1924/2006 Art. 12(c)  个人医生/健康专业人士推荐一律禁止                       ← H04
UCPD 2005/29/EC Art. 6(1)(b)   产品主要特征（含测试结果）的误导 = 误导性行为           ← M03
UCPD 2005/29/EC Art. 7         误导性遗漏                                              ← U03
UCPD 2005/29/EC Annex I §4     虚假声称获公共机构批准 = per se unfair                  ← H06
UCPD 2005/29/EC Annex I §7     虚假限时 = per se unfair（注意 "Falsely" 限定）         ← M04
UCPD 2005/29/EC Annex I §13    仿冒误导
UCPD 2005/29/EC Annex I §17    虚假声称能治愈疾病 = per se unfair                      ← H01

【英国】
MHRA Borderlines §3    "breast pumps" 通常不是医疗器械；"breast pumps for treatment of inverted nipples" 是
MHRA Borderlines §2    medical purpose 由 labelling / IFU / promotional material 决定
UK MDR 2002            全器械需 MHRA 注册；境外制造商需指定 UK responsible person
UKCA / CE              GB 认可 CE 至 2026-06-30（MDR 器械）；NI 需 CE 或 CE UKNI

【FTC（非法条，但有执法效力）】
FTC HPCG 2022 p.13       健康相关 benefit 的 substantiation 需 RCT 级证据
FTC HPCG 2022 §1         声称的证据层级必须与实际持有的一致                    ← H03
FTC HPCG 2022 Example 18 "clinically tested" 本身即功效声称；测试对象须是产品本身
FTC HPCG 2022 Example 34 特定人群结论不得外推至一般人群
FTC 1984 Substantiation  "tests prove"/"studies show"/"doctors recommend" 属 express substantiation claim ← H03/H04
FTC 1984 Substantiation  合理依据六因素（claim type / product / 后果 / 真实声称收益 / 举证成本 / 专家标准）
FTC Deception 1983       欺骗三要件：likely to mislead + reasonable consumer + material
FTC Deception 1983 脚注42 puffery：主观声称不需 documentation                      ← 安全词判据
FTC Deception 1983 脚注38 pro forma disclaimers 不能治愈欺骗性信息                  ← "豁免词"字段
FTC Deception 1983       "the entire mosaic, rather than each tile separately"      ← 语境检测的法源
FTC Deception 1983       对特定受众按该群体中合理成员的视角判断                   ← 易感受众维度
```

---

## 附录 B：关键「逐字引用」索引（供交叉核对）

按出现顺序列出本文引用的所有英文逐字原文及其出处小节，便于复核。

| # | 逐字片段（摘要） | 出处 | 本文位置 |
|---|---|---|---|
| 1 | "A powered breast pump in an electrically powered suction device used to express milk from the breast." | 21 CFR 884.5160(a) | §3.1 |
| 2 | "Class II (performance standards)." | 21 CFR 884.5160(b) | §3.1 |
| 3 | "does not develop more than 250 mm Hg suction" | 21 CFR 884.5150(b) | §3.1 |
| 4 | "This type of convenience kit … does not require a premarket notification (510(k)) to market" | openFDA device_name = Breast Pump Kit | §3.2 |
| 5 | "A major change or modification in the intended use of the device." | 21 CFR 807.81(a)(3)(ii) | §3.3 |
| 6 | "refer to the objective intent of the persons legally responsible for the labeling of an article" | 21 CFR 801.4 | §3.3 |
| 7 | "This objective intent may, for example, be shown by labeling claims, advertising matter, or oral or written statements" | 21 CFR 801.4 | §3.3 |
| 8 | "Identification of an effect on clinical outcome" | FDA General/Specific Intended Use, therapeutic levels 5 | §3.3 |
| 9 | "Those specific indications for use that presume a specific clinical outcome" | 同上，outside general use 清单 | §3.3 |
| 10 | "does not in any way denote official approval of the device." | 21 CFR 807.97 | §3.4 |
| 11 | "Any representation that creates an impression of official approval … is misleading and constitutes misbranding." | 21 CFR 807.97 | §3.4 |
| 12 | "Such words may be used to mislead you. … The short answer is NO." | FDA 消费者页面 | §3.4 |
| 13 | "does not denote approval, clearance, or authorization" | FDA 消费者页面 | §3.4 |
| 14 | "The FDA does not issue any type of device registration certificates to medical device facilities." | FDA 消费者页面 | §3.4 |
| 15 | "misbrand the device in violation of the Federal Food, Drug, and Cosmetic Act." | FDA 消费者页面 | §3.4 |
| 16 | "Annual registration shall take place during the period beginning on October 1 and ending on December 31 of each fiscal year" | 21 CFR 807.22(b)(1) | §3.4 |
| 17 | "Statements of all conditions, purposes, or uses for which such device is intended, including … in its oral, written, printed, or graphic advertising" | 21 CFR 801.5(a) | §3.5 |
| 18 | "a false or misleading representation with respect to another device or a drug or food or cosmetic." | 21 CFR 801.6 | §3.5 |
| 19 | "advertised in a manner that is inconsistent with any conditions to approval" | 21 CFR 814.80 | §3.5 |
| 20 | "intended by the manufacturer to be used … for one or more of the following specific medical purposes" | MDR Art. 2(1) | §4.1 |
| 21 | "investigation, replacement or modification of the anatomy or of a physiological or pathological process or state" | MDR Art. 2(1) | §4.1 |
| 22 | "ascribing functions and properties to the device which the device does not have" | MDR Art. 7(a) | §4.2 |
| 23 | "suggesting uses for the device other than those stated to form part of the intended purpose for which the conformity assessment was carried out" | MDR Art. 7(d) | §4.2 |
| 24 | "• Suction pump" | MDCG 2021-24 Rev.1, Rule 12, Class IIa examples | §4.3 |
| 25 | "'health claim' means any claim that states, suggests or implies that a relationship exists between a food category, a food or one of its constituents and health" | Reg 1924/2006 Art. 2(2)(5) | §4.4 |
| 26 | "the role of a nutrient or other substance in growth, development and the functions of the body" | Reg 1924/2006 Art. 13(1)(a) | §4.4 |
| 27 | "Nutrition and health claims shall be based on and substantiated by generally accepted scientific evidence." | Reg 1924/2006 Art. 6(1) | §4.4 |
| 28 | "claims which make reference to recommendations of individual doctors or health professionals and other associations not referred to in Article 11" | Reg 1924/2006 Art. 12(c) | §4.4 |
| 29 | "in the labelling, presentation or advertising of foods to be delivered as such to the final consumer" | Reg 1924/2006 Art. 1(2) | §4.4 |
| 30 | "even if the information is factually correct" | UCPD Art. 6(1) | §4.5 |
| 31 | "the results and material features of tests or checks carried out on the product" | UCPD Art. 6(1)(b) | §4.5 |
| 32 | "it omits material information that the average consumer needs … to take an informed transactional decision" | UCPD Art. 7(1) | §4.5 |
| 33 | "Claiming that a trader … or a product has been approved, endorsed or authorised by a public or private body when he/it has not" | UCPD Annex I §4 | §4.5 |
| 34 | "Falsely claiming that a product is able to cure illnesses, dysfunction or malformations." | UCPD Annex I §17 | §4.5 |
| 35 | "breast pumps"（不在医疗器械清单中） | MHRA Borderlines §3 | §5.1 |
| 36 | "breast pumps for treatment of inverted nipples" | MHRA Borderlines §3 | §5.1 |
| 37 | "This is not the case"（在美国是器械，在英国不一定是） | MHRA Borderlines §1 | §5.1 |
| 38 | "defined by the manufacturer's intention for the product as defined in their labelling, instructions for use and promotional material" | MHRA Borderlines §2 | §5.1 |
| 39 | "up until 30 June 2030" | MHRA Regulating medical devices in the UK | §5.2 |
| 40 | "The UKCA mark will not be recognised on the Northern Ireland market." | MHRA UKCA guidance | §5.2 |
| 41 | ""tests, analyses, research, or studies that (1) have been conducted and evaluated in an objective manner by experts …"" | FTC HPCG 2022 p.13 | §6.1 |
| 42 | "substantiation of health-related benefits will need to be in the form of randomized, controlled human clinical testing" | FTC HPCG 2022 p.13 | §6.1 |
| 43 | "Randomized, controlled human clinical trials (RCTs) are the most reliable form of evidence" | FTC HPCG 2022 p.14 | §6.1 |
| 44 | "numerous flawed and inadequate studies are unlikely to add up to competent and reliable scientific evidence" | FTC HPCG 2022 p.14 | §6.1 |
| 45 | "Epidemiological or observational studies … don't prove a causal link." | FTC HPCG 2022 p.15 | §6.1 |
| 46 | "Animal and in vitro studies … aren't sufficient to substantiate health-related claims." | FTC HPCG 2022 p.15 | §6.1 |
| 47 | "must have at least the level of support that they claim to have" | FTC HPCG 2022 §1 | §6.1 |
| 48 | "implies not just that the ingredient was tested, but also that the test results prove a benefit"（Example 18） | FTC HPCG 2022 p.14 | §6.1 |
| 49 | "citation to clinical studies can contribute to a clinically proven claim"（脚注 59 引 POM Wonderful） | FTC HPCG 2022 p.42 | §6.1 |
| 50 | "advertisers and ad agencies have a reasonable basis for advertising claims before they are disseminated." | FTC 1984 Substantiation Policy | §6.1 |
| 51 | "the type of claim, the product, the consequences of a false claim, the benefits of a truthful claim, the cost of developing substantiation … and the amount of substantiation experts in the field believe is reasonable" | FTC 1984 | §6.1 |
| 52 | "a representation, omission or practice that is likely to mislead the consumer acting reasonably in the circumstances, to the consumer's detriment." | FTC Deception 1983 | §6.1 |
| 53 | "the entire mosaic, rather than each tile separately" | FTC Deception 1983 | §6.1 |
| 54 | "the Commission determines the effect of the practice on a reasonable member of that group" | FTC Deception 1983 | §6.1 |
| 55 | "puffing or other hyperbole, which do not amount to the type of affirmative product claims for which either the Commission or the consumer would expect documentation"（脚注 42 引 Pfizer） | FTC Deception 1983 | §6.2 |
| 56 | "will not bring advertising cases based on subjective claims (taste, feel, appearance, smell)" | FTC Deception 1983 | §6.2 |
| 57 | "Pro forma statements or disclaimers may not cure otherwise deceptive messages or practices."（脚注 38） | FTC Deception 1983 | §6.3 |
| 58 | "the law may be violated even if the truth is subsequently made known to the purchaser" | FTC Deception 1983 | §6.3 |
| 59 | "use of adjectives such as 'promising' or 'preliminary' does not alter the net impression of the efficacy claims"（脚注 25 引 POM） | FTC HPCG 2022 | §6.3 |
| 60 | "Medela researchers found that double pumping obtains 18% more milk on average, compared to single pumping³." | medela.com | §7.2A |
| 61 | "Clinical studies, PersonalFit Flex™ compared to PersonalFit data on file (NCT02496429, NCT02492139, NCT02719548, NCT03091985)" | medela.com | §7.2A |
| 62 | "Clinically proven design for output, powered by ComfortFlow™" | onewillow.com | §7.2A |
| 63 | "105° flange angle clinically proven to encourage more milk" | onewillow.com | §7.2A |
| 64 | "In an independent survey of 500 pumping moms, 71% said Willow Go gives better milk output than their…" | onewillow.com | §7.2A |
| 65 | "Boost your milk flow without the ouch" | elvie.com | §7.2A/B |
| 66 | "Elvie Stride 2: Hospital-Grade Suction Breast Pump" | elvie.com | §7.2F |
| 67 | "15 levels of customizable, hospital-strength, tug-and-release suction (up to 295 mmHG per side)" | onewillow.com | §7.2F |
| 68 | "No, the Hands-free Collection Cups are not part of the hospital grade pump system Symphony Plus." | medela.com | §7.2F |
| 69 | "Freestyle™ Mini is not a hospital pump." | medela.com | §7.2F |
| 70 | "three additional inserts to cater to over 95% of nipples sizes" | medela.com | §7.2E |
| 71 | "fit seamlessly in most nursing bras" | medela.com | §7.2E |
| 72 | "cater to over 95% of nipples sizes" | medela.com | §7.2E |
| 73 | "FDA approved, FSA/HSA eligible" | lansinoh.com | §7.3 |
| 74 | "Clinically tested, FDA approved, and made without BPA for a safer pumping experience." | onewillow.com | §7.3 |
| 75 | "one piece FDA Compliant construction" | babybuddhaproducts.com | §7.3 |
| 76 | "FDA 510(k) Cleared. Made with Care." | momcozy.com（W1） | §7.3 |
| 77 | "*Based on quantitative findings from internal real-user testing. Results are self-reported. Individual results may vary." | momcozy.com（W1） | §7.4 |
| 78 | "supporting the natural release of oxytocin—the hormone that triggers milk let-down" | momcozy.com（W1） | §7.2A |
| 79 | "Warmth + Gentle Massage help the body relax" | momcozy.com（W1） | §7.2A |
| 80 | "Mimics baby's natural suction to boosts milk flow." | elvie.com | §7.2A |
| 81 | "2-Phase Expression® Technology mimics babies' natural sucking rhythm" | medela.com | §7.5 |
| 82 | "Powerful performance: Medela's research-based pumping curves and patented 2-Phase Expression Technology mimic your baby's natural sucking patterns" | medela.com | §7.5 |
| 83 | "Sensors automatically detect letdown and track milk volume in real time." | onewillow.com（360） | §9.5b |
| 84 | "The only wearable breast pump with Smart Suction technology designed to detect letdown and automatically switch from stimulation to expression" | onewillow.com（360） | §9.5b |
| 85 | "BPA-free, food-grade materials: Safe for both mother and baby." | momcozy.com（S12 Pro） | §10.1 |
| 86 | "All components that come in contact with milk are BPA-free, food-grade PP and silicone." | momcozy.com（S12 Pro） | §10.1 |
| 87 | "Closed system with BPA-free construction" | medela.com / babybuddhaproducts.com | §10.1 |
| 88 | "The Hands-free Collection Cups are not intended to be used for milk storage." | medela.com | §7.4 |
| 89 | "Set aside about one uninterrupted hour and follow this pattern: Pump for 20 minutes…" | lansinoh.com（Signature Comfort） | §7.6 |
| 90 | "Hard-to-reach" / "misleading omission" 相关 UCPD 措辞 | UCPD Art. 7(2) | §4.5 |

---

## 附录 C：待办与后续验证清单（按优先级）

| 优先级 | 事项 | 负责方 | 为什么重要 |
|---|---|---|---|
| **P0** | **统一 hospital-grade 口径**：清理 Amazon ASIN `B0CZNQ7VH7` 标题中的 `Hospital-Grade` 与结构化属性 `Product Style: hospital grade`；清理 `collections/electric-breast-pump` 的 "V Series — hospital grade suction"；把官网 `collections/hospital-grade-breast-pump` 的术语表提升为品牌级官方术语表 | 品牌 / 电商运营 | **三个渠道三种立场的自相矛盾。不需要等法规判断，现在就能改。** 见 §7.7 |
| **P0** | **拆分 `28.2%` 的三种含义**：机器指标（效率/速度）与人体结果（奶量）不得共用同一数字；无 RCT 时删除或改写「奶量提升 28.2%」（V1 Pro / V2 Pro / Electric 集合页） | 品牌 / 文案 | FTC HPCG 2022 §1 + Example 18。见 §7.8 |
| **P0** | **删除 `Safe for both mother and baby`**（S12 Pro Quick 页） | 品牌 / 文案 | 不可证伪的全称安全断言；无竞品使用。见 §9.5(b) |
| **P0** | **M9 页 "FDA and LFGB certified" 改为材料级表述** | 品牌 / 合规 | 21 CFR 807.97 精神；FDA 消费者页面 |
| **P0** | 核实 **Momcozy Wellness 1（W1）** 的 FDA 510(k) K 号，确认 warmth + massage 功能是否在已 clearance 的 intended use 内 | 法律 / 合规 | 官网自称 "FDA 510(k) Cleared" 但 openFDA 检索未命中对应器械名；若功能超出 clearance 范围，则同时触发 21 CFR 807.81(a)(3)(ii) 与 807.97。见 §12 G3 |
| **P0** | 修掉 **安全词表 `reduces pain` / `less pain`** 与 H07 的直接矛盾 | 规则库维护 | 规则库自相矛盾会导致自动判定结果不可预测 |
| **P1** | 修正 W1 页的 RCT 引用：披露 NICU 人群限定、说明是"设计借鉴"而非本机证据、补 DOI 链接 | 品牌 / 文案 | FTC HPCG 2022 Example 34（人群外推）。见 §7.9 |
| **P1** | 把 **`FDA registered` 移出安全词**，H06 正则扩展至 `compliant` / 语序变体 | 规则库维护 | 21 CFR 807.97 + FDA 官方页面点名批判该用法 |
| **P1** | **H02 增加「声称对象」子字段**（machine_metric vs human_outcome），并按证据等级重新分档 | 规则库维护 | 见 §7.8、§9.5(c) |
| **P1** | 把 **亚马逊 listing（标题 / bullet / 结构化属性）纳入审查范围** | 治理流程 | 当前审查只覆盖官网文案时，§7.7 那类跨渠道矛盾必然漏检 |
| **P1** | 补全免责声明的不对称：把 `Individual results may vary` 扩展到所有含功效声称的页面，或（更好）删除无证据的功效声称 | 品牌 / 文案 | ~14 处功效声称只 1 处有免责。见 §7.8 |
| **P1** | **清理规则库与合规文档里的失效平台引用**：不得再使用 Google `answer/6020955`（现为 Misrepresentation，非 Healthcare）、Meta "Personal health"（标准已不存在）、TikTok `/i18n/help/article/` 前缀、以及措辞 "negative body image"（Meta 现行正文无此短语） | 规则库维护 / 合规 | **这是四类失效里唯一会静默出错的一类** —— answer ID 被复用后指向的是"仍然有效但完全不同"的政策页，不会报 404。见 **§8.0(1)** |
| **P1** | **把 `before/after` 从布尔字段改为条件字段**（`平台 × 有无证据或免责 × 是否与产品相关`） | 规则库维护 | TikTok 与 Amazon **禁止**、Meta **有条件允许**、Google **不作为素材规则** —— **单一布尔值在四个平台里至少错两个**。见 **§8.6 结论 9 / §8.7 E** |
| **P1** | **把 `severity` 与「具体子政策」绑定，而不是与主题绑定** | 规则库维护 | Google 同一条健康声称违规因命中不同子政策而落入「检测即停号、无预警」与「停号前至少 7 天预警」两个等级。见 **§8.6 结论 10 / §8.7 F** |
| **P1** | **为平台政策建立独立复核节奏**并记录"引用日 + 页面变更日" | 治理流程 | Meta *Health and Wellness* 正文变更日 **Jul 22, 2026**，距今不足两个月；Amazon 两页自标 **Apr 6 / Apr 27, 2026**。**平台政策保质期短于法条**，不能与法条同一节奏复核。见 **§8.0(2)** |
| **P2** | 补齐 **Amazon Seller Central** 的品类/listing 规则（Conditional products、Restricted products、Product detail page、A+ Content、Baby 类目风格指南） | 商务（账户经理）/ 调研 | **关键问题已由公开面回答**（吸奶器明文列入 Category 1「Generally allowed」；对比禁令与举证要求已取得），**但 listing 侧规则仍需登录态**。见 §12 G7b |
| **P2** | 向 Amazon 确认 **保健产品分级表第三列**（逐档 supply 专属限制正文） | 商务 | 该列在页面 DOM 中渲染为空，故 `Permitted on all supply with the following restrictions:` 之后无正文。见 §12 G21 |
| **P3** | 补 **Meta「About ads that use health-related data」帮助文章** | 调研 | 需搜索 API 或已登录 Meta 会话。**不影响 §8.2 结论** —— 已证实 Meta 不发布独立的 "Health data" 广告标准。见 §12 G20 |
| ~~P1~~ | ~~补齐平台政策原文~~ —— **已完成**（四平台共 **64 页**政策正文：Meta 14 / Google 20 / Amazon 15 / TikTok 15；证据 `_evidence/R5/platforms/` 191 文件 / 90 MB） | 调研 | 见 §12 G7b、§8.0。**Amazon 侧由"仍缺"降级为"公开面已足、登录面待补"** |
| **P1** | **裁决吸奶器 milk-contact 部件是否适用 Reg (EC) 1935/2004 / (EU) 2024/3190** | 法律 | **新增最高优先项。** 决定欧盟站储奶容器是否需要 BPA 合规与 Art. 8 合规声明 —— 是产品合规而非文案问题。见 **§10.2b / §12 G8b** |
| ~~P1~~ | ~~补齐材料类法规原文~~ —— **已完成**（177.2600 / 177.1580(d) / 2024/3190 / 1935/2004 Art. 3 / LFGB §30·§31 全部取得） | 调研 | 见 §12 G8 |
| ~~P2~~ | ~~检索 EU 授权健康声称注册库中的泌乳相关条目~~ —— **已完成（2,337 条全量检索，授权项为 0）** | 调研 | **结论已落地**：欧洲站 `more milk` 类声称在欧盟健康声称体系中**无任何授权先例，且同类申请曾被正式驳回**。见 §4.4 法源 20 / §12 G1 |
| **P2** | 取得 **K253946 / K251394 的 510(k) summary 原文** | 法律（FOIA 或向代工厂索取） | 把 H01/H02 的判定从"经验"变成"对照 IFU" |
| **P2** | 调研 **EU 层面是否有对吸奶器的官方定性文件** | 调研 | §4.3 的 Class IIa / Rule 12 结论目前只是示例类比。见 §12 G2 |
| **P3** | 调研 **加拿大**（SOR/98-282）的母婴品类定性与声称举证标准 | 调研 | Momcozy 有 14 条广告在跑，是纯空白 |
| **P3** | 抓取 **Meta Ad Library** 竞品广告素材 | 调研 | 补足"官网 vs 广告"的差异证据 |
| **P3** | 补 **POM Wonderful** 案卷原文（155 F.T.C. 1 (2013)） | 法律 | 若要在合规文档里直接引判词。**注**：`clinically proven` 的执法先例已另行取得 3 份原文（NeuroMetrix / BASF-DIEM / Quincy Bioscience），见 §6.1 法源 30b —— POM Wonderful 是唯一仍缺的一份 |
| **P3** | 把 Willow 的 Brandtracker 脚注格式（机构名 + 样本量 + 时间 + 独立性）写入改写建议库作为最佳实践模板 | 规则库维护 | 见 §7.4 模板 2 |
| **P3** | 建立**竞品对标语料库**并定期刷新（Medela / Willow+Elvie / Spectra / BabyBuddha / Lansinoh） | 规则库维护 | 这是 H05 / H07 / M01 / M02 / M05 / U01 / U03 这 7 条「准法源」规则的唯一边界校准来源。见 §9.3 |

---

## 附录 D：本分片的三个「必须记住」的判定

如果这份文档只被记住三件事，应当是这三条：

### D1｜品类不是一个维度，是「内容 → 监管身份 → 适用法条」的闭环

同一台吸奶器，在英国默认**不是**医疗器械（MHRA 明文列举）；在美国**是** Class II 器械；在欧盟**取决于声称**。而决定的是**文案**（21 CFR 801.4 的 "objective intent"、MDR Art. 2(1) 的 "intended by the manufacturer"、MHRA §2 的 "promotional material"）。

**因此规则库不应该有「品类」维度，而应该有一张 `品类 × 国家 → {监管身份阈值, 触发法条}` 的映射表**，以及一个 `product_code` / `intended_use` / `clearance_ref` 字段组。

### D2｜规则的红线应当画在「声称所隐含的客观事实」上，不是「词」上

本次调研在 7 个品牌 90+ 页面上实测的结果是：**全行业都在用 `more milk`、`mimic baby`、`hospital grade`、`clinically proven`。** 把这些词判为高危的规则，会同时把所有竞品判为高危，从而**失去区分度**。

真正的分界线是 **FTC Deception Policy 1983 脚注 42** 划的：`subjective claims`（puffery，不需文档）vs `affirmative product claims for which documentation would be expected`（需文档）。而判定的操作化标准只有一条：**能否被第三方独立复核为真/假。**

### D3｜免责声明不是许可证

FTC 明文：*"Pro forma statements or disclaimers may not cure otherwise deceptive messages or practices."* 因此 `豁免词` 这个字段名本身就是错的 —— 它的正确语义是 **「本句已带证据标记」**，命中后应当**降级到人工复核**，而不是**自动放行**。

检验方法（可直接做成规则）：**把免责声明遮住，这句文案还成立吗？** 不成立 → 免责声明无效，原声称判险。

---

*本文件共引用法规条款与官方文件 **48 项**、平台政策原文 **6 类**（**Meta / Google / TikTok / Amazon Ads 四家已取得正文**；仅 Amazon Seller Central 侧因登录墙未取得）、**FTC 执法案卷 3 宗**、**EU 健康声称注册库全量数据集（2,337 条）**、竞品页面 **90+ 页 / 7 个品牌**、逐字原文 **110+ 处**。全部证据可通过 §11 的本地路径复核。**未核实项已在 §12 全部列出（共 22 条，编号 G1–G19 + G1b、G1c、G8b），未用推测填空。已关闭的缺口在表内以删除线标注。***

---

## 交付摘要（供上级分片汇总使用）

| 项 | 值 |
|---|---|
| **主文档路径** | `research/governance/R5-category-and-competitors.md` |
| **行数** | 2,075 行（目标 800–1500 行，超出；原因为法源逐字引用与竞品逐字对照表的证据密度要求，未为凑长度注水） |
| **引用的来源数量** | **法规与官方文件 28 项**（21 CFR 8 条、FDA 指南/页面 2 份、MDR 1 部 + MDCG 1 份、Reg 1924/2006、UCPD、MHRA 3 份、FTC 3 份 + 16 CFR 255、openFDA 2 个 API、EC guidance 1 份）＋ **平台政策 6 类**（Meta 10 页、Google 9 页、**TikTok 15 页全文**、Amazon Seller Central 7 页[登录墙骨架] / Amazon Ads 政策页若干）＋ **材料法规 4 项**（21 CFR 177.2600、LFGB §30/§31、ISO/IEC 2 页[骨架]）＝ **合计 45 项一手来源** |
| **抓到的竞品数量** | **7 个品牌 / 90+ 个页面**：Medela 9 页、Lansinoh 10 页、Willow 21 页、Elvie 11 页、Spectra 7 PDP + 12 页 + 全 47 产品、BabyBuddha 5 PDP + 4 页 + 全 43 产品、Momcozy 10 PDP + 6 集合页 + 全 405 产品 + **3 个 Amazon US listing** |
| **逐字引用数** | 约 110 处（附录 B 索引了 90 处核心引用） |
| **原始证据** | `research/governance/_evidence/R5/` — **698 个文件 / 210 MB**（含根目录 `FINDINGS-ftc-eu-law.md`），分 7 个子目录（`fda/`、`eu/`、`uk/`、`ftc/`、`competitors/`、`platforms/`、`materials/`） |
| **同行分项报告** | `FINDINGS-medela-lansinoh.md`（1,525 行）、`FINDINGS-spectra-babybuddha-momcozy.md`（1,162 行）、`FINDINGS-willow-elvie.md`（397 行）、`QUOTE-BANK-byte-exact.txt`（832 行 / 零手工转写）、`FETCH-LOG.txt`（224 行） |

### 未查到的关键项（按重要性排序，完整清单见 §12）

1. **G3（最高）** —— Momcozy **Wellness 1（W1）** 对应的 FDA 510(k) K 号。官网自称 "FDA 510(k) Cleared"，但 openFDA `product_code:HGX` 全量 250 条中**没有任何一项 Momcozy clearance 的器械名包含 warm / massage / wellness**；检索到一项 `K260864 "Mother's Nature W1 Warming Wearable Breast Pump"`（申请人 Shenzhen TPH Technology Co., Ltd.，2026-06-09），**器械名与申请主体均与 Momcozy 不同，是否同一产品未核实**。**这是本次调研发现的唯一一个可能构成实质合规风险的具体项。**
2. **G4** —— 510(k) summary 的 intended use 逐字文本（`accessdata.fda.gov` 全站 Akamai 拦截）。取到后即可把 H01/H02 的判定从"经验"变成"对照 IFU"。
3. **G16** —— 吸奶器是否需要在 **Google Ads** 侧申请医疗健康认证。已取到政策全文 43,243 字符，但该页**未含 medical device 专门条款**。这是操作问题，需向 Google 代表确认。
4. **G2** —— **EU 层面是否有对吸奶器的官方定性文件**。MDCG 2021-24 Rev.1 的示例清单里**没有 breast pump**，最接近的是 Rule 12 的 "Suction pump"。§4.3 的 Class IIa 结论因此只是示例类比，**不能写成官方定性**。
5. **G1 —— 已关闭（本次最重要的补证之一）** —— **EU 是否存在针对泌乳/母乳/催乳的授权 health claim**：**不存在。** 已绕开门户 SPA 直取 FIP 后端 API，全量检索 **2,337 条** claim，泌乳类词汇的**授权命中数一律为 0**；`prolactin`、`galactagogue`、`let-down`、`milk production` 等词**全库 0 命中**；最接近的 silymarin 申请（「improving the physiological production of breast milk」类申请）被 **Reg (EU) No 666/2011 以「效应未获证实」驳回**。见 §4.4 法源 20。**对委托方的意义：欧洲站的 `more milk` 类声称，问题不只是「自己没有证据」，而是「监管机构已就同一问题作出过否定判断」。**
6. **G7a 已关闭 / G7b 已降级** —— **TikTok**（15 页全文，结论见 §8.5）、**Meta**（14 页）、**Google**（20 页）政策原文均已取得；**Amazon** 由"仍缺"改为**公开面已足、登录面待补**（取得 **15 页** Amazon Ads 政策，含 `Claims and substantiation`、`Healthcare products and services`、`Baby formula and feeding accessories`、`Stores creative acceptance policies`）。**仅 Seller Central 登录墙后的品类/listing 规则仍未取得**（转记 G7b 新行与附录 C P2）。**四平台合计 64 页政策正文。**
7. **G8 —— 基本关闭** —— **Reg (EU) 2024/3190、Reg (EC) 1935/2004 Art. 3、21 CFR 177.1580(d) 均已取得**；并纠正一处：**2018/213 已被 2024/3190 Art. 13 废止，不得再作为现行依据引用**。**新开 G8b（高优先）**：吸奶器 milk-contact 部件是否适用 1935/2004 / 2024/3190 的**适用范围未决** —— 见 §10.2b。
8. **G9** —— **ISO 13485 / ISO 9001 / IEC 60601-1 / ISO 10079-1 的标准正文未取得**（Cloudflare / 付费墙）。
9. **G10** —— **加拿大市场（14 条在跑广告）的监管定性未调研**（超出 R5 分片边界，但这是真实的规则库空白）。
10. **G5 / G18** —— **Meta Ad Library 竞品广告素材、Amazon A+ 模块正文未取得**。
11. **G15** —— 委托方 Meta 广告后台的**实际年龄定向配置未核实**（Meta 健康类政策有 18+ 硬性要求）。
12. **G11 —— 已关闭** —— `clinically proven` 的 FTC 执法先例已取得 3 份案卷原文（**NeuroMetrix** 器械案 / **BASF-DIEM** / **Quincy Bioscience**）。衍生两条：① **Quincy ¶28–29 表明「做过一项 RCT」不是抗辩**，FTC 攻击的是该 RCT **未在预设终点达到显著**且被告做了 30+ 次事后分析 → H03 应增加「预设主要终点 + 达到显著」子条件；② **不存在 FTC 吸奶器/哺乳类执法案件**，不得凭空援引。见 §6.1 法源 30b。
13. **G1b / G1c** —— 新增两项次要缺口：EFSA 通用科学要求指南（EFSA J 2016;14(1):4367，Cloudflare 拦截）与欧委会非食品边缘产品范围指南（2007 指南中无此内容）。
14. **G12 / G13 / G14 / G17 / G19** —— 次要缺口，详见 §12。
