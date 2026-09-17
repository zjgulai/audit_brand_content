# -*- coding: utf-8 -*-
"""R5 integration — step: platform-policy evidence (FINDINGS-platform-policies.md)."""
import io, sys

P = "research/governance/R5-category-and-competitors.md"
t = io.open(P, encoding="utf-8").read()
orig_len = len(t)
log = []

def sub1(anchor, new, label):
    global t
    n = t.count(anchor)
    if n != 1:
        print("ABORT: anchor count=%d for %s" % (n, label)); sys.exit(1)
    t = t.replace(anchor, new, 1)
    log.append(label)

# ============ 1. §8.0 — stale-reference register  (insert before §8.1) ============
A0 = "### 8.1 平台政策不是法源，但必须与法源分字段存放"
B0 = u"""### 8.0 ⚠️ 失效引用登记表 —— 任务书里给的平台政策 URL 有一部分已经不对了

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

"""
sub1(A0, B0 + A0, "§8.0 inserted")

# ============ 2. §8.2 strengthening — Meta taxonomy + negative body image wording ============
A2 = u"**（2）Meta 的 Personal Attributes 政策禁止暗示受众的个人健康属性。**"
B2 = u"""> **⚠️ 政策名与措辞的一处更新（2026-09-15 核验）**：
> 1. **Meta 已不存在名为 "Personal health" 的独立广告标准**（四个语区全部 404）。其覆盖面现拆入 *Health and Wellness*（`restricted-goods-services/health-wellness/`）下的 `Adult Products and Reproductive Health` 小节 —— 即上引同一页。**引用时不要写 "Meta Personal health policy"，那是本次调研早期笔记里的旧名。**
> 2. **Meta 现行正文已不再使用 "negative body image" 这个说法。** 现行对应句在 *Advertising Standards: Introduction* → `PROMOTING POSITIVE USER EXPERIENCES`（逐字）：
>
> > We also prohibit other objectionable material, such as **content implying or attempting to generate negative self-perception in order to promote diet, weight loss or other health related products**.
>
> 而 *Health and Wellness* 页内的对应表述是（逐字）：`statements of inferiority about physical appearance (i.e., terms, descriptions, or questions that are negative and attack an individual's appearance, specific body parts, or hygiene)`。
> **规则库若沿用 "negative body image" 作为关键词，会在 Meta 现行正文上零命中**；而新表述比旧短语**更宽**（`or other health related products`）。Google 侧对应词是 `Body shaming` / `Negativity related to physical attributes or social interactions`（见 §8.3、§8.7 F）。

"""
sub1(A2, B2 + A2, "§8.2 Meta taxonomy strengthened")

# ============ 3. §8.4 — Amazon Category 1 finding ============
A4 = u"### 8.5 TikTok —— 已取得正文（15 页），且命中一条**平台专属**的硬约束"
B4 = u"""#### (6) 本项的核心补充：**Amazon 明文把 Breast Pump 列入「Category 1（低敏感度）：一般允许」**

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

"""
sub1(A4, B4 + A4, "§8.4(6) Amazon Category 1 inserted")

# ============ 4. §8.7 — cross-platform reflex sentences ============
A7 = u"### 8.6 本节的七个落地结论"
B7 = u"""### 8.7 四个平台的「反射句」—— 按委托方三条待测声称逐条对照

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

"""
sub1(A7, B7 + A7, "§8.7 inserted")

# ============ 5. §8.6 — heading + 3 new conclusions ============
A6 = u"### 8.6 本节的七个落地结论"
sub1(A6, u"### 8.6 本节的落地结论", "§8.6 heading retitled")

