# -*- coding: utf-8 -*-
"""R5 integration pass 11: close G8/G17, add G8b, register new evidence, fix stale note."""
import io, sys

p = '/Users/lute/Project/audit_multi_content/research/governance/R5-category-and-competitors.md'
s = io.open(p, encoding='utf-8').read()
subs = []

# ---------- 1. stale "未取得" note in 10.2 ----------
subs.append((
u"3. **EU 侧**：本次调研**未取得** Commission Regulation (EU) 2018/213 或 (EU) 2024/3190 的原文（见 §12 G8）。",
u"3. **EU 侧**：**已取得** Commission Regulation (EU) 2024/3190 原文，且发现 **Reg (EU) 2018/213 已被其 Art. 13 废止**。欧盟的 BPA 规则比美国严格得多 —— 详见下方 **§10.2b**。"
))

# ---------- 2. LFGB note: 1935/2004 Art.3 now available ----------
subs.append((
u"> **注意 LFGB § 31(1) 明确指向 Reg 1935/2004 Art. 3** —— 这给出了欧盟侧的正确引用路径（本次未取得 Reg 1935/2004 Art. 3 的逐字原文，见 §12 G8）。",
u"""> **注意 LFGB § 31(1) 明确指向 Reg 1935/2004 Art. 3** —— 这给出了欧盟侧的正确引用路径。**本次已取得 Reg (EC) No 1935/2004 Art. 3 逐字原文**（`_evidence/R5/materials/32004R1935.txt`）：
>
> > **Article 3 — General requirements**
> > 1. Materials and articles, including active and intelligent materials and articles, shall be manufactured in compliance with good manufacturing practice so that, under normal or foreseeable conditions of use, they do not transfer their constituents to food in quantities which could: (a) endanger human health; or (b) bring about an unacceptable change in the composition of the food; or (c) bring about a deterioration in the organoleptic characteristics thereof.
> > 2. **The labelling, advertising and presentation of a material or article shall not mislead the consumers.**
>
> **Art. 3(2) 是欧盟侧直接约束「材质类安全词」的条款** —— 它是 UCPD 之外、**专门针对食品接触材料广告**的误导性禁令。委托方在欧盟使用 `food-grade silicone` / `BPA-free` / `LFGB certified` 这类材质声称时，**Art. 3(2) 比 UCPD 更贴近**（UCPD 管一般商业行为，Art. 3(2) 直接管 FCM 的 labelling / advertising / presentation）。"""
))

# ---------- 3. 10.4 gap list: BPA items now obtained ----------
subs.append((
u"- FDA 对 BPA 的官方立场原文，以及 BPA 从婴儿奶瓶/吸嘴杯/配方粉包装中移除的 Federal Register 具体引用（**G8**）",
u"- ~~FDA 对 BPA 的官方立场原文，以及 BPA 移除的 Federal Register 引用~~ —— **已补齐**：法源为 **21 CFR 177.1580(d)**（逐字）+ **77 FR 41899 / 78 FR 41840**，见 §10.2"
))
subs.append((
u"- Regulation (EC) No 1935/2004 Art. 3 的逐字原文（**G8**）",
u"- ~~Regulation (EC) No 1935/2004 Art. 3 的逐字原文~~ —— **已取得**，见 §10.3 注（含 Art. 3(2) 的误导性禁令）"
))
subs.append((
u"- FDA Food Contact Substance Notification (FCN) 程序的官方说明（**G8**）",
u"- FDA Food Contact Substance Notification (FCN) 程序的官方说明（**G8**，仍未取得）\n- **各 milk-contact 部件（集乳瓶/储奶容器/矽膠件）是否适用 Reg (EC) 1935/2004 与 (EU) 2024/3190** —— 适用范围未决，见 **§10.2b** 与 **§12 G8b**"
))

# ---------- 4. G8 rewrite ----------
subs.append((
u"| **G8** | **材料类法规原文（部分取得，部分缺失）** | **已取得**：21 CFR 177.2600（含萃取限值与 177.2600(h) 奶嘴排除条款）、LFGB § 30/§ 31 德文原文。**未取得**：FDA 对 BPA 的官方立场原文页、BPA 移除的 Federal Register 引用、Reg (EU) 2018/213、**Reg (EU) 2024/3190**、Reg (EC) 1935/2004 Art. 3、FDA FCN 程序说明 | `fda.gov` 对 curl 返回 Akamai 拦截；eur-lex 部分文件需 CELLAR 路径（对 1935/2004 与 2024/3190 本次未尝试） | **中**。§10 已能给出 `food-grade silicone` / `LFGB certified` / `BPA-free` 三个结论与替换表；**缺的是 BPA 的法规状态与欧盟 2024/3190 禁令的时间表** |",
u"| **G8** | **材料类法规原文** —— **大部分已取得，本项基本关闭** | **已取得**：21 CFR 177.2600（含 (e)(f) 萃取限值与 (h) 奶嘴排除）、**21 CFR 177.1580(d)**（BPA/PC 用途排除）、**Reg (EU) 2024/3190**（含 Art. 1(2)、Art. 3、Art. 11、Art. 12(1)、Art. 13、Annex II/III）、**Reg (EC) 1935/2004 Art. 3**、LFGB § 30/§ 31 德文原文。**未取得**：FDA 自己的 BPA 立场页面（Akamai）、FDA FCN 程序说明、**Reg (EU) 2024/3190 Art. 12(2) 起的完整过渡日期** | 成功路径：**eCFR 需 `-L` 跟随 302 + 完整 UA + 本地代理**（`curl` 直连会拿到 302/空响应）；EUR-Lex 走 CELLAR；`fda.gov` 全站 Akamai | **大幅降低**。§10.1/§10.2/§10.2b/§10.3 现有完整法源链。**剩余缺口很小**，其中仅 Art. 12(2) 日期为需补的细节（见 G8b） |"
))

