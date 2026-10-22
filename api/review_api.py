#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api/review_api.py — T2-01：review-api 只读 API

只从已落盘的 IR / 投影读状态；本文件不导入、不调用任何判定实现，
不在 API 层计算 state/layer/coverage。OpenAPI 3.1 由 FastAPI + Pydantic 生成。

鉴权：base.auth_session 的 opaque session cookie + base.rbac 的对象 ACL。

## C-103 只读入口审计（契约）

`/api/v1/rules`、`/api/v1/control-points`、`/api/v1/routing` 是**只读入口**。
对这三个路径发 `POST` / `PUT` / `PATCH` / `DELETE`：

  - 一律返回 **403**，不落任何业务数据；
  - 每次拒绝向 access-log **追加一行 JSONL**，字段固定为：
    `ts` / `principal` / `open_id` / `tenant_id` / `method` / `target` /
    `reason` / `env`；
  - access-log 路径由 `REVIEW_API_ACCESS_LOG` 指定，默认
    `~/.dsh/audit-data/access-log.jsonl`（仓外，文件 0600、目录 0700）；
  - `GET` 是正常读取，**不写** access-log。

## C-104 身份绑定（契约）

  - 生产模式下 principal 必须同时带非空 `open_id` 与 `tenant_id`，
    缺任一返回 **401**（身份不完整，无法建立绑定），并记一条
    `reason=identity_incomplete` 审计；
  - `simulated=True` 的模拟身份仅允许在 `APP_ENV=dev` 且显式设置
    `ALLOW_SIMULATED_IDENTITY=1` 时使用；生产模式（或其他未授权组合）
    返回 **403**，并记一条 `reason=simulated_identity_*` 审计；
  - `ALLOW_SIMULATED_IDENTITY=1` 与 `APP_ENV != dev` 的组合在**启动时**
    直接抛 `RuntimeError`，不允许带着这个配置跑起来；
  - principal 的 `tenant_id` 必须与 session 的 tenant 一致，否则 403
    （`reason=identity_tenant_mismatch`）。

