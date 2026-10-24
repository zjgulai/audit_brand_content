#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_grant_registry.py — T-314: grant registry into authority.

## Why this verifier exists before the implementation

`base/projection_store.apply_batch()` unconditionally writes **any** batch into
`review_cases`, ignoring `aggregate_type`. Measured (2026-10-24, section G0):

    batch = {aggregate_type: "grant_registry", aggregate_id: "grants:on_x", ...}
    proj.apply_batch(batch)          -> accepted
    proj.list_cases()                -> ["grants:on_x"]

So once a grant aggregate reaches the authority, it shows up as a *case* in
`GET /api/v1/cases`. A reviewer would see a case named `grants:on_x`, and
`can_read_content` would judge it by case ACL.

G0 therefore goes **red first, green after the fix** -- per AGENTS.md 2.1.

## Coverage

  G0  projection isolation: grant_registry must not land in review_cases
  G1  three-state flow: propose -> execute -> approve
  G2  three distinct actors (three negative cases)
  G3  scope overreach: cross-tenant / missing product line / empty set
  G4  restart identity
  G5  allowlist actually takes effect (can_act flips)
  G6  reverse control: empty injected source -> can_act must be False
  G7  audit quad (who / when / what changed / why)
  G8  grant_id does not collide across restarts
  G9  validate_grant_actors is called at approve time

## Exit codes

  0 all pass - 1 red - 2 untested (import failure)

## Current state (2026-10-24)

  G0 red (hole proven). G1-G9 have no object yet: reducer has no grant_* branch.
  This file SHOULD exit 1 right now. That is the accurate reading; do not
  delete G0 to make CI green.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Subjects this verifier covers. Listed as literal paths because
# tools/verify_coverage.py section C requires the filename to appear verbatim
# in this source -- an import statement does not satisfy it (that check asks
# "does the verifier name what it verifies", not "does it import it").
SUBJECTS = (
    "base/review_reducer.py",
    "base/projection_store.py",
    "base/rbac.py",
)

try:
    from base.business_event_store import BusinessEventStore, WriterLease
    from base.projection_store import ProjectionStore
    from base.rbac import can_act
    from base.reviews_ledger import (
        LedgerConflict, LedgerNotFound, LedgerValidation)
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: cannot import base layer: %s" % exc)
    sys.exit(2)


def _batch(*, seq, aggregate_type, aggregate_id, command="grant_propose",
           state=None, prev=None):
    """Minimal valid batch; used only by the G0 isolation probe."""
    st = state or {"case_id": aggregate_id, "version": 1, "status": "proposed"}
    return {
        "schema_version": "business-command-batch/v1",
        "command_id": "cmd-%012d" % seq,
        "authority_seq": seq,
        "prev_manifest_sha256": prev,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "expected_version": 0,
        "result_version": int(st.get("version") or 1),
        "actor": {"principal_id": "u-probe", "tenant_id": "t1"},
        "command": command,
        "occurred_at": "2026-10-24T00:00:00Z",
        "idempotency_key": "probe-%d" % seq,
        "request_sha256": "a" * 64,
        "manifest_sha256": "b" * 64,
        "events": [{"type": "probe.%s" % command, "state": st}],
        "result": {},
    }


