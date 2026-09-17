# R4 · 度量与透明度 · 一手证据包

抓取日期：**2026-09-15**（ISO）。所有文件在 `research/governance/_evidence/R4/`。
本机直连被墙（google/meta/tiktok/archive.org 全部超时），全部抓取经本机代理 `http://127.0.0.1:7890` 完成；
部分站点需完整浏览器头（`--compressed --http2` + `Sec-Fetch-*`）才能通过 bot 防护。

---

## 0. 一个关键发现（对报告最有用的一条）

**Meta 把《Community Standards Enforcement Report》的完整数据以 CSV 文本内嵌在其报告页的 SSR payload 里**，
文件名 `CSER-2026_Q2.csv`，无需登录、无需 API key。本地已存 `meta-cser-2026Q2.csv`（5409 行，2026Q2 为最新季度）。
GraphQL 查询名为 `TransparencyReportCSERRootCSVQuery`（queryID `31742207542036840`），页面为
`https://transparency.meta.com/reports/community-standards-enforcement/hateful-conduct/facebook/`。

同理，**YouTube 的 DSA 透明度报告（Art 15/24）以结构化 CSV 公开发布在 Google 的公开 GCS bucket**
`https://storage.googleapis.com/transparencyreport/report-downloads/`（bucket 可匿名列举，共 1065 个 key）。

---

## 1. 抓到的东西清单

| 本地文件名 | URL | 抓取日期 | HTTP | 字节 |
|---|---|---|---|---|
| `meta-cse-overview.html` | transparency.meta.com/en-us/reports/community-standards-enforcement/ | 2026-09-15 | 200 | 488,624 |
| `meta-metric-prevalence.html` | transparency.meta.com/policies/improving/prevalence-metric/ | 2026-09-15 | 200 | 449,846 |
| `meta-metric-proactive-rate.html` | .../policies/improving/proactive-rate-metric/ | 2026-09-15 | 200 | 423,570 |
| `meta-metric-appealed-content.html` | .../policies/improving/appealed-content-metric/ | 2026-09-15 | 200 | 458,926 |
| `meta-metric-restored-content.html` | .../policies/improving/restored-content-metric/ | 2026-09-15 | 200 | 418,541 |
| `meta-metric-content-actioned.html` | .../policies/improving/content-actioned-metric/ | 2026-09-15 | 200 | 440,712 |
| `meta-metric-precision.html` | .../policies/improving/precision-metric/ | 2026-09-15 | 200 | 424,133 |
| `meta-metric-false-positive-volume.html` | .../policies/improving/false-positive-volume-metric/ | 2026-09-15 | 200 | 429,707 |
| `meta-getting-better-at-measurement.html` | .../policies/improving/getting-better-at-measurement/ | 2026-09-15 | 200 | 457,049 |
| `meta-corrections-adjustments.html` | .../policies/improving/corrections-adjustments/ | 2026-09-15 | 200 | 491,653 |
| `meta-cse-hateful-conduct-fb.html` | transparency.meta.com/reports/community-standards-enforcement/hateful-conduct/facebook/ | 2026-09-15 | 200 | 1,137,612 |
| **`meta-cser-2026Q2.csv`** | 内嵌于上述页面（`CSER-2026_Q2.csv`） | 2026-09-15 | 200 | 422,567 |
| `tiktok-cg-report.html` | tiktok.com/transparency/en/cg-report | 2026-09-15 | 200 | 5,330,565 |
| **`tiktok-2026Q1-cger-data.zip`** | sf16-va.tiktokcdn.com/.../2026Q1/2026Q1_CGER_English.zip | 2026-09-15 | 200 | 801,016 |
| `tiktok-cger-2026Q1/2026Q1_raw_data_cger_English.csv` | 上 zip 解包 | 2026-09-15 | — | 12,984,384 |
| `tiktok-cger-2026Q1/CGER_README.txt` | 上 zip 内 | 2026-09-15 | — | 4,146 |
| `tiktok-2026Q1-prevalence.html` / `-volume` / `-speed` / `-policies` | sf16-va.tiktokcdn.com/.../2026Q1/1..4_*_English.html | 2026-09-15 | 200 | 58,642 / 68,826 / 69,706 / 80,411 |
| **`youtube-vvr-methodology-barnett.pdf`** | storage.googleapis.com/transparencyreport/youtube/YouTube's VVR Methodology - A Statistical Assessment - Arnold Barnett.pdf | 2026-09-15 | 200 | 654,460（16 页） |
| **`youtube-dsa-report-2026H1.zip`** | storage.googleapis.com/transparencyreport/report-downloads/YouTube - DSA Aug 2026_2026-1-1_2026-6-30.zip | 2026-09-15 | 200 | 261,034 |
| `youtube-dsa-2026H1/*.csv`（11 个） | 上 zip 解包 | 2026-09-15 | — | 合计约 1.3 MB |
| `youtube-dsa-audit-2024-2025.pdf` | .../report-downloads/dsa-audit-youtube_2024-6-1_2025-5-31_en_v1.pdf | 2026-09-15 | 200 | 3,266,348 |
| `google-dsa-risk-assessment-2025.pdf` | .../report-downloads/dsa-risk-assessment_2025-8-28_2025-8-28_en_v1.pdf | 2026-09-15 | 200 | 6,480,903 |
| `google-dsa-online-platforms-report-feb2025.xlsx` | storage.googleapis.com/transparencyreport/dsa/EU DSA Online Platforms Report - Feb 2025.xlsx | 2026-09-15 | 200 | 88,116 |
| `_gcs-listing.txt` | storage.googleapis.com/transparencyreport/ 完整 key 列表 | 2026-09-15 | 200 | 61,457 |
| **`eu-cellar-32022R2065.html`** | publications.europa.eu/resource/celex/32022R2065（EU 出版局 Cellar API，官方全文） | 2026-09-15 | 200 | 838,166 |
| `dsa-articles-extracted.txt` | 由上文件抽取 Art 15/16/17/24/34/35/42 | 2026-09-15 | — | 21,672 |
| `dsa-tdb-statement-search.html` | transparency.dsa.ec.europa.eu/statement | 2026-09-15 | 200 | 168,525 |
| `dsa-tdb-api-doc.html` | .../page/api-documentation | 2026-09-15 | 200 | 104,563 |
| `dsa-tdb-additional-explanation.html` | .../page/additional-explanation-for-statement-attributes | 2026-09-15 | 200 | 61,981 |
| `dsa-tdb-documentation.html` | .../page/documentation | 2026-09-15 | 200 | 59,075 |
| `dsa-tdb-download-page.html` | .../explore-data/download | 2026-09-15 | 200 | 212,119 |
| `dsa-tdb-research-api.html` | .../page/research-api | 2026-09-15 | 200 | 70,653 |
| `dsa-tdb-retention-policy.html` | .../page/data-retention-policy | 2026-09-15 | 200 | 33,518 |
| `ec-dsa-tdb-qa.html` | digital-strategy.ec.europa.eu/en/faqs/dsa-transparency-database-questions-and-answers | 2026-09-15 | 200 | 89,315 |
| `santaclara-principles.html`（SCP 2.0 全文） | santaclaraprinciples.org/ | 2026-09-15 | 200 | 31,712 |
| `santaclara-scp1-2018.html`（SCP 1.0 全文） | santaclaraprinciples.org/scp1 | 2026-09-15 | 200 | 9,827 |
| `scp2-open-consultation-report.pdf` | santaclaraprinciples.org/images/SantaClara_Report.pdf | 2026-09-15 | 200 | 1,146,740 |
| **`krippendorff-2004-reliability.pdf`** | repository.upenn.edu DSpace bitstream（MD5 与仓库声明一致） | 2026-09-15 | 200 | 286,771（15 页） |
| `kappa-benchmark-scale-stata-kappa-manual.pdf` | stata.com/manuals/rkappa.pdf | 2026-09-15 | 200 | 199,508（16 页） |
| `pubmed-landis-koch-843571-abstract.txt` | eutils.ncbi.nlm.nih.gov efetch（PubMed HTML 是 JS 挑战页） | 2026-09-15 | 200 | 849 |
| `offenseval-semeval2019.pdf` | aclanthology.org/N19-1144.pdf | 2026-09-15 | 200 | 187,995 |
| `waseem-2016-disagreement.pdf` | aclanthology.org/W16-5618.pdf | 2026-09-15 | 200 | 121,690 |
| `jigsaw-toxicity-iaa.pdf` | arxiv.org/pdf/1903.04561 | 2026-09-15 | 200 | 1,275,642 |

---

## 2. 逐字证据摘录

### A. 平台透明度报告的指标定义与数字

#### A-1 Meta · prevalence（违规内容占比）

来源：<https://transparency.meta.com/policies/improving/prevalence-metric/>（页首标注 `UPDATED MAR 6, 2025`），抓取 2026-09-15。

> "**Prevalence** considers all the views of content on Facebook or Instagram and measures the estimated percentage of those views that were of violating content. (Learn more about how we define views in "Why we measure the prevalence of views.") This metric assumes that the impact caused by violating content is proportional to the number of times that content is viewed."

> "**How we measure prevalence** — Prevalence of violating content is **estimated using samples of content views** from across Facebook or Instagram. We calculate it as: the estimated number of views that showed violating content, divided by the estimated number of total content views on Facebook or Instagram. If the prevalence of adult nudity and sexual activity was 0.18% to 0.20%, that would mean of every 10,000 content views, 18 to 20 on average were of content that violated our standards for adult nudity and sexual activity."

> "Some types of violations occur very infrequently on our services. … As a result, many times we do not find enough violating samples to precisely estimate prevalence. In these cases, we can estimate an **upper limit** of how often someone would see content that violates these policies."

