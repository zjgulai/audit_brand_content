#!/usr/bin/env python3
"""lint_whitelist.py —— 白名单三项不变量机检（ADR-0008）

三项不变量（全部可机检，任一违反即 exit 1）：

  W1  disjointness  没有任何 active 白名单词出现在判定规则的检测词表中
                    ← 违反即「安全」去证明「有风险」。本项目实测 56/57 条误报源于此。
  W2  attribution   每个 active 白名单词必须在**某个通道**（放行或降级）里有受益人
                    ← 违反即「没有受益人的豁免」：加了不生效，或是一条未登记的例外。
                    ★ 两个通道都算（D9）：一个词从放行带移到降级带，仍然在做事。
  W3  quarantine    被隔离的词不得出现在任何 exempts 中
                    ← 违反即隔离失效。

  W4  channel       同一词不得在同一条规则里既落放行又落降级
                    ← 违反即两条通道互相抵消。

  W5  band-registry 规则**声明**的带词 与 运行时**取到**的带词 必须一致（双向）
                    ← W5a 死声明：规则写了 `downgrade_band.keywords`，白名单表没登记
                       → 运行时取不到，行为与「没声明」完全一样，且无任何提示。
                       这正是事故 B（26 词只有 10 词抄到）的**同型复发**，
                       只不过这次「抄漏」的地方换成了白名单表。
                    ← W5b 凭空例外：白名单登记了某词、规则里没声明
                       → 一条没人知道的豁免，读规则文件的人永远看不到它。

  W6  override      逐词落点覆盖（`keyword_effect_overrides`）必须真的改变落点
                    ← W6a 死覆盖：覆盖的词不在 `keywords` 里 → 永不参与判定
                    ← W6b 空改动：覆盖落点与规则默认相同 → 伪装成改动的空改动
                    ← W6c 非法落点：不是四档之一 → 会被静默丢弃

  ★ W5 为什么是这次迁移的检出处：迁移前 `T6.1` / `T2.2.quiet-claim` /
    `T2.2.suction-claim` 三条规则共 4 个带词是死的（`FDA 注册` / `silent mode` /
    `静音模式` / `suction settings`）。W5a 迁移前红、迁移后绿 —— 这是它的正对照。
  ★ W6 是同一个病的第二个入口（2026-09-16 · D9）：覆盖写错一个词名，或写成与默认
    相同的落点，行为与没写完全一样 —— 而评审时看得见一行新配置，会以为改动生效了。
    「看得见的新配置」比「看不见的缺失」更容易骗过人，所以它需要独立的机检。

W1 是本次事故的直接防复发项。事故成因不是某人疏忽，而是**结构上允许**
白名单与黑名单同表同字段：任何 `SELECT 检测关键词` 都会把两者拼在一起。

用法：
  python3 lint_whitelist.py                       # 检本地骨架
  python3 lint_whitelist.py --live                # 检现网快照（预期 W1 W2 失败 —— 这正是要修的）
  python3 lint_whitelist.py --live --json         # 机读输出
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
SNAPSHOT = ROOT / "research/live/snapshot-20260916T050845Z.json"
SAFE_TYPE = "安全词白名单"


def split_terms(raw):
    return [x.strip().lower() for x in re.split(r"[/,，;；\n]", raw or "") if x.strip()]


def load_live():
    """从现网快照装载：白名单词 与 判定规则词表 都取自同一张表 —— 事故的结构成因。"""
    snap = json.loads(SNAPSHOT.read_text())
    recs = snap["sources"]["boundary_rules"]["records"]
    wl_words, rule_kw, rule_ex = [], {}, {}
    for r in recs:
        f = r["fields"]
        rid = str(f.get("规则编号") or "").strip()
        if str(f.get("边界类型") or "").strip() == SAFE_TYPE:
            wl_words = split_terms(f.get("检测关键词"))
            continue
        rule_kw[rid] = set(split_terms(f.get("检测关键词")))
        rule_ex[rid] = set(split_terms(f.get("豁免词")))
    return wl_words, rule_kw, rule_ex, "live"


def band_target(rule, word=None):
    """`downgrade_band.effect` 箭头右侧 = 该带真正的落点通道。给 `word` 时逐词判。

    ★ 这是同一个病：一个 `downgrade_band` 字段承担「放行」与「降级」两条通道，
      靠 effect 里的字符串区分，而不是靠结构。此处把字符串解析出来，让检查可做。
    ★ 2026-09-16（D9）：落点可以逐词覆盖（`keyword_effect_overrides`），所以这里
      也必须逐词判 —— linter 若只看规则级 effect，`FDA registered` 会被当成放行词，
      而它实际落在降级带，于是 W5a 会把一次**正确的**迁移报成死声明（假红）。
      假红比不检更坏：它训练人忽略这个检查。
    """
    band = rule.get("downgrade_band") or {}
    eff = str(band.get("effect") or "").strip()
    if word is not None:
        # ★ D18：覆盖的键是「通道 → 词」（见 score.band_hits 的说明）
        ov = band.get("keyword_effect_overrides") or {}
        lw = str(word).strip().lower()
        kind = "downgrade" if lw in {str(x).strip().lower()
                                     for x in (band.get("keywords") or [])} else "pass"
        for k, v in (ov.get(kind) or {}).items():
            if isinstance(v, str) and str(k).strip().lower() == lw:
                eff = v.strip()
                break
    if "→" in eff:
        return eff.split("→")[-1].strip()
    return "none" if eff in ("none", "") else eff


def load_local():
    """从分离后的文件装载：三个来源物理分离（ADR-0008 / ADR-0009）。

    ★ 不再从规则文件读带 —— 规则文件已不持有任何词表（见 vocab.py）。
    """
    from vocab import load_vocab
    V = load_vocab()
    wl = {"words": V.whitelist}
    wl_words = [e["word"] for e in V.whitelist]
    active = {e["word"].lower(): e for e in V.whitelist if e["status"] == "active"}
    return wl_words, V.match, V.pass_bands, V.down_bands, "local", active, wl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="检现网快照而不是本地骨架")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    if a.live:
        wl_words, rule_kw, rule_ex, src = load_live()
        active = {w.lower(): None for w in wl_words}
        quarantined = set()
        rule_grant = rule_ex          # 现网 `豁免词` 就是放行通道
        rule_down = {}
        # W5 在现网**按构造为空**：现网只有 `豁免词` 一个字段，它同时是「声明」与
        # 「运行时取词」—— 没有两个东西可以比对。所以这里显式置空并在输出里说明，
        # 而不是给一个永远绿的假检查。
        band_decl, targets, w5_na = {}, {}, "现网无独立的带声明字段（`豁免词` 即运行时来源），W5 不适用"
        rules_by_key, w6_na = {}, "现网无逐词覆盖字段"
    else:
        wl_words, rule_kw, rule_grant, rule_down, src, active, wl = load_local()
        quarantined = {e["word"].lower() for e in wl["words"] if e["status"] == "quarantined"}
        # ★ W5 直接读原始文件，不经 vocab.load_vocab()：
        #   linter 若复用被测代码的装载器，装载器的 bug 会同时骗过检查与实现。
        from vocab import band_target as _bt
        _rd = json.loads((HERE / "rules-v1.json").read_text())
        rules_by_key = {r["rule_key"]: r for r in _rd["rules"]}
        band_decl = {r["rule_key"]: {str(k).strip().lower()
                                     for k in ((r.get("downgrade_band") or {}).get("keywords") or [])}
                     for r in _rd["rules"]}
        targets = {r["rule_key"]: _bt(r) for r in _rd["rules"]}
        w5_na = None
        w6_na = None

    fails = []

    # ── W1 disjointness ────────────────────────────────────────────
    w1 = []
    for w in wl_words:
        lw = w.lower()
        if lw in quarantined:
            continue
        for rid, kws in rule_kw.items():
            if lw in kws:
                w1.append({"word": w, "rule": rid})
    if w1:
        fails.append("W1")

    # ── W2 attribution ─────────────────────────────────────────────
    # ★ 判据是「有没有受益人」，所以**两个通道都算**（2026-09-16 · D9 修正）：
    #   原实现只看 `rule_grant`（=放行带），于是 `FDA registered` 被 D9 移入降级带后
    #   立刻变成假红 —— 它明明在 T6.1 上产生降级效果，却被算成「没有受益人」。
    #   这正是我上面给 W5a 修过的同一种错：**判据跟着通道走，而通道有两个**。
    #   假红比不检更坏：它训练人忽略这个检查。
    w2 = []
    for w in wl_words:
        lw = w.lower()
        if lw in quarantined:
            continue
        if not any(lw in g for g in rule_grant.values()) \
           and not any(lw in g for g in rule_down.values()):
            w2.append(w)
    if w2:
        fails.append("W2")

    # ── W3 quarantine ──────────────────────────────────────────────
    # ★ 边界：隔离词不得进入**放行**通道，但**可以**进入降级通道。
    #   gentle / comfort 正是如此：不给 H07 放行，只把 H07 从 auto_reject 降到 manual_review。
    w3 = []
    for w in quarantined:
        for rid, g in rule_grant.items():
            if w in g:
                w3.append({"word": w, "rule": rid, "channel": "grant"})
    if w3:
        fails.append("W3")

    # ── W4 通道唯一性：同一词不得在同一条规则里既落放行又落降级 ──────
    w4 = []
    for w in wl_words:
        lw = w.lower()
        g = {rid for rid, s in rule_grant.items() if lw in s}
        dn = {rid for rid, s in rule_down.items() if lw in s}
        for rid in g & dn:
            w4.append({"word": w, "rule": rid})
    if w4:
        fails.append("W4")

    # ── W5a 死声明：规则声明了带词，运行时取不到 ─────────────────────
    # 只在 target=auto_pass 的规则上检。target=manual_review 的规则**不在规则文件里
    # 声明带词**（实测 0 条声明），它们的降级词全部来自 context-guards 表 ——
    # 所以那一边没有「死声明」这个概念，检了会全是假红。
    # 会红的情况：有人在 rules-v1.json 的 downgrade_band.keywords 里加了一个词，
    # 却忘了在 whitelist-v1.json 登记它。
    # ★ 2026-09-16（D9）：判据从「在放行带里取得到」放宽为「**在某个带里取得到**」——
    #   逐词覆盖之后，一个 declared 词合法地落在降级带（`FDA registered` 就是）。
    #   放宽的是**通道**，不是**可达性**：声明了却在两个带里都取不到，仍然红。
    w5a = []
    for rid, decl in band_decl.items():
        if targets.get(rid) != "auto_pass":
            continue
        runtime = rule_grant.get(rid, set()) | rule_down.get(rid, set())
        for k in sorted(decl - runtime):
            w5a.append({"rule": rid, "word": k,
                        "channel": band_target(rules_by_key[rid], k)})
    if w5a:
        fails.append("W5a")

    # ── W5b 凭空例外：白名单登记了某词，规则里没声明 ─────────────────
    w5b = []
    for w in wl_words:
        lw = w.lower()
        for rid, s in rule_grant.items():
            if lw in s and targets.get(rid) == "auto_pass" and lw not in band_decl.get(rid, set()):
                w5b.append({"word": w, "rule": rid})
    if w5b:
        fails.append("W5b")

    # ── W6 逐词覆盖自洽（keyword_effect_overrides）──────────────────
    # ★ 与 W5 同一个病，换了个字段：**声明了但取不到**，行为与「没声明」一模一样。
    #   W5 抓的是「规则声明了带词、词表没登记」；W6 抓的是「覆盖声明了、词不在带里」。
    #   两种情况都长成一行的样子，也都不报错 —— 所以必须机检，不能靠读代码看出来。
    #   额外的 W6c 抓一种更坏的情况：覆盖写了、落点与默认相同 —— 伪装成改动的空改动。
    w6 = []
    if w6_na is None:
        for rid, r in rules_by_key.items():
            band = r.get("downgrade_band") or {}
            ov = band.get("keyword_effect_overrides") or {}
            if not ov:
                continue
            decl = band_decl.get(rid, set())
            default_target = targets.get(rid)
            for k, v in (ov.get("downgrade") or {}).items():
                kw = str(k).strip().lower()
                landed = band_target(r, k)
                if kw not in decl:
                    w6.append({"rule": rid, "word": k, "kind": "W6a 死覆盖",
                               "why": "覆盖的词不在 downgrade_band.keywords 里"})
                if landed == default_target:
                    w6.append({"rule": rid, "word": k, "kind": "W6b 空改动",
                               "why": f"覆盖落点与规则默认相同（{default_target}）"})
                if landed not in ("auto_pass", "manual_review", "auto_reject",
                                  "auto_pass_with_note"):
                    w6.append({"rule": rid, "word": k, "kind": "W6c 非法落点",
                               "why": f"落点 {landed!r} 不是四档之一"})
    if w6:
        fails.append("W6")

    if a.json:
        print(json.dumps({"source": src, "failures": fails,
                          "W1": w1, "W2": w2, "W3": w3, "W4": w4,
                          "W5a": w5a, "W5b": w5b, "W6": w6},
                         ensure_ascii=False, indent=2))
    else:
        print(f"白名单不变量机检 —— 来源：{'现网快照' if src == 'live' else '本地骨架'}")
        print(f"白名单词 {len(wl_words)} ｜ 判定规则 {len(rule_kw)} 条")
        print()

        print(f"W1｜disjointness（active 白名单词 ∩ 判险词表 = ∅）")
        if w1:
            print(f"   ❌ 违反 {len(w1)} 处 —— 「安全」正在证明「有风险」：")
            for x in w1:
                print(f"      {x['word']:<14} 同时是 {x['rule']} 的判险词")
        else:
            print("   ✅ 无交集")
        print()

        print("W2｜attribution（每个 active 词必须在**某个通道**里有受益人）")
        if w2:
            print(f"   ❌ 违反 {len(w2)} 词 —— 没有受益人的豁免（加了不生效）：")
            print(f"      {w2}")
        else:
            print("   ✅ 全部有明确放行目标")
        print()

        print("W3｜quarantine（隔离词不得进入放行通道；可进降级通道）")
        if w3:
            print(f"   ❌ 违反 {len(w3)} 处：{w3}")
        else:
            print("   ✅ 隔离词未进入放行通道")
        print()

        print("W4｜channel-exclusivity（同一词不得同时既放行又降级同一条规则）")
        if w4:
            print(f"   ❌ 违反 {len(w4)} 处：{w4}")
        else:
            print("   ✅ 放行与降级通道互斥")
        print()

        print("W5｜band-registry（规则声明的带词 = 运行时取到的带词）")
        if w5_na:
            print(f"   —— 不适用：{w5_na}")
        elif w5a or w5b:
            if w5a:
                print(f"   ❌ W5a 死声明 {len(w5a)} 处 —— 规则写了、白名单没登记，运行时取不到：")
                for x in w5a:
                    print(f"      {x['word']:<18} 声明于 {x['rule']}")
            if w5b:
                print(f"   ❌ W5b 凭空例外 {len(w5b)} 处 —— 白名单登记了、规则里没声明：")
                for x in w5b:
                    print(f"      {x['word']:<18} 放行 {x['rule']}")
        else:
            print("   ✅ 声明与运行时一致（双向）")
            print("      ★ 本项的正对照：迁移前 4 处死声明（W5a 红），迁移后归零。")
            print("      ★ D9 之后判据是「在**某个**带里取得到」：`FDA registered` 合法地落在降级带。")
        print()

        print("W6｜override-consistency（逐词覆盖 keyword_effect_overrides 必须真的改变落点）")
        if w6_na:
            print(f"   —— 不适用：{w6_na}")
        elif w6:
            print(f"   ❌ 违反 {len(w6)} 处：")
            for x in w6:
                print(f"      {x['kind']:<12} {x['word']:<18} @ {x['rule']} —— {x['why']}")
        else:
            print("   ✅ 每条覆盖都落在带内、且落点与默认不同")
            print("      ★ 本项的正对照：T6.1 的 `FDA registered` / `FDA 注册` 覆盖为 manual_review。")
        print()

        if fails:
            structural = [f for f in fails if f != "W2"]
            if structural:
                print(f"结论：❌ 结构回归 —— {len(structural)} 项不变量被违反（{' '.join(structural)}）")
            elif "W2" in fails:
                print(f"结论：⚠ 结构通过；W2 的 {len(w2)} 词是**法务待定**（不是代码缺陷）")
                print(f"      这 {len(w2)} 词**没有任何受益人**（豁免表为空，或指向的规则不存在）。")
                print("      需法务选：删除，或补一条规则 —— 加了不生效的豁免与没加是一样的。")
                print("      ★ 这个数字原先在输出里是写死的 14，与同一行算出的值不一致 ——")
                print("        一个印出来的数不等于它自己算出的数，就是最小的那种假账。")
        else:
            print("结论：✅ 六项不变量全部成立")

    # 退出码区分两类失败：1=结构回归（必须挡），2=政策待定（记录但不挡）
    structural = [f for f in fails if f != "W2"]
    if structural:
        return 1
    if "W2" in fails:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
