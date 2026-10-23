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

  0 全过 · 1 有红 · 2 未测（回归集或规则表读不出 / 人工台账未签）

  三条分支的语义（`main()` 里逐一实现，`--controls` 各有一条退出码对照）：

  | 条件 | 退出码 |
  |---|---|
  | 机器半边（G-OWNER / G-LEGAL）有红 | **1** 红 |
  | 机器半边全绿 + 人工台账**未签** | **2** 未测 |
  | 机器半边全绿 + 台账全签 | **0** 通过 |

## ⚠️ 本文件今天**没有映射进 `verifier_map`** —— 而台账里的读数是错的

**这是一个必须写下来、否则下一个人看不到的状态**（与 `waiver-v1.json` 的「未闭项-触发点」
同一个动作：一个只在对话里存在的状态，下一个人看不到）。

1. **`untested` 那一栏对 #86 说的是错的。**
   它显示「缺 test_id / fixture / command」，读起来像**执行点还没建**。
   而实际上：**判据已建好、`--controls` 15/15 过、三条退出码分支都在跑。**
   缺的只是 `verifier_map` 里那一行。

2. **为什么不映射**（2026-10-23 实测，不是推测）：
   本文件的机器半边**今天就是红的**（`G-OWNER` 产品归属未定、`G-LEGAL` 7 条法规条目
   0 条 `legal_confirmation`），所以 `main()` 走第一条分支退 **1**。
   映射之后 runner 记 `FAILED #86 exit=1`，而
   **`verify_acceptance_ratchet.py` 要求 `failed == 0`** —— 整条棘轮红。

   ```
   $ .venv/bin/python tools/verify_acceptance_ratchet.py --run
   ❌ failed=1 —— 有红的验收项，一条都不许合入
   ```

   ★ 曾经考虑过「红也退 2」来绕过 —— **否决**。
     那会把两条**真缺口**（没有人认领 owner、法规条目没有法务确认）藏进「未测」，
     而「未测」在台账里读起来只是「还没做」，不像「这里有问题」。
     **把红伪装成未测，比不映射糟得多。**

3. **什么时候会变**：下面两件事到位之后，机器半边转绿 → 映射自然生效，
   那时它会走「退 2（未签）」那条分支 —— 正是设计的行为。
   - `owner.产品归属`：需要**产品 / 委托方书面认领**（不是我们能填的）
   - 7 条法规条目的 `legal_confirmation`：需要**法务逐条确认**（同样不是我们能填的）

   这两项的人工签收落点是 `research/governance/regression-set-manual-v1.json`
   （4 条，现状全部 `not_run`）。

## 用法

    python3 tools/verify_regression_governance.py
    python3 tools/verify_regression_governance.py --controls

## 已知盲区

* 本文件判的是**引擎视角**的「涉及法规」（命中带 `external_ref` 的规则），
  不是**法务视角**的 —— 一条样本可能在内容上触及法规但今天没有规则覆盖它
  （本集合里 `no_rule_coverage` 那 49 条），那些**不计入**。
* 人工台账里填了 `{by, at}` 就会让它变绿 —— 本文件**不验证签署真实性**，
  那一格只能靠人核原件或审批流。
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


# ── 人工签收台账（行 86 的 ③：签署真实性只能人核原件）───────────────────
MANUAL_LEDGER = ROOT / "research" / "governance" / "regression-set-manual-v1.json"

#: `--controls` 用的哨兵：表示「这一格故意不给文件」，与「给了 None」不同。
#: ★ 用独立哨兵而不是 None：None 是合法输入（表示用默认台账），
#:   把两者混成一个值，就分不出「没传」与「传了个空」—— 本轮第 4 次同类错。
_MISSING = object()


