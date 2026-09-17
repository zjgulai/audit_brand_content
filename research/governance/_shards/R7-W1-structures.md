# R7-W1 真实系统规则库结构横剖

> 本部分只做**结构**调研：切轴方式、单条规则的内部字段、作用域表达位置、兜底类目、后果档数、版本机制。
> **不做**规则内容分析、不做规则引擎实现（R3）、不做裁决制度（R2）、不做面向客户的最终报告。
> 生成日期：2026-09-15　工作目录：`/Users/lute/Project/audit_multi_content`

## 0. 本部分结论

**七条结论。** 每条一句话，后附证据指向（`§x.y` = 本文件对应小节）。本部分共横剖 **13 个系统**：GitHub / Mozilla AMO / PyPI-PSF / npm / AWS / Stripe / eBay / Meta / Google Ads / Amazon / Adyen / TikTok / YouTube。

1. **没有两个系统切同一条轴。** 13 个系统的主切轴分别是：文档法律性质（GitHub §1.1.1）、扩展生命周期（AMO §1.2.1）、行为主题（PyPI §1.3.1、Meta §1.8.1、TikTok §1.12.1、YouTube §1.13.1）、政策文件（npm §1.4.1）、产品/服务（AWS §1.5.1，110 章）、准入资格档（Stripe §1.6.1）、卖家义务域（eBay §1.7.1）、栏目职能（Google §1.9.1）、经营流程环节（Amazon §1.10.1）、可配置规则构件（Adyen §1.11.1）—— **"内容治理规则库"不存在行业统一的分类骨架，切轴选择由平台自身的规制对象决定。**

2. **规则级元数据在 13 个系统中几乎全部为零，元数据一律挂在文档级。** GitHub AUP 的 bullet 无 ID/无等级/无平台字段，全部元数据在 YAML front-matter（§1.1.2）；PyPI、npm、Meta 的规则单元同样零字段；**唯一例外是 AWS——它的十进制条款号（如 `8.3.2`）被正文反复当作引用 ID 使用（§1.5.2），以及 Google 的 `criterion ID` 与 `answer ID`（§1.9.1、§1.9.3）。**

3. **作用域几乎从不出现在规则内部，而由"文档分区"承载——共观测到 7 种载体。** 文档字段（GitHub `versions: fpt` §1.1.3）、章号（AWS §1.5.3a）、页顶横幅（Amazon `This article applies to selling in: United States` §1.10.3a）、URL 路径（TikTok `/en/us/` §1.12.3a）、独立 section（Meta `Locally Illegal...` §1.8.3）、独立文章（Google OFAC 篇 §1.9.3a）、括注白名单（Stripe `Supported in ... Prohibited in all other countries` §1.6.3a）。**"作用域"是文档结构的属性，不是规则的属性。**

4. **"国家 × 品类"的二维结构只存在于商业平台，且只有 2 个系统给出了可逐项比对的样本。** Stripe 用 12 个国家节 + 逐项 P/R 标签（`Domestic charter air travel` 在 5 国分属 P / R / 未列，§1.6.2），Google 用 6 个带数字 `criterion ID` 的法域条目（§1.9.3a）；**而 GitHub、PyPI、npm、AMO 全部只说"你负责遵守一切适用法律"，不设国家维度（§1.1.3、§1.3.3、§1.4.3）。**

5. **"兜底"有四种互不兼容的哲学，且没有任何两个相邻系统采用同一种。** 显式抓漏条（GitHub AUP 第 11 节 §1.1.4）、枚举尾兜底（`and other limitations`，GitHub/PyPI）、非穷尽声明（`not an exhaustive list`，Stripe §1.6.4、YouTube `This list isn't complete.` §1.13.2、TikTok §1.12.2）、主观全权裁量（npm `they deem unacceptable` §1.4.4）、声明未列举即自由（AMO `developers are free to maintain their add-ons in the manner they choose` §1.2.4、npm 的许可条件结构 §1.4.4）。**其中 Amazon 是唯一取消兜底"默认允许"含义的系统：`Do not assume that a product is permitted because it is not listed`（§1.10.2b）。**

6. **后果档数从 2 到 10+ 跨两个数量级，且分档维度彼此无关。** AMO = 3 类**作用对象**（单版本/整扩展/开发者账号，§1.2.5b）、AWS = 4 段**程序阶段 + 时限**（§1.5.5）、Stripe = 2 档**尽调门槛**（§1.6.5）、Google = 逐政策配额 `1 警告 + 3 strike`（3/7 天/封号，§1.9.5）、Meta = 账号级累计 6 档（1/2-6/7/8/9/10+ 次，§1.8.5c）、YouTube = 同一 90 天窗口内 3 次 strike（7/14 天/频道移除，§1.13.5）。**"同样违规 N 次"在 Meta / Google / YouTube 会导致完全不同的后果——这是本报告对跨平台合规最直接可操作的结构发现（§1.13.5 对照表）。**

7. **版本机制与"规则库的存储方式"强相关，与平台规模无关。** 文本存于 git 的四个系统里，npm 直接把读者导向 `.mdx` 源文件与 git 历史（`Please refer to the git history for this document`，§1.4.6），PyPI 底层同样在 git 却只暴露一个 `Superseded` 横幅与日期（§1.3.6）；TikTok 用 URL 查询参数承载版本（`?cgversion=2025H2update`，且把**未来**生效日写进 `lastUpdate` 字段，§1.12.6）；Meta 有全站强制的 `CHANGE LOG` 字段但逐条**只有日期无说明**（§1.8.6）；**AWS AUP 与 GitHub AUP 都属于最薄一档——就地覆盖、无通知期、无历史版本（§1.1.6、§1.5.6）。**

**两条附带的、对本次调研方法论有直接影响的发现**（不占结论编号）：

- **规则库之间存在真实的 fork 与引用谱系，不是彼此独立的样本。** PyPI AUP 在正文里声明 `This policy is based on GitHub's Acceptable Use Policies and modified from its original form.`（CC-BY-4.0，§1.3.6），且与 GitHub 逐句共享骨架（含 `In short, be excellent to each other.`，§1.3.2）；npm 的名称与商标治理**整体引用 GitHub 政策库**（`npm follows GitHub's Username Policy`，§1.4.3e）。**同源文本对同一问题可以给出相反规则：`dual-use purpose` 在 GitHub 是免责要件，在 PyPI 是入罪要件（§1.3.3d）。**
- **同一公司内部可以并行两套版本机制。** Google Ads 有 `Change log` 一级栏目并按时态二分（`Upcoming and recent changes` / `Past changes`，§1.9.6），而本批 YouTube 证据三份文件中未出现任何变更记录（§1.13.6）。


## 1. 逐系统剖析

### 1.1 GitHub

GitHub 的站点政策（Site Policy）是一个**多文档、多轴的文档族**，而不是一棵单一分类树。它至少叠了四层切轴：文档类型轴（Terms / AUP / Privacy / Other / Content Removal / Security）、行为主题轴（AUP 的 1–11 节）、**单主题独立子页轴**（AUP 下挂 13 个独立 URL 的子政策）、以及产品/合同轴（Corporate ToS、Additional Product Terms）。

#### 1.1.1 切了什么轴

**主轴 = 文档类型（policy family），次轴 = 行为主题，第三轴 = 单主题拆页。**

站点政策索引把全部政策分成 6 个 flat 分组：

【原文】`GitHub Terms` / `Acceptable Use Policies` / `Privacy Policies` / `Other Site Policies` / `Content Removal Policies` / `Security Policies`
来源：`R7/github-site-policy-index.txt` → https://docs.github.com/en/site-policy

【判断】这是**按文档法律性质切轴**，不是按内容危害类型切轴。同一个危害（例如「隐私侵害」）会同时出现在 Privacy Policies（General Privacy Statement）、AUP 正文第 3 节、AUP 子页 `github-doxxing-and-invasion-of-privacy`、以及 Content Removal Policies（Private Information Removal Policy）里 —— **同一主题在多轴下重复登记**。指向：`R7/github-site-policy-index.txt` 全量分组清单。

AUP 正文自身是 11 个编号主题节（主题轴）：

【原文】
```
## 1. Compliance with Laws and Regulations
## 2. User Safety
## 3. Intellectual Property, Authenticity, and Private Information
## 4. Spam and Inauthentic Activity on GitHub
## 5. Site Access and Safety
## 6. Services Usage Limits
## 7. Information Usage Restrictions
## 8. Privacy
## 9. Excessive Bandwidth Use
## 10. Advertising on GitHub
## 11. User Protection
```
来源：`R7/github-docs-aup-src.md` → https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【判断】11 节**不是按严重程度排序的**：第 1 节是总则性「守法」，第 9 节「过度带宽」和第 10 节「广告」在危害谱系上明显轻于第 2 节「用户安全」，却排在其后。这是**按主题域聚集 + 把操作类限制放尾部**的编排，严重度不体现在位置。指向：同上标题清单。

第三轴：AUP 的 13 个子主题被拆成独立 URL 的独立政策页，形成 AUP 的「分册」：

【原文】
```
[Active Malware or Exploits](/en/site-policy/acceptable-use-policies/github-active-malware-or-exploits)
[Bullying and Harassment](...)
[Disrupting the Experience of Other Users](...)
[Doxxing and Invasion of Privacy](...)
[Hate Speech and Discrimination](...)
[Impersonation](...)
[Disinformation Policy](...)
[Sexually Obscene Content](...)
[Threats of Violence and Gratuitously Violent Content](...)
[Terrorism and Violent Extremism Content](...)
[CSAM Policy](...)
[NCII](...)
[Synthetic Media and AI Tools](...)
[GitHub Appeal and Reinstatement](...)
```
来源：`R7/github-site-policy-index.txt` → https://docs.github.com/en/site-policy

【判断】AUP 正文里的小节标题与子页标题**不同名**：正文第 2 节用词是 "sexually obscene"、"discriminatory or abusive"、"false, inaccurate, or intentionally deceptive information"、"harasses or abuses"，子页标题分别是 "Sexually Obscene Content"、"Hate Speech and Discrimination"、"Disinformation Policy"、"Bullying and Harassment"。**同一规则在正文与分册里有两套命名（一个描述行为、一个命名类目）**。指向：`R7/github-docs-aup-src.md` 第 2 节 vs `R7/github-site-policy-index.txt` AUP 分组。

#### 1.1.2 一条规则的内部结构

GitHub 没有「规则表」，**单条规则 = 文档内一个 bullet 或一个编号节**。规则的最小单位是**无编号的 bullet 项**，不携带任何结构化元数据（无 ID、无等级、无适用平台字段）。

【原文】`* is [sexually obscene](/site-policy/acceptable-use-policies/github-sexually-obscene-content) or relates to sexual exploitation or abuse, including of minors;`
来源：`R7/github-docs-aup-src.md`（第 2 节 User Safety 第 2 个 bullet）→ https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【判断】bullet 的**唯一内部结构**是：`否定式主句（"is/are X"） + 可选的行内链接（指向分册子页） + 可选的分号分隔从句`。没有任何字段承载等级、法域、平台。指向：同上。

**真正携带元数据的层在文件级，而不是规则级。** GitHub 官方文档源 Markdown 的 YAML front-matter 有 4 个字段：

【原文】
```yaml
---
title: GitHub Acceptable Use Policies
redirect_from:
  - /articles/github-acceptable-use-policies
  - /github/site-policy/github-acceptable-use-policies
versions:
  fpt: '*'
category:
  - Follow acceptable use policies
---
```
来源：`R7/github-docs-aup-src.md` 第 1–12 行 → https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

对照另一份（Community Guidelines）：

【原文】
```yaml
---
title: GitHub Community Guidelines
redirect_from:
  - /community-guidelines
  - /articles/github-community-guidelines
  - /github/site-policy/github-community-guidelines
  - /github/site-policy/acceptable-use-policies/github-community-guidelines
versions:
  fpt: '*'
category:
  - Review product and program terms
---
```
来源：`R7/github-docs-cg-src.md` 第 1–12 行 → https://docs.github.com/en/site-policy/github-terms/github-community-guidelines

【判断】四个字段各自的角色：
- `title` = 规则库条目的人类名（不保证与 URL slug 同名）。
- `redirect_from` = **规则库的迁移历史表**，是 4 个系统中唯一显式把 URL 沿革写进文档本身的机制。
- `versions: fpt: '*'` = 作用域字段（见 1.1.3），AUP / CG / ToS 三份**全部**是 `fpt: '*'`。
- `category` = 规则库的**一级归类**，值是一个字符串数组；AUP 归入 `Follow acceptable use policies`，CG 与 ToS 归入 `Review product and program terms`。注意 AUP 的 category 是「follow（遵守）」，而 CG/ToS 是「review（审阅）」—— **category 描述的是读者动作，不是内容主题**。

指向：`R7/github-docs-aup-src.md`、`R7/github-docs-cg-src.md`、`R7/github-docs-tos-src.md` 的 front-matter。

**文档级还有第二类内部结构：`Short version` 摘要块**（自然语言，非结构化的「摘要/正文」双段式）：

【原文】`**Short version:** _We host a wide variety of collaborative projects from all over the world, and that collaboration only works when our users are able to work together in good faith. While using the Service, you must comply with our Acceptable Use Policies, which include some restrictions on content and conduct on GitHub related to user safety, intellectual property, privacy, authenticity, and other limitations. In short, be excellent to each other._`
来源：`R7/github-docs-aup-src.md` 第 15 行 → https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【判断】这段 "Short version" 实质上承担了**规则库的类目枚举职责**：它把 AUP 归纳为 5 个域 —— `user safety, intellectual property, privacy, authenticity, and other limitations`。其中 `and other limitations` 是 GitHub 唯一一处显式的开闭枚举兜底措辞。指向：同上。

ToS 另有一张**结构化目录表**，这是 GitHub 文档族里唯一的表格化索引：

【原文】
```
| Section | What can you find there? |
| --- | --- |
| [A. Definitions](#a-definitions) | Some basic terms, defined in a way that will help you understand this agreement. ... |
| [B. Account Terms](#b-account-terms) | These are the basic requirements of having an Account on GitHub.  |
| [C. Acceptable Use](#c-acceptable-use)| These are the basic rules you must follow when using your GitHub Account. |
```
来源：`R7/github-docs-tos-src.md` 第 20–24 行 → https://docs.github.com/en/site-policy/github-terms/github-terms-of-service

【判断】ToS 用**字母编号 A–R（18 节）**，AUP 用**数字编号 1–11**，CG 用**无编号的散文标题**。三份同族文档三套编号方案，**没有统一的规则标识符空间**。指向：`R7/github-docs-tos-src.md` 汇总表 vs `R7/github-docs-aup-src.md` vs `R7/github-docs-cg-src.md`。

#### 1.1.3 作用域如何表达

GitHub 有**两种**作用域表达，且都不在规则正文里。

**(a) 文档级 `versions` 字段**：

【原文】`versions:\n  fpt: '*'`
来源：`R7/github-docs-aup-src.md`、`R7/github-docs-cg-src.md`、`R7/github-docs-tos-src.md` 三份 front-matter

【判断】`fpt` 指 Free / Pro / Team 三档账号计划，`'*'` 是通配。**这是账号计划（订阅层级）作用域，不是法域作用域。** 三份核心政策全部 `fpt: '*'`，意味着在这三份文档里作用域是「全体适用」，不区分计划。指向：三份源文件 front-matter。

站点政策索引的页面本身把版本显式渲染出来：【原文】`Version: Free, Pro, & Team`（来源：`R7/github-site-policy-index.txt` → https://docs.github.com/en/site-policy）。这印证 `fpt` = Free/Pro/Team。

**(b) 正文内的自然语言限定词** —— 国家/法域不通过字段表达，而通过条款文字：

【原文】`You are responsible for using the Service in compliance with all applicable laws, regulations, and all of our Acceptable Use Policies.`
来源：`R7/github-docs-aup-src.md` 第 16–18 行（第 1 节）→ https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【原文】`If you decide to post any promotional materials in your Account, you are solely responsible for complying with all applicable laws and regulations, including without limitation the U.S. Federal Trade Commission's Guidelines on Endorsements and Testimonials.`
来源：`R7/github-docs-aup-src.md` 第 115 行（第 10 节）→ 同一 URL

【判断】GitHub 处理法域的方式是**举证责任外推**：不建法域字段，改为「你负责遵守一切适用法律」+ 个别节里点名单一法域（此处点名美国 FTC）。**整个 AUP 只点名了一个法域**（美国）。指向：同上两段。

**(c) 平台/产品作用域靠「另立一份文档」而非字段**。ToS 目录第 I 节即为此：

【原文】`| [I. Additional Product Terms](#i-github-additional-product-terms) | We have a few specific rules for GitHub's features and products. |`
来源：`R7/github-docs-tos-src.md` 第 30 行 → https://docs.github.com/en/site-policy/github-terms/github-terms-of-service

站点政策索引里对应一整个产品级文档族：【原文】`[GitHub Terms for Additional Products and Features]` / `[GitHub Pre-release License Terms]` / `[GitHub Marketplace Terms of Service]` / `[GitHub Sponsors Additional Terms]` / `[GitHub Copilot Extension Developer Policy]` / `[GitHub Secret Scanning Partner Program Agreement]`（来源：`R7/github-site-policy-index.txt`）。

【判断】**GitHub 的产品作用域 = 文档族成员资格**，不是一个字段值。AUP 第 9 节把这条路径写得很直白：【原文】`For more details on specific features' bandwidth limitations, see the [GitHub Additional Product Terms]`（来源：`R7/github-docs-aup-src.md` 第 105 行）。所以「某个功能的具体限制在别处」是**显式设计的引用跳转**。

**(d) 一处罕见的「法域/授权来源」限定词**，出现在第 5 节：

【原文】`activities permitted under bug bounty programs, such as the [GitHub Bug Bounty program](https://bounty.github.com), are not considered "unauthorized," but must only affect the organization whose bug bounty program authorized the activity.`
来源：`R7/github-docs-aup-src.md` 第 76–77 行 → https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【判断】这是 GitHub 全文里唯一一处**通过「授权来源」而非「行为本身」来划边界的写法** —— 同一行为（入侵测试）因是否获得授权而合法/非法。这是**例外条款内嵌于禁止条款**的结构，不是独立例外表。指向：同上。

#### 1.1.4 兜底/其他类目

GitHub **没有名为「Other」的规则类目**，但有**三重兜底**，且措辞各不相同：

(1) **枚举尾部兜底**（AUP 摘要里的其他域）：【原文】`related to user safety, intellectual property, privacy, authenticity, and other limitations`
来源：`R7/github-docs-aup-src.md` 第 15 行

(2) **「非穷尽清单」声明**（Community Guidelines 尾部）：
【原文】`These are only guidelines; they do not modify our [Terms of Service](...) and are not intended to be a complete list. Under those terms, GitHub retains full discretion to remove any content or terminate any accounts for activity that violates our [Acceptable Use Policies](...). These guidelines describe when we will exercise that discretion.`
来源：`R7/github-docs-cg-src.md` 第 78 行 → https://docs.github.com/en/site-policy/github-terms/github-community-guidelines

(3) **一句独立的「用户保护」总兜底条**（AUP 第 11 节，全文最后一条实体规则）：
【原文】
```
## 11. User Protection

You must not engage in activity that significantly harms other users.

We will interpret our policies and resolve disputes in favor of protecting users as a whole.
```
来源：`R7/github-docs-aup-src.md` 第 117–121 行 → https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【判断】第 11 节是**教科书式的兜底条款**：它不描述任何具体行为，只给一个模糊判据（"significantly harms other users"），并配一句**解释规则**（"interpret our policies ... in favor of protecting users as a whole"）——即兜底条款不仅抓漏，还**规定歧义时向用户保护一侧倾斜**。这是本报告所有系统里唯一的「兜底条款自带解释方向」。指向：同上。

【判断】三重兜底各自的作用面不同：(1) 管类目枚举遗漏，(2) 管**文档效力层级**（CG 不修改 ToS、非完整清单），(3) 管**具体行为遗漏**。三者不互相替代。指向：上述三段。

#### 1.1.5 严重等级/后果

**GitHub 不给规则分等级。** AUP 11 个节没有一处标注严重度、没有 tier、没有分数。

后果被集中写在一处，且是 **flat 的 5 项动作清单**（Community Guidelines）：

【原文】
```
Where we have decided that moderation action is warranted, these are some of the ways we may respond:

* Removing the offending content
* Blocking or disabling the offending content
* Downgrading the visibility of the offending content
* Hiding a user account or organization from public view
* Suspending a user account or organization
```
来源：`R7/github-docs-cg-src.md` 第 64–70 行 → https://docs.github.com/en/site-policy/github-terms/github-community-guidelines

【判断】
- **档数 = 5，且是"响应手段清单"而不是"处罚阶梯"**：措辞是 `some of the ways we may respond`（"部分方式"），不是阶梯等级，**不承诺递进关系**。
- 5 项里只有 1 项是账号级（`Suspending a user account or organization`），其余 4 项都是内容级。
- 真正的终局动作（termination / content removal）**不在这个清单里**，而是通过链接指向 ToS：

【原文】`**Enforcement.** GitHub retains full discretion to [take action](/site-policy/github-terms/github-community-guidelines#what-happens-if-someone-violates-githubs-policies) in response to a violation of these policies, including account suspension, account [termination](/site-policy/github-terms/github-terms-of-service#3-github-may-terminate), or [removal](/site-policy/github-terms/github-terms-of-service#2-github-may-remove-content) of content.`
来源：`R7/github-docs-aup-src.md` 第 125 行（AUP 尾部 Enforcement 块）→ https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【判断】**后果的"事实清单"在 CG，"法律授权"在 ToS，"政策侧声明"在 AUP 尾部** —— 三处互相交叉引用，形成三角。这意味着「后果」在 GitHub 不是一个可枚举的封闭集合，而是 `discretion`（自由裁量）+ 示例。指向：上述两段 + ToS 目录 M 节 `Cancellation and Termination`。

【判断】GitHub 用**判断因素清单**代替等级表。CG 明示裁量时考虑的维度不是"违规多严重"，而是三个平台侧原则：

【原文】`We optimize for code collaboration. We recognize that code can have multiple uses and we distinguish between how the code is being used on the platform and other possible uses.` / `We take a human-centered approach to content moderation and we tailor our responses to meet the needs of a specific situation.` / `Our decisions are rooted in our core belief that serving an interconnected community ... requires a commitment to diversity, inclusion, and belonging.`
来源：`R7/github-docs-cg-src.md` 第 55–62 行

其中还含一条**双用途抗辩原则**：【原文】`with no implicit or explicit dual-use purpose prior to the abuse occurring`（来源：`R7/github-docs-aup-src.md` 第 74 行，第 5 节）—— 这是把"代码的合法用途"写进禁止条款的构成要件（即：若事先存在双用途目的，则不算违规）。

**唯一的"梯度"是解释性的，不是规则性的**：

【原文】`This could include taking into account potentially offensive content being posted in a way that lacks context or makes it easy for other users to unwittingly view or interact with while using GitHub. In those instances, we may favor moderation in order to safeguard our community.`
来源：`R7/github-docs-cg-src.md` 第 59–60 行

【判断】「展示方式」（是否缺上下文、是否易被无意看到）构成事实上的加减档因素，但**它是裁量说明，不是任何规则字段**。指向：同上。

后果链的另一半在 ToS 的两节标题上：【原文】`| [M. Cancellation and Termination](#m-cancellation-and-termination) | You may cancel this agreement and close your Account at any time. |`（来源：`R7/github-docs-tos-src.md` 第 37 行）与 AUP 引用的锚点 `#3-github-may-terminate`、`#2-github-may-remove-content` —— 说明 ToS 内部**把"移除内容"与"终止账号"拆成两个独立小节**，即平台把内容级处罚与账号级处罚当作两套独立权限来立法。

#### 1.1.6 变更历史

**GitHub 规则库内没有任何变更日志、生效日期或版本号。**

【判断】三份核心源 Markdown 的 front-matter 只含 `title / redirect_from / versions / category` 四个字段（见 1.1.2），**没有 `last_updated`、`date`、`version`、`changelog` 字段**。`versions: fpt: '*'` 中的 `versions` 是作用域声明（按 Docs 产品版本分流），**不是时间版本**。指向：`R7/github-docs-aup-src.md`、`R7/github-docs-cg-src.md`、`R7/github-docs-tos-src.md` front-matter。

**唯一的时间痕迹是行内注释**，且只有一处被保留在抓取到的源文件里：

【原文】`<!-- localization update 2026-03-11 - Feedback 1131974 -->`
来源：`R7/github-docs-aup-src.md` 第 115 行前（第 11 节 User Protection 上方）→ https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【判断】这条注释的语义是**翻译/本地化更新 + 反馈单号**，不是规则内容变更记录。它证明 GitHub 的源文件里存在**未被渲染的内部注释层**（含日期与工单号），但这一层是本地化工作流的产物，不构成对外的变更历史。指向：同上。

**变更的对外承诺写在"通知期"条款里，而不是历史记录里**：

【原文】`| [R. Changes to these Terms of Service](#r-changes-to-these-terms) | We may modify this agreement, but we will give you 30 days' notice of material changes. |`
来源：`R7/github-docs-tos-src.md` 第 40 行 → https://docs.github.com/en/site-policy/github-terms/github-terms-of-service

【原文】`These policies may be updated from time to time and are provided below.`
来源：`R7/github-docs-aup-src.md` 第 18 行 → https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies

【判断】**GitHub 的版本机制 = "前置通知 + 变更后无痕覆盖"，不是版本化存档。** ToS 承诺重大变更提前 30 天通知；AUP 只承诺"不时更新"。两者都**不保留旧版本、不发布 diff**。指向：上述两段。

【判断】`redirect_from` 是 GitHub 唯一**显式的沿革记录**，但它记录的是**URL 迁移**（`/articles/...` → `/github/site-policy/...` → AUP 子路径），不是规则内容变更。CG 的 redirect_from 有 4 条，AUP 有 2 条，ToS 有 6 条（`/tos`, `/terms`, `/terms-of-service`, `/github-terms-of-service-draft`, `/articles/github-terms-of-service`, `/github/site-policy/github-terms-of-service`）—— 其中 `/github-terms-of-service-draft` 是**唯一一条暗示文档曾以草案形态存在的痕迹**。指向：三份 front-matter。

【判断】CG 的授权方式本身也是版本相关的结构证据：`We dedicate these Community Guidelines to the public domain for anyone to use, reuse, adapt, or whatever, under the terms of [CC0-1.0]`（来源：`R7/github-docs-cg-src.md` 第 76 行）。CC0 意味着该文档**被有意排除在版本控制与归属约束之外**，任何人都可复制，因此对 CG 做版本追踪在制度上是被放弃的。

### 1.2 Mozilla AMO（addons.mozilla.org 扩展审核政策）

AMO 的结构与本报告其他所有系统**根本不同**：它是**同一文档内的十进制多级编号树**（1 → 1.1 → 6.2.2.1），而不是「多份文档 + 平铺类目」。规则的层级深度由编号深度直接承载。

#### 1.2.1 切了什么轴

**主轴 = 扩展的生命周期/合规维度（不是内容危害类型）。** 8 个一级节：

【原文】
```
[Content](#content)
[Submission Guidelines](#submission-guidelines)
[Development Practices](#development-practices)
[User Scripts](#user-scripts)
[Data Collection and Transmission Disclosure and Control](#data-collection-and-transmission-disclosure-and-control)
[Monetization](#monetization)
[Security, Compliance and Blocking](#security-compliance-and-blocking)
```
来源：`R7/amo-addon-policies.txt` 第 2170–2184 行（页内 TOC）→ https://extensionworkshop.com/documentation/publish/add-on-policies/

对照正文实际的一级标题（含 TOC 未列的 1）：

【原文】
```
1. No Surprises
2. Content
3. Submission Guidelines
4. Development Practices
5. User Scripts
6. Data Collection and Transmission Disclosure and Control
7. Monetization
8. Security, Compliance and Blocking
```
来源：`R7/amo-addon-policies.txt` 第 2185、2203、2225、2245、2269、2277、2373、2381 行 → 同一 URL

【判断】切轴逻辑是**"用户会怎样被骗"**而不是"内容属于什么类"：第 1 节 **No Surprises**（不意外）作为首条规则，是**以用户预期为核心的行为轴**；后续 2–7 各自对应一个可被滥用面（内容/提交/开发实践/用户脚本/数据/变现）；第 8 节是**元节**（执行与封禁），不描述被禁行为。指向：同上标题清单。

**次轴 = 编号深度承载规则强度。** 最深的规则在数据同意域：

【原文】
```
6.2.1. If the add-on is only compatible with Firefox 140 or later and uses Firefox's built-in data collection and transmission consent experience:
6.2.2. If the add-on is compatible with Firefox 139 and earlier or does not use Firefox's built-in data collection and transmission consent experience:
6.2.2.1. Personal Data (opt-in)
6.2.2.2. Implicit Consent for Self-Evident, Single-Use Extension
6.2.2.3. Technical & User Interaction Data (opt-out)
```
来源：`R7/amo-addon-policies.txt` 第 2301、2307、2331、2339、2361 行 → 同一 URL

【判断】**AMO 用"浏览器版本号"作为规则的分支条件** —— 6.2.1 与 6.2.2 的分野是 `Firefox 140 or later` vs `Firefox 139 and earlier`。这是本报告全部系统里**唯一一处把运行时/产品版本写进规则分支条件**的结构。指向：同上。

【判断】6.2.2.1 / 6.2.2.2 / 6.2.2.3 这第三层不是按危害分级，而是**按数据类型 × 同意模式（opt-in / implicit / opt-out）二维交叉**：个人数据=opt-in、自明单用途扩展=隐式同意、技术交互数据=opt-out。**同意模式是数据类型的函数，被写成三条并列规则。** 指向：上述三个编号标题。

#### 1.2.2 一条规则的内部结构

**最小规则单位 = 无编号的陈述句/祈使句，句式模板高度固定。** AMO 的规则句有三种规整形态：

(a) **`must` 强义务式**：
【原文】
```
Add-ons must only request those permissions that are necessary for them to function.
Add-ons must be self-contained and not load remote code for execution.
Add-ons must not load or redirect to a remote new tab page. The new tab page must be contained within the add-on.
Add-ons must not relax web page security headers, such as the Content Security Policy.
Add-ons must use encryption when transporting data remotely.
Add-ons should avoid including redundant code or files.
Add-ons must not negatively impact the performance or stability of Firefox.
```
来源：`R7/amo-addon-policies.txt` 第 2251–2263 行（第 4 节）→ https://extensionworkshop.com/documentation/publish/add-on-policies/

【判断】第 4 节第 6 条是 `should`（建议），其余 6 条是 `must`（强制）。**同一节内的相邻 bullet 用不同情态动词区分强制/建议强度** —— 这就是 AMO 表达"等级"的方式之一（见 1.2.5）。指向：同上。

(b) **`X are not permitted` 类目禁止式**（用于主题页）：
【原文】
```
Add-ons with the sole purpose of promoting, installing, loading or launching an outside website, application or add-on are not permitted.
Themes that feature low-quality, stretched, or blank images, as well as those themes in which the header image is misaligned, are not permitted. Duplicate themes are not permitted.
```
来源：`R7/amo-addon-policies.txt` 第 2221–2223 行（第 2 节）→ 同一 URL

(c) **`is prohibited` 事项式**（数据域）：
【原文】
```
Search functionality provided or loaded by the add-on must not transmit search terms or intercept searches that are going to a third-party search provider.
Transmitting or facilitating the transmission of ancillary information (e.g. any data not required for the add-on's functionality as stated in the description) is prohibited.
The transmission of browsing activity is only permitted as part of the add-on's primary function.
```
来源：`R7/amo-addon-policies.txt` 第 2285–2289 行（第 6.1 节）→ 同一 URL

【判断】第三种句式 `X is only permitted as part of Y`（**"仅在…时才允许"**）是 AMO 特有的**许可要件式**写法：默认禁止，附条件开禁。它比 GitHub 的"双用途抗辩"更结构化 —— GitHub 把双用途写在禁止条款的构成要件里（"with no ... dual-use purpose"），AMO 则把它单列成"仅允许"的正面条款。指向：`R7/amo-addon-policies.txt` 第 2289 行 vs `R7/github-docs-aup-src.md` 第 74 行。

**规则级元数据：所有 AMO 规则零元数据。** 唯一的**文档级元数据**是贡献者与最后更新者（见 1.2.6），**不是**规则级。

**文档内部有一个"多级限定链"结构**（小节为父节注入条件）：
【原文】`Add-ons must limit data transmission to what is necessary for functionality, and must use the data only for the purpose for which it was transmitted. For the purposes of this policy, data transmission refers to any data that is collected, used, transferred, shared, or handled outside of the add-on or the local browser.`
来源：`R7/amo-addon-policies.txt` 第 2279 行（第 6 节导语）→ 同一 URL

【判断】AMO 的**节导语承担"术语定义 + 适用边界"职责**：`For the purposes of this policy, data transmission refers to ...` 是**文档内定义条款**，为下属 6.1/6.2/6.3 的全部规则设定共同适用面。这是"作用域在父节点、规则在子节点"的结构。指向：同上。

同类还有：
【原文】`If the add-on uses native messaging, the Add-on Policies (including those related to user consent and control) apply to any data sent to the native application as well.`
来源：`R7/amo-addon-policies.txt` 第 2281 行 → 同一 URL

【判断】这是**作用域扩张条款**：把整份政策的作用面从"扩展本体"扩到"native messaging 对端应用"。**扩张写法放在第 6 节导语，一条覆盖全部 6.x 子规则。** 指向：同上。

#### 1.2.3 作用域如何表达

AMO 的作用域表达有 **4 种并存**，全部在**正文里**，不靠字段：

**(a) 分发渠道作用域（正面/负面双写）**：
【原文】`In addition, add-ons listed on addons.mozilla.org must adhere to the following policies:`
来源：`R7/amo-addon-policies.txt` 第 2209 行（第 2 节）→ https://extensionworkshop.com/documentation/publish/add-on-policies/

【原文】`We expect all add-ons, whether hosted on addons.mozilla.org or not, to be secure and well-maintained in how they handle both their own data and their users' data.`
来源：`R7/amo-addon-policies.txt` 第 2383 行（第 8 节）→ 同一 URL

【判断】**同一份文档里，第 2 节限定 `listed on addons.mozilla.org`，第 8 节明说 `whether hosted on addons.mozilla.org or not`。** 即：**部分规则只覆盖 AMO 上架扩展，部分规则覆盖全部扩展（含自分发）** —— 这个差别**只由节首一句限定词表达**，没有 scope 字段，也没有在目录/标题上标注。指向：上述两段。

**(b) 法域作用域（单一法域 + 其他法域保留条款）**：
【原文】`Add-ons and their content must conform to the laws of the United States. (Add-ons that violate or have content that violates the law in other jurisdictions may also be removed or have access limited.)`
来源：`R7/amo-addon-policies.txt` 第 2217 行（第 2 节）→ 同一 URL

【判断】AMO 显式指定**美国法**为唯一基准法域，括号内为非美法域的**保留裁量**（may also be removed or have access limited）。对比 GitHub 的「你负责遵守一切适用法律」（不指定基准法域），**AMO 选定基准法域 + 保留外扩，GitHub 则完全外推**。指向：`R7/amo-addon-policies.txt` 第 2217 行 vs `R7/github-docs-aup-src.md` 第 16–18 行。

**(c) 部署环境作用域**（企业托管为例外）：
【原文】`Add-ons installed in an enterprise environment can bypass asking for data collection consent when they are installed by enterprise policy. For more information, refer to the [enterprise documentation](/documentation/enterprise/enterprise-development/). If the add-on uses Firefox's built-in data collection and transmission consent experience, then the browser will bypass this by default.`
来源：`R7/amo-addon-policies.txt` 第 2297–2298 行（第 6.2 节）→ 同一 URL

