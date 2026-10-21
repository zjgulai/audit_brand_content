#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""工作台权威数据备份/恢复。

备份只收已提交 manifest 及其引用对象，并可选收长期审计；运行态 session、
step-up、SQLite 投影、WAL/SHM、writer lock、staging 均不在输入集合中。
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
from pathlib import Path, PurePosixPath

from base.business_event_store import BusinessEventStore
from base.projection_store import ProjectionStore
from base.projector import Projector


class RecoveryError(Exception):
    def __init__(self, code, detail=""):
        self.code = code
        self.detail = detail
        super().__init__("%s: %s" % (code, detail))


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _write_private(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _safe_relative(raw, *, prefix=None):
    if not isinstance(raw, str) or not raw:
        raise RecoveryError("backup_path", "空路径")
    pure = PurePosixPath(raw)
    if pure.is_absolute() or ".." in pure.parts or "." in pure.parts:
        raise RecoveryError("backup_path", raw)
    if prefix is not None and (not pure.parts or pure.parts[0] != prefix):
        raise RecoveryError("backup_path", raw)
    return Path(*pure.parts)


def _business_manifests(authority_root):
    manifest_dir = Path(authority_root) / "manifests"
    if not manifest_dir.is_dir():
        raise RecoveryError("authority_manifests_missing")
    rows = []
    for path in sorted(manifest_dir.glob("*.json")):
        try:
            raw = path.read_bytes()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError, UnicodeError) as exc:
            raise RecoveryError("authority_manifest_unreadable", path.name) from exc
        if "authority_seq" not in value:
            continue
        try:
            seq = int(value["authority_seq"])
        except (TypeError, ValueError) as exc:
            raise RecoveryError("authority_sequence", path.name) from exc
        rows.append((seq, path.name, raw, value))
    rows.sort(key=lambda item: item[0])
    if not rows:
        raise RecoveryError("authority_empty")
    return rows


def _collect_authority(authority_root):
    root = Path(authority_root).resolve()
    rows = _business_manifests(root)
    collected = {}
    previous = None
    for expected, (seq, name, manifest_raw, manifest) in enumerate(rows, 1):
        if seq != expected:
            raise RecoveryError("authority_sequence", "expected=%d actual=%d" % (expected, seq))
        if manifest.get("prev_manifest_sha256") != previous:
            raise RecoveryError("authority_chain", "seq=%d" % seq)
        manifest_rel = Path("manifests") / name
        collected[manifest_rel.as_posix()] = manifest_raw
        entries = manifest.get("entries")
        if not isinstance(entries, list) or len(entries) != 1:
            raise RecoveryError("authority_entries", "seq=%d" % seq)
        entry = entries[0]
        rel = _safe_relative(entry.get("path"), prefix="events")
        source = root / rel
        try:
            raw = source.read_bytes()
        except OSError as exc:
            raise RecoveryError("authority_object_missing", rel.as_posix()) from exc
        if _sha(raw) != entry.get("sha256"):
            raise RecoveryError("authority_object_hash", rel.as_posix())
        collected[rel.as_posix()] = raw
        previous = _sha(manifest_raw)
    return collected, {
        "authority_seq": rows[-1][0],
        "manifest_sha256": previous,
        "command_count": len(rows),
    }


def _ensure_private_parent(path):
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    mode = parent.stat().st_mode & 0o777
    if mode & 0o077:
        raise RecoveryError("backup_permissions", "parent_not_private")


def _audit_snapshot(path):
    raw = Path(path).resolve().read_bytes()
    if raw and not raw.endswith(b"\n"):
        raise RecoveryError("audit_snapshot_incomplete", Path(path).name)
    for line in raw.splitlines():
        try:
            value = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise RecoveryError("audit_snapshot_invalid", Path(path).name) from exc
        if not isinstance(value, dict):
            raise RecoveryError("audit_snapshot_invalid", Path(path).name)
    return raw


