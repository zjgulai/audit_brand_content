#!/usr/bin/env python3
"""
kb_query.py —— 需求知识库 · 黄金问题查询（G3 验收）

建设方案 §七 定义了 10 条黄金问题，作为「可用性」的验收门：
**不读代码就能回答这 10 个问题**，否则台账只是把飞书表格搬了个家。

本脚本把每条问题做成一条可复现命令。答不出来的问题会被标成 GAP —— 
**答不出来不是失败，假装答得出来才是。**

用法：
  python3 tools/kb_query.py              # 全部 10 条
  python3 tools/kb_query.py 3            # 只跑第 3 条
  python3 tools/kb_query.py --md         # 生成查询手册
"""

import collections
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "research", "kb"))
import load  # noqa: E402

LEDGER = os.path.join(load.KB, "台账-v1.json")
EVIDENCE = os.path.join(load.KB, "证据映射.json")
ANALYSIS = os.path.join(load.KB, "结构分析.json")
MANUAL = os.path.join(load.KB, "查询手册.md")

IN_FLIGHT = ("进行中", "未开始", "已停滞")


def load_all():
    led = json.load(open(LEDGER, encoding="utf-8"))
    return led, [r for r in led["records"] if r["role"] != "excluded"]


# ── 十条黄金问题 ────────────────────────────────────────────

def q1(led, rs):
    """现在总共有多少条在跑的需求？分别来自哪些系统？"""
    out = [f"台账共 {len(rs)} 条（顶层 {sum(1 for r in rs if r['level']=='top')} + "
           f"子任务 {sum(1 for r in rs if r['level']=='child')}）"]
    run = [r for r in rs if r.get("status") in IN_FLIGHT]
    out.append(f"在跑（进行中 + 未开始 + 已停滞）：{len(run)} 条")
    for sysname in ("creative", "seo"):
        s = [r for r in rs if r["source_system"] == sysname]
        sr = [r for r in s if r.get("status") in IN_FLIGHT]
        out.append(f"  {sysname:<9} 共 {len(s):>4} 条，在跑 {len(sr):>4} 条")
    for t, n in collections.Counter(r["source_table"] for r in run).most_common():
        out.append(f"    · {t:<24} {n:>4}")
    return out


def q2(led, rs):
    """哪些需求逾期未交付？逾期多久？"""
    today = load.today()
    cand = [r for r in rs if r.get("date_due") and r.get("status") != "已完成"]
    over = []
    for r in cand:
        d = load.days_between(r["date_due"], today)
        if d > 0:
            over.append((d, r))
    over.sort(key=lambda x: -x[0])
    out = [f"有计划完成日期且未完成的 {len(cand)} 条中，逾期 {len(over)} 条"
           f"（基准日 {today}）"]
    out.append("⚠️ 全量 1160 条里只有 189 条有计划完成日期 —— "
               "**逾期率只能建在这个子集上，不能外推**")
    for d, r in over[:12]:
        out.append(f"  {d:>4} 天  [{r['source_system']}] {str(r['title'])[:44]:<46}"
                   f" 负责人={r.get('owner') or '—'} 状态={r.get('status') or '—'}")
    if len(over) > 12:
        out.append(f"  … 另 {len(over)-12} 条")
    return out


def q3(led, rs):
    """每个品线各压了多少需求？哪条品线最紧？"""
    ev = json.load(open(EVIDENCE, encoding="utf-8"))
    out = [f"{'品线族':<8}{'总需求':>7}{'在跑':>7}{'已停滞':>7}{'无状态':>7}{'证据':>6}  分级"]
    for row in ev["rows"]:
        fam = row["品线族"]
        out.append(f"{fam:<8}{row['需求条数']:>7}{row['进行中']+row['未开始']+row['已停滞']:>7}"
                   f"{row['已停滞']:>7}{row['无状态']:>7}{row['已声明证据数']:>6}"
                   f"  {row['证据分级']}")
    un = ev["totals"]["demands_unmapped"]
    out.append(f"\n另有 {un} 条品线未识别（PSEO「翼果未分类」283 条为主）")
    return out


def q4(led, rs):
    """每个跟进人/剪辑师手上各有多少条在跑？"""
    run = [r for r in rs if r.get("status") in IN_FLIGHT and r.get("owner")]
    c = collections.Counter()
    for r in run:
        for who in str(r["owner"]).split(";"):
            who = who.strip()
            if who:
                c[who] += 1
    out = [f"在跑且填了负责人的 {len(run)} 条，涉及 {len(c)} 人"]
    for who, n in c.most_common(15):
        out.append(f"  {n:>4}  {who}")
    return out


def q5(led, rs):
    """哪些需求在多个系统里重复出现？"""
    an = json.load(open(ANALYSIS, encoding="utf-8"))
    ds = an["duplicate_summary"]
    out = [f"扫描 {ds['demand_records_scanned']} 条，排除 {ds['child_rows_excluded']} 条 WBS 子任务",
           f"同标题+同SKU+同日期 的重复键 {ds['duplicate_keys']} 个，涉 {ds['records_involved']} 条",
           f"**跨表重复 {ds['cross_table_keys']} 个** —— creative 与 seo 是两条互不重叠的线"]
    for d in an["duplicate_candidates"][:6]:
        out.append(f"  ×{d['n']}  {d['items'][0]['raw'][:46]}  ← {', '.join(d['tables'])}")
    return out


