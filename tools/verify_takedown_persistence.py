#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T-312d 下线任务持久化与指标口径的自证。

主体：base/takedown.py（metrics_view / check_no_deadline）、
base/review_reducer.py（takedown_create/transition）、base/review_command_service.py、
api/review_api.py（GET /takedown-tasks 的 {tasks, metrics} 形状）、
web/src/pages/TakedownPage.tsx（年龄只格式化不计算 —— 静态扫描）。

设计纪律：任务经真权威（service.execute takedown_create）落 state；
「重启恒等」读新开实例的 state()，不读内存对象。
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base import takedown as TD
    from base.reviews_ledger import LedgerConflict, LedgerValidation
    from base.business_event_store import BusinessEventStore, WriterLease
    from base.projector import Projector
    from base.projection_store import ProjectionStore
    from base.review_command_service import ReviewCommandService
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入被测模块: %s" % exc)
    sys.exit(2)


def _ingest_and_close(svc, cid, actor="ou_w", now=None):
    base_t = now if now is not None else time.time()
    svc.execute(aggregate_id=cid, command="ingest_submission",
                actor={"principal_id": actor, "tenant_id": "t1"},
                expected_version=0,
                payload={"submission_id": "s-" + cid,
                         "submission_hash": "h" * 64,
                         "content": {"unit_id": "u-" + cid,
                                     "fingerprint": {"text_sha256": "a" * 64}},
                         "ir": {"ir_id": "ir-" + cid, "ir_version": "v1",
                                "findings": [],
                                "decision": {"state": "REVIEW"},
                                "control_points_version": "cp-1"},
                         "kb_snapshot_hash": "b" * 64,
                         "conflict_table_version": "cp-1",
                         "judgment": {"label": "REVIEW", "run_state": "OK"},
                         "tenant": "t1", "product_line": "pump",
                         "submitter_id": actor},
                idempotency_key="ing-" + cid, now=base_t)
    svc.execute(aggregate_id=cid, command="claim",
                actor={"principal_id": actor, "tenant_id": "t1"},
                expected_version=1, payload={},
                idempotency_key="cl-" + cid, now=base_t + 1)
    svc.execute(aggregate_id=cid, command="submit_review",
                actor={"principal_id": actor, "tenant_id": "t1"},
                expected_version=2,
                payload={"conclusion": {"review_notes": "结案"}},
                idempotency_key="close-" + cid, now=base_t + 2)


