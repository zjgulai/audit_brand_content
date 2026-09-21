# 广告审核/上架合规：政策架构与申诉流程 —— Meta / TikTok / Amazon 一手证据

> 采集时间：本轮会话。采集工具：`curl` + `web_fetch`（`web_search` / `exa_search` / `read_page` 在本环境不可用，已全部改用直连抓取 + Wayback 前缀）。
> 证据强度标注：**【已打开原文】** = 我实际抓取到该 URL 的正文并读取；**【未打开】** = 尝试过但被拦截/无存档/需登录；若某字段公开资料不存在则写「**未找到公开资料**」；推断标注 `[推断]`。
> 引号内文字为**逐字原文**，均附来源 URL。

---

## 0. 一句话总览（三方对比）

| 维度 | Meta | TikTok | Amazon |
|---|---|---|---|
| 规则库骨架 | **两轴**：Ad Content（内容轴，7 大类）+ Business Assets（资产轴，7 类）；每页有 `Policy details` / `Change log` 双标签 | **行业×主题清单**（21 个主题政策 + 22 个资源类政策），每篇顶部 `Last updated:` 日期 | **分层**：Community Guidelines（评论侧）/ 各垂直合规政策（上架侧）/ AHR 账号绩效分 |
| 分级处置 | remove / reduce / inform 三分法 + **strike（警示）计数制** | 拒稿（disapproval）→ 账号 `Attention Needed`（警告）→ `Poor`（停号）→ 临时/永久停号 | 内容移除 / 限制社区功能 / 暂停或终止账号 / 扣留款项；上架侧 AHR 分数跌破阈值或"单一致命违规"即停号 |
| 申诉入口 | 内容侧：Support Inbox 内「request another review」；广告侧业务帮助中心（本次未取到原文） | Ads Manager 右下角 `?` / 右上角 `Customer Support` → **Advertiser Support** | Community 侧：举报表单 + 产品页 Report；卖家侧：**Account Health Dashboard** |
| SLA | **未找到公开资料**（广告审核时限） | **「most are reviewed within 24 hours」**；停号后 **30 天**申诉窗 | **未找到公开资料**（申诉处理时限） |
| 申诉次数限制 | **未找到公开资料** | 临时停号 30 天窗口；**永久停号后不可再申诉** | **未找到公开资料** |
| 翻案回流 | `[推断]` 无公开说明 | `[推断]` 无公开说明 | **有线索**：AHR 分数「improves through violation resolution」 |
| 人机边界 | **明确**：AI/ML 先筛，漏掉的转人工队列；专家可升级到 Global Operations / Content Policy | **明确**：「may involve manual reviews or automated tools」 | **明确**：ML/AI 预筛 + 认证实验室 + 专家团队 |
| 政策版本化 | **有**：每政策页独立 `Change log`，含日期版本（例：`Mar 24, 2023`、`Oct 22, 2024`） | **有**：每篇政策顶部 `Last updated:` 月份 | **未找到公开资料**（无公开政策变更日志） |

---

## A. Meta 广告

### A.1 它解决什么 / 目标用户
面向 Meta 全系广告（Facebook / Instagram / Messenger / Audience Network 等）的**广告内容与商业资产准入与执法规则集**，用户是广告主、代理商与商务资产（主页、BM、像素、账户）运营方。
Transparency Center 导航对它的定位原文（**已打开原文**，`https://transparency.meta.com/policies/ad-standards/`，经 Wayback `web/2024`）：
> "Meta Advertising Standards — Policies for ad content and business assets."

### A.2 规则库怎么组织（**已打开原文 + 已从存档索引验证路径存在**）

Meta Advertising Standards 是**两轴结构**，根页 `https://transparency.meta.com/policies/ad-standards/`。

**轴一：广告内容（Ad Content）** —— 7 个一级类目，路径形如 `/policies/ad-standards/<一级>/<二级>/`：

> **证据口径说明（重要）**：下表**一级类目名**是我从实际存档 URL 的**路径段**归纳出来的，**不是** Meta 在某个页面上明文列出的目录。二级政策路径**全部来自真实存档 URL 列表**。下表中每一条二级路径都对应一个真实存在的存档页面（我已抽验其中 4 条并读到正文）。**一级类目的「7 大类」归组属 `[推断]`**。

| 一级类目 | 二级政策（实际存档路径，逐字） |
|---|---|
| `objectionable-content` | adult-content, adult-nudity-and-sexual-activity, adult-sexual-exploitation, adult-sexual-solicitation-and-sexually-explicit-language, bullying-harassment, child-sexual-exploitation-abuse-nudity, commercial-exploitation-of-crises-and-controversial-events, grammar-and-profanity, low-quality-or-disruptive-experiences, personal-attributes, personal-health-and-appearance, privacy-violations-personal-attributes, profanity, sale-of-body-parts, sensational-content, suicide-selfinjury-eating-disorders, violent-graphic-content |
| `restricted-goods-services` | alcohol, bodily-parts-and-fluid, commercial-exploitation-of-crises-and-controversial-events, cryptocurrency-products-and-services, dating-ads, drug-alcohol-addiction-treatment, drugs-pharmaceuticals, financial-services, gambling-games, hazardous-goods-materials, health-wellness, historical-artifacts, live-endangered-nonendangered-animals, tobacco-related-products, weapons-ammunitions-explosives |
| `content-specific-restrictions` | addiction-treatment, adult-products-or-services, alcohol, cosmetic-procedures-and-wellness, cryptocurrency-products-and-services, dating, financial-services, gambling, online-pharmacies, otc-drugs, prescription-drugs, social-casino-games, subscription-services |
| `deceptive-content` | cheating-and-deceitful-practices, circumventing-systems, non-existent-functionality, prohibited-financial-products-and-services, spyware-or-malware, unacceptable-business-practices, unrealistic-outcomes |
| `dangerous-content` | tobacco, unsafe-supplements, weapons |
| `intellectual-property-infringement` | brand-endorsement, brand-usage, copyright-and-trademarks, third-party-infringement, user-interface-screenshots |
| `fraud-scams` | fraud-scams-deceptive-practices, unacceptable-business-practices |

补充类目：`product-format-specific-policies/non-functional-landing-page`（版位/落地页专项）。

**轴二：商业资产（Business Assets）** —— 路径 `/policies/ad-standards/business-assets/<类>/`，实际存档二级类目（逐字）：`account-authenticity`, `account-integrity`, `cybersecurity`, `inauthentic-behavior`, `spam`, `user-requests`, `violating-content`, `Evading-Enforcement`, `Violating-Networks-or-Associations`。

> 归档路径验证方式：从 Wayback CDX 索引拉取 `transparency.meta.com/policies/ad-standards/` 前缀下全部存档 URL（1500 条），剔除 JS/CSS/埋点噪声后得到 100 条真实政策路径，上表均出自该列表。**注意**：`unacceptable-content`、`deceptive-content`、`dangerous-content` 等一级目录本身**不是**可访问页面（返回 404 存档），实际可访问的是其下的二级叶子页 —— 所以「7 大类」是 `[推断]` 出的分组名，**政策页本身只暴露二级路径**。

