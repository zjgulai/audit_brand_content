#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SQLite 投影自证：临时文件、可重建、坏序拒绝、无幽灵记录。

主体：base/business_event_store.py、base/projection_store.py、base/projector.py、
base/review_command_service.py。
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from base.business_event_store import BusinessEventStore, WriterLease
    from base.projection_store import ProjectionError, ProjectionStore
    from base.projector import Projector
    from base.review_command_service import ReviewCommandService
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入投影模块: %s" % exc)
    sys.exit(2)


def actor():
    return {"principal_id": "u1", "tenant_id": "t1"}


def main():
    passed = 0
    failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        print(("PASS" if ok else "FAIL") + ": " + name + (" " + detail if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    root = tempfile.mkdtemp(prefix="projection-store-")
    extra_roots = []
    try:
        auth_root = os.path.join(root, "authority")
        lease = WriterLease(os.path.join(auth_root, "writer.lock")).acquire()
        authority = BusinessEventStore(auth_root, lease=lease, clock=lambda: 1000)
        authority.execute(aggregate_id="case-1", command="claim", actor=actor(),
                          expected_version=0, payload={}, idempotency_key="c1", now=1000)
        authority.execute(aggregate_id="case-1", command="save_draft", actor=actor(),
                          expected_version=1,
                          payload={"form": {"x": 1}, "notes": "draft",
                                   "evidence_selections": [], "references": []},
                          idempotency_key="d1", now=1001)
        authority.execute(aggregate_id="case-1", command="submit_review", actor=actor(),
                          expected_version=2,
                          payload={"conclusion": {"review_notes": "done"}},
                          idempotency_key="s1", now=1002)

        db = os.path.join(root, "projection", "review.db")
        projection = ProjectionStore(db, clock=lambda: 1003)
        projector = Projector(authority, projection)

        report(projection.status(authority.head())["status"] == "lagging",
               "C0 未投影时 status=lagging")
        projector.catch_up()
        st = projection.status(authority.head())
        case = projection.get_case("case-1")
        report(st["status"] == "fresh" and st["lag_commits"] == 0
               and st["projection"]["manifest_sha256"] ==
               st["authority"]["manifest_sha256"],
               "C1 catch_up 后 seq/hash fresh", repr(st))
        report(case["status"] == "closed" and case["version"] == 3,
               "C2 案件状态/版本投影一致", repr(case))
        drafts = projection.list_drafts("case-1")
        formal = projection.list_formal("case-1")
        report(len(drafts) == 1 and drafts[0]["notes"] == "draft",
               "C3 草稿正文可查询", repr(drafts))
        report(len(formal) == 1 and formal[0]["conclusion"]["review_notes"] == "done",
               "C4 formal 正文可查询", repr(formal))

        # C5 重复 apply 不重复记录
        last = authority.batches()[-1]
        replay = projection.apply_batch(last)
        report(replay["replayed"] is True and len(projection.list_formal("case-1")) == 1,
               "C5 重复 command 幂等投影", repr(replay))

        # C6 projection-only 幽灵 draft 在 rebuild 后消失
        projection._conn.execute(
            "INSERT INTO drafts(draft_id,case_id,snapshot_seq,author,content_json) "
            "VALUES('ghost','case-1',999,'x','{}')")
        report(projection.get_draft("ghost") is not None, "C6a 构造幽灵记录")
        projector.rebuild()
        report(projection.get_draft("ghost") is None,
               "C6b rebuild 清掉 projection-only 幽灵")
        rebuilt_status = projection.status(authority.head())
        report(isinstance(rebuilt_status["projection"]["rebuilt_at"], str)
               and rebuilt_status["projection"]["rebuilt_at"].endswith("Z"),
               "C6c rebuilt_at 符合契约 date-time", repr(rebuilt_status))
        forged_head = dict(authority.head())
        forged_head["manifest_sha256"] = "f" * 64
        forged = projection.status(forged_head)
        report(forged["status"] == "corrupt"
               and forged["last_error_code"] == "projection_manifest_mismatch",
               "C6d 同 seq 异 manifest hash 必须 corrupt", repr(forged))
        # 前缀 hash 不一致时，不能靠应用后续批次把最终 hash 洗成 fresh。
        prefix_db = os.path.join(root, "projection-prefix.db")
        prefix = ProjectionStore(prefix_db, clock=lambda: 1003)
        prefix.apply_batch(authority.batches()[0])
        prefix._conn.execute(
            "UPDATE projection_meta SET manifest_sha256=? WHERE singleton=1",
            ("f" * 64,))
        try:
            Projector(authority, prefix).catch_up()
            prefix_denied = False
        except ProjectionError as exc:
            prefix_denied = exc.code == "projection_prefix_mismatch"
        report(prefix_denied and prefix.watermark()["applied_seq"] == 1,
               "C6e 异历史前缀拒绝后续批次洗白")
        prefix.close()

        # C7 删除投影文件后，从权威全量重建
        projection.close()
        for suffix in ("", "-wal", "-shm"):
            try:
                os.unlink(db + suffix)
            except FileNotFoundError:
                pass
        projection2 = ProjectionStore(db, clock=lambda: 1004)
        Projector(authority, projection2).rebuild()
        report(projection2.get_case("case-1")["version"] == 3
               and len(projection2.list_drafts("case-1")) == 1,
               "C7 删投影后只靠权威重建")

        # C8 断序 apply 明确失败
        bad = dict(last)
        bad["command_id"] = "cmd-gap"
        bad["authority_seq"] = 9
        bad["manifest_sha256"] = "f" * 64
        try:
            projection2.apply_batch(bad)
            denied = False
        except ProjectionError as exc:
            denied = exc.code == "projection_sequence"
        report(denied, "C8 投影断序拒绝")

        # C9 仓内路径与 :memory: 拒绝
        denied = 0
        for bad_path in (":memory:", os.path.join(ROOT, "projection.db")):
            try:
                ProjectionStore(bad_path)
            except ProjectionError:
                denied += 1
        report(denied == 2, "C9 非仓外文件投影拒绝")
        unavailable_db = os.path.join(root, "unavailable.db")
        unavailable_store = ProjectionStore(unavailable_db)
        unavailable_store.close()
        unavailable = unavailable_store.status(authority.head())
        report(unavailable["status"] == "unavailable"
               and unavailable["last_error_code"] == "projection_unavailable",
               "C9b 关闭/不可用 SQLite 产出 unavailable 状态", repr(unavailable))

        # C10 权威成功而投影失败 → 202；同 key 重试不多写，可 read-your-write
        root5 = tempfile.mkdtemp(prefix="projection-lag-")
        extra_roots.append(root5)
        l5 = WriterLease(os.path.join(root5, "authority", "writer.lock")).acquire()
        a5 = BusinessEventStore(os.path.join(root5, "authority"), lease=l5,
                                clock=lambda: 2000)
        p5 = ProjectionStore(os.path.join(root5, "projection.db"), clock=lambda: 2001)

        class FailingProjection:
            def __init__(self, real):
                self.real = real
            def __getattr__(self, name):
                return getattr(self.real, name)
            def apply_batch(self, _batch):
                raise ProjectionError("injected_projection_failure", "test")
            def mark_error(self, code):
                self.real.mark_error(code)

        service = ReviewCommandService(a5, FailingProjection(p5))
        command = dict(
            aggregate_id="case-lag", command="claim", actor=actor(),
            expected_version=0, payload={}, idempotency_key="lag-1", now=2000)
        lag = service.execute(**command)
        replay = service.execute(**command)
        ryw = service.read_your_write(lag["reconcile_token"])
        wrong_case = service.read_your_write(
            lag["reconcile_token"], aggregate_id="case-other",
            principal_id="u1", tenant_id="t1")
        wrong_actor = service.read_your_write(
            lag["reconcile_token"], aggregate_id="case-lag",
            principal_id="u2", tenant_id="t1")
        report(lag["http_status"] == 202 and lag["projection_lag"] is True
               and replay["replayed"] is True and len(a5.batches()) == 1
               and ryw and ryw["result"]["version"] == 1
               and wrong_case is None and wrong_actor is None,
               "C10 投影失败202 + 同key不重写 + 权威read-your-write绑定案/人",
               repr((lag, replay, ryw)))
        l5.release()

        # C11 未知 reconcile token 不许返回别的结果
        report(service.read_your_write("missing") is None,
               "C11 未知 reconcile token 返回空")
        # 临时故障解除后无需重启；reconcile 会追平同一权威批次。
        service.projection = p5
        reconciled = service.reconcile()
        report(reconciled["status"] == "fresh"
               and p5.get_case("case-lag")["version"] == 1,
               "C11b 临时投影失败解除后可在线 reconcile 到 fresh", repr(reconciled))

        # C12 同进程两线程写由 service 单飞，投影不能先应用 seq2。
        import threading
        root6 = tempfile.mkdtemp(prefix="projection-threaded-")
        extra_roots.append(root6)
        l6 = WriterLease(os.path.join(root6, "authority", "writer.lock")).acquire()
        a6 = BusinessEventStore(os.path.join(root6, "authority"), lease=l6,
                                clock=lambda: 3000)
        p6 = ProjectionStore(os.path.join(root6, "projection.db"), clock=lambda: 3001)
        s6 = ReviewCommandService(a6, p6)
        first = s6.execute(
            aggregate_id="case-threaded", command="claim", actor=actor(),
            expected_version=0, payload={}, idempotency_key="thread-claim", now=3000)
        barrier = threading.Barrier(2)
        threaded = []

        def write_version(key, notes):
            barrier.wait()
            try:
                threaded.append(s6.execute(
                    aggregate_id="case-threaded", command="save_draft", actor=actor(),
                    expected_version=1, payload={"form": {}, "notes": notes,
                                                 "evidence_selections": [],
                                                 "references": []},
                    idempotency_key=key, now=3001))
            except Exception as exc:  # noqa: BLE001
                threaded.append(exc)

        ts = [threading.Thread(target=write_version, args=("thread-%d" % i, str(i)))
              for i in (1, 2)]
        for thread in ts:
            thread.start()
        for thread in ts:
            thread.join()
        successes = [x for x in threaded if isinstance(x, dict)]
        conflicts = [x for x in threaded
                     if getattr(x, "code", None) == "version_conflict"]
        status6 = p6.status(a6.head())
        report(first["http_status"] == 200 and len(successes) == 1
               and len(conflicts) == 1 and status6["status"] == "fresh"
               and status6["projection"]["applied_seq"] == 2,
               "C12 两线程同版本写恰一成功且投影保持 fresh", repr(threaded))

        # C13 不同案件并发 claim 都成功；全局单飞只排顺序，不误拒第二案。
        barrier = threading.Barrier(2)
        different = []

        def claim_case(case_id):
            barrier.wait()
            try:
                different.append(s6.execute(
                    aggregate_id=case_id, command="claim", actor=actor(),
                    expected_version=None, payload={},
                    idempotency_key="claim-" + case_id, now=3010))
            except Exception as exc:  # noqa: BLE001
                different.append(exc)

        ts = [threading.Thread(target=claim_case, args=(case_id,))
              for case_id in ("case-a", "case-b")]
        for thread in ts:
            thread.start()
        for thread in ts:
            thread.join()
        report(len([x for x in different if isinstance(x, dict)
                    and x["http_status"] == 200]) == 2
               and p6.status(a6.head())["status"] == "fresh",
               "C13 两线程领取不同案件均成功", repr(different))

        # C14 lease 到期由 service 追加释放事件，随后新 reviewer 可领取。
        exp = s6.execute(
            aggregate_id="case-expiring", command="claim", actor=actor(),
            expected_version=None, payload={}, idempotency_key="expire-claim", now=4000)
        expiry = exp["result"]["lease_expires"]
        released = s6.expire_if_due("case-expiring", now=expiry + 1)
        reclaimed = s6.execute(
            aggregate_id="case-expiring", command="claim",
            actor={"principal_id": "u2", "tenant_id": "t1"},
            expected_version=None, payload={}, idempotency_key="expire-reclaim",
            now=expiry + 2)
        state = a6.state("case-expiring")
        report(released and released["result"]["status"] == "released"
               and released["result"]["released_draft_id"]
               and reclaimed["result"]["assignee"] == "u2"
               and state["version"] == 3,
               "C14 lease 到期保存草稿、释放、可由新人领取", repr(state))

        # C15 readiness/status 与写同锁：authority 已提交但投影未 apply 时不得误报。
        apply_entered = threading.Event()
        allow_apply = threading.Event()
        original_apply = p6.apply_batch

        def blocked_apply(batch):
            if batch.get("aggregate_id") == "case-readiness-race":
                apply_entered.set()
                allow_apply.wait(5)
            return original_apply(batch)

        p6.apply_batch = blocked_apply
        write_result = []
        status_result = []
        writer = threading.Thread(target=lambda: write_result.append(s6.execute(
            aggregate_id="case-readiness-race", command="claim", actor=actor(),
            expected_version=None, payload={}, idempotency_key="readiness-race",
            now=8000)))
        writer.start()
        apply_entered.wait(5)
        reader = threading.Thread(target=lambda: status_result.append(s6.status()))
        reader.start()
        reader.join(0.1)
        waited = reader.is_alive()
        allow_apply.set()
        writer.join(5)
        reader.join(5)
        p6.apply_batch = original_apply
        report(waited and write_result[0]["http_status"] == 200
               and status_result[0]["status"] == "fresh",
               "C15 status 等待在途 authority+projection 原子窗口，不误报")
        l6.release()

        projection2.close()
        lease.release()
    finally:
        shutil.rmtree(root, ignore_errors=True)
        for extra in extra_roots:
            shutil.rmtree(extra, ignore_errors=True)

    print("----------------------------------------")
    if not failed:
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
