#!/usr/bin/env python3
"""wire_whitelist.py —— 白名单与规则的接线校验（ADR-0008 的实现）

修的是事故 B：现网白名单没有程序化通道，靠人把词抄进各规则的 `豁免词`。
26 词只有 10 个抄到了，14 个孤儿；抄漏的 `reduces pain` 直接变成 EB-R011。

★ 设计修正（本人第一版写错了，记录在此）：
  第一版新建了一个并行的 `exempt_band` 字段，结果撞出 8 处「同一词既放行又降级」。
  查证后发现**骨架本来就是自洽的** —— `downgrade_band` 一个字段承担两条通道，
  由 `effect` 字符串的**箭头右侧**决定落点：
      "auto_reject → auto_pass"      落点 auto_pass    （真放行）
      "manual_review → auto_pass"    落点 auto_pass    （真放行）
      "auto_reject → manual_review"  落点 manual_review（真降级）
  10 个手抄白名单词全部落在 auto_pass 带里，4 个隔离词落在 manual_review 带里 —— 无冲突。
  所以正确的动作是**校验**既有结构，不是新建重复字段。

  （顺带：`downgrade_band` 这个名字让通道语义藏在字符串里，是「同一字段装两种机制」
    的第三处实例，与 `安全词`、`豁免词` 同病。改名会让 score.py 的
    in_downgrade_band 失效，属独立变更，此处只标注不动手。）

本脚本做两件事：
  1. 把 T9.objective-parameter 的 `match.keywords` 清空，还原成纯主题节点。
     设计文档 §2.2.1 原话：「T9 是一个主题，不是一张白名单」。
  2. 校验：白名单每个 active 词的豁免目标，确实落在 effect 指向 auto_pass 的带里。

幂等：重复运行结果一致。首次运行前自动备份 rules-v1.json.bak。
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RULES = HERE / "rules-v1.json"
WL = HERE / "whitelist-v1.json"
BAK = HERE / "rules-v1.json.bak"

TOPIC_ONLY_KEY = "T9.objective-parameter"


def band_target(rule):
    """`downgrade_band.effect` 的箭头右侧 = 该带真正的落点通道。"""
    eff = str((rule.get("downgrade_band") or {}).get("effect") or "").strip()
    if "→" in eff:
        return eff.split("→")[-1].strip()
    if eff in ("none", ""):
        return "none"
    return eff


def main():
    wl = json.loads(WL.read_text())
    doc = json.loads(RULES.read_text())
    rules = {r["rule_key"]: r for r in doc["rules"]}

    if not BAK.exists():
        shutil.copy2(RULES, BAK)
        print(f"备份 → {BAK.name}")

    # ── 1. T9 还原成纯主题节点 ────────────────────────────────────
    print()
    print("① T9 还原为纯主题节点（设计文档 §2.2.1：T9 是主题，不是白名单）")
    t9 = rules.get(TOPIC_ONLY_KEY)
    changed = 0
    if t9 is None:
        print(f"   ⚠ 找不到 {TOPIC_ONLY_KEY}")
    else:
        wl_lower = {e["word"].lower() for e in wl["words"]}
        old_kw = list((t9.get("match") or {}).get("keywords") or [])
        keep = [k for k in old_kw if k.lower() not in wl_lower]
        if old_kw:
            t9.setdefault("match", {})["keywords"] = keep
            changed += 1
        t9["topic_only"] = True
        t9["$topic_only_note"] = [
            "★ ADR-0008：本节点是**主题**，不持有词表，不产生命中。",
            f"原 {len(old_kw)} 个白名单词已迁出至 whitelist-v1.json（独立表）。",
            "设计文档 §2.2.1：「T9 是一个主题，不是一张白名单」。",
            "此前用 is_modifier 在运行时兜住 —— 那是开关不是结构：词仍在同表同字段，",
            "任何 `SELECT 检测关键词` 仍会取到它们，本项目 56/57 条误报即由此而来。",
        ]
        t9.pop("$is_modifier_note", None)
        print(f"   match.keywords: {len(old_kw)} → {len(keep)}")
        if keep:
            print(f"   ⚠ 仍有非白名单词残留（需人工确认归属）：{keep}")

    if changed:
        RULES.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        print(f"\n已写回 {RULES.name}（{changed} 处变更）")

    # ── 2. 接线校验：豁免目标必须落在 auto_pass 带 ──────────────────
    print()
    print("② 接线校验：每个 active 白名单词的豁免目标，须落在 effect→auto_pass 的带里")
    missing, mismatched, ok = [], [], []
    for e in wl["words"]:
        if e["status"] != "active":
            continue
        targets = e.get("exempts_rule_keys") or []
        if not targets:
            missing.append(e["word"])
            continue
        for rk in targets:
            r = rules.get(rk)
            if r is None:
                mismatched.append((e["word"], rk, "规则不存在"))
                continue
            band_kw = {k.lower() for k in (r.get("downgrade_band") or {}).get("keywords", [])}
            tgt = band_target(r)
            if e["word"].lower() not in band_kw:
                mismatched.append((e["word"], rk, f"不在该规则的带里（带={sorted(band_kw)}）"))
            elif tgt != "auto_pass":
                mismatched.append((e["word"], rk, f"落在 {tgt} 带，不是 auto_pass"))
            else:
                ok.append((e["word"], rk))

    for w, rk in ok:
        print(f"   ✅ {w:<22} → {rk}（auto_pass）")
    for w, rk, why in mismatched:
        print(f"   ❌ {w:<22} → {rk}：{why}")

    # ── 3. 隔离词的落点核对 ────────────────────────────────────────
    print()
    print("③ 隔离词落点核对（不得落在 auto_pass 带）")
    bad_q = []
    for e in wl["words"]:
        if e["status"] != "quarantined":
            continue
        w = e["word"].lower()
        for rk, r in rules.items():
            band_kw = {k.lower() for k in (r.get("downgrade_band") or {}).get("keywords", [])}
            if w in band_kw:
                tgt = band_target(r)
                flag = "❌" if tgt == "auto_pass" else "✅"
                if tgt == "auto_pass":
                    bad_q.append((e["word"], rk))
                print(f"   {flag} {e['word']:<12} → {rk}（{tgt}）")

    # ── 4. 无受益人的豁免（交给法务）────────────────────────────────
    print()
    print("④ ⚠ 无受益人的豁免 —— 14 词豁免了不存在的规则（需法务定夺，非代码可解）")
    print(f"   {missing}")
    print("   两种可能，必须由法务选：")
    print("     (a) 该词本就不需要豁免 → 应从白名单删除")
    print("     (b) 该词豁免的规则缺失  → 应补一条判定规则")
    print("   现状是 (a)(b) 都不做，词躺在白名单里给人「已经处理过」的错觉。")

    print()
    hard_fail = mismatched or bad_q
    if hard_fail:
        print(f"结论：❌ 接线不一致 {len(mismatched)} 处、隔离失效 {len(bad_q)} 处")
        return 1
    print(f"结论：✅ 接线全部一致（{len(ok)} 处）；{len(missing)} 词待法务定性")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