**每个政策页统一结构**（逐字，来自 `https://transparency.meta.com/policies/ad-standards/deceptive-content/unrealistic-outcomes/` 等页）：
```
Home > Policies > Advertising Standards > <政策名>
  Policy details | Change log
  CHANGE LOG
  Change log
  Today            Current version
  <日期>           <政策名>
  <政策正文：一句话总则 → Overview → Guidelines（Ads can't… / Ads can…）→ 例证>
  Enforcement
  Review teams
  Stakeholder engagement
```

### A.3 案例库怎么组织（**已打开原文**）
**没有独立的「案例库」**。案例以**正反例证（allowed / not allowed 对照）内嵌在每条政策正文里**，例如 `personal-attributes` 页按属性维度逐条列举（逐字）：
> "GENERAL GUIDANCE — Ad creative that describes or shows the promoted product or service / Using the words like \"you/other\" without referencing a personal attribute"
> "RACE OR ETHNICITY — \"Meet Hispanic men online now!\" \"Find black singles today.\" \"Meet other black singles near you!\""
> "SEXUAL ORIENTATION OR PRACTICES — \"Atlantis Gay Cruises\" \"Gay dating online now!\" \"Are you gay?\" \"Meet other lesbians now!\""
> "PHYSICAL OR MENTAL HEALTH AND DISABILITY — \"Bulimia counseling available\""

`unrealistic-outcomes` 页同样是**禁止例证清单**（逐字）：
> "Unrealistic employment opportunities … Guarantees or promises of employment, financial gain, or other benefits without information on the specific job or title, responsibilities, requirements, or risks."
> "Click-bait tactics. Content that employs click-bait tactics, such as the use of sensational language"

**另一个「案例库」是 Ad Library（广告库）**（导航原文，**已打开原文**）：
> "Ad Library tools — Comprehensive and searchable database of all ads currently running across Meta technologies"

### A.4 申诉怎么走
- **内容侧（有原文）** —— `https://transparency.meta.com/enforcement/taking-action/taking-down-violating-content/`（页面标注 `UPDATED NOV 12, 2024`），五步 takedown experience 第 4 步逐字：
  > "Option for review — If people disagree with the decision, they can ask for another review and provide more information."
  正文逐字：
  > "We occasionally make mistakes. If you believe we made a mistake by removing your content, you usually can let us know, and we'll take another look."
  入口位置逐字：
  > "You can also find it in your Support Inbox on Facebook or Support Requests on Instagram."
- **广告侧（**未打开**）** —— 官方广告审核与申诉说明位于 Meta Business Help Center（`www.facebook.com/business/help/...`）。本次尝试结果：
  - `https://www.facebook.com/business/help/<articleId>` 直连返回 **HTTP 400 + 1542 字节空壳**（无正文）；
  - `https://en-gb.facebook.com/business/help/<articleId>` 同上 400；
  - `https://www.facebook.com/business/help` 同样 400；
  - `https://www.facebook.com/business/help/sitemap.xml` → 400；
  - Wayback 对 `www.facebook.com/business/help/1732903289135458` 返回 **404「The Wayback Machine has not archived that URL」**（该 URL 本身是我用于探测的占位，非确认文章 id）；
  - `https://www.facebook.com/robots.txt` **已打开原文**，其 sitemap 列表含 `https://www.facebook.com/business/sitemap/www_facebook_com_business_sitemap.xml.gz`，但该文件直连返回 **HTTP 403 / 0 字节**，Wayback 亦不可用。
  - **结论：Meta 广告审核流程、人审介入条件、申诉 SLA 的官方原文，本轮未取到 → 「未找到公开资料」（就本次可访问范围而言）。**
- **次数限制**：**未找到公开资料**。
- **翻案回流规则库**：**未找到公开资料**。`[推断]` 从 `unrealistic-outcomes` 反复出现的 "Read less Read more" 与 `Change log` 日期（`Mar 24, 2023`、`Oct 22, 2024`）看，政策会改版，但没有任何官方文字说明申诉翻案数据会回流到规则更新。

### A.5 人机分工边界（**已打开原文**）
`https://transparency.meta.com/enforcement/detecting-violations/how-review-teams-work/`（`UPDATED NOV 12, 2024`），逐字：
> "Content review: when we use technology and when we use human review"
> "For example, we use artificial intelligence and machine learning tools to help us identify and remove a large amount of violating content—often, before anyone sees it."
> "**In those instances where our technology misses something or needs more input, we rely on thousands of reviewers around the world to enforce our Community Standards.**"
> "As potential content violations get routed to review teams, each reviewer is assigned a queue of posts to individually evaluate."
> "In other cases, context is key. For example, our technology might be unsure whether a post contains bullying, a policy area that requires extra context and nuance because it often reflects the nature of personal relationships. In this case, we'll send the post to review teams that have the right subject matter and language expertise for further review. **If necessary, they can also escalate it to subject matter experts on the Global Operations or Content Policy teams.**"

**stated thresholds（阈值）**：官方只给了**定性触发词**（"technology misses something"、"needs more input"、"might be unsure"），**未找到公开的具体数值阈值**。

### A.6 可量化公开数字（**已打开原文**）
- **15,000+ 人工审核员**（两处口径，逐字）：
  > `https://transparency.meta.com/enforcement/detecting-violations/` — "Over 15,000 reviewers across the globe review potential violations on Facebook and Instagram. They receive in-depth training and often specialize in certain policy areas and regions. Altogether, they review content in more than 80 languages."
  > 各广告政策页页脚 — "Our global team of over 15,000 reviewers work every day to keep people on Facebook safe."
- **80+ 语言**（同上）。
- **三分法定义**（`https://transparency.meta.com/enforcement/taking-action/`，逐字）：
  > "Meta takes a three-part approach to content enforcement on Facebook and Instagram: remove, reduce and inform."
  > "**Remove** — … We remove content that goes against our policies as soon as we become aware of it."
  > "**Reduce** — Some problematic content can create a negative experience … We'll often reduce the distribution of this content, **even when it doesn't quite meet the standard for removal under our policies.**"
  > "**Inform** — When content is potentially sensitive or misleading, we sometimes add a warning or share additional information from independent fact-checkers."
- **strike（警示）计数制**（`.../taking-action/taking-down-violating-content/`，逐字）：
  > "We use a strike system to count violations and hold you accountable for the content you post. **Depending on which policy your content goes against, your previous history of violations and the number of strikes you have, your account may also be restricted or disabled.**"
- **广告拒稿率 / 申诉翻案率 / 广告审核时长**：**未找到公开资料**（Meta 的 Community Standards Enforcement Report 覆盖的是内容而非广告；本次未取到任何披露广告审核时效或翻案率的官方页面）。

