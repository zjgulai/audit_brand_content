#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BusinessEventStore 自证：仅临时仓外目录，不碰真实数据。

主体：base/business_event_store.py、base/artifact_store.py。
"""
from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

try:
    from base.business_event_store import (
        AuthorityConflict, AuthorityCorrupt, BusinessEventStore, WriterLease,
    )
except Exception as exc:  # noqa: BLE001
    print("UNTESTED: 无法导入 business_event_store: %s" % exc)
    sys.exit(2)


def actor(name="u1"):
    return {"principal_id": name, "tenant_id": "t1"}


def execute_claim(store, key="k1", principal="u1"):
    return store.execute(
        aggregate_id="case-1", command="claim", actor=actor(principal),
        expected_version=0, payload={}, idempotency_key=key, now=1000)


def concurrent_worker(root, start, queue, principal):
    start.wait()
    lease = WriterLease(os.path.join(root, "writer.lock"))
    try:
        lease.acquire()
        store = BusinessEventStore(root, lease=lease, clock=lambda: 1000)
        result = execute_claim(store, key="concurrent-" + principal, principal=principal)
        queue.put(("ok", result["batch"]["result_version"]))
    except Exception as exc:  # noqa: BLE001
        queue.put((getattr(exc, "code", type(exc).__name__), None))
    finally:
        lease.release()


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

    roots = []
    try:
        root = tempfile.mkdtemp(prefix="business-events-")
        roots.append(root)
        lease = WriterLease(os.path.join(root, "writer.lock")).acquire()
        store = BusinessEventStore(root, lease=lease, clock=lambda: 1000)

        # C0 正常 claim，批次与 manifest 只有一个可见结果
        first = execute_claim(store)
        report(first["replayed"] is False
               and first["batch"]["authority_seq"] == 1
               and first["batch"]["result"]["status"] == "claimed",
               "C0 claim 形成 seq=1 权威批次", repr(first))

        # C1 同 key 同请求回放，不多写
        again = execute_claim(store)
        report(again["replayed"] is True and len(store.batches()) == 1,
               "C1 同 key 同请求回放旧结果", repr(again))

        # C2 同 key 异请求（版本/body）拒绝
        try:
            store.execute(aggregate_id="case-1", command="claim", actor=actor(),
                          expected_version=1, payload={}, idempotency_key="k1", now=1001)
            conflict = False
        except AuthorityConflict as exc:
            conflict = exc.code == "idempotency_conflict"
        report(conflict and len(store.batches()) == 1,
               "C2 同 key 异请求 409 语义且不写", "")

        # C3 重启加载后仍回放同一个 key
        lease.release()
        lease = WriterLease(os.path.join(root, "writer.lock")).acquire()
        restarted = BusinessEventStore(root, lease=lease, clock=lambda: 1002)
        replay = execute_claim(restarted)
        report(replay["replayed"] is True and restarted.state("case-1")["version"] == 1,
               "C3 重启回放状态与幂等结果", repr(replay))
        # HTTP claim 不带 version：同 key 重试须绑定原批次版本，而不是当前版本。
        implicit_first = restarted.execute(
            aggregate_id="case-implicit", command="claim", actor=actor(),
            expected_version=None, payload={}, idempotency_key="implicit-claim", now=1003)
        implicit_replay = restarted.execute(
            aggregate_id="case-implicit", command="claim", actor=actor(),
            expected_version=None, payload={}, idempotency_key="implicit-claim", now=1004)
        report(implicit_first["batch"]["expected_version"] == 0
               and implicit_replay["replayed"] is True
               and restarted.state("case-implicit")["version"] == 1,
               "C3b 无 version claim 同 key 在状态前进后仍回放", repr(implicit_replay))

        # C4 第二存活写者拿不到 lease
        second = WriterLease(os.path.join(root, "writer.lock"))
        try:
            second.acquire()
            blocked = False
        except AuthorityConflict as exc:
            blocked = exc.code == "writer_lease_held"
        report(blocked, "C4 第二 writer 被拒", "")

        # C5 无 lease 的 store 不许执行写
        reader = BusinessEventStore(root, lease=None)
        try:
            reader.execute(aggregate_id="case-2", command="claim", actor=actor(),
                           expected_version=0, payload={}, idempotency_key="x")
            denied = False
        except AuthorityConflict as exc:
            denied = exc.code == "writer_lease_missing"
        report(denied, "C5 无 writer lease 写入拒绝", "")

        lease.release()

        # C6 两进程同时 claim：一个持 lease 成功，另一个明确失败
        root2 = tempfile.mkdtemp(prefix="business-concurrent-")
        roots.append(root2)
        start = multiprocessing.Event()
        queue = multiprocessing.Queue()
        ps = [multiprocessing.Process(target=concurrent_worker,
                                      args=(root2, start, queue, "u%d" % i))
              for i in (1, 2)]
        for process in ps:
            process.start()
        start.set()
        results = [queue.get(timeout=10) for _ in ps]
        for process in ps:
            process.join(10)
        oks = [x for x in results if x[0] == "ok"]
        report(len(oks) == 1 and len(results) == 2,
               "C6 双进程 writer 恰一成功", repr(results))

        # C7 manifest 序号断层启动必须红
        root3 = tempfile.mkdtemp(prefix="business-gap-")
        roots.append(root3)
        l3 = WriterLease(os.path.join(root3, "writer.lock")).acquire()
        s3 = BusinessEventStore(root3, lease=l3, clock=lambda: 1000)
        execute_claim(s3)
        l3.release()
        manifest = os.path.join(root3, "manifests", "cmd-000000000001.json")
        data = json.load(open(manifest, encoding="utf-8"))
        data["authority_seq"] = 2
        with open(manifest, "w", encoding="utf-8") as f:
            json.dump(data, f)
        try:
            BusinessEventStore(root3)
            corrupt = False
        except AuthorityCorrupt as exc:
            corrupt = exc.code == "authority_sequence"
        report(corrupt, "C7 authority 序号断层启动失败", "")

        # C8 事件内容哈希不符启动必须红
        root4 = tempfile.mkdtemp(prefix="business-hash-")
        roots.append(root4)
        l4 = WriterLease(os.path.join(root4, "writer.lock")).acquire()
        s4 = BusinessEventStore(root4, lease=l4, clock=lambda: 1000)
        execute_claim(s4)
        l4.release()
        with open(os.path.join(root4, "events", "cmd-000000000001.json"), "ab") as f:
            f.write(b"x")
        try:
            BusinessEventStore(root4)
            corrupt = False
        except AuthorityCorrupt as exc:
            corrupt = exc.code == "command_event_hash"
        report(corrupt, "C8 command event 哈希不符启动失败", "")

        # C9 manifest rename 前崩溃留下未提交 event；读者必须报红，唯一写者可清理后继续。
        root5 = tempfile.mkdtemp(prefix="business-orphan-event-")
        roots.append(root5)
        os.makedirs(os.path.join(root5, "events"), exist_ok=True)
        orphan = os.path.join(root5, "events", "cmd-000000000001.json")
        with open(orphan, "wb") as f:
            f.write(b"uncommitted-event")
        try:
            BusinessEventStore(root5)
            corrupt = False
        except AuthorityCorrupt as exc:
            corrupt = exc.code == "authority_uncommitted_event"
        l5 = WriterLease(os.path.join(root5, "writer.lock")).acquire()
        recovered = BusinessEventStore(root5, lease=l5, clock=lambda: 3000)
        committed = execute_claim(recovered, key="after-crash")
        report(corrupt and committed["batch"]["authority_seq"] == 1
               and len(recovered.batches()) == 1,
               "C9 未提交 event 读者红、唯一写者清理后可续写")
        l5.release()

    finally:
        for root in roots:
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
