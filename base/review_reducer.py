#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""复核台账纯 reducer：命令 + 旧状态 → 新状态 + 事件 + 返回值。

不读写文件、不持有锁、不发通知。生产权威写入由 BusinessEventStore 统一提交；
现有 ReviewsLedger 继续供开发装配和旧验证器使用。
"""
from __future__ import annotations

import copy
import hashlib
import json
import time

from base.reviews_ledger import (
    LEASE_SECONDS,
    LedgerConflict,
    LedgerNotFound,
    LedgerValidation,
)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _iso(now):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(now)))


def _nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise LedgerValidation("bad_" + name, "%s 必须是非空字符串" % name)
    return value.strip()


def initial_state(case_id):
    return {
        "case_id": _nonempty(case_id, "case_id"),
        "status": "unassigned",
        "assignee": None,
        "version": 0,
        "claimed_at": None,
        "last_activity": None,
        "lease_expires": None,
        "released_at": None,
        "released_draft_id": None,
        "draft_seq": 0,
        "primary_draft_id": None,
        "drafts": [],
        "fragment_references": [],
        "formal_reviews": [],
    }


def public_case(state):
    return {
        key: copy.deepcopy(state.get(key))
        for key in (
            "case_id", "status", "assignee", "version", "claimed_at",
            "last_activity", "lease_expires", "released_at",
            "released_draft_id", "primary_draft_id",
        )
    }


def _draft(state, draft_id):
    return next((d for d in state["drafts"] if d["draft_id"] == draft_id), None)


def _require_claim(state, actor, expected_version, now):
    if state["status"] == "claimed" and state["lease_expires"] is not None:
        if float(now) > float(state["lease_expires"]):
            raise LedgerConflict("lease_expired", "领取 lease 已过期")
    if state["status"] != "claimed" or state["assignee"] != actor:
        raise LedgerConflict("not_assignee", "当前不是该案的 assignee")
    if state["version"] != expected_version:
        raise LedgerConflict(
            "version_conflict",
            "期望版本 %r，实际 %r" % (expected_version, state["version"]),
        )


def _new_draft(state, actor, now, content, *, kind, derived_from=None):
    seq = state["draft_seq"] + 1
    content_hash = _hash(content)
    draft_id = "draft-" + _hash({
        "case_id": state["case_id"], "seq": seq, "author": actor,
        "content_hash": content_hash, "kind": kind,
        "derived_from": derived_from,
    })[:16]
    draft = {
        "case_id": state["case_id"], "draft_id": draft_id,
        "snapshot_seq": seq, "snapshot_at": _iso(now),
        "content_hash": content_hash, "author": actor,
        "derived_from": derived_from, "snapshot_kind": kind,
        **copy.deepcopy(content),
    }
    if kind == "adopt":
        draft["adopted_at"] = _iso(now)
    state["draft_seq"] = seq
    state["drafts"].append(draft)
    state["primary_draft_id"] = draft_id
    return draft


def _event(command, state, actor, now, detail=None):
    return {
        "type": "review.%s" % command,
        "aggregate_type": "review_case",
        "aggregate_id": state["case_id"],
        "version": state["version"],
        "actor": actor,
        "occurred_at": _iso(now),
        "detail": copy.deepcopy(detail or {}),
        "state": copy.deepcopy(state),
    }


def reduce_command(old_state, command, actor, expected_version, payload=None,
                   *, now=None, lease_seconds=LEASE_SECONDS):
    """返回 ``(new_state, [event], result)``；拒绝时不改变入参。"""
    state = copy.deepcopy(old_state or initial_state((payload or {}).get("case_id")))
    actor = _nonempty(actor, "actor")
    payload = copy.deepcopy(payload or {})
    now = time.time() if now is None else float(now)
    expected_version = int(expected_version)

    if state["version"] != expected_version:
        raise LedgerConflict(
            "version_conflict",
            "期望版本 %r，实际 %r" % (expected_version, state["version"]),
        )

    detail = {}
    if command == "claim":
        if state["status"] == "claimed":
            raise LedgerConflict("already_claimed", "案件已被领取")
        if state["status"] == "closed":
            raise LedgerConflict("case_closed", "案件已提交，不能重新领取")
        state.update({
            "status": "claimed", "assignee": actor,
            "claimed_at": _iso(now), "last_activity": _iso(now),
            "lease_expires": now + int(lease_seconds),
        })
    elif command == "unclaim":
        _require_claim(state, actor, expected_version, now)
        if not state["drafts"]:
            content = {"form": {}, "notes": "", "evidence_selections": [],
                       "references": []}
            _new_draft(state, actor, now, content, kind="lease_release")
        state.update({
            "status": "released", "assignee": None,
            "released_at": _iso(now),
            "released_draft_id": state["primary_draft_id"],
            "lease_expires": None,
        })
    elif command == "reassign":
        _require_claim(state, actor, expected_version, now)
        new_assignee = _nonempty(payload.get("assignee"), "assignee")
        state["assignee"] = new_assignee
        state["last_activity"] = _iso(now)
        detail["new_assignee"] = new_assignee
    elif command == "heartbeat":
        _require_claim(state, actor, expected_version, now)
        state["last_activity"] = _iso(now)
        state["lease_expires"] = now + int(lease_seconds)
    elif command == "save_draft":
        _require_claim(state, actor, expected_version, now)
        form = payload.get("form", {})
        notes = payload.get("notes", "")
        evidence = payload.get("evidence_selections", [])
        references = payload.get("references", [])
        if not isinstance(form, dict):
            raise LedgerValidation("bad_form", "form 必须是 dict")
        if not isinstance(notes, str):
            raise LedgerValidation("bad_notes", "notes 必须是字符串")
        if not isinstance(evidence, list) or not isinstance(references, list):
            raise LedgerValidation("bad_draft", "evidence_selections/references 必须是 list")
        draft = _new_draft(
            state, actor, now,
            {"form": form, "notes": notes,
             "evidence_selections": evidence, "references": references},
            kind="autosave",
        )
        detail["draft_id"] = draft["draft_id"]
    elif command == "adopt_draft":
        _require_claim(state, actor, expected_version, now)
        source_id = _nonempty(payload.get("source_draft_id"), "source_draft_id")
        source = _draft(state, source_id)
        if source is None:
            raise LedgerNotFound("draft_not_found", "源 draft 不存在")
        if source_id != state["primary_draft_id"]:
            raise LedgerConflict("not_primary", "只能 adopt primary draft")
        draft = _new_draft(
            state, actor, now,
            {"form": source["form"], "notes": source["notes"],
             "evidence_selections": source["evidence_selections"],
             "references": source["references"]},
            kind="adopt", derived_from=source_id,
        )
        detail.update({"draft_id": draft["draft_id"], "derived_from": source_id})
    elif command == "reference_fragment":
        _require_claim(state, actor, expected_version, now)
        source_id = _nonempty(payload.get("source_draft_id"), "source_draft_id")
        field_path = _nonempty(payload.get("field_path"), "field_path")
        fragment = payload.get("fragment")
        if fragment is None or (isinstance(fragment, str) and not fragment.strip()):
            raise LedgerValidation("bad_fragment", "fragment 不能为空")
        source = _draft(state, source_id)
        if source is None:
            raise LedgerNotFound("draft_not_found", "源 draft 不存在")
        if source_id == state["primary_draft_id"]:
            raise LedgerConflict("primary_requires_adopt", "primary draft 必须显式 adopt")
        ref = {
            "case_id": state["case_id"], "source_draft_id": source_id,
            "field_path": field_path, "fragment": fragment,
            "author": actor, "at": _iso(now),
        }
        state["fragment_references"].append(ref)
        detail["reference"] = ref
    elif command == "submit_review":
        _require_claim(state, actor, expected_version, now)
        conclusion = payload.get("conclusion")
        if not isinstance(conclusion, dict):
            raise LedgerValidation("bad_conclusion", "conclusion 必须是 dict")
        if not isinstance(conclusion.get("review_notes"), str) or not conclusion["review_notes"].strip():
            raise LedgerValidation("bad_conclusion", "review_notes 必须是非空字符串")
        formal_id = "formal-" + _hash({
            "case_id": state["case_id"], "actor": actor,
            "version": state["version"] + 1, "conclusion": conclusion,
        })[:16]
        formal = {
            "formal_id": formal_id, "case_id": state["case_id"],
            "author": actor, "submitted_at": _iso(now),
            "from_draft_id": state["primary_draft_id"],
            "conclusion": conclusion,
        }
        state["formal_reviews"].append(formal)
        state["status"] = "closed"
        state["lease_expires"] = None
        detail["formal_id"] = formal_id
    elif command == "expire_lease":
        if state["status"] != "claimed" or state["lease_expires"] is None:
            raise LedgerConflict("not_claimed", "没有可过期的 lease")
        if now <= float(state["lease_expires"]):
            raise LedgerConflict("lease_active", "lease 尚未过期")
        if not state["drafts"]:
            content = {"form": {}, "notes": "", "evidence_selections": [],
                       "references": []}
            _new_draft(state, state["assignee"], now, content,
                       kind="lease_release")
        detail["released_assignee"] = state["assignee"]
        state.update({
            "status": "released", "assignee": None,
            "released_at": _iso(now),
            "released_draft_id": state["primary_draft_id"],
            "lease_expires": None,
        })
    else:
        raise LedgerValidation("bad_command", "未知命令 %r" % command)

    state["version"] += 1
    event = _event(command, state, actor, now, detail)
    result = public_case(state)
    if "draft_id" in detail:
        result["draft"] = copy.deepcopy(_draft(state, detail["draft_id"]))
    if "formal_id" in detail:
        result["formal"] = copy.deepcopy(state["formal_reviews"][-1])
    if "reference" in detail:
        result["reference"] = copy.deepcopy(detail["reference"])
    return state, [event], result


def apply_event(_old_state, event):
    if not isinstance(event, dict) or not isinstance(event.get("state"), dict):
        raise LedgerValidation("bad_event", "review 事件缺 state 快照")
    return copy.deepcopy(event["state"])
