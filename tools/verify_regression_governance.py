#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tools/verify_regression_governance.py —— 验收表行 86 / SEC-6-GS-4 的**机器半边**

## 行原文（`PMO/audit/验收表-v3-覆盖全部判据-20261017.md:218`）

> 检查冻结回归集清单的 owner/维护记录**指向产品**；
> 逐条检查**涉及法规的条目**是否带法务确认记录（确认人 + 时间）。
> 确认签署的真实性无法从系统自动判定，需人工核对签署原件或审批流；
> 维护归属不清或法规条目无法务确认即红。

## 为什么单独一个文件，而不是并进 `verify_regression_set.py`

那一支已经映射到**行 85**（规模/陷阱/覆盖/指纹/变更门）。把行 86 的判据塞进去，
会让 #85 因为**不属于它的理由**变红 —— 那是「一个映射行承载两个判据」，
与 #132 那次不许映射的理由同形（映射的粒度不得粗于它要证明的那件事）。

## 两半，结论不同

| 行 86 的要求 | 本文件 | 当前读数 |
|---|---|---|
| ① owner / 维护记录**指向产品** | **G-OWNER** | ❌ **红**：保管人有，产品归属**未定** |
| ② 涉及法规的条目带法务确认（确认人 + 时间） | **G-LEGAL** | ❌ **红**：7 条涉及法规，**0 条**有确认 |
| ③ 签署的**真实性**要人核原件 | — | **无机器判据，如实留 manual** |

★ **这两条红不是缺陷，是行 86 该报出来的东西。**
  「没有人认领」与「没有人确认」如果不红，它们就永远不会被处理。

## 「涉及法规」的判据（**先定义，后测量**）

一条样本「涉及法规」⟺ 它在今天的引擎下命中的**任一规则**带非空 `external_ref`。

- 定义写进 `regression-set-v1.json` 的 `涉及法规_判据` 字段，与建集分开、可复核。
- ★ 它判的是**引擎视角**的「涉及法规」，不是**法务视角**的。
  一条样本可能内容上触及法规但今天没有规则覆盖它（本集合里 `no_rule_coverage` 那 49 条）——
  那些**不计入**。这个差异写在判据里，不假装覆盖了法务的全部口径。

## **本文件不证明什么**

* **不证明签署真实。** 有人把 `legal_confirmation` 填上 `{by: "法务", at: "..."}` 就能让它变绿 ——
  这一条**只能靠人核原件**。本文件只证明「字段在不在」，且结论行必须这么说。
* **不证明样本代表业务分布**（83 条为人工编写的通用广告语）。

## 退出码

  0 全过 · 1 有红 · 2 未测（回归集或规则表读不出）

## 用法

    python3 tools/verify_regression_governance.py
    python3 tools/verify_regression_governance.py --controls
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGRESSION = ROOT / "research" / "governance" / "regression-set-v1.json"
RULES = ROOT / "research" / "governance" / "skeleton" / "rules-v1.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "research" / "governance" / "skeleton") not in sys.path:
    sys.path.insert(0, str(ROOT / "research" / "governance" / "skeleton"))


# ── 纯判定函数（可被 --controls 单独喂样本）─────────────────────────────
def check_owner(reg):
    """G-OWNER：owner / 维护记录必须**指向产品**。返回问题列表。

    ★ 只写「当前保管人」不算通过 —— 保管人是「谁在盘上放这个文件」，
      行 86 要的是「谁对这份清单负责」，那是产品。
      两者混为一谈，就会出现「建集的人自动成了负责人」这种默认推定。
    """
    problems = []
    owner = reg.get("owner")
    if not isinstance(owner, dict):
        return ["回归集没有 owner 段 —— 行 86：维护归属不清即红"]

    product = owner.get("产品归属")
    if not product:
        problems.append(
            "owner.产品归属 为空（%r）—— 行 86 要求指向产品。"
            "原因记录：%s" % (product, str(owner.get("产品归属未定原因") or "（无记录）")[:120]))

    records = owner.get("维护记录")
    if not isinstance(records, list) or not records:
        problems.append("owner.维护记录 为空 —— 行 86 要求有维护记录")
    else:
        for i, r in enumerate(records):
            if not isinstance(r, dict):
                problems.append("维护记录[%d] 不是对象" % i)
                continue
            for k in ("at", "by", "what"):
                if not str(r.get(k) or "").strip():
                    problems.append("维护记录[%d] 缺 %s" % (i, k))
    return problems


