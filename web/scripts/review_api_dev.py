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

from types import SimpleNamespace  # noqa: E402

from api.review_api import (  # noqa: E402
    AuthorityCaseSource,
    FileProjectionRepository,
    create_app,
)
from base import rbac  # noqa: E402
from base.auth_session import SessionStore  # noqa: E402
from base.authority_review_reader import AuthorityReviewReader  # noqa: E402
from base.business_event_store import BusinessEventStore, WriterLease  # noqa: E402
from base.finding_store import FindingRejected, FindingStore  # noqa: E402
from base.projection_store import ProjectionStore  # noqa: E402
from base.review_command_service import ReviewCommandService  # noqa: E402
from base.submission_service import SubmissionIngestor  # noqa: E402

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
_repo = FileProjectionRepository(DATA_ROOT)
_finding_store = FindingStore()

# ★ D-3 修复：把投影案件里的 finding 预热进 FindingStore（供本地联调就地 confirm/reject 使用）。
#   1. 空 quote 的边界夹具（用于测试 UI 渲染「无原文引用」）不满足 FindingStore 非空 quote 准入，跳过；
#   2. FindingStore.transition(new_status="confirmed") 在 produced_by="semantic" 时由 M1 要求
#      confirmed_by_rule_class=True（与 tools/verify_write_api.py:123 同口径）。
for _case in _repo.list_cases():
    _ir = (_case or {}).get("ir") or {}
    for _f in _ir.get("findings") or []:
        if not isinstance(_f, dict):
            continue
        _fid = _f.get("finding_id")
        if not _fid or _finding_store.get(_fid) is not None:
            continue
        _rec = dict(_f)
        if _rec.get("produced_by") == "semantic" and _rec.get("status") == "candidate":
            _rec["confirmed_by_rule_class"] = True
        try:
            _finding_store.insert(_rec)
        except FindingRejected:
            pass

# ── 开发装配接通写路径 + 媒体上传（ADR-0021 主线）─────────────────────
#
# ★ 改前这个装配**没有** review_command_service，于是 `POST /submissions`
#   恒 501 —— 于是提交页永远只能显示那段「前端 3 条正则算出来的即时审计」。
#   实测（2026-10-28）：只传 service 仍然 501，`write_api.py` 是**两道门**
#   （`review_command_service is None or submission_ingestor is None`），
#   四个部件缺一不可。
#
# ★ 所有落盘位置都在 `${RUN_DIR}`（仓外 tmp）下：
#   `ProjectionStore.__init__` 硬性拒绝仓内路径（`projection_store.py:37-38`），
#   素材根同理 —— 下载物 / 上传物进公开仓是 §2.6 红线。
_DEV_STATE = Path(DATA_ROOT).parent / "runtime"
_DEV_STATE.mkdir(parents=True, exist_ok=True)
_DEV_MEDIA_ROOT = _DEV_STATE / "media"
_DEV_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

_dev_lease = WriterLease(_DEV_STATE / "authority" / "writer.lock")
_dev_lease.acquire()
_dev_authority = BusinessEventStore(_DEV_STATE / "authority", lease=_dev_lease)
_dev_projection = ProjectionStore(_DEV_STATE / "projection.sqlite")
_dev_service = ReviewCommandService(_dev_authority, _dev_projection)
_dev_ingestor = SubmissionIngestor(media_roots=[str(_DEV_MEDIA_ROOT)])
# ★ 打开媒体进件：开发环境要能真的试图片/视频。
#   `REVIEW_MEDIA_INGEST` 读的是**环境变量**，所以这里设进 os.environ ——
#   与生产走同一条读法（不设模块常量，那会让「自证测的开关」与
#   「生产读的开关」变成两个东西，§2.4.8）。
os.environ.setdefault("REVIEW_MEDIA_INGEST", "1")

app = create_app(
    session_store=_store,
    repository=_repo,
    finding_store=_finding_store,
    principals=PRINCIPALS,
    app_env="dev",
    review_command_service=_dev_service,
    submission_ingestor=_dev_ingestor,
    case_source=AuthorityCaseSource(_dev_authority),
    # ★★ 台账摘要也必须读 authority —— 否则「认领」在界面上永远不会生效。
    #
    #   改前这里是 `None`，于是 `review` 摘要从**内存 ReviewsLedger** 读，
    #   而写路径（claim / unclaim / actions）写的是 **authority**。
    #   两份数据分叉，实测：
    #
    #       POST /cases/case-c4964393/claim → 200  version=1
    #       GET  /cases/case-c4964393       → review.status="unassigned" version=0
    #
    #   表现是界面显示「请求已接受，但台账回读未完成」，而请求**确实成功了**。
    #   这条不是时序问题：它在同一次请求之后立刻、且永远发生。
    review_read_store=AuthorityReviewReader(_dev_authority),
)
# 上传端点从 `app.state.production_settings` 读素材根。
# 开发装配没有 ProductionSettings，这里给一个最小替身 —— 只带 `media_roots`。
app.state.production_settings = SimpleNamespace(media_roots=(str(_DEV_MEDIA_ROOT),))

# ── 开发装配套上人级名单（否则 P-08 下线台全链路 403）───────────────
#
# ★ 为什么必须有这一条：`base/rbac.py` 把下线执行/豁免与 release.sign 定为
#   **人级名单**，且「未注入名单源 → 回落空集 → 全拒」（fail closed）。
#   生产装配会注入 `build_allowlist_source(projection)`；而本开发装配
#   **此前没有注入**，于是 `POST /takedown-tasks/{id}/start` 恒 403。
#
#   实测代价：`bash web/scripts/dev-up.sh` 在阶段 [8/11]
#   （`check_review_actions.mjs` 的真点击 Start）**必然失败**，
#   而且失败信息是 `403 Forbidden` —— 读起来像权限缺陷，实际是
#   「开发夹具少接了一根线」。`git stash` 掉本轮改动后复跑同样 rc=1，
#   确认是既有问题、不是新增回归。
#
# ★ 只放**开发身份**，而且是逐条点名（不是「dev 环境全放行」）：
#   写成全放行会让开发环境的行为与生产无可比性，本地能过的东西上线就 403 ——
#   那正是 TS-1「本地能过就上线」要禁止的形状。
# ★ `takedown.waive` 刻意不授给 u_dp3：豁免要求双人审批 + 独立钥匙，
#   本地把它放开会让那条链在开发下**看起来**通过，而生产里没人能豁免。
DEV_ALLOWLIST = {
    # ★ 只能点名 **u_signer**：`rbac._ROLE_CAPS` 里只有 signer 有
    #   `takedown.execute` 这个角色能力（dp3/dp4 只有 case.review / appeal.handle）。
    #   第一版写成 {"u_dp3"}，实测仍然 403 —— 因为名单是**第二道**门，
    #   角色能力是**第一道**门，两道都得过。写错的那一版看起来「名单已经配好了」，
    #   而实际拦住它的是前一道，报的还是同一个 403 —— 无法从症状反推是哪一道。
    "takedown.execute": frozenset({"u_signer"}),
    "takedown.waive": frozenset(),
    "release.sign": frozenset({"u_signer"}),
}
rbac.set_allowlist_source(lambda: DEV_ALLOWLIST)


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