【判断】**企业部署 = 独立作用域维度**，作用方式是把一条规则**降级为可豁免**（`can bypass asking for data collection consent`）。这是"作用域决定规则是否生效"（而非"作用域决定规则内容"）的写法。指向：同上。

**(d) 品类作用域**（扩展 / 主题 / 用户脚本管理器三分）：
【原文】`Themes that feature low-quality, stretched, or blank images ... are not permitted.` / `Usage of the userScripts API is allowed for user script managers only.` / `Add-ons with the sole purpose of promoting, installing, loading or launching an outside website, application or add-on are not permitted.`
来源：`R7/amo-addon-policies.txt` 第 2223 行（Theme）、第 2271 行（User Script）、第 2221 行（Add-on）→ 同一 URL

【判断】**品类作为主语写在规则句首**（"Themes that…"、"Usage of the userScripts API…"、"Add-ons with…"），没有独立品类字段。指向：同上三行。

**(e) 版本兼容作用域** —— 见 1.2.1 的 6.2.1 / 6.2.2 分支。

**没有找到的**：任何国家代码、地区列表、语言维度字段。AMO 用**"基准法域 + 一句保留"**覆盖了本可用国家列表表达的东西（见 4 章的搜索验证）。

#### 1.2.4 兜底/其他类目

AMO **没有 named "Other" 类目**，但有一条明确写出的**自由原则作为默认态**：

【原文】`In general, developers are free to maintain their add-ons in the manner they choose. However, in order to maintain appropriate data security measures and allow us to effectively review code, we have certain technical requirements that all add-ons must meet.`
来源：`R7/amo-addon-policies.txt` 第 2247 行（第 4 节导语）→ https://extensionworkshop.com/documentation/publish/add-on-policies/

【判断】这是**"默认允许 + 例外列举"结构**（default-permissive），与 GitHub 的"默认禁止 + 兜底条款"（default-prohibitive）方向相反。AMO 的兜底不是抓漏条款，而是**声明未列举之处开发自由**。指向：同上。这是本报告最清晰的一处「兜底哲学对立」。

另有一条**开放式的裁量兜底**（第 4 节）：
【原文】`In particular, potentially dangerous APIs may only be used in ways that are demonstrably safe, and code within add-ons that cannot be verified as behaving safely and correctly may need to be refactored.`
来源：`R7/amo-addon-policies.txt` 第 2249 行 → 同一 URL

【判断】`potentially dangerous APIs may only be used in ways that are demonstrably safe` —— **以"可证明安全"为判据的开放禁止**，不列举哪些 API。它和 `Reviewers may ask you to refactor parts of the code if it is not reviewable`（第 2241 行）共同构成**"不可审查性 = 可拒绝理由"**的兜底：当规则无法事先枚举时，兜底判据是"审查者能否验证"。指向：第 2247、2241 行。

**另有一条"最低要求"式兜底**：
【原文】`The following requirements are of particular importance:`
来源：`R7/amo-addon-policies.txt` 第 2255 行 → 同一 URL

【判断】`of particular importance` 意味着该 7 条 bullet 是**从完整要求集中挑出的重点子集**，即承认存在未列出的其他要求。这是"清单非穷尽"的另一种隐式表达（对比 GitHub CG 的显式 `not intended to be a complete list`）。指向：同上。

#### 1.2.5 严重等级/后果

AMO 的等级表达是**双轨**：情态动词区分义务强度，执行节区分后果强度。

**(a) 义务强度 —— 情态动词分档**
【原文】`Add-ons should avoid including redundant code or files.`（对照同节其余为 must）
来源：`R7/amo-addon-policies.txt` 第 2261 行 vs 2251–2263 行 → https://extensionworkshop.com/documentation/publish/add-on-policies/

【判断】观测到的档：`must`（强制）> `should`（建议）。**这不是后果档，是义务档。** 全篇第 4 节里 7 条 bullet 中只有 `should avoid including redundant code or files` 一条用 should。指向：同上。

**(b) 后果档 —— 执行节给出 3 类 + 2 条时间规则**

【原文】
```
Mozilla may reject or block affected versions or entire add-ons that don't comply with the above policies, depending on the extent of their non-compliance.

Mozilla may attempt to contact the add-on's developer(s) and provide a reasonable time frame for the problems to be corrected before a block is deployed. If an add-on appears to intentionally or repeatedly violate the policies, or its developers have proven unreachable, unresponsive, or uncooperative, blocking may be immediate.

Mozilla reserves the right to block or delete any developer's account on addons.mozilla.org, thereby preventing further use of the service, for certain violations of Mozilla's policies.
```
来源：`R7/amo-addon-policies.txt` 第 2385–2393 行（第 8.1 节 Policy Enforcement）→ https://extensionworkshop.com/documentation/publish/add-on-policies/

【判断】**对象粒度是 3 档且是本报告最细的**：`affected versions`（单版本） < `entire add-ons`（整扩展） < `developer's account`（开发者账号）。这是"按作用对象分档"而非"按处罚轻重分档"—— 且第 1 段明确说了分档依据是 **`depending on the extent of their non-compliance`（不合规的程度）**。指向：第 2387 行。

【判断】**时间维度作为独立档位依据**：默认给 `a reasonable time frame` 先联系整改；一旦满足 `intentionally or repeatedly violate` 或 `developers have proven unreachable, unresponsive, or uncooperative` 则 `blocking may be immediate`。**即 AMO 的"加档因素"是主观恶意/重复性/可联络性，而非危害大小。** 指向：第 2389–2391 行。

【判断】AMO 只用了 **2 个动作词**：`reject` 与 `block`。**没有 GitHub 式的 5 项响应清单，也没有 Meta 式的 tier 编号。** 三个后果档共享同一对动作词，靠**对象**而非**动作**区分。指向：第 2387–2393 行。

**(c) 与 review-rejection 页的交叉** —— 执行节显式外链到后果说明页：
【原文】`For more information about rejection and blocking, see [What does review rejection mean to users?](/documentation/publish/what-does-review-rejection-mean-to-users/)`
来源：`R7/amo-addon-policies.txt` 第 2394 行 → 同一 URL（该目标页已在证据中：`R7/amo-review-rejection.txt`）

#### 1.2.6 变更历史

**AMO 有全系统最完整的"文档级溯源元数据"，但依然没有版本号或 diff。**

页面尾部三个块（抓取文本连续出现）：

【原文】
```
Tags:

[add-ons](/tags/add-ons/)

[review](/tags/review/)

[policies](/tags/policies/)

Contributors:
[kewisch](https://github.com/kewisch/)

[rebloor](https://github.com/rebloor/)

[wagnerand](https://github.com/wagnerand/)

[atsay](https://github.com/atsay/)

[jvillalobos](https://github.com/jvillalobos/)

[wbamberg](https://github.com/wbamberg/)

[kmaglione](https://github.com/kmaglione/)

[dotproto](https://github.com/dotproto/)

[bacharakis](https://github.com/bacharakis/)

Last update:
[bacharakis](https://github.com/bacharakis/)
Apr 30, 2026
```
来源：`R7/amo-addon-policies.txt` 第 2396–2430 行 → https://extensionworkshop.com/documentation/publish/add-on-policies/

【判断】三重元数据：
- **`Tags`** = 规则库的**检索标签**，值域是 `add-ons` / `review` / `policies`（**只有 3 个标签**，粒度极粗，不构成分类树，是两个"领域标签"+ 一个"文档类型标签"）。
- **`Contributors`** = 9 个具名 GitHub 账号，是规则的**作者集合**（不是审阅者集合）。
- **`Last update`** = **具名个人 + 绝对日期**（`bacharakis` / `Apr 30, 2026`）。

**这是全部证据里唯一给出"谁在何时改了这份规则"的系统。** GitHub 只有匿名注释，Meta 只有日期串，npm/AWS 无。指向：同上。

【判断】**但仍然是整页级别的最后修改时间，不是逐条规则的行级历史，也没有 old/new diff。** 规则级的变更粒度不存在。指向：同上（页尾只有一组 Contributors + 一个 Last update，不在任何小节出现）。

对照另外三份 AMO 文档，三份都有同样的 Tags/Contributors/Last update 三元组（`R7/amo-review-rejection.txt` 第 2207/2221/2224 行、`R7/amo-source-code-submission.txt` 第 2329/2339/2350 行、`R7/amo-index.txt` 第 2255/2260 行）——**说明这是 Extension Workshop 站点的模板级机制，四份文档联合构成一个可溯源的规则库。** 指向：上述四文件的行号。

【判断】另有一条**版本回滚的产品功能**存在，但它管的是扩展版本而非规则版本：【原文】`[Version Rollback](/documentation/publish/version-rollback/)`（来源：`R7/amo-index.txt` 第 441 行 → https://extensionworkshop.com/documentation/publish/）。**注意不要把它误读成规则版本机制。**

### 1.3 PyPI / PSF（Python Software Foundation）

**PyPI 是 GitHub AUP 的一个声明式 fork。** 这不是推断 —— 文档自己写了（见 1.3.6）。因此本节的多数结构差异可读作"fork 之后的分叉点"，可比性极高。

#### 1.3.1 切了什么轴

**与 GitHub 同源的两轴：顶层 flat 否定式清单 + 下层单主题节。但 PyPI 的目录与正文用了两套不同的排序。**

目录（页面 TOC）是**字母序**：

【原文】
```
[Active Malware or Exploits](#active-malware-or-exploits)
[Advertising](#advertising)
[Bullying and Harassment](#bullying-and-harassment)
[Disrupting the Experience of Other Users](#disrupting-the-experience-of-other-users)
[Doxxing and Invasion of Privacy](#doxxing-and-invasion-of-privacy)
[Hate Speech and Discrimination](#hate-speech-and-discrimination)
[Impersonation](#impersonation)
[Misinformation and Disinformation](#misinformation-and-disinformation)
[Sexually Obscene Content](#sexually-obscene-content)
[Threats of Violence and Gratuitously Violent Content](#threats-of-violence-and-gratuitously-violent-content)
[Usage Limits](#usage-limits)
[Violations and Enforcement](#violations-and-enforcement)
[Credits & License](#credits-license)
```
来源：`R7/pypi-aup.txt` 第 36–60 行 → https://pypi.org/policy/acceptable-use-policy/

正文则先放**一整段无标题的连续 bullet 清单**，此后才逐个出现上表的小标题：

【原文】`We do not allow content or activity on PyPI that:`（`R7/pypi-aup.txt` 第 157 行），随后是 `is unlawful or promotes unlawful activities;` … `is off-topic, or interacts with platform features in a way that significantly or repeatedly disrupts the experience of other users.`（第 159–203 行区间）

【判断】**PyPI 的目录是字母索引，正文是主题分组，两者顺序不一致**；且正文最前面有一段"无标题总清单"，承接了 GitHub AUP 第 2/3/4/5 节合并后的全部否定句。**目录不是文档结构的镜像，而是检索入口。** 指向：`R7/pypi-aup.txt` 第 36–60 行 vs 第 157 行起。

【判断】**PyPI 的类目命名几乎全部沿用 GitHub**：`Active Malware or Exploits` / `Bullying and Harassment` / `Disrupting the Experience of Other Users` / `Doxxing and Invasion of Privacy` / `Hate Speech and Discrimination` / `Impersonation` / `Misinformation and Disinformation` / `Sexually Obscene Content` / `Threats of Violence and Gratuitously Violent Content` —— 与 GitHub 站点政策索引的 AUP 子页清单逐条对应（对比 `R7/github-site-policy-index.txt`）。**PyPI 只删不增**：未继承 GitHub 的 Terrorism、CSAM、NCII、Synthetic Media 四个子页。指向：两份文件的类目清单比对。

**fork 分叉点（PyPI 新增的类目）**：`Usage Limits` / `Violations and Enforcement` / `Credits & License` 三节是 PyPI 特有的，把 GitHub 散落的尾部条款（第 9 节带宽、Enforcement 块、法务声明）**收拢为三个正式一级类目**。指向：`R7/pypi-aup.txt` 第 481、506、519 行。

#### 1.3.2 一条规则的内部结构

**与 GitHub 同构：无编号 bullet，零规则级元数据。** fork 关系可由摘要段逐字证实：

【原文】`Short version: PyPI is a critical resource for the Python ecosystem, which hosts a variety of projects from a diverse group of users. That resource is only effective when our users are able to work together as part of a community in good faith. While using PyPI, you must comply with our Acceptable Use Policies, which include some restrictions on content and conduct on PyPI related to user safety, intellectual property, privacy, authenticity, and other limitations. In short, be excellent to each other.`
来源：`R7/pypi-aup.txt` 第 149–155 行 → https://pypi.org/policy/acceptable-use-policy/

对照 GitHub 原文（`R7/github-docs-aup-src.md` 第 15 行）：`**Short version:** _We host a wide variety of collaborative projects from all over the world, and that collaboration only works when our users are able to work together in good faith. ... related to user safety, intellectual property, privacy, authenticity, and other limitations. In short, be excellent to each other._`

【判断】**两段共享骨架、共享结尾句（`In short, be excellent to each other.`）、共享五域枚举（`user safety, intellectual property, privacy, authenticity, and other limitations`）。** PyPI 只做了名词替换（`GitHub`→`PyPI`、`collaborative projects`→`Python ecosystem`）。**连兜底措辞 `and other limitations` 都被一起 fork。** 指向：上述两段逐字比对。

**fork 后的"本地化"体现在句式上**：PyPI 的 bullet 去掉了 GitHub 的行内链接，变成纯文本，但保留了分号结尾与 `or` 收尾：

【原文】`is sexually obscene or relates to sexual exploitation or abuse, including of minors;`
来源：`R7/pypi-aup.txt` 第 163 行（对照 `R7/github-docs-aup-src.md` 第 24 行同句带链接版本）

**PyPI 新增的两种语用句式（GitHub 原版没有）：**

(1) **负向澄清 `not all X is Y`**：
【原文】`Please note, not all unwelcome conduct is necessarily considered harassment. For example, disagreeing with another user may not rise to the level of harassment on our platform. In addition, sharing criticism of public figures or projects, or topics of public interest, does not necessarily fall under this policy.`
来源：`R7/pypi-aup.txt`（Bullying and Harassment 节尾）→ https://pypi.org/policy/acceptable-use-policy/

(2) **跨类目升格提示 `may rise to the level of Z`**：
【原文】`Please note that disruptive conduct may also violate other restrictions in our Acceptable Use Policies. For example, depending on the nature and severity of the activity, it may rise to the level of bullying and harassment.`
来源：`R7/pypi-aup.txt`（Disrupting the Experience of Other Users 节尾）→ 同一 URL

【判断】第 (2) 种是**类目间的升级关系声明**：轻类目（Disrupting）在 `nature and severity` 足够时可升格为重类目（Bullying and Harassment）。**这是本报告唯一在规则正文中显式写出类目间升格路径的结构** —— 对比 Meta 靠 tier 判定、YouTube 靠 strike 累计、GitHub 完全不写。指向：同上。

**Terms of Use（另一份文档）的内部结构完全不同：第一人称承诺书。**
【原文】`By registering to upload materials to PyPI, I agree and affirmatively acknowledge the following:`
来源：`R7/pypi-terms.txt` 第 97–98 行 → https://pypi.org/policy/terms-of-use/

【原文】`"Content" means any data, content, code, video, images or other materials of any type that I upload, submit, or otherwise transmit to or through PyPI. Acceptable Content is restricted to Python packages and related information.`
来源：`R7/pypi-terms.txt` 第 100–102 行 → 同一 URL

【判断】句式主语是 **`I`**，不是 `you`。条款模板为 `I retain...` / `I represent and warrant that...` / `I further warrant that...`。**规则库的语法人称在此翻转：从"平台约束用户"变成"用户逐条自证合规"。** 指向：`R7/pypi-terms.txt` 第 97 行起的全部条款。

【判断】Terms 中唯一的**内容类型限定**就藏在这句定义里：`Acceptable Content is restricted to Python packages and related information.` —— PyPI 的"内容类型作用域"= 是否属于 Python 包及相关信息，**用一句定义表达，不构成字段或类目**。指向：第 102 行。

#### 1.3.3 作用域如何表达

**(a) 内容类型作用域（PyPI 特有，最关键）**
【原文】`Acceptable Content is restricted to Python packages and related information.`
来源：`R7/pypi-terms.txt` 第 102 行 → https://pypi.org/policy/terms-of-use/

【判断】GitHub 是代码托管（内容类型＝代码/issue/comment），PyPI 是包索引（内容类型＝发布包 + 元数据）。**这个根本差别只由一句定义承载。** 指向：同上。

**(b) 平台范围作用域 —— 只覆盖 PyPI 本站**
【原文】`We do not allow content or activity on PyPI that:`
来源：`R7/pypi-aup.txt` 第 157 行 → https://pypi.org/policy/acceptable-use-policy/

【判断】GitHub 对应句为 `on GitHub`，PyPI 为 `on PyPI` —— **fork 时替换的唯一作用域名词**。但两者的规约对象不同：PyPI 规约"上传到 PyPI 的内容"，GitHub AUP 规约"平台上的一切内容与活动"。指向：两份文件对应句。

**(c) 法域作用域 —— 沿用 GitHub 的外推策略**
【原文】`you are solely responsible for complying with all applicable laws and regulations, including without limitation the U.S. Federal Trade Commission's Guidelines on Endorsements and Testimonials.`
来源：`R7/pypi-aup.txt`（Advertising 节）→ 同一 URL

【判断】**美国 FTC 指引这一段被逐字 fork。** PyPI 继承了 GitHub 的"点名美国单一法域"策略。指向：两份文件 Advertising 节。

但 PyPI 在**出口管制**上写了 GitHub AUP 没有的硬条款：

【原文】`I represent and warrant that I have complied with all government regulations concerning the transfer or export of any Content I upload to PyPI. In particular, if I am subject to United States law, I represent and warrant that I have obtained any required governmental authorization for the export of the Content I upload. I further affirm that any Content I provide is not intended for use by a government end-user engaged in the manufacture or distribution of items or services controlled on the Wassenaar Munitions List as defined in part 772 of the United States Export Administration Regulations, or by any other embargoed user.`
来源：`R7/pypi-terms.txt` 第 138–146 行 → https://pypi.org/policy/terms-of-use/

【判断】**这是全部证据中唯一点名具体法域法规编号（Wassenaar Munitions List / 15 CFR part 772）的条款**，且以 `if I am subject to United States law` 作为**条件性法域触发**（不受美国法约束者不适用此条）。**法域条件写在条款内部，仍无字段。** 指向：同上。

**(d) 双用途作用域 —— PyPI 明确关闭 GitHub 留下的开口**
【原文】`Note that this includes dual-use content, including content that is used for research into vulnerabilities, malware, or exploits, including bug bounties. We consider PyPI to be a platform used primarily for installation and run-time use of code, and not for research.`
来源：`R7/pypi-aup.txt`（Active Malware or Exploits 节）→ https://pypi.org/policy/acceptable-use-policy/

对照 GitHub（`R7/github-docs-aup-src.md` 第 74 行）对同一情形的处理：`with no implicit or explicit dual-use purpose prior to the abuse occurring`，另加 bug bounty 授权例外（第 76–77 行）。

【判断】**本报告最重要的一处结构对立**：同为 fork 关系，GitHub 把 `dual-use purpose` 写成**免责要件**（有双用途目的 → 不构成违规），PyPI 写成**入罪要件**（`this includes dual-use content` → 双用途照样违规），并额外点名排除 `bug bounties`。**同一个短语在两份文档里被反向使用，说明该表述本身不承载固定规范含义，方向完全由各平台按自身内容类型决定。** 指向：两份文件同一节对照。

#### 1.3.4 兜底/其他类目

与 GitHub 同源的三重兜底，前两项全部保留：

(1) 枚举尾部：【原文】`related to user safety, intellectual property, privacy, authenticity, and other limitations`（`R7/pypi-aup.txt` 第 152–153 行）

(2) 总兜底条 —— **PyPI 把它从独立编号节降级为一段散文**：
【原文】`You must not engage in activity that significantly harms other users. We will interpret our policies and resolve disputes in favor of protecting users as a whole.`
来源：`R7/pypi-aup.txt` 第 228–231 行 → https://pypi.org/policy/acceptable-use-policy/

【判断】同样的两句话在 GitHub 是 **AUP 第 11 节，有编号、有标题、独立成节**（`R7/github-docs-aup-src.md` 第 117–121 行）；在 PyPI 变成**插在正文中段、无编号、无标题的两句**（紧接 `These policies may be updated from time to time` 之后，位于各主题节之前）。**fork 抹掉了编号层级，兜底条款的可见性与可引用性下降。** 指向：两份文件对应段落。

(3) PyPI **新增一条以"切题性"为判据的兜底类目**：
【原文】`is off-topic, or interacts with platform features in a way that significantly or repeatedly disrupts the experience of other users.`
来源：`R7/pypi-aup.txt` 第 201–203 行 → 同一 URL

【判断】`is off-topic` 是 GitHub 原版**没有**的禁止项。包索引平台特有：一个包若与 Python 开发无关即属 off-topic。**它与 1.3.3(a) 的 `Acceptable Content is restricted to Python packages` 形成呼应**（定义式声明 + 禁止式兜底的配对）。指向：第 201 行 + `R7/pypi-terms.txt` 第 102 行。

#### 1.3.5 严重等级/后果

**PyPI 没有任何等级、tier 或分数。后果是一句 flat 清单，且只有 3 项：**

【原文】`PyPI retains full discretion to take action in response to a violation of these policies, including account suspension, account termination, or removal of content.`
来源：`R7/pypi-aup.txt` 第 508–510 行（Violations and Enforcement 节）→ https://pypi.org/policy/acceptable-use-policy/

【判断】**档数 = 3**（`account suspension` / `account termination` / `removal of content`），全部是动作名，无顺序、无门槛、无对应违规类型。对比 GitHub 的 5 项（多出 `blocking/disabling`、`downgrading visibility`、`hiding a user account or organization from public view`）—— **PyPI fork 时砍掉了全部 3 项"可见性/可发现性"类处罚，只留账号与内容两类。** 指向：`R7/pypi-aup.txt` 第 508–510 行 vs `R7/github-docs-cg-src.md` 第 68–70 行。

**PyPI 的独有结构：明确取消申诉。**
【原文】`While the majority of interactions between individuals in PyPI's community fall within our Acceptable Use Policies and Community Guidelines, violations of those policies do occur at times. When they do, PyPI staff may need to take enforcement action to address the violations. In all cases, these actions are permanent and there is no basis to reverse a moderation action taken by PyPI Staff.`
来源：`R7/pypi-aup.txt` 第 512–517 行 → 同一 URL

【判断】**`In all cases, these actions are permanent and there is no basis to reverse a moderation action`** —— 全部证据中**最强硬的终局性声明**：不是"分级裁量"，而是"一律永久、无复审依据"。对照：GitHub 专设 `Appeal and Reinstatement` 页（`R7/github-site-policy-index.txt` AUP 分组最后一条）、YouTube 有 strike 过期机制、Meta 有申诉渠道。**PyPI 是唯一明确写"没有复审依据"的系统。** 指向：同上。

**唯一带"程度"措辞的规则靠副词而非档位**：

【原文】`PyPI generally does not impose resource limitations on any features. If we determine your usage of PyPI to be significantly excessive in relation to other users of similar features, we reserve the right to suspend your Account, throttle your requests, or otherwise limit your activity until you can reduce your usage.`
来源：`R7/pypi-aup.txt` 第 483–488 行（Usage Limits）→ 同一 URL

【原文】`We do not allow behavior that significantly or continually disrupts the experience of other users.`
来源：`R7/pypi-aup.txt`（Disrupting the Experience of Other Users）→ 同一 URL

【判断】**PyPI 的"严重度"以程度副词寄生在规则构成要件里**：`significantly excessive`、`significantly or continually disrupts`、`significantly harms other users`（第 228 行）—— 三个 `significantly` 分别界定三条不同规则的成立门槛。**程度副词就是 PyPI 的等级机制**（无 tick、无 tier、无分数）。指向：上述三段。

【判断】**唯一的"升格指示"在正文里，不在处罚表里**：`depending on the nature and severity of the activity, it may rise to the level of bullying and harassment`。PyPI 允许 Disrupting 类案件**升格定性**为 Bullying，但**升格后适用何种后果仍无规定** —— 类目可升级，处罚不可升级。指向：Disrupting 节尾段。

**另有一处"能力保留式"后果**：
【原文】`We reserve the right to remove any promotional materials or advertisements that, in our sole discretion, violate any PyPI terms or policies.`
来源：`R7/pypi-aup.txt`（Advertising 节）→ 同一 URL

【判断】`in our sole discretion` 与 `retains full discretion` 是 PyPI 授权裁量的固定措辞，共出现 2 次（Advertising + Violations and Enforcement）。**裁量是唯一贯穿性的"等级替代物"。** 指向：Advertising 节 + 第 508 行。

#### 1.3.6 变更历史

**PyPI 是全部证据中唯一具备"显式作废记录 + 显式 fork 出处声明 + 页面日期 + 开源许可证"四项的系统。**

**(1) 作废横幅（Terms of Use 页）**
【原文】
```
Note

Superseded by
[PyPI Terms of Service](../Terms-of-Service/)
: February 25,
2025
```
来源：`R7/pypi-terms.txt` 第 89–95 行 → https://pypi.org/policy/terms-of-use/

【判断】**本报告唯一的"作废 + 后继文档 + 生效日期"三元记录**：旧文档 `PyPI Terms of Use` 被 `PyPI Terms of Service` 取代，日期 `February 25, 2025`。**旧文档仍在线可读** —— 这就是版本存档。对照 GitHub 的"前置通知 + 变更后无痕覆盖"（1.1.6）。指向：同上。

【判断】AUP 页面也出现 `Superseded` 字样（`R7/pypi-aup.txt` 第 63、65 行，位于侧边导航的文档状态标记区），但**正文未给出后继文档名与日期**。两页的作废信息披露完整度不一致：Terms 给全三元组，AUP 只给一个状态词。指向：`R7/pypi-aup.txt` 第 63–65 行 vs `R7/pypi-terms.txt` 第 89–95 行。

**(2) fork 出处声明 + 许可证 + 日期（AUP 页尾 Credits & License 节）**
【原文】
```
This policy is based on
[GitHub's Acceptable Use Policies](https://docs.github.com/en/site-policy/acceptable-use-policies/)
and
modified from its original form.

Licensed under the
[Creative Commons Attribution 4.0 International license](https://creativecommons.org/licenses/by/4.0/).

February 13, 2025
```
来源：`R7/pypi-aup.txt` 第 521–533 行 → https://pypi.org/policy/acceptable-use-policy/

【判断】三重元数据：
- **上游出处**：`based on GitHub's Acceptable Use Policies and modified from its original form` —— **规则库的 fork 谱系写在文档正文里**。
- **许可**：`Creative Commons Attribution 4.0 International` —— **规则文本本身是被许可的作品**。这正是 fork 得以合法发生的前提。
- **日期**：`February 13, 2025` —— 文档级日期，`月 日, 年` 格式，**无版本号**。

对照 GitHub Community Guidelines 的 `CC0-1.0` 公有领域奉献（`R7/github-docs-cg-src.md` 第 76 行）：**GitHub 的 CG 放弃版权以便任何人复用，而 GitHub AUP 本身未见许可证声明；PyPI 取用 AUP 后为其 fork 成果声明 CC-BY-4.0。** 形成"上游无声明、下游署名授权"的链条。指向：`R7/github-docs-cg-src.md` 第 76 行 vs `R7/pypi-aup.txt` 第 527–531 行。

**(3) 底层仓库线索（结构性证据）**
【原文】`Made with [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/)`
来源：`R7/pypi-aup.txt` 末行、`R7/pypi-terms.txt` 末行

【原文】`[GitHub](https://github.com/psf/policies)`
来源：`R7/pypi-aup.txt` 第 9 行（页面顶栏）

【判断】PSF 政策站点是 **MkDocs 静态站，源在 GitHub 仓库 `psf/policies`**。即：**规则文本存放在 git 仓库中，全站同源，规则历史天然由 git 承载 —— 但站点不渲染任何 git 历史、diff 或版本号。** 这是"版本能力存在但未暴露"的结构：底层有版本控制，面向读者的界面只有 `Superseded` 横幅与一个日期。指向：上述两行。

【判断】同时注意 PyPI 的规则族**不止 AUP 一份**：侧栏列出 `PSF Privacy Notice` / `Terms of Service` / `Acceptable Use Policy` / `Terms of Use`（已作废）/ `Code of Conduct` / `Privacy Notice`，且 Python 站与 PyCon US 站各有一套 Code of Conduct 与执行程序（`R7/pypi-aup.txt` 第 20–30、80–110 行的侧栏导航）。**即 PyPI/PSF 采用"多站点 + 每站一套政策"的组织方式，AUP 只是其中一个成员。** 指向：`R7/pypi-aup.txt` 侧栏导航全文。
---

### 1.4 npm

npm 的结构特征：**它有一份真正的"政策库索引"（14 条 Policies 导航），但内容规则不在 AUP 里 —— 而在《Open Source Terms》的 `Acceptable Use` / `Acceptable Content` 两节，写法是"许可授予的条件"。** 且 npm **把变更历史显式外包给 git**。

#### 1.4.1 切了什么轴

**主轴 = 政策类型（policy document），且是全证据中最完整的一份政策库目录。** npm 文档站的 `Policies` 分组列出 14 项：

【原文】
```
[Terms of Use](/policies/terms)
[Open Source Terms](/policies/open-source-terms)
[Dual Use Content](/policies/dual-use)
[Private Terms](/policies/private-terms)
[Code of Conduct](/policies/conduct)
[Package Name Disputes](/policies/disputes)
[npm License](/policies/npm-license)
[Privacy Policy](/policies/privacy)
[Unpublish Policy](/policies/unpublish)
[Copyright and DMCA Policy](/policies/dmca)
[Logos and Usage](/policies/logos-and-usage)
[Security](/policies/security)
[Replication and web crawler policy](/policies/crawlers)
[Threats and mitigations](/threats-and-mitigations)
```
来源：`R7/npm-terms-of-use.txt` 第 235–252 行（同一导航块在 `R7/npm-unpublish.txt`、`R7/npm-disputes.txt`、`R7/npm-security.txt`、`R7/npm-open-source-terms.txt` 第 241 行附近重复出现）→ https://docs.npmjs.com/policies/terms

【判断】这 14 项**不是内容类目，而是"问题域 + 文档类型"的混合切轴**：
- 按**合同类型**：Terms of Use / Open Source Terms / Private Terms
- 按**主题问题域**：Dual Use Content / Code of Conduct / Package Name Disputes / Privacy / Unpublish / DMCA / Logos / Security / Crawlers / Threats
- 按**许可**：npm License

**即 npm 的政策库索引是"一份文件一条轴"，每条轴名 = 该文件的主题**，而不是"一个类目一组合规规则"。指向：同上导航块。

【判断】**npm 是唯一为双用途内容单独立一份政策页的系统**（`/policies/dual-use`，`Dual Use Content`）。对照 GitHub 把双用途写进 AUP 第 5 节的一个从句、PyPI 写进 Active Malware 节的一段 Note —— **npm 把它提升为独立文档**。指向：导航块第 3 项。

**内容规则的实际切轴（在 Open Source Terms 内）= 两个节**：
【原文】
```
[Acceptable Use](#acceptable-use)
[Acceptable Content](#acceptable-content)
```
来源：`R7/npm-open-source-terms.txt` 第 479、485 行 → https://docs.npmjs.com/policies/open-source-terms

【判断】**"行为"（Acceptable Use）与"内容"（Acceptable Content）在 npm 里是分开的两节** —— 这是全部证据中唯一显式做此二分的结构。GitHub 的 AUP 把两者混在同一句（`We do not allow content or activity on GitHub that:`），Meta 也混写（`content or activity`）。**npm 的 `Acceptable Use` 管行为、`Acceptable Content` 管被托管的制品。** 指向：`R7/npm-open-source-terms.txt` 第 595、639 行两个标题。

**Acceptable Use 节内部再分"行为类型"**：不给子标题，但可辨出 5 类 —— 违反其他政策（指向 Code of Conduct / Dispute Policy）、不得提交违规内容、信息披露类、账号与名称类、自动化与基础设施类。指向：第 597–637 行。

**Acceptable Content 节按"制品种类"枚举**：
【原文】`Unacceptable content can take the form of a package, a README file, a user or organization name, or any other content submitted to npm Services.`
来源：`R7/npm-open-source-terms.txt` 第 641–643 行 → 同一 URL

【判断】**npm 明确列出"内容载体"清单**（package / README / user or organization name / any other content），这是本报告唯一把"被规制对象"的形式也枚举出来的写法。**用户名和组织名在 npm 里是"内容"的一种** —— 这解释了为什么 npm 需要一份独立的 Disputes Policy。指向：同上。

#### 1.4.2 一条规则的内部结构

**最小规则单位 = `You will (not) ...` 句式。** npm 的规则用**将来时承诺句**，而非 GitHub/PyPI 的"我们不允许"否定式：

【原文】
```
You will abide by the [Code of Conduct](/policies/conduct) and the [Dispute Policy](/policies/disputes).
You will not submit material to npm as a package or in any other form that violates npm's Acceptable Content , described below.
You will not disclose information that you do not have the right to disclose, such as confidential information of others.
You will not copy or share any personally identifiable information of any other person without their specific permission.
You will not violate any applicable law.
You will not use or attempt to use another person's Account without their specific permission.
You will not buy, sell, or otherwise trade in user names, organization names, names for Packages , or any other names reserved on npm Services , for money or other compensation.
You will not use npm Services ' ability to send e-mail to send advertisements, chain letters, or other solicitations.
You will not automate access to, use, or monitor the Website, such as with a web crawler, browser plug-in or add-on, or other computer program that is not a web browser. You may replicate data from the Public Registry using the Public APIs per this Agreement.
You will not use npm Services to send email to distribution lists, newsgroups, or group mail aliases.
You will not falsely imply that you are affiliated with or endorsed by npm.
You will not operate illegal schemes, such as pyramid schemes, via npm Services.
You will not deep-hyperlink to images or other non-hypertext content served by npm Services.
You will not remove any marking indicating proprietary ownership from any material got via npm Services.
You will not display any portion of the Website via an HTML IFRAME.
You will not disable, avoid, or circumvent any security or access restrictions of npm Services, or access parts of npm Services not intended for access by you.
You will not strain infrastructure of npm Services with an unreasonable volume of requests, or requests designed to impose an unreasonable load on IT systems underlying npm Services. ...
You will not encourage or assist any other person in violation of "Acceptable Use".
```
来源：`R7/npm-open-source-terms.txt` 第 597–637 行 → https://docs.npmjs.com/policies/open-source-terms

【判断】共 18 条，**全部以 `You will` 开头**，规则之间无编号、无 ID、无元数据，靠**行序**引用（正文用 `described below` 做内部指向）。**规则级元数据为零，与 GitHub/PyPI 相同。** 指向：同上。

【判断】句式的**法律性质不同于其他系统**：这不是"平台单方声明禁止"，而是**"你的使用许可受以下条件约束"**。这一段的上位句是：

【原文】`Your permission to use npm Open Source, as well as any permission you may have to use Paid Services, are subject to the following conditions:`
来源：`R7/npm-open-source-terms.txt` 第 585 行 → 同一 URL

【判断】**npm 把内容规则构造成"许可条件"（condition of a license grant）而不是"行为守则"** —— 违反的后果因此是"许可自动失效"，而非"平台裁量处罚"。这解释了 1.4.5 里 npm 后果条款的措辞（`You may not use npm Services after npm says you may not`）。指向：第 585–593 行。