A6b = u"""| 7 | **Amazon 明文禁止「与竞品直接对比」（`We do not permit direct comparison to competitor brands.`），并要求对比声称引用独立来源且**距今 12–18 个月内**；量化性能声称的证据必须能在**产品详情页或产品包装**上被发现** | **§8.4(2)(3)** | **H08 在 Amazon 上不需要论证「是否误导」，指名对比本身不被接受**；**M06 获得一条可自动执行的判据**（引用独立来源 + 时效 ≤12–18 个月）；`28.2%` 类声称在 Amazon 上比在官网**多一层**「证据就地可发现」要求 |"""
B6b = A6b + u"""
| 8 | **Amazon 明文把 `Breast Pump` 列入 Category 1（低敏感度：Generally allowed）**，但同一页要求 `all implicit and explicit claims … are accurate, truthful, not misleading, and, when appropriate, backed by scientific evidence` | **§8.4(6)** | **Amazon 侧的风险定位改为"文案层"**：品类投放资格不是问题，**声称**才是问题。§8.4(1) 的"Seller Central 登录墙"**不再构成本品类的实质证据缺口**（已转记 G21 为细节性缺口） |
| 9 | **`before/after` 不能做成一个布尔字段** —— TikTok（产品效果对比）与 Amazon（体重管理）**禁止**；Meta **有条件允许**（美容类 18+，且"与产品或服务无关"的才禁）；Google **不作为素材规则**，只经 *Unreliable claims* 与 *Imposing negativity* 间接命中 | **§8.7 E** | `before_after` 必须建为 **`平台 × 有无证据或免责 × 是否与产品相关` 的条件字段**。**单一 `before_after: banned` 会在四个平台里至少错两个** |
| 10 | **Google 的处置严重度分散在子政策里**，同一条健康声称违规因触发不同子政策而落入不同等级：*Unacceptable business practices / Unauthorized pharmacies* = `suspended upon detection and without prior warning`；*Unreliable claims / Editorial* = `A warning will be issued at least 7 days prior to any suspension` | **§8.7 F** | **严重度不是 topic 的属性，是"topic × 命中的子政策"的属性**。`severity` 字段必须与**具体子政策**绑定，不能只挂在主题上 |
| 11 | **Meta 与 Google 现行正文都已不再使用旧措辞**（Meta 无 "negative body image"、无 "Personal health" 标准；Google 的 answer ID 已被复用） | **§8.0、§8.2、§8.7 A** | **规则库的 `platform_policy` 字段必须记录"引用日 + 页面变更日"**；Meta *Health and Wellness* 的正文变更日是 **Jul 22, 2026**，距今不足两个月 —— 平台政策的**保质期短于法条**，需要单独的复核节奏 |"""
sub1(A6b, B6b, "§8.6 added conclusions 8-11")

# ============ 6. §7.1 — pre-empt the "claims density in ads" over-extension ============
A71 = u"### 7.1 样本与方法"
sub1(A71, u"""> **⚠️ 适用范围限定（本次补充取证后加注）**：本节的竞品证据**全部来自官网与落地页**，**不代表这些品牌的付费广告用词**。§8 的平台政策取证（64 页）进一步说明：**平台政策约束的是"广告素材与落地页"，其判据与官网文案的判据不是同一套**（例：Amazon 要求量化声称的证据"可在产品详情页或包装上被发现"，Meta 禁止暗示受众的个人健康属性 —— 这两条对官网文案都不适用）。
> **因此"竞品在广告里功效密度更低"是一个观察，不是已证实的事实。** 若要把"竞品广告用词更保守"作为规则放宽的依据，必须先取得广告素材（Meta Ad Library 等），见 **§12 G5**。

""" + A71, "§7.1 scope caveat added")

# ============ 7. §11.3 — deliverables register ============
A113 = u"| **`_evidence/R5/ftc/enforcement/`** | **3 宗 FTC 执法案卷原文**（NeuroMetrix / BASF-DIEM / Quincy Bioscience，各含 PDF + PDFTEXT） | **§6.1 法源 30b** |"
B113 = A113 + u"""
| **`_evidence/R5/FINDINGS-platform-policies.md`**（128 KB / 1,715 行） | **四平台广告政策逐字取证**（Meta / Google / Amazon / TikTok，**64 页政策正文**）；含 §0.2 URL 失效核验、§2.0 Google answer ID 复用表、跨平台「反射句」对照、before/after 分歧与严重度梯度 | **§8.0、§8.2–§8.7** |
| **`_evidence/R5/platforms/`** | **191 个文件 / 90 MB**：85 份 HTML + 105 份文本提取，逐文件带 `TITLE / URL / FETCH_DATE=2026-09-15` 头；`_tools/` 内含可复用的 `fetch.sh`（代理 + curl）与 `render.py`（CDP 无头渲染） | **§8（全部）** |"""
sub1(A113, B113, "§11.3 deliverables added")

