#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生产复核 reducer 九种命令的纯函数自证。

主体：base/review_reducer.py、base/reviews_ledger.py。
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base.review_reducer import initial_state, reduce_command
    from base.reviews_ledger import LEASE_SECONDS, LedgerConflict, LedgerValidation
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 review reducer: %s" % exc)
    sys.exit(2)


def apply(state, command, actor, version, payload=None, now=1000):
    new_state, events, result = reduce_command(
        state, command, actor, version, payload or {}, now=now)
    assert len(events) == 1
    assert events[0]["state"] == new_state
    assert events[0]["version"] == new_state["version"]
    return new_state, events[0], result


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

    try:
        state = initial_state("case-all")
        state, event, result = apply(state, "claim", "alice", 0, now=1000)
        report(state["status"] == "claimed" and state["version"] == 1
               and state["lease_expires"] == 1000 + LEASE_SECONDS,
               "C0 claim 建 lease/v1")

        state, event, result = apply(state, "save_draft", "alice", 1, {
            "form": {"verdict": "REVIEW"}, "notes": "Alice draft",
            "evidence_selections": ["e1"], "references": [],
        }, now=1001)
        alice_draft = result["draft"]["draft_id"]
        report(state["version"] == 2 and state["primary_draft_id"] == alice_draft,
               "C1 save_draft 建不可变快照/v2")

        old_expiry = state["lease_expires"]
        state, event, result = apply(state, "heartbeat", "alice", 2, now=1100)
        report(state["version"] == 3
               and state["lease_expires"] == 1100 + LEASE_SECONDS
               and state["lease_expires"] > old_expiry,
               "C2 heartbeat 续 lease/v3")

        state, event, result = apply(state, "reassign", "alice", 3,
                                     {"assignee": "bob"}, now=1101)
        report(state["version"] == 4 and state["assignee"] == "bob"
               and event["detail"]["new_assignee"] == "bob",
               "C3 reassign 留痕/v4")

        state, event, result = apply(state, "adopt_draft", "bob", 4,
                                     {"source_draft_id": alice_draft}, now=1102)
        bob_draft = result["draft"]["draft_id"]
        report(state["version"] == 5 and bob_draft != alice_draft
               and result["draft"]["derived_from"] == alice_draft
               and state["primary_draft_id"] == bob_draft,
               "C4 adopt 复制快照并保留 derived_from/v5")

        state, event, result = apply(state, "reference_fragment", "bob", 5, {
            "source_draft_id": alice_draft,
            "field_path": "notes",
            "fragment": "Alice",
        }, now=1103)
        report(state["version"] == 6
               and result["reference"]["source_draft_id"] == alice_draft
               and len(state["fragment_references"]) == 1,
               "C5 reference 非主草稿片段留痕/v6")

        state, event, result = apply(state, "unclaim", "bob", 6, now=1104)
        report(state["version"] == 7 and state["status"] == "released"
               and state["assignee"] is None
               and state["released_draft_id"] == bob_draft,
               "C6 unclaim 释放且保留主草稿/v7")

        state, event, result = apply(state, "claim", "bob", 7, now=1105)
        state, event, result = apply(state, "submit_review", "bob", 8,
                                     {"conclusion": {"review_notes": "done"}},
                                     now=1106)
        report(state["version"] == 9 and state["status"] == "closed"
               and result["formal"]["from_draft_id"] == bob_draft,
               "C7 submit 建 formal 并闭案/v9")

        expired = initial_state("case-expire")
        expired, _, _ = apply(expired, "claim", "alice", 0, now=2000)
        expired, event, result = apply(
            expired, "expire_lease", "lease-sweeper", 1,
            now=2000 + LEASE_SECONDS + 1)
        report(expired["status"] == "released" and expired["assignee"] is None
               and expired["version"] == 2
               and event["detail"]["released_assignee"] == "alice"
               and expired["released_draft_id"],
               "C8 expire_lease 保存草稿与原领取人/v2")

        active = initial_state("case-active")
        active, _, _ = apply(active, "claim", "alice", 0, now=3000)
        before = copy.deepcopy(active)
        try:
            reduce_command(
                active, "expire_lease", "lease-sweeper", 1, {},
                now=3000 + LEASE_SECONDS - 1)
            denied = False
        except LedgerConflict as exc:
            denied = exc.code == "lease_active"
        report(denied and active == before,
               "C9 未到期 lease 拒绝且入参不变")

        expired_actor = initial_state("case-expired-actor")
        expired_actor, _, _ = apply(expired_actor, "claim", "alice", 0, now=4000)
        for command, payload in (
            ("heartbeat", {}),
            ("save_draft", {"form": {}, "notes": "late",
                            "evidence_selections": [], "references": []}),
            ("submit_review", {"conclusion": {"review_notes": "late"}}),
        ):
            before_expired = copy.deepcopy(expired_actor)
            try:
                reduce_command(
                    expired_actor, command, "alice", 1, payload,
                    now=4000 + LEASE_SECONDS + 1)
                denied = False
            except LedgerConflict as exc:
                denied = exc.code == "lease_expired"
            report(denied and expired_actor == before_expired,
                   "C9b 过期 assignee 的 %s 被拒且状态不变" % command)

        before = copy.deepcopy(state)
        try:
            reduce_command(state, "submit_review", "bob", 8,
                           {"conclusion": {}}, now=1200)
            denied = False
        except (LedgerConflict, LedgerValidation):
            denied = True
        report(denied and state == before,
               "C10 失败命令不修改旧状态")

        try:
            reduce_command(initial_state("case-bad"), "unknown", "alice", 0, {}, now=1)
            denied = False
        except LedgerValidation as exc:
            denied = exc.code == "bad_command"
        report(denied, "C11 未知命令 fail closed")
    except AssertionError as exc:
        print("UNTESTED: 验收器内部断言失败: %s" % exc, file=sys.stderr)
        return 2

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
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
