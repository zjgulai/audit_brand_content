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

import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
import time

IDLE_SECONDS = 30 * 60
ABSOLUTE_SECONDS = 8 * 60 * 60
STEP_UP_SECONDS = 5 * 60

_OPAQUE_RE = re.compile(r"^[A-Za-z0-9_-]{20,}$")


def _absolute_expired(created_at, now):
    return (now - created_at) > ABSOLUTE_SECONDS


def is_opaque_cookie(value):
    """cookie 只能是 opaque id；带 '=' ':' '|' 或过短都拒绝。"""
    if not isinstance(value, str):
        return False
    if any(ch in value for ch in ("=", ":", "|", " ", "\n", "\t")):
        return False
    return bool(_OPAQUE_RE.match(value))


class SessionStore(object):
    def __init__(self, db_path, *, busy_timeout_ms=5000,
                 step_up_audit_path=None, auth_audit_path=None,
                 generation_file=None):
        self.db_path = db_path
        self.step_up_audit_path = step_up_audit_path
        self.auth_audit_path = auth_audit_path
        self.generation_file = generation_file
        existed = db_path != ":memory:" and os.path.exists(db_path)
        self._lock = threading.RLock()
        # FastAPI / TestClient 的同步依赖可能在 portal/threadpool 线程执行；
        # 连接创建于主线程，必须允许跨线程使用；所有事务由本类的 RLock 串行化。
        self._conn = sqlite3.connect(db_path, check_same_thread=False,
                                     isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=%d" % int(busy_timeout_ms))
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
        self._migrate()
        self._bind_generation(existed)

    def _bind_generation(self, existed):
        if not self.generation_file:
            return
        path = os.path.abspath(self.generation_file)
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        generation_exists = os.path.exists(path)
        if not generation_exists:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.write(fd, secrets.token_urlsafe(32).encode("ascii"))
                os.fsync(fd)
            finally:
                os.close(fd)
        elif not existed:
            # generation 文件是独立长期状态；DB 消失后新建必须轮换，
            # 后续把旧 DB 拷回来时其内 generation 会失配并被清空。
            fd = os.open(path, os.O_TRUNC | os.O_WRONLY, 0o600)
            try:
                os.write(fd, secrets.token_urlsafe(32).encode("ascii"))
                os.fsync(fd)
            finally:
                os.close(fd)
        generation = open(path, encoding="ascii").read().strip()
        if not generation:
            raise RuntimeError("session_generation_unreadable")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS session_generation ("
            "singleton INTEGER PRIMARY KEY CHECK(singleton=1), generation TEXT NOT NULL)")
        row = self._conn.execute(
            "SELECT generation FROM session_generation WHERE singleton=1").fetchone()
        if row is None:
            if existed and generation_exists:
                # DB 文件仍存在但 generation 表消失：视为重置/旧备份，
                # 轮换长期 generation，避免随后拷回旧 DB 时旧会话复活。
                generation = secrets.token_urlsafe(32)
                fd = os.open(path, os.O_TRUNC | os.O_WRONLY, 0o600)
                try:
                    os.write(fd, generation.encode("ascii"))
                    os.fsync(fd)
                finally:
                    os.close(fd)
                self._conn.execute("DELETE FROM sessions")
                self._conn.execute("DELETE FROM step_up_tokens")
                self._conn.execute("DELETE FROM oauth_states")
            self._conn.execute(
                "INSERT INTO session_generation(singleton,generation) VALUES(1,?)",
                (generation,))
        elif row[0] != generation:
            self._conn.execute("DELETE FROM sessions")
            self._conn.execute("DELETE FROM step_up_tokens")
            self._conn.execute("DELETE FROM oauth_states")
            self._conn.execute(
                "UPDATE session_generation SET generation=? WHERE singleton=1",
                (generation,))

    def _columns(self, table):
        return {row[1] for row in self._conn.execute(
            "PRAGMA table_info(%s)" % table).fetchall()}

    def _add_column(self, table, name, declaration):
        if name not in self._columns(table):
            self._conn.execute(
                "ALTER TABLE %s ADD COLUMN %s %s" % (table, name, declaration))

    def _migrate(self):
        # 旧 session.db 原地升级；字段缺失和“值为空”是两种状态，不回退默认身份。
        for name, declaration in (
            ("csrf_hash", "TEXT"),
            ("auth_time", "REAL"),
            ("provider", "TEXT"),
            ("issuer", "TEXT"),
            ("revoked_at", "REAL"),
            ("revoke_reason", "TEXT"),
            ("audit_ref", "TEXT"),
            ("authz_version", "TEXT"),
        ):
            self._add_column("sessions", name, declaration)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS oauth_states (
                state_hash TEXT PRIMARY KEY,
                nonce TEXT NOT NULL,
                flow TEXT NOT NULL,
                redirect_uri TEXT NOT NULL,
                principal TEXT,
                case_id TEXT,
                action TEXT,
                browser_nonce TEXT,
                expires_at REAL NOT NULL,
                consumed_at REAL,
                created_at REAL NOT NULL
            )"""
        )
        self._add_column("oauth_states", "browser_nonce", "TEXT")

    @staticmethod
    def _digest(value):
        if not isinstance(value, str) or not value:
            return None
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _now(now):
        return time.time() if now is None else float(now)

    def create_session(self, principal, tenant="t1", now=None, *,
                       provider=None, issuer=None, csrf_token=None,
                       auth_time=None, audit_ref=None, authz_version=None):
        """创建服务端 session，返回只含 opaque id 的 cookie。"""
        now = self._now(now)
        sid = secrets.token_urlsafe(32)
        with self._lock:
            self._conn.execute(
                "INSERT INTO sessions "
                "(id,principal,tenant,created_at,last_activity,revoked,csrf_hash,"
                "auth_time,provider,issuer,audit_ref,authz_version) "
                "VALUES(?,?,?,?,?,0,?,?,?,?,?,?)",
                (sid, principal, tenant, now, now, self._digest(csrf_token),
                 now if auth_time is None else float(auth_time),
                 provider, issuer, audit_ref, authz_version),
            )
        return sid

    def get_session(self, cookie, now=None):
        """有效则返回 {principal, tenant} 并续 idle；否则 None。"""
        if not is_opaque_cookie(cookie):
            return None
        now = self._now(now)
        with self._lock:
            row = self._conn.execute(
                "SELECT principal, tenant, created_at, last_activity, revoked, authz_version "
                "FROM sessions WHERE id = ?", (cookie,)).fetchone()
            if row is None:
                return None
            principal, tenant, created_at, last_activity, revoked, authz_version = row
            if revoked or _absolute_expired(created_at, now) or (now - last_activity) > IDLE_SECONDS:
                return None
            self._conn.execute(
                "UPDATE sessions SET last_activity = ? WHERE id = ? AND revoked=0",
                (now, cookie))
            return {"principal": principal, "tenant": tenant,
                    "authz_version": authz_version}

    def _append_audit(self, path, record):
        if not path:
            return
        raw = (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, mode=0o700, exist_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_APPEND | os.O_WRONLY, 0o600)
        try:
            view = memoryview(raw)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)

    def revoke_session(self, cookie, *, actor=None, reason=None, now=None):
        now = self._now(now)
        with self._lock:
            cur = self._conn.execute(
                "UPDATE sessions SET revoked=1,revoked_at=?,revoke_reason=? "
                "WHERE id=?", (now, reason, cookie))
        self._append_audit(self.auth_audit_path, {
            "ts": now, "event": "session_revoked",
            "session_ref": "session:" + (self._digest(cookie) or "")[:24],
            "actor_hash": self._digest(actor), "reason": reason,
            "matched": cur.rowcount == 1,
        })

    def issue_step_up(self, principal, case_id, action, nonce, now=None):
        now = self._now(now)
        token = secrets.token_urlsafe(32)
        token_hash = self._digest(token)
        with self._lock:
            self._conn.execute(
                "INSERT INTO step_up_tokens "
                "(token, principal, case_id, action, nonce, expires_at, used, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 0, ?)",
                (token_hash, principal, case_id, action, nonce,
                 now + STEP_UP_SECONDS, now),
            )
        return token

    def _audit_step_up(self, *, ref, principal, case_id, action, success, now):
        if not self.step_up_audit_path:
            return
        record = {
            "ts": float(now), "step_up_ref": ref,
            "principal_hash": self._digest(principal),
            "case_hash": self._digest(case_id), "action": action,
            "success": bool(success),
        }
        self._append_audit(self.step_up_audit_path, record)

    def consume_step_up_ref(self, token, principal, case_id, action, nonce,
                            now=None):
        """原子消费并返回不可逆 audit ref；失败返回 None。"""
        if not isinstance(token, str) or not token:
            return None
        now = self._now(now)
        token_hash = self._digest(token)
        ref = "stepup:" + token_hash[:24]
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                cur = self._conn.execute(
                    "UPDATE step_up_tokens SET used=1 WHERE token=? AND principal=? "
                    "AND case_id=? AND action=? AND nonce=? AND used=0 AND expires_at>=?",
                    (token_hash, principal, case_id, action, nonce, now),
                )
                success = cur.rowcount == 1
                self._audit_step_up(
                    ref=ref, principal=principal, case_id=case_id, action=action,
                    success=success, now=now)
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
        return ref if success else None

    def consume_step_up(self, token, principal, case_id, action, nonce,
                        now=None):
        """兼容旧调用：校验并消费，成功 True、失败 False。"""
        return self.consume_step_up_ref(
            token, principal, case_id, action, nonce, now=now) is not None

    def rotate_csrf(self, cookie):
        token = secrets.token_urlsafe(32)
        with self._lock:
            cur = self._conn.execute(
                "UPDATE sessions SET csrf_hash=? WHERE id=? AND revoked=0",
                (self._digest(token), cookie))
            if cur.rowcount != 1:
                return None
        return token

    def verify_csrf(self, cookie, token):
        digest = self._digest(token)
        if digest is None:
            return False
        with self._lock:
            row = self._conn.execute(
                "SELECT csrf_hash,revoked FROM sessions WHERE id=?", (cookie,)).fetchone()
        return bool(row and not row[1] and secrets.compare_digest(row[0] or "", digest))

    def session_metadata(self, cookie):
        if not is_opaque_cookie(cookie):
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT principal,tenant,created_at,last_activity,auth_time,provider,issuer,"
                "revoked,revoked_at,revoke_reason,audit_ref FROM sessions WHERE id=?",
                (cookie,)).fetchone()
        if row is None:
            return None
        keys = ("principal", "tenant", "created_at", "last_activity", "auth_time",
                "provider", "issuer", "revoked", "revoked_at", "revoke_reason",
                "audit_ref")
        return dict(zip(keys, row))

    def issue_oauth_state(self, *, flow, redirect_uri, nonce, principal=None,
                          case_id=None, action=None, browser_nonce=None,
                          now=None, ttl=300):
        now = self._now(now)
        state = secrets.token_urlsafe(32)
        with self._lock:
            self._conn.execute(
                "INSERT INTO oauth_states(state_hash,nonce,flow,redirect_uri,principal,"
                "case_id,action,browser_nonce,expires_at,consumed_at,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,NULL,?)",
                (self._digest(state), nonce, flow, redirect_uri, principal,
                 case_id, action, browser_nonce, now + float(ttl), now))
        return state

    def consume_oauth_state(self, state, *, flow, redirect_uri,
                            browser_nonce=None, now=None):
        now = self._now(now)
        with self._lock:
            if browser_nonce is None:
                cur = self._conn.execute(
                    "UPDATE oauth_states SET consumed_at=? WHERE state_hash=? "
                    "AND flow=? AND redirect_uri=? AND browser_nonce IS NULL "
                    "AND consumed_at IS NULL AND expires_at>=?",
                    (now, self._digest(state), flow, redirect_uri, now))
            else:
                cur = self._conn.execute(
                    "UPDATE oauth_states SET consumed_at=? WHERE state_hash=? "
                    "AND flow=? AND redirect_uri=? AND browser_nonce=? "
                    "AND consumed_at IS NULL AND expires_at>=?",
                    (now, self._digest(state), flow, redirect_uri,
                     browser_nonce, now))
            if cur.rowcount != 1:
                return None
            row = self._conn.execute(
                "SELECT nonce,principal,case_id,action FROM oauth_states WHERE state_hash=?",
                (self._digest(state),)).fetchone()
        return {"nonce": row[0], "principal": row[1],
                "case_id": row[2], "action": row[3]}

    def invalidate_all(self):
        """模拟 session DB 丢失后的全失效：清空 session 与 step-up。"""
        with self._lock:
            self._conn.execute("DELETE FROM sessions")
            self._conn.execute("DELETE FROM step_up_tokens")
            self._conn.execute("DELETE FROM oauth_states")

    def ready(self):
        try:
            with self._lock:
                row = self._conn.execute("SELECT 1").fetchone()
            return bool(row and row[0] == 1)
        except sqlite3.Error:
            return False

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
