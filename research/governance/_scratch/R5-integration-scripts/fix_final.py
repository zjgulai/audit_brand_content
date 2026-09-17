# -*- coding: utf-8 -*-
"""R5 integration pass 6: final counts + closing summary refresh."""
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()
subs = []

# ---------- 1. closing evidence tally ----------
subs.append((
u"*本文件共引用法规条款与官方文件 **45 项**、平台政策原文 **6 类**（**Meta / Google / TikTok / Amazon Ads 四家已取得正文**；仅 Amazon Seller Central 侧因登录墙未取得）、竞品页面 **90+ 页 / 7 个品牌**、逐字原文 **110+ 处**。全部证据可通过 §11 的本地路径复核。**未核实项已在 §12 全部列出（共 19 条，编号 G1–G19），未用推测填空。***",
u"*本文件共引用法规条款与官方文件 **45 项**、平台政策原文 **6 类**（**Meta / Google / TikTok / Amazon Ads 四家已取得正文**；仅 Amazon Seller Central 侧因登录墙未取得）、**FTC 执法案卷 3 宗**、**EU 健康声称注册库全量数据集（2,337 条）**、竞品页面 **90+ 页 / 7 个品牌**、逐字原文 **110+ 处**。全部证据可通过 §11 的本地路径复核。**未核实项已在 §12 全部列出（共 21 条，编号 G1–G19 + G1b、G1c），未用推测填空。已关闭的缺口在表内以删除线标注。***"
))

# ---------- 2. closing summary: G1 no longer open ----------
subs.append((
u"5. **G1** —— **EU 是否存在针对泌乳/母乳/催乳的授权 health claim**。EU Register 门户是 Angular SPA，未能检索。",
u"5. **G1 —— 已关闭（本次最重要的补证之一）** —— **EU 是否存在针对泌乳/母乳/催乳的授权 health claim**：**不存在。** 已绕开门户 SPA 直取 FIP 后端 API，全量检索 **2,337 条** claim，泌乳类词汇的**授权命中数一律为 0**；`prolactin`、`galactagogue`、`let-down`、`milk production` 等词**全库 0 命中**；最接近的 silymarin 申请（「improving the physiological production of breast milk」类申请）被 **Reg (EU) No 666/2011 以「效应未获证实」驳回**。见 §4.4 法源 20。**对委托方的意义：欧洲站的 `more milk` 类声称，问题不只是「自己没有证据」，而是「监管机构已就同一问题作出过否定判断」。**"
))

# ---------- 3. closing summary: G11 closed ----------
subs.append((
u"12. **G11 / G12 / G13 / G14 / G17 / G19** —— 次要缺口，详见 §12。",
u"12. **G11 —— 已关闭** —— `clinically proven` 的 FTC 执法先例已取得 3 份案卷原文（**NeuroMetrix** 器械案 / **BASF-DIEM** / **Quincy Bioscience**）。衍生两条：① **Quincy ¶28–29 表明「做过一项 RCT」不是抗辩**，FTC 攻击的是该 RCT **未在预设终点达到显著**且被告做了 30+ 次事后分析 → H03 应增加「预设主要终点 + 达到显著」子条件；② **不存在 FTC 吸奶器/哺乳类执法案件**，不得凭空援引。见 §6.1 法源 30b。\n"
u"13. **G1b / G1c** —— 新增两项次要缺口：EFSA 通用科学要求指南（EFSA J 2016;14(1):4367，Cloudflare 拦截）与欧委会非食品边缘产品范围指南（2007 指南中无此内容）。\n"
u"14. **G12 / G13 / G14 / G17 / G19** —— 次要缺口，详见 §12。"
))

for a, b in subs:
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:90])); sys.exit(1)
    s = s.replace(a, b)

io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
