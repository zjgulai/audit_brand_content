# -*- coding: utf-8 -*-
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()

old_g7 = u"| **G7** | **Amazon 与 TikTok 平台政策原文** | 委派并行分项抓取；`_evidence/R5/platforms/amazon-*.html` 全部 7 个文件均只渲染出约 1,894 字符骨架；`_list_tiktok*.txt` 仅为抓取清单 | Amazon Seller Central / Advertising 帮助页需登录或 JS 渲染；TikTok 政策页未取到正文 | **中高**。§8.4、§8.5 因此只有间接结论。**Meta 与 Google 的政策原文已取得（见 §8.2、§8.3），已足以支撑\"platform 维度是否需要独立规则族\"的结论（答：需要）；但 Amazon 侧仍缺** —— 而 Momcozy 的主要销售渠道是 Amazon。 |"

new_g7 = (
u"| **G7a** | ~~**TikTok 平台政策原文**~~ —— **已补齐，本项关闭** | 改走服务端渲染的 `ads.tiktok.com/help/article/<slug>`（`/i18n/help/` 为 JS 空壳）；取得 **15 页正文 / 198,080 字符**，抓取日 2026-09-15 | **已解决**。其中 *Healthcare and Pharmaceuticals*（115,731 字符，2026-08 版）、*Weight Management and Body Image*（2026-09 版）、*Misleading and false content*（2026-04 版）三页与本品类直接相关 | **已关闭**。结论见 §8.5，含一条平台专属硬约束（美国站 medical devices 要求 18+ 定向）与一条 `平台×国家` 联合键实证（法国/黎巴嫩/卡塔尔·南非·阿联酋/土耳其 4 组市场对 medical devices 禁前后对比，**美国不在其列**）。仅 3 页（ad-review-checklist / creative-best-practices / market-specific-requirements）仍为骨架，不影响上述结论。 |\n"
u"| **G7b** | **Amazon 平台政策原文（仍未取得）** | `_evidence/R5/platforms/amazon-*.html` 全部 7 个 Seller Central 文件只渲染出约 1,894 字符骨架（标题均为 `Amazon`，正文实为语言选择器）；`advertising.amazon.com/resources/ad-policy` 与 `/prohibited-content` 返回 404 | **Seller Central 帮助页 `sellercentral.amazon.com/help/hub/reference/external/G…` 为登录墙**，返回通用 Amazon 外壳、无政策内容。Amazon Ads 侧部分页面可取：已确认 **Stores creative acceptance policies**（`advertising.amazon.com/resources/ad-policy/en`）为服务端渲染，含 `2.4 Claims and comparative statements`、`2.4.1 Warranty and guarantees` 等章节 | **高**。§8.4 因此仍只有间接结论。**Meta / Google / TikTok 三家的政策原文已足以支撑「platform 维度需要独立规则族」（答：需要）；但 Amazon 侧仍缺** —— 而 Momcozy 的主要销售渠道是 Amazon。替代路径：向 Amazon 账户经理索取政策文档，或用已登录卖家账号导出 Seller Central 帮助页。 |"
)

subs = [
 (old_g7, new_g7),
 (u"| **P1** | 补齐 **平台政策原文**（Meta Health & wellness / Google Healthcare / TikTok / Amazon） | 调研 | 规则库若要建 `platform` 维度，这是前提。见 §12 G7 |",
  u"| **P1** | 补齐 **平台政策原文**的剩余缺口：Amazon Seller Central（登录墙） | 调研 / 商务 | Meta、Google、**TikTok 已补齐**（见 §8.5），规则库要建 `platform` 维度已具备三家依据；**Amazon 侧需走账户经理索取**。见 §12 G7b |"),
 (u"6. **G7（部分）** —— **Amazon 与 TikTok 平台政策原文未取得**（Meta 与 Google 已取得）。",
  u"6. **G7a 已关闭 / G7b 仍开放** —— **TikTok 平台政策原文已补齐**（15 页全文，结论见 §8.5）；**Amazon Seller Central 政策原文仍未取得**（登录墙），Amazon Ads 侧仅取得 Stores CAP 等部分页面（Meta、Google 已取得）。"),
]

for a, b in subs:
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:80]))
        sys.exit(1)
    s = s.replace(a, b)

io.open(p, 'w', encoding='utf-8').write(s)
print("all replacements ok")
