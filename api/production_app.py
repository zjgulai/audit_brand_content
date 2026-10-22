#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""严格生产装配：持久权威/投影、独立飞书OAuth、health/readiness。"""
from __future__ import annotations

import asyncio
import json
import os
import re
import stat
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode, urlparse

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.oauth import FeishuWebOAuthProvider, OAuthError
from api.review_api import AuthorityCaseSource, FileProjectionRepository, create_app
from base.auth_session import SessionStore
from base.business_event_store import BusinessEventStore, WriterLease
from base.principal_directory import PrincipalDirectory
from base.projection_store import ProjectionStore
from base.projector import Projector
from base.rbac import can_act, can_read_content
from base.review_command_service import ReviewCommandService
from base.submission_service import SubmissionIngestor


PRODUCTION_WRITE_PATHS = {
    "/api/v1/submissions",
    "/api/v1/cases/{id}/claim",
    "/api/v1/cases/{id}/unclaim",
    "/api/v1/cases/{id}/reassign",
    "/api/v1/cases/{id}/actions",
}
COOKIE_NAME = "__Host-session"
OAUTH_BIND_COOKIE = "__Host-oauth-bind"
REAUTH_BIND_COOKIE = "__Host-reauth-bind"


class ReauthStartBody(BaseModel):
    case_id: str
    action: str
    nonce: str


class RuntimeProxy:
    def __init__(self, runtime, attribute):
        self.runtime = runtime
        self.attribute = attribute

    def _target(self):
        target = getattr(self.runtime, self.attribute, None)
        if target is None:
            raise RuntimeError("runtime_not_started:%s" % self.attribute)
        return target

    def __getattr__(self, name):
        return getattr(self._target(), name)


class SettingsError(Exception):
    pass


