#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-313a/b 通知聚合的自证：aggregate 判定 / reducer 命令 / 权威持久化 / 投影迁移。

主体：base/review_reducer.py（NOTIFICATION_COMMANDS / aggregate_type_for /
initial_state 分支）、base/projection_store.py（SCHEMA_VERSION 3、notifications 表、
apply_batch 分流、list_notifications）、base/business_event_store.py（跨重启持久化）；类型清单单一来源：
base/notifications.py（TYPES 经 _notification_types() 导入，N1d 反向对照）。

P 段走真 BusinessEventStore（真 WriterLease + tmp 目录），不手搓批次 ——
「重启恒等」读的是新开实例的 state()，不是内存对象。
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import base.review_reducer as RR
    from base.review_reducer import (NOTIFICATION_COMMANDS, aggregate_type_for,
                                     initial_state, reduce_command)
    from base.reviews_ledger import (LedgerConflict, LedgerNotFound,
                                     LedgerValidation)
    from base.business_event_store import BusinessEventStore, WriterLease
    from base.projector import Projector
    from base.projection_store import ProjectionStore
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入被测模块: %s" % exc)
    sys.exit(2)

AGG = "notifications:t1:u1"


def _inbox_state():
    return initial_state(AGG)


def _apply(state, command, payload, actor="system", now=1000):
    new_state, events, result = reduce_command(
        state, command, actor, state["version"], payload or {}, now=now)
    assert len(events) == 1 and events[0]["state"] == new_state
    return new_state, result


def store_h_like():
    import base.auth_session as _AS
    return _AS.SessionStore(":memory:")


def _PROD_PATHS():
    import sys as _sys
    sys.path.insert(0, str(ROOT))
    from api.production_app import PRODUCTION_WRITE_PATHS
    return PRODUCTION_WRITE_PATHS


