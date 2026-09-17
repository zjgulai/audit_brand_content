#!/usr/bin/env python3
"""wire_context_guards.py —— 语境守卫与规则的接线（ADR-0009 / 决策 4 的实现）

修的是与「事故 B」同源的病：
现网把语境守卫塞在规则库的 `豁免词` 字段里，与 10 个白名单词共用字段。
`豁免词` 同时装着**两种机制**，靠词本身的语义区分 —— 而不是靠结构。
94 个条目里 84 个是守卫、10 个是白名单词，且**这个比例没有任何地方记着**。

本脚本做三件事：
  1. 把 6 条规则 `downgrade_band.keywords` 里的降级词搬出 rules-v1.json。
     搬迁后规则只保留 `effect`（声明通道落点），词表由 vocab.py 从独立表组装。
  2. **等价性验证**：搬迁后 `vocab.down_bands` 必须与搬迁前的带**逐词相同**。
     不等价就是行为变更，必须挡住 —— 否则「重构」会悄悄改判定。
  3. 报告 G3 违反（登记为守卫却走在 auto_pass 带）—— 这 4 个词属白名单机制。

★ 执行顺序：必须先跑 build_context_guards.py（它读搬迁前的带），再跑本脚本。

幂等：重复运行结果一致。

用法：
  python3 wire_context_guards.py            # 预演
  python3 wire_context_guards.py --apply    # 写回 rules-v1.json
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from vocab import load_vocab, band_target       # noqa: E402

RULES = HERE / "rules-v1.json"
GUARDS = HERE / "context-guards-v1.json"
BAK = HERE / "rules-v1.json.bak"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    G = json.loads(GUARDS.read_text())
    doc = json.loads(RULES.read_text())
    rules = {r["rule_key"]: r for r in doc["rules"]}

    # ── ① 搬迁 + 记录搬迁前的带（用于等价性验证） ────────────────────
    print("① 搬迁：把降级词从 rules-v1.json 取出，改由独立表装载")
    before = {}
    changed = 0
    for rk, r in sorted(rules.items()):
        band = r.get("downgrade_band") or {}
        kw = list(band.get("keywords") or [])
        if not kw:
            continue
        tgt = band_target(r)
        if tgt != "manual_review":
            # 放行带本次不动 —— 它归白名单表管，且含 4 个待裁定的 G3 词
            print(f"   ↷ {rk:28s} 落点 {tgt}，非降级带，本次不动（{len(kw)} 词）")
            continue
        before[rk] = {k.strip().lower() for k in kw}
        band["keywords"] = []
        band["$moved_to"] = "context-guards-v1.json"
        band["$moved_note"] = [
            "★ ADR-0009：本规则的降级词表已移出规则文件，改由 vocab.load_vocab() 组装。",
            f"原 {len(kw)} 词 → context-guards-v1.json（语境守卫表）"
            "；其中属白名单隔离词者（gentle/comfort）仍由 whitelist-v1.json 提供。",
            "理由与白名单同：词表留在规则文件里，任何『扫一遍所有关键词』的动作",
            "都会把降级词当成判险词 —— 而 `豁免词` 这份字段里还混着 10 个白名单词。",
            "本规则只保留 `effect` —— 它声明自己的通道落点，不含词。",
        ]
        changed += 1
        print(f"   {rk:28s} keywords {len(kw)} → 0")
    print(f"\n   共 {changed} 条规则、{sum(len(v) for v in before.values())} 个词位移交")

    if not a.apply:
        print("\n（未加 --apply，未写回；等价性验证需要写回后进行）")
        return 0

    if not BAK.exists():
        shutil.copy2(RULES, BAK)
        print(f"备份 → {BAK.name}")
    RULES.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    print(f"已写回 {RULES.name}")

    # ── ② 等价性验证：搬迁不得改变任何行为 ──────────────────────────
    print()
    print("② 等价性验证：搬迁后 vocab.down_bands 必须与搬迁前逐词相同")
    V = load_vocab()
    bad = 0
    for rk, old in sorted(before.items()):
        new = V.down_bands.get(rk, set())
        if new == old:
            print(f"   ✅ {rk:28s} {len(old)} 词，逐词一致")
        else:
            bad += 1
            print(f"   ❌ {rk:28s} 丢失 {sorted(old - new)} ／ 多出 {sorted(new - old)}")
    if not before:
        print("   （无搬迁，跳过）")

    # ── ③ G3 违反 ────────────────────────────────────────────────
    print()
    print("③ G3 违反（登记为守卫，实际走在放行通道）")
    g3 = [w for w in G["words"] if w.get("g3_violation")]
    if not g3:
        print("   ✅ 无")
    for w in g3:
        print(f"   ❌ {w['word']:<22} 占据 {w['g3_violation']} 的 auto_pass 带")
    if g3:
        print(f"   {len(g3)} 个词证成主张（事实/参数），属**白名单**机制。")
        print("   处置需 Owner/法务定：移入白名单表，或从豁免词中删除。")
        print("   本脚本**不动它们** —— 语义裁定不是开发者的权限（ADR-0008 §三）。")

    if bad:
        print(f"\n结论：❌ 等价性验证失败 {bad} 条 —— 行为已变，需人工核对")
        return 1
    print(f"\n结论：✅ 搬迁等价（{len(before)} 条规则逐词一致），G3 待裁定 {len(g3)} 词")
    return 0


if __name__ == "__main__":
    sys.exit(main())
