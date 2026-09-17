# -*- coding: utf-8 -*-
"""R5 integration pass 3: FTC enforcement precedents + gap register updates."""
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()
subs = []

# ---------- 1. Insert enforcement block after 法源 30, before 法源 31 ----------
anchor = u"**法源 31 —— FTC Policy Statement Regarding Advertising Substantiation (1984-11-23)**"
enforcement = u"""**法源 30b —— 「clinically proven」的执法先例：三份案卷原文（已取得）**

前文 §9.1 对 H03 的法源判定依据的是 HPCG 2022 的**文本**。本次另外取得了 FTC 对 `clinically proven` 的**三份执法文书原文**，它们回答的是另一个问题：**FTC 实际怎么打这类声称？**

| # | 案件 | 案号 / Matter | 产品类型 | 对 `clinically proven` 的处置（逐字） |
|---|---|---|---|---|
| 1 | **FTC v. NeuroMetrix, Inc.** | D. Mass. **1:20-cv-10428-FDS**；complaint 2020-03-03；Matter 172 3130 | **器械**（Quell 神经刺激器）—— **结构上最接近吸奶器** | 起诉状 ¶13：*"…that it is **clinically proven** to do so, and that it is cleared by FDA for this specific use."*；广告原文：*"Quell is the only FDA cleared, doctor recommended, 100% drug free device **clinically proven** to relieve chronic pain at the touch of a button."*；同意令 §III.A 禁止声称 *"That any Device is **clinically proven** to: 1. Provide widespread relief from chronic or severe pain…"*，§III.B 禁止 *"That the performance or benefits of any Device are scientifically or clinically proven or otherwise established"*。**$4M 和解，约 $3.9M 退还消费者。** |
| 2 | **In re BASF SE / DIEM Labs** | **C-4744** 与 **C-4745**；Matter 192 3088；consent order 2021-06 | 膳食补充剂 | 命令 §III.A–C 禁止声称 *"that any Covered Product is clinically proven to reduce liver fat…"*、*"clinically proven to cure, mitigate, or treat any disease"*、*"that the health benefits, performance, or safety of any Covered Product is scientifically or clinically proven or otherwise established"* |
| 3 | **FTC v. Quincy Bioscience**（Prevagen） | S.D.N.Y. **1:17-cv-00124**；complaint 2017-01-09；Matter 152 3206 | 膳食补充剂 | **COUNT II "FALSE PROOF CLAIMS"**：*"Prevagen is **clinically shown** to improve memory; … in 90 days; … to reduce memory problems associated with aging…"* |

**第 3 案里对委托方最有用的是 ¶28–29**：FTC 攻击的**不是「完全没有研究」，而是一份真实存在的双盲安慰剂对照 RCT**（Madison Memory Study，n=218，9 项任务）—— 理由是它 *"failed to show a statistically significant improvement … on any of the nine computerized cognitive tasks"*，且被告随后做了 *">30 post hoc analyses"*（事后亚组分析）。

> **这直接改变 H03 的判定方式。** 委托方若要写 `clinically proven`，**「我们做过一项临床研究」不是抗辩理由**：FTC 的检验是「**该研究在预设终点上是否达到统计学显著**」。一项未达预设终点的 RCT，在 FTC 口径下**等于没有证据**；用事后分析补强会被单独点名。**建议把这一条写成 H03 的判定子规则**：不仅要有 RCT，还要**有预设主要终点且达到显著**。

**⚠️ 一条重要的否定性发现（避免过度引用）**：本次检索 FTC 案件库（`ftc-cases-search-clinically-proven.html` 等）**未发现任何涉及吸奶器或哺乳类声称的 FTC 执法案件**。

> **不要在合规文档里写「FTC 曾处罚过吸奶器品牌」—— 不存在这样的案件。** 结构上可援引的先例是 **NeuroMetrix（器械）** 与 **BASF/DIEM（补充剂）**，两者都说明：**器械类 + `clinically proven` + FDA cleared 混用，正是 FTC 的标准靶心** —— 而 Quell 那句广告词（`FDA cleared` + `doctor recommended` + `clinically proven` + `100% drug free`）与吸奶器行业的常见话术**几乎逐项对应**（对应 H06 / H04 / H03 / H05）。

**本地证据**：`_evidence/R5/ftc/enforcement/`（6 份 PDF + 6 份 PDFTEXT + 检索页 HTML）。

**法源 31 —— FTC Policy Statement Regarding Advertising Substantiation (1984-11-23)**"""

subs.append((anchor, enforcement))

for a, b in subs:
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:90])); sys.exit(1)
    s = s.replace(a, b)

io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
