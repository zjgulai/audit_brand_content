#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""权威命令提交 + SQLite 投影协调；权威成功不因投影失败回滚。"""
from __future__ import annotations

import copy
import threading

from base.business_event_store import AuthorityConflict
from base.projector import Projector


class ReviewCommandService:
    def __init__(self, authority, projection):
        self.authority = authority
        self.projection = projection
        # WriterLease 只约束跨进程写者；FastAPI 同步 handler 会在线程池并发。
        # 权威提交 + 按序追投影必须在本进程再单飞，避免 seq2 先于 seq1 apply。
        self._lock = threading.RLock()

    def status(self):
        with self._lock:
            self.authority.verify_integrity()
            return self.projection.status(self.authority.head())

    def execute(self, **command):
        with self._lock:
            committed = self.authority.execute(**command)
            return self._respond(committed["batch"], committed["replayed"])

    def _respond(self, batch, replayed):
        """权威已提交后的统一响应：投影追平成功 200，失败 202（不回滚权威）。"""
        try:
            # 不只 apply 当前批：前一次临时失败后，同 key 重试也应补齐所有缺批。
            Projector(self.authority, self.projection).catch_up()
        except Exception as exc:
            code = getattr(exc, "code", type(exc).__name__)
            try:
                self.projection.mark_error(code)
            except Exception:
                pass
            return {
                "http_status": 202,
                "projection_lag": True,
                "authority_snapshot": {
                    "command_id": batch["command_id"],
                    "authority_seq": batch["authority_seq"],
                    "aggregate_id": batch["aggregate_id"],
                    "result_version": batch["result_version"],
                    "manifest_sha256": batch["manifest_sha256"],
                },
                "reconcile_token": batch["reconcile_token"],
                "result": copy.deepcopy(batch["result"]),
                "replayed": replayed,
                "error_code": "projection_lag",
            }
        return {
            "http_status": 200,
            "projection_lag": False,
            "authority_snapshot": {
                "command_id": batch["command_id"],
                "authority_seq": batch["authority_seq"],
                "aggregate_id": batch["aggregate_id"],
                "result_version": batch["result_version"],
                "manifest_sha256": batch["manifest_sha256"],
            },
            "reconcile_token": batch["reconcile_token"],
            "result": copy.deepcopy(batch["result"]),
            "replayed": replayed,
        }

    def execute_submission(self, *, ingestor, submission, principal,
                           idempotency_key):
        """内容入库：先按输入哈希查幂等，命中直接回放；未命中才判定+提交。

        判定在 authority 提交之前同步完成；失败不会留下「有案件、无判定」的残件。
        整个过程在本进程锁内，避免并发同 key 时两个请求都判定、其中一个被
        authority 的 payload 哈希误判成 idempotency_conflict。
        """
        with self._lock:
            if not isinstance(idempotency_key, str) or not idempotency_key.strip():
                raise AuthorityConflict("idempotency_key_missing", "Idempotency-Key 必填")
            principal_id = (principal or {}).get("id")
            tenant = (principal or {}).get("tenant")
            if not all(isinstance(v, str) and v.strip()
                       for v in (principal_id, tenant)):
                raise AuthorityConflict("actor_missing", "principal id/tenant 必填")
            actor = {"principal_id": principal_id.strip(), "tenant_id": tenant.strip()}
            incoming = ingestor.submission_hash(submission, principal=principal)
            existing = self.authority.idempotent(actor, idempotency_key)
            if existing is not None:
                events = existing.get("events") or [{}]
                state = events[0].get("state") if isinstance(events[0], dict) else {}
                if (state or {}).get("submission_hash") != incoming:
                    raise AuthorityConflict(
                        "idempotency_conflict",
                        "同 key 已绑定不同的 submission")
                return self._respond(existing, True)
            prepared = ingestor.prepare(submission, principal=principal)
            committed = self.authority.execute(
                aggregate_id=prepared["case_id"], command="ingest_submission",
                actor=actor, expected_version=0, payload=prepared["payload"],
                idempotency_key=idempotency_key)
            return self._respond(committed["batch"], committed["replayed"])

    def reconcile(self):
        with self._lock:
            Projector(self.authority, self.projection).catch_up()
            return self.projection.status(self.authority.head())

    def expire_if_due(self, aggregate_id, *, now=None,
                      actor_id="lease-sweeper"):
        with self._lock:
            state = self.authority.state(aggregate_id)
            lease_expires = state.get("lease_expires")
            if state.get("status") != "claimed" or lease_expires is None:
                return None
            import time
            current = time.time() if now is None else float(now)
            if current <= float(lease_expires):
                return None
            return self.execute(
                aggregate_id=aggregate_id, command="expire_lease",
                actor={"principal_id": actor_id, "tenant_id": "system"},
                expected_version=state["version"], payload={},
                idempotency_key="lease-expire:%s:%s" %
                (aggregate_id, state["version"]), now=current)

    def read_your_write(self, reconcile_token, *, aggregate_id=None,
                        principal_id=None, tenant_id=None):
        if not isinstance(reconcile_token, str) or not reconcile_token:
            return None
        for batch in self.authority.batches():
            if batch.get("reconcile_token") != reconcile_token:
                continue
            actor = batch.get("actor") or {}
            if aggregate_id is not None and batch.get("aggregate_id") != aggregate_id:
                return None
            if principal_id is not None and actor.get("principal_id") != principal_id:
                return None
            if tenant_id is not None and actor.get("tenant_id") != tenant_id:
                return None
            return {
                "authority_snapshot": {
                    "command_id": batch["command_id"],
                    "authority_seq": batch["authority_seq"],
                    "aggregate_id": batch["aggregate_id"],
                    "result_version": batch["result_version"],
                    "manifest_sha256": batch["manifest_sha256"],
                },
                "result": copy.deepcopy(batch["result"]),
            }
        return None
