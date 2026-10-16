#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
漏报归因：新引擎漏掉的 74 次现行命中，到底是什么性质。

★ 为什么必须做这一步：Recall 0.689 这个数字本身**不能判断是新引擎有问题还是数据有问题**。
  如果不归因就报出去，等于把一个未解的问题包装成一个指标。

归因分四类（互斥，按证据强度排序）：
  A_missed_by_us   片段**确实在正文里**，新引擎没命中 → **我们的缺陷**，必须修
  B_text_absent    片段**不在正文里**，但能在该记录的其他字段找到 → 字段范围问题
  C_unverifiable   片段**整个记录里都找不到** → 现行判定依据的文本不在表内
  D_fuzzy_match    片段不在，但正文里有高度近似的表述 → 现行判定做了模糊匹配
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score  # noqa: E402

WIDE_FIELDS = ["广告名称", "广告系列Campaign", "落地页URL", "广告组", "修改建议", "命中原因"]

# 近似匹配：把片段压成字母数字骨架，看是否是子串关系
def skeleton(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def main():
    rules, recs = score.load()
    eng = score.Engine(rules)

    # 每条记录的新引擎命中集合
    new_by_id = {}
    for r in recs:
        hits, _ = eng.assess(score.rec_text(r))
        new_by_id[r.get("外部广告ID", "")] = {h.parent_rule for h in hits}

    cats = Counter()
    detail = defaultdict(list)

    for r in recs:
        rid = r.get("外部广告ID", "")
        text = score.rec_text(r)
        tl = text.lower()
        wide = " | ".join(str(r.get(f, "")) for f in WIDE_FIELDS).lower()
        new_rules = new_by_id.get(rid, set())

        for part in (r.get("命中片段", "") or "").split("/"):
            part = part.strip()
            if ":" not in part:
                continue
            rule_id, frag = part.split(":", 1)
            rule_id, frag = rule_id.strip(), frag.strip()
            if not frag:
                continue
            # 只看漏报：现行有、新引擎没有
            if rule_id in new_rules:
                continue
            # 也不看停用规则
            if rule_id == "U02":
                continue

            fl = frag.lower()
            if fl in tl:
                cat = "A_missed_by_us"
            elif fl in wide:
                cat = "B_text_absent"
            elif skeleton(frag) and skeleton(frag) in skeleton(text):
                cat = "D_fuzzy_match"
            else:
                # 片段可能是多个词，逐个试
                toks = [t for t in re.split(r"[,\s]+", fl) if len(t) > 3]
                if toks and any(t in tl for t in toks):
                    cat = "D_fuzzy_match"
                else:
                    cat = "C_unverifiable"
            cats[cat] += 1
            detail[cat].append((rid, rule_id, frag))

    total = sum(cats.values())
    print("=" * 70)
    print(f"漏报归因：新引擎漏掉的 {total} 次现行命中")
    print("=" * 70)
    label = {
        "A_missed_by_us": "A 我们的缺陷（片段在正文里，引擎没命中）",
        "B_text_absent":  "B 字段范围（片段不在文案里，在别的字段）",
        "C_unverifiable": "C 不可验证（整条记录里都找不到该片段）",
        "D_fuzzy_match":  "D 模糊匹配（正文有近似表述，无逐字片段）",
    }
    for k in ["A_missed_by_us", "B_text_absent", "C_unverifiable", "D_fuzzy_match"]:
        n = cats.get(k, 0)
        print(f"  {label[k]:46s} {n:3d}  ({n/total*100:4.1f}%)")
    print()

    for k in ["A_missed_by_us", "B_text_absent", "D_fuzzy_match", "C_unverifiable"]:
        if not detail[k]:
            continue
        print("-" * 70)
        print(f"{label[k]} —— 样例（最多 12 条）")
        print("-" * 70)
        by_rule = Counter(x[1] for x in detail[k])
        print(f"  按规则: {dict(by_rule)}")
        for rid, rule_id, frag in detail[k][:12]:
            print(f"    {rid}  {rule_id}:{frag[:60]}")
        print()

    out = HERE / "_data" / "miss_attribution.json"
    out.write_text(json.dumps(
        {"categories": dict(cats),
         "detail": {k: v for k, v in detail.items()}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {out}")


if __name__ == "__main__":
    main()
