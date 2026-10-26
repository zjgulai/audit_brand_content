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
from fastapi import Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.oauth import FeishuWebOAuthProvider, OAuthError
from api.review_api import AuthorityCaseSource, FileProjectionRepository, create_app
from base.auth_session import SessionStore
from base.business_event_store import BusinessEventStore, WriterLease
from base.principal_directory import PrincipalDirectory
from base.projection_store import ProjectionStore
from base.projector import Projector
from base.rbac import can_act, can_read_content, can_read_report
from base.report_render_bridge import ReportRenderBridge
from base.report_store import ReportStore
from base.review_command_service import ReviewCommandService
from base.submission_service import SubmissionIngestor


PRODUCTION_WRITE_PATHS = {
    "/api/v1/submissions",
    "/api/v1/cases/{id}/claim",
    "/api/v1/cases/{id}/unclaim",
    "/api/v1/cases/{id}/reassign",
    "/api/v1/cases/{id}/actions",
    # T-312b：下线六条。改前它们是 501 —— 而 `IMPLEMENTED_WRITE_PATHS` 里
    # 一直有它们，于是「开发装配能点、生产点了报错」。
    "/api/v1/takedown-tasks/{id}/start",
    "/api/v1/takedown-tasks/{id}/complete",
    "/api/v1/takedown-tasks/{id}/fail",
    "/api/v1/takedown-tasks/{id}/retry",
    "/api/v1/takedown-tasks/{id}/reassign",
    "/api/v1/takedown-tasks/{id}/waive",
    # T-310c：签发两条进权威。原先不放行的原因（缺 kb_snapshot_hash）
    # 已由 T-310a 消除（D1 裁定口径，判定时点写入 state）；
    # 生产分支走 ReviewCommandService.release_decision，状态落
    # state["release"]，不再落内存 gate —— C3j 断言随之翻转为「必须在册」。
    "/api/v1/cases/{id}/release-decision",
    "/api/v1/cases/{id}/release-revoke",
    # T-315c：撤权端点（grant_revoke 命令；能力判定在路由 + reducer 两层）。
    "/api/v1/admin/grants/{id}/revoke",
    # T-313d：通知 read/ack（写自己的收件箱）。
    "/api/v1/notifications/{id}/read",
    "/api/v1/notifications/{id}/ack",
    # T-402：名单治理四条（propose ×2 / execute / approve）。
    #
    # ★ 改前它们**不在**本表，而 `api/admin_api.register_admin_routes()` 已经在
    #   生产装配（service 非 None）里注册了它们 —— 于是「开发装配能点、
    #   生产点了返 501 capability_not_enabled」。与 T-312b 那六条下线同形状。
    #
    # ★ 为什么要这四条**一起**进：它们是三权分立的**同一条链**的三个必经步骤。
    #   只放 propose 会让人提了单永远批不了（execute/approve 仍 501），
    #   而「提案成功」这个 200 看起来像功能可用 —— 那比全 501 更误导。
    #
    # ★ `/admin/grants/{id}/revoke` 早就在本表里（T-315c 直接加的生产表，
    #   没经过 `IMPLEMENTED_WRITE_PATHS`）。它不在这四条之内，本票不改它；
    #   这处表间不一致由 T-408 的「spec ≡ 实现表」断言显式表态。
    "/api/v1/admin/signer-grants",
    "/api/v1/admin/takedown-grants",
    "/api/v1/admin/grants/{id}/execute",
    "/api/v1/admin/grants/{id}/approve",
    # T-401a：申诉三条（open / migrate / withdraw）。
    #
    # ★ 与 T-312b/T-402 同一个病：`IMPLEMENTED_WRITE_PATHS` 里一直有它们、
    #   `ReviewCommandService` 也早已实现（T-311 done），**只有本表没有** ——
    #   于是生产下 P-06 的每一个按钮都返 501。
    #
    # ★ 三条一起进，理由同 T-402：它们是同一个申诉状态机的三条命令。
    #   只放 open 会让人开了申诉永远撤不掉 / 迁不掉。
    #
    # ★ 光加这三条**不够**（本票最花时间的地方）：`GET /api/v1/appeals`
    #   改前只读 frozen `appeals.json`（盘上不存在），于是「POST 200、
    #   列表永远空」。读侧改造在同一次提交里（`api/review_api.py` 的
    #   `list_appeals` 分支），否则票面判据「重启后仍可读」永远绿不了。
    "/api/v1/appeals",
    "/api/v1/appeals/{id}/migrate",
    "/api/v1/appeals/{id}/withdraw",
    # T-403：报告重签（ADR-0017）。它**不写权威状态**，只签发一条带时效的链接。
    # 加进本表是因为生产闸门按「能力表」拦写请求 —— 不放行就永远 501。
    "/api/v1/reports/{id}/resign",
}
def build_allowlist_source(projection):
    """`rbac._ALLOWLIST_SOURCE` 的生产实现：读投影里的已批准授权。

    返回 {capability: frozenset(principal_id)}。

    ★ 只读 `grant_registry` 表（投影），不读权威 —— 心跳每秒可能调很多次，
      读 SQLite 比扫权威的 manifest 链便宜得多。投影 fresh 由
      `maintain_once()` 的 reconcile 保证。
    ★ 任何异常都回落空集：名单读不到时「没人能下线」比「谁都能下线」安全。
    ★ **只收 state == "approved"**：撤权（T-315a）把 grant 迁出 approved 后
      人自动出局 —— S-b（撤权后新签被拒）的机制性来源。模块级函数是为了
      让 verify_grant_registry 直接 import 真身，而不是在验证器里养一份镜像。
    """
    empty = {"takedown.execute": frozenset(), "takedown.waive": frozenset(),
             "release.sign": frozenset()}
    if projection is None:
        return empty
    try:
        out = {k: set() for k in empty}
        for state in projection.list_grant_registries():
            for grant in state.get("grants") or []:
                if grant.get("state") != "approved":
                    continue
                cap = grant.get("capability")
                if cap in out and isinstance(grant.get("user_id"), str):
                    out[cap].add(grant["user_id"])
        return {k: frozenset(v) for k, v in out.items()}
    except Exception:
        return empty


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


