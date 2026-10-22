#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_finding_adjudication.py — T-170a/b：finding 裁决进权威链 + 结案守卫

## 它验什么

  A  confirm/reject 在生产路径可用：/actions 未开启 → 501；开启后 → 200。
  B  未裁决守卫：判定产出 1 条 candidate 时直接 submit_review → 409
     `unadjudicated_findings`；先 confirm/reject 再 submit → 200。
  C  裁决是 authority 命令：状态在 `ir.findings` 里，重启/重建后仍在；
     不依赖内存 `finding_store`。
  D  反向对照：确认一条已 confirmed 的 rule finding → 409
     `invalid_finding_transition`；不存在的 finding → 404；未 claim → 409。
  E  守卫不是恒拒：没有 candidate 的干净案件仍可正常 submit。
  F  变异证明（外部执行）：删掉 submit_review 的守卫后，B 必须红。

退出码：0 全过 / 1 有红 / 2 未测（TestClient/httpx 或依赖导入失败）。
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from fastapi.testclient import TestClient
    from api.review_api import (
        AuthorityCaseSource, FileProjectionRepository, create_app)
    from api.write_api import IMPLEMENTED_WRITE_PATHS
    from base.auth_session import SessionStore
    from base.business_event_store import BusinessEventStore, WriterLease
    from base.judge_entry import judge_unit
    from base.projection_store import ProjectionStore
    from base.projector import Projector
    from base.review_command_service import ReviewCommandService
    from base.submission_service import SubmissionIngestor
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 finding 裁决依赖: %s" % exc)
    print("提示：本验证器需要 fastapi/httpx；请用 `uv run` 或 "
          "`.venv/bin/python tools/verify_finding_adjudication.py` 运行，"
          "系统 python3 缺依赖时退 2 不代表实现坏了。")
    sys.exit(2)

TENANT = "t1"
PRODUCT_LINE = "吸奶器"
CURE_TEXT = "Our formula can cure disease and treat symptoms."
CLEAN_TEXT = "新品上市：售价 199 元，容量 240ml，适合 0-6 个月宝宝。"
CANDIDATE_ID = "f-candidate-fixture"
TMP_ROOTS = []

SUBJECTS = (
    "base/review_reducer.py",
    "api/write_api.py",
    "base/business_event_store.py",
    "base/projection_store.py",
    "base/review_command_service.py",
)


def body(submission_id, text=CURE_TEXT):
    return {
        "submission_id": submission_id,
        "content_type": "文本",
        "content_stage": "final_content",
        "entry_channel": "群消息",
        "source": {"kind": "free_text"},
        "text": text,
        "product_line": PRODUCT_LINE,
    }


def principal():
    return {"id": "u1", "tenant": TENANT, "open_id": "ou-1",
            "tenant_id": TENANT, "roles": ["dp3"],
            "product_lines": [PRODUCT_LINE]}


def judge_with_candidate(unit, **kwargs):
    """真实判定 + 一条 semantic candidate；用来证明守卫真的会挡。"""
    result = judge_unit(unit, **kwargs)
    ir = copy.deepcopy(result["ir"])
    text = unit["text"]
    quote = "cure disease"
    start = text.lower().find(quote)
    if start < 0:
        raise RuntimeError("fixture text 不含 cure disease")
    ir["findings"].append({
        "finding_id": CANDIDATE_ID,
        "control_code": "H01",
        "rule_key": "semantic.fixture",
        "status": "candidate",
        "severity": "L4",
        "produced_by": "semantic",
        "derived_from": None,
        "detected_by": "P1",
        "quote": text[start:start + len(quote)],
        "location": {"kind": "text_span", "start": start,
                     "end": start + len(quote), "quote": quote},
        "authority_ref": [],
        "authority_state": None,
        "rule_conflict": False,
        "confirmed_by_rule_class": False,
    })
    return {**result, "ir": ir, "findings": ir["findings"]}