@dataclass(frozen=True)
class ProductionSettings:
    authority_root: Path
    frozen_projection_root: Path
    review_projection_db: Path
    session_db: Path
    access_log_path: Path
    principal_directory: Path
    public_origin: str
    oauth_client_id: str
    oauth_client_secret: str
    oauth_redirect_uri: str
    oauth_reauth_redirect_uri: str | None = None
    oauth_scope: str = "auth:user.id:read"
    tenant_allowlist: frozenset[str] = frozenset()

    def __post_init__(self):
        path_names = (
            "authority_root", "frozen_projection_root", "review_projection_db",
            "session_db", "access_log_path", "principal_directory",
        )
        repo = Path(__file__).resolve().parent.parent
        paths = []
        for name in path_names:
            raw = getattr(self, name)
            if str(raw) == ":memory:":
                raise SettingsError(name + "_memory_forbidden")
            path = Path(raw).expanduser().resolve()
            if path == repo or repo in path.parents:
                raise SettingsError(name + "_inside_repository")
            object.__setattr__(self, name, path)
            paths.append((name, path))
        for index, (left_name, left) in enumerate(paths):
            for right_name, right in paths[index + 1:]:
                if left == right or left in right.parents or right in left.parents:
                    raise SettingsError("data_paths_overlap:%s:%s" %
                                        (left_name, right_name))
        origin = self.public_origin.rstrip("/")
        parsed = urlparse(origin)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path:
            raise SettingsError("public_origin_must_be_https_origin")
        object.__setattr__(self, "public_origin", origin)
        if self.oauth_redirect_uri != origin + "/auth/callback":
            raise SettingsError("oauth_redirect_mismatch")
        reauth_redirect = (self.oauth_reauth_redirect_uri or
                           origin + "/auth/reauth/callback")
        if reauth_redirect != origin + "/auth/reauth/callback":
            raise SettingsError("oauth_reauth_redirect_mismatch")
        object.__setattr__(self, "oauth_reauth_redirect_uri", reauth_redirect)
        if not self.oauth_client_id.startswith("cli_") or not self.oauth_client_secret:
            raise SettingsError("oauth_config")
        if "auth:user.id:read" not in set(self.oauth_scope.split()):
            raise SettingsError("oauth_scope_missing_user_id")
        if not self.tenant_allowlist:
            raise SettingsError("tenant_allowlist_empty")

    @staticmethod
    def from_env(env=None):
        env = dict(os.environ if env is None else env)
        required = (
            "REVIEW_AUTHORITY_ROOT", "REVIEW_FROZEN_PROJECTION_ROOT",
            "REVIEW_PROJECTION_DB", "REVIEW_API_SESSION_DB",
            "REVIEW_API_ACCESS_LOG", "REVIEW_PRINCIPAL_DIRECTORY",
            "REVIEW_PUBLIC_ORIGIN", "REVIEW_OAUTH_CLIENT_ID",
            "REVIEW_OAUTH_CLIENT_SECRET", "REVIEW_OAUTH_REDIRECT_URI",
            "REVIEW_OAUTH_REAUTH_REDIRECT_URI", "REVIEW_TENANT_ALLOWLIST",
        )
        missing = [key for key in required if not env.get(key)]
        if missing:
            raise SettingsError("missing_config:" + ",".join(missing))
        origin = env["REVIEW_PUBLIC_ORIGIN"].rstrip("/")
        parsed = urlparse(origin)
        if parsed.scheme != "https" or not parsed.netloc or parsed.path:
            raise SettingsError("public_origin_must_be_https_origin")
        redirect = env["REVIEW_OAUTH_REDIRECT_URI"]
        if redirect != origin + "/auth/callback":
            raise SettingsError("oauth_redirect_mismatch")
        repo = Path(__file__).resolve().parent.parent

        def external(name, *, directory=False):
            raw = env[name]
            if raw == ":memory:":
                raise SettingsError(name + "_memory_forbidden")
            path = Path(raw).expanduser().resolve()
            if path == repo or repo in path.parents:
                raise SettingsError(name + "_inside_repository")
            return path

        tenants = frozenset(x.strip() for x in
                            env["REVIEW_TENANT_ALLOWLIST"].split(",") if x.strip())
        if not tenants:
            raise SettingsError("tenant_allowlist_empty")
        authority_root = external("REVIEW_AUTHORITY_ROOT", directory=True)
        frozen_root = external("REVIEW_FROZEN_PROJECTION_ROOT", directory=True)
        projection_db = external("REVIEW_PROJECTION_DB")
        session_db = external("REVIEW_API_SESSION_DB")
        access_log = external("REVIEW_API_ACCESS_LOG")
        principal_directory = external("REVIEW_PRINCIPAL_DIRECTORY")
        paths = (authority_root, frozen_root, projection_db, session_db,
                 access_log, principal_directory)
        if len(set(paths)) != len(paths):
            raise SettingsError("data_paths_must_be_distinct")
        return ProductionSettings(
            authority_root=authority_root,
            frozen_projection_root=frozen_root,
            review_projection_db=projection_db,
            session_db=session_db,
            access_log_path=access_log,
            principal_directory=principal_directory,
            public_origin=origin,
            oauth_client_id=env["REVIEW_OAUTH_CLIENT_ID"],
            oauth_client_secret=env["REVIEW_OAUTH_CLIENT_SECRET"],
            oauth_redirect_uri=redirect,
            oauth_reauth_redirect_uri=env["REVIEW_OAUTH_REAUTH_REDIRECT_URI"],
            oauth_scope=env.get("REVIEW_OAUTH_SCOPE", "auth:user.id:read"),
            tenant_allowlist=tenants,
        )