### A.7 政策版本化 / 生效日 / 变更日志（**已打开原文**）—— 这是 Meta 的强项
每个政策页有独立 `Change log` 标签页，格式逐字为：
```
CHANGE LOG
Change log
Today            Current version
Oct 22, 2024     Online Gambling and Games      ← 来源：/policies/ad-standards/restricted-goods-services/gambling-games/
Mar 24, 2023     Cryptocurrency Products and Services  ← 来源：/policies/ad-standards/content-specific-restrictions/cryptocurrency-products-and-services/
```
页级更新时间戳逐字：`UPDATED NOV 12, 2024`（`/enforcement/taking-action/taking-down-violating-content/`、`/enforcement/detecting-violations/how-review-teams-work/`）。
> 注意：本轮抓到的 changelog 只渲染出「当前版本 + 日期」一行，**未能取到更早版本的完整 diff 列表** —— 该 changelog 是前端按需加载的，Wayback 存档未包含历史条目。**历史版本明细「未找到公开资料」。**

### A.8 出处链接 + 证据强度（Meta）
| URL | 内容 | 强度 |
|---|---|---|
| `https://transparency.meta.com/policies/ad-standards/` | 政策根页（导航/定位语） | Wayback `web/2024` **已打开原文**（直连 400 空壳） |
| `https://transparency.meta.com/enforcement/taking-action/` | remove/reduce/inform 三分法 | Wayback **已打开原文** |
| `https://transparency.meta.com/enforcement/detecting-violations/` | 15,000 审核员 / 80 语言 / AI 优先 | Wayback **已打开原文** |
| `https://transparency.meta.com/enforcement/detecting-violations/how-review-teams-work/` | 人机分工边界（关键原文） | Wayback **已打开原文** |
| `https://transparency.meta.com/enforcement/taking-action/taking-down-violating-content/` | strike 制 / 申诉入口 | Wayback **已打开原文** |
| `https://transparency.meta.com/policies/ad-standards/restricted-goods-services/gambling-games/` | written permission 模型 + Change log | Wayback **已打开原文** |
| `https://transparency.meta.com/policies/ad-standards/deceptive-content/unrealistic-outcomes/` | 禁止例证清单 | Wayback **已打开原文** |
| `https://transparency.meta.com/policies/ad-standards/objectionable-content/personal-attributes/` | 正反例证（案例库形态） | Wayback **已打开原文** |
| `https://transparency.meta.com/policies/ad-standards/product-format-specific-policies/non-functional-landing-page/` | 落地页合规四项校验 | Wayback **已打开原文** |
| `https://transparency.meta.com/policies/ad-standards/content-specific-restrictions/cryptocurrency-products-and-services/` | 许可制 + `Mar 24, 2023` 版本 | Wayback **已打开原文** |
| `https://transparency.meta.com/policies/ad-standards/business-assets/` | 资产轴存在性 | Wayback **已打开原文**（正文为空壳，仅导航） |
| `https://www.facebook.com/business/help/*` | 广告审核/申诉官方说明 | **未打开**（直连 400 空壳；Wayback 无存档） |
| `https://www.facebook.com/robots.txt` | 发现 business sitemap | 直连 **已打开原文** |
| `https://www.facebook.com/business/sitemap/www_facebook_com_business_sitemap.xml.gz` | 帮助中心 URL 全量 | **未打开**（403 / 0 字节） |

---

## B. TikTok 广告

### B.1 它解决什么 / 目标用户
TikTok for Business 的**广告准入政策总库 + 广告主账号治理 + 申诉入口**，用户是广告主/代理商/店铺运营。
TikTok Advertising Policies 总页（**已打开原文**，`https://ads.tiktok.com/help/article/tiktok-advertising-policies`，实际重定向到 `https://ads.tiktok.com/resources/help/article/tiktok-advertising-policies`）逐字：
> "TikTok Advertising Policies — Last updated: August 2025"
> "TikTok advertising policies — Read the following articles to learn about our advertising policies."

### B.2 规则库怎么组织（**已打开原文**）
**单层主题清单，非父子目录**。总页把政策分成两组：

**组一「TikTok advertising policies」（21 篇主题政策，逐字）**：
> Ad Format and Functionality · Adult Content · Alcohol · Animals and Environment · Dangerous Products or Services · Deceptive practices · Discrimination, Harassment, and Bullying · Financial Services · Gambling and Games · Healthcare and Pharmaceuticals · Intellectual Property Infringement · Misinformation · Misleading and false content · Other Products and Services · Politics, Governments, and Elections · Suicide and Self-Harm · Teen Safety and Wellbeing · TikTok After Conversion Experience Policy · Violence and Dangerous Activities · Weight Management and Body Image · Pangle Industry Entry Policies · Pangle Ad Creative Policies

**组二「TikTok advertising policy resources」（22 篇资源/程序类政策，逐字）**：
> About TikTok Advertising Policies for Promote · Advertiser Account Policy · Advertising on TikTok - First Things to Note · Branded Content Policy - Market-specific Requirements · Data Collection Standards · Government Agency Advertisers · Housing, Employment, and Credit ("HEC") Ad Policy · Industries with Certificate Requirements - SEA and NEA · Intellectual Property Infringement Rules for Ads · Market-specific requirements for ad approval · Non-Governmental Organization (NGO) and Non-Profit Organization (NPO) Advertisers · Regional Self-Regulatory Ad Codes for the European Union · State-Affiliated Media Advertisers · TikTok Advertiser Tools and Related Terms Overview · TikTok Ad After Conversion Experience Management Guidelines · TikTok Ad After Conversion Experience: Customer Review Guidelines

**单篇政策内部结构**（以 `tiktok-ads-policy-dangerous-products-or-services` 为例，逐字）：
```
Last updated: April 2025
Principle                      ← 该主题的政策原则
<子主题，如 "Weapons, ammunition, and explosives">
  Policy                       ← 一句话硬规则
  Examples of what is not allowed:
  In some cases, the following may be allowed:
```
> 该「**禁止清单 + 例外清单**」二元结构是 TikTok 政策页的统一骨架，也是它最接近「案例库」的部分。

**行业分级思路**：TikTok 用**「原则 + 逐例允许/不允许」**表达分级，而非显式的 prohibited/restricted 两级目录。但账号政策页给出了三级**执法**分层（见 B.5）。
> `[推断]`「prohibited industries / restricted industries / editorial」这种三分法是**外部对 TikTok 的通行描述，TikTok 官方政策总页本身并不使用这组词**；官方只按行业主题平铺，并用「In some cases… may be allowed」表达受限。

### B.3 案例库怎么组织（**已打开原文**）
**无独立案例库**。案例 = 每条子政策下的 `Examples of what is not allowed` / `In some cases, the following may be allowed` 清单。逐字示例（`https://ads.tiktok.com/help/article/tiktok-ads-policy-dangerous-products-or-services`）：
> "Weapons, ammunition, and explosives — Policy: We do not allow ad content and landing pages to display or promote the use of dangerous weapons, ammunitions, explosives in real life, or other objects that may cause harm to individuals."
> "Examples of what is not allowed: Blades, knives, or any such sharp objects … Guns, gun parts, and ammunition including paintball guns, and BB guns … Batons, nunchucks, taser guns, pepper spray, or self-defense weaponry"
> "In some cases, the following may be allowed: Toys, water guns, toys that do not look like real weapons … Depictions of weapons in TV dramas, films, and cartoon scenes … Knives* used as utility tools, such as box cutters or pocket knives"
> "*Knives may be allowed in the following markets if the ad is restricted to viewers aged 18 years and older: Austria, Belgium, Bulgaria, Czech Republic, Denmark, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Israel, Luxembourg, Netherlands, Norway, Poland, Portugal, Romania, Spain, Sweden, Switzerland, United Kingdom"

