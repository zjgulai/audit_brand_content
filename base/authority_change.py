#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""authority_change.py —— 权威源变更 → 重审入队（RL-15 / 行 103）

权威源：规则、控制点、路由。**Web 只读，权威源在别处**；当权威源同步到
新版本时，必须产生一个可数的变更事件，并为每个受影响案件入队一次重审。

本模块只做三件事：

  1. 校验变更事件（kind / old_version / new_version）；
  2. 生成稳定的 `event_key`，同一事件重复送达只接受一次（幂等）；
  3. 为每个 case 生成 `trigger=authority_change` 的 queued job，交给可注入的
     `enqueue(job)` —— 生产调用方接真实队列，测试可接内存列表。

它不拉取权威源、不判规则内容、不执行重审。事件源（同步器）负责在检测到
版本变化后调用 `on_authority_changed()`。
"""
from __future__ import annotations

import datetime
import hashlib
import json

AUTHORITY_KINDS = ("rules", "control_points", "routing")


def _canonical(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _iso(now):
    if now is not None:
        return now
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def on_authority_changed(event, *, case_ids, enqueue=None, seen=None, now=None):
    """处理一次权威源变更事件；返回 {accepted, event_key, jobs}。

    `seen` 是调用方持久化的已见事件集合（set）。传入它时，同一
    (kind, old_version, new_version) 第二次送达返回 accepted=False 且不再入队。
    """
    if not isinstance(event, dict):
        raise ValueError("event 必须是对象")
    kind = event.get("kind")
    old_version = event.get("old_version")
    new_version = event.get("new_version")
    if kind not in AUTHORITY_KINDS:
        raise ValueError("kind 必须是 %r，收到 %r" % (AUTHORITY_KINDS, kind))
    for name, value in (("old_version", old_version),
                        ("new_version", new_version)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("%s 必须是非空字符串" % name)
    if old_version == new_version:
        raise ValueError("old_version 与 new_version 相同，不是一次变更")
    if not isinstance(case_ids, (list, tuple)):
        raise ValueError("case_ids 必须是数组")
    if any(not isinstance(cid, str) or not cid for cid in case_ids):
        raise ValueError("case_ids 的每一项都必须是非空字符串")

    event_key = "auth-" + _sha(_canonical({
        "kind": kind, "old_version": old_version,
        "new_version": new_version,
    }))[:16]
    if seen is not None:
        if not hasattr(seen, "add"):
            raise ValueError("seen 必须是可 add 的集合")
        if event_key in seen:
            return {"accepted": False, "reason": "duplicate_event",
                    "event_key": event_key, "jobs": []}
        seen.add(event_key)

    created_at = _iso(now)
    jobs = []
    for cid in case_ids:
        job = {
            "job_id": "job-" + _sha(_canonical({
                "case_id": cid, "event_key": event_key,
            }))[:16],
            "case_id": cid,
            "state": "queued",
            "trigger": "authority_change",
            "authority_kind": kind,
            "old_version": old_version,
            "new_version": new_version,
            "created_at": created_at,
        }
        jobs.append(job)
        if enqueue is not None:
            enqueue(job)
    return {"accepted": True, "event_key": event_key, "jobs": jobs}
