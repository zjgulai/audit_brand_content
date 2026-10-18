#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/disposition_router.py —— 唯一处置路由（T1-10）

## 职责边界（技术方案 §2 #15）

输入 decision_table 的输出（`state` / `layer` / `obligations`），补齐：

    owner / finalizer / can_finalize / release_status / appeal_channel / due_at

  - **不重算 state / layer**：输出原样带回输入值；只做一致性守卫
    （state↔layer 映射、冲突必须 DP4）。
  - **不重生成 obligations**：原样透传，不增不删不改顺序。
  - **不发送、不写回执、不判 finding**：只产出处置路由字段。

## 五档与层

| state | 允许 layer | owner / finalizer |
|---|---|---|
| BLOCK | DP2 | 机器（工具预审）|
| REVIEW | DP3 或 DP4 | 内容审核员 / 法务 |
| 未审查 | DP0 | 投放侧 |
| 待自决 | DP1 | 文案提交人 |
| PASS | DP1 | 文案提交人 |

冲突样本（`any_authority_conflict` / `rule_conflict` / `max_sev_authority=conflict`）
**必须落 DP4**；落 DP3 直接拒。

## 释放状态

五档一律 `release_status="待放行"`。本模块没有、也不允许有
「标签 → 发布状态」的直连路径；输入里带的释放状态会被覆盖。

## 案件号与申诉

`case_id = receipt_id`；`appeal_channel` 必定包含该案件号。
"""
from __future__ import annotations

import datetime
import json
import os
import re

DEFAULT_ROUTING = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "research", "governance", "routing-v1.json")

FIVE_STATES = ("BLOCK", "REVIEW", "未审查", "待自决", "PASS")
LAYERS = ("DP0", "DP1", "DP2", "DP3", "DP4")

# state → 允许的层（比"重算"窄：只用来拒绝不一致，不用于回填）
LAYER_RULES = {
    "BLOCK": ("DP2",),
    "REVIEW": ("DP3", "DP4"),
    "未审查": ("DP0",),
    "待自决": ("DP1",),
    "PASS": ("DP1",),
}

# 层 → (owner, finalizer)；can_finalize 一律 True（"这一层由这一层结"），
# 但任何一层的 can_finalize 都不等于"可以放行"。
ROLE = {
    "DP0": ("投放侧", "投放侧"),
    "DP1": ("文案提交人", "文案提交人"),
    "DP2": ("机器（工具预审）", "机器（工具预审）"),
    "DP3": ("内容审核员", "内容审核员"),
    "DP4": ("法务", "法务"),
}

DEFAULT_DUE = "2 个工作日"
DEFAULT_ESCALATION = "项目统筹"


class InvalidDecision(ValueError):
    pass


def _add_business_days(dt, n):
    d = dt
    added = 0
    while added < n:
        d = d + datetime.timedelta(days=1)
        if d.weekday() < 5:
            added += 1
    return d


def _parse_now(now):
    if now is None:
        return datetime.datetime.now(datetime.timezone.utc)
    s = now.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def _iso_z(dt):
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _due_days(text):
    m = re.search(r"(\d+)\s*个工作日", text or "")
    return int(m.group(1)) if m else 2


class DispositionRouter(object):
    def __init__(self, routing_path=None):
        self.path = os.path.abspath(routing_path or DEFAULT_ROUTING)
        with open(self.path, "rb") as f:
            data = json.loads(f.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("routing 表顶层必须是对象")
        self.routing_version = data.get("routing_version")
        if not isinstance(self.routing_version, str) or not self.routing_version:
            raise ValueError("routing_version 缺失")
        self.routes = {}
        for row in data.get("routes") or []:
            if isinstance(row, dict) and isinstance(row.get("control_code"), str):
                self.routes[row["control_code"]] = row

    def route(self, decision, receipt_id, control_code=None, now=None):
        if not isinstance(receipt_id, str) or not receipt_id:
            raise InvalidDecision("receipt_id 必须是非空字符串")
        if not isinstance(decision, dict):
            raise InvalidDecision("decision 必须是 dict")
        if decision.get("run_state") != "OK":
            raise InvalidDecision("只路由 run_state=OK 的判定输出")
        state = decision.get("state")
        layer = decision.get("layer")
        if state not in FIVE_STATES:
            raise InvalidDecision("未知 state：%r" % (state,))
        if layer not in LAYERS:
            raise InvalidDecision("未知 layer：%r" % (layer,))
        obligations = decision.get("obligations")
        if not isinstance(obligations, list):
            raise InvalidDecision("obligations 必须是 list")

        if layer not in LAYER_RULES[state]:
            raise InvalidDecision("state=%s 不允许落 %s（允许：%s）"
                                  % (state, layer, "/".join(LAYER_RULES[state])))

        conflict = (decision.get("any_authority_conflict") is True
                    or decision.get("rule_conflict") is True
                    or decision.get("max_sev_authority") == "conflict")
        if conflict and layer != "DP4":
            raise InvalidDecision("冲突样本必须落 DP4，收到 %s" % layer)

        owner, finalizer = ROLE[layer]
        if control_code is not None:
            row = self.routes.get(control_code)
            if row is None:
                raise InvalidDecision("未知 control_code：%r" % (control_code,))
            # 只有路由表那一行与本次处置层一致时才采用它的 owner；
            # 冲突升级到 DP4 时，仍由 DP4 的角色接手。
            if row.get("layer") == layer and isinstance(row.get("owner"), str) and row["owner"]:
                owner = row["owner"]
            due_text = row.get("due") or DEFAULT_DUE
            escalation = row.get("escalation") or DEFAULT_ESCALATION
        else:
            due_text = DEFAULT_DUE
            escalation = DEFAULT_ESCALATION

        if not isinstance(owner, str) or not owner:
            raise InvalidDecision("owner 为空：不允许无负责人的路由")
        if not isinstance(finalizer, str) or not finalizer:
            raise InvalidDecision("finalizer 为空")

        start = _parse_now(now)
        due_at = _iso_z(_add_business_days(start, _due_days(due_text)))

        return {
            "state": state,
            "layer": layer,
            "obligations": list(obligations),
            "owner": owner,
            "finalizer": finalizer,
            "can_finalize": True,
            "release_status": "待放行",
            "case_id": receipt_id,
            "receipt_id": receipt_id,
            "appeal_channel": "申诉通道：案件号 %s" % receipt_id,
            "due_at": due_at,
            "escalation": escalation,
            "routing_version": self.routing_version,
        }
