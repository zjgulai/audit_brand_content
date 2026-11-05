#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/ops_watch.py — 核心审核工作流稳定性与各阶段耗时巡检 + 运营日报/周报聚合（只读）

回答委托方 2026-10-31 三项要求的第 3 项：检查核心内容审核工作流的稳定性以及各阶段的耗时，
并为每日 P-1 运营日报、每周 P-1 运营周报（含耗时趋势 + 判例回流「规则缺口榜」）、
工作日 P-2 SLA 催办与 P-4 运维自检提供同源只读数据。

数据来源：
  1. 工作台投影库（review.db 的 review_cases 表）里每个案件的
     `report_snapshot.receipt.workflow_timing`（判定时冻结的那一份）与 `status`。
  2. 判例回流队列（`research/governance/_evidence/review_feedback_queue.jsonl`）。

不做判定、不写盘、不联网 —— 纯只读统计。阈值判红只是「建议人工看一眼」，
最终分流仍归工作台人工（ADR-0005 边界不变）。
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

#: 巡检阈值（毫秒 / 小时 / 比例）。上次调整：2026-11-05。
#: 依据：当前实测 P50 ≈ 个位数 ms（纯本地规则引擎），这里的阈值针对的是
#: workflow_timing 的步骤求和口径（不含模型外呼等待）。
THRESHOLDS = {
    "p50_ms": 5_000,                  # 单案判定步骤求和 P50 超过 5s → 异常
    "p90_ms": 30_000,                 # P90 超过 30s → 异常
    "max_ms": 120_000,                # 任一单案超过 2 分钟 → 异常
    "step_timeout_ms": 30_000,        # 单案耗时超过 30s 计入超时分子
    "failure_rate": 0.20,             # 通道解析失败率超过 20% → 异常
    "timeout_rate": 0.20,             # 通道超时率超过 20% → 异常
    "stuck_unassigned_hours": 24,     # 待领单超过 24h → 催办
}


def _percentile(sorted_vals: List[float], q: float) -> Optional[float]:
    if not sorted_vals:
        return None
    idx = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
    return round(sorted_vals[idx], 1)


