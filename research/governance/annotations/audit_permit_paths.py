#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_permit_paths.py —— 「允许措辞」到底住在哪一层？

★ 这份脚本回答一个具体问题（O1 咨询单的证据底稿）：
   现行审核表里被判红/黄的广告，常同时含有规则文本自己宣布「允许」的措辞
   （comfort / gentle / discomfort / 缓解涨奶 / soulage les engorgements）。
   那么 —— 「允许」这个状态，在代码里住哪一行？

★ 结论（由本脚本机械复现，不手写）：
   它不住在任何一行。它是「检测不到」的副作用。
   详见输出 §4 与 §5。

输入（只读）：
  skeleton/_data/rules_raw.json   21 条现行规则的原始抽取（含 exceptions）
  skeleton/rules-v1.json          本次重建的 26 条叶子规则（含 downgrade_band）
  skeleton/_data/records.json     291 条真实审核记录（人在用的那张表）

用法：
  python3 annotations/audit_permit_paths.py
退出码：0 = 全部核验通过；1 = 断言失败（说明底层数据变了，需重跑分析）
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW = ROOT / "skeleton" / "_data" / "rules_raw.json"
V1 = ROOT / "skeleton" / "rules-v1.json"
RECORDS = ROOT / "skeleton" / "_data" / "records.json"

# 允许措辞家族 —— 用于 §5 扫描现行表
ALLOW_WORDS = ["comfort", "gentle", "discomfort"]


def fires(rule, text):
    """复现 v1 规则的命中判定：keywords 子串 + patterns 正则。返回命中的具体项。"""
    tl = text.lower()
    for k in rule["match"].get("keywords", []):
        if k.lower() in tl:
            return "kw:" + k
    for p in rule["match"].get("patterns", []):
        try:
            if re.search(p, tl, re.I):
                return "re:" + p
        except re.error:
            pass
    return None


def self_detectable(entry, rule):
    """一条豁免词能否被 rule 自己检测到（即豁免分支是否有进入条件）。"""
    return (entry in rule["match"].get("keywords", [])) or any(
        re.search(p, entry, re.I) for p in rule["match"].get("patterns", []))


