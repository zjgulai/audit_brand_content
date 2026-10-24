#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作台业务权威事件：不可变 command batch + manifest 链。

SQLite 不是本模块的真相源；它只消费这里的已提交批次。
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

from base.artifact_store import ArtifactStore
from base.review_reducer import (
    aggregate_type_for, initial_state, reduce_command)


class AuthorityError(Exception):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


class AuthorityConflict(AuthorityError):
    pass


class AuthorityCorrupt(AuthorityError):
    pass


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _iso(now):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(now)))


class WriterLease:
    """跨进程单写者租约；OS flock + owner token + inode。

    flock 随进程/FD 关闭自动释放，不能被 PID 复用或陈旧锁文件永久卡死。
    """

    def __init__(self, path):
        self.path = Path(path)
        self.owner = secrets.token_urlsafe(24)
        self.inode = None
        self.acquired = False
        self.fd = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise AuthorityConflict("writer_lease_held", "已有存活写者") from exc
            payload = _canonical({
                "pid": os.getpid(), "owner": self.owner, "acquired_at": time.time(),
            }).encode("utf-8")
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            view = memoryview(payload)
            while view:
                written = os.write(fd, view)
                view = view[written:]
            os.fsync(fd)
            self.inode = os.fstat(fd).st_ino
            self.fd = fd
            self.acquired = True
            return self
        except Exception:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)
            raise

    def assert_owner(self):
        if not self.acquired or self.inode is None or self.fd is None:
            raise AuthorityConflict("writer_lease_missing", "当前进程没有 writer lease")
        try:
            stat = self.path.stat()
            os.lseek(self.fd, 0, os.SEEK_SET)
            data = json.loads(os.read(self.fd, 4096).decode("utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise AuthorityConflict("writer_lease_lost", type(exc).__name__) from exc
        if stat.st_ino != self.inode or data.get("owner") != self.owner:
            raise AuthorityConflict("writer_lease_lost", "writer lease owner/inode 已变化")

    def release(self):
        if self.fd is None:
            self.acquired = False
            self.inode = None
            return
        # 锁文件本身长期保留；若先 unlink 再 unlock，另一进程可在旧 inode
        # 仍持锁时创建新 inode，形成两个“唯一”写者。
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)
        self.fd = None
        self.acquired = False
        self.inode = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, _typ, _value, _traceback):
        self.release()


