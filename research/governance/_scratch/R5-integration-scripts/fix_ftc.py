# -*- coding: utf-8 -*-
"""R5 integration pass 2: FTC enforcement + EU register closure + nomenclature."""
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()
subs = []

# ---------- 1. nomenclature ----------
subs.append((
u'（"Pfizer factors" / "Duffy factors"，源自 *Pfizer, Inc., 81 F.T.C. 23 (1972)*）',
u'（"**Pfizer factors**" —— 源自 *Pfizer, Inc., 81 F.T.C. 23 (1972)*。**FTC 自己的用语是 "Pfizer factors"（HPCG 2022 尾注 27），不要写成 "Duffy factors"。**）'
))

# ---------- 2. EU: process claim has no Regulation text ----------
subs.append((
u"**核实结果：该表述不在 Art. 2(2)(5) 里，也不在本条例的任何位置。`physiological process` 这个词组在 Reg 1924/2006 全文中出现 0 次。**",
u"**核实结果：该表述不在 Art. 2(2)(5) 里，也不在本条例的任何位置。`physiological process` 这个词组在 Reg 1924/2006 全文中出现 0 次。**\n\n"
u"> 逐字核对方式：对**完整合并版**全文做大小写不敏感检索，词根 `physiolog` 仅命中 **5 次**，全部是 `nutritional or physiological **effect**`（Art. 2(2)(3) 的 \"other substance\" 定义，以及 Art. 5(1)(a)、5(1)(b)(i)、5(1)(b)(ii)、5(1)(d)）。**`physiological process` 作为词组出现 0 次**；它也不在 Art. 2(2)(6)（疾病风险降低定义）或 Art. 2(2)(4)（营养声称定义）中。\n>\n"
u"> **该说法的真实出处是 EFSA / 欧委会的行政用语，不是条例文本。** 见本节「法源 20」。\n\n"
u"**那么「支持某个生理过程」这类声称在欧洲的法源住在哪里？答：Art. 13(1)(a)。**"
))

