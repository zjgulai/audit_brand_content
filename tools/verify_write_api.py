#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_write_api.py — T2-02：review-api 写端点

覆盖：
  C0  claim/unclaim/reassign：接 reviews_ledger；409 冲突；403 越权；Idempotency-Key
  C1  actions：confirm/reject 走 finding_store 新建条目 + derived_from；版本冲突 409
  C2  appeals：open/pause/migrate/withdraw/stale；非原申诉人 migrate → 403
  C3  takedown：start/complete/fail/retry/reassign/waive 接 base/takedown，回填校验
  C4  release-decision/revoke → 501「release_gate 未实现」，不得假成功
  C5  静态扫描：API 层不 import 判定实现、不计算 state
  R1  Idempotency-Key 重复请求不得产生第二条
  R2  越权 → 403
  R3  appeal 非原申诉人 migrate → 403
  R4  release 占位返回 200 → 红

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import asyncio
import json
import os
import re
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from api.review_api import create_app, InMemoryRepository
    from api.write_api import AppealStore
    from base.auth_session import SessionStore
    from base.finding_store import FindingStore
    from base.reviews_ledger import ReviewsLedger
    from base import takedown as TD
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入写 API 依赖: %s" % exc)
    sys.exit(2)


def call(app, method, path, cookie=None, key=None, body=None):
    headers = [(b"host", b"testserver")]
    if cookie:
        headers.append((b"cookie", ("session=" + cookie).encode()))
    if key is not None:
        headers.append((b"idempotency-key", key.encode()))
    raw = b""
    if body is not None:
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers.append((b"content-type", b"application/json"))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": b"", "headers": headers,
        "client": ("test", 1234), "server": ("testserver", 80),
        "root_path": "",
    }
    messages = []

    async def receive():
        return {"type": "http.request", "body": raw, "more_body": False}

    async def send(message):
        messages.append(message)

    asyncio.run(app(scope, receive, send))
    start = next(m for m in messages if m["type"] == "http.response.start")
    payload = b"".join(m.get("body", b"") for m in messages
                       if m["type"] == "http.response.body")
    parsed = json.loads(payload.decode("utf-8")) if payload else None
    return start["status"], parsed


def ir(ir_id="ir-1", state="BLOCK"):
    return {
        "ir_id": ir_id, "ir_version": "review-ir-v1",
        "source_ir_version": "cu-1",
        "content_unit_ref": {"unit_id": "cu-1", "kind": "image"},
        "findings": [],
        "decision": {"state": state, "layer": "DP2",
                     "release_status": "待放行", "obligations": []},
        "coverage": {"coverage_state": "partial",
                     "modalities_evaluated": ["image"],
                     "rules_version": "rules-v1",
                     "control_points_applied": ["H01"]},
        "receipt_ref": "rc-1", "rule_snapshot": "rs-1",
        "kb_snapshot": "kb-1", "control_points_version": "cp-v1",
        "created_at": "2026-10-19T00:00:00Z",
    }


def release_case(case_id):
    h = "a" * 64
    return {
        "case_id": case_id, "tenant": "t1", "product_line": "pump",
        "submitter_id": "u_sub", "final_reviewer_id": "u_dp3",
        "assignee_id": "u_dp3", "actionable": True,
        "ir": ir(case_id + "-ir"),
        "case_version": 1,
        "ir_id": case_id + "-ir", "ir_version": "review-ir-v1",
        "raw_sha256": h, "text_sha256": h,
        "conflict_table_version": "ct-v1",
        "frame_manifest_hash": h, "keyframe_set_hash": h,
        "ocr_output_hash": h, "asr_output_hash": h,
        "model_config_hash": h, "sampling_config_hash": h,
        "rule_snapshot": {"version": "rules-v1", "hash": h},
        "kb_snapshot": {"version": "kb-v1", "hash": h},
        "used_authority_refs": [], "media_fingerprints": [],
    }


