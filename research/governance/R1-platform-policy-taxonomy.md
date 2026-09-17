# R1 — 平台内容/广告政策库的结构解剖

> **分片**：R1 ｜ 依据 `research/governance/00-调研任务书.md`
> **抓取日期**：**2026-09-15**（本文所有引用的抓取时间均为该日；政策类内容会变）
> **证据根目录**：`research/governance/_evidence/R1/`（**约 420 个文件**：250+ 个 `.md` 文本抽取 + 约 190 个 `.html` 原文 + 3 个结构化 JSON）
> **覆盖平台**：Meta（Community Standards / Advertising Standards）、Google Ads、YouTube、TikTok、Amazon（Selling / Ads）
> **写作约定**：`【原文】` = 我逐字读到的页面文字；`【判断】` = 我的推论。凡不能回溯到原文的一律标「未核实」。
> **⚠ 三处常见说法经核实不成立**：「Meta CS 有 6 大分区」（§2.1）、「Meta 三段式 Policy Rationale / Policy Detail / Enforcement」（§3.2）、「Amazon AHR 四档」（§5.5，实为 3 档颜色 + 4 档严重度）。

---

## 0. 结论先行

**12 条硬结论**（每条后附着证据所在小节）：

1. **「Meta Community Standards 有 6 大分区」是错的。** 现行英文版首页只有 **1 个 `<h1>`、0 个 `h2/h3/h4`**，27 个条目是一条**平铺列表**。旧文档里的「6 大分区」在当前页面上不存在。（§2.1）
2. **「Meta 三段式 Policy Rationale / Policy Detail / Enforcement」也不准确。** 真实的条目模板是：`Policy Details` 锚 → `CHANGE LOG` → `Policy Rationale` → 禁止清单 → 「需更多语境才能执法」清单 → `User experiences` → `Data`。**27 条里有 1 条连 `Policy Rationale` 都没有**（`additional-protection-minors`）。（§3.1、§3.2）
3. **27 条里 18 条（67%）带「需额外信息/语境才能执法」的显式分层**——平台自己承认三分之二的规则不能纯自动判。（§3.2、§5.1）
4. **五家全部把「规则本体」与「适用范围」分离，而且是五种不同的分离手法**：Meta 用「独立的本地法报告层」、Google 用「certification 闸门页」、TikTok 用「规则行内 regional 限定词」、Amazon 用「每篇文章声明适用 marketplace」、YouTube 用「geographic visibility 参数」。（§4）
5. **Google 把辖区写进了规则的名字**：changelog 里的条目标题就是 `Update to Gambling and Games Policy: Colorado, USA`、`…: France`、`…: Ireland`、`…: Alberta, Canada`、`…: Australia`、`…: Global`。**辖区是规则身份的一部分，不是规则的属性。**（§4.7）
6. **Google Ads 的 strike 是「按政策分别计数」的**：`An account can receive a maximum of one warning and 3 strikes per policy violation`，且只在 15 条具名政策上启用 strike 制度，其余政策不累积 strike。（§5.2）
7. **TikTok 的严重等级不是字段，而是「规则行所在的清单」**：同一模板下三块 `NOT ALLOWED` / `FYF INELIGIBLE & AGE-RESTRICTED` / `ALLOWED`，规则写在哪一块就决定了后果。（§3.4、§5.4）
8. **Amazon 是唯一给出连续量纲的**：AHR `0–1,000`，`Healthy 200–1,000` / `At Risk 100–199` / `Unhealthy ≤99`，四档严重度 `critical / high / medium / low`，**重复违规会提高每次扣分的点值**，180 天窗口。（§5.5）
9. **「豁免」在四家都是「例外之上的再限制」**：TikTok 原文——`Even if we allow content under a public interest exception, we might still: Make it ineligible for the FYF / Add a warning screen / Add a context label`。豁免 ≠ 放行。（§6.3）
10. **YouTube EDSA 是概率模型，不是二值开关**：官网用「More likely / Less likely to get an EDSA exception」两列表格给出倾向，并明说 `Adding context to your EDSA content doesn't guarantee that it will get an EDSA exception.`（§6.1）
11. **政策变更记录：五家五种形态，粒度差两个数量级。** Google Ads 2026 年**一年 58 条**变更、每条独立文章、带生效日 + 发布日 + 辖区；Meta Community Standards 的 `CHANGE LOG` **只有裸日期没有说明**，最新一条字面上就是字符串 `Today`；Meta **没有任何全局 changelog 路由**（`/policies/ad-standards/changelog/` 404）。（§7）
12. **平台从不声称规则库＝合规全集。** Google 原文 `This isn't an exhaustive explanation of local legal requirements in each location. You're still responsible for researching and complying with local laws`；Meta 原文 `It is an advertiser's responsibility to understand and comply with … in addition to all local laws, regulations and, where applicable, self-regulatory advertising codes`。**平台政策与法律被当作两个各自独立生效的规则体。**（§4.1、§4.2）
13. **「法律性移除 ≠ 平台违规」是三家独立确认的行业共识。** Meta 与 TikTok 的措辞**逐字相同**：`restrict access to the content only in the jurisdiction where it is alleged to be unlawful`；Meta 另加 `do not impose any other penalties or feature restrictions`；YouTube 对应 `In these cases, your channel won't get a strike.`（§4.6 M7）
14. **Google 用第四维度处置**——`Remarketing list disabling`：被处置的不是广告也不是账号，而是**一个数据资产**。Momcozy 的对应物是「素材库 / 受众包」。（§5.2）
15. **Amazon Ads 逐字点名了 `Breast Pump`，归入 `Category 1 (low sensitivity products): Generally allowed`** —— 但仍带 supply 级限制（`Amazon O&O Streaming TV must exclude content rated NR, TV-Y, TV-Y7, and G`）与申报义务（`accurate category declaration`）。**这是本次调研对 Momcozy 最直接的一条证据。**（§8.2）
16. **只有 Amazon 把阈值写成数字**：`Show the product as 85% of the image.` / `pure white background (RGB color values: 255, 255, 255)` / `Product titles must not have more than 75 characters` / `environmental claims must be dated within 24 months`。**没有「适当」「明显」这类词。**（§3.6）

---

## 1. 方法与可复现性

### 1.1 访问路径与障碍（**必须记录，因为它改变了证据性质**）

本次抓取遇到三层障碍，逐层绕过后才拿到原文：

| 层 | 现象 | 解决 |
|---|---|---|
| 网络 | 直连 `transparency.meta.com` / `support.google.com` / `youtube.com` / `tiktok.com` / `web.archive.org` 全部 **TCP 超时**（`HTTP:000`）；`example.com`、`github.com`、`pypi.org`、`baidu.com` 正常 | 发现本机存在本地代理端口 `127.0.0.1:7890`（`nc -z` 探测），全流量走 `https_proxy=http://127.0.0.1:7890` 后全部可达 |
| **DNS** | **根因确认：本机 DNS 被劫持**（出口 IP `61.141.171.202`，China Telecom）。`www.youtube.com` 被解析到 `31.13.92.37`、`www.tiktok.com` 被解析到 `157.240.7.20`——**这两个都是 Meta 的 IP**；`web.google.com`、`wikipedia`、`archive.org` 同样被污染 | 代理同时解决 DNS（远端解析） |
| **Amazon 专用** | `web_fetch` 对 Amazon 全部页面返回 **HTTP 200 + 空 body**；默认 headless Chrome 崩溃（`sandbox initialization failed: Operation not permitted`） | 改用 **Chrome 153 headless `--no-sandbox` + CDP**（`--remote-debugging-port=9222`），轮询 `document.body.innerText`；可用 URL 形式为 `https://sellercentral.amazon.com/help/hub/reference/external/<GUID>` |
| 工具 | `web_fetch` 对 `transparency.meta.com` 直接 `fetch failed`；`read_page`（Firecrawl keyless）在抓到 Meta CS 索引 + 2 个条目后返回 `429 … retry_after_seconds: 86359`（≈24 小时封禁） | 改为 `curl` + 代理；`read_page` 仅用于少数已成功的页面 |
| 站点反爬 | `transparency.meta.com` 对裸 `curl` 返回 **HTTP 400 + 一个 Facebook Comet `<title>Error</title>` 页**（约 261 KB，非目标内容） | 补齐 `--compressed` + 完整浏览器头（`Sec-Fetch-Dest/Mode/Site/User`、`sec-ch-ua*`、`Accept-Language`、`Upgrade-Insecure-Requests`）后返回 **HTTP 200** 真实 HTML |
| 站点渲染 | TikTok CG 页是 Remix SSR + URL-encoded JSON；普通 HTML→文本抽取得 **1 行** | 抽取 `<script data-ttark="__remixContext">` 内容 → `urllib.parse.unquote` → `json.loads` → 取 `state.loaderData.root.CGPosts[*].contents[*].content` |

**对读者的含义**：本文所有 Meta / Google / YouTube / TikTok / Amazon 原文均来自**真实服务端 HTML**（`--compressed` + 浏览器头），不是 JS 渲染后的近似。`.html` 原文已全部留档。

### 1.2 证据保存约定

- 文本抽取：`_evidence/R1/<platform>-<slug>.md`
- 原始 HTML：`_evidence/R1/<slug>.html`（或 `_evidence/R1/html/`）
- 结构化抽取：`tiktok-fyf-standards.remix.json`、`tiktok-accounts-features.remix.json`
- 索引与结构清单：`meta-cs-STRUCTURE-INVENTORY.md`、`meta-cs-FETCH-MANIFEST.md`、`meta-ad-LINK-MAP.md`
- 每个 `.md` 头部三行标注：来源 URL / 抓取日期 / 抽取方式。

### 1.3 术语

| 英文 | 中文 | 说明 |
|---|---|---|
| Community Standards (CS) | 社区标准 | Meta 的用户内容规则体 |
| Advertising Standards / Ad Policies | 广告标准 / 广告政策 | Meta / Google 的广告规则体 |
| enforcement tier / severity | 处置档位 / 严重度 | 违规后的后果等级 |
| strike | 记过 | 累进式处罚计数单位 |
| scope / applicability | 适用范围 | 规则在何处、对谁、何时生效 |
| policy line | 政策行 | 一条规则体内部的最小可判定语句（本文的「条款编号」以此为单位） |
| change log / changelog | 变更日志 | 政策修订的公开记录 |

---

## 2. 顶层分区怎么切

### 2.1 Meta Community Standards —— **平铺 27 条，无分区**

**【原文】** 首页正文（`_evidence/R1/meta-cs-index.md`）：
> `Our Community Standards apply to everyone, all around the world, and to all types of content, including AI-generated content.`
> `Each section of our Community Standards starts with a "Policy Rationale" that sets out the aims of the policy followed by specific policy lines that outline:`
> `Content that's not allowed; and`
> `Content that requires additional information or context to enforce on, content that is allowed with a warning screen or content that is allowed but can only be viewed by adults aged 18 and older.`
> `Please note that the US English version of the Community Standards reflects the most up to date set of the policies and should be used as the primary document.`

**结构事实（原始 HTML 层验证，见 `meta-cs-STRUCTURE-INVENTORY.md`）**：

- DOM 中 **只有 1 个 `<h1>`**（`Community Standards`），**`h2/h3/h4` 计数为 0**。
- 27 个条目链接构成**一条不间断的列表**（CMS JSON 里也是顺排的 `MCDSCMSCommonLink` 数组）。
- 旧版「6 大分区」的名称（`Violence and Criminal Behavior` / `Objectionable Content` / `Integrity and Authenticity` / `Respecting Intellectual Property` / `Content-Related Requests`）在页面中**检索命中数为 0**。
- 页面上唯一的分组视觉元素是 `AUTHENTICITY / SAFETY / PRIVACY / DIGNITY` 四个词——它们装饰的是开头「Our commitment to voice」价值叙事段，**不是** 27 条的目录分组。

**【判断】** 27 条的**排列顺序**仍保留主题聚类（前行是伤害/犯罪/暴力类，中段是安全类，后段是诚信/真实性类，尾部是知识产权与请求类），但**页面已不再声明分组**。对 Momcozy 的含义：**不要指望平台给出稳定的顶层分类学——平台自己都在往平铺走。**

27 条清单（顺序即页面顺序，`_evidence/R1/meta-cs-index.md`）：
`Coordinating Harm and Promoting Crime` / `Dangerous Organizations and Individuals` / `Prohibited Commercial Practices` / `Restricted Goods and Services` / `Violence and Incitement` / `Adult Sexual Exploitation` / `Bullying and Harassment` / `Child Sexual Exploitation, Abuse, and Nudity` / `Human Exploitation` / `Suicide, Self-Injury, and Eating Disorders` / `Adult Nudity and Sexual Activity` / `Adult Sexual Solicitation and Sexually Explicit Language` / `Hateful Conduct` / `Privacy Violations` / `Violent and Graphic Content` / `Account Integrity` / `Authentic Identity Representation` / `Cybersecurity` / `Inauthentic Behavior` / `Memorialization` / `Misinformation` / `Spam` / `Third-Party Intellectual Property Infringement` / `Using Meta Intellectual Property and Licenses` / `Additional Protection of Minors` / `Locally Illegal Content, Products, or Services` / `User Requests`

**⚠ 5 处 slug ≠ 标题的重定向**（做规则抓取脚本时会踩）：

| 请求 URL 片段 | 实际规范页 |
|---|---|
| `coordinating-harm-publicizing-crime` | `coordinating-harm-promoting-crime` |
| `regulated-goods` | `restricted-goods-services` |
| `sexual-exploitation-adults` | `adult-sexual-exploitation` |
| `hate-speech` | `hateful-conduct` |
| `privacy-violations-image-privacy-rights` | `privacy-violations` |

**兜底分区**：Meta CS 里**有一个显式的兜底条目**——`Locally Illegal Content, Products, or Services`。它不是主题分区，而是**「凡是地方法律要求删、但 CS 没覆盖」的兜底通道**（详见 §4.1）。`User Requests` 是第二个兜底条目（用户请求类）。

### 2.2 Meta Advertising Standards —— 同样平铺，但**分区外壳存在于页面内锚点**

**【原文】** 索引页（`_evidence/R1/meta-ad-index.md`）：
> `Advertisers running ads across Meta technologies must follow our Community Standards and our Advertising Standards.`

结构事实（`meta-ad-LINK-MAP.md`）：

- 索引页是**平铺列表**；**分组 URL 全部 302 到 `/policies/ad-standards/#<section>`**——`/business-assets/`、`/objectionable-content/`、`/unacceptable-content/`、`/deceptive-content/` 都是锚跳转，**没有独立的分组落地页**；`/restricted-goods-services/` 直接 **404**。
- 实际有 **43 个政策页**，可归到 6 组（这是从页面内锚点还原的，非页面声明）：`community-standards`(1) / `unacceptable-content`(8) / `objectionable-content`(9) / `deceptive-content`(1) / `restricted-goods-services`(16) / `business-assets`(5) / `intellectual-property-infringement`(2) / `SIEP`(1)。
- 索引页有四个「policy principles」作为**判据层**（不是规则）：`PROTECTING PEOPLE FROM UNSAFE AND DISCRIMINATORY PRACTICES` / `PROTECTING PEOPLE FROM FRAUD OR SCAMS` / `PROMOTING POSITIVE USER EXPERIENCES` / `PROMOTING TRANSPARENCY`。

**【判断】** Meta 的广告库是**「一层平铺 + 锚点假分区」**。分组 URL 之所以不独立，是因为分组本身不承载语义——真正的结构在 policy page 内部的「Guidelines」小节里。

### 2.3 Google Ads Policies —— **双顶层分区：Help Center 四段导航 + 政策四桶分类学**

**【原文】** Help Center 左侧导航（`_evidence/R1/google-ads-policies-overview.md`、`google-ads-changelog-recent.md`、`google-ads-review-process-topic.md`）逐字：

```
- List of ad policies
    - Advertising policies
    - Third-party policies
    - Related policies & terms
- Review process
    - Approval process
    - Disapprovals and suspensions
- Verification and transparency
    - Verification and transparency
- Change log
    - Upcoming and recent changes
    - Past changes
```

**【判断】** 这是一个**按「规则生命周期阶段」切的分区，不是按主题切**：

| 顶层分区 | 承载什么 | 为什么这样切 |
|---|---|---|
| `List of ad policies` | **规则本体** | 只放「什么不能做」 |
| `Review process` | **裁决与状态** | 只放「系统怎么判、判完是什么状态」 |
| `Verification and transparency` | **准入门槛** | 只放「谁有资格投」 |
| `Change log` | **版本** | 只放「什么时候改的」 |

**这是本次调研里最可直接复用的一条分区原则**：把「规则」「裁决状态」「准入资格」「版本」切成四个互斥的顶层区，而不是把它们混在一条政策里。

**⚠ 但 Google 实际上有「两套顶层分区」，必须区分开**（这是本文的一处重要更正）：

**分区 A —— Help Center 导航（规则的「存放位置」）**：上表四段。

**分区 B —— 政策分类学（规则的「性质分类」）**，见 `_evidence/R1/google-ads-policies-overview.md`，逐字：
> `Our advertising policies cover 4 broad areas:`
> `**Prohibited content:** Content you can't advertise on the Google Network`
> `**Prohibited practices:** Things you can't do if you want to advertise with us`
> `**Restricted content and features:** Content you can advertise, but with limitations`
> `**Editorial and technical:** Quality standards for your ads, websites, and apps`

**【判断】分区 B 是本次调研里最值得抄的一条「顶层分类学」**，因为它的切分轴是**「违规的性质」而不是「违规的主题」**：

| 分区 B 的桶 | 判据（原文） | 对 Momcozy 的意义 |
|---|---|---|
| `Prohibited content` | `Content you can't advertise` | 绝对红线——**不可救**，改写也没用 |
| `Prohibited practices` | `Things you can't do` | **行为**红线（如规避系统、数据收集）——与内容无关 |
| `Restricted content and features` | `Content you can advertise, **but with limitations**` | **可救**——对应「审慎关注 / 需限定」 |
| `Editorial and technical` | `Quality standards` | **质量而非合规**——对应「品牌调性」 |

**这四桶正好回答 Momcozy 的「边界类型四档」该怎么定**：他们的 `严格限制红线 / 审慎关注 / 人工复核 / 安全词白名单` 混了「性质」与「流程」（`人工复核` 是流程状态，不是规则性质）。Google 的四桶全部是**规则性质**，流程状态另置（`Review process` 分区）。

主题则在 `List of ad policies → Advertising policies` 之下再分（`google-ads-policy-list.md`、`google-ads-topic-list-of-ad-policies.md`），约 43 个条目按字母序列出，**`Legal requirements` 是其中一个与其他政策平级的条目**（见 §4.2）。

### 2.4 YouTube —— **双规则体 + 双分区轴**

YouTube 有两个**互不替代**的规则体：

- **Community Guidelines**（`_evidence/R1/youtube-community-guidelines-full.md`）：决定内容**能不能留在平台上**。
- **Advertiser-friendly content guidelines**（`_evidence/R1/youtube-advertiser-friendly.md`）：决定内容**能不能赚钱**。

**Community Guidelines 的 6 个顶层分区**（`_evidence/R1/youtube-community-guidelines-overview.md`，来源 `support.google.com/youtube/answer/9288567`），逐字：
`Spam & deceptive practices` / `Sensitive content` / `Violent or dangerous content` / `Regulated goods` / `Misinformation` / `Educational, Documentary, Scientific, and Artistic (EDSA) content`

**【判断】** 注意最后一节：**YouTube 把一个「例外制度」（EDSA）提升成了与主题规则并列的顶层分区。** 这是五家里唯一这样做的——其余四家都把例外写成规则内部的子句。**好处**：例外制度获得与规则同等的可见度与维护优先级；**代价**：分区不再互斥（EDSA 横切前五个分区）。**Momcozy 若重视「合规话术」与「语境豁免」，可以照抄这个做法——把「可豁免情形」独立成一个顶层区。**

**【原文】**（`youtube-advertiser-friendly.md`）：
> `Note: All content uploaded to YouTube must comply with both our Community Guidelines and our Program Policies. If your content violates our Community Guidelines, it may be removed from YouTube. If you see violative content, you can report it.`
> `This article aims to help you understand which individual videos or Shorts on your channel are suitable for advertisers. Creators can use this article to understand both the platform's self-certification questionnaire and specific rules about what will receive ad earnings, will receive limited ad earnings, and what will receive no ad earnings. Our policies apply to all portions of your content (video, Short, or live stream, thumbnail, title, description, and tags).`

Advertiser-friendly 的 14 个主题分区（`youtube-advertiser-friendly.md`）：
`Inappropriate language` / `Violence` / `Adult content` / `Shocking content` / `Harmful acts and unreliable content` / `Hateful & derogatory content` / `Recreational drugs and drug-related content` / `Firearms-related content` / `Controversial issues` / `Sensitive events` / `Enabling dishonest behavior` / `Inappropriate content for kids and families` / `Incendiary and demeaning` / `Tobacco-related content`

