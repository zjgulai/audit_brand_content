#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""权威备份/空目录恢复自证。

主体：base/backend_recovery.py、base/business_event_store.py、
base/projection_store.py、base/projector.py。

★ C15（2026-10-24，#135 补票）：编排/运维配置中**不存在** session 库的备份任务
  （存在即红）。#135 实测：往 docker-compose.yml 的 services 加一个
  backup-session 服务、把 /backup/session.db 复制成 session-backup.db，
  本验证器只读 base/backend_recovery 的 excludes/哨兵，从不读编排配置 →
  整链 rc=0。C15 直接读仓库的 docker-compose.yml，按「session 库 × 拷贝/备份
  动词」的组合形状判（不点名键名 —— 键名会漏掉别的写法，形状不会），
  --controls 喂夹带 backup-session 服务的坏 compose 必须红、真 compose 不许误报。
"""
from __future__ import annotations

import json
import os
import re
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


# ── C15：session 库备份任务扫描（编排/运维配置）──────────────────────────
#
# ★ 判据按**形状**不按键名：某个具体的字面量（'session.db'）出现与否，
#   挡不住改一个名字的备份任务 —— 会漏的那条判据等于没有（§2.4 的教训）。
#   形状 = 「session 库特征」与「拷贝/备份/上传动词」在**同一个配置单元**
#   （compose 服务块 / cron 行 / systemd unit / launchd plist）里同时出现。
#   白名单注释里提到这些词不算（注释不算代码 —— 与 C5/J1a 同一条读法）。

SESSION_FILE_SHAPE = re.compile(
    r"session[\w.-]*\.(?:db|sqlite3?|sqlite-*|bak)"
    r"|sessions?\b.*(backup|bak|copy|dump)"
    r"|(?:backup|bak|copy|dump).*sessions?\b", re.I)

SESSION_DIR_SHAPE = re.compile(r"session[s]?(?![_-]?audit)", re.I)

COPY_VERB_SHAPE = re.compile(
    r"\b(?:cp|copy|rsync|tar|dump|sqlite3\b[^|\n;]*\"?\.(?:backup|dump)"
    r"|backup|upload|sync|s3\s+cp|gsutil\s+cp|aws\s+s3)\b", re.I)

LINE_COMMENT_SHAPE = re.compile(r"^\s*(?:#|//)")

OPS_CONFIG_CANDIDATES = (
    "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
    "deploy/crontab", "crontab", "deploy/backup.sh",
)


def scan_session_backup_tasks(text):
    """返回配置文本里「session 库 × 拷贝动词」的命中清单（用于报告与对照）。"""
    hits = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or LINE_COMMENT_SHAPE.match(line):
            continue
        if SESSION_DIR_SHAPE.search(line) and COPY_VERB_SHAPE.search(line):
            hits.append(line.strip())
    return hits


def scan_ops_configs(root):
    """扫仓库根的编排/运维配置文件（compose / crontab / deploy 脚本）。"""
    findings = []
    for name in OPS_CONFIG_CANDIDATES:
        path = Path(root) / name
        if not path.is_file():
            continue
        hits = scan_session_backup_tasks(
            path.read_text(encoding="utf-8", errors="replace"))
        if hits:
            findings.append((name, hits))
    return findings


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

        # C15 ★ 编排/运维配置里不许有 session 库的备份任务（#135 补票）。
        #   判据原文（验收表行 135 ①）：「编排/运维配置中不存在 session 库的
        #   备份任务（存在即红）」。#135 实测：compose 里加一个把 session.db
        #   拷成 session-backup.db 的服务后整链全绿 —— 三个 verifier 0 处读
        #   编排配置。这里逐个配置单元查「session 库特征 × 拷贝动词」组合。
        ops_findings = scan_ops_configs(ROOT)
        report(not ops_findings,
               "C15 编排/运维配置中不存在 session 库的备份任务",
               repr(ops_findings))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    print("----------------------------------------")
    if failed == 0:
        print("✅ %d/%d 全过" % (passed, passed + failed))
        return 0
    print("❌ %d passed, %d failed" % (passed, failed), file=sys.stderr)
    return 1


# ═══════════════════ --controls：#135 离线反向对照 ═══════════════════
#
# 判定体是 scan_session_backup_tasks()/scan_ops_configs()。#135 实测的变异是
# 往 compose services 加 backup-session 服务（cp session.db → session-backup.db）。
# 这里喂同形状的坏样本与各种「提到 session 但不是备份任务」的好样本：
#   坏样本（逐个必须红）：compose 服务块 / crontab 行 / 显式 session.db 字面量
#   好样本（不许误报）：真 compose、注释、auth/step-up 审计备份、主检查的
#                      excludes 判定体自身
# 任何一条不成立 → 退 1。

_BAD_COMPOSE = """\
name: bad
services:
  api:
    image: app:local
  backup-session:
    image: busybox:stable
    command: ["sh","-c","cp /backup/session.db /backup/session-backup.db"]
    volumes:
      - /srv/data/db:/backup