**npm 独有：规则内部含"元注释"，解释规则为何故意写宽。**
【原文】`You will not strain infrastructure of npm Services with an unreasonable volume of requests, or requests designed to impose an unreasonable load on IT systems underlying npm Services. This rule is intentionally loose, to give npm the flexibility it needs to keep npm Services working for the user community as a whole. But to draw one clear line, under no circumstances are five million requests to npm Services in a single month-long period by any single individual, organization, or group of affiliated companies remotely reasonable. If you have a special need to make lots and lots of requests, [our sales team](mailto:sales@npmjs.com) can help.`
来源：`R7/npm-open-source-terms.txt` 第 631–633 行 → 同一 URL

【判断】**这是全部证据中唯一一条自带"为什么这样写"说明的规则**：`This rule is intentionally loose, to give npm the flexibility it needs` + `But to draw one clear line` —— **模糊标准 + 一个硬数字兜底**。规则结构因此是三层：`unreasonable`（标准）→ 元注释（说明故意模糊）→ `five million requests ... in a single month-long period`（唯一硬阈值）。

**`five million requests per month` 是全部文本型规则证据中唯一出现的绝对数值阈值。** 对照：Meta/YouTube 用 tier 与 strike 计数、AMO 用 `a reasonable time frame`、AWS 用 `2 business days`（时限而非量）—— **没有一个给出"请求量"级数字，只有 npm 给了。** 指向：同上。

**Acceptable Content 节的结构 = 开放判据 + 非穷尽示例。**
【原文】`Administrators at npm reserve the right to delete content hosted on the npm Services that they deem unacceptable. Unacceptable content can take the form of a package, a README file, a user or organization name, or any other content submitted to npm Services. A few examples of unacceptable content:`
来源：`R7/npm-open-source-terms.txt` 第 641–645 行 → 同一 URL

【判断】**结构是"全权裁量 + 载体枚举 + 非穷尽示例"**：`reserve the right` 建立裁量，`can take the form of` 枚举载体，`A few examples of` 明示列举不穷尽。**核心判据是 `they deem unacceptable`（主观认定），没有任何客观标准** —— 这是本报告中最弱约束力的规则构造（对比 GitHub 用 `significantly harms`、PyPI 用三个 `significantly`）。指向：同上。

**npm 的双用途规则结构（第三个立场）**：
【原文】`Content containing malicious computer code, such as computer viruses, computer worms, rootkits, back doors, or spyware. This includes content submitted for research purposes. Tools designed and documented explicitly to assist in security research are acceptable, but exploits and malware that use the npm registry as a deployment or delivery vector are not.`
来源：`R7/npm-open-source-terms.txt`（Acceptable Content 节）→ 同一 URL

【判断】**第三个双用途立场（对比 GitHub 与 PyPI）**，且是三者中最细的：
- GitHub：`dual-use purpose` 是**免责要件** → 有双用途目的即不违规（`R7/github-docs-aup-src.md` 第 74 行）
- PyPI：`this includes dual-use content ... including bug bounties` → 双用途**照样违规**（`R7/pypi-aup.txt` Active Malware 节）
- npm：**按"用途 + 交付渠道"二分** —— `submitted for research purposes` 也在禁止范围内；但 `Tools designed and documented explicitly to assist in security research are acceptable`；判据落在**是否把 registry 当 deployment or delivery vector**。

**三份文档对同一问题给出三种不同的判据轴（目的 / 内容类型 / 交付渠道）。** 指向：上述三份文件对应段落。

**规则内部的"载体兼容性"要件（npm 特有）**：
【原文】`Packages that are not functionally compatible with the npm command-line client. For example, a "package" cannot simply be a PNG or JPEG image, a movie file, or a text document uploaded directly to the registry. Using the Public Registry as a general purpose database is not allowed.`
来源：`R7/npm-open-source-terms.txt`（Acceptable Content 节）→ 同一 URL

【判断】这是**结构性等同物**于 PyPI 的 `Acceptable Content is restricted to Python packages`（1.3.3a）与 GitHub 的"代码托管"隐含预设：**包管理平台都有一条"内容必须是该平台的合法制品"的元规则**，但表达方式三家不同 —— PyPI 用定义句、npm 用禁止句 + 例子、GitHub 完全不用（不做限制）。指向：三份文件对应段落。

#### 1.4.3 作用域如何表达

**(a) 服务分区作用域 —— npm 用"文档分区"而非字段**
【原文】`Your permission to use npm Open Source, as well as any permission you may have to use Paid Services, are subject to the following conditions:`
来源：`R7/npm-open-source-terms.txt` 第 585 行 → https://docs.npmjs.com/policies/open-source-terms

【判断】npm 的作用域主轴是**免费/付费服务分区**：`npm Open Source`（含 Public Registry + 网站）由 Open Source Terms 管；`Paid Services`（Solo / Orgs）由 `/policies/private-terms` 管。**作用域 = 你读的是哪份文档。** 指向：第 585 行 + `R7/npm-terms-of-use.txt` 的 `[Paid npm services](#paid-npm-services)` 节（`npm's paid products, including the npm Solo and Orgs plans, are covered by the npm Paid Services Terms`）。

**(b) 注册处范围作用域**
【原文】`(the Public Registry ). npm, Inc. ( npm ) operates each of those services. These terms refer to all of them together as npm Open Source .`
来源：`R7/npm-open-source-terms.txt` 第 515 行 → 同一 URL

【判断】`Public Registry` 是具名的作用域实体，另有 `Private Terms` / `private packages` 与之对置。**但有 `[Replication and web crawler policy](/policies/crawlers)` 单管"复制 registry 数据"这一行为域** —— 即某些行为有专属作用域文档。指向：导航块 + 第 515 行。

**(c) 法域作用域 —— 一处显式法域限定 + 仲裁条款**
【原文】`You will not violate any applicable law.`
来源：`R7/npm-open-source-terms.txt` 第 605 行 → 同一 URL

【判断】与其他系统不同，**npm 的法域条款只有一句泛化表述，没有点名任何国家或法规**。但 npm Open Source Terms 含强制仲裁条款（`an agreement to arbitrate disputes individually in "Arbitration"`，第 521–523 行）—— **法域问题被转化为程序问题（仲裁）而不是实体规则**。指向：第 521–523、605 行。

**(d) 年龄作用域（独有的实体化资格条件）**
【原文】`You must be at least 13 years of age to use npm Services.`
来源：`R7/npm-open-source-terms.txt` 第 589 行 → 同一 URL

【判断】**全部证据里唯一写死年龄门槛的通用条款**。对照：GitHub 把年龄放在 ToS 的 Account Terms 而未在 AUP 出现，Meta 的 `18 and older` 是**内容可见性档位**（见 1.8.5）而非使用者资格。**npm 的 13 岁是"使用资格"，Meta 的 18 岁是"观看资格"——同一数字域承载完全不同的结构角色。** 指向：第 589 行 vs `R1/meta-cs-STRUCTURE-INVENTORY.md` 第 5 节。

**(e) 作用域的"外部依赖"（npm 独有）** —— npm 的 Disputes Policy 把作用域判据整体外包给 GitHub：
【原文】`npm follows GitHub's [Username Policy](https://docs.github.com/en/site-policy/other-site-policies/github-username-policy). This means that usernames, organization names, and package names are available on a first-come, first-served basis, and are intended for immediate and active use.`
来源：`R7/npm-disputes.txt` 第 463–467 行（`tl;dr` 节）→ https://docs.npmjs.com/policies/disputes

【原文】`npm processes Trademark claims under GitHub's [Trademark Policy](https://docs.github.com/en/site-policy/content-removal-policies/github-trademark-policy).`
来源：`R7/npm-disputes.txt`（Trademarks 节）→ 同一 URL

【原文】`please follow the formal [name dispute process](https://docs.github.com/en/site-policy/content-removal-policies/github-trademark-policy) on GitHub - that is the only path we act on.`
来源：`R7/npm-disputes.txt`（Squatting 节）→ 同一 URL

【判断】**npm 的名称/商标治理通过引用整体指向 GitHub 的政策库**（甚至在 GitHub 的表单 `support.github.com/contact/trademark-policy` 上受理）。这与 PyPI 的"fork 文本"是两种不同的规则库间关系：
- **PyPI = 文本级 fork**（复制 → 本地化 → 署名）
- **npm = 引用级委托**（不复制 → 运行时跳转到上游）

**同一生态圈里，下游规则库对上游的依赖可以采取 fork 或 reference 两种形态。** 指向：`R7/npm-disputes.txt` 三处引用 vs `R7/pypi-aup.txt` 第 521–529 行。

#### 1.4.4 兜底/其他类目

**npm 没有名为 "Other" 的类目，兜底由三处构成，全部是"开放判据 + 非穷尽示例"。**

(1) **Acceptable Content 全节即兜底**：
【原文】`Administrators at npm reserve the right to delete content hosted on the npm Services that they deem unacceptable. ... A few examples of unacceptable content:`
来源：`R7/npm-open-source-terms.txt` 第 641–645 行 → https://docs.npmjs.com/policies/open-source-terms

【判断】**`deem unacceptable` 是全部证据中最宽的兜底判据（纯主观），`A few examples of` 是显式非穷尽标记。** 由于禁止集合由裁量定义，npm 的 Acceptable Content 节**整个就是兜底条款** —— 4 条示例只是说明，不是规则集。指向：同上。

(2) **载体枚举尾部兜底**：【原文】`or any other content submitted to npm Services`（第 643 行）—— 与 GitHub 的 `and other limitations`、PyPI 的 `and other limitations` 同类，但 npm 兜的是**载体形式**，GH/PyPI 兜的是**规则类目**。指向：第 643 行。

(3) **许可条件式兜底**：
【原文】`You will not encourage or assist any other person in violation of "Acceptable Use".`
来源：`R7/npm-open-source-terms.txt` 第 637 行 → 同一 URL

【判断】**"协助他人违反"作为最后一条规则**，是覆盖面最广的兜底（把第三方行为也纳入）。**这是全部证据中唯一显式的"协助违规则亦违规"条款。** GitHub 只有 `using GitHub as a platform for propagating abuse on other platforms`（跨平台，不同构），Meta 只在正文含 `coordinating harm`。指向：第 637 行。

(4) **另有一处"未定义即默认允许"的隐含兜底**：Acceptable Use 全节 **不含**任何"其他未列行为亦禁止"的条款，且上位句是 `Your permission ... subject to the following conditions` —— **条件之外即允许**（default-permissive，结构上同 AMO 的 1.2.4）。指向：第 585 行 + 第 597–637 行的封闭清单。

#### 1.4.5 严重等级/后果

**npm 没有等级、tier 或分数。后果分两类，且判据用词明显宽于其他系统。**

**(a) 账号级后果（3 个动作）**
【原文】`npm may restrict, suspend, or terminate your Account according to the Copyright Policy, if npm reasonably believes that you are in breach of these Terms, or if npm reasonably believes that you have misused npm Services.`
来源：`R7/npm-open-source-terms.txt` 第 703 行（`[Your Account](#your-account)` 节）→ https://docs.npmjs.com/policies/open-source-terms

【判断】**档数 = 3**（`restrict` / `suspend` / `terminate`），用 `or` 连接、无门槛说明。**注意这不是独立的"处罚条款"，而是写在「你的账号」一节的属性说明里** —— 后果条款**寄生在主体定义节**中，不单列 Enforcement 节。对比 PyPI 有独立 `Violations and Enforcement` 节、GitHub CG 有独立处罚段、AMO 有独立 `8.1 Policy Enforcement`。**npm 是唯一不设独立执行节的系统。** 指向：第 703 行。

**(b) 内容级后果（无需通知）**
【原文】`npm may remove Your Content from npm Services without notice if npm suspects Your Content was submitted or used in violation of "Acceptable Use", as well as per the Copyright Policy.`
来源：`R7/npm-open-source-terms.txt` 第 711 行 → 同一 URL

【判断】**`if npm suspects`（怀疑即可）是本报告中最低的举证门槛**。对照：
- GitHub：`Where we have decided that moderation action is warranted`（已决定）
- PyPI：`retains full discretion`（裁量）
- Meta：分级 + `reasonably`（合理相信）
- AMO：`depending on the extent of their non-compliance`（程度认定）
- AWS：`we reasonably believe` + 2 business days 整改期（合理相信 + 程序）
- npm：`suspects` + `without notice`（怀疑 + 无通知）

**这是六档举证门槛中最低的一档。** 指向：第 711 行与其他系统对应句。

**(c) 硬性终止规则（非裁量）**
【原文】`You may not use npm Services after npm says you may not, such as by disabling your Account.`
来源：`R7/npm-open-source-terms.txt` 第 591 行 → 同一 URL

【判断】**这是全部证据中唯一"禁令无期限、无复审、自动生效"的资格取消条款**（形式上是用户承诺，实质上是永久禁令）。与 PyPI 的 `these actions are permanent and there is no basis to reverse`（1.3.5）类似，但 npm 连"申诉不存在"都没写，只写了用户的**承诺不再使用**。指向：第 591 行。

**(d) 名称类专属后果梯度（Disputes Policy，唯一有名字级梯度的部分）**
【原文】`Accounts violating the name squatting policy may be removed or renamed without notice. Attempts to sell, buy, or solicit other forms of payment in exchange for account names are prohibited and may result in permanent account suspension.`
来源：`R7/npm-disputes.txt`（`Squatting` 节）→ https://docs.npmjs.com/policies/disputes

【判断】**同一个 Squatting 行为内有两档后果**：单纯占名 → `removed or renamed without notice`；**倒卖名称** → `permanent account suspension`。**这是全部证据中唯一在规则正文里就地写出"行为变体 → 后果升级"的映射**（其他系统的升格都在执行说明或 tier 表里）。指向：同上。

**(e) 名称类行为的"品类差异化判定标准"（Disputes Policy 的核心结构）**
【原文】
```
Package names are considered squatted if the package has no genuine function.
Organization names are considered squatted if there are no packages published within a reasonable time. If an organization is a paid organization, it may have private packages that are invisible to third parties. For privacy reasons, we cannot reveal whether or not an organization has private packages, so a paid organization will never be considered squatted.
We are extremely unlikely to transfer control of a username, as it is totally valid to be an npm user and never publish any packages: for instance, you might be part of an organization or need read-only access to private packages.
```
来源：`R7/npm-disputes.txt`（`Packages` / `Organizations` / `Usernames` 三节）→ https://docs.npmjs.com/policies/disputes

【判断】**同一违规概念（squatting）在三个载体上有三套完全不同的判定标准**，且**付费组织被结构性豁免**（`a paid organization will never be considered squatted`）—— 理由是隐私（无法核实其是否有私有包）。**这是本报告唯一一例"因无法取证而导致某类主体被整体排除在规则适用范围外"的结构。** 指向：同上。

**(f) 唯一出现"永久"措辞的后果**：`permanent account suspension`（Disputes）。**npm 全库只在这一处用 `permanent`。** 指向：同上。

#### 1.4.6 变更历史

**npm 是全部证据中唯一把"变更历史"显式委托给 git 的系统，并且给出了源文件路径。**

**(1) 每个政策文档都有一段标准化的 `Changes` 节：**
【原文】`This is a living document and may be updated from time to time. Please refer to the [git history for this document](https://github.com/npm/documentation/blob/main/content/policies/unpublish.mdx) to view the changes.`
来源：`R7/npm-unpublish.txt`（`[Changes](#changes)` 节）→ https://docs.npmjs.com/policies/unpublish

【原文】`This is a living document and may be updated from time to time. Please refer to the [git history for this document](https://github.com/npm/documentation/blob/main/content/policies/security.mdx) to view the changes.`
来源：`R7/npm-security.txt`（`[Changes](#changes)` 节）→ https://docs.npmjs.com/policies/security

【判断】**两处都给出了精确的 `.mdx` 源文件路径**（`content/policies/unpublish.mdx`、`content/policies/security.mdx`）。**这是全部证据中唯一让读者能直接定位到规则源文件并查看提交历史的机制。** 对比：PyPI 底层也在 git（`psf/policies`）但**不暴露路径、不引导读者去看**（1.3.6）；AMO 暴露 GitHub 贡献者账号但不暴露文件路径；GitHub 完全不暴露。**npm 是唯一把 git 当作对外版本界面的系统。** 指向：上述两段。

**(2) 显式"最后更新日期" + "可查阅历史版本"（Terms 独有）**
【原文】`npm last updated these npm Open Source Terms on March 10, 2022. You can review prior versions at [https://github.com/npm/documentation/blob/main/content/policies/open-source-terms.mdx](https://github.com/npm/documentation/blob/main/content/policies/open-source-terms.mdx) .`
来源：`R7/npm-open-source-terms.txt` 第 517–519 行 → https://docs.npmjs.com/policies/open-source-terms

【判断】两个要素：
- **绝对日期**：`March 10, 2022`（格式 `月 日, 年`，与 PyPI 同格式，无版本号）
- **"历史版本可查"的明确指路**：`You can review prior versions at <git 路径>`

**(3) 变更通知机制（同文件）**
【原文】`npm may change these Terms and the additional terms for Paid Services in the future. npm will post changes on the Website with a new "last updated" date. If you have an Account, npm will notify you of changes by email to the address provided for your Account, by a message on the Website, or both. If you do not have an account, npm may notify you of changes by a general announcement via the Website, but it is up to you to check for changes to these Terms. After receiving notice of changes to these Terms, you must accept those changes to continue using npm Services. You accept changes to these Terms by continuing to use npm Services.`
来源：`R7/npm-open-source-terms.txt` 第 541 行 → 同一 URL

【判断】这套机制有 4 个结构件，**是本报告最完整的变更机制设计**：
1. **公示载体**：`a new "last updated" date`（页面上重写日期，不保留旧版于站内）
2. **通知分层**：有账号 → 邮件和/或站内消息；无账号 → 仅站内公告 + **举证责任在用户**（`it is up to you to check for changes`）
3. **同意机制**：`You accept changes ... by continuing to use npm Services`（**继续使用即同意**，消极同意）
4. **版本指引**：`You can review prior versions at <git 路径>`（第 517–519 行）

**对照 GitHub 的 `30 days' notice of material changes`（有通知期、无同意机制）、PyPI 的 supersession 横幅（有版本存档、无通知），npm 是唯一同时规定"通知 + 同意"但没有通知期的。** 指向：第 541 行 vs `R7/github-docs-tos-src.md` 第 40 行。

**(4) 许可与署名**
【原文】
```
Copyright (C) npm, Inc., All rights reserved

This document may be reused under a [Creative Commons Attribution-ShareAlike License](https://creativecommons.org/licenses/by-sa/4.0/).
```
来源：`R7/npm-unpublish.txt`（`[License](#license)` 节）、`R7/npm-disputes.txt`、`R7/npm-security.txt` 同一位置 → https://docs.npmjs.com/policies/unpublish

【判断】**CC-BY-SA 4.0**（带 ShareAlike），区别于 PyPI 的 CC-BY 4.0（无 ShareAlike）与 GitHub CG 的 CC0-1.0。**三份规则库三档许可强度：CC0（放弃）< CC-BY（署名）< CC-BY-SA（署名 + 传染）。** 同时明写 `All rights reserved` 与 CC 授权并置 —— 授权对象是**文档文本**，保留的是**公司权利**。指向：三份文件对应段落。

**(5) 无版本号**：npm 全库政策文档**均无 `version` 字段或版本号**，只有日期。指向：上述各处。

**(6) 未抓取的政策页**：`/policies/dual-use`（Dual Use Content）在全部 5 份证据文件的侧栏导航中出现，但本次抓取未取回该页正文；它**不是 404**，是未被列入抓取清单。见第 4 章。指向：`R7/npm-open-source-terms.txt` 第 241 行。
---

### 1.5 AWS

AWS 的结构是本报告中最极端的**两极结构**：对外行为规则只有 **6 条 bullet**（AUP），而服务级规则有 **110 个编号专章**（Service Terms）。两者不是"总则 + 细则"的关系，而是**两套平行且互不引用的规则集**。

#### 1.5.1 切了什么轴

**AUP 的轴 = 被侵害的法益类型，只有 6 条，全部在最高抽象层。**

【原文】
```
You may not use, or facilitate or allow others to use, the Services or the AWS Site:

for any illegal or fraudulent activity;

to violate the rights of others;

to threaten, incite, promote, or actively encourage violence, terrorism, or other serious harm;

for any content or activity that promotes child sexual exploitation or abuse;

to violate the security, integrity, or availability of any user, network, computer or communications system, software application, or network or computing device;

to distribute, publish, send, or facilitate the sending of unsolicited mass email or other messages, promotions, advertising, or solicitations (or "spam").
```
来源：`R7/aws-aup.txt` 第 267–279 行 → https://aws.amazon.com/aup/

【判断】**AWS AUP 只有 6 条规则，是本报告中规则条数最少的规则库。** 切轴是**被侵害的客体/法益**：法律秩序（illegal/fraudulent）、他人权利（rights of others）、人身安全（violence/terrorism）、未成年人（CSAM）、系统安全（security/integrity/availability）、通信秩序（spam）。**没有一条针对内容主题**（无 hate speech、无 nudity、无 misinformation、无 IP 单列）—— 与 GitHub 的 11 节、Meta 的 27 节形成数量级差异。指向：同上。

【判断】**AWS 是唯一一个以"不得使用（use）服务去做什么"为主句而非"不得发布什么内容"的规则库。** 主句为 `You may not use ... the Services or the AWS Site:`，其后全部是**目的状语**（`for any illegal...` / `to violate...` / `to threaten...`）。即**规则单元是"用途"，不是"内容"**。云端基础设施平台把规制对象定位为使用目的而非内容主题。指向：第 267 行。

**Service Terms 的轴 = 产品/服务，110 个编号专章。**

【原文】`1. Universal Service Terms (Applicable to All Services)` … `110. Free Exploration Services`
来源：`R7/aws-service-terms.txt` 第 263 行（第 1 章）至第 2442 行（第 110 章）→ https://aws.amazon.com/service-terms/

【判断】从 `2. Betas and Previews` / `3. Amazon CloudFront` / `4. AWS Outposts` / `5. Amazon Elastic Compute Cloud` … 直到 `110. Free Exploration Services`，**共 110 个一级编号章，几乎一服务一章**（`grep -cE '^[0-9]{1,3}\. [A-Z]'` = 110）。**这是全部证据中唯一的"按产品切轴"规则库。** 指向：`R7/aws-service-terms.txt` 全文编号章清单。

【判断】**第 1 章是唯一跨服务章**（`Universal Service Terms (Applicable to All Services)`），第 2–110 章各自只作用于一个产品。**作用域由"你落在哪一章"决定，而不是由规则内的限定词决定** —— 这是作用域表达的最强形式（文档级排他）。指向：第 263 行 + 后续各章标题。

**AWS 独特的多文档分工（Legal 索引页给出）：**
【原文】
```
[AWS Customer Agreement](/agreement/) – this agreement governs your use of our services
[AWS Service Terms](/serviceterms/) – these additional terms apply to your use of specific services
[AWS Service Level Agreements](/legal/service-level-agreements/) – these service level agreements apply to your use of specific services
[AWS Acceptable Use Policy](/aup/) – this policy describes prohibited uses of our services
[AWS Trademark Guidelines](/trademark-guidelines/) – this page describes the guidelines for using certain of our trademarks and other designations
[AWS Site Terms](/terms/) – these terms govern your use of the AWS website
[Privacy Notice](/privacy/) – this notice describes how information about you is used and shared
```
来源：`R7/aws-legal-index.txt` 第 268–290 行 → https://aws.amazon.com/legal/

【判断】AWS 的切轴是**"文档职能"**：合同（Customer Agreement）/ 服务附加条款（Service Terms）/ 服务水平（SLA）/ 禁止用途（AUP）/ 商标 / 网站条款 / 隐私。**每个职能一份文档，互不重叠。** 对比 GitHub 的 6 分组（文档性质）与 npm 的 14 项（主题 + 合同混合）—— **AWS 是最纯粹的"按法律职能切轴"。** 指向：同上。

⚠️ **注意**：`R7/aws-legal-index.txt` 的索引里另有若干**按法域命名的独立文档**，这是"法域 → 独立文档"的直接证据：
【原文】
```
[AWS Korea Telco](/legal/amcskr/) – this page provides information about AMCS Korea
[AWS India Grievance Officer](/legal/aispl-grievance-officer/) – this page provides information about the grievance officer
[Sharing of Customer's Personal Information in Compliance with The Act on the Protection of Personal Information in Japan](/legal/shipping-of-personal-information-japan/)
[AWS Indonesia Consumer Information](/legal/notice-to-customers-of-pt-amazon-web-services-indonesia/) – this page provides information for customers of PT Amazon Web Services Indonesia
```
来源：`R7/aws-legal-index.txt`（Legal links 列表）→ https://aws.amazon.com/legal/

【判断】**韩国 / 印度 / 日本 / 印尼各有一份法域专属文档**，而美国、欧洲、澳洲没有对应文档。**AWS 的法域差异以"是否为该法域单开一份文档"来表达，不在规则内加限定词。** 这是"作用域 → 文档存在性"的表达方式。指向：同上清单。

#### 1.5.2 一条规则的内部结构

**AUP 的规则单位 = 无编号的目的状语从句，比 GitHub 更短。**

【判断】AUP 的 6 条规则**没有主语、没有编号、没有链接、没有示例**，最短一条仅 5 个词（`for any illegal or fraudulent activity;`）。**规则内部结构 = `for/to + 目的短语`，零元数据。** 是全部证据中信息量最低的单条规则形态。指向：`R7/aws-aup.txt` 第 269–279 行。

**Service Terms 的规则单位 = 十进制编号条款，且这个编号是可引用的稳定标识符。**

【原文】`1.1. You may not transfer outside the Services any software (including related documentation) you obtain from us or third party licensors in connection with the Services without specific authorization to do so.`
来源：`R7/aws-service-terms.txt` 第 269 行 → https://aws.amazon.com/service-terms/

【判断】**AWS 是全部证据中唯一其条款编号在正文中被反复当作引用标识使用的系统。** 证据：`8.3.2. This Section applies to data provided by monitors in your AWS account`（第 583 行，条款自指）、`5.5.2. EC2 Capacity Blocks for ML.`（第 535 行，条款内嵌条款名）。**即「8.3.2」这样的编号是规则 ID。** 对比：GitHub 无编号、PyPI 无编号、npm 无编号、Meta 无编号、AMO 有编号但从不自引。指向：第 583、535 行。

**AWS 独有：条款内含"定义 + 门槛 + 程序 + 时限 + 后果 + 例外 + 累犯"九件套。** 第 1.4 条是全文结构最完整的单条规则：

【原文】`In connection with your use of the Services, you are responsible for maintaining licenses and adhering to the license terms of any software you run. If we reasonably believe any of Your Content violates the law, infringes or misappropriates the rights of any third party, or otherwise violates a material term of the Agreement (including the Service Terms, or the Acceptable Use Policy) ("Prohibited Content"), we will notify you of the Prohibited Content and may request that such content be removed from the Services or access to it be disabled. If you do not remove or disable access to the Prohibited Content within 2 business days of our notice, we may remove or disable access to the Prohibited Content or suspend the Services to the extent we are not able to remove or disable access to the Prohibited Content. Notwithstanding the foregoing, we may remove or disable access to any Prohibited Content without prior notice in connection with illegal content, where the content may disrupt or threaten the Services or in accordance with applicable law or any judicial, regulatory or other governmental order or request. In the event that we remove Your Content without prior notice, we will provide prompt notice to you unless prohibited by law. We terminate the accounts of repeat infringers in appropriate circumstances.`
来源：`R7/aws-service-terms.txt` 第 277 行（第 1.4 条）→ https://aws.amazon.com/service-terms/

【判断】这一条内部有 **9 个结构件**，是本报告单条规则中最多的：
1. **义务前置句**（维护许可）
2. **判据与门槛**：`we reasonably believe`（合理相信）
3. **术语定义**：`("Prohibited Content")` —— 定义与构成要件合并
4. **第一步程序**：`we will notify you ... and may request that such content be removed`
5. **整改期 + 硬时限**：`within 2 business days of our notice`
6. **逾期后果**：`we may remove or disable access ... or suspend the Services`
7. **例外与免通知情形**：`Notwithstanding the foregoing ... without prior notice in connection with illegal content, where the content may disrupt or threaten the Services or in accordance with applicable law or any judicial, regulatory or other governmental order`
8. **事后通知义务**：`we will provide prompt notice to you unless prohibited by law`
9. **累犯政策**：`We terminate the accounts of repeat infringers in appropriate circumstances`

**这 9 件套是全部证据中最完整的"单条规则内部结构"。** 指向：第 277 行。

【判断】**`2 business days` 是全部证据中唯一的"法定整改期数字"**（其余系统的整改期都是 `a reasonable time frame` 之类）。同时 `Notwithstanding the foregoing` 是**唯一在系统内部用作固定例外引导词的标记**（`R1/meta-cs-STRUCTURE-INVENTORY.md` 脚注 1 指出 Meta 全站 27 个 section 中只有 2 个含 `Notwithstanding`）。指向：第 277 行。

【判断】**"累犯终止"条款（repeat infringer policy）是 AWS 独有**：`We terminate the accounts of repeat infringers in appropriate circumstances.` —— GitHub/Meta/YouTube 用"strike 累积/tier"表达重复违规，**AWS 用一句法定化的"累犯即终止"**（措辞直接对应 DMCA 的 repeat infringer 义务）。指向：第 277 行末句。

**另一种规则形态：`You may not:` + 编号子清单**（第 5 章 Microsoft 软件许可）：
【原文】
```
The Microsoft Software is neither sold nor distributed to you, and you may use it solely in conjunction with the Services. You may not transfer or use the Microsoft Software outside the Services. You may not remove, modify, or obscure any copyright, trademark, or other proprietary rights notices that are contained in or on the Microsoft Software. You may not reverse engineer, decompile, or disassemble the Microsoft Software, except to the extent expressly permitted by applicable law.
```
来源：`R7/aws-service-terms.txt` 第 475–481 行 → 同一 URL

【判断】**AWS 在服务专章里内嵌"分列表"结构**：章 → 条 → `You may not:` 引导的子列表。**层级比 AUP 深一层。** 指向：第 475–481 行。

**AWS 独有：产品能力边界的"设计意图声明"（不是禁止，是边界 + 免责）。**
【原文】`Amazon WorkSpaces is designed to serve as a cloud desktop service. WorkSpaces may not be used to accept inbound network connections, as server instances, or to serve web traffic or your network traffic, and you may not reconfigure the inbound network connections of your WorkSpaces.`
来源：`R7/aws-service-terms.txt` 第 1060 行（第 26.3 条）→ 同一 URL

【原文】`AWS IoT SiteWise Scenario Discovery is not designed to enable real-time vehicle control or transmission of operational commands to vehicles, and is not intended to be used by itself for any direct integration into any vehicle or vehicle system or for any regulatory submission. AWS is not responsible for any such uses.`
来源：`R7/aws-service-terms.txt` 第 1306 行（第 39.14 条）→ 同一 URL

【判断】**规则结构 = `X is designed to ...` + `may not be used to ...` + `AWS is not responsible for any such uses`** —— 即**"产品定位声明 + 越界禁止 + 责任排除"三连**。合规判据是**产品是否被用于其设计用途**，而不是内容危害。这是基础设施平台特有的规则构造。指向：第 1060、1306 行。

**AWS 独有：AI 训练用途的横切限制（同一句式在 3 个不同服务章重复）**
【原文】`Except where permitted by Amazon Bio Discovery, you may not use Amazon Bio Discovery to generate Content for the express purpose of training an AI model or service or developing a substantially similar AI model or service.`（第 1002 行，第 22.5 条）
【原文】`Except where permitted by Amazon Connect Talent, you may not use Amazon Connect Talent to generate Content for the express purpose of training an AI model or service or developing a substantially similar AI model or service.`（第 1320 行，第 40.5 条）
【原文】`Except where permitted by the AI Service, you may not use an AI Service to generate Content for the express purpose of training an AI model or service or developing a substantially similar AI model or service.`（第 1512 行，第 50.5 条）
来源：均出自 `R7/aws-service-terms.txt` → https://aws.amazon.com/service-terms/

【判断】**同一个"禁止用生成内容训练竞品模型"规则被逐字复制到每一个 AI 服务专章**（第 22.5、40.5、50.5 条，句式与用词完全一致，只替换服务名）。**这是"按产品切轴"结构的直接代价：横切关切必须逐章重复，无法集中表达。** 对比 Meta/Google 用统一类目 + 法域表表达横切关切（见 1.8、1.9）。**这是本报告最重要的结构性代价发现之一。** 指向：上述三行（同一句式至少出现 3 次）。

#### 1.5.3 作用域如何表达

**(a) 服务作用域 —— 由"章节编号"表达（最强形式）**
【原文】`1. Universal Service Terms (Applicable to All Services)`
来源：`R7/aws-service-terms.txt` 第 263 行 → https://aws.amazon.com/service-terms/

【判断】AWS 的作用域**不是规则内的限定词，而是规则所在的章号**：落在第 1 章的规则全域适用，落在第 5 章的规则只适用于 EC2，落在第 92 章只适用于 Clean Rooms。**作用域 = 分区，规则不重复声明。** 这是全部证据中最干净的"作用域外置"设计。指向：第 263 行 + 后续 110 章。

**(b) 法域作用域 —— 唯一的国家→签约主体映射表**
【原文】
```
| Account Country | AWS Contracting Party | Facsimile | Mailing Address |
| Australia (w.e.f. 1 October 2022) | Amazon Web Services Australia Pty Ltd (ABN: 63 605 345 891) | N/A | Level 37, 2-26 Park Street, Sydney, NSW, 2000, Australia |
| Japan (w.e.f. 1 October 2022) | Amazon Web Services Japan G.K. | N/A | 1-3-1 Azabudai, Minato-ku, Tokyo 106-0041, Japan |
| South Korea (w.e.f. 1 April 2025) | Amazon Web Services Korea LLC | N/A | L12, East tower, 231, Teheran-ro, Gangnam-gu, Seoul, 06142, Republic of Korea |
| The countries within Europe, the Middle East, and Africa (except South Africa and Turkey) listed at ... (w.e.f. 1 January 2022) | Amazon Web Services EMEA SARL | 352 2789 0057 | 38 Avenue John F. Kennedy, L-1855, Luxembourg |
| India (for transactions between buyers and third party providers incorporated in India) (w.e.f. 1 October 2025) | Amazon Web Services India Private Limited | 011-47985609 | Unit Nos. 1401 to 1421 International Trade Tower, Nehru Place, Delhi 110019, India |
| Any other country that is not listed in this table above | Amazon Web Services, Inc. | 206-266-7010 | 410 Terry Avenue North, Seattle, WA 98109-5210 U.S.A. |
```
来源：`R7/aws-service-terms.txt` 第 825–951 行 → https://aws.amazon.com/service-terms/

【判断】这是**全部证据中唯一的"国家 → 规则适用主体"映射表**，包含 8 个结构要点：
1. **维度是账户所在国**（`Account Country`），不是用户国籍、不是内容来源地。
2. **映射目标是"签约法人主体"**（`AWS Contracting Party`），即**法域差异被转化为"你与哪个实体签约"**，不是"适用哪套规则内容"。
3. **每个条目带生效日期**（`w.e.f. 1 October 2022` 等，格式 `w.e.f. D Month YYYY`），即**表的每一行可以独立于其他行生效**。
4. **有默认行 / 兜底行**：`Any other country that is not listed in this table above` → `Amazon Web Services, Inc.`。**这是本报告唯一带显式"其他"兜底行的表。**
5. **一行的值可以是一组国家**（EMEA），且该组通过**外链到另一个页面**（`/legal/aws-emea-countries/`）定义 —— **即"国家列表"被外置成独立文档，不内嵌。**
6. EMEA 行带**排除项**：`except South Africa and Turkey`。
7. EMEA 行带**脚注**：`1 This applies only if your purchase on AWS Marketplace is from a third party that has been onboarded to Amazon Web Services EMEA SARL. Otherwise, Amazon Web Services, Inc. is the applicable AWS Contracting Party.` —— **即同一账户国可能因交易对手不同而落在不同主体上，表本身不足以决定作用域。**
8. India 行带**交易类型限定**：`for transactions between buyers and third party providers incorporated in India`。

