#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api/review_api.py — T2-01：review-api 只读 API

只从已落盘的 IR / 投影读状态；本文件不导入、不调用任何判定实现，
不在 API 层计算 state/layer/coverage。OpenAPI 3.1 由 FastAPI + Pydantic 生成。

鉴权：base.auth_session 的 opaque session cookie + base.rbac 的对象 ACL。
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

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
    kind: str


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


class CaseDetail(BaseModel):
    case_id: str
    ir: ReviewIR


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
    """从仓外投影目录只读加载 JSON；文件不存在则对应集合为空。"""

    def __init__(self, root):
        def load(name, default):
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, ValueError):
                return default

        super().__init__(
            cases=load("cases.json", []),
            reports=load("reports.json", []),
            rules=load("rules.json", []),
            control_points=load("control-points.json", []),
            routing=load("routing.json", []),
            notifications=load("notifications.json", []),
            metrics=load("metrics.json", {}),
            appeals=load("appeals.json", []),
            release_pending=load("release-pending.json", []),
            takedown_tasks=load("takedown-tasks.json", []),
            signer_grants=load("signer-grants.json", []),
            takedown_grants=load("takedown-grants.json", []),
            sessions=load("sessions.json", []),
            release_readiness=load("release-readiness.json", {}),
        )


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


def _summary(case):
    ir = case.get("ir") or {}
    dec = ir.get("decision") or {}
    return {
        "case_id": case.get("case_id"),
        "ir_id": ir.get("ir_id"),
        "state": dec.get("state"),
        "layer": dec.get("layer"),
        "release_status": dec.get("release_status"),
        "tenant": case.get("tenant"),
        "product_line": case.get("product_line"),
        "assignee_id": case.get("assignee_id"),
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


def create_app(*, session_store=None, repository=None, principals=None,
               principal_provider=None, openapi_version="3.1.0",
               reviews_ledger=None, finding_store=None, appeals=None,
               release_gate=None):
    store = session_store or SessionStore(
        os.environ.get("REVIEW_API_SESSION_DB", ":memory:"))
    repo = repository or FileProjectionRepository(
        os.environ.get("REVIEW_API_DATA_ROOT",
                       os.path.expanduser("~/.dsh/audit-data/projection")))

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
        session = request.app.state.session_store.get_session(
            request.cookies.get("session"))
        if not session:
            raise HTTPException(401, "缺少或无效 session")
        return session

    def principal_dep(request: Request, session=Depends(session_dep)):
        principal = request.app.state.principal_provider(
            session["principal"], session["tenant"])
        if not principal:
            raise HTTPException(401, "无法解析 principal")
        return principal

    def internal_dep(principal=Depends(principal_dep)):
        if not ({"it", "coordinator"} & set(principal.get("roles") or [])):
            raise HTTPException(403, "仅内部角色可读")
        return principal

    def require_read(principal, case):
        if not can_read_content(principal, case):
            raise HTTPException(403, "无权读取该案件内容")

    @app.get("/api/v1/cases", response_model=List[CaseSummary])
    def list_cases(principal=Depends(principal_dep)):
        return [_summary(c) for c in repo.list_cases()
                if can_read_content(principal, c)]

    @app.get("/api/v1/cases/{id}", response_model=CaseDetail)
    def get_case(id: str, principal=Depends(principal_dep)):
        case = repo.get_case(id)
        if case is None:
            raise HTTPException(404, "案件不存在")
        require_read(principal, case)
        return {"case_id": id, "ir": case["ir"]}

    @app.get("/api/v1/queue", response_model=List[CaseSummary])
    def queue(principal=Depends(principal_dep)):
        return [_summary(c) for c in repo.list_cases()
                if can_read_content(principal, c)
                and _ir_state(c) in ("REVIEW", "待自决")]

    @app.get("/api/v1/reports", response_model=List[ReportSummary])
    def list_reports(principal=Depends(principal_dep)):
        out = []
        for report in repo.list_reports():
            case = repo.get_case(report.get("case_id"))
            if case is None or can_read_content(principal, case):
                out.append(_report_summary(report))
        return out

    @app.get("/api/v1/reports/{id}", response_model=ReportDetail)
    def get_report(id: str, principal=Depends(principal_dep)):
        report = repo.get_report(id)
        if report is None:
            raise HTTPException(404, "报告不存在")
        case = repo.get_case(report.get("case_id"))
        if case is not None:
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
        return [n for n in repo.notifications
                if n.get("principal") in (None, principal.get("id"))]

    @app.get("/api/v1/appeals")
    def appeals(principal=Depends(principal_dep)):
        return repo.appeals

    @app.get("/api/v1/release/pending")
    def release_pending(principal=Depends(principal_dep)):
        return repo.release_pending

    @app.get("/api/v1/cases/{id}/release-readiness")
    def release_readiness(id: str, principal=Depends(principal_dep)):
        case = repo.get_case(id)
        if case is None:
            raise HTTPException(404, "案件不存在")
        require_read(principal, case)
        return repo.release_readiness.get(id, {})

    @app.get("/api/v1/takedown-tasks")
    def takedown_tasks(principal=Depends(principal_dep)):
        return repo.takedown_tasks

    @app.get("/api/v1/admin/signer-grants")
    def signer_grants(_=Depends(internal_dep)):
        return repo.signer_grants

    @app.get("/api/v1/admin/takedown-grants")
    def takedown_grants(_=Depends(internal_dep)):
        return repo.takedown_grants

    @app.get("/api/v1/admin/sessions")
    def sessions(_=Depends(internal_dep)):
        return repo.sessions

    @app.get("/metrics")
    def metrics(_=Depends(internal_dep)):
        return repo.metrics

    implemented = register_write_routes(app, principal_dep=principal_dep)

    def placeholder(request: Request, _principal=Depends(principal_dep)):
        if ("/release-decision" in request.url.path
                or "/release-revoke" in request.url.path):
            raise HTTPException(501, "release_gate 未实现，不能返回假成功")
        raise HTTPException(501, "写端点尚未实现")

    for path in WRITE_PATHS:
        if path in implemented:
            continue
        app.add_api_route(path, placeholder, methods=["POST"],
                          response_model=ErrorResponse)

    return app


app = create_app()