> "It's important to note that when the prevalence of a violation type is so low that we can only provide upper limits, this limit may change by a few hundredths of a percentage point between reporting periods. However, **changes this small may not be statistically significant**; in such cases, these small changes do not indicate an actual difference in the prevalence of this violating content on the service."

> "We estimate how often content is **seen** rather than the amount of content **posted** because we want to determine how much that content affected people…"

中文要点：Meta 的 prevalence **是抽样估算，不是全量**；分母是"内容浏览量（views）"而非"发布量"；样本不足时只给上界。

#### A-2 Meta · proactive rate（主动发现率）

来源：<https://transparency.meta.com/policies/improving/proactive-rate-metric/>（`UPDATED FEB 22, 2023`）。

> "This metric shows the **percentage of all content or accounts acted on that we found and actioned before users reported them to us**. We use this metric as an indicator of how effectively we detect violations."

> "We calculate this percentage as: **the number of pieces of content acted on that we found and actioned before people using Facebook or Instagram reported them, divided by the total number of pieces of content we took action on.**"

> "Our proactive rate **doesn't reflect how long it takes us to detect violating content or how many times it was viewed before detection. It also doesn't reflect how many violations we failed to detect altogether** or how many times that content was viewed. And though the percentage of content we proactively detect can be very high — as high as 99% in some categories — even the remaining small percentage can cause significant impact to people."

中文要点：主动发现率的分母是"已处置量"，**不是"全部违规量"**，因此它无法衡量漏检（这正是"覆盖率"缺口）。

#### A-3 Meta · appealed content / restored content（申诉与恢复率）

来源：<https://transparency.meta.com/policies/improving/appealed-content-metric/>（`UPDATED NOV 18, 2022`）。

> "**This metric shouldn't be interpreted as an indicator of the accuracy of our decisions on content**, as people may choose to appeal for many different reasons."

> "We report the total number of pieces of content that had an appeal submitted in each quarter … Keep in mind that this means that **the numbers can't be compared directly to content actioned or to content restored for the same quarter**."

来源：<https://transparency.meta.com/policies/improving/restored-content-metric/>（`UPDATED OCT 4, 2022`）。

> "By "**restore**," we mean returning content that we previously removed or removing a cover from content that we previously covered with a warning. We report content that we restored **in response to appeals as well as content we restored that wasn't directly appealed**."

> "It might be tempting to read this metric as an indicator of the mistakes we make in taking action on content. However, … **restoring a post doesn't necessarily mean a mistake was made**."

#### A-4 Meta · 最新一期（H1 2026，数据文件 `CSER-2026_Q2.csv`，最新季度 2026Q2）

来源：<https://transparency.meta.com/en-us/reports/community-standards-enforcement/>（页首 `H1 2026 Report`），数字取自内嵌 CSV。

关键 takeaway 逐字（页面正文）：

> "At the end of H1 2026, global enforcement precision averaged around 91% on Facebook and around 92% on Instagram."

> "On Facebook, prevalence for adult nudity and sexual activity decreased (0.10 - 0.11% in Q4 2025 to 0.07 - 0.08% in Q2 2026) by deploying LLMs to close enforcement gaps."

> "Prevalence of violent and graphic content increased by 0.05% on both Facebook (0.15% - 0.16% in Q4 2025 to 0.20% - 0.21% during Q2 2026) and on Instagram (0.09% to 0.10% in Q4 2025 to 0.14% - 0.15% during Q2 2026) due to real world events."

2026Q2 明细（Facebook，节选）：

| policy_area | Prevalence | Proactive rate | Content Actioned | Content Appealed | Restored (w/ appeal) | Restored (w/o appeal) |
|---|---|---|---|---|---|---|
| Hateful Conduct | 0.02%–0.02% | 66.40% | 1,500,000 | 253,800 | 28,700 | 2,500 |
| Bullying & Harassment | 0.10%–0.10% | 66.60% | 2,200,000 | 356,100 | 62,000 | 3,400 |
| Violence and Incitement | 0.03%–0.03% | 73.50% | 776,400 | 111,500 | 28,300 | 3,300 |
| Violent and Graphic Content | 0.20%–0.21% | 96.20% | 5,700,000 | 25,900 | 5,900 | 1,800 |
| Adult Nudity & Sexual Activity | 0.07%–0.08% | 96.20% | 27,800,000 | 643,500 | 79,600 | 39,200 |
| Spam | 未列（仅上界类） | 99.60% | 84,000,000 | 382,400 | 292,600 | 5,307,400 |
| Dangerous Organizations: Terrorism | <0.05% | 98.80% | 3,800,000 | 273,500 | 73,000 | 26,600 |
| Restricted Goods & Services: Firearms | <0.05% | 97.80% | 1,400,000 | 78,900 | 5,800 | 5,900 |
| Suicide, Self-Injury, and Eating Disorders | <0.05% | 99.30% | 6,900,000 | 306,700 | 64,900 | 7,700 |
| Fake Accounts | 未列 | N/A | 822,400,000 | 未列 | 未列 | 未列 |
| **Cross-Policy Data** | — | — | Content Removed **258,700,000** | — | Precision **90.80%–91.85%** | False positive vol. **30.2M–30.8M** |

2026Q2 明细（Instagram，节选）：

| policy_area | Prevalence | Proactive rate | Content Actioned | Content Appealed |
|---|---|---|---|---|
| Hateful Conduct | 0.01%–0.02% | 82.80% | 1,400,000 | 309,000 |
| Violence and Incitement | 0.02%–0.03% | 90.50% | 897,400 | 124,800 |
| Violent and Graphic Content | 0.14%–0.15% | 96.60% | 3,800,000 | 8,800 |
| Adult Nudity & Sexual Activity | 0.10%–0.11% | 85.60% | 16,100,000 | 990,300 |
| Spam | — | 99.90% | 36,300,000 | 486,600 |
| **Cross-Policy Data** | — | — | Content Removed **102,000,000** | Precision **90.78%–92.24%** |

> ⚠️ **注意 prevalence 的稀疏性**：Facebook 14 个 policy area 中，只有 5 个给出了区间 prevalence（Adult Nudity、Bullying & Harassment、Hateful Conduct、Violence and Incitement、Violent and Graphic Content），其余 4 个只给 `<0.05%` 上界。**这正是"规则库覆盖率"无法用 prevalence 衡量的直接证据。**

#### A-5 YouTube · Violative View Rate（VVR）定义与抽样方法

来源（官方委托、Google 资助的方法学评估）：Barnett, A. (2021), *YouTube's Violative View Rate Methodology: A Statistical Assessment*, September 2021，第 1–2 页、第 5–7 页。
URL：<https://storage.googleapis.com/transparencyreport/youtube/YouTube's%20VVR%20Methodology%20-%20A%20Statistical%20Assessment%20-%20Arnold%20Barnett.pdf>

> "It estimates this frequency through a metric called the "**Violative View Rate**" (**VVR**). **The VVR is the percentage of views of videos on the YouTube platform that violate its Community Guidelines.**"（p.1）

> "As noted, YouTube's goal is to estimate the fraction of views on its platform that violate its Community Guidelines (in statistical parlance, the population of interest is **all YouTube views**). A viewing arises when one person watches a video for any length of time. The emphasis on views accommodates the commonsensical notion that a violative video that is widely watched is more harmful than another such video that is rarely seen."（p.5）

> "Using a machine-learning classifier, YouTube has devised a **score** for each video … The scores can vary from 0 to 1. YouTube then moved to an exercise in **stratified sampling**, based on creating non overlapping ranges for the video scores. … YouTube decided that it would create **five strata**, namely, lowest risk, 2nd lowest, 2nd highest, highest, and "no score available." **Random sampling would then take place among the views in each stratum, meaning that a given video's probability of selection would be proportional to the number of people who viewed it. Each sampled video would be evaluated by a trained person for its adherence to the Community Guidelines.**"（pp.5–6）

> "The investigation with sampled views takes place **daily** at YouTube. In accordance with the principles of **dynamic stratified sampling**, the sample sizes in the five ranges are **revised each day based on actual VVR rates in those ranges over the 90 preceding days**."（p.7）

> "**The quarterly VVR is an average of 9 daily VVR estimates, weighted by the number of views on the platform each day** (which can vary)."（p.7）

中文要点：YouTube 的 VVR 与 Meta prevalence 同构——**都是对"浏览量"总体的分层随机抽样估算**，都有置信区间/误差界。

#### A-6 YouTube · 最新数字（DSA 透明度报告 H1 2026，2026-08-28 发布，覆盖 2026-01-01/2026-06-30）

来源：`youtube-dsa-2026H1/8_automated_means.csv` 等，原件 <https://storage.googleapis.com/transparencyreport/report-downloads/YouTube%20-%20DSA%20Aug%202026_2026-1-1_2026-6-30.zip>

| 指标（DSA 报告字段） | Scope | 值 |
|---|---|---|
| Number of measures solely taken by automated means | Total | **34,496,297** |
| Number of measures not taken by automated means | Total | **1,931,541** |
| Accuracy of the automated means – Accuracy | Total | **0.998 – 0.999**（System level accuracy for Videos） |
| Accuracy of the automated means – Accuracy | Total | **0.98**（System level accuracy for Comments） |
| Accuracy – **Precision** | Total | **0.874 – 0.896**（Automated Removal Precision） |
| Accuracy – **Recall** | Total | **0.0017 – 0.0019**（Q1 Violative View Rate (VVR) for Videos） |
| Accuracy – **Recall** | Total | **0.0015 – 0.0017**（Q2 Violative View Rate (VVR) for Videos） |
| Accuracy – Recall | Total | **0.0013 – 0.0018**（H1 Violative View Rate (VVR) for Comments） |
| Number of complaints submitted to internal-complaints mechanism | Total | **365,511** |
| 同上 – Decisions upheld | | **233,329** |
| 同上 – Decisions reversed | | **91,810** |
| 同上 – Median time（天） | | **5** |
| Number of notices received | TOTAL | **292,538** |
| …from Trusted flaggers | TOTAL | **213** |
| Number of specific items of information included in the total | TOTAL | **651,047** |
| Number of actions taken on the basis of the law | TOTAL | **400,785** |
| Number of actions taken on the basis of the terms and conditions | TOTAL | **21,281** |