def _timing_of(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    snap = state.get("report_snapshot")
    rc = (
        snap.get("receipt")
        if isinstance(snap, dict) and isinstance(snap.get("receipt"), dict)
        else {}
    )
    wt = rc.get("workflow_timing") or (state.get("ir") or {}).get("workflow_timing")
    return wt if isinstance(wt, dict) else None


def _parse_ts(created_at: Any) -> Optional[float]:
    if not created_at:
        return None
    try:
        s = str(created_at).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return float(calendar.timegm(dt.datetime.fromisoformat(s).utctimetuple()))
    except Exception:
        return None


def _age_hours(created_at: Any, now: float) -> Optional[float]:
    ts = _parse_ts(created_at)
    if ts is None:
        return None
    return round((now - ts) / 3600.0, 1)


def _case_summary(st: Dict[str, Any]) -> Dict[str, Any]:
    judgment = st.get("judgment") if isinstance(st.get("judgment"), dict) else {}
    ir = st.get("ir") if isinstance(st.get("ir"), dict) else {}
    decision = ir.get("decision") if isinstance(ir.get("decision"), dict) else {}
    label = (
        judgment.get("label")
        or decision.get("external_label")
        or decision.get("state")
        or st.get("label")
        or "REVIEW"
    )
    findings = ir.get("findings") if isinstance(ir.get("findings"), list) else []
    confirmed = [
        f
        for f in findings
        if isinstance(f, dict) and f.get("status") != "candidate"
    ]
    preview = [
        {
            "control_code": f.get("control_code") or f.get("rule_key") or "规则",
            "quote": str(f.get("quote") or "")[:30],
        }
        for f in confirmed[:3]
    ]
    return {
        "case_id": st.get("case_id"),
        "product_line": st.get("product_line") or "吸奶器",
        "content_type": (st.get("content") or {}).get("content_type")
        or st.get("content_type")
        or "文本",
        "entry_channel": st.get("entry_channel") or "群消息",
        "label": label,
        "status": st.get("status") or "unassigned",
        "assignee": st.get("assignee"),
        "confirmed_findings_count": len(confirmed),
        "findings_preview": preview,
        "created_at": st.get("created_at") or ir.get("created_at"),
    }


def summarize_states(
    states: List[Dict[str, Any]],
    *,
    now: float,
    thresholds: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """纯函数：对一组案件 state 汇总各通道耗时 P50/P90/max、失败率、超时率与积压。

    满足恒等式：每个 carrier 的 `n_timed + n_untimed == n`。
    """
    th = dict(THRESHOLDS)
    if thresholds:
        th.update(thresholds)

    by_carrier: Dict[str, Dict[str, Any]] = {}
    failures = {
        "parse_failed": 0,
        "judgment_failed": 0,
        "stuck_unassigned_gt_hours": 0,
    }
    breaches: List[str] = []
    cases_summary: List[Dict[str, Any]] = []
    total = 0

    for st in states:
        if not isinstance(st, dict):
            continue
        total += 1
        cases_summary.append(_case_summary(st))
        carrier = st.get("entry_channel") or "未知通道"
        unit = st.get("content") or {}
        parse_status = unit.get("parse_status", "ok")
        is_parse_failed = parse_status == "failed"
        if is_parse_failed:
            failures["parse_failed"] += 1

        slot = by_carrier.setdefault(
            carrier,
            {
                "n": 0,
                "n_timed": 0,
                "n_untimed": 0,
                "n_failed": 0,
                "n_timeout": 0,
                "timings": [],
                "step_totals": {},
                "slowest_step": None,
            },
        )
        slot["n"] += 1
        if is_parse_failed:
            slot["n_failed"] += 1

        wt = _timing_of(st)
        if wt and wt.get("status") == "ok" and wt.get("total_ms") is not None:
            t_ms = float(wt["total_ms"])
            slot["n_timed"] += 1
            slot["timings"].append(t_ms)
            if t_ms > th["step_timeout_ms"]:
                slot["n_timeout"] += 1
            for s_item in wt.get("slowest") or []:
                if isinstance(s_item, dict) and s_item.get("name"):
                    sname = str(s_item["name"])
                    dur = float(s_item.get("duration_ms") or 0.0)
                    slot["step_totals"][sname] = (
                        slot["step_totals"].get(sname, 0.0) + dur
                    )
        else:
            slot["n_untimed"] += 1

        if st.get("status") == "unassigned":
            created = st.get("created_at") or (st.get("ir") or {}).get("created_at")
            age_h = _age_hours(created, now)
            if age_h is not None and age_h > th["stuck_unassigned_hours"]:
                failures["stuck_unassigned_gt_hours"] += 1

    for carrier, slot in by_carrier.items():
        timings = sorted(slot.pop("timings"))
        step_totals = slot.pop("step_totals")
        if step_totals:
            slot["slowest_step"] = sorted(
                step_totals.items(), key=lambda kv: (-kv[1], kv[0])
            )[0][0]
        slot["p50_ms"] = _percentile(timings, 0.5)
        slot["p90_ms"] = _percentile(timings, 0.9)
        slot["max_ms"] = timings[-1] if timings else None
        denom = max(1, slot["n"])
        slot["failure_rate"] = round(slot["n_failed"] / denom, 4)
        slot["timeout_rate"] = round(slot["n_timeout"] / denom, 4)

        if slot["p50_ms"] is not None and slot["p50_ms"] > th["p50_ms"]:
            breaches.append(
                f"{carrier}：P50 耗时 {slot['p50_ms']}ms 超过阈值 {th['p50_ms']}ms"
            )
        if slot["p90_ms"] is not None and slot["p90_ms"] > th["p90_ms"]:
            breaches.append(
                f"{carrier}：P90 耗时 {slot['p90_ms']}ms 超过阈值 {th['p90_ms']}ms"
            )
        if slot["max_ms"] is not None and slot["max_ms"] > th["max_ms"]:
            breaches.append(
                f"{carrier}：最慢单案 {slot['max_ms']}ms 超过阈值 {th['max_ms']}ms"
            )
        if slot["failure_rate"] > th["failure_rate"]:
            breaches.append(
                f"{carrier}：失败率 {round(slot['failure_rate'] * 100, 1)}% 超过阈值 {round(th['failure_rate'] * 100, 1)}%"
            )
        if slot["timeout_rate"] > th["timeout_rate"]:
            breaches.append(
                f"{carrier}：超时率 {round(slot['timeout_rate'] * 100, 1)}% 超过阈值 {round(th['timeout_rate'] * 100, 1)}%"
            )

    if failures["stuck_unassigned_gt_hours"]:
        breaches.append(
            f"{failures['stuck_unassigned_gt_hours']} 单待领单超过 "
            f"{th['stuck_unassigned_hours']} 小时"
        )

    return {
        "ok": True,
        "untested_reason": "",
        "total": total,
        "by_carrier": by_carrier,
        "failures": failures,
        "breaches": breaches,
        "thresholds": th,
        "cases": cases_summary,
    }


def compute_timing_trend(
    states: List[Dict[str, Any]], *, now: float, days: int = 7
) -> Dict[str, Any]:
    """纯函数：同一份投影库按 [now-days, now] 与 [now-2*days, now-days) 两个窗口现算耗时趋势。"""
    win_sec = float(days) * 86400.0
    cur_cutoff = now - win_sec
    prev_cutoff = now - 2.0 * win_sec

    cur_states: List[Dict[str, Any]] = []
    prev_states: List[Dict[str, Any]] = []

    for st in states:
        if not isinstance(st, dict):
            continue
        created = st.get("created_at") or (st.get("ir") or {}).get("created_at")
        ts = _parse_ts(created)
        if ts is None or ts >= cur_cutoff:
            cur_states.append(st)
        elif ts >= prev_cutoff:
            prev_states.append(st)

    cur_sum = summarize_states(cur_states, now=now)
    prev_sum = summarize_states(prev_states, now=now)

    rows: List[Dict[str, Any]] = []
    all_carriers = sorted(
        set(cur_sum["by_carrier"].keys()) | set(prev_sum["by_carrier"].keys())
    )
    for c in all_carriers:
        c_cur = cur_sum["by_carrier"].get(c) or {}
        c_prev = prev_sum["by_carrier"].get(c) or {}
        cur_p50 = c_cur.get("p50_ms")
        prev_p50 = c_prev.get("p50_ms")
        cur_p90 = c_cur.get("p90_ms")
        prev_p90 = c_prev.get("p90_ms")
        delta_p90 = (
            round(cur_p90 - prev_p90, 1)
            if (cur_p90 is not None and prev_p90 is not None)
            else None
        )
        rows.append(
            {
                "carrier": c,
                "n_current": c_cur.get("n", 0),
                "n_previous": c_prev.get("n", 0),
                "p50_ms": cur_p50,
                "prev_p50_ms": prev_p50,
                "p90_ms": cur_p90,
                "prev_p90_ms": prev_p90,
                "p90_delta_ms": delta_p90,
                "failure_rate": c_cur.get("failure_rate", 0.0),
                "timeout_rate": c_cur.get("timeout_rate", 0.0),
            }
        )

    return {
        "window_days": int(days),
        "current_total": cur_sum["total"],
        "previous_total": prev_sum["total"],
        "rows": rows,
    }


def collect_ops_stats(
    db_path: Optional[Path] = None,
    *,
    now: Optional[float] = None,
    queue_path: Optional[Path] = None,
    days: int = 7,
) -> Dict[str, Any]:
    """读投影库与判例回流队列，产出稳定性、耗时趋势与规则缺口榜读数。**只读**，任何异常都落 untested 不抛。"""
    if db_path is None:
        try:
            from base.feishu_guard_ingest import workbench_data_root

            db_path = workbench_data_root() / "db" / "review.db"
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "untested_reason": f"解析投影库路径失败：{exc}",
                "total": 0,
                "by_carrier": {},
                "failures": {},
                "breaches": [],
                "thresholds": THRESHOLDS,
            }
    if not Path(db_path).exists():
        return {
            "ok": False,
            "untested_reason": f"投影库不存在：{db_path}",
            "total": 0,
            "by_carrier": {},
            "failures": {},
            "breaches": [],
            "thresholds": THRESHOLDS,
        }

    now_ts = time.time() if now is None else float(now)
    try:
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT state_json FROM review_cases").fetchall()
        conn.close()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "untested_reason": f"投影库读不出：{exc}",
            "total": 0,
            "by_carrier": {},
            "failures": {},
            "breaches": [],
            "thresholds": THRESHOLDS,
        }

    states: List[Dict[str, Any]] = []
    for (sj,) in rows:
        try:
            st = json.loads(sj)
            if isinstance(st, dict):
                states.append(st)
        except Exception:
            continue

    summary = summarize_states(states, now=now_ts)
    summary["trend"] = compute_timing_trend(states, now=now_ts, days=days)

    try:
        from base.precedent_feedback import collect_precedent_ranking

        summary["precedent"] = collect_precedent_ranking(
            queue_path=queue_path, days=days, now=now_ts
        )
    except Exception as exc:  # noqa: BLE001
        summary["precedent"] = {
            "ok": False,
            "untested_reason": f"规则缺口榜汇总失败：{exc}",
            "n_records": 0,
            "n_attributed": 0,
            "n_unattributed": 0,
            "ranking": [],
            "unattributed": {"n": 0, "why": {}},
        }

    return summary


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="工作流耗时与判例回流巡检")
    ap.add_argument("--db", type=str, default=None)
    ap.add_argument("--queue", type=str, default=None)
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()
    out = collect_ops_stats(
        db_path=Path(args.db) if args.db else None,
        queue_path=Path(args.queue) if args.queue else None,
        days=args.days,
    )
    print(json.dumps(out, ensure_ascii=False, indent=1))
