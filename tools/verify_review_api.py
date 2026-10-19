#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_review_api.py — T2-01 review-api（只读 API）

覆盖：
  C0  OpenAPI 3.1；UIUX Appendix B 的每个端点都存在（缺一即红）
  C1  Pydantic 响应模型字段与 contracts/review-ir-v1.schema.json 对齐
  C2  鉴权：无 session → 401；越权 → 403；IT 读内容 → 403
  C3  /metrics 内部：非内部角色 403，内部 200
  C4  /cases/{id}/unclaim 写端点存在（501 占位）
  C5  状态直接读已落盘 IR，不在 API 层计算（静态扫描无判定实现 import）
  R1  API 层 import 判定实现 → 静态扫描红
  R2  删鉴权 → 无 session 用例红
  R3  OpenAPI 写成 3.0 → 红
  R4  缺 /unclaim 端点 → Appendix B 覆盖红

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
UIUX = os.path.join(REPO_ROOT, "PMO", "audit",
                    "内容审查Agent-UIUX前后端规格草案-v1.md")
IR_SCHEMA = os.path.join(REPO_ROOT, "contracts", "review-ir-v1.schema.json")

try:
    from api.review_api import create_app, InMemoryRepository
    from base.auth_session import SessionStore
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 api.review_api: %s" % exc)
    sys.exit(2)


def expected_endpoints():
    """从 UIUX Appendix B 表解析端点；/metrics 不加重前缀。"""
    text = open(UIUX, encoding="utf-8").read()
    section = text.split("# Appendix B", 1)[1].split("# Appendix C", 1)[0]
    out = set()
    for line in section.splitlines():
        m = re.match(r"^\| (GET|POST|GET/POST) ([^|]+) \|", line)
        if not m:
            continue
        methods = m.group(1).split("/")
        cell = m.group(2).strip()
        for token in cell.split():
            if not token.startswith("/"):
                continue
            for sub in token.split("\\|"):
                if not sub.startswith("/"):
                    continue
                path = sub if sub == "/metrics" else "/api/v1" + sub
                for method in methods:
                    out.add((method, path))
    return out


