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

        # ── C12–C15（T-316b）：ingest 携带的报告渲染输入 ──────────────
        #
        # 缺口：judge_entry 丢弃 snapshot 那段已在 verify_judge_entry 的 C6–C9
        # 验过。这里验的是**另一半** —— reducer 收到它之后是否原样保留、
        # 坏形状是否被拒。两处分开，是因为一个是「有没有传」、一个是
        # 「传到了以后会不会被悄悄改掉」，失败时要查的文件不同。
        base_payload = {
            "submission_id": "s-snap",
            "submission_hash": "h" * 64,
            "tenant": "t1", "product_line": "p",
            "submitter_id": "alice",
            "content": {"unit_id": "u-1",
                        "fingerprint": {"text_sha256": "a" * 64}},
            # T-310a：签发绑定字段进了 ingest 契约（缺即 bad_binding_fields）。
            # ctv 与 ir.control_points_version 是同一个量，reducer 断言两者一致。
            "ir": {"ir_id": "ir-1", "findings": [],
                   "decision": {"state": "REVIEW"},
                   "control_points_version": "cp-1"},
            "kb_snapshot_hash": "b" * 64,
            "conflict_table_version": "cp-1",
            "judgment": {"label": "REVIEW", "run_state": "OK"},
            "report_snapshot": {
                "ir": {"ir_id": "ir-1", "findings": [],
                       "decision": {"state": "REVIEW"}},
                "failure_kind_counts": {"fetch_error": 0, "parse_error": 0,
                                        "empty": 0, "unsupported": 0},
                "unknown_bucket_counts": {},
                "evidence": [], "unassessed": [],
                "receipt": {"skill": "s", "version": "1"},
            },
        }

        snap_state, snap_events, _ = reduce_command(
            initial_state("case-snap"), "ingest_submission", "alice", 0,
            {**base_payload, "case_id": "case-snap"}, now=5000)
        report(snap_state["report_snapshot"] is not None
               and snap_state["report_snapshot"]["ir"]["ir_id"] == "ir-1",
               "C12 ingest 保留 report_snapshot（不被丢弃）")
        # ★ 反向面：事件快照是权威的持久形态。只要 state 里有而事件里没有，
        #   重放就会把它丢掉 —— 这条防的正是那种写法。
        report(snap_events[0]["state"]["report_snapshot"] is not None,
               "C13 report_snapshot 进入事件快照（重放后仍在）")

        # 缺省必须被接受（不是所有 judge_fn 都会给），且落成 None 不是缺键
        # ★ C14 必须自己 try/except，不能让它抛到 main 的兜底。
        #   第一版没写，实测：把 report_snapshot 改成必填后，本验证器退 2
        #   并打印「UNTESTED: bad_report_snapshot: 必填」—— 一条判据如果只可能
        #   绿或「未测」，它就不是判据（#136 / 0d84ccd 的同一个形状）。
        no_snap = {k: v for k, v in base_payload.items() if k != "report_snapshot"}
        try:
            ns_state, _, _ = reduce_command(
                initial_state("case-nosnap"), "ingest_submission", "alice", 0,
                {**no_snap, "case_id": "case-nosnap"}, now=5000)
            absent_ok = ("report_snapshot" in ns_state
                         and ns_state["report_snapshot"] is None)
            absent_detail = ""
        except LedgerValidation as exc:
            absent_ok = False
            absent_detail = "%s: %s" % (exc.code, exc.detail)
        report(absent_ok,
               "C14 不给 report_snapshot → 键仍在且为 None（缺省不是错误）",
               absent_detail)

        # 坏形状必须拒 —— 坏快照一旦随权威落盘就是永久的
        for name, mutate in (
                ("不是对象", lambda v: v.update({"report_snapshot": ["x"]})),
                ("ir 不是对象", lambda v: v["report_snapshot"].update({"ir": "x"})),
                ("failure_kind_counts 不是对象",
                 lambda v: v["report_snapshot"].update({"failure_kind_counts": []})),
        ):
            bad = copy.deepcopy({**base_payload, "case_id": "case-badsnap"})
            mutate(bad)
            try:
                reduce_command(initial_state("case-badsnap"), "ingest_submission",
                               "alice", 0, bad, now=5000)
                rejected = False
            except LedgerValidation as exc:
                rejected = exc.code == "bad_report_snapshot"
            report(rejected, "C15 report_snapshot %s → 拒绝" % name)

        # ── G 段：grant_revoke（T-315a：撤权 = approved→revoked，不是删除）──
        def _approved_grant(case_id):
            s = initial_state(case_id)
            s, _, r = apply(s, "grant_propose", "dp4", 0, {
                "capability": "takedown.execute", "user_id": "u_x",
                "reason": "值班需要",
                "scope": {"tenant": "t1", "product_lines": ["home"]}})
            gid = r["grant"]["grant_id"]
            s, _, _ = apply(s, "grant_execute", "it1", s["version"],
                            {"grant_id": gid})
            s, _, _ = apply(s, "grant_approve", "appr1", s["version"],
                            {"grant_id": gid})
            return s, gid

        gs, gid_g = _approved_grant("case-grant")
        gs2, _, rg = apply(gs, "grant_revoke", "admin1", gs["version"],
                           {"grant_id": gid_g, "reason": "调岗收回"})
        report(rg["grant"]["state"] == "revoked"
               and rg["grant"]["revoked_by"] == "admin1"
               and rg["grant"]["revoke_reason"] == "调岗收回"
               and rg["grant"]["revoked_at"] is not None,
               "G1 revoke 置 revoked 并落三字段")
        report(any(h.get("action") == "revoke" and h.get("from") == "approved"
                   and h.get("to") == "revoked" and h.get("note") == "调岗收回"
                   for h in rg["grant"]["history"]),
               "G1b history 追加 revoke 行（不重写）")
        report(gs2["version"] == gs["version"] + 1,
               "G1c 授权版本 = 聚合 version，撤权命令递增 1")

        def _revoke_twice():
            s, gid = _approved_grant("case-grant-2")
            s, _, _ = apply(s, "grant_revoke", "admin1", s["version"],
                            {"grant_id": gid, "reason": "第一次"})
            return apply(s, "grant_revoke", "admin2", s["version"],
                         {"grant_id": gid, "reason": "第二次"})
        try:
            _revoke_twice()
            report(False, "G2 重复撤权 → grant_not_active", "（未拒绝）")
        except LedgerConflict as exc:
            report(exc.code == "grant_not_active",
                   "G2 重复撤权 → grant_not_active", "（%s）" % exc.code)

        def _self_revoke():
            s, gid = _approved_grant("case-grant-3")
            return apply(s, "grant_revoke", "u_x", s["version"],
                         {"grant_id": gid, "reason": "自己撤自己"})
        try:
            _self_revoke()
            report(False, "G3 自己撤自己 → self_revoke", "（未拒绝）")
        except LedgerConflict as exc:
            report(exc.code == "self_revoke",
                   "G3 自己撤自己 → self_revoke", "（%s）" % exc.code)

        def _no_reason():
            s, gid = _approved_grant("case-grant-4")
            return apply(s, "grant_revoke", "admin1", s["version"],
                         {"grant_id": gid, "reason": "  "})
        try:
            _no_reason()
            report(False, "G4 空 reason → bad_revoke_reason", "（未拒绝）")
        except LedgerValidation as exc:
            report(exc.code == "bad_revoke_reason",
                   "G4 空 reason → bad_revoke_reason", "（%s）" % exc.code)

        def _revoke_before_approve():
            s = initial_state("case-grant-5")
            s, _, r = apply(s, "grant_propose", "dp4", 0, {
                "capability": "takedown.execute", "user_id": "u_x",
                "reason": "值班需要",
                "scope": {"tenant": "t1", "product_lines": ["home"]}})
            return apply(s, "grant_revoke", "admin1", s["version"],
                         {"grant_id": r["grant"]["grant_id"], "reason": "太早"})
        try:
            _revoke_before_approve()
            report(False, "G5 proposed 状态不可撤 → grant_not_active", "（未拒绝）")
        except LedgerConflict as exc:
            report(exc.code == "grant_not_active",
                   "G5 proposed 状态不可撤 → grant_not_active", "（%s）" % exc.code)

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
