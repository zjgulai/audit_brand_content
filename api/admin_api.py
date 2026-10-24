#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""api/admin_api.py — T-314b：授权名单治理写路由

四条路由，与前端 P-11（`AdminGrantsPage.tsx`）逐字段对齐：

  POST /api/v1/admin/signer-grants     propose（capability ∈ release.*）
  POST /api/v1/admin/takedown-grants   propose（capability ∈ takedown.*）
  POST /api/v1/admin/grants/{id}/execute
  POST /api/v1/admin/grants/{id}/approve

## 为什么单独一个文件

`write_api.py` 已 1000 行，且 admin 的鉴权链与案件写链完全不同：
案件写按 `can_act(principal, "case.review", case)` 判对象级 ACL；
admin 写按**角色**判（dp4 提案 / it 执行 / coordinator 审批），
对象是「一个租户的名单」，没有案件可挂。

## 三权分立落在哪

- **reducer** 判逐步：同一个人不许走完三步（`same_actor`）；
- **`validate_grant_actors()`** 判综合：角色、能力、scope 不越界，
  只在 **approve** 那一步调用 —— 那一刻三个主体才齐备。

两层不能互相替代：前者防「一个人冒充三个」，后者防「三个不合格的人」。

## 边界

本文件**不计算**任何 state（同 `write_api.py` 的 C5 约束）：
读权威状态一律经 `ReviewCommandService`，路由只做参数整形与错误映射。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from base.rbac import validate_grant_actors

SIGNER_CAPABILITIES = frozenset({"release.sign", "release.revoke"})
TAKEDOWN_CAPABILITIES = frozenset({"takedown.execute", "takedown.waive"})

PROPOSE_PATHS = ("/api/v1/admin/signer-grants", "/api/v1/admin/takedown-grants")
TRANSITION_PATHS = ("/api/v1/admin/grants/{id}/execute",
                    "/api/v1/admin/grants/{id}/approve")


class GrantProposeBody(BaseModel):
    """与前端 P-11 的 POST body 逐字段对齐。

    ★ 前端发的是 `product_line`（单数、一个字符串），而 reducer 的
      `scope.product_lines` 是数组。转换只在这一层做一次 ——
      不让前端改成数组，因为 P-11 的界面就是「一个人 + 一条品线」。
    """
    user_id: str
    capability: str
    product_line: str
    platform: Optional[str] = None
    reason: str


class GrantTransitionBody(BaseModel):
    note: Optional[str] = ""


def _error(exc):
    """领域错误 → HTTP。与 write_api 的 raise_command_http 同口径的子集。"""
    code = getattr(exc, "code", None)
    detail = getattr(exc, "detail", "") or ""
    if code == "grant_not_found":
        return HTTPException(404, "%s: %s" % (code, detail))
    if code == "same_actor":
        return HTTPException(403, "%s: %s" % (code, detail))
    if code in ("bad_grant", "actor_missing", "idempotency_key_missing"):
        return HTTPException(400, "%s: %s" % (code, detail))
    if code in ("not_proposed", "not_executed", "duplicate_grant",
                "version_conflict"):
        return HTTPException(409, "%s: %s" % (code, detail))
    return None


