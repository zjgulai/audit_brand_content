#!/usr/bin/env python3
"""
kb_gaps.py —— 需求知识库的**缺口登记表**（`research/kb/缺口-v1.json`）

## 为什么存在

本轮（B3.0）在验收器里抓到一条**恒真检查**：

    c.add("D2", "缺口显式声明", True, ...)      # ← 输入里根本没有变量

它的本意是「声明出来就不是欺骗，静默略过才是」—— 这个立场是对的，但写法让它
**永远绿**：无论有没有缺口、缺口有没有落点，都是 PASS。于是 ADR-0013 §二 给
B2 定的 Done 条件「**10 条黄金问题全部可答**」在 `Q7` 明确打印
「❌ GAP：无法回答」的情况下被判为达成 —— 判据被自己的恒真绕过去了。

而 `Q7` 那句「→ 已登记为对源系统的数据需求：状态变更需留痕」里，
**「已登记」当时没有任何落点**：全仓只有两处散文（`查询手册.md` 与
`README.md`）和 `README` 表格里的一行字。这是本项目反复出现的老病
——「声明了没实现」—— 换了个更体面的说法。

## 这张表干什么

把 kb 线上**所有**缺口收进一处、编上号、写明「影响哪条黄金问题」「量是多少」
「谁去要」「怎么复算」。于是：

  · `Q7` 的 GAP 声明不再是散文，而是**从本表读出来的**（表里没有这一条，
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
]


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
            "id": "D1", "kind": "data",
            "title": "源系统没有状态变更时间戳",
            "why": "只有「当前状态」，没有「何时变成这个状态」。没有历史就算不出"
                   "停留时长；用「提交日期至今」代替会把「一直没开始」和"
                   "「做到一半停住」混为一谈。",
            "affects": ["Q7"],
            "量": {"in_flight": facts["in_flight"]},
            "量说明": "在跑的条数 —— 就是这个数上「卡了多久」不可算",
            "owner": "源系统负责人（creative=Roxie / seo=Rikka）",
            "status": "待提出",
            "提出方式": "向源系统加一个「状态变更时间」字段或开启状态变更留痕",
            "复算": "python3 tools/kb_query.py 7",
        },
        {
            "id": "D2", "kind": "data",
            "title": "四个疑似「开始时间」字段的语义未确认",
            "why": "Q7 原先的理由是「源系统没有任何时间字段」，实测不准确：需求类表里"
                   "有四个名字带「开始」的字段，且在跑记录里填得不少（seo 48/48、"
                   "创意支持 22/41）。但它们各自是**实际开始**还是**计划开始**未确认"
                   "（【平面】那张表干脆叫「计划开始时间」）。语义未确认 → 不得用于计算"
                   "停留时长，否则会把「排期没到」算成「卡住了」。",
            "affects": ["Q7"],
            "量": {"start_like_fields": len(startf)},
            "量说明": "需求类表中名字带「开始/启动」的字段个数",
            "明细": startf,
            "owner": "源系统负责人（creative=Roxie / seo=Rikka）",
            "status": "待提出",
            "提出方式": "逐字段确认语义（实际/计划、填写时机），确认前该字段不得进判据",
            "复算": "python3 tools/kb_query.py 7",
        },
        {
            "id": "D3", "kind": "access",
            "title": "材料收集表大部分读不到",
            "why": "材料表只记「链接」，不记「这条链接我到底读不读得到」。于是"
                   "「收集了 15 条」是错觉：读得到的是少数。",
            "affects": ["Q10"],
            "量": {"materials_unreadable": facts["materials_unreadable"],
                  "materials_total": facts["materials_total"]},
            "owner": "Roxie、Rikka、Misty、Emma",
            "status": "待补授权或重取链接",
            "复算": "python3 tools/kb_materials_lark.py（打印实测可读性）",
        },
        {
            "id": "D4", "kind": "classification",
            "title": "品线字段取值未归一",
            "why": "PSEO 的「品类」字段里写的是「翼果未分类，后续文章已进行分类」"
                   "—— 把一句话写进了分类字段。未归一的取值无法参与任何品线口径的统计。",
            "affects": ["Q3", "Q8"],
            "量": {"demands_unmapped": facts["demands_unmapped"]},
            "owner": "SEO 侧（Rikka）",
            "status": "待确认口径",
            "复算": "python3 tools/kb_evidence.py（缺口表 §三）",
        },
        {
            "id": "D5", "kind": "schema",
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
            "id": "D6", "kind": "evidence",
            "title": "七个品线族零证据",
            "why": "本地全部合规证据只覆盖吸奶器一个品线；其余品线的需求拿不到"
                   "任何本地判定依据。",
            "affects": ["Q8"],
            "量": {"demands_without_evidence": facts["demands_without_evidence"],
                  "lines_with_evidence": facts["lines_with_evidence"]},
            "owner": "品牌 / 法务 / 各品线负责人",
            "status": "待收集",
            "复算": "python3 tools/kb_query.py 8",
        },
        {
            "id": "D7", "kind": "evidence",
            "title": "内部正负样本库没有真实样本",
            "why": "业务侧表里有 8 条记录，其中 7 条备注写「样例」—— 是模板示范，"
                   "不是数据。这是 Agent 训练素材最核心的来源，也是最贵的一块。",
            "affects": ["Q10"],
            "量": {"samples_on_disk": facts["samples_on_disk"],
                  "samples_marked_sample": facts["samples_marked_sample"],
                  "samples_header_returned": facts["samples_header_returned"]},
            "量说明": "★ 三个数并排：盘上记录数 / 其中标「样例」的 / 文件头声明的条数。"
                     "前两个相等（全是样例），第三个数更大 —— **证据落盘件自己和自己打架**，"
                     "在重新拉取之前不许把 8 当成事实",
            "owner": "品牌张丽敏、吸奶器银舒涵、喂养 William、法务",
            "status": "待收集；且需重拉证据（落盘件与抬头不一致）",
            "复算": "python3 tools/kb_classes.py（同时打印这两个数）",
        },
        {
            "id": "D8", "kind": "evidence",
            "title": "外部标准库有 62 条条款级条目，但 0 条经法务确认",
            "why": "B3.0 时这条写的是「没有条款级条目」。2026-09-17 制品落盘"
                   "（research/kb/外部标准库-v1.json，17 来源 / 62 条），"
                   "缺口因此**换了形态而没有消失**：条目有了，但全部 status=research、"
                   "authority.ratifier 仍为 null —— 研究稿仍不能被当成判定依据。"
                   "★ 量从 0 变成 62 是这条缺口第一次能被算出来。",
            "affects": ["Q10", "F3"],
            "量": {"ext_entries": facts["ext_entries"],
                  "ext_ratified": facts["ext_ratified"]},
            "量说明": "已入册的条款级条目数 / 其中经法务确认的 —— 62 与 0 并排，"
                     "就是「有材料」与「能引用」之间的距离",
            "owner": "法务 Sharon、专家 Emma、北美待定",
            "status": "待法务逐条确认（建议顺序：14 条空白 + 6 条高价值）",
            "复算": "python3 tools/verify_external.py --offline",
        },
        {
            "id": "D9", "kind": "process",
            "title": "源表 `合规·绿` 一列扛三个正交量：157 条里 0 条是「已查且通过」",
            "why": "B3.4 演练先看到的是「59 条无文案被标绿」。执行 D9 时把**全部 157 条"
                   "绿标**逐行重跑引擎，洞比原来大一档：55 条无文案 + 99 条**规则库"
                   "够不着**（引擎落 catch_all）+ 3 条**引擎命中了、源表没有**"
                   "（2026-09-17 经 D15 逐行对账：**是我们迁移翻了语义**，"
                   "源表那一次的放行是对的），"
                   "而「已查且通过」是 **0 条**。这不是新提法 —— 设计文档 §4.5/§5.1 早已"
                   "认定语义重载，R2 §2989 甚至写了「这个数字无法被还原」。**现在还原了。**"
                   "再叠加两条实证：`检查人` 列 0/291 从未有人填写；`命中规则` 非空 132 条"
                   "恰好等于红 91+黄 30+灰 11，非空为空 159 条恰好等于绿 157+空 2，"
                   "**无一例外** —— 即 `合规·绿` 不是结论，是「规则没命中」这个默认值的"
                   "显示名（见 D15）。代价是一个字段扛三个量使两个数**在数学上算不出来**："
                   "盲区率 43.1%、未审率 53.9%。逐行还原账与给投放侧的变更请求已交付。",
            "affects": ["Q1", "Q6"],
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
            "id": "D10", "kind": "evidence",
            "title": "Meta 政策页在本机无匿名取法，只能对 09-15 的钉住件核",
            "why": "transparency.meta.com 是纯客户端 SPA，正文经 /api/graphql/ 拉取。"
                   "实测八条路全部只得到标题与 JS bundle：朴素 UA、浏览器 UA、无斜杠、"
                   "?_fb_noscript=1、en-gb、?print=1、amp、Firecrawl 渲染、浏览器桥"
                   "（未连接）。今天六条能核上，靠的是仓内 _evidence/R1 与 R5 里 "
                   "2026-09-15 抓的证据件（URL 与引用来源一致）。"
                   "★ 这六条的可复核性上限 = 那一天。",
            "affects": ["F3", "D8"],
            "量": {"sources_meta": facts["sources_meta"],
                  "entries_meta": facts["entries_meta"]},
            "量说明": "Meta 来源数 / 其中条目数 —— 这两个数就是「只能靠钉住件」的暴露面",
            "owner": "证据侧",
            "status": "待定：接受「钉住件即证据上限」，还是需要一条能刷新 Meta 页的取法",
            "提出方式": "确认可接受钉住件，或提供代理/渲染取法",
            "复算": "python3 tools/verify_external.py --offline",
        },
        {
            "id": "D11", "kind": "evidence",
            "title": "TikTok 广告政策正文页取不到，库内只有品牌内容政策一条",
            "why": "TikTok Advertising Policies 正文由 cognition.byteoversea.com 拉取，"
                   "匿名请求 302 跳登录。故 S17 只有 Branded Content Policy"
                   "（tiktok.com/legal 可静态抓）四条。这是覆盖缺口，不是抓取失败。",
            "affects": ["F3", "D8"],
            "量": {"sources_tiktok": facts["sources_tiktok"],
                  "entries_tiktok": facts["entries_tiktok"]},
            "量说明": "TikTok 来源数 / 条目数 —— 与其他渠道相比明显偏薄",
            "owner": "证据侧",
            "status": "待确认：是否需要登录态或替代来源补齐 TikTok 广告政策",
            "提出方式": "提供可访问路径，或接受当前覆盖",
            "复算": "python3 tools/verify_external.py --only S17",
        },
        {
            "id": "D12", "kind": "evidence",
            "title": "EU 侧（MDR/EUR-Lex）抓不到，英国站只有 MHRA + CAP",
            "why": "eur-lex.europa.eu 返回 HTTP 202 + 空 body，本轮没有欧盟条目。"
                   "英国站的两条依据（MHRA 药品广告、CAP §12）都不覆盖医疗器械侧 ——"
                   "英国站的依据面比看上去窄。",
            "affects": ["F3", "D8"],
            "量": {"sources_eu": facts["sources_eu"],
                  "sources_uk": facts["sources_uk"]},
            "量说明": "欧盟来源数 / 英国来源数 —— 0 与 2 并排",
            "owner": "证据侧 + 法务",
            "status": "待确认：欧盟侧是否必须补（涉及英国站与欧盟站的合规判定）",
            "提出方式": "确认是否补 EU 来源",
            "复算": "python3 tools/verify_external.py --offline",
        },
        {
            "id": "D13", "kind": "legal",
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
            "id": "D14", "kind": "legal",
            "title": "14 条空白条目 / 7 个候选规则族待法务确认",
            "why": "62 条里有 14 条的「关联规则」为空（= 我们规则库没有对应条目），"
                   "归成 7 个候选规则族。全部 status=research、ratifier=null。"
                   "★ 其中 EXT-016（素材中广告主身份）的归族由整合人判定，"
                   "研究者未在制品中落组 —— 这一条的分组是人的判断，不是来源的说法。",
            "affects": ["F3", "D8"],
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
            "id": "D15", "kind": "data",
            "title": "规则迁移不保真：94 个旧豁免词里 28 个被翻成「降级」，"
                     "把本该放行的广告标成可疑",
            # ★ 本条已**改写**。立案时的表述是「源表的规则扫描漏放 3 条」——
            #   做完逐行对账后，那句话是错的，且错的方向是**指控了源表**。
            #   留这段注释是为了让「改口」这件事本身可审计。
            "why": "D9 逐行还原时掉出来 3 条绿标被引擎命中。当时的解释是「源表漏放」。"
                   "2026-09-17 做了两次扫描的逐行对账（`audit_migration_fidelity.py`），"
                   "结论反过来了：**源表是对的，错的是我们自己的迁移**。"
                   "证据链：① 旧规则 H01 的 `exceptions` 里有 `treat yourself`；"
                   "② 同批次 `Savannah-20260825` 天然对照证明旧 `exceptions` 的语义是"
                   "**放行**（i=265 含豁免词→源表 0 命中·绿；i=270/271 不含→命中 H07,U04·红，"
                   "同一次扫描）；③ 迁移把这 94 个豁免词拆进语境守卫表（80）与白名单（14），"
                   "其中 **28 个已接线、却不属于免责/否定类** —— 它们被当成"
                   "「免责声明」降级了，而它们根本不是免责声明（`treat yourself` 是词义消歧、"
                   "`natural letdown` 是生理事实、`inspired by` 是归因）。"
                   "设计文档 §F「免责声明不是许可证」这条教条**只对否定式成立**，"
                   "迁移把它无差别套到了全部 94 个词上。同一个短语，旧系统拿它免责、"
                   "新系统拿它定罪。另有一条同根词被拆进相反通道：`comfort` 进白名单（放行）、"
                   "`comfortable` 进语境守卫（降级）。",
            "affects": ["Q1", "Q6"],
            "量": {
                "legacy_exception_words": facts["legacy_exception_words"],
                "exception_wired_non_disclaimer": facts["exception_wired_non_disclaimer"],
                "regression_false_positives": facts["regression_false_positives"],
                "scan_drift_records": facts["scan_drift_records"],
                "scan_pairs_agree": facts["scan_pairs_agree"],
                "orphan_keywords": facts["orphan_keywords"],
            },
            "量说明": "旧豁免词总数 / 其中被当成降级接线、却非免责否定类的 / "
                      "**实际翻掉的记录数（假阳性）** / 两次扫描有分歧的记录数 / "
                      "两次扫描一致的记录数 / 在新规则里彻底没有家的旧关键词数。"
                      "★ 假阳性那一格是 3、不是 28：28 是**暴露面**，3 是**这份语料上"
                      "已经发生的**。两个数都要写，只写一个都会误导。",
            "owner": "审核侧（规则维护，谁迁的谁修）；不需要投放侧动手",
            "status": "待修：把 28 个非免责类豁免词按语义分三档归位"
                      "（真免责→维持降级 / 词义消歧与归因→改为放行 / 弱化表述→法务定性）；"
                      "`treat yourself` 一类应先改回放行",
            "提出方式": "把旧规则集的 94 个豁免词与新系统的两张词表逐词对账，"
                        "并用同批次对照实测旧语义 —— 不靠回忆，靠重跑",
            "复算": "python3 research/governance/audit_migration_fidelity.py --check",
            "$report": "research/governance/skeleton/_data/迁移保真度.json",
        },
        {
            "id": "D16", "kind": "data",
            "title": "源表扫描看到的文案，我们没采到：13 个命中片段在今天的语料里搜不到",
            "why": "源表有一列 `命中片段`，记的是**它当时到底命中了什么字符串**，"
                   "132 条记录、270 个片段。拿它逐条回今天的语料里搜，"
                   "**13 个搜不到**（4.8%），涉及 6 条记录 —— 例如 i=48 源表自报命中"
                   "`whisper` / `hospital` / `hospital-grade` / `maximum suction`，"
                   "而这四个串在 `Primary Text` 里一个都没有。"
                   "★ 这不是规则差异，是**输入差异**：源表扫描看到的广告资产"
                   "（RSA 的多个标题/描述、附加信息）比我们存下来的多。"
                   "两者必须分开，否则「去修采集」会被记成「去改规则」—— "
                   "这正是 D9 那类合并计数病的同一形状。"
                   "`EMPTY` / `<文案为空` 是源表给「整行没读到」留的哨兵值，已排除。",
            "affects": ["Q1", "Q6"],
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
    ]
    return {
        "schema_version": "缺口-v1",
        "snapshot_id": facts["snapshot_id"],
        "basis_date": facts["basis_date"],
        "generated_by": "tools/kb_gaps.py",
        "$note": NOTE,
        "gaps": gaps,
    }


def main():
    check = "--check" in sys.argv
    doc = build()
    new = json.dumps(doc, ensure_ascii=False, indent=1) + "\n"
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else None
    if new == old:
        print(f"✅ 缺口登记与重算一致：{len(doc['gaps'])} 条"
              f"（{'/'.join(g['id'] for g in doc['gaps'])}）")
        return 0
    if check:
        print("❌ 缺口登记与重算不一致 —— 修复：python3 tools/kb_gaps.py")
        return 1
    open(OUT, "w", encoding="utf-8").write(new)
    print(f"✅ 已写回 {os.path.relpath(OUT, load.REPO)}：{len(doc['gaps'])} 条缺口")
    for g in doc["gaps"]:
        q = ("量=" + json.dumps(g["量"], ensure_ascii=False)) if "量" in g \
            else "量=不可重算"
        print(f"   {g['id']:<3}{g['kind']:<15}{g['title'][:26]:<28}{q}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
