#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""base/artifact_store.py — P-1 跨产物原子提交（T0-04）

唯一可见提交点 = manifests/<run_id>.json 的 rename。
写序：
  ① staging/<run_id>/<name>.tmp 写 + fsync
  ② rename 到最终不可变路径（blobs/<sha256>、ir/<id>.json、receipts/<id>.json、reports/<id>.md）+ fsync 目录
  ③ manifests/<run_id>.json.tmp 写 + fsync
  ④ fsync manifests/ 目录
  ⑤ rename manifest.tmp -> manifest.json      ← 唯一可见提交点
  ⑥ fsync manifests/ 目录
  ⑦ 删 staging/<run_id>/

恢复四态：committed / orphan / uncommitted / garbage。
本模块只做物理提交与恢复；不判 state/layer、不渲染报告、不定义 schema。
"""

import hashlib
import json
import os
import re
import shutil
import time


class SimulatedCrash(Exception):
    """测试用故障注入；不用于生产。"""


# 无法读出 PID 的锁（旧格式 / 写到一半）要等这么久才清，避免把正在写的锁删掉。
LOCK_STALE_SECONDS = 3600


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # 进程存在但无权发信号
    except OSError:
        return False


class ArtifactStore(object):
    def __init__(self, root):
        self.root = os.path.abspath(root)
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if self.root == repo_root or self.root.startswith(repo_root + os.sep):
            raise RuntimeError("data root must be outside the repository: %s" % self.root)
        self.staging = os.path.join(self.root, "staging")
        self.blobs = os.path.join(self.root, "blobs")
        self.ir = os.path.join(self.root, "ir")
        self.receipts = os.path.join(self.root, "receipts")
        self.reports = os.path.join(self.root, "reports")
        self.events = os.path.join(self.root, "events")
        self.manifests = os.path.join(self.root, "manifests")
        self.locks = os.path.join(self.root, "locks")
        for d in (self.staging, self.blobs, self.ir, self.receipts,
                  self.reports, self.events, self.manifests, self.locks):
            os.makedirs(d, exist_ok=True)
        self._assert_same_fs()
        self._clean_stale_locks()
        self._clean_stale_staging()

    def _assert_same_fs(self):
        devs = set()
        for d in (self.staging, self.blobs, self.manifests):
            devs.add(os.stat(d).st_dev)
        if len(devs) != 1:
            raise RuntimeError("staging/blobs/manifests must be on the same filesystem")

    def _fsync_file(self, path):
        fd = os.open(path, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _fsync_dir(self, path):
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        except OSError:
            # macOS 对目录 fsync 可能返回 EINVAL；不阻塞提交，但写序仍按设计执行。
            pass
        finally:
            os.close(fd)

    def _clean_stale_locks(self):
        """清掉没有活主（PID 不存在）的锁；活 PID 一律保留（反向对照：C8）。"""
        if not os.path.isdir(self.locks):
            return
        now = time.time()
        for name in os.listdir(self.locks):
            if not name.endswith(".lock"):
                continue
            path = os.path.join(self.locks, name)
            pid = None
            ts = None
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("pid") is not None:
                    pid = int(data["pid"])
                if data.get("ts") is not None:
                    ts = float(data["ts"])
            except Exception:  # noqa: BLE001
                pass
            if pid is not None and _pid_alive(pid):
                continue
            if pid is not None:
                stale = True  # 死 PID：立即清
            else:
                if ts is None:
                    try:
                        ts = os.path.getmtime(path)
                    except OSError:
                        continue
                stale = (now - ts) > LOCK_STALE_SECONDS
            if stale:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def _lock_is_live(self, run_id):
        path = os.path.join(self.locks, run_id + ".lock")
        try:
            with open(path, encoding="utf-8") as f:
                pid = json.load(f).get("pid")
            return pid is not None and _pid_alive(int(pid))
        except Exception:  # noqa: BLE001
            return False

    def _clean_stale_staging(self):
        """清掉没有活锁的 staging 残留；活锁对应的 staging 一律保留。"""
        if not os.path.isdir(self.staging):
            return
        for name in os.listdir(self.staging):
            path = os.path.join(self.staging, name)
            if not os.path.isdir(path):
                continue
            if self._lock_is_live(name):
                continue
            shutil.rmtree(path, ignore_errors=True)

    def _lock(self, run_id):
        path = os.path.join(self.locks, run_id + ".lock")
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        try:
            payload = json.dumps(
                {"pid": os.getpid(), "ts": time.time()}).encode("utf-8")
            while payload:
                n = os.write(fd, payload)
                payload = payload[n:]
            os.fsync(fd)
        finally:
            os.close(fd)
        self._lock_path = path

    def _unlock(self):
        path = getattr(self, "_lock_path", None)
        if path and os.path.exists(path):
            try:
                os.unlink(path)
            except OSError:
                pass
        self._lock_path = None

    @staticmethod
    def _safe_key(key):
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", key):
            raise ValueError("artifact key 只允许 [A-Za-z0-9._-]：%r" % (key,))
        return key

    def _final_path(self, kind, key, data):
        key = self._safe_key(key)
        if kind == "blobs":
            return os.path.join(self.blobs, _sha256(data))
        if kind == "ir":
            return os.path.join(self.ir, key + ".json")
        if kind == "receipts":
            return os.path.join(self.receipts, key + ".json")
        if kind == "reports":
            return os.path.join(self.reports, key + ".md")
        if kind == "events":
            return os.path.join(self.events, key + ".json")
        raise ValueError("unknown artifact kind: %s" % kind)

    def commit(self, run_id, artifacts, crash_at=None, hard_crash_at=None,
               manifest_extra=None):
        """提交一次运行的全部产物；返回 manifest dict。

        `manifest_extra` 只允许补充非保留元数据；用于 authority_seq / prev hash。
        已存在 manifest 一律拒绝，防止同 run_id 覆盖历史。

        crash_at=1..5 为进程内故障注入（抛 SimulatedCrash）；
        hard_crash_at=4/5 在关键点直接 os._exit(9)（真实进程崩溃，跳过 finally）。
        """
        run_id = self._safe_key(run_id)
        mfinal = os.path.join(self.manifests, run_id + ".json")
        if os.path.exists(mfinal):
            raise FileExistsError("manifest 已存在，不许覆盖：%s" % run_id)
        self._lock(run_id)
        staging_run = os.path.join(self.staging, run_id)
        os.makedirs(staging_run, exist_ok=True)
        try:
            # ① staging 写 + fsync
            for i, a in enumerate(artifacts):
                tmp = os.path.join(staging_run, "%d.tmp" % i)
                with open(tmp, "wb") as f:
                    f.write(a["data"])
                    f.flush()
                    os.fsync(f.fileno())
                a["_tmp"] = tmp
                if crash_at == 1 and i == 0:
                    raise SimulatedCrash("staging_half")

            # ② rename 到最终不可变路径
            for i, a in enumerate(artifacts):
                final = self._final_path(a["kind"], a["key"], a["data"])
                a["_final"] = final
                os.makedirs(os.path.dirname(final), exist_ok=True)
                digest = _sha256(a["data"])
                if os.path.exists(final):
                    with open(final, "rb") as f:
                        existing = _sha256(f.read())
                    if existing != digest:
                        raise FileExistsError(
                            "不可变产物已存在且内容不同：%s" %
                            os.path.relpath(final, self.root))
                    os.unlink(a["_tmp"])
                else:
                    os.replace(a["_tmp"], final)
                self._fsync_dir(os.path.dirname(final))
                if crash_at == 2 and i == 0:
                    raise SimulatedCrash("rename_half")

            # ③ manifest.tmp
            entries = []
            for a in artifacts:
                entries.append({
                    "path": os.path.relpath(a["_final"], self.root),
                    "sha256": _sha256(a["data"]),
                })
            manifest = {
                "schema_version": "atomic-manifest/1.0",
                "run_id": run_id,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "entries": entries,
            }
            if manifest_extra is not None:
                if not isinstance(manifest_extra, dict):
                    raise TypeError("manifest_extra 必须是 dict")
                reserved = set(manifest) & set(manifest_extra)
                if reserved:
                    raise ValueError("manifest_extra 不许覆盖保留字段：%s" % sorted(reserved))
                manifest.update(manifest_extra)
            mtmp = os.path.join(self.manifests, run_id + ".json.tmp")
            with open(mtmp, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            if crash_at == 3:
                raise SimulatedCrash("manifest_tmp")

            # ④ fsync manifests/ 目录
            self._fsync_dir(self.manifests)
            if hard_crash_at == 4:
                os._exit(9)  # 真实崩溃：不执行 finally，锁留在盘上
            if crash_at == 4:
                raise SimulatedCrash("before_manifest_rename")

            # ⑤ 唯一可见提交点
            mfinal = os.path.join(self.manifests, run_id + ".json")
            os.replace(mtmp, mfinal)
            # ⑥ fsync manifests/ 目录
            self._fsync_dir(self.manifests)
            if hard_crash_at == 5:
                os._exit(9)
            if crash_at == 5:
                raise SimulatedCrash("after_manifest_rename")

            # ⑦ 删 staging
            shutil.rmtree(staging_run, ignore_errors=True)
            return manifest
        finally:
            self._unlock()

    def read_manifest(self, run_id):
        """读已提交的 manifest；不存在/读不出返回 None。"""
        mfinal = os.path.join(self.manifests, run_id + ".json")
        try:
            with open(mfinal, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def recovery_index(self, run_id):
        """按 manifest 逐条回读，返回实际索引（含 actual_sha256/exists）。

        与 recover() 同一份判据：路径、存在性、内容哈希。
        """
        manifest = self.read_manifest(run_id)
        if manifest is None:
            return []
        index = []
        for entry in manifest.get("entries", []):
            rel = entry.get("path", "")
            path = os.path.join(self.root, rel)
            exists = os.path.isfile(path)
            actual = None
            if exists:
                with open(path, "rb") as f:
                    actual = _sha256(f.read())
            index.append({
                "path": rel,
                "sha256": entry.get("sha256"),
                "actual_sha256": actual,
                "exists": exists,
            })
        return index

    def _committed_paths(self):
        """汇总**所有**已提交 manifest 引用的相对路径（多 run）。"""
        paths = set()
        if not os.path.isdir(self.manifests):
            return paths
        for name in os.listdir(self.manifests):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(self.manifests, name), encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:  # noqa: BLE001
                continue
            for entry in manifest.get("entries", []):
                rel = entry.get("path")
                if rel:
                    paths.add(os.path.normpath(rel))
        return paths

    def rebuild_projection(self, run_id):
        """从 manifest 重建投影，并与磁盘实际文件逐条对拍。

        返回 {ok, entries, missing, extra, mismatched, manifest_entries, disk_entries}：
          missing    = manifest 多出来的条目（磁盘没有）
          extra      = 磁盘多出来的文件（manifest 没有）
          mismatched = 路径存在但 sha256 不符
        其他 run 的 manifest 已引用的文件不计入本 run 的 extra（blobs 可共享）。
        """
        manifest = self.read_manifest(run_id)
        if manifest is None:
            return {"ok": False, "error": "manifest_missing", "entries": [],
                    "missing": [], "extra": [], "mismatched": [],
                    "manifest_entries": 0, "disk_entries": 0}
        expected = {}
        for entry in manifest.get("entries", []):
            rel = os.path.normpath(entry.get("path", ""))
            expected[rel] = entry.get("sha256")

        other = set()
        if os.path.isdir(self.manifests):
            for name in os.listdir(self.manifests):
                if not name.endswith(".json") or name == run_id + ".json":
                    continue
                try:
                    with open(os.path.join(self.manifests, name),
                              encoding="utf-8") as f:
                        m = json.load(f)
                except Exception:  # noqa: BLE001
                    continue
                for entry in m.get("entries", []):
                    rel = entry.get("path")
                    if rel:
                        other.add(os.path.normpath(rel))

        actual = {}
        for base in (self.blobs, self.ir, self.receipts, self.reports,
                     self.events):
            for dirpath, _dirnames, filenames in os.walk(base):
                for fn in filenames:
                    path = os.path.join(dirpath, fn)
                    rel = os.path.normpath(os.path.relpath(path, self.root))
                    if rel in other:
                        continue
                    with open(path, "rb") as f:
                        actual[rel] = _sha256(f.read())

        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        mismatched = sorted(k for k in set(expected) & set(actual)
                            if expected[k] != actual[k])
        entries = []
        for rel in sorted(set(expected) | set(actual)):
            entries.append({
                "path": rel,
                "manifest_sha256": expected.get(rel),
                "actual_sha256": actual.get(rel),
            })
        return {
            "ok": not (missing or extra or mismatched),
            "entries": entries,
            "missing": missing,
            "extra": extra,
            "mismatched": mismatched,
            "manifest_entries": len(expected),
            "disk_entries": len(actual),
        }

    def recover(self, run_id):
        """返回 (state, detail)。四态：committed / orphan / uncommitted / garbage。"""
        self._clean_stale_locks()
        mfinal = os.path.join(self.manifests, run_id + ".json")
        if os.path.exists(mfinal):
            try:
                with open(mfinal, encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception as exc:  # noqa: BLE001
                return "orphan", "manifest unreadable: %s" % exc
            for entry in manifest.get("entries", []):
                rel = entry.get("path", "")
                if rel.startswith("staging" + os.sep) or rel.endswith(".tmp"):
                    return "orphan", "manifest points at staging path: %s" % rel
                path = os.path.join(self.root, rel)
                if not os.path.isfile(path):
                    return "orphan", "missing entry: %s" % rel
                with open(path, "rb") as f:
                    if _sha256(f.read()) != entry.get("sha256"):
                        return "orphan", "hash mismatch: %s" % rel
            return "committed", manifest

        staging_run = os.path.join(self.staging, run_id)
        if os.path.isdir(staging_run):
            for _dirpath, _dirnames, filenames in os.walk(staging_run):
                if filenames:
                    return "uncommitted", "staging temp remains"
        mtmp = os.path.join(self.manifests, run_id + ".json.tmp")
        if os.path.exists(mtmp):
            return "uncommitted", "manifest.tmp remains"

        # 多 run 共用内容目录：只有**没有被任何已提交 manifest 引用**的对象才是垃圾。
        referenced = self._committed_paths()
        for base in (self.blobs, self.ir, self.receipts, self.reports,
                     self.events):
            for dirpath, _dirnames, filenames in os.walk(base):
                for fn in filenames:
                    rel = os.path.relpath(os.path.join(dirpath, fn), self.root)
                    if os.path.normpath(rel) not in referenced:
                        return "garbage", "unreferenced object: %s" % rel
        return "uncommitted", "nothing committed"