def legal_rule_keys(rules_doc):
    """带 `external_ref` 的规则 —— 即「引用了外部标准库」的那些。"""
    return {r["rule_key"] for r in (rules_doc.get("rules") or [])
            if r.get("external_ref")}


def find_legal_samples(reg, rules_doc, judge_fn=None):
    """按**先定义的判据**找出「涉及法规」的样本。

    判据：命中任一 `external_ref` 非空的规则。
    `judge_fn` 可注入（--controls 用），默认走真引擎。
    """
    if judge_fn is None:
        import judge as J
        judge_fn = lambda text: J.judge(text, origin="test")  # noqa: E731
    legal_rules = legal_rule_keys(rules_doc)
    out = []
    for s in reg.get("samples") or []:
        try:
            res = judge_fn(s.get("text") or "")
        except Exception:  # noqa: BLE001
            continue
        hits = {h.get("rule_key") for h in (res.get("hits") or [])}
        touched = sorted(hits & legal_rules)
        if touched:
            out.append({"id": s.get("id"), "rules": touched,
                        "confirmation": s.get("legal_confirmation")})
    return out


def check_legal(legal_samples):
    """G-LEGAL：涉及法规的条目必须带 `legal_confirmation`（确认人 + 时间）。"""
    problems = []
    if not legal_samples:
        # ★ 零条也必须说清：是真的没有法规条目，还是判据失效了？
        return ["按判据算出的法规条目为 0 —— 要么集合里真的没有，"
                "要么「涉及法规」的判据已经失效（两种都要人看一眼，不许当绿）"]
    for s in legal_samples:
        c = s.get("confirmation")
        if not isinstance(c, dict):
            problems.append("%s 涉及法规（%r）但没有 legal_confirmation"
                            % (s["id"], s["rules"]))
            continue
        for k in ("by", "at"):
            if not str(c.get(k) or "").strip():
                problems.append("%s 的 legal_confirmation 缺 %s" % (s["id"], k))
    return problems