class ProductionRuntime:
    def __init__(self, settings, *, oauth_provider=None):
        self.settings = settings
        self.oauth_provider = oauth_provider or FeishuWebOAuthProvider(
            client_id=settings.oauth_client_id,
            client_secret=settings.oauth_client_secret)
        self.lease = WriterLease(settings.authority_root / "writer.lock")
        self.session_store = None
        self.authority = None
        self.projection = None
        self.service = None
        self.directory = None
        self.ready = False
        self.ready_error = "not_started"

    @staticmethod
    def _ensure_private_dir(path):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise SettingsError("data_permissions")

    def start(self):
        try:
            for directory in (
                self.settings.authority_root,
                self.settings.review_projection_db.parent,
                self.settings.session_db.parent,
                self.settings.access_log_path.parent,
            ):
                self._ensure_private_dir(directory)
            if not self.settings.frozen_projection_root.is_dir():
                raise SettingsError("frozen_projection_missing")
            self.lease.acquire()
            self.session_store = SessionStore(
                str(self.settings.session_db),
                step_up_audit_path=str(
                    self.settings.access_log_path.parent / "step-up-audit.jsonl"),
                auth_audit_path=str(
                    self.settings.access_log_path.parent / "auth-audit.jsonl"),
                generation_file=str(
                    self.settings.access_log_path.parent / "session-generation"))
            self.directory = PrincipalDirectory(
                self.settings.principal_directory, require_authz_version=True)
            if not self.directory.ready():
                raise SettingsError("principal_directory_empty")
            self.authority = BusinessEventStore(
                self.settings.authority_root, lease=self.lease)
            self.projection = ProjectionStore(self.settings.review_projection_db)
            Projector(self.authority, self.projection).catch_up()
            if self.projection.status(self.authority.head())["status"] != "fresh":
                raise SettingsError("projection_not_fresh")
            self.service = ReviewCommandService(self.authority, self.projection)
            self.ready = True
            self.ready_error = None
        except Exception as exc:
            self.ready = False
            self.ready_error = getattr(exc, "code", str(exc).split(":", 1)[0])
            self.stop(error_code=self.ready_error)
            raise

    def stop(self, *, error_code="stopping"):
        self.ready = False
        self.ready_error = error_code
        if self.projection is not None:
            self.projection.close()
            self.projection = None
        if self.session_store is not None:
            self.session_store.close()
            self.session_store = None
        self.service = None
        self.authority = None
        self.lease.release()

    def maintain_once(self):
        if self.service is None or self.authority is None:
            raise RuntimeError("runtime_not_started:maintenance")
        try:
            self.service.reconcile()
            for case_id in self.authority.aggregate_ids():
                self.service.expire_if_due(case_id)
            self.lease.assert_owner()
            if not self.session_store.ready() or not self.directory.ready():
                raise RuntimeError("maintenance_dependency_unavailable")
            self.ready = True
            self.ready_error = None
            return True
        except Exception as exc:
            self.ready = False
            self.ready_error = getattr(exc, "code", "lease_sweeper_failed")
            return False

    def readiness(self):
        lease_ok = False
        if self.lease.acquired:
            try:
                self.lease.assert_owner()
                lease_ok = True
            except Exception:
                lease_ok = False
        permissions_ok = True
        for directory in (
            self.settings.authority_root,
            self.settings.review_projection_db.parent,
            self.settings.session_db.parent,
            self.settings.access_log_path.parent,
        ):
            try:
                permissions_ok = permissions_ok and not (
                    stat.S_IMODE(directory.stat().st_mode) & 0o077)
            except OSError:
                permissions_ok = False
        authority_ok = False
        projection_ok = False
        if self.service is not None:
            try:
                status = self.service.status()
                authority_ok = True
                projection_ok = status["status"] == "fresh"
            except Exception:
                authority_ok = False
                projection_ok = False
        checks = {
            "config": self.settings is not None,
            "authority_chain": authority_ok,
            "projection_fresh": projection_ok,
            "session_db": bool(self.session_store and self.session_store.ready()),
            "writer_lease": lease_ok,
            "data_permissions": permissions_ok,
            "principal_directory": bool(self.directory and self.directory.ready()),
        }
        ready = self.ready and all(checks.values())
        return {"ready": ready,
                "checks": checks,
                "error_code": None if ready else (self.ready_error or "not_ready")}


def _origin_ok(request, origin):
    supplied = request.headers.get("origin")
    if supplied:
        return supplied.rstrip("/") == origin
    referer = request.headers.get("referer")
    return bool(referer and referer.startswith(origin + "/"))


def _runtime_review_service(runtime):
    service = runtime.service
    if service is None:
        raise RuntimeError("runtime_not_started:service")
    return service


def _runtime_projection(runtime):
    projection = runtime.projection
    if projection is None:
        raise RuntimeError("runtime_not_started:projection")
    return projection


