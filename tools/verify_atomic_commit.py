#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_atomic_commit.py — P-1 原子提交验收（T0-04 / T0-04b）

全部在 mktemp 临时目录内执行，不碰真实数据根。
  C0–C5 六种进程内崩溃点
  C6    提交后删 blob → orphan
  C7/C8 stale lock 清理 + 活 PID 锁保留（反向对照）
  C9/C10 真实子进程 os._exit(9)（manifest rename 前/后）
  C11   manifest 与 recovery 索引逐条对拍
  C12  孤儿 blob → garbage
  C13  manifest 指向缺失文件 → orphan
  R1    去掉产物提升（单点提交 bug）→ orphan

退出码：
  0 = 全过
  1 = 有红
  2 = 未测（模块导入失败 / 验收器自身异常）—— 未测 ≠ 通过 ≠ 红
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

try:
    from base.artifact_store import ArtifactStore, SimulatedCrash
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 base.artifact_store: %s" % exc)
    sys.exit(2)


def _artifacts():
    return [
        {"kind": "blobs", "key": "blob-1", "data": b"hello-blob-1"},
        {"kind": "ir", "key": "ir-1", "data": b'{"ir":"one"}'},
        {"kind": "reports", "key": "report-1", "data": b"# report one\n"},
    ]


def _new_store():
    root = tempfile.mkdtemp(prefix="atomic-commit-")
    return root, ArtifactStore(root)


def _run_case(name, crash_at=None, bad_mode=None, post=None):
    root = None
    try:
        root, store = _new_store()
        try:
            store.commit("run-1", _artifacts(), crash_at=crash_at, bad_mode=bad_mode)
            outcome = None
        except SimulatedCrash as exc:
            outcome = str(exc)
        if post:
            post(store)
        state, detail = store.recover("run-1")
        return state, detail, outcome
    finally:
        if root and os.path.isdir(root):
            shutil.rmtree(root, ignore_errors=True)