> ⚠️ **极重要的一处口径事实**：YouTube 把 **VVR（违规浏览量占比）填进了 DSA 模板里的 "Accuracy of the automated means – Recall" 字段**。也就是说，在 EU 法定模板中，"漏检率/覆盖率"这一维度是以 VVR 的形式被量化申报的——precision 0.87–0.90 的同时 recall/VVR 是 0.0017–0.0019。**这是"覆盖率"在法规模板中被落地的唯一实例**（详见 E 节）。
> 另：`4_notices.csv` 的上下文栏逐字写道："Where a large proportion of total notices are processed by automated means, the overall median time to take action may be 0 hours."

#### A-7 TikTok · 指标定义

来源：CGER 报告页与数据包（<https://www.tiktok.com/transparency/en/cg-report>、`2026Q1_CGER_English.zip`），抓取 2026-09-15。

报告正文（2026Q1，`richText/cger-narrative`）逐字：

> "January - March 2026
> As part of our ongoing commitment to transparency, we are significantly expanding the number of markets for which we provide enforcement data. We are now including all markets that have had at least 50,000 removals for the quarter, increasing the total list from 50 markets previously to more than 130.
> … As we expand the deployment of AI in our safety strategies, we are adding videos taken down by AI moderation to the automated removals bar chart from this report onwards. **Automated removals, including those by AI, now make up more than 96% of total removals.**"

图表脚注（Dashboard 3 – Rates and TAT，`3_Speed_English.html`）逐字：

> "NOTE: Limited to short form video. **Proactive removal means identifying and removing a video before it's reported.** Removal within 24 hours means removing the video within 24 hours of it being posted on our platform."

数据字典（`CGER_README.txt`）逐字：

> "**`Result`**: The numerical value for the row. This can be a raw count (e.g., 1,500,000) or a percentage/rate (e.g., 0.952 representing 95.2%). … **Values may be omitted for privacy if they represent fewer than 1,000 users.**"

#### A-8 TikTok · 最新数字（Jan–Mar 2026，取自官方原始 CSV，All/All 汇总行）

| Metric | 值 |
|---|---|
| **Total videos removed** | **184,012,576** |
| **Proactive removal rate** | **0.993**（99.3%） |
| **Video: Removal rate of published** | **0.005**（0.5%） |
| **Removal rate within 24 hours** | **0.944**（94.4%） |
| **Removal rate before any views** | 见 CSV（本季度行存在，值按 All 汇总） |
| Comments removed | 237,517,128 |
| Comment: Removal rate of published | 0.002（0.2%） |
| LIVE sessions suspended | 50,791,858 |
| LIVE: Suspension rate of published | 0.027（2.7%） |
| **Videos restored** | **8,838,710** |
| LIVE sessions restored | 4,171,677 |
| Accounts removed（按行） | under-13: 25,764,372；fake accounts: 2,860,632；other: 2,410,387 |

推导比率（本次计算，非原文数字）：videos restored / total videos removed ≈ **4.80%**；automated share > 96%（官方口径）。

---

### B. DSA 透明度数据库（EU）

#### B-1 DSA 条款原文

来源：**欧盟出版局官方全文**（Regulation (EU) 2022/2065），经 Cellar API 取得：
<http://publications.europa.eu/resource/celex/32022R2065> → 重定向到 `cellar/3ff67256-…/DOC_1`，HTTP 200，838,166 bytes。
本地文件：`eu-cellar-32022R2065.html`、`dsa-articles-extracted.txt`。
（注：`eur-lex.europa.eu` 前端被 AWS WAF 拦截返回 HTTP 202 + JS 挑战页，共 2,038 bytes，**不可用**；Cellar API 是其官方后端的等价来源。）

**Article 15 — Transparency reporting obligations for providers of intermediary services**（第 1 段）

> "1. Providers of intermediary services shall make publicly available, in a machine-readable format and in an easily accessible manner, at least once a year, clear, easily comprehensible reports on any content moderation that they engaged in during the relevant period. Those reports shall include, in particular, information on the following, as applicable:
> (a) for providers of intermediary services, the number of orders received from Member States' authorities including orders issued in accordance with Articles 9 and 10, categorised by the type of illegal content concerned, the Member State issuing the order, and the median time needed to inform the authority issuing the order, or any other authority specified in the order, of its receipt, and to give effect to the order;
> (b) for providers of hosting services, the number of notices submitted in accordance with Article 16, categorised by the type of alleged illegal content concerned, the number of notices submitted by trusted flaggers, any action taken pursuant to the notices by differentiating whether the action was taken on the basis of the law or the terms and conditions of the provider, the number of notices processed by using automated means and the median time needed for taking the action;
> (c) for providers of intermediary services, meaningful and comprehensible information about the content moderation engaged in at the providers' own initiative, including the use of automated tools, the measures taken to provide training and assistance to persons in charge of content moderation, the number and type of measures taken that affect the availability, visibility and accessibility of information provided by the recipients of the service and the recipients' ability to provide information through the service, and other related restrictions of the service; **the information reported shall be categorised by the type of illegal content or violation of the terms and conditions of the service provider, by the detection method and by the type of restriction applied**;
> (d) for providers of intermediary services, the number of complaints received through the internal complaint-handling systems in accordance with the provider's terms and conditions and additionally, for providers of online platforms, in accordance with Article 20, the basis for those complaints, decisions taken in respect of those complaints, the median time needed for taking those decisions and the number of instances where those decisions were reversed;
> **(e) any use made of automated means for the purpose of content moderation, including a qualitative description, a specification of the precise purposes, indicators of the accuracy and the possible rate of error of the automated means used in fulfilling those purposes, and any safeguards applied.**"

**Article 17 — Statement of reasons**（第 1、3 段）

> "1. Providers of hosting services shall provide a clear and specific statement of reasons to any affected recipients of the service for any of the following restrictions imposed on the ground that the information provided by the recipient of the service is illegal content or incompatible with their terms and conditions:
> (a) any restrictions of the visibility of specific items of information provided by the recipient of the service, including removal of content, disabling access to content, or demoting content;
> (b) suspension, termination or other restriction of monetary payments;
> (c) suspension or termination of the provision of the service in whole or in part;
> (d) suspension or termination of the recipient of the service's account."

> "3. The statement of reasons referred to in paragraph 1 shall at least contain the following information:
> (a) information on whether the decision entails either the removal of, the disabling of access to, the demotion of or the restriction of the visibility of the information, or the suspension or termination of monetary payments related to that information, or imposes other measures referred to in paragraph 1 with regard to the information, and, where relevant, **the territorial scope of the decision and its duration**;
> (b) the facts and circumstances relied on in taking the decision, including, where relevant, information on whether the decision was taken pursuant to a notice submitted in accordance with Article 16 or based on voluntary own-initiative investigations and, where strictly necessary, the identity of the notifier;
> (c) where applicable, information on the use made of automated means in taking the decision, including information on whether the decision was taken in respect of content **detected or identified using automated means**;
> (d) where the decision concerns allegedly illegal content, a reference to the legal ground relied on and explanations as to why the information is considered to be illegal content on that ground;
> (e) where the decision is based on the alleged incompatibility of the information with the terms and conditions of the provider of hosting services, a reference to the contractual ground relied on and explanations as to why the information is considered to be incompatible with that ground;
> (f) clear and user-friendly information on the possibilities for redress available to the recipient of the service in respect of the decision, in particular, where applicable through internal complaint-handling mechanisms, out-of-court dispute settlement and judicial redress."

**Article 24 — Transparency reporting obligations for providers of online platforms**（第 1、5 段）

> "1. In addition to the information referred to in Article 15, providers of online platforms shall include in the reports referred to in that Article information on the following:
> (a) the number of disputes submitted to the out-of-court dispute settlement bodies referred to in Article 21, the outcomes of the dispute settlement, and the median time needed for completing the dispute settlement procedures, as well as the share of disputes where the provider of the online platform implemented the decisions of the body;
> (b) the number of suspensions imposed pursuant to Article 23, distinguishing between suspensions enacted for the provision of manifestly illegal content, the submission of manifestly unfounded notices and the submission of manifestly unfounded complaints."

> "5. Providers of online platforms shall, without undue delay, submit to the Commission the decisions and the statements of reasons referred to in Article 17(1) for the inclusion in a **publicly accessible machine-readable database managed by the Commission**. Providers of online platforms shall ensure that the information submitted does not contain personal data."

**Article 42 — Transparency reporting obligations（VLOP 加密义务）**（第 1、2 段）

> "2. The reports referred to in paragraph 1 of this Article published by providers of very large online platforms shall, in addition to the information referred to in Article 15 and Article 24(1), specify:
> (a) the human resources that the provider of very large online platforms dedicates to content moderation in respect of the service offered in the Union, **broken down by each applicable official language of the Member States**, including for compliance with the obligations set out in Articles 16 and 22, as well as for compliance with the obligations set out in Article 20;
> (b) the qualifications and linguistic expertise of the persons carrying out the activities referred to in point (a), as well as the training and support given to such staff;
> **(c) the indicators of accuracy and related information referred to in Article 15(1), point (e), broken down by each official language of the Member States.**
> The reports shall be published in at least one of the official languages of the Member States."

**Article 34 — Risk assessment**（第 1、2 段，与"覆盖率"最接近的合规度量条款）