def candidate(fid):
    return {
        "finding_id": fid, "control_code": "H01", "detected_by": "P1",
        "authority_ref": [], "authority_state": "ok", "severity": "L4",
        "status": "candidate", "location": {"bbox": {"x1": 0.1, "y1": 0.2,
                                                       "x2": 0.4, "y2": 0.6}},
        "quote": "原文", "produced_by": "semantic", "derived_from": None,
        "confirmed_by_rule_class": True,
    }


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

    cases = [
        {"case_id": "case-1", "tenant": "t1", "product_line": "pump",
         "submitter_id": "u_sub", "final_reviewer_id": "u_dp3",
         "assignee_id": "u_dp3", "actionable": True, "ir": ir("ir-1")},
        {"case_id": "case-2", "tenant": "t1", "product_line": "pump",
         "submitter_id": "u_other", "final_reviewer_id": "u_dp3",
         "assignee_id": "u_dp3", "actionable": True, "ir": ir("ir-2")},
        {"case_id": "case-3", "tenant": "t1", "product_line": "pump",
         "submitter_id": "u_other", "final_reviewer_id": "u_dp3",
         "assignee_id": "u_dp3", "actionable": True, "ir": ir("ir-3")},
        release_case("case-release"),
        release_case("case-release2"),
    ]
    tasks = [
        TD.new_task(task_id="t-1", case_id="case-1", platform="amazon",
                    tenant="t1", product_line="pump",
                    created_at="2026-10-19T00:00:00Z", assignee="u_dp3"),
        TD.new_task(task_id="t-2", case_id="case-1", platform="tiktok",
                    tenant="t1", product_line="pump",
                    created_at="2026-10-19T00:00:00Z", assignee="u_dp3"),
        TD.new_task(task_id="t-3", case_id="case-1", platform="meta",
                    tenant="t1", product_line="pump",
                    created_at="2026-10-19T00:00:00Z", assignee="u_dp3"),
        TD.new_task(task_id="t-4", case_id="case-1", platform="amazon",
                    tenant="t1", product_line="pump",
                    created_at="2026-10-19T00:00:00Z", assignee="u_dp3"),
    ]
    repo = InMemoryRepository(cases=cases, reports=[], takedown_tasks=tasks)
    principals = {
        "u_sub": {"open_id": "ou_u_sub", "tenant_id": "t1",
                  "roles": ["submitter"], "product_lines": ["pump"],
                  "product_line": "pump", "capabilities": ["release.sign"]},
        "u_dp3": {"open_id": "ou_u_dp3", "tenant_id": "t1",
                  "roles": ["coordinator"], "product_lines": ["pump"],
                  "product_line": "pump"},
        "u_it": {"open_id": "ou_u_it", "tenant_id": "t1",
                 "roles": ["it"], "product_lines": ["pump"],
                 "product_line": "pump"},
        "u_signer": {"open_id": "ou_u_signer", "tenant_id": "t1",
                     "roles": ["signer"], "product_lines": ["pump"],
                     "product_line": "pump",
                     "capabilities": ["release.sign", "release.revoke"]},
    }
    store = SessionStore(":memory:")
    sub = store.create_session("u_sub", tenant="t1", now=time.time())
    coord = store.create_session("u_dp3", tenant="t1", now=time.time())
    signer = store.create_session("u_signer", tenant="t1", now=time.time())
    fs = FindingStore()
    for fid in ("f-1", "f-2", "f-3"):
        fs.insert(candidate(fid))
    ledger = ReviewsLedger()
    appeals = AppealStore()
    app = create_app(session_store=store, repository=repo,
                     principals=principals, reviews_ledger=ledger,
                     finding_store=fs, appeals=appeals)

    # C0 claim / idempotency / unclaim / reassign
    st, claim = call(app, "POST", "/api/v1/cases/case-1/claim", coord,
                     "K-claim-1", {})
    report(st == 200 and claim["version"] == 1,
           "C0 claim 成功", "%s %r" % (st, claim))
    st2, claim2 = call(app, "POST", "/api/v1/cases/case-1/claim", coord,
                       "K-claim-1", {})
    claim_events = [e for e in ledger.events() if e["kind"] == "claim"
                    and e["case_id"] == "case-1"]
    report(st2 == 200 and claim2["version"] == claim["version"]
           and len(claim_events) == 1,
           "R1 同 Idempotency-Key 重复 claim 不产生第二条",
           "%s %r events=%d" % (st2, claim2, len(claim_events)))
    st, _ = call(app, "POST", "/api/v1/cases/case-1/claim", coord,
                 "K-claim-other", {})
    report(st == 409, "C0 不同 key 重复 claim → 409", str(st))
    st, _ = call(app, "POST", "/api/v1/cases/case-3/claim", coord, None, {})
    report(st == 400, "C0 缺 Idempotency-Key → 400", str(st))
    st, _ = call(app, "POST", "/api/v1/cases/case-3/claim", sub,
                 "K-claim-sub", {})
    report(st == 403, "R2 提交人 claim → 403", str(st))

    st, un = call(app, "POST", "/api/v1/cases/case-1/unclaim", coord,
                  "K-unclaim-1", {"version": claim["version"]})
    report(st == 200 and un["status"] == "released"
           and ledger.list_drafts("case-1"),
           "C0 unclaim → released 且 draft 已保存",
           "%s %r" % (st, un))
    st, claim3 = call(app, "POST", "/api/v1/cases/case-1/claim", coord,
                      "K-claim-2", {})
    st, reassigned = call(app, "POST", "/api/v1/cases/case-1/reassign", coord,
                          "K-reassign-1", {"version": claim3["version"],
                                           "assignee": "u_dp3b"})
    report(st == 200 and reassigned["assignee"] == "u_dp3b",
           "C0 reassign 成功", "%s %r" % (st, reassigned))

    # C1 actions：confirm 新建条目 + derived_from；版本冲突
    st, claim2 = call(app, "POST", "/api/v1/cases/case-2/claim", coord,
                      "K-claim-case2", {})
    st, act = call(app, "POST", "/api/v1/cases/case-2/actions", coord,
                   "K-action-confirm",
                   {"version": claim2["version"], "finding_id": "f-1",
                    "action": "confirm"})
    old = fs.get("f-1")
    report(st == 200 and act["finding"]["status"] == "confirmed"
           and act["finding"]["derived_from"] == "f-1"
           and act["finding"]["finding_id"] != "f-1"
           and old["status"] == "superseded",
           "C1 confirm：新条目 + derived_from，旧条 superseded",
           "%s %r old=%r" % (st, act, old))
    st, _ = call(app, "POST", "/api/v1/cases/case-2/actions", coord,
                 "K-action-stale",
                 {"version": 999, "finding_id": "f-2", "action": "confirm"})
    report(st == 409, "C1 版本冲突 → 409", str(st))
    st, rej = call(app, "POST", "/api/v1/cases/case-2/actions", coord,
                   "K-action-reject",
                   {"version": claim2["version"], "finding_id": "f-3",
                    "action": "reject"})
    report(st == 200 and rej["finding"]["status"] == "rejected"
           and rej["finding"]["derived_from"] == "f-3",
           "C1 reject：新条目 + derived_from", "%s %r" % (st, rej))

    # C2 appeals：pause / migrate / 非原申诉人 / stale / withdraw
    st, ap = call(app, "POST", "/api/v1/appeals", sub, "K-appeal-1",
                  {"case_id": "case-1", "reason": "误判"})
    report(st == 200 and ap["state"] == "open", "C2 申诉 open", "%s %r" % (st, ap))
    st, _ = call(app, "POST", "/api/v1/appeals/%s/migrate" % ap["appeal_id"],
                 coord, "K-mig-wrong", {})
    report(st == 403, "R3 非原申诉人 migrate → 403", str(st))
    appeals.pause("case-1", now=time.time())
    st, migrated = call(app, "POST",
                        "/api/v1/appeals/%s/migrate" % ap["appeal_id"],
                        sub, "K-mig-ok", {})
    report(st == 200 and migrated["state"] == "migrated",
           "C2 原申诉人 migrate → migrated", "%s %r" % (st, migrated))

    st, ap2 = call(app, "POST", "/api/v1/appeals", sub, "K-appeal-2",
                   {"case_id": "case-1", "reason": "再申诉"})
    appeals.pause("case-1", now=time.time())
    stale = appeals.mark_stale(now=time.time() + 31 * 86400)
    report(any(x["appeal_id"] == ap2["appeal_id"] and x["state"] == "stale"
               for x in stale),
           "C2 paused 超 30 天 → stale（不关闭）", repr(stale))

    st, ap3 = call(app, "POST", "/api/v1/appeals", sub, "K-appeal-3",
                   {"case_id": "case-1", "reason": "待撤"})
    st, _ = call(app, "POST", "/api/v1/appeals/%s/withdraw" % ap3["appeal_id"],
                 sub, "K-wd-bad", {})
    report(st == 400, "C2 withdraw 缺 reason → 400", str(st))
    st, wd = call(app, "POST", "/api/v1/appeals/%s/withdraw" % ap3["appeal_id"],
                  sub, "K-wd-ok", {"reason": "不需要了"})
    report(st == 200 and wd["state"] == "withdrawn",
           "C2 withdraw → withdrawn", "%s %r" % (st, wd))

    # C3 takedown
    st, t1 = call(app, "POST", "/api/v1/takedown-tasks/t-1/start", coord,
                  "K-td-start-1", {})
    report(st == 200 and t1["state"] == "in_progress",
           "C3 takedown start", "%s %r" % (st, t1))
    st, t1c = call(app, "POST", "/api/v1/takedown-tasks/t-1/complete", coord,
                   "K-td-complete-1",
                   {"evidence": {"platform": "amazon", "executed_by": "u_dp3",
                                 "executed_at": "2026-10-19T00:00:00Z",
                                 "receipt_id": "R-1"}})
    report(st == 200 and t1c["state"] == "completed" and t1c.get("evidence"),
           "C3 takedown complete 回填校验通过", "%s %r" % (st, t1c))
    st, _ = call(app, "POST", "/api/v1/takedown-tasks/t-4/start", coord,
                 "K-td-start-4", {})
    st, _ = call(app, "POST", "/api/v1/takedown-tasks/t-4/complete", coord,
                 "K-td-empty", {"evidence": {}})
    report(st == 400, "C3 无证据 complete → 400", str(st))
    call(app, "POST", "/api/v1/takedown-tasks/t-2/start", coord,
         "K-td-start-2", {})
    st, failed_task = call(app, "POST", "/api/v1/takedown-tasks/t-2/fail", coord,
                           "K-td-fail-2", {})
    st, retried = call(app, "POST", "/api/v1/takedown-tasks/t-2/retry", coord,
                       "K-td-retry-2", {})
    st, re2 = call(app, "POST", "/api/v1/takedown-tasks/t-2/reassign", coord,
                   "K-td-reassign-2", {"assignee": "u_dp3b"})
    report(failed_task["state"] == "failed" and retried["state"] == "pending"
           and re2["assignee"] == "u_dp3b",
           "C3 fail → retry → reassign",
           repr((failed_task, retried, re2)))
    call(app, "POST", "/api/v1/takedown-tasks/t-3/start", coord,
         "K-td-start-3", {})
    call(app, "POST", "/api/v1/takedown-tasks/t-3/fail", coord,
         "K-td-fail-3", {})
    st, waived = call(
        app, "POST", "/api/v1/takedown-tasks/t-3/waive", coord, "K-td-waive-3",
        {"approvers": [
            {"actor": "u_a", "scopes": ["takedown.waive"], "scope_match": True},
            {"actor": "u_b", "scopes": ["takedown.waive"], "scope_match": True}],
         "reason": "已协商", "evidence": {"note": "ok"}})
    report(st == 200 and waived.get("waived", {}).get("approvers")
           == ["u_a", "u_b"],
           "C3 waive 双人审批通过", "%s %r" % (st, waived))

    # C4 release-decision / revoke：真实 ReleaseGate + step-up + SoD + 版本
    st, _ = call(app, "POST", "/api/v1/cases/case-release/release-decision",
                 signer, "K-rel-nostep",
                 {"decision": "sign", "version": 1, "reason": "缺 step-up"})
    report(st == 403, "C4 缺 step-up → 403", str(st))
    st, _ = call(app, "POST", "/api/v1/cases/case-release/release-decision",
                 sub, "K-rel-self",
                 {"decision": "sign", "version": 1, "reason": "自签"})
    report(st == 403, "C4 自签 → 403", str(st))
    st, _ = call(app, "POST", "/api/v1/cases/case-release/release-decision",
                 signer, "K-rel-version",
                 {"decision": "sign", "version": 999, "reason": "旧版本"})
    report(st == 409, "C4 版本冲突 → 409", str(st))

    token = store.issue_step_up("u_signer", "case-release", "sign",
                                "n-sign", now=time.time())
    st, signed = call(app, "POST",
                      "/api/v1/cases/case-release/release-decision", signer,
                      "K-rel-sign",
                      {"decision": "sign", "version": 1, "reason": "签发",
                       "step_up_token": token, "nonce": "n-sign"})
    sig = (signed or {}).get("signature") or {}
    report(st == 200 and len(sig.get("signature_hash", "")) == 64
           and (signed or {}).get("release", {}).get("status") == "signed"
           and (signed or {}).get("release", {}).get("release_status") == "已放行",
           "C4/R4 sign 真实成功（签名 + signed/已放行；占位 200 不成立）",
           "%s %r" % (st, signed))

    token = store.issue_step_up("u_signer", "case-release", "revoke",
                                "n-revoke", now=time.time())
    st, revoked = call(app, "POST",
                       "/api/v1/cases/case-release/release-revoke", signer,
                       "K-rel-revoke",
                       {"version": 1, "reason": "撤回",
                        "step_up_token": token, "nonce": "n-revoke"})
    report(st == 200
           and (revoked or {}).get("release", {}).get("status") == "revoked"
           and (revoked or {}).get("release", {}).get("release_status") == "已撤回",
           "C4 revoke 真实成功（revoked/已撤回）", "%s %r" % (st, revoked))

    token = store.issue_step_up("u_signer", "case-release2", "reject",
                                "n-reject", now=time.time())
    st, rejected = call(app, "POST",
                        "/api/v1/cases/case-release2/release-decision", signer,
                        "K-rel-reject",
                        {"decision": "reject", "version": 1, "reason": "材料不足",
                         "step_up_token": token, "nonce": "n-reject"})
    report(st == 200
           and (rejected or {}).get("release", {}).get("status") == "rejected"
           and (rejected or {}).get("release", {}).get("release_status") == "已拒绝",
           "C4 reject 真实成功（rejected/已拒绝）", "%s %r" % (st, rejected))

    # C5 静态扫描
    sources = [open(os.path.join(REPO_ROOT, "api", name),
                    encoding="utf-8").read()
               for name in ("review_api.py", "write_api.py")]
    forbidden = ["decision_table", "coverage_composer", "evidence_sync",
                 "semantic_judge", "rule_judge", "normalizer",
                 "orchestrator", "derive_state(", "decide("]
    leaked = [(name, token) for name, src in zip(("review_api.py", "write_api.py"), sources)
              for token in forbidden if token in src]
    report(not leaked, "C5 API 层不含判定实现", repr(leaked))
    computed = []
    for name, src in zip(("review_api.py", "write_api.py"), sources):
        computed += [(name, line) for line in src.splitlines()
                     if re.match(r"^\s*(state|decision|[a-z_]*_state)\s*=", line)]
    report(not computed, "C5 API 层不计算 state/decision", repr(computed[:3]))
    direct_release = []
    for name, src in zip(("review_api.py", "write_api.py"), sources):
        direct_release += [(name, line) for line in src.splitlines()
                           if re.match(r"^\s*release_status\s*=", line)]
    report(not direct_release,
           "C5 机器/前端不可直写 release_status", repr(direct_release[:3]))
    report("gate.sign(" in sources[1] and "gate.revoke(" in sources[1],
           "C5 release 只走 ReleaseGate", "")

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
        import traceback
        tb = traceback.extract_tb(exc.__traceback__)
        if tb and os.path.basename(tb[-1].filename) in (
                "write_api.py", "review_api.py", "reviews_ledger.py",
                "finding_store.py", "takedown.py"):
            print("FAIL: 写 API 依赖抛异常: %s: %s"
                  % (type(exc).__name__, exc), file=sys.stderr)
            sys.exit(1)
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