**区域化差异案例库**：`tiktok-ads-policy-healthcare-pharmaceuticals` 页按**国家**列出「Ad topic / Details」，逐字片段：
> "Lebanon — Prescription medicines: Not allowed. Over-the-counter medicines: May be allowed if the following requirements are met…"
> "Bangladesh — Prescription medicine: Not allowed…"
> "**Applicable to: Canada, United States"（处方药例外市场）

**另有一个「市场准入前置审批」案例库**（`market-specific-requirements-for-ad-approval`，逐字）：
> "In some jurisdictions, such as Nigeria, advertisements must be approved prior to publication by the regulatory authority or submitted to the regulatory authority for notification or registration within a certain time period after publication."
> "The Advertising Regulatory Council of Nigeria Act 2022 (the \"ARCON Act\") imposes a general obligation on advertisers and agencies to obtain prior approval of the Advertising Standards Panel (\"ASP\") before publishing any advertisement targeting the Nigerian market."

### B.4 申诉怎么走（**已打开原文** —— 这是三方里最完整的一手申诉文档）
来源：`https://ads.tiktok.com/help/article/advertising-on-tiktok-first-things-to-note`（`Last updated: February 2025`）

**审核要素（人机边界的一半）逐字**：
> "2.2 Ad review process — As part of the TikTok ads review process, we take the following into consideration: Eligibility of the promoted product or services; Ad content which includes: Caption or text, Images or visual content, Audio content, Any other content that forms part of the ad that would be published to target audience; Targeted market and age group; Consistency between an ad and the landing page; Functionality and eligibility of landing page"

**SLA 逐字（关键数字）**：
> "**While some TikTok ads might take longer than usual for the review process to complete, most are reviewed within 24 hours.** Once your ad has been approved and published, you will receive a notification."
> "If the ad is rejected and there are changes that can be made to help publish your ad, you will be notified through Ad Group on the TikTok Ads Manager platform."

**路径一：改稿重提（Edit and submit）逐字**：
> "2.3 Actions to take if rejected — Edit and submit: If your TikTok Ads have been rejected due to non-compliance with our policies, review the details of the disapproval, edit the ad, and submit them for re-review."
> "To edit your ad: Start at your TikTok Ads Manager dashboard. Select Notifications to review the details of rejection. **It will be shown in your Ad Group as suggestions.** Recreate or amend your ad based on the information in the received notification. … Save your changes. Once saved, your ad will be submitted for re-review."

**路径二：申诉（File an appeal）逐字 —— 这就是申诉入口**：
> "File an appeal or get help — **If you cannot edit your ads or feel it was mistakenly rejected, request a review of the decision via Advertiser Support.** Visit our View Campaign or Ad Status | TikTok Ads Manager page for more details."
> "Start at your TikTok Ads Manager dashboard. From the bottom-right corner select the **?** icon.; or From the top-right corner, select **Customer Support**, or from the bottom-right, select the **Help** icon."

**路径三：账号级申诉（最硬的一手 SLA）** —— `https://ads.tiktok.com/help/article/account-suspensions`（`Last updated: June 2026`），逐字：
> "We review ads and account behavior to ensure advertisers follow TikTok's advertising policies. If we find your account isn't following our policies, your account may be suspended. **You can see how well your account and ads align with our policies in the Account Health tab in TikTok Ads Manager.** If your Account Health status says **Attention Needed**, there are issues with your ads or account, and you'll receive warning notifications and suggestions to improve. If your Account Health status is **Poor**, your account will be suspended."
> "Note: Some issues can lead to an immediate suspension if the violation is severe."
> "**Temporary suspension** — If this is your first violation, you'll have **30 days** to address the issues with your ads or ad account or submit an appeal."
> "**Permanent suspension** — If these issues remain or your appeal is rejected after 30 days, the suspension will be permanent. **You won't be able to appeal this decision** and you'll lose access to TikTok Ads Manager features."
> "Common violations that can lead to account suspension: We received reports or complaints about your account from people on TikTok or other channels. / There are problems with your ad content, or qualifications or services provided in your ads. / You made changes to your ad's landing page after creating a campaign. / There is malicious behavior or intent suspected during ad creation. / There is a violation of the TikTok Advertising Guidelines or other standards."

**申诉次数限制（逐字）**：临时停号 = **首个违规给 30 天窗口申诉一次**；**永久停号后「You won't be able to appeal this decision」** —— 即**永久停号为终局，无二次申诉**。
**翻案回流**：**未找到公开资料**（无任何官方文字说明申诉数据反馈进规则）。

### B.5 人机分工边界（**已打开原文**）
`https://ads.tiktok.com/help/article/actor-policy`（Advertiser Account Policy，`Last updated: August 2025`）逐字：
> "Violation review process — … **Our review processes may involve manual reviews or automated tools to detect policy violations and risky behavior.** Depending on the severity of the situation, enforcement actions may include **temporary or permanent suspension from all Bytedance platforms or full traffic control restrictions for TikTok.** These measures are essential to ensure a secure and reliable advertising experience for everyone."
> "To uphold the integrity of our ecosystem, **we reserve the right to evaluate and assess advertiser behavior.**"

**stated thresholds（阈值）** —— TikTok 是三方中唯一给出**可操作状态阈值**的：
> `attention-state = Attention Needed` → 警告 + 改进建议（**不停号**）
> `poor-state = Poor` → **停号**
> `severity gate = "Some issues can lead to an immediate suspension if the violation is severe"`（**绕过分数、直接停号**）
（来源：`account-suspensions`，**已打开原文**）
> 具体分数/数值门槛未公开 → **未找到公开资料**。

**账号被盗的自动处置**（`actor-policy`，逐字）：
> "In the event of a suspected account takeover, the compromised account will be temporarily suspended to mitigate potential harm to both advertisers and users, and the account will be securely restored to its rightful owner."

### B.6 可量化公开数字（**已打开原文**）
- **广告审核 SLA：`most are reviewed within 24 hours`**（`advertising-on-tiktok-first-things-to-note`，`Last updated: February 2025`）
- **账号停号申诉窗：`30 days`**（`account-suspensions`，`Last updated: June 2026`）
- **主动检出率 / 翻案率 / 审核人数量**：**未找到公开资料**（TikTok 未在这两篇中披露任何比例或绝对值）。

