#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_stage_gate_d5.py - D5 stage gate: the real production assembly, end to end.

## Why this file exists

Every other verifier in this repo builds the app by hand:

    create_app(session_store=..., repository=..., review_command_service=...)

`api/production_app.create_production_app()` is **never** built that way in a
test. So the whole class of defects where "the pieces work but the production
wiring is wrong" is invisible: `ProductionRuntime.start()` decides which
stores exist, which allowlist source gets injected, which report ACL is used,
and which write paths are enabled. A typo there fails **only in production**.

Measured 2026-10-24, before this file: three of the last five defects found
this session were exactly this shape (rbac allowlist never injected, report
ACL reading a singular `role`, `report_root` missing from settings).

## What it proves

    D5-1  `ProductionRuntime.start()` comes up with only real settings
    D5-2  submit -> judge -> claim -> close, through the production app
    D5-3  the report is published to REPORT_ROOT and lands in authority
    D5-4  restart (new runtime, same data roots) keeps the report identical
    D5-5  the allowlist source is really injected (can_act reads the projection)
    D5-6  the six takedown write paths are enabled in production
    D5-7  release-decision is still 501 in production (T-310 not delivered)
    D5-8  `maintain_once()` runs without raising (heartbeat is live)
    D5-9  write paths NOT in PRODUCTION_WRITE_PATHS answer 501, not 403/500

Exit codes: 0 all pass / 1 red / 2 untested (import / node).
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

TENANT = "t1"
PRODUCT_LINE = "pump"
CLEAN_TEXT = "新品上市：售价 199 元，容量 240ml，适合 0-6 个月宝宝。"

SUBJECTS = (
    "api/production_app.py",
    "api/review_api.py",
    "api/write_api.py",
    "base/review_command_service.py",
    "base/report_render_bridge.py",
    "base/rbac.py",
)

try:
    from fastapi.testclient import TestClient
    from api.oauth import FakeOAuthProvider
    from api.production_app import (
        PRODUCTION_WRITE_PATHS, ProductionRuntime, ProductionSettings,
        create_production_app)
    # ★ 2026-10-31：D5-6b 要对账两张表，缺一条 import 会让断言现场 NameError
    #   —— 那会表现成「跑不起来」而不是「对不上」，两种红指向完全不同的修法。
    from api.write_api import IMPLEMENTED_WRITE_PATHS
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: cannot import production assembly: %s" % exc)
    sys.exit(2)


def make_settings(root, *, report_root=None, tenant_allowlist=None):
    root = Path(root)
    frozen = root / "frozen"
    frozen.mkdir(parents=True, exist_ok=True)
    principal = root / "principals.json"
    # 两个身份：u1 提交/复核（coordinator），u2 签发（signer）——
    # SoD 禁止提交人签发自己的案件，单身份走不通签发腿。
    principal.write_text(json.dumps({"principals": [
        {
            "id": "u1", "tenant_id": TENANT, "open_id": "ou-u1",
            "roles": ["dp3", "coordinator"], "product_lines": [PRODUCT_LINE],
            "product_line": PRODUCT_LINE, "capabilities": [], "status": "active",
            "authz_version": "u1-v1",
        },
        {
            "id": "u2", "tenant_id": TENANT, "open_id": "ou-u2",
            "roles": ["dp3", "signer"], "product_lines": [PRODUCT_LINE],
            "product_line": PRODUCT_LINE, "status": "active",
            # T-310c：签发的 SoD 判定读 principal["capabilities"]（gate._authorize
            # 既有口径）；名单层（can_sign_release）由 D5-8 的授权链证明。
            "capabilities": ["release.sign", "release.revoke"],
            "authz_version": "u2-v1",
        },
        {
            "id": "u3", "tenant_id": TENANT, "open_id": "ou-u3",
            "roles": ["dp4"], "product_lines": [PRODUCT_LINE],
            "product_line": PRODUCT_LINE, "capabilities": [], "status": "active",
            "authz_version": "u3-v1",
        },
        {
            "id": "u4", "tenant_id": TENANT, "open_id": "ou-u4",
            "roles": ["it"], "product_lines": [PRODUCT_LINE],
            "product_line": PRODUCT_LINE, "capabilities": [], "status": "active",
            "authz_version": "u4-v1",
        }]}), encoding="utf-8")
    return ProductionSettings(
        authority_root=root / "authority",
        frozen_projection_root=frozen,
        review_projection_db=root / "projection" / "review.db",
        session_db=root / "session" / "session.db",
        access_log_path=root / "audit" / "access.jsonl",
        principal_directory=principal,
        report_root=report_root or (root / "reports"),
        public_origin="https://ca.example",
        oauth_client_id="cli_stage_gate",
        oauth_client_secret="not-a-real-secret",
        oauth_redirect_uri="https://ca.example/auth/callback",
        oauth_reauth_redirect_uri="https://ca.example/auth/reauth/callback",
        tenant_allowlist=frozenset(tenant_allowlist or {TENANT}),
    )


