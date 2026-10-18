#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/evidence_sync.py —— 依据同步：authority_state / rule_conflict（T1-06）

## 职责边界（技术方案 §2 #9 / §1bis.1）

在判定步内作为**具名子阶段** enrich `DraftFinding`：

  - 对每条 `status=confirmed` 的 finding 计算 `authority_state`；
  - 钉住 `rule_snapshot` / `kb_snapshot`；
  - 产出 `ValidatedFinding` 所需的字段（同一个 finding 的后续版本，
    **不新增 finding、不分配 finding_id、不判 state/layer、不写回执**）。

## ref 级六态 → finding 级四值

| ref 级 | finding 级 | 含义 |
|---|---|---|
| `ok` | `ok` | 依据可取、未过期、无冲突 |
| `missing` | `missing` | 查不到依据 |
| `expired` | `expired` | 依据已过期 |
| `conflict` | `conflict` | 多条依据互相冲突 |
| `untested` | `missing` | **没查成**（KB 不可达 / 查询异常）—— 不许当 ok |
| `disabled` | `missing` | 停用依据不能支撑结论 |

聚合顺序：**conflict > expired > missing > ok**（missing 与 expired 的先后见
技术方案 §残留②，本实现取 conflict > expired > missing；不影响链 6/8/10）。
`authority_ref` 为空 / null → `missing`。

## 三分法（Playbook §3.3.6）

| authority_state | route | 机结资格 |
|---|---|---|
| `missing` | `DP3` 内容审核员 | ❌ |
| `expired` | `DP3` 内容审核员 | ❌ |
| `conflict` | `DP4` 法务 | ❌ |
| `ok` | 不转人 | ✅（且 `rule_conflict=false`） |

