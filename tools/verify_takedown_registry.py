#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_takedown_registry.py - T-312a: takedown tasks into authority.

## Why this file exists before the implementation

Measured 2026-10-24: production has **no way to create a takedown task**.
All 7 takedown routes in `api/review_api.WRITE_PATHS` are transitions
(start/complete/fail/retry/reassign/waive) plus a GET. And:

    grep should_create_task / new_task / notify_created / metrics_view
    -> production consumers: 0 each (only tools/verify_takedown.py)

So rows #95-#101 can be green while production cannot produce a single task
object. T0 below goes red first (AGENTS.md 2.1).

## Coverage

  T0  takedown_create / takedown_transition exist in reducer
  T1  create lands in state["takedown_tasks"] with content-derived task_id
  T2  duplicate create (same case + trigger, unfinished) rejected
  T3  trigger is required and must be revoke/invalidated
  T4  transition delegates to base.takedown.check_transition (ONE transition table)
  T5  no deadline field survives (RL-8)
  T6  task survives in the event snapshot (replay keeps it)
  T7  per-task version increments on each transition
  T8  trigger/reason preserved verbatim across transitions

Exit codes: 0 all pass / 1 red / 2 untested (import failure)
"""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SUBJECTS = (
    "base/review_reducer.py",
    "base/takedown.py",
)

try:
    from base import takedown as TD
    from base.review_reducer import initial_state, reduce_command
    from base.reviews_ledger import LedgerConflict, LedgerValidation
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: cannot import: %s" % exc)
    sys.exit(2)

CASE = "case-td-1"


def _st():
    st = initial_state(CASE)
    st["tenant"] = "on_t1"
    st["product_line"] = "pump"
    return st


def _create(state, version, **over):
    payload = {
        "trigger": "revoke", "platform": "amazon_us",
        "assignee": "ou_exec", "reviewers": ["ou_rev"],
        "reason": "撤回后需下线",
    }
    payload.update(over)
    return reduce_command(state, "takedown_create", "ou_signer", version,
                          {**payload, "case_id": CASE}, now=1000)


def _tr(state, version, **over):
    payload = {"task_id": "", "to": "in_progress", "action": "start"}
    payload.update(over)
    return reduce_command(state, "takedown_transition", "ou_exec", version,
                          {**payload, "case_id": CASE}, now=2000 + version)


def main():
    passed = failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name +
              ((" " + detail) if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    src = open(os.path.join(ROOT, "base", "review_reducer.py"),
               encoding="utf-8").read()
    if "takedown_create" not in src:
        report(False, "T0 takedown_create exists in reducer",
               "production has no create path; #95-#101 describe objects "
               "that cannot be produced")
        print("----------------------------------------")
        print("%d passed, %d failed" % (passed, failed), file=sys.stderr)
        return 1

    # ---- T1 create ----
    s1, ev1, r1 = _create(_st(), 0)
    tasks = s1.get("takedown_tasks") or []
    report(len(tasks) == 1, "T1a create lands one task", repr(len(tasks)))
    t1 = tasks[0] if tasks else {}
    report(t1.get("state") == "pending", "T1b initial state pending", repr(t1.get("state")))
    report(t1.get("trigger") == "revoke", "T1c trigger recorded", repr(t1.get("trigger")))
    report(t1.get("reason") == "撤回后需下线", "T1d reason recorded verbatim")
    report(t1.get("tenant") == "on_t1", "T1e tenant recorded")
    report(t1.get("version") == 0, "T1f task version starts at 0", repr(t1.get("version")))
    report(isinstance(t1.get("task_id"), str) and t1["task_id"].startswith("td-")
           and not t1["task_id"].endswith("-1"),
           "T1g task_id is content-derived, not a bare counter",
           repr(t1.get("task_id")))

    # ---- T3 trigger validation ----
    # ★ 期望的 code 要写**实际的那个**：_nonempty 抛的是 bad_<字段名>，
    #   不是统一的 bad_task。第一版四行都写 bad_task，后两行落红 ——
    #   那不是实现错，是我把「同一类错误」当成了「同一个 code」。
    #   判据宁可指得具体：知道缺的是 platform 比知道「参数不对」有用。
    for name, over, expect in (
            ("缺 trigger", {"trigger": None}, "bad_task"),
            ("未知 trigger", {"trigger": "expired"}, "bad_task"),
            ("缺 platform", {"platform": ""}, "bad_platform"),
            ("缺 assignee", {"assignee": ""}, "bad_assignee"),
    ):
        code = None
        try:
            _create(_st(), 0, **over)
        except (LedgerConflict, LedgerValidation) as exc:
            code = exc.code
        report(code == expect, "T3 %s -> %s" % (name, expect), repr(code))

    # ---- T2 duplicate ----
    code = None
    try:
        _create(s1, 1)
    except (LedgerConflict, LedgerValidation) as exc:
        code = exc.code
    report(code == "duplicate_task", "T2 same case+trigger unfinished -> duplicate_task",
           repr(code))

    # ---- T4 transition delegates to TD.transition ----
    tid = t1.get("task_id", "")
    s2, _, r2 = _tr(s1, 1, task_id=tid)
    t2 = s2["takedown_tasks"][0]
    report(t2.get("state") == "in_progress", "T4a start -> in_progress", repr(t2.get("state")))
    report(t2.get("version") == 1, "T7a per-task version increments", repr(t2.get("version")))
    report(t2.get("trigger") == "revoke" and t2.get("reason") == "撤回后需下线",
           "T8 trigger/reason preserved across transitions")

    # illegal transition must be rejected by TD's table, not a copy
    code = None
    try:
        _tr(s2, 2, task_id=tid, to="pending", action=None)
    except Exception as exc:  # noqa: BLE001
        code = getattr(exc, "code", None)
    report(code == "E_TRANSITION",
           "T4b illegal in_progress->pending rejected with TD's code", repr(code))

    # T4c: the reducer must go through TD.transition(), not re-implement it.
    #
    # ★ 第一版这里改 TD.TRANSITIONS 看 reducer 跟不跟 —— 那是**假判据**：
    #   一个自己抄表的实现如果 import 的是同一个 dict 对象，改表它也会跟着变，
    #   所以它照样绿（实测 M2 变异 survived）。真正能区分的是
    #   **TD.transition() 除判迁移之外做的事**：追加 history。
    #   抄一份表自己拼 dict 的实现不会写 history。
    s3, _, _ = _tr(s2, 2, task_id=tid, to="failed", action="fail")
    t3 = s3["takedown_tasks"][0]
    hist = t3.get("history") or []
    report(len(hist) == 2
           and hist[-1].get("from") == "in_progress"
           and hist[-1].get("to") == "failed"
           and hist[-1].get("action") == "fail",
           "T4c reducer goes through TD.transition (history appended there)",
           repr(hist[-1] if hist else None))

    # T4d: action validation lives in TD.check_transition (E_ACTION), so a
    # re-implementation that only compares the target state will let a bogus
    # action through.
    saved = copy.deepcopy(TD.TRANSITIONS)
    try:
        code = None
        try:
            _tr(s3, 3, task_id=tid, to="in_progress", action="bogus_action")
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", None)
        report(code == "E_ACTION",
               "T4d bogus action on failed->in_progress rejected (E_ACTION)",
               repr(code))
    finally:
        TD.TRANSITIONS.clear()
        TD.TRANSITIONS.update(saved)

    # ---- T5 no deadline ----
    bad = [k for k in s1["takedown_tasks"][0]
           if k.lower() in ("deadline", "due_at", "expires_at", "sla_deadline",
                            "due_date")]
    report(bad == [], "T5 no deadline field in the stored task", repr(bad))
    try:
        TD.check_no_deadline(s1["takedown_tasks"][0])
        ok5 = True
    except TD.TakedownError as exc:
        ok5 = False
    report(ok5, "T5b TD.check_no_deadline accepts the stored task")

    # ---- T6 event snapshot ----
    report(ev1[0]["state"].get("takedown_tasks"),
           "T6 task enters the event snapshot (survives replay)")

    print("----------------------------------------")
    if failed == 0:
        print("OK %d/%d passed" % (passed, passed + failed))
        return 0
    print("FAILED %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: verifier crashed: %s" % exc)
        sys.exit(2)