def create_backup(authority_root, destination, *, audit_log=None,
                  audit_logs=None, now=None):
    """创建一个新备份目录；destination 已存在即拒绝。"""
    destination = Path(destination).resolve()
    if destination.exists():
        raise RecoveryError("backup_destination_exists")
    _ensure_private_parent(destination)
    objects, head = _collect_authority(authority_root)
    if audit_log is not None:
        audit = Path(audit_log).resolve()
        if audit.is_file():
            objects["audit/access.jsonl"] = _audit_snapshot(audit)
    for name, raw_path in sorted((audit_logs or {}).items()):
        if not isinstance(name, str) or not name.endswith(".jsonl"):
            raise RecoveryError("audit_name", str(name))
        _safe_relative("audit/" + name, prefix="audit")
        audit = Path(raw_path).resolve()
        if audit.is_file():
            objects["audit/" + name] = _audit_snapshot(audit)
    staging = Path(tempfile.mkdtemp(prefix=".%s-" % destination.name,
                                    dir=str(destination.parent)))
    try:
        os.chmod(staging, 0o700)
        entries = []
        for rel in sorted(objects):
            raw = objects[rel]
            _write_private(staging / _safe_relative(rel), raw)
            entries.append({"path": rel, "sha256": _sha(raw), "bytes": len(raw)})
        manifest = {
            "schema_version": "review-authority-backup/v1",
            "created_at": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if now is None else float(now))),
            "authority": head,
            "entries": entries,
            "excludes": [
                "session_db", "session_generation", "step_up", "projection_db", "sqlite_wal",
                "sqlite_shm", "writer_lock", "staging", "cache",
            ],
        }
        raw = (_canonical(manifest) + "\n").encode("utf-8")
        _write_private(staging / "backup-manifest.json", raw)
        os.replace(staging, destination)
        return manifest
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _verify_backup(backup_root):
    root = Path(backup_root).resolve()
    manifest_path = root / "backup-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise RecoveryError("backup_manifest_unreadable") from exc
    if manifest.get("schema_version") != "review-authority-backup/v1":
        raise RecoveryError("backup_schema")
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not entries:
        raise RecoveryError("backup_entries")
    expected = set()
    for entry in entries:
        rel = _safe_relative(entry.get("path"))
        rel_text = rel.as_posix()
        if rel_text in expected:
            raise RecoveryError("backup_duplicate", rel_text)
        if rel.parts[0] not in ("manifests", "events", "audit"):
            raise RecoveryError("backup_unexpected_kind", rel_text)
        expected.add(rel_text)
        try:
            raw = (root / rel).read_bytes()
        except OSError as exc:
            raise RecoveryError("backup_object_missing", rel_text) from exc
        if _sha(raw) != entry.get("sha256") or len(raw) != entry.get("bytes"):
            raise RecoveryError("backup_object_hash", rel_text)
    actual = set()
    for path in root.rglob("*"):
        if path.is_file() and path != manifest_path:
            actual.add(path.relative_to(root).as_posix())
    if actual != expected:
        raise RecoveryError("backup_file_set")
    return manifest


