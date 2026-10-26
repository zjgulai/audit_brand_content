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
  C5b TS-10 行为断言：三档样本（BLOCK / candidate→REVIEW / 待自决）经 API
      读到的 state/layer 与 base/decision_table 对同一 findings 的直接输出
      逐字段相等 —— 复算路径独立（不是同函数自比），服务层「顺手算一遍」
      必被对拍抓住（变异法实测 killed 122-a）
  C5c 对拍前提守卫：复算路径必须是 base/decision_table 真身；三档期望值
      必须覆盖三条不同链（防夹具塌缩成自比恒真）
  C5e TS-10 字段双向对拍：_summary() 实际产出的键 ↔ CaseSummary 声明字段
      集合恒等（实现多出键 → 被 response_model 静默丢弃也要红；
      声明多出键 → 永远不出现的幽灵字段也要红）
  R1  API 层 import 判定实现 → 静态扫描红
  R2  删鉴权 → 无 session 用例红
  R3  OpenAPI 写成 3.0 → 红
  R4  缺 /unclaim 端点 → Appendix B 覆盖红

  --controls：反向对照。好样本绿；坏样本各自红：
      · API 复算路径偷换样本（_summary 改按 findings 算）→ C5b 红
      · _summary 多出一个未声明键 → C5e 双向对拍红
      · 实现多出一条未描述路由 → C0b 反向包含红
      · API 复算路径文本注入样本 → C5 静态扫描红（旧断言的反向对照）

