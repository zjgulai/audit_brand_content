#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据桥：把 PRD 里的两张源表抽成骨架可直接消费的 JSON。

**为什么优先复用 `audit_rule_table.py` 的解析器**：
那张表的字段里有逗号（`检测关键词` 用 ", " 分隔，但关键词本身可能含逗号）、
正则里也有逗号（`[^.!?|,]*leak`）。裸 split(",") 会切碎正则 —— 这是已被踩过的坑，
`split_patterns()` 已经处理了（按括号/字符类深度切分）。重新实现一遍必然踩同一个坑。

产物：
  skeleton/_data/rules_raw.json    21 条规则（原始字段，未改写）
  skeleton/_data/records.json      291 条广告记录（原始字段）

本脚本只做搬运，**不做任何判断**。改写发生在 rules-v1.json（手工维护）。
"""
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
GOV = HERE.parent
sys.path.insert(0, str(GOV))

from audit_rule_table import (  # noqa: E402
    load_rules,
    load_tables,
    to_dicts,
    keywords_of,
    split_patterns,
)

OUT = HERE / "_data"
OUT.mkdir(exist_ok=True)

AD_TABLE_KEY = "广告文案明细"
RULE_TABLE_KEY = "品线内容边界规则库"


def find_table(tables, needle):
    hits = [k for k in tables if needle in k]
    if len(hits) != 1:
        raise SystemExit(f"表名匹配不唯一：{needle!r} → {hits}")
    return hits[0]


def split_list(raw):
    """按 , 切分普通列表字段（豁免词等 —— 这些字段不含嵌套逗号）。"""
    return [x.strip() for x in (raw or "").split(",") if x.strip()]


def main():
    # ---------- 规则 ----------
    hdr, rule_rows = load_rules()
    rules = []
    for r in rule_rows:
        rules.append({
            "rule_id": r.get("规则编号", "").strip(),
            "boundary_type": r.get("边界类型", "").strip(),
            "applicable_products": split_list(r.get("适用产品", "").replace("、", ",")),
            "risk_level_legacy": r.get("风险等级", "").strip(),
            "keywords": keywords_of(r),
            "boundary_content": r.get("边界内容", "").strip(),
            "detect_mode_legacy": r.get("判断方式", "").strip(),
            "source_legacy": r.get("依据来源", "").strip(),
            "enabled": r.get("启用状态", "").strip() == "启用",
            "patterns": split_patterns(r.get("正则表达式", "") or ""),
            "exceptions": split_list(r.get("豁免词", "")),
            "trigger_reason": r.get("触发原因", "").strip(),
            "_n_cols": r.get("__COLCOUNT__"),
        })

    # ---------- 记录 ----------
    tables = load_tables()
    ad_key = find_table(tables, AD_TABLE_KEY)
    ad_hdr, ad_rows = tables[ad_key]
    records = to_dicts(ad_hdr, ad_rows)


    def num(v):
        s = (v or "").replace(",", "").replace("$", "").strip()
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None

    for rec in records:
        rec["_spend"] = num(rec.get("近7天费用USD"))
        rec["_impr"] = num(rec.get("近7天展示"))
        rec["_clicks"] = num(rec.get("近7天点击"))
        hr = (rec.get("命中规则", "") or "").strip()
        rec["_hit_rules"] = [x.strip() for x in hr.split(",") if x.strip() and x.strip() != "EMPTY"]

    (OUT / "rules_raw.json").write_text(
        json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "records.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- 自检（不静默） ----------
    print(f"规则 {len(rules)} 条 → {OUT/'rules_raw.json'}")
    print(f"记录 {len(records)} 条 → {OUT/'records.json'}")
    print()
    print("规则字段完整性：")
    missing = [r["rule_id"] for r in rules if not r["rule_id"]]
    if missing:
        print(f"  ✗ 无编号的规则：{missing}")
    n_list = len(records[0]) if records else 0
    print(f"  记录字段数：{n_list}（含 4 个派生 _ 字段）")
    print()
    print("暴露量自检：")
    nonzero = [r for r in records if r["_spend"] and r["_spend"] > 0]
    print(f"  有花费记录 {len(nonzero)}/{len(records)}，合计 ${sum(r['_spend'] for r in nonzero):,.2f}")
    zero = len([r for r in records if r["_spend"] == 0])
    print(f"  花费=0 的记录 {zero} 条 —— ⚠ 这些记录**没有真实暴露量**，")
    print(f"    其 risk_level 缺 likelihood 分量，必须走 L0/未覆盖分支而不是硬套公式")
    print()
    print("命中规则分布：")
    c = Counter(x for r in records for x in r["_hit_rules"])
    for k, v in c.most_common(10):
        print(f"  {k:6s} {v:3d} 条命中")
    never = [r["rule_id"] for r in rules
             if r["enabled"] and r["rule_id"] not in c]
    print(f"  从未命中的启用规则：{never}")


if __name__ == "__main__":
    main()