### B.7 政策版本化 / 生效日（**已打开原文**）
**每篇政策页顶部均有 `Last updated: <月份 年份>`**，本轮实际取到的版本戳：
| 政策页 | Last updated |
|---|---|
| `tiktok-advertising-policies`（总页） | **August 2025** |
| `advertising-on-tiktok-first-things-to-note` | **February 2025** |
| `market-specific-requirements-for-ad-approval` | **March 2025** |
| `tiktok-ads-policy-dangerous-products-or-services` | **April 2025** |
| `tiktok-ads-policy-alcohol` | **September 2025** |
| `tiktok-ads-policy-deceptive-practices` | **August 2025** |
| `actor-policy` | **August 2025** |
| `account-suspensions` | **June 2026** |
> **独立的「变更日志 / changelog」页面：未找到公开资料** —— TikTok 只给「最近更新时间」，不给历史版本 diff（与 Meta 的 `Change log` 标签不同）。

### B.8 出处链接 + 证据强度（TikTok）
| URL | 内容 | 强度 |
|---|---|---|
| `https://ads.tiktok.com/help/article/tiktok-advertising-policies`（→ `/resources/help/article/...`） | 政策总库分类清单 + `Last updated: August 2025` | 直连 **已打开原文**（HTTP 200） |
| `https://ads.tiktok.com/help/article/advertising-on-tiktok-first-things-to-note` | **审核要素 / 24h SLA / 改稿 / 申诉入口** | 直连 **已打开原文** |
| `https://ads.tiktok.com/help/article/account-suspensions` | **账号健康三态 / 30 天申诉窗 / 永久停号不可申诉** | 直连 **已打开原文** |
| `https://ads.tiktok.com/help/article/actor-policy` | **人机边界 / 处置层级 / 盗号处置** | 直连 **已打开原文** |
| `https://ads.tiktok.com/help/article/tiktok-ads-policy-dangerous-products-or-services` | 禁止+例外二元案例结构 + 区域年龄门槛 | 直连 **已打开原文** |
| `https://ads.tiktok.com/help/article/market-specific-requirements-for-ad-approval` | 尼日利亚 ARCON 前置审批 | 直连 **已打开原文** |
| `https://ads.tiktok.com/help/article/tiktok-ads-policy-healthcare-pharmaceuticals` | 逐国「Ad topic / Details」差异库 | 直连 **已打开原文** |
| `https://ads.tiktok.com/help/article/tiktok-ads-policy-deceptive-practices` | "Accounts that engage in these behaviors or exhibit patterns of abuse may be suspended or banned." | 直连 **已打开原文** |
| `https://ads.tiktok.com/help/article/tiktok-ads-policy-alcohol` | 酒精专项约束 | 直连 **已打开原文** |

---

## C. Amazon

### C.1 它解决什么 / 目标用户
Amazon 侧存在**两套并行的合规体系**，目标用户不同：
1. **Community Guidelines（社区准则）** —— 面向前台用户（买家评论、Q&A、投票、清单、论坛）。**已打开原文**：`https://www.amazon.com/gp/help/customer/display.html?nodeId=GLHXEX85MENUE4XF`
   > "Guidelines for keeping the Amazon Community helpful, relevant, meaningful, and appropriate. The community is a place to share your thoughts and experiences (positive and negative) with other customers. The following guidelines explain what's allowed and not allowed."
2. **上架/卖家合规（listing compliance）** —— 面向卖家（Restricted Products、Condition Guidelines、Product Detail Page Rules、AHR 账号健康）。文件在 Seller Central 内，**需登录**（见 C.8 未打开清单）；公开侧证据来自 Amazon 官方报告页（见 C.2/C.6）。

### C.2 规则库怎么组织

**(a) Community Guidelines —— 结构清晰，已打开原文**
页面给出 `Table of Contents`（逐字两级）：
> "What the guidelines apply to / Who can participate / **What's not allowed**（Seller, order, or shipping feedback; Comments about pricing or availability; Content written in unsupported languages; Repetitive text, spam, or pictures created with symbols; Private information; Profanity or harassment; Hate speech; Sexual content; External links; Ads, conflicts of interest, promotional content; Compensated reviews; Plagiarism, infringement, or impersonation; Illegal activities）/ **Consequences for violations** / How to report violations"

**准入门槛（可量化，逐字）**：
> "**You must have spent $50 on Amazon.com, using a credit or debit card, in the past 12 months, to:** Create reviews (including star ratings) … Answer customer questions … Submit helpful votes … Create idea lists … Follow other contributors … Create posts on Amazon Inspire … Comment on Shop by Interest posts and reply to others' comments"
> "(Note: Promotional discounts don't count towards the $50 minimum spending requirement.)"

**适用范围边界（逐字）**：
> "The guidelines don't apply to content in products or services sold on Amazon (for example, content of a book)."

**(b) 卖家上架侧 —— 分层结构（公开页可证，逐字）**
`https://trustworthyshopping.aboutamazon.com/2025-trustworthy-shopping-experience-report`（**已打开原文**）：
> "Our approach to selection is fundamentally about ensuring customers can always buy with confidence in Amazon's store. **We make decisions at two levels: what products can be sold, and what requirements must be met to sell them.** When determining what to sell, we focus on ensuring products are authentic, safe, and compliant. We may verify supply chains, request safety testing information, or perform other checks to confirm the integrity of products entering our catalog. **For products that are more safety sensitive or require special handling, we may require more robust supply chain documentation, verification of storage and handling practices, and specific sourcing channels or minimum inventory volumes, before a seller can list an offer.**"
> "These controls build on a foundational expectation: **all products sold in Amazon's store must be safe and authentic, and compliant with all applicable laws, regulations, and Amazon policies.**"
> "And that sometimes means **removing selection we believe to be unsafe even if the product meets the prevailing industry standards.**"

**(c) 账号绩效层：Account Health Rating (AHR)**（逐字，同页）：
> "Our **Account Health Rating (AHR)** is one example—a store-level score that reflects a seller's compliance with Amazon policies and potential risks to customers, legal obligations, and reputation of the store. **The score decreases when a seller incurs policy violations and improves through violation resolution and successful order fulfillment.**"

**(d) 评论侧专项政策**（**已打开原文**）：
- `https://www.amazon.com/gp/help/customer/display.html?nodeId=G8CXDFT9GLRRSV3G` —— **Anti-Manipulation Policy for Customer Reviews**
  > "Any attempt to manipulate reviews, including by directly or indirectly contributing false, misleading or inauthentic content, is strictly prohibited."
- `https://www.amazon.com/gp/help/customer/display.html?nodeId=G3UA5WC5S5UUKB5G` —— **Customer Reviews**
  > "**We have a zero tolerance policy for any review designed to mislead or manipulate customers.** We don't allow anyone to write reviews as a form of promotion. The following are types of reviews that we don't allow and will remove: A review by someone who has a direct or indirect financial interest in the product. … A review in exchange for monetary reward. … A negative review from a seller on a competitor's product."
- `https://www.amazon.com/gp/help/customer/display.html?nodeId=GDSRWWGGRA2JXSNZ` —— **About Promotional Content**
  > "promotional content - i.e., an endorsement by someone with a financial or close personal connection to what they're endorsing - is only allowed in limited circumstances, and must always be clearly and conspicuously disclosed as promotional content if not obvious from the context."

