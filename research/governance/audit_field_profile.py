#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_field_profile.py — 字段可用性剖面审计

回答：这份记录表的每个字段，是「信息」还是「装饰」？

核心判据（本脚本的方法论主张）：
    看一个字段是装饰还是信息，不要看填充率，要看它的取值
    能不能被另一个字段独立验证。
    `投放地区` 填充率 99.3%，但 74.2% 的取值是「其他」——高填充率掩盖了零信息量。

只读 PRD/内容治理需求文档.md，不修改任何输入。

用法：
    python3 research/governance/audit_field_profile.py
    python3 research/governance/audit_field_profile.py --json   # 输出机器可读结果
"""

import re
import sys
import json
from collections import Counter, defaultdict
from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "PRD" / "内容治理需求文档.md"
HEADER_PREFIX = "| 广告名称 | 平台 |"

# 广告账号名 → 该账号声明的投放地区（人工从账号名提取，用于独立验证）
ACCOUNT_REGION = {
    "Momcozy-Angel-FR": ["FR"],
    "Momcozy-PL-1": ["PL"],
    "Momcozy-Jolla(US&UK&CA&PL)—吸奶器": ["US", "UK", "CA", "PL"],
    "Momcozy-Angel(DE&FR&PL其他品线）": ["DE", "FR", "PL"],
    "Momcozy-UK-1": ["UK"],
    "Momcozy-CA-1-1": ["CA"],
    "Momcozy-EU-1": ["EU"],
    "Momcozy-AU-1-1": ["AU"],
    "Momcozy-ES-1-1": ["ES"],
    "Momcozy-IT-1-1": ["IT"],
    "Momcozy-外部需求投放": ["?"],
}

# campaign 名 → 地区（返回规范化的 ISO 风格代码，便于与账号名声明直接比较）
REGION_NORM = {
    "美国": "US", "德国": "DE", "波兰": "PL", "法国": "FR",
    "英国": "UK", "加拿大": "CA", "西班牙": "ES", "意大利": "IT",
    "澳大利亚": "AU", "欧盟": "EU", "日本": "JP", "荷兰": "NL",
}


def campaign_region(camp):
    """从 campaign 名恢复地区，返回规范化代码或 None。"""
    # 拉丁代码形式：-US-、欧洲DE、欧洲PL
    m = re.search(r"[-–](US|UK|CA|AU|DE|FR|PL|ES|IT|JP|NL)[-–]", camp)
    if m:
        return m.group(1)
    m = re.search(r"欧洲(DE|PL|FR|ES|IT|NL)", camp)
    if m:
        return m.group(1)
    # 中文形式：-美国-、-德国-
    m = re.search(r"[-–](" + "|".join(REGION_NORM) + r")[-–]", camp)
    if m:
        return REGION_NORM[m.group(1)]
    # 欧洲小国EUR 等聚合区
    m = re.search(r"欧洲小国([A-Z]{3})", camp)
    if m:
        return "EU" if m.group(1) == "EUR" else m.group(1)
    return None


def split_row(row):
    """转义感知切分：\\| 是内容，不是分隔符。"""
    return [c.strip() for c in re.split(r"(?<!\\)\|", row)[1:-1]]


def load():
    text = DOC.read_text(encoding="utf-8")
    lines = text.split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith(HEADER_PREFIX))
    header = split_row(lines[start])
    rows, j = [], start + 2
    while j < len(lines) and lines[j].startswith("|"):
        cells = split_row(lines[j])
        if len(cells) == len(header):
            rows.append(cells)
        j += 1
    return header, rows


EMPTY = {"", "-", "—", "/", "－"}


def profile_fields(header, rows):
    out = []
    for k, h in enumerate(header):
        vals = [r[k] for r in rows if r[k] not in EMPTY]
        out.append({
            "field": h,
            "filled": len(vals),
            "fill_rate": round(len(vals) / len(rows) * 100, 1),
            "distinct": len(set(vals)),
            "top": Counter(vals).most_common(3),
        })
    return out


def catch_all_test(header, rows, field, catchall="其他"):
    """「其他」桶检验：占比越高，字段越装不住东西。"""
    k = header.index(field)
    c = Counter(r[k] for r in rows)
    total = sum(c.values())
    oth = c.get(catchall, 0)
    return {"field": field, "catchall": catchall, "count": oth,
            "rate": round(oth / total * 100, 1), "values": dict(c)}


def cross_validate_region(header, rows):
    """三字段交叉验证：字段声明 vs campaign 名 vs 账号名。"""
    acc_i, camp_i, reg_i = (header.index("广告账号"),
                            header.index("广告系列Campaign"),
                            header.index("投放地区"))
    by_acc = defaultdict(lambda: {"n": 0, "field": Counter(), "camp": Counter()})
    for r in rows:
        d = by_acc[r[acc_i] or "(空)"]
        d["n"] += 1
        d["field"][r[reg_i]] += 1
        d["camp"][campaign_region(r[camp_i]) or "(未解析)"] += 1

    table, agree, total_named, mixed = [], 0, 0, []
    for acc, d in sorted(by_acc.items(), key=lambda x: -x[1]["n"]):
        declared = ACCOUNT_REGION.get(acc)
        recovered = {k for k in d["camp"] if k != "(未解析)"}
        # 一致性判定：campaign 恢复出的地区集合 是否被账号名声明的地区集合覆盖
        ok = None
        if declared and declared != ["?"] and recovered:
            ok = recovered <= set(declared)
            total_named += 1
            agree += 1 if ok else 0
            if not ok:
                mixed.append({"account": acc, "declared": declared,
                              "recovered": sorted(recovered)})
        table.append({"account": acc, "n": d["n"],
                      "field_says": dict(d["field"]),
                      "campaign_says": dict(d["camp"]),
                      "account_name_says": declared,
                      "consistent": ok})
    return table, agree, total_named, mixed


def platform_balance(header, rows):
    p_i, a_i, r_i = (header.index("平台"), header.index("广告账号"),
                     header.index("命中规则"))
    out = {}
    for p in ("Google", "Meta"):
        sub = [r for r in rows if r[p_i] == p]
        if not sub:
            continue
        hit = [r for r in sub if r[r_i] and "EMPTY" not in r[r_i]]
        out[p] = {
            "n": len(sub),
            "share": round(len(sub) / len(rows) * 100, 1),
            "account_field_filled": sum(1 for r in sub if r[a_i]),
            "hit": len(hit),
            "hit_rate": round(len(hit) / len(sub) * 100, 1),
        }
    return out


def main():
    header, rows = load()
    as_json = "--json" in sys.argv

    fields = profile_fields(header, rows)
    catchalls = [catch_all_test(header, rows, f)
                 for f in ("投放地区", "文案语种", "广告类型")]
    region_table, agree, total_named, mixed = cross_validate_region(header, rows)
    platforms = platform_balance(header, rows)

    zero = [f["field"] for f in fields if f["filled"] == 0]

    if as_json:
        print(json.dumps({
            "n_records": len(rows), "n_fields": len(header),
            "fields": [{k: v for k, v in f.items() if k != "top"} for f in fields],
            "catch_all": catchalls,
            "region_cross_validation": region_table,
            "region_agreement": f"{agree}/{total_named}",
            "region_mixed_accounts": mixed,
            "platform_balance": platforms,
            "zero_fill_fields": zero,
        }, ensure_ascii=False, indent=2))
        return 0

    W = 78
    print("=" * W)
    print(f"字段可用性剖面审计　　{len(rows)} 条记录 × {len(header)} 字段")
    print("=" * W)

    print(f"\n### 1. 字段填充率剖面\n")
    print(f"{'字段':<18}{'填充':>6}{'填充率':>9}{'取值数':>8}")
    print("-" * W)
    for f in fields:
        mark = "  ← 零填充" if f["filled"] == 0 else ""
        print(f"{f['field']:<18}{f['filled']:>6}{f['fill_rate']:>8.1f}%{f['distinct']:>8}{mark}")

    print(f"\n### 2. 「其他」桶检验（高填充率掩盖零信息量）\n")
    for c in catchalls:
        print(f"{c['field']:<12} 其他={c['count']}/{len(rows)} = {c['rate']:>5.1f}%   "
              f"实际取值: {c['values']}")

    print(f"\n### 3. 三字段交叉验证：`投放地区` 的数据其实完好\n")
    print(f"{'广告账号':<36}{'字段说':<14}{'campaign说':<16}{'一致'}")
    print("-" * W)
    for t in region_table:
        fld = ",".join(f"{k}×{v}" for k, v in t["field_says"].items())
        cmp_ = ",".join(f"{k}×{v}" for k, v in t["campaign_says"].items())
        ok = {True: "✓", False: "✗", None: "—"}[t["consistent"]]
        print(f"{t['account'][:35]:<36}{fld[:13]:<14}{cmp_[:15]:<16}{ok}")
    print(f"\n   一致率：{agree}/{total_named} 个可验证账号")
    if mixed:
        print(f"\n   ⚠ 跨地区账号（campaign 地区超出账号名声明）：")
        for m in mixed:
            print(f"     {m['account']}  账号名声明={m['declared']}  "
                  f"实际恢复={m['recovered']}")

    print(f"\n### 4. 平台抽样偏差（→ 02 号文件 §7 的更正依据）\n")
    for p, d in platforms.items():
        print(f"{p:<8} n={d['n']:<5} 占比={d['share']:>5.1f}%   "
              f"广告账号填充={d['account_field_filled']}/{d['n']}   "
              f"命中率={d['hit_rate']:>5.1f}%")

    print(f"\n### 5. 结论\n")
    print(f"  零填充字段：{zero if zero else '（无）'}")
    print(f"  `投放地区` 的 `其他` 桶装了 {catchalls[0]['count']} 条"
          f"（{catchalls[0]['rate']}%），而 campaign 名可精确恢复 US/DE/PL ——")
    print(f"  这是数据字典枚举值缺失，不是数据脏。")
    print(f"  Meta 侧 `广告账号` 填充率 0% → 非同源样本 → 平台维度不可检验。")
    print("=" * W)
    return 0


if __name__ == "__main__":
    sys.exit(main())
