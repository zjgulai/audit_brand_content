# -*- coding: utf-8 -*-
"""R5 integration pass 5: add G1b (EFSA general guidance) + update priorities/counts."""
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()
subs = []

# ---------- 1. Add G1b right after the (now closed) G1 row ----------
g1_tail = u"注意口径：按 **claim status** 为 269 授权 / 按**法律依据**为 228，引用时须注明用了哪个。 |\n"
g1b = (u"| **G1b** | **EFSA *General scientific guidance for stakeholders on health claims applications*（EFSA J 2016;14(1):4367）** | 尝试取 `efsa.europa.eu` 与 Wiley DOI | **两者对非浏览器客户端均返回 Cloudflare 403**；该文亦不在 Europe PMC 开放获取库中（经 Europe PMC REST API 确认） | **中**。这是 EFSA 关于健康声称**通用科学要求**的权威文件（G1 里引用的是两份专项 2018 指南：EFSA J 2018;16(10):5434 肌肉功能与体能、EFSA J 2018;16(12):5136 抗氧化与心血管）。**若要论证「什么样的泌乳类证据 EFSA 会接受」，需要这一份。** 可用路径：机构 IP / 订阅访问，或 Europe PMC 之外的开放仓储。 |\n"
        u"| **G1c** | **欧委会关于「非食品类边缘产品」的范围指南** | 已取得 2007-12-14 常设委员会指南全文（14 页）并逐一核对 | **该 2007 指南中没有非食品边缘产品的讨论**；另在 `food.ec.europa.eu` 定位到 3 份后续 collective answer 文件，本次未下载 | **低**。不影响「吸奶器不是 food、Reg 1924/2006 不适用」的结论（该结论由 Art. 1(2) 文本直接支撑）。仅在需要欧委会**官方口径**确认「器械不适用 1924/2006」时才需要。 |\n")
subs.append((g1_tail, g1_tail + g1b))

# ---------- 2. P2 line: EU register now done ----------
subs.append((
u"| **P2** | 检索 **EU 授权健康声称注册库**中的泌乳相关条目 | 调研 | 若欧盟无授权 claim，则欧洲站 `more milk` 一律无基础。见 §12 G1 |",
u"| ~~P2~~ | ~~检索 EU 授权健康声称注册库中的泌乳相关条目~~ —— **已完成（2,337 条全量检索，授权项为 0）** | 调研 | **结论已落地**：欧洲站 `more milk` 类声称在欧盟健康声称体系中**无任何授权先例，且同类申请曾被正式驳回**。见 §4.4 法源 20 / §12 G1 |"
))

# ---------- 3. P3 line: enforcement now obtained ----------
subs.append((
u"| **P3** | 补 **POM Wonderful** 案卷原文（155 F.T.C. 1 (2013)） | 法律 | 若要在合规文档里直接引判词 |",
u"| **P3** | 补 **POM Wonderful** 案卷原文（155 F.T.C. 1 (2013)） | 法律 | 若要在合规文档里直接引判词。**注**：`clinically proven` 的执法先例已另行取得 3 份原文（NeuroMetrix / BASF-DIEM / Quincy Bioscience），见 §6.1 法源 30b —— POM Wonderful 是唯一仍缺的一份 |"
))

for a, b in subs:
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:90])); sys.exit(1)
    s = s.replace(a, b)

io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
