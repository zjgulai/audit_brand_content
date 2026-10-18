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
    print("report-smoke -> %s" % report["case_id"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
