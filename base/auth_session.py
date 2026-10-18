#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/auth_session.py — T0-07 切片 1：服务端会话与 step-up

边界：
- Session 独立 SQLite（不与业务投影共库）；cookie 只含 opaque id，不含身份/权限/tenant。
- idle 30 分钟 / absolute 8 小时；活动只续 idle，不续 absolute；撤销立即失效。
- step-up token：TTL 5 分钟、single-use、绑定 principal + case + action + nonce。
- session DB 丢失/重建 → 全部 session + step-up 失效（查不到即拒绝）。
- 本模块不做 RBAC/ACL；权限判断在 review-api / release_gate。
"""

import re
import secrets
import sqlite3
import time

IDLE_SECONDS = 30 * 60
ABSOLUTE_SECONDS = 8 * 60 * 60
STEP_UP_SECONDS = 5 * 60

_OPAQUE_RE = re.compile(r"^[A-Za-z0-9_-]{20,}$")


def _absolute_expired(created_at, now):
    return (now - created_at) > ABSOLUTE_SECONDS


def _single_use_violation(used):
    return bool(used)


def is_opaque_cookie(value):
    """cookie 只能是 opaque id；带 '=' ':' '|' 或过短都拒绝。"""
    if not isinstance(value, str):
        return False
    if any(ch in value for ch in ("=", ":", "|", " ", "\n", "\t")):
        return False
    return bool(_OPAQUE_RE.match(value))


class SessionStore(object):
    def __init__(self, db_path):
        self.db_path = db_path
        # FastAPI / TestClient 的同步依赖可能在 portal/threadpool 线程执行；
        # 连接创建于主线程，必须允许跨线程使用（仍由单连接串行化）。
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                principal TEXT NOT NULL,
                tenant TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_activity REAL NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0
            )"""
        )
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS step_up_tokens (
                token TEXT PRIMARY KEY,
                principal TEXT NOT NULL,
                case_id TEXT NOT NULL,
                action TEXT NOT NULL,
                nonce TEXT NOT NULL,
                expires_at REAL NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL
            )"""
        )
        self._conn.commit()

    @staticmethod
    def _now(now):
        return time.time() if now is None else float(now)

    def create_session(self, principal, tenant="t1", now=None):
        """创建服务端 session，返回只含 opaque id 的 cookie。"""
        now = self._now(now)
        sid = secrets.token_urlsafe(32)
        self._conn.execute(
            "INSERT INTO sessions (id, principal, tenant, created_at, last_activity, revoked) "
            "VALUES (?, ?, ?, ?, ?, 0)",
            (sid, principal, tenant, now, now),
        )
        self._conn.commit()
        return sid

    def get_session(self, cookie, now=None):
        """有效则返回 {principal, tenant} 并续 idle；否则 None。"""
        if not is_opaque_cookie(cookie):
            return None
        now = self._now(now)
        row = self._conn.execute(
            "SELECT principal, tenant, created_at, last_activity, revoked "
            "FROM sessions WHERE id = ?",
            (cookie,),
        ).fetchone()
        if row is None:
            return None
        principal, tenant, created_at, last_activity, revoked = row
        if revoked:
            return None
        if _absolute_expired(created_at, now):
            return None
        if (now - last_activity) > IDLE_SECONDS:
            return None
        self._conn.execute(
            "UPDATE sessions SET last_activity = ? WHERE id = ?", (now, cookie)
        )
        self._conn.commit()
        return {"principal": principal, "tenant": tenant}

    def revoke_session(self, cookie):
        self._conn.execute("UPDATE sessions SET revoked = 1 WHERE id = ?", (cookie,))
        self._conn.commit()

    def issue_step_up(self, principal, case_id, action, nonce, now=None):
        now = self._now(now)
        token = secrets.token_urlsafe(32)
        self._conn.execute(
            "INSERT INTO step_up_tokens "
            "(token, principal, case_id, action, nonce, expires_at, used, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
            (token, principal, case_id, action, nonce, now + STEP_UP_SECONDS, now),
        )
        self._conn.commit()
        return token

    def consume_step_up(self, token, principal, case_id, action, nonce,
                        now=None):
        """校验并消费 token；成功返回 True，任一绑定/时限/单次校验失败返回 False。"""
        if not isinstance(token, str) or not token:
            return False
        now = self._now(now)
        row = self._conn.execute(
            "SELECT principal, case_id, action, nonce, expires_at, used "
            "FROM step_up_tokens WHERE token = ?",
            (token,),
        ).fetchone()
        if row is None:
            return False
        t_principal, t_case, t_action, t_nonce, expires_at, used = row
        if now > expires_at:
            return False
        if _single_use_violation(used):
            return False
        if (t_principal != principal or t_case != case_id or
                t_action != action or t_nonce != nonce):
            return False
        self._conn.execute(
            "UPDATE step_up_tokens SET used = 1 WHERE token = ?", (token,)
        )
        self._conn.commit()
        return True

    def invalidate_all(self):
        """模拟 session DB 丢失后的全失效：清空 session 与 step-up。"""
        self._conn.execute("DELETE FROM sessions")
        self._conn.execute("DELETE FROM step_up_tokens")
        self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