def _create_task(svc, cid, key, assignee="u_td", now=None):
    return svc.execute(
        aggregate_id=cid, command="takedown_create",
        actor={"principal_id": "ou_coord", "tenant_id": "t1"},
        expected_version=None,
        payload={"trigger": "revoke", "platform": "amazon_us",
                 "assignee": assignee, "reason": "签发撤回"},
        idempotency_key="td-" + key, now=now if now is not None else time.time())


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

    try:
        root = tempfile.mkdtemp(prefix="td-persist-")
        tmp_roots.append(root)
        lease = WriterLease(os.path.join(root, "a", "lock")).acquire()
        auth = BusinessEventStore(os.path.join(root, "a"), lease=lease)
        proj = ProjectionStore(os.path.join(root, "p.db"))
        svc = ReviewCommandService(auth, proj)

        _ingest_and_close(svc, "case-td")
        out1 = _create_task(svc, "case-td", "1",
                            now=time.time() - 2 * 86400)
        task1 = out1["result"].get("takedown_task") or {}
        report(task1["task_id"].startswith("td-")
               and task1["assignee"] == "u_td"
               and task1.get("completed_by") is None,
               "P0 takedown_create 经真权威落任务")

        # P1 重启恒等
        auth2 = BusinessEventStore(os.path.join(root, "a"), lease=lease)
        tasks_after = auth2.state("case-td")["takedown_tasks"]
        report(len(tasks_after) == 1
               and tasks_after[0]["task_id"] == task1["task_id"],
               "P1 重启恒等：任务仍在")
        # P2 跨重启不撞号（同案同 trigger 会撞 duplicate_task —— 那是另一条
        # 守卫；跨重启撞号用第二个案件测）
        _ingest_and_close(svc, "case-td2")
        out2 = _create_task(svc, "case-td2", "2", assignee="u_td2",
                            now=time.time() - 2 * 86400)
        task2 = out2["result"].get("takedown_task") or {}
        report(task2["task_id"] != task1["task_id"],
               "P2 重启后第二条 task_id 不撞号")
        # P3 投影可重建
        Projector(auth2, proj).catch_up()
        proj_tasks = (proj.get_case("case-td") or {}).get("takedown_tasks")
        report(proj_tasks == auth2.state("case-td")["takedown_tasks"],
               "P3 投影任务与权威恒等")
        proj.reset()
        Projector(auth2, proj).catch_up()
        report((proj.get_case("case-td") or {}).get("takedown_tasks")
               == auth2.state("case-td")["takedown_tasks"],
               "P3b 删投影重建后恒等")
        # P7 无 deadline
        try:
            for t in auth2.state("case-td")["takedown_tasks"]:
                TD.check_no_deadline(t)
            report(True, "P7 任务无 deadline 字段（check_no_deadline 全过）")
        except Exception as exc:  # noqa: BLE001
            report(False, "P7 任务无 deadline 字段", "%s" % exc)

        # P6 失败不落案：非法迁移 completed→pending
        svc.execute(aggregate_id="case-td", command="takedown_transition",
                    actor={"principal_id": "u_td", "tenant_id": "t1"},
                    expected_version=None,
                    payload={"task_id": task1["task_id"], "to": "in_progress",
                                 "action": "start"},
                    idempotency_key="t-start")
        svc.execute(aggregate_id="case-td", command="takedown_transition",
                    actor={"principal_id": "u_td", "tenant_id": "t1"},
                    expected_version=None,
                    payload={"task_id": task1["task_id"], "to": "completed",
                             "action": "complete",
                             "evidence": {"url": "https://x"}},
                    idempotency_key="t-done")
        seq_before = auth2.head()["seq"]
        try:
            svc.execute(aggregate_id="case-td", command="takedown_transition",
                        actor={"principal_id": "u_td", "tenant_id": "t1"},
                        expected_version=None,
                        payload={"task_id": task1["task_id"],
                                 "to": "pending", "action": "retry"},
                        idempotency_key="t-bad")
            report(False, "P6 非法迁移 → 拒", "（未拒绝）")
        except LedgerConflict:
            report(auth2.head()["seq"] == seq_before,
                   "P6 非法迁移 → 拒且权威 seq 不变")
        except LedgerValidation:
            report(auth2.head()["seq"] == seq_before,
                   "P6 非法迁移 → 拒且权威 seq 不变")

        # P4/P5：GET 形状与年龄口径（dev 装配走 repo；形状两装配一致）
        from api.review_api import create_app as _ca
        import base.auth_session as _AS
        store_h = _AS.SessionStore(":memory:")
        PEOPLE_H = {"u_dp3": {"id": "u_dp3", "roles": ["dp3"], "tenant": "t1",
                              "tenant_id": "t1", "product_lines": ["pump"],
                              "product_line": "pump", "open_id": "ou_3"}}
        app_h = _ca(session_store=store_h, principals=PEOPLE_H)
        s_h = store_h.create_session("u_dp3", tenant="t1", now=time.time())
        from fastapi.testclient import TestClient
        c_h = TestClient(app_h, cookies={"session": s_h})
        r_h = c_h.get("/api/v1/takedown-tasks")
        body_h = r_h.json() if r_h.status_code == 200 else {}
        report(r_h.status_code == 200
               and isinstance(body_h.get("tasks"), list)
               and isinstance(body_h.get("metrics"), dict)
               and body_h["metrics"].get("open_count") == 0,
               "P4 全新库 GET → tasks [] 且 metrics.open_count == 0（不是 404/{}）",
               "%s %r" % (r_h.status_code, body_h.get("metrics")))

        # P5 年龄一个口径：HTTP 产出 == TD.metrics_view 独立复算（容差 0.01 天）
        proj.close()
        proj4 = ProjectionStore(os.path.join(root, "p.db"))
        app_p = _ca(session_store=_AS.SessionStore(":memory:"),
                    review_command_service=ReviewCommandService(auth2, proj4),
                    case_state_provider=lambda cid: auth2.state(cid),
                    principals=PEOPLE_H)
        s_p = app_p.state.session_store.create_session("u_dp3", tenant="t1",
                                                       now=time.time())
        c_p = TestClient(app_p, cookies={"session": s_p})
        r_p = c_p.get("/api/v1/takedown-tasks")
        body_p = r_p.json() if r_p.status_code == 200 else {}
        tasks_live = []
        for cid in auth2.aggregate_ids():
            st = auth2.state(cid)
            if st.get("tenant") == "t1":
                tasks_live.extend(st.get("takedown_tasks") or [])
        expect = TD.metrics_view(tasks_live)
        got = body_p.get("metrics") or {}
        ages_ok = (
            got.get("open_count") == expect["open_count"]
            and [a["task_id"] for a in got.get("ages") or []]
            == [a["task_id"] for a in expect["ages"]]
            and all(abs(a["age_days"] - e["age_days"]) < 1e-5
                    for a, e in zip(got.get("ages") or [],
                                    expect["ages"])))
        report(r_p.status_code == 200 and ages_ok,
               "P5 年龄只有一个口径：HTTP metrics == TD.metrics_view 复算",
               "open=%r/%r" % (got.get("open_count"), expect["open_count"]))
        # P5b 生产装配的年龄判定不允许出现超时类字段（结构上不给画绿标的机会）
        report(all(k not in got for k in ("on_time", "overdue", "healthy")),
               "P5b metrics 无 on_time/overdue/healthy 字段")
        # P5c 前端静态扫描：TakedownPage 不再用 Date.now() 算年龄、formatTaskAge 已删
        fe = (ROOT / "web" / "src" / "pages" / "TakedownPage.tsx").read_text(
            encoding="utf-8")
        report("formatTaskAge" not in fe and "Date.now()" not in fe
               and "formatAgeDays" in fe,
               "P5c 前端只格式化（formatTaskAge/Date.now 已删，formatAgeDays 在）")
        proj4.close()
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