指向：第 825–951 行。

【判断】**该表只服务于 AWS Marketplace 章节（第 20 章），不是全站通用机制。** 引导句为 `For purposes of facilitating your purchases from third parties on AWS Marketplace, the applicable AWS Contracting Party under the Agreement is set out in the table below.`（第 825 行）。**即 AWS 只在"跨境交易"场景才把国家维度显式化。** 指向：第 825 行。

**(c) 与签约主体相关的另一处作用域（跨主体合并）**
【原文】`To benefit from any contract with AWS enabling you to use AWS Services under the same terms as your affiliate's Agreement solely because your accounts are joined as Member Accounts of their Organization (as defined in the AWS Organizations section below), your AWS Contracting Party must be a signatory to your affiliate's Agreement.`
来源：`R7/aws-service-terms.txt` 第 387 行（第 1.27 条）→ 同一 URL

【判断】**组织合并（Organizations）会让规则作用域跨主体延伸，而 AWS 明确设了一个"同签约主体"前提条件来封堵。** 这是"作用域随法人结构变化"的显式规则。指向：第 387 行。

**(d) 地区/区域作用域（特殊受管区域）**
【原文】`18. AWS GovCloud (US) Service Terms`
来源：`R7/aws-service-terms.txt` 第 797 行 → 同一 URL

【判断】**GovCloud 作为独立章存在，意味着"美国政府专用区域"的规则差异靠独立章承载，而非在通用章内加限定词。** 与 (a) 的分区策略一致。指向：第 797 行。

**(e) 法域作为"资格条件 + 举证义务"**
【原文】`Non-U.S.-based entities may not be Sellers without providing the Form W-8BEN (Certificate of Foreign Status of Beneficial Owner for United States Tax Withholding) to establish that you are not a U.S. person.`
来源：`R7/aws-service-terms.txt` 第 539 行（第 5.6.1 条）→ 同一 URL

【判断】**用法域（美国/非美国）直接作为"资格条件"**：非美国实体本是允许的，但须以税务表格自证身份。**这是"法域 → 举证义务"而非"法域 → 规则内容"的又一种模式。** 指向：第 539 行。

#### 1.5.4 兜底/其他类目

**AWS AUP 没有"其他"类目，也没有任何兜底条款。** 6 条规则之后即进入 `Investigation and Enforcement` 节。

【原文】`We may investigate any suspected violation of this Policy, and remove or disable access to any content or resource that violates this Policy. You agree to cooperate with us to remedy any violation.`
来源：`R7/aws-aup.txt` 第 283 行 → https://aws.amazon.com/aup/

【判断】**兜底功能由"宽泛的抽象判据"承担，而非专门的兜底条款。** 例：`for any illegal or fraudulent activity` / `to violate the rights of others` / `or other serious harm` —— 这三条本身就是无边界判据。**AWS 不需要兜底条款，因为它的 6 条规则全都是兜底级的抽象。** 这是"抽象度换兜底"的结构策略（对比 GitHub：具体规则 + 显式兜底条）。指向：`R7/aws-aup.txt` 第 269–279 行。

**唯一的开放式枚举尾**：
【原文】`to threaten, incite, promote, or actively encourage violence, terrorism, or other serious harm;`
来源：`R7/aws-aup.txt` 第 273 行 → 同一 URL

【判断】`or other serious harm` 是 AUP 里唯一一处 `or other X` 式开放性枚举尾。**其余 5 条都以具体名词收束，无开放尾。** 指向：第 273 行。

**Service Terms 中的"非标准服务"覆盖**：第 2 章 `Betas and Previews` 与第 110 章 `Free Exploration Services` 承担"非商业标准服务"的覆盖职责，但**不是兜底类目，而是命名类目**。指向：`R7/aws-service-terms.txt` 第 413、2442 行。

#### 1.5.5 严重等级/后果

**AWS AUP 完全不设等级，且在"违规认定"上引入了一个其他系统都没有的裁量因素。**

【原文】`When determining whether there has been a violation of this Policy, we may consider your ability and willingness to comply with this Policy, including the policies and processes you have in place to prevent or identify and remove any prohibited content or activity.`
来源：`R7/aws-aup.txt` 第 285 行 → https://aws.amazon.com/aup/

【判断】**这是全部证据中唯一把"你有没有合规制度"作为违规认定因素的系统。** 判据不是"内容/行为有多严重"，而是 **`your ability and willingness to comply`**（能力 + 意愿）+ **`the policies and processes you have in place`**（是否建立了流程）。**即：AWS 把"是否违规"部分转化为"你是否具备合规能力与流程"的组织能力审查。** 指向：第 285 行。

**后果档数 = 2（AUP 层），全部是内容级**
【原文】`We may investigate any suspected violation of this Policy, and remove or disable access to any content or resource that violates this Policy.`
来源：`R7/aws-aup.txt` 第 283 行 → 同一 URL

【判断】AUP 只写了两项动作：`remove` / `disable access to`，且都是**内容或资源级**，**AUP 全文不提账号封禁**。账号级后果（`suspend the Services`）只在 Service Terms 第 1.4 条出现。**即：AWS 把"对外宣称的后果"（AUP）压到最低，把真正的执行权限留在合同性文档里。** 指向：`R7/aws-aup.txt` 第 283 行 vs `R7/aws-service-terms.txt` 第 277 行。

**AWS 的后果序列（Service Terms 第 1.4 条）= 本报告最完整的分段阶梯：**

| 阶段 | 触发条件 | 后果 | 通知 |
|---|---|---|---|
| 1 | `we reasonably believe` 存在 Prohibited Content | `may request that such content be removed ... or access ... disabled` | `we will notify you` |
| 2 | 用户未在 `2 business days` 内整改 | `we may remove or disable access ... or suspend the Services` | 已通知 |
| 3 | 违法内容 / 内容可能扰乱或威胁服务 / 依法或依司法、监管、政府命令 | `may remove or disable access ... without prior notice` | **免前置通知**，但 `we will provide prompt notice to you unless prohibited by law` |
| 4 | 累犯 | `We terminate the accounts of repeat infringers` | 未规定 |

来源：`R7/aws-service-terms.txt` 第 277 行 → https://aws.amazon.com/service-terms/

【判断】
- **档数 = 4 段**，是全部证据中唯一**按"程序阶段 + 时限"分档**（而非按违规类型或严重度分档）的后果结构。
- 分档变量是三个：**是否配合整改 / 是否为违法内容或服务风险 / 是否累犯**。
- **"服务级暂停"（`suspend the Services`）是本报告粒度最大的后果**：不是封账号，而是**暂停整个云服务**。指向：上述表格。

**其他服务章内嵌的专属后果**（示例）：
【原文】`if you do, we may throttle or suspend your data services or suspend your account.`
来源：`R7/aws-service-terms.txt` 第 1628 行（第 51.3 条，Lightsail 数据费规避）→ 同一 URL

【判断】这是后果的**第三种粒度：`throttle`（限速）**。AWS 在服务章里可以定义该服务特有的后果档（限速 / 暂停数据服务 / 暂停账号），**这些档不存在于 AUP，也不存在统一的后果词汇表** —— 是"按产品切轴"结构的又一后果。指向：第 1628 行。

**另有一处罚款/收费式后果（唯一与费用挂钩的后果）**：
【原文】`if we terminate the Agreement other than for cause, terminate an individual EC2 Reserved Instance or EC2 Dedicated Host Reservation type, or terminate the Savings Plans, EC2 Reserved Instance or EC2 Dedicated Host pricing program(s), we will refund you a pro rata portion of any up-front fee paid`
来源：`R7/aws-service-terms.txt` 第 529 行（第 5.4.2 条）→ 同一 URL

【判断】AWS 的部分后果带**退款条款**（按比例退还预付费）。**这是全部证据中唯一把"后果"与"金钱补偿"绑定的规则** —— 因为被终止的服务是预付费资源。其余系统（内容平台）的后果都不涉及退款。指向：第 529 行。

#### 1.5.6 变更历史

**AWS 只有"最后更新日期"一行，无版本号、无历史版本、无 diff、无通知期承诺。**

【原文】`Last Updated: July 1, 2021`
来源：`R7/aws-aup.txt` 第 261 行 → https://aws.amazon.com/aup/

【原文】`Last Updated: September 11, 2026`
来源：`R7/aws-service-terms.txt` 第 261 行 → https://aws.amazon.com/service-terms/

【判断】两处日期格式为 `Month D, YYYY`（与 PyPI/npm 同格式）。**AUP 的最后更新停在 2021-07-01，而 Service Terms 更新到 2026-09-11 —— 相隔 5 年。** 这一对比是结构性的：**AWS 把变更集中在 Service Terms（服务章），AUP 层已冻结。** 指向：上述两行。

**变更机制条款（三句话，全部在 AUP 导语）**
【原文】`This Acceptable Use Policy ("Policy") governs your use of the services offered by Amazon Web Services, Inc. and its affiliates ("Services") and our website(s) including [http://aws.amazon.com](/) ("AWS Site"). We may modify this Policy by posting a revised version on the AWS Site. By using the Services or accessing the AWS Site, you agree to the latest version of this Policy.`
来源：`R7/aws-aup.txt` 第 263–265 行 → https://aws.amazon.com/aup/

【判断】变更机制三件套，**是本报告最简的版本机制**：
1. **变更方式**：`by posting a revised version on the AWS Site`（**就地覆盖**）
2. **同意方式**：`By using the Services or accessing the AWS Site, you agree to the latest version`（**使用即同意**，同 npm）
3. **通知期**：**无。既无 `30 days' notice`（GitHub），也无邮件/站内通知分层（npm）。**

**AWS 是全部系统里变更机制最薄的一档：无通知期、无通知渠道、无历史版本、无 git 链接、无 supersession 记录。唯一的信息是页顶一行日期。** 指向：第 263–265 行 + 第 261 行。

**一处隐含的版本痕迹（术语层，非规则版本）**：
【原文】`For purposes of these Service Terms, "Your Content" includes any "Company Content" and any "Customer Content," and "AWS Content" includes "Amazon Properties."`
来源：`R7/aws-service-terms.txt` 第 265 行 → https://aws.amazon.com/service-terms/

【判断】这句显示 AWS 文本中**残留了旧术语**（`Company Content` / `Amazon Properties` 是历史用词），通过"术语并入"条款把旧词映射到现行框架。**这是全部证据中唯一一处可从术语叠层读出历史遗留的文本。** 指向：第 265 行。
---

### 1.6 Stripe（支付侧 · 受限业务清单）

Stripe 是本报告**唯一一个把"国家 × 品类"作为一等规则维度**的系统。对所有做跨境电商的读者，这一节的作用域结构比前面所有开放平台都更同构。

#### 1.6.1 切了什么轴

**主轴 = 准入资格等级（prohibited / restricted），次轴 = 国家，第三轴 = 产品。**

页面的 `How to use this page` 节把全页切分列成 6 个具名区：

【原文】
```
High-risk jurisdictions and persons
Prohibited businesses
Industries that can't use Stripe, and products Stripe doesn't support.
Restricted businesses
Industries and products that require additional due diligence.
Jurisdiction-specific prohibited businesses
Countries that have specific prohibitions.
Prohibited uses of Stripe products
Stripe may never be used for certain activities, regardless of the industry.
Prohibitions for Stripe Issuing products
Prohibitions related to the use of issuing products.
Stripe Capital restricted business types
Restricted businesses for Stripe Capital Products
```
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 48–59 行 → https://stripe.com/legal/restricted-businesses

【判断】**这是一个真正的多轴规则库**，四个轴各自独立：
1. **主体/地域轴**（High-risk jurisdictions and persons）—— 按"人/地区"禁
2. **行业轴**（Prohibited businesses / Restricted businesses）—— 按"做什么生意"禁
3. **国家轴**（Jurisdiction-specific prohibited businesses）—— 按"在哪个国家"禁
4. **产品轴**（Prohibited uses / Issuing / Capital）—— 按"用哪个 Stripe 产品"禁

**同一个业务可以在轴 2 是允许的、在轴 3 被某国禁止、在轴 4 被某个产品禁止 —— 四轴的结果需要叠加。** 指向：同上。

【判断】**"Prohibited" 与 "Restricted" 的分野不是严重度，而是"是否需要额外尽调"**。原文对 Restricted 的定义是 `Industries and products that require additional due diligence`（需额外尽调），对 Prohibited 的定义是 `Industries that can't use Stripe, and products Stripe doesn't support`（不能用/不支持）。**即分档依据是"程序门槛"而非"危害程度"。** 指向：第 50–53 行。

**轴 3（国家）的展开方式是"一国家一节"**（第 228 行起），共 12 个国家/地区：Brazil / Canada / India / Indonesia / Japan / Malaysia / Mexico / Singapore / Thailand / United Arab Emirates / United States（另加 High-risk jurisdictions 中的国名清单）。指向：第 228–357 行。

#### 1.6.2 一条规则的内部结构

**规则单位 = 无编号的商品/服务名词短语**，比 GitHub 的 bullet 更短，且**规则句本身不含判据**。

【原文】
```
Brazil
Genital and nipple jewelry
Genital prosthetics
Sex accessories and lifelike sex toys
Canada
Alcohol (Restricted)
Mortgage consulting
```
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 229–235 行 → https://stripe.com/legal/restricted-businesses

【判断】**Stripe 的规则单元是一个"品类名"，没有任何谓语、判据、条件。** 判据由**所在小节**提供（在 Prohibited Businesses 节下的品类即禁止；在 Restricted Businesses 节下的即需尽调；在某国小节下的即该国特有）。**这是"轴即判据"的极端形式：规则文本只说"是什么"，不说"会怎样"。** 指向：同上。

**两种国家节的格式（同一维度的两套表达）：**

格式 A —— **纯列表，不加标签**（Brazil / Canada / India / Japan / Malaysia / Mexico / Singapore / UAE / US）：
【原文】
```
India
Airbags
Alcohol
Captive insurance companies
Cash couriers
Charities
Chit funds
Cross-border jewelry sales
Currency exchange
...
Unlicensed financial institutions
Vehicle sales
```
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 238–258 行 → 同一 URL

格式 B —— **列表前加图例行，逐项内联 P/R 标签**（Indonesia / Thailand）：
【原文】
```
Indonesia
(Prohibited = P, Restricted = R)
Alcohol R
Domestic charter air travel P
Insurance R
Live chat / streaming R
Live stock R
Packaged food and cosmetics R
Pilgrimage / Umrah tour packages R
Precious metals and jewelry R
Products requiring national-standard certification R
```
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 260–271 行 → 同一 URL

【原文】
```
Thailand
(Prohibited = P, Restricted = R)
Alcohol P
Bodyguard services P
Charities P
Dating services P
Domestic charter air travel R
Food and cosmetics R
Historical artifacts P
Hotels, tour operators, and transportation services R
Insurance R
New vehicle sales P
Private investigators or detective agencies P
Psychic services and fortune tellers P
Timeshares P
Vehicle sales P
Vitamins P
```
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 322–338 行 → 同一 URL

【判断】**同一份文档里，国家维度用了两种互不兼容的表达**：格式 A 的国家（如 India）把"prohibited"编码进**章节归属**（因为它们在 `Jurisdiction-specific prohibited businesses` 标题下），格式 B 的国家（Indonesia / Thailand）把"prohibited vs restricted"编码进**行内单字母标签**（`P` / `R`），并用一行图例 `(Prohibited = P, Restricted = R)` 声明。

**为什么两种？** 因为 Canada 节里出现了 `Alcohol (Restricted)` —— 括注式，第三种写法。**Stripe 在国家维度上同时存在三种档位表达（章节归属 / 括注 / 单字母标签），没有统一方案。** 指向：第 235 行（Canada 括注）、第 260–271 行（Indonesia 标签）、第 322–338 行（Thailand 标签）。

**【判断】最重要的一条：同一品类在不同国家有不同的档位。** `Domestic charter air travel` 在本页出现 5 次以上：
- Indonesia：`Domestic charter air travel P`（禁止）
- Malaysia：`Domestic charter air travel`（在禁止节下）
- Mexico：`Domestic charter air travel`（在禁止节下）
- Singapore：`Domestic charter air travel`（在禁止节下）
- Thailand：`Domestic charter air travel R`（受限）

**同一个商品名，跨 5 个国家，档位从 P 到 R 到"未列出"。** 指向：第 263、290、297、313、328 行。

**另一条同构证据**：`Genital prosthetics` 出现在 Brazil / India / Japan / Malaysia / Mexico / Singapore / UAE 七国节的禁止清单中，**但不在 Canada、Indonesia、Thailand 的清单里**。指向：第 230、245、281、291、298、313、343 行。

#### 1.6.3 作用域如何表达（本节最关键）

**Stripe 是本报告中唯一把"作用域"表达为"在同一页上并列的多个国家节"的系统 —— 作用域 = 你在读哪一节。**

**(a) 国家作用域的三种机制**

**机制 1：独立国家节**（框架性、枚举式）—— 见 1.6.1 轴 3。

**机制 2：规则条目内联国家白/黑名单**（用于 Restricted Businesses 节）：
【原文】
```
Equity crowdfunding (Limited availability: Please contact our sales team if you would like to work with Stripe. Note: Supported in Australia, Germany, France, Singapore, the United Kingdom, and the United States. Prohibited in all other countries.)
Charity sweepstakes and raffles for the explicit purpose of fundraising (Note: Supported in Australia, Brazil, Canada, Hong Kong, Ireland, Mexico, the United Kingdom, and the United States. Prohibited in all other countries.)
Organizations fundraising for a charitable purpose (Note: Supported in Australia, Canada, the United Kingdom, and the United States. Prohibited in all other countries.)
```
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 178–180 行 → https://stripe.com/legal/restricted-businesses

【判断】**这是"单一品类 → 支持国白名单 + 兜底全禁"的完整句式模板**：
```
<品类名> (Note: Supported in <国家列表>. Prohibited in all other countries.)
```
三要素齐备：**白名单（Supported in ...）+ 默认规则（Prohibited in all other countries）+ 无须穷尽枚举黑名单**。**这是本报告中最紧凑的"国家作用域"表达**：一条规则内嵌一张国家表，且有显式默认值。指向：第 178–180 行。

【判断】对照 AWS 表格（1.5.3b）：**AWS 用"表 + 尾行兜底"；Stripe 用"括注 + 尾句兜底"。同一逻辑，两种载体。** 而 GitHub/PyPI/npm/Meta/YouTube **完全没有这个机制**。指向：`R7/aws-service-terms.txt` 第 825–951 行 vs 本节第 178–180 行。

**机制 3：法律转致（把判据交给当地法）**：
【原文】`Any other products or services that are in violation of law in the jurisdictions where your business is located or to which your business is targeted`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 84 行 → 同一 URL

【判断】**这是一条"作用域自指"的兜底条**：判据 = `law in the jurisdictions where your business is located or to which your business is targeted`（你的营业地法 + 你的目标市场法）。**即规则文本不枚举任何国家，而是把"哪些国家"交给读者自答。** 这是"法域 → 转致"而非"法域 → 枚举"的模式（对比 GitHub/PyPI 的"你负责遵守一切适用法"，措辞更精确：加了"目标市场"这一维度）。指向：第 84 行。

**(b) 俄罗斯相关：一个"国家 → 品类"的成组禁令**
【原文】`Export, re-export, sell, or supply accounting services; trust and corporate formation services; management consulting services; architecture services; engineering services; quantum computing services; information technology (IT) consultancy and design services; and IT-support services and cloud-based services for enterprise management software and design and manufacturing software to any person located in Russia. In the European Union and the United Kingdom, it is prohibited to use Stripe's products and services, directly or indirectly, to provide credit-rating services, market research and public relations services, advertising services, auditing services, or legal advisory services to any person located in Russia.`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 69 行 → 同一 URL

【原文】`Deal in any goods prohibited by law for export to or import from Russia (for example, luxury goods, sensitive goods included in the Common High Priority Items List, enterprise management software and design software).`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 71 行 → 同一 URL

【判断】**同一个目标国（俄罗斯），规则内容按"服务类型"分两套，且第二套只在 `In the European Union and the United Kingdom` 生效。** 即**"目标国 × 实施主体所在法域"是二维的** —— 不是"俄罗斯禁止什么"，而是"EU/UK 主体对俄罗斯禁止什么"。**这是本报告最精细的一处法域规则结构**：禁止的对象国与施加义务的法域被同时表达。指向：第 69 行。

**(c) 高风险的"人"维度（非国家）**
【原文】`Persons Stripe has determined for various reasons, including legal, contractual, and commercial reasons, to be prohibited, such as those individuals or entities named to a restricted person or party list of, or otherwise restricted by, the United States, United Kingdom, European Union, or United Nations, including the sanctions maintained by the US Office of Foreign Assets Control or the Denied Persons List or Entity List maintained by the US Department of Commerce.`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 66 行 → 同一 URL

【判断】**作用域被扩展到"人"（natural persons / entities），且判据是四个法域的制裁名单（US / UK / EU / UN），并逐一点名具体名单（OFAC / Denied Persons List / Entity List）。** 这是本报告唯一同时点名 4 个法域名单体系的作用域条款。指向：第 66 行。

**(d) 产品维度的"法域一致性"义务（独有）**
【原文】`When you sign up for Stripe Issuing, you share with Stripe the location of your business, the physical address of your beneficial owners , and the jurisdiction in which your business is registered. Stripe requires that the physical location of your business, its jurisdiction of registration, and the physical address of at least one of your beneficial owners all match. Furthermore, you must use Issuing cards primarily in the same jurisdiction.`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt`（Prohibitions for Stripe Issuing products → International use）→ 同一 URL

【原文】`As a user of Stripe Issuing, you must comply with our US compliance guidelines (or see the EU- and UK-specific guidelines )`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt`（Prohibitions for Stripe Issuing products → Noncompliance）→ 同一 URL

【判断】两条独有结构：
1. **"法域一致性"要求**：营业地 / 注册地 / 实益所有人地址**三者必须一致**，且用卡也须在同一法域。**这是"法域"从"适用哪套规则"变成"必须落在同一法域"的结构**——法域成为**合规实体属性**，而非规则选择器。
2. **默认法域 + 分册例外**：默认 `our US compliance guidelines`，EU/UK 另有专册（`the EU- and UK-specific guidelines`）。**默认美国 + 分册例外**，与 GitHub 的点名美国策略同构但更明确（因为它给出了例外分册的入口）。

指向：同上两段。

**(e) 文档级的"国家 × 语言"矩阵（Stripe legal 索引）**
【原文】
```
Mainland China (English)
Australia
English
Austria
Deutsch
English
Belgium
Nederlands
Français
Deutsch
English
Brazil
Português
English
Bulgaria
English
Canada
English
Français
```
来源：`_evidence/R7/marketplace/stripe-legal-index.txt` 第 30–47 行 → https://stripe.com/legal

【判断】**Stripe 的法务文档索引按"国家 → 可用语言"组织**，且**同一国家可有多种语言版本**（Belgium 四种、Canada 两种、Austria 两种、Brazil 两种）。**即"国家"是文档导航的第一维，"语言"是第二维。** 这是全部证据中唯一把国家作为**文档导航维度**（而非规则内容维度）的结构。指向：同上。

【判断】Stripe legal 导航另列出两个横向文档族：`Regional Regulatory Disclosures & Policies` 与 `Translations`（第 24–25 行）—— **"地区监管披露"是独立文档族**，即**地区维度的规则被集中在专门文档里，而不是散落在主协议中**。指向：`stripe-legal-index.txt` 第 24–25 行。

#### 1.6.4 兜底/其他类目

**Stripe 没有名为 "Other" 的类目，但有 4 类不同性质的兜底，且两类显式声明"非穷尽"。**

(1) **显式非穷尽声明 ×2**：
【原文】`The types of businesses listed here are representative of prohibited categories, but this is not an exhaustive list.`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 73 行 → https://stripe.com/legal/restricted-businesses

【原文】`The types of businesses listed below are representative of our restricted businesses but not exhaustive.`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 169 行 → 同一 URL

【判断】**两个主轴各配一句"非穷尽"声明**，措辞略有差异（`not an exhaustive list` vs `not exhaustive`）。**即 Prohibited 与 Restricted 两个清单都是开放集合。** 指向：第 73、169 行。

(2) **类目尾部开放兜底 ×3**（每类一条）：
【原文】`Any other products or services that are in violation of law in the jurisdictions where your business is located or to which your business is targeted`（Illegal 类）
【原文】`Any other products or services that directly infringe or facilitate infringement upon the trademark, patent, copyright, trade secrets, proprietary, or privacy rights of any third party`（IP 类）
【原文】`Any other businesses that Stripe considers unfair, deceptive, or predatory towards consumers`（UDAAP 类）
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 84、116、165 行 → 同一 URL

【判断】**Stripe 的兜底不是一条总兜底，而是"每个子类各配一条 `Any other ...`"** —— 三条兜底各自收束一个子类，且判据各异：法域违法 / 侵权 / Stripe 主观认定（`Stripe considers`）。**这是本报告兜底条款数量最多的系统（3 条类内兜底 + 2 条非穷尽声明）。** 指向：第 84、116、165 行。

(3) **未列出即默认允许（结构性）**：`Jurisdiction-specific prohibited businesses` 节只列 12 个国家。**未列出的国家在"国家轴"上不受额外限制**（但仍受行业轴约束）。即国家轴是**列举式白名单制的黑名单**（enumerated，不兜底）。指向：第 228–357 行。

(4) **产品专属兜底**：
【原文】`Any other abusive use of Stripe Issuing, including: Using Issuing cards to abuse free-trial products at scale / Using Issuing cards to buy in-demand items or services with the sole intent to sell them for profit (for example, retail scalping) / Using Issuing cards for any other illegitimate purposes`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt`（Prohibitions for Stripe Issuing products → Other abusive use）→ 同一 URL

#### 1.6.5 严重等级/后果

**Stripe 有明确的二档准入等级，但没有"处罚阶梯"。**

**档数 = 2（Prohibited / Restricted），区分依据是程序而非危害**：
【原文】`Prohibited businesses — Industries that can't use Stripe, and products Stripe doesn't support.` / `Restricted businesses — Industries and products that require additional due diligence.`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 50–53 行 → https://stripe.com/legal/restricted-businesses

【判断】**Restricted 不是"轻一点的禁止"，而是"需要额外尽调、可能批准也可能不批准"**。原文的后果说明是：

【原文】`Businesses in these categories require additional due diligence by Stripe in order to confirm our ability to support them. When you create your Stripe account, you will be asked to provide additional information (such as proof of relevant licenses or more details about your business model) to confirm your eligibility to use Stripe. Due to card network rules, requirements of financial partners, and our own compliance and legal obligations, if your business falls into one of the categories below, Stripe might not be able to grant approval for your business to use our products. If we do provide approval, note that the approval is specific to each service offer, and it may be modified or revoked by Stripe at any time per the terms of the Stripe Services Agreement.`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 167 行 → 同一 URL

【判断】这一段的 5 个结构件是本报告在"准入型后果"上最完整的：
1. **触发**：落入 Restricted 类目
2. **举证义务**：`you will be asked to provide additional information (such as proof of relevant licenses ...)`
3. **决定权**：`Stripe might not be able to grant approval`（不承诺批准）
4. **粒度**：`the approval is specific to each service offer`（**逐产品审批，不是逐账号**）
5. **可撤销性**：`it may be modified or revoked by Stripe at any time`

**"逐产品审批 + 随时可撤销"是 Stripe 独有的后果结构**（其他系统都是账号级或内容级）。指向：第 167 行。

**后果机制的唯一一处时间性条款（自动终止，非裁量）**：
【原文】`If there is inactivity on all cards associated with an account for a period of 12 consecutive months, Stripe automatically closes your Issuing account.`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt`（Prohibitions for Stripe Issuing products → Inactivity）→ 同一 URL

【判断】**唯一一条"无违规也终止"的后果**：触发条件是**不活跃满 12 个月**，而非违规。**这是全部证据中唯一把"不活跃"作为终止事由的规则。** 指向：同上。

**另有合规整改后果（带时限）**：
【原文】`our compliance teams might ask you to update your marketing materials or aspects of your user experience. ... Failure to comply within the requested time frames might result in the closure of your Stripe account.`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt`（Prohibitions for Stripe Issuing products → Noncompliance）→ 同一 URL

【判断】同 AWS 第 1.4 条（时限 + 逾期后果），但 Stripe 的时限是 `the requested time frames`（由 Stripe 逐案指定，不写死数字），AWS 写死 `2 business days`。指向：同段 vs `R7/aws-service-terms.txt` 第 277 行。

**"从不成为言论仲裁者"的自我限制条款（独有）**：
【原文】`Crucially, in the area of political expression, we want to avoid becoming an arbiter of what speech is legitimate. At Stripe, we do not restrict access to our services based on political viewpoints or affiliation.`
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 42 行 → 同一 URL

【判断】支付平台**主动声明排除一个本可规制的维度（政治观点）**。对照 Stripe 同时声明 `we have to adhere to financial laws and regulations, as well as rules and policies set by our financial partners, such as card networks and banking partners. This means we aren't able to support some businesses, even if we might desire to do so.`（第 44 行）—— **即 Stripe 明确把"限制的理由"归因于外部（法律 + 卡组织 + 银行），而非自身好恶。** 这是本报告唯一给出"限制的正当性来源"声明的规则库。指向：第 42、44 行。

#### 1.6.6 变更历史

**Stripe 是全部证据中唯一把"变更条目"写成"品类 + 方向 + 受影响法域"三元组的系统。**

**(1) 页顶更新区**
【原文】
```
Last updated: 2026-05-13
We've made important updates to the list of restricted and prohibited businesses. Here's what you need to know:
Updated domestic charter air travel from prohibited to restricted in the US, CA, UK, EU, BR, IN, TH, AU.
```
来源：`_evidence/R7/marketplace/stripe-restricted-businesses.txt` 第 37–39 行 → https://stripe.com/legal/restricted-businesses

【判断】这一条变更记录的三个结构件是全部证据中独有的：
1. **日期**：`2026-05-13`（**ISO 8601 格式 `YYYY-MM-DD`，与其他系统全不同** —— GitHub 无日期、PyPI/npm/AWS 用 `Month D, YYYY`、Meta 用 `Mon D, YYYY`）
2. **变更方向**：`from prohibited to restricted`（**明示档位迁移方向**）
3. **受影响法域**：`in the US, CA, UK, EU, BR, IN, TH, AU`（**ISO 3166 双字母码 + 区域码混用，逐国列出**）

**这是本报告唯一的"变更日志条目"，也是唯一一次在变更记录里出现国家码。** 其他系统的 changelog 要么不存在，要么只有日期（Meta 的 Change Log 全站只有日期）。指向：第 37–39 行。

【判断】注意日志用 `US, CA, UK, EU, BR, IN, TH, AU` —— **混用了 ISO 3166-1 alpha-2（US/CA/BR/IN/TH/AU）、ISO 3166-1 alpha-2 的非标准变体（UK 而非常用的 GB）、以及非国家实体（EU）**。即**变更日志里的法域代码没有受控词表**。指向：第 39 行。

**(2) 无版本号、无历史版本链接、无通知期条款**：整页只有 `Last updated: 2026-05-13`（第 37 行）一处时间信息，**不含 `version` 字段、不指向旧版本、不承诺通知期**。指向：整页。

---

### 1.7 eBay（市场侧 · 卖家守则）

⚠️ **取证说明（重要）**：本节的 eBay 证据有明确的完整度限制，先声明以免误用：
- `_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt`（HTTP 200，118,061B raw / 15,303B 文本）**是可用证据**，但它抓到的是 **eBay 的简体中文本地化版本**，且文本层含大量导航噪声（导航占约 100 行，正文约 90 行）。
- `_evidence/R7/marketplace/ebay-policy-index.txt`（38,602B）与 `ebay-prohibited-restricted-items.txt`（38,627B）**HTTP 状态虽为 200，但正文是反爬验证页，不是政策内容**。原文为：`Security Measure | eBay` / `Please verify yourself to continue` / `To keep eBay a safe place to buy and sell, we will occasionally ask you to verify yourself.`（来源：`_evidence/R7/marketplace/ebay-policy-index.txt` 第 6–10 行）。**这两个文件不可作为政策证据** —— 两个文件体量几乎相同（相差 25 字节）且正文一致，实为同一验证页的两次抓取。二者只进第 4 章「不可达来源」。
- 因此 **eBay 的"禁售清单"结构我未取到**，本节只剖析**卖家守则**的结构，且"切轴/兜底/等级"诸节的完整度低于其他系统。

#### 1.7.1 切了什么轴（基于卖家守则）

**主轴 = 卖家义务域（守则 → 表现标准 → 具体政策），是三层的 hub-and-spoke 结构。**

卖家守则页尾列出的"相关帮助主题"给出了 eBay 的政策族清单：

【原文】
```
销售守则政策 记住一些基本的销售守则，可以为买家带来出色的体验。 文章预计阅读时间： 15 分钟
卖家标准政策
我们的卖家表现要求旨在帮助确保买家在 eBay 上获得出色的体验。您的卖家级别表明您是否达到或超出我们的最低标准。
文章预计阅读时间： 9 分钟
税务政策
卖家必须遵守所有适用于 eBay 销售活动的税法规定。
文章预计阅读时间： 5 分钟
知识产权政策
禁止在 eBay 上刊登侵犯他人知识产权的物品或产品。
文章预计阅读时间： 5 分钟
销售政策
我们的政策旨在为所有 eBay 用户营造公平、安全的交易体验。卖家有责任定期查看并遵守 eBay 的销售政策，履行我们的用户协议中规定的卖家义务。
概览预计阅读时间： 2 分钟
签名确认政策
当买家举报未收到物品或提出付款纠纷申诉时，为使卖家获得 eBay 提供的保障，以及当卖家未收到退回的物品时，为使买家获得保障，我们要求在运送大额物品时增加签名确认。
文章预计阅读时间： 5 分钟
```
来源：`_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt` 第 183–198 行 → https://www.ebay.com/help/policies/selling-policies/seller-code-of-conduct?id=4345

【判断】eBay 的切轴是**"义务域 → 独立帮助文章"**：销售守则 / 卖家标准 / 税务 / 知识产权 / 销售政策 / 签名确认，每域一篇独立文章。**与 npm 的"一份文件一条轴"同构，但 eBay 的轴名是"卖家要做什么"，而 npm 的轴名是"一个法律问题域"。** 指向：同上。

**【判断】eBay 独有：每条政策带"预计阅读时间"元数据**（`文章预计阅读时间： 15 分钟` / `9 分钟` / `5 分钟` / `2 分钟`）。**这是全部证据中唯一的规则级"阅读成本"元数据** —— 其他系统的元数据都是版本、标签、责任人、法域，只有 eBay 标注**读者需要花多久读完**。这暗示 eBay 把政策当作**需要被消费的内容**而非**需要被引用的规范**。指向：第 183–198 行。

**正文内的次级切轴（卖家守则正文）= 按"对谁负责"分**：对买家（不得滥用买家权利相关）、对平台（不得违反禁售政策）、对自身（表现标准）。指向：第 84–173 行。

#### 1.7.2 一条规则的内部结构

**规则单位 = 中文陈述句，且经常是"描述情形 + 后果"两段式。**