### C.3 案例库怎么组织（**已打开原文**）
**无独立案例库**。案例同样以**「不允许清单 + 举例」内嵌**：

Community Guidelines 用**仿真引语**做反例（逐字）：
> "Finding a gift card in your product package. For example: \"You're our lucky winner of a $50 Gift Card! To claim your prize, leave a 5-star review.\""
> "Receiving refund or free replacement offers while asking you to change, remove a negative review or leave a positive review. For example: \"We apologize for any inconvenience regarding your order and would like to offer you a full refund for your purchase. Could you also help by updating your comment for our customer service after receiving your refund?\""
> "Getting messages from sellers or fake review brokers about full reimbursement for buying and reviewing products. … \"Send your order number or a screenshot to support@abcdec.com. Our support team will process a refund for you when you leave us a review.\""
> "Scanning QR codes or following links that require reviews for warranty registration. For example: \"Scan here to qualify for your warranty.\""

Customer Reviews 页用**违规类型清单**（逐字）：
> "A review of a game in exchange for bonus in-game credits. / A positive review from an artist on a peer's album in exchange for receiving a positive review from them."

Promotional Content 页用**场景清单**（逐字）：
> "A product brand posts a review of their own product / A customer posts a review in exchange for cash, a free or discounted product, a gift certificate, or a discount off a future purchase provided by a third party / A customer posts a review in exchange for entry into a contest or sweepstakes or membership in a program"

### C.4 申诉怎么走

**(a) 买家/评论侧 —— 入口明确，已打开原文**
`nodeId=GLHXEX85MENUE4XF` 的 `How to report violations` 给了 **4 条并列入口**（逐字）：
> "**Reporting review compensations** — If someone offers you compensation to create, edit, or remove a review: Fill the **Report Review Compensation form**. Include the product name, upload up to four images, and provide a detailed comment. Select Submit. After we receive your report, we'll investigate and take appropriate action."
> "**Reporting a review** — Locate the review: on the product detail page, find the review you wish to report. Select **Report**. This button is located below the review."
> "**Reporting an issue with the product or seller** — … Scroll down to locate the link labeled **Report an issue with this Product or Seller**. Select the appropriate option from the drop-down menu. Submit your report."
> "**Seller reports of attack by a competitor** — Go to the Seller Central. In Seller Central, find the \"Help\" icon in the top-right corner. **Select \"Get Support\" or navigate to your Account Health Dashboard.** Select Report Abuse or choose the relevant issue from the available options. Select the violation type. Provide the requested details and submit a report."

**(b) 卖家 listing takedown / 账号停用申诉 —— 「Plan of Action」模型**
- **确认存在申诉/恢复通道（已打开原文，官方口径）**：`aboutamazon` 2025 Trustworthy Shopping Experience Report 相关页逐字：
  > "we've invested in tools such as **Amazon's Account Health Dashboard, which gives sellers transparency and control into their adherence to policies, performance targets, and more.**"
  > "**the program is fully integrated into Amazon's Account Health Dashboard**, allowing accredited providers to validate existing documentation or test products, with results submitted directly from laboratories to Amazon."
- **AHR 恢复机制（已打开原文，最接近「翻案回流」的官方表述）**：
  > "The score decreases when a seller incurs policy violations and **improves through violation resolution and successful order fulfillment.**"
- **停号的两种触发（已打开原文，逐字）**：
  > "When AHR suspends a seller, it happens for one of two reasons: **Poor historical performance:** A seller's score falls below our thresholds due to accumulated violations, whether different types of issues or repeat violations of the same policy. **Having a single critical issue:** Immediate zero-tolerance violations, primarily involving abuse, compliance issues, or confirmed counterfeit."
- **POA（Plan of Action）三要素（root cause / immediate corrective action / preventive measures）**：**未找到公开资料** —— 这是业界通行的 Seller Central 申诉模板结构，但本轮**没有取到任何 Amazon 官方页面**以该措辞描述它。`[推断]` 该结构存在于 Seller Central 内部帮助文档（需登录）。
- **申诉 SLA / 处理时限**：**未找到公开资料**。
- **申诉次数限制 / escalation 层级**：**未找到公开资料**。
- **翻案回流规则库**：**未找到公开资料**。`[推断]` "improves through violation resolution" 只说明**账号分数**会随违规解决而回升，并未说明**规则本身**会因申诉翻案而调整。

**(c) 版权/侵权侧（相邻体系，已打开原文发现入口）**
- `https://sell.amazon.com/programs/ip-accelerator`（Amazon Intellectual Property Accelerator）
- `https://sell.amazon.com/brand-registry/project-zero`、`https://sell.amazon.com/brand-registry/transparency`
- `https://www.aboutamazon.com/about-us/public-policy/counterfeits`
（以上来自 `sell.amazon.com/sitemap.xml` 与 `aboutamazon.com/sitemap.xml` 的**实际抓取结果**，非猜测）

### C.5 人机分工边界（**已打开原文**）
**卖家上架侧（最具体的一段官方描述）** —— `https://www.aboutamazon.com/news/company-news/product-safety-and-compliance-in-our-store`，逐字：
> "Our proactive measures begin when a seller attempts to open an account. **Our new seller account vetting includes a number of verifications and uses proprietary machine learning technology that stops bad actors before they can register or list a single product in our store.**"
> "**We have a dedicated global team of compliance specialists that review submitted safety documentation**, and we have additional qualification requirements that sellers must meet to offer products."
> "Once a product is available in our store, **we continuously scan our product listings and updates to find products that might present a concern. Every few minutes, our tools review the hundreds of millions of products, scan the more than five billion attempted daily changes to product detail pages, and analyze the tens of millions of customer reviews that are submitted weekly** for signs of a concern and investigate accordingly. **Our tools use natural language processing and machine learning, which means new information is fed into our tools daily so they can learn and constantly get better at proactively blocking suspicious products.**"
> "if a customer reports a concern with a product, **a customer service associate can instantly trigger an investigation.**"

**卖家侧 2025 口径（更细，已打开原文）** —— `trustworthyshopping.aboutamazon.com/2025-...report`，逐字：
> "All new sellers are required to complete Amazon's robust verification process before they are allowed to sell in Amazon's store. We then continuously monitor activity throughout a seller's journey, with our automated technology and artificial intelligence (AI) scanning billions of attempted changes to product detail pages daily for signs of potential abuse. **Multimodal systems also analyze billions of signals simultaneously—including text, images, seller behavior, and supply chain patterns—to identify potential abuse before it reaches customers.**"
> "We launched our **direct product validation program** to allow us to work directly with **accredited safety laboratories** to verify the compliance of products in our store. We deployed **Omniscan**—an advanced machine learning system that verifies the readability and language of essential safety details at scale before products are listed—across our global fulfillment network in the U.S., Canada, UK, Türkiye, Saudi Arabia, and Europe. **The system generated image sets for more than 12 million products.**"
> "To protect the integrity of customer reviews, **our systems analyze thousands of data points across billions of reviews before a review appears in the store**, drawing on review data that dates back to 1995 to help detect fake or abusive content. **In 2025, we proactively blocked hundreds of millions suspected fake reviews from our store.**"
> "We have begun leveraging **new agentic AI that continuously scans for products that may have evaded our existing controls—serving as an audit** and furthering our ability to surface potential risks. These agentic audits on top of customer feedback, regulatory developments, and insights from our expert teams, support our constant refinement and evolution of our safety policies."