def main():
    raw_list = json.loads(RAW.read_text())
    raw = {r["rule_id"]: r for r in raw_list}
    v1 = json.loads(V1.read_text())["rules"]
    by_key = {r["rule_key"]: r for r in v1}
    records = json.loads(RECORDS.read_text())

    print("=" * 84)
    print("§1  现行 21 条规则的 exceptions 分支，有进入条件吗？")
    print("=" * 84)
    total_ex = inert_ex = 0
    for rule_id, r in raw.items():
        for e in r.get("exceptions") or []:
            total_ex += 1
            if not self_detectable(e, {"match": {"keywords": r.get("keywords", []),
                                                 "patterns": r.get("patterns", [])}}):
                inert_ex += 1
    print(f"  全库 exceptions 共 {total_ex} 条；其中自身检测不到的 {inert_ex} 条"
          f"（{inert_ex/total_ex:.0%}）")
    h01 = raw["H01"]
    h01_inert = sum(1 for e in h01["exceptions"]
                    if not self_detectable(e, {"match": {"keywords": h01["keywords"],
                                                         "patterns": h01["patterns"]}}))
    print(f"  H01：{h01_inert}/{len(h01['exceptions'])} 条检测不到 → "
          f"**该分支从未生效**（不是设计选择，是没有进入条件）")

    print()
    print("=" * 84)
    print("§2  H01 的 exceptions 在重建（v1）中的去向")
    print("=" * 84)
    kids = {k: v for k, v in by_key.items() if v.get("parent_rule") == "H01"}
    kw, dg, pat = set(), set(), set()
    for v in kids.values():
        kw |= set(v["match"].get("keywords", []))
        dg |= set(v.get("downgrade_band", {}).get("keywords", []))
        pat |= set(v["match"].get("patterns", []))
    ex = h01["exceptions"]
    kept = [e for e in ex if e in dg]
    lost = [e for e in ex if e not in kw and e not in dg and e not in pat]
    print(f"  原文 {len(ex)} 条 → v1 保留 {len(kept)} 条（全部落在 downgrade_band）、"
          f"丢失 {len(lost)} 条")
    t15 = by_key["T1.5.duct-unclog"]
    unre = [e for e in kept if not fires(t15, e)]
    print(f"  保留的 {len(kept)} 条中，{len(unre)} 条触发不了 T1.5（即豁免仍无进入条件）：")
    for e in unre:
        print(f"      · {e}")
    print(f"  ★ 净效果：**豁免的有效行为零变化**——丢的本来就进不去，留的也进不去。")
    print(f"    但文档层与代码层从此不一致：原文说「允许 X」，代码里没有任何地方认识 X。")

    print()
    print("=" * 84)
    print("§3  v1 全库 downgrade_band 可达性")
    print("=" * 84)
    unreachable, tot = [], 0
    for r in v1:
        for k in r.get("downgrade_band", {}).get("keywords", []):
            tot += 1
            if not fires(r, k):
                unreachable.append((r["rule_key"], k))
    print(f"  {len(unreachable)}/{tot} 条豁免词不可达（{len(unreachable)/tot:.0%}）")
    by_rule = {}
    for rk, k in unreachable:
        by_rule.setdefault(rk, []).append(k)
    for rk, ks in sorted(by_rule.items(), key=lambda x: -len(x[1])):
        print(f"      {rk:28s} {len(ks):2d} 条")
    print("  注：可达的 15 条全部是『否定式免责声明』（not intended to treat / 不能预防乳腺炎…），"
          "\n      它们自身含检测词，规则会命中，豁免才起作用。"
          "\n      也就是说：**豁免机制只对『说不是』有效，对『怎么说可以』完全无效。**")

    print()
    print("=" * 84)
    print("§4  O1 的四种表述，在 26 条叶子规则下的可见性")
    print("=" * 84)
    probes = [
        ("Soulage Les Engorgements", "法语 · 实际在投（B036/B038/B040/B041）"),
        ("Ease Engorgement Comfort", "英语 · 实际在投（B002/B032）"),
        ("relieve engorgement", "英语 · H01 原文列为允许"),
        ("缓解涨奶", "中文 · H01 原文列为允许；rules-v1 写进 T1.5 豁免"),
        ("treat engorgement", "英语 · H01 原文列为红线（对照）"),
    ]
    for t, note in probes:
        hits = [f"{r['rule_key']}" for r in v1 if fires(r, t)]
        tag = "★ 零命中 · 引擎完全不可见" if not hits else "命中 " + ",".join(hits)
        print(f"  「{t}」".ljust(34) + tag)
        print(f"      {note}")

    print()
    print("=" * 84)
    print("§5  现行 291 条表：被判红/黄、却同时含『允许措辞』的记录")
    print("=" * 84)
    rows = []
    for r in records:
        blob = ((r.get("Primary Text") or "") + " " + (r.get("Headline") or "")).lower()
        found = [w for w in ALLOW_WORDS if w in blob]
        if found and r["风险等级"] in ("高危·红", "中危·黄"):
            rows.append((r["广告名称"], r["风险等级"], r["命中规则"], found))
    print(f"  {len(rows)}/{len(records)} 条（{len(rows)/len(records):.1%}）")
    print("  → 这些记录里，同一个广告词被拆成两半：判红的半边进了表，"
          "\n    允许的半边没有进表、也没有进建议。改写时允许的半边会被一起删掉。")

    print()
    print("=" * 84)
    print("§6  判红原因文本里，规则自己写的许可语")
    print("=" * 84)
    fr = [r for r in records if r["投放地区"] == "法国"
          and r["广告名称"] in ("w1-卖点图", "w1-卖点视频")]
    all_has = fr and all("缓解胀满不适" in (r["命中原因"] or "") for r in fr)
    print(f"  法国 W1 卖点图/视频 {len(fr)} 条，命中规则 {set(r['命中规则'] for r in fr)}")
    print(f"  其中『命中原因』字段含许可语「缓解胀满不适」：{all_has}")
    if fr:
        print(f"  原文：{fr[0]['命中原因'][:150]}…")
    print("  → 同一条记录：被判红（因 sans douleur），同时含被宣布允许的"
          "\n    Soulage Les Engorgements。裁判与许可写在同一个字段里，互不引用。")

    # ------------------------------------------------------------------ 断言
    print()
    print("=" * 84)
    assert h01_inert == len(h01["exceptions"]), "H01 exceptions 出现可达项，结论需重算"
    assert len(unre) == len(kept) == 14, f"保留/不可达数不符：{len(kept)}/{len(unre)}"
    assert len(lost) == 30, f"丢失数不符：{len(lost)}"
    assert not any(fires(r, "Soulage Les Engorgements") for r in v1), \
        "Soulage Les Engorgements 已可命中，O1 结论需重算"
    assert all_has, "许可语不在判红原因中，§6 结论需重算"
    print("✓ 全部断言通过：§1–§6 结论可由本脚本复现。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