【原文】`一旦确定买家违反 滥用买家权利政策 ，我们将移除任何相关的差评或中评，以及不良交易记录，包括服务指标中的处理中的个案。对于滥用权利的买家，我们可能还会限制其在 eBay 上提交退货请求的权限。对于严重的个案或多次滥用权利的行为，我们可能会冻结买家帐户。`
来源：`_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt` 第 84 行 → https://www.ebay.com/help/policies/selling-policies/seller-code-of-conduct?id=4345

【判断】**eBay 的单条规则内嵌三档后果**，且分档变量明确写在句中：
- 一般认定 → 移除差评/中评 + 清除不良交易记录
- 加重 → 限制提交退货请求权限
- `严重的个案或多次滥用权利的行为` → 冻结帐户

**即 eBay 把"后果阶梯"写在规则正文里，而不是集中在一张处罚表里。** 这是与 GitHub/Meta 相反的策略。指向：第 84 行。

【判断】触发门槛用**副词短语**表达（`严重的个案` / `多次滥用`），与 PyPI 的三个 `significantly` 同构（见 1.3.5）。指向：第 84 行 vs `R7/pypi-aup.txt` 第 228 行。

**另一种规则形态：以"违规示例"反写规则**
【原文】`违反我们 违禁和限制物品政策 的物品` / `未遵守您的服务承诺（例如不遵守退货政策）` / `具有严重的政策违规记录，例如出售伪造物品、使用禁止的直接代发方式或在 eBay 平台外进行交易`
来源：`_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt` 第 163–168 行 → 同一 URL

【判断】**这三条是"导致卖家降级/失去保障的行为"清单，用 `<行为>（例如 <具体例子>）` 模板**。注意 `在 eBay 平台外进行交易`（off-platform transactions）是市场平台特有的禁止项 —— **内容平台（GitHub/PyPI/npm）没有这条，因为它预设了平台外的真实交易存在。** 指向：第 168 行。

**跨政策引用是 eBay 规则的主要连接方式**：正文密集出现指向其他政策的链接标题（`滥用买家权利政策` / `卖家标准政策` / `服务指标政策` / `违禁和限制物品政策` / `滥用卖家保障政策` / `知识产权政策`）。**即 eBay 的规则句子本身不完整，须靠跨政策链接闭合。** 指向：第 84–196 行。

#### 1.7.3 作用域如何表达

**eBay 的作用域表达是"站点"（site），且它在本页中只以隐含方式出现。**

【判断】本页证据中**未找到任何国家/法域字段、法域限定词或国家列表**。可观测到的唯一地域线索是页面的**本地化形态本身**：抓到的版本标题为 `卖家保障 | eBay`、语言选择器为 `请选择语言。当前选择： 简体中文 / English`（来源：`_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt` 第 9–13 行）。

【判断】**eBay 的法域维度以"站点分站 + 语言版本"承载，本条证据只能看到语言维度（简体中文 vs English），看不到"同一政策在不同 eBay 站点是否有不同内容"。** 若要回答"eBay 的禁售清单是否按国家差异"，需要 eBay 各站点（ebay.com / ebay.co.uk / ebay.de）的禁售清单页 —— **本次抓取未取到**（见第 4 章）。**如实记为：结构未取到，不推断。** 指向：第 9–13 行 + 第 4 章。

**唯一的"作用域隐含表达"**：`在 eBay 平台外进行交易` 说明 eBay 明确区分**平台内 / 平台外**这一作用域维度（平台外行为也被规制，作为降级事由）。指向：第 168 行。

#### 1.7.4 兜底/其他类目

**本条证据中未找到 eBay 的兜底类目或"其他"类目。**
- 正文中**没有出现** `其他` / `其他类目` / 非穷尽声明。
- 但出现了**开放式的例子引导词** `例如`（用于 `未遵守您的服务承诺（例如不遵守退货政策）` 与 `具有严重的政策违规记录，例如出售伪造物品...`），**说明其列举是示例性的、非穷尽的** —— 这是隐式的开放性，不是显式的兜底类目。

【判断】受证据限制，**eBay 是否有兜底类目记为"未找到"**，不推断。指向：`_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt` 第 163–173 行。

#### 1.7.5 严重等级/后果

**eBay 的等级结构 = 卖家级别（seller level），这是与所有其他系统都不同的"以持续表现为基础的等级"。**

【原文】`我们的卖家表现要求旨在帮助确保买家在 eBay 上获得出色的体验。您的卖家级别表明您是否达到或超出我们的最低标准。`
来源：`_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt` 第 184–187 行 → https://www.ebay.com/help/policies/selling-policies/seller-code-of-conduct?id=4345

【原文】`有关表现评估方式的全部详情，请阅读我们的 卖家标准政策 和 服务指标政策 。`
来源：`_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt` 第 134 行 → 同一 URL

【判断】**eBay 的等级不是"违规 → 处罚"的映射，而是"持续表现 → 级别"的映射**：`卖家级别`（seller level）由服务指标（service metrics）决定，达标即保持，不达标即降级。**这是本报告唯一的"连续评级型"等级机制** —— 对比 GitHub 的 5 项响应清单、Meta 的 tier、YouTube 的 strike、Stripe 的准入二档、AWS 的四段程序。指向：第 134、184–187 行。

**后果档（从正文可辨）= 4 类，且混合了"处罚"与"失去保障"两种性质**：
1. **失去平台保障**：`如果 eBay 介入，协助处理退货或未收到物品请求：如果买家退回的物品已使用或损坏，您将无法再从买家的退款中扣除金额`（第 176 行）
2. **记录不予清除**：`一旦我们确定您有责任向买家退款，我们不会移除差评和中评，并将退货计入"卖家未解决的已关闭个案"`（第 178 行）
3. **卖家级别下降**（通过 `卖家标准政策` 间接实现，本页未给具体档位）
4. **买家侧后果**（本页同时规定了买家滥用权利的后果）：`我们可能会冻结买家帐户`（第 84 行）

来源：`_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt` → 同一 URL

【判断】**"不提供保障"（denial of protection）是 eBay 独有的后果类型**：不是禁止你做什么，而是**当你违规时，平台不再替你承担买卖纠纷的损失**。GitHub/PyPI/npm/AWS/Stripe 都没有这一档 —— 它们只有"移除/限制/封禁/拒绝准入"。**这是市场平台特有的后果结构**（因为市场平台的核心服务就是纠纷保障）。指向：第 176–178 行。

#### 1.7.6 变更历史

**本条证据中未找到 eBay 的变更历史机制。**
- 页面文本中**没有出现** `最后更新` / `Last updated` / 版本号 / 变更记录。
- **未找到** 任何日期字段。

【判断】受证据完整度限制，**eBay 的变更机制记为"未找到"** —— 注意这**不等于"eBay 没有变更机制"**，只等于"我取到的这一页（简中版卖家守则）里没有出现"。eBay 的帮助文章通常带"此文章是否有帮助"反馈控件与更新时间，本页只取到了前者（`这篇文章对您有帮助吗？`，第 173 行）。指向：`_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt` 第 173 行。
---

### 1.8 Meta（基于 R1 证据）

Meta 是本报告**唯一拥有完整"规则内部字段集"的系统** —— 每一个政策 section 都是同一套字段的实例，且字段名在页面上固定出现。

> **证据性质说明**：本节的一手证据是 `R1/meta-cs-*.md`（27 个 section 的文本抽取，逐文件头含 `source URL` / `http status: 200` / `raw html bytes`）。另有一份同批产出的 `R1/meta-cs-STRUCTURE-INVENTORY.md`，它是对同一批 `.html` 的结构统计表 —— **本节的原始引用一律直接取自 `meta-cs-*.md` 或 `meta-*.md` 正文**；凡引用 INVENTORY 的统计结论处，均明确标注为"INVENTORY 统计"。

#### 1.8.1 切了什么轴

**主轴 = 危害主题（harm topic），27 个 section，且索引页是一张纯 flat 清单。**

27 个 section 逐条列出（索引页原文）：

【原文】
```
[Coordinating Harm and Promoting Crime](</policies/community-standards/coordinating-harm-publicizing-crime/>)
[Dangerous Organizations and Individuals](</policies/community-standards/dangerous-individuals-organizations/>)
[Prohibited Commercial Practices](</policies/community-standards/prohibited-commercial-practices/>)
[Restricted Goods and Services](</policies/community-standards/regulated-goods/>)
[Violence and Incitement](</policies/community-standards/violence-incitement/>)
[Adult Sexual Exploitation](</policies/community-standards/sexual-exploitation-adults/>)
[Bullying and Harassment](</policies/community-standards/bullying-harassment/>)
[Child Sexual Exploitation, Abuse, and Nudity](</policies/community-standards/child-sexual-exploitation-abuse-nudity/>)
[Human Exploitation](</policies/community-standards/human-exploitation/>)
[Suicide, Self-Injury, and Eating Disorders](</policies/community-standards/suicide-self-injury/>)
[Adult Nudity and Sexual Activity](</policies/community-standards/adult-nudity-sexual-activity/>)
[Adult Sexual Solicitation and Sexually Explicit Language](</policies/community-standards/sexual-solicitation/>)
[Hateful Conduct](</policies/community-standards/hate-speech/>)
[Privacy Violations](</policies/community-standards/privacy-violations-image-privacy-rights/>)
[Violent and Graphic Content](</policies/community-standards/violent-graphic-content/>)
[Account Integrity ](</policies/community-standards/account-integrity/>)
[Authentic Identity Representation](</policies/community-standards/authentic-identity-representation/>)
[Cybersecurity](</policies/community-standards/cybersecurity/>)
[Inauthentic Behavior](</policies/community-standards/inauthentic-behavior/>)
[Memorialization](</policies/community-standards/memorialization/>)
[Misinformation](</policies/community-standards/misinformation/>)
[Spam](</policies/community-standards/spam/>)
[Third-Party Intellectual Property Infringement](</policies/community-standards/intellectual-property/>)
[Using Meta Intellectual Property and Licenses](</policies/community-standards/meta-intellectual-property/>)
[Additional Protection of Minors](</policies/community-standards/additional-protection-minors/>)
[Locally Illegal Content, Products, or Services](</policies/community-standards/locally-illegal-products-services/>)
[User Requests](</policies/community-standards/user-requests/>)
```
来源：`R1/meta-cs-index.md` 第 82–134 行 → https://transparency.meta.com/policies/community-standards/

【判断】**索引页是 flat 的：27 个 section 无分组标题。** INVENTORY 的核验指出：原始 HTML 中该页只有 1 个 `<h1>`（"Community Standards"），**无任何 `<h2>/<h3>/<h4>`**，且对 "Violence and Criminal Behavior" / "Objectionable Content" / "Integrity and Authenticity" / "Respecting Intellectual Property" / "Content-Related Requests" 五个候选组名的大小写不敏感检索**均为 0 命中**（INVENTORY 脚注 3）。**即：任何"Meta 有 6 大分组"的说法都不来自现行索引页。** 指向：`R1/meta-cs-index.md` 第 82–134 行 + INVENTORY 脚注 3。

【判断】**但顺序本身是有信息的**：前 15 项是"内容危害"（harm to persons / content），后 12 项是"平台与身份完整性"（account integrity / identity / cybersecurity / inauthentic behavior / memorialization / misinformation / spam / IP / minors / local law / user requests）。**这是"危害内容 → 平台完整性"的隐性二分，但以顺序而非标题承载。** 指向：同上清单。

【判断】**只有 2 个 section 名带"标准外"语义**：`Locally Illegal Content, Products, or Services`（法域专章）与 `User Requests`（请求处理专章）。**这两个是"元 section"，不是危害类目** —— 前者承载法域差异，后者承载用户请求流程。**即 Meta 把"法域"独立成一个 section，而不是在每条规则上加限定词。** 指向：第 132、134 行。

#### 1.8.2 一条规则的内部结构（Meta 最强的结构）

**Meta 的每个 section 都按同一套字段模板组织，字段名在页面上显式出现。** 索引页对模板的说明：

【原文】`Each section of our Community Standards starts with a "Policy Rationale" that sets out the aims of the policy followed by specific policy lines that outline: Content that's not allowed; and Content that requires additional information or context to enforce on, content that is allowed with a warning screen or content that is allowed but can only be viewed by adults aged 18 and older.`
来源：`R1/meta-cs-index.md`（Community Standards 节）→ https://transparency.meta.com/policies/community-standards/

**从单个 section 可观测到的字段顺序**（以 Hateful Conduct 为例）：

【原文】字段出现顺序（页内标题逐字）：
```
Enforcement
Policy Details
User Experiences
Data
...
CHANGE LOG
Today
Jan 7, 2025
Feb 29, 2024
...
Policy Rationale
...
For the following Community Standards, we require additional information and/or context to enforce:
...
Data
```
来源：`R1/meta-cs-hate-speech.md` 第 12、36、38、40、44–50、102、186、220 行 → https://transparency.meta.com/policies/community-standards/hateful-conduct/

【判断】**单条 section 的字段集 = 6 个**：
1. **`CHANGE LOG`** —— 日期串（仅日期，无逐条说明）
2. **`Policy Rationale`** —— 政策目的 + 术语定义
3. **policy lines**（`Do not post:` 之后的禁止项清单）
4. **`For the following Community Standards, we require additional information and/or context to enforce:`** —— **"需要额外语境"分组**（明文的分档标题）
5. **`User Experiences`** —— 用户端体验说明
6. **`Data`** —— 指向透明度数据的链接

**【判断】这是本报告唯一拥有"具名字段槽位"的规则库。** 对比：GitHub 只有"短版摘要 + 标题 + bullet"；PyPI/npm 只有 bullet；AMO 只有编号标题；AWS 只有编号条款；Stripe 只有品类名。**Meta 的 `Policy Rationale` / `User Experiences` / `Data` / `CHANGE LOG` 是四个可在页面上定位、可逐 section 比对的固定字段。** 指向：同上标题清单。

**`Policy Rationale` 承担"定义 + 分档声明"双重职责**（这是 Meta 结构的关键）：

【原文】`We define hateful conduct as direct attacks against people — rather than concepts or institutions — on the basis of what we call protected characteristics (PCs): race, ethnicity, national origin, disability, religious affiliation, caste, sexual orientation, sex, gender identity, and serious disease. Additionally, we consider age a protected characteristic when referenced along with another protected characteristic. We also protect refugees, migrants, immigrants, and asylum seekers from the most severe attacks (Tier 1 below), though we do allow commentary on and criticism of immigration policies.`
来源：`R1/meta-cs-hate-speech.md` 第 104 行 → https://transparency.meta.com/policies/community-standards/hateful-conduct/

【原文】`We separate this speech into two tiers of severity, described below.`
来源：`R1/meta-cs-hate-speech.md` 第 106 行 → 同一 URL

【判断】**`Policy Rationale` 里同时完成了三件事**：(a) 定义核心术语（`protected characteristics` 并**枚举 11 项封闭清单**）；(b) **声明本 section 的档数**（`two tiers of severity`）；(c) 引入**近似概念**（`age ... referenced along with another protected characteristic` / `non-protected characteristics, such as occupation, when they are referenced along with a protected characteristic`）。**"档数"写在 Policy Rationale 里，是本报告唯一把等级声明显式写进规则文本的系统。** 指向：第 104–106 行。

【判断】**Meta 的规则有"定义 → 分档 → 列举"三段式，且定义层可携带精确的限定条件**，例如 `we consider age a protected characteristic when referenced along with another protected characteristic` —— 这是**"概念组合触发"型定义**（单列不触发，组合才触发），在其他系统里没有对应物。指向：第 104 行。

**第二类句式：`Do not post:` 引导的禁止清单**（独立一行，与 Rationale 分离）：
【原文】`Do not post:`（`R1/meta-cs-hate-speech.md` 第 116 行，紧接于 Policy Rationale 各段之后）
来源：`R1/meta-cs-hate-speech.md` → 同一 URL

【判断】**Meta 把"为什么禁"（Rationale）与"禁什么"（Do not post）切成两个物理分离的块**，而 GitHub 把两者都省略（只有"禁什么"）。**这是"规则说明"与"规则本体"分离的唯一样本。** 指向：第 102（Rationale）与第 116（Do not post）行。

**第三类结构：`Notwithstanding` 例外块（极稀有）**

INVENTORY 脚注 1 的统计：**27 个 section 中只有 2 个含 `Notwithstanding`**：

【原文】`Notwithstanding the above, we do not prohibit content that condemns, raises awareness of, or educates others about scams or other prohibited commercial practices, without either revealing sensitive information or promoting them.`（prohibited-commercial-practices）
【原文】`* Notwithstanding the above, we do not prohibit:` 后接三个嵌套项：`Cross promotion that is not triggered by payment to a third party` / `Transferring admin or moderation responsibilities for a page or group to another user based on their interest in the page or group, rather than an exchange of value.` / `Posting or sharing clearly identified Branded Content.`（spam）
来源：`R1/meta-cs-STRUCTURE-INVENTORY.md` 脚注 1（逐字引自对应 `meta-cs-*.html`）

【判断】**`Notwithstanding the above, we do not prohibit:` 是 Meta 的"例外清单"结构** —— 整个 section 的禁令之后，用一句 `Notwithstanding` 打开一个反向白名单。**25/27 的 section 没有这个块**，即**例外条款不是模板字段，是少数 section 的附加件**。指向：INVENTORY 脚注 1（统计）+ 上述原文。

#### 1.8.3 作用域如何表达

**Meta 的作用域主轴是"产品"（Facebook / Instagram / Threads / Messenger），表达方式是"句中列举"，且各 section 不一致。**

【原文】`That is why we don't allow hateful conduct on Facebook, Instagram, or Threads.`
来源：`R1/meta-cs-hate-speech.md` 第 102 行 → https://transparency.meta.com/policies/community-standards/hateful-conduct/

【原文】`The Community Standards outline what is and isn't allowed on Facebook, Instagram, Messenger and Threads.`
来源：`R1/meta-cs-index.md`（Community Standards 引言）→ https://transparency.meta.com/policies/community-standards/

【判断】**同一规则族内出现两个不同的产品清单**：索引页是 `Facebook, Instagram, Messenger and Threads`（4 个），Hateful Conduct 是 `Facebook, Instagram, or Threads`（3 个，**无 Messenger**）。**即产品作用域在 section 级可以窄于索引级，且不通过字段表达，只通过句中产品名列举。** 指向：上述两段。

**法域作用域：由独立 section 承载 + section 内的条件性条款**
【原文】`Locally Illegal Content, Products, or Services`（section 名，`R1/meta-cs-index.md` 第 132 行）

INVENTORY 从该 section 抽出的逐字内容：
【原文】`When regulators or government entities believe content on our services goes against local law, they may ask us to restrict the content.` / `Where we do act against user content on the basis of local law rather than our Community Standards, we endeavor to restrict access to the content only in the jurisdiction where it is alleged to be unlawful and do not impose any other penalties or feature restr...`
来源：`R1/meta-cs-STRUCTURE-INVENTORY.md` 表内 `locally-illegal-products-services` 行（逐字引自 `meta-cs-locally-illegal-products-services.html`）

【判断】**这是本报告最清晰的"法域作用域"结构声明**：`we endeavor to restrict access to the content only in the jurisdiction where it is alleged to be unlawful and do not impose any other penalties` —— **法域差异通过"地域性屏蔽"实现（同一内容在 A 国可见、B 国不可见），而非"同一平台在不同国家有不同规则"。** 且明确加了第二重限制：**地域屏蔽不伴随其他处罚**。指向：INVENTORY 表该行。

**section 内的法域条件条款（3 处，逐字）**：
【原文】`Note: if you are a European Union user, and are seeing content that you believe violates hate speech laws within your country, you can submit a legal removal request to [Facebook](<https://www.`（hate-speech）
【原文】`* An adult, where the content was reported by the adult from outside the United States and applicable law may provide rights to removal.`（privacy-violations-image-privacy-rights）
【原文】`As part of that effort, outside of the United States we partner with third-party fact checking organizations in many parts of the world to review and rate the accuracy of the most viral content on our platforms`（misinformation）
来源：`R1/meta-cs-STRUCTURE-INVENTORY.md` 表内对应行的 "Any region/country-specific text?" 列（逐字引自对应 `.html`）

【判断】**Meta 的法域条款全部以"美国 / 非美国"或"EU 用户"这类二分表述出现，没有出现国别列表。** 唯一的方向性是：**默认规则假定美国，非美国情形作为附加条款**（`outside of the United States` ×2）。指向：上述三段。

**一处国际法援引（唯一）**：
【原文】`We do this only after weighing the public interest value against the risk of harm, and we look to international human rights standards to make these judgments.`
来源：`R1/meta-cs-index.md`（Our commitment to voice 节）→ https://transparency.meta.com/policies/community-standards/

【判断】**Meta 是唯一明示以"国际人权标准"作为裁量依据的系统** —— 不是某国法，而是国际人权框架。这与其"全球统一标准 + 地域屏蔽"的结构一致。指向：同上。

**主文档的语种作用域声明（唯一）**：
【原文】`**Please note that the US English version of the Community Standards reflects the most up to date set of the policies and should be used as the primary document.**`
来源：`R1/meta-cs-index.md`（Introduction 节）→ 同一 URL

【判断】**这是全部证据中唯一"语言版本效力优先级"条款**：美式英语版为唯一准据版本，其他语言版本（含本证据抓到的可能就是英文版）降为参考。**即"语言"是 Meta 的一等作用域维度，且带效力排序。** 其余系统（GitHub/Stripe/eBay）有多语言版本但都没有声明效力优先级。指向：同上。

#### 1.8.4 兜底/其他类目

**Meta 没有 named "Other" 类目。兜底通过 3 种机制实现。**

(1) **`Locally Illegal Content, Products, or Services` 承担"法域兜底"** —— 见 1.8.3。该 section 的政策体**不含任何 bullet**（INVENTORY 统计："0 bullets"），**全文是 2 段散文**。**即兜底 section 不是规则清单，而是程序说明。**

(2) **`User Requests` 承担"用户请求兜底"** —— 该 section 只有 2 条 policy-line bullet（INVENTORY 统计），**是 27 个 section 中最短的之一**（并列最短：`additional-protection-minors` 3 条）。

(3) **Policy Rationale 内的"意图例外"充当个案兜底**：
【原文】`We recognize that people sometimes share content that includes slurs or someone else's speech in order to condemn the speech or report on it. In other cases, speech, including slurs, that might otherwise violate our standards is used self-referentially or in an empowering way. We allow this type of speech where the speaker's intention is clear. Where intention is unclear, we may remove content.`
来源：`R1/meta-cs-hate-speech.md` 第 108 行 → https://transparency.meta.com/policies/community-standards/hateful-conduct/

【判断】**这是"意图兜底"：判据是 `where the speaker's intention is clear`，且给出反向默认 —— `Where intention is unclear, we may remove content`（**意图不明则移除**）。**这是本报告唯一显式规定"证据不足时向移除一侧倾斜"的规则** —— 方向与 GitHub 的 `resolve disputes in favor of protecting users as a whole`（1.1.4）同向，但 Meta 是针对"意图证据"这一具体维度写的。指向：第 108 行。

**INVENTORY 的"结构离群值"统计（引用时已标注为统计结论）**：
- `additional-protection-minors` 是**唯一没有 `Policy Rationale` 字段的 section**，其政策体直接以 `We comply with:` 开头。
- `locally-illegal-products-services` 的**政策体 0 条 bullet**，正文是 2 段散文。
- `prohibited-commercial-practices` 是**唯一页面中完全不出现 `warning screen` 字符串的 section**。
来源：`R1/meta-cs-STRUCTURE-INVENTORY.md` 脚注 4、5

【判断】**即 Meta 的"统一模板"有 3 个已确认的破例实例**，说明模板是**惯例而非校验机制**（无 schema 强制）。指向：同上。

#### 1.8.5 严重等级/后果（Meta 全系统最强）

**Meta 的等级是"tier（在规则内声明）+ strike（在执行文档中阶梯化）"双层。**

**(a) 规则内的 severity tier**
【原文】`We separate this speech into two tiers of severity, described below.`
来源：`R1/meta-cs-hate-speech.md` 第 106 行 → https://transparency.meta.com/policies/community-standards/hateful-conduct/

【判断】**档数在规则文本内被显式声明（`two tiers`）并在小节标题里命名为 `Tier 1`。** INVENTORY 统计指出 `dangerous-individuals-organizations` 的正文也含 `Tier 1` 字样（`Tier 1 includes hate organizations; criminal organizations, including those designated by the United States government as Specially Designated Narcotics Trafficking Kingpins (SDNTKs); and terrorist organizations...`）。**即 tier 是 Meta 的规则级等级字段，但以散文标签而非结构化字段存在。** 指向：第 106 行 + INVENTORY 表。

**(b) 内容可见性档（3 档，来自索引页声明）**
【原文】`Content that's not allowed; and Content that requires additional information or context to enforce on, content that is allowed with a warning screen or content that is allowed but can only be viewed by adults aged 18 and older.`
来源：`R1/meta-cs-index.md`（Community Standards 节）→ https://transparency.meta.com/policies/community-standards/

【判断】**内容侧后果档数 = 4**：不允许 / 需额外语境 / 允许但加警告屏 / 允许但限 18+。**这是本报告中唯一"允许但降级"的两档（warning screen / 18+）** —— 其他系统的后果都是"删/限/封"，只有 Meta 有"保留内容但改变其可见形态"。指向：同上。

INVENTORY 的 policy-body-only 统计给出实际分布（已标注为统计）：`warning screen` 仅出现在 4 个 section 的政策体中（child-sexual-exploitation / suicide-self-injury / adult-nudity-sexual-activity / violent-graphic-content）；`18 and older` 出现在 5 个；`severe` 出现在 5 个（violence-incitement / bullying-harassment / hate-speech / violent-graphic-content / account-integrity）。来源：INVENTORY 脚注 5。

**(c) strike 阶梯（执行文档，10 档，逐档写明时长）**
【原文】
```
One strike: You'll get a warning since this is your first strike.
Two to six strikes: You'll be restricted from specific features, like posting in groups, for a limited amount of time.
Seven strikes: You'll get a one-day restriction from creating content, which includes posting, commenting, creating a Page, and more.
Eight strikes: You'll get a 3-day restriction from creating content.
Nine strikes: You'll get a 7-day restriction from creating content.
Ten or more strikes: You'll get a 30-day restriction from creating content.
```
来源：`R1/meta-ad-enforcement-restricting-accounts.md` → https://transparency.meta.com/enforcement/taking-action/restricting-accounts/

【判断】**这是全部证据中最细的后果阶梯（6 个命名档，覆盖 1/2-6/7/8/9/10+ 次 strike），且每档给出精确时长（1 天 / 3 天 / 7 天 / 30 天）。** 其他系统：GitHub 5 项无门槛清单、PyPI 3 项、npm 3 项、AMO 3 类对象、AWS 4 段程序、Stripe 2 档准入、YouTube 3 strike。**Meta 的档数最多且带时间刻度。** 指向：同上。

**(d) 严重违规的"跳过阶梯"机制**
【原文】`In some cases, a violation may be severe enough, such as posting child sexual exploitation content, that we'll disable your account, Page or group on Facebook, or your account on Instagram, after one occurrence.`
来源：`R1/meta-ad-enforcement-counting-strikes.md` → https://transparency.meta.com/enforcement/taking-action/counting-strikes/

【原文】`If content you posted goes against our more severe policies, such as our policy on dangerous individuals and organizations or adult sexual exploitation, you may receive additional, longer restrictions from certain features, on top of the standard restrictions above. For example, you may be restricted from creating ads and using Facebook Live for set periods of time, starting on your first strike.`
来源：`R1/meta-ad-enforcement-restricting-accounts.md` → https://transparency.meta.com/enforcement/taking-action/restricting-accounts/

【判断】**两条平行的"加档"机制**：
1. **单次即封**（`after one occurrence`）—— 用于最严重类目（举例为 CSE）
2. **首次即加长限制**（`starting on your first strike`）+ **跨产品限制**（`creating ads and using Facebook Live`）—— 用于 `more severe policies`

**即 Meta 的等级是"基线阶梯 + 按类目升档"的二维结构**，类目严重度是独立于 strike 数的第二个维度。指向：上述两段。

**(e) strike 的"失效/豁免"规则（Meta 独有）**
【原文】`To ensure our strike system is fair and proportionate, we won't count strikes on violating content posted over 90 days ago for most violations or over 4 years ago for more severe violations. We also won't count strikes for certain policy violations. This includes when someone shares their own financial information, which we remove to prevent fraud, or cases where we have extra context about the nature of the violation.`
来源：`R1/meta-ad-enforcement-counting-strikes.md` → https://transparency.meta.com/enforcement/taking-action/counting-strikes/

【原文】`If we remove multiple pieces of content at once, without notifying you at each removal, we may also count them as a single strike. All strikes on Facebook or Instagram expire after one year.`
来源：`R1/meta-ad-enforcement-counting-strikes.md` → 同一 URL

【判断】**4 类"不计 strike"的规则，是本报告独有的"计数豁免"机制**：
1. **时间失效**：`over 90 days ago`（多数违规）/ `over 4 years ago`（更严重违规）—— **两个回溯窗口，按严重度分档**
2. **类目豁免**：`certain policy violations`（举例：用户分享自己的财务信息，为防诈而删除）
3. **语境豁免**：`cases where we have extra context about the nature of the violation`
4. **批量合并**：一次移除多条 → 可计为**单次** strike
5. **strike 过期**：`All strikes on Facebook or Instagram expire after one year`

**即 Meta 的等级不只是"几次违规 → 多长处罚"，而是"哪些违规算数 → 怎么算"。** 这是本报告唯一把"计数规则"独立成文的系统。指向：同上两段。

**【判断】strike 的判据是三维的，且写在执行文档里**：
【原文】`Whether we apply a strike depends on the severity of the content, the context in which it was shared and when it was posted.`
来源：`R1/meta-ad-enforcement-counting-strikes.md` → 同一 URL

**三维 = severity / context / timing。** 注意 `timing`（何时发布）**既影响是否计 strike（90 天 / 4 年回溯），也可能影响 strike 本身是否施加** —— 这在其他系统中没有对应物。指向：同上。

**(f) 误判纠正通道**
【原文】`Sometimes we might make mistakes. If you think we got something wrong, you can let us know in the app. If we find that your content did actually follow our Community Standards, we'll put the content back on Facebook or Instagram. We'll also remove the strike and restriction so that it won't count against you in the future.`
来源：`R1/meta-ad-enforcement-restricting-accounts.md` → 同一 URL

【判断】**明确"strike 可撤回且不追溯计入"**，与 PyPI 的"一律不可逆"（1.3.5）构成两个极端。指向：同上 vs `R7/pypi-aup.txt` 第 512–517 行。

**(g) 一处有时限的例外协议（独有）**
【原文】`Update July 12, 2024: Periodic Review — To ensure our users can hear from political candidates on our platforms, going forward, we will review the accounts subject to this protocol on a periodic basis to determine whether heightened penalties for Community Standards violations remain appropriate. We will make this determination by weighing our responsibility, as outlined by the Oversight Board, to "allow political expression" against our responsibility "to avoid serious risks to other human rights."`
来源：`R1/meta-ad-enforcement-restricting-accounts.md` → 同一 URL

【判断】**执行文档内嵌"带日期的政策修订块"**（`Update July 12, 2024: Periodic Review`），是本报告唯一在执行规则正文里出现"Update + 日期 + 标题"的写法。且该块**引入了第二个裁量主体（Oversight Board）的指引**作为权衡依据。指向：同上。

#### 1.8.6 变更历史（Meta 有本报告最完整的逐条日期记录）

**Meta 每个 section 都带 `CHANGE LOG` 字段，且回溯到 2018 年。**

【原文】
```
CHANGE LOG

Today

Jan 7, 2025

Feb 29, 2024

Dec 5, 2023

May 25, 2023

Nov 23, 2022

Jul 28, 2022

Jun 30, 2022

Nov 24, 2021

Oct 28, 2021

Jun 23, 2021

Jan 28, 2021

Nov 18, 2020

Oct 12, 2020

Sep 23, 2020

Aug 11, 2020

Jul 30, 2020

Jun 22, 2020

Mar 26, 2020

Feb 27, 2020

Dec 16, 2019

Oct 30, 2019

Aug 26, 2019

Jul 30, 2019

Jul 1, 2019

Mar 20, 2019

Aug 31, 2018

May 25, 2018
```
来源：`R1/meta-cs-hate-speech.md` 第 44–100 行 → https://transparency.meta.com/policies/community-standards/hateful-conduct/

【判断】**4 个结构特征**：
1. **仅日期，无逐条说明** —— INVENTORY 脚注 4 明确：`Change Log entries are dates only - no per-entry description text is rendered for any section.`
2. **最新一条永远是字面量 `Today`**（相对标签，不是绝对日期）—— 这是本报告唯一用相对时间的变更记录。
3. **倒序排列**，Hateful Conduct 一条回溯到 `May 25, 2018`，为该 section 提供了完整的 8 年修订轨迹。
4. **`Today` 之后的第一个绝对日期因 section 而异**：Hateful Conduct 是 `Jan 7, 2025`（29 条），`regulated-goods` 有 32 条（回溯至 `Aug 31, 2018`），`intellectual-property` **只有 2 条**（`Today` + `Aug 26, 2024`），`meta-intellectual-property`、`prohibited-commercial-practices`、`meta-intellectual-property` 等**只有 `Today` 一条**。

来源：`R1/meta-cs-hate-speech.md` 第 44–100 行 + INVENTORY 表各行的 "Change Log dates" 列（统计）。

【判断】**变更频率在 section 之间差异极大**（从 1 条到 32 条），**而 Change Log 字段本身是全 section 强制存在的**（INVENTORY 表 "Change Log present?" 列 27/27 全为 yes）。**即 Meta 强制记录变更、但不强制变更有内容。** 指向：INVENTORY 表首列。

**【判断】执行文档的版本信息形式不同**：`meta-ad-enforcement-counting-strikes.md` 用 `UPDATEDAPR 23, 2025`，`restricting-accounts` 用 `UPDATEDNOV 12, 2024`（来源：两文件正文首部）。**即"政策 section"用 CHANGE LOG 列表，"执行 hub 页"用单行 UPDATED 标记** —— 两套版本机制并存于同一站点。指向：上述两文件 + INVENTORY 脚注 6（该脚注指出两个 enforcement hub 页既无 Change Log 也无 Policy Rationale，是"narrative hub pages, not policy sections"）。

**无版本号**：Meta 全站政策**均无 `version` 字段或版本号**，只有日期。指向：上述各处。
---

### 1.9 Google（基于 R1 证据）

Google Ads 的政策库是本报告中**唯一把"变更日志"提升为一级导航栏目**的系统，也是**唯一用"地理标准 ID"表达法域**的系统。

> **证据说明**：`R1/google-ads-list-of-policies.md` **是 404 页**（正文逐字为 `# Sorry, this page can't be found.` / `This page doesn't exist in Advertising Policies Help. It may be deleted because the feature doesn't exist anymore, or the URL may be incorrect.`）。**该文件不作为政策内容证据**；但它的**导航框架仍然有效**（404 页由 Help Center 外壳渲染，导航为真实站点结构）。本节引用该文件时只引其导航，并已在此声明。可用的政策内容证据为 `google-ads-topic-list-of-ad-policies.md`、`google-ads-country-restrictions-6163740.md`、`google-ads-repeat-violations-strikes.md` 等。

#### 1.9.1 切了什么轴

**主轴 = 政策族（topic family），4 个一级栏目 + 每栏目下的子栏目：**

【原文】（导航逐字，取自 404 页外壳）
```
- List of ad policies
- Review process
- Verification and transparency
- Change log
```
【原文】（二级）
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
来源：`R1/google-ads-list-of-policies.md` 第 15–40 行（导航框架）→ https://support.google.com/adspolicy/answer/1316545