> "1. Providers of very large online platforms and of very large online search engines shall diligently identify, analyse and assess any systemic risks in the Union stemming from the design or functioning of their service and its related systems, including algorithmic systems, or from the use made of their services. … This risk assessment shall be specific to their services and proportionate to the systemic risks, taking into consideration their severity and probability, and shall include the following systemic risks: (a) the dissemination of illegal content through their services; (b) any actual or foreseeable negative effects for the exercise of fundamental rights …; (c) any actual or foreseeable negative effects on civic discourse and electoral processes, and public security; (d) any actual or foreseeable negative effects in relation to gender-based violence, the protection of public health and minors …"

> "2. When conducting risk assessments, providers … shall take into account, in particular, whether and how the following factors influence any of the systemic risks referred to in paragraph 1: (a) the design of their recommender systems …; **(b) their content moderation systems; (c) the applicable terms and conditions and their enforcement**; (d) systems for selecting and presenting advertisements; (e) data related practices of the provider."

**Article 35 — Mitigation of risks**（第 1 段，节选）

> "(c) adapting content moderation processes, including the speed and quality of processing notices related to specific types of illegal content and, where appropriate, the expeditious removal of, or the disabling of access to, the content notified … as well as adapting any relevant decision-making processes and dedicated resources for content moderation; … (f) reinforcing the internal processes, resources, testing, documentation, or supervision of any of their activities in particular as regards detection of systemic risk;"

#### B-2 DSA 透明度数据库的数据 schema

来源：<https://transparency.dsa.ec.europa.eu/page/api-documentation>（"Statement Attributes" 一节），抓取 2026-09-15。

逐字字段定义（节选关键项）：

> "**Decision Grounds (decision_ground)** — This is a required field and tells us the basis on which the decision was taken. `DECISION_GROUND_ILLEGAL_CONTENT` Illegal Content / `DECISION_GROUND_INCOMPATIBLE_CONTENT` Content incompatible with terms and conditions"

> "**Content Type (content_type)** — This is a required attribute, and it tells us what type of content is targeted by the statement of reason. The value provided must be an array with at least one of the following: `CONTENT_TYPE_APP` App / `CONTENT_TYPE_AUDIO` Audio / `CONTENT_TYPE_IMAGE` Image / `CONTENT_TYPE_PRODUCT` Product / `CONTENT_TYPE_SYNTHETIC_MEDIA` Synthetic Media / `CONTENT_TYPE_TEXT` Text / `CONTENT_TYPE_VIDEO` Video / `CONTENT_TYPE_OTHER` Other"

> "**Category (category)** — This is a required attribute, and it tells us which category the statement belongs to."（16 个 `STATEMENT_CATEGORY_*`：Animal welfare、Consumer information infringements、Cyber violence、Cyber violence against women、Data protection and privacy violations、Illegal or harmful speech、Intellectual property infringements、Negative effects on civic discourse or elections、Type of alleged illegal content not specified by the notifier、Other violation of provider's terms and conditions、Protection of minors、Risk for public security、Scams and/or fraud、Self-harm、Unsafe, non-compliant or prohibited products、Violence）

> "**Category Specification (category_specification)** — This is an optional attribute, and it tells us which additional keywords the statement belongs to."（`KEYWORD_*` 列表，前端共约 50 项，如 `KEYWORD_ANIMAL_HARM`、`KEYWORD_HATE_SPEECH`、`KEYWORD_MISINFORMATION_DISINFORMATION_FIMI`、`KEYWORD_SEXUAL_ABUSE` 等）

> "**Information source (source_type)** — This is a required field … `SOURCE_ARTICLE_16` Notice submitted in accordance with Article 16 DSA / `SOURCE_TRUSTED_FLAGGER` Notice submitted by a trusted flagger / `SOURCE_TYPE_OTHER_NOTIFICATION` Other type of notification / `SOURCE_VOLUNTARY` Own voluntary initiative"

> "**Automated Detection (automated_detection)** — This is a required attribute and it must be in the form "Yes" or "No". This indicates to us that decision taken in respect of automatically detected means."

> "**Automated Decision (automated_decision)** — This is a required attribute and it must be one of the following: `AUTOMATED_DECISION_FULLY` Fully automated / `AUTOMATED_DECISION_PARTIALLY` Partially automated / `AUTOMATED_DECISION_NOT_AUTOMATED` Not Automated"

> "**Platform Unique Identifier (puid)** — This is a string that uniquely identifies this statement within the platform. This attribute is required and it must be unique within your platform. Limited to 500 characters…"

> "**Decision visibility (decision_visibility)** … `DECISION_VISIBILITY_CONTENT_REMOVED` / `..._DISABLED` / `..._DEMOTED` / `..._AGE_RESTRICTED` / `..._INTERACTION_RESTRICTED` / `..._LABELLED` / `..._OTHER`"
> "**Territorial scope** … `territorial_scope`（ISO 3166 国家码数组，如 `["PT","ES","DE"]`）"
> "**Facts and circumstances relied on in taking the decision (decision_facts)** — required textual field … Limited to 5000 characters."
> 其他日期字段：`content_date`、`application_date`、`end_date_visibility_restriction`、`end_date_account_restriction`、`end_date_monetary_restriction`、`end_date_service_restriction`；`content_language`（ISO 639-1 大写）；`content_id`（键值对，目前仅接受商品标识符）。

官方 schema → 条款映射（来源 <https://transparency.dsa.ec.europa.eu/page/documentation>，逐字）：

> "This page explains what type of information is collected, and how the different data fields map onto **Article 17 DSA**, which lays down the requirements of sending statements of reasons to recipients of the service."
> "**Why is this information included?** Article 17(1) and 17(4) DSA require the statements of reasons submitted to the database to be clear and specific. In addition, characteristics of the content affected by the content moderation decision are part of the facts and circumstances referred to in Article 17(3)(b) of the DSA. The requirements under this first sub-category also increase the database's function to ensure transparency and to enable scrutiny over content moderation decisions in line with **recital 66** of the DSA."

EC 官方 FAQ（<https://digital-strategy.ec.europa.eu/en/faqs/dsa-transparency-database-questions-and-answers>）逐字：

> "Article 17 of the Digital Services Act (DSA) requires all providers of hosting services to provide clear and specific information, called statements of reasons, to users whenever they remove or otherwise restrict access to their content. Additionally, **Article 24 (5)** of the DSA requires providers of online platforms, which are a type of hosting service, to send all their statements of reasons to the Commission's DSA Transparency Database for collection. The database is publicly accessible and machine-readable."

> "**Is there any part of a statement of reasons that is not published in the DSA Transparency Database?** Providers of online platforms are obliged to remove any personal data from the information they publish in the DSA Transparency Database, in accordance with Article 24(5) of the DSA. … **Redress options are also not included** in the DSA Transparency Database as those are relevant only for the addressee of the statement of reasons."

#### B-3 是否可以批量下载？—— 可以，且有完整日内全量 dump

来源：<https://transparency.dsa.ec.europa.eu/explore-data/download>，逐字：

> "**New file formats & aggregated data available for download** — You can now download the **global version of the full daily files in Parquet format**. You can also download **daily aggregates** of statements of reasons submissions in csv or Parquet format. …"

> "On this page, you can download **zipped csv files containing the daily submissions of statements of reasons, either for all platforms collectively or for each platform individually**. The files are provided in **full and light versions**."

> "**Full archive files contain all the public data points of each individual statement of reasons submitted on a given day. That is, each file contains the entire attribute schema of the database. Light archive files only contain a subset of the attribute schema** of the database, notably no free text fields with a character limit higher than 2000 characters (i.e. `illegal_content_explanation`, `incompatible_content_explanation` or `decision_facts`). **Light archive files also do not contain the `territorial_scope` attribute.**"

> "To download a compact, aggregated version of the data in csv or Parquet format, reporting the number of statements of reasons sharing the same categorical features, you can visit the **dsa-tdb package documentation**. Two types of aggregations are provided: the **basic aggregation currently feeding the Dashboard** and an **advanced one aggregating the data on all the database's non-free-text fields columns**."

配套工具（官方开源）：`dsa-tdb` Python 包，<https://code.europa.eu/dsa/transparency-database/dsa-tdb>；数据库本体源码 <https://github.com/digital-services-act/transparency-database>（GPLv2，README 逐字："The DSA Transparency Database collects the statements of reasons submitted by providers of online platforms to the Commission, **in accordance with Article 24(5) of the DSA**…"）。

**数据保留政策**（<https://transparency.dsa.ec.europa.eu/page/data-retention-policy>，`Effective Date: 18 February 2025`，`Policy Version: 2.0`）逐字：

> "**Statement of Reasons (SoR)**: Each SoR will be accessible via the Search Statement of Reasons page for a period of **six months (180 days)** from the date it is entered into the Transparency Database. After six months, the SoR will be removed from the search index but **will remain accessible in the CSV format within the daily dumps files**. … Since the implementation of our **V.2 Schema on July 1st**, we have archived any previous SORs from V1 of the Transparency Database."
> "**Daily Dumps Files**: Daily dumps and aggregated data views will be available for download for a period of **5 years** after their creation date. Once this period has elapsed, daily dumps will be transferred to cold storage."
> "**Dashboard**: The Dashboard will display aggregated statistics incorporating the most recent 5 years of collected data."

**搜索/导出限额**（<https://transparency.dsa.ec.europa.eu/statement>）逐字：

> "Data is updated once every day and **only the first 10 000 results are paginated. The first 1000 statements of reasons among those can be manually exported in .csv format.**"
> 页面实时计数（抓取时）：`Statements of Reasons: 3825951680`，平台数 370+。

**Research API 明确禁止批量抓取**（<https://transparency.dsa.ec.europa.eu/page/research-api>）逐字：