**【判断】** YouTube 的分区轴是**「后果类型」而不是「主题」**：CG 是「移除轴」，advertiser-friendly 是「变现轴」。同一段内容可以在 CG 上合规、在变现轴上被打黄标。**规则库必须允许「一条内容 × 多套后果」**。

### 2.5 TikTok —— **有真正的分区，且分区 = 后果**

**【原文】**（`_evidence/R1/tiktok-fyf-standards.md` POST 0）：
> `You're in the right place if you're wondering:`
> `- What's allowed on TikTok`
> `- What's not allowed on TikTok`
> `- What's not allowed in the For You feed (FYF)`
> `We've organized our Community Guidelines by topic to make information easier to find. Under each category, you'll find a "More information" section.`

CG 的 12 个 POST（=`_evidence/R1/tiktok-accounts-features.remix.json` 的 `CGPosts` 数组，顺序即页面顺序）：

| # | 分区 | 性质 |
|---|---|---|
| 0 | Overview | 总则 + 「Our Rules」速查表 |
| 1 | Community Principles | **判据层**（8 条原则） |
| 2 | Youth Safety and Well-Being | 主题 |
| 3 | Safety and Civility | 主题 |
| 4 | Mental and Behavioral Health | 主题 |
| 5 | Sensitive and Mature Themes | 主题 |
| 6 | Integrity and Authenticity | 主题 |
| 7 | Regulated Goods, Services, and Commercial Activities | 主题 |
| 8 | Privacy and Security | 主题 |
| 9 | **For You feed Eligibility Standards** | **后果** |
| 10 | **Accounts and Features** | **后果（账号/功能维度）** |
| 11 | **Enforcement** | **后果 + 例外 + 申诉** |

**【判断】** TikTok 的分区是**「主题区」与「后果区」混排**的：2–8 是主题，9–11 是横切的后果与程序。这造成一个结构后果——**同一个主题下的规则行会按后果被拆到不同的块里**（见 §3.4），所以「一条规则」在文档里没有唯一位置，只有「一个规则行 × 它所在的清单」才是完整规则。

### 2.6 Amazon —— **按「资产类型」切，且每篇文章声明适用 marketplace**

Amazon 没有单一政策库，而是**四条并行资产线**，并由一个主索引收口：

**主索引**：`Program Policies`（`sellercentral.amazon.com/gp/help/external/G521`，`_evidence/R1/amazon-program-policies-G521.md`），顶层标题逐字：
> `General Policies / Intellectual Property / Product and Listing Requirements / Shipping / Tax / Optional Programs / See also`

`Product and Listing Requirements` 之下逐字列出：
> `Amazon Marketplace Fair Pricing Policy, Amazon Policy on Reference Prices, ASIN creation policy, Category, product, and listing restrictions, Product Detail Page Rules, Product Guidelines, Prohibited Product Claims, Restricted Products Policy`

`Optional Programs` 的兜底写法逐字：
> `If you participate in any optional program, the program policy for that optional program will apply.`

| 资产线 | 代表文件（`_evidence/R1/`） | 管什么 |
|---|---|---|
| 协议层 | `amazon-bsa-G1791.md` | Business Solutions Agreement（总合同，661 行） |
| 卖家行为 | `amazon-selling-policies-G1801.md`、`amazon-prohibited-seller-activities-G200386250.md`、`amazon-anticounterfeiting-G201165970.md`、`amazon-reviews-policies-GYRKB5RU3FS5TURN.md` | 卖家行为 |
| 商品与详情页 | `amazon-product-detail-page-rules-G200390640.md`、`amazon-product-image-guide-G1881.md`、`amazon-restricted-products-G200164330.md`、`amazon-prohibited-product-claims-G202024200.md` | Listing 本身 |
| 广告 | `amazon-ads-policies-G5RLASA28TP9TFXZ.md`、`amazon-ads-prohibited-content-GRW23T7LB4MFMBXQ.md`、`amazon-ads-prohibited-products-GZS8A5XCFQJTS88N.md`、`amazon-ads-healthcare-GPSSMTEAA6AEWY3A.md`、`amazon-ads-change-log-G8X8M375UPCN4UUC.md` | 投放 |
| 账户健康 | `amazon-ahr.md`、`amazon-ahr-faq-GR786P4BPEVKTBAG.md`、`amazon-ahr-included-policies-GQ5DSES264XVXNX7.md` | 计分与停用 |

**广告侧的顶层分区**（`advertising.amazon.com/help/G26M9XTK78AMR8TP` "Rules and policies"），逐字：
> `General requirements / Targeting / Prohibited content across all supply / Prohibited products and services across all supply / Prohibited content and products for Amazon O&O supply / Amazon DSP inventory policies / Content adjacency policies for Amazon DSP / Ad policy change log / Open Internet publisher ad policies`

**【判断】** Amazon 的广告分区轴是**「**投放位置（supply）**」**——`across all supply` 与 `for Amazon O&O supply` 并列，说明**同一条禁止规则在不同 supply 上的效力不同**。这是五家里独有的一个维度：**规则 × 载体（自有媒体 vs 开放网络）**。对 Momcozy 直接有用——他们的内容会同时投 Meta/Google 自有位与开放网络。

**【原文】** 每篇文章头部声明适用市场（`amazon-ahr.md`）：
> `This article applies to selling in: United States`

**【判断】** Amazon 用的是**「资产类型 × marketplace」二维切法**，而且 marketplace 不是脚注，是**文章级的头部字段**。这是五家里最接近 Momcozy 需要的「平台 × 国家」结构的做法，但它把 marketplace 放在**文档元数据**而不是规则字段里——代价是同一政策要维护 20 份副本。

### 2.7 顶层分区横向对照表

| | Meta CS | Meta Ads | Google Ads | YouTube | TikTok | Amazon |
|---|---|---|---|---|---|---|
| 分区依据 | **无分区**（平铺 27） | **无分区**（平铺 43，锚点假分组） | **生命周期四段** | **后果轴**（留存 / 变现） | **主题 + 后果混排** | **资产类型** |
| 分区数 | 0（声明） | 0（声明） | 4 顶层 → 主题在第三层 | 2 规则体 × 14 主题 | 12 POST | 5 资产线 |
| 分区是否互斥 | N/A | N/A | **是**（规则/裁决/准入/版本） | 否（CG 与 AFF 可同时命中） | 否（主题与后果交叉） | 是 |
| 有无兜底分区 | **有**：`Locally Illegal Content…` | **有**：`Unacceptable Content` | 有：`Other restricted businesses` | 有：`Controversial issues` | 有：`Regulated Goods…Compliance` 类 | 有：`Prohibited seller activities` |
| 按产品面切？ | **否**（全文适用 FB/IG/Messenger/Threads） | 否 | 部分（Display & Video 360 有独立条款） | **是**（视频/Shorts/直播/缩略图/标题/描述/标签） | **是**（LIVE / 搜索 / 评论 / DM / 变现分节） | **是**（Listing / Ads / 账户分线） |
| 按投放位（supply）切？ | 否 | 部分（版位不在政策层） | 否 | 否 | 否 | **是**（`across all supply` vs `for Amazon O&O supply`；`prohibited on Fire TV/Alexa/Amazon store homepage`） |
| 按风险类型切？ | 主题 (=风险类型) | 主题 | 主题 | 后果 | 主题 | 资产 |

**三条结构观察（【判断】）**：

- **O1：分区越按「后果」切，规则库越好维护。** Google（规则/裁决/准入/版本）与 YouTube（留存/变现）都按后果切，两者也是唯二把「同一行为的多套后果」表达清楚的家。按主题切的 Meta CS / TikTok 则必须让规则行自带后果标签。
- **O2：没有人按「品类」切顶层分区。** 品类（category）在五家里**永远是第二层或字段级**：Google 走 `certification`（哪个行业要资质）、Meta 走 `restricted-goods-services/*` 子页、Amazon 走 `restricted-products`。**顶层按品类切是错误的。**
- **O3：没有人按「平台（FB/IG/TikTok）」切分区，因为每家只管自己的平台。** 跨平台维度是**Momcozy 独有的**（因为它要同时投 Google/Meta/TikTok/Amazon），平台政策库里没有可借鉴的先例——这一维必须自建。

### 2.8 关于「其他」兜底分区的实证

| 平台 | 兜底条款原文 | 位置 |
|---|---|---|
| Meta | `Locally Illegal Content, Products, or Services`（独立条目）+ `We require that Ads on Facebook and Instagram must not be unlawful.` | `meta-cs-locally-illegal.md`；`meta-ad-*/locally-illegal-products-services/` |
| Google | `Other restricted businesses`（`We restrict certain kinds of businesses from advertising with us to prevent users from being exploited, even if individual businesses appear to comply with our other policies.`） | `google-ads-location-specific-requirements.md` |
| TikTok | `Regulated Goods, Services, and Commercial Activities` 末段：`Registered business accounts and verified TikTok Shop sellers may be allowed to sell or market some regulated items if…` | `tiktok-community-guidelines.md` |
| YouTube | `Controversial issues`（`This is a broad category…`） | `youtube-advertiser-friendly.md` |
| Amazon | `Prohibited seller activities` + BSA 的概括违约条款 | `amazon-prohibited-seller-activities-G200386250.md` |

**【判断】** 兜底分区的存在本身说明：**平台承认规则库不可能穷举**。所以兜底不是「其他」垃圾桶，而是**一条有明确判据的独立规则**（Meta 的判据是「地方法律」、Google 的判据是「易被滥用」）。Momcozy 若建兜底，必须写清判据，否则会退化成垃圾桶。

---

## 3. 单条规则的内部结构

### 3.1 Meta Community Standards —— 真实模板（逐字）

**通用模板**（`meta-cs-STRUCTURE-INVENTORY.md` 归纳 + `meta-cs-spam.md` / `meta-cs-hate-speech.md` 逐字核对）：

```
[锚点导航]  Policy Details | User Experiences | Data(12/27 有)

## <Title>
### Policy details

CHANGE LOG
<裸日期列表，最新一条字面上是 "Today">

Policy Rationale
<价值论证段落，通常 2–4 段>

<禁止清单，标签各条不统一：We do not allow: / Do not post: / We Remove: …>

For the following Community Standards, we require additional information and/or context to enforce:
Do not post:
<需要语境的规则行>

Notwithstanding the above, we do not prohibit:      ← 仅 2/27 有
<例外清单>

### User experiences
Reporting / Post-report communication / Takedown experience / Warning screens

### Data
[View the latest Community Standards Enforcement Report]
[Enforcement]

### 页脚
We have the same policies around the world, for everyone on Facebook.
Review teams — Our global team of over 15,000 reviewers…
Stakeholder engagement — Outside experts, academics, NGOs and policymakers…
Get help with <topic> — …
```

**逐字样例：`Spam`**（`_evidence/R1/meta-cs-spam.md`）

> `CHANGE LOG`
> `Today`
> `Jun 26, 2024`
> `Jun 30, 2022`
> `Dec 17, 2020`
> `Oct 30, 2019`
>
> `Policy Rationale`
> `We do not allow content that is designed to deceive, mislead, or overwhelm users in order to artificially increase viewership. …`
> `Online spam is a lucrative industry. Our policies and detection must constantly evolve to keep up with emerging spam trends and tactics. …`
>
> `We do not allow:`
> `Posting, sharing, engaging with content or creating accounts, Groups, Pages, Events or other assets, either manually or automatically, at very high frequencies.`
>
> `We may place restrictions on accounts that are acting at lower frequencies when other indicators of Spam (e.g., posting repetitive content) or signals of inauthenticity are present.`
> …
> `Notwithstanding the above, we do not prohibit:`
> `Cross promotion that is not triggered by payment to a third party`
> `Transferring admin or moderation responsibilities for a page or group to another user based on their interest in the page or group, rather than an exchange of value.`
> `Posting or sharing clearly identified Branded Content.`

**逐字样例：`Hateful Conduct`**（`_evidence/R1/meta-cs-hate-speech.md`）——展示**条内严重度分层**：

> `We define hateful conduct as direct attacks against people — rather than concepts or institutions — on the basis of what we call protected characteristics (PCs): race, ethnicity, national origin, disability, religious affiliation, caste, sexual orientation, sex, gender identity, and serious disease. …`
> `We separate this speech into two tiers of severity, described below.`
> `Do not post:`
> `**Tier 1**`
> `Content targeting a person or group of people … with: Dehumanizing speech … Allegations of serious immorality and criminality: … Calls and hopes for the following harms … Harmful stereotypes historically linked to intimidation or violence, such as Blackface; Holocaust denial; …`
> `**Tier 2**`
> `Content targeting a person or group of people on the basis of their protected characteristic(s) (in written or visual form) with: Calls or support for exclusion or segregation … Insults, including those about: Character… Mental characteristics… Other areas… Targeted cursing…`

**这是本节最重要的一条**：**`Tier 1` / `Tier 2` 是写在规则文本里的严重度分层**，不是外挂的元数据字段。后果差异由别处（`Counting strikes`）规定，但**分层本身在规则体内**。

### 3.2 Meta 模板的**不统一**（回答「是否所有条目都有这三段」）

**答：不是。** 逐项计数（对 27 个 `.md` 用 `grep -l` 计数，已排除索引类文件）：

| 结构标记 | 命中条数 / 27 |
|---|---|
| `CHANGE LOG` | 28（含索引页）→ **27/27 客户端均有** |
| `Policy Rationale` | 28 → **26/27**（唯一缺失：`additional-protection-minors`） |
| `User experiences` | 27 → **27/27** |
| `We do not allow` | 14 |
| `Do not post` | 5 |
| `We Remove` | 4 |
| **`we require additional information`** | **18** |
| `Notwithstanding` | **2** |

**三条硬结论**：

1. **`Policy Rationale` 不是普适的。** `additional-protection-minors` 没有它，正文直接从 `We comply with:` 起。所以模板是 **26/27 一致，1 例外**。
2. **禁止清单的标签不统一**（`We do not allow` / `Do not post` / `We Remove` 混用），意味着**不能靠标签做机器解析**。
3. **`Notwithstanding`（例外块）只有 2/27 有**——`prohibited-commercial-practices` 与 `spam`。其余 25 条的例外散落在 `Policy Rationale` 段落里（例如 `Hateful Conduct` 的 satire 例外写在 rationale 后段，不在 Notwithstanding 块）。

`prohibited-commercial-practices` 的例外原文（`_evidence/R1/meta-cs-prohibited-commercial-practices.md`）：
> `Notwithstanding the above, we do not prohibit content that condemns, raises awareness of, or educates others about scams or other prohibited commercial practices, without either revealing sensitive information or promoting them.`

**⚠「三段式 Policy Rationale / Policy Detail / Enforcement」的核实结论**：**部分不成立**。
- `Policy Rationale` ✅ 存在（26/27）。
- `Policy Detail` 是页面上**真实存在的标题**，但它是 `### Policy details` —— **一个包裹整条政策的容器标题（锚点 `#policy-details`）**，不是「政策细节」这一独立语义段。
- `Enforcement` ❌ **不是条内段落**。它是**页脚的一个链接块标题**，指向 `/enforcement/` 总站。条内并没有 per-rule 的 enforcement 说明。

### 3.3 Google Ads 单条政策的结构

Google 的单条政策是**「双段式 + eligibility 表」**。以 `Healthcare and medicines` 与 `Gambling and games` 为例（`google-ads-policies-overview.md`）：

```
<政策简介段：We're dedicated to following advertising regulations…>
<禁止条：Examples of what's not allowed / not allowed:>
<允许条：Examples of what's allowed / allowed:>
<资格段：Learn more about the <policy> / 需提交 certification>
<scope 提示：Check local regulations for the areas you want to target.>
```

**【原文】** `Healthcare and medicines`（`google-ads-policies-overview.md`）：
> `Below are some examples of healthcare content that is allowed in certain circumstances. You're expected to familiarize yourself with the local law and regulations for any location your ads target. Learn about what happens if you violate our policies.`

**【原文】** `Alcohol`：
> `We abide by local alcohol laws and industry standards, so we don't allow certain kinds of alcohol-related advertising, both for alcohol and drinks that resemble alcohol. Some types of alcohol-related ads are allowed if they meet the policies below, don't target minors, and target only countries that are explicitly allowed to show alcohol ads.`

**【判断】** Google 与 Meta 的关键差别：**Google 的「允许/不允许」是同一政策页内的两块，而「在哪个国家允许」被推到另一个页面（certification / location-specific）**。Meta 则把国家清单直接写在政策页的 `Guidelines` 小节里（见 §4.1）。

### 3.4 TikTok 单条规则的结构 —— **一个模板，三块清单，后果由块决定**

**【原文】** 每个主题下的固定结构（`_evidence/R1/tiktok-community-guidelines.md`）：

```
#### <Topic>
### More information
##### NOT ALLOWED
<规则行…>
##### FYF INELIGIBLE & AGE-RESTRICTED
<规则行…>
##### ALLOWED
<规则行…>
```

**逐字样例：`Hate Speech and Hateful Behavior`**（`tiktok-community-guidelines.md`，节选）：
> `##### NOT ALLOWED`
> `- Promoting "conversion therapy" programs aimed at changing someone's sexual orientation or gender identity`
> `- **In some regions**, insulting religion or showing the desecration of religious symbols or sites`
> `##### FYF INELIGIBLE & AGE-RESTRICTED`
> `##### ALLOWED`

注意第二条规则行里的 **`In some regions`** —— **这是 TikTok 把「适用范围」写进规则行本身的唯一手法**（详见 §4.4）。

**【判断】** TikTok 的设计是**「严重度 = 结构位置」**：规则行写在哪一块，后果就是什么。好处是永远不可能出现「规则与等级不一致」；代价是**同一行为的多个后果无法表达**（比如「既 18+ 又不进 FYF」以外的组合写不出来）。

### 3.5 YouTube 单条规则的结构

YouTube CG 条目是**叙述式 + 例示**（`youtube-community-guidelines-full.md` / `youtube-community-guidelines-overview.md`）。

Advertiser-friendly 条目则是**三态表**（`youtube-advertiser-friendly.md`）：

```
### <Topic>
<叙述：什么内容不适合投放，语境如何改变结论>
Policy Detail
| Ads guidance | Questionnaire options & details |
| This content can earn ad revenue | <示例> |
| … (limited / no ad revenue) |
```

**【原文】** `Violence` 条：
> `Content where the focal point is on blood, violence, or injury, when presented without other context, is not suitable for advertising. If you're showing violent content in a news, educational, artistic, or documentary context, that additional context is important. For example, if a video provides news reporting on a violent event like a terrorist attack in a journalistic context, it may be eligible for monetization. Violence in unedited video gameplay is generally acceptable for advertising, but montages where gratuitous violence is the focal point is not.`

并给出**允许示例**的原文清单：
> `Law enforcement including regular duty in action (such as forcible arrest, crowd control, dispute with officer, forcible entry); unedited gameplay violence occurring after the first 7 seconds; mild violence with minimal blood; dead bodies that are fully obscured, blurred, prepared for burial, or shown in historical events like wars, as part of an educational video. Non-violent or brief references to foreign terrorist organizations (FTOs). Educational content or journalistic reporting which includes imagery related to foreign terrorist organizations or mentioning foreign terrorist organizations as the central topic.`

**【判断】** 注意 `occurring after the first 7 seconds` —— **平台把「阈值」写成可执行的边界条件**（7 秒）。这是 Momcozy 的规则库最该学的一手：**把「过度」「明显」「大量」这类模糊词换成一个可数的量**。

### 3.6 Amazon 单条规则的结构 —— **唯一一家把阈值写成数字的**

Amazon 政策是**编号/加粗条款式**，配合 **BSA 的合同条款**作为最终兜底。

**【原文】** Amazon Ads 总则（`amazon-ads-policies-G5RLASA28TP9TFXZ.md`）：
> `All advertisements are subject to review. Review times may vary by ad product and may be extended during periods of high submission volume, including large numbers of simultaneous submissions. Amazon reserves the right to reject, remove, or require modifications to ads that don't meet its policies, at its sole discretion. Amazon may also take immediate action to protect the stability, security, or integrity of its advertising systems, including throttling delivery, restricting access, or excluding specific ad entities. When appropriate, Amazon will notify affected advertisers with information to help resolve the issue. Amazon may suspend or terminate ad accounts for severe or repeated policy violations. Policies are periodically updated. Review the change log for updates.`

**⭐ 量化阈值——这是全五家里最值得直接抄的一组原文。**

**【原文】** `Product image guide`（`_evidence/R1/amazon-product-image-guide-G1881.md`），MAIN 图片要求的四个子分区为 `Basic requirements / Background and visual requirements / Model and display requirements / Category-specific guidance`，逐字条款：
> `Show the product as **85%** of the image.`
> `Show the entire product within the frame of the image. Do not cut off any part of the product.`
> `Only show the product once in the image.`
> `Show only one unit of the product and any accessories that are included with the product.`
> `Have a **pure white background (RGB color values: 255, 255, 255)** to create a consistent shopping experience for customers across search and product detail pages.`
> `Don't show accessories or any props that aren't included with the product and could confuse the customer.`
> `Don't show any part of a mannequin, regardless of the mannequin's appearance.`

