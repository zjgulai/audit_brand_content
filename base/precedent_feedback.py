#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/precedent_feedback.py — 判例回流闭环：人工复核与机器五标签分歧提取、只追加队列与规则缺口榜

回答立项口径第四项交付「审核留存及反馈机制」的后半边：
当工作台执行 `submit_review` 或 `review_and_close` 结案后，若人工复核结论与机器五标签不一致，
自动把一条结构化候选记录追加到 `research/governance/_evidence/review_feedback_queue.jsonl`，
并供每周 P-1 运营周报汇总出「规则缺口榜」（rule_gap_ranking）。

三条硬纪律：
1. 纯函数判定：`derive_feedback` 与 `rule_gap_ranking` 不碰盘、不联网、不改入参；
2. 幂等只追加：以 `formal_id` 作为 `candidate_id`（幂等键），重放同 `formal_id` 不重复入队；
3. 诚实三态：队列文件不可读或全坏行时落 `ok=False` + `untested_reason`，不伪装成「0 条缺口」。
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QUEUE_REL = "research/governance/_evidence/review_feedback_queue.jsonl"
QUEUE_ENV = "SHOUHENG_FEEDBACK_QUEUE"

MACHINE_LABELS = ("PASS", "待自决", "REVIEW", "BLOCK", "未审查")

DIVERGENCE_KINDS = (
    "human_overrode_block",      # 机器 BLOCK → 人工放行 (PASS)
    "human_upgraded_to_block",   # 机器 PASS → 人工改判违规/要求修改 (BLOCK)
    "human_resolved_to_pass",    # 机器 REVIEW/待自决 → 人工确认放行 (PASS)
    "human_resolved_to_block",   # 机器 REVIEW/待自决 → 人工确认需修改 (BLOCK)
    "human_rejected_findings",   # 人工在 adjudicate_finding 中驳回了机器 candidate
    "human_reviewed_unreadable", # 机器 未审查 → 人工直接结案
    "unattributed",              # 人工结案带有分歧信号但缺方向
)

DIRECTIONS = ("over_strict", "under_strict", "capability_gap", "unknown")


def default_queue_path(env: Optional[Dict[str, str]] = None) -> Path:
    raw = (os.environ if env is None else env).get(QUEUE_ENV)
    if raw and str(raw).strip():
        return Path(str(raw).strip()).expanduser().resolve()
    return (REPO_ROOT / DEFAULT_QUEUE_REL).resolve()


