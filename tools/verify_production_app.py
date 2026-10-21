#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""正式生产装配自证：fake OAuth + 权威/投影/CSRF/health。

主体：api/production_app.py、api/oauth.py、api/review_api.py、api/write_api.py、
base/auth_session.py、base/principal_directory.py、base/review_command_service.py。
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from fastapi.testclient import TestClient
    from api.oauth import FakeOAuthProvider, OAuthIdentity
    from api.production_app import ProductionSettings, SettingsError, create_production_app
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入生产装配: %s" % exc)
    sys.exit(2)


def ir():
    return {
        "ir_id": "ir-prod", "ir_version": "v1", "source_ir_version": "v1",
        "content_unit_ref": {"unit_id": "u-prod", "kind": "free_text"},
        "findings": [],
        "decision": {"state": "REVIEW", "layer": "DP3",
                     "release_status": "待放行", "obligations": []},
        "coverage": {"coverage_state": "full", "modalities_evaluated": ["text"],
                     "rules_version": "r1", "control_points_applied": ["H01"]},
        "receipt_ref": "rc-prod", "rule_snapshot": "r1", "kb_snapshot": "k1",
        "control_points_version": "cp1", "created_at": "2026-10-21T00:00:00Z",
    }


def settings(root):
    root = Path(root)
    frozen = root / "frozen"
    frozen.mkdir(mode=0o700)
    (frozen / "cases.json").write_text(json.dumps([{
        "case_id": "case-prod", "tenant": "t1", "product_line": "pump",
        "submitter_id": "u-sub", "final_reviewer_id": "u-final",
        "assignee_id": "reviewer", "actionable": True, "ir": ir(),
    }, {
        "case_id": "case-other", "tenant": "t1", "product_line": "pump",
        "submitter_id": "u-other", "final_reviewer_id": "u-final",
        "assignee_id": "reviewer", "actionable": True, "ir": ir(),
    }]), encoding="utf-8")
    principal = root / "principals.json"
    principal.write_text(json.dumps({"principals": [{
        "id": "reviewer", "tenant_id": "t1", "open_id": "ou-reviewer",
        "roles": ["dp3", "signer"], "product_lines": ["pump"],
        "product_line": "pump", "capabilities": [], "status": "active",
        "authz_version": "reviewer-v1",
    }, {
        "id": "reviewer2", "tenant_id": "t1", "open_id": "ou-reviewer2",
        "roles": ["dp3"], "product_lines": ["pump"],
        "product_line": "pump", "capabilities": [], "status": "active",
        "authz_version": "reviewer2-v1",
    }]}), encoding="utf-8")
    return ProductionSettings(
        authority_root=root / "authority",
        frozen_projection_root=frozen,
        review_projection_db=root / "projection" / "review.db",
        session_db=root / "session" / "session.db",
        access_log_path=root / "audit" / "access.jsonl",
        principal_directory=principal,
        public_origin="https://ca.example",
        oauth_client_id="cli_fake",
        oauth_client_secret="not-a-real-secret",
        oauth_redirect_uri="https://ca.example/auth/callback",
        oauth_reauth_redirect_uri="https://ca.example/auth/reauth/callback",
        oauth_scope="auth:user.id:read",
        tenant_allowlist=frozenset({"t1"}),
    )


def csrf(client):
    return client.cookies.get("csrf")


def headers(client, key):
    return {
        "Origin": "https://ca.example",
        "X-CSRF-Token": csrf(client),
        "Idempotency-Key": key,
    }


