# -*- coding: utf-8 -*-
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()

old = u"""### 8.4 Amazon —— 本次未取得有效证据

`_evidence/R5/platforms/` 下的 `amazon-*.html` 文件（`amazon-medical-devices.html`、`amazon-conditional-products.html`、`amazon-product-detail-page-rules.html`、`amazon-advertising-policies.html`、`amazon-aplus-content.html`、`amazon-restricted-products.html`、`amazon-health-personal-care.html`）**均只渲染出约 1,894 字符的骨架，未包含政策正文**（Amazon Seller Central / Advertising 帮助页需要登录或依赖 JS 渲染）。

**因此本节对 Amazon 只有一条间接但重要的发现**（来自 §7.7 的竞品实证）：**Momcozy 的 Amazon listing 使用了品牌自控的结构化属性字段**（`Product Style: hospital grade`），并且这个字段与官网的否认声明矛盾。

> **这意味着：Amazon 侧的风险点不是"政策写了什么"，而是"品牌自己填了什么字段"。** 结构化属性（`Product Style`、`Material Type Free`、`Special Feature` 等）是**可直接被消费者看到的、品牌自己声明的产品事实**，落入 UCPD Art. 6(1)(b) 的 "specification"。**委托方应当把 Amazon listing 的结构化属性纳入内容审查范围** —— 这一步不需要等 Amazon 政策原文，现在就能做。
"""

new = u"""### 8.4 Amazon —— Seller Central 侧为登录墙，但 **Ads 侧取得正文**，且含一条可直接解决 H08/M06 的条款

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
"""

n = s.count(old)
if n != 1:
    sys.stderr.write("MISMATCH count=%d\n" % n); sys.exit(1)
s = s.replace(old, new)
io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
