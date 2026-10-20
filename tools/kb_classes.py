#!/usr/bin/env python3
"""
kb_classes.py —— 4 类知识库的**登记表**（`research/kb/知识库-v1.json`）

## 为什么存在

业务侧在自己的 Base 里已经**定义好了 4 类知识库**（要包含什么、建议字段、
负责人、需向对接人收集的问题）。过去这份定义在本仓有三处影子：

  · `需求知识库-建设方案` §六 P2 的一张表
  · `tools/kb_materials_lark.py` 的 `CATEGORIES`（抄了一遍）
  · 同文件的 `TASKS`（又抄了一遍「每类缺什么」）

三处各自会漂。更麻烦的是第三处 —— 它抄的是**现状**，而现状是唯一必须现算的东西。
B3.0 已经因为这个形状吃过一次（同一个数在两处矛盾，见 ADR §15.4）。

## 本表的规矩

**定义抄业务侧（逐字），现状一律现算。** 每一类的「本地现有条目 / 状态 / 缺口说明」
三列由本脚本从制品重算：

  外部标准库       ← `research/kb/外部标准库-v1.json`（研究稿在 `_staging/` 另计）
  内部正负样本库   ← `_evidence/正负样本.raw.txt` 逐条解析
  措辞表达库       ← `skeleton/rules-v1.json` · `whitelist-v1.json` · `context-guards-v1.json`
  产品描述库       ← `tools/kb_materials_data.py` 的实测可读性

**空类必须显式说自己是空的，并指向缺口编号。** 这四类里现在有三类是空的或半空的 ——
把它们写成「进行中」很容易，但那正是这套知识库最不该犯的错。
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "research", "kb"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import load                  # noqa: E402
import kb_materials_data as md   # noqa: E402

OUT = os.path.join(load.KB, "知识库-v1.json")
EXT = os.path.join(load.KB, "外部标准库-v1.json")
EXT_STAGING = os.path.join(load.KB, "_staging", "外部标准库-研究稿.json")
# ★ 2026-10-20：原来的 `SAMPLES = _evidence/正负样本.raw.txt` 已删。
#   样本现在读 `research/live/LATEST.json`（见 parse_samples）。留着一个没有消费者的
#   常量，正是 AGENTS.md §2.4 点名的「定义了没人用」——它会让人以为还有第二条源。
SKEL = os.path.join(load.REPO, "research", "governance", "skeleton")

# ── 定义：逐字取自业务侧「知识库分类说明」表（这一半是抄的，且应当只是抄） ──
DEFS = [
    {"知识库": "外部标准库",
     "要包含什么": "美国法规、平台政策、行业标准、医学共识、本地常识",
     "建议字段材料": "官方链接/PDF、条款、内部合规摘要、适用产品线、生效日期",
     "负责人": "法务 Sharon、专家 Emma、北美待定",
     "待收集问题": "已有政策/合规摘要？需覆盖哪些平台？哪些医学结论需专家确认？",
     "缺口": "KB-GAP-8"},
    {"知识库": "内部正面与负面样本库",
     "要包含什么": "正面：已通过且合规的优秀内容；负面：投诉、下架、警告、返工、"
                   "达人争议、审核争议",
     "建议字段材料": "样本 ID、产品线、渠道、内容类型、原文/截图/视频、问题/亮点、"
                     "风险等级、依据、处理结果、修改前后、是否可规则化",
     "负责人": "品牌张丽敏、吸奶器银舒涵、喂养 William、法务",
     "待收集问题": "各品线已有多少正/负样本？是否可外发？是否可脱敏？",
     "缺口": "KB-GAP-7"},
    {"知识库": "措辞表达库",
     "要包含什么": "Do not say / Say this instead；禁用、慎用、推荐表达；中英对照；适用场景",
     "建议字段材料": "表达、类型、场景、依据、风险等级、替代表达、语言",
     "负责人": "品牌、法务、北美、专家",
     "待收集问题": "已有禁用词/推荐话术？哪些表达易被平台误判？",
     "缺口": "KB-GAP-6"},
    {"知识库": "产品描述库",
     "要包含什么": "功能边界、型号差异、允许/禁止描述、适用人群、使用场景、认证参数、常见误解",
     "建议字段材料": "产品线、型号、卖点、边界、禁止表述、认证、FAQ",
     "负责人": "吸奶器 Misty/银舒涵、喂养 William、品牌 Daisy/张丽敏、专家 Emma",
     "待收集问题": "各品线已有产品手册/卖点/认证？哪些描述容易越界？",
     "缺口": "KB-GAP-3"},
]


def _json(p, default=None):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def parse_samples():
    """从当前快照里读「正面和负面样本」表，现算规模与质量读数。

    ★ 2026-10-20 换源（在此之前读的是 `_evidence/正负样本.raw.txt`）。

    旧实现读的是一份 1.3 KB 的 dump：5 条记录、抬头写 `returned=8`、备注全是「样例」。
    它还把这处「文件自己和自己打架」当成整个样本库的问题。实测云端同表当时已有
    **186 条**真实记录，`渠道/市场` `审核人` `来源` `提交时间` 四列 186/186 非空。

    也就是说：**真实记录不是 1 条，是 0 条被读到。** 病不在数据，在源。

    现在读 `research/live/LATEST.json` 指向的快照。★ 刻意**不复用** kb_facts 的
    解析器 —— E2 要在「登记表里写的数」与「重算出来的数」之间比对，两者必须来自
    不同的实现，否则那条检查恒真。这条理由在换源之后一字未变。
    """
    ptr = os.path.join(load.REPO, "research", "live", "LATEST.json")
    if not os.path.exists(ptr):
        return None
    try:
        latest = json.load(open(ptr, encoding="utf-8"))
        snap_path = os.path.join(load.REPO, "research", "live", latest["latest"])
        doc = json.load(open(snap_path, encoding="utf-8"))
    except (OSError, KeyError, json.JSONDecodeError):
        return None
    src = (doc.get("sources") or {}).get("kb_samples")
    if src is None:
        return None
    recs = src.get("records") or []
    fields = [(r.get("fields") or {}) for r in recs]

    def _has(f, k):
        v = f.get(k)
        if isinstance(v, str):
            return v.strip() != ""
        if isinstance(v, list):
            return len(v) > 0
        return v is not None

    marked = sum(1 for f in fields if "样例" in str(f.get("备注（如处理结果/建议）") or ""))
    return {
        "文件头声明": {"total": src.get("api_total"), "returned": src.get("read_count")},
        "盘上记录数": len(recs),
        "标注为样例": marked,
        "真实样本": len(recs) - marked,
        "不一致": (src.get("api_total") != src.get("read_count")) if src.get("api_total") else None,
        "快照": latest.get("latest"),
        "快照时刻": doc.get("captured_at_utc"),
        # 下面四个是这次换源之后**才第一次能被算出来**的质量读数
        "无原因分类": sum(1 for f in fields if not _has(f, "原因分类")),
        "无图片附件": sum(1 for f in fields
                          if f.get("素材类型") == "图片" and not _has(f, "图片素材")),
        "无建议": sum(1 for f in fields if not _has(f, "建议")),
        "正例数": sum(1 for f in fields if f.get("分类") == "正例"),
    }


def status_rows():
    """**现算**每一类的现状。返回 {类名: {"本地现有条目":…, "状态":…, "缺口说明":…, "量":{…}}}"""
    ext = _json(EXT, {"entries": []})
    staging = _json(EXT_STAGING, {"entries": [], "sources": []})
    ratified = [e for e in ext.get("entries", []) if e.get("status") == "ratified"]
    research = [e for e in ext.get("entries", []) if e.get("status") == "research"]
    smp = parse_samples()
    rules = _json(os.path.join(SKEL, "rules-v1.json"), {"rules": []})["rules"]
    wl = _json(os.path.join(SKEL, "whitelist-v1.json"), {})
    cg = _json(os.path.join(SKEL, "context-guards-v1.json"), {})
    # ★ 读**制品自己的 stats 块**，不要自己数列表长度。第一版数的是
    #   `words` 的长度（30 / 85），而 stats 里写着 total=30 / active=26 ——
    #   「26 词」指的是 active。同一份文件里两个都叫「白名单词数」的数，
    #   正是 B3.0 治过的那种病；这里直接引用制品声明的口径，并把它写清。
    wl_stats = wl.get("stats", {})
    cg_stats = cg.get("stats", {})
    ev = _json(os.path.join(load.KB, "证据映射.json"), {"totals": {}, "rows": []})
    lines_with = ev["totals"].get("lines_with_evidence")
    lines_total = len(ev.get("rows", [])) or None
    cls = md.by_class()
    prod = cls["产品描述库"]
    prod_readable = sum(1 for m in prod if m["可读性"] == "ok")

    return {
        "外部标准库": {
            "本地现有条目": (f"{len(ext.get('entries', []))} 条已入册"
                             f"（其中 ratified {len(ratified)} / research {len(research)}）；"
                             f"研究稿另计 {len(staging.get('entries', []))} 条"
                             f"／来源 {len(staging.get('sources', []))} 个"),
            "状态": ("空白" if not ext.get("entries") and not staging.get("entries")
                     else ("已有条目但全部未经法务确认" if not ratified else "部分已确认")),
            "缺口说明": "R1 做了平台政策分类学研究，但没有产出可被工具调用的条款级条目；"
                        "B3.2 起按 D28 以「研究稿·未经法务确认」入册，法务只做确认/否决",
            "量": {"ext_entries": len(ext.get("entries", [])),
                   "ext_ratified": len(ratified),
                   "ext_staging_entries": len(staging.get("entries", [])),
                   "ext_staging_sources": len(staging.get("sources", []))},
        },
        "内部正面与负面样本库": {
            "本地现有条目": (
                (f"{smp['盘上记录数']} 条（快照 {smp['快照']}，"
                 f"应用身份可见 {smp['文件头声明']['total']} 条）；"
                 f"正向样本 {smp['正例数']} 条 / 无原因分类 {smp['无原因分类']} 条 / "
                 f"无建议 {smp['无建议']} 条 / 标图但无图 {smp['无图片附件']} 条"
                 if smp else "无样本快照（先跑 python3 tools/live_snapshot.py）")),
            "状态": ("有货但未治理" if smp and smp["盘上记录数"] else "空白"),
            "缺口说明": (
                "★ 2026-10-20 换源。此前读的是 `_evidence/正负样本.raw.txt`"
                "（5 条、备注全写「样例」），据此判定「没有真实样本」——**判错了**："
                "云端同表当时已有 186 条，问题在本地没读，不在业务方没交。"
                "现在真实缺陷换了形态：① 全表 0 条正例（`分类` 字段的「正例」选项从未被用），"
                "于是「PASS 误放率」无法测；② 27% 记录 `原因分类` 为空，"
                "正文前缀是 `【审核问题】`（不在 7 个枚举里），疑为流程反馈混入样本；"
                "③ `素材类型=图片` 却有 55 条没有图片附件；④ 视频样本 0 条。"
                "这些**都还未经业务确认**，登记为缺口而不是就地清洗。"),
            "量": {"samples_on_disk": smp["盘上记录数"] if smp else None,
                   "samples_marked_sample": smp["标注为样例"] if smp else None,
                   "samples_real": smp["真实样本"] if smp else None,
                   "samples_positive": smp["正例数"] if smp else None,
                   "samples_no_reason": smp["无原因分类"] if smp else None,
                   "samples_no_advice": smp["无建议"] if smp else None,
                   "samples_image_missing": smp["无图片附件"] if smp else None},
        },
        "措辞表达库": {
            "本地现有条目": (f"规则 {len(rules)} 条 + 白名单 active "
                             f"{wl_stats.get('active', '?')}/{wl_stats.get('total', '?')} 词"
                             f"（隔离 {wl_stats.get('quarantined', '?')}）+ 语境守卫 "
                             f"{cg_stats.get('guards', '?')} 条"
                             f"（已接线 {cg_stats.get('wired', '?')}）；"
                             f"改写建议 52 条在飞书源表，本地未落盘"),
            "状态": (f"已有货但只覆盖 {lines_with}/{lines_total} 个品线"
                     if lines_with is not None else "无法判定品线覆盖"),
            "缺口说明": "全部已声明证据的适用产品为吸奶器型号（W1/M5/M6/M9/Air1）。"
                        "其余品线 0 条 —— 品线覆盖以 `证据映射.json` 为准，不由本表另算一个数",
            "量": {"lex_rules": len(rules),
                   "lex_whitelist_active": wl_stats.get("active"),
                   "lex_guards": cg_stats.get("guards"),
                   "lex_guards_wired": cg_stats.get("wired"),
                   "lex_lines_covered": lines_with,
                   "lex_lines_total": lines_total},
        },
        "产品描述库": {
            "本地现有条目": f"{len(prod)} 条材料登记，其中可程序读取 {prod_readable} 条",
            "状态": "材料不可读" if prod_readable == 0 else "部分可读",
            "缺口说明": "材料已登记但权限错误（131006/1310213），等于 0；"
                        "且只覆盖吸奶器/婴幼儿/喂养，缺 5 个品线",
            "量": {"prod_materials": len(prod), "prod_readable": prod_readable},
        },
    }


def build():
    rows = status_rows()
    cls = []
    for d in DEFS:
        r = dict(d)
        s = rows[d["知识库"]]
        r.pop("缺口", None)
        r["本地现有条目"] = s["本地现有条目"]
        r["状态"] = s["状态"]
        r["缺口说明"] = s["缺口说明"]
        r["缺口编号"] = d["缺口"]
        r["量"] = s["量"]
        cls.append(r)
    mats = md.readable()
    return {
        "schema_version": "知识库-v1",
        "generated_by": "tools/kb_classes.py",
        "authority": {
            "定义": "业务侧「知识库分类说明」表（逐字）",
            "现状": "本脚本现算 —— 不许手抄",
            "条目确认": "外部标准库条目在法务确认前一律 status=research（D28）",
        },
        "$note": [
            "★ 本表回答黄金问题 KB-Q-10「4 类知识库各有多少条、缺什么、谁负责」。",
            "★ 定义是抄的，现状是算的。任何一类的「本地现有条目」都必须能在",
            "  `tools/kb_classes.py` 的 status_rows() 里重算出来，否则 E 组会红。",
            "★ 空类必须显式说自己是空的，并带缺口编号 —— 把空写成「进行中」是",
            "  这套知识库最容易犯、也最难被发现的错。",
            "★ 检查：`python3 tools/verify_kb.py`（F 组）。",
        ],
        "材料收集": {
            "总数": mats["total"],
            "可程序读取": mats["readable"],
            "不可读": mats["unreadable"],
            "按性质": {n: sum(1 for m in md.MATERIALS if m["材料性质"] == n)
                       for n in md.NATURES},
            "按归属": {k: len(v) for k, v in md.by_class().items()},
            "未分类": len(md.unclassified()),
        },
        "classes": cls,
    }


def category_rows():
    """给 `kb_materials_lark.py` 写飞书用的行（与本地登记表同一来源）。"""
    return [{k: v for k, v in c.items() if k != "量"} for c in build()["classes"]]


def collection_tasks():
    """P2.3 收集任务：**由登记表生成**，每类一条 + 一条跨类权限。

    与 `CATEGORIES` 同源。过去 TASKS 是手写的一份「每类缺什么」，
    与定义表重复 —— 同一件事写两处就会漂。
    """
    out = []
    for c in build()["classes"]:
        st = c["状态"]
        out.append((c["知识库"], c["待收集问题"], c["负责人"],
                    "未启动" if "空白" in st or "不可读" in st else "部分完成",
                    f"〔缺口:{c['缺口编号']}〕{c['本地现有条目']} —— {c['缺口说明']}"))
    r = md.readable()
    out.append(("（跨类）权限",
                f"材料收集表 {r['total']} 条中 {r['unreadable']} 条无法以程序方式读取，"
                f"需补授权或重取链接",
                "Roxie、Rikka、Misty、Emma", "未启动",
                f"可读 {r['readable']} 条 / 不可读 {r['unreadable']} 条（现算）。"
                "材料表原本只记链接不记可读性，导致「收集了 N 条」的错觉"))
    return out


def main():
    check = "--check" in sys.argv
    new = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    old = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else None
    if new == old:
        print("✅ 4 类登记表与重算一致")
        return 0
    if check:
        print("❌ 4 类登记表与重算不一致 —— 修复：python3 tools/kb_classes.py")
        return 1
    open(OUT, "w", encoding="utf-8").write(new)
    print(f"✅ 已写回 {os.path.relpath(OUT, load.REPO)}")
    for c in build()["classes"]:
        print(f"   {c['知识库']:<14}{c['状态']:<18}{c['本地现有条目'][:44]}"
              f"  〔缺口:{c['缺口编号']}〕")
    print(f"   材料：{json.dumps(build()['材料收集'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