def probe_projection_isolation(tmp):
    """G0: grant_registry must stay out of review_cases.

    The criterion asks one thing only: after apply, is it in review_cases?
    It does not ask "did it raise" -- "rejected" and "accepted but written
    elsewhere" both count as isolated; "accepted into review_cases" does not.
    That keeps the criterion stable while the implementation may change.
    """
    proj = ProjectionStore(os.path.join(tmp, "g0.db"))
    try:
        before = [c.get("case_id") for c in proj.list_cases()]
        try:
            proj.apply_batch(_batch(seq=1, aggregate_type="grant_registry",
                                    aggregate_id="grants:on_probe"))
            applied = True
            err = ""
        except Exception as exc:  # noqa: BLE001
            applied = False
            err = "%s: %s" % (type(exc).__name__, exc)
        after = [c.get("case_id") for c in proj.list_cases()]
        leaked = "grants:on_probe" in after
        detail = "before=%r after=%r applied=%s err=%s" % (
            before, after, applied, err)
        return (not leaked), detail
    finally:
        proj.close()


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

    tmp = tempfile.mkdtemp(prefix="grant-registry-")
    try:
        isolated, detail = probe_projection_isolation(tmp)
        report(isolated,
               "G0 grant_registry aggregate stays out of review_cases", detail)
        if not isolated:
            print("", file=sys.stderr)
            print("G0 red is ACCURATE: projection_store.apply_batch() ignores "
                  "aggregate_type,", file=sys.stderr)
            print("so any aggregate lands in review_cases. Fix: "
                  "PMO/implement/T-314-*.md section 5 T-314a.", file=sys.stderr)
            print("Until then this file must NOT be added to verifier_map.",
                  file=sys.stderr)

        try:
            from base.review_reducer import reduce_command, initial_state  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            print("UNTESTED: reducer not importable: %s" % exc, file=sys.stderr)
            return 2

        src = open(os.path.join(ROOT, "base", "review_reducer.py"),
                   encoding="utf-8").read()
        if "grant_propose" not in src:
            print("", file=sys.stderr)
            print("UNTESTED: reducer has no grant_* command branch -> "
                  "G1-G9 have no object", file=sys.stderr)
            print("That is UNTESTED, not pass (0 pass / 1 red / 2 untested).",
                  file=sys.stderr)
            print("----------------------------------------", file=sys.stderr)
            print("%d passed, %d failed (G1-G9 untested)" % (passed, failed),
                  file=sys.stderr)
            return 1 if failed else 2

        # ── G1–G9：reducer 已落地，逐条断言 ─────────────────────────
        from base.review_reducer import reduce_command, initial_state

        AGG = "grants:on_t1"
        SCOPE = {"tenant": "on_t1", "product_lines": ["pump"]}

        def propose(actor="ou_dp4", **over):
            payload = {"capability": "takedown.execute", "user_id": "ou_exec",
                       "scope": dict(SCOPE), "reason": "需要下线"}
            payload.update(over)
            st = initial_state(AGG)
            st["tenant"] = "on_t1"
            return reduce_command(st, "grant_propose", actor, 0,
                                  {**payload, "case_id": AGG}, now=1000)

        def step(state, cmd, actor, version, **payload):
            return reduce_command(state, cmd, actor, version,
                                  {**payload, "case_id": AGG}, now=1100 + version)

        def denied(cmd, actor, state, version, **payload):
            try:
                step(state, cmd, actor, version, **payload)
                return None
            except (LedgerConflict, LedgerValidation, LedgerNotFound) as exc:
                return exc.code

        # G1 三态走通
        s1, _, r1 = propose()
        gid = r1["grant"]["grant_id"]
        s2, _, _ = step(s1, "grant_execute", "ou_it", 1, grant_id=gid)
        s3, _, _ = step(s2, "grant_approve", "ou_coord", 2, grant_id=gid)
        g = s3["grants"][0]
        report(g["state"] == "approved"
               and [h["action"] for h in g["history"]] == ["propose", "execute", "approve"],
               "G1 propose→execute→approve 三态走通",
               "%r %r" % (g["state"], [h["action"] for h in g["history"]]))

        # G2 三方不同人（三条各一）
        report(denied("grant_execute", "ou_dp4", s1, 1, grant_id=gid) == "same_actor",
               "G2a 提案人自己 execute → 拒")
        report(denied("grant_approve", "ou_it", s2, 2, grant_id=gid) == "same_actor",
               "G2b 执行人自己 approve → 拒")
        report(denied("grant_approve", "ou_dp4", s2, 2, grant_id=gid) == "same_actor",
               "G2c 提案人 approve → 拒")

        # G3 scope 分两层，各归各的：
        #   · reducer 只判**形状**（空品线集合不是通配 → 拒）；
        #   · 越出授予人自身 scope 由 validate_grant_actors() 判，在 approve 那一步。
        # ★ 第一版我把「跨租户/越品线」也写进 reducer 断言，结果两条 FAIL ——
        #   不是实现漏了，是我把判据放错了层。reducer 是纯函数，它拿不到
        #   「授予人自己有哪些品线」这个事实，硬判只能靠猜。
        code = None
        try:
            propose(scope={"tenant": "on_t1", "product_lines": []})
        except (LedgerConflict, LedgerValidation) as exc:
            code = exc.code
        report(code == "bad_grant",
               "G3a 空品线集合 → reducer 拒（空不是通配）", repr(code))

        from base.rbac import validate_grant_actors
        p_dp4 = {"id": "ou_dp4", "roles": ["dp4"], "tenant": "on_t1",
                 "product_lines": ["pump"]}
        p_it = {"id": "ou_it", "roles": ["it"], "tenant": "on_t1",
                "product_lines": ["pump"]}
        p_coord = {"id": "ou_coord", "roles": ["coordinator"], "tenant": "on_t1",
                   "product_lines": ["pump"]}
        report(validate_grant_actors(p_dp4, p_it, p_coord,
                                     granted_scope=dict(SCOPE)) is True,
               "G3b 三主体同 scope → validate_grant_actors 允许")
        report(validate_grant_actors(
                   p_dp4, p_it, p_coord,
                   granted_scope={"tenant": "on_t2", "product_lines": ["pump"]}) is False,
               "G3c 跨租户授予 → 拒")
        report(validate_grant_actors(
                   p_dp4, p_it, p_coord,
                   granted_scope={"tenant": "on_t1", "product_lines": ["bottle"]}) is False,
               "G3d 越品线授予 → 拒")

        # G4 重启恒等：重建 store 后仍是 approved
        proj2 = ProjectionStore(os.path.join(tmp, "g4.db"))
        try:
            proj2.apply_batch(_batch(
                seq=1, aggregate_type="grant_registry", aggregate_id=AGG,
                command="grant_approve",
                state={"case_id": AGG, "tenant": "on_t1", "version": 3,
                       "status": "approved", "grants": s3["grants"]}))
            proj2.close()
            proj2 = ProjectionStore(os.path.join(tmp, "g4.db"))
            rows = proj2.list_grant_registries()
            got = rows[0] if rows else {}
            report(got.get("status") == "approved",
                   "G4 重建后 grant_registry 仍是 approved", repr(got.get("status")))
        finally:
            proj2.close()

        # ── G4b/G4c（T-314b）：权威写 grant → 投影分流 → tenant 可读 ──
        #
        # ★ 这一段是本票抓出的真缺陷：`business_event_store` 与 `review_reducer`
        #   都把 aggregate_type **硬编码成 review_case**（共 3 处）。于是哪怕
        #   projection 侧已经能分流，权威写出来的批次仍然自称「案件」，
        #   名单聚合会落进 review_cases。T-314a 的 G0 只测了 projection 的
        #   apply_batch，测不到这一层 —— 判据盖住的那一跳才是不出事的跳。
        from base.business_event_store import BusinessEventStore, WriterLease
        from base.projector import Projector
        from base.review_reducer import aggregate_type_for

        report(aggregate_type_for("grants:on_t1") == "grant_registry"
               and aggregate_type_for("case-abc") == "review_case",
               "G4b aggregate_type_for 是唯一判定（两个方向各一次）")

        auth_root = os.path.join(tmp, "auth_g4b")
        auth = BusinessEventStore(auth_root,
                                  lease=WriterLease(
                                      os.path.join(auth_root, "l")).acquire())
        proj_g = ProjectionStore(os.path.join(tmp, "g4b.db"))
        # ★ 整段包 try/except 而不是 try/finally：第一版是 try/finally，
        #   实测把 tenant 改回 state.get("tenant") 后 apply_batch 抛
        #   grant_aggregate_id，异常把 G4c–G4g 全部跳过 —— **一条都没有变成红项**，
        #   而读数看起来像 23/23。这正是 #136 的形状：一条判据如果只可能绿或
        #   「没跑到」，它就不是判据。现在异常被收成一条红项，后面照样跑完。
        try:
            for kid, cmd, ver, extra in (
                    ("k1", "grant_propose", 0, {
                        "capability": "takedown.execute", "user_id": "ou_exec",
                        "scope": dict(SCOPE), "reason": "需要下线"}),
                    ("k2", "grant_execute", 1, {"grant_id": gid}),
                    ("k3", "grant_approve", 2, {"grant_id": gid})):
                auth.execute(aggregate_id=AGG, command=cmd,
                             actor={"principal_id": {"k1": "ou_dp4", "k2": "ou_it",
                                                     "k3": "ou_coord"}[kid],
                                    "tenant_id": "on_t1"},
                             expected_version=ver,
                             payload={**extra, "case_id": AGG},
                             idempotency_key=kid, now=2000 + ver)
            Projector(auth, proj_g).catch_up()
            batch_type = auth.batches()[0]["aggregate_type"]
            report(batch_type == "grant_registry",
                   "G4c 权威批次自称 grant_registry（不再硬编码 review_case）",
                   repr(batch_type))
            report(proj_g.status(auth.head())["status"] == "fresh",
                   "G4d 三段写入后投影 fresh（分流没把链弄断）")
            report([c.get("case_id") for c in proj_g.list_cases()] == [],
                   "G4e 权威→投影全链路：review_cases 无名单聚合",
                   repr([c.get("case_id") for c in proj_g.list_cases()]))
            rows = proj_g.list_grant_registries()
            report(len(rows) == 1 and rows[0].get("tenant") == "on_t1",
                   "G4f tenant 从 aggregate_id 取出并可读（不是 NULL）",
                   repr([r.get("tenant") for r in rows]))
            report(rows and rows[0].get("grants", [{}])[0].get("state") == "approved",
                   "G4g 投影里三条命令的结果是 approved",
                   repr(rows[0].get("grants", [{}])[0].get("state") if rows else None))
        except AssertionError as exc:
            raise
        except Exception as exc:  # noqa: BLE001
            # 链路抛错本身就是一个红项，不是「未测」。
            report(False, "G4c–G4g 权威→投影链路未抛错",
                   "%s: %s" % (type(exc).__name__, exc))
        finally:
            proj_g.close()

        # G5 名单真生效（can_act 翻转）+ G6 反向（空源必须 False）
        import base.rbac as RBAC
        p_exec = {"id": "ou_exec", "roles": ["signer"], "tenant": "on_t1",
                  "product_lines": ["pump"]}
        case = {"tenant": "on_t1", "product_line": "pump", "submitter_id": "x",
                "final_reviewer_id": "y", "assignee_id": None, "actionable": True}
        saved_source = getattr(RBAC, "_ALLOWLIST_SOURCE", None)
        try:
            RBAC.set_allowlist_source(lambda: {"takedown.execute": frozenset({"ou_exec"}),
                                               "takedown.waive": frozenset()})
            report(can_act(p_exec, "takedown.execute", case) is True,
                   "G5a 名单含该人 → can_act True")
            RBAC.set_allowlist_source(lambda: {"takedown.execute": frozenset(),
                                               "takedown.waive": frozenset()})
            report(can_act(p_exec, "takedown.execute", case) is False,
                   "G6 注入空源 → can_act False（证明它读的是注入源）")
        finally:
            if saved_source is None:
                RBAC._ALLOWLIST_SOURCE = None
            else:
                RBAC.set_allowlist_source(saved_source)

        # G7 留痕四元
        report(all(k in g["history"][-1] for k in ("actor", "at", "from", "to", "note"))
               and g["history"][-1]["actor"] == "ou_coord",
               "G7 每条 history 四元齐全且 actor 是审批人")
        report(g["reason"] == "需要下线",
               "G7b reason 不被后续命令改写（依据是依据）", repr(g.get("reason")))

        # G8 跨重启不撞号
        s_other, _, r_other = propose(user_id="ou_other")
        report(r_other["grant"]["grant_id"] != gid,
               "G8 不同 user 产生不同 grant_id")
        # 同一 state 内两条同参数 → seq 递增 → id 不同
        s_two, _, r_two = step(s1, "grant_propose", "ou_dp4", 1,
                               capability="takedown.waive", user_id="ou_exec",
                               scope=dict(SCOPE), reason="第二份")
        report(r_two["grant"]["grant_id"] not in (gid, r_other["grant"]["grant_id"]),
               "G8b 同 state 内第二条 grant_id 唯一")

        # G9 validate_grant_actors 在 approve 那一步被调用（接缝不悬空）
        # G9 三权分立的两层都要在：reducer 的逐步判定 + rbac 的综合判定。
        # 这里断言「reducer 不复制角色/能力矩阵」—— 那是 rbac 的唯一职责，
        # 两份矩阵必然漂移（AGENTS.md 2.4.8）。
        src_reducer = open(os.path.join(ROOT, "base", "review_reducer.py"),
                           encoding="utf-8").read()
        report("_ROLE_CAPS" not in src_reducer and "role_capabilities" not in src_reducer,
               "G9 reducer 不复制角色矩阵（能力判定只在 rbac 一处）")
        # ---- G5–G8：HTTP 三权分立全链路 ----
        try:
            from fastapi.testclient import TestClient
            from api.review_api import create_app
            import base.auth_session as _AS

            PEOPLE = {
                "ou_dp4": {"id": "ou_dp4", "roles": ["dp4"], "tenant": "on_t1",
                           "product_lines": ["pump"], "open_id": "ou_1",
                           "tenant_id": "on_t1"},
                "ou_it": {"id": "ou_it", "roles": ["it"], "tenant": "on_t1",
                          "product_lines": ["pump"], "open_id": "ou_2",
                          "tenant_id": "on_t1"},
                "ou_coord": {"id": "ou_coord", "roles": ["coordinator"],
                             "tenant": "on_t1", "product_lines": ["pump"],
                             "open_id": "ou_3", "tenant_id": "on_t1"},
            }
            import tempfile as _tmpmod
            from base.review_command_service import ReviewCommandService
            from base.projector import Projector as _Proj
            dh = _tmpmod.mkdtemp(prefix="grant-http-")
            lease_h = WriterLease(os.path.join(dh, "a", "lock")).acquire()
            auth_h = BusinessEventStore(os.path.join(dh, "a"), lease=lease_h)
            proj_h = ProjectionStore(os.path.join(dh, "p.db"))
            svc_h = ReviewCommandService(auth_h, proj_h)
            _Proj(auth_h, proj_h).catch_up()
            store_h = _AS.SessionStore(":memory:")
            sids = {p: store_h.create_session(p, tenant="on_t1", provider="dev",
                                              issuer="x", csrf_token="c1")
                    for p in PEOPLE}
            paths = {"/api/v1/admin/signer-grants",
                     "/api/v1/admin/takedown-grants",
                     "/api/v1/admin/grants/{id}/execute",
                     "/api/v1/admin/grants/{id}/approve"}
            ap_h = create_app(session_store=store_h, review_command_service=svc_h,
                              enabled_write_capabilities=paths, principals=PEOPLE,
                              grant_principal_provider=lambda pid, t: PEOPLE.get(pid))
            ap_h.state.app_env = "dev"
            ap_h.state.repository.cases = []

            def cl(p):
                return TestClient(ap_h, cookies={"session": sids[p]})

            # ★ G15a 必须在**提案之前**跑：提案之后列表就不空了。
            #   第一版放在 G17 那一段里，那里已有 1 条 → 断言恒假。
            _empty = cl("ou_coord").get("/api/v1/admin/takedown-grants")
            report(_empty.status_code == 200 and _empty.json() == [],
                   "G15a 空名单 GET 返回 []（不是 404、不是 {}）",
                   "%s %r" % (_empty.status_code, _empty.json()))

            r_p = cl("ou_dp4").post(
                "/api/v1/admin/takedown-grants",
                json={"user_id": "ou_exec", "capability": "takedown.execute",
                      "product_line": "pump", "platform": "amazon_us",
                      "reason": "需要下线"},
                headers={"Idempotency-Key": "g1"})
            gid_h = (r_p.json() or {}).get("grant_id")
            report(r_p.status_code == 200 and isinstance(gid_h, str)
                   and (r_p.json() or {}).get("state") == "proposed",
                   "G10 HTTP dp4 提案 → proposed（顶层带 grant_id）",
                   "%s %r" % (r_p.status_code, gid_h))

            r_d = cl("ou_dp4").post(f"/api/v1/admin/grants/{gid_h}/execute",
                                    json={}, headers={"Idempotency-Key": "g2"})
            report(r_d.status_code == 403
                   and "same_actor" in (r_d.json().get("message") or ""),
                   "G11 提案人自己 execute → 403 same_actor（reducer 那层）",
                   str(r_d.status_code))

            r_e = cl("ou_it").post(f"/api/v1/admin/grants/{gid_h}/execute",
                                   json={"note": "已执行"},
                                   headers={"Idempotency-Key": "g3"})
            report(r_e.status_code == 200
                   and (r_e.json() or {}).get("state") == "executed",
                   "G11b it execute → executed", str(r_e.status_code))

            r_x = cl("ou_it").post(f"/api/v1/admin/grants/{gid_h}/approve",
                                   json={}, headers={"Idempotency-Key": "g4"})
            # ★ 这一条是本票最重要的一条：它证明 validate_grant_actors 真的被调用了。
            #   执行人自己做审批时，rbac 那层必须拒（"grant_actors_invalid"）；
            #   而 reducer 那层也会拒（same_actor）。两者任一先拦住都算对，
            #   但**必须拦**。第一版接线写错时（hasattr 恒 False），这里会 200。
            report(r_x.status_code == 403,
                   "G12 执行人自己 approve → 403（reducer 的 same_actor）",
                   "%s %r" % (r_x.status_code, (r_x.json().get("message") or "")[:40]))

            # ★★ G12c：**只有 rbac 能拦**的场景。
            #
            # G12 是假判据：删掉 validate_grant_actors 后 reducer 的 same_actor
            # 仍然拦住「执行人自批」，所以它照样绿（变异 M1 实测 survived）。
            # 要证明 rbac 那层真的在跑，必须构造一个 **三个人都不同、
            # reducer 全放行、但其中一人 scope 不够** 的样本。
            # 这里让审批人的 product_lines 不含本案品线。
            PEOPLE_NARROW = dict(PEOPLE)
            PEOPLE_NARROW["ou_coord"] = dict(PEOPLE["ou_coord"],
                                             product_lines=["other"])
            ap_n = create_app(session_store=store_h, review_command_service=svc_h,
                              enabled_write_capabilities=paths,
                              principals=PEOPLE_NARROW,
                              grant_principal_provider=(
                                  lambda pid, t: PEOPLE_NARROW.get(pid)))
            ap_n.state.app_env = "dev"
            ap_n.state.repository.cases = []
            c_n = TestClient(ap_n, cookies={"session": sids["ou_coord"]})
            r_n = c_n.post(f"/api/v1/admin/grants/{gid_h}/approve",
                           json={"note": "scope 不够"},
                           headers={"Idempotency-Key": "g4c"})
            report(r_n.status_code == 403
                   and "grant_actors_invalid" in (r_n.json().get("message") or ""),
                   "G12c 审批人 scope 不覆盖本案 → 403（只有 rbac 能拦这一条）",
                   "%s %r" % (r_n.status_code,
                              (r_n.json().get("message") or "")[:40]))

            r_a = cl("ou_coord").post(f"/api/v1/admin/grants/{gid_h}/approve",
                                      json={"note": "批准"},
                                      headers={"Idempotency-Key": "g5"})
            report(r_a.status_code == 200
                   and (r_a.json() or {}).get("state") == "approved",
                   "G12b coord approve → approved", str(r_a.status_code))

            g_st = (auth_h.state("grants:on_t1").get("grants") or [{}])[0]
            report([h["action"] for h in g_st.get("history") or []]
                   == ["propose", "execute", "approve"],
                   "G13 authority 里三态留痕齐全",
                   repr([h["action"] for h in g_st.get("history") or []]))

            # G9 dp4 进不了会话审计 —— 证明 grant_dep 没有放宽错东西
            report(cl("ou_dp4").get("/api/v1/admin/sessions").status_code == 403,
                   "G14 dp4 仍读不到 /admin/sessions（grant_dep 未放宽无关能力）")
            # ---- G15–G17：GET 读 authority + 名单源注入生效 ----
            #
            # ★ 改前这两个 GET 读 frozen JSON，而那两份文件盘上不存在
            #   （`find` 0 个）→ 永远返回 []。写侧走 authority，
            #   于是「提案成功、刷新后看不到」—— 两个真相源。
            rows_after = cl("ou_coord").get("/api/v1/admin/takedown-grants").json()
            report(len(rows_after) == 1
                   and rows_after[0]["state"] == "approved"
                   and rows_after[0]["product_line"] == "pump"
                   and rows_after[0]["platform"] == "amazon_us",
                   "G15 GET 读 authority（提案即时可见，字段与前端 GrantRecord 对齐）",
                   repr(rows_after[0] if rows_after else None)[:120])

            # 两类授权不许串台
            report(cl("ou_coord").get("/api/v1/admin/signer-grants").json() == [],
                   "G16 takedown 类授权不出现在 signer 类列表里（能力分本）")

            # G17 名单源注入 → can_act 翻转
            import base.rbac as _rbac
            saved_src = getattr(_rbac, "_ALLOWLIST_SOURCE", None)
            try:
                _rbac.set_allowlist_source(lambda: {
                    cap: frozenset(
                        g["user_id"]
                        for g in (auth_h.state("grants:on_t1").get("grants") or [])
                        if g.get("state") == "approved"
                        and g.get("capability") == cap)
                    for cap in ("takedown.execute", "takedown.waive")})
                case_g = {"tenant": "on_t1", "product_line": "pump",
                          "submitter_id": "x", "final_reviewer_id": "y",
                          "assignee_id": None, "actionable": True}
                p_exec_g = {"id": "ou_exec", "roles": ["signer"],
                            "tenant": "on_t1", "product_lines": ["pump"]}
                report(_rbac.can_act(p_exec_g, "takedown.execute", case_g) is True,
                       "G17 注入源读到已批准名单 → can_act True")
                _rbac.set_allowlist_source(lambda: {
                    "takedown.execute": frozenset(), "takedown.waive": frozenset()})
                report(_rbac.can_act(p_exec_g, "takedown.execute", case_g) is False,
                       "G17b 注入空源 → can_act False（读的是注入源不是常量）")
            finally:
                _rbac.set_allowlist_source(saved_src)

            lease_h.release()
            proj_h.close()
        except Exception as exc:  # noqa: BLE001
            report(False, "G5–G9 HTTP 三权分立链路",
                   "%s: %s" % (type(exc).__name__, exc))

        # ---- G18–G20：ProductionRuntime 注入链路（真机，非 mock）----
        #
        # ★ 前面 G17 用的是手工注入的 lambda；这一段用**真实 ProductionRuntime**
        #   的 allowlist_source()，证明装配真的接上了、且只认 approved。
        try:
            import json as _json
            from base import rbac as _rbac2
            from api.production_app import ProductionSettings, ProductionRuntime

            dp = tempfile.mkdtemp(prefix="grant-runtime-")
            os.chmod(dp, 0o700)
            pp = {n: os.path.join(dp, n) for n in
                  ("authority", "frozen", "projection.db", "session.db",
                   "access.log", "principals.json", "reports")}
            for n in ("authority", "frozen"):
                os.makedirs(pp[n])
                os.chmod(pp[n], 0o700)
            with open(pp["principals.json"], "w", encoding="utf-8") as f:
                _json.dump({"principals": [
                    {"id": "ou_dp4", "tenant_id": "t1", "open_id": "o1",
                     "roles": ["dp4"], "product_lines": ["pump"],
                     "status": "active", "authz_version": "1"},
                    {"id": "ou_it", "tenant_id": "t1", "open_id": "o2",
                     "roles": ["it"], "product_lines": ["pump"],
                     "status": "active", "authz_version": "1"},
                    {"id": "ou_coord", "tenant_id": "t1", "open_id": "o3",
                     "roles": ["coordinator"], "product_lines": ["pump"],
                     "status": "active", "authz_version": "1"},
                ]}, f)
            from pathlib import Path as _P
            settings = ProductionSettings(
                authority_root=_P(pp["authority"]),
                frozen_projection_root=_P(pp["frozen"]),
                review_projection_db=_P(pp["projection.db"]),
                session_db=_P(pp["session.db"]),
                access_log_path=_P(pp["access.log"]),
                principal_directory=_P(pp["principals.json"]),
                # T-316d：报告落盘根。与其它数据路径一样必须在仓外。
                report_root=_P(pp["reports"]),
                public_origin="https://audit.example.com",
                oauth_client_id="cli_x", oauth_client_secret="s",
                oauth_redirect_uri="https://audit.example.com/auth/callback",
                tenant_allowlist=frozenset({"t1"}))
            CASE_R = {"tenant": "t1", "product_line": "pump", "submitter_id": "x",
                      "final_reviewer_id": "y", "assignee_id": None,
                      "actionable": True}
            P_R = {"id": "ou_exec2", "roles": ["signer"], "tenant": "t1",
                   "product_lines": ["pump"]}
            rt = ProductionRuntime(settings)
            try:
                rt.start()
                report(_rbac2._ALLOWLIST_SOURCE is not None,
                       "G18 ProductionRuntime.start 注入了名单源")
                report(_rbac2.can_act(P_R, "takedown.execute", CASE_R) is False,
                       "G18b 空名单 → can_act False（fail closed）")

                def _ex2(cmd, actor, payload, key, now):
                    return rt.service.execute(
                        aggregate_id="grants:t1", command=cmd,
                        actor={"principal_id": actor, "tenant_id": "t1"},
                        expected_version=None, payload=payload,
                        idempotency_key=key, now=now)

                _ex2("grant_propose", "ou_dp4",
                     {"capability": "takedown.execute", "user_id": "ou_exec2",
                      "scope": {"tenant": "t1", "product_lines": ["pump"]},
                      "reason": "r"}, "p1", 1000)
                gid_r = rt.authority.state("grants:t1")["grants"][0]["grant_id"]
                _ex2("grant_execute", "ou_it", {"grant_id": gid_r}, "p2", 1100)
                # ★ 这一条最重要：executed 但未 approved 时**不许生效**。
                #   差这一步，一张提案就能开下线权。
                report(_rbac2.can_act(P_R, "takedown.execute", CASE_R) is False,
                       "G19 executed 未 approved → can_act 仍 False（三权未走完）")
                _ex2("grant_approve", "ou_coord", {"grant_id": gid_r}, "p3", 1200)
                report(_rbac2.can_act(P_R, "takedown.execute", CASE_R) is True,
                       "G19b approved 后 → can_act True")
                report(_rbac2.can_act(P_R, "takedown.waive", CASE_R) is False,
                       "G20 另一能力不随本次授权放开（execute ≠ waive）")
            finally:
                rt.stop()
                _rbac2.set_allowlist_source(None)
        except Exception as exc:  # noqa: BLE001
            report(False, "G18–G20 ProductionRuntime 注入链路",
                   "%s: %s" % (type(exc).__name__, exc))


        print("----------------------------------------")
        if failed == 0:
            print("✅ %d/%d passed" % (passed, passed + failed))
            return 0
        print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: verifier crashed: %s" % exc)
        sys.exit(2)