【判断】Google 的切轴是**"规则 / 流程 / 透明度 / 变更"四分**，而不是按内容危害分类：
- **规则本体**在 `List of ad policies` → `Advertising policies`
- **执行程序**独立成 `Review process`（`Approval process` / `Disapprovals and suspensions`）
- **可核验性**独立成 `Verification and transparency`
- **变更**独立成 `Change log`（并再分 `Upcoming and recent changes` / `Past changes`）

**"执行程序"与"变更记录"各占一级栏目，这是本报告唯一的编排。** 对比：Meta 把执行放在另一站点（`/enforcement/`）、GitHub 混在文档尾部、AWS 混在第 1.4 条里。指向：同上。

**次轴 = 广告政策条目，按字母序排列**（这才是"政策清单"本体）：
【原文】
```
...Copyrights
...Counterfeit goods
...Cryptocurrencies and related products
...Dangerous products or services
...Data collection and use
...Dating and Companionship
...Destination requirements
...Editorial
...Enabling dishonest behavior
...Financial products and services
...Gambling and games
...Healthcare and medicines
...Inappropriate content
...Lead form requirements
...Legal requirements
...Limited ad serving
...Misrepresentation
...Other restricted businesses
...Prediction Markets
...Restricted targeting in Personalized advertising
```
来源：`R1/google-ads-topic-list-of-ad-policies.md` 第 20–48 行 → https://support.google.com/adspolicy/topic/1626336

【判断】**这是本报告唯一按字母序排列规则库的样本**（GitHub 按主题、Meta 按危害、AWS 按产品、Stripe 按资格档、Google 按 A-Z）。**字母序意味着"规则之间无优先级"，且新增规则不需要决定归属** —— 代价是失去主题聚类。指向：同上。

【判断】**一条 Google 政策条目 = 一个标题 + 一个 answer ID URL**（`answer/6018015` 等），**answer ID 就是规则 ID**。这是本报告第四种规则标识体系（AWS 用十进制条款号、AMO 用十进制约号、GitHub 用 URL slug、Google 用数字 answer ID）。指向：第 20–48 行。

#### 1.9.2 一条规则的内部结构

**规则单位 = 独立 answer 文章**（每政策一条），文章内部结构以 `google-ads-country-restrictions-6163740.md` 为例可完整观测。

【判断】**规则内部结构 = 导语（适用范围句）+ 分节（每节一个后果面/条件面）**。该文的 6 个分节标题逐字为：`Recently added regions` / `Account access within embargoed regions` / `Refunds for existing accounts` / `Location targeting` / `Account support and optimization`（另有开头的主体清单）。**即一条 Google 规则可以按"账号 / 登录 / 退款 / 投放定向 / 支持"等**不同业务面**分节展开。** 指向：`R1/google-ads-country-restrictions-6163740.md` 全文。

**适用范围句（放在最前）**：
【原文】`The following article applies to all Google Ads products.`
来源：`R1/google-ads-country-restrictions-6163740.md` → https://support.google.com/google-ads/answer/6163740?hl=en

【判断】**Google 把"适用范围"写在文章第一行**，而同族的另一篇文章写的是语言效力：

【原文】`Google provides translated versions of the Advertising Policies Help Center, though they're not meant to change the content of the policies. The English version is the official language used to enforce Google Ads policies.`
来源：`R1/google-ads-repeat-violations-strikes.md` → https://support.google.com/adspolicy/answer/10922738?hl=en

【判断】**这是"语言版本效力"声明，与 Meta 的 `the US English version ... should be used as the primary document`（1.8.3）同构，但 Google 的措辞更硬：`The English version is the official language used to enforce`（英文版是执行时使用的官方语言）。** 两个系统都承认多语言版本的效力排序问题 —— 这是跨国平台共有的结构需求。指向：同上 vs `R1/meta-cs-index.md`。

#### 1.9.3 作用域如何表达（Google 的结构强项）

**(a) 法域作用域 = 制裁名单 + 地理标准 ID（独有）**
【原文】`Google must comply with sanctions imposed by the [United States Office of Foreign Assets Control (OFAC)]. As a result, Google Ads isn't available to advertisers in the following countries or territories (with criterion ID): Crimea (21120) / Cuba (2192) / So-called Donetsk People's Republic (DNR) (21113) / Iran (2364) / So-called Luhansk People's Republic (LNR) (21111) / North Korea (2408)`
来源：`R1/google-ads-country-restrictions-6163740.md` → https://support.google.com/google-ads/answer/6163740?hl=en

【判断】**三处独有结构**：
1. **法域的唯一依据是外部名单**：`sanctions imposed by the United States Office of Foreign Assets Control (OFAC)` —— **规则不自行认定国家，而是挂接一个外部法律名单**。对照 Stripe 同时点名 OFAC / Denied Persons List / Entity List 与 UN/EU/UK 四体系（1.6.3c）—— **Stripe 是多名单，Google 是单一名单。**
2. **每个法域条目带括号数字 `criterion ID`**：`Crimea (21120)` / `Cuba (2192)` / `Iran (2364)` / `North Korea (2408)`。**这是本报告唯一的"法域机器标识符"** —— 国家/地区在 Google 系统里是一个有数字 ID 的实体，可在定向逻辑中引用（见下）。
3. **对争议地区用 `So-called`（所谓的）前缀**：`So-called Donetsk People's Republic (DNR)` / `So-called Luhansk People's Republic (LNR)` —— **命名本身承载法律立场**（不承认其国家地位）。**这是本报告唯一在规则文本中通过称谓表达承认/不承认的写法。**

指向：同上。

**(b) 同一个法域禁令拆成 4 个"业务面"分节** —— 这是 Google 法域作用域的关键扩展：
【原文】`If you're based in a location that's recently become subject to OFAC sanctions, your Google Ads account will be suspended. Manager accounts based in embargoed countries or territories will be suspended, and their managed accounts may also be suspended.`（账号面）
【原文】`Even if your account is not based in one of the embargoed countries or territories, you could still be affected by the embargo. That's because when you're physically present in an embargoed country or territory, you won't be able to sign in to Google Ads.`（登录面）
【原文】`We'll try to provide refunds to affected Google Ads account owners with unused prepayment balances to the extent that we are legally allowed.`（退款面）
【原文】`Countries or territories subject to OFAC sanctions are not able to be targeted in Google Ads. If your campaigns target a country or territory that was recently added to the OFAC list, those campaigns will stop running.`（投放定向面）
【原文】`If you're located outside these regions but promote products or services based in the region, you're not eligible to receive customized support or account optimization.`（支持面）
来源：均出自 `R1/google-ads-country-restrictions-6163740.md` → https://support.google.com/google-ads/answer/6163740?hl=en

【判断】**同一个法域维度被展开成 5 个互不相同的规制面**：账号归属地 / 人的物理位置 / 退款资格 / 广告定向目标 / 服务支持资格。**这是本报告最完整的"法域作用域分解"**：
- **账号归属地** vs **人的物理位置**是两个独立维度（`Even if your account is not based in ... when you're physically present in ...`）
- **目标市场**（targeting）是第三个维度（`not able to be targeted`）
- **业务实际所在地**是第四个维度（`promote products or services based in the region` → 仅失支持资格，不封号）

**即 Google 承认"你在哪、你的账号在哪、你卖去哪、你的业务在哪"是四个不同的法域坐标，且各自的后果不同。** 对跨境电商业务，这四维分解是最有参考价值的结构。指向：同上五段。

**(c) 法域后果的绝对性（无例外条款）**
【原文】`If your account is affected by OFAC sanctions, we'll notify you by email when we suspend your account. No grace periods or exceptions are possible.`
来源：`R1/google-ads-country-restrictions-6163740.md` → 同一 URL

【判断】**`No grace periods or exceptions are possible.` 是本报告最绝对的一句后果声明** —— 比 PyPI 的"一律不可逆"（讲复审）更硬：它连**整改期与例外**都排除了。对照 AWS 的 `2 business days` 整改期、AMO 的 `a reasonable time frame`、npm 的 `without notice`（无通知期但有裁量）。指向：同上。

**(d) 申诉通道仍然保留**：
【原文】`If you believe your account shouldn't have been suspended, please use [this form] to request an appeal.`
来源：`R1/google-ads-country-restrictions-6163740.md` → 同一 URL

【判断】**"无例外"与"可申诉"并存** —— 即 Google 区分"实体规则不可例外"与"事实认定可复核"。**这是本报告唯一显式做出这一区分的系统。** 指向：同上。

**(e) 产品作用域**：【原文】`The following article applies to all Google Ads products.`（同一 URL）—— 即该篇声明全域适用；反过来说明**其他文章可以只适用于部分产品**（声明机制存在，但本篇不用）。

#### 1.9.4 兜底/其他类目

Google 的兜底以"命名类目"形式存在，而非 "Other"：
【原文】`Other restricted businesses`（政策条目名）
【原文】`Inappropriate content`（政策条目名）
【原文】`Limited ad serving`（政策条目名）
来源：`R1/google-ads-topic-list-of-ad-policies.md` 第 44、38、40 行 → https://support.google.com/adspolicy/topic/1626336

【判断】**`Other restricted businesses` 是本报告唯一一个类目名里直接含 `Other` 的规则类目。** 它承担"未单列的限制类业务"的兜底职责，并有独立 URL（`answer/6368711`），**是可引用的正式规则，不是脚注**。指向：第 44 行。

【判断】**`Limited ad serving` 是功能等同的"软兜底"**：不是禁止，而是限制投放量/位。对照 Meta 的 `warning screen` / `18 and older`（1.8.5）—— **两家都存在"允许但降级"这一中间档，但表达方式不同：Meta 用内容可见性档，Google 用投放量档。** 指向：第 40 行 + `R1/meta-cs-index.md`。

#### 1.9.5 严重等级/后果（Google 的 strike 是本报告最"计数精确"的一套）

**Google 的后果档链 = 警告（1 次）→ strike 1 → strike 2 → strike 3，且每档时长写死。**

【原文】`Strikes are issued to your Google Ads account when you repeatedly violate certain Google Ads policies. Note that no strikes are issued for the first policy violation. You will be able to receive a maximum of 3 strikes, and the penalties applied with each strike will progressively increase. Temporary account holds will be applied for the first and second strikes (for 3 and 7 days respectively), while the third strike will result in an account suspension.`
来源：`R1/google-ads-repeat-violations-strikes.md` → https://support.google.com/adspolicy/answer/10922738?hl=en

【判断】**档数与时长**：警告（0 天）→ strike 1 = `3 days` 临时账号冻结 → strike 2 = `7 days` → strike 3 = `account suspension`（无期限）。**这是本报告第二细的阶梯**（Meta 是 1/3/7/30 天六档 + 封号；Google 是 3/7 天 + 封号三档）。

【判断】**"首次违规不计 strike，只警告"是 Google 与 Meta 共有的设计**（Meta：`One strike: You'll get a warning since this is your first strike.`；Google：`no strikes are issued for the first policy violation`）。**两家都把"第一次"设为非惩罚档。** 指向：本节 + `R1/meta-ad-enforcement-restricting-accounts.md`。

**"警告只能用一次，且逐政策计数"（Google 独有）：**
【原文】`An account can receive a maximum of one warning and 3 strikes per policy violation.`
来源：`R1/google-ads-repeat-violations-strikes.md` → 同一 URL

【判断】**strike 与警告都是"逐政策"计数的**（`per policy violation`），而不是像 Meta 那样账号级累计。**这是两种根本不同的计数模型**：
- **Meta：账号级池**（`Two to six strikes` → 累计到账号，跨政策）
- **Google：政策级池**（每个政策各有一个"1 警告 + 3 strike"配额）

**对多品类经营的卖家，这个差别是决定性的：Google 下违规 A 政策不影响 B 政策的配额，Meta 下则共用同一个 strike 池。** 指向：同上 vs `R1/meta-ad-enforcement-restricting-accounts.md`。

**strike 制度的适用范围是被显式枚举的政策清单（Google 独有）：**
【原文】`This strike-based system applies to the following policies: Enabling dishonest behavior, Unapproved substances, Guns, gun parts and related products, Explosives, Other Weapons, Tobacco, Compensated sexual acts, Mail-order brides, Clickbait, Misleading ad design, Bail bond services, Call directories, forwarding, and recording services, Credit repair services, Binary options, and Personal loans.`
来源：`R1/google-ads-repeat-violations-strikes.md` → 同一 URL

【判断】**共 15 个政策被点名纳入 strike 制度** —— 即**其他政策即使重复违规也不走这套阶梯**。**这是本报告唯一"按政策清单划定等级制度适用范围"的结构**（Meta 用的是反向表述：`more severe policies`，举例说明但不给完整清单）。指向：同上。

**AI + 人工的判定分工（Google 独有）：**
【原文】`We use a combination of Google's AI and human evaluation to detect and remove ads which violate our policies and are harmful to users and the overall Google Ads ecosystem. Our enforcement technologies may use Google's AI, modeled on human reviewers' decisions, to help protect our users and keep our ad platforms safe. The policy-violating content is either removed by Google's AI or, where a more nuanced determination is required, it is flagged for further review by trained operators and analysts who conduct content evaluations that might be difficult for algorithms to perform alone, for example because an understanding of the context of the ad is required. The results of these manual reviews are then used to help build training data to further improve our machine learning models.`
来源：`R1/google-ads-repeat-violations-strikes.md` → 同一 URL

【判断】**Google 是全部证据中唯一在规则文档里描述"自动判定 + 人工复核 + 反馈训练"闭环的系统**。这条不属"等级"，但属"后果如何被决定" —— 它解释了为什么 Google 的等级可以逐政策精确计数（自动化判定使细粒度计数可运维）。**这是"结构选择受执行能力约束"的直接证据。** 指向：同上。

#### 1.9.6 变更历史（Google 独有：变更日志是一级栏目）

【原文】（导航）`- Change log` → `- Upcoming and recent changes` / `- Past changes`
来源：`R1/google-ads-list-of-policies.md` 第 23、40–43 行（导航框架）→ https://support.google.com/adspolicy/topic/3230816

【判断】**Google 是唯一把"变更日志"做成一级导航栏目的系统**，且**日志按时态二分：未生效/近期（Upcoming and recent）vs 已失效（Past）**。**即 Google 承认"已公布未生效"是一个独立状态** —— 这是本报告唯一显式建模"预告期"的版本机制。对照：GitHub 的 `30 days' notice`（时间承诺但无预告页）、TikTok 的 `On September 24, 2026, we are updating ... Check out the new Community Guidelines here`（页内预告句）、Stripe 的页顶单条 changelog。**只有 Google 把预告做成常设栏目。** 指向：同上。

**另有一条"政策生效日期"的独立文档族**：
【原文】`Regulators and enforcement dates`（`R1/google-ads-regulators-enforcement-dates.md` 文件名所示主题）
【原文】`[Change log](/adspolicy/topic/3230816?hl=en&ref_topic=1308156,)`
来源：后者出自 `R1/google-ads-list-of-policies.md` 第 23 行（导航）

【判断】**Google 把"监管机构 + 执法日期"作为独立文档**，即**法域监管变化被建模为需要跟踪的外部事件，而不是内嵌在规则里的限定词**（与 1.9.3a 的"挂接 OFAC 名单"策略一致）。指向：`R1/google-ads-regulators-enforcement-dates.md` 文件名 + 导航。

**无版本号**：Google 政策文章**使用 `Updated on <date>` 之类行内标记（本批证据中 Amazon 明确含 `Updated on Apr 6, 2026`；Google 各 answer 页的时间戳以 `hl=en` 语言参数区分版本，未见版本号）**。指向：`R1/amazon-ads-healthcare-GPSSMTEAA6AEWY3A.md` 的 `Updated on Apr 6, 2026`。

---

### 1.10 Amazon（基于 R1 证据）

> **⚠️ 取证警告（沿用父 agent 的核验结论，并已在本节遵守）**：`R1/amazon-*.md` 是 `read_page` 文本层产物。Amazon 把正文以**转义 JSON + 超长行**内嵌在 `.html` 中（实测 `amazon-ads-*.html` 普遍有单行 29,989 字符），**按行读取的抽取器会静默丢弃正文**。因此：
> - 本节的引用**全部取自 `.md` 文本层中肉眼可见的句子**；
> - **凡"页面上应有但文本层未见"的内容，一律写"结构可见、正文未取到"，不补写**。
> - 尤其：`Country-specific restrictions` 小节在本批 `.md` 中**只有标题与国名、无国别正文**（该内容位于 React 折叠组件内，抓取未展开）。

#### 1.10.1 切了什么轴

**主轴 = 政策文件族（policy article），由 hub 页按 6 组汇聚。**

【原文】（Program Policies hub 的页内导航）
```
On this page
General Policies
Intellectual Property
Product and Listing Requirements
Shipping
Tax
Optional Programs
See also
```
来源：`R1/amazon-program-policies-G521.md`（`On this page` 区块）→ https://sellercentral.amazon.com/gp/help/external/G521

【判断】**Amazon Seller Central 的切轴 = "卖家经营职能"**：一般政策 / 知识产权 / 商品与刊登要求 / 物流 / 税务 / 可选项目。**这是本报告唯一以"经营流程环节"切轴的规则库**（其他系统按危害、主题、产品、资格档、字母序切）。

**次轴 = 每个分节下平铺大量具名政策文章**（`General Policies` 一组即含 30+ 条）：
【原文】（节录，逐字）
```
A-to-z Claims Process for Property Damage and Personal Injury
Account Health Rating Program Policy
Agent policy
Amazon Brand Analytics Terms and Conditions
Amazon Brand Referral Bonus Terms and Conditions
Amazon Business Invoicing Policy
Amazon Currency Converter for Sellers Terms and Conditions
Amazon Imaging Services Terms and Conditions
Amazon Luxury program terms
Amazon Policy on reference prices
Amazon Renewed program policies
Amazon Renewed quality
Amazon Seller Code of Conduct
Amazon Services Provider – Program Policies
Amazon Stolen Goods Policy
Amazon Vine Terms and Conditions
Amazon Warehousing and Distribution terms and conditions
ASIN Creation Policy
Black-Owned Business badge
Commercial Liability Insurance Policy
Commercial Liability Insurance Requirements
Communication Guidelines
Conditions of Use
Countries accepted for seller registration
Customer Product Reviews Policies
Customer Service by Amazon Terms & Conditions
Customization Program Terms for Sellers
Dangerous Goods policy
Drop Shipping Policy
EU Value Added Tax (EU VAT) Registration Agreement
FBA Dangerous Goods Program Terms and Conditions
FBA inventory reimbursement policy
```
来源：`R1/amazon-program-policies-G521.md` → https://sellercentral.amazon.com/gp/help/external/G521

【判断】**这是本报告单页政策链接最多的规则索引**（`General Policies` 一组即 30+ 条，全页预估 100+）。**切轴实际上是"一议题一文章"**，与 npm 的 14 项同构但规模大一个数量级。指向：同上。

【判断】**Amazon 的类目名不带"危害"语义，而带"对象"语义**：`ASIN Creation Policy` / `Customer Product Reviews Policies` / `Drop Shipping Policy` / `Dangerous Goods policy` / `Amazon Stolen Goods Policy`。**即 Amazon 的规则命名以"被规制的业务对象"为主语**（ASIN、评论、代发、危险品、赃物），而非"被保护的权益"（GitHub 用 user safety / IP；Meta 用 hateful conduct）。指向：同上清单。

#### 1.10.2 一条规则的内部结构

**规则单位 = 独立帮助文章，文章内部按"业务面"分节，且带 `On this page` 目录。**

以 `Healthcare products and services`（Amazon Ads）为例，其 `On this page` 目录逐字为：
【原文】
```
On this page
Prohibited products and services
Health claims and comparative statements
Consumer healthcare products
Sexual wellness products
Prescription pharmaceuticals
Healthcare services
Country-specific restrictions
Updated on Apr 6, 2026
```
来源：`R1/amazon-ads-healthcare-GPSSMTEAA6AEWY3A.md` → https://advertising.amazon.com/help/GPSSMTEAA6AEWY3A

【判断】**单条规则文章的字段集 = 6 个业务面小节 + 1 个 `Country-specific restrictions` 小节 + 1 个 `Updated on <date>` 时间戳。** 这是本报告在**品类级规则**上最完整的字段集。

【判断】**`Country-specific restrictions` 是文章内的固定槽位，而不是独立文档** —— 即 **Amazon 把"国别差异"作为每条品类规则的附属小节**。对照 Stripe 把国别做成独立大节（1.6.1 轴 3）、AWS 做成表、Meta 做成独立 section（1.8.3）、Google 做成独立 answer 文章（1.9.3）。**五种载体，同一维度。** 指向：同上 vs 各系统对应处。

**⚠️ 正文未取到**：本批 `R1/amazon-ads-claims-substantiation-*.md` 的 `Country-specific restrictions` 小节**只有国名、无国别正文**。父 agent 已对原始 HTML 做 `mailing address` / `study and date` / `postal` 检索，**均 0 命中**（因其位于 React 折叠组件内）。**故此处记为"结构可见、正文未取到"，不作引用。** 另有 `R1/amazon-ads-claims-substantiation-country-restrictions.md`（26KB 解码件，由 R7-W3 产出）可供后续补充，本分片未使用。

**规则句式的三种形态（自 Amazon Seller Central 证据）：**

(a) **义务总纲 + 违规后果**：
【原文】`If you list products on Amazon, you must comply with all applicable laws, regulations, standards, and our policies related to those products and product listings.` / `The sale of illegal, unsafe, or other restricted products listed on these pages can lead to legal action, including civil and criminal penalties.`
来源：`R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md` → https://sellercentral.amazon.com/help/hub/reference/external/GX9VRVWH8HXTDTK7

(b) **"不要推定允许"的反向举证规则（Amazon 独有）**：
【原文】`Carefully review the Restricted Products policies before listing a product. Do not assume that a product is permitted because it is not listed in our "Examples of Prohibited Listings" or has an existing ASIN. If in doubt about whether a product may be sold, do not list it, and seek guidance from your legal counsel.`
来源：`R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md` → 同一 URL

【判断】**这是本报告唯一显式规定"未被列入不等于被允许"的条款**，且给出行动指令：`If in doubt ... do not list it, and seek guidance from your legal counsel`（存疑则不刊登，并咨询你自己的律师）。**即 Amazon 把"品类是否可售"的最终判断责任外推给卖家 + 卖家律师。** 对照 GitHub 的"兜底条款抓漏"、AWS 的"抽象判据"、Stripe 的"非穷尽声明" —— **只有 Amazon 把这个不确定性转化为卖家的作为义务。** 指向：同上。

同时它揭示了 Amazon 的兜底类目名：**`"Examples of Prohibited Listings"`** —— 明示为"示例"，故为开放集合。指向：同上。

(c) **"目的性错误 → 直接终止"的加重规则**：
【原文】`If listings are identified to be purposefully inaccurate, miscategorized, or deceptively described to circumvent any of Amazon's Category, product, and listing restrictions, sellers' accounts may be subjected to corrective actions, including but not limited to the immediate termination of selling privileges.`
来源：`R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md` → 同一 URL

【判断】**加重事由是"规避意图"（`purposefully ... to circumvent`）而非危害大小** —— 与 AMO 的 `intentionally or repeatedly violate`（1.2.5b）、AWS 的重复侵权（1.5.5）同构。**三个系统都把"故意规避"设为最高档事由。** 指向：同上。

**规则内部的"前置审批"要件（Amazon 独有）**：
【原文】`Certain categories require sellers to obtain pre-approval from Amazon before listing in those categories.` / `Certain categories require you to provide additional information or a supplemental guarantee before listing in those categories.`
来源：`R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md` → 同一 URL

【判断】**品类准入被建模为"前置审批 + 补充担保"两道门**，与 Stripe 的"逐产品审批"（1.6.5）同构。**注意：这两句用的是 `Certain categories`（某些品类），即该文档不枚举哪些品类 —— 门的存在是明文，门的名单在别处。** 指向：同上。

#### 1.10.3 作用域如何表达（Amazon 的关键结构）

**(a) 文档级法域横幅（本报告最清晰的单文档作用域标记）**
【原文】`This article applies to selling in: United States`
来源：`R1/amazon-program-policies-G521.md`、`R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md`（两文件同一位置）→ https://sellercentral.amazon.com/gp/help/external/G521

【判断】**Amazon 把作用域做成页面顶部的固定横幅 `This article applies to selling in: <国家>`**。**这是全部证据中最显式、最机器可读的"单文档作用域"声明。** 对照：Stripe 用国家节、AWS 用国家表、Meta 用独立 section、Google 用独立文章、GitHub 用 `versions: fpt` 字段（作用域却是账号计划而非国家）。**Amazon 是唯一把"本文档适用于哪个国家"写成一行固定文案的。** 指向：同上。

**(b) 语言选择器 = 国家-语言对**
【原文】
```
Select your preferred language
English - US
中文 - CN
한국어 - KR
Français - FR
Italiano - IT
हिंदी - IN
ไทย - TH
தமிழ் - IN
Tiếng Việt - VN
Deutsch - DE
Português - BR
中文 - TW
日本語 - JP
Español - ES
```
来源：`R1/amazon-program-policies-G521.md`、`R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md` → 同一 URL

【判断】**Amazon 的语言选择器标注为 `<语言> - <国家码>`**（`English - US` / `中文 - CN` / `中文 - TW`），**即语言维度与国家维度被绑定为一个选择项**。对照 Stripe 的 legal 索引是**两级**（先国家，后语言：Belgium → Nederlands / Français / Deutsch / English）。**两种不同的"国家 × 语言"建模方式：
- **Amazon：一维**（语言-国家对，扁平）
- **Stripe：二维**（国家 → 语言列表）

**对"同一规则在 A 国和 B 国是否不同"这个问题，Amazon 的一维建模意味着"换语言 = 换国家版本"，两者无法分离。** 指向：本节清单 vs `_evidence/R7/marketplace/stripe-legal-index.txt` 第 30–47 行。

**(c) 国家清单作为独立政策文章**
【原文】`Countries accepted for seller registration`（政策条目标题）
来源：`R1/amazon-program-policies-G521.md`（`General Policies` 组）→ https://sellercentral.amazon.com/gp/help/external/G521

【判断】**"哪些国家可注册卖家"是独立一篇文章**，与"哪些国家可售某品类"分离。**即注册国资格与销售国资格是两个独立维度。** 另有 `amazon-intl-sellers-G200404870.md`（`International sellers`）与 `amazon-taxes-regulations-global-selling-G201468380.md`（全球销售税务）── **Amazon 的跨境维度由多篇专门文章承载**。指向：同上 + 对应文件名。

**(d) 法域作为"合规义务来源"（而非规则限定词）**：
【原文】`Ads for healthcare products and services must follow all applicable local laws and regulations. Ads may be limited by placement, supply, or scheduling restrictions.`
来源：`R1/amazon-ads-healthcare-GPSSMTEAA6AEWY3A.md` → https://advertising.amazon.com/help/GPSSMTEAA6AEWY3A

【判断】**`must follow all applicable local laws and regulations`（转致当地法）+ `Country-specific restrictions`（本页国别小节）双轨并存** —— 即 Amazon 同时用"转致"和"枚举"两种法域表达。**这与 Stripe 的做法一致（转致兜底 + 国家节枚举），而与 GitHub/PyPI 只用转致不同。** 指向：同上。

#### 1.10.4 兜底/其他类目

**Amazon 的兜底类目名 = `Restricted Products` + `"Examples of Prohibited Listings"`**（见 1.10.2b）。

【原文】`For more information on how to appeal a decision, go to Additional information and resources for sellers about our Restricted Products policy.`
来源：`R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md` → https://sellercentral.amazon.com/help/hub/reference/external/GX9VRVWH8HXTDTK7

【原文】`Those participating in Fulfillment by Amazon (FBA), should also review the FBA Product Restrictions page which lists products that are not eligible for the FBA program.`
来源：`R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md` → 同一 URL

【判断】**Amazon 有三级"禁售"体系，分散在不同承载物上**：
1. **`Restricted Products` policy** —— 禁售总政策（有独立文章与申诉说明）
2. **`"Examples of Prohibited Listings"`** —— 禁售示例清单（明示为示例 = 开放集合）
3. **`FBA Product Restrictions`** —— **物流渠道级禁运清单**（不与"可否销售"同集）

**第 3 层是本报告唯一"销售资格"与"履约渠道资格"分离的结构** —— 一个商品可以合法销售但不能走 FBA。GitHub/PyPI/npm/Stripe 都没有这个维度。指向：同上。

**"未列入即允许"的明确否定**（见 1.10.2b）是 Amazon 兜底的核心 —— **它取消了兜底条款的"默认允许"含义**。指向：同一段落。

#### 1.10.5 严重等级/后果

**Amazon 不给等级编号，而是列举后果类型，并把分档变量写明。**

【原文】`Sellers who violate Amazon policies or applicable law may be subject to enforcement action, which can vary depending on the type of offense and account history.`
来源：`R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md` → https://sellercentral.amazon.com/help/hub/reference/external/GX9VRVWH8HXTDTK7

【判断】**这是本报告中对"分档变量"最简洁的表述：`the type of offense`（违规类型）+ `account history`（账号历史）** —— 两个变量。对照：Meta = severity + context + timing + 类目（4 个）；Google = 政策 ID + 次数（2 个）；AWS = 配合度 + 内容性质 + 累犯（3 个）；Stripe = 尽调结果（1 个）。

**后果类型（从文本可辨）= 4 类**：
1. `legal action, including civil and criminal penalties`（外部法律后果）
2. `corrective actions`（平台纠正措施）
3. `the immediate termination of selling privileges`（立即终止销售权）
4. `Additional information and resources for sellers about our Restricted Products policy`（申诉通道）

来源：同上两段。

【判断】**唯一被明写"立即"（`immediate`）的后果是终止销售权**，且触发条件是"故意规避"（见 1.10.2c）。**即 Amazon 不用刻度的档位，而用"是否故意"作为"是否立即"的开关。** 指向：同上。

**通知义务被明文化（Amazon 独有）**：
【原文】`Sellers are notified of violations using concise, violation-specific messaging that includes sufficient detail to easily identify which items are in violation and why, how to learn more, and to appeal.`
来源：`R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md` → 同一 URL

【原文】`Sellers who have had their selling privileges removed may appeal the decision in most cases.`
来源：`R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md` → 同一 URL

【判断】**Amazon 把这四要素写进规则文本**：`which items are in violation`（哪些商品）/ `why`（为什么）/ `how to learn more`（如何了解详情）/ `to appeal`（如何申诉）。对照 YouTube 的四要素（`What content was removed` / `Which policies it violated` / `How it affects your channel` / `What you can do next`，见 1.12.5）—— **两家用几乎相同的四要素定义"合格违规通知"，是本报告中最强的一处跨系统收敛。** 指向：同上 vs `R1/youtube-strike-basics.md`。

【判断】`may appeal the decision in most cases` 中的 **`in most cases`** 是本报告唯一对申诉权加限定语的表述（对比 PyPI 的"一律不可逆"、Google 的"无例外但可申诉"）。指向：同上。

**账号健康度作为前置度量（Amazon 独有）**：
【原文】`Account Health Rating Program Policy`（政策条目标题）
来源：`R1/amazon-program-policies-G521.md`（`General Policies` 组）→ https://sellercentral.amazon.com/gp/help/external/G521

【判断】**Amazon 有一条专门的 `Account Health Rating Program Policy`** —— 即**账号健康分是独立成文的制度**，是"账号历史"这一分档变量的载体。对照 eBay 的 `卖家级别`（1.7.5）—— **两家 marketplace 都用"持续评分"而非"违规计数"作为等级基座。这是 marketplace 与内容平台的系统性结构差异。** 指向：同上 + `R1/amazon-account-health-assurance-GGQY933W4RDPJT29.md` 文件名。

#### 1.10.6 变更历史

**Amazon 用文章级 `Updated on <date>` 时间戳，无版本号、无历史版本。**

【原文】`Updated on Apr 6, 2026`
来源：`R1/amazon-ads-healthcare-GPSSMTEAA6AEWY3A.md` → https://advertising.amazon.com/help/GPSSMTEAA6AEWY3A

【判断】**格式为 `Updated on Mon D, YYYY`**（与 PyPI/npm/AWS 的 `Month D, YYYY` 同族但多一个 `Updated on` 前缀）。**位置在文章末尾**（`On this page` 目录的末项），即**每篇文章各自带自己的更新时间**，而非全站统一。

【判断】**本批 Amazon 证据中未找到任何变更日志、旧版本链接、通知期条款或 supersession 声明。** 与 AWS 同属"最薄版本机制"一档。**记为未找到，不推断。** 指向：本批全部 `R1/amazon-*.md`。

---

### 1.11 Adyen（支付侧 · 风控文档索引）

> **证据限制说明**：`_evidence/R7/marketplace/adyen-risk-index.txt`（HTTP 200，151,367B raw / 6,819B 文本）**可用，但它是文档站点的导航索引页，不是受限业务清单**。真正想抓的 `adyen-prohibited-restricted.txt` **是 404**（HTTP 404，167B），故 Adyen 的"禁售/受限产品"规则结构**未取到**。本节只写索引页可证实的文档组织方式。

#### 1.11.1 切了什么轴

【原文】（`Risk management` 文档导航，逐字节录）
```
Risk management
Overview
Configure risk settings
RISK PROFILES
Create a risk profile
Configure your risk profile
Risk lists
Custom rules
Machine learning rules
Post-authorization rules
Risk field reference
Fraud results in API responses and webhooks
Run A/B test experiments
Other risk engine features
Automate submitting referrals
Referrals API reference
Skip risk rules
Control traffic
Data collection
Extra risk management
Address Verification System (AVS)
Dynamic 3D Secure
Case management
Shopper DNA
Monitor risk performance
Disputes
Understanding disputes
Dispute flow
Dispute reason codes and defense requirements
Dispute timeframes
Manage disputes
Chargeback guidelines
Accel & STAR chargebacks
```
来源：`_evidence/R7/marketplace/adyen-risk-index.txt` → https://docs.adyen.com/risk-management/

【判断】**Adyen 的"风控"切轴 = 配置步骤 × 引擎能力 × 运营流程**，且**以"可配置项"为单位而非"禁止项"为单位**：`Risk lists` / `Custom rules` / `Machine learning rules` / `Post-authorization rules` / `Risk field reference`。

**这是本报告唯一以"客户可配置的规则构件"为轴的"规则库"。** 即：**Adyen 把合规判断权交给商户自己配置（risk profile + rules），平台提供的是规则引擎的原语（field reference、rule types），而不是一张禁止清单。** 对照 Stripe 提供一张详细的禁止清单并由 Stripe 判定。**两种支付侧的规则组织范式：清单式（Stripe）vs 引擎式（Adyen）。** 指向：同上导航全文。

【判断】**唯一的"外部规则清单"入口是 `Risk lists`**（风险名单）—— 这对应制裁/黑名单场景，与 Google 的 OFAC 挂接（1.9.3a）同类，但 Adyen 把它建模为**可配置的数据表**而非文档中的国家枚举。指向：同上。

#### 1.11.2 — 1.11.6

**本节其余 5 个小节（规则内部结构 / 作用域表达 / 兜底类目 / 严重等级 / 变更历史）均记为「未找到」** —— 因为承载这些内容的规则文档（受限与禁售产品清单）本次抓取返回 404，索引页只提供导航分类名，不提供任何规则正文、字段、作用域限定词、兜底类目、等级或变更记录。

**明确区分**：这是**证据未取到**，不是**Adyen 缺少这些结构**。见第 4 章。
---

### 1.12 TikTok（基于 R1 证据）

TikTok 是**唯一在 URL 里带版本号**的系统，也是唯一把"允许在平台但禁止进入推荐流"建成**第三档**的系统。