def restore_backup(backup_root, authority_destination, *, projection_db=None,
                   audit_destination=None, audit_destinations=None):
    """从已验真备份恢复；所有正式目标先预检，构建成功后才逐项 rename。"""
    backup_root = Path(backup_root).resolve()
    manifest = _verify_backup(backup_root)
    destination = Path(authority_destination).resolve()
    projection_path = Path(projection_db).resolve() if projection_db is not None else None
    requested_audits = dict(audit_destinations or {})
    if audit_destination is not None:
        requested_audits.setdefault("access.jsonl", audit_destination)
    backup_audits = {
        entry["path"].split("/", 1)[1]: entry["path"]
        for entry in manifest["entries"]
        if entry["path"].startswith("audit/")
    }
    audit_targets = {}
    for name, raw_path in requested_audits.items():
        if name not in backup_audits:
            continue
        if not isinstance(name, str) or not name.endswith(".jsonl"):
            raise RecoveryError("audit_name", str(name))
        audit_targets[name] = Path(raw_path).resolve()
    targets = [destination]
    if projection_path is not None:
        targets.append(projection_path)
    targets.extend(audit_targets.values())
    for index, left in enumerate(targets):
        for right in targets[index + 1:]:
            if left == right or left in right.parents or right in left.parents:
                raise RecoveryError("restore_targets_overlap")

    for path, code in (
        (destination, "restore_destination_exists"),
        (projection_path, "projection_destination_exists"),
    ):
        if path is not None and path.exists():
            raise RecoveryError(code)
    for path in audit_targets.values():
        if path.exists():
            raise RecoveryError("audit_destination_exists")
    _ensure_private_parent(destination)
    if projection_path is not None:
        _ensure_private_parent(projection_path)
    for path in audit_targets.values():
        _ensure_private_parent(path)

    authority_stage = Path(tempfile.mkdtemp(
        prefix=".%s-" % destination.name, dir=str(destination.parent)))
    projection_stage = None
    audit_stages = {}
    projection = None
    published = []
    try:
        os.chmod(authority_stage, 0o700)
        for entry in manifest["entries"]:
            rel = _safe_relative(entry["path"])
            if rel.parts[0] in ("manifests", "events"):
                _write_private(authority_stage / rel, (backup_root / rel).read_bytes())
        authority = BusinessEventStore(authority_stage)
        head = authority.head()
        declared = manifest.get("authority") or {}
        if (head.get("seq") != declared.get("authority_seq") or
                head.get("manifest_sha256") != declared.get("manifest_sha256")):
            raise RecoveryError("restore_authority_mismatch")

        projection_status = None
        if projection_path is not None:
            projection_stage = Path(tempfile.mkstemp(
                prefix=".%s-" % projection_path.name,
                dir=str(projection_path.parent))[1])
            projection_stage.unlink()
            projection = ProjectionStore(projection_stage)
            projection_status = Projector(authority, projection).rebuild()
            projection.close()
            projection = None
            for suffix in ("-wal", "-shm"):
                sidecar = Path(str(projection_stage) + suffix)
                if sidecar.exists():
                    raise RecoveryError("projection_sidecar_open")

        for name, target in audit_targets.items():
            fd, raw_stage = tempfile.mkstemp(
                prefix=".%s-" % target.name, dir=str(target.parent))
            os.close(fd)
            stage = Path(raw_stage)
            stage.unlink()
            _write_private(stage, (backup_root / backup_audits[name]).read_bytes())
            audit_stages[name] = stage

        # 所有内容与状态都已验证后，才让正式路径可见。下面每一步都只发布完整对象。
        os.replace(authority_stage, destination)
        published.append(destination)
        authority_stage = None
        if projection_stage is not None:
            os.replace(projection_stage, projection_path)
            published.append(projection_path)
            projection_stage = None
        for name in sorted(audit_stages):
            stage = audit_stages[name]
            target = audit_targets[name]
            os.replace(stage, target)
            published.append(target)
        audit_stages.clear()
        return {
            "authority": head,
            "projection": projection_status,
            "audit_restored": bool(audit_targets),
            "audit_files_restored": sorted(audit_targets),
            "sessions_restored": False,
        }
    except Exception:
        if projection is not None:
            projection.close()
        if authority_stage is not None:
            shutil.rmtree(authority_stage, ignore_errors=True)
        if projection_stage is not None:
            try:
                projection_stage.unlink()
            except FileNotFoundError:
                pass
        for stage in audit_stages.values():
            try:
                stage.unlink()
            except FileNotFoundError:
                pass
        # 若极罕见的 rename 阶段失败，回滚本次刚发布的全新目标，允许原命令重试。
        for path in reversed(published):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    path.unlink()
                except FileNotFoundError:
                    pass
        raise