# ---------- 5. G8b new row after G8 ----------
g8b = (u"| **G8b** | **吸奶器 milk-contact 部件是否适用 Reg (EC) 1935/2004 与 (EU) 2024/3190（适用范围未决）** | 逐字核对 1935/2004 Art. 1(2)（三条适用判据）与 Art. 1(3)（**仅 3 项排除，无医疗器械排除**）；确认 2024/3190 全文 **0 次**提及 `medical device` / `2017/745` / `MDR`；检索欧委会 FCM 指南与 MDCG 文件 | **无主管机关明确表述**。1935/2004 与 MDR 2017/745 的边界文件未涵盖吸奶器/储奶容器 | **高（本次新增的最高优先项之一）**。储奶容器在正常使用中**必然接触母乳**，且通常以「可储奶」宣传，落在 Art. 1(2)(c)；但产品整体受 MDR 管辖。**两种解读都会导致不同的合规义务**：若适用，则需 BPA 合规 + **Art. 8 合规声明（Annex III）**。**这不是文案问题，是产品合规问题。** 建议：向代工厂索取材质声明 + 法律团队出具意见。见 §10.2b |\n")
subs.append((
u"| **G9** | **ISO 13485 / ISO 9001 / IEC 60601-1 / ISO 10079-1 的官方适用范围文本**",
g8b + u"| **G9** | **ISO 13485 / ISO 9001 / IEC 60601-1 / ISO 10079-1 的官方适用范围文本**"
))

# ---------- 6. G17 rewrite ----------
subs.append((
u"| **G17** | **FDA 对 BPA 的官方立场原文** | 未成功获取 | `fda.gov` Akamai 拦截 | **中**。§10.2 因此只能给出\"美国没有普遍强制要求\"的结论，无法引用 FDA 的原始措辞 |",
u"| **G17** | ~~**FDA 对 BPA 的官方立场原文**~~ —— **实质已解决**（引文类型已替换） | `fda.gov` 正文页对 `curl`/`web_fetch` 均返回 **Akamai 拦截**；但 FDA 的**规则文本**与其**公告引用**改由 **eCFR（21 CFR 177.1580(d)）** 与 **Federal Register（77 FR 41899 / 78 FR 41840）** 取得 | **已绕开**。`fda.gov` 的 sitemap.xml **不受 Akamai 拦截**，可用于定位迁移后的页面 | **已关闭（部分）**。§10.2 现在引用的是**规则文本与 FR 公告**，比引用 FDA 网站文案更强。**仍缺**：FDA BPA 科普页原文与「FDA 不签发注册证书」页原文（后者在 §3.4 已通过二手转述引用，若要逐字仍需补） |"
))

# ---------- 7. P1 priority line ----------
subs.append((
u"| **P1** | 补齐 **材料类法规原文**（21 CFR 177.2600、Reg (EU) 2024/3190、Reg (EC) 1935/2004 Art. 3、LFGB §31） | 调研 | 决定 `BPA-free` / `food-grade silicone` 能否进安全词表。见 §12 G8 |",
u"| **P1** | **裁决吸奶器 milk-contact 部件是否适用 Reg (EC) 1935/2004 / (EU) 2024/3190** | 法律 | **新增最高优先项。** 决定欧盟站储奶容器是否需要 BPA 合规与 Art. 8 合规声明 —— 是产品合规而非文案问题。见 **§10.2b / §12 G8b** |\n"
u"| ~~P1~~ | ~~补齐材料类法规原文~~ —— **已完成**（177.2600 / 177.1580(d) / 2024/3190 / 1935/2004 Art. 3 / LFGB §30·§31 全部取得） | 调研 | 见 §12 G8 |"
))

# ---------- 8. closing summary item 7 ----------
subs.append((
u"7. **G8（部分）** —— **FDA BPA 立场原文、Reg (EU) 2018/213、Reg (EU) 2024/3190、Reg (EC) 1935/2004 Art. 3 未取得**（21 CFR 177.2600 与 LFGB §30/§31 已取得）。",
u"7. **G8 —— 基本关闭** —— **Reg (EU) 2024/3190、Reg (EC) 1935/2004 Art. 3、21 CFR 177.1580(d) 均已取得**；并纠正一处：**2018/213 已被 2024/3190 Art. 13 废止，不得再作为现行依据引用**。**新开 G8b（高优先）**：吸奶器 milk-contact 部件是否适用 1935/2004 / 2024/3190 的**适用范围未决** —— 见 §10.2b。"
))

for a, b in subs:
    if a.endswith('_MARKER\n'):
        continue
    n = s.count(a)
    if n != 1:
        sys.stderr.write("MISMATCH count=%d for: %s\n" % (n, a[:90])); sys.exit(1)
    s = s.replace(a, b)

io.open(p, 'w', encoding='utf-8').write(s)
print("ok")