# ============ 8. §12.1 — G7b update + G20/G21 ============
A7b = u"| **G8** | **材料类法规原文**"
B7b = u"""| **G7b** | **Amazon 平台政策原文** —— **已大幅补齐（本项降级）** | 补取路径：公开 **Amazon Ads** 面（`advertising.amazon.com/help/<ID>` 与 `/resources/ad-policy/<完整 slug>`）。本次取得 **15 页**，含 `Claims and substantiation`、`Healthcare products and services`、`Baby formula and feeding accessories`、`Prohibited products and services across all supply`、`General requirements`、`Stores creative acceptance policies` | **Seller Central 帮助页（`sellercentral.amazon.com/help/hub/reference/external/G…`）仍为登录墙**（每页仅约 1,847 字符通用外壳） | **高 → 中（已降级）**。**关键问题已被公开面回答**：① 吸奶器明文列入 **Category 1（低敏感度：Generally allowed）**——投放资格无问题；② `We do not permit direct comparison to competitor brands.`——**H08 在 Amazon 上直接闭环**；③ `Regulatory endorsement claims on healthcare products.`——**"FDA approved"/"clinically proven" 在 Amazon 上最硬**。**仍缺**：Conditional products、Restricted products、medical devices / FDA-cleared devices 规则、Product detail page 规则、A+ Content / Brand Registry、Baby 类目风格指南（均需已登录卖家账号或 SP-API 文档） |
| **G20** | **Meta「About ads that use health-related data」帮助文章** | 枚举 Meta Business Help Center 候选文章 ID（3 个）并渲染；尝试枚举全部 57 个 `/policies/*` 与 44 个 `/ad-standards/*` | Meta Business Help Center 对 curl 返回 **HTTP 400**；3 个候选 ID 渲染出的是**别的文章**；**无搜索 API 可用**（Firecrawl 429 / Exa 未配置），无法定位正确 ID | **中**。**已确立一条实质性的否定结论：Meta 不发布独立的 "Data and Privacy" 或 "Health data" 广告标准**（已由 57 + 44 个 URL 全量枚举 + 404 探测证实）。Meta 把"广告用健康数据"放在 **Advertising Standards 之外**（Data Policy / Business Tools Terms，且 health **不是** Special Ad Category）。**因此 §8.2 的结论不依赖这篇文章**，缺口仅影响"定向与数据使用"这一非文案层面 |
| **G21** | **Amazon 保健产品分级表的第三列（逐档 supply 专属限制正文）** | 已取得 Category 1/2/3 的**档次名与品类成员**（逐字），但第三列在 DOM 中渲染为空单元格 | 页面渲染问题（该表格列未输出内容）；`Homepage / Fire Devices` 等供给面限制只在 `Baby formula` 页以文字形式出现 | **低**。`Category 1: Generally allowed` 已足够支撑"投放资格无问题"的结论；缺口仅影响"哪些供给面受限"的细节 |
| **G8** | **材料类法规原文**"""
sub1(A7b, B7b, "§12.1 G7b updated + G20/G21 added")

# ============ 9. appendix C — followups ============
AC = u"## 附录 C：待办与后续验证清单（按优先级）"
sub1(AC, AC, "appendix C anchor verified (no-op)")

io.open(P, "w", encoding="utf-8").write(t)
print("OK  %d -> %d chars (+%d)" % (orig_len, len(t), len(t) - orig_len))
for x in log:
    print("  -", x)
