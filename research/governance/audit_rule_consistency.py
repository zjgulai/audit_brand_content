#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规则库交叉一致性检验（21 条规则）
—— 回答：规则库内部是否存在自相矛盾、语义重叠、通道不一致

四类检验：
  T1 关键词重叠：两条规则的检测关键词是否有交集（潜在双重判定）
  T2 豁免词 vs 检测词：某条的豁免词是否落在另一条的检测词内（真矛盾）
  T3 正则 vs 关键词：正则能否匹配该规则自己的关键词（通道一致性）
  T4 边界类型 vs 风险等级：两列是否一一对应（冗余编码）

只读。输出到 stdout。
"""
import re
import sys
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
PRD = ROOT / "PRD" / "内容治理需求文档.md"

SENT = "\x00P\x00"


def split_md_row(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip().replace(SENT, "|") for c in s.replace("\\|", SENT).split("|")]


def grab(lines, marker):
    st = next(i for i, l in enumerate(lines) if l.startswith(marker))
    hi = next(i for i in range(st, st + 10) if lines[i].strip().startswith("|"))
    h = split_md_row(lines[hi])
    out = []
    i = hi + 2
    while i < len(lines) and lines[i].strip().startswith("|"):
        out.append(split_md_row(lines[i]))
        i += 1
    return h, out


def norm_terms(s):
    """把逗号分隔的词表拆成规范化集合。"""
    if not s:
        return set()
    parts = re.split(r"[,，、;；]", s)
    return {p.strip().lower() for p in parts if p.strip()}


def main():
    lines = PRD.read_text(encoding="utf-8").split("\n")
    hdr, rows = grab(lines, "## 表：品线内容边界规则库")
    col = {h: i for i, h in enumerate(hdr)}

    def g(row, name):
        j = col.get(name)
        return row[j].strip() if j is not None and j < len(row) else ""

    rules = []
    for r in rows:
        rid = g(r, "规则编号")
        rules.append({
            "id": rid,
            "type": g(r, "边界类型"),
            "risk": g(r, "风险等级"),
            "kw": norm_terms(g(r, "检测关键词")),
            "ex": norm_terms(g(r, "豁免词")),
            "rx": g(r, "正则表达式"),
            "content": g(r, "边界内容"),
        })

    print("=" * 78)
    print("规则库交叉一致性检验")
    print("=" * 78)
    print(f"\n参与检验的规则：{len(rules)} 条\n")

    fail = 0

    # ---------------------------------------------------------- T1 关键词重叠
    print("=" * 78)
    print("T1｜关键词重叠：两条规则的检测关键词有交集 → 同一条文案会被判两次")
    print("=" * 78)
    print()
    overlaps = []
    for i, a in enumerate(rules):
        for b in rules[i + 1:]:
            inter = a["kw"] & b["kw"]
            if inter:
                overlaps.append((a["id"], b["id"], inter))
    if overlaps:
        print("| 规则 A | 规则 B | 交集关键词 | 交集大小 |")
        print("|---|---|---|---:|")
        for a, b, inter in sorted(overlaps, key=lambda x: -len(x[2])):
            shown = ", ".join(sorted(inter)[:8])
            if len(inter) > 8:
                shown += f" …（共 {len(inter)}）"
            print(f"| {a} | {b} | {shown} | {len(inter)} |")
    else:
        print("（无重叠）")
    print()

    # ------------------------------------------------- T2 豁免词 vs 他条检测词
    print("=" * 78)
    print("T2｜豁免词 vs 检测词：一条的豁免词落在另一条的检测词内 → 真·自相矛盾")
    print("=" * 78)
    print()
    print("判据：若 X 条把词 W 列为「豁免」（本条不适用），而 Y 条把 W 列为「检测」（应判险），")
    print("      则同一个 W 会同时触发「不判」与「判」两条结论。")
    print()
    print("**判据适用范围（重要）**：『安全词』行的 `边界类型` = `安全词白名单`，")
    print("其 `边界内容` 声明为「客观功能/真实认证关键词（正面提示，不参与降级）」——")
    print("它是一个**白名单，不做判险**。因此它不能作为 T2 的『检测方』，")
    print("否则会把「规则坦白说这些词是安全的」误报成「规则自相矛盾」。")
    print("→ 检测方只取真正的判险规则（边界类型 ≠ 安全词白名单）。")
    print()
    # 分离白名单
    risk_rules = [r for r in rules if r["type"] != "安全词白名单"]
    print(f"判险规则：{len(risk_rules)} 条；白名单：{len(rules) - len(risk_rules)} 条")
    print()
    conflicts = []
    for a in risk_rules:
        for b in risk_rules:
            if a["id"] == b["id"]:
                continue
            inter = a["ex"] & b["kw"]
            if inter:
                conflicts.append((a["id"], b["id"], inter))
    if conflicts:
        print("| 豁免方（不判） | 检测方（判险） | 冲突词 | 后果 |")
        print("|---|---|---|---|")
        for a, b, inter in sorted(conflicts, key=lambda x: -len(x[2])):
            shown = ", ".join(f"`{w}`" for w in sorted(inter)[:6])
            if len(inter) > 6:
                shown += f" …（共 {len(inter)}）"
            print(f"| **{a}** | **{b}** | {shown} | {a} 说这些词命中时本条不适用，但 {b} 说这些词应判险 |")
        fail += len(conflicts)
    else:
        print("**→ 判险规则之间的 豁免词↔检测词 冲突为 0 组。**")
        print()
        print("（注：R5 曾口头指出「安全词表 `reduces pain`/`less pain` 与 H07 矛盾」。")
        print(" 经本检验：该矛盾存在于 **H07↔安全词** 之间（见 T1），而不是在两条判险规则之间。）")
        print()
        print("★★ 2026-09-16 更正：本处原写「按白名单『不参与降级』的定义，它不会造成运行时的双重结论」。")
        print("   **这句话是错的，且它正是事故得以存续的原因。** 实测三条：")
        print("   ① 白名单**确实**参与降级 —— 26 词中有 10 个被人工抄进 H06/H07/M01/M02 的 `豁免词`：")
        print("        H06 ← FDA cleared/registered；M01 ← low noise/quiet mode/low-decibel；")
        print("        M02 ← suction level/adjustable suction；H07 ← comfort/gentle")
        print("      白名单**唯一**的作用机制就是喂这些通道。若真『不参与降级』，26 词全是死重。")
        print("      所以它行内自称的「不参与降级」与它实际被使用的方式互相矛盾。")
        print("   ② 损害不是「运行时双重结论」，而是**词表污染**：任何 `SELECT 检测关键词`")
        print("      都会把这 26 个白名单词拼进违规词表。`tools/offline_replay.py` 正是如此，")
        print("      跑出 56/57 条误报 —— 已发布的「误报 55.9%」是假数字（修正后 4.9%）。")
        print("   ③ 该行 disposition 若为 auto_pass 而某判险规则同时命中同一个词，")
        print("      运行时的确会得到两个相反结论 —— 抄漏的 reduces pain/less pain 即此种。")
        print("   → 处置：白名单已**物理分离**为独立表（skeleton/whitelist-v1.json，ADR-0008），")
        print("     判定词表改为从独立来源装载，并在使用点硬断言 W1 隔离（违反即 exit 3）。")
    print()

    # ------------------------------------------- T2b 同一条内 豁免词 vs 检测词
    print("=" * 78)
    print("T2b｜同一条规则内：豁免词与自己的检测词交集")
    print("=" * 78)
    print()
    selfc = []
    for a in rules:
        inter = a["ex"] & a["kw"]
        if inter:
            selfc.append((a["id"], inter))
    if selfc:
        print("| 规则 | 自相矛盾的词 |")
        print("|---|---|")
        for rid, inter in selfc:
            print(f"| {rid} | {', '.join(f'`{w}`' for w in sorted(inter))} |")
        fail += len(selfc)
    else:
        print("（无）")
    print()

    # ------------------------------------------------- T3 正则 vs 自己的关键词
    print("=" * 78)
    print("T3｜检测通道完整性：哪些关键词『真的会漏』")
    print("=" * 78)
    print()
    print("**原口径（v1）过粗**：曾统计出 413 个关键词「正则匹配不到」。")
    print("但正则本就不需要逐字覆盖关键词——它通常用 `\\w*` / `[^.!?|]*` 覆盖词形变化与语序。")
    print("因此「匹配不到」不等于「会漏」。真正的问题是两类：")
    print()
    print("  **(i) 无正则的判险规则**：整条规则只有关键词通道，无第二道防线")
    print("  **(ii) 有正则但形态上不可能匹配**：典型是中文词进了英文正则")
    print()
    noregex = [r for r in rules if not r["rx"] and r["type"] != "安全词白名单"]
    print(f"**(i) 无正则的判险规则：{len(noregex)} 条**")
    print()
    print("| 规则 | 边界类型 | 关键词数 |")
    print("|---|---|---:|")
    tot_nr = 0
    for r in noregex:
        tot_nr += len(r["kw"])
        print(f"| {r['id']} | {r['type']} | {len(r['kw'])} |")
    print(f"| **合计** | | **{tot_nr}** |")
    print()

    print("**(ii) 有正则，但中文关键词不可能被英文正则匹配**")
    print()
    print("| 规则 | 中文关键词 | 数量 |")
    print("|---|---|---:|")
    tot_zh = 0
    zh_map = {}
    for r in rules:
        if not r["rx"]:
            continue
        try:
            cre = re.compile(r["rx"], re.I)
        except re.error:
            continue
        zh = [w for w in r["kw"] if re.search(r"[\u4e00-\u9fff]", w) and not cre.search(w)]
        if zh:
            zh_map[r["id"]] = zh
            tot_zh += len(zh)
            print(f"| {r['id']} | {', '.join(f'`{w}`' for w in sorted(zh)[:8])}"
                  f"{' …' if len(zh) > 8 else ''} | {len(zh)} |")
    print(f"| **合计** | | **{tot_zh}** |")
    print()

    # ------------------------------------------------- 关键：这些词真的出现过吗
    print("=" * 78)
    print("T3b｜关键检验：这些『会漏』的关键词，**真的在生产文案里出现过吗**")
    print("=" * 78)
    print()
    print("光说「正则匹配不到」不等于会漏——要看这个词有没有真的出现。")
    print("语料：291 条广告文案的 Primary Text + Headline + 广告名称 + 广告系列 + 命中片段。")
    print()
    try:
        _, rec_rows = grab(lines, "## 表：广告文案明细")
        rcol = {h: i for i, h in enumerate(_)} if False else None
    except StopIteration:
        rec_rows = []
    # grab 返回 (header, rows)，上面写法有误，重新取
    rec_hdr, rec_rows = grab(lines, "## 表：广告文案明细")
    rec_col = {h: i for i, h in enumerate(rec_hdr)}

    def rgv(row, name):
        j = rec_col.get(name)
        return row[j].strip() if j is not None and j < len(row) else ""

    chunks = []
    for row in rec_rows:
        for f in ["Primary Text", "Headline", "广告名称", "广告系列Campaign", "命中片段"]:
            v = rgv(row, f)
            if v:
                chunks.append(v)
    CORPUS = " \n ".join(chunks).lower()

    gaps = []
    for r in noregex:
        for w in r["kw"]:
            if len(w) >= 3 and w in CORPUS:
                gaps.append((r["id"], w, False))
    for rid, zh in zh_map.items():
        for w in zh:
            if w in CORPUS:
                gaps.append((rid, w, True))

    if gaps:
        print("| 规则 | 在语料中出现过的关键词 | 该规则有正则? |")
        print("|---|---|---|")
        seen = set()
        for rid, w, has_rx in gaps:
            if (rid, w) in seen:
                continue
            seen.add((rid, w))
            tag = "是（但匹配不到）" if has_rx else "**否**"
            print(f"| {rid} | `{w}` | {tag} |")
        print()
        print(f"共 **{len(seen)}** 个「会漏且真的出现过」的关键词。")
    else:
        print("**→ 这些关键词在 291 条广告文案语料中均未出现。**")
        print()
        print("  即：虽然存在通道缺口，但**当前样本尚未暴露它**。")
        print("  这解释了为什么它至今没有被发现 —— 而这也正是它危险的地方：")
        print("  缺口已经存在，样本还没走到那里。")
    print()
    print(f"（无正则规则的关键词总数：{tot_nr}；中文词无法被英文正则匹配的总数：{tot_zh}）")
    print()

    # ------------------------------------------------- T4 边界类型 vs 风险等级
    print("=" * 78)
    print("T4｜边界类型 vs 风险等级：两列是否一一对应（冗余编码）")
    print("=" * 78)
    print()
    pair = defaultdict(set)
    rev = defaultdict(set)
    for a in rules:
        pair[a["type"]].add(a["risk"])
        rev[a["risk"]].add(a["type"])
    print("| 边界类型 | 对应的风险等级 |")
    print("|---|---|")
    for k, v in pair.items():
        print(f"| {k} | {', '.join(sorted(v))} |")
    print()
    print("| 风险等级 | 对应的边界类型 |")
    print("|---|---|")
    for k, v in rev.items():
        print(f"| {k} | {', '.join(sorted(v))} |")
    print()
    bij = all(len(v) == 1 for v in pair.values()) and all(len(v) == 1 for v in rev.values())
    same = len(pair) == len(rev) == len({(a["type"], a["risk"]) for a in rules})
    if bij and same:
        print("→ **两列构成双射（一一对应），互为冗余编码。**")
        print("  承载同一信息的两个字段，任一列的取值都能推出另一列。")
    else:
        print("→ 两列并非严格一一对应，需人工判读。")
    print()

    # ---------------------------------------------------------------- 汇总
    print("=" * 78)
    print("汇总")
    print("=" * 78)
    print()
    print("| 检验 | 发现数 |")
    print("|---|---:|")
    print(f"| T1 规则间关键词重叠 | {len(overlaps)} 对 |")
    print(f"| T2 判险规则间 豁免词↔检测词 冲突 | {len(conflicts)} 组 |")
    print(f"| T2b 同规则内 豁免词↔检测词 冲突 | {len(selfc)} 条 |")
    print(f"| T3(i) 无正则的判险规则 | {len(noregex)} 条（{tot_nr} 个关键词只有单通道） |")
    print(f"| T3(ii) 中文关键词无法被英文正则匹配 | {tot_zh} 个 |")
    print(f"| T3b 「会漏且真的出现过」的关键词 | {len(seen) if gaps else 0} 个 |")
    print(f"| T4 边界类型↔风险等级 | {'双射（冗余）' if (bij and same) else '非双射'} |")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