def create_production_app(settings: ProductionSettings, *, oauth_provider=None):
    runtime = ProductionRuntime(settings, oauth_provider=oauth_provider)

    @asynccontextmanager
    async def lifespan(_app):
        runtime.start()
        stop_sweeper = asyncio.Event()

        async def sweep_expired():
            while not stop_sweeper.is_set():
                runtime.maintain_once()
                try:
                    await asyncio.wait_for(stop_sweeper.wait(), timeout=30)
                except asyncio.TimeoutError:
                    pass

        sweeper = asyncio.create_task(sweep_expired())
        try:
            yield
        finally:
            stop_sweeper.set()
            await sweeper
            runtime.stop()

    # 创建时只组装路由；真正的 store 在 lifespan.start 后通过代理 provider 使用。
    # cases.json 不再是必需文件：新案件由 authority case source 提供。
    frozen = FileProjectionRepository(
        settings.frozen_projection_root, strict=True, require_cases=False)

    def principal_provider(principal_id, tenant):
        if runtime.directory is None:
            return None
        return runtime.directory.by_id(principal_id, tenant)

    def require_projection_fresh_for_shared_route():
        if runtime.projection is None or runtime.authority is None:
            raise HTTPException(503, "projection_unavailable")
        try:
            status = runtime.projection.status(runtime.authority.head())
        except Exception as exc:
            raise HTTPException(503, "projection_unavailable") from exc
        if status["status"] != "fresh":
            raise HTTPException(503, "projection_lag")

    review_service_proxy = RuntimeProxy(runtime, "service")
    projection_proxy = RuntimeProxy(runtime, "projection")
    app = create_app(
        session_store=RuntimeProxy(runtime, "session_store"),
        repository=frozen,
        principal_provider=principal_provider,
        review_read_store=projection_proxy,
        review_command_service=review_service_proxy,
        enabled_write_capabilities=PRODUCTION_WRITE_PATHS,
        review_freshness_provider=require_projection_fresh_for_shared_route,
        case_state_provider=lambda case_id: (
            runtime.authority.state(case_id) if runtime.authority is not None else None),
        review_assignee_validator=lambda principal_id, case: bool(
            runtime.directory and runtime.directory.eligible_assignee(principal_id, case)),
        case_source=AuthorityCaseSource(RuntimeProxy(runtime, "authority")),
        submission_ingestor=SubmissionIngestor(),
        session_cookie_name=COOKIE_NAME,
        app_env="production",
        access_log_path=str(settings.access_log_path),
    )
    app.router.lifespan_context = lifespan
    app.state.production_runtime = runtime
    app.state.public_origin = settings.public_origin

    @app.middleware("http")
    async def production_gate(request: Request, call_next):
        if request.url.path in ("/healthz", "/readyz", "/auth/login", "/auth/callback",
                                "/auth/reauth/callback"):
            return await call_next(request)
        if not runtime.ready and request.url.path not in ("/api/v1/me", "/api/v1/logout"):
            return JSONResponse(status_code=503,
                                content={"code": "not_ready", "message": "服务未就绪"})
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not _origin_ok(request, settings.public_origin):
                return JSONResponse(status_code=403,
                                    content={"code": "origin_denied", "message": "Origin 校验失败"})
            cookie = request.cookies.get(COOKIE_NAME)
            token = request.headers.get("x-csrf-token")
            try:
                csrf_ok = runtime.session_store.verify_csrf(cookie, token)
            except Exception:
                runtime.ready = False
                runtime.ready_error = "session_unavailable"
                return JSONResponse(
                    status_code=503,
                    content={"code": "session_unavailable", "message": "服务未就绪"})
            if not csrf_ok:
                return JSONResponse(status_code=403,
                                    content={"code": "csrf_denied", "message": "CSRF 校验失败"})
        return await call_next(request)

    def session_or_503(cookie):
        try:
            return runtime.session_store.get_session(cookie)
        except Exception as exc:
            runtime.ready = False
            runtime.ready_error = "session_unavailable"
            raise HTTPException(503, "session_unavailable") from exc

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz", include_in_schema=False)
    def readyz():
        body = runtime.readiness()
        return JSONResponse(content=body, status_code=200 if body["ready"] else 503)

    @app.get("/auth/login", include_in_schema=False)
    def login():
        if not runtime.ready:
            raise HTTPException(503, "服务未就绪")
        nonce = os.urandom(16).hex()
        state = runtime.session_store.issue_oauth_state(
            flow="login", redirect_uri=settings.oauth_redirect_uri,
            nonce=nonce, browser_nonce=nonce, ttl=300)
        url = runtime.oauth_provider.authorize_url(
            state=state, redirect_uri=settings.oauth_redirect_uri,
            scope=settings.oauth_scope)
        response = RedirectResponse(url=url, status_code=302)
        response.set_cookie(OAUTH_BIND_COOKIE, nonce, secure=True, httponly=True,
                            samesite="lax", path="/", max_age=300)
        return response

    @app.get("/auth/callback", include_in_schema=False)
    def callback(request: Request, code: str, state: str):
        if not runtime.ready:
            raise HTTPException(503, "服务未就绪")
        browser_nonce = request.cookies.get(OAUTH_BIND_COOKIE)
        if not browser_nonce:
            raise HTTPException(400, "oauth_browser_binding_missing")
        oauth_state = runtime.session_store.consume_oauth_state(
            state, flow="login", redirect_uri=settings.oauth_redirect_uri,
            browser_nonce=browser_nonce)
        if oauth_state is None:
            raise HTTPException(400, "oauth_state_invalid")
        try:
            identity = runtime.oauth_provider.exchange_code(
                code=code, redirect_uri=settings.oauth_redirect_uri)
        except OAuthError as exc:
            raise HTTPException(401, exc.code)
        if identity.tenant_id not in settings.tenant_allowlist:
            raise HTTPException(403, "tenant_not_allowed")
        principal = runtime.directory.by_identity(identity.tenant_id, identity.open_id)
        if principal is None:
            raise HTTPException(403, "principal_not_authorized")
        csrf = os.urandom(24).hex()
        sid = runtime.session_store.create_session(
            principal["id"], tenant=identity.tenant_id,
            provider="feishu", issuer=runtime.oauth_provider.issuer,
            csrf_token=csrf, auth_time=None,
            authz_version=principal.get("authz_version"))
        response = RedirectResponse(url=settings.public_origin + "/queue", status_code=303)
        response.delete_cookie(OAUTH_BIND_COOKIE, path="/", secure=True,
                               httponly=True, samesite="lax")
        response.set_cookie(COOKIE_NAME, sid, secure=True, httponly=True,
                            samesite="lax", path="/")
        response.set_cookie("csrf", csrf, secure=True, httponly=False,
                            samesite="lax", path="/")
        return response

    @app.post("/api/v1/reauth/start", include_in_schema=False)
    def reauth_start(request: Request, body: ReauthStartBody):
        case_id, action, nonce = body.case_id, body.action, body.nonce
        if action not in ("sign", "reject", "revoke"):
            raise HTTPException(400, "reauth_action_invalid")
        if not nonce:
            raise HTTPException(400, "reauth_nonce_missing")
        principal, case = require_case_access(request, case_id)
        capability = "release.revoke" if action == "revoke" else "release.sign"
        if not can_act(principal, capability, case):
            raise HTTPException(403, "reauth_action_not_allowed")
        cookie = request.cookies.get(COOKIE_NAME)
        session = session_or_503(cookie)
        if not session:
            raise HTTPException(401, "缺少或无效 session")
        browser_nonce = os.urandom(16).hex()
        state = runtime.session_store.issue_oauth_state(
            flow="reauth", redirect_uri=settings.oauth_reauth_redirect_uri,
            nonce=nonce, principal=principal["id"], case_id=case_id,
            action=action, browser_nonce=browser_nonce, ttl=300)
        url = runtime.oauth_provider.authorize_url(
            state=state, redirect_uri=settings.oauth_reauth_redirect_uri,
            scope=settings.oauth_scope, prompt="consent")
        response = RedirectResponse(url=url, status_code=302)
        response.set_cookie(REAUTH_BIND_COOKIE, browser_nonce, secure=True,
                            httponly=True, samesite="lax", path="/", max_age=300)
        return response

    @app.get("/auth/reauth/callback", include_in_schema=False)
    def reauth_callback(request: Request, code: str, state: str):
        if not runtime.ready:
            raise HTTPException(503, "服务未就绪")
        cookie = request.cookies.get(COOKIE_NAME)
        session = session_or_503(cookie)
        if not session:
            raise HTTPException(401, "缺少或无效 session")
        browser_nonce = request.cookies.get(REAUTH_BIND_COOKIE)
        if not browser_nonce:
            raise HTTPException(400, "reauth_browser_binding_missing")
        oauth_state = runtime.session_store.consume_oauth_state(
            state, flow="reauth", redirect_uri=settings.oauth_reauth_redirect_uri,
            browser_nonce=browser_nonce)
        if oauth_state is None:
            raise HTTPException(400, "reauth_state_invalid")
        try:
            identity = runtime.oauth_provider.exchange_code(
                code=code, redirect_uri=settings.oauth_reauth_redirect_uri)
        except OAuthError as exc:
            raise HTTPException(401, exc.code)
        principal = runtime.directory.by_identity(identity.tenant_id, identity.open_id)
        if (principal is None or principal["id"] != session["principal"] or
                identity.tenant_id != session["tenant"] or
                oauth_state["principal"] != session["principal"] or
                (session.get("authz_version") is not None and
                 session.get("authz_version") != principal.get("authz_version"))):
            raise HTTPException(403, "reauth_identity_mismatch")
        token = runtime.session_store.issue_step_up(
            principal["id"], oauth_state["case_id"], oauth_state["action"],
            oauth_state["nonce"])
        response = JSONResponse({
            "step_up_token": token, "case_id": oauth_state["case_id"],
            "action": oauth_state["action"], "nonce": oauth_state["nonce"],
            "expires_in": 300,
        }, headers={"Cache-Control": "no-store", "Pragma": "no-cache"})
        response.delete_cookie(REAUTH_BIND_COOKIE, path="/", secure=True,
                               httponly=True, samesite="lax")
        return response

    def require_case_access(request, case_id):
        cookie = request.cookies.get(COOKIE_NAME)
        session = session_or_503(cookie)
        if not session:
            raise HTTPException(401, "缺少或无效 session")
        principal = runtime.directory.by_id(session["principal"], session["tenant"])
        if (principal is None or
                (session.get("authz_version") is not None and
                 session.get("authz_version") != principal.get("authz_version"))):
            raise HTTPException(401, "主体授权已变化，请重新登录")
        case = frozen.get_case(case_id)
        if case is None:
            raise HTTPException(404, "案件不存在")
        effective = dict(case)
        live = runtime.authority.state(case_id)
        effective["assignee_id"] = live.get("assignee")
        effective["actionable"] = live.get("status") in ("unassigned", "released")
        if principal is None or not can_read_content(principal, effective):
            raise HTTPException(403, "无权读取该案件内容")
        return principal, case

    def ensure_projection_fresh(request, principal, case_id):
        projection = _runtime_projection(runtime)
        try:
            status = projection.status(runtime.authority.head())
        except Exception as exc:
            raise HTTPException(503, "projection_unavailable") from exc
        if status["status"] == "fresh":
            return None
        token = request.headers.get("x-reconcile-token")
        if token:
            value = _runtime_review_service(runtime).read_your_write(
                token, aggregate_id=case_id,
                principal_id=principal["id"], tenant_id=principal["tenant_id"])
            if value is not None:
                return value
        raise HTTPException(503, "projection_lag")

    @app.get("/api/v1/cases/{case_id}/review")
    def review_summary(case_id: str, request: Request):
        principal, _case = require_case_access(request, case_id)
        authority = ensure_projection_fresh(request, principal, case_id)
        if authority is not None:
            return {"source": "authority", **authority}
        return _runtime_projection(runtime).get_case(case_id) or {
            "case_id": case_id, "status": "unassigned", "version": 0,
            "assignee": None,
        }

    @app.get("/api/v1/cases/{case_id}/drafts")
    def drafts(case_id: str, request: Request):
        principal, _case = require_case_access(request, case_id)
        authority = ensure_projection_fresh(request, principal, case_id)
        if authority is not None:
            draft = authority["result"].get("draft")
            if draft is None:
                raise HTTPException(503, "projection_lag")
            return [draft]
        return _runtime_projection(runtime).list_drafts(case_id)

    @app.get("/api/v1/drafts/{draft_id}")
    def draft(draft_id: str, request: Request):
        projection = _runtime_projection(runtime)
        value = projection.get_draft(draft_id)
        token = request.headers.get("x-reconcile-token")
        if value is None and token:
            service = _runtime_review_service(runtime)
            raw = service.read_your_write(token)
            result = (raw or {}).get("result") or {}
            candidate = result.get("draft")
            case_id = result.get("case_id")
            if isinstance(candidate, dict) and candidate.get("draft_id") == draft_id and case_id:
                principal, _case = require_case_access(request, case_id)
                raw = service.read_your_write(
                    token, aggregate_id=case_id,
                    principal_id=principal["id"], tenant_id=principal["tenant_id"])
                if raw is not None:
                    return candidate
        if value is None:
            status = projection.status(runtime.authority.head())
            if status["status"] != "fresh":
                raise HTTPException(503, "projection_lag")
            raise HTTPException(404, "draft 不存在")
        principal, _case = require_case_access(request, value["case_id"])
        ensure_projection_fresh(request, principal, value["case_id"])
        return value

    @app.get("/api/v1/cases/{case_id}/formal-reviews")
    def formal_reviews(case_id: str, request: Request):
        principal, _case = require_case_access(request, case_id)
        authority = ensure_projection_fresh(request, principal, case_id)
        if authority is not None:
            formal = authority["result"].get("formal")
            if formal is None:
                raise HTTPException(503, "projection_lag")
            return [formal]
        return _runtime_projection(runtime).list_formal(case_id)

    @app.get("/api/v1/me")
    def me(request: Request):
        cookie = request.cookies.get(COOKIE_NAME)
        session = session_or_503(cookie)
        if not session:
            raise HTTPException(401, "缺少或无效 session")
        principal = runtime.directory.by_id(session["principal"], session["tenant"])
        if principal is None:
            raise HTTPException(401, "principal 已撤销")
        if (session.get("authz_version") is not None and
                session.get("authz_version") != principal.get("authz_version")):
            raise HTTPException(401, "主体授权已变化，请重新登录")
        return {"principal": principal["id"], "tenant": principal["tenant_id"],
                "roles": principal["roles"], "product_lines": principal["product_lines"]}

    @app.post("/api/v1/logout")
    def logout(request: Request):
        cookie = request.cookies.get(COOKIE_NAME)
        runtime.session_store.revoke_session(cookie, reason="user_logout")
        response = JSONResponse({"logged_out": True})
        response.delete_cookie(COOKIE_NAME, path="/", secure=True, httponly=True,
                               samesite="lax")
        response.delete_cookie("csrf", path="/", secure=True, samesite="lax")
        return response

    # ── SPA 静态产物 ────────────────────────────────────────────────────
    # ★ 2026-10-22：原计划由宿主机共享反代 `ai_video_nginx` 直接 serve，
    #   但实测它在**容器里**，看不到宿主机新目录（`/opt/momcozy-audit-platform/web`
    #   不在它的挂载表里）。给共享反代加挂载点等于改动 40+ 站点的容器配置，
    #   风险不成比例。改为**由本服务自己 serve**：反代只需 proxy_pass 到 :18000。
    #
    # ★ 必须挂在**最后**：mount 会吃掉该前缀下的所有路由，
    #   先挂会让 /api/ 与 /auth/ 一起被当成静态文件。
    _web_root = os.environ.get("AUDIT_WEB_ROOT") or "/app/web_dist"
    if os.path.isdir(_web_root):
        app.mount("/", StaticFiles(directory=_web_root, html=True), name="spa")

    return app


def app_from_env():
    return create_production_app(ProductionSettings.from_env())