> "In line with the DSA Transparency Database data retention policy, the `statement_index` only contains statements of reasons submitted by platforms within the **last 6 months**. Older statements of reasons are not available through the Research API endpoints. **The DSA Transparency Database Research API endpoints are specifically designed for programmatic statistical and pattern analysis, NOT for bulk data collection.**"

> "**Use Conditions & Limitations** … 4. The maximum response size of an API request is **5MB**. 5. The maximum execution time of an API request is **30 seconds**. 6. The maximum result size is **1000 rows per query and there is no pagination support**. … 9. The Research endpoints are NOT intended for download…"

> 开通方式：EU Login 账号 → 联系 `CNECT-DSA-HELPDESK@ec.europa.eu` 申请 token。

---

### C. 人机一致性 / 标注者一致性的原始文献

#### C-1 Landis & Koch (1977) kappa 解释量表

**结论：原文无任何合法开放副本。** Unpaywall `is_oa:false / oa_status:"closed"`；Semantic Scholar `openAccessPdf.status:"CLOSED"`（DOI 10.2307/2529310，JSTOR/ Wiley 付费墙）。**`landis-koch-1977.pdf` 在本目录里是一个 Cloudflare 403 HTML 错误页（4,918 bytes），不是 PDF，不得引用为来源。**

**已核实的官方元数据**（NCBI E-utilities efetch，绕过了 PubMed 网页的 JS 挑战页；本地 `pubmed-landis-koch-843571-abstract.txt`）：

> "1. Biometrics. 1977 Mar;33(1):159-74.
> The measurement of observer agreement for categorical data.
> Landis JR, Koch GG.
> This paper presents a general statistical methodology for the analysis of multivariate categorical data arising from observer reliability studies. The procedure essentially involves the construction of functions of the observed proportions which are directed at the extent to which the observers agree among themselves and the construction of test statistics for hypotheses involving these functions. Tests for interobserver bias are presented in terms of first-order marginal homogeneity and measures of interobserver agreement are developed as generalized kappa-type statistics. These procedures are illustrated with a clinical diagnosis example from the epidemiological literature.
> PMID: 843571 [Indexed for MEDLINE]"

**六档量表的逐字复现 + 原始页码锚点**——最佳开放来源是 **Stata 官方手册**（同时给出了原文页码）：

来源：*Stata 18 Base Reference Manual*, `kappa — Interrater agreement`, "Remarks and examples → Two raters"，第 3 页。
URL：<https://www.stata.com/manuals/rkappa.pdf>（本地 `kappa-benchmark-scale-stata-kappa-manual.pdf`）

> "The kappa-statistic measure of agreement is scaled to be 0 when the amount of agreement is what would be expected to be observed by chance and 1 when there is perfect agreement. For intermediate values, **Landis and Koch (1977a, 165)** suggest the following interpretations:
> below 0.0    Poor
> 0.00 – 0.20  Slight
> 0.21 – 0.40  Fair
> 0.41 – 0.60  Moderate
> 0.61 – 0.80  Substantial
> 0.81 – 1.00  Almost perfect"

> 🔑 **`(1977a, 165)` 这个页码锚点就是原刊页码**：量表位于 *Biometrics* 33(1):159–174 的第 **165** 页。手册以 `1977a` 区分同年另一篇 `1977b`（ANOVA 推广）。

**第二条独立开放复现**（同一六行，明确标注出处）：
Wan Nor Arifin, *Clinical Agreement* 讲义, slide 14，<https://wnarifin.github.io/lecture/mstat/Clinical%20Agreement.pdf>

> "• The following guidelines by Landis and Koch (1977) is helpful for interpretation of ĸ: < 0.00 Poor / 0.00 – 0.20 Slight / 0.21 – 0.40 Fair / 0.41 – 0.60 Moderate / 0.61 – 0.80 Substantial / 0.81 – 1.00 Almost perfect"

> **引用建议**：正文引 `Landis & Koch (1977), Biometrics 33(1):159–174, p.165` 是安全的（页码经 Stata 手册独立锚定）；但**不要声称直接读过原文 PDF**。若报告要求"逐字原文页码"，请照抄上面的 Stata 手册引文并注明"经 Stata 官方手册转引，页码 165"。

#### C-2 Cohen (1960), "A Coefficient of Agreement for Nominal Scales"

**原文同样不可得**（OpenAlex `is_oa:false, oa_status:"closed", any_repository_has_fulltext:false`；Sage DOI 10.1177/001316446002000104 及其 `/doi/pdf/` 均返回 bot 挑战页）。**`未核实`** —— 不要引用 1960 年原文措辞。

目录中已有的 `cohen-1960-kappa.pdf` **不是原文**，是 University of Portland COM 425 课程讲义，其中转引了原文 Table 2：

> "Cohen's Kappa is a statistic that assesses interjudge agreement for nominally coded data. It can be applied at both the global level (i.e. for the coding system as a whole) and the local level (i.e. for individual categories). In either case, the formula is kappa = … where p₀ is the proportion of units that the two judges coded the same, and p_c is the proportion expected by chance."

> "Attached, you will find **Table 2 from Jacob Cohen, "A Coefficient of Agreement for Nominal Scales," Educational and Psychological Measurement, 1960, 20, 37-46.** … the units on which the judges agreed are displayed along the main diagonals, so p₀ = .44 + .20 + .06 = .70, and f₀ = 88 + 40 + 12 = 140."

> ⚠️ **`cohen-1960-kappa-usp.pdf` 不是 Cohen 1960**，而是 Fleiss, Cohen & Everitt (1969), "Large Sample Standard Errors of Kappa and Weighted Kappa", *Psychological Bulletin* 72(5):323–327。不要混用。

**κ 定义的可引用替代**：Krippendorff (2004) HCR 论文的 Figure 2 以统一形式列出七个系数（见下），其中 Cohen 的表达式逐字为：

> "Cohen (1960)  κ = 1 – (b + c) / (p_A q_B + p_B q_A)"

#### C-3 Krippendorff's alpha —— 阈值 .800 / .667 的逐字原文

来源：Krippendorff, K. (2004). "Reliability in Content Analysis: Some Common Misconceptions and Recommendations." *Human Communication Research* **30(3):411–433**。
本地文件：`krippendorff-2004-reliability.pdf`（15 页，作者 accepted manuscript，取自 UPenn ScholarlyCommons 机构库 bitstream，**MD5 与仓库声明校验值一致**）。抓取 2026-09-15。

**Section "Recommendations"，条目 (iii)**，manuscript 第 12 页（期刊页码 ≈429，**`未核实`**，因为这是 manuscript 而非排版版）：

> "(iii) An acceptable level of agreement below which data are to be rejected as too unreliable must be chosen depending on the costs of drawing invalid conclusions from these data. When human lives hang on the results of a content analysis, whether they inform a legal decision or tip the scale from peace to war, decision criteria have to be set far higher than when a content analysis is intended to merely support scholarly arguments. In case of the latter, to be sure that the data under consideration are at least similarly interpretable by other scholars (as represented by different coders), **I suggested elsewhere to require α ≥ .800, and where tentative conclusions are still acceptable, α ≥ .667 (Krippendorff, 2004, p. 241).** Except for perfect agreement, there are no magical numbers, however. The ones suggested here should be verified by suitable experiments. To ensure that the measured agreement is representative of the data in question, confidence intervals should be consulted. Testing the null-hypothesis that observed agreement deviates from chance has no bearing on reliability, which concerns deviations from perfect agreement or 1.000."

中文要点：**α ≥ .800 才算可靠；仅作暂定/探索性结论时可接受 α ≥ .667**；阈值出处指向 Krippendorff 方法书 **p.241**（注意：HCR 论文与同名方法书同为 2004 年，是两个不同来源，不要混淆）。

**α 的定义形式**（同文 Figure 2，第 ~5 页）：

> "Agreement = 1 – Observed / Expected Disagreements
> … Krippendorff (1970)  α = 1 – (b + c) / (2 p q)  where n = the number of 0s and 1s used jointly
> Cohen (1960)  κ = 1 – (b + c) / (p_A q_B + p_B q_A)"

> "So, D_o expresses the lack of agreement; whereas D_e defines the zero point of the measure."

> **`未核实`**：Krippendorff *Content Analysis: An Introduction to Its Methodology*（3rd ed. 2013 / 4th ed. 2019）§11.x 的正文定义——未找到任何开放副本（Google Books / 出版社样章不可达）。

#### C-4 内容审核/毒性标注领域**实际报告**的 IAA 数值

**(a) Gab Hate Corpus** —— ⚠️ **任务书给的出处有误**：不存在 LREC-2020 的 GHC 论文（已核对 LREC-2020 全部 895 篇标题，`2020.lrec-1.169` 是 *Alector* 法语简化语料）。正确出处是：
Kennedy et al. (2022), *Introducing the Gab Hate Corpus: defining and applying hate-based rhetoric to social media posts at scale*, **Language Resources and Evaluation 56:79–108**, DOI 10.1007/s10579-021-09569-x（**闭源**，数字取自 author manuscript）。

方法句（manuscript p.21）逐字：
> "To evaluate inter-annotator agreement, we computed **Fleiss's kappa** for multiple annotators (Fleiss, 1971) and the **Prevalence-Adjusted and Bias-Adjusted Kappa (PABAK)**…"

Table 3（N=27,655，manuscript p.35）逐字数值：

| 标签 | Fleiss (PABAK) | All |
|---|---|---|
| HD Human Degradation | **0.23 (0.67)** | 8.5% |
| CV Calls for Violence | **0.28 (0.97)** | 0.6% |
| VO Vulgar/Offensive | **0.30 (0.79)** | 6.3% |
| REL Religious Identity | 0.52 (0.69) | 3.1% |
| RAE Racial/Ethnic Identity | 0.48 (0.59) | 3.5% |
| SXO Sexual Orientation | 0.53 (0.90) | 0.7% |
| GEN Gender Identity | 0.47 (0.87) | 0.9% |
| IDL Ideology | 0.29 (0.66) | 1.6% |
| NAT Nationality | 0.26 (0.69) | 1.5% |
| POL Political Identity | 0.25 (0.61) | 2.3% |
| MPH Mental/Physical Health | 0.18 (0.92) | 0.2% |
| **IM Implicit Rhetoric** | **0.03 (0.38)** | 1.8% |