def q6(led, rs):
    """哪些需求已完成但没有产出物？"""
    done = [r for r in rs if r.get("status") == "已完成"]
    noout = [r for r in done if not r.get("deliverable")]
    out = [f"已完成 {len(done)} 条，其中产出物字段为空 {len(noout)} 条"
           f"（{len(noout)/len(done):.0%}）"]
    for t, n in collections.Counter(r["source_table"] for r in noout).most_common():
        tot = sum(1 for r in done if r["source_table"] == t)
        out.append(f"  {t:<24} {n:>4} / {tot:<4} 完成项无产出物")
    out.append("⚠️ 「产出物字段为空」≠「没有产出物」—— 可能只是没填。"
               "这张表回答的是**可追溯性**，不是实际交付情况。")
    return out


def q7(led, rs):
    """哪些需求卡在同一状态超过阈值？"""
    stuck = [r for r in rs if r.get("status") == "已停滞"]
    out = [f"显式标记「已停滞」的：{len(stuck)} 条"]
    for r in stuck:
        out.append(f"    {str(r['title'])[:60]}  [{r['source_table']}]")
    out.append("")
    out.append("❌ **GAP：无法回答「卡在同一状态超过 N 天」**")
    out.append("   原因：源系统只有当前状态，没有状态变更时间戳。")
    out.append("   没有历史就无法算停留时长 —— 用「提交日期至今」代替会把"
               "「一直没开始」和「做到一半停住」混为一谈。")
    out.append("   → 已登记为对源系统的数据需求：状态变更需留痕。")
    return out


def q8(led, rs):
    """本地已有证据能支撑哪些需求？哪些需求零证据？"""
    ev = json.load(open(EVIDENCE, encoding="utf-8"))
    t = ev["totals"]
    out = [f"已声明品线专属证据 {t['declared_evidence']} 项，"
           f"覆盖 {t['lines_with_evidence']}/{len(ev['rows'])} 个品线族"]
    for row in ev["rows"]:
        mark = "✅" if row["已声明证据数"] else "❌"
        out.append(f"  {mark} {row['品线族']:<8} 证据 {row['已声明证据数']:>2}  "
                   f"对应需求 {row['需求条数']:>4} 条  {row['证据分级']}")
    zero = sum(r["需求条数"] for r in ev["rows"] if not r["已声明证据数"])
    out.append(f"\n**零证据品线共 {zero} 条需求，占已归入品线的 "
               f"{zero/t['demands_mapped']:.0%}**")
    out.append("本地全部合规证据只覆盖吸奶器一个品线。")
    return out


def q9(led, rs):
    """哪些需求类型反复出现、具备规则化/自动化潜力？"""
    c = collections.Counter(r["category"] for r in rs if r.get("category"))
    out = ["按类别（需求类型 / 性质 / 渠道）统计："]
    for k, n in c.most_common(16):
        out.append(f"  {n:>4}  {k}")
    names = collections.Counter()
    for r in rs:
        t = str(r.get("title") or "")
        for sep in ("：", ":"):
            if sep in t:
                names[t.split(sep)[0].strip()[:20]] += 1
                break
    out.append("\n标题前缀反复出现（疑似可模板化的批量作业）：")
    for k, n in names.most_common(10):
        if n >= 3:
            out.append(f"  {n:>4}  {k}")
    return out


def q10(led, rs):
    """4 类知识库各有多少条、缺什么、谁负责？"""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from kb_materials_lark import CATEGORIES, MATERIALS
    out = []
    ok = sum(1 for m in MATERIALS if m["可读性"] == "ok")
    out.append(f"材料收集 {len(MATERIALS)} 条：可读 {ok} / 不可读 {len(MATERIALS)-ok}")
    out.append("")
    for c in CATEGORIES:
        out.append(f"── {c['知识库']}  【{c['状态']}】")
        out.append(f"   负责人：{c['负责人']}")
        out.append(f"   现有：  {c['本地现有条目']}")
        out.append(f"   缺口：  {c['缺口说明']}")
    return out


QUESTIONS = [
    ("多少条在跑、来自哪些系统", q1),
    ("哪些逾期、逾期多久", q2),
    ("每个品线压了多少、哪条最紧", q3),
    ("每个负责人手上多少条", q4),
    ("哪些需求跨系统重复", q5),
    ("哪些已完成但没有产出物", q6),
    ("哪些卡在同一状态超过阈值", q7),
    ("哪些需求有证据、哪些零证据", q8),
    ("哪些需求类型可规则化", q9),
    ("4 类知识库各有多少、缺什么、谁负责", q10),
]


def main():
    want = None
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        want = int(args[0])
    led, rs = load_all()

    print(f"═══ 需求知识库 · 黄金问题（快照 {led['snapshot_id']}）═══\n")
    sections = []
    for i, (name, fn) in enumerate(QUESTIONS, 1):
        if want and i != want:
            continue
        lines = fn(led, rs)
        print(f"Q{i}. {name}")
        for l in lines:
            print(f"   {l}")
        print()
        sections.append((i, name, lines))

    if "--md" in sys.argv:
        md = ["# 需求知识库 · 查询手册", "",
              f"> 快照 `{led['snapshot_id']}`　台账 {len(rs)} 条",
              "> 每条问题配一条可复现命令：`python3 tools/kb_query.py <N>`", ""]
        for i, name, lines in sections:
            md.append(f"## Q{i}. {name}")
            md.append("")
            md.append(f"```bash\npython3 tools/kb_query.py {i}\n```")
            md.append("")
            md.append("```")
            md.extend(lines)
            md.append("```")
            md.append("")
        # 预算：每题一行摘要
        md.append("## 一页纸速查")
        md.append("")
        md.append("| # | 问题 | 一句话答案 |")
        md.append("|---|---|---|")
        for i, name, lines in sections:
            md.append(f"| {i} | {name} | {lines[0][:70]} |")
        md.append("")
        open(MANUAL, "w", encoding="utf-8").write("\n".join(md))
        print(f"→ {os.path.relpath(MANUAL, load.REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