#: ADR-0017 §四：签名密钥的环境变量。`_PREV` 只用于**验**（轮换窗口），
#: 绝不用于签 —— 若也用它签，轮换就永远「轮」不完。
LINK_SECRET_ENV = "REVIEW_REPORT_LINK_SECRET"
LINK_SECRET_PREV_ENV = "REVIEW_REPORT_LINK_SECRET_PREV"
LINK_TTL_ENV = "REVIEW_REPORT_LINK_TTL"
#: 密钥最短 32 字节。短于此直接**构造期拒**（不是运行时降级）：
#: 一条弱密钥签出来的链接与强密钥长得一样，而危害只在被攻破时才显形。
LINK_SECRET_MIN_BYTES = 32


def _link_secrets_from_env(env, *, required=False):
    """读签名密钥。返回 `(new, *prev)`；没配返回空元组。

    ★ **不设默认值**：一条内置的默认密钥等于「所有人都知道密钥」。
    ★ 长度不足 → `SettingsError`（构造期拒），不是静默忽略：
      忽略会让部署方以为配好了，而 `resign` 一直返 503。
    """
    out = []
    for name in (LINK_SECRET_ENV, LINK_SECRET_PREV_ENV):
        raw = (env.get(name) or "").strip()
        if not raw:
            continue
        if len(raw.encode("utf-8")) < LINK_SECRET_MIN_BYTES:
            raise SettingsError("%s_too_short（至少 %d 字节）"
                                % (name.lower(), LINK_SECRET_MIN_BYTES))
        out.append(raw)
    if required and not out:
        raise SettingsError("report_link_secret_missing")
    return tuple(out)


