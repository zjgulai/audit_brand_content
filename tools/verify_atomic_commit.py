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
  C14  多 run：B 未提交不得因 A 的已提交 blob 判 garbage
  C15  多 run + 真孤儿 blob → garbage
  C16  仓内数据根必须被拒
  C17  staging/blobs/manifests 跨文件系统必须被拒
  C18  manifest 指向 staging/.tmp → orphan
  R1    去掉产物提升（单点提交 bug，测试注入）→ orphan
  M-1   源码级变异：注释掉产物提升后整份验证器必须 rc=1，不许退 rc=2

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
import types
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRA_ROOT = os.environ.get("ATOMIC_STORE_ROOT")
sys.path.insert(0, REPO_ROOT)
if EXTRA_ROOT:
    sys.path.insert(0, EXTRA_ROOT)

try:
    from base import artifact_store as _store_mod
    from base.artifact_store import ArtifactStore, SimulatedCrash
    STORE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(_store_mod.__file__)))
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


def _run_case(name, crash_at=None, post=None):
    root = None
    try:
        root, store = _new_store()
        try:
            store.commit("run-1", _artifacts(), crash_at=crash_at)
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
        run_cwd = EXTRA_ROOT or REPO_ROOT
        return subprocess.run([sys.executable, "-c", code], cwd=run_cwd,
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
        if os.path.exists(victim):
            os.unlink(victim)
        state, detail = store13.recover("run-miss")
        report(state == "orphan" and "missing entry" in str(detail),
               "C13 manifest 指向缺失文件 → orphan",
               "state=%s %s" % (state, detail))
    finally:
        shutil.rmtree(root13, ignore_errors=True)

    # C14 多 run：另一个 run 的已提交 blob 不是本 run 的垃圾
    root14 = tempfile.mkdtemp(prefix="multi-run-")
    try:
        store14 = ArtifactStore(root14)
        store14.commit("run-A", _artifacts())
        state, detail = store14.recover("run-B")
        report(state == "uncommitted",
               "C14 多 run：B 未提交不得因 A 的 blob 判 garbage",
               "state=%s %s" % (state, detail))
    finally:
        shutil.rmtree(root14, ignore_errors=True)

    # C15 多 run + 真孤儿 blob → 仍必须 garbage
    root15 = tempfile.mkdtemp(prefix="multi-run-garbage-")
    try:
        store15 = ArtifactStore(root15)
        store15.commit("run-A", _artifacts())
        with open(os.path.join(store15.blobs, "deadbeef"), "wb") as f:
            f.write(b"orphan")
        state, detail = store15.recover("run-B")
        report(state == "garbage" and "unreferenced blob" in str(detail),
               "C15 多 run + 真孤儿 blob → garbage",
               "state=%s %s" % (state, detail))
    finally:
        shutil.rmtree(root15, ignore_errors=True)

    # C16 仓内数据根必须被拒（STORE_ROOT = 被导入模块自己的仓库根）
    try:
        ArtifactStore(STORE_ROOT)
        ok16 = False
        detail16 = "no exception"
    except RuntimeError as exc:
        ok16 = "outside the repository" in str(exc)
        detail16 = str(exc)
    report(ok16, "C16 仓内数据根被拒", detail16)

    # C17 staging/blobs/manifests 跨文件系统必须被拒
    root17 = tempfile.mkdtemp(prefix="same-fs-")
    try:
        store17 = ArtifactStore(root17)
        real_stat = os.stat

        def fake_stat(path, *args, **kwargs):
            p = os.path.abspath(path)
            dev = 2 if p.endswith(os.sep + "blobs") else 1
            return types.SimpleNamespace(st_dev=dev)

        with mock.patch("base.artifact_store.os.stat", fake_stat):
            try:
                store17._assert_same_fs()
                ok17 = False
                detail17 = "no exception"
            except RuntimeError as exc:
                ok17 = "same filesystem" in str(exc)
                detail17 = str(exc)
        report(ok17, "C17 跨文件系统被拒", detail17)
    finally:
        shutil.rmtree(root17, ignore_errors=True)

    # C18 manifest 指向 staging/.tmp → orphan
    root18 = tempfile.mkdtemp(prefix="manifest-staging-")
    try:
        store18 = ArtifactStore(root18)
        with open(os.path.join(store18.manifests, "run-stale.json"),
                  "w", encoding="utf-8") as f:
            json.dump({"schema_version": "atomic-manifest/1.0",
                       "run_id": "run-stale",
                       "entries": [{"path": "staging/run-stale/0.tmp",
                                    "sha256": "0" * 64}]}, f)
        state, detail = store18.recover("run-stale")
        report(state == "orphan" and "manifest points at staging path" in str(detail),
               "C18 manifest 指向 staging/.tmp → orphan",
               "state=%s %s" % (state, detail))
    finally:
        shutil.rmtree(root18, ignore_errors=True)

    # C19 崩溃遗留 staging：无活锁 → 启动清理
    root19 = tempfile.mkdtemp(prefix="staging-stale-")
    try:
        stale_dir = os.path.join(root19, "staging", "run-stale")
        os.makedirs(stale_dir, exist_ok=True)
        with open(os.path.join(stale_dir, "0.tmp"), "wb") as f:
            f.write(b"orphan")
        ArtifactStore(root19)
        report(not os.path.exists(stale_dir),
               "C19 无活锁的 staging 残留 → 启动清理", "")
    finally:
        shutil.rmtree(root19, ignore_errors=True)

    # C20 活锁对应的 staging 不得清理（反向对照）
    root20 = tempfile.mkdtemp(prefix="staging-live-")
    try:
        live_dir = os.path.join(root20, "staging", "run-live")
        os.makedirs(live_dir, exist_ok=True)
        with open(os.path.join(live_dir, "0.tmp"), "wb") as f:
            f.write(b"live")
        os.makedirs(os.path.join(root20, "locks"), exist_ok=True)
        with open(os.path.join(root20, "locks", "run-live.lock"),
                  "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "ts": time.time()}, f)
        ArtifactStore(root20)
        report(os.path.isdir(live_dir),
               "C20 活锁 staging 不被清理（反向对照）", "")
    finally:
        shutil.rmtree(root20, ignore_errors=True)

    # C21 从 manifest 重建投影：数量/路径/sha 全对
    root21 = tempfile.mkdtemp(prefix="projection-ok-")
    try:
        store21 = ArtifactStore(root21)
        store21.commit("run-proj", _artifacts())
        proj = store21.rebuild_projection("run-proj")
        report(proj["ok"] is True
               and proj["manifest_entries"] == 3
               and proj["disk_entries"] == 3
               and not proj["missing"] and not proj["extra"]
               and not proj["mismatched"],
               "C21 manifest 重建投影与磁盘逐条一致", repr(proj))
    finally:
        shutil.rmtree(root21, ignore_errors=True)

    # C22 manifest 多一条 → missing 红
    root22 = tempfile.mkdtemp(prefix="projection-extra-entry-")
    try:
        store22 = ArtifactStore(root22)
        store22.commit("run-extra", _artifacts())
        manifest = store22.read_manifest("run-extra")
        ghost = "blobs/" + "0" * 64
        manifest["entries"].append({"path": ghost, "sha256": "0" * 64})
        with open(os.path.join(store22.manifests, "run-extra.json"),
                  "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        proj = store22.rebuild_projection("run-extra")
        report(not proj["ok"] and ghost in proj["missing"],
               "C22 manifest 多一条 → missing 红", repr(proj))
    finally:
        shutil.rmtree(root22, ignore_errors=True)

    # C23 manifest 少一条 → extra 红
    root23 = tempfile.mkdtemp(prefix="projection-fewer-entry-")
    try:
        store23 = ArtifactStore(root23)
        store23.commit("run-few", _artifacts())
        manifest = store23.read_manifest("run-few")
        removed = manifest["entries"].pop()["path"]
        with open(os.path.join(store23.manifests, "run-few.json"),
                  "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        proj = store23.rebuild_projection("run-few")
        report(not proj["ok"] and removed in proj["extra"],
               "C23 manifest 少一条 → extra 红", repr(proj))
    finally:
        shutil.rmtree(root23, ignore_errors=True)

    # C24 文件 sha 不符 → mismatched 红
    root24 = tempfile.mkdtemp(prefix="projection-sha-")
    try:
        store24 = ArtifactStore(root24)
        store24.commit("run-sha", _artifacts())
        manifest = store24.read_manifest("run-sha")
        victim_rel = manifest["entries"][0]["path"]
        with open(os.path.join(root24, victim_rel), "ab") as f:
            f.write(b"x")
        proj = store24.rebuild_projection("run-sha")
        report(not proj["ok"] and victim_rel in proj["mismatched"],
               "C24 文件 sha 不符 → mismatched 红", repr(proj))
    finally:
        shutil.rmtree(root24, ignore_errors=True)

    # R1 测试注入（不改生产函数）：跳过产物提升，只 rename manifest
    rootR = tempfile.mkdtemp(prefix="manifest-only-")
    try:
        storeR = ArtifactStore(rootR)
        real_replace = os.replace

        def fake_replace(src, dst):
            d = os.path.abspath(os.path.dirname(dst))
            if d in (storeR.blobs, storeR.ir, storeR.receipts, storeR.reports):
                return None  # 故意不提升
            return real_replace(src, dst)

        with mock.patch("base.artifact_store.os.replace", fake_replace):
            storeR.commit("run-1", _artifacts())
        state, detail = storeR.recover("run-1")
        report(state == "orphan", "R1 去掉产物提升（测试注入）→ orphan",
               "got=%s %s" % (state, detail))
    finally:
        shutil.rmtree(rootR, ignore_errors=True)

    # M-1 自测：注释掉产物提升后，验证器必须 rc=1（不是 rc=2 未测）
    if os.environ.get("ATOMIC_SELFTEST_MUTATION") != "0":
        mut_root = tempfile.mkdtemp(prefix="atomic-mutation-")
        try:
            pkg = os.path.join(mut_root, "base")
            os.makedirs(pkg)
            src_path = os.path.join(REPO_ROOT, "base", "artifact_store.py")
            with open(src_path, encoding="utf-8") as f:
                src = f.read()
            needle = '                os.replace(a["_tmp"], final)\n'
            mutated = src.replace(
                needle, "                pass  # MUTATION: promotion disabled\n")
            if mutated == src:
                report(False, "M-1 无法构造产物提升变异", "needle not found")
            else:
                with open(os.path.join(pkg, "artifact_store.py"),
                          "w", encoding="utf-8") as f:
                    f.write(mutated)
                with open(os.path.join(pkg, "__init__.py"),
                          "w", encoding="utf-8") as f:
                    f.write("")
                env = os.environ.copy()
                env["ATOMIC_STORE_ROOT"] = mut_root
                env["ATOMIC_SELFTEST_MUTATION"] = "0"
                prev = env.get("PYTHONPATH")
                env["PYTHONPATH"] = mut_root + (
                    (os.pathsep + prev) if prev else "")
                proc = subprocess.run(
                    [sys.executable, os.path.abspath(__file__)],
                    cwd=REPO_ROOT, env=env, capture_output=True, text=True)
                blob = (proc.stdout or "") + (proc.stderr or "")
                report(proc.returncode == 1 and "FAIL:" in blob,
                       "M-1 注释掉产物提升 → rc=1（不是 rc=2 未测）",
                       "rc=%s tail=%s" % (proc.returncode, blob[-400:]))
        finally:
            shutil.rmtree(mut_root, ignore_errors=True)

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
