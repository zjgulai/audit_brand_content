#!/usr/bin/env python3
"""
kb_gaps.py —— 需求知识库的**缺口登记表**（`research/kb/缺口-v1.json`）

## 为什么存在

本轮（B3.0）在验收器里抓到一条**恒真检查**：

    c.add("KB-CHK-2", "缺口显式声明", True, ...)      # ← 输入里根本没有变量

它的本意是「声明出来就不是欺骗，静默略过才是」—— 这个立场是对的，但写法让它
**永远绿**：无论有没有缺口、缺口有没有落点，都是 PASS。于是 ADR-0013 §二 给
B2 定的 Done 条件「**10 条黄金问题全部可答**」在 `KB-Q-7` 明确打印
「❌ GAP：无法回答」的情况下被判为达成 —— 判据被自己的恒真绕过去了。

而 `KB-Q-7` 那句「→ 已登记为对源系统的数据需求：状态变更需留痕」里，
**「已登记」当时没有任何落点**：全仓只有两处散文（`查询手册.md` 与
`README.md`）和 `README` 表格里的一行字。这是本项目反复出现的老病
——「声明了没实现」—— 换了个更体面的说法。

## 这张表干什么

把 kb 线上**所有**缺口收进一处、编上号、写明「影响哪条黄金问题」「量是多少」
「谁去要」「怎么复算」。于是：

  · `KB-Q-7` 的 GAP 声明不再是散文，而是**从本表读出来的**（表里没有这一条，
    它就打印「未登记」），检查随之变红；
  · 每个缺口的量都有一个**可重算的键**，键对不上就红；
  · 算不出来的量必须显式写 `量_unrecomputable` —— 不许悄悄留一个没人能核的数。

用法：
  python3 tools/kb_gaps.py            # 重算并写回 缺口-v1.json
  python3 tools/kb_gaps.py --check     # 只比对，不改盘
"""

import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "research", "kb"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import load        # noqa: E402
import kb_facts    # noqa: E402

OUT = os.path.join(load.KB, "缺口-v1.json")

NOTE = [
    "★ 本表是 kb 线**全部缺口**的登记处。任何一处 GAP 结论都必须在这里有编号，",
    "  且 `量` 里的每个键都要能在 `tools/kb_facts.py` 重算出来 —— 键对不上即红。",
    "★ 缺口分五类：data（要源系统给）/ access（要权限）/ classification（口径未定）",
    "  / evidence（本地缺证据）/ schema（表结构本身缺内容）。",
    "★ 「量」算不出来时必须写 `量_unrecomputable` 说明为什么 —— 不许留一个",
    "  没人能核的数字。这是本表唯一一条自我约束：**数字要么可重算，要么说清为何不可**。",
    "★ 检查：`python3 tools/verify_kb.py`（E1/E2 两条）。",
    "★ 编号前缀（D37）：本表条目一律 `KB-GAP-#`，`affects` 里的黄金问题一律 `KB-Q-#`。",
    "  全仓**裸写的 `D#`/`Q#` 只表示台账编号** —— 本表自身的编号裸写即撞车，由 E6 守。",
]

# ── D37：kb 线自有编号加前缀，旧编号作为别名保留 ────────────────────────
#   ★ 这一段必须写在**生成器里**，不能只手写在制品上：`main()` 会整份重写
#     `缺口-v1.json`，只手写会被下一次重算冲掉 —— 而「别名被冲掉」这件事
#     不会有任何检查报红（E5 只比对制品与重算是否一致，一致地丢掉别名也算一致）。
RENAMED_FROM = {
    "★": "D37 把 kb 线自有编号从裸 `D#` 改名为 `KB-GAP-#`（理由见 legal-decisions-v1.json · D37）。",
    "为什么保留别名": "本仓已有大量散文按 `〔缺口:D#〕` 指认缺口；删掉别名等于把一次编号迁移"
                "变成一批悬空引用。旧→新的对照写在制品里，不写在人的记忆里。",
    "★ 注意": "裸 `D3` 在本仓**另外**还是台账决定「4 个走错通道的词迁入白名单表」—— "
            "别名只在**本表范围内**成立，跨文件引用一律用 `KB-GAP-#`。",
    **{f"D{i}": f"KB-GAP-{i}" for i in range(1, 17)},
}


def start_like_fields(snap):
    """列出需求类表里名字带「开始/启动」的字段 —— 「卡住多久」够不够算，取决于它们。"""
    out = []
    for t in sorted(snap.ledger_tables(), key=lambda x: (x.system, x.name)):
        for f in (t.fields or []):
            if any(k in str(f) for k in ("开始", "启动")):
                out.append({"表": f"{t.system}/{t.name}", "字段": str(f)})
    return out


