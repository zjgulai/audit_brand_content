#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_authority_change.py —— 权威源变更 → 重审入队（行 103 / RL-15）

验证 `base/authority_change.on_authority_changed()`：
  A 三类权威源（rules / control_points / routing）各自产生变更事件；
  B 每个 case 入队一条 queued / trigger=authority_change 的 job；
  C 同一事件重复送达 → duplicate，不重复入队（幂等）；
  D 新版本 → 新事件，不误判 duplicate；
  E 非法事件（未知 kind / 版本为空 / 版本相同 / case_id 非法）必须拒；
  F 不传 enqueue 也返回 jobs（生产可接队列，测试可接内存）。

退出码：0 全过 / 1 有红 / 2 未测（导入失败）。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from base.authority_change import AUTHORITY_KINDS, on_authority_changed
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.authority_change: %s" % exc)
    sys.exit(2)


def main():
    passed = 0
    failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        if ok:
            print("PASS: %s" % name)
            passed += 1
        else:
            print("FAIL: %s %s" % (name, detail), file=sys.stderr)
            failed += 1

    def raises(fn):
        try:
            fn()
        except ValueError:
            return True
        except Exception:  # noqa: BLE001
            return False
        return False

    cases = ["case-1", "case-2"]
    for kind in AUTHORITY_KINDS:
        queued = []
        seen = set()
        out = on_authority_changed(
            {"kind": kind, "old_version": "v1", "new_version": "v2"},
            case_ids=cases, enqueue=queued.append, seen=seen,
            now="2026-10-19T00:00:00Z")
        report(out.get("accepted") is True and len(out.get("jobs") or []) == 2
               and len(queued) == 2
               and all(j.get("state") == "queued"
                       and j.get("trigger") == "authority_change"
                       and j.get("authority_kind") == kind
                       and j.get("old_version") == "v1"
                       and j.get("new_version") == "v2"
                       and j.get("case_id") in cases
                       for j in queued),
               "A %s 变更 → 每个 case 一条 queued job" % kind,
               repr(out))
        report(out.get("event_key", "").startswith("auth-")
               and len({j["job_id"] for j in queued}) == 2,
               "A %s event_key/job_id 形状" % kind, repr(out.get("event_key")))

    seen = set()
    queued = []
    ev = {"kind": "rules", "old_version": "v1", "new_version": "v2"}
    first = on_authority_changed(ev, case_ids=cases,
                                 enqueue=queued.append, seen=seen)
    n_after_first = len(queued)
    second = on_authority_changed(ev, case_ids=cases,
                                  enqueue=queued.append, seen=seen)
    report(first.get("accepted") is True
           and second.get("accepted") is False
           and second.get("reason") == "duplicate_event"
           and second.get("jobs") == []
           and len(queued) == n_after_first,
           "C 同一事件重复 → duplicate，不重复入队", repr(second))
    report(first.get("event_key") == second.get("event_key"),
           "C duplicate 的 event_key 与首次一致", "")

    third = on_authority_changed(
        {"kind": "rules", "old_version": "v2", "new_version": "v3"},
        case_ids=cases, enqueue=queued.append, seen=seen)
    report(third.get("accepted") is True
           and third.get("event_key") != first.get("event_key")
           and len(queued) == n_after_first + 2,
           "D 新版本 → 新事件，不误判 duplicate", repr(third))

    for name, event in [
        ("未知 kind", {"kind": "kb", "old_version": "v1", "new_version": "v2"}),
        ("old 为空", {"kind": "rules", "old_version": "", "new_version": "v2"}),
        ("new 为空", {"kind": "rules", "old_version": "v1", "new_version": ""}),
        ("版本相同", {"kind": "rules", "old_version": "v1", "new_version": "v1"}),
    ]:
        report(raises(lambda e=event: on_authority_changed(
            e, case_ids=cases)), "E %s → 拒" % name, "")
    report(raises(lambda: on_authority_changed(
        {"kind": "rules", "old_version": "v1", "new_version": "v2"},
        case_ids=[""])), "E 非法 case_id → 拒", "")

    no_enqueue = on_authority_changed(
        {"kind": "routing", "old_version": "r1", "new_version": "r2"},
        case_ids=["case-9"])
    report(no_enqueue.get("accepted") is True
           and len(no_enqueue.get("jobs") or []) == 1
           and no_enqueue["jobs"][0]["case_id"] == "case-9",
           "F 不传 enqueue 也返回 jobs", repr(no_enqueue))

    empty = on_authority_changed(
        {"kind": "control_points", "old_version": "c1", "new_version": "c2"},
        case_ids=[])
    report(empty.get("accepted") is True and empty.get("jobs") == [],
           "F 无案件也接受，但 jobs 为空", repr(empty))

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验证器自身异常: %s" % exc)
        sys.exit(2)
