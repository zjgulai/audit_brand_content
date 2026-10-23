#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_combination_escalation.py —— 行 29：组合规则共现升级

## 对象在哪（先查再写）

组合规则**在仓里**：`research/governance/skeleton/rules-v1.json` 的
`T7.2.pain-scenario` 带 `escalation.when_cooccurring_with`（T1.5.duct-unclog /
T2.1.2.pain-relief）与 `to_severity: L4`、`to_disposition: auto_reject`；
读它的是 `research/governance/skeleton/score.py:466 _apply_escalation()`。

## 但在生产引擎里**没有这一层**

`base/rule_judge.py`（ADR-0016 的唯一生产判定引擎）全仓 `escalat` **0 命中** ——
也就是说：这条规则的数据写着「共现升级到 L4」，**生产判定不会升级**。
所以本脚本验的是**分析引擎**的行为；#29 **不映射**（映射会让验收表声称产品会升级）。

## 断言

| 段 | 断言 | 反向对照 |
|---|---|---|
| **C29-1** | 场景名词 + 消除性动词共现 → 源命中 `escalated=True`、severity 升到 `to_severity`、disposition 改成 `to_disposition` | 只给场景名词 → 不升级 |
| **C29-2** | 只含单个要素 → 不上调 | 共现但源规则**没有** escalation → 不上调 |
| **C29-3** | 升级来自**规则数据**而不是「只要有多个命中就升」：换一条没有 escalation 的源规则，同样共现也不升 | — |

退出码：0 / 1 / 2（导入失败）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKEL = ROOT / "research" / "governance" / "skeleton"
for p in (str(ROOT), str(SKEL)):
    if p not in sys.path:
        sys.path.insert(0, p)

RULES = SKEL / "rules-v1.json"
SOURCE = "T7.2.pain-scenario"


class Untested(Exception):
    pass


def _score():
    try:
        import score  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        raise Untested(f"导入 skeleton/score.py 失败：{type(e).__name__}: {e}")
    return score


def _rules():
    if not RULES.is_file():
        raise Untested(f"没有规则文件：{RULES}")
    try:
        return json.loads(RULES.read_text(encoding="utf-8"))["rules"]
    except Exception as e:  # noqa: BLE001
        raise Untested(f"读规则失败：{e}")


def _engine(score, rules):
    e = object.__new__(score.Engine)      # 只测 _apply_escalation，不跑完整引擎
    e.rules = rules
    return e


def _hit(score, key, sev, disp):
    return score.Hit(rule_key=key, parent_rule="H01", topic="T", severity=sev,
                     disposition=disp)


def check_escalation(score, rules) -> list[str]:
    problems = []
    src = next((r for r in rules if r["rule_key"] == SOURCE), None)
    if not src or "escalation" not in src:
        return [f"C29 规则数据里找不到 {SOURCE} 的 escalation —— 对象不在了"]
    esc = src["escalation"]
    others = esc["when_cooccurring_with"]
    # ★ 升级必须真的「上调」：to_severity 与源同档就不是升级。
    if esc.get("to_severity") == src.get("severity"):
        problems.append(
            f"C29 escalation.to_severity={esc.get('to_severity')!r} 与源 severity 同档 —— 没有真的上调")
    e = _engine(score, rules)

    # C29-1 共现 → 升级
    hits = [_hit(score, SOURCE, src["severity"], src.get("disposition", "")),
            _hit(score, others[0], "L2", "manual_review")]
    e._apply_escalation("...", hits)
    h = hits[0]
    if not h.escalated:
        problems.append(f"C29-1 共现（{SOURCE} + {others[0]}）没有触发升级")
    if h.severity != esc["to_severity"]:
        problems.append(f"C29-1 升级后 severity={h.severity!r}，预期 {esc['to_severity']!r}")
    if h.disposition != esc["to_disposition"]:
        problems.append(f"C29-1 升级后 disposition={h.disposition!r}，预期 {esc['to_disposition']!r}")
    if not h.escalation_reason:
        problems.append("C29-1 升级没有留下 escalation_reason")

    # C29-2a 只有源要素 → 不升
    solo = [_hit(score, SOURCE, src["severity"], src.get("disposition", ""))]
    e._apply_escalation("...", solo)
    if solo[0].escalated or solo[0].severity != src["severity"]:
        problems.append("C29-2a 只有场景名词也升级了 —— 升级来自「有多命中」而非共现规则")

    # C29-2b 只有另一个要素 → 不升
    other_only = [_hit(score, others[0], "L2", "manual_review")]
    e._apply_escalation("...", other_only)
    if other_only[0].escalated:
        problems.append("C29-2b 只有要素之一也升级了")

    # C29-3 共现但源规则没有 escalation → 不升（证明升级来自规则数据）
    stripped = [{k: v for k, v in r.items() if k != "escalation"} for r in rules]
    e2 = _engine(score, stripped)
    hits2 = [_hit(score, SOURCE, src["severity"], src.get("disposition", "")),
             _hit(score, others[0], "L2", "manual_review")]
    e2._apply_escalation("...", hits2)
    if hits2[0].escalated or hits2[0].severity != src["severity"]:
        problems.append("C29-3 把 escalation 从规则里拿掉后仍然升级了 —— 升级不是由规则数据驱动的")
    return problems