def main():
    passed = 0
    failed = 0

    def report(ok, name, detail=""):
        nonlocal passed, failed
        if ok:
            print("PASS: %s" % name)
            passed += 1
        else:
            print("FAIL: %s %s" % (name, detail), file=sys.stderr)
            failed += 1

    # 0 正常提交
    state, detail, _ = _run_case("normal")
    report(state == "committed", "C0 正常提交 → committed", "got=%s %s" % (state, detail))

    # ① 写 staging 一半时崩溃
    state, detail, _ = _run_case("staging-half", crash_at=1)
    report(state == "uncommitted", "C1 staging 一半崩溃 → uncommitted", "got=%s %s" % (state, detail))

    # ② rename 到最终路径一半时崩溃
    state, detail, _ = _run_case("rename-half", crash_at=2)
    report(state == "uncommitted", "C2 rename 一半崩溃 → uncommitted", "got=%s %s" % (state, detail))

    # ③ 写 manifest.tmp 时崩溃
    state, detail, _ = _run_case("manifest-tmp", crash_at=3)
    report(state == "uncommitted", "C3 manifest.tmp 崩溃 → uncommitted", "got=%s %s" % (state, detail))

    # ④ rename manifest 前崩溃
    state, detail, _ = _run_case("before-manifest-rename", crash_at=4)
    report(state == "uncommitted", "C4 manifest rename 前崩溃 → uncommitted", "got=%s %s" % (state, detail))

    # ⑤ rename manifest 后、删 staging 前崩溃
    state, detail, _ = _run_case("after-manifest-rename", crash_at=5)
    report(state == "committed", "C5 manifest rename 后崩溃 → committed", "got=%s %s" % (state, detail))

    # ⑥ 提交后删掉一个 blob
    def _delete_blob(store):
        for dirpath, _dirnames, filenames in os.walk(store.blobs):
            for fn in filenames:
                os.unlink(os.path.join(dirpath, fn))
                return
    state, detail, _ = _run_case("delete-blob", post=_delete_blob)
    report(state == "orphan", "C6 提交后删 blob → orphan", "got=%s %s" % (state, detail))

    # C7 stale lock 清理（dead PID）
    root7 = tempfile.mkdtemp(prefix="lock-stale-")
    try:
        os.makedirs(os.path.join(root7, "locks"), exist_ok=True)
        lock7 = os.path.join(root7, "locks", "run-dead.lock")
        with open(lock7, "w", encoding="utf-8") as f:
            json.dump({"pid": 999999, "ts": time.time()}, f)
        ArtifactStore(root7)
        report(not os.path.exists(lock7), "C7 stale lock（dead PID）被清理", "")
    finally:
        shutil.rmtree(root7, ignore_errors=True)

    # C8 live lock 不得被清理（反向对照）
    root8 = tempfile.mkdtemp(prefix="lock-live-")
    try:
        os.makedirs(os.path.join(root8, "locks"), exist_ok=True)
        lock8 = os.path.join(root8, "locks", "run-live.lock")
        with open(lock8, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "ts": time.time() - 99999}, f)
        ArtifactStore(root8)
        report(os.path.exists(lock8), "C8 live PID lock 不被清理（反向对照）", "")
    finally:
        shutil.rmtree(root8, ignore_errors=True)

    def _hard_crash(root, run_id, crash_at):
        code = (
            "import base.artifact_store as m\n"
            "s = m.ArtifactStore(%r)\n"
            "arts = [{'kind':'blobs','key':'b','data':b'x'},"
            "{'kind':'reports','key':'r','data':b'# r'}]\n"
            "s.commit(%r, arts, hard_crash_at=%d)\n" % (root, run_id, crash_at))
        return subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT,
                              capture_output=True, text=True)

    # C9 真实进程崩溃：manifest rename 前
    root9 = tempfile.mkdtemp(prefix="hard-crash-4-")
    try:
        proc = _hard_crash(root9, "run-hard4", 4)
        store9 = ArtifactStore(root9)
        state, detail = store9.recover("run-hard4")
        lock9 = os.path.join(root9, "locks", "run-hard4.lock")
        mtmp9 = os.path.join(root9, "manifests", "run-hard4.json.tmp")
        mfinal9 = os.path.join(root9, "manifests", "run-hard4.json")
        report(proc.returncode == 9 and state == "uncommitted"
               and os.path.exists(mtmp9) and not os.path.exists(mfinal9)
               and not os.path.exists(lock9),
               "C9 真实进程崩溃（rename 前）→ uncommitted + 锁清理",
               "rc=%s state=%s detail=%s" % (proc.returncode, state, detail))
    finally:
        shutil.rmtree(root9, ignore_errors=True)

    # C10 真实进程崩溃：manifest rename 后
    root10 = tempfile.mkdtemp(prefix="hard-crash-5-")
    try:
        proc = _hard_crash(root10, "run-hard5", 5)
        store10 = ArtifactStore(root10)
        state, detail = store10.recover("run-hard5")
        mfinal10 = os.path.join(root10, "manifests", "run-hard5.json")
        report(proc.returncode == 9 and state == "committed"
               and os.path.exists(mfinal10),
               "C10 真实进程崩溃（rename 后）→ committed",
               "rc=%s state=%s detail=%s" % (proc.returncode, state, detail))
    finally:
        shutil.rmtree(root10, ignore_errors=True)

    # C11 manifest 与 recovery 索引逐条一致
    root11 = tempfile.mkdtemp(prefix="index-")
    try:
        store11 = ArtifactStore(root11)
        store11.commit("run-index", _artifacts())
        manifest = store11.read_manifest("run-index")
        index = store11.recovery_index("run-index")
        ok = (manifest is not None and len(manifest["entries"]) == 3
              and len(index) == 3
              and all(i["exists"] and i["actual_sha256"] is not None
                      for i in index)
              and all(e["path"] == i["path"] and e["sha256"] == i["actual_sha256"]
                      for e, i in zip(manifest["entries"], index)))
        report(ok, "C11 manifest 与 recovery 索引逐条一致", "")
    finally:
        shutil.rmtree(root11, ignore_errors=True)

    # C12 孤儿 blob → garbage
    root12 = tempfile.mkdtemp(prefix="garbage-")
    try:
        blobs = os.path.join(root12, "blobs")
        os.makedirs(blobs, exist_ok=True)
        with open(os.path.join(blobs, "deadbeef"), "wb") as f:
            f.write(b"orphan")
        store12 = ArtifactStore(root12)
        state, detail = store12.recover("run-garbage")
        report(state == "garbage", "C12 孤儿 blob → garbage",
               "state=%s %s" % (state, detail))
    finally:
        shutil.rmtree(root12, ignore_errors=True)

    # C13 manifest 指向缺失文件 → orphan
    root13 = tempfile.mkdtemp(prefix="missing-entry-")
    try:
        store13 = ArtifactStore(root13)
        store13.commit("run-miss", _artifacts())
        manifest = store13.read_manifest("run-miss")
        victim = os.path.join(root13, manifest["entries"][0]["path"])
        os.unlink(victim)
        state, detail = store13.recover("run-miss")
        report(state == "orphan" and "missing entry" in str(detail),
               "C13 manifest 指向缺失文件 → orphan",
               "state=%s %s" % (state, detail))
    finally:
        shutil.rmtree(root13, ignore_errors=True)

    # 反向对照：只 rename manifest、不把产物提升到最终路径 → 必须 orphan
    state, detail, _ = _run_case("manifest-only", bad_mode="manifest_only")
    report(state == "orphan", "R1 去掉产物提升（单点提交 bug）→ orphan", "got=%s %s" % (state, detail))

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