论文自评（p.22）逐字：
> "While our annotators are far from identical in their labeling tendencies, sufficient agreement is obtained for top-level categories (HD, CV, and VO) and for target populations. However, **the low agreement for Implicit/Explicit rhetoric casts doubts on their usefulness and informativeness**."

**(b) OffensEval / SemEval-2019 Task 6** —— Zampieri, Malmasi, Nakov, Rosenthal, Farra, Kumar, *Predicting the Type and Target of Offensive Posts in Social Media*, NAACL-HLT 2019, pp.1415–1420，**p.1417**（本地 `offenseval-semeval2019.pdf`）：

> "We computed **Fleiss' kappa on the trial dataset for the five annotators on 21 of the tweets. The value was .83 for Layer A (OFF vs. NOT) indicating high agreement.**"

> "Approximately 60% of the time, the two annotators agreed, and thus no additional annotation was needed. A third annotation was requested for the rest of the tweets; there was no instance when more than three annotations were needed."

> ⚠️ 注意样本量：**κ=.83 只在 21 条试标注上算过**，全文其余部分未再报告一致性数值。

**(c) Sap, Card, Gabriel, Choi, Smith (2019)**, *The Risk of Racial Bias in Hate Speech Detection*, ACL 2019, pp.1668–1678, §5：

> "Despite the inherent subjectivity of these questions, workers frequently agreed about a tweet being offensive to anyone (**76% pairwise agreement, κ = 0.48**) or to themselves (**74% p.a., κ = 0.30**)."

**(d) Waseem (2016)**, *Are You a Racist or Am I Seeing Things? Annotator Influence on Hate Speech Detection on Twitter*, NLP+CSS Workshop, pp.138–142，**p.139**（本地 `waseem-2016-disagreement.pdf`，已逐字核验）：

> "Considering annotator agreement, we find that the inter-annotator agreement among the amateur annotators is **κ = 0.57 (σ = 0.08)**."

> Table 3 caption: "Table 3: Kappa scores comparing majority voted label and full agreement with expert annotations." 表体：`Majority Vote 0.34 | Full Agreement 0.70`

> "Considering the overlap with the Waseem and Hovy (2016), we see that the agreement is **extremely low (mean pairwise κ = 0.14 between all annotator groups and Waseem and Hovy (2016))**."

> 中文要点：**同一批推文换一批标注者，κ 从 0.57 掉到 0.14**——这是"人类标注者之间本来就不一致"最直接的实证。

**(e) 负面结果（必须写进报告，避免被误引）**：Jigsaw / Borkan et al. (2019) *Nuanced Metrics for Measuring Unintended Bias with Real Data for Text Classification*（arXiv:1903.04561，本地 `jigsaw-toxicity-iaa.pdf`）**全文没有任何 kappa / alpha / Fleiss 数值**——它只报 bias 指标（subgroup AUC、BPSN、BNSP）。**不要把它当作"IAA 数值来源"。**

---

### D. Santa Clara Principles

#### D-1 2018 原版三条原则（逐字）

来源：<https://santaclaraprinciples.org/scp1>，抓取 2026-09-15。原文说明其性质：

> "These principles are meant to serve as a starting point, outlining **minimum levels of transparency and accountability** that we hope can serve as the basis for a more in-depth dialogue in the future."
> "Now, on the occasion of the second Content Moderation at Scale conference in Washington, DC on **May 7th, 2018**, we propose these **three principles** as initial steps…"

> "**1. Numbers**
> At a minimum, this information should be broken down along each of these dimensions:
> - Total number of discrete posts and accounts flagged.
> - Total number of discrete posts removed and accounts suspended.
> - Number of discrete posts and accounts flagged, and number of discrete posts removed and accounts suspended, **by category of rule violated**.
> - Number of discrete posts and accounts flagged, and number of discrete posts removed and accounts suspended, **by format of content** at issue (e.g., text, audio, image, video, live stream).
> - Number of discrete posts and accounts flagged, and number of discrete posts removed and accounts suspended, **by source of flag** (e.g., governments, trusted flaggers, users, different types of automated detection).
> - Number of discrete posts and accounts flagged, and number of discrete posts removed and accounts suspended, **by locations of flaggers and impacted users** (where apparent).
> This data should be provided in a regular report, **ideally quarterly, in an openly licensed, machine-readable format**."

> "**2. Notice**
> In general, companies should provide detailed guidance to the community about what content is prohibited, including examples of permissible and impermissible content and the guidelines used by reviewers. Companies should also provide an explanation of how automated detection is used across each category of content. When providing a user with notice about why her post has been removed or an account has been suspended, a minimum level of detail for an adequate notice includes:
> - URL, content excerpt, and/or other information sufficient to allow identification of the content removed.
> - The specific clause of the guidelines that the content was found to violate.
> - How the content was detected and removed (flagged by other users, governments, trusted flaggers, automated detection, or external legal or other complaint). The identity of individual flaggers should generally not be revealed, however, content flagged by government should be identified as such, unless prohibited by law.
> - Explanation of the process through which the user can appeal the decision.
> Notices should be available in a durable form that is accessible even if a user's account is suspended or terminated. Users who flag content should also be presented with a log of content they have reported and the outcomes of moderation processes."

> "**3. Appeal**
> Minimum standards for a meaningful appeal include:
> - Human review by a person or panel of persons that was not involved in the initial decision.
> - An opportunity to present additional information that will be considered in the review.
> - Notification of the results of the review, and a statement of the reasoning sufficient to allow the user to understand the decision.
> In the long term, independent external review processes may also be an important component for users to be able to seek redress."

#### D-2 Santa Clara Principles 2.0（2023 更新版，逐字）

来源：<https://santaclaraprinciples.org/>，抓取 2026-09-15。结构变化逐字：

> "This second iteration of the Santa Clara Principles is divided into **Foundational and Operational Principles**. Foundational Principles are overarching and cross-cutting principles… The Operational Principles set out more granular expectations for the largest or most mature companies… **In contrast to the minimum standards set out in the first iteration, this second iteration provides greater specificity regarding precisely what information is needed to ensure meaningful transparency and accountability.**"

> "This second iteration … **expands the scope of where transparency is required** with respect to what is considered "content" and "action" taken by a company. The term "**content**" refers to **all user-generated content, paid or unpaid, on a service, including advertising**. The terms "**action**" and "**actioned**" refer to **any form of enforcement action** taken by a company with respect to a user's content or account due to non-compliance with their rules and policies, **including (but not limited to) the removal of content, algorithmic downranking of content, and the suspension (whether temporary or permanent) of accounts**."

> "They are **not designed to provide a template for regulation**."

**新增的 4 条 Foundational Principles**（1.0 没有）：
1. Human Rights and Due Process —— 逐字："Companies should ensure that human rights and due process considerations are integrated at all stages of the content moderation process… **Companies should only use automated processes to identify or remove content or suspend accounts, whether supplemented by human review or not, when there is sufficiently high confidence in the quality and accuracy of those processes.**"
2. Understandable Rules and Policies
3. Cultural Competence —— 逐字："…**Companies will report data that demonstrates their language, regional, and cultural competence for the users they serve, such as numbers that demonstrate the language and geographical distribution of their content moderators.**"
4. **State Involvement in Content Moderation**（全新）—— 逐字："Companies should recognise the particular risks to users' rights that result from state involvement in content moderation processes. This includes a state's involvement in the development and enforcement of the company's rules and policies, either to comply with local law or serve other state interests…"

**Operational Principle 1. Numbers —— 新增的量化要求**（相对 1.0 的实质扩张），逐字：

> "Companies should publish information about pieces of content and accounts actioned, **broken down by country or region, if available, and category of rule violated**, along each of these dimensions:
> - Total number of pieces of content actioned and accounts suspended.
> - Number of appeals of decisions to action content or suspend accounts.
> - **Number (or percentage) of successful appeals that resulted in pieces of content or accounts being reinstated, and the number (or percentage) of unsuccessful appeals** and;
> - **Number (or percentage) of successful or unsuccessful appeals of content initially flagged by automated detection.**
> - **Number of posts or accounts reinstated by the company proactively, without any appeal, after recognition that they had been erroneously actioned or suspended.**
> - Numbers reflecting enforcement of hate speech policies, **by targeted group or characteristic**, where apparent, though companies should not collect data on targeted groups for this purpose
> - Numbers related to content removals and restrictions made during **crisis periods**, such as during the COVID-19 pandemic and periods of violent conflict."

> "**Special reporting requirements apply to decisions made with the involvement of state actors, which should be broken down by country:**
> - The number of demands or requests made by state actors for content or accounts to be actioned
> - **The identity of the state actor for each request**
> - Whether the content was flagged by a court order/judge or other type of state actor
> - The number of demands or requests made by state actors that were actioned and the number of demands or requests that did not result in actioning.
> - Whether the basis of each flag was an alleged breach of the company's rules and policies (and, if so, which rules or policies) or of local law (and, if so, which provisions of local law), or both.
> - Whether the actions taken against content were on the basis of a violation of the company's rules and policies or a violation of local law."

