# -*- coding: utf-8 -*-
"""R5 fixup: restore 8.6-before-8.7 order; update Appendix C follow-ups."""
import io, sys

P = "research/governance/R5-category-and-competitors.md"
t = io.open(P, encoding="utf-8").read()
orig = len(t)

# ---- 1. restore numeric order: §8.6 (conclusions) must precede §8.7 (reflex sentences) ----
h7 = u"### 8.7 四个平台的「反射句」"
h6 = u"### 8.6 本节的落地结论"
h9 = u"## 九、对 Momcozy 的直接含义"
for h in (h7, h6, h9):
    if t.count(h) != 1:
        print("ABORT: heading not unique:", h, t.count(h)); sys.exit(1)

i7, i6, i9 = t.index(h7), t.index(h6), t.index(h9)
if not (i7 < i6 < i9):
    print("ABORT: unexpected order", i7, i6, i9); sys.exit(1)

sep = u"\n\n---\n\n"
block87 = t[i7:i6]                      # §8.7 body incl. trailing separator
block86 = t[i6:i9]                      # §8.6 body incl. trailing separator
for b in (block87, block86):
    if not b.endswith(sep):
        print("ABORT: block does not end with separator"); sys.exit(1)

t = t[:i7] + block86 + block87 + t[i9:]
print("  - restored order: 8.6 now precedes 8.7")

# ---- 2. Appendix C: mark platform-evidence item done, add platform follow-ups ----
old_p1 = u"| **P1** | 补齐 **平台政策原文**的剩余缺口：Amazon Seller Central（登录墙） | 调研 / 商务 | Meta、Google、**TikTok 已补齐**（见 §8.5），规则库要建 `platform` 维度已具备三家依据；**Amazon 侧需走账户经理索取**。见 §12 G7b |"
new_p1 = u"""| **P1** | **清理规则库与合规文档里的失效平台引用**：不得再使用 Google `answer/6020955`（现为 Misrepresentation，非 Healthcare）、Meta "Personal health"（标准已不存在）、TikTok `/i18n/help/article/` 前缀、以及措辞 "negative body image"（Meta 现行正文无此短语） | 规则库维护 / 合规 | **这是四类失效里唯一会静默出错的一类** —— answer ID 被复用后指向的是"仍然有效但完全不同"的政策页，不会报 404。见 **§8.0(1)** |
| **P1** | **把 `before/after` 从布尔字段改为条件字段**（`平台 × 有无证据或免责 × 是否与产品相关`） | 规则库维护 | TikTok 与 Amazon **禁止**、Meta **有条件允许**、Google **不作为素材规则** —— **单一布尔值在四个平台里至少错两个**。见 **§8.6 结论 9 / §8.7 E** |
| **P1** | **把 `severity` 与「具体子政策」绑定，而不是与主题绑定** | 规则库维护 | Google 同一条健康声称违规因命中不同子政策而落入「检测即停号、无预警」与「停号前至少 7 天预警」两个等级。见 **§8.6 结论 10 / §8.7 F** |
| **P1** | **为平台政策建立独立复核节奏**并记录"引用日 + 页面变更日" | 治理流程 | Meta *Health and Wellness* 正文变更日 **Jul 22, 2026**，距今不足两个月；Amazon 两页自标 **Apr 6 / Apr 27, 2026**。**平台政策保质期短于法条**，不能与法条同一节奏复核。见 **§8.0(2)** |
| **P2** | 补齐 **Amazon Seller Central** 的品类/listing 规则（Conditional products、Restricted products、Product detail page、A+ Content、Baby 类目风格指南） | 商务（账户经理）/ 调研 | **关键问题已由公开面回答**（吸奶器明文列入 Category 1「Generally allowed」；对比禁令与举证要求已取得），**但 listing 侧规则仍需登录态**。见 §12 G7b |
| **P2** | 向 Amazon 确认 **保健产品分级表第三列**（逐档 supply 专属限制正文） | 商务 | 该列在页面 DOM 中渲染为空，故 `Permitted on all supply with the following restrictions:` 之后无正文。见 §12 G21 |
| **P3** | 补 **Meta「About ads that use health-related data」帮助文章** | 调研 | 需搜索 API 或已登录 Meta 会话。**不影响 §8.2 结论** —— 已证实 Meta 不发布独立的 "Health data" 广告标准。见 §12 G20 |
| ~~P1~~ | ~~补齐平台政策原文~~ —— **已完成**（四平台共 **64 页**政策正文：Meta 14 / Google 20 / Amazon 15 / TikTok 15；证据 `_evidence/R5/platforms/` 191 文件 / 90 MB） | 调研 | 见 §12 G7b、§8.0。**Amazon 侧由"仍缺"降级为"公开面已足、登录面待补"** |"""
if t.count(old_p1) != 1:
    print("ABORT: appendix C anchor count =", t.count(old_p1)); sys.exit(1)
t = t.replace(old_p1, new_p1, 1)
print("  - Appendix C: platform items updated")

io.open(P, "w", encoding="utf-8").write(t)
print("OK %d -> %d chars (%+d)" % (orig, len(t), len(t) - orig))
