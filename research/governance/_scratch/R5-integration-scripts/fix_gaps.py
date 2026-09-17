# -*- coding: utf-8 -*-
"""R5 integration pass 4: fix evidence filenames + close/refine gaps G1, G11; add G1b."""
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()
subs = []

# ---------- A. real on-disk filename corrections ----------
s=s.replace(u"_evidence/R5/ftc/ecfr-16cfr255-endorsement-guides.html", u"_evidence/R5/ftc/ecfr-16cfr255-endorsement-guides.TEXT.txt")
s=s.replace(u"_evidence/R5/ftc/ftc-deception-1983.pdf", u"_evidence/R5/ftc/ftc-deception-policy-statement-1983.pdf")
s=s.replace(u"`_evidence/R5/ftc/ftc-deception-policy-statement-1983.pdf` / `.txt`（15 页，46,710 字符）", u"`_evidence/R5/ftc/ftc-deception-policy-statement-1983.pdf`、`.PDFTEXT.txt`（15 页，46,710 字符）")
s=s.replace(u"_evidence/R5/ftc/ftc-policy-statement-advertising-substantiation-1984.PAGETEXT.txt", u"_evidence/R5/ftc/ftc-policy-statement-advertising-substantiation-1984.CLEAN.txt")

# ---------- B. close G1 (EU register) ----------
old_g1 = u"| **G1** | **EU 是否存在针对泌乳/母乳/催乳的授权 health claim** | 计划检索 EU Register of nutrition and health claims（`ec.europa.eu/food/food-feed-portal/screen/health-claims/registers`）；因 Firecrawl 限流 + 门户需 JS 交互，**未完成** | 门户为 JS 渲染；`web_fetch`/`curl` 无法穿透 | **中等**。不影响「1924/2006 不适用于吸奶器」的结论（该结论由 Art. 1(2) 的 \"foods\" 定义直接支撑），但无法断言\"欧盟没有任何泌乳类授权 claim\"。**若法律团队要写\"在欧盟，more milk 类声称无任何授权基础\"，必须先补这一项。** |"
new_g1 = u"| **G1** | ~~**EU 是否存在针对泌乳/母乳/催乳的授权 health claim**~~ —— **已完整检索，本项关闭** | 绕开门户 SPA，直接调用 FIP 后端 API：`ec.europa.eu/food/food-feed-portal/**backend**/api/policy-items?foodDomain=nut&authorisationType=nut_auth`（`backend/` 段由 `assets/env-json-config.json` 的运行时 `core.base` 覆盖得到）。取回 **2,337 条**全量 claim（19,885,668 B JSON） | **已解决**。**结论：授权项为 0。** 全部泌乳类词汇（`lactation` 2 命中、`breast milk` 3、`breastfeed` 2、`milk secretion`/`mammary`/`nursing` 各 1）**授权的命中数一律为 0**；`milk production`、`milk supply`、`prolactin`、`galactagogue`、`let-down`、`lactogenesis`、`mammogenesis`、`human milk` **全库 0 命中** | **已关闭**。结论与陷阱说明见 **§4.4 法源 20**（含 silymarin POL-HC-6243 被 Reg (EU) No 666/2011 驳回的原文、以及「2 条授权 DHA 声称含 `breastfed` 但描述的是孩子发育、不可延伸」的警示）。**独立复核**：另一 agent 从原始 JSON 重算，四个计数逐项复现一致。注意口径：按 **claim status** 为 269 授权 / 按**法律依据**为 228，引用时须注明用了哪个。 |"
subs.append((old_g1, new_g1))

# ---------- C. close G11 ----------
old_g11 = u"| **G11** | **FTC 针对「clinically proven」的具体执法案例原文** | 委派并行分项；本次本人未逐一核验案卷 | 时间分配 | **中等**。§6.1 引用的 **POM Wonderful LLC, 155 F.T.C. 1 (2013)** 与 **POM Wonderful LLC v. FTC, 777 F.3d 478 (D.C. Cir. 2015)** 是通过 FTC HPCG 2022 的脚注间接引用的，**未取得案卷原文逐字文本**。**若要在合规文档里直接引用判词，需补 POM Wonderful 的 Commission Opinion 原文。** |"
new_g11 = u"| **G11** | ~~**FTC 针对「clinically proven」的具体执法案例原文**~~ —— **已取得 3 份案卷原文，本项关闭** | `_evidence/R5/ftc/enforcement/`：**NeuroMetrix**（1:20-cv-10428-FDS，器械）、**BASF/DIEM**（C-4744 / C-4745）、**Quincy Bioscience / Prevagen**（1:17-cv-00124）的 complaint 与 order 原文（各含 PDF + PDFTEXT） | **已解决**。**NeuroMetrix 是器械类先例**，其被禁广告词 `FDA cleared` + `doctor recommended` + `clinically proven` + `100% drug free` 与吸奶器行业话术几乎逐项对应 | **已关闭**。逐字引用与判定子规则见 **§6.1 法源 30b**。**两项衍生结论**：① Quincy ¶28–29 表明**「做过一项 RCT」不是抗辩** —— FTC 攻击的是该 RCT **未在预设主要终点达到显著**、且被告做了 30+ 次事后分析，故 H03 应增加「预设主要终点 + 达到显著」子条件；② **未发现任何 FTC 吸奶器/哺乳类执法案件**，不得凭空援引。**仍缺**：POM Wonderful Commission Opinion（155 F.T.C. 1 (2013)）原文 —— 该案仍是通过 HPCG 脚注间接引用。 |"
subs.append((old_g11, new_g11))

for a, b in subs:
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:90])); sys.exit(1)
    s = s.replace(a, b)

io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