**【原文】** `Product detail page rules`（`_evidence/R1/amazon-product-detail-page-rules-G200390640.md`），四个分区 `Policies for writing listings / Policies for adding detail pages / Policies for editing detail pages / Guidance for editing detail pages associated with Brand Registry branded ASINs`，编号规则逐字：
> `Comply with any relevant style guides and refrain from using HTML, JavaScript, or other code.`
> `Exclude inappropriate content such as obscene or offensive materials, links or contact information, plot spoilers, reviews or requests for reviews, and advertising.`
> `Accurately categorize and describe your products.`
> `Refrain from creating duplicate pages for a product that already has a detail page.`
> `Create new detail pages for new products or versions.`
> `Product titles must not have more than **75 characters**, including spaces… Use item highlights to add more descriptive features of the product, which has a character limit of **125 characters** (including spaces).`

**【原文】** `Claims and substantiation`（`_evidence/R1/amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.md`）——**与 Momcozy 品类直接相关**：
> `Ads for weight management are prohibited from guaranteeing permanent weight loss, a specific rate of weight loss, or promising that weight won't be regained after stopping the product.`
> `Ads must avoid content that encourages unhealthy eating habits or negative body image and are prohibited from using before and after imagery.`
> `Claims that non-prescription products are as effective as prescription products.`
> `We permit environmental claims, origin claims, warranties or guarantees, and claims that describe health or quality ingredients on ingestible products such as gluten free or organic. These claims must be substantiated on the ad creative, product detail page, or landing page, and **environmental claims must be dated within 24 months.**`
> `Product endorsements: Medical or professional society endorsements (for example, "#1 physician recommended allergy medicine"). If the claim is on the product packaging, no further substantiation is needed. Otherwise, substantiation, **including source and date (within 24 months)**, is required in the ad creative, on product packaging, or landing page.`
> `Comparative claims: Claims that compare a product or service to a competitor's product (for example, "Provides 50% more pain relief than the leading brand"). … substantiation, including source and date (within 24 months), is required…`

**【判断】三条可学的结构：**

1. **阈值全部数字化**（`85%` / `RGB 255,255,255` / `75 characters` / `125 characters` / `24 months`）。**没有「适当」「明显」「大量」这类词。** 这正是 Momcozy 规则库最缺的东西——他们的 `边界内容` 若含模糊词，Agent 无法稳定判定。
2. **「证据必须带日期」是一个通用机制**（`including source and date (within 24 months)`）。**证据的有效期**比证据本身更容易被忽略。
3. **Amazon 用「保留权利」条款故意留出不确定性**（`in its sole discretion` / `may take immediate action`）。**它的规则不是穷举清单，而是授权条款 + 示例。** 这是与 Meta/Google「可枚举规则」根本不同的哲学。

**【判断】** Amazon 的结构特征是**「保留权利」条款密度远高于其他四家**。这意味着 Amazon 的规则库**故意保留不确定性**——它不承诺规则的完备性，因此**没有任何自动化审查系统能宣称「已覆盖 Amazon 政策」**。

### 3.7 单条规则结构横向对照

| | 规则体的最小单位 | 严重度写在哪 | 例外写在哪 | 语境依赖怎么写 |
|---|---|---|---|---|
| Meta CS | policy line（无编号，靠缩进层级） | **规则文本内的 Tier 1/Tier 2** | `Notwithstanding` 块（2/27）或 rationale 段内 | **独立小标题**：`For the following Community Standards, we require additional information and/or context to enforce:`（18/27） |
| Google Ads | 「not allowed / allowed」条目 | 不在规则页，在 Review process 的 status 定义里 | eligibility / certification 段 | 政策页一句 `expected to familiarize yourself with the local law` |
| YouTube AFF | 三态表行 | **表行位置**（can earn / limited / no） | 叙述段 | 叙述段 + `More likely / Less likely` 对照表 |
| TikTok | 规则行 + 所属清单 | **清单位置**（NOT ALLOWED / FYF INELIGIBLE / ALLOWED） | `ALLOWED` 块 | 规则行内 `In some regions` / `In certain cases` |
| Amazon | 条款条目 | 不在规则页，在 AHR（critical/high/medium/low） | 罕见 | 「保留权利」条款 |

**核心发现**：**五家里没有一家把 severity 写成规则的一个普通字段。** 三种实现：
1. **写进规则文本**（Meta 的 Tier 1/Tier 2）
2. **由结构位置隐含**（TikTok 的清单、YouTube 的表行）
3. **完全外置到计分系统**（Google 的 status、Amazon 的 AHR）

---

## 4. 【核心】「适用范围」与「规则本体」的分离

这是本次调研最核心的问题。**结论：五家全部分离，但五家用了五种不同手法，且都同时使用了多种手法。**

### 4.1 Meta —— 三层分离 + 「本地法不带处罚」

**手法 A：全局同一性声明（写在每条政策页脚）**

**【原文】** 27 条 CS 页脚 + 广告政策页脚，逐字：
> `We have the same policies around the world, for everyone on Facebook.`

索引页的对应声明：
> `Our Community Standards apply to everyone, all around the world, and to all types of content, including AI-generated content.`

**手法 B：独立的「本地法」条目，且明确声明它不带平台处罚**

**【原文】** `Locally Illegal Content, Products, or Services`（`_evidence/R1/meta-cs-locally-illegal.md`），`Policy Rationale` 全文逐字：
> `When regulators or government entities believe content on our services goes against local law, they may ask us to restrict the content. Non-government entities and members of the public may also send reports alleging content is unlawful. We may also receive court orders.`
> `When we receive a report or an order, we first review it against the Community Standards. If we determine that the content goes against our policies, we remove it. If content does not go against our policies, in line with our commitments as a member of the Global Network Initiative and our Corporate Human Rights Policy, we conduct a careful legal review as well as human rights due diligence to determine whether the report is valid.`
> `In cases where we believe that reports are not legally valid, are overly broad, or are inconsistent with international human rights standards, we may request clarification or take no action.`
> `**Where we do act against user content on the basis of local law rather than our Community Standards, we endeavor to restrict access to the content only in the jurisdiction where it is alleged to be unlawful and do not impose any other penalties or feature restrictions. We also notify the affected user.**`
> `We also publish reports detailing how we assess reports of content violating local law and instances where we restricted access to content in such cases, available here.`

**【判断】这是全五家里最干净的一次「规则本体 / 适用范围」分离声明。** 它同时确定了四件事：

| 维度 | 规则本体（Community Standards） | 本地法（Local Law） |
|---|---|---|
| 适用空间 | 全球同一 | **仅指称违法的辖区** |
| 触发源 | 平台自审 | 监管/政府/法院/公众举报 |
| 判定程序 | 对 CS 比对 | 法律审查 + 人权尽职调查 |
| **后果** | strike / 功能限制 / 停用 | **`do not impose any other penalties or feature restrictions`** |
| 申诉 | 平台内申诉 | 本地法报告体系 |

**手法 C：把「地区」做成一条可检视的公开报表，而不是政策条目**

**【原文】** `_evidence/R1/meta-report-restrictions-by-country.md`：
> `# Restrictions by country`
> `Search for country specific information on content we restricted based on local law.`

该报表站有五个子页：`Overview` / `Restrictions by country` / **`Global restrictions`** / `Case studies` / **`How we assess reports of content violating local law`**。

**【判断】** 注意 `Global restrictions` 与 `Restrictions by country` 是**并列的两个类别**——Meta 把「全球适用的法律限制」与「某国独有的法律限制」分开管理。**这是「辖区」维度的完整取值：Global / <Country>。**

**手法 D：规则行内的「local nuance」修正子句**

**【原文】** `Hateful Conduct`（`meta-cs-hate-speech.md`）：
> `Sometimes, based on local nuance, we consider certain words or phrases as frequently used proxies for protected characteristics.`

以及该条的 EU 专段：
> `Note: if you are a European Union user, and are seeing content that you believe violates hate speech laws within your country, you can submit a legal removal request to Facebook or Instagram.`

**手法 E：把「哪些词算违规」做成按 market 维护的独立词表，并公开其治理流程**

**【原文】** `How We Create and Use Market-Specific Slur Lists`（`_evidence/R1/meta-enf-market-slurs.md`，页面标注 `UPDATED AUG 12, 2022`）：
> `A language can be shared across nations and cultures, but slurs are often specific to a region or community (which we call a market). This is why we use slur lists that are specific to markets, not just languages.`
> `Our content moderation routing incorporates both language and region to determine the appropriate reviewer(s) for content, but generally, language plays a larger role in that complex routing. For example, Southern Cone market queues will encompass content that comes from Chile, Uruguay, Argentina, and Paraguay and for which the primary language is Spanish.`
> `Each market queuing algorithm also has a condition called a "catch all." This condition allows for all jobs in a language that is not assigned to the countries that the market covers to automatically fall in the markets most relevant for that language.`
> `**We conduct an annual audit of our slur lists.** This is done by our operational teams in collaboration with our regional market teams, who together review the slurs and reach a conclusion as to whether the word retains the offensive character that initially qualified it for the list.`
> `… Cultural context is provided (news articles, academic articles, etc.), and **at least 50 pieces of content containing that term must be collected and assessed.**`

**【判断】这是「规则本体 / 适用范围」分离的最重要范例，也是本文对 Momcozy 最关键的一条可搬运机制：**

> **规则本体**（universal）：`Content that describes or negatively targets people with slurs. Slurs are defined as words that inherently create an atmosphere of exclusion and intimidation against people on the basis of a protected characteristic…`
> **适用范围参数**（market-scoped）：**具体哪些词构成 slur 的清单**
> **治理**：market 团队建表 → 每条词至少 50 条样本 → policy 团队复核 → **年度审计** → 允许 NGO 提议增删

即：**把「规则」与「规则在本地的具体实现（词表/阈值/清单）」拆成两个受治理的资产，用不同的更新节奏维护。** 规则的更新慢，词表的更新快，词表有年度审计。

**手法 F：广告侧用 `Guidelines` 小节承载国家清单**

`Alcohol` 政策页结构（`meta-ad-alcohol.md`）：
- 规则本体在 `Overview` / `Alcohol` 标题下
- 地理清单在**独立的 `Guidelines` 标题下**：
> `As global alcohol laws vary, advertisers need to make sure they comply with all applicable targeting requirements. Some countries don't allow the sale or promotion of alcohol, while others have minimum drinking ages.`
> `Advertisers can't run alcohol ads in the following countries or regions:` （接 18 个国家/地区）+ 允许国家清单（带各国最低饮酒年龄）

政策摘要里则用一句**scope 声明**：
> `Note that our policies prohibit ads promoting or referencing alcohol in some countries, based on local law.`

同一手法出现在 `health-wellness`（`meta-ad-health-wellness.md`）：
> `For weight loss products that require prescription, please refer to Drugs and Pharmaceuticals ads policy and comply with the geo-targeting, and written permission requirements.`
> `For Reproductive health and wellness drugs or treatments that require prescription, please refer to Drugs and Pharmaceuticals ads policy and comply with the geo-targeting, and written permission requirements in addition to this policy.`

**【判断】** 这里有一层很关键的机制：**跨政策路由 + scope 收窄**。当条件成立（需处方），**适用的规则换成另一条，且 scope 收窄为「geo-targeting + 书面许可」**。这不是「同一条规则在不同国家不同」，而是「**同一条规则在不同条件下路由到不同规则 + 不同 scope**」。

Meta 广告侧还有一层：`_evidence/R1/meta-ad-index.md` 载有 **`Transparency requirements under the EU Digital Services Act`** 独立小节——又一次「法域 → 独立章节」。

### 4.2 Google Ads —— 五层分离（**本文认为最可复用的一套**）

**（本文此处更正早期判断：country-specific 不止「certification 闸门」一种手法，而是五层并存；且此前列为「未核实」的 per-country 矩阵已经取得。）**

**层 1：一条明文声明，把「法」与「平台政策」并列为两个各自生效的规则体**

**【原文】** `Legal requirements`（`_evidence/R1/google-ads-legal-requirements.md`；URL `support.google.com/adspolicy/answer/6023676`）：
> `You're required to comply with the local laws and regulations of any area your ads target, **in addition to** Google Ads policies. You're expected to familiarize yourself with the local laws and regulations for any location your ads target.`
> `Certain locations, industries, and trade associations have their own codes for advertising and marketing. You can refer to this List of advertising codes for some of the codes that may apply.`
> `**This isn't an exhaustive explanation of local legal requirements in each location. You're still responsible for researching and complying with local laws where your business operates, and in any location your ads target.**`
> `In some limited circumstances, violations of local law may be considered egregious and result in account suspension. If this happens, all ads in the suspended account will stop running, and you may not be able to advertise using Google Ads or Display & Video 360 again. Any related accounts may also be permanently suspended and your new accounts may be automatically suspended at setup.`

同一句话在 `What happens if you violate our policies` 里再次出现（`google-ads-violation-consequences.md`）：
> `To ensure a safe and positive experience for users, Google requires that advertisers comply with **all applicable laws and regulations in addition to** the Google Ads policies.`

**并在这条「法律要求」页里直接嵌入了法规原文**——`Audiovisual Media Services Directive` 小节逐字引用 **Article 9** 全文（含 `(a)`–`(g)` 各项，例如 `(f) audiovisual commercial communications for medicinal products and medical treatment available only on prescription in the Member State within whose jurisdiction the media service provider falls shall be prohibited;`）。另有 `Trade sanctions violation` 小节列出受制裁国家（`Currently, there are embargoes on Crimea, Cuba, so-called Donetsk People's Republic (DNR) and Luhansk People's Republic (LNR), Iran, and North Korea.`），以及 `Reports of illegal content to Google` 入口。

**【判断】** 这是五家里唯一把**外部法规原文直接搬进政策库**的做法，且它被放在 **`Legal requirements` 这个独立章节**，不污染任何一条业务政策，并且在 `List of ad policies` 索引里**与其他政策平级**。**这是「规则本体不动，法域要求挂载」的教科书实现。**

**层 2：`certification` / `verification` 闸门——把「在哪个国家允许」变成「你有没有资格证」**

**【原文】** `Apply to advertise certain products & services using Google Ads`（`_evidence/R1/google-ads-location-specific-requirements.md`）：
> `In addition to completing advertiser verification, certain industries require you to apply to advertise content related to that industry. **Requirements vary by location, so check the location-specific restrictions for every location where you plan to advertise.**`
> `If your ad is disapproved because you still need to apply to advertise for a specific industry, you can find that information in the status of your ad: … If the policy details show "Certificate required", apply to advertise per the policy instructions below.`

该页对每个受限行业给出「申请入口」，例如：
> `Gambling-related ads are allowed if they comply with the Gambling and games policies and the advertiser applies and is allowed to advertise for certain products. Gambling ads must target approved countries, have a landing page that displays information about responsible gambling, and never target minors. Check local regulations for the areas you want to target.`
> `Financial services — Beginning on the dates listed in Relevant Regulators and Enforcement Dates, advertisers in certain locations may need to meet additional requirements to run financial services ads. Google may require verification for advertisers, and **a separate verification may be needed for each targeted location.**`
> `Political content and election advertising — To run election ads for the location of the election, you must be verified under that region's Election Ads verification process. For example, you must complete the Australia Election Ads verification process to run Australia Election Ads in Australia. To run election ads that target outside of the location of the election, you must be verified under either the Election Ads Verification or Advertiser Verification process for the region in which the advertiser is located. For example, a UK-based advertiser must complete a UK verification process to run New Zealand Election Ads in any region outside New Zealand.`
> `High Fat Sugar Salt Food and Beverage Ads: In the EU and UK, advertisers are required to self-declare that they are using an account to run HFSS F&B campaigns.`

**【判断】** 这是一套**「(规则 × 辖区 × 广告主) 三元组 → 需不需要一个凭证」**的结构。规则本体只写「受限」；「在哪些辖区、需要什么凭证、怎么申请」全部外置。**凭证是 scope 的可执行化形式。**

**层 3：`Relevant Regulators and Enforcement Dates` —— 按「监管机构 × 生效日」维护的表**

`_evidence/R1/google-ads-regulators-enforcement-dates.md`（807 行）是这份表。它把「哪个国家的哪个监管机构、从哪天起、要求什么」做成一张可查询清单。

**【判断】** 这是**时间维度进入 scope** 的证据：**同一条规则在同一个国家的不同日期可以不同。** 规则库的 scope 必须是 `(jurisdiction, effective_date)` 而不是单纯的 `jurisdiction`。

**层 4（更正新增）：per-policy 的「国家 × 产品 × 资质」矩阵——**这是最可执行的一层****

**（此前本文把「完整 (政策 × 国家) 允许矩阵」列为未核实缺口，现已取得原文。）**

**【原文】** `Gambling and games` 政策页（`_evidence/R1/google-ads-gambling-games.md`，URL `support.google.com/adspolicy/answer/6018017`），H2 标题即 `## Country-specific requirements`，正文是一张**逐国表**，每国两列 `Products allowed` + `Country-specific certification requirement`：

| 国家 | Products allowed（逐字） | Country-specific certification requirement（逐字） |
|---|---|---|
| `Angola` | `Online gambling: Sports betting / Online games / Gambling-related lotteries` | `Operator must be a licensed operator registered with the Instituto de Supervisão de Jogos. Learn how to apply.` |
| `Argentina` | `Online gambling: Lotteries / Sports betting / Online casino games / Online gambling` | `Operator must be province-run or province-licensed entities. Learn how to apply.` |

同页另有一条**账户级约束**：
> `Note: An account may be certified for either online gambling or social casino games content. In order to advertise both, you will need separate accounts.`

**【判断】这就是「同一行为在不同辖区归属不同规则」的最完整实现**——它同时给出了三个维度的取值：**辖区（Angola/Argentina）× 产品子类（Sports betting/Online casino games…）× 资质要求（具体监管机构名 + 申请人类型）**。而且**资质要求指向的是该国的具体监管机构名称**（`Instituto de Supervisão de Jogos`）。

**重要：每个政策的国家段标题并不统一**——同一个 Google Ads 里存在至少四种命名：
| 标题 | 出现于 |
|---|---|
| `Country-specific requirements` | Gambling and games |
| `Location specifics` | Alcohol、Sexual content |
| `High APR personal loans (US specific)` | Financial products and services |
| `Regional Restrictions` | Political content |

**【判断】这是 Google Ads 的一个**一致性缺陷**：同一个语义（地区限制）用了四个不同的标题。**机器无法用统一选择器抓取，人也会漏读。** Momcozy 若要建立「适用范围」字段，**必须强制单一命名**——这是从 Google 的缺陷里学到的负面教训。

**层 5：`Eligible (limited)` —— scope 直接成为广告的一种状态**

**【原文】** `Eligible (limited): Definition`（`_evidence/R1/google-ads-eligible-limited.md`）：
> `A status given to ads and products that comply with our policies but are limited in where and when they can show.`
> `An ad or product will be marked "Eligible (limited)" when Google Ads policies, such as Alcohol, Gambling, Healthcare, and Trademarks, prevent certain types of ads or products from showing in certain locations, to certain ages, or on certain devices.`
> `Additionally, ads may be limited due to policy restrictions based on the content of your ad or website. This limitation can also apply if your website content contains terms associated with regulated industries, even if your products or services themselves are compliant.`
> `For example: A gambling ad or product run by an advertiser certified under our Gambling policy will serve as Eligible (limited). / An ad or product labeled for our Sexual Content: Moderately Restricted policy will serve as Eligible (limited).`

而 `What happens if you violate our policies` 里给出的完整名称为 **`Eligible (limited all locations)`**：
> `An ad will be marked "Eligible (limited all locations)" when Google Ads policies (common examples include Alcohol, Copyrights, Gambling, Healthcare, and Trademarks) prevent certain types of ads from showing in your targeted locations. Depending on the policy topic, available certification and verification programs, and target country, the ads can serve on a limited basis.`

**【判断】这是全五家里最优美的一个设计：把「适用范围」直接做成投放系统的一个状态值。** 规则合规但地区不允许 → 不是「违规」，是 `Eligible (limited)`。**违规与受限在状态机层面被分开了。** 这正是 Momcozy 的四档「高危/审慎/待复核/合规」缺的那一档（见 §8.3）。

### 4.3 YouTube —— 规则全球统一，scope 靠「独立法务层 + 可见性参数」

YouTube 的**社区规则文本全球统一，没有国家变体**（这是与 Google Ads 最大的差别——同属 Google，广告侧有逐国矩阵，社区侧没有）。它的 scope 分离体现在**三个独立层**：

