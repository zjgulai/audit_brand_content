#!/usr/bin/env python3
"""lint_context_guards.py —— 语境守卫五项不变量机检（ADR-0009 / 决策 4）

五项不变量（任一结构项违反即 exit 1）：

  G1 disjointness  没有任何 active 守卫词出现在判定规则的 match.keywords 中
                   ← 违反即「否定表述本身被判险」：
                     `does not cure` 触发 `cure` 规则、又拿不到降级信号 → 误报。
  G2 attribution   每个守卫词必须声明至少一条 downgrades（否则是死重：加了不生效）
  G3 direction     守卫词只允许落 manual_review 带；**落 auto_pass 带即违反**
                   ★ G3 是白名单与本表的结构分界：守卫绝不放行。
  G4 cross-table   守卫词不得与**未隔离**的白名单词重名
                   （隔离的白名单词可以走降级通道 —— 这是 W3 的边界，不是违反）
  G5 wiring        wired=false 的守卫不计入失败，但每条必须给出 wire_gap 成因

退出码区分三类结果（与 lint_whitelist.py 同口径）：
  0 = 全部成立   1 = 结构回归（必须挡）   2 = 政策待定（记录但不挡）

用法：
  python3 lint_context_guards.py
  python3 lint_context_guards.py --json
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def band_target(rule):
    eff = str((rule.get("downgrade_band") or {}).get("effect") or "").strip()
    return eff.split("→")[-1].strip() if "→" in eff else ("none" if eff in ("none", "") else eff)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    G = json.loads((HERE / "context-guards-v1.json").read_text())
    W = json.loads((HERE / "whitelist-v1.json").read_text())
    rules = json.loads((HERE / "rules-v1.json").read_text())["rules"]
    guards = G["words"]
    gset = {w["word"].lower(): w for w in guards}
    active_guards = {k: v for k, v in gset.items() if v.get("status") == "active"}

    rule_kw = {r["rule_key"]: {k.lower() for k in (r.get("match") or {}).get("keywords", [])}
               for r in rules}
    at_pass = {r["rule_key"] for r in rules if band_target(r) == "auto_pass"}
    at_down = {r["rule_key"] for r in rules if band_target(r) == "manual_review"}

    wl_active = {w["word"].lower() for w in W["words"] if w["status"] == "active"}
    wl_quar = {w["word"].lower() for w in W["words"] if w["status"] == "quarantined"}

    fails = []

    # ── G1 disjointness ────────────────────────────────────────────
    g1 = [{"word": w, "rule": rk} for w, e in active_guards.items()
          for rk, kws in rule_kw.items() if w in kws]
    if g1:
        fails.append("G1")

    # ── G2 attribution ─────────────────────────────────────────────
    g2 = [e["word"] for e in active_guards.values()
          if not [t for t in e.get("downgrades") or [] if t in rule_kw]]
    if g2:
        fails.append("G2")

    # ── G3 direction：守卫不得落放行带（覆盖全部守卫，含待裁定词） ────
    g3 = [{"word": e["word"], "rule": rk, "status": e.get("status")}
          for e in gset.values()
          for rk in e.get("downgrades") or [] if rk in at_pass]
    if g3:
        fails.append("G3")

    # ── G4 cross-table ─────────────────────────────────────────────
    g4 = [{"word": e["word"], "clash": "active 白名单词"}
          for w, e in active_guards.items() if w in wl_active]
    if g4:
        fails.append("G4")

    # ── G5 wiring（政策项，不挡） ───────────────────────────────────
    g5 = [{"word": e["word"], "gap": e.get("wire_gap"), "status": e.get("status")}
          for e in gset.values() if e.get("status") != "active"]
    if g5:
        fails.append("G5")

    # 交叉核对：守卫表声称的方向必须与规则带的方向一致
    drift = []
    for e in active_guards.values():
        for rk in e.get("downgrades") or []:
            if rk not in rule_kw:
                continue
            if e.get("wired") and rk not in at_down:
                drift.append({"word": e["word"], "rule": rk,
                              "declared": "downgrade", "actual": "not-a-downgrade-band"})
    if drift:
        fails.append("G3-drift")

    if a.json:
        print(json.dumps({"failures": fails, "G1": g1, "G2": g2, "G3": g3,
                          "G4": g4, "G5": g5, "drift": drift}, ensure_ascii=False, indent=2))
    else:
        print("语境守卫不变量机检 —— 来源：context-guards-v1.json（独立表）")
        from collections import Counter as _C
        st = _C(e.get("status") for e in guards)
        print(f"守卫词 {len(guards)}（active {st['active']} / pending {st['pending']} / "
              f"misrouted {st['misrouted']}）｜ 判定规则 {len(rule_kw)} 条 ｜ "
              f"放行带 {len(at_pass)} 条 / 降级带 {len(at_down)} 条")
        print()

        print("G1｜disjointness（守卫词 ∩ 判险词表 = ∅）")
        if g1:
            print(f"   ❌ 违反 {len(g1)} 处 ——「否定表述本身被判险」：")
            for x in g1:
                print(f"      {x['word']:<22} 同时是 {x['rule']} 的判险词")
        else:
            print("   ✅ 无交集")
        print()

        print("G2｜attribution（每个守卫词必须声明至少一条降级目标）")
        print(f"   ❌ 违反 {len(g2)} 词：{g2}" if g2 else "   ✅ 全部有明确降级目标")
        print()

        print("G3｜direction（守卫只允许落 manual_review 带 —— **绝不放行**）")
        if g3:
            print(f"   ❌ 违反 {len(g3)} 处 —— 登记为守卫却走在放行通道：")
            for x in g3:
                print(f"      {x['word']:<22} 落在 {x['rule']} 的 auto_pass 带")
            print("      这 4 个词证成主张（事实/参数），属**白名单**机制，走错了通道。")
        else:
            print("   ✅ 守卫未进入任何放行带")
        print()

        print("G4｜cross-table（守卫词不得与 active 白名单词重名）")
        print(f"   ❌ 违反 {len(g4)} 处：{g4}" if g4 else "   ✅ 与白名单表无重名")
        print()

        print("G5｜wiring（未接线的守卫必须逐条给出成因）")
        if g5:
            from collections import Counter
            cnt = Counter(x["gap"].split("——")[0] for x in g5)
            print(f"   ⚠ 非 active {len(g5)} 词：")
            for k, v in cnt.most_common():
                print(f"      {v:3d}  {k}")
            print("      这不是代码缺陷 —— 是需法务/Owner 定性的接线缺口。")
        else:
            print("   ✅ 全部守卫已接线")
        print()

        if drift:
            print(f"G3-drift｜声明方向与规则带不一致 {len(drift)} 处：{drift}")
            print()

        structural = [f for f in fails if f != "G5"]
        if structural:
            print(f"结论：❌ 结构回归 —— {len(structural)} 项不变量被违反（{' '.join(structural)}）")
        elif "G5" in fails:
            print(f"结论：⚠ 结构通过；G5 的 {len(g5)} 词是**接线缺口**（不是代码缺陷）")
        else:
            print("结论：✅ 五项不变量全部成立")

    structural = [f for f in fails if f != "G5"]
    if structural:
        return 1
    if "G5" in fails:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