> "**Due to the increasing role that automated processes play in content moderation, a comprehensive understanding of companies' processes and systems requires transparency around the use of automated decision-making tools.** In addition to the numbers about the use of automation called for above, companies should publish information relating to:
> - When and how automated processes are used (whether alone or with human oversight) when actioning content.
> - The categories and types of content where automated processes are used;
> - **The key criteria used by automated processes for making decisions;**
> - **The confidence/accuracy/success rates of automated processes, including changes over time and differences between languages and content categories;**
> - The extent to which there is human oversight over any automated processes, including the ability of users to seek human review of any automated content moderation decisions;
> - The number (or percentage) of successful and unsuccessful appeals when the content or account was first flagged by automated detection, broken down by content format and category of violation;
> - Participation in cross-industry hash-sharing databases or other initiatives and how the company responds to content flagged through such initiatives.
> **All data should be provided in a regular report, ideally quarterly, in an openly licensed, machine-readable format.**"

**Operational Principle 2. Notice / 3. Appeal**（相对 1.0 的新增，逐字）：
> "Notices should be **timely** and should include an explanation of the process through which the user can appeal the decision…"
> "Notices should be in the **language of the original post or in the user interface language** selected by the user."
> "Notices should provide users with information about available **user support channels** and how to access them."
> "Where appropriate, notice should also be provided to **other relevant individuals, including group administrators and flaggers**. This should include a notice posted at the original location of the…"

> ⚠️ **关于 "State of Content Moderation" 报告要求**：在 SCP 2.0 正文与 Open Consultation Report 中**均未检到 "State of Content Moderation" 这一专名**（grep 命中 0）。SCP 2.0 中对应"报告要求"的表述是 Operational Principle 1 结尾的 "All data should be provided in a regular report, ideally quarterly, in an openly licensed, machine-readable format."，以及新增的**州行为者报告要求**（见上）。**若报告中要写 "State of Content Moderation 报告"，需另找出处，否则应写「未核实」。**

---

### E. 覆盖率（coverage）与合规度量

#### E-1 核心结论：**未找到"规则库覆盖率"的标准定义。**

已穷尽检索：DSA Art 15/17/24/34/35/37/42 原文、DSA 透明度数据库全部官方文档与 schema、EC 官方 FAQ、Meta / YouTube / TikTok 全部指标定义页、Meta CSER 数据字典、TikTok CGER README 与术语表、Santa Clara 1.0 与 2.0、OpenAlex 检索（"coverage of content moderation policies" / "rule coverage audit content moderation" / "measuring completeness of content moderation policy taxonomies"）。**没有任何一手来源给出「内容审核规则库覆盖率」的量化定义。**

#### E-2 找到的**最接近**的一手材料（按贴合度排序）

**(1) DSA 法定模板把"漏检/覆盖率"维度落到了 `Recall` 字段上——这是唯一被法规模板承接的覆盖率型指标。**
来源：Google/YouTube 的 DSA 透明度报告 H1 2026，`8_automated_means.csv`（官方申报文件）。
该 CSV 的指标名为 `Accuracy of the automated means - Recall`，Scope 值为 `Q1 Violative View Rate (VVR) for Videos` / `Q2 Violative View Rate (VVR) for Videos` / `H1 Violative View Rate (VVR) for Comments`，数值 0.0017–0.0019 / 0.0015–0.0017 / 0.0013–0.0018。
→ **语义**：法规要求申报"自动化手段的准确性与可能错误率"（Art 15(1)(e)），YouTube 用 **VVR（违规浏览量占比）** 来充填其中代表"漏检"的一侧。**precision ≈ 0.87–0.90 与 recall/VVR ≈ 0.0017 并列，正是"覆盖面"的可比形式。**

**(2) DSA Art 15(1)(c)：法条用"分类完备性"而非"覆盖率"来规定披露义务。** 逐字：
> "the information reported shall be **categorised by the type of illegal content or violation of the terms and conditions of the service provider, by the detection method and by the type of restriction applied**"

→ 即：**要求按（违规类型 × 检测方式 × 处置类型）三维交叉全量披露**。这是"规则库覆盖率"在法规文本中最接近的等价物（要求"每一格都要有数"），但法条本身**不定义覆盖率数值**。

**(3) DSA Art 15(1)(e)：唯一被点名的准确度指标，但仍是"准确率/错误率"而非"覆盖率"。** 逐字：
> "indicators of the accuracy and the possible rate of error of the automated means used in fulfilling those purposes"

**(4) DSA Art 42(2)(c) 要求把上述准确度指标按成员国官方语言逐一切分。** 逐字：
> "the indicators of accuracy and related information referred to in Article 15(1), point (e), broken down by each official language of the Member States"

→ 这是**"语言维度覆盖率"**的法定要求（每种语言都必须有准确度指标）。

**(5) DSA Art 34(2)(b)(c)：风险评估只要求"考虑"内容审核系统与条款执行，无量化定义。** 逐字：
> "…whether and how the following factors influence any of the systemic risks referred to in paragraph 1: … (b) their content moderation systems; (c) the applicable terms and conditions and their enforcement"

→ **Art 34/35 全篇不含任何百分比、阈值或覆盖率定义**，只有"diligently identify, analyse and assess"这样的过程义务。

**(6) 行业中实际被当作"覆盖率型指标"使用的四个分母式度量**（三者口径互不相同、不可直接比较）：

| 度量 | 分母 | 分子 | 出处 |
|---|---|---|---|
| Meta **prevalence** | 全部内容**浏览量**（抽样估算） | 违规内容浏览量 | Meta prevalence metric 页 |
| YouTube **VVR** | 全部视频**浏览量**（分层随机抽样、每日抽样） | 违规视频浏览量 | Barnett (2021) VVR Methodology |
| TikTok **Proactive removal rate** | **已处置**视频数 | 用户举报前即被处置的视频数 | TikTok CGER 术语/图表脚注 |
| TikTok **Video: Removal rate of published** | **已发布**视频数 | 被移除视频数（2026Q1 = 0.5%） | TikTok CGER 原始 CSV |

→ **关键差异**：prevalence / VVR 的分母是"曝光量"，TikTok 的 removal-rate-of-published 的分母是"发布量"，Meta 的 proactive rate 的分母是"已处置量"。**只有前两者在数学上等价于"未被拦截的违规占比"（即 1 − 覆盖率的一种可能定义）；后两者都不能用来推断漏检量。**

**(7) Santa Clara Principles 2.0 Operational Principle 1** 要求披露"自动化流程的 confidence/accuracy/success rates"与"按语言、内容类别切分"，但同样**不给出覆盖率的定义或阈值**（逐字见 D-2）。

---

## 3. 指标对照表（三家平台 + DSA）

| 维度 | **Meta** | **YouTube** | **TikTok** | **DSA（法规模板）** |
|---|---|---|---|---|
| **"违规占比"指标名** | Prevalence | Violative View Rate (VVR) | Video: Removal rate of published | 无对应法定指标名；由平台自选填入 |
| **定义原文** | "measures the estimated percentage of those views that were of violating content" | "the percentage of views of videos on the YouTube platform that violate its Community Guidelines" | 图表名为 "Removal Over Publish"；CSV metric `Video: Removal rate of published` | — |
| **分母** | 全部内容**浏览量** | 全部视频**浏览量** | 已**发布**视频数 | — |
| **是否抽样** | **是**（"estimated using samples of content views"） | **是**（5 层动态分层随机抽样，每日；季度值 = 9 个日估计按浏览量加权平均） | 否（全量计数） | — |
| **最新值** | FB 2026Q2：Hateful Conduct 0.02%；VGC 0.20–0.21%；Adult Nudity 0.07–0.08%；另有 4 类仅给 `<0.05%` 上界 | 2026 H1：Q1 VVR 0.0017–0.0019；Q2 VVR 0.0015–0.0017；Comments H1 VVR 0.0013–0.0018 | 2026Q1：Video removal rate of published **0.5%**；Comments **0.2%**；LIVE **2.7%** | — |
| **主动发现率指标名** | Proactive rate | 未用此名（自动化占比以 measure 数体现） | Proactive removal rate | Art 15(1)(c) 要求按 detection method 分类披露 |
| **定义原文** | "percentage of all content or accounts acted on that we found and actioned before users reported them to us" | — | "Proactive removal means identifying and removing a video before it's reported." | "…categorised by … the detection method…" |
| **分母（关键）** | **已处置量**（≠ 全部违规量） | — | 已处置视频数 | — |
| **最新值** | FB 2026Q2：Spam 99.60%、Suicide/Self-Injury 99.30%、Terrorism 98.80%、VGC 96.20%、Adult Nudity 96.20%、Violence & Incitement 73.50%、**Hateful Conduct 66.40%**、Bullying & Harassment 66.60% | H1 2026 自动化处置 34,496,297 vs 非自动化 1,931,541（≈94.7% 自动化） | 2026Q1：**99.3%**；官方口径 "Automated removals, including those by AI, now make up more than 96% of total removals" | — |
| **准确率/精确率** | Enforcement Precision（FB 2026Q2 **90.80%–91.85%**；IG **90.78%–92.24%**）；False Positive Volume（FB 30.2–30.8M；IG 9.1–9.5M） | **Precision 0.874–0.896**；Accuracy videos 0.998–0.999，comments 0.98 | 未公布对应数值 | Art 15(1)(e)："indicators of the accuracy and the possible rate of error"；Art 42(2)(c) 要求按语言切分 |
| **申诉量** | Content Appealed | Number of complaints submitted to the internal-complaints mechanism | 未在 CGER 主指标中单列（"Appeal success rate" 定义见 IP 术语表） | Art 15(1)(d)："the number of complaints received… the number of instances where those decisions were reversed" |
| **申诉最新值** | FB 2026Q2 合计（14 类）：Hateful Conduct 253,800；Adult Nudity 643,500；Spam 382,400；… | **365,511**（upheld 233,329 / reversed 91,810；median 5 天） | — | — |
| **恢复/推翻率** | "Content Restored with appeal" + "Content Restored without appeal" 分列 | 由 upheld/reversed 直接给出 **reversal rate ≈ 25.1%**（91,810 / 365,511） | Videos restored **8,838,710**（÷ 总移除 184,012,576 ≈ **4.80%**） | Art 15(1)(d) 要求报 "the number of instances where those decisions were reversed" |
| **恢复的最新值** | FB 2026Q2 Hateful Conduct：with appeal 28,700 + without appeal 2,500（合计 31,200 / actioned 1,500,000 ≈ 2.1%） | reversed 91,810 | — | — |
| **口径警示（原文）** | "the numbers can't be compared directly to content actioned or to content restored for the same quarter"；"This metric shouldn't be interpreted as an indicator of the accuracy of our decisions" | — | "Values may be omitted for privacy if they represent fewer than 1,000 users." | Art 24(5)：提交前必须去个人数据 |
| **报告周期与格式** | 半年报（季度数据） | DSA 报告：半年；GTR 页面另有季度 | 季度 | Art 15：至少每年一次，machine-readable；Art 42：VLOP 至少每半年 |
| **数据可下载性** | **CSV 内嵌页面 SSR payload**（`CSER-2026_Q2.csv`，5,409 行，无需授权） | **官方 GCS bucket 结构化 CSV**（`report-downloads/YouTube - DSA ...zip`） | **官方 CDN zip（原始 CSV，12.9MB，96,681 行）** | 数据库全量 **daily dumps（csv/Parquet，全量+轻量两版）**，保留 5 年 |
| **个人数据/隐私处理** | — | — | 少于 1,000 用户的值省略 | Art 24(5) 强制去个人数据 |