**买家评论侧（已打开原文）** —— `nodeId=GLHXEX85MENUE4XF`，逐字：
> "**Amazon invests significant resources to stop fake reviews before our customers find them. We use a combination of sophisticated tools and expert investigators to find and stop abusive behavior.** Our team takes legal action against fake review brokers who try to deceive our customers."
> "If we find unusual reviewing behavior, we might limit the ability to submit reviews."

**stated thresholds（阈值，已打开原文）** —— 结构化阈值只有一个：AHR「score falls below our thresholds」（**未给出具体分数**）；另有「single critical issue」零容忍直通。**具体数值「未找到公开资料」。**

### C.6 可量化公开数字（**已打开原文**）
| 数字 | 逐字原文 | 来源 |
|---|---|---|
| 2018 年投入 **over $400 million** 保护店铺 | "In 2018 alone, we invested over $400 million to protect our store and our customers" | aboutamazon 产品安全页 |
| 2018 年**主动拦截 3 billion+ 可疑 listing** | "In 2018, our teams and technologies **proactively blocked more than three billion suspect listings** for various forms of abuse, including non-compliance, **before they were published to our store.**" | 同上 |
| 每日扫描 **5 billion+** 详情页改动 | "scan the more than **five billion attempted daily changes to product detail pages**" | 同上 |
| 每周分析 **tens of millions** 评论 | "analyze the **tens of millions of customer reviews** that are submitted weekly" | 同上 |
| **99.9%+ 侵权 listing 主动拦截** | "Amazon's proactive controls **blocked more than 99.9% of suspected infringing listings before a brand owner ever had to find and report them.**" | 2025 Trustworthy Shopping Experience Report |
| 2020 至今 **32,000+ bad actors** 被追诉，跨 **14 国** | "Since 2020, Amazon's Counterfeit Crimes Unit has pursued **more than 32,000 bad actors** through litigation and criminal referrals to law enforcement, **across 14 countries**." | 同上 |
| 2025 年查获处置 **15 million+ 假货** | "In 2025, we identified, seized, and appropriately disposed of **more than 15 million counterfeit products** worldwide" | 同上 |
| 2025 年关停 **100+ 假评/诈骗网站** | "our legal actions led to the shutdown of **more than 100 websites** attempting to facilitate fake reviews and scams" | 同上 |
| 2025 年拦截 **hundreds of millions 假评** | "In 2025, **we proactively blocked hundreds of millions suspected fake reviews** from our store." | 同上 |
| Omniscan 生成 **12 million+ 商品**图像集 | "The system generated image sets for **more than 12 million products.**" | 同上 |
| 早预警系统**提前 8 天**拦截 | "blocking the infringing listings **a full eight days before the brand owner even shared their IP with us.**" | 同上 |
| 中国执法协作 **70+ 次线下突击** | "led to **more than 70 successful local raid actions** against manufacturers, suppliers, and distributors of counterfeit products" | 同上 |
| **100%** 新卖家须完成验证 | "**100% of new sellers** are required to complete Amazon's robust verification process before they are allowed to sell in Amazon's store." | 同上 |
| 评论准入门槛 **$50/12 个月** | "You must have spent **$50 on Amazon.com**, using a credit or debit card, **in the past 12 months**, to: Create reviews…" | Community Guidelines |
| 举报补偿可传 **4 张图** | "upload up to **four images**" | Community Guidelines |
| SENTRIX 钓鱼 URL 下架 **+10%** | "have increased successful phishing URL takedowns by **more than 10%**." | 同上 |
| 与 **34 家**消费者组织、**71 个**议题、**7 国**合作 | "partnered with **34 consumer organizations** to deliver safety information on **71 key topics across seven countries**" | 同上 |
| **10 个** ORC 特别工作组 | "We are also a member of **10 organized retail crime task forces** led by attorneys general across the United States." | 同上 |

**未找到公开资料的量化项**：申诉**翻案率**、listing 上架审核**平均时长/SLA**、申诉**处理时长**。

### C.7 政策版本化 / 变更日志
- Community Guidelines 有**"我们会更新"的表述但无 changelog**（逐字）：
  > "By using community features, you agree to our Conditions of Use and Privacy Notice. You also agree to follow these guidelines, **which we update from time to time.**"
- **Conditions of Use 有明确生效日**（逐字，`nodeId=GLSBYFE9MGKKQXXM`）：
  > "**Last updated: August 14, 2026**"
- **独立政策变更日志（changelog）**：**未找到公开资料**。
- AHR / 上架政策的版本号：**未找到公开资料**。
- 但有**年度报告机制**可作事实上的「版本快照」：`https://trustworthyshopping.aboutamazon.com/2025-trustworthy-shopping-experience-report`（2025 年首份 Trustworthy Shopping Experience Report，逐字）：
  > "For the past five years, Amazon has published an annual **Brand Protection Report**… That's why today we're releasing Amazon's **Trustworthy Shopping Experience Report**, providing a comprehensive look at how we're protecting customers, selling partners, and brands across our global store. **The report expands our commitment to trust and safety, continuing to cover brand protection and anti-counterfeiting, but now also encompassing organized retail crime, product safety, scam prevention, and trustworthy reviews.**"

### C.8 出处链接 + 证据强度（Amazon）

**✅ 已打开原文**
| URL | 内容 |
|---|---|
| `https://www.amazon.com/gp/help/customer/display.html?nodeId=GLHXEX85MENUE4XF` | Community Guidelines 全文（TOC、$50 门槛、不允许清单、**违规后果四级**、4 条举报入口） |
| `https://www.amazon.com/gp/help/customer/display.html?nodeId=G8CXDFT9GLRRSV3G` | Anti-Manipulation Policy for Customer Reviews |
| `https://www.amazon.com/gp/help/customer/display.html?nodeId=G3UA5WC5S5UUKB5G` | Customer Reviews（zero tolerance policy） |
| `https://www.amazon.com/gp/help/customer/display.html?nodeId=GDSRWWGGRA2JXSNZ` | About Promotional Content |
| `https://www.amazon.com/gp/help/customer/display.html?nodeId=GPEWN3RSQPEU2HST` | Amazon Vine |
| `https://www.amazon.com/gp/help/customer/display.html?nodeId=GLSBYFE9MGKKQXXM` | Conditions of Use（`Last updated: August 14, 2026`） |
| `https://www.aboutamazon.com/news/company-news/product-safety-and-compliance-in-our-store` | 人机分工 + 2018 量化数字 |
| `https://www.aboutamazon.com/news/policy-news-views/amazon-trustworthy-shopping-experience-report-2025` | Trustworthy Shopping 报告导读 + AHR 引言 |
| `https://trustworthyshopping.aboutamazon.com/2025-trustworthy-shopping-experience-report` | **AHR 停号双因 / 两层选品决策 / 99.9% / 32,000 / 15M / 100+ / 12M / 70+ / 100%** |
| `https://www.aboutamazon.com/news/how-amazon-works/creating-a-trustworthy-reviews-experience` | （已抓取）评论信任体验 |
| `https://www.aboutamazon.com/news/policy-news-views/how-amazon-is-working-to-stop-fake-reviews` | （已抓取）假评治理 |
| `https://www.aboutamazon.com/news/policy-new-views/amazon-brand-protection-report-2024-counterfeit-products` | （已抓取）2024 品牌保护报告 |
| `https://sell.amazon.com/sitemap.xml` / `https://www.aboutamazon.com/sitemap.xml` | 用于**发现**上述真实 URL（非猜测） |
| `https://sell.amazon.com/robots.txt` | 发现 sitemap |

