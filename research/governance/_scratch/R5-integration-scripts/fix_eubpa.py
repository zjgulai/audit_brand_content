# -*- coding: utf-8 -*-
"""R5 integration pass 10: insert 10.2b EU BPA (2024/3190) with scope analysis."""
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()

anchor = u"### 10.3 LFGB —— 是德国食品饲料法典的**章节引用**，不是认证"

newsec = u"""### 10.2b 欧盟 BPA —— **(EU) 2024/3190 已生效，且 2018/213 已被废止**（美国口径不能平移到欧盟）

**法源 —— Commission Regulation (EU) 2024/3190（逐字）**

> **Commission Regulation (EU) 2024/3190 of 19 December 2024** on the use of bisphenol A (BPA) and other bisphenols and bisphenol derivatives with harmonised classification for specific hazardous properties in certain materials and articles intended to come into contact with food, **amending Regulation (EU) No 10/2011 and repealing Regulation (EU) 2018/213**
>
> **Article 3 — Prohibition of the use of BPA**
> 1. **The use of BPA and its salts in the manufacture of food contact materials and articles referred to in Article 1(2) and the placing on the Union market of food contact materials and articles manufactured using BPA, is prohibited.**
> 2. By way of derogation from paragraph 1, BPA and its salts may be used in the manufacture of food contact materials and articles for a specific application set out in **Annex II**, subject to the restrictions laid down therein.
>
> **Article 1(2)** —— 适用材质为：`(a) adhesives; (b) rubbers; (c) ion-exchange resins; (d) plastics; (e) printing inks; **(f) silicones**; and (g) varnishes and coatings.`
>
> **Article 13 — Repeal**：`Regulation (EU) 2018/213 is repealed.`

- CELEX：**32024R3190**；OJ L 系列 **2024/3190**，2024-12-31 公布
- 本地证据：`_evidence/R5/materials/32024R3190.{txt,xhtml}`

**⚠️ 第一条给规则库的更正**：**不要引用 Reg (EU) 2018/213 作为现行依据** —— 它已被 Art. 13 明文废止。任何引用 2018/213 的合规文档或规则条目都需要改指向 2024/3190。**注意 `silicones` 被 Art. 1(2)(f) 明确列入适用材质**，这与美国侧（§177.1580 只管 polycarbonate、不管 silicone）形成鲜明对比。

**时间表（逐字核对）**：

| 节点 | 日期 | 依据 |
|---|---|---|
| 生效 | 公布后第 20 日 → **2025-01-20** | Art. 14（`shall enter into force on the twentieth day following that of its publication`） |
| **重复使用**最终食品接触制品**首次投放市场**的截止 | **2026-07-20** | Art. 12(1) |
| 已在市场上的重复使用制品可继续流通至 | **2029-01-20** | Art. 12（其余款；**本次已核对到 Art. 12(1)，(2) 起的日期需补充确认，见 §12 G8b**） |
| 一次性制品投放市场截止 | 2026-07-20（特定品类 2028-01-20） | Art. 11(1)(2) |

**Annex II 的豁免与本品类无关**：Annex II 仅授权两类特定应用 —— ①容量 >1,000 升的自支撑制品上的**液态环氧树脂**（varnishes and coatings）；②**聚砜过滤膜组件**（plastics），且均要求 `Migration into food shall not be detectable`。**吸奶器与储奶容器不落在任何一项豁免内。**

#### ⚠️ 一个必须由法律团队裁决的适用范围问题（本次调研的新发现）

**Reg (EC) No 1935/2004 Art. 1(2)** 的适用范围是：制品在其成品状态下 `(a) are intended to be brought into contact with food; or (b) are already in contact with food and were intended for that purpose; or **(c) can reasonably be expected to be brought into contact with food or to transfer their constituents to food under normal or foreseeable conditions of use.**`

**而 Art. 1(3) 的排除项只有三项**：`(a)` 古董；`(b)` 可食用涂层；`(c)` 固定供水设备。**没有医疗器械排除项** —— 本次已逐字核对 1935/2004 全文，`medical device` / `2017/745` / `MDR` 三个词在该条例中的出现次数均为 **0**。

**这意味着适用性回到一个事实判断**：

| 立场 | 论证 |
|---|---|
| **在范围内（保守解读）** | 吸奶器的**集乳瓶、储奶容器、奶瓶**在正常使用中**必然接触母乳**，且通常以「可储奶、可喂哺」宣传 —— 直接落入 Art. 1(2)(c) 的 `reasonably be expected to be brought into contact with food`。故其 **PC 材质部件**受 2024/3190 的 BPA 禁令约束；若含矽膠部件，则 Art. 1(2)(f) 的 `silicones` 亦在列。 |
| **不在范围内（宽松解读）** | 整套产品作为 **MDR (EU) 2017/745 下的医疗器械**受器械法规管辖；储奶瓶作为**器械附件**随器械一并监管，不按食品接触材料单独适用 1935/2004。 |

**本次调研未能找到任何一方的主管机关明确表述**（欧委会 FCM 指南与 MDCG 文件均未检索到吸奶器/储奶容器的边缘定性）。**因此这是一个真实开放的适用范围问题，不是本次能定论的。**

> **为什么它值得委托方立刻处理**：这不是文案问题，而是**产品合规问题**。委托方在欧盟有 **26 条法国广告在跑**（任务书 §二.D），若其储奶/集乳部件的材质受 2024/3190 约束，则需确认：①是否含 BPA 或 BPA 衍生单体；②是否符合 Art. 8 的**合规声明（declaration of compliance, Annex III）**要求。**建议动作：向代工厂索取各 milk-contact 部件的材质声明与 FCM 合规文件，并请法律团队就「储奶容器是否适用 1935/2004」出具意见。** 见 §12 G8b。
>
> **对文案的即时含义**：`BPA-free` 在欧盟的意义与美国不同 —— 美国是「不是法定要求」（§10.2），**欧盟是「正在成为法定要求」**。因此在欧盟站，`BPA-free` 正从**卖点**退化为**合规基线**；而 §10.1 那条 `BPA-free, food-grade materials: Safe for both mother and baby.` 的风险不降反升（合规基线 + 全称安全断言）。

"""

n = s.count(anchor)
if n != 1:
    sys.stderr.write("MISMATCH anchor count=%d\n" % n); sys.exit(1)
s = s.replace(anchor, newsec + anchor)
io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