def build(ingestor, capabilities=None):
    tmp = Path(tempfile.mkdtemp(prefix="finding-adjudication-"))
    TMP_ROOTS.append(tmp)
    lease = WriterLease(tmp / "writer.lock")
    lease.acquire()
    authority = BusinessEventStore(tmp / "authority", lease=lease)
    projection = ProjectionStore(tmp / "review.db")
    service = ReviewCommandService(authority, projection)
    store = SessionStore(":memory:")
    frozen = tmp / "frozen"
    frozen.mkdir()
    app = create_app(
        session_store=store,
        repository=FileProjectionRepository(
            frozen, strict=True, require_cases=False),
        case_source=AuthorityCaseSource(authority),
        submission_ingestor=ingestor,
        review_read_store=projection,
        review_command_service=service,
        principal_provider=lambda principal_id, tenant: dict(
            principal(), id=principal_id, tenant=tenant, tenant_id=tenant),
        enabled_write_capabilities=(set(IMPLEMENTED_WRITE_PATHS)
                                    if capabilities is None else capabilities),
        app_env="dev",
    )
    session = store.create_session("u1", tenant=TENANT)
    client = TestClient(app)
    client.cookies.set("session", session)
    return {"client": client, "authority": authority,
            "projection": projection, "service": service,
            "lease": lease, "tmp": tmp}


def call(client, method, path, key, payload=None):
    response = client.request(
        method, path, json=payload,
        headers={"Idempotency-Key": key} if key else {})
    try:
        parsed = response.json()
    except ValueError:
        parsed = None
    return response.status_code, parsed