**❌ 未打开（明确列出）**
| URL | 失败原因 |
|---|---|
| `https://sellercentral.amazon.com/gp/help/G200164650`（Restricted products） | HTTP 200 但**正文仅 1840 字符的营销外壳**，无政策正文（JS 加载 + 需登录） |
| `https://sellercentral.amazon.com/help/hub/reference/G200164650` | **302 跳到 `ap/signin` 登录页** |
| `https://sellercentral.amazon.com/help/hub/reference/external/G200164650` | 同上，仅外壳 |
| `https://sellercentral.amazon.com/gp/help/customer/display.html?nodeId=G200164650` | 仅外壳 |
| `G201844550` / `G200390890` / `G1791` / `G200444500` / `G2356341300` / `G201844590`（均试 `gp/help/external/` 与 `help/hub/reference/external/` 两种形式，共 14 次请求） | 全部仅外壳或登录跳转 |
| `https://web.archive.org/web/2024/<上述 sellercentral URL>` | Wayback 无有效存档（返回 0 字节 / 4695 字节登录壳 / 仅 645 字符） |
| `https://sellercentral.amazon.com/help/api/hub/article?articleId=G200164650` | HTTP **404** |
| `https://sell.amazon.com/policies`、`https://sell.amazon.com/help`、`https://sell.amazon.com/learn/product-compliance`、`https://sell.amazon.com/learn/restricted-products` | 全部 **HTTP 404** |
| `https://brandservices.amazon.com/trustworthy-shopping-experience-report` | 302 到 `sell.amazon.com/brand-registry`（非目标页） |
| `https://www.aboutamazon.com/news/innovation-at-amazon/amazon-brand-protection-report-2023` 等 3 个猜测 URL | **HTTP 404**（已从 sitemap 换成真实 URL） |

---

## D. 交叉结论（回答「Specifically hunt for」七项）

1. **规则库组织**：Meta = 两轴大类 + 二级叶子政策（**唯一有显式变化日志标签的**）；TikTok = 平铺主题清单（21 主题 + 22 资源），**政策页内是「禁止清单 + 例外清单」二元式**；Amazon = **按对象分体系**（买家社区 / 卖家上架 / 账号绩效 AHR），上架侧显式「两层决策：能卖什么 + 卖它需要满足什么」。
2. **分级执法原文**：
   - Meta：`remove / reduce / inform` + `strike system` + `"account may also be restricted or disabled"`
   - TikTok：`Attention Needed`（警告）→ `Poor`（停号）→ `temporary`（30 天）→ `permanent`（不可申诉）；`"may include temporary or permanent suspension from all Bytedance platforms or full traffic control restrictions for TikTok"`
   - Amazon：`Remove their content / Limit their ability to use community features / Suspend or terminate their account / Withhold payments`；上架侧 AHR 双因停号
3. **申诉入口**：Meta 内容侧 = Support Inbox「request another review」；TikTok = Ads Manager `?`/`Customer Support` → Advertiser Support；Amazon = Report 按钮 / Report Review Compensation 表单 / Account Health Dashboard。
   **SLA**：仅 TikTok 公开 `most are reviewed within 24 hours` + `30 days` 申诉窗。**次数限制**：仅 TikTok 明确「永久停号不可再申诉」。**翻案回流**：**三方均「未找到公开资料」**。
4. **人机边界**：三方都**明确采用「AI/ML 预筛 → 人工兜底/升级」**，且都用相似措辞（Meta："where our technology misses something or needs more input"；TikTok："may involve manual reviews or automated tools"；Amazon："proprietary machine learning technology" + "dedicated global team of compliance specialists"）。**三方均未公开任何数值型触发阈值。**
5. **可量化公开数字**：Meta 只有 `15,000+ reviewers` / `80+ languages`；TikTok 只有 `24h` / `30 days`；**Amazon 数字最丰富**（99.9% 主动拦截、3B 拦截 listing、32,000 bad actors、15M 假货、$400M 投入、12M Omniscan、100% 新卖家验证、70+ 突袭、$50 评论门槛）。**三方的「申诉翻案率」全部未找到公开资料。**
6. **版本化**：Meta 每政策页有 `Change log`（含日期版本）；TikTok 每页有 `Last updated:` 月份（无历史 diff）；Amazon 只有条款类有 `Last updated`，**无政策 changelog**。
7. **证据缺口（重要）**：**Meta 的广告审核与申诉流程官方说明完全落在 `facebook.com/business/help/` 内，而该域名在本环境下直连返回 400、Wayback 无存档** —— 因此 Meta 侧的「广告审核 SLA / 人审介入条件 / 广告申诉入口原文」本轮**确实未能取得**，请勿以二手资料替代。

---

## E. 本次采集的方法与限制（可复现）
- **可用**：`curl -sL --max-time 40 -A "<Chrome UA>"`；`ads.tiktok.com`、`amazon.com/gp/help`、`aboutamazon.com`、`sell.amazon.com`、`trustworthyshopping.aboutamazon.com` 直连可用。
- **Wayback 前缀 `https://web.archive.org/web/2024/<url>`**：对 `transparency.meta.com` **有效且必需**（直连返回 HTTP 400 + 265KB 空壳，正文长度 0）。但 Internet Archive 本次会话中**间歇性宕机**（多次返回 `Internet Archive: Temporarily Offline` 或 `000` 连接失败），需重试循环；其 **CDX 索引 API 在会话前半段超时，后半段恢复**，本报告 Meta 分类树即来自 CDX 恢复后的 1500 条存档 URL 列表。
- **不可用**：`web_search`、`exa_search`、`read_page`（配额/密钥问题）；`facebook.com` 全站对本 UA 返回 400 空壳；`sellercentral.amazon.com` 正文需登录且无 Wayback 存档。
- **未使用的替代手段**：本会话**无法启动子代理**（`subagent depth 4 exceeds maxDepth 3`），全部抓取由主线完成。
- **未做的事**：未使用任何二手/媒体/第三方博客作为证据；所有引文均来自我实际抓取到正文的页面。猜测性 URL 均在报告中标注为失败项。