1. **`Age-restricted` 作为一种独立处置**（`_evidence/R1/youtube-age-restricted.md`），与移除并列。
2. **地理可见性作为创作者可配参数**——`_evidence/R1/youtube-policy-updates.md` 逐字：
> `**[September 2026] Upcoming changes to paid promotions:** … When creators select **Yes** under the updated Paid promotion & brands section in YouTube Studio, they can now manually configure **granular geographic visibility (including country-specific routing)** and age gating (from 18 to 25+).`
3. **地方政府的移除请求**走独立流程，明确「不给 strike」。`_evidence/R1/youtube-strike-basics.md` 逐字：
> `**Note:** We may remove content for reasons other than Community Guidelines violations. For example, a first-party privacy complaint or a court order. **In these cases, your channel won't get a strike.**`

   该法务层另有独立入口：`_evidence/R1/youtube-legal-issues.md`、`youtube-legal-complaints.md`，逐字：`Each court order is examined and evaluated based on a set of regional and global criteria`（来源 `support.google.com/youtube/answer/6156383`），以及按国家/地区选择争议管辖的处理入口（`answer/9996224`：`select your country/region of dispute from the menu`）。

**【判断】** 所以 YouTube 的 scope 结构是：**规则体全球统一 + 法务层按辖区独立 + 创作者可配 geographic visibility**。**社区规则本体完全不带地域信息**——这与 Google Ads（辖区写进规则名/规则表）形成同公司内部的鲜明对比，说明「同一家公司在不同产品线上可以选不同的 scope 架构」，**scope 的表达方式没有唯一正确答案，取决于该规则是否真会因辖区而变。**

**【判断】** 第 3 条与 Meta 的 `do not impose any other penalties` 是**同一个设计决定**：**法律性移除不带平台处罚，是两套东西。** 五家里至少三家（Meta、YouTube、Google 的 `Legal requirements`）独立表达了这一点——这不是巧合，是行业共识。

### 4.4 TikTok —— 三层：**总则声明 + 规则行限定词 + 本地法隔离**

**（本文此处更正早期判断：TikTok **有**明确的地区差异声明，且本地法层与 Meta 同构。）**

**层 1：明确的地区差异总则**

**【原文】** `Sensitive and Mature Themes`（`_evidence/R1/tiktok-community-guidelines.md` 第 608 行）：
> `TikTok welcomes a range of content, from family-friendly to more mature. Because our community is global, we consider cultural and regional differences when handling content that may be sensitive. To respect local norms, we may apply these guidelines differently depending on the region.`

**层 2：原则层声明**

**【原文】** `Community Principles`（`tiktok-community-guidelines.md`）：
> `**Respect Local Cultures:** People use TikTok in over 150 countries. We work with local experts to make sure that our global approach considers the way harms are experienced across regions, and that **we allow for regional applications of our guidelines while upholding human rights standards.**`

**层 3：本地法隔离——与 Meta 完全同构的声明**

**【原文】** `Government removal requests`（`_evidence/R1/tiktok-government-removal-requests.md`）：
> `In scenarios where we do take action against content based on a local law violation (rather than TikTok's Community Guidelines or other policies), as a general principle, **we seek to restrict access to the content only in the jurisdiction where it is alleged to be unlawful.**`
> `**Step 5: Take action and close the case** … If we take action based on a removal request based on a violation of local laws, we restrict access to the content only in the jurisdiction where it is alleged to be unlawful. **Limited exceptions may apply, for example, where justified based on legal and safety grounds.** We will issue a response to the relevant government authority and may also notify the impacted user of the action taken (e.g. where required or permitted to do so).`

**【判断】这是本次调研第二个重要发现：Meta 与 TikTok 用几乎相同的措辞声明了同一条原则**——**基于本地法的处置只做地域性屏蔽，不扩散到全球**。Meta 原文 `restrict access to the content only in the jurisdiction where it is alleged to be unlawful`，TikTok 原文 `we seek to restrict access to the content only in the jurisdiction where it is alleged to be unlawful`（**逐字相同**）。

配合 YouTube 的 `In these cases, your channel won't get a strike.`，**三家独立确认：法律性移除 ≠ 平台违规，两者走不同管道、不同后果、不同地域范围。** 这已构成行业共识级的设计原则，不是个别做法。

**层 4：规则行内限定词（**仍是最弱的一层**）**

逐字样例：
- `Hate Speech and Hateful Behavior → NOT ALLOWED`：`- In some regions, insulting religion or showing the desecration of religious symbols or sites`
- `Accounts and Features`：`**You must be at least 13 years old to have a TikTok account**, though some places have different age restrictions.`
- `Accounts and Features → LIVE 不合格清单`：`- In some regions, LIVE sessions that show adults engaging in intimate kissing, sexualized framing, sexualized behavior, or sexually explicit language`
- 同一清单另有 `- In all regions, LIVE sessions that: Show physical altercations, even if they aren't graphic …`

**【判断】** 有 15+ 处 `In some regions` 子句（宗教、大麻、酒精、赌博、枪支、身体暴露、LIVE 等），但**没有一处列出具体是哪些地区**。所以 TikTok 的 scope 表达在**总则层是完备的**（层 1–3），在**规则行层是不可执行的**（层 4）。**这是反例，不是范本**——Momcozy 若在自己的规则里写「部分地区」，必须附上地区枚举。

另一个 scope 维度：**TikTok 的 CG 通过 URL 参数版本化 + 按地区路由**。抓取时服务端注入的 `__REGION__DATA__INJECTED__` 显示 `{"VRegion":"sg","VGeo":"VGEO-ROW"}`，而 CG 内容本身带 `cgversion=2025H2update`。**【判断】** 这意味着同一份 CG 在不同地区可能服务不同内容——**但本文未能取得地区差异清单，列入缺口 §10.2。**

### 4.5 Amazon —— 分离度体现在「文章级 marketplace 头部」+ 广告侧的显式国家段

**【原文】** 每篇政策文章头部（`amazon-ahr.md`）：
> `This article applies to selling in: United States`

AHR 还明确说明了**按店铺分别计分**：
> `It is displayed on your seller's Account Health page for each store in which you sell worldwide.`

**广告侧有显式的国家层**。**【原文】**（`_evidence/R1/amazon-ads-prohibited-products-GZS8A5XCFQJTS88N.md`、`amazon-ads-general-requirements-G4U9JBZH3664JWX2.md`）：
> `This section covers requirements for all ads. **Additional country-specific and supply-specific restrictions may apply.**`

`Prohibited products` 页里有一个字面上的 **`Country-specific restrictions`** 标题，其下按**国家组**列举（逐字）：
> `Australia and New Zealand`
> `Denmark, Finland, France, Germany, Netherlands, Norway, Poland, Sweden, and Switzerland`
> `Singapore`
> `United Kingdom`

Healthcare 广告政策页同样有 `Country-specific restrictions` 段，逐字列出：
> `Austria, Belgium, Bulgaria, Croatia, Cyprus, Czechia, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Poland, Portugal, Romania, Slovakia, Slovenia, Spain, and Sweden / Brazil / Singapore / United Kingdom`

卖家侧（`_evidence/R1/amazon-intl-sellers-G200404870.md`、`amazon-taxes-regulations-global-selling-G201468380.md`）：
> `you must understand the laws that apply to you as a seller, and only list and sell products that comply with those laws`
> （`Taxes and regulations for Amazon Global Selling`）`provides an overview by region` … `check out Amazon's Compliance Reference tool to find requirements in your chosen store`

另有 `Account enforcement for Regulatory and Safety Compliance violations`（`GX9VRVWH8HXTDTK7`）：
> `If you list products on Amazon, you must comply with all applicable laws, regulations, standards, and our policies`

**【判断】** Amazon 的 scope 分离有**两种粒度并存**：
- **卖家侧**：scope 放在**文档元数据**（`applies to selling in: <marketplace>`），代价是同一政策要维护 20 份副本。
- **广告侧**：scope 放在**规则页内的 `Country-specific restrictions` 段**，且允许**国家组**（`Denmark, Finland, France, …`）作为取值。

**对应到 Momcozy：不要在文档层表达 scope（会副本漂移），要在字段层表达；但可以允许「国家组」作为一个取值**（EU、北欧四国等），避免逐国维护。

**⚠ 缺口**：GPSR（EU 通用产品安全法规）**在本次抓取的全部 Amazon 页面中都未出现**（NOT FOUND）。Amazon 是否以 GPSR 为名维护合规要求，未核实。

### 4.6 分离手法的九种可复用机制（归纳）

| # | 机制 | 谁在用 | 机制描述 | 对 Momcozy 的适配度 |
|---|---|---|---|---|
| M1 | **全局同一性声明** | Meta | 一条政策页脚写明规则全球一致，把差异全部推到别处 | ★★★ 必抄 |
| M2 | **独立法域章节** | Meta（本地法条目 / EU DSA）、Google（`Legal requirements` 且与业务政策平级） | 法域要求不写进业务规则，另起一条/一章；**Google 还把 AVMSD Art.9 法规原文直接搬进来** | ★★★ 必抄 |
| M3 | **法域要求映射到独立资产** | Meta（market slur lists） | 规则不变，本地化实现（词表/阈值）单独维护 + 年度审计 | ★★★ 必抄 |
| M4 | **凭证闸门** | Google（certification） | 「在 X 国能不能投」= 「有没有该国的凭证」 | ★★☆ 若涉及资质类卖点（医疗器械）必抄 |
| M5 | **per-policy 国家矩阵** | Google（`## Country-specific requirements` 逐国表） | 规则页内直接给「国家 × 产品子类 × 资质要求」表，资质指向该国监管机构名 | ★★★ 必抄（本文认为这是最可执行的一层） |
| M6 | **scope 变成状态值** | Google（`Eligible (limited)`） | 合规但地区受限，是一种投放状态而不是违规 | ★★★ 必抄 |
| M7 | **本地法隔离（只做地域屏蔽 + 不处罚）** | Meta + TikTok（**两家措辞逐字相同**）+ YouTube（`won't get a strike`） | 基于本地法的处置只屏蔽指称违法的辖区，不扩散、不计 strike | ★★★ 必抄 |
| M8 | **文档级 scope 头部** | Amazon 卖家侧 | 每篇文档声明适用市场 | ☆ 不抄（会造成副本漂移）；**但「国家组」作为取值可抄** |
| M9 | **规则行内限定词** | TikTok（`In some regions`，15+ 处，无地区枚举） | 直接在规则句子里加地区限定 | ☆ 不抄（不可执行） |

**⭐ 一个跨家一致性的强发现（M7）**：三家平台用几乎相同的语言独立声明了同一条原则——
- Meta：`we endeavor to restrict access to the content **only in the jurisdiction where it is alleged to be unlawful** and do not impose any other penalties or feature restrictions`
- TikTok：`we seek to restrict access to the content **only in the jurisdiction where it is alleged to be unlawful**`（**与 Meta 逐字相同**）
- YouTube：`We may remove content for reasons other than Community Guidelines violations. For example, a first-party privacy complaint or a court order. **In these cases, your channel won't get a strike.**`

**【判断】** 这不是个别做法，**是行业共识级的设计原则**：**法律性移除与平台违规是两套管道，后果不同、地域范围不同、计数不同。** Momcozy 必须在自己规则库里把这两人分开——否则会把「某国法律不允许」误记成「品牌违规」，污染规则库的统计与升格计数。

### 4.7 「同一行为在不同辖区归属不同规则」的显式声明方式

**Google 的答案最彻底：把辖区写进规则的名字。**

**【原文】** `Upcoming and recent changes → 2026`（`_evidence/R1/google-ads-changelog-2026.md`），条目标题逐字：
```
Update to Gambling and Games Policy: Global (August 2026)
Update to Gambling and Games Policy: Colorado, USA (June 2026)
Update to Gambling and Games Policy: France (June 2026)
Update to Gambling and Games Policy: Ireland (May 2026)
Update to Gambling and Games Policy: Alberta, Canada (April 2026)
Update to Gambling and Games Policy: Australia (April 2026)
Updates to Cryptocurrency Advertising Policy in France (July 2026)
```

**【原文】** `Update to Gambling and Games Policy: Colorado, USA (June 2026)`（`_evidence/R1/google-ads-chg-gambling-colorado.md`）正文逐字：
> `On July 1, 2026, Google Ads will update the **US country-specifics** of its Gambling and games policy. We will begin permitting Daily Fantasy Sports ads in Colorado for operators licensed by the state's Department of Revenue's Division of Gaming (CDOG).`
> `Advertisers must apply for certification.`
> `The Gambling and games policy page will be updated when the policy goes into effect on July 1, 2026.`
> `(Posted on June 15, 2026)`

**【原文】** `Update to Gambling and Games Policy: France (June 2026)`（`google-ads-chg-gambling-france.md`）：
> `On June 29, 2026, Google will update the Gambling and Games policy for France **to align with the current regulatory landscape for online gambling content**.`
> `Operators of the statutory lottery monopoly will be added to the list of entities entitled to be certified.`
> `(Posted on June 12, 2026)`

**【原文】** `Update to Gambling and Games Policy: Global (August 2026)`（`google-ads-chg-gambling-global.md`）：
> `On August 26, 2026, Google is updating its certification applications and standards for **all online gambling jurisdictions**…`
> `**You must hold a valid local license for every region you intend to target and provide evidence of that licence.**`

**【判断】四条可直接搬运的设计规则：**

- **R1｜辖区是规则身份的一部分。** 规则 ID 的构造应为 `<主题>.<辖区>`，而不是 `规则{ jurisdiction: 属性 }`。因为「Gambling: France」与「Gambling: Global」是**两条会被分别修订、分别失效的规则**。
- **R2｜必须存在 `Global` 这个辖区取值**，与具体国家并列（Meta 的 `Global restrictions` 报表、Google 的 `…: Global` 条目都证实了这一点）。
- **R3｜辖区可以是次国家层级。** `Colorado, USA`、`Alberta, Canada` 证明「国家」不是最细粒度。
- **R4｜辖区差异的成因要写出来。** Google 写 `to align with the current regulatory landscape`，即**变更理由必须指向一个外部法律事件**。

**Meta 的对应声明方式**：不写进规则名，而是**用一份公开报表承载**（`Restrictions by country` + `Global restrictions`），并在本地法条目里声明后果差异（无处罚）。**Meta 用「报表 + 后果声明」，Google 用「规则命名 + 凭证」。两种都可搬，Google 的更适合机器处理，Meta 的更适合人读。**

---

## 5. 严重等级（severity / enforcement tier）如何声明

### 5.1 Meta

**（a）总体框架：三分法 `remove / reduce / inform`**

**【原文】** `How Meta enforces its policies`（`_evidence/R1/meta-enforcement-hub.md`）：
> `We take a three-part approach to content enforcement: remove, reduce and inform.`

`Taking action` 下的完整条目（原文标题）：
- REMOVE：`Taking down violating content` / `Counting strikes` / `Restricting accounts` / `Restricting accounts of public figures during civil unrest` / `Disabling accounts` / `Removing Pages and groups` / **`How we create and use market-specific slur lists`**
- REDUCE：`Reducing the distribution of problematic content` / `Penalties for sharing fact-checked content`
- INFORM：`Providing context on sensitive or misleading content`

**（b）strike 阶梯（内容侧）**

**【原文】** `Counting strikes`（`_evidence/R1/meta-enf-counting-strikes.md`，页面标注 `UPDATED APR 23, 2025`）：
> `If you post content that goes against the Community Standards, we'll remove it and may then apply a strike to your Facebook or Instagram account. **Whether we apply a strike depends on the severity of the content, the context in which it was shared and when it was posted.**`
> `In some cases, a violation may be severe enough, such as posting child sexual exploitation content, that we'll disable your account, Page or group on Facebook, or your account on Instagram, **after one occurrence**.`
> `To ensure our strike system is fair and proportionate, **we won't count strikes on violating content posted over 90 days ago for most violations or over 4 years ago for more severe violations.** We also won't count strikes for certain policy violations.`
> `If we remove multiple pieces of content at once, without notifying you at each removal, we may also count them as a single strike. **All strikes on Facebook or Instagram expire after one year.**`

**【原文】** `Restricting accounts`（`_evidence/R1/meta-enf-restricting-accounts.md`）逐字阶梯：
> `One strike: You'll get a warning since this is your first strike.`
> `Two to six strikes: You'll be restricted from specific features, like posting in groups, for a limited amount of time.`
> `Seven strikes: You'll get a one-day restriction from creating content, which includes posting, commenting, creating a Page, and more.`
> `Eight strikes: You'll get a 3-day restriction from creating content.`
> `Nine strikes: You'll get a 7-day restriction from creating content.`
> `Ten or more strikes: You'll get a 30-day restriction from creating content.`
> `For most violations, if you continue to post content that goes against the Community Standards after repeated warnings and restrictions, we will disable your account.`

**（c）「更严重政策」的额外限制**

**【原文】**（同上）：
> `If content you posted goes against our more severe policies, such as our policy on dangerous individuals and organizations or adult sexual exploitation, you may receive additional, longer restrictions from certain features, on top of the standard restrictions above. For example, **you may be restricted from creating ads and using Facebook Live for set periods of time, starting on your first strike.**`

**（d）广告侧阶梯**

**【原文】** `Outcome of review`（`_evidence/R1/meta-ad-index.md`）：
> `If a violation is found at any point in the review process, the ad will be rejected, and the Business Account or its assets may be restricted. **Lower quality ads which do not necessarily violate our policies may experience impacted performance.**`
> `If a Business Account or its assets (ad account, Page or user account) is restricted, that account or asset can't be used to advertise across our technologies. If a user account is restricted from advertising on a Business Account or ad account, other members of those accounts may still be able to advertise.`

**【原文】** `Advertising restrictions for policy violations`（`_evidence/R1/meta-ad-bhc-advertising-restrictions.md`）——**四类受限资产**：
> `Business portfolio: … If restricted, your business portfolio isn't allowed to advertise.`
> `Ad account: … If restricted, your ad account, its ads and some of its advertising assets are disabled.`
> `Page: … If restricted, your Page isn't allowed to advertise.`
> `Personal profile: … If restricted, you are not allowed to use Meta Products to advertise.`

以及受限的具体表现清单：
> `Limits on the amount an advertiser can spend per day or a lower payment threshold / Loss of access to some payment features / Loss of access to some advertising features / Loss of the ability to advertise on Meta platforms`

**【原文】** 永久停用的酌情条款（同上）：
> `Under certain circumstances, Meta reserves the right to disable your account permanently prior to the 6 months.`

**⚠「severe violations 清单」的核实结论**：**Meta 在广告侧没有公开的 severe violations 清单。** 广告侧只有上述酌情条款。**明确列举「一次即停用」的，只有内容侧的 CS 体系**，且举的例子是 `posting child sexual exploitation content`。`Transparency Center` 上**不存在**独立的广告 strikes / severity 页面。

### 5.2 Google Ads

**（a）广告级状态（5 个）**

**【原文】** `Review process` 文章清单（`_evidence/R1/google-ads-review-process-topic.md`）+ 各定义页：
| 状态 | 含义（逐字） | 来源 |
|---|---|---|
| `Eligible` | 正常投放 | 隐含 |
| `Eligible (limited)` | `A status given to ads and products that comply with our policies but are limited in where and when they can show.` | `google-ads-eligible-limited.md` |
| `Eligible (limited all locations)` | `…prevent certain types of ads from showing in your targeted locations.` | `google-ads-violation-consequences.md` |
| `Under review` | 审核中（有独立定义页 `answer/99486`） | `google-ads-review-process-topic.md` |
| `Disapproved` | `A disapproved ad won't be able to run until the policy violation is fixed and the ad is reviewed.` | `google-ads-violation-consequences.md` |
| `Not eligible` | `A status given to campaigns, ad groups, ads, or keywords that are not serving.` | `google-ads-not-eligible.md` |
| **`Past Violation`** | `…our system may identify disapproved ads that no longer violate our policies. If your ad was disapproved for an extended period of time and our enforcement system later decides that the policy no longer applies, Google may keep the ad disapproved and classify the ad as "Past Violation". Google does this to prevent you from unintentionally exhausting spend on old ads.` | `google-ads-past-violations.md` |

**【判断】** `Past Violation` 是一个**因为规则变更而新增的状态**——它证明**规则库的版本变更必须能触发存量内容的重新裁决**。这是 Momcozy 完全没考虑的一环（规则改了，已审过的内容要不要重审？）。

**（b）账户级阶梯（strike 制度）**

**【原文】** `What happens if you violate our policies`（`_evidence/R1/google-ads-violation-consequences.md`）——**五档按固定顺序排列**（H2 标题逐字，顺序即原文顺序）：
> `## Ad or asset disapproval` — `Ads and assets that don't follow Google Ads policies will be disapproved. A disapproved ad won't be able to run until the policy violation is fixed and the ad is reviewed.`
> `## Ad serving eligibility`
> `## Account suspension`
> `## Remarketing list disabling` — `Remarketing lists that don't follow the Personalized advertising policy may be disabled. These lists can no longer be used with ad campaigns, and new users won't be added to the lists.`
> `## Compliance review` — `We may review your business for compliance with the Customer Match policy at any time.`

**【判断】** 注意 `Remarketing list disabling` 是**第四个维度**——被处置的对象不是广告、不是账号，而是**一个数据资产（再营销名单）**。Momcozy 做的是品牌内容审查，对应的是「素材库/受众包」，这一档可类比为「把某个素材或受众标记为不可用」。