def build(facts=None, snap=None):
    if snap is None:
        snap = load.snapshot()
    if facts is None:
        facts = kb_facts.compute(snap)
    startf = start_like_fields(snap)

    gaps = [
        {
            "id": "KB-GAP-1", "kind": "data",
            "title": "源系统没有状态变更时间戳",
            "why": "只有「当前状态」，没有「何时变成这个状态」。没有历史就算不出"
                   "停留时长；用「提交日期至今」代替会把「一直没开始」和"
                   "「做到一半停住」混为一谈。",
            "affects": ["KB-Q-7"],
            "量": {"in_flight": facts["in_flight"]},
            "量说明": "在跑的条数 —— 就是这个数上「卡了多久」不可算",
            "owner": "源系统负责人（creative=Roxie / seo=Rikka）",
            "status": "待提出",
            "提出方式": "向源系统加一个「状态变更时间」字段或开启状态变更留痕",
            "复算": "python3 tools/kb_query.py 7",
        },
        {
            "id": "KB-GAP-2", "kind": "data",
            "title": "四个疑似「开始时间」字段的语义未确认",
            "why": "KB-Q-7 原先的理由是「源系统没有任何时间字段」，实测不准确：需求类表里"
                   "有四个名字带「开始」的字段，且在跑记录里填得不少（seo 48/48、"
                   "创意支持 22/41）。但它们各自是**实际开始**还是**计划开始**未确认"
                   "（【平面】那张表干脆叫「计划开始时间」）。语义未确认 → 不得用于计算"
                   "停留时长，否则会把「排期没到」算成「卡住了」。",
            "affects": ["KB-Q-7"],
            "量": {"start_like_fields": len(startf)},
            "量说明": "需求类表中名字带「开始/启动」的字段个数",
            "明细": startf,
            "owner": "源系统负责人（creative=Roxie / seo=Rikka）",
            "status": "待提出",
            "提出方式": "逐字段确认语义（实际/计划、填写时机），确认前该字段不得进判据",
            "复算": "python3 tools/kb_query.py 7",
        },
        {
            "id": "KB-GAP-3", "kind": "access",
            "title": "材料收集表大部分读不到",
            "why": "材料表只记「链接」，不记「这条链接我到底读不读得到」。于是"
                   "「收集了 15 条」是错觉：读得到的是少数。",
            "affects": ["KB-Q-10"],
            "量": {"materials_unreadable": facts["materials_unreadable"],
                  "materials_total": facts["materials_total"]},
            "owner": "Roxie、Rikka、Misty、Emma",
            "status": "待补授权或重取链接",
            "复算": "python3 tools/kb_materials_lark.py（打印实测可读性）",
        },
        {
            "id": "KB-GAP-4", "kind": "classification",
            "title": "品线字段取值未归一",
            "why": "PSEO 的「品类」字段里写的是「翼果未分类，后续文章已进行分类」"
                   "—— 把一句话写进了分类字段。未归一的取值无法参与任何品线口径的统计。",
            "affects": ["KB-Q-3", "KB-Q-8"],
            "量": {"demands_unmapped": facts["demands_unmapped"]},
            "owner": "SEO 侧（Rikka）",
            "status": "待确认口径",
            "复算": "python3 tools/kb_evidence.py（缺口表 §三）",
        },
        {
            "id": "KB-GAP-5", "kind": "schema",
            "title": "三张空壳表：有表无内容",
            "why": "【红人&社媒】支持 / 优质素材-语言拓展 / 产品x品线资料整理 三张表"
                   "存在但无可用内容。空壳表会被当成「已覆盖的领域」。",
            "affects": [],
            "量": {"empty_tables": facts["empty_tables"]},
            "owner": "creative 侧（Roxie）",
            "status": "待定：补内容或明确废弃",
            "复算": "python3 -c \"import sys;sys.path.insert(0,'research/kb');"
                    "import load;[print(t.name) for t in load.snapshot().all() if t.kind=='empty']\"",
        },
        {
            "id": "KB-GAP-6", "kind": "evidence",
            "title": "七个品线族零证据",
            "why": "本地全部合规证据只覆盖吸奶器一个品线；其余品线的需求拿不到"
                   "任何本地判定依据。",
            "affects": ["KB-Q-8"],
            "量": {"demands_without_evidence": facts["demands_without_evidence"],
                  "lines_with_evidence": facts["lines_with_evidence"]},
            "owner": "品牌 / 法务 / 各品线负责人",
            "status": "待收集",
            "复算": "python3 tools/kb_query.py 8",
            # ── 外部承诺（2026-09-21 登记）───────────────────────────────
            # ★ 为什么要单独一个字段：这条缺口**已经有人在关它了**，而那件事
            #   此前只写在一篇飞书文档的「周进展」里，本项目侧零记录 ——
            #   也就是说，承诺方到期没交付，我们这边没有任何东西会响。
            #   `due` 是这条记录唯一的执行点：见 main() 的「承诺到期」段。
            "承诺": {
                "by": "上游（项目统筹 李倩怡 Dora）",
                "what": "「规则库：目前仅吸奶器的规则库相对齐全。其它已跟业务沟通"
                        "接下来两周陆续整理提供。」",
                "due": "2026-10-02",
                "$due_basis": "原文只写「两周」，未给具体日期。周进展标注日为 0918，"
                              "0918 + 14 天 = 2026-10-02。**这个日期是本项目的换算，"
                              "不是上游承诺的原文** —— 逾期时先问「是不是我算错了」，"
                              "再问「是不是没交」。",
                "$source": "PRD/feishu/美国市场内容治理项目-一页纸计划书.md（§周进展 0918；"
                           "该 wiki 页最后编辑 2026-09-20 12:06）",
                "登记于": "2026-09-21",
                "$why_unrecorded_before": "该句写在一篇 09-20 才被改过的上游文档里，"
                                          "而项目侧最后一次改动是 09-18 16:29 —— "
                                          "两个时间对不上，所以此前没有记录不是遗漏，是没到过。",
            },
        },
        {
            "id": "KB-GAP-7", "kind": "evidence",
            "title": "内部正负样本库：有 186 条真数据，但无正例、27% 无分类、视频为 0",
            "why": "★ 2026-10-20 **换源并改判**。此前这条写「业务侧表里有 8 条记录，"
                   "其中 7 条备注写样例 —— 没有真实样本」，判据是本地那份 1.3 KB 的"
                   "`_evidence/正负样本.raw.txt`（5 条、抬头 returned=8）。"
                   "实测云端同表当时已有 **186 条**真实记录，`渠道/市场`、`审核人`、"
                   "`来源`、`提交时间` 四列 **186/186 非空**，时间跨度 2026-07-25 → 2026-10-21。"
                   "所以「没有真实样本」这句话是**读错了源**得出的，不是业务方没交。"
                   "缺陷因此换了形态而没有消失：① 全表 **0 条正例**（`分类` 字段的"
                   "「正例」选项从未被用过）——「PASS 误放率」因此无法测；"
                   "② **51 条（27%）`原因分类` 为空**，正文前缀全是「【审核问题】」，"
                   "不在 7 个枚举值里，疑为流程反馈混入内容样本；"
                   "③ `素材类型=图片` 却有 **55 条没有图片附件**；④ **视频样本 0 条**。"
                   "这些读数全部未经业务确认，本条登记为缺口，**不就地清洗**。",
            "affects": ["KB-Q-10"],
            "量": {"samples_on_disk": facts["samples_on_disk"],
                  "samples_marked_sample": facts["samples_marked_sample"],
                  "samples_header_returned": facts["samples_header_returned"],
                  "samples_unclassified": facts["samples_unclassified"]},
            "量说明": "★ 2026-10-20 换源后的四个数：快照里的记录数 / 其中备注写「样例」的 / "
                     "应用身份可见总数 / 原因分类为空的。"
                     "**第一与第三个应当相等**（同一次拉取），不等才是真问题；"
                     "第四个是本轮新暴露、且第一次能被算出来的质量缺口。"
                     "在此之前这里并排的是「盘上 5 / 样例 5 / 抬头 8」——"
                     "那三个数只证明了本地在读一份旧 dump，与样本库的真实规模无关。",
            "owner": "品牌张丽敏、吸奶器银舒涵、喂养 William、法务",
            "status": "有数据待治理：补正例、分类 51 条空值、核实 55 条无图、补视频样本",
            "复算": "python3 tools/kb_classes.py（打印记录数与四项链质量读数）",
        },
        {
            "id": "KB-GAP-8", "kind": "evidence",
            "title": "外部标准库有 62 条条款级条目，但 0 条经法务确认",
            "why": "B3.0 时这条写的是「没有条款级条目」。2026-09-17 制品落盘"
                   "（research/kb/外部标准库-v1.json，17 来源 / 62 条），"
                   "缺口因此**换了形态而没有消失**：条目有了，但全部 status=research、"
                   "authority.ratifier 仍为 null —— 研究稿仍不能被当成判定依据。"
                   "★ 量从 0 变成 62 是这条缺口第一次能被算出来。",
            "affects": ["KB-Q-10", "F3"],
            "量": {"ext_entries": facts["ext_entries"],
                  "ext_ratified": facts["ext_ratified"]},
            "量说明": "已入册的条款级条目数 / 其中经法务确认的 —— 62 与 0 并排，"
                     "就是「有材料」与「能引用」之间的距离",
            "owner": "法务 Sharon、专家 Emma、北美待定",
            "status": "待法务逐条确认（建议顺序：14 条空白 + 6 条高价值）",
            "复算": "python3 tools/verify_external.py --offline",
        },
        {
            "id": "KB-GAP-9", "kind": "process",
            "title": "源表 `合规·绿` 一列扛三个正交量：157 条里 0 条是「已查且通过」",
            "why": "B3.4 演练先看到的是「59 条无文案被标绿」。执行 KB-GAP-9 时把**全部 157 条"
                   "绿标**逐行重跑引擎，洞比原来大一档：55 条无文案 + 99 条**规则库"
                   "够不着**（引擎落 catch_all）+ 3 条**引擎命中了、源表没有**"
                   "（2026-09-17 经 KB-GAP-15 逐行对账：**是我们迁移翻了语义**，"
                   "源表那一次的放行是对的），"
                   "而「已查且通过」是 **0 条**。这不是新提法 —— 设计文档 §4.5/§5.1 早已"
                   "认定语义重载，R2 §2989 甚至写了「这个数字无法被还原」。**现在还原了。**"
                   "再叠加两条实证：`检查人` 列 0/291 从未有人填写；`命中规则` 非空 132 条"
                   "恰好等于红 91+黄 30+灰 11，非空为空 159 条恰好等于绿 157+空 2，"
                   "**无一例外** —— 即 `合规·绿` 不是结论，是「规则没命中」这个默认值的"
                   "显示名（见 KB-GAP-15）。代价是一个字段扛三个量使两个数**在数学上算不出来**："
                   "盲区率 43.1%、未审率 53.9%。逐行还原账与给投放侧的变更请求已交付。",
            "affects": ["KB-Q-1", "KB-Q-6"],
            "量": {"risk_green": facts["risk_green"],
                  "risk_green_spend_usd": facts["risk_green_spend_usd"],
                  "risk_green_no_text": facts["risk_green_no_text"],
                  "risk_green_uncovered": facts["risk_green_uncovered"],
                  "risk_green_uncovered_spend_usd": facts["risk_green_uncovered_spend_usd"],
                  "ads_unread": facts["ads_unread"],
                  "ads_total_spend_usd": facts["ads_total_spend_usd"],
                  "risk_blind_spot_rate": facts["risk_blind_spot_rate"]},
            "量说明": "绿标条数 / 它们的投放金额 / 其中无文案 / 其中规则未覆盖 / "
                     "未覆盖那批的金额 / 整行没读到的（不是无文案广告）/ 全表投放 / "
                     "盲区率 —— 八个数并排。**「已查且通过」那一格没有键，因为它恒为 0**，"
                     "由 audit_risk_label.py 直接印出来。",
            "owner": "广告投放侧（creative=Roxie）+ 源表口径",
            "status": "已交付变更请求（三轴拆列 + 291 行迁移表），待投放侧回："
                      "research/governance/源表口径-风险等级-变更请求.md",
            "提出方式": "把 `风险等级` 拆成 `可审内容`（有/无/未读到）· `覆盖状态`"
                        "（覆盖/未覆盖/不适用）· `风险等级`（L1–L4）三列；"
                        "`待复核·灰` 移出等级改记 `复核状态`。"
                        "★ 不要「无文案记录留空」—— 空值在这张表里已经有主（那 2 行没读到的）",
            "复算": "python3 research/governance/audit_risk_label.py --check",
            "$report": "research/governance/端到端送审-演练报告.md §三/§三·补；"
                       "research/governance/源表口径-风险等级-变更请求.md",
        },
        {
            "id": "KB-GAP-10", "kind": "evidence",
            "title": "Meta 政策页在本机无匿名取法，只能对 09-15 的钉住件核",
            "why": "transparency.meta.com 是纯客户端 SPA，正文经 /api/graphql/ 拉取。"
                   "实测八条路全部只得到标题与 JS bundle：朴素 UA、浏览器 UA、无斜杠、"
                   "?_fb_noscript=1、en-gb、?print=1、amp、Firecrawl 渲染、浏览器桥"
                   "（未连接）。今天六条能核上，靠的是仓内 _evidence/R1 与 R5 里 "
                   "2026-09-15 抓的证据件（URL 与引用来源一致）。"
                   "★ 这六条的可复核性上限 = 那一天。",
            "affects": ["F3", "KB-GAP-8"],
            "量": {"sources_meta": facts["sources_meta"],
                  "entries_meta": facts["entries_meta"]},
            "量说明": "Meta 来源数 / 其中条目数 —— 这两个数就是「只能靠钉住件」的暴露面",
            "owner": "证据侧",
            "status": "待定：接受「钉住件即证据上限」，还是需要一条能刷新 Meta 页的取法",
            "提出方式": "确认可接受钉住件，或提供代理/渲染取法",
            "复算": "python3 tools/verify_external.py --offline",
        },
        {
            "id": "KB-GAP-11", "kind": "evidence",
            "title": "TikTok 广告政策正文页取不到，库内只有品牌内容政策一条",
            "why": "TikTok Advertising Policies 正文由 cognition.byteoversea.com 拉取，"
                   "匿名请求 302 跳登录。故 S17 只有 Branded Content Policy"
                   "（tiktok.com/legal 可静态抓）四条。这是覆盖缺口，不是抓取失败。",
            "affects": ["F3", "KB-GAP-8"],
            "量": {"sources_tiktok": facts["sources_tiktok"],
                  "entries_tiktok": facts["entries_tiktok"]},
            "量说明": "TikTok 来源数 / 条目数 —— 与其他渠道相比明显偏薄",
            "owner": "证据侧",
            "status": "待确认：是否需要登录态或替代来源补齐 TikTok 广告政策",
            "提出方式": "提供可访问路径，或接受当前覆盖",
            "复算": "python3 tools/verify_external.py --only S17",
        },
        {
            "id": "KB-GAP-12", "kind": "evidence",
            "title": "EU 侧（MDR/EUR-Lex）抓不到，英国站只有 MHRA + CAP",
            "why": "eur-lex.europa.eu 返回 HTTP 202 + 空 body，本轮没有欧盟条目。"
                   "英国站的两条依据（MHRA 药品广告、CAP §12）都不覆盖医疗器械侧 ——"
                   "英国站的依据面比看上去窄。",
            "affects": ["F3", "KB-GAP-8"],
            "量": {"sources_eu": facts["sources_eu"],
                  "sources_uk": facts["sources_uk"]},
            "量说明": "欧盟来源数 / 英国来源数 —— 0 与 2 并排",
            "owner": "证据侧 + 法务",
            "status": "待确认：欧盟侧是否必须补（涉及英国站与欧盟站的合规判定）",
            "提出方式": "确认是否补 EU 来源",
            "复算": "python3 tools/verify_external.py --offline",
        },
        {
            "id": "KB-GAP-13", "kind": "legal",
            "title": "三条规则只能引 FTC 举证通则，无专门条款",
            "why": "T2.2.suction-claim（吸力）、T2.2.quiet-claim（噪音）、"
                   "T2.1.3.milk-flow（出奶速度）在公开政策里找不到专门条款，"
                   "只能挂到 EXT-039「客观宣称必须举证」。★ 通则能不能当依据，"
                   "是法务口径问题，不是研究问题。",
            "affects": ["F3"],
            "量": {"rules_only_general": facts["rules_only_general"],
                  "rules_total": facts["rules_total"]},
            "量说明": "只能引通则的规则数 / 真规则总数（真规则 = 规则键 - catch_all）",
            "owner": "法务 Sharon",
            "status": "待裁定：引通则是否够用，还是要为这三条另找依据或降级处理",
            "提出方式": "法务就「通则是否可作为规则依据」给一个口径",
            "复算": "python3 tools/kb_facts.py --check",
        },
        {
            "id": "KB-GAP-14", "kind": "legal",
            "title": "14 条空白条目 / 7 个候选规则族待法务确认",
            "why": "62 条里有 14 条的「关联规则」为空（= 我们规则库没有对应条目），"
                   "归成 7 个候选规则族。全部 status=research、ratifier=null。"
                   "★ 其中 EXT-016（素材中广告主身份）的归族由整合人判定，"
                   "研究者未在制品中落组 —— 这一条的分组是人的判断，不是来源的说法。",
            "affects": ["F3", "KB-GAP-8"],
            "量": {"entries_blank": facts["entries_blank"],
                  "families": facts["families"],
                  "entries_total": facts["entries_total"]},
            "量说明": "空白条目数 / 候选族数 / 条目总数 —— 14 条空白不是小数，"
                     "接近全库四分之一",
            "owner": "法务 Sharon + 产品/投放侧",
            "status": "待确认：按「14 条空白 + 6 条高价值」的顺序过，确认后 status 才可改 ratified",
            "提出方式": "法务逐条确认",
            "复算": "python3 tools/verify_kb.py",
        },
        {
            "id": "KB-GAP-15", "kind": "data",
            "title": "规则迁移不保真：旧规则的「豁免词」语义在迁移中消失 —— "
                     "36 个自我触发词里只剩 2 个还能放行",
            # ★ 本条已**改写**。立案时的表述是「源表的规则扫描漏放 3 条」——
            #   做完逐行对账后，那句话是错的，且错的方向是**指控了源表**。
            #   留这段注释是为了让「改口」这件事本身可审计。
            "why": "KB-GAP-9 逐行还原时掉出来 3 条绿标被引擎命中。当时的解释是「源表漏放」。"
                   "2026-09-17 做了两次扫描的逐行对账（`audit_migration_fidelity.py`），"
                   "结论反过来了：**源表是对的，错的是我们自己的迁移**。"
                   "证据链：① 旧规则 H01 的 `exceptions` 里有 `treat yourself`；"
                   "② 同批次 `Savannah-20260825` 天然对照证明旧 `exceptions` 的语义是"
                   "**放行**（i=265 含豁免词→源表 0 命中·绿；i=270/271 不含→命中 H07,U04·红，"
                   "同一次扫描）。"
                   "★ 结论用**实测**给出，不用任何分类字段：旧规则的 94 个豁免词里，"
                   "只有「自身就会命中本规则」的 36 个词，豁免才真正生效过。"
                   "把这 36 个词逐个喂给今天的引擎：**只剩 2 个还能放行**（`silent mode`/"
                   "`静音模式`，即 D3 法务定案的那次修正）——**13 个变成降级**、"
                   "**21 个的语义彻底消失**（词在守卫表里但 `已接线=False`，规则按满档 "
                   "L4 auto_reject 判险）。21 个里 8 个是中文否定式（`不能治疗`/`并非治疗`…）、"
                   "7 个是英文否定式（`cannot treat`/`won't cure`…），"
                   "而同义的 `not intended to treat` 却是降级 —— **同一个意思，语种不同、结局不同**。"
                   "另：这条的立案稿曾写「28 个非免责类被翻成降级，其中甲类 14 个应改回放行」，"
                   "该分类已撤回 —— 它建立在 `guard_type`（机器推导、自带「待法务确认」标注）"
                   "这个启发式上，且把源表写明的三层设计（放行 / 走 M07 审慎 / 判险）压成了两层。"
                   "撤回记录保留在脚本里，见 `audit_migration_fidelity.py` 轴 1b 段。",
            "affects": ["KB-Q-1", "KB-Q-6"],
            "量": {
                "legacy_exception_words": facts["legacy_exception_words"],
                "exception_self_triggering": facts["exception_self_triggering"],
                "exception_still_pass": facts["exception_still_pass"],
                "exception_now_downgrade": facts["exception_now_downgrade"],
                "exception_full_severity": facts["exception_full_severity"],
                "regression_false_positives": facts["regression_false_positives"],
                "scan_drift_records": facts["scan_drift_records"],
                "scan_pairs_agree": facts["scan_pairs_agree"],
                "orphan_keywords": facts["orphan_keywords"],
            },
            "量说明": "旧豁免词总数 / 其中豁免真正生效过的（自身会命中本规则）/ "
                      "**今天仍能放行的** / **变成降级的** / **语义彻底消失、按满档判险的** / "
                      "本语料上已翻掉的记录数（假阳性）/ 两次扫描有分歧的记录数 / "
                      "两次扫描一致的记录数 / 新规则里彻底没有家的旧关键词数。"
                      "★ 三个桶必须满足 2+13+21=36，守恒成门（V45c）。"
                      "★ 已发生的那一格是 3：21 是**暴露面**，3 是**这份语料上真的错了的**。"
                      "两个数都要写，只写一个都会误导。",
            "owner": "审核侧（规则维护，谁迁的谁修）；不需要投放侧动手",
            "status": "待修，两件事："
                      "① **21 个未接线**的否定式豁免词（免责声明今天会被 L4 自动拒绝）"
                      "——先决定接线与否，中文 8 个优先；"
                      "② **13 个已接线但通道从放行变降级**的，逐词定性"
                      "（`treat yourself` 是词义消歧、不是主张 → 应放行；"
                      "其余否定式属免责声明，维持降级亦可辩护 → 交法务）",
            "提出方式": "把旧规则集的 94 个豁免词与新系统的两张词表逐词对账，"
                        "并用同批次对照实测旧语义 —— 不靠回忆，靠重跑",
            "复算": "python3 research/governance/audit_migration_fidelity.py --check",
            "$report": "research/governance/skeleton/_data/迁移保真度.json",
        },
        {
            "id": "KB-GAP-16", "kind": "data",
            "title": "源表扫描看到的文案，我们没采到：13 个命中片段在今天的语料里搜不到",
            "why": "源表有一列 `命中片段`，记的是**它当时到底命中了什么字符串**，"
                   "132 条记录、270 个片段。拿它逐条回今天的语料里搜，"
                   "**13 个搜不到**（4.8%），涉及 6 条记录 —— 例如 i=48 源表自报命中"
                   "`whisper` / `hospital` / `hospital-grade` / `maximum suction`，"
                   "而这四个串在 `Primary Text` 里一个都没有。"
                   "★ 这不是规则差异，是**输入差异**：源表扫描看到的广告资产"
                   "（RSA 的多个标题/描述、附加信息）比我们存下来的多。"
                   "两者必须分开，否则「去修采集」会被记成「去改规则」—— "
                   "这正是 KB-GAP-9 那类合并计数病的同一形状。"
                   "`EMPTY` / `<文案为空` 是源表给「整行没读到」留的哨兵值，已排除。",
            "affects": ["KB-Q-1", "KB-Q-6"],
            "量": {
                "src_fragments_total": facts["src_fragments_total"],
                "src_fragments_not_in_corpus": facts["src_fragments_not_in_corpus"],
                "src_fragments_missing_records": facts["src_fragments_missing_records"],
            },
            "量说明": "源表自报片段总数 / 今天的语料里搜不到的 / 涉及记录数。"
                      "★ 这条的分母是**源表自己留下的证据**，不是我们的估计 —— "
                      "所以它不需要抽样就能算。",
            "owner": "数据采集侧（把广告资产采全，至少 RSA 的全部标题与描述）",
            "status": "待确认：采集口径覆盖到哪一层资产；确认前不得假定"
                      "「引擎没命中 = 这条干净」",
            "提出方式": "拿源表 `命中片段` 逐串回搜今天的语料 —— 源表早就把证据留下了，"
                        "此前没有人用它",
            "复算": "python3 research/governance/audit_migration_fidelity.py --check",
            "$report": "research/governance/skeleton/_data/迁移保真度.json 轴 4",
        },

        # ── B3.5（2026-09-17）：外部标准库落盘时暴露的五个缺口 ──
        #   前三条是**取证面**的：不是没做，是本机没有可复现的取法；
        #   后两条是**法务面**的：材料在，口径没定。

        # ── 2026-10-20 委托方指出后当场量化：样本表的两个结构性缺陷 ──
        #   这两条与 KB-GAP-7 不是一件事：GAP-7 讲「有没有数据」，
        #   GAP-17/18 讲「有的这些数据能不能当判据用」。合并会让两种修法
        #   （补样本 vs 改采集）被记成同一个数。
        {
            "id": "KB-GAP-17", "kind": "data",
            "title": "样本表的图片与判定理由无法对应：344 个附件全是占位名",
            "why": "委托方 2026-10-20 指出「很多『图片素材』和『具体原因/分析』无法对应」。"
                   "量化后成因比「写得不清楚」更硬：**344 个附件文件名 100% 是 "
                   "`sN_N.png`**（`s0_0`…`s2_4`，前缀即记录序号）。"
                   "★ **归因已核实（2026-10-20）**：这些名字是**飞书 API 原样返回的**，"
                   "不是本地采集脚本改的 —— 直接调 `bitable/v1/.../records` 得到的就是这组名。"
                   "所以重命名发生在**导入多维表之前**，改我们的采集代码无效，"
                   "必须问业务方原始图还在不在。"
                   "第二层证据：**127/186 条的附件数与 `原文反馈` 里的 `!Image` 标记数不等**"
                   "（59 条相等）—— 贴进群里的图和存下来的图都不是同一组。"
                   "第三层：想从正文恢复图序也走不通 —— 129 条带图记录里，"
                   "「编号条目数 = 附件数 = `!Image` 数」三者同时成立的**只有 3 条**"
                   "（116 条正文无编号、54 条 `!Image` 数与附件数相符、仅 6 条编号数相符）。",
            "affects": ["KB-Q-10"],
            "量": {
                "samples_attachments": facts["samples_attachments"],
                "samples_att_renamed": facts["samples_att_renamed"],
                "samples_att_count_mismatch": facts["samples_att_count_mismatch"],
            },
            "量说明": "附件总数 / 其中文件名是占位式的 / 附件数与原文 `!Image` 标记数不等的记录数。"
                      "★ 第一个与第二个相等 → 100% 重命名，不是偶发；"
                      "第三个是本条真正的痛处：图与原文已经对不上。",
            "owner": "业务侧（样本表导入环节：原始文件名与图片顺序是否还能取回）",
            "status": "待确认：**改我们的代码无效**（名字来自飞书返回）；须问导入方原始图是否仍在",
            "提出方式": "先问采集脚本能否不重命名落盘；再问业务侧群里原图是否仍可取",
            "复算": "python3 tools/kb_facts.py --check（读 samples_att_* 三项）",
        },
        {
            "id": "KB-GAP-18", "kind": "data",
            "title": "样本理由列混入聊天转录：81% 的记录里同时有 @人、寒暄与贴图标记",
            "why": "委托方 2026-10-20 指出「『具体原因/分析』里有很多噪音文本」。"
                   "这不是零星的错别字，而是**这一列存的是整段群聊**："
                   "**151/186（81.2%）**的记录至少命中一个聊天特征，"
                   "**123/186（66.1%）命中两个以上**。逐项："
                   "`@某人` 131 条（70.4%）、寒暄/催促（麻烦看看/辛苦/姐姐/收到）115 条（61.8%）、"
                   "粘贴的聊天标记（`[图片]` / `!Image` / `【项目方` / `【初审`）108 条（58.1%）、"
                   "`【审核问题】` 前缀 51 条（27.4%）。"
                   "正文长度 p50 只有 **165 字**，其中真正的判定理由被夹在对话里。"
                   "★ 后果有两层：① 直接拿这一列做 gold，模型学到的是「读群聊」"
                   "而不是「判内容」；② 它与 KB-GAP-7 的「51 条原因为空」**同源** ——"
                   "那 51 条的正文只有 `【审核问题】` 开头的一段对话，"
                   "分类信息从来没被写进结构化字段。",
            "affects": ["KB-Q-10"],
            "量": {
                "samples_noise_any": facts["samples_noise_any"],
                "samples_noise_heavy": facts["samples_noise_heavy"],
                "samples_unclassified": facts["samples_unclassified"],
            },
            "量说明": "至少命中一个聊天特征的记录数 / 命中两个以上的 / 原因分类为空的。"
                      "★ 这三个数一起看才有意义：噪声高的记录里，"
                      "结构化字段（原因分类）往往也是空的 —— 同一段对话既没被拆成理由，"
                      "也没被归类。",
            "owner": "业务侧（样本录入口径）+ 数据侧（能否从 `原文反馈` 重抽结构化理由）",
            "status": "待定口径：什么算「一条可用的判定理由」；确认前不得把该列当 gold",
            "提出方式": "拿 `原文反馈` 里的【X】前缀 + 问题要点重抽一版，与现有列比对",
            "复算": "python3 tools/kb_facts.py --check（读 samples_noise_* 与 samples_unclassified）",
        },
        {
            "id": "KB-GAP-19", "kind": "data",
            "title": "样本表不是判例库，是设计审核群的聊天转录：审核人字段记的是转发者",
            "why": "★ 2026-10-20 挖深后的发现，比 KB-GAP-7/17/18 更靠根 —— "
                   "它决定这张表**到底是什么**。两个硬读数："
                   "① **`审核人` 字段 186/186 等于 `来源` 里的发言人**，"
                   "也就是**把内容转进群的人**；而正文 `【终审-@X】` 里真正被请去审的人"
                   "（被 `@` 最多的那位，159 次）**在 `审核人` 字段里 0 次出现**。"
                   "拿 `审核人` 字段去统计「谁审得多」会得到一个完全错的结论 —— "
                   "这正是 §2.4.1 那个病：两个同源字段并排，看着一致，其实恒真。"
                   "② `原文反馈` 的第一段 `【审核】` 里，**106/186 正文其实是送审请求**"
                   "（`【终审-@X】麻烦看看` + 一段需求简报），其中 **77 条完全不含任何"
                   "判定词**（建议/不对/去掉/用错…）—— 这些记录**根本没有审核结论**，"
                   "是「还没审」的半成品。"
                   "★ 合起来看：这张表是把设计审核群的聊天**按消息转录**进多维表，"
                   "不是「有人逐条做过内容审查判定」。真正可当审核意见的只有约 47 条。"
                   "对 Agent 训练素材而言，**可用量级是「几十条」，不是「186 条」**。",
            "affects": ["KB-Q-10"],
            "量": {
                "samples_reviewer_is_forwarder": facts["samples_reviewer_is_forwarder"],
                "samples_audit_is_request": facts["samples_audit_is_request"],
                "samples_request_no_verdict": facts["samples_request_no_verdict"],
            },
            "量说明": "审核人字段==来源发言人的条数 / 审核段正文实为送审请求的条数 / "
                      "送审请求里完全不含判定词的条数。"
                      "★ 第一个若 == 总数（186），说明 `审核人` 字段不承载「谁审的」这个信息；"
                      "第三个是「盘上有多少条根本没有审核结论」的下界。",
            "owner": "业务侧（样本表的录入/采集口径：到底想存聊天还是存判例）",
            "status": "待确认：这张表的定位（判例库 vs 聊天存档）；"
                      "在定位明确前，`审核人` 字段不得用于任何「审核人」语义的统计",
            "提出方式": "拿正文 `@` 到的真实审核人与 `审核人` 字段并排给业务方看，确认口径",
            "复算": "python3 tools/kb_facts.py --check（读 samples_reviewer_is_forwarder 等三项）",
        },
        {
            "id": "KB-GAP-20", "kind": "design",
            "title": "品牌一致性层：控制点为空、引擎规则为 0 —— 最高频的问题，零判据",
            "why": "★ 2026-10-20。品牌一致性是全项目**最高频**的问题类别"
                   "（讨论稿 33/98；样本表里 `原因分类=品牌一致性` **71/186** 也是最高）。"
                   "而它在判定链上**一处接入点都没有**，四个可重算的读数为证："
                   "① `control-points-v1.json` 的「品牌控制」族 **state=无控制点**"
                   "（20 个控制点里 0 个属品牌；4 个族全空，理由统一写「待产品+法务签署」）；"
                   "② `rules-v1.json` 26 条规则里 **0 条**是品牌规则"
                   "（全是医疗宣称/FDA/竞品/安全/紧迫感）；"
                   "③ 七轴里 BRAND 轴只有 **10 条**（638 条中的 1.6%），"
                   "且来源是 W-2 妈妈心理，与 Momcozy 资产包**零交集**；"
                   "④ 4 类知识库登记表里**没有「品牌」这一类**。"
                   "★ 后果：`PMO/守衡-创建全景图与知识库体系-讨论稿-v1.md:421` 写过"
                   "「品牌一致性是最常见问题 → 必须先有判据」，但至今没有对应执行点。"
                   "这是**缺判据**，不是缺样本（样本有 71 条，见 KB-GAP-7/19）。",
            "affects": ["KB-Q-10"],
            "量": {
                "brand_control_points": facts["brand_control_points"],
                "brand_control_empty_families": facts["brand_control_empty_families"],
                "brand_axis_rules": facts["brand_axis_rules"],
                "brand_engine_rules": facts["brand_engine_rules"],
            },
            "量说明": "品牌控制点数 / 空族数 / 七轴 BRAND 条数 / 引擎品牌规则数。"
                      "★ 前两个是 0 与 4，后两个是 10 与 0 —— "
                      "「有 10 条分类标签」与「有 0 条能拦的规则」是两件事，"
                      "并排放才看得出这一层是空的。",
            "owner": "产品 + 法务（控制点内容）+ 品牌侧（判据来源）",
            "status": "待定：品牌控制点内容未签署；引擎品牌规则 0 条",
            "提出方式": "先定「品牌一致性」的可判口径（从 71 条样本归纳），再落控制点与规则",
            "复算": "python3 tools/kb_facts.py --check（读 brand_* 四项）",
        },
        {
            "id": "KB-GAP-21", "kind": "data",
            "title": "Momcozy 资产包的禁用词是「提示词约束」，不能直接当发布内容检测规则",
            "why": "★ 2026-10-20 实测。`PMO/audit/momcozy-assets/rules/brand_semantic_library.md`"
                   "§1.3 的禁用词块抬头逐字写着「**绝对禁止出现在任何 Prompt 中的词**」——"
                   "它约束的是 **AIGC 生成提示词**，不是**已发布文案**。"
                   "而最直觉的做法（把这 20 个词直接做成 `rules-v1.json` 条目）"
                   "**被实测否掉**：拿 232 条真实广告文案试跑，"
                   "`perfect` 命中 **9.9%**、`must` **7.8%**、`hospital` **6.0%**、"
                   "`ideal` **5.6%** —— 语境全是正常营销语"
                   "（「Find Your Perfect Flow」「Must-Haves zum Stillen」「ideal for busy moms」）。"
                   "直接接进去，品牌规则一上线就会被当噪声关掉。"
                   "★ 另有一层口径错位：20 个词里 **17 个在引擎里完全不存在**，"
                   "3 个（clinical/hospital/perfect）只作别的规则子串，且属医疗合规语境。"
                   "所以「品牌禁用词与引擎零交集」这句话，"
                   "**不是引擎漏了品牌，是两者量的不是同一件事**。",
            "affects": ["KB-Q-10"],
            "量": {"brand_engine_rules": facts["brand_engine_rules"]},
            "量说明": "引擎里的品牌规则数（0）。"
                      "★ 这条的意义不在这个数，在**它证明「补词表」这条路走不通**："
                      "词表属于生成期，判定属于发布期，混用会产生 >5% 的误报。",
            "owner": "品牌侧（区分「生成期内规」与「发布期判据」）+ 产品",
            "status": "已定性：资产包 = AIGC 生成期内规；**不得**直接作为发布审查规则源",
            "提出方式": "品牌判据改从 71 条品牌一致性样本的审核意见归纳，不从禁用词来",
            "复算": "python3 tools/kb_facts.py --check（brand_engine_rules）+ 本文 §1.3 原文",
        },
        {
            "id": "KB-GAP-22", "kind": "evidence",
            "title": "品牌视觉一致性检查器是概念代码，且 58 张风格锚定图目录不存在",
            "why": "★ 2026-10-20。两件事同属「视觉一致性」这一层，且都只在纸面上："
                   "① `brand_consistency_controls.md` 里有 14 个检查项，"
                   "但 `check_image()` 的函数体是 `pass`，文件自己标注为「**概念代码**」；"
                   "`sop.md` 把一致性检查列为 Step 4.1「自动检查（概念）」—— "
                   "「概念」二字决定了它没有任何执行点。"
                   "② `manifest.json` 声明 155 条资产且 `all_sha256_match: true`，"
                   "但 `sref-candidates/` 的 **58 张风格锚定图目录不存在**，"
                   "`python3 tools/verify_assets_baseline.py` 实测 **exit 1（58 条 A2 缺文件）**。"
                   "★ 而**没有任何一处引用它** —— 该 verifier 没被登记进 `AGENTS.md §2.1`"
                   "那张自证表，等于一个天天红的检查器没人看。"
                   "③ 色彩三处不一致（semantic 6 个 hex / design_tokens 6 个 / BRAND_CONFIG 4 色），"
                   "**没有一份被指定为权威**；禁用词三份清单（29 / 14 / 若干）互不相等。",
            "affects": ["KB-Q-10"],
            "量": {"brand_asset_files": facts["brand_asset_files"],
                  "brand_asset_files_missing": facts["brand_asset_files_missing"]},
            "量说明": "manifest 声明的资产数 / 盘上实际缺的文件数（当前 155 / 58，"
                      "缺的全是 `sref-candidates/`）。"
                      "★ 这个数原本只活在 `verify_assets_baseline.py` 的退出码里，"
                      "而该 verifier 没被登记进 AGENTS.md §2.1 的自证表 —— "
                      "红了也没人看。放进 kb_facts 后，E2 会顺带守住它。",
            "owner": "品牌侧（视觉 rubric 与色彩权威）+ 资产采集侧（sref 图补回或降级 manifest）",
            "status": "待确认：58 张锚定图能否补回；不能则须把 manifest 的 "
                      "`all_sha256_match` 降级并写明",
            "提出方式": "先补 verify_assets_baseline 进 §2.1 自证表，否则它红了也没人知道",
            "复算": "python3 tools/verify_assets_baseline.py",
        },
    ]
    return {
        "schema_version": "缺口-v1",
        "snapshot_id": facts["snapshot_id"],
        "basis_date": facts["basis_date"],
        "generated_by": "tools/kb_gaps.py",
        "$note": NOTE,
        "$renamed_from": RENAMED_FROM,
        "gaps": gaps,
    }