class BusinessEventStore:
    """已提交 command batch 的读写门；要求调用方持有 WriterLease。"""

    def __init__(self, root, *, lease=None, clock=None):
        self.root = Path(root).resolve()
        self.artifacts = ArtifactStore(str(self.root))
        self.lease = lease
        self.clock = clock or time.time
        self._lock = threading.RLock()
        self._batches = []
        self._states = {}
        self._idempotency = {}
        self._head_hash = None
        self._load()

    def _manifest_files(self):
        return sorted(Path(self.artifacts.manifests).glob("*.json"))

    @staticmethod
    def _manifest_hash(path):
        return _sha(path.read_bytes())

    def _load(self):
        rows = []
        referenced_events = set()
        for path in self._manifest_files():
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise AuthorityCorrupt("manifest_unreadable", path.name) from exc
            for entry in manifest.get("entries", []):
                rel = entry.get("path") if isinstance(entry, dict) else None
                if isinstance(rel, str) and rel.startswith("events/"):
                    referenced_events.add(rel)
            if "authority_seq" not in manifest:
                continue  # 既有 run manifest 不是业务命令链。
            rows.append((int(manifest["authority_seq"]), path, manifest))
        rows.sort(key=lambda item: item[0])
        previous = None
        for expected, (seq, path, manifest) in enumerate(rows, 1):
            if seq != expected:
                raise AuthorityCorrupt("authority_sequence", "期望 %d，实际 %d" % (expected, seq))
            if manifest.get("prev_manifest_sha256") != previous:
                raise AuthorityCorrupt("authority_chain", "seq=%d 前序哈希不符" % seq)
            event_entries = [e for e in manifest.get("entries", [])
                             if str(e.get("path", "")).startswith("events/")]
            if len(event_entries) != 1:
                raise AuthorityCorrupt("command_event_entry", "seq=%d event条目数=%d" %
                                       (seq, len(event_entries)))
            event_entry = event_entries[0]
            rel = Path(event_entry["path"])
            if rel.is_absolute() or ".." in rel.parts or rel.parts[0] != "events":
                raise AuthorityCorrupt("command_event_path", "seq=%d" % seq)
            event_path = self.root / rel
            try:
                raw = event_path.read_bytes()
                if _sha(raw) != event_entry.get("sha256"):
                    raise AuthorityCorrupt("command_event_hash", event_path.name)
                batch = json.loads(raw.decode("utf-8"))
            except AuthorityCorrupt:
                raise
            except (OSError, ValueError, UnicodeError) as exc:
                raise AuthorityCorrupt("command_event_unreadable", event_path.name) from exc
            if batch.get("authority_seq") != seq or batch.get("command_id") != manifest.get("command_id"):
                raise AuthorityCorrupt("command_manifest_mismatch", "seq=%d" % seq)
            previous = self._manifest_hash(path)
            self._index(batch, manifest_sha256=previous, replay=True)
        self._head_hash = previous
        # manifest rename 前崩溃可能只留下最终 events 文件。它不是已提交权威，
        # 但会占住下一次同 command_id 的不可变路径。只有持 lease 的唯一写者
        # 可以在启动时清；只读实例则明确报 corrupt，不安静忽略。
        events_root = Path(self.artifacts.events)
        uncommitted = sorted(
            path for path in events_root.glob("*.json")
            if path.relative_to(self.root).as_posix() not in referenced_events)
        if uncommitted:
            if self.lease is None:
                raise AuthorityCorrupt(
                    "authority_uncommitted_event",
                    ",".join(path.name for path in uncommitted))
            self.lease.assert_owner()
            for path in uncommitted:
                path.unlink()

    def _index(self, batch, *, manifest_sha256, replay):
        key = (batch["actor"]["principal_id"], batch["actor"]["tenant_id"],
               batch["idempotency_key"])
        if key in self._idempotency:
            raise AuthorityCorrupt("idempotency_duplicate", batch["idempotency_key"])
        saved = copy.deepcopy(batch)
        saved["manifest_sha256"] = manifest_sha256
        self._idempotency[key] = saved
        self._batches.append(saved)
        events = batch.get("events") or []
        if len(events) != 1 or not isinstance(events[0].get("state"), dict):
            raise AuthorityCorrupt("review_event_shape", batch["command_id"])
        self._states[batch["aggregate_id"]] = copy.deepcopy(events[0]["state"])

    def verify_integrity(self):
        with self._lock:
            return self._verify_integrity_locked()

    def _verify_integrity_locked(self):
        rows = []
        for path in self._manifest_files():
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeError) as exc:
                raise AuthorityCorrupt("manifest_unreadable", path.name) from exc
            if "authority_seq" in manifest:
                rows.append((int(manifest["authority_seq"]), path, manifest))
        rows.sort(key=lambda item: item[0])
        previous = None
        for expected, (seq, path, manifest) in enumerate(rows, 1):
            if seq != expected or manifest.get("prev_manifest_sha256") != previous:
                raise AuthorityCorrupt("authority_chain", "seq=%r" % seq)
            entries = [entry for entry in manifest.get("entries", [])
                       if isinstance(entry, dict)
                       and str(entry.get("path", "")).startswith("events/")]
            if len(entries) != 1:
                raise AuthorityCorrupt("command_event_entry", "seq=%d" % seq)
            rel = Path(entries[0]["path"])
            if rel.is_absolute() or ".." in rel.parts or rel.parts[0] != "events":
                raise AuthorityCorrupt("command_event_path", "seq=%d" % seq)
            try:
                raw = (self.root / rel).read_bytes()
                batch = json.loads(raw.decode("utf-8"))
            except (OSError, ValueError, UnicodeError) as exc:
                raise AuthorityCorrupt("command_event_unreadable", "seq=%d" % seq) from exc
            if (_sha(raw) != entries[0].get("sha256") or
                    batch.get("authority_seq") != seq or
                    batch.get("command_id") != manifest.get("command_id")):
                raise AuthorityCorrupt("command_event_hash", "seq=%d" % seq)
            previous = self._manifest_hash(path)
        if len(rows) != len(self._batches) or previous != self._head_hash:
            raise AuthorityCorrupt("authority_runtime_mismatch")
        return True

    def head(self):
        return {
            "seq": len(self._batches),
            "manifest_sha256": self._head_hash,
            "committed_at": (self._batches[-1]["occurred_at"] if self._batches else None),
        }

    def aggregate_ids(self):
        return sorted(self._states)

    def state(self, aggregate_id):
        return copy.deepcopy(self._states.get(aggregate_id) or initial_state(aggregate_id))

    def batches(self, after_seq=0):
        return [copy.deepcopy(row) for row in self._batches
                if row["authority_seq"] > int(after_seq)]

    def command(self, command_id):
        return next((copy.deepcopy(row) for row in self._batches
                     if row["command_id"] == command_id), None)

    def idempotent(self, actor, idempotency_key):
        """按 (principal, tenant, key) 查已提交批次；不存在的 key 返回 None。"""
        if not isinstance(actor, dict) or not isinstance(idempotency_key, str):
            return None
        key = (actor.get("principal_id"), actor.get("tenant_id"),
               idempotency_key.strip())
        return copy.deepcopy(self._idempotency.get(key))

    @staticmethod
    def request_hash(*, aggregate_id, command, actor, expected_version, payload):
        body = {
            "aggregate_id": aggregate_id, "command": command,
            "actor": actor, "expected_version": expected_version,
            "payload": payload or {},
        }
        return _sha(_canonical(body).encode("utf-8"))

    def execute(self, *, aggregate_id, command, actor, expected_version,
                payload, idempotency_key, now=None):
        with self._lock:
            return self._execute_locked(
                aggregate_id=aggregate_id, command=command, actor=actor,
                expected_version=expected_version, payload=payload,
                idempotency_key=idempotency_key, now=now)

    def _execute_locked(self, *, aggregate_id, command, actor, expected_version,
                        payload, idempotency_key, now=None):
        if self.lease is None:
            raise AuthorityConflict("writer_lease_missing", "生产写必须持有 writer lease")
        self.lease.assert_owner()
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise AuthorityConflict("idempotency_key_missing", "Idempotency-Key 必填")
        if not isinstance(actor, dict):
            raise AuthorityConflict("actor_missing", "actor 必须是对象")
        principal = actor.get("principal_id")
        tenant = actor.get("tenant_id")
        if not all(isinstance(v, str) and v.strip() for v in (principal, tenant)):
            raise AuthorityConflict("actor_missing", "principal_id/tenant_id 必填")
        actor = {"principal_id": principal.strip(), "tenant_id": tenant.strip()}
        payload = copy.deepcopy(payload or {})
        idem = (actor["principal_id"], actor["tenant_id"], idempotency_key.strip())
        existing = self._idempotency.get(idem)
        # claim 的 HTTP 请求体没有 version：首次在 writer lock 内绑定当前版本；
        # 重试必须沿用原批次的 expected_version 算 hash，不能拿已经前进的版本
        # 把同一个请求误判成 idempotency_conflict。
        if expected_version is None:
            effective_version = (existing["expected_version"] if existing is not None
                                 else self.state(aggregate_id)["version"])
        else:
            effective_version = int(expected_version)
        request_sha = self.request_hash(
            aggregate_id=aggregate_id, command=command, actor=actor,
            expected_version=effective_version, payload=payload)
        if existing is not None:
            if existing["request_sha256"] != request_sha:
                raise AuthorityConflict("idempotency_conflict",
                                        "同 key 已绑定不同 actor/path/body/version")
            return {"replayed": True, "batch": copy.deepcopy(existing)}

        old = self.state(aggregate_id)
        timestamp = self.clock() if now is None else float(now)
        new_state, events, result = reduce_command(
            old, command, actor["principal_id"], effective_version,
            {**payload, "case_id": aggregate_id}, now=timestamp)
        seq = len(self._batches) + 1
        command_id = "cmd-%012d" % seq
        reconcile_token = secrets.token_urlsafe(24)
        agg_type = aggregate_type_for(aggregate_id)
        batch = {
            "schema_version": "business-command-batch/v1",
            "command_id": command_id,
            "authority_seq": seq,
            "prev_manifest_sha256": self._head_hash,
            # ★ T-314b：不是硬编码 review_case。判定只有 aggregate_type_for 一份。
            "aggregate_type": agg_type,
            "aggregate_id": aggregate_id,
            "expected_version": effective_version,
            "result_version": int(new_state["version"]),
            "actor": actor,
            "command": command,
            "occurred_at": _iso(timestamp),
            "idempotency_key": idempotency_key.strip(),
            "request_sha256": request_sha,
            "events": events,
            "result": result,
            "reconcile_token": reconcile_token,
        }
        data = (_canonical(batch) + "\n").encode("utf-8")
        manifest = self.artifacts.commit(
            command_id,
            [{"kind": "events", "key": command_id, "data": data}],
            manifest_extra={
                "authority_seq": seq,
                "prev_manifest_sha256": self._head_hash,
                "command_id": command_id,
                "aggregate_type": agg_type,
                "aggregate_id": aggregate_id,
            },
        )
        manifest_path = Path(self.artifacts.manifests) / (command_id + ".json")
        manifest_sha = self._manifest_hash(manifest_path)
        self._index(batch, manifest_sha256=manifest_sha, replay=False)
        self._head_hash = manifest_sha
        return {"replayed": False, "batch": copy.deepcopy(self._batches[-1]),
                "manifest": manifest}
