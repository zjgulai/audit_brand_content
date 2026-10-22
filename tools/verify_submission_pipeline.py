#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_submission_pipeline.py — T-100…T-103：内容入库 → 判定 → 案件 → 读回

## 它验什么

  P  依据解析器：19 个 active 控制点的 authority_ref 全部可解析；篡改/缺条目 → missing。
  R  reducer：version 0 起建案；ingest_submission 写 content/ir；重复 → already_ingested。
  I  authority 幂等：同 key 重放不重判、不新增批次；同 key 异 submission → 409；
     同 submission 异 key → 409；投影重建后 IR 仍在。
  E  端到端：POST /api/v1/submissions → GET /api/v1/cases/{id} 读回 findings 与 decision；
     同时断言 **BLOCK 路径可达**，以及 claim 能看见新案。
  V  REVIEW 路径：注入 missing 依据查询 → REVIEW + evidence_gap，findings 仍读得回；
     干净文本仍是 REVIEW（PASS 在空族存在期间结构性不可达，不伪造）。
  N  反向对照：坏输入 / 判定抛错 / 判定 run_state != OK / 读回断言对篡改值必须红；
     没有 IR 的案件不得返回 200 + 空 findings。
  C  T-103：frozen 目录为空、没有 cases.json 也能建案并读回；扫描器对
     `open("cases.json","w")` 与 `Path("cases.json").write_text(...)` 必须红，
     真实 api/+base/ 必须没有写命中。