def _closed(gap):
    """缺口是否已关闭 —— 只看 status 的前缀，不猜语义。

    这里刻意**不**写"只要 status 不是『待』就算关闭"：那会让一个把 status 写成
    空字符串的条目静默变成"已关闭"，而"没填"和"做完了"必须长得不一样。
    """
    st = (gap.get("status") or "").strip()
    return st.startswith("已") or st.startswith("关闭") or bool((gap.get("承诺") or {}).get("完成于"))


def check_due(doc, today=None):
    """承诺到期检查 —— 本文件里「外部承诺」这条约束的**唯一执行点**。

    背景：KB-GAP-6 有一条 2026-09-21 才登记进来的外部承诺（上游「两周内」提供
    其余品线规则）。登记本身不产生任何约束力 —— 承诺方到期没交，得**有东西会响**。
    这个函数就是那个东西。

    退出码语义（三个码必须能分辨，`AGENTS.md` §2.4.1）：
        0 = 无逾期
        1 = 登记与重算不一致（漂移，见 main）
        2 = 有承诺逾期未交付
    """
    today = today or date.today()
    overdue = []
    for g in doc["gaps"]:
        c = g.get("承诺")
        if not c or not c.get("due") or _closed(g):
            continue
        try:
            due = date.fromisoformat(c["due"])
        except ValueError:
            print(f"❌ {g['id']} 的 承诺.due 不是 ISO 日期：{c['due']!r} —— "
                  f"无法比较，按逾期处理（不静默跳过）")
            overdue.append((g, None))
            continue
        if today > due:
            overdue.append((g, (today - due).days))

    if not overdue:
        n = sum(1 for g in doc["gaps"] if g.get("承诺") and not _closed(g))
        if n:
            print(f"⏳ 在途外部承诺 {n} 条，均未到期")
        return 0

    print("─" * 72)
    print("⏰ 外部承诺逾期 —— 这不是登记不一致，是**有人欠着东西**")
    for g, days in overdue:
        c = g["承诺"]
        age = f"逾期 {days} 天" if days is not None else "**due 无法解析**"
        print(f"   {g['id']} · {g['title']}")
        print(f"     承诺方 : {c.get('by')}")
        print(f"     到期   : {c.get('due')}（{age}）")
        print(f"     原文   : {c.get('what')}")
        print(f"     依据   : {c.get('$due_basis', '（未写换算依据）')}")
        print(f"     来源   : {c.get('$source')}")
        print(f"   → 动作：**先去问承诺方，不要直接把它记成延误** —— "
              f"上面的到期日若是本项目换算出来的，第一个要核的是换算本身。")
    print("─" * 72)
    return 2


