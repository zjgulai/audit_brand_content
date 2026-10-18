#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/reviews_ledger.py — T2-02a：人工复核台账 / 领取 / 草稿

边界：
- claim 原子独占（进程内锁 + 乐观版本）；lease 30 分钟无活动自动释放，
  释放前保证 draft 已保存；心跳延长 lease；版本冲突明确抛出。
- draft 是**不可变全字段快照**（form/notes/evidence selections/references），
  每次记录 snapshot_seq/snapshot_at/content_hash/author；autosave 只写台账，
  **不产 formal finding/decision/report**；只有 explicit submit 才进 formal。
- adopt：新 assignee 可只读前任 draft；显式 adopt 一份 primary 才复制成新 draft
  并记 derived_from；其他 draft 只能引用片段（source_draft_id+field_path+fragment），
  不自动 merge，原 draft 永不修改。
- 抽样台账：非 BLOCK 四层（PASS/待自决/REVIEW/未审查）分别抽样；BLOCK 全量复核；
  未复核完 → status=untested + reviewed_ratio，不许用部分样本算比率。
"""
from __future__ import annotations

import copy
import hashlib
import json
import threading
import time

LEASE_SECONDS = 30 * 60
NON_BLOCK_LAYERS = ("PASS", "待自决", "REVIEW", "未审查")
BLOCK_LAYER = "BLOCK"
ALL_LABELS = NON_BLOCK_LAYERS + (BLOCK_LAYER,)


class LedgerError(Exception):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


class LedgerConflict(LedgerError):
    pass


class LedgerNotFound(LedgerError):
    pass


class LedgerValidation(LedgerError):
    pass


def _iso(now):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(float(now)))


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _hash(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise LedgerValidation("bad_" + name, "%s 必须是非空字符串" % name)
    return value.strip()


class ReviewsLedger(object):
    def __init__(self, lease_seconds=LEASE_SECONDS, clock=None):
        self.lease_seconds = int(lease_seconds)
        self.clock = clock or time.time
        self._lock = threading.RLock()
        self._cases = {}
        self._drafts = {}
        self._events = []
        self._formal = []
        self._sampling = None

    # ───────────────────────── 基础 ─────────────────────────

    def _now(self, now):
        return self.clock() if now is None else float(now)

    def _case(self, case_id):
        case = self._cases.get(case_id)
        if case is None:
            case = {
                "case_id": case_id, "status": "unassigned", "assignee": None,
                "version": 0, "claimed_at": None, "last_activity": None,
                "lease_expires": None, "released_at": None,
                "released_draft_id": None, "draft_seq": 0,
                "primary_draft_id": None, "drafts": [],
                "fragment_references": [],
            }
            self._cases[case_id] = case
        return case

    def _case_view(self, case):
        return {
            "case_id": case["case_id"], "status": case["status"],
            "assignee": case["assignee"], "version": case["version"],
            "claimed_at": case["claimed_at"],
            "last_activity": case["last_activity"],
            "lease_expires": case["lease_expires"],
            "released_at": case["released_at"],
            "released_draft_id": case["released_draft_id"],
            "primary_draft_id": case["primary_draft_id"],
        }

    def _event(self, kind, case, actor, now, **extra):
        rec = {"kind": kind, "case_id": case["case_id"], "actor": actor,
               "at": _iso(now), "version": case["version"]}
        rec.update(extra)
        self._events.append(rec)

    def get_case(self, case_id):
        with self._lock:
            return self._case_view(self._case(case_id))

    def events(self):
        with self._lock:
            return copy.deepcopy(self._events)

    def formal_events(self):
        with self._lock:
            return copy.deepcopy(self._formal)

    # ───────────────────────── lease ─────────────────────────

    def _save_lease_draft(self, case, now):
        """释放前保证至少有一份 draft；已有快照则保留最新那份。"""
        if case["drafts"]:
            latest = case["drafts"][-1]
            return latest["draft_id"]
        seq = case["draft_seq"] + 1
        content = {"form": {}, "notes": "", "evidence_selections": [],
                   "references": []}
        content_hash = _hash(content)
        draft_id = "draft-" + _hash({
            "case_id": case["case_id"], "seq": seq,
            "author": case["assignee"], "content_hash": content_hash,
        })[:16]
        draft = {
            "case_id": case["case_id"], "draft_id": draft_id,
            "snapshot_seq": seq, "snapshot_at": _iso(now),
            "content_hash": content_hash, "author": case["assignee"],
            "derived_from": None, "snapshot_kind": "lease_release",
            "form": {}, "notes": "", "evidence_selections": [],
            "references": [],
        }
        case["draft_seq"] = seq
        case["drafts"].append(draft)
        self._drafts[draft_id] = draft
        return draft_id

    def _expire_locked(self, now):
        released = []
        for case in self._cases.values():
            if case["status"] != "claimed":
                continue
            if case["lease_expires"] is None or now < case["lease_expires"]:
                continue
            draft_id = self._save_lease_draft(case, now)
            case["status"] = "released"
            case["assignee"] = None
            case["released_at"] = _iso(now)
            case["released_draft_id"] = draft_id
            case["version"] += 1
            self._event("lease_released", case, None, now,
                        released_draft_id=draft_id)
            released.append(self._case_view(case))
        return released

    def expire(self, now=None):
        with self._lock:
            return self._expire_locked(self._now(now))

    # ───────────────────────── claim / heartbeat ─────────────────────────

    def claim(self, case_id, actor, now=None):
        actor = _nonempty(actor, "actor")
        now = self._now(now)
        with self._lock:
            self._expire_locked(now)
            case = self._case(case_id)
            if case["status"] == "claimed":
                raise LedgerConflict("already_claimed", "案件已被领取")
            if case["status"] == "closed":
                raise LedgerConflict("case_closed", "案件已提交，不能重新领取")
            case["status"] = "claimed"
            case["assignee"] = actor
            case["claimed_at"] = _iso(now)
            case["last_activity"] = _iso(now)
            case["lease_expires"] = now + self.lease_seconds
            case["version"] += 1
            self._event("claim", case, actor, now)
            return self._case_view(case)

    def unclaim(self, case_id, actor, version, now=None):
        """主动释放 claim；释放前保存 draft（与 lease 到期同一条路径）。"""
        actor = _nonempty(actor, "actor")
        now = self._now(now)
        with self._lock:
            self._expire_locked(now)
            case = self._case(case_id)
            self._require_claim(case, actor, version)
            draft_id = self._save_lease_draft(case, now)
            case["status"] = "released"
            case["assignee"] = None
            case["released_at"] = _iso(now)
            case["released_draft_id"] = draft_id
            case["version"] += 1
            self._event("unclaim", case, actor, now,
                        released_draft_id=draft_id)
            return self._case_view(case)

    def reassign(self, case_id, actor, version, new_assignee, now=None):
        """在 claim 存续期内改派；只换 assignee，lease 继续。"""
        actor = _nonempty(actor, "actor")
        new_assignee = _nonempty(new_assignee, "new_assignee")
        now = self._now(now)
        with self._lock:
            self._expire_locked(now)
            case = self._case(case_id)
            self._require_claim(case, actor, version)
            case["assignee"] = new_assignee
            case["last_activity"] = _iso(now)
            case["version"] += 1
            self._event("reassign", case, actor, now,
                        new_assignee=new_assignee)
            return self._case_view(case)

    def heartbeat(self, case_id, actor, version, now=None):
        actor = _nonempty(actor, "actor")
        now = self._now(now)
        with self._lock:
            self._expire_locked(now)
            case = self._case(case_id)
            if version != case["version"]:
                raise LedgerConflict(
                    "version_conflict",
                    "期望版本 %r，实际 %r" % (version, case["version"]))
            if case["status"] != "claimed" or case["assignee"] != actor:
                raise LedgerConflict("not_assignee", "当前不是该案的 assignee")
            case["last_activity"] = _iso(now)
            case["lease_expires"] = now + self.lease_seconds
            case["version"] += 1
            self._event("heartbeat", case, actor, now)
            return {"version": case["version"],
                    "lease_expires": case["lease_expires"]}

    # ───────────────────────── draft ─────────────────────────

    def _require_claim(self, case, actor, version):
        if case["status"] != "claimed" or case["assignee"] != actor:
            raise LedgerConflict("not_assignee", "当前不是该案的 assignee")
        if version != case["version"]:
            raise LedgerConflict(
                "version_conflict",
                "期望版本 %r，实际 %r" % (version, case["version"]))

    def _draft_view(self, draft):
        return copy.deepcopy(draft)

    def autosave(self, case_id, actor, version, *, form, notes,
                 evidence_selections, references, primary=True, now=None):
        actor = _nonempty(actor, "actor")
        if not isinstance(form, dict):
            raise LedgerValidation("bad_form", "form 必须是 dict")
        if not isinstance(notes, str):
            raise LedgerValidation("bad_notes", "notes 必须是字符串")
        if not isinstance(evidence_selections, list):
            raise LedgerValidation("bad_evidence_selections", "必须是 list")
        if not isinstance(references, list):
            raise LedgerValidation("bad_references", "必须是 list")
        now = self._now(now)
        with self._lock:
            self._expire_locked(now)
            case = self._case(case_id)
            self._require_claim(case, actor, version)
            content = {
                "form": copy.deepcopy(form), "notes": notes,
                "evidence_selections": copy.deepcopy(evidence_selections),
                "references": copy.deepcopy(references),
            }
            content_hash = _hash(content)
            seq = case["draft_seq"] + 1
            draft_id = "draft-" + _hash({
                "case_id": case_id, "seq": seq, "author": actor,
                "content_hash": content_hash,
            })[:16]
            draft = {
                "case_id": case_id, "draft_id": draft_id,
                "snapshot_seq": seq, "snapshot_at": _iso(now),
                "content_hash": content_hash, "author": actor,
                "derived_from": None, "snapshot_kind": "autosave",
                **content,
            }
            case["draft_seq"] = seq
            case["drafts"].append(draft)
            self._drafts[draft_id] = draft
            if primary:
                case["primary_draft_id"] = draft_id
            case["version"] += 1
            self._event("draft_autosave", case, actor, now,
                        draft_id=draft_id, content_hash=content_hash)
            return {"draft": self._draft_view(draft),
                    "version": case["version"], "formal": None}

    def get_draft(self, draft_id):
        with self._lock:
            draft = self._drafts.get(draft_id)
            if draft is None:
                raise LedgerNotFound("draft_not_found", "draft 不存在：%r" % draft_id)
            return self._draft_view(draft)

    def list_drafts(self, case_id):
        with self._lock:
            case = self._case(case_id)
            return [self._draft_view(d) for d in case["drafts"]]

    def adopt(self, case_id, actor, version, source_draft_id, now=None):
        actor = _nonempty(actor, "actor")
        now = self._now(now)
        with self._lock:
            self._expire_locked(now)
            case = self._case(case_id)
            self._require_claim(case, actor, version)
            source = self._drafts.get(source_draft_id)
            if source is None or source["case_id"] != case_id:
                raise LedgerNotFound("draft_not_found", "源 draft 不存在")
            if source_draft_id != case["primary_draft_id"]:
                raise LedgerConflict(
                    "not_primary",
                    "只能 adopt primary draft；其他 draft 只能引用片段")
            seq = case["draft_seq"] + 1
            draft_id = "draft-" + _hash({
                "case_id": case_id, "seq": seq, "author": actor,
                "derived_from": source_draft_id,
                "content_hash": source["content_hash"],
            })[:16]
            draft = {
                "case_id": case_id, "draft_id": draft_id,
                "snapshot_seq": seq, "snapshot_at": _iso(now),
                "content_hash": source["content_hash"], "author": actor,
                "derived_from": source_draft_id, "snapshot_kind": "adopt",
                "adopted_at": _iso(now),
                "form": copy.deepcopy(source["form"]),
                "notes": source["notes"],
                "evidence_selections": copy.deepcopy(source["evidence_selections"]),
                "references": copy.deepcopy(source["references"]),
            }
            case["draft_seq"] = seq
            case["drafts"].append(draft)
            self._drafts[draft_id] = draft
            case["primary_draft_id"] = draft_id
            case["version"] += 1
            self._event("draft_adopt", case, actor, now,
                        draft_id=draft_id, derived_from=source_draft_id)
            return {"draft": self._draft_view(draft), "version": case["version"]}

    def reference_fragment(self, case_id, actor, version, *,
                           source_draft_id, field_path, fragment, now=None):
        actor = _nonempty(actor, "actor")
        field_path = _nonempty(field_path, "field_path")
        if fragment is None or (isinstance(fragment, str) and not fragment.strip()):
            raise LedgerValidation("bad_fragment", "fragment 不能为空")
        now = self._now(now)
        with self._lock:
            self._expire_locked(now)
            case = self._case(case_id)
            self._require_claim(case, actor, version)
            source = self._drafts.get(source_draft_id)
            if source is None or source["case_id"] != case_id:
                raise LedgerNotFound("draft_not_found", "源 draft 不存在")
            if source_draft_id == case["primary_draft_id"]:
                raise LedgerConflict(
                    "primary_requires_adopt",
                    "primary draft 必须显式 adopt，不能只引用片段")
            ref = {
                "case_id": case_id, "source_draft_id": source_draft_id,
                "field_path": field_path, "fragment": copy.deepcopy(fragment),
                "author": actor, "at": _iso(now),
            }
            case["fragment_references"].append(ref)
            case["version"] += 1
            self._event("fragment_reference", case, actor, now,
                        source_draft_id=source_draft_id,
                        field_path=field_path)
            return {"reference": copy.deepcopy(ref), "version": case["version"]}

    # ───────────────────────── submit（唯一 formal 入口） ─────────────────────────

    def submit(self, case_id, actor, version, conclusion, now=None):
        actor = _nonempty(actor, "actor")
        if not isinstance(conclusion, dict):
            raise LedgerValidation("bad_conclusion", "conclusion 必须是 dict")
        now = self._now(now)
        with self._lock:
            self._expire_locked(now)
            case = self._case(case_id)
            self._require_claim(case, actor, version)
            formal_id = "formal-" + _hash({
                "case_id": case_id, "actor": actor, "at": _iso(now),
                "conclusion": conclusion,
            })[:16]
            formal = {
                "formal_id": formal_id, "case_id": case_id, "author": actor,
                "submitted_at": _iso(now),
                "from_draft_id": case["primary_draft_id"],
                "conclusion": copy.deepcopy(conclusion),
                "finding": copy.deepcopy(conclusion.get("finding")),
                "decision": copy.deepcopy(conclusion.get("decision")),
            }
            self._formal.append(formal)
            case["status"] = "closed"
            case["version"] += 1
            self._event("formal_submit", case, actor, now,
                        formal_id=formal_id)
            return {"formal": copy.deepcopy(formal), "version": case["version"]}

    # ───────────────────────── 抽样台账（L5-3） ─────────────────────────

    def open_sampling(self, cases, reviewer, now=None):
        reviewer = _nonempty(reviewer, "reviewer")
        if not isinstance(cases, list):
            raise LedgerValidation("bad_cases", "cases 必须是 list")
        now = self._now(now)
        layers = {label: [] for label in NON_BLOCK_LAYERS}
        block = []
        for item in cases:
            if not isinstance(item, dict):
                raise LedgerValidation("bad_case", "case 必须是 dict")
            case_id = _nonempty(item.get("case_id"), "case_id")
            label = item.get("label")
            if label not in ALL_LABELS:
                raise LedgerValidation("bad_label", "未知标签：%r" % (label,))
            if label == BLOCK_LAYER:
                block.append({"case_id": case_id, "reviewed": False})
            else:
                layers[label].append(case_id)
        with self._lock:
            self._sampling = {
                "round_id": "sample-" + _hash({
                    "reviewer": reviewer, "at": _iso(now)} )[:16],
                "reviewer": reviewer, "opened_at": _iso(now),
                "layers": layers, "block": block,
            }
            self._events.append({
                "kind": "sampling_open", "reviewer": reviewer,
                "at": _iso(now), "layers": {k: len(v) for k, v in layers.items()},
                "block": len(block),
            })
        return self.sampling_status()

    def record_block_review(self, case_id, reviewer, conclusion,
                            false_positive=False, now=None):
        reviewer = _nonempty(reviewer, "reviewer")
        conclusion = _nonempty(conclusion, "conclusion")
        if not isinstance(false_positive, bool):
            raise LedgerValidation("bad_false_positive", "false_positive 必须是 bool")
        now = self._now(now)
        with self._lock:
            if self._sampling is None:
                raise LedgerNotFound("no_sampling", "尚未开启抽样")
            entry = next((x for x in self._sampling["block"]
                          if x["case_id"] == case_id), None)
            if entry is None:
                raise LedgerNotFound("not_block_case", "不是 BLOCK 抽样条目")
            if entry["reviewed"]:
                raise LedgerConflict("already_reviewed", "该 BLOCK 已复核")
            entry.update({
                "reviewed": True, "reviewer": reviewer,
                "conclusion": conclusion, "false_positive": false_positive,
                "reviewed_at": _iso(now),
            })
            self._events.append({
                "kind": "block_review", "case_id": case_id,
                "reviewer": reviewer, "at": _iso(now),
            })
            return copy.deepcopy(entry)

    def sampling_status(self):
        with self._lock:
            if self._sampling is None:
                return {"status": "untested", "reason": "no_sampling_round",
                        "layers": {k: [] for k in NON_BLOCK_LAYERS},
                        "missing_layers": list(NON_BLOCK_LAYERS),
                        "block": {"total": 0, "reviewed": 0,
                                  "reviewed_ratio": 0.0,
                                  "false_positive_rate": None}}
            layers = copy.deepcopy(self._sampling["layers"])
            missing = [k for k in NON_BLOCK_LAYERS if not layers[k]]
            block = self._sampling["block"]
            total = len(block)
            reviewed = sum(1 for x in block if x.get("reviewed"))
            ratio = (reviewed / total) if total else 0.0
            complete = total == reviewed and not missing
            fp = sum(1 for x in block if x.get("false_positive"))
            return {
                "status": "ok" if complete else "untested",
                "layers": layers,
                "missing_layers": missing,
                "block": {
                    "total": total, "reviewed": reviewed,
                    "reviewed_ratio": round(ratio, 6),
                    "false_positive_rate": (
                        round(fp / total, 6) if complete and total else None),
                    "cases": copy.deepcopy(block),
                },
            }