# ── 主检查 ────────────────────────────────────────────────────────────
def main() -> int:
    results = []

    def check(cid, ok, msg):
        results.append((cid, bool(ok), msg))
        print(("  ✅ " if ok else "  ❌ ") + cid + "  " + msg)

    print("=" * 72)
    print("行 86 / SEC-6-GS-4 · 回归集维护归属与法务确认（**机器半边**）")
    print("=" * 72)

    if not REGRESSION.exists() or not RULES.exists():
        print("  ⚠ 读不到回归集或规则表 —— 未测，不是通过")
        return 2
    try:
        reg = json.loads(REGRESSION.read_text(encoding="utf-8"))
        rules = json.loads(RULES.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("  ⚠ 解析失败：%s —— 未测" % exc)
        return 2

    own = check_owner(reg)
    check("G-OWNER", not own, "owner 指向产品，且维护记录三项齐全"
          if not own else str(own[:2]))

    try:
        legal = find_legal_samples(reg, rules)
    except Exception as exc:  # noqa: BLE001
        print("  ⚠ 引擎跑不起来：%s —— G-LEGAL 未测" % exc)
        return 2

    leg = check_legal(legal)
    check("G-LEGAL", not leg,
          "涉及法规的 %d 条都带 legal_confirmation" % len(legal)
          if not leg else
          "%d 条涉及法规，%d 条有问题：%s"
          % (len(legal), len([p for p in leg if 'legal_confirmation' in p]), leg[:2]))

    print("-" * 72)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = len(results) - passed
    print("  共 %d 项 · 通过 %d · 失败 %d" % (len(results), passed, failed))
    if failed:
        print("  ❌ 退 1（有红）")
        print("     ★ 这两条红**不是缺陷，是行 86 该报出来的东西**：")
        print("       没有人认领 → 维护归属不清；没有人确认 → 法规条目无法务确认。")
        print("       它们如果不红，就永远不会被处理。")
        return 1
    print("  ✅ 全过 —— 只证明：owner 字段指向产品、涉及法规的条目都填了")
    print("     `legal_confirmation`。")
    print("     ★ **不证明签署真实** —— 有人填上 {by, at} 就能让它变绿，")
    print("       这一条只能靠人核原件或审批流。行 86 的 ③ 如实留 manual。")
    return 0


# ── --controls ────────────────────────────────────────────────────────
def run_controls() -> int:
    """反向对照。**每条先写预判、再跑、并列贴出。**"""
    if not REGRESSION.exists() or not RULES.exists():
        print("  ⚠ 真源缺失 —— 未测")
        return 2
    reg = json.loads(REGRESSION.read_text(encoding="utf-8"))
    rules = json.loads(RULES.read_text(encoding="utf-8"))

    ok_owner = {"产品归属": "产品（委托方）", "维护记录": [
        {"at": "2026-10-22", "by": "x", "what": "建集"}]}
    legal = [{"id": "S1", "rules": ["T1.1.medical-cure"], "confirmation": None}]
    legal_ok = [{"id": "S1", "rules": ["T1.1.medical-cure"],
                 "confirmation": {"by": "法务", "at": "2026-10-22"}}]

    # 注入式判官：让 --controls 不依赖真引擎（真引擎结果会随规则库变）
    def fake_judge_factory(hit_map):
        def f(text):
            return {"hits": [{"rule_key": k} for k in hit_map.get(text, [])]}
        return f

    cases = [
        ("好样本：owner 指向产品 + 维护记录齐全",
         False, lambda: check_owner({"owner": ok_owner})),
        ("坏样本：没有 owner 段",
         True, lambda: check_owner({})),
        ("坏样本：产品归属为空（当前真实状态）",
         True, lambda: check_owner({"owner": dict(ok_owner, 产品归属=None)})),
        ("坏样本：维护记录为空",
         True, lambda: check_owner({"owner": dict(ok_owner, 维护记录=[])})),
        ("坏样本：维护记录缺 at",
         True, lambda: check_owner({"owner": dict(
             ok_owner, 维护记录=[{"by": "x", "what": "y"}])})),

        ("好样本：法规条目都带确认",
         False, lambda: check_legal(legal_ok)),
        ("坏样本：法规条目没有确认（当前真实状态）",
         True, lambda: check_legal(legal)),
        ("坏样本：确认缺 at",
         True, lambda: check_legal([{"id": "S1", "rules": ["R"],
                                     "confirmation": {"by": "法务"}}])),
        ("★ 坏样本：法规条目为 0 也要红（判据可能失效）",
         True, lambda: check_legal([])),

        # ★ 「涉及法规」判据本身：成对
        ("★ 命中 external_ref 规则 → 判为涉及法规",
         True, lambda: [
             s for s in find_legal_samples(
                 {"samples": [{"id": "A", "text": "x"}]}, rules,
                 judge_fn=fake_judge_factory({"x": ["T1.1.medical-cure"]}))
             if s["id"] == "A"]),
        ("★ 只命中无 external_ref 的规则 → 不算涉及法规",
         False, lambda: [
             s for s in find_legal_samples(
                 {"samples": [{"id": "B", "text": "y"}]}, rules,
                 judge_fn=fake_judge_factory({"y": ["T10.1.enjoy-every-moment"]}))
             if s["id"] == "B"]),
    ]

    print("=" * 72)
    print("verify_regression_governance · --controls（预判 vs 实测并列）")
    print("=" * 72)
    print("  %-46s %-6s %-6s %s" % ("样本", "预判", "实测", "一致"))
    print("  " + "-" * 64)
    bad = 0
    for name, want_red, fn in cases:
        try:
            problems = fn()
            got_red = bool(problems)
            note = "" if got_red == want_red else "  ← " + str(problems[:2])[:80]
        except Exception as exc:  # noqa: BLE001
            got_red, note = None, "  对照自身异常：%s" % exc
        ok = (got_red is not None and got_red == want_red)
        bad += int(not ok)
        print("  %-46s %-6s %-6s %s%s"
              % (name[:46],
                 "红" if want_red else "绿",
                 "异常" if got_red is None else ("红" if got_red else "绿"),
                 "✓" if ok else "✗", note))

    print("-" * 72)
    if bad:
        print("❌ %d/%d 与预判不符 —— 差异那几行就是该查的地方" % (bad, len(cases)))
        return 1
    print("✅ %d/%d 预判全部命中" % (len(cases), len(cases)))
    return 0


def _parse_args(argv):
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument("--controls", action="store_true")
    args, unknown = ap.parse_known_args(argv)
    if unknown:
        print("  ⚠ 未知参数 %s —— 未测（不是通过）" % unknown)
        raise SystemExit(2)
    return args


if __name__ == "__main__":
    try:
        a = _parse_args(sys.argv[1:])
        sys.exit(run_controls() if a.controls else main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s: %s" % (type(exc).__name__, exc))
        sys.exit(2)
