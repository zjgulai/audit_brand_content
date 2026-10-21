#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""权威备份/空目录恢复自证。

主体：base/backend_recovery.py、base/business_event_store.py、
base/projection_store.py、base/projector.py。
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from base.backend_recovery import RecoveryError, create_backup, restore_backup
    from base.business_event_store import BusinessEventStore, WriterLease
    from base.projection_store import ProjectionStore
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入恢复模块: %s" % exc)
    sys.exit(2)


def main():
    passed = failed = 0
    root = Path(tempfile.mkdtemp(prefix="backend-recovery-"))
    os.chmod(root, 0o700)

    def report(ok, name, detail=""):
        nonlocal passed, failed
        ok = bool(ok)
        print(("PASS" if ok else "FAIL") + ": " + name +
              ((" " + detail) if detail else ""),
              file=sys.stdout if ok else sys.stderr)
        passed += int(ok)
        failed += int(not ok)

    try:
        authority_root = root / "authority"
        lease = WriterLease(authority_root / "writer.lock").acquire()
        store = BusinessEventStore(authority_root, lease=lease, clock=lambda: 1000)
        actor = {"principal_id": "reviewer", "tenant_id": "t1"}
        store.execute(aggregate_id="case-restore", command="claim", actor=actor,
                      expected_version=0, payload={}, idempotency_key="restore-claim")
        store.execute(aggregate_id="case-restore", command="save_draft", actor=actor,
                      expected_version=1,
                      payload={"form": {"verdict": "REVIEW"}, "notes": "saved",
                               "evidence_selections": [], "references": []},
                      idempotency_key="restore-draft", now=1001)
        source_head = store.head()
        source_state = store.state("case-restore")
        lease.release()

        session = root / "session.db"
        projection_old = root / "old-projection.db"
        session.write_bytes(b"SESSION-SENTINEL")
        projection_old.write_bytes(b"PROJECTION-SENTINEL")
        (root / "session.db-wal").write_bytes(b"WAL-SENTINEL")
        audit = root / "audit.jsonl"
        audit.write_text('{"event":"AUDIT-SENTINEL"}\n', encoding="utf-8")
        auth_audit = root / "auth-audit.jsonl"
        auth_audit.write_text('{"event":"AUTH-AUDIT-SENTINEL"}\n', encoding="utf-8")
        step_audit = root / "step-up-audit.jsonl"
        step_audit.write_text('{"event":"STEP-AUDIT-SENTINEL"}\n', encoding="utf-8")

        backup = root / "backup-v1"
        manifest = create_backup(
            authority_root, backup, audit_log=audit,
            audit_logs={"auth-audit.jsonl": auth_audit,
                        "step-up-audit.jsonl": step_audit}, now=2000)
        names = {e["path"] for e in manifest["entries"]}
        report(names == {
            "manifests/cmd-000000000001.json",
            "manifests/cmd-000000000002.json",
            "events/cmd-000000000001.json",
            "events/cmd-000000000002.json",
            "audit/access.jsonl",
            "audit/auth-audit.jsonl",
            "audit/step-up-audit.jsonl",
        }, "C0 备份只收 manifest 引用对象与长期审计", repr(sorted(names)))
        raw = b"".join(path.read_bytes() for path in backup.rglob("*") if path.is_file())
        report(b"SESSION-SENTINEL" not in raw and b"PROJECTION-SENTINEL" not in raw
               and b"WAL-SENTINEL" not in raw,
               "C1 session/projection/WAL 哨兵未进入备份")
        report(set(manifest["excludes"]) >= {
            "session_db", "session_generation", "step_up", "projection_db", "sqlite_wal",
            "sqlite_shm", "writer_lock", "staging",
        }, "C2 备份契约显式登记排除项")

        restored_authority = root / "restored-authority"
        restored_projection = root / "restored" / "projection.db"
        restored_audit = root / "restored" / "access.jsonl"
        restored_auth_audit = root / "restored" / "auth-audit.jsonl"
        restored_step_audit = root / "restored" / "step-up-audit.jsonl"
        result = restore_backup(
            backup, restored_authority,
            projection_db=restored_projection,
            audit_destinations={
                "access.jsonl": restored_audit,
                "auth-audit.jsonl": restored_auth_audit,
                "step-up-audit.jsonl": restored_step_audit,
            })
        restored_store = BusinessEventStore(restored_authority)
        restored_db = ProjectionStore(restored_projection)
        report(restored_store.head() == source_head,
               "C3 空目录恢复后权威 head 逐字段一致", repr(result["authority"]))
        report(restored_store.state("case-restore") == source_state,
               "C4 空目录恢复后聚合状态逐字段一致")
        report(restored_db.status(restored_store.head())["status"] == "fresh",
               "C5 投影只靠恢复权威从零重建为 fresh")
        report(restored_db.get_case("case-restore") == source_state,
               "C6 重建投影与权威状态逐字段一致")
        report(result["sessions_restored"] is False
               and not (root / "restored" / "session.db").exists(),
               "C7 恢复不带 session/step-up")
        report(restored_audit.read_text(encoding="utf-8") == audit.read_text(encoding="utf-8")
               and restored_auth_audit.read_text(encoding="utf-8") ==
               auth_audit.read_text(encoding="utf-8")
               and restored_step_audit.read_text(encoding="utf-8") ==
               step_audit.read_text(encoding="utf-8"),
               "C8 access/auth/step-up 长期审计均可显式恢复")
        restored_db.close()

        # 坏备份必须先红，不能产生半恢复目录。
        event = backup / "events/cmd-000000000002.json"
        original = event.read_bytes()
        event.write_bytes(original + b"tamper")
        bad_destination = root / "bad-restore"
        try:
            restore_backup(backup, bad_destination)
            denied = False
        except RecoveryError as exc:
            denied = exc.code == "backup_object_hash"
        report(denied and not bad_destination.exists(),
               "C9 坏对象哈希拒绝且不产生恢复目录")
        event.write_bytes(original)

        # 已存在目的地一律拒绝，防覆盖已有权威/投影。
        try:
            restore_backup(backup, restored_authority)
            denied = False
        except RecoveryError as exc:
            denied = exc.code == "restore_destination_exists"
        report(denied, "C10 恢复不覆盖已有权威")

        # 备份内额外文件也红，不能夹带 session/私货。
        extra = backup / "session.db"
        extra.write_bytes(b"SMUGGLED")
        try:
            restore_backup(backup, root / "extra-restore")
            denied = False
        except RecoveryError as exc:
            denied = exc.code == "backup_file_set"
        report(denied, "C11 备份夹带额外文件即拒绝")
        extra.unlink()

        # 后半目标冲突必须在 authority 发布前拒绝，不留不可重试半恢复。
        conflict_authority = root / "conflict-authority"
        conflict_audit = root / "existing-audit.jsonl"
        conflict_audit.write_text("existing\n", encoding="utf-8")
        try:
            restore_backup(
                backup, conflict_authority,
                projection_db=root / "conflict-projection.db",
                audit_destination=conflict_audit)
            denied = False
        except RecoveryError as exc:
            denied = exc.code == "audit_destination_exists"
        report(denied and not conflict_authority.exists()
               and not (root / "conflict-projection.db").exists(),
               "C12 审计目标冲突时 authority/projection 都不落位")

        overlap_authority = root / "overlap-authority"
        overlap = root / "overlap-output"
        try:
            restore_backup(
                backup, overlap_authority, projection_db=overlap,
                audit_destination=overlap)
            denied = False
        except RecoveryError as exc:
            denied = exc.code == "restore_targets_overlap"
        report(denied and not overlap_authority.exists() and not overlap.exists(),
               "C13 projection/audit 目标碰撞必须拒绝")

        partial_audit = root / "partial-audit.jsonl"
        partial_audit.write_text('{"event":"half"}', encoding="utf-8")
        partial_backup = root / "partial-backup"
        try:
            create_backup(
                authority_root, partial_backup,
                audit_logs={"auth-audit.jsonl": partial_audit})
            denied = False
        except RecoveryError as exc:
            denied = exc.code == "audit_snapshot_incomplete"
        report(denied and not partial_backup.exists(),
               "C14 审计半行快照拒绝，不生成伪完整备份")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
