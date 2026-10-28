#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api/write_api.py — T2-02：review-api 写端点

只做编排：claim/lease/draft 走 reviews_ledger；finding 状态变化走 finding_store；
appeal 的 pause/migrate/stale 走 AppealStore；takedown 的状态机/回填/waive 走 base/takedown。
API 层不计算 state/layer，也不写 decision/coverage。
"""
from __future__ import annotations

import calendar
import copy
import hashlib
import json
import threading
import time
from typing import Any, Dict, List, Optional

from fastapi import Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from base import takedown as TD
from base.finding_store import FindingRejected
from base.release_gate import (
    InvalidTransition, SignatureError, SoDViolation, StepUpError,
)
from base.rbac import can_act, can_reassign_takedown
from base.business_event_store import AuthorityConflict
from base.reviews_ledger import (
    LedgerConflict, LedgerNotFound, LedgerValidation,
)
from base.submission_service import SubmissionRejected


class ClaimBody(BaseModel):
    pass


class SubmissionBody(BaseModel):
    """内容入库请求；四维字段与 base.contract / submission_router 同一取值域。"""
    submission_id: str
    content_type: str
    # ★★ 2026-10-28 改成**可选**：这是 T-455 那条推断唯一能活过来的方式。
    #
    #   改前是 `content_stage: str`（必填），而 `apply_stage_inference()`
    #   只在它**缺失**时才推断 —— 于是网页提交永远带值，
    #   `intent_inference` 永远落 `absent`，**这条推断在 HTTP 路径上从未触发过**。
    #   （实测：schema 必填 → 不做 stage 的请求在 422 就被拦下，到不了 reducer。
    #     T-455 的 D 组全绿，因为它走的是 `ingestor.prepare()` 而不是 HTTP。）
    #
    #   ★ 「缺了」与「给了」是两件不同的事，这个字段现在必须能表达前者：
    #     用户从群消息转过来一段文案时，**确实可能不知道**那是提纲还是成稿。
    #
    #   ★ 缺了不一定能推断出来。三条口径见 `apply_stage_inference()`：
    #     推断不出 → **不补**，让四维校验照原样报 422（缺字段），
    #     绝不默认成某一档（默认 final_content 会让 brief 按终稿判，
    #     默认 brief 会让终稿被当草稿放过 —— 两个方向都错）。
    content_stage: Optional[str] = None
    entry_channel: str
    source: Dict[str, Any]
    text: Optional[str] = None
    fields: Optional[Dict[str, Any]] = None
    product_line: str
    tenant: Optional[str] = None
    uri: Optional[str] = None


class VersionBody(BaseModel):
    version: int


class ReassignBody(VersionBody):
    assignee: str


class ActionBody(VersionBody):
    action: str
    finding_id: Optional[str] = None
    draft: Optional[Dict[str, Any]] = None
    conclusion: Optional[Dict[str, Any]] = None
    source_draft_id: Optional[str] = None
    field_path: Optional[str] = None
    fragment: Any = None
    assignee: Optional[str] = None
    reason: Optional[str] = None


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


class NotificationItemBody(BaseModel):
    """T-313d：通知 read/ack 的请求体（模块级 —— 局部类炸 ForwardRef）。"""
    notification_id: str


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
                    ts = calendar.timegm(
                        time.strptime(paused_at, "%Y-%m-%dT%H:%M:%SZ"))
                except ValueError:
                    continue
                if now - ts > days * 86400:
                    item["state"] = "stale"
                    item["stale_at"] = self._iso(now)
                    marked.append(copy.deepcopy(item))
        return marked


IMPLEMENTED_WRITE_PATHS = {
    "/api/v1/submissions",
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
    # T-313d：通知 read/ack（写自己的收件箱；GET 的 authority 分支在 review_api）。
    "/api/v1/notifications/{id}/read",
    "/api/v1/notifications/{id}/ack",
    # ★ 2026-10-28（ADR-0021 主线）：媒体上传。
    #   它是**写**（落盘到 REVIEW_MEDIA_ROOTS），所以必须在这张表里 ——
    #   否则 S8 会报「没人认领的写端点」，而那正是它该报的。
    "/api/v1/uploads",
}


def _idempotent(request, key, fn, *, actor=None, request_body=None):
    if not isinstance(key, str) or not key.strip():
        raise HTTPException(400, "缺少 Idempotency-Key")
    request_hash = hashlib.sha256(json.dumps({
        "actor": actor, "path": request.url.path,
        "body": request_body,
    }, ensure_ascii=False, sort_keys=True,
       separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
    cache_key = (actor, request.url.path, key.strip())
    cache = request.app.state.idempotency
    lock = request.app.state.idempotency_lock
    with lock:
        existing = cache.get(cache_key)
        if existing is not None:
            if existing["request_hash"] != request_hash:
                raise HTTPException(409, "idempotency_conflict")
            return copy.deepcopy(existing["result"])
        # legacy/禁用写域在同一进程锁内执行+登记；生产复核不走这里，
        # 而是用 BusinessEventStore 的跨重启权威幂等。
        result = fn()
        cache[cache_key] = {
            "request_hash": request_hash,
            "result": copy.deepcopy(result),
        }
        return result


def _ledger_call(fn):
    try:
        return fn()
    except LedgerConflict as exc:
        raise HTTPException(409, "%s: %s" % (exc.code, exc.detail))
    except LedgerNotFound as exc:
        raise HTTPException(404, "%s: %s" % (exc.code, exc.detail))
        if code == "not_original_signer":
            # SoD 类：撤回只能由原签发人执行（T-315b / #123c）。
            raise HTTPException(403, "%s: %s" % (exc.code, exc.detail))
    except LedgerValidation as exc:
        raise HTTPException(400, "%s: %s" % (exc.code, exc.detail))


def register_write_routes(app, *, principal_dep, review_command_service=None,
                          enabled_capabilities=None, assignee_validator=None,
                          submission_ingestor=None):
    repo = app.state.repository
    ledger = app.state.reviews_ledger
    findings = app.state.finding_store
    appeals = app.state.appeals
    gate = app.state.release_gate
    enabled = (
        set(IMPLEMENTED_WRITE_PATHS)
        if enabled_capabilities is None
        else set(enabled_capabilities)
    )

    def require_enabled(path):
        if path not in enabled:
            raise HTTPException(501, "capability_not_enabled")

    def case_or_404(case_id):
        case = repo.get_case(case_id)
        if case is None:
            raise HTTPException(404, "案件不存在")
        return case

    def require_review(principal, case):
        effective = dict(case)
        if review_command_service is not None:
            live = review_command_service.authority.state(case.get("case_id"))
            effective["assignee_id"] = live.get("assignee")
            effective["actionable"] = live.get("status") in (
                "unassigned", "released")
        if not can_act(principal, "case.review", effective):
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

    def require_takedown(principal, task, capability="takedown.execute"):
        """下线写操作的能力判定（T-312b）。

        ## 三把钥匙，不是一把

        | 路由 | 钥匙 | 为什么 |
        |---|---|---|
        | start / complete / fail / retry | `takedown.execute` | 「去平台上把它弄下来」 |
        | reassign | `can_reassign_takedown`（coordinator + 同租户） | UIUX TD-12：统筹改派；统筹**没有** execute |
        | waive | `takedown.waive` | 「宣布不用下线」——与执行方向相反 |

        ★ 为什么 waive 不能靠 `takedown.execute` 满足：
          合成一把钥匙等于让「被派去干活的人」自动获得「可以宣布不干」的资格，
          而 waive 是双人审批 + 原签发人不得唯一 —— 它防的正是执行人自批。
          `base/takedown.py` 的 `check_waive` 会拦「执行人当审批人」，
          但如果执行人自己就能调 waive 路由，那道门只剩形式。

        ★ 改派为什么不复用 execute：见 `rbac.can_reassign_takedown` 的 docstring。
          照 T-312 施工单字面接 `takedown.execute` 会让改派全系统无人可做。

        ## 为什么 task 能当 case 传给 can_act

        `can_act` 的 scope 判定读 `tenant` 与 `product_line`，任务对象两个都有。
        **platform 维度尚未建模**（`base/rbac.py:37` 已记），这里不假装有。
        """
        if not can_act(principal, capability, task):
            raise HTTPException(
                403, "无权执行下线动作：%s（任务 %s）" % (capability, task.get("task_id")))

    def raise_command_http(exc, command):
        """领域错误转稳定 HTTP；未知异常原样抛。"""
        code = getattr(exc, "code", None)
        if code in ("writer_lease_lost", "writer_lease_missing",
                    "writer_lease_held"):
            raise HTTPException(503, code)
        if code in ("version_conflict", "already_claimed", "case_closed",
                    "not_assignee", "not_primary", "primary_requires_adopt",
                    "lease_expired", "lease_active", "not_claimed",
                    "idempotency_conflict", "already_ingested",
                    "unadjudicated_findings", "invalid_finding_transition",
                    "invalid_transition"):
            if command == "ingest_submission" and code == "version_conflict":
                raise HTTPException(409, "already_ingested: 该 submission 已建案")
            raise HTTPException(409, "%s: %s" % (code, getattr(exc, "detail", "")))
        if code in ("draft_not_found", "finding_not_found",
                    # ★ 2026-10-28：为「不在 authority 里的案件」做复核动作。
                    #   它与 finding_not_found 同为 404，但**不是同一件事**：
                    #   前者是「这个案件不在这里」，后者是「案件在、但那条
                    #   finding 不在」。混成一个码会让排查走错方向
                    #   （实测踩过：报 finding_not_found，而去查证据链）。
                    "case_not_in_authority"):
            raise HTTPException(404, "%s: %s" % (code, getattr(exc, "detail", "")))
        if code == "not_original_signer":
            # SoD 类：撤回只能由原签发人执行（T-315b / #123c）。
            raise HTTPException(403, "%s: %s" % (code, getattr(exc, "detail", "")))
        if code and (code.startswith("bad_") or code in
                     ("idempotency_key_missing", "actor_missing")):
            raise HTTPException(400, "%s: %s" % (code, getattr(exc, "detail", "")))
        raise exc

    def run_review_command(*, request, principal, case_id, command,
                           expected_version, payload, idempotency_key,
                           legacy_fn):
        if review_command_service is None:
            return _idempotent(
                request, idempotency_key, lambda: _ledger_call(legacy_fn),
                actor=principal["id"],
                request_body={"case_id": case_id, "command": command,
                              "expected_version": expected_version,
                              "payload": payload or {}})
        try:
            outcome = review_command_service.execute(
                aggregate_id=case_id,
                command=command,
                actor={"principal_id": principal["id"],
                       "tenant_id": principal["tenant"]},
                expected_version=expected_version,
                payload=payload or {},
                idempotency_key=idempotency_key,
            )
        except Exception as exc:  # 领域错误在这里转成稳定 HTTP；未知异常继续抛
            raise_command_http(exc, command)
        response = dict(outcome["result"])
        response.update({
            "authority_snapshot": outcome["authority_snapshot"],
            "reconcile_token": outcome["reconcile_token"],
            "projection_lag": outcome["projection_lag"],
            "replayed": outcome["replayed"],
        })
        return JSONResponse(content=response, status_code=outcome["http_status"])

    @app.post("/api/v1/uploads")
    async def upload_media(request: Request,
                           principal=Depends(principal_dep),
                           idempotency_key: Optional[str] = Header(
                               None, alias="Idempotency-Key")):
        """媒体上传：浏览器文件 → 落盘 → 返回可进件的本地路径。

        ## 为什么这个协议是「字节直传 + X-Filename 头」而不是 multipart

        `pyproject.toml` 只声明了 fastapi / pydantic / uvicorn，
        **没有 python-multipart** —— 而 FastAPI 的 `UploadFile` 靠它，
        不装会在 import 期就报错。为上传这一个端点把依赖塞进生产镜像，
        风险大于收益（本项目 P0-A / P0-C 两次事故都是漏装依赖）。
        所以：请求体就是文件字节，文件名走 `X-Filename` 头。

        ## 返回什么

            {"path": 服务端绝对路径, "kind": "image"|"video",
             "byte_size": n, "sha256": "...", "display_name": "...",
             "stored_name": "..."}

        前端把它填进 `submission.source.uri` 即可走既有进件链。

        ★ **不接受客户端给的落盘路径。** 落盘位置只由服务端决定
          （`media_roots[0]/_uploads/`），客户端只提供一个「显示名」。
        """
        require_enabled("/api/v1/uploads")

        from base import media_upload as MU

        filename = (request.headers.get("x-filename") or "").strip()
        if not filename:
            raise HTTPException(
                400, "缺 X-Filename 头（上传必须带文件名，用它判后缀白名单）")

        # 从应用配置里读素材根。★ 用 `getattr` 而不是硬取：
        # 开发装配可能没有 settings，那时应当拒（未配根 = 不收上传）。
        settings = getattr(app.state, "production_settings", None)
        roots = tuple(getattr(settings, "media_roots", ()) or ())
        if not roots:
            raise HTTPException(
                503, "未配置 REVIEW_MEDIA_ROOTS —— 不配根目录就不收上传")

        declared = request.headers.get("content-length")
        try:
            declared_size = int(declared) if declared else None
        except ValueError:
            declared_size = None

        # ★ 先按声明的长度拦一次：超限时**连读都不读**。
        #   这一步在 `save_upload()` 里也有一道（它要先知道上限才知道该不该读），
        #   这里提前拦是为了不让一个 1GB 的请求进到 body 解析。
        suffix_kind = MU.ALLOWED_SUFFIXES.get(
            __import__("os").path.splitext(filename)[1].lower())
        limit = (MU.MAX_VIDEO_BYTES if suffix_kind == "video"
                 else MU.MAX_IMAGE_BYTES)
        if declared_size is not None and declared_size > limit:
            raise HTTPException(
                413, "upload_too_large: 声明 %d 字节，上限 %d" % (declared_size, limit))

        # ★ 用 `await request.body()` 而不是流式：FastAPI 的 `Request.stream()`
        #   是 async 生成器，而 `save_upload()` 要的是同步 read 流。
        #   把 async 桥成同步要在同步函数里起事件循环 —— 那会在 uvicorn 的
        #   线程池里制造第二个 loop，是不稳定来源。
        #
        #   代价：整个文件进内存。所以上面**必须**先按 content-length 拦住，
        #   否则一个没声明长度的 1GB 请求会直接 OOM。
        #   ★ 若将来要真流式，正确做法是让 `save_upload` 接受 async 流，
        #     而不是在这里桥接。
        raw = await request.body()
        if len(raw) > limit:
            raise HTTPException(
                413, "upload_too_large: 实际 %d 字节，上限 %d" % (len(raw), limit))

        try:
            info = MU.save_upload(
                filename=filename,
                stream=__import__("io").BytesIO(raw),
                media_roots=roots,
                declared_size=len(raw),
            )
        except MU.UploadRejected as exc:
            raise HTTPException(exc.status, "%s: %s" % (exc.code, exc.detail)) from exc

        return JSONResponse(content=info, status_code=201)

    @app.post("/api/v1/submissions")
    def create_submission(body: SubmissionBody, request: Request,
                          principal=Depends(principal_dep),
                          idempotency_key: Optional[str] = Header(
                              None, alias="Idempotency-Key")):
        """内容入库：校验 + 判定在 authority 提交之前完成；失败不建案。"""
        require_enabled("/api/v1/submissions")
        if review_command_service is None or submission_ingestor is None:
            raise HTTPException(501, "capability_not_enabled")
        try:
            outcome = review_command_service.execute_submission(
                ingestor=submission_ingestor, submission=body.model_dump(),
                principal=principal, idempotency_key=idempotency_key)
        except SubmissionRejected as exc:
            raise HTTPException(exc.status, "%s: %s" % (exc.code, exc.detail))
        except Exception as exc:  # 领域错误转 HTTP；未知异常继续抛
            raise_command_http(exc, "ingest_submission")
        response = dict(outcome["result"])
        response.update({
            "authority_snapshot": outcome["authority_snapshot"],
            "reconcile_token": outcome["reconcile_token"],
            "projection_lag": outcome["projection_lag"],
            "replayed": outcome["replayed"],
        })
        return JSONResponse(content=response, status_code=outcome["http_status"])

    @app.post("/api/v1/cases/{id}/claim")
    def claim(id: str, request: Request, body: ClaimBody,
              principal=Depends(principal_dep),
              idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/cases/{id}/claim")
        case = case_or_404(id)
        if review_command_service is not None:
            review_command_service.expire_if_due(id)
        require_review(principal, case)
        expected = None if review_command_service else 0
        return run_review_command(
            request=request, principal=principal, case_id=id, command="claim",
            expected_version=expected, payload={}, idempotency_key=idempotency_key,
            legacy_fn=lambda: ledger.claim(id, principal["id"]))

    @app.post("/api/v1/cases/{id}/unclaim")
    def unclaim(id: str, request: Request, body: VersionBody,
                principal=Depends(principal_dep),
                idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/cases/{id}/unclaim")
        case = case_or_404(id)
        require_review(principal, case)
        return run_review_command(
            request=request, principal=principal, case_id=id, command="unclaim",
            expected_version=body.version, payload={}, idempotency_key=idempotency_key,
            legacy_fn=lambda: ledger.unclaim(id, principal["id"], body.version))

    @app.post("/api/v1/cases/{id}/reassign")
    def reassign(id: str, request: Request, body: ReassignBody,
                 principal=Depends(principal_dep),
                 idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/cases/{id}/reassign")
        case = case_or_404(id)
        require_review(principal, case)
        if assignee_validator is not None and not assignee_validator(
                body.assignee, case):
            raise HTTPException(400, "assignee_not_eligible")
        return run_review_command(
            request=request, principal=principal, case_id=id, command="reassign",
            expected_version=body.version, payload={"assignee": body.assignee},
            idempotency_key=idempotency_key,
            legacy_fn=lambda: ledger.reassign(
                id, principal["id"], body.version, body.assignee))

    @app.post("/api/v1/cases/{id}/actions")
    def actions(id: str, request: Request, body: ActionBody,
                principal=Depends(principal_dep),
                idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/cases/{id}/actions")
        case = case_or_404(id)
        require_review(principal, case)

        if review_command_service is not None:
            if body.action == "save_draft":
                draft = body.draft or {}
                return run_review_command(
                    request=request, principal=principal, case_id=id,
                    command="save_draft", expected_version=body.version,
                    payload={
                        "form": draft.get("form") or {},
                        "notes": draft.get("notes") or "",
                        "evidence_selections": draft.get("evidence_selections") or [],
                        "references": draft.get("references") or [],
                    },
                    idempotency_key=idempotency_key,
                    legacy_fn=lambda: None)
            if body.action == "submit":
                if not isinstance(body.conclusion, dict):
                    raise HTTPException(400, "submit 必须带 conclusion")
                return run_review_command(
                    request=request, principal=principal, case_id=id,
                    command="submit_review", expected_version=body.version,
                    payload={"conclusion": body.conclusion},
                    idempotency_key=idempotency_key,
                    legacy_fn=lambda: None)
            if body.action == "heartbeat":
                return run_review_command(
                    request=request, principal=principal, case_id=id,
                    command="heartbeat", expected_version=body.version,
                    payload={}, idempotency_key=idempotency_key,
                    legacy_fn=lambda: None)
            if body.action == "reassign":
                # actions 兼容入口与独立 /reassign 使用同一条持久命令。
                if not isinstance(body.assignee, str) or not body.assignee.strip():
                    raise HTTPException(400, "reassign 必须带 assignee")
                if assignee_validator is not None and not assignee_validator(
                        body.assignee, case):
                    raise HTTPException(400, "assignee_not_eligible")
                return run_review_command(
                    request=request, principal=principal, case_id=id,
                    command="reassign", expected_version=body.version,
                    payload={"assignee": body.assignee.strip()},
                    idempotency_key=idempotency_key,
                    legacy_fn=lambda: None)
            if body.action == "adopt_draft":
                return run_review_command(
                    request=request, principal=principal, case_id=id,
                    command="adopt_draft", expected_version=body.version,
                    payload={"source_draft_id": body.source_draft_id},
                    idempotency_key=idempotency_key,
                    legacy_fn=lambda: None)
            if body.action == "reference_fragment":
                return run_review_command(
                    request=request, principal=principal, case_id=id,
                    command="reference_fragment", expected_version=body.version,
                    payload={"source_draft_id": body.source_draft_id,
                             "field_path": body.field_path,
                             "fragment": body.fragment},
                    idempotency_key=idempotency_key,
                    legacy_fn=lambda: None)
            if body.action in ("confirm", "reject"):
                if not body.finding_id:
                    raise HTTPException(400, "confirm/reject 必须带 finding_id")
                return run_review_command(
                    request=request, principal=principal, case_id=id,
                    command="adjudicate_finding", expected_version=body.version,
                    payload={
                        "finding_id": body.finding_id,
                        "decision": ("confirmed" if body.action == "confirm"
                                     else "rejected"),
                        "reason": body.reason or "",
                    },
                    idempotency_key=idempotency_key,
                    legacy_fn=lambda: None)
            raise HTTPException(501, "capability_not_enabled")

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
            if body.action == "heartbeat":
                return _ledger_call(lambda: ledger.heartbeat(
                    id, principal["id"], body.version))
            if body.action == "reassign":
                if not isinstance(body.assignee, str) or not body.assignee.strip():
                    raise HTTPException(400, "reassign 必须带 assignee")
                if assignee_validator is not None and not assignee_validator(
                        body.assignee, case):
                    raise HTTPException(400, "assignee_not_eligible")
                return _ledger_call(lambda: ledger.reassign(
                    id, principal["id"], body.version, body.assignee.strip()))
            if body.action == "adopt_draft":
                if not isinstance(body.source_draft_id, str) or not body.source_draft_id.strip():
                    raise HTTPException(400, "adopt_draft 必须带 source_draft_id")
                return _ledger_call(lambda: ledger.adopt(
                    id, principal["id"], body.version, body.source_draft_id.strip()))
            if body.action == "reference_fragment":
                if not isinstance(body.source_draft_id, str) or not body.source_draft_id.strip():
                    raise HTTPException(400, "reference_fragment 必须带 source_draft_id")
                if not isinstance(body.field_path, str) or not body.field_path.strip():
                    raise HTTPException(400, "reference_fragment 必须带 field_path")
                return _ledger_call(lambda: ledger.reference_fragment(
                    id, principal["id"], body.version,
                    source_draft_id=body.source_draft_id.strip(),
                    field_path=body.field_path.strip(),
                    fragment=body.fragment))
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

        return _idempotent(
            request, idempotency_key, run, actor=principal["id"],
            request_body=body.model_dump())

    # ── 申诉（T-311c）────────────────────────────────────────────────
    #
    # 生产（review_command_service 非 None）走 reducer 的 appeal_* 命令，
    # 状态进 authority，重启不丢；开发装配仍走内存 AppealStore。
    #
    # ★ 三条共同点：**不再用 _idempotent()**。那个缓存在
    #   `app.state.idempotency`（一个进程内 dict），重启即失 ——
    #   重启后同 key 重放会建出第二条申诉。改成走 authority 的跨重启幂等，
    #   与 /submissions 同一条路。

    def _appeal_authority(principal, case_id):
        """申诉的服务层入口；返回 (service, actor) 或抛 503。"""
        if review_command_service is None:
            raise HTTPException(501, "capability_not_enabled")
        return review_command_service, {
            "principal_id": principal["id"], "tenant_id": principal["tenant"]}

    def _appeal_conflict(exc):
        """领域错误 → HTTP。与 raise_command_http 同口径，但只覆盖申诉会抛的码。"""
        code = getattr(exc, "code", None)
        detail = getattr(exc, "detail", "") or ""
        if code in ("appeal_not_found",):
            return HTTPException(404, "%s: %s" % (code, detail))
        if code in ("not_original_appellant",):
            return HTTPException(403, "%s: %s" % (code, detail))
        if code in ("bad_appeal", "missing_reason"):
            return HTTPException(400, "%s: %s" % (code, detail))
        if code in ("not_paused", "terminal_state", "duplicate_appeal",
                    "version_conflict"):
            return HTTPException(409, "%s: %s" % (code, detail))
        return None

    def _run_appeal(principal, case_id, command, payload, idempotency_key):
        service, actor = _appeal_authority(principal, case_id)
        try:
            outcome = service.execute(
                aggregate_id=case_id, command=command, actor=actor,
                expected_version=None, payload=payload,
                idempotency_key=idempotency_key)
        except Exception as exc:  # noqa: BLE001
            mapped = _appeal_conflict(exc)
            if mapped is not None:
                raise mapped from exc
            raise_command_http(exc, command)
        response = dict(outcome["result"])
        # ★ 平铺一层 appeal 的字段到顶层。
        #
        # 内存版 AppealStore 返回的是**扁平**的 {"appeal_id": ..., "state": ...}，
        # 而权威返回把它包在 result["appeal"] 里。前端 AppealsPage 读的是
        # `created.appeal_id` / `created.state`（顶层）——
        # 不铺这一层，开申诉会返回 200 但前端**静默显示 undefined**，
        # 而且没有任何断言会红（前端只在 dev 下渲染，生产走同一份代码）。
        #
        # 顶层与嵌套都保留：顶层保持与内存版兼容，嵌套保留完整权威结果。
        appeal = response.get("appeal")
        if isinstance(appeal, dict):
            for key, value in appeal.items():
                response.setdefault(key, value)
        response.update({
            "authority_snapshot": outcome["authority_snapshot"],
            "reconcile_token": outcome["reconcile_token"],
            "projection_lag": outcome["projection_lag"],
            "replayed": outcome["replayed"],
        })
        return JSONResponse(content=response, status_code=outcome["http_status"])

    def _require_key(key):
        if not isinstance(key, str) or not key.strip():
            raise HTTPException(400, "缺少 Idempotency-Key")

    @app.post("/api/v1/appeals")
    def create_appeal(request: Request, body: AppealCreate,
                      principal=Depends(principal_dep),
                      idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/appeals")
        case = case_or_404(body.case_id)
        require_tenant(principal, case)
        if review_command_service is not None:
            _require_key(idempotency_key)
            if not isinstance(body.reason, str) or not body.reason.strip():
                raise HTTPException(400, "bad_appeal: reason 必填")
            return _run_appeal(
                principal, body.case_id, "appeal_open",
                {"reason": body.reason.strip(), "tenant": principal["tenant"]},
                idempotency_key)
        return _idempotent(
            request, idempotency_key,
            lambda: appeals.open(body.case_id, principal["id"], body.reason),
            actor=principal["id"], request_body=body.model_dump())

    def _appeal_case_id(principal, appeal_id, idempotency_key, command, payload):
        """把 appeal_id 解析回 case_id，再走权威命令。

        ★ 反查在**服务层**（`find_appeal_case`），不在这里读 state ——
          本文件有一条硬约束 C5「API 层不计算 state/decision」，
          第一版我在 API 里直接扫 authority.state()，被 C5 的扫描器抓到。
          那条约束是对的：API 只编排，不碰状态。
        """
        service, _actor = _appeal_authority(principal, None)
        case_id = service.find_appeal_case(appeal_id, tenant=principal["tenant"])
        if case_id is None:
            raise HTTPException(404, "appeal_not_found: 申诉不存在")
        return _run_appeal(principal, case_id, command,
                           {**payload, "appeal_id": appeal_id},
                           idempotency_key)

    @app.post("/api/v1/appeals/{id}/migrate")
    def migrate_appeal(id: str, request: Request,
                       principal=Depends(principal_dep),
                       idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/appeals/{id}/migrate")
        if review_command_service is not None:
            _require_key(idempotency_key)
            return _appeal_case_id(principal, id, idempotency_key,
                                   "appeal_migrate", {})
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
        return _idempotent(
            request, idempotency_key, run, actor=principal["id"],
            request_body={"appeal_id": id, "action": "migrate"})

    @app.post("/api/v1/appeals/{id}/withdraw")
    def withdraw_appeal(id: str, request: Request, body: AppealWithdraw,
                        principal=Depends(principal_dep),
                        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/appeals/{id}/withdraw")
        if review_command_service is not None:
            _require_key(idempotency_key)
            if not isinstance(body.reason, str) or not body.reason.strip():
                raise HTTPException(400, "missing_reason: 撤销必须写 reason")
            return _appeal_case_id(principal, id, idempotency_key,
                                   "appeal_withdraw",
                                   {"reason": body.reason.strip()})
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
        return _idempotent(
            request, idempotency_key, run, actor=principal["id"],
            request_body={"appeal_id": id, **body.model_dump()})

    def takedown_action(action):
        def handler(id: str, request: Request,
                    principal=Depends(principal_dep),
                    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
            require_enabled("/api/v1/takedown-tasks/{id}/" + action)
            task = task_or_404(id)
            require_tenant(principal, task, "takedown task")
            require_takedown(principal, task, "takedown.execute")

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
            return _idempotent(
                request, idempotency_key, run, actor=principal["id"],
                request_body={"task_id": id, "action": action})
        return handler

    for action in ("start", "fail", "retry"):
        app.add_api_route("/api/v1/takedown-tasks/{id}/" + action,
                          takedown_action(action), methods=["POST"])

    @app.post("/api/v1/takedown-tasks/{id}/complete")
    def takedown_complete(id: str, request: Request, body: TakedownEvidence,
                          principal=Depends(principal_dep),
                          idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/takedown-tasks/{id}/complete")
        task = task_or_404(id)
        require_tenant(principal, task, "takedown task")
        require_takedown(principal, task, "takedown.execute")

        def run():
            try:
                # ★ completed_by 取**已认证的 principal**，不取 body。
                #   取 body 就等于让调用方自己声明「我是谁」——
                #   而 require_takedown 刚刚才用 principal 判过权限，
                #   两处用两个身份来源，等于自己给自己开门。
                new = TD.complete(task, body.evidence, actor=principal["id"])
            except TD.TakedownError as exc:
                raise HTTPException(400, "%s: %s" % (exc.code, exc.detail))
            new["version"] = int(new.get("version") or 0) + 1
            save_task(new)
            return new
        return _idempotent(
            request, idempotency_key, run, actor=principal["id"],
            request_body={"task_id": id, **body.model_dump()})

    @app.post("/api/v1/takedown-tasks/{id}/reassign")
    def takedown_reassign(id: str, request: Request, body: TakedownReassign,
                          principal=Depends(principal_dep),
                          idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/takedown-tasks/{id}/reassign")
        task = task_or_404(id)
        require_tenant(principal, task, "takedown task")
        # TD-12：改派是统筹的职责，不是执行人的职责（见 rbac.can_reassign_takedown）
        if not can_reassign_takedown(principal, task):
            raise HTTPException(403, "无权改派下线任务：需本租户统筹角色")

        def run():
            if body.version is not None and body.version != int(task.get("version") or 0):
                raise HTTPException(409, "version_conflict: 任务版本已变化")
            new = copy.deepcopy(task)
            new["assignee"] = body.assignee
            new["version"] = int(new.get("version") or 0) + 1
            save_task(new)
            return new
        return _idempotent(
            request, idempotency_key, run, actor=principal["id"],
            request_body={"task_id": id, **body.model_dump()})

    @app.post("/api/v1/takedown-tasks/{id}/waive")
    def takedown_waive(id: str, request: Request, body: TakedownWaive,
                       principal=Depends(principal_dep),
                       idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/takedown-tasks/{id}/waive")
        task = task_or_404(id)
        require_tenant(principal, task, "takedown task")
        # ★ 另一把钥匙：takedown.execute 不能作证 waive（见 require_takedown）
        require_takedown(principal, task, "takedown.waive")

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
        return _idempotent(
            request, idempotency_key, run, actor=principal["id"],
            request_body={"task_id": id, **body.model_dump()})

    def _consume_step_up(principal, state, action, token, nonce, now=None):
        """step-up 消费（T-310c）。与 ReleaseGate._consume 同一形状；
        store 来自 app.state —— 生产装配是 RuntimeProxy，开发装配是真 store。
        service 不持有 session（与 reducer 不消费 step-up 同一条分工）。
        """
        store = app.state.session_store
        if store is None:
            raise StepUpError("没有 session store —— step-up 无法消费，拒绝签发")
        if not isinstance(token, str) or not token:
            raise StepUpError("step-up token 缺失")
        ref = store.consume_step_up_ref(
            token, principal.get("id"), state.get("case_id"), action,
            nonce, now=now)
        if not ref:
            raise StepUpError("step-up token 无效（过期/已用/绑定不符）")
        return ref

    @app.post("/api/v1/cases/{id}/release-decision")
    async def release_decision(id: str, request: Request, body: ReleaseDecisionBody,
                         principal=Depends(principal_dep),
                         idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/cases/{id}/release-decision")
        case = case_or_404(id)
        if body.decision not in ("sign", "reject"):
            raise HTTPException(400, "decision 必须是 sign/reject")
        if review_command_service is not None:
            # 生产读权威版本（投影/frozen 的 case 形状没有 case_version 键，
            # 统一用 case.get("case_version") 会在生产恒 409）。
            live = review_command_service.authority.state(id) or {}
            if body.version != live.get("version"):
                raise HTTPException(409, "version_conflict: 案件版本已变化")
            # 生产分支（T-310c）：签发进权威 state["release"]。
            # ★ 判定函数与下面的内存分支是同一份（ReleaseGate._authorize /
            #   _binding / validate_signature），只是状态落点不同 ——
            #   这不是双口径，两条分支并存是施工单 §T-310c 的明文决定。
            def run_prod():
                try:
                    outcome = review_command_service.release_decision(
                        aggregate_id=id, principal=principal,
                        action=body.decision, token=body.step_up_token,
                        nonce=body.nonce, reason=body.reason or "",
                        step_up_consumer=_consume_step_up,
                        idempotency_key=idempotency_key)
                except (SoDViolation, StepUpError, InvalidTransition,
                        SignatureError) as exc:
                    code = type(exc).__name__
                    status = {"SoDViolation": 403, "StepUpError": 403,
                              "InvalidTransition": 409,
                              "SignatureError": 400}[code]
                    raise HTTPException(status, "%s: %s" % (code, exc))
                except AuthorityConflict as exc:
                    raise_command_http(exc, "release_sign")
                except LedgerConflict as exc:
                    raise_command_http(exc, body.decision)
                except LedgerValidation as exc:
                    raise_command_http(exc, body.decision)
                response = dict(outcome["result"])
                response.update({
                    "authority_snapshot": outcome["authority_snapshot"],
                    "reconcile_token": outcome["reconcile_token"],
                    "projection_lag": outcome["projection_lag"],
                    "replayed": outcome["replayed"],
                })
                return JSONResponse(content=response,
                                    status_code=outcome["http_status"])
            # 生产幂等走权威（BusinessEventStore 的跨重启幂等），不走
            # _idempotent 的进程内缓存 —— 与 submission 同一条路。
            if not isinstance(idempotency_key, str) or not idempotency_key.strip():
                raise HTTPException(400, "缺少 Idempotency-Key")
            return run_prod()

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

        return _idempotent(
            request, idempotency_key, run, actor=principal["id"],
            request_body={"case_id": id, **body.model_dump()})

    @app.post("/api/v1/cases/{id}/release-revoke")
    async def release_revoke(id: str, request: Request, body: ReleaseRevokeBody,
                       principal=Depends(principal_dep),
                       idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
        require_enabled("/api/v1/cases/{id}/release-revoke")
        case = case_or_404(id)

        if review_command_service is not None:
            # 生产读权威版本（同 release-decision 的理由）。
            live = review_command_service.authority.state(id) or {}
            if body.version != live.get("version"):
                raise HTTPException(409, "version_conflict: 案件版本已变化")
            def run_prod():
                try:
                    outcome = review_command_service.release_decision(
                        aggregate_id=id, principal=principal, action="revoke",
                        token=body.step_up_token, nonce=body.nonce,
                        reason=body.reason or "",
                        step_up_consumer=_consume_step_up,
                        idempotency_key=idempotency_key)
                except (SoDViolation, StepUpError, InvalidTransition,
                        SignatureError) as exc:
                    code = type(exc).__name__
                    status = {"SoDViolation": 403, "StepUpError": 403,
                              "InvalidTransition": 409,
                              "SignatureError": 400}[code]
                    raise HTTPException(status, "%s: %s" % (code, exc))
                except (AuthorityConflict, LedgerConflict,
                        LedgerValidation) as exc:
                    raise_command_http(exc, "release_revoke")
                response = dict(outcome["result"])
                response.update({
                    "authority_snapshot": outcome["authority_snapshot"],
                    "reconcile_token": outcome["reconcile_token"],
                    "projection_lag": outcome["projection_lag"],
                    "replayed": outcome["replayed"],
                })
                return JSONResponse(content=response,
                                    status_code=outcome["http_status"])
            if not isinstance(idempotency_key, str) or not idempotency_key.strip():
                raise HTTPException(400, "缺少 Idempotency-Key")
            return run_prod()

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

        return _idempotent(
            request, idempotency_key, run, actor=principal["id"],
            request_body={"case_id": id, **body.model_dump()})

    # ── T-313d：通知 read/ack ────────────────────────────────────────
    # 写的是**自己的**收件箱（聚合 = notifications:<tenant>:<principal>），
    # 收件人身份来自 principal，不收 body 指定 —— 否则一个人可以替别人已读。
    # （body 模型在模块级：局部类会让 pydantic 的 ForwardRef 解析炸掉。）

    def _notification_command(command):
        def handler(body: NotificationItemBody, request: Request,
                    principal=Depends(principal_dep),
                    idempotency_key: Optional[str] = Header(
                        None, alias="Idempotency-Key")):
            path = "/api/v1/notifications/{id}/" + command
            require_enabled(path)
            if review_command_service is None:
                # 开发装配：内存 repo 原位标记（重启即丢，与其它开发路径一致）。
                for row in repo.notifications:
                    if row.get("notification_id") == body.notification_id:
                        row["read_at"] = row.get("read_at") or "dev"
                        if command == "ack":
                            row["acked_at"] = row.get("acked_at") or "dev"
                        return {"ok": True, "notification": dict(row)}
                raise HTTPException(404, "notification_not_found")
            try:
                fn = (review_command_service.notification_read
                      if command == "read"
                      else review_command_service.notification_ack)
                outcome = fn(principal=principal,
                             notification_id=body.notification_id,
                             idempotency_key=idempotency_key)
            except LedgerConflict as exc:
                raise_command_http(exc, "notification_" + command)
            except LedgerValidation as exc:
                raise_command_http(exc, "notification_" + command)
            except LedgerNotFound as exc:
                raise_command_http(exc, "notification_" + command)
            response = dict(outcome["result"])
            response.update({
                "authority_snapshot": outcome["authority_snapshot"],
                "reconcile_token": outcome["reconcile_token"],
                "projection_lag": outcome["projection_lag"],
                "replayed": outcome["replayed"],
            })
            return JSONResponse(content=response,
                                status_code=outcome["http_status"])
        return handler

    app.add_api_route("/api/v1/notifications/{id}/read",
                      _notification_command("read"), methods=["POST"])
    app.add_api_route("/api/v1/notifications/{id}/ack",
                      _notification_command("ack"), methods=["POST"])

    return IMPLEMENTED_WRITE_PATHS