principal 由调用方注入（测试用 mapping，生产接真实 IdP）；本模块不为它
补 `open_id` / `tenant_id` —— 缺字段就是缺字段，不会用 principal id 冒充。
"""
from __future__ import annotations

import datetime
import json
import os
import threading
from typing import Any, Dict, List, Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from base.auth_session import SessionStore
from base.rbac import can_read_content


# ───────────────────────── Pydantic 响应模型 ─────────────────────────

class Finding(BaseModel):
    model_config = ConfigDict(extra="allow")
    finding_id: str
    control_code: str
    status: str
    severity: str
    produced_by: str
    derived_from: Optional[str]
    authority_state: Optional[str] = None
    detected_by: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    quote: Optional[str] = None
    evidence_id: Optional[str] = None


class Decision(BaseModel):
    model_config = ConfigDict(extra="allow")
    state: str
    layer: str
    release_status: str
    obligations: List[str] = Field(default_factory=list)


class Coverage(BaseModel):
    model_config = ConfigDict(extra="allow")
    coverage_state: str
    modalities_evaluated: List[str] = Field(default_factory=list)
    rules_version: str
    control_points_applied: List[str] = Field(default_factory=list)
    not_evaluated_reason: List[Dict[str, Any]] = Field(default_factory=list)


class ContentUnitRef(BaseModel):
    unit_id: str
    kind: Literal["ad_text", "free_text", "landing_page", "structured_json",
                  "image", "video", "文档"]
    parse_status: Literal["ok", "partial", "failed"] = "ok"
    failure_kind: Optional[Literal["fetch_error", "parse_error", "empty",
                                   "unsupported"]] = None

    @model_validator(mode="after")
    def failed_has_kind(self):
        if self.parse_status == "failed" and not self.failure_kind:
            raise ValueError("parse_status=failed 必须带 failure_kind")
        if self.parse_status != "failed" and self.failure_kind is not None:
            raise ValueError("非 failed 不许带 failure_kind")
        return self


class ReviewIR(BaseModel):
    model_config = ConfigDict(extra="allow")
    ir_id: str
    ir_version: str
    content_unit_ref: ContentUnitRef
    source_ir_version: str
    findings: List[Finding]
    decision: Decision
    coverage: Coverage
    receipt_ref: str
    rule_snapshot: str
    kb_snapshot: str
    control_points_version: str
    created_at: str
    media_fingerprints: Optional[Dict[str, Any]] = None


class CaseSummary(BaseModel):
    case_id: str
    ir_id: Optional[str] = None
    state: Optional[str] = None
    layer: Optional[str] = None
    release_status: Optional[str] = None
    tenant: Optional[str] = None
    product_line: Optional[str] = None
    assignee_id: Optional[str] = None
    sample: Optional[bool] = None
    entry_channel: Optional[str] = None
    created_at: Optional[str] = None
    title_or_excerpt: Optional[str] = None
    high_severity_count: Optional[int] = None
    coverage_state: Optional[str] = None


class CaseDetail(BaseModel):
    case_id: str
    ir: ReviewIR
    review: Optional[Dict[str, Any]] = None
    content_unit: Optional[Dict[str, Any]] = None


class ReportSummary(BaseModel):
    report_id: str
    case_id: Optional[str] = None
    ir_id: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[str] = None


class ReportDetail(ReportSummary):
    pass


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None
    request_id: str = ""


# ───────────────────────── 只读数据源 ─────────────────────────

class InMemoryRepository:
    """冻结投影的内存副本；API 只读。"""

    def __init__(self, *, cases=None, reports=None, rules=None,
                 control_points=None, routing=None, notifications=None,
                 metrics=None, appeals=None, release_pending=None,
                 takedown_tasks=None, signer_grants=None,
                 takedown_grants=None, sessions=None,
                 release_readiness=None):
        self.cases = list(cases or [])
        self.reports = list(reports or [])
        self.rules = list(rules or [])
        self.control_points = list(control_points or [])
        self.routing = list(routing or [])
        self.notifications = list(notifications or [])
        self.metrics = dict(metrics or {})
        self.appeals = list(appeals or [])
        self.release_pending = list(release_pending or [])
        self.takedown_tasks = list(takedown_tasks or [])
        self.signer_grants = list(signer_grants or [])
        self.takedown_grants = list(takedown_grants or [])
        self.sessions = list(sessions or [])
        self.release_readiness = dict(release_readiness or {})

    def list_cases(self):
        return list(self.cases)

    def get_case(self, case_id):
        return next((c for c in self.cases if c.get("case_id") == case_id), None)

    def list_reports(self):
        return list(self.reports)

    def get_report(self, report_id):
        return next((r for r in self.reports if r.get("report_id") == report_id), None)


class FileProjectionRepository(InMemoryRepository):
    """从仓外投影目录加载 JSON；strict 模式坏/缺文件直接拒绝。

    `require_cases=False` 供生产 authority case source 使用：新案件由 authority 提供，
    frozen `cases.json` 不再是启动必需文件（缺失时按空列表，而不是启动失败）。
    """

    def __init__(self, root, *, strict=False, require_cases=True):
        def load(name, default, expected_type, *, required=False):
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8") as f:
                    value = json.load(f)
            except FileNotFoundError as exc:
                if strict and required:
                    raise RuntimeError("frozen_projection_missing:%s" % name) from exc
                return default
            except (OSError, ValueError) as exc:
                if strict:
                    raise RuntimeError("frozen_projection_unreadable:%s" % name) from exc
                return default
            if not isinstance(value, expected_type):
                if strict:
                    raise RuntimeError("frozen_projection_shape:%s" % name)
                return default
            return value

        cases = load("cases.json", [], list, required=require_cases)
        if strict:
            for index, case in enumerate(cases):
                if not isinstance(case, dict):
                    raise RuntimeError("frozen_projection_case_shape:%d" % index)
                ir = case.get("ir")
                stored_outcome = ir.get("decision") if isinstance(ir, dict) else None
                required = (case.get("case_id"), case.get("tenant"),
                            case.get("product_line"))
                if (not all(isinstance(value, str) and value for value in required)
                        or not isinstance(stored_outcome, dict)
                        or not isinstance(stored_outcome.get("state"), str)):
                    raise RuntimeError("frozen_projection_case_shape:%d" % index)

        super().__init__(
            cases=cases,
            reports=load("reports.json", [], list),
            rules=load("rules.json", [], list),
            control_points=load("control-points.json", [], list),
            routing=load("routing.json", [], list),
            notifications=load("notifications.json", [], list),
            metrics=load("metrics.json", {}, dict),
            appeals=load("appeals.json", [], list),
            release_pending=load("release-pending.json", [], list),
            takedown_tasks=load("takedown-tasks.json", [], list),
            signer_grants=load("signer-grants.json", [], list),
            takedown_grants=load("takedown-grants.json", [], list),
            sessions=load("sessions.json", [], list),
            release_readiness=load("release-readiness.json", {}, dict),
        )


class AuthorityCaseSource:
    """从 authority state 构造只读案件视图；没有 ir 的状态不算已建成的案件。"""

    def __init__(self, authority):
        self.authority = authority

    @staticmethod
    def _case(state):
        if not isinstance(state, dict) or not isinstance(state.get("ir"), dict):
            return None
        ir = state["ir"]
        return {
            "case_id": state.get("case_id"),
            "tenant": state.get("tenant"),
            "product_line": state.get("product_line"),
            "submitter_id": state.get("submitter_id"),
            "assignee_id": state.get("assignee"),
            "actionable": state.get("status") in ("unassigned", "released"),
            "ir": ir,
            "content": state.get("content"),
            "case_version": int(state.get("version") or 0),
            "ir_id": ir.get("ir_id"),
            "ir_version": ir.get("ir_version"),
        }

    def get_case(self, case_id):
        return self._case(self.authority.state(case_id))

    def list_cases(self):
        out = []
        for case_id in self.authority.aggregate_ids():
            case = self._case(self.authority.state(case_id))
            if case is not None:
                out.append(case)
        return out


class CaseOverlayRepository:
    """案件读取叠加层：authority 新建案件优先，其余集合仍走 frozen 仓库。

    只覆盖 `get_case` / `list_cases`；其他属性原样委托，避免第二份投影实现。
    """

    def __init__(self, delegate, case_source):
        self._delegate = delegate
        self._case_source = case_source

    def get_case(self, case_id):
        case = self._case_source.get_case(case_id)
        return case if case is not None else self._delegate.get_case(case_id)

    def list_cases(self):
        merged = {}
        order = []
        for case in self._delegate.list_cases():
            case_id = case.get("case_id")
            if case_id not in merged:
                order.append(case_id)
            merged[case_id] = case
        for case in self._case_source.list_cases():
            case_id = case.get("case_id")
            if case_id not in merged:
                order.append(case_id)
            merged[case_id] = case
        return [merged[case_id] for case_id in order]

    def __getattr__(self, name):
        return getattr(self._delegate, name)


def _ir_state(case):
    ir = case.get("ir") or {}
    return ir["decision"]["state"] if "decision" in ir else None


def _ir_field(case, *keys):
    value = case.get("ir") or {}
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _review_summary(value, *, store=None, case_id=None):
    if not isinstance(value, dict):
        return value
    out = {
        key: value.get(key)
        for key in (
            "case_id", "status", "assignee", "version", "claimed_at",
            "last_activity", "lease_expires", "released_at",
            "released_draft_id", "primary_draft_id",
        )
    }
    drafts = value.get("drafts")
    if not isinstance(drafts, list) and store is not None and case_id:
        list_fn = getattr(store, "list_drafts", None)
        if callable(list_fn):
            try:
                drafts = list_fn(case_id)
            except Exception:
                drafts = None
    if isinstance(drafts, list):
        out["drafts"] = drafts
        primary_id = out.get("primary_draft_id")
        out["primary_draft"] = next(
            (d for d in drafts if isinstance(d, dict) and d.get("draft_id") == primary_id),
            drafts[-1] if drafts else None,
        )
    else:
        out["drafts"] = []
        out["primary_draft"] = None
    refs = value.get("fragment_references")
    out["fragment_references"] = refs if isinstance(refs, list) else []
    return out


def _extract_excerpt(case):
    unit = case.get("content") or case.get("content_unit") or {}
    if isinstance(unit, dict):
        txt = unit.get("text")
        if isinstance(txt, str) and txt.strip():
            return txt.strip().replace("\n", " ")[:64]
    ir = case.get("ir") or {}
    for f in ir.get("findings") or []:
        if isinstance(f, dict) and isinstance(f.get("quote"), str) and f["quote"].strip():
            return f["quote"].strip().replace("\n", " ")[:64]
    return None


def _summary(case):
    ir = case.get("ir") or {}
    dec = ir.get("decision") or {}
    cov = ir.get("coverage") or {}
    findings = ir.get("findings") or []
    high_cnt = sum(
        1 for f in findings
        if isinstance(f, dict) and str(f.get("severity") or "").upper() in ("L4", "L5")
    )
    unit = case.get("content") or case.get("content_unit") or {}
    channel = case.get("entry_channel")
    if not channel and isinstance(unit, dict):
        ctx = unit.get("context") or {}
        if isinstance(ctx, dict):
            channel = ctx.get("entry_channel") or ctx.get("channel")
    return {
        "case_id": case.get("case_id"),
        "ir_id": ir.get("ir_id"),
        "state": dec.get("state"),
        "layer": dec.get("layer"),
        "release_status": dec.get("release_status"),
        "tenant": case.get("tenant"),
        "product_line": case.get("product_line"),
        "assignee_id": case.get("assignee_id"),
        "sample": bool(case.get("sample")) if "sample" in case else None,
        "entry_channel": channel,
        "created_at": ir.get("created_at"),
        "title_or_excerpt": _extract_excerpt(case),
        "high_severity_count": high_cnt,
        "coverage_state": cov.get("coverage_state"),
    }


def _report_summary(report):
    return {
        "report_id": report.get("report_id"),
        "case_id": report.get("case_id"),
        "ir_id": report.get("ir_id"),
        "url": report.get("url"),
        "published_at": report.get("published_at"),
    }


# Appendix B 中所有写端点（本阶段统一 501 占位，但必须存在）。
WRITE_PATHS = (
    "/api/v1/submissions",
    "/api/v1/cases/{id}/claim",
    "/api/v1/cases/{id}/unclaim",
    "/api/v1/cases/{id}/reassign",
    "/api/v1/cases/{id}/actions",
    "/api/v1/appeals",
    "/api/v1/appeals/{id}/migrate",
    "/api/v1/appeals/{id}/withdraw",
    "/api/v1/cases/{id}/release-decision",
    "/api/v1/cases/{id}/release-revoke",
    "/api/v1/takedown-tasks/{id}/start",
    "/api/v1/takedown-tasks/{id}/complete",
    "/api/v1/takedown-tasks/{id}/fail",
    "/api/v1/takedown-tasks/{id}/retry",
    "/api/v1/takedown-tasks/{id}/reassign",
    "/api/v1/takedown-tasks/{id}/waive",
    "/api/v1/reports/{id}/resign",
    "/api/v1/notifications/{id}/read",
    "/api/v1/notifications/{id}/ack",
    "/api/v1/admin/signer-grants",
    "/api/v1/admin/takedown-grants",
)


ACCESS_LOG_ENV = "REVIEW_API_ACCESS_LOG"
DEFAULT_ACCESS_LOG = os.path.expanduser("~/.dsh/audit-data/access-log.jsonl")
READONLY_WRITE_PATHS = ("/api/v1/rules", "/api/v1/control-points",
                        "/api/v1/routing")


class AccessLog(object):
    """只读入口/身份拒绝的 JSONL 审计追加器（C-103/C-104）。

    目录与文件都落在仓外；路径只在第一次写入时创建，import 本身没有副作用。
    审计写失败不改变拒绝结论（拒绝已经成立），但会让调用方拿到 False。
    """

    def __init__(self, path=None):
        self.path = path or os.environ.get(ACCESS_LOG_ENV) or DEFAULT_ACCESS_LOG
        self._lock = threading.Lock()

    def write(self, *, principal, method, target, reason, env):
        principal = principal or {}
        record = {
            "ts": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "principal": principal.get("id"),
            "open_id": principal.get("open_id"),
            "tenant_id": principal.get("tenant_id"),
            "method": method,
            "target": target,
            "reason": reason,
            "env": env,
        }
        data = (json.dumps(record, ensure_ascii=False, sort_keys=True)
                + "\n").encode("utf-8")
        with self._lock:
            try:
                parent = os.path.dirname(os.path.abspath(self.path))
                os.makedirs(parent, mode=0o700, exist_ok=True)
                fd = os.open(self.path, os.O_CREAT | os.O_APPEND | os.O_WRONLY,
                             0o600)
                try:
                    view = memoryview(data)
                    while view:
                        n = os.write(fd, view)
                        view = view[n:]
                    os.fsync(fd)
                finally:
                    os.close(fd)
            except OSError:
                return False
        return True


def create_app(*, session_store=None, repository=None, principals=None,
               principal_provider=None, openapi_version="3.1.0",
               reviews_ledger=None, review_read_store=None,
               review_command_service=None, enabled_write_capabilities=None,
               review_freshness_provider=None, case_state_provider=None,
               review_assignee_validator=None, case_source=None,
               submission_ingestor=None,
               session_cookie_name="session", finding_store=None, appeals=None,
               release_gate=None, app_env=None,
               allow_simulated_identity=None, access_log_path=None):
    store = session_store or SessionStore(
        os.environ.get("REVIEW_API_SESSION_DB", ":memory:"))
    repo = repository or FileProjectionRepository(
        os.environ.get("REVIEW_API_DATA_ROOT",
                       os.path.expanduser("~/.dsh/audit-data/projection")))
    if case_source is not None:
        repo = CaseOverlayRepository(repo, case_source)

    resolved_env = (app_env if app_env is not None
                    else os.environ.get("APP_ENV") or "production")
    resolved_env = resolved_env.strip().lower()
    if allow_simulated_identity is None:
        allow_simulated_identity = (
            os.environ.get("ALLOW_SIMULATED_IDENTITY") == "1")
    if allow_simulated_identity and resolved_env != "dev":
        raise RuntimeError(
            "ALLOW_SIMULATED_IDENTITY=1 仅允许在 APP_ENV=dev 下使用"
            "（当前 APP_ENV=%s）" % resolved_env)

    if principal_provider is None:
        mapping = principals or {}

        def principal_provider(principal_id, tenant):
            p = dict(mapping.get(principal_id, {}))
            p["id"] = principal_id
            p["tenant"] = tenant
            p.setdefault("roles", [])
            p.setdefault("product_lines", [])
            return p

    app = FastAPI(title="Content Review API", version="1.0",
                  openapi_version=openapi_version)
    app.openapi_version = openapi_version
    from base.reviews_ledger import ReviewsLedger
    from base.finding_store import FindingStore
    from base.release_gate import ReleaseGate
    from api.write_api import register_write_routes, AppealStore

    app.state.session_store = store
    app.state.repository = repo
    app.state.principal_provider = principal_provider
    app.state.reviews_ledger = reviews_ledger or ReviewsLedger()
    app.state.finding_store = finding_store or FindingStore()
    app.state.appeals = appeals or AppealStore()
    app.state.release_gate = release_gate or ReleaseGate(sessions=store)
    app.state.idempotency = {}
    app.state.idempotency_lock = threading.Lock()
    app.state.app_env = resolved_env
    app.state.allow_simulated_identity = allow_simulated_identity
    app.state.access_log = AccessLog(access_log_path)
    repo_ledger = review_read_store or app.state.reviews_ledger
    app.state.review_command_service = review_command_service
    app.state.session_cookie_name = session_cookie_name

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": str(exc.status_code),
                "message": str(exc.detail),
                "details": None,
                "request_id": request.headers.get("x-request-id", ""),
            },
        )

    async def session_dep(request: Request):
        try:
            session = request.app.state.session_store.get_session(
                request.cookies.get(request.app.state.session_cookie_name))
        except Exception as exc:
            raise HTTPException(503, "session_unavailable") from exc
        if not session:
            raise HTTPException(401, "缺少或无效 session")
        return session

    def _audit_rejection(request, principal, reason):
        request.app.state.access_log.write(
            principal=principal, method=request.method,
            target=request.url.path, reason=reason,
            env=request.app.state.app_env)

    def principal_dep(request: Request, session=Depends(session_dep)):
        try:
            principal = request.app.state.principal_provider(
                session["principal"], session["tenant"])
        except Exception as exc:
            raise HTTPException(503, "principal_directory_unavailable") from exc
        if not principal:
            raise HTTPException(401, "无法解析 principal")

        # 模拟身份先判：生产模式一律 403（即使它没带绑定字段），
        # dev 且显式开关时才放行 —— 它是本地替身，不要求真实 open_id。
        if principal.get("simulated") is True:
            if not (request.app.state.app_env == "dev"
                    and request.app.state.allow_simulated_identity):
                reason = ("simulated_identity_in_production"
                          if request.app.state.app_env != "dev"
                          else "simulated_identity_not_allowed")
                _audit_rejection(request, principal, reason)
                raise HTTPException(403, "模拟身份不允许在当前环境使用")
            return principal

        open_id = principal.get("open_id")
        tenant_id = principal.get("tenant_id")
        if (not isinstance(open_id, str) or not open_id.strip()
                or not isinstance(tenant_id, str) or not tenant_id.strip()):
            _audit_rejection(request, principal, "identity_incomplete")
            raise HTTPException(401, "身份缺少 open_id/tenant_id")
        if tenant_id != session.get("tenant"):
            _audit_rejection(request, principal, "identity_tenant_mismatch")
            raise HTTPException(403, "身份 tenant_id 与 session 不一致")
        if (session.get("authz_version") is not None
                and session.get("authz_version") != principal.get("authz_version")):
            _audit_rejection(request, principal, "identity_authorization_changed")
            raise HTTPException(401, "主体授权已变化，请重新登录")
        return principal

    def internal_dep(principal=Depends(principal_dep)):
        if not ({"it", "coordinator"} & set(principal.get("roles") or [])):
            raise HTTPException(403, "仅内部角色可读")
        return principal

    def effective_case(case):
        value = dict(case)
        if case_state_provider is not None:
            live = case_state_provider(case.get("case_id"))
            if isinstance(live, dict):
                value["assignee_id"] = live.get("assignee")
                value["actionable"] = live.get("status") in (
                    "unassigned", "released")
        return value

    def require_read(principal, case):
        if not can_read_content(principal, effective_case(case)):
            raise HTTPException(403, "无权读取该案件内容")

    def require_review_fresh():
        if review_freshness_provider is not None:
            review_freshness_provider()

    @app.get("/api/v1/cases", response_model=List[CaseSummary])
    def list_cases(principal=Depends(principal_dep)):
        require_review_fresh()
        return [_summary(effective_case(c)) for c in repo.list_cases()
                if can_read_content(principal, effective_case(c))]

    @app.get("/api/v1/cases/{id}", response_model=CaseDetail)
    def get_case(id: str, principal=Depends(principal_dep)):
        case = repo.get_case(id)
        if case is None:
            raise HTTPException(404, "案件不存在")
        require_read(principal, case)
        require_review_fresh()
        unit = case.get("content_unit") or case.get("content")
        return {
            "case_id": id,
            "ir": case["ir"],
            "review": _review_summary(repo_ledger.get_case(id), store=repo_ledger, case_id=id),
            "content_unit": unit if isinstance(unit, dict) else None,
        }

    @app.get("/api/v1/queue", response_model=List[CaseSummary])
    def queue(principal=Depends(principal_dep)):
        require_review_fresh()
        return [_summary(effective_case(c)) for c in repo.list_cases()
                if can_read_content(principal, effective_case(c))
                and _ir_state(c) in ("REVIEW", "待自决")]

    @app.get("/review-api/queue", response_model=List[CaseSummary])
    def review_api_queue(principal=Depends(principal_dep)):
        """联调别名：只读列出所有可读案件，不改任何状态。"""
        return [_summary(effective_case(c)) for c in repo.list_cases()
                if can_read_content(principal, effective_case(c))]

    @app.get("/api/v1/reports", response_model=List[ReportSummary])
    def list_reports(principal=Depends(principal_dep)):
        out = []
        for report in repo.list_reports():
            case = repo.get_case(report.get("case_id"))
            if case is not None and can_read_content(principal, effective_case(case)):
                out.append(_report_summary(report))
        return out

    @app.get("/api/v1/reports/{id}", response_model=ReportDetail)
    def get_report(id: str, principal=Depends(principal_dep)):
        report = repo.get_report(id)
        if report is None:
            raise HTTPException(404, "报告不存在")
        case = repo.get_case(report.get("case_id"))
        if case is None:
            raise HTTPException(404, "报告缺少可授权案件")
        require_read(principal, case)
        return _report_summary(report)

    @app.get("/api/v1/rules")
    def rules(principal=Depends(principal_dep)):
        return repo.rules

    @app.get("/api/v1/control-points")
    def control_points(principal=Depends(principal_dep)):
        return repo.control_points

    @app.get("/api/v1/routing")
    def routing(principal=Depends(principal_dep)):
        return repo.routing

    @app.get("/api/v1/notifications")
    def notifications(principal=Depends(principal_dep)):
        # ★ 字段名必须是 `recipient` —— `base/notifications.py` 产出的就是它。
        #   这里曾经写成 `n.get("principal")`，而该字段**根本不存在**，
        #   于是 `None in (None, uid)` 恒真：任何人登录都能拿到全部通知。
        #   code=0、字段读得出、没有任何东西会红 —— 这正是 K-02 的形状。
        #   回归断言在 tools/verify_review_api.py 的 C6。
        tenant = principal.get("tenant")
        return [n for n in repo.notifications
                if n.get("tenant") == tenant
                and n.get("recipient") in (None, principal.get("id"))]

    @app.get("/api/v1/appeals")
    def appeals(principal=Depends(principal_dep)):
        tenant = principal.get("tenant")
        return [row for row in repo.appeals if row.get("tenant") == tenant]

    @app.get("/api/v1/release/pending")
    def release_pending(principal=Depends(principal_dep)):
        tenant = principal.get("tenant")
        return [row for row in repo.release_pending if row.get("tenant") == tenant]

    @app.get("/api/v1/cases/{id}/release-readiness")
    def release_readiness(id: str, principal=Depends(principal_dep)):
        case = repo.get_case(id)
        if case is None:
            raise HTTPException(404, "案件不存在")
        require_read(principal, case)
        return repo.release_readiness.get(id, {})

    @app.get("/api/v1/takedown-tasks")
    def takedown_tasks(principal=Depends(principal_dep)):
        tenant = principal.get("tenant")
        return [row for row in repo.takedown_tasks if row.get("tenant") == tenant]

    @app.get("/api/v1/admin/signer-grants")
    def signer_grants(principal=Depends(internal_dep)):
        tenant = principal.get("tenant")
        return [row for row in repo.signer_grants if row.get("tenant") == tenant]

    @app.get("/api/v1/admin/takedown-grants")
    def takedown_grants(principal=Depends(internal_dep)):
        tenant = principal.get("tenant")
        return [row for row in repo.takedown_grants if row.get("tenant") == tenant]

    @app.get("/api/v1/admin/sessions")
    def sessions(request: Request, principal=Depends(internal_dep)):
        if request.app.state.app_env == "production":
            raise HTTPException(404, "not_found")
        tenant = principal.get("tenant")
        return [row for row in repo.sessions if row.get("tenant") == tenant]

    @app.get("/metrics")
    def metrics(principal=Depends(internal_dep)):
        tenant = principal.get("tenant")
        if isinstance(repo.metrics, dict) and tenant in repo.metrics:
            return repo.metrics[tenant]
        return {}

    implemented = register_write_routes(
        app, principal_dep=principal_dep,
        review_command_service=review_command_service,
        enabled_capabilities=enabled_write_capabilities,
        assignee_validator=review_assignee_validator,
        submission_ingestor=submission_ingestor)

    def placeholder(request: Request, _principal=Depends(principal_dep)):
        raise HTTPException(501, "写端点尚未实现")

    for path in WRITE_PATHS:
        if path in implemented:
            continue
        app.add_api_route(path, placeholder, methods=["POST"],
                          response_model=ErrorResponse)

    def _make_readonly_guard(path, method):
        def readonly_guard(request: Request,
                           principal=Depends(principal_dep)):
            _audit_rejection(request, principal, "read_only_entry")
            raise HTTPException(403, "只读入口不接受写请求")
        safe_path = path.strip("/").replace("/", "_").replace("-", "_")
        readonly_guard.__name__ = "readonly_%s_%s" % (
            safe_path, method.lower())
        return readonly_guard

    for path in READONLY_WRITE_PATHS:
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            app.add_api_route(
                path, _make_readonly_guard(path, method),
                methods=[method],
                operation_id="readonly_%s_%s" % (
                    path.strip("/").replace("/", "_").replace("-", "_"),
                    method.lower()))

    return app
