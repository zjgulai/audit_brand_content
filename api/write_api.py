#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api/write_api.py — T2-02：review-api 写端点

只做编排：claim/lease/draft 走 reviews_ledger；finding 状态变化走 finding_store；
appeal 的 pause/migrate/stale 走 AppealStore；takedown 的状态机/回填/waive 走 base/takedown。
API 层不计算 state/layer，也不写 decision/coverage。
"""
from __future__ import annotations

import copy
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from base import takedown as TD
from base.finding_store import FindingRejected
from base.release_gate import (
    InvalidTransition, SignatureError, SoDViolation, StepUpError,
)
from base.rbac import can_act
from base.reviews_ledger import (
    LedgerConflict, LedgerNotFound, LedgerValidation,
)


class ClaimBody(BaseModel):
    pass


class VersionBody(BaseModel):
    version: int


class ReassignBody(VersionBody):
    assignee: str


class ActionBody(VersionBody):
    action: str
    finding_id: Optional[str] = None
    draft: Optional[Dict[str, Any]] = None
    conclusion: Optional[Dict[str, Any]] = None


class AppealCreate(BaseModel):
    case_id: str
    reason: str


class AppealWithdraw(BaseModel):
    reason: Optional[str] = None


class TakedownEvidence(BaseModel):
    evidence: Dict[str, Any]


class TakedownReassign(BaseModel):
    assignee: str
    version: Optional[int] = None


class TakedownWaive(BaseModel):
    approvers: List[Dict[str, Any]]
    reason: str
    evidence: Any
    original_signer: Optional[str] = None


class ReleaseDecisionBody(BaseModel):
    decision: str
    version: int
    step_up_token: Optional[str] = None
    nonce: Optional[str] = None
    reason: Optional[str] = None


class ReleaseRevokeBody(BaseModel):
    version: int
    step_up_token: Optional[str] = None
    nonce: Optional[str] = None
    reason: Optional[str] = None


class AppealError(Exception):
    def __init__(self, code, detail="", status=409):
        self.code = code
        self.detail = detail
        self.status = status
        super().__init__("%s: %s" % (code, detail))


class AppealStore(object):
    """申诉的暂停/迁移/stale 语义；API 只调用本类。"""

    def __init__(self, clock=None):
        self.clock = clock or time.time
        self._lock = threading.RLock()
        self._items = {}
        self._seq = 0

    def _now(self, now):
        return self.clock() if now is None else float(now)

    def open(self, case_id, appellant, reason, now=None):
        if not case_id or not appellant or not reason:
            raise AppealError("bad_appeal", "case_id/appellant/reason 必填", 400)
        now = self._now(now)
        with self._lock:
            self._seq += 1
            appeal_id = "appeal-%d" % self._seq
            item = {
                "appeal_id": appeal_id, "case_id": case_id,
                "appellant": appellant, "reason": reason,
                "state": "open", "opened_at": self._iso(now),
                "paused_at": None, "migrated_at": None,
            }
            self._items[appeal_id] = item
            return copy.deepcopy(item)

    @staticmethod
    def _iso(now):
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(now)))

    def get(self, appeal_id):
        with self._lock:
            item = self._items.get(appeal_id)
            if item is None:
                raise AppealError("appeal_not_found", "申诉不存在", 404)
            return copy.deepcopy(item)

    def list(self):
        with self._lock:
            return [copy.deepcopy(x) for x in self._items.values()]

    def pause(self, case_id, reason="version_invalidated", now=None):
        now = self._now(now)
        paused = []
        with self._lock:
            for item in self._items.values():
                if item["case_id"] == case_id and item["state"] == "open":
                    item["state"] = "paused_version_invalidated"
                    item["pause_reason"] = reason
                    item["paused_at"] = self._iso(now)
                    paused.append(copy.deepcopy(item))
        return paused

    def migrate(self, appeal_id, actor, now=None):
        now = self._now(now)
        with self._lock:
            item = self._items.get(appeal_id)
            if item is None:
                raise AppealError("appeal_not_found", "申诉不存在", 404)
            if actor != item["appellant"]:
                raise AppealError("not_original_appellant",
                                  "只有原申诉人可以确认迁移", 403)
            if item["state"] != "paused_version_invalidated":
                raise AppealError("not_paused", "只有 paused 的申诉可迁移", 409)
            item["state"] = "migrated"
            item["migrated_at"] = self._iso(now)
            return copy.deepcopy(item)

    def withdraw(self, appeal_id, actor, reason, now=None):
        if not isinstance(reason, str) or not reason.strip():
            raise AppealError("missing_reason", "撤销必须写 reason", 400)
        now = self._now(now)
        with self._lock:
            item = self._items.get(appeal_id)
            if item is None:
                raise AppealError("appeal_not_found", "申诉不存在", 404)
            if actor != item["appellant"]:
                raise AppealError("not_original_appellant",
                                  "只有原申诉人可以撤销", 403)
            if item["state"] not in ("open", "paused_version_invalidated"):
                raise AppealError("terminal_state", "终态申诉不能撤销", 409)
            item["state"] = "withdrawn"
            item["withdrawn_at"] = self._iso(now)
            item["withdraw_reason"] = reason
            return copy.deepcopy(item)

    def mark_stale(self, now=None, days=30):
        """paused 超过 days 天未迁移 → stale（停止提醒、不关闭）。"""
        now = self._now(now)
        marked = []
        with self._lock:
            for item in self._items.values():
                if item["state"] != "paused_version_invalidated":
                    continue
                paused_at = item.get("paused_at")
                if not paused_at:
                    continue
                try:
                    ts = time.mktime(time.strptime(paused_at, "%Y-%m-%dT%H:%M:%SZ"))
                except ValueError:
                    continue
                if now - ts > days * 86400:
                    item["state"] = "stale"
                    item["stale_at"] = self._iso(now)
                    marked.append(copy.deepcopy(item))
        return marked


IMPLEMENTED_WRITE_PATHS = {
    "/api/v1/cases/{id}/claim",
    "/api/v1/cases/{id}/unclaim",
    "/api/v1/cases/{id}/reassign",
    "/api/v1/cases/{id}/actions",
    "/api/v1/appeals",
    "/api/v1/appeals/{id}/migrate",
    "/api/v1/appeals/{id}/withdraw",
    "/api/v1/takedown-tasks/{id}/start",
    "/api/v1/takedown-tasks/{id}/complete",
    "/api/v1/takedown-tasks/{id}/fail",
    "/api/v1/takedown-tasks/{id}/retry",
    "/api/v1/takedown-tasks/{id}/reassign",
    "/api/v1/takedown-tasks/{id}/waive",
    "/api/v1/cases/{id}/release-decision",
    "/api/v1/cases/{id}/release-revoke",
}


def _idempotent(request, key, fn):
    if not isinstance(key, str) or not key.strip():
        raise HTTPException(400, "缺少 Idempotency-Key")
    cache_key = (request.url.path, key)
    cache = request.app.state.idempotency
    lock = request.app.state.idempotency_lock
    with lock:
        if cache_key in cache:
            return copy.deepcopy(cache[cache_key])
    result = fn()
    with lock:
        cache[cache_key] = copy.deepcopy(result)
    return result


def _ledger_call(fn):
    try:
        return fn()
    except LedgerConflict as exc:
        raise HTTPException(409, "%s: %s" % (exc.code, exc.detail))
    except LedgerNotFound as exc:
        raise HTTPException(404, "%s: %s" % (exc.code, exc.detail))
    except LedgerValidation as exc:
        raise HTTPException(400, "%s: %s" % (exc.code, exc.detail))


def register_write_routes(app, *, principal_dep):
    repo = app.state.repository
    ledger = app.state.reviews_ledger
    findings = app.state.finding_store
    appeals = app.state.appeals
    gate = app.state.release_gate

    def case_or_404(case_id):
        case = repo.get_case(case_id)
        if case is None:
            raise HTTPException(404, "案件不存在")
        return case

    def require_review(principal, case):
        if not can_act(principal, "case.review", case):
            raise HTTPException(403, "无权执行复核动作")

    def require_tenant(principal, obj, what="case"):
        """写操作的对象必须与 principal 同租户（TS-1）。"""
        if principal.get("tenant") != obj.get("tenant"):
            raise HTTPException(403, "跨租户：principal 与 %s tenant 不一致" % what)

    def task_or_404(task_id):
        task = next((t for t in repo.takedown_tasks
                     if t.get("task_id") == task_id), None)
        if task is None:
            raise HTTPException(404, "下线任务不存在")
        return task

    def save_task(task):
        for i, t in enumerate(repo.takedown_tasks):
            if t.get("task_id") == task.get("task_id"):
                repo.takedown_tasks[i] = task
                return
        repo.takedown_tasks.append(task)

    @app.post("/api/v1/cases/{id}/claim")
    def claim(id: str, request: Request, body: ClaimBody,
              principal=Depends(principal_dep),
              idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        case = case_or_404(id)
        require_review(principal, case)
        return _idempotent(request, idempotency_key,
                           lambda: _ledger_call(
                               lambda: ledger.claim(id, principal["id"])))

    @app.post("/api/v1/cases/{id}/unclaim")
    def unclaim(id: str, request: Request, body: VersionBody,
                principal=Depends(principal_dep),
                idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        case = case_or_404(id)
        require_review(principal, case)
        return _idempotent(request, idempotency_key,
                           lambda: _ledger_call(
                               lambda: ledger.unclaim(id, principal["id"],
                                                      body.version)))

    @app.post("/api/v1/cases/{id}/reassign")
    def reassign(id: str, request: Request, body: ReassignBody,
                 principal=Depends(principal_dep),
                 idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        case = case_or_404(id)
        require_review(principal, case)
        return _idempotent(request, idempotency_key,
                           lambda: _ledger_call(
                               lambda: ledger.reassign(id, principal["id"],
                                                       body.version,
                                                       body.assignee)))

    @app.post("/api/v1/cases/{id}/actions")
    def actions(id: str, request: Request, body: ActionBody,
                principal=Depends(principal_dep),
                idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        case = case_or_404(id)
        require_review(principal, case)

        def run():
            current = ledger.get_case(id)["version"]
            if body.version != current:
                raise HTTPException(409, "version_conflict: 案件版本已变化")
            if body.action == "save_draft":
                draft = body.draft or {}
                return _ledger_call(lambda: ledger.autosave(
                    id, principal["id"], body.version,
                    form=draft.get("form") or {},
                    notes=draft.get("notes") or "",
                    evidence_selections=draft.get("evidence_selections") or [],
                    references=draft.get("references") or [],
                    primary=bool(draft.get("primary", True))))
            if body.action == "submit":
                if not isinstance(body.conclusion, dict):
                    raise HTTPException(400, "submit 必须带 conclusion")
                return _ledger_call(lambda: ledger.submit(
                    id, principal["id"], body.version, body.conclusion))
            if body.action not in ("confirm", "reject"):
                raise HTTPException(400, "action 必须是 confirm/reject/save_draft/submit")
            if not body.finding_id:
                raise HTTPException(400, "confirm/reject 必须带 finding_id")
            old = findings.get(body.finding_id)
            if old is None:
                raise HTTPException(404, "finding 不存在")
            if old.get("status") != "candidate":
                raise HTTPException(409, "只有 candidate 可以做确认/驳回")
            new_status = "confirmed" if body.action == "confirm" else "rejected"
            try:
                rec = findings.transition(body.finding_id,
                                          new_status=new_status)
            except FindingRejected as exc:
                raise HTTPException(409, "%s: %s" % (exc.code, exc.detail))
            return {"finding": rec}

        return _idempotent(request, idempotency_key, run)

    @app.post("/api/v1/appeals")
    def create_appeal(request: Request, body: AppealCreate,
                      principal=Depends(principal_dep),
                      idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_tenant(principal, case_or_404(body.case_id))
        return _idempotent(
            request, idempotency_key,
            lambda: appeals.open(body.case_id, principal["id"], body.reason))

    @app.post("/api/v1/appeals/{id}/migrate")
    def migrate_appeal(id: str, request: Request,
                       principal=Depends(principal_dep),
                       idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        try:
            appeal = appeals.get(id)
        except AppealError as exc:
            raise HTTPException(exc.status, "%s: %s" % (exc.code, exc.detail))
        require_tenant(principal, case_or_404(appeal["case_id"]))

        def run():
            try:
                return appeals.migrate(id, principal["id"])
            except AppealError as exc:
                raise HTTPException(exc.status, "%s: %s" % (exc.code, exc.detail))
        return _idempotent(request, idempotency_key, run)

    @app.post("/api/v1/appeals/{id}/withdraw")
    def withdraw_appeal(id: str, request: Request, body: AppealWithdraw,
                        principal=Depends(principal_dep),
                        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        try:
            appeal = appeals.get(id)
        except AppealError as exc:
            raise HTTPException(exc.status, "%s: %s" % (exc.code, exc.detail))
        require_tenant(principal, case_or_404(appeal["case_id"]))

        def run():
            try:
                return appeals.withdraw(id, principal["id"], body.reason)
            except AppealError as exc:
                raise HTTPException(exc.status, "%s: %s" % (exc.code, exc.detail))
        return _idempotent(request, idempotency_key, run)

    def takedown_action(action):
        def handler(id: str, request: Request,
                    principal=Depends(principal_dep),
                    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
            task = task_or_404(id)
            require_tenant(principal, task, "takedown task")

            def run():
                try:
                    if action == "start":
                        new = TD.transition(task, "in_progress", action="start")
                    elif action == "fail":
                        new = TD.transition(task, "failed", action="fail")
                    elif action == "retry":
                        new = TD.transition(task, "pending", action="retry")
                    else:
                        raise HTTPException(400, "未知 action")
                except TD.TakedownError as exc:
                    raise HTTPException(409, "%s: %s" % (exc.code, exc.detail))
                new["version"] = int(new.get("version") or 0) + 1
                save_task(new)
                return new
            return _idempotent(request, idempotency_key, run)
        return handler

    for action in ("start", "fail", "retry"):
        app.add_api_route("/api/v1/takedown-tasks/{id}/" + action,
                          takedown_action(action), methods=["POST"])

    @app.post("/api/v1/takedown-tasks/{id}/complete")
    def takedown_complete(id: str, request: Request, body: TakedownEvidence,
                          principal=Depends(principal_dep),
                          idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        task = task_or_404(id)
        require_tenant(principal, task, "takedown task")

        def run():
            try:
                new = TD.complete(task, body.evidence)
            except TD.TakedownError as exc:
                raise HTTPException(400, "%s: %s" % (exc.code, exc.detail))
            new["version"] = int(new.get("version") or 0) + 1
            save_task(new)
            return new
        return _idempotent(request, idempotency_key, run)

    @app.post("/api/v1/takedown-tasks/{id}/reassign")
    def takedown_reassign(id: str, request: Request, body: TakedownReassign,
                          principal=Depends(principal_dep),
                          idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        task = task_or_404(id)
        require_tenant(principal, task, "takedown task")

        def run():
            if body.version is not None and body.version != int(task.get("version") or 0):
                raise HTTPException(409, "version_conflict: 任务版本已变化")
            new = copy.deepcopy(task)
            new["assignee"] = body.assignee
            new["version"] = int(new.get("version") or 0) + 1
            save_task(new)
            return new
        return _idempotent(request, idempotency_key, run)

    @app.post("/api/v1/takedown-tasks/{id}/waive")
    def takedown_waive(id: str, request: Request, body: TakedownWaive,
                       principal=Depends(principal_dep),
                       idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        task = task_or_404(id)
        require_tenant(principal, task, "takedown task")

        def run():
            try:
                checked = TD.check_waive(
                    approvers=body.approvers,
                    executor=task.get("assignee") or "",
                    original_signer=body.original_signer,
                    reason=body.reason, evidence=body.evidence,
                )
            except TD.TakedownError as exc:
                raise HTTPException(400, "%s: %s" % (exc.code, exc.detail))
            new = copy.deepcopy(task)
            new["waived"] = checked
            new["version"] = int(new.get("version") or 0) + 1
            save_task(new)
            return new
        return _idempotent(request, idempotency_key, run)

    @app.post("/api/v1/cases/{id}/release-decision")
    async def release_decision(id: str, request: Request, body: ReleaseDecisionBody,
                         principal=Depends(principal_dep),
                         idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        case = case_or_404(id)
        if body.decision not in ("sign", "reject"):
            raise HTTPException(400, "decision 必须是 sign/reject")
        if body.version != case.get("case_version"):
            raise HTTPException(409, "version_conflict: 案件版本已变化")

        def run():
            try:
                if body.decision == "reject":
                    sig = gate.reject(case, principal, body.step_up_token,
                                      body.nonce, reason=body.reason or "")
                else:
                    sig = gate.sign(case, principal, body.step_up_token,
                                    body.nonce, decision="signed",
                                    reason=body.reason or "")
            except SoDViolation as exc:
                raise HTTPException(403, "SoD: %s" % exc)
            except StepUpError as exc:
                raise HTTPException(403, "step_up: %s" % exc)
            except InvalidTransition as exc:
                raise HTTPException(409, "invalid_transition: %s" % exc)
            except SignatureError as exc:
                raise HTTPException(400, "signature: %s" % exc)
            return {"signature": sig, "release": gate.state(id)}

        return _idempotent(request, idempotency_key, run)

    @app.post("/api/v1/cases/{id}/release-revoke")
    async def release_revoke(id: str, request: Request, body: ReleaseRevokeBody,
                       principal=Depends(principal_dep),
                       idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        case = case_or_404(id)
        if body.version != case.get("case_version"):
            raise HTTPException(409, "version_conflict: 案件版本已变化")

        def run():
            try:
                out = gate.revoke(case, principal, body.step_up_token,
                                  body.nonce, reason=body.reason or "")
            except SoDViolation as exc:
                raise HTTPException(403, "SoD: %s" % exc)
            except StepUpError as exc:
                raise HTTPException(403, "step_up: %s" % exc)
            except InvalidTransition as exc:
                raise HTTPException(409, "invalid_transition: %s" % exc)
            except SignatureError as exc:
                raise HTTPException(400, "signature: %s" % exc)
            return {"release": out, "state": gate.state(id)}

        return _idempotent(request, idempotency_key, run)

    return IMPLEMENTED_WRITE_PATHS