def _iso_utc(ts: float) -> str:
    return dt.datetime.fromtimestamp(float(ts), tz=dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _extract_machine_summary(state: Dict[str, Any]) -> Dict[str, Any]:
    judgment = state.get("judgment") if isinstance(state.get("judgment"), dict) else {}
    ir = state.get("ir") if isinstance(state.get("ir"), dict) else {}
    decision = ir.get("decision") if isinstance(ir.get("decision"), dict) else {}
    label = (
        judgment.get("label")
        or decision.get("external_label")
        or decision.get("state")
        or state.get("label")
        or "REVIEW"
    )
    layer = judgment.get("layer") or decision.get("layer") or state.get("layer") or "DP3"
    findings = ir.get("findings") if isinstance(ir.get("findings"), list) else []

    control_codes: List[str] = []
    rule_keys: List[str] = []
    rejected_ids: List[str] = []
    confirmed_count = 0
    candidate_count = 0
    sample_quote = ""

    for f in findings:
        if not isinstance(f, dict):
            continue
        st = f.get("status")
        if st == "confirmed":
            confirmed_count += 1
        elif st == "candidate":
            candidate_count += 1
        elif st == "rejected":
            fid = str(f.get("finding_id") or "")
            if fid:
                rejected_ids.append(fid)
        cc = str(f.get("control_code") or "").strip()
        if cc and cc not in control_codes:
            control_codes.append(cc)
        rk = str(f.get("rule_key") or "").strip()
        if rk and rk not in rule_keys:
            rule_keys.append(rk)
        if not sample_quote and f.get("quote"):
            sample_quote = str(f.get("quote")).replace("\n", " ").strip()[:60]

    return {
        "label": str(label),
        "layer": str(layer),
        "findings_total": len(findings),
        "confirmed": confirmed_count,
        "candidate": candidate_count,
        "rejected_finding_ids": rejected_ids,
        "control_codes": control_codes,
        "rule_keys": rule_keys,
        "sample_quote": sample_quote,
    }


def _extract_human_signal(
    state: Dict[str, Any], command: str, detail: Optional[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    formals = state.get("formal_reviews")
    if not isinstance(formals, list) or not formals:
        return None
    target_id = (detail or {}).get("formal_id")
    formal = None
    if target_id:
        for item in reversed(formals):
            if isinstance(item, dict) and item.get("formal_id") == target_id:
                formal = item
                break
    if formal is None:
        formal = formals[-1] if isinstance(formals[-1], dict) else None
    if not isinstance(formal, dict):
        return None

    conclusion = formal.get("conclusion") if isinstance(formal.get("conclusion"), dict) else {}
    verdict = conclusion.get("verdict")
    verdict_choice = conclusion.get("verdict_choice") or conclusion.get("disposition")
    explicit_label = conclusion.get("human_label") or conclusion.get("final_label")
    notes = str(conclusion.get("review_notes") or "").replace("\n", " ").strip()

    return {
        "formal_id": str(formal.get("formal_id") or target_id or ""),
        "author": str(formal.get("author") or ""),
        "submitted_at": str(formal.get("submitted_at") or ""),
        "path": str(conclusion.get("path") or command),
        "verdict": str(verdict) if verdict in ("agree", "overturn") else None,
        "verdict_choice": (
            str(verdict_choice)
            if verdict_choice in ("uphold", "revise", "override_pass")
            else None
        ),
        "explicit_label": (
            str(explicit_label) if explicit_label in MACHINE_LABELS else None
        ),
        "review_notes_len": len(notes),
        "notes_excerpt": notes[:120],
        "adjudicated_finding_ids": list(conclusion.get("adjudicated_finding_ids") or []),
    }


def _classify_divergence(
    machine_label: str, human: Dict[str, Any], rejected_ids: List[str]
) -> Tuple[Optional[str], Optional[str], str, List[str]]:
    """返回 (implied_label, divergence_kind, direction, co_signals)。
    若人机完全一致（无分歧），返回 (implied_label, None, "none", [])。
    """
    verdict = human.get("verdict")
    choice = human.get("verdict_choice")
    explicit = human.get("explicit_label")
    co_signals: List[str] = []
    if rejected_ids:
        co_signals.append("human_rejected_findings")

    # 1. 显式给出了人工五标签
    if explicit in MACHINE_LABELS:
        if explicit == machine_label:
            if rejected_ids:
                return explicit, "human_rejected_findings", "over_strict", co_signals
            return explicit, None, "none", []
        if explicit == "PASS" and machine_label == "BLOCK":
            return "PASS", "human_overrode_block", "over_strict", co_signals
        if explicit == "BLOCK" and machine_label == "PASS":
            return "BLOCK", "human_upgraded_to_block", "under_strict", co_signals
        if explicit == "PASS" and machine_label in ("REVIEW", "待自决"):
            return "PASS", "human_resolved_to_pass", "over_strict", co_signals
        if explicit == "BLOCK" and machine_label in ("REVIEW", "待自决"):
            return "BLOCK", "human_resolved_to_block", "under_strict", co_signals
        return explicit, "unattributed", "unknown", co_signals

    # 2. 机器为「未审查」却被人工结案
    if machine_label == "未审查":
        return None, "human_reviewed_unreadable", "capability_gap", co_signals

    # 3. 机器为 BLOCK
    if machine_label == "BLOCK":
        if choice == "override_pass" or verdict == "overturn":
            return "PASS", "human_overrode_block", "over_strict", co_signals
        if choice in ("uphold", "revise") or verdict == "agree":
            if rejected_ids:
                return "BLOCK", "human_rejected_findings", "over_strict", co_signals
            return "BLOCK", None, "none", []
        if rejected_ids:
            return "BLOCK", "human_rejected_findings", "over_strict", co_signals
        return "BLOCK", None, "none", []

    # 4. 机器为 PASS
    if machine_label == "PASS":
        if choice == "revise" or verdict == "overturn":
            return "BLOCK", "human_upgraded_to_block", "under_strict", co_signals
        if choice in ("uphold", "override_pass") or verdict == "agree":
            if rejected_ids:
                return "PASS", "human_rejected_findings", "over_strict", co_signals
            return "PASS", None, "none", []
        if rejected_ids:
            return "PASS", "human_rejected_findings", "over_strict", co_signals
        return "PASS", None, "none", []

    # 5. 机器为 REVIEW / 待自决
    if machine_label in ("REVIEW", "待自决"):
        if choice == "override_pass" or verdict == "overturn":
            return "PASS", "human_resolved_to_pass", "over_strict", co_signals
        if choice == "revise":
            return "BLOCK", "human_resolved_to_block", "under_strict", co_signals
        if choice == "uphold" or verdict == "agree":
            if rejected_ids:
                return machine_label, "human_rejected_findings", "over_strict", co_signals
            return machine_label, None, "none", []
        if rejected_ids:
            return machine_label, "human_rejected_findings", "over_strict", co_signals
        return None, "unattributed", "unknown", co_signals

    return None, "unattributed", "unknown", co_signals


def derive_feedback(
    state: Dict[str, Any],
    *,
    command: str,
    detail: Optional[Dict[str, Any]] = None,
    now: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """纯函数：根据结案后的案件权威 state 派生一条判例回流候选记录。

    返回：
      - None：非结案命令或缺少 formal_reviews
      - {"skip": "no_divergence", "formal_id": ...}：人机一致，不写队列
      - 完整候选 dict（含 candidate_id = formal_id）：人机不一致，应追加进队列
    """
    if command not in ("submit_review", "review_and_close"):
        return None
    if not isinstance(state, dict):
        return None

    snap = copy.deepcopy(state)
    human = _extract_human_signal(snap, command, detail)
    if not human or not human.get("formal_id"):
        return None

    machine = _extract_machine_summary(snap)
    implied_label, kind, direction, co_signals = _classify_divergence(
        machine["label"], human, machine["rejected_finding_ids"]
    )
    if kind is None:
        return {"skip": "no_divergence", "formal_id": human["formal_id"]}

    ts = time.time() if now is None else float(now)
    return {
        "schema": "precedent-feedback-v1",
        "v": 1,
        "candidate_id": human["formal_id"],
        "formal_id": human["formal_id"],
        "case_id": str(snap.get("case_id") or ""),
        "tenant": str(snap.get("tenant") or ""),
        "product_line": str(snap.get("product_line") or "吸奶器"),
        "entry_channel": str(snap.get("entry_channel") or "未知通道"),
        "command": command,
        "actor": human["author"],
        "case_version": int(snap.get("version") or 0),
        "recorded_at": _iso_utc(ts),
        "recorded_ts": round(ts, 3),
        "machine": {
            "label": machine["label"],
            "layer": machine["layer"],
            "findings_total": machine["findings_total"],
            "confirmed": machine["confirmed"],
            "candidate": machine["candidate"],
            "control_codes": machine["control_codes"],
            "rule_keys": machine["rule_keys"],
            "sample_quote": machine["sample_quote"],
        },
        "human": {
            "verdict": human["verdict"],
            "verdict_choice": human["verdict_choice"],
            "explicit_label": human["explicit_label"],
            "implied_label": implied_label,
            "review_notes_len": human["review_notes_len"],
            "notes_excerpt": human["notes_excerpt"],
            "rejected_finding_ids": machine["rejected_finding_ids"],
            "adjudicated_finding_ids": human["adjudicated_finding_ids"],
        },
        "divergence": {
            "kind": kind,
            "direction": direction,
            "also": co_signals,
        },
    }


def merge_records(lines: Iterable[str]) -> Dict[str, Any]:
    """只追加 JSONL 的读侧合并（按 candidate_id 幂等去重，统计坏行而不静默丢弃）。"""
    by_id: Dict[str, Dict[str, Any]] = {}
    duplicates: List[str] = []
    bad_lines = 0

    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            bad_lines += 1
            continue
        if not isinstance(obj, dict) or not obj.get("candidate_id"):
            bad_lines += 1
            continue
        cid = str(obj["candidate_id"])
        if cid in by_id:
            duplicates.append(cid)
        by_id[cid] = obj

    return {
        "records": list(by_id.values()),
        "duplicates": duplicates,
        "bad_lines": bad_lines,
    }


class FeedbackQueue:
    """判例回流候选队列（append-only JSONL，按 candidate_id=formal_id 幂等）。"""

    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path).resolve() if path is not None else default_queue_path()

    def append(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        """追加一条分歧候选记录。**永不抛。**"""
        try:
            if not isinstance(rec, dict) or not rec.get("candidate_id"):
                return {"ok": False, "appended": False, "detail": "invalid_record"}
            cid = str(rec["candidate_id"])
            if self.path.exists():
                existing = self.read()
                if existing.get("ok"):
                    for item in existing.get("records") or []:
                        if item.get("candidate_id") == cid:
                            return {
                                "ok": True,
                                "appended": False,
                                "duplicate": True,
                                "candidate_id": cid,
                                "path": str(self.path),
                            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"
            fd = os.open(str(self.path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
            try:
                os.write(fd, line.encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
            return {
                "ok": True,
                "appended": True,
                "duplicate": False,
                "candidate_id": cid,
                "path": str(self.path),
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "appended": False,
                "detail": "append_failed:%s:%s" % (type(exc).__name__, exc),
            }

    def read(self) -> Dict[str, Any]:
        """读取并幂等合并队列。文件不存在时返回 ok=True, exists=False, records=[]。"""
        if not self.path.exists():
            return {
                "ok": True,
                "exists": False,
                "untested_reason": "",
                "path": str(self.path),
                "records": [],
                "duplicates": [],
                "bad_lines": 0,
            }
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                merged = merge_records(fh)
            if merged["bad_lines"] > 0 and not merged["records"]:
                return {
                    "ok": False,
                    "exists": True,
                    "untested_reason": "队列文件全部为损坏行（%d 行）" % merged["bad_lines"],
                    "path": str(self.path),
                    "records": [],
                    "duplicates": merged["duplicates"],
                    "bad_lines": merged["bad_lines"],
                }
            return {
                "ok": True,
                "exists": True,
                "untested_reason": "",
                "path": str(self.path),
                "records": merged["records"],
                "duplicates": merged["duplicates"],
                "bad_lines": merged["bad_lines"],
            }
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "exists": True,
                "untested_reason": "读取反馈队列失败：%s" % exc,
                "path": str(self.path),
                "records": [],
                "duplicates": [],
                "bad_lines": 0,
            }


def rule_gap_ranking(
    records: List[Dict[str, Any]],
    *,
    days: int = 7,
    now: Optional[float] = None,
    top_n: int = 5,
) -> Dict[str, Any]:
    """纯函数：汇总近 N 天的判例回流记录，生成 P-1 周报的「规则缺口榜」。

    恒等式：n_attributed + n_unattributed == n_records（窗口内总分歧记录数）。
    """
    ts_now = time.time() if now is None else float(now)
    cutoff = ts_now - float(days) * 86400.0

    in_win: List[Dict[str, Any]] = []
    for r in records or []:
        if not isinstance(r, dict):
            continue
        rts = r.get("recorded_ts")
        if isinstance(rts, (int, float)) and not isinstance(rts, bool):
            if float(rts) < cutoff:
                continue
        in_win.append(r)

    n_records = len(in_win)
    n_attributed = 0
    n_unattributed = 0
    unattributed_why: Dict[str, int] = {}
    buckets: Dict[str, Dict[str, Any]] = {}
    by_kind: Dict[str, int] = {}

    for r in in_win:
        div = r.get("divergence") if isinstance(r.get("divergence"), dict) else {}
        kind = str(div.get("kind") or "unattributed")
        direction = str(div.get("direction") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1

        machine = r.get("machine") if isinstance(r.get("machine"), dict) else {}
        codes = [str(c) for c in (machine.get("control_codes") or []) if str(c).strip()]
        rkeys = [str(k) for k in (machine.get("rule_keys") or []) if str(k).strip()]
        quote = str(machine.get("sample_quote") or "")
        human = r.get("human") if isinstance(r.get("human"), dict) else {}
        excerpt = str(human.get("notes_excerpt") or "")

        if kind == "unattributed":
            n_unattributed += 1
            unattributed_why["no_implied_label"] = (
                unattributed_why.get("no_implied_label", 0) + 1
            )
            continue

        if not codes:
            # 机器 PASS 漏报（人工升级为 BLOCK）时，机器未命中任何已有 control_code：
            # 归入「待新增规则（漏报候选）」，让「无对应规则键」的盲区在榜上显式可见。
            if direction == "under_strict":
                codes = ["待新增规则（漏报候选）"]
                rkeys = ["unmapped-under-strict"]
            else:
                n_unattributed += 1
                unattributed_why["no_control_code"] = (
                    unattributed_why.get("no_control_code", 0) + 1
                )
                continue

        n_attributed += 1
        for idx, code in enumerate(codes):
            rk = rkeys[idx] if idx < len(rkeys) else (rkeys[0] if rkeys else code)
            b = buckets.setdefault(
                code,
                {
                    "control_code": code,
                    "rule_key": rk,
                    "count": 0,
                    "direction_counts": {},
                    "kinds": {},
                    "case_ids": [],
                    "sample_quote": "",
                    "notes_excerpt": "",
                    "last_seen": "",
                },
            )
            b["count"] += 1
            b["direction_counts"][direction] = (
                b["direction_counts"].get(direction, 0) + 1
            )
            b["kinds"][kind] = b["kinds"].get(kind, 0) + 1
            cid = str(r.get("case_id") or "")
            if cid and cid not in b["case_ids"] and len(b["case_ids"]) < 5:
                b["case_ids"].append(cid)
            if quote and not b["sample_quote"]:
                b["sample_quote"] = quote
            if excerpt and not b["notes_excerpt"]:
                b["notes_excerpt"] = excerpt
            rec_at = str(r.get("recorded_at") or "")
            if rec_at > b["last_seen"]:
                b["last_seen"] = rec_at

    sorted_items = sorted(
        buckets.values(), key=lambda x: (-x["count"], x["control_code"])
    )
    ranking: List[Dict[str, Any]] = []
    for idx, item in enumerate(sorted_items[: max(1, int(top_n))], start=1):
        d_counts = item["direction_counts"]
        top_dir = (
            sorted(d_counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
            if d_counts
            else "unknown"
        )
        ranking.append(
            {
                "rank": idx,
                "control_code": item["control_code"],
                "rule_key": item["rule_key"],
                "count": item["count"],
                "direction": top_dir,
                "kinds": item["kinds"],
                "case_ids": item["case_ids"],
                "sample_quote": item["sample_quote"],
                "notes_excerpt": item["notes_excerpt"],
                "last_seen": item["last_seen"],
            }
        )

    return {
        "ok": True,
        "untested_reason": "",
        "window_days": int(days),
        "n_records": n_records,
        "n_attributed": n_attributed,
        "n_unattributed": n_unattributed,
        "by_kind": by_kind,
        "ranking": ranking,
        "unattributed": {"n": n_unattributed, "why": unattributed_why},
    }


def collect_precedent_ranking(
    *,
    queue_path: Optional[Path] = None,
    days: int = 7,
    now: Optional[float] = None,
    top_n: int = 5,
) -> Dict[str, Any]:
    """读取队列文件并计算规则缺口榜。读失败时保持 ok=False（未测）。"""
    q = FeedbackQueue(queue_path)
    loaded = q.read()
    if not loaded.get("ok"):
        return {
            "ok": False,
            "untested_reason": loaded.get("untested_reason") or "反馈队列不可读",
            "window_days": int(days),
            "n_records": 0,
            "n_attributed": 0,
            "n_unattributed": 0,
            "by_kind": {},
            "ranking": [],
            "unattributed": {"n": 0, "why": {}},
            "bad_lines": loaded.get("bad_lines", 0),
        }
    ranked = rule_gap_ranking(
        loaded.get("records") or [], days=days, now=now, top_n=top_n
    )
    ranked["queue_exists"] = bool(loaded.get("exists"))
    ranked["bad_lines"] = int(loaded.get("bad_lines") or 0)
    ranked["duplicates_count"] = len(loaded.get("duplicates") or [])
    return ranked


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="判例回流队列与规则缺口榜")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--queue", type=str, default=None)
    args = ap.parse_args()
    qpath = Path(args.queue) if args.queue else None
    out = collect_precedent_ranking(queue_path=qpath, days=args.days, top_n=args.top)
    print(json.dumps(out, ensure_ascii=False, indent=1))
