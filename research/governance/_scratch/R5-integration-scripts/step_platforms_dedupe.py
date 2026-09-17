# -*- coding: utf-8 -*-
"""R5 fixup: collapse the superseded G7b row and refresh its two downstream impressions."""
import io, sys
p="research/governance/R5-category-and-competitors.md"
t=io.open(p,encoding='utf-8').read(); orig=len(t)

old_row=u'| **G7b** | **Amazon 平台政策原文（仍未取得）** | `_evidence/R5/platforms/amazon-*.html` 全部 7 个 Seller Central 文件只渲染出约 1,894 字符骨架（标题均为 `Amazon`，正文实为语言选择器）；`advertising.amazon.com/resources/ad-policy` 与 `/prohibited-content` 返回 404 | **Seller Central 帮助页 `sellercentral.amazon.com/help/hub/reference/external/G…` 为登录墙**，返回通用 Amazon 外壳、无政策内容。Amazon Ads 侧部分页面可取：已确认 **Stores creative acceptance policies**（`advertising.amazon.com/resources/ad-policy/en`）为服务端渲染，含 `2.4 Claims and comparative statements`、`2.4.1 Warranty and guarantees` 等章节 | **高**。§8.4 因此仍只有间接结论。**Meta / Google / TikTok 三家的政策原文已足以支撑「platform 维度需要独立规则族」（答：需要）；但 Amazon 侧仍缺** —— 而 Momcozy 的主要销售渠道是 Amazon。替代路径：向 Amazon 账户经理索取政策文档，或用已登录卖家账号导出 Seller Central 帮助页。 |'
new_row=u'| ~~**G7b**~~ | ~~**Amazon 平台政策原文（仍未取得）**~~ —— **已被下一行的 G7b 取代（本行为首轮取证记录，保留以备追溯）** | ~~`_evidence/R5/platforms/amazon-*.html` 全部 7 个 Seller Central 文件只渲染出约 1,894 字符骨架~~；首轮只确认 **Stores creative acceptance policies**（`advertising.amazon.com/resources/ad-policy/en`）为服务端渲染 | **Seller Central 帮助页 `sellercentral.amazon.com/help/hub/reference/external/G…` 为登录墙**（此结论在第二轮取证中**依然成立**）。**当时的影响判断「Amazon 侧仍缺」已被第二轮推翻** | ~~**高**~~ → 见下一行。**首轮判断"§8.4 因此仍只有间接结论"已被否决**：第二轮取得 Amazon Ads 公开面 15 页，其中 `Claims and substantiation`、`Healthcare products and services`、`Stores creative acceptance policies` 三页**直接给出了本品类的关键结论**（含 `Breast Pump` 明文列入 Category 1、对比禁令、举证要求）。**保留本行是为了留下"判断曾经偏差"的记录。** |'
if t.count(old_row)!=1:
    print("ABORT: old G7b row count =",t.count(old_row)); sys.exit(1)
t=t.replace(old_row,new_row,1)
print("  - G7b old row marked superseded (kept for traceability)")

old_line=u'6. **G7a 已关闭 / G7b 仍开放** —— **TikTok 平台政策原文已补齐**（15 页全文，结论见 §8.5）；**Amazon Seller Central 政策原文仍未取得**（登录墙），Amazon Ads 侧仅取得 Stores CAP 等部分页面（Meta、Google 已取得）。'
new_line=u'6. **G7a 已关闭 / G7b 已降级** —— **TikTok**（15 页全文，结论见 §8.5）、**Meta**（14 页）、**Google**（20 页）政策原文均已取得；**Amazon** 由"仍缺"改为**公开面已足、登录面待补**（取得 **15 页** Amazon Ads 政策，含 `Claims and substantiation`、`Healthcare products and services`、`Baby formula and feeding accessories`、`Stores creative acceptance policies`）。**仅 Seller Central 登录墙后的品类/listing 规则仍未取得**（转记 G7b 新行与附录 C P2）。**四平台合计 64 页政策正文。**'
if t.count(old_line)!=1:
    print("ABORT: old impression line count =",t.count(old_line)); sys.exit(1)
t=t.replace(old_line,new_line,1)
print("  - appendix D impression refreshed")

io.open(p,'w',encoding='utf-8').write(t)
print("OK %d -> %d (%+d)"%(orig,len(t),len(t)-orig))