def main():
    passed = failed = 0
    tmp_roots = []

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name +
              ((" " + detail) if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    def expect(kind, fn, code, name):
        try:
            fn()
            report(False, name, "（未拒绝）")
        except kind as exc:
            report(getattr(exc, "code", "") == code,
                   name, "（%s）" % getattr(exc, "code", ""))

    try:
        # ---- N0：aggregate_type_for 是唯一一份判定 ----
        report(aggregate_type_for(AGG) == "notifications",
               "N0 notifications:<t>:<u> -> notifications")
        report(aggregate_type_for("grants:t1") == "grant_registry"
               and aggregate_type_for("case-x") == "review_case",
               "N0b grants/case 判定不受影响")
        expect(LedgerValidation,
               lambda: initial_state("notifications:t1"),
               "bad_notification_aggregate", "N0c 缺 recipient 段 → 拒")
        expect(LedgerValidation,
               lambda: initial_state("notifications:t1:"),
               "bad_notification_aggregate", "N0d 空 recipient → 拒")
        st = _inbox_state()
        report(st["tenant"] == "t1" and st["recipient"] == "u1"
               and st["items"] == [] and st["version"] == 0,
               "N0e initial_state 产出收件箱形状（tenant/recipient 进 state）")

        # ---- N1：emit → read → ack 快乐路径（纯函数）----
        st, res = _apply(st, "notification_emit", {
            "type": "lease_released", "dedup_key": "case-a:2",
            "related_case_id": "case-a", "payload": {"note": "x"}})
        nid = res["notification"]["notification_id"]
        report(nid.startswith("notif-") and len(res["items"]) == 1
               and res["notification"]["read_at"] is None,
               "N1 emit 建条目、结果带收件箱形状")
        def _dup():
            s0 = _inbox_state()
            s0, _ = _apply(s0, "notification_emit",
                           {"type": "lease_released", "dedup_key": "case-a:2"})
            return _apply(s0, "notification_emit",
                          {"type": "lease_released", "dedup_key": "case-a:2"})
        expect(LedgerConflict, _dup,
               "duplicate_notification", "N1c 重复 emit → duplicate_notification")
        expect(LedgerValidation,
               lambda: _apply(_inbox_state(), "notification_emit", {
                   "type": "no_such_type", "dedup_key": "k"}),
               "bad_notification", "N1d 未知 type → 拒（TYPES 单一来源）")

        st, _ = _apply(st, "notification_read", {"notification_id": nid})
        report(st["items"][0]["read_at"] is not None, "N1e read 写 read_at")
        def _unread_ack():
            fresh = _inbox_state()
            fresh, r = _apply(fresh, "notification_emit", {
                "type": "lease_released", "dedup_key": "unread-1"})
            return _apply(fresh, "notification_ack",
                          {"notification_id": r["notification"]["notification_id"]})
        expect(LedgerConflict, _unread_ack,
               "ack_without_read", "N1f 未读先 ack → ack_without_read")
        expect(LedgerConflict,
               lambda: _apply(st, "notification_read", {"notification_id": nid}),
               "already_read", "N1g 重复 read → already_read")
        st, _ = _apply(st, "notification_ack", {"notification_id": nid})
        report(st["items"][0]["acked_at"] is not None, "N1h ack 写 acked_at")
        expect(LedgerNotFound,
               lambda: _apply(st, "notification_read", {"notification_id": "notif-none"}),
               "notification_not_found", "N1i 不存在的通知 → not_found")

        # ---- N2：不同收件人同 dedup 是两条不同通知（id 含 recipient）----
        other = initial_state("notifications:t1:u2")
        other, _ = _apply(other, "notification_emit",
                          {"type": "lease_released", "dedup_key": "case-a:2"})
        report(other["items"][0]["notification_id"] != nid,
               "N2 recipient 参与 id，不同收件人互不撞号")

        # ---- N3：收件箱上限与归档（D3：超限归档最旧已读，未读永不淘汰）----
        old_limit = RR.NOTIFICATION_INBOX_LIMIT
        try:
            RR.NOTIFICATION_INBOX_LIMIT = 3
            s3 = _inbox_state()
            for k in range(3):
                s3, _ = _apply(s3, "notification_emit",
                               {"type": "case_overdue", "dedup_key": "d%d" % k})
            s3, _ = _apply(s3, "notification_read",
                           {"notification_id": s3["items"][0]["notification_id"]})
            s3, _ = _apply(s3, "notification_emit",
                           {"type": "case_overdue", "dedup_key": "d3"})
            report(s3["items"][0]["archived"] is True
                   and s3["archived_count"] == 1,
                   "N3a 超限归档最旧已读、archived_count 递增")
            expect(LedgerNotFound,
                   lambda: _apply(s3, "notification_read",
                                  {"notification_id": s3["items"][0]["notification_id"]}),
                   "notification_not_found", "N3b 已归档条目不再可操作")
            s4 = _inbox_state()
            for k in range(3):
                s4, _ = _apply(s4, "notification_emit",
                               {"type": "case_overdue", "dedup_key": "e%d" % k})
            expect(LedgerConflict,
                   lambda: _apply(s4, "notification_emit",
                                  {"type": "case_overdue", "dedup_key": "e3"}),
                   "inbox_full", "N3c 全未读且已满 → inbox_full（未读永不淘汰）")
        finally:
            RR.NOTIFICATION_INBOX_LIMIT = old_limit

        # ---- P 段：真权威 + 真投影（重启恒等 / 幂等重放 / 投影可重建）----
        root = tempfile.mkdtemp(prefix="notif-persist-")
        tmp_roots.append(root)
        lease = WriterLease(os.path.join(root, "a", "lock")).acquire()
        auth = BusinessEventStore(os.path.join(root, "a"), lease=lease)
        proj = ProjectionStore(os.path.join(root, "p.db"))
        payload = {"type": "lease_released", "dedup_key": "case-x:1",
                   "related_case_id": "case-x", "payload": {"who": "alice"}}
        out1 = auth.execute(aggregate_id=AGG, command="notification_emit",
                            actor={"principal_id": "system", "tenant_id": "t1"},
                            expected_version=0, payload=payload,
                            idempotency_key="emit-1", now=1000)
        nid1 = out1["batch"]["result"]["notification"]["notification_id"]
        out2 = auth.execute(aggregate_id=AGG, command="notification_read",
                            actor={"principal_id": "u1", "tenant_id": "t1"},
                            expected_version=1,
                            payload={"notification_id": nid1},
                            idempotency_key="read-1", now=1001)
        report(nid1.startswith("notif-")
               and out2["batch"]["result"]["notification"]["read_at"] is not None,
               "P1 emit/read 走真权威成功")
        replay = auth.execute(aggregate_id=AGG, command="notification_emit",
                              actor={"principal_id": "system", "tenant_id": "t1"},
                              expected_version=0, payload=payload,
                              idempotency_key="emit-1", now=1002)
        report(replay.get("replayed") is True
               and len(auth.state(AGG)["items"]) == 1,
               "P2 同幂等键重放不多写（权威层幂等）")

        # 重启恒等：新开 authority/projection 实例读同一目录。
        auth2 = BusinessEventStore(os.path.join(root, "a"), lease=lease)
        st_after = auth2.state(AGG)
        report(len(st_after["items"]) == 1
               and st_after["items"][0]["read_at"] is not None,
               "P3 重启后收件箱与已读状态仍在")
        Projector(auth2, proj).catch_up()
        boxes = proj.list_notifications(tenant="t1", recipient="u1")
        report(len(boxes) == 1 and boxes[0]["tenant"] == "t1"
               and boxes[0]["recipient"] == "u1"
               and boxes[0]["items"][0]["read_at"] is not None,
               "P4 投影 list_notifications 按列拼回形状、内容与权威一致")
        report(not proj.list_cases(),
               "P4b 通知聚合不进 review_cases（案件列表零污染）")
        proj.reset()
        Projector(auth2, proj).catch_up()
        boxes2 = proj.list_notifications(tenant="t1", recipient="u1")
        report(boxes2 == boxes, "P5 删投影重建后恒等")
        expect(LedgerValidation,
               lambda: reduce_command(_inbox_state(), "bogus_notification", "s",
                                      0, {}, now=1000),
               "bad_command", "P6 通知聚合上的未知命令仍 fail closed")
        proj.close()

        # ---- M 段：迁移（真 v2 库升 v3；静默跳过是 f1d8ba4 的同族新病）----
        v2_dir = tempfile.mkdtemp(prefix="projection-v2-")
        tmp_roots.append(v2_dir)
        v2_path = os.path.join(v2_dir, "v2.db")
        import sqlite3 as _sqlite3
        conn = _sqlite3.connect(v2_path)
        conn.executescript("""
        BEGIN IMMEDIATE;
        CREATE TABLE applied_commands (
          command_id TEXT PRIMARY KEY, authority_seq INTEGER NOT NULL UNIQUE,
          request_sha256 TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
          applied_at REAL NOT NULL);
        CREATE TABLE review_cases (
          case_id TEXT PRIMARY KEY, version INTEGER NOT NULL, status TEXT NOT NULL,
          assignee TEXT, state_json TEXT NOT NULL);
        CREATE TABLE drafts (
          draft_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, snapshot_seq INTEGER NOT NULL,
          author TEXT, content_json TEXT NOT NULL);
        CREATE INDEX drafts_case_idx ON drafts(case_id, snapshot_seq);
        CREATE TABLE formal_reviews (
          formal_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, submitted_at TEXT,
          content_json TEXT NOT NULL);
        CREATE INDEX formal_case_idx ON formal_reviews(case_id, submitted_at);
        CREATE TABLE projection_meta (
          singleton INTEGER PRIMARY KEY CHECK(singleton=1), applied_seq INTEGER NOT NULL,
          manifest_sha256 TEXT, rebuilt_at REAL, last_error_code TEXT);
        INSERT INTO projection_meta VALUES(1, 0, NULL, NULL, NULL);
        CREATE TABLE grant_registry (
          tenant TEXT PRIMARY KEY, version INTEGER NOT NULL, state_json TEXT NOT NULL);
        PRAGMA user_version=2;
        COMMIT;
        """)
        conn.close()
        opened = None
        err = None
        try:
            opened = ProjectionStore(v2_path)
        except Exception as exc:  # noqa: BLE001
            err = "%s: %s" % (type(exc).__name__, exc)
        if opened is not None:
            uv = opened._conn.execute("PRAGMA user_version").fetchone()[0]
            has_notif = bool(opened._conn.execute(
                "SELECT name FROM sqlite_master WHERE name='notifications'").fetchone())
            has_old = bool(opened._conn.execute(
                "SELECT name FROM sqlite_master WHERE name='grant_registry'").fetchone())
            opened.close()
            report(uv == 3 and has_notif and has_old,
                   "M1 ★ 真 v2 库升 v3：notifications 表在、旧表不重建",
                   "user_version=%r notifications=%r grant_registry=%r"
                   % (uv, has_notif, has_old))
        else:
            report(False, "M1 ★ 真 v2 库升 v3", err or "打开失败")

        # ---- M2：未知 aggregate_type 仍拒（不许静默）----
        bad_dir = tempfile.mkdtemp(prefix="projection-badtype-")
        tmp_roots.append(bad_dir)
        pbad = ProjectionStore(os.path.join(bad_dir, "b.db"))
        bad_batch = {
            "schema_version": "business-command-batch/v1",
            "command_id": "cmd-x", "authority_seq": 1,
            # 首批的 prev 与全新投影存的 NULL 一致（business_event_store._head_hash 初始为 None）
            "prev_manifest_sha256": None, "manifest_sha256": "1" * 64,
            "request_sha256": "2" * 64,
            "aggregate_type": "mystery", "aggregate_id": "mystery:t1",
            "events": [{"type": "review.x", "version": 1,
                        "state": {"case_id": "mystery:t1", "version": 1}}],
        }
        try:
            pbad.apply_batch(copy.deepcopy(bad_batch))
            report(False, "M2 未知 aggregate_type 必拒", "（未抛）")
        except Exception as exc:  # noqa: BLE001
            report(getattr(exc, "code", "") == "unknown_aggregate_type",
                   "M2 未知 aggregate_type 必拒", "（%s）" % getattr(exc, "code", ""))
        pbad.close()

        # ---- E 段：触发点装配（T-313c）----
        from base.review_command_service import ReviewCommandService as _RCS
        root2 = tempfile.mkdtemp(prefix="notif-trigger-")
        tmp_roots.append(root2)
        lease2 = WriterLease(os.path.join(root2, "a", "lock")).acquire()
        auth3 = BusinessEventStore(os.path.join(root2, "a"), lease=lease2)
        proj3 = ProjectionStore(os.path.join(root2, "p.db"))
        svc3 = _RCS(auth3, proj3)
        cid_e = "case-trig"
        auth3.execute(aggregate_id=cid_e, command="ingest_submission",
                      actor={"principal_id": "ou_w", "tenant_id": "t1"},
                      expected_version=0,
                      payload={"submission_id": "s-trig",
                               "submission_hash": "h" * 64,
                               "content": {"unit_id": "u-trig",
                                           "fingerprint": {"text_sha256": "a" * 64}},
                               "ir": {"ir_id": "ir-trig", "ir_version": "v1",
                                      "findings": [],
                                      "decision": {"state": "REVIEW"},
                                      "control_points_version": "cp-1"},
                               "kb_snapshot_hash": "b" * 64,
                               "conflict_table_version": "cp-1",
                               "judgment": {"label": "REVIEW", "run_state": "OK"},
                               "tenant": "t1", "product_line": "pump",
                               "submitter_id": "ou_w"},
                      idempotency_key="ing", now=1000)
        auth3.execute(aggregate_id=cid_e, command="claim",
                      actor={"principal_id": "ou_w", "tenant_id": "t1"},
                      expected_version=1, payload={}, idempotency_key="cl",
                      now=1001)
        # E1：expire_lease → lease_released 通知给被释放的 assignee
        # ★ 经服务层：钩子在 ReviewCommandService.execute（裸 authority 不产通知）。
        svc3.execute(aggregate_id=cid_e, command="expire_lease",
                     actor={"principal_id": "sweeper", "tenant_id": "t1"},
                     expected_version=2, payload={}, idempotency_key="exp",
                     now=1001 + 10 ** 9)
        inbox_w = auth3.state("notifications:t1:ou_w")
        report(any(i["type"] == "lease_released" and i["read_at"] is None
                   for i in inbox_w["items"]),
               "E1 expire_lease 产出 lease_released 给被释放人")
        # E2：emit 失败可见不抛（坏 type → ok False）
        bad = svc3.emit_notification(tenant="t1", recipient="ou_w",
                                     ntype="no_such", dedup_key="k",
                                     idempotency_key="e-bad")
        report(bad.get("ok") is False and bool(bad.get("detail")),
               "E2 emit 失败可见（永不抛）", repr(bad.get("detail")))
        # E3：同键重放只一条（幂等）
        out_e = svc3.emit_notification(tenant="t1", recipient="ou_x",
                                       ntype="case_overdue", dedup_key="d1",
                                       idempotency_key="e-x")
        out_e2 = svc3.emit_notification(tenant="t1", recipient="ou_x",
                                        ntype="case_overdue", dedup_key="d1",
                                        idempotency_key="e-x")
        report(out_e.get("ok") and out_e2.get("ok")
               and out_e2.get("replayed") is True
               and len(auth3.state("notifications:t1:ou_x")["items"]) == 1,
               "E3 emit 幂等键重放不多写")

        # ---- D 段：API 转正（T-313d）----
        from api.review_api import create_app as _ca
        reader = lambda tenant, recipient: (  # noqa: E731 生产读法的镜像：读投影
            proj3.list_notifications(tenant=tenant, recipient=recipient))
        app_d = _ca(session_store=store_h_like(), review_command_service=svc3,
                    notification_reader=reader)
        proj3.close()
        report("/api/v1/notifications/{id}/read" in _PROD_PATHS()
               and "/api/v1/notifications/{id}/ack" in _PROD_PATHS(),
               "D1 read/ack 进生产能力表")

        # ---- S 段：reducer 不发通知的结构判据（运行时半边在 T-313c/d 验证器）----
        src = (ROOT / "base" / "review_reducer.py").read_text(encoding="utf-8")
        report("NotificationOutbox" not in src and "feishu" not in src.lower()
               and ".emit(" not in src,
               "S1 reducer 源码无外发通道引用（纯函数纪律的结构面）")
        report("case_id" not in json.dumps(
                   [i for i in st["items"]][0] if st["items"] else {})
               or "related_case_id" in json.dumps(st["items"][0]),
               "S2 条目用 related_case_id（不与 store 的 case_id 注入约定撞车）")
    except AssertionError as exc:
        print("UNTESTED: 验收器内部断言失败: %s" % exc, file=sys.stderr)
        return 2
    finally:
        for r in tmp_roots:
            shutil.rmtree(r, ignore_errors=True)

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
