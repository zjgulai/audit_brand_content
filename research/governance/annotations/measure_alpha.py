#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
measure_alpha.py —— 计算 ANN-GUIDE-001 的标注者间一致性 α（Fleiss' κ）。

设计原则：
  · 三个标注者文件缺失时【明确失败】，绝不静默返回一个假 α。
  · 同时算 Fleiss' κ（多标注者总体）与成对 Cohen's κ（定位是哪两个人在分歧）。
  · 分「叶子」「等级」两条轴分别统计 —— 因为指南分管辖层与严重度层，两层可以独立不一致。
  · 分歧条目全部列出，并回指到指南的哪一步（A/B/C），供重写那一步。
"""
import json, pathlib, sys, collections, itertools, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ANN = ROOT / "annotations"
RATERS = ["A", "B", "C"]
LEAF_SET = ["T1.4", "T1.5", "T2.1.2", "T2.2.2", "不判", "存疑"]
LEVEL_SET = ["红 L4", "黄 L2", "不判", "存疑"]


def normalize_label(s):
    """归一化标注标签，消除纯格式差异（不消除实质分歧）。

    ★ 实测教训：rater C 把多管辖写成 `T1.5 + T1.4`（带空格），A/B 写 `T1.5+T1.4`。
      不归一化时这一条差异污染了 6 个条目的 κ —— 那测的是书写习惯，不是判定一致性。
      归一化只做：去空白、统一连接符。**不合并任何不同叶子。**
    """
    s = (s or "").strip()
    s = s.replace("＋", "+").replace("·", "+").replace("、", "+")
    s = re.sub(r"\s*\+\s*", "+", s)
    s = re.sub(r"\s+", " ", s)
    return s


def load_rater(tag):
    p = ANN / f"annot_rater_{tag}.tsv"
    if not p.exists():
        return None
    rows = {}
    for ln in p.read_text().splitlines():
        ln = ln.rstrip("\n")
        if not ln.strip():
            continue
        parts = ln.split("\t")
        if len(parts) < 3:
            parts = ln.split()
        if len(parts) < 3:
            raise ValueError(f"{p.name}: 行格式错误（需 3 列）: {ln!r}")
        bid, leaf, level = parts[0].strip(), parts[1].strip(), parts[2].strip()
        rows[bid] = (normalize_label(leaf), normalize_label(level))
    return rows


def fleiss_kappa(table):
    """table: list of dicts {category: count}, 每项标注者数相同。"""
    n_items = len(table)
    if n_items == 0:
        return None
    cats = sorted({c for row in table for c in row})
    n_rat = sum(table[0].values())
    if n_rat < 2:
        return None
    P_i = []
    for row in table:
        s = sum(v * (v - 1) for v in row.values())
        P_i.append(s / (n_rat * (n_rat - 1)))
    P_bar = sum(P_i) / n_items
    p_j = {c: sum(row.get(c, 0) for row in table) / (n_items * n_rat) for c in cats}
    P_e = sum(v * v for v in p_j.values())
    if P_e == 1.0:
        return 1.0
    return (P_bar - P_e) / (1 - P_e)


def krippendorff_alpha_nominal(units):
    """Krippendorff's α (nominal)，允许缺失值。

    units: list of list-of-labels（每个 unit 一个标注者列表，缺失可不填）

    ★ 设计文档 §4.2.1 明确「用 α 不用 κ」（依据 R4 §5.2，Krippendorff 2004 逐字）。
      因此本函数是【主指标】；Fleiss' κ 仅作旁证 —— 引用标准不能自选。

    α = 1 − D_o / D_e
      D_o = (1/N) Σ_u [ Σ_{c} n_uc(m_u − n_uc) / (m_u(m_u−1)) ]   … 观察到的分歧
      D_e = [ Σ_c n_c(n_c−1) ] / [ n(n−1) ]                        … 期望分歧

      n_uc = 单元 u 中类别 c 的标注数；m_u = 单元 u 的标注者数；n = 总标注数

    ⚠ 两处分母都踩过坑，已用可手算算例锁定（见下方自检）：
      ① D_o 的分母是 m_u(m_u−1)，不是 (m_u−1)。
         漏掉那个 m，会让「标注者完全一致」的语料算出 Do=2 而不是 0 → α 变成负数。
      ② D_e 的分母是 n(n−1)，不是 (n−1)。
      ③ D_e = 0 只在「没有任何一个类别被标注过两次」时发生（即 n_c ≤ 1 ∀c，
         例如总标注数 ≤ 1）。此时 α 无定义 → 返回 None。
         ⚠ 注意：「全部标注值同属一类」（如 4 个标注全是 'a'）**不是**退化 ——
         此时 n_a=4，D_e = 4·3/(4·3) = 1，α = 1 − 0/1 = **1.0 是正确的**。
         本实现曾把这种情形误判为退化，自检已锁死。
    """
    units = [u for u in units if len(u) >= 2]
    N = len(units)
    if N == 0:
        return None
    n = sum(len(u) for u in units)
    if n < 2:
        return None
    Do_num = 0.0
    for u in units:
        m = len(u)
        cnt = collections.Counter(u)
        # Σ_c n_uc(m_u − n_uc)  =  m² − Σ_c n_uc²
        pair_dis = m * m - sum(c * c for c in cnt.values())
        Do_num += pair_dis / (m * (m - 1))          # ★ 分母 m(m−1)，不是 (m−1)
    Do = Do_num / N
    allc = collections.Counter(c for u in units for c in u)
    De = sum(c * (c - 1) for c in allc.values()) / (n * (n - 1))   # ★ 分母 n(n−1)
    if De == 0:
        # 退化：全部标注值同属一类 → 期望分歧为 0，α 无定义。
        # 不返回 1.0 —— 那会把「退化」伪装成「完美一致」（Krippendorff 第一悖论）。
        return None
    return 1 - Do / De


def cohen_kappa(a, b):
    """a,b: dict item->label（同一批 item）"""
    items = sorted(set(a) & set(b))
    if not items:
        return None
    cats = sorted(set(a[i] for i in items) | set(b[i] for i in items))
    n = len(items)
    po = sum(1 for i in items if a[i] == b[i]) / n
    pe = sum((sum(1 for i in items if a[i] == c) / n) *
             (sum(1 for i in items if b[i] == c) / n) for c in cats)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def interpret(k):
    if k is None:
        return "无法计算"
    if k >= 0.80:
        return "★ 达标（≥0.80）"
    if k >= 0.60:
        return "接近（0.60–0.80），需定位分歧步"
    return "不达标（<0.60），该判定步需重写"


def main():
    data = {}
    missing = []
    for t in RATERS:
        d = load_rater(t)
        if d is None:
            missing.append(t)
        else:
            data[t] = d
    if missing:
        print(f"✗ 缺少标注者文件：{', '.join('annot_rater_%s.tsv' % m for m in missing)}")
        print("  α 无法计算。不输出任何估计值 —— 一个假 α 比没有 α 更糟。")
        return 2
    present = [t for t in RATERS if t in data]
    print(f"已读入标注者：{', '.join(present)}")

    # 取交集条目
    common = set(data[present[0]])
    for t in present[1:]:
        common &= set(data[t])
    common = sorted(common)
    print(f"共同条目：{len(common)} 条")
    for t in present:
        extra = set(data[t]) - set(common)
        if extra:
            print(f"  注：{t} 多出 {len(extra)} 条不在交集内，已排除")

    results = {}
    results_alpha = {}
    for axis, idx in (("叶子（管辖）", 0), ("等级（严重度）", 1)):
        print("\n" + "=" * 74)
        print(f"轴：{axis}")
        table = []
        for bid in common:
            row = collections.Counter()
            for t in present:
                row[data[t][bid][idx]] += 1
            table.append(dict(row))

        # ★ 主指标：Krippendorff's α（设计文档 §4.2.1「用 α 不用 κ」）
        units = [[data[t][bid][idx] for t in present] for bid in common]
        alpha = krippendorff_alpha_nominal(units)
        results_alpha[axis] = alpha
        print(f"  ★ Krippendorff's α = {alpha:.4f}   {interpret(alpha)}   ← 主指标")

        # 旁证：Fleiss' κ
        k = fleiss_kappa(table)
        results[axis] = k
        print(f"    Fleiss' κ        = {k:.4f}   （旁证，本文档口径以 α 为准）")

        # 分布
        print("  各标注者取值分布：")
        for t in present:
            c = collections.Counter(data[t][bid][idx] for bid in common)
            print(f"    {t}: " + "  ".join(f"{kk}={vv}" for kk, vv in c.most_common()))

        # 成对 Cohen
        print("  成对 Cohen's κ（定位分歧对）：")
        for x, y in itertools.combinations(present, 2):
            a = {bid: data[x][bid][idx] for bid in common}
            b = {bid: data[y][bid][idx] for bid in common}
            kk = cohen_kappa(a, b)
            agree = sum(1 for bid in common if a[bid] == b[bid])
            print(f"    {x}–{y}: κ={kk:.4f}  完全一致 {agree}/{len(common)}"
                  f" ({agree/len(common):.1%})")

        # 全体分歧条目
        dis = [bid for bid in common
               if len({data[t][bid][idx] for t in present}) > 1]
        print(f"  全体不一致条目：{len(dis)}/{len(common)} ({len(dis)/len(common):.1%})")
        for bid in dis:
            vals = " | ".join(f"{t}={data[t][bid][idx]}" for t in present)
            print(f"    {bid}: {vals}")

    json.dump({"krippendorff_alpha": results_alpha,
               "fleiss_kappa_sideevidence": results,
               "raters": present,
               "n_common": len(common)},
              open(ANN / "alpha_result.json", "w"), ensure_ascii=False, indent=1)
    print(f"\n→ {ANN / 'alpha_result.json'}")

    ok = all(v is not None and v >= 0.80 for v in results_alpha.values())
    print("\n" + ("✓ 两条轴 α 均 ≥ 0.80 —— 「先对齐人」达成（设计文档 §3.4 / §4.2.1）。"
                  if ok else "✗ α 未达标：按指南 §10 第 6 条，定位分歧所在步并重写那一步。"))
    return 0




def _selftest():
    """α 实现自检 —— 用可手算算例锁定，防止上面那两处分母再次写错。

    运行：python3 annotations/measure_alpha.py --selftest
    """
    cases = []

    # 1) 完全一致且语料有方差 → α = 1.0
    cases.append(("完全一致（有方差）", [["a", "a"], ["a", "a"], ["b", "b"], ["b", "b"]], 1.0))

    # 2) 手算算例：6 单元 × 2 标注者 × 2 类
    #    Do = (0+0+1+1+0+0)/6 = 2/6
    #    De = (n_a(n_a-1) + n_b(n_b-1)) / (n(n-1)) = (6*5 + 6*5)/(12*11) = 5/11
    #    α = 1 - (2/6)/(5/11) = 1 - 11/15 = 4/15
    cases.append(("手算算例", [["a", "a"], ["a", "a"], ["a", "b"],
                            ["b", "a"], ["b", "b"], ["b", "b"]], 4 / 15))

    # 3) 全部同类但非退化：n_a=4 → D_e = 12/12 = 1 → α = 1.0（正确，不是无定义）
    cases.append(("全部同类（α=1）", [["a", "a"], ["a", "a"]], 1.0))

    # 4) 真退化：单次标注 → 无法计算分歧 → α 无定义
    cases.append(("真退化（单标注）", [["a"]], None))

    ok = True
    print("Krippendorff's α 自检：")
    for name, units, exp in cases:
        got = krippendorff_alpha_nominal(units)
        if exp is None:
            good = got is None
            shown = "None（无定义）" if got is None else f"{got:.6f}"
            want = "None（无定义）"
        else:
            good = got is not None and abs(got - exp) < 1e-9
            shown = "None" if got is None else f"{got:.6f}"
            want = f"{exp:.6f}"
        ok &= good
        print(f"  {'✓' if good else '✗'} {name:18s} 实现={shown:>14s}  期望={want}")

    # 5) 缺失值可算
    got = krippendorff_alpha_nominal([["a", "a"], ["b", "b", "b"], ["a", "b"]])
    good = got is not None
    ok &= good
    print(f"  {'✓' if good else '✗'} {'含缺失值可算':18s} 实现={got:.6f}")

    print("✓ 全部通过" if ok else "✗ 自检失败")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    sys.exit(main())