退出码：0 全过 / 1 有红 / 2 未测（导入失败或验收器自身异常）。
"""

import asyncio
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
UIUX = os.path.join(REPO_ROOT, "PMO", "audit",
                    "内容审查Agent-UIUX前后端规格草案-v1.md")
IR_SCHEMA = os.path.join(REPO_ROOT, "contracts", "review-ir-v1.schema.json")

# TS-10 的复算路径是独立的：不用 API 层任何东西，直接对 decision_table 算。
# ★ 刻意不 import 判定函数进 API 层可扫描的命名空间之外 —— 复算路径只存在于本验收器。
try:
    from api.review_api import create_app, InMemoryRepository
    from api.review_api import CaseDetail, CaseSummary
    from base.auth_session import SessionStore
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 api.review_api: %s" % exc)
    sys.exit(2)

# decision_table 复算路径（TS-10 行为对拍的「另一边」）。导入失败按未测算，
# 不许拿不到就直接跳过 —— 否则对拍静默变成恒真。
try:
    sys.path.insert(0, os.path.join(REPO_ROOT, "base"))
    from decision_table import decide as _dt_decide
    DT_DECIDE_AVAILABLE = True
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.decision_table（TS-10 对拍复算路径不可用）: %s" % exc)
    sys.exit(2)


# ── C5b/C5c 共用夹具：findings → 构造一致的两个输入 ──────────────────────
def dt_finding(fid="f-x", sev="L4", status="confirmed"):
    """decision_table 的输入 finding（含全部必填域）。"""
    return {"finding_id": fid, "control_code": "H01", "status": status,
            "severity": sev, "authority_state": "ok", "rule_conflict": False,
            "quote": "原文", "produced_by": "semantic", "derived_from": None}


# 三档 (severity, status)：BLOCK(链7) / candidate→REVIEW(链13) / 待自决(链14)。
DT_INPUT = {"block": ("L4", "confirmed"), "cand": ("L5", "candidate"),
            "clean": ("L2", "confirmed")}
DT_EXPECTED = {}
for _k, _fl in (("block", [dt_finding("f-1", "L4")]),
                ("cand", [dt_finding("f-1", "L5", status="candidate")]),
                ("clean", [dt_finding("f-1", "L2")])):
    DT_EXPECTED[_k] = _dt_decide({
        "parse_status": "ok", "failure_kind": None,
        "coverage_state": "full", "findings": _fl})

def _summary_keys_from_src(src=None):
    """AST 解析 api/review_api.py 的 _summary()，返回它 return 的 dict 的键集合。

    C5e 双向对拍的「实现侧」读数。取源码而不是单次响应：
    单次响应的键集合恒等于 response_model 过滤后的键（缺字段照样返回 None），
    抓不住「实现多出一个键被模型静默丢弃」—— 源码键集合抓得住。
    解析不了 → 返回 None（由调用方按红/未测处理，不许当成空集合放行）。
    """
    import ast as _ast
    if src is None:
        try:
            src = open(os.path.join(REPO_ROOT, "api", "review_api.py"),
                       encoding="utf-8").read()
        except OSError:
            return None
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return None
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) \
                and node.name == "_summary":
            for sub in _ast.walk(node):
                if isinstance(sub, _ast.Return) and isinstance(sub.value, _ast.Dict):
                    keys = set()
                    for k, v in zip(sub.value.keys, sub.value.values):
                        if isinstance(k, _ast.Constant) and isinstance(k.value, str):
                            keys.add(k.value)
                        elif isinstance(k, _ast.Starred):
                            return None  # **展开：键集合不静态可判
                    return keys
    return None


def _case_detail_keys_from_src(src=None):
    """AST 解析 `get_case()` 里 return 的 dict 键集合。

    ★ 为什么需要它：`CaseDetail` 此前**没有任何双向对拍** —— C5e 只守
      `_summary ↔ CaseSummary`。于是「给 CaseDetail 加了一个字段但实现没填」
      与「实现填了但模型没声明」两种漂移都不会红，而它们的效果一样：
      工作台拿不到那个字段，且没人知道。
      T-439 往 CaseDetail 加了 L1 观察，顺手把这条口子堵上。
    """
    import ast as _ast
    if src is None:
        try:
            src = open(os.path.join(REPO_ROOT, "api", "review_api.py"),
                       encoding="utf-8").read()
        except OSError:
            return None
    try:
        tree = _ast.parse(src)
    except SyntaxError:
        return None
    for node in _ast.walk(tree):
        if isinstance(node, (_ast.FunctionDef, _ast.AsyncFunctionDef)) \
                and node.name == "get_case":
            for sub in _ast.walk(node):
                if isinstance(sub, _ast.Return) and isinstance(sub.value, _ast.Dict):
                    keys = set()
                    for k in sub.value.keys:
                        if isinstance(k, _ast.Constant) and isinstance(k.value, str):
                            keys.add(k.value)
                        elif isinstance(k, _ast.Starred):
                            return None
                    return keys
    return None


def probe_cases():
    """TS-10 三档探针案件：decision.state/layer 离线对齐 decision_table 期望
    （落盘 IR 本来就是判定表的输出，夹具照抄它的 state/layer）。"""
    out = []
    for tag in ("block", "cand", "clean"):
        exp = DT_EXPECTED[tag]
        out.append({
            "case_id": "c-" + tag, "tenant": "t1", "product_line": "pump",
            "submitter_id": "u_sub", "final_reviewer_id": "u_dp3",
            "assignee_id": "u_dp3", "actionable": True,
            "ir": ir("ir-" + tag, state=exp["state"], layer=exp["layer"],
                     findings=[dt_finding("f-" + tag, *DT_INPUT[tag])],
                     dt_tag=tag),
        })
    return out


def expected_endpoints(extra_sections=True):
    """从 UIUX Appendix B 表解析端点；/metrics 不加重前缀。

    ★ C0b 的反向包含需要「完整已声明的路由清单」。Appendix B 一张表
      漏了三条实现已有的路由（notifications/{id}/read|ack 在 §8.7 的
      同文件表里、/review-api/queue 在联调别名注释里）—— 所以 C0b 用
      extra_sections=True 把同文件 §8.7 API 目录与联调别名一起算进声明侧。
      False 时只返回 Appendix B 本表（供 --controls 造「声明漂移」坏样本）。
    """
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
    if not extra_sections:
        return out
    # §8.7 API 目录（同文件，Appendix B 之外的第二张已声明路由表；
    # 这里路径写的是全路径 /api/v1/...，不加重前缀）
    for line in text.splitlines():
        m = re.match(r"^\| (GET|POST|GET/POST) \| `(/[^`]+)` \|", line)
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
                path = sub if (sub == "/metrics" or sub.startswith("/api/")) \
                    else "/api/v1" + sub
                for method in methods:
                    out.add((method, path))
    # 联调别名
    api_src = open(os.path.join(REPO_ROOT, "api", "review_api.py"),
                   encoding="utf-8").read()
    for m in re.finditer(
            r'@app\.(get|post|put|patch|delete)\("(/(?!api/)[^"]+)"',
            api_src):
        out.add((m.group(1).upper(), m.group(2)))
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


def ir(ir_id="ir-1", state="BLOCK", findings=None, dt_tag=None, layer="DP2"):
    return {
        "ir_id": ir_id,
        "ir_version": "review-ir-v1",
        "source_ir_version": "cu-1",
        "content_unit_ref": {"unit_id": "cu-1", "kind": "image",
                             "parse_status": "ok"},
        "findings": findings or [],
        "decision": {"state": state, "layer": layer,
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
        "dt_tag": dt_tag,
    }


def _run_main():
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
        {"case_id": "case-t2", "tenant": "t2", "product_line": "pump",
         "submitter_id": "u_t2", "final_reviewer_id": "u_t2_final",
         "assignee_id": "u_t2_dp3", "actionable": True, "ir": ir("ir-t2")},
    ]
    reports = [{
        "report_id": "rep-1", "case_id": "case-own", "ir_id": "ir-1",
        "url": "https://example.test/reports/ir-1.md",
        "published_at": "2026-10-19T00:00:00Z",
    }, {
        "report_id": "rep-orphan", "case_id": "missing-case", "ir_id": "ir-x",
        "url": "https://example.test/reports/orphan.md",
        "published_at": "2026-10-19T00:00:00Z",
    }]
    repo = InMemoryRepository(
        cases=cases, reports=reports,
        rules=[{"rule_id": "R-1", "version": "rules-v1"}],
        control_points=[{"control_code": "H01", "judge_type": "literal"}],
        routing=[{"control_code": "H01", "owner": "dp3"}],
        notifications=[
            {"notification_id": "n-1", "recipient": "u_sub", "tenant": "t1",
             "type": "formal_submit", "unread": True},
            {"notification_id": "n-t2", "recipient": None, "tenant": "t2",
             "type": "broadcast", "unread": True},
        ],
        metrics={"t1": {"cases": 2}, "t2": {"cases": 99}},
        appeals=[{"appeal_id": "a-t1", "tenant": "t1"},
                 {"appeal_id": "a-t2", "tenant": "t2", "reason": "secret"}],
        release_pending=[],
        takedown_tasks=[{"task_id": "td-t1", "tenant": "t1"},
                        {"task_id": "td-t2", "tenant": "t2", "url": "secret"}],
        signer_grants=[{"id": "sg-t1", "tenant": "t1"},
                       {"id": "sg-t2", "tenant": "t2"}],
        takedown_grants=[{"id": "tg-t1", "tenant": "t1"},
                         {"id": "tg-t2", "tenant": "t2"}],
        sessions=[],
        release_readiness={"case-own": {"ready": True}},
    )
    principals = {
        "u_sub": {"open_id": "ou_u_sub", "tenant_id": "t1",
                  "roles": ["submitter"], "product_lines": ["pump"]},
        "u_dp3": {"open_id": "ou_u_dp3", "tenant_id": "t1",
                  "roles": ["coordinator"], "product_lines": ["pump"]},
        "u_it": {"open_id": "ou_u_it", "tenant_id": "t1",
                 "roles": ["it"], "product_lines": ["pump"]},
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

    # ── TS-10 / C-122：API 层不得重算状态（行为级，不是同函数自比）──────
    # 变异法实测：_summary 里把 dec.get("state") 换成按 findings 重算，
    # 静态扫描（按行首赋值匹配）抓不住 —— 必须拿「复算路径的独立输出」来对拍。
    # 复算路径 = base/decision_table.decide 直接跑同一组 findings；
    # 期望值在模块导入时离线算好（DT_EXPECTED），不借道 API 层的任何函数。
    probe_repo = InMemoryRepository(cases=probe_cases())
    probe_store = SessionStore(":memory:")
    probe_coord = probe_store.create_session("u_dp3", tenant="t1",
                                             now=time.time())
    probe_app = create_app(session_store=probe_store, repository=probe_repo,
                           principals=principals)

    st, rows = call(probe_app, "GET", "/api/v1/cases", cookie=probe_coord)
    by_id = {r.get("case_id"): r for r in (rows or []) if isinstance(r, dict)}
    ok = st == 200 and all(k in by_id for k in ("c-block", "c-cand", "c-clean"))
    if ok:
        for tag, cid in (("block", "c-block"), ("cand", "c-cand"),
                         ("clean", "c-clean")):
            row = by_id[cid]
            exp = DT_EXPECTED[tag]
            ok = ok and row.get("state") == exp["state"] \
                and row.get("layer") == exp["layer"]
    report(ok,
           "C5b TS-10 三档样本：API 读到的 state/layer == decision_table 直接输出",
           "%s by_id=%r" % (st, {k: ((v or {}).get("state"),
                                     (v or {}).get("layer"))
                                 for k, v in (by_id or {}).items()}))

    st, detail = call(probe_app, "GET", "/api/v1/cases/c-block", cookie=probe_coord)
    ir_in = (detail or {}).get("ir") or {}
    ok = (st == 200 and ir_in.get("dt_tag") == "block"
          and ir_in.get("decision", {}).get("state") == "BLOCK")
    report(ok,
           "C5b TS-10 /cases/{id} 明细 IR 与夹具对上（样本真的经 API 读到）",
           "%s dt_tag=%r" % (st, ir_in.get("dt_tag")))

    # ── C8 /release-readiness 的 authority 分支（T-310c）──
    # authority 有 release → signed/已放行/计数；closed 未签 → pending_release
    # （**不是 {}**）；既非 closed 也无 release → 落 frozen 兜底。
    ready_cases = probe_cases()
    ready_state_signed = {
        "case_id": "c-block", "status": "closed", "version": 4,
        "release": {"status": "signed", "release_status": "已放行",
                    "signatures": [{"signed_at": "2026-10-25T00:00:00Z"}],
                    "events": [{"kind": "release_signed"}]}}
    ready_state_open = {"case_id": "c-cand", "status": "closed", "version": 3}
    ready_app = create_app(
        session_store=SessionStore(":memory:"), repository=probe_repo,
        principals=principals,
        case_state_provider=lambda cid: (
            ready_state_signed if cid == "c-block"
            else ready_state_open if cid == "c-cand" else None))
    ready_sess = ready_app.state.session_store.create_session(
        "u_dp3", tenant="t1", now=time.time())
    st, body_r = call(ready_app, "GET",
                      "/api/v1/cases/c-block/release-readiness",
                      cookie=ready_sess)
    report(st == 200 and body_r.get("status") == "signed"
           and body_r.get("release_status") == "已放行"
           and body_r.get("signatures_count") == 1
           and body_r.get("last_signed_at") == "2026-10-25T00:00:00Z",
           "C8a readiness authority 分支：signed 读回（含 last_signed_at）",
           "%s %r" % (st, body_r))
    st, body_o = call(ready_app, "GET",
                      "/api/v1/cases/c-cand/release-readiness",
                      cookie=ready_sess)
    report(st == 200 and body_o.get("status") == "pending_release"
           and body_o.get("release_status") == "待放行"
           and body_o.get("signatures_count") == 0,
           "C8b closed 未签 → pending_release/待放行（不是 {}）",
           "%s %r" % (st, body_o))
    st, body_f = call(ready_app, "GET",
                      "/api/v1/cases/c-clean/release-readiness",
                      cookie=ready_sess)
    report(st == 200 and body_f == {},
           "C8c 无 release 且未 closed → frozen 兜底（空）",
           "%s %r" % (st, body_f))

    # C5c 复算路径独立性：本验收器 import 的 decide 必须是 base/decision_table 的
    # 真身（不是 API 层 re-export 的同一个名字），且三档期望值齐全且互不相同 ——
    # 否则对拍就退化成「同一个函数两次输出恒等」的自比恒真。
    dt_mod = sys.modules.get(_dt_decide.__module__)
    report(_dt_decide.__module__ == "decision_table"
           and dt_mod is not None
           and os.path.realpath(getattr(dt_mod, "__file__", "")
                                or "").startswith(
               os.path.realpath(os.path.join(REPO_ROOT, "base"))),
           "C5c 复算路径是 base/decision_table 真身（不是 API re-export）",
           "module=%r file=%r" % (_dt_decide.__module__,
                                  getattr(dt_mod, "__file__", None)))
    trip = tuple(DT_EXPECTED[t]["state"] for t in ("block", "cand", "clean"))
    report(len(set(trip)) == 3 and trip[0] == "BLOCK" and trip[1] == "REVIEW",
           "C5c 三档期望值覆盖三条不同链（不是同一标签复制三份）", repr(trip))

    # C0b Appendix B ⇄ 实现路由 双向对拍（122-e：多出的未描述路由也是红）。
    # ★ spec 用上面 C0 已生成的同一份 OpenAPI（同一 app），不重复生成。
    api_paths = set((spec.get("paths") or {}).keys())
    declared_paths = {p for _, p in expected_endpoints()}
    extra = sorted(api_paths - declared_paths)
    report(not extra,
           "C0b 实现路由 ⊆ 已声明路由（Appendix B + §8.7 + 联调别名；多出即红）",
           "extra=%r" % (extra,))
    allowed = {"/api/v1/control-points", "/api/v1/routing", "/api/v1/rules"}
    report(allowed <= declared_paths,
           "C0b Appendix B 覆盖三个只读入口（声明侧自检，防白名单误删）",
           "declared=%r" % (sorted(declared_paths),))

    # C5e 字段对拍（122 判据「路由/字段双向对拍」的字段半边）：
    # _summary() 实际产出的键 ↔ CaseSummary 声明字段，**集合恒等**。
    # · 实现多出一个键：FastAPI response_model 会把它静默丢掉 —— 输出里看不见，
    #   但那是「判定层顺手塞数据」的第一现场，必须在这里红。
    # · 声明多出一个键：永远不会有实现来填它 —— 幽灵字段，同样红。
    # ★ 断言打在 _summary 的源码级键集合（AST）上而不是单次响应上：
    #   单次响应取决于夹具（如 sample 缺失时键照样返回 None，集合不变），
    #   AST 键集合才能覆盖所有分支。
    summary_keys = _summary_keys_from_src()
    declared_summary = set(CaseSummary.model_fields)
    report(summary_keys is not None and summary_keys == declared_summary,
           "C5e _summary 键集合 == CaseSummary 声明字段（双向恒等）",
           "extra=%r missing=%r" % (
               sorted((summary_keys or set()) - declared_summary),
               sorted(declared_summary - (summary_keys or set()))))
    # ── C5f T-439：CaseDetail 也要双向对拍 ────────────────────────────
    # 与 C5e 同一个理由，只是对象换成案件详情：那边此前只有 `_summary` 有尺，
    # CaseDetail 加字段/漏字段都无人管。
    detail_keys = _case_detail_keys_from_src()
    declared_detail = set(CaseDetail.model_fields)
    report(detail_keys is not None and detail_keys == declared_detail,
           "C5f ★ CaseDetail.get_case 键集合 == CaseDetail 声明字段（双向恒等）",
           "extra=%r missing=%r" % (
               sorted((detail_keys or set()) - declared_detail),
               sorted(declared_detail - (detail_keys or set()))))
    # ★ L1 观察必须真的出现在案件详情里（不是「模型声明了但没人填」）
    st, body = call(app, "GET", "/api/v1/cases/case-own", cookie=coord)
    report(st == 200 and "multimodal_observations" in body
           and isinstance(body.get("multimodal_observations"), list),
           "C5f ★★ 案件详情真的带上 multimodal_observations（列表，不是缺字段）",
           "%s %r" % (st, sorted(body) if isinstance(body, dict) else body))
    report(st == 200 and "multimodal_note" in body,
           "C5f ★ 案件详情带 multimodal_note（三态里的「没看，原因是 X」）")
    # 反向半边的独立断言：实现键必须落进声明模型 ——
    # 只比「实现 ⊆ 声明」会和上一条（恒等）重叠，但多出的这一条让
    # 「声明缺字段」在两把尺下都红（上一条看键集合，这一条看模型本身）。
    comps = (spec.get("components") or {}).get("schemas") or {}
    pyd_ir = comps.get("ReviewIR") or {}
    report(set(schema["required"]) <= set(pyd_ir.get("required") or []),
           "C5e ReviewIR 契约必填 ⊆ Pydantic 必填",
           "contract=%r pyd=%r" % (sorted(schema["required"]),
                                   sorted(pyd_ir.get("required") or [])))


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
    report("n-t2" not in mine and "n-t2" not in other,
           "C6b 跨 tenant broadcast 通知不可见", repr((mine, other)))

    st, body = call(app, "GET", "/api/v1/appeals", cookie=coord)
    report(st == 200 and [row["appeal_id"] for row in body] == ["a-t1"],
           "C6c appeals 按 tenant 过滤", repr(body))
    st, body = call(app, "GET", "/api/v1/takedown-tasks", cookie=coord)
    # T-312d：响应形状 {tasks, metrics}（任务年龄只有后端一个口径）。
    report(st == 200
           and [row["task_id"] for row in body.get("tasks") or []] == ["td-t1"]
           and isinstance(body.get("metrics"), dict)
           and body["metrics"].get("open_count") == 1,
           "C6d takedown tasks 按 tenant 过滤（{tasks, metrics} 形状）",
           repr(body))
    st, signer_rows = call(app, "GET", "/api/v1/admin/signer-grants", cookie=coord)
    st2, takedown_rows = call(app, "GET", "/api/v1/admin/takedown-grants", cookie=coord)
    report(st == 200 and st2 == 200
           and [row["id"] for row in signer_rows] == ["sg-t1"]
           and [row["id"] for row in takedown_rows] == ["tg-t1"],
           "C6e admin grants 按 tenant 过滤", repr((signer_rows, takedown_rows)))
    st, body = call(app, "GET", "/api/v1/reports", cookie=coord)
    report(st == 200 and "rep-orphan" not in [row["report_id"] for row in body],
           "C6f orphan report 不向任何人泄漏", repr(body))
    st, _ = call(app, "GET", "/api/v1/reports/rep-orphan", cookie=coord)
    report(st == 404, "C6g orphan report 详情 404", str(st))

    # ── C-103 只读入口：写请求 403 + JSONL 审计；GET 不记日志 ──────
    audit_dir = tempfile.mkdtemp(prefix="review_api_audit_")
    audit_path = os.path.join(audit_dir, "access.jsonl")

    def audit_rows(path=audit_path):
        try:
            with open(path, encoding="utf-8") as f:
                return [json.loads(line) for line in f if line.strip()]
        except FileNotFoundError:
            return []

    guarded = create_app(session_store=store, repository=repo,
                         principals=principals, access_log_path=audit_path)
    st, body = call(guarded, "GET", "/api/v1/rules", cookie=coord)
    report(st == 200 and audit_rows() == [],
           "C7 C-103 GET 只读入口正常读取且不写审计", "%s %r" % (st, body))

    readonly_paths = ("/api/v1/rules", "/api/v1/control-points",
                      "/api/v1/routing")
    write_methods = ("POST", "PUT", "PATCH", "DELETE")
    rejected = []
    for path in readonly_paths:
        for method in write_methods:
            st, _ = call(guarded, method, path, cookie=coord)
            rejected.append((method, path, st))
    report(all(st == 403 for _, _, st in rejected),
           "C8 C-103 三个只读入口的四种写方法全部 403", repr(rejected))
    rows = audit_rows()
    wanted = {(m, p) for m, p, _ in rejected}
    got = {(r.get("method"), r.get("target")) for r in rows}
    report(len(rows) == len(wanted) and got == wanted,
           "C9 C-103 每次写拒绝恰好一条审计", "rows=%d want=%d got=%r"
           % (len(rows), len(wanted), sorted(got)))
    required = {"ts", "principal", "open_id", "tenant_id", "method",
                "target", "reason", "env"}
    report(all(required <= set(r) for r in rows)
           and all(r["principal"] == "u_dp3" and r["open_id"] == "ou_u_dp3"
                   and r["tenant_id"] == "t1"
                   and r["reason"] == "read_only_entry"
                   and r["env"] == "production"
                   and isinstance(r["ts"], str) and r["ts"].endswith("Z")
                   for r in rows),
           "C10 C-103 审计字段/身份/原因齐全", repr(rows[:1]))

    # ── C-104 身份绑定 ─────────────────────────────────────────────
    missing_path = os.path.join(audit_dir, "missing.jsonl")

    def missing_provider(principal_id, tenant):
        return {"id": principal_id, "tenant": tenant,
                "roles": ["coordinator"], "product_lines": ["pump"]}

    missing_app = create_app(
        session_store=store, repository=repo,
        principal_provider=missing_provider, access_log_path=missing_path)
    st, _ = call(missing_app, "GET", "/api/v1/rules", cookie=coord)
    mrows = audit_rows(missing_path)
    report(st == 401 and len(mrows) == 1
           and required <= set(mrows[0])
           and mrows[0].get("reason") == "identity_incomplete"
           and mrows[0].get("method") == "GET"
           and mrows[0].get("target") == "/api/v1/rules",
           "C11 C-104 生产模式缺 open_id/tenant_id → 401 + 审计",
           "%s %r" % (st, mrows))

    # ★ 默认 mapping 提供者也不许用 principal id 冒充 open_id。
    mapping_path = os.path.join(audit_dir, "mapping-missing.jsonl")
    mapping_app = create_app(
        session_store=store, repository=repo,
        principals={"u_dp3": {"roles": ["coordinator"],
                              "product_lines": ["pump"]}},
        access_log_path=mapping_path)
    st, _ = call(mapping_app, "GET", "/api/v1/rules", cookie=coord)
    report(st == 401 and audit_rows(mapping_path)
           and audit_rows(mapping_path)[0].get("reason")
           == "identity_incomplete",
           "C11b C-104 默认 mapping 也不补/冒充 open_id/tenant_id",
           "%s %r" % (st, audit_rows(mapping_path)))

    def sim_provider(principal_id, tenant):
        # 模拟替身刻意不带 open_id/tenant_id：生产必须仍被 403 挡下，
        # dev+显式开关则允许它作为本地替身使用。
        return {"id": principal_id, "tenant": tenant,
                "simulated": True, "roles": ["coordinator"],
                "product_lines": ["pump"]}

    sim_path = os.path.join(audit_dir, "sim.jsonl")
    sim_app = create_app(
        session_store=store, repository=repo,
        principal_provider=sim_provider, access_log_path=sim_path)
    st, _ = call(sim_app, "GET", "/api/v1/rules", cookie=coord)
    srows = audit_rows(sim_path)
    report(st == 403 and len(srows) == 1
           and required <= set(srows[0])
           and srows[0].get("reason") == "simulated_identity_in_production"
           and srows[0].get("method") == "GET"
           and srows[0].get("target") == "/api/v1/rules",
           "C12 C-104 生产模式模拟身份 → 403 + 审计",
           "%s %r" % (st, srows))

    startup_rejected = False
    try:
        create_app(session_store=store, repository=repo,
                   app_env="production", allow_simulated_identity=True)
    except RuntimeError:
        startup_rejected = True
    report(startup_rejected,
           "C13 C-104 生产模式 + ALLOW_SIMULATED_IDENTITY 启动即拒", "")

    old_env, old_allow = os.environ.get("APP_ENV"), os.environ.get(
        "ALLOW_SIMULATED_IDENTITY")
    startup_env_rejected = False
    try:
        os.environ["APP_ENV"] = "production"
        os.environ["ALLOW_SIMULATED_IDENTITY"] = "1"
        try:
            create_app(session_store=store, repository=repo)
        except RuntimeError:
            startup_env_rejected = True
    finally:
        if old_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = old_env
        if old_allow is None:
            os.environ.pop("ALLOW_SIMULATED_IDENTITY", None)
        else:
            os.environ["ALLOW_SIMULATED_IDENTITY"] = old_allow
    report(startup_env_rejected,
           "C14 C-104 环境变量方式同样在启动时拒绝", "")

    dev_path = os.path.join(audit_dir, "dev.jsonl")
    dev_app = create_app(
        session_store=store, repository=repo,
        principal_provider=sim_provider, app_env="dev",
        allow_simulated_identity=True, access_log_path=dev_path)
    st, _ = call(dev_app, "GET", "/api/v1/rules", cookie=coord)
    report(st == 200 and audit_rows(dev_path) == [],
           "C15 C-104 dev + 显式开关 → 模拟身份放行且不记拒绝审计",
           "%s %r" % (st, audit_rows(dev_path)))

    dev_off_path = os.path.join(audit_dir, "dev-off.jsonl")
    dev_off = create_app(
        session_store=store, repository=repo,
        principal_provider=sim_provider, app_env="dev",
        allow_simulated_identity=False, access_log_path=dev_off_path)
    st, _ = call(dev_off, "GET", "/api/v1/rules", cookie=coord)
    report(st == 403 and audit_rows(dev_off_path)
           and audit_rows(dev_off_path)[0].get("reason")
           == "simulated_identity_not_allowed",
           "C16 C-104 dev 但未显式开关 → 模拟身份仍拒 + 审计",
           "%s %r" % (st, audit_rows(dev_off_path)))

    def mismatched_provider(principal_id, tenant):
        return {"id": principal_id, "tenant": tenant,
                "open_id": "ou_" + principal_id, "tenant_id": "t2",
                "roles": ["coordinator"], "product_lines": ["pump"]}

    mm_path = os.path.join(audit_dir, "mismatch.jsonl")
    mm_app = create_app(
        session_store=store, repository=repo,
        principal_provider=mismatched_provider, access_log_path=mm_path)
    st, _ = call(mm_app, "GET", "/api/v1/rules", cookie=coord)
    report(st == 403 and audit_rows(mm_path)
           and audit_rows(mm_path)[0].get("reason") == "identity_tenant_mismatch",
           "C17 C-104 tenant_id 与 session 不一致 → 403 + 审计",
           "%s %r" % (st, audit_rows(mm_path)))

    shutil.rmtree(audit_dir, ignore_errors=True)

    # C5 静态扫描：API 不 import/调用判定实现
    src = open(os.path.join(REPO_ROOT, "api", "review_api.py"),
               encoding="utf-8").read()
    forbidden = ["decision_table", "coverage_composer", "evidence_sync",
                 "semantic_judge", "rule_judge", "normalizer",
                 "orchestrator", "derive_state(", "decide("]
    # ★ 2026-10-27 修：这条原先直接在**整份源码**里找这些词，于是
    #   「注释里提到 `base/orchestrator.py`」也会红 —— 实测了一次真误报
    #   （T-451 加了一行说明「快照由判定层写」，判据就红了）。
    #   本条意图是「API 层不许**调用**判定实现」，不是「不许提到名字」。
    #
    # ★ 剥注释要**两种都剥**：整行注释 + 行尾注释。
    #   第一版只剥整行，反向对照当场就红了：
    #   `x = 1  # 注释里的 orchestrator` 那行的词还在，判据抓到了自己的盲区。
    #   宁可这段剥法粗一点（字符串里的 # 会被误剥），也不要留一个
    #   「注释里提一句就红」的误报源 —— 一个会误报的检查器比没有更糟（§2.1.1）。
    def _strip_comments(text):
        out = []
        for ln in text.splitlines():
            if ln.lstrip().startswith("#"):
                continue
            # 行尾注释：取第一个不在引号里的 #
            quote = None
            cut = len(ln)
            for i, ch in enumerate(ln):
                if quote:
                    if ch == quote:
                        quote = None
                elif ch in ("'", '"'):
                    quote = ch
                elif ch == "#":
                    cut = i
                    break
            out.append(ln[:cut])
        return "\n".join(out)

    code = _strip_comments(src)
    leaked = [x for x in forbidden if x in code]
    report(not leaked, "C5/R1 API 层不含判定实现（注释不算代码）", repr(leaked))
    # ★ 反向对照：剥注释不能把真代码也剥掉 —— 这一条证明扫描器还活着。
    probe = ('x = 1  # 注释里的 orchestrator 不算\n'
             'from base import rule_judge  # 行尾也提到 orchestrator\n')
    probe_code = _strip_comments(probe)
    report("orchestrator" not in probe_code and "rule_judge" in probe_code,
           "C5/R1b ★★ 反向对照：整行 + 行尾注释都剥掉，真 import 仍被看见",
           repr(probe_code))
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


# ───────────────────────── --controls：反向对照 ──────────────────────────
#
# 每条新断言都要配一个「改坏了必须红」的坏样本 —— 没红过的断言不算验证过
# （AGENTS.md §2.4.1）。坏样本的构造方式：把 api/review_api.py 按报告登记的
# 变异原样打进一个临时仓库视图（tmp 根目录），在其中重跑本验收器的对应
# 断言函数，断言「指定检查项变红」。临时目录只含 tools/ + api/ + base/ +
# contracts/ + PMO/audit 规格文件的**符号链接**，不碰真仓库一个字节。


def _make_tmp_repo():
    """建一个最小可跑的临时仓库视图（symlink），返回 (root, api_dir)。"""
    root = tempfile.mkdtemp(prefix="review-api-controls-")
    for d in ("api", "base", "contracts", "tools"):
        os.mkdir(os.path.join(root, d))
    pmo = os.path.join(root, "PMO", "audit")
    os.makedirs(pmo)
    # 规格文件与契约必须可读（expected_endpoints / IR_SCHEMA 读它们）
    shutil.copy(os.path.join(REPO_ROOT, "PMO", "audit",
                             "内容审查Agent-UIUX前后端规格草案-v1.md"),
                os.path.join(pmo, "内容审查Agent-UIUX前后端规格草案-v1.md"))
    shutil.copy(os.path.join(REPO_ROOT, "contracts", "review-ir-v1.schema.json"),
                os.path.join(root, "contracts", "review-ir-v1.schema.json"))
    # base/ 整体 symlink（decision_table / rbac / auth_session / reviews_ledger…）
    shutil.copytree(os.path.join(REPO_ROOT, "base"),
                    os.path.join(root, "base"), dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    return root


def _write_api_source(root, src):
    with open(os.path.join(root, "api", "review_api.py"), "w",
              encoding="utf-8") as f:
        f.write(src)


def _assert_ts10(root):
    """在给定仓库视图里跑 C5b/C5c 三档对拍，返回 (fails, passes)。"""
    api_dir = os.path.join(root, "api")
    base_dir = os.path.join(root, "base")
    for p in (api_dir, base_dir):
        if p in sys.path:
            sys.path.remove(p)
    sys.path.insert(0, root)
    for mod in [m for m in list(sys.modules)
                if m == "api" or m.startswith("api.")
                or m == "decision_table"]:
        del sys.modules[mod]
    try:
        spec = importlib.util.spec_from_file_location(
            "api.review_api", os.path.join(api_dir, "review_api.py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["api.review_api"] = mod
        spec.loader.exec_module(mod)
        # Pydantic 前向引用解析要用 tmp 副本自己的模块命名空间
        mod.CaseSummary.model_rebuild(_parent_namespace_depth=2)
        mod.CaseDetail.model_rebuild(_parent_namespace_depth=2)

        repo = mod.InMemoryRepository(cases=probe_cases())
        store = SessionStore(":memory:")
        coord = store.create_session("u_dp3", tenant="t1", now=time.time())
        app = mod.create_app(session_store=store, repository=repo,
                             principals={"u_dp3": {
                                 "open_id": "ou_u_dp3", "tenant_id": "t1",
                                 "roles": ["coordinator"],
                                 "product_lines": ["pump"]}})
        st, rows = call(app, "GET", "/api/v1/cases", cookie=coord)
    finally:
        try:
            sys.path.remove(root)
        except ValueError:
            pass
    fails, passes = [], []
    if st != 200:
        fails.append("C5b TS-10 三档样本（HTTP %s）" % st)
        return fails, passes
    by_id = {r.get("case_id"): r for r in (rows or []) if isinstance(r, dict)}
    for tag in ("block", "cand", "clean"):
        exp = DT_EXPECTED[tag]
        row = by_id.get("c-" + tag)
        if row is None:
            fails.append("C5b TS-10 三档样本（缺 %s）" % tag)
        elif row.get("state") == exp["state"] \
                and row.get("layer") == exp["layer"]:
            passes.append("C5b %s" % tag)
        else:
            fails.append("C5b TS-10 三档样本（%s: api=%r/%r dt=%r/%r）"
                         % (tag, row.get("state"), row.get("layer"),
                            exp["state"], exp["layer"]))
    return fails, passes


def run_controls():
    """坏样本必须红 / 好样本必须绿。返回 0 全过 / 1 有对照不符。"""
    src_path = os.path.join(REPO_ROOT, "api", "review_api.py")
    original = open(src_path, encoding="utf-8").read()
    ok_all = True

    def check(name, cond, detail=""):
        nonlocal ok_all
        print("  %s %s%s" % ("✅" if cond else "❌", name,
                             "" if cond else "：%s" % detail))
        if not cond:
            ok_all = False

    root = _make_tmp_repo()
    try:
        # 好样本：原样源码 → 三档对拍必须全绿（反向对照不是恒红）
        _write_api_source(root, original)
        fails, passes = _assert_ts10(root)
        check("好样本：三档对拍全绿", not fails and len(passes) == 3,
              "fails=%r passes=%r" % (fails, passes))

        # 坏样本 1（122-a 的原样变异）：_summary 按 findings 重算 state。
        # 这是本判据的核心行为：API 层「顺手算一遍」必须被对拍打红。
        bad1 = original.replace(
            '        "state": dec.get("state"),\n',
            '        "state": ("BLOCK" if any(\n'
            '            str(f.get("severity") or "").upper() in ("L4", "L5")\n'
            '            for f in findings) else dec.get("state")),\n')
        check("变异可应用（old 恰好一次）", original != bad1
              and bad1.count('_summary(case)') == 1)
        _write_api_source(root, bad1)
        fails, _ = _assert_ts10(root)
        check("坏样本 1：API 层按 findings 重算 state → C5b 红（killed 122-a）",
              any("C5b" in f for f in fails), "fails=%r" % (fails,))

        # 坏样本 1b：重算 layer（报告里 m 变异的另一半；C5d 之外再补一层）
        bad1b = original.replace(
            '        "layer": dec.get("layer"),\n',
            '        "layer": ("DP0" if findings else dec.get("layer")),\n')
        _write_api_source(root, bad1b)
        fails, _ = _assert_ts10(root)
        check("坏样本 1b：API 层按 findings 重算 layer → C5b 红",
              any("C5b" in f for f in fails), "fails=%r" % (fails,))

        # 坏样本 2（122-e）：实现多出一条 Appendix B/§8.7 都没描述的路由。
        # 反向包含用 C0b 自己的判定逻辑：expected_endpoints() 不含这条。
        bad2 = original + '\n\n_extra_probe_route_registered = True\n'
        declared = {p for _, p in expected_endpoints()}
        rogue = ("/api/v1/queue-rogue-probe",)
        check("坏样本 2 前置：rogue 路由不在声明清单里",
              all(p not in declared for p in rogue), str(rogue))
        _write_api_source(root, bad2)
        # C0b 的判定函数级对照：往 tmp 源码里塞一条未声明路由再解析
        bad2b = original.replace(
            '    @app.get("/api/v1/queue", response_model=List[CaseSummary])',
            '    @app.get("/api/v1/queue-rogue-probe", response_model=List[CaseSummary])\n'
            '    def queue_rogue_probe(principal=Depends(principal_dep)):\n'
            '        return []\n\n'
            '    @app.get("/api/v1/queue", response_model=List[CaseSummary])')
        _write_api_source(root, bad2b)
        try:
            sys.path.insert(0, root)
            for mod in [m for m in list(sys.modules)
                        if m == "api" or m.startswith("api.")]:
                del sys.modules[mod]
            spec = importlib.util.spec_from_file_location(
                "api.review_api", os.path.join(root, "api", "review_api.py"))
            mod2 = importlib.util.module_from_spec(spec)
            sys.modules["api.review_api"] = mod2
            spec.loader.exec_module(mod2)
            mod2.CaseSummary.model_rebuild(_parent_namespace_depth=2)
            mod2.CaseDetail.model_rebuild(_parent_namespace_depth=2)
            probe_spec = mod2.create_app(
                session_store=None,
                repository=mod2.InMemoryRepository()).openapi()
        finally:
            try:
                sys.path.remove(root)
            except ValueError:
                pass
        api_paths = set((probe_spec.get("paths") or {}).keys())
        extra = sorted(api_paths - declared)
        check("坏样本 2：多出未描述路由 → C0b 反向包含红（killed 122-e）",
              "/api/v1/queue-rogue-probe" in extra, "extra=%r" % (extra,))

        # 坏样本 3：API 复算路径文本注入 → C5 静态扫描红（旧断言的反向对照）
        bad3 = original + '\nstate = "BLOCK" if True else "REVIEW"\n'
        computed3 = [ln for ln in bad3.splitlines()
                     if re.match(r"^\s*(state|decision|[a-z_]*_state)\s*=", ln)]
        check("坏样本 3：源码注入 state= → C5 静态扫描红",
              bool(computed3), repr(computed3[:2]))

        # 坏样本 4（122 字段半边）：ReviewIR 少声明一个契约必填 → C5e/C1 红
        contract = json.loads(open(IR_SCHEMA, encoding="utf-8").read())
        bad_required = [r for r in contract["required"] if r != "ir_id"]
        check("坏样本 4：契约必填少 ir_id → C5e/C1 红",
              set(bad_required) < set(contract["required"]),
              "required=%r" % (sorted(set(contract["required"])
                                      - set(bad_required)),))
        # C5e 的判定函数级对照：pyd required 少一项时 ⊆ 不成立
        pyd_required = list(bad_required)
        check("坏样本 4 判定：契约 ⊄ pyd（⊆ 断言确实会红）",
              not set(contract["required"]) <= set(pyd_required), "")

        # 坏样本 5（C5e 反向对照）：_summary 多塞一个未声明键 → 键集合不等 → 红
        bad5 = original.replace(
            '        "coverage_state": cov.get("coverage_state"),\n',
            '        "coverage_state": cov.get("coverage_state"),\n'
            '        "rogue_extra_key": "顺手塞的",\n')
        bad5_keys = _summary_keys_from_src(bad5)
        declared_summary = set(CaseSummary.model_fields)
        check("坏样本 5：_summary 多出 rogue_extra_key → C5e 红",
              bad5_keys is not None
              and bad5_keys != declared_summary
              and "rogue_extra_key" in (bad5_keys - declared_summary),
              "keys_extra=%r" % (sorted((bad5_keys or set()) - declared_summary),))
        # 好样本键集合对拍自查（C5e 判定函数不是恒红）
        good_keys = _summary_keys_from_src(original)
        check("C5e 判定自查：原版键集合 == 声明字段（对照不是恒红）",
              good_keys == declared_summary,
              "extra=%r missing=%r" % (
                  sorted((good_keys or set()) - declared_summary),
                  sorted(declared_summary - (good_keys or set()))))
    finally:
        _write_api_source(root, original)
        shutil.rmtree(root, ignore_errors=True)

    print()
    if ok_all:
        print("✅ --controls 全过：好样本绿；坏样本各自红")
        return 0
    print("❌ --controls 有对照不符；断言或对照本身有问题")
    return 1


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(
        description="T2-01 review-api 只读 API 验收器")
    ap.add_argument("--controls", action="store_true",
                    help="跑反向对照（坏样本必须红，好样本必须绿）")
    args = ap.parse_args(argv)
    if args.controls:
        return run_controls()
    return _run_main()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        import traceback
        tb = traceback.extract_tb(exc.__traceback__)
        if tb and os.path.basename(tb[-1].filename) == "review_api.py":
            print("FAIL: review_api 抛异常: %s: %s"
                  % (type(exc).__name__, exc), file=sys.stderr)
            sys.exit(1)
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
