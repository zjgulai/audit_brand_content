#!/usr/bin/env python3
"""build_whitelist.py —— 从现网快照抽出「安全词白名单」，独立成表（ADR-0008）

背景（为什么必须物理分离）：
  现网把白名单塞在 `品线内容边界规则库` 的第 18 行，`检测关键词` 字段与判险规则同名字段。
  实测三类事故都源于此：

  事故 A｜词表污染：任何 `SELECT 检测关键词 FROM 规则库` 都会把 26 个白名单词
          拼进违规词表。本项目 `offline_replay.py` 正是这样跑出 56/57 条误报
          （「误报 55.9%」的数字是假的）。
  事故 B｜手抄同步：白名单没有程序化通道，靠人把词抄进各规则的 `豁免词`。
          26 词只有 10 个抄到了；16 个是孤儿（加了不生效）。
  事故 C｜抄漏即矛盾：`reduces pain` / `less pain` 抄漏 → 同时是 H07 判险词
          和白名单词，零机制可裁决。即 EB-R011，登记为「未修复」。

本脚本把白名单抽为独立文件，并把「隐含的手抄关系」变成显式字段 `exempts`。
输出：whitelist-v1.json（只读输入，不修改快照）
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
SNAPSHOT = ROOT / "research/live/snapshot-20260916T050845Z.json"

SAFE_TYPE = "安全词白名单"

# ── 判别标准（R5-E，唯一一条）：能否被第三方独立复核为真/假 ──────────────
# 不满足者隔离，不进入放行通道。隔离不是删除 —— 保留记录与理由，供复查。
QUARANTINE = {
    "reduces pain": "主张疗效（= H07 判险词），不可独立复核为客观参数；且已被 H07 判险，放行会与 H07 直接冲突",
    "less pain":    "主张疗效（= H07 判险词），同上",
    "gentle":       "主观感受词，无客观量纲，第三方无法复核真/假",
    "comfort":      "主观感受词，无客观量纲，第三方无法复核真/假",
}

# 每类词所需的证据类型（供第二段逐字核验使用）
EVIDENCE = {
    "spec":    "product_spec",       # 产品规格书
    "cert":    "certificate",        # 认证文件
    "feature": "feature_list",       # 功能清单
}

# 现网规则编号 → 本地骨架 rule_key。白名单的豁免目标要能落到骨架规则上，
# 否则「白名单 → 规则」这条链在骨架侧断掉，又退化成人工对照。
LEGACY_TO_RULE_KEY = {
    "H01": "T1.1.medical-cure",
    "H02": "T2.1.1.milk-supply",
    "H05": "T5.1.safety-claim",
    "H06": "T6.1.regulatory-status",
    "H07": "T2.1.2.pain-relief",
    "M01": "T2.2.quiet-claim",
    "M02": "T2.2.suction-claim",
    "M05": "T3.3.institution-grade",
    "U03": "T7.1.hospital-scenario",
}


def split_terms(raw):
    return [x.strip() for x in re.split(r"[/,，;；\n]", raw or "") if x.strip()]


def main():
    snap = json.loads(SNAPSHOT.read_text())
    recs = snap["sources"]["boundary_rules"]["records"]

    wl_row, rules = None, {}
    for r in recs:
        f = r["fields"]
        rid = str(f.get("规则编号") or "").strip()
        if str(f.get("边界类型") or "").strip() == SAFE_TYPE:
            wl_row = (rid, r)
            continue
        rules[rid] = {
            "kw": {w.lower() for w in split_terms(f.get("检测关键词"))},
            "ex": {w.lower() for w in split_terms(f.get("豁免词"))},
        }

    if wl_row is None:
        print("❌ 快照里找不到边界类型=" + SAFE_TYPE, file=sys.stderr)
        return 1

    rid, rec = wl_row
    f = rec["fields"]
    words = split_terms(f.get("检测关键词"))

    entries, orphans, conflicts, propagated = [], [], [], {}
    for w in words:
        lw = w.lower()
        # 现网里这个词实际被抄进了哪些规则的豁免词 —— 把隐含关系显式化
        exempts = sorted(r for r, v in rules.items() if lw in v["ex"])
        # 现网里这个词是否又是某条规则的判险词 —— 这就是矛盾
        clash = sorted(r for r, v in rules.items() if lw in v["kw"])
        q = QUARANTINE.get(lw)

        if clash:
            conflicts.append((w, clash))
        if not exempts and not q:
            orphans.append(w)
        for r in exempts:
            propagated.setdefault(r, []).append(w)

        entries.append({
            "word": w,
            "lang": "en" if re.fullmatch(r"[a-z0-9\-\s]+", lw) else "zh",
            "status": "quarantined" if q else "active",
            "quarantine_reason": q,
            # ★ 显式豁免目标：白名单词 → 它给哪几条规则的「放行通道」供词
            "exempts": exempts,
            # 落到本地骨架的 rule_key，供规则侧生成 exempt_band
            "exempts_rule_keys": sorted(LEGACY_TO_RULE_KEY[r] for r in exempts
                                        if r in LEGACY_TO_RULE_KEY),
            "evidence_required": EVIDENCE["cert"] if "fda" in lw else EVIDENCE["spec"],
            "live_clash_with_detection": clash,
            "source_legacy": rid,
        })

    out = {
        "$schema_version": "whitelist-v1",
        "$note": [
            "★ ADR-0008：本表是独立白名单，**不得与判定规则同表混放**。",
            "现网把白名单塞在规则库第 18 行，`检测关键词` 字段与判险规则同名，",
            "导致任何『读规则库拼词表』的动作都会让『安全』去证明『有风险』。",
            "本表唯一用途：为 `exempts` 列出的规则的 downgrade_band 提供放行词。",
            "不产生任何命中（没有 hit 语义）。这一点与规则的区别是结构性的，",
            "不依赖任何 `is_modifier` 之类的运行时开关。",
        ],
        "admission_criterion": {
            "rule": "能否被第三方独立复核为真/假（R5-E）",
            "note": "不满足者进入 quarantined，不参与放行。这是唯一判别标准，不再有第二套。",
        },
        "invariants": [
            "W1 disjointness ｜ active 词的 word 不得出现在任何判定规则的 match.keywords 中",
            "W2 attribution ｜ 每个 active 词必须有非空 exempts（否则是死重：加了不生效）",
            "W3 quarantine  ｜ quarantined 词不得进入任何「放行通道」",
            "   ★ W3 的边界：隔离词**可以**进入 downgrade_band（降级 ≠ 放行）。",
            "     gentle/comfort 正是如此 —— 它们不给 H07 放行，但把 H07 从 auto_reject",
            "     降到 manual_review。放行与降级是两个通道，不是一件事。",
        ],
        "source": {
            "snapshot": SNAPSHOT.name,
            "legacy_rule_id": rid,
            "legacy_record_id": rec.get("record_id"),
            "legacy_boundary_type": SAFE_TYPE,
        },
        "stats": {
            "total": len(entries),
            "active": sum(1 for e in entries if e["status"] == "active"),
            "quarantined": sum(1 for e in entries if e["status"] == "quarantined"),
            "orphans_in_live": len(orphans),
        },
        "words": entries,
    }

    (HERE / "whitelist-v1.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2) + "\n")

    # ── 报告：不静默 ────────────────────────────────────────────────
    print(f"白名单独立成表：{len(entries)} 词"
          f"（active {out['stats']['active']} / quarantined {out['stats']['quarantined']}）")
    print(f"输出 → {HERE / 'whitelist-v1.json'}")
    print()

    print("① 现网手抄同步的实际覆盖面（exempts 显式化）")
    for r in sorted(propagated):
        print(f"   {r:<5} ← {len(propagated[r])} 词  {sorted(propagated[r])}")
    print(f"   ── 26 词中只有 {sum(len(v) for v in propagated.values())} 处手抄关系，"
          f"孤儿 {len(orphans)} 词（加了不生效）")
    if orphans:
        print(f"   孤儿：{sorted(orphans)}")
    print()

    print("② 隔离词（不参与放行）")
    for e in entries:
        if e["status"] == "quarantined":
            print(f"   {e['word']:<14} {e['quarantine_reason'][:52]}")
    print()

    print("③ ★ 现网仍存在的『同一词既是白名单又是判险词』矛盾")
    if conflicts:
        for w, rs in conflicts:
            print(f"   {w:<14} 同时是 {rs} 的判险词 —— 零机制可裁决（EB-R011，登记为未修复）")
    else:
        print("   无")
    print()

    # ── ④ 顺带查出：`豁免词` 字段装的是两种机制 ──────────────────────
    print("④ ★ `豁免词` 字段 = 两种机制混装（与安全词同病）")
    wl_lower = {w.lower() for w in words}
    a_cnt = b_cnt = 0
    for rid_, v in sorted(rules.items()):
        a = [x for x in v["ex"] if x in wl_lower]
        b = [x for x in v["ex"] if x not in wl_lower]
        a_cnt += len(a); b_cnt += len(b)
        if v["ex"]:
            print(f"   {rid_:<5} 白名单类 {len(a):<3} 语境守卫类 {len(b):<3}")
    print(f"   ── 合计：白名单类 {a_cnt} ｜ 语境守卫类 {b_cnt}"
          f"（{b_cnt / max(a_cnt + b_cnt, 1):.0%} 是另一种机制）")
    print("   语境守卫 = 否定/免责（can't cure / not a medical device / 不能治疗乳腺炎）")
    print("   它与「客观参数」毫无关系，却和放行词共用同一字段 → 需第 4 项决策")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
