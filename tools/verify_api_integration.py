#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_api_integration.py — API ↔ 落盘 IR 联调

- 用 tools/smoke_end_to_end.py 现有链路产出真实 ReviewIR（通过 SMOKE_DUMP_IR
  导出到临时目录，不重复实现构造）。
- 用 fastapi.testclient.TestClient 挂 api/review_api.py 的 app。
- 断言 /review-api/queue 能列出该案；GET /cases/{id} 的 decision/coverage/
  release_status 与落盘 IR 逐字段一致；把 IR 改成哨兵值后 API 必须原样返回，
  证明 API 不重算。

退出码：0 全过 / 1 有红 / 2 未测（httpx/TestClient 不可用、smoke 未跑通）。
"""

import copy
import json
import os
import subprocess
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from fastapi.testclient import TestClient
    from api.review_api import create_app, FileProjectionRepository
    from base.auth_session import SessionStore
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: TestClient / API 依赖不可用: %s" % exc)
    sys.exit(2)


def release_case():
    h = "a" * 64
    return {
        "case_id": "case-release", "tenant": "t1", "product_line": "pump",
        "submitter_id": "u_sub", "final_reviewer_id": "u_dp3",
        "assignee_id": "u_dp3", "actionable": True,
        "ir": {
            "ir_id": "ir-rel", "ir_version": "review-ir-v1",
            "source_ir_version": "cu-rel",
            "content_unit_ref": {"unit_id": "cu-rel", "kind": "text"},
            "findings": [],
            "decision": {"state": "REVIEW", "layer": "DP3",
                         "release_status": "待放行", "obligations": []},
            "coverage": {"coverage_state": "full",
                         "modalities_evaluated": ["text"],
                         "rules_version": "rules-v1",
                         "control_points_applied": ["H01"]},
            "receipt_ref": "rc-rel", "rule_snapshot": "rs",
            "kb_snapshot": "kb", "control_points_version": "cp",
            "created_at": "2026-10-19T00:00:00Z",
        },
        "case_version": 1, "ir_id": "ir-rel", "ir_version": "review-ir-v1",
        "raw_sha256": h, "text_sha256": h,
        "conflict_table_version": "ct-v1",
        "frame_manifest_hash": h, "keyframe_set_hash": h,
        "ocr_output_hash": h, "asr_output_hash": h,
        "model_config_hash": h, "sampling_config_hash": h,
        "rule_snapshot": {"version": "rules-v1", "hash": h},
        "kb_snapshot": {"version": "kb-v1", "hash": h},
        "used_authority_refs": [], "media_fingerprints": [],
    }


def contains(expected, got):
    """落盘 IR 的每个字段都必须原样出现在响应里；允许 Pydantic 补默认字段。"""
    if isinstance(expected, dict):
        if not isinstance(got, dict):
            return False
        return all(k in got and contains(v, got[k]) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(got, list) or len(expected) != len(got):
            return False
        return all(contains(a, b) for a, b in zip(expected, got))
    return expected == got


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

    tmp = tempfile.mkdtemp(prefix="api-integration-")
    projection = os.path.join(tmp, "projection")
    os.makedirs(projection, exist_ok=True)

    # 1) 现有 smoke 链路产出真实 ReviewIR + cases 投影（只落临时目录）
    env = os.environ.copy()
    env["SMOKE_DUMP_IR"] = projection
    proc = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "tools", "smoke_end_to_end.py")],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        print("UNTESTED: smoke_end_to_end 未跑通（rc=%s）\n%s"
              % (proc.returncode, (proc.stdout or "")[-800:] + (proc.stderr or "")[-800:]))
        return 2

    cases_path = os.path.join(projection, "cases.json")
    with open(cases_path, encoding="utf-8") as f:
        cases = json.load(f)
    if not cases or not cases[0].get("ir"):
        print("UNTESTED: smoke 未导出 cases/IR")
        return 2

    # 2) 哨兵值：证明 API 原样读 IR，不重算
    ir = cases[0]["ir"]
    ir["decision"]["state"] = "SENTINEL-LABEL"
    ir["decision"]["layer"] = "SENTINEL-LAYER"
    ir["decision"]["release_status"] = "SENTINEL-RELEASE"
    ir["coverage"]["coverage_state"] = "SENTINEL-COVERAGE"
    ir["coverage"]["rules_version"] = "SENTINEL-RULES"
    expected = copy.deepcopy(ir)
    cases.append(release_case())
    with open(cases_path, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)

    store = SessionStore(":memory:")
    sid = store.create_session("u_dp3", tenant="t1", now=time.time())
    signer_sid = store.create_session("u_signer", tenant="t1", now=time.time())
    repo = FileProjectionRepository(projection)
    app = create_app(
        session_store=store, repository=repo,
        principals={
            "u_dp3": {"open_id": "ou_u_dp3", "tenant_id": "t1",
                      "roles": ["coordinator"],
                      "product_lines": ["pump"], "product_line": "pump"},
            "u_signer": {"open_id": "ou_u_signer", "tenant_id": "t1",
                         "roles": ["signer"],
                         "product_lines": ["pump"], "product_line": "pump",
                         "capabilities": ["release.sign", "release.revoke"]},
        })
    client = TestClient(app)
    cookies = {"session": sid}

    # 3) /review-api/queue 列出该案（真实 smoke IR 是 BLOCK；联调别名列出可读案件）
    resp = client.get("/review-api/queue", cookies=cookies)
    body = resp.json() if resp.status_code == 200 else None
    ids = [x.get("case_id") for x in (body or [])]
    report(resp.status_code == 200 and "case-smoke" in ids,
           "C0 /review-api/queue 列出 smoke 案件",
           "%s %r" % (resp.status_code, body))
    report(any(x.get("state") == "SENTINEL-LABEL" for x in (body or [])),
           "C0 queue 的标签来自 IR 哨兵值，不重算",
           repr(body))

    # 4) GET /cases/{id} 与落盘 IR 逐字段一致
    resp = client.get("/api/v1/cases/case-smoke", cookies=cookies)
    detail = resp.json() if resp.status_code == 200 else {}
    got = detail.get("ir") or {}
    report(resp.status_code == 200, "C1 GET /cases/{id} 200",
           "%s %r" % (resp.status_code, detail))
    report(contains(expected, got),
           "C1/C2 返回 IR 与落盘 IR 逐字段一致（含哨兵）",
           json.dumps({"got": got, "expected": expected}, ensure_ascii=False)[:1200])
    for key in ("state", "layer", "release_status"):
        report(got.get("decision", {}).get(key) == expected["decision"][key],
               "C2 decision.%s 原样返回" % key,
               repr(got.get("decision", {}).get(key)))
    for key in ("coverage_state", "rules_version"):
        report(got.get("coverage", {}).get(key) == expected["coverage"][key],
               "C2 coverage.%s 原样返回" % key,
               repr(got.get("coverage", {}).get(key)))

    # 5) 写侧：claim → actions.save_draft → actions.submit，独立 reviews_ledger
    r = client.post("/api/v1/cases/case-smoke/claim", json={},
                    headers={"Idempotency-Key": "I-claim"},
                    cookies=cookies)
    claim = r.json() if r.status_code == 200 else {}
    report(r.status_code == 200 and claim.get("status") == "claimed",
           "W0 claim → claimed", "%s %r" % (r.status_code, claim))

    r = client.post(
        "/api/v1/cases/case-smoke/actions",
        json={"action": "save_draft", "version": claim["version"],
              "draft": {"form": {"summary": "联调草稿"}, "notes": "note",
                        "evidence_selections": ["E-1"], "references": []}},
        headers={"Idempotency-Key": "I-draft"}, cookies=cookies)
    draft_out = r.json() if r.status_code == 200 else {}
    draft = draft_out.get("draft") or {}
    report(r.status_code == 200 and draft.get("snapshot_seq") == 1
           and len(draft.get("content_hash", "")) == 64,
           "W1 actions.save_draft → draft 快照", "%s %r" % (r.status_code, draft_out))
    report(len(app.state.reviews_ledger.formal_events()) == 0,
           "W1 autosave 不产 formal", repr(app.state.reviews_ledger.formal_events()))

    r = client.post(
        "/api/v1/cases/case-smoke/actions",
        json={"action": "submit", "version": draft_out.get("version"),
              "conclusion": {"status": "confirmed", "reason": "联调提交"}},
        headers={"Idempotency-Key": "I-submit"}, cookies=cookies)
    submitted = r.json() if r.status_code == 200 else {}
    formal = app.state.reviews_ledger.formal_events()
    report(r.status_code == 200 and len(formal) == 1
           and formal[0].get("from_draft_id") == draft.get("draft_id")
           and submitted.get("formal", {}).get("from_draft_id") == draft.get("draft_id"),
           "W2 actions.submit → reviews_ledger 独立账本 formal",
           "%s %r %r" % (r.status_code, submitted, formal))
    report(app.state.reviews_ledger.get_case("case-smoke").get("status") == "closed",
           "W2 submit 后 ledger status=closed",
           repr(app.state.reviews_ledger.get_case("case-smoke")))

    resp = client.get("/api/v1/cases/case-smoke", cookies=cookies)
    again = resp.json() if resp.status_code == 200 else {}
    review = again.get("review") or {}
    report(resp.status_code == 200 and review.get("status") == "closed"
           and review.get("version") == submitted.get("version"),
           "W3 API 回读反映 ledger 状态变化（不重算）",
           "%s review=%r submitted=%r" % (resp.status_code, review, submitted))
    report((again.get("ir") or {}).get("decision", {}).get("state")
           == "SENTINEL-LABEL",
           "W3 写后 IR 仍原样返回哨兵，不重算",
           repr((again.get("ir") or {}).get("decision")))

    # 6) 无 step-up 的签发 → API 级 403
    r = client.post(
        "/api/v1/cases/case-release/release-decision",
        json={"decision": "sign", "version": 1, "reason": "无 step-up"},
        headers={"Idempotency-Key": "I-rel-nostep"},
        cookies={"session": signer_sid})
    report(r.status_code == 403, "W4 无 step-up 签发 → 403",
           "%s %r" % (r.status_code, r.text))

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
                "review_api.py", "write_api.py", "auth_session.py"):
            print("FAIL: API 依赖抛异常: %s: %s"
                  % (type(exc).__name__, exc), file=sys.stderr)
            sys.exit(1)
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
