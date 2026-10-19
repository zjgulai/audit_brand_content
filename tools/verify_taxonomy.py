#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_taxonomy.py —— `base/taxonomy.py` 的回归与门槛

口径（2026-10-19 定稿）：
  - 主分母 = 512：primary_reviewed ∈ 七轴 且 needs_split=false 且非 policy_fragment；
  - 主断言：512 条 axis_exact ≥ 95%；
  - A：10 条 needs_split 全部返回 SPLIT_REQUIRED + aggregated_rule_needs_split；
  - B：27 条 EDITORIAL → QUALITY_ONLY、quality_tag=EDITORIAL、primary=null；
  - C：25 条 NOT_A_RULE → NOT_A_RULE、record_kind=not_a_rule、primary=null；
  - 碰撞率 = 0；UNKNOWN 率 ≤5%；P0 召回 4/4；
  - 盲测：清空 rule_text/condition 后一致率必须显著下降（≤85%）；
  - 输入构造函数不得读取 `primary_initial` / `primary_reviewed`（只允许验证器用于 gold）。

退出码：0 达标 / 1 有红 / 2 未测（基准读不到）。
"""
from __future__ import annotations

import collections
import inspect
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from base.taxonomy import (
        AXES, classify_rule, detect_collisions, derive_severity, is_editorial,
    )
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.taxonomy: %s" % exc)
    sys.exit(2)

BASELINE = os.path.join(ROOT, "research", "governance",
                        "rules-mece-migration-v1.json")
P0_IDS = {
    "r-242c9de1bf755dca", "r-9961b7d19cdd81e6",
    "r-fbbd2396bcd0c136", "r-6430cde694cab5b7",
}


def _input(rule):
    """构造 classify_rule 输入：只允许规则自身与文本字段。"""
    return {
        "rule_id": rule.get("rule_id"),
        "rule_text": rule.get("rule_text") or "",
        "condition": rule.get("condition") or "",
        "subcategory_original": rule.get("subcategory_original"),
        "category_original": rule.get("category_original"),
        "nature_raw": rule.get("nature_raw"),
        "severity_raw": rule.get("severity_raw"),
        "p_level": rule.get("p_level"),
        "topic": rule.get("topic"),
        "needs_split": bool(rule.get("needs_split")),
    }


def _blind_input(rule):
    x = _input(rule)
    x["rule_text"] = ""
    x["condition"] = ""
    return x


def _category_baseline(rows):
    by = collections.defaultdict(collections.Counter)
    for r in rows:
        by[r.get("category_original")][r["primary_reviewed"]] += 1
    pred = {k: v.most_common(1)[0][0] for k, v in by.items()}
    ok = sum(1 for r in rows
             if pred.get(r.get("category_original")) == r["primary_reviewed"])
    return ok, len(rows)


def main():
    try:
        data = json.load(open(BASELINE, encoding="utf-8"))
        rows = data["assignments"]
    except (OSError, ValueError, KeyError) as exc:
        print("未测：基准读不到（%s）；未测不是通过" % exc, file=sys.stderr)
        return 2

    seven = set(AXES)
    denom = [r for r in rows
             if r.get("primary_reviewed") in seven
             and not r.get("needs_split")
             and not r.get("policy_fragment")]
    print("基准：638 条；主分母（七轴 / 非 split / 非 fragment）= %d" % len(denom))
    print("分布：%r" % dict(collections.Counter(
        r["primary_reviewed"] for r in denom)))
    if len(denom) != 512:
        print("❌ 主分母 %d ≠ 512（基准漂移）" % len(denom), file=sys.stderr)
        return 1

    # 静态断言：输入构造函数与分类器都不得读基准标签/质量标记。
    input_src = inspect.getsource(_input)
    classify_src = inspect.getsource(classify_rule)
    forbidden = ("primary_initial", "primary_reviewed",
                 "quality_tag", "policy_fragment")
    leaked = [x for x in forbidden
              if x in input_src or x in classify_src]
    print("%s 输入构造函数/classify_rule 不读基准标签或质量标记"
          % ("✓" if not leaked else "✗"))

    out = [(classify_rule(_input(r)), r) for r in denom]
    correct = sum(1 for o, r in out if o.get("primary") == r["primary_reviewed"])
    axis_exact = correct / float(len(out)) if out else 0.0
    print("axis_exact（512）= %d/%d = %.4f（阈值 ≥0.95）"
          % (correct, len(out), axis_exact))

    n_cat, n_cat_total = _category_baseline(denom)
    print("朴素基线（按 category 多数轴）= %d/%d = %.4f"
          % (n_cat, n_cat_total, n_cat / float(n_cat_total)))

    # 盲测
    blind_correct = 0
    for r in denom:
        o = classify_rule(_blind_input(r))
        if o.get("primary") == r["primary_reviewed"]:
            blind_correct += 1
    blind = blind_correct / float(len(denom))
    print("盲测（清空文本）= %d/%d = %.4f（要求 ≤0.85）"
          % (blind_correct, len(denom), blind))

    # A/B/C
    split_rows = [r for r in rows if r.get("needs_split")]
    a_ok = all(classify_rule(_input(r)).get("status") == "SPLIT_REQUIRED"
               and classify_rule(_input(r)).get("unknown_reason")
               == "aggregated_rule_needs_split" for r in split_rows)
    print("%s A needs_split %d 条 → SPLIT_REQUIRED/aggregated_rule_needs_split"
          % ("✓" if a_ok else "✗", len(split_rows)))

    ed = [r for r in rows if r.get("primary_reviewed") == "EDITORIAL"]
    ed_hit = sum(1 for r in ed if is_editorial(_input(r)))
    ed_fp = sum(1 for r in rows if r.get("primary_reviewed") != "EDITORIAL"
                and is_editorial(_input(r)))
    b_ok = ed_hit == len(ed)
    print("%s B is_editorial：EDITORIAL 命中 %d/%d；非 EDITORIAL 误报 %d"
          % ("✓" if b_ok else "✗", ed_hit, len(ed), ed_fp))

    # A 优先：needs_split 的聚合规则即使 primary_reviewed=NOT_A_RULE，
    # 也返回 SPLIT_REQUIRED，因此 C 的分母剔除 needs_split。
    nr = [r for r in rows if r.get("primary_reviewed") == "NOT_A_RULE"
          and not r.get("needs_split")]
    c_ok = all(classify_rule(_input(r)).get("status") == "NOT_A_RULE"
               and classify_rule(_input(r)).get("record_kind") == "not_a_rule"
               and classify_rule(_input(r)).get("primary") is None for r in nr)
    print("%s C NOT_A_RULE（剔除 needs_split）%d 条 → NOT_A_RULE/not_a_rule/primary=null"
          % ("✓" if c_ok else "✗", len(nr)))

    # 碰撞 / UNKNOWN / P0
    collisions = sum(1 for r in denom if detect_collisions(_input(r)))
    unknowns = sum(1 for o, _ in out if o.get("status") == "UNKNOWN")
    collision_rate = collisions / float(len(denom))
    unknown_rate = unknowns / float(len(denom))
    print("碰撞 = %d（率 %.4f，要求 0）；UNKNOWN = %d（率 %.4f，要求 ≤0.05）"
          % (collisions, collision_rate, unknowns, unknown_rate))

    p0_hit = 0
    for r in rows:
        if r.get("rule_id") in P0_IDS:
            o = classify_rule(_input(r))
            if o.get("primary") in ("SCENE", "RIGHT") and o.get("severity") == 5:
                p0_hit += 1
    print("P0 召回 = %d/%d（要求 4/4）" % (p0_hit, len(P0_IDS)))

    failures = []
    if axis_exact < 0.95:
        failures.append("axis_exact < 0.95")
    if blind > 0.85:
        failures.append("盲测未下降")
    if not a_ok:
        failures.append("A needs_split")
    if not b_ok:
        failures.append("B EDITORIAL")
    if not c_ok:
        failures.append("C NOT_A_RULE")
    if collisions != 0:
        failures.append("collision")
    if unknown_rate > 0.05:
        failures.append("unknown_rate")
    if p0_hit != len(P0_IDS):
        failures.append("p0_recall")
    if leaked:
        failures.append("输入读基准标签")
    if failures:
        print("❌ 未达标：%s" % ", ".join(failures), file=sys.stderr)
        return 1
    print("✅ taxonomy 回归与门槛全过")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验证器自身异常: %s" % exc)
        sys.exit(2)