def _link_ttl_from_env(env):
    """读 TTL。缺省 1 小时；越界（<=0 或 >30 天）构造期拒。

    ★ 上限必须有执行点，否则「过期签名」会退化成「永不过期」——
      那样这个端点存在的唯一理由就没了（ADR-0017 §五）。
    """
    from base.report_store import LINK_TTL_DEFAULT_SECONDS, LINK_TTL_MAX_SECONDS
    raw = (env.get(LINK_TTL_ENV) or "").strip()
    if not raw:
        return LINK_TTL_DEFAULT_SECONDS
    if not raw.isdigit():
        raise SettingsError("report_link_ttl_not_a_number")
    value = int(raw)
    if value <= 0 or value > LINK_TTL_MAX_SECONDS:
        raise SettingsError("report_link_ttl_out_of_range")
    return value


@dataclass(frozen=True)
class ProductionSettings:
    authority_root: Path
    frozen_projection_root: Path
    review_projection_db: Path
    session_db: Path
    access_log_path: Path
    principal_directory: Path
    # T-316d：报告落盘根。**必填，无默认值** —— 原因见 __post_init__ 的注释。
    report_root: Path
    public_origin: str
    oauth_client_id: str
    oauth_client_secret: str
    oauth_redirect_uri: str
    oauth_reauth_redirect_uri: str | None = None
    oauth_scope: str = "auth:user.id:read"
    tenant_allowlist: frozenset[str] = frozenset()
    #: ADR-0017：报告链接签名密钥，**新的在前**。空 = 本部署不签发带签名链接
    #: （`resign` 返 503）。★ 刻意**没有默认值也不是必填**：报告读写在无密钥时
    #: 必须照常工作 —— 让整个报告系统因为「没配签名密钥」起不来，
    #: 代价远大于「重签不可用」。
    report_link_secrets: tuple[str, ...] = ()
    report_link_ttl: int = 3600
    #: T-431/T-437：图片进件允许的位图根目录（`REVIEW_MEDIA_ROOTS`，逗号分隔）。
    #:
    #: ★ 默认**空**，且空 = 不收图（`SubmissionIngestor` 会在 `_build_image_unit`
    #:   里返 503 `media_root_not_configured`）。这不是保守，是安全边界：
    #:   没有根约束时那个端点会变成「对机器上任意文件做 OCR 并回显正文」的读取器。
    #:
    #: ★ 与 `report_root` 那批路径**不同**：它们是「写出去的」数据根，
    #:   必须彼此不重叠；这里是「读进来的」素材根，只要求存在且是目录，
    #:   **允许**放在仓外任意可读位置，也**允许**与写路径重叠（比如素材就放在
    #:   authority_root 旁边）。把它塞进 `path_names` 会让「素材目录与数据目录
    #:   同处一个父目录」变成构造期失败，而那是一个完全正常的部署。
    media_roots: tuple[str, ...] = ()

    def __post_init__(self):
        # ★ `report_root` 必须在这里，不能只加一个字段。
        #
        #   `path_names` 决定两件事：路径**不许在仓内**、且**不许彼此重叠**。
        #   报告正文是内容（含 IR 与依据），落在仓内等于把内容提交进公开仓
        #   —— 与 `base/takedown.py` 那条「截图落仓外、不进公开仓」是同一个理由。
        #   而「与 access_log 同一路径」会让报告文件与 audit 日志在一个文件里，
        #   两个写者互相截断。
        path_names = (
            "authority_root", "frozen_projection_root", "review_projection_db",
            "session_db", "access_log_path", "principal_directory",
            "report_root",
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
        # ★ 素材根：与上面那批「写路径」用**不同**的规矩。
        #
        #   写路径：不许在仓内、不许彼此重叠（理由见上）。
        #   素材根：允许在仓外任何可读目录，**也允许**与写路径重叠。
        #   但两条必须有：
        #     ① 必须是**存在的目录** —— 配了一个不存在的根，等于配了一道永远 404 的门，
        #        而运维会以为「已经允许这个目录了」。
        #     ② 不许是 `:memory:` 之类的空值（那是把「没配」写成「配了」）。
        #   ★ 刻意**不**在这里校验「在仓内就拒」：素材可能是仓内的测试夹具目录。
        #     真上线时若要收窄，那是另一条策略，不该在构造期悄悄决定。
        roots = []
        for index, raw in enumerate(self.media_roots):
            text = str(raw or "").strip()
            if not text:
                raise SettingsError("media_roots[%d]_empty" % index)
            path = Path(text).expanduser().resolve()
            if not path.is_dir():
                raise SettingsError("media_roots[%d]_not_a_directory" % index)
            if path in roots:
                raise SettingsError("media_roots[%d]_duplicate" % index)
            roots.append(path)
        object.__setattr__(self, "media_roots", tuple(str(p) for p in roots))

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
            "REVIEW_REPORT_ROOT",
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
        # ★ `REVIEW_MEDIA_ROOTS` **不是必填**：不配 = 不收图（这是默认且安全的）。
        #   但一旦配了，每一项都要能过 `__post_init__` 的存在性检查 ——
        #   「配了个不存在的目录」与「没配」必须长得不一样，否则运维会以为
        #   门已经开了。逗号分隔，允许前后空白。
        media_roots = tuple(
            x.strip() for x in (env.get("REVIEW_MEDIA_ROOTS") or "").split(",")
            if x.strip())
        authority_root = external("REVIEW_AUTHORITY_ROOT", directory=True)
        frozen_root = external("REVIEW_FROZEN_PROJECTION_ROOT", directory=True)
        projection_db = external("REVIEW_PROJECTION_DB")
        session_db = external("REVIEW_API_SESSION_DB")
        access_log = external("REVIEW_API_ACCESS_LOG")
        principal_directory = external("REVIEW_PRINCIPAL_DIRECTORY")
        report_root = external("REVIEW_REPORT_ROOT", directory=True)
        paths = (authority_root, frozen_root, projection_db, session_db,
                 access_log, principal_directory, report_root)
        if len(set(paths)) != len(paths):
            raise SettingsError("data_paths_must_be_distinct")
        return ProductionSettings(
            authority_root=authority_root,
            frozen_projection_root=frozen_root,
            review_projection_db=projection_db,
            session_db=session_db,
            access_log_path=access_log,
            principal_directory=principal_directory,
            report_root=report_root,
            public_origin=origin,
            oauth_client_id=env["REVIEW_OAUTH_CLIENT_ID"],
            oauth_client_secret=env["REVIEW_OAUTH_CLIENT_SECRET"],
            oauth_redirect_uri=redirect,
            oauth_reauth_redirect_uri=env["REVIEW_OAUTH_REAUTH_REDIRECT_URI"],
            oauth_scope=env.get("REVIEW_OAUTH_SCOPE", "auth:user.id:read"),
            tenant_allowlist=tenants,
            report_link_secrets=_link_secrets_from_env(env),
            report_link_ttl=_link_ttl_from_env(env),
            media_roots=media_roots,
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
        self.report_store = None
        self.report_bridge = None
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
                self.settings.report_root,
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
            # T-316d：报告落盘。
            #
            # ★ ACL 用 `can_read_content(principal, case)`，**不用**
            #   `ReportStore._default_authorize`。后者读 `principal["role"]`
            #   （单数、"DP3" 大写），而真实 principal 是 `roles`（复数、小写）
            #   —— 接上即全禁，而 `verify_report_store.py` 的夹具恰好用单数大写，
            #   所以它一直绿。这是第五处「验证器形状 ≠ 生产形状」。
            #
            # ★ static_base 用 public_origin + "/static"：报告正文是静态文件，
            #   由反代服务；它不是 API 端点（`_check_static_base` 会拒含 api 的路径）。
            self.report_store = ReportStore(
                str(self.settings.report_root),
                self.settings.public_origin + "/static",
                authorize=self._report_authorize,
                # ADR-0017：链接签名密钥（新的在前）。生产必须显式给；
                # 没给时报告系统照常工作，只有 `resign` 返 503 ——
                # **不许**降级成「发一个无签名的『新链接』」。
                link_secrets=self.settings.report_link_secrets,
                link_ttl=self.settings.report_link_ttl)
            self.report_bridge = ReportRenderBridge(
                str(Path(__file__).resolve().parent.parent))
            # T-317c：重审执行体的两个注入点 —— 外部绑定采集（规则表 + KB
            # 快照的**当前**值）与真重判（judge_unit 用当前快照重跑）。
            _ingestor = SubmissionIngestor()
            from base.control_points import ControlPointRegistry as _CPR

            def _external_binding():
                from base.rule_judge import RuleJudge as _RJ
                reg = _CPR()
                kb_id = _ingestor._kb_snapshot()
                import hashlib as _hl
                return {
                    "rule_snapshot": {"version": "rules-v1",
                                      # 与 judge_entry 同一来源：RuleJudge 的快照指纹
                                      "hash": _RJ(reg).rule_snapshot_sha256},
                    "kb_snapshot": {"version": kb_id,
                                    "hash": _hl.sha256(
                                        kb_id.encode("utf-8")).hexdigest()},
                    "conflict_table_version": reg.table_version,
                    "raw_sha256": None, "text_sha256": None,
                    "media_fingerprints": [],
                    "used_authority_refs": [],
                }

            def _rejudge(state):
                judgment = _ingestor.judge_fn(
                    state["content"],
                    authority_query=_ingestor._query(),
                    kb_snapshot=_ingestor._kb_snapshot())
                return {
                    "ir": judgment["ir"],
                    "report_snapshot": judgment.get("report_snapshot"),
                    "judgment": {"label": judgment.get("label"),
                                 "layer": judgment.get("layer"),
                                 "release_status": judgment.get("release_status"),
                                 "run_state": judgment.get("run_state"),
                                 "receipt": judgment.get("receipt")},
                    "kb_snapshot_hash": __import__("hashlib").sha256(
                        _ingestor._kb_snapshot().encode("utf-8")).hexdigest(),
                    "conflict_table_version":
                        judgment["ir"].get("control_points_version"),
                    "media_fingerprints":
                        judgment["ir"].get("media_fingerprints") or {},
                }

            self.service = ReviewCommandService(
                self.authority, self.projection,
                report_store=self.report_store,
                report_bridge=self.report_bridge,
                external_binding_provider=_external_binding,
                rejudge_fn=_rejudge)
            # T-314c：把「已批准的授权名单」注入 rbac。
            #
            # 改前 `TAKEDOWN_ALLOWLIST` 是模块级常量且两个名单都是空集 ——
            # 授权写进权威后 `can_act` 仍读常量，于是「授权成功、实际不生效」。
            #
            # ★ 注入源里**只收 state == "approved"** 的记录：proposed / executed
            #   都还不算授权（三权分立没走完）。差这一步，一张提案就能开下线权。
            # ★ 读不到投影时返回空集（fail closed），不是「全放行」。
            from base import rbac as _rbac
            _rbac.set_allowlist_source(self.allowlist_source)
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

    # 报告 ACL：口径与判据都在 `base/rbac.can_read_report`（单一来源）。
    # 生产与验证器调同一个函数 —— 否则「验证器绿、生产全禁」会再来一次。
    _report_authorize = staticmethod(can_read_report)

    def allowlist_source(self):
        """`rbac._ALLOWLIST_SOURCE` 的生产实现：读投影里的已批准授权。"""
        return build_allowlist_source(self.projection)

    def maintain_once(self):
        if self.service is None or self.authority is None:
            raise RuntimeError("runtime_not_started:maintenance")
        try:
            self.service.reconcile()
            # T-317c：失效扫描 —— 每个 signed 案件当前外部绑定 vs 签名绑定；
            # 无变化是常态（invalidate_if_due 返 None），有变化建重审 job。
            for case_id in list(self.authority.aggregate_ids()):
                try:
                    self.service.invalidate_if_due(case_id)
                except Exception:  # noqa: BLE001
                    pass
            for case_id in self.authority.aggregate_ids():
                self.service.expire_if_due(case_id)
            # T-311b：申诉「暂停超 30 天转 stale」的**唯一生产触发点**。
            # 改前 `AppealStore.mark_stale()` 全仓只有验证器调过一次，
            # 生产里 0 调用 —— 一条没有触发点的规则等于没有规则。
            # 挂在心跳（30s）而不是 GET /appeals：读端点写状态会让
            # 「打开列表」变成一次写操作，且并发下会撞版本。
            # 失败不上浮（mark_appeals_stale 自己收集 errors），
            # 否则一个案件的 stale 失败会让整轮心跳记成不就绪。
            self.service.mark_appeals_stale()
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
            # ★ 2026-10-26：`report_root` 此前不在这个循环里，而 `start()` 的
            #   `_ensure_private_dir` 循环**含**它。两处口径不一致的后果是：
            #   报告目录被换成 0755（或整个丢了），`/readyz` 仍然七项全 true。
            #   实测到的组合是「列表有、点开 404、readyz 全绿」——
            #   三个读数各自都对，合起来是一次数据缺失。
            #   两个循环现在覆盖同一组目录，这一条由 verify_image_shape 的 I4 断言。
            self.settings.report_root,
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
    # ── 报告重签（T-403 / ADR-0017）─────────────────────────────────
    #
    # 为什么单独一条路由而不是塞进 review_api 的通用写链：
    #   `resign` 不写任何权威状态（正文与索引都不变），它只产出**一条链接**。
    #   走 `ReviewCommandService.execute()` 会凭空产生一条 command batch，
    #   而那会让「重签」在审计里看起来像一次状态变更 —— 它不是。
    #
    # ★ 审计仍然留：每次重签写一行 access-log（谁、什么时候、对哪条报告）。
    #   链接是有时效的凭据，签发凭据这件事必须可追溯。
    def resign_report(id: str, request: Request):
        cookie = request.cookies.get(COOKIE_NAME)
        session = session_or_503(cookie)
        if not session:
            raise HTTPException(401, "缺少或无效 session")
        principal = runtime.directory.by_id(session["principal"],
                                           session["tenant"])
        if (principal is None or
                (session.get("authz_version") is not None and
                 session.get("authz_version") != principal.get("authz_version"))):
            raise HTTPException(401, "主体授权已变化，请重新登录")
        store = runtime.report_store
        if store is None:
            raise HTTPException(503, "report_store_unavailable")
        # ★ 鉴权走**索引里的 acl**（`ReportStore.resign` 内部调 `authorize`），
        #   不先反查 case —— 报告是内容寻址的独立对象，`case_id` 可能已结案
        #   而 assignee 被清空；用 case 反查会让「结案后本人也重签不了」。
        out = store.resign(id, principal)
        if not out.get("ok"):
            detail = str(out.get("detail") or "")
            # ★ 密钥缺失 → 503，**不是** 200 也不是 500：
            #   它是「这个部署没开启这项能力」，与「报告坏了」完全不同。
            #   ADR-0017 §四：绝不许降级成「发一个无签名的『新链接』」。
            if out.get("needs_secret"):
                raise HTTPException(
                    503, "report_link_signing_unavailable: 服务端未配置签名密钥")
            if detail == "not_found":
                raise HTTPException(404, "报告不存在")
            if detail == "forbidden":
                raise HTTPException(403, "无权为该报告申请重签")
            raise HTTPException(500, "resign_failed: %s" % detail)
        # ★ `AccessLog.write` 只有固定字段（不接 extra）。链接签发是「发凭据」
        #   这一类动作，必须留痕；把 `exp`/`ttl` 写进 `reason` 而不是改日志
        #   结构 —— 改结构会牵动所有既有读日志的脚本，而这是 T-403 不该付的代价。
        # ★ `AccessLog` 挂在 `app.state.access_log`（`create_app` 建的），
        #   **不在 runtime 上** —— 第一版写成 `runtime.access_log`，
        #   实测 AttributeError 把整个请求打成 500。
        #   审计写失败**不许**让重签失败：链接已经签出来了，
        #   这里失败只丢一条日志，而回滚它会让用户以为没签成、再点一次。
        try:
            request.app.state.access_log.write(
                principal=principal, method="POST", target=request.url.path,
                reason="report_resign exp=%s ttl=%s" % (out.get("exp"),
                                                        out.get("ttl")),
                env="production")
        except Exception:  # noqa: BLE001
            pass
        return {"report_id": id, "url": out["url"],
                "exp": out["exp"], "ttl": out["ttl"],
                # ★ 明确告诉调用方：正文没动。前端据此显示「旧报告保持不可变」。
                "content_unchanged": True, "sha256": out.get("sha256")}


    app = create_app(
        session_store=RuntimeProxy(runtime, "session_store"),
        repository=frozen,
        principal_provider=principal_provider,
        review_read_store=projection_proxy,
        # T-313d：通知收件箱读投影（按 tenant+recipient 过滤）。
        notification_reader=lambda tenant, recipient: (
            projection_proxy.list_notifications(tenant=tenant,
                                                recipient=recipient)
            if projection_proxy is not None else None),
        review_command_service=review_service_proxy,
        enabled_write_capabilities=PRODUCTION_WRITE_PATHS,
        review_freshness_provider=require_projection_fresh_for_shared_route,
        case_state_provider=lambda case_id: (
            runtime.authority.state(case_id) if runtime.authority is not None else None),
        review_assignee_validator=lambda principal_id, case: bool(
            runtime.directory and runtime.directory.eligible_assignee(principal_id, case)),
        case_source=AuthorityCaseSource(RuntimeProxy(runtime, "authority")),
        # T-437：素材根从 settings 读。不配 = 不收图（`_build_image_unit` 返 503）。
        # ★ 为什么不在这里发明默认值：默认值会让「没配」显示成「配了」，
        #   而这个端点的安全性完全取决于根目录约束。
        submission_ingestor=SubmissionIngestor(
            media_roots=getattr(runtime.settings, "media_roots", ()) or ()),
        # T-314b：approve 那一步要用它取提案人与执行人的 principal
        grant_principal_provider=principal_provider,
        session_cookie_name=COOKIE_NAME,
        app_env="production",
        access_log_path=str(settings.access_log_path),
        # T-403 / ADR-0017：报告重签的真实实现。注入而非事后 add_api_route ——
        # 占位循环在 create_app 内部注册，事后追加会「先到先得」而占位先赢。
        report_resign_handler=resign_report,
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
            # ★ 2026-10-22：把**实际收到的** tenant_key 说出来。
            #
            # 原先只回 `tenant_not_allowed`，而配置者需要对上的是飞书返回的
            # opaque 值（形如 `on_xxxx`，不是租户显示名）。瞎猜一次就要走一轮
            # 「改 .env → 重启 → 扫码登录」，而扫码需要真人。
            #
            # 为什么可以回显：调用方**刚刚完成飞书授权**，这个值本来就属于他；
            # 且它不是凭据 —— 拿到它不能换任何东西。反过来，把它藏起来会让
            # 配置变成盲猜。
            raise HTTPException(
                403, "tenant_not_allowed:收到 %r，允许列表 %s"
                     % (identity.tenant_id, sorted(settings.tenant_allowlist)))
        principal = runtime.directory.by_identity(identity.tenant_id, identity.open_id)
        if principal is None:
            # ★ 2026-10-22：同一条理由 —— 把实际收到的身份回显给配置者。
            #   与 tenant_not_allowed 那次是同一个病的第二次：
            #   配置者要对上的是飞书返回的 opaque open_id（`ou_xxxx`），
            #   而 `principals.json` 里现在填的是占位符。
            #   不回显就要再走一轮「改文件 → 重启 → 扫码」，扫码要真人。
            #
            #   为什么可以回显：调用方**刚刚完成飞书授权**，这就是他自己的身份；
            #   它不是凭据（拿 open_id 换不到 access_token）。
            raise HTTPException(
                403, "principal_not_authorized:tenant=%r open_id=%r name=%r"
                     % (identity.tenant_id, identity.open_id, identity.name))
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

    # ── 报告正文（T-316d）────────────────────────────────────────────
    #
    # ★ 为什么由本服务自己 serve，而不是交给反代：
    #   1. 宿主机共享反代在**容器里**，看不到本服务的 `REVIEW_REPORT_ROOT`
    #      （挂载）—— 与 SPA 那条完全同一个理由（见下段注释）。
    #   2. 就算能看见，静态文件服务也**不做授权**。报告正文含 IR、依据、
    #      未审说明 —— 让反代裸 serve 等于任何人拿到 URL 就能读。
    #      本路由走 `ReportStore.read()`，那里有 `can_read_report`。
    #
    # ★ 路径必须与 `static_base` 一致（`public_origin + "/static"` +
    #   `/reports/<id>.md`）。`ReportStore._valid_url` 会校验这个前缀，
    #   两处不一致的话发布的每条报告都会被判 `bad_url`。
    #
    # ★ 必须注册在 SPA fallback **之前**：那个 `/{full_path:path}` 会吃掉
    #   `/static/...` 并回落成 index.html，于是报告 URL 打开是前端首页。
    #
    # ★ 未登录 → 401 而不是 403：这条路径是「拿 URL 就能试」的形状，
    #   区分「没登录」与「登录了但无权」对排障有用，且 401 不会泄露
    #   「这个 report_id 存在」。
    @app.get("/static/reports/{report_id}.md", include_in_schema=False)
    def report_body(report_id: str, request: Request):
        cookie = request.cookies.get(COOKIE_NAME)
        session = runtime.session_store.get_session(cookie) if cookie else None
        if not session:
            raise HTTPException(401, "缺少或无效 session")
        # 与 `principal_provider` 同一条路：session 只存 id/tenant，
        # principal 本体从 directory 现取（那里是唯一真相）。
        try:
            principal = runtime.directory.by_id(
                session["principal"], session["tenant"])
        except Exception:  # noqa: BLE001
            raise HTTPException(503, "principal_directory_unavailable")
        if not principal:
            raise HTTPException(401, "无法解析 principal")
        store = runtime.report_store
        if store is None:
            raise HTTPException(503, "report_store_unavailable")
        # ADR-0017：把**请求者实际用的那个链接**交给 store 验签。
        # ★ 传给 store 的是「不含 scheme/host 的部分也要能比」——
        #   这里用完整 URL：`request.url` 在容器里是 http://127.0.0.1，
        #   而 public_origin 是 https://ca.example，两者**不同**。
        #   所以不拿 request.url 比前缀，改为把 path+query 拼回 static_base。
        link_url = "%s%s" % (
            store.static_base,
            request.url.path[len("/static"):] + (
                "?" + request.url.query if request.url.query else ""))
        out = store.read(report_id, principal, link_url=link_url)
        # ★ 不区分「不存在」与「无权」：两者都返回 404。
        #   区分开会让这条路径变成一个 report_id 枚举器。
        #
        # ★ 但「链接过期/被篡改」必须**不同**（ADR-0017 §三）：
        #   那是「链接失效」而不是「报告不存在」，用户要看到的是
        #   「请申请重签」而不是「报告没了」—— 两者的下一步动作完全相反。
        detail = str(out.get("detail") or "")
        if not out.get("ok") and detail.startswith("link_expired"):
            raise HTTPException(403, "链接已过期，请申请重签")
        if not out.get("ok") and detail in (
                "link_bad_signature", "link_bad_params", "link_bad_exp",
                "link_bad_sig_shape", "link_wrong_report", "link_no_secret"):
            raise HTTPException(403, "链接无效")
        if not out.get("ok"):
            raise HTTPException(404, "报告不存在")
        return Response(content=out["content"], media_type="text/markdown; charset=utf-8",
                        headers={"Cache-Control": "private, max-age=0, must-revalidate"})

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
        _index = os.path.join(_web_root, "index.html")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str):
            """SPA 深链接回落。

            `StaticFiles(html=True)` 只在**目录**请求上返回 index.html，
            不会为 `/queue`、`/cases/xxx` 这类客户端路由回落 —— 实测直接 404。
            而单页应用的这些路径必须由前端路由接管。

            优先级：真实静态文件 > index.html。绝不接管 /api/ 与 /auth/
            （它们在 mount 之前已注册，走不到这里；这条注释是给未来改的人看的）。
            """
            candidate = os.path.normpath(os.path.join(_web_root, full_path))
            # 防目录穿越：规范化后必须仍在 _web_root 内
            if (candidate.startswith(_web_root + os.sep) or candidate == _web_root) \
                    and os.path.isfile(candidate):
                return FileResponse(candidate)
            return FileResponse(_index)

    return app


def app_from_env():
    return create_production_app(ProductionSettings.from_env())