> **证据说明**：`R1/tiktok-community-guidelines.md`（`SOURCE_URL: https://www.tiktok.com/community-guidelines/en/us/ (cgversion=2025H2update)`）与 `R1/tiktok-fyf-standards.md`（`(extracted from Remix __remixContext JSON; page is client-rendered)`）为可用证据。`R1/tiktok-community-guidelines-2026H2.md` 从 `?cgversion=2026H2update` 抓取，**服务端只渲染了 Overview 节，其余 11 节内容数组为空** —— 引用时已就此设限。`R1/tiktok-community-guidelines-updates.md` 是版本元数据的专项抽取件。

#### 1.12.1 切了什么轴

**主轴 = 主题（topic），7 个一级主题：**

【原文】（逐字节录，`Our Rules` 汇总段的分组标题）
```
**Safety and Civility**
**Mental and Behavioral Health**
**Sensitive and Mature Themes**
**Integrity and Authenticity**
**Regulated Goods, Services, and Commercial Activities**
**Privacy and Security**
**Content Moderation**
```
来源：`R1/tiktok-community-guidelines.md` 第 29、39、45、51、59、65、72 行 → https://www.tiktok.com/community-guidelines/en/us/

【判断】**7 个主题是显式命名并在页面上加粗出现的**（对比 Meta 索引页完全 flat 无标题、GitHub AUP 用编号节）。**TikTok 是"显式分组 + 组内枚举"的样本**，与 Meta 的"flat 27 项"、Google 的"字母序"构成三种索引哲学。指向：同上。

【判断】主题内的条目是**加粗的规则名 + 一句话规则**，例如 `**Hate Speech and Hateful Behavior: **We don't allow content that promotes hate or attacks people based on protected attributes like race, religion, gender, or sexual orientation.`（第 31 行）。**即 TikTok 的规则单元 = "规则名：一句话禁令"**，规则名与规则句绑定在同一行。

【判断】**TikTok 的 `Content Moderation` 是一个主题，不是一个执行章节**（第 72 行）—— 与 Google 的 `Review process` 一级栏目（1.9.1）、Meta 的独立 enforcement 站点（1.8.5）结构类似但归入同一文档。

**第三轴（TikTok 独有）= 分发渠道（platform vs For You feed）**：
【原文】`You're in the right place if you're wondering: What's allowed on TikTok / What's not allowed on TikTok / What's not allowed in the For You feed (FYF)`
来源：`R1/tiktok-community-guidelines.md`（Overview 节）→ https://www.tiktok.com/community-guidelines/en/us/

【判断】**TikTok 把"是否进入推荐流"作为与"是否允许"并列的第三个问题**，并单独维护一份 FYF 标准（`R1/tiktok-fyf-standards.md`，SOURCE 为 `/community-guidelines/en/fyf-standards/`）。

**即 TikTok 的后果空间是三值而非二值：禁止 / 允许但不可推荐 / 允许且可推荐。** 对照 Meta 的 `warning screen` / `18 and older`（内容可见性降级，1.8.5）与 Google 的 `Limited ad serving`（投放量降级，1.9.4）—— **三家都有"降级而非禁止"档，但 TikTok 的降级维度是"分发/推荐"，Meta 是"观看门槛"，Google 是"投放量"。** 指向：同上 + `R1/tiktok-fyf-standards.md`。

#### 1.12.2 一条规则的内部结构

**规则单位 = `We don't allow ...` 一句话 + （分类下）`More information` 定义区。**

【原文】`We've organized our Community Guidelines by topic to make information easier to find. Under each category, you'll find a "More information" section. That's where we define key terms, answer common questions, and share helpful examples. These examples are meant to guide you, but they don't cover every situation.`
来源：`R1/tiktok-community-guidelines.md`（Overview 节）→ https://www.tiktok.com/community-guidelines/en/us/

【判断】**TikTok 的规则内部字段 = 2 个**：
1. **规则句**（`We don't allow ...`）
2. **`More information` 区**（术语定义 + FAQ + 示例）

**这是"规则 + 释义"二段式**，与 Meta 的"Policy Rationale + Do not post"（1.8.2）同构，**区别在于 Meta 的 Rationale 在前（先讲目的）、TikTok 的 More information 在后（后给定义与例子）**。指向：同上 vs `R1/meta-cs-hate-speech.md`。

**两种句式并存**（可对比同一主题下的两条）：
【原文】`**Harassment and Bullying: **We don't allow content that harasses or bullies others, including degrading remarks about appearance, doxing, sexual harassment, or coordinated abuse. We allow commentary about political figures which may be critical, but remove content that crosses into severe harm.`
来源：`R1/tiktok-community-guidelines.md` 第 37 行 → 同一 URL

【判断】**这一条内含"禁止 + 明确允许 + 允许到某点为止"三段**：`We don't allow ...`（禁）/ `We allow commentary about political figures which may be critical`（明示允许）/ `but remove content that crosses into severe harm`（临界点）。**即 TikTok 在单条规则里同时写出了"红线"与"保护带"，并用 `severe harm` 作为转换点。** 对照 Meta 的意图例外（1.8.4）、GitHub 的双用途要件（1.1.5）—— **三家都用"某点之前允许、之后禁止"的连续判据，但 TikTok 把这条连续性写在规则句内，Meta 写在 Policy Rationale 段，GitHub 写在从句。** 指向：第 37 行。

**"示例非穷尽"的显式声明（TikTok 与 Stripe/Amazon 共有）**：
【原文】`These examples are meant to guide you, but they don't cover every situation.`
来源：`R1/tiktok-community-guidelines.md`（Overview 节）→ 同一 URL

#### 1.12.3 作用域如何表达

**(a) 法域作用域 = 由 URL 路径承载（TikTok 独有）**
【原文】`Source: https://www.tiktok.com/community-guidelines/en/us/  (cgversion=2025H2update)`
来源：`R1/tiktok-community-guidelines.md` 头部元数据行

【判断】**TikTok 的社区准则 URL 含 `/en/us/` 路径段** —— 即**语言 + 国家是 URL 的一等组成部分**，每个国家/语言可能有各自的准则版本。**这是本报告唯一用法域做 URL 路径的系统。** 对照 Amazon 的页顶横幅（1.10.3a）、Stripe 的国家节（1.6.1）、AWS 的国家表（1.5.3b）—— **TikTok 把作用域放在"资源标识符"层，是最彻底的表达。** 指向：同上。

【判断】**本次证据只取到 `/en/us/` 一个版本**，因此**无法证实"其他国家的 TikTok 准则是否与美版不同"**。结构上路径支持分版，内容上未取到差异。**如实记为：机制可见、分版内容未取到。** 指向：同上。

**(b) 版本作用域 = 由 URL 查询参数承载（TikTok 独有）**
【原文】`Source: https://www.tiktok.com/safety/en/policies-and-engagement/overview?cgversion=2026H2update`
来源：`R1/tiktok-community-guidelines-2026H2.md` 头部元数据行

【判断】**`?cgversion=2025H2update` / `?cgversion=2026H2update` 是可寻址的版本标识**。**这是全部证据中唯一"用查询参数定位规则版本"的系统** —— 意味着**旧版本与新版本可同时在线上被 URL 访问**。对照 npm 的"git 历史链接"（可回溯但需离开站点）、PyPI 的"supersession 横幅"（旧文在线上但无版本参数）、Google 的"Past changes"栏目（有归档但无版本号参数）。**TikTok 是唯一把版本做成 URL 维度的。** 指向：同上。

**(c) 年龄作用域 = 独立主题（TikTok 独有）**
【原文】`**Age Restrictions and Safety Features**`
来源：`R1/tiktok-community-guidelines.md` 第 129 行 → https://www.tiktok.com/community-guidelines/en/us/

【原文】`**Youth Safety Enforcement**`
来源：`R1/tiktok-community-guidelines.md` 第 143 行 → 同一 URL

【判断】**TikTok 把年龄限制做成独立主题节（而非散落的规则限定词）**，且另有一节专讲未成年人执法。对照：npm 的 13 岁写在资格条款里（1.4.3d）、Meta 的 18+ 是内容可见性档（1.8.5）、AMO 无年龄维度。**TikTok 是唯一把"年龄"提升为类目维度的系统，且区分"限制"与"执法"两节。** 指向：第 129、143 行。

**(d) 账号类型作用域（TikTok 独有）**
【原文】`**News and Government, Politician, and Political Party Accounts**`
来源：`R1/tiktok-community-guidelines.md` 第 1219 行 → 同一 URL

【原文】`**LIVE Features and Monetization**` / `**LIVE Commercial Content**` / `**LIVE Gaming**`
来源：`R1/tiktok-community-guidelines.md` 第 1252、1261、1267 行 → 同一 URL

【判断】**TikTok 为特定账号类型（新闻/政府/政客/政党）与特定功能（LIVE）设专门规则节**。**即"账号身份"与"使用哪个功能"都是作用域维度。** 对照 Meta 的 `Account Integrity` / `Authentic Identity Representation`（按主题而非按账号类型）、Google 的 `Verification and transparency` 栏目。指向：上述行号。

#### 1.12.4 兜底/其他类目

**本批证据中未出现名为 "Other" 的类目。**

【判断】TikTok 的兜底以**三处显式开放声明**承担：
1. `These examples are meant to guide you, but they don't cover every situation.`（Overview，示例非穷尽）
2. `This list isn't complete.`（**注**：此句出自 `R1/youtube-strike-basics.md` 对 YouTube 的描述，**不是 TikTok 原文**；TikTok 对应声明为第 1 条）
3. `**Content Moderation**` 主题本身承担"未列举情形的处理"说明职责（第 72 行）

【判断】**TikTok 的 `Content Moderation` 主题是兜底的结构性载体** —— 它不讲"禁什么"，而讲"如何判断与处理"。对照 Meta 的 `Locally Illegal Content` + `User Requests` 两个元 section（1.8.4）、GitHub 的 AUP 第 11 节（1.1.4）。**三家都用"元类目"承担兜底，但命名不同：TikTok 用流程名、Meta 用请求类型名、GitHub 用价值名（User Protection）。** 指向：第 72 行。

**另有一处"严重违规"的封闭枚举（区分兜底与枚举）**：
【原文】`**Severe violations include:**`
来源：`R1/tiktok-community-guidelines.md` 第 1208 行 → https://www.tiktok.com/community-guidelines/en/us/

【判断】**`Severe violations include:` 是一个显式的"最重档清单"引导句**，其后续内容本批证据未展开。**注意它是 `include`（包含）而非 `are`（即是）—— 即该枚举同样是开放集合。** 指向：第 1208 行。

#### 1.12.5 严重等级/后果

**TikTok 本批证据中未见 tier/等级数字**，但存在可辨识的**三档后果空间**：

| 档 | 表达位置 | 原文依据 |
|---|---|---|
| 禁止（不可发布） | 各主题规则句 | `We don't allow ...`（第 37 行等） |
| 允许但不可推荐 | 独立 FYF 标准文档 + Overview 三问 | `What's not allowed in the For You feed (FYF)`（Overview） |
| 严重违规（最重档前提） | 专门清单 | `**Severe violations include:**`（第 1208 行） |

【判断】**TikTok 的中间档（FYF 降级）在结构上等价于 Meta 的 `warning screen` / Google 的 `Limited ad serving`**，但**它是唯一被建成独立文档 + 独立 URL 的降级档**（`/community-guidelines/en/fyf-standards/`）。**即"降级规则"与"禁止规则"在 TikTok 是两份并列文档，在 Meta/Google 是同一文档内的限定词。** 指向：`R1/tiktok-fyf-standards.md` SOURCE 行 + `R1/tiktok-community-guidelines.md` Overview 节。

**未找到**：TikTok 的 strike 计数、等级编号、处罚时长。**记为未找到，不推断。**

#### 1.12.6 变更历史（TikTok 的版本机制是本报告最完整的）

**TikTok 每个 CG section 都带 5 个版本元数据字段，且有明确的"下一版本"。**

【原文】（`R1/tiktok-community-guidelines-updates.md` 抽取的元数据，逐字）
```
## Live version (default URL, no cgversion param)

version: 2025H2update
versionName: 2025 August

lastUpdate (verbatim, all 12 sections):
"On September 24, 2026, we are updating our Community Guidelines so you can continue to create, discover, and share safely on TikTok. Check out the new Community Guidelines here."

Released August 14, 2025

Effective September 13, 2025

## Next version (?cgversion=2026H2update)

version: 2026H2update
versionName: 2026 August
```
来源：`R1/tiktok-community-guidelines-updates.md` → https://www.tiktok.com/community-guidelines/

【判断】**TikTok 的版本元数据字段集 = 6 个，是本报告最完整的一套**：
1. **`version`** —— 机器标识符，格式 `<年><半年>update`（`2025H2update`）—— **本报告唯一的"结构化版本号"**
2. **`versionName`** —— 人类可读版本名（`2025 August`）
3. **`lastUpdate`** —— **页内预告句**（见下）
4. **`Released`** —— 发布日（`August 14, 2025`）
5. **`Effective`** —— 生效日（`September 13, 2025`）
6. **下一版本标识**（`2026H2update` / `2026 August`）

**这是全部证据中唯一同时区分"发布日"与"生效日"的系统**（其他系统只有一个日期或没有日期），也是唯一有**预测性版本名**（把下一版的名字先公开）的系统。指向：同上。

**【原文】页内预告句（`lastUpdate` 的值，逐字，12 个 section 全部相同）**：
`On September 24, 2026, we are updating our Community Guidelines so you can continue to create, discover, and share safely on TikTok. Check out the new Community Guidelines here.`

来源：`R1/tiktok-community-guidelines-updates.md` → 同一 URL

【判断】**TikTok 把"未来生效日期"作为每条 section 的 `lastUpdate` 字段值** —— 即**这个字段承载的不是"上次更新何时发生"，而是"下次更新何时生效"**。**这是一个字段语义的反转**：其他系统的 last-updated 都指向过去（PyPI `February 13, 2025`、npm `March 10, 2022`、AWS `July 1, 2021`、Stripe `2026-05-13`、Meta `Today`），**只有 TikTok 指向未来**。指向：同上。

【判断】该句在 12 个 section 中逐字相同 —— **即预告是全站级的，不是逐 section 的**，但字段在每节都渲染一次（冗余但保持一致）。指向：同上。

**"同一规则的两个版本同时在线上"**：`?cgversion=2026H2update` 可访问 2026 版（本批证据只取到其 Overview，其余 11 节内容为空 —— 说明新版是**渐进发布**状态）。指向：`R1/tiktok-community-guidelines-2026H2.md` NOTE 行。

---

### 1.13 YouTube（基于 R1 证据）

YouTube 的 strike 制度是本报告**规则最细、时间刻度最全**的一套，且**它明确把"内容移除"与"内容移除 + strike"分开**。

#### 1.13.1 切了什么轴

**主轴 = 危害主题，6 个一级节，且包含一个"例外"节。**

【原文】（`R1/youtube-community-guidelines-full.md` 的一级/二级标题逐字）
```
# YouTube's Community Guidelines
## Spam & deceptive practices
## Sensitive content
## Violent or dangerous content
## Regulated goods
## Misinformation
## Educational, Documentary, Scientific, and Artistic (EDSA) content
## Was this helpful?
```
来源：`R1/youtube-community-guidelines-full.md` 第 5–123 行 → https://www.youtube.com/howyoutubeworks/policies/community-guidelines/

【判断】**YouTube 的 6 节里有 5 节是危害类目，第 6 节 `Educational, Documentary, Scientific, and Artistic (EDSA) content` 是"例外/豁免"节。** **这是本报告唯一把"例外"提升为与危害类目同级的一级节的系统。** 对照：GitHub 把例外写成从句（1.1.3d）、PyPI 写成 Note 段（1.3.3d）、Meta 写成 `Notwithstanding` 块（1.8.2）、TikTok 写在规则句内（1.12.2）。**YouTube 把 EDSA 独立成节，且有固定缩写名。** 指向：第 113 行。

【判断】**`Was this helpful?` 也是一个二级标题**（第 123 行）—— **即用户反馈控件被抽成了文档结构的一部分**，与 eBay 的 `文章预计阅读时间`（1.7.1）同类：**两个系统都把"文档消费行为"的元数据/控件纳入了政策页的结构。** 指向：第 123 行 + `_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt` 第 173 行。

#### 1.13.2 一条规则的内部结构

**规则族被显式声明为"非穷尽"，且区分"因 CG 移除"与"因其他原因移除"。**

【原文】`[Community Guidelines] are the rules of the road for how to behave on YouTube. These policies apply to all types of content on our platform, including unlisted and private content, comments, [links], posts, and thumbnails. This list isn't complete. If your content violates our Community Guidelines, your channel may get a strike.`
来源：`R1/youtube-strike-basics.md` → https://support.google.com/youtube/answer/2802032

【判断】**三个结构要点**：
1. **作用域被逐类列举**：`all types of content ... including unlisted and private content, comments, links, posts, and thumbnails` —— **涵盖非公开内容（unlisted/private）是本报告唯一一处**（其他平台的作用域默认是"公开内容"）。**对内容治理而言这是关键差别：非公开内容也被审。**
2. **`This list isn't complete.`** —— 显式非穷尽声明。
3. **后果是模态的**：`may get a strike`（`may`，非必然）。

指向：同上。

**"移除 ≠ strike"的分离（YouTube 独有）：**
【原文】`**Note:** We may remove content for reasons other than Community Guidelines violations. For example, a first-party [privacy complaint] or a court order. In these cases, your channel won't get a strike.`
来源：`R1/youtube-strike-basics.md` → 同一 URL

【判断】**这是本报告唯一明确区分"移除内容"与"施加 strike"两个动作的系统**，并给出两个法定/准法定移除事由（`a first-party privacy complaint` / `a court order`）。**即 YouTube 的后果有两个独立坐标轴：内容是否被移除（是/否）× 是否计 strike（是/否）。** 对照：GitHub 的 5 项响应清单中"移除内容"与"暂停账号"并列（1.1.5）、Meta 的 strike 与移除同步（1.8.5）、AWS 的移除不含 strike 概念。**只有 YouTube 承认"移除但无责"这一格。** 指向：同上。

**违规通知的 4 要素（与 Amazon 收敛）：**
【原文】`We'll also tell you: What content was removed / Which policies it violated (for example [harassment] or [violence]) / How it affects your channel / What you can do next`
来源：`R1/youtube-strike-basics.md` → 同一 URL

【判断】**与 Amazon 的 `which items are in violation and why, how to learn more, and to appeal`（1.10.5）几乎同构** —— 两家独立演化出同一套"合格违规通知"四要素。**这是本报告中最强的一处跨系统结构性收敛（marketplace 与内容平台在通知义务上趋同）。** 指向：同上 vs `R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md`。

#### 1.13.3 作用域如何表达

**(a) 内容类型作用域**（见 1.13.2）：`all types of content ... including unlisted and private content, comments, links, posts, and thumbnails`。

**(b) 语言作用域**：本批 YouTube 证据未见语言效力声明（对比 Google Ads 的 `The English version is the official language used to enforce Google Ads policies`，1.9.2）。**注意：YouTube 与 Google Ads 同属 Google，但本批证据中只有 Ads 侧出现该声明。记为：本批证据未找到，不等于不存在。** 指向：`R1/google-ads-repeat-violations-strikes.md` vs 本批 `R1/youtube-*.md`。

**(c) 产品/频道类型作用域（YouTube 独有）**：
【原文】`If your Official Artist Channel gets a Community Guidelines strike, the channel will be suspended and become a standard channel.`
来源：`R1/youtube-strike-basics.md` → https://support.google.com/youtube/answer/2802032

【判断】**特定频道类型（`Official Artist Channel`）有专属后果**：strike → **降级为普通频道**（不是封禁）。这是本报告唯一"降级频道等级"的后果，与 TikTok 的账号类型规则节（1.12.3d）同类但后果更具体。指向：同上。

**(d) 高级功能的独立准入（YouTube 独有）**：
【原文】`A strike may also result in losing access to [advanced features].`
来源：`R1/youtube-strike-basics.md` → 同一 URL

【判断】**"高级功能"是独立于频道存续的第二层资格** —— strike 可以只剥夺功能而不封频道。对照 Meta 的 `restricted from creating ads and using Facebook Live`（1.8.5）—— **两家都有"功能级处罚"层。** 指向：同上。

#### 1.13.4 兜底/其他类目

**YouTube 的兜底 = `This list isn't complete.`（显式非穷尽）+ `EDSA` 例外节（反向兜底）。**

【判断】**`This list isn't complete.` 是本报告措辞最简的兜底声明**，且**位置极靠前**（规则族介绍段末尾），而 GitHub/PyPI/Stripe 的同类声明都在文档尾部。**位置差异意味着 YouTube 把"清单不完整"作为读者进入规则前的预设，而非读完后的免责。** 指向：`R1/youtube-strike-basics.md`。

【判断】**EDSA 节是"反向兜底"**：不是"还有哪些被禁"，而是"哪些本来被禁的其实可能被允许"。**这是本报告唯一把例外做成一级类目的系统**（见 1.13.1）。指向：`R1/youtube-community-guidelines-full.md` 第 113 行。

**未找到**：名为 "Other" 的类目。**记为未找到。** 指向：本批 `R1/youtube-*.md`。

#### 1.13.5 严重等级/后果（本报告最细的时间刻度）

**YouTube 的等级 = 警告 → 3 次 strike，每一步都有明确时长与失效规则。**

**第 0 档 · 警告（可被培训消掉）**
【原文】`We understand mistakes happen and you don't mean to violate our policies — that's why the first violation is typically only a warning. To have this warning expire after 90 days, you can take an optional [policy training]. However, if your content violates the same policy within that 90 day window, the warning may not expire and your channel may be given a strike.`
来源：`R1/youtube-strike-basics.md` → https://support.google.com/youtube/answer/2802032

【原文】`If you complete an optional policy training, your warning will expire after 90 days. The 90-day period starts from when the training is completed, not when the warning is issued. If you violate a different policy after completing the training, you will get another warning.`
来源：`R1/youtube-strike-basics.md` → 同一 URL

【判断】**YouTube 的警告机制有 4 个独有结构件**：
1. **警告可通过"完成政策培训"消掉** —— **这是本报告唯一"以教育行为换取免责"的机制**（对照 Amazon 的 `supplemental guarantee`、Stripe 的 `proof of relevant licenses` 是**资质**而非**学习**）。
2. **90 天起算点是"完成培训时"，不是"发出警告时"** —— 起点被明确定义。
3. **同一政策内再犯 → 警告不失效并直接给 strike；不同政策再犯 → 只给新警告** —— **即"是否升级"取决于政策是否相同**（与 Google Ads 的"逐政策计数"同构，1.9.5）。
4. **并非所有警告都可培训**：`Note: Not all Community Guidelines warnings are eligible for policy trainings.`

指向：同上两段。

**第 1 档 · First Strike（停权 1 周 + 功能清单）**
【原文】`If we find your content doesn't follow our policies for a second time, you'll get a strike. This strike means you will not be allowed to do the following for 1 week: Upload videos or live streams / Start a scheduled live stream / Schedule a video to become public / Create a Premiere / Add a trailer to an upcoming Premiere or live stream / Create custom thumbnails or posts / Create, edit, or add collaborators to playlists / Add or remove playlists from the watch page using the "Save" button`
来源：`R1/youtube-strike-basics.md` → 同一 URL

【原文】`Your scheduled public content is set to "private" for the penalty period duration. You have to reschedule it when the freeze period ends.`
【原文】`**Note:** Penalty starts from the date of acknowledgement.`
【原文】`After the 1-week period, we restore full privileges automatically, but the strike remains on your channel for 90 days.`
来源：`R1/youtube-strike-basics.md` → 同一 URL

【判断】**本报告唯一逐项列出"被剥夺的具体能力"的处罚**（8 项功能），且**包含"已排定的公开内容被改为 private"这一被动副作用**。**且起算点被明确定义为 `the date of acknowledgement`（知悉日）而非处罚日。** 这三处（能力枚举 / 被动副作用 / 起算点）在全部证据中没有对应物。指向：同上。

**第 2 档 · Second Strike（2 周）**
【原文】`If you get a second strike within the same 90-day period as your first strike, you will not be allowed to post content for 2 weeks. If there are no further issues, after the 2-week period, we restore full privileges automatically. Each strike will not expire until 90 days from the time it was issued.`
来源：`R1/youtube-strike-basics.md` → 同一 URL

**第 3 档 · Third Strike（频道永久移除）**
【原文】`3 strikes in the same 90-day period may result in your channel being permanently removed from YouTube. Each strike will not expire until 90 days from the time it was issued.`
来源：`R1/youtube-strike-basics.md` → 同一 URL

【原文】`**Note:** Deleting your content doesn't remove a strike. We may also issue a Community Guidelines strike on deleted content.`
来源：`R1/youtube-strike-basics.md` → 同一 URL

【判断】**三个关键设计**：
1. **"3 次"必须落在同一个 90 天窗口内** —— 即 strike 不是无限累计，而是**滑动窗口内计数**。对照 Meta 的 1 年过期 + 90 天/4 年回溯（1.8.5）、Google 的逐政策 1 警告 + 3 strike 无窗口（1.9.5）。**YouTube 是唯一用"窗口内计数"的。**
2. **每次 strike 各自 90 天失效**（`Each strike will not expire until 90 days from the time it was issued`）—— 即第三次 strike 也可能只停留 90 天。
3. **删除内容不能消 strike**（`Deleting your content doesn't remove a strike`）—— **本报告唯一显式封堵"销毁证据"路径的条款。**

指向：同上。

**"单次严重违规直接终止"（与 Meta 同构）**：
【原文】`Sometimes a single case of severe abuse will result in [channel termination] without warning.`
来源：`R1/youtube-strike-basics.md` → 同一 URL

【原文】`Repeated violations of our policies– or a single case of severe abuse– may still result in the termination of your account. We may prevent repeat offenders from taking trainings in the future.`
来源：`R1/youtube-strike-basics.md` → 同一 URL

【判断】**与 Meta 的 `In some cases, a violation may be severe enough ... that we'll disable your account ... after one occurrence`（1.8.5d）同构** —— **两家都设了"跳过阶梯"的最重档**。另有一处独有：**屡犯者可能被剥夺接受培训的资格**（`We may prevent repeat offenders from taking trainings in the future`），即**教育免责权本身可以因累犯而丧失**。指向：同上。

**三系统等级对照（本报告的核心可比结论之一）**：

| | 档数 | 起算/失效 | 计数模型 | 跳过阶梯 |
|---|---|---|---|---|
| **Meta** | 警告 + 6 档（1/2-6/7/8/9/10+） | strike 1 年后过期；90 天 / 4 年回溯不计 | **账号级累计** | 有（`after one occurrence`） |
| **Google Ads** | 警告 + 3 strike（3d/7d/封号） | 未述窗口 | **逐政策配额**（每政策 1 警告 + 3 strike） | 未述 |
| **YouTube** | 警告 + 3 strike（7d/14d/频道移除） | **同一 90 天窗口内计数**；各 strike 90 天失效 | **窗口内计数 + 同政策升级判定** | 有（`a single case of severe abuse`） |

来源：分别为 `R1/meta-ad-enforcement-restricting-accounts.md` + `R1/meta-ad-enforcement-counting-strikes.md`、`R1/google-ads-repeat-violations-strikes.md`、`R1/youtube-strike-basics.md`。

【判断】**三家都用"警告 + strike"骨架，但计数模型完全不同**：账号级池 / 逐政策配额 / 窗口内计数。**这意味着"同样违规 N 次"在三家会导致完全不同的后果** —— 这是本报告对跨平台合规最直接可操作的结构发现。指向：上表三行来源。

#### 1.13.6 变更历史

**本批 YouTube 证据中未找到版本号、变更日志或生效日期。**

【判断】`R1/youtube-strike-basics.md`、`R1/youtube-community-guidelines-full.md`、`R1/youtube-community-guidelines-overview.md` 三份证据中**均未出现** `Last updated` / `version` / `CHANGE LOG` / 生效日期。
- **`R1/youtube-policy-updates.md`** 文件名暗示 YouTube 有一份政策更新页，但本分片**未读取该文件**，故**不引用**。
- **对照**：**YouTube 与 Google Ads 同属 Google，但 Ads 侧有 `Change log` 一级栏目（1.9.6），YouTube 侧本批证据中没有对应结构。** 这就是"同一公司内部两套版本机制"的实例。

【判断】记为**未找到**，并明确：**这是本批证据的覆盖问题，不是 YouTube 不存在变更机制的结论。** 指向：本批 `R1/youtube-*.md`。

---

## 2. 对照总表

13 个系统逐行。**空格内容为「未找到」时一律写出，不留空白、不推断。**

