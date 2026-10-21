#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作台复核台账 SQLite 查询投影；可从权威 command batch 全量重建。"""
from __future__ import annotations

import calendar
import copy
import json
import os
import sqlite3
import threading
import time
from pathlib import Path


SCHEMA_VERSION = 1


class ProjectionError(Exception):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


class ProjectionStore:
    def __init__(self, path, *, busy_timeout_ms=5000, clock=None):
        if not isinstance(path, (str, os.PathLike)) or str(path) == ":memory:":
            raise ProjectionError("projection_path", "生产投影必须使用仓外文件 SQLite")
        self.path = Path(path).resolve()
        repo = Path(__file__).resolve().parent.parent
        if self.path == repo or repo in self.path.parents:
            raise ProjectionError("projection_path", "投影库不允许在仓库内")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or time.time
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False,
                                     isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=%d" % int(busy_timeout_ms))
        self._migrate()

    def _migrate(self):
        with self._lock:
            version = int(self._conn.execute("PRAGMA user_version").fetchone()[0])
            if version > SCHEMA_VERSION:
                raise ProjectionError("projection_schema_newer", str(version))
            if version == 0:
                self._conn.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE applied_commands (
                  command_id TEXT PRIMARY KEY,
                  authority_seq INTEGER NOT NULL UNIQUE,
                  request_sha256 TEXT NOT NULL,
                  manifest_sha256 TEXT NOT NULL,
                  applied_at REAL NOT NULL
                );
                CREATE TABLE review_cases (
                  case_id TEXT PRIMARY KEY,
                  version INTEGER NOT NULL,
                  status TEXT NOT NULL,
                  assignee TEXT,
                  state_json TEXT NOT NULL
                );
                CREATE TABLE drafts (
                  draft_id TEXT PRIMARY KEY,
                  case_id TEXT NOT NULL,
                  snapshot_seq INTEGER NOT NULL,
                  author TEXT,
                  content_json TEXT NOT NULL
                );
                CREATE INDEX drafts_case_idx ON drafts(case_id, snapshot_seq);
                CREATE TABLE formal_reviews (
                  formal_id TEXT PRIMARY KEY,
                  case_id TEXT NOT NULL,
                  submitted_at TEXT,
                  content_json TEXT NOT NULL
                );
                CREATE INDEX formal_case_idx ON formal_reviews(case_id, submitted_at);
                CREATE TABLE projection_meta (
                  singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                  applied_seq INTEGER NOT NULL,
                  manifest_sha256 TEXT,
                  rebuilt_at REAL,
                  last_error_code TEXT
                );
                INSERT INTO projection_meta(singleton, applied_seq, manifest_sha256,
                                            rebuilt_at, last_error_code)
                  VALUES(1, 0, NULL, NULL, NULL);
                PRAGMA user_version=1;
                COMMIT;
                """)

    def watermark(self):
        row = self._conn.execute(
            "SELECT applied_seq, manifest_sha256, rebuilt_at, last_error_code "
            "FROM projection_meta WHERE singleton=1").fetchone()
        return dict(row)

    def apply_batch(self, batch):
        if not isinstance(batch, dict):
            raise ProjectionError("batch_type", "batch 必须是对象")
        seq = batch.get("authority_seq")
        events = batch.get("events") or []
        if len(events) != 1 or not isinstance(events[0].get("state"), dict):
            raise ProjectionError("event_shape", "review batch 必须恰好一个完整 state 事件")
        state = copy.deepcopy(events[0]["state"])
        case_id = batch.get("aggregate_id")
        if state.get("case_id") != case_id:
            raise ProjectionError("aggregate_mismatch", "state.case_id 与 aggregate_id 不一致")
        manifest_sha = batch.get("manifest_sha256")
        if not isinstance(manifest_sha, str) or len(manifest_sha) != 64:
            raise ProjectionError("manifest_hash", "batch 缺 manifest_sha256")
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                meta = self._conn.execute(
                    "SELECT applied_seq FROM projection_meta WHERE singleton=1").fetchone()
                applied = int(meta[0])
                existing = self._conn.execute(
                    "SELECT request_sha256, manifest_sha256 FROM applied_commands "
                    "WHERE command_id=?", (batch.get("command_id"),)).fetchone()
                if existing is not None:
                    if (existing[0] != batch.get("request_sha256") or
                            existing[1] != manifest_sha):
                        raise ProjectionError("command_conflict", batch.get("command_id"))
                    self._conn.execute("ROLLBACK")
                    return {"replayed": True, "applied_seq": applied}
                if seq != applied + 1:
                    raise ProjectionError(
                        "projection_sequence", "期望 %d，实际 %r" % (applied + 1, seq))
                stored_hash = self._conn.execute(
                    "SELECT manifest_sha256 FROM projection_meta WHERE singleton=1").fetchone()[0]
                if batch.get("prev_manifest_sha256") != stored_hash:
                    raise ProjectionError(
                        "projection_prefix_mismatch", "投影前缀与权威链不一致")
                self._conn.execute(
                    "INSERT INTO applied_commands(command_id,authority_seq,request_sha256,"
                    "manifest_sha256,applied_at) VALUES(?,?,?,?,?)",
                    (batch["command_id"], seq, batch["request_sha256"],
                     manifest_sha, self.clock()))
                self._conn.execute(
                    "INSERT INTO review_cases(case_id,version,status,assignee,state_json) "
                    "VALUES(?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET "
                    "version=excluded.version,status=excluded.status,assignee=excluded.assignee,"
                    "state_json=excluded.state_json",
                    (case_id, int(state["version"]), state["status"],
                     state.get("assignee"), _json(state)))
                # state 快照是该 aggregate 的完整投影；整案替换可避免幽灵 draft/formal。
                self._conn.execute("DELETE FROM drafts WHERE case_id=?", (case_id,))
                for draft in state.get("drafts") or []:
                    self._conn.execute(
                        "INSERT INTO drafts(draft_id,case_id,snapshot_seq,author,content_json) "
                        "VALUES(?,?,?,?,?)",
                        (draft["draft_id"], case_id, int(draft["snapshot_seq"]),
                         draft.get("author"), _json(draft)))
                self._conn.execute("DELETE FROM formal_reviews WHERE case_id=?", (case_id,))
                for formal in state.get("formal_reviews") or []:
                    self._conn.execute(
                        "INSERT INTO formal_reviews(formal_id,case_id,submitted_at,content_json) "
                        "VALUES(?,?,?,?)",
                        (formal["formal_id"], case_id, formal.get("submitted_at"),
                         _json(formal)))
                self._conn.execute(
                    "UPDATE projection_meta SET applied_seq=?,manifest_sha256=?,"
                    "last_error_code=NULL WHERE singleton=1", (seq, manifest_sha))
                self._conn.execute("COMMIT")
                return {"replayed": False, "applied_seq": seq}
            except Exception:
                try:
                    self._conn.execute("ROLLBACK")
                except sqlite3.Error:
                    pass
                raise

    def mark_error(self, code):
        with self._lock:
            self._conn.execute(
                "UPDATE projection_meta SET last_error_code=? WHERE singleton=1",
                (str(code),))

    def get_case(self, case_id):
        row = self._conn.execute(
            "SELECT state_json FROM review_cases WHERE case_id=?", (case_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_cases(self):
        rows = self._conn.execute(
            "SELECT state_json FROM review_cases ORDER BY case_id").fetchall()
        return [json.loads(row[0]) for row in rows]

    def list_drafts(self, case_id):
        rows = self._conn.execute(
            "SELECT content_json FROM drafts WHERE case_id=? ORDER BY snapshot_seq",
            (case_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def get_draft(self, draft_id):
        row = self._conn.execute(
            "SELECT content_json FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def list_formal(self, case_id):
        rows = self._conn.execute(
            "SELECT content_json FROM formal_reviews WHERE case_id=? "
            "ORDER BY submitted_at, formal_id", (case_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def reset(self):
        with self._lock:
            self._conn.executescript("""
            BEGIN IMMEDIATE;
            DELETE FROM drafts;
            DELETE FROM formal_reviews;
            DELETE FROM review_cases;
            DELETE FROM applied_commands;
            UPDATE projection_meta SET applied_seq=0,manifest_sha256=NULL,
              rebuilt_at=NULL,last_error_code=NULL WHERE singleton=1;
            COMMIT;
            """)

    def mark_rebuilt(self):
        rebuilt_at = time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(self.clock())))
        self._conn.execute(
            "UPDATE projection_meta SET rebuilt_at=? WHERE singleton=1",
            (rebuilt_at,))

    def status(self, authority_head, *, reconcile_token=None):
        try:
            wm = self.watermark()
        except sqlite3.Error:
            return {
                "schema_version": "projection-status/v1",
                "status": "unavailable",
                "authority": {
                    "seq": int(authority_head.get("seq") or 0),
                    "manifest_sha256": authority_head.get("manifest_sha256"),
                    "committed_at": authority_head.get("committed_at"),
                },
                "projection": {
                    "applied_seq": 0, "manifest_sha256": None,
                    "schema_version": SCHEMA_VERSION, "rebuilt_at": None,
                },
                "lag_commits": int(authority_head.get("seq") or 0),
                "lag_seconds": 0.0,
                "last_error_code": "projection_unavailable",
                "reconcile_token": reconcile_token,
            }
        authority_seq = int(authority_head.get("seq") or 0)
        applied = int(wm["applied_seq"])
        error = wm.get("last_error_code")
        if error:
            state = "corrupt"
        elif applied == authority_seq:
            applied_hash = wm.get("manifest_sha256")
            authority_hash = authority_head.get("manifest_sha256")
            if applied_hash != authority_hash:
                state = "corrupt"
                error = "projection_manifest_mismatch"
            else:
                state = "fresh"
        elif applied < authority_seq:
            state = "lagging"
        else:
            state = "corrupt"
            error = "projection_ahead"
        committed = authority_head.get("committed_at")
        lag_seconds = 0.0
        if state == "lagging" and committed:
            try:
                lag_seconds = max(0.0, self.clock() - calendar.timegm(
                    time.strptime(committed, "%Y-%m-%dT%H:%M:%SZ")))
            except ValueError:
                lag_seconds = 0.0
        return {
            "schema_version": "projection-status/v1",
            "status": state,
            "authority": {
                "seq": authority_seq,
                "manifest_sha256": authority_head.get("manifest_sha256"),
                "committed_at": committed,
            },
            "projection": {
                "applied_seq": applied,
                "manifest_sha256": wm.get("manifest_sha256"),
                "schema_version": SCHEMA_VERSION,
                "rebuilt_at": wm.get("rebuilt_at"),
            },
            "lag_commits": max(0, authority_seq - applied),
            "lag_seconds": lag_seconds,
            "last_error_code": error,
            "reconcile_token": reconcile_token,
        }

    def close(self):
        try:
            self._conn.close()
        except sqlite3.Error:
            pass