# ---------- 3. Replace 法源 20 (unverified) with verified finding ----------
subs.append((
u"**法源 20 —— EU Register of nutrition and health claims（未核实项）**：本次调研**未能完成**对 EU 授权健康声称注册库中「lactation / breastfeeding / milk production / prolactin」相关条目的检索（注册库门户需要 JavaScript 交互）。**因此「欧盟是否存在任何针对泌乳的授权 health claim」这一关键问题，本次未核实。** 见第十一节。",
u"""**法源 20 —— EU Register of nutrition and health claims：已完整检索，**答案是「没有」**（本节为 2026-09-15 补齐）**

委托方若要在欧洲站写 `more milk` / 催乳 / 泌乳类声称，**必须先知道这个结论**：

> **注册库中不存在任何与泌乳、母乳、哺乳、产奶、催乳素、催乳剂（galactagogue）、奶阵（let-down）或乳腺功能相关的「授权」健康声称。所有涉及这些主题的条目一律为「未授权」。**

**检索方法与数据完整性**（可复核）：

| 项 | 值 |
|---|---|
| 数据源 | European Commission, Food and Feed Information Portal (FIP) |
| **API base** | `https://ec.europa.eu/food/food-feed-portal/**backend**/api`（`backend/` 段是门户 SPA 不暴露的关键；由 `assets/env-json-config.json` 的运行时覆盖 `modules.core.base` 得到） |
| 端点 | `GET {base}/policy-items?foodDomain=nut&authorisationType=nut_auth` |
| 取数要求 | 浏览器 User-Agent + `--compressed`（**不加压缩时 19.9 MB 响应会在约 4.4 MB 处截断成非法 JSON**） |
| 数据规模 | **2,337 条** claim = **授权 269 / 未授权 2,067 / 撤销 1**（按法律依据分：Art.13(1)=2070、Art.13(5)=162、Art.14(1)(a)=46、Art.14(1)(b)=59） |
| 本地证据 | `_evidence/R5/eu/eu-health-claims-register-RAW.json`（19,885,668 B）、`-AUTHORISED.csv`、`-NON-AUTHORISED.csv`、`-SEARCH-lactation.md`、`-VERIFICATION-independent.md` |
| 独立复核 | **由另一名 agent 从原始 JSON 独立重算**，2,337 / 269 / 2,067 / 1 四个数字逐项复现一致；并与 CELLAR 取回的 Reg (EU) No 432/2012 交叉验证（泌乳类 0 命中） |

**逐词命中数 —— 授权项一律为 0**：

| 检索词 | 全库命中 | 其中「授权」 |
|---|---|---|
| `lactation` | 2 | **0** |
| `breast milk` | 3 | **0** |
| `breastfeed` / `breast feed` | 2 / 1 | **0** |
| `milk secretion` / `mammary` / `nursing` | 1 / 1 / 1 | **0** |
| `milk production`、`milk supply`、`prolactin`、`galactagogue`、`let-down`、`lactogenesis`、`mammogenesis`、`human milk` | **0**（全库任何字段均无） | — |

**⚠️ 一个必须避开的误读（这是一个陷阱）**：注册库中**确有 2 条「授权」声称包含 `breastfed`** —— 但它们**不是泌乳声称**：

> POL-HC-6201：*"Docosahexaenoic acid (DHA) maternal intake contributes to the normal brain development of the foetus and **breastfed** infants."*
> POL-HC-6234：*"Docosahexaenoic acid (DHA) maternal intake contributes to the normal development of the eye of the foetus and **breastfed** infants."*
> （两条均为 Art. 14(1)(b)，由 Reg (EU) No 440/2011 授权）

**它们描述的是「孩子」的发育，不是母亲的泌乳。** 表述主体与声称对象都不同，**不能延伸成泌乳声称**。（另有一条授权的 "milk" 条目 POL-HC-6400，是酸奶中的乳糖消化，同样无关。）

**另一处精度问题**：天真的 `lactat` 检索会返回 8 条，但**只有 2 条是真阳性**，其余是血液**乳酸（lactate）**（运动生理学：`ventilatory and lactate thresholds`、`reduction of lactates in excess`）。且 `lactating` 作为**声称措辞**出现 0 次，仅在上述两条 DHA 声称的 **conditions of use** 字段中出现两次（`Information shall be given to pregnant and lactating women…`）—— 那是**目标人群披露**，不是声称。

**最接近的一次尝试，也被驳回了**（这是本节最有说服力的一条）：

> **POL-HC-6243**，Silymarin BIO-C®（水飞蓟），Art. 13(5)，状态 `HCCS_NON_AUTHORISED`：
> *"Suggested for improving the physiological production of breast milk during breast feeding"*
> 由 **Commission Regulation (EU) No 666/2011** 驳回；EFSA Question Q-2009-00957；理由：**effect not substantiated（效应未获证实）**。

其他被驳回的同类条目：POL-HC-7883 蜂王浆（*"Royal jelly helps promote milk secretion in breastfeeding mothers"*）、POL-HC-8511 *Lactobacillus fermentum* CECT 5716（Reg (EU) 2018/1555 驳回）、POL-HC-6285 双歧杆菌（Reg (EU) No 957/2010 驳回）、POL-HC-7516 EPA/DHA（*"increases breast milk DHA levels during nursing"*）。

**对委托方的直接结论**：

1. **`more milk` 类声称在欧盟没有任何授权基础。**「欧盟没有授权」不等于「吸奶器不能这么宣传」—— 因为 Reg 1924/2006 按 Art. 1(2) 只管 **foods**，吸奶器不是 food（见本节前文三层判断）。**但这条证据把欧洲站的风险从「可能违规」变成了「你在主张一个欧盟从未承认过的健康效应」** —— 这是 UCPD Art. 6(1)(b)（`the results to be expected from its use`）下的实质性风险，因为**整个欧盟食品健康声称体系在同一个问题上的监管判断是「证据不足、驳回」**。
2. **它对 §9.1 的 H02 判定是一个重要补强**：美国口径下 H02 是「有证据就能说」；欧盟口径下，同类声称**曾被正式提交并因证据不足被驳回**。委托方若在欧盟主张泌乳功效，需要承担的不只是「自己没证据」，而是「**监管机构已经就同一问题作出过否定判断**」。

**未取得项**：EFSA *Guidance on the scientific requirements for health claims related to functions of the body*（该文件本身）—— `efsa.europa.eu` 与 Wiley 对非浏览器客户端返回 **Cloudflare 403**，且不在 Europe PMC 开放获取库中。已改引两份可获取的 2018 年专项指南（肌肉功能与体能 EFSA J 2018;16(10):5434；抗氧化与心血管 EFSA J 2018;16(12):5136）。**正确的下一步引用是 EFSA J 2016;14(1):4367**（*General scientific guidance for stakeholders on health claims applications*），见 §12 G1b。"""
))

for a, b in subs:
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:90])); sys.exit(1)
    s = s.replace(a, b)

io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
