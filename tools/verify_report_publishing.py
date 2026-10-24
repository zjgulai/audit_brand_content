#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_report_publishing.py - T-316d: report publishing into authority.

## Why this file exists

T-316c delivered the render adaptor (`base/report_render_bridge.py`).
Nothing called it. And even if something had, the result would have been
lost on restart: `ReportStore` writes an index under `report_root`, but the
**case state had no `report` field at all** (measured 2026-10-24:
`grep -n '"report"' base/review_reducer.py` -> 0 hits).

So this verifier covers the two hops that were still missing:

    closing a case  ->  render  ->  ReportStore.publish  ->  report_publish
                                                                  command
                                                                     |
                                       GET /api/v1/reports  <--------+

## Coverage

    P1  e2e: submit -> judge -> claim -> close -> report appears in GET /reports
    P2  restart identity: same report_id / url / sha256 after reopening
    P3  the .md on disk has the six blocks and the sha256 matches the authority
    P4  render failure does NOT fail the close (node missing -> closed, report absent)
    P5  the snapshot used is the one frozen at judging time, not recomputed
    P6  ACL: a same-tenant coordinator reads it; a foreign tenant does not
    P7  report_publish rejected unless the case is closed
    P8  a second publish with a different report_id is refused (immutable)
    P9  same report_id replays idempotently (no duplicate command, no drift)
    P10 bad report_id / sha256 / url shapes are refused

Exit codes: 0 all pass / 1 red / 2 untested (no node / import failure).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

TENANT = "t1"
PRODUCT_LINE = "pump"
CLEAN_TEXT = "新品上市：售价 199 元，容量 240ml，适合 0-6 个月宝宝。"
TMP_ROOTS = []

SUBJECTS = (
    "base/report_render_bridge.py",
    "base/report_store.py",
    "base/review_command_service.py",
    "base/review_reducer.py",
    "api/review_api.py",
    "api/production_app.py",
)

try:
    from api.review_api import (
        AuthorityCaseSource, FileProjectionRepository, create_app)
    from api.write_api import IMPLEMENTED_WRITE_PATHS
    from base.auth_session import SessionStore
    from base.business_event_store import BusinessEventStore, WriterLease
    from base.projection_store import ProjectionStore
    from base.report_render_bridge import ReportRenderBridge
    from base.report_store import ReportStore
    from base.review_command_service import ReviewCommandService
    from base.review_reducer import initial_state, reduce_command
    from base.reviews_ledger import LedgerConflict, LedgerValidation
    from base.submission_service import SubmissionIngestor
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: cannot import: %s" % exc)
    sys.exit(2)


def submission(submission_id="s-rp-1", text=CLEAN_TEXT):
    return {
        "submission_id": submission_id, "content_type": "文本",
        "content_stage": "final_content", "entry_channel": "群消息",
        "source": {"kind": "free_text"}, "text": text,
        "product_line": PRODUCT_LINE,
    }


def principal(pid="u1", tenant=TENANT):
    return {"id": pid, "tenant": tenant, "open_id": "ou-" + pid,
            "tenant_id": tenant, "roles": ["dp3"],
            "product_lines": [PRODUCT_LINE], "product_line": PRODUCT_LINE}


def build(tmp, *, with_reports=True, node_path=None, principal_tenant=TENANT):
    lease = WriterLease(tmp / "writer.lock")
    lease.acquire()
    authority = BusinessEventStore(tmp / "authority", lease=lease)
    projection = ProjectionStore(tmp / "review.db")
    store = SessionStore(":memory:")
    frozen = tmp / "frozen"
    frozen.mkdir(exist_ok=True)
    report_store = None
    bridge = None
    if with_reports:
        report_store = ReportStore(
            str(tmp / "reports-root"), "https://ca.example/static")
        bridge = ReportRenderBridge(REPO_ROOT, node_path=node_path)
    service = ReviewCommandService(
        authority, projection,
        report_store=report_store, report_bridge=bridge)
    app = create_app(
        session_store=store,
        repository=FileProjectionRepository(
            frozen, strict=True, require_cases=False),
        case_source=AuthorityCaseSource(authority),
        submission_ingestor=SubmissionIngestor(),
        review_read_store=projection,
        review_command_service=service,
        principal_provider=lambda pid, tenant: dict(
            principal(pid, principal_tenant), tenant=tenant, tenant_id=tenant),
        enabled_write_capabilities=set(IMPLEMENTED_WRITE_PATHS),
        app_env="dev",
    )
    session = store.create_session("u1", tenant=TENANT)
    from fastapi.testclient import TestClient
    client = TestClient(app)
    client.cookies.set("session", session)
    return {"client": client, "authority": authority, "projection": projection,
            "service": service, "lease": lease, "tmp": tmp,
            "report_store": report_store}