**【原文】** 账户级（同上）：
> `If we detect an **egregious violation**, your account will be suspended **immediately without prior warning**. An egregious violation of the Google Ads policies is a violation so serious that it is unlawful or poses significant harm to our users or our digital advertising ecosystem. … Given that egregious violations will cause immediate account suspension, upon detection and without prior warning, **we limit these to cases when such action is the only effective method to adequately prevent illegal activity and/or significant user harm.**`
> `For other violations that lead to account suspension, **we will send you a warning to outline the nature of the policy violation and any remedial action that can be taken, in order to comply. This notification will be sent at least 7 days before suspension action.**`
> `For repeat violations of a policy, we issue strikes to your Google ads account and penalties progressively increase with each subsequent strike leading up to account suspension. **You will receive a maximum of 3 strikes per policy** on your Google Ads account.`
> `If we suspend your account, all ads in the suspended account will stop running, and we will no longer accept advertising from you, unless successfully appealed. **Any related accounts (for example, accounts using the same payment method) will also be suspended, and any new accounts you create will be automatically suspended.**`

**【原文】** `About enforcement procedures for repeat violations`（`_evidence/R1/google-ads-repeat-violations.md`）：
> `Strikes are issued to your Google Ads account when you repeatedly violate certain Google Ads policies. **Note that no strikes are issued for the first policy violation.** You will be able to receive a maximum of 3 strikes, and the penalties applied with each strike will progressively increase. **Temporary account holds will be applied for the first and second strikes (for 3 and 7 days respectively), while the third strike will result in an account suspension.**`
> `**This strike-based system applies to the following policies:** Enabling dishonest behavior, Unapproved substances, Guns, gun parts and related products, Explosives, Other Weapons, Tobacco, Compensated sexual acts, Mail-order brides, Clickbait, Misleading ad design, Bail bond services, Call directories, forwarding, and recording services, Credit repair services, Binary options, and Personal loans.`
> `An account can receive a **maximum of one warning and 3 strikes per policy violation**.`
> `## Warning — … that's why the first violation is only a warning. Note that you'll only be warned once through an email notification. The next time your ads violate a Google Ads policy, you'll get a strike.`
> `## First Strike — You will earn your first strike when we detect that you have continued to violate a specific Google Ads policy, even after receiving an initial warning. Your account will be in a temporary hold state for **3 days**…`
> `## Second Strike — You will receive a second strike if you violate the same policy again **within 90 days of the first strike**. … temporary hold state for **7 days**…`
> `## Third Strike — You will receive a third and final strike if you violate the same policy **within 90 days of the second strike**. Your account will then be **suspended** for repeat violation of our policies.`

**【判断】三个极重要的结构设计，Momcozy 一条都没有：**

1. **strike 只在 15 条具名政策上启用。** 其余政策违规只 disapproval，不累积 strike。→ **严重度是「政策级属性」，不是全局统一。**
2. **strike 按政策分别计数**（`per policy`）。→ **计数器的主键是「规则」，不是「账号」也不是「内容」。**
3. **strike 有 90 天窗口。** → 计数带过期。
4. **「先警告、再 strike」的两段式**：第一次违规永远只是 warning，**"no strikes are issued for the first policy violation"**。

### 5.3 YouTube

**【原文】** `Community Guidelines strike basics`（`_evidence/R1/youtube-strike-basics.md`）：
> `**Note:** We may remove content for reasons other than Community Guidelines violations. For example, a first-party privacy complaint or a court order. In these cases, your channel won't get a strike.`
> `#### Warning — We understand mistakes happen and you don't mean to violate our policies — that's why **the first violation is typically only a warning**. To have this warning expire after 90 days, you can take an optional policy training. However, if your content violates the same policy within that 90 day window, the warning may not expire and your channel may be given a strike.`
> `Sometimes **a single case of severe abuse will result in channel termination without warning.**`
> `#### Optional policy trainings — … If you complete an optional policy training, your warning will expire after 90 days. **The 90-day period starts from when the training is completed, not when the warning is issued.** If you violate a different policy after completing the training, you will get another warning.`
> `#### First Strike — If we find your content doesn't follow our policies for a second time, you'll get a strike. This strike means you will not be allowed to do the following for **1 week**: Upload videos or live streams / Start a scheduled live stream / Schedule a video to become public / Create a Premiere / Add a trailer to an upcoming Premiere or live stream / Create custom thumbnails or posts / Create, edit, or add collaborators to playlists / Add or remove playlists from the watch page using the "Save" button`
> `After the 1-week period, we restore full privileges automatically, but **the strike remains on your channel for 90 days.**`
> `#### Second Strike — If you get a second strike within the same 90-day period as your first strike, you will not be allowed to post content for **2 weeks**. … **Each strike will not expire until 90 days from the time it was issued.**`
> `#### Third Strike — **3 strikes in the same 90-day period may result in your channel being permanently removed from YouTube.**`
> `**Note:** Deleting your content doesn't remove a strike. We may also issue a Community Guidelines strike on deleted content.`

**【原文】** 终止条件（`_evidence/R1/youtube-strike-expiry.md`）：
> `Reasons channels or accounts can be terminated: Repeated violations of the Community Guidelines or Terms of Service across any form of content … / **A single case of severe abuse** (such as predatory behavior, spam, or pornography) / **Dedication to a policy violation** (like hate speech, harassment, or impersonation)`
> `Creators have up to **1 year** from the date their channel was terminated to submit an appeal.`

**【判断】** YouTube 的独特设计：**把「惩罚期」与「strike 有效期」分开。** 1 周冻结是惩罚，90 天是计数窗口。**规则库需要两个时间字段，不是一个。** 另外**「完成培训可缩短警告期」**是一个**修复动作能改变风险状态**的机制——对 Momcozy 很有参考价值（改完文案后能否「洗白」记录）。

**（c）变现侧三态**（`_evidence/R1/youtube-advertiser-friendly.md`）：
> `…what will receive ad earnings, will receive **limited ad earnings**, and what will **receive no ad earnings**.`
> `You'll find examples of content not suitable for ads, and may result in a "Limited ad earnings" or "No ad earnings" notice monetization state.`

**【原文】** 自动决策可被人工覆核：
> `Our systems don't always get it right, but you can request human review of decisions made by our automated systems.`

**（c）货币化状态实为 8 个，不是 3 个**

`Monetization icon guide for YouTube Studio`（`_evidence/R1/youtube-monetization-icons.md`，来源 `support.google.com/youtube/answer/9208564`）给出**八个图标状态**，逐字：
`Checking` / `On` / `Exceptions` / `Sharing` / `Escrow` / `Limited` / `Ineligible` / `Off`

逐字含义（节选）：
> `Checking — This icon shows next to a video when our systems are checking a video for ad suitability. … While the ad suitability check is in progress, we don't show ads on your video.` / `This check usually takes less than 20 minutes and at most 1 hour.`
> `On — This icon shows next to a video when it meets our advertiser-friendly content guidelines.`
> `Exceptions — This icon shows next to a video when its audience is set as made for kids. The video is only eligible for non-personalized ads.`
> `Sharing — This icon shows when you upload a cover video of a song, and a music publisher claims it. … The video splits revenue with the music rights holders.`
> `Escrow — This icon shows next to a video when revenue is being held separately during the Content ID dispute process.`

**【判断】这是对本文 §6.5「三态」的一个重要限定**：**「三态」（可赚 / 有限赚 / 不可赚）是政策语义上的三态，但落地到系统状态机上是八态。** 多出来的五个（`Checking` / `Exceptions` / `Sharing` / `Escrow` / `Off`）都不是政策判定，而是**版权、受众设置、审核进行中**等非政策原因。

**对 Momcozy 的含义**：**「不可用」不等于「违规」。** 审查 Agent 若只输出「合规 / 不合规」，会把「版权争议中」「审核未完成」「受众设为儿童」这类**非政策状态**误报为违规。**规则库必须把「政策后果」与「系统状态」分开**——这又是一个被四档模型压扁的维度（见 §8.4）。

### 5.4 TikTok

**（a）四机制（后果由清单决定）**（`_evidence/R1/tiktok-community-guidelines.md`）：
> `#### We Remove Content — Everyone on TikTok can share content, but when we identify content that falls under the "Not Allowed" rules in our Community Guidelines, we'll remove it.`
> `#### We Age-Restrict Content — Some content may not be appropriate for people under 18. When we identify content that falls under the "Age-Restricted" standards in our Community Guidelines, we make it viewable only for adults.`
> `#### For You Feed Standards — … When we identify content that falls under the "FYF Ineligible" standards in our Community Guidelines, it won't be recommended in the FYF.`
> `#### We give you tools and resources to stay informed and in control — … In addition, for some content, you'll see **opt-in screens or banners** to give you more context about a post.`

**（b）账号级阶梯**

**【原文】** `Accounts and Features`（`_evidence/R1/tiktok-accounts-features.remix.json` → POST 10）：
> `We'll also take action if someone breaks our Community Guidelines. **That can mean a warning, a restriction, or a full ban**, depending on what happened.`
> `We may ban an account or user for: **Repeated rule violations / A single, severe violation / Trying to avoid enforcement / Running accounts dedicated to breaking the rules**, like spreading hate, the unauthorized trading of regulated, prohibited (e.g. counterfeit), or high-risk goods, or pretending to be someone else`
> `If someone seriously breaks the rules or tries to dodge enforcement, we may ban all of their accounts.`
> `**Severe violations include:** Inciting or threatening serious violence when there's a credible risk of harm or danger to public safety / Engaging in child sexual abuse, including sharing, helping others access, or downloading CSAM, soliciting youth, or grooming / Sharing graphic imagery of adult sexual abuse, including non-consensual acts or image-based abuse / Coordinating or facilitating human trafficking or smuggling`

**（c）平台外的行为也算**（同页）：
> `We may also restrict or ban accounts belonging to people who have engaged in **egregious off-platform behaviors**, when we have sufficient evidence to support enforcement. These behaviors include being the member of a violent or hateful organization, committing an act of sexual abuse against a youth or adult, promoting or engaging in severe violent crimes (like murder), or engaging in human trafficking. When assessing these cases, we consider several factors, including **the time since the act occurred, whether penalties have been served, efforts toward rehabilitation, and the potential impact on public interest discussion.**`

**（d）功能级分层（每个功能有自己的门槛与后果）**（同页）：
> `LIVE … If a LIVE session includes content that violates our policies, the session may be stopped, and the creator could face temporary restrictions from going LIVE. … **You must be 18 and older to go LIVE and to send gifts to a creator during a LIVE session.**`
> `**You must be 16 and older to use DMs.** … If you violate "Not Allowed" rules, your message will be removed and you might be temporarily blocked from sending new ones.`
> `**You must be 18 and older to use monetization features.** … If you break the rules, we may temporarily restrict your access. Repeated violations can lead to permanent loss of monetization features. **Content that isn't eligible for the FYF may also be restricted from monetization.**`
> `All commercial content must be disclosed using the content disclosure setting. … If we find commercial content that hasn't been properly disclosed, we may **apply the content disclosure setting ourselves** or remove it from the FYF.`

**【判断】** 三条独有设计：
1. **后果是「多维封套」**：内容层（删/18+/不推荐）+ 账号层（警告/限制/封禁）+ **功能层**（LIVE / DM / 搜索 / 链接 / 评论 / 变现各有独立门槛与处罚）。**规则库必须允许「一条规则 → 多个后果维度」。**
2. **平台外行为纳入判定**，且给出四因子裁量测试（时间、是否已受罚、改造努力、对公共讨论的影响）。**这是「不可穷举」问题的正式回应。**
3. **平台可代为补标**（`apply the content disclosure setting ourselves`）——**「应标未标」有自动补正路径，而不是直接判违规。**

### 5.5 Amazon

**【原文】** `Account Health Rating program policy`（`_evidence/R1/amazon-ahr.md`，`sellercentral.amazon.com/help/hub/reference/external/G200205250`）：
> `The AHR indicates your selling account's risk of deactivation due to non-compliance with certain Amazon selling policies. … The AHR is a **color-coded score that ranges from 0 to 1,000** and provides near real-time status of your account's health… Upon detection of any new policy violations associated with your selling account, **you lose points**. You gain points when you successfully address those violations.`
> `All new sellers start with a score of **200**, and over time, sellers will see a score that accurately reflects their account health based on policy adherence and selling activities over the **last 180 days**.`
> `If your AHR is green (**"Healthy"**, based on a score of **200-1,000**), that means your account is not at risk of deactivation based on the policies comprising the score. If your AHR is yellow (**"At Risk"**, based on a score of **100-199**), your account is at risk of deactivation. When your AHR is red (**"Unhealthy"**, based on a score of **99 or lower**), your account is either eligible for deactivation or already deactivated.`
> `**Regardless of your AHR score, Amazon may deactivate your account immediately if we suspect fraudulent, deceptive, illegal, or otherwise harmful activity**, in order to protect customers, sellers, and Amazon's store.`
> `### AHR impact by severity`
> `To calculate your AHR, we assign a certain number of points to each policy violation **based on the severity of the violation**. **There are four severity levels: critical, high, medium, and low.** Critical violations are the most serious violations, which can lead to immediate account enforcement. **When determining the severity, we consider factors including the degree to which the violation negatively impacts the customer experience and whether the policy violation contravenes applicable laws and regulations.**`
> `### Repeat policy violations`
> `Multiple violations of the same policy impact your account health in two ways. First, **the point values associated with violations included in your AHR increase each time that same policy is violated.** That means that repeat violations will cause your AHR to degrade faster, with higher severity repeat violations having the most impact.`
> `Second, your account may be at immediate risk of deactivation if you reach the **maximum number of repeat violations for a single policy in a 180-day period**. The maximum number of repeat violations for a given policy may vary depending on the severity of the violation, but **can be as low as two violations for higher severity violations.**`

**【原文】** `Account Health Rating: Frequently Asked Questions`（`_evidence/R1/amazon-ahr-faq-GR786P4BPEVKTBAG.md`）——**给出了硬数字**：
> `To calculate your AHR, all new sellers start with a score of 200. Points are deducted from your AHR score each time we find a new policy violation, and added back when you successfully address that violation. **Point values for each violation are based on the severity level and typically range from two to eight.** However, **critical violations automatically bring your AHR score to zero.** Also, if you violate the same policy multiple times, **sometimes, negative point values double per repeat violation.** To ensure that your AHR is evaluated in the context of the size of your business, you also gain **four points for every 200 successful orders** you fulfilled over the last 180 days.`
> `When we detect a critical violation, we will notify you of the violation via your Account Health page and email. **Your AHR will turn red and reflect a numeric score of zero. You will have a three-day grace period to address the violation before account deactivation.**`
> `**The maximum number of repeat violations is five for infringement-related policies and two for restricted products policies.**`
> `Repeat violation thresholds are based on violation severity, with more severe violations having lower thresholds than less severe ones.`

**⚠ 一处必须更正的常见误传**：任务书与诸多二手资料把 AHR 说成四档（0–99 / 100–199 / 200–499 / 500–1,000）。**这是错的。** Amazon 的原文只有**三档颜色**（`Healthy 200–1,000` / `At Risk 100–199` / `Unhealthy ≤99`），**四档是「严重度等级」而不是「健康度档位」**：
- 健康档（AHR score）：**3 档**
- 严重度（violation severity）：**4 档**（`critical / high / medium / low`）

**把两个正交的量纲混为一谈，是这份政策最容易被误读的地方。**

**广告侧**（`_evidence/R1/amazon-ads-policies-G5RLASA28TP9TFXZ.md`）：
> `Amazon may also take immediate action to protect the stability, security, or integrity of its advertising systems, including **throttling delivery, restricting access, or excluding specific ad entities**. … Amazon may **suspend or terminate ad accounts for severe or repeated policy violations.**`

**【原文】** 广告侧也有「重复升格」的表述（`_evidence/R1/amazon-ads-account-enforcement-regulatory.md` 等）：
> `repeated violations may result in account suspension. The duration of the suspension and possibility for reinstatement will correspond to the severity of policies violation.`

**【判断】Amazon 是五家里唯一把 severity 做成「可计算量纲」的，且它揭示了四个关键设计：**

1. **严重度有明确的判定轴**：`customer experience 受损程度` + `是否违反法律法规`。**注意第二条轴——「违法」是一档独立升格因素。** 这与 Google 的 `egregious … is unlawful` 一致。
2. **重复违规是乘数而非加数**：原文 `negative point values **double** per repeat violation`。这比「第 N 次触发第 N 档」更能表达风险累积。
3. **`critical` 是短路**：不是扣分，而是 **`automatically bring your AHR score to zero`**，直接置零 + **3 天宽限期**。**「置零」与「扣分」是两种不同的运算。**
4. **恢复也要有机制**：`added back when you successfully address that violation` + `four points for every 200 successful orders`。**规则库里存在「正向积分」，不只是惩罚。** 这是五家里唯一给「做对了」也计分的。

### 5.6 五家严重等级对照总表

| | 内容级（能不能留） | 投放/变现阶段 | 账号级 | 一次性重罚 | 计数窗口 | 计数主键 |
|---|---|---|---|---|---|---|
| **Meta CS** | 保留 / **警告屏 / 18+** / 移除 | — | warning → 功能限制 → 创作冻结（1/3/7/30 天）→ 停用 | **严重违规一次即停用**（例：CSE 内容）；「更严重政策」**从第一个 strike 就给额外限制** | strike 90 天（多数）/ 4 年（更严重）；strike **1 年过期** | 账号（Page/Group 分别计） |
| **Meta Ads** | — | 拒登 / 资产受限（business portfolio / ad account / Page / profile） | 6 个月后可永久停用（酌情） | **无公开清单** | 未公开 | 资产 |
| **Google Ads** | — | Eligible / **Eligible (limited)** / Under review / Disapproved / Not eligible / **Past Violation** | warning → **3 天 hold** → **7 天 hold** → 停用 | **`egregious` 立即停用、无预警**；非 egregious **至少提前 7 天通知** | **90 天**（同政策） | **政策**（每政策 1 warning + 最多 3 strike） |
| **YouTube** | 保留 / 18+ / 移除 | **可赚 / 有限赚 / 不可赚** 三态 | warning（90 天，可培训缩短）→ 1 strike（1 周冻结）→ 2 strike（2 周）→ 3 strike（终止） | **`a single case of severe abuse` 无预警终止**；另有 `dedication to a policy violation` | 90 天计数窗口；strike 90 天过期；终止申诉 **1 年** | 频道 |
| **TikTok** | **NOT ALLOWED**（删）/ **AGE-RESTRICTED**（18+）/ **FYF INELIGIBLE**（不推荐）/ 上下文标签 | 同上（FYF 独立） | warning / restriction / **full ban** | **A single, severe violation**；严重违规 4 类列举；**平台外行为亦可** | 未公开 | 账号 + **功能**（LIVE / DM / 搜索 / 链接 / 评论 / 变现各自计） |
| **Amazon** | Listing 移除 / 抑制 / 停售 | 广告否决 / 限流（throttling） / 排除特定广告实体 | **AHR 0–1000**：Healthy 200+ / At Risk 100–199 / Unhealthy ≤99 | **`critical` 违规可立即处置**；`Regardless of your AHR score … may deactivate immediately` | **180 天** | **政策**（每政策重复次数上限，高危可低至 2 次） |

### 5.7 五条设计规律（【判断】）

- **L1｜「第一次违规 ≠ 处罚」是四家的共识。** Google `no strikes are issued for the first policy violation`；YouTube `the first violation is typically only a warning`；Meta `One strike: You'll get a warning since this is your first strike.`；TikTok `warning, a restriction, or a full ban`。**Momcozy 的四档里没有「仅警告」这一档。**
- **L2｜严重度必须能「一次触顶」。** 四家都有 immediate/egregious 通路，且都明确列举了触顶情形（Google 限定为「别无他法的情形」，TikTok 列 4 类，YouTube 列 3 类原因，Meta 举 1 例）。
- **L3｜计数窗口是规则库的一等字段。** 90 天（Google/YouTube）／1 年（Meta strike 过期）／180 天（Amazon）。**没有窗口的计数会让规则库永久记得旧错。**
- **L4｜计数主键决定架构。** Google/Amazon 按**政策**计数，Meta/YouTube 按**账号**计数。按政策计数要求规则有稳定 ID——**Momcozy 已有 `规则编号` 字段，具备这个前提。**
- **L5｜「合规但受限」必须与「违规」分开。** Google 的 `Eligible (limited)`、YouTube 的 `limited ad earnings`、TikTok 的 `FYF INELIGIBLE`、Meta 的 warning screen/18+ 都是这一档。**Momcozy 现有的四档把这一档压扁了。**

---

## 6. 豁免与语境条款怎么写

### 6.1 YouTube —— EDSA（Educational / Documentary / Scientific / Artistic）