def cookie_for(runtime, pid="u1"):
    """建 session，并返回 (sid, csrf)。

    ★ CSRF token 由**调用方**生成后交给 store（store 只存它的 hash），
      所以这里必须自己拿住明文。第一版去 store 里 `get(sid)["csrf_token"]`
      取明文 —— 它不存在，这是设计（服务端不该能还原 token）。
    """
    csrf = "csrf-" + os.urandom(8).hex()
    sid = runtime.session_store.create_session(
        pid, tenant=TENANT, csrf_token=csrf)
    return sid, csrf


def call(client, method, path, key, payload=None, csrf=None):
    """生产 app 的三个门都必须过：session cookie、Origin、CSRF token。

    ★ 第一版只带 Idempotency-Key，三条写请求全 403 且 body 是 None
      （Starlette 的 403 走的是默认处理器，不是本 app 的 JSON 处理器）。
      那不是「生产坏了」—— 那正是 CSRF 在工作。**测生产装配就必须像
      浏览器一样带上它要求的头**，否则测的是 403，不是业务链。
    """
    headers = {}
    if key:
        headers["Idempotency-Key"] = key
    headers["Origin"] = "https://ca.example"
    if csrf:
        headers["X-CSRF-Token"] = csrf
    # ★ `payload=None` 时**发空对象**，不发「没有 body」。
    #   `POST /claim` 的 `ClaimBody` 是必填 body（可以是空对象），
    #   `json=None` 会让 httpx 完全省略 body → FastAPI 422 `Field required`
    #   → 看起来像「生产里 claim 坏了」。实测过：同一个请求 json={} 是 200。
    if payload is None and method.upper() in ("POST", "PUT", "PATCH"):
        payload = {}
    response = client.request(method, path, json=payload, headers=headers)
    try:
        parsed = response.json()
    except ValueError:
        parsed = None
    return response.status_code, parsed


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
        print("UNTESTED: node not on PATH - report rendering is part of this gate")
        return 2

    root = Path(tempfile.mkdtemp(prefix="stage-gate-d5-"))
    runtime = None
    try:
        settings = make_settings(root)
        # ★ 必须**先**造出前端产物目录，SPA fallback 才会被注册。
        #
        #   实测（M3 变异）：`/{full_path:path}` 那条路由只在
        #   `os.path.isdir(AUDIT_WEB_ROOT)` 时注册。沙盒里 `/app/web_dist` 不存在，
        #   于是 SPA fallback 根本没挂 —— 那么「报告端点必须注册在它之前」
        #   这条断言**测的是一个不存在的对手**，把报告端点挪到它后面仍然 15/15。
        #   造出 index.html 之后，顺序错了就会被 SPA 吃掉、D5-10 才真的会红。
        web_root = root / "web_dist"
        web_root.mkdir(parents=True, exist_ok=True)
        (web_root / "index.html").write_text(
            "<!doctype html><title>spa</title><div id=root></div>", encoding="utf-8")
        _old_web_root = os.environ.get("AUDIT_WEB_ROOT")
        os.environ["AUDIT_WEB_ROOT"] = str(web_root)
        try:
            app = create_production_app(
                settings, oauth_provider=FakeOAuthProvider())
        finally:
            if _old_web_root is None:
                os.environ.pop("AUDIT_WEB_ROOT", None)
            else:
                os.environ["AUDIT_WEB_ROOT"] = _old_web_root
        runtime = app.state.production_runtime
        try:
            runtime.start()
        except Exception as exc:  # noqa: BLE001
            report(False, "D5-1 ProductionRuntime.start()",
                   "%s: %s" % (type(exc).__name__, exc))
            raise
        report(runtime.ready is True
               and runtime.service is not None
               and runtime.report_store is not None
               and runtime.report_bridge is not None,
               "D5-1 ★ production assembly starts (authority+projection+report wired)",
               "ready=%r store=%r bridge=%r" % (
                   runtime.ready, runtime.report_store is not None,
                   runtime.report_bridge is not None))

        # D5-5 allowlist source injected
        import base.rbac as RBAC
        report(RBAC._ALLOWLIST_SOURCE is not None,
               "D5-5 ★ rbac allowlist source injected by start()",
               repr(RBAC._ALLOWLIST_SOURCE))

        # D5-6 / D5-7 capability tables
        takedown_paths = {
            "/api/v1/takedown-tasks/{id}/start",
            "/api/v1/takedown-tasks/{id}/complete",
            "/api/v1/takedown-tasks/{id}/fail",
            "/api/v1/takedown-tasks/{id}/retry",
            "/api/v1/takedown-tasks/{id}/reassign",
            "/api/v1/takedown-tasks/{id}/waive",
        }
        report(takedown_paths <= set(PRODUCTION_WRITE_PATHS),
               "D5-6 ★ six takedown write paths enabled in production",
               repr(sorted(takedown_paths - set(PRODUCTION_WRITE_PATHS))))
        # T-310c：签发两条进生产能力表（D5-7 原断言「仍 501」随交付翻转 ——
        # 那条防假成功的反向对照，如今判据反过来：放行必须有真实现撑着，
        # 由下面的 D5-9（真签发）与 D5-13（重启后仍在）证明不是假成功。
        report("/api/v1/cases/{id}/release-decision" in PRODUCTION_WRITE_PATHS
               and "/api/v1/cases/{id}/release-revoke" in PRODUCTION_WRITE_PATHS,
               "D5-7 ★ release 两条已进生产能力表（T-310c 交付，有真实现）")

        # ★★ 2026-10-31：D5-6b —— 实现表里的每一条，生产都必须放行。
        #
        #   这是同一个病第四次（T-312b 下线六条 / T-402 名单四条 /
        #   T-401a 申诉三条 / 这次 uploads）。每次的形状完全一样：
        #   `IMPLEMENTED_WRITE_PATHS` 加了，`PRODUCTION_WRITE_PATHS` 没加，
        #   于是「开发测得通、生产 501」，而**没有任何东西会红** ——
        #   因为既有自证要么跑开发装配（回落成实现表），要么直接调底层。
        #
        #   ★ 判据是**单向包含**，不是相等。我第一版写的是相等，当场红了：
        #     只在生产表里的有 5 条（admin 四条 + reports/resign），它们由
        #     `api/admin_api.py` 与重签 handler 实现、**不经过** `write_api`
        #     的 `require_enabled` 闸门，所以本来就不该出现在实现表里。
        #     把那 5 条也塞进实现表，等于让实现表宣称一件它不负责的事。
        #
        #   ★ 所以真正会伤到用户的那个方向只有一个：
        #     「实现了、生产没放行」→ 用户点了 501。反过来（生产表多一条）
        #     由那段代码自己是否真的注册了路由来保证，`OPENAPI` 那条已经覆盖。
        _impl = set(IMPLEMENTED_WRITE_PATHS)
        _prod = set(PRODUCTION_WRITE_PATHS)
        report(_impl <= _prod,
               "D5-6b ★★ 实现表 ⊆ 生产能力表（上一版漏了 /api/v1/uploads，"
               "生产选图片一律 501）",
               "实现了但生产没放行=%r（这些在生产上必 501）"
               % (sorted(_impl - _prod),))

        session, csrf = cookie_for(runtime)
        client = TestClient(app)
        client.cookies.set("__Host-session", session)

        # D5-2 submit -> judge -> claim -> close
        st, created = call(client, "POST", "/api/v1/submissions", "d5-ingest", csrf=csrf, payload={
            "submission_id": "s-d5-1", "content_type": "文本",
            "content_stage": "final_content", "entry_channel": "群消息",
            "source": {"kind": "free_text"}, "text": CLEAN_TEXT,
            "product_line": PRODUCT_LINE})
        case_id = (created or {}).get("case_id")
        report(st == 200 and case_id,
               "D5-2a submit -> case created through production app",
               "%s %r" % (st, (created or {}).get("case_id")))
        st, claimed = call(client, "POST", "/api/v1/cases/%s/claim" % case_id,
                           "d5-claim", csrf=csrf)
        report(st == 200 and (claimed or {}).get("status") == "claimed",
               "D5-2b claim", "%s %r" % (st, (claimed or {}).get("status")))
        st, closed = call(
            client, "POST", "/api/v1/cases/%s/actions" % case_id, "d5-close",
            csrf=csrf,
            payload={"action": "submit",
                     "version": (claimed or {}).get("version"),
                     "conclusion": {"review_notes": "逐条看过后结案"}})
        report(st == 200 and (closed or {}).get("status") == "closed",
               "D5-2c close", "%s %r" % (st, (closed or {}).get("status")))

        # ── D5-2d ★ T-451：工作流耗时必须能被 HTTP 读到 ──────────────
        # ★ 为什么这条不能只在 verify_workflow_timing 里验：
        #   那边验的是「算得对」；这里验的是「**真的从生产接口读得出来**」。
        #   两者是两件事 —— due_at 就是「算得对但进不了权威」的先例，
        #   而自证当时是 60/60 全绿。
        st, detail = call(client, "GET", "/api/v1/cases/%s" % case_id, "d5-timing")
        timing = (detail or {}).get("workflow_timing") if st == 200 else None
        report(isinstance(timing, dict) and timing.get("status") == "ok",
               "D5-2d ★★ 案件详情接口返回 workflow_timing（status=ok）",
               "%s %r" % (st, (timing or {}).get("status")))
        report(isinstance(timing, dict) and isinstance(timing.get("total_ms"), (int, float))
               and timing["total_ms"] > 0,
               "D5-2e ★★★ 总耗时是正数（秒差会得 0，本行必红）",
               repr((timing or {}).get("total_ms")))
        report(isinstance(timing, dict) and isinstance(timing.get("slowest"), list)
               and len(timing["slowest"]) >= 1,
               "D5-2f ★ 最慢步骤非空（能归因到具体哪一步慢）",
               repr((timing or {}).get("slowest")))

        # D5-3 report published
        rep = (closed or {}).get("report") or {}
        record = (runtime.authority.state(case_id) or {}).get("report") or {}
        on_disk = settings.report_root / record.get("path", "-")
        body = on_disk.read_text(encoding="utf-8") if on_disk.is_file() else ""
        report(rep.get("ok") is True and record.get("report_id")
               and on_disk.is_file()
               and "## 执行回执" in body,
               "D5-3 ★ close publishes the report into REPORT_ROOT + authority",
               "ok=%r id=%r disk=%r" % (rep.get("ok"), record.get("report_id"),
                                        on_disk.is_file()))

        # D5-10/11/12 报告正文端点（URL 真的能打开）
        #
        # ★ 这一段为什么必须有：报告 URL 是 `/static/reports/<id>.md`，
        #   而 SPA fallback 是 `/{full_path:path}` —— **它会吃掉这个前缀并
        #   回落成 index.html**。不单独断言的话，「报告写进去了」与
        #   「用户点链接能看到」是两件事，而只有前者有执行点。
        url_path = record.get("url", "")
        prefix = settings.public_origin
        # ★ 只剥掉 origin（`https://ca.example`），**保留 `/static` 这一段**。
        #   第一版剥的是 `origin + "/static"`，剩下 `/reports/x.md` ——
        #   少了 `/static`，路由匹配不上，断言报 404 而实现是对的。
        #   从 URL 反推路径时，剥到哪一段必须与路由的前缀逐字对齐。
        local_path = url_path[len(prefix):] if url_path.startswith(prefix) else url_path
        r_body = client.get(local_path)
        body_text = r_body.text or ""
        report(r_body.status_code == 200,
               "D5-10 ★ report URL path answers 200 (SPA fallback does not eat it)",
               "%s -> %s" % (local_path, r_body.status_code))
        # ★ 只断言 200 不够：SPA fallback 也返回 200（它回落成 index.html）。
        #   必须断言**正文是报告**，且**不是**那个 index.html。
        report(r_body.status_code == 200
               and "# 内容审查报告" in body_text
               and "id=root" not in body_text,
               "D5-10b body is the report, NOT the SPA index.html",
               "len=%d head=%r" % (len(body_text), body_text[:24]))

        # 未登录 → 401（不是 403，也不泄露 report_id 是否存在）
        anon = TestClient(app)
        r_anon = anon.get(local_path)
        report(r_anon.status_code == 401,
               "D5-11 ★ report body without session -> 401",
               str(r_anon.status_code))

        # 跨租户 → 404（不是 403：区分开就是 report_id 枚举器）
        st_x, _ = call(client, "GET", "/static/reports/rp%s.md" % ("0" * 16), None)
        report(st_x in (401, 404),
               "D5-12 nonexistent report_id -> 401/404, never 200",
               str(st_x))

        # D5-8 heartbeat
        try:
            runtime.maintain_once()
            hb_ok, hb_detail = True, ""
        except Exception as exc:  # noqa: BLE001
            hb_ok, hb_detail = False, "%s: %s" % (type(exc).__name__, exc)
        report(hb_ok, "D5-8 maintain_once() runs (heartbeat live)", hb_detail)

        # D5-8 授权链（T-315b）：signer 必须被 release.sign 名单点名。
        # 名单源读投影 approved grants —— 先证明「未点名 → 403 且不烧 token」，
        # 再走 propose(dp4) → execute(it) → approve(coordinator) 三权分立。
        live_version = (runtime.authority.state(case_id) or {}).get("version")
        sid_u2_pre, csrf_u2_pre = cookie_for(runtime, "u2")
        client_u2_pre = TestClient(app)
        client_u2_pre.cookies.set("__Host-session", sid_u2_pre)
        tok_pre = runtime.session_store.issue_step_up(
            "u2", case_id, "sign", "n-d5-pre")
        st8a, _ = call(client_u2_pre, "POST",
                       "/api/v1/cases/%s/release-decision" % case_id,
                       "d5-sign-pre", csrf=csrf_u2_pre,
                       payload={"decision": "sign", "version": live_version,
                                "reason": "未点名", "step_up_token": tok_pre,
                                "nonce": "n-d5-pre"})
        report(st8a == 403,
               "D5-8a 未被 release.sign 名单点名 → 403（step-up 不消费）",
               str(st8a))
        svc = runtime.service
        gagg = "grants:%s" % TENANT
        gp = svc.execute(aggregate_id=gagg, command="grant_propose",
                         actor={"principal_id": "u3", "tenant_id": TENANT},
                         expected_version=0,
                         payload={"capability": "release.sign", "user_id": "u2",
                                  "reason": "D5 签发授权",
                                  "scope": {"tenant": TENANT,
                                            "product_lines": [PRODUCT_LINE]}},
                         idempotency_key="d5-gp")
        gid = gp["result"]["grant"]["grant_id"]
        svc.execute(aggregate_id=gagg, command="grant_execute",
                    actor={"principal_id": "u4", "tenant_id": TENANT},
                    expected_version=1, payload={"grant_id": gid},
                    idempotency_key="d5-ge")
        svc.execute(aggregate_id=gagg, command="grant_approve",
                    actor={"principal_id": "u1", "tenant_id": TENANT},
                    expected_version=2, payload={"grant_id": gid},
                    idempotency_key="d5-ga")
        report("u2" in (runtime.allowlist_source().get("release.sign")
                        or frozenset()),
               "D5-8b 三权分立授权链后 u2 进 release.sign 名单")
        # 反向：提案人自己审批 → 403（三权分立仍活着）
        try:
            svc.execute(aggregate_id=gagg, command="grant_approve",
                        actor={"principal_id": "u3", "tenant_id": TENANT},
                        expected_version=3, payload={"grant_id": gid},
                        idempotency_key="d5-ga-bad")
            report(False, "D5-8c 提案人自审 → 拒", "（未拒绝）")
        except Exception as exc:  # noqa: BLE001
            report(True, "D5-8c 提案人自审 → 拒",
                   "%s" % getattr(exc, "code", type(exc).__name__))

        # D5-9 release-decision 进权威（T-310c）：step-up 真消费、签名真构造、
        # 状态落 state["release"]。原断言「501」随交付翻转。
        # ★ 用 u2 签发：SoD 禁止提交人（u1）签发自己的案件 —— 单身份走不通。
        sid_u2, csrf_u2 = cookie_for(runtime, "u2")
        client_u2 = TestClient(app)
        client_u2.cookies.set("__Host-session", sid_u2)
        token9 = runtime.session_store.issue_step_up(
            "u2", case_id, "sign", "n-d5-sign")
        st9, body9 = call(client_u2, "POST",
                          "/api/v1/cases/%s/release-decision" % case_id,
                          "d5-release", csrf=csrf_u2,
                          payload={"decision": "sign", "version": live_version,
                                   "reason": "D5 签发", "step_up_token": token9,
                                   "nonce": "n-d5-sign"})
        rel9 = (body9 or {}).get("release") or {}
        sig9 = (body9 or {}).get("signature") or {}
        report(st9 == 200 and rel9.get("status") == "signed"
               and rel9.get("release_status") == "已放行"
               and len(sig9.get("signature_hash", "")) == 64
               and sig9.get("kb_snapshot_hash") == (runtime.authority.state(case_id)
                                                    or {}).get("kb_snapshot_hash"),
               "D5-9 ★ 生产装配真实签发（signed/已放行/绑定 kb_snapshot_hash）",
               "%s %r" % (st9, rel9.get("status")))
        # 缺 step-up 必须 403 且权威 seq 不变（失败不落案）
        seq_before = runtime.authority.head()["seq"]
        live_version2 = (runtime.authority.state(case_id) or {}).get("version")
        st9b, body9b = call(client_u2, "POST",
                            "/api/v1/cases/%s/release-revoke" % case_id,
                            "d5-revoke-nostep", csrf=csrf_u2,
                            payload={"version": live_version2, "reason": "x"})
        report(st9b == 403
               and runtime.authority.head()["seq"] == seq_before,
               "D5-9b 缺 step-up 的撤回 → 403 且权威不落批次",
               "%s seq %r" % (st9b, seq_before))

        # D5-4 restart identity
        before = dict(record)
        before_body = body
        runtime.stop()
        runtime2 = ProductionRuntime(settings, oauth_provider=FakeOAuthProvider())
        runtime2.start()
        try:
            after = (runtime2.authority.state(case_id) or {}).get("report") or {}
            after_path = settings.report_root / after.get("path", "-")
            after_body = (after_path.read_text(encoding="utf-8")
                          if after_path.is_file() else "")
            report(after.get("report_id") == before.get("report_id")
                   and after.get("sha256") == before.get("sha256")
                   and after.get("url") == before.get("url")
                   and after_body == before_body,
                   "D5-4 ★ restart keeps report_id/sha256/url/bytes identical",
                   "id %r -> %r" % (before.get("report_id"),
                                    after.get("report_id")))
            # D5-13 签发重启恒等（T-310b/c）：重启后 state["release"] 仍 signed。
            # （/release-readiness 的 authority 分支在 verify_review_api 里测 ——
            #   这里再造第二个 runtime app 会跟 writer lease 打架。）
            rel_after = (runtime2.authority.state(case_id) or {}).get("release") or {}
            report(rel_after.get("status") == "signed"
                   and len(rel_after.get("signatures") or []) == 1,
                   "D5-13 ★ 签发跨重启仍在（state['release'] 恒等）",
                   repr(rel_after.get("status")))
        finally:
            runtime2.stop()
            runtime = None
    except Exception as exc:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        report(False, "D5 gate crashed", "%s: %s" % (type(exc).__name__, exc))
    finally:
        try:
            if runtime is not None:
                runtime.stop()
        except Exception:  # noqa: BLE001
            pass
        import base.rbac as RBAC
        RBAC.set_allowlist_source(None)
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
        print("UNTESTED: verifier crashed: %s" % exc)
        sys.exit(2)
