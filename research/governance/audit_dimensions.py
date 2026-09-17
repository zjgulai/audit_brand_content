#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用他们自己的 291 条数据，检验「国家 × 品类 × 平台 × 内容类型」这四个维度
**是否真的会改变判定结果**。

方法：对每个维度，看同一类风险在不同维度取值下的命中率是否显著不同。
如果一条规则在所有国家/平台的命中率都一样，那这个维度对这条规则就不构成维度。

这比「讨论维度模型应该怎么设计」有力，因为它用的是他们自己的数据。

用法：python3 research/governance/audit_dimensions.py
"""
import re, sys, math
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_records as arc


def chi2_p(obs):
    """2xk 列联表的卡方检验，返回 (chi2, df, 粗略 p)。只用于量级判断。"""
    rows = len(obs)
    cols = len(obs[0]) if rows else 0
    if rows < 2 or cols < 2:
        return 0.0, 0, 1.0
    rt = [sum(r) for r in obs]
    ct = [sum(obs[i][j] for i in range(rows)) for j in range(cols)]
    n = sum(rt)
    if n == 0:
        return 0.0, 0, 1.0
    chi = 0.0
    for i in range(rows):
        for j in range(cols):
            e = rt[i] * ct[j] / n
            if e > 0:
                chi += (obs[i][j] - e) ** 2 / e
    df = (rows - 1) * (cols - 1)
    # 用 Wilson–Hilferty 近似算 p
    if df == 0:
        return chi, 0, 1.0
    z = ((chi / df) ** (1 / 3) - (1 - 2 / (9 * df))) / math.sqrt(2 / (9 * df))
    p = 0.5 * math.erfc(z / math.sqrt(2))
    return chi, df, p


def main():
    _, ads = arc.load_table("广告文案明细")

    # 从 campaign 名恢复真实市场（投放地区 字段 216/291 是「其他」，不可用）
    def market(a):
        c = (a.get("广告系列Campaign", "") or "") + " " + (a.get("广告名称", "") or "")
        for pat, name in [("欧洲DE", "德国"), ("欧洲FR", "法国"), ("欧洲ES", "西班牙"),
                          ("欧洲IT", "意大利"), ("欧洲UK", "英国"), ("欧洲PL", "波兰")]:
            if pat in c:
                return name
        if re.search(r"\bUS\b", c):
            return "美国"
        if re.search(r"\bCA\b", c):
            return "加拿大"
        if "欧洲" in c:
            return "欧洲(未细分)"
        return "(不可辨)"

    def ruleset(a):
        return set(re.findall(r"\b[HMU]\d{2}\b", a.get("命中规则") or ""))

    for a in ads:
        a["_market"] = market(a)
        a["_rules"] = ruleset(a)
        # 内容模态
        pt = (a.get("Primary Text") or "").strip()
        hl = (a.get("Headline") or "").strip()
        at = a.get("广告类型", "")
        if "视频" in at:
            a["_modal"] = "视频"
        elif "图片" in at:
            a["_modal"] = "图片"
        elif pt or hl:
            a["_modal"] = "文本"
        else:
            a["_modal"] = "(无素材信息)"

    DIMS = ["_market", "平台", "文案语种", "_modal", "品线"]
    RULES = sorted({r for a in ads for r in a["_rules"]})
    RULES = [r for r in RULES if sum(1 for a in ads if r in a["_rules"]) >= 3]

    print("=" * 92)
    print("维度有效性检验：同一规则在不同维度取值下的命中率（命中数/该取值下的记录数）")
    print("=" * 92)

    summary = {}
    for dim in DIMS:
        print()
        print(f"── 维度：{dim} ──")
        vals = [v for v, c in Counter(a[dim] for a in ads).most_common() if c >= 5]
        vals = [v for v in vals if v != "(不可辨)"][:7]
        if len(vals) < 2:
            print("   取值不足，跳过")
            continue
        base = {v: sum(1 for a in ads if a[dim] == v) for v in vals}
        print(f"   {'规则':<7}" + "".join(f"{v[:8]:>11}" for v in vals) + f"{'  卡方p':>9}  判定")
        rows_out = []
        for rid in RULES:
            obs = [[sum(1 for a in ads if a[dim] == v and rid in a["_rules"]),
                    base[v] - sum(1 for a in ads if a[dim] == v and rid in a["_rules"])]
                   for v in vals]
            chi, df, p = chi2_p(obs)
            rates = "".join(f"{obs[i][0]/base[v]*100:>10.0f}%" for i, v in enumerate(vals))
            verdict = "★ 有差异" if p < 0.05 else "· 无差异"
            print(f"   {rid:<7}{rates}{p:>9.3f}  {verdict}")
            rows_out.append((rid, p, [obs[i][0] / base[v] for i, v in enumerate(vals)]))
        sig = [r for r in rows_out if r[1] < 0.05]
        summary[dim] = (len(rows_out), len(sig), [r[0] for r in sig])
        print(f"   → {len(sig)}/{len(rows_out)} 条规则在该维度上存在显著差异"
              f"{'：' + ', '.join(r[0] for r in sig) if sig else ''}")

    print()
    print("=" * 92)
    print("汇总：哪个维度真的改变了判定？")
    print("=" * 92)
    print(f"  {'维度':<10}{'检验规则数':>10}{'显著差异':>10}   显著的具体规则")
    for dim in DIMS:
        if dim not in summary:
            continue
        n, s, which = summary[dim]
        print(f"  {dim:<10}{n:>10}{s:>10}   {', '.join(which) if which else '—'}")

    # ---------- 语种：同一条规则的不同语种表面形态 ----------
    print()
    print("=" * 92)
    print("语种维度：同一条规则在不同语种下的实际命中词（这是维度带来的真实差异）")
    print("=" * 92)
    per_rule_lang = defaultdict(lambda: defaultdict(set))
    for a in ads:
        fr = a.get("命中片段") or ""
        for chunk in fr.split("/"):
            m = re.match(r"^\s*([HMU]\d{2}|安全词)\s*[:：]\s*(.+)$", chunk.strip())
            if not m:
                continue
            rid, txt = m.group(1), m.group(2)
            for term in re.split(r"\s*,\s*", txt):
                term = term.strip()
                if term and term != "EMPTY":
                    per_rule_lang[rid][a.get("文案语种", "")].add(term)
    for rid in ["H07", "H02", "M01", "M02", "M05", "U03"]:
        if rid not in per_rule_lang:
            continue
        print(f"\n  {rid}:")
        for lang, terms in sorted(per_rule_lang[rid].items()):
            print(f"    {lang or '(空)':<6} {', '.join(sorted(terms))}")

    # ---------- 维度组合的实际占用率 ----------
    print()
    print("=" * 92)
    print("维度组合的占用率：四维笛卡尔积里，实际有数据的格子有多少")
    print("=" * 92)
    markets = sorted({a["_market"] for a in ads if a["_market"] != "(不可辨)"})
    plats = sorted({a["平台"] for a in ads if a["平台"]})
    modals = sorted({a["_modal"] for a in ads if a["_modal"] != "(无素材信息)"})
    langs = sorted({a.get("文案语种", "") for a in ads if a.get("文案语种")})
    cats = sorted({a.get("品线", "") for a in ads if a.get("品线")})
    print(f"  实际出现的取值：")
    print(f"    市场   {len(markets)}: {markets}")
    print(f"    平台   {len(plats)}: {plats}")
    print(f"    语种   {len(langs)}: {langs}")
    print(f"    模态   {len(modals)}: {modals}")
    print(f"    品类   {len(cats)}: {cats}")
    full = len(markets) * len(plats) * len(modals) * len(langs) * len(cats)
    occ = len({(a["_market"], a["平台"], a["_modal"], a.get("文案语种"), a.get("品线"))
               for a in ads if a["_market"] != "(不可辨)"})
    print()
    print(f"  五维笛卡尔积格子数（仅按现有取值）：{full}")
    print(f"  实际有记录的格子数：              {occ}")
    print(f"  占用率：                          {occ/full:.1%}")
    print(f"  规则条数：                        21")
    print(f"  若按 PRD 规划的扩张（+婴幼儿品线、+美国市场、+Amazon/TikTok 平台）：")
    print(f"    市场 8 × 平台 5 × 语种 6 × 模态 3 × 品类 5 = {8*5*6*3*5} 格 vs 规则 21 条")

    # ---------- 内容模态：命中率差异 ----------
    print()
    print("=" * 92)
    print("模态维度的真相：引擎在不同模态上的可见性")
    print("=" * 92)
    for m in ["文本", "图片", "视频", "(无素材信息)"]:
        sub = [a for a in ads if a["_modal"] == m]
        if not sub:
            continue
        hastxt = sum(1 for a in sub if (a.get("Primary Text") or "").strip() or (a.get("Headline") or "").strip())
        hit = sum(1 for a in sub if a["_rules"])
        print(f"  {m:<10}{len(sub):>5} 条   有文案 {hastxt:>3} ({hastxt/len(sub):>5.1%})   "
              f"有命中 {hit:>3} ({hit/len(sub):>5.1%})")


if __name__ == "__main__":
    main()