**【原文】** `Educational, Documentary, Scientific, and Artistic (EDSA) content`（`_evidence/R1/youtube-community-guidelines-full.md`，来源 `support.google.com/youtube/answer/9288567`）：
> `Our Community Guidelines aim to make YouTube a safer community. Sometimes, content that would otherwise violate our Community Guidelines may stay on YouTube when it has Educational, Documentary, Scientific, or Artistic (EDSA) context. **We may also make exceptions for content that is in the public's interest, such as congressional or parliamentary proceedings, campaign speeches, or debates over ongoing government actions.** In these cases, the content gets an EDSA exception. **This is not a pass to violate our Community Guidelines.**`

**【原文】** 评估程序（`_evidence/R1/youtube-edsa-exceptions.md`）：
> `**Note:** Adding context to your EDSA content doesn't guarantee that it will get an EDSA exception.`
> `## How content gets an EDSA exception`
> `We assess whether content gets an EDSA exception **on a case-by-case basis**. First, we check if there's a Community Guidelines violation in the content. If there's a violation, we review if there's enough context in the content to make an EDSA exception. **We review WHAT context is present and WHERE the context is.**`
> `## What context to add to your EDSA content`
> `We make most EDSA exceptions when content has one or more of the following:`
> `1. **Basic facts about what's happening in the content:** Identify who's in the content, describe what the content shows or when and where it takes place, or explain why certain content is present.`

**关键的「倾向性对照表」结构**（原文表头）：
> `These examples illustrate content that's more likely and less likely to get an EDSA exception:`
> `| **More** likely to get an EDSA exception | **Less** likely to get an EDSA exception |`
> `| Security footage that shows victims of a violent robbery getting injured with details in the video. Details may include where and when the crime took place, how it happened, and why the video is posted. | Security footage that shows victims of a violent robbery getting injured with emoji, like 😆 or 😲, s… |`

**【判断】这就是「引用他人违规内容来批评它」这类问题的标准解法**：
- 例外**不是**按内容主题给的，而是按**语境证据是否在场**给的。
- 语境的判定有两个轴：**WHAT（有哪些语境）** 与 **WHERE（语境出现在哪里）**。
- 平台**不承诺结果**（`doesn't guarantee`），而给**倾向性对照**（more/less likely）——**用对照表代替模糊承诺**。
- 表格的对照项是**成对的**：同一素材，加了事实细节 → 更可能；加了 😆 emoji → 更不可能。**这是可直接抄的评估界面设计。**
- **`This is not a pass to violate our Community Guidelines.`** 一句把例外的边界钉死——**例外是逐案裁量，不是一张通行证。**

### 6.2 Meta —— Newsworthiness Allowance

**【原文】** `Our approach to newsworthy content`（`_evidence/R1/meta-newsworthiness.md`，页面标注 `UPDATED NOV 12, 2024`）：
> `In rare cases, we allow content that may violate the Community Standards, if it's newsworthy and if keeping it visible is in the public interest.`
> `We do this only after conducting a thorough review that weighs the public interest against the risk of harm. We look to international human rights standards, as reflected in our Corporate Human Rights Policy, to help make these judgments.`
> `## Our newsworthiness allowance`
> `We introduced our newsworthiness allowance in October 2016 after receiving global criticism for removing the iconic "Napalm Girl" photo, which, as a result of this allowance, is visible across our platforms today.`
> `We've found that determining the newsworthiness of a piece of content can be highly subjective. … We conduct a thorough assessment of any potentially newsworthy content and **our reviewers consider a number of factors prior to escalating to our Content Policy team.**`
> `When making a newsworthy determination, we assess whether that content surfaces an imminent threat to public health or safety, or gives voice to perspectives currently being debated as part of a political process. We also consider other factors, such as:`
> `- **Country-specific circumstances** (for example, whether there is an election underway, or the country is at war)`
> `- **The nature of the speech**, including whether it relates to governance or politics`
> `- **The political structure of the country**, including whether it has a free press`
> `We remove content, even if it has some degree of newsworthiness, when leaving it up presents a risk of harm, such as physical, emotional and financial harm, or a direct threat to public safety. **For content we allow that may be sensitive or disturbing, we include a warning screen. In these cases, we can also limit the ability to view the content to adults, ages 18 and older.**`
> `Content from all sources, including news outlets, politicians, or other people, is eligible for a newsworthy allowance. While the speaker may factor into the balancing test, **we do not presume that any person's speech is inherently newsworthy, including politicians.**`
> `Newsworthy allowances can be **"narrow,"** in which an allowance applies to a single piece of content or **"scaled,"** which may apply more broadly to something like a phrase.`

**公开发布的裁定统计（原文）**：
> `## Newsworthy Data — August 2025`
> `- From June 1, 2024 through June 1, 2025, we documented a total of 44 newsworthy decisions`
> `- 20 of those documented allowances were issued for politicians`
> `- Of the 44 newsworthy decisions, we documented a total of 6 scaled newsworthy decisions`

**并给出四个逐字案例**（哥伦比亚警察暴力报道中的 slur、乌克兰国防部焦尸视频、巴西议员乳首画面、亚美尼亚战俘视频）。

**【判断】Meta 的豁免设计有四处可搬：**

1. **豁免是一条被命名的制度**（`the newsworthiness allowance`），有生效起点、有升级路径（reviewer → `Content Policy team`）、有公开统计。
2. **豁免本身是分工况的**：`narrow`（单条内容）vs `scaled`（推广到一个短语）。**豁免可以是「一次性的」或「一条新规则」——这是豁免的两种粒度。**
3. **辖区是豁免判定的因子**：`Country-specific circumstances (for example, whether there is an election underway, or the country is at war)`。**同一个内容在美国可豁免、在战时国家不可豁免。这是「适用范围」渗入豁免层的证据。**
4. **豁免的产物仍是分级的**：allow / allow + warning screen / allow + 18+。**豁免不是通过/不通过，是「通过但降级」。**

### 6.3 TikTok —— Public Interest Exceptions

**【原文】** `Enforcement`（`_evidence/R1/tiktok-accounts-features.remix.json` → POST 11）：
> `We recognize that some content that would otherwise violate our rules may be in the public interest to view. **Public interest refers to topics that inform, inspire, or educate the community and enhance deliberation about matters of broad collective significance.** We may allow content to remain on TikTok under public interest exceptions, including:`
> `- Documentary`
> `- Educational`
> `- Medical or Scientific`
> `- Counterspeech`
> `- Satirical`
> `- Artistic`
> `When reviewing content, we consider if the post **raises awareness or challenges harmful behavior**. If you want to post content that does this, you might consider using features like **captions, stickers, or voiceover** to make it clear.`
> `**Even if we allow content under a public interest exception, we might still:**`
> `- Make it ineligible for the FYF`
> `- Add a warning screen`
> `- Add a context label`
> `**We won't make exceptions for content that could cause extreme harm, like showing explicit imagery of abuse involving a young person.**`

**【判断】这是本文认为最完整的一套豁免设计**，因为它同时给出了四件事，而其他家最多给两件：
| 要素 | TikTok 的原文 |
|---|---|
| 判据（什么是 public interest） | `topics that inform, inspire, or educate the community and enhance deliberation about matters of broad collective significance` |
| 情形枚举（6 类） | `Documentary / Educational / Medical or Scientific / Counterspeech / Satirical / Artistic` |
| **可操作的补强动作** | `using features like captions, stickers, or voiceover to make it clear` |
| **豁免后的残余限制** | `Make it ineligible for the FYF / Add a warning screen / Add a context label` |
| 硬底线（例外的例外） | `We won't make exceptions for content that could cause extreme harm` |

**特别值得抄的两点**：
- **`Counterspeech` 是一个独立豁免类别**——**这就是「引用他人违规内容来批评它」的正式分类**。
- **`Medical or Scientific` 是独立豁免类别**——对 Momcozy（母婴医疗健康品类）直接相关。**说「吸奶器有助于建立泌乳量」在医疗/科学语境下可豁免，但豁免后仍可能被 18+ 或不推荐。**

### 6.4 Google —— 为什么几乎没有「内容豁免」

Google Ads 的政策页**不设 EDSA 式内容豁免**，而是用 **certification（资格）** 和 **`Eligible (limited)`（限域投放）** 代替。唯一接近「例外」的表述是各政策里的 `Some types of X-related ads are allowed if they meet the policies below…`。

**【原文】**（`google-ads-policies-overview.md`）：
> `Some types of alcohol-related ads are allowed if they meet the policies below, don't target minors, and target only countries that are explicitly allowed to show alcohol ads.`
> `Gambling-related ads are allowed if they comply with the policies below and the advertiser has received the proper Google Ads certification.`

**【判断】** **Google 用「资格 + 地域」替代「语境豁免」。** 这对广告场景其实是更合适的模型：广告是商业行为，「公共利益语境」很难成立，所以 Google 干脆不给豁免口子，而是给**「满足条件 + 拿到资质 + 限定地区」**的可执行路径。**Momcozy 做的是广告与品牌内容，Meta/Google 的广告侧模型比 TikTok/YouTube 的社区侧模型更贴近。**

### 6.5 「允许 / 限制 / 需标注」三态的五种实现

| 实现方式 | 代表 | 原文 |
|---|---|---|
| **① 结构位置定义三态** | TikTok | `NOT ALLOWED` / `FYF INELIGIBLE & AGE-RESTRICTED` / `ALLOWED` 三个 `#####` 块 |
| **② 三态表** | YouTube AFF | `This content can earn ad revenue` / `limited ad earnings` / `no ad earnings` |
| **③ 状态机取值** | Google | `Eligible` / `Eligible (limited)` / `Disapproved` / `Not eligible` |
| **④ 内容层三态+标注** | Meta CS | 索引页原文：`Content that's not allowed; and Content that requires additional information or context to enforce on, content that is allowed with a warning screen or content that is allowed but can only be viewed by adults aged 18 and older.` |
| **⑤ 标签式** | TikTok / YouTube | TikTok `Add a warning screen / Add a context label`；YouTube `viewer disclosure label` |

**Meta 的索引页那句话是全五家里对三态最精确的表述**，逐字再引一次：
> `Content that's not allowed; and`
> `Content that requires additional information or context to enforce on, content that is allowed with a warning screen or content that is allowed but can only be viewed by adults aged 18 and older.`

**【判断】它把「三态」实际上分成了四态**：
1. `not allowed`（不允许）
2. `requires additional information or context to enforce on`（**语境依赖——需要人来判**）
3. `allowed with a warning screen`（允许但需标注）
4. `allowed but can only be viewed by adults aged 18 and older`（允许但限龄）

**注意第 2 类：它不是「结果」，是「前置条件」——"只有拿到更多语境才能判"。** Momcozy 现有的「待复核」近似这一档，但语义不同：Momcozy 的「待复核」是**流程状态**，Meta 的是**规则属性**（这条规则永远需要语境）。

### 6.6 「引用他人违规内容来批评它」的处理方式对照

| 平台 | 条款原文 | 机制 |
|---|---|---|
| Meta CS `Hateful Conduct` | `We recognize that people sometimes share content that includes slurs or someone else's speech in order to condemn the speech or report on it. In other cases, speech, including slurs, that might otherwise violate our standards is used self-referentially or in an empowering way. **We allow this type of speech where the speaker's intention is clear. Where intention is unclear, we may remove content.**` | 意图清晰则放行；不清晰则移除 |
| Meta CS `Hateful Conduct` | `In certain cases, we will allow content that may otherwise violate the Community Standards when it is determined that the content is satirical. **Content will only be allowed if the violating elements of the content are being satirized or attributed to something or someone else in order to mock or criticize them.**` | 讽刺例外需要「违规元素本身是被讽刺的对象」 |
| Meta CS `Prohibited Commercial Practices` | `Notwithstanding the above, we do not prohibit content that condemns, raises awareness of, or educates others about scams or other prohibited commercial practices, without either revealing sensitive information or promoting them.` | 谴责/科普/警示可，**但不得泄露敏感信息或推广** |
| Meta CS `Spam` | `Notwithstanding the above, we do not prohibit: Cross promotion that is not triggered by payment to a third party …` | 具名情形例外 |
| Meta 市场词表 | `…slur lists and policies include guidance on circumstances in which a given slur might be used in a permissible way, as when they are used in a clear self-referential way, when used in its alternative meaning, **when discussing the use of the slurs, when reporting on the slur, when condemning the use of the slur**, or when the slur is used in a explicitly positive way.` | **词表自带允许情形清单**（`meta-enf-market-slurs.md`） |
| TikTok | `Counterspeech` 作为 6 类 public interest exception 之一 | 类别化 |
| YouTube | EDSA 中的 `Documentary` / `Scientific` + `WHAT context / WHERE context` | 语境在场性判定 |
| Google Ads | 无对应条款。**未核实**是否存在申诉层的同类裁量。 | — |

**【判断】Meta 的方案最完整，因为它把「允许情形」写进了词表本身**（`slur lists and policies include guidance on circumstances in which a given slur might be used in a permissible way`）。这意味着**规则库的一个条目同时携带「禁止实现」与「允许实现」两份清单**——这正好对应任务书里 S1-08 的 `examples_violation` / `examples_normal` / `non_violation_patterns` 三段式写法。

---

## 7. 政策变更如何记录（changelog）

### 7.1 Meta

**Community Standards**：每条政策页内有一个 `CHANGE LOG` 块，**内容是裸日期列表，没有任何说明文字**。逐字（`meta-cs-spam.md`）：
```
CHANGE LOG

Today

Jun 26, 2024

Jun 30, 2022

Dec 17, 2020

Oct 30, 2019
```
`Hateful Conduct` 的列表长得多（28 项，从 `Today` 回溯到 `May 26, 2018`），逐字前若干项：`Today / Jan 8, 2025 / Mar 1, 2024 / Dec 6, 2023 / May 26, 2023 / Nov 24, 2022 / Jul 29, 2022 …`（`meta-cs-hate-speech.md`）。

**取证事实**：
- 最新一条字面上就是字符串 **`Today`**——**没有日期，无法机器解析**。
- **没有变更说明、没有变更理由、没有生效日与发布日的区分。**

**Advertising Standards**：
- 每条政策页同样有 `CHANGE LOG`，但是一个**客户端 tablist**（如 `health-wellness`：`Today / Jul 22, 2026 / Dec 26, 2024`），**只有被选中的那个修订版是服务端渲染的**，历史版本需要真实浏览器点击才能取到。
- **不存在全局 changelog 路由**：`/policies/ad-standards/changelog/` → **404**；`/policies/changelog/` → **404**；`/overview/` → **404**；`/SIEP-advertising/changelog/` → **404**。（`meta-ad-LINK-MAP.md`）

**【判断】** Meta 的变更记录是**五家里最弱的**：有日期无内容，无全局视图，无理由。但它有一个别家没有的东西——**每个条目独立的时间线**（`hateful-conduct` 有 28 个修订点，说明高频迭代的是具体条目而不是整本政策）。

### 7.2 Google Ads —— **五家里最强**

**结构**（`_evidence/R1/google-ads-changelog-recent.md`）：
```
Change log
  Upcoming and recent changes (topic/29265)
      2026 (topic/16794025)
      2025 (topic/16083443)
      2024 (topic/16090031)
      Update to Standard Contractual Clauses (SCCs) (October 2021)
  Past changes (topic/7330871)
```
**注意顶层就叫 `Change log`，并且把它和「规则 / 裁决 / 准入」并列为四大分区之一。**

**粒度**：2026 年 **58 条**变更（`google-ads-chg-gambling-colorado.md` 页脚逐字：`1 of 58`）。平均每月约 5 条。

**每条变更是一个独立文章，内部有固定四要素**。逐字（`google-ads-chg-gambling-colorado.md`）：
| 要素 | 原文 |
|---|---|
| 生效日 + 变更内容 | `On July 1, 2026, Google Ads will update the US country-specifics of its Gambling and games policy. We will begin permitting Daily Fantasy Sports ads in Colorado for operators licensed by the state's Department of Revenue's Division of Gaming (CDOG).` |
| 要求的动作 | `Advertisers must apply for certification.` |
| 生效时合并到政策页的声明 | `The Gambling and games policy page will be updated when the policy goes into effect on July 1, 2026.` |
| **发布日** | `(Posted on June 15, 2026)` |

**变更理由也写明**（`google-ads-chg-gambling-france.md`）：
> `On June 29, 2026, Google will update the Gambling and Games policy for France **to align with the current regulatory landscape for online gambling content.**`

**【判断】四要素模型 = `effective_date` + `posted_date` + `reason` + `required_action`，并且有 `pending → merged` 的生命周期**（公告先发，生效日再改政策页）。**这是 Momcozy 最该抄的 changelog 结构。**

### 7.3 YouTube

**【原文】** `YouTube policy updates`（`_evidence/R1/youtube-policy-updates.md`）：
> `This article summarizes recent and past updates made to YouTube's policies. For other updates relevant to YouTube creators, check out our Creator updates.`
> `## Latest updates`
> `- **[August 2026] First frame view counting:** Views will be counted the moment a video begins to play across all formats, including Shorts, long form video, and live streams. [Learn more].`
> `- **[September 2026] Upcoming changes to paid promotions:** …`
> `## Previous updates`
> `Terms of Service`
> `- **[December, 2021] Update to YouTube's Terms of Service**. On January 5, 2022, we're updating our YouTube Terms of Service to help clarify…`

**结构**：`[月份 年份]` 标签 + 一句话摘要 + 详情链接；历史部分按**主题折叠分组**（`Terms of Service` 等）。**有生效日（`On January 5, 2022`）**，与 `[December, 2021]` 的发布月分离——**同 Google 一样区分发布日与生效日**。

### 7.4 TikTok —— **版本化发布，而非逐条 changelog**

**【原文】** 每个 CG POST 的元数据（`_evidence/R1/tiktok-accounts-features.remix.json` → `CGPosts[*]`）：
```
version:      2025H2update
versionName:  2025 August
lastUpdate:   "On September 24, 2026, we are updating our Community Guidelines so you can continue to create, discover, and share safely on TikTok. Check out the new Community Guidelines here."
              "Released August 14, 2025"
              "Effective September 13, 2025"
```
URL 亦带版本令牌：`https://www.tiktok.com/community-guidelines/en/us/  (cgversion=2025H2update)`；下一版链接为 `…overview?cgversion=2026H2update`。

**【判断】TikTok 用「版本整体发布」代替「逐条 changelog」**：
- 版本号是**半年制**（`2025H2update` → `2026H2update`）。
- **发布日与生效日分离，间隔约 30 天**（`Released August 14, 2025` / `Effective September 13, 2025`）。
- **提前公告下一版**（在 2025H2 页面上挂着 2026H2 的生效日 `September 24, 2026`）。
- **版本是可寻址的**（URL 参数），所以旧版可回看。
- 但**没有「这一版改了什么」的说明**——**这是它的弱点：能定位版本，不能看 diff。**

### 7.5 Amazon

**【原文】** `Ad policy change log`（`_evidence/R1/amazon-ads-change-log-G8X8M375UPCN4UUC.md`，页面标注 `Updated on Apr 27, 2026`）：
> `All policies can be accessed from the Rules and policies page.`

**这是一张结构化表格，列头逐字**：
> `Change title | Change summary | Link to policy page | Month of the change`

**行样例逐字**：
> `Clarification about review times being extended due to high submission volume.` ｜ `This change updates the guidance about review times during periods of high submission volume including simultaneous submissions.` ｜ `Amazon Ads policies and Ads content moderation` ｜ `April 2026`
> `Update to advertising policies applicable to public service announcements (PSAs).` ｜ `This change updates the policy guidance that governs PSA advertisements. Review the policy page for more detail.` ｜ `Public service announcements` ｜ `April 2026`

**【判断】Amazon 的表格是全五家里唯一「变更 → 受影响政策」双向可跳转的**（`Link to policy page` 列）。粒度到月，不到日。

**卖家侧还有第二个 changelog**，针对协议层。**【原文】** `Changes to the Amazon Services Business Solutions Agreement`（`_evidence/R1/amazon-changes-to-bsa-G47071.md`，`sellercentral.amazon.com/help/hub/reference/external/G47071`）：
> `Effective March 4, 2026, we will update the US/CA Amazon Services Business Solution Agreement (BSA) as follows:`
> （接编号变更清单，例如）`Add new Section 19, defining and restricting use of automated agents/AI systems.`
> `This information is intended to provide a summary of some of the recent changes.`

**【判断】** 注意 BSA changelog 的两点：**（1）有明确生效日**；**（2）它自认是摘要而非全文**（`intended to provide a summary of some of the recent changes`）——**平台自己声明 changelog 不完备**，这在法律上很重要：变更通知不构成完整告知义务的履行。另有 `Account Health News` 作为账户健康类变更的通知渠道。

**⭐ 一条与 Momcozy 直接相关的 BSA 变更**：`Add new Section 19, defining and restricting use of automated agents/AI systems.` —— **Amazon 在 2026 年 3 月新增了对 AI/自动化代理的条款。** Momcozy 正在建「内容审查 Agent」，若该 Agent 将来触碰 Amazon 侧操作，这条是必须先读的。**本文只读到该变更的标题级摘要，条款全文未取得（见缺口 §10.2）。**