def call(app, method, path, cookie=None, body=None):
    headers = [(b"host", b"testserver")]
    if cookie:
        headers.append((b"cookie", ("session=" + cookie).encode()))
    if body is not None:
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
        return {"type": "http.request", "body": body or b"", "more_body": False}

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
        "ir_id": ir_id,
        "ir_version": "review-ir-v1",
        "source_ir_version": "cu-1",
        "content_unit_ref": {"unit_id": "cu-1", "kind": "image"},
        "findings": [],
        "decision": {"state": state, "layer": "DP2",
                     "release_status": "待放行", "obligations": []},
        "coverage": {"coverage_state": "partial",
                     "modalities_evaluated": ["image"],
                     "rules_version": "rules-v1",
                     "control_points_applied": ["H01"]},
        "receipt_ref": "rc-1",
        "rule_snapshot": "rs-1",
        "kb_snapshot": "kb-1",
        "control_points_version": "cp-v1",
        "created_at": "2026-10-19T00:00:00Z",
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
        {"case_id": "case-own", "tenant": "t1", "product_line": "pump",
         "submitter_id": "u_sub", "final_reviewer_id": "u_dp3",
         "assignee_id": "u_dp3", "actionable": True, "ir": ir()},
        {"case_id": "case-other", "tenant": "t1", "product_line": "pump",
         "submitter_id": "u_other", "final_reviewer_id": "u_dp3",
         "assignee_id": "u_dp3", "actionable": True, "ir": ir("ir-2")},
    ]
    reports = [{
        "report_id": "rep-1", "case_id": "case-own", "ir_id": "ir-1",
        "url": "https://example.test/reports/ir-1.md",
        "published_at": "2026-10-19T00:00:00Z",
    }]
    repo = InMemoryRepository(
        cases=cases, reports=reports,
        rules=[{"rule_id": "R-1", "version": "rules-v1"}],
        control_points=[{"control_code": "H01", "judge_type": "literal"}],
        routing=[{"control_code": "H01", "owner": "dp3"}],
        notifications=[{"notification_id": "n-1", "recipient": "u_sub",
                        "type": "formal_submit", "unread": True}],
        metrics={"cases": 2},
        appeals=[], release_pending=[], takedown_tasks=[],
        signer_grants=[], takedown_grants=[], sessions=[],
        release_readiness={"case-own": {"ready": True}},
    )
    principals = {
        "u_sub": {"roles": ["submitter"], "product_lines": ["pump"]},
        "u_dp3": {"roles": ["coordinator"], "product_lines": ["pump"]},
        "u_it": {"roles": ["it"], "product_lines": ["pump"]},
    }

    store = SessionStore(":memory:")
    sub = store.create_session("u_sub", tenant="t1", now=time.time())
    coord = store.create_session("u_dp3", tenant="t1", now=time.time())
    it = store.create_session("u_it", tenant="t1", now=time.time())
    app = create_app(session_store=store, repository=repo, principals=principals)

    # C0/R3/R4 OpenAPI 3.1 + Appendix B 全端点
    spec = app.openapi()
    report(str(spec.get("openapi", "")).startswith("3.1"),
           "C0/R3 OpenAPI 版本为 3.1", repr(spec.get("openapi")))
    paths = spec.get("paths") or {}
    missing = []
    for method, path in sorted(expected_endpoints()):
        item = paths.get(path)
        if not item or method.lower() not in item:
            missing.append("%s %s" % (method, path))
    report(not missing, "C0/R4 UIUX Appendix B 端点全部存在",
           "missing=%r" % (missing[:8],))

    # C1 Pydantic 模型与 ReviewIR 契约对齐
    schema = json.loads(open(IR_SCHEMA, encoding="utf-8").read())
    pyd = (spec.get("components", {}).get("schemas", {})
           .get("ReviewIR", {}))
    report(set(schema["required"]) <= set(pyd.get("required") or []),
           "C1 ReviewIR Pydantic 必填字段与契约对齐",
           "contract=%r pyd=%r" % (sorted(schema["required"]),
                                   sorted(pyd.get("required") or [])))

    # C2 鉴权
    st, body = call(app, "GET", "/api/v1/cases")
    report(st == 401, "C2/R2 无 session → 401", "%s %r" % (st, body))
    st, body = call(app, "GET", "/api/v1/cases", cookie=sub)
    report(st == 200 and isinstance(body, list) and len(body) == 1,
           "C2 提交人只看到自己可读案件", "%s %r" % (st, body))
    st, _ = call(app, "GET", "/api/v1/cases/case-other", cookie=sub)
    report(st == 403, "C2 越权读他人案件 → 403", str(st))
    st, _ = call(app, "GET", "/api/v1/cases/case-own", cookie=it)
    report(st == 403, "C2 IT 读内容 → 403", str(st))
    st, _ = call(app, "GET", "/api/v1/cases/case-own", cookie=coord)
    report(st == 200, "C2 统筹读租户内案件 → 200", str(st))
    st, _ = call(app, "GET", "/api/v1/reports/rep-1", cookie=it)
    report(st == 403, "C2 IT 读报告 → 403", str(st))

    # C3 /metrics 内部
    st, _ = call(app, "GET", "/metrics", cookie=sub)
    report(st == 403, "C3 非内部角色读 /metrics → 403", str(st))
    st, body = call(app, "GET", "/metrics", cookie=coord)
    report(st == 200 and body.get("cases") == 2,
           "C3 内部角色读 /metrics → 200", "%s %r" % (st, body))

    # C4 /unclaim 存在（501 占位）
    st, body = call(app, "POST", "/api/v1/cases/case-own/unclaim",
                    cookie=sub, body=b"{}")
    report(st in (422, 501), "C4 /unclaim 写端点存在（实现后 422/占位 501）",
           "%s %r" % (st, body))


    # C6 通知可见性：只能看到发给自己的（P0 回归 —— 曾经任何人都能拿到全部）
    #
    # ★ 这条断言的由来：过滤字段曾写成 `principal`，而记录里叫 `recipient`。
    #   该字段恒不存在 → `None in (None, uid)` 恒真 → 全员可见。
    #   正样本（自己拿得到）与负样本（别人拿不到）必须成对，
    #   只有负样本的话，一个「全返回空」的实现也能过。
    st, body = call(app, "GET", "/api/v1/notifications", cookie=sub)
    mine = [n.get("notification_id") for n in (body or [])]
    report(st == 200 and "n-1" in mine,
           "C6 通知正样本：自己发的通知自己看得到", "%s %r" % (st, body))
    st, body = call(app, "GET", "/api/v1/notifications", cookie=coord)
    other = [n.get("notification_id") for n in (body or [])]
    report(st == 200 and "n-1" not in other,
           "C6 ★ 通知负样本：别人的通知看得到 = 越权", "%s %r" % (st, body))

    # C5 静态扫描：API 不 import/调用判定实现
    src = open(os.path.join(REPO_ROOT, "api", "review_api.py"),
               encoding="utf-8").read()
    forbidden = ["decision_table", "coverage_composer", "evidence_sync",
                 "semantic_judge", "rule_judge", "normalizer",
                 "orchestrator", "derive_state(", "decide("]
    leaked = [x for x in forbidden if x in src]
    report(not leaked, "C5/R1 API 层不含判定实现", repr(leaked))
    computed = [
        line for line in src.splitlines()
        if re.match(r"^\s*(state|decision|[a-z_]*_state)\s*=", line)
    ]
    report(not computed, "C5/R1 API 层不计算 state/decision", repr(computed[:3]))
    report('ir["decision"]["state"]' in src or "ir.decision.state" in src,
           "C5 状态从已落盘 IR 读，不计算", "")

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
        if tb and os.path.basename(tb[-1].filename) == "review_api.py":
            print("FAIL: review_api 抛异常: %s: %s"
                  % (type(exc).__name__, exc), file=sys.stderr)
            sys.exit(1)
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
