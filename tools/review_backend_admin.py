#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生产后端离线运维入口：权威备份、空目录恢复、投影重建。

主体：base/backend_recovery.py、base/business_event_store.py、
base/projection_store.py、base/projector.py。命令不读取凭据，不连接飞书。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from base.backend_recovery import create_backup, restore_backup  # noqa: E402
from base.business_event_store import BusinessEventStore, WriterLease  # noqa: E402
from base.projection_store import ProjectionStore  # noqa: E402
from base.projector import Projector  # noqa: E402


def _audits(directory):
    if directory is None:
        return {}
    root = Path(directory).expanduser().resolve()
    return {
        name: root / name
        for name in ("access.jsonl", "auth-audit.jsonl", "step-up-audit.jsonl")
        if (root / name).is_file()
    }


def backup(args):
    result = create_backup(
        args.authority, args.destination,
        audit_logs=_audits(args.audit_dir))
    print(json.dumps({
        "ok": True, "operation": "backup",
        "authority_seq": result["authority"]["authority_seq"],
        "entries": len(result["entries"]),
        "destination": str(Path(args.destination).expanduser().resolve()),
    }, ensure_ascii=False, sort_keys=True))


def restore(args):
    audit_targets = {}
    if args.audit_dir:
        root = Path(args.audit_dir).expanduser().resolve()
        audit_targets = {
            name: root / name
            for name in ("access.jsonl", "auth-audit.jsonl", "step-up-audit.jsonl")
        }
    result = restore_backup(
        args.backup, args.authority_destination,
        projection_db=args.projection_db,
        audit_destinations=audit_targets)
    print(json.dumps({
        "ok": True, "operation": "restore",
        "authority_seq": result["authority"]["seq"],
        "projection_status": ((result.get("projection") or {}).get("status")),
        "audit_files_restored": result.get("audit_files_restored") or [],
        "sessions_restored": result["sessions_restored"],
    }, ensure_ascii=False, sort_keys=True))


def rebuild(args):
    if not args.yes:
        raise SystemExit("rebuild 会清空并重建投影；必须显式带 --yes")
    authority_root = Path(args.authority).expanduser().resolve()
    lease = WriterLease(authority_root / "writer.lock").acquire()
    projection = None
    try:
        authority = BusinessEventStore(authority_root, lease=lease)
        projection = ProjectionStore(args.projection_db)
        result = Projector(authority, projection).rebuild()
    finally:
        if projection is not None:
            projection.close()
        lease.release()
    print(json.dumps({
        "ok": True, "operation": "rebuild",
        "status": result["status"],
        "applied_seq": result["projection"]["applied_seq"],
    }, ensure_ascii=False, sort_keys=True))


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("backup", help="备份已提交权威与长期审计")
    p.add_argument("--authority", required=True)
    p.add_argument("--destination", required=True)
    p.add_argument("--audit-dir")
    p.set_defaults(func=backup)

    p = sub.add_parser("restore", help="恢复到全新 authority/projection/audit 目标")
    p.add_argument("--backup", required=True)
    p.add_argument("--authority-destination", required=True)
    p.add_argument("--projection-db", required=True)
    p.add_argument("--audit-dir")
    p.set_defaults(func=restore)

    p = sub.add_parser("rebuild", help="从权威原地重建可删除投影")
    p.add_argument("--authority", required=True)
    p.add_argument("--projection-db", required=True)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=rebuild)
    return ap


def main():
    args = parser().parse_args()
    try:
        args.func(args)
        return 0
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({
            "ok": False,
            "error_code": getattr(exc, "code", type(exc).__name__),
        }, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