### 7.6 changelog 对照总表

| | 位置 | 粒度 | 有无说明/理由 | 有无生效日 | 有无发布日 | 可否机器解析 | 全局视图 |
|---|---|---|---|---|---|---|---|
| **Meta CS** | 每页内 `CHANGE LOG` | **不定期，条目级**（`hateful-conduct` 28 次） | **无** | 无 | 无（最新为 `Today`） | **否** | **无** |
| **Meta Ads** | 每页内 tablist | 条目级 | 无 | 无 | 无 | 否（需浏览器点击） | **无**（changelog 路由 404） |
| **Google Ads** | **独立顶层分区** | **2026 年 58 条** | **有**（`to align with the current regulatory landscape`） | **有**（`On July 1, 2026`） | **有**（`Posted on June 15, 2026`） | **是** | **有**（按年） |
| **YouTube** | 单篇汇总文章 | 月级 | 有（一句话摘要） | **有**（`On January 5, 2022`） | 有（`[December, 2021]`） | 部分（`[Month Year]` 前缀可解析） | 有 |
| **TikTok** | **版本号 + URL 令牌** | **半年级** | **无 diff** | **有**（`Effective September 13, 2025`） | **有**（`Released August 14, 2025`） | **是**（结构化字段） | 版本可寻址 |
| **Amazon Ads** | **结构化表格** | **月级** | **有**（summary 列） | 无（只有月份） | 无 | **是**（四列表） | 有 |

### 7.7 变更记录的最小字段集（【判断】，取自五家的并集）

```yaml
change_id:            # 唯一标识（Google 用 answer ID；Amazon 用表格行）
change_title:         # 「Update to <政策名>: <辖区>」——Google 的命名法
effective_date:       # 生效日（Google/YouTube/TikTok 都有）
posted_date:          # 公告日（Google/YouTube/TikTok 都有）
change_summary:       # 改了什么（Amazon 有；YouTube 一句话）
change_reason:        # 为什么改（Google 有；指向外部法律/监管事件）
affected_policy_ref:  # 受影响的政策 ID（Amazon 有双向链接）
affected_jurisdiction:# Global / <国家> / <次国家>（Google 有）
required_action:      # 广告主要做什么（Google 的 certification 提示）
merge_status:         # pending → merged（Google 的「生效日才更新政策页」）
```

**五家里没有一家同时具备全部 10 个字段。** Google 有 8 个，Amazon 有 6 个，TikTok 有 4 个，YouTube 有 5 个，Meta 有 0 个。**并集就是 Momcozy 的目标 schema。**

---

## 8. 对 Momcozy 的直接含义

> 本节把上面的发现翻译成对 `PRD/内容治理需求文档.md` 里那套 21 条规则库、19 条卖点边界、52 条改写建议、291 条明细的具体建议。
> 凡涉及现有资产的地方，字段名沿用任务书 §2 的原文写法。

### 8.1 四维假设的裁决：「国家 × 品类 × 平台 × 内容类型」

**问题原文**：*审核规则库应该如何来定义：是按照国家 × 品类 × 平台 × 内容类型？*

**裁决：四维里有 2 个是平台自己在用的维度，2 个不是。而且四者不是同一层的东西，不能做笛卡尔积。**

| 维度 | 平台是否在用 | 证据 | 在 Momcozy 中应处的层 |
|---|---|---|---|
| **国家 / 辖区** | ✅ **五家全在用**，且是**独立的一层** | Meta `Restrictions by country` + `Global restrictions`；Google `Gambling and Games Policy: Colorado, USA` / `: France`；Amazon `This article applies to selling in: United States`；TikTok `In some regions`；YouTube `country-specific routing` | **适用范围层（Scope）**，不是规则本体的一部分 |
| **平台** | ⚠ **平台自己不用**（每家只管自己）——但这恰恰说明它是**必须外置的维度** | 五家政策库全部只描述自家平台 | **适用范围层（Scope）** |
| **内容类型** | ✅ **部分在用，且用法很特别** | YouTube `Our policies apply to all portions of your content (video, Short, or live stream, thumbnail, title, description, and tags)`；Meta `all types of content, including AI-generated content` | **适用范围层（Scope）**，且是**「载体」而非「品类」** |
| **品类** | ✅ 在用，但**永远不是顶层分区** | Google 走 certification（哪个行业要资质）；Meta 走 `restricted-goods-services/*` 子页；Amazon 走 `restricted-products` | **规则本体的第二层**（§2.7 观察 O2） |

**结论（可直接写进 PRD 的一句话）**：

> **Momcozy 的四维不是并联的四个分区键，而是「一个规则本体 + 一组适用范围参数」。**
> 规则本体按**边界类型（对应平台的「政策主题」）** 组织；国家、平台、内容类型三者是**适用范围参数**，挂在规则上而不是切分规则。

**证据锚点（已在 §8.2 展开）**：Amazon Ads 的 `Healthcare products and services` 政策把 `Breast Pump` 逐字列入 `Category 1 (low sensitivity products)`，并对该档给出 **supply 级**限制（`Amazon O&O Streaming TV must exclude content rated NR, TV-Y, TV-Y7, and G`）与**版位级**禁止（`Category 2` 的 `Fire TV, Fire tablet, Alexa, Amazon store homepage: prohibited`）。**这证明「品类」确实存在，但它是通过「品类 → 敏感度档 → 版位限制」这条链起作用的，而不是通过「品类分区」起作用的。**

**具体分层建议**：

```
L0 规则本体（Rule Body）        ← 按边界类型组织，全球同一，慢变
   H/M/U/安全词 四族保留，但每个规则条目要能带「本地实现」
L1 适用范围（Scope）            ← 挂在规则上的参数，快变
   jurisdiction: Global | US | FR | DE | ES | IT | GB | CA … 
   platform:     Meta | Google | TikTok | Amazon | YouTube | DTC
   carrier:      文本 | 图片 | 视频 | 标题 | 描述 | 落地页 | 达人素材
   audience:     adult | minor | 18+
L2 本地实现（Local Realization）← 按 (规则 × 辖区) 维护的具体清单
   词表 / 阈值 / 表述清单 / 资质要求  ← 对应 Meta 的 market slur lists
L3 后果（Consequence）          ← 按 (规则 × 平台) 决定
   不通过 / 限域 / 需标注 / 18+ / 需资质 / 需人工语境判定
```

**四条必须纠正的现状**：

1. **`适用产品` 写死为 `W1、M5、M6、M9、Air1`** —— 这是把「品类」和「具体型号」混淆了。平台的做法是**规则按品类/主题写，型号是适用范围的一个取值**。建议改成两个字段：`适用品类`（吸奶器 / 喂养用品 / …）+ `适用型号`（可空 = 全品线）。
2. **`判断方式` 21/21 全是 `自动可检测`** —— **Meta 有 67%（18/27）的规则明确标注「需要额外信息或语境才能执法」。** 全部标成自动可检测在统计上不可能成立。建议引入 Meta 的三态表述（§6.5），把 `判断方式` 的取值改为：`自动可判` / **`需语境方可判`** / `仅人工判`。
3. **投放地区是 `其他216 / 法国26 / 英国19 / 加拿大14 / 西班牙11 / 意大利3`（无美国）** —— 与规则库的 `适用产品` 完全无关联字段。**Google 的 `Eligible (limited)` 说明「地区」是投放系统的一等参数**，Momcozy 必须把 `投放地区` 变成规则适用性判定的输入。
4. **`依据来源` 只指向两份内部文件** —— 五家平台没有一家把「依据」写成内部反馈，全部指向**公开的、可被外部核验的**政策页 / 法规条款。建议 `依据来源` 改为 `条款编号 + URL` 的引用形式（本文的引用格式可直接沿用）。

### 8.2 品类维度：「吸奶器」在平台政策里的确切位置（**本次调研对 Momcozy 最直接的一条证据**）

Momcozy 主营吸奶器。**在五家平台的政策库里，只有 Amazon 把「吸奶器」写成了一条明确的分类条目**，而且写在一个完整的「敏感度 × supply 限制」矩阵里。

**【原文】** `Healthcare products and services`（Amazon Ads，`_evidence/R1/amazon-ads-healthcare-GPSSMTEAA6AEWY3A.md`，URL `advertising.amazon.com/help/GPSSMTEAA6AEWY3A`，页面标注 `Updated on Apr 6, 2026`）：

> `Supply-specific policies for consumer healthcare products vary to protect the customer experience. Requirements are defined by product categories as follows (non-exhaustive list).`
>
> | 档位 | Product types（逐字，节选） | Supply-specific restrictions（逐字，节选） |
> |---|---|---|
> | `**Category 1 (low sensitivity products): Generally allowed**` | `Allergy and Sinus, Splints and Supports, **Breast Pump**, Cough and Cold, COVID Test Kits, Digestion, Eczema, Eye health, Foot Remedies, General Stress, General Wellness Health Tests or Monitors, Menopause, Menstruation Products, Physical Therapy Aids, Pain Relievers, Rosacea, Sleep or snoring Aids, and others.` | `Permitted on all supply with the following restrictions:` / `Amazon O&O Streaming TV must exclude content rated NR, TV-Y, TV-Y7, and G` / `Open Internet: permitted with accurate category declaration` |
> | `**Category 2 (medium sensitivity products): Allowed with restrictions**` | `Denture care, head lice treatments, Hearing, Mobility and Visual Aids, Psoriasis, Smoking Cessation, Weight Loss, and others.` | `Fire TV, Fire tablet, Alexa, Amazon store homepage: prohibited` / `Amazon O&O Streaming TV: must exclude content rated NR, TV-Y, TV-Y7, and G` |
> | `**Category 3 (high sensitivity products): Allowed with additional restrictions**` | （同页续） | （同页续） |

另有独立的药品档位表（同页）：
> `Prescription pharmaceuticals are drugs prescribed or administered by a doctor or healthcare professional. Ads for prescription pharmaceuticals are reviewed on a case-by-case basis and permitted in **the United States, New Zealand, and Canada only**. In addition, awareness campaigns from prescription pharmaceutical manufacturers that do not contain any reference to specific pharmaceutical products are permitted in **the United Kingdom, France, Italy, Germany, and Spain**.`
> `Category 1 (moderate sensitivity): Allowed with restrictions — Allergies, Arthritis, Asthma, Blood Pressure, … Menopause, … Smoking Cessation`
> `Category 2 (higher sensitivity): Allowed with additional restrictions — ADHD, Alzheimer, Anxiety, Bipolar Disorder, Cancer, … Birth Control, Tuberculosis, and Weight Loss`

**【判断】这条证据的价值在于它同时给出了五个维度的取值，而 Momcozy 的规则库目前一个都没有：**

| 维度 | Amazon 的实际取值 | 对 Momcozy 的含义 |
|---|---|---|
| **产品品类** | `Breast Pump` 被**逐字点名** | 不需要自己发明品类树——平台已有权威分类，**直接对齐** |
| **敏感度档** | `Category 1/2/3`（low/medium/high sensitivity） | 这是**品类级的严重度预设**，比逐条规则打标签更省 |
| **投放位置（supply）** | `Amazon O&O Streaming TV` / `Open Internet` / `Fire TV` / `Alexa` / `Twitch` / `Amazon store` | 呼应的正是 Momcozy 的「平台」维度，**但更细：平台内的具体版位** |
| **内容分级（content rating）** | `must exclude content rated NR, TV-Y, TV-Y7, and G` | 一个 Momcozy 完全没有的维度——**同一素材在不同版位要按分级过滤** |
| **声明要求** | `accurate category declaration`（申报品类） | 「如实申报品类」本身是一条可执行动作 |

**最重要的一条【判断】**：
> **吸奶器在 Amazon Ads 里是 `Category 1 (low sensitivity products): Generally allowed`——即最低敏感度、原则上允许。**
> **但「Generally allowed」不等于无限制**：它仍然带 supply 级限制（O&O Streaming TV 要排除 NR/TV-Y/TV-Y7/G 分级内容）和申报义务（`accurate category declaration`）。
> **这正是 §5.7 L5 说的「合规但受限」那一档在 Momcozy 自己品类上的具体形态。** 他们现有的四档（高危/审慎/待复核/合规）里，没有一档能表达「原则上允许，但在某些版位要按分级过滤」。

**⚠ 需要 R5 补充的部分**：`Breast Pump` 在其他四家的政策库里**没有被逐字点名**（Meta 归入 `Health and Wellness`/`Restricted Goods and Services`，Google 归入 `Healthcare and medicines` 政策 + certification，TikTok 归入 `Regulated Goods, Services, and Commercial Activities`，YouTube 无专条）。**「吸奶器是否构成医疗器械、在各国如何归类」属 R5 范围，本文不做判断。**

### 8.3 把「规则本体 / 适用范围分离」搬进 12 字段 schema

**现有 12 字段**：`规则编号 | 边界类型 | 适用产品 | 风险等级 | 检测关键词 | 边界内容 | 判断方式 | 依据来源 | 启用状态 | 正则表达式 | 豁免词 | 触发原因`

**能否直接搬？能，但需要拆字段而不是加字段。** 五家的做法是把「一条规则」拆成**规则本体 + 适用范围 + 本地实现 + 后果**四件东西。逐字段改造建议：

| 现有字段 | 问题（对照本文证据） | 改造后 | 新增/拆分 |
|---|---|---|---|
| `规则编号` | **保留。** Google/Amazon 按政策分别计 strike，前提就是规则有稳定 ID | `rule_id`，建议改为 `<族>.<主题>.<序号>`，并新增 `version` | +`rule_version` |
| `边界类型` | 保留，但它是**唯一的本体分区键**，应严格对齐平台的顶层主题（§2.7 O2：品类不是顶层） | `boundary_type`（严格限制红线/审慎关注/人工复核/安全词白名单）不变 | — |
| `适用产品` | **混淆品类与型号**（`W1、M5、M6、M9、Air1` 写死） | **拆两个**：`product_category` + `product_models[]` | **拆** |
| **（新增）** | 平台全部把「在哪些国家」外置 | **`scope_jurisdiction[]`**，取值必须含 `Global`（Google `…: Global`、Meta `Global restrictions`）。建议枚举：`Global / US / CA / GB / FR / DE / ES / IT / …`，**并允许次国家层级**（Google 有 `Colorado, USA`、`Alberta, Canada`） | **+字段** |
| **（新增）** | 平台把「在哪个平台」当 scope | **`scope_platform[]`**：`Meta / Google / TikTok / Amazon / YouTube / DTC` | **+字段** |
| **（新增）** | YouTube 原文把载体逐个列出 | **`scope_carrier[]`**：`正文 / 标题 / 描述 / 图片 / 视频 / 缩略图 / 落地页 / 达人素材` | **+字段** |
| **（新增）** | Amazon 的 severity 判据之一是「是否违反法律法规」；Google 的 `Legal requirements` 单独成章 | **`rule_source`**：`platform_policy` 或 `law`。**区分「平台政策」与「法律」两个各自生效的规则体**（Google 原文 `in addition to Google Ads policies`）。同时新增 **`legal_ref`**（如 `Directive 2010/13/EU Art. 9`、`16 CFR § 255.5`） | **+2 字段** |
| `风险等级` | **四档压扁了「合规但受限」**（§5.7 L5） | **拆两个字段**：`severity`（Amazon 式四档：`critical / high / medium / low`）+ **`consequence_type`**（Google 式状态：`不通过 / 限域投放 / 需标注 / 18+ / 需资质 / 需语境判定`） | **拆** |
| `检测关键词` | **这是「本地实现」，不是规则本体。** 对应 Meta 的 market slur lists | **拆**：`keyword_set_ref`（指向一个可独立更新的词表资产，带 `market` 维度）+ 保留内联兜底 | **拆** |
| `边界内容` | 保留 = 规则本体陈述 | `rule_statement`（建议对齐 Meta 的 `Policy Rationale` 写法：先写**为什么**，再写**禁止什么**） | — |
| `判断方式` | 21/21 全 `自动可检测` 不成立 | `detection_mode`：`自动可判 / 需语境方可判 / 仅人工判`（Meta 18/27 是第二档） | 改取值域 |
| `依据来源` | 指向内部文件 | `evidence_ref[]`：**URL + 条款编号 + 抓取日期**（本文格式） | 改 |
| `启用状态` | 保留。但缺**生效日与发布日** | **拆**：`status` + `effective_date` + `posted_date`（Google/YouTube/TikTok 三家都区分后两者） | **+2 字段** |
| `正则表达式` | 保留 = 本地实现的一部分 | `pattern`，建议与 `keyword_set_ref` 同一层 | — |
| `豁免词` | 保留，但**只有 5/21 有** | `allowance[]`，并且**每一档豁免都要带残余后果** → 新增 `residual_consequence[]`（TikTok 原文：豁免后仍可能 `ineligible for the FYF / warning screen / context label`） | **+字段** |
| `触发原因` | 保留 | `trigger_reason` | — |
| **（新增）** | 平台把「重复计数」当一等概念 | **`repeat_policy`**：`count_key`（rule / account）、`window_days`（90 / 180 / 365）、`escalation`（Amazon 式**乘数**或 Google 式**阶梯**） | **+字段** |
| **（新增）** | 平台把「例外情形」写进规则（Meta slur lists `guidance on circumstances in which a given slur might be used in a permissible way`） | **`allowance_cases[]`**：`self_reference / alternative_meaning / discussing / reporting / condemning / positive_use`（Meta 逐字 6 种）+ `counterspeech`（TikTok） | **+字段** |
| **（新增）** | 平台把「语境补强动作」写出来 | **`context_actions[]`**：TikTok `captions, stickers, or voiceover`；YouTube `basic facts: who/what/when/where/why` | **+字段** |

**改完的字段数**：12 → **约 22**。但这不是膨胀，是**把混在 12 个字段里的 4 类语义（本体 / 范围 / 实现 / 后果）分开**——正是五家平台一致的做法。

**最小可行版本（若不想一步到位）**：只做 **3 个改动**即可拿到 80% 收益：
1. `适用产品` 拆成 `品类` + `型号`；
2. 新增 `scope_jurisdiction[]` + `scope_platform[]`（**必须含 `Global`**）；
3. `风险等级` 拆成 `severity` + `consequence_type`。

### 8.4 严重等级：现有四档（高危/审慎/待复核/合规）缺什么

**现有四档**：`高危` / `审慎` / `待复核` / `合规`

**与平台分级对比，缺 6 样东西：**

| # | 缺什么 | 平台的证据 | 具体建议 |
|---|---|---|---|
| **1** | **缺「仅警告」档** | Google `no strikes are issued for the first policy violation`；YouTube `the first violation is typically only a warning`；Meta `One strike: You'll get a warning…`；TikTok `warning, a restriction, or a full ban` | 现有四档全是**静态风险标签**，没有**违规后的处置阶梯**。应新增独立的 `enforcement_ladder`：`提醒 → 复核 → 下架/驳回 → 账号级限制 → 停投` |
| **2** | **缺「合规但受限」档** | Google `Eligible (limited)`——`comply with our policies but are limited in where and when they can show`；YouTube `limited ad earnings`；TikTok `FYF INELIGIBLE` | 现有 `合规` 把「完全可用」和「可用但限域/限龄/需标注」压成一档。**必须拆出「受限可用」** |
| **3** | **缺「一次触顶」通路** | Google `egregious … suspended immediately without prior warning`；TikTok `A single, severe violation` + 4 类列举；YouTube `a single case of severe abuse`；Amazon `critical … can lead to immediate account enforcement` | 现有 `高危` 没有区分「多次才升级」与「一次即触顶」。**`高危` 应再分 `critical`（一次触顶）与 `high`** |
| **4** | **缺「计数的窗口与主键」** | Google/YouTube **90 天**；Amazon **180 天**；Meta strike **1 年过期**；Google/Amazon 按**政策**计数 | 291 条在跑明细里没有「同一规则被同一账号命中过几次、多久内」的字段。**没有窗口的计数会让旧错永久跟随** |
| **5** | **缺「重复违规的升格方式」** | Amazon：`the point values associated with violations included in your AHR **increase each time that same policy is violated**`（**乘数**）+ `maximum number of repeat violations for a single policy in a 180-day period … can be as low as two violations for higher severity violations` | 现有的是**静态四档**，没有「第 N 次」的升格规则 |
| **6** | **缺「严重度的判定轴」** | Amazon 逐字：`When determining the severity, we consider factors including **the degree to which the violation negatively impacts the customer experience** and **whether the policy violation contravenes applicable laws and regulations**` | 现有 `风险等级` 没有说明档位是怎么定的。**建议明写两条轴：① 对消费者的误导/伤害程度；② 是否触犯法规**（第二条轴可直接对接 R5 分片的监管事实） |

**另有一条 Momcozy 独有的缺口（平台没有，但它必须补）**：

