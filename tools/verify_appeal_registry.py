#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_appeal_registry.py - T-311a: appeals into authority.

## Why this file exists before the implementation

`api/write_api.py` keeps appeals in an in-process dict (`AppealStore._items`)
with an auto-increment counter (`appeal-%d % self._seq`). Three real defects
measured 2026-10-24:

  1. `_seq` resets on restart -> a new appeal reuses `appeal-1` and collides
     with history. `verify_write_api.py` creates a fresh AppealStore() each
     run, so it structurally cannot see the collision.
  2. `mark_stale()` (paused 30 days -> stale) has **zero** callers in
     production; only verify_write_api calls it. A rule with no trigger point
     is not a rule.
  3. appeals carry **no `tenant` field**, while `GET /api/v1/appeals`
     filters by `row.get("tenant") == tenant` -> in-memory appeals are never
     findable.

So A0-A3 below go red first, green after the reducer lands (AGENTS.md 2.1).

## Coverage

  A0  appeal ids are content-derived, not process counters (no restart collision)
  A1  every appeal carries tenant
  A2  open -> pause -> stale -> migrate / withdraw five-state machine
  A3  pause/stale/migrate/withdraw only write their own fields (RL-12 (4))
  A4  non-appellant migrate / withdraw rejected
  A5  pause is idempotent (no open appeals -> empty result, not an error)
  A6  stale does not close (state must stay 'stale', never 'closed')
  A7  appeal survives in the event snapshot (replay keeps it)
  A8  appeals land in review_cases projection (they belong to a case)

