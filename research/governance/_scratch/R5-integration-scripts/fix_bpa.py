# -*- coding: utf-8 -*-
"""R5 integration pass 9: verified BPA/EU materials corrections from the materials subagent."""
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()
subs = []

# ---------- 1. fix 807.65 subpart B -> D ----------
subs.append((u"subpart-B/section-807.65", u"subpart-D/section-807.65"))

# ---------- 2. rewrite 10.2 with verified sources ----------
old_102 = u"""**本次调研未能取得 FDA 关于 BPA 的官方原文页面**（`fda.gov` 对 `curl` 返回 Akamai 拦截，`web_fetch` 对该具体 URL 未尝试成功）。**因此「FDA 对 BPA 的立场原文」与「BPA 从婴儿奶瓶/吸嘴杯/配方粉包装中移除的具体 Federal Register 引用」在本分节标注为未核实**（见 §12 G8/G17）。"""

new_102 = u"""**本次已补齐美国侧的法源（2026-09-15 补证）**：`fda.gov` 虽对 `curl` 返回 Akamai 拦截，但 **`ecfr.gov` 可正常取到正文**（需 `-L` 跟随 302 + 完整浏览器 UA，经本地代理）。本节此前标注为未核实的两项，现均有 Primary Source。

**法源 —— 21 CFR 177.1580(d) Polycarbonate resins（逐字，权威原文）**

> **(d) Polycarbonate resins may be used in accordance with this section except in infant feeding bottles (baby bottles) and spill-proof cups, including their closures and lids, designed to help train babies and toddlers to drink from cups (sippy cups).**
>
> [42 FR 14572, Mar. 15, 1977, as amended at … **77 FR 41902, July 17, 2012**]

- 来源：eCFR，Title 21 截至 **2026-09-10** 的现行版本
- 本地证据：`_evidence/R5/materials/ecfr-177-1580-polycarbonate-resins.html`

**逐字读出来的三层含义（这才是「BPA-free 不是法定要求」的真正法源）**：

1. **它是一个「用途排除」，不是「物质禁令」。** 该条禁止的是把**聚碳酸酯树脂**用于婴儿奶瓶与吸嘴杯（含其盖与扣件）这几类**特定产品**；**BPA 作为聚碳酸酯单体在其他所有用途中仍然合法**。所以「美国禁了 BPA」是错的，正确表述是「美国把 BPA 从婴儿奶瓶/吸嘴杯这两类用途中移出了」。
2. **它管的是聚碳酸酯（PC），不是硅胶。** §177.1580 的标题是 *Polycarbonate resins*。**委托方若使用的是矽膠與 PP 部件，本条的适用性與「矽膠是否食品级」是两回事** —— 不要把 177.1580 与 177.2600（rubber articles，见 §10.1）混为一谈。**Momcozy 的 `BPA-free` 声称若要核查，核查对象是奶瓶/储奶容器这类 PC 可能出现的部件，而 `food-grade silicone` 的核查对象是 §10.1 的萃取限值。**
3. **该排除是通过「食品添加剂废弃（abandonment）」程序完成的，不是基于安全性。** 对应 **77 FR 41899（2012-07-17，ACC 申请）** 与 **78 FR 41840（2013-07-12，Markey 申请）**。**FDA 的逐字表述为：`An amendment of the food additive regulations based on abandonment is not based on safety`。** FDA 同时**拒绝**设立任何 BPA 标识要求（78 FR 41840, Response to Comment 7），并**驳回**了 NRDC 要求全面禁止 BPA 用于食品包装的公民请愿（2012-03-30）。

> **⚠️ 这一条对委托方的文案有直接后果**：既然美国的移除**不是安全性结论**，那么把 `BPA-free` 当作**安全声称**来用（如 §10.1 那条 `BPA-free, food-grade materials: Safe for both mother and baby.`）在法源上是**双重错位** —— 既不是法定认证，也不代表监管机构认定 BPA 不安全。`BPA-free` 只能作为**成分事实**陈述，不能承载安全结论。"""

subs.append((old_102, new_102))

# ---------- 3. EU 2024/3190: replace the "未取得" note with verified + scope warning ----------
old_eu = u"- Commission Regulation (EU) 2018/213 与 **(EU) 2024/3190**（2024-12-19 BPA 食品接触材料禁令）的原文、CELEX 号与生效/过渡日期（**G8**）"
new_eu = u"""- ~~Commission Regulation (EU) 2018/213 与 **(EU) 2024/3190** 原文与生效/过渡日期~~ —— **已取得（见下方 §10.2b），本项关闭**"""

subs.append((old_eu, new_eu))

for a, b in subs:
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:90])); sys.exit(1)
    s = s.replace(a, b)

io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
