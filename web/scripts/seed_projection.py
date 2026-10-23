#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给本地联调投影补一条报告记录（只写临时投影，不碰仓库）。

smoke_end_to_end.py 只导出 cases.json；报告查看页需要一个真实可读的
/reports/{id}。本脚本读取临时 cases.json，写 reports.json。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from base import takedown as TD  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--projection", required=True)
    args = ap.parse_args()
    root = Path(args.projection)
    cases = json.loads((root / "cases.json").read_text(encoding="utf-8"))
    if not cases:
        print("cases.json 为空", file=sys.stderr)
        return 1
    case = cases[0]
    report = {
        "report_id": "report-smoke",
        "case_id": case.get("case_id"),
        "ir_id": (case.get("ir") or {}).get("ir_id"),
        "url": "https://static.example.com/reports/report-smoke.md",
        "published_at": "2026-10-19T00:00:00Z",
    }
    (root / "reports.json").write_text(
        json.dumps([report], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    notifications = [
        {
            "notification_id": "notif-smoke-1",
            "tenant": "t1",
            "recipient": "u_dp3",
            "type": "in_app",
            "case_id": case.get("case_id"),
            "title": "样例工作台内通知",
            "message": "案件已生成工作台内通知记录（不代表外部消息已送达）",
            "unread": True,
            "created_at": "2026-10-19T00:00:00Z",
        }
    ]
    (root / "notifications.json").write_text(
        json.dumps(notifications, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    takedown_tasks = [
        TD.new_task(
            task_id="td-smoke-1",
            case_id=case.get("case_id"),
            platform="amazon",
            tenant="t1",
            product_line="pump",
            created_at="2026-10-19T00:00:00Z",
            assignee="u_dp3",
        )
    ]
    (root / "takedown-tasks.json").write_text(
        json.dumps(takedown_tasks, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("report-smoke -> %s" % report["case_id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