"""

_BAD_CRONTAB = """\
# hourly backup
0 * * * * root /usr/bin/rsync -a /srv/data/db/session.db /srv/backups/
"""

_GOOD_COMPOSE = """\
name: good
services:
  api:
    image: app:local
    volumes:
      - /srv/data/db:/data/db
    stop_grace_period: 30s
"""


def controls() -> int:
    fails = []
    n_cases = [0]

    def ok(name, cond, detail=""):
        n_cases[0] += 1
        cond = bool(cond)
        if not cond:
            fails.append(name)
        print("  %s %s %s" % ("✅" if cond else "❌", name, detail))

    print("=" * 78)
    print("backend_recovery · 离线反向对照（--controls · #135 编排备份任务）")
    print("=" * 78)

    # ── 坏样本：每种运维形状都必须红 ──
    hits_bad_compose = scan_session_backup_tasks(_BAD_COMPOSE)
    ok("坏样本（compose 加 backup-session 服务）→ 必须命中", bool(hits_bad_compose),
       repr(hits_bad_compose))
    ok("坏样本命中的是 backup-session 那一行（不是 api 块）",
       bool(hits_bad_compose) and all("session" in h.lower() for h in hits_bad_compose),
       repr(hits_bad_compose))
    hits_bad_cron = scan_session_backup_tasks(_BAD_CRONTAB)
    ok("坏样本（crontab 行 rsync session.db）→ 必须命中", bool(hits_bad_cron),
       repr(hits_bad_cron))
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "docker-compose.yml").write_text(_BAD_COMPOSE, encoding="utf-8")
        found = scan_ops_configs(d)
        ok("坏样本（落成真 docker-compose.yml）→ scan_ops_configs 必须报出",
           len(found) == 1 and found[0][0] == "docker-compose.yml", repr(found))

    # ── 好样本：不许误报 ──
    hits_good = scan_session_backup_tasks(_GOOD_COMPOSE)
    ok("好样本（真 compose，无备份任务）→ 不许命中", not hits_good, repr(hits_good))
    ok("好样本（注释里提到 session 备份）→ 不许命中（注释不算代码）",
       not scan_session_backup_tasks(
           "# rsync session.db daily  ← 只是注释\n   # cp session.db /bak\n"))
    ok("好样本（auth/step-up 审计的备份挂载）→ 不许命中（审计不是 session 库）",
       not scan_session_backup_tasks(
           '- /srv/data/logs/auth-audit.jsonl:/logs/auth-audit.jsonl:ro\n'
           '  cp auth-audit.jsonl /backup/\n'))
    ok("好样本（业务库/projection 备份任务）→ 不许命中（只管 session 库）",
       not scan_session_backup_tasks(
           "0 * * * * root /usr/bin/rsync -a /srv/data/db/projection.db /srv/backups/\n"))
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "docker-compose.yml").write_text(_GOOD_COMPOSE, encoding="utf-8")
        ok("好样本（真 compose 落盘）→ scan_ops_configs 不许报",
           scan_ops_configs(d) == [], "")

    print("-" * 78)
    if fails:
        print("❌ %d 项失败：%s" % (len(fails), fails))
        return 1
    print("✅ %d 项全过（该红、该绿都有）" % n_cases[0])
    return 0


if __name__ == "__main__":
    try:
        if "--controls" in sys.argv[1:]:
            sys.exit(controls())
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print("UNTESTED: 验收器自身异常: %s" % exc)
        sys.exit(2)