def check_manual(path=None):
    """读人工签收台账。返回 (problems, n_total, n_signed)。

    `problems is None` → 台账读不出（调用方落**退 2**，不是红）。
    `problems == []`   → 全部已签。

    ★ 判据照抄 `web/a11y-manual-v1.json` 那一套：
      `status ∈ accept_status` **且** `evidence` / `owner` / `date` 三项非空才算签收。
      其余一律算**未测**（退 2），不算红、也不算通过。

    ★ 为什么「未签」是退 2 而不是退 0：
      行 86 的 ③「签署真实性」没有机器判据。把它算绿，等于说「没签 = 签了」。
      而 runner 读退 2 会记 `命令退 2（未测）`，**不会冒充 passed**。
    """
    p = Path(path) if path is not None else MANUAL_LEDGER
    if not p.is_file():
        return None, 0, 0
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None, 0, 0
    if not isinstance(d, dict):
        return None, 0, 0
    items = d.get("items")
    accept = d.get("accept_status")
    if not isinstance(items, list) or not items or not isinstance(accept, list):
        return None, 0, 0

    problems, signed = [], 0
    for it in items:
        if not isinstance(it, dict):
            problems.append("台账条目不是对象")
            continue
        name = str(it.get("item") or "（未命名）")
        if it.get("status") in accept and all(
                str(it.get(k) or "").strip() for k in ("evidence", "owner", "date")):
            signed += 1
        else:
            problems.append("%s（status=%r）" % (name, it.get("status")))
    return problems, len(items), signed


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
def main(regression_path=None, rules_path=None, manual_path=None) -> int:
    """三条分支，每条都要能被 `--controls` 反向对照 —— 所以路径可注入。

    | 分支 | 条件 | 退出码 |
    |---|---|---|
    | 红 | 机器半边（G-OWNER / G-LEGAL）有红 | **1** |
    | 未测 | 机器半边全绿，但人工台账**未签** | **2** |
    | 绿 | 机器半边全绿 + 台账全签 | **0** |
    """
    results = []
    REG = Path(regression_path) if regression_path else REGRESSION
    RUL = Path(rules_path) if rules_path else RULES

    def check(cid, ok, msg):
        results.append((cid, bool(ok), msg))
        print(("  ✅ " if ok else "  ❌ ") + cid + "  " + msg)

    print("=" * 72)
    print("行 86 / SEC-6-GS-4 · 回归集维护归属与法务确认（**机器半边**）")
    print("=" * 72)

    if not REG.exists() or not RUL.exists():
        print("  ⚠ 读不到回归集或规则表 —— 未测，不是通过")
        return 2
    try:
        reg = json.loads(REG.read_text(encoding="utf-8"))
        rules = json.loads(RUL.read_text(encoding="utf-8"))
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

    # ── 机器半边过了，但**人工签收没做** → 退 2（未测），不是退 0 ──────────
    #   ★ 2026-10-23（05 裁定，按 #112 的模式）：
    #
    #   映射的风险**不是「后半没验」，是「runner 报 passed 而读者以为全验了」**。
    #   行 86 的 ③「签署真实性要人核原件」**没有任何机器判据** ——
    #   有人把 `legal_confirmation` 填上 {by, at} 就能让 G-LEGAL 变绿，
    #   而那证明不了签名是真的。
    #
    #   所以：机器半边全绿 + 人工台账未签 → **退 2**。
    #   runner 会把它记成 `命令退 2（未测）`，落在 `untested_origin: executed_rc2`，
    #   **不会冒充 passed**。
    #
    #   ★ 两种退 2 含义相反，结论行必须分开写：
    #     · 「机器半边坏了」→ 退 1，是红
    #     · 「机器半边过了、签署没做」→ 退 2，是未测
    #   把后者写成前者会让人去查一个没坏的机器半边；
    #   把后者写成退 0 会让「没签」看起来像「签了」。
    manual_problems, n_total, n_signed = check_manual(manual_path)
    if manual_problems is None:
        print("  ⚠ 退 2：人工签收台账读不出 —— 未测（不是通过，也不是红）")
        return 2
    if manual_problems:
        print("  ⚠ **机器半边已过，但人工签收未完成** → 退 2（未测，不是通过）")
        print("     已签 %d / %d 项。未签的：" % (n_signed, n_total))
        for p in manual_problems[:6]:
            print("       · %s" % p)
        print()
        print("     ★ 这次退 2 的原因是**签署未做**，不是机器半边坏了 ——")
        print("       两种退 2 含义相反：前者去催人，后者去查代码。")
        print("       行 86 的 ③「签署真实性」只能人核原件或审批流。")
        return 2

    print("  ✅ 全过 —— 机器半边（owner 指向产品、法规条目填了 legal_confirmation）")
    print("     + 人工签收台账 %d/%d 已签（含签署真实性核对）。" % (n_signed, n_total))
    print("     ★ 仍**不证明**签署本身是真的 —— 台账是人写的，")
    print("       它证明的是「有人对着原件核过并留下了姓名/日期/证据指针」。")
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

    # ── 三条**退出码**分支的反向对照 ────────────────────────────────────
    #   ★ 上面那组比的是「问题列表空不空」，这一组比的是 **main() 的退出码**。
    #     两者不能混用：`check_*` 返回问题列表，而分支语义是 0/1/2 三态。
    #     （这正是本轮第 4 次「符号语义错位」的教训：`[]` 不等于「红」，
    #       而「有红」也不等于「退 1」—— 退 2 也是一种非零。）
    #
    #   三条分支各要一条对照，缺一条就有一个方向恒真：
    #     · 机器有红 → 1
    #     · 机器全绿 + 未签 → **2**（关键：不能是 0）
    #     · 机器全绿 + 全签 → 0
    import tempfile as _tf
    code_cases = []

    def _mk(reg_obj, manual_obj):
        td = _tf.mkdtemp(prefix="rgv-ctl-")
        rp = Path(td) / "reg.json"
        mp = Path(td) / "manual.json"
        rp.write_text(json.dumps(reg_obj, ensure_ascii=False), encoding="utf-8")
        if manual_obj is _MISSING:
            mp = Path(td) / "nope.json"          # 不给文件 → 读不出
        elif manual_obj is not None:
            mp.write_text(json.dumps(manual_obj, ensure_ascii=False), encoding="utf-8")
        return rp, mp

    # ★ 2026-10-23 修一处我自己的夹具错误：第一版 `good_reg` 的样本是 `"x"`，
    #   它**命中不了任何规则** → G-LEGAL 判「0 条涉及法规 → 红」，
    #   于是三条本该走到「人工台账」分支的用例全部退 1，看起来像分支写错了。
    #   实际是**夹具没有造出「机器半边全绿」这个前提**。
    #   现在用一个真能命中 `T1.1.medical-cure`（带 external_ref）的句子，
    #   并给它 `legal_confirmation`，这样 G-OWNER 与 G-LEGAL 才都是绿的。
    _LEGAL_TEXT = "This breast pump cures mastitis"
    good_reg = {
        "samples": [{"id": "S1", "text": _LEGAL_TEXT,
                     "legal_confirmation": {"by": "法务", "at": "2026-10-22"}}],
        "owner": {"产品归属": "产品（委托方）",
                  "维护记录": [{"at": "2026-10-22", "by": "x", "what": "建集"}]},
    }
    bad_reg = {"samples": [{"id": "S1", "text": _LEGAL_TEXT}],
               "owner": {"产品归属": None}}
    unsigned = {"accept_status": ["signed"], "items": [
        {"item": "a", "status": "not_run", "evidence": "", "owner": "", "date": ""}]}
    signed = {"accept_status": ["signed"], "items": [
        {"item": "a", "status": "signed", "evidence": "原件-001",
         "owner": "张三", "date": "2026-10-23"}]}

    def _run(reg_obj, manual_obj, want_code, name, expect_exit):
        rp, mp = _mk(reg_obj, manual_obj)
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            got = main(regression_path=rp, rules_path=RULES, manual_path=mp)
        code_cases.append((name, expect_exit, got))

    _run(bad_reg, None, 1, "★ 机器半边有红 → 必须退 1", 1)
    _run(good_reg, unsigned, 2, "★★ 机器全绿但人工台账未签 → 必须退 2（不是 0）", 2)
    _run(good_reg, signed, 0, "★ 机器全绿 + 台账全签 → 必须退 0", 0)
    _run(good_reg, _MISSING, 2, "★ 人工台账读不出 → 必须退 2（未测）", 2)

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
    print("  三条退出码分支（0 / 1 / 2）")
    print("  " + "-" * 64)
    for name, want, got in code_cases:
        ok = (want == got)
        bad += int(not ok)
        print("  %-46s %-6s %-6s %s"
              % (name[:46], "退 %d" % want, "退 %d" % got, "✓" if ok else "✗"))

    print("-" * 72)
    if bad:
        print("❌ %d 项与预判不符 —— 差异那几行就是该查的地方" % bad)
        return 1
    print("✅ 全部预判命中：%d 条问题列表对照 + %d 条退出码分支对照"
          % (len(cases), len(code_cases)))
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