**不得 fail-open**：任何未知状态、查询异常、坏 ref 都压成 `missing`，
`may_block()` 对缺失/过期/冲突/字段不全一律返回 `False`。
"""
from __future__ import annotations

import hashlib
import json

REF_STATES = ("ok", "missing", "expired", "conflict", "untested", "disabled")
AUTHORITY_STATES = ("ok", "missing", "expired", "conflict")
STATUSES = ("confirmed", "candidate", "rejected", "superseded")

_RANK = {"ok": 0, "missing": 1, "expired": 2, "conflict": 3}


class EvidenceSyncError(ValueError):
    pass


class InvalidSnapshot(EvidenceSyncError):
    pass


def _state_of(x):
    """ref 查询结果可以是 str 或 {'state': ...}。"""
    if isinstance(x, str):
        return x, None
    if isinstance(x, dict):
        return x.get("state"), x.get("reason")
    return None, None


def collapse_ref_state(state):
    """ref 级六态 → finding 级四值；未知状态一律压成 missing（fail-closed）。"""
    if state == "ok":
        return "ok"
    if state == "expired":
        return "expired"
    if state == "conflict":
        return "conflict"
    # missing / untested / disabled / 未知 / None
    return "missing"


def aggregate_authority(states):
    """把一批 ref 状态（字符串或 {'state':...}）聚合为 finding 级四值。"""
    worst = "ok"
    any_state = False
    for item in states or ():
        raw, _reason = _state_of(item)
        collapsed = collapse_ref_state(raw)
        any_state = True
        if _RANK[collapsed] > _RANK[worst]:
            worst = collapsed
    if not any_state:
        return "missing"
    return worst


def _ref_id(ref):
    if not isinstance(ref, dict):
        return None
    for k in ("ref_id", "entry_id", "article", "url"):
        v = ref.get(k)
        if isinstance(v, str) and v:
            return v
    try:
        blob = json.dumps(ref, ensure_ascii=False, sort_keys=True).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return "ref_" + hashlib.sha256(blob).hexdigest()[:16]


def _query_ref(query, ref):
    """查一条 ref；任何异常/未知状态都落 untested（→ missing）。"""
    rid = _ref_id(ref)
    if rid is None:
        return {"ref_id": None, "state": "untested", "collapsed": "missing",
                "reason": "bad_ref"}
    try:
        result = query(ref)
    except Exception as e:  # noqa: BLE001
        return {"ref_id": rid, "state": "untested", "collapsed": "missing",
                "reason": "kb_unreachable:%s" % (type(e).__name__,)}
    raw, reason = _state_of(result)
    if raw not in REF_STATES:
        return {"ref_id": rid, "state": "untested", "collapsed": "missing",
                "reason": "unknown_state:%r" % (raw,)}
    return {"ref_id": rid, "state": raw, "collapsed": collapse_ref_state(raw),
            "reason": reason}


def _aggregate_reason(details):
    for d in details:
        if d["state"] == "conflict":
            return "ref_conflict"
    for d in details:
        if d["state"] == "expired":
            return "ref_expired"
    for d in details:
        if d["collapsed"] == "missing":
            return d.get("reason") or "missing"
    if not details:
        return "no_authority_ref"
    return None


def _check_snapshots(rule_snapshot, kb_snapshot):
    if not isinstance(rule_snapshot, str) or not rule_snapshot:
        raise InvalidSnapshot("rule_snapshot 必须是非空字符串（实际 %r）" % (rule_snapshot,))
    if not isinstance(kb_snapshot, str) or not kb_snapshot:
        raise InvalidSnapshot("kb_snapshot 必须是非空字符串（实际 %r）" % (kb_snapshot,))


def enrich_finding(finding, query, rule_snapshot, kb_snapshot):
    """enrich 一条 finding；返回**新对象**，不修改输入。"""
    _check_snapshots(rule_snapshot, kb_snapshot)
    if not isinstance(finding, dict):
        raise EvidenceSyncError("finding 必须是 dict")
    status = finding.get("status")
    if status not in STATUSES:
        raise EvidenceSyncError("status=%r 不在 %s" % (status, list(STATUSES)))

    out = dict(finding)
    out["rule_snapshot"] = rule_snapshot
    out["kb_snapshot"] = kb_snapshot

    if status != "confirmed":
        # DF-2：candidate / rejected / superseded 不进判定链，不要求 authority_state。
        out["authority_state"] = None
        out["rule_conflict"] = False
        out["resolution_detail"] = None
        return out

    refs = finding.get("authority_ref")
    if refs is None:
        refs = []
    elif not isinstance(refs, list):
        # 坏输入不许 fail-open：当作「没有可用依据」。
        refs = []
    details = [_query_ref(query, r) for r in refs]
    state = aggregate_authority([d["state"] for d in details])
    out["authority_state"] = state
    out["rule_conflict"] = (state == "conflict")
    out["resolution_detail"] = {
        "refs": details,
        "reason": _aggregate_reason(details),
    }
    return out


def enrich_findings(findings, query, rule_snapshot, kb_snapshot):
    """批量 enrich；返回 finding 列表 + 路由 + 四态计数。"""
    _check_snapshots(rule_snapshot, kb_snapshot)
    if not isinstance(findings, list):
        raise EvidenceSyncError("findings 必须是 list")

    enriched = [enrich_finding(f, query, rule_snapshot, kb_snapshot) for f in findings]
    counts = {s: 0 for s in AUTHORITY_STATES}
    counts["not_computed"] = 0
    routing = []
    for e in enriched:
        st = e.get("authority_state")
        if st is None:
            counts["not_computed"] += 1
        else:
            counts[st] += 1
        routing.append({
            "finding_id": e.get("finding_id"),
            "authority_state": st,
            "route": route_for(st) if st is not None else None,
            "machine_final_eligible": may_block(e),
        })
    return {
        "findings": enriched,
        "routing": routing,
        "counts": counts,
        "rule_snapshot": rule_snapshot,
        "kb_snapshot": kb_snapshot,
    }


def route_for(authority_state):
    """三分法路由；未知状态按 DP3（fail-closed，不返回 None）。"""
    if authority_state == "ok":
        return None
    if authority_state == "conflict":
        return "DP4"
    # missing / expired / None / 未知
    return "DP3"


def may_block(validated):
    """机结资格：只有 authority_state=ok 且 rule_conflict 明确为 False 才为真。

    字段缺失 / 类型不对 / 任何不确定状态一律 False —— 这是防 fail-open 的执行点。
    """
    if not isinstance(validated, dict):
        return False
    if validated.get("authority_state") != "ok":
        return False
    return validated.get("rule_conflict") is False