def main():
    passed = failed = 0
    root = tempfile.mkdtemp(prefix="production-app-")

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name + (" " + detail if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    try:
        cfg = settings(root)
        provider = FakeOAuthProvider({
            "good-code": OAuthIdentity("t1", "ou-reviewer", name="Reviewer"),
            "good-code-2": OAuthIdentity("t1", "ou-reviewer2", name="Reviewer 2"),
            "bad-tenant": OAuthIdentity("t2", "ou-reviewer"),
        })
        app = create_production_app(cfg, oauth_provider=provider)
        with TestClient(app, base_url="https://ca.example") as client:
            r = client.get("/healthz")
            report(r.status_code == 200 and r.json() == {"status": "ok"},
                   "C0 healthz 只报存活", r.text)
            r = client.get("/readyz")
            report(r.status_code == 200 and r.json().get("ready") is True,
                   "C1 readyz 生产依赖齐全", r.text)

            # OAuth state 在服务端生成；fake callback 建本地 opaque session。
            r = client.get("/auth/login", follow_redirects=False)
            location = r.headers.get("location", "")
            from urllib.parse import parse_qs, urlparse
            state = parse_qs(urlparse(location).query).get("state", [None])[0]
            report(r.status_code == 302 and bool(state),
                   "C2 login 产生授权 state", location)
            r = client.get("/auth/callback", params={"code": "good-code", "state": state},
                           follow_redirects=False)
            set_cookie = ";".join(r.headers.get_list("set-cookie"))
            report(r.status_code == 303
                   and "__Host-session=" in set_cookie
                   and "Secure" in set_cookie and "HttpOnly" in set_cookie
                   and "SameSite=lax" in set_cookie,
                   "C3 callback 建 Secure HttpOnly session", set_cookie)
            r = client.get("/api/v1/me")
            report(r.status_code == 200 and r.json().get("principal") == "reviewer",
                   "C4 /me 解析 tenant+open_id 本地主体", r.text)
            # 运行中撤销本地主体，已有 session 也必须立即失效。
            directory = json.loads(cfg.principal_directory.read_text(encoding="utf-8"))
            directory["principals"][0]["status"] = "revoked"
            cfg.principal_directory.write_text(json.dumps(directory), encoding="utf-8")
            revoked = client.get("/api/v1/me")
            report(revoked.status_code == 401,
                   "C4b principal 目录变更后运行中撤销立即生效", revoked.text)
            directory["principals"][0]["status"] = "active"
            directory["principals"][0]["authz_version"] = "reactivated-v2"
            cfg.principal_directory.write_text(json.dumps(directory), encoding="utf-8")
            reactivated = client.get("/api/v1/me")
            report(reactivated.status_code == 401,
                   "C4b 重新激活也不复活旧 session", reactivated.text)

            # 当前旧 session 已按 authz_version 失效；重新走正式 OAuth 继续后续测试。
            relogin = client.get("/auth/login", follow_redirects=False)
            relogin_state = parse_qs(urlparse(relogin.headers["location"]).query)["state"][0]
            client.get("/auth/callback",
                       params={"code": "good-code", "state": relogin_state},
                       follow_redirects=False)

            # reauth 必须走独立 OAuth callback，身份匹配后才签发绑定 token。
            start = client.post(
                "/api/v1/reauth/start", headers={
                    "Origin": "https://ca.example", "X-CSRF-Token": csrf(client)},
                json={"case_id": "case-prod", "action": "sign",
                      "nonce": "release-nonce"}, follow_redirects=False)
            reauth_location = start.json().get("detail") if start.status_code != 302 else start.headers.get("location", "")
            reauth_state = parse_qs(urlparse(reauth_location).query).get("state", [None])[0]
            reauth_redirect = parse_qs(urlparse(reauth_location).query).get(
                "redirect_uri", [None])[0]
            reauth_prompt = parse_qs(urlparse(reauth_location).query).get(
                "prompt", [None])[0]
            callback = client.get(
                "/auth/reauth/callback",
                params={"code": "good-code", "state": reauth_state},
                follow_redirects=False)
            step = callback.json()
            token = step.get("step_up_token")
            consumed = app.state.production_runtime.session_store.consume_step_up(
                token, "reviewer", "case-prod", "sign", "release-nonce")
            consumed_again = app.state.production_runtime.session_store.consume_step_up(
                token, "reviewer", "case-prod", "sign", "release-nonce")
            report(start.status_code == 302
                   and reauth_redirect == "https://ca.example/auth/reauth/callback"
                   and reauth_prompt == "consent"
                   and callback.status_code == 200
                   and callback.headers.get("cache-control") == "no-store"
                   and step.get("expires_in") == 300
                   and consumed and not consumed_again,
                   "C4c reauth 独立 callback 签发 5 分钟绑定单次 token",
                   repr((start.text, callback.text)))
            missing_csrf = client.post(
                "/api/v1/reauth/start", headers={"Origin": "https://ca.example"},
                json={"case_id": "case-prod", "action": "sign", "nonce": "x"})
            report(missing_csrf.status_code == 403,
                   "C4d reauth start 同样受 CSRF 门", missing_csrf.text)

            # 缺 CSRF / 错 Origin 拒绝
            r = client.post("/api/v1/cases/case-prod/claim",
                            headers={"Origin": "https://ca.example",
                                     "Idempotency-Key": "missing-csrf"}, json={})
            report(r.status_code == 403 and r.json().get("code") == "csrf_denied",
                   "C5 缺 CSRF → 403", r.text)
            r = client.post("/api/v1/cases/case-prod/claim",
                            headers={"Origin": "https://evil.example",
                                     "X-CSRF-Token": csrf(client),
                                     "Idempotency-Key": "bad-origin"}, json={})
            report(r.status_code == 403 and r.json().get("code") == "origin_denied",
                   "C6 错 Origin → 403", r.text)

            # 首批持久 review 写链
            r = client.post("/api/v1/cases/case-prod/claim",
                            headers=headers(client, "claim-1"), json={})
            claim = r.json()
            report(r.status_code == 200 and claim.get("version") == 1,
                   "C7 production claim → v1", r.text)
            r = client.post("/api/v1/cases/case-prod/actions",
                            headers=headers(client, "draft-1"),
                            json={"action": "save_draft", "version": 1,
                                  "draft": {"notes": "draft", "form": {},
                                            "evidence_selections": [], "references": []}})
            draft = r.json()
            report(r.status_code == 200 and draft.get("version") == 2
                   and draft.get("draft", {}).get("draft_id"),
                   "C8 production draft → v2", r.text)
            r = client.post("/api/v1/cases/case-prod/actions",
                            headers=headers(client, "submit-1"),
                            json={"action": "submit", "version": 2,
                                  "conclusion": {"review_notes": "approved by human"}})
            submitted = r.json()
            report(r.status_code == 200 and submitted.get("version") == 3
                   and submitted.get("status") == "closed",
                   "C9 production submit → closed/v3", r.text)
            r = client.get("/api/v1/cases/case-prod/review")
            report(r.status_code == 200 and r.json().get("version") == 3,
                   "C10 GET review 回读持久投影", r.text)
            r = client.get("/api/v1/cases/case-prod/drafts")
            report(r.status_code == 200 and len(r.json()) == 1
                   and r.json()[0]["notes"] == "draft",
                   "C11 GET drafts 回读正文", r.text)
            r = client.get("/api/v1/cases/case-prod/formal-reviews")
            report(r.status_code == 200 and len(r.json()) == 1,
                   "C12 GET formal 回读正文", r.text)

            # 同 key 同请求回放不多写
            r = client.post("/api/v1/cases/case-prod/actions",
                            headers=headers(client, "submit-1"),
                            json={"action": "submit", "version": 2,
                                  "conclusion": {"review_notes": "approved by human"}})
            report(r.status_code == 200 and r.json().get("replayed") is True,
                   "C13 同 key 重放旧结果", r.text)

            # 首批以外写能力必须关闭
            r = client.post("/api/v1/appeals", headers=headers(client, "appeal-1"),
                            json={"case_id": "case-prod", "reason": "x"})
            report(r.status_code == 501, "C14 appeal capability 关闭", r.text)
            r = client.post("/api/v1/cases/case-prod/actions",
                            headers=headers(client, "confirm-1"),
                            json={"action": "confirm", "version": 3,
                                  "finding_id": "f-missing"})
            report(r.status_code == 501, "C15 finding confirm capability 关闭", r.text)

            # logout 后旧 session 立即 401
            r = client.post("/api/v1/logout", headers={
                "Origin": "https://ca.example", "X-CSRF-Token": csrf(client)})
            report(r.status_code == 200 and r.json().get("logged_out") is True,
                   "C16 logout 成功", r.text)
            r = client.get("/api/v1/me")
            report(r.status_code == 401, "C17 logout 后 session 失效", r.text)

        # reassign 后 ACL 跟随权威 assignee；未知目标拒绝，冻结 assignee 不再承权。
        acl_root = tempfile.mkdtemp(prefix="production-reassign-acl-")
        try:
            acl_cfg = settings(acl_root)
            acl_app = create_production_app(acl_cfg, oauth_provider=provider)
            with TestClient(acl_app, base_url="https://ca.example") as old_client:
                login = old_client.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                old_client.get(
                    "/auth/callback", params={"code": "good-code", "state": state},
                    follow_redirects=False)
                old_client.post(
                    "/api/v1/cases/case-prod/claim",
                    headers=headers(old_client, "acl-claim"), json={})
                unknown = old_client.post(
                    "/api/v1/cases/case-prod/reassign",
                    headers=headers(old_client, "acl-unknown"),
                    json={"version": 1, "assignee": "does-not-exist"})
                moved = old_client.post(
                    "/api/v1/cases/case-prod/reassign",
                    headers=headers(old_client, "acl-move"),
                    json={"version": 1, "assignee": "reviewer2"})
                old_write = old_client.post(
                    "/api/v1/cases/case-prod/actions",
                    headers=headers(old_client, "acl-old-write"),
                    json={"action": "heartbeat", "version": 2})
                # 第二 cookie jar 复用同一已启动 app，不再开启第二 lifespan。
                new_client = TestClient(acl_app, base_url="https://ca.example")
                try:
                    login = new_client.get("/auth/login", follow_redirects=False)
                    state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                    new_client.get(
                        "/auth/callback", params={"code": "good-code-2", "state": state},
                        follow_redirects=False)
                    new_read = new_client.get("/api/v1/cases/case-prod/review")
                    new_write = new_client.post(
                        "/api/v1/cases/case-prod/actions",
                        headers=headers(new_client, "acl-new-write"),
                        json={"action": "heartbeat", "version": 2})
                finally:
                    new_client.close()
            report(unknown.status_code == 400 and moved.status_code == 200
                   and old_write.status_code == 403 and new_read.status_code == 200
                   and new_write.status_code == 200,
                   "C15b reassign 目标校验且写 ACL 跟随权威 assignee",
                   repr((unknown.text, moved.text, old_write.text,
                         new_read.text, new_write.text)))
        finally:
            shutil.rmtree(acl_root, ignore_errors=True)

        # 重启应用后权威/投影/幂等仍在
        app2 = create_production_app(cfg, oauth_provider=provider)
        with TestClient(app2, base_url="https://ca.example") as c2:
            r = c2.get("/readyz")
            report(r.status_code == 200, "C18 重启后 ready", r.text)
            report(app2.state.production_runtime.projection.get_case("case-prod")["version"] == 3,
                   "C19 重启后投影 v3")
            report(len(app2.state.production_runtime.authority.batches()) == 3,
                   "C20 重启后权威命令仍为3条")

        # OAuth state 重放/错 tenant 拒绝（新应用，独立 session）
        app3 = create_production_app(cfg, oauth_provider=provider)
        with TestClient(app3, base_url="https://ca.example") as c3:
            login = c3.get("/auth/login", follow_redirects=False)
            state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
            first = c3.get("/auth/callback", params={"code": "good-code", "state": state},
                           follow_redirects=False)
            replay = c3.get("/auth/callback", params={"code": "good-code", "state": state},
                            follow_redirects=False)
            report(first.status_code == 303 and replay.status_code == 400,
                   "C21 OAuth state 重放拒绝", replay.text)
            login = c3.get("/auth/login", follow_redirects=False)
            state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
            bad = c3.get("/auth/callback", params={"code": "bad-tenant", "state": state},
                         follow_redirects=False)
            report(bad.status_code == 403, "C22 非 allowlist tenant 拒绝", bad.text)

        # OAuth state 必须绑定发起登录的浏览器；另一 cookie jar 不能代领 callback。
        bind_root = tempfile.mkdtemp(prefix="oauth-binding-")
        try:
            bind_cfg = settings(bind_root)
            bind_app = create_production_app(bind_cfg, oauth_provider=provider)
            with TestClient(bind_app, base_url="https://ca.example") as owner:
                login = owner.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                stranger = TestClient(bind_app, base_url="https://ca.example")
                try:
                    stolen = stranger.get(
                        "/auth/callback", params={"code": "good-code", "state": state},
                        follow_redirects=False)
                finally:
                    stranger.close()
                proper = owner.get(
                    "/auth/callback", params={"code": "good-code", "state": state},
                    follow_redirects=False)
                report(stolen.status_code == 400 and proper.status_code == 303,
                       "C22b OAuth state 绑定发起浏览器且错误尝试不消费 state",
                       stolen.text)
        finally:
            shutil.rmtree(bind_root, ignore_errors=True)

        # 投影失败：权威保留、POST 202、普通 GET 503，只有 token 可读本次权威结果。
        lag_root = tempfile.mkdtemp(prefix="production-lag-")
        try:
            lag_cfg = settings(lag_root)
            lag_app = create_production_app(lag_cfg, oauth_provider=provider)
            with TestClient(lag_app, base_url="https://ca.example") as lag_client:
                login = lag_client.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                lag_client.get("/auth/callback",
                               params={"code": "good-code", "state": state},
                               follow_redirects=False)
                projection = lag_app.state.production_runtime.projection
                original_apply = projection.apply_batch

                def fail_projection(_batch):
                    raise RuntimeError("projection-sentinel")

                projection.apply_batch = fail_projection
                write = lag_client.post(
                    "/api/v1/cases/case-prod/claim",
                    headers=headers(lag_client, "lag-claim"), json={})
                write_body = write.json()
                report(write.status_code == 202
                       and write_body.get("projection_lag") is True
                       and write_body.get("version") == 1
                       and isinstance(write_body.get("reconcile_token"), str),
                       "C24 投影失败但权威成功 → 202", write.text)
                token = write_body.get("reconcile_token")
                ordinary = lag_client.get("/api/v1/cases/case-prod/review")
                report(ordinary.status_code == 503
                       and "projection_lag" in ordinary.text
                       and '"version":1' not in ordinary.text,
                       "C25 普通 GET 不把旧投影冒充当前值", ordinary.text)
                generic = lag_client.get("/api/v1/cases/case-prod")
                queue = lag_client.get("/api/v1/queue")
                cases = lag_client.get("/api/v1/cases")
                report(generic.status_code == 503
                       and queue.status_code == 503 and cases.status_code == 503
                       and "projection_lag" in generic.text,
                       "C25b Web case/queue/list GET 全过 freshness 门", generic.text)
                read_your_write = lag_client.get(
                    "/api/v1/cases/case-prod/review",
                    headers={"X-Reconcile-Token": token})
                ryw = read_your_write.json()
                report(read_your_write.status_code == 200
                       and ryw.get("source") == "authority"
                       and ryw.get("result", {}).get("version") == 1,
                       "C26 本次 token authority read-your-write", read_your_write.text)
                cross_case = lag_client.get(
                    "/api/v1/cases/case-other/review",
                    headers={"X-Reconcile-Token": token})
                report(cross_case.status_code == 503
                       and '"source":"authority"' not in cross_case.text,
                       "C26b token 不跨 case", cross_case.text)
                wrong = lag_client.get(
                    "/api/v1/cases/case-prod/review",
                    headers={"X-Reconcile-Token": "x" * 32})
                report(wrong.status_code == 503,
                       "C27 错 token 仍拒绝旧投影", wrong.text)
                report(lag_app.state.production_runtime.authority.head()["seq"] == 1,
                       "C28 202 不回滚权威")
                projection.apply_batch = original_apply
        finally:
            shutil.rmtree(lag_root, ignore_errors=True)

        # draft/formal 在投影失败时必须真正消费 authority result，不可返回空列表。
        content_lag_root = tempfile.mkdtemp(prefix="production-content-lag-")
        try:
            content_cfg = settings(content_lag_root)
            content_app = create_production_app(content_cfg, oauth_provider=provider)
            with TestClient(content_app, base_url="https://ca.example") as content_client:
                login = content_client.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                content_client.get(
                    "/auth/callback", params={"code": "good-code", "state": state},
                    follow_redirects=False)
                content_client.post(
                    "/api/v1/cases/case-prod/claim",
                    headers=headers(content_client, "content-claim"), json={})
                projection = content_app.state.production_runtime.projection
                original_apply = projection.apply_batch
                projection.apply_batch = lambda _batch: (_ for _ in ()).throw(
                    RuntimeError("content-lag"))
                saved = content_client.post(
                    "/api/v1/cases/case-prod/actions",
                    headers=headers(content_client, "content-draft"),
                    json={"action": "save_draft", "version": 1,
                          "draft": {"notes": "authority-draft", "form": {},
                                    "evidence_selections": [], "references": []}})
                saved_body = saved.json()
                draft_token = saved_body.get("reconcile_token")
                draft_id = (saved_body.get("draft") or {}).get("draft_id")
                no_token = content_client.get("/api/v1/cases/case-prod/drafts")
                with_token = content_client.get(
                    "/api/v1/cases/case-prod/drafts",
                    headers={"X-Reconcile-Token": draft_token})
                draft_by_id = content_client.get(
                    "/api/v1/drafts/%s" % draft_id,
                    headers={"X-Reconcile-Token": draft_token})
                report(saved.status_code == 202 and no_token.status_code == 503
                       and with_token.status_code == 200
                       and with_token.json()[0]["notes"] == "authority-draft"
                       and draft_by_id.status_code == 200,
                       "C28b draft 202 后仅正确 token 可读 authority 正文",
                       repr((no_token.text, with_token.text)))
                projection.apply_batch = original_apply
                # 先补齐 draft 投影，再让 submit 自身失败，得到 formal token。
                Projector = __import__("base.projector", fromlist=["Projector"]).Projector
                Projector(content_app.state.production_runtime.authority, projection).catch_up()
                projection.apply_batch = lambda _batch: (_ for _ in ()).throw(
                    RuntimeError("formal-lag"))
                submitted = content_client.post(
                    "/api/v1/cases/case-prod/actions",
                    headers=headers(content_client, "content-submit"),
                    json={"action": "submit", "version": 2,
                          "conclusion": {"review_notes": "authority-formal"}})
                formal_token = submitted.json().get("reconcile_token")
                no_token = content_client.get(
                    "/api/v1/cases/case-prod/formal-reviews")
                with_token = content_client.get(
                    "/api/v1/cases/case-prod/formal-reviews",
                    headers={"X-Reconcile-Token": formal_token})
                report(submitted.status_code == 202 and no_token.status_code == 503
                       and with_token.status_code == 200
                       and with_token.json()[0]["conclusion"]["review_notes"] ==
                       "authority-formal",
                       "C28c formal 202 后仅正确 token 可读 authority 正文",
                       repr((no_token.text, with_token.text)))
                projection.apply_batch = original_apply
        finally:
            shutil.rmtree(content_lag_root, ignore_errors=True)

        # readiness 每次真探本地依赖；缓存的布尔不能掩盖现场故障。
        ready_root = tempfile.mkdtemp(prefix="production-ready-faults-")
        try:
            ready_cfg = settings(ready_root)
            ready_app = create_production_app(ready_cfg, oauth_provider=provider)
            with TestClient(ready_app, base_url="https://ca.example") as ready_client:
                runtime = ready_app.state.production_runtime
                original_reconcile = runtime.service.reconcile
                calls = [0]

                def transient_reconcile():
                    calls[0] += 1
                    if calls[0] == 1:
                        raise RuntimeError("transient-maintenance")
                    return original_reconcile()

                runtime.service.reconcile = transient_reconcile
                first_maintenance = runtime.maintain_once()
                second_maintenance = runtime.maintain_once()
                report(not first_maintenance and second_maintenance
                       and runtime.ready and runtime.ready_error is None,
                       "C29b sweeper 瞬时失败后下一轮自动恢复 ready")
                runtime.service.reconcile = original_reconcile
                original_lock = runtime.lease.path.read_bytes()
                runtime.lease.path.write_text(
                    json.dumps({"pid": 1, "owner": "other"}), encoding="utf-8")
                r = ready_client.get("/readyz")
                report(r.status_code == 503
                       and r.json()["checks"]["writer_lease"] is False,
                       "C30 writer lease 丢失 → not ready", r.text)
                runtime.lease.path.write_bytes(original_lock)
                runtime.session_store.close()
                r = ready_client.get("/readyz")
                report(r.status_code == 503
                       and r.json()["checks"]["session_db"] is False,
                       "C31 session DB 不可用 → not ready", r.text)
                authority_state = runtime.authority.state("case-prod")
                projected_state = runtime.projection.get_case("case-prod")
                health = ready_client.get("/healthz")
                report(health.status_code == 200
                       and authority_state["case_id"] == "case-prod"
                       and projected_state is None,
                       "C31b session 故障不影响 health/权威/业务投影直读")
                runtime.projection.close()
                r = ready_client.get("/readyz")
                report(r.status_code == 503
                       and r.json()["checks"]["projection_fresh"] is False
                       and str(ready_cfg.review_projection_db) not in r.text
                       and "ProgrammingError" not in r.text,
                       "C32 projection 不可用 → 503 且低敏", r.text)
        finally:
            shutil.rmtree(ready_root, ignore_errors=True)

        # 反方向：业务投影坏时 session 认证仍可用，但 ready 必须 503。
        projection_fault_root = tempfile.mkdtemp(prefix="production-projection-fault-")
        try:
            projection_cfg = settings(projection_fault_root)
            projection_app = create_production_app(projection_cfg, oauth_provider=provider)
            with TestClient(projection_app, base_url="https://ca.example") as projection_client:
                login = projection_client.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                projection_client.get(
                    "/auth/callback", params={"code": "good-code", "state": state},
                    follow_redirects=False)
                projection_app.state.production_runtime.projection.close()
                me = projection_client.get("/api/v1/me")
                ready = projection_client.get("/readyz")
                report(me.status_code == 200 and ready.status_code == 503
                       and ready.json()["checks"]["session_db"] is True
                       and ready.json()["checks"]["projection_fresh"] is False,
                       "C32a projection 故障不影响 session 认证", repr((me.text, ready.text)))
        finally:
            shutil.rmtree(projection_fault_root, ignore_errors=True)

        # authority event 在运行中被篡改，ready 必须真回读 hash 并变 503。
        authority_fault_root = tempfile.mkdtemp(prefix="production-authority-fault-")
        try:
            authority_cfg = settings(authority_fault_root)
            authority_app = create_production_app(authority_cfg, oauth_provider=provider)
            with TestClient(authority_app, base_url="https://ca.example") as authority_client:
                login = authority_client.get("/auth/login", follow_redirects=False)
                state = parse_qs(urlparse(login.headers["location"]).query)["state"][0]
                authority_client.get(
                    "/auth/callback", params={"code": "good-code", "state": state},
                    follow_redirects=False)
                authority_client.post(
                    "/api/v1/cases/case-prod/claim",
                    headers=headers(authority_client, "authority-fault"), json={})
                event = authority_cfg.authority_root / "events/cmd-000000000001.json"
                event.write_bytes(event.read_bytes() + b"tamper")
                r = authority_client.get("/readyz")
                report(r.status_code == 503
                       and r.json()["checks"]["authority_chain"] is False
                       and str(authority_cfg.authority_root) not in r.text,
                       "C32b authority hash 篡改 → 503 且低敏", r.text)
        finally:
            shutil.rmtree(authority_fault_root, ignore_errors=True)

        # 严格 frozen projection：坏 JSON 不得退化为空集合。
        bad_frozen_root = tempfile.mkdtemp(prefix="production-bad-frozen-")
        try:
            bad_cfg = settings(bad_frozen_root)
            (bad_cfg.frozen_projection_root / "cases.json").write_text(
                "{not-json", encoding="utf-8")
            try:
                create_production_app(bad_cfg, oauth_provider=provider)
                denied = False
            except RuntimeError as exc:
                denied = "frozen_projection_unreadable:cases.json" in str(exc)
            report(denied, "C33 坏 frozen cases 启动前 fail closed")
            (bad_cfg.frozen_projection_root / "cases.json").write_text(
                json.dumps([{"case_id": "shape-only"}]), encoding="utf-8")
            try:
                create_production_app(bad_cfg, oauth_provider=provider)
                denied = False
            except RuntimeError as exc:
                denied = "frozen_projection_case_shape:0" in str(exc)
            report(denied, "C33b frozen case 元素缺字段同样 fail closed")
        finally:
            shutil.rmtree(bad_frozen_root, ignore_errors=True)

        # start 中途失败必须清理 lease，修好配置后同进程能立即重试。
        cleanup_root = tempfile.mkdtemp(prefix="production-start-cleanup-")
        try:
            cleanup_cfg = settings(cleanup_root)
            cleanup_cfg.principal_directory.write_text(
                json.dumps({"principals": []}), encoding="utf-8")
            bad_app = create_production_app(cleanup_cfg, oauth_provider=provider)
            try:
                with TestClient(bad_app, base_url="https://ca.example"):
                    pass
                startup_failed = False
            except Exception as exc:  # noqa: BLE001
                startup_failed = "principal_directory_empty" in str(exc)
            lock_exists = (cleanup_cfg.authority_root / "writer.lock").exists()
            retry_lease = __import__(
                "base.business_event_store", fromlist=["WriterLease"]).WriterLease(
                    cleanup_cfg.authority_root / "writer.lock")
            try:
                retry_lease.acquire()
                reacquired = True
            except Exception:  # noqa: BLE001
                reacquired = False
            finally:
                retry_lease.release()
            report(startup_failed and lock_exists and reacquired,
                   "C34 启动中途失败释放 OS writer lease（锁文件可保留）")
        finally:
            shutil.rmtree(cleanup_root, ignore_errors=True)

        # 第二实例指向同一权威目录时必须抢不到 writer lease。
        first_app = create_production_app(cfg, oauth_provider=provider)
        with TestClient(first_app, base_url="https://ca.example"):
            second_app = create_production_app(cfg, oauth_provider=provider)
            try:
                with TestClient(second_app, base_url="https://ca.example"):
                    second_denied = False
            except Exception as exc:  # noqa: BLE001
                second_denied = "writer_lease_held" in str(exc)
            report(second_denied, "C29 第二生产实例 writer lease 拒绝")

        # 严格配置缺失必须启动前红
        try:
            ProductionSettings.from_env({})
            denied = False
        except SettingsError:
            denied = True
        report(denied, "C23 缺生产配置 fail closed")
        env_root = Path(tempfile.mkdtemp(prefix="production-env-"))
        try:
            common = {
                "REVIEW_AUTHORITY_ROOT": str(env_root / "authority"),
                "REVIEW_FROZEN_PROJECTION_ROOT": str(env_root / "frozen"),
                "REVIEW_PROJECTION_DB": str(env_root / "same.db"),
                "REVIEW_API_SESSION_DB": str(env_root / "same.db"),
                "REVIEW_API_ACCESS_LOG": str(env_root / "access.jsonl"),
                "REVIEW_PRINCIPAL_DIRECTORY": str(env_root / "principals.json"),
                "REVIEW_PUBLIC_ORIGIN": "https://ca.example",
                "REVIEW_OAUTH_CLIENT_ID": "cli_independent",
                "REVIEW_OAUTH_CLIENT_SECRET": "not-real",
                "REVIEW_OAUTH_REDIRECT_URI": "https://ca.example/auth/callback",
                "REVIEW_OAUTH_REAUTH_REDIRECT_URI": "https://ca.example/auth/reauth/callback",
                "REVIEW_TENANT_ALLOWLIST": "t1",
            }
            try:
                ProductionSettings.from_env(common)
                denied = False
            except SettingsError as exc:
                denied = str(exc) == "data_paths_must_be_distinct"
            report(denied, "C23b session/projection/audit 等路径必须彼此独立")
            # live gate 的敏感结论必须包含 reauth consent/step-up hash/generation。
            live_gate_src = (ROOT / "tools/verify_feishu_web_oauth_live.py").read_text(
                encoding="utf-8")
            report(all(term in live_gate_src for term in (
                "fresh_consent_confirmed", "reauth_flow_verified",
                "step_up_single_use", "step_up_token_hashed",
                "session_generation_verified")),
                "C23c live OAuth evidence 不止登录，含 reauth/step-up/generation")
        finally:
            shutil.rmtree(env_root, ignore_errors=True)

    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("----------------------------------------")
    if not failed:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
