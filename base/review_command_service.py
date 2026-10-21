#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""权威命令提交 + SQLite 投影协调；权威成功不因投影失败回滚。"""
from __future__ import annotations

import copy
import threading

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
            batch = committed["batch"]
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
                    "replayed": committed["replayed"],
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
                "replayed": committed["replayed"],
            }

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