def production_gap() -> str:
    """生产引擎是否实现升级（今天是 0 命中）。返回一行事实描述。"""
    p = ROOT / "base" / "rule_judge.py"
    if not p.is_file():
        return "未测：没有 base/rule_judge.py"
    hits = p.read_text(encoding="utf-8").lower().count("escalat")
    return f"生产引擎 base/rule_judge.py 里 escalat 命中 {hits} 处"


def controls() -> int:
    try:
        score = _score()
        rules = _rules()
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        return 2
    bad = check_escalation(score, rules)
    # 反向对照：把源规则的 escalation 去掉后，共现不得升级（已在 C29-3 内）
    cases = [
        ("正样本：共现升级 + 单要素不升 + 无 escalation 不升",
         lambda: not bad),
        ("★ 坏样本：把 to_severity 改成 L2（与源同档）→ 判据必须能发现「没有真的上调」",
         lambda: _mutated(score, rules, to_severity="L2")),
    ]
    fail = 0
    print("=" * 78)
    print("行 29 · 组合规则共现升级（分析引擎 score.py，离线）")
    print("=" * 78)
    for i, (name, fn) in enumerate(cases, 1):
        try:
            ok, err = bool(fn()), ""
        except Exception as e:  # noqa: BLE001
            ok, err = False, f"（{type(e).__name__}: {e}）"
        if not ok:
            fail += 1
        print(f"  {'✅' if ok else '❌'} [{i}/{len(cases)}] {name}{err}")
    print("-" * 78)
    if fail:
        print(f"❌ {len(cases)} 项中 {fail} 项失败")
        return 1
    print(f"✅ {len(cases)} 项全过")
    return 0


def _mutated(score, rules, **patch) -> bool:
    """把源规则的 escalation 改掉后，判据必须报出问题。"""
    import copy
    mutated = copy.deepcopy(rules)
    for r in mutated:
        if r["rule_key"] == SOURCE:
            r["escalation"].update(patch)
    return bool(check_escalation(score, mutated))


def main(argv: list[str]) -> int:
    if "--controls" in argv:
        return controls()
    try:
        score = _score()
        rules = _rules()
        problems = check_escalation(score, rules)
    except Untested as e:
        print(f"⚠️ 未测：{e}")
        return 2
    print("=" * 78)
    print("行 29 · 组合规则共现升级")
    print("=" * 78)
    print(f"  数据：{RULES.relative_to(ROOT)} 的 {SOURCE}.escalation")
    print(f"  {production_gap()}")
    if problems:
        for p in problems:
            print(f"  ❌ {p}")
        print(f"\n❌ 退 1：{len(problems)} 处不成立")
        return 1
    print("✅ 退 0：共现升级、单要素不升、去掉 escalation 不升（三侧都成立）。")
    print("   ⚠️ 这只覆盖**分析引擎**；生产引擎没有 escalation 实现，#29 不映射。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001
        print(f"⚠️ 未测：{type(exc).__name__}: {exc}")
        sys.exit(2)