---

## 4. 失败清单

| URL / 目标 | 失败原因 | 替代来源 | 结果 |
|---|---|---|---|
| `eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2065`（及 `HTML/`、`OJ:` 变体） | **AWS WAF JS 挑战**，返回 HTTP 202 + 2,038 bytes 挑战页 | **EU 出版局 Cellar API** `publications.europa.eu/resource/celex/32022R2065` | ✅ 已解决（838KB 官方全文） |
| `transparency.meta.com/.../methodology/`、`/hate-speech/facebook/`、`/guidelines/` | HTTP 404（路径已改版） | 正确路径为 `/policies/improving/*-metric/` 与 `/reports/community-standards-enforcement/<policy>/facebook/` | ✅ 已解决 |
| Meta 站点初始访问（无完整浏览器头） | HTTP **400**（Akamai bot 防护） | 加 `--compressed --http2` + `Sec-Fetch-*` + `sec-ch-ua` 全套头 | ✅ 已解决 |
| `transparency.meta.com/*`、`www.tiktok.com/*`、`support.google.com/*`、`transparencyreport.google.com/*`、`www.google.com/*`、`web.archive.org`、`r.jina.ai` | **直连超时 000**（本机网络对这些域整体不可达） | 本机代理 `http://127.0.0.1:7890` | ✅ 已解决 |
| `transparencyreport.google.com/youtube-policy/overview` | HTTP 200 但仅 7,814 bytes 的 **JS 外壳**，数据由客户端异步加载；`api/v3/youtubepolicy/*` 全部 404 | **官方 GCS bucket** `storage.googleapis.com/transparencyreport/`（含 `youtube/YouTube's VVR Methodology…pdf` 与全部 DSA 报告 zip） | ⚠️ **部分替代**：拿到 VVR 方法学原文与 DSA 结构化数据，但**未拿到 GTR 网页上按违规类型切分的 removals/appeals 明细**（见下条） |
| `support.google.com/youtube/answer/9228202` | HTTP 404（answer ID 已失效/改版） | 未找到现行 help article ID | ❌ **未核实**：**YouTube Community Guidelines Enforcement Report 的官方"指标定义"页面未取得**；现用的是 DSA 报告字段名 + VVR 方法学 PDF |
| `transparency.dsa.ec.europa.eu/page/faq`、`/page/data-access`、`/page/datasets`、`/page/download`、`/page/overview`、`/datasets` | HTTP 404（导航已重构） | 正确路径 `/explore-data/download`、`/page/documentation`、`/page/research-api`、`/page/data-retention-policy` | ✅ 已解决 |
| `santaclaraprinciples.org/principles/` | HTTP 404 | SCP 2.0 全文在**首页**；2018 版在 `/scp1` | ✅ 已解决 |
| `landis-koch-1977.pdf`（所有已知镜像：dentalage.co.uk、jstor、wiley、jhsph、stat.washington.edu、ics.uci.edu、medcalc.org、deepblue.lib.umich.edu 等 12 个） | 403 Cloudflare / 404 / 付费墙；Semantic Scholar 判定 `CLOSED`，Unpaywall `is_oa:false` | **Stata 官方手册**（逐字六档 + 原刊页码锚点 `(1977a, 165)`）+ PubMed E-utilities 摘要 | ⚠️ **原文不可得**；量表逐字已由两条独立开放来源核实，页码 165 已锚定 |
| `pubmed.ncbi.nlm.nih.gov/843571/` | HTTP 203，返回 **JS proof-of-work 挑战页**（非摘要） | `eutils.ncbi.nlm.nih.gov/.../efetch.fcgi?db=pubmed&id=843571&rettype=abstract&retmode=text` | ✅ 已解决 |
| Cohen (1960) 原文（Sage `10.1177/001316446002000104` 及 `/doi/pdf/`；uvm.edu；colorado.edu） | bot 挑战页 / 404 / 14-byte 残页；OpenAlex `is_oa:false, any_repository_has_fulltext:false` | 只能用课程讲义转引 + Krippendorff (2004) Figure 2 中的 κ 表达式 | ❌ **未核实**：不得引用 1960 年原文措辞 |
| Krippendorff *Content Analysis*（3rd/4th ed.）§11.x | 无开放副本；Google Books / 出版社样章不可达 | HCR 2004 论文中的 α 定义（Figure 2）+ 阈值原文 | ❌ **未核实**（书内定义） |
| `asc.upenn.edu/.../Reliability in Content Analysis.pdf` | 403 Cloudflare | **UPenn ScholarlyCommons 机构库 DSpace bitstream** | ✅ 已解决（MD5 校验一致） |
| `faculty.washington.edu/jwilker/559/Krippendorf.pdf` | 404 | 同上 | ✅ 已解决 |
| Brave Search `search.brave.com` | 前 2 次查询可用，之后持续 **HTTP 429 / "safest" 拦截页** | 改用 Google 一次（失败，需 JS）、Bing（经代理返回中国区无关结果）、OpenAlex / Semantic Scholar API、NCBI E-utilities、ACL Anthology 站内检索 | ⚠️ 检索能力受限 |
| `web_search` 工具（firecrawl） | **免费额度耗尽，`retry_after_seconds: 86000+`**（约 24 小时） | 同上 | ❌ 本会话不可用 |
| `exa_search` 工具 | 未配置 API Key | — | ❌ 不可用 |
| 浏览器工具（`browser_*`） | "The controlled tab was closed. Select the current page in the side panel before retrying."——**受控标签页未就绪，无法驱动真实浏览器绕过 bot 防护** | 用 curl + 代理 + 完整浏览器头 | ⚠️ 未使用 |
| `aclanthology.org`（直连） | 8 秒超时 | 经代理可达 | ✅ 已解决 |
| Jigsaw / Borkan et al. 作为 IAA 来源 | **该论文不含任何 IAA 统计量**（全文 regex 扫描 `kappa|agreement|inter-annotator` 零命中） | 改用 Waseem (2016)、Sap et al. (2019)、GHC、OffensEval | ❌ **应剔除**，勿引用 |
| 任务书给出的 GHC 出处 "LREC 2020" / `2020.lrec-1.169` | 该 ID 实为 *Alector* 法语简化语料；**不存在 LREC-2020 的 GHC 论文**（已核对全部 895 篇 LREC-2020 标题） | 正确出处：Kennedy et al. (2022), *Language Resources and Evaluation* **56:79–108**, DOI 10.1007/s10579-021-09569-x（闭源，用 author manuscript） | ✅ 已更正 |
| 任务书给出的 Waseem 2016 出处 `W16-5105` | 该 ID 实为 BioTxtM 2016 生物医学摘要论文 | 正确 ID **`W16-5618`** | ✅ 已更正 |
| "State of Content Moderation 报告"（SCP 2.0） | SCP 2.0 全文与 Open Consultation Report **grep 零命中** | SCP 2.0 中对应表述为 Operational Principle 1 的 "All data should be provided in a regular report, ideally quarterly, in an openly licensed, machine-readable format." + 新增的州行为者报告要求 | ❌ **未核实** |
| 「规则库覆盖率」的标准定义 | 见 E-1，穷尽检索后**不存在** | 最接近者为 DSA Art 15(1)(c) 的三维分类完备性要求 + YouTube 在 DSA 模板 `Recall` 字段申报 VVR | ❌ **未找到标准定义** |

---

## 5. 数据口径上必须在报告里说清的三件事

1. **"主动发现率"不是覆盖率。** Meta 官方原文自己承认："Our proactive rate doesn't reflect how long it takes us to detect violating content or how many times it was viewed before detection. **It also doesn't reflect how many violations we failed to detect altogether**."（proactive-rate-metric 页）——分母是"已处置量"，漏检在数学上不可见。
2. **只有 prevalence / VVR 是"分母覆盖式"度量，且都是抽样估算。** 二者分母都是浏览量；Meta 会在样本不足时退化为上界（`<0.05%`），并明确警告"changes this small may not be statistically significant"。
3. **TikTok 的 0.5% "removal rate of published" 与 Meta 的 0.02% "prevalence" 不可比**：前者分母是发布量、全量计数；后者分母是浏览量、抽样估算。把这两个数字放进同一张图比较是口径错误。
