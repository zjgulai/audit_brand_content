#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对 PRD 里现存的「品线内容边界规则库（21 条）」做可执行一致性审计。

不是读文档下判断，而是把规则表当数据跑：
  1. 规则自带的正则，能不能命中规则自己声明的「检测关键词」？
  2. 规则自带的「豁免词」，会不会被规则自己的正则捕获？（= 规则自己制造误报）
  3. 291 条在跑记录里，每条规则实际命中多少次？哪些规则从未命中？
  4. 「适用产品」字段与实际出现的型号是否一致？
  5. 规则族（H/M/U/安全词）与「风险等级」「边界类型」是否一一对应？

用法：python3 research/governance/audit_rule_table.py
"""
import re
import sys
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRD = ROOT / "PRD" / "内容治理需求文档.md"

RULE_HDR = "## 表：品线内容边界规则库"
AD_HDR = "## 表：广告文案明细"
SELL_HDR = "## 表：W1卖点表达边界"
SUG_HDR = "## 表：风险文案改写建议库"


def split_md_row(line):
    """按未转义的 | 切分 markdown 表格行；\\| 还原为 |。"""
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells, buf, i = [], [], 0
    while i < len(line):
        c = line[i]
        if c == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if c == "|":
            cells.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    cells.append("".join(buf))
    return [c.strip() for c in cells]


def load_tables():
    """返回 {章节标题: (表头, [行...])}。"""
    lines = PRD.read_text(encoding="utf-8").splitlines()
    tables, cur, rows, hdr = {}, None, [], None
    for ln in lines:
        if ln.startswith("## 表："):
            if cur and hdr:
                tables[cur] = (hdr, rows)
            cur, rows, hdr = ln[len("## 表："):].strip(), [], None
            continue
        if ln.startswith("#"):
            if cur and hdr:
                tables[cur] = (hdr, rows)
            cur, rows, hdr = None, [], None
            continue
        if cur is not None and ln.startswith("|"):
            cells = split_md_row(ln)
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c != ""):
                continue  # 分隔行
            if hdr is None:
                hdr = cells
            else:
                rows.append(cells)
    if cur and hdr:
        tables[cur] = (hdr, rows)
    return tables


def to_dicts(hdr, rows):
    out = []
    for r in rows:
        if len(r) != len(hdr):
            d = dict(zip(hdr, r))
            d["__COLCOUNT__"] = len(r)
            out.append(d)
        else:
            out.append(dict(zip(hdr, r)))
    return out


def load_rules():
    """解析 21 条规则 + 6 条正则/豁免词字段。"""
    lines = PRD.read_text(encoding="utf-8").splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith(RULE_HDR))
    hdr, rows = None, []
    for ln in lines[start + 1:]:
        if ln.startswith("#"):
            break
        if ln.startswith("|"):
            cells = split_md_row(ln)
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c != ""):
                continue
            if hdr is None:
                hdr = cells
            else:
                rows.append(cells)
    rules = []
    for r in rows:
        d = dict(zip(hdr, r))
        if len(r) != len(hdr):
            d["__COLCOUNT__"] = len(r)
        rules.append(d)
    return hdr, rules


def keywords_of(rule):
    raw = rule.get("检测关键词", "") or ""
    return [k.strip() for k in raw.split(",") if k.strip()]


def split_patterns(raw):
    """把规则的正则字段切成多条 pattern。

    字段用 ", " 分隔多条正则，但**单条正则内部也会出现逗号**（如 `[^.!?|,]*leak`）。
    因此不能裸 split(",")，必须在括号/字符类深度为 0 时才切。
    """
    raw = (raw or "").strip()
    if not raw:
        return []
    parts, buf, depth, in_class, i = [], [], 0, False, 0
    while i < len(raw):
        c = raw[i]
        if c == "\\" and i + 1 < len(raw):          # 转义：整对吃掉
            buf.append(c); buf.append(raw[i + 1]); i += 2; continue
        if in_class:
            if c == "]":
                in_class = False
            buf.append(c); i += 1; continue
        if c == "[":
            in_class = True; buf.append(c); i += 1; continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth = max(0, depth - 1)
        if c == "," and depth == 0:
            parts.append("".join(buf)); buf = []; i += 1; continue
        buf.append(c); i += 1
    parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def compile_rule_regex(raw):
    """规则里的正则用 | 表示交替（飞书里 \\| 转义后被还原）；同时兼容 ^ $ 等。"""
    pats = []
    for p in split_patterns(raw):
        try:
            pats.append(re.compile(p, re.IGNORECASE))
        except re.error as e:
            pats.append(("__BAD__", str(e), p))
    return pats or None


def main():
    hdr, rules = load_rules()
    report = {}
    print("=" * 78)
    print("规则表结构")
    print("=" * 78)
    print(f"表头 {len(hdr)} 列：{' | '.join(hdr)}")
    print(f"规则条数：{len(rules)}")
    bad = [r.get("规则编号", "?") for r in rules if "__COLCOUNT__" in r]
    print(f"列数不符的行：{bad if bad else '无'}")

    # ---------- 1. 正则 vs 检测关键词 ----------
    print()
    print("=" * 78)
    print("[1] 规则自带的正则，能否命中规则自己声明的检测关键词")
    print("=" * 78)
    print(f"{'规则':<8}{'关键词数':>8}{'正则条数':>10}{'被正则覆盖':>12}{'覆盖率':>10}  未覆盖示例")
    cov_rows = []
    for r in rules:
        rid = r.get("规则编号", "?")
        kws = keywords_of(r)
        pats = compile_rule_regex(r.get("正则表达式", ""))
        good = [p for p in (pats or []) if not isinstance(p, tuple)]
        if not kws:
            continue
        if not good:
            print(f"{rid:<8}{len(kws):>8}{0:>10}{'—':>12}{'—':>10}  (无正则)")
            cov_rows.append((rid, len(kws), 0, 0, 0.0))
            continue
        covered = [k for k in kws if any(p.search(k) for p in good)]
        miss = [k for k in kws if k not in covered]
        rate = len(covered) / len(kws)
        cov_rows.append((rid, len(kws), len(good), len(covered), rate))
        sample = ", ".join(miss[:4]) + (" …" if len(miss) > 4 else "")
        print(f"{rid:<8}{len(kws):>8}{len(good):>10}{len(covered):>12}{rate:>9.0%}  {sample}")

    # ---------- 2. 豁免词会不会被自己的正则抓到 ----------
    print()
    print("=" * 78)
    print("[2] 豁免词会不会被规则自己的正则捕获（规则自己制造的误报）")
    print("=" * 78)
    selfcatch = []
    for r in rules:
        rid = r.get("规则编号", "?")
        pats = compile_rule_regex(r.get("正则表达式", ""))
        good = [p for p in (pats or []) if not isinstance(p, tuple)]
        ex = [w.strip() for w in (r.get("豁免词", "") or "").split(",") if w.strip()]
        if not good or not ex:
            continue
        hit = [w for w in ex if any(p.search(w) for p in good)]
        if hit:
            selfcatch.append((rid, hit, len(ex)))
            print(f"  ✗ {rid}: {len(hit)}/{len(ex)} 个豁免词被本规则正则命中 → {hit[:6]}")
    if not selfcatch:
        print("  无")
    else:
        print()
        print(f"  合计 {len(selfcatch)} 条规则存在「正则过宽、靠豁免词打补丁」的结构")

    # ---------- 3. 291 条记录里的实际命中 ----------
    print()
    print("=" * 78)
    print("[3] 291 条在跑记录里的实际命中分布")
    print("=" * 78)
    ads = None
    for name, (h, rws) in load_tables().items():
        if name.startswith("广告文案明细"):
            ads = to_dicts(h, rws)
            break
    if ads is None:
        print("  未找到广告明细表")
    else:
        print(f"  记录数：{len(ads)}")
        colset = {len(a) for a in ads}
        print(f"  每行实际列数集合：{sorted(colset)}（表头 {len(ads[0])} 列）")
        # 字段实际命名与表头是否一致
        hits = Counter()
        lvl = Counter()
        for a in ads:
            for tok in re.findall(r"\b([HMU]\d{2})\b", a.get("命中规则", "") or ""):
                hits[tok] += 1
            lvl[a.get("风险等级", "").strip()] += 1
        declared = {r.get("规则编号", "") for r in rules}
        print()
        print("  风险等级分布：")
        for k, v in lvl.most_common():
            print(f"    {k or '(空)':<14}{v:>5}")
        print()
        print(f"  {'规则':<8}{'命中次数':>8}   是否在规则表中声明")
        never = []
        for rid in [r.get("规则编号", "") for r in rules]:
            n = hits.get(rid, 0)
            print(f"  {rid:<8}{n:>8}   {'✓' if rid in declared else '✗'}")
            if n == 0:
                never.append(rid)
        ghost = sorted(set(hits) - declared)
        print()
        print(f"  从未被命中的规则（{len(never)} 条）：{never}")
        print(f"  记录里出现但规则表中不存在的编号：{ghost if ghost else '无'}")

    # ---------- 4. 适用产品 vs 实际型号 ----------
    print()
    print("=" * 78)
    print("[4] 「适用产品」字段 vs 其余表里实际出现的型号")
    print("=" * 78)
    prod_field = Counter(r.get("适用产品", "") for r in rules)
    for k, v in prod_field.items():
        print(f"  规则表中「适用产品」取值 {k!r} → {v} 条规则")
    tabs = load_tables()
    models = Counter()
    for r in rules:
        pass
    for name, (h, rws) in tabs.items():
        if name.startswith("风险文案改写建议库"):
            for d in to_dicts(h, rws):
                for m in re.findall(r"W1|M5 Smart|M5|M6|M9|Air ?1|S12 Pro|V1 Pro", d.get("适用型号", "")):
                    models[m.replace(" ", " ")] += 1
    print()
    print("  改写建议库的「适用型号」实际取值：")
    for k, v in models.most_common():
        print(f"    {k:<12}{v:>4}")
    rule_models = set(re.findall(r"W1|M5|M6|M9|Air ?1", list(prod_field)[0] if prod_field else ""))
    used_models = set(models)
    print()
    print(f"  规则表声明的型号集合：{sorted(rule_models)}")
    print(f"  改写库实际用到的型号：{sorted(used_models)}")
    print(f"  ★ 在改写库出现但规则表未声明：{sorted(used_models - rule_models)}")

    # ---------- 5. 三个分类字段的交叉表 ----------
    print()
    print("=" * 78)
    print("[5] 规则族（编号前缀） × 边界类型 × 风险等级 是否一一对应")
    print("=" * 78)
    cross = defaultdict(Counter)
    for r in rules:
        rid = r.get("规则编号", "?")
        pre = "安全词" if rid.startswith("安全词") else rid[:1]
        cross[pre][(r.get("边界类型", ""), r.get("风险等级", ""))] += 1
    consistent = True
    for pre in sorted(cross):
        combos = cross[pre]
        flag = "✓" if len(combos) == 1 else "✗ 多义"
        if len(combos) != 1:
            consistent = False
        print(f"  前缀 {pre:<6} {flag}  {dict(combos)}")
    if not consistent:
        print()
        print("  ★ 存在同一前缀映射到多个 (边界类型, 风险等级) 组合 → 编号族不是单一分类轴")

    # ---------- 输出 JSON ----------
    report = {
        "rule_count": len(rules),
        "regex_coverage": [
            {"rule": r, "keywords": k, "patterns": p, "covered": c, "rate": round(rt, 4)}
            for (r, k, p, c, rt) in cov_rows
        ],
        "exemption_selfcatch": [{"rule": r, "caught": h, "total": t} for (r, h, t) in selfcatch],
        "never_fired": never if ads else [],
        "ghost_codes": ghost if ads else [],
        "family_consistency": {k: {f"{a} / {b}": v for (a, b), v in c.items()} for k, c in cross.items()},
    }
    out = Path(__file__).resolve().parent / "_evidence" / "rule_table_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"机器可读结果已写入 {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
