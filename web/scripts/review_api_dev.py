#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地联调用的 review-api 入口。

不修改 `api/review_api.py`：这里只把它的 `create_app()` 用**临时投影 +
本地 session store + 最小 principal 表**装配起来，供前端 dev server 连。

  REVIEW_API_DATA_ROOT   投影目录（cases.json 等）
  REVIEW_API_SESSION_DB  session sqlite 路径

启动：
  /path/to/.venv/bin/uvicorn review_api_dev:app --app-dir web/scripts

────────────────────────────────────────────────────────────────────────
★ 2026-10-20 新增：本地身份切换器（`POST /dev/session`）

前端需要能「以某个角色登录」才能演示 RBAC —— 复核动作要认出 principal，
而 `LoginPage` 至今是占位，飞书 OAuth（T-1）未接。

**这个端点只存在于本文件**，即只存在于本地联调入口：
  - 生产入口 `api/review_api.py` 里没有它，一行都没动；
  - 它挂在 `/dev/` 前缀下，不是 `/api/v1/`；
  - 部署时用的不是这个文件，所以它进不了生产。

它做两件事：写一条 session、把 cookie 打进响应。
身份由调用方指定，但**只能从 PRINCIPALS 里选** —— 不接受任意 principal 字符串，
否则它就是一条「随便当任何人」的后门，而这正是它要避免的。
"""
from __future__ import annotations

import ipaddress
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from fastapi import Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from api.review_api import FileProjectionRepository, create_app  # noqa: E402
from base.auth_session import SessionStore  # noqa: E402

DATA_ROOT = os.environ.get("REVIEW_API_DATA_ROOT")
if not DATA_ROOT:
    raise SystemExit("REVIEW_API_DATA_ROOT 未设置")
if os.environ.get("APP_ENV", "").strip().lower() != "dev":
    raise SystemExit("review_api_dev 只允许 APP_ENV=dev")
if os.environ.get("REVIEW_DEV_IDENTITY") != "1":
    raise SystemExit("review_api_dev 需要显式 REVIEW_DEV_IDENTITY=1")

SESSION_DB = os.environ.get("REVIEW_API_SESSION_DB", ":memory:")

# 三个角色，覆盖「能看到 / 能复核 / 不能签发」三档。
# 注意 role 与 capability 是两回事：signer 有资格，但仍受 SoD 与 scope 约束。
PRINCIPALS = {
    "u_dp3": {
        "open_id": "ou_dev_u_dp3",
        "tenant_id": "t1",
        "roles": ["dp3"],
        "product_lines": ["pump", "wearable", "skincare", "feeding"],
        "product_line": "pump",
    },
    "u_dp4": {
        "open_id": "ou_dev_u_dp4",
        "tenant_id": "t1",
        "roles": ["dp4"],
        "product_lines": ["pump", "wearable", "skincare", "feeding"],
        "product_line": "pump",
    },
    "u_signer": {
        "open_id": "ou_dev_u_signer",
        "tenant_id": "t1",
        "roles": ["signer"],
        "product_lines": ["pump"],
        "product_line": "pump",
        "capabilities": ["release.sign", "release.revoke"],
    },
}

# 供前端身份切换器读取：只暴露 id / 显示名 / 角色 / 品线，不暴露任何凭据
DEV_IDENTITIES = [
    {"id": "u_dp3", "label": "DP3 审核员", "roles": ["dp3"],
     "product_lines": PRINCIPALS["u_dp3"]["product_lines"]},
    {"id": "u_dp4", "label": "DP4 法务", "roles": ["dp4"],
     "product_lines": PRINCIPALS["u_dp4"]["product_lines"]},
    {"id": "u_signer", "label": "签发人", "roles": ["signer"],
     "product_lines": PRINCIPALS["u_signer"]["product_lines"]},
]

_store = SessionStore(SESSION_DB)

app = create_app(
    session_store=_store,
    repository=FileProjectionRepository(DATA_ROOT),
    principals=PRINCIPALS,
    app_env="dev",
)


def _loopback_host(host: str) -> bool:
    value = (host or "").strip().lower()
    if value.startswith("["):
        end = value.find("]")
        value = value[1:end] if end > 0 else value
    elif value.count(":") == 1:
        value = value.rsplit(":", 1)[0]
    # 裸 IPv6（如 ::1）含多个冒号，不能按 host:port 规则切。
    if value == "localhost":
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


def _dev_request_allowed(request: Request) -> bool:
    client = request.client.host if request.client else ""
    host = request.headers.get("host", "")
    origin = request.headers.get("origin")
    if not _loopback_host(client) or not _loopback_host(host):
        return False
    if origin:
        parsed = urlparse(origin)
        if parsed.scheme not in ("http", "https") or not _loopback_host(parsed.hostname or ""):
            return False
    return True


def _deny_non_loopback(request: Request) -> JSONResponse | None:
    if _dev_request_allowed(request):
        return None
    return JSONResponse(
        status_code=403,
        content={
            "code": "403",
            "message": "开发身份接口只允许 loopback 请求",
            "details": None,
            "request_id": request.headers.get("x-request-id", ""),
        },
    )


@app.get("/dev/identities")
def dev_identities(request: Request) -> JSONResponse:
    """身份切换器的数据源。只读，不含凭据。"""
    denied = _deny_non_loopback(request)
    if denied is not None:
        return denied
    return JSONResponse({"identities": DEV_IDENTITIES})


@app.post("/dev/session")
async def dev_session(request: Request) -> JSONResponse:
    """
    以指定 principal 建一条 session，并把 opaque cookie 写进响应。

    只接受 PRINCIPALS 里已有的 id —— 这是「选一个已有身份」，
    不是「扮演任意人」。未知 id 一律 400。
    """
    denied = _deny_non_loopback(request)
    if denied is not None:
        return denied
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 — 空体或坏 JSON 都按缺参数处理
        body = {}
    principal_id = (body or {}).get("principal")
    if principal_id not in PRINCIPALS:
        return JSONResponse(
            status_code=400,
            content={
                "code": "400",
                "message": "未知 principal：%r（可选：%s）"
                % (principal_id, ", ".join(sorted(PRINCIPALS))),
                "details": None,
                "request_id": "",
            },
        )

    tenant = PRINCIPALS[principal_id].get("tenant_id", "t1")
    old_cookie = request.cookies.get("session")
    cookie = _store.create_session(principal_id, tenant=tenant)
    if old_cookie and old_cookie != cookie:
        _store.revoke_session(old_cookie)
    response = JSONResponse({"principal": principal_id, "tenant": tenant})
    response.set_cookie(
        key="session",
        value=cookie,
        httponly=True,
        samesite="strict",
        path="/",
    )
    return response