| 系统 | 主切轴 | 是否多轴 | 规则内部字段数 | 作用域表达位置 | 兜底类目名 | 后果档数 | 版本机制 |
|---|---|---|---|---|---|---|---|
| **GitHub** `§1.1` | 文档法律性质（6 分组）→ 行为主题（AUP 11 节）→ 单主题拆页 | **是（4 轴）**：文档类型 / 行为主题 / 子页 / 产品合同 | **0**（规则=无编号 bullet）；文档级 4 字段（`title` / `redirect_from` / `versions` / `category`） | 文档 front-matter 字段 `versions: fpt: '*'`（**账号计划，非法域**）+ 正文限定词（点名美国 FTC 1 处）+ 另立文档 | 无 named Other；三重兜底：`and other limitations`（枚举尾）/ AUP 第 11 节 `User Protection` / CG 的 `not intended to be a complete list` | **5**（内容 4 项 + 账号 1 项，flat 无门槛，措辞 `some of the ways we may respond`） | `redirect_from`（URL 沿革 4/2/6 条）；无版本号、无 changelog；ToS 承诺 `30 days' notice of material changes`；无痕覆盖 |
| **Mozilla AMO** `§1.2` | 扩展生命周期/合规维度（8 节），十进制多级编号树 | 是：节 × 编号深度；6.2.1/6.2.2 按 **Firefox 版本**分支 | **0**（规则=无编号陈述句）；**文档级 3 字段**：`Tags`（仅 3 个标签）/ `Contributors`（9 具名 GitHub 账号）/ `Last update`（具名 + 日期） | 正文限定词 4 种：分发渠道（`listed on addons.mozilla.org` vs `whether hosted on addons.mozilla.org or not`）、法域（**美国为基准** + 其他法域保留）、部署环境（企业策略可豁免同意）、品类主语（Themes / userScripts / Add-ons） | 无 named Other；`In general, developers are free to maintain their add-ons in the manner they choose`（默认允许）+ `The following requirements are of particular importance`（清单非穷尽）+ `demonstrably safe`（开放判据） | **3 类作用对象**（`affected versions` < `entire add-ons` < `developer's account`）；义务强度 `must` / `should` 2 档；`blocking may be immediate` 由**故意/重复/失联**触发 | **全证据最完整**：`Contributors` + `Last update: bacharakis / Apr 30, 2026`；无版本号、无 diff、无行级历史 |
| **PyPI / PSF** `§1.3` | GitHub 同源两轴（flat 清单 + 单主题节）；**目录字母序、正文主题序** | 是（2 轴，但 fork 后轴名不变） | **0**（规则=bullet）；文档级：`Superseded` 状态、CC-BY-4.0、日期 | 定义句（`Acceptable Content is restricted to Python packages and related information`）+ 法域转致 + **出口管制点名 `Wasserman Munitions List` / 15 CFR part 772** + `if I am subject to United States law` 条件触发 | `and other limitations`（fork 自 GitHub）、`significantly harms other users`（降级为散文）、**新增 `is off-topic`** | **3**（`suspension` / `termination` / `removal of content`）—— 砍掉了 GitHub 全部 3 项可见性处罚 | **唯一四项齐备**：`Superseded by PyPI Terms of Service: February 25, 2025`（旧文仍在线）+ fork 出处声明 + `February 13, 2025` + CC-BY-4.0；底层 git（`psf/policies`）**不暴露** |
| **npm** `§1.4` | 政策文件（**14 项 Policies 索引**）；内容规则在 Open Source Terms 内分 `Acceptable Use`（行为）/ `Acceptable Content`（制品）两节 | 是（政策类型 / 行为 vs 内容 / 产品分区） | **0**（规则=18 条 `You will (not)...`）；**规则内含元注释**：`This rule is intentionally loose` | 文档分区（Open Source Terms vs Private Terms）+ 年龄门槛（`at least 13 years of age`）+ 法域转致（`You will not violate any applicable law`）+ **名称治理整体引用 GitHub** | 无 named Other；`they deem unacceptable`（**最宽兜底，纯主观**）+ `A few examples of`（非穷尽）+ `You will not encourage or assist any other person in violation` | **3**（`restrict` / `suspend` / `terminate`）；`suspects` + `without notice`（**最低举证门槛**）；Disputes 内 `removed or renamed` → `permanent account suspension` 两档 | **唯一把变更历史外包给 git**：`Please refer to the git history for this document` + 精确 `.mdx` 路径；`npm last updated ... on March 10, 2022. You can review prior versions at <git>`；通知分层（有账号邮件 / 无账号自行查看）；CC-BY-SA 4.0 |
| **AWS** `§1.5` | **AUP = 6 条法益级用途禁止；Service Terms = 110 个产品专章**（两极结构） | 是（法益 / 产品 110 章 / 文档职能 / 账户国） | **9 件套**（第 1.4 条：义务句 + `reasonably believe` + 术语定义 + 通知程序 + `2 business days` 时限 + 逾期后果 + `Notwithstanding` 例外 + 事后通知 + 累犯终止）—— **本报告最完整的单条规则** | **章号**（`1. Universal Service Terms` 全域，2–110 章按产品）+ **国家→签约主体表**（6 行，含 `Any other country that is not listed in this table above` 兜底行，仅限 Marketplace 章）+ 法域命名文档（Korea/India/Japan/Indonesia）+ GovCloud 独立章 | 无兜底条款 —— **用 6 条抽象判据替代**（`for any illegal or fraudulent activity` / `or other serious harm`）；`Prohibited Content` 为具名术语 | **4 段程序阶梯**（合理相信→通知整改 / 逾期 2 工作日 / 违法或服务风险免通知 / 累犯终止）；服务章内另有 `throttle`；唯一带**退款**条款 | **最薄一档**：仅页顶 `Last Updated`。AUP 停在 **July 1, 2021**，Service Terms 到 **September 11, 2026**；`By using the Services ... you agree to the latest version`；无通知期、无历史版本、无 git |
| **Stripe** `§1.6` | **准入资格档（Prohibited / Restricted）× 国家 × 产品**，四轴并列 | **是（4 轴）**：主体地域 / 行业 / 国家 / 产品 | **0**（规则=无谓语品类名，判据由所在小节提供） | **四种机制**：(a) 12 个国家独立节；(b) 条目内联白名单 `(Note: Supported in <国家列表>. Prohibited in all other countries.)`；(c) 法域转致 `law in the jurisdictions where your business is located or to which your business is targeted`；(d) **法域一致性义务**（营业地/注册地/实益所有人地址 `all match`）+ 文档导航按国家×语言二维（Belgium 4 语言） | 无 named Other；**3 条类内 `Any other ...` 兜底** + **2 条显式非穷尽声明**（`this is not an exhaustive list` / `not exhaustive`）—— **本报告兜底条数最多** | **2 档准入**（Prohibited / Restricted，区分依据是**尽调程序**而非危害）；`approval is specific to each service offer` + `may be modified or revoked ... at any time`；`No grace periods` 属 Google；Stripe 另有**不活跃 12 个月自动关户** | **唯一带方向与法域的变更条目**：`Last updated: 2026-05-13`（ISO 8601）+ `Updated domestic charter air travel from prohibited to restricted in the US, CA, UK, EU, BR, IN, TH, AU.`；无版本号、无历史版本 |
| **eBay** `§1.7` | 卖家义务域（守则 / 标准 / 税务 / IP / 销售 / 签名确认），hub-and-spoke | 是（义务域 × 卖家级别） | **每政策带 `文章预计阅读时间：N 分钟`**（**唯一阅读成本元数据**）；规则句为中文陈述句，单条内嵌三档后果 | **未找到**国家/法域字段或列表；唯一地域线索是页面本地化（`简体中文 / English`）+ 平台内外之分（`在 eBay 平台外进行交易`）。**禁售清单页抓到的是反爬验证页，结构未取到** | **未找到**（正文无 `其他` 类目、无非穷尽声明；仅有示例引导词 `例如`） | **4 类**，含 marketplace 独有的 **"不提供保障"**（`您将无法再从买家的退款中扣除金额` / `我们不会移除差评和中评`）；另有**卖家级别**（连续评级型，非违规计数） | **未找到**（本页无 `最后更新` / 版本号 / 变更记录） |
| **Meta** `§1.8` | 危害主题，**27 个 section，索引页纯 flat 无分组标题**（原始 HTML 仅 1 个 `<h1>`，5 个候选组名 0 命中） | 是（危害主题 × 产品 × 法域 section） | **6 个具名字段**：`CHANGE LOG` / `Policy Rationale` / policy lines / `For the following Community Standards, we require additional information and/or context to enforce:` / `User Experiences` / `Data` —— **本报告唯一具名字段槽位的规则库** | 句中产品列举（**且 section 级可窄于索引级**：索引 4 个产品含 Messenger，Hateful Conduct 只 3 个）+ 法域独立 section（`Locally Illegal...`，含 `restrict access ... only in the jurisdiction where it is alleged to be unlawful`）+ 3 处 `outside the United States` 条件条款 + **语言效力声明**（`US English version ... should be used as the primary document`） | 无 named Other；元 section 兜底（`Locally Illegal Content...` 0 bullet 纯散文 + `User Requests` 2 bullet）+ **意图兜底**（`We allow this type of speech where the speaker's intention is clear. Where intention is unclear, we may remove content.`）+ `Notwithstanding` 例外块（**27 个 section 中仅 2 个**） | **内容侧 4 档**（不允许 / 需额外语境 / 允许+warning screen / 允许+18 岁以上）；**账号侧 6 档**（1 / 2-6 / 7 / 8 / 9 / 10+ 次，时长 警告/限功能/1d/3d/7d/30d）+ 严重类目**单次即封** + 首次即加长限制；**4 类不计 strike**（90 天 / 4 年回溯、类目豁免、语境豁免、批量合并为 1）+ strike **1 年过期** | **全站强制 `CHANGE LOG` 字段**（27/27 存在），**逐条只有日期无说明**；最新一条恒为字面量 `Today`；条目数 1–32 差异极大（`intellectual-property` 仅 2 条）；执行 hub 页改用 `UPDATEDAPR 23, 2025` 单行标记；无版本号 |
| **Google Ads** `§1.9` | **4 个一级栏目**（规则 / Review process / Verification and transparency / **Change log**）；政策条目按 **A-Z 字母序** | 是（栏目职能 / 字母序条目 / 法域 / 政策适用范围） | 文章 = 导语适用范围句 + 按业务面分节（账号 / 登录 / 退款 / 投放定向 / 支持） | **制裁名单挂接**（`sanctions imposed by OFAC`）+ **每个法域带数字 `criterion ID`**（`Crimea (21120)` / `Iran (2364)`）+ 争议地区用 `So-called` 前缀 + **同一法域拆成 5 个规制面**（账号归属地 / 人的物理位置 / 退款资格 / 定向目标 / 支持资格）+ 语言效力（`The English version is the official language used to enforce`） | **`Other restricted businesses`**（**唯一类目名含 Other**，有独立 URL `answer/6368711`）；另有功能等同的 `Limited ad serving` / `Inappropriate content` | **3 strike**（警告 → `3 days` 临时冻结 → `7 days` → `account suspension`）；**逐政策配额**：`a maximum of one warning and 3 strikes per policy violation`；strike 制度**仅适用于被逐一点名的 15 个政策**；`No grace periods or exceptions are possible.`（但可申诉） | **唯一把变更日志做成一级导航栏目**：`Change log` → `Upcoming and recent changes` / `Past changes`（**唯一显式建模"已公布未生效"状态**）；另设 `Regulators and enforcement dates` 独立文档族；无版本号 |
| **Amazon** `§1.10` | **经营流程环节**（General Policies / Intellectual Property / Product and Listing Requirements / Shipping / Tax / Optional Programs），一节 30+ 篇文章 | 是（经营职能 × 品类文章 × 国家） | 品类文章 = **6 个业务面小节 + `Country-specific restrictions` 小节 + `Updated on <date>`**；规则句三种形态（义务总纲 / 反向举证 / 目的性错误加重） | **页顶固定横幅 `This article applies to selling in: United States`**（**最显式、最机器可读的单文档作用域**）+ **语言选择器为 `<语言> - <国家码>` 一维对**（`English - US` / `中文 - CN` / `中文 - TW`）+ 国家清单独立成文（`Countries accepted for seller registration`）+ 内容类型限制（`Ads for healthcare products and services must follow all applicable local laws and regulations`） | **`Restricted Products`** + **`"Examples of Prohibited Listings"`**（明示为示例）；**唯一取消兜底"默认允许"含义**：`Do not assume that a product is permitted because it is not listed in our "Examples of Prohibited Listings" or has an existing ASIN.`；另有 `FBA Product Restrictions`（**物流渠道级禁运，与销售资格分离**） | **4 类后果**（法律后果 / 纠正措施 / 立即终止销售权 / 申诉）；**分档变量 2 个**：`the type of offense` + `account history`；`immediate termination` 由**故意规避**（`purposefully ... to circumvent`）触发；**通知四要素写进规则**（`which items` / `why` / `how to learn more` / `to appeal`）；`Account Health Rating Program Policy` 独立成文 | 文章级 `Updated on Apr 6, 2026`；**无版本号、无 changelog、无历史版本、无通知期** —— 与 AWS 同属最薄一档 |
| **Adyen** `§1.11` | **可配置规则构件**（Risk profiles / Risk lists / Custom rules / Machine learning rules / Post-authorization rules / Risk field reference） | 是（配置步骤 × 引擎能力 × 运营流程） | **未找到** | **未找到** | **未找到** | **未找到** | **未找到** |
| **TikTok** `§1.12` | 主题（**7 个显式一级主题**）；**第三轴 = 分发渠道（平台 vs For You feed）** | 是（主题 / FYF / 年龄 / 账号类型 / LIVE） | 规则 = `We don't allow ...` 一句话 + **`More information` 定义区**（术语 + FAQ + 示例） | **URL 路径承载法域**（`/community-guidelines/en/us/`）；**URL 查询参数承载版本**（`?cgversion=2025H2update`）；年龄做成独立主题节（`Age Restrictions and Safety Features` / `Youth Safety Enforcement`）；账号类型节（`News and Government, Politician, and Political Party Accounts`） | 无 named Other；`These examples are meant to guide you, but they don't cover every situation.`；`Content Moderation` 主题承担兜底载体职责；`Severe violations include:`（`include` = 开放集合） | **3 档后果空间**：禁止 / **允许但不可进入推荐流（FYF 独立文档）** / 严重违规；**未见 strike 计数、等级编号、处罚时长** | **唯一 URL 可寻址版本**：`?cgversion=2025H2update` / `2026H2update`（新旧版同时在线上）；**6 个元数据字段**：`version`（`2025H2update`）/ `versionName`（`2025 August`）/ `lastUpdate` / `Released`（`August 14, 2025`）/ `Effective`（`September 13, 2025`）/ 下一版本；**唯一区分发布日与生效日**；`lastUpdate` 值指向**未来**（`On September 24, 2026, we are updating...`） |
| **YouTube** `§1.13` | 危害主题 6 节 + **`Educational, Documentary, Scientific, and Artistic (EDSA) content` 例外节**（唯一把例外做成一级节） | 是（危害主题 / 例外 / 频道类型 / 功能） | 规则句 + `Was this helpful?` 控件作为文档结构一部分；`This list isn't complete.` 置于介绍段（**位置最靠前的非穷尽声明**） | 内容类型逐类列举（**含 `unlisted and private content`——唯一覆盖非公开内容**）；频道类型（`Official Artist Channel` strike → 降级为 `standard channel`）；功能层（`advanced features`）；语言效力**未找到** | 无 named Other；`This list isn't complete.` + EDSA 例外节（**反向兜底**） | **警告 + 3 strike**：警告可经**政策培训**在 90 天后失效（**唯一以教育换免责**，起算点为**完成培训时**）；strike 1 = 停权 1 周 + **8 项功能逐项枚举** + 已排定内容转 private（起算点 `the date of acknowledgement`）；strike 2 = 2 周；strike 3 = 频道永久移除；**同一 90 天窗口内计数** + 各 strike 各自 90 天失效；**删除内容不能消 strike**；`a single case of severe abuse` 直接终止 + **屡犯者可能被剥夺受训资格** | 本批证据三份文件中**未找到** `Last updated` / `version` / `CHANGE LOG` / 生效日期（**证据覆盖问题，非结论**） |

**表格读数提示**：本表"后果档数"一列刻意保留各系统自己的分档维度（对象 / 程序 / 门槛 / 配额 / 累计 / 窗口），**不做归一化** —— 因为归一化会抹掉本报告最重要的一处发现：13 个系统的"档"根本不是同一个量。

---

## 3. 横向模式

12 条。每条后括注可核验的具体证据指向。

**M1. 规则级元数据普遍为零，治理信息全部上浮到文档级。**
13 个系统中，规则的内部结构是"一个 bullet / 一句 `We don't allow...` / 一个品类名 / 一条编号条款"，**没有系统在规则上挂 ID、等级、法域或生效日期字段**（`§1.1.2`、`§1.3.2`、`§1.4.2`、`§1.6.2`）。所有结构化信息（版本、作用域、责任人、标签）都在文档头或文档尾（GitHub YAML front-matter `§1.1.2`、AMO `Tags`/`Contributors`/`Last update` `§1.2.6`、npm 政策导航 `§1.4.1`）。**唯一的部分例外是 AWS：其十进制条款号在正文里被反复自引，构成了事实上的规则 ID（`§1.5.2`）。**

**M2. 作用域从不内嵌于规则，七种文档级载体覆盖了全部样本。**
观测到的载体：① front-matter 字段（GitHub `versions: fpt: '*'`，`§1.1.3`）② 章号分区（AWS 第 1 章全域 vs 2–110 章按产品，`§1.5.3a`）③ 页顶横幅（Amazon `This article applies to selling in: United States`，`§1.10.3a`）④ URL 路径（TikTok `/en/us/`，`§1.12.3a`）⑤ 独立 section（Meta `Locally Illegal Content, Products, or Services`，`§1.8.3`）⑥ 独立文章（Google OFAC 篇，`§1.9.3a`）⑦ 条目内联括注（Stripe `Supported in ... Prohibited in all other countries`，`§1.6.3a`）。**没有任何一个系统把法域写成规则字段。**

**M3. "国家"这个维度是商业平台与开放平台的分水岭。**
**有国家维度的 5 个**：Stripe（12 国节 + 逐项 P/R 标签，`§1.6.1`）、AWS（国家→签约主体表 6 行含兜底行，`§1.5.3b`）、Google（6 个带数字 ID 的法域条目 + 拆成 5 个规制面，`§1.9.3`）、Amazon（页顶横幅 + 国家清单独立成文 + FBA 渠道级，`§1.10.3`）、TikTok（URL 路径分版，`§1.12.3a`）。
**无国家维度的 4 个**：GitHub、PyPI、npm、AMO —— 全部只写"你负责遵守一切适用法律"（`§1.1.3`、`§1.3.3`、`§1.4.3`、`§1.2.1`）。
**分界线不是平台大小，而是"是否存在跨境交易/投放"。**

**M4. 同一个"国家 × 品类"结构有五种载体，且只有 Stripe 给出了可直接比对的逐项矩阵。**
载体分别是独立大节（Stripe）、表（AWS）、文章内小节（Amazon `Country-specific restrictions`）、独立 section（Meta）、独立文章（Google）。**其中 Stripe 是唯一能在同一页上逐项比对的样本**：`Domestic charter air travel` 在 Indonesia 标 `P`、Thailand 标 `R`、Malaysia/Mexico/Singapore 列在禁止节下、`§1.6.2`；`Genital prosthetics` 出现在 7 国禁止清单但不在 Canada/Indonesia/Thailand（`§1.6.2`）。**其余四种载体都需要跨文档拼接。**

**M5. 兜底的四种哲学没有任何两个相邻系统共用同一种。**
(1) **显式抓漏条**：GitHub AUP 第 11 节，判据 `significantly harms other users`，且**自带解释方向** `resolve disputes in favor of protecting users as a whole`（`§1.1.4`）。
(2) **非穷尽声明**：Stripe（2 句）、YouTube（`This list isn't complete.`）、TikTok、npm（`A few examples of`）、Meta（`Notwithstanding` 仅 2/27）。
(3) **主观全权裁量**：npm `they deem unacceptable` —— 禁止集合由裁量定义，整个 Acceptable Content 节即兜底（`§1.4.4`）。
(4) **默认允许**：AMO `developers are free to maintain their add-ons in the manner they choose`（`§1.2.4`）；npm 的许可条件结构使"条件之外即允许"（`§1.4.4`）。
**唯一推翻 (4) 的是 Amazon**：`Do not assume that a product is permitted because it is not listed in our "Examples of Prohibited Listings"`（`§1.10.2b`）。

**M6. 六档举证门槛，低端与高端相差一个数量级。**
按宽严排序（宽 → 严）：npm `suspects` + `without notice`（`§1.4.5b`）< GitHub `Where we have decided that moderation action is warranted`（`§1.1.5`）< PyPI `retains full discretion`（`§1.3.5`）≈ Stripe `Stripe might not be able to grant approval`（`§1.6.5`）< AMO `depending on the extent of their non-compliance`（`§1.2.5b`）< AWS `we reasonably believe` **且附 2 工作日整改期**（`§1.5.5`）。**AWS 是唯一把举证门槛与程序时限绑定写的系统。**

**M7. "故意 / 重复 / 规避"是跨系统收敛的加档事由，而危害大小不是。**
AMO：`intentionally or repeatedly violate ... blocking may be immediate`（`§1.2.5b`）。AWS：`accounts of repeat infringers`（`§1.5.2`）。Amazon：`purposefully inaccurate, miscategorized, or deceptively described to circumvent` → `immediate termination`（`§1.10.2c`）。Meta：`more severe policies` + `after one occurrence`（`§1.8.5d`）。YouTube：`a single case of severe abuse`（`§1.13.5`）。**即加档的触发词集中在"主观状态"与"重复性"，而非"后果严重度"** —— 这四家与 YouTube 的例外（`severe abuse`）方向一致。

**M8. "允许但降级"是普遍存在的中间档，但降级维度各不相同。**
Meta：内容可见性（`warning screen` / `18 and older`，`§1.8.5b`）。Google：投放量（`Limited ad serving`，`§1.9.4`）。TikTok：**分发/推荐**（FYF 独立成文档 + 独立 URL，`§1.12.1`）。eBay：**平台保障**（`您将无法再从买家的退款中扣除金额`，`§1.7.5`）。AWS：服务能力（`throttle`，`§1.5.5`）。YouTube：功能集（8 项功能逐项停用，`§1.13.5`）。**六种降级维度，没有两个相同。**

**M9. 三巨头的 strike 制度骨架相同、计数模型完全不同——这是跨平台合规最直接可操作的结构差异。**
Meta = **账号级累计池**（1/2-6/7/8/9/10+ 次，`§1.8.5c`）；Google Ads = **逐政策配额**（每政策 1 警告 + 3 strike，`§1.9.5`）；YouTube = **同一 90 天窗口内计数**且各 strike 各自 90 天失效（`§1.13.5`）。**后果：在 Google 下违规 A 政策不消耗 B 政策配额；在 Meta 下则共用同一个 strike 池。** 三家都设"首次不罚只警告"，但 YouTube 的警告可经**政策培训**消除（`§1.13.5`），Meta/Google 不可。

**M10. 版本机制与"规则文本存在哪里"强相关，与平台规模无关。**
底层在 git 的系统呈现两种相反的选择：**npm 把 git 变成对外版本界面**（`Please refer to the git history for this document` + 精确 `.mdx` 路径 + `You can review prior versions at <git>`，`§1.4.6`）；**PyPI 底层同样在 git（`psf/policies`）却只暴露一个 `Superseded` 横幅与日期**（`§1.3.6`）。同时：**AWS 与 GitHub AUP 同为最薄一档**（就地覆盖、无通知期、无历史版本，`§1.5.6`、`§1.1.6`），**GitHub AUP 的最后更新停在 2021-07-01（AWS）与无日期（GitHub）** —— 而 **AMO 能给出"谁在何时改的"**（`Last update: bacharakis / Apr 30, 2026`，`§1.2.6`）。

**M11. 规则库之间存在真实的 fork 与引用谱系，样本并非彼此独立。**
PyPI AUP 在正文声明 fork 自 GitHub 并声明 CC-BY-4.0（`§1.3.6`），逐句共享骨架含 `In short, be excellent to each other.`（`§1.3.2`）；npm 的名称/商标治理**整体引用 GitHub 政策库**（`npm follows GitHub's Username Policy` / `npm processes Trademark claims under GitHub's Trademark Policy`，`§1.4.3e`）。
**由此产生一条对内容治理有直接含义的发现**：**同一段文本在同源的两份规则库中可以承载相反规范** —— `dual-use purpose` 在 GitHub 是**免责要件**（`with no implicit or explicit dual-use purpose prior to the abuse occurring`），在 PyPI 是**入罪要件**（`Note that this includes dual-use content ... including bug bounties`），在 npm 则是**按交付渠道二分**（`exploits and malware that use the npm registry as a deployment or delivery vector are not`）（`§1.3.3d`、`§1.4.2`）。

**M12. "跨条目重复"是按产品/对象切轴结构的必然代价，且没有任何系统解决了它。**
AWS 把"禁止用生成内容训练竞品模型"逐字复制到每个 AI 服务专章（第 22.5 / 40.5 / 50.5 条，句式完全一致只换服务名，`§1.5.2`）；Amazon 的 `Certain categories require ...` 用 `Certain`（某些）回避枚举哪些品类（`§1.10.2c`）；Stripe 的 `Genital prosthetics` 在 7 个国家节里重复列出、`Domestic charter air travel` 在 5 个国家节里重复列出（`§1.6.2`）；PyPI 的 `and other limitations` 与 GitHub 完全相同（`§1.3.2`）。**横切关切在"按产品切轴"的结构里无法集中表达 —— 这是本报告发现的最重要的结构性代价。**

**M13（补充）. 两个"元结构"信号：规则页正在承载"消费者文档"的功能。**
eBay 在每条政策上标注 `文章预计阅读时间：N 分钟`（`§1.7.1`），YouTube 把一个 `Was this helpful?` 控件抽成文档的二级标题（`§1.13.1`）。**13 个系统中只有这两个把"读者如何消费政策"纳入规则页结构** —— 其余系统的元数据全是版本、责任人、法域等**治理侧**字段。

---

## 4. 不可达来源

以下来源在本次抓取中**明确失败或内容不可用**，一律不作为证据。每一行给出失败性质与判定依据。

### 4.1 抓取失败（HTTP 非 200 / 空文件 / 挑战页）

| 来源 | URL | 失败性质 | 判定依据 |
|---|---|---|---|
| npm Acceptable Use | `https://docs.npmjs.com/policies/acceptable-use` | **HTTP 404**（三次重试均 404，返回 481,005B 的 404 外壳） | `R7/_fetchlog.tsv` 第 8–10 行 |
| Mozilla AMO review process | `https://extensionworkshop.com/documentation/publish/add-on-review-process/` | **HTTP 404**（246B） | `R7/_fetchlog.tsv` |
| Mozilla AMO reviewer checklist | `https://extensionworkshop.com/documentation/publish/reviewer-checklist/` | **HTTP 404**（243B） | `R7/_fetchlog.tsv` |
| Shopify Acceptable Use Policy | `https://www.shopify.com/legal/acceptable-use-policy` | **HTTP 404**（三次重试均 404，10–11KB 404 页）→ 故本报告**未设 Shopify 独立小节** | `R7/_fetchlog.tsv` 第 42–46 行 |
| Wikipedia 政策清单 | `https://en.wikipedia.org/wiki/Wikipedia:List_of_policies_and_guidelines` | **HTTP 000**（抓取未完成，0 字节） | `R7/_fetchlog.tsv` 第 1 行 |
| OpenStreetMap Good practice | `https://wiki.openstreetmap.org/wiki/Good_practice` | **HTTP 000**（0 字节） | `R7/_fetchlog.tsv` |
| Wikimedia Foundation Policy:Main | `https://foundation.wikimedia.org/wiki/Policy:Main` | **HTTP 000**（0 字节） | `R7/_fetchlog.tsv` |
| **eBay 卖家规则索引** | `https://www.ebay.com/help/policies/default/ebays-rules-for-sellers?id=4342` | **HTTP 200 但正文是反爬验证页** | `_evidence/R7/marketplace/ebay-policy-index.txt` 第 6–10 行逐字：`Security Measure | eBay` / `Please verify yourself to continue` / `To keep eBay a safe place to buy and sell, we will occasionally ask you to verify yourself.` |
| **eBay 禁售与受限物品** | `https://www.ebay.com/help/policies/prohibited-restricted-items/prohibited-restricted-items?id=4207` | **HTTP 200 但正文是同一反爬验证页**（38,627B vs 上一文件 38,602B，相差 25B，正文一致 → 实为同一验证页的两次抓取） | 同上一行；**且已触发父 agent 的同哈希陷阱警告** |
| Walmart Marketplace policies | `https://marketplace.walmart.com/help/article/...` | **HTTP 404** | `_evidence/R7/marketplace/walmart-marketplace-policies.txt`、`walmart-prohibited-products.txt` 头部 `HTTP: 404` |
| Adyen restricted & prohibited products | `https://docs.adyen.com/risk-management/restricted-and-prohibited-products/` | **HTTP 404**（167B）→ 故 `§1.11` 的 2–6 小节全部记为"未找到" | `_evidence/R7/marketplace/adyen-prohibited-restricted.txt` 头部 `HTTP: 404` |
| Etsy seller policy | `https://www.etsy.com/legal/sellers/` | **HTTP 000**（107B，抓取未完成） | `_evidence/R7/marketplace/etsy-seller-policy.txt` 头部 `HTTP: 000` |
| Etsy prohibited items | `https://www.etsy.com/legal/prohibited/`（据文件名推断） | **HTTP 000**（110B，抓取未完成） | `_evidence/R7/marketplace/etsy-prohibited-items.txt` 头部 `HTTP: 000` |
| Google Ads policy index（marketplace 批） | 见文件头 | **HTTP 000**（123B） | `_evidence/R7/marketplace/google-ads-policy-index.txt`、`google-ads-misrepresentation.txt` 头部 `HTTP: 000` |
| Meta ad standards index（marketplace 批） | 见文件头 | **HTTP 000**（124B）—— 需 JS 渲染或挡了 curl | `_evidence/R7/marketplace/meta-ad-standards-index.txt` 头部 `HTTP: 000` |
| **Google Ads "List of ad policies"** | `https://support.google.com/adspolicy/answer/1316545` | **HTTP 200 但正文是 404 页**（逐字：`# Sorry, this page can't be found.` / `This page doesn't exist in Advertising Policies Help.`） | `R1/google-ads-list-of-policies.md`（该文件命中 `can't be found` 2 次）→ **本报告 `§1.9.1` 只引其导航框架，并在节首明确声明，未引其任何"政策内容"** |

### 4.2 已存在但本次未抓取（**不是**不可达，但在本报告中未被使用）

| 来源 | 位置 | 说明 |
|---|---|---|
| npm `Dual Use Content` 政策页 | `/policies/dual-use` | 在全部 5 份 npm 证据文件的侧栏导航中均出现（`R7/npm-open-source-terms.txt` 第 241 行等），**不是 404，是不在本次抓取清单内** → `§1.4.1`、`§1.4.6` 已标注 |
| YouTube 政策更新页 | `R1/youtube-policy-updates.md` | 文件存在于 R1 目录，本分片**未读取**，故 `§1.13.6` 不引用它，只记为"本批证据三份文件未找到变更记录" |
| Amazon 国别限制正文解码件 | `_evidence/R1/amazon-ads-claims-substantiation-country-restrictions.md`（26KB） | 由 R7-W3 从 `.html` 超长 JSON 行解出；本分片未使用 → `§1.10.2` 已标注"结构可见、正文未取到" |

### 4.3 结构性取证陷阱（已遵守，未违反）

1. **Amazon `.md` 文本层不完整**：Amazon 把正文以转义 JSON + 超长行内嵌在 `.html`（实测 `amazon-ads-*.html` 单行可达 29,989 字符）。**按行读取或对行长度设上限的抽取器会静默丢弃正文**（假阴性）。本报告 `§1.10` 的所有引用**均取自 `.md` 中肉眼可见的句子**；`Country-specific restrictions` 小节一律记为"结构可见、正文未取到"，未补写。
2. **反爬验证页伪装成 200**：eBay 两个政策页 HTTP 200 但正文是 `Please verify yourself` 验证页（见 4.1）。**HTTP 200 ≠ 内容可用。**
3. **404 页保留了真实导航**：`R1/google-ads-list-of-policies.md` 的正文是 404，但 404 页由 Help Center 外壳渲染，导航为真实站点结构。本报告只在明确声明后引其导航。
4. **同哈希文件不可作交叉印证**：父 agent 已确认 `R1/youtube-channel-terminations.md` 与 `R1/youtube-strike-expiry.md` **逐字节完全相同**。**本报告 `§1.13` 未引用这两个文件中的任何一个**，YouTube 后果结构全部取自 `R1/youtube-strike-basics.md` 单一来源。

---

## 5. 证据清单

### 5.1 R7 目录（开放平台与支付侧）

| 文件路径 | 原始 URL | 本报告引用处 |
|---|---|---|
| `_evidence/R7/github-docs-aup-src.md` | https://docs.github.com/en/site-policy/acceptable-use-policies/github-acceptable-use-policies | §1.1.1–1.1.6 |
| `_evidence/R7/github-docs-cg-src.md` | https://docs.github.com/en/site-policy/github-terms/github-community-guidelines | §1.1.1–1.1.6 |
| `_evidence/R7/github-docs-tos-src.md` | https://docs.github.com/en/site-policy/github-terms/github-terms-of-service | §1.1.2、§1.1.5、§1.1.6 |
| `_evidence/R7/github-site-policy-index.txt` | https://docs.github.com/en/site-policy | §1.1.1、§1.1.3 |
| `_evidence/R7/amo-addon-policies.txt` | https://extensionworkshop.com/documentation/publish/add-on-policies/ | §1.2.1–1.2.6 |
| `_evidence/R7/amo-index.txt` | https://extensionworkshop.com/documentation/publish/ | §1.2.6 |
| `_evidence/R7/amo-review-rejection.txt` | https://extensionworkshop.com/documentation/publish/what-does-review-rejection-mean-to-users/ | §1.2.5c、§1.2.6 |
| `_evidence/R7/amo-source-code-submission.txt` | https://extensionworkshop.com/documentation/publish/source-code-submission/ | §1.2.6 |
| `_evidence/R7/pypi-aup.txt` | https://pypi.org/policy/acceptable-use-policy/ | §1.3.1–1.3.6 |
| `_evidence/R7/pypi-terms.txt` | https://pypi.org/policy/terms-of-use/ | §1.3.2、§1.3.3、§1.3.6 |
| `_evidence/R7/npm-terms-of-use.txt` | https://docs.npmjs.com/policies/terms | §1.4.1、§1.4.3a |
| `_evidence/R7/npm-open-source-terms.txt` | https://docs.npmjs.com/policies/open-source-terms | §1.4.1–1.4.6 |
| `_evidence/R7/npm-unpublish.txt` | https://docs.npmjs.com/policies/unpublish | §1.4.6 |
| `_evidence/R7/npm-disputes.txt` | https://docs.npmjs.com/policies/disputes | §1.4.3e、§1.4.5d/e |
| `_evidence/R7/npm-security.txt` | https://docs.npmjs.com/policies/security | §1.4.6 |
| `_evidence/R7/aws-aup.txt` | https://aws.amazon.com/aup/ | §1.5.1–1.5.6 |
| `_evidence/R7/aws-service-terms.txt` | https://aws.amazon.com/service-terms/ | §1.5.1–1.5.6 |
| `_evidence/R7/aws-legal-index.txt` | https://aws.amazon.com/legal/ | §1.5.1 |
| `_evidence/R7/_fetchlog.tsv` | ——（抓取日志，含 HTTP 状态码） | §4.1 全部行 |
| `_evidence/R7/marketplace/stripe-restricted-businesses.txt` | https://stripe.com/legal/restricted-businesses | §1.6.1–1.6.6 |
| `_evidence/R7/marketplace/stripe-legal-index.txt` | https://stripe.com/legal | §1.6.3e、§1.10.3b |
| `_evidence/R7/marketplace/ebay-seller-code-of-conduct.txt` | https://www.ebay.com/help/policies/selling-policies/seller-code-of-conduct?id=4345 | §1.7.1–1.7.6、§1.13.1、§3-M13 |
| `_evidence/R7/marketplace/ebay-policy-index.txt` | https://www.ebay.com/help/policies/default/ebays-rules-for-sellers?id=4342 | **仅 §4.1（不可达）** |
| `_evidence/R7/marketplace/ebay-prohibited-restricted-items.txt` | https://www.ebay.com/help/policies/prohibited-restricted-items/prohibited-restricted-items?id=4207 | **仅 §4.1（不可达）** |
| `_evidence/R7/marketplace/adyen-risk-index.txt` | https://docs.adyen.com/risk-management/ | §1.11.1 |
| `_evidence/R7/marketplace/adyen-prohibited-restricted.txt` | https://docs.adyen.com/risk-management/restricted-and-prohibited-products/ | **仅 §4.1（404）** |
| `_evidence/R7/marketplace/walmart-marketplace-policies.txt` | https://marketplace.walmart.com/help/article/... | **仅 §4.1（404）** |
| `_evidence/R7/marketplace/walmart-prohibited-products.txt` | https://marketplace.walmart.com/help/article/prohibited-products | **仅 §4.1（404）** |
| `_evidence/R7/marketplace/etsy-seller-policy.txt` | https://www.etsy.com/legal/sellers/ | **仅 §4.1（HTTP 000）** |
| `_evidence/R7/marketplace/etsy-prohibited-items.txt` | https://www.etsy.com/legal/prohibited/ | **仅 §4.1（HTTP 000）** |
| `_evidence/R7/marketplace/google-ads-policy-index.txt`、`google-ads-misrepresentation.txt`、`meta-ad-standards-index.txt` | 见各文件头 | **仅 §4.1（HTTP 000）** |

### 5.2 R1 目录（平台侧）

| 文件路径 | 原始 URL（取自文件头 `source URL` / `Source` 行） | 本报告引用处 |
|---|---|---|
| `_evidence/R1/meta-cs-index.md` | https://transparency.meta.com/policies/community-standards/ | §1.8.1、§1.8.2、§1.8.3、§1.8.5b |
| `_evidence/R1/meta-cs-hate-speech.md` | https://transparency.meta.com/policies/community-standards/hate-speech/（canonical 服务为 `/hateful-conduct/`） | §1.8.2–1.8.6 |
| `_evidence/R1/meta-cs-STRUCTURE-INVENTORY.md` | 同批 27 个 section 的结构统计表（**二手统计件，引用处均已标注"INVENTORY 统计"**） | §1.8.1、§1.8.2、§1.8.3、§1.8.4 |
| `_evidence/R1/meta-ad-enforcement-counting-strikes.md` | https://transparency.meta.com/enforcement/taking-action/counting-strikes/ | §1.8.5c–e |
| `_evidence/R1/meta-ad-enforcement-restricting-accounts.md` | https://transparency.meta.com/enforcement/taking-action/restricting-accounts/ | §1.8.5c–g |
| `_evidence/R1/google-ads-topic-list-of-ad-policies.md` | https://support.google.com/adspolicy/topic/1626336 | §1.9.1、§1.9.4 |
| `_evidence/R1/google-ads-country-restrictions-6163740.md` | https://support.google.com/google-ads/answer/6163740?hl=en | §1.9.2、§1.9.3 |
| `_evidence/R1/google-ads-repeat-violations-strikes.md` | https://support.google.com/adspolicy/answer/10922738?hl=en | §1.9.2、§1.9.5 |
| `_evidence/R1/google-ads-list-of-policies.md` | https://support.google.com/adspolicy/answer/1316545 | **仅导航框架**，§1.9.1、§1.9.6（节首已声明正文为 404） |
| `_evidence/R1/amazon-program-policies-G521.md` | https://sellercentral.amazon.com/gp/help/external/G521 | §1.10.1、§1.10.3a/b/c、§1.10.5 |
| `_evidence/R1/amazon-account-enforcement-regulatory-GX9VRVWH8HXTDTK7.md` | https://sellercentral.amazon.com/help/hub/reference/external/GX9VRVWH8HXTDTK7 | §1.10.2、§1.10.3a/b、§1.10.4、§1.10.5 |
| `_evidence/R1/amazon-ads-healthcare-GPSSMTEAA6AEWY3A.md` | https://advertising.amazon.com/help/GPSSMTEAA6AEWY3A | §1.10.2、§1.10.3d、§1.10.6、§1.9.6 |
| `_evidence/R1/tiktok-community-guidelines.md` | https://www.tiktok.com/community-guidelines/en/us/（`cgversion=2025H2update`） | §1.12.1–1.12.5 |
| `_evidence/R1/tiktok-fyf-standards.md` | https://www.tiktok.com/community-guidelines/en/fyf-standards/ | §1.12.1、§1.12.5 |
| `_evidence/R1/tiktok-community-guidelines-updates.md` | https://www.tiktok.com/community-guidelines/（in-page `lastUpdate` + `cgversion`） | §1.12.6 |
| `_evidence/R1/tiktok-community-guidelines-2026H2.md` | https://www.tiktok.com/safety/en/policies-and-engagement/overview?cgversion=2026H2update | §1.12.3b、§1.12.6（**仅 Overview 节有正文**，已声明） |
| `_evidence/R1/youtube-strike-basics.md` | https://support.google.com/youtube/answer/2802032 | §1.13.1–1.13.6（**YouTube 后果结构的唯一来源**） |
| `_evidence/R1/youtube-community-guidelines-full.md` | https://www.youtube.com/howyoutubeworks/policies/community-guidelines/ | §1.13.1、§1.13.4 |
| `_evidence/R1/youtube-community-guidelines-overview.md` | https://www.youtube.com/howyoutubeworks/policies/community-guidelines/ | §1.13.1（结构对照） |

### 5.3 引用了文件名但未读取正文的 R1 文件（**声明，未引用其内容**）

`R1/amazon-account-health-assurance-GGQY933W4RDPJT29.md`、`R1/amazon-intl-sellers-G200404870.md`、`R1/amazon-taxes-regulations-global-selling-G201468380.md`、`R1/google-ads-regulators-enforcement-dates.md`、`R1/meta-cs-locally-illegal-products-services.md`（其逐字内容经 INVENTORY 表转引，已在 §1.8.3、§1.8.4 标注）、`R1/tiktok-accounts-features.md`、`R1/youtube-policy-updates.md`、`R1/youtube-strike-expiry.md`、`R1/youtube-channel-terminations.md`（后两者**互为同哈希文件，本报告一律不引**）。

### 5.4 统计自检

- 覆盖系统数：**13**
- 【原文】逐字引用块数：见文末自检报告
- 引用来源文件数：R7 目录 31 个 + R1 目录 18 个 = **49 个**