def ingest_and_claim(env, submission_id):
    client = env["client"]
    st, created = call(client, "POST", "/api/v1/submissions",
                       "ingest-%s" % submission_id, body(submission_id))
    if st != 200:
        raise AssertionError("ingest failed: %s %r" % (st, created))
    case_id = created["case_id"]
    st, claimed = call(client, "POST", "/api/v1/cases/%s/claim" % case_id,
                       "claim-%s" % submission_id, {})
    if st != 200:
        raise AssertionError("claim failed: %s %r" % (st, claimed))
    return case_id, claimed["version"]


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

    # ── A/B：confirm/reject 可用 + 未裁决守卫 ──────────────────────
    env = build(SubmissionIngestor(judge_fn=judge_with_candidate))
    client = env["client"]
    st, created = call(client, "POST", "/api/v1/submissions", "ingest-1",
                       body("s-1"))
    case_id = (created or {}).get("case_id")
    st_case, detail = call(client, "GET", "/api/v1/cases/%s" % case_id, None)
    statuses = [f.get("status") for f in
                ((detail or {}).get("ir") or {}).get("findings") or []]
    report(st == 200 and st_case == 200 and "candidate" in statuses,
           "A1 判定产出带 candidate 的案件", "%s %r" % (st_case, statuses))
    st, claimed = call(client, "POST", "/api/v1/cases/%s/claim" % case_id,
                       "claim-1", {})
    version = (claimed or {}).get("version")
    report(st == 200 and isinstance(version, int),
           "A2 claim 取得当前版本", "%s %r" % (st, claimed))
    st, blocked = call(
        client, "POST", "/api/v1/cases/%s/actions" % case_id, "submit-blocked",
        {"action": "submit", "version": version,
         "conclusion": {"review_notes": "未逐条看就结案"}})
    report(st == 409 and "unadjudicated_findings" in str((blocked or {}).get("message")),
           "B1 有 candidate 直接 submit → 409 unadjudicated_findings",
           "%s %r" % (st, blocked))
    st, confirmed = call(
        client, "POST", "/api/v1/cases/%s/actions" % case_id, "confirm-1",
        {"action": "confirm", "version": version,
         "finding_id": CANDIDATE_ID, "reason": "人工确认"})
    finding = (confirmed or {}).get("finding") or {}
    version = (confirmed or {}).get("version")
    report(st == 200 and finding.get("status") == "confirmed"
           and finding.get("adjudicated_by") == "u1",
           "B2 confirm candidate → 200 且状态落 confirmed",
           "%s %r" % (st, finding))
    st, submitted = call(
        client, "POST", "/api/v1/cases/%s/actions" % case_id, "submit-ok",
        {"action": "submit", "version": version,
         "conclusion": {"review_notes": "逐条看过后结案"}})
    report(st == 200 and (submitted or {}).get("status") == "closed"
           and (submitted or {}).get("formal"),
           "B3 裁决后 submit → 200 并生成 formal",
           "%s %r" % (st, submitted))

    # ── B：reject 路径 ────────────────────────────────────────────
    reject_env = build(SubmissionIngestor(judge_fn=judge_with_candidate))
    reject_case, reject_version = ingest_and_claim(reject_env, "s-reject")
    st, rejected = call(
        reject_env["client"], "POST",
        "/api/v1/cases/%s/actions" % reject_case, "reject-1",
        {"action": "reject", "version": reject_version,
         "finding_id": CANDIDATE_ID, "reason": "误报"})
    report(st == 200 and ((rejected or {}).get("finding") or {}).get("status") == "rejected",
           "B4 reject candidate → 200", "%s %r" % (st, rejected))
    st, submitted = call(
        reject_env["client"], "POST",
        "/api/v1/cases/%s/actions" % reject_case, "submit-after-reject",
        {"action": "submit", "version": (rejected or {}).get("version"),
         "conclusion": {"review_notes": "驳回后结案"}})
    report(st == 200, "B5 reject 后 submit → 200", "%s %r" % (st, submitted))

    # ── C：重启后仍在（authority 重放，不是内存态） ───────────────
    stored = env["authority"].state(case_id)
    stored_finding = next(
        (f for f in (stored.get("ir") or {}).get("findings") or []
         if f.get("finding_id") == CANDIDATE_ID), None)
    report(stored_finding is not None
           and stored_finding.get("status") == "confirmed"
           and stored_finding.get("adjudicated_by") == "u1",
           "C1 裁决已写进 authority state 的 ir.findings",
           repr(stored_finding))
    env["lease"].release()
    lease2 = WriterLease(env["tmp"] / "writer.lock")
    lease2.acquire()
    try:
        authority2 = BusinessEventStore(env["tmp"] / "authority", lease=lease2)
        replayed = next(
            (f for f in (authority2.state(case_id).get("ir") or {}).get("findings") or []
             if f.get("finding_id") == CANDIDATE_ID), None)
        projection2 = ProjectionStore(env["tmp"] / "rebuild.db")
        Projector(authority2, projection2).rebuild()
        rebuilt_case = projection2.get_case(case_id)
        rebuilt_finding = next(
            (f for f in (rebuilt_case.get("ir") or {}).get("findings") or []
             if f.get("finding_id") == CANDIDATE_ID), None)
        report(replayed is not None
               and replayed.get("status") == "confirmed"
               and rebuilt_finding is not None
               and rebuilt_finding.get("status") == "confirmed",
               "C2 重启 + 投影重建后裁决仍在",
               "replayed=%r rebuilt=%r" % (replayed, rebuilt_finding))
        projection2.close()
    finally:
        lease2.release()

    # ── D：非法转移 / 不存在 / 未 claim ──────────────────────────
    bad_env = build(SubmissionIngestor(judge_fn=judge_with_candidate))
    bad_case, bad_version = ingest_and_claim(bad_env, "s-bad")
    st, bad = call(
        bad_env["client"], "POST", "/api/v1/cases/%s/actions" % bad_case,
        "confirm-rule", {"action": "confirm", "version": bad_version,
                         "finding_id": "f-rule-confirmed"})
    # 真实 rule finding 的 id 不是这个固定值；先取一条 confirmed 的 id。
    if st == 404:
        st_case, detail = call(
            bad_env["client"], "GET",
            "/api/v1/cases/%s" % bad_case, None)
        confirmed_id = next(
            (f.get("finding_id") for f in
             ((detail or {}).get("ir") or {}).get("findings") or []
             if f.get("status") == "confirmed"), None)
        if confirmed_id:
            st, bad = call(
                bad_env["client"], "POST",
                "/api/v1/cases/%s/actions" % bad_case, "confirm-rule-2",
                {"action": "confirm", "version": bad_version,
                 "finding_id": confirmed_id})
    report(st == 409 and "invalid_finding_transition" in str((bad or {}).get("message")),
           "D1 确认已 confirmed 的 rule finding → 409", "%s %r" % (st, bad))
    st, bad = call(
        bad_env["client"], "POST", "/api/v1/cases/%s/actions" % bad_case,
        "confirm-missing", {"action": "confirm", "version": bad_version,
                            "finding_id": "f-does-not-exist"})
    report(st == 404, "D2 不存在的 finding → 404", "%s %r" % (st, bad))

    unclaimed_env = build(SubmissionIngestor(judge_fn=judge_with_candidate))
    st, created = call(unclaimed_env["client"], "POST", "/api/v1/submissions",
                       "ingest-unclaimed", body("s-unclaimed"))
    unclaimed_case = (created or {}).get("case_id")
    st, bad = call(
        unclaimed_env["client"], "POST",
        "/api/v1/cases/%s/actions" % unclaimed_case, "confirm-unclaimed",
        {"action": "confirm", "version": 1, "finding_id": CANDIDATE_ID})
    report(st == 409 and "not_assignee" in str((bad or {}).get("message")),
           "D3 未 claim 就裁决 → 409 not_assignee", "%s %r" % (st, bad))

    # ── E：守卫不是恒拒：没有 candidate 的干净案件仍可 submit ────
    clean_env = build(SubmissionIngestor())
    clean_case, clean_version = ingest_and_claim(clean_env, "s-clean")
    st, clean_submit = call(
        clean_env["client"], "POST",
        "/api/v1/cases/%s/actions" % clean_case, "clean-submit",
        {"action": "submit", "version": clean_version,
         "conclusion": {"review_notes": "无候选，正常结案"}})
    report(st == 200 and (clean_submit or {}).get("status") == "closed",
           "E1 没有 candidate 的干净案件可正常 submit",
           "%s %r" % (st, clean_submit))

    # ── A：capability 成对断言 ────────────────────────────────────
    disabled_caps = set(IMPLEMENTED_WRITE_PATHS) - {
        "/api/v1/cases/{id}/actions"}
    disabled_env = build(SubmissionIngestor(judge_fn=judge_with_candidate),
                         capabilities=disabled_caps)
    st, created = call(disabled_env["client"], "POST", "/api/v1/submissions",
                       "ingest-disabled", body("s-disabled"))
    disabled_case = (created or {}).get("case_id")
    st, disabled = call(
        disabled_env["client"], "POST",
        "/api/v1/cases/%s/actions" % disabled_case, "confirm-disabled",
        {"action": "confirm", "version": 1, "finding_id": CANDIDATE_ID})
    report(st == 501, "A3 /actions 未开启 → 501 capability_not_enabled",
           "%s %r" % (st, disabled))
    enabled_env = build(SubmissionIngestor(judge_fn=judge_with_candidate))
    enabled_case, enabled_version = ingest_and_claim(enabled_env, "s-enabled")
    st, enabled = call(
        enabled_env["client"], "POST",
        "/api/v1/cases/%s/actions" % enabled_case, "confirm-enabled",
        {"action": "confirm", "version": enabled_version,
         "finding_id": CANDIDATE_ID})
    report(st == 200, "A4 /actions 开启 → confirm 200", "%s %r" % (st, enabled))

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    finally:
        for root in TMP_ROOTS:
            shutil.rmtree(root, ignore_errors=True)
    sys.exit(code)
