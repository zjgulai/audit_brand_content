# -*- coding: utf-8 -*-
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()

subs = []

# 1. section 8.6 title + add conclusion 7
subs.append((
u"### 8.6 本节的六个落地结论",
u"### 8.6 本节的七个落地结论"))

subs.append((
u"| 6 | **同一类素材的合规路径因平台而异**：TikTok 对对比性素材是\"**附证据或免责声明**即可\"，而 Momcozy 现行 21 条规则**没有承载免责声明的字段** | §8.5(1) | 规则 schema 需增加 `可豁免条件` 与 `免责声明要求` 两个字段（现有 schema 只有 `豁免词`，是词级而非句级/素材级） |",
u"| 6 | **同一类素材的合规路径因平台而异**：TikTok 对对比性素材是\"**附证据或免责声明**即可\"，而 Momcozy 现行 21 条规则**没有承载免责声明的字段** | §8.5(1) | 规则 schema 需增加 `可豁免条件` 与 `免责声明要求` 两个字段（现有 schema 只有 `豁免词`，是词级而非句级/素材级） |\n"
u"| 7 | **Amazon 明文禁止「与竞品直接对比」（`We do not permit direct comparison to competitor brands.`），并要求对比声称引用独立来源且**距今 12–18 个月内**；量化性能声称的证据必须能在**产品详情页或产品包装**上被发现** | **§8.4(2)(3)** | **H08 在 Amazon 上不需要论证「是否误导」，指名对比本身不被接受**；**M06 获得一条可自动执行的判据**（引用独立来源 + 时效 ≤12–18 个月）；`28.2%` 类声称在 Amazon 上比在官网**多一层**「证据就地可发现」要求 |"))

# 2. §11.3 产出清单 —— 更新数字
subs.append((
u"*本文件共引用法规条款与官方文件 **45 项**、平台政策原文 **6 类**（Meta / Google / TikTok 已取得正文；Amazon Seller Central 侧登录墙未取得，仅 Ads 侧部分取得）、竞品页面 **90+ 页 / 7 个品牌**、逐字原文 **110+ 处**。",
u"*本文件共引用法规条款与官方文件 **45 项**、平台政策原文 **6 类**（**Meta / Google / TikTok / Amazon Ads 四家已取得正文**；仅 Amazon Seller Central 侧因登录墙未取得）、竞品页面 **90+ 页 / 7 个品牌**、逐字原文 **110+ 处**。"))

# 3. §11.1 增补 Amazon Ads 条目（插到 36 之后，即 TikTok 37 之前）
subs.append((
u"| 37 | **TikTok Advertising Policies — Misleading and false content** |",
u"| 36b | **Amazon Ads — Stores creative acceptance policies** | 全文（正文 31,413 字符；含 §2.4 `Claims and comparative statements`：`We do not permit direct comparison to competitor brands.`、`dated within the previous 12-18 months`、§2.4.1 Warranty and guarantees、Australia locale 条款） | https://advertising.amazon.com/resources/ad-policy/en | `_evidence/R5/platforms/amazon-stores-creative-acceptance-policies.html` |\n"
u"| 36c | Amazon Ads 政策其余页面（Sponsored Ads / DSP / general policies 等） | 部分取得（HTML 较大，未逐页确认正文完整度） | advertising.amazon.com/resources/ad-policy | `_evidence/R5/platforms/amazon-sponsored-ads-additional-policies.html` 等 |\n"
u"| 37 | **TikTok Advertising Policies — Misleading and false content** |"))

for a, b in subs:
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:90])); sys.exit(1)
    s = s.replace(a, b)

io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