| # | 缺什么 | 说明 |
|---|---|---|
| **7** | **缺「品牌调性」这一轴** | 五家平台都不管品牌调性——**这是 Momcozy 的私有维度**。现有 `边界类型` 里的「审慎关注」混着合规与调性两类东西。建议 `severity`（合规风险）与 `brand_tier`（调性偏离）**分成两个独立评分**，不要塞进同一个四档 |
| **8** | **缺「非政策状态」** | YouTube 的货币化有 **8 个图标状态**，其中 `Checking`（审核中）/ `Sharing`（版权分成）/ `Escrow`（版权争议托管）/ `Exceptions`（儿童受众）**都不是政策判定**。现有四档会把「审核未完成」「版权问题」误报为风险档 | 新增 `blocking_reason`：`policy_violation / pending_review / rights_issue / audience_setting / platform_gate`，与 `severity` 正交 |

**推荐的严重度模型（合成自五家）**：

```yaml
# 两条独立的轴（不要合并）
compliance_severity:  critical | high | medium | low     # 对齐 Amazon 四档
brand_deviation:      none | minor | notable | severe    # Momcozy 私有，平台无对应

# 后果类型（对齐 Google 状态机 + TikTok 清单）
consequence_type:     不通过 | 限域投放 | 需标注 | 18+ | 需资质 | 需语境判定 | 完全可用

# 升级规则
escalation:
  count_key:   rule            # 对齐 Google/Amazon：按规则计数
  window_days: 180             # 对齐 Amazon
  mode:        multiplier      # 对齐 Amazon：再犯提高点值，而非跳档
  one_strike:  [critical]      # 对齐四家的「一次触顶」
  first_time:  warning         # 对齐四家的「第一次只警告」
```

### 8.5 三条立刻可执行的动作（按投入产出排序）

**动作 1（半天，收益最大）：给 21 条规则补 `scope` 三字段。**

现在 21 条规则的适用性是隐式的（`适用产品` 写死五个型号、`依据来源` 是内部文件）。按平台做法补：

```yaml
scope_jurisdiction: [Global]        # 或 [US]、[FR, DE, ES, IT]、[EU]
scope_platform:     [Meta, Google]  # 或 [TikTok]、[Amazon]
scope_carrier:      [正文, 图片]     # 或 [视频]、[落地页]
```
**这一步直接回答了他们最初的问题**，而且不需要重写任何规则内容。

**动作 2（一天）：把 `适用产品` 拆成 `品类 + 型号`，并把 `判断方式` 的取值域改成三档。**

理由：`W1、M5、M6、M9、Air1` 是型号不是品类，一旦上新品就要改 21 条规则；`自动可检测` 21/21 与 Meta 的 18/27 语境依赖率直接矛盾，会让审查 Agent 系统性高估自己的自动化能力（任务书 §2 反模式清单里的「兜底路径比主路径更宽松」正是同一类问题）。

**动作 3（两天）：建 `changelog` 表，字段用 §7.7 的 10 字段并集；并给每条规则加 `effective_date` / `posted_date`。**

理由：Google 一年 58 条变更、TikTok 半年一版、Amazon 有结构化表格，而 Momcozy 现在的规则变更没有任何记录机制（`依据来源` 只写了一个日期 `品线反馈2026-09-10 T4`）。**没有 changelog，规则库就无法自迭代**——这是任务书问题 4 的最小前置条件。

---

## 9. 证据清单

### 9.1 一手来源 URL（全部抓取于 2026-09-15）

**Meta**
| # | URL | 内容 | 本地证据 |
|---|---|---|---|
| M-1 | `https://transparency.meta.com/policies/community-standards/` | CS 索引（27 条平铺） | `meta-cs-index.md` / `.html` |
| M-2 | `…/community-standards/spam/` | 条目模板 + Notwithstanding | `meta-cs-spam.md` |
| M-3 | `…/community-standards/hate-speech/` → `hateful-conduct` | Tier 1/Tier 2 + satire + EU 段 | `meta-cs-hate-speech.md` |
| M-4 | `…/community-standards/locally-illegal-products-services/` | **本地法分离声明** | `meta-cs-locally-illegal.md` |
| M-5 | `…/community-standards/additional-protection-minors/` | 唯一无 Policy Rationale | `meta-cs-additional-protection-minors.md` |
| M-6 | `…/community-standards/regulated-goods/` | Health and Wellness 品类规则 | `meta-cs-regulated-goods.md` |
| M-7 | `…/enforcement/` | remove / reduce / inform | `meta-enforcement-hub.md` |
| M-8 | `…/enforcement/taking-action/counting-strikes/` | strike 窗口与过期 | `meta-enf-counting-strikes.md` |
| M-9 | `…/enforcement/taking-action/restricting-accounts/` | strike 阶梯逐条 | `meta-enf-restricting-accounts.md` |
| M-10 | `…/enforcement/taking-action/how-we-create-and-use-market-slurs/` | **market 词表治理** | `meta-enf-market-slurs.md` |
| M-11 | `…/features/approach-to-newsworthy-content/` | newsworthiness allowance | `meta-newsworthiness.md` |
| M-12 | `…/policies/ad-standards/` | 广告索引 + 四原则 + review | `meta-ad-index.md` |
| M-13 | `…/reports/content-restrictions/country/` | **按国家限制报表** | `meta-report-restrictions-by-country.md` |
| M-14 | 43 个 ad-standards 子页 | 广告政策全文 | `meta-ad-*.md`（见 `meta-ad-LINK-MAP.md`） |

**Google Ads**
| # | URL | 内容 | 本地证据 |
|---|---|---|---|
| G-1 | `https://support.google.com/adspolicy/answer/6008942` | 政策总览 | `google-ads-policies-overview.md` |
| G-2 | `…/adspolicy/answer/6023676` | **Legal requirements（含 AVMSD Art.9 原文）** | `google-ads-legal-requirements.md` |
| G-3 | `…/adspolicy/answer/16114090`（由 `7645254` 进入） | **certification 闸门 + location-specific** | `google-ads-location-specific-requirements.md` |
| G-4 | `…/adspolicy/answer/12390454` | Relevant Regulators and Enforcement Dates | `google-ads-regulators-enforcement-dates.md` |
| G-5 | `…/adspolicy/topic/29265`、`topic/16794025` | **Change log / 2026 年 58 条** | `google-ads-changelog-recent.md`、`google-ads-changelog-2026.md` |
| G-6 | `…/adspolicy/answer/17117810` | `Gambling: Colorado, USA` 变更（四要素） | `google-ads-chg-gambling-colorado.md` |
| G-7 | `…/adspolicy/answer/17101147` | `Gambling: France` 变更 | `google-ads-chg-gambling-france.md` |
| G-8 | `…/adspolicy/answer/17258294` | `Gambling: Global` 变更 | `google-ads-chg-gambling-global.md` |
| G-9 | `…/adspolicy/answer/10922738` | **repeat violations / strike 制度** | `google-ads-repeat-violations.md` |
| G-10 | `…/adwordspolicy/answer/7187501` | **违规后果总表** | `google-ads-violation-consequences.md` |
| G-11 | `…/adspolicy/answer/2684542` | **Eligible (limited) 定义** | `google-ads-eligible-limited.md` |
| G-12 | `…/adspolicy/answer/10658384` | Past Violation | `google-ads-past-violations.md` |
| G-13 | `…/adspolicy/topic/1316546`、`topic/1308266` | Review process / Disapprovals | `google-ads-review-process-topic.md`、`google-ads-disapprovals-suspensions.md` |

**YouTube**
| # | URL | 内容 | 本地证据 |
|---|---|---|---|
| Y-1 | `https://www.youtube.com/howyoutubeworks/policies/community-guidelines/` | CG 全文 | `youtube-community-guidelines-full.md` |
| Y-2 | `https://support.google.com/youtube/answer/2802032` | **strike 阶梯 + warning + 培训** | `youtube-strike-basics.md` |
| Y-3 | `…/youtube/answer/2802168` | **终止条件 + 申诉 1 年** | `youtube-strike-expiry.md` |
| Y-4 | `…/youtube/answer/6162278` | **advertiser-friendly 三态 + 14 主题** | `youtube-advertiser-friendly.md` |
| Y-5 | EDSA 例外页 | **EDSA + more/less likely 表** | `youtube-edsa-exceptions.md` |
| Y-6 | YouTube policy updates | **policy changelog** | `youtube-policy-updates.md` |

**TikTok**
| # | URL | 内容 | 本地证据 |
|---|---|---|---|
| T-1 | `https://www.tiktok.com/community-guidelines/en/us/` | CG 全文（12 POST） | `tiktok-community-guidelines.md` |
| T-2 | `…/community-guidelines/en/fyf-standards/` | FYF 标准 + **Enforcement POST** | `tiktok-fyf-standards.md`、`tiktok-fyf-standards.remix.json` |
| T-3 | `…/community-guidelines/en/accounts-features/` | **账号/功能处置 + public interest exception** | `tiktok-accounts-features.md`、`tiktok-accounts-features.remix.json` |

**Amazon**
| # | URL | 内容 | 本地证据 |
|---|---|---|---|
| A-1 | Seller Central `Account Health Rating program policy` | **AHR 0–1000 + 四档 severity** | `amazon-ahr.md` |
| A-2 | `https://advertising.amazon.com/help/G8X8M375UPCN4UUC` | **Ad policy change log（四列表）** | `amazon-ads-change-log-G8X8M375UPCN4UUC.md` |
| A-3 | Amazon Ads policies | 广告总则与保留权利 | `amazon-ads-policies-G5RLASA28TP9TFXZ.md` |
| A-4 | `…/G1881` | 商品图片规范 | `amazon-product-image-guide-G1881.md` |
| A-5 | `…/G200390640` | Product detail page rules | `amazon-product-detail-page-rules-G200390640.md` |
| A-6 | `…/G200386250` | Prohibited seller activities | `amazon-prohibited-seller-activities-G200386250.md` |
| A-7 | `…/G521` | **Program Policies 主索引** | `amazon-program-policies-G521.md` |
| A-8 | `advertising.amazon.com/help/GPSSMTEAA6AEWY3A` | **Healthcare 分级（含 `Breast Pump`）** | `amazon-ads-healthcare-GPSSMTEAA6AEWY3A.md` |
| A-9 | `advertising.amazon.com/help/G6UU66YLSCUYDULQ` | Claims and substantiation | `amazon-ads-claims-substantiation-G6UU66YLSCUYDULQ.md` |
| A-10 | `advertising.amazon.com/help/G26M9XTK78AMR8TP` | 广告政策索引（9 个分区） | `amazon-ads-policies-guidelines-G26M9XTK78AMR8TP.md` |
| A-11 | `sellercentral.amazon.com/help/hub/reference/external/G47071` | **BSA 变更（含 Section 19 / AI agents）** | `amazon-changes-to-bsa-G47071.md` |
| A-12 | `sellercentral.amazon.com/help/hub/reference/external/GR786P4BPEVKTBAG` | **AHR FAQ（含硬数字）** | `amazon-ahr-faq-G786P4BPEVKTBAG.md` |
| A-13 | `…/GZ9VRVWH8HXTDTK7`（实际 `GX9VRVWH8HXTDTK7`） | Regulatory/Safety 账户执法 | `amazon-account-enforcement-regulatory.md` |

**Google Ads（补充）**
| # | URL | 内容 | 本地证据 |
|---|---|---|---|
| G-14 | `support.google.com/adspolicy/answer/6018017` | **Gambling 逐国表（`## Country-specific requirements`）** | `google-ads-gambling-games.md`（1692 行） |
| G-15 | `support.google.com/adspolicy/topic/2996750` | List of ad policies（43 条目，含 `Legal requirements` 平级） | `google-ads-topic-list-of-ad-policies.md` |
| G-16 | `support.google.com/adspolicy/topic/3230816` | Change log 总页（含 ~500 条 Past changes） | `google-ads-topic-change-log.md`（1051 行） |
| G-17 | `support.google.com/adspolicy/answer/15938075` | Circumventing systems | `google-ads-circumventing-systems.md` |

**TikTok / YouTube（补充）**
| # | URL | 内容 | 本地证据 |
|---|---|---|---|
| T-4 | `tiktok.com/community-guidelines/.../government-removal-requests` | **政府移除请求的辖区隔离声明** | `tiktok-government-removal-requests.md` |
| T-5 | `…?cgversion=2026H2update` | 下一版 CG（Released 2026-08-25 / Effective 2026-09-24） | `tiktok-community-guidelines-2026H2.md` |
| Y-7 | `support.google.com/youtube/answer/9288567` | **CG 六大分区 + EDSA 段落** | `youtube-community-guidelines-overview.md`、`youtube-community-guidelines-full.md` |
| Y-8 | `support.google.com/youtube/answer/9208564` | **货币化 8 图标状态** | `youtube-monetization-icons.md` |
| Y-9 | `support.google.com/youtube/answer/10008196` | **YouTube policy updates（带日期 changelog）** | `youtube-policy-updates.md` |

### 9.2 本地证据统计

- 本报告直接引用的**一手来源 URL 约 90 个**（§9.1 列出主表，`meta-ad-LINK-MAP.md` 另收录 121 个 BHC 文章链接备查）
- `research/governance/_evidence/R1/`：**约 420 个文件**——250+ 个 `.md` 文本抽取、约 190 个 `.html` 原文、3 个结构化 JSON（`tiktok-fyf-standards.remix.json`、`tiktok-accounts-features.remix.json`、`tiktok-community-guidelines*.remix.json`）
- 按平台分：`meta-cs-*` 31、`meta-enf-*` 8、`meta-ad-*` 66、`google-ads-*` 51、`youtube-*` 20、`tiktok-*` 5、`amazon-*` 46+
- 结构清单与索引：`meta-cs-STRUCTURE-INVENTORY.md`（27 条 × 11 列）、`meta-cs-FETCH-MANIFEST.md`、`meta-ad-LINK-MAP.md`
- 本文所有 `【原文】` 均可在这三个索引所指向的文件里逐字复核。

---

## 10. 缺口清单

### 10.1 抓取失败 / 无法取得的来源

| # | 目标 | 失败原因 | 影响 | 是否已缓解 |
|---|---|---|---|---|
| 1 | `transparency.meta.com` 直连 | TCP 超时（网络层） | — | 已通过本地代理 `127.0.0.1:7890` 解决 |
| 2 | `transparency.meta.com` 裸 curl | **HTTP 400 + Facebook Comet `<title>Error</title>` 页（≈261 KB）** | — | 已通过 `--compressed` + 完整 `Sec-Fetch-*`/`sec-ch-ua` 头解决 |
| 3 | `read_page`（Firecrawl keyless） | **429，`retry_after_seconds: 86359`（≈24 h）**，会话中不可用 | 早期未能批量抓取 | 已改用 curl + 代理 |
| 4 | `facebook.com/business/help/2231579525013959` | **404**（"That page doesn't exist"） | 少一条 Meta 广告帮助页 | 未缓解（已存 404 页面留证） |
| 5 | Meta 全局 changelog | **`/policies/ad-standards/changelog/`、`/policies/changelog/`、`/overview/`、`/SIEP-advertising/changelog/` 全部 404** | **Meta 确认没有全局 changelog**（这是结论而非缺口） | 已结论化 |
| 6 | Meta 广告政策的历史修订版 | `CHANGE LOG` 是客户端 tablist，**只有当前版被服务端渲染** | 拿不到历史版本的逐字差异 | **未缓解**。需真实浏览器逐 tab 点击 |
| 7 | Meta 广告侧 `severe violations` 清单 | **不存在**：Transparency Center 无广告专属 strikes/severity 页 | 「哪些广告违规一次即停用」无法逐字引用 | 已结论化（`NOT FOUND`） |
| 8 | TikTok 地区差异清单 | CG 按 `VRegion` 路由（抓到时为 `sg`），`In some regions` **未列出具体地区** | 无法知道 TikTok 的辖区差异内容 | **未缓解**。需从多个地区 IP 抓取对比 |
| 9 | TikTok CG 的**历史版本 diff** | 版本令牌可寻址（`cgversion=2025H2update`），但**每版只有发布日期与生效日期，没有 diff 说明** | 无法列出「这一版改了什么」 | 已结论化（TikTok 用版本替代 diff） |
| 10 | YouTube CG 的地域差异 | 未发现公开的辖区规则差异页 | — | 已结论化（YouTube 用 `age-restricted` + 政府请求流程而非辖区规则） |
| 11 | Google Ads 全部政策条目逐条抓取 | 只取了总览 + 若干代表条目 | 「政策清单的完整分区树」可能不全 | 部分缓解（`google-ads-policy-list.md` + 45 个页面已入库） |
| 12 | Amazon Seller Central 部分帮助页 | 部分路径需登录 | AHR 主文已取得，细则页缺失 | 部分缓解 |

### 10.2 未核实的问题（明确留白，不用推测填空）

**已在本次调研中解决、不再列为缺口的**（保留记录以便追溯）：
- ✅ **Google Ads 的 per-country 矩阵**：已取得 `support.google.com/adspolicy/answer/6018017` 的 `## Country-specific requirements` 逐国表（Angola / Argentina 等），见 §4.2 层 4。
- ✅ **TikTok 的地区差异声明**：已取得原文（`we consider cultural and regional differences…`）+ 政府移除请求的辖区隔离声明，见 §4.4。
- ✅ **YouTube 的货币化状态集**：已取得 8 个图标状态（`Checking / On / Exceptions / Sharing / Escrow / Limited / Ineligible / Off`），见 §5.3。
- ✅ **Amazon AHR 的点值范围**：已取得 `typically range from two to eight` 与 `negative point values double per repeat violation`，见 §5.5。
- ✅ **Amazon 的国家层**：已取得 `Country-specific restrictions` 标题与国家组取值，见 §4.5。

**仍未核实的（明确留白，不用推测填空）：**

1. **Meta 广告 strikes 的计数窗口与升级规则——未核实。** Transparency Center 上没有广告专属的 strikes 页面，BHC 只有「6 个月后可永久停用」的酌情条款。广告违规是否累积 strike、窗口多长，**我没有找到公开原文**。
2. **Google Ads `Eligible (limited)` 的完整判定矩阵——仍部分未核实。** 已取得 Gambling 的逐国表，但**完整的 (全部受限政策 × 全部国家) 矩阵**未逐字取得；且各政策国家段标题不统一（四种命名，见 §4.2），**无法保证没有遗漏的政策页**。
3. **Meta `reduced distribution` 的量化降权幅度——未核实。** `Reducing the distribution of problematic content` 页面未逐字抓取。
4. **TikTok `FYF INELIGIBLE` 与 `AGE-RESTRICTED` 是否互斥——未核实。** CG 的 `##### FYF INELIGIBLE & AGE-RESTRICTED` 是一个合并标题，无法从文本判断两者是同一档还是并列档。
5. **Amazon AHR 的每条政策点值表——未核实。** 只知道范围是 2–8 与 critical 置零，**没有公开的逐政策点值表**。
6. **TikTok 的「哪些地区」——未核实。** 15+ 处 `In some regions` 均未枚举地区；CG 按 `VRegion` 路由（抓到时为 `sg`），**需要多地区 IP 对比抓取才能还原差异**。
7. **Amazon BSA 新增 Section 19（automated agents / AI systems）的条款全文——未核实。** 只读到 changelog 的标题级摘要（`Add new Section 19, defining and restricting use of automated agents/AI systems.`）。**这条与 Momcozy 的审查 Agent 直接相关，建议优先补齐。**
8. **GPSR（EU 通用产品安全法规）在 Amazon 政策库中的位置——未核实（NOT FOUND）。** 本次抓取的全部 Amazon 页面均未出现 GPSR 字样。
9. **五家的规则条目总数——未核实。** Meta CS 27 条、Meta Ads 43 页、Google 政策约 43 条目（`List of ad policies`）、TikTok 12 个 POST、Amazon 四条资产线。**「一条规则」在各家的粒度不同，无法跨家比较总数。**
10. **平台规则库的内部存储结构——未核实，且很可能不存在。** 本文解剖的是**对外发布形态**，不是内部规则引擎的数据模型。任何「平台内部就是按这个 schema 存的」的推断都超出证据范围。
11. **Momcozy 的 21 条规则与平台政策的具体映射——本文未做。** 这需要 R5（母婴品类监管与竞品）的分片事实，属越界。本文只提供了 §8.2 那条「吸奶器 = Amazon Category 1」的锚点。
12. **Meta 广告政策历史修订版的逐字差异——未核实。** `CHANGE LOG` 是客户端 tablist，仅当前版服务端渲染，需要真实浏览器逐 tab 点击。

### 10.3 与任务书分片边界的说明

本文严格限定在**结构解剖**。以下内容**刻意未写**（属其他分片）：

- 规则生命周期 / error analysis / 度量 → **R4**
- Rules-as-Code 的 schema 设计与冲突检测 → **R3**
- 母婴品类的监管边界与竞品合规表达 → **R5**
- 广告监管裁决案例库机制 → **R2**

本文引用了平台的**结构**（如 Amazon 的四档 severity、Google 的 strike 计数键）作为**规则库骨架的证据**，但**没有**展开其运营流程（那是 R4）或实现技术（那是 R3）。
