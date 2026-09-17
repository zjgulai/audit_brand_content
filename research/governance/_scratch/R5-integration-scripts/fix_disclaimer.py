# -*- coding: utf-8 -*-
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()

anchor = u"831:**更正后的字段语义**"
# find the paragraph after line 831 by its leading text
needle = u"> 检验方法（可直接做成规则）：**把免责声明遮住，这句文案还成立吗？** 如果不成立 → 免责声明无效，原声称判险。"

addition = needle + u"""

**法源 37 —— 平台侧对免责声明的相反要求（TikTok，逐字）**

> **Comparative claims may be allowed, subjected to the provision of evidence or clear disclaimer(s).**

（TikTok Advertising Policies, *Misleading and false content*, "Malicious, Subjective and Before-and-after Comparisons"，Last updated **April 2026**；`_evidence/R5/platforms/tiktok-misleading-and-false-content.txt:75-77`。详见 §8.5(1)。）

**两条法源合起来看，是这个规则库最容易搞错的一处**：

| | FTC（法源 34/36） | TikTok（法源 37） |
|---|---|---|
| 免责声明的作用 | **不能**治愈欺骗 → 是**上限**：免责声明**不能**让一个无证据的声称变合法 | **可以**作为放行条件 → 是**下限**：**有证据 *或* 有清晰免责声明**即可过审 |

一个声称要同时满足两者，唯一可行解是 **「有证据 **且** 有合格免责声明」**：

- 只有免责声明、没有证据 → **TikTok 可能放行，但 FTC 判欺骗**；
- 只有证据、没有免责声明 → **FTC 可接受，但 TikTok 可能拒登**。

**因此当前「命中豁免词 → 不判险」的设计比表面看起来更危险**：它实际上是把 **TikTok 的下限当成了 FTC 的上限** —— 用一句免责声明换取了本应由证据换取的放行。这与 §7.8 的实证吻合：Momcozy 约 14 处功效声称中**只有 1 处**带免责声明，而与此同时 H02 类的 `more milk` / `release oxytocin` 声称**没有** RCT 级证据支撑。"""

subs = [(needle, addition)]

for a, b in subs:
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:80]))
        sys.exit(1)
    s = s.replace(a, b)

# renumber the subsequent 法源 markers in section 6.3 only if they collide
io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