def register_admin_routes(app, *, principal_dep, review_command_service=None,
                          internal_dep=None, enabled_capabilities=None,
                          principal_provider=None):
    """注册四条 admin 写路由。返回已注册的路径集合。"""
    enabled = set(enabled_capabilities or ())
    registered = set()

    if review_command_service is None:
        # 开发装配：不注册，由 review_api 的 501 占位接管。
        return registered

    internal = internal_dep or principal_dep
    #: (principal_id, tenant) -> principal dict | None。approve 那一步用它取前两个主体。
    principal_provider = principal_provider

    def _require(path):
        if path not in enabled:
            raise HTTPException(501, "capability_not_enabled")

    def _require_key(key):
        if not isinstance(key, str) or not key.strip():
            raise HTTPException(400, "缺少 Idempotency-Key")

    def _actor(principal):
        return {"principal_id": principal["id"],
                "tenant_id": principal.get("tenant") or principal.get("tenant_id")}

    def _respond(outcome):
        body = dict(outcome["result"])
        grant = body.get("grant")
        if isinstance(grant, dict):
            # 顶层铺平：前端 GrantRecord 读的是顶层字段（同申诉那个坑）
            for key, value in grant.items():
                body.setdefault(key, value)
        body.update({
            "authority_snapshot": outcome["authority_snapshot"],
            "reconcile_token": outcome["reconcile_token"],
            "projection_lag": outcome["projection_lag"],
            "replayed": outcome["replayed"],
        })
        return JSONResponse(content=body, status_code=outcome["http_status"])

    def _execute(principal, tenant, command, payload, idempotency_key):
        try:
            outcome = review_command_service.execute(
                aggregate_id="grants:" + tenant, command=command,
                actor=_actor(principal), expected_version=None,
                payload=payload, idempotency_key=idempotency_key)
        except Exception as exc:  # noqa: BLE001
            mapped = _error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        return _respond(outcome)

    def _propose(path, allowed):
        def handler(body: GrantProposeBody, request: Request,
                    principal=Depends(internal),
                    idempotency_key: Optional[str] = Header(
                        None, alias="Idempotency-Key")):
            _require(path)
            _require_key(idempotency_key)
            if body.capability not in allowed:
                raise HTTPException(
                    400, "bad_grant: capability 必须是 %r" % (sorted(allowed),))
            tenant = principal.get("tenant") or principal.get("tenant_id")
            if not isinstance(tenant, str) or not tenant.strip():
                raise HTTPException(403, "principal 缺 tenant")
            # ★ 不信任 body 里的 tenant；scope.tenant 一律取 principal 的租户。
            #   否则一个人可以给别的租户提案（越权）。
            scope = {"tenant": tenant, "product_lines": [body.product_line]}
            payload = {
                "capability": body.capability,
                "user_id": body.user_id.strip(),
                "scope": scope,
                "reason": body.reason.strip(),
            }
            if body.platform:
                payload["platform"] = body.platform
            return _execute(principal, tenant, "grant_propose", payload,
                            idempotency_key)
        return handler

    def _transition(action):
        path = "/api/v1/admin/grants/{id}/" + action

        def handler(id: str, request: Request,
                    body: GrantTransitionBody = None,
                    principal=Depends(internal),
                    idempotency_key: Optional[str] = Header(
                        None, alias="Idempotency-Key")):
            _require(path)
            _require_key(idempotency_key)
            tenant = principal.get("tenant") or principal.get("tenant_id")
            if not isinstance(tenant, str) or not tenant.strip():
                raise HTTPException(403, "principal 缺 tenant")
            payload = {"grant_id": id, "tenant": tenant}
            if body is not None and body.note:
                payload["note"] = body.note

            if action == "approve":
                # ★ 三主体综合校验只在 approve 这一步做 —— 那一刻三人齐备。
                #
                # ★★ 第一版这里写成 `hasattr(service, "directory_principal")`，
                #    而 ReviewCommandService 根本没有这个方法 —— 于是 proposer
                #    恒为 None，`if proposer and executor` 恒假，校验**静默跳过**。
                #    那是「接线看起来接上了、实际是空操作」，比不接更坏。
                #
                # 改成**显式要求** principal_provider；没给就是装配错了，
                # 直接 503，不许降级成「跳过校验」。
                if principal_provider is None:
                    raise HTTPException(
                        503, "grant_approval_unavailable: 未装配 principal_provider")
                current = review_command_service.authority.state(
                    "grants:" + tenant)
                target = next((g for g in current.get("grants") or []
                               if g.get("grant_id") == id), None)
                if target is None:
                    raise HTTPException(404, "grant_not_found: 授权不存在")
                proposer = principal_provider(target.get("proposed_by"), tenant)
                executor = principal_provider(target.get("executed_by"), tenant)
                if proposer is None or executor is None:
                    # 名单里的人已从目录消失 —— fail closed，不许放行
                    raise HTTPException(
                        403, "grant_actors_invalid: 提案人或执行人不在目录中")
                if not validate_grant_actors(proposer, executor, principal,
                                             granted_scope=target.get("scope") or {}):
                    raise HTTPException(
                        403, "grant_actors_invalid: 三主体或 scope 不满足")
            return _execute(principal, tenant, "grant_" + action,
                            payload, idempotency_key)
        return handler

    app.add_api_route(PROPOSE_PATHS[0], _propose(PROPOSE_PATHS[0],
                                                 SIGNER_CAPABILITIES),
                      methods=["POST"])
    registered.add(PROPOSE_PATHS[0])
    app.add_api_route(PROPOSE_PATHS[1], _propose(PROPOSE_PATHS[1],
                                                 TAKEDOWN_CAPABILITIES),
                      methods=["POST"])
    registered.add(PROPOSE_PATHS[1])
    for action in ("execute", "approve"):
        app.add_api_route("/api/v1/admin/grants/{id}/" + action,
                          _transition(action), methods=["POST"])
        registered.add("/api/v1/admin/grants/{id}/" + action)
    return registered