def call(client, method, path, key, payload=None):
    response = client.request(
        method, path, json=payload,
        headers={"Idempotency-Key": key} if key else {})
    try:
        parsed = response.json()
    except ValueError:
        parsed = None
    return response.status_code, parsed


def close_a_case(env, submission_id="s-rp-1", text=CLEAN_TEXT):
    """提交 → 判定 → 领取 → 结案。返回 (case_id, close_body)。"""
    client = env["client"]
    st, created = call(client, "POST", "/api/v1/submissions",
                       "ingest-" + submission_id, submission(submission_id, text))
    if st != 200:
        raise AssertionError("ingest %s %r" % (st, created))
    case_id = created["case_id"]
    st, claimed = call(client, "POST", "/api/v1/cases/%s/claim" % case_id,
                       "claim-" + submission_id, {})
    if st != 200:
        raise AssertionError("claim %s %r" % (st, claimed))
    st, closed = call(
        client, "POST", "/api/v1/cases/%s/actions" % case_id,
        "close-" + submission_id,
        {"action": "submit", "version": claimed["version"],
         "conclusion": {"review_notes": "逐条看过后结案"}})
    if st != 200:
        raise AssertionError("close %s %r" % (st, closed))
    return case_id, closed


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

    if shutil.which("node") is None:
        print("UNTESTED: node not on PATH - report rendering cannot run")
        return 2

    tmp = Path(tempfile.mkdtemp(prefix="report-publishing-"))
    TMP_ROOTS.append(tmp)

    # ---- P1 e2e ----
    try:
        env = build(tmp)
        case_id, closed = close_a_case(env)
        published = closed.get("report") or {}
        st, listed = call(env["client"], "GET", "/api/v1/reports", None)
        rows = listed if isinstance(listed, list) else []
        mine = [r for r in rows if r.get("case_id") == case_id]
        report(published.get("ok") is True
               and published.get("report_id")
               and st == 200 and len(mine) == 1
               and mine[0].get("report_id") == published.get("report_id"),
               "P1 ★ e2e: close -> report published -> visible in GET /reports",
               "ok=%r id=%r listed=%d mine=%d" % (
                   published.get("ok"), published.get("report_id"),
                   len(rows), len(mine)))
    except Exception as exc:  # noqa: BLE001
        report(False, "P1 ★ e2e: close -> report published -> visible in GET /reports",
               "%s: %s" % (type(exc).__name__, exc))
        print("----------------------------------------")
        print("FAILED %d passed, %d failed" % (passed, failed), file=sys.stderr)
        shutil.rmtree(tmp, ignore_errors=True)
        return 1

    # ---- P3 on-disk bytes match authority ----
    try:
        record = env["authority"].state(case_id).get("report") or {}
        path = tmp / "reports-root" / record.get("path", "")
        data = path.read_bytes()
        text = data.decode("utf-8")
        import hashlib
        sha = hashlib.sha256(data).hexdigest()
        blocks = ["## 结论", "## 命中的问题", "## 覆盖证明",
                  "## 依据清单", "## 未审说明", "## 执行回执"]
        report(path.is_file() and sha == record.get("sha256")
               and all(b in text for b in blocks),
               "P3 ★ on-disk .md matches authority sha256 and has six blocks",
               "sha_ok=%r missing=%r" % (
                   sha == record.get("sha256"),
                   [b for b in blocks if b not in text]))
        report(record.get("source_ir_fingerprint")
               and len(str(record["source_ir_fingerprint"])) == 64,
               "P3b report carries source_ir_fingerprint (rebuildable)",
               repr(record.get("source_ir_fingerprint"))[:20])
        report(record.get("published_by") == "u1",
               "P3c published_by records the closer", repr(record.get("published_by")))
    except Exception as exc:  # noqa: BLE001
        report(False, "P3 ★ on-disk .md matches authority sha256", str(exc))

    # ---- P2 restart identity ----
    try:
        before = env["authority"].state(case_id).get("report") or {}
        env["lease"].release()
        env2 = build(tmp)
        after = env2["authority"].state(case_id).get("report") or {}
        st, got = call(env2["client"], "GET", "/api/v1/reports/%s"
                       % before.get("report_id"), None)
        report(after.get("report_id") == before.get("report_id")
               and after.get("sha256") == before.get("sha256")
               and after.get("url") == before.get("url")
               and st == 200,
               "P2 ★ restart identity: report_id/url/sha256 unchanged",
               "%s before=%r after=%r" % (
                   st, before.get("report_id"), after.get("report_id")))
        env = env2
    except Exception as exc:  # noqa: BLE001
        report(False, "P2 ★ restart identity", "%s: %s" % (type(exc).__name__, exc))

    # ---- P4 render failure must not fail the close ----
    try:
        tmp4 = Path(tempfile.mkdtemp(prefix="report-nonode-"))
        TMP_ROOTS.append(tmp4)
        env4 = build(tmp4, node_path="")
        case4, closed4 = close_a_case(env4, "s-rp-4")
        rep4 = closed4.get("report") or {}
        report(closed4.get("status") == "closed"
               and rep4.get("ok") is False
               and rep4.get("detail") == "node_missing"
               and not (env4["authority"].state(case4).get("report")),
               "P4 ★ node missing -> case still closed, report absent with reason",
               "status=%r report=%r" % (closed4.get("status"), rep4))
    except Exception as exc:  # noqa: BLE001
        report(False, "P4 ★ node missing -> close still succeeds",
               "%s: %s" % (type(exc).__name__, exc))

    # ---- P5 snapshot belongs to this case ----
    #
    # ★ 第一版断言「正文里出现原文里的 298 / 300ml」—— 那**不成立**：
    #   `renderReport` 只输出结论/问题/覆盖/依据/未审/回执，**不含原文**。
    #   这条断言永远假，与实现好坏无关。**判据要对着真实产出写。**
    #
    # 换成能红的形状：两个案件各自产出**不同的 report_id 与不同正文**，
    # 且正文里的 IR id 与各自权威 state 里的 ir_id 一致。
    try:
        case5, closed5 = close_a_case(env, "s-rp-5",
                                      "第二批判定：售价 298 元，容量 300ml。")
        rec5 = env["authority"].state(case5).get("report") or {}
        rec1 = env["authority"].state(case_id).get("report") or {}
        text5 = (tmp / "reports-root" / rec5.get("path", "-")).read_text(encoding="utf-8")
        ir5 = (env["authority"].state(case5).get("ir") or {}).get("ir_id")
        ir1 = (env["authority"].state(case_id).get("ir") or {}).get("ir_id")
        report(rec5.get("report_id") and rec1.get("report_id")
               and rec5["report_id"] != rec1["report_id"]
               and ir5 and ir5 in text5 and ir5 != ir1,
               "P5 ★ each case gets its own report (id + IR id in body)",
               "id5=%r id1=%r ir5=%r in_body=%r" % (
                   rec5.get("report_id"), rec1.get("report_id"), ir5, ir5 in text5))
    except Exception as exc:  # noqa: BLE001
        report(False, "P5 ★ each case gets its own report", str(exc))

    # ---- P6 ACL ----
    try:
        rid = (env["authority"].state(case_id).get("report") or {}).get("report_id")
        from base.rbac import can_read_content, can_read_report
        same = principal("u-coord", TENANT)
        same["roles"] = ["coordinator"]
        other = principal("u-out", "t9")
        other["roles"] = ["coordinator"]
        rec_acl = {
            "tenant": env["authority"].state(case_id).get("tenant"),
            "product_line": env["authority"].state(case_id).get("product_line"),
            "submitter_id": env["authority"].state(case_id).get("submitter_id"),
            "assignee": [],
        }
        pseudo = {"tenant": rec_acl["tenant"],
                  "product_line": rec_acl["product_line"],
                  "submitter_id": rec_acl["submitter_id"],
                  "assignee_id": None, "actionable": False}
        report(can_read_content(same, pseudo) is True
               and can_read_content(other, pseudo) is False,
               "P6 ★ report ACL = case readability (same tenant yes, other no)",
               "same=%r other=%r" % (can_read_content(same, pseudo),
                                     can_read_content(other, pseudo)))
        # 通过真实 ReportStore.read 走一遍授权 —— 用**生产同一个**判据函数。
        #
        # ★ 第一版用 `build()` 里未注入 authorize 的 store（它走
        #   `_default_authorize`，读单数大写的 `role`），于是 same=False、
        #   other=True —— **两头都反了**。那正好复现了「验证器绿、生产全禁」
        #   的实现形状，只不过这次它红在了验证器里，被我看见了。
        from base.rbac import can_read_report
        env["report_store"].authorize = can_read_report
        ok_same = env["report_store"].read(rid, same).get("ok") is True
        ok_other = env["report_store"].read(rid, other).get("ok") is False
        report(ok_same and ok_other,
               "P6b ReportStore.read honors can_read_report (production criterion)",
               "same=%r other=%r" % (ok_same, ok_other))
        # ★ P6c：**结案后的真实形状** —— assigned 为空。
        #
        #   结案命令会清空 assignee，于是索引里的 `acl.assigned` 是 `[]`。
        #   任何「必须在 assigned 里」的口径在这时**对所有人都为假**，
        #   包括结案人自己。而 `_default_authorize` 的 DP3/DP4 分支恰好是
        #   这个口径 —— 它是「验证器绿、生产全禁」的第五个实例。
        #
        #   ★ 这条是补出来的：M5 变异（把口径换成单数 role + 要求 in assigned）
        #     在 P6a/P6b 下**没有红** —— 因为 coordinator 走的是兜底分支。
        #     真正能抓它的，是「结案后自己读自己的报告」这个场景。
        # ★ 从**真实索引记录**读，不手搓一个空 assigned —— 手搓的只能证明
        #   「空 assigned 会被拒」，证明不了「生产写进去的就是非空」。
        #   这条断言的落点是「发布时把结案人写进 acl.assigned」这个动作本身。
        real = next((r for r in env["report_store"].read_index()["records"]
                     if r.get("report_id") == rid), {})
        real_assigned = (real.get("acl") or {}).get("assigned") or []
        closer = principal("u1", TENANT)
        closer["roles"] = ["dp3"]
        ok_closer = can_read_report(closer, real) is True
        report(ok_closer and real_assigned == ["u1"],
               "P6c ★ ★ the closer is recorded in acl.assigned and can read back",
               "assigned=%r ok=%r" % (real_assigned, ok_closer))
        # ★ P6d：**判据必须能被单点看到**。
        #
        #   P6c 抓不到「口径换成 _default_authorize」的变异 —— 实测过：
        #   因为 `_default_authorize` 读 `principal["role"]`（单数），而真实
        #   principal 只有 `roles`，于是它每个分支都不命中、**落到最后一行
        #   `return False`**，看着像「拒绝了」。而 `can_read_report` 的
        #   coordinator 兜底分支又恰好放行 —— 两个错叠加起来就成了对的。
        #
        #   修法是**把「单数 role 一律不认」这条判据显式钉住**：
        #   一个只带 `role`（单数、大写）的主体，不管它多像 DP3，都必须拒。
        #   规矩来源：`base/rbac.py` 全仓只认 `roles`（复数、小写）。
        legacy = {"id": "u1", "tenant": TENANT, "product_line": PRODUCT_LINE,
                  "role": "DP3", "assigned": ["u1"]}
        report(can_read_report(legacy, real) is False,
               "P6d ★ ★ a principal with singular `role` is NOT accepted",
               "legacy_ok=%r" % (can_read_report(legacy, real),))
    except Exception as exc:  # noqa: BLE001
        report(False, "P6 ★ report ACL", "%s: %s" % (type(exc).__name__, exc))

    # ---- P7/P8/P9/P10 reducer-level rules ----
    def st_closed():
        st = initial_state("case-rp")
        st["tenant"] = TENANT
        st["product_line"] = PRODUCT_LINE
        st["status"] = "closed"
        return st

    RID = "rp" + "a" * 16
    GOOD = {"report_id": RID, "sha256": "b" * 64,
            "url": "https://ca.example/static/reports/%s.md" % RID,
            "path": "reports/%s.md" % RID,
            "source_ir_id": "ir-1", "source_ir_version": "content-unit-v1",
            "source_ir_fingerprint": "c" * 64,
            "created_at": "2026-10-24T00:00:00Z",
            "renderer": "report_render.mjs@v1"}

    try:
        open_state = initial_state("case-open")
        open_state["status"] = "claimed"
        code = None
        try:
            reduce_command(open_state, "report_publish", "u1", 0,
                           {**GOOD, "case_id": "case-open"}, now=1000)
        except (LedgerConflict, LedgerValidation) as exc:
            code = exc.code
        report(code == "report_requires_closed",
               "P7 ★ report_publish refused unless the case is closed", repr(code))
    except Exception as exc:  # noqa: BLE001
        report(False, "P7 ★ report_publish requires closed", str(exc))

    try:
        s7, ev7, r7 = reduce_command(st_closed(), "report_publish", "u1", 0,
                                     {**GOOD, "case_id": "case-rp"}, now=1000)
        rep = s7.get("report") or {}
        report(rep.get("report_id") == RID and rep.get("published_by") == "u1"
               and r7.get("report", {}).get("report_id") == RID,
               "P7b report lands in state and in the command result",
               repr(rep.get("report_id")))
    except Exception as exc:  # noqa: BLE001
        s7, rep = st_closed(), {}
        report(False, "P7b report lands in state", str(exc))

    # P8 ★ 随 T-317b 翻转：不同 report_id = 重审的新报告 → **追加**（不覆盖），
    #   旧条目原样保留在 state["reports"]；`report` 指向最新一份。
    #   旧断言「refused」是 T-316d 的契约；重审（T-317）必然产新 report_id，
    #   不改守卫重审就发不出报告（10-23 #98 假绿的根因之一：产物没动）。
    try:
        other_id = "rp" + "d" * 16
        s8, _ev8, r8 = reduce_command(s7, "report_publish", "u1", int(
            s7["version"]), {**GOOD, "report_id": other_id,
                             "case_id": "case-rp"}, now=2000)
        reports = s8.get("reports") or []
        report(s8["report"]["report_id"] == other_id
               and [r["report_id"] for r in reports]
               == [rep["report_id"], other_id],
               "P8 ★ 不同 report_id 追加为第二条，旧条目原样保留（T-317b）",
               repr([r["report_id"] for r in reports]))
    except Exception as exc:  # noqa: BLE001
        report(False, "P8 ★ 不同 report_id 追加为第二条", str(exc))

    # P9 同一 report_id 幂等
    try:
        s9, ev9, r9 = reduce_command(s7, "report_publish", "u2", int(
            s7["version"]), {**GOOD, "case_id": "case-rp"}, now=3000)
        report(s9.get("report") == s7.get("report")
               and r9.get("report", {}).get("published_by") == "u1",
               "P9 same report_id replays idempotently (no drift, no overwrite)",
               "published_by=%r" % (r9.get("report", {}).get("published_by"),))
    except Exception as exc:  # noqa: BLE001
        report(False, "P9 same report_id replays idempotently", str(exc))

    # P10 形状校验
    cases = [
        ("report_id 不是 rp+16hex", {"report_id": "rpXYZ"}, "bad_report_id"),
        ("report_id 大写", {"report_id": "rp" + "A" * 16}, "bad_report_id"),
        ("sha256 太短", {"sha256": "abc"}, "bad_report"),
        ("sha256 含非 hex", {"sha256": "z" * 64}, "bad_report"),
        ("url 不是 http(s)", {"url": "file:///tmp/x.md"}, "bad_report"),
        ("url 空", {"url": ""}, "bad_url"),
        ("path 空", {"path": ""}, "bad_path"),
    ]
    for label, override, expect in cases:
        code = None
        try:
            reduce_command(st_closed(), "report_publish", "u1", 0,
                           {**GOOD, **override, "case_id": "case-rp"}, now=1000)
        except (LedgerConflict, LedgerValidation) as exc:
            code = exc.code
        report(code == expect, "P10 %s -> %s" % (label, expect), repr(code))

    shutil.rmtree(tmp, ignore_errors=True)
    for root in TMP_ROOTS:
        shutil.rmtree(root, ignore_errors=True)

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
        import traceback
        traceback.print_exc()
        print("UNTESTED: verifier crashed: %s" % exc)
        sys.exit(2)