def main():
    check = "--check" in sys.argv
    doc = build()
    new = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else None
    drift = new != old
    if drift and check:
        print("❌ 缺口登记与重算不一致 —— 修复：python3 tools/kb_gaps.py")
    elif drift:
        open(OUT, "w", encoding="utf-8").write(new)
        print(f"✅ 已写回 {os.path.relpath(OUT, load.REPO)}：{len(doc['gaps'])} 条缺口")
        for g in doc["gaps"]:
            q = ("量=" + json.dumps(g["量"], ensure_ascii=False)) if "量" in g \
                else "量=不可重算"
            print(f"   {g['id']:<3}{g['kind']:<15}{g['title'][:26]:<28}{q}")
    else:
        print(f"✅ 缺口登记与重算一致：{len(doc['gaps'])} 条"
              f"（{'/'.join(g['id'] for g in doc['gaps'])}）")

    # 承诺到期检查**独立于漂移检查**：两件事必须能被分开报，
    # 否则「有人欠交付」会被读成「脚本要我重跑一遍」。
    due = check_due(doc)
    if drift and check:
        if due:
            print("（本次同时存在两种状态：退出码取 1=登记漂移；上述逾期内容已单独打印，未被吞掉）")
        return 1
    return due


if __name__ == "__main__":
    sys.exit(main())