Exit codes: 0 all pass / 1 red / 2 untested (import failure)
"""
from __future__ import annotations

import copy
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SUBJECTS = (
    "base/review_reducer.py",
    "base/projection_store.py",
)

try:
    from base.review_reducer import initial_state, reduce_command
    from base.reviews_ledger import (
        LedgerConflict, LedgerNotFound, LedgerValidation)
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: cannot import reducer: %s" % exc)
    sys.exit(2)


CASE = "case-appeal-1"


def _st():
    st = initial_state(CASE)
    st["tenant"] = "on_t1"
    return st


def _open(state, actor="ou_sub", reason="misjudged", version=0):
    return reduce_command(state, "appeal_open", actor, version,
                          {"case_id": CASE, "reason": reason}, now=1000)


def _step(state, cmd, actor, version, **payload):
    return reduce_command(state, cmd, actor, version,
                          {**payload, "case_id": CASE}, now=2000 + version)


def _denied(state, cmd, actor, version, **payload):
    try:
        _step(state, cmd, actor, version, **payload)
        return None
    except (LedgerConflict, LedgerValidation, LedgerNotFound) as exc:
        return exc.code


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
    if "appeal_open" not in src:
        # A0-A8 have no object yet. Report red, not "untested": the defect
        # (process-counter ids, missing tenant) is real and present today.
        report(False, "A0-A8 appeal_* commands exist in reducer",
               "reducer has no appeal_open; defects 1-3 from the docstring "
               "are live in api/write_api.AppealStore")
        print("----------------------------------------")
        print("%d passed, %d failed" % (passed, failed), file=sys.stderr)
        return 1

    # ---- A0/A1: id derivation and tenant ----
    s1, ev1, r1 = _open(_st())
    a1 = r1["appeal"]
    report(a1["appeal_id"].startswith("appeal-")
           and not a1["appeal_id"].endswith("-1"),
           "A0a appeal_id is not a bare process counter", repr(a1["appeal_id"]))

    # restart simulation: rebuild from the same *empty* initial state and open
    # a second appeal with the same inputs. A counter-based id would produce
    # 'appeal-1' both times; a content-derived one differs by seq.
    s2, _, r2 = _open(_st(), actor="ou_sub2", reason="second")
    report(r2["appeal"]["appeal_id"] != a1["appeal_id"],
           "A0b different inputs -> different id")

    # same store, second appeal: seq advances, ids differ
    s1b, _, r1b = _open(s1, actor="ou_sub", reason="another", version=1)
    report(r1b["appeal"]["appeal_id"] != a1["appeal_id"],
           "A0c same store second appeal -> distinct id (seq advances)")

    report(a1.get("tenant") == "on_t1",
           "A1a appeal carries tenant", repr(a1.get("tenant")))
    report(a1.get("appellant") == "ou_sub" and a1.get("reason") == "misjudged",
           "A1b appellant/reason recorded verbatim")

    # ---- A2/A3: five-state machine and field discipline ----
    s_pause, _, r_pause = _step(s1b, "appeal_pause", "system", 2,
                                reason="version_invalidated")
    paused = [a for a in s_pause["appeals"] if a["appeal_id"] == a1["appeal_id"]]
    report(paused and paused[0]["state"] == "paused_version_invalidated",
           "A2a pause -> paused_version_invalidated",
           repr(paused[0]["state"] if paused else None))
    report(paused and paused[0]["state"] != "closed",
           "A2b pause does NOT close (RL-12)")
    # field discipline: everything except the three pause keys unchanged
    before = a1
    after = paused[0] if paused else {}
    allowed = {"state", "pause_reason", "paused_at"}
    touched = sorted(k for k in set(before) | set(after)
                     if k not in allowed and before.get(k) != after.get(k))
    report(touched == [], "A3a pause writes only state/pause_reason/paused_at",
           repr(touched))

    # stale: paused_at in the past
    # ★ 时钟方向：_step 用的 now 是 2000+v 秒（模拟时钟，1970 年前后）。
    #   第一版把 paused_at 写成 "2020-01-01" —— 那在 now 之**后**，
    #   差值恒为负，stale 永不触发，而看起来像「实现漏了」。
    #   判据必须让 paused_at 落在 now 之前 31 天。
    import calendar as _cal
    import time as _time
    stale_state = copy.deepcopy(s_pause)
    past = 2003 - 31 * 86400
    past_iso = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime(past))
    for a in stale_state["appeals"]:
        if a["appeal_id"] == a1["appeal_id"]:
            a["paused_at"] = past_iso
    s_stale, _, r_stale = _step(stale_state, "appeal_stale", "system", 3, days=30)
    stale_row = next((a for a in s_stale["appeals"]
                      if a["appeal_id"] == a1["appeal_id"]), {})
    report(stale_row.get("state") == "stale",
           "A6a paused > 30d -> stale", repr(stale_row.get("state")))
    report(stale_row.get("state") != "closed",
           "A6b stale does not close (RL-12)")
    report(stale_row.get("reason") == "misjudged"
           and stale_row.get("appellant") == "ou_sub",
           "A3b stale keeps reason/appellant verbatim")

    # migrate by non-appellant -> rejected; by appellant -> migrated
    s_paused_only = copy.deepcopy(s_pause)
    report(_denied(s_paused_only, "appeal_migrate", "ou_other", 3,
                   appeal_id=a1["appeal_id"]) == "not_original_appellant",
           "A4a non-appellant migrate -> not_original_appellant")
    s_mig, _, _ = _step(s_paused_only, "appeal_migrate", "ou_sub", 3,
                        appeal_id=a1["appeal_id"])
    mig_row = next(a for a in s_mig["appeals"] if a["appeal_id"] == a1["appeal_id"])
    report(mig_row["state"] == "migrated", "A2c appellant migrate -> migrated",
           repr(mig_row["state"]))

    # withdraw: reason required; non-appellant rejected; terminal state rejected
    s_wd_base, _, r_wd = _open(_st(), actor="ou_sub", reason="to withdraw")
    wid = r_wd["appeal"]["appeal_id"]
    report(_denied(s_wd_base, "appeal_withdraw", "ou_sub", 1, appeal_id=wid) ==
           "missing_reason", "A4b withdraw without reason -> missing_reason")
    report(_denied(s_wd_base, "appeal_withdraw", "ou_other", 1, appeal_id=wid,
                   reason="x") == "not_original_appellant",
           "A4c non-appellant withdraw -> not_original_appellant")
    s_wd, _, _ = _step(s_wd_base, "appeal_withdraw", "ou_sub", 1,
                       appeal_id=wid, reason="no longer needed")
    wd_row = next(a for a in s_wd["appeals"] if a["appeal_id"] == wid)
    report(wd_row["state"] == "withdrawn", "A2d withdraw -> withdrawn")
    report(_denied(s_wd, "appeal_withdraw", "ou_sub", 2, appeal_id=wid,
                   reason="again") == "terminal_state",
           "A4d withdraw on withdrawn -> terminal_state")

    # ---- A5: pause idempotent ----
    # ★ 必须自带 try/except。第一版没有，实测把「无事可暂停就抛错」的变异下，
    #   异常冒到 main 的兜底，本文件退 2 打印 UNTESTED —— 而 A5 本来要报的红
    #   一条都没出现。这是**第三次**踩同一个形状（C14、G4c-G4g、这里）：
    #   一条判据如果只可能绿或「没跑到」，它就不是判据。
    try:
        s_none, _, r_none = _step(s_wd, "appeal_pause", "system", 2,
                                  reason="version_invalidated")
        a5_ok = (isinstance(r_none.get("paused"), list) and r_none["paused"] == [])
        a5_detail = repr(r_none.get("paused"))
    except Exception as exc:  # noqa: BLE001
        a5_ok = False
        a5_detail = "%s: %s" % (type(exc).__name__, exc)
    report(a5_ok, "A5 pause with no open appeals -> empty list, not an error",
           a5_detail)

    # ---- A7: event snapshot keeps appeals ----
    report(ev1[0]["state"].get("appeals"),
           "A7 appeal enters the event snapshot (survives replay)")
    report(ev1[0]["state"]["appeals"][0].get("tenant") == "on_t1",
           "A7b snapshot appeal carries tenant")

    # ---- A9/A10: production trigger point (ReviewCommandService) ----
    #
    # T-311 施工单 §一 第 4 条：`mark_stale` 生产 0 调用。这一段验的是
    # **服务层那条真实路径**，不是 reducer 再测一遍。
    from base.business_event_store import BusinessEventStore, WriterLease
    from base.projection_store import ProjectionStore
    from base.review_command_service import ReviewCommandService
    from base.projector import Projector
    import tempfile as _tmp

    try:
        d = _tmp.mkdtemp(prefix="appeal-sweep-")
        lease = WriterLease(os.path.join(d, "a", "lock")).acquire()
        auth = BusinessEventStore(os.path.join(d, "a"), lease=lease)
        proj = ProjectionStore(os.path.join(d, "p.db"))
        svc = ReviewCommandService(auth, proj)

        # 两个案件各开一条申诉，然后 pause 并把 paused_at 拨到 31 天前
        for cid in ("case-sw-1", "case-sw-2"):
            auth.execute(aggregate_id=cid, command="appeal_open",
                         actor={"principal_id": "ou_sub", "tenant_id": "on_t1"},
                         expected_version=0,
                         payload={"reason": "x", "tenant": "on_t1"},
                         idempotency_key="k-" + cid, now=1000)
            auth.execute(aggregate_id=cid, command="appeal_pause",
                         actor={"principal_id": "sys", "tenant_id": "on_t1"},
                         expected_version=1,
                         payload={"reason": "version_invalidated"},
                         idempotency_key="kp-" + cid, now=1000)
        # 把 paused_at 拨回过去（直接改权威状态不现实，改用 now 往前推）
        past = 1000 - 31 * 86400
        # ★ days 必须被真正传下去，否则「30 天」这条业务规则没有执行点。
        #   第一版只用 31 天验，实测把 days 改成 0 仍然绿 —— 因为 now 已推后
        #   31 天，判据 `now - paused_at > 0` 照样成立。加一个 29 天的时间点：
        #   它必须**不**触发。两个点一起才钉住 days。
        out_29 = svc.mark_appeals_stale(now=1000 + 29 * 86400, days=30)
        states_29 = [a.get("state") for cid in ("case-sw-1", "case-sw-2")
                     for a in auth.state(cid).get("appeals") or []]
        report(out_29.get("staled") == 0
               and all(x == "paused_version_invalidated" for x in states_29),
               "A9b 29 天未到期 -> 一个都不转（days 被真正使用）",
               "staled=%r states=%r" % (out_29.get("staled"), states_29))

        out2 = svc.mark_appeals_stale(now=1000 + 31 * 86400, days=30)
        states = [a.get("state") for cid in ("case-sw-1", "case-sw-2")
                  for a in auth.state(cid).get("appeals") or []]
        a9_ok = out2.get("staled") == 2 and all(x == "stale" for x in states)
        a9_detail = "staled=%r errors=%r states=%r" % (
            out2.get("staled"), out2.get("errors"), states)
    except Exception as exc:  # noqa: BLE001
        a9_ok, a9_detail = False, "%s: %s" % (type(exc).__name__, exc)
    report(a9_ok, "A9 服务层扫全案把超期申诉转 stale（2/2 案）", a9_detail)

    # A10: 没有 paused 的案件必须被跳过，且不计入 staled、不报错
    try:
        out3 = svc.mark_appeals_stale(now=1000 + 90 * 86400, days=30)
        a10_ok = out3.get("staled") == 0 and not out3.get("errors")
        a10_detail = repr(out3)
    except Exception as exc:  # noqa: BLE001
        a10_ok, a10_detail = False, "%s: %s" % (type(exc).__name__, exc)
    report(a10_ok, "A10 无 paused 申诉时幂等（staled=0 且无 error）", a10_detail)
    try:
        proj.close()
    except Exception:
        pass

    # ---- A11/A12: 生产路径（HTTP → authority），含重启恒等 ----
    #
    # A9/A10 验的是服务层；这一段验**路由层**：一次真实 POST 是否落进权威、
    # 重启后同 key 重放是否仍只留一条。改前做不到 —— 幂等缓存在
    # `app.state.idempotency`（进程内 dict），重启即失。
    try:
        from fastapi.testclient import TestClient
        from api.review_api import create_app
        import base.auth_session as _AS

        d11 = _tmp.mkdtemp(prefix="appeal-http-")
        lease1 = WriterLease(os.path.join(d11, "a", "lock")).acquire()
        auth1 = BusinessEventStore(os.path.join(d11, "a"), lease=lease1)
        proj1 = ProjectionStore(os.path.join(d11, "p.db"))
        svc1 = ReviewCommandService(auth1, proj1)
        src_st = initial_state("case-http")
        src_st.update({"tenant": "on_t1", "product_line": "p",
                       "submitter_id": "ou_sub", "version": 1,
                       "ir": {"ir_id": "ir1", "findings": [],
                              "decision": {"state": "REVIEW"}}})
        auth1.execute(aggregate_id="case-http", command="ingest_submission",
                      actor={"principal_id": "ou_sub", "tenant_id": "on_t1"},
                      expected_version=0,
                      payload={"submission_id": "s1", "submission_hash": "h" * 64,
                               "content": {"unit_id": "u1",
                                           "fingerprint": {"text_sha256": "a" * 64}},
                               "ir": {"ir_id": "ir1", "findings": [],
                                      "decision": {"state": "REVIEW"},
                                      "control_points_version": "cp-1"},
                               "kb_snapshot_hash": "b" * 64,
                               "conflict_table_version": "cp-1",
                               "judgment": {"label": "REVIEW", "run_state": "OK"},
                               "tenant": "on_t1", "product_line": "p",
                               "submitter_id": "ou_sub"},
                      idempotency_key="ing", now=1000)
        Projector(auth1, proj1).catch_up()

        def _app(svc):
            ap = create_app(review_command_service=svc,
                            enabled_write_capabilities={
                                "/api/v1/appeals",
                                "/api/v1/appeals/{id}/migrate",
                                "/api/v1/appeals/{id}/withdraw"},
                            principals={"ou_sub": {
                                "roles": ["submitter"], "tenant": "on_t1",
                                "product_lines": ["p"],
                                "open_id": "ou_1", "tenant_id": "on_t1"}})
            ap.state.app_env = "dev"
            st_ = _AS.SessionStore(":memory:")
            sid_ = st_.create_session("ou_sub", tenant="on_t1", provider="dev",
                                      issuer="x", csrf_token="c1")
            ap.state.session_store = st_
            ap.state.session_cookie_name = "session"
            ap.state.repository.cases = [{
                "case_id": "case-http", "tenant": "on_t1", "product_line": "p",
                "submitter_id": "ou_sub", "assignee_id": None, "actionable": True,
                "ir": {"ir_id": "ir1", "findings": [],
                       "decision": {"state": "REVIEW", "layer": "DP3",
                                    "release_status": "待放行"}}}]
            return ap, sid_

        ap1, sid1 = _app(svc1)
        cl1 = TestClient(ap1, cookies={"session": sid1})
        r_open = cl1.post("/api/v1/appeals",
                          json={"case_id": "case-http", "reason": "misjudged"},
                          headers={"Idempotency-Key": "ap-1"})
        aid11 = (r_open.json() or {}).get("appeal_id")
        # ★ 顶层必须有 appeal_id：前端 AppealsPage 读的是 created.appeal_id。
        #   权威把结果包在 result["appeal"] 里，不铺平的话前端静默 undefined。
        a11_ok = (r_open.status_code == 200 and isinstance(aid11, str)
                  and (r_open.json() or {}).get("state") == "open")
        a11_detail = "%s %r" % (r_open.status_code, aid11)
    except Exception as exc:  # noqa: BLE001
        a11_ok, a11_detail, aid11 = False, "%s: %s" % (type(exc).__name__, exc), None
    report(a11_ok, "A11 HTTP POST /appeals 落进权威且顶层带 appeal_id", a11_detail)

    # 重启：释放 lease、关投影、重建
    try:
        lease1.release()
        proj1.close()
        lease2 = WriterLease(os.path.join(d11, "a", "lock")).acquire()
        auth2 = BusinessEventStore(os.path.join(d11, "a"), lease=lease2)
        proj2 = ProjectionStore(os.path.join(d11, "p.db"))
        svc2 = ReviewCommandService(auth2, proj2)
        Projector(auth2, proj2).catch_up()
        ap2, sid2 = _app(svc2)
        cl2 = TestClient(ap2, cookies={"session": sid2})
        before = len(auth2.state("case-http").get("appeals") or [])
        r_rep = cl2.post("/api/v1/appeals",
                         json={"case_id": "case-http", "reason": "misjudged"},
                         headers={"Idempotency-Key": "ap-1"})
        after = len(auth2.state("case-http").get("appeals") or [])
        a12_ok = (before == 1 and after == 1
                  and (r_rep.json() or {}).get("replayed") is True)
        a12_detail = "before=%d after=%d replayed=%r" % (
            before, after, (r_rep.json() or {}).get("replayed"))
        lease2.release()
        proj2.close()
    except Exception as exc:  # noqa: BLE001
        a12_ok, a12_detail = False, "%s: %s" % (type(exc).__name__, exc)
    report(a12_ok, "A12 重启后同 key 重放仍只留一条（幂等在权威里）", a12_detail)

    # ---- A13: 生产申诉分支不得再套内存幂等 ----
    #
    # ★ 这条是我在做变异时想清楚的一件事：`_run_appeal` 内部已经走
    #   `service.execute(..., idempotency_key=...)`，那是**权威的跨重启幂等**。
    #   外面再包一层 `_idempotent()`（app.state.idempotency，进程内 dict）是
    #   冗余的 —— 它不会造成重复建案，但会让 `replayed` 在重启前恒为 False，
    #   而且多出一份与权威不一致的缓存。
    #   变异 M2 没能让 A12 变红，正是因为它**不是 bug**。判据要直接测这件事本身。
    # ★ 第一版切分写错了：用 `return _idempotent(` 当分隔符，
    #   而变异恰好把它插在开头 —— 切完左边为空，判据恒真（M2 照样绿）。
    #   换成结构判据：**每一个 _run_appeal( 调用点前面 200 字符内不许出现
    #   `_idempotent(`**。这直接对应「生产分支是否被内存幂等包住」。
    src_api = open(os.path.join(ROOT, "api", "write_api.py"),
                   encoding="utf-8").read()
    offenders = []
    pos = 0
    while True:
        idx = src_api.find("_run_appeal(", pos)
        if idx < 0:
            break
        window = src_api[max(0, idx - 200):idx]
        # 定义处本身不算调用点
        if not window.rstrip().endswith("def"):
            if "_idempotent(" in window:
                offenders.append(src_api[max(0, idx - 60):idx].splitlines()[-1:])
        pos = idx + 1
    report(offenders == [],
           "A13 生产申诉分支不套内存 _idempotent（幂等只在权威一处）",
           repr(offenders[:2]))

    # ---- A8: projection puts appeals in review_cases (not a separate table) ----
    src_proj = open(os.path.join(ROOT, "base", "projection_store.py"),
                    encoding="utf-8").read()
    report("appeals" not in src_proj or "grant_registry" in src_proj,
           "A8 appeals project into review_cases (same aggregate as the case)")

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
