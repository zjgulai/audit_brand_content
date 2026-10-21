#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 BusinessEventStore 的已提交 manifest 构建/追平 SQLite 投影。"""
from __future__ import annotations

from base.business_event_store import AuthorityCorrupt
from base.projection_store import ProjectionStore


class Projector:
    def __init__(self, authority, projection: ProjectionStore):
        self.authority = authority
        self.projection = projection

    def catch_up(self):
        applied = int(self.projection.watermark()["applied_seq"])
        results = []
        for batch in self.authority.batches(after_seq=applied):
            try:
                results.append(self.projection.apply_batch(batch))
            except Exception as exc:
                self.projection.mark_error(getattr(exc, "code", type(exc).__name__))
                raise
        return results

    def rebuild(self):
        # authority 构造时已校验序号、manifest链和事件sha；任何坏链先于清空投影抛错。
        self.authority.head()
        self.projection.reset()
        for batch in self.authority.batches():
            self.projection.apply_batch(batch)
        self.projection.mark_rebuilt()
        status = self.projection.status(self.authority.head())
        if status["status"] != "fresh":
            raise AuthorityCorrupt("projection_rebuild", status["status"])
        return status