退出码：0 全过 / 1 有红 / 2 未测（TestClient/httpx 不可用或依赖导入失败）。
"""
from __future__ import annotations

import ast
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
    from api.production_app import PRODUCTION_WRITE_PATHS
    from api.write_api import IMPLEMENTED_WRITE_PATHS
    from base.auth_session import SessionStore
    from base.authority_query import ExternalStandardsAuthority
    from base.business_event_store import BusinessEventStore, WriterLease
    from base.projection_store import ProjectionStore
    from base.projector import Projector
    from base.review_command_service import ReviewCommandService
    from base.review_reducer import initial_state, reduce_command
    from base.reviews_ledger import LedgerConflict, LedgerValidation
    from base.submission_service import SubmissionIngestor
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入入库链路依赖: %s" % exc)
    print("提示：本验证器需要 fastapi/httpx；请用 `uv run` 或 "
          "`.venv/bin/python tools/verify_submission_pipeline.py` 运行，"
          "系统 python3 缺依赖时退 2 不代表实现坏了。")
    sys.exit(2)

TENANT = "t1"
PRODUCT_LINE = "吸奶器"
CURE_TEXT = "Our formula can cure disease and treat symptoms."
CLEAN_TEXT = "新品上市：售价 199 元，容量 240ml，适合 0-6 个月宝宝。"
TMP_ROOTS = []

# 覆盖登记表要求 subjects 的「文件名 + 父目录段」在本源码里逐字出现。
SUBJECTS = (
    "base/authority_query.py",
    "base/submission_service.py",
    "base/review_reducer.py",
    "base/business_event_store.py",
    "base/projection_store.py",
    "base/review_command_service.py",
    "api/write_api.py",
    "api/review_api.py",
    "api/production_app.py",
    "research/kb/外部标准库-v1.json",
)


def body(submission_id="s-1", text=CURE_TEXT, **overrides):
    value = {
        "submission_id": submission_id,
        "content_type": "文本",
        "content_stage": "final_content",
        "entry_channel": "群消息",
        "source": {"kind": "free_text"},
        "text": text,
        "product_line": PRODUCT_LINE,
    }
    value.update(overrides)
    return value


def principal():
    return {"id": "u1", "tenant": TENANT, "open_id": "ou-1",
            "tenant_id": TENANT, "roles": ["dp3"],
            "product_lines": [PRODUCT_LINE]}


def build(ingestor=None, capabilities=None):
    tmp = Path(tempfile.mkdtemp(prefix="submission-pipeline-"))
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
        submission_ingestor=ingestor or SubmissionIngestor(),
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
    return {
        "client": client, "authority": authority, "projection": projection,
        "service": service, "store": store, "frozen": frozen, "tmp": tmp,
        "lease": lease,
    }


def _contains(expected, got):
    """expected 的每个字段都必须在 got 里逐值相等；got 允许补模型默认字段。"""
    if isinstance(expected, dict):
        return isinstance(got, dict) and all(
            key in got and _contains(value, got[key])
            for key, value in expected.items())
    if isinstance(expected, list):
        return (isinstance(got, list) and len(expected) == len(got)
                and all(_contains(a, b) for a, b in zip(expected, got)))
    return expected == got


def readback_ok(expected_ir, got_ir):
    """端到端判据本身；单独可调，供反向对照证明它不是恒真。

    响应模型会给 Finding 补 `evidence_id: null` 之类的默认字段，所以用
    「expected ⊆ got」而不是整字典相等；但 expected 里缺字段/值不同仍然红。
    """
    if not isinstance(expected_ir, dict) or not isinstance(got_ir, dict):
        return False
    return (_contains(expected_ir.get("decision"), got_ir.get("decision"))
            and _contains(expected_ir.get("findings"), got_ir.get("findings")))


def cases_json_write_offenses(root):
    """AST 扫描：对 cases.json 的写入调用。注释/字符串提及不算。"""
    root = Path(root)
    offenses = []
    for path in root.rglob("*.py"):
        if any(part in {".git", ".venv", "node_modules", "__pycache__"}
               for part in path.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, UnicodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name not in ("open", "write_text", "write_bytes"):
                continue
            segment = ast.get_source_segment(source, node) or ""
            if "cases.json" not in segment:
                continue
            if name == "open":
                modes = []
                for arg in list(node.args[1:]) + [
                        kw.value for kw in node.keywords if kw.arg == "mode"]:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        modes.append(arg.value)
                if not any(("w" in mode or "a" in mode or "x" in mode)
                           for mode in modes):
                    continue
            offenses.append((str(path.relative_to(root)), node.lineno, name))
    return offenses


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

    # ── P 依据解析器 ────────────────────────────────────────────────
    resolver = ExternalStandardsAuthority()
    cp = json.loads((REPO_ROOT / "research" / "governance"
                     / "control-points-v1.json").read_text(encoding="utf-8"))
    active_refs = [ref for point in cp["control_points"]
                   if point.get("status") == "active"
                   for ref in (point.get("authority_ref") or [])]
    resolved = [resolver.query(ref) for ref in active_refs]
    report(len(active_refs) >= 19 and all(r["state"] == "ok" for r in resolved),
           "P1 全部 active 控制点 authority_ref 可解析为 ok",
           "%d refs / states=%r" % (len(active_refs), sorted({r["state"] for r in resolved})))
    report(resolver.snapshot_id.startswith("external-stdlib-v1:")
           and resolver.snapshot_id == ExternalStandardsAuthority().snapshot_id,
           "P2 kb_snapshot 稳定且带指纹", resolver.snapshot_id)
    h01 = next(ref for ref in active_refs if ref.get("entry_id") == "EXT-021")
    report(resolver.query({**h01, "fingerprint": "sha256:deadbeef"})["state"] == "missing",
           "P3 篡改 fingerprint → missing")
    report(resolver.query({"entry_id": "EXT-NOPE"})["state"] == "missing",
           "P4 不存在的 entry_id → missing")
    report(resolver.query({"path": "../../etc/passwd", "quote": "x"})["state"] == "missing",
           "P5 越界 path → missing")
    internal_ref = next((ref for point in cp["control_points"]
                         for ref in (point.get("authority_ref") or [])
                         if ref.get("path")), None)
    if internal_ref is not None:
        report(resolver.query(internal_ref)["state"] == "ok",
               "P6 内部引用 path+quote 可解析",
               json.dumps(internal_ref, ensure_ascii=False)[:120])
    else:
        report(False, "P6 内部引用 path+quote 可解析", "真实控制点里没有内部引用样本")

    # ── R reducer ───────────────────────────────────────────────────
    ingestor = SubmissionIngestor()
    prepared = ingestor.prepare(body(), principal=principal())
    state = initial_state(prepared["case_id"])
    report(state["version"] == 0 and state.get("submission_id") is None,
           "R1 initial_state 从 version 0 起且无 submission")
    new_state, events, result = reduce_command(
        state, "ingest_submission", "u1", 0,
        {**prepared["payload"], "case_id": prepared["case_id"]})
    report(new_state["version"] == 1
           and new_state["submission_id"] == "s-1"
           and new_state["submission_hash"] == prepared["payload"]["submission_hash"]
           and isinstance(new_state["content"], dict)
           and isinstance(new_state["ir"], dict),
           "R2 ingest_submission 写入 content/ir 且 version=1",
           repr(sorted(new_state)))
    report(result["submission_id"] == "s-1"
           and result["decision"]["state"] == new_state["ir"]["decision"]["state"]
           and events[0]["type"] == "review.ingest_submission",
           "R3 命令结果携带 submission_id/decision")
    try:
        reduce_command(new_state, "ingest_submission", "u1", 1,
                       {**prepared["payload"], "case_id": prepared["case_id"]})
        duplicate = None
    except LedgerConflict as exc:
        duplicate = exc.code
    report(duplicate == "already_ingested", "R4 重复 ingest → already_ingested", repr(duplicate))
    for name, mutate in (
            ("缺 submission_hash", lambda value: value.pop("submission_hash")),
            ("judgment.run_state≠OK", lambda value: value["judgment"].update({"run_state": "ERROR"})),
            ("label 与 IR 不一致", lambda value: value["judgment"].update({"label": "PASS"})),
            ("content 缺 fingerprint", lambda value: value["content"].pop("fingerprint")),
    ):
        bad = json.loads(json.dumps(prepared["payload"]))
        mutate(bad)
        try:
            reduce_command(initial_state("case-bad"), "ingest_submission", "u1", 0,
                           {**bad, "case_id": "case-bad"})
            rejected = False
        except LedgerValidation:
            rejected = True
        report(rejected, "R5 %s → 拒绝" % name)

    # ── I 幂等 + 投影重建 ───────────────────────────────────────────
    env = build()
    client, authority = env["client"], env["authority"]
    first = client.post("/api/v1/submissions", json=body(), headers={"Idempotency-Key": "k-1"})
    case_id = (first.json() or {}).get("case_id")
    report(first.status_code == 200 and first.json().get("replayed") is False
           and authority.head()["seq"] == 1,
           "I1 首次提交建案（seq=1）", "%s %r" % (first.status_code, first.json()))
    replay = client.post("/api/v1/submissions", json=body(), headers={"Idempotency-Key": "k-1"})
    report(replay.status_code == 200 and replay.json().get("replayed") is True
           and replay.json().get("case_id") == case_id and authority.head()["seq"] == 1,
           "I2 同 key 重放不重判、不新增批次",
           "%s seq=%s" % (replay.status_code, authority.head()["seq"]))
    other_key = client.post("/api/v1/submissions", json=body(), headers={"Idempotency-Key": "k-2"})
    report(other_key.status_code == 409
           and "already_ingested" in str(other_key.json().get("message")),
           "I3 同 submission 异 key → 409 already_ingested",
           "%s %r" % (other_key.status_code, other_key.json()))
    other_body = client.post("/api/v1/submissions",
                             json=body(text="different text"),
                             headers={"Idempotency-Key": "k-1"})
    report(other_body.status_code == 409
           and "idempotency_conflict" in str(other_body.json().get("message")),
           "I4 同 key 异 submission → 409 idempotency_conflict",
           "%s %r" % (other_body.status_code, other_body.json()))
    stored = authority.state(case_id)
    Projector(authority, env["projection"]).rebuild()
    rebuilt = env["projection"].get_case(case_id)
    report(rebuilt is not None and rebuilt.get("ir") == stored.get("ir"),
           "I5 删投影重建后 authority 里的 IR 逐字段相同")

    # ── E 端到端 BLOCK + 读回 ──────────────────────────────────────
    got = client.get("/api/v1/cases/%s" % case_id)
    got_ir = (got.json() or {}).get("ir") or {}
    report(got.status_code == 200 and got_ir.get("decision", {}).get("state") == "BLOCK",
           "E1 GET /cases/{id} 读回 BLOCK decision",
           "%s %r" % (got.status_code, got_ir.get("decision")))
    report(readback_ok(stored.get("ir"), got_ir),
           "E2 findings 与 authority 判定逐条相等",
           "got=%d expected=%d" % (len(got_ir.get("findings") or []),
                                   len((stored.get("ir") or {}).get("findings") or [])))
    report(bool(got_ir.get("findings"))
           and all(f.get("quote") and f.get("severity") and f.get("control_code")
                   for f in got_ir["findings"]),
           "E3 BLOCK 案件带真实 findings（quote/severity/control_code）")
    listed = client.get("/api/v1/cases")
    report(listed.status_code == 200
           and case_id in {row["case_id"] for row in listed.json()},
           "E4 GET /cases 能列出新案")
    queued = client.get("/api/v1/queue")
    report(queued.status_code == 200
           and case_id not in {row["case_id"] for row in queued.json()},
           "E5 BLOCK 不进 REVIEW queue（不冒充待人工）")
    claimed = client.post("/api/v1/cases/%s/claim" % case_id, json={},
                          headers={"Idempotency-Key": "claim-1"})
    report(claimed.status_code == 200 and claimed.json().get("status") == "claimed",
           "E6 新案可被 claim（写路由看得见）",
           "%s %r" % (claimed.status_code, claimed.json()))

    ad_env = build()
    ad_body = body(submission_id="s-ad", text=None, source={"kind": "ad_text"},
                   fields={"Primary Text": "Our formula can cure disease",
                           "Headline": "Feel better"})
    ad_response = ad_env["client"].post(
        "/api/v1/submissions", json=ad_body,
        headers={"Idempotency-Key": "ad-1"})
    ad_case = (ad_response.json() or {}).get("case_id")
    ad_ir = (ad_env["client"].get(
        "/api/v1/cases/%s" % ad_case).json() or {}).get("ir") or {}
    report(ad_response.status_code == 200
           and ad_ir.get("content_unit_ref", {}).get("kind") == "ad_text"
           and ad_ir.get("decision", {}).get("state") == "BLOCK",
           "E7 ad_text 走 from_ad_record 并读回 BLOCK",
           "%s %r" % (ad_response.status_code, ad_ir.get("content_unit_ref")))

    # ── V REVIEW 路径 + PASS 不可达 ────────────────────────────────
    missing_env = build(SubmissionIngestor(
        authority_query=lambda ref: {"state": "missing"}))
    review_response = missing_env["client"].post(
        "/api/v1/submissions", json=body(submission_id="s-review"),
        headers={"Idempotency-Key": "review-1"})
    review_case = (review_response.json() or {}).get("case_id")
    review_ir = (missing_env["client"].get(
        "/api/v1/cases/%s" % review_case).json() or {}).get("ir") or {}
    report(review_response.status_code == 200
           and review_ir.get("decision", {}).get("state") == "REVIEW"
           and "evidence_gap" in (review_ir.get("decision", {}).get("obligations") or [])
           and len(review_ir.get("findings") or []) > 0
           and all(f.get("authority_state") == "missing"
                   for f in review_ir["findings"]),
           "V1 依据 missing → REVIEW + evidence_gap，findings 仍读得回",
           repr(review_ir.get("decision")))
    clean_env = build()
    clean_response = clean_env["client"].post(
        "/api/v1/submissions", json=body(submission_id="s-clean", text=CLEAN_TEXT),
        headers={"Idempotency-Key": "clean-1"})
    clean_case = (clean_response.json() or {}).get("case_id")
    clean_ir = (clean_env["client"].get(
        "/api/v1/cases/%s" % clean_case).json() or {}).get("ir") or {}
    reasons = json.dumps(clean_ir.get("coverage", {}).get(
        "not_evaluated_reason", []), ensure_ascii=False)
    report(clean_response.status_code == 200
           and clean_ir.get("decision", {}).get("state") == "REVIEW"
           and clean_ir.get("coverage", {}).get("coverage_state") == "partial"
           and "场景控制" in reasons and "权利控制" in reasons and "渠道控制" in reasons,
           "V2 干净文本仍是 REVIEW（PASS 结构性不可达，不伪造）",
           "%r %r" % (clean_ir.get("decision"), clean_ir.get("coverage")))

    # ── N 反向对照 ─────────────────────────────────────────────────
    bad_env = build()
    bad_client = bad_env["client"]
    seq_before = bad_env["authority"].head()["seq"]
    bad_cases = [
        ("缺 submission_id", {"content_type": "文本"}, 422),
        ("非法 content_type", body(content_type="图片"), 422),
        ("非法 source.kind", body(source={"kind": "document"}), 422),
        ("ad_text 空字段", body(source={"kind": "ad_text"}, fields={}), 422),
        ("NAS 通道", body(entry_channel="NAS"), 422),
        ("超长正文", body(text="x" * 100001), 413),
    ]
    for index, (name, payload, expected) in enumerate(bad_cases):
        st, response = (lambda r: (r.status_code, r.json()))(
            bad_client.post("/api/v1/submissions", json=payload,
                            headers={"Idempotency-Key": "bad-%d" % index}))
        report(st == expected and bad_env["authority"].head()["seq"] == seq_before,
               "N1 %s → %d 且不建案" % (name, expected),
               "%s %r" % (st, response))

    def boom(*_args, **_kwargs):
        raise RuntimeError("judge boom")

    fail_env = build(SubmissionIngestor(judge_fn=boom))
    st, response = (lambda r: (r.status_code, r.json()))(
        fail_env["client"].post("/api/v1/submissions", json=body(submission_id="s-fail"),
                                headers={"Idempotency-Key": "fail-1"}))
    report(st == 422 and fail_env["authority"].head()["seq"] == 0,
           "N2 判定抛错 → 422 且 authority 为空", "%s %r" % (st, response))

    def not_ok(*_args, **_kwargs):
        return {"run_state": "ERROR", "label": None, "layer": None,
                "release_status": None, "ir": {}, "findings": []}

    error_env = build(SubmissionIngestor(judge_fn=not_ok))
    st, response = (lambda r: (r.status_code, r.json()))(
        error_env["client"].post("/api/v1/submissions",
                                 json=body(submission_id="s-error"),
                                 headers={"Idempotency-Key": "error-1"}))
    report(st == 422 and error_env["authority"].head()["seq"] == 0,
           "N3 判定 run_state≠OK → 422 且 authority 为空", "%s %r" % (st, response))

    tampered = json.loads(json.dumps(got_ir))
    tampered["decision"]["state"] = "PASS"
    report(not readback_ok(stored.get("ir"), tampered),
           "N4 读回断言对篡改 decision 必须红（判据不是恒真）")
    tampered = json.loads(json.dumps(got_ir))
    if tampered.get("findings"):
        tampered["findings"][0]["quote"] = "TAMPERED"
    report(not readback_ok(stored.get("ir"), tampered),
           "N5 读回断言对篡改 findings 必须红")

    no_ir = bad_env["service"].execute(
        aggregate_id="case-no-ir", command="claim",
        actor={"principal_id": "u1", "tenant_id": TENANT},
        expected_version=0, payload={}, idempotency_key="no-ir-claim")
    no_ir_case = no_ir["result"]["case_id"]
    st, response = (lambda r: (r.status_code, r.json()))(
        bad_env["client"].get("/api/v1/cases/%s" % no_ir_case))
    report(st == 404, "N6 没有 IR 的案件不得返回 200 + 空 findings",
           "%s %r" % (st, response))

    # ── C T-103：frozen 目录与 cases.json 写入 ─────────────────────
    report(env["frozen"].is_dir() and os.listdir(env["frozen"]) == []
           and not (env["frozen"] / "cases.json").exists(),
           "C1 frozen 目录为空且始终没有 cases.json",
           repr(os.listdir(env["frozen"])))
    real_offenses = (cases_json_write_offenses(REPO_ROOT / "api")
                     + cases_json_write_offenses(REPO_ROOT / "base"))
    report(real_offenses == [], "C2 api/+base/ 没有 cases.json 写入点",
           repr(real_offenses))
    control = Path(tempfile.mkdtemp(prefix="cases-json-control-"))
    TMP_ROOTS.append(control)
    (control / "bad.py").write_text(
        'import json\n'
        'open("cases.json", "w").write("{}")\n'
        'from pathlib import Path\n'
        'Path("cases.json").write_text("{}")\n', encoding="utf-8")
    offenses = cases_json_write_offenses(control)
    report(len(offenses) == 2, "C3 写入扫描器对坏样本必须红",
           repr(offenses))

    # ── 生产写面 ───────────────────────────────────────────────────
    report("/api/v1/submissions" in PRODUCTION_WRITE_PATHS
           and "/api/v1/submissions" in IMPLEMENTED_WRITE_PATHS,
           "S1 入库端点同时进入生产 capability 与实现表")

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
